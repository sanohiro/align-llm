#!/usr/bin/env python3
"""Canonical source-manifest wire validation for the Section 9 worker.

This module owns only the source-manifest bytes and semantic bounds.  It does
not inspect Git, open filesystem paths, follow symlinks, or materialize a
private tree; those operations remain in the descriptor-relative worker slice.
"""

from __future__ import annotations

import re
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


SOURCE_MANIFEST_LIMIT = 64 * 1024 * 1024
MAX_ENTRIES = 200_000
MAX_DEPTH = 64
MAX_PATH_BYTES = MAX_STRING_BYTES // 2
MAX_SYMLINK_BYTES = 2_048
MAX_FILE_BYTES = 536_870_912
MAX_TOTAL_SOURCE_BYTES = 4 * 1024 * 1024 * 1024
MAX_RAW_PATH_LINK_BYTES = 64 * 1024 * 1024
MAX_GIT_MODE = {"dir": "040000", "file": None, "symlink": "120000"}
HEX = re.compile(r"^[0-9a-f]+$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MODE = re.compile(r"^[0-7]{4}$")

SOURCE_FIELDS = (
    "schema_version",
    "kind",
    "revision",
    "tree_id",
    "object_format",
    "index_sha256",
    "root_mode",
    "root_staged_mode",
    "entries",
    "exceptions",
)
ENTRY_FIELDS = (
    "path_hex",
    "kind",
    "mode",
    "staged_mode",
    "git_mode",
    "git_object",
    "size",
    "sha256",
    "symlink_target_hex",
)
EXCEPTION_FIELDS = ("git", "target", "main")


class SourceManifestError(WireError):
    """The source-manifest value violates the Section 9 wire contract."""


@dataclass(frozen=True)
class SourceSummary:
    entry_count: int
    total_file_bytes: int
    depth: int
    raw_path_link_bytes: int


def _fields(value: Mapping[str, Any], expected: tuple[str, ...], label: str) -> None:
    if tuple(value.keys()) != expected:
        raise SourceManifestError(f"{label} has the wrong field order or field set")


def _string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise SourceManifestError(f"{label} is not a string")
    if "\x00" in value:
        raise SourceManifestError(f"{label} contains NUL")
    try:
        if len(value.encode("utf-8", "strict")) > MAX_STRING_BYTES:
            raise SourceManifestError(f"{label} exceeds its string bound")
    except UnicodeEncodeError as error:
        raise SourceManifestError(f"{label} is not valid UTF-8") from error
    return value


def _uint(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= 2**64:
        raise SourceManifestError(f"{label} is not an unsigned 64-bit integer")
    return value


def _exact_uint(value: Any, expected: int, label: str) -> None:
    if _uint(value, label) != expected:
        raise SourceManifestError(f"{label} is not {expected}")


def _mode(value: Any, label: str) -> str:
    value = _string(value, label)
    if not MODE.fullmatch(value) or int(value, 8) > 0o777:
        raise SourceManifestError(f"{label} is not a four-digit mode below 01000")
    return value


def _object_id(value: Any, label: str, width: int) -> str:
    value = _string(value, label)
    if len(value) != width or not re.fullmatch(r"[0-9a-f]+", value):
        raise SourceManifestError(f"{label} has the wrong object-id width or case")
    return value


def _sha256(value: Any, label: str) -> str:
    value = _string(value, label)
    if not HEX64.fullmatch(value):
        raise SourceManifestError(f"{label} is not lowercase SHA-256 hex")
    return value


def _hex_bytes(value: Any, label: str, *, max_bytes: int) -> bytes:
    value = _string(value, label)
    if len(value) % 2 or not value or not HEX.fullmatch(value):
        raise SourceManifestError(f"{label} is not non-empty lowercase hex")
    if len(value) // 2 > max_bytes:
        raise SourceManifestError(f"{label} exceeds its byte bound")
    try:
        decoded = bytes.fromhex(value)
    except ValueError as error:
        raise SourceManifestError(f"{label} is not hex") from error
    if b"\x00" in decoded:
        raise SourceManifestError(f"{label} contains NUL")
    return decoded


def _relative_path(value: Any, label: str) -> tuple[bytes, tuple[bytes, ...]]:
    raw = _hex_bytes(value, label, max_bytes=MAX_PATH_BYTES)
    if raw.startswith(b"/"):
        raise SourceManifestError(f"{label} is absolute")
    components = tuple(raw.split(b"/"))
    if any(not component or component in (b".", b"..", b".git") for component in components):
        raise SourceManifestError(f"{label} has an invalid relative component")
    return raw, components


def _root_mode(value: Any, label: str) -> str:
    value = _mode(value, label)
    mode = int(value, 8)
    if mode & 0o7000 or mode & 0o700 != 0o700:
        raise SourceManifestError(f"{label} does not provide the required source-root mode")
    return value


def _directory_modes(mode_value: Any, staged_value: Any, label: str) -> None:
    mode = _root_mode(mode_value, f"{label}.mode")
    if _mode(staged_value, f"{label}.staged_mode") != "0700":
        raise SourceManifestError(f"{label} staged mode is not 0700")
    if mode == "0000":  # defensive: _root_mode already rejects this
        raise SourceManifestError(f"{label} source mode is empty")


def _validate_entry(
    value: Any,
    *,
    index: int,
    object_width: int,
    prior_path: bytes | None,
    prior_paths: Mapping[bytes, str],
) -> tuple[bytes, tuple[bytes, ...], SourceSummary]:
    if not isinstance(value, Mapping):
        raise SourceManifestError(f"source entry[{index}] is not an object")
    _fields(value, ENTRY_FIELDS, f"source entry[{index}]")
    path, components = _relative_path(value["path_hex"], f"source entry[{index}].path_hex")
    if prior_path is not None and path <= prior_path:
        raise SourceManifestError("source entries are not strictly raw-byte sorted")
    if len(components) > MAX_DEPTH:
        raise SourceManifestError("source entry exceeds its depth bound")
    for depth in range(1, len(components)):
        ancestor = b"/".join(components[:depth])
        ancestor_kind = prior_paths.get(ancestor)
        if ancestor_kind is None:
            raise SourceManifestError("source entry is missing a parent directory")
        if ancestor_kind != "dir":
            raise SourceManifestError("a source file or symlink is an entry ancestor")
    kind = _string(value["kind"], f"source entry[{index}].kind")
    if kind not in ("dir", "file", "symlink"):
        raise SourceManifestError("source entry kind is invalid")
    git_object = _object_id(value["git_object"], f"source entry[{index}].git_object", object_width)
    git_mode = value["git_mode"]
    size = _uint(value["size"], f"source entry[{index}].size")
    total_file_bytes = 0
    target_bytes = 0
    if kind == "dir":
        if git_mode != MAX_GIT_MODE["dir"]:
            raise SourceManifestError("source directory Git mode is invalid")
        _directory_modes(value["mode"], value["staged_mode"], f"source entry[{index}]")
        if size != 0 or value["sha256"] is not None or value["symlink_target_hex"] is not None:
            raise SourceManifestError("source directory has non-directory fields")
    elif kind == "file":
        mode = _mode(value["mode"], f"source entry[{index}].mode")
        staged = _mode(value["staged_mode"], f"source entry[{index}].staged_mode")
        expected = {"0644": ("100644", "0444"), "0755": ("100755", "0555")}.get(mode)
        if expected is None or git_mode != expected[0] or staged != expected[1]:
            raise SourceManifestError("source file mode mapping is invalid")
        if size > MAX_FILE_BYTES or value["symlink_target_hex"] is not None:
            raise SourceManifestError("source file size or symlink field is invalid")
        _sha256(value["sha256"], f"source entry[{index}].sha256")
        total_file_bytes = size
    else:
        if git_mode != MAX_GIT_MODE["symlink"] or value["mode"] is not None or value["staged_mode"] is not None:
            raise SourceManifestError("source symlink mode mapping is invalid")
        target = _hex_bytes(
            value["symlink_target_hex"],
            f"source entry[{index}].symlink_target_hex",
            max_bytes=MAX_SYMLINK_BYTES,
        )
        if size != len(target) or value["sha256"] is None:
            raise SourceManifestError("source symlink size or digest is invalid")
        digest = _sha256(value["sha256"], f"source entry[{index}].sha256")
        if digest != sha256_hex(target):
            raise SourceManifestError("source symlink digest does not match target bytes")
        target_bytes = len(target)
    if not isinstance(git_mode, str) or git_mode not in ("040000", "100644", "100755", "120000"):
        raise SourceManifestError("source Git mode is invalid")
    return path, components, SourceSummary(1, total_file_bytes, len(components), len(path) + target_bytes)


def validate_source_manifest(value: Mapping[str, Any]) -> SourceSummary:
    if not isinstance(value, Mapping):
        raise SourceManifestError("source manifest is not an object")
    _fields(value, SOURCE_FIELDS, "source manifest")
    _exact_uint(value["schema_version"], 1, "source manifest schema_version")
    kind = _string(value["kind"], "source manifest kind")
    if kind not in ("project-source", "align-source"):
        raise SourceManifestError("source manifest kind is invalid")
    object_format = _string(value["object_format"], "source manifest object_format")
    if object_format not in ("sha1", "sha256"):
        raise SourceManifestError("source manifest object format is invalid")
    if kind == "align-source" and object_format != "sha1":
        raise SourceManifestError("Align source must use SHA-1 object IDs")
    object_width = 40 if object_format == "sha1" else 64
    _object_id(value["revision"], "source manifest revision", object_width)
    _object_id(value["tree_id"], "source manifest tree_id", object_width)
    _sha256(value["index_sha256"], "source manifest index_sha256")
    _root_mode(value["root_mode"], "source manifest root_mode")
    if _mode(value["root_staged_mode"], "source manifest root_staged_mode") != "0700":
        raise SourceManifestError("source manifest root staged mode is not 0700")
    exceptions = value["exceptions"]
    if not isinstance(exceptions, Mapping):
        raise SourceManifestError("source manifest exceptions is not an object")
    _fields(exceptions, EXCEPTION_FIELDS, "source manifest exceptions")
    expected_main = "root-file-output" if kind == "project-source" else None
    if (
        exceptions["git"] != "root-git-control"
        or exceptions["target"] != "root-directory-output"
        or exceptions["main"] != expected_main
    ):
        raise SourceManifestError("source manifest exception labels are invalid")
    entries = value["entries"]
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise SourceManifestError("source manifest entries are missing or too large")
    prior_path: bytes | None = None
    prior_paths: dict[bytes, str] = {}
    count = 0
    total_file_bytes = 0
    depth = 0
    raw_path_link_bytes = 0
    for index, entry in enumerate(entries):
        path, components, summary = _validate_entry(
            entry,
            index=index,
            object_width=object_width,
            prior_path=prior_path,
            prior_paths=prior_paths,
        )
        if components[0] in (b"target", b"main"):
            raise SourceManifestError("source output exception leaked into entries")
        prior_path = path
        prior_paths[path] = entry["kind"]
        count += summary.entry_count
        total_file_bytes += summary.total_file_bytes
        depth = max(depth, summary.depth)
        raw_path_link_bytes += summary.raw_path_link_bytes
        if total_file_bytes > MAX_TOTAL_SOURCE_BYTES or raw_path_link_bytes > MAX_RAW_PATH_LINK_BYTES:
            raise SourceManifestError("source manifest exceeds its byte bounds")
    return SourceSummary(count, total_file_bytes, depth, raw_path_link_bytes)


def parse_source_manifest_bytes(raw: bytes) -> Mapping[str, Any]:
    return parse_canonical_json(raw, limit=SOURCE_MANIFEST_LIMIT)


def canonical_source_manifest_bytes(value: Mapping[str, Any]) -> bytes:
    validate_source_manifest(value)
    raw = canonical_json_bytes(value)
    if len(raw) > SOURCE_MANIFEST_LIMIT:
        raise SourceManifestError("serialized source manifest exceeds its byte bound")
    return raw


def serialized_source_manifest_digest(value: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_source_manifest_bytes(value))


def validate_source_manifest_bytes(raw: bytes) -> Mapping[str, Any]:
    value = parse_source_manifest_bytes(raw)
    validate_source_manifest(value)
    return value
