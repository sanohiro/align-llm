#!/usr/bin/env python3
"""Construct and independently consume invocation-private native generation case records."""
from __future__ import annotations

import dataclasses
import hashlib
import math
from pathlib import Path
import struct
from collections.abc import Mapping

from gpu_backend_recipe import RecipeError, bounded_i64, bounded_text, canonical, lowercase_hex
from gpu_qualification_deadline import Deadline, checked, finite_f32
from gpu_qualification_records import exact_keys, parse_record, require_i32_array
from gpu_qualification_stream import Frame, NumericStream
from gpu_qualification_traversal import Traversal

MAX_RECORD_BYTES = 4 * 1024 * 1024
OBSERVATION_INTS = (
    "graph_nodes", "read_bytes", "read_calls", "sync_calls", "weight_upload_count",
    "weight_upload_bytes", "kv_upload_bytes", "input_upload_bytes", "prefill_executions", "prefill_microbatch_width",
    "decode_executions", "allocated_host_bytes", "allocated_device_bytes",
    "weights_buffer_bytes", "kv_buffer_bytes", "managed_host_peak_bytes", "application_host_reserved_bytes", "managed_device_peak_bytes",
    "resident_weight_payload_bytes", "resident_kv_payload_bytes",
    "model_operations", "model_layers", "model_experts",
    "device_total_bytes", "device_free_bytes",
)
OBSERVATION_TEXT = ("bundle_id", "device_name", "device_description", "device_id")
PHASES = {"production", "production_binding", "reproduction", "reproduction_binding",
          "forced", "forced_binding", "finish"}


@dataclasses.dataclass(frozen=True)
class Residency:
    weight_count: int
    weight_bytes: int
    kv_bytes: int

    @classmethod
    def derive(cls, geometry: Mapping[str, object], traversal: Traversal, maximum: int) -> Residency:
        if geometry.get("status") != "ok" or geometry.get("error_code") != "":
            raise RecipeError("native residency geometry is not successful")
        coverage, quant, source = (geometry.get(key) for key in ("coverage", "quant", "source"))
        if not all(isinstance(value, dict) for value in (coverage, quant, source)):
            raise RecipeError("native residency geometry lacks complete coverage")
        weight_count = 3 + 12 * traversal.layers
        for value in (coverage.get("tensor_count"), coverage.get("assigned_tensor_count"),
                      source.get("tensor_count")):
            if type(value) is not int or value != weight_count:
                raise RecipeError("native residency tensor coverage differs from model layout")
        if coverage.get("unassigned_tensors") != [] or coverage.get("size_sum_ok") is not True:
            raise RecipeError("native residency coverage is incomplete")
        weight_bytes = bounded_i64(coverage.get("total_tensor_bytes"), 1, (1 << 63) - 1,
                                   "native weight payload")
        if type(quant.get("total_tensor_bytes")) is not int or quant["total_tensor_bytes"] != weight_bytes:
            raise RecipeError("native residency payload totals differ")
        model = geometry["model"]
        head_dim = bounded_i64(model.get("head_dim"), 1, (1 << 63) - 1, "native KV head dimension")
        heads = bounded_i64(model.get("n_head_kv"), 1, (1 << 63) - 1, "native KV head count")
        kv_bytes = bounded_i64(8 * traversal.layers * head_dim * heads * (traversal.prompt + maximum - 1),
                               1, (1 << 63) - 1, "native KV payload")
        return cls(weight_count, weight_bytes, kv_bytes)


