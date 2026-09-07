#!/usr/bin/env python3
"""Construct the G1 compiler/runtime/shim/candidate/reference preparation sequence."""

from __future__ import annotations

import pathlib
import re
import stat

from gpu_backend_recipe import RecipeError
from gpu_qualification_run import PreparationCommand
from gpu_qualifier_process import _single_link_sha256


def _input(name: str, path: pathlib.Path) -> str:
    token = f"<{name}>:sha256:{_single_link_sha256(path, name)}"
    return token


def commands(
    *,
    work: pathlib.Path,
    compiler: pathlib.Path,
    runtime: pathlib.Path,
    copier: pathlib.Path,
    driver: pathlib.Path,
    reference_driver: pathlib.Path,
    entry: pathlib.Path,
    shim_source: pathlib.Path,
    platform: str,
    align_revision: str,
    source_commit: str,
    ggml_include: pathlib.Path | None = None,
    backend_library: pathlib.Path | None = None,
) -> tuple[PreparationCommand, ...]:
    """Bind admitted build inputs; the driver supplies its verified SDK and host link inputs.

    All paths are explicit. Real qualification supplies both private ggml directories; the
    reference driver supplies the separately built CPU backend; the model-free owner supplies
    the checked-in stub source and neither directory. There is no
    filesystem probe that changes the selected source or backend.
    """
    if platform not in {"macos", "linux", "wsl2"}:
        raise RecipeError("preparation build platform is unsupported")
    if any(re.fullmatch(r"[0-9a-f]{40}", value) is None
           for value in (align_revision, source_commit)):
        raise RecipeError("preparation build revision is invalid")
    if not work.is_absolute():
        raise RecipeError("preparation build root is not absolute")
    metadata = work.stat(follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode & 0o077:
        raise RecipeError("preparation build root is not private")
    if entry.suffix != ".align" or entry.stem in {"alignc", "cpu-reference"}:
        raise RecipeError("preparation entry filename is invalid")
    if (ggml_include is None) != (backend_library is None):
        raise RecipeError("preparation requires both ggml include and library inputs")
    for directory in (ggml_include, backend_library):
        if directory is not None:
            resolved = directory.resolve(strict=True)
            if not directory.is_absolute() or not directory.is_dir() \
                    or work.resolve(strict=True) not in resolved.parents:
                raise RecipeError("preparation ggml directory is outside the private build root")

    inputs = dict((
        ("compiler-input", compiler), ("runtime-input", runtime), ("copy-tool", copier),
        ("c-driver", driver), ("reference-driver", reference_driver),
        ("entry-source", entry), ("shim-source", shim_source),
    ))
    tokens = {name: _input(name, path) for name, path in inputs.items()}
    suffix = "dylib" if platform == "macos" else "so"
    shim = work / f"libalign_ggml_shim.{suffix}"
    copied_compiler = work / "alignc"
    copied_runtime = work / "libalign_runtime.a"
    reference_work = work / "cpu-reference"
    candidate = work / entry.stem
    for output in (shim, copied_compiler, copied_runtime, reference_work, candidate):
        if output.exists() or output.is_symlink():
            raise RecipeError("preparation build output is occupied")

    result = []
    for key, output, name in (
        ("compiler-input", copied_compiler, "alignc"),
        ("runtime-input", copied_runtime, "align-runtime"),
    ):
        result.append(PreparationCommand(
            (str(copier), str(inputs[key]), output.name),
            (tokens["copy-tool"], tokens[key], output.name),
            {tokens["copy-tool"]: copier, tokens[key]: inputs[key]},
            output, name, align_revision,
        ))

    flags = [
        "-shared", "-fPIC", "-O2", "-ffp-contract=off", "-DALIGN_GGML_FP_CONTRACT_OFF=1",
        "-Wall", "-Wextra", "-Werror",
    ]
    if platform == "macos":
        flags.extend(("-Xlinker", "-install_name", "-Xlinker", f"@rpath/{shim.name}"))
    physical = [str(driver), *flags, str(shim_source), "-o", shim.name, "-lm"]
    logical = [tokens["c-driver"], *flags, tokens["shim-source"], "-o", shim.name, "-lm"]
    mappings = {tokens["c-driver"]: driver, tokens["shim-source"]: shim_source}
    if ggml_include is not None and backend_library is not None:
        physical.extend(("-I", str(ggml_include), "-L", str(backend_library),
                         "-Xlinker", "-rpath", "-Xlinker", str(backend_library),
                         "-lggml", "-lggml-base"))
        logical.extend(("-I", "<ggml-include>:owned", "-L", "<backend-library>:owned",
                        "-Xlinker", "-rpath", "-Xlinker", "<backend-library>:owned",
                        "-lggml", "-lggml-base"))
        mappings.update({"<ggml-include>:owned": ggml_include,
                         "<backend-library>:owned": backend_library})
    result.append(PreparationCommand(
        tuple(physical), tuple(logical), mappings, shim, "align-ggml-shim", source_commit,
    ))
    copied_token = tokens["compiler-input"].replace("<compiler-input>", "<align-compiler>")
    for cwd, name, selected_driver, driver_token in (
        (work, "align-llm", driver, tokens["c-driver"]),
        (reference_work, "cpu-reference", reference_driver, tokens["reference-driver"]),
    ):
        result.append(PreparationCommand(
            (str(copied_compiler), "build", str(entry), "--profile", "release", "--cc", str(selected_driver)),
            (copied_token, "build", tokens["entry-source"], "--profile", "release",
             "--cc", driver_token),
            {copied_token: copied_compiler, tokens["entry-source"]: entry,
             driver_token: selected_driver},
            cwd / entry.stem, name, source_commit, cwd,
        ))
    # This directory is the only construction side effect. Validate every path and output first;
    # the invocation owner removes it on failure together with all other private build products.
    reference_work.mkdir(mode=0o700)
    return tuple(result)
