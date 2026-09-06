#!/usr/bin/env python3
"""Build one immutable pinned-ggml GPU backend bundle and its replayable source snapshot."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import pathlib
import platform
import stat
import subprocess
import sys
import tempfile


GGML_COMMIT = "bb4caa7540188872173c44d161602d9271386413"
GGML_REPOSITORY = "https://github.com/ggml-org/llama.cpp.git"
MAX_SOURCE_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_RETAINED_DATA_BYTES = 512 * 1024 * 1024
ZERO_DIGEST = "0" * 64
EMPTY_DIGEST = hashlib.sha256(b"").hexdigest()

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
    repositories = {
        "align-llm": "https://github.com/sanohiro/align-llm.git",
        "ggml": GGML_REPOSITORY,
    }
    if not isinstance(source_kind, str) or source_kind not in repositories \
            or manifest["repository"] != repositories[source_kind]:
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


def command(argv: list[str], *, cwd: pathlib.Path | None = None) -> bytes:
    try:
        return subprocess.run(argv, cwd=cwd, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.decode(errors="replace") if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        raise RecipeError(f"command failed: {argv[0]}: {detail.strip()}") from exc


def text_command(argv: list[str], *, cwd: pathlib.Path | None = None) -> str:
    return command(argv, cwd=cwd).decode("utf-8").strip()


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


def require_source(source: pathlib.Path) -> None:
    source = source.resolve()
    top = pathlib.Path(text_command(["git", "rev-parse", "--show-toplevel"], cwd=source)).resolve()
    if top != source:
        raise RecipeError("source is not the Git worktree root")
    if text_command(["git", "rev-parse", "HEAD"], cwd=source) != GGML_COMMIT:
        raise RecipeError("source HEAD is not the pinned ggml commit")
    if text_command(["git", "remote", "get-url", "origin"], cwd=source) != GGML_REPOSITORY:
        raise RecipeError("source origin is not the pinned ggml repository")
    status = command(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--ignored"], cwd=source,
    )
    if status:
        raise RecipeError("source worktree contains modified, untracked, or ignored paths")


def source_snapshot(source: pathlib.Path) -> tuple[dict[str, object], bytes, bytes, dict[str, bytes]]:
    tree = text_command(["git", "rev-parse", "HEAD^{tree}"], cwd=source)
    object_format = text_command(["git", "rev-parse", "--show-object-format"], cwd=source)
    raw_commit = command(["git", "cat-file", "commit", "HEAD"], cwd=source)
    listing = command(["git", "ls-tree", "-rz", "--full-tree", "HEAD"], cwd=source)
    rows: list[dict[str, object]] = []
    blobs: dict[str, bytes] = {}
    for raw_row in listing.split(b"\0"):
        if not raw_row:
            continue
        header, raw_path = raw_row.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split(" ")
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise RecipeError("source tree contains an unsupported non-file entry")
        path = raw_path.decode("utf-8")
        data = (source / path).read_bytes()
        framed = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
        computed_oid = hashlib.new(object_format, framed).hexdigest()
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
        "source_kind": "ggml",
        "repository": GGML_REPOSITORY,
        "object_format": object_format,
        "commit": GGML_COMMIT,
        "commit_object_sha256": digest(raw_commit),
        "tree": tree,
        "files": rows,
    }
    rendered = canonical(manifest)
    if not rows or len(rows) > 100_000 or len(rendered) > MAX_SOURCE_MANIFEST_BYTES:
        raise RecipeError("source manifest exceeds its schema-1 bounds")
    return manifest, rendered, raw_commit, blobs


def identity(name: str, argv: list[str]) -> dict[str, str]:
    raw = command(argv)
    version = raw.decode("utf-8", errors="strict").splitlines()[0].strip()
    if not version or len(version.encode()) > 256:
        raise RecipeError(f"{name} version is outside the identity bound")
    return {"name": name, "version": version, "sha256": digest(raw)}


def toolchain(backend: str) -> dict[str, dict[str, str]]:
    result = {
        "c_compiler": identity("cc", [os.environ.get("CC", "cc"), "--version"]),
        "cxx_compiler": identity("cxx", [os.environ.get("CXX", "c++"), "--version"]),
    }
    if backend == "metal":
        result["sdk"] = identity("macos", ["xcrun", "--sdk", "macosx", "--show-sdk-version"])
        result["toolkit"] = {"name": "none", "version": "none", "sha256": EMPTY_DIGEST}
    else:
        result["sdk"] = identity("glibc", ["ldd", "--version"])
        result["toolkit"] = identity("cuda", ["nvcc", "--version"])
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


def build(backend: str, source: pathlib.Path, output: pathlib.Path) -> None:
    require_host(backend)
    require_source(source)
    if output.exists() or output.is_symlink():
        raise RecipeError("output must be a new path")
    _, source_bytes, raw_commit, blobs = source_snapshot(source)
    tools = toolchain(backend)
    parent = output.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gpu-recipe-build-", dir=parent) as raw_build:
        build_dir = pathlib.Path(raw_build)
        command(["cmake", "-S", str(source), "-B", str(build_dir), *flags(backend)])
        command(["cmake", "--build", str(build_dir), "--target", "ggml", "--parallel", "4"])
        binary_dir = build_dir / "bin"
        sources = artifact_sources(backend, binary_dir)
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
            artifacts = []
            for role, name, source_path in sources:
                data = source_path.resolve().read_bytes()
                (bundle_dir / name).write_bytes(data)
                artifacts.append({"role": role, "path": name, "bytes": len(data), "sha256": digest(data)})
            artifacts.sort(key=lambda row: (row["role"], row["path"]))
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
                "toolchain": tools,
                "build_flags": flags(backend),
                "artifacts": artifacts,
            }
            bundle["bundle_id"] = digest(canonical(bundle))
            (bundle_dir / "manifest.json").write_bytes(canonical(bundle))
            replay_source_snapshot(source_dir, "ggml")
            os.rename(stage, output)


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
