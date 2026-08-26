#!/usr/bin/env python3
"""Independent GGUF container writer for the R0-GGUF-INSPECT owner test.

`docs/specs/r0-gguf-inspection.md` section 4.1. This generator emits container bytes from its own
`struct`-packing tables and an ordered field list transcribed from section 2.4. It never imports,
parses, or derives a value from `src/gguf.align`: its expected-value tables are computed here, in
Python, which is what makes the owner a real differential check rather than a mirror of the decoder.

Fixtures are written into a caller-supplied temporary tree at test time and are never committed. A
model file, even a synthetic one, is a build input, not source.

Usage: gguf_fixture.py OUTPUT_DIR   (writes the fixtures plus `manifest.json`)
"""

import json
import math
import struct
import sys
from pathlib import Path

# Section 2.5.2 / 2.4.4 constants, transcribed from the plan rather than read from the decoder.
WINDOW_BYTES = 1048576
DEFAULT_ALIGNMENT = 32
ARRAY_PREVIEW = 8
MAX_STRING_BYTES = 16777216
MAX_ARRAY_ELEMENTS = 16777216
MAX_METADATA_KV = 4096
MAX_TENSORS = 1048576

UINT8, INT8, UINT16, INT16, UINT32, INT32, FLOAT32 = 0, 1, 2, 3, 4, 5, 6
BOOL, STRING, ARRAY, UINT64, INT64, FLOAT64 = 7, 8, 9, 10, 11, 12

TYPE_NAMES = {
    UINT8: "UINT8", INT8: "INT8", UINT16: "UINT16", INT16: "INT16",
    UINT32: "UINT32", INT32: "INT32", FLOAT32: "FLOAT32", BOOL: "BOOL",
    STRING: "STRING", ARRAY: "ARRAY", UINT64: "UINT64", INT64: "INT64",
    FLOAT64: "FLOAT64",
}

FIXED_WIDTH = {
    UINT8: 1, INT8: 1, BOOL: 1, UINT16: 2, INT16: 2,
    UINT32: 4, INT32: 4, FLOAT32: 4, UINT64: 8, INT64: 8, FLOAT64: 8,
}

GGML_NAMES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1",
    10: "Q2_K", 11: "Q3_K", 12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 15: "Q8_K",
    16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S", 20: "IQ4_NL", 21: "IQ3_S",
    22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16", 26: "I32", 27: "I64", 28: "F64",
    29: "IQ1_M", 30: "BF16", 34: "TQ1_0", 35: "TQ2_0",
}

U64_BIT63 = 0x8000000000000001


