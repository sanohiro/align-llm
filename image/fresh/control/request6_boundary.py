#!/usr/bin/env python3
"""Non-evidence Request 6 boundary dispatcher.

The boundary deliberately stops before reading or executing the future
consumer worker.  It authenticates the inherited image inputs and retained
path identity, then rejects every worker-presence state with the same bounded
revision result.
"""

from __future__ import annotations

import os
import posixpath
import stat
import sys
from typing import Sequence

from fresh_attestation import (
    IMAGE_KEY_ID,
    IMAGE_PREDICATE_TYPE,
    WireError,
    sha256_hex,
    validate_image_predicate,
    verify_envelope,
)
from fresh_image_control import (
    IMAGE_PUBLIC_KEY_PATH,
    MANIFEST_PATH,
    MAX_ATTESTATION_BYTES,
    MAX_MANIFEST_BYTES,
    ControlError,
    _canonical_relative_from_absolute,
    _close_descriptors_except,
    _identity,
    _normalize_absolute,
    _read_key,
    _read_sealed,
    _boundary_worker_presence,
)
from fresh_manifest import validate_manifest_bytes


BOUNDARY_ENVIRONMENT = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
    "HOME": "/nonexistent",
    "TMPDIR": "/tmp",
}
EXPECTED_DESCRIPTORS = {0, 1, 2, 4, 6, 8, 18}


class BoundaryFailure(Exception):
    def __init__(self, phase: str) -> None:
        super().__init__(phase)
        self.phase = phase


def _descriptor_set() -> set[int]:
    descriptors: set[int] = set()
    try:
        names = os.listdir("/proc/self/fd")
    except OSError as error:
        raise BoundaryFailure("input") from error
    for name in names:
        try:
            descriptor = int(name)
            os.fstat(descriptor)
        except (OSError, ValueError):
            continue
        descriptors.add(descriptor)
    return descriptors


def _strict_arguments(arguments: Sequence[str]) -> tuple[str, str]:
    values = list(arguments)
    if len(values) != 14:
        raise BoundaryFailure("input")
    expected = [
        "--mode",
        "ordinary-adoption-boundary",
        "--project-root-fd",
        "4",
        "--image-attestation-fd",
        "6",
        "--manifest-fd",
        "8",
        "--align-repo-root-fd",
        "18",
        "--align-repo-absolute",
        None,
        "--align-repo-relative",
        None,
    ]
    for actual, wanted in zip(values, expected):
        if wanted is not None and actual != wanted:
            raise BoundaryFailure("input")
    try:
        absolute = _normalize_absolute(values[11])
        relative = values[13]
        if _canonical_relative_from_absolute(absolute) != relative:
            raise BoundaryFailure("input")
    except BoundaryFailure:
        raise
    except (ControlError, OSError, UnicodeError) as error:
        raise BoundaryFailure("input") from error
    if any(ord(character) < 0x20 for character in relative):
        raise BoundaryFailure("input")
    return absolute, relative


def _require_environment() -> None:
    if dict(os.environ) != BOUNDARY_ENVIRONMENT:
        raise BoundaryFailure("input")


def _validate_retained_paths(
    project_fd: int, align_fd: int, absolute: str, relative: str
) -> None:
    try:
        project_stat = os.fstat(project_fd)
        align_stat = os.fstat(align_fd)
        if not stat.S_ISDIR(project_stat.st_mode) or not stat.S_ISDIR(align_stat.st_mode):
            raise BoundaryFailure("revision")
        project_path = os.readlink(f"/proc/self/fd/{project_fd}")
        align_path = os.readlink(f"/proc/self/fd/{align_fd}")
        if " (deleted)" in project_path or " (deleted)" in align_path:
            raise BoundaryFailure("revision")
        project_path = _normalize_absolute(project_path)
        align_path = _normalize_absolute(align_path)
        if align_path != absolute or posixpath.relpath(align_path, project_path) != relative:
            raise BoundaryFailure("revision")
        if _identity(project_fd) == _identity(align_fd):
            raise BoundaryFailure("revision")
    except BoundaryFailure:
        raise
    except (ControlError, OSError) as error:
        raise BoundaryFailure("revision") from error


def _verify_inputs(project_fd: int, align_fd: int, absolute: str, relative: str) -> None:
    _validate_retained_paths(project_fd, align_fd, absolute, relative)
    try:
        image_raw = _read_sealed(
            6,
            limit=MAX_ATTESTATION_BYTES,
            expected_name="align-llm-image",
        )
        manifest_raw = _read_sealed(
            8,
            limit=MAX_MANIFEST_BYTES,
            expected_name="align-llm-manifest",
        )
        manifest = validate_manifest_bytes(manifest_raw)
        image_key = _read_key(IMAGE_PUBLIC_KEY_PATH, private=False, owner=0)
        verified = verify_envelope(
            image_raw,
            expected_payload_type=IMAGE_PREDICATE_TYPE,
            expected_key_id=IMAGE_KEY_ID,
            public_key=image_key,
            predicate_validator=validate_image_predicate,
        )
        if verified.predicate["manifest_path"] != MANIFEST_PATH:
            raise BoundaryFailure("input")
        if verified.predicate["manifest_sha256"] != sha256_hex(manifest_raw):
            raise BoundaryFailure("input")
        if not manifest["runtime_bindings"]:
            raise BoundaryFailure("input")
    except BoundaryFailure:
        raise
    except (ControlError, OSError, WireError, KeyError, TypeError) as error:
        raise BoundaryFailure("input") from error


def main(arguments: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if arguments is None else arguments)
    try:
        absolute, relative = _strict_arguments(values)
        _require_environment()
        if _descriptor_set() != EXPECTED_DESCRIPTORS:
            raise BoundaryFailure("input")
        _close_descriptors_except(EXPECTED_DESCRIPTORS)
        if _descriptor_set() != EXPECTED_DESCRIPTORS:
            raise BoundaryFailure("input")
        _verify_inputs(4, 18, absolute, relative)
        try:
            _boundary_worker_presence(4)
        except ControlError as error:
            raise BoundaryFailure("revision") from error
    except BoundaryFailure as error:
        try:
            os.write(2, f"json-scan adoption: ERROR {error.phase}\n".encode("ascii"))
        except OSError:
            pass
        return 1
    except Exception:
        try:
            os.write(2, b"json-scan adoption: ERROR input\n")
        except OSError:
            pass
        return 1
    return 1


__all__ = ["main"]
