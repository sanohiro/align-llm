"""Independent C7-PersistedResult fixture vectors for the bounded functional smokes.

`docs/specs/c7-persisted-result.md` sections 4.3, 4.4, 5.1, and 10.2 are the normative source.
Everything here is transcribed from those sections and computed with Python's own integer
arithmetic, `hashlib`, and an ordered field table. It never imports, parses, or derives a value
from `src/persisted_result.align`, and it never calls Python's generic JSON serializer for the
canonical wire.

This module is the fixture owner for the six checked-in `c7-persisted-result-*-smoke` runners
only. The full generated/differential/mutation corpus and its seeded reference remain owned by the
separate `persisted-result-qualification` slice named in section 12.
"""

import hashlib

SCHEMA_VERSION = 1
INPUT_KIND = "C7_VERIFICATION_INPUT"
RESULT_KIND = "C7_PERSISTED_RESULT"
ALGORITHM = "bounded-bucket-v1"
FAIL_DIAGNOSTIC = "expected does not match observed"

# Section 4.4 minimum text vector: escaped quote, literal slash, escaped backslash, the five
# literal control spellings, a semantic NUL byte, and a four-byte UTF-8 scalar. 64 bytes.
ESCAPED_NOTE = "quote:\" slash:/ backslash:\\ controls:\\b\\f\\n\\r\\t NUL:\x00 emoji:\U0001F600"

# Section 4.4 normative digests. They are assertions about the wire, not values derived from it.
GOLDEN_INPUT_SHA256 = "6de733d453b56f83c4dbe11406e72996cc52a3a236b8d221d383133b77bb89d2"
GOLDEN_CONTENT_SHA256 = "a0160d3677ecac64c1682e3802e01462e178412702a8ca1cdf6c55c5841b379a"
GOLDEN_RESULT_SHA256 = "8fb29a7205886c45cff455b3061c605c83afc5e8fd3be58f37c00fa8d997fab5"


def quote_string(value: str) -> str:
    """The Request 7 escape grammar, walked over Unicode scalar values."""
    parts = ['"']
    for character in value:
        point = ord(character)
        if character == '"':
            parts.append('\\"')
        elif character == "\\":
            parts.append("\\\\")
        elif character == "\b":
            parts.append("\\b")
        elif character == "\f":
            parts.append("\\f")
        elif character == "\n":
            parts.append("\\n")
        elif character == "\r":
            parts.append("\\r")
        elif character == "\t":
            parts.append("\\t")
        elif point < 0x20:
            parts.append("\\u%04x" % point)
        elif 0xD800 <= point <= 0xDFFF:
            raise ValueError("surrogate code point is not valid UTF-8 text")
        else:
            parts.append(character)
    parts.append('"')
    return "".join(parts)


def _object(fields: list[tuple[str, str]]) -> str:
    return "{" + ",".join(f'{quote_string(name)}:{text}' for name, text in fields) + "}"


def _integer(value: int) -> str:
    return "%d" % value


def encode_input(
    case_id: str,
    left: int,
    right: int,
    lower_bound: int,
    upper_bound: int,
    expected: int,
    note: str | None = None,
    schema_version: int = SCHEMA_VERSION,
    artifact_kind: str = INPUT_KIND,
    algorithm: str = ALGORITHM,
) -> str:
    """Section 4.1 declaration order; `None` is omitted and `""` is present."""
    fields = [
        ("schema_version", _integer(schema_version)),
        ("artifact_kind", quote_string(artifact_kind)),
        ("case_id", quote_string(case_id)),
        ("algorithm", quote_string(algorithm)),
        ("left", _integer(left)),
        ("right", _integer(right)),
        ("lower_bound", _integer(lower_bound)),
        ("upper_bound", _integer(upper_bound)),
        ("expected", _integer(expected)),
    ]
    if note is not None:
        fields.append(("note", quote_string(note)))
    return _object(fields)


def encode_result(
    case_id: str,
    status: str,
    left: int,
    right: int,
    lower_bound: int,
    upper_bound: int,
    expected: int,
    observed: int,
    input_sha256: str,
    note: str | None,
    diagnostic: str | None,
    content_sha256: str,
    schema_version: int = SCHEMA_VERSION,
    artifact_kind: str = RESULT_KIND,
    algorithm: str = ALGORITHM,
) -> str:
    """Section 4.2 declaration order; `content_sha256` is blank in the preimage mode."""
    fields = [
        ("schema_version", _integer(schema_version)),
        ("artifact_kind", quote_string(artifact_kind)),
        ("case_id", quote_string(case_id)),
        ("algorithm", quote_string(algorithm)),
        ("status", quote_string(status)),
        ("left", _integer(left)),
        ("right", _integer(right)),
        ("lower_bound", _integer(lower_bound)),
        ("upper_bound", _integer(upper_bound)),
        ("expected", _integer(expected)),
        ("observed", _integer(observed)),
        ("input_sha256", quote_string(input_sha256)),
    ]
    if note is not None:
        fields.append(("note", quote_string(note)))
    if diagnostic is not None:
        fields.append(("diagnostic", quote_string(diagnostic)))
    fields.append(("content_sha256", quote_string(content_sha256)))
    return _object(fields)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def bounded_bucket(left: int, right: int, lower_bound: int, upper_bound: int) -> int:
    """Section 5.1, written from the specification rather than from the Align source."""
    raw = left + right
    if raw < lower_bound:
        return 0
    if raw < upper_bound:
        return 1
    return 2


def expected_pair(
    case_id: str,
    left: int,
    right: int,
    lower_bound: int,
    upper_bound: int,
    expected: int,
    note: str | None = None,
) -> tuple[str, str, str]:
    """Return the exact input bytes, artifact bytes, and status for one valid case."""
    source = encode_input(case_id, left, right, lower_bound, upper_bound, expected, note)
    observed = bounded_bucket(left, right, lower_bound, upper_bound)
    status = "PASS" if observed == expected else "FAIL"
    diagnostic = None if observed == expected else FAIL_DIAGNOSTIC
    preimage = encode_result(
        case_id,
        status,
        left,
        right,
        lower_bound,
        upper_bound,
        expected,
        observed,
        digest(source),
        note,
        diagnostic,
        "",
    )
    artifact = encode_result(
        case_id,
        status,
        left,
        right,
        lower_bound,
        upper_bound,
        expected,
        observed,
        digest(source),
        note,
        diagnostic,
        digest(preimage),
    )
    return source, artifact, status


def require_golden() -> None:
    """Fail fast when a fixture edit drifts from the section 4.4 normative vectors."""
    source, artifact, status = expected_pair("upper-equal", 4, 5, 0, 9, 2, ESCAPED_NOTE)
    if status != "PASS":
        raise SystemExit("c7 fixtures: the golden vector is not a PASS case")
    if len(ESCAPED_NOTE.encode("utf-8")) != 64:
        raise SystemExit("c7 fixtures: the escaped note vector is not 64 bytes")
    if digest(source) != GOLDEN_INPUT_SHA256:
        raise SystemExit(f"c7 fixtures: input_sha256 drifted to {digest(source)}")
    preimage = encode_result(
        "upper-equal", "PASS", 4, 5, 0, 9, 2, 2, GOLDEN_INPUT_SHA256, ESCAPED_NOTE, None, ""
    )
    if digest(preimage) != GOLDEN_CONTENT_SHA256:
        raise SystemExit(f"c7 fixtures: content_sha256 drifted to {digest(preimage)}")
    if digest(artifact) != GOLDEN_RESULT_SHA256:
        raise SystemExit(f"c7 fixtures: result_sha256 drifted to {digest(artifact)}")
