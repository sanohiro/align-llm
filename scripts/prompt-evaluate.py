#!/usr/bin/env python3
"""Deterministic C6 evaluator used by the Align command boundary."""

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
from typing import Any, Iterable, Mapping, Sequence


REQUEST_LIMIT = 65_536
ARTIFACT_LIMIT = 2_097_152
MEASUREMENT_LIMIT = 262_144
SNAPSHOT_LIMIT = 1_048_576
SNAPSHOT_ARTIFACT_LIMIT = 1_073_741_824
RESULT_LIMIT = 268_435_456
EVIDENCE_LIMIT = 8_388_608
CHILD_CLEANUP_MARGIN_NS = 5_000_000_000
SNAPSHOT_HELPER_OUTER_TIMEOUT_NS = 35_000_000_000
SOURCE_VERIFIER_OUTER_TIMEOUT_NS = 125_000_000_000
CANONICAL_STRING_CHUNK = 16_384
CONTEXT_SECTION_LIMIT = 65_536
LEARNED_APPEND_LIMIT = 8_192
MEMORY_JSONL_LIMIT = 1_048_576
CONTEXT_TRUNCATION_MARKER = b"\n[context truncated]"
DIAGNOSTIC_TRUNCATION_MARKER = b"\n[output truncated]"
MEMORY_EVENT_TEXT_FIELDS = (
    "root", "task_id", "attempted_patch", "final_status", "failure_stage", "failed_test",
    "failure_status", "root_cause", "repair_result", "successful_strategy",
    "unsuccessful_strategy", "recommended_tests", "risky_symbols",
)
MEMORY_EVENT_INTEGER_FIELDS = (
    "schema_version", "iteration_count", "repair_count", "risk_score",
)
MEMORY_EVENT_FIELDS = frozenset(MEMORY_EVENT_TEXT_FIELDS + MEMORY_EVENT_INTEGER_FIELDS)
PROVIDER_KINDS = ("CLOUD_OPENAI", "LOCAL_OPENAI", "LLAMA_CPP", "FIXTURE")
CREDENTIAL_PROVIDER_KINDS = ("CLOUD_OPENAI", "LOCAL_OPENAI")
HEX = frozenset("0123456789abcdef")
SOURCE_POLICY_FIELDS = (
    "schema_version", "artifact_kind", "policy_id", "helper_path", "helper_sha256",
    "helper_runtime", "interpreter_sha256", "git_executable_sha256", "content_sha256",
)
SOURCE_RESULT_FIELDS = (
    "schema_version", "artifact_kind", "status", "error_code", "error",
    "align_llm_reachability", "align_llm_observed_head", "align_reachability",
    "align_observed_revision", "corpus_reachability", "corpus_observed_source_sha256",
    "content_sha256",
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
    "verifier_git_executable_path", "evaluation_evidence_path", "generation_child_path",
    "generation_child_sha256",
)
EVALUATE_REQUEST_FIELDS_OMITTED = tuple(
    name for name in EVALUATE_REQUEST_FIELDS if name != "verifier_corpus_file_set_manifest_path"
)
PR_SET_CHILD_SUBREAPER = 36
ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
FIXED_ADAPTER_PATH = "scripts/prompt-fixed-adapter.py"
FIXED_SNAPSHOT_HELPER_PATH = "scripts/prompt-snapshot-helper.py"
ENVIRONMENT_PROBE_FIELDS = (
    "schema_version", "artifact_kind", "producer", "os", "os_release", "architecture",
    "cpu", "logical_cpu_count", "gpu", "runtime_identity", "content_sha256",
)
ARTIFACT_DIGEST_FIELDS = ("path", "mode", "byte_count", "sha256")
SNAPSHOT_RESULT_FIELDS = (
    "schema_version", "artifact_kind", "task_id", "status", "error_code", "error",
    "environment_probe", "artifact_digests", "content_sha256",
)
WORKSPACE_PREFLIGHT_RESULT_FIELDS = (
    "schema_version", "artifact_kind", "evaluation_id", "status", "error_code", "error",
    "physical_project_root", "physical_workspace_path", "environment_probe", "content_sha256",
)
TASK_MEASUREMENT_FIELDS = (
    "schema_version", "artifact_kind", "status", "failure_kind", "build_status", "test_status",
    "repair_loop_count", "unrelated_diff_count", "patch_size_bytes", "public_api_change_count",
    "policy_violation_count", "cleanup_passed", "containment_passed", "benchmark_regression_ppm",
    "generation_to_passing_patch_ns", "rendered_prompt_sha256", "generation_request",
    "environment_probe", "seed_attestation", "diagnostic_summary", "diagnostic_stdout",
    "diagnostic_stderr", "content_sha256",
)
# C4-REPAIR-EDITSET. `TASK_MEASUREMENT` version 2 appends four members immediately before
# `content_sha256`, which is the position the canonical encoder and every existing consumer already
# tolerate. Version 1 is unchanged and permanently decodable: the two tuples are selected by the
# document's own `schema_version`, never by which keys happen to be present.
TASK_MEASUREMENT_V2_MEMBERS = (
    "edit_set", "edit_set_total_bytes", "patch_sha256", "base_adapter_runtime_identity",
)
TASK_MEASUREMENT_V2_FIELDS = (
    TASK_MEASUREMENT_FIELDS[:-1] + TASK_MEASUREMENT_V2_MEMBERS + ("content_sha256",)
)
EDIT_SET_BLOCK_FIELDS = (
    "schema_version", "artifact_kind", "path", "body_bytes", "body_sha256", "body_text",
    "content_sha256",
)
# The corpus selects the adapter, so the measurement version is a checked function of the corpus
# rather than a value a producer may choose (spec section 3.5, ladder row 11). The task manifest's
# `measurement_adapter_runtime` pins this file's digest and the evaluator re-verifies it against the
# retained helper before the invocation; the path below is the selector that digest pins.
REPAIR_ADAPTER_RELATIVE = "scripts/prompt-repair-adapter.py"
GENERATION_REQUEST_FIELDS = (
    "schema_version", "artifact_kind", "rendered_prompt_sha256", "system_text_sha256",
    "user_text_sha256", "generation_policy_sha256", "provider_control_sha256",
    "environment_policy_sha256", "max_tokens", "temperature_micros", "paired_seed",
    "provider_request_sha256", "seed_attestation_sha256", "content_sha256",
)
SEED_ATTESTATION_FIELDS = (
    "schema_version", "artifact_kind", "provider_kind", "provider_model", "requested_seed",
    "result", "applied_seed", "provider_request_sha256", "content_sha256",
)
PROMPT_TEXT_FIELDS = ("schema_version", "artifact_kind", "artifact_id", "text", "content_sha256")
ARTIFACT_REFERENCE_FIELDS = ("artifact_kind", "path", "artifact_id", "content_sha256")
CONTEXT_POLICY_FIELDS = (
    "include_patch_evaluation", "include_failure_memory", "include_diagnostics",
    "max_patch_evaluation_bytes", "max_failure_events", "max_failure_context_bytes",
    "max_diagnostic_bytes_per_stream",
)
PROMPT_VARIANT_FIELDS = (
    "schema_version", "artifact_kind", "variant_id", "base_prompt", "repo_prompt",
    "learned_prompt_append", "context_policy", "candidate_id", "content_sha256",
)
CORPUS_REVISION_FIELDS = (
    "schema_version", "artifact_kind", "source_kind", "source_repository_id", "source_sha256",
    "content_sha256",
)
PROMPT_SCOPE_FIELDS = (
    "schema_version", "artifact_kind", "repo_id", "repo_profile_revision", "align_revision",
    "corpus_id", "corpus_revision", "evaluation_provider_kind", "evaluation_provider_model",
    "generation_policy_sha256", "acceptance_policy_sha256", "base_prompt_sha256",
    "repo_prompt_sha256", "content_sha256",
)
PROMPT_EXPERIMENT_FIELDS = (
    "schema_version", "artifact_kind", "experiment_id", "status", "error_code", "error",
    "parent_activation", "scope", "opportunity", "proposal_provider_kind",
    "proposal_provider_endpoint_id", "proposal_provider_model", "proposal_elapsed_ns",
    "proposal_status_code", "proposal_summary", "candidate_variant", "bounded_provider_output",
    "content_sha256",
)
PROMPT_ACTIVATION_FIELDS = (
    "schema_version", "artifact_kind", "activation_id", "operation", "scope",
    "parent_activation_id", "parent_activation_sha256", "effective_variant",
    "accepted_evaluation_id", "accepted_evaluation_sha256", "rollback_target_activation_id",
    "rollback_target_activation_sha256", "decision_reason", "content_sha256",
)
PROMPT_ACTIVATION_RESULT_FIELDS = (
    "schema_version", "artifact_kind", "decision_id", "status", "error_code", "error",
    "activation", "content_sha256",
)
PROMPT_CORPUS_FIELDS = (
    "schema_version", "artifact_kind", "corpus_id", "corpus_revision", "task_files",
    "content_sha256",
)
ARTIFACT_EXPECTATION_FIELDS = ("path", "kind", "expected_sha256")
REGRESSION_LIMIT_FIELDS = (
    "maximum_unrelated_diff_count", "maximum_patch_size_bytes", "maximum_public_api_change_count",
    "maximum_repair_loops", "maximum_benchmark_regression_ppm",
)
PROMPT_TASK_FIELDS = (
    "schema_version", "artifact_kind", "task_id", "repo_id", "repo_revision", "repo_path",
    "require_clean_repo", "cmd", "argv", "snapshot_cmd", "snapshot_argv",
    "measurement_adapter_runtime", "snapshot_helper_runtime", "cwd", "timeout_ns",
    "task_prompt_path", "context_sources_path", "generation_policy_path", "provider_control_path",
    "environment_policy_path", "validation_runner_path", "validation_runner_sha256",
    "task_definition_path", "task_definition_sha256", "validation_argv", "patch_path",
    "patch_sha256", "artifacts", "regression_limits",
    # The repair-template pair is `Option::None` for every schema-1 corpus written before
    # `docs/specs/c4-repair-measured.md`, and the canonical encoding omits a `None`, so the three
    # frozen `eval/tasks/prompt-v1/*.json` manifests keep their exact bytes and their exact
    # `content_sha256`. A task that declares `maximum_repair_loops >= 1` must declare the pair.
    "repair_template_path", "repair_template_sha256",
    "content_sha256",
)
ACCEPTANCE_POLICY_FIELDS = (
    "schema_version", "artifact_kind", "policy_id", "minimum_task_count",
    "minimum_samples_per_variant", "minimum_completion_gain_count", "minimum_time_improvement_ppm",
    "maximum_time_regression_ppm", "maximum_repair_loop_regression_count", "content_sha256",
)
WORKSPACE_PREFLIGHT_REQUEST_FIELDS = (
    "schema_version", "artifact_kind", "evaluation_id", "project_root", "workspace_path",
    "content_sha256",
)
GENERATION_POLICY_FIELDS = (
    "schema_version", "artifact_kind", "generation_policy_id", "evaluation_provider_kind",
    "evaluation_provider_endpoint_id", "evaluation_provider_model", "provider_control_sha256",
    "provider_service_revision", "max_prompt_bytes", "max_tokens", "temperature_micros",
    "seed_mode", "seed_base", "content_sha256",
)
PROVIDER_CONTROL_FIELDS = (
    "schema_version", "artifact_kind", "provider_control_id", "provider_kind", "endpoint",
    "endpoint_id", "model", "api_key_env", "tokenize_endpoint", "timeout_ns",
    "max_response_bytes", "content_sha256",
)
ENVIRONMENT_POLICY_FIELDS = (
    "schema_version", "artifact_kind", "policy_id", "allowed_variables", "executable_paths",
    "locale", "content_sha256",
)
CONTEXT_SOURCES_FIELDS = (
    "schema_version", "artifact_kind", "task_id", "patch_evaluation", "failure_memory_jsonl",
    "diagnostic_stdout", "diagnostic_stderr", "content_sha256",
)
# --- C4-REPAIR-MEASURED: the bounded second attempt ---------------------------------------------
# `docs/specs/c4-repair-measured.md` owns this contract. The evaluator, not the byte-frozen
# measurement adapter, owns the attempt loop, because the repair prompt is a function of attempt
# one's realized output and the evaluator is the sole owner of rendering, sealing, and
# expected-input identity (spec sections 2.4 and 3.1).
REPAIR_TEMPLATE_FIELDS = (
    "schema_version", "artifact_kind", "template_id", "preamble_text", "section_headers",
    "closing_text", "content_sha256",
)
# C4-REPAIR-EDITSET adds `EDITSET` immediately after `STATUS`, so the model reads the verdict and
# then what produced it, before the output describing it. The four earlier kinds keep their relative
# order, so a version-2 prompt with `EDITSET` absent has the same section sequence as a
# `canonical-v1r` prompt.
REPAIR_SECTION_KINDS = ("STATUS", "EDITSET", "SUMMARY", "STDOUT", "STDERR")
# The kind set a `canonical-v1r` template declares. It stays admissible, and that is a decision:
# `eval/prompt/c4-repair-gate/` was measured against that corpus's exact scope digest, and making
# its sealed template undecodable would leave a merged evidence chain naming a corpus that can no
# longer be run. Which set a task's template must declare is ladder row 8, and it is selected the
# same way ladder row 11 selects the measurement version: by the adapter the corpus names. A task
# running the repair adapter must declare all five kinds; any other task must declare exactly the
# four it always did. A template is never "upgraded" by inference.
REPAIR_SECTION_KINDS_V1 = ("STATUS", "SUMMARY", "STDOUT", "STDERR")
# Fixed drop precedence (spec section 4.4). `STATUS` is never dropped: it is at most
# REPAIR_STATUS_LIMIT bytes and it is the single most load-bearing fact in the prompt. Dropping is
# whole-section, never a byte cut, so this capability never splits a UTF-8 code point.
#
# `EDITSET` is dropped **last**, and that is a decision argued from the C4-REPAIR-MEASURED failure
# modes rather than from tidiness. That run measured what a repair prompt carrying only the
# diagnostics achieves on this corpus: zero recoveries in ten attempts, with six of six attempts
# that had produced a validated edit set re-emitting a patch of exactly the same byte count.
# Dropping `EDITSET` early would make an over-budget row silently degrade into the experiment that
# already returned a negative. It is nevertheless droppable rather than joining `STATUS`, because it
# is the only section that can blow the budget by itself — up to `MAXIMUM_FILE_BLOCKS` blocks
# against four fixed-size streams — and losing a measurement to
# `SKIPPED`/`REPAIR_PROMPT_BUDGET` is worse than making one under a degraded prompt, provided the
# degradation is recorded. `repair_prompt_source.dropped_sections` and
# `repair_editset_attempt_count` are that record.
REPAIR_DROP_ORDER = ("STDOUT", "STDERR", "SUMMARY", "EDITSET")
# Producer-side, whole-block, applied in `scripts/prompt-repair-adapter.py`. Declared here too
# because the evaluator's rendered section can never exceed what the producer persisted, and a
# section source that did would be a producer defect this bound makes visible.
EDIT_SET_LIMIT = 16_384
# The frozen adapter's own edit-set bounds, restated so a persisted `edit_set` is checked against
# the same ceilings `validated_edit_set` enforced before the block was ever kept.
MAXIMUM_FILE_BLOCKS = 32
MAXIMUM_EDIT_BYTES = 262_144
REPAIR_STATUS_LIMIT = 128
REPAIR_TEMPLATE_TEXT_LIMIT = 16_384
REPAIR_SECTION_HEADER_LIMIT = 256
# One repair attempt, so at most two attempts per row. The corpus manifest carries the real cap in
# `regression_limits.maximum_repair_loops`; this is the structural ceiling this capability admits.
MAXIMUM_REPAIR_ATTEMPTS = 1
ATTEMPT_RECORD_FIELDS = (
    "schema_version", "artifact_kind", "attempt_index", "attempt_kind", "status", "skip_reason",
    "rendered_prompt_sha256", "repair_prompt_source", "adapter_request_sha256",
    # Each attempt is its own contained invocation with its own sealed prompt, so it produces its
    # own snapshot request, its own before/after snapshot results, and its own input snapshot.
    # The row-level `snapshot_attestations` array stays exactly one record per row — the schedule
    # check binds it positionally to rows — so these four digests are what keep every trace record
    # bound to the invocation that produced it once a row can run twice.
    "snapshot_request_sha256", "before_snapshot_result_sha256", "after_snapshot_result_sha256",
    "input_snapshot_sha256",
    "generation_request", "seed_attestation", "paired_seed", "measurement",
    "repair_preparation_ns", "adapter_elapsed_ns", "adapter_overhead_ns", "measurement_sha256",
    "content_sha256",
)
REPAIR_PROMPT_SOURCE_FIELDS = (
    "schema_version", "artifact_kind", "template_sha256", "source_attempt_index",
    "source_measurement_sha256", "included_sections", "dropped_sections", "assembled_bytes",
    "content_sha256",
)
PROVIDER_SERVICE_PROBE_FIELDS = (
    "schema_version", "artifact_kind", "provider_service_revision", "server_version_string",
    "server_binary_sha256", "model_sha256", "content_sha256",
)
SKIP_REASONS = (
    "NONE", "REPAIR_PROMPT_BUDGET", "REPAIR_NOT_ELIGIBLE", "REPAIR_INPUT_UNAVAILABLE",
)
INPUT_ARTIFACT_FIELDS = {
    "PROMPT_EXPERIMENT_RESULT": PROMPT_EXPERIMENT_FIELDS,
    "PROMPT_ACTIVATION_RESULT": PROMPT_ACTIVATION_RESULT_FIELDS,
    "PROMPT_EVALUATION_CORPUS": PROMPT_CORPUS_FIELDS,
    "PROMPT_ACCEPTANCE_POLICY": ACCEPTANCE_POLICY_FIELDS,
    "WORKSPACE_PREFLIGHT_REQUEST": WORKSPACE_PREFLIGHT_REQUEST_FIELDS,
    "PROMPT_EVALUATION_TASK": PROMPT_TASK_FIELDS,
    "GENERATION_POLICY": GENERATION_POLICY_FIELDS,
    "EVALUATION_PROVIDER_CONTROL": PROVIDER_CONTROL_FIELDS,
    "ENVIRONMENT_POLICY": ENVIRONMENT_POLICY_FIELDS,
    "TASK_PROMPT": PROMPT_TEXT_FIELDS,
    "CONTEXT_SOURCES": CONTEXT_SOURCES_FIELDS,
    "PROMPT_SOURCE_VERIFIER_POLICY": SOURCE_POLICY_FIELDS,
}
# The canonical encoding omits an `Option::None`, exactly as the evaluate request's own
# `EVALUATE_REQUEST_FIELDS_OMITTED` already allows. A `PROPOSED` experiment result therefore
# never carries `proposal_status_code`, which is `Some` only for `PROVIDER_HTTP_STATUS`, so the
# input boundary must accept both the canonical omitted form and an explicit `null`.
INPUT_ARTIFACT_OPTIONAL = {
    "PROMPT_EXPERIMENT_RESULT": frozenset({"proposal_status_code"}),
    # A schema-1 task manifest written before C4-REPAIR-MEASURED omits the repair-template pair
    # entirely, which is the canonical encoding of `Option::None` and leaves its digest unchanged.
    "PROMPT_EVALUATION_TASK": frozenset({"repair_template_path", "repair_template_sha256"}),
}


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


class EvaluationError(ValueError):
    """A declared evaluation input or trusted child result is invalid."""


