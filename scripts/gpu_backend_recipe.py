#!/usr/bin/env python3
"""Build one immutable pinned-ggml GPU backend bundle and its replayable source snapshot."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import pathlib
import platform
import shutil
import stat
import subprocess
import sys
import tempfile


GGML_COMMIT = "bb4caa7540188872173c44d161602d9271386413"
GGML_REPOSITORY = "https://github.com/ggml-org/llama.cpp.git"
SOURCE_REPOSITORIES = {
    "align-llm": "https://github.com/sanohiro/align-llm.git",
    "ggml": GGML_REPOSITORY,
}
MAX_SOURCE_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_RETAINED_DATA_BYTES = 512 * 1024 * 1024
MAX_BUNDLE_ARTIFACT_BYTES = 512 * 1024 * 1024
ZERO_DIGEST = "0" * 64
EMPTY_DIGEST = hashlib.sha256(b"").hexdigest()
GIT_SAFE_OPTIONS = (
    "--no-pager",
    "-c", "core.useReplaceRefs=false",
    "-c", "core.fsmonitor=false",
    "-c", "core.hooksPath=/dev/null",
    "-c", "credential.helper=",
    "-c", "diff.external=",
)

COMMON_FLAGS = (
    "-G", "Ninja",
    "-DCMAKE_BUILD_TYPE=Release",
    "-DBUILD_SHARED_LIBS=ON",
    "-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON",
    "-DGGML_BACKEND_DL=ON",
    "-DGGML_STATIC=OFF",
    "-DGGML_NATIVE=OFF",
    "-DGGML_CCACHE=OFF",
    "-DGGML_CPU=OFF",
    "-DGGML_OPENMP=OFF",
    "-DGGML_ACCELERATE=OFF",
    "-DGGML_BLAS=OFF",
    "-DGGML_LLAMAFILE=OFF",
    "-DGGML_RPC=OFF",
    "-DGGML_VULKAN=OFF",
    "-DGGML_SYCL=OFF",
    "-DGGML_OPENVINO=OFF",
    "-DGGML_MUSA=OFF",
    "-DGGML_HIP=OFF",
    "-DGGML_BUILD_TESTS=OFF",
    "-DGGML_BUILD_EXAMPLES=OFF",
    "-DLLAMA_BUILD_TESTS=OFF",
    "-DLLAMA_BUILD_EXAMPLES=OFF",
    "-DLLAMA_BUILD_SERVER=OFF",
    "-DLLAMA_CURL=OFF",
)

BACKEND_FLAGS = {
    "metal": (
        "-DCMAKE_INSTALL_RPATH=@loader_path",
        "-DGGML_METAL=ON",
        "-DGGML_METAL_EMBED_LIBRARY=ON",
        "-DGGML_METAL_NDEBUG=ON",
        "-DGGML_CUDA=OFF",
    ),
    "cuda": (
        "-DCMAKE_INSTALL_RPATH=$ORIGIN",
        "-DCMAKE_CUDA_ARCHITECTURES=89",
        "-DGGML_METAL=OFF",
        "-DGGML_CUDA=ON",
        "-DGGML_CUDA_GRAPHS=ON",
        "-DGGML_CUDA_FA=ON",
        "-DGGML_CUDA_FA_ALL_QUANTS=OFF",
        "-DGGML_CUDA_FORCE_MMQ=OFF",
        "-DGGML_CUDA_FORCE_CUBLAS=OFF",
        "-DGGML_CUDA_NCCL=OFF",
    ),
}

TARGET = {
    "metal": {"os": "macos", "arch": "aarch64", "gpu_architectures": ["apple_m1"]},
    "cuda": {"os": "linux", "arch": "x86_64", "gpu_architectures": ["sm_89"]},
}


class RecipeError(Exception):
    pass


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_executable(value: str, label: str) -> str:
    selected = pathlib.Path(value)
    if "/" in value:
        if not selected.is_absolute():
            raise RecipeError(f"{label} must be an absolute path or a bare command name")
        try:
            resolved = selected.resolve()
        except (OSError, RuntimeError) as exc:
            raise RecipeError(f"{label} cannot be resolved") from exc
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise RecipeError(f"{label} is not executable")
        return os.fspath(resolved)
    resolved_name = shutil.which(value)
    if resolved_name is None:
        raise RecipeError(f"{label} is not available")
    try:
        resolved = pathlib.Path(resolved_name).resolve()
    except (OSError, RuntimeError) as exc:
        raise RecipeError(f"{label} cannot be resolved") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise RecipeError(f"{label} is not executable")
    return os.fspath(resolved)


def selected_tools(backend: str) -> dict[str, str]:
    values = {
        "git": resolve_executable("git", "git"),
        "cmake": resolve_executable("cmake", "cmake"),
        "ninja": resolve_executable("ninja", "ninja"),
        "cc": resolve_executable(os.environ.get("CC", "cc"), "CC"),
        "cxx": resolve_executable(os.environ.get("CXX", "c++"), "CXX"),
    }
    if backend == "metal":
        values["platform"] = resolve_executable("xcrun", "xcrun")
    else:
        values["platform"] = resolve_executable(os.environ.get("CUDACXX", "nvcc"), "CUDACXX")
        values["ldd"] = resolve_executable("ldd", "ldd")
    return values


def isolated_environment(tools: dict[str, str], owned_root: pathlib.Path) -> dict[str, str]:
    owned_root.mkdir(parents=True, exist_ok=True)
    home = owned_root / "home"
    temporary = owned_root / "tmp"
    home.mkdir()
    temporary.mkdir()
    search_directories = []
    for executable in tools.values():
        directory = os.fspath(pathlib.Path(executable).parent)
        if directory not in search_directories:
            search_directories.append(directory)
    for directory in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
        if directory not in search_directories:
            search_directories.append(directory)
    environment = {
        "CC": tools["cc"],
        "CXX": tools["cxx"],
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_GRAFT_FILE": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": os.fspath(home),
        "LC_ALL": "C",
        "PATH": os.pathsep.join(search_directories),
        "TMPDIR": os.fspath(temporary),
        "TZ": "UTC",
    }
    if "ldd" in tools:
        environment["CUDACXX"] = tools["platform"]
    return environment


def rename_noreplace(source: pathlib.Path, destination: pathlib.Path) -> None:
    if source.parent != destination.parent:
        raise RecipeError("atomic publication requires one parent directory")
    library = ctypes.CDLL(None, use_errno=True)
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) \
        | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        parent_fd = os.open(source.parent, directory_flags)
    except OSError as exc:
        raise RecipeError("output parent cannot be opened") from exc
    try:
        source_bytes = os.fsencode(source.name)
        destination_bytes = os.fsencode(destination.name)
        if sys.platform == "darwin":
            function = library.renameatx_np
            function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                                 ctypes.c_uint]
            function.restype = ctypes.c_int
            result = function(parent_fd, source_bytes, parent_fd, destination_bytes, 0x00000004)
        elif sys.platform.startswith("linux"):
            function = library.renameat2
            function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                                 ctypes.c_uint]
            function.restype = ctypes.c_int
            result = function(parent_fd, source_bytes, parent_fd, destination_bytes, 1)
        else:
            raise RecipeError("atomic no-replace publication is unsupported on this host")
        if result != 0:
            error = ctypes.get_errno()
            if error in {errno.EEXIST, errno.ENOTEMPTY}:
                raise RecipeError("output became occupied before publication")
            raise RecipeError(f"cannot publish output: {os.strerror(error)}")
    finally:
        os.close(parent_fd)


def strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RecipeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_canonical(raw: bytes, maximum: int) -> dict[str, object]:
    if not raw or len(raw) > maximum or raw.startswith(b"\xef\xbb\xbf") or not raw.endswith(b"\n"):
        raise RecipeError("record framing is invalid")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                RecipeError(f"invalid JSON constant: {value}"),
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, UnicodeEncodeError) as exc:
        raise RecipeError("record is not strict UTF-8 JSON") from exc
    try:
        rendered = canonical(value)
    except UnicodeEncodeError as exc:
        raise RecipeError("record contains an invalid Unicode scalar") from exc
    if not isinstance(value, dict) or rendered != raw:
        raise RecipeError("record is not one canonical object")
    return value


def exact_keys(value: object, expected: tuple[str, ...], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or tuple(value) != expected:
        raise RecipeError(f"{label} keys are invalid")
    return value


def bounded_text(value: object, minimum: int, maximum: int, label: str) -> str:
    if not isinstance(value, str) or not minimum <= len(value.encode("utf-8")) <= maximum:
        raise RecipeError(f"{label} is outside its UTF-8 bound")
    return value


def bounded_i64(value: object, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise RecipeError(f"{label} is outside its integer bound")
    return value


def lowercase_hex(value: object, width: int, label: str) -> str:
    text = bounded_text(value, width, width, label)
    try:
        encoded = text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RecipeError(f"{label} is not lowercase hexadecimal") from exc
    if any(byte not in b"0123456789abcdef" for byte in encoded):
        raise RecipeError(f"{label} is not lowercase hexadecimal")
    try:
        bytes.fromhex(text)
    except ValueError as exc:
        raise RecipeError(f"{label} is not hexadecimal") from exc
    return text


def retained_path(value: object, label: str) -> str:
    text = bounded_text(value, 1, MAX_SOURCE_MANIFEST_BYTES, label)
    if "\x00" in text or "\\" in text or text.startswith("/"):
        raise RecipeError(f"{label} is not a retained relative path")
    components = text.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise RecipeError(f"{label} has an invalid component")
    return text


def validate_source_manifest(value: object) -> dict[str, object]:
    manifest = exact_keys(value, (
        "schema_version", "artifact_kind", "source_kind", "repository", "object_format",
        "commit", "commit_object_sha256", "tree", "files",
    ), "source manifest")
    if bounded_i64(manifest["schema_version"], 1, 1, "schema_version") != 1 \
            or manifest["artifact_kind"] != "GPU_SOURCE_MANIFEST":
        raise RecipeError("source manifest version or kind is invalid")
    source_kind = manifest["source_kind"]
    if not isinstance(source_kind, str) or source_kind not in SOURCE_REPOSITORIES \
            or manifest["repository"] != SOURCE_REPOSITORIES[source_kind]:
        raise RecipeError("source kind and repository do not match")
    object_format = manifest["object_format"]
    if not isinstance(object_format, str) or object_format not in {"sha1", "sha256"}:
        raise RecipeError("source object format is invalid")
    oid_width = 40 if object_format == "sha1" else 64
    lowercase_hex(manifest["commit"], oid_width, "commit")
    lowercase_hex(manifest["commit_object_sha256"], 64, "commit_object_sha256")
    lowercase_hex(manifest["tree"], oid_width, "tree")
    rows = manifest["files"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100_000:
        raise RecipeError("source file count is outside its bound")
    previous = b""
    seen: set[str] = set()
    for ordinal, raw_row in enumerate(rows):
        row = exact_keys(raw_row, ("path", "mode", "bytes", "git_oid", "sha256"), "source file")
        path = retained_path(row["path"], f"files[{ordinal}].path")
        encoded = path.encode("utf-8")
        if ordinal and encoded <= previous:
            raise RecipeError("source files are not strictly sorted by raw UTF-8 path")
        previous = encoded
        if path in seen:
            raise RecipeError("source file path is duplicated")
        seen.add(path)
        if not isinstance(row["mode"], str) or row["mode"] not in {"100644", "100755", "120000"}:
            raise RecipeError("source file mode is invalid")
        bounded_i64(row["bytes"], 0, 2**63 - 1, f"files[{ordinal}].bytes")
        lowercase_hex(row["git_oid"], oid_width, f"files[{ordinal}].git_oid")
        lowercase_hex(row["sha256"], 64, f"files[{ordinal}].sha256")
    return manifest


def object_oid(object_format: str, kind: bytes, payload: bytes) -> str:
    framed = kind + b" " + str(len(payload)).encode("ascii") + b"\0" + payload
    return hashlib.new(object_format, framed).hexdigest()


def build_tree_oid(object_format: str, rows: list[dict[str, object]]) -> str:
    root: dict[str, object] = {}
    for row in rows:
        components = str(row["path"]).split("/")
        cursor = root
        for component in components[:-1]:
            existing = cursor.get(component)
            if existing is None:
                existing = {}
                cursor[component] = existing
            if not isinstance(existing, dict):
                raise RecipeError("source path has a file ancestor")
            cursor = existing
        leaf = components[-1]
        if leaf in cursor:
            raise RecipeError("source path collides with another entry")
        cursor[leaf] = (row["mode"], row["git_oid"])

    def encode_tree(entries: dict[str, object]) -> str:
        payload = bytearray()
        ordered = sorted(
            entries.items(),
            key=lambda item: item[0].encode("utf-8") + (b"/" if isinstance(item[1], dict) else b""),
        )
        for name, entry in ordered:
            if isinstance(entry, dict):
                mode = "40000"
                oid = encode_tree(entry)
            else:
                mode, oid = entry
            payload.extend(mode.encode("ascii"))
            payload.extend(b" ")
            payload.extend(name.encode("utf-8"))
            payload.extend(b"\0")
            payload.extend(bytes.fromhex(str(oid)))
        return object_oid(object_format, b"tree", bytes(payload))

    return encode_tree(root)


def single_link_file_at(parent_fd: int, name: str, label: str, maximum: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise RecipeError(f"{label} is not a single-link regular file") from exc
        raise RecipeError(f"{label} is absent") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise RecipeError(f"{label} is not a single-link regular file")
        if before.st_size > maximum:
            raise RecipeError(f"{label} exceeds its retained-data bound")
        chunks = []
        length = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum - length + 1))
            if not chunk:
                break
            chunks.append(chunk)
            length += len(chunk)
            if length > maximum:
                raise RecipeError(f"{label} exceeds its retained-data bound")
        after = os.fstat(descriptor)
        stable_fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
            raise RecipeError(f"{label} changed while it was read")
        return b"".join(chunks)
    except OSError as exc:
        raise RecipeError(f"{label} cannot be read") from exc
    finally:
        os.close(descriptor)


def stable_directory(before: os.stat_result, after: os.stat_result) -> bool:
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_mtime_ns", "st_ctime_ns")
    return all(getattr(before, field) == getattr(after, field) for field in fields)


def replay_source_snapshot(source_dir: pathlib.Path, expected_kind: str) -> dict[str, object]:
    if expected_kind not in {"align-llm", "ggml"}:
        raise RecipeError("source snapshot owner kind is invalid")
    source_dir = source_dir.absolute()
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) \
        | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        root_fd = os.open(source_dir, directory_flags)
    except OSError as exc:
        raise RecipeError("source snapshot directory is absent") from exc
    try:
        root_before = os.fstat(root_fd)
        if not stat.S_ISDIR(root_before.st_mode):
            raise RecipeError("source snapshot root is not a directory")
        try:
            root_entries = set(os.listdir(root_fd))
        except OSError as exc:
            raise RecipeError("source snapshot root cannot be enumerated") from exc
        if root_entries != {"manifest.json", "commit", "blobs"}:
            raise RecipeError("source snapshot root closure is invalid")
        try:
            blob_fd = os.open("blobs", directory_flags, dir_fd=root_fd)
        except OSError as exc:
            raise RecipeError("source blob root is not a directory") from exc
        try:
            blob_before = os.fstat(blob_fd)
            if not stat.S_ISDIR(blob_before.st_mode):
                raise RecipeError("source blob root is not a directory")

            manifest_raw = single_link_file_at(
                root_fd, "manifest.json", "source manifest", MAX_SOURCE_MANIFEST_BYTES,
            )
            manifest = validate_source_manifest(parse_canonical(
                manifest_raw, MAX_SOURCE_MANIFEST_BYTES,
            ))
            if manifest["source_kind"] != expected_kind:
                raise RecipeError("source snapshot kind does not match its owner")
            commit_maximum = MAX_RETAINED_DATA_BYTES - len(manifest_raw)
            if commit_maximum < 0:
                raise RecipeError("source snapshot exceeds the retained-data bound")
            commit_raw = single_link_file_at(root_fd, "commit", "source commit", commit_maximum)
            if digest(commit_raw) != manifest["commit_object_sha256"]:
                raise RecipeError("source commit content digest does not match")
            if object_oid(str(manifest["object_format"]), b"commit", commit_raw) != manifest["commit"]:
                raise RecipeError("source commit Git object does not match")
            try:
                first_line = commit_raw.split(b"\n", 1)[0].decode("ascii")
            except UnicodeDecodeError as exc:
                raise RecipeError("source commit tree header is invalid") from exc
            if first_line != f"tree {manifest['tree']}":
                raise RecipeError("source commit names a different tree")

            rows = manifest["files"]
            assert isinstance(rows, list)
            expected_blobs = {str(row["sha256"]) for row in rows}
            try:
                blob_entries = set(os.listdir(blob_fd))
            except OSError as exc:
                raise RecipeError("source blob root cannot be enumerated") from exc
            if blob_entries != expected_blobs:
                raise RecipeError("source blob closure is invalid")
            blob_identities: dict[str, tuple[int, str]] = {}
            retained_bytes = len(manifest_raw) + len(commit_raw)
            for sha256 in sorted(expected_blobs):
                remaining = MAX_RETAINED_DATA_BYTES - retained_bytes
                data = single_link_file_at(blob_fd, sha256, f"source blob {sha256}", remaining)
                retained_bytes += len(data)
                if digest(data) != sha256:
                    raise RecipeError("source blob content digest does not match")
                blob_identities[sha256] = (
                    len(data), object_oid(str(manifest["object_format"]), b"blob", data),
                )
            for ordinal, row in enumerate(rows):
                length, git_oid = blob_identities[str(row["sha256"])]
                if length != row["bytes"]:
                    raise RecipeError(f"source blob length does not match row {ordinal}")
                if git_oid != row["git_oid"]:
                    raise RecipeError(f"source blob Git object does not match row {ordinal}")
            if build_tree_oid(str(manifest["object_format"]), rows) != manifest["tree"]:
                raise RecipeError("source tree Git object does not match")
            try:
                root_after_entries = set(os.listdir(root_fd))
                blob_after_entries = set(os.listdir(blob_fd))
                root_after = os.fstat(root_fd)
                blob_after = os.fstat(blob_fd)
            except OSError as exc:
                raise RecipeError("source snapshot cannot be rechecked") from exc
            if root_after_entries != root_entries or blob_after_entries != blob_entries \
                    or not stable_directory(root_before, root_after) \
                    or not stable_directory(blob_before, blob_after):
                raise RecipeError("source snapshot closure changed while it was read")

            snapshot = hashlib.sha256()
            snapshot.update(b"GPU_SOURCE_SNAPSHOT\0")
            snapshot.update(expected_kind.encode("ascii"))
            snapshot.update(b"\0")
            snapshot.update(manifest_raw)
            for row in rows:
                snapshot.update(bytes.fromhex(str(row["sha256"])))
            return {
                "source_kind": expected_kind,
                "manifest_sha256": digest(manifest_raw),
                "snapshot_sha256": snapshot.hexdigest(),
                "commit": manifest["commit"],
                "tree": manifest["tree"],
                "file_count": len(rows),
            }
        finally:
            os.close(blob_fd)
    finally:
        os.close(root_fd)


def command(
    argv: list[str], *, cwd: pathlib.Path | None = None,
    environment: dict[str, str] | None = None,
) -> bytes:
    try:
        return subprocess.run(argv, cwd=cwd, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                              env=environment).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.decode(errors="replace") if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        raise RecipeError(f"command failed: {argv[0]}: {detail.strip()}") from exc


def text_command(
    argv: list[str], *, cwd: pathlib.Path | None = None,
    environment: dict[str, str] | None = None,
) -> str:
    return command(argv, cwd=cwd, environment=environment).decode("utf-8").strip()


def git_command(
    git: str, arguments: list[str], *, source: pathlib.Path,
    environment: dict[str, str],
) -> bytes:
    return command(
        [git, *GIT_SAFE_OPTIONS, *arguments], cwd=source, environment=environment,
    )


def git_text(
    git: str, arguments: list[str], *, source: pathlib.Path,
    environment: dict[str, str],
) -> str:
    return git_command(git, arguments, source=source, environment=environment) \
        .decode("utf-8").strip()


def flags(backend: str) -> list[str]:
    return [*COMMON_FLAGS, *BACKEND_FLAGS[backend]]


def plan(backend: str) -> dict[str, object]:
    return {
        "backend": backend,
        "ggml_commit": GGML_COMMIT,
        "target": TARGET[backend],
        "configure_flags": flags(backend),
        "build_argv_suffix": ["--target", "ggml", "--parallel", "4"],
    }


def _source_identity(source_kind: str, commit: str | None) -> tuple[str, str]:
    if source_kind not in SOURCE_REPOSITORIES:
        raise RecipeError("source kind is invalid")
    if source_kind == "ggml":
        if commit is not None and commit != GGML_COMMIT:
            raise RecipeError("source commit is not the pinned ggml commit")
        commit = GGML_COMMIT
    if not isinstance(commit, str) or len(commit) not in (40, 64):
        raise RecipeError("source requires an exact commit identity")
    lowercase_hex(commit, len(commit), "source commit")
    return SOURCE_REPOSITORIES[source_kind], commit


def require_source(
    source: pathlib.Path, git: str, environment: dict[str, str], *,
    source_kind: str = "ggml", commit: str | None = None,
) -> None:
    repository, commit = _source_identity(source_kind, commit)
    source = source.resolve()
    top = pathlib.Path(git_text(
        git, ["rev-parse", "--show-toplevel"], source=source, environment=environment,
    )).resolve()
    if top != source:
        raise RecipeError("source is not the Git worktree root")
    if git_text(git, ["rev-parse", "HEAD"], source=source,
                environment=environment) != commit:
        raise RecipeError(f"source HEAD is not the pinned {source_kind} commit")
    if git_text(git, ["remote", "get-url", "origin"], source=source,
                environment=environment) != repository:
        raise RecipeError(f"source origin is not the pinned {source_kind} repository")
    replacements = git_command(
        git, ["for-each-ref", "--format=%(refname)%00", "refs/replace/"],
        source=source, environment=environment,
    )
    if replacements:
        raise RecipeError("source repository contains Git replacement refs")
    status = git_command(
        git, ["status", "--porcelain=v1", "--untracked-files=all", "--ignored"],
        source=source, environment=environment,
    )
    if status:
        raise RecipeError("source worktree contains modified, untracked, or ignored paths")


def validate_captured_source(
    manifest: dict[str, object], manifest_raw: bytes, raw_commit: bytes,
    blobs: dict[str, bytes], expected_kind: str,
) -> None:
    validated = validate_source_manifest(parse_canonical(
        manifest_raw, MAX_SOURCE_MANIFEST_BYTES,
    ))
    if validated != manifest or validated["source_kind"] != expected_kind:
        raise RecipeError("captured source manifest does not match its owner")
    object_format = str(validated["object_format"])
    if digest(raw_commit) != validated["commit_object_sha256"]:
        raise RecipeError("captured source commit content digest does not match")
    if object_oid(object_format, b"commit", raw_commit) != validated["commit"]:
        raise RecipeError("captured source commit Git object does not match")
    try:
        first_line = raw_commit.split(b"\n", 1)[0].decode("ascii")
    except UnicodeDecodeError as exc:
        raise RecipeError("captured source commit tree header is invalid") from exc
    if first_line != f"tree {validated['tree']}":
        raise RecipeError("captured source commit names a different tree")

    rows = validated["files"]
    assert isinstance(rows, list)
    expected_blobs = {str(row["sha256"]) for row in rows}
    if set(blobs) != expected_blobs:
        raise RecipeError("captured source blob closure is invalid")
    retained_bytes = len(manifest_raw) + len(raw_commit)
    identities: dict[str, tuple[int, str]] = {}
    for sha256, data in blobs.items():
        retained_bytes += len(data)
        if retained_bytes > MAX_RETAINED_DATA_BYTES or digest(data) != sha256:
            raise RecipeError("captured source blob content or retained-data bound is invalid")
        identities[sha256] = (len(data), object_oid(object_format, b"blob", data))
    for ordinal, row in enumerate(rows):
        length, git_oid = identities[str(row["sha256"])]
        if length != row["bytes"] or git_oid != row["git_oid"]:
            raise RecipeError(f"captured source blob identity does not match row {ordinal}")
    if build_tree_oid(object_format, rows) != validated["tree"]:
        raise RecipeError("captured source tree Git object does not match")


def source_snapshot(
    source: pathlib.Path, git: str, environment: dict[str, str],
    *, source_kind: str = "ggml", commit: str | None = None,
) -> tuple[dict[str, object], bytes, bytes, dict[str, bytes]]:
    repository, commit = _source_identity(source_kind, commit)
    require_source(source, git, environment, source_kind=source_kind, commit=commit)
    tree = git_text(git, ["rev-parse", commit + "^{tree}"], source=source,
                    environment=environment)
    object_format = git_text(
        git, ["rev-parse", "--show-object-format"], source=source, environment=environment,
    )
    raw_commit = git_command(git, ["cat-file", "commit", commit], source=source,
                             environment=environment)
    listing = git_command(git, ["ls-tree", "-rz", "--full-tree", commit], source=source,
                          environment=environment)
    rows: list[dict[str, object]] = []
    blobs: dict[str, bytes] = {}
    for raw_row in listing.split(b"\0"):
        if not raw_row:
            continue
        header, raw_path = raw_row.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split(" ")
        if kind != "blob" or mode not in {"100644", "100755", "120000"}:
            raise RecipeError("source tree contains an unsupported non-file entry")
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RecipeError("source tree contains a non-UTF-8 path") from exc
        source_path = source / path
        try:
            metadata = source_path.lstat()
            if mode == "120000":
                if not stat.S_ISLNK(metadata.st_mode):
                    raise RecipeError(f"working path differs from its Git mode: {path}")
                data = os.readlink(os.fsencode(source_path))
            else:
                if not stat.S_ISREG(metadata.st_mode):
                    raise RecipeError(f"working path differs from its Git mode: {path}")
                data = source_path.read_bytes()
        except OSError as exc:
            raise RecipeError(f"working path cannot be read: {path}") from exc
        computed_oid = object_oid(object_format, b"blob", data)
        if computed_oid != oid:
            raise RecipeError(f"working file differs from its Git blob: {path}")
        sha256 = digest(data)
        blobs.setdefault(sha256, data)
        rows.append({
            "path": path,
            "mode": mode,
            "bytes": len(data),
            "git_oid": oid,
            "sha256": sha256,
        })
    manifest = {
        "schema_version": 1,
        "artifact_kind": "GPU_SOURCE_MANIFEST",
        "source_kind": source_kind,
        "repository": repository,
        "object_format": object_format,
        "commit": commit,
        "commit_object_sha256": digest(raw_commit),
        "tree": tree,
        "files": rows,
    }
    rendered = canonical(manifest)
    if not rows or len(rows) > 100_000 or len(rendered) > MAX_SOURCE_MANIFEST_BYTES:
        raise RecipeError("source manifest exceeds its schema-1 bounds")
    validate_captured_source(manifest, rendered, raw_commit, blobs, source_kind)
    require_source(source, git, environment, source_kind=source_kind, commit=commit)
    return manifest, rendered, raw_commit, blobs


def materialize_source(
    manifest: dict[str, object], blobs: dict[str, bytes], destination: pathlib.Path,
) -> None:
    destination.mkdir()
    rows = manifest["files"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        relative = pathlib.Path(str(row["path"]))
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = blobs[str(row["sha256"])]
        if row["mode"] == "120000":
            try:
                os.symlink(data, os.fsencode(target))
            except (OSError, ValueError) as exc:
                raise RecipeError(f"cannot materialize source symlink: {relative}") from exc
        else:
            try:
                target.write_bytes(data)
                target.chmod(0o755 if row["mode"] == "100755" else 0o644)
            except OSError as exc:
                raise RecipeError(f"cannot materialize source file: {relative}") from exc


def identity(
    name: str, argv: list[str], environment: dict[str, str],
) -> dict[str, str]:
    raw = command(argv, environment=environment)
    try:
        version = raw.decode("utf-8", errors="strict").splitlines()[0].strip()
    except (UnicodeDecodeError, IndexError) as exc:
        raise RecipeError(f"{name} version probe is invalid") from exc
    if not version or len(version.encode()) > 256:
        raise RecipeError(f"{name} version is outside the identity bound")
    return {"name": name, "version": version, "sha256": digest(raw)}


def toolchain(
    backend: str, tools: dict[str, str], environment: dict[str, str],
) -> dict[str, dict[str, str]]:
    result = {
        "c_compiler": identity("cc", [tools["cc"], "--version"], environment),
        "cxx_compiler": identity("cxx", [tools["cxx"], "--version"], environment),
    }
    if backend == "metal":
        result["sdk"] = identity(
            "macos", [tools["platform"], "--sdk", "macosx", "--show-sdk-version"], environment,
        )
        result["toolkit"] = {"name": "none", "version": "none", "sha256": EMPTY_DIGEST}
    else:
        result["sdk"] = identity("glibc", [tools["ldd"], "--version"], environment)
        result["toolkit"] = identity("cuda", [tools["platform"], "--version"], environment)
    return result


def require_host(backend: str) -> None:
    system = platform.system()
    machine = platform.machine()
    if backend == "metal" and (system != "Darwin" or machine not in {"arm64", "aarch64"}):
        raise RecipeError("the Metal recipe requires macOS on AArch64")
    if backend == "cuda" and (system != "Linux" or machine != "x86_64"):
        raise RecipeError("the CUDA recipe requires Linux on x86_64")


def artifact_sources(backend: str, binary_dir: pathlib.Path) -> list[tuple[str, str, pathlib.Path]]:
    if backend == "metal":
        values = [
            ("backend_plugin", "libggml-metal.so", binary_dir / "libggml-metal.so"),
            ("shared_library", "libggml-base.0.dylib", binary_dir / "libggml-base.0.dylib"),
            ("shared_library", "libggml-base.dylib", binary_dir / "libggml-base.dylib"),
            ("shared_library", "libggml.0.dylib", binary_dir / "libggml.0.dylib"),
            ("shared_library", "libggml.dylib", binary_dir / "libggml.dylib"),
        ]
    else:
        values = [
            ("backend_plugin", "libggml-cuda.so", binary_dir / "libggml-cuda.so"),
            ("shared_library", "libggml-base.so.0", binary_dir / "libggml-base.so.0"),
            ("shared_library", "libggml-base.so", binary_dir / "libggml-base.so"),
            ("shared_library", "libggml.so.0", binary_dir / "libggml.so.0"),
            ("shared_library", "libggml.so", binary_dir / "libggml.so"),
        ]
    for _, _, path in values:
        if not path.exists() or not path.resolve().is_file():
            raise RecipeError(f"expected build artifact is absent: {path.name}")
    return values


def copy_artifacts(
    sources: list[tuple[str, str, pathlib.Path]], bundle_dir: pathlib.Path,
) -> list[dict[str, object]]:
    artifacts = []
    artifact_bytes = 0
    for role, name, source_path in sources:
        resolved_source = source_path.resolve()
        try:
            metadata = resolved_source.stat()
        except OSError as exc:
            raise RecipeError(f"cannot inspect build artifact: {name}") from exc
        if not stat.S_ISREG(metadata.st_mode) or not 1 <= metadata.st_size \
                <= MAX_BUNDLE_ARTIFACT_BYTES:
            raise RecipeError(f"build artifact size is outside its bound: {name}")
        artifact_bytes += metadata.st_size
        if artifact_bytes > MAX_BUNDLE_ARTIFACT_BYTES:
            raise RecipeError("build artifact aggregate exceeds its bound")
        try:
            data = resolved_source.read_bytes()
        except OSError as exc:
            raise RecipeError(f"cannot read build artifact: {name}") from exc
        if len(data) != metadata.st_size:
            raise RecipeError(f"build artifact changed while it was read: {name}")
        try:
            (bundle_dir / name).write_bytes(data)
        except OSError as exc:
            raise RecipeError(f"cannot retain build artifact: {name}") from exc
        artifacts.append({"role": role, "path": name, "bytes": len(data), "sha256": digest(data)})
    artifacts.sort(key=lambda row: (row["role"], row["path"]))
    return artifacts


def build(backend: str, source: pathlib.Path, output: pathlib.Path) -> None:
    source = source.resolve()
    output = pathlib.Path(os.path.abspath(output))
    try:
        output.relative_to(source)
    except ValueError:
        pass
    else:
        raise RecipeError("output must be outside the source checkout")
    parent = output.parent.resolve()
    try:
        parent.relative_to(source)
    except ValueError:
        pass
    else:
        raise RecipeError("output parent must be outside the source checkout")
    output = parent / output.name
    require_host(backend)
    if output.exists() or output.is_symlink():
        raise RecipeError("output must be a new path")
    with tempfile.TemporaryDirectory(prefix="gpu-recipe-work-") as raw_work:
        work_dir = pathlib.Path(raw_work)
        executables = selected_tools(backend)
        environment = isolated_environment(executables, work_dir)
        require_source(source, executables["git"], environment)
        manifest, source_bytes, raw_commit, blobs = source_snapshot(
            source, executables["git"], environment,
        )
        identities = toolchain(backend, executables, environment)
        private_source = work_dir / "source"
        build_dir = work_dir / "build"
        materialize_source(manifest, blobs, private_source)
        build_environment = dict(environment)
        build_environment["GIT_CEILING_DIRECTORIES"] = os.fspath(work_dir)
        configure_flags = [
            *flags(backend),
            f"-DCMAKE_MAKE_PROGRAM={executables['ninja']}",
            f"-DCMAKE_C_COMPILER={executables['cc']}",
            f"-DCMAKE_CXX_COMPILER={executables['cxx']}",
        ]
        if backend == "cuda":
            configure_flags.append(f"-DCMAKE_CUDA_COMPILER={executables['platform']}")
        command(
            [executables["cmake"], "-S", os.fspath(private_source), "-B", os.fspath(build_dir),
             *configure_flags],
            environment=build_environment,
        )
        command(
            [executables["cmake"], "--build", os.fspath(build_dir),
             "--target", "ggml", "--parallel", "4"],
            environment=build_environment,
        )
        binary_dir = build_dir / "bin"
        sources = artifact_sources(backend, binary_dir)
        parent.mkdir(parents=True, exist_ok=True)
        if output.exists() or output.is_symlink():
            raise RecipeError("output became occupied during the build")
        with tempfile.TemporaryDirectory(prefix="gpu-recipe-output-", dir=parent) as raw_stage:
            stage = pathlib.Path(raw_stage)
            bundle_dir = stage / "bundle"
            source_dir = stage / "source"
            blob_dir = source_dir / "blobs"
            bundle_dir.mkdir()
            blob_dir.mkdir(parents=True)
            (source_dir / "manifest.json").write_bytes(source_bytes)
            (source_dir / "commit").write_bytes(raw_commit)
            for sha256, data in sorted(blobs.items()):
                (blob_dir / sha256).write_bytes(data)
            artifacts = copy_artifacts(sources, bundle_dir)
            bundle = {
                "schema_version": 1,
                "artifact_kind": "GPU_BACKEND_BUNDLE",
                "bundle_id": ZERO_DIGEST,
                "backend": backend,
                "ggml": {
                    "commit": GGML_COMMIT,
                    "source_manifest_sha256": digest(source_bytes),
                    "version": GGML_COMMIT,
                },
                "target": TARGET[backend],
                "toolchain": identities,
                "build_flags": configure_flags,
                "artifacts": artifacts,
            }
            bundle["bundle_id"] = digest(canonical(bundle))
            bundle_bytes = canonical(bundle)
            if len(bundle_bytes) > 256 * 1024:
                raise RecipeError("backend bundle manifest exceeds its schema-1 bound")
            (bundle_dir / "manifest.json").write_bytes(bundle_bytes)
            replay_source_snapshot(source_dir, "ggml")
            rename_noreplace(stage, output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True, choices=sorted(BACKEND_FLAGS))
    parser.add_argument("--print-plan", action="store_true")
    parser.add_argument("--source", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    if not args.print_plan and (args.source is None or args.output is None):
        parser.error("--source and --output are required unless --print-plan is used")
    if args.print_plan and (args.source is not None or args.output is not None):
        parser.error("--print-plan does not accept --source or --output")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.print_plan:
            sys.stdout.buffer.write(canonical(plan(args.backend)))
        else:
            build(args.backend, args.source.resolve(), args.output.absolute())
    except RecipeError as exc:
        print(f"gpu backend recipe: ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
