#!/usr/bin/env python3
"""Small image-owned handoff supervisor for the ordinary Request 6 profile."""

from __future__ import annotations

import base64
import hashlib
import os
import socket
import sys
from typing import Sequence

from fresh_attestation import (
    RUN_KEY_ID,
    WireError,
    validate_ordinary_adoption_predicate,
    verify_envelope,
)
from fresh_image_control import (
    ORDINARY_ENVIRONMENT,
    ORDINARY_PREDICATE_TYPE,
    _read_key,
    _read_sealed,
    _run_controlled_child,
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


def _strict(arguments: Sequence[str]) -> None:
    expected = [
        "--mode", "ordinary-adoption", "--project-root-fd", "4",
        "--align-repo-root-fd", "18", "--capsule-fd", "12", "--worker-fd", "13",
        "--invocation-nonce-fd", "15", "--supervisor-channel-fd", "16",
        "--image-attestation-fd", "6", "--manifest-fd", "8",
    ]
    if list(arguments) != expected:
        raise NamespaceFailure("input")
    if dict(os.environ) != ORDINARY_ENVIRONMENT:
        raise NamespaceFailure("input")


def run(arguments: Sequence[str]) -> int:
    _strict(arguments)
    capsule = _read_sealed(
        12,
        limit=262_144,
        expected_name="align-llm-ordinary-adoption-capsule",
    )
    worker = _read_sealed(
        13,
        limit=4_194_304,
        expected_name="align-llm-ordinary-adoption-worker",
    )
    nonce = _read_sealed(
        15,
        limit=32,
        expected_name="align-llm-ordinary-adoption-nonce",
    )
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
    try:
        proof = channel.recv(32)
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    if len(proof) != 32:
        raise NamespaceFailure("toolchain")
    expected = hashlib.sha256(
        b"align-llm/ordinary-adoption/worker-admission/v2\0"
        + bytes.fromhex(predicate["dispatch_ticket_sha256"])
        + nonce
        + hashlib.sha256(capsule).digest()
    ).digest()
    if proof != expected:
        raise NamespaceFailure("toolchain")
    result = _run_controlled_child(
        [
            "/usr/bin/python3",
            "-I",
            "-B",
            "/proc/self/fd/13",
            "--project-root-fd",
            "4",
            "--align-root-fd",
            "18",
            "--capsule-fd",
            "12",
            "--invocation-nonce-fd",
            "15",
            "--supervisor-channel-fd",
            "16",
        ],
        environment=ORDINARY_ENVIRONMENT,
        timeout=5_000,
        pass_fds=(4, 12, 13, 15, 16, 18),
        cwd="/proc/self/fd/4",
    )
    if result.returncode == 0:
        if result.stderr or result.stdout != b"json-scan adoption: PASS\n":
            raise NamespaceFailure("fixture")
        os.write(1, result.stdout)
        return 0
    if 1 <= result.returncode <= 6:
        raise NamespaceFailure(PHASE_NAMES[result.returncode - 1])
    raise NamespaceFailure("unobserved")


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        return run(list(sys.argv[1:] if arguments is None else arguments))
    except NamespaceFailure as error:
        return fail(error.phase)
    except Exception:
        return fail("toolchain")


if __name__ == "__main__":
    raise SystemExit(main())
