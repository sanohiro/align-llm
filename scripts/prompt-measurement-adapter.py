#!/usr/bin/env python3
"""Task-parameterized C6 measurement adapter backed by the derived Align generation child.

This is the sibling of `scripts/prompt-fixed-adapter.py` required by section 11.3 of
`docs/specs/c6-prompt-context-optimizer.md`. It is a byte-equal corpus member carrying a
`PYTHON:<sha>` runtime label, so the evaluator's task-command owner still admits exactly
`<interpreter> <one helper>` argv and still requires the declared `measurement_adapter_runtime`
digest and reviewed corpus membership.

It owns workspace orchestration, sealed input admission, contained execution of the validation
runner, `TaskMeasurement` assembly, and redaction, and it performs no provider wire serialization.
The single provider generation call is delegated to the derived `./main prompt generate` child so
that provider request bytes keep exactly one producer: `provider_request_sha256`, the seed
attestation, and the provider identity are copied out of the child's response verbatim.

Every identity the fixed adapter hard-codes is a declared input here: the validation runner, the
task definition, the optional fixture patch, the validation argv, and the generation child all
arrive in the `TaskAdapterRequest` with their digests. Each declared file is verified and sealed
before launch and re-verified after the child returns.

The generation response is not a patch. It carries the settled whole-file edit format described in
section 11.3: one `FILE: <repo-relative-path>` header per edited file followed by a fenced block
holding that file's complete new content. This adapter parses those blocks, requires every declared
path to be inside the task definition's `allowed_edits`, and turns the edit set into the
whole-file-replacement unified diff the validation runner applies. The runner's own allowlist,
pristine-checkout, and mode checks are unchanged and remain the authoritative second gate.
"""

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
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


REQUEST_LIMIT = 65_536
ARTIFACT_LIMIT = 2_097_152
RESULT_LIMIT = 262_144
DIAGNOSTIC_LIMIT = 16_384
SUMMARY_LIMIT = 4_096
GENERATION_RESPONSE_LIMIT = 2_097_152
# The derived generation child is a linked Align executable, not a corpus artifact; it uses
# the same explicit-executable bound as the evaluator and the gate validator.
EXECUTABLE_LIMIT = 268_435_456
HEX64 = frozenset("0123456789abcdef")
PR_SET_CHILD_SUBREAPER = 36
TRUNCATION_MARKER = b"\n[output truncated]"
RUNNER_BOOTSTRAP = (
    "import os,sys;fd=int(sys.argv.pop(1));name=sys.argv.pop(1);"
    "data=b''.join(iter(lambda:os.read(fd,65536),b''));"
    "globals()['__file__']=name;exec(compile(data,name,'exec'))"
)
# The reserved substitution tokens of the declared `validation_argv`. Nothing else in that argv is
# interpreted, so the runner invocation shape belongs to the task manifest rather than to this file.
TASK_TOKEN = "%TASK%"
PATCH_TOKEN = "%PATCH%"
GENERATION_RESPONSE_FIELDS = (
    "schema_version", "artifact_kind", "request_id", "status", "error_code", "error",
    "provider_kind", "provider_model", "provider_request_sha256", "seed_result", "applied_seed",
    "http_status", "content", "dispatch_start_ns", "dispatch_end_ns", "content_sha256",
)
GENERATION_REQUEST_FIELDS = (
    "schema_version", "artifact_kind", "request_id", "provider_kind", "endpoint",
    "provider_model", "api_key_env", "rendered_prompt_path", "rendered_prompt_sha256",
    "max_tokens", "temperature_micros", "paired_seed", "timeout_ns", "max_response_bytes",
    "content_sha256",
)
SEED_RESULTS = ("APPLIED", "UNSUPPORTED", "REJECTED")
# The settled section 11.3 measurement response edit format.
FILE_MARKER = "FILE:"
MAXIMUM_FILE_BLOCKS = 32
MAXIMUM_EDIT_BYTES = 262_144


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


class EditFormatError(AdapterError):
    """The generation response carries no parsable whole-file edit set.

    This is the patch-absent outcome, not an adapter defect: the provider answered, and the answer
    did not contain a usable edit. The row is `FAIL`/`PATCH` with both stages `NOT_RUN`.
    """


class PolicyViolation(AdapterError):
    """The response asked to edit a path outside the task definition's `allowed_edits`.

    The edit set is refused before the validation runner is launched, so no out-of-allowlist byte
    ever reaches a checkout. The row is `POLICY_VIOLATION`/`POLICY` with both stages `NOT_RUN`.
    """