class ChildBoundaryError(EvaluationError):
    """A trusted child crossed a process timeout, capture, or execution boundary."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AbortEvaluation(Exception):
    """Carry a fully assembled terminal result out of one attempt without unwinding by hand.

    An attempt is now one of up to two invocations inside a row, so the abort paths that used to
    `return finish(...)` directly from the row body must cross a function boundary. The result is
    built at the raise site, exactly as before, so the rows, attestations, and checkpoint it
    captures are the ones observed at that instant.
    """

    def __init__(
        self,
        result: dict[str, Any],
        checkpoint: tuple[int, int, int, int, int, int] | None = None,
        cleanup_diagnosed: bool = False,
    ) -> None:
        super().__init__(result.get("error", ""))
        self.result = result
        self.checkpoint = checkpoint
        self.cleanup_diagnosed = cleanup_diagnosed


class AdapterFailure(EvaluationError):
    """A validated adapter invocation failed after its input identity was established."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


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

    def read_bytes(self) -> bytes:
        output = bytearray()
        offset = 0
        while offset < self.identity[3]:
            chunk = os.pread(self.descriptor, min(1_048_576, self.identity[3] - offset), offset)
            if not chunk:
                raise EvaluationError("declared source changed while reading")
            output.extend(chunk)
            offset += len(chunk)
        return bytes(output)

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


def zombie_without_live_task(status_lines: list[str]) -> bool:
    """Report whether `/proc/PID/status` text describes a fully terminated entry.

    A `State: Z` thread-group leader whose group still holds another task is a
    live process: its leader thread exited, but a worker thread keeps running
    under the zombie leader and can still act. Only `Threads: 1` proves that no
    task in the group can execute again. A missing or malformed
    `State:`/`Threads:` line fails closed and reports the entry as live.
    """
    try:
        state = next(line for line in status_lines if line.startswith("State:")).split()[1]
        tasks = int(next(line for line in status_lines if line.startswith("Threads:")).split()[1])
    except (IndexError, StopIteration, ValueError):
        return False
    return state == "Z" and tasks == 1


def descendant_process_ids(root_pids: set[int]) -> set[int]:
    """Return the live descendants of `root_pids` from the /proc parent links.

    An entry is omitted only when it has fully terminated: `State: Z` with
    `Threads: 1`, a zombie thread-group leader whose group holds no other task.
    It keeps a process-table slot until someone waits for it and can never
    execute again, so it cannot escape containment. Under
    `PR_SET_CHILD_SUBREAPER` an adopted orphan that has already exited becomes a
    permanent zombie child of this process, and counting it would report a
    containment failure for a process that no longer runs. A zombie leader whose
    group still holds a live worker thread is a running process and is reported.
    Terminated entries are still traversed, so a live entry parented to one is
    still reported.

    The two parse failures are deliberately asymmetric. An entry that exits
    between the directory scan and the status read, or whose `PPid:` line is
    absent or malformed, is dropped by the shared `OSError`/`IndexError` path
    exactly as a vanished process is. That arm fails open for a single
    unparseable entry, a tradeoff consciously accepted for parse robustness
    because without a parent link the entry cannot be placed in the tree at all.
    A missing or malformed `State:`/`Threads:` line instead fails closed and
    reports the entry, because its parent link is already known and only the
    justification for skipping it is missing.
    """
    parents: dict[int, list[int]] = {}
    terminated: set[int] = set()
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
        except (IndexError, OSError, StopIteration, ValueError):
            continue
        if zombie_without_live_task(status_lines):
            terminated.add(pid)
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
                if child not in terminated:
                    descendants.add(child)
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


def owned_descendant_ids(process: subprocess.Popen[bytes] | None = None) -> set[int]:
    roots = {os.getpid()}
    if process is not None:
        roots.add(process.pid)
    descendants = descendant_process_ids(roots)
    descendants.discard(os.getpid())
    if process is not None:
        descendants.discard(process.pid)
    return descendants


def cleanup_process_group(process: subprocess.Popen[bytes], maximum_seconds: float = 2.0) -> bool:
    """Kill the private group plus nested-session descendants and prove absence."""

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
        owned.update(adopted)
        reap_process_ids(adopted, 0.05)
        time.sleep(0.01)
    return complete and not process_group_exists(process.pid) and not owned_descendant_ids()


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


def exact_record(value: Any, fields: tuple[str, ...], kind: str | None = None) -> bool:
    return (
        isinstance(value, dict)
        and tuple(value) == fields
        and (kind is None or value.get("schema_version") == 1 and value.get("artifact_kind") == kind)
    )


def record_digest_valid(value: Mapping[str, Any]) -> bool:
    return valid_hex(value.get("content_sha256")) and canonical_digest(
        {**value, "content_sha256": ""},
    ) == value["content_sha256"]


def bounded_text(value: Any, maximum: int, *, empty: bool = False) -> bool:
    return (
        isinstance(value, str) and "\0" not in value
        and (empty or bool(value)) and len(value.encode("utf-8")) <= maximum
    )


