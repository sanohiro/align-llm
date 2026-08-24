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
from typing import Any, Mapping


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

    def __init__(self, root: Path, *, evaluated_is_ancestor: bool = True) -> None:
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

        # Bind the fixture to the real fixture source identities.
        result["scope"]["align_revision"] = self.align_revision
        result["scope"]["corpus_revision"]["source_sha256"] = self.corpus_revision
        result["environment"]["core"]["align_llm_commit"] = self.evaluated_commit
        result["environment"]["core"]["align_revision"] = self.align_revision
        bind_variant(result["parent_variant"])
        bind_variant(result["candidate_variant"])
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
        accepted["activation"]["parent_activation_id"] = baseline["decision_id"]
        accepted["activation"]["parent_activation_sha256"] = baseline["content_sha256"]
        accepted["activation"]["accepted_evaluation_id"] = result["evaluation_id"]
        accepted["activation"]["accepted_evaluation_sha256"] = result["content_sha256"]
        bind_activation(accepted)

        rollback = copy.deepcopy(baseline)
        rollback["decision_id"] = "rollback-v1"
        rollback["status"] = "ROLLED_BACK"
        rollback["activation"]["activation_id"] = "rollback-v1/activation"
        rollback["activation"]["operation"] = "ROLLBACK"
        rollback["activation"]["effective_variant"] = copy.deepcopy(result["parent_variant"])
        rollback["activation"]["parent_activation_id"] = accepted["decision_id"]
        rollback["activation"]["parent_activation_sha256"] = accepted["content_sha256"]
        rollback["activation"]["rollback_target_activation_id"] = baseline["decision_id"]
        rollback["activation"]["rollback_target_activation_sha256"] = baseline["content_sha256"]
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
