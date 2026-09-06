#!/usr/bin/env python3
"""Validate G1 schema-1 bundle, calibration, and qualification profile records."""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
import re
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
    strict_object,
    validate_source_manifest,
)


MAX_PROFILE_BYTES = 256 * 1024
MAX_CALIBRATION_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = 256 * 1024
I64_MAX = 2**63 - 1
I64_MIN = -(2**63)
I32_MAX = 2**31 - 1
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
CASE_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,48}\Z")


def exact_keys(value: object, expected: tuple[str, ...], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or len(value) != len(expected) or set(value) != set(expected):
        raise RecipeError(f"{label} keys are invalid")
    return {key: value[key] for key in expected}


def parse_record(raw: bytes, maximum: int) -> dict[str, object]:
    if not raw or len(raw) > maximum or raw.startswith(b"\xef\xbb\xbf") \
            or not raw.endswith(b"\n"):
        raise RecipeError("record framing is invalid")
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
                                     f"cases[{ordinal}].expected_token_ids", maximum=128)
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
