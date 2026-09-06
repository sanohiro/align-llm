#!/usr/bin/env python3
"""Build one immutable pinned-ggml GPU backend bundle and its replayable source snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import tempfile


GGML_COMMIT = "bb4caa7540188872173c44d161602d9271386413"
GGML_REPOSITORY = "https://github.com/ggml-org/llama.cpp.git"
MAX_SOURCE_MANIFEST_BYTES = 16 * 1024 * 1024
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
