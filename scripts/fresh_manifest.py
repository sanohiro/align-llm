#!/usr/bin/env python3
"""Canonical digest-tree and schema-2 manifest helpers for Section 9.

The module is deliberately pure.  It validates authenticated bytes and
recomputes structural/serialized digests, but it does not open host paths or
copy cache/runtime data.  Those ownership and descriptor operations belong to
the repository worker slice.
"""

from __future__ import annotations

import hashlib
import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fresh_attestation import (
    MAX_STRING_BYTES,
    WireError,
    canonical_json_bytes,
    parse_canonical_json,
    sha256_hex,
)


MANIFEST_LIMIT = 64 * 1024 * 1024
MAX_TOOLS = 128
MAX_RUNTIME_BINDINGS = 256
MAX_ENTRIES = 200_000
MAX_DEPTH = 64
MAX_FILE_BYTES = 536_870_912
MAX_CACHE_BYTES = 21_474_836_480
MAX_PROBE_BYTES = 65_536
MAX_ARGV = 32
MAX_ARGV_BYTES = 4096
CONTROLLER_PATH = "scripts/fresh-align-compiler"
BOOTSTRAP_PATH = "/usr/local/libexec/align-llm/fresh-bootstrap"
TOOL_INVENTORY = (
    "git",
    "cargo",
    "rustc",
    "llvm-config",
    "llvm-config-22",
    "cc",
    "cxx",
    "ar",
    "ranlib",
    "linker",
    "bwrap",
    "sh",
    "make",
    "python3",
    "env",
    "bash",
    "prlimit",
    "clang",
    "clang++",
    "strip",
    "objdump",
    "objcopy",
    "llvm-profdata",
    "llvm-profdata-22",
    "llvm-bcanalyzer",
    "llvm-bcanalyzer-22",
    "llvm-readobj",
    "llvm-nm",
    "ld",
    "ld.lld",
    "id",
    "mount-guard",
    "basename",
    "cat",
    "chmod",
    "cmp",
    "cp",
    "diff",
    "dirname",
    "find",
    "grep",
    "head",
    "mkdir",
    "mktemp",
    "mv",
    "readlink",
    "realpath",
    "rm",
    "rmdir",
    "sed",
    "seq",
    "sleep",
    "stat",
    "tail",
    "tee",
    "touch",
    "tr",
    "wc",
)
ALLOWED_CACHE_PREFIXES = (
    "git/checkouts",
    "git/db",
    "registry/cache",
    "registry/index",
    "registry/src",
)
_CACHE_PREFIX_PARTS = tuple(tuple(prefix.split("/")) for prefix in ALLOWED_CACHE_PREFIXES)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MODE = re.compile(r"^[0-7]{4}$")

MANIFEST_FIELDS = (
    "schema_version",
    "controller",
    "bootstrap",
    "platform",
    "tools",
    "runtime_bindings",
    "cargo_cache",
)
CONTROLLER_FIELDS = ("path", "api")
BOOTSTRAP_FIELDS = ("path", "sha256", "api")
PLATFORM_FIELDS = ("os", "architecture", "kernel_minimum", "python_minimum", "make_minimum")
TOOL_FIELDS = ("name", "path", "namespace_path", "mode", "sha256", "argv", "stdout", "stderr")
RUNTIME_FIELDS = ("source", "target", "kind", "manifest", "manifest_sha256")
CACHE_FIELDS = ("root", "manifest", "manifest_sha256", "entry_count")
CACHE_MANIFEST_FIELDS = (
    "schema_version",
    "allowed_prefixes",
    "root",
    "entry_count",
    "total_size",
)
DIGEST_ROOT_FIELDS = ("kind", "mode", "staged_mode", "size", "sha256", "entries")
DIGEST_ENTRY_FIELDS = ("name", "kind", "mode", "staged_mode", "size", "sha256", "entries")


class ManifestError(WireError):
    """The manifest or digest-tree value violates the Section 9 wire contract."""


@dataclass(frozen=True)
class TreeSummary:
    entry_count: int
    total_size: int
    depth: int


def _fields(value: Mapping[str, Any], expected: tuple[str, ...], label: str) -> None:
    if tuple(value.keys()) != expected:
        raise ManifestError(f"{label} has the wrong field order or field set")


