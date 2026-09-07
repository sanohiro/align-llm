#!/usr/bin/env python3
"""Construct the native C driver used by isolated G1 preparation commands."""

from __future__ import annotations

import dataclasses
import pathlib
import stat

from gpu_backend_recipe import RecipeError
from gpu_qualifier_process import (
    ToolchainDirectory, ToolchainExecutable, _file_sha256, run_owned_command,
)


@dataclasses.dataclass(frozen=True)
class NativeDriver:
    path: pathlib.Path
    sdk: ToolchainDirectory
    tool_dependencies: tuple[ToolchainExecutable, ...]


def _c_string(value: str) -> str:
    # Fixed-width octal escapes preserve arbitrary UTF-8 path bytes without C escape ambiguity.
    return '"' + "".join(f"\\{byte:03o}" for byte in value.encode("utf-8")) + '"'


def build_driver(
    *, compiler: ToolchainExecutable, linker: ToolchainExecutable,
    sdk: ToolchainDirectory, work: pathlib.Path, home: pathlib.Path,
    temporary: pathlib.Path, library_root: pathlib.Path, platform: str,
    deadline_ns: int,
) -> NativeDriver:
    if platform not in {"macos", "linux", "wsl2"}:
        raise RecipeError("native driver platform is unsupported")
    for root in (work, library_root):
        if not root.is_absolute() or not stat.S_ISDIR(root.stat(follow_symlinks=False).st_mode) \
                or root.stat().st_mode & 0o077:
            raise RecipeError("native driver root is not private and absolute")
    if linker.path.name != "ld":
        raise RecipeError("native driver linker must retain its ld invocation name")
    compiler.recheck(compiler.sha256)
    linker.recheck(linker.sha256)
    sdk.recheck(sdk.sha256)
    source, output = work / "native-driver.c", work / "native-driver"
    tool_root = work / "native-tools"
    if any(path.exists() or path.is_symlink() for path in (source, output, tool_root)):
        raise RecipeError("native driver output is occupied")
    tool_root.mkdir(mode=0o700)
    (tool_root / "ld").symlink_to(linker.path)
    selected_linker = ToolchainExecutable.admit(tool_root / "ld")
    extra = ["-L", str(library_root), "-Xlinker", "-rpath", "-Xlinker", str(library_root),
             "-B", str(tool_root) + "/"]
    extra.extend(["-isysroot", str(sdk.path)] if platform == "macos" else ["--sysroot=" + str(sdk.path)])
    raw = '''#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static char *variable(const char *prefix, const char *value) {
    if (value == NULL || value[0] != '/' || strlen(value) > 4096) return NULL;
    size_t head = strlen(prefix), tail = strlen(value);
    char *result = malloc(head + tail + 1);
    if (result == NULL) return NULL;
    memcpy(result, prefix, head);
    memcpy(result + head, value, tail + 1);
    return result;
}

int main(int argc, char **argv) {
    if (argc < 2) return 93;
    char *home = variable("HOME=", getenv("HOME"));
    char *temporary = variable("TMPDIR=", getenv("TMPDIR"));
    if (home == NULL || temporary == NULL) return 92;
    char *environment[] = {home, (char *) "LC_ALL=C", temporary, (char *) "TZ=UTC", NULL};
    const char *extra[] = { @EXTRA@ };
    size_t count = sizeof(extra) / sizeof(extra[0]);
    char **selected = calloc((size_t) argc + count + 1, sizeof(char *));
    if (selected == NULL) return 94;
    selected[0] = (char *) @COMPILER@;
    for (int at = 1; at < argc; at++) selected[at] = argv[at];
    for (size_t at = 0; at < count; at++) selected[(size_t) argc + at] = (char *) extra[at];
    execve(selected[0], selected, environment);
    return errno == 0 ? 91 : errno;
}
'''.replace("@EXTRA@", ", ".join(map(_c_string, extra))).replace("@COMPILER@", _c_string(str(compiler.path)))
    with source.open("x", encoding="utf-8") as stream:
        stream.write(raw)
    source.chmod(0o600)
    cc_token = "<host-cc>:sha256:" + compiler.sha256
    source_token = "<native-driver-source>:sha256:" + _file_sha256(source, "native driver source")
    sdk_token = "<host-sdk>:sha256:" + sdk.sha256
    physical = [str(compiler.path), "-Wall", "-Wextra", "-Werror", str(source), "-o", output.name]
    logical = [cc_token, "-Wall", "-Wextra", "-Werror", source_token, "-o", output.name]
    # -isysroot is accepted by both installed Clang and GCC and keeps its path a separate argument.
    physical.extend(("-isysroot", str(sdk.path)))
    logical.extend(("-isysroot", sdk_token))
    physical.extend(("-B", str(tool_root)))
    logical.extend(("-B", "<native-tools>:owned"))
    try:
        result = run_owned_command(
            kind="compiler_materialize", physical_argv=physical, logical_argv=logical,
            mappings={cc_token: compiler, source_token: source, sdk_token: sdk,
                      "<native-tools>:owned": tool_root},
            cwd=work, home=home, temporary=temporary, timeout_seconds=60,
            deadline_ns=deadline_ns, sdk=sdk, tool_dependencies=(compiler, selected_linker),
        )
        if result.terminal != "PASS":
            raise RecipeError("native driver compilation failed: " + result.stderr.retained.decode(errors="replace"))
        ToolchainExecutable.admit(output)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return NativeDriver(output, sdk, (compiler, selected_linker))
