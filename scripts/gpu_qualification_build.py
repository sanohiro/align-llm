#!/usr/bin/env python3
"""Construct the G1 compiler/runtime/shim/candidate/reference preparation sequence."""

from __future__ import annotations

import pathlib
import re
import stat
import dataclasses
from collections.abc import Callable

from gpu_backend_recipe import RecipeError
from gpu_qualification_run import PreparationCommand
from gpu_qualifier_process import ToolchainDirectory, ToolchainExecutable, _file_sha256


def _input(name: str, path: pathlib.Path | ToolchainExecutable) -> str:
    if isinstance(path, ToolchainExecutable):
        path.recheck(path.sha256)
        digest = path.sha256
    else:
        digest = _file_sha256(path, name)
    token = f"<{name}>:sha256:{digest}"
    return token


def compiler_materialization_command(
    *, work: pathlib.Path, compiler: pathlib.Path, python: ToolchainExecutable,
    helper: pathlib.Path, cc: ToolchainExecutable, linker: ToolchainExecutable,
    git: ToolchainExecutable, sdk: ToolchainDirectory, platform: str, align_revision: str,
    support_archives: dict[str, pathlib.Path] | None = None,
) -> PreparationCommand:
    if platform not in {"macos", "linux", "wsl2"} \
            or re.fullmatch(r"[0-9a-f]{40}", align_revision) is None:
        raise RecipeError("compiler materialization platform or revision is invalid")
    compiler_token = _input("compiler-input", compiler)
    helper_token = _input("compiler-materializer", helper)
    python_token = "<host-python>:sha256:" + python.sha256
    cc_token = "<host-cc>:sha256:" + cc.sha256
    linker_token = "<host-linker>:sha256:" + linker.sha256
    git_token = "<host-git>:sha256:" + git.sha256
    sdk_token = "<host-sdk>:sha256:" + sdk.sha256
    metadata_token = _input("host-sdk-metadata", sdk.metadata_path)
    digest = compiler_token.rsplit(":sha256:", 1)[1]
    physical = (str(python.path), "-B", str(helper), str(compiler), digest, str(cc.path),
                str(linker.path), str(sdk.path), str(sdk.metadata_path), str(work), platform, "alignc",
                str(git.path), align_revision)
    logical = (python_token, "-B", helper_token, compiler_token, digest, cc_token,
               linker_token, sdk_token, metadata_token, "<compiler-work>:owned", platform, "alignc",
               git_token, align_revision)
    mappings = {python_token: python, helper_token: helper, compiler_token: compiler,
                cc_token: cc, linker_token: linker, git_token: git, sdk_token: sdk,
                metadata_token: sdk.metadata_path, "<compiler-work>:owned": work}
    if support_archives:
        if set(support_archives) != {"crypto", "ssl", "zstd"}:
            raise RecipeError("compiler support archive set is incomplete")
        for name in ("crypto", "ssl", "zstd"):
            path = support_archives[name]
            token = _input("support-" + name, path)
            digest = token.rsplit(":sha256:", 1)[1]
            physical += (str(path), digest)
            logical += (token, digest)
            mappings[token] = path
    return PreparationCommand(
        physical, logical, mappings,
        work / "alignc", "alignc", align_revision, work, sdk, (cc, linker),
    )


