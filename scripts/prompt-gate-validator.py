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
so an unverified local build cannot satisfy the gate. The declared digest is then bound to the
locator's ``generation_child_sha256`` during source-bundle revalidation, so the same three-way
equality the evidence claims — retained bytes, declared input, recorded evidence identity — must
hold before any source identity is observed.

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
    # Appended after the settled references, following the `generation_child_sha256` precedent:
    # the environment policy travels with the gate evidence, so the manifest binds it by digest
    # instead of leaving it a path-only member of this directory.
    "environment_policy",
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
    "generation_child_sha256",
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
EXPECTED_INPUT_V2_FIELDS = (
    "schema_version",
    "artifact_kind",
    "task_id",
    "sample_index",
    "variant",
    # One record per non-`SKIPPED` attempt rather than per row, so the identity that must be
    # unique, complete, and unextended grows an attempt ordinal.
    "attempt_index",
    "rendered_prompt_sha256",
    "context_sources_sha256",
    "generation_request_sha256",
    "adapter_request_sha256",
    "provider_request_sha256",
    "content_sha256",
)
# --- C4-REPAIR-MEASURED: the version-2 row shape ------------------------------------------------
# `docs/specs/c4-repair-measured.md` sections 3.2 and 3.3 own this contract. One record cannot
# decode both shapes, so the validator carries one exact field tuple per version and selects by
# the container's `schema_version` — never by the presence of a field. A version-1 row has no
# `attempts`, no row-level `repair_loop_count`, and no row-level `generation_to_passing_patch_ns`,
# and is never given a compatibility default for one.
TASK_ROW_V1_FIELDS = (
    "schema_version",
    "artifact_kind",
    "evaluation_id",
    "task_id",
    "sample_index",
    "variant",
    "variant_id",
    "variant_sha256",
    "prompt_preparation_ns",
    "time_to_passing_patch_ns",
    "evaluation_input",
    "measurement",
    "content_sha256",
)
TASK_ROW_V1_OPTIONAL = frozenset({"time_to_passing_patch_ns"})
TASK_ROW_V2_FIELDS = (
    "schema_version",
    "artifact_kind",
    "evaluation_id",
    "task_id",
    "sample_index",
    "variant",
    "variant_id",
    "variant_sha256",
    "prompt_preparation_ns",
    "repair_loop_count",
    "generation_to_passing_patch_ns",
    "time_to_passing_patch_ns",
    "attempts",
    "evaluation_input",
    "measurement",
    "content_sha256",
)
TASK_ROW_V2_OPTIONAL = frozenset(
    {"generation_to_passing_patch_ns", "time_to_passing_patch_ns"}
)
ATTEMPT_RECORD_FIELDS = (
    "schema_version",
    "artifact_kind",
    "attempt_index",
    "attempt_kind",
    "status",
    "skip_reason",
    "rendered_prompt_sha256",
    "repair_prompt_source",
    "adapter_request_sha256",
    # Each attempt is its own contained invocation, so it produces its own snapshot request,
    # before/after snapshot results, and input snapshot. `snapshot_attestations` stays one record
    # per row because its schedule check binds it positionally, so these four are what keep a
    # repair invocation's trace records bound to the attempt that produced them. Declared in the
    # producer's order (`scripts/prompt-evaluate.py`, the `TASK_ATTEMPT_RECORD` literal) and in
    # `src/prompt_artifacts.align`'s `TaskAttemptRecord`: after `adapter_request_sha256` and
    # before `generation_request`.
    "snapshot_request_sha256",
    "before_snapshot_result_sha256",
    "after_snapshot_result_sha256",
    "input_snapshot_sha256",
    "generation_request",
    "seed_attestation",
    "paired_seed",
    "measurement",
    "repair_preparation_ns",
    "adapter_elapsed_ns",
    "adapter_overhead_ns",
    "measurement_sha256",
    "content_sha256",
)
# A `SKIPPED` attempt carries identity and the work that reached the skip decision, and nothing
# else; a `PASS` attempt is the only one carrying `adapter_overhead_ns`. Every one of those is a
# canonically omitted `Option::None`, so all of them are optional at the shape boundary and the
# per-status presence rule is enforced explicitly in `validate_attempt_record`.
ATTEMPT_RECORD_OPTIONAL = frozenset(
    {
        "rendered_prompt_sha256",
        "repair_prompt_source",
        "adapter_request_sha256",
        "snapshot_request_sha256",
        "before_snapshot_result_sha256",
        "after_snapshot_result_sha256",
        "input_snapshot_sha256",
        "generation_request",
        "seed_attestation",
        "measurement",
        "adapter_overhead_ns",
        "measurement_sha256",
    }
)
# The four trace digests an attempt that ran must carry, paired with the persisted stream each one
# must name. Mirrors the attestation rule below, which binds the row-level documents the same way.
ATTEMPT_TRACE_POOLS = (
    ("snapshot_request_sha256", "snapshot_requests"),
    ("before_snapshot_result_sha256", "snapshot_results"),
    ("after_snapshot_result_sha256", "snapshot_results"),
    ("input_snapshot_sha256", "input_snapshots"),
)
REPAIR_PROMPT_SOURCE_FIELDS = (
    "schema_version",
    "artifact_kind",
    "template_sha256",
    "source_attempt_index",
    "source_measurement_sha256",
    "included_sections",
    "dropped_sections",
    "assembled_bytes",
    "content_sha256",
)
# C4-REPAIR-EDITSET adds `EDITSET` immediately after `STATUS` and drops it **last**. A
# `canonical-v1r` prompt names only the four earlier kinds, and its relative order does not move,
# so both corpora's section lists validate against this one ordering.
REPAIR_SECTION_KINDS = ("STATUS", "EDITSET", "SUMMARY", "STDOUT", "STDERR")
# C4-REPAIR-TEMPLATE inserts `POLICY` between `STATUS` and `EDITSET`. The four- and five-kind
# lists are subsequences of this one, so all three corpora's section lists validate against one
# ordering, exactly as the five-kind list already covered the four-kind one.
REPAIR_SECTION_KINDS_V3 = ("STATUS", "POLICY", "EDITSET", "SUMMARY", "STDOUT", "STDERR")
REPAIR_ADAPTER_RELATIVE = "scripts/prompt-repair-adapter.py"
TEMPLATE_ADAPTER_RELATIVE = "scripts/prompt-template-adapter.py"
EDIT_SET_BLOCK_FIELDS = (
    "schema_version", "artifact_kind", "path", "body_bytes", "body_sha256", "body_text",
    "content_sha256",
)
TASK_MEASUREMENT_V2_MEMBERS = (
    "edit_set", "edit_set_total_bytes", "patch_sha256", "base_adapter_runtime_identity",
)
TASK_MEASUREMENT_V3_MEMBERS = (
    "edit_refusal", "completion_bytes", "completion_sha256", "completion_text",
)
EDIT_REFUSAL_PATCH_CODES = (
    "NO_FILE_BLOCK", "HEADER_WITHOUT_BLOCK", "UNTERMINATED_BLOCK", "TOO_MANY_BLOCKS",
    "DUPLICATE_PATH", "BODY_TOO_LARGE", "UNCHANGED_FILES",
)
EDIT_REFUSAL_POLICY_CODES = ("PATH_NOT_EDITABLE", "PATH_ESCAPES_SOURCE")
EDIT_REFUSAL_CODES = ("NONE",) + EDIT_REFUSAL_PATCH_CODES + EDIT_REFUSAL_POLICY_CODES
COMPLETION_LIMIT = 32_768
MAXIMUM_FILE_BLOCKS = 32
MAXIMUM_EDIT_BYTES = 262_144
EDIT_SET_LIMIT = 16_384
# The marker the frozen `bounded_text` appends at the end of a diagnostic it had to cut. Ladder
# row 17 reads the tail of `diagnostic_summary`, which is exactly the part a cut removes.
SUMMARY_TRUNCATION_TEXT = "\n[output truncated]"
# The bound `bounded_text` cuts a summary to. A genuine cut summary is at least this long — the
# frozen producer writes `raw[:limit - len(marker)] + marker` — so the length corroborates the
# marker and a short summary cannot claim the exemption by ending in the marker's text.
SUMMARY_LIMIT = 4_096
ATTEMPT_KINDS = ("INITIAL", "REPAIR")
ATTEMPT_STATUSES = ("PASS", "FAIL", "POLICY_VIOLATION", "ERROR", "SKIPPED")
SKIP_REASONS = ("NONE", "REPAIR_PROMPT_BUDGET", "REPAIR_NOT_ELIGIBLE", "REPAIR_INPUT_UNAVAILABLE")
# The existing two-hour ceiling both implementations already enforce. It is not raised.
TIMING_CEILING_NS = 7_200_000_000_000
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
AGGREGATE_OPTIONAL = frozenset(
    {
        # A task or corpus with no paired pass has no median and therefore no ppm pair. The
        # canonical encoding omits each `Option::None`, so a completion-gain acceptance — the
        # only path that does not require a paired pass — reaches this boundary without them.
        "parent_paired_median_time_ns",
        "candidate_paired_median_time_ns",
        "time_improvement_ppm",
        "time_regression_ppm",
        # C4-REPAIR-EDITSET's denominator is present only for a corpus whose adapter can render
        # the section, so a `canonical-v1r` version-2 document — `eval/prompt/c4-repair-gate/` —
        # legitimately omits it. `rescore` recomputes the same presence, so an omission here is
        # never a silent default: the two shapes must agree exactly.
        "parent_repair_editset_attempt_count",
        "candidate_repair_editset_attempt_count",
        "repair_editset_attempt_count",
        # C4-REPAIR-TEMPLATE's secondary counter is present only for a corpus whose adapter
        # persists `edit_refusal`, so the three earlier chains legitimately omit it.
        "parent_edit_refusal_count",
        "candidate_edit_refusal_count",
        "edit_refusal_count",
    }
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
# The version-2 aggregates append the repair columns; the version-1 prefix does not move, so a
# version-1 document keeps its exact recomputed shape.
TASK_AGGREGATE_V2_FIELDS = TASK_AGGREGATE_FIELDS + (
    "parent_repair_attempt_count",
    "candidate_repair_attempt_count",
    "parent_repair_recovery_count",
    "candidate_repair_recovery_count",
    "repair_recovery_paired",
    # C4-REPAIR-EDITSET's denominator, per variant.
    "parent_repair_editset_attempt_count",
    "candidate_repair_editset_attempt_count",
    # C4-REPAIR-TEMPLATE's secondary counter, per variant.
    "parent_edit_refusal_count",
    "candidate_edit_refusal_count",
)
CORPUS_AGGREGATE_V2_FIELDS = CORPUS_AGGREGATE_FIELDS + (
    # The C4 gate quantity and its two denominators. The gate consumes
    # `repair_recovery_paired_count` only.
    "repair_attempt_count",
    "repair_recovery_count",
    "repair_recovery_paired_count",
    # Repair attempts whose prompt actually carried `EDITSET`. A denominator, never a gate input.
    "repair_editset_attempt_count",
    # Ran attempts refused by the edit policy. A pre-committed secondary, never a gate input.
    "edit_refusal_count",
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
CORPUS_FIELDS = (
    "schema_version",
    "artifact_kind",
    "corpus_id",
    "corpus_revision",
    "task_files",
    "content_sha256",
)
WORKSPACE_PREFLIGHT_REQUEST_FIELDS = (
    "schema_version",
    "artifact_kind",
    "evaluation_id",
    "project_root",
    "workspace_path",
    "content_sha256",
)
WORKSPACE_PREFLIGHT_FIELDS = (
    "schema_version",
    "artifact_kind",
    "evaluation_id",
    "status",
    "error_code",
    "error",
    "physical_project_root",
    "physical_workspace_path",
    "environment_probe",
    "content_sha256",
)
INPUT_SNAPSHOT_FIELDS = (
    "schema_version",
    "artifact_kind",
    "task_id",
    "task_manifest_sha256",
    "artifact_digests",
    "environment_sha256",
    "content_sha256",
)
SNAPSHOT_RESULT_FIELDS = (
    "schema_version",
    "artifact_kind",
    "task_id",
    "status",
    "error_code",
    "error",
    "environment_probe",
    "artifact_digests",
    "content_sha256",
)
SNAPSHOT_ATTESTATION_FIELDS = (
    "schema_version",
    "artifact_kind",
    "task_id",
    "sample_index",
    "variant",
    "status",
    "error_code",
    "error",
    "snapshot_request_sha256",
    "before_snapshot_result_sha256",
    "after_snapshot_result_sha256",
    "before_input_snapshot_sha256",
    "after_input_snapshot_sha256",
    "content_sha256",
)
ENVIRONMENT_POLICY_IDENTITY = "policy_id"
# Every declared `ArtifactReference` the evaluation result carries, with the kind it must name and
# the identity field of the artifact the same result embeds. Section 4.5 requires the reference and
# the embedded artifact to be the same document, so the gate binds both halves rather than trusting
# a reference nobody re-derives.
EMBEDDED_REFERENCES = (
    ("experiment", "experiment_artifact", "PROMPT_EXPERIMENT_RESULT", "experiment_id"),
    ("parent_activation", "parent_activation_artifact", "PROMPT_ACTIVATION_RESULT", "decision_id"),
    ("corpus_source", "corpus", "PROMPT_EVALUATION_CORPUS", "corpus_id"),
    ("acceptance_policy_source", "acceptance_policy", "PROMPT_ACCEPTANCE_POLICY", "policy_id"),
    ("generation_policy_source", "generation_policy", "GENERATION_POLICY", "generation_policy_id"),
    (
        "provider_control_source",
        "provider_control",
        "EVALUATION_PROVIDER_CONTROL",
        "provider_control_id",
    ),
    (
        "workspace_preflight_source",
        "workspace_preflight",
        "WORKSPACE_PREFLIGHT_RESULT",
        "evaluation_id",
    ),
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


def completed_record(value: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    """Restore each canonically omitted `Option::None` so a comparison sees one shape."""
    return {name: value.get(name) for name in fields}


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
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            pid = int(status_path.parent.name)
            status_lines = status_path.read_text().splitlines()
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
        "environment_policy": "ENVIRONMENT_POLICY",
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
        "generation_child_sha256",
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


def bind_scope_prompts(scope: Mapping[str, Any], variant: Mapping[str, Any], label: str) -> None:
    """Require the scope's declared prompt digests to be the variant's nested prompt digests."""
    for scope_name, nested in (("base_prompt_sha256", "base_prompt"), ("repo_prompt_sha256", "repo_prompt")):
        declared = require_digest(scope.get(scope_name), f"{label} scope {scope_name}")
        if declared != variant[nested]["content_sha256"]:
            raise GateError(f"{label} scope {scope_name} is not the variant's {nested} digest")


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
    # `valid_activation_shape` in `src/prompt_artifacts.align` requires the effective variant's
    # nested prompt digests to be the scope's declared prompt digests. The gate recomputes both, so
    # it must compare them too; otherwise a rebound scope could name prompts the variant never used.
    bind_scope_prompts(activation["scope"], activation["effective_variant"], f"{label} activation")
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


# --- C4-REPAIR-EDITSET: the version-2 measurement -----------------------------------------------
#
# Owner split (spec section 7.8). This validator and `scripts/prompt-evaluate.py` own the rules
# that need a file outside the result document — the `allowed_edits` membership of ladder row 15 —
# and share the rest with the Align verifier, which recomputes them independently. Nothing here is
# trusted from the persisted document.


def validate_edit_set_block(value: Any, label: str) -> dict[str, Any]:
    """Ladder row 15, less its `allowed_edits` membership. An omitted block keeps its identity.

    Membership in the task definition's editable set is deliberately NOT checked here.
    `validate_evaluation_pair` is a pure function of the two documents it is handed — that is what
    lets the frozen-chain regression call it directly against checked-in evidence with no source
    tree — and the editable set lives in a file outside them. `scripts/prompt-evaluate.py` owns
    that one rule, against the manifest-declared digest-pinned task definition, at the moment the
    adapter result is admitted; the block can never be persisted without passing it there.
    """
    block = exact_record(value, EDIT_SET_BLOCK_FIELDS, label)
    if block["schema_version"] != 1 or block["artifact_kind"] != "EDIT_SET_BLOCK":
        raise GateError(f"{label} header is invalid")
    if not isinstance(block["path"], str) or not block["path"]:
        raise GateError(f"{label} names no path")
    require_integer(block["body_bytes"], f"{label} body bytes", minimum=0, maximum=MAXIMUM_EDIT_BYTES)
    require_digest(block["body_sha256"], f"{label} body digest")
    body = block["body_text"]
    if body is not None:
        if not isinstance(body, str):
            raise GateError(f"{label} body text is not a string")
        raw = body.encode("utf-8")
        if len(raw) > EDIT_SET_LIMIT:
            raise GateError(f"{label} carried a body beyond the producer's own budget")
        if hashlib.sha256(raw).hexdigest() != block["body_sha256"]:
            raise GateError(f"{label} body digest does not digest its body text")
        if len(raw) != block["body_bytes"]:
            raise GateError(f"{label} body length disagrees with its declared byte count")
    return block


def validate_measurement_version(
    measurement: Mapping[str, Any], task: Mapping[str, Any], label: str,
) -> None:
    """Ladder rows 10 to 17 on one persisted measurement, at whichever version it declares."""
    version = measurement.get("schema_version")
    if version not in (1, 2, 3):
        raise GateError(f"{label} declares an unknown measurement version")
    # Ladder row 16: the version is a checked function of the corpus, not a producer's choice, now
    # three-way. One reader for the selector, so no rule can disagree about which corpus this is.
    declared = list(task.get("argv") or [])
    adapter = declared[1] if len(declared) == 2 else None
    expected = (
        3 if adapter == TEMPLATE_ADAPTER_RELATIVE
        else 2 if adapter == REPAIR_ADAPTER_RELATIVE else 1
    )
    if version != expected:
        raise GateError(f"{label} version disagrees with the adapter its corpus names")
    present = [name for name in TASK_MEASUREMENT_V2_MEMBERS if name in measurement]
    later = [name for name in TASK_MEASUREMENT_V3_MEMBERS if name in measurement]
    if version < 3 and later:
        # Ladder row 15: absence below version 3 is required, never defaulted.
        raise GateError(f"{label} carries {later[0]} below version 3")
    if version == 1:
        # Ladder row 10: absence at version 1 is required, never defaulted.
        if present:
            raise GateError(f"{label} carries {present[0]} at version 1")
        return
    if version == 3:
        validate_measurement_version_three(measurement, label)
    # Ladder row 10 at version 2, read on the **persisted** wire form rather than on the adapter's
    # result file. The two serializations differ and the distinction is load bearing: the adapter
    # writes every key, `null` included, and `scripts/prompt-evaluate.py` holds it to the exact
    # 27-key tuple at that boundary; the canonical encoder that produces this document **omits an
    # `Option::None`**, so an absent key here means `None` and is the correct encoding of one. Only
    # `base_adapter_runtime_identity` is unconditionally `Some` at version 2, so only it must be
    # present; the other three are governed by rows 13 and 14, which read absence as `None`.
    # Requiring all four keys here rejected every real version-2 document whose attempt produced no
    # edit set — caught by running this validator against the published gate evidence, which is the
    # one thing the fixture could not tell us because the fixture writes its `None`s explicitly.
    identity = measurement.get("base_adapter_runtime_identity")
    if not isinstance(identity, str) or not identity.startswith("PYTHON:"):
        raise GateError(f"{label} carries no base adapter runtime identity at version 2")
    require_digest(identity[7:], f"{label} base adapter runtime identity")
    # Ladder row 13.
    patch = measurement.get("patch_sha256")
    if (patch is not None) != (measurement["patch_size_bytes"] > 0):
        raise GateError(f"{label} patch digest presence disagrees with its patch size")
    if patch is not None:
        require_digest(patch, f"{label} patch digest")
    blocks = measurement.get("edit_set")
    total = measurement.get("edit_set_total_bytes")
    # Ladder row 14.
    if (blocks is None) != (total is None):
        raise GateError(f"{label} edit set and its total disagree on presence")
    if blocks is None:
        return
    if not isinstance(blocks, list) or not blocks or len(blocks) > MAXIMUM_FILE_BLOCKS:
        raise GateError(f"{label} edit set is empty or exceeds its block bound")
    records = [
        validate_edit_set_block(item, f"{label} edit set block {ordinal}")
        for ordinal, item in enumerate(blocks, start=1)
    ]
    paths = [item["path"] for item in records]
    if paths != sorted(paths) or len(set(paths)) != len(paths):
        raise GateError(f"{label} edit set paths are not unique and sorted ascending")
    if total != sum(item["body_bytes"] for item in records):
        raise GateError(f"{label} edit set total is not the sum of its block byte counts")
    # Ladder row 17: the cheapest cross-check in the design. `diagnostic_summary` is produced by
    # the frozen sequencing from `applied_edits` and `edit_set` from the same `edits` list, so a
    # divergence means the section 3.2 near-copy diverged.
    #
    # A **truncated** summary is exempt, and that is not a softening of the row: the marker is
    # appended at the end, so the applied-edit list is precisely what the cut removes, and holding
    # a cut summary to the full path list would refuse a legitimate measurement whose summary
    # exceeded `SUMMARY_LIMIT`.
    #
    # The exemption needs the marker **and** the length. `bounded_text` only cuts a summary that
    # exceeded `SUMMARY_LIMIT`, and it cuts to `SUMMARY_LIMIT - len(marker)` bytes before appending
    # the marker, so a genuine cut summary is never shorter than the bound. Taking the marker text
    # alone would let a producer name any applied-edit list at all and end the string with it.
    marker = "applied edits: "
    summary = measurement["diagnostic_summary"]
    if (
        summary.endswith(SUMMARY_TRUNCATION_TEXT)
        and len(summary.encode("utf-8")) >= SUMMARY_LIMIT
    ):
        return
    if marker in summary:
        named = [item for item in summary.rsplit(marker, 1)[1].split(", ") if item]
        if named != paths:
            raise GateError(f"{label} diagnostic summary names another applied-edit list")


def validate_measurement_version_three(measurement: Mapping[str, Any], label: str) -> None:
    """Ladder rows 17 to 20, read on the **persisted wire form** rather than on a key tuple.

    The distinction is load bearing and this is the third capability to meet it: the adapter writes
    every key, `null` included, and `scripts/prompt-evaluate.py` holds it to the exact 31-key tuple
    at that boundary; the canonical encoder that produces this document **omits an `Option::None`**,
    so an absent key here means `None` and is the correct encoding of one. Only `edit_refusal` is
    unconditionally `Some` at version 3, so only it must be present. `completion_bytes` and
    `completion_sha256` are present whenever a provider response was received, and `completion_text`
    is usually absent.
    """
    code = measurement.get("edit_refusal")
    if code not in EDIT_REFUSAL_CODES:
        raise GateError(f"{label} carries no valid edit refusal code at version 3")
    if (code in EDIT_REFUSAL_PATCH_CODES) != (measurement["failure_kind"] == "PATCH"):
        raise GateError(f"{label} refusal class disagrees with its failure kind")
    if code in EDIT_REFUSAL_PATCH_CODES and measurement["patch_size_bytes"] != 0:
        raise GateError(f"{label} records a refused patch with a non-zero patch size")
    if code in EDIT_REFUSAL_POLICY_CODES and (
        measurement["status"] != "POLICY_VIOLATION" or measurement["failure_kind"] != "POLICY"
    ):
        raise GateError(f"{label} records a policy-class refusal that is not a policy violation")
    # The invariant this capability exists to establish, and the one C4E could not state: the
    # reproduced-unchanged refusal keeps the blocks its producer built one line before the raise.
    if code == "UNCHANGED_FILES":
        if measurement.get("edit_set") is None:
            raise GateError(f"{label} discarded the blocks its refusal was computed from")
        if measurement.get("patch_sha256") is not None:
            raise GateError(f"{label} records a patch digest for an empty synthesized patch")
    elif code != "NONE" and measurement.get("edit_set") is not None:
        raise GateError(f"{label} carries an edit set for a refusal that never built one")
    count = measurement.get("completion_bytes")
    digest_value = measurement.get("completion_sha256")
    if (count is None) != (digest_value is None):
        raise GateError(f"{label} completion identity members disagree on presence")
    response_received = measurement["generation_request"]["provider_request_sha256"] != "0" * 64
    if (count is not None) != response_received:
        raise GateError(f"{label} completion identity disagrees with provider response presence")
    if count is not None:
        require_integer(count, f"{label} completion bytes", minimum=0, maximum=2_097_152)
        require_digest(digest_value, f"{label} completion digest")
    text = measurement.get("completion_text")
    if text is None:
        return
    if code in ("NONE", "UNCHANGED_FILES"):
        raise GateError(f"{label} persists a completion excerpt where the edit set explains it")
    if not isinstance(text, str) or len(text.encode("utf-8")) > COMPLETION_LIMIT:
        raise GateError(f"{label} completion excerpt is not bounded text")
    if count is None:
        raise GateError(f"{label} persists a completion excerpt with no completion identity")


def validate_measurement_probe(
    measurement: Mapping[str, Any], task: Mapping[str, Any], label: str,
) -> None:
    """Ladder row 12: the section 2.3 gap, closed at attempt level.

    The row-level check binds only the final attempt once a row can run twice, so without this an
    intermediate attempt could carry any probe at all. `producer` names a role and is the same
    literal for both adapters; `runtime_identity` names a file and must not be.
    """
    probe = measurement["environment_probe"]
    if probe["producer"] != "MEASUREMENT_ADAPTER":
        raise GateError(f"{label} measurement probe names another producer")
    if probe["runtime_identity"] != task["measurement_adapter_runtime"]:
        raise GateError(f"{label} measurement probe names another runtime identity")


def validate_repair_prompt_source(value: Any, policy: Mapping[str, Any], label: str) -> None:
    """Section 3.2 and section 4.3: the repair prompt's recorded provenance and section ladder."""
    source = exact_record(value, REPAIR_PROMPT_SOURCE_FIELDS, label)
    if source["schema_version"] != 1 or source["artifact_kind"] != "REPAIR_PROMPT_SOURCE":
        raise GateError(f"{label} header is invalid")
    require_digest(source["template_sha256"], f"{label} template digest")
    require_digest(source["source_measurement_sha256"], f"{label} source measurement digest")
    if source["source_attempt_index"] != 1:
        raise GateError(f"{label} does not consume the initial attempt")
    included = source["included_sections"]
    dropped = source["dropped_sections"]
    for name, sections in (("included", included), ("dropped", dropped)):
        if not isinstance(sections, list):
            raise GateError(f"{label} {name} sections are not a list")
        ordered = [kind for kind in REPAIR_SECTION_KINDS_V3 if kind in sections]
        if sections != ordered or len(set(sections)) != len(sections):
            raise GateError(f"{label} {name} sections are not the fixed order without repeats")
    if set(included) & set(dropped):
        raise GateError(f"{label} sections are both included and dropped")
    # `STATUS` is never dropped: it is the single most load-bearing fact in the prompt and it is
    # bounded far below any budget that could force a drop.
    if "STATUS" in dropped:
        raise GateError(f"{label} drops the STATUS section")
    # `POLICY` joins it, and for a different reason: `STATUS` plus `POLICY` are at most 2,176 bytes
    # together, so they structurally cannot be why a prompt exceeds its budget. `EDITSET` stays
    # droppable because up to 32 blocks can blow the budget by themselves.
    if "POLICY" in dropped:
        raise GateError(f"{label} drops the POLICY section")
    require_integer(
        source["assembled_bytes"],
        f"{label} assembled bytes",
        minimum=1,
        maximum=policy["max_prompt_bytes"],
    )


def path_is_tree_descendant(path: str, root: str) -> bool:
    """`src/prompt_score.align:3530`: a path strictly beneath `root`, separator included."""
    return len(path) > len(root) + 1 and path.startswith(root) and path[len(root)] == "/"


def file_expectation_digest(entry: Mapping[str, Any]) -> str:
    """The canonical mode/path/digest preimage a `FILE` expectation is taken over.

    Mirrors `verifier_file_expectation_matches` (`src/prompt_score.align:3513`), so a FILE
    expectation binds the observed mode as well as the observed content.
    """
    preimage = f"{entry['mode']} {entry['path']}\0F {entry['sha256']}\n".encode("utf-8")
    return hashlib.sha256(preimage).hexdigest()


def snapshot_request_closure(
    request: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> bool:
    """Every observed artifact is one the request asked for, in the order it asked.

    The port of `verifier_snapshot_artifact_closure` (`src/prompt_score.align:3543`): each static
    expectation matches the next observed digest, a `TREE` expectation additionally consumes its
    own descendants, the additional files follow in declaration order, and nothing is left over.
    """
    digests = snapshot["artifact_digests"]
    if not isinstance(digests, list):
        return False
    index = 0
    for expectation in request["static_expectations"]:
        if index >= len(digests) or digests[index]["path"] != expectation["path"]:
            return False
        if expectation["kind"] == "FILE":
            if file_expectation_digest(digests[index]) != expectation["expected_sha256"]:
                return False
            index += 1
        else:
            if digests[index]["sha256"] != expectation["expected_sha256"]:
                return False
            root = expectation["path"]
            index += 1
            while index < len(digests) and path_is_tree_descendant(digests[index]["path"], root):
                index += 1
    for additional in request["additional_files"]:
        if index >= len(digests) or digests[index]["path"] != additional:
            return False
        index += 1
    return index == len(digests)


def validate_attempt_traces(
    attempt: Mapping[str, Any],
    task: Mapping[str, Any],
    pools: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    label: str,
) -> None:
    """Section 3.8 row 22: resolve an attempt's four trace digests and cross-validate them.

    `snapshot_attestations` carries one record per row and so cannot reach a repair invocation's
    trace records; the attempt record is what binds them. Membership in the persisted pool is not
    enough — the port of `verifier_attempt_trace_cross_valid` (`src/prompt_score.align:4877`)
    resolves each digest to **exactly one** record of this row's task, requires the before and
    after observations to be the same observation, requires both to be closed over the resolved
    request, and requires the input snapshot to be this task's and to carry what was observed.
    """
    resolved: dict[str, Mapping[str, Any]] = {}
    for name, pool in ATTEMPT_TRACE_POOLS:
        digest = require_digest(attempt[name], f"{label} {name}")
        candidates = pools[pool].get(digest)
        if not candidates:
            raise GateError(f"{label} {name} names no persisted record")
        owned = [item for item in candidates if item["task_id"] == task["task_id"]]
        if len(owned) != 1:
            raise GateError(f"{label} {name} does not resolve to exactly one record of its task")
        resolved[name] = owned[0]
    request = resolved["snapshot_request_sha256"]
    before = resolved["before_snapshot_result_sha256"]
    after = resolved["after_snapshot_result_sha256"]
    input_snapshot = resolved["input_snapshot_sha256"]
    before_probe = before.get("environment_probe")
    after_probe = after.get("environment_probe")
    if before_probe is None or after_probe is None:
        raise GateError(f"{label} observed no environment probe")
    if (
        before_probe["content_sha256"] != after_probe["content_sha256"]
        or before["artifact_digests"] != after["artifact_digests"]
    ):
        raise GateError(f"{label} before and after observations record drift")
    for name, observation in (("before", before), ("after", after)):
        if not snapshot_request_closure(request, observation):
            raise GateError(f"{label} {name} observation is not closed over its snapshot request")
    if input_snapshot["task_manifest_sha256"] != task["content_sha256"]:
        raise GateError(f"{label} input snapshot names another task manifest")
    if input_snapshot["artifact_digests"] != before["artifact_digests"]:
        raise GateError(f"{label} input snapshot does not carry the observed artifact digests")


def validate_attempt_record(
    value: Any,
    row: Mapping[str, Any],
    task: Mapping[str, Any],
    policy: Mapping[str, Any],
    pools: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    ordinal: int,
    label: str,
) -> dict[str, Any]:
    """One attempt: its identity, its per-status presence rule, and its own timing bounds."""
    attempt = exact_record(value, ATTEMPT_RECORD_FIELDS, label, ATTEMPT_RECORD_OPTIONAL)
    if attempt["schema_version"] != 1 or attempt["artifact_kind"] != "TASK_ATTEMPT_RECORD":
        raise GateError(f"{label} header is invalid")
    if attempt["attempt_index"] != ordinal:
        raise GateError(f"{label} attempt index is not dense and ascending from one")
    if attempt["attempt_kind"] not in ATTEMPT_KINDS:
        raise GateError(f"{label} attempt kind is invalid")
    if attempt["status"] not in ATTEMPT_STATUSES:
        raise GateError(f"{label} status is invalid")
    if attempt["skip_reason"] not in SKIP_REASONS:
        raise GateError(f"{label} skip reason is invalid")
    skipped = attempt["status"] == "SKIPPED"
    if skipped != (attempt["skip_reason"] != "NONE"):
        raise GateError(f"{label} skip reason does not agree with its status")
    if attempt["paired_seed"] != row["evaluation_input"]["paired_seed"]:
        raise GateError(f"{label} paired seed disagrees with its row")
    require_integer(
        attempt["repair_preparation_ns"], f"{label} repair preparation", minimum=0,
        maximum=TIMING_CEILING_NS,
    )
    if attempt["attempt_kind"] == "INITIAL" and attempt["repair_preparation_ns"] != 0:
        raise GateError(f"{label} initial attempt records repair preparation work")
    # Section 3.2: a `SKIPPED` attempt carries only identity, not a run. The four trace digests
    # belong to the same rule: a skipped repair made no contained invocation, so it produced no
    # snapshot request, no snapshot result, and no input snapshot to name.
    run_bound = (
        "rendered_prompt_sha256", "adapter_request_sha256", "snapshot_request_sha256",
        "before_snapshot_result_sha256", "after_snapshot_result_sha256", "input_snapshot_sha256",
        "generation_request", "seed_attestation", "measurement", "measurement_sha256",
    )
    for name in run_bound:
        present = attempt.get(name) is not None
        if present == skipped:
            state = "carries" if present else "omits"
            raise GateError(f"{label} {state} {name} against its status")
    if not skipped:
        validate_attempt_traces(attempt, task, pools, label)
    if skipped:
        if attempt["adapter_elapsed_ns"] != 0:
            raise GateError(f"{label} skipped attempt records adapter time")
        if attempt.get("adapter_overhead_ns") is not None:
            raise GateError(f"{label} skipped attempt records adapter overhead")
        if attempt["attempt_kind"] != "REPAIR":
            raise GateError(f"{label} skipped attempt is not a repair attempt")
    else:
        require_integer(
            attempt["adapter_elapsed_ns"], f"{label} adapter elapsed", minimum=1,
            maximum=TIMING_CEILING_NS,
        )
        require_digest(attempt["rendered_prompt_sha256"], f"{label} rendered prompt digest")
        require_digest(attempt["adapter_request_sha256"], f"{label} adapter request digest")
        require_digest(attempt["measurement_sha256"], f"{label} measurement digest")
        measurement = attempt["measurement"]
        if measurement["content_sha256"] != attempt["measurement_sha256"]:
            raise GateError(f"{label} measurement digest does not match its measurement")
        if measurement["rendered_prompt_sha256"] != attempt["rendered_prompt_sha256"]:
            raise GateError(f"{label} measurement names another rendered prompt")
        if measurement["status"] != attempt["status"]:
            raise GateError(f"{label} status disagrees with its measurement")
        if attempt["generation_request"] != measurement["generation_request"]:
            raise GateError(f"{label} generation request is not its measurement's")
        if attempt["seed_attestation"] != measurement["seed_attestation"]:
            raise GateError(f"{label} seed attestation is not its measurement's")
        # Ladder rows 10 to 17 and row 12, on every attempt that ran rather than only on the row's
        # final one. Once a row can run twice, the row-level check binds only the last attempt.
        validate_measurement_version(measurement, task, f"{label} measurement")
        validate_measurement_probe(measurement, task, label)
        # `adapter_overhead_ns` is present exactly on a `PASS` attempt, where the adapter reports
        # its own generation window and the difference against the evaluator-observed span is
        # publishable rather than arguable.
        overhead = attempt.get("adapter_overhead_ns")
        if (overhead is not None) != (attempt["status"] == "PASS"):
            raise GateError(f"{label} adapter overhead presence does not agree with its status")
        if overhead is not None:
            reported = measurement["generation_to_passing_patch_ns"]
            if overhead < 0 or attempt["adapter_elapsed_ns"] - reported != overhead:
                raise GateError(f"{label} adapter overhead is not its measured difference")
    source = attempt.get("repair_prompt_source")
    if source is not None:
        if attempt["attempt_kind"] != "REPAIR":
            raise GateError(f"{label} initial attempt carries a repair prompt source")
        validate_repair_prompt_source(source, policy, f"{label} repair prompt source")
    return attempt


def validate_attempts(
    row: Mapping[str, Any],
    task: Mapping[str, Any],
    policy: Mapping[str, Any],
    pools: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    label: str,
) -> None:
    """Section 3.8 rows 16 to 19: attempt order, the repair bound, binding, and timing."""
    attempts = row["attempts"]
    if not isinstance(attempts, list) or not attempts:
        raise GateError(f"{label} carries no attempts")
    maximum_repair_loops = task["regression_limits"]["maximum_repair_loops"]
    # Bounded before anything iterates it: `1 + maximum_repair_loops` is the structural ceiling.
    if len(attempts) > 1 + maximum_repair_loops:
        raise GateError(f"{label} carries more attempts than its task admits")
    records = [
        validate_attempt_record(
            item, row, task, policy, pools, ordinal, f"{label} attempt {ordinal}",
        )
        for ordinal, item in enumerate(attempts, start=1)
    ]
    kinds = [item["attempt_kind"] for item in records]
    if kinds.count("INITIAL") != 1 or kinds[0] != "INITIAL":
        raise GateError(f"{label} does not begin with exactly one initial attempt")
    if kinds.count("REPAIR") > 1:
        raise GateError(f"{label} carries more than one repair attempt")
    ran = [item for item in records if item["status"] != "SKIPPED"]
    if not ran:
        raise GateError(f"{label} has no attempt that ran")
    # Each adapter invocation is single-attempt, so an adapter that reported a repair loop of its
    # own would double-count against the evaluator-owned row total. The check binds exactly where
    # double-counting is possible — a task that offers a repair attempt. Where none is offered the
    # adapter's value is carried verbatim and is simply not the authority, which is what keeps the
    # byte-frozen `scripts/prompt-fixed-adapter.py` usable unchanged.
    if maximum_repair_loops >= 1:
        for item in ran:
            if item["measurement"]["repair_loop_count"] != 0:
                raise GateError(f"{label} adapter reported a repair loop it cannot run")
    observed_loops = sum(
        item["attempt_kind"] == "REPAIR" and item["status"] != "SKIPPED" for item in records
    )
    if row["repair_loop_count"] != observed_loops:
        raise GateError(f"{label} repair loop count does not match its repair attempts")
    if row["repair_loop_count"] > maximum_repair_loops:
        raise GateError(f"{label} repair loop count exceeds its task limit")
    # Ladder row 18: version-1-shaped consumers keep reading `row.measurement` unchanged, so it
    # must be the final attempt that ran, byte for byte.
    if canonical_bytes(row["measurement"]) != canonical_bytes(ran[-1]["measurement"]):
        raise GateError(f"{label} measurement is not its final attempt's measurement")
    # Section 3.6: the evaluator-observed total through the first passing attempt, by exact
    # addition against the existing ceiling. Nothing saturates and nothing is clamped.
    total = 0
    computed: int | None = None
    for item in records:
        if item["status"] == "SKIPPED":
            continue
        total += item["adapter_elapsed_ns"] + item["repair_preparation_ns"]
        if item["status"] == "PASS":
            computed = total
            break
    persisted = row.get("generation_to_passing_patch_ns")
    if persisted != computed:
        raise GateError(f"{label} generation total is not the sum of its attempts")
    if computed is not None and (computed <= 0 or computed > TIMING_CEILING_NS):
        raise GateError(f"{label} generation total is outside its persisted bound")
    total_time = row.get("time_to_passing_patch_ns")
    if computed is None:
        if total_time is not None:
            raise GateError(f"{label} records a passing total without a passing attempt")
    else:
        expected_total = row["prompt_preparation_ns"] + computed
        if total_time != expected_total:
            raise GateError(f"{label} total time is not preparation plus generation")
        if total_time <= 0 or total_time > TIMING_CEILING_NS:
            raise GateError(f"{label} total time is outside its persisted bound")


def row_repair_loop_count(row: Mapping[str, Any]) -> int:
    """One producer per field, selected by version and never by presence.

    At version 1 the authority is `row.measurement.repair_loop_count`, exactly as it always was.
    At version 2 the evaluator owns the count and writes it at the row level, because a repair
    attempt is a second adapter invocation and no single adapter document can see both.
    """
    if row["schema_version"] >= 2:
        return row["repair_loop_count"]
    return row["measurement"]["repair_loop_count"]


def row_repair_editset_attempts(row: Mapping[str, Any]) -> int:
    """C4-REPAIR-EDITSET's denominator, recomputed and never trusted from the persisted document.

    A repair attempt contributes when it ran and its own `repair_prompt_source.included_sections`
    names `EDITSET`, so a row that dropped the section under the budget ladder is excluded from
    every edit-set claim by a persisted number rather than by an argument.
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


def row_edit_refusal_count(row: Mapping[str, Any]) -> int:
    """C4-REPAIR-TEMPLATE's secondary counter, recomputed and never trusted from the document.

    An attempt contributes when it ran and its `measurement.edit_refusal` is not `NONE`. Only a
    version-3 measurement defines the quantity, so a row from an earlier corpus contributes nothing
    and its corpus records the member absent rather than zero.
    """
    if row["schema_version"] < 2:
        return 0
    total = 0
    for attempt in row["attempts"]:
        measurement = attempt.get("measurement")
        if attempt["status"] == "SKIPPED" or not measurement:
            continue
        if measurement.get("edit_refusal") not in (None, "NONE"):
            total += 1
    return total


def row_repair_attempted(row: Mapping[str, Any]) -> bool:
    return row["schema_version"] >= 2 and row["repair_loop_count"] >= 1


def row_repair_recovered(row: Mapping[str, Any]) -> bool:
    """The section 1.4 gate predicate, evaluated on one row."""
    if row["schema_version"] < 2:
        return False
    attempts = row["attempts"]
    return (
        len(attempts) == 2
        and attempts[0]["attempt_kind"] == "INITIAL"
        and attempts[0]["status"] == "FAIL"
        and attempts[1]["attempt_kind"] == "REPAIR"
        and attempts[1]["status"] == "PASS"
    )


def scored_attempts(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The attempts that actually ran. A `SKIPPED` attempt is recorded but never scored."""
    return [item for item in row["attempts"] if item["status"] != "SKIPPED"]


def rescore(
    result: Mapping[str, Any], policy: Mapping[str, Any]
) -> tuple[str, list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """Recompute the section 8 aggregates, status, and serious-regression stream."""
    version = result["schema_version"]
    tasks = result["tasks"]
    rows = result["rows"]
    sample_count = result["sample_count"]
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
    corpus_edit_refusals = 0
    editset_corpus = any(
        list(task.get("argv") or [])[1:] in ([REPAIR_ADAPTER_RELATIVE], [TEMPLATE_ADAPTER_RELATIVE])
        for task in tasks
    )
    template_corpus = any(
        list(task.get("argv") or [])[1:] == [TEMPLATE_ADAPTER_RELATIVE] for task in tasks
    )
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
        task_parent_repairs = sum(row_repair_loop_count(row) for row in parent_rows)
        task_candidate_repairs = sum(row_repair_loop_count(row) for row in candidate_rows)
        parent_refusals = sum(row_edit_refusal_count(row) for row in parent_rows)
        candidate_refusals = sum(row_edit_refusal_count(row) for row in candidate_rows)
        parent_editset = sum(row_repair_editset_attempts(row) for row in parent_rows)
        candidate_editset = sum(row_repair_editset_attempts(row) for row in candidate_rows)
        parent_attempted = sum(row_repair_attempted(row) for row in parent_rows)
        candidate_attempted = sum(row_repair_attempted(row) for row in candidate_rows)
        parent_recovered = sum(row_repair_recovered(row) for row in parent_rows)
        candidate_recovered = sum(row_repair_recovered(row) for row in candidate_rows)
        # A (task, variant) pair counts only when *every* paired sample recovered, so a single
        # lucky sample is not a reproducible recovery.
        parent_paired_recovery = bool(parent_rows) and all(
            row_repair_recovered(row) for row in parent_rows
        )
        candidate_paired_recovery = bool(candidate_rows) and all(
            row_repair_recovered(row) for row in candidate_rows
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
        aggregate = {
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
        if version >= 2:
            aggregate.update({
                "parent_repair_attempt_count": parent_attempted,
                "candidate_repair_attempt_count": candidate_attempted,
                "parent_repair_recovery_count": parent_recovered,
                "candidate_repair_recovery_count": candidate_recovered,
                "repair_recovery_paired": parent_paired_recovery or candidate_paired_recovery,
            })
            if editset_corpus:
                aggregate.update({
                    "parent_repair_editset_attempt_count": parent_editset,
                    "candidate_repair_editset_attempt_count": candidate_editset,
                })
            if template_corpus:
                aggregate.update({
                    "parent_edit_refusal_count": parent_refusals,
                    "candidate_edit_refusal_count": candidate_refusals,
                })
            corpus_edit_refusals += parent_refusals + candidate_refusals
            corpus_repair_editset += parent_editset + candidate_editset
            corpus_repair_attempts += parent_attempted + candidate_attempted
            corpus_repair_recoveries += parent_recovered + candidate_recovered
            corpus_repair_recovery_paired += int(parent_paired_recovery) + int(
                candidate_paired_recovery
            )
        aggregates.append(aggregate)
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
    if version >= 2:
        corpus.update({
            "repair_attempt_count": corpus_repair_attempts,
            "repair_recovery_count": corpus_repair_recoveries,
            "repair_recovery_paired_count": corpus_repair_recovery_paired,
        })
        if editset_corpus:
            # Present only for a corpus whose adapter can render the section; see the evaluator's
            # note. Requiring it at version 2 unconditionally would reject the merged
            # `eval/prompt/c4-repair-gate/` evidence, which predates this capability.
            corpus["repair_editset_attempt_count"] = corpus_repair_editset
        if template_corpus:
            corpus["edit_refusal_count"] = corpus_edit_refusals

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
            # record keeps its exact existing shape and position; the parent arm gets a
            # distinguishable one, emitted first.
            parent_loops = row_repair_loop_count(parent_row)
            if parent_loops > limit["maximum_repair_loops"]:
                reasons.append(
                    reason(
                        task["task_id"],
                        sample,
                        "REPAIR_LOOPS",
                        str(parent_loops),
                        "NONE",
                        str(limit["maximum_repair_loops"]),
                    )
                )
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
            candidate_loops = row_repair_loop_count(candidate_row)
            if candidate_loops > limit["maximum_repair_loops"]:
                reasons.append(
                    reason(
                        task["task_id"],
                        sample,
                        "REPAIR_LOOPS",
                        "NONE",
                        str(candidate_loops),
                        str(limit["maximum_repair_loops"]),
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


def validate_embedded_references(result: Mapping[str, Any]) -> None:
    """Bind every declared `ArtifactReference` to the artifact the same result embeds.

    Each `*_source` field is a reference the evaluator wrote beside the decoded document it read.
    The gate recomputes the embedded document's own digest elsewhere; here it requires the reference
    to name that exact kind, identity, and digest, so a rewritten reference cannot survive.
    """
    for source_name, artifact_name, kind, identity in EMBEDDED_REFERENCES:
        label = f"evaluation {source_name}"
        reference = validate_reference(result.get(source_name), kind, label)
        artifact = result.get(artifact_name)
        if not isinstance(artifact, dict):
            raise GateError(f"evaluation {artifact_name} is not an object")
        if require_own_digest(artifact, f"evaluation {artifact_name}") != reference["content_sha256"]:
            raise GateError(f"{label} digest does not match the embedded {artifact_name}")
        if reference["artifact_id"] != artifact.get(identity):
            raise GateError(f"{label} names another {artifact_name}")
        if artifact.get("artifact_kind") != kind:
            raise GateError(f"evaluation {artifact_name} is not a {kind}")


def validate_corpus_coverage(result: Mapping[str, Any], scope: Mapping[str, Any]) -> None:
    """Require the frozen corpus manifest and the evaluated task list to be the same task set.

    The evaluator loads `tasks[i]` from `corpus.task_files[i]` and passes that same relative path
    into task `i`'s automatic snapshot, so the persisted evidence carries the positional link. The
    gate re-derives it: every declared task file is the snapshotted manifest of the task at its
    ordinal, and no snapshot names a task the corpus does not declare.
    """
    corpus = exact_record(result.get("corpus"), CORPUS_FIELDS, "evaluation corpus")
    if corpus["schema_version"] != 1 or corpus["artifact_kind"] != "PROMPT_EVALUATION_CORPUS":
        raise GateError("evaluation corpus header is invalid")
    if corpus["corpus_id"] != scope["corpus_id"]:
        raise GateError("evaluation corpus id disagrees with its scope")
    if corpus["corpus_revision"] != scope["corpus_revision"]:
        raise GateError("evaluation corpus revision disagrees with its scope")
    task_files = corpus["task_files"]
    tasks = result["tasks"]
    if not isinstance(task_files, list) or not task_files:
        raise GateError("evaluation corpus declares no task files")
    for ordinal, relative in enumerate(task_files):
        require_bundle_relative(relative, f"evaluation corpus task file {ordinal}")
    if len(set(task_files)) != len(task_files):
        raise GateError("evaluation corpus declares one task file twice")
    if len(task_files) != len(tasks):
        raise GateError("evaluation corpus task files do not cover the evaluated tasks exactly")
    task_ids = [task["task_id"] for task in tasks]
    if len(set(task_ids)) != len(task_ids):
        raise GateError("evaluation tasks repeat one task id")
    declared = set(task_files)
    snapshots = result["input_snapshots"]
    covered: set[str] = set()
    for ordinal, task in enumerate(tasks):
        group = [item for item in snapshots if item["task_id"] == task["task_id"]]
        if not group:
            raise GateError("an evaluated task carries no input snapshot")
        for snapshot in group:
            if snapshot["task_manifest_sha256"] != task["content_sha256"]:
                raise GateError("an input snapshot names another task manifest")
            named = {entry["path"] for entry in snapshot["artifact_digests"]} & declared
            if named != {task_files[ordinal]}:
                raise GateError("an input snapshot does not observe its declared task file")
        covered.add(task["task_id"])
    if {item["task_id"] for item in snapshots} != covered:
        raise GateError("the input snapshots cover a task the corpus does not declare")
    # Section 3.8 row 23: one input snapshot per *contained invocation*, not per row. At version 1
    # a row runs exactly once and this is the row count it has always been; at version 2 a row may
    # run a repair attempt, which seals its own prompt and so produces its own input snapshot. A
    # `SKIPPED` repair made no invocation and buys no snapshot. Mirrors
    # `verifier_rows_and_attestations_valid` (`src/prompt_score.align:5024`-`5025`).
    if len(snapshots) > count_ran_invocations(result):
        raise GateError("the input snapshots outnumber the run's contained invocations")


def count_ran_invocations(result: Mapping[str, Any]) -> int:
    """Contained invocations across the document: one per row, plus each repair that ran."""
    rows = result.get("rows")
    if not isinstance(rows, list):
        raise GateError("gate evaluation has no rows")
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            raise GateError("evaluation row is not an object")
        attempts = row.get("attempts")
        if attempts is None:
            total += 1
            continue
        if not isinstance(attempts, list) or not attempts:
            raise GateError("an evaluation row carries no attempts")
        for attempt in attempts:
            if not isinstance(attempt, dict):
                raise GateError("an evaluation attempt is not an object")
            if attempt.get("status") != "SKIPPED":
                total += 1
    return total


def validate_snapshot_closure(
    result: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, list[Mapping[str, Any]]]]:
    """Require complete, matching before/after snapshot observation for every scored row.

    Returns the persisted-record pool per trace stream, keyed by each record's own digest, so an
    attempt record's four trace digests resolve to exactly the documents this validator already
    admitted rather than merely being tested for membership.
    """
    pools: dict[str, dict[str, list[Mapping[str, Any]]]] = {}
    for name, fields, kind, label in (
        ("snapshot_requests", None, "SNAPSHOT_REQUEST", "snapshot request"),
        ("snapshot_results", SNAPSHOT_RESULT_FIELDS, "SNAPSHOT_RESULT", "snapshot result"),
        ("input_snapshots", INPUT_SNAPSHOT_FIELDS, "TASK_INPUT_SNAPSHOT", "input snapshot"),
        (
            "snapshot_attestations",
            SNAPSHOT_ATTESTATION_FIELDS,
            "RUN_SNAPSHOT_ATTESTATION",
            "snapshot attestation",
        ),
    ):
        stream = result.get(name)
        if not isinstance(stream, list) or not stream:
            raise GateError(f"gate evaluation carries no {label} stream")
        digests: dict[str, list[Mapping[str, Any]]] = {}
        for item in stream:
            if not isinstance(item, dict):
                raise GateError(f"a {label} is not an object")
            if fields is not None:
                exact_record(item, fields, label)
            if item.get("schema_version") != 1 or item.get("artifact_kind") != kind:
                raise GateError(f"a {label} header is invalid")
            digests.setdefault(require_own_digest(item, label), []).append(item)
        pools[name] = digests

    for item in result["snapshot_results"]:
        if item["status"] != "MATCH" or item["error_code"] != "NONE" or item["error"] != "":
            raise GateError("a snapshot result is not MATCH")

    attestations = result["snapshot_attestations"]
    if len(attestations) != len(rows):
        raise GateError("the snapshot attestations do not cover every row exactly once")
    for attestation, row in zip(attestations, rows):
        if (attestation["task_id"], attestation["sample_index"], attestation["variant"]) != (
            row["task_id"],
            row["sample_index"],
            row["variant"],
        ):
            raise GateError("a snapshot attestation is out of row order")
        if (
            attestation["status"] != "COMPLETE"
            or attestation["error_code"] != "NONE"
            or attestation["error"] != ""
        ):
            raise GateError("a snapshot attestation is not COMPLETE")
        if (
            attestation["before_snapshot_result_sha256"]
            != attestation["after_snapshot_result_sha256"]
            or attestation["before_input_snapshot_sha256"]
            != attestation["after_input_snapshot_sha256"]
        ):
            raise GateError("a snapshot attestation records observed drift")
        for field, pool in (
            ("snapshot_request_sha256", "snapshot_requests"),
            ("before_snapshot_result_sha256", "snapshot_results"),
            ("after_snapshot_result_sha256", "snapshot_results"),
            ("before_input_snapshot_sha256", "input_snapshots"),
            ("after_input_snapshot_sha256", "input_snapshots"),
        ):
            if require_digest(attestation[field], f"attestation {field}") not in pools[pool]:
                raise GateError(f"a snapshot attestation {field} names no persisted record")
    return pools


def validate_workspace_preflight(result: Mapping[str, Any], evaluation_id: str) -> None:
    """The workspace admission this evaluation actually ran under must be SAFE."""
    request = exact_record(
        result.get("workspace_preflight_request"),
        WORKSPACE_PREFLIGHT_REQUEST_FIELDS,
        "workspace preflight request",
    )
    if (
        request["schema_version"] != 1
        or request["artifact_kind"] != "WORKSPACE_PREFLIGHT_REQUEST"
        or request["evaluation_id"] != evaluation_id
    ):
        raise GateError("workspace preflight request header or identity is invalid")
    require_own_digest(request, "workspace preflight request")
    preflight = exact_record(
        result.get("workspace_preflight"), WORKSPACE_PREFLIGHT_FIELDS, "workspace preflight"
    )
    if (
        preflight["schema_version"] != 1
        or preflight["artifact_kind"] != "WORKSPACE_PREFLIGHT_RESULT"
        or preflight["evaluation_id"] != evaluation_id
    ):
        raise GateError("workspace preflight header or identity is invalid")
    if (
        preflight["status"] != "SAFE"
        or preflight["error_code"] != "NONE"
        or preflight["error"] != ""
    ):
        raise GateError("gate evaluation workspace preflight is not SAFE")


def validate_provider_binding(result: Mapping[str, Any], scope: Mapping[str, Any]) -> None:
    """Bind the executable provider control to the scope and the generation policy that named it."""
    control = result.get("provider_control")
    policy = result.get("generation_policy")
    if not isinstance(control, dict) or not isinstance(policy, dict):
        raise GateError("gate evaluation has no provider control or generation policy")
    if control.get("provider_kind") == "FIXTURE":
        raise GateError("gate evaluation used the FIXTURE provider")
    if policy["provider_control_sha256"] != control["content_sha256"]:
        raise GateError("generation policy does not bind the evaluated provider control")
    for policy_name, control_name in (
        ("evaluation_provider_kind", "provider_kind"),
        ("evaluation_provider_endpoint_id", "endpoint_id"),
        ("evaluation_provider_model", "model"),
    ):
        if policy[policy_name] != control[control_name]:
            raise GateError(f"generation policy {policy_name} disagrees with the provider control")
    for scope_name, control_name in (
        ("evaluation_provider_kind", "provider_kind"),
        ("evaluation_provider_model", "model"),
    ):
        if scope[scope_name] != control[control_name]:
            raise GateError(f"evaluation scope {scope_name} disagrees with the provider control")


def validate_evaluation_pair(
    result: dict[str, Any], evidence: dict[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    """Re-verify the improved evaluation and its independently produced evidence."""
    exact_record(result, EVALUATION_RESULT_FIELDS, "evaluation result", EVALUATION_RESULT_OPTIONAL)
    # C4-REPAIR-MEASURED section 3.2: the container's version selects the row record, and it is
    # read before any row field is decoded. Version 1 stays decodable, byte for byte, forever.
    version = result["schema_version"]
    if version not in (1, 2) or result["artifact_kind"] != "PROMPT_EVALUATION_RESULT":
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
    # The evidence container moves in lockstep with the result: it carries the expected-input
    # records whose shape and cardinality the result's version fixes.
    if (
        evidence["schema_version"] != version
        or evidence["artifact_kind"] != "PROMPT_EVALUATION_EVIDENCE"
    ):
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
    # Section 4.2: the scope's prompt digests are the evaluated hierarchy, so both variants must
    # carry exactly those nested prompts. This mirrors `valid_activation_shape`.
    bind_scope_prompts(scope, result["parent_variant"], "gate evaluation parent")
    bind_scope_prompts(scope, result["candidate_variant"], "gate evaluation candidate")

    # Every reference the result declares is bound to the artifact the same result embeds, and the
    # embedded policies are bound back to the scope digests that name them.
    validate_embedded_references(result)
    if scope["acceptance_policy_sha256"] != result["acceptance_policy"]["content_sha256"]:
        raise GateError("evaluation scope acceptance policy digest is not the evaluated policy")
    if scope["generation_policy_sha256"] != result["generation_policy"]["content_sha256"]:
        raise GateError("evaluation scope generation policy digest is not the evaluated policy")
    validate_provider_binding(result, scope)
    validate_workspace_preflight(result, evaluation_id)
    validate_corpus_coverage(result, scope)

    rows = result["rows"]
    if not isinstance(rows, list) or not rows:
        raise GateError("gate evaluation has no rows")
    trace_pools = validate_snapshot_closure(result, rows)
    row_fields = TASK_ROW_V1_FIELDS if version == 1 else TASK_ROW_V2_FIELDS
    row_optional = TASK_ROW_V1_OPTIONAL if version == 1 else TASK_ROW_V2_OPTIONAL
    tasks_by_id = {task["task_id"]: task for task in result["tasks"]}
    generation_policy = result["generation_policy"]
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise GateError("evaluation row is not an object")
        # A row whose own version disagrees with the container's is rejected before any field
        # decode. The two shapes are never migrated into one another.
        if row.get("schema_version") != version:
            raise GateError("evaluation row version disagrees with its container")
        exact_record(row, row_fields, f"evaluation row {index}", row_optional)
        if row["artifact_kind"] != "PROMPT_TASK_ROW":
            raise GateError(f"evaluation row {index} header is invalid")
        if row.get("evaluation_id") != evaluation_id:
            raise GateError("evaluation row is bound to another evaluation")
        expected_variant = parent_digest if row.get("variant") == "PARENT" else candidate_digest
        if row.get("variant_sha256") != expected_variant:
            raise GateError("evaluation row variant digest does not match its named variant")
        if row["measurement"]["seed_attestation"]["result"] != "APPLIED":
            raise GateError("gate evaluation row does not carry an APPLIED seed attestation")
        row_task = tasks_by_id.get(row["task_id"])
        if row_task is None:
            raise GateError(f"evaluation row {index} names a task the corpus does not declare")
        validate_measurement_version(
            row["measurement"], row_task, f"evaluation row {index} measurement",
        )
        validate_measurement_probe(row["measurement"], row_task, f"evaluation row {index}")
        if version >= 2:
            task = row_task
            validate_attempts(
                row, task, generation_policy, trace_pools, f"evaluation row {index}"
            )

    expected_inputs = evidence["expected_inputs"]
    if not isinstance(expected_inputs, list):
        raise GateError("evidence expected inputs are not a list")
    if version == 1:
        # Unchanged: one digest per row, positionally, in row order.
        if len(expected_inputs) != len(rows):
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
                    raise GateError(
                        f"evidence expected input {index} {name} does not match its row"
                    )
    else:
        # Section 3.2: one record per attempt that ran, keyed on
        # (task, sample, variant, attempt_index), with no duplicate, missing, or extra identity.
        # The producer appends inside the attempt loop, so the order is row order then attempt
        # order and the positional rule still holds.
        scheduled = [(row, attempt) for row in rows for attempt in scored_attempts(row)]
        if len(expected_inputs) != len(scheduled):
            raise GateError("evidence expected inputs do not cover every attempt exactly once")
        attempt_identities: set[tuple[str, int, str, int]] = set()
        for index, (expected, (row, attempt)) in enumerate(zip(expected_inputs, scheduled)):
            exact_record(expected, EXPECTED_INPUT_V2_FIELDS, f"evidence expected input {index}")
            if (
                expected["schema_version"] != 2
                or expected["artifact_kind"] != "PROMPT_EXPECTED_INPUT_DIGEST"
            ):
                raise GateError(f"evidence expected input {index} header is invalid")
            identity = (
                expected["task_id"],
                expected["sample_index"],
                expected["variant"],
                expected["attempt_index"],
            )
            if identity != (
                row["task_id"], row["sample_index"], row["variant"], attempt["attempt_index"],
            ):
                raise GateError(f"evidence expected input {index} is out of attempt order")
            if identity in attempt_identities:
                raise GateError("evidence expected inputs repeat one attempt identity")
            attempt_identities.add(identity)
            evaluation_input = row["evaluation_input"]
            generation = attempt["generation_request"]
            for name, actual in (
                ("rendered_prompt_sha256", attempt["rendered_prompt_sha256"]),
                ("context_sources_sha256", evaluation_input["context_sources_sha256"]),
                ("generation_request_sha256", generation["content_sha256"]),
                ("adapter_request_sha256", attempt["adapter_request_sha256"]),
                ("provider_request_sha256", generation["provider_request_sha256"]),
            ):
                if expected[name] != actual:
                    raise GateError(
                        f"evidence expected input {index} {name} does not match its attempt"
                    )

    policy = validate_acceptance_policy(result.get("acceptance_policy"))
    status, aggregates, corpus, reasons = rescore(result, policy)
    if reasons:
        raise GateError("recomputed scoring finds a serious regression the gate result omits")
    if status != "IMPROVED":
        raise GateError(f"recomputed acceptance decision is {status}, not IMPROVED")
    persisted_aggregates = result["task_aggregates"]
    if not isinstance(persisted_aggregates, list) or len(persisted_aggregates) != len(aggregates):
        raise GateError("persisted task aggregates do not cover every task")
    task_aggregate_fields = TASK_AGGREGATE_FIELDS if version == 1 else TASK_AGGREGATE_V2_FIELDS
    corpus_aggregate_fields = (
        CORPUS_AGGREGATE_FIELDS if version == 1 else CORPUS_AGGREGATE_V2_FIELDS
    )
    for persisted, computed in zip(persisted_aggregates, aggregates):
        exact_record(persisted, task_aggregate_fields, "task aggregate", AGGREGATE_OPTIONAL)
        # Both sides are completed, because an `Option::None` is canonically omitted on the
        # persisted side and the recompute omits the same member for the same reason. Comparing a
        # completed persisted record against a raw computed one would read an omission as a
        # disagreement and reject a document that is exactly right.
        if completed_record(persisted, task_aggregate_fields) != completed_record(
            computed, task_aggregate_fields
        ):
            raise GateError("persisted task aggregate disagrees with the recomputed value")
    persisted_corpus = result.get("corpus_aggregate")
    exact_record(persisted_corpus, corpus_aggregate_fields, "corpus aggregate", AGGREGATE_OPTIONAL)
    if completed_record(persisted_corpus, corpus_aggregate_fields) != completed_record(
        corpus, corpus_aggregate_fields
    ):
        raise GateError("persisted corpus aggregate disagrees with the recomputed value")

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
    # Section 4.4: an envelope-level `ArtifactReference` uses the envelope `decision_id` and
    # envelope digest, while lineage inside `PromptActivation` uses the nested activation ID and
    # digest. `src/prompt_state.align` links the nested identity, so the gate compares that.
    if (
        accepted_activation["parent_activation_id"] != baseline_activation["activation_id"]
        or accepted_activation["parent_activation_sha256"]
        != baseline_activation["content_sha256"]
    ):
        raise GateError("accepted activation parent is not the evaluated baseline")
    if (
        accepted_activation["accepted_evaluation_id"] != result["evaluation_id"]
        or accepted_activation["accepted_evaluation_sha256"] != result["content_sha256"]
    ):
        raise GateError("accepted activation does not name the improved evaluation")
    if (
        rollback_activation["parent_activation_id"] != accepted_activation["activation_id"]
        or rollback_activation["parent_activation_sha256"]
        != accepted_activation["content_sha256"]
    ):
        raise GateError("rollback activation parent is not the accepted activation")
    if (
        rollback_activation["rollback_target_activation_id"]
        != baseline_activation["activation_id"]
        or rollback_activation["rollback_target_activation_sha256"]
        != baseline_activation["content_sha256"]
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
    generation_child_sha256: str,
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
    # The third leg of the derived-child identity: the retained bytes were already proven equal to
    # the declared input, so binding that input to the checked-in locator rejects a gate run whose
    # child is a different binary than the reviewed evidence records.
    if generation_child_sha256 != locator["generation_child_sha256"]:
        raise GateError("explicit generation child digest does not match the gate locator")

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


def bind_environment_identity(
    core: Mapping[str, Any], locator: Mapping[str, Any], environment_policy: Mapping[str, Any]
) -> None:
    """Bind the producer-owned environment identity to the checked-in gate inputs.

    `EnvironmentIdentityCore` records the source-verifier runtime and policy digest the measurement
    ran under and the environment policy the adapters were launched with. All three are checked-in
    gate inputs, so the gate requires the recorded identity to be the reviewed one rather than an
    unverified claim.
    """
    for core_name, locator_name in (
        ("source_verifier_runtime", "source_verifier_runtime"),
        ("source_verifier_policy_sha256", "source_verifier_policy_sha256"),
    ):
        if core.get(core_name) != locator[locator_name]:
            raise GateError(f"evaluation environment {core_name} disagrees with the gate locator")
    if core.get("environment_policy_sha256") != environment_policy["content_sha256"]:
        raise GateError("evaluation environment policy digest is not the checked-in gate policy")


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
            environment_policy = load_referenced(
                directory, manifest["environment_policy"], POLICY_LIMIT, "gate environment policy"
            )
            if (
                environment_policy.get("schema_version") != 1
                or environment_policy.get("artifact_kind") != "ENVIRONMENT_POLICY"
            ):
                raise GateError("gate environment policy header is invalid")
            if manifest["environment_policy"]["artifact_id"] != environment_policy.get(
                ENVIRONMENT_POLICY_IDENTITY
            ):
                raise GateError("gate manifest environment policy reference names another policy")
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
            bind_environment_identity(
                result["environment"]["core"], manifest["source_locator"], environment_policy
            )
            observe_source_bundle(
                manifest["source_locator"],
                evidence["trust"],
                resolved_root,
                python,
                GitTool(git_executable),
                checkout,
                child_digest,
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