def bounded_integer(value: Any, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def prompt_text_valid(value: Any, kind: str) -> bool:
    return (
        exact_record(value, PROMPT_TEXT_FIELDS, kind)
        and valid_ascii_identifier(value.get("artifact_id"))
        and bounded_text(value.get("text"), ARTIFACT_LIMIT, empty=True)
        and record_digest_valid(value)
    )


def reference_valid(value: Any, kind: str) -> bool:
    return (
        exact_record(value, ARTIFACT_REFERENCE_FIELDS)
        and value.get("artifact_kind") == kind
        and bounded_text(value.get("path"), 4096)
        and valid_ascii_identifier(value.get("artifact_id"))
        and valid_hex(value.get("content_sha256"))
    )


def context_policy_valid(value: Any) -> bool:
    return (
        exact_record(value, CONTEXT_POLICY_FIELDS)
        and all(isinstance(value.get(name), bool) for name in (
            "include_patch_evaluation", "include_failure_memory", "include_diagnostics",
        ))
        and all(bounded_integer(value.get(name), 0, ARTIFACT_LIMIT) for name in (
            "max_patch_evaluation_bytes", "max_failure_context_bytes", "max_diagnostic_bytes_per_stream",
        ))
        and bounded_integer(value.get("max_failure_events"), 0, 1_048_576)
    )


def variant_valid(value: Any) -> bool:
    return (
        exact_record(value, PROMPT_VARIANT_FIELDS, "PROMPT_VARIANT")
        and valid_ascii_identifier(value.get("variant_id"))
        and prompt_text_valid(value.get("base_prompt"), "BASE_PROMPT")
        and prompt_text_valid(value.get("repo_prompt"), "REPO_PROMPT")
        and bounded_text(value.get("learned_prompt_append"), ARTIFACT_LIMIT, empty=True)
        and context_policy_valid(value.get("context_policy"))
        and valid_ascii_identifier(value.get("candidate_id"), allow_empty=True)
        and record_digest_valid(value)
    )


def corpus_revision_valid(value: Any) -> bool:
    return (
        exact_record(value, CORPUS_REVISION_FIELDS, "CORPUS_REVISION")
        and value.get("source_kind") in ("GIT_COMMIT", "FILE_SET")
        and isinstance(value.get("source_repository_id"), str)
        and valid_hex(value.get("source_sha256"), (40, 64))
        and record_digest_valid(value)
    )


def scope_valid(value: Any) -> bool:
    return (
        exact_record(value, PROMPT_SCOPE_FIELDS, "PROMPT_SCOPE")
        and all(valid_ascii_identifier(value.get(name)) for name in (
            "repo_id", "repo_profile_revision", "corpus_id",
        ))
        and valid_hex(value.get("align_revision"), (40, 64))
        and corpus_revision_valid(value.get("corpus_revision"))
        and all(bounded_text(value.get(name), 256) for name in (
            "evaluation_provider_kind", "evaluation_provider_model",
        ))
        and all(valid_hex(value.get(name)) for name in (
            "generation_policy_sha256", "acceptance_policy_sha256", "base_prompt_sha256",
            "repo_prompt_sha256", "content_sha256",
        ))
        and record_digest_valid(value)
    )


def activation_valid(value: Any) -> bool:
    return (
        exact_record(value, PROMPT_ACTIVATION_FIELDS, "PROMPT_ACTIVATION")
        and valid_ascii_identifier(value.get("activation_id"))
        and value.get("operation") in ("BASELINE", "ACCEPT", "ROLLBACK")
        and scope_valid(value.get("scope"))
        and variant_valid(value.get("effective_variant"))
        and all(isinstance(value.get(name), str) for name in (
            "parent_activation_id", "parent_activation_sha256", "accepted_evaluation_id",
            "accepted_evaluation_sha256", "rollback_target_activation_id",
            "rollback_target_activation_sha256", "decision_reason",
        ))
        and record_digest_valid(value)
    )


def artifact_expectations_valid(value: Any) -> bool:
    return (
        isinstance(value, list) and 1 <= len(value) <= 64
        and all(
            exact_record(item, ARTIFACT_EXPECTATION_FIELDS)
            and bounded_text(item.get("path"), 4096)
            and item.get("kind") in ("FILE", "TREE")
            and valid_hex(item.get("expected_sha256"))
            for item in value
        )
    )


def declared_shape(value: Any, fields: tuple[str, ...], optional: frozenset[str]) -> bool:
    """Fields in declared order, minus canonically omitted `Option::None` members."""
    if not isinstance(value, dict):
        return False
    actual = tuple(value)
    cursor = 0
    for name in fields:
        if cursor < len(actual) and actual[cursor] == name:
            cursor += 1
        elif name not in optional:
            return False
    return cursor == len(actual)


def validate_input_artifact_shape(kind: str, value: Mapping[str, Any]) -> None:
    fields = INPUT_ARTIFACT_FIELDS.get(kind)
    if fields is None:
        return
    optional = INPUT_ARTIFACT_OPTIONAL.get(kind, frozenset())
    shaped = (
        exact_record(value, fields, kind) if not optional
        else declared_shape(value, fields, optional)
        and value.get("schema_version") == 1 and value.get("artifact_kind") == kind
    )
    if not shaped or not record_digest_valid(value):
        raise EvaluationError(f"{kind} schema is invalid")
    valid = True
    if kind == "PROMPT_EXPERIMENT_RESULT":
        valid = (
            valid_ascii_identifier(value.get("experiment_id"))
            and value.get("status") == "PROPOSED" and value.get("error_code") == "NONE"
            and value.get("error") == "" and reference_valid(value.get("parent_activation"), "PROMPT_ACTIVATION_RESULT")
            and scope_valid(value.get("scope")) and reference_valid(value.get("opportunity"), "OPPORTUNITY")
            and all(bounded_text(value.get(name), 256) for name in (
                "proposal_provider_kind", "proposal_provider_endpoint_id", "proposal_provider_model",
            ))
            and bounded_integer(value.get("proposal_elapsed_ns"), 0, 7_200_000_000_000)
            and value.get("proposal_status_code") is None
            and bounded_text(value.get("proposal_summary"), 4096, empty=True)
            and variant_valid(value.get("candidate_variant"))
            and bounded_text(value.get("bounded_provider_output"), ARTIFACT_LIMIT, empty=True)
        )
    elif kind == "PROMPT_ACTIVATION_RESULT":
        valid = (
            valid_ascii_identifier(value.get("decision_id")) and value.get("status") == "BASELINED"
            and value.get("error_code") == "NONE" and value.get("error") == ""
            and activation_valid(value.get("activation"))
        )
    elif kind == "PROMPT_EVALUATION_CORPUS":
        valid = (
            valid_ascii_identifier(value.get("corpus_id"))
            and corpus_revision_valid(value.get("corpus_revision"))
            and isinstance(value.get("task_files"), list)
            and 1 <= len(value["task_files"]) <= 64
            and all(bounded_text(item, 4096) for item in value["task_files"])
        )
    elif kind == "PROMPT_ACCEPTANCE_POLICY":
        valid = (
            valid_ascii_identifier(value.get("policy_id"))
            and bounded_integer(value.get("minimum_task_count"), 1, 64)
            and bounded_integer(value.get("minimum_samples_per_variant"), 2, 16)
            and bounded_integer(value.get("minimum_completion_gain_count"), 1, 1024)
            and bounded_integer(value.get("minimum_time_improvement_ppm"), 1, 1_000_000)
            and bounded_integer(value.get("maximum_time_regression_ppm"), 0, 1_000_000)
            and bounded_integer(value.get("maximum_repair_loop_regression_count"), 0, 65_536)
        )
    elif kind == "WORKSPACE_PREFLIGHT_REQUEST":
        valid = (
            valid_ascii_identifier(value.get("evaluation_id"))
            and bounded_text(value.get("project_root"), 4096)
            and bounded_text(value.get("workspace_path"), 4096)
        )
    elif kind == "PROMPT_EVALUATION_TASK":
        limits = value.get("regression_limits")
        valid = (
            valid_ascii_identifier(value.get("task_id")) and valid_ascii_identifier(value.get("repo_id"))
            and valid_hex(value.get("repo_revision"), (40, 64)) and bounded_text(value.get("repo_path"), 4096)
            and isinstance(value.get("require_clean_repo"), bool)
            and all(bounded_text(value.get(name), 4096) for name in (
                "cmd", "snapshot_cmd", "cwd", "task_prompt_path", "context_sources_path",
                "generation_policy_path", "provider_control_path", "environment_policy_path",
            ))
            and all(bounded_text(value.get(name), 256) for name in (
                "measurement_adapter_runtime", "snapshot_helper_runtime",
            ))
            and bounded_integer(value.get("timeout_ns"), 1, 7_200_000_000_000)
            and all(bounded_text(value.get(name), 4096) for name in (
                "validation_runner_path", "task_definition_path",
            ))
            and all(valid_hex(value.get(name)) for name in (
                "validation_runner_sha256", "task_definition_sha256",
            ))
            and isinstance(value.get("validation_argv"), list)
            and bool(value.get("validation_argv"))
            and all(
                isinstance(item, str) and 0 < len(item.encode("utf-8")) <= 4096
                for item in value.get("validation_argv")
            )
            # The `Option` pair is `None` for a provider-backed task whose patch comes from the
            # generation response and `Some` only for a deterministic fixture-style task.
            and (value.get("patch_path") is None) == (value.get("patch_sha256") is None)
            and (
                value.get("patch_path") is None
                or (bounded_text(value.get("patch_path"), 4096) and valid_hex(value.get("patch_sha256")))
            )
            and artifact_expectations_valid(value.get("artifacts"))
            and exact_record(limits, REGRESSION_LIMIT_FIELDS)
            and bounded_integer(limits.get("maximum_unrelated_diff_count"), 0, 1_048_576)
            and bounded_integer(limits.get("maximum_patch_size_bytes"), 0, 67_108_864)
            and bounded_integer(limits.get("maximum_public_api_change_count"), 0, 1_048_576)
            and bounded_integer(limits.get("maximum_repair_loops"), 0, 64)
            and (limits.get("maximum_benchmark_regression_ppm") is None or bounded_integer(
                limits.get("maximum_benchmark_regression_ppm"), 0, 1_000_000,
            ))
            # Ladder row 4: this capability admits exactly zero or one repair loop. A larger value
            # would be headroom no code path reaches and no test exercises, so it is rejected here
            # rather than silently permitted up to the structural ceiling of 64.
            and limits.get("maximum_repair_loops") <= MAXIMUM_REPAIR_ATTEMPTS
            # The pair is present exactly when the task offers a repair attempt.
            and (value.get("repair_template_path") is None) == (value.get("repair_template_sha256") is None)
            and (limits.get("maximum_repair_loops") >= 1) == (value.get("repair_template_path") is not None)
            and (
                value.get("repair_template_path") is None
                or (
                    bounded_text(value.get("repair_template_path"), 4096)
                    and valid_hex(value.get("repair_template_sha256"))
                )
            )
        )
    elif kind == "GENERATION_POLICY":
        valid = (
            valid_ascii_identifier(value.get("generation_policy_id"))
            and all(bounded_text(value.get(name), 256) for name in (
                "evaluation_provider_kind", "evaluation_provider_endpoint_id",
                "evaluation_provider_model", "provider_service_revision",
            ))
            and valid_hex(value.get("provider_control_sha256"))
            and bounded_integer(value.get("max_prompt_bytes"), 1, 1_048_576)
            and bounded_integer(value.get("max_tokens"), 1, 1_048_576)
            and bounded_integer(value.get("temperature_micros"), 0, 1_000_000)
            and value.get("seed_mode") == "PAIRED_FIXED"
            and bounded_integer(value.get("seed_base"), -(2**63), 2**63 - 1)
        )
    elif kind == "EVALUATION_PROVIDER_CONTROL":
        valid = (
            valid_ascii_identifier(value.get("provider_control_id"))
            and all(bounded_text(value.get(name), 4096 if name == "endpoint" else 256) for name in (
                "provider_kind", "endpoint", "endpoint_id", "model",
            ))
            and (value.get("api_key_env") is None or bounded_text(value.get("api_key_env"), 256))
            and (value.get("tokenize_endpoint") is None or bounded_text(value.get("tokenize_endpoint"), 4096))
            and bounded_integer(value.get("timeout_ns"), 1, 7_200_000_000_000)
            and bounded_integer(value.get("max_response_bytes"), 1, RESULT_LIMIT)
        )
    elif kind == "ENVIRONMENT_POLICY":
        valid = valid_ascii_identifier(value.get("policy_id")) and isinstance(value.get("allowed_variables"), list)
    elif kind == "TASK_PROMPT":
        valid = prompt_text_valid(value, "TASK_PROMPT")
    elif kind == "CONTEXT_SOURCES":
        valid = (
            valid_ascii_identifier(value.get("task_id"))
            and prompt_text_valid(value.get("patch_evaluation"), "PATCH_EVALUATION")
            and prompt_text_valid(value.get("failure_memory_jsonl"), "FAILURE_MEMORY_JSONL")
            and prompt_text_valid(value.get("diagnostic_stdout"), "DIAGNOSTIC_STDOUT")
            and prompt_text_valid(value.get("diagnostic_stderr"), "DIAGNOSTIC_STDERR")
        )
    elif kind == "PROMPT_SOURCE_VERIFIER_POLICY":
        valid = (
            valid_ascii_identifier(value.get("policy_id"))
            and bounded_text(value.get("helper_path"), 4096)
            and bounded_text(value.get("helper_runtime"), 256)
            and all(valid_hex(value.get(name)) for name in (
                "helper_sha256", "interpreter_sha256", "git_executable_sha256",
            ))
        )
    if not valid:
        raise EvaluationError(f"{kind} value is invalid")


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
    # The derived generation child is built, not committed, so it is not a corpus member: its
    # per-run absolute path and declared digest travel in this request and in the recorded check
    # evidence. There is no environment or sibling-checkout fallback.
    validate_absolute_path_syntax(request.get("generation_child_path"), "generation child")
    if not valid_hex(request.get("generation_child_sha256")):
        raise EvaluationError("generation child digest is invalid")


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


def load_bound(
    path: Path, kind: str, maximum: int = ARTIFACT_LIMIT, versions: tuple[int, ...] = (1,),
) -> dict[str, Any]:
    """Decode one bounded artifact and bind its own digest.

    `versions` exists for exactly one artifact: `TASK_MEASUREMENT` is now decodable at 1 and 2
    (spec section 3.3). Every other kind keeps the single admitted version it always had, so
    widening this helper does not widen any other decode.
    """
    value = load_json(path, maximum)
    if value.get("schema_version") not in versions or value.get("artifact_kind") != kind or not valid_hex(value.get("content_sha256")):
        raise EvaluationError(f"{kind} header is invalid")
    normalized = dict(value)
    normalized["content_sha256"] = ""
    if hashlib.sha256(canonical_digest_bytes(normalized)).hexdigest() != value["content_sha256"]:
        raise EvaluationError(f"{kind} digest does not match")
    validate_input_artifact_shape(kind, value)
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
    physical_parent = physical_directory(parent if not must_exist or parent.is_dir() else parent.parent)
    if not must_exist:
        metadata = os.stat(physical_parent, follow_symlinks=False)
        if metadata.st_mode & 0o222 == 0 or not os.access(physical_parent, os.W_OK | os.X_OK):
            raise EvaluationError("evaluation output parent is not writable")
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
    executable_total = 0
    if any(
        not isinstance(item, str)
        or not item.startswith("/")
        or not item
        or len(item.encode("utf-8")) > 4096
        or "\0" in item
        for item in executable_paths
    ):
        raise EvaluationError("environment executable path is invalid")
    for item in executable_paths:
        executable_total += len(item.encode("utf-8"))
        if executable_total > 65_536:
            raise EvaluationError("environment executable policy exceeds its byte bound")
    locale = policy.get("locale")
    if not isinstance(locale, str) or not locale or len(locale.encode("utf-8")) > 64 or "\0" in locale:
        raise EvaluationError("environment locale is invalid")
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
            or ENVIRONMENT_NAME.fullmatch(name) is None
            or not isinstance(value, str)
            or len(value.encode("utf-8")) > 4096
            or "\0" in value
            or not isinstance(item["source"], str)
            or item["source"] != "EXPLICIT_POLICY"
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
    if output.get("LANG") != locale or output.get("LC_ALL") != locale:
        raise EvaluationError("environment locale disagrees with LANG or LC_ALL")
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
    if not CHILD_SUBREAPER_ENABLED:
        raise ChildBoundaryError("PROCESS")
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
        if process_group_exists(process.pid) or owned_descendant_ids(process):
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


def command(task: Mapping[str, Any], name: str, project: Path) -> tuple[list[str], RetainedRegularFile]:
    argv = list(task[name])
    if not argv or argv[0] != task["cmd" if name == "argv" else "snapshot_cmd"]:
        raise EvaluationError("task command and argv disagree")
    executable = Path(argv[0])
    if not executable.is_absolute():
        executable = project / executable
    argv[0] = str(executable)
    if len(argv) != 2:
        raise EvaluationError("task interpreter command must contain one helper")
    helper_path = relative_path(project, argv[1])
    runtime_name = "measurement_adapter_runtime" if name == "argv" else "snapshot_helper_runtime"
    runtime = task[runtime_name]
    if not isinstance(runtime, str) or not runtime.startswith("PYTHON:") or not valid_hex(runtime[7:]):
        raise EvaluationError("task helper runtime identity is invalid")
    helper = RetainedRegularFile(helper_path, ARTIFACT_LIMIT)
    try:
        if helper.sha256() != runtime[7:]:
            raise EvaluationError("task helper runtime digest does not match")
        argv[1] = helper.process_path()
        return argv, helper
    except BaseException:
        helper.close()
        raise


def utf8_prefix(raw: bytes, max_bytes: int) -> bytes:
    """Longest UTF-8-safe prefix inside a byte budget; the port of `prompt_model.utf8_prefix`."""
    boundary = min(max_bytes, len(raw))
    if boundary <= 0:
        return b""
    probe = boundary
    while probe > 0:
        last = raw[probe - 1]
        if 0x80 <= last <= 0xBF:
            probe -= 1
            continue
        expected = 1 if last <= 0x7F else 2 if last <= 0xDF else 3 if last <= 0xEF else 4
        return raw[:probe - 1] if boundary - (probe - 1) < expected else raw[:boundary]
    return raw[:boundary]


def bounded_body(raw: bytes, limit: int, marker: bytes) -> bytes:
    """Port of `prompt_model.bounded_text`: the marker lives inside the same byte budget."""
    if limit <= 0:
        return b""
    if len(raw) <= limit:
        return raw
    if len(marker) > limit:
        return b""
    return utf8_prefix(raw, limit - len(marker)) + marker


def decoded_memory_event(line: bytes) -> dict[str, Any] | None:
    """Port of `failure_memory.decode_memory_event`: one line must be a complete `MemoryEvent`.

    Align's `json.decode` requires every declared field exactly once, rejects a declared duplicate,
    a type mismatch, an out-of-range integer, trailing input, and a malformed string, and skips
    undeclared keys. `MemoryEvent` selects borrowed `str` fields, so Align cannot materialize an
    escaped value and rejects the line; in a valid JSON document every backslash is inside a string
    token, which makes the scan below exact for every declared field. A line whose only escape sits
    in an undeclared key or value is the one input this port rejects and Align skips.
    """
    if b"\\" in line:
        return None
    try:
        pairs = json.loads(line.decode("utf-8"), object_pairs_hook=lambda items: items)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(pairs, list) or not all(
        isinstance(item, tuple) and len(item) == 2 for item in pairs
    ):
        return None
    value: dict[str, Any] = {}
    for name, item in pairs:
        if name in MEMORY_EVENT_FIELDS and name in value:
            return None
        value[name] = item
    if not all(isinstance(value.get(name), str) for name in MEMORY_EVENT_TEXT_FIELDS):
        return None
    return value if all(
        isinstance(value.get(name), int)
        and not isinstance(value.get(name), bool)
        and -(2 ** 63) <= value[name] <= 2 ** 63 - 1
        for name in MEMORY_EVENT_INTEGER_FIELDS
    ) else None


def valid_memory_jsonl(raw: bytes) -> bool:
    """Port of `failure_memory.valid_memory_jsonl`: every non-empty line is a schema-1 event."""
    if len(raw) > MEMORY_JSONL_LIMIT:
        return False
    cursor = 0
    while cursor < len(raw):
        line_break = raw.find(b"\n", cursor)
        line_end = len(raw) if line_break < 0 else line_break
        line = raw[cursor:line_end]
        if line:
            event = decoded_memory_event(line)
            if event is None or event["schema_version"] != 1:
                return False
        if line_break < 0:
            break
        cursor = line_end + 1
    return True


def selected_failure_context(raw: bytes, task_id: bytes, max_events: int, max_bytes: int) -> bytes | None:
    """Port of `failure_memory.select_context`; `None` is the invalid selector result."""
    if max_events < 0 or max_events > 64 or max_bytes < 0 or max_bytes > CONTEXT_SECTION_LIMIT:
        return None
    if not valid_memory_jsonl(raw):
        return None
    if max_events == 0 or max_bytes == 0 or not task_id:
        return b""
    selected: list[bytes] = []
    cursor = len(raw)
    remaining = max_bytes
    while cursor > 0 and len(selected) < max_events:
        line_break = raw.rfind(b"\n", 0, cursor)
        line_start = 0 if line_break < 0 else line_break + 1
        line = raw[line_start:cursor]
        if line:
            event = decoded_memory_event(line)
            if event is not None and event["schema_version"] == 1 and event["task_id"].encode("utf-8") == task_id:
                cost = len(line) + (1 if selected else 0)
                if cost <= remaining:
                    selected.append(line)
                    remaining -= cost
        cursor = 0 if line_break < 0 else line_break
    return b"\n".join(reversed(selected))


def valid_section_limit(enabled: bool, limit: int, maximum: int) -> bool:
    if limit < 0 or limit > maximum:
        return False
    return limit > 0 if enabled else limit == 0


def valid_render_policy(policy: Mapping[str, Any]) -> bool:
    """Port of `prompt_model.valid_policy`: each flag binds its own limit."""
    if not valid_section_limit(
        policy["include_patch_evaluation"], policy["max_patch_evaluation_bytes"], CONTEXT_SECTION_LIMIT,
    ):
        return False
    if not valid_section_limit(
        policy["include_failure_memory"], policy["max_failure_context_bytes"], CONTEXT_SECTION_LIMIT,
    ):
        return False
    if policy["max_failure_events"] < 0 or policy["max_failure_events"] > 64:
        return False
    if policy["include_failure_memory"] != (policy["max_failure_events"] > 0):
        return False
    return valid_section_limit(
        policy["include_diagnostics"], policy["max_diagnostic_bytes_per_stream"], CONTEXT_SECTION_LIMIT,
    )


def valid_render_sources(
    base_prompt: bytes, repo_prompt: bytes, task_prompt: bytes, learned_prompt_append: bytes,
    failure_memory_jsonl: bytes, patch_evaluation: bytes, diagnostic_stdout: bytes, diagnostic_stderr: bytes,
) -> bool:
    """Port of `prompt_model.valid_sources`: every context source is bounded before composition."""
    if any(len(item) > CONTEXT_SECTION_LIMIT for item in (base_prompt, repo_prompt, task_prompt)):
        return False
    if len(learned_prompt_append) > LEARNED_APPEND_LIMIT:
        return False
    if any(len(item) > CONTEXT_SECTION_LIMIT for item in (
        patch_evaluation, diagnostic_stdout, diagnostic_stderr,
    )):
        return False
    return len(failure_memory_jsonl) <= MEMORY_JSONL_LIMIT


def render_prompt(
    base_prompt: str, repo_prompt: str, task_prompt: str, learned_prompt_append: str, task_id: str,
    failure_memory_jsonl: str, policy: Mapping[str, Any], patch_evaluation: str,
    diagnostic_stdout: str, diagnostic_stderr: str,
) -> tuple[str, str, str]:
    """Byte-faithful port of `prompt_model.render`; returns its status, text, and raw text digest."""
    base_raw = base_prompt.encode("utf-8")
    repo_raw = repo_prompt.encode("utf-8")
    task_raw = task_prompt.encode("utf-8")
    learned_raw = learned_prompt_append.encode("utf-8")
    memory_raw = failure_memory_jsonl.encode("utf-8")
    patch_raw = patch_evaluation.encode("utf-8")
    stdout_raw = diagnostic_stdout.encode("utf-8")
    stderr_raw = diagnostic_stderr.encode("utf-8")
    if not valid_render_policy(policy) or not valid_render_sources(
        base_raw, repo_raw, task_raw, learned_raw, memory_raw, patch_raw, stdout_raw, stderr_raw,
    ):
        return "INVALID_INPUT", "", ""
    memory = selected_failure_context(
        memory_raw, task_id.encode("utf-8"), policy["max_failure_events"], policy["max_failure_context_bytes"],
    )
    if memory is None:
        return "INVALID_FAILURE_MEMORY", "", ""

    output = bytearray()
    output += base_raw
    output += b"\n\n--- repo prompt ---\n"
    output += repo_raw
    output += b"\n\n--- task prompt ---\n"
    output += task_raw
    output += b"\n\n--- learned prompt append ---\n"
    output += learned_raw if learned_raw else b"(none)"

    output += b"\n\n--- patch evaluation context ---\n"
    if policy["include_patch_evaluation"]:
        output += bounded_body(patch_raw, policy["max_patch_evaluation_bytes"], CONTEXT_TRUNCATION_MARKER)
    else:
        output += b"(omitted)"

    output += b"\n\n--- failure memory context ---\n"
    output += memory if policy["include_failure_memory"] else b"(omitted)"

    output += b"\n\n--- current failure diagnostics ---\n"
    if policy["include_diagnostics"]:
        limit = policy["max_diagnostic_bytes_per_stream"]
        output += b"stdout:\n"
        output += bounded_body(stdout_raw, limit, DIAGNOSTIC_TRUNCATION_MARKER)
        output += b"\nstderr:\n"
        output += bounded_body(stderr_raw, limit, DIAGNOSTIC_TRUNCATION_MARKER)
    else:
        output += b"(omitted)"

    raw = bytes(output)
    return "VALID", raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()


def render(variant: Mapping[str, Any], task_prompt: Mapping[str, Any], context: Mapping[str, Any]) -> tuple[str, str]:
    """Render one variant against one task's context sources, or reject the invalid render."""
    status, text, sha256 = render_prompt(
        variant["base_prompt"]["text"],
        variant["repo_prompt"]["text"],
        task_prompt["text"],
        variant["learned_prompt_append"],
        context["task_id"],
        context["failure_memory_jsonl"]["text"],
        variant["context_policy"],
        context["patch_evaluation"]["text"],
        context["diagnostic_stdout"]["text"],
        context["diagnostic_stderr"]["text"],
    )
    if status == "INVALID_FAILURE_MEMORY":
        raise EvaluationError("rendered prompt failure memory profile is invalid")
    if status != "VALID":
        raise EvaluationError("rendered prompt context policy or source bounds are invalid")
    return text, sha256


def expected_template_kinds(task: Mapping[str, Any]) -> tuple[str, ...]:
    """Ladder row 8: which section kinds this task's sealed template must declare, exactly."""
    declared = list(task.get("argv") or [])
    if len(declared) == 2 and declared[1] == REPAIR_ADAPTER_RELATIVE:
        return REPAIR_SECTION_KINDS
    return REPAIR_SECTION_KINDS_V1


def valid_repair_template(value: Any, kinds: tuple[str, ...] = REPAIR_SECTION_KINDS) -> bool:
    """Ladder row 8: the sealed repair template decodes, is UTF-8, and is non-empty.

    `kinds` is the exact header set this task's corpus must declare. It is an equality, never a
    subset test: a template carrying a kind the evaluator does not render, or missing one it does,
    is a corpus defect rather than a tolerable difference.
    """
    headers = value.get("section_headers") if isinstance(value, dict) else None
    return (
        exact_record(value, REPAIR_TEMPLATE_FIELDS, "REPAIR_PROMPT_TEMPLATE")
        and record_digest_valid(value)
        and valid_ascii_identifier(value.get("template_id"))
        and bounded_text(value.get("preamble_text"), REPAIR_TEMPLATE_TEXT_LIMIT)
        and bounded_text(value.get("closing_text"), REPAIR_TEMPLATE_TEXT_LIMIT)
        and isinstance(headers, dict)
        and tuple(headers) == kinds
        and all(bounded_text(headers[kind], REPAIR_SECTION_HEADER_LIMIT) for kind in kinds)
    )


def repair_status_text(measurement: Mapping[str, Any]) -> str:
    """Section 1 of the repair prompt: four status labels, one per line, at most 128 bytes."""
    return (
        f"status: {measurement['status']}\n"
        f"failure_kind: {measurement['failure_kind']}\n"
        f"build_status: {measurement['build_status']}\n"
        f"test_status: {measurement['test_status']}"
    )


def edit_set_fence(body: str) -> str:
    """The shortest backtick run that carries `body` as content rather than terminating it.

    This is the frozen `fence_run` / `closing_fence` rule read backwards. That parser terminates a
    block on a line that is only backticks and at least as long as the opening run, so an opening
    run one longer than the longest such line inside the body makes every nested fence ordinary
    content. Nothing else in the body can close the block.
    """
    longest = 0
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped and set(stripped) == {"`"}:
            longest = max(longest, len(stripped))
    return "`" * max(3, longest + 1)


def repair_edit_set_text(measurement: Mapping[str, Any]) -> str:
    """Section 4.3: attempt one's realized edit set, in the response's own whole-file format.

    Format-consistency is deliberate. The C4 run measured this model failing the whole-file format
    on one task in eight of eight attempts; a prompt that displayed a unified diff while demanding
    whole files would push toward exactly that mode. The rejected alternative — rendering the
    synthesized unified diff — is smaller on the wire and is a *different* format from the one
    required, and is rejected for that reason.

    The section is rendered from the **persisted** `edit_set`, never from a live value, exactly as
    `STDOUT` is rendered from `diagnostic_stdout`. If a block was omitted for budget at the
    producer, the prompt cannot show it either, and the two stay in agreement by construction. An
    omitted block is one line naming its path and byte count, never a partial file: a half-truncated
    source file would invite the model to complete a file it can only half see, and the whole-file
    format makes that a silent data-loss patch.

    A version-1 measurement carries no `edit_set`, so this returns the empty string and the section
    is simply not emitted — which is how `SUMMARY`, `STDOUT`, and `STDERR` already behave.
    """
    blocks = measurement.get("edit_set")
    if not blocks:
        return ""
    parts: list[str] = []
    for block in blocks:
        path = block["path"]
        body = block.get("body_text")
        if body is None:
            parts.append(f"FILE: {path} [omitted for prompt budget: {block['body_bytes']} bytes]")
            continue
        if body and not body.endswith("\n"):
            body += "\n"
        fence = edit_set_fence(body)
        parts.append(f"FILE: {path}\n{fence}\n{body}{fence}")
    return "\n\n".join(parts)


def repair_section_sources(measurement: Mapping[str, Any]) -> dict[str, str]:
    """Every source is a field of the failing attempt's persisted `TASK_MEASUREMENT`.

    Nothing is re-captured, re-read, re-redacted, or re-truncated: the adapter already applied
    `redact_credential` and then bounded each stream, in that order, before these bytes were
    persisted. Consuming its output verbatim is what makes section 4.4's re-derivation close.
    """
    return {
        "STATUS": repair_status_text(measurement),
        "EDITSET": repair_edit_set_text(measurement),
        "SUMMARY": measurement["diagnostic_summary"],
        "STDOUT": measurement["diagnostic_stdout"],
        "STDERR": measurement["diagnostic_stderr"],
    }


def repair_prompt_text(
    template: Mapping[str, Any], base_text: str, sources: Mapping[str, str], included: Sequence[str],
) -> str:
    """The repair prompt is a strict textual extension of the attempt it repairs.

    The variant's base prompt, repo prompt, task prompt, learned append, and canned context
    sections are the attempt-1 text byte-for-byte; the repair sections are appended, never
    substituted, so the two attempts' inputs are directly diffable in the evidence.
    """
    headers = template["section_headers"]
    parts = [base_text, "\n\n", template["preamble_text"]]
    for kind in REPAIR_SECTION_KINDS:
        if kind in headers and kind in included:
            parts.extend(("\n\n", headers[kind], "\n", sources[kind]))
    parts.extend(("\n\n", template["closing_text"]))
    return "".join(parts)


def ordered_sections(kinds: Iterable[str]) -> list[str]:
    selected = set(kinds)
    return [kind for kind in REPAIR_SECTION_KINDS if kind in selected]


def assemble_repair_prompt(
    template: Mapping[str, Any], base_text: str, sources: Mapping[str, str], maximum_bytes: int,
) -> tuple[str | None, list[str], list[str], int]:
    """Assemble the repair prompt, dropping whole sections in the fixed precedence of section 4.3.

    Returns `(text, included, dropped, assembled_bytes)`, with `text` `None` when even the
    preamble, headers, attempt-1 text, and `STATUS` exceed the generation policy's prompt budget.
    A drop is always whole-section: a half-truncated stream would end mid-traceback and invite the
    model to repair a failure it can only half see.

    **The two lists are not a partition of `REPAIR_SECTION_KINDS`, deliberately.** `included` is
    what the assembled prompt actually carries and `dropped` is what the budget ladder removed. A
    section whose source is empty was never a candidate, so it appears in neither: the adapter
    produced nothing for it, and calling that a "drop" would report a budget decision that was
    never taken. The published gate evidence shows the case — all four
    `layer-precedence-frozen-module` repairs have an empty `diagnostic_stdout`, and record
    `included_sections: [STATUS, SUMMARY, STDERR]` with `dropped_sections: []`. Section 4.3 of
    `docs/specs/c4-repair-measured.md` states the same rule; a consumer that needs "was this
    section available" must read `attempt.measurement` and not infer it from these two lists.
    """
    # Only a kind the sealed template declares can be included: the template is the corpus's
    # statement of what its repair prompt carries, and a section with no header has no rendering.
    headers = template["section_headers"]
    included = [kind for kind in REPAIR_SECTION_KINDS if kind in headers and sources[kind]]
    dropped: list[str] = []
    while True:
        text = repair_prompt_text(template, base_text, sources, included)
        assembled = len(text.encode("utf-8"))
        if assembled <= maximum_bytes:
            return text, included, ordered_sections(dropped), assembled
        droppable = [kind for kind in REPAIR_DROP_ORDER if kind in included]
        if not droppable:
            return None, included, ordered_sections(dropped), assembled
        included = [kind for kind in included if kind != droppable[0]]
        dropped.append(droppable[0])


def repair_eligibility(measurement: Mapping[str, Any]) -> str:
    """Ladder row 18: are attempt one's own diagnostics usable as a repair input at all?

    **`EDITSET` alone does not make a repair eligible.** The three diagnostic streams are what tell
    the model why the answer was rejected; the edit set only tells it what the answer was. A run
    with an edit set and no diagnostics at all is still `SKIPPED`, which keeps this predicate
    exactly the one C4-REPAIR-MEASURED fixed and keeps the two runs' eligibility comparable.
    """
    if not measurement.get("cleanup_passed") or not measurement.get("containment_passed"):
        return "REPAIR_INPUT_UNAVAILABLE"
    sources = repair_section_sources(measurement)
    if not any(sources[kind] for kind in ("SUMMARY", "STDOUT", "STDERR")):
        return "REPAIR_INPUT_UNAVAILABLE"
    return "NONE"


def skipped_attempt_record(
    attempt_index: int, reason: str, repair_source: dict[str, Any] | None,
    preparation_ns: int, paired_seed: int,
) -> dict[str, Any]:
    """A skipped repair is a measured outcome; it never becomes a silent single-attempt row.

    The record carries identity and the work that reached the skip decision, and nothing else: no
    rendered prompt, no adapter request, no generation request, no measurement. It is never
    counted in `row.repair_loop_count` and never contributes to any timing sum.
    """
    return bind({
        "schema_version": 1,
        "artifact_kind": "TASK_ATTEMPT_RECORD",
        "attempt_index": attempt_index,
        "attempt_kind": "REPAIR",
        "status": "SKIPPED",
        "skip_reason": reason,
        "rendered_prompt_sha256": None,
        "repair_prompt_source": repair_source,
        "adapter_request_sha256": None,
        "snapshot_request_sha256": None,
        "before_snapshot_result_sha256": None,
        "after_snapshot_result_sha256": None,
        "input_snapshot_sha256": None,
        "generation_request": None,
        "seed_attestation": None,
        "paired_seed": paired_seed,
        "measurement": None,
        "repair_preparation_ns": preparation_ns,
        "adapter_elapsed_ns": 0,
        "adapter_overhead_ns": None,
        "measurement_sha256": None,
        "content_sha256": "",
    })


def repair_prompt_source_record(
    template: Mapping[str, Any], measurement: Mapping[str, Any], included: Sequence[str],
    dropped: Sequence[str], assembled: int,
) -> dict[str, Any]:
    return bind({
        "schema_version": 1,
        "artifact_kind": "REPAIR_PROMPT_SOURCE",
        "template_sha256": template["content_sha256"],
        "source_attempt_index": 1,
        "source_measurement_sha256": measurement["content_sha256"],
        "included_sections": list(included),
        "dropped_sections": list(dropped),
        "assembled_bytes": assembled,
        "content_sha256": "",
    })


def build_repair_attempt(
    run_attempt: Any, first: Mapping[str, Any], template: Mapping[str, Any] | None,
    generation: Mapping[str, Any], paired_seed: int,
) -> dict[str, Any]:
    """Render the repair prompt from attempt one's own persisted diagnostics and run attempt two.

    `repair_preparation_ns` is the monotonic span from immediately after the previous attempt's
    adapter exits to immediately before this attempt's adapter is spawned, so the assembly work
    that reached a skip decision is measured exactly like the assembly work that reached a call.
    """
    started_ns = time.monotonic_ns()
    measurement = first["measurement"]

    def skipped(reason: str, source: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "skipped": True,
            "record": skipped_attempt_record(
                2, reason, source, time.monotonic_ns() - started_ns, paired_seed,
            ),
        }

    if template is None:
        return skipped("REPAIR_NOT_ELIGIBLE", None)
    reason = repair_eligibility(measurement)
    if reason != "NONE":
        return skipped(reason, None)
    sources = repair_section_sources(measurement)
    text, included, dropped, assembled = assemble_repair_prompt(
        template, first["rendered_text"], sources, generation["max_prompt_bytes"],
    )
    source = repair_prompt_source_record(template, measurement, included, dropped, assembled)
    if text is None:
        # Ladder row 14: no provider call is made, and the dropped sections are recorded so the
        # budget decision is legible in the evidence rather than inferred from an absence.
        return skipped("REPAIR_PROMPT_BUDGET", source)
    # Ladder row 15: the producer runs section 4.4's re-derivation against its own output. This
    # buys auditability, not independence-from-the-run: the repair prompt's content is a function
    # of the model's attempt-one output, so no verifier can derive it from the frozen assets alone.
    rederived = repair_prompt_text(
        template, first["rendered_text"], repair_section_sources(measurement),
        source["included_sections"],
    )
    if rederived != text:
        raise EvaluationError("the repair prompt is not re-derivable from its persisted source")
    return run_attempt(2, text, digest(text), source, time.monotonic_ns() - started_ns)


def attempt_total_ns(records: Sequence[Mapping[str, Any]]) -> int | None:
    """Section 3.6: the evaluator-observed total through the first passing attempt.

    Every addition is exact `i64` and is bounds-checked against the existing two-hour ceiling
    before it is persisted. Nothing saturates and nothing is clamped: a silently clamped
    nanosecond count is the prior incident class this rule exists to prevent.
    """
    total = 0
    for record in records:
        if record["status"] == "SKIPPED":
            continue
        total += record["adapter_elapsed_ns"] + record["repair_preparation_ns"]
        if record["status"] == "PASS":
            if total <= 0 or total > 7_200_000_000_000:
                raise EvaluationError("attempt timing total is outside its persisted bound")
            return total
    return None


def write_exclusive(
    path: Path, raw: bytes, maximum: int, owned_paths: set[Path] | None = None,
) -> None:
    if len(raw) > maximum:
        raise EvaluationError("evaluation output exceeds its bound")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    if owned_paths is not None:
        owned_paths.add(path)
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
    write_exclusive(path, canonical(value), ARTIFACT_LIMIT, owned_paths)
    return path


def create_owned_output(path: Path, owned_paths: set[Path]) -> int:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    owned_paths.add(path)
    return descriptor


def retire_owned_path(path: Path, owned_paths: set[Path]) -> bool:
    """Remove one path and retire ownership before any later occupant can be considered ours."""
    if path not in owned_paths:
        return True
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return False
    owned_paths.discard(path)
    return True


def cleanup_owned_paths(owned_paths: set[Path]) -> list[Path]:
    """Best-effort cleanup whose return contains only still-owned survivors."""
    for path in sorted(
        tuple(owned_paths), key=lambda item: (len(item.parts), os.fsencode(item)), reverse=True,
    ):
        retire_owned_path(path, owned_paths)
    return sorted(owned_paths, key=lambda item: os.fsencode(item))


def valid_environment_probe(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and tuple(value) == ENVIRONMENT_PROBE_FIELDS
        and value.get("schema_version") == 1
        and value.get("artifact_kind") == "ENVIRONMENT_PROBE"
        and all(
            isinstance(value.get(name), str) and 0 < len(value[name].encode("utf-8")) <= 256
            for name in ("producer", "os", "os_release", "architecture", "cpu", "gpu", "runtime_identity")
        )
        and (
            value.get("logical_cpu_count") is None
            or isinstance(value.get("logical_cpu_count"), int)
            and not isinstance(value.get("logical_cpu_count"), bool)
            and 0 < value["logical_cpu_count"] <= 1_048_576
        )
        and valid_hex(value.get("content_sha256"))
        and canonical_digest({**value, "content_sha256": ""}) == value["content_sha256"]
    )


def valid_artifact_digest(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and tuple(value) == ARTIFACT_DIGEST_FIELDS
        and isinstance(value.get("path"), str)
        and 0 < len(value["path"].encode("utf-8")) <= 4096
        and isinstance(value.get("mode"), str)
        and 0 < len(value["mode"].encode("utf-8")) <= 16
        and isinstance(value.get("byte_count"), int)
        and not isinstance(value.get("byte_count"), bool)
        and value["byte_count"] >= 0
        and valid_hex(value.get("sha256"))
    )


def bounded_snapshot_tree_paths(
    project: Path, relative: str, maximum_entries: int,
) -> list[str]:
    if maximum_entries < 1:
        raise EvaluationError("snapshot expanded path count exceeds its bound")
    root = relative_path(project, relative)
    metadata = os.lstat(root)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise EvaluationError("snapshot tree root is unsafe")
    selected = [relative]
    pending = [root]
    while pending:
        directory = pending.pop()
        entries = []
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if len(selected) + len(entries) >= maximum_entries:
                    raise EvaluationError("snapshot expanded path count exceeds its bound")
                entries.append(entry)
        entries.sort(key=lambda item: os.fsencode(item.name))
        for entry in entries:
            metadata = entry.stat(follow_symlinks=False)
            child_path = Path(entry.path)
            child = str(child_path.relative_to(project))
            if stat.S_ISDIR(metadata.st_mode):
                selected.append(child)
                pending.append(child_path)
            elif stat.S_ISREG(metadata.st_mode):
                selected.append(child)
            else:
                raise EvaluationError("snapshot tree contains an unsafe entry")
    selected.sort(key=os.fsencode)
    return selected


def expected_snapshot_paths(request: Mapping[str, Any], project: Path) -> list[str]:
    static_expectations = request.get("static_expectations")
    additional_files = request.get("additional_files")
    if (
        not isinstance(static_expectations, list) or len(static_expectations) > 64
        or not isinstance(additional_files, list) or len(additional_files) > 32
    ):
        raise EvaluationError("snapshot declaration count exceeds its bound")
    paths: list[str] = []
    expanded = 0
    for expectation in static_expectations:
        relative = expectation["path"]
        if expectation["kind"] == "FILE":
            selected = [relative]
        elif expectation["kind"] == "TREE":
            selected = bounded_snapshot_tree_paths(project, relative, 128 - expanded)
        else:
            raise EvaluationError("snapshot expectation kind is invalid")
        expanded += len(selected)
        if expanded > 128:
            raise EvaluationError("snapshot expanded path count exceeds its bound")
        paths.extend(selected)
    paths.extend(additional_files)
    if len(paths) != len(set(paths)):
        raise EvaluationError("snapshot paths overlap")
    return paths


def valid_snapshot_result(
    value: Any, task_id: str, request: Mapping[str, Any], project: Path,
) -> bool:
    if (
        not isinstance(value, dict)
        or tuple(value) != SNAPSHOT_RESULT_FIELDS
        or value.get("schema_version") != 1
        or value.get("artifact_kind") != "SNAPSHOT_RESULT"
        or value.get("task_id") != task_id
        or value.get("status") not in ("MATCH", "MISMATCH", "ERROR")
        or not isinstance(value.get("error_code"), str)
        or not isinstance(value.get("error"), str)
        or not isinstance(value.get("artifact_digests"), list)
        or len(value["artifact_digests"]) > 160
        or not all(valid_artifact_digest(item) for item in value["artifact_digests"])
        or len({item["path"] for item in value["artifact_digests"]}) != len(value["artifact_digests"])
    ):
        return False
    if value["environment_probe"] is not None and not valid_environment_probe(value["environment_probe"]):
        return False
    try:
        expected_paths = expected_snapshot_paths(request, project)
    except (EvaluationError, OSError, ValueError):
        return False
    observed_paths = [item["path"] for item in value["artifact_digests"]]
    if sum(item["byte_count"] for item in value["artifact_digests"]) > SNAPSHOT_ARTIFACT_LIMIT:
        return False
    if value["status"] in ("MATCH", "MISMATCH"):
        if value["status"] == "MATCH" and observed_paths != expected_paths:
            return False
        if value["status"] == "MISMATCH" and observed_paths != expected_paths[:len(observed_paths)]:
            return False
    if value["status"] == "MATCH":
        return value["error_code"] == "NONE" and value["error"] == "" and value["environment_probe"] is not None
    if not 0 < len(value["error"].encode("utf-8")) <= 4096:
        return False
    if value["status"] == "MISMATCH":
        return (
            value["error_code"] in ("PATH", "TYPE", "MODE", "CONTENT", "TREE", "REPO_REVISION", "DIRTY_REPO")
            and value["environment_probe"] is not None
        )
    return (
        value["error_code"] == "ENVIRONMENT" and value["environment_probe"] is None
        or value["error_code"] in ("INTERNAL", "CLEANUP") and value["environment_probe"] is not None
    )


def valid_workspace_preflight(value: Any, evaluation_id: str) -> bool:
    if not (
        isinstance(value, dict)
        and tuple(value) == WORKSPACE_PREFLIGHT_RESULT_FIELDS
        and value.get("schema_version") == 1
        and value.get("artifact_kind") == "WORKSPACE_PREFLIGHT_RESULT"
        and value.get("evaluation_id") == evaluation_id
        and value.get("status") in ("SAFE", "UNSAFE", "ERROR")
        and isinstance(value.get("error_code"), str)
        and isinstance(value.get("error"), str)
        and isinstance(value.get("physical_project_root"), str)
        and isinstance(value.get("physical_workspace_path"), str)
        and (
            value.get("environment_probe") is None
            or valid_environment_probe(value.get("environment_probe"))
        )
    ):
        return False
    if value["status"] == "SAFE":
        return (
            value["error_code"] == "NONE"
            and value["error"] == ""
            and value["physical_project_root"] != ""
            and value["physical_workspace_path"] != ""
            and value["environment_probe"] is not None
        )
    if not 0 < len(value["error"].encode("utf-8")) <= 4096:
        return False
    paths_valid = value["physical_project_root"] == "" or value["physical_workspace_path"] == ""
    if value["status"] == "UNSAFE":
        return (
            value["error_code"] in ("TYPE", "SYMLINK", "ESCAPE", "NOT_EMPTY")
            and paths_valid
            and value["environment_probe"] is None
        )
    return (
        value["error_code"] in ("ENVIRONMENT", "INTERNAL", "CLEANUP")
        and paths_valid
        and value["environment_probe"] is None
    )


def measurement_state_valid(value: Mapping[str, Any]) -> bool:
    status = value.get("status")
    failure = value.get("failure_kind")
    build = value.get("build_status")
    test = value.get("test_status")
    cleanup = value.get("cleanup_passed")
    containment = value.get("containment_passed")
    violations = value.get("policy_violation_count")
    elapsed = value.get("generation_to_passing_patch_ns")
    if status == "PASS":
        return (
            failure == "NONE" and build == "PASS" and test == "PASS"
            and cleanup is True and containment is True and violations == 0
            and isinstance(elapsed, int) and not isinstance(elapsed, bool) and elapsed > 0
        )
    if status == "FAIL":
        stages = {
            "PROVIDER": ("NOT_RUN", "NOT_RUN"),
            "PATCH": ("NOT_RUN", "NOT_RUN"),
            "BUILD": ("FAIL", "NOT_RUN"),
            "TEST": ("PASS", "FAIL"),
        }
        return (
            failure in stages and (build, test) == stages[failure]
            and cleanup is True and containment is True and violations == 0 and elapsed is None
        )
    if status == "POLICY_VIOLATION":
        return (
            failure == "POLICY"
            and (build, test) in (("NOT_RUN", "NOT_RUN"), ("PASS", "NOT_RUN"), ("PASS", "PASS"))
            and cleanup is True and containment is True
            and isinstance(violations, int) and not isinstance(violations, bool) and violations > 0
            and elapsed is None
        )
    if status != "ERROR" or elapsed is not None:
        return False
    if containment is False:
        return failure == "CONTAINMENT"
    if cleanup is False:
        return containment is True and failure == "CLEANUP"
    return (
        containment is True and cleanup is True and failure == "ADAPTER"
        and (build == "ERROR" or test == "ERROR")
    )


def valid_task_measurement(
    value: Any, task: Mapping[str, Any], rendered_sha256: str,
    adapter_request: Mapping[str, Any], sample: int, seed: int, prompt_oversized: bool = False,
    allowed_edits: frozenset[str] = frozenset(),
) -> bool:
    if (
        not isinstance(value, dict)
        # Ladder rows 9 and 10. The version is read first and the field tuple is selected from it,
        # so every version-2 member is present at version 2 and absent at version 1. Presence never
        # stands in for a version, in either direction.
        or value.get("schema_version") not in (1, 2)
        or tuple(value) != (
            TASK_MEASUREMENT_V2_FIELDS if value.get("schema_version") == 2
            else TASK_MEASUREMENT_FIELDS
        )
        or value.get("artifact_kind") != "TASK_MEASUREMENT"
        or value.get("status") not in ("PASS", "FAIL", "POLICY_VIOLATION", "ERROR")
        or value.get("failure_kind") not in (
            "NONE", "PROVIDER", "PATCH", "BUILD", "TEST", "POLICY", "CLEANUP", "CONTAINMENT", "ADAPTER",
        )
        or value.get("build_status") not in ("PASS", "FAIL", "NOT_RUN", "ERROR")
        or value.get("test_status") not in ("PASS", "FAIL", "NOT_RUN", "ERROR")
        or not isinstance(value.get("cleanup_passed"), bool)
        or not isinstance(value.get("containment_passed"), bool)
        or value.get("rendered_prompt_sha256") != rendered_sha256
        or not all(isinstance(value.get(name), str) for name in (
            "failure_kind", "build_status", "test_status", "diagnostic_summary",
            "diagnostic_stdout", "diagnostic_stderr",
        ))
        or not all(
            isinstance(value.get(name), int) and not isinstance(value.get(name), bool) and value[name] >= 0
            for name in (
                "repair_loop_count", "unrelated_diff_count", "patch_size_bytes",
                "public_api_change_count", "policy_violation_count",
            )
        )
        or value["repair_loop_count"] > 64
        or value["unrelated_diff_count"] > 1_048_576
        or value["patch_size_bytes"] > 67_108_864
        or value["public_api_change_count"] > 1_048_576
        or value["policy_violation_count"] > 1_048_576
        or (
            value.get("benchmark_regression_ppm") is not None
            and (
                not isinstance(value.get("benchmark_regression_ppm"), int)
                or isinstance(value.get("benchmark_regression_ppm"), bool)
                or value["benchmark_regression_ppm"] < 0
                or value["benchmark_regression_ppm"] > 1_000_000
            )
        )
        or (
            value.get("generation_to_passing_patch_ns") is not None
            and (
                not isinstance(value.get("generation_to_passing_patch_ns"), int)
                or isinstance(value.get("generation_to_passing_patch_ns"), bool)
                or value["generation_to_passing_patch_ns"] <= 0
                or value["generation_to_passing_patch_ns"] > 7_200_000_000_000
            )
        )
    ):
        return False
    if not measurement_state_valid(value):
        return False
    if prompt_oversized and (
        adapter_request.get("variant") != "CANDIDATE" or value.get("status") != "POLICY_VIOLATION"
    ):
        return False
    generation = value.get("generation_request")
    attestation = value.get("seed_attestation")
    if (
        not isinstance(generation, dict)
        or tuple(generation) != GENERATION_REQUEST_FIELDS
        or generation.get("schema_version") != 1
        or generation.get("artifact_kind") != "GENERATION_REQUEST_IDENTITY"
        or generation.get("rendered_prompt_sha256") != rendered_sha256
        or generation.get("paired_seed") != seed
        or not all(valid_hex(generation.get(name)) for name in (
            "rendered_prompt_sha256", "system_text_sha256", "user_text_sha256",
            "generation_policy_sha256", "provider_control_sha256", "environment_policy_sha256",
            "provider_request_sha256", "seed_attestation_sha256", "content_sha256",
        ))
        or not all(
            isinstance(generation.get(name), int)
            and not isinstance(generation.get(name), bool)
            and -(2**63) <= generation[name] <= 2**63 - 1
            for name in ("max_tokens", "temperature_micros", "paired_seed")
        )
        or generation.get("max_tokens", 0) <= 0
        or generation.get("temperature_micros", -1) < 0
        or not valid_hex(generation.get("content_sha256"))
        or canonical_digest({**generation, "content_sha256": ""}) != generation.get("content_sha256")
        or not isinstance(attestation, dict)
        or tuple(attestation) != SEED_ATTESTATION_FIELDS
        or attestation.get("schema_version") != 1
        or attestation.get("artifact_kind") != "SEED_CAPABILITY_ATTESTATION"
        or attestation.get("requested_seed") != seed
        or not isinstance(attestation.get("provider_kind"), str)
        or not 0 < len(attestation["provider_kind"].encode("utf-8")) <= 256
        or not isinstance(attestation.get("provider_model"), str)
        or not 0 < len(attestation["provider_model"].encode("utf-8")) <= 256
        or attestation.get("result") not in ("APPLIED", "UNSUPPORTED", "REJECTED")
        or (
            attestation.get("applied_seed") is not None
            and (
                not isinstance(attestation.get("applied_seed"), int)
                or isinstance(attestation.get("applied_seed"), bool)
                or not -(2**63) <= attestation["applied_seed"] <= 2**63 - 1
            )
        )
        or not valid_hex(attestation.get("provider_request_sha256"))
        or not valid_hex(attestation.get("content_sha256"))
        or canonical_digest({**attestation, "content_sha256": ""}) != attestation.get("content_sha256")
        or attestation.get("provider_request_sha256") != generation.get("provider_request_sha256")
        or generation.get("seed_attestation_sha256") != attestation.get("content_sha256")
        or not valid_environment_probe(value.get("environment_probe"))
        or len(value["diagnostic_summary"].encode("utf-8")) > 4096
        or len(value["diagnostic_stdout"].encode("utf-8")) > 16384
        or len(value["diagnostic_stderr"].encode("utf-8")) > 16384
        or (
            task["regression_limits"].get("maximum_benchmark_regression_ppm") is None
            and value.get("benchmark_regression_ppm") is not None
        )
        or (
            task["regression_limits"].get("maximum_benchmark_regression_ppm") is not None
            and value["status"] == "PASS"
            and value.get("benchmark_regression_ppm") is None
        )
        or (
            task["regression_limits"].get("maximum_benchmark_regression_ppm") is not None
            and value["status"] != "PASS"
            and value.get("benchmark_regression_ppm") is not None
        )
        or (
            attestation.get("result") == "APPLIED"
            and attestation.get("applied_seed") != seed
        )
        or (
            attestation.get("result") != "APPLIED"
            and attestation.get("applied_seed") is not None
        )
    ):
        return False
    if not valid_measurement_version_two(value, task, allowed_edits):
        return False
    # Ladder row 12: the section 2.3 gap, closed at attempt level. `producer` names a role, so it is
    # the same literal for both adapters; `runtime_identity` names a file, and binding it here makes
    # every ran attempt's probe carry the digest of the code that actually ran, not only the row's
    # final one.
    probe = value["environment_probe"]
    if (
        probe["producer"] != "MEASUREMENT_ADAPTER"
        or probe["runtime_identity"] != task["measurement_adapter_runtime"]
    ):
        return False
    return (
        adapter_request.get("task_id") == task.get("task_id")
        and adapter_request.get("sample_index") == sample
        and adapter_request.get("paired_seed") == seed
    )


def valid_edit_set_block(value: Any, allowed: frozenset[str]) -> bool:
    """Ladder row 15: one `EDIT_SET_BLOCK`, and the whole of what a block promises.

    `body_sha256` digests the **redacted** bytes the producer held, and `body_text` carries those
    same bytes when the block was inside the prompt budget, so the two must agree exactly when both
    are present. An omitted block keeps `path`, `body_bytes`, and `body_sha256` and loses only its
    text, which is what lets a reader see what the budget removed.
    """
    return (
        exact_record(value, EDIT_SET_BLOCK_FIELDS, "EDIT_SET_BLOCK")
        and record_digest_valid(value)
        and isinstance(value.get("path"), str)
        and value["path"] in allowed
        and isinstance(value.get("body_bytes"), int)
        and not isinstance(value.get("body_bytes"), bool)
        and 0 <= value["body_bytes"] <= MAXIMUM_EDIT_BYTES
        and valid_hex(value.get("body_sha256"))
        and (
            value.get("body_text") is None
            or isinstance(value.get("body_text"), str)
            and len(value["body_text"].encode("utf-8")) <= EDIT_SET_LIMIT
            and hashlib.sha256(value["body_text"].encode("utf-8")).hexdigest() == value["body_sha256"]
        )
    )


def task_allowed_edits(task: Mapping[str, Any], project: Path) -> frozenset[str]:
    """The task definition's editable set, read from the manifest-declared, digest-pinned file."""
    resolved = relative_path(project, task["task_definition_path"])
    raw = read_bounded(resolved, ARTIFACT_LIMIT)
    if hashlib.sha256(raw).hexdigest() != task["task_definition_sha256"]:
        raise EvaluationError("the task definition digest disagrees")
    try:
        value = json.loads(raw.decode("utf-8", "strict"))
    except (UnicodeError, json.JSONDecodeError):
        raise EvaluationError("the task definition is not canonical JSON") from None
    allowed = value.get("allowed_edits") if isinstance(value, dict) else None
    if (
        not isinstance(allowed, list) or not allowed
        or not all(isinstance(item, str) and item for item in allowed)
    ):
        raise EvaluationError("the task definition declares no usable editable set")
    return frozenset(allowed)


def valid_measurement_version_two(
    value: Mapping[str, Any], task: Mapping[str, Any], allowed_edits: frozenset[str],
) -> bool:
    """Ladder rows 11 and 13-17: the version-2 members, and their ties to the version-1 ones.

    Row 11 is the rule that makes the measurement's version a checked function of the corpus rather
    than a value a producer may choose: a task whose declared adapter is
    `scripts/prompt-repair-adapter.py` must emit version 2, and any other adapter must emit
    version 1. The measurement's version is decoupled from `PROMPT_TASK_ROW`'s, which does not move;
    this rule is what keeps the decoupling deterministic.
    """
    declared = list(task.get("argv") or [])
    expects_two = len(declared) == 2 and declared[1] == REPAIR_ADAPTER_RELATIVE
    if (value["schema_version"] == 2) != expects_two:
        return False
    if value["schema_version"] == 1:
        # Ladder row 10 at version 1: absence is required, never defaulted. The field-tuple check
        # in `valid_task_measurement` already rejects a stray key on a document that reached it
        # through the adapter boundary; stating it here as well makes this function total, so the
        # rule has an addressable owner rather than an emergent one.
        return not any(name in value for name in TASK_MEASUREMENT_V2_MEMBERS)
    identity = value.get("base_adapter_runtime_identity")
    if (
        not isinstance(identity, str)
        or not identity.startswith("PYTHON:")
        or not valid_hex(identity[7:])
    ):
        return False
    # Row 13. The patch digest is present exactly when a patch reached the validation runner, which
    # `patch_size_bytes` already records; a digest without bytes, or bytes without a digest, is a
    # producer defect rather than a permitted shape.
    if (value.get("patch_sha256") is not None) != (value["patch_size_bytes"] > 0):
        return False
    if value.get("patch_sha256") is not None and not valid_hex(value["patch_sha256"]):
        return False
    blocks = value.get("edit_set")
    total = value.get("edit_set_total_bytes")
    if (blocks is None) != (total is None):
        return False
    if blocks is None:
        return True
    if not isinstance(blocks, list) or not blocks or len(blocks) > MAXIMUM_FILE_BLOCKS:
        return False
    if not all(valid_edit_set_block(block, allowed_edits) for block in blocks):
        return False
    paths = [block["path"] for block in blocks]
    if paths != sorted(paths) or len(set(paths)) != len(paths):
        return False
    if (
        not isinstance(total, int) or isinstance(total, bool)
        or total != sum(block["body_bytes"] for block in blocks)
    ):
        return False
    # Row 17, the cheapest cross-check in the design and the most valuable. `diagnostic_summary` is
    # produced by the frozen sequencing from `applied_edits`, and `edit_set` is produced from the
    # same `edits` list, so a divergence means the section 3.2 near-copy diverged.
    marker = "applied edits: "
    summary = value["diagnostic_summary"]
    if marker in summary:
        named = [item for item in summary.rsplit(marker, 1)[1].split(", ") if item]
        if named != paths:
            return False
    return True


def classify_task_drift(
    environment_probe: Mapping[str, Any],
    artifact_digests: Sequence[Mapping[str, Any]],
    baseline_environment_probe: Mapping[str, Any],
    baseline_artifact_digests: Sequence[Mapping[str, Any]],
) -> str:
    if environment_probe != baseline_environment_probe:
        return "ENVIRONMENT_DRIFT"
    if artifact_digests != baseline_artifact_digests:
        return "INPUT_DRIFT"
    return "NONE"


def invocation_workspace_entries(*paths: Path) -> list[str]:
    """Return the exact current invocation namespace admitted by both snapshots."""
    return sorted(path.name for path in paths)


def invoke_snapshot(
    task: Mapping[str, Any], request_path: Path, result_path: Path, project: Path,
    environment: Mapping[str, str], environment_probe: Mapping[str, Any],
    owned_paths: set[Path],
) -> dict[str, Any]:
    descriptor = -1
    try:
        descriptor = create_owned_output(result_path, owned_paths)
        argv, helper = command(task, "snapshot_argv", project)
        argv = argv + [
            "--snapshot-request", str(request_path), "--result", str(result_path),
            "--result-fd", str(descriptor),
        ]
        completed = run_child(
            argv,
            project / task["cwd"],
            environment,
            max(nested_owner_timeout(task["timeout_ns"]), SNAPSHOT_HELPER_OUTER_TIMEOUT_NS),
            0,
            (descriptor, helper.descriptor),
        )
        helper.verify_unchanged(task["snapshot_helper_runtime"][7:])
        helper.close()
        helper = None
        os.close(descriptor)
        descriptor = -1
        if completed.returncode != 0 or completed.stdout or completed.stderr:
            raise EvaluationError("snapshot helper process failed")
        result = load_bound(result_path, "SNAPSHOT_RESULT", SNAPSHOT_LIMIT)
        snapshot_request = load_bound(request_path, "SNAPSHOT_REQUEST", SNAPSHOT_LIMIT)
        if not valid_snapshot_result(result, task["task_id"], snapshot_request, project):
            raise EvaluationError("snapshot helper result is invalid")
        return result
    except ChildBoundaryError as failure:
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
    finally:
        if "helper" in locals() and helper is not None:
            helper.close()
        if descriptor >= 0:
            os.close(descriptor)


def invoke_adapter(
    task: Mapping[str, Any], adapter_request: Mapping[str, Any], request_path: Path,
    variant_path: Path, rendered_path: Path, measurement_path: Path,
    project: Path, environment: Mapping[str, str], provider_timeout_ns: int, sample: int, seed: int,
    prompt_oversized: bool, owned_paths: set[Path], allowed_edits: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    descriptor = -1
    try:
        descriptor = create_owned_output(measurement_path, owned_paths)
        argv, helper = command(task, "argv", project)
        argv = argv + [
            "--prompt-variant", str(variant_path), "--rendered-prompt", str(rendered_path),
            "--sample-index", str(sample), "--paired-seed", str(seed),
            "--adapter-request", str(request_path), "--result", str(measurement_path),
            "--result-fd", str(descriptor),
        ]
        completed = run_child(
            argv,
            project / task["cwd"],
            environment,
            nested_owner_timeout(task["timeout_ns"] + provider_timeout_ns),
            0,
            (descriptor, helper.descriptor),
        )
        helper.verify_unchanged(task["measurement_adapter_runtime"][7:])
        helper.close()
        helper = None
    except ChildBoundaryError as failure:
        cleanup_passed = retire_owned_path(measurement_path, owned_paths)
        if not cleanup_passed:
            raise AdapterFailure("CLEANUP_FAILED", "measurement artifact cleanup failed") from None
        if failure.reason == "CLEANUP":
            raise AdapterFailure("CLEANUP_FAILED", "measurement adapter cleanup failed") from None
        if failure.reason == "TIMEOUT":
            raise AdapterFailure("ADAPTER_TIMEOUT", "measurement adapter timed out") from None
        if failure.reason == "OUTPUT":
            raise AdapterFailure("ADAPTER_PROCESS_OUTPUT", "measurement adapter produced process output") from None
        raise AdapterFailure("ADAPTER_RESULT", "measurement adapter process failed") from None
    except OSError:
        raise AdapterFailure("ADAPTER_RESULT", "measurement result path is occupied or unavailable") from None
    finally:
        if "helper" in locals() and helper is not None:
            helper.close()
        if descriptor >= 0:
            os.close(descriptor)
    if completed.returncode != 0 or completed.stdout or completed.stderr:
        if not retire_owned_path(measurement_path, owned_paths):
            raise AdapterFailure("CLEANUP_FAILED", "measurement artifact cleanup failed")
        raise AdapterFailure("ADAPTER_RESULT", "measurement adapter process failed")
    try:
        measurement = load_bound(
            measurement_path, "TASK_MEASUREMENT", MEASUREMENT_LIMIT, versions=(1, 2),
        )
        if not valid_task_measurement(
            measurement, task, adapter_request["rendered_prompt_sha256"], adapter_request, sample, seed,
            prompt_oversized=prompt_oversized, allowed_edits=allowed_edits,
        ):
            raise EvaluationError("measurement adapter result is semantically invalid")
    except (EvaluationError, OSError, TypeError, ValueError, KeyError):
        if not retire_owned_path(measurement_path, owned_paths):
            raise AdapterFailure("CLEANUP_FAILED", "measurement artifact cleanup failed") from None
        raise AdapterFailure("ADAPTER_RESULT", "measurement adapter result is invalid") from None
    if not retire_owned_path(measurement_path, owned_paths):
        raise AdapterFailure("CLEANUP_FAILED", "measurement artifact cleanup failed")
    return measurement


def prepare_pair(
    result: dict[str, Any],
    trust: Mapping[str, Any],
    expected_inputs: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    bind(result)
    if not canonical_fits(result, RESULT_LIMIT):
        compact_oversized_result(result, expected_inputs)
        bind(result)
    evidence = bind({
        # The evidence container moves in lockstep with the result: it carries
        # `PROMPT_EXPECTED_INPUT_DIGEST` records that are now one per attempt, so a document's
        # members and its container share one version exactly as the result's rows do.
        "schema_version": 2,
        "artifact_kind": "PROMPT_EVALUATION_EVIDENCE",
        "evaluation_id": result["evaluation_id"],
        "evaluation_result_sha256": result["content_sha256"],
        "trust": trust,
        "expected_inputs": expected_inputs,
        "content_sha256": "",
    })
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
        "schema_version": 2,
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


def invalid_result_only(
    evaluation_id: str,
    sample_count: Any,
    error_code: str,
    error: str,
) -> dict[str, Any]:
    safe_evaluation_id = (
        evaluation_id
        if valid_ascii_identifier(evaluation_id) and "/" not in evaluation_id and evaluation_id not in (".", "..")
        else None
    )
    result = {
        "schema_version": 2,
        "artifact_kind": "PROMPT_EVALUATION_RESULT",
        "evaluation_id": safe_evaluation_id,
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
    return result


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
        # A document's rows all carry the container's version. The two frozen version-1
        # documents stay uniformly version 1 and decodable forever; nothing is ever migrated.
        "schema_version": 2,
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
    if tuple(value) != SOURCE_RESULT_FIELDS or value.get("status") not in ("COMPLETE", "UNAVAILABLE"):
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
        value.get("error_code") == "GIT_UNAVAILABLE"
        and isinstance(value.get("error"), str)
        and 0 < len(value["error"].encode("utf-8")) <= 4096
        and all(value.get(reachability) == "UNVERIFIED" and value.get(observed) is None for reachability, observed in fields)
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
    if "credential" in detail:
        # `MISSING_CREDENTIAL` is the section 5 code for an absent or empty credential, not for
        # every message that happens to mention one. A declared name that conflicts with the
        # environment policy is an invalid declaration and takes the same `INVALID_SCHEMA` code as
        # a malformed or oversized name, so a first-substring match cannot mislabel it.
        return "MISSING_CREDENTIAL" if "missing" in detail or "empty" in detail else "INVALID_SCHEMA"
    if "identifier" in detail:
        return "INVALID_ID"
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


def canonical_file_expectation(relative: str, metadata: os.stat_result, content_sha256: str) -> str:
    mode = f"{stat.S_IFMT(metadata.st_mode) | stat.S_IMODE(metadata.st_mode):06o}"
    raw = f"{mode} {relative}".encode("utf-8") + b"\0F " + content_sha256.encode("ascii") + b"\n"
    return hashlib.sha256(raw).hexdigest()


def bounded_declared_tree(
    project: Path, relative: str, maximum_entries: int = 128,
    maximum_bytes: int = ARTIFACT_LIMIT,
) -> tuple[list[str], int, int]:
    root = relative_path(project, relative)
    root_metadata = os.lstat(root)
    if not stat.S_ISDIR(root_metadata.st_mode) or stat.S_ISLNK(root_metadata.st_mode):
        raise EvaluationError("task source tree root is unsafe")
    files: list[str] = []
    entry_count = 1
    byte_count = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        entries = []
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if entry_count + len(entries) >= maximum_entries:
                    raise EvaluationError("task source tree exceeds its entry cap")
                entries.append(entry)
        entries.sort(key=lambda item: os.fsencode(item.name))
        for entry in entries:
            metadata = entry.stat(follow_symlinks=False)
            entry_count += 1
            path = Path(entry.path)
            if stat.S_ISDIR(metadata.st_mode):
                pending.append(path)
            elif stat.S_ISREG(metadata.st_mode):
                byte_count += metadata.st_size
                if byte_count > maximum_bytes:
                    raise EvaluationError("task source tree exceeds its byte cap")
                files.append(str(path.relative_to(project)))
            else:
                raise EvaluationError("task source tree contains an unsafe entry")
    return files, entry_count, byte_count


def declared_source_files(
    tasks: Sequence[Mapping[str, Any]], task_files: Sequence[str], project: Path,
) -> tuple[dict[str, str | None], set[str]]:
    declared: dict[str, str | None] = {relative: None for relative in task_files}
    execution: set[str] = set()
    for task in tasks:
        expanded_entries = 0
        expanded_bytes = 0
        execution.update((task["argv"][1], task["snapshot_argv"][1]))
        for expectation in task["artifacts"]:
            relative = expectation["path"]
            if expectation["kind"] == "FILE":
                metadata = os.lstat(relative_path(project, relative))
                if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                    raise EvaluationError("task source file is unsafe")
                expanded_entries += 1
                expanded_bytes += metadata.st_size
                if expanded_entries > 128 or expanded_bytes > ARTIFACT_LIMIT:
                    raise EvaluationError("task source artifacts exceed their cap")
                declared[relative] = expectation["expected_sha256"]
                continue
            if expanded_entries >= 128:
                raise EvaluationError("task source artifacts exceed their cap")
            files, entries, byte_count = bounded_declared_tree(
                project, relative, 128 - expanded_entries, ARTIFACT_LIMIT - expanded_bytes,
            )
            expanded_entries += entries
            expanded_bytes += byte_count
            if expanded_entries > 128 or expanded_bytes > ARTIFACT_LIMIT:
                raise EvaluationError("task source artifacts exceed their cap")
            for path in files:
                declared[path] = None
    return declared, execution


def git_member(
    source: Path, relative: str, revision: str, git: RetainedRegularFile,
    environment: Mapping[str, str], content_sha256: str, source_mode: int,
) -> bool:
    completed = run_child(
        [
            git.process_path(), "--no-pager", "-c", "core.fsmonitor=false",
            "-c", "core.hooksPath=/dev/null", "-c", "diff.external=",
            "-c", "credential.helper=", "ls-tree", "-z", "--full-tree", revision, "--", relative,
        ],
        source,
        environment,
        SOURCE_VERIFIER_OUTER_TIMEOUT_NS,
        8192,
        (git.descriptor,),
    )
    if completed.returncode != 0 or completed.stderr:
        raise EvaluationError("corpus Git membership query failed")
    suffix = b"\t" + relative.encode("utf-8") + b"\0"
    if not completed.stdout.endswith(suffix) or completed.stdout.count(b"\0") != 1:
        return False
    header = completed.stdout[:-len(suffix)]
    fields = header.split(b" ")
    if (
        len(fields) != 3 or fields[1] != b"blob"
        or fields[0] != f"{source_mode:06o}".encode("ascii")
        or len(fields[2]) not in (40, 64)
        or any(byte not in b"0123456789abcdef" for byte in fields[2])
    ):
        return False
    blob = run_child(
        [git.process_path(), "--no-pager", "-c", "core.fsmonitor=false",
         "-c", "core.hooksPath=/dev/null", "cat-file", "blob", fields[2].decode("ascii")],
        source,
        environment,
        SOURCE_VERIFIER_OUTER_TIMEOUT_NS,
        ARTIFACT_LIMIT,
        (git.descriptor,),
    )
    if blob.returncode != 0 or blob.stderr:
        raise EvaluationError("corpus Git blob query failed")
    return hashlib.sha256(blob.stdout).hexdigest() == content_sha256


def file_set_members(raw: bytes) -> dict[str, tuple[int, str]]:
    prefix = b"ALIGN-LLM-CORPUS-FILE-SET-V1\n"
    if not raw.startswith(prefix):
        raise EvaluationError("corpus file-set manifest is malformed")
    cursor = len(prefix)
    newline = raw.find(b"\n", cursor)
    if newline < 0:
        raise EvaluationError("corpus file-set manifest is malformed")
    try:
        count = int(raw[cursor:newline].decode("ascii"))
    except (UnicodeError, ValueError):
        raise EvaluationError("corpus file-set manifest is malformed") from None
    cursor = newline + 1
    members: dict[str, tuple[int, str]] = {}
    for _ in range(count):
        mode_end = raw.find(b" ", cursor)
        count_end = raw.find(b" ", mode_end + 1)
        if mode_end < 0 or count_end < 0:
            raise EvaluationError("corpus file-set manifest is malformed")
        try:
            mode = int(raw[cursor:mode_end], 8)
            path_count = int(raw[mode_end + 1:count_end].decode("ascii"))
        except (UnicodeError, ValueError):
            raise EvaluationError("corpus file-set manifest is malformed") from None
        start = count_end + 1
        end = start + path_count
        if raw[end:end + 3] != b"\0F " or end + 68 > len(raw) or raw[end + 67:end + 68] != b"\n":
            raise EvaluationError("corpus file-set manifest is malformed")
        try:
            relative = raw[start:end].decode("utf-8", "strict")
            content = raw[end + 3:end + 67].decode("ascii", "strict")
        except UnicodeError:
            cursor = end + 68
            continue
        members[relative] = (mode, content)
        cursor = end + 68
    if cursor != len(raw):
        raise EvaluationError("corpus file-set manifest is malformed")
    return members


def verify_task_source_membership(
    request: Mapping[str, Any], tasks: Sequence[Mapping[str, Any]], project: Path,
    task_files: Sequence[str] = (), policy: Mapping[str, Any] | None = None,
    trust: Mapping[str, Any] | None = None, environment: Mapping[str, str] | None = None,
) -> None:
    strict = trust is not None and trust.get("corpus_reachability") == "VERIFIED"
    declared, execution = declared_source_files(tasks, task_files if strict else (), project)
    if not execution.issubset(declared):
        raise EvaluationError("task execution helper is absent from reviewed task source")
    if FIXED_ADAPTER_PATH not in declared or FIXED_SNAPSHOT_HELPER_PATH not in declared:
        raise EvaluationError("fixed evaluator helpers are absent from reviewed task source")
    try:
        source = physical_directory(Path(request["verifier_corpus_source_path"]))
    except (EvaluationError, OSError):
        if strict:
            raise
        return
    file_set: dict[str, tuple[int, str]] = {}
    git: RetainedRegularFile | None = None
    if strict and request["verifier_corpus_source_kind"] == "FILE_SET":
        manifest = request.get("verifier_corpus_file_set_manifest_path")
        if not isinstance(manifest, str):
            raise EvaluationError("corpus file-set manifest is unavailable")
        manifest_file = RetainedRegularFile(Path(manifest), 8_388_608)
        try:
            file_set = file_set_members(manifest_file.read_bytes())
            manifest_file.verify_unchanged(request["verifier_corpus_source_sha256"])
        finally:
            manifest_file.close()
    elif strict:
        if policy is None or environment is None:
            raise EvaluationError("corpus Git membership policy is unavailable")
        git = RetainedRegularFile(Path(request["verifier_git_executable_path"]), RESULT_LIMIT)
        if git.sha256() != policy["git_executable_sha256"]:
            git.close()
            raise EvaluationError("corpus Git executable identity disagrees")
    try:
        for relative, expected in declared.items():
            project_file = RetainedRegularFile(relative_path(project, relative), ARTIFACT_LIMIT)
            source_file = RetainedRegularFile(relative_path(source, relative), ARTIFACT_LIMIT)
            try:
                project_sha = project_file.sha256()
                source_sha = source_file.sha256()
                project_metadata = os.fstat(project_file.descriptor)
                source_metadata = os.fstat(source_file.descriptor)
                if project_sha != source_sha or project_metadata.st_mode != source_metadata.st_mode:
                    raise EvaluationError("task execution source is not a reviewed corpus member")
                if expected is not None and canonical_file_expectation(relative, project_metadata, project_sha) != expected:
                    raise EvaluationError("task source artifact digest does not match")
                if strict and request["verifier_corpus_source_kind"] == "FILE_SET":
                    member = file_set.get(relative)
                    mode = stat.S_IFMT(source_metadata.st_mode) | stat.S_IMODE(source_metadata.st_mode)
                    if member != (mode, source_sha):
                        raise EvaluationError("task source is absent from the verified file set")
                elif strict and git is not None and not git_member(
                    source, relative, request["verifier_corpus_source_sha256"], git, environment,
                    source_sha, stat.S_IFMT(source_metadata.st_mode) | stat.S_IMODE(source_metadata.st_mode),
                ):
                    raise EvaluationError("task source is absent from the verified Git commit")
            finally:
                source_file.close()
                project_file.close()
    finally:
        if git is not None:
            git.verify_unchanged(policy["git_executable_sha256"])
            git.close()


def validated_task_files(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) < 1
        or len(value) > 64
        or not all(isinstance(item, str) for item in value)
    ):
        raise EvaluationError("corpus task count is invalid")
    return value


def static_expectation_paths(task: Mapping[str, Any]) -> set[str]:
    """Every path a declared static expectation already covers, file or tree member."""
    covered: set[str] = set()
    for expectation in task.get("artifacts") or []:
        if not isinstance(expectation, dict) or not isinstance(expectation.get("path"), str):
            continue
        covered.add(expectation["path"])
    return covered


def inside_declared_tree(task: Mapping[str, Any], relative: str) -> bool:
    return any(
        isinstance(expectation, dict)
        and expectation.get("kind") == "TREE"
        and isinstance(expectation.get("path"), str)
        and relative.startswith(f"{expectation['path']}/")
        for expectation in task.get("artifacts") or []
    )


def automatic_snapshot_files(
    request: Mapping[str, Any], task_file: str, task: Mapping[str, Any], project: Path,
) -> list[str]:
    declared = {
        request["experiment_path"], request["parent_activation_path"], request["corpus_path"],
        request["acceptance_policy_path"], request["workspace_preflight_path"],
        request["verifier_source_policy_path"], ".align-revision", task_file,
        task["generation_policy_path"], task["provider_control_path"], task["environment_policy_path"],
        task["task_prompt_path"], task["context_sources_path"],
    }
    # The manifest's `artifacts` array is mandatory and closed and already covers the task
    # prompt/context artifacts, so a manifest that declares them would otherwise make the request's
    # expanded paths overlap, which is invalid. A static expectation wins: it carries the reviewed
    # digest, and dropping the duplicate keeps exactly one record per path.
    declared -= static_expectation_paths(task)
    declared = {item for item in declared if not inside_declared_tree(task, item)}
    paths = sorted(declared, key=os.fsencode)
    for relative in paths:
        RetainedRegularFile(relative_path(project, relative), ARTIFACT_LIMIT).close()
    if len(paths) > 29:
        raise EvaluationError("automatic snapshot input count exceeds its bound")
    return paths


def score_median(values: list[int]) -> int | None:
    if not values:
        return None
    values.sort()
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    lower = values[middle - 1]
    return lower + (values[middle] - lower) // 2


def time_metrics(parent: int | None, candidate: int | None) -> tuple[int | None, int | None]:
    if parent is None or candidate is None or parent <= 0:
        return None, None
    if candidate <= parent:
        return (parent - candidate) * 1_000_000 // parent, 0
    return 0, (candidate - parent) * 1_000_000 // parent


def reason(
    task_id: str, sample: int, code: str, parent: str, candidate: str, limit: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id, "sample_index": sample, "code": code,
        "parent_value": parent, "candidate_value": candidate, "limit": limit,
    }


def row_repair_loop_count(row: Mapping[str, Any]) -> int:
    """One producer per field, selected by version and never by presence.

    A version-1 row has no row-level `repair_loop_count` and must not be given a compatibility
    default for one: its authority is, and stays, `row.measurement.repair_loop_count`.
    """
    if row["schema_version"] >= 2:
        return row["repair_loop_count"]
    return row["measurement"]["repair_loop_count"]


def row_generation_ns(row: Mapping[str, Any]) -> int | None:
    if row["schema_version"] >= 2:
        return row.get("generation_to_passing_patch_ns")
    return row["measurement"]["generation_to_passing_patch_ns"]


def row_repair_attempted(row: Mapping[str, Any]) -> bool:
    return row["schema_version"] >= 2 and row["repair_loop_count"] >= 1


def row_repair_editset_attempts(row: Mapping[str, Any]) -> int:
    """Section 3.8: repair attempts on this row whose prompt actually carried `EDITSET`.

    A repair attempt contributes when it ran — not `SKIPPED` — and its own
    `repair_prompt_source.included_sections` names `EDITSET`. It is a **denominator**, never a gate
    input: a row that dropped `EDITSET` under the budget ladder is excluded from every edit-set
    claim by a persisted number rather than by an argument.
    """
    if row["schema_version"] < 2:
        return 0
    total = 0
    for attempt in row["attempts"]:
        if attempt["attempt_kind"] != "REPAIR" or attempt["status"] == "SKIPPED":
            continue
        source = attempt.get("repair_prompt_source") or {}
        if "EDITSET" in (source.get("included_sections") or []):
            total += 1
    return total


def row_repair_recovered(row: Mapping[str, Any]) -> bool:
    """The section 1.4 gate predicate, evaluated on one row."""
    if row["schema_version"] < 2:
        return False
    attempts = row["attempts"]
    return (
        len(attempts) == 2
        and attempts[0]["attempt_kind"] == "INITIAL" and attempts[0]["status"] == "FAIL"
        and attempts[1]["attempt_kind"] == "REPAIR" and attempts[1]["status"] == "PASS"
    )


def status_value(measurement: Mapping[str, Any]) -> str:
    status = measurement["status"]
    if status == "POLICY_VIOLATION":
        return "POLICY_VIOLATION"
    return status


def complete_score(
    tasks: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]], sample_count: int,
    policy: Mapping[str, Any], trust: Mapping[str, Any], environment: Mapping[str, Any],
    provider_control: Mapping[str, Any],
) -> tuple[str, bool, list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    aggregates: list[dict[str, Any]] = []
    indexed: list[dict[int, dict[str, Mapping[str, Any]]]] = []
    corpus_parent_times: list[int] = []
    corpus_candidate_times: list[int] = []
    corpus_parent_repairs = 0
    corpus_candidate_repairs = 0
    corpus_repair_attempts = 0
    corpus_repair_recoveries = 0
    corpus_repair_recovery_paired = 0
    corpus_repair_editset = 0
    editset_corpus = any(expected_template_kinds(task) == REPAIR_SECTION_KINDS for task in tasks)
    parent_passes = 0
    candidate_passes = 0
    paired_passes = 0
    for task in tasks:
        selected = [row for row in rows if row["task_id"] == task["task_id"]]
        pairs: dict[int, dict[str, Mapping[str, Any]]] = {}
        for row in selected:
            pairs.setdefault(row["sample_index"], {})[row["variant"]] = row
        if len(pairs) != sample_count or any(set(pair) != {"PARENT", "CANDIDATE"} for pair in pairs.values()):
            raise EvaluationError("complete score row schedule is invalid")
        indexed.append(pairs)
        parent_rows = [pairs[sample]["PARENT"] for sample in range(1, sample_count + 1)]
        candidate_rows = [pairs[sample]["CANDIDATE"] for sample in range(1, sample_count + 1)]
        task_parent_passes = sum(row["measurement"]["status"] == "PASS" for row in parent_rows)
        task_candidate_passes = sum(row["measurement"]["status"] == "PASS" for row in candidate_rows)
        task_parent_repairs = sum(row_repair_loop_count(row) for row in parent_rows)
        task_candidate_repairs = sum(row_repair_loop_count(row) for row in candidate_rows)
        parent_attempted = sum(row_repair_attempted(row) for row in parent_rows)
        candidate_attempted = sum(row_repair_attempted(row) for row in candidate_rows)
        parent_recovered = sum(row_repair_recovered(row) for row in parent_rows)
        candidate_recovered = sum(row_repair_recovered(row) for row in candidate_rows)
        parent_editset = sum(row_repair_editset_attempts(row) for row in parent_rows)
        candidate_editset = sum(row_repair_editset_attempts(row) for row in candidate_rows)
        # A (task, variant) pair counts only when *every* paired sample recovered, so a single
        # lucky sample is not a reproducible recovery.
        parent_paired_recovery = bool(parent_rows) and all(row_repair_recovered(row) for row in parent_rows)
        candidate_paired_recovery = bool(candidate_rows) and all(row_repair_recovered(row) for row in candidate_rows)
        task_parent_times: list[int] = []
        task_candidate_times: list[int] = []
        task_paired = 0
        for sample in range(1, sample_count + 1):
            parent_row = pairs[sample]["PARENT"]
            candidate_row = pairs[sample]["CANDIDATE"]
            if parent_row["measurement"]["status"] == "PASS" and candidate_row["measurement"]["status"] == "PASS":
                task_paired += 1
                task_parent_times.append(parent_row["time_to_passing_patch_ns"])
                task_candidate_times.append(candidate_row["time_to_passing_patch_ns"])
        parent_median = score_median(task_parent_times)
        candidate_median = score_median(task_candidate_times)
        improvement, regression = time_metrics(parent_median, candidate_median)
        aggregates.append({
            "task_id": task["task_id"], "parent_pass_count": task_parent_passes,
            "candidate_pass_count": task_candidate_passes,
            "parent_repair_loop_count": task_parent_repairs,
            "candidate_repair_loop_count": task_candidate_repairs, "paired_pass_count": task_paired,
            "parent_paired_median_time_ns": parent_median,
            "candidate_paired_median_time_ns": candidate_median,
            "time_improvement_ppm": improvement, "time_regression_ppm": regression,
            "parent_repair_attempt_count": parent_attempted,
            "candidate_repair_attempt_count": candidate_attempted,
            "parent_repair_recovery_count": parent_recovered,
            "candidate_repair_recovery_count": candidate_recovered,
            "repair_recovery_paired": parent_paired_recovery or candidate_paired_recovery,
        })
        if editset_corpus:
            aggregates[-1].update({
                "parent_repair_editset_attempt_count": parent_editset,
                "candidate_repair_editset_attempt_count": candidate_editset,
            })
        corpus_repair_editset += parent_editset + candidate_editset
        corpus_repair_attempts += parent_attempted + candidate_attempted
        corpus_repair_recoveries += parent_recovered + candidate_recovered
        corpus_repair_recovery_paired += int(parent_paired_recovery) + int(candidate_paired_recovery)
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
        "task_count": len(tasks), "sample_count": sample_count, "parent_pass_count": parent_passes,
        "candidate_pass_count": candidate_passes, "parent_repair_loop_count": corpus_parent_repairs,
        "candidate_repair_loop_count": corpus_candidate_repairs, "paired_pass_count": paired_passes,
        "parent_paired_median_time_ns": parent_median,
        "candidate_paired_median_time_ns": candidate_median,
        "completion_gain_count": candidate_passes - parent_passes,
        "time_improvement_ppm": improvement, "time_regression_ppm": regression,
        "repair_loop_regression_count": repair_regression,
        # The C4 gate quantity and its two denominators. The gate consumes
        # `repair_recovery_paired_count` only; `status` and `gate_eligible` stay the C6 acceptance
        # verdict and are recorded alongside as secondary evidence, never as the C4 claim.
        "repair_attempt_count": corpus_repair_attempts,
        "repair_recovery_count": corpus_repair_recoveries,
        "repair_recovery_paired_count": corpus_repair_recovery_paired,
    }
    if editset_corpus:
        # C4-REPAIR-EDITSET's denominator: repair attempts whose prompt actually carried `EDITSET`.
        # The gate still consumes `repair_recovery_paired_count` only.
        #
        # Present only for a corpus whose adapter can render the section. A `canonical-v1r`
        # template declares no `EDITSET` kind, so the quantity is undefined for it rather than
        # zero, and `eval/prompt/c4-repair-gate/` is a merged version-2 document written before
        # this capability existed. Presence follows the corpus's adapter, exactly as ladder row
        # 11's measurement version does.
        corpus["repair_editset_attempt_count"] = corpus_repair_editset
    reasons: list[dict[str, Any]] = []
    if repair_regression > policy["maximum_repair_loop_regression_count"]:
        reasons.append(reason(
            "CORPUS", 0, "REPAIR_LOOPS", str(corpus_parent_repairs), str(corpus_candidate_repairs),
            str(policy["maximum_repair_loop_regression_count"]),
        ))
    if regression is not None and regression > policy["maximum_time_regression_ppm"]:
        reasons.append(reason(
            "CORPUS", 0, "TIME", str(parent_median), str(candidate_median),
            str(policy["maximum_time_regression_ppm"]),
        ))
    for ordinal, task in enumerate(tasks):
        aggregate = aggregates[ordinal]
        limit = task["regression_limits"]
        task_regression = aggregate["time_regression_ppm"]
        if task_regression is not None and task_regression > policy["maximum_time_regression_ppm"]:
            reasons.append(reason(
                task["task_id"], 0, "TIME", str(aggregate["parent_paired_median_time_ns"]),
                str(aggregate["candidate_paired_median_time_ns"]), str(policy["maximum_time_regression_ppm"]),
            ))
        for sample in range(1, sample_count + 1):
            parent_row = indexed[ordinal][sample]["PARENT"]
            candidate_row = indexed[ordinal][sample]["CANDIDATE"]
            parent = parent_row["measurement"]
            candidate = candidate_row["measurement"]
            candidate_value = status_value(candidate)
            # Variant-symmetric from version 2 on. The check was candidate-only while repair was
            # unreachable, so a PARENT row exceeding its task's declared cap was checked nowhere.
            # With repair enabled on both arms that hole becomes reachable. Every version-1 row in
            # existence carries `repair_loop_count: 0` against a limit of `0`, so extending the
            # check is vacuous on the frozen chain and no version-1 verdict changes. The candidate
            # record keeps its exact existing shape; the parent arm gets a distinguishable one.
            parent_loops = row_repair_loop_count(parent_row)
            if parent_loops > limit["maximum_repair_loops"]:
                reasons.append(reason(
                    task["task_id"], sample, "REPAIR_LOOPS", str(parent_loops), "NONE",
                    str(limit["maximum_repair_loops"]),
                ))
            if parent["status"] == "PASS" and candidate["status"] != "PASS":
                reasons.append(reason(task["task_id"], sample, "PASS_TO_FAIL", "PASS", candidate_value, "NONE"))
            if parent["build_status"] == "PASS" and candidate["build_status"] != "PASS":
                reasons.append(reason(task["task_id"], sample, "BUILD", "PASS", candidate_value, "NONE"))
            if parent["test_status"] == "PASS" and candidate["test_status"] != "PASS":
                reasons.append(reason(task["task_id"], sample, "TEST", "PASS", candidate_value, "NONE"))
            if candidate["status"] == "POLICY_VIOLATION":
                reasons.append(reason(task["task_id"], sample, "POLICY", "NONE", "POLICY_VIOLATION", "NONE"))
            for field, maximum, code in (
                ("unrelated_diff_count", "maximum_unrelated_diff_count", "UNRELATED_DIFF"),
                ("public_api_change_count", "maximum_public_api_change_count", "PUBLIC_API"),
                ("patch_size_bytes", "maximum_patch_size_bytes", "PATCH_SIZE"),
            ):
                if candidate[field] > limit[maximum]:
                    reasons.append(reason(
                        task["task_id"], sample, code, "NONE", str(candidate[field]), str(limit[maximum]),
                    ))
            candidate_loops = row_repair_loop_count(candidate_row)
            if candidate_loops > limit["maximum_repair_loops"]:
                reasons.append(reason(
                    task["task_id"], sample, "REPAIR_LOOPS", "NONE", str(candidate_loops),
                    str(limit["maximum_repair_loops"]),
                ))
            benchmark_limit = limit["maximum_benchmark_regression_ppm"]
            benchmark = candidate["benchmark_regression_ppm"]
            if candidate["status"] == "PASS" and benchmark_limit is not None and benchmark > benchmark_limit:
                reasons.append(reason(
                    task["task_id"], sample, "BENCHMARK", "NONE", str(benchmark), str(benchmark_limit),
                ))
    if reasons:
        status = "SERIOUS_REGRESSION"
    else:
        completion = corpus["completion_gain_count"] >= policy["minimum_completion_gain_count"]
        timing = (
            candidate_passes == parent_passes
            and all(item["candidate_pass_count"] >= item["parent_pass_count"] for item in aggregates)
            and corpus_candidate_repairs <= corpus_parent_repairs
            and improvement is not None and improvement >= policy["minimum_time_improvement_ppm"]
        )
        status = "IMPROVED" if completion or timing else "NO_IMPROVEMENT"
    gate = (
        status == "IMPROVED" and not reasons and provider_control["provider_kind"] != "FIXTURE"
        and trust["align_llm_reachability"] == "VERIFIED"
        and trust["align_reachability"] == "VERIFIED" and trust["corpus_reachability"] == "VERIFIED"
        and environment["core"]["logical_cpu_count"] is not None
        and len(tasks) >= policy["minimum_task_count"] and sample_count >= policy["minimum_samples_per_variant"]
        and all(row["measurement"]["seed_attestation"]["result"] == "APPLIED" for row in rows)
    )
    return status, gate, aggregates, corpus, reasons


def validated_credential_name(
    control: Mapping[str, Any], environment_policy: Mapping[str, Any],
) -> str | None:
    """Bind the section 5.2 credential-name rule to the declared provider kind."""
    provider_kind = control["provider_kind"]
    api_key_env = control["api_key_env"]
    if provider_kind not in PROVIDER_KINDS:
        raise EvaluationError("provider control kind is not a declared provider")
    if api_key_env is None:
        if provider_kind == "CLOUD_OPENAI":
            raise EvaluationError("provider credential environment name is missing")
        return None
    if provider_kind not in CREDENTIAL_PROVIDER_KINDS:
        raise EvaluationError("provider control kind must not declare an api key environment name")
    if (
        not isinstance(api_key_env, str)
        or ENVIRONMENT_NAME.fullmatch(api_key_env) is None
        or len(api_key_env.encode("utf-8")) > 256
    ):
        raise EvaluationError("provider control api key environment name is malformed")
    if any(item.get("name") == api_key_env for item in environment_policy["allowed_variables"]):
        raise EvaluationError("provider credential environment name duplicates the environment policy")
    return api_key_env


def adapter_child_environment(
    environment_values: Mapping[str, str], credential_env_name: str | None, credential_value: str | None,
) -> dict[str, str]:
    """`env_clear()`, then the ordered policy variables, then exactly one credential entry."""
    environment = dict(environment_values)
    if credential_env_name is not None:
        if credential_env_name in environment:
            raise EvaluationError("provider credential environment name duplicates the environment policy")
        environment[credential_env_name] = credential_value
    return environment


def resolved_credential(name: str | None) -> str | None:
    """Read the named credential exactly once, before the first external call."""
    if name is None:
        return None
    value = os.environ.get(name)
    if not value:
        raise EvaluationError("provider credential environment value is missing or empty")
    return value


def validated_generation_child(request: Mapping[str, Any]) -> Path:
    """Retain the declared generation child as an absolute regular executable with its exact bytes.

    The binary is built, not committed, so it cannot be a corpus member; its reviewed `src/` tree and
    `.align-revision` carry the reviewed-source proof and its per-run identity is this path/digest
    pair. The declared digest must equal the same-descriptor bytes, so neither a stale claim nor an
    unverified local build can be admitted.
    """
    child = Path(request["generation_child_path"])
    try:
        descriptor = os.open(child, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise EvaluationError("generation child is unreadable") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise EvaluationError("generation child is not a regular file")
        if not metadata.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            raise EvaluationError("generation child is not executable")
        hasher = hashlib.sha256()
        offset = 0
        while offset < metadata.st_size:
            chunk = os.pread(descriptor, min(65_536, metadata.st_size - offset), offset)
            if not chunk:
                raise EvaluationError("generation child changed while reading")
            hasher.update(chunk)
            offset += len(chunk)
        after = os.fstat(descriptor)
        if (metadata.st_dev, metadata.st_ino, metadata.st_size) != (after.st_dev, after.st_ino, after.st_size):
            raise EvaluationError("generation child identity disagrees")
        if hasher.hexdigest() != request["generation_child_sha256"]:
            raise EvaluationError("generation child digest disagrees")
    finally:
        os.close(descriptor)
    return child


def validated_repair_template(
    task: Mapping[str, Any], generation: Mapping[str, Any], project: Path,
) -> dict[str, Any] | None:
    """Ladder rows 5 and 6, run before any provider call or workspace mutation.

    A task that offers no repair attempt carries no template and returns `None`; a task that does
    must name a corpus member whose bytes hash to the manifest's `repair_template_sha256`.
    """
    declared = task.get("repair_template_path")
    if declared is None:
        return None
    artifact_paths = {
        expectation.get("path") for expectation in task.get("artifacts", [])
        if isinstance(expectation, dict) and expectation.get("kind") == "FILE"
    }
    if declared not in artifact_paths:
        raise EvaluationError("the repair template is not a corpus member")
    resolved = relative_path(project, declared)
    raw = read_bounded(resolved, ARTIFACT_LIMIT)
    if hashlib.sha256(raw).hexdigest() != task["repair_template_sha256"]:
        raise EvaluationError("the repair template digest disagrees")
    template = load_bound(resolved, "REPAIR_PROMPT_TEMPLATE")
    if not valid_repair_template(template, expected_template_kinds(task)):
        raise EvaluationError("the repair template schema is invalid")
    # Ladder row 6: the prompt budget must at least admit the template's own fixed text, so a
    # budget that can never carry a repair prompt is rejected before the run rather than
    # discovered as a `REPAIR_PROMPT_BUDGET` skip on every row.
    headers = template["section_headers"]
    fixed = len(template["preamble_text"].encode("utf-8")) + len(template["closing_text"].encode("utf-8"))
    fixed += sum(len(headers[kind].encode("utf-8")) + 3 for kind in headers)
    if fixed + REPAIR_STATUS_LIMIT > generation["max_prompt_bytes"]:
        raise EvaluationError("the generation policy prompt budget cannot carry the repair template")
    return template


def validated_evaluation_inputs(request: Mapping[str, Any], project: Path) -> dict[str, Any]:
    if request["sample_count"] < 2 or request["sample_count"] > 16:
        raise EvaluationError("sample count is invalid")

    source_policy = load_bound(relative_path(project, request["verifier_source_policy_path"]), "PROMPT_SOURCE_VERIFIER_POLICY")
    if tuple(source_policy) != SOURCE_POLICY_FIELDS:
        raise EvaluationError("source verifier policy fields are invalid")
    if source_policy["content_sha256"] != request["verifier_source_policy_sha256"]:
        raise EvaluationError("source verifier policy identity disagrees")
    experiment = load_bound(relative_path(project, request["experiment_path"]), "PROMPT_EXPERIMENT_RESULT")
    parent = load_bound(relative_path(project, request["parent_activation_path"]), "PROMPT_ACTIVATION_RESULT")
    corpus = load_bound(relative_path(project, request["corpus_path"]), "PROMPT_EVALUATION_CORPUS")
    acceptance = load_bound(relative_path(project, request["acceptance_policy_path"]), "PROMPT_ACCEPTANCE_POLICY")
    preflight_request = load_bound(relative_path(project, request["workspace_preflight_path"]), "WORKSPACE_PREFLIGHT_REQUEST")
    task_files = validated_task_files(corpus.get("task_files"))
    tasks = [load_bound(relative_path(project, item), "PROMPT_EVALUATION_TASK") for item in task_files]
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
    credential_env_name = validated_credential_name(control, environment_policy)
    credential_value = resolved_credential(credential_env_name)
    generation_child = validated_generation_child(request)
    validate_source_boundary(request, source_policy, project)
    task_inputs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    task_snapshot_files: list[list[str]] = []
    task_repair_templates: list[dict[str, Any] | None] = []
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
        artifact_paths = {
            expectation.get("path") for expectation in task.get("artifacts", [])
            if isinstance(expectation, dict) and expectation.get("kind") == "FILE"
        }
        if (
            len(task["argv"]) != 2
            or task["argv"][0] != task["cmd"]
            or task["argv"][1] not in artifact_paths
            or len(task["snapshot_argv"]) != 2
            or task["snapshot_argv"][0] != task["snapshot_cmd"]
            or task["snapshot_argv"][1] not in artifact_paths
        ):
            raise EvaluationError("task executable is not the fixed reviewed adapter boundary")
        relative_path(project, task["argv"][1])
        relative_path(project, task["snapshot_argv"][1])
        # Every declared measurement input except the generation child is a corpus member and keeps
        # the existing membership, digest, and admission checks unchanged.
        declared_inputs = [
            (task["validation_runner_path"], task["validation_runner_sha256"]),
            (task["task_definition_path"], task["task_definition_sha256"]),
        ]
        if task["patch_path"] is not None:
            declared_inputs.append((task["patch_path"], task["patch_sha256"]))
        for declared_path, declared_sha in declared_inputs:
            if declared_path not in artifact_paths:
                raise EvaluationError("a declared measurement input is not a corpus member")
            resolved = relative_path(project, declared_path)
            if hashlib.sha256(read_bounded(resolved, SNAPSHOT_ARTIFACT_LIMIT)).hexdigest() != declared_sha:
                raise EvaluationError("a declared measurement input digest disagrees")
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
        task_repair_templates.append(validated_repair_template(task, generation, project))
        task_snapshot_files.append(automatic_snapshot_files(
            request, task_files[len(task_snapshot_files)], task, project,
        ))
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
    for task_prompt, context in task_inputs:
        for variant in (parent_variant, candidate):
            render(variant, task_prompt, context)
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
        "credential_env_name": credential_env_name, "credential_value": credential_value,
        "generation_child": generation_child,
        "task_inputs": task_inputs, "task_snapshot_files": task_snapshot_files,
        "task_repair_templates": task_repair_templates,
        "scope": scope, "candidate": candidate,
        "parent_variant": parent_variant, "task_files": task_files,
    }


def evaluate(
    request_path: Path,
    final_result_relative: str,
    final_evidence_relative: str,
    owned_paths: set[Path],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
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
        result = invalid_result_only(
            request.get("evaluation_id", ""),
            request.get("sample_count", 0),
            "INVALID_PATH",
            "evaluation evidence path is invalid",
        )
        return result, None
    try:
        validate_request_source_declaration(request)
        inputs = validated_evaluation_inputs(request, project)
    except (EvaluationError, OSError, TypeError, ValueError, KeyError, IndexError) as failure:
        code = validation_error_code(failure)
        detail = str(failure)[:4096] or "evaluation input is invalid"
        result = invalid_result_only(
            request.get("evaluation_id", ""), request.get("sample_count", 0), code, detail,
        )
        return result, None
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
    # The one-shot credential owner: the name reaches the adapter request, the value reaches only
    # the measurement-adapter child environment, and neither the snapshot helper nor any persisted
    # record ever observes the value.
    credential_env_name = inputs["credential_env_name"]
    generation_child = inputs["generation_child"]
    adapter_environment = adapter_child_environment(
        environment_values, credential_env_name, inputs.pop("credential_value"),
    )
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

    def failed_preflight(error_code: str, detail: str) -> dict[str, Any]:
        return bind({
            "schema_version": 1,
            "artifact_kind": "WORKSPACE_PREFLIGHT_RESULT",
            "evaluation_id": request["evaluation_id"],
            "status": "ERROR",
            "error_code": error_code,
            "error": detail,
            "physical_project_root": "",
            "physical_workspace_path": "",
            "environment_probe": None,
            "content_sha256": "",
        })

    try:
        trust = source_trust(request, source_policy, project, environment_values)
        verify_task_source_membership(
            request, tasks, project, inputs["task_files"], source_policy, trust, environment_values,
        )
    except AdapterFailure as failure:
        preflight = failed_preflight("CLEANUP", failure.detail)
        result = evaluation_result_record(
            result_context, "ERROR", failure.code, failure.detail, preflight, None,
            [], [], [], [], [],
        )
        return prepare_pair(result, trust, [])
    except (EvaluationError, OSError, TypeError, KeyError, ValueError) as failure:
        detail = str(failure)[:4096] or "reviewed source admission failed"
        preflight = failed_preflight("INTERNAL", detail)
        result = evaluation_result_record(
            result_context, "ERROR", "SNAPSHOT_ERROR", detail, preflight, None,
            [], [], [], [], [],
        )
        return prepare_pair(result, trust, [])

    preflight_path = relative_path(project, request["workspace_preflight_path"])
    snapshot_command, preflight_helper = command(first_task, "snapshot_argv", project)
    try:
        completed = run_child(
            snapshot_command + ["--workspace-preflight-request", str(preflight_path)],
            project / first_task["cwd"],
            environment_values,
            max(nested_owner_timeout(first_task["timeout_ns"]), SNAPSHOT_HELPER_OUTER_TIMEOUT_NS),
            65_536,
            (preflight_helper.descriptor,),
        )
        preflight_helper.verify_unchanged(first_task["snapshot_helper_runtime"][7:])
        if completed.returncode != 0 or completed.stderr:
            raise EvaluationError("workspace preflight process failed")
        preflight = json.loads(completed.stdout.decode("utf-8", "strict"))
        normalized_preflight = dict(preflight)
        claimed = normalized_preflight.get("content_sha256")
        normalized_preflight["content_sha256"] = ""
        if (
            not valid_hex(claimed)
            or hashlib.sha256(canonical_digest_bytes(normalized_preflight)).hexdigest() != claimed
            or not valid_workspace_preflight(preflight, request["evaluation_id"])
        ):
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
    finally:
        preflight_helper.close()
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
        return prepare_pair(result, trust, [])
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
        return prepare_pair(result, trust, [])
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

    def finish(
        result: dict[str, Any],
        checkpoint: tuple[int, int, int, int, int, int] | None = None,
        cleanup_diagnosed: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        survivors = cleanup_owned_paths(owned_paths)
        if cleanup_diagnosed or survivors:
            if checkpoint is not None and len(rows) == checkpoint[4]:
                del snapshot_requests[checkpoint[0]:]
                del snapshot_results[checkpoint[1]:]
                del input_snapshots[checkpoint[2]:]
                del attestations[checkpoint[3]:]
                del expected_inputs[checkpoint[5]:]
            detail = (
                result.get("error", "")
                if cleanup_diagnosed and not survivors
                else "evaluator-owned workspace cleanup failed"
            )
            result = evaluation_result("ERROR", "CLEANUP_FAILED", detail)
        return prepare_pair(result, trust, expected_inputs)

    for task_ordinal, task in enumerate(tasks):
        task_prompt, context = task_inputs[task_ordinal]
        automatic_files = inputs["task_snapshot_files"][task_ordinal]
        repair_template = inputs["task_repair_templates"][task_ordinal]
        # The corpus manifest is the cap. A task declaring `0` behaves exactly as it did before
        # C4-REPAIR-MEASURED, which is how `eval/prompt/canonical-v1/` keeps working unchanged.
        repair_limit = min(task["regression_limits"]["maximum_repair_loops"], MAXIMUM_REPAIR_ATTEMPTS)
        baseline_artifact_digests: list[dict[str, Any]] | None = None
        baseline_environment_probe: dict[str, Any] | None = None
        with tempfile.TemporaryDirectory(prefix="prompt-snapshot-request-") as request_directory:
            schedule = []
            for sample in range(1, request["sample_count"] + 1):
                schedule.extend(("PARENT", "CANDIDATE") if sample % 2 else ("CANDIDATE", "PARENT"))
                for variant_name in schedule[-2:]:
                    checkpoint = (
                        len(snapshot_requests), len(snapshot_results), len(input_snapshots),
                        len(attestations), len(rows), len(expected_inputs),
                    )
                    variant = parent_variant if variant_name == "PARENT" else candidate
                    paired_seed = generation["seed_base"] + sample - 1

                    def attest(
                        status: str, error_code: str, detail: str, before_sha: str | None,
                        after_sha: str | None, before_input_sha: str | None,
                        after_input_sha: str | None, request_sha: str,
                    ) -> None:
                        attestations.append(bind({
                            "schema_version": 1,
                            "artifact_kind": "RUN_SNAPSHOT_ATTESTATION",
                            "task_id": task["task_id"],
                            "sample_index": sample,
                            "variant": variant_name,
                            "status": status,
                            "error_code": error_code,
                            "error": detail,
                            "snapshot_request_sha256": request_sha,
                            "before_snapshot_result_sha256": before_sha,
                            "after_snapshot_result_sha256": after_sha,
                            "before_input_snapshot_sha256": before_input_sha,
                            "after_input_snapshot_sha256": after_input_sha,
                            "content_sha256": "",
                        }))

                    def run_attempt(
                        attempt_index: int, rendered_text: str, rendered_text_sha: str,
                        repair_source: dict[str, Any] | None, preparation_ns: int,
                    ) -> dict[str, Any]:
                        """One ordinary adapter invocation against a fresh pinned checkout.

                        Attempt two is not a resumption of attempt one: `eval/runners/run-coding-task.py`
                        builds its own pinned checkout and asserts the fixture fails before the patch,
                        so an independent validation of a different patch is all a second invocation
                        is. That is what makes an evaluator-owned loop possible with the adapter and
                        the runner byte-identical.
                        """
                        nonlocal baseline_artifact_digests, baseline_environment_probe
                        # Fixed-width attempt suffix on a fixed-depth run directory. Nothing
                        # unbounded is concatenated into a run-local name; the prior incident class
                        # is `ENAMETOOLONG`.
                        prefix = f"t{task_ordinal + 1}-s{sample}-{variant_name.lower()}-a{attempt_index}"
                        variant_path = temporary_json(workspace, f"{prefix}-variant.json", variant, owned_paths)
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
                        adapter_request = bind({
                            "schema_version": 1, "artifact_kind": "TASK_ADAPTER_REQUEST",
                            "evaluation_id": request["evaluation_id"], "task_id": task["task_id"], "sample_index": sample,
                            "variant": variant_name, "variant_path": str(variant_path), "variant_sha256": variant["content_sha256"],
                            "rendered_prompt_path": str(rendered_path), "rendered_prompt_sha256": rendered["content_sha256"],
                            "generation_policy_path": str(relative_path(project, task["generation_policy_path"])),
                            "generation_policy_sha256": generation["content_sha256"],
                            "provider_control_path": str(relative_path(project, task["provider_control_path"])),
                            "provider_control_sha256": control["content_sha256"], "workspace_path": str(workspace),
                            "result_path": str(measurement_path), "paired_seed": paired_seed,
                            "credential_env_name": credential_env_name,
                            "environment_policy_sha256": environment_policy["content_sha256"],
                            "validation_runner_path": str(relative_path(project, task["validation_runner_path"])),
                            "validation_runner_sha256": task["validation_runner_sha256"],
                            "task_definition_path": str(relative_path(project, task["task_definition_path"])),
                            "task_definition_sha256": task["task_definition_sha256"],
                            "validation_argv": list(task["validation_argv"]),
                            "patch_path": (
                                None if task["patch_path"] is None
                                else str(relative_path(project, task["patch_path"]))
                            ),
                            "patch_sha256": task["patch_sha256"],
                            "generation_child_path": str(generation_child),
                            "generation_child_sha256": request["generation_child_sha256"],
                            # The task's own deadline bounds the adapter's contained validation runner.
                            # The generation child keeps the provider-control deadline, so the two
                            # sequential inner children stay strictly inside the outer sum below.
                            "task_deadline_ns": task["timeout_ns"],
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
                            "additional_files": automatic_files + [
                                str(variant_path.relative_to(project)),
                                str(rendered_path.relative_to(project)),
                                str(adapter_request_path.relative_to(project)),
                            ],
                            "workspace_path": str(workspace),
                            "allowed_workspace_entries": invocation_workspace_entries(
                                variant_path, rendered_path, adapter_request_path, measurement_path,
                            ),
                            "content_sha256": "",
                        })
                        snapshot_request_path = Path(request_directory) / "request.json"
                        snapshot_request_path.unlink(missing_ok=True)
                        temporary_json(Path(request_directory), "request.json", snapshot_request)
                        snapshot_result_path = Path(request_directory) / f"t{task_ordinal + 1}-snapshot-result.json"
                        before = invoke_snapshot(
                            task, snapshot_request_path, snapshot_result_path, project,
                            environment_values, preflight["environment_probe"],
                            owned_paths,
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
                            attest(
                                "PRECHECK_FAILED", failure_code, failure_detail,
                                before["content_sha256"], None, None, None,
                                snapshot_request["content_sha256"],
                            )
                            raise AbortEvaluation(
                                evaluation_result("ERROR", failure_code, failure_detail), checkpoint,
                                cleanup_diagnosed=failure_code == "CLEANUP_FAILED",
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
                        persistent_paths = set(expected_snapshot_paths({
                            "static_expectations": task["artifacts"],
                            "additional_files": automatic_files,
                        }, project))
                        current_static_digests = [
                            item for item in before["artifact_digests"] if item["path"] in persistent_paths
                        ]
                        if baseline_artifact_digests is None:
                            baseline_artifact_digests = current_static_digests
                            baseline_environment_probe = before["environment_probe"]
                        else:
                            drift_code = classify_task_drift(
                                before["environment_probe"], current_static_digests,
                                baseline_environment_probe, baseline_artifact_digests,
                            )
                            drift_detail = ""
                            if drift_code == "ENVIRONMENT_DRIFT":
                                drift_detail = "task environment drifted between adapter invocations"
                            elif drift_code == "INPUT_DRIFT":
                                drift_detail = "task input drifted between adapter invocations"
                            if drift_code != "NONE":
                                attest(
                                    "PRECHECK_DRIFT", drift_code, drift_detail,
                                    before["content_sha256"], None, input_snapshot["content_sha256"], None,
                                    snapshot_request["content_sha256"],
                                )
                                raise AbortEvaluation(
                                    evaluation_result("ERROR", drift_code, drift_detail), checkpoint,
                                )
                        if not retire_owned_path(snapshot_result_path, owned_paths):
                            raise AbortEvaluation(
                                evaluation_result(
                                    "ERROR", "CLEANUP_FAILED", "snapshot result cleanup failed",
                                ),
                                checkpoint,
                                cleanup_diagnosed=True,
                            )
                        prompt_oversized = len(rendered["text"].encode("utf-8")) > generation["max_prompt_bytes"]
                        if variant_name == "PARENT" and prompt_oversized:
                            failure_detail = "parent rendered prompt exceeds max_prompt_bytes"
                            attest(
                                "ADAPTER_FAILED", "ADAPTER_RESULT", failure_detail,
                                before["content_sha256"], None, input_snapshot["content_sha256"], None,
                                snapshot_request["content_sha256"],
                            )
                            raise AbortEvaluation(
                                evaluation_result("ERROR", "ADAPTER_RESULT", failure_detail), checkpoint,
                            )
                        started_ns = time.monotonic_ns()
                        try:
                            measurement = invoke_adapter(
                                task, adapter_request, adapter_request_path, variant_path, rendered_path, measurement_path,
                                project,
                                adapter_environment,
                                control["timeout_ns"],
                                sample,
                                paired_seed,
                                prompt_oversized,
                                owned_paths,
                                # Ladder row 15's membership test. The editable set is read from the
                                # manifest-declared, digest-pinned task definition, so a version-2
                                # `edit_set` block naming a path outside it is rejected by the same
                                # authority the adapter itself consulted.
                                task_allowed_edits(task, project),
                            )
                        except AdapterFailure as failure:
                            attest(
                                "ADAPTER_FAILED", failure.code, failure.detail,
                                before["content_sha256"], None, input_snapshot["content_sha256"], None,
                                snapshot_request["content_sha256"],
                            )
                            raise AbortEvaluation(
                                evaluation_result("ERROR", failure.code, failure.detail),
                                checkpoint,
                                cleanup_diagnosed=failure.code == "CLEANUP_FAILED",
                            ) from None
                        # Evaluator-observed, monotonic, and closed immediately after the adapter
                        # child exits and its result is read. Section 3.6: a failing attempt's own
                        # `generation_to_passing_patch_ns` is `None` by the C6 state machine, so the
                        # repair total cannot be assembled from adapter-reported values at all.
                        adapter_elapsed_ns = time.monotonic_ns() - started_ns
                        # Ladder row 10: each adapter invocation is single-attempt by construction,
                        # so an adapter that reports a repair loop of its own would double-count
                        # against the evaluator-owned `row.repair_loop_count`.
                        #
                        # Narrowed, and recorded as a deviation from spec section 3.3, which
                        # assumed every adapter emits the literal `0`. The provider-backed
                        # `scripts/prompt-measurement-adapter.py` does; the deterministic
                        # `scripts/prompt-fixed-adapter.py` emits `1` on its expected-failure path
                        # and is a byte-frozen `canonical-v1` corpus member that cannot be edited
                        # without breaking `make prompt-gate-check`. The check therefore binds
                        # exactly where double-counting is possible — a task that offers a repair
                        # attempt. Where no repair is offered the adapter's value is carried
                        # verbatim in `attempt.measurement` and is simply not the authority.
                        if repair_limit >= 1 and measurement["repair_loop_count"] != 0:
                            failure_detail = "measurement adapter reported a repair loop it cannot run"
                            attest(
                                "ADAPTER_FAILED", "ADAPTER_RESULT", failure_detail,
                                before["content_sha256"], None, input_snapshot["content_sha256"], None,
                                snapshot_request["content_sha256"],
                            )
                            raise AbortEvaluation(
                                evaluation_result("ERROR", "ADAPTER_RESULT", failure_detail), checkpoint,
                            )
                        # Ladder row 11: the evaluator re-derives the rendered prompt identity
                        # independently and requires equality before wrapping the adapter's document.
                        if measurement.get("rendered_prompt_sha256") != rendered["content_sha256"]:
                            failure_detail = "measurement adapter result identity disagrees"
                            attest(
                                "ADAPTER_FAILED", "ADAPTER_RESULT", failure_detail,
                                before["content_sha256"], None, input_snapshot["content_sha256"], None,
                                snapshot_request["content_sha256"],
                            )
                            raise AbortEvaluation(
                                evaluation_result("ERROR", "ADAPTER_RESULT", failure_detail), checkpoint,
                            )
                        after = invoke_snapshot(
                            task, snapshot_request_path, snapshot_result_path, project,
                            environment_values, preflight["environment_probe"],
                            owned_paths,
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
                            attest(
                                "POSTCHECK_FAILED", failure_code, failure_detail,
                                before["content_sha256"], after["content_sha256"],
                                input_snapshot["content_sha256"], None,
                                snapshot_request["content_sha256"],
                            )
                            raise AbortEvaluation(
                                evaluation_result("ERROR", failure_code, failure_detail), checkpoint,
                                cleanup_diagnosed=failure_code == "CLEANUP_FAILED",
                            )
                        after_static_digests = [
                            item for item in after["artifact_digests"] if item["path"] in persistent_paths
                        ]
                        post_drift_code = classify_task_drift(
                            after["environment_probe"], after_static_digests,
                            baseline_environment_probe, baseline_artifact_digests,
                        )
                        post_drift_detail = ""
                        if post_drift_code == "ENVIRONMENT_DRIFT":
                            post_drift_detail = "task environment drifted after adapter invocation"
                        elif post_drift_code == "INPUT_DRIFT":
                            post_drift_detail = "task input drifted from its first admitted invocation"
                        elif before["artifact_digests"] != after["artifact_digests"]:
                            post_drift_code = "INPUT_DRIFT"
                            post_drift_detail = "task input drifted after adapter invocation"
                        if post_drift_code != "NONE":
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
                            attest(
                                "POSTCHECK_DRIFT", post_drift_code, post_drift_detail,
                                before["content_sha256"], after["content_sha256"],
                                input_snapshot["content_sha256"], after_input_snapshot["content_sha256"],
                                snapshot_request["content_sha256"],
                            )
                            raise AbortEvaluation(
                                evaluation_result("ERROR", post_drift_code, post_drift_detail), checkpoint,
                            )
                        # Attempt one's workspace, adapter child, and sealed inputs are released
                        # before attempt two is prepared, on both the pass and the fail path. A run
                        # that cannot prove it cleaned up cannot prove the next attempt was contained.
                        cleanup_passed = True
                        for path in (snapshot_result_path, adapter_request_path, rendered_path, variant_path):
                            if not retire_owned_path(path, owned_paths):
                                cleanup_passed = False
                        if not cleanup_passed:
                            raise AbortEvaluation(
                                evaluation_result(
                                    "ERROR", "CLEANUP_FAILED", "evaluator-owned workspace cleanup failed",
                                ),
                                checkpoint,
                                cleanup_diagnosed=True,
                            )
                        # A terminal adapter measurement does NOT abort here. The invocation ran:
                        # it produced a snapshot request, before/after results, and an input
                        # snapshot, and every one of those must be referenced by the record of the
                        # invocation that produced it. Aborting inside the attempt would leave them
                        # in the persisted streams with no row, no attempt, and no attestation
                        # naming them, and the "no unreferenced trace record" rule would reject the
                        # whole document at publish time. The row is completed and attested exactly
                        # as it was at version 1, and the caller raises the terminal error after
                        # appending it.
                        if not any(item["content_sha256"] == input_snapshot["content_sha256"] for item in input_snapshots):
                            input_snapshots.append(input_snapshot)
                        overhead_ns: int | None = None
                        if measurement["status"] == "PASS":
                            overhead_ns = adapter_elapsed_ns - measurement["generation_to_passing_patch_ns"]
                            if overhead_ns < 0:
                                raise AbortEvaluation(
                                    evaluation_result(
                                        "ERROR", "TIMING",
                                        "adapter-reported generation exceeds the evaluator-observed span",
                                    ),
                                    checkpoint,
                                )
                        record = bind({
                            "schema_version": 1,
                            "artifact_kind": "TASK_ATTEMPT_RECORD",
                            "attempt_index": attempt_index,
                            "attempt_kind": "INITIAL" if attempt_index == 1 else "REPAIR",
                            "status": measurement["status"],
                            "skip_reason": "NONE",
                            "rendered_prompt_sha256": rendered["content_sha256"],
                            "repair_prompt_source": repair_source,
                            "adapter_request_sha256": adapter_request["content_sha256"],
                            "snapshot_request_sha256": snapshot_request["content_sha256"],
                            "before_snapshot_result_sha256": before["content_sha256"],
                            "after_snapshot_result_sha256": after["content_sha256"],
                            "input_snapshot_sha256": input_snapshot["content_sha256"],
                            "generation_request": measurement["generation_request"],
                            "seed_attestation": measurement["seed_attestation"],
                            "paired_seed": paired_seed,
                            "measurement": measurement,
                            "repair_preparation_ns": preparation_ns,
                            "adapter_elapsed_ns": adapter_elapsed_ns,
                            "adapter_overhead_ns": overhead_ns,
                            "measurement_sha256": measurement["content_sha256"],
                            "content_sha256": "",
                        })
                        expected_inputs.append(bind({
                            "schema_version": 2, "artifact_kind": "PROMPT_EXPECTED_INPUT_DIGEST",
                            "task_id": task["task_id"], "sample_index": sample, "variant": variant_name,
                            "attempt_index": attempt_index,
                            "rendered_prompt_sha256": rendered["content_sha256"],
                            "context_sources_sha256": context["content_sha256"],
                            "generation_request_sha256": measurement["generation_request"]["content_sha256"],
                            "adapter_request_sha256": adapter_request["content_sha256"],
                            "provider_request_sha256": measurement["generation_request"]["provider_request_sha256"],
                            "content_sha256": "",
                        }))
                        return {
                            "record": record,
                            "measurement": measurement,
                            "rendered_text": rendered_text,
                            "adapter_request": adapter_request,
                            "snapshot_request_sha256": snapshot_request["content_sha256"],
                            "before_sha256": before["content_sha256"],
                            "after_sha256": after["content_sha256"],
                            "input_snapshot_sha256": input_snapshot["content_sha256"],
                        }

                    try:
                        rendered_text, rendered_text_sha = render(variant, task_prompt, context)
                        attempts = [run_attempt(1, rendered_text, rendered_text_sha, None, 0)]
                        # Ladder row 12: a row whose first attempt did not fail, or whose task
                        # offers no repair loop, closes with exactly one attempt.
                        if repair_limit >= 1 and attempts[0]["measurement"]["status"] == "FAIL":
                            try:
                                attempts.append(build_repair_attempt(
                                    run_attempt, attempts[0], repair_template, generation, paired_seed,
                                ))
                            except EvaluationError as failure:
                                # Ladder row 15. A prompt the producer cannot re-derive from its
                                # own persisted output is an un-auditable artifact of a
                                # nondeterministic run, so the row errors here rather than
                                # persisting a repair attempt no verifier could ever recompute.
                                raise AbortEvaluation(
                                    evaluation_result(
                                        "ERROR", "REPAIR_RENDER", str(failure)[:4096],
                                    ),
                                    checkpoint,
                                ) from None
                    except AbortEvaluation as abort:
                        return finish(abort.result, abort.checkpoint, abort.cleanup_diagnosed)
                    # `row.measurement` is the final attempt that actually ran, so every existing
                    # consumer of `row.measurement.*` keeps working with no re-derivation.
                    final = [item for item in attempts if not item.get("skipped")][-1]
                    attest(
                        "COMPLETE", "NONE", "", final["before_sha256"], final["after_sha256"],
                        final["input_snapshot_sha256"], final["input_snapshot_sha256"],
                        final["snapshot_request_sha256"],
                    )
                    evaluation_input = bind({
                        "schema_version": 1, "artifact_kind": "EVALUATION_INPUT_IDENTITY", "task_id": task["task_id"],
                        "task_input_snapshot_sha256": final["input_snapshot_sha256"],
                        "parent_variant_sha256": parent_variant["content_sha256"],
                        "candidate_variant_sha256": candidate["content_sha256"],
                        "task_prompt_sha256": task_prompt["content_sha256"],
                        "context_sources_sha256": context["content_sha256"],
                        "generation_policy_sha256": generation["content_sha256"],
                        "generation_request_sha256": final["measurement"]["generation_request"]["content_sha256"],
                        "adapter_request_sha256": final["adapter_request"]["content_sha256"],
                        "environment_policy_sha256": environment_policy["content_sha256"],
                        "environment_sha256": environment["environment_id"], "sample_index": sample,
                        "paired_seed": paired_seed, "content_sha256": "",
                    })
                    records = [item["record"] for item in attempts]
                    try:
                        generation_ns = attempt_total_ns(records)
                    except EvaluationError as failure:
                        return finish(
                            evaluation_result("ERROR", "TIMING", str(failure)[:4096]), checkpoint,
                        )
                    # Unchanged, and deliberately so: `prompt_preparation_ns` is a hard-coded
                    # constant here today rather than a measured span, which deviates from
                    # `docs/specs/c6-prompt-context-optimizer.md` section 5.2. Measuring it is a
                    # separate concern with its own owner; fixing it inside this diff would
                    # silently change every version-2 row total for an unrelated reason.
                    preparation_ns = 20_000_000
                    if generation_ns is not None and preparation_ns + generation_ns > 7_200_000_000_000:
                        return finish(
                            evaluation_result(
                                "ERROR", "TIMING", "row timing total is outside its persisted bound",
                            ),
                            checkpoint,
                        )
                    row = bind({
                        "schema_version": 2, "artifact_kind": "PROMPT_TASK_ROW", "evaluation_id": request["evaluation_id"],
                        "task_id": task["task_id"], "sample_index": sample, "variant": variant_name,
                        "variant_id": variant["variant_id"], "variant_sha256": variant["content_sha256"],
                        "prompt_preparation_ns": preparation_ns,
                        "repair_loop_count": sum(
                            item["attempt_kind"] == "REPAIR" and item["status"] != "SKIPPED"
                            for item in records
                        ),
                        "generation_to_passing_patch_ns": generation_ns,
                        "time_to_passing_patch_ns": None if generation_ns is None else preparation_ns + generation_ns,
                        "attempts": records,
                        "evaluation_input": evaluation_input,
                        "measurement": final["measurement"], "content_sha256": "",
                    })
                    rows.append(row)
                    # Terminal adapter error, raised only now that the row, its attempts, its
                    # expected-input identities, and its attestation are all persisted. This is
                    # the version-1 order and it is deliberate: the published `ERROR` document
                    # keeps the failing row, and `make prompt-evaluate-smoke` asserts exactly that.
                    if final["measurement"].get("status") == "ERROR":
                        failure_detail = (
                            final["measurement"].get("diagnostic_summary")
                            or "measurement adapter returned an error"
                        )
                        failure_code = (
                            "CLEANUP_FAILED"
                            if not final["measurement"].get("cleanup_passed", True)
                            else "ADAPTER_RESULT"
                        )
                        return finish(
                            evaluation_result("ERROR", failure_code, failure_detail[:4096]),
                            checkpoint,
                            cleanup_diagnosed=failure_code == "CLEANUP_FAILED",
                        )

    status, gate, task_aggregates, corpus_aggregate, reasons = complete_score(
        tasks, rows, request["sample_count"], acceptance, trust, environment, control,
    )
    result = evaluation_result(status, "NONE", "")
    result["gate_eligible"] = gate
    result["task_aggregates"] = task_aggregates
    result["corpus_aggregate"] = corpus_aggregate
    result["serious_regression_reasons"] = reasons
    return finish(result)


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--final-result-relative", required=True)
    parser.add_argument("--final-evidence-relative", required=True)
    return parser.parse_args(arguments)


def emit_evaluation_output(
    result: Mapping[str, Any], evidence: Mapping[str, Any] | None,
) -> None:
    result_bytes = canonical(result)
    if len(result_bytes) > RESULT_LIMIT:
        raise EvaluationError("evaluation result exceeds its bound")
    evidence_bytes = b"" if evidence is None else canonical(evidence)
    if len(evidence_bytes) > EVIDENCE_LIMIT:
        raise EvaluationError("evaluation evidence exceeds its bound")
    pieces = [b"1\n", result_bytes] if evidence is None else [b"2\n", result_bytes, b"\n", evidence_bytes]
    for piece in pieces:
        offset = 0
        while offset < len(piece):
            offset += os.write(sys.stdout.fileno(), piece[offset:])


def main(arguments: Sequence[str] | None = None) -> int:
    values = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    owned_paths: set[Path] = set()
    status = 2
    try:
        result, evidence = evaluate(
            values.request,
            values.final_result_relative,
            values.final_evidence_relative,
            owned_paths,
        )
        emit_evaluation_output(result, evidence)
        status = 0
    except (EvaluationError, OSError, TypeError, ValueError, KeyError, IndexError):
        return 3 if cleanup_owned_paths(owned_paths) else 2
    return status


if __name__ == "__main__":
    raise SystemExit(main())
