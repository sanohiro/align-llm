#!/usr/bin/env python3
"""Assemble truthful case rows from admitted plans and observed native outcomes."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

from gpu_backend_recipe import RecipeError
from gpu_qualification_native_sequence import Outcome, Plan
from gpu_qualification_publish import RetainedFile
from gpu_qualification_records import validate_case
from gpu_qualification_cases import CaseSequence


def empty_numeric() -> dict[str, object]:
    return {
        "compared": False, "expected_scalar_count": 0, "actual_scalar_count": 0,
        "expected_layer_count": 0, "actual_layer_count": 0, "expected_router_boundary_count": 0,
        "actual_router_boundary_count": 0, "expected_final_logit_count": 0,
        "actual_final_logit_count": 0, "max_absolute_f64_bits": "0000000000000000",
        "max_relative_f64_bits": "0000000000000000", "near_tie_count": 0, "mismatch_count": 0,
    }


def assemble(ordinal: int, expected: Mapping[str, object], plan: Plan, outcome: Outcome | None
             ) -> tuple[dict[str, object], dict[str, RetainedFile]]:
    if (expected["model_id"], expected["calibration_case_id"], expected["repeat_index"]) != plan.identity \
            or (expected["execution"] == "gpu_resident") != plan.gpu \
            or expected["maximum_tokens"] != plan.case.document["maximum_tokens"]:
        raise RecipeError("case evidence profile and native plan differ")
    process = None if outcome is None else outcome.process
    native = None if outcome is None else outcome.native
    failed = None if outcome is None else outcome.native_failure
    observation = native.observation if native is not None and plan.gpu else {}
    accepted = outcome is not None and outcome.accepted
    terminal = "FAIL" if process is None or (process.terminal == "PASS" and not accepted) else process.terminal
    category, stage = ("", "") if accepted else ("PROCESS", "case_spawn")
    nonfinite = 0 if failed is None else failed["stream_nonfinite_count"]
    if outcome is not None and process.terminal == "PASS" and not accepted:
        category, stage = "COMPUTE", "readback"
    if nonfinite:
        category, stage = "NONFINITE", "readback"
    if process is not None and (process.rss_peak_bytes is None or process.rss_peak_bytes <= 0
                               or process.descendants_before or process.descendants_after):
        if terminal == "PASS":
            terminal, category, stage = "FAIL", "PROCESS", "qualifier_cleanup"

    work = plan.case.model_work
    residency = plan.case.residency
    placement = {
        "expected_model_operations": work.operations if plan.gpu else 0,
        "gpu_model_operations": observation.get("model_operations", 0), "cpu_model_operations": 0,
        "expected_layers": work.layers if plan.gpu else 0,
        "gpu_layers": observation.get("model_layers", 0), "cpu_layers": 0,
        "expected_experts": work.experts if plan.gpu else 0,
        "gpu_experts": observation.get("model_experts", 0), "cpu_experts": 0,
        "expected_weights_device_bytes": residency.weight_bytes if plan.gpu else 0,
        "minimum_weights_device_bytes": observation.get("resident_weight_payload_bytes", 0),
        "expected_kv_device_bytes": residency.kv_bytes if plan.gpu else 0,
        "minimum_kv_device_bytes": observation.get("resident_kv_payload_bytes", 0),
        "expected_weight_upload_count": residency.weight_count if plan.gpu else 0,
        "weight_upload_count": observation.get("weight_upload_count", 0),
        "weight_upload_bytes": observation.get("weight_upload_bytes", 0),
    }
    read_bytes = observation.get("read_bytes", 0)
    log_paths = {name: "" if process is None else f"logs/case-{ordinal:03d}.{name}"
                 for name in ("stdout", "stderr")}
    row = {
        "ordinal": ordinal,
        **{key: expected[key] for key in ("case_id", "calibration_case_id", "role", "execution",
                                         "repeat_index", "model_id", "option_id")},
        "terminal": terminal, "category": category, "stage": stage,
        "exit_code": None if process is None else process.exit_code,
        "signal": None if process is None else process.signal,
        "command": {"kind": "", "argv": [], "environment": [], "sha256": ""} if process is None else process.command,
        "output_sha256": "" if native is None else native.output_sha256,
        "token_ids": [] if native is None else list(native.production["token_ids"]),
        "nonfinite_count": nonfinite,
        "numeric": empty_numeric() if outcome is None or outcome.numeric is None else dict(outcome.numeric),
        "placement": placement,
        "transfers": {
            "host_to_device_bytes": sum(observation.get(key, 0) for key in
                                        ("weight_upload_bytes", "kv_upload_bytes", "input_upload_bytes")),
            "device_to_host_bytes": read_bytes,
            "unexpected_device_to_host_bytes": max(0, read_bytes - plan.case.traversal.positions
                                                    * plan.case.traversal.vocabulary * 4),
            "wait_count": observation.get("sync_calls", 0),
        },
        "memory": {
            "managed_host_peak_bytes": observation.get("managed_host_peak_bytes", 0),
            "managed_device_peak_bytes": observation.get("managed_device_peak_bytes", 0),
            "uma_alias_peak_bytes": 0,
            "rss_peak_bytes": 0 if process is None or process.rss_peak_bytes is None else process.rss_peak_bytes,
            "driver_peak_bytes": None,
        },
        "timing": {"wall_ns": 0 if process is None else process.elapsed_ns,
                   **{key: None for key in ("load_ns", "ttft_ns", "prefill_ns", "decode_ns",
                                            "device_ns", "transfer_ns", "wait_ns")}},
        "stdout_path": log_paths["stdout"], "stderr_path": log_paths["stderr"],
    }
    frozen = {"expected_token_ids": plan.case.document["expected_token_ids"],
              "expected_output_sha256": hashlib.sha256(plan.case.document["expected_output_utf8"].encode()).hexdigest()}
    validated = validate_case(row, expected=dict(expected), calibration_case=frozen, status="FAIL")
    retained = {}
    if process is not None:
        data = plan.case.input_bytes()
        digest = hashlib.sha256(data).hexdigest()
        label = "candidate" if plan.gpu else "cpu-reference"
        if process.command["argv"] != [f"<{label}>:sha256:{plan.executable_sha256}",
                                        f"<case-input>:sha256:{digest}"]:
            raise RecipeError("case command differs from its executable or owned input")
        retained[f"case-inputs/{ordinal:03d}.json"] = RetainedFile("case_input", data, len(data), digest)
        for name in ("stdout", "stderr"):
            captured = getattr(process, name)
            retained[log_paths[name]] = RetainedFile(name, captured.retained, captured.original_bytes,
                                                    captured.original_sha256)
    return validated, retained


class CaseRecords:
    def __init__(self, expected: Sequence[Mapping[str, object]], plans: Sequence[Plan]) -> None:
        if len(expected) != len(plans) or not 16 <= len(plans) <= 256:
            raise RecipeError("case record schedule is incomplete")
        self.expected = tuple(dict(row) for row in expected)
        self.plans = tuple(plans)
        self.rows: list[dict[str, object]] = []
        self.retained: dict[str, RetainedFile] = {}
        self.descendants_before = 0
        self.descendants_after = 0
        self.finished = False
        self.failure: dict[str, object] = {"category": "", "stage": "", "case_ordinal": -1, "detail": ""}
        for ordinal, (row, plan) in enumerate(zip(self.expected, self.plans)):
            assemble(ordinal, row, plan, None)  # Validate frozen construction before the first child.

    def consume(self, ordinal: int, outcome: Outcome) -> bool:
        if self.finished or ordinal != len(self.rows) or ordinal >= len(self.plans) \
                or (self.rows and self.rows[-1]["terminal"] != "PASS"):
            raise RecipeError("case records require consecutive unfinished consumption")
        row, retained = assemble(ordinal, self.expected[ordinal], self.plans[ordinal], outcome)
        self.rows.append(row)
        self.retained.update(retained)
        self.descendants_before += outcome.process.descendants_before
        self.descendants_after += outcome.process.descendants_after
        return row["terminal"] == "PASS"

    def finish(self, sequence: CaseSequence) -> None:
        if self.finished or sequence.count != len(self.plans) or not sequence._used:
            raise RecipeError("case records require one completed sequence checkpoint")
        if sequence.complete:
            if len(self.rows) != len(self.plans) or any(row["terminal"] != "PASS" for row in self.rows):
                raise RecipeError("complete sequence differs from retained case records")
        else:
            ordinal = sequence.failure_ordinal
            if ordinal is None or sequence.accepted != ordinal or len(self.rows) not in {ordinal, ordinal + 1}:
                raise RecipeError("failed sequence differs from retained case prefix")
            if len(self.rows) == ordinal:
                outcome = None if sequence.failed_result is None else Outcome(
                    sequence.failed_result, None, None, None, "case validation did not complete")
                row, retained = assemble(ordinal, self.expected[ordinal], self.plans[ordinal], outcome)
                self.rows.append(row)
                self.retained.update(retained)
                if outcome is not None:
                    self.descendants_before += outcome.process.descendants_before
                    self.descendants_after += outcome.process.descendants_after
            row = self.rows[ordinal]
            if row["terminal"] == "PASS":
                row.update(terminal="FAIL", category="PROCESS", stage="readback")
            self.failure = {"category": row["category"], "stage": row["stage"], "case_ordinal": ordinal,
                            "detail": ("generation deadline expired during case validation"
                                       if sequence.failure_detail == "generation deadline expired during case validation"
                                       else "case execution or validation did not complete successfully")}
        self.finished = True
