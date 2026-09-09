#!/usr/bin/env python3
"""Assemble a schema-1 qualification profile from frozen source and calibration records."""

from __future__ import annotations

import dataclasses
import hashlib

from gpu_backend_recipe import MAX_SOURCE_MANIFEST_BYTES, RecipeError, canonical
from gpu_qualification_records import (
    MAX_BUNDLE_BYTES, MAX_CALIBRATION_BYTES, MAX_PROFILE_BYTES, expected_profile_cases,
    normalize_source_manifest, parse_record, validate_bundle, validate_calibration,
    validate_profile_records, validate_runtime_option,
)


@dataclasses.dataclass(frozen=True)
class ModelPaths:
    model_path: str
    pack_path: str
    geometry_path: str
    calibration_path: str
    runtime_cache_budget_bytes: int


def assemble_profile(
    *, profile_id: str, platform: str, option_id: str,
    runtime_option_raw: bytes, align_source_raw: bytes, ggml_source_raw: bytes,
    bundle_raw: bytes, bundle_manifest_path: str, calibration_raws: list[bytes],
    model_paths: tuple[ModelPaths, ModelPaths], preparation_deadline_ns: int,
    generation_deadline_ns: int,
) -> bytes:
    """Construct identities and the complete CPU/GPU expansion; never infer calibration results."""
    if len(model_paths) != 2 or len(calibration_raws) != 2:
        raise RecipeError("profile assembly requires two models and calibrations")
    align_source = normalize_source_manifest(parse_record(align_source_raw, MAX_SOURCE_MANIFEST_BYTES))
    ggml_source = normalize_source_manifest(parse_record(ggml_source_raw, MAX_SOURCE_MANIFEST_BYTES))
    bundle = validate_bundle(parse_record(bundle_raw, MAX_BUNDLE_BYTES), ggml_source)
    calibrations = [validate_calibration(parse_record(raw, MAX_CALIBRATION_BYTES)) for raw in calibration_raws]
    option = validate_runtime_option(parse_record(runtime_option_raw, MAX_PROFILE_BYTES), embedded=False)
    models = []
    for calibration, paths in zip(calibrations, model_paths, strict=True):
        identity = calibration["model"]
        models.append({
            "model_id": identity["model_id"],
            "model_path": paths.model_path,
            "model_sha256": identity["model_sha256"],
            "pack_path": paths.pack_path,
            "pack_sha256": identity["pack_sha256"],
            "geometry_path": paths.geometry_path,
            "geometry_sha256": identity["geometry_sha256"],
            "calibration_path": paths.calibration_path,
            "calibration_sha256": hashlib.sha256(canonical(calibration)).hexdigest(),
            "runtime_cache_budget_bytes": paths.runtime_cache_budget_bytes,
        })
    profile = {
        "schema_version": 1,
        "artifact_kind": "GPU_RUNTIME_PROFILE",
        "profile_id": profile_id,
        "platform": platform,
        "source": {"commit": align_source["commit"],
                   "manifest_sha256": hashlib.sha256(canonical(align_source)).hexdigest()},
        "bundle_manifest": {"path": bundle_manifest_path,
                            "sha256": hashlib.sha256(canonical(bundle)).hexdigest()},
        "models": models,
        "runtime_options": [{"option_id": option_id, **option}],
        "cases": expected_profile_cases(calibrations, option_id),
        "deadlines_ns": {"preparation": preparation_deadline_ns, "generation": generation_deadline_ns},
    }
    records = validate_profile_records(
        runtime_option_raw=runtime_option_raw, align_source_raw=align_source_raw,
        ggml_source_raw=ggml_source_raw, bundle_raw=bundle_raw,
        calibration_raws=calibration_raws, profile_raw=canonical(profile),
    )
    return canonical(records["profile"])