class ImmutableInput:
    """A verified pathname snapshot copied into one sealed anonymous regular file."""

    def __init__(
        self, path: Path, expected_sha256: str, label: str, executable: bool = False,
        maximum: int = ARTIFACT_LIMIT,
    ) -> None:
        source = -1
        descriptor = -1
        try:
            source = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            before = os.fstat(source)
            if not stat.S_ISREG(before.st_mode) or before.st_size < 0 or before.st_size > maximum:
                raise AdapterError(f"{label} type or size is invalid")
            if executable and not before.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                raise AdapterError(f"{label} is not an executable regular file")
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
            if executable:
                os.fchmod(descriptor, 0o500)
            seals = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE
            fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)
            if fcntl.fcntl(descriptor, fcntl.F_GET_SEALS) != seals:
                raise AdapterError(f"{label} sealing failed")
            self.descriptor = descriptor
            self.seals = seals
            self.label = label
            self.byte_count = len(raw)
            self.sha256 = hashlib.sha256(raw).hexdigest()
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

    def read_sealed(self) -> bytes:
        """The exact verified bytes, read back out of the sealed descriptor rather than the path."""
        raw = bytearray()
        while len(raw) < self.byte_count:
            chunk = os.pread(self.descriptor, min(65_536, self.byte_count - len(raw)), len(raw))
            if not chunk:
                raise AdapterError(f"retained {self.label} is short")
            raw.extend(chunk)
        return bytes(raw)

    def verify_sealed(self) -> None:
        if fcntl.fcntl(self.descriptor, fcntl.F_GET_SEALS) != self.seals:
            raise AdapterError(f"retained {self.label} lost its seals")

    def close(self) -> None:
        os.close(self.descriptor)


class ProducedInput(ImmutableInput):
    """A sealed immutable input produced in this process rather than admitted from a pathname.

    The provider-backed patch has no declared digest because it is the generation response's
    content; it is still sealed so the contained runner reads the exact bytes this adapter measured.
    """

    def __init__(self, raw: bytes, label: str) -> None:
        descriptor = -1
        try:
            if len(raw) > ARTIFACT_LIMIT:
                raise AdapterError(f"{label} exceeds its bound")
            descriptor = os.memfd_create(f"align-{label}", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
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
            self.label = label
            self.byte_count = len(raw)
            self.sha256 = hashlib.sha256(raw).hexdigest()
            descriptor = -1
        except OSError:
            raise AdapterError(f"{label} is unavailable") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)


def response_lines(content: str) -> list[str]:
    """Split a response into lines on LF only, tolerating CRLF.

    `str.splitlines` also breaks on form feed and the Unicode line separators, which would silently
    corrupt a file whose content contains them, so the split is explicit.
    """
    return [line[:-1] if line.endswith("\r") else line for line in content.split("\n")]


def fence_run(line: str) -> int:
    """The opening backtick-run length of a fence line, or 0 when the line is not a fence."""
    stripped = line.strip()
    run = len(stripped) - len(stripped.lstrip("`"))
    return run if run >= 3 else 0


def closing_fence(line: str, opening: int) -> bool:
    """A closing fence is only backticks and is at least as long as the opening run.

    A longer outer fence therefore carries shorter nested fences as ordinary content, which is the
    documented way for a response to emit a file that itself contains fenced text.
    """
    stripped = line.strip()
    return bool(stripped) and set(stripped) == {"`"} and len(stripped) >= opening


def parse_file_blocks(content: str) -> list[tuple[str, str]]:
    """Parse the settled whole-file response format out of one generation response.

    Prose before, between, and after the blocks is ignored. The opening fence may carry a language
    tag. A `FILE:` header with no terminated block is a format failure rather than a silently
    dropped edit, so a truncated response can never apply a partial file.
    """
    lines = response_lines(content)
    blocks: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        header = lines[index].strip().strip("*").strip()
        index += 1
        if not header.startswith(FILE_MARKER):
            continue
        declared = header[len(FILE_MARKER):].strip().strip("`").strip().strip('"').strip("'")
        while index < len(lines) and not fence_run(lines[index]):
            if lines[index].strip().strip("*").strip().startswith(FILE_MARKER):
                raise EditFormatError("a FILE header carries no fenced block")
            index += 1
        if index >= len(lines):
            raise EditFormatError("a FILE header carries no fenced block")
        opening = fence_run(lines[index])
        index += 1
        body: list[str] = []
        terminated = False
        while index < len(lines):
            if closing_fence(lines[index], opening):
                terminated = True
                index += 1
                break
            body.append(lines[index])
            index += 1
        if not terminated:
            raise EditFormatError("a fenced file block is not terminated")
        if len(blocks) >= MAXIMUM_FILE_BLOCKS:
            raise EditFormatError("the response declares too many file blocks")
        blocks.append((declared, "".join(line + "\n" for line in body)))
    return blocks


def validated_edit_set(content: str, allowed_edits: Sequence[str]) -> list[tuple[str, str]]:
    """The parsed edit set, refused unless every declared path is inside `allowed_edits`.

    An unsafe spelling — absolute, escaping, or otherwise not a declared editable path — cannot be
    a member of the allowlist, so it takes the same policy-violation exit as any other out-of-set
    path instead of a separate rejection.
    """
    blocks = parse_file_blocks(content)
    if not blocks:
        raise EditFormatError("the response declares no file block")
    edits: dict[str, str] = {}
    for declared, body in blocks:
        path = declared[2:] if declared.startswith("./") else declared
        if path not in allowed_edits:
            raise PolicyViolation(f"the response edits a file outside the editable set: {path}")
        if path in edits:
            raise EditFormatError(f"the response declares {path} twice")
        if len(body.encode("utf-8")) > MAXIMUM_EDIT_BYTES:
            raise EditFormatError(f"the emitted content for {path} exceeds its bound")
        edits[path] = body
    return sorted(edits.items())


