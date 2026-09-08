#!/usr/bin/env python3
"""Validate G1 schema-1 bundle, calibration, and qualification profile records."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
import json
import math
import os
import pathlib
import re
import stat
import struct
from typing import Iterable

from gpu_backend_recipe import (
    MAX_BUNDLE_ARTIFACT_BYTES,
    RecipeError,
    bounded_i64,
    bounded_text,
    canonical,
    lowercase_hex,
    retained_path,
    replay_source_snapshot,
    single_link_file_at,
    strict_object,
    validate_source_manifest,
)


MAX_EVIDENCE_FILES = 8192
MAX_PROFILE_BYTES = 256 * 1024
MAX_CALIBRATION_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = 256 * 1024
I64_MAX = 2**63 - 1
I64_MIN = -(2**63)
I32_MAX = 2**31 - 1
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
CASE_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,48}\Z")
LOGICAL_PATH = re.compile(
    r"<[a-z0-9][a-z0-9._-]{0,63}>:(?:owned|sha256:[0-9a-f]{64})\Z",
)
FAILURE_CATEGORIES = {
    "CONFIG", "SOURCE_IDENTITY", "PREPARATION", "BUILD", "BACKEND_UNAVAILABLE",
    "DEVICE_UNAVAILABLE", "BUNDLE_IDENTITY", "UNSUPPORTED_CAPABILITY", "MEMORY_BUDGET",
    "ALLOCATION", "TRANSFER", "COMPUTE", "NONFINITE", "DEVICE_LOST", "BUSY", "PROCESS",
    "PUBLICATION", "CLEANUP",
}
FAILURE_STAGES = {
    "options", "source", "compiler", "runtime", "candidate_build", "shim_build",
    "cpu_reference_build", "model", "device", "plan", "allocate", "upload", "prefill",
    "decode", "readback", "synchronize", "release", "case_spawn", "publication",
    "qualifier_cleanup",
}


def exact_keys(value: object, expected: tuple[str, ...], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or len(value) != len(expected) or set(value) != set(expected):
        raise RecipeError(f"{label} keys are invalid")
    return {key: value[key] for key in expected}


def parse_record(raw: bytes, maximum: int) -> dict[str, object]:
    if not raw or len(raw) > maximum or raw.startswith(b"\xef\xbb\xbf") \
            or not raw.endswith(b"\n"):
        raise RecipeError("record framing is invalid")
    return parse_json_object(raw, maximum)


def parse_json_object(raw: bytes, maximum: int) -> dict[str, object]:
    """Read a bounded JSON object without imposing a different format's LF convention."""
    if not raw or len(raw) > maximum or raw.startswith(b"\xef\xbb\xbf"):
        raise RecipeError("JSON object framing is invalid")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                RecipeError(f"invalid JSON constant: {constant}"),
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, UnicodeEncodeError) as exc:
        raise RecipeError("record is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RecipeError("record is not one JSON object")
    try:
        canonical(value)
    except UnicodeEncodeError as exc:
        raise RecipeError("record contains an invalid Unicode scalar") from exc
    return value


def normalize_source_manifest(value: object) -> dict[str, object]:
    result = exact_keys(value, (
        "schema_version", "artifact_kind", "source_kind", "repository", "object_format",
        "commit", "commit_object_sha256", "tree", "files",
    ), "source manifest")
    rows = result["files"]
    if isinstance(rows, list):
        result["files"] = [
            exact_keys(row, ("path", "mode", "bytes", "git_oid", "sha256"), "source file")
            for row in rows
        ]
    return validate_source_manifest(result)


def require_identifier(value: object, label: str, *, case: bool = False) -> str:
    if not isinstance(value, str) or not (CASE_IDENTIFIER if case else IDENTIFIER).fullmatch(value):
        raise RecipeError(f"{label} is not a valid identifier")
    return value


def require_enum(value: object, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise RecipeError(f"{label} is invalid")
    return value


def require_digest(value: object, label: str) -> str:
    return lowercase_hex(value, 64, label)


def require_path(value: object, label: str) -> str:
    return retained_path(value, label)


def require_i32_array(
    value: object, label: str, *, minimum: int = 0, maximum: int = 4096,
) -> list[int]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise RecipeError(f"{label} count is outside its bound")
    for ordinal, item in enumerate(value):
        bounded_i64(item, 0, I32_MAX, f"{label}[{ordinal}]")
    return value


def self_hash(value: dict[str, object], field: str, label: str) -> None:
    expected = require_digest(value[field], field)
    zeroed = dict(value)
    zeroed[field] = "0" * 64
    actual = hashlib.sha256(canonical(zeroed)).hexdigest()
    if actual != expected:
        raise RecipeError(f"{label} self identity does not match")


def file_ref(value: object, label: str) -> dict[str, object]:
    result = exact_keys(value, ("path", "sha256"), label)
    require_path(result["path"], f"{label}.path")
    require_digest(result["sha256"], f"{label}.sha256")
    return result


def identity(value: object, label: str) -> dict[str, object]:
    result = exact_keys(value, ("name", "version", "sha256"), label)
    bounded_text(result["name"], 1, 256, f"{label}.name")
    bounded_text(result["version"], 1, 4096, f"{label}.version")
    require_digest(result["sha256"], f"{label}.sha256")
    return result


def validate_runtime_option(value: object, *, embedded: bool) -> dict[str, object]:
    prefix = ("option_id",) if embedded else ()
    result = exact_keys(value, prefix + (
        "schema_version", "backend", "device", "backend_bundle", "placement",
        "host_budget_bytes", "device_budget_bytes", "prefetch",
    ), "runtime option")
    if embedded:
        require_identifier(result["option_id"], "option_id")
    bounded_i64(result["schema_version"], 1, 1, "runtime option schema_version")
    require_enum(result["backend"], {"metal", "cuda"}, "runtime option backend")
    bounded_text(result["device"], 1, 256, "runtime option device")
    require_path(result["backend_bundle"], "runtime option backend_bundle")
    if result["placement"] != "resident" or result["prefetch"] != "off":
        raise RecipeError("runtime option placement or prefetch is invalid")
    bounded_i64(result["host_budget_bytes"], 1, I64_MAX, "host_budget_bytes")
    bounded_i64(result["device_budget_bytes"], 1, I64_MAX, "device_budget_bytes")
    return result


def validate_bundle(value: object, ggml_source: dict[str, object]) -> dict[str, object]:
    result = exact_keys(value, (
        "schema_version", "artifact_kind", "bundle_id", "backend", "ggml", "target",
        "toolchain", "build_flags", "artifacts",
    ), "backend bundle")
    bounded_i64(result["schema_version"], 1, 1, "bundle schema_version")
    if result["artifact_kind"] != "GPU_BACKEND_BUNDLE":
        raise RecipeError("backend bundle kind is invalid")
    backend = require_enum(result["backend"], {"metal", "cuda"}, "bundle backend")

    ggml = exact_keys(result["ggml"], ("commit", "source_manifest_sha256", "version"),
                      "bundle ggml")
    result["ggml"] = ggml
    oid_width = 40 if ggml_source["object_format"] == "sha1" else 64
    lowercase_hex(ggml["commit"], oid_width, "bundle ggml commit")
    require_digest(ggml["source_manifest_sha256"], "bundle ggml manifest digest")
    bounded_text(ggml["version"], 1, 4096, "bundle ggml version")
    if ggml_source["source_kind"] != "ggml" or ggml["commit"] != ggml_source["commit"]:
        raise RecipeError("bundle does not bind the supplied ggml source")
    if ggml["source_manifest_sha256"] != hashlib.sha256(canonical(ggml_source)).hexdigest():
        raise RecipeError("bundle ggml source manifest digest does not match")

    target = exact_keys(result["target"], ("os", "arch", "gpu_architectures"),
                        "bundle target")
    result["target"] = target
    target_os = require_enum(target["os"], {"macos", "linux"}, "bundle target os")
    target_arch = require_enum(target["arch"], {"aarch64", "x86_64"}, "bundle target arch")
    architectures = target["gpu_architectures"]
    if not isinstance(architectures, list) or not 1 <= len(architectures) <= 32:
        raise RecipeError("bundle GPU architecture count is outside its bound")
    if len(set(architectures)) != len(architectures):
        raise RecipeError("bundle GPU architectures are duplicated")
    for ordinal, architecture in enumerate(architectures):
        require_identifier(architecture, f"gpu_architectures[{ordinal}]")
    if backend == "metal" and (target_os, target_arch) != ("macos", "aarch64"):
        raise RecipeError("Metal bundle target is invalid")
    if backend == "cuda" and (target_os, target_arch) != ("linux", "x86_64"):
        raise RecipeError("CUDA bundle target is invalid")

    toolchain = exact_keys(result["toolchain"],
                           ("c_compiler", "cxx_compiler", "sdk", "toolkit"),
                           "bundle toolchain")
    for key in toolchain:
        toolchain[key] = identity(toolchain[key], f"bundle toolchain {key}")
    result["toolchain"] = toolchain
    toolkit = toolchain["toolkit"]
    assert isinstance(toolkit, dict)
    is_none = toolkit == {
        "name": "none",
        "version": "none",
        "sha256": hashlib.sha256(b"").hexdigest(),
    }
    if (backend == "metal" and not is_none) or (backend == "cuda" and is_none):
        raise RecipeError("bundle toolkit identity does not match backend")

    build_flags = result["build_flags"]
    if not isinstance(build_flags, list) or len(build_flags) > 128:
        raise RecipeError("bundle build flag count is outside its bound")
    for ordinal, flag in enumerate(build_flags):
        bounded_text(flag, 1, 4096, f"build_flags[{ordinal}]")
        if "\x00" in flag:
            raise RecipeError(f"build_flags[{ordinal}] contains NUL")

    artifacts = result["artifacts"]
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 128:
        raise RecipeError("bundle artifact count is outside its bound")
    previous: tuple[str, str] | None = None
    paths: set[str] = set()
    total = 0
    for ordinal, raw_artifact in enumerate(artifacts):
        artifact = exact_keys(raw_artifact, ("role", "path", "bytes", "sha256"),
                              f"artifacts[{ordinal}]")
        role = require_enum(artifact["role"], {
            "shared_library", "backend_plugin", "kernel_binary", "shader_library", "metadata",
        }, f"artifacts[{ordinal}].role")
        path = require_path(artifact["path"], f"artifacts[{ordinal}].path")
        order = (role, path)
        if previous is not None and order <= previous:
            raise RecipeError("bundle artifacts are not strictly sorted by role and path")
        previous = order
        if path in paths:
            raise RecipeError("bundle artifact path is duplicated")
        paths.add(path)
        size = bounded_i64(artifact["bytes"], 1, MAX_BUNDLE_ARTIFACT_BYTES,
                           f"artifacts[{ordinal}].bytes")
        total += size
        if total > MAX_BUNDLE_ARTIFACT_BYTES:
            raise RecipeError("bundle artifact aggregate exceeds its bound")
        require_digest(artifact["sha256"], f"artifacts[{ordinal}].sha256")
        artifacts[ordinal] = artifact
    self_hash(result, "bundle_id", "backend bundle")
    return result


def f32_tolerance(value: object, label: str) -> str:
    bits = lowercase_hex(value, 8, label)
    number = struct.unpack(">f", bytes.fromhex(bits))[0]
    if not math.isfinite(number) or number < 0:
        raise RecipeError(f"{label} is not finite and nonnegative")
    return bits


def f64_nonnegative(value: object, label: str) -> str:
    bits = lowercase_hex(value, 16, label)
    number = struct.unpack(">d", bytes.fromhex(bits))[0]
    if not math.isfinite(number) or number < 0:
        raise RecipeError(f"{label} is not finite and nonnegative")
    return bits


def validate_calibration(value: object) -> dict[str, object]:
    result = exact_keys(value, (
        "schema_version", "artifact_kind", "calibration_id", "backend", "bundle_id", "model",
        "precision", "comparison", "cases",
    ), "numeric calibration")
    bounded_i64(result["schema_version"], 1, 1, "calibration schema_version")
    if result["artifact_kind"] != "GPU_NUMERIC_CALIBRATION":
        raise RecipeError("numeric calibration kind is invalid")
    require_enum(result["backend"], {"metal", "cuda"}, "calibration backend")
    require_digest(result["bundle_id"], "calibration bundle_id")

    model = exact_keys(result["model"],
                       ("model_id", "model_sha256", "pack_sha256", "geometry_sha256",
                        "quantization"), "calibration model")
    result["model"] = model
    require_enum(model["model_id"], {"qwen2", "olmoe"}, "calibration model_id")
    for key in ("model_sha256", "pack_sha256", "geometry_sha256"):
        require_digest(model[key], f"calibration {key}")
    if model["quantization"] != "Q4_K_M" or result["precision"] != "f32":
        raise RecipeError("calibration quantization or precision is invalid")

    comparison = exact_keys(result["comparison"], (
        "absolute_tolerance_f32_bits", "relative_tolerance_f32_bits",
        "near_tie_tolerance_f32_bits", "nonfinite", "reference", "layer_scope", "topk_rule",
    ), "calibration comparison")
    result["comparison"] = comparison
    for key in (
        "absolute_tolerance_f32_bits", "relative_tolerance_f32_bits",
        "near_tie_tolerance_f32_bits",
    ):
        f32_tolerance(comparison[key], key)
    if comparison["nonfinite"] != "reject" or comparison["reference"] != "cpu-same-build" \
            or comparison["layer_scope"] != "all" \
            or comparison["topk_rule"] != "same-ordered-ids-or-declared-near-tie":
        raise RecipeError("calibration comparison policy is invalid")

    cases = result["cases"]
    if not isinstance(cases, list) or not 2 <= len(cases) <= 32:
        raise RecipeError("calibration case count is outside its bound")
    roles: set[str] = set()
    identifiers: set[str] = set()
    for ordinal, raw_case in enumerate(cases):
        case = exact_keys(raw_case, (
            "case_id", "role", "prompt_utf8", "prompt_sha256", "prompt_token_ids",
            "teacher_forced_token_ids", "sampler_mode", "temperature_micros", "seed",
            "maximum_tokens", "expected_token_ids", "expected_output_utf8",
            "expected_output_sha256",
        ), f"calibration cases[{ordinal}]")
        case_id = require_identifier(case["case_id"], f"cases[{ordinal}].case_id", case=True)
        if case_id in identifiers:
            raise RecipeError("calibration case_id is duplicated")
        identifiers.add(case_id)
        roles.add(require_enum(case["role"], {"calibration", "holdout"},
                               f"cases[{ordinal}].role"))
        prompt = bounded_text(case["prompt_utf8"], 0, 65_536, f"cases[{ordinal}].prompt_utf8")
        if hashlib.sha256(prompt.encode()).hexdigest() != require_digest(
                case["prompt_sha256"], f"cases[{ordinal}].prompt_sha256"):
            raise RecipeError("calibration prompt digest does not match")
        require_i32_array(case["prompt_token_ids"], f"cases[{ordinal}].prompt_token_ids")
        require_i32_array(case["teacher_forced_token_ids"],
                          f"cases[{ordinal}].teacher_forced_token_ids", minimum=1)
        sampler = require_enum(case["sampler_mode"], {"greedy", "seeded"},
                               f"cases[{ordinal}].sampler_mode")
        temperature = bounded_i64(case["temperature_micros"], 0, I64_MAX,
                                  f"cases[{ordinal}].temperature_micros")
        bounded_i64(case["seed"], I64_MIN, I64_MAX, f"cases[{ordinal}].seed")
        if (sampler == "greedy" and (temperature != 0 or case["seed"] != 0)) \
                or (sampler == "seeded" and temperature != 300_000):
            raise RecipeError("calibration sampler parameters are invalid")
        maximum_tokens = bounded_i64(case["maximum_tokens"], 1, 128,
                                     f"cases[{ordinal}].maximum_tokens")
        expected = require_i32_array(case["expected_token_ids"],
                                     f"cases[{ordinal}].expected_token_ids", minimum=1, maximum=128)
        if len(expected) > maximum_tokens:
            raise RecipeError("expected token count exceeds maximum_tokens")
        output = bounded_text(case["expected_output_utf8"], 0, MAX_CALIBRATION_BYTES,
                              f"cases[{ordinal}].expected_output_utf8")
        if hashlib.sha256(output.encode()).hexdigest() != require_digest(
                case["expected_output_sha256"], f"cases[{ordinal}].expected_output_sha256"):
            raise RecipeError("calibration output digest does not match")
        cases[ordinal] = case
    if roles != {"calibration", "holdout"}:
        raise RecipeError("calibration must contain calibration and holdout cases")
    self_hash(result, "calibration_id", "numeric calibration")
    return result


def expected_profile_cases(
    calibrations: Iterable[dict[str, object]], option_id: str,
) -> list[dict[str, object]]:
    result = []
    for calibration in calibrations:
        model = calibration["model"]
        assert isinstance(model, dict)
        model_id = str(model["model_id"])
        cases = calibration["cases"]
        assert isinstance(cases, list)
        for calibration_case in cases:
            assert isinstance(calibration_case, dict)
            case_id = str(calibration_case["case_id"])
            for execution, repeat_index in (
                ("cpu", 0), ("gpu_resident", 0), ("cpu", 1), ("gpu_resident", 1),
            ):
                result.append({
                    "case_id": f"{case_id}.{execution}.{repeat_index}",
                    "calibration_case_id": case_id,
                    "role": calibration_case["role"],
                    "execution": execution,
                    "repeat_index": repeat_index,
                    "model_id": model_id,
                    "option_id": "" if execution == "cpu" else option_id,
                    "maximum_tokens": calibration_case["maximum_tokens"],
                })
    return result


def validate_profile(
    value: object, *, profile_raw: bytes, align_source: dict[str, object],
    bundle: dict[str, object],
    calibrations: list[dict[str, object]], calibration_raws: list[bytes],
) -> dict[str, object]:
    result = exact_keys(value, (
        "schema_version", "artifact_kind", "profile_id", "platform", "source",
        "bundle_manifest", "models", "runtime_options", "cases", "deadlines_ns",
    ), "runtime profile")
    bounded_i64(result["schema_version"], 1, 1, "profile schema_version")
    if result["artifact_kind"] != "GPU_RUNTIME_PROFILE":
        raise RecipeError("runtime profile kind is invalid")
    require_identifier(result["profile_id"], "profile_id")
    platform = require_enum(result["platform"], {"macos", "linux", "wsl2"}, "profile platform")

    source = exact_keys(result["source"], ("commit", "manifest_sha256"), "profile source")
    result["source"] = source
    if align_source["source_kind"] != "align-llm" or source["commit"] != align_source["commit"] \
            or source["manifest_sha256"] != hashlib.sha256(canonical(align_source)).hexdigest():
        raise RecipeError("profile does not bind the supplied align-llm source")
    result["bundle_manifest"] = file_ref(result["bundle_manifest"], "profile bundle_manifest")
    if result["bundle_manifest"]["sha256"] != hashlib.sha256(canonical(bundle)).hexdigest():
        raise RecipeError("profile bundle manifest digest does not match")

    if len(calibrations) != 2 or len(calibration_raws) != 2:
        raise RecipeError("profile requires exactly two calibrations")
    models = result["models"]
    if not isinstance(models, list) or len(models) != 2:
        raise RecipeError("profile requires exactly two model rows")
    model_ids: list[str] = []
    all_case_ids: set[str] = set()
    for ordinal, raw_model in enumerate(models):
        model = exact_keys(raw_model, (
            "model_id", "model_path", "model_sha256", "pack_path", "pack_sha256",
            "geometry_path", "geometry_sha256", "calibration_path", "calibration_sha256",
            "runtime_cache_budget_bytes",
        ), f"profile models[{ordinal}]")
        model_id = require_enum(model["model_id"], {"qwen2", "olmoe"},
                                f"models[{ordinal}].model_id")
        model_ids.append(model_id)
        for key in ("model_path", "pack_path", "geometry_path", "calibration_path"):
            require_path(model[key], f"models[{ordinal}].{key}")
        for key in ("model_sha256", "pack_sha256", "geometry_sha256", "calibration_sha256"):
            require_digest(model[key], f"models[{ordinal}].{key}")
        calibration = calibrations[ordinal]
        calibration_model = calibration["model"]
        assert isinstance(calibration_model, dict)
        if calibration_model["model_id"] != model_id \
                or calibration["backend"] != bundle["backend"] \
                or calibration["bundle_id"] != bundle["bundle_id"]:
            raise RecipeError("profile calibration model/backend/bundle binding does not match")
        for profile_key in ("model_sha256", "pack_sha256", "geometry_sha256"):
            if model[profile_key] != calibration_model[profile_key]:
                raise RecipeError("profile model digest does not match calibration")
        if model["calibration_sha256"] != hashlib.sha256(calibration_raws[ordinal]).hexdigest():
            raise RecipeError("profile calibration digest does not match")
        budget = bounded_i64(model["runtime_cache_budget_bytes"], 0, I64_MAX,
                             f"models[{ordinal}].runtime_cache_budget_bytes")
        if (model_id == "qwen2" and budget != 0) or (model_id == "olmoe" and budget <= 0):
            raise RecipeError("profile model cache budget is invalid")
        calibration_cases = calibration["cases"]
        assert isinstance(calibration_cases, list)
        for calibration_case in calibration_cases:
            assert isinstance(calibration_case, dict)
            case_id = str(calibration_case["case_id"])
            if case_id in all_case_ids:
                raise RecipeError("calibration case IDs are not unique across models")
            all_case_ids.add(case_id)
        models[ordinal] = model
    if model_ids != ["qwen2", "olmoe"]:
        raise RecipeError("profile model order is invalid")

    options = result["runtime_options"]
    if not isinstance(options, list) or len(options) != 1:
        raise RecipeError("profile requires exactly one runtime option")
    option = validate_runtime_option(options[0], embedded=True)
    options[0] = option
    if option["backend"] != bundle["backend"]:
        raise RecipeError("profile option backend does not match bundle")
    bundle_parent = pathlib.PurePosixPath(str(result["bundle_manifest"]["path"])).parent
    if bundle_parent.as_posix() != option["backend_bundle"]:
        raise RecipeError("profile option does not resolve to the bundle manifest directory")
    if (option["backend"] == "metal" and platform != "macos") \
            or (option["backend"] == "cuda" and platform not in {"linux", "wsl2"}):
        raise RecipeError("profile platform does not match backend")
    if any(model["runtime_cache_budget_bytes"] > option["host_budget_bytes"] for model in models):
        raise RecipeError("profile model cache budget exceeds the host budget")

    cases = result["cases"]
    if not isinstance(cases, list) or not 16 <= len(cases) <= 256:
        raise RecipeError("profile case count is outside its bound")
    expected = expected_profile_cases(calibrations, str(option["option_id"]))
    if cases != expected:
        raise RecipeError("profile cases are not the complete derived expansion")
    result["cases"] = expected

    deadlines = exact_keys(result["deadlines_ns"], ("preparation", "generation"),
                           "profile deadlines")
    result["deadlines_ns"] = deadlines
    bounded_i64(deadlines["preparation"], 1, 3_600_000_000_000, "preparation deadline")
    bounded_i64(deadlines["generation"], 1, 900_000_000_000, "generation deadline")
    if len(profile_raw) > MAX_PROFILE_BYTES:
        raise RecipeError("profile exceeds its canonical size bound")
    return result


def validate_profile_records(
    *, runtime_option_raw: bytes, align_source_raw: bytes, ggml_source_raw: bytes,
    bundle_raw: bytes, calibration_raws: list[bytes], profile_raw: bytes,
) -> dict[str, object]:
    option = validate_runtime_option(parse_record(runtime_option_raw, MAX_PROFILE_BYTES),
                                     embedded=False)
    align_source = normalize_source_manifest(parse_record(align_source_raw, 16 * 1024 * 1024))
    ggml_source = normalize_source_manifest(parse_record(ggml_source_raw, 16 * 1024 * 1024))
    bundle = validate_bundle(parse_record(bundle_raw, MAX_BUNDLE_BYTES), ggml_source)
    calibrations = [
        validate_calibration(parse_record(raw, MAX_CALIBRATION_BYTES))
        for raw in calibration_raws
    ]
    normalized_calibration_raws = [canonical(calibration) for calibration in calibrations]
    profile = validate_profile(
        parse_record(profile_raw, MAX_PROFILE_BYTES),
        profile_raw=profile_raw,
        align_source=align_source,
        bundle=bundle,
        calibrations=calibrations,
        calibration_raws=normalized_calibration_raws,
    )
    embedded = profile["runtime_options"]
    assert isinstance(embedded, list) and isinstance(embedded[0], dict)
    if {key: embedded[0][key] for key in option} != option:
        raise RecipeError("standalone and embedded runtime options do not match")
    return {
        "runtime_option": option,
        "align_source": align_source,
        "ggml_source": ggml_source,
        "bundle": bundle,
        "calibrations": calibrations,
        "profile": profile,
    }


def source_snapshot_sha256(manifest: dict[str, object]) -> str:
    snapshot = hashlib.sha256()
    snapshot.update(b"GPU_SOURCE_SNAPSHOT\0")
    snapshot.update(str(manifest["source_kind"]).encode("ascii"))
    snapshot.update(b"\0")
    snapshot.update(canonical(manifest))
    rows = manifest["files"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        snapshot.update(bytes.fromhex(str(row["sha256"])))
    return snapshot.hexdigest()


def case_order_sha256(profile: dict[str, object]) -> str:
    cases = profile["cases"]
    raw = canonical(cases)
    return hashlib.sha256(b"GPU_CASE_ORDER\0" + raw[:-1]).hexdigest()


def produced_identity(value: object, status: str, label: str) -> dict[str, object]:
    result = exact_keys(value, ("state", "name", "version", "sha256"), label)
    state = require_enum(result["state"], {"available", "unavailable"}, f"{label}.state")
    if state == "available":
        bounded_text(result["name"], 1, 256, f"{label}.name")
        bounded_text(result["version"], 1, 4096, f"{label}.version")
        require_digest(result["sha256"], f"{label}.sha256")
    elif result["name"] != "" or result["version"] != "" or result["sha256"] != "" \
            or status != "FAIL":
        raise RecipeError(f"{label} unavailable identity is invalid")
    return result


def command_digest(kind: str, argv: list[str], environment: list[str]) -> str:
    result = hashlib.sha256()
    result.update(b"GPU_QUALIFIER_COMMAND\0")

    def text_frame(value: str) -> None:
        encoded = value.encode("utf-8")
        result.update(len(encoded).to_bytes(8, "little"))
        result.update(encoded)

    text_frame(kind)
    result.update(len(argv).to_bytes(4, "little"))
    for item in argv:
        text_frame(item)
    result.update(len(environment).to_bytes(4, "little"))
    for item in environment:
        text_frame(item)
    return result.hexdigest()


def command_path(value: str) -> tuple[str, str] | None:
    """Split a standalone path token or a CMake definition with exactly one path value."""
    if value.startswith("<"):
        if not LOGICAL_PATH.fullmatch(value):
            raise RecipeError("command argv contains a malformed logical path")
        return "", value
    if value.startswith("-D") and "=<" in value:
        match = re.fullmatch(r"(-D[A-Z][A-Z0-9_]*(?::(?:PATH|FILEPATH))?=)(<.*)", value)
        if match is None or not LOGICAL_PATH.fullmatch(match.group(2)):
            raise RecipeError("command argv contains a malformed CMake path definition")
        return match.group(1), match.group(2)
    return None


def validate_command(
    value: object, *, allow_sentinel: bool, expected_kind: str | None = None,
) -> dict[str, object]:
    result = exact_keys(value, ("kind", "argv", "environment", "sha256"), "command")
    if result == {"kind": "", "argv": [], "environment": [], "sha256": ""}:
        if not allow_sentinel:
            raise RecipeError("command sentinel is not allowed")
        return result
    kind = require_enum(result["kind"], {
        "compiler_materialize", "runtime_materialize", "candidate_build", "shim_build",
        "cpu_reference_build", "case",
    }, "command kind")
    if expected_kind is not None and kind != expected_kind:
        raise RecipeError("command kind does not match its owner")
    argv = result["argv"]
    if not isinstance(argv, list) or not argv:
        raise RecipeError("command argv is empty")
    for ordinal, item in enumerate(argv):
        text = bounded_text(item, 1, 4096, f"command argv[{ordinal}]")
        if "\0" in text:
            raise RecipeError("command argv contains NUL")
        command_path(text)
        if text.startswith(("/", "~/", "\\")) or re.search(r"(?:^|=)[A-Za-z]:[\\/]", text) \
                or "=/" in text:
            raise RecipeError("command argv exposes a machine-local path")
    environment = result["environment"]
    if not isinstance(environment, list) or len(environment) != 4:
        raise RecipeError("command environment is invalid")
    for ordinal, item in enumerate(environment):
        bounded_text(item, 1, 4096, f"command environment[{ordinal}]")
    if not (
        environment[0].startswith("HOME=<") and environment[0].endswith(">:owned")
        and environment[1] == "LC_ALL=C"
        and environment[2].startswith("TMPDIR=<") and environment[2].endswith(">:owned")
        and environment[3] == "TZ=UTC"
    ):
        raise RecipeError("command environment is not the closed canonical environment")
    expected = command_digest(kind, argv, environment)
    if require_digest(result["sha256"], "command sha256") != expected:
        raise RecipeError("command digest does not match")
    return result


def validate_case(
    value: object, *, expected: dict[str, object], calibration_case: dict[str, object],
    status: str,
) -> dict[str, object]:
    result = exact_keys(value, (
        "ordinal", "case_id", "calibration_case_id", "role", "execution", "repeat_index",
        "model_id", "option_id", "terminal", "category", "stage", "exit_code", "signal",
        "command", "output_sha256", "token_ids", "nonfinite_count", "numeric", "placement",
        "transfers", "memory", "timing", "stdout_path", "stderr_path",
    ), "evidence case")
    ordinal = bounded_i64(result["ordinal"], 0, 255, "case ordinal")
    for key in (
        "case_id", "calibration_case_id", "role", "execution", "repeat_index", "model_id",
        "option_id",
    ):
        if result[key] != expected[key]:
            raise RecipeError(f"evidence case {key} does not match profile")
    terminal = require_enum(result["terminal"],
                            {"PASS", "FAIL", "TIMEOUT", "CRASH", "SIGNAL", "MISSING"},
                            "case terminal")
    category = result["category"]
    stage = result["stage"]
    if result["exit_code"] is not None:
        bounded_i64(result["exit_code"], I64_MIN, I64_MAX, "case exit_code")
    if result["signal"] is not None:
        bounded_i64(result["signal"], 1, I64_MAX, "case signal")
    if terminal == "PASS":
        if category != "" or stage != "" or result["exit_code"] != 0 or result["signal"] is not None:
            raise RecipeError("passing case terminal fields are invalid")
        require_digest(result["output_sha256"], "case output_sha256")
    else:
        require_enum(category, FAILURE_CATEGORIES, "case category")
        require_enum(stage, FAILURE_STAGES, "case stage")
        if terminal == "FAIL":
            if result["signal"] is not None:
                raise RecipeError("failed case exit fields are invalid")
        elif terminal in {"TIMEOUT", "MISSING"}:
            if result["exit_code"] is not None or result["signal"] is not None:
                raise RecipeError("timeout/missing case exit fields are invalid")
        elif terminal == "CRASH":
            if result["signal"] is not None or not isinstance(result["exit_code"], int) \
                    or result["exit_code"] == 0:
                raise RecipeError("crashed case exit fields are invalid")
        elif result["exit_code"] is not None or not isinstance(result["signal"], int) \
                or result["signal"] <= 0:
            raise RecipeError("signaled case exit fields are invalid")
        if result["output_sha256"] != "":
            require_digest(result["output_sha256"], "case output_sha256")

    spawned = result["command"] != {"kind": "", "argv": [], "environment": [], "sha256": ""}
    result["command"] = validate_command(
        result["command"], allow_sentinel=terminal != "PASS", expected_kind="case" if spawned else None,
    )
    if terminal == "PASS" and not spawned:
        raise RecipeError("passing case has no command")
    if terminal == "FAIL" and spawned != (result["exit_code"] is not None):
        raise RecipeError("failed case exit code does not match child existence")
    if spawned:
        label = "candidate" if expected["execution"] == "gpu_resident" else "cpu-reference"
        argv = result["command"]["argv"]
        if len(argv) != 2 or re.fullmatch(r"<" + label + r">:sha256:[0-9a-f]{64}", argv[0]) is None \
                or re.fullmatch(r"<case-input>:sha256:[0-9a-f]{64}", argv[1]) is None:
            raise RecipeError("case command does not bind its role-specific executable and input")
        require_path(result["stdout_path"], "case stdout_path")
        require_path(result["stderr_path"], "case stderr_path")
    elif result["stdout_path"] != "" or result["stderr_path"] != "":
        raise RecipeError("unspawned case has log paths")

    maximum_tokens = int(expected["maximum_tokens"])
    token_ids = require_i32_array(result["token_ids"], "case token_ids", maximum=maximum_tokens)
    bounded_i64(result["nonfinite_count"], 0, I64_MAX, "case nonfinite_count")

    numeric_keys = (
        "expected_scalar_count", "actual_scalar_count", "expected_layer_count",
        "actual_layer_count", "expected_router_boundary_count", "actual_router_boundary_count",
        "expected_final_logit_count", "actual_final_logit_count", "max_absolute_f64_bits",
        "max_relative_f64_bits", "near_tie_count", "mismatch_count",
    )
    numeric = exact_keys(result["numeric"], ("compared", *numeric_keys), "case numeric")
    result["numeric"] = numeric
    if not isinstance(numeric["compared"], bool):
        raise RecipeError("case numeric compared is not boolean")
    for key in numeric_keys[:-4]:
        bounded_i64(numeric[key], 0, I64_MAX, f"case numeric {key}")
    f64_nonnegative(numeric["max_absolute_f64_bits"], "max_absolute_f64_bits")
    f64_nonnegative(numeric["max_relative_f64_bits"], "max_relative_f64_bits")
    bounded_i64(numeric["near_tie_count"], 0, I64_MAX, "near_tie_count")
    bounded_i64(numeric["mismatch_count"], 0, I64_MAX, "mismatch_count")
    if result["execution"] == "cpu":
        if numeric["compared"]:
            raise RecipeError("CPU evidence case is numerically compared")
    elif terminal == "PASS" and not numeric["compared"]:
        raise RecipeError("GPU evidence case lacks numeric comparison")
    if not numeric["compared"]:
        for key in numeric_keys[:8] + numeric_keys[10:]:
            if numeric[key] != 0:
                raise RecipeError("uncompared case numeric counts are not zero")
        if numeric["max_absolute_f64_bits"] != "0000000000000000" \
                or numeric["max_relative_f64_bits"] != "0000000000000000":
            raise RecipeError("uncompared case numeric error bits are not zero")
    if terminal == "PASS":
        if token_ids != calibration_case["expected_token_ids"] \
                or result["output_sha256"] != calibration_case["expected_output_sha256"]:
            raise RecipeError("passing case output does not match calibration")
        if result["nonfinite_count"] != 0 or numeric["mismatch_count"] != 0:
            raise RecipeError("passing case contains nonfinite or mismatched values")
        if result["execution"] == "gpu_resident":
            pairs = (
                ("expected_scalar_count", "actual_scalar_count"),
                ("expected_layer_count", "actual_layer_count"),
                ("expected_router_boundary_count", "actual_router_boundary_count"),
                ("expected_final_logit_count", "actual_final_logit_count"),
            )
            if any(numeric[expected_key] != numeric[actual_key]
                   for expected_key, actual_key in pairs):
                raise RecipeError("passing GPU numeric coverage is incomplete")
            if numeric["expected_scalar_count"] <= 0 or numeric["expected_layer_count"] <= 0 \
                    or numeric["expected_final_logit_count"] <= 0:
                raise RecipeError("passing GPU numeric coverage is empty")
            router_count = numeric["expected_router_boundary_count"]
            if (result["model_id"] == "qwen2" and router_count != 0) \
                    or (result["model_id"] == "olmoe" and router_count <= 0):
                raise RecipeError("passing GPU router coverage is invalid")

    placement_names = (
        "expected_model_operations", "gpu_model_operations", "cpu_model_operations",
        "expected_layers", "gpu_layers", "cpu_layers", "expected_experts", "gpu_experts",
        "cpu_experts", "expected_weights_device_bytes", "minimum_weights_device_bytes",
        "expected_kv_device_bytes", "minimum_kv_device_bytes", "expected_weight_upload_count",
        "weight_upload_count", "weight_upload_bytes",
    )
    placement = exact_keys(result["placement"], placement_names, "case placement")
    result["placement"] = placement
    for key in placement_names:
        bounded_i64(placement[key], 0, I64_MAX, f"case placement {key}")
    if terminal == "PASS" and result["execution"] == "gpu_resident":
        equal_pairs = (
            ("expected_model_operations", "gpu_model_operations"),
            ("expected_layers", "gpu_layers"),
            ("expected_experts", "gpu_experts"),
            ("expected_weights_device_bytes", "minimum_weights_device_bytes"),
            ("expected_kv_device_bytes", "minimum_kv_device_bytes"),
            ("expected_weight_upload_count", "weight_upload_count"),
        )
        if any(placement[expected_key] != placement[actual_key]
               for expected_key, actual_key in equal_pairs):
            raise RecipeError("passing GPU placement coverage is incomplete")
        if placement["cpu_model_operations"] != 0 or placement["cpu_layers"] != 0 \
                or placement["cpu_experts"] != 0:
            raise RecipeError("passing GPU row reports CPU model work")
        if placement["expected_model_operations"] <= 0 or placement["expected_layers"] <= 0 \
                or placement["expected_weights_device_bytes"] <= 0 \
                or placement["expected_kv_device_bytes"] <= 0 \
                or placement["expected_weight_upload_count"] <= 0:
            raise RecipeError("passing GPU placement coverage is empty")
        experts = placement["expected_experts"]
        if (result["model_id"] == "qwen2" and experts != 0) \
                or (result["model_id"] == "olmoe" and experts <= 0):
            raise RecipeError("passing GPU expert coverage is invalid")

    transfers = exact_keys(result["transfers"], (
        "host_to_device_bytes", "device_to_host_bytes", "unexpected_device_to_host_bytes",
        "wait_count",
    ), "case transfers")
    result["transfers"] = transfers
    for key in transfers:
        bounded_i64(transfers[key], 0, I64_MAX, f"case transfers {key}")
    if terminal == "PASS" and result["execution"] == "gpu_resident" \
            and transfers["unexpected_device_to_host_bytes"] != 0:
        raise RecipeError("passing GPU row contains an unexpected readback")

    memory = exact_keys(result["memory"], (
        "managed_host_peak_bytes", "application_host_reserved_bytes", "managed_device_peak_bytes", "uma_alias_peak_bytes",
        "rss_peak_bytes", "driver_peak_bytes",
    ), "case memory")
    result["memory"] = memory
    for key in memory:
        if key == "driver_peak_bytes" and memory[key] is None:
            continue
        bounded_i64(memory[key], 0, I64_MAX, f"case memory {key}")

    timing = exact_keys(result["timing"], (
        "wall_ns", "load_ns", "ttft_ns", "prefill_ns", "decode_ns", "device_ns",
        "transfer_ns", "wait_ns",
    ), "case timing")
    result["timing"] = timing
    for key in timing:
        if timing[key] is None:
            continue
        bounded_i64(timing[key], 1 if key == "wall_ns" and spawned else 0, I64_MAX,
                    f"case timing {key}")
    if status == "PASS" and terminal != "PASS":
        raise RecipeError("passing evidence contains a nonpassing case")
    if ordinal < 0:
        raise RecipeError("case ordinal is invalid")
    return result


def validate_evidence(
    value: object, *, profile_records: dict[str, object], evidence_raw: bytes,
) -> dict[str, object]:
    result = exact_keys(value, (
        "schema_version", "artifact_kind", "status", "suite", "profile_id", "source", "host",
        "bundle", "inputs", "preparation_commands", "files", "cases", "aggregate", "cleanup",
        "failure", "elapsed_ns",
    ), "runtime evidence")
    bounded_i64(result["schema_version"], 1, 1, "evidence schema_version")
    if result["artifact_kind"] != "GPU_RUNTIME_EVIDENCE" or result["suite"] != "generation":
        raise RecipeError("runtime evidence kind or suite is invalid")
    status = require_enum(result["status"], {"PASS", "FAIL"}, "evidence status")
    profile = profile_records["profile"]
    bundle_record = profile_records["bundle"]
    align_source = profile_records["align_source"]
    ggml_source = profile_records["ggml_source"]
    calibrations = profile_records["calibrations"]
    assert isinstance(profile, dict) and isinstance(bundle_record, dict)
    assert isinstance(align_source, dict) and isinstance(ggml_source, dict)
    assert isinstance(calibrations, list)
    if result["profile_id"] != profile["profile_id"]:
        raise RecipeError("evidence profile_id does not match")

    source = exact_keys(result["source"], (
        "commit", "source_manifest_sha256", "source_snapshot_sha256", "align_revision",
        "align_compiler", "align_runtime", "qualifier", "candidate", "shim", "cpu_reference",
    ), "evidence source")
    result["source"] = source
    if source["commit"] != align_source["commit"] \
            or source["source_manifest_sha256"] != hashlib.sha256(canonical(align_source)).hexdigest() \
            or source["source_snapshot_sha256"] != source_snapshot_sha256(align_source):
        raise RecipeError("evidence align-llm source identity does not match")
    lowercase_hex(source["align_revision"], 40, "evidence align_revision")
    for key in (
        "align_compiler", "align_runtime", "qualifier", "candidate", "shim", "cpu_reference",
    ):
        source[key] = produced_identity(source[key], status, f"evidence source {key}")
        if status == "PASS" and source[key]["state"] != "available":
            raise RecipeError("passing evidence has an unavailable produced identity")

    host = exact_keys(result["host"], (
        "platform", "os_version", "kernel", "arch", "wsl", "cpu", "logical_cpus",
        "host_total_bytes", "host_free_bytes", "backend", "device_state", "registry_device",
        "device_description", "driver", "gpu_architecture", "device_total_bytes",
        "device_free_bytes",
    ), "evidence host")
    result["host"] = host
    host_platform = require_enum(host["platform"], {"macos", "linux", "wsl2"}, "host platform")
    if host_platform != profile["platform"]:
        raise RecipeError("evidence host platform does not match profile")
    for key in ("os_version", "kernel", "cpu"):
        bounded_text(host[key], 1, 4096, f"host {key}")
    require_enum(host["arch"], {"aarch64", "x86_64"}, "host arch")
    if not isinstance(host["wsl"], bool) or host["wsl"] != (host_platform == "wsl2"):
        raise RecipeError("host WSL identity is invalid")
    bounded_i64(host["logical_cpus"], 1, I64_MAX, "host logical_cpus")
    bounded_i64(host["host_total_bytes"], 1, I64_MAX, "host total bytes")
    bounded_i64(host["host_free_bytes"], 0, I64_MAX, "host free bytes")
    if host["host_free_bytes"] > host["host_total_bytes"] or host["backend"] != bundle_record["backend"]:
        raise RecipeError("host memory or backend identity is invalid")
    target = bundle_record["target"]
    assert isinstance(target, dict)
    expected_platform = "macos" if target["os"] == "macos" else host_platform
    if host_platform != expected_platform or host["arch"] != target["arch"]:
        raise RecipeError("evidence host does not match bundle target")
    device_state = require_enum(host["device_state"], {"available", "unavailable"},
                                "host device_state")
    device_strings = ("registry_device", "device_description", "driver", "gpu_architecture")
    if device_state == "available":
        for key in device_strings:
            bounded_text(host[key], 1, 4096, f"host {key}")
        bounded_i64(host["device_total_bytes"], 1, I64_MAX, "device total bytes")
        bounded_i64(host["device_free_bytes"], 0, I64_MAX, "device free bytes")
        if host["device_free_bytes"] > host["device_total_bytes"]:
            raise RecipeError("host device free bytes exceed total")
    elif status != "FAIL" or any(host[key] != "" for key in device_strings) \
            or host["device_total_bytes"] != 0 or host["device_free_bytes"] != 0:
        raise RecipeError("unavailable device identity is invalid")

    bundle = exact_keys(result["bundle"], (
        "manifest_sha256", "bundle_id", "ggml_source_manifest_sha256",
        "ggml_source_snapshot_sha256", "loaded_artifact_sha256s",
    ), "evidence bundle")
    result["bundle"] = bundle
    expected_bundle_digest = hashlib.sha256(canonical(bundle_record)).hexdigest()
    if bundle["manifest_sha256"] != expected_bundle_digest \
            or bundle["bundle_id"] != bundle_record["bundle_id"] \
            or bundle["ggml_source_manifest_sha256"] != hashlib.sha256(
                canonical(ggml_source)).hexdigest() \
            or bundle["ggml_source_snapshot_sha256"] != source_snapshot_sha256(ggml_source):
        raise RecipeError("evidence bundle identity does not match")
    loaded = bundle["loaded_artifact_sha256s"]
    if not isinstance(loaded, list) or len(loaded) != len(set(loaded)):
        raise RecipeError("loaded artifact identities are invalid")
    declared_artifacts = bundle_record["artifacts"]
    assert isinstance(declared_artifacts, list)
    declared_digests = {artifact["sha256"] for artifact in declared_artifacts}
    for ordinal, item in enumerate(loaded):
        if require_digest(item, f"loaded_artifact_sha256s[{ordinal}]") not in declared_digests:
            raise RecipeError("loaded artifact is absent from bundle")

    inputs = exact_keys(result["inputs"],
                        ("profile_sha256", "models", "calibration_ids", "case_order_sha256"),
                        "evidence inputs")
    result["inputs"] = inputs
    if inputs["profile_sha256"] != hashlib.sha256(canonical(profile)).hexdigest():
        raise RecipeError("evidence profile digest does not match")
    expected_models = []
    profile_models = profile["models"]
    assert isinstance(profile_models, list)
    for model in profile_models:
        assert isinstance(model, dict)
        expected_models.append({
            "model_id": model["model_id"],
            "model_sha256": model["model_sha256"],
            "pack_sha256": model["pack_sha256"],
            "geometry_sha256": model["geometry_sha256"],
        })
    model_rows = inputs["models"]
    if not isinstance(model_rows, list):
        raise RecipeError("evidence input models are invalid")
    normalized_models = [
        exact_keys(row, ("model_id", "model_sha256", "pack_sha256", "geometry_sha256"),
                   "evidence input model")
        for row in model_rows
    ]
    if normalized_models != expected_models:
        raise RecipeError("evidence input models do not match profile")
    inputs["models"] = normalized_models
    calibration_ids = inputs["calibration_ids"]
    expected_calibration_ids = [calibration["calibration_id"] for calibration in calibrations]
    if calibration_ids != expected_calibration_ids:
        raise RecipeError("evidence calibration IDs do not match")
    if inputs["case_order_sha256"] != case_order_sha256(profile):
        raise RecipeError("evidence case order digest does not match")

    commands = result["preparation_commands"]
    if not isinstance(commands, list) or len(commands) > 16:
        raise RecipeError("preparation command count is outside its bound")
    order = (
        "compiler_materialize", "runtime_materialize", "shim_build", "candidate_build",
        "cpu_reference_build",
    )
    for ordinal, command in enumerate(commands):
        if ordinal >= len(order):
            raise RecipeError("preparation command sequence is too long")
        commands[ordinal] = validate_command(command, allow_sentinel=False,
                                             expected_kind=order[ordinal])
    if status == "PASS" and len(commands) != len(order):
        raise RecipeError("passing evidence has incomplete preparation commands")
    identity_order = ("align_compiler", "align_runtime", "shim", "candidate", "cpu_reference")
    for ordinal, identity_key in enumerate(identity_order):
        state = source[identity_key]["state"]
        if ordinal < max(0, len(commands) - 1) and state != "available":
            raise RecipeError("completed preparation identity is unavailable")
        if ordinal >= len(commands) and state != "unavailable":
            raise RecipeError("unexecuted preparation identity is available")
    command_identity_names = {
        "qualifier": "qualifier",
        "align-compiler": "align_compiler",
        "cc": "align_compiler",
        "align-runtime": "align_runtime",
        "shim": "shim",
        "cpu-reference": "cpu_reference",
    }
    for command in commands:
        for argument in command["argv"]:
            reference = command_path(argument)
            match = None if reference is None else re.fullmatch(
                r"<([^>]+)>:sha256:([0-9a-f]{64})", reference[1],
            )
            if match and match.group(1) in command_identity_names:
                produced = source[command_identity_names[match.group(1)]]
                if produced["state"] == "available" and produced["sha256"] != match.group(2):
                    raise RecipeError("preparation command identity does not match produced input")

    files = result["files"]
    if not isinstance(files, list) or len(files) + 1 > MAX_EVIDENCE_FILES:
        raise RecipeError("evidence file count is outside its bound")
    roles = {
        "profile", "bundle_manifest", "calibration", "align_source_manifest",
        "align_source_commit", "align_source_blob", "ggml_source_manifest",
        "ggml_source_commit", "ggml_source_blob", "helper", "shim", "backend_artifact",
        "stdout", "stderr", "case_input",
    }
    previous_path: bytes | None = None
    retained_total = 0
    for ordinal, raw_file in enumerate(files):
        file = exact_keys(raw_file, (
            "role", "path", "bytes", "sha256", "original_bytes", "original_sha256", "truncated",
        ), f"evidence files[{ordinal}]")
        role = require_enum(file["role"], roles, f"evidence files[{ordinal}].role")
        path = require_path(file["path"], f"evidence files[{ordinal}].path")
        encoded = path.encode("utf-8")
        if previous_path is not None and encoded <= previous_path:
            raise RecipeError("evidence files are not strictly sorted by path")
        previous_path = encoded
        size = bounded_i64(file["bytes"], 0, MAX_BUNDLE_ARTIFACT_BYTES,
                           f"evidence files[{ordinal}].bytes")
        original_size = bounded_i64(file["original_bytes"], size, I64_MAX,
                                    f"evidence files[{ordinal}].original_bytes")
        sha256 = require_digest(file["sha256"], f"evidence files[{ordinal}].sha256")
        original_sha256 = require_digest(
            file["original_sha256"], f"evidence files[{ordinal}].original_sha256")
        if not isinstance(file["truncated"], bool):
            raise RecipeError("evidence file truncated is not boolean")
        if file["truncated"]:
            if role not in {"stdout", "stderr"} or size != 4 * 1024 * 1024 \
                    or original_size <= size:
                raise RecipeError("evidence file truncation is invalid")
        elif original_size != size or original_sha256 != sha256:
            raise RecipeError("untruncated evidence file identities differ")
        retained_total += size
        if retained_total > MAX_BUNDLE_ARTIFACT_BYTES:
            raise RecipeError("evidence retained-data aggregate exceeds its bound")
        files[ordinal] = file

    case_values = result["cases"]
    profile_cases = profile["cases"]
    assert isinstance(profile_cases, list)
    calibration_cases: dict[str, dict[str, object]] = {}
    for calibration in calibrations:
        assert isinstance(calibration, dict)
        for calibration_case in calibration["cases"]:
            assert isinstance(calibration_case, dict)
            calibration_cases[str(calibration_case["case_id"])] = calibration_case
    if not isinstance(case_values, list) or len(case_values) > len(profile_cases):
        raise RecipeError("evidence cases are not a profile prefix")
    for ordinal, raw_case in enumerate(case_values):
        case_values[ordinal] = validate_case(
            raw_case,
            expected=profile_cases[ordinal],
            calibration_case=calibration_cases[str(profile_cases[ordinal]["calibration_case_id"])],
            status=status,
        )
        command = case_values[ordinal]["command"]
        if command["kind"]:
            role = "candidate" if profile_cases[ordinal]["execution"] == "gpu_resident" else "cpu_reference"
            label = role.replace("_", "-")
            produced = source[role]
            if produced["state"] != "available" or command["argv"][0] != f"<{label}>:sha256:{produced['sha256']}":
                raise RecipeError("case executable identity does not match produced input")
            retained = next((row for row in files if row["path"] == f"case-inputs/{ordinal:03d}.json"), None)
            if retained is None or retained["role"] != "case_input" or not 1 <= retained["bytes"] <= 4 * 1024 * 1024 \
                    or command["argv"][1] != f"<case-input>:sha256:{retained['sha256']}":
                raise RecipeError("case input identity does not match retained input")
        if case_values[ordinal]["ordinal"] != ordinal:
            raise RecipeError("evidence case ordinal is not contiguous")
        memory = case_values[ordinal]["memory"]
        assert isinstance(memory, dict)
        option = profile["runtime_options"][0]
        assert isinstance(option, dict)
        if memory["managed_host_peak_bytes"] + memory["application_host_reserved_bytes"] > option["host_budget_bytes"] \
                or memory["managed_device_peak_bytes"] > option["device_budget_bytes"]:
            raise RecipeError("evidence case exceeds profile memory budget")
    if status == "PASS" and len(case_values) != len(profile_cases):
        raise RecipeError("passing evidence omits profile cases")

    aggregate = exact_keys(result["aggregate"], (
        "case_count", "passed_count", "failed_count", "managed_host_peak_bytes",
        "managed_device_peak_bytes", "decision",
    ), "evidence aggregate")
    result["aggregate"] = aggregate
    passed = sum(case["terminal"] == "PASS" for case in case_values)
    failed = len(case_values) - passed
    host_peak = max((case["memory"]["managed_host_peak_bytes"] for case in case_values), default=0)
    device_peak = max((case["memory"]["managed_device_peak_bytes"] for case in case_values),
                      default=0)
    if (
        aggregate["case_count"] != len(case_values)
        or aggregate["passed_count"] != passed
        or aggregate["failed_count"] != failed
        or aggregate["managed_host_peak_bytes"] != host_peak
        or aggregate["managed_device_peak_bytes"] != device_peak
        or aggregate["decision"] != "unmeasured"
    ):
        raise RecipeError("evidence aggregate does not match cases")

    cleanup = exact_keys(result["cleanup"], (
        "descendants_before", "descendants_after", "owned_paths_removed",
        "invocation_state_safe", "source_unchanged", "inputs_unchanged",
    ), "evidence cleanup")
    result["cleanup"] = cleanup
    bounded_i64(cleanup["descendants_before"], 0, I64_MAX, "cleanup descendants_before")
    bounded_i64(cleanup["descendants_after"], 0, I64_MAX, "cleanup descendants_after")
    for key in ("owned_paths_removed", "invocation_state_safe", "source_unchanged",
                "inputs_unchanged"):
        if not isinstance(cleanup[key], bool):
            raise RecipeError(f"cleanup {key} is not boolean")

    failure = exact_keys(result["failure"],
                         ("category", "stage", "case_ordinal", "detail"),
                         "evidence failure")
    result["failure"] = failure
    if status == "PASS":
        if failure != {"category": "", "stage": "", "case_ordinal": -1, "detail": ""}:
            raise RecipeError("passing evidence failure fields are not empty")
        if not all(cleanup[key] for key in (
            "owned_paths_removed", "invocation_state_safe", "source_unchanged",
            "inputs_unchanged",
        )):
            raise RecipeError("passing evidence cleanup is incomplete")
    else:
        require_enum(failure["category"], FAILURE_CATEGORIES, "failure category")
        require_enum(failure["stage"], FAILURE_STAGES, "failure stage")
        bounded_i64(failure["case_ordinal"], -1, len(profile_cases) - 1,
                    "failure case_ordinal")
        bounded_text(failure["detail"], 1, 4096, "failure detail")
        preparation_failure_stages = {
            "compiler": 0,
            "runtime": 1,
            "shim_build": 2,
            "candidate_build": 3,
            "cpu_reference_build": 4,
        }
        failed_preparation = preparation_failure_stages.get(str(failure["stage"]))
        if failed_preparation is not None:
            if len(commands) not in {failed_preparation, failed_preparation + 1} \
                    or failure["case_ordinal"] != -1 or case_values \
                    or any(source[key]["state"] != ("available" if ordinal < failed_preparation
                                                   else "unavailable")
                           for ordinal, key in enumerate(identity_order)):
                raise RecipeError("preparation failure identity or command prefix is invalid")
    if status == "PASS" and (
        cleanup["descendants_after"] != 0 or cleanup["descendants_before"] != 0
    ):
        raise RecipeError("passing evidence retained a child process")
    bounded_i64(result["elapsed_ns"], 1, I64_MAX, "evidence elapsed_ns")
    if len(evidence_raw) > 8 * 1024 * 1024:
        raise RecipeError("evidence result exceeds its canonical size bound")
    return result


def validate_evidence_records(
    *, runtime_option_raw: bytes, align_source_raw: bytes, ggml_source_raw: bytes,
    bundle_raw: bytes, calibration_raws: list[bytes], profile_raw: bytes,
    evidence_raw: bytes,
) -> dict[str, object]:
    records = validate_profile_records(
        runtime_option_raw=runtime_option_raw,
        align_source_raw=align_source_raw,
        ggml_source_raw=ggml_source_raw,
        bundle_raw=bundle_raw,
        calibration_raws=calibration_raws,
        profile_raw=profile_raw,
    )
    evidence = validate_evidence(
        parse_record(evidence_raw, 8 * 1024 * 1024),
        profile_records=records,
        evidence_raw=evidence_raw,
    )
    records["evidence"] = evidence
    return records


def read_evidence_tree(root: pathlib.Path) -> tuple[dict[str, bytes], set[str]]:
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) \
        | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        root_fd = os.open(root.absolute(), directory_flags)
    except OSError as exc:
        raise RecipeError("evidence directory is absent or unsafe") from exc
    files: dict[str, bytes] = {}
    directories: set[str] = set()

    def visit(directory_fd: int, prefix: str) -> None:
        before = os.fstat(directory_fd)
        try:
            names_before = sorted(os.listdir(directory_fd))
        except OSError as exc:
            raise RecipeError("evidence directory cannot be enumerated") from exc
        for name in names_before:
            path = f"{prefix}/{name}" if prefix else name
            require_path(path, "evidence directory path")
            try:
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                raise RecipeError("evidence directory entry cannot be inspected") from exc
            if stat.S_ISDIR(metadata.st_mode):
                try:
                    child_fd = os.open(name, directory_flags, dir_fd=directory_fd)
                except OSError as exc:
                    raise RecipeError("evidence directory contains an unsafe directory") from exc
                try:
                    directories.add(path)
                    visit(child_fd, path)
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(metadata.st_mode):
                maximum = 8 * 1024 * 1024 if path == "result.json" \
                    else MAX_BUNDLE_ARTIFACT_BYTES
                files[path] = single_link_file_at(
                    directory_fd, name, f"evidence file {path}",
                    maximum,
                )
            else:
                raise RecipeError("evidence directory contains a non-regular entry")
        try:
            names_after = sorted(os.listdir(directory_fd))
            after = os.fstat(directory_fd)
        except OSError as exc:
            raise RecipeError("evidence directory cannot be rechecked") from exc
        fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_mtime_ns", "st_ctime_ns")
        if names_before != names_after or any(
            getattr(before, field) != getattr(after, field) for field in fields
        ):
            raise RecipeError("evidence directory changed while it was read")

    try:
        visit(root_fd, "")
    finally:
        os.close(root_fd)
    return files, directories


def expected_directory_roles(records: dict[str, object]) -> dict[str, str]:
    evidence = records["evidence"]
    profile = records["profile"]
    align_source = records["align_source"]
    ggml_source = records["ggml_source"]
    bundle = records["bundle"]
    calibrations = records["calibrations"]
    assert isinstance(evidence, dict) and isinstance(profile, dict)
    assert isinstance(align_source, dict) and isinstance(ggml_source, dict)
    assert isinstance(bundle, dict) and isinstance(calibrations, list)
    expected = {
        "profile.json": "profile",
        "bundle-manifest.json": "bundle_manifest",
        "source/align-llm/manifest.json": "align_source_manifest",
        "source/align-llm/commit": "align_source_commit",
        "source/ggml/manifest.json": "ggml_source_manifest",
        "source/ggml/commit": "ggml_source_commit",
    }
    models = profile["models"]
    assert isinstance(models, list)
    for model in models:
        assert isinstance(model, dict)
        expected[str(model["calibration_path"])] = "calibration"
    for source, kind in ((align_source, "align_source_blob"), (ggml_source, "ggml_source_blob")):
        rows = source["files"]
        assert isinstance(rows, list)
        source_kind = source["source_kind"]
        for row in rows:
            assert isinstance(row, dict)
            expected[f"source/{source_kind}/blobs/{row['sha256']}"] = kind
    artifacts = bundle["artifacts"]
    assert isinstance(artifacts, list)
    for artifact in artifacts:
        assert isinstance(artifact, dict)
        expected[f"artifacts/{artifact['sha256']}"] = "backend_artifact"
    source_identity = evidence["source"]
    assert isinstance(source_identity, dict)
    for key in ("align_compiler", "align_runtime", "qualifier", "candidate"):
        identity_value = source_identity[key]
        assert isinstance(identity_value, dict)
        if identity_value["state"] == "available":
            expected[f"artifacts/{identity_value['sha256']}"] = "helper"
    for key, role in (("shim", "shim"), ("cpu_reference", "helper")):
        identity_value = source_identity[key]
        assert isinstance(identity_value, dict)
        if identity_value["state"] == "available":
            expected[f"artifacts/{identity_value['sha256']}"] = role
    failure = evidence["failure"]
    commands = evidence["preparation_commands"]
    assert isinstance(failure, dict) and isinstance(commands, list)
    preparation_stages = {
        "compiler": 0, "runtime": 1, "shim_build": 2, "candidate_build": 3,
        "cpu_reference_build": 4,
    }
    failed_ordinal = preparation_stages.get(str(failure["stage"]))
    if evidence["status"] == "FAIL" and failure["case_ordinal"] == -1 \
            and failed_ordinal is not None and len(commands) == failed_ordinal + 1:
        command_ordinal = len(commands) - 1
        expected[f"logs/{command_ordinal:03d}.stdout"] = "stdout"
        expected[f"logs/{command_ordinal:03d}.stderr"] = "stderr"
    cases = evidence["cases"]
    assert isinstance(cases, list)
    for case in cases:
        assert isinstance(case, dict)
        command = case["command"]
        assert isinstance(command, dict)
        if command["kind"] != "":
            expected[f"case-inputs/{case['ordinal']:03d}.json"] = "case_input"
            expected[str(case["stdout_path"])] = "stdout"
            expected[str(case["stderr_path"])] = "stderr"
    return expected


def validate_retained_case_input(raw: bytes, case: Mapping[str, object], frozen: Mapping[str, object]) -> None:
    record = exact_keys(parse_record(raw, 4 * 1024 * 1024), (
        "schema_version", "artifact_kind", "model_id", "model_path", "pack_path", "geometry_path",
        "options_path", "cache_budget_bytes", "prompt_utf8", "maximum_tokens", "temperature_micros", "seed",
        "expected_prompt_ids", "expected_token_ids", "expected_output_utf8", "forced_ids", "stream_root",
        "stream_name", "stream_limit"), "retained case input")
    if canonical(record) != raw or type(record["schema_version"]) is not int or record["schema_version"] != 1 \
            or record["artifact_kind"] != "GPU_RUNTIME_CASE_INPUT" or record["model_id"] != case["model_id"]:
        raise RecipeError("retained case input identity is invalid")
    for key, expected_key in (("prompt_utf8", "prompt_utf8"), ("maximum_tokens", "maximum_tokens"),
                              ("temperature_micros", "temperature_micros"), ("seed", "seed"),
                              ("expected_prompt_ids", "prompt_token_ids"), ("expected_token_ids", "expected_token_ids"),
                              ("expected_output_utf8", "expected_output_utf8"), ("forced_ids", "teacher_forced_token_ids")):
        if type(record[key]) is not type(frozen[expected_key]) or record[key] != frozen[expected_key]:
            raise RecipeError("retained case input differs from frozen case")
    for key, maximum in (("expected_prompt_ids", 2048), ("expected_token_ids", 128), ("forced_ids", 4096)):
        require_i32_array(record[key], "retained case " + key, minimum=1, maximum=maximum)
    gpu = case["execution"] == "gpu_resident"
    for key in ("model_path", "pack_path", "geometry_path", "stream_root", "options_path"):
        value = bounded_text(record[key], 0 if key == "options_path" and not gpu else 1, 4096, "case input path")
        if "\0" in value or (value and not pathlib.Path(value).is_absolute()):
            raise RecipeError("retained case input path is invalid")
    if bool(record["options_path"]) != gpu:
        raise RecipeError("retained case input execution role differs")
    budget = bounded_i64(record["cache_budget_bytes"], 0, I64_MAX, "case input cache budget")
    if (case["model_id"] == "qwen2" and budget != 0) or (case["model_id"] == "olmoe" and budget == 0):
        raise RecipeError("retained case input cache policy differs")
    name = bounded_text(record["stream_name"], 1, 64, "case input stream name")
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name) is None:
        raise RecipeError("retained case input stream name is invalid")
    bounded_i64(record["stream_limit"], 108, 4 * 1024 * 1024 * 1024, "case input stream limit")


def replay_evidence_directory(root: pathlib.Path) -> dict[str, object]:
    files, directories = read_evidence_tree(root)
    if "result.json" not in files:
        raise RecipeError("evidence result.json is absent")
    try:
        preliminary = parse_record(files["profile.json"], MAX_PROFILE_BYTES)
        embedded = preliminary["runtime_options"]
        if not isinstance(embedded, list) or len(embedded) != 1 or not isinstance(embedded[0], dict):
            raise RecipeError("evidence profile runtime option is invalid")
        standalone = {key: value for key, value in embedded[0].items() if key != "option_id"}
        models = preliminary["models"]
        if not isinstance(models, list) or len(models) != 2:
            raise RecipeError("evidence profile models are invalid")
        calibration_paths = [str(model["calibration_path"]) for model in models]
    except (KeyError, TypeError) as exc:
        raise RecipeError("evidence profile cannot select retained inputs") from exc
    try:
        records = validate_evidence_records(
            runtime_option_raw=canonical(standalone),
            align_source_raw=files["source/align-llm/manifest.json"],
            ggml_source_raw=files["source/ggml/manifest.json"],
            bundle_raw=files["bundle-manifest.json"],
            calibration_raws=[files[path] for path in calibration_paths],
            profile_raw=files["profile.json"],
            evidence_raw=files["result.json"],
        )
    except KeyError as exc:
        raise RecipeError("evidence directory is missing a required record") from exc
    for key, path in (
        ("runtime_option", None),
        ("align_source", "source/align-llm/manifest.json"),
        ("ggml_source", "source/ggml/manifest.json"),
        ("bundle", "bundle-manifest.json"),
        ("profile", "profile.json"),
        ("evidence", "result.json"),
    ):
        if path is not None and canonical(records[key]) != files[path]:
            raise RecipeError(f"evidence {key} is not stored canonically")
    calibrations = records["calibrations"]
    assert isinstance(calibrations, list)
    for calibration, path in zip(calibrations, calibration_paths, strict=True):
        if canonical(calibration) != files[path]:
            raise RecipeError("evidence calibration is not stored canonically")

    evidence = records["evidence"]
    assert isinstance(evidence, dict)
    rows = evidence["files"]
    assert isinstance(rows, list)
    row_map = {str(row["path"]): row for row in rows}
    expected_paths = {"result.json", *row_map}
    if set(files) != expected_paths:
        raise RecipeError("evidence file closure does not match result.json")
    expected_directories = {
        parent.as_posix()
        for path in expected_paths
        for parent in pathlib.PurePosixPath(path).parents
        if parent.as_posix() != "."
    }
    if directories != expected_directories:
        raise RecipeError("evidence directory closure is invalid")
    expected_roles = expected_directory_roles(records)
    if set(row_map) != set(expected_roles):
        raise RecipeError("evidence required file closure is incomplete")
    for path, row in row_map.items():
        assert isinstance(row, dict)
        data = files[path]
        if row["role"] != expected_roles[path] or len(data) != row["bytes"] \
                or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise RecipeError("evidence retained file identity or role does not match")

    frozen_by_id = {case["case_id"]: case for calibration in calibrations for case in calibration["cases"]}
    for case in evidence["cases"]:
        if case["command"]["kind"]:
            validate_retained_case_input(files[f"case-inputs/{case['ordinal']:03d}.json"],
                                         case, frozen_by_id[case["calibration_case_id"]])

    align_summary = replay_source_snapshot(root / "source" / "align-llm", "align-llm")
    ggml_summary = replay_source_snapshot(root / "source" / "ggml", "ggml")
    source = evidence["source"]
    bundle_evidence = evidence["bundle"]
    assert isinstance(source, dict) and isinstance(bundle_evidence, dict)
    if align_summary["snapshot_sha256"] != source["source_snapshot_sha256"] \
            or ggml_summary["snapshot_sha256"] != bundle_evidence["ggml_source_snapshot_sha256"]:
        raise RecipeError("evidence source replay identity does not match result")
    return records
