#!/usr/bin/env python3
"""Retained-root input admission for the G1 GPU qualifier."""

from __future__ import annotations

import dataclasses
import errno
import hashlib
import os
import pathlib
import stat
from collections.abc import Iterator
from contextlib import contextmanager

from gpu_backend_recipe import (
    MAX_BUNDLE_ARTIFACT_BYTES,
    MAX_RETAINED_DATA_BYTES,
    MAX_SOURCE_MANIFEST_BYTES,
    RecipeError,
    canonical,
    parse_canonical,
    retained_path,
    validate_captured_source,
    validate_source_manifest,
)
from gpu_qualification_records import (
    MAX_BUNDLE_BYTES,
    MAX_CALIBRATION_BYTES,
    MAX_PROFILE_BYTES,
    parse_record,
    validate_profile_records,
)


READ_CHUNK = 1024 * 1024
STABLE_FIELDS = (
    "st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns",
)


@dataclasses.dataclass(frozen=True)
class FileIdentity:
    bytes: int
    sha256: str
    stat_values: tuple[int, ...]


@dataclasses.dataclass(frozen=True)
class SourceInput:
    manifest_raw: bytes
    manifest: dict[str, object]
    commit_raw: bytes
    blobs: dict[str, bytes]
    snapshot_sha256: str


@dataclasses.dataclass(frozen=True)
class AdmittedInput:
    root: pathlib.Path
    profile_name: str
    records: dict[str, object]
    profile_raw: bytes
    bundle_raw: bytes
    calibration_raws: tuple[bytes, bytes]
    runtime_option_raw: bytes
    align_source: SourceInput
    ggml_source: SourceInput
    files: dict[str, FileIdentity]

    def read_retained(self, relative: str, maximum: int) -> bytes:
        root = _RetainedRoot(self.root)
        try:
            data = root.read(relative, maximum)
            if root.identities.get(relative) != self.files.get(relative):
                raise RecipeError("qualification input changed after admission")
            return data
        finally:
            root.close()

    def recheck(self) -> None:
        current = admit(self.root / self.profile_name)
        if current.files != self.files:
            raise RecipeError("qualification input changed after admission")


