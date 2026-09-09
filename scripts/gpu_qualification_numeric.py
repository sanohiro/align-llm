#!/usr/bin/env python3
"""Exact schema-1 scalar comparison over bounded binary32 stream chunks."""

from __future__ import annotations

import math
import struct
from fractions import Fraction

from gpu_backend_recipe import RecipeError
from gpu_qualification_deadline import Deadline, checked
from gpu_qualification_records import f32_tolerance


MAX_CHUNK_BYTES = 4 * 1024 * 1024
MIN_NORMAL = 2.0 ** -126


def _tolerance(bits: str) -> float:
    return struct.unpack(">f", bytes.fromhex(f32_tolerance(bits, "numeric tolerance")))[0]


class ScalarComparison:
    def __init__(self, absolute_bits: str, relative_bits: str, *, deadline: Deadline | None = None) -> None:
        self.deadline = deadline
        self.absolute = _tolerance(absolute_bits)
        self.relative = _tolerance(relative_bits)
        self.scalar_count = 0
        self.nonfinite_count = 0
        self.mismatch_count = 0
        self._absolute_max = 0.0
        self._relative_max = Fraction(0)
        self._relative_floor = 0.0

    def compare(self, reference: bytes, candidate: bytes) -> None:
        if len(reference) != len(candidate) or len(reference) % 4 \
                or len(reference) > MAX_CHUNK_BYTES:
            raise RecipeError("numeric chunk size is invalid")
        count = len(reference) // 4
        if self.scalar_count > (1 << 63) - 1 - count:
            raise RecipeError("numeric scalar count exceeds its bound")
        self.scalar_count += count
        for (r,), (c,) in checked(zip(struct.iter_unpack("<f", reference),
                                      struct.iter_unpack("<f", candidate), strict=True), self.deadline):
            if not math.isfinite(r) or not math.isfinite(c):
                self.nonfinite_count += 1
                continue
            if r == c:
                continue  # Includes opposite signed zero, after rejecting all nonfinites.
            difference = abs(c - r)
            scale = max(abs(r), abs(c), MIN_NORMAL)
            # Each operand has at most 24 significand bits. R*scale has at most 48, so this
            # product and the selected threshold are EXACT binary64 values, without underflow.
            threshold = max(self.absolute, self.relative * scale)
            if difference == threshold:
                # Subtraction can round when binary32 exponents are far apart. Its rounded value
                # can change an order comparison against an exact threshold only on equality.
                exact_difference = abs(Fraction(c) - Fraction(r))
                mismatch = exact_difference > Fraction(threshold)
            else:
                exact_difference = None
                mismatch = difference > threshold
            if mismatch:
                self.mismatch_count += 1
            # Rounding is monotone: max(round(d)) == round(max(d)). This is one correctly-rounded
            # subtraction, so the absolute maximum does not require retaining every exact d.
            self._absolute_max = max(self._absolute_max, difference)
            approximate_relative = difference / scale
            if approximate_relative >= self._relative_floor:
                if exact_difference is None:
                    exact_difference = abs(Fraction(c) - Fraction(r))
                exact_relative = exact_difference / Fraction(scale)
                if exact_relative > self._relative_max:
                    self._relative_max = exact_relative
                    # The subtraction and division each round; the stored exact maximum also
                    # rounds when converted for this filter. Four adjacent binary64 values give
                    # a conservative exclusion margin even at a binade boundary. Candidates in
                    # that margin are ordered exactly, never by the double-rounded quotient.
                    floor = float(exact_relative)
                    for _ in range(4):
                        floor = math.nextafter(floor, -math.inf)
                    self._relative_floor = floor

    @property
    def max_absolute_f64_bits(self) -> str:
        return struct.pack(">d", self._absolute_max).hex()

    @property
    def max_relative_f64_bits(self) -> str:
        return struct.pack(">d", float(self._relative_max)).hex()


class RoutingComparison:
    def __init__(self, scalars: ScalarComparison, near_tie_bits: str) -> None:
        self.scalars = scalars
        self.deadline = scalars.deadline
        self.tolerance = Fraction(_tolerance(near_tie_bits))
        self.boundary_count = 0
        self.near_tie_count = 0
        self.routing_mismatch_count = 0

    def compare(
        self, reference_scores: bytes, candidate_scores: bytes,
        reference_ids: tuple[int, ...], candidate_ids: tuple[int, ...],
        reference_weights: bytes, candidate_weights: bytes,
    ) -> None:
        count = len(reference_scores) // 4
        selected = len(reference_ids)
        if not reference_scores or len(reference_scores) % 4 \
                or len(reference_scores) != len(candidate_scores) \
                or len(reference_scores) > MAX_CHUNK_BYTES \
                or not 0 < selected <= count or selected != len(candidate_ids) \
                or len(reference_weights) != 4 * selected \
                or len(candidate_weights) != len(reference_weights):
            raise RecipeError("routing tensor shape is invalid")
        for ids in (reference_ids, candidate_ids):
            if any(type(index) is not int or not 0 <= index < count for index in checked(ids, self.deadline)) \
                    or len(set(checked(ids, self.deadline))) != selected:
                raise RecipeError("routing IDs are duplicated or out of range")
        reference = tuple(value for (value,) in checked(struct.iter_unpack("<f", reference_scores), self.deadline))
        candidate = tuple(value for (value,) in checked(struct.iter_unpack("<f", candidate_scores), self.deadline))
        mismatches_before = self.scalars.mismatch_count
        nonfinite_before = self.scalars.nonfinite_count
        self.scalars.compare(reference_scores, candidate_scores)
        self.scalars.compare(reference_weights, candidate_weights)
        self.boundary_count += 1
        if any(not math.isfinite(value) for values in (reference, candidate) for value in checked(values, self.deadline)):
            return  # The scalar owner already records NONFINITE before any routing predicate.

        def valid_topk(scores, ids):
            chosen = set(checked(ids, self.deadline))
            if any(scores[left] < scores[right] for left, right in checked(zip(ids, ids[1:]), self.deadline)):
                return False
            return not any(score > scores[ids[-1]] for index, score in checked(enumerate(scores), self.deadline) if index not in chosen)

        if not valid_topk(reference, reference_ids) or not valid_topk(candidate, candidate_ids):
            self.routing_mismatch_count += 1
            return
        chosen = set(checked(reference_ids, self.deadline))
        excluded = [score for index, score in checked(enumerate(reference), self.deadline) if index not in chosen]
        near_tie = False
        if not excluded:
            matches = reference_ids == candidate_ids
        else:
            boundary = Fraction(reference[reference_ids[-1]])
            gap = boundary - Fraction(max(checked(excluded, self.deadline)))
            if gap > self.tolerance:
                matches = reference_ids == candidate_ids
            else:
                near_tie = True
                group = {index for index, score in checked(enumerate(reference), self.deadline)
                         if abs(Fraction(score) - boundary) <= self.tolerance}
                reference_outside = tuple(index for index in checked(reference_ids, self.deadline) if index not in group)
                candidate_outside = tuple(index for index in checked(candidate_ids, self.deadline) if index not in group)
                matches = reference_outside == candidate_outside
        if not matches:
            self.routing_mismatch_count += 1
        elif near_tie and self.scalars.mismatch_count == mismatches_before \
                and self.scalars.nonfinite_count == nonfinite_before:
            self.near_tie_count += 1
