#!/usr/bin/env python3
"""Private source-tree materialization for the G1 GPU qualifier."""

from __future__ import annotations

import dataclasses
import hashlib
import os
import pathlib
import shutil
import stat

from gpu_backend_recipe import RecipeError, materialize_source
from gpu_qualification_input import AdmittedInput, SourceInput


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
    rows = source.manifest["files"]
    assert isinstance(rows, list)
    expected_files = {str(row["path"]) for row in rows if isinstance(row, dict)}
    actual_files: set[str] = set()
    for root, directories, files in os.walk(destination, followlinks=False):
        root_path = pathlib.Path(root)
        for name in [*directories, *files]:
            path = root_path / name
            if path.is_dir() and not path.is_symlink():
                continue
            actual_files.add(path.relative_to(destination).as_posix())
    if actual_files != expected_files:
        raise RecipeError("materialized source file closure is invalid")

    for ordinal, row in enumerate(rows):
        assert isinstance(row, dict)
        relative = str(row["path"])
        target = destination / relative
        try:
            metadata = target.lstat()
            if row["mode"] == "120000":
                if not stat.S_ISLNK(metadata.st_mode):
                    raise RecipeError(
                        f"materialized source mode does not match row {ordinal}",
                    )
                data = os.readlink(os.fsencode(target))
            else:
                if not stat.S_ISREG(metadata.st_mode):
                    raise RecipeError(
                        f"materialized source mode does not match row {ordinal}",
                    )
                executable = bool(metadata.st_mode & 0o111)
                if executable != (row["mode"] == "100755"):
                    raise RecipeError(
                        f"materialized source executable mode does not match row {ordinal}",
                    )
                data = target.read_bytes()
        except OSError as exc:
            raise RecipeError(f"materialized source cannot be read at row {ordinal}") from exc
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise RecipeError(f"materialized source content does not match row {ordinal}")


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
