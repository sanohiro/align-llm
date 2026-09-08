#!/usr/bin/env python3
"""Public qualifier lifecycle: admit, prepare, execute, clean, publish and replay."""
from __future__ import annotations

import pathlib
import sys
import time
from collections.abc import Sequence

from gpu_backend_recipe import RecipeError
from gpu_qualification_cli import Arguments, open_invocation, parse_arguments, prepare_invocation
from gpu_qualification_execute import execute
from gpu_qualification_host_observation import observe_host, probe_owner
from gpu_qualification_publish import prepare, publish
from gpu_qualification_run import PreparationState, failure_evidence, _artifact
from gpu_qualification_source import _verify_tree


def helper_identity(invocation, launcher: pathlib.Path) -> None:
    rows = {row["path"]: row for row in invocation.admitted.align_source.manifest["files"]}
    paths = {launcher}
    paths.update(pathlib.Path(module.__file__).resolve(strict=True)
                 for name, module in tuple(sys.modules.items())
                 if name.startswith("gpu_") and getattr(module, "__file__", None))
    for path in paths:
        row = rows.get("scripts/" + path.name)
        if row is None or row["mode"] not in {"100644", "100755"}:
            raise RecipeError("qualifier helper is absent from the admitted source")
        data, digest = _artifact(path.absolute())
        if len(data) != row["bytes"] or digest != row["sha256"]:
            raise RecipeError("qualifier helper differs from the admitted source")


def qualify(arguments: Arguments, *, launcher: pathlib.Path) -> str:
    started = time.monotonic_ns()
    invocation = open_invocation(arguments)
    cleanup_attempted = False
    try:
        helper_identity(invocation, launcher)
        profile = invocation.admitted.records["profile"]
        bundle = invocation.admitted.records["bundle"]
        revision = (invocation.sources.align_llm / ".align-revision").read_text().strip()
        if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
            raise RecipeError("admitted Align revision is invalid")
        preparation = PreparationState(launcher, name="gpu-runtime-qualify",
            version=profile["source"]["commit"], preparation_timeout_ns=profile["deadlines_ns"]["preparation"])
        probe = probe_owner(work=invocation.work, home=invocation.home,
                            temporary=invocation.temporary, deadline_ns=preparation.deadline_ns)
        host = observe_host(expected_platform=profile["platform"], backend=bundle["backend"],
                            probe=probe, deadline_ns=preparation.deadline_ns)
        prepare_invocation(invocation, preparation, entry_relative="src/runtime_case.align")
        if preparation.complete:
            execution = execute(invocation, preparation, align_revision=revision, host=host)
            evidence, retained = execution.evidence, execution.retained
        else:
            ordinal = preparation.failure_ordinal
            if ordinal is None:
                raise RecipeError("preparation has no terminal checkpoint")
            evidence = failure_evidence(invocation.admitted, preparation, align_revision=revision,
                host=host, category="PREPARATION" if ordinal < 2 else "BUILD",
                stage=("compiler", "runtime", "shim_build", "candidate_build", "cpu_reference_build")[ordinal],
                detail="native preparation did not complete", owned_paths_removed=False)
            retained = preparation.retained

        def fail(category: str, stage: str, detail: str) -> None:
            if evidence["status"] == "PASS":
                evidence["status"] = "FAIL"
                evidence["failure"] = dict(category=category, stage=stage, case_ordinal=-1, detail=detail)

        try:
            _verify_tree(invocation.admitted.align_source, invocation.sources.align_llm)
            _verify_tree(invocation.admitted.ggml_source, invocation.sources.ggml)
            helper_identity(invocation, launcher)
        except (RecipeError, OSError):
            evidence["cleanup"]["source_unchanged"] = False
            fail("SOURCE_IDENTITY", "source", "source identity changed during qualification")
        try:
            invocation.admitted.recheck()
        except (RecipeError, OSError):
            evidence["cleanup"]["inputs_unchanged"] = False
            fail("CONFIG", "source", "retained inputs changed during qualification")
        prepared = prepare(invocation.admitted, retained)
        evidence["files"] = prepared.rows
        try:
            cleanup_attempted = True
            invocation.cleanup()
            evidence["cleanup"]["owned_paths_removed"] = True
        except (RecipeError, OSError):
            evidence["cleanup"]["invocation_state_safe"] = False
            fail("CLEANUP", "qualifier_cleanup", "invocation cleanup did not complete")
        evidence["elapsed_ns"] = max(1, time.monotonic_ns() - started)
        # Publication independently rechecks retained inputs and replays the staged directory.
        # Input drift may therefore prevent even FAIL publication; it never yields false evidence.
        publish(invocation.admitted, evidence, prepared, arguments.output)
        return str(evidence["status"])
    finally:
        if not cleanup_attempted:
            invocation.cleanup()


def main(arguments: Sequence[str], *, launcher: pathlib.Path) -> int:
    try:
        status = qualify(parse_arguments(arguments), launcher=launcher)
    except (RecipeError, OSError, RuntimeError):
        print("gpu-runtime-qualify: FAIL (qualification or evidence publication did not complete)", file=sys.stderr)
        return 1
    print("gpu-runtime-qualify: " + status)
    return 0 if status == "PASS" else 1
