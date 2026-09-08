#!/usr/bin/env python3
"""The shared generation deadline, checked inside bounded validation work."""
from __future__ import annotations

import dataclasses
import hashlib
import math
import struct
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


_F32_BLOCK = struct.Struct("<1024f")


def finite_f32(payload, deadline: Deadline | None = None) -> bool:
    """Check every IEEE f32 with bounded C-level batches and 1024-scalar deadline checks."""
    if len(payload) % 4:
        raise RecipeError("f32 validation payload is truncated")
    for offset in range(0, len(payload), _F32_BLOCK.size):
        if deadline is not None:
            deadline.check()
        remaining = len(payload) - offset
        values = _F32_BLOCK.unpack_from(payload, offset) if remaining >= _F32_BLOCK.size else \
            struct.unpack_from("<" + str(remaining // 4) + "f", payload, offset)
        if not all(map(math.isfinite, values)):
            return False
    if deadline is not None:
        deadline.check()
    return True


def sha256_file(path, deadline: Deadline | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            if deadline is not None:
                deadline.check()
            chunk = source.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    if deadline is not None:
        deadline.check()
    return digest.hexdigest()
