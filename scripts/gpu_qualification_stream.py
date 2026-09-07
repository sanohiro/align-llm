#!/usr/bin/env python3
"""Retained, bounded reader for the G1 private numeric stream."""

from __future__ import annotations

import dataclasses
import hashlib
import os
import pathlib
import stat
import struct

from gpu_backend_recipe import RecipeError, lowercase_hex


MAX_BYTES = 4 * 1024 * 1024 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_CHUNK_BYTES = 4 * 1024 * 1024
FILE_HEADER = struct.Struct("<8sIIQ")
RECORD_HEADER = struct.Struct("<6I2Q")


def _identity(metadata: os.stat_result) -> tuple[int, ...]:
    return tuple(getattr(metadata, field) for field in (
        "st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns",
    ))


@dataclasses.dataclass(frozen=True)
class Frame:
    kind: int
    layer: int
    step: int
    width: int
    height: int
    payload_bytes: int
    ordinal: int


class NumericStream:
    def __init__(
        self, path: pathlib.Path, *, model: int, maximum_bytes: int,
        expected_sha256: str | None = None,
    ) -> None:
        self._fd = -1
        self._failed = True
        self.verified = False
        self.records = 0
        self.consumed_bytes = 0
        self._remaining = 0
        self._hash = hashlib.sha256()
        self.path = path
        if not path.is_absolute() or type(model) is not int or model not in (1, 2) \
                or type(maximum_bytes) is not int or not 108 <= maximum_bytes <= MAX_BYTES:
            raise RecipeError("numeric stream admission arguments are invalid")
        if expected_sha256 is not None:
            lowercase_hex(expected_sha256, 64, "numeric stream digest")
        self._expected_sha256 = expected_sha256
        self.maximum_bytes = maximum_bytes
        try:
            self._fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                               | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0))
            before = os.fstat(self._fd)
            self._initial = _identity(before)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 \
                    or not 108 <= before.st_size <= maximum_bytes:
                raise RecipeError("numeric stream is not a bounded single-link regular file")
            magic, observed_model, reserved, declared = FILE_HEADER.unpack(self._read_exact(FILE_HEADER.size))
            if magic != b"G1TRACE1" or observed_model != model or reserved != 0 \
                    or not before.st_size <= declared <= maximum_bytes:
                raise RecipeError("numeric stream header does not match its contract")
            self.maximum_bytes = declared
            self._failed = False
        except BaseException:
            self.close()
            raise

    def _read_exact(self, count: int) -> bytes:
        if self._fd < 0:
            raise RecipeError("numeric stream is closed")
        if self.consumed_bytes > self.maximum_bytes - count:
            raise RecipeError("numeric stream exceeds its byte ceiling")
        result = bytearray()
        remaining = count
        while remaining:
            data = os.read(self._fd, remaining)
            if not data:
                raise RecipeError("numeric stream is truncated")
            self._hash.update(data)
            self.consumed_bytes += len(data)
            remaining -= len(data)
            result.extend(data)
        return bytes(result)

    def read_frame(self) -> Frame | None:
        if self._fd < 0:
            raise RecipeError("numeric stream is closed")
        if self._failed:
            raise RecipeError("numeric stream already failed")
        if self.verified:
            return None
        self._failed = True
        if self._remaining:
            raise RecipeError("numeric payload must be consumed before its next frame")
        values = RECORD_HEADER.unpack(self._read_exact(RECORD_HEADER.size))
        kind, layer, step, width, height, reserved, payload, ordinal = values
        if kind == 0:
            if values[:-1] != (0,) * 7 or ordinal != self.records or not self.records:
                raise RecipeError("numeric stream footer is invalid")
            if os.read(self._fd, 1):
                raise RecipeError("numeric stream has trailing bytes")
            if self.consumed_bytes != self._initial[4] \
                    or _identity(os.fstat(self._fd)) != self._initial \
                    or _identity(self.path.stat(follow_symlinks=False)) != self._initial:
                raise RecipeError("numeric stream identity changed")
            if self._expected_sha256 is not None and self._hash.hexdigest() != self._expected_sha256:
                raise RecipeError("numeric stream digest does not match")
            self.verified = True
            self._failed = False
            return None
        if kind not in (1, 2, 3, 4, 5, 6) or reserved != 0 or ordinal != self.records \
                or not width or not height or payload != width * height * 4 \
                or payload > MAX_PAYLOAD_BYTES or step > (127 if kind == 1 else 4096):
            raise RecipeError("numeric frame tag, ordinal or shape is invalid")
        if (kind in (1, 6) and (layer != 0xffffffff or height != 1)) \
                or (kind not in (1, 6) and layer == 0xffffffff):
            raise RecipeError("numeric frame layer does not match its kind")
        if self.consumed_bytes > self.maximum_bytes - payload - RECORD_HEADER.size:
            raise RecipeError("numeric frame leaves no room for its payload and footer")
        self.records += 1
        self._remaining = payload
        self._failed = False
        return Frame(kind, layer, step, width, height, payload, ordinal)

    def read_payload(self, maximum_bytes: int = MAX_CHUNK_BYTES) -> bytes:
        if self._failed:
            raise RecipeError("numeric stream already failed")
        self._failed = True
        if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= MAX_CHUNK_BYTES:
            raise RecipeError("numeric payload chunk bound is invalid")
        count = min(maximum_bytes, self._remaining)
        data = self._read_exact(count)
        self._remaining -= count
        self._failed = False
        return data

    @property
    def sha256(self) -> str:
        if not self.verified or self._failed:
            raise RecipeError("numeric stream has not been verified")
        return self._hash.hexdigest()

    def close(self) -> None:
        if getattr(self, "_fd", -1) >= 0:
            descriptor, self._fd = self._fd, -1
            os.close(descriptor)

    def __enter__(self) -> NumericStream:
        return self

    def __exit__(self, kind, value, traceback) -> None:
        try:
            self.close()
        except OSError:
            if kind is None:
                raise
        if kind is None and (not self.verified or self._failed):
            raise RecipeError("numeric stream was not completely consumed")

    def __del__(self) -> None:
        try:
            self.close()
        except OSError:
            pass