def cpu_reference_command(
    *,
    work: pathlib.Path,
    output: pathlib.Path,
    compiler: pathlib.Path,
    entry: pathlib.Path,
    ggml_source: pathlib.Path,
    shim_source: pathlib.Path,
    project_source: pathlib.Path,
    parent_driver: pathlib.Path,
    tools: dict[str, ToolchainExecutable],
    sdk: ToolchainDirectory,
    platform: str,
    ggml_commit: str,
    source_commit: str,
    compiler_sha256: str | None = None,
) -> PreparationCommand:
    """Construct the same-source static CPU reference as one bounded preparation command."""
    if compiler_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", compiler_sha256) is None:
        raise RecipeError("CPU reference compiler identity is invalid")
    if set(tools) != {"cmake", "cc", "cxx", "ar", "ranlib", "linker", "ninja"}:
        raise RecipeError("CPU reference tool set is incomplete or contains an extra tool")
    if platform not in {"macos", "linux", "wsl2"} or any(
        re.fullmatch(r"[0-9a-f]{40}", value) is None for value in (ggml_commit, source_commit)
    ):
        raise RecipeError("CPU reference platform or source identity is invalid")
    if not work.is_absolute() or not stat.S_ISDIR(work.stat(follow_symlinks=False).st_mode) \
            or work.stat().st_mode & 0o077:
        raise RecipeError("CPU reference work root is not private and absolute")
    root = work.resolve(strict=True)
    for directory in (output, ggml_source, project_source):
        if not directory.is_absolute() or not directory.is_dir() \
                or root not in directory.resolve(strict=True).parents:
            raise RecipeError("CPU reference directory is outside its private work root")
    if entry.suffix != ".align" or (output / entry.stem).exists() \
            or (output / entry.stem).is_symlink() or (output / "build").exists() \
            or (output / "build").is_symlink():
        raise RecipeError("CPU reference entry or output is invalid")

    mappings: dict[str, pathlib.Path | ToolchainDirectory | ToolchainExecutable] = {}
    physical: list[str] = []
    logical: list[str] = []
    for name in ("cmake", "cc", "cxx", "ar", "ranlib", "linker", "ninja"):
        tool = tools[name]
        tool.recheck(tool.sha256)
        token = "<host-" + name + ">:sha256:" + tool.sha256
        mappings[token] = tool
        if name == "cmake":
            continue
        physical.append(f"-D{name.upper()}:FILEPATH={tool.path}")
        logical.append(f"-D{name.upper()}:FILEPATH={token}")
    cmake_token = "<host-cmake>:sha256:" + tools["cmake"].sha256
    physical.insert(0, str(tools["cmake"].path))
    logical.insert(0, cmake_token)
    for variable, label, path in (
        ("ALIGNC", "align-compiler", compiler), ("ENTRY", "cpu-entry", entry),
        ("SHIM_SOURCE", "cpu-shim-source", shim_source),
        ("PARENT_DRIVER", "cpu-parent-driver", parent_driver),
    ):
        token = ("<align-compiler>:sha256:" + compiler_sha256
                 if variable == "ALIGNC" and compiler_sha256 is not None else _input(label, path))
        mappings[token] = path
        physical.append(f"-D{variable}:FILEPATH={path}")
        logical.append(f"-D{variable}:FILEPATH={token}")
    for variable, label, path in (
        ("OUTPUT", "cpu-output", output), ("GGML_SOURCE", "cpu-ggml-source", ggml_source),
        ("PROJECT_SOURCE", "cpu-project", project_source),
    ):
        token = f"<{label}>:owned"
        mappings[token] = path
        physical.append(f"-D{variable}:PATH={path}")
        logical.append(f"-D{variable}:PATH={token}")
    sdk.recheck(sdk.sha256)
    sdk_token = "<host-sdk>:sha256:" + sdk.sha256
    mappings[sdk_token] = sdk
    physical.append(f"-DSDK:PATH={sdk.path}")
    logical.append(f"-DSDK:PATH={sdk_token}")
    literals = (f"-DHOST_PLATFORM={platform}", f"-DGGML_COMMIT={ggml_commit}")
    physical.extend(literals)
    logical.extend(literals)
    script = project_source / "build.cmake"
    script_token = _input("cpu-build-script", script)
    mappings[script_token] = script
    physical.extend(("-P", str(script)))
    logical.extend(("-P", script_token))
    return PreparationCommand(
        tuple(physical), tuple(logical), mappings, output / entry.stem,
        "cpu-reference", source_commit, work, sdk,
    )


