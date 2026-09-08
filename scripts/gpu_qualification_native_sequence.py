#!/usr/bin/env python3
"""Run native CPU/GPU case pairs under the existing single process deadline."""
from __future__ import annotations

import dataclasses
from pathlib import Path
import shutil
from collections.abc import Callable, Sequence

from gpu_backend_recipe import RecipeError, canonical, lowercase_hex
from gpu_qualification_backend import _write
from gpu_qualification_cases import CaseCommand, CaseSequence
from gpu_qualification_native import NativeCase, NativeSuccess, failure, success
from gpu_qualification_records import f32_tolerance, require_identifier
from gpu_qualifier_process import OwnedCommandResult


@dataclasses.dataclass(frozen=True)
class Plan:
    identity: tuple[str, str, int]
    case: NativeCase
    executable: Path
    executable_sha256: str
    comparison: dict[str, str]
    bundle_id: str | None = None
    device: str | None = None

    @property
    def gpu(self) -> bool:
        return bool(self.case.document["options_path"])


@dataclasses.dataclass(frozen=True)
class Outcome:
    process: OwnedCommandResult
    native: NativeSuccess | None
    numeric: dict[str, object] | None
    native_failure: dict[str, object] | None
    error: str

    @property
    def accepted(self) -> bool:
        return self.process.terminal == "PASS" and self.native is not None and not self.error


def _projection(plan: Plan) -> bytes:
    return canonical({key: value for key, value in plan.case.document.items()
                      if key not in {"options_path", "stream_root", "stream_name"}})


def run(plans: Sequence[Plan], *, budget_ns: int, work: Path, home: Path, temporary: Path,
        consume: Callable[[int, Outcome], bool], sequence: CaseSequence | None = None) -> CaseSequence:
    sequence = CaseSequence(len(plans), budget_ns) if sequence is None else sequence
    if sequence.count != len(plans) or sequence.deadline_ns - sequence.started_ns != budget_ns \
            or sequence._used:
        raise RecipeError("native execution requires matching fresh sequence state")
    if len(plans) % 2 or not work.is_absolute() or work.resolve(strict=True) != work:
        raise RecipeError("native case sequence root or pair count is invalid")
    roots = [Path(plan.case.document["stream_root"]) for plan in plans]
    if len(set(roots)) != len(roots) or any(root.parent != work for root in roots):
        raise RecipeError("native case scratch roots are not distinct direct invocation children")
    identities = set()
    for ordinal, plan in enumerate(plans):
        if not isinstance(plan.identity, tuple) or len(plan.identity) != 3 \
                or type(plan.identity[2]) is not int or plan.identity[2] not in (0, 1):
            raise RecipeError("native case repeat identity is invalid")
        require_identifier(plan.identity[1], "native calibration case", case=True)
        if not ordinal % 2:
            if plan.identity in identities:
                raise RecipeError("native case pair identity is duplicated")
            identities.add(plan.identity)
        for key in ("absolute_tolerance_f32_bits", "relative_tolerance_f32_bits", "near_tie_tolerance_f32_bits"):
            f32_tolerance(plan.comparison.get(key), "native " + key)
        lowercase_hex(plan.executable_sha256, 64, "native executable digest")
        if not plan.executable.is_absolute() or plan.gpu != bool(ordinal % 2):
            raise RecipeError("native executable or CPU/GPU order is invalid")
        if plan.identity[0] != plan.case.document["model_id"]:
            raise RecipeError("native plan model identity differs")
        if ordinal % 2:
            previous = plans[ordinal - 1]
            if previous.identity != plan.identity or previous.case.traversal != plan.case.traversal \
                    or previous.case.residency != plan.case.residency \
                    or previous.case.model_work != plan.case.model_work \
                    or previous.comparison != plan.comparison or _projection(previous) != _projection(plan):
                raise RecipeError("native pair does not share its complete frozen identity")
    acquired: set[Path] = set()
    pending: tuple[Plan, NativeSuccess] | None = None

    def cleanup(root: Path) -> None:
        if root in acquired:
            try:
                shutil.rmtree(root)
            except OSError as error:
                raise RecipeError("native case scratch cleanup failed") from error
            acquired.remove(root)

    def construct(ordinal: int) -> CaseCommand:
        plan, root = plans[ordinal], roots[ordinal]
        root.mkdir(mode=0o700)
        acquired.add(root)
        path = _write(root, "input.json", plan.case.input_bytes())
        name = "candidate" if plan.gpu else "cpu-reference"
        executable_token = f"<{name}>:sha256:{plan.executable_sha256}"
        input_token = "<case-input>:owned"
        return CaseCommand((str(plan.executable), str(path)), (executable_token, input_token),
                           {executable_token: plan.executable, input_token: path})

    def accept(ordinal: int, process: OwnedCommandResult) -> bool:
        nonlocal pending
        plan = plans[ordinal]
        observed = None
        numeric = None
        failed = None
        error = ""
        try:
            if process.stdout.truncated or process.stderr.truncated:
                raise RecipeError("native case logs are truncated")
            if process.terminal != "PASS":
                if process.stdout.retained:
                    failed = failure(process.stdout.retained, plan.case)
                raise RecipeError("native case child did not pass: " + process.terminal)
            observed = success(process.stdout.retained, plan.case,
                               expected_bundle_id=plan.bundle_id, expected_device=plan.device)
            if plan.gpu:
                if pending is None:
                    raise RecipeError("native GPU case has no validated CPU predecessor")
                reference_plan, reference = pending
                numeric, nonfinite, routing_mismatch = plan.case.traversal.compare(
                    reference_plan.case.stream_path, plan.case.stream_path,
                    reference_sha256=reference.stream_sha256,
                    reference_token_ids=reference.production["token_ids"],
                    candidate_token_ids=observed.production["token_ids"], comparison=plan.comparison)
                if nonfinite or routing_mismatch or numeric["mismatch_count"]:
                    error = "native paired numeric comparison failed"
                cleanup(Path(reference_plan.case.document["stream_root"]))
                pending = None
                cleanup(roots[ordinal])
            else:
                pending = (plan, observed)
        except (RecipeError, OSError) as fault:
            error = str(fault)
        outcome = Outcome(process, observed, numeric, failed, error)
        consumer_accepted = consume(ordinal, outcome)
        return outcome.accepted and consumer_accepted is True

    try:
        sequence.run([lambda index=index: construct(index) for index in range(len(plans))],
                     cwd=work, home=home, temporary=temporary, consume=accept)
        return sequence
    finally:
        failed_cleanup = False
        for root in tuple(acquired):
            try:
                cleanup(root)
            except RecipeError:
                failed_cleanup = True
        if failed_cleanup:
            raise RecipeError("native case scratch cleanup failed")
