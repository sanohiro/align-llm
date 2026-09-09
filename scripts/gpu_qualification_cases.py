#!/usr/bin/env python3
"""Serial case execution with one generation deadline and explicit validation completion."""

from __future__ import annotations

import dataclasses
import pathlib
import time
from collections.abc import Callable, Mapping, Sequence

from gpu_backend_recipe import RecipeError
from gpu_qualifier_process import OwnedCommandResult, run_owned_command


@dataclasses.dataclass(frozen=True)
class CaseCommand:
    physical_argv: tuple[str, ...]
    logical_argv: tuple[str, ...]
    mappings: Mapping[str, pathlib.Path]


class CaseSequence:
    def __init__(self, count: int, budget_ns: int) -> None:
        if type(count) is not int or not 16 <= count <= 256 \
                or type(budget_ns) is not int or not 1 <= budget_ns <= 900_000_000_000:
            raise RecipeError("case sequence count or generation budget is invalid")
        self.count = count
        self.started_ns = time.monotonic_ns()
        self.deadline_ns = self.started_ns + budget_ns
        self.accepted = 0
        self.failure_ordinal: int | None = None
        self.failure_detail = ""
        self.failed_result: OwnedCommandResult | None = None
        self.elapsed_ns = 0
        self._used = False

    @property
    def complete(self) -> bool:
        return self.accepted == self.count and self.failure_ordinal is None

    def run(
        self, commands: Sequence[Callable[[], CaseCommand]], *, cwd: pathlib.Path,
        home: pathlib.Path, temporary: pathlib.Path,
        consume: Callable[[int, OwnedCommandResult], bool],
    ) -> None:
        """The consumer retains logs and validates outputs/numeric data before returning true."""
        if self._used or len(commands) != self.count:
            raise RecipeError("case sequence requires a fresh state and complete command schedule")
        self._used = True
        for ordinal, construct in enumerate(commands):
            result = None
            try:
                if time.monotonic_ns() >= self.deadline_ns:
                    raise RecipeError("generation deadline expired before case construction")
                command = construct()
                result = run_owned_command(
                    kind="case", physical_argv=command.physical_argv,
                    logical_argv=command.logical_argv, mappings=command.mappings,
                    cwd=cwd, home=home, temporary=temporary,
                    timeout_seconds=900, deadline_ns=self.deadline_ns,
                )
                # Even a failed child has owned logs/termination evidence for the consumer.
                accepted = consume(ordinal, result)
                if result.terminal != "PASS":
                    raise RecipeError("case child did not pass")
                if time.monotonic_ns() >= self.deadline_ns:
                    raise RecipeError("generation deadline expired during case validation")
                if accepted is not True:
                    raise RecipeError("case output or numeric validation did not pass")
                self.accepted += 1
            except (RecipeError, OSError) as error:
                self.failure_ordinal = ordinal
                self.failed_result = result
                self.failure_detail = str(error)
                return
            finally:
                self.elapsed_ns = max(self.elapsed_ns, time.monotonic_ns() - self.started_ns)
