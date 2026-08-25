#!/usr/bin/env python3
"""Deterministic, silent C6 fixture adapter backed by the contained coding runner."""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import platform
import selectors
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "eval" / "runners" / "run-coding-task.py"
TASK = ROOT / "eval" / "tasks" / "coding-v1" / "python-inclusive-range" / "task.json"
PATCHES = {
    "PARENT": ROOT / "eval" / "baselines" / "patches" / "python-inclusive-range-parent.patch",
    "CANDIDATE": ROOT / "eval" / "baselines" / "patches" / "python-inclusive-range.patch",
}
RUNNER_SHA256 = "6d6c203be044e993f04a2261e3b03c19aca06ae369e25743d8bed174e7879bcd"
TASK_SHA256 = "1884f01a329752c1383081342c65d062241aefaefff2f206f6604008bde74940"
PATCH_SHA256 = {
    "PARENT": "a2c2aac194d3cdad9808c23923afa64cf8f09909d2b5519ae08c7d94218d1fe3",
    "CANDIDATE": "dd5cc51395782e77775d63d982973458200769318a7c5c94c4a54c4c999824ce",
}
REQUEST_LIMIT = 65_536
ARTIFACT_LIMIT = 2_097_152
RESULT_LIMIT = 262_144
DIAGNOSTIC_LIMIT = 16_384
HEX64 = frozenset("0123456789abcdef")
PR_SET_CHILD_SUBREAPER = 36
TRUNCATION_MARKER = b"\n[output truncated]"
RUNNER_BOOTSTRAP = (
    "import os,sys;fd=int(sys.argv.pop(1));name=sys.argv.pop(1);"
    "data=b''.join(iter(lambda:os.read(fd,65536),b''));"
    "globals()['__file__']=name;exec(compile(data,name,'exec'))"
)


def enable_child_subreaper() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    try:
        return ctypes.CDLL(None, use_errno=True).prctl(
            PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0,
        ) == 0
    except (AttributeError, OSError):
        return False


CHILD_SUBREAPER_ENABLED = enable_child_subreaper()


class AdapterError(ValueError):
    """The adapter request or a declared input is invalid."""


class ImmutableInput:
    """A verified pathname snapshot copied into one sealed anonymous regular file."""

    def __init__(self, path: Path, expected_sha256: str, label: str) -> None:
        source = -1
        descriptor = -1
        try:
            source = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            before = os.fstat(source)
            if not stat.S_ISREG(before.st_mode) or before.st_size < 0 or before.st_size > ARTIFACT_LIMIT:
                raise AdapterError(f"{label} type or size is invalid")
            raw = bytearray()
            offset = 0
            while offset < before.st_size:
                chunk = os.pread(source, min(65_536, before.st_size - offset), offset)
                if not chunk:
                    raise AdapterError(f"{label} changed while reading")
                raw.extend(chunk)
                offset += len(chunk)
            after = os.fstat(source)
            identity = lambda value: (
                value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns,
            )
            if identity(before) != identity(after) or hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise AdapterError(f"{label} identity disagrees")
            descriptor = os.memfd_create(
                f"align-{label}", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING,
            )
            written = 0
            while written < len(raw):
                written += os.write(descriptor, raw[written:])
            os.lseek(descriptor, 0, os.SEEK_SET)
            seals = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE
            fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)
            if fcntl.fcntl(descriptor, fcntl.F_GET_SEALS) != seals:
                raise AdapterError(f"{label} sealing failed")
            self.descriptor = descriptor
            self.seals = seals
            self.byte_count = len(raw)
            descriptor = -1
        except OSError:
            raise AdapterError(f"{label} is unavailable") from None
        finally:
            if source >= 0:
                os.close(source)
            if descriptor >= 0:
                os.close(descriptor)

    def process_path(self) -> str:
        return f"/proc/self/fd/{self.descriptor}"

    def verify_sealed(self) -> None:
        if fcntl.fcntl(self.descriptor, fcntl.F_GET_SEALS) != self.seals:
            raise AdapterError("retained runner input lost its seals")

    def close(self) -> None:
        os.close(self.descriptor)


