#!/usr/bin/env python3
"""Run compiler materialization inside the qualifier's existing owned process group."""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import os
import pathlib
import subprocess
import sys

from gpu_backend_recipe import GIT_SAFE_OPTIONS, RecipeError
from gpu_qualification_driver import plan_driver
from gpu_qualification_run import _artifact
from gpu_qualifier_process import ToolchainDirectory, ToolchainExecutable, _private_directory


def verify_managed(compiler, expected, revision, git, work, environment) -> None:
    path = pathlib.Path(__file__).with_name("align-toolchain")
    loader = importlib.machinery.SourceFileLoader("gpu_managed_verifier", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    owner = importlib.util.module_from_spec(spec)
    loader.exec_module(owner)
    source = compiler.parent.parent.parent
    if compiler != source / owner.COMPILER:
        raise RecipeError("compiler input is not a managed release output")

    def execute(arguments):
        if arguments[0] == "git":
            git.recheck(git.sha256)
            argv = (str(git.path), "--no-optional-locks", *GIT_SAFE_OPTIONS, *arguments[1:])
        elif arguments[0] == str(compiler):
            if _artifact(compiler)[1] != expected:
                raise RecipeError("managed compiler changed before its version probe")
            argv = tuple(arguments)
        else:
            raise RecipeError("managed verifier selected an unexpected executable")
        # Keep output memory bounded while retaining stderr in the outer command's capture.
        with subprocess.Popen(argv, cwd=work, env=environment, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE) as process:
            assert process.stdout is not None
            try:
                raw = process.stdout.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise RecipeError("managed verification output exceeds its bound")
                if process.wait() != 0:
                    raise RecipeError("managed verification command failed")
                return raw.decode("utf-8", errors="strict").strip()
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise

    try:
        owner.verify(source, revision, execute=execute)
    except (owner.ToolchainError, UnicodeDecodeError) as error:
        raise RecipeError(f"managed verification failed: {error}") from error


def main(arguments: list[str]) -> None:
    if len(arguments) != 11:
        raise RecipeError("compiler materialization arguments are incomplete")
    source, expected, cc, ld, sdk_root, sdk_metadata, directory, platform, output_name, git, revision = arguments
    if output_name != "alignc":
        raise RecipeError("compiler materialization output is invalid")
    work = _private_directory(pathlib.Path(directory), "compiler work")
    home = _private_directory(pathlib.Path(os.environ.get("HOME", "")), "compiler HOME")
    temporary = _private_directory(pathlib.Path(os.environ.get("TMPDIR", "")), "compiler TMPDIR")
    environment = {"HOME": str(home), "LC_ALL": "C", "TMPDIR": str(temporary), "TZ": "UTC"}
    output = work / output_name
    if output.exists() or output.is_symlink():
        raise RecipeError("compiler materialization output is occupied")
    data, digest = _artifact(pathlib.Path(source))
    if digest != expected:
        raise RecipeError("compiler materialization input changed")
    verify_managed(pathlib.Path(source), expected, revision,
                   ToolchainExecutable.admit(pathlib.Path(git)), work, environment)
    sdk = ToolchainDirectory.admit(pathlib.Path(sdk_root), pathlib.Path(sdk_metadata))
    planned = plan_driver(
        compiler=ToolchainExecutable.admit(pathlib.Path(cc)),
        linker=ToolchainExecutable.admit(pathlib.Path(ld)), sdk=sdk,
        work=work, library_root=work, platform=platform,
    )
    created = False
    try:
        sdk.recheck(sdk.sha256)
        for tool in planned.driver.tool_dependencies:
            tool.recheck(tool.sha256)
        # The outer process owner captures both inherited streams and terminates this entire
        # group. A nested owner/session here would let the C compiler escape that boundary.
        subprocess.run(planned.physical_argv, cwd=work, env=environment,
                       stdin=subprocess.DEVNULL, check=True)
        ToolchainExecutable.admit(planned.driver.path)
        with output.open("xb") as stream:
            created = True
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        output.chmod(0o700)
        if _artifact(output)[1] != hashlib.sha256(data).hexdigest():
            raise RecipeError("compiler materialization copy changed")
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        planned.driver.path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (RecipeError, OSError, subprocess.CalledProcessError) as error:
        print(f"compiler materialization: {error}", file=sys.stderr)
        raise SystemExit(1)
