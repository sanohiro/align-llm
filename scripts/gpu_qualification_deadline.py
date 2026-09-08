#!/usr/bin/env python3
"""The shared generation deadline, checked inside bounded validation work."""
from __future__ import annotations

import dataclasses
import time
from collections.abc import Iterable, Iterator
from typing import TypeVar

from gpu_backend_recipe import RecipeError

T = TypeVar("T")
EXPIRED = "generation deadline expired during numeric validation"


@dataclasses.dataclass(frozen=True)
class Deadline:
    monotonic_ns: int

    def __post_init__(self) -> None:
        if type(self.monotonic_ns) is not int or self.monotonic_ns <= 0:
            raise RecipeError("numeric validation deadline is invalid")

    def check(self) -> None:
        if time.monotonic_ns() >= self.monotonic_ns:
            raise RecipeError(EXPIRED)


def checked(values: Iterable[T], deadline: Deadline | None) -> Iterator[T]:
    if deadline is None:
        yield from values
        return
    deadline.check()
    for index, value in enumerate(values):
        if index % 1024 == 0:
            deadline.check()
        yield value
    deadline.check()
