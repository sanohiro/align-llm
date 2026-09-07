#!/usr/bin/env python3
"""Exclusive, replay-checked evidence publication for the G1 GPU qualifier."""

from __future__ import annotations

import dataclasses
import hashlib
import os
import pathlib
import shutil
import stat
import tempfile
from collections.abc import Mapping

from gpu_backend_recipe import (
    MAX_BUNDLE_ARTIFACT_BYTES,
    RecipeError,
    canonical,
    rename_noreplace,
    retained_path,
)
from gpu_qualification_input import AdmittedInput
from gpu_qualification_records import (
    expected_directory_roles,
    replay_evidence_directory,
    validate_evidence_records,
)


MAX_EVIDENCE_FILES = 4096
MAX_EVIDENCE_RESULT_BYTES = 8 * 1024 * 1024


@dataclasses.dataclass(frozen=True)
class RetainedFile:
    role: str
    data: bytes
    original_bytes: int | None = None
    original_sha256: str | None = None


@dataclasses.dataclass(frozen=True)
class PreparedPublication:
    content: dict[str, bytes]
    rows: list[dict[str, object]]


def _row(path: str, retained: RetainedFile) -> dict[str, object]:
    retained_path(path, "evidence retained path")
    size = len(retained.data)
    if size > MAX_BUNDLE_ARTIFACT_BYTES:
        raise RecipeError("evidence retained file exceeds its bound")
    sha256 = hashlib.sha256(retained.data).hexdigest()
    original_bytes = size if retained.original_bytes is None else retained.original_bytes
    original_sha256 = sha256 if retained.original_sha256 is None else retained.original_sha256
    if original_bytes < size:
        raise RecipeError("evidence retained file original size is invalid")
    if not isinstance(original_sha256, str) or len(original_sha256) != 64:
        raise RecipeError("evidence retained file original digest is invalid")
    return {
        "role": retained.role,
        "path": path,
        "bytes": size,
        "sha256": sha256,
        "original_bytes": original_bytes,
        "original_sha256": original_sha256,
        "truncated": original_bytes > size,
    }


def _standard_files(admitted: AdmittedInput) -> dict[str, RetainedFile]:
    records = admitted.records
    profile = records["profile"]
    bundle = records["bundle"]
    calibrations = records["calibrations"]
    assert isinstance(profile, dict) and isinstance(bundle, dict) and isinstance(calibrations, list)
    result = {
        "profile.json": RetainedFile("profile", canonical(profile)),
        "bundle-manifest.json": RetainedFile("bundle_manifest", canonical(bundle)),
        "source/align-llm/manifest.json": RetainedFile(
            "align_source_manifest", admitted.align_source.manifest_raw,
        ),
        "source/align-llm/commit": RetainedFile(
            "align_source_commit", admitted.align_source.commit_raw,
        ),
        "source/ggml/manifest.json": RetainedFile(
            "ggml_source_manifest", admitted.ggml_source.manifest_raw,
        ),
        "source/ggml/commit": RetainedFile(
            "ggml_source_commit", admitted.ggml_source.commit_raw,
        ),
    }
    models = profile["models"]
    assert isinstance(models, list)
    for model, calibration in zip(models, calibrations, strict=True):
        assert isinstance(model, dict) and isinstance(calibration, dict)
        result[str(model["calibration_path"])] = RetainedFile(
            "calibration", canonical(calibration),
        )
    for source, role in (
        (admitted.align_source, "align_source_blob"),
        (admitted.ggml_source, "ggml_source_blob"),
    ):
        kind = str(source.manifest["source_kind"])
        for sha256, data in source.blobs.items():
            result[f"source/{kind}/blobs/{sha256}"] = RetainedFile(role, data)
    bundle_manifest = profile["bundle_manifest"]
    assert isinstance(bundle_manifest, dict)
    bundle_parent = pathlib.PurePosixPath(str(bundle_manifest["path"])).parent
    artifacts = bundle["artifacts"]
    assert isinstance(artifacts, list)
    for artifact in artifacts:
        assert isinstance(artifact, dict)
        sha256 = str(artifact["sha256"])
        source_path = (bundle_parent / str(artifact["path"])).as_posix()
        data = admitted.read_retained(source_path, MAX_BUNDLE_ARTIFACT_BYTES)
        destination = f"artifacts/{sha256}"
        candidate = RetainedFile("backend_artifact", data)
        if destination in result and result[destination] != candidate:
            raise RecipeError("evidence content-addressed input collision")
        result[destination] = candidate
    return result


