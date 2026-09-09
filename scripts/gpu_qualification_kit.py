#!/usr/bin/env python3
"""Publish a complete locally assembled qualifier input only after ordinary admission."""

from __future__ import annotations

import dataclasses
import os
import pathlib
import shutil
import stat
import tempfile
from collections.abc import Mapping

from gpu_backend_recipe import RecipeError, rename_noreplace, retained_path, write_source_snapshot
from gpu_qualification_input import STABLE_FIELDS, admit
from gpu_qualification_records import MAX_PROFILE_BYTES, parse_record


COPY_CHUNK = 1024 * 1024


@dataclasses.dataclass(frozen=True)
class CapturedSource:
    manifest: dict[str, object]
    manifest_raw: bytes
    commit_raw: bytes
    blobs: dict[str, bytes]


def _identity(metadata: os.stat_result) -> tuple[int, ...]:
    return tuple(getattr(metadata, field) for field in STABLE_FIELDS)


def _copy(source: pathlib.Path, destination: pathlib.Path) -> None:
    if not source.is_absolute():
        raise RecipeError("kit file input must be absolute")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) \
        | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(source, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise RecipeError("kit input is not a single-link regular file")
        total = 0
        with destination.open("xb") as output:
            while True:
                data = os.read(descriptor, min(COPY_CHUNK, before.st_size - total + 1))
                if not data:
                    break
                total += len(data)
                if total > before.st_size:
                    raise RecipeError("kit input grew while being copied")
                output.write(data)
        if total != before.st_size or _identity(os.fstat(descriptor)) != _identity(before) \
                or _identity(source.stat(follow_symlinks=False)) != _identity(before):
            raise RecipeError("kit input changed while being copied")
    finally:
        os.close(descriptor)


def assemble_kit(
    *, output: pathlib.Path, profile_raw: bytes, sources: tuple[CapturedSource, CapturedSource],
    files: Mapping[str, bytes | pathlib.Path],
) -> pathlib.Path:
    parse_record(profile_raw, MAX_PROFILE_BYTES)
    if len(sources) != 2 or [item.manifest.get("source_kind") for item in sources] != ["align-llm", "ggml"]:
        raise RecipeError("kit requires align-llm and ggml source captures in that order")
    names = set()
    for name, value in files.items():
        retained_path(name, "kit input path")
        parts = pathlib.PurePosixPath(name).parts
        if parts[0] in ("profile.json", "source") or not isinstance(value, (bytes, pathlib.Path)):
            raise RecipeError("kit input path is reserved or its value is invalid")
        names.add(name)
    for name in names:
        if any(parent.as_posix() in names for parent in pathlib.PurePosixPath(name).parents):
            raise RecipeError("kit input paths have a file/directory prefix collision")
    if not output.is_absolute() or not output.name or output.exists() or output.is_symlink():
        raise RecipeError("kit output must be a new absolute path")
    parent = output.parent
    if not stat.S_ISDIR(parent.stat(follow_symlinks=False).st_mode):
        raise RecipeError("kit output parent must be a real directory")
    destination = parent.resolve(strict=True) / output.name
    stage = pathlib.Path(tempfile.mkdtemp(prefix=f".{output.name}.kit-", dir=destination.parent))
    try:
        written = {"profile.json"}
        (stage / "source").mkdir(mode=0o700)
        for captured in sources:
            kind = str(captured.manifest["source_kind"])
            prefix = f"source/{kind}"
            write_source_snapshot(stage / prefix, captured.manifest, captured.manifest_raw,
                                  captured.commit_raw, captured.blobs, kind)
            written.update((f"{prefix}/manifest.json", f"{prefix}/commit"))
            written.update(f"{prefix}/blobs/{sha256}" for sha256 in captured.blobs)
        with (stage / "profile.json").open("xb") as profile:
            profile.write(profile_raw)
        for name in sorted(names):
            target = stage / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            value = files[name]
            if isinstance(value, bytes):
                with target.open("xb") as stream:
                    stream.write(value)
            else:
                _copy(value, target)
            written.add(name)
        admitted = admit(stage / "profile.json")
        if set(admitted.files) != written:
            raise RecipeError("kit file mapping does not match the complete referenced closure")
        rename_noreplace(stage, destination)
        return destination / "profile.json"
    finally:
        if stage.exists():
            shutil.rmtree(stage)
