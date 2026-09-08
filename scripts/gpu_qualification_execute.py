#!/usr/bin/env python3
"""Join the prepared native sequence, host observations and retained case evidence."""
from __future__ import annotations

import dataclasses
import time

from gpu_backend_recipe import RecipeError
from gpu_qualification_case_records import CaseRecords
from gpu_qualification_cases import CaseSequence
from gpu_qualification_cli import Invocation, native_plans
from gpu_qualification_host_observation import observe_device, probe_owner, same_device
from gpu_qualification_native_sequence import Outcome, run
from gpu_qualification_publish import RetainedFile
from gpu_qualification_run import PreparationState, failure_evidence


@dataclasses.dataclass(frozen=True)
class ExecutionEvidence:
    evidence: dict[str, object]
    retained: dict[str, RetainedFile]


def execute(invocation: Invocation, preparation: PreparationState, *, align_revision: str,
            host: dict[str, object]) -> ExecutionEvidence:
    """Keep the observed prefix even when native cleanup or device enrichment fails."""
    if not preparation.complete:
        raise RecipeError("generation evidence requires completed native preparation")
    profile = invocation.admitted.records["profile"]
    bundle = invocation.admitted.records["bundle"]
    evidence = failure_evidence(invocation.admitted, preparation, align_revision=align_revision,
        host=host, category="CONFIG", stage="plan", detail="native case planning did not complete",
        owned_paths_removed=False)
    retained = dict(preparation.retained)
    records = None
    sequence = None
    first_device = None
    device_failure = None
    execution_failure = None
    try:
        plans = native_plans(invocation, preparation)
        records = CaseRecords(profile["cases"], plans)
        budget = profile["deadlines_ns"]["generation"]
        sequence = CaseSequence(len(plans), budget)
        probe = probe_owner(work=invocation.work, home=invocation.home,
                            temporary=invocation.temporary, deadline_ns=sequence.deadline_ns)

        def consume(ordinal: int, outcome: Outcome) -> bool:
            nonlocal first_device, device_failure
            accepted = records.consume(ordinal, outcome)
            # Retain valid native device facts even if the numeric comparison failed.
            if plans[ordinal].gpu and outcome.native is not None:
                observed = outcome.native.observation
                try:
                    if first_device is None:
                        evidence["host"] = observe_device(host, observed, bundle=bundle,
                                                        probe=probe, deadline_ns=sequence.deadline_ns)
                        first_device = dict(observed)
                        # The runtime owner opens this exact verified plugin before returning
                        # a device snapshot. Other declared dependencies are not inferred loaded.
                        plugin = "libggml-" + bundle["backend"] + ".so"
                        loaded = [row["sha256"] for row in bundle["artifacts"]
                                  if row["role"] == "backend_plugin" and row["path"] == plugin]
                        if len(loaded) != 1:
                            raise RecipeError("native bundle plugin is ambiguous")
                        evidence["bundle"]["loaded_artifact_sha256s"] = loaded
                    else:
                        same_device(first_device, observed)
                except (RecipeError, OSError):
                    # Preserve the earlier compute failure if there was one.
                    if accepted:
                        records.rows[-1].update(terminal="FAIL", category="DEVICE_UNAVAILABLE", stage="device")
                        device_failure = ordinal
                    return False
            return accepted

        run(plans, budget_ns=budget, work=invocation.work, home=invocation.home,
            temporary=invocation.temporary, consume=consume, sequence=sequence)
    except (RecipeError, OSError):
        execution_failure = "native case construction or cleanup did not complete"
    finally:
        if records is not None and sequence is not None and sequence._used:
            records.finish(sequence)
            evidence["cases"] = records.rows
            retained.update(records.retained)
            evidence["cleanup"]["descendants_before"] += records.descendants_before
            evidence["cleanup"]["descendants_after"] += records.descendants_after
            if execution_failure is not None:
                evidence["cleanup"]["invocation_state_safe"] = False
            if not sequence.complete:
                evidence["failure"] = records.failure
                if device_failure is not None:
                    evidence["failure"]["detail"] = "native device identity or host enrichment failed"
            elif execution_failure is None:
                evidence["failure"] = dict(category="", stage="", case_ordinal=-1, detail="")
                evidence["status"] = "PASS"
            else:
                evidence["failure"] = dict(category="CLEANUP", stage="qualifier_cleanup",
                    case_ordinal=-1, detail=execution_failure)
                evidence["cleanup"]["invocation_state_safe"] = False
        cases = evidence["cases"]
        passed = sum(row["terminal"] == "PASS" for row in cases)
        evidence["aggregate"] = dict(case_count=len(cases), passed_count=passed,
            failed_count=len(cases) - passed,
            managed_host_peak_bytes=max((row["memory"]["managed_host_peak_bytes"] for row in cases), default=0),
            managed_device_peak_bytes=max((row["memory"]["managed_device_peak_bytes"] for row in cases), default=0),
            decision="unmeasured")
        evidence["elapsed_ns"] = max(1, time.monotonic_ns() - preparation.started_ns)
    return ExecutionEvidence(evidence, retained)