def process_group_exists(group: int) -> bool:
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def descendant_process_ids(root_pids: set[int]) -> set[int]:
    """Return the live descendants of `root_pids` from the /proc parent links.

    A zombie (`State: Z`) has already terminated and holds only a process-table
    slot until someone waits for it, so it cannot escape containment and is
    never reported. Under `PR_SET_CHILD_SUBREAPER` an adopted orphan that has
    already exited becomes a permanent zombie child of this process, and
    counting it would report a containment failure for a process that no longer
    runs. Zombies are still traversed, so a live entry parented to one is still
    reported. An entry that exits between the directory scan and the status read
    is skipped by the same `OSError` path.
    """
    parents: dict[int, list[int]] = {}
    zombies: set[int] = set()
    if not sys.platform.startswith("linux"):
        return set()
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            pid = int(status_path.parent.name)
            status_lines = status_path.read_text(encoding="utf-8").splitlines()
            parent_line = next(
                line for line in status_lines if line.startswith("PPid:")
            )
            parent = int(parent_line.split()[1])
            state_line = next(
                line for line in status_lines if line.startswith("State:")
            )
            state = state_line.split()[1]
        except (IndexError, OSError, StopIteration, ValueError):
            continue
        if state == "Z":
            zombies.add(pid)
        parents.setdefault(parent, []).append(pid)
    descendants: set[int] = set()
    visited: set[int] = set()
    pending = list(root_pids)
    while pending:
        parent = pending.pop()
        for child in parents.get(parent, []):
            if child not in visited:
                visited.add(child)
                pending.append(child)
                if child not in zombies:
                    descendants.add(child)
    return descendants


def owned_descendant_ids(process: subprocess.Popen[bytes] | None = None) -> set[int]:
    roots = {os.getpid()}
    if process is not None:
        roots.add(process.pid)
    descendants = descendant_process_ids(roots)
    descendants.discard(os.getpid())
    if process is not None:
        descendants.discard(process.pid)
    return descendants


def kill_process_ids(process_ids: set[int]) -> bool:
    complete = True
    for pid in process_ids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            complete = False
    return complete


def reap_process_ids(process_ids: set[int], maximum_seconds: float) -> None:
    pending = set(process_ids)
    deadline = time.monotonic() + maximum_seconds
    while pending and time.monotonic() < deadline:
        for pid in tuple(pending):
            try:
                waited, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                if not Path(f"/proc/{pid}").exists():
                    pending.discard(pid)
                continue
            if waited == pid:
                pending.discard(pid)
        if pending:
            time.sleep(0.01)


def cleanup_process_group(process: subprocess.Popen[bytes], maximum_seconds: float = 2.0) -> bool:
    if not CHILD_SUBREAPER_ENABLED:
        return False
    complete = True
    owned = owned_descendant_ids(process)
    complete = kill_process_ids(owned)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        complete = False
    try:
        process.wait(timeout=maximum_seconds)
    except (OSError, subprocess.TimeoutExpired):
        complete = False
    adopted = owned_descendant_ids()
    complete = kill_process_ids(adopted) and complete
    owned.update(adopted)
    reap_process_ids(owned, maximum_seconds)
    deadline = time.monotonic() + maximum_seconds
    while time.monotonic() < deadline:
        adopted = owned_descendant_ids()
        if not process_group_exists(process.pid) and not adopted:
            return complete
        complete = kill_process_ids(adopted) and complete
        reap_process_ids(adopted, 0.05)
        time.sleep(0.01)
    return complete and not process_group_exists(process.pid) and not owned_descendant_ids()


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


# The section 11.3 task-parameterization fields are appended after `environment_policy_sha256` and
# before `content_sha256`, so every field this fixture adapter already relied on keeps its position.
# This adapter keeps its hard-coded runner, task, and patch identities and remains the deterministic
# non-gate fixture owner; it changes only to keep the exact field-order check and the
# `EvaluationInputIdentity.adapter_request_sha256` preimage in agreement with the evaluator.
REQUEST_FIELDS = (
    "schema_version", "artifact_kind", "evaluation_id", "task_id", "sample_index", "variant",
    "variant_path", "variant_sha256", "rendered_prompt_path", "rendered_prompt_sha256",
    "generation_policy_path", "generation_policy_sha256", "provider_control_path",
    "provider_control_sha256", "workspace_path", "result_path", "paired_seed",
    "credential_env_name", "environment_policy_sha256", "validation_runner_path",
    "validation_runner_sha256", "task_definition_path", "task_definition_sha256",
    "validation_argv", "patch_path", "patch_sha256", "generation_child_path",
    "generation_child_sha256", "task_deadline_ns", "content_sha256",
)


