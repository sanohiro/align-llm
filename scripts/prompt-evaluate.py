#!/usr/bin/env python3
"""Deterministic C6 evaluator used by the Align command boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


REQUEST_LIMIT = 65_536
ARTIFACT_LIMIT = 2_097_152
MEASUREMENT_LIMIT = 262_144
SNAPSHOT_LIMIT = 1_048_576
RESULT_LIMIT = 268_435_456
EVIDENCE_LIMIT = 8_388_608
CHILD_CLEANUP_MARGIN_NS = 5_000_000_000
SNAPSHOT_HELPER_OUTER_TIMEOUT_NS = 35_000_000_000
SOURCE_VERIFIER_OUTER_TIMEOUT_NS = 125_000_000_000
CANONICAL_STRING_CHUNK = 16_384
HEX = frozenset("0123456789abcdef")
SOURCE_POLICY_FIELDS = (
    "schema_version", "artifact_kind", "policy_id", "helper_path", "helper_sha256",
    "helper_runtime", "interpreter_sha256", "git_executable_sha256", "content_sha256",
)
EVALUATE_REQUEST_FIELDS = (
    "schema_version", "artifact_kind", "evaluation_id", "project_root", "experiment_path",
    "parent_activation_path", "corpus_path", "sample_count", "acceptance_policy_path",
    "workspace_path", "workspace_preflight_path", "verifier_align_llm_repository_path",
    "verifier_align_llm_commit", "verifier_align_repository_path", "verifier_align_revision",
    "verifier_corpus_source_path", "verifier_corpus_source_kind",
    "verifier_corpus_file_set_manifest_path", "verifier_corpus_source_repository_id",
    "verifier_corpus_source_sha256", "verifier_source_policy_path",
    "verifier_source_policy_sha256", "verifier_python_executable_path",
    "verifier_git_executable_path", "evaluation_evidence_path",
)
EVALUATE_REQUEST_FIELDS_OMITTED = tuple(
    name for name in EVALUATE_REQUEST_FIELDS if name != "verifier_corpus_file_set_manifest_path"
)


class EvaluationError(ValueError):
    """A declared evaluation input or trusted child result is invalid."""


class ChildBoundaryError(EvaluationError):
    """A trusted child crossed a process timeout, capture, or execution boundary."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AdapterFailure(EvaluationError):
    """A validated adapter invocation failed after its input identity was established."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ResultOnlyInvalid(EvaluationError):
    """A decoded request failed before the paired-evidence boundary."""


class RetainedRegularFile:
    """One no-follow regular file whose identity remains bound through child launch."""

    def __init__(self, path: Path, maximum: int) -> None:
        try:
            self.descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        except OSError:
            raise EvaluationError("declared executable is unavailable") from None
        self.maximum = maximum
        try:
            self.identity = self._identity()
        except BaseException:
            os.close(self.descriptor)
            raise

    def _identity(self) -> tuple[int, int, int, int]:
        metadata = os.fstat(self.descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > self.maximum:
            raise EvaluationError("declared executable type or size is invalid")
        return metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size

    def sha256(self) -> str:
        hasher = hashlib.sha256()
        offset = 0
        while offset < self.identity[3]:
            chunk = os.pread(self.descriptor, min(1_048_576, self.identity[3] - offset), offset)
            if not chunk:
                raise EvaluationError("declared executable changed while reading")
            hasher.update(chunk)
            offset += len(chunk)
        return hasher.hexdigest()

    def verify_unchanged(self, expected: str) -> None:
        if self._identity() != self.identity or self.sha256() != expected:
            raise EvaluationError("declared executable changed during use")

    def process_path(self) -> str:
        path = f"/proc/self/fd/{self.descriptor}"
        if not Path(path).exists():
            raise EvaluationError("retained executable launch is unavailable")
        return path

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


def cleanup_process_group(process: subprocess.Popen[bytes], maximum_seconds: float = 2.0) -> bool:
    """Kill the private group, reap the direct child, and prove group absence."""

    complete = True
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
    deadline = time.monotonic() + maximum_seconds
    while process_group_exists(process.pid) and time.monotonic() < deadline:
        time.sleep(0.01)
    return complete and not process_group_exists(process.pid)


def canonical_chunks(value: Any, *, omit_mapping_none: bool = False):
    """Yield canonical JSON in bounded chunks without cloning the value graph."""

    if isinstance(value, Mapping):
        yield b"{"
        first = True
        for key, child in value.items():
            if omit_mapping_none and child is None:
                continue
            if not first:
                yield b","
            first = False
            yield from canonical_chunks(key)
            yield b":"
            yield from canonical_chunks(child, omit_mapping_none=omit_mapping_none)
        yield b"}"
        return
    if isinstance(value, (list, tuple)):
        yield b"["
        for ordinal, child in enumerate(value):
            if ordinal:
                yield b","
            yield from canonical_chunks(child, omit_mapping_none=omit_mapping_none)
        yield b"]"
        return
    if isinstance(value, str):
        yield b'"'
        for offset in range(0, len(value), CANONICAL_STRING_CHUNK):
            encoded = json.dumps(value[offset : offset + CANONICAL_STRING_CHUNK], ensure_ascii=False)
            yield encoded[1:-1].encode("utf-8")
        yield b'"'
        return
    yield json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def canonical(value: Any) -> bytes:
    return b"".join(canonical_chunks(value))


def canonical_digest_bytes(value: Any) -> bytes:
    return b"".join(canonical_chunks(value, omit_mapping_none=True))


def canonical_digest(value: Any) -> str:
    hasher = hashlib.sha256()
    for chunk in canonical_chunks(value, omit_mapping_none=True):
        hasher.update(chunk)
    return hasher.hexdigest()


def bind(value: dict[str, Any]) -> dict[str, Any]:
    value["content_sha256"] = ""
    value["content_sha256"] = canonical_digest(value)
    return value


def nested_owner_timeout(timeout_ns: int) -> int:
    """Leave the trusted inner owner time to kill, reap, and report first."""

    return timeout_ns + CHILD_CLEANUP_MARGIN_NS


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_hex(value: Any, sizes: tuple[int, ...] = (64,)) -> bool:
    return isinstance(value, str) and len(value) in sizes and all(character in HEX for character in value)


def valid_ascii_identifier(value: Any, *, allow_empty: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    raw = value.encode("utf-8")
    return (allow_empty and not raw) or bool(raw) and len(raw) <= 128 and all(0x20 <= byte <= 0x7E for byte in raw)


def validate_absolute_path_syntax(value: Any, label: str) -> None:
    if not isinstance(value, str) or len(value.encode("utf-8")) > 4096 or "\0" in value:
        raise EvaluationError(f"{label} path is invalid")
    components = value.split("/")
    if components[0] != "" or len(components) < 2 or any(
        not component
        or component in (".", "..")
        or len(component.encode("utf-8")) > 255
        for component in components[1:]
    ):
        raise EvaluationError(f"{label} path is invalid")


def validate_request_source_declaration(request: Mapping[str, Any]) -> None:
    evaluation_id = request.get("evaluation_id")
    if (
        not valid_ascii_identifier(evaluation_id)
        or "/" in evaluation_id
        or evaluation_id in (".", "..")
    ):
        raise EvaluationError("evaluation identifier is invalid")
    kind = request.get("verifier_corpus_source_kind")
    manifest = request.get("verifier_corpus_file_set_manifest_path")
    if kind == "FILE_SET":
        if not isinstance(manifest, str):
            raise EvaluationError("file-set manifest path is required")
        validate_absolute_path_syntax(manifest, "file-set manifest")
        if request.get("verifier_corpus_source_repository_id") != "":
            raise EvaluationError("file-set repository identity must be empty")
        if not valid_hex(request.get("verifier_corpus_source_sha256")):
            raise EvaluationError("file-set source digest is invalid")
    elif kind == "GIT_COMMIT":
        if manifest is not None:
            raise EvaluationError("Git source must not declare a file-set manifest")
        if not valid_ascii_identifier(request.get("verifier_corpus_source_repository_id")):
            raise EvaluationError("Git source repository identity is invalid")
        if not valid_hex(request.get("verifier_corpus_source_sha256"), (40, 64)):
            raise EvaluationError("Git source digest is invalid")
    else:
        raise EvaluationError("corpus source kind is invalid")
    for name, label in (
        ("verifier_align_llm_repository_path", "align-llm repository"),
        ("verifier_align_repository_path", "Align repository"),
        ("verifier_corpus_source_path", "corpus source"),
        ("verifier_python_executable_path", "source verifier Python executable"),
        ("verifier_git_executable_path", "source verifier Git executable"),
    ):
        validate_absolute_path_syntax(request.get(name), label)
    if not valid_hex(request.get("verifier_align_llm_commit"), (40, 64)):
        raise EvaluationError("align-llm source identity is invalid")
    if not valid_hex(request.get("verifier_align_revision"), (40, 64)):
        raise EvaluationError("Align source identity is invalid")
    if not valid_hex(request.get("verifier_source_policy_sha256")):
        raise EvaluationError("source verifier policy digest is invalid")


def read_bounded(path: Path, maximum: int) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise EvaluationError("evaluation input is unavailable") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > maximum:
            raise EvaluationError("evaluation input type or size is invalid")
        output = bytearray()
        while len(output) <= maximum:
            chunk = os.read(descriptor, min(65_536, maximum + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
        if len(output) > maximum:
            raise EvaluationError("evaluation input exceeds its bound")
        return bytes(output)
    finally:
        os.close(descriptor)


def load_json(path: Path, maximum: int) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            if key in value:
                raise EvaluationError("evaluation input has a duplicate field")
            value[key] = child
        return value

    try:
        value = json.loads(
            read_bounded(path, maximum).decode("utf-8", "strict"),
            object_pairs_hook=unique_object,
        )
    except (UnicodeError, json.JSONDecodeError):
        raise EvaluationError("evaluation input is not UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise EvaluationError("evaluation input is not an object")
    return value


def load_bound(path: Path, kind: str, maximum: int = ARTIFACT_LIMIT) -> dict[str, Any]:
    value = load_json(path, maximum)
    if value.get("schema_version") != 1 or value.get("artifact_kind") != kind or not valid_hex(value.get("content_sha256")):
        raise EvaluationError(f"{kind} header is invalid")
    normalized = dict(value)
    normalized["content_sha256"] = ""
    if hashlib.sha256(canonical_digest_bytes(normalized)).hexdigest() != value["content_sha256"]:
        raise EvaluationError(f"{kind} digest does not match")
    return value


def physical_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise EvaluationError("evaluation root is not absolute")
    current = Path("/")
    for component in path.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except OSError:
            raise EvaluationError("evaluation root is unavailable") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise EvaluationError("evaluation root contains a symlink")
    if not stat.S_ISDIR(os.stat(path, follow_symlinks=False).st_mode):
        raise EvaluationError("evaluation root is not a directory")
    return path.resolve(strict=True)


def relative_path(project: Path, value: Any, *, must_exist: bool = True) -> Path:
    if not isinstance(value, str) or not value or "\0" in value or Path(value).is_absolute():
        raise EvaluationError("project-relative path is invalid")
    parts = Path(value).parts
    if any(part in ("", ".", "..") for part in parts):
        raise EvaluationError("project-relative path has an invalid component")
    target = project.joinpath(*parts)
    parent = target if must_exist else target.parent
    physical_directory(parent if parent.is_dir() else parent.parent)
    if must_exist:
        try:
            resolved = target.resolve(strict=True)
        except FileNotFoundError:
            raise EvaluationError("evaluation input is unavailable") from None
        except OSError:
            raise EvaluationError("evaluation input cannot be read") from None
        try:
            resolved.relative_to(project)
        except ValueError:
            raise EvaluationError("project-relative input escapes the root") from None
    return target


def reference(kind: str, path: str, identifier: str, sha256: str) -> dict[str, Any]:
    return {"artifact_kind": kind, "path": path, "artifact_id": identifier, "content_sha256": sha256}


def child_environment(policy: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(policy.get("allowed_variables"), list) or len(policy["allowed_variables"]) > 64:
        raise EvaluationError("environment variable policy exceeds its bound")
    executable_paths = policy.get("executable_paths")
    if not isinstance(executable_paths, list) or len(executable_paths) > 32:
        raise EvaluationError("environment executable policy exceeds its bound")
    if any(
        not isinstance(item, str)
        or not item.startswith("/")
        or not item
        or len(item.encode("utf-8")) > 4096
        or "\0" in item
        for item in executable_paths
    ):
        raise EvaluationError("environment executable path is invalid")
    output: dict[str, str] = {}
    prior = ""
    total = 0
    for ordinal, item in enumerate(policy["allowed_variables"]):
        if not isinstance(item, dict) or set(item) != {"name", "non_secret_value", "source", "precedence"}:
            raise EvaluationError("environment variable record is invalid")
        name = item["name"]
        value = item["non_secret_value"]
        if (
            not isinstance(name, str)
            or not name
            or len(name.encode("utf-8")) > 256
            or "\0" in name
            or not isinstance(value, str)
            or len(value.encode("utf-8")) > 4096
            or "\0" in value
            or not isinstance(item["source"], str)
            or not item["source"]
            or item["precedence"] != ordinal
            or name <= prior
            or name in output
        ):
            raise EvaluationError("environment policy is not strictly ordered")
        total += len(name.encode("utf-8")) + len(value.encode("utf-8"))
        if total > 65_536:
            raise EvaluationError("environment policy exceeds its byte bound")
        output[name] = value
        prior = name
    return output


def validate_task_command(task: Mapping[str, Any], name: str, policy: Mapping[str, Any], project: Path) -> None:
    argv_name = "argv" if name == "cmd" else "snapshot_argv"
    argv = task.get(argv_name)
    command_value = task.get(name)
    if (
        not isinstance(argv, list)
        or not argv
        or len(argv) > 64
        or not isinstance(command_value, str)
        or argv[0] != command_value
    ):
        raise EvaluationError("task command vector is invalid")
    total = 0
    for item in argv:
        if not isinstance(item, str) or not item or "\0" in item or len(item.encode("utf-8")) > 4096:
            raise EvaluationError("task command argument is invalid")
        total += len(item.encode("utf-8")) + 1
    if total > 262_144:
        raise EvaluationError("task command vector exceeds its byte bound")
    executable = Path(command_value)
    if executable.is_absolute():
        if command_value not in policy["executable_paths"]:
            raise EvaluationError("task executable is not declared by the environment policy")
    else:
        relative_path(project, command_value)


def run_child(
    argv: list[str],
    cwd: Path,
    environment: Mapping[str, str],
    timeout_ns: int,
    cap: int,
    pass_fds: tuple[int, ...] = (),
) -> subprocess.CompletedProcess[bytes]:
    if timeout_ns <= 0:
        raise EvaluationError("child timeout is invalid")
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,
            pass_fds=pass_fds,
        )
    except OSError:
        raise ChildBoundaryError("PROCESS") from None
    captures = {"stdout": bytearray(), "stderr": bytearray()}
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + timeout_ns / 1_000_000_000
    cleanup_attempted = False
    try:
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            assert stream is not None
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ChildBoundaryError("TIMEOUT")
            events = selector.select(remaining)
            if not events:
                raise ChildBoundaryError("TIMEOUT")
            for key, _ in events:
                stream = key.fileobj
                target = captures[key.data]
                try:
                    chunk = os.read(stream.fileno(), min(65_536, cap + 1 - len(target)))
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue
                target.extend(chunk)
                if len(target) > cap:
                    raise ChildBoundaryError("OUTPUT")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ChildBoundaryError("TIMEOUT")
        process.wait(timeout=remaining)
        if process_group_exists(process.pid):
            cleanup_attempted = True
            if not cleanup_process_group(process):
                raise ChildBoundaryError("CLEANUP")
            raise ChildBoundaryError("PROCESS")
    except (OSError, subprocess.TimeoutExpired, ChildBoundaryError) as failure:
        if not cleanup_attempted:
            cleanup_attempted = True
            if not cleanup_process_group(process):
                raise ChildBoundaryError("CLEANUP") from None
        if isinstance(failure, ChildBoundaryError):
            raise failure
        if isinstance(failure, subprocess.TimeoutExpired):
            raise ChildBoundaryError("TIMEOUT") from None
        raise ChildBoundaryError("PROCESS") from None
    finally:
        selector.close()
        for stream in (process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
    return subprocess.CompletedProcess(argv, process.returncode, bytes(captures["stdout"]), bytes(captures["stderr"]))


def command(task: Mapping[str, Any], name: str, project: Path) -> list[str]:
    argv = list(task[name])
    if not argv or argv[0] != task["cmd" if name == "argv" else "snapshot_cmd"]:
        raise EvaluationError("task command and argv disagree")
    executable = Path(argv[0])
    if not executable.is_absolute():
        executable = project / executable
    argv[0] = str(executable)
    return argv


def render(variant: Mapping[str, Any], task_prompt: Mapping[str, Any], context: Mapping[str, Any]) -> tuple[str, str]:
    policy = variant["context_policy"]
    if any(policy[name] for name in ("include_patch_evaluation", "include_failure_memory", "include_diagnostics")):
        raise EvaluationError("fixed corpus requires disabled context sections")
    text = "".join((
        variant["base_prompt"]["text"], "\n\n--- repo prompt ---\n", variant["repo_prompt"]["text"],
        "\n\n--- task prompt ---\n", task_prompt["text"], "\n\n--- learned prompt append ---\n",
        variant["learned_prompt_append"] or "(none)", "\n\n--- patch evaluation context ---\n(omitted)",
        "\n\n--- failure memory context ---\n(omitted)",
        "\n\n--- current failure diagnostics ---\n(omitted)",
    ))
    return text, digest(text)


def write_exclusive(path: Path, raw: bytes, maximum: int) -> None:
    if len(raw) > maximum:
        raise EvaluationError("evaluation output exceeds its bound")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            offset += os.write(descriptor, raw[offset:])
    finally:
        os.close(descriptor)


def temporary_json(
    directory: Path,
    name: str,
    value: Mapping[str, Any],
    owned_paths: set[Path] | None = None,
) -> Path:
    path = directory / name
    write_exclusive(path, canonical(value), ARTIFACT_LIMIT)
    if owned_paths is not None:
        owned_paths.add(path)
    return path


def invoke_snapshot(
    task: Mapping[str, Any], request_path: Path, result_path: Path, project: Path,
    environment: Mapping[str, str], environment_probe: Mapping[str, Any],
) -> dict[str, Any]:
    argv = command(task, "snapshot_argv", project) + ["--snapshot-request", str(request_path), "--result", str(result_path)]
    try:
        completed = run_child(
            argv,
            project / task["cwd"],
            environment,
            max(nested_owner_timeout(task["timeout_ns"]), SNAPSHOT_HELPER_OUTER_TIMEOUT_NS),
            0,
        )
        if completed.returncode != 0 or completed.stdout or completed.stderr:
            raise EvaluationError("snapshot helper process failed")
        result = load_bound(result_path, "SNAPSHOT_RESULT", SNAPSHOT_LIMIT)
        result_path.unlink()
        if result.get("task_id") != task["task_id"] or result.get("status") not in ("MATCH", "MISMATCH", "ERROR"):
            raise EvaluationError("snapshot helper result is invalid")
        return result
    except ChildBoundaryError as failure:
        result_path.unlink(missing_ok=True)
        return bind({
            "schema_version": 1,
            "artifact_kind": "SNAPSHOT_RESULT",
            "task_id": task["task_id"],
            "status": "ERROR",
            "error_code": "CLEANUP" if failure.reason == "CLEANUP" else "INTERNAL",
            "error": "snapshot helper cleanup failed" if failure.reason == "CLEANUP" else "snapshot helper process failed",
            "environment_probe": environment_probe,
            "artifact_digests": [],
            "content_sha256": "",
        })
    except (EvaluationError, OSError, TypeError, KeyError):
        result_path.unlink(missing_ok=True)
        return bind({
            "schema_version": 1,
            "artifact_kind": "SNAPSHOT_RESULT",
            "task_id": task["task_id"],
            "status": "ERROR",
            "error_code": "INTERNAL",
            "error": "snapshot helper process failed",
            "environment_probe": environment_probe,
            "artifact_digests": [],
            "content_sha256": "",
        })


def invoke_adapter(
    task: Mapping[str, Any], adapter_request: Mapping[str, Any], request_path: Path,
    variant_path: Path, rendered_path: Path, measurement_path: Path,
    project: Path, environment: Mapping[str, str], provider_timeout_ns: int, sample: int, seed: int,
) -> dict[str, Any]:
    argv = command(task, "argv", project) + [
        "--prompt-variant", str(variant_path), "--rendered-prompt", str(rendered_path),
        "--sample-index", str(sample), "--paired-seed", str(seed),
        "--adapter-request", str(request_path), "--result", str(measurement_path),
    ]
    try:
        completed = run_child(
            argv,
            project / task["cwd"],
            environment,
            nested_owner_timeout(max(task["timeout_ns"], provider_timeout_ns)),
            0,
        )
    except ChildBoundaryError as failure:
        if failure.reason == "CLEANUP":
            raise AdapterFailure("CLEANUP_FAILED", "measurement adapter cleanup failed") from None
        if failure.reason == "TIMEOUT":
            raise AdapterFailure("ADAPTER_TIMEOUT", "measurement adapter timed out") from None
        if failure.reason == "OUTPUT":
            raise AdapterFailure("ADAPTER_PROCESS_OUTPUT", "measurement adapter produced process output") from None
        raise AdapterFailure("ADAPTER_RESULT", "measurement adapter process failed") from None
    if completed.returncode != 0 or completed.stdout or completed.stderr:
        raise AdapterFailure("ADAPTER_RESULT", "measurement adapter process failed")
    try:
        measurement = load_bound(measurement_path, "TASK_MEASUREMENT", MEASUREMENT_LIMIT)
    except EvaluationError:
        raise AdapterFailure("ADAPTER_RESULT", "measurement adapter result is invalid") from None
    measurement_path.unlink()
    return measurement


def write_prepared_pair(
    prepared_result: Path,
    prepared_evidence: Path,
    result: dict[str, Any],
    trust: Mapping[str, Any],
    expected_inputs: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    bind(result)
    if not canonical_fits(result, RESULT_LIMIT):
        compact_oversized_result(result, expected_inputs)
        bind(result)
    evidence = bind({
        "schema_version": 1,
        "artifact_kind": "PROMPT_EVALUATION_EVIDENCE",
        "evaluation_id": result["evaluation_id"],
        "evaluation_result_sha256": result["content_sha256"],
        "trust": trust,
        "expected_inputs": expected_inputs,
        "content_sha256": "",
    })
    write_exclusive(prepared_result, canonical(result), RESULT_LIMIT)
    try:
        write_exclusive(prepared_evidence, canonical(evidence), EVIDENCE_LIMIT)
    except BaseException:
        prepared_result.unlink(missing_ok=True)
        raise
    return result, evidence


def canonical_fits(value: Any, maximum: int) -> bool:
    """Check the persisted JSON bound without first allocating the whole encoding."""
    total = 0
    for chunk in canonical_chunks(value):
        total += len(chunk)
        if total > maximum:
            return False
    return True


def compact_oversized_result(result: dict[str, Any], expected_inputs: list[dict[str, Any]]) -> None:
    """Replace an oversized result graph with its bounded trace envelope in place."""
    trace_digest = hashlib.sha256()
    trace_record_count = 0

    def include(record: Mapping[str, Any]) -> None:
        nonlocal trace_record_count
        trace_record_count += 1
        trace_digest.update(
            f'{trace_record_count} {record.get("artifact_kind", "")} {record.get("content_sha256", "")}\n'.encode(
                "utf-8"
            )
        )

    for name in ("workspace_preflight_request", "workspace_preflight"):
        record = result.get(name)
        if isinstance(record, Mapping):
            include(record)
    for name in ("snapshot_requests", "snapshot_results", "input_snapshots", "snapshot_attestations"):
        value = result.get(name)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping):
                    include(item)
    attempted_invocations = len(result.get("snapshot_attestations", []))
    overflow = bind({
        "schema_version": 1,
        "artifact_kind": "PROMPT_TRACE_OVERFLOW",
        "attempted_invocation_count": attempted_invocations,
        "trace_record_count": trace_record_count,
        "trace_digest_sha256": trace_digest.hexdigest(),
        "content_sha256": "",
    })
    compact = {
        "schema_version": 1,
        "artifact_kind": "PROMPT_EVALUATION_RESULT",
        "evaluation_id": result["evaluation_id"],
        "status": "ERROR",
        "error_code": "RESULT_TOO_LARGE",
        "error": "canonical evaluation result exceeds 268435456 bytes",
        "experiment": None,
        "experiment_artifact": None,
        "parent_activation": None,
        "parent_activation_artifact": None,
        "scope": result["scope"],
        "parent_variant": None,
        "candidate_variant": None,
        "corpus_source": None,
        "corpus": None,
        "tasks": [],
        "acceptance_policy_source": None,
        "acceptance_policy": None,
        "generation_policy_source": None,
        "generation_policy": None,
        "provider_control_source": None,
        "provider_control": None,
        "workspace_preflight_source": None,
        "workspace_preflight_request": None,
        "workspace_preflight": None,
        "environment": None,
        "snapshot_requests": [],
        "snapshot_results": [],
        "input_snapshots": [],
        "snapshot_attestations": [],
        "trace_failure": overflow,
        "sample_count": result["sample_count"],
        "gate_eligible": False,
        "rows": [],
        "task_aggregates": [],
        "corpus_aggregate": None,
        "serious_regression_reasons": [],
        "content_sha256": "",
    }
    for name in (
        "tasks",
        "snapshot_requests",
        "snapshot_results",
        "input_snapshots",
        "snapshot_attestations",
        "rows",
        "task_aggregates",
        "serious_regression_reasons",
    ):
        value = result.get(name)
        if isinstance(value, list):
            value.clear()
    expected_inputs.clear()
    result.clear()
    result.update(compact)


def write_invalid_result_only(
    prepared_result: Path,
    evaluation_id: str,
    sample_count: Any,
    error_code: str,
    error: str,
) -> None:
    result = {
        "schema_version": 1,
        "artifact_kind": "PROMPT_EVALUATION_RESULT",
        "evaluation_id": evaluation_id,
        "status": "INVALID_INPUT",
        "error_code": error_code,
        "error": error,
        "experiment": None,
        "experiment_artifact": None,
        "parent_activation": None,
        "parent_activation_artifact": None,
        "scope": None,
        "parent_variant": None,
        "candidate_variant": None,
        "corpus_source": None,
        "corpus": None,
        "tasks": [],
        "acceptance_policy_source": None,
        "acceptance_policy": None,
        "generation_policy_source": None,
        "generation_policy": None,
        "provider_control_source": None,
        "provider_control": None,
        "workspace_preflight_source": None,
        "workspace_preflight_request": None,
        "workspace_preflight": None,
        "environment": None,
        "snapshot_requests": [],
        "snapshot_results": [],
        "input_snapshots": [],
        "snapshot_attestations": [],
        "trace_failure": None,
        "sample_count": sample_count if isinstance(sample_count, int) and not isinstance(sample_count, bool) else 0,
        "gate_eligible": False,
        "rows": [],
        "task_aggregates": [],
        "corpus_aggregate": None,
        "serious_regression_reasons": [],
        "content_sha256": "",
    }
    bind(result)
    write_exclusive(prepared_result, canonical(result), RESULT_LIMIT)


def evaluation_result_record(
    context: Mapping[str, Any],
    status: str,
    error_code: str,
    error: str,
    preflight: Mapping[str, Any],
    environment: Mapping[str, Any] | None,
    snapshot_requests: list[dict[str, Any]],
    snapshot_results: list[dict[str, Any]],
    input_snapshots: list[dict[str, Any]],
    attestations: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    task_aggregates: list[dict[str, Any]] | None = None,
    corpus_aggregate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = context["request"]
    experiment = context["experiment"]
    parent = context["parent"]
    corpus = context["corpus"]
    acceptance = context["acceptance"]
    first_task = context["first_task"]
    generation = context["generation"]
    control = context["control"]
    return {
        "schema_version": 1,
        "artifact_kind": "PROMPT_EVALUATION_RESULT",
        "evaluation_id": request["evaluation_id"],
        "status": status,
        "error_code": error_code,
        "error": error,
        "experiment": reference(
            "PROMPT_EXPERIMENT_RESULT", request["experiment_path"],
            experiment["experiment_id"], experiment["content_sha256"],
        ),
        "experiment_artifact": experiment,
        "parent_activation": reference(
            "PROMPT_ACTIVATION_RESULT", request["parent_activation_path"],
            parent["decision_id"], parent["content_sha256"],
        ),
        "parent_activation_artifact": parent,
        "scope": context["scope"],
        "parent_variant": context["parent_variant"],
        "candidate_variant": context["candidate"],
        "corpus_source": reference(
            "PROMPT_EVALUATION_CORPUS", request["corpus_path"],
            corpus["corpus_id"], corpus["content_sha256"],
        ),
        "corpus": corpus,
        "tasks": context["tasks"],
        "acceptance_policy_source": reference(
            "PROMPT_ACCEPTANCE_POLICY", request["acceptance_policy_path"],
            acceptance["policy_id"], acceptance["content_sha256"],
        ),
        "acceptance_policy": acceptance,
        "generation_policy_source": reference(
            "GENERATION_POLICY", first_task["generation_policy_path"],
            generation["generation_policy_id"], generation["content_sha256"],
        ),
        "generation_policy": generation,
        "provider_control_source": reference(
            "EVALUATION_PROVIDER_CONTROL", first_task["provider_control_path"],
            control["provider_control_id"], control["content_sha256"],
        ),
        "provider_control": control,
        "workspace_preflight_source": reference(
            "WORKSPACE_PREFLIGHT_RESULT", request["workspace_preflight_path"],
            request["evaluation_id"], preflight["content_sha256"],
        ),
        "workspace_preflight_request": context["preflight_request"],
        "workspace_preflight": preflight,
        "environment": environment,
        "snapshot_requests": snapshot_requests,
        "snapshot_results": snapshot_results,
        "input_snapshots": input_snapshots,
        "snapshot_attestations": attestations,
        "trace_failure": None,
        "sample_count": request["sample_count"],
        "gate_eligible": False,
        "rows": rows,
        "task_aggregates": [] if task_aggregates is None else task_aggregates,
        "corpus_aggregate": corpus_aggregate,
        "serious_regression_reasons": [],
        "content_sha256": "",
    }


def build_environment(
    probe: Mapping[str, Any], request: Mapping[str, Any], task: Mapping[str, Any],
    source_policy: Mapping[str, Any], environment_policy: Mapping[str, Any],
) -> dict[str, Any]:
    core = {
        "schema_version": 1, "artifact_kind": "ENVIRONMENT_IDENTITY_CORE",
        "os": probe["os"], "os_release": probe["os_release"], "architecture": probe["architecture"],
        "cpu": probe["cpu"], "logical_cpu_count": probe["logical_cpu_count"], "gpu": probe["gpu"],
        "align_llm_commit": request["verifier_align_llm_commit"],
        "align_revision": request["verifier_align_revision"],
        "measurement_adapter_runtime": task["measurement_adapter_runtime"],
        "snapshot_helper_runtime": task["snapshot_helper_runtime"],
        "source_verifier_runtime": source_policy["helper_runtime"],
        "source_verifier_policy_sha256": source_policy["content_sha256"],
        "environment_policy_sha256": environment_policy["content_sha256"],
    }
    return bind({
        "schema_version": 1, "artifact_kind": "ENVIRONMENT_IDENTITY", "core": core,
        "environment_id": hashlib.sha256(canonical_digest_bytes(core)).hexdigest(), "content_sha256": "",
    })


def valid_source_observation(value: Mapping[str, Any]) -> bool:
    if value.get("status") not in ("COMPLETE", "UNAVAILABLE"):
        return False
    fields = (
        ("align_llm_reachability", "align_llm_observed_head"),
        ("align_reachability", "align_observed_revision"),
        ("corpus_reachability", "corpus_observed_source_sha256"),
    )
    for reachability_name, observed_name in fields:
        reachability = value.get(reachability_name)
        observed = value.get(observed_name)
        if reachability not in ("VERIFIED", "UNVERIFIED"):
            return False
        if observed is not None and not valid_hex(observed, (40, 64)):
            return False
        if reachability == "VERIFIED" and observed is None:
            return False
    if value["status"] == "COMPLETE":
        return value.get("error_code") == "NONE" and value.get("error") == ""
    return (
        isinstance(value.get("error_code"), str)
        and bool(value["error_code"])
        and isinstance(value.get("error"), str)
        and 0 < len(value["error"].encode("utf-8")) <= 4096
    )


def unavailable_trust(request: Mapping[str, Any]) -> dict[str, Any]:
    return bind({
        "schema_version": 1, "artifact_kind": "PROMPT_VERIFIER_TRUST",
        "expected_align_llm_commit": request["verifier_align_llm_commit"],
        "expected_align_revision": request["verifier_align_revision"],
        "expected_corpus_source_kind": request["verifier_corpus_source_kind"],
        "expected_corpus_source_repository_id": request["verifier_corpus_source_repository_id"],
        "expected_corpus_source_sha256": request["verifier_corpus_source_sha256"],
        "align_llm_reachability": "UNVERIFIED", "align_llm_observed_head": None,
        "align_reachability": "UNVERIFIED", "align_observed_revision": None,
        "corpus_reachability": "UNVERIFIED", "corpus_observed_source_sha256": None,
        "content_sha256": "",
    })


def validate_source_boundary(
    request: Mapping[str, Any], policy: Mapping[str, Any], project: Path
) -> None:
    if (
        not valid_ascii_identifier(policy.get("policy_id"))
        or not valid_hex(policy.get("helper_sha256"))
        or not valid_hex(policy.get("interpreter_sha256"))
        or not valid_hex(policy.get("git_executable_sha256"))
        or not isinstance(policy.get("helper_runtime"), str)
        or len(policy["helper_runtime"].encode("utf-8")) > 256
    ):
        raise EvaluationError("source verifier policy identity is invalid")
    helper = relative_path(project, policy["helper_path"])
    python = Path(request["verifier_python_executable_path"])
    git = Path(request["verifier_git_executable_path"])
    if not python.is_absolute():
        raise EvaluationError("source verifier Python path is invalid")
    if not git.is_absolute():
        raise EvaluationError("source verifier Git path is invalid")
    expected_runtime = f'CPYTHON:{policy["interpreter_sha256"]}:{policy["helper_sha256"]}'
    if policy.get("helper_runtime") != expected_runtime:
        raise EvaluationError("source verifier runtime identity does not match")
    declared = (
        (helper, ARTIFACT_LIMIT, policy["helper_sha256"], "helper"),
        (python, RESULT_LIMIT, policy["interpreter_sha256"], "interpreter"),
        (git, RESULT_LIMIT, policy["git_executable_sha256"], "Git"),
    )
    for path, maximum, expected, label in declared:
        carrier = RetainedRegularFile(path, maximum)
        try:
            if carrier.sha256() != expected:
                raise EvaluationError(f"source verifier {label} digest does not match")
        finally:
            carrier.close()


def source_trust(
    request: Mapping[str, Any], policy: Mapping[str, Any], project: Path, environment: Mapping[str, str]
) -> dict[str, Any]:
    helper = relative_path(project, policy["helper_path"])
    python = Path(request["verifier_python_executable_path"])
    if not python.is_absolute():
        raise EvaluationError("source verifier Python path is invalid")
    expected_runtime = f'CPYTHON:{policy["interpreter_sha256"]}:{policy["helper_sha256"]}'
    if policy.get("helper_runtime") != expected_runtime:
        raise EvaluationError("source verifier runtime identity does not match")
    git = Path(request["verifier_git_executable_path"])
    if not git.is_absolute():
        raise EvaluationError("source verifier Git path is invalid")
    carriers: list[RetainedRegularFile] = []
    try:
        helper_carrier = RetainedRegularFile(helper, ARTIFACT_LIMIT)
        carriers.append(helper_carrier)
        python_carrier = RetainedRegularFile(python, RESULT_LIMIT)
        carriers.append(python_carrier)
        git_carrier = RetainedRegularFile(git, RESULT_LIMIT)
        carriers.append(git_carrier)
        if helper_carrier.sha256() != policy["helper_sha256"]:
            raise EvaluationError("source verifier helper digest does not match")
        if python_carrier.sha256() != policy["interpreter_sha256"]:
            raise EvaluationError("source verifier interpreter digest does not match")
        if git_carrier.sha256() != policy["git_executable_sha256"]:
            raise EvaluationError("source verifier Git digest does not match")
        verifier_request = bind({
            "schema_version": 1, "artifact_kind": "PROMPT_SOURCE_VERIFIER_REQUEST", "mode": "EVALUATION",
            "align_llm_repository_path": request["verifier_align_llm_repository_path"],
            "expected_align_llm_commit": request["verifier_align_llm_commit"], "tested_align_llm_head": None,
            "align_repository_path": request["verifier_align_repository_path"],
            "expected_align_revision": request["verifier_align_revision"],
            "corpus_source_path": request["verifier_corpus_source_path"],
            "corpus_source_kind": request["verifier_corpus_source_kind"],
            "corpus_file_set_manifest_path": request.get("verifier_corpus_file_set_manifest_path"),
            "expected_corpus_source_repository_id": request["verifier_corpus_source_repository_id"],
            "expected_corpus_source_sha256": request["verifier_corpus_source_sha256"],
            "git_executable_path": git_carrier.process_path(),
            "git_executable_sha256": policy["git_executable_sha256"], "content_sha256": "",
        })
        with tempfile.TemporaryDirectory(prefix="prompt-source-boundary-") as directory:
            root = Path(directory)
            request_path = temporary_json(root, "request.json", verifier_request)
            result_path = root / "result.json"
            try:
                completed = run_child(
                    [
                        python_carrier.process_path(),
                        helper_carrier.process_path(),
                        "--source-verifier-request",
                        str(request_path),
                        "--result",
                        str(result_path),
                    ],
                    project,
                    environment,
                    SOURCE_VERIFIER_OUTER_TIMEOUT_NS,
                    0,
                    (helper_carrier.descriptor, python_carrier.descriptor, git_carrier.descriptor),
                )
                if completed.returncode == 3:
                    raise AdapterFailure("CLEANUP_FAILED", "source verifier cleanup failed")
                if completed.returncode != 0 or completed.stdout or completed.stderr:
                    raise EvaluationError("source verifier process failed")
                observed = load_bound(result_path, "PROMPT_SOURCE_VERIFIER_RESULT", MEASUREMENT_LIMIT)
                if not valid_source_observation(observed):
                    raise EvaluationError("source verifier result is malformed")
                if (
                    observed["align_llm_reachability"] == "VERIFIED"
                    and observed["align_llm_observed_head"] != request["verifier_align_llm_commit"]
                ) or (
                    observed["align_reachability"] == "VERIFIED"
                    and observed["align_observed_revision"] != request["verifier_align_revision"]
                ) or (
                    observed["corpus_reachability"] == "VERIFIED"
                    and observed["corpus_observed_source_sha256"] != request["verifier_corpus_source_sha256"]
                ):
                    raise EvaluationError("source verifier result identity disagrees")
            except ChildBoundaryError as failure:
                if failure.reason == "CLEANUP":
                    raise AdapterFailure("CLEANUP_FAILED", "source verifier cleanup failed") from None
                observed = unavailable_trust(request)
            except AdapterFailure:
                raise
            except EvaluationError:
                observed = {
                    "status": "UNAVAILABLE",
                    "align_llm_reachability": "UNVERIFIED",
                    "align_llm_observed_head": None,
                    "align_reachability": "UNVERIFIED",
                    "align_observed_revision": None,
                    "corpus_reachability": "UNVERIFIED",
                    "corpus_observed_source_sha256": None,
                }
        helper_carrier.verify_unchanged(policy["helper_sha256"])
        python_carrier.verify_unchanged(policy["interpreter_sha256"])
        git_carrier.verify_unchanged(policy["git_executable_sha256"])
        return bind({
            "schema_version": 1, "artifact_kind": "PROMPT_VERIFIER_TRUST",
            "expected_align_llm_commit": request["verifier_align_llm_commit"],
            "expected_align_revision": request["verifier_align_revision"],
            "expected_corpus_source_kind": request["verifier_corpus_source_kind"],
            "expected_corpus_source_repository_id": request["verifier_corpus_source_repository_id"],
            "expected_corpus_source_sha256": request["verifier_corpus_source_sha256"],
            "align_llm_reachability": observed["align_llm_reachability"],
            "align_llm_observed_head": observed["align_llm_observed_head"],
            "align_reachability": observed["align_reachability"],
            "align_observed_revision": observed["align_observed_revision"],
            "corpus_reachability": observed["corpus_reachability"],
            "corpus_observed_source_sha256": observed["corpus_observed_source_sha256"],
            "content_sha256": "",
        })
    finally:
        for carrier in reversed(carriers):
            carrier.close()


def validation_error_code(error: BaseException) -> str:
    detail = str(error).lower()
    if "unavailable" in detail or "not found" in detail:
        return "INPUT_NOT_FOUND"
    if "type" in detail or "regular" in detail:
        return "INPUT_TYPE"
    if "digest" in detail:
        return "INVALID_DIGEST"
    if "scope" in detail:
        return "SCOPE_MISMATCH"
    if "workspace" in detail and "empty" in detail:
        return "WORKSPACE_NOT_EMPTY"
    if "path" in detail or "directory" in detail or "root" in detail or "working" in detail:
        return "INVALID_PATH"
    if "count" in detail or "bound" in detail or "timeout" in detail:
        return "INVALID_BOUNDS"
    if "identity" in detail or "disagree" in detail or "reference" in detail:
        return "INVALID_REFERENCE"
    return "INVALID_SCHEMA"


def validated_evaluation_inputs(request: Mapping[str, Any], project: Path) -> dict[str, Any]:
    if request["sample_count"] < 2 or request["sample_count"] > 16:
        raise EvaluationError("sample count is invalid")

    source_policy = load_bound(relative_path(project, request["verifier_source_policy_path"]), "PROMPT_SOURCE_VERIFIER_POLICY")
    if tuple(source_policy) != SOURCE_POLICY_FIELDS:
        raise EvaluationError("source verifier policy fields are invalid")
    if source_policy["content_sha256"] != request["verifier_source_policy_sha256"]:
        raise EvaluationError("source verifier policy identity disagrees")
    validate_source_boundary(request, source_policy, project)
    experiment = load_bound(relative_path(project, request["experiment_path"]), "PROMPT_EXPERIMENT_RESULT")
    parent = load_bound(relative_path(project, request["parent_activation_path"]), "PROMPT_ACTIVATION_RESULT")
    corpus = load_bound(relative_path(project, request["corpus_path"]), "PROMPT_EVALUATION_CORPUS")
    acceptance = load_bound(relative_path(project, request["acceptance_policy_path"]), "PROMPT_ACCEPTANCE_POLICY")
    preflight_request = load_bound(relative_path(project, request["workspace_preflight_path"]), "WORKSPACE_PREFLIGHT_REQUEST")
    tasks = [load_bound(relative_path(project, item), "PROMPT_EVALUATION_TASK") for item in corpus["task_files"]]
    if len(tasks) < 1 or len(tasks) > 64:
        raise EvaluationError("corpus task count is invalid")
    first_task = tasks[0]
    generation = load_bound(relative_path(project, first_task["generation_policy_path"]), "GENERATION_POLICY")
    control = load_bound(relative_path(project, first_task["provider_control_path"]), "EVALUATION_PROVIDER_CONTROL")
    environment_policy = load_bound(relative_path(project, first_task["environment_policy_path"]), "ENVIRONMENT_POLICY")
    environment_values = child_environment(environment_policy)
    if (
        not isinstance(control.get("timeout_ns"), int)
        or isinstance(control["timeout_ns"], bool)
        or control["timeout_ns"] <= 0
        or control["timeout_ns"] > 7_200_000_000_000
    ):
        raise EvaluationError("provider control timeout is invalid")
    if control["provider_kind"] != "FIXTURE" or control["api_key_env"] is not None:
        raise EvaluationError("fixed evaluator requires a credential-free fixture provider")
    task_inputs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    task_ids: set[str] = set()
    for task in tasks:
        if (
            task["task_id"] in task_ids
            or task["measurement_adapter_runtime"] != first_task["measurement_adapter_runtime"]
            or task["snapshot_helper_runtime"] != first_task["snapshot_helper_runtime"]
        ):
            raise EvaluationError("task identity is invalid or duplicated")
        task_ids.add(task["task_id"])
        if (
            not isinstance(task.get("timeout_ns"), int)
            or isinstance(task["timeout_ns"], bool)
            or task["timeout_ns"] <= 0
            or task["timeout_ns"] > 7_200_000_000_000
        ):
            raise EvaluationError("task timeout is invalid")
        cwd = relative_path(project, task["cwd"])
        if not cwd.is_dir():
            raise EvaluationError("task working directory is invalid")
        validate_task_command(task, "cmd", environment_policy, project)
        validate_task_command(task, "snapshot_cmd", environment_policy, project)
        task_generation = load_bound(relative_path(project, task["generation_policy_path"]), "GENERATION_POLICY")
        task_control = load_bound(relative_path(project, task["provider_control_path"]), "EVALUATION_PROVIDER_CONTROL")
        task_environment = load_bound(relative_path(project, task["environment_policy_path"]), "ENVIRONMENT_POLICY")
        if task_generation != generation or task_control != control or task_environment != environment_policy:
            raise EvaluationError("task policies disagree")
        task_prompt = load_bound(relative_path(project, task["task_prompt_path"]), "TASK_PROMPT")
        context = load_bound(relative_path(project, task["context_sources_path"]), "CONTEXT_SOURCES")
        if context["task_id"] != task["task_id"]:
            raise EvaluationError("task context identity disagrees")
        task_inputs.append((task_prompt, context))
    scope = experiment["scope"]
    candidate = experiment["candidate_variant"]
    parent_variant = parent["activation"]["effective_variant"]
    if (
        scope != parent["activation"]["scope"] or scope["corpus_revision"] != corpus["corpus_revision"]
        or scope["generation_policy_sha256"] != generation["content_sha256"]
        or scope["acceptance_policy_sha256"] != acceptance["content_sha256"]
        or request["verifier_align_revision"] != scope["align_revision"]
        or request["verifier_corpus_source_kind"] != scope["corpus_revision"]["source_kind"]
        or request["verifier_corpus_source_repository_id"] != scope["corpus_revision"]["source_repository_id"]
        or request["verifier_corpus_source_sha256"] != scope["corpus_revision"]["source_sha256"]
        or any(task["repo_id"] != scope["repo_id"] for task in tasks)
    ):
        raise EvaluationError("evaluation scope identities disagree")
    workspace = physical_directory(Path(request["workspace_path"]))
    try:
        workspace.relative_to(project)
    except ValueError:
        raise EvaluationError("workspace escapes the project") from None
    return {
        "workspace": workspace, "experiment": experiment, "parent": parent, "corpus": corpus,
        "acceptance": acceptance, "preflight_request": preflight_request, "source_policy": source_policy,
        "tasks": tasks, "first_task": first_task, "generation": generation, "control": control,
        "environment_policy": environment_policy, "environment_values": environment_values,
        "task_inputs": task_inputs, "scope": scope, "candidate": candidate,
        "parent_variant": parent_variant,
    }


def evaluate(
    request_path: Path,
    prepared_result: Path,
    prepared_evidence: Path,
    final_result_relative: str,
    final_evidence_relative: str,
    owned_paths: set[Path],
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = load_json(request_path, REQUEST_LIMIT)
    request_fields = tuple(request)
    if (
        request_fields not in (EVALUATE_REQUEST_FIELDS, EVALUATE_REQUEST_FIELDS_OMITTED)
        or request.get("schema_version") != 1
        or request.get("artifact_kind") != "PROMPT_EVALUATE_REQUEST"
    ):
        raise EvaluationError("evaluate request header is invalid")
    project = physical_directory(Path(request["project_root"]))
    final_result = relative_path(project, final_result_relative, must_exist=False)
    if final_result.exists() or final_result.is_symlink():
        raise EvaluationError("evaluation result path is occupied")
    try:
        final_evidence = relative_path(project, final_evidence_relative, must_exist=False)
        evidence_valid = (
            final_evidence_relative == request["evaluation_evidence_path"]
            and final_result != final_evidence
            and not final_evidence.exists()
            and not final_evidence.is_symlink()
        )
    except (EvaluationError, KeyError, TypeError):
        evidence_valid = False
    if not evidence_valid:
        write_invalid_result_only(
            prepared_result,
            request.get("evaluation_id", ""),
            request.get("sample_count", 0),
            "INVALID_PATH",
            "evaluation evidence path is invalid",
        )
        raise ResultOnlyInvalid("evaluation evidence path is invalid")
    try:
        validate_request_source_declaration(request)
        inputs = validated_evaluation_inputs(request, project)
    except (EvaluationError, OSError, TypeError, ValueError, KeyError, IndexError) as failure:
        code = validation_error_code(failure)
        detail = str(failure)[:4096] or "evaluation input is invalid"
        write_invalid_result_only(
            prepared_result, request.get("evaluation_id", ""), request.get("sample_count", 0), code, detail,
        )
        raise ResultOnlyInvalid(detail) from None
    workspace = inputs["workspace"]
    experiment = inputs["experiment"]
    parent = inputs["parent"]
    corpus = inputs["corpus"]
    acceptance = inputs["acceptance"]
    preflight_request = inputs["preflight_request"]
    source_policy = inputs["source_policy"]
    tasks = inputs["tasks"]
    first_task = inputs["first_task"]
    generation = inputs["generation"]
    control = inputs["control"]
    environment_policy = inputs["environment_policy"]
    environment_values = inputs["environment_values"]
    task_inputs = inputs["task_inputs"]
    scope = inputs["scope"]
    candidate = inputs["candidate"]
    parent_variant = inputs["parent_variant"]
    trust = unavailable_trust(request)

    result_context = {
        "request": request,
        "experiment": experiment,
        "parent": parent,
        "scope": scope,
        "parent_variant": parent_variant,
        "candidate": candidate,
        "corpus": corpus,
        "tasks": tasks,
        "acceptance": acceptance,
        "first_task": first_task,
        "generation": generation,
        "control": control,
        "preflight_request": preflight_request,
    }

    preflight_path = relative_path(project, request["workspace_preflight_path"])
    snapshot_command = command(first_task, "snapshot_argv", project)
    try:
        completed = run_child(
            snapshot_command + ["--workspace-preflight-request", str(preflight_path)],
            project / first_task["cwd"],
            environment_values,
            max(nested_owner_timeout(first_task["timeout_ns"]), SNAPSHOT_HELPER_OUTER_TIMEOUT_NS),
            65_536,
        )
        if completed.returncode != 0 or completed.stderr:
            raise EvaluationError("workspace preflight process failed")
        preflight = json.loads(completed.stdout.decode("utf-8", "strict"))
        normalized_preflight = dict(preflight)
        claimed = normalized_preflight.get("content_sha256")
        normalized_preflight["content_sha256"] = ""
        if not valid_hex(claimed) or hashlib.sha256(canonical_digest_bytes(normalized_preflight)).hexdigest() != claimed:
            raise EvaluationError("workspace preflight result is malformed")
    except ChildBoundaryError as failure:
        preflight = bind({
            "schema_version": 1,
            "artifact_kind": "WORKSPACE_PREFLIGHT_RESULT",
            "evaluation_id": request["evaluation_id"],
            "status": "ERROR",
            "error_code": "CLEANUP" if failure.reason == "CLEANUP" else "ENVIRONMENT",
            "error": "workspace preflight helper cleanup failed" if failure.reason == "CLEANUP" else "workspace preflight helper failed",
            "physical_project_root": "",
            "physical_workspace_path": "",
            "environment_probe": None,
            "content_sha256": "",
        })
    except (EvaluationError, UnicodeError, json.JSONDecodeError, TypeError, KeyError):
        preflight = bind({
            "schema_version": 1,
            "artifact_kind": "WORKSPACE_PREFLIGHT_RESULT",
            "evaluation_id": request["evaluation_id"],
            "status": "ERROR",
            "error_code": "ENVIRONMENT",
            "error": "workspace preflight helper failed",
            "physical_project_root": "",
            "physical_workspace_path": "",
            "environment_probe": None,
            "content_sha256": "",
        })
    if preflight.get("status") != "SAFE":
        result_code = (
            "WORKSPACE_UNSAFE" if preflight.get("status") == "UNSAFE"
            else "CLEANUP_FAILED" if preflight.get("error_code") == "CLEANUP"
            else "SNAPSHOT_ERROR"
        )
        detail = preflight.get("error", "workspace preflight failed")
        result = evaluation_result_record(
            result_context, "ERROR", result_code, detail, preflight, None, [], [], [], [], [],
        )
        return write_prepared_pair(prepared_result, prepared_evidence, result, trust, [])
    try:
        trust = source_trust(request, source_policy, project, environment_values)
    except AdapterFailure as failure:
        result = evaluation_result_record(
            result_context, "ERROR", failure.code, failure.detail, preflight, None, [], [], [], [], [],
        )
        return write_prepared_pair(prepared_result, prepared_evidence, result, trust, [])
    except EvaluationError:
        result = evaluation_result_record(
            result_context, "ERROR", "INPUT_DRIFT", "source verifier executable identity drifted",
            preflight, None, [], [], [], [], [],
        )
        return write_prepared_pair(prepared_result, prepared_evidence, result, trust, [])
    seed_base = generation.get("seed_base")
    maximum_offset = request["sample_count"] - 1
    if (
        not isinstance(seed_base, int)
        or isinstance(seed_base, bool)
        or seed_base < -(2**63)
        or seed_base > 2**63 - 1
        or seed_base > (2**63 - 1) - maximum_offset
    ):
        result = evaluation_result_record(
            result_context,
            "ERROR",
            "ARITHMETIC",
            "paired seed arithmetic overflows signed i64",
            preflight,
            None,
            [],
            [],
            [],
            [],
            [],
        )
        return write_prepared_pair(prepared_result, prepared_evidence, result, trust, [])
    environment = build_environment(preflight["environment_probe"], request, first_task, source_policy, environment_policy)

    rows: list[dict[str, Any]] = []
    expected_inputs: list[dict[str, Any]] = []
    snapshot_requests: list[dict[str, Any]] = []
    snapshot_results: list[dict[str, Any]] = []
    input_snapshots: list[dict[str, Any]] = []
    attestations: list[dict[str, Any]] = []

    def evaluation_result(status: str, error_code: str, error: str) -> dict[str, Any]:
        return evaluation_result_record(
            result_context, status, error_code, error, preflight, environment,
            snapshot_requests, snapshot_results, input_snapshots, attestations, rows,
        )

    for task_ordinal, task in enumerate(tasks):
        task_prompt, context = task_inputs[task_ordinal]
        entry_names: list[str] = []
        for sample in range(1, request["sample_count"] + 1):
            for variant_name in ("PARENT", "CANDIDATE"):
                prefix = f"t{task_ordinal + 1}-s{sample}-{variant_name.lower()}"
                entry_names.extend((f"{prefix}-variant.json", f"{prefix}-rendered.json", f"{prefix}-request.json", f"{prefix}-measurement.json"))
        entry_names.append(f"t{task_ordinal + 1}-snapshot-result.json")
        with tempfile.TemporaryDirectory(prefix="prompt-snapshot-request-") as request_directory:
            schedule = []
            for sample in range(1, request["sample_count"] + 1):
                schedule.extend(("PARENT", "CANDIDATE") if sample % 2 else ("CANDIDATE", "PARENT"))
                for variant_name in schedule[-2:]:
                    variant = parent_variant if variant_name == "PARENT" else candidate
                    prefix = f"t{task_ordinal + 1}-s{sample}-{variant_name.lower()}"
                    variant_path = temporary_json(workspace, f"{prefix}-variant.json", variant, owned_paths)
                    rendered_text, rendered_text_sha = render(variant, task_prompt, context)
                    rendered = bind({
                        "schema_version": 1, "artifact_kind": "RENDERED_PROMPT", "task_id": task["task_id"],
                        "variant_id": variant["variant_id"], "variant_sha256": variant["content_sha256"],
                        "task_prompt_sha256": task_prompt["content_sha256"],
                        "context_sources_sha256": context["content_sha256"], "text": rendered_text,
                        "content_sha256": "",
                    })
                    if rendered_text_sha != digest(rendered["text"]):
                        raise EvaluationError("rendered prompt digest changed")
                    rendered_path = temporary_json(workspace, f"{prefix}-rendered.json", rendered, owned_paths)
                    measurement_path = workspace / f"{prefix}-measurement.json"
                    owned_paths.add(measurement_path)
                    adapter_request = bind({
                        "schema_version": 1, "artifact_kind": "TASK_ADAPTER_REQUEST",
                        "evaluation_id": request["evaluation_id"], "task_id": task["task_id"], "sample_index": sample,
                        "variant": variant_name, "variant_path": str(variant_path), "variant_sha256": variant["content_sha256"],
                        "rendered_prompt_path": str(rendered_path), "rendered_prompt_sha256": rendered["content_sha256"],
                        "generation_policy_path": str(relative_path(project, task["generation_policy_path"])),
                        "generation_policy_sha256": generation["content_sha256"],
                        "provider_control_path": str(relative_path(project, task["provider_control_path"])),
                        "provider_control_sha256": control["content_sha256"], "workspace_path": str(workspace),
                        "result_path": str(measurement_path), "paired_seed": generation["seed_base"] + sample - 1,
                        "credential_env_name": None, "environment_policy_sha256": environment_policy["content_sha256"],
                        "content_sha256": "",
                    })
                    adapter_request_path = temporary_json(
                        workspace, f"{prefix}-request.json", adapter_request, owned_paths
                    )
                    snapshot_request = bind({
                        "schema_version": 1,
                        "artifact_kind": "SNAPSHOT_REQUEST",
                        "task_id": task["task_id"],
                        "project_root": str(project),
                        "repo_path": task["repo_path"],
                        "repo_revision": task["repo_revision"],
                        "require_clean_repo": task["require_clean_repo"],
                        "static_expectations": task["artifacts"],
                        "additional_files": [
                            str(variant_path.relative_to(project)),
                            str(rendered_path.relative_to(project)),
                            str(adapter_request_path.relative_to(project)),
                        ],
                        "workspace_path": str(workspace),
                        "allowed_workspace_entries": sorted(entry_names),
                        "content_sha256": "",
                    })
                    snapshot_request_path = Path(request_directory) / "request.json"
                    snapshot_request_path.unlink(missing_ok=True)
                    temporary_json(Path(request_directory), "request.json", snapshot_request)
                    snapshot_result_path = workspace / f"t{task_ordinal + 1}-snapshot-result.json"
                    owned_paths.add(snapshot_result_path)
                    before = invoke_snapshot(
                        task, snapshot_request_path, snapshot_result_path, project,
                        environment_values, preflight["environment_probe"],
                    )
                    if not any(item["content_sha256"] == snapshot_request["content_sha256"] for item in snapshot_requests):
                        snapshot_requests.append(snapshot_request)
                    if not any(item["content_sha256"] == before["content_sha256"] for item in snapshot_results):
                        snapshot_results.append(before)
                    if before["status"] != "MATCH":
                        failure_code = (
                            "SNAPSHOT_MISMATCH" if before["status"] == "MISMATCH"
                            else "CLEANUP_FAILED" if before.get("error_code") == "CLEANUP"
                            else "SNAPSHOT_ERROR"
                        )
                        failure_detail = before["error"]
                        attestations.append(bind({
                            "schema_version": 1,
                            "artifact_kind": "RUN_SNAPSHOT_ATTESTATION",
                            "task_id": task["task_id"],
                            "sample_index": sample,
                            "variant": variant_name,
                            "status": "PRECHECK_FAILED",
                            "error_code": failure_code,
                            "error": failure_detail,
                            "snapshot_request_sha256": snapshot_request["content_sha256"],
                            "before_snapshot_result_sha256": before["content_sha256"],
                            "after_snapshot_result_sha256": None,
                            "before_input_snapshot_sha256": None,
                            "after_input_snapshot_sha256": None,
                            "content_sha256": "",
                        }))
                        return write_prepared_pair(
                            prepared_result, prepared_evidence,
                            evaluation_result("ERROR", failure_code, failure_detail), trust, expected_inputs,
                        )
                    input_snapshot = bind({
                        "schema_version": 1,
                        "artifact_kind": "TASK_INPUT_SNAPSHOT",
                        "task_id": task["task_id"],
                        "task_manifest_sha256": task["content_sha256"],
                        "artifact_digests": before["artifact_digests"],
                        "environment_sha256": environment["environment_id"],
                        "content_sha256": "",
                    })
                    if not any(item["content_sha256"] == input_snapshot["content_sha256"] for item in input_snapshots):
                        input_snapshots.append(input_snapshot)
                    try:
                        measurement = invoke_adapter(
                            task, adapter_request, adapter_request_path, variant_path, rendered_path, measurement_path,
                            project,
                            environment_values,
                            control["timeout_ns"],
                            sample,
                            generation["seed_base"] + sample - 1,
                        )
                    except AdapterFailure as failure:
                        attestations.append(bind({
                            "schema_version": 1,
                            "artifact_kind": "RUN_SNAPSHOT_ATTESTATION",
                            "task_id": task["task_id"],
                            "sample_index": sample,
                            "variant": variant_name,
                            "status": "ADAPTER_FAILED",
                            "error_code": failure.code,
                            "error": failure.detail,
                            "snapshot_request_sha256": snapshot_request["content_sha256"],
                            "before_snapshot_result_sha256": before["content_sha256"],
                            "after_snapshot_result_sha256": None,
                            "before_input_snapshot_sha256": input_snapshot["content_sha256"],
                            "after_input_snapshot_sha256": None,
                            "content_sha256": "",
                        }))
                        return write_prepared_pair(
                            prepared_result,
                            prepared_evidence,
                            evaluation_result("ERROR", failure.code, failure.detail),
                            trust,
                            expected_inputs,
                        )
                    if measurement.get("rendered_prompt_sha256") != rendered["content_sha256"]:
                        failure_detail = "measurement adapter result identity disagrees"
                        attestations.append(bind({
                            "schema_version": 1,
                            "artifact_kind": "RUN_SNAPSHOT_ATTESTATION",
                            "task_id": task["task_id"],
                            "sample_index": sample,
                            "variant": variant_name,
                            "status": "ADAPTER_FAILED",
                            "error_code": "ADAPTER_RESULT",
                            "error": failure_detail,
                            "snapshot_request_sha256": snapshot_request["content_sha256"],
                            "before_snapshot_result_sha256": before["content_sha256"],
                            "after_snapshot_result_sha256": None,
                            "before_input_snapshot_sha256": input_snapshot["content_sha256"],
                            "after_input_snapshot_sha256": None,
                            "content_sha256": "",
                        }))
                        return write_prepared_pair(
                            prepared_result, prepared_evidence,
                            evaluation_result("ERROR", "ADAPTER_RESULT", failure_detail), trust, expected_inputs,
                        )
                    after = invoke_snapshot(
                        task, snapshot_request_path, snapshot_result_path, project,
                        environment_values, preflight["environment_probe"],
                    )
                    if not any(item["content_sha256"] == after["content_sha256"] for item in snapshot_results):
                        snapshot_results.append(after)
                    if after["status"] != "MATCH":
                        failure_code = (
                            "SNAPSHOT_MISMATCH" if after["status"] == "MISMATCH"
                            else "CLEANUP_FAILED" if after.get("error_code") == "CLEANUP"
                            else "SNAPSHOT_ERROR"
                        )
                        failure_detail = after["error"]
                        attestations.append(bind({
                            "schema_version": 1,
                            "artifact_kind": "RUN_SNAPSHOT_ATTESTATION",
                            "task_id": task["task_id"],
                            "sample_index": sample,
                            "variant": variant_name,
                            "status": "POSTCHECK_FAILED",
                            "error_code": failure_code,
                            "error": failure_detail,
                            "snapshot_request_sha256": snapshot_request["content_sha256"],
                            "before_snapshot_result_sha256": before["content_sha256"],
                            "after_snapshot_result_sha256": after["content_sha256"],
                            "before_input_snapshot_sha256": input_snapshot["content_sha256"],
                            "after_input_snapshot_sha256": None,
                            "content_sha256": "",
                        }))
                        return write_prepared_pair(
                            prepared_result, prepared_evidence,
                            evaluation_result("ERROR", failure_code, failure_detail), trust, expected_inputs,
                        )
                    if before["artifact_digests"] != after["artifact_digests"]:
                        after_input_snapshot = bind({
                            "schema_version": 1,
                            "artifact_kind": "TASK_INPUT_SNAPSHOT",
                            "task_id": task["task_id"],
                            "task_manifest_sha256": task["content_sha256"],
                            "artifact_digests": after["artifact_digests"],
                            "environment_sha256": environment["environment_id"],
                            "content_sha256": "",
                        })
                        if not any(item["content_sha256"] == after_input_snapshot["content_sha256"] for item in input_snapshots):
                            input_snapshots.append(after_input_snapshot)
                        failure_detail = "task input drifted after adapter invocation"
                        attestations.append(bind({
                            "schema_version": 1,
                            "artifact_kind": "RUN_SNAPSHOT_ATTESTATION",
                            "task_id": task["task_id"],
                            "sample_index": sample,
                            "variant": variant_name,
                            "status": "POSTCHECK_DRIFT",
                            "error_code": "INPUT_DRIFT",
                            "error": failure_detail,
                            "snapshot_request_sha256": snapshot_request["content_sha256"],
                            "before_snapshot_result_sha256": before["content_sha256"],
                            "after_snapshot_result_sha256": after["content_sha256"],
                            "before_input_snapshot_sha256": input_snapshot["content_sha256"],
                            "after_input_snapshot_sha256": after_input_snapshot["content_sha256"],
                            "content_sha256": "",
                        }))
                        return write_prepared_pair(
                            prepared_result, prepared_evidence,
                            evaluation_result("ERROR", "INPUT_DRIFT", failure_detail), trust, expected_inputs,
                        )
                    evaluation_input = bind({
                        "schema_version": 1, "artifact_kind": "EVALUATION_INPUT_IDENTITY", "task_id": task["task_id"],
                        "task_input_snapshot_sha256": input_snapshot["content_sha256"],
                        "parent_variant_sha256": parent_variant["content_sha256"],
                        "candidate_variant_sha256": candidate["content_sha256"],
                        "task_prompt_sha256": task_prompt["content_sha256"],
                        "context_sources_sha256": context["content_sha256"],
                        "generation_policy_sha256": generation["content_sha256"],
                        "generation_request_sha256": measurement["generation_request"]["content_sha256"],
                        "adapter_request_sha256": adapter_request["content_sha256"],
                        "environment_policy_sha256": environment_policy["content_sha256"],
                        "environment_sha256": environment["environment_id"], "sample_index": sample,
                        "paired_seed": generation["seed_base"] + sample - 1, "content_sha256": "",
                    })
                    preparation_ns = 20_000_000
                    generation_ns = measurement["generation_to_passing_patch_ns"]
                    row = bind({
                        "schema_version": 1, "artifact_kind": "PROMPT_TASK_ROW", "evaluation_id": request["evaluation_id"],
                        "task_id": task["task_id"], "sample_index": sample, "variant": variant_name,
                        "variant_id": variant["variant_id"], "variant_sha256": variant["content_sha256"],
                        "prompt_preparation_ns": preparation_ns,
                        "time_to_passing_patch_ns": None if generation_ns is None else preparation_ns + generation_ns,
                        "evaluation_input": evaluation_input, "measurement": measurement, "content_sha256": "",
                    })
                    rows.append(row)
                    expected_inputs.append(bind({
                        "schema_version": 1, "artifact_kind": "PROMPT_EXPECTED_INPUT_DIGEST", "task_id": task["task_id"],
                        "sample_index": sample, "variant": variant_name,
                        "rendered_prompt_sha256": rendered["content_sha256"],
                        "context_sources_sha256": context["content_sha256"],
                        "generation_request_sha256": measurement["generation_request"]["content_sha256"],
                        "adapter_request_sha256": adapter_request["content_sha256"],
                        "provider_request_sha256": measurement["generation_request"]["provider_request_sha256"],
                        "content_sha256": "",
                    }))
                    attestations.append(bind({
                        "schema_version": 1, "artifact_kind": "RUN_SNAPSHOT_ATTESTATION", "task_id": task["task_id"],
                        "sample_index": sample, "variant": variant_name, "status": "COMPLETE", "error_code": "NONE",
                        "error": "", "snapshot_request_sha256": snapshot_request["content_sha256"],
                        "before_snapshot_result_sha256": before["content_sha256"],
                        "after_snapshot_result_sha256": after["content_sha256"],
                        "before_input_snapshot_sha256": input_snapshot["content_sha256"],
                        "after_input_snapshot_sha256": input_snapshot["content_sha256"], "content_sha256": "",
                    }))
                    if measurement.get("status") == "ERROR":
                        failure_detail = measurement.get("diagnostic_summary") or "measurement adapter returned an error"
                        failure_code = "CLEANUP_FAILED" if not measurement.get("cleanup_passed", True) else "ADAPTER_RESULT"
                        return write_prepared_pair(
                            prepared_result, prepared_evidence,
                            evaluation_result("ERROR", failure_code, failure_detail[:4096]), trust, expected_inputs,
                        )
                    if not any(item["content_sha256"] == input_snapshot["content_sha256"] for item in input_snapshots):
                        input_snapshots.append(input_snapshot)
                    for path in (adapter_request_path, rendered_path, variant_path):
                        path.unlink()

    task_aggregates = []
    for task in tasks:
        selected = [row for row in rows if row["task_id"] == task["task_id"]]
        parent_rows = [row for row in selected if row["variant"] == "PARENT"]
        candidate_rows = [row for row in selected if row["variant"] == "CANDIDATE"]
        if any(row["measurement"]["status"] != "FAIL" for row in parent_rows) or any(row["measurement"]["status"] != "PASS" for row in candidate_rows):
            raise EvaluationError("fixed adapter produced an unexpected outcome")
        task_aggregates.append({
            "task_id": task["task_id"], "parent_pass_count": 0,
            "candidate_pass_count": len(candidate_rows),
            "parent_repair_loop_count": sum(row["measurement"]["repair_loop_count"] for row in parent_rows),
            "candidate_repair_loop_count": 0, "paired_pass_count": 0,
            "parent_paired_median_time_ns": None, "candidate_paired_median_time_ns": None,
            "time_improvement_ppm": None, "time_regression_ppm": None,
        })
    total_samples = len(tasks) * request["sample_count"]
    corpus_aggregate = {
        "task_count": len(tasks), "sample_count": request["sample_count"], "parent_pass_count": 0,
        "candidate_pass_count": total_samples, "parent_repair_loop_count": total_samples,
        "candidate_repair_loop_count": 0, "paired_pass_count": 0,
        "parent_paired_median_time_ns": None, "candidate_paired_median_time_ns": None,
        "completion_gain_count": total_samples, "time_improvement_ppm": None,
        "time_regression_ppm": None, "repair_loop_regression_count": 0,
    }
    result = evaluation_result("IMPROVED", "NONE", "")
    result["task_aggregates"] = task_aggregates
    result["corpus_aggregate"] = corpus_aggregate
    return write_prepared_pair(prepared_result, prepared_evidence, result, trust, expected_inputs)


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--prepared-result", required=True, type=Path)
    parser.add_argument("--prepared-evidence", required=True, type=Path)
    parser.add_argument("--final-result-relative", required=True)
    parser.add_argument("--final-evidence-relative", required=True)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    values = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    owned_paths: set[Path] = set()
    status = 2
    try:
        evaluate(
            values.request,
            values.prepared_result,
            values.prepared_evidence,
            values.final_result_relative,
            values.final_evidence_relative,
            owned_paths,
        )
        status = 0
    except ResultOnlyInvalid:
        status = 0
    except (EvaluationError, OSError, TypeError, ValueError, KeyError, IndexError):
        status = 2
    cleanup_failed = False
    for path in sorted(owned_paths, key=lambda item: len(item.parts), reverse=True):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            cleanup_failed = True
    return 3 if cleanup_failed else status


if __name__ == "__main__":
    raise SystemExit(main())
