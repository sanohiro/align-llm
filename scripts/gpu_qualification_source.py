#!/usr/bin/env python3
"""Private source-tree materialization for the G1 GPU qualifier."""

from __future__ import annotations

import dataclasses
import hashlib
import os
import pathlib
import shutil
import stat

from gpu_backend_recipe import RecipeError, materialize_source, single_link_file_at, stable_directory
from gpu_qualification_input import AdmittedInput, SourceInput, STABLE_FIELDS


@dataclasses.dataclass(frozen=True)
class MaterializedSources:
    root: pathlib.Path
    align_llm: pathlib.Path
    ggml: pathlib.Path

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


def _verify_tree(source: SourceInput, destination: pathlib.Path) -> None:
    rows = {row["path"]: row for row in source.manifest["files"]}
    expected_directories = {parent.as_posix() for name in rows
                            for parent in pathlib.PurePosixPath(name).parents
                            if parent.as_posix() != "."}
    seen_files: set[str] = set()
    seen_directories: set[str] = set()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK

    def walk(descriptor: int, prefix: str) -> None:
        before = os.fstat(descriptor)
        for name in os.listdir(descriptor):
            relative = prefix + name
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                if relative not in expected_directories:
                    raise RecipeError("materialized source directory closure is invalid")
                child = os.open(name, flags, dir_fd=descriptor)
                try:
                    opened = os.fstat(child)
                    if any(getattr(opened, field) != getattr(metadata, field) for field in STABLE_FIELDS):
                        raise RecipeError("materialized source directory changed")
                    seen_directories.add(relative)
                    walk(child, relative + "/")
                finally:
                    os.close(child)
                continue
            row = rows.get(relative)
            if row is None:
                raise RecipeError("materialized source file closure is invalid")
            if row["mode"] == "120000":
                if not stat.S_ISLNK(metadata.st_mode):
                    raise RecipeError("materialized source symlink mode differs")
                data = os.readlink(os.fsencode(name), dir_fd=descriptor)
            else:
                if not stat.S_ISREG(metadata.st_mode) or bool(metadata.st_mode & 0o111) != (row["mode"] == "100755"):
                    raise RecipeError("materialized source executable mode differs")
                data = single_link_file_at(descriptor, name, "materialized source file", row["bytes"])
            after = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if any(getattr(after, field) != getattr(metadata, field) for field in STABLE_FIELDS):
                raise RecipeError("materialized source file changed")
            if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise RecipeError("materialized source content differs")
            seen_files.add(relative)
        if not stable_directory(before, os.fstat(descriptor)):
            raise RecipeError("materialized source directory changed")

    try:
        descriptor = os.open(destination, flags)
        try:
            before = os.fstat(descriptor)
            walk(descriptor, "")
            if not stable_directory(before, destination.lstat()):
                raise RecipeError("materialized source root changed")
        finally:
            os.close(descriptor)
    except OSError as error:
        raise RecipeError("materialized source cannot be read") from error
    if seen_files != set(rows) or seen_directories != expected_directories:
        raise RecipeError("materialized source file closure is invalid")


def materialize(admitted: AdmittedInput, parent: pathlib.Path) -> MaterializedSources:
    """Rebuild both admitted source closures beneath one new private directory."""
    private_parent = _private_directory(parent, "source materialization parent")
    root = private_parent / "source"
    if root.exists() or root.is_symlink():
        raise RecipeError("source materialization output is occupied")
    try:
        root.mkdir(mode=0o700)
        align_llm = root / "align-llm"
        ggml = root / "ggml"
        materialize_source(admitted.align_source.manifest, admitted.align_source.blobs, align_llm)
        materialize_source(admitted.ggml_source.manifest, admitted.ggml_source.blobs, ggml)
        _verify_tree(admitted.align_source, align_llm)
        _verify_tree(admitted.ggml_source, ggml)
        admitted.recheck()
        return MaterializedSources(root, align_llm, ggml)
    except BaseException:
        if root.exists() and not root.is_symlink():
            shutil.rmtree(root)
        raise
