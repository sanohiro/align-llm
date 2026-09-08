#!/usr/bin/env python3
"""Independent geometry/case projection for the complete G1 numeric tensor traversal."""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Iterator, Mapping

from gpu_qualification_deadline import Deadline
from gpu_backend_recipe import RecipeError, bounded_i64
from gpu_qualification_pair import NumericPair
from gpu_qualification_records import require_i32_array
from gpu_qualification_stream import Frame, MAX_BYTES, MAX_CHUNK_BYTES, MAX_PAYLOAD_BYTES


@dataclasses.dataclass(frozen=True)
class Router:
    layer: int
    step: int
    experts: int
    selected: int
    ordinal: int


@dataclasses.dataclass(frozen=True)
class Traversal:
    model: int
    layers: int
    embedding: int
    vocabulary: int
    experts: int
    selected: int
    prompt: int
    forced: int
    expected_ids: tuple[int, ...]

    @classmethod
    def derive(cls, geometry: Mapping[str, object], case: Mapping[str, object]) -> Traversal:
        if geometry.get("kind") != "R1_MODEL_IR" or type(geometry.get("schema_version")) is not int \
                or geometry["schema_version"] != 2 or not isinstance(geometry.get("model"), dict):
            raise RecipeError("numeric geometry is not model IR schema 2")
        model = geometry["model"]
        if model.get("arch") not in ("qwen2", "olmoe"):
            raise RecipeError("numeric geometry architecture is unsupported")
        def field(name, low=1, high=(1 << 32) - 2):
            return bounded_i64(model.get(name), low, high, "numeric geometry " + name)
        layers, embedding, vocabulary = field("n_layer"), field("n_embd"), field("n_vocab")
        routed = model["arch"] == "olmoe"
        experts = field("n_expert", 1 if routed else 0, MAX_CHUNK_BYTES // 4 if routed else 0)
        selected = field("n_expert_used", 1, experts) if routed else 0
        prompt = require_i32_array(case.get("prompt_token_ids"), "numeric prompt", minimum=1, maximum=2048)
        forced = require_i32_array(case.get("teacher_forced_token_ids"), "numeric forced tokens", minimum=1)
        maximum = bounded_i64(case.get("maximum_tokens"), 1, 128, "numeric maximum tokens")
        expected = require_i32_array(case.get("expected_token_ids"), "numeric expected tokens", minimum=1, maximum=maximum)
        if any(token >= vocabulary for tokens in (prompt, forced, expected) for token in tokens):
            raise RecipeError("numeric case token is outside the vocabulary")
        context = field("context_length", 1, (1 << 63) - 1)
        if len(prompt) + max(maximum - 1, len(forced)) > context:
            raise RecipeError("numeric traversal exceeds model context")
        if max(embedding * (len(prompt) if layers > 1 else 1), vocabulary) * 4 > MAX_PAYLOAD_BYTES:
            raise RecipeError("numeric tensor exceeds its frame payload bound")
        result = cls(2 if routed else 1, layers, embedding, vocabulary, experts, selected,
                     len(prompt), len(forced), tuple(expected))
        if result.maximum_bytes > MAX_BYTES:
            raise RecipeError("numeric traversal exceeds the stream byte bound")
        return result

    @property
    def positions(self) -> int:
        return len(self.expected_ids)

    @property
    def columns(self) -> int:
        return 2 * ((self.layers - 1) * self.prompt + 1) + (self.positions - 1 + self.forced) * self.layers

    @property
    def layer_count(self) -> int:
        return self.layers * (self.positions + self.forced + 1)

    @property
    def router_count(self) -> int:
        return self.columns if self.model == 2 else 0

    @property
    def final_count(self) -> int:
        return self.vocabulary * (2 * self.positions + self.forced + 1)

    @property
    def scalar_count(self) -> int:
        return self.embedding * self.columns + self.final_count + (self.experts + self.selected) * self.router_count

    @property
    def frame_count(self) -> int:
        return self.layer_count + 3 * self.router_count + 2 * self.positions + self.forced + 1

    @property
    def maximum_bytes(self) -> int:
        return 24 + 40 * (self.frame_count + 1) + 4 * (self.scalar_count + self.selected * self.router_count)

    def instructions(self) -> Iterator[Frame | Router]:
        ordinal = 0
        for step in range(self.positions):
            yield Frame(1, 0xffffffff, step, self.vocabulary, 1, self.vocabulary * 4, ordinal)
            ordinal += 1
        for positions in (self.positions, self.forced + 1):
            for step in range(positions):
                for layer in range(self.layers):
                    width = self.prompt if step == 0 and layer != self.layers - 1 else 1
                    if self.model == 2:
                        for _ in range(width):
                            yield Router(layer, step, self.experts, self.selected, ordinal)
                            ordinal += 3
                    yield Frame(2, layer, step, self.embedding, width, self.embedding * width * 4, ordinal)
                    ordinal += 1
                yield Frame(6, 0xffffffff, step, self.vocabulary, 1, self.vocabulary * 4, ordinal)
                ordinal += 1

    def compare(
        self, reference: pathlib.Path, candidate: pathlib.Path, *, reference_sha256: str,
        reference_token_ids: list[int], candidate_token_ids: list[int], comparison: Mapping[str, str],
        deadline: Deadline | None = None,
    ) -> tuple[dict[str, object], int, int]:
        for tokens in (reference_token_ids, candidate_token_ids):
            require_i32_array(tokens, "actual production tokens", minimum=1, maximum=128)
            if tuple(tokens) != self.expected_ids:
                raise RecipeError("production token prefix differs from the frozen case")
        with NumericPair(reference, candidate, model=self.model, maximum_bytes=self.maximum_bytes,
                         reference_sha256=reference_sha256,
                         absolute_bits=comparison["absolute_tolerance_f32_bits"],
                         relative_bits=comparison["relative_tolerance_f32_bits"],
                         near_tie_bits=comparison["near_tie_tolerance_f32_bits"], deadline=deadline) as pair:
            for instruction in self.instructions():
                if isinstance(instruction, Frame):
                    pair.scalar(instruction)
                else:
                    pair.router(**dataclasses.asdict(instruction))
            pair.finish()
        numeric = {"compared": True}
        for name, expected, actual in (
            ("scalar", self.scalar_count, pair.scalars.scalar_count),
            ("layer", self.layer_count, pair.layer_count),
            ("router_boundary", self.router_count, pair.routing.boundary_count),
            ("final_logit", self.final_count, pair.final_logit_count),
        ):
            if expected != actual:
                raise RecipeError("numeric traversal count disagrees with consumed tensors")
            numeric[f"expected_{name}_count"] = expected
            numeric[f"actual_{name}_count"] = actual
        numeric.update(
            max_absolute_f64_bits=pair.scalars.max_absolute_f64_bits,
            max_relative_f64_bits=pair.scalars.max_relative_f64_bits,
            near_tie_count=pair.routing.near_tie_count, mismatch_count=pair.scalars.mismatch_count,
        )
        return numeric, pair.scalars.nonfinite_count, pair.routing.routing_mismatch_count
