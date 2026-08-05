#!/usr/bin/env python3
"""Strict wire helpers for the Section 9 runner attestations.

This module intentionally has no repository, filesystem, subprocess, or network
behavior.  The image supervisor, bootstrap, and repository worker use it as the
common parser for their signed DSSE predicates.  Keeping the wire layer pure
makes its byte-level contract independently testable before process ownership
and source materialization are added.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Mapping


IMAGE_PREDICATE_TYPE = "https://align-llm.dev/attestations/runner-image/v1"
INVOCATION_PREDICATE_TYPE = (
    "https://align-llm.dev/attestations/runner-invocation/v1"
)
IMAGE_KEY_ID = "align-llm-runner-image-v1"
RUN_KEY_ID = "align-llm-run-v1"
CONTROLLER_PATH = "scripts/fresh-align-compiler"
MAX_STRING_BYTES = 4096
MAX_PREDICATE_BYTES = 64 * 1024
MAX_ENVELOPE_BYTES = 256 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class WireError(ValueError):
    """The input is not a canonical, schema-valid attestation value."""


def _escape_string(value: str) -> str:
    pieces: list[str] = ['"']
    for character in value:
        codepoint = ord(character)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise WireError("unpaired surrogate in string")
        if character == '"':
            pieces.append('\\"')
        elif character == "\\":
            pieces.append("\\\\")
        elif character == "\b":
            pieces.append("\\b")
        elif character == "\t":
            pieces.append("\\t")
        elif character == "\n":
            pieces.append("\\n")
        elif character == "\f":
            pieces.append("\\f")
        elif character == "\r":
            pieces.append("\\r")
        elif 0 < codepoint < 0x20:
            pieces.append(f"\\u00{codepoint:02X}")
        else:
            pieces.append(character)
    pieces.append('"')
    return "".join(pieces)


def _render_json(value: Any, level: int = 0) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise WireError("negative integer in canonical JSON")
        return str(value)
    if isinstance(value, str):
        return _escape_string(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        indent = " " * (2 * (level + 1))
        closing_indent = " " * (2 * level)
        rendered = [indent + _render_json(item, level + 1) for item in value]
        return "[\n" + ",\n".join(rendered) + "\n" + closing_indent + "]"
    if isinstance(value, Mapping):
        if not value:
            return "{}"
        rendered = []
        indent = " " * (2 * (level + 1))
        closing_indent = " " * (2 * level)
        for key, child in value.items():
            if not isinstance(key, str):
                raise WireError("object key is not a string")
            rendered.append(
                indent + _escape_string(key) + ": " + _render_json(child, level + 1)
            )
        return "{\n" + ",\n".join(rendered) + "\n" + closing_indent + "}"
    raise WireError(f"unsupported JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize an ordered JSON object with the Section 9 grammar."""

    if not isinstance(value, Mapping):
        raise WireError("canonical root is not an object")
    try:
        return (_render_json(value) + "\n").encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise WireError("canonical JSON is not valid UTF-8") from error


def _duplicate_check(pairs: list[tuple[str, Any]]) -> OrderedDict[str, Any]:
    result: OrderedDict[str, Any] = OrderedDict()
    for key, value in pairs:
        if key in result:
            raise WireError(f"duplicate object field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise WireError(f"non-finite JSON number: {value}")


def parse_canonical_json(raw: bytes, *, limit: int = MAX_PREDICATE_BYTES) -> OrderedDict[str, Any]:
    """Parse and byte-check a canonical UTF-8 JSON object."""

    if not isinstance(raw, bytes) or len(raw) > limit:
        raise WireError("JSON input exceeds its byte bound")
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_check,
            parse_constant=_reject_constant,
            parse_float=lambda _: (_ for _ in ()).throw(WireError("floating number")),
        )
        if not isinstance(value, OrderedDict):
            raise WireError("JSON root is not an object")
        canonical = canonical_json_bytes(value)
    except WireError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise WireError("invalid UTF-8 JSON") from error
    except RecursionError as error:
        raise WireError("JSON nesting exceeds its bounded parser depth") from error
    if canonical != raw:
        raise WireError("JSON is not canonical")
    return value