def f32_bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def f64_bits(value):
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def f32_of_bits(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def f64_of_bits(bits):
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


def marker_f32(bits):
    """A `value` that must round-trip through `f32` to the declared bit pattern."""
    return {"$f32": "%08x" % bits}


def marker_f64(bits):
    return {"$f64": "%016x" % bits}


def decode_or_none(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


class Scalar:
    """One fixed-width or string metadata value, plus its expected rendering."""

    def __init__(self, type_id, payload, value_expect, extra=None, raw_bytes=None):
        self.type_id = type_id
        self.payload = payload
        self.value_expect = value_expect
        self.extra = extra or {}
        self.raw_bytes = raw_bytes

    def preview_expect(self):
        if self.type_id == FLOAT32:
            return {"value": self.value_expect, "bits": self.extra["value_bits"]}
        if self.type_id == FLOAT64:
            return {"value": self.value_expect, "bits": self.extra["value_bits"]}
        if self.type_id == STRING and self.value_expect is None:
            return {
                "value": None,
                "invalid_utf8": True,
                "byte_length": self.extra["byte_length"],
            }
        return self.value_expect


def u8v(v):
    return Scalar(UINT8, struct.pack("<B", v), v)


def i8v(v):
    return Scalar(INT8, struct.pack("<b", v), v)


def u16v(v):
    return Scalar(UINT16, struct.pack("<H", v), v)


def i16v(v):
    return Scalar(INT16, struct.pack("<h", v), v)


def u32v(v):
    return Scalar(UINT32, struct.pack("<I", v), v)


def i32v(v):
    return Scalar(INT32, struct.pack("<i", v), v)


def u64v(v):
    return Scalar(UINT64, struct.pack("<Q", v), v)


def i64v(v):
    return Scalar(INT64, struct.pack("<q", v), v)


def f32v(value=None, bits=None):
    if bits is None:
        bits = f32_bits(value)
    finite = math.isfinite(f32_of_bits(bits))
    hexed = "%08x" % bits
    return Scalar(
        FLOAT32,
        struct.pack("<I", bits),
        marker_f32(bits) if finite else None,
        {"value_bits": hexed},
    )


def f64v(value=None, bits=None):
    if bits is None:
        bits = f64_bits(value)
    finite = math.isfinite(f64_of_bits(bits))
    hexed = "%016x" % bits
    return Scalar(
        FLOAT64,
        struct.pack("<Q", bits),
        marker_f64(bits) if finite else None,
        {"value_bits": hexed},
    )


def boolv(byte):
    return Scalar(BOOL, struct.pack("<B", byte), byte != 0)


def strv(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    decoded = decode_or_none(raw)
    extra = {} if decoded is not None else {"byte_length": len(raw)}
    return Scalar(STRING, struct.pack("<Q", len(raw)) + raw, decoded, extra, raw)


class Array:
    """One typed metadata array, plus its expected bounded rendering."""

    def __init__(self, element_type, elements, packed=None, count=None):
        self.type_id = ARRAY
        self.element_type = element_type
        self.elements = elements
        length = len(elements) if count is None else count
        body = bytearray()
        body += struct.pack("<I", element_type)
        body += struct.pack("<Q", length)
        if packed is None:
            for element in elements:
                body += element.payload
        else:
            body += packed
        self.payload = bytes(body)
        preview = [e.preview_expect() for e in elements[:ARRAY_PREVIEW]]
        self.value_expect = {
            "element_type": element_type,
            "element_type_name": TYPE_NAMES[element_type],
            "length": length,
            "preview": preview,
            "truncated": length > ARRAY_PREVIEW,
        }
        self.extra = {}
        self.raw_bytes = None


class Kv:
    def __init__(self, key, value):
        self.key_raw = key.encode("utf-8") if isinstance(key, str) else key
        self.value = value

    def expect(self, index):
        decoded = decode_or_none(self.key_raw)
        row = {
            "index": index,
            "key": decoded,
            "key_invalid_utf8": decoded is None,
            "type": self.value.type_id,
            "type_name": TYPE_NAMES[self.value.type_id],
            "value": self.value.value_expect,
        }
        if "value_bits" in self.value.extra:
            row["value_bits"] = self.value.extra["value_bits"]
        if self.value.type_id == STRING and self.value.value_expect is None:
            row["invalid_utf8"] = True
            row["byte_length"] = self.value.extra["byte_length"]
        return row


class Tensor:
    def __init__(self, name, dims, type_id, offset):
        self.name_raw = name.encode("utf-8") if isinstance(name, str) else name
        self.dims = dims
        self.type_id = type_id
        self.offset = offset

    def expect(self, index, data_offset):
        decoded = decode_or_none(self.name_raw)
        label = GGML_NAMES.get(self.type_id)
        return {
            "index": index,
            "name": decoded,
            "name_invalid_utf8": decoded is None,
            "n_dims": len(self.dims),
            "dims": list(self.dims),
            "type": self.type_id,
            "type_name": label,
            "type_known": label is not None,
            "offset": self.offset,
            "absolute_offset": data_offset + self.offset if data_offset >= 0 else -1,
        }


class Container:
    """A complete v2/v3 container. Records the absolute offset of every decoded field so the
    negative corpus can state an exact `error_offset` without guessing."""

    def __init__(self, kvs, tensors, version=3, alignment=DEFAULT_ALIGNMENT,
                 data_len=None, tensor_count=None, kv_count=None):
        self.kvs = kvs
        self.tensors = tensors
        self.version = version
        self.alignment = alignment
        self.kv_offsets = []
        self.tensor_offsets = []
        buf = bytearray()
        buf += b"GGUF"
        buf += struct.pack("<I", version)
        buf += struct.pack("<Q", len(tensors) if tensor_count is None else tensor_count)
        buf += struct.pack("<Q", len(kvs) if kv_count is None else kv_count)
        for kv in kvs:
            marks = {"key_len": len(buf)}
            buf += struct.pack("<Q", len(kv.key_raw))
            marks["key"] = len(buf)
            buf += kv.key_raw
            marks["type"] = len(buf)
            buf += struct.pack("<I", kv.value.type_id)
            marks["value"] = len(buf)
            if isinstance(kv.value, Array):
                marks["array_element_type"] = len(buf)
                marks["array_length"] = len(buf) + 4
                marks["array_elements"] = len(buf) + 12
            buf += kv.value.payload
            marks["end"] = len(buf)
            self.kv_offsets.append(marks)
        self.metadata_end = len(buf)
        for tensor in tensors:
            marks = {"name_len": len(buf)}
            buf += struct.pack("<Q", len(tensor.name_raw))
            marks["name"] = len(buf)
            buf += tensor.name_raw
            marks["n_dims"] = len(buf)
            buf += struct.pack("<I", len(tensor.dims))
            marks["dims"] = len(buf)
            for extent in tensor.dims:
                buf += struct.pack("<Q", extent)
            marks["type"] = len(buf)
            buf += struct.pack("<I", tensor.type_id)
            marks["offset"] = len(buf)
            buf += struct.pack("<Q", tensor.offset)
            marks["end"] = len(buf)
            self.tensor_offsets.append(marks)
        self.tensor_table_end = len(buf)
        remainder = self.tensor_table_end % alignment
        self.data_offset = (
            self.tensor_table_end if remainder == 0
            else self.tensor_table_end + alignment - remainder
        )
        buf += b"\0" * (self.data_offset - self.tensor_table_end)
        if data_len is None:
            data_len = max([t.offset for t in tensors], default=0) + alignment
        buf += b"\xa5" * data_len
        self.bytes = bytes(buf)

    def metadata_expect(self):
        return [kv.expect(i) for i, kv in enumerate(self.kvs)]

    def tensors_expect(self):
        return [t.expect(i, self.data_offset) for i, t in enumerate(self.tensors)]

    def architecture(self):
        for kv in self.kvs:
            if kv.key_raw == b"general.architecture" and kv.value.type_id == STRING:
                return kv.value.value_expect
        return None

    def alignment_source(self):
        for kv in self.kvs:
            if kv.key_raw == b"general.alignment":
                return "general.alignment"
        return "default"

    def top_expect(self, path, status="ok", error_code="", error_offset=-1):
        return {
            "schema_version": 1,
            "kind": "R0_GGUF_INSPECTION",
            "path": path,
            "status": status,
            "error_code": error_code,
            "error_offset": error_offset,
            "file_size": len(self.bytes),
            "header": {
                "magic": "GGUF",
                "version": self.version,
                "tensor_count": len(self.tensors),
                "metadata_kv_count": len(self.kvs),
            },
            "architecture": self.architecture(),
            "alignment": self.alignment,
            "alignment_source": self.alignment_source(),
            "metadata_end": self.metadata_end,
            "tensor_table_end": self.tensor_table_end,
            "data_offset": self.data_offset,
        }


ESCAPE_STRING = (
    b'quote:" backslash:\\ slash:/ '
    b"\x08\x0c\n\r\t"
    b"\x01"
    b"\x00"
    + "4byte:\U0001f600".encode("utf-8")
)


def full_kvs():
    return [
        Kv("general.architecture", strv("testarch")),
        Kv("kv.uint8", u8v(200)),
        Kv("kv.int8", i8v(-128)),
        Kv("kv.uint16", u16v(65535)),
        Kv("kv.int16", i16v(-32768)),
        Kv("kv.uint32", u32v(4294967295)),
        Kv("kv.int32", i32v(-2147483648)),
        Kv("kv.float32", f32v(1000000.0)),
        Kv("kv.bool.true", boolv(1)),
        Kv("kv.bool.nonzero", boolv(7)),
        Kv("kv.bool.false", boolv(0)),
        Kv("kv.string.escapes", strv(ESCAPE_STRING)),
        Kv("kv.string.invalid", strv(b"ok\xffbad")),
        Kv(b"bad\xffkey", strv("value-behind-a-bad-key")),
        Kv("kv.uint64.i64max", u64v(2 ** 63 - 1)),
        Kv("kv.int64.min", i64v(-(2 ** 63))),
        Kv("kv.float64.pi", f64v(math.pi)),
        Kv("kv.float32.zero", f32v(0.0)),
        Kv("kv.float32.negzero", f32v(-0.0)),
        Kv("kv.float32.max", f32v(bits=0x7F7FFFFF)),
        Kv("kv.float32.micro", f32v(1e-6)),
        Kv("kv.float64.subnormal", f64v(bits=1)),
        Kv("kv.float32.inf", f32v(bits=0x7F800000)),
        Kv("kv.float64.nan", f64v(bits=0x7FF8000000000000)),
        Kv("kv.array.i32.len0", Array(INT32, [])),
        Kv("kv.array.i32.len1", Array(INT32, [i32v(42)])),
        Kv("kv.array.i32.len8", Array(INT32, [i32v(v) for v in range(8)])),
        Kv("kv.array.i32.len9", Array(INT32, [i32v(v) for v in range(9)])),
        Kv("kv.array.str.len0", Array(STRING, [])),
        Kv("kv.array.str.len1", Array(STRING, [strv("a")])),
        Kv("kv.array.str.len8", Array(STRING, [strv("s%d" % v) for v in range(8)])),
        Kv("kv.array.str.len9", Array(STRING, [strv("s%d" % v) for v in range(9)])),
        Kv("kv.array.str.invalid", Array(STRING, [strv("good"), strv(b"\xff\xfe"), strv("tail")])),
        Kv("kv.array.f32", Array(FLOAT32, [f32v(0.5), f32v(-0.25), f32v(1e-6)])),
        Kv("kv.array.bool", Array(BOOL, [boolv(1), boolv(0), boolv(3)])),
        Kv("kv.array.u64", Array(UINT64, [u64v(1), u64v(2 ** 63 - 1)])),
    ]


def full_tensors():
    return [
        Tensor("t.one", [4], 0, 0),
        Tensor("t.two", [3584, 152064], 12, 32),
        Tensor("t.four", [2, 3, 4, 5], 199, 64),
        Tensor(b"bad\xffname", [7], 1, 96),
    ]


def padded_key(prefix, target_length):
    return prefix + "." + "p" * max(0, target_length - len(prefix) - 1)


def aligned_container():
    """A container whose tensor table already ends on an alignment boundary, so `data_offset`
    equals `tensor_table_end`."""
    for pad in range(1, 64):
        kvs = [Kv("general.architecture", strv("alignedarch")),
               Kv(padded_key("kv.pad", pad), u32v(1))]
        tensors = [Tensor("t.aligned", [2, 2], 0, 0)]
        candidate = Container(kvs, tensors)
        if candidate.tensor_table_end % DEFAULT_ALIGNMENT == 0:
            return candidate
    raise SystemExit("gguf_fixture: no aligned tensor-table end found")


def straddle_container(filler_length, tail_only=False):
    kvs = [
        Kv("general.architecture", strv("straddle")),
        Kv("kv.filler", strv(b"x" * filler_length)),
        Kv("kv.straddle.text", strv("boundary-value-\U0001f642")),
        Kv("kv.straddle.i32", i32v(-7)),
    ]
    tensors = [Tensor("t.straddle.name", [11, 22, 33], 1, 0)]
    return Container(kvs, tensors)


def write(out_dir, name, payload):
    path = out_dir / name
    path.write_bytes(payload)
    return path


def truncated_case(name, base, cut):
    """A container cut at one structural boundary. Below the 24-byte header the container is too
    small to describe itself at all; at or above it the walk fails on the first range it cannot
    read. Either way the requirement is the same: a recorded error code, never an abort."""
    if cut < 24:
        error = {"code": "GGUF_TOO_SMALL", "offset": 0}
    else:
        error = {"code": "GGUF_TRUNCATED", "offset": None, "offset_max": cut}
    return {
        "name": name,
        "file": name,
        "bytes": base.bytes[:cut],
        "exit": 1,
        "error": error,
    }


def patched(base, offset, replacement):
    raw = bytearray(base if isinstance(base, (bytes, bytearray)) else base.bytes)
    raw[offset:offset + len(replacement)] = replacement
    return bytes(raw)


def build(out_dir):
    cases = []

    # ---- positive: the complete synthetic container -----------------------------------------
    full = Container(full_kvs(), full_tensors())
    assert len(full.bytes) < 65536, len(full.bytes)
    cases.append({
        "name": "full",
        "file": "full.gguf",
        "bytes": full.bytes,
        "exit": 0,
        "top": full.top_expect("@PATH@"),
        "metadata": full.metadata_expect(),
        "tensors": full.tensors_expect(),
        # Section 4.3 property 1: for a fixture smaller than the window a single `pread` returns
        # the whole file, so `bytes_read` equals `file_size` exactly.
        "bytes_read": len(full.bytes),
        "field_order": True,
    })

    # ---- positive: alignment override and an already-aligned table end ------------------------
    align64 = Container(
        [Kv("general.architecture", strv("align64arch")), Kv("general.alignment", u32v(64))],
        [Tensor("t.a", [4], 0, 0), Tensor("t.b", [4], 0, 64)],
        alignment=64,
    )
    cases.append({
        "name": "alignment-override",
        "file": "align64.gguf",
        "bytes": align64.bytes,
        "exit": 0,
        "top": align64.top_expect("@PATH@"),
        "metadata": align64.metadata_expect(),
        "tensors": align64.tensors_expect(),
    })

    aligned = aligned_container()
    assert aligned.data_offset == aligned.tensor_table_end
    cases.append({
        "name": "data-offset-already-aligned",
        "file": "aligned.gguf",
        "bytes": aligned.bytes,
        "exit": 0,
        "top": aligned.top_expect("@PATH@"),
        "metadata": aligned.metadata_expect(),
        "tensors": aligned.tensors_expect(),
    })

    # ---- positive: an empty container --------------------------------------------------------
    empty = Container([], [], data_len=32)
    cases.append({
        "name": "empty-container",
        "file": "empty.gguf",
        "bytes": empty.bytes,
        "exit": 0,
        "top": empty.top_expect("@PATH@"),
        "metadata": [],
        "tensors": [],
    })

    # ---- positive: explicit window growth ----------------------------------------------------
    big_text = ("g" * (WINDOW_BYTES + 151424)).encode("ascii")
    growth = Container(
        [Kv("general.architecture", strv("growth")), Kv("kv.big", strv(big_text))],
        [Tensor("t.g", [1], 0, 0)],
    )
    cases.append({
        "name": "window-growth",
        "file": "growth.gguf",
        "bytes": growth.bytes,
        "exit": 0,
        "top": growth.top_expect("@PATH@"),
        "metadata": growth.metadata_expect(),
        "tensors": growth.tensors_expect(),
    })

    # ---- positive: skip accounting -----------------------------------------------------------
    skip_count = 400000
    skip_values = [v % 97 for v in range(skip_count)]
    skip_array = Array(
        INT32,
        [i32v(v) for v in skip_values[:ARRAY_PREVIEW]],
        packed=struct.pack("<%di" % skip_count, *skip_values),
        count=skip_count,
    )
    skip = Container(
        [Kv("general.architecture", strv("skiparch")), Kv("kv.array.i32.big", skip_array)],
        [Tensor("t.s", [8], 0, 0)],
    )
    array_elements_at = skip.kv_offsets[1]["array_elements"]
    array_end = array_elements_at + skip_count * FIXED_WIDTH[INT32]
    assert array_elements_at + ARRAY_PREVIEW * 4 < WINDOW_BYTES
    assert array_end > WINDOW_BYTES
    predicted = WINDOW_BYTES + (len(skip.bytes) - array_end)
    cases.append({
        "name": "skip-accounting",
        "file": "skip.gguf",
        "bytes": skip.bytes,
        "exit": 0,
        "top": skip.top_expect("@PATH@"),
        "metadata": skip.metadata_expect(),
        "tensors": skip.tensors_expect(),
        # The fixed-width tail is advanced over, never read: exactly `array_end - WINDOW_BYTES`
        # bytes of this file never enter `bytes_read`.
        "bytes_read": predicted,
        "bytes_read_lt_file_size": True,
        "skipped_bytes": array_end - WINDOW_BYTES,
    })

    # A STRING array of comparable size cannot be skipped: each element's length prefix is
    # interleaved with its bytes, so every window is read.
    control_count = 133000
    control_packed = bytearray()
    for v in range(control_count):
        control_packed += struct.pack("<Q", 4) + ("e%03d" % (v % 1000)).encode("ascii")
    control_array = Array(
        STRING,
        [strv("e%03d" % (v % 1000)) for v in range(ARRAY_PREVIEW)],
        packed=bytes(control_packed),
        count=control_count,
    )
    control = Container(
        [Kv("general.architecture", strv("controlarch")), Kv("kv.array.str.big", control_array)],
        [Tensor("t.c", [8], 0, 0)],
    )
    cases.append({
        "name": "skip-accounting-string-control",
        "file": "skip-control.gguf",
        "bytes": control.bytes,
        "exit": 0,
        "top": control.top_expect("@PATH@"),
        # Nothing but the trailing data section escapes the read: a STRING array
        # must be walked element by element.
        "unread_max": 64,
    })

    # ---- positive: refill boundary and borrow expiry ------------------------------------------
    reference = straddle_container(16)
    cases.append({
        "name": "straddle-reference",
        "file": "straddle-ref.gguf",
        "bytes": reference.bytes,
        "exit": 0,
        "top": reference.top_expect("@PATH@"),
        "metadata": reference.metadata_expect(),
        "tensors": reference.tensors_expect(),
        "straddle_role": "reference",
    })
    probe = straddle_container(0)
    targets = [
        ("key", probe.kv_offsets[2]["key"], len(b"kv.straddle.text")),
        ("string-value", probe.kv_offsets[2]["value"] + 8, len("boundary-value-\U0001f642".encode())),
        ("length-prefix", probe.kv_offsets[2]["key_len"], 8),
        ("dims", probe.tensor_offsets[0]["dims"], 24),
        ("tensor-name", probe.tensor_offsets[0]["name"], len(b"t.straddle.name")),
    ]
    for label, base, width in targets:
        filler = WINDOW_BYTES - base - width // 2
        assert filler > 0, (label, base, width)
        variant = straddle_container(filler)
        assert base + filler < WINDOW_BYTES < base + filler + width, (label, base, filler, width)
        cases.append({
            "name": "refill-boundary-" + label,
            "file": "straddle-%s.gguf" % label,
            "bytes": variant.bytes,
            "exit": 0,
            "top": variant.top_expect("@PATH@"),
            "metadata": variant.metadata_expect(),
            "tensors": variant.tensors_expect(),
            "straddle_role": "variant",
        })

    # ---- negative corpus: one fixture per section 2.6 row -------------------------------------
    cases.append({
        "name": "error-too-small",
        "file": "too-small.gguf",
        "bytes": b"GGUF\x03\x00\x00\x00\x01\x00",
        "exit": 1,
        "error": {"code": "GGUF_TOO_SMALL", "offset": 0},
        "top": {"header": {"magic": "", "version": -1, "tensor_count": -1,
                           "metadata_kv_count": -1},
                "metadata_end": -1, "tensor_table_end": -1, "data_offset": -1,
                "architecture": None, "alignment": 32, "alignment_source": "default"},
        "metadata": [],
        "tensors": [],
    })
    cases.append({
        "name": "error-bad-magic",
        "file": "bad-magic.gguf",
        "bytes": patched(full, 0, b"GGUX"),
        "exit": 1,
        "error": {"code": "GGUF_BAD_MAGIC", "offset": 0},
        "top": {"header": {"magic": "GGUX", "version": -1, "tensor_count": -1,
                           "metadata_kv_count": -1}},
        "metadata": [],
        "tensors": [],
    })
    cases.append({
        "name": "error-unsupported-version",
        "file": "version1.gguf",
        "bytes": patched(full, 4, struct.pack("<I", 1)),
        "exit": 1,
        "error": {"code": "GGUF_UNSUPPORTED_VERSION", "offset": 4},
        "top": {"header": {"magic": "GGUF", "version": 1}},
    })
    cases.append({
        "name": "error-count-overflow-tensor-count",
        "file": "overflow-tensor-count.gguf",
        "bytes": patched(full, 8, struct.pack("<Q", U64_BIT63)),
        "exit": 1,
        "error": {"code": "GGUF_COUNT_OVERFLOW", "offset": 8},
    })
    cases.append({
        "name": "error-count-implausible-kv",
        "file": "implausible-kv.gguf",
        "bytes": patched(full, 16, struct.pack("<Q", MAX_METADATA_KV + 1)),
        "exit": 1,
        "error": {"code": "GGUF_COUNT_IMPLAUSIBLE", "offset": 16},
    })
    cases.append({
        "name": "error-count-implausible-tensors",
        "file": "implausible-tensors.gguf",
        "bytes": patched(full, 8, struct.pack("<Q", MAX_TENSORS + 1)),
        "exit": 1,
        "error": {"code": "GGUF_COUNT_IMPLAUSIBLE", "offset": 8},
    })
    cases.append({
        "name": "error-string-too-large",
        "file": "string-too-large.gguf",
        "bytes": patched(full, full.kv_offsets[0]["key_len"],
                         struct.pack("<Q", MAX_STRING_BYTES + 1)),
        "exit": 1,
        "error": {"code": "GGUF_STRING_TOO_LARGE", "offset": full.kv_offsets[0]["key_len"]},
    })
    cases.append({
        "name": "error-unknown-value-type",
        "file": "unknown-value-type.gguf",
        "bytes": patched(full, full.kv_offsets[1]["type"], struct.pack("<I", 13)),
        "exit": 1,
        "error": {"code": "GGUF_UNKNOWN_VALUE_TYPE", "offset": full.kv_offsets[1]["type"]},
        # Exactly the one pair completed before the failure survives into the document.
        "metadata_count": 1,
        "tensors": [],
    })
    array_kv = 24  # kv.array.i32.len0
    cases.append({
        "name": "error-unknown-array-element-type",
        "file": "unknown-array-element.gguf",
        "bytes": patched(full, full.kv_offsets[array_kv]["array_element_type"],
                         struct.pack("<I", 13)),
        "exit": 1,
        "error": {"code": "GGUF_UNKNOWN_VALUE_TYPE",
                  "offset": full.kv_offsets[array_kv]["array_element_type"]},
        "metadata_count": array_kv,
    })
    cases.append({
        "name": "error-nested-array",
        "file": "nested-array.gguf",
        "bytes": patched(full, full.kv_offsets[array_kv]["array_element_type"],
                         struct.pack("<I", ARRAY)),
        "exit": 1,
        "error": {"code": "GGUF_NESTED_ARRAY",
                  "offset": full.kv_offsets[array_kv]["array_element_type"]},
    })
    uint64_kv = 14  # kv.uint64.i64max
    cases.append({
        "name": "error-value-overflow",
        "file": "value-overflow.gguf",
        "bytes": patched(full, full.kv_offsets[uint64_kv]["value"], struct.pack("<Q", U64_BIT63)),
        "exit": 1,
        "error": {"code": "GGUF_VALUE_OVERFLOW", "offset": full.kv_offsets[uint64_kv]["value"]},
        "metadata_count": uint64_kv,
    })
    cases.append({
        "name": "error-array-length-overflow",
        "file": "array-length-overflow.gguf",
        "bytes": patched(full, full.kv_offsets[array_kv]["array_length"],
                         struct.pack("<Q", U64_BIT63)),
        "exit": 1,
        "error": {"code": "GGUF_COUNT_OVERFLOW",
                  "offset": full.kv_offsets[array_kv]["array_length"]},
    })
    cases.append({
        "name": "error-array-length-implausible",
        "file": "array-length-implausible.gguf",
        "bytes": patched(full, full.kv_offsets[array_kv]["array_length"],
                         struct.pack("<Q", MAX_ARRAY_ELEMENTS + 1)),
        "exit": 1,
        "error": {"code": "GGUF_COUNT_IMPLAUSIBLE",
                  "offset": full.kv_offsets[array_kv]["array_length"]},
    })
    cases.append({
        "name": "error-string-length-overflow",
        "file": "string-length-overflow.gguf",
        "bytes": patched(full, full.kv_offsets[0]["value"], struct.pack("<Q", U64_BIT63)),
        "exit": 1,
        "error": {"code": "GGUF_COUNT_OVERFLOW", "offset": full.kv_offsets[0]["value"]},
    })

    bad_alignment_value = Container(
        [Kv("general.architecture", strv("badalign")), Kv("general.alignment", u32v(24))],
        [Tensor("t.a", [4], 0, 0)],
    )
    cases.append({
        "name": "error-bad-alignment-not-power-of-two",
        "file": "bad-alignment.gguf",
        "bytes": bad_alignment_value.bytes,
        "exit": 1,
        "error": {"code": "GGUF_BAD_ALIGNMENT",
                  "offset": bad_alignment_value.kv_offsets[1]["value"]},
    })
    bad_alignment_zero = Container(
        [Kv("general.alignment", u32v(0))], [Tensor("t.a", [4], 0, 0)],
    )
    cases.append({
        "name": "error-bad-alignment-zero",
        "file": "bad-alignment-zero.gguf",
        "bytes": bad_alignment_zero.bytes,
        "exit": 1,
        "error": {"code": "GGUF_BAD_ALIGNMENT",
                  "offset": bad_alignment_zero.kv_offsets[0]["value"]},
    })
    bad_alignment_type = Container(
        [Kv("general.alignment", i32v(64))], [Tensor("t.a", [4], 0, 0)],
    )
    cases.append({
        "name": "error-bad-alignment-type",
        "file": "bad-alignment-type.gguf",
        "bytes": bad_alignment_type.bytes,
        "exit": 1,
        "error": {"code": "GGUF_BAD_ALIGNMENT",
                  "offset": bad_alignment_type.kv_offsets[0]["value"]},
    })

    cases.append({
        "name": "error-bad-dims-zero",
        "file": "bad-dims-zero.gguf",
        "bytes": patched(full, full.tensor_offsets[0]["n_dims"], struct.pack("<I", 0)),
        "exit": 1,
        "error": {"code": "GGUF_BAD_DIMS", "offset": full.tensor_offsets[0]["n_dims"]},
        "tensors": [],
    })
    cases.append({
        "name": "error-bad-dims-five",
        "file": "bad-dims-five.gguf",
        "bytes": patched(full, full.tensor_offsets[0]["n_dims"], struct.pack("<I", 5)),
        "exit": 1,
        "error": {"code": "GGUF_BAD_DIMS", "offset": full.tensor_offsets[0]["n_dims"]},
    })
    cases.append({
        "name": "error-dims-overflow",
        "file": "dims-overflow.gguf",
        "bytes": patched(full, full.tensor_offsets[0]["dims"], struct.pack("<Q", U64_BIT63)),
        "exit": 1,
        "error": {"code": "GGUF_COUNT_OVERFLOW", "offset": full.tensor_offsets[0]["dims"]},
    })
    cases.append({
        "name": "error-tensor-name-length-overflow",
        "file": "tensor-name-overflow.gguf",
        "bytes": patched(full, full.tensor_offsets[0]["name_len"], struct.pack("<Q", U64_BIT63)),
        "exit": 1,
        "error": {"code": "GGUF_COUNT_OVERFLOW", "offset": full.tensor_offsets[0]["name_len"]},
    })
    cases.append({
        "name": "error-offset-overflow",
        "file": "offset-overflow.gguf",
        "bytes": patched(full, full.tensor_offsets[1]["offset"], struct.pack("<Q", U64_BIT63)),
        "exit": 1,
        "error": {"code": "GGUF_OFFSET_OVERFLOW", "offset": full.tensor_offsets[1]["offset"]},
        # Tensor 0 completed before the failure; tensor 1 did not.
        "tensors_count": 1,
    })
    cases.append({
        "name": "error-tensor-misaligned",
        "file": "tensor-misaligned.gguf",
        "bytes": patched(full, full.tensor_offsets[1]["offset"], struct.pack("<Q", 33)),
        "exit": 1,
        "error": {"code": "GGUF_TENSOR_MISALIGNED", "offset": full.tensor_offsets[1]["offset"]},
        "tensors_count": 1,
    })
    cases.append({
        "name": "error-tensor-out-of-range",
        "file": "tensor-out-of-range.gguf",
        "bytes": patched(full, full.tensor_offsets[1]["offset"],
                         struct.pack("<Q", 1 << 40)),
        "exit": 1,
        "error": {"code": "GGUF_TENSOR_OUT_OF_RANGE",
                  "offset": full.tensor_offsets[1]["offset"]},
        # Step 9 runs after the whole table decoded, so every entry survives into the document.
        "tensors_count": len(full.tensors),
    })

    # `GGUF_TRUNCATED` with an exactly predictable offset: the header is complete but the first
    # metadata key length is not present at all.
    cases.append({
        "name": "error-truncated-after-header",
        "file": "truncated-header.gguf",
        "bytes": full.bytes[:24],
        "exit": 1,
        "error": {"code": "GGUF_TRUNCATED", "offset": 24},
        "top": {"header": {"magic": "GGUF", "version": 3, "tensor_count": len(full.tensors),
                           "metadata_kv_count": len(full.kvs)}},
        "metadata": [],
        "tensors": [],
    })
    cases.append({
        "name": "error-truncated-mid-header",
        "file": "truncated-mid-header.gguf",
        "bytes": full.bytes[:28],
        "exit": 1,
        "error": {"code": "GGUF_TRUNCATED", "offset": 24},
    })
    # `data_offset` past the end of the file.
    assert full.data_offset > full.tensor_table_end, "the full fixture must need real padding"
    cases.append({
        "name": "error-truncated-data-offset",
        "file": "truncated-data-offset.gguf",
        "bytes": full.bytes[:full.tensor_table_end],
        "exit": 1,
        "error": {"code": "GGUF_TRUNCATED", "offset": full.tensor_table_end},
        "tensors_count": len(full.tensors),
    })

    # Every structural boundary, truncated: each must yield `GGUF_TRUNCATED` and no abort.
    boundaries = [
        ("magic", 2),
        ("version", 6),
        ("tensor-count", 12),
        ("kv-count", 20),
        ("key-length", full.kv_offsets[0]["key_len"] + 4),
        ("key-bytes", full.kv_offsets[0]["key"] + 3),
        ("value-type", full.kv_offsets[0]["type"] + 2),
        ("value-body", full.kv_offsets[0]["value"] + 3),
        ("array-elements", full.kv_offsets[array_kv + 3]["array_elements"] + 5),
        ("tensor-name-length", full.tensor_offsets[0]["name_len"] + 4),
        ("tensor-name-bytes", full.tensor_offsets[0]["name"] + 2),
        ("tensor-dims", full.tensor_offsets[0]["dims"] + 3),
        ("tensor-offset", full.tensor_offsets[0]["offset"] + 5),
    ]
    for label, cut in boundaries:
        cases.append(truncated_case("truncated-%s.gguf" % label, full, cut))
        cases[-1]["name"] = "truncated-boundary-" + label

    # ---- precedence: the earlier section 2.6 row wins ------------------------------------------
    both_magic_version = patched(patched(full, 0, b"GGUX"), 4, struct.pack("<I", 1))
    cases.append({
        "name": "precedence-magic-before-version",
        "file": "precedence-magic-version.gguf",
        "bytes": both_magic_version,
        "exit": 1,
        "error": {"code": "GGUF_BAD_MAGIC", "offset": 0},
    })
    implausible_and_truncated = patched(full, 16, struct.pack("<Q", MAX_METADATA_KV + 1))[:200]
    cases.append({
        "name": "precedence-implausible-before-truncation",
        "file": "precedence-implausible-truncated.gguf",
        "bytes": implausible_and_truncated,
        "exit": 1,
        "error": {"code": "GGUF_COUNT_IMPLAUSIBLE", "offset": 16},
    })
    misaligned_and_out_of_range = patched(full, full.tensor_offsets[1]["offset"],
                                          struct.pack("<Q", (1 << 40) + 1))
    cases.append({
        "name": "precedence-misaligned-before-out-of-range",
        "file": "precedence-misaligned-range.gguf",
        "bytes": misaligned_and_out_of_range,
        "exit": 1,
        "error": {"code": "GGUF_TENSOR_MISALIGNED", "offset": full.tensor_offsets[1]["offset"]},
    })

    for case in cases:
        write(out_dir, case["file"], case.pop("bytes"))
    return {
        "window_bytes": WINDOW_BYTES,
        "cases": cases,
    }


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: gguf_fixture.py OUTPUT_DIR\n")
        return 2
    out_dir = Path(argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = build(out_dir)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
