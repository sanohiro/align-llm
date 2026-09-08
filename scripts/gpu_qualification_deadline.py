#!/usr/bin/env python3
"""The shared generation deadline, checked inside bounded validation work."""
from __future__ import annotations

import dataclasses
import hashlib
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


# A little-endian F32 is nonfinite exactly when its exponent is all ones:
# byte 3 has low seven bits 0x7f, and byte 2 has its high bit set.
_F32_HIGH_EXPONENT = bytes(int((value & 0x7f) == 0x7f) for value in range(256))
_F32_BLOCK_BYTES = 4096


def finite_f32(payload, deadline: Deadline | None = None) -> bool:
    """Classify every F32 exponent, with unchanged 1024-scalar deadline checks."""
    if len(payload) % 4:
        raise RecipeError("f32 validation payload is truncated")
    for offset in range(0, len(payload), _F32_BLOCK_BYTES):
        if deadline is not None:
            deadline.check()
        end = min(offset + _F32_BLOCK_BYTES, len(payload))
        high = bytes(payload[offset + 3:end:4]).translate(_F32_HIGH_EXPONENT)
        index = high.find(b"\1")
        while index >= 0:
            if payload[offset + index * 4 + 2] & 0x80:
                return False
            index = high.find(b"\1", index + 1)
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