@dataclasses.dataclass(frozen=True)
class ModelWork:
    operations: int
    layers: int
    experts: int

    @classmethod
    def derive(cls, traversal: Traversal, context: int) -> ModelWork:
        routed = traversal.model == 2
        bounded_i64(context, traversal.prompt, (1 << 63) - 1, "native attention context")
        prefill = 0
        for offset in range(0, traversal.prompt, 128):
            valid = min(traversal.prompt, offset + 128)
            width = min(context, ((valid + 255) // 256) * 256)
            pads = 2 if width > valid else 0
            # Contiguous K is required by SET on every chunk. Non-final chunks end
            # at the highest layer's K/V writes (nine materializing operations),
            # without that layer's attention/FFN, output narrowing or vocabulary head.
            full_layer = (30 + traversal.selected if routed else 25) + pads
            prefill += (full_layer * traversal.layers + 6 if valid == traversal.prompt
                        else full_layer * (traversal.layers - 1) + 9 + pads + 1)
        decode = (32 + traversal.selected if routed else 27) * traversal.layers + 6
        operations = prefill + (traversal.positions - 1) * decode
        layers = traversal.layers * traversal.positions + (traversal.layers - 1) * (traversal.prefill_chunks - 1)
        experts = (traversal.selected * ((traversal.layers - 1) * traversal.prompt + 1
                    + traversal.layers * (traversal.positions - 1))) if routed else 0
        for value in (operations, layers, experts):
            bounded_i64(value, 0, (1 << 63) - 1, "native model work")
        return cls(operations, layers, experts)


@dataclasses.dataclass(frozen=True)
class NativeCase:
    document: dict[str, object]
    traversal: Traversal
    residency: Residency
    model_work: ModelWork

    @property
    def stream_path(self) -> Path:
        return Path(self.document["stream_root"]) / self.document["stream_name"]

    def input_bytes(self) -> bytes:
        data = canonical(self.document)
        if len(data) > MAX_RECORD_BYTES:
            raise RecipeError("native case input exceeds its bound")
        return data


@dataclasses.dataclass(frozen=True)
class NativeMetadata:
    production: dict[str, object]
    observation: dict[str, object]
    output_sha256: str


@dataclasses.dataclass(frozen=True)
class NativeSuccess:
    production: dict[str, object]
    observation: dict[str, object]
    output_sha256: str
    stream_sha256: str


def prepare(*, model_id: str, geometry: Mapping[str, object], calibration_case: Mapping[str, object],
            model_path: Path, pack_path: Path, geometry_path: Path, options_path: Path | None,
            cache_budget_bytes: int, stream_root: Path, stream_name: str) -> NativeCase:
    traversal = Traversal.derive(geometry, calibration_case)
    if model_id != ("qwen2" if traversal.model == 1 else "olmoe"):
        raise RecipeError("native case model does not match geometry")
    for path in (model_path, pack_path, geometry_path, stream_root, options_path):
        if path is not None and (not path.is_absolute() or len(str(path).encode()) > 4096 or "\0" in str(path)):
            raise RecipeError("native case physical path is invalid")
    if not stream_name or len(stream_name) > 64 or stream_name[0] not in "abcdefghijklmnopqrstuvwxyz0123456789" \
            or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for character in stream_name):
        raise RecipeError("native case stream name is invalid")
    bounded_i64(cache_budget_bytes, 0, (1 << 63) - 1, "native cache budget")
    temperature = calibration_case["temperature_micros"]
    seed = calibration_case["seed"]
    if type(temperature) is not int or temperature not in (0, 300000):
        raise RecipeError("native sampling temperature is invalid")
    bounded_i64(seed, -(1 << 63), (1 << 63) - 1, "native sampling seed")
    if temperature == 0 and seed != 0:
        raise RecipeError("native greedy seed is not zero")
    prompt = bounded_text(calibration_case["prompt_utf8"], 0, 1048576, "native prompt")
    text = bounded_text(calibration_case["expected_output_utf8"], 0, 1048576, "native expected output")
    if (model_id == "qwen2" and (cache_budget_bytes != 0 or temperature != 0)) \
            or (model_id == "olmoe" and cache_budget_bytes < 1):
        raise RecipeError("native model sampling/cache policy is invalid")
    if calibration_case["sampler_mode"] != ("greedy" if temperature == 0 else "seeded"):
        raise RecipeError("native sampler mode differs from temperature")
    if hashlib.sha256(prompt.encode()).hexdigest() != calibration_case["prompt_sha256"] \
            or hashlib.sha256(text.encode()).hexdigest() != calibration_case["expected_output_sha256"]:
        raise RecipeError("native frozen text digest differs")

    document = {
        "schema_version": 1, "artifact_kind": "GPU_RUNTIME_CASE_INPUT", "model_id": model_id,
        "model_path": str(model_path), "pack_path": str(pack_path), "geometry_path": str(geometry_path),
        "options_path": "" if options_path is None else str(options_path),
        "cache_budget_bytes": cache_budget_bytes, "prompt_utf8": prompt,
        "maximum_tokens": calibration_case["maximum_tokens"], "temperature_micros": temperature, "seed": seed,
        "expected_prompt_ids": list(calibration_case["prompt_token_ids"]),
        "expected_token_ids": list(calibration_case["expected_token_ids"]), "expected_output_utf8": text,
        "forced_ids": list(calibration_case["teacher_forced_token_ids"]), "stream_root": str(stream_root),
        "stream_name": stream_name, "stream_limit": traversal.maximum_bytes,
    }
    result = NativeCase(document, traversal, Residency.derive(geometry, traversal, calibration_case["maximum_tokens"]),
                        ModelWork.derive(traversal, geometry["model"]["context_length"]))
    result.input_bytes()
    return result


def _record(raw: bytes, kind: str, keys: tuple[str, ...]) -> dict[str, object]:
    record = exact_keys(parse_record(raw, MAX_RECORD_BYTES), keys, "native output")
    if type(record["schema_version"]) is not int or record["schema_version"] != 1 \
            or record["artifact_kind"] != kind or canonical(record) != raw:
        raise RecipeError("native output identity or canonical encoding is invalid")
    return record


def failure(raw: bytes, case: NativeCase) -> dict[str, object]:
    record = _record(raw, "GPU_RUNTIME_CASE_FAILURE", (
        "schema_version", "artifact_kind", "phase", "category", "stage", "stream_nonfinite_count", "stream_bytes", "stream_records"))
    if not isinstance(record["phase"], str) or record["phase"] not in PHASES:
        raise RecipeError("native failure phase is invalid")
    if not isinstance(record["category"], str) or not isinstance(record["stage"], str) \
            or record["category"] not in {"CONFIG", "BACKEND_UNAVAILABLE", "DEVICE_UNAVAILABLE", "BUNDLE_IDENTITY",
                                   "UNSUPPORTED_CAPABILITY", "MEMORY_BUDGET", "ALLOCATION", "TRANSFER",
                                   "COMPUTE", "NONFINITE", "DEVICE_LOST", "BUSY", "CLEANUP"} \
            or record["stage"] not in {"options", "model", "device", "plan", "allocate", "upload",
                                       "prefill", "decode", "readback", "synchronize", "release"}:
        raise RecipeError("native first-fault category or stage is invalid")
    bounded_i64(record["stream_nonfinite_count"], 0, case.traversal.scalar_count, "native nonfinite count")
    bounded_i64(record["stream_bytes"], 24, case.traversal.maximum_bytes, "native failed stream bytes")
    bounded_i64(record["stream_records"], 0, case.traversal.frame_count, "native failed stream records")
    if (record["category"] == "NONFINITE") != (record["stream_nonfinite_count"] > 0):
        raise RecipeError("native nonfinite category differs from its counter")
    return record


def _observation(raw: object, case: NativeCase, expected_bundle_id: str | None,
                 expected_device: str | None) -> dict[str, object]:
    observation = exact_keys(raw, ("available", *OBSERVATION_INTS, *OBSERVATION_TEXT), "native observation")
    gpu = bool(case.document["options_path"])
    if type(observation["available"]) is not bool or observation["available"] != gpu:
        raise RecipeError("native observation availability differs from execution")
    for key in OBSERVATION_INTS:
        bounded_i64(observation[key], 0, (1 << 63) - 1, "native " + key)
    for key in OBSERVATION_TEXT:
        bounded_text(observation[key], 0, 128, "native " + key)
    if not gpu:
        if any(observation[key] != 0 for key in OBSERVATION_INTS) \
                or any(observation[key] != "" for key in OBSERVATION_TEXT):
            raise RecipeError("CPU result invents GPU observations")
        return observation
    if expected_bundle_id is None or expected_device is None:
        raise RecipeError("GPU observation lacks independent device/bundle identity")
    lowercase_hex(expected_bundle_id, 64, "native expected bundle")
    if observation["bundle_id"] != expected_bundle_id or observation["device_name"] != expected_device \
            or not observation["device_description"]:
        raise RecipeError("native device/bundle identity differs")
    positions = case.traversal.positions
    if observation["device_total_bytes"] < 1 or observation["device_free_bytes"] > observation["device_total_bytes"]:
        raise RecipeError("native device memory properties are invalid")
    if observation["managed_host_peak_bytes"] < observation["allocated_host_bytes"] \
            or observation["managed_device_peak_bytes"] < observation["allocated_device_bytes"]:
        raise RecipeError("native memory peak is below its current allocation")
    if not 0 < observation["resident_weight_payload_bytes"] <= observation["weights_buffer_bytes"] \
            or not 0 < observation["resident_kv_payload_bytes"] <= observation["kv_buffer_bytes"]:
        raise RecipeError("native resident payload is outside its buffer extent")
    if observation["resident_weight_payload_bytes"] != case.residency.weight_bytes \
            or observation["resident_kv_payload_bytes"] != case.residency.kv_bytes \
            or observation["weight_upload_count"] != case.residency.weight_count:
        raise RecipeError("native resident payload or binding count differs from independent geometry")
    if observation["model_operations"] != case.model_work.operations \
            or observation["model_layers"] != case.model_work.layers \
            or observation["model_experts"] != case.model_work.experts:
        actual = tuple(observation[key] for key in ("model_operations", "model_layers", "model_experts"))
        expected = (case.model_work.operations, case.model_work.layers, case.model_work.experts)
        raise RecipeError(f"native model work differs from independent geometry: {actual} != {expected}")
    if observation["read_calls"] != positions or observation["read_bytes"] != positions * case.traversal.vocabulary * 4 \
            or observation["prefill_executions"] != case.traversal.prefill_chunks \
            or observation["prefill_microbatch_width"] != min(128, case.traversal.prompt) \
            or observation["decode_executions"] != positions - 1:
        raise RecipeError("native production observations differ from generated positions")
    for key in ("graph_nodes", "weight_upload_count", "input_upload_bytes", "allocated_host_bytes",
                "allocated_device_bytes", "weights_buffer_bytes", "kv_buffer_bytes"):
        if observation[key] < 1:
            raise RecipeError("native successful observation is absent: " + key)
    return observation


def _finite(payload: bytes, deadline: Deadline | None = None) -> None:
    if not finite_f32(payload, deadline):
        raise RecipeError("native numeric stream contains a nonfinite value")


def validate_router(scores_raw, ids_raw, weights_raw, deadline=None):
    _finite(scores_raw, deadline)
    _finite(weights_raw, deadline)
    scores = tuple(value for (value,) in checked(struct.iter_unpack("<f", scores_raw), deadline))
    ids = tuple(value for (value,) in checked(struct.iter_unpack("<i", ids_raw), deadline))
    weights = tuple(value for (value,) in checked(struct.iter_unpack("<f", weights_raw), deadline))
    if any(not 0 <= index < len(scores) for index in checked(ids, deadline)) or len(set(checked(ids, deadline))) != len(ids):
        raise RecipeError("native routing IDs are invalid")
    chosen = set(checked(ids, deadline))
    if any(scores[left] < scores[right] for left, right in checked(zip(ids, ids[1:]), deadline)) \
            or any(score > scores[ids[-1]] for index, score in checked(enumerate(scores), deadline) if index not in chosen) \
            or weights != tuple(scores[index] for index in checked(ids, deadline)):
        raise RecipeError("native routing selection or weights are inconsistent")


def consume_stream(case: NativeCase, *, deadline: Deadline | None = None) -> str:
    with NumericStream(case.stream_path, model=case.traversal.model,
                       maximum_bytes=case.traversal.maximum_bytes, deadline=deadline) as stream:
        for instruction in case.traversal.instructions():
            if isinstance(instruction, Frame):
                if stream.read_frame() != instruction:
                    raise RecipeError("native numeric frame differs from independent traversal")
                remaining = instruction.payload_bytes
                while remaining:
                    payload = stream.read_payload()
                    _finite(payload, deadline)
                    remaining -= len(payload)
            else:
                payloads = []
                for offset, (kind, width) in enumerate(((3, instruction.experts), (4, instruction.selected),
                                                       (5, instruction.selected))):
                    expected = Frame(kind, instruction.layer, instruction.step, width, 1, width * 4,
                                     instruction.ordinal + offset)
                    if stream.read_frame() != expected:
                        raise RecipeError("native routing frame differs from independent traversal")
                    payloads.append(stream.read_payload())
                scores_raw, ids_raw, weights_raw = payloads
                validate_router(scores_raw, ids_raw, weights_raw, deadline)
        if stream.read_frame() is not None or stream.consumed_bytes != case.traversal.maximum_bytes:
            raise RecipeError("native numeric stream has extra data or a wrong size")
        return stream.sha256


def success_metadata(raw: bytes, case: NativeCase, *, expected_bundle_id: str | None = None,
            expected_device: str | None = None, deadline: Deadline | None = None) -> NativeMetadata:
    if deadline is not None:
        deadline.check()
    record = _record(raw, "GPU_RUNTIME_CASE_OUTPUT", (
        "schema_version", "artifact_kind", "production", "stream_bytes", "stream_records"))
    production = exact_keys(record["production"], ("text", "token_ids", "prompt_ids", "observation"),
                            "native production")
    text = bounded_text(production["text"], 0, 1048576, "native output text")
    require_i32_array(production["token_ids"], "native output tokens", minimum=1, maximum=128)
    require_i32_array(production["prompt_ids"], "native output prompt", minimum=1, maximum=2048)
    if text != case.document["expected_output_utf8"] \
            or production["token_ids"] != case.document["expected_token_ids"] \
            or production["prompt_ids"] != case.document["expected_prompt_ids"]:
        raise RecipeError("native output does not match frozen case")
    if type(record["stream_bytes"]) is not int or record["stream_bytes"] != case.traversal.maximum_bytes \
            or type(record["stream_records"]) is not int or record["stream_records"] != case.traversal.frame_count:
        raise RecipeError("native output stream totals differ from independent traversal")
    observation = _observation(production["observation"], case, expected_bundle_id, expected_device)
    return NativeMetadata(production, observation, hashlib.sha256(text.encode()).hexdigest())


def success(raw: bytes, case: NativeCase, *, expected_bundle_id: str | None = None,
            expected_device: str | None = None, deadline: Deadline | None = None) -> NativeSuccess:
    metadata = success_metadata(raw, case, expected_bundle_id=expected_bundle_id,
                                expected_device=expected_device, deadline=deadline)
    return NativeSuccess(metadata.production, metadata.observation, metadata.output_sha256,
                         consume_stream(case, deadline=deadline))