def load_request(path: Path) -> dict[str, Any]:
    value = decoded_artifact(path, REQUEST_LIMIT, "TASK_ADAPTER_REQUEST")
    if tuple(value) != REQUEST_FIELDS:
        raise AdapterError("adapter request fields are invalid")
    if value["variant"] not in PATCHES or not isinstance(value["sample_index"], int) or value["sample_index"] < 1:
        raise AdapterError("adapter request sample identity is invalid")
    if not isinstance(value["paired_seed"], int) or value["credential_env_name"] is not None:
        raise AdapterError("fixture adapter seed or credential identity is invalid")
    deadline = value["task_deadline_ns"]
    if not isinstance(deadline, int) or isinstance(deadline, bool) or deadline <= 0:
        raise AdapterError("adapter request task deadline is invalid")
    for name in (
        "variant_sha256", "rendered_prompt_sha256", "generation_policy_sha256",
        "provider_control_sha256", "environment_policy_sha256", "validation_runner_sha256",
        "task_definition_sha256", "generation_child_sha256",
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


class BoundedCapture:
    def __init__(self) -> None:
        self.data = bytearray()
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        if self.truncated:
            return
        remaining = DIAGNOSTIC_LIMIT - len(self.data)
        if len(chunk) > remaining:
            self.data.extend(chunk[:remaining])
            self.truncated = True
        else:
            self.data.extend(chunk)

    def bytes(self) -> bytes:
        if not self.truncated:
            return bytes(self.data)
        prefix = max(0, DIAGNOSTIC_LIMIT - len(TRUNCATION_MARKER))
        return bytes(self.data[:prefix]) + TRUNCATION_MARKER


def capture_fixture_output(
    process: subprocess.Popen[bytes], timeout: float,
) -> tuple[bytes, bytes]:
    captures = {"stdout": BoundedCapture(), "stderr": BoundedCapture()}
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + timeout
    try:
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            assert stream is not None
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout)
            events = selector.select(remaining)
            if not events:
                raise subprocess.TimeoutExpired(process.args, timeout)
            for key, _ in events:
                stream = key.fileobj
                try:
                    chunk = os.read(stream.fileno(), 65_536)
                except BlockingIOError:
                    continue
                if chunk:
                    captures[key.data].append(chunk)
                else:
                    selector.unregister(stream)
                    stream.close()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout)
        process.wait(timeout=remaining)
    finally:
        selector.close()
        for stream in (process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
    return captures["stdout"].bytes(), captures["stderr"].bytes()


def execute_fixture(variant: str, timeout_ns: int) -> tuple[str, bool, bool, bytes, bytes, int]:
    timeout = max(0.001, timeout_ns / 1_000_000_000)
    environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/tools:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    for name in (
        "ALIGN_LLM_FRESH_COMPILER",
        "ALIGN_LLM_BWRAP",
        "ALIGN_LLM_PRLIMIT",
        "ALIGN_LLM_TOOL_ROOT",
        "ALIGN_LLM_PYTHON",
        "ALIGN_LLM_VALIDATION_USERNS_PATH",
    ):
        if name in os.environ:
            environment[name] = os.environ[name]
    process: subprocess.Popen[bytes] | None = None
    retained: list[ImmutableInput] = []
    patch_byte_count = 0
    try:
        if not CHILD_SUBREAPER_ENABLED:
            return "ERROR", False, False, b"", b"child-subreaper containment is unavailable", 0
        runner = ImmutableInput(RUNNER, RUNNER_SHA256, "coding-runner")
        retained.append(runner)
        task = ImmutableInput(TASK, TASK_SHA256, "coding-task")
        retained.append(task)
        patch = ImmutableInput(PATCHES[variant], PATCH_SHA256[variant], "coding-patch")
        retained.append(patch)
        patch_byte_count = patch.byte_count
        process = subprocess.Popen(
            [
                sys.executable, "-c", RUNNER_BOOTSTRAP, str(runner.descriptor), str(RUNNER),
                "--retained-inputs", task.process_path(), patch.process_path(),
            ],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,
            pass_fds=tuple(item.descriptor for item in retained),
        )
        stdout, stderr = capture_fixture_output(process, timeout)
        for item in retained:
            item.verify_sealed()
        if process_group_exists(process.pid) or owned_descendant_ids(process):
            cleanup_passed = cleanup_process_group(process)
            return "ERROR", cleanup_passed, False, b"", b"contained runner left a descendant", patch_byte_count
        outcome = "PASS" if process.returncode == 0 else "TEST_FAIL" if process.returncode == 4 else "ERROR"
        return outcome, True, True, stdout, stderr, patch_byte_count
    except subprocess.TimeoutExpired as error:
        assert process is not None
        cleanup_passed = cleanup_process_group(process)
        return "ERROR", cleanup_passed, cleanup_passed, b"", str(error).encode("utf-8")[:DIAGNOSTIC_LIMIT], patch_byte_count
    except OSError as error:
        cleanup_passed = True if process is None else cleanup_process_group(process)
        return "ERROR", cleanup_passed, cleanup_passed, b"", str(error).encode("utf-8")[:DIAGNOSTIC_LIMIT], patch_byte_count
    except AdapterError as error:
        cleanup_passed = True if process is None else cleanup_process_group(process)
        return "ERROR", cleanup_passed, cleanup_passed, b"", str(error).encode("utf-8")[:DIAGNOSTIC_LIMIT], patch_byte_count
    finally:
        for item in retained:
            item.close()


def measurement(
    request: Mapping[str, Any], rendered: Mapping[str, Any], policy: Mapping[str, Any], control: Mapping[str, Any]
) -> dict[str, Any]:
    prompt_oversized = len(rendered["text"].encode("utf-8")) > policy["max_prompt_bytes"]
    if prompt_oversized:
        outcome, cleanup_passed, containment_passed = "POLICY", True, True
        stdout, stderr, patch_byte_count = b"", b"", 0
    else:
        outcome, cleanup_passed, containment_passed, stdout, stderr, patch_byte_count = execute_fixture(
            request["variant"], int(control["timeout_ns"])
        )
    generation, attestation = provider_identities(request, rendered, policy, control)
    is_candidate = request["variant"] == "CANDIDATE"
    passed = outcome == "PASS"
    expected_failure = outcome == "TEST_FAIL"
    policy_violation = outcome == "POLICY"
    status = "PASS" if passed else "FAIL" if expected_failure else "POLICY_VIOLATION" if policy_violation else "ERROR"
    value = {
        "schema_version": 1,
        "artifact_kind": "TASK_MEASUREMENT",
        "status": "ERROR" if not cleanup_passed or not containment_passed else status,
        "failure_kind": "CONTAINMENT" if not containment_passed else "CLEANUP" if not cleanup_passed else "NONE" if passed else "TEST" if expected_failure else "POLICY" if policy_violation else "ADAPTER",
        "build_status": "NOT_RUN" if policy_violation else "PASS" if outcome != "ERROR" else "ERROR",
        "test_status": "NOT_RUN" if policy_violation else "PASS" if passed else "FAIL" if expected_failure else "ERROR",
        "repair_loop_count": 1 if expected_failure else 0,
        "unrelated_diff_count": 0,
        "patch_size_bytes": patch_byte_count,
        "public_api_change_count": 0,
        "policy_violation_count": 1 if policy_violation else 0,
        "cleanup_passed": cleanup_passed,
        "containment_passed": containment_passed,
        "benchmark_regression_ppm": None,
        "generation_to_passing_patch_ns": 80_000_000 if passed and is_candidate else None,
        "rendered_prompt_sha256": rendered["content_sha256"],
        "generation_request": generation,
        "environment_probe": environment_probe(),
        "seed_attestation": attestation,
        "diagnostic_summary": "prompt exceeds max_prompt_bytes" if policy_violation else "contained fixture passed" if passed else "contained fixture failed as expected" if expected_failure else "contained fixture runner failed",
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


def write_retained_result(path: Path, descriptor: int, value: Mapping[str, Any]) -> None:
    raw = canonical_bytes(value)
    if len(raw) > RESULT_LIMIT:
        raise AdapterError("adapter result exceeds its bound")
    descriptor_metadata = os.fstat(descriptor)
    path_metadata = os.stat(path, follow_symlinks=False)
    if (
        not stat.S_ISREG(descriptor_metadata.st_mode)
        or descriptor_metadata.st_size != 0
        or (descriptor_metadata.st_dev, descriptor_metadata.st_ino)
        != (path_metadata.st_dev, path_metadata.st_ino)
    ):
        raise AdapterError("adapter result descriptor identity is invalid")
    offset = 0
    while offset < len(raw):
        offset += os.write(descriptor, raw[offset:])
    os.fsync(descriptor)


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-variant", required=True, type=Path)
    parser.add_argument("--rendered-prompt", required=True, type=Path)
    parser.add_argument("--sample-index", required=True, type=int)
    parser.add_argument("--paired-seed", required=True, type=int)
    parser.add_argument("--adapter-request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--result-fd", type=int)
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
        result = measurement(request, rendered, policy, control)
        if values.result_fd is None:
            write_exclusive(values.result, result)
        else:
            write_retained_result(values.result, values.result_fd, result)
        return 0
    except (AdapterError, OSError, TypeError, ValueError, KeyError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
