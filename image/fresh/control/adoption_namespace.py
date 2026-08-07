#!/usr/bin/env python3
"""Small image-owned handoff supervisor for the ordinary Request 6 profile."""

from __future__ import annotations

import base64
import hashlib
import os
import socket
import stat
import sys
from typing import Sequence

from fresh_attestation import (
    RUN_KEY_ID,
    WireError,
    validate_ordinary_adoption_predicate,
    verify_envelope,
)
from fresh_image_control import (
    ORDINARY_NAMESPACE_ENVIRONMENT,
    ORDINARY_PREDICATE_TYPE,
    _read_key,
)


PHASE_NAMES = ("input", "toolchain", "revision", "build", "fixture", "cleanup")


class NamespaceFailure(Exception):
    def __init__(self, phase: str) -> None:
        self.phase = phase


def fail(phase: str) -> int:
    if phase == "unobserved":
        return 7
    if phase not in PHASE_NAMES:
        return 7
    os.write(2, f"json-scan adoption: ERROR {phase}\n".encode("ascii"))
    return PHASE_NAMES.index(phase) + 1


def _strict(arguments: Sequence[str]) -> tuple[str, str, str]:
    expected = [
        "--capsule-path", "/authority/capsule",
        "--worker-path", "/authority/worker",
        "--nonce-path", "/authority/nonce",
        "--supervisor-channel-fd", "16",
        "--mode", "ordinary-adoption",
    ]
    if list(arguments) != expected:
        raise NamespaceFailure("input")
    if dict(os.environ) != ORDINARY_NAMESPACE_ENVIRONMENT:
        raise NamespaceFailure("input")
    return expected[1], expected[3], expected[5]


def _descriptor_set() -> set[int]:
    result: set[int] = set()
    for name in os.listdir("/proc/self/fd"):
        try:
            descriptor = int(name)
            os.fstat(descriptor)
            result.add(descriptor)
        except (OSError, ValueError):
            pass
    return result


def _read_authority(path: str, *, limit: int) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise NamespaceFailure("toolchain")
        raw = bytearray()
        while len(raw) <= limit:
            block = os.read(descriptor, min(65_536, limit + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        after = os.fstat(descriptor)
        if (
            len(raw) > limit
            or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_mode != after.st_mode
            or before.st_size != after.st_size
        ):
            raise NamespaceFailure("toolchain")
        return bytes(raw)
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    finally:
        os.close(descriptor)


def _receive_proof(channel: socket.socket) -> bytes:
    try:
        proof, _, flags, _ = channel.recvmsg(33, 0)
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    if flags & socket.MSG_TRUNC or len(proof) != 32:
        raise NamespaceFailure("toolchain")
    channel.setblocking(False)
    try:
        try:
            extra, _, flags, _ = channel.recvmsg(1, socket.MSG_PEEK)
        except BlockingIOError:
            extra = b""
            flags = 0
        if extra or flags & socket.MSG_TRUNC:
            raise NamespaceFailure("toolchain")
    finally:
        channel.setblocking(True)
    return proof


def run(arguments: Sequence[str]) -> int:
    capsule_path, worker_path, nonce_path = _strict(arguments)
    if _descriptor_set() != {0, 1, 2, 16}:
        raise NamespaceFailure("input")
    capsule = _read_authority(capsule_path, limit=262_144)
    worker = _read_authority(worker_path, limit=4_194_304)
    nonce = _read_authority(nonce_path, limit=32)
    if len(nonce) != 32:
        raise NamespaceFailure("toolchain")
    try:
        key = _read_key(
            "/usr/local/share/align-llm/run-verifier.pub", private=False, owner=0
        )
        verified = verify_envelope(
            capsule,
            expected_payload_type=ORDINARY_PREDICATE_TYPE,
            expected_key_id=RUN_KEY_ID,
            public_key=key,
            predicate_validator=validate_ordinary_adoption_predicate,
        )
    except (WireError, OSError, ValueError) as error:
        raise NamespaceFailure("toolchain") from error
    predicate = verified.predicate
    if predicate["worker_size"] != len(worker) or predicate["worker_sha256"] != hashlib.sha256(worker).hexdigest():
        raise NamespaceFailure("revision")
    if predicate["invocation_nonce"] != base64.urlsafe_b64encode(nonce).rstrip(b"=").decode("ascii"):
        raise NamespaceFailure("input")
    channel = socket.socket(fileno=16)
    proof = _receive_proof(channel)
    expected = hashlib.sha256(
        b"align-llm/ordinary-adoption/worker-admission/v2\0"
        + bytes.fromhex(predicate["dispatch_ticket_sha256"])
        + nonce
        + hashlib.sha256(capsule).digest()
    ).digest()
    if proof != expected:
        raise NamespaceFailure("toolchain")
    # This image/profile slice installs and authenticates the handoff surface, but it does
    # not yet own the bwrap staging, capability drop, descendant reaping, or namespace
    # tmpfs lifecycle required by the consumer worker.  Never run Make against a caller
    # pathname until that complete owner exists.
    raise NamespaceFailure("toolchain")


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        return run(list(sys.argv[1:] if arguments is None else arguments))
    except NamespaceFailure as error:
        return fail(error.phase)
    except Exception:
        return fail("toolchain")


if __name__ == "__main__":
    raise SystemExit(main())