def _string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise ManifestError(f"{label} is not a string")
    if "\x00" in value:
        raise ManifestError(f"{label} contains NUL")
    try:
        size = len(value.encode("utf-8", "strict"))
    except UnicodeEncodeError as error:
        raise ManifestError(f"{label} is not valid UTF-8") from error
    if size > MAX_STRING_BYTES:
        raise ManifestError(f"{label} exceeds its string bound")
    return value


def _uint(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= 2**64:
        raise ManifestError(f"{label} is not an unsigned 64-bit integer")
    return value


def _exact_uint(value: Any, expected: int, label: str) -> None:
    if _uint(value, label) != expected:
        raise ManifestError(f"{label} is not {expected}")


def _hex64(value: Any, label: str) -> str:
    value = _string(value, label)
    if not HEX64.fullmatch(value):
        raise ManifestError(f"{label} is not lowercase SHA-256 hex")
    return value


def _mode(value: Any, label: str) -> str:
    value = _string(value, label)
    if not MODE.fullmatch(value) or int(value, 8) > 0o777:
        raise ManifestError(f"{label} is not a four-digit mode below 01000")
    return value


def _absolute_path(value: Any, label: str) -> str:
    value = _string(value, label)
    if not value.startswith("/") or value.endswith("/"):
        raise ManifestError(f"{label} is not an absolute canonical path")
    if any(component in ("", ".", "..") for component in value.split("/")[1:]):
        raise ManifestError(f"{label} contains a non-canonical component")
    return value


def _namespace_path(value: Any, label: str) -> str:
    value = _absolute_path(value, label)
    if value != "/tools" and not value.startswith("/tools/"):
        raise ManifestError(f"{label} is outside /tools")
    return value


def _probe_hex(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ManifestError(f"{label} is not a string")
    if "\x00" in value:
        raise ManifestError(f"{label} contains NUL")
    try:
        value.encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise ManifestError(f"{label} is not valid UTF-8") from error
    if len(value) > MAX_PROBE_BYTES * 2 or len(value) % 2:
        raise ManifestError(f"{label} exceeds its decoded-byte bound")
    if not re.fullmatch(r"[0-9a-f]*", value):
        raise ManifestError(f"{label} is not lowercase hex")
    try:
        bytes.fromhex(value)
    except ValueError as error:
        raise ManifestError(f"{label} is not hex") from error
    return value


def _argv(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_ARGV:
        raise ManifestError(f"{label} is not a bounded argv")
    result = []
    total = 0
    for index, argument in enumerate(value):
        argument = _string(argument, f"{label}[{index}]")
        total += len(argument.encode("utf-8"))
        result.append(argument)
    if total > MAX_ARGV_BYTES:
        raise ManifestError(f"{label} exceeds its encoded-byte bound")
    return result


def _name(value: Any, label: str) -> str:
    value = _string(value, label)
    if "/" in value or value in (".", ".."):
        raise ManifestError(f"{label} is not a single path component")
    return value


def _digest_tree_preimage(node: Mapping[str, Any], *, root: bool) -> bytes:
    kind = node["kind"]
    if kind == "file":
        return bytes.fromhex(node["sha256"])
    prefix = (
        b"align-llm-digest-tree-v2"
        + b"\0"
        + node["mode"].encode("ascii")
        + node["staged_mode"].encode("ascii")
        + struct.pack(">Q", node["size"])
    )
    for child in node["entries"]:
        # The root has no own name field; each child still contributes its
        # single-component name to the structural preimage.
        name = child["name"].encode("utf-8")
        child_kind = b"\x01" if child["kind"] == "file" else b"\x02"
        prefix += (
            child_kind
            + struct.pack(">I", len(name))
            + name
            + child["mode"].encode("ascii")
            + child["staged_mode"].encode("ascii")
            + struct.pack(">Q", child["size"])
            + bytes.fromhex(child["sha256"])
        )
    return prefix


def structural_digest(node: Mapping[str, Any]) -> str:
    """Return the structural digest of a validated file or directory node."""

    if node["kind"] == "file":
        return node["sha256"]
    return hashlib.sha256(_digest_tree_preimage(node, root=True)).hexdigest()


def _validate_tree_node(
    node: Any,
    *,
    root: bool,
    depth: int,
    path: tuple[str, ...],
) -> TreeSummary:
    if not isinstance(node, Mapping):
        raise ManifestError("digest-tree node is not an object")
    _fields(node, DIGEST_ROOT_FIELDS if root else DIGEST_ENTRY_FIELDS, "digest-tree node")
    kind = _string(node["kind"], "digest-tree kind")
    if kind not in ("file", "dir"):
        raise ManifestError("digest-tree kind is not file or dir")
    if not root:
        _name(node["name"], "digest-tree name")
    mode = _mode(node["mode"], "digest-tree mode")
    staged_mode = _mode(node["staged_mode"], "digest-tree staged_mode")
    size = _uint(node["size"], "digest-tree size")
    if size > MAX_FILE_BYTES:
        raise ManifestError("digest-tree file exceeds its size bound")
    digest = _hex64(node["sha256"], "digest-tree sha256")
    entries = node["entries"]
    if not isinstance(entries, list):
        raise ManifestError("digest-tree entries is not an array")
    if depth > MAX_DEPTH:
        raise ManifestError("digest-tree exceeds its depth bound")
    if kind == "file":
        if entries:
            raise ManifestError("digest-tree file has children")
        return TreeSummary(0 if root else 1, size, depth)
    if size != 0:
        raise ManifestError("digest-tree directory has nonzero size")
    if root and path:
        raise ManifestError("digest-tree root has a path")
    names: list[bytes] = []
    count = 1 if not root else 0
    total = 0
    max_depth = depth
    for child in entries:
        if not isinstance(child, Mapping):
            raise ManifestError("digest-tree child is not an object")
        child_name = _name(child.get("name"), "digest-tree name")
        child_bytes = child_name.encode("utf-8")
        if names and child_bytes <= names[-1]:
            raise ManifestError("digest-tree entries are not raw-byte sorted")
        names.append(child_bytes)
        summary = _validate_tree_node(
            child,
            root=False,
            depth=depth + 1,
            path=path + (child_name,),
        )
        count += summary.entry_count
        total += summary.total_size
        if count > MAX_ENTRIES or total > MAX_CACHE_BYTES:
            raise ManifestError("digest-tree exceeds its cardinality or byte bound")
        max_depth = max(max_depth, summary.depth)
    expected = hashlib.sha256(_digest_tree_preimage(node, root=root)).hexdigest()
    if digest != expected:
        raise ManifestError("digest-tree structural digest mismatch")
    return TreeSummary(count, total, max_depth)


def validate_digest_tree(value: Mapping[str, Any], *, root_kind: str | None = None) -> TreeSummary:
    if not isinstance(value, Mapping):
        raise ManifestError("digest-tree root is not an object")
    if root_kind is not None and value.get("kind") != root_kind:
        raise ManifestError("digest-tree root kind does not match binding kind")
    return _validate_tree_node(value, root=True, depth=0, path=())


def serialized_digest(value: Mapping[str, Any]) -> str:
    validate_digest_tree(value)
    return sha256_hex(canonical_json_bytes(value))


def _validate_cache_paths(node: Mapping[str, Any], path: tuple[str, ...] = ()) -> None:
    for child in node["entries"]:
        child_path = path + (child["name"],)
        is_prefix_ancestor = any(
            parts[: len(child_path)] == child_path for parts in _CACHE_PREFIX_PARTS
        )
        is_below_prefix = any(
            len(child_path) > len(parts) and child_path[: len(parts)] == parts
            for parts in _CACHE_PREFIX_PARTS
        )
        is_prefix_directory = any(child_path == parts for parts in _CACHE_PREFIX_PARTS)
        if child["kind"] == "file":
            if not is_below_prefix:
                raise ManifestError("cache file is outside an allowed prefix")
        elif not (is_prefix_ancestor or is_below_prefix or is_prefix_directory):
            raise ManifestError("cache directory is outside an allowed prefix")
        _validate_cache_paths(child, child_path)


def _validate_cache_modes(node: Mapping[str, Any]) -> None:
    mode = int(node["mode"], 8)
    staged = node["staged_mode"]
    if node["kind"] == "dir":
        if mode & 0o7000 or mode & 0o700 != 0o700 or staged != "0700":
            raise ManifestError("cache directory mode mapping is invalid")
    elif mode & 0o7111 or mode & 0o400 == 0 or staged != "0600":
        raise ManifestError("cache file mode mapping is invalid")
    for child in node["entries"]:
        _validate_cache_modes(child)


def validate_cache_manifest(value: Mapping[str, Any]) -> TreeSummary:
    if not isinstance(value, Mapping):
        raise ManifestError("cache manifest is not an object")
    _fields(value, CACHE_MANIFEST_FIELDS, "cache manifest")
    _exact_uint(value["schema_version"], 2, "cache manifest schema_version")
    prefixes = value["allowed_prefixes"]
    if prefixes != list(ALLOWED_CACHE_PREFIXES):
        raise ManifestError("cache allowlist is not the fixed ordered list")
    summary = validate_digest_tree(value["root"], root_kind="dir")
    _validate_cache_paths(value["root"])
    _validate_cache_modes(value["root"])
    if _uint(value["entry_count"], "cache entry_count") != summary.entry_count:
        raise ManifestError("cache entry_count does not match the tree")
    if _uint(value["total_size"], "cache total_size") != summary.total_size:
        raise ManifestError("cache total_size does not match the tree")
    if summary.total_size > MAX_CACHE_BYTES:
        raise ManifestError("cache total size exceeds its bound")
    return summary


def _validate_tool(value: Any, index: int) -> None:
    if not isinstance(value, Mapping):
        raise ManifestError(f"tool[{index}] is not an object")
    _fields(value, TOOL_FIELDS, f"tool[{index}]")
    name = _name(value["name"], f"tool[{index}].name")
    path = _absolute_path(value["path"], f"tool[{index}].path")
    namespace = _namespace_path(value["namespace_path"], f"tool[{index}].namespace_path")
    if namespace != f"/tools/{name}":
        raise ManifestError("tool namespace_path does not match name")
    if _mode(value["mode"], f"tool[{index}].mode") != "0755":
        raise ManifestError("tool mode is not 0755")
    _hex64(value["sha256"], f"tool[{index}].sha256")
    argv = _argv(value["argv"], f"tool[{index}].argv")
    if not argv or argv[0] != path:
        raise ManifestError("tool argv does not start with its host path")
    _probe_hex(value["stdout"], f"tool[{index}].stdout")
    _probe_hex(value["stderr"], f"tool[{index}].stderr")


def _validate_runtime_tree_modes(node: Mapping[str, Any]) -> None:
    if node["kind"] == "dir":
        if node["staged_mode"] != "0700":
            raise ManifestError("runtime directory staged mode is not 0700")
    else:
        expected = "0555" if int(node["mode"], 8) & 0o111 else "0444"
        if node["staged_mode"] != expected:
            raise ManifestError("runtime file staged mode does not match its source mode")
    for child in node["entries"]:
        _validate_runtime_tree_modes(child)


def _validate_runtime(value: Any, index: int) -> TreeSummary:
    if not isinstance(value, Mapping):
        raise ManifestError(f"runtime_binding[{index}] is not an object")
    _fields(value, RUNTIME_FIELDS, f"runtime_binding[{index}]")
    _absolute_path(value["source"], f"runtime_binding[{index}].source")
    target = _absolute_path(value["target"], f"runtime_binding[{index}].target")
    kind = _string(value["kind"], f"runtime_binding[{index}].kind")
    if kind not in ("file", "tree"):
        raise ManifestError("runtime binding kind is invalid")
    summary = validate_digest_tree(value["manifest"], root_kind="file" if kind == "file" else "dir")
    _validate_runtime_tree_modes(value["manifest"])
    if _hex64(value["manifest_sha256"], f"runtime_binding[{index}].manifest_sha256") != serialized_digest(
        value["manifest"]
    ):
        raise ManifestError("runtime binding serialized digest mismatch")
    reserved = ("/align-src", "/workspace", "/tools", "/cargo", "/target")
    if any(target == path or target.startswith(path + "/") for path in reserved):
        raise ManifestError("runtime target overlaps a reserved namespace")
    return summary


def validate_manifest(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise ManifestError("manifest is not an object")
    _fields(value, MANIFEST_FIELDS, "manifest")
    _exact_uint(value["schema_version"], 2, "manifest schema_version")
    controller = value["controller"]
    if not isinstance(controller, Mapping):
        raise ManifestError("controller is not an object")
    _fields(controller, CONTROLLER_FIELDS, "controller")
    if _string(controller["path"], "controller.path") != CONTROLLER_PATH:
        raise ManifestError("controller identity is invalid")
    _exact_uint(controller["api"], 1, "controller.api")
    bootstrap = value["bootstrap"]
    if not isinstance(bootstrap, Mapping):
        raise ManifestError("bootstrap is not an object")
    _fields(bootstrap, BOOTSTRAP_FIELDS, "bootstrap")
    if _string(bootstrap["path"], "bootstrap.path") != BOOTSTRAP_PATH:
        raise ManifestError("bootstrap identity is invalid")
    _exact_uint(bootstrap["api"], 1, "bootstrap.api")
    _hex64(bootstrap["sha256"], "bootstrap.sha256")
    platform = value["platform"]
    if not isinstance(platform, Mapping):
        raise ManifestError("platform is not an object")
    _fields(platform, PLATFORM_FIELDS, "platform")
    architecture = platform.get("architecture")
    expected_platform = {
        "os": "linux",
        "architecture": architecture,
        "kernel_minimum": "6.8",
        "python_minimum": "3.12",
        "make_minimum": "4.3",
    }
    if architecture not in ("x86_64", "aarch64") or dict(platform) != expected_platform:
        raise ManifestError("platform profile is not a supported native Linux profile")
    tools = value["tools"]
    if not isinstance(tools, list) or not tools or len(tools) > MAX_TOOLS:
        raise ManifestError("manifest tools inventory is empty or too large")
    names: set[str] = set()
    namespaces: set[str] = set()
    ordered_names: list[str] = []
    for index, tool in enumerate(tools):
        _validate_tool(tool, index)
        name = tool["name"]
        namespace = tool["namespace_path"]
        if name in names or namespace in namespaces:
            raise ManifestError("manifest tool identity is duplicated")
        names.add(name)
        namespaces.add(namespace)
        ordered_names.append(name)
    if tuple(ordered_names) != TOOL_INVENTORY:
        raise ManifestError("manifest tool inventory is not the fixed ordered list")
    bindings = value["runtime_bindings"]
    if not isinstance(bindings, list) or len(bindings) > MAX_RUNTIME_BINDINGS:
        raise ManifestError("runtime binding inventory is too large")
    targets: list[str] = []
    runtime_entry_count = 0
    runtime_total_size = 0
    for index, binding in enumerate(bindings):
        summary = _validate_runtime(binding, index)
        targets.append(binding["target"])
        runtime_entry_count += summary.entry_count
        runtime_total_size += summary.total_size
        if runtime_entry_count > MAX_ENTRIES or runtime_total_size > MAX_CACHE_BYTES:
            raise ManifestError("runtime bindings exceed their aggregate bounds")
    for index, target in enumerate(targets):
        for other in targets[index + 1 :]:
            if target == other or target.startswith(other + "/") or other.startswith(target + "/"):
                raise ManifestError("runtime binding targets overlap")
    cache = value["cargo_cache"]
    if not isinstance(cache, Mapping):
        raise ManifestError("cargo_cache is not an object")
    _fields(cache, CACHE_FIELDS, "cargo_cache")
    _absolute_path(cache["root"], "cargo_cache.root")
    cache_manifest_path = _absolute_path(cache["manifest"], "cargo_cache.manifest")
    cache_root = cache["root"]
    if cache_manifest_path == cache_root or cache_manifest_path.startswith(cache_root + "/"):
        raise ManifestError("cargo cache manifest is inside its cache root")
    _hex64(cache["manifest_sha256"], "cargo_cache.manifest_sha256")
    cache_entry_count = _uint(cache["entry_count"], "cargo_cache.entry_count")
    if cache_entry_count > MAX_ENTRIES:
        raise ManifestError("cargo_cache.entry_count exceeds its bound")


def parse_manifest_bytes(raw: bytes) -> Mapping[str, Any]:
    return parse_canonical_json(raw, limit=MANIFEST_LIMIT)


def parse_cache_manifest_bytes(raw: bytes) -> Mapping[str, Any]:
    return parse_canonical_json(raw, limit=MANIFEST_LIMIT)


def validate_manifest_bytes(raw: bytes) -> Mapping[str, Any]:
    value = parse_manifest_bytes(raw)
    validate_manifest(value)
    return value


def validate_cache_manifest_bytes(raw: bytes) -> Mapping[str, Any]:
    value = parse_cache_manifest_bytes(raw)
    validate_cache_manifest(value)
    return value
