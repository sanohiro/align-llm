#!/usr/bin/env python3
"""Independent CI validator for the checked-in C6 prompt gate evidence bundle.

The validator re-verifies the gate chain described in section 9 of
``docs/specs/c6-prompt-context-optimizer.md``. It trusts no persisted verdict: every
gate-chain digest is recomputed, the acceptance decision and gate eligibility are rescored
from the persisted rows, and the source identity is re-observed through a content-bound
source verifier launched from explicit build inputs.

The four machine inputs are explicit command-line values with no environment, ambient, or
sibling-checkout fallback:

    --source-bundle-root    absolute root of the CI-created source bundle
    --python-executable-path  absolute physical CPython 3.12 executable
    --git-executable-path   absolute physical Git executable
    --generation-child-path   absolute physical ``./main`` generation child executable
    --generation-child-sha256 lowercase SHA-256 of that exact executable

The generation child is the section 11.3 derived-child relaxation: the binary is built, not
committed, so it is never a corpus member and neither its absolute path nor a machine-specific
spelling is frozen into ``eval/prompt/canonical-v1/``. Its per-run pair is validated before any
evidence identity is read, and the retained same-descriptor bytes must equal the declared digest,
so an unverified local build cannot satisfy the gate.

``--gate-manifest`` defaults to ``eval/prompt/gate/prompt-gate-manifest.json`` beneath the
current working directory, which is the actual CI checkout the gate head is derived from.

Exit codes are deterministic:

    0  the gate evidence bundle is accepted
    1  an explicit build input is missing, malformed, or unusable
    2  the gate evidence bundle is rejected
    3  a validator-owned child process could not be fully removed
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


MANIFEST_LIMIT = 65_536
ACTIVATION_LIMIT = 2_097_152
EVALUATION_LIMIT = 268_435_456
EVIDENCE_LIMIT = 8_388_608
POLICY_LIMIT = 65_536
EXECUTABLE_LIMIT = 268_435_456
GIT_OUTPUT_LIMIT = 262_144
GIT_CONFIG_LIMIT = 4_194_304
GIT_TIMEOUT_SECONDS = 10
VERIFIER_TIMEOUT_SECONDS = 120
PATH_LIMIT = 4_096
PR_SET_CHILD_SUBREAPER = 36

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

GATE_MANIFEST_RELATIVE = "eval/prompt/gate/prompt-gate-manifest.json"

MANIFEST_FIELDS = (
    "schema_version",
    "artifact_kind",
    "gate_id",
    "source_locator",
    "baseline_activation",
    "improved_evaluation",
    "improved_evaluation_evidence",
    "accepted_activation",
    "rollback_activation",
    "content_sha256",
)
LOCATOR_FIELDS = (
    "schema_version",
    "artifact_kind",
    "source_bundle_id",
    "align_llm_source_relative_path",
    "align_source_relative_path",
    "corpus_source_relative_path",
    "corpus_file_set_manifest_relative_path",
    "source_verifier_policy_relative_path",
    "source_verifier_policy_sha256",
    "source_verifier_relative_path",
    "source_verifier_sha256",
    "source_verifier_runtime",
    "source_verifier_interpreter_sha256",
    "git_executable_sha256",
    "content_sha256",
)
LOCATOR_OPTIONAL = frozenset({"corpus_file_set_manifest_relative_path"})
REFERENCE_FIELDS = ("artifact_kind", "path", "artifact_id", "content_sha256")
SOURCE_POLICY_FIELDS = (
    "schema_version",
    "artifact_kind",
    "policy_id",
    "helper_path",
    "helper_sha256",
    "helper_runtime",
    "interpreter_sha256",
    "git_executable_sha256",
    "content_sha256",
)
ACTIVATION_RESULT_FIELDS = (
    "schema_version",
    "artifact_kind",
    "decision_id",
    "status",
    "error_code",
    "error",
    "activation",
    "content_sha256",
)
ACTIVATION_RESULT_OPTIONAL = frozenset({"decision_id", "activation"})
ACTIVATION_FIELDS = (
    "schema_version",
    "artifact_kind",
    "activation_id",
    "operation",
    "scope",
    "parent_activation_id",
    "parent_activation_sha256",
    "effective_variant",
    "accepted_evaluation_id",
    "accepted_evaluation_sha256",
    "rollback_target_activation_id",
    "rollback_target_activation_sha256",
    "decision_reason",
    "content_sha256",
)
EVALUATION_RESULT_FIELDS = (
    "schema_version",
    "artifact_kind",
    "evaluation_id",
    "status",
    "error_code",
    "error",
    "experiment",
    "experiment_artifact",
    "parent_activation",
    "parent_activation_artifact",
    "scope",
    "parent_variant",
    "candidate_variant",
    "corpus_source",
    "corpus",
    "tasks",
    "acceptance_policy_source",
    "acceptance_policy",
    "generation_policy_source",
    "generation_policy",
    "provider_control_source",
    "provider_control",
    "workspace_preflight_source",
    "workspace_preflight_request",
    "workspace_preflight",
    "environment",
    "snapshot_requests",
    "snapshot_results",
    "input_snapshots",
    "snapshot_attestations",
    "trace_failure",
    "sample_count",
    "gate_eligible",
    "rows",
    "task_aggregates",
    "corpus_aggregate",
    "serious_regression_reasons",
    "content_sha256",
)
EVALUATION_RESULT_OPTIONAL = frozenset(
    {
        "evaluation_id",
        "experiment",
        "experiment_artifact",
        "parent_activation",
        "parent_activation_artifact",
        "scope",
        "parent_variant",
        "candidate_variant",
        "corpus_source",
        "corpus",
        "acceptance_policy_source",
        "acceptance_policy",
        "generation_policy_source",
        "generation_policy",
        "provider_control_source",
        "provider_control",
        "workspace_preflight_source",
        "workspace_preflight_request",
        "workspace_preflight",
        "environment",
        "trace_failure",
        "corpus_aggregate",
    }
)
EVIDENCE_FIELDS = (
    "schema_version",
    "artifact_kind",
    "evaluation_id",
    "evaluation_result_sha256",
    "trust",
    "expected_inputs",
    "content_sha256",
)
TRUST_FIELDS = (
    "schema_version",
    "artifact_kind",
    "expected_align_llm_commit",
    "expected_align_revision",
    "expected_corpus_source_kind",
    "expected_corpus_source_repository_id",
    "expected_corpus_source_sha256",
    "align_llm_reachability",
    "align_llm_observed_head",
    "align_reachability",
    "align_observed_revision",
    "corpus_reachability",
    "corpus_observed_source_sha256",
    "content_sha256",
)
TRUST_OPTIONAL = frozenset(
    {"align_llm_observed_head", "align_observed_revision", "corpus_observed_source_sha256"}
)
EXPECTED_INPUT_FIELDS = (
    "schema_version",
    "artifact_kind",
    "task_id",
    "sample_index",
    "variant",
    "rendered_prompt_sha256",
    "context_sources_sha256",
    "generation_request_sha256",
    "adapter_request_sha256",
    "provider_request_sha256",
    "content_sha256",
)
TASK_AGGREGATE_FIELDS = (
    "task_id",
    "parent_pass_count",
    "candidate_pass_count",
    "parent_repair_loop_count",
    "candidate_repair_loop_count",
    "paired_pass_count",
    "parent_paired_median_time_ns",
    "candidate_paired_median_time_ns",
    "time_improvement_ppm",
    "time_regression_ppm",
)
CORPUS_AGGREGATE_FIELDS = (
    "task_count",
    "sample_count",
    "parent_pass_count",
    "candidate_pass_count",
    "parent_repair_loop_count",
    "candidate_repair_loop_count",
    "paired_pass_count",
    "parent_paired_median_time_ns",
    "candidate_paired_median_time_ns",
    "completion_gain_count",
    "time_improvement_ppm",
    "time_regression_ppm",
    "repair_loop_regression_count",
)
ACCEPTANCE_POLICY_FIELDS = (
    "schema_version",
    "artifact_kind",
    "policy_id",
    "minimum_task_count",
    "minimum_samples_per_variant",
    "minimum_completion_gain_count",
    "minimum_time_improvement_ppm",
    "maximum_time_regression_ppm",
    "maximum_repair_loop_regression_count",
    "content_sha256",
)
SOURCE_RESULT_FIELDS = (
    "schema_version",
    "artifact_kind",
    "status",
    "error_code",
    "error",
    "align_llm_reachability",
    "align_llm_observed_head",
    "align_reachability",
    "align_observed_revision",
    "corpus_reachability",
    "corpus_observed_source_sha256",
    "content_sha256",
)

ALLOWED_LOCAL_KEYS = (
    re.compile(r"^remote\.[^.]+\.(url|pushurl|fetch)$"),
    re.compile(r"^branch\.[^.]+\.(remote|merge)$"),
)
REJECTED_EXACT_KEYS = frozenset(
    {
        "core.alternaterefscommand",
        "core.askpass",
        "core.attributesfile",
        "core.editor",
        "core.excludesfile",
        "core.fsmonitor",
        "core.fsmonitorhookversion",
        "core.gitproxy",
        "core.hookspath",
        "core.pager",
        "core.sshcommand",
        "core.worktree",
        "credential.helper",
        "diff.external",
        "gpg.program",
        "sequence.editor",
        "uploadpack.packobjectshook",
    }
)
REJECTED_KEY_PATTERNS = (
    re.compile(r"^alias\."),
    re.compile(r"^browser\..*\.(cmd|path)$"),
    re.compile(r"^credential\."),
    re.compile(r"^diff\..*\.(command|textconv)$"),
    re.compile(r"^difftool\..*\.(cmd|path)$"),
    re.compile(r"^filter\..*\.(clean|smudge|process)$"),
    re.compile(r"^gpg\..*\.program$"),
    re.compile(r"^guitool\..*\.cmd$"),
    re.compile(r"^http\..*\.proxy$"),
    re.compile(r"^include\."),
    re.compile(r"^includeif\."),
    re.compile(r"^man\..*\.(cmd|path)$"),
    re.compile(r"^mergetool\..*\.(cmd|path)$"),
    re.compile(r"^pager\."),
    re.compile(r"^remote\..*\.(promisor|partialclonefilter|proxy|receivepack|uploadpack)$"),
)

FIXED_GIT_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_PAGER": "cat",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_GRAFT_FILE": "/dev/null",
}
FIXED_GIT_OVERRIDES = (
    "-c",
    "core.useReplaceRefs=false",
    "-c",
    "core.alternateRefsCommand=",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "credential.helper=",
    "-c",
    "diff.external=",
)


def enable_child_subreaper() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    try:
        return ctypes.CDLL(None, use_errno=True).prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
    except (AttributeError, OSError):
        return False


CHILD_SUBREAPER_ENABLED = enable_child_subreaper()


class InputError(ValueError):
    """An explicit build input is missing, malformed, or unusable."""


class GateError(ValueError):
    """The gate evidence bundle is rejected."""


class GateCleanupError(GateError):
    """A validator-owned child process could not be fully removed."""


# --- canonical encoding and digests -------------------------------------------------


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def canonical_digest_bytes(value: Any) -> bytes:
    def omit_none(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: omit_none(child) for key, child in item.items() if child is not None}
        if isinstance(item, list):
            return [omit_none(child) for child in item]
        return item

    return canonical_bytes(omit_none(value))


def computed_digest(value: Mapping[str, Any]) -> str:
    preimage = dict(value)
    preimage["content_sha256"] = ""
    return hashlib.sha256(canonical_digest_bytes(preimage)).hexdigest()


def bind_digest(value: dict[str, Any]) -> dict[str, Any]:
    value["content_sha256"] = ""
    value["content_sha256"] = hashlib.sha256(canonical_digest_bytes(value)).hexdigest()
    return value


def require_own_digest(value: Mapping[str, Any], label: str) -> str:
    claimed = value.get("content_sha256")
    if not isinstance(claimed, str) or HEX64.fullmatch(claimed) is None:
        raise GateError(f"{label} digest is not a lowercase SHA-256")
    if computed_digest(value) != claimed:
        raise GateError(f"{label} digest does not match its canonical bytes")
    return claimed


# --- bounded reads ------------------------------------------------------------------


def read_bounded(path: Path, limit: int, label: str) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise GateError(f"{label} is not a regular readable file") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > limit:
            raise GateError(f"{label} has an invalid type or size")
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(descriptor, min(65_536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > limit:
            raise GateError(f"{label} exceeds its bound")
        return bytes(data)
    finally:
        os.close(descriptor)


def json_object(raw: bytes, label: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            if key in value:
                raise GateError(f"{label} has a duplicate field")
            value[key] = child
        return value

    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError):
        raise GateError(f"{label} is not valid UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise GateError(f"{label} is not an object")
    return value


def load_object(path: Path, limit: int, label: str) -> dict[str, Any]:
    return json_object(read_bounded(path, limit, label), label)


# --- shared field and value validation ----------------------------------------------


def exact_record(
    value: Any, fields: Sequence[str], label: str, optional: frozenset[str] = frozenset()
) -> dict[str, Any]:
    """Require an object whose fields are ``fields`` in order, minus omitted options."""
    if not isinstance(value, dict):
        raise GateError(f"{label} is not an object")
    actual = tuple(value)
    cursor = 0
    for name in fields:
        if cursor < len(actual) and actual[cursor] == name:
            cursor += 1
        elif name not in optional:
            raise GateError(f"{label} has the wrong fields or order")
    if cursor != len(actual):
        raise GateError(f"{label} has the wrong fields or order")
    return value


def require_text(value: Any, label: str, *, maximum: int = PATH_LIMIT, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value) or "\x00" in value:
        raise GateError(f"{label} is not bounded text")
    if len(value.encode("utf-8", "strict")) > maximum:
        raise GateError(f"{label} exceeds its bound")
    return value


def require_identifier(value: Any, label: str, maximum: int = 128) -> str:
    text = require_text(value, label, maximum=maximum)
    if not text.isascii():
        raise GateError(f"{label} is not an ASCII identifier")
    return text


def require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise GateError(f"{label} is not a lowercase SHA-256")
    return value


def require_revision(value: Any, label: str) -> str:
    if not isinstance(value, str) or (
        HEX40.fullmatch(value) is None and HEX64.fullmatch(value) is None
    ):
        raise GateError(f"{label} is not a full lowercase revision")
    return value


def require_integer(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise GateError(f"{label} is not an integer")
    if value < minimum or value > maximum:
        raise GateError(f"{label} is out of range")
    return value


def require_bundle_relative(value: Any, label: str) -> Path:
    text = require_text(value, label)
    candidate = Path(text)
    if candidate.is_absolute() or text.startswith("/") or "\\" in text:
        raise GateError(f"{label} is not a bundle-relative path")
    parts = text.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise GateError(f"{label} has an empty, dot, or parent component")
    return candidate


# --- explicit machine inputs ---------------------------------------------------------


def require_explicit_absolute(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise InputError(f"{label} is missing or empty")
    if "\x00" in value or len(value.encode("utf-8", "surrogateescape")) > PATH_LIMIT:
        raise InputError(f"{label} is not bounded text")
    path = Path(value)
    if not path.is_absolute():
        raise InputError(f"{label} is not absolute")
    if any(part in (".", "..") for part in path.parts[1:]):
        raise InputError(f"{label} has an unsafe component")
    if str(path) != value.rstrip("/") and str(path) != value:
        raise InputError(f"{label} is not a normalized absolute path")
    return path


def require_explicit_digest(value: Any, label: str) -> str:
    """Require an explicit lowercase SHA-256 build input with no ambient fallback."""
    if not isinstance(value, str) or not value:
        raise InputError(f"{label} is missing or empty")
    if HEX64.fullmatch(value) is None:
        raise InputError(f"{label} is not a lowercase SHA-256")
    return value


class RetainedExecutable:
    """A regular executable pinned by descriptor for every direct child invocation."""

    def __init__(self, path: Path, label: str, maximum: int = EXECUTABLE_LIMIT) -> None:
        self.label = label
        try:
            self.descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        except OSError:
            raise InputError(f"{label} is not a physical regular readable file") from None
        self.maximum = maximum
        try:
            self.identity = self._identity()
        except BaseException:
            os.close(self.descriptor)
            raise

    def _identity(self) -> tuple[int, int, int, int]:
        metadata = os.fstat(self.descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size <= 0
            or metadata.st_size > self.maximum
        ):
            raise InputError(f"{self.label} has an invalid type or size")
        if not metadata.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            raise InputError(f"{self.label} is not executable")
        return metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size

    def sha256(self) -> str:
        hasher = hashlib.sha256()
        offset = 0
        while offset < self.identity[3]:
            chunk = os.pread(self.descriptor, min(1_048_576, self.identity[3] - offset), offset)
            if not chunk:
                raise InputError(f"{self.label} changed while reading")
            hasher.update(chunk)
            offset += len(chunk)
        return hasher.hexdigest()

    def process_path(self) -> Path:
        path = Path(f"/proc/self/fd/{self.descriptor}")
        if not path.exists():
            raise GateError(f"retained {self.label} execution is unavailable")
        return path

    def verify_unchanged(self, expected: str) -> None:
        if self._identity() != self.identity or self.sha256() != expected:
            raise GateError(f"{self.label} changed during gate observation")

    def close(self) -> None:
        os.close(self.descriptor)


def sha256_file(path: Path, label: str, limit: int = EXECUTABLE_LIMIT) -> str:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise GateError(f"{label} is not a physical regular readable file") from None
    hasher = hashlib.sha256()
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > limit:
            raise GateError(f"{label} has an invalid type or size")
        remaining = metadata.st_size
        while remaining:
            chunk = os.read(descriptor, min(1_048_576, remaining))
            if not chunk:
                raise GateError(f"{label} changed while reading")
            hasher.update(chunk)
            remaining -= len(chunk)
        return hasher.hexdigest()
    finally:
        os.close(descriptor)


# --- physical path boundary ----------------------------------------------------------


def physical_directory(path: Path, label: str) -> Path:
    current = Path("/")
    for component in path.parts[1:]:
        current = current / component
        try:
            metadata = os.lstat(current)
        except OSError:
            raise GateError(f"{label} is unavailable") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise GateError(f"{label} has a symlink component")
    try:
        metadata = os.stat(path, follow_symlinks=False)
    except OSError:
        raise GateError(f"{label} is unavailable") from None
    if not stat.S_ISDIR(metadata.st_mode):
        raise GateError(f"{label} is not a directory")
    return path.resolve(strict=True)


def physical_regular_file(path: Path, label: str) -> Path:
    physical_directory(path.parent, f"{label} parent directory")
    try:
        metadata = os.lstat(path)
    except OSError:
        raise GateError(f"{label} is unavailable") from None
    if stat.S_ISLNK(metadata.st_mode):
        raise GateError(f"{label} is a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise GateError(f"{label} is not a regular file")
    return path


def resolve_beneath(root: Path, relative: Path, label: str) -> Path:
    candidate = root / relative
    resolved = candidate.parent
    try:
        resolved = resolved.resolve(strict=False)
    except OSError:
        raise GateError(f"{label} is unavailable") from None
    if root != resolved and root not in resolved.parents:
        raise GateError(f"{label} escapes the source bundle root")
    return candidate


# --- bounded process containment -----------------------------------------------------


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
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            pid = int(status_path.parent.name)
            parent_line = next(
                line for line in status_path.read_text().splitlines() if line.startswith("PPid:")
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


def run_contained(
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    inherited: Sequence[int],
    timeout_seconds: float,
    label: str,
) -> bytes:
    """Run one direct argv vector in a private session with a bounded stdout capture."""
    if not CHILD_SUBREAPER_ENABLED:
        raise GateCleanupError(f"{label} process containment is unavailable")
    try:
        process = subprocess.Popen(
            [str(item) for item in command],
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
            pass_fds=tuple(inherited),
        )
    except OSError:
        raise GateError(f"{label} is unavailable") from None
    output = bytearray()
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + timeout_seconds
    cleanup_attempted = False
    try:
        assert process.stdout is not None
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GateError(f"{label} timed out")
            events = selector.select(remaining)
            if not events:
                raise GateError(f"{label} timed out")
            for key, _ in events:
                try:
                    chunk = os.read(
                        key.fileobj.fileno(), min(65_536, GIT_OUTPUT_LIMIT + 1 - len(output))
                    )
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                output.extend(chunk)
                if len(output) > GIT_OUTPUT_LIMIT:
                    raise GateError(f"{label} exceeded its output cap")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise GateError(f"{label} timed out")
        process.wait(timeout=remaining)
        if process_group_exists(process.pid) or owned_descendant_ids(process):
            cleanup_attempted = True
            if not cleanup_process_group(process):
                raise GateCleanupError(f"{label} cleanup failed")
            raise GateError(f"{label} left a descendant")
    except (OSError, subprocess.TimeoutExpired, GateError) as failure:
        if not cleanup_attempted:
            cleanup_attempted = True
            if not cleanup_process_group(process):
                raise GateCleanupError(f"{label} cleanup failed") from None
        if isinstance(failure, GateCleanupError):
            raise failure
        raise GateError(f"{label} failed or exceeded its boundary") from None
    finally:
        selector.close()
        if process.stdout is not None and not process.stdout.closed:
            process.stdout.close()
    if process.returncode != 0:
        raise GateError(f"{label} failed")
    return bytes(output)


# --- repository-local Git isolation --------------------------------------------------


def parse_config(raw: bytes, label: str) -> None:
    if len(raw) > GIT_CONFIG_LIMIT or b"\x00" in raw:
        raise GateError(f"{label} is malformed or too large")
    section = ""
    for source_line in raw.splitlines():
        line = source_line.strip()
        if not line or line.startswith((b"#", b";")):
            continue
        if line.startswith(b"[") and line.endswith(b"]"):
            try:
                header = line[1:-1].decode("utf-8", "strict").strip().lower()
            except UnicodeError:
                raise GateError(f"{label} section is invalid") from None
            match = re.fullmatch(r'([a-z0-9-]+)(?:\s+"((?:[^"\\]|\\.)*)")?', header)
            if match is None:
                raise GateError(f"{label} section is malformed")
            section = match.group(1)
            if match.group(2) is not None:
                section += "." + match.group(2).replace('\\"', '"').lower()
            continue
        if not section or b"=" not in line:
            raise GateError(f"{label} assignment is malformed")
        raw_key, _ = line.split(b"=", 1)
        try:
            key = f"{section}.{raw_key.decode('ascii', 'strict').strip().lower()}"
        except UnicodeError:
            raise GateError(f"{label} key is invalid") from None
        rejected = key in REJECTED_EXACT_KEYS or any(
            pattern.match(key) for pattern in REJECTED_KEY_PATTERNS
        )
        allowed = any(pattern.fullmatch(key) for pattern in ALLOWED_LOCAL_KEYS)
        if rejected and not allowed:
            raise GateError(f"{label} has a command-bearing key")


def resolve_git_metadata(repository: Path, label: str) -> tuple[Path, Path]:
    root = physical_directory(repository, label)
    dotgit = root / ".git"
    try:
        metadata = os.lstat(dotgit)
    except OSError:
        raise GateError(f"{label} Git metadata is unavailable") from None
    if stat.S_ISDIR(metadata.st_mode):
        git_dir = dotgit.resolve(strict=True)
    elif stat.S_ISREG(metadata.st_mode):
        raw = read_bounded(dotgit, 4096, f"{label} gitdir pointer")
        if not raw.startswith(b"gitdir: ") or not raw.endswith(b"\n") or raw.count(b"\n") != 1:
            raise GateError(f"{label} gitdir pointer is malformed")
        try:
            pointer = os.fsdecode(raw[8:-1])
        except UnicodeError:
            raise GateError(f"{label} gitdir pointer is not decodable") from None
        candidate = Path(pointer)
        if not candidate.is_absolute():
            candidate = root / candidate
        git_dir = physical_directory(candidate, f"{label} Git directory")
    else:
        raise GateError(f"{label} .git is not a directory or pointer file")
    commondir_path = git_dir / "commondir"
    if commondir_path.exists():
        raw = read_bounded(commondir_path, 4096, f"{label} commondir pointer")
        if not raw.endswith(b"\n") or raw.count(b"\n") != 1 or b"\x00" in raw:
            raise GateError(f"{label} commondir pointer is malformed")
        candidate = Path(os.fsdecode(raw[:-1]))
        if not candidate.is_absolute():
            candidate = git_dir / candidate
        common_dir = physical_directory(candidate, f"{label} Git common directory")
    else:
        common_dir = git_dir
    return git_dir, common_dir


def scan_local_git_metadata(repository: Path, label: str) -> tuple[Path, Path]:
    """Raw metadata and configuration walk performed before any Git child."""
    git_dir, common_dir = resolve_git_metadata(repository, label)
    for config, name in ((common_dir / "config", "config"), (git_dir / "config.worktree", "config.worktree")):
        if config.exists() or config.is_symlink():
            parse_config(
                read_bounded(config, GIT_CONFIG_LIMIT, f"{label} local Git {name}"),
                f"{label} local Git {name}",
            )
    for candidate in (
        common_dir / "refs" / "replace",
        common_dir / "info" / "grafts",
        common_dir / "objects" / "info" / "alternates",
    ):
        if candidate.exists() or candidate.is_symlink():
            raise GateError(f"{label} has Git replacement, graft, or alternate metadata")
    return git_dir, common_dir


class GitTool:
    """Every Git child uses this exact retained descriptor, argv prefix, and environment."""

    def __init__(self, executable: RetainedExecutable) -> None:
        self.executable = executable

    def run(self, repository: Path, *arguments: str, label: str) -> bytes:
        if not CHILD_SUBREAPER_ENABLED:
            raise GateCleanupError(f"{label} process containment is unavailable")
        command = [
            str(self.executable.process_path()),
            "--no-pager",
            "-C",
            str(repository),
            *FIXED_GIT_OVERRIDES,
            *arguments,
        ]
        return run_contained(
            command,
            repository,
            FIXED_GIT_ENVIRONMENT,
            (self.executable.descriptor,),
            GIT_TIMEOUT_SECONDS,
            label,
        )

    def verify_common_directory(self, repository: Path, raw_common: Path, label: str) -> None:
        """Require Git to report the raw-walk common directory and an empty replacement namespace."""
        reported = self.run(
            repository,
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
            label=f"{label} Git common-directory locator",
        )
        try:
            text = reported.decode("utf-8", "strict").strip()
        except UnicodeError:
            raise GateError(f"{label} Git common directory is not decodable") from None
        if not text or Path(text).resolve(strict=True) != raw_common:
            raise GateError(f"{label} Git common directory disagrees with its raw metadata")
        stream = self.run(
            repository,
            "for-each-ref",
            "--format=%(refname)%00",
            "refs/replace/",
            label=f"{label} Git replacement namespace",
        )
        if stream:
            raise GateError(f"{label} Git replacement namespace is non-empty")


# --- gate manifest and locator -------------------------------------------------------


def validate_reference(value: Any, kind: str, label: str) -> dict[str, Any]:
    reference = exact_record(value, REFERENCE_FIELDS, label)
    if reference["artifact_kind"] != kind:
        raise GateError(f"{label} does not name a {kind}")
    require_bundle_relative(reference["path"], f"{label} path")
    require_identifier(reference["artifact_id"], f"{label} artifact id")
    require_digest(reference["content_sha256"], f"{label} digest")
    return reference


def validate_manifest(value: dict[str, Any]) -> dict[str, Any]:
    manifest = exact_record(value, MANIFEST_FIELDS, "gate manifest")
    if manifest["schema_version"] != 1 or manifest["artifact_kind"] != "PROMPT_GATE_MANIFEST":
        raise GateError("gate manifest header is invalid")
    require_identifier(manifest["gate_id"], "gate manifest gate id")
    require_own_digest(manifest, "gate manifest")
    validate_locator(manifest["source_locator"])
    references = {
        "baseline_activation": "PROMPT_ACTIVATION_RESULT",
        "improved_evaluation": "PROMPT_EVALUATION_RESULT",
        "improved_evaluation_evidence": "PROMPT_EVALUATION_EVIDENCE",
        "accepted_activation": "PROMPT_ACTIVATION_RESULT",
        "rollback_activation": "PROMPT_ACTIVATION_RESULT",
    }
    seen: set[str] = set()
    for name, kind in references.items():
        reference = validate_reference(manifest[name], kind, f"gate manifest {name}")
        if reference["path"] in seen:
            raise GateError("gate manifest references one path twice")
        seen.add(reference["path"])
    return manifest


def validate_locator(value: Any) -> dict[str, Any]:
    locator = exact_record(value, LOCATOR_FIELDS, "gate source locator", LOCATOR_OPTIONAL)
    if locator["schema_version"] != 1 or locator["artifact_kind"] != "PROMPT_GATE_SOURCE_LOCATOR":
        raise GateError("gate source locator header is invalid")
    require_identifier(locator["source_bundle_id"], "gate source bundle id")
    for name in (
        "align_llm_source_relative_path",
        "align_source_relative_path",
        "corpus_source_relative_path",
        "source_verifier_policy_relative_path",
        "source_verifier_relative_path",
    ):
        require_bundle_relative(locator[name], f"gate locator {name}")
    manifest_relative = locator.get("corpus_file_set_manifest_relative_path")
    if manifest_relative is not None:
        require_bundle_relative(manifest_relative, "gate locator corpus file-set manifest path")
    for name in (
        "source_verifier_policy_sha256",
        "source_verifier_sha256",
        "source_verifier_interpreter_sha256",
        "git_executable_sha256",
    ):
        require_digest(locator[name], f"gate locator {name}")
    expected_runtime = (
        f"CPYTHON:{locator['source_verifier_interpreter_sha256']}:{locator['source_verifier_sha256']}"
    )
    if locator["source_verifier_runtime"] != expected_runtime:
        raise GateError("gate locator source-verifier runtime identity is invalid")
    require_own_digest(locator, "gate source locator")
    return locator


# --- referenced artifact loading -----------------------------------------------------


def load_referenced(
    directory: Path, reference: Mapping[str, Any], limit: int, label: str
) -> dict[str, Any]:
    relative = Path(reference["path"])
    candidate = directory / relative
    resolved_parent = candidate.parent.resolve(strict=False)
    directory_resolved = directory.resolve(strict=True)
    if directory_resolved != resolved_parent and directory_resolved not in resolved_parent.parents:
        raise GateError(f"{label} escapes the gate evidence directory")
    physical_regular_file(candidate, label)
    artifact = load_object(candidate, limit, label)
    claimed = require_own_digest(artifact, label)
    if claimed != reference["content_sha256"]:
        raise GateError(f"{label} digest does not match its manifest reference")
    return artifact


# --- activation validation -----------------------------------------------------------


def validate_variant_digests(variant: Any, label: str) -> str:
    if not isinstance(variant, dict):
        raise GateError(f"{label} is not an object")
    for name in ("base_prompt", "repo_prompt"):
        nested = variant.get(name)
        if not isinstance(nested, dict):
            raise GateError(f"{label} {name} is not an object")
        require_own_digest(nested, f"{label} {name}")
    return require_own_digest(variant, label)


def validate_scope_digests(scope: Any, label: str) -> str:
    if not isinstance(scope, dict):
        raise GateError(f"{label} is not an object")
    revision = scope.get("corpus_revision")
    if not isinstance(revision, dict):
        raise GateError(f"{label} corpus revision is not an object")
    require_own_digest(revision, f"{label} corpus revision")
    return require_own_digest(scope, label)


def validate_activation(artifact: dict[str, Any], status: str, label: str) -> dict[str, Any]:
    exact_record(artifact, ACTIVATION_RESULT_FIELDS, label, ACTIVATION_RESULT_OPTIONAL)
    if artifact["schema_version"] != 1 or artifact["artifact_kind"] != "PROMPT_ACTIVATION_RESULT":
        raise GateError(f"{label} header is invalid")
    if artifact["status"] != status:
        raise GateError(f"{label} status is not {status}")
    if artifact["error_code"] != "NONE" or artifact["error"] != "":
        raise GateError(f"{label} carries an error")
    decision_id = require_identifier(artifact.get("decision_id"), f"{label} decision id", 96)
    activation = artifact.get("activation")
    exact_record(activation, ACTIVATION_FIELDS, f"{label} activation")
    if activation["schema_version"] != 1 or activation["artifact_kind"] != "PROMPT_ACTIVATION":
        raise GateError(f"{label} activation header is invalid")
    if activation["activation_id"] != f"{decision_id}/activation":
        raise GateError(f"{label} activation id is not derived from its decision id")
    operation = {"BASELINED": "BASELINE", "ACCEPTED": "ACCEPT", "ROLLED_BACK": "ROLLBACK"}[status]
    if activation["operation"] != operation:
        raise GateError(f"{label} operation does not match its status")
    validate_scope_digests(activation["scope"], f"{label} scope")
    validate_variant_digests(activation["effective_variant"], f"{label} effective variant")
    require_own_digest(activation, f"{label} activation")

    def pair(prefix: str) -> tuple[bool, bool]:
        identifier = activation[f"{prefix}_id"]
        digest = activation[f"{prefix}_sha256"]
        if not isinstance(identifier, str) or not isinstance(digest, str):
            raise GateError(f"{label} {prefix} pair is not text")
        empty = not identifier and not digest
        present = bool(identifier) and identifier.isascii() and HEX64.fullmatch(digest) is not None
        if not empty and not present:
            raise GateError(f"{label} {prefix} pair is inconsistent")
        return empty, present

    parent_empty, parent_present = pair("parent_activation")
    accepted_empty, accepted_present = pair("accepted_evaluation")
    rollback_empty, rollback_present = pair("rollback_target_activation")
    reason = activation["decision_reason"]
    if operation == "BASELINE":
        valid = parent_empty and accepted_empty and rollback_empty and reason == ""
    elif operation == "ACCEPT":
        valid = parent_present and accepted_present and rollback_empty and reason == ""
    else:
        valid = (
            parent_present
            and (accepted_empty or accepted_present)
            and rollback_present
            and bool(reason)
            and len(reason.encode("utf-8")) <= 4096
        )
    if not valid:
        raise GateError(f"{label} activation cross-field shape is invalid for {operation}")
    return activation


# --- evaluation scoring re-computation ------------------------------------------------


def score_median(values: Sequence[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    lower = ordered[middle - 1]
    return lower + (ordered[middle] - lower) // 2


def time_metrics(parent: int | None, candidate: int | None) -> tuple[int | None, int | None]:
    if parent is None or candidate is None or parent <= 0:
        return None, None
    if candidate <= parent:
        return (parent - candidate) * 1_000_000 // parent, 0
    return 0, (candidate - parent) * 1_000_000 // parent


def status_value(measurement: Mapping[str, Any]) -> str:
    return measurement["status"]


def rescore(
    result: Mapping[str, Any], policy: Mapping[str, Any]
) -> tuple[str, list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """Recompute the section 8 aggregates, status, and serious-regression stream."""
    tasks = result["tasks"]
    rows = result["rows"]
    sample_count = result["sample_count"]
    aggregates: list[dict[str, Any]] = []
    indexed: list[dict[int, dict[str, Mapping[str, Any]]]] = []
    corpus_parent_times: list[int] = []
    corpus_candidate_times: list[int] = []
    corpus_parent_repairs = 0
    corpus_candidate_repairs = 0
    parent_passes = 0
    candidate_passes = 0
    paired_passes = 0
    if len(rows) != len(tasks) * sample_count * 2:
        raise GateError("evaluation row count does not match its task and sample schedule")
    for task in tasks:
        selected = [row for row in rows if row["task_id"] == task["task_id"]]
        pairs: dict[int, dict[str, Mapping[str, Any]]] = {}
        for row in selected:
            variant = row["variant"]
            if variant not in ("PARENT", "CANDIDATE"):
                raise GateError("evaluation row variant label is invalid")
            sample = row["sample_index"]
            if variant in pairs.setdefault(sample, {}):
                raise GateError("evaluation rows repeat one task, sample, and variant")
            pairs[sample][variant] = row
        if len(pairs) != sample_count or any(
            set(pair) != {"PARENT", "CANDIDATE"} for pair in pairs.values()
        ):
            raise GateError("evaluation rows are not a complete parent/candidate schedule")
        if set(pairs) != set(range(1, sample_count + 1)):
            raise GateError("evaluation sample indices are not the exact one-based schedule")
        indexed.append(pairs)
        parent_rows = [pairs[sample]["PARENT"] for sample in range(1, sample_count + 1)]
        candidate_rows = [pairs[sample]["CANDIDATE"] for sample in range(1, sample_count + 1)]
        task_parent_passes = sum(row["measurement"]["status"] == "PASS" for row in parent_rows)
        task_candidate_passes = sum(row["measurement"]["status"] == "PASS" for row in candidate_rows)
        task_parent_repairs = sum(row["measurement"]["repair_loop_count"] for row in parent_rows)
        task_candidate_repairs = sum(
            row["measurement"]["repair_loop_count"] for row in candidate_rows
        )
        task_parent_times: list[int] = []
        task_candidate_times: list[int] = []
        task_paired = 0
        for sample in range(1, sample_count + 1):
            parent_row = pairs[sample]["PARENT"]
            candidate_row = pairs[sample]["CANDIDATE"]
            if (
                parent_row["measurement"]["status"] == "PASS"
                and candidate_row["measurement"]["status"] == "PASS"
            ):
                task_paired += 1
                task_parent_times.append(parent_row["time_to_passing_patch_ns"])
                task_candidate_times.append(candidate_row["time_to_passing_patch_ns"])
        parent_median = score_median(task_parent_times)
        candidate_median = score_median(task_candidate_times)
        improvement, regression = time_metrics(parent_median, candidate_median)
        aggregates.append(
            {
                "task_id": task["task_id"],
                "parent_pass_count": task_parent_passes,
                "candidate_pass_count": task_candidate_passes,
                "parent_repair_loop_count": task_parent_repairs,
                "candidate_repair_loop_count": task_candidate_repairs,
                "paired_pass_count": task_paired,
                "parent_paired_median_time_ns": parent_median,
                "candidate_paired_median_time_ns": candidate_median,
                "time_improvement_ppm": improvement,
                "time_regression_ppm": regression,
            }
        )
        parent_passes += task_parent_passes
        candidate_passes += task_candidate_passes
        corpus_parent_repairs += task_parent_repairs
        corpus_candidate_repairs += task_candidate_repairs
        paired_passes += task_paired
        corpus_parent_times.extend(task_parent_times)
        corpus_candidate_times.extend(task_candidate_times)

    parent_median = score_median(corpus_parent_times)
    candidate_median = score_median(corpus_candidate_times)
    improvement, regression = time_metrics(parent_median, candidate_median)
    repair_regression = max(0, corpus_candidate_repairs - corpus_parent_repairs)
    corpus = {
        "task_count": len(tasks),
        "sample_count": sample_count,
        "parent_pass_count": parent_passes,
        "candidate_pass_count": candidate_passes,
        "parent_repair_loop_count": corpus_parent_repairs,
        "candidate_repair_loop_count": corpus_candidate_repairs,
        "paired_pass_count": paired_passes,
        "parent_paired_median_time_ns": parent_median,
        "candidate_paired_median_time_ns": candidate_median,
        "completion_gain_count": candidate_passes - parent_passes,
        "time_improvement_ppm": improvement,
        "time_regression_ppm": regression,
        "repair_loop_regression_count": repair_regression,
    }

    def reason(task_id: str, sample: int, code: str, parent: str, candidate: str, limit: str):
        return {
            "task_id": task_id,
            "sample_index": sample,
            "code": code,
            "parent_value": parent,
            "candidate_value": candidate,
            "limit": limit,
        }

    reasons: list[dict[str, Any]] = []
    if repair_regression > policy["maximum_repair_loop_regression_count"]:
        reasons.append(
            reason(
                "CORPUS",
                0,
                "REPAIR_LOOPS",
                str(corpus_parent_repairs),
                str(corpus_candidate_repairs),
                str(policy["maximum_repair_loop_regression_count"]),
            )
        )
    if regression is not None and regression > policy["maximum_time_regression_ppm"]:
        reasons.append(
            reason(
                "CORPUS",
                0,
                "TIME",
                str(parent_median),
                str(candidate_median),
                str(policy["maximum_time_regression_ppm"]),
            )
        )
    for ordinal, task in enumerate(tasks):
        aggregate = aggregates[ordinal]
        limit = task["regression_limits"]
        task_regression = aggregate["time_regression_ppm"]
        if task_regression is not None and task_regression > policy["maximum_time_regression_ppm"]:
            reasons.append(
                reason(
                    task["task_id"],
                    0,
                    "TIME",
                    str(aggregate["parent_paired_median_time_ns"]),
                    str(aggregate["candidate_paired_median_time_ns"]),
                    str(policy["maximum_time_regression_ppm"]),
                )
            )
        for sample in range(1, sample_count + 1):
            parent = indexed[ordinal][sample]["PARENT"]["measurement"]
            candidate = indexed[ordinal][sample]["CANDIDATE"]["measurement"]
            candidate_value = status_value(candidate)
            if parent["status"] == "PASS" and candidate["status"] != "PASS":
                reasons.append(
                    reason(task["task_id"], sample, "PASS_TO_FAIL", "PASS", candidate_value, "NONE")
                )
            if parent["build_status"] == "PASS" and candidate["build_status"] != "PASS":
                reasons.append(
                    reason(task["task_id"], sample, "BUILD", "PASS", candidate_value, "NONE")
                )
            if parent["test_status"] == "PASS" and candidate["test_status"] != "PASS":
                reasons.append(
                    reason(task["task_id"], sample, "TEST", "PASS", candidate_value, "NONE")
                )
            if candidate["status"] == "POLICY_VIOLATION":
                reasons.append(
                    reason(task["task_id"], sample, "POLICY", "NONE", "POLICY_VIOLATION", "NONE")
                )
            for field, maximum, code in (
                ("unrelated_diff_count", "maximum_unrelated_diff_count", "UNRELATED_DIFF"),
                ("public_api_change_count", "maximum_public_api_change_count", "PUBLIC_API"),
                ("patch_size_bytes", "maximum_patch_size_bytes", "PATCH_SIZE"),
                ("repair_loop_count", "maximum_repair_loops", "REPAIR_LOOPS"),
            ):
                if candidate[field] > limit[maximum]:
                    reasons.append(
                        reason(
                            task["task_id"],
                            sample,
                            code,
                            "NONE",
                            str(candidate[field]),
                            str(limit[maximum]),
                        )
                    )
            benchmark_limit = limit.get("maximum_benchmark_regression_ppm")
            benchmark = candidate.get("benchmark_regression_ppm")
            if (
                candidate["status"] == "PASS"
                and benchmark_limit is not None
                and benchmark is not None
                and benchmark > benchmark_limit
            ):
                reasons.append(
                    reason(
                        task["task_id"],
                        sample,
                        "BENCHMARK",
                        "NONE",
                        str(benchmark),
                        str(benchmark_limit),
                    )
                )
    if reasons:
        status = "SERIOUS_REGRESSION"
    else:
        completion = corpus["completion_gain_count"] >= policy["minimum_completion_gain_count"]
        timing = (
            candidate_passes == parent_passes
            and all(item["candidate_pass_count"] >= item["parent_pass_count"] for item in aggregates)
            and corpus_candidate_repairs <= corpus_parent_repairs
            and improvement is not None
            and improvement >= policy["minimum_time_improvement_ppm"]
        )
        status = "IMPROVED" if completion or timing else "NO_IMPROVEMENT"
    return status, aggregates, corpus, reasons


def validate_acceptance_policy(value: Any) -> dict[str, Any]:
    policy = exact_record(value, ACCEPTANCE_POLICY_FIELDS, "acceptance policy")
    if policy["schema_version"] != 1 or policy["artifact_kind"] != "PROMPT_ACCEPTANCE_POLICY":
        raise GateError("acceptance policy header is invalid")
    require_identifier(policy["policy_id"], "acceptance policy id")
    require_integer(policy["minimum_task_count"], "minimum task count", minimum=1, maximum=64)
    require_integer(
        policy["minimum_samples_per_variant"], "minimum samples per variant", minimum=2, maximum=16
    )
    require_integer(
        policy["minimum_completion_gain_count"],
        "minimum completion gain count",
        minimum=1,
        maximum=1_024,
    )
    require_integer(
        policy["minimum_time_improvement_ppm"],
        "minimum time improvement ppm",
        minimum=1,
        maximum=1_000_000,
    )
    require_integer(
        policy["maximum_time_regression_ppm"],
        "maximum time regression ppm",
        minimum=0,
        maximum=1_000_000,
    )
    require_integer(
        policy["maximum_repair_loop_regression_count"],
        "maximum repair loop regression count",
        minimum=0,
        maximum=65_536,
    )
    return policy


def validate_evaluation_pair(
    result: dict[str, Any], evidence: dict[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    """Re-verify the improved evaluation and its independently produced evidence."""
    exact_record(result, EVALUATION_RESULT_FIELDS, "evaluation result", EVALUATION_RESULT_OPTIONAL)
    if result["schema_version"] != 1 or result["artifact_kind"] != "PROMPT_EVALUATION_RESULT":
        raise GateError("evaluation result header is invalid")
    if result["status"] != "IMPROVED":
        raise GateError("gate evaluation is not IMPROVED")
    if result["error_code"] != "NONE" or result["error"] != "":
        raise GateError("gate evaluation carries an error")
    if result.get("trace_failure") is not None:
        raise GateError("gate evaluation carries a trace overflow envelope")
    if result["gate_eligible"] is not True:
        raise GateError("gate evaluation is not marked gate eligible")
    if result["serious_regression_reasons"]:
        raise GateError("gate evaluation records a serious regression")
    evaluation_id = require_identifier(result.get("evaluation_id"), "evaluation id")
    require_integer(result["sample_count"], "evaluation sample count", minimum=2, maximum=16)
    if not isinstance(result["tasks"], list) or not result["tasks"]:
        raise GateError("gate evaluation has no tasks")

    exact_record(evidence, EVIDENCE_FIELDS, "evaluation evidence")
    if evidence["schema_version"] != 1 or evidence["artifact_kind"] != "PROMPT_EVALUATION_EVIDENCE":
        raise GateError("evaluation evidence header is invalid")
    if evidence["evaluation_id"] != evaluation_id:
        raise GateError("evidence evaluation id does not match its result")
    if evidence["evaluation_result_sha256"] != result["content_sha256"]:
        raise GateError("evidence result digest does not match its result")

    trust = exact_record(evidence["trust"], TRUST_FIELDS, "evidence trust", TRUST_OPTIONAL)
    if trust["schema_version"] != 1 or trust["artifact_kind"] != "PROMPT_VERIFIER_TRUST":
        raise GateError("evidence trust header is invalid")
    require_revision(trust["expected_align_llm_commit"], "expected align-llm commit")
    require_revision(trust["expected_align_revision"], "expected Align revision")
    if trust["expected_corpus_source_kind"] == "GIT_COMMIT":
        require_identifier(
            trust["expected_corpus_source_repository_id"], "expected corpus repository id"
        )
        require_revision(trust["expected_corpus_source_sha256"], "expected corpus identity")
    elif trust["expected_corpus_source_kind"] == "FILE_SET":
        if trust["expected_corpus_source_repository_id"] != "":
            raise GateError("file-set corpus trust carries a repository id")
        require_digest(trust["expected_corpus_source_sha256"], "expected corpus identity")
    else:
        raise GateError("evidence corpus source kind is invalid")
    for reachability, observed in (
        ("align_llm_reachability", "align_llm_observed_head"),
        ("align_reachability", "align_observed_revision"),
        ("corpus_reachability", "corpus_observed_source_sha256"),
    ):
        if trust[reachability] != "VERIFIED":
            raise GateError(f"gate evidence {reachability} is not VERIFIED")
        require_revision(trust.get(observed), f"evidence {observed}")
    if trust["align_llm_observed_head"] != trust["expected_align_llm_commit"]:
        raise GateError("evidence align-llm observation disagrees with its expectation")
    if trust["align_observed_revision"] != trust["expected_align_revision"]:
        raise GateError("evidence Align observation disagrees with its expectation")
    if trust["corpus_observed_source_sha256"] != trust["expected_corpus_source_sha256"]:
        raise GateError("evidence corpus observation disagrees with its expectation")

    scope = result.get("scope")
    scope_digest = validate_scope_digests(scope, "evaluation scope")
    if scope["align_revision"] != trust["expected_align_revision"]:
        raise GateError("evaluation scope Align revision disagrees with its evidence")
    revision = scope["corpus_revision"]
    if (
        revision["source_kind"] != trust["expected_corpus_source_kind"]
        or revision["source_repository_id"] != trust["expected_corpus_source_repository_id"]
        or revision["source_sha256"] != trust["expected_corpus_source_sha256"]
    ):
        raise GateError("evaluation scope corpus identity disagrees with its evidence")
    environment = result.get("environment")
    if not isinstance(environment, dict) or not isinstance(environment.get("core"), dict):
        raise GateError("gate evaluation has no environment identity")
    core = environment["core"]
    if (
        core.get("align_llm_commit") != trust["expected_align_llm_commit"]
        or core.get("align_revision") != trust["expected_align_revision"]
    ):
        raise GateError("evaluation environment source identity disagrees with its evidence")
    cpu_count = core.get("logical_cpu_count")
    if not isinstance(cpu_count, int) or isinstance(cpu_count, bool) or cpu_count <= 0:
        raise GateError("gate evaluation environment has no positive logical CPU count")

    parent_digest = validate_variant_digests(result.get("parent_variant"), "parent variant")
    candidate_digest = validate_variant_digests(result.get("candidate_variant"), "candidate variant")
    if parent_digest == candidate_digest:
        raise GateError("gate evaluation parent and candidate variants are identical")

    rows = result["rows"]
    if not isinstance(rows, list) or not rows:
        raise GateError("gate evaluation has no rows")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise GateError("evaluation row is not an object")
        if row.get("evaluation_id") != evaluation_id:
            raise GateError("evaluation row is bound to another evaluation")
        expected_variant = parent_digest if row.get("variant") == "PARENT" else candidate_digest
        if row.get("variant_sha256") != expected_variant:
            raise GateError("evaluation row variant digest does not match its named variant")
        if row["measurement"]["seed_attestation"]["result"] != "APPLIED":
            raise GateError("gate evaluation row does not carry an APPLIED seed attestation")

    expected_inputs = evidence["expected_inputs"]
    if not isinstance(expected_inputs, list) or len(expected_inputs) != len(rows):
        raise GateError("evidence expected inputs do not cover every row exactly once")
    identities: set[tuple[str, int, str]] = set()
    for index, (expected, row) in enumerate(zip(expected_inputs, rows)):
        exact_record(expected, EXPECTED_INPUT_FIELDS, f"evidence expected input {index}")
        if (
            expected["schema_version"] != 1
            or expected["artifact_kind"] != "PROMPT_EXPECTED_INPUT_DIGEST"
        ):
            raise GateError(f"evidence expected input {index} header is invalid")
        identity = (expected["task_id"], expected["sample_index"], expected["variant"])
        if identity != (row["task_id"], row["sample_index"], row["variant"]):
            raise GateError(f"evidence expected input {index} is out of row order")
        if identity in identities:
            raise GateError("evidence expected inputs repeat one row identity")
        identities.add(identity)
        measurement = row["measurement"]
        evaluation_input = row["evaluation_input"]
        generation = measurement["generation_request"]
        for name, actual in (
            ("rendered_prompt_sha256", measurement["rendered_prompt_sha256"]),
            ("context_sources_sha256", evaluation_input["context_sources_sha256"]),
            ("generation_request_sha256", evaluation_input["generation_request_sha256"]),
            ("adapter_request_sha256", evaluation_input["adapter_request_sha256"]),
            ("provider_request_sha256", generation["provider_request_sha256"]),
        ):
            if expected[name] != actual:
                raise GateError(f"evidence expected input {index} {name} does not match its row")

    policy = validate_acceptance_policy(result.get("acceptance_policy"))
    status, aggregates, corpus, reasons = rescore(result, policy)
    if reasons:
        raise GateError("recomputed scoring finds a serious regression the gate result omits")
    if status != "IMPROVED":
        raise GateError(f"recomputed acceptance decision is {status}, not IMPROVED")
    persisted_aggregates = result["task_aggregates"]
    if not isinstance(persisted_aggregates, list) or len(persisted_aggregates) != len(aggregates):
        raise GateError("persisted task aggregates do not cover every task")
    for persisted, computed in zip(persisted_aggregates, aggregates):
        exact_record(persisted, TASK_AGGREGATE_FIELDS, "task aggregate")
        if persisted != computed:
            raise GateError("persisted task aggregate disagrees with the recomputed value")
    persisted_corpus = result.get("corpus_aggregate")
    exact_record(persisted_corpus, CORPUS_AGGREGATE_FIELDS, "corpus aggregate")
    if persisted_corpus != corpus:
        raise GateError("persisted corpus aggregate disagrees with the recomputed value")

    provider_control = result.get("provider_control")
    if not isinstance(provider_control, dict):
        raise GateError("gate evaluation has no provider control")
    if provider_control.get("provider_kind") == "FIXTURE":
        raise GateError("gate evaluation used the FIXTURE provider")
    if len(result["tasks"]) < policy["minimum_task_count"]:
        raise GateError("gate evaluation task count is below the acceptance policy minimum")
    if result["sample_count"] < policy["minimum_samples_per_variant"]:
        raise GateError("gate evaluation sample count is below the acceptance policy minimum")
    return parent_digest, candidate_digest, scope_digest


def validate_chain(
    result: Mapping[str, Any],
    baseline: Mapping[str, Any],
    baseline_activation: Mapping[str, Any],
    accepted: Mapping[str, Any],
    accepted_activation: Mapping[str, Any],
    rollback: Mapping[str, Any],
    rollback_activation: Mapping[str, Any],
    parent_digest: str,
    candidate_digest: str,
    scope_digest: str,
) -> None:
    """Require the exact section 9 baseline -> accepted -> rolled-back lineage."""
    for label, activation in (
        ("baseline", baseline_activation),
        ("accepted", accepted_activation),
        ("rollback", rollback_activation),
    ):
        if activation["scope"]["content_sha256"] != scope_digest:
            raise GateError(f"{label} activation is bound to another scope")
    if baseline_activation["effective_variant"]["content_sha256"] != parent_digest:
        raise GateError("baseline activation does not carry the evaluated parent variant")
    if accepted_activation["effective_variant"]["content_sha256"] != candidate_digest:
        raise GateError("accepted activation does not carry the evaluated candidate variant")
    if rollback_activation["effective_variant"]["content_sha256"] != parent_digest:
        raise GateError("rollback activation does not restore the proven baseline variant")
    if (
        accepted_activation["parent_activation_id"] != baseline["decision_id"]
        or accepted_activation["parent_activation_sha256"] != baseline["content_sha256"]
    ):
        raise GateError("accepted activation parent is not the evaluated baseline")
    if (
        accepted_activation["accepted_evaluation_id"] != result["evaluation_id"]
        or accepted_activation["accepted_evaluation_sha256"] != result["content_sha256"]
    ):
        raise GateError("accepted activation does not name the improved evaluation")
    if (
        rollback_activation["parent_activation_id"] != accepted["decision_id"]
        or rollback_activation["parent_activation_sha256"] != accepted["content_sha256"]
    ):
        raise GateError("rollback activation parent is not the accepted activation")
    if (
        rollback_activation["rollback_target_activation_id"] != baseline["decision_id"]
        or rollback_activation["rollback_target_activation_sha256"] != baseline["content_sha256"]
    ):
        raise GateError("rollback activation target is not the proven baseline activation")
    if len({baseline["decision_id"], accepted["decision_id"], rollback["decision_id"]}) != 3:
        raise GateError("gate activations do not have three distinct decision identities")


# --- source-bundle revalidation ------------------------------------------------------


def validate_source_policy(
    path: Path, locator: Mapping[str, Any]
) -> dict[str, Any]:
    policy = load_object(path, POLICY_LIMIT, "source verifier policy")
    exact_record(policy, SOURCE_POLICY_FIELDS, "source verifier policy")
    if (
        policy["schema_version"] != 1
        or policy["artifact_kind"] != "PROMPT_SOURCE_VERIFIER_POLICY"
    ):
        raise GateError("source verifier policy header is invalid")
    require_identifier(policy["policy_id"], "source verifier policy id")
    claimed = require_own_digest(policy, "source verifier policy")
    if claimed != locator["source_verifier_policy_sha256"]:
        raise GateError("source verifier policy digest does not match the gate locator")
    if policy["helper_path"] != locator["source_verifier_relative_path"]:
        raise GateError("source verifier policy helper path does not match the gate locator")
    for policy_name, locator_name in (
        ("helper_sha256", "source_verifier_sha256"),
        ("helper_runtime", "source_verifier_runtime"),
        ("interpreter_sha256", "source_verifier_interpreter_sha256"),
        ("git_executable_sha256", "git_executable_sha256"),
    ):
        if policy[policy_name] != locator[locator_name]:
            raise GateError(f"source verifier policy {policy_name} does not match the gate locator")
    return policy


def gate_verifier_request(
    locator: Mapping[str, Any],
    trust: Mapping[str, Any],
    root: Path,
    tested_head: str,
    git_process_path: Path,
) -> dict[str, Any]:
    value = {
        "schema_version": 1,
        "artifact_kind": "PROMPT_SOURCE_VERIFIER_REQUEST",
        "mode": "GATE",
        "align_llm_repository_path": str(root / locator["align_llm_source_relative_path"]),
        "expected_align_llm_commit": trust["expected_align_llm_commit"],
        "tested_align_llm_head": tested_head,
        "align_repository_path": str(root / locator["align_source_relative_path"]),
        "expected_align_revision": trust["expected_align_revision"],
        "corpus_source_path": str(root / locator["corpus_source_relative_path"]),
        "corpus_source_kind": trust["expected_corpus_source_kind"],
        "corpus_file_set_manifest_path": (
            None
            if locator.get("corpus_file_set_manifest_relative_path") is None
            else str(root / locator["corpus_file_set_manifest_relative_path"])
        ),
        "expected_corpus_source_repository_id": trust["expected_corpus_source_repository_id"],
        "expected_corpus_source_sha256": trust["expected_corpus_source_sha256"],
        "git_executable_path": str(git_process_path),
        "git_executable_sha256": locator["git_executable_sha256"],
        "content_sha256": "",
    }
    if value["corpus_file_set_manifest_path"] is None:
        del value["corpus_file_set_manifest_path"]
    return bind_digest(value)


def derive_tested_head(git: GitTool, checkout: Path, raw_common: Path) -> str:
    git.verify_common_directory(checkout, raw_common, "CI checkout")
    status = git.run(
        checkout,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--ignore-submodules=all",
        label="CI checkout status",
    )
    if status:
        raise GateError("CI checkout is not clean")
    for arguments, expected, label in (
        (("rev-parse", "--is-inside-work-tree"), "true", "CI checkout work-tree probe"),
        (("rev-parse", "--is-shallow-repository"), "false", "CI checkout shallow probe"),
    ):
        observed = git.run(checkout, *arguments, label=label)
        if observed.decode("ascii", "replace").strip() != expected:
            raise GateError(f"{label} did not report {expected}")
    head = git.run(checkout, "rev-parse", "--verify", "HEAD", label="CI checkout head")
    try:
        text = head.decode("ascii", "strict").strip()
    except UnicodeError:
        raise GateError("CI checkout head is not ASCII") from None
    if HEX40.fullmatch(text) is None and HEX64.fullmatch(text) is None:
        raise GateError("CI checkout head is not a full lowercase commit")
    return text


def observe_source_bundle(
    locator: Mapping[str, Any],
    trust: Mapping[str, Any],
    root: Path,
    python: RetainedExecutable,
    git_tool: GitTool,
    checkout: Path,
) -> None:
    """Revalidate every locator target, then re-observe source identity through the helper."""
    align_llm_root = physical_directory(
        resolve_beneath(root, Path(locator["align_llm_source_relative_path"]), "align-llm source"),
        "align-llm source",
    )
    align_root = physical_directory(
        resolve_beneath(root, Path(locator["align_source_relative_path"]), "Align source"),
        "Align source",
    )
    corpus_root = physical_directory(
        resolve_beneath(root, Path(locator["corpus_source_relative_path"]), "corpus source"),
        "corpus source",
    )
    manifest_relative = locator.get("corpus_file_set_manifest_relative_path")
    if (manifest_relative is not None) != (trust["expected_corpus_source_kind"] == "FILE_SET"):
        raise GateError("gate locator file-set manifest pairing disagrees with the evidence trust")
    if manifest_relative is not None:
        physical_regular_file(
            resolve_beneath(root, Path(manifest_relative), "corpus file-set manifest"),
            "corpus file-set manifest",
        )
    policy_path = physical_regular_file(
        resolve_beneath(
            root, Path(locator["source_verifier_policy_relative_path"]), "source verifier policy"
        ),
        "source verifier policy",
    )
    helper_path = physical_regular_file(
        resolve_beneath(root, Path(locator["source_verifier_relative_path"]), "source verifier"),
        "source verifier",
    )
    validate_source_policy(policy_path, locator)
    if sha256_file(helper_path, "source verifier") != locator["source_verifier_sha256"]:
        raise GateError("source verifier helper digest does not match the gate locator")
    if python.sha256() != locator["source_verifier_interpreter_sha256"]:
        raise GateError("explicit Python executable digest does not match the gate locator")
    if git_tool.executable.sha256() != locator["git_executable_sha256"]:
        raise GateError("explicit Git executable digest does not match the gate locator")

    # Every Git checkout is raw-scanned before the first Git child runs anywhere.
    scans: list[tuple[Path, Path, str]] = []
    for repository_root, label in (
        (checkout, "CI checkout"),
        (align_llm_root, "source-bundle align-llm checkout"),
        (align_root, "source-bundle Align checkout"),
    ):
        scans.append((repository_root, scan_local_git_metadata(repository_root, label)[1], label))
    if trust["expected_corpus_source_kind"] == "GIT_COMMIT":
        scans.append(
            (
                corpus_root,
                scan_local_git_metadata(corpus_root, "source-bundle corpus checkout")[1],
                "source-bundle corpus checkout",
            )
        )

    tested_head = derive_tested_head(git_tool, checkout, scans[0][1])
    for repository_root, raw_common, label in scans[1:]:
        git_tool.verify_common_directory(repository_root, raw_common, label)

    request = gate_verifier_request(
        locator, trust, root, tested_head, git_tool.executable.process_path()
    )
    with tempfile.TemporaryDirectory(prefix="prompt-gate-source-") as directory:
        workspace = Path(directory)
        request_path = workspace / "request.json"
        request_path.write_bytes(canonical_bytes(request))
        result_path = workspace / "result.json"
        run_contained(
            [
                str(python.process_path()),
                str(helper_path),
                "--source-verifier-request",
                str(request_path),
                "--result",
                str(result_path),
            ],
            checkout,
            FIXED_GIT_ENVIRONMENT,
            (python.descriptor, git_tool.executable.descriptor),
            VERIFIER_TIMEOUT_SECONDS,
            "gate source verifier",
        )
        observed = load_object(result_path, POLICY_LIMIT, "source verifier result")
    exact_record(observed, SOURCE_RESULT_FIELDS, "source verifier result")
    require_own_digest(observed, "source verifier result")
    if observed["status"] != "COMPLETE" or observed["error_code"] != "NONE":
        raise GateError("gate source verification is unavailable")
    if observed["align_llm_reachability"] != "VERIFIED":
        raise GateError("source-bundle align-llm checkout is not VERIFIED")
    if observed["align_llm_observed_head"] != tested_head:
        raise GateError("source-bundle align-llm head does not equal the derived CI head")
    if observed["align_reachability"] != "VERIFIED":
        raise GateError("source-bundle Align checkout is not VERIFIED")
    if observed["align_observed_revision"] != trust["expected_align_revision"]:
        raise GateError("source-bundle Align revision disagrees with the evidence")
    if observed["corpus_reachability"] != "VERIFIED":
        raise GateError("source-bundle corpus is not VERIFIED")
    if observed["corpus_observed_source_sha256"] != trust["expected_corpus_source_sha256"]:
        raise GateError("source-bundle corpus identity disagrees with the evidence")

    git_tool.run(
        checkout,
        "merge-base",
        "--is-ancestor",
        trust["expected_align_llm_commit"],
        tested_head,
        label="evaluated-commit ancestry",
    )
    python.verify_unchanged(locator["source_verifier_interpreter_sha256"])
    git_tool.executable.verify_unchanged(locator["git_executable_sha256"])


# --- entry point ---------------------------------------------------------------------


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=True, description="Validate the C6 gate bundle.")
    parser.add_argument("--source-bundle-root", required=True)
    parser.add_argument("--python-executable-path", required=True)
    parser.add_argument("--git-executable-path", required=True)
    parser.add_argument("--generation-child-path", required=True)
    parser.add_argument("--generation-child-sha256", required=True)
    parser.add_argument("--gate-manifest", default=None)
    return parser.parse_args(arguments)


def admit_generation_child(path: Path, declared: str) -> None:
    """Admit the per-run generation child from its explicit pair alone.

    The child binary is built, not committed, so no corpus membership, locator entry, or frozen
    canonical asset can vouch for it. The descriptor is opened without following a symlink and the
    digest is read from that same descriptor, so the compared bytes are the ones the declared pair
    names; the validator never launches the child, so the descriptor is released once the declared
    digest is proven equal.
    """
    child = RetainedExecutable(path, "explicit generation child")
    try:
        if child.sha256() != declared:
            raise InputError(
                "explicit generation child bytes do not match --generation-child-sha256"
            )
    finally:
        child.close()


def validate(values: argparse.Namespace) -> None:
    checkout = Path.cwd()
    manifest_path = (
        checkout / GATE_MANIFEST_RELATIVE
        if values.gate_manifest is None
        else Path(values.gate_manifest)
    )
    root = require_explicit_absolute(values.source_bundle_root, "--source-bundle-root")
    python_path = require_explicit_absolute(
        values.python_executable_path, "--python-executable-path"
    )
    git_path = require_explicit_absolute(values.git_executable_path, "--git-executable-path")
    child_path = require_explicit_absolute(values.generation_child_path, "--generation-child-path")
    child_digest = require_explicit_digest(
        values.generation_child_sha256, "--generation-child-sha256"
    )
    # The fourth explicit pair is checked before any gate evidence identity is read.
    admit_generation_child(child_path, child_digest)
    python = RetainedExecutable(python_path, "explicit Python executable")
    try:
        git_executable = RetainedExecutable(git_path, "explicit Git executable")
        try:
            try:
                resolved_root = physical_directory(root, "--source-bundle-root")
            except GateError as error:
                raise InputError(str(error)) from None
            manifest = validate_manifest(
                load_object(manifest_path, MANIFEST_LIMIT, "gate manifest")
            )
            directory = manifest_path.parent
            baseline = load_referenced(
                directory, manifest["baseline_activation"], ACTIVATION_LIMIT, "baseline activation"
            )
            result = load_referenced(
                directory, manifest["improved_evaluation"], EVALUATION_LIMIT, "improved evaluation"
            )
            evidence = load_referenced(
                directory,
                manifest["improved_evaluation_evidence"],
                EVIDENCE_LIMIT,
                "improved evaluation evidence",
            )
            accepted = load_referenced(
                directory, manifest["accepted_activation"], ACTIVATION_LIMIT, "accepted activation"
            )
            rollback = load_referenced(
                directory, manifest["rollback_activation"], ACTIVATION_LIMIT, "rollback activation"
            )
            if manifest["improved_evaluation_evidence"]["artifact_id"] != manifest[
                "improved_evaluation"
            ]["artifact_id"]:
                raise GateError("gate manifest evidence reference names another evaluation")
            for name, artifact, identity in (
                ("baseline_activation", baseline, "decision_id"),
                ("accepted_activation", accepted, "decision_id"),
                ("rollback_activation", rollback, "decision_id"),
                ("improved_evaluation_evidence", evidence, "evaluation_id"),
            ):
                if manifest[name]["artifact_id"] != artifact.get(identity):
                    raise GateError(f"gate manifest {name} reference names another artifact")
            baseline_activation = validate_activation(baseline, "BASELINED", "baseline activation")
            accepted_activation = validate_activation(accepted, "ACCEPTED", "accepted activation")
            rollback_activation = validate_activation(
                rollback, "ROLLED_BACK", "rollback activation"
            )
            parent_digest, candidate_digest, scope_digest = validate_evaluation_pair(
                result, evidence
            )
            if manifest["improved_evaluation"]["artifact_id"] != result["evaluation_id"]:
                raise GateError("gate manifest evaluation reference names another evaluation")
            validate_chain(
                result,
                baseline,
                baseline_activation,
                accepted,
                accepted_activation,
                rollback,
                rollback_activation,
                parent_digest,
                candidate_digest,
                scope_digest,
            )
            observe_source_bundle(
                manifest["source_locator"],
                evidence["trust"],
                resolved_root,
                python,
                GitTool(git_executable),
                checkout,
            )
        finally:
            git_executable.close()
    finally:
        python.close()


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        values = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    except SystemExit:
        return 1
    try:
        validate(values)
    except GateCleanupError as error:
        print(f"prompt-gate-validator: cleanup: {error}", file=sys.stderr)
        return 3
    except InputError as error:
        print(f"prompt-gate-validator: input: {error}", file=sys.stderr)
        return 1
    except (GateError, OSError, KeyError, TypeError, IndexError) as error:
        print(f"prompt-gate-validator: rejected: {error}", file=sys.stderr)
        return 2
    print("prompt gate validator: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