def prepare(
    admitted: AdmittedInput, produced: Mapping[str, RetainedFile],
) -> PreparedPublication:
    """Build the exact retained byte map and file rows before staging exists."""
    retained = _standard_files(admitted)
    for path, item in produced.items():
        retained_path(path, "produced evidence path")
        if path in retained:
            raise RecipeError("produced evidence path collides with an input")
        retained[path] = item
    retained_paths = set(retained)
    for path in retained_paths:
        parents = pathlib.PurePosixPath(path).parents
        if any(parent.as_posix() in retained_paths for parent in parents):
            raise RecipeError("evidence file projection contains a path collision")
    if len(retained) + 1 > MAX_EVIDENCE_FILES:
        raise RecipeError("evidence file projection exceeds its bound")
    rows = [_row(path, retained[path]) for path in sorted(retained, key=lambda item: item.encode())]
    retained_total = sum(int(row["bytes"]) for row in rows)
    if retained_total > MAX_BUNDLE_ARTIFACT_BYTES:
        raise RecipeError("evidence retained-data projection exceeds its bound")
    return PreparedPublication(
        content={path: retained[path].data for path in retained},
        rows=rows,
    )


def _write_exclusive(root: pathlib.Path, relative: str, data: bytes) -> None:
    target = root / relative
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) \
        | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(target, flags, 0o600)
        view = memoryview(data)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise RecipeError("evidence file write made no progress")
            written += count
        os.fsync(descriptor)
    except OSError as exc:
        raise RecipeError(f"evidence file cannot be written: {relative}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def publish(
    admitted: AdmittedInput,
    evidence: dict[str, object],
    prepared: PreparedPublication,
    output: pathlib.Path,
) -> None:
    """Publish one canonical evidence directory only after complete replay and input recheck."""
    evidence_raw = canonical(evidence)
    if len(evidence_raw) > MAX_EVIDENCE_RESULT_BYTES:
        raise RecipeError("evidence result exceeds its bound")
    if len(prepared.content) + 1 > MAX_EVIDENCE_FILES:
        raise RecipeError("evidence file projection exceeds its bound")
    if sum(len(data) for data in prepared.content.values()) + len(evidence_raw) \
            > MAX_BUNDLE_ARTIFACT_BYTES:
        raise RecipeError("evidence directory projection exceeds its bound")
    records = validate_evidence_records(
        runtime_option_raw=admitted.runtime_option_raw,
        align_source_raw=admitted.align_source.manifest_raw,
        ggml_source_raw=admitted.ggml_source.manifest_raw,
        bundle_raw=admitted.bundle_raw,
        calibration_raws=list(admitted.calibration_raws),
        profile_raw=admitted.profile_raw,
        evidence_raw=evidence_raw,
    )
    roles = expected_directory_roles(records)
    if set(roles) != set(prepared.content):
        raise RecipeError("evidence prepared file closure does not match result")
    row_map = {str(row["path"]): row for row in prepared.rows}
    evidence_rows = evidence["files"]
    if not isinstance(evidence_rows, list) or evidence_rows != prepared.rows:
        raise RecipeError("evidence file rows do not match prepared content")
    for path, data in prepared.content.items():
        row = row_map[path]
        if row["role"] != roles[path] or row["bytes"] != len(data) \
                or row["sha256"] != hashlib.sha256(data).hexdigest():
            raise RecipeError("evidence prepared content identity does not match result")

    destination = output.absolute()
    parent = destination.parent
    try:
        parent_metadata = parent.stat(follow_symlinks=False)
    except OSError as exc:
        raise RecipeError("evidence output parent is absent") from exc
    if not stat.S_ISDIR(parent_metadata.st_mode) or destination.exists() or destination.is_symlink():
        raise RecipeError("evidence output must be a new path beneath a real directory")
    try:
        admitted_root = admitted.root.resolve(strict=True)
        resolved_parent = parent.resolve(strict=True)
    except OSError as exc:
        raise RecipeError("evidence output or input root cannot be resolved") from exc
    if resolved_parent == admitted_root or admitted_root in resolved_parent.parents:
        raise RecipeError("evidence output must be outside the qualification input root")

    try:
        stage = pathlib.Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=parent))
    except OSError as exc:
        raise RecipeError("evidence staging directory cannot be created") from exc
    try:
        for path in sorted(prepared.content, key=lambda item: item.encode()):
            _write_exclusive(stage, path, prepared.content[path])
        _write_exclusive(stage, "result.json", evidence_raw)
        admitted.recheck()
        replayed = replay_evidence_directory(stage)
        if canonical(replayed["evidence"]) != evidence_raw:
            raise RecipeError("staged evidence replay changed the result")
        rename_noreplace(stage, destination)
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise
