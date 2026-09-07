#!/usr/bin/env python3
"""Private backend-bundle staging for the G1 GPU qualifier."""

from __future__ import annotations

import dataclasses
import hashlib
import os
import pathlib
import shutil
import stat

from gpu_backend_recipe import MAX_BUNDLE_ARTIFACT_BYTES, RecipeError, retained_path
from gpu_qualification_input import AdmittedInput


@dataclasses.dataclass(frozen=True)
class StagedBackend:
    root: pathlib.Path
    manifest: pathlib.Path
    artifacts: tuple[pathlib.Path, ...]

    def cleanup(self) -> None:
        try:
            shutil.rmtree(self.root)
        except FileNotFoundError:
            pass


def _private_directory(path: pathlib.Path, label: str) -> pathlib.Path:
    if not path.is_absolute():
        raise RecipeError(f"{label} is not absolute")
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise RecipeError(f"{label} cannot be inspected") from exc
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode & 0o077:
        raise RecipeError(f"{label} is not a private directory")
    return path.resolve(strict=True)


def _write(root: pathlib.Path, relative: str, data: bytes) -> pathlib.Path:
    normalized = retained_path(relative, "staged backend path")
    target = root / normalized
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
                raise RecipeError("staged backend write made no progress")
            written += count
        os.fsync(descriptor)
    except OSError as exc:
        raise RecipeError(f"staged backend file cannot be written: {relative}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return target


def _verify(path: pathlib.Path, expected_bytes: int, expected_sha256: str) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 \
                or before.st_size != expected_bytes or before.st_size > MAX_BUNDLE_ARTIFACT_BYTES:
            raise RecipeError("staged backend file identity is invalid")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise RecipeError("staged backend file cannot be read") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    if total != expected_bytes or digest.hexdigest() != expected_sha256 or any(
        getattr(before, field) != getattr(after, field) for field in fields
    ):
        raise RecipeError("staged backend file changed or has the wrong content")


def stage(admitted: AdmittedInput, parent: pathlib.Path) -> StagedBackend:
    """Copy the admitted manifest and artifacts into a new private bundle tree."""
    private_parent = _private_directory(parent, "backend staging parent")
    root = private_parent / "backend"
    if root.exists() or root.is_symlink():
        raise RecipeError("backend staging output is occupied")
    try:
        root.mkdir(mode=0o700)
        manifest = _write(root, "manifest.json", admitted.bundle_raw)
        _verify(
            manifest,
            len(admitted.bundle_raw),
            hashlib.sha256(admitted.bundle_raw).hexdigest(),
        )
        profile = admitted.records["profile"]
        bundle = admitted.records["bundle"]
        assert isinstance(profile, dict) and isinstance(bundle, dict)
        manifest_ref = profile["bundle_manifest"]
        artifacts = bundle["artifacts"]
        assert isinstance(manifest_ref, dict) and isinstance(artifacts, list)
        input_parent = pathlib.PurePosixPath(str(manifest_ref["path"])).parent
        staged: list[pathlib.Path] = []
        for artifact in artifacts:
            assert isinstance(artifact, dict)
            relative = retained_path(artifact["path"], "backend artifact path")
            source = (input_parent / relative).as_posix()
            data = admitted.read_retained(source, MAX_BUNDLE_ARTIFACT_BYTES)
            target = _write(root, relative, data)
            _verify(target, int(artifact["bytes"]), str(artifact["sha256"]))
            staged.append(target)
        admitted.recheck()
        return StagedBackend(root, manifest, tuple(staged))
    except BaseException:
        if root.exists() and not root.is_symlink():
            shutil.rmtree(root)
        raise
