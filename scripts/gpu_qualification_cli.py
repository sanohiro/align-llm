#!/usr/bin/env python3
"""CLI admission and invocation lifetime for the G1 GPU qualifier."""

from __future__ import annotations

import dataclasses
import pathlib
import shutil
import stat
import tempfile
from collections.abc import Sequence

from gpu_backend_recipe import RecipeError
from gpu_qualification_input import AdmittedInput, admit
from gpu_qualification_publish import validate_output
from gpu_qualification_source import MaterializedSources, materialize


@dataclasses.dataclass(frozen=True)
class Arguments:
    profile: pathlib.Path
    suite: str
    output: pathlib.Path


@dataclasses.dataclass(frozen=True)
class Invocation:
    arguments: Arguments
    admitted: AdmittedInput
    root: pathlib.Path
    home: pathlib.Path
    temporary: pathlib.Path
    work: pathlib.Path
    sources: MaterializedSources

    def cleanup(self) -> None:
        try:
            shutil.rmtree(self.root)
        except FileNotFoundError:
            pass


def parse_arguments(arguments: Sequence[str]) -> Arguments:
    values: dict[str, str] = {}
    ordinal = 0
    while ordinal < len(arguments):
        flag = arguments[ordinal]
        if flag not in {"--profile", "--suite", "--output"}:
            raise RecipeError("gpu qualifier argument is unknown")
        if flag in values:
            raise RecipeError("gpu qualifier argument is duplicated")
        ordinal += 1
        if ordinal >= len(arguments) or arguments[ordinal].startswith("--"):
            raise RecipeError("gpu qualifier argument has no value")
        value = arguments[ordinal]
        if not value or "\x00" in value:
            raise RecipeError("gpu qualifier argument value is invalid")
        values[flag] = value
        ordinal += 1
    if set(values) != {"--profile", "--suite", "--output"}:
        raise RecipeError("gpu qualifier arguments are incomplete")
    if values["--suite"] != "generation":
        raise RecipeError("gpu qualifier suite is unsupported")
    return Arguments(
        pathlib.Path(values["--profile"]),
        values["--suite"],
        pathlib.Path(values["--output"]),
    )


def _private_child(parent: pathlib.Path, name: str) -> pathlib.Path:
    child = parent / name
    child.mkdir(mode=0o700)
    metadata = child.stat(follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode & 0o077:
        raise RecipeError("gpu qualifier invocation child is not private")
    return child


def open_invocation(arguments: Arguments) -> Invocation:
    """Admit all retained input before creating one private, output-sibling invocation root."""
    admitted = admit(arguments.profile.absolute())
    destination, parent = validate_output(admitted, arguments.output)
    root: pathlib.Path | None = None
    try:
        root = pathlib.Path(tempfile.mkdtemp(prefix=f".{destination.name}.invoke-", dir=parent))
        root.chmod(0o700)
        home = _private_child(root, "home")
        temporary = _private_child(root, "tmp")
        work = _private_child(root, "work")
        sources = materialize(admitted, work)
        return Invocation(arguments, admitted, root, home, temporary, work, sources)
    except BaseException:
        if root is not None and root.exists() and not root.is_symlink():
            shutil.rmtree(root)
        raise