class _RetainedRoot:
    def __init__(self, root: pathlib.Path) -> None:
        self.path = root.absolute()
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) \
            | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            self.fd = os.open(self.path, flags)
            metadata = os.fstat(self.fd)
        except OSError as exc:
            if "self.fd" in vars(self):
                os.close(self.fd)
            raise RecipeError("qualification input root is not a retained directory") from exc
        if not stat.S_ISDIR(metadata.st_mode):
            os.close(self.fd)
            raise RecipeError("qualification input root is not a retained directory")
        self.identities: dict[str, FileIdentity] = {}

    def close(self) -> None:
        os.close(self.fd)

    @contextmanager
    def directory(self, relative: str) -> Iterator[int]:
        components = retained_path(relative, "qualification directory").split("/")
        descriptor: int | None = None
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) \
            | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.dup(self.fd)
            for component in components:
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
                if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    raise RecipeError("qualification path component is not a directory")
            yield descriptor
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise RecipeError("qualification path contains a symlink component") from exc
            raise RecipeError("qualification directory is absent") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)

    @contextmanager
    def file(self, relative: str, maximum: int | None) -> Iterator[tuple[int, os.stat_result]]:
        normalized = retained_path(relative, "qualification file")
        path = pathlib.PurePosixPath(normalized)
        parent = path.parent.as_posix()
        manager = self.directory(parent) if parent != "." else _borrowed_fd(self.fd)
        with manager as parent_fd:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(path.name, flags, dir_fd=parent_fd)
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise RecipeError(f"qualification file is a symlink: {normalized}") from exc
                raise RecipeError(f"qualification file is absent: {normalized}") from exc
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                    raise RecipeError(
                        f"qualification file is not single-link regular: {normalized}",
                    )
                if maximum is not None and before.st_size > maximum:
                    raise RecipeError(f"qualification file exceeds its bound: {normalized}")
                yield descriptor, before
            finally:
                os.close(descriptor)

    def read(self, relative: str, maximum: int) -> bytes:
        with self.file(relative, maximum) as (descriptor, before):
            try:
                chunks: list[bytes] = []
                total = 0
                digest = hashlib.sha256()
                while True:
                    chunk = os.read(descriptor, min(READ_CHUNK, maximum - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > maximum:
                        raise RecipeError(f"qualification file exceeds its bound: {relative}")
                    chunks.append(chunk)
                    digest.update(chunk)
                self._finish(relative, descriptor, before, total, digest.hexdigest())
                return b"".join(chunks)
            except OSError as exc:
                raise RecipeError(f"qualification file cannot be read: {relative}") from exc

    def digest(self, relative: str, maximum: int | None = None) -> str:
        with self.file(relative, maximum) as (descriptor, before):
            try:
                total = 0
                digest = hashlib.sha256()
                while True:
                    chunk = os.read(descriptor, READ_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if maximum is not None and total > maximum:
                        raise RecipeError(f"qualification file exceeds its bound: {relative}")
                    digest.update(chunk)
                value = digest.hexdigest()
                self._finish(relative, descriptor, before, total, value)
                return value
            except OSError as exc:
                raise RecipeError(f"qualification file cannot be read: {relative}") from exc

    def entries(self, relative: str) -> set[str]:
        with self.directory(relative) as descriptor:
            try:
                return set(os.listdir(descriptor))
            except OSError as exc:
                raise RecipeError("qualification directory cannot be enumerated") from exc

    def _finish(
        self, relative: str, descriptor: int, before: os.stat_result, total: int, digest: str,
    ) -> None:
        after = os.fstat(descriptor)
        before_values = tuple(int(getattr(before, field)) for field in STABLE_FIELDS)
        after_values = tuple(int(getattr(after, field)) for field in STABLE_FIELDS)
        if total != before.st_size or before_values != after_values:
            raise RecipeError(f"qualification file changed while it was read: {relative}")
        identity = FileIdentity(total, digest, after_values)
        previous = self.identities.setdefault(relative, identity)
        if previous != identity:
            raise RecipeError(f"qualification file changed between reads: {relative}")


@contextmanager
def _borrowed_fd(descriptor: int) -> Iterator[int]:
    yield descriptor


def _source_input(root: _RetainedRoot, kind: str) -> SourceInput:
    prefix = f"source/{kind}"
    manifest_raw = root.read(f"{prefix}/manifest.json", MAX_SOURCE_MANIFEST_BYTES)
    manifest = validate_source_manifest(parse_canonical(manifest_raw, MAX_SOURCE_MANIFEST_BYTES))
    if manifest["source_kind"] != kind:
        raise RecipeError("qualification source kind does not match its directory")
    rows = manifest["files"]
    assert isinstance(rows, list)
    expected_blobs = {str(row["sha256"]) for row in rows}
    if root.entries(f"{prefix}/blobs") != expected_blobs:
        raise RecipeError("qualification source blob closure is invalid")
    commit_raw = root.read(f"{prefix}/commit", MAX_RETAINED_DATA_BYTES - len(manifest_raw))
    blobs: dict[str, bytes] = {}
    retained = len(manifest_raw) + len(commit_raw)
    for sha256 in sorted(expected_blobs):
        remaining = MAX_RETAINED_DATA_BYTES - retained
        data = root.read(f"{prefix}/blobs/{sha256}", remaining)
        retained += len(data)
        blobs[sha256] = data
    validate_captured_source(manifest, manifest_raw, commit_raw, blobs, kind)
    snapshot = hashlib.sha256()
    snapshot.update(b"GPU_SOURCE_SNAPSHOT\0")
    snapshot.update(kind.encode("ascii"))
    snapshot.update(b"\0")
    snapshot.update(manifest_raw)
    for row in rows:
        assert isinstance(row, dict)
        snapshot.update(bytes.fromhex(str(row["sha256"])))
    return SourceInput(manifest_raw, manifest, commit_raw, blobs, snapshot.hexdigest())


def _preliminary_paths(profile: dict[str, object]) -> tuple[str, tuple[str, str]]:
    try:
        bundle = profile["bundle_manifest"]
        models = profile["models"]
        if not isinstance(bundle, dict) or not isinstance(models, list) or len(models) != 2:
            raise RecipeError("qualification profile cannot select its records")
        bundle_path = retained_path(bundle["path"], "profile bundle path")
        calibrations = tuple(
            retained_path(model["calibration_path"], "profile calibration path")
            for model in models if isinstance(model, dict)
        )
    except (KeyError, TypeError) as exc:
        raise RecipeError("qualification profile cannot select its records") from exc
    if len(calibrations) != 2:
        raise RecipeError("qualification profile cannot select its calibrations")
    return bundle_path, (calibrations[0], calibrations[1])


def _runtime_option(profile: dict[str, object]) -> bytes:
    try:
        options = profile["runtime_options"]
        if not isinstance(options, list) or len(options) != 1 or not isinstance(options[0], dict):
            raise RecipeError("qualification profile runtime option is invalid")
        return canonical({key: value for key, value in options[0].items() if key != "option_id"})
    except (KeyError, TypeError) as exc:
        raise RecipeError("qualification profile runtime option is invalid") from exc


def admit(profile_path: pathlib.Path) -> AdmittedInput:
    """Validate one complete profile-root package before any qualifier side effect."""
    absolute = profile_path.absolute()
    if absolute.name in {"", ".", ".."}:
        raise RecipeError("qualification profile path is invalid")
    root = _RetainedRoot(absolute.parent)
    try:
        profile_raw = root.read(absolute.name, MAX_PROFILE_BYTES)
        preliminary = parse_record(profile_raw, MAX_PROFILE_BYTES)
        bundle_path, calibration_paths = _preliminary_paths(preliminary)
        bundle_raw = root.read(bundle_path, MAX_BUNDLE_BYTES)
        calibration_raws = tuple(
            root.read(path, MAX_CALIBRATION_BYTES) for path in calibration_paths
        )
        runtime_option_raw = _runtime_option(preliminary)
        align_source = _source_input(root, "align-llm")
        ggml_source = _source_input(root, "ggml")
        records = validate_profile_records(
            runtime_option_raw=runtime_option_raw,
            align_source_raw=align_source.manifest_raw,
            ggml_source_raw=ggml_source.manifest_raw,
            bundle_raw=bundle_raw,
            calibration_raws=list(calibration_raws),
            profile_raw=profile_raw,
        )
        profile = records["profile"]
        bundle = records["bundle"]
        assert isinstance(profile, dict) and isinstance(bundle, dict)
        if root.digest(bundle_path, MAX_BUNDLE_BYTES) != profile["bundle_manifest"]["sha256"]:
            raise RecipeError("qualification bundle path digest does not match")
        if hashlib.sha256(align_source.manifest_raw).hexdigest() \
                != profile["source"]["manifest_sha256"]:
            raise RecipeError("qualification align source path digest does not match")
        models = profile["models"]
        assert isinstance(models, list)
        for ordinal, model in enumerate(models):
            assert isinstance(model, dict)
            for path_key, digest_key in (
                ("model_path", "model_sha256"),
                ("pack_path", "pack_sha256"),
                ("geometry_path", "geometry_sha256"),
                ("calibration_path", "calibration_sha256"),
            ):
                if root.digest(str(model[path_key])) != model[digest_key]:
                    raise RecipeError(
                        f"qualification model {ordinal} {path_key} digest does not match",
                    )
        bundle_parent = pathlib.PurePosixPath(bundle_path).parent
        artifacts = bundle["artifacts"]
        assert isinstance(artifacts, list)
        for ordinal, artifact in enumerate(artifacts):
            assert isinstance(artifact, dict)
            artifact_path = (bundle_parent / str(artifact["path"])).as_posix()
            if root.digest(artifact_path, MAX_BUNDLE_ARTIFACT_BYTES) != artifact["sha256"]:
                raise RecipeError(f"qualification bundle artifact {ordinal} digest does not match")
        return AdmittedInput(
            root=root.path,
            profile_name=absolute.name,
            records=records,
            profile_raw=profile_raw,
            bundle_raw=bundle_raw,
            calibration_raws=(calibration_raws[0], calibration_raws[1]),
            runtime_option_raw=runtime_option_raw,
            align_source=align_source,
            ggml_source=ggml_source,
            files=dict(root.identities),
        )
    finally:
        root.close()