def split_diff_lines(text: str) -> tuple[list[str], bool]:
    """The diff line list plus whether the text ends with a newline."""
    if not text:
        return [], True
    complete = text.endswith("\n")
    lines = text.split("\n")
    if complete:
        lines.pop()
    return lines, complete


def whole_file_hunk(path: str, old: str | None, new: str) -> str:
    """One whole-file replacement hunk: every old line removed, every new line added.

    No context line is emitted, so the hunk needs nothing but the pinned file's exact bytes and
    applies with plain `git apply`. An identical file contributes nothing.
    """
    new_lines, new_complete = split_diff_lines(new)
    if old is None:
        header = f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n"
        old_lines, old_complete = [], True
    else:
        old_lines, old_complete = split_diff_lines(old)
        # A fenced block always ends with a line break before its closing fence, so the parser
        # reconstructs every body with a final newline and the format cannot express its absence.
        # A pinned file that ends without one is therefore reproduced exactly when the line
        # sequences agree, and the unchanged-content refusal must still fire; otherwise every such
        # file would yield a spurious whole-file hunk that only adds a newline.
        if old_lines == new_lines and (old_complete == new_complete or not old_complete):
            return ""
        header = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
    parts = [header, f"@@ -{1 if old_lines else 0},{len(old_lines)} +{1 if new_lines else 0},{len(new_lines)} @@\n"]
    parts.extend(f"-{line}\n" for line in old_lines)
    if old_lines and not old_complete:
        parts.append("\\ No newline at end of file\n")
    parts.extend(f"+{line}\n" for line in new_lines)
    if new_lines and not new_complete:
        parts.append("\\ No newline at end of file\n")
    return "".join(parts)


def task_edit_policy(task_definition: ImmutableInput, project: Path) -> tuple[Path, tuple[str, ...]]:
    """The pinned source root and the editable set, read from the sealed task definition."""
    try:
        value = json.loads(task_definition.read_sealed().decode("utf-8", "strict"))
    except (UnicodeError, json.JSONDecodeError):
        raise AdapterError("task definition is not canonical JSON") from None
    if not isinstance(value, dict):
        raise AdapterError("task definition is not a record")
    allowed = value.get("allowed_edits")
    source_dir = value.get("source_dir")
    if (
        not isinstance(allowed, list) or not allowed or len(allowed) > MAXIMUM_FILE_BLOCKS
        or not all(isinstance(item, str) and item for item in allowed)
        or not isinstance(source_dir, str) or not source_dir
    ):
        raise AdapterError("task definition declares no usable editable set")
    root = (project / source_dir).resolve()
    try:
        root.relative_to(project)
    except ValueError:
        raise AdapterError("task definition source directory escapes the project") from None
    if not root.is_dir():
        raise AdapterError("task definition source directory is unavailable")
    return root, tuple(allowed)


def pinned_source(root: Path, relative: str) -> str | None:
    """The pinned bytes of one editable file, or `None` when the edit creates it.

    The pinned tree is the evaluator's already-attested task artifact, and nothing read here is
    trusted: the synthesized hunk only applies when the runner's own checkout holds these exact
    bytes, and the runner re-checks the allowlist after applying.
    """
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise PolicyViolation(f"the editable path escapes the pinned source: {relative}") from None
    try:
        descriptor = os.open(target, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError:
        raise AdapterError(f"pinned source is unavailable: {relative}") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAXIMUM_EDIT_BYTES:
            raise AdapterError(f"pinned source type or size is invalid: {relative}")
        raw = bytearray()
        while len(raw) < metadata.st_size:
            chunk = os.pread(descriptor, min(65_536, metadata.st_size - len(raw)), len(raw))
            if not chunk:
                break
            raw.extend(chunk)
    finally:
        os.close(descriptor)
    try:
        return bytes(raw).decode("utf-8", "strict")
    except UnicodeError:
        raise AdapterError(f"pinned source is not UTF-8: {relative}") from None


def synthesized_patch(edits: Sequence[tuple[str, str]], root: Path) -> bytes:
    """The whole-file-replacement unified diff for one validated edit set."""
    parts = [whole_file_hunk(path, pinned_source(root, path), body) for path, body in edits]
    raw = "".join(parts).encode("utf-8")
    if not raw:
        raise EditFormatError("the response reproduced the pinned files unchanged")
    return raw


def process_group_exists(group: int) -> bool:
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def descendant_process_ids(root_pids: set[int]) -> set[int]:
    parents: dict[int, list[int]] = {}
    if not sys.platform.startswith("linux"):
        return set()
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            pid = int(status_path.parent.name)
            parent_line = next(
                line for line in status_path.read_text(encoding="utf-8").splitlines()
                if line.startswith("PPid:")
            )
            parent = int(parent_line.split()[1])
        except (OSError, StopIteration, ValueError):
            continue
        parents.setdefault(parent, []).append(pid)
    descendants: set[int] = set()
    pending = list(root_pids)
    while pending:
        parent = pending.pop()
        for child in parents.get(parent, []):
            if child not in descendants:
                descendants.add(child)
                pending.append(child)
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
    if value["variant"] not in ("PARENT", "CANDIDATE"):
        raise AdapterError("adapter request variant is invalid")
    if not isinstance(value["sample_index"], int) or isinstance(value["sample_index"], bool):
        raise AdapterError("adapter request sample identity is invalid")
    if value["sample_index"] < 1 or not isinstance(value["paired_seed"], int):
        raise AdapterError("adapter request sample identity is invalid")
    deadline = value["task_deadline_ns"]
    if not isinstance(deadline, int) or isinstance(deadline, bool) or deadline <= 0:
        raise AdapterError("adapter request task deadline is invalid")
    if value["credential_env_name"] is not None and not isinstance(value["credential_env_name"], str):
        raise AdapterError("adapter request credential identity is invalid")
    for name in (
        "variant_sha256", "rendered_prompt_sha256", "generation_policy_sha256",
        "provider_control_sha256", "environment_policy_sha256", "validation_runner_sha256",
        "task_definition_sha256", "generation_child_sha256",
    ):
        if not valid_digest(value[name]):
            raise AdapterError("adapter request contains an invalid digest")
    argv = value["validation_argv"]
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise AdapterError("adapter request validation argv is invalid")
    patch_path = value.get("patch_path")
    patch_sha256 = value.get("patch_sha256")
    if (patch_path is None) != (patch_sha256 is None):
        raise AdapterError("adapter request patch identity is incomplete")
    if patch_path is not None and (not isinstance(patch_path, str) or not valid_digest(patch_sha256)):
        raise AdapterError("adapter request patch identity is invalid")
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


def redact(text: str, credential: str | None) -> str:
    """The exact section 1.2 pass, applied before truncation, hashing, or persistence."""
    if not credential:
        return text
    return text.replace(credential, "[REDACTED]")


def redacted_bytes(raw: bytes, credential: str | None) -> bytes:
    """The section 1.2 pass over raw bytes, so it can run before any byte-level truncation."""
    if not credential:
        return raw
    return raw.replace(credential.encode("utf-8"), b"[REDACTED]")


def bounded_diagnostic(text: str, credential: str | None) -> bytes:
    """Redact a diagnostic string first, then bound it. Never the other way round."""
    return redacted_bytes(text.encode("utf-8"), credential)[:DIAGNOSTIC_LIMIT]


def bounded_text(raw: bytes, limit: int, credential: str | None) -> str:
    text = redact(raw.decode("utf-8", "replace"), credential)
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    prefix = max(0, limit - len(TRUNCATION_MARKER))
    return (encoded[:prefix] + TRUNCATION_MARKER).decode("utf-8", "replace")


class BoundedCapture:
    """A bounded capture that redacts before it truncates.

    The section 1.2 pass must run on the complete stream: truncating first can split a credential
    across the boundary, leaving a prefix of the secret inside the retained bytes that no later
    replacement can find. Each chunk is therefore appended to a small pending tail, everything that
    can no longer begin a credential occurrence is redacted and only then admitted against the
    bound, and the residual tail is redacted at close.
    """

    def __init__(self, credential: str | None = None) -> None:
        self.data = bytearray()
        self.truncated = False
        self.pending = bytearray()
        self.credential = (credential or "").encode("utf-8")

    def _admit(self, raw: bytes) -> None:
        if self.truncated or not raw:
            return
        remaining = DIAGNOSTIC_LIMIT - len(self.data)
        if len(raw) > remaining:
            self.data.extend(raw[:remaining])
            self.truncated = True
        else:
            self.data.extend(raw)

    def _redacted(self, raw: bytes) -> bytes:
        return raw.replace(self.credential, b"[REDACTED]") if self.credential else raw

    def append(self, chunk: bytes) -> None:
        if self.truncated:
            return
        if not self.credential:
            self._admit(chunk)
            return
        self.pending.extend(chunk)
        # The whole pending window is redacted, then everything except its last
        # `len(credential) - 1` bytes is admitted: only those trailing bytes can still begin an
        # occurrence that the next chunk completes, so nothing that could be part of a credential
        # is ever admitted before the pass has seen its complete bytes.
        redacted = self._redacted(bytes(self.pending))
        keep = len(self.credential) - 1
        if len(redacted) > keep:
            self._admit(redacted[: len(redacted) - keep] if keep else redacted)
            self.pending = bytearray(redacted[len(redacted) - keep :]) if keep else bytearray()

    def bytes(self) -> bytes:
        if self.pending:
            raw = bytes(self.pending)
            self.pending.clear()
            self._admit(self._redacted(raw))
        if not self.truncated:
            return bytes(self.data)
        prefix = max(0, DIAGNOSTIC_LIMIT - len(TRUNCATION_MARKER))
        return bytes(self.data[:prefix]) + TRUNCATION_MARKER


def capture_output(
    process: subprocess.Popen[bytes], timeout: float, credential: str | None = None,
) -> tuple[bytes, bytes]:
    captures = {"stdout": BoundedCapture(credential), "stderr": BoundedCapture(credential)}
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


def child_environment(credential_env_name: str | None, credential_value: str | None) -> dict[str, str]:
    """`env_clear()`, then the ordered policy variables, then at most one credential entry."""
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
    if credential_env_name is not None:
        if credential_env_name in environment:
            raise AdapterError("credential environment name duplicates the policy environment")
        if not credential_value:
            raise AdapterError("credential environment value is missing or empty")
        environment[credential_env_name] = credential_value
    return environment


class GenerationFailure(AdapterError):
    """The two-process handoff failed; the row is never scoreable.

    Digest mismatch, a truncated or malformed response, a nonzero child exit, and a child timeout
    all arrive here, and the section 5.2 precedence — `CONTAINMENT`, then `CLEANUP`, then `ADAPTER`
    — is applied from the flags this failure carries.
    """

    def __init__(self, reason: str, cleanup_passed: bool = True, containment_passed: bool = True) -> None:
        super().__init__(reason)
        self.cleanup_passed = cleanup_passed
        self.containment_passed = containment_passed


def generation_request_document(
    request: Mapping[str, Any], control: Mapping[str, Any], policy: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        "schema_version": 1,
        "artifact_kind": "PROMPT_GENERATION_REQUEST",
        "request_id": f"{request['task_id']}-s{request['sample_index']}-{request['variant'].lower()}",
        "provider_kind": control["provider_kind"],
        "endpoint": control["endpoint"],
        "provider_model": control["model"],
        "api_key_env": control["api_key_env"],
        "rendered_prompt_path": request["rendered_prompt_path"],
        "rendered_prompt_sha256": request["rendered_prompt_sha256"],
        "max_tokens": policy["max_tokens"],
        "temperature_micros": policy["temperature_micros"],
        "paired_seed": request["paired_seed"],
        "timeout_ns": control["timeout_ns"],
        "max_response_bytes": control["max_response_bytes"],
        "content_sha256": "",
    }
    ordered = {key: value[key] for key in GENERATION_REQUEST_FIELDS if value[key] is not None}
    bind_digest(ordered)
    return {key: ordered[key] for key in GENERATION_REQUEST_FIELDS if key in ordered}


def validated_generation_response(path: Path, paired_seed: int) -> dict[str, Any]:
    """Decode the child's single output. Any malformed or absent document is a failed handoff."""
    try:
        raw = read_bounded(path, GENERATION_RESPONSE_LIMIT)
    except AdapterError:
        raise GenerationFailure("generation child produced no readable response") from None
    try:
        value = json.loads(raw.decode("utf-8", "strict"))
    except (UnicodeError, json.JSONDecodeError):
        raise GenerationFailure("generation response is truncated or malformed") from None
    if not isinstance(value, dict):
        raise GenerationFailure("generation response is not a record")
    if tuple(value) != tuple(name for name in GENERATION_RESPONSE_FIELDS if name in value):
        raise GenerationFailure("generation response field order is invalid")
    for name in ("schema_version", "artifact_kind", "request_id", "status", "error_code", "error",
                 "provider_kind", "provider_model", "provider_request_sha256", "seed_result",
                 "dispatch_start_ns", "dispatch_end_ns", "content_sha256"):
        if name not in value:
            raise GenerationFailure("generation response is missing a required field")
    if value["schema_version"] != 1 or value["artifact_kind"] != "PROMPT_GENERATION_RESPONSE":
        raise GenerationFailure("generation response header is invalid")
    normalized = dict(value)
    normalized["content_sha256"] = ""
    if hashlib.sha256(canonical_digest_bytes(normalized)).hexdigest() != value["content_sha256"]:
        raise GenerationFailure("generation response digest does not bind its own bytes")
    if not valid_digest(value["provider_request_sha256"]):
        raise GenerationFailure("generation response request digest is invalid")
    if value["seed_result"] not in SEED_RESULTS:
        raise GenerationFailure("generation response seed result is invalid")
    applied = value.get("applied_seed")
    if value["seed_result"] == "APPLIED":
        if applied != paired_seed:
            raise GenerationFailure("applied seed does not equal the requested paired seed")
    elif applied is not None:
        raise GenerationFailure("a non-applied seed result carries an applied seed")
    if value["status"] != "GENERATED":
        raise GenerationFailure(f"generation child reported {value['status']}/{value['error_code']}")
    if not isinstance(value.get("content"), str) or not value["content"]:
        raise GenerationFailure("generated response carries no content")
    return value


def run_generation_child(
    child: ImmutableInput,
    document: Mapping[str, Any],
    scratch: Path,
    timeout: float,
    environment: Mapping[str, str],
    project: Path,
    credential: str | None,
) -> dict[str, Any]:
    """Launch the sealed generation child exactly once and return its validated response.

    The child is one more contained direct child of this adapter: it inherits the same private
    session and group, the same kill/reap/absence-proof cleanup, and the same exactly-once boundary
    as the validation runner. It is launched only through the retained descriptor, never by
    reopening the public pathname.
    """
    request_path = scratch / "generation-request.json"
    response_path = scratch / "generation-response.json"
    process: subprocess.Popen[bytes] | None = None
    try:
        descriptor = os.open(
            request_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600,
        )
        try:
            raw = canonical_bytes(document)
            offset = 0
            while offset < len(raw):
                offset += os.write(descriptor, raw[offset:])
        finally:
            os.close(descriptor)
        process = subprocess.Popen(
            [child.process_path(), "prompt", "generate", str(request_path), str(response_path)],
            cwd=project,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,
            pass_fds=(child.descriptor,),
        )
        stdout, stderr = capture_output(process, timeout, credential)
        # The retained input must be unchanged after the child returns.
        child.verify_sealed()
        if process_group_exists(process.pid) or owned_descendant_ids(process):
            cleanup_passed = cleanup_process_group(process)
            raise GenerationFailure(
                "generation child left a descendant", cleanup_passed, False,
            )
        if process.returncode != 0:
            # `stderr` left `BoundedCapture` already redacted; the slice below is a second
            # truncation, so the bytes are redacted before it and never after.
            detail = redacted_bytes(stderr, credential)[:256].decode("utf-8", "replace")
            raise GenerationFailure(f"generation child exited {process.returncode}: {detail}")
        return validated_generation_response(response_path, document["paired_seed"])
    except subprocess.TimeoutExpired:
        assert process is not None
        cleanup_passed = cleanup_process_group(process)
        raise GenerationFailure("generation child timed out", cleanup_passed, cleanup_passed) from None
    except OSError as error:
        if process is not None:
            cleanup_process_group(process)
        raise GenerationFailure(f"generation child could not run: {error}") from None


def execute_validation(
    request: Mapping[str, Any],
    runner: ImmutableInput,
    task_definition: ImmutableInput,
    patch: ImmutableInput,
    timeout_ns: int,
    environment: Mapping[str, str],
    project: Path,
    credential: str | None,
) -> tuple[str, bool, bool, bytes, bytes]:
    """Run the declared validation runner contained, exactly as the fixed adapter does."""
    timeout = max(0.001, timeout_ns / 1_000_000_000)
    argv_tail = [
        task_definition.process_path() if item == TASK_TOKEN
        else patch.process_path() if item == PATCH_TOKEN
        else item
        for item in request["validation_argv"]
    ]
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [
                sys.executable, "-c", RUNNER_BOOTSTRAP, str(runner.descriptor),
                request["validation_runner_path"], *argv_tail,
            ],
            cwd=project,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,
            pass_fds=(runner.descriptor, task_definition.descriptor, patch.descriptor),
        )
        stdout, stderr = capture_output(process, timeout, credential)
        for item in (runner, task_definition, patch):
            item.verify_sealed()
        if process_group_exists(process.pid) or owned_descendant_ids(process):
            cleanup_passed = cleanup_process_group(process)
            return "ERROR", cleanup_passed, False, b"", b"contained runner left a descendant"
        outcome = (
            "PASS" if process.returncode == 0
            else "TEST_FAIL" if process.returncode == 4
            else "ERROR"
        )
        return outcome, True, True, stdout, stderr
    except subprocess.TimeoutExpired as error:
        assert process is not None
        cleanup_passed = cleanup_process_group(process)
        return "ERROR", cleanup_passed, cleanup_passed, b"", bounded_diagnostic(str(error), credential)
    except (OSError, AdapterError) as error:
        cleanup_passed = True if process is None else cleanup_process_group(process)
        return "ERROR", cleanup_passed, cleanup_passed, b"", bounded_diagnostic(str(error), credential)


def provider_identities(
    request: Mapping[str, Any],
    rendered: Mapping[str, Any],
    policy: Mapping[str, Any],
    control: Mapping[str, Any],
    response: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Copy the provider identity, request digest, and seed attestation out of the response verbatim.

    Nothing here re-serializes provider bytes: `provider_request_sha256` has exactly one producer,
    the generation child, so the section 5.2 non-circularity rule holds with the child as the
    provider boundary.
    """
    if response is None:
        provider_kind = control["provider_kind"]
        provider_model = control["model"]
        provider_sha = "0" * 64
        seed_result = "UNSUPPORTED"
        applied_seed = None
    else:
        provider_kind = response["provider_kind"]
        provider_model = response["provider_model"]
        provider_sha = response["provider_request_sha256"]
        seed_result = response["seed_result"]
        applied_seed = response.get("applied_seed")
    attestation = {
        "schema_version": 1,
        "artifact_kind": "SEED_CAPABILITY_ATTESTATION",
        "provider_kind": provider_kind,
        "provider_model": provider_model,
        "requested_seed": request["paired_seed"],
        "result": seed_result,
        "applied_seed": applied_seed,
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


def measurement(
    request: Mapping[str, Any],
    rendered: Mapping[str, Any],
    policy: Mapping[str, Any],
    control: Mapping[str, Any],
    project: Path,
    scratch: Path,
) -> dict[str, Any]:
    credential_env_name = request["credential_env_name"]
    credential_value = os.environ.get(credential_env_name) if credential_env_name else None
    response: dict[str, Any] | None = None
    retained: list[ImmutableInput] = []
    outcome = "ERROR"
    cleanup_passed = True
    containment_passed = True
    stdout = b""
    stderr = b""
    patch_byte_count = 0
    generation_ns: int | None = None
    applied_edits: list[str] = []
    summary = "provider-backed measurement failed"

    if len(rendered["text"].encode("utf-8")) > policy["max_prompt_bytes"]:
        # An oversized candidate prompt is a pre-run policy violation: no provider call is made and
        # no validation runner is launched.
        generation, attestation = provider_identities(request, rendered, policy, control, None)
        return assemble(
            request, rendered, "POLICY", True, True, b"", b"", 0, None, generation, attestation,
            "prompt exceeds max_prompt_bytes", credential_value,
        )
    try:
        if not CHILD_SUBREAPER_ENABLED:
            raise AdapterError("child-subreaper containment is unavailable")
        # The credential value reaches exactly two processes: this adapter and its generation
        # child. The validation runner's environment stays the cleared policy environment with no
        # credential entry. A missing or empty value for a declared name fails here, before the
        # first external call.
        policy_environment = child_environment(None, None)
        generation_environment = child_environment(credential_env_name, credential_value)
        # Every declared input is verified and sealed before any launch, so a wrong declared digest
        # is rejected before the generation child or the validation runner can leave any marker.
        child = ImmutableInput(
            Path(request["generation_child_path"]), request["generation_child_sha256"],
            "generation-child", executable=True, maximum=EXECUTABLE_LIMIT,
        )
        retained.append(child)
        runner = ImmutableInput(
            Path(request["validation_runner_path"]), request["validation_runner_sha256"],
            "validation-runner",
        )
        retained.append(runner)
        task_definition = ImmutableInput(
            Path(request["task_definition_path"]), request["task_definition_sha256"],
            "task-definition",
        )
        retained.append(task_definition)
        declared_patch: ImmutableInput | None = None
        if request["patch_path"] is not None:
            declared_patch = ImmutableInput(
                Path(request["patch_path"]), request["patch_sha256"], "declared-patch",
            )
            retained.append(declared_patch)

        document = generation_request_document(request, control, policy)
        provider_timeout = max(0.001, control["timeout_ns"] / 1_000_000_000)
        # The measured window starts immediately before the generation child is launched, so child
        # spawn and initialization cost is inside it. The child's own clock never defines it.
        started = time.monotonic_ns()
        response = run_generation_child(
            child, document, scratch, provider_timeout, generation_environment, project,
            credential_value,
        )
        if declared_patch is not None:
            # A deterministic fixture-style task declares its own patch; nothing is parsed from the
            # provider response, and the fixed adapter's contract is reproduced exactly.
            patch = declared_patch
        else:
            # The settled section 11.3 measurement response format: whole-file blocks, validated
            # against the task's editable set before anything is applied, then turned into the
            # whole-file-replacement diff the validation runner applies.
            source_root, allowed_edits = task_edit_policy(task_definition, project)
            edits = validated_edit_set(response["content"], allowed_edits)
            applied_edits = [path for path, _ in edits]
            patch = ProducedInput(synthesized_patch(edits, source_root), "generated-patch")
            retained.append(patch)
        patch_byte_count = patch.byte_count
        # The validation runner is bounded by the task's own declared deadline, not by the
        # provider-control deadline that bounds the generation child. Two sequential children each
        # bounded by the provider deadline could exceed the evaluator's outer sum; bounded by the
        # provider and task deadlines respectively they cannot.
        outcome, cleanup_passed, containment_passed, stdout, stderr = execute_validation(
            request, runner, task_definition, patch, request["task_deadline_ns"],
            policy_environment, project, credential_value,
        )
        if outcome == "PASS":
            # Stopped immediately after the first full required validation command passes.
            generation_ns = time.monotonic_ns() - started
            summary = "provider-backed candidate patch passed validation"
        elif outcome == "TEST_FAIL":
            summary = "provider-backed candidate patch failed validation"
        else:
            summary = "contained validation runner failed"
        summary = f"{summary}; applied edits: {', '.join(applied_edits) or 'declared patch'}"
    except PolicyViolation as failure:
        # The provider answered and its seed attestation is real, so the response identity is kept:
        # a policy violation is a scored outcome, not a failed handoff.
        outcome, generation_ns = "POLICY", None
        summary = str(failure)
        stderr = bounded_diagnostic(str(failure), credential_value)
    except EditFormatError as failure:
        outcome, generation_ns = "PATCH", None
        summary = str(failure)
        stderr = bounded_diagnostic(str(failure), credential_value)
    except GenerationFailure as failure:
        outcome, response, generation_ns = "ERROR", None, None
        cleanup_passed = failure.cleanup_passed
        containment_passed = failure.containment_passed
        summary = str(failure)
        stderr = bounded_diagnostic(str(failure), credential_value)
    except (AdapterError, OSError, TypeError, ValueError, KeyError) as failure:
        outcome, response, generation_ns = "ERROR", None, None
        summary = str(failure)
        stderr = bounded_diagnostic(str(failure), credential_value)
    finally:
        for item in retained:
            try:
                item.close()
            except OSError:
                cleanup_passed = False

    generation, attestation = provider_identities(request, rendered, policy, control, response)
    return assemble(
        request, rendered, outcome, cleanup_passed, containment_passed, stdout, stderr,
        patch_byte_count, generation_ns, generation, attestation, summary, credential_value,
    )


def assemble(
    request: Mapping[str, Any],
    rendered: Mapping[str, Any],
    outcome: str,
    cleanup_passed: bool,
    containment_passed: bool,
    stdout: bytes,
    stderr: bytes,
    patch_byte_count: int,
    generation_ns: int | None,
    generation: Mapping[str, Any],
    attestation: Mapping[str, Any],
    summary: str,
    credential_value: str | None,
) -> dict[str, Any]:
    passed = outcome == "PASS"
    expected_failure = outcome == "TEST_FAIL"
    policy_violation = outcome == "POLICY"
    # The response answered but carried no usable edit set: a scored `FAIL`/`PATCH` with both
    # stages `NOT_RUN`, never an adapter error.
    patch_absent = outcome == "PATCH"
    not_run = policy_violation or patch_absent
    status = (
        "PASS" if passed else "FAIL" if expected_failure or patch_absent
        else "POLICY_VIOLATION" if policy_violation else "ERROR"
    )
    value = {
        "schema_version": 1,
        "artifact_kind": "TASK_MEASUREMENT",
        "status": "ERROR" if not cleanup_passed or not containment_passed else status,
        "failure_kind": (
            "CONTAINMENT" if not containment_passed
            else "CLEANUP" if not cleanup_passed
            else "NONE" if passed
            else "TEST" if expected_failure
            else "POLICY" if policy_violation
            else "PATCH" if patch_absent
            else "ADAPTER"
        ),
        "build_status": "NOT_RUN" if not_run else "PASS" if outcome != "ERROR" else "ERROR",
        "test_status": (
            "NOT_RUN" if not_run else "PASS" if passed
            else "FAIL" if expected_failure else "ERROR"
        ),
        "repair_loop_count": 0,
        "unrelated_diff_count": 0,
        "patch_size_bytes": patch_byte_count,
        "public_api_change_count": 0,
        "policy_violation_count": 1 if policy_violation else 0,
        "cleanup_passed": cleanup_passed,
        "containment_passed": containment_passed,
        "benchmark_regression_ppm": None,
        "generation_to_passing_patch_ns": (
            generation_ns if status == "PASS" and cleanup_passed and containment_passed else None
        ),
        "rendered_prompt_sha256": rendered["content_sha256"],
        "generation_request": dict(generation),
        "environment_probe": environment_probe(),
        "seed_attestation": dict(attestation),
        "diagnostic_summary": bounded_text(summary.encode("utf-8"), SUMMARY_LIMIT, credential_value),
        "diagnostic_stdout": bounded_text(stdout, DIAGNOSTIC_LIMIT, credential_value),
        "diagnostic_stderr": bounded_text(stderr, DIAGNOSTIC_LIMIT, credential_value),
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
    owned: list[Path] = []
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
            or policy["evaluation_provider_kind"] != control["provider_kind"]
            or policy["evaluation_provider_model"] != control["model"]
            or policy["seed_mode"] != "PAIRED_FIXED"
        ):
            raise AdapterError("adapter declared identities disagree")
        # `FIXTURE` never dispatches a model provider, so this adapter never admits it: the fixed
        # adapter remains the deterministic non-gate fixture owner.
        if control["provider_kind"] == "FIXTURE":
            raise AdapterError("the measurement adapter does not admit a FIXTURE provider control")
        project = Path(__file__).resolve().parent.parent
        # The two-process handoff documents live in a private directory, never in the evaluator's
        # workspace, so the snapshot's allowed workspace entries stay exactly what the evaluator
        # declared.
        scratch = Path(tempfile.mkdtemp(prefix="prompt-measurement-adapter-")).resolve()
        owned.append(scratch)
        result = measurement(request, rendered, policy, control, project, scratch)
        if values.result_fd is None:
            write_exclusive(values.result, result)
        else:
            write_retained_result(values.result, values.result_fd, result)
        return 0
    except (AdapterError, OSError, TypeError, ValueError, KeyError):
        return 2
    finally:
        for path in owned:
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