def _strict_b64url(value: Any, *, name: str, expected_size: int | None = None) -> bytes:
    if not isinstance(value, str) or not value or "=" in value:
        raise WireError(f"{name} is not unpadded base64url")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as error:
        raise WireError(f"{name} is not ASCII") from error
    if not re.fullmatch(rb"[A-Za-z0-9_-]+", encoded) or len(encoded) % 4 == 1:
        raise WireError(f"{name} is not unpadded base64url")
    try:
        decoded = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
    except Exception as error:  # pragma: no cover - defensive library boundary
        raise WireError(f"{name} cannot be decoded") from error
    if base64.urlsafe_b64encode(decoded).rstrip(b"=") != encoded:
        raise WireError(f"{name} has non-canonical base64url bits")
    if expected_size is not None and len(decoded) != expected_size:
        raise WireError(f"{name} has the wrong decoded size")
    return decoded


def _fields(value: Mapping[str, Any], expected: tuple[str, ...], name: str) -> None:
    if tuple(value.keys()) != expected:
        raise WireError(f"{name} has the wrong field order or field set")


def _string(value: Any, name: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise WireError(f"{name} is not a string")
    if "\x00" in value:
        raise WireError(f"{name} contains NUL")
    try:
        size = len(value.encode("utf-8", "strict"))
    except UnicodeEncodeError as error:
        raise WireError(f"{name} is not valid UTF-8") from error
    if size > MAX_STRING_BYTES:
        raise WireError(f"{name} exceeds its string bound")
    return value


def _sha256(value: Any, name: str) -> str:
    value = _string(value, name)
    if not HEX64.fullmatch(value):
        raise WireError(f"{name} is not lowercase SHA-256 hex")
    return value


def _sha256_tagged(value: Any, name: str) -> str:
    value = _string(value, name)
    if not value.startswith("sha256:") or not HEX64.fullmatch(value[7:]):
        raise WireError(f"{name} is not a tagged SHA-256 digest")
    return value


def _absolute_path(value: Any, name: str) -> str:
    value = _string(value, name)
    if not value.startswith("/") or value.endswith("/"):
        raise WireError(f"{name} is not an absolute canonical path")
    components = value.split("/")[1:]
    if any(component in ("", ".", "..") for component in components):
        raise WireError(f"{name} contains a non-canonical component")
    return value


def _version(value: Any, name: str) -> str:
    value = _string(value, name)
    if not SEMVER.fullmatch(value):
        raise WireError(f"{name} is not major.minor.patch")
    return value


def _relative_path(value: Any, name: str) -> str:
    value = _string(value, name)
    if value.startswith("/") or any(component == "" for component in value.split("/")):
        raise WireError(f"{name} is not a non-empty relative path")
    if any(component == "." for component in value.split("/")):
        raise WireError(f"{name} contains a dot component")
    return value


def validate_image_predicate(value: Mapping[str, Any]) -> Mapping[str, Any]:
    fields = (
        "schema_version",
        "image_digest",
        "image_name",
        "provenance_digest",
        "verifier_identity",
        "verifier_version",
        "verifier_key_id",
        "verifier_key_sha256",
        "supervisor_path",
        "supervisor_sha256",
        "bootstrap_path",
        "bootstrap_sha256",
        "manifest_path",
        "manifest_sha256",
    )
    _fields(value, fields, "image predicate")
    if value["schema_version"] != 1 or isinstance(value["schema_version"], bool):
        raise WireError("image predicate schema version is not 1")
    _sha256_tagged(value["image_digest"], "image_digest")
    _string(value["image_name"], "image_name")
    _sha256_tagged(value["provenance_digest"], "provenance_digest")
    if _string(value["verifier_identity"], "verifier_identity") != IMAGE_KEY_ID:
        raise WireError("wrong image verifier identity")
    _version(value["verifier_version"], "verifier_version")
    if _string(value["verifier_key_id"], "verifier_key_id") != IMAGE_KEY_ID:
        raise WireError("wrong image verifier key id")
    _sha256(value["verifier_key_sha256"], "verifier_key_sha256")
    _absolute_path(value["supervisor_path"], "supervisor_path")
    _sha256(value["supervisor_sha256"], "supervisor_sha256")
    _absolute_path(value["bootstrap_path"], "bootstrap_path")
    _sha256(value["bootstrap_sha256"], "bootstrap_sha256")
    _absolute_path(value["manifest_path"], "manifest_path")
    _sha256(value["manifest_sha256"], "manifest_sha256")
    return value


def validate_invocation_predicate(value: Mapping[str, Any]) -> Mapping[str, Any]:
    fields = (
        "schema_version",
        "image_attestation_sha256",
        "manifest_sha256",
        "repository_object_format",
        "repository_head",
        "align_repo_relative",
        "controller_path",
        "controller_sha256",
        "supervisor_identity",
        "supervisor_version",
        "supervisor_key_id",
        "supervisor_key_sha256",
    )
    _fields(value, fields, "invocation predicate")
    if value["schema_version"] != 1 or isinstance(value["schema_version"], bool):
        raise WireError("invocation predicate schema version is not 1")
    _sha256(value["image_attestation_sha256"], "image_attestation_sha256")
    _sha256(value["manifest_sha256"], "manifest_sha256")
    object_format = _string(value["repository_object_format"], "repository_object_format")
    if object_format not in ("sha1", "sha256"):
        raise WireError("unsupported repository object format")
    head = _string(value["repository_head"], "repository_head")
    expected_length = 40 if object_format == "sha1" else 64
    if len(head) != expected_length or not re.fullmatch(r"[0-9a-f]+", head):
        raise WireError("repository_head has the wrong width or case")
    _relative_path(value["align_repo_relative"], "align_repo_relative")
    if _string(value["controller_path"], "controller_path") != CONTROLLER_PATH:
        raise WireError("wrong controller path")
    _sha256(value["controller_sha256"], "controller_sha256")
    if _string(value["supervisor_identity"], "supervisor_identity") != IMAGE_KEY_ID:
        raise WireError("wrong supervisor identity")
    _version(value["supervisor_version"], "supervisor_version")
    if _string(value["supervisor_key_id"], "supervisor_key_id") != RUN_KEY_ID:
        raise WireError("wrong supervisor key id")
    _sha256(value["supervisor_key_sha256"], "supervisor_key_sha256")
    return value


def dsse_pae(payload_type: str, predicate: bytes) -> bytes:
    payload_type = _string(payload_type, "payloadType")
    if "\n" in payload_type or "\r" in payload_type:
        raise WireError("payloadType contains a line break")
    return (
        b"DSSEv1 "
        + str(len(payload_type.encode("utf-8"))).encode("ascii")
        + b" "
        + payload_type.encode("utf-8")
        + b" "
        + str(len(predicate)).encode("ascii")
        + b" "
        + predicate
    )


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


# Ed25519 parameters from RFC 8032.  The implementation is intentionally
# self-contained so the wire verifier does not depend on a Python package or
# a mutable host executable.
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = ((y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q)) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if (x * x - xx) % _Q != 0:
        raise WireError("invalid Ed25519 point")
    if x & 1:
        x = _Q - x
    return x


_BASE = (_xrecover((4 * pow(5, _Q - 2, _Q)) % _Q), (4 * pow(5, _Q - 2, _Q)) % _Q)
_IDENTITY = (0, 1)


def _point_add(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    product = _D * x1 * x2 * y1 * y2 % _Q
    inverse_plus = pow(1 + product, _Q - 2, _Q)
    inverse_minus = pow(1 - product, _Q - 2, _Q)
    return (
        (x1 * y2 + x2 * y1) * inverse_plus % _Q,
        (y1 * y2 + x1 * x2) * inverse_minus % _Q,
    )


def _scalar_mult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = _IDENTITY
    addend = point
    while scalar:
        if scalar & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        scalar >>= 1
    return result


def _decode_point(encoded: bytes) -> tuple[int, int]:
    if len(encoded) != 32:
        raise WireError("Ed25519 point has the wrong size")
    value = int.from_bytes(encoded, "little")
    sign = value >> 255
    y = value & ((1 << 255) - 1)
    if y >= _Q:
        raise WireError("non-canonical Ed25519 point")
    x = _xrecover(y)
    if (x & 1) != sign:
        x = _Q - x
    if (-x * x + y * y - 1 - _D * x * x * y * y) % _Q != 0:
        raise WireError("invalid Ed25519 point")
    return x, y


def _encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    value = y | ((x & 1) << 255)
    return value.to_bytes(32, "little")


def verify_ed25519(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        public_point = _decode_point(public_key)
        r_bytes = signature[:32]
        r_point = _decode_point(r_bytes)
        scalar = int.from_bytes(signature[32:], "little")
        if scalar >= _L:
            return False
        challenge = int.from_bytes(
            hashlib.sha512(r_bytes + public_key + message).digest(), "little"
        ) % _L
        expected = _point_add(r_point, _scalar_mult(public_point, challenge))
        actual = _scalar_mult(_BASE, scalar)
        return _encode_point(actual) == _encode_point(expected)
    except (WireError, OverflowError, ValueError):
        return False


def ed25519_public_key(seed: bytes) -> bytes:
    """Derive the canonical Ed25519 public key for one 32-byte private seed."""

    if not isinstance(seed, bytes) or len(seed) != 32:
        raise WireError("Ed25519 private seed has the wrong size")
    digest = hashlib.sha512(seed).digest()
    scalar_bytes = bytearray(digest[:32])
    scalar_bytes[0] &= 248
    scalar_bytes[31] &= 63
    scalar_bytes[31] |= 64
    scalar = int.from_bytes(scalar_bytes, "little")
    return _encode_point(_scalar_mult(_BASE, scalar))


def sign_ed25519(seed: bytes, message: bytes) -> bytes:
    """Create a deterministic RFC 8032 Ed25519 signature from a private seed."""

    if not isinstance(message, bytes):
        raise WireError("Ed25519 message is not bytes")
    public_key = ed25519_public_key(seed)
    digest = hashlib.sha512(seed).digest()
    scalar_bytes = bytearray(digest[:32])
    scalar_bytes[0] &= 248
    scalar_bytes[31] &= 63
    scalar_bytes[31] |= 64
    scalar = int.from_bytes(scalar_bytes, "little")
    nonce = int.from_bytes(hashlib.sha512(digest[32:] + message).digest(), "little") % _L
    encoded_r = _encode_point(_scalar_mult(_BASE, nonce))
    challenge = int.from_bytes(
        hashlib.sha512(encoded_r + public_key + message).digest(), "little"
    ) % _L
    encoded_s = ((nonce + challenge * scalar) % _L).to_bytes(32, "little")
    signature = encoded_r + encoded_s
    if not verify_ed25519(public_key, message, signature):
        raise WireError("Ed25519 self-check failed")
    return signature


def signed_envelope(
    predicate: Mapping[str, Any], *, payload_type: str, key_id: str, seed: bytes
) -> bytes:
    """Serialize and sign one canonical single-signature DSSE envelope."""

    predicate_bytes = canonical_json_bytes(predicate)
    signature = sign_ed25519(seed, dsse_pae(payload_type, predicate_bytes))
    return canonical_json_bytes(
        OrderedDict(
            [
                ("payloadType", payload_type),
                (
                    "payload",
                    base64.urlsafe_b64encode(predicate_bytes)
                    .rstrip(b"=")
                    .decode("ascii"),
                ),
                (
                    "signatures",
                    [
                        OrderedDict(
                            [
                                ("keyid", key_id),
                                (
                                    "sig",
                                    base64.urlsafe_b64encode(signature)
                                    .rstrip(b"=")
                                    .decode("ascii"),
                                ),
                            ]
                        )
                    ],
                ),
            ]
        )
    )


@dataclass(frozen=True)
class VerifiedEnvelope:
    payload_type: str
    predicate_bytes: bytes
    predicate: Mapping[str, Any]
    key_id: str
    signature: bytes


def verify_envelope(
    raw: bytes,
    *,
    expected_payload_type: str,
    expected_key_id: str,
    public_key: bytes,
    predicate_validator: Any,
) -> VerifiedEnvelope:
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise WireError("DSSE envelope exceeds its byte bound")
    envelope = parse_canonical_json(raw, limit=MAX_ENVELOPE_BYTES)
    _fields(envelope, ("payloadType", "payload", "signatures"), "DSSE envelope")
    payload_type = _string(envelope["payloadType"], "payloadType")
    if payload_type != expected_payload_type:
        raise WireError("unexpected DSSE predicate type")
    predicate_bytes = _strict_b64url(envelope["payload"], name="payload")
    if len(predicate_bytes) > MAX_PREDICATE_BYTES:
        raise WireError("predicate exceeds its byte bound")
    predicate = parse_canonical_json(predicate_bytes)
    predicate_validator(predicate)
    signatures = envelope["signatures"]
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise WireError("DSSE envelope must contain exactly one signature")
    signature_object = signatures[0]
    if not isinstance(signature_object, Mapping):
        raise WireError("DSSE signature is not an object")
    _fields(signature_object, ("keyid", "sig"), "DSSE signature")
    key_id = _string(signature_object["keyid"], "keyid")
    if key_id != expected_key_id:
        raise WireError("unexpected DSSE key id")
    signature = _strict_b64url(signature_object["sig"], name="sig", expected_size=64)
    if not verify_ed25519(public_key, dsse_pae(payload_type, predicate_bytes), signature):
        raise WireError("Ed25519 signature verification failed")
    return VerifiedEnvelope(payload_type, predicate_bytes, predicate, key_id, signature)
