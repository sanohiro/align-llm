#!/usr/bin/env python3
"""Consume adjacent numeric streams against independently supplied tensor expectations."""

from __future__ import annotations

import contextlib
import pathlib
import struct
import sys

from gpu_backend_recipe import RecipeError, lowercase_hex
from gpu_qualification_deadline import Deadline, checked
from gpu_qualification_numeric import RoutingComparison, ScalarComparison
from gpu_qualification_stream import Frame, MAX_CHUNK_BYTES, NumericStream


class NumericPair:
    def __init__(
        self, reference: pathlib.Path, candidate: pathlib.Path, *, model: int,
        maximum_bytes: int, reference_sha256: str,
        absolute_bits: str, relative_bits: str, near_tie_bits: str,
        deadline: Deadline | None = None,
    ) -> None:
        self.deadline = deadline
        self._stack = contextlib.ExitStack()
        self._failed = True
        self.finished = False
        self.layer_count = 0
        self.final_logit_count = 0
        lowercase_hex(reference_sha256, 64, "paired reference stream digest")
        self.scalars = ScalarComparison(absolute_bits, relative_bits, deadline=deadline)
        self.routing = RoutingComparison(self.scalars, near_tie_bits)
        try:
            self.reference = self._stack.enter_context(NumericStream(
                reference, model=model, maximum_bytes=maximum_bytes,
                expected_sha256=reference_sha256, deadline=deadline,
            ))
            self.candidate = self._stack.enter_context(NumericStream(
                candidate, model=model, maximum_bytes=maximum_bytes, deadline=deadline,
            ))
        except BaseException:
            # Close acquired streams without claiming complete consumption or masking admission.
            self._stack.__exit__(*sys.exc_info())
            raise
        self._failed = False

    def _begin(self) -> None:
        if self._failed or self.finished:
            raise RecipeError("numeric pair is failed or finished")
        self._failed = True

    def _expect(self, expected: Frame) -> None:
        if self.reference.read_frame() != expected or self.candidate.read_frame() != expected:
            raise RecipeError("numeric frame does not match independent case expectation")

    def scalar(self, expected: Frame) -> None:
        self._begin()
        if expected.kind not in (1, 2, 6):
            raise RecipeError("scalar comparison requires a layer or final-logit frame")
        self._expect(expected)
        remaining = expected.payload_bytes
        while remaining:
            count = min(remaining, MAX_CHUNK_BYTES)
            self.scalars.compare(self.reference.read_payload(count), self.candidate.read_payload(count))
            remaining -= count
        if expected.kind == 2:
            self.layer_count += 1
        else:
            self.final_logit_count += expected.width
        self._failed = False

    def router(self, *, layer: int, step: int, experts: int, selected: int, ordinal: int) -> None:
        self._begin()
        if any(type(value) is not int for value in (layer, step, experts, selected, ordinal)) \
                or not 0 < selected <= experts <= MAX_CHUNK_BYTES // 4:
            raise RecipeError("routing boundary expectation is invalid")
        payloads = []
        # One token's boundary is three adjacent frames, bounding retained routing payloads.
        for offset, (kind, width) in enumerate(((3, experts), (4, selected), (5, selected))):
            self._expect(Frame(kind, layer, step, width, 1, width * 4, ordinal + offset))
            payloads.append((self.reference.read_payload(width * 4), self.candidate.read_payload(width * 4)))
        reference_ids, candidate_ids = (
            tuple(value for (value,) in checked(struct.iter_unpack("<i", data), self.deadline)) for data in payloads[1]
        )
        self.routing.compare(*payloads[0], reference_ids, candidate_ids, *payloads[2])
        self._failed = False

    def finish(self) -> None:
        self._begin()
        if self.reference.read_frame() is not None or self.candidate.read_frame() is not None:
            raise RecipeError("numeric pair has unrequested frames")
        self.finished = True
        self._failed = False

    def __enter__(self) -> NumericPair:
        return self

    def __exit__(self, kind, value, traceback) -> None:
        self._stack.__exit__(kind, value, traceback)
        if kind is None and (self._failed or not self.finished):
            raise RecipeError("numeric pair was not completely compared")
