#!/usr/bin/env python3
"""Admit the installed host tools against a G1 bundle's recipe identities."""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import platform as host_platform
import shutil
import sys

from gpu_backend_recipe import EMPTY_DIGEST, RecipeError
from gpu_qualifier_process import ToolchainDirectory, ToolchainExecutable, _file_sha256, run_owned_command


@dataclasses.dataclass(frozen=True)
class HostToolchain:
    platform: str
    tools: dict[str, ToolchainExecutable]
    sdk: ToolchainDirectory
    identities: dict[str, dict[str, str]]
    support_archives: dict[str, pathlib.Path]


def _find(name: str) -> ToolchainExecutable:
    selected = shutil.which(name)
    if selected is None:
        raise RecipeError(f"qualification host requires {name}")
    return ToolchainExecutable.admit(pathlib.Path(selected).absolute())


def _platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "wsl2" if "microsoft" in host_platform.release().lower() else "linux"
    raise RecipeError("qualification host platform is unsupported")


def _system_sdk() -> ToolchainDirectory:
    return ToolchainDirectory.admit(pathlib.Path("/"), pathlib.Path("/etc/os-release").resolve(strict=True))


def admit_host(
    *, platform: str, expected: dict[str, object], work: pathlib.Path,
    home: pathlib.Path, temporary: pathlib.Path, deadline_ns: int,
) -> HostToolchain:
    if platform != _platform():
        raise RecipeError("qualification profile does not match the host platform")

    def probe(tool: ToolchainExecutable, *arguments: str) -> bytes:
        token = "<host-probe>:sha256:" + tool.sha256
        result = run_owned_command(
            kind="compiler_materialize", physical_argv=(str(tool.path), *arguments),
            logical_argv=(token, *arguments), mappings={token: tool},
            cwd=work, home=home, temporary=temporary, timeout_seconds=15,
            deadline_ns=deadline_ns,
        )
        if result.terminal != "PASS":
            raise RecipeError("qualification host probe failed")
        return result.stdout.retained

    def text(tool: ToolchainExecutable, *arguments: str) -> str:
        raw = probe(tool, *arguments)
        try:
            value = raw.decode("utf-8", errors="strict").strip()
        except UnicodeDecodeError as error:
            raise RecipeError("qualification host path probe is not UTF-8") from error
        if not value or len(value.encode()) > 4096 or any(c in value for c in "\x00\n\r"):
            raise RecipeError("qualification host path probe is malformed")
        return value

    def identity(name: str, tool: ToolchainExecutable, *arguments: str) -> dict[str, str]:
        raw = probe(tool, *arguments)
        try:
            version = raw.decode("utf-8", errors="strict").splitlines()[0].strip()
        except (UnicodeDecodeError, IndexError) as error:
            raise RecipeError("qualification host version probe is malformed") from error
        if not version or len(version.encode()) > 256:
            raise RecipeError("qualification host version is outside its bound")
        return {"name": name, "version": version, "sha256": hashlib.sha256(raw).hexdigest()}

    tools = {"cmake": _find("cmake"), "ninja": _find("ninja")}
    if platform == "macos":
        selector = _find("xcrun")
        for key, name in (("cc", "clang"), ("cxx", "clang++"), ("ar", "ar"),
                          ("ranlib", "ranlib"), ("linker", "ld")):
            tools[key] = ToolchainExecutable.admit(pathlib.Path(text(selector, "--find", name)))
        sdk_path = pathlib.Path(text(selector, "--sdk", "macosx", "--show-sdk-path"))
        sdk = ToolchainDirectory.admit(sdk_path, sdk_path / "SDKSettings.json")
        sdk_identity = identity("macos", selector, "--sdk", "macosx", "--show-sdk-version")
        toolkit_identity = {"name": "none", "version": "none", "sha256": EMPTY_DIGEST}
    else:
        for key, name in (("cc", "cc"), ("cxx", "c++"), ("ar", "ar"),
                          ("ranlib", "ranlib"), ("linker", "ld")):
            tools[key] = _find(name)
        sdk = _system_sdk()
        sdk_identity = identity("glibc", _find("ldd"), "--version")
        toolkit_identity = identity("cuda", _find("nvcc"), "--version")
    identities = {
        "c_compiler": identity("cc", tools["cc"], "--version"),
        "cxx_compiler": identity("cxx", tools["cxx"], "--version"),
        "sdk": sdk_identity, "toolkit": toolkit_identity,
    }
    if identities != expected:
        raise RecipeError("qualification host toolchain does not match the bundle")
    if platform == "macos" and pathlib.Path(
        text(selector, "--sdk", "macosx", "--show-sdk-path"),
    ).resolve(strict=True) != sdk.path:
        raise RecipeError("qualification host SDK selection changed")
    package_tool = _find("pkg-config")
    archives = {}
    for package, names in (("openssl", ("crypto", "ssl")), ("libzstd", ("zstd",))):
        directory = pathlib.Path(text(package_tool, "--variable=libdir", package))
        if not directory.is_absolute():
            raise RecipeError("qualification support library directory is not absolute")
        for name in names:
            path = directory / ("lib" + name + ".a")
            _file_sha256(path, "support archive")
            with path.open("rb") as stream:
                if stream.read(8) != b"!<arch>\n":
                    raise RecipeError("qualification support library is not a static archive")
            archives[name] = path
    sdk.recheck(sdk.sha256)
    for tool in tools.values():
        tool.recheck(tool.sha256)
    return HostToolchain(platform, tools, sdk, identities, archives)