def commands(
    *,
    work: pathlib.Path,
    compiler: pathlib.Path,
    runtime: pathlib.Path,
    copier: pathlib.Path | ToolchainExecutable,
    driver: pathlib.Path,
    reference_driver: pathlib.Path,
    entry: pathlib.Path,
    shim_source: pathlib.Path,
    platform: str,
    align_revision: str,
    source_commit: str,
    ggml_include: pathlib.Path | None = None,
    backend_library: pathlib.Path | None = None,
    sdk: ToolchainDirectory | None = None,
    compiler_materialized: bool = False,
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

    if sdk is not None:
        sdk.recheck(sdk.sha256)

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
    if compiler_materialized and _file_sha256(copied_compiler, "materialized compiler") \
            != _file_sha256(compiler, "compiler input"):
        raise RecipeError("materialized compiler does not match its input")
    for output in (shim, copied_compiler, copied_runtime, reference_work, candidate):
        if output == copied_compiler and compiler_materialized:
            continue
        if output.exists() or output.is_symlink():
            raise RecipeError("preparation build output is occupied")

    result = []
    for key, output, name in (
        ("compiler-input", copied_compiler, "alignc"),
        ("runtime-input", copied_runtime, "align-runtime"),
    ):
        result.append(PreparationCommand(
            (str(copier.path if isinstance(copier, ToolchainExecutable) else copier), str(inputs[key]), output.name),
            (tokens["copy-tool"], tokens[key], output.name),
            {tokens["copy-tool"]: copier, tokens[key]: inputs[key]},
            output, name, align_revision, sdk=sdk,
        ))

    flags = [
        "-shared", "-fPIC", "-O2", "-ffp-contract=off", "-DALIGN_GGML_FP_CONTRACT_OFF=1",
        "-Wall", "-Wextra", "-Werror",
    ]
    if platform == "macos":
        flags.extend(("-Xlinker", "-install_name", "-Xlinker", f"@rpath/{shim.name}"))
    physical = [str(driver), *flags, str(shim_source), "-o", shim.name, "-lm"]
    logical = [tokens["c-driver"], *flags, tokens["shim-source"], "-o", shim.name, "-lm"]
    mappings: dict[str, pathlib.Path | ToolchainDirectory] = {
        tokens["c-driver"]: driver, tokens["shim-source"]: shim_source,
    }
    if sdk is not None:
        sdk_token = "<host-sdk>:sha256:" + sdk.sha256
        physical.extend(("-isysroot", str(sdk.path)))
        logical.extend(("-isysroot", sdk_token))
        mappings[sdk_token] = sdk
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
        tuple(physical), tuple(logical), mappings, shim, "align-ggml-shim", source_commit, sdk=sdk,
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
            cwd / entry.stem, name, source_commit, cwd, sdk=sdk,
        ))
    # This directory is the only construction side effect. Validate every path and output first;
    # the invocation owner removes it on failure together with all other private build products.
    reference_work.mkdir(mode=0o700)
    return tuple(result)


def grouped_commands(
    *, work: pathlib.Path, compiler: pathlib.Path, python: ToolchainExecutable,
    helper: pathlib.Path, git: ToolchainExecutable, copier: ToolchainExecutable,
    entry: pathlib.Path, shim_source: pathlib.Path, reference_shim_source: pathlib.Path,
    reference_project: pathlib.Path, ggml_source: pathlib.Path,
    platform: str, align_revision: str, source_commit: str, ggml_commit: str,
    tools: dict[str, ToolchainExecutable], sdk: ToolchainDirectory,
    support_archives: dict[str, pathlib.Path], ggml_include: pathlib.Path | None = None,
    backend_library: pathlib.Path | None = None,
) -> tuple[PreparationCommand | Callable[[], PreparationCommand], ...]:
    """Bind grouped bootstrap now, and construct its dependent four steps after success."""
    first = compiler_materialization_command(
        work=work, compiler=compiler, python=python, helper=helper, cc=tools["cc"],
        linker=tools["linker"], git=git, sdk=sdk, platform=platform,
        align_revision=align_revision, support_archives=support_archives,
    )
    remaining: list[PreparationCommand] = []

    def command_at(ordinal: int) -> PreparationCommand:
        if not remaining:
            driver = work / "native-driver"
            remaining.extend(commands(
                work=work, compiler=compiler, runtime=compiler.parent / "libalign_runtime.a",
                copier=copier, driver=driver, reference_driver=driver, entry=entry,
                shim_source=shim_source, platform=platform, align_revision=align_revision,
                source_commit=source_commit, ggml_include=ggml_include,
                backend_library=backend_library, sdk=sdk, compiler_materialized=True,
            ))
            remaining[4] = cpu_reference_command(
                work=work, output=work / "cpu-reference", compiler=work / "alignc", entry=entry,
                ggml_source=ggml_source, shim_source=reference_shim_source,
                project_source=reference_project, parent_driver=driver, tools=tools, sdk=sdk,
                platform=platform, ggml_commit=ggml_commit, source_commit=source_commit,
            )
            dependencies = (tools["cc"], ToolchainExecutable.admit(work / "native-tools/ld"))
            remaining[:] = [dataclasses.replace(command, tool_dependencies=dependencies) for command in remaining]
        return remaining[ordinal]

    return (first, *(lambda ordinal=ordinal: command_at(ordinal) for ordinal in range(1, 5)))
