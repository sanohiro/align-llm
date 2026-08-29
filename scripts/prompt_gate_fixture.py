#!/usr/bin/env python3
"""Build a minimal but complete C6 prompt gate evidence bundle for owner smokes.

The bundle is derived from the checked-in `eval/fixtures/c6-prompt-state/templates.jsonl`
artifacts, so the fixture chain uses the same record shapes the shipped evaluator and
activation owners produce. The builder rebinds every gate-chain digest, so a rejection
family only has to mutate one field and rebind the artifacts it owns.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PROJECT_ROOT / "eval" / "fixtures" / "c6-prompt-state" / "templates.jsonl"
SOURCE_VERIFIER = PROJECT_ROOT / "scripts" / "prompt-source-verifier.py"
GIT = Path(os.environ.get("ALIGN_LLM_TOOL_ROOT", "/usr/bin")) / "git"

MANIFEST_NAME = "prompt-gate-manifest.json"
BASELINE_NAME = "prompt-activation-baseline-v1.json"
EVALUATION_NAME = "prompt-evaluation-improved.json"
EVIDENCE_NAME = "prompt-evaluation-improved-evidence.json"
ACCEPTED_NAME = "prompt-activation-accepted.json"
ROLLBACK_NAME = "prompt-activation-rolled-back.json"
ENVIRONMENT_POLICY_NAME = "environment-policy.json"
POLICY_RELATIVE = "source-verifier-policy.json"
VERIFIER_RELATIVE = "prompt-source-verifier.py"
GENERATION_CHILD_RELATIVE = "build/main"


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


def bind(value: dict[str, Any]) -> dict[str, Any]:
    value["content_sha256"] = ""
    value["content_sha256"] = hashlib.sha256(canonical_digest_bytes(value)).hexdigest()
    return value


def bind_variant(value: dict[str, Any]) -> dict[str, Any]:
    bind(value["base_prompt"])
    bind(value["repo_prompt"])
    return bind(value)


def bind_scope(value: dict[str, Any], variant: Mapping[str, Any]) -> dict[str, Any]:
    bind(value["corpus_revision"])
    value["base_prompt_sha256"] = variant["base_prompt"]["content_sha256"]
    value["repo_prompt_sha256"] = variant["repo_prompt"]["content_sha256"]
    return bind(value)


def bind_activation(value: dict[str, Any]) -> dict[str, Any]:
    activation = value["activation"]
    bind_variant(activation["effective_variant"])
    bind_scope(activation["scope"], activation["effective_variant"])
    bind(activation)
    return bind(value)


def bind_declared_inputs(result: dict[str, Any]) -> None:
    """Bind the corpus, task, snapshot, and preflight documents the gate now cross-checks.

    The shipped evaluator emits one consistent set of declared inputs: the corpus names the task
    files, each task's automatic snapshot observes its own task file, every attestation names the
    exact snapshot documents it observed, and each `*_source` reference carries the digest of the
    document the same result embeds. The fixture reproduces those links so a rejection family only
    has to break the one it owns.
    """
    for task in result["tasks"]:
        bind(task)
    task_files = result["corpus"]["task_files"]
    bind(result["corpus"])
    for ordinal, snapshot in enumerate(result["input_snapshots"]):
        task = result["tasks"][min(ordinal, len(result["tasks"]) - 1)]
        snapshot["task_id"] = task["task_id"]
        snapshot["task_manifest_sha256"] = task["content_sha256"]
        declared = task_files[min(ordinal, len(task_files) - 1)]
        if all(entry["path"] != declared for entry in snapshot["artifact_digests"]):
            snapshot["artifact_digests"].append(
                {
                    "path": declared,
                    "mode": "100644",
                    "byte_count": 1,
                    "sha256": task["content_sha256"],
                }
            )
        bind(snapshot)
    for stream in ("snapshot_requests", "snapshot_results"):
        for item in result[stream]:
            bind(item)
    request_digest = result["snapshot_requests"][0]["content_sha256"]
    snapshot_digest = result["snapshot_results"][0]["content_sha256"]
    input_digest = result["input_snapshots"][0]["content_sha256"]
    for attestation in result["snapshot_attestations"]:
        attestation["snapshot_request_sha256"] = request_digest
        attestation["before_snapshot_result_sha256"] = snapshot_digest
        attestation["after_snapshot_result_sha256"] = snapshot_digest
        attestation["before_input_snapshot_sha256"] = input_digest
        attestation["after_input_snapshot_sha256"] = input_digest
        bind(attestation)
    # C4-REPAIR-MEASURED: at version 2 a row may run more than one contained invocation, and one
    # positional attestation per row can no longer reach the second one's trace records. Every
    # attempt that ran therefore names them itself, and the fixture binds them to the same
    # persisted documents the attestation names, so an attempt digest resolves inside this
    # document's own pools exactly as a real run's does.
    for row in result["rows"]:
        attempts = row.get("attempts")
        if not attempts:
            continue
        for attempt in attempts:
            if attempt["status"] == "SKIPPED":
                continue
            attempt["snapshot_request_sha256"] = request_digest
            attempt["before_snapshot_result_sha256"] = snapshot_digest
            attempt["after_snapshot_result_sha256"] = snapshot_digest
            attempt["input_snapshot_sha256"] = input_digest
            bind(attempt)
        bind(row)
    bind(result["workspace_preflight_request"])
    bind(result["workspace_preflight"])
    for source_name, artifact_name in (
        ("corpus_source", "corpus"),
        ("acceptance_policy_source", "acceptance_policy"),
        ("generation_policy_source", "generation_policy"),
        ("provider_control_source", "provider_control"),
        ("workspace_preflight_source", "workspace_preflight"),
    ):
        result[source_name]["content_sha256"] = result[artifact_name]["content_sha256"]


# --- C4-REPAIR-MEASURED: the version-2 fixture --------------------------------------------------
# `docs/specs/c4-repair-measured.md` sections 3.2 and 3.6. The upgrade keeps every row's final
# measurement status, and therefore every version-1 aggregate, exactly where the template put it;
# what it adds is the attempt stream underneath, the row-level repair count, and the
# evaluator-observed totals that reproduce the same `time_to_passing_patch_ns` the row already
# carried. So a version-2 rejection family differs from its version-1 sibling in the attempt
# machinery alone.
ATTEMPT_ELAPSED_INITIAL_NS = 30
ATTEMPT_ELAPSED_REPAIR_NS = 50
ATTEMPT_REPAIR_PREPARATION_NS = 10
ATTEMPT_OVERHEAD_NS = 10


def synthetic_digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


# C4-REPAIR-EDITSET. The version-2 fixture corpus names `scripts/prompt-repair-adapter.py`, so
# ladder row 11 requires every attempt measurement to be version 2, and the version-2 members are
# emitted here rather than defaulted anywhere. `EDITSET_BODY` is a plausible whole-file answer; the
# validator recomputes `body_sha256` over it, so it cannot be a placeholder.
REPAIR_ADAPTER_RELATIVE = "scripts/prompt-repair-adapter.py"
# C4-REPAIR-TEMPLATE. The fixture corpus now names the third adapter, so ladder row 16 requires
# every attempt measurement to be version 3 and the version-3 members are emitted here rather than
# defaulted anywhere. `COMPLETION_TEXT` is the model prose the one refused row actually produced;
# the validator bounds it and ties it to the refusal code, so it cannot be a placeholder either.
TEMPLATE_ADAPTER_RELATIVE = "scripts/prompt-template-adapter.py"
TEMPLATE_ADAPTER_RUNTIME = "PYTHON:" + synthetic_digest("prompt-template-adapter")[:64]
COMPLETION_TEXT = "I would change src/duration.py to divide by sixty.\n"
REPAIR_ADAPTER_RUNTIME = "PYTHON:" + synthetic_digest("prompt-repair-adapter")[:64]
BASE_ADAPTER_RUNTIME = "PYTHON:" + synthetic_digest("prompt-measurement-adapter")[:64]
# Two blocks, not one, and that is a coverage requirement rather than a flourish: a single-block
# edit set cannot falsify the ladder row that requires paths to be unique and ascending, so every
# mutant of that row survived while this fixture emitted one block.
EDITSET_PATH = "src/duration.py"
EDITSET_BODY = "def round_to_minutes(seconds):\n    return seconds // 60\n"
SECOND_EDITSET_PATH = "tests/test_duration.py"
SECOND_EDITSET_BODY = "def test_round_to_minutes():\n    assert True\n"
EDITSET_EDITS = ((EDITSET_PATH, EDITSET_BODY), (SECOND_EDITSET_PATH, SECOND_EDITSET_BODY))


def edit_set_block(path: str, body: str) -> dict[str, Any]:
    return bind(
        {
            "schema_version": 1,
            "artifact_kind": "EDIT_SET_BLOCK",
            "path": path,
            "body_bytes": len(body.encode("utf-8")),
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "body_text": body,
            "content_sha256": "",
        }
    )


def edit_set_blocks() -> list[dict[str, Any]]:
    return [edit_set_block(path, body) for path, body in EDITSET_EDITS]


# Named here rather than imported from the validator: a smoke that read the bound from the module
# under test could not falsify a mutant that moved it.
MAXIMUM_FILE_BLOCKS_FOR_SMOKE = 32


def applied_edits_text() -> str:
    """The `applied edits: ` tail ladder row 17 cross-checks against the block path list."""
    return ", ".join(path for path, _ in EDITSET_EDITS)


def attempt_measurement(
    template: Mapping[str, Any], *, passing: bool, rendered: str, generation_ns: int | None,
    carries_edit_set: bool = True,
) -> dict[str, Any]:
    """One attempt's own `TaskMeasurement`, at the template adapter's version 3."""
    measurement = copy.deepcopy(dict(template))
    measurement["status"] = "PASS" if passing else "FAIL"
    measurement["failure_kind"] = "NONE" if passing else "TEST"
    measurement["build_status"] = "PASS"
    measurement["test_status"] = "PASS" if passing else "FAIL"
    # Every adapter invocation is single-attempt, so its own repair count is zero on every attempt.
    measurement["repair_loop_count"] = 0
    measurement["rendered_prompt_sha256"] = rendered
    if generation_ns is None:
        measurement.pop("generation_to_passing_patch_ns", None)
    else:
        measurement["generation_to_passing_patch_ns"] = generation_ns
    generation = measurement["generation_request"]
    generation["rendered_prompt_sha256"] = rendered
    generation["user_text_sha256"] = synthetic_digest(f"user:{rendered}")
    bind(generation)
    # The version-2 members, in their declared position immediately before `content_sha256`. The
    # summary's applied-edit list is the edit set's path list, which ladder row 17 cross-checks.
    blocks = edit_set_blocks()
    measurement["environment_probe"] = copy.deepcopy(measurement["environment_probe"])
    measurement["environment_probe"]["runtime_identity"] = TEMPLATE_ADAPTER_RUNTIME
    bind(measurement["environment_probe"])
    measurement["diagnostic_summary"] = (
        "provider-backed candidate patch "
        + ("passed" if passing else "failed")
        + f" validation; applied edits: {applied_edits_text()}"
    )
    tail = measurement.pop("content_sha256")
    measurement["schema_version"] = 3
    completion = f"{COMPLETION_TEXT}{rendered}\n"
    refusal = "NONE"
    if carries_edit_set:
        measurement["edit_set"] = blocks
        measurement["edit_set_total_bytes"] = sum(item["body_bytes"] for item in blocks)
        measurement["patch_sha256"] = synthetic_digest(f"patch:{rendered}")
        if measurement["patch_size_bytes"] <= 0:
            # Ladder row 13 ties the digest to the byte count, so a fixture patch must have bytes.
            measurement["patch_size_bytes"] = sum(
                len(body.encode("utf-8")) for _, body in EDITSET_EDITS
            )
    else:
        # The `FAIL`/`PATCH` mode, encoded the way the wire actually encodes it: an `Option::None`
        # is **omitted**, not written as `null`. A fixture that wrote the keys explicitly would
        # hide the one shape every real mode-2 row takes, which is exactly the defect class that
        # made the validator reject published evidence the first time it saw it.
        measurement["patch_size_bytes"] = 0
        measurement["diagnostic_summary"] = "the response declares no file block"
        # At version 3 a refusal is a code, and the code and `failure_kind` are one decision: a
        # `PATCH`-class refusal beside `failure_kind: TEST` is exactly the conflation this
        # capability exists to make impossible, so this row carries the shape a real refusal takes.
        measurement["failure_kind"] = "PATCH"
        measurement["build_status"] = "NOT_RUN"
        measurement["test_status"] = "NOT_RUN"
        refusal = "NO_FILE_BLOCK"
    measurement["base_adapter_runtime_identity"] = BASE_ADAPTER_RUNTIME
    # The four version-3 members, in their declared position. `edit_refusal` is unconditional;
    # the completion identity is present because a response was received; the excerpt is present
    # only on the refusal for which no structured substitute exists.
    measurement["edit_refusal"] = refusal
    measurement["completion_bytes"] = len(completion.encode("utf-8"))
    measurement["completion_sha256"] = hashlib.sha256(completion.encode("utf-8")).hexdigest()
    if refusal != "NONE":
        measurement["completion_text"] = completion
    measurement["content_sha256"] = tail
    return bind(measurement)


def attempt_record(
    *,
    index: int,
    kind: str,
    measurement: Mapping[str, Any],
    paired_seed: int,
    rendered: str,
    adapter_request: str,
    elapsed_ns: int,
    preparation_ns: int,
    repair_prompt_source: Mapping[str, Any] | None,
) -> dict[str, Any]:
    passing = measurement["status"] == "PASS"
    record = {
        "schema_version": 1,
        "artifact_kind": "TASK_ATTEMPT_RECORD",
        "attempt_index": index,
        "attempt_kind": kind,
        "status": measurement["status"],
        "skip_reason": "NONE",
        "rendered_prompt_sha256": rendered,
        "repair_prompt_source": copy.deepcopy(repair_prompt_source),
        "adapter_request_sha256": adapter_request,
        # The four trace digests of this attempt's own contained invocation, in the producer's
        # declared order. They are filled by `bind_declared_inputs` once the trace streams are
        # bound, because an attempt must name records this document actually persists — a
        # synthetic digest here would make the whole rule vacuous.
        "snapshot_request_sha256": None,
        "before_snapshot_result_sha256": None,
        "after_snapshot_result_sha256": None,
        "input_snapshot_sha256": None,
        "generation_request": copy.deepcopy(measurement["generation_request"]),
        "seed_attestation": copy.deepcopy(measurement["seed_attestation"]),
        "paired_seed": paired_seed,
        "measurement": copy.deepcopy(dict(measurement)),
        "repair_preparation_ns": preparation_ns,
        "adapter_elapsed_ns": elapsed_ns,
        "adapter_overhead_ns": (
            elapsed_ns - measurement["generation_to_passing_patch_ns"] if passing else None
        ),
        "measurement_sha256": measurement["content_sha256"],
        "content_sha256": "",
    }
    return bind(record)


def repair_prompt_source(
    template_sha256: str, source_measurement_sha256: str, carries_edit_set: bool = True,
) -> dict[str, Any]:
    """A row whose attempt one produced no edit set cannot include the section, so its
    `included_sections` omits `EDITSET` and it drops out of the denominator by construction."""
    sections = ["STATUS", "POLICY", "EDITSET", "SUMMARY", "STDOUT", "STDERR"]
    if not carries_edit_set:
        sections.remove("EDITSET")
    return bind(
        {
            "schema_version": 1,
            "artifact_kind": "REPAIR_PROMPT_SOURCE",
            "template_sha256": template_sha256,
            "source_attempt_index": 1,
            "source_measurement_sha256": source_measurement_sha256,
            "included_sections": sections,
            "dropped_sections": [],
            "assembled_bytes": 4096,
            "content_sha256": "",
        }
    )


def upgrade_to_v2(result: dict[str, Any], evidence: dict[str, Any]) -> None:
    """Rewrite a built version-1 result and its evidence into the version-2 attempt shape.

    Every row gains one repair attempt, so the corpus repairs balance across the two arms and the
    reused acceptance policy's `maximum_repair_loop_regression_count: 0` is met without relaxing
    it. A row whose final measurement passes records `INITIAL FAIL` then `REPAIR PASS`, which is
    the section 1.4 recovery predicate; the failing row records `INITIAL FAIL` then `REPAIR FAIL`,
    which is a measured non-recovery.
    """
    result["schema_version"] = 2
    evidence["schema_version"] = 2
    for task in result["tasks"]:
        # The corpus manifest is the cap: one repair loop, so a second would be a policy violation
        # rather than silently permitted headroom.
        task["regression_limits"]["maximum_repair_loops"] = 1
        # The corpus names the second adapter, which is what makes ladder row 11 require a
        # version-2 measurement from every attempt of this fixture.
        task["argv"] = [task["cmd"], TEMPLATE_ADAPTER_RELATIVE]
        task["measurement_adapter_runtime"] = TEMPLATE_ADAPTER_RUNTIME
        bind(task)
    template_sha256 = synthetic_digest("repair-template")
    expected_inputs: list[dict[str, Any]] = []
    for ordinal, row in enumerate(result["rows"]):
        final = row["measurement"]
        passing = final["status"] == "PASS"
        paired_seed = row["evaluation_input"]["paired_seed"]
        label = f"{row['task_id']}:{row['sample_index']}:{row['variant']}"
        initial_rendered = synthetic_digest(f"rendered:{label}:1")
        repair_rendered = synthetic_digest(f"rendered:{label}:2")
        initial_request = synthetic_digest(f"adapter:{label}:1")
        repair_request = synthetic_digest(f"adapter:{label}:2")
        # Exactly one row reproduces the wire's mode-2 shape: no edit set, no patch digest, and
        # the three `Option` members **omitted** rather than written as `null`. A passing attempt
        # must still carry its patch, so the row chosen is one whose repair also fails.
        carries_edit_set = passing or ordinal != 0
        initial_measurement = attempt_measurement(
            final, passing=False, rendered=initial_rendered, generation_ns=None,
            carries_edit_set=carries_edit_set,
        )
        repair_measurement = attempt_measurement(
            final,
            passing=passing,
            rendered=repair_rendered,
            generation_ns=(
                ATTEMPT_ELAPSED_REPAIR_NS - ATTEMPT_OVERHEAD_NS if passing else None
            ),
            carries_edit_set=carries_edit_set,
        )
        records = [
            attempt_record(
                index=1,
                kind="INITIAL",
                measurement=initial_measurement,
                paired_seed=paired_seed,
                rendered=initial_rendered,
                adapter_request=initial_request,
                elapsed_ns=ATTEMPT_ELAPSED_INITIAL_NS,
                preparation_ns=0,
                repair_prompt_source=None,
            ),
            attempt_record(
                index=2,
                kind="REPAIR",
                measurement=repair_measurement,
                paired_seed=paired_seed,
                rendered=repair_rendered,
                adapter_request=repair_request,
                elapsed_ns=ATTEMPT_ELAPSED_REPAIR_NS,
                preparation_ns=ATTEMPT_REPAIR_PREPARATION_NS,
                repair_prompt_source=repair_prompt_source(
                    template_sha256, initial_measurement["content_sha256"], carries_edit_set,
                ),
            ),
        ]
        generation_ns = (
            ATTEMPT_ELAPSED_INITIAL_NS
            + ATTEMPT_ELAPSED_REPAIR_NS
            + ATTEMPT_REPAIR_PREPARATION_NS
            if passing
            else None
        )
        # `row.measurement` is the final attempt's, byte for byte, so every existing consumer of
        # `row.measurement.*` keeps working with no re-derivation.
        row["measurement"] = copy.deepcopy(repair_measurement)
        row["evaluation_input"]["generation_request_sha256"] = repair_measurement[
            "generation_request"
        ]["content_sha256"]
        row["evaluation_input"]["adapter_request_sha256"] = repair_request
        bind(row["evaluation_input"])
        ordered: dict[str, Any] = {}
        for name, value in list(row.items()):
            if name == "time_to_passing_patch_ns":
                continue
            if name == "evaluation_input":
                ordered["repair_loop_count"] = 1
                if generation_ns is not None:
                    ordered["generation_to_passing_patch_ns"] = generation_ns
                    ordered["time_to_passing_patch_ns"] = (
                        row["prompt_preparation_ns"] + generation_ns
                    )
                ordered["attempts"] = [copy.deepcopy(item) for item in records]
            ordered[name] = value
        row.clear()
        row.update(ordered)
        row["schema_version"] = 2
        bind(row)
        for record in records:
            expected_inputs.append(
                bind(
                    {
                        "schema_version": 2,
                        "artifact_kind": "PROMPT_EXPECTED_INPUT_DIGEST",
                        "task_id": row["task_id"],
                        "sample_index": row["sample_index"],
                        "variant": row["variant"],
                        "attempt_index": record["attempt_index"],
                        "rendered_prompt_sha256": record["rendered_prompt_sha256"],
                        "context_sources_sha256": row["evaluation_input"][
                            "context_sources_sha256"
                        ],
                        "generation_request_sha256": record["generation_request"][
                            "content_sha256"
                        ],
                        "adapter_request_sha256": record["adapter_request_sha256"],
                        "provider_request_sha256": record["generation_request"][
                            "provider_request_sha256"
                        ],
                        "content_sha256": "",
                    }
                )
            )
    evidence["expected_inputs"] = expected_inputs

    # The repair columns, computed here rather than borrowed from the validator, so the aggregate
    # comparison in `validate_evaluation_pair` stays an independent recomputation.
    def recovered(row: Mapping[str, Any]) -> bool:
        attempts = row["attempts"]
        return (
            len(attempts) == 2
            and attempts[0]["attempt_kind"] == "INITIAL"
            and attempts[0]["status"] == "FAIL"
            and attempts[1]["attempt_kind"] == "REPAIR"
            and attempts[1]["status"] == "PASS"
        )

    def editset_attempts(rows: Sequence[Mapping[str, Any]]) -> int:
        total = 0
        for row in rows:
            for attempt in row["attempts"]:
                if attempt["attempt_kind"] != "REPAIR" or attempt["status"] == "SKIPPED":
                    continue
                source = attempt.get("repair_prompt_source") or {}
                if "EDITSET" in (source.get("included_sections") or []):
                    total += 1
        return total

    def edit_refusals(rows: Sequence[Mapping[str, Any]]) -> int:
        total = 0
        for row in rows:
            for attempt in row["attempts"]:
                measurement = attempt.get("measurement")
                if attempt["status"] == "SKIPPED" or not measurement:
                    continue
                if measurement.get("edit_refusal") not in (None, "NONE"):
                    total += 1
        return total

    corpus_attempts = 0
    corpus_recoveries = 0
    corpus_paired = 0
    corpus_editset = 0
    corpus_refusals = 0
    for aggregate in result["task_aggregates"]:
        selected = [row for row in result["rows"] if row["task_id"] == aggregate["task_id"]]
        arms = {
            variant: [row for row in selected if row["variant"] == variant]
            for variant in ("PARENT", "CANDIDATE")
        }
        counts = {
            variant: (
                sum(row["repair_loop_count"] >= 1 for row in rows),
                sum(recovered(row) for row in rows),
                bool(rows) and all(recovered(row) for row in rows),
            )
            for variant, rows in arms.items()
        }
        editset_counts = {variant: editset_attempts(rows) for variant, rows in arms.items()}
        aggregate["parent_repair_attempt_count"] = counts["PARENT"][0]
        aggregate["candidate_repair_attempt_count"] = counts["CANDIDATE"][0]
        aggregate["parent_repair_recovery_count"] = counts["PARENT"][1]
        aggregate["candidate_repair_recovery_count"] = counts["CANDIDATE"][1]
        aggregate["repair_recovery_paired"] = counts["PARENT"][2] or counts["CANDIDATE"][2]
        aggregate["parent_repair_editset_attempt_count"] = editset_counts["PARENT"]
        aggregate["candidate_repair_editset_attempt_count"] = editset_counts["CANDIDATE"]
        corpus_editset += editset_counts["PARENT"] + editset_counts["CANDIDATE"]
        refusal_counts = {variant: edit_refusals(rows) for variant, rows in arms.items()}
        aggregate["parent_edit_refusal_count"] = refusal_counts["PARENT"]
        aggregate["candidate_edit_refusal_count"] = refusal_counts["CANDIDATE"]
        corpus_refusals += refusal_counts["PARENT"] + refusal_counts["CANDIDATE"]
        aggregate["parent_repair_loop_count"] = sum(
            row["repair_loop_count"] for row in arms["PARENT"]
        )
        aggregate["candidate_repair_loop_count"] = sum(
            row["repair_loop_count"] for row in arms["CANDIDATE"]
        )
        corpus_attempts += counts["PARENT"][0] + counts["CANDIDATE"][0]
        corpus_recoveries += counts["PARENT"][1] + counts["CANDIDATE"][1]
        corpus_paired += int(counts["PARENT"][2]) + int(counts["CANDIDATE"][2])
    corpus = result["corpus_aggregate"]
    corpus["parent_repair_loop_count"] = sum(
        item["parent_repair_loop_count"] for item in result["task_aggregates"]
    )
    corpus["candidate_repair_loop_count"] = sum(
        item["candidate_repair_loop_count"] for item in result["task_aggregates"]
    )
    corpus["repair_loop_regression_count"] = max(
        0, corpus["candidate_repair_loop_count"] - corpus["parent_repair_loop_count"]
    )
    corpus["repair_attempt_count"] = corpus_attempts
    corpus["repair_recovery_count"] = corpus_recoveries
    corpus["repair_recovery_paired_count"] = corpus_paired
    corpus["repair_editset_attempt_count"] = corpus_editset
    corpus["edit_refusal_count"] = corpus_refusals


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repository: Path, *arguments: str) -> str:
    environment = os.environ.copy()
    for name in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_GRAFT_FILE"):
        environment.pop(name, None)
    environment.update(
        {
            "GIT_AUTHOR_NAME": "C6 Gate Fixture",
            "GIT_AUTHOR_EMAIL": "c6@example.invalid",
            "GIT_COMMITTER_NAME": "C6 Gate Fixture",
            "GIT_COMMITTER_EMAIL": "c6@example.invalid",
        }
    )
    completed = subprocess.run(
        [str(GIT), *arguments],
        cwd=repository,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        env=environment,
    )
    return completed.stdout.strip()


def repository(path: Path, name: str, commits: int = 1) -> list[str]:
    """Create a clean repository with `commits` linear commits and return their SHAs."""
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "C6 Gate Fixture")
    git(path, "config", "user.email", "c6@example.invalid")
    heads: list[str] = []
    for index in range(commits):
        (path / "source.txt").write_text(f"{name}-{index}\n")
        git(path, "add", "source.txt")
        git(path, "commit", "-qm", f"{name} {index}")
        heads.append(git(path, "rev-parse", "HEAD"))
    return heads


class GateBundle:
    """One materialized gate fixture: CI checkout, source bundle, and evidence directory."""

    def __init__(
        self,
        root: Path,
        *,
        evaluated_is_ancestor: bool = True,
        schema_version: int = 1,
    ) -> None:
        self.schema_version = schema_version
        self.root = root
        self.checkout = root / "ci-checkout"
        self.bundle_root = root / "source-bundle"
        self.gate_directory = self.checkout / "eval" / "prompt" / "gate"
        self.python_executable = Path(sys.executable).resolve(strict=True)
        self.git_executable = GIT.resolve(strict=True)
        self.evaluated_is_ancestor = evaluated_is_ancestor
        self._build()

    # -- construction --------------------------------------------------------------

    def _build(self) -> None:
        evaluated = repository(self.checkout, "align-llm")[0]
        if self.evaluated_is_ancestor:
            self.evaluated_commit = evaluated
        else:
            self.evaluated_commit = repository(self.root / "unrelated", "unrelated")[0]

        # The generation child is built, never committed, so it is neither a CI-checkout file nor
        # a source-bundle member: only the explicit per-run pair names it.
        self.generation_child = self.root / GENERATION_CHILD_RELATIVE
        self.generation_child.parent.mkdir(parents=True)
        self.generation_child.write_text("#!/bin/sh\nexit 0\n")
        self.generation_child.chmod(0o755)
        self.generation_child_sha256 = sha256_bytes(self.generation_child)

        self.bundle_root.mkdir()
        self.align_revision = repository(self.bundle_root / "align", "align")[0]
        self.corpus_revision = repository(self.bundle_root / "corpus", "corpus")[0]

        verifier = self.bundle_root / VERIFIER_RELATIVE
        shutil.copyfile(SOURCE_VERIFIER, verifier)
        verifier.chmod(0o644)
        self.verifier_sha256 = sha256_bytes(verifier)
        self.interpreter_sha256 = sha256_bytes(self.python_executable)
        self.git_sha256 = sha256_bytes(self.git_executable)
        self.runtime = f"CPYTHON:{self.interpreter_sha256}:{self.verifier_sha256}"

        self.policy = bind(
            {
                "schema_version": 1,
                "artifact_kind": "PROMPT_SOURCE_VERIFIER_POLICY",
                "policy_id": "gate-source-policy-v1",
                "helper_path": VERIFIER_RELATIVE,
                "helper_sha256": self.verifier_sha256,
                "helper_runtime": self.runtime,
                "interpreter_sha256": self.interpreter_sha256,
                "git_executable_sha256": self.git_sha256,
                "content_sha256": "",
            }
        )
        (self.bundle_root / POLICY_RELATIVE).write_bytes(canonical_bytes(self.policy))

        self._build_artifacts()
        self.gate_directory.mkdir(parents=True)
        self.write()

    def finalize(self) -> "GateBundle":
        """Publish the gate evidence in the CI checkout and mirror it into the bundle.

        A rejection family mutates the written artifacts first, so the fixture always
        presents a clean CI checkout and only the intended field differs.
        """
        git(self.checkout, "add", "-A")
        git(self.checkout, "commit", "-qm", "gate evidence")
        self.tested_head = git(self.checkout, "rev-parse", "HEAD")
        mirror = self.bundle_root / "align-llm"
        if mirror.exists():
            shutil.rmtree(mirror)
        shutil.copytree(self.checkout, mirror, symlinks=True)
        return self

    def _build_artifacts(self) -> None:
        documents = [json.loads(line) for line in TEMPLATES.read_text("utf-8").splitlines()]
        result, _ineligible, evidence, baseline = (copy.deepcopy(item) for item in documents)

        # The environment policy travels with the gate evidence and is bound by the manifest.
        self.environment_policy = bind(
            {
                "schema_version": 1,
                "artifact_kind": "ENVIRONMENT_POLICY",
                "policy_id": "gate-environment-v1",
                "allowed_variables": [
                    {
                        "name": name,
                        "non_secret_value": value,
                        "source": "EXPLICIT_POLICY",
                        "precedence": precedence,
                    }
                    for precedence, (name, value) in enumerate(
                        (("LANG", "C"), ("LC_ALL", "C"), ("PATH", "/usr/bin:/bin"))
                    )
                ],
                "executable_paths": ["/usr/bin/python3"],
                "locale": "C",
                "content_sha256": "",
            }
        )

        # Bind the fixture to the real fixture source identities.
        result["scope"]["align_revision"] = self.align_revision
        result["scope"]["corpus_revision"]["source_sha256"] = self.corpus_revision
        core = result["environment"]["core"]
        core["align_llm_commit"] = self.evaluated_commit
        core["align_revision"] = self.align_revision
        # The producer-owned environment identity names the checked-in gate inputs.
        core["source_verifier_runtime"] = self.runtime
        core["source_verifier_policy_sha256"] = self.policy["content_sha256"]
        core["environment_policy_sha256"] = self.environment_policy["content_sha256"]
        bind_variant(result["parent_variant"])
        bind_variant(result["candidate_variant"])
        # The declared policies are bound before the scope, because the scope names their digests.
        bind(result["provider_control"])
        result["generation_policy"]["provider_control_sha256"] = result["provider_control"][
            "content_sha256"
        ]
        bind(result["generation_policy"])
        bind(result["acceptance_policy"])
        result["scope"]["acceptance_policy_sha256"] = result["acceptance_policy"]["content_sha256"]
        result["scope"]["generation_policy_sha256"] = result["generation_policy"]["content_sha256"]
        bind_scope(result["scope"], result["parent_variant"])
        bind(result["environment"])
        result["corpus"]["corpus_revision"] = copy.deepcopy(result["scope"]["corpus_revision"])
        result["experiment_artifact"]["scope"] = copy.deepcopy(result["scope"])
        result["experiment_artifact"]["candidate_variant"] = copy.deepcopy(
            result["candidate_variant"]
        )
        for row in result["rows"]:
            selected = (
                result["parent_variant"] if row["variant"] == "PARENT" else result["candidate_variant"]
            )
            row["variant_sha256"] = selected["content_sha256"]
            row["evaluation_input"]["parent_variant_sha256"] = result["parent_variant"][
                "content_sha256"
            ]
            row["evaluation_input"]["candidate_variant_sha256"] = result["candidate_variant"][
                "content_sha256"
            ]

        # Baseline activation carries the evaluated parent variant and the evaluation scope.
        baseline["decision_id"] = "baseline-v1"
        baseline["activation"]["activation_id"] = "baseline-v1/activation"
        baseline["activation"]["scope"] = copy.deepcopy(result["scope"])
        baseline["activation"]["effective_variant"] = copy.deepcopy(result["parent_variant"])
        bind_activation(baseline)

        result["parent_activation"] = {
            "artifact_kind": "PROMPT_ACTIVATION_RESULT",
            "path": BASELINE_NAME,
            "artifact_id": baseline["decision_id"],
            "content_sha256": baseline["content_sha256"],
        }
        result["parent_activation_artifact"] = copy.deepcopy(baseline)
        result["experiment_artifact"]["parent_activation"] = copy.deepcopy(
            result["parent_activation"]
        )
        bind(result["experiment_artifact"])
        result["experiment"]["content_sha256"] = result["experiment_artifact"]["content_sha256"]
        # C4-REPAIR-MEASURED: the version-2 attempt stream is layered on the fully bound
        # version-1 documents, so the two fixtures differ in the attempt machinery alone.
        if self.schema_version >= 2:
            upgrade_to_v2(result, evidence)
        bind_declared_inputs(result)
        bind(result)

        evidence["evaluation_result_sha256"] = result["content_sha256"]
        trust = evidence["trust"]
        trust["expected_align_llm_commit"] = self.evaluated_commit
        trust["align_llm_observed_head"] = self.evaluated_commit
        trust["expected_align_revision"] = self.align_revision
        trust["align_observed_revision"] = self.align_revision
        trust["expected_corpus_source_sha256"] = self.corpus_revision
        trust["corpus_observed_source_sha256"] = self.corpus_revision
        bind(trust)
        bind(evidence)

        accepted = copy.deepcopy(baseline)
        accepted["decision_id"] = "accept-v1"
        accepted["status"] = "ACCEPTED"
        accepted["activation"]["activation_id"] = "accept-v1/activation"
        accepted["activation"]["operation"] = "ACCEPT"
        accepted["activation"]["effective_variant"] = copy.deepcopy(result["candidate_variant"])
        # Section 4.4 lineage: the nested activation ID and digest, exactly as
        # `src/prompt_state.align` links a real accepted activation.
        accepted["activation"]["parent_activation_id"] = baseline["activation"]["activation_id"]
        accepted["activation"]["parent_activation_sha256"] = baseline["activation"]["content_sha256"]
        accepted["activation"]["accepted_evaluation_id"] = result["evaluation_id"]
        accepted["activation"]["accepted_evaluation_sha256"] = result["content_sha256"]
        bind_activation(accepted)

        rollback = copy.deepcopy(baseline)
        rollback["decision_id"] = "rollback-v1"
        rollback["status"] = "ROLLED_BACK"
        rollback["activation"]["activation_id"] = "rollback-v1/activation"
        rollback["activation"]["operation"] = "ROLLBACK"
        rollback["activation"]["effective_variant"] = copy.deepcopy(result["parent_variant"])
        rollback["activation"]["parent_activation_id"] = accepted["activation"]["activation_id"]
        rollback["activation"]["parent_activation_sha256"] = accepted["activation"]["content_sha256"]
        rollback["activation"]["rollback_target_activation_id"] = baseline["activation"]["activation_id"]
        rollback["activation"]["rollback_target_activation_sha256"] = (
            baseline["activation"]["content_sha256"]
        )
        rollback["activation"]["decision_reason"] = "gate evidence rollback"
        bind_activation(rollback)

        self.baseline = baseline
        self.result = result
        self.evidence = evidence
        self.accepted = accepted
        self.rollback = rollback

    # -- serialization -------------------------------------------------------------

    def locator(self) -> dict[str, Any]:
        return bind(
            {
                "schema_version": 1,
                "artifact_kind": "PROMPT_GATE_SOURCE_LOCATOR",
                "source_bundle_id": "gate-source-bundle-v1",
                "align_llm_source_relative_path": "align-llm",
                "align_source_relative_path": "align",
                "corpus_source_relative_path": "corpus",
                "source_verifier_policy_relative_path": POLICY_RELATIVE,
                "source_verifier_policy_sha256": self.policy["content_sha256"],
                "source_verifier_relative_path": VERIFIER_RELATIVE,
                "source_verifier_sha256": self.verifier_sha256,
                "source_verifier_runtime": self.runtime,
                "source_verifier_interpreter_sha256": self.interpreter_sha256,
                "git_executable_sha256": self.git_sha256,
                # The evidence-recorded derived-child identity: the accept path records the real
                # per-run digest, so a rejection family only has to mutate this one field.
                "generation_child_sha256": self.generation_child_sha256,
                "content_sha256": "",
            }
        )

    def manifest(self) -> dict[str, Any]:
        def reference(kind: str, name: str, artifact: Mapping[str, Any], key: str):
            return {
                "artifact_kind": kind,
                "path": name,
                "artifact_id": artifact[key],
                "content_sha256": artifact["content_sha256"],
            }

        return bind(
            {
                "schema_version": 1,
                "artifact_kind": "PROMPT_GATE_MANIFEST",
                "gate_id": "c6-gate-v1",
                "source_locator": self.locator(),
                "baseline_activation": reference(
                    "PROMPT_ACTIVATION_RESULT", BASELINE_NAME, self.baseline, "decision_id"
                ),
                "improved_evaluation": reference(
                    "PROMPT_EVALUATION_RESULT", EVALUATION_NAME, self.result, "evaluation_id"
                ),
                "improved_evaluation_evidence": reference(
                    "PROMPT_EVALUATION_EVIDENCE", EVIDENCE_NAME, self.evidence, "evaluation_id"
                ),
                "accepted_activation": reference(
                    "PROMPT_ACTIVATION_RESULT", ACCEPTED_NAME, self.accepted, "decision_id"
                ),
                "rollback_activation": reference(
                    "PROMPT_ACTIVATION_RESULT", ROLLBACK_NAME, self.rollback, "decision_id"
                ),
                "environment_policy": reference(
                    "ENVIRONMENT_POLICY",
                    ENVIRONMENT_POLICY_NAME,
                    self.environment_policy,
                    "policy_id",
                ),
                "content_sha256": "",
            }
        )

    def write(self) -> None:
        for name, value in (
            (BASELINE_NAME, self.baseline),
            (EVALUATION_NAME, self.result),
            (EVIDENCE_NAME, self.evidence),
            (ACCEPTED_NAME, self.accepted),
            (ROLLBACK_NAME, self.rollback),
            (ENVIRONMENT_POLICY_NAME, self.environment_policy),
        ):
            (self.gate_directory / name).write_bytes(canonical_bytes(value))
        (self.gate_directory / MANIFEST_NAME).write_bytes(canonical_bytes(self.manifest()))

    def write_manifest(self, value: Mapping[str, Any]) -> None:
        (self.gate_directory / MANIFEST_NAME).write_bytes(canonical_bytes(value))

    @property
    def manifest_path(self) -> Path:
        return self.gate_directory / MANIFEST_NAME

    def arguments(self) -> list[str]:
        return [
            "--source-bundle-root",
            str(self.bundle_root),
            "--python-executable-path",
            str(self.python_executable),
            "--git-executable-path",
            str(self.git_executable),
            "--generation-child-path",
            str(self.generation_child),
            "--generation-child-sha256",
            self.generation_child_sha256,
            "--gate-manifest",
            str(self.manifest_path),
        ]
