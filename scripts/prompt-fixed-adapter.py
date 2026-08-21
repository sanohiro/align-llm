#!/usr/bin/env python3
"""Deterministic, silent C6 fixture adapter backed by the contained coding runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "eval" / "runners" / "run-coding-task.py"
TASK = ROOT / "eval" / "tasks" / "coding-v1" / "python-inclusive-range" / "task.json"
PATCHES = {
    "PARENT": ROOT / "eval" / "baselines" / "patches" / "python-inclusive-range-parent.patch",
    "CANDIDATE": ROOT / "eval" / "baselines" / "patches" / "python-inclusive-range.patch",
}
REQUEST_LIMIT = 65_536
ARTIFACT_LIMIT = 2_097_152
RESULT_LIMIT = 262_144
DIAGNOSTIC_LIMIT = 16_384
HEX64 = frozenset("0123456789abcdef")


class AdapterError(ValueError):
    """The adapter request or a declared input is invalid."""


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def canonical_digest_bytes(value: Any) -> bytes:
    def omit_none(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: omit_none(child) for key, child in item.items() if child is not None}
        if isinstance(item, list):
            return [omit_none(child) for child in item]
        return item

    return canonical_bytes(omit_none(value))


def bind_digest(value: dict[str, Any]) -> None:
    value["content_sha256"] = ""
    value["content_sha256"] = hashlib.sha256(canonical_digest_bytes(value)).hexdigest()


def valid_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in HEX64 for character in value)


def read_bounded(path: Path, maximum: int) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise AdapterError("adapter input is unavailable") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > maximum:
            raise AdapterError("adapter input type or size is invalid")
        output = bytearray()
        while len(output) <= maximum:
            chunk = os.read(descriptor, min(65_536, maximum + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
        if len(output) > maximum:
            raise AdapterError("adapter input exceeds its limit")
        return bytes(output)
    finally:
        os.close(descriptor)


def decoded_artifact(path: Path, maximum: int, kind: str) -> dict[str, Any]:
    try:
        value = json.loads(read_bounded(path, maximum).decode("utf-8", "strict"))
    except (UnicodeError, json.JSONDecodeError):
        raise AdapterError("adapter input is not canonical JSON") from None
    if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("artifact_kind") != kind:
        raise AdapterError("adapter input header is invalid")
    if not valid_digest(value.get("content_sha256")):
        raise AdapterError("adapter input digest is invalid")
    normalized = dict(value)
    normalized["content_sha256"] = ""
    if canonical_bytes(normalized) != canonical_bytes(json.loads(canonical_bytes(normalized))):
        raise AdapterError("adapter input cannot be normalized")
    if hashlib.sha256(canonical_digest_bytes(normalized)).hexdigest() != value["content_sha256"]:
        raise AdapterError("adapter input digest does not match")
    return value


REQUEST_FIELDS = (
    "schema_version", "artifact_kind", "evaluation_id", "task_id", "sample_index", "variant",
    "variant_path", "variant_sha256", "rendered_prompt_path", "rendered_prompt_sha256",
    "generation_policy_path", "generation_policy_sha256", "provider_control_path",
    "provider_control_sha256", "workspace_path", "result_path", "paired_seed",
    "credential_env_name", "environment_policy_sha256", "content_sha256",
)


def load_request(path: Path) -> dict[str, Any]:
    value = decoded_artifact(path, REQUEST_LIMIT, "TASK_ADAPTER_REQUEST")
    if tuple(value) != REQUEST_FIELDS:
        raise AdapterError("adapter request fields are invalid")
    if value["variant"] not in PATCHES or not isinstance(value["sample_index"], int) or value["sample_index"] < 1:
        raise AdapterError("adapter request sample identity is invalid")
    if not isinstance(value["paired_seed"], int) or value["credential_env_name"] is not None:
        raise AdapterError("fixture adapter seed or credential identity is invalid")
    for name in (
        "variant_sha256", "rendered_prompt_sha256", "generation_policy_sha256",
        "provider_control_sha256", "environment_policy_sha256",
    ):
        if not valid_digest(value[name]):
            raise AdapterError("adapter request contains an invalid digest")
    return value


def same_path(left: str, right: Path) -> bool:
    try:
        return Path(left).resolve(strict=True) == right.resolve(strict=True)
    except OSError:
        return False


def runtime_identity() -> str:
    return "PYTHON:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def environment_probe() -> dict[str, Any]:
    logical = os.cpu_count()
    value = {
        "schema_version": 1,
        "artifact_kind": "ENVIRONMENT_PROBE",
        "producer": "MEASUREMENT_ADAPTER",
        "os": platform.system().lower(),
        "os_release": platform.release(),
        "architecture": platform.machine().lower(),
        "cpu": platform.processor() or platform.machine().lower(),
        "logical_cpu_count": logical if logical and logical > 0 else None,
        "gpu": "none",
        "runtime_identity": runtime_identity(),
        "content_sha256": "",
    }
    bind_digest(value)
    return value


def provider_identities(
    request: Mapping[str, Any], rendered: Mapping[str, Any], policy: Mapping[str, Any], control: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    provider_request = {
        "provider_kind": "FIXTURE",
        "provider_model": control["model"],
        "rendered_prompt_sha256": rendered["content_sha256"],
        "max_tokens": policy["max_tokens"],
        "temperature_micros": policy["temperature_micros"],
        "paired_seed": request["paired_seed"],
    }
    provider_sha = hashlib.sha256(canonical_bytes(provider_request)).hexdigest()
    attestation = {
        "schema_version": 1,
        "artifact_kind": "SEED_CAPABILITY_ATTESTATION",
        "provider_kind": "FIXTURE",
        "provider_model": control["model"],
        "requested_seed": request["paired_seed"],
        "result": "APPLIED",
        "applied_seed": request["paired_seed"],
        "provider_request_sha256": provider_sha,
        "content_sha256": "",
    }
    bind_digest(attestation)
    generation = {
        "schema_version": 1,
        "artifact_kind": "GENERATION_REQUEST_IDENTITY",
        "rendered_prompt_sha256": rendered["content_sha256"],
        "system_text_sha256": hashlib.sha256(b"").hexdigest(),
        "user_text_sha256": hashlib.sha256(rendered["text"].encode("utf-8")).hexdigest(),
        "generation_policy_sha256": policy["content_sha256"],
        "provider_control_sha256": control["content_sha256"],
        "environment_policy_sha256": request["environment_policy_sha256"],
        "max_tokens": policy["max_tokens"],
        "temperature_micros": policy["temperature_micros"],
        "paired_seed": request["paired_seed"],
        "provider_request_sha256": provider_sha,
        "seed_attestation_sha256": attestation["content_sha256"],
        "content_sha256": "",
    }
    bind_digest(generation)
    return generation, attestation


def execute_fixture(variant: str, timeout_ns: int) -> tuple[bool, bytes, bytes]:
    timeout = max(0.001, timeout_ns / 1_000_000_000)
    environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    try:
        process = subprocess.Popen(
            [sys.executable, str(RUNNER), str(TASK), str(PATCHES[variant])],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(timeout=timeout)
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            pass
        else:
            os.killpg(process.pid, signal.SIGKILL)
            return False, b"", b"contained runner left a descendant"
        return process.returncode == 0, stdout[:DIAGNOSTIC_LIMIT], stderr[:DIAGNOSTIC_LIMIT]
    except subprocess.TimeoutExpired as error:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=1)
        return False, b"", str(error).encode("utf-8")[:DIAGNOSTIC_LIMIT]
    except OSError as error:
        return False, b"", str(error).encode("utf-8")[:DIAGNOSTIC_LIMIT]


def measurement(
    request: Mapping[str, Any], rendered: Mapping[str, Any], policy: Mapping[str, Any], control: Mapping[str, Any]
) -> dict[str, Any]:
    passed, stdout, stderr = execute_fixture(request["variant"], int(control["timeout_ns"]))
    generation, attestation = provider_identities(request, rendered, policy, control)
    is_candidate = request["variant"] == "CANDIDATE"
    status = "PASS" if passed else "FAIL"
    value = {
        "schema_version": 1,
        "artifact_kind": "TASK_MEASUREMENT",
        "status": status,
        "failure_kind": "NONE" if passed else "TEST",
        "build_status": "PASS",
        "test_status": "PASS" if passed else "FAIL",
        "repair_loop_count": 0 if passed else 1,
        "unrelated_diff_count": 0,
        "patch_size_bytes": PATCHES[request["variant"]].stat().st_size,
        "public_api_change_count": 0,
        "policy_violation_count": 0,
        "cleanup_passed": True,
        "containment_passed": True,
        "benchmark_regression_ppm": None,
        "generation_to_passing_patch_ns": 80_000_000 if passed and is_candidate else None,
        "rendered_prompt_sha256": rendered["content_sha256"],
        "generation_request": generation,
        "environment_probe": environment_probe(),
        "seed_attestation": attestation,
        "diagnostic_summary": "contained fixture passed" if passed else "contained fixture failed as expected",
        "diagnostic_stdout": stdout.decode("utf-8", "replace"),
        "diagnostic_stderr": stderr.decode("utf-8", "replace"),
        "content_sha256": "",
    }
    bind_digest(value)
    return value


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    raw = canonical_bytes(value)
    if len(raw) > RESULT_LIMIT:
        raise AdapterError("adapter result exceeds its bound")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            offset += os.write(descriptor, raw[offset:])
    finally:
        os.close(descriptor)


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-variant", required=True, type=Path)
    parser.add_argument("--rendered-prompt", required=True, type=Path)
    parser.add_argument("--sample-index", required=True, type=int)
    parser.add_argument("--paired-seed", required=True, type=int)
    parser.add_argument("--adapter-request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    values = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    try:
        request = load_request(values.adapter_request)
        if (
            request["sample_index"] != values.sample_index
            or request["paired_seed"] != values.paired_seed
            or not same_path(request["variant_path"], values.prompt_variant)
            or not same_path(request["rendered_prompt_path"], values.rendered_prompt)
            or Path(request["result_path"]) != values.result
        ):
            raise AdapterError("adapter CLI and request identities disagree")
        variant = decoded_artifact(values.prompt_variant, ARTIFACT_LIMIT, "PROMPT_VARIANT")
        rendered = decoded_artifact(values.rendered_prompt, ARTIFACT_LIMIT, "RENDERED_PROMPT")
        policy = decoded_artifact(Path(request["generation_policy_path"]), ARTIFACT_LIMIT, "GENERATION_POLICY")
        control = decoded_artifact(Path(request["provider_control_path"]), ARTIFACT_LIMIT, "EVALUATION_PROVIDER_CONTROL")
        if (
            variant["content_sha256"] != request["variant_sha256"]
            or rendered["content_sha256"] != request["rendered_prompt_sha256"]
            or rendered["variant_sha256"] != variant["content_sha256"]
            or rendered["variant_id"] != variant["variant_id"]
            or policy["content_sha256"] != request["generation_policy_sha256"]
            or control["content_sha256"] != request["provider_control_sha256"]
            or policy["provider_control_sha256"] != control["content_sha256"]
            or policy["evaluation_provider_kind"] != "FIXTURE"
            or control["provider_kind"] != "FIXTURE"
            or policy["evaluation_provider_model"] != control["model"]
            or policy["seed_mode"] != "PAIRED_FIXED"
        ):
            raise AdapterError("adapter declared identities disagree")
        write_exclusive(values.result, measurement(request, rendered, policy, control))
        return 0
    except (AdapterError, OSError, TypeError, ValueError, KeyError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
