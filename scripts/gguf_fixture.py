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
    29: "IQ1_M", 30: "BF16", 34: "TQ1_0", 35: "TQ2_0", 39: "MXFP4",
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


def straddle_container(filler_length):
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



# =================================================================================================
# R1-QWEN-MODEL-IR corpus (`docs/specs/r1-qwen-model-ir.md` section 4.1).
#
# The generator keeps its independence property here too: the GGML block-geometry table below is
# transcribed separately from the one in `src/gguf.align`, and every expected `nbytes`, block byte
# size, and coverage total is computed in Python from the bytes this file writes. That is what makes
# the size-sum oracle a real differential check rather than a mirror of the implementation.
# =================================================================================================

I64_MAX = 9223372036854775807

# Transcribed from `docs/specs/r1-qwen-model-ir.md` section 2.6, not imported from `src/`.
MAX_UNASSIGNED_REPORTED = 16
MAX_DETAIL_BYTES = 256

# id -> (elements per block, bytes per block). Every id outside this table is
# `R1_UNKNOWN_TENSOR_TYPE`, never a guessed size.
GGML_GEOMETRY = {
    0: (1, 4), 1: (1, 2), 2: (32, 18), 3: (32, 20), 6: (32, 22), 7: (32, 24),
    8: (32, 34), 9: (32, 36), 10: (256, 84), 11: (256, 110), 12: (256, 144),
    13: (256, 176), 14: (256, 210), 15: (256, 292), 24: (1, 1), 25: (1, 2),
    26: (1, 4), 27: (1, 8), 28: (1, 8), 30: (1, 2), 39: (32, 17),
}

# Every quantized tensor's **first** axis must be a multiple of its GGML block size, because that is
# the invariant `ggml_row_size` enforces; `n_embd` and `n_ff` are therefore multiples of 256, the
# widest block in the table. `n_vocab` stays 32 and `n_ff` stays distinct from `n_embd` so a
# transposed `ffn_down` is still a test failure, and every resulting byte size is a multiple of the
# 32-byte container alignment, which is what keeps the size-sum oracle satisfiable.
QWEN_BASE = {
    "n_layer": 2, "n_embd": 256, "n_head": 4, "n_head_kv": 2,
    "n_ff": 512, "n_vocab": 32, "context_length": 512,
}

# Norms and biases are F32; the projections are deliberately mixed so one file exercises a
# 256-element K-block, a 32-element legacy block, and a 1-element unquantized type, giving
# `quant.type_counts` five ascending rows.
QWEN_TYPES = {
    "token_embd": 12, "output_norm": 0, "output": 14,
    "attn_norm": 0, "attn_q": 12, "attn_q_bias": 0, "attn_k": 12, "attn_k_bias": 0,
    "attn_v": 14, "attn_v_bias": 0, "attn_output": 8, "ffn_norm": 0,
    "ffn_gate": 12, "ffn_up": 2, "ffn_down": 14,
}

# One tensor per listed geometry id, placed on a slot whose element count keeps both the block
# alignment and the 32-byte container alignment satisfiable.
GEOMETRY_TYPES = {
    "attn_k_bias": {0: 24, 1: 25},          # [128]
    "attn_v_bias": {0: 26, 1: 27},          # [128]
    "attn_norm": {0: 0, 1: 1},              # [256]
    "attn_q_bias": {0: 28, 1: 30},          # [256]
    "ffn_norm": {0: 7, 1: 9},               # [256]
    "output_norm": {None: 0},               # [256]
    "token_embd": {None: 10},               # [256, 32]
    "output": {None: 15},                   # [256, 32]
    # Id 39 (MXFP4) rides `attn_k` because `[256, 128]` gives `(256 / 32) * 17 * 128 = 17,408`
    # bytes, a multiple of the 32-byte container alignment. Id 2 keeps its other slot in
    # `ffn_up`, so no row leaves the sweep.
    "attn_k": {0: 3, 1: 39},                # [256, 128]
    "attn_v": {0: 6, 1: 8},                 # [256, 128]
    "attn_q": {0: 11, 1: 14},               # [256, 256]
    "attn_output": {0: 12, 1: 13},          # [256, 256]
    "ffn_gate": {0: 12, 1: 14},             # [256, 512]
    "ffn_up": {0: 8, 1: 2},                 # [256, 512]
    "ffn_down": {0: 13, 1: 10},             # [512, 256]
}

QWEN_GLOBAL_ROLES = ["token_embd", "output_norm", "output"]
QWEN_LAYER_ROLES = [
    "attn_norm", "attn_q", "attn_q_bias", "attn_k", "attn_k_bias",
    "attn_v", "attn_v_bias", "attn_output", "ffn_norm", "ffn_gate",
    "ffn_up", "ffn_down",
]
ROLE_SUFFIX = {
    "attn_norm": "attn_norm.weight", "attn_q": "attn_q.weight", "attn_q_bias": "attn_q.bias",
    "attn_k": "attn_k.weight", "attn_k_bias": "attn_k.bias", "attn_v": "attn_v.weight",
    "attn_v_bias": "attn_v.bias", "attn_output": "attn_output.weight",
    "ffn_norm": "ffn_norm.weight", "ffn_gate": "ffn_gate.weight",
    "ffn_up": "ffn_up.weight", "ffn_down": "ffn_down.weight",
}


def qwen_role_shape(role, p):
    head_dim = p["n_embd"] // p["n_head"]
    e, v, ff = p["n_embd"], p["n_vocab"], p["n_ff"]
    q, kv = p["n_head"] * head_dim, p["n_head_kv"] * head_dim
    return {
        "token_embd": [e, v], "output": [e, v], "output_norm": [e],
        "attn_norm": [e], "attn_q": [e, q], "attn_q_bias": [q],
        "attn_k": [e, kv], "attn_k_bias": [kv], "attn_v": [e, kv], "attn_v_bias": [kv],
        "attn_output": [q, e], "ffn_norm": [e], "ffn_gate": [e, ff],
        "ffn_up": [e, ff], "ffn_down": [ff, e],
    }[role]


def qwen_role_name(role, layer):
    if layer is None:
        return {"token_embd": "token_embd.weight", "output_norm": "output_norm.weight",
                "output": "output.weight"}[role]
    return "blk.%d.%s" % (layer, ROLE_SUFFIX[role])


def nbytes_of(dims, type_id):
    """GGML sizes a tensor by rows, not by its element product: `ggml_row_size` requires
    `ne0 % blck_size == 0` and gives one row `type_size * ne0 / blck_size` bytes. A tensor whose
    element count is a multiple of the block size but whose first axis is not is unrepresentable,
    so the assertion below is on `dims[0]`."""
    elements = 1
    for extent in dims:
        elements *= extent
    block_size, type_bytes = GGML_GEOMETRY[type_id]
    assert dims[0] % block_size == 0, (dims, type_id, block_size)
    if elements == 0:
        return 0
    row_bytes = (dims[0] // block_size) * type_bytes
    return row_bytes * (elements // dims[0])


def qwen_kvs(p, arch="qwen2", drop=(), overrides=None, extra=None):
    """The metadata block, in the order a real converter writes it."""
    overrides = overrides or {}
    rows = [
        ("general.architecture", strv(arch)),
        ("general.file_type", u32v(15)),
        ("general.quantization_version", u32v(2)),
        ("qwen2.block_count", u32v(p["n_layer"])),
        ("qwen2.context_length", u32v(p["context_length"])),
        ("qwen2.embedding_length", u32v(p["n_embd"])),
        ("qwen2.feed_forward_length", u32v(p["n_ff"])),
        ("qwen2.attention.head_count", u32v(p["n_head"])),
        ("qwen2.attention.head_count_kv", u32v(p["n_head_kv"])),
        ("qwen2.rope.freq_base", f32v(1000000.0)),
        ("qwen2.attention.layer_norm_rms_epsilon", f32v(1e-06)),
        ("tokenizer.ggml.tokens", Array(STRING, [strv("t%d" % i) for i in range(p["n_vocab"])])),
    ]
    out = []
    for key, value in rows:
        if key in drop:
            continue
        out.append(Kv(key, overrides.get(key, value)))
    for key, value in (extra or []):
        out.append(Kv(key, value))
    return out


class QwenModel:
    """A synthetic qwen2 container plus every expected value of its `R1_MODEL_IR` document."""

    def __init__(self, p=None, types=None, tied=False, arch="qwen2", drop=(), overrides=None,
                 extra=None, layout=None, trailing=0, mutate=None, kv_override=None):
        self.p = dict(QWEN_BASE)
        self.p.update(p or {})
        self.types = dict(QWEN_TYPES)
        if types:
            self.types.update(types)
        self.tied = tied

        # ---- tensor table, in file order ----------------------------------------------------
        self.entries = []          # (role, layer, name, dims, type_id)
        for role in QWEN_GLOBAL_ROLES:
            if role == "output" and tied:
                continue
            self.entries.append((role, None, qwen_role_name(role, None),
                                 qwen_role_shape(role, self.p), self.resolve_type(role, None)))
        for layer in range(self.p["n_layer"]):
            for role in QWEN_LAYER_ROLES:
                self.entries.append((role, layer, qwen_role_name(role, layer),
                                     qwen_role_shape(role, self.p),
                                     self.resolve_type(role, layer)))
        if mutate:
            self.entries = mutate(self.entries)

        # ---- data-section layout ---------------------------------------------------------------
        # Every tensor's byte size is a multiple of the 32-byte container alignment, so a contiguous
        # placement is also an alignment-correct one and `data_offset + sum(nbytes) == file_size`
        # holds exactly. That single property is what makes the oracle testable without a 4.68 GB
        # model.
        sizes = [nbytes_of(dims, type_id) if type_id in GGML_GEOMETRY else 0
                 for (_, _, _, dims, type_id) in self.entries]
        order = layout(self.entries) if layout else list(range(len(self.entries)))
        offsets = [0] * len(self.entries)
        cursor = 0
        for position in order:
            assert cursor % DEFAULT_ALIGNMENT == 0, (position, cursor)
            offsets[position] = cursor
            cursor += sizes[position]
        self.sizes = sizes
        self.offsets = offsets
        self.total_bytes = cursor

        tensors = [Tensor(name, dims, type_id, offsets[index])
                   for index, (_, _, name, dims, type_id) in enumerate(self.entries)]
        kvs = qwen_kvs(self.p, arch=arch, drop=drop, overrides=overrides, extra=extra)
        if kv_override:
            kvs = kv_override(kvs)
        self.container = Container(kvs, tensors, data_len=cursor + trailing)
        self.bytes = self.container.bytes
        self.arch = arch

    def resolve_type(self, role, layer):
        entry = self.types[role]
        if isinstance(entry, dict):
            if layer in entry:
                return entry[layer]
            return entry[None]
        return entry

    def index_of(self, name):
        for index, (_, _, entry_name, _, _) in enumerate(self.entries):
            if entry_name == name:
                return index
        return -1

    def absolute(self, index):
        return self.container.data_offset + self.offsets[index]

    def tensor_expect(self, index, role):
        _, _, name, dims, type_id = self.entries[index]
        elements = 1
        for extent in dims:
            elements *= extent
        block_size, type_bytes = GGML_GEOMETRY[type_id]
        return {
            "name": name,
            "role": role,
            "type": type_id,
            "type_name": GGML_NAMES[type_id],
            "n_dims": len(dims),
            "dims": list(dims),
            "n_elements": elements,
            "block_size": block_size,
            "type_bytes": type_bytes,
            "nbytes": self.sizes[index],
            "offset": self.offsets[index],
            "absolute_offset": self.absolute(index),
            # Schema 2. Every dense block claims the whole tensor, so both fields equal the values
            # above and the qwen2 corpus's byte arithmetic is unchanged.
            "claimed_absolute_offset": self.absolute(index),
            "claimed_nbytes": self.sizes[index],
        }

    def block_expect(self, block_index, kind, layer, members):
        """`members` is a list of (role, tensor index)."""
        tensors = [self.tensor_expect(index, role) for role, index in members]
        byte_size = sum(t["nbytes"] for t in tensors)
        first = min(t["absolute_offset"] for t in tensors)
        end = max(t["absolute_offset"] + t["nbytes"] for t in tensors)
        return {
            "index": block_index,
            "kind": kind,
            "layer": layer,
            "expert": -1,
            "tensor_count": len(tensors),
            "byte_size": byte_size,
            "first_absolute_offset": first,
            "end_absolute_offset": end,
            "contiguous": end - first == byte_size,
            "tensors": tensors,
        }

    def blocks_expect(self):
        blocks = []
        blocks.append(self.block_expect(0, "WeightBlock", -1,
                                        [("token_embd", self.index_of("token_embd.weight"))]))
        for layer in range(self.p["n_layer"]):
            attention = [(role, self.index_of(qwen_role_name(role, layer)))
                         for role in QWEN_LAYER_ROLES[:8]]
            blocks.append(self.block_expect(1 + 2 * layer, "AttentionBlock", layer, attention))
            mlp = [(role, self.index_of(qwen_role_name(role, layer)))
                   for role in QWEN_LAYER_ROLES[8:]]
            blocks.append(self.block_expect(2 + 2 * layer, "MlpBlock", layer, mlp))
        output_source = "token_embd.weight" if self.tied else "output.weight"
        blocks.append(self.block_expect(
            1 + 2 * self.p["n_layer"], "WeightBlock", -1,
            [("output_norm", self.index_of("output_norm.weight")),
             ("output", self.index_of(output_source))]))
        return blocks

    def quant_expect(self):
        rows = []
        for type_id in sorted(set(entry[4] for entry in self.entries)):
            members = [i for i, entry in enumerate(self.entries) if entry[4] == type_id]
            rows.append({
                "type": type_id,
                "type_name": GGML_NAMES[type_id],
                "tensor_count": len(members),
                "bytes": sum(self.sizes[i] for i in members),
            })
        return {
            "file_type": 15,
            "file_type_present": True,
            "type_counts": rows,
            "total_tensor_bytes": self.total_bytes,
        }

    def model_expect(self, rope_dim=None, scaling=None):
        head_dim = self.p["n_embd"] // self.p["n_head"]
        return {
            "arch": self.arch,
            "n_layer": self.p["n_layer"],
            "n_embd": self.p["n_embd"],
            "n_head": self.p["n_head"],
            "n_head_kv": self.p["n_head_kv"],
            "head_dim": head_dim,
            "n_ff": self.p["n_ff"],
            "n_vocab": self.p["n_vocab"],
            "n_expert": 0,
            "context_length": self.p["context_length"],
            "rms_eps": marker_f32(f32_bits(1e-06)),
            "rms_eps_bits": "%08x" % f32_bits(1e-06),
            "rope": {
                "type": 2,
                "type_name": "neox",
                "type_source": "architecture",
                "freq_base": marker_f32(f32_bits(1000000.0)),
                "freq_base_bits": "%08x" % f32_bits(1000000.0),
                "dim_count": head_dim if rope_dim is None else rope_dim,
                "dim_count_source": "derived" if rope_dim is None else "metadata",
                "scaling_type": scaling,
            },
        }

    def coverage_expect(self):
        return {
            "tensor_count": len(self.entries),
            "assigned_tensor_count": len(self.entries),
            "unassigned_tensors": [],
            "block_count": 2 * self.p["n_layer"] + 2,
            "data_offset": self.container.data_offset,
            "total_tensor_bytes": self.total_bytes,
            "computed_end": self.container.data_offset + self.total_bytes,
            "file_size": len(self.bytes),
            "size_sum_ok": True,
        }

    def source_expect(self):
        return {
            "gguf_version": 3,
            "alignment": DEFAULT_ALIGNMENT,
            "file_size": len(self.bytes),
            "data_offset": self.container.data_offset,
            "tensor_count": len(self.entries),
            "metadata_kv_count": len(self.container.kvs),
            "bytes_read": len(self.bytes),
        }

    def positive(self, name, file_name, rope_dim=None, scaling=None, **extra):
        case = {
            "name": name,
            "file": file_name,
            "bytes": self.bytes,
            "exit": 0,
            "source": self.source_expect(),
            "model": self.model_expect(rope_dim=rope_dim, scaling=scaling),
            "quant": self.quant_expect(),
            "coverage": self.coverage_expect(),
            "blocks": self.blocks_expect(),
        }
        case.update(extra)
        return case


def qwen_build(out_dir):
    """The section 4.1 corpus: four positive fixtures, the geometry sweep, and one negative fixture
    per reachable row of section 2.6, each carrying the code and `error_detail` this generator
    computed from the bytes it wrote."""
    cases = []

    def negative(name, file_name, payload, code, detail, **extra):
        case = {"name": name, "file": file_name, "bytes": payload, "exit": 1,
                "error": {"code": code, "detail": detail}}
        case.update(extra)
        cases.append(case)
        return case

    # ---- positive: the complete synthetic qwen2 container -------------------------------------
    full = QwenModel()
    assert len(full.bytes) < 1048576, len(full.bytes)
    assert full.container.data_offset + full.total_bytes == len(full.bytes)
    cases.append(full.positive(
        "qwen2-full", "qwen2-full.gguf",
        bytes_read=len(full.bytes),
        field_order=True,
    ))

    # Tied embeddings: an absent `output.weight` puts `token_embd.weight` in two blocks and the
    # oracle still holds, because the shared tensor's bytes are counted once.
    tied = QwenModel(tied=True)
    tied_case = tied.positive("qwen2-tied", "qwen2-tied.gguf")
    tied_case["tied"] = True
    cases.append(tied_case)

    # A declared rope dimension count and a rope scaling type, pinning `dim_count_source:
    # "metadata"` and a non-null `scaling_type`.
    rope = QwenModel(extra=[("qwen2.rope.dimension_count", u32v(16)),
                            ("qwen2.rope.scaling.type", strv("linear"))])
    cases.append(rope.positive("qwen2-rope-dim", "qwen2-rope-dim.gguf",
                               rope_dim=16, scaling="linear"))

    # The same logical model with the data section grouped by role across layers — which is exactly
    # what the reference model's writer does — so a per-layer block's tensors are scattered and at
    # least one block is non-contiguous while the oracle still holds.
    def role_major(entries):
        return sorted(range(len(entries)),
                      key=lambda i: (entries[i][0], entries[i][1] if entries[i][1] is not None else -1))

    permuted = QwenModel(layout=role_major)
    permuted_case = permuted.positive("qwen2-permuted", "qwen2-permuted.gguf")
    assert any(not block["contiguous"] for block in permuted_case["blocks"]), "layout is contiguous"
    cases.append(permuted_case)

    # One tensor per listed geometry id, so every row of the section 2.5.7 table is exercised with a
    # generator-computed `nbytes` in one file.
    geometry = QwenModel(types=GEOMETRY_TYPES)
    geometry_case = geometry.positive("qwen2-geometry", "qwen2-geometry.gguf")
    covered = set(entry[4] for entry in geometry.entries)
    assert covered == set(GGML_GEOMETRY), sorted(set(GGML_GEOMETRY) - covered)
    geometry_case["geometry_ids"] = sorted(covered)
    cases.append(geometry_case)

    # A non-finite rope base is a wire-rendering problem, not a structural one, so it stays a
    # positive case: `null` plus the exact bits is the honest rendering.
    nonfinite = QwenModel(overrides={"qwen2.rope.freq_base": f32v(bits=0x7F800000)})
    nonfinite_case = nonfinite.positive("qwen2-nonfinite", "qwen2-nonfinite.gguf")
    nonfinite_case["model"]["rope"]["freq_base"] = None
    nonfinite_case["model"]["rope"]["freq_base_bits"] = "7f800000"
    cases.append(nonfinite_case)

    nan = QwenModel(overrides={
        "qwen2.attention.layer_norm_rms_epsilon": f32v(bits=0x7FC00000)})
    nan_case = nan.positive("qwen2-nan", "qwen2-nan.gguf")
    nan_case["model"]["rms_eps"] = None
    nan_case["model"]["rms_eps_bits"] = "7fc00000"
    cases.append(nan_case)

    # `kv_array_length` on a value that is not an ARRAY returns `None` rather than a coerced value,
    # so the `n_vocab` cross-check is simply not performed and the derivation still succeeds.
    tokens_scalar = QwenModel(overrides={"tokenizer.ggml.tokens": u32v(31)})
    cases.append(tokens_scalar.positive("qwen2-tokens-scalar", "qwen2-tokens-scalar.gguf"))

    # A repeated `general.architecture` resolves to its **first** occurrence, which is the rule
    # `find_key` applies to every other key. A last-wins reader would derive `llama` here and reject
    # a model it can describe.
    dup_arch = QwenModel(extra=[("general.architecture", strv("llama"))])
    cases.append(dup_arch.positive("qwen2-dup-arch", "qwen2-dup-arch.gguf"))

    # A key whose bytes are not valid UTF-8 holds a zero-length span and can never match a lookup,
    # so it changes nothing about the derivation.
    invalid_key = QwenModel(extra=[(b"qwen2.block\xffcount", u32v(99))])
    invalid_key_case = invalid_key.positive("qwen2-invalid-key", "qwen2-invalid-key.gguf")
    cases.append(invalid_key_case)

    # ---- negative corpus: one fixture per reachable section 2.6 row ----------------------------
    negative("qwen2-bad-magic", "qwen2-bad-magic.gguf", patched(full, 0, b"GGUX"),
             "R1_GGUF_ERROR", "GGUF_BAD_MAGIC",
             table_sentinels={"tensor_count": 0, "metadata_kv_count": 0, "gguf_version": -1},
             blocks_len=0)

    wrong_arch = QwenModel(arch="llama")
    negative("qwen2-wrong-arch", "qwen2-wrong-arch.gguf", wrong_arch.bytes,
             "R1_UNSUPPORTED_ARCH", "llama", blocks_len=0,
             model_sentinels={"n_layer": -1, "n_embd": -1, "n_head": -1, "n_head_kv": -1,
                              "head_dim": -1, "n_ff": -1, "n_vocab": -1, "n_expert": -1,
                              "context_length": -1, "rms_eps": None, "rms_eps_bits": None})

    # Container-controlled text carried into `error_detail` and into the positional summary block.
    arch_escapes = QwenModel(arch=ESCAPE_STRING.decode("utf-8", "surrogateescape")
                             if False else "line1\nstatus:\tERROR\x7fline2")
    negative("qwen2-arch-escapes", "qwen2-arch-escapes.gguf", arch_escapes.bytes,
             "R1_UNSUPPORTED_ARCH", "line1\nstatus:\tERROR\x7fline2",
             summary_arch="line1\\x0astatus:\\x09ERROR\\x7fline2",
             summary_detail="line1\\x0astatus:\\x09ERROR\\x7fline2")

    escapes = QwenModel(arch=ESCAPE_STRING.decode("utf-8"))
    negative("qwen2-wire-escapes", "qwen2-wire-escapes.gguf", escapes.bytes,
             "R1_UNSUPPORTED_ARCH", ESCAPE_STRING.decode("utf-8"))

    missing_key = QwenModel(drop=("qwen2.block_count",))
    negative("qwen2-missing-key", "qwen2-missing-key.gguf", missing_key.bytes,
             "R1_MISSING_KEY", "qwen2.block_count")

    key_type = QwenModel(overrides={"qwen2.embedding_length": strv("128")})
    negative("qwen2-key-type", "qwen2-key-type.gguf", key_type.bytes,
             "R1_KEY_TYPE_MISMATCH", "qwen2.embedding_length")

    expert_type = QwenModel(extra=[("qwen2.expert_count", strv("4"))])
    negative("qwen2-expert-type", "qwen2-expert-type.gguf", expert_type.bytes,
             "R1_KEY_TYPE_MISMATCH", "qwen2.expert_count")

    implausible = QwenModel(overrides={"qwen2.attention.head_count": u32v(0)})
    negative("qwen2-implausible", "qwen2-implausible.gguf", implausible.bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "qwen2.attention.head_count")

    zero_layer = QwenModel(overrides={"qwen2.block_count": u32v(0)})
    negative("qwen2-zero-layer", "qwen2-zero-layer.gguf", zero_layer.bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "qwen2.block_count")

    indivisible = QwenModel(overrides={"qwen2.embedding_length": u32v(129)})
    negative("qwen2-indivisible", "qwen2-indivisible.gguf", indivisible.bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "qwen2.embedding_length")

    rope_dim_bad = QwenModel(extra=[("qwen2.rope.dimension_count", u32v(4096))])
    negative("qwen2-rope-dim-implausible", "qwen2-rope-dim-implausible.gguf", rope_dim_bad.bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "qwen2.rope.dimension_count")

    # Present, declared `STRING`, and not valid UTF-8. `scaling_type: null` is reserved for "the
    # container did not supply it", so reporting this as `null` would erase the difference.
    scaling_invalid = QwenModel(extra=[("qwen2.rope.scaling.type", strv(b"lin\xffear"))])
    negative("qwen2-scaling-invalid-utf8", "qwen2-scaling-invalid-utf8.gguf",
             scaling_invalid.bytes, "R1_KEY_TYPE_MISMATCH", "qwen2.rope.scaling.type")

    moe = QwenModel(extra=[("qwen2.expert_count", u32v(4))])
    negative("qwen2-moe", "qwen2-moe.gguf", moe.bytes, "R1_UNSUPPORTED_MOE", "4")

    def duplicate_entries(entries):
        target = [e for e in entries if e[2] == "blk.0.attn_norm.weight"][0]
        return entries + [target]

    duplicate = QwenModel(mutate=duplicate_entries)
    negative("qwen2-duplicate", "qwen2-duplicate.gguf", duplicate.bytes,
             "R1_DUPLICATE_TENSOR", "blk.0.attn_norm.weight")

    # An unknown `ggml_type` id is an error and never a guessed size: R1 computes a byte size, and a
    # guess silently corrupts every downstream offset.
    unknown = patched(full, full.container.tensor_offsets[full.index_of(
        "blk.0.attn_norm.weight")]["type"], struct.pack("<I", 21))
    unknown = patched(unknown, full.container.tensor_offsets[full.index_of(
        "blk.1.attn_norm.weight")]["type"], struct.pack("<I", 199))
    negative("qwen2-unknown-type", "qwen2-unknown-type.gguf", unknown,
             "R1_UNKNOWN_TENSOR_TYPE", "21")

    # Id 5 was defined and later removed from GGML, so it has a name in no table and a geometry in
    # this one; it must be rejected exactly like an id GGML has never used.
    removed = patched(full, full.container.tensor_offsets[0]["type"], struct.pack("<I", 5))
    negative("qwen2-unknown-type-removed", "qwen2-unknown-type-removed.gguf", removed,
             "R1_UNKNOWN_TENSOR_TYPE", "5")

    # `token_embd.weight` is Q4_K, so its first axis must be a multiple of 256. 33 is not, and its
    # element product is not a multiple either.
    unaligned = patched(full, full.container.tensor_offsets[0]["dims"],
                        struct.pack("<Q", 33))
    negative("qwen2-unaligned", "qwen2-unaligned.gguf", unaligned,
             "R1_TENSOR_SHAPE_UNALIGNED", "token_embd.weight")

    # The discriminating case: `[128, 64]` is 8,192 elements, a clean multiple of the 256-element
    # Q4_K block, and is still unrepresentable because GGML's invariant is per row. A frontend that
    # tested only the element product would size this tensor and accept the model.
    row_unaligned = patched(full, full.container.tensor_offsets[0]["dims"],
                            struct.pack("<Q", 128))
    row_unaligned = patched(row_unaligned, full.container.tensor_offsets[0]["dims"] + 8,
                            struct.pack("<Q", 64))
    negative("qwen2-row-unaligned", "qwen2-row-unaligned.gguf", row_unaligned,
             "R1_TENSOR_SHAPE_UNALIGNED", "token_embd.weight")

    # ---- the overflow class, each guard tested before the arithmetic it protects ----------------
    def reshape_dims(entries, name, dims):
        return [(role, layer, entry_name, dims if entry_name == name else entry_dims, type_id)
                for (role, layer, entry_name, entry_dims, type_id) in entries]

    def bare_qwen(tensors, data_len=64, p=None, tied=True, drop=("tokenizer.ggml.tokens",)):
        return Container(qwen_kvs({**QWEN_BASE, **(p or {})}, drop=drop), tensors,
                         data_len=data_len)

    dims3 = bare_qwen([Tensor("token_embd.weight", [2 ** 31, 2 ** 31, 2 ** 31], 0, 0)])
    negative("qwen2-overflow-dims", "qwen2-overflow-dims.gguf", dims3.bytes,
             "R1_SIZE_OVERFLOW", "token_embd.weight",
             inspect_dims=[[2 ** 31, 2 ** 31, 2 ** 31]])

    dims4 = bare_qwen([Tensor("token_embd.weight", [2 ** 22, 2 ** 22, 2 ** 22, 2 ** 22], 0, 0)])
    negative("qwen2-overflow-dims4", "qwen2-overflow-dims4.gguf", dims4.bytes,
             "R1_SIZE_OVERFLOW", "token_embd.weight",
             inspect_dims=[[2 ** 22, 2 ** 22, 2 ** 22, 2 ** 22]])

    nbytes_overflow = bare_qwen([Tensor("token_embd.weight", [2 ** 62], 0, 0)])
    negative("qwen2-overflow-nbytes", "qwen2-overflow-nbytes.gguf", nbytes_overflow.bytes,
             "R1_SIZE_OVERFLOW", "token_embd.weight")

    total_overflow = bare_qwen([
        Tensor("token_embd.weight", [2 ** 30, 2 ** 30], 0, 0),
        Tensor("output_norm.weight", [2 ** 30, 2 ** 30], 0, 32),
    ])
    negative("qwen2-overflow-total", "qwen2-overflow-total.gguf", total_overflow.bytes,
             "R1_SIZE_OVERFLOW", "output_norm.weight")

    # `n_vocab` is derived from `token_embd.weight` `dims[1]`, so the step-10 shape check is built
    # from the very value it would have to falsify. These two fixtures own the bound that catches
    # what that circularity cannot: a vocabulary of zero, and one three orders of magnitude past any
    # shipping tokenizer.
    vocab_zero = QwenModel(
        mutate=lambda entries: reshape_dims(entries, "token_embd.weight", [QWEN_BASE["n_embd"], 0]))
    negative("qwen2-vocab-zero", "qwen2-vocab-zero.gguf", vocab_zero.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "token_embd.weight", blocks_len=0)

    vocab_huge = bare_qwen([Tensor("token_embd.weight", [256, 2 ** 30], 0, 0)])
    negative("qwen2-vocab-implausible", "qwen2-vocab-implausible.gguf", vocab_huge.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "token_embd.weight", blocks_len=0)

    # ---- block assembly, coverage, and the oracle ---------------------------------------------
    missing_tensor = QwenModel(
        mutate=lambda entries: [e for e in entries if e[2] != "blk.1.ffn_up.weight"])
    negative("qwen2-missing-tensor", "qwen2-missing-tensor.gguf", missing_tensor.bytes,
             "R1_MISSING_TENSOR", "blk.1.ffn_up.weight",
             # The embedding block, both layer-0 blocks, and the layer-1 attention block completed
             # before the failure; the layer-1 MLP block did not.
             blocks_len=4)

    missing_embd = QwenModel(
        mutate=lambda entries: [e for e in entries if e[2] != "token_embd.weight"])
    negative("qwen2-missing-embd", "qwen2-missing-embd.gguf", missing_embd.bytes,
             "R1_MISSING_TENSOR", "token_embd.weight", blocks_len=0)

    bad_shape = QwenModel(
        mutate=lambda entries: reshape_dims(entries, "blk.0.attn_q.weight", [256, 128]))
    negative("qwen2-bad-shape", "qwen2-bad-shape.gguf", bad_shape.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "blk.0.attn_q.weight", blocks_len=1)

    vocab = QwenModel(overrides={
        "tokenizer.ggml.tokens": Array(STRING, [strv("t%d" % i) for i in range(31)])})
    negative("qwen2-vocab-mismatch", "qwen2-vocab-mismatch.gguf", vocab.bytes,
             "R1_VOCAB_MISMATCH", "31!=32", blocks_len=0)

    extra_tensor = QwenModel(mutate=lambda entries: entries + [
        ("attn_q", 9, "blk.9.attn_q.weight", [256, 256], 12)])
    negative("qwen2-extra-tensor", "qwen2-extra-tensor.gguf", extra_tensor.bytes,
             "R1_UNASSIGNED_TENSOR", "blk.9.attn_q.weight",
             unassigned=["blk.9.attn_q.weight"])

    invalid_name = QwenModel(mutate=lambda entries: entries + [
        ("attn_q", None, b"bad\xffname", [256, 256], 12)])
    negative("qwen2-invalid-name", "qwen2-invalid-name.gguf", invalid_name.bytes,
             "R1_UNASSIGNED_TENSOR", "", unassigned=[""])

    # `coverage.unassigned_tensors` is capped at MAX_UNASSIGNED_REPORTED, so a document cannot grow
    # with the size of the defect. This fixture is also the bounded-work regression: 50,000 extra
    # tensors are a linear amount of work, not a quadratic one (section 7, item 15). The junk
    # tensors declare a zero extent, so they cost table bytes and no data bytes at all — which also
    # pins `tensor_nbytes`'s zero-element guard.
    junk_count = 50000
    many = QwenModel(p={"n_layer": 1}, mutate=lambda entries: entries + [
        ("junk", None, "junk.%05d.weight" % i, [0], 0) for i in range(junk_count)])
    many_names = ["junk.%05d.weight" % i for i in range(MAX_UNASSIGNED_REPORTED)]
    negative("qwen2-many-tensors", "qwen2-many-tensors.gguf", many.bytes,
             "R1_UNASSIGNED_TENSOR", "junk.00000.weight",
             unassigned=many_names, unassigned_total=junk_count, bounded_work=True)

    # `error_detail` is bounded at MAX_DETAIL_BYTES and truncated at a UTF-8 scalar boundary. This
    # name is 100 three-byte scalars, so the 256-byte cut lands inside the 86th one and the detail
    # must stop at 255 bytes rather than splitting it.
    long_name = "\u3042" * 100
    long_raw = long_name.encode("utf-8")
    long_cut = MAX_DETAIL_BYTES
    while long_cut > 0 and (long_raw[long_cut] & 0xC0) == 0x80:
        long_cut -= 1
    long_detail = long_raw[:long_cut]
    assert len(long_detail) == 255, len(long_detail)
    long_case = QwenModel(mutate=lambda entries: entries + [
        ("attn_q", None, long_name, [256, 256], 12)])
    negative("qwen2-long-name", "qwen2-long-name.gguf", long_case.bytes,
             "R1_UNASSIGNED_TENSOR", long_detail.decode("utf-8"),
             unassigned=[long_name])

    size_sum = QwenModel(trailing=64)
    negative("qwen2-size-sum", "qwen2-size-sum.gguf", size_sum.bytes,
             "R1_SIZE_SUM_MISMATCH",
             "%d!=%d" % (size_sum.container.data_offset + size_sum.total_bytes,
                         len(size_sum.bytes)))

    # ---- early exit: the columns hold exactly the entries completed before the failure ----------
    partial_kv = patched(full, full.container.kv_offsets[3]["type"], struct.pack("<I", 13))
    negative("qwen2-partial-kv", "qwen2-partial-kv.gguf", partial_kv,
             "R1_GGUF_ERROR", "GGUF_UNKNOWN_VALUE_TYPE",
             table_sentinels={"metadata_kv_count": 3, "tensor_count": 0})

    partial_tensor = patched(full, full.container.tensor_offsets[2]["offset"],
                             struct.pack("<Q", 33))
    negative("qwen2-partial-tensor", "qwen2-partial-tensor.gguf", partial_tensor,
             "R1_GGUF_ERROR", "GGUF_TENSOR_MISALIGNED",
             table_sentinels={"metadata_kv_count": len(full.container.kvs), "tensor_count": 2})

    # ---- precedence: the earlier section 2.6 row wins ------------------------------------------
    precedence_arch = QwenModel(arch="llama", drop=("qwen2.block_count",))
    negative("qwen2-precedence-arch-key", "qwen2-precedence-arch-key.gguf",
             precedence_arch.bytes, "R1_UNSUPPORTED_ARCH", "llama")

    precedence_key = QwenModel(
        drop=("qwen2.block_count",),
        mutate=lambda entries: reshape_dims(entries, "blk.0.attn_q.weight", [256, 128]))
    negative("qwen2-precedence-key-shape", "qwen2-precedence-key-shape.gguf",
             precedence_key.bytes, "R1_MISSING_KEY", "qwen2.block_count")

    precedence_type = patched(QwenModel(trailing=64).bytes,
                              full.container.tensor_offsets[0]["type"], struct.pack("<I", 21))
    negative("qwen2-precedence-type-sum", "qwen2-precedence-type-sum.gguf", precedence_type,
             "R1_UNKNOWN_TENSOR_TYPE", "21")

    precedence_dup = QwenModel(mutate=lambda entries: duplicate_entries(entries) + [
        ("attn_q", 9, "blk.9.attn_q.weight", [256, 256], 12)])
    negative("qwen2-precedence-duplicate-unassigned", "qwen2-precedence-duplicate-unassigned.gguf",
             precedence_dup.bytes, "R1_DUPLICATE_TENSOR", "blk.0.attn_norm.weight")

    for case in cases:
        write(out_dir, case["file"], case.pop("bytes"))
    return cases

# =================================================================================================
# R1B-GPTOSS-MOE-IR corpus (`docs/specs/r1b-gptoss-moe-ir.md` section 4.1).
#
# The generator keeps its independence property here too: every expected `nbytes`, every per-expert
# claim, and every block byte total is computed in Python from the bytes this file writes, with the
# MXFP4 row transcribed into `GGML_GEOMETRY` separately from `src/gguf.align`. That is what makes
# the claim-tiling oracle a real differential check rather than a mirror of the implementation.
#
# **Every key name, tensor name, and shape below is an ASSUMPTION** (section 2.5's banner): no
# gpt-oss model is present on this host and `make model-ir-parity` for this architecture is a
# recorded `N/A`. The corpus therefore pins the *derivation*, not the real model.
# =================================================================================================

MAX_EXPERTS = 1024
MAX_BLOCKS = 65536

GPTOSS_BASE = {
    "n_layer": 2, "n_embd": 256, "n_head": 8, "n_head_kv": 2,
    "key_length": 64, "value_length": 64,
    "n_ff": 256, "n_ff_exp": 32, "n_expert": 8, "n_expert_used": 2,
    "n_vocab": 32, "context_length": 512,
    "sliding_window": 64, "sliding_window_pattern": 2,
}

# Mixed on purpose: the three stacked expert weights are MXFP4; the router, the norms, `attn_sinks`,
# and every bias are F32; `attn_q` / `attn_k` / `token_embd` are Q4_K; `attn_v` / `output` are Q6_K;
# `attn_output` is Q8_0 — five ascending `quant.type_counts` rows (ids 0, 8, 12, 14, 39).
#
# A stacked MXFP4 **bias** would have `plane_bytes = row_bytes = 136`, which is not a multiple of the
# 32-byte container alignment, so expert biases are F32.
GPTOSS_TYPES = {
    "token_embd": 12, "output_norm": 0, "output": 14,
    "attn_norm": 0, "attn_q": 12, "attn_q_bias": 0, "attn_k": 12, "attn_k_bias": 0,
    "attn_v": 14, "attn_v_bias": 0, "attn_output": 8, "attn_output_bias": 0,
    "attn_sinks": 0, "ffn_norm": 0, "router": 0, "router_bias": 0,
    "ffn_gate_exps": 39, "ffn_gate_exps_bias": 0,
    "ffn_up_exps": 39, "ffn_up_exps_bias": 0,
    "ffn_down_exps": 39, "ffn_down_exps_bias": 0,
    "ffn_gate_up_exps": 39, "ffn_gate_up_exps_bias": 0,
}

GPTOSS_GLOBAL_ROLES = ["token_embd", "output_norm", "output"]
GPTOSS_ATTENTION_ROLES = [
    "attn_norm", "attn_q", "attn_q_bias", "attn_k", "attn_k_bias",
    "attn_v", "attn_v_bias", "attn_output", "attn_output_bias", "attn_sinks",
]
GPTOSS_ROUTER_ROLES = ["ffn_norm", "router", "router_bias"]
GPTOSS_SPLIT_ROLES = [
    "ffn_gate_exps", "ffn_gate_exps_bias", "ffn_up_exps", "ffn_up_exps_bias",
    "ffn_down_exps", "ffn_down_exps_bias",
]
GPTOSS_FUSED_ROLES = [
    "ffn_gate_up_exps", "ffn_gate_up_exps_bias", "ffn_down_exps", "ffn_down_exps_bias",
]
# The roles the plan slices: their expert axis is the last declared one, with extent `n_expert`.
GPTOSS_SLICED = set(GPTOSS_SPLIT_ROLES) | set(GPTOSS_FUSED_ROLES)

GPTOSS_SUFFIX = {
    "attn_norm": "attn_norm.weight", "attn_q": "attn_q.weight", "attn_q_bias": "attn_q.bias",
    "attn_k": "attn_k.weight", "attn_k_bias": "attn_k.bias",
    "attn_v": "attn_v.weight", "attn_v_bias": "attn_v.bias",
    "attn_output": "attn_output.weight", "attn_output_bias": "attn_output.bias",
    "attn_sinks": "attn_sinks.weight", "ffn_norm": "ffn_norm.weight",
    "router": "ffn_gate_inp.weight", "router_bias": "ffn_gate_inp.bias",
    "ffn_gate_exps": "ffn_gate_exps.weight", "ffn_gate_exps_bias": "ffn_gate_exps.bias",
    "ffn_up_exps": "ffn_up_exps.weight", "ffn_up_exps_bias": "ffn_up_exps.bias",
    "ffn_down_exps": "ffn_down_exps.weight", "ffn_down_exps_bias": "ffn_down_exps.bias",
    "ffn_gate_up_exps": "ffn_gate_up_exps.weight",
    "ffn_gate_up_exps_bias": "ffn_gate_up_exps.bias",
}


def gptoss_head_dim(p):
    if p.get("key_length") is not None:
        return p["key_length"]
    return p["n_embd"] // p["n_head"]


def gptoss_ff_exp(p):
    if p.get("n_ff_exp") is not None:
        return p["n_ff_exp"]
    return p["n_ff"]


def gptoss_role_shape(role, p):
    head_dim = gptoss_head_dim(p)
    ff = gptoss_ff_exp(p)
    e, v, x = p["n_embd"], p["n_vocab"], p["n_expert"]
    q, kv = p["n_head"] * head_dim, p["n_head_kv"] * head_dim
    return {
        "token_embd": [e, v], "output": [e, v], "output_norm": [e],
        "attn_norm": [e], "attn_q": [e, q], "attn_q_bias": [q],
        "attn_k": [e, kv], "attn_k_bias": [kv], "attn_v": [e, kv], "attn_v_bias": [kv],
        "attn_output": [q, e], "attn_output_bias": [e], "attn_sinks": [p["n_head"]],
        "ffn_norm": [e], "router": [e, x], "router_bias": [x],
        "ffn_gate_exps": [ff, e, x], "ffn_gate_exps_bias": [ff, x],
        "ffn_up_exps": [ff, e, x], "ffn_up_exps_bias": [ff, x],
        "ffn_down_exps": [e, ff, x], "ffn_down_exps_bias": [e, x],
        "ffn_gate_up_exps": [2 * ff, e, x], "ffn_gate_up_exps_bias": [2 * ff, x],
    }[role]


def gptoss_role_name(role, layer):
    if layer is None:
        return {"token_embd": "token_embd.weight", "output_norm": "output_norm.weight",
                "output": "output.weight"}[role]
    return "blk.%d.%s" % (layer, GPTOSS_SUFFIX[role])


def gptoss_kvs(p, arch="gpt-oss", drop=(), overrides=None, extra=None):
    """The metadata block, in the order a converter plausibly writes it. Presence, type, and value
    are all validated in the section 2.6 order, so the file order below is deliberately not that
    order."""
    overrides = overrides or {}
    rows = [
        ("general.architecture", strv(arch)),
        ("general.file_type", u32v(15)),
        ("general.quantization_version", u32v(2)),
        ("gpt-oss.block_count", u32v(p["n_layer"])),
        ("gpt-oss.context_length", u32v(p["context_length"])),
        ("gpt-oss.embedding_length", u32v(p["n_embd"])),
        ("gpt-oss.feed_forward_length", u32v(p["n_ff"])),
        ("gpt-oss.expert_feed_forward_length",
         u32v(p["n_ff_exp"]) if p.get("n_ff_exp") is not None else None),
        ("gpt-oss.expert_count", u32v(p["n_expert"])),
        ("gpt-oss.expert_used_count", u32v(p["n_expert_used"])),
        ("gpt-oss.attention.head_count", u32v(p["n_head"])),
        ("gpt-oss.attention.head_count_kv", u32v(p["n_head_kv"])),
        ("gpt-oss.attention.key_length",
         u32v(p["key_length"]) if p.get("key_length") is not None else None),
        ("gpt-oss.attention.value_length",
         u32v(p["value_length"]) if p.get("value_length") is not None else None),
        ("gpt-oss.attention.sliding_window",
         u32v(p["sliding_window"]) if p.get("sliding_window") is not None else None),
        ("gpt-oss.attention.sliding_window_pattern",
         u32v(p["sliding_window_pattern"]) if p.get("sliding_window_pattern") is not None else None),
        ("gpt-oss.rope.freq_base", f32v(1000000.0)),
        ("gpt-oss.attention.layer_norm_rms_epsilon", f32v(1e-06)),
        ("tokenizer.ggml.tokens", Array(STRING, [strv("t%d" % i) for i in range(p["n_vocab"])])),
    ]
    out = []
    for key, value in rows:
        if value is None or key in drop:
            continue
        out.append(Kv(key, overrides.get(key, value)))
    for key, value in (extra or []):
        out.append(Kv(key, value))
    return out


class GptOssModel:
    """A synthetic gpt-oss container plus every expected value of its `R1_MODEL_IR` document."""

    def __init__(self, p=None, types=None, tied=False, fused=False, arch="gpt-oss", drop=(),
                 overrides=None, extra=None, layout=None, trailing=0, mutate=None,
                 drop_roles=()):
        self.p = dict(GPTOSS_BASE)
        self.p.update(p or {})
        self.types = dict(GPTOSS_TYPES)
        if types:
            self.types.update(types)
        self.tied = tied
        self.fused = fused
        self.expert_roles = GPTOSS_FUSED_ROLES if fused else GPTOSS_SPLIT_ROLES
        self.drop_roles = set(drop_roles)
        head_dim = gptoss_head_dim(self.p)
        self.head_dim = head_dim
        self.head_dim_source = "metadata" if self.p.get("key_length") is not None else "derived"
        self.ff_exp = gptoss_ff_exp(self.p)
        self.ff_exp_source = "metadata" if self.p.get("n_ff_exp") is not None else "derived"

        # ---- tensor table, in file order ------------------------------------------------------
        self.entries = []          # (role, layer, name, dims, type_id)
        for role in GPTOSS_GLOBAL_ROLES:
            if role == "output" and tied:
                continue
            if role in self.drop_roles:
                continue
            self.entries.append((role, None, gptoss_role_name(role, None),
                                 gptoss_role_shape(role, self.p), self.types[role]))
        for layer in range(self.p["n_layer"]):
            for role in GPTOSS_ATTENTION_ROLES + GPTOSS_ROUTER_ROLES + self.expert_roles:
                if role in self.drop_roles:
                    continue
                self.entries.append((role, layer, gptoss_role_name(role, layer),
                                     gptoss_role_shape(role, self.p), self.types[role]))
        if mutate:
            self.entries = mutate(self.entries)

        # ---- data-section layout --------------------------------------------------------------
        # Every tensor's byte size is a multiple of the 32-byte container alignment, and for a
        # sliced tensor so is every expert plane, or a contiguous placement could not also be
        # alignment-correct and the size-sum oracle would be unsatisfiable.
        sizes = [nbytes_of(dims, type_id) if type_id in GGML_GEOMETRY else 0
                 for (_, _, _, dims, type_id) in self.entries]
        order = layout(self.entries) if layout else list(range(len(self.entries)))
        offsets = [0] * len(self.entries)
        cursor = 0
        for position in order:
            assert cursor % DEFAULT_ALIGNMENT == 0, (position, cursor)
            offsets[position] = cursor
            cursor += sizes[position]
        self.sizes = sizes
        self.offsets = offsets
        self.total_bytes = cursor

        tensors = [Tensor(name, dims, type_id, offsets[index])
                   for index, (_, _, name, dims, type_id) in enumerate(self.entries)]
        kvs = gptoss_kvs(self.p, arch=arch, drop=drop, overrides=overrides, extra=extra)
        self.container = Container(kvs, tensors, data_len=cursor + trailing)
        self.bytes = self.container.bytes
        self.arch = arch

    def index_of(self, name):
        for index, (_, _, entry_name, _, _) in enumerate(self.entries):
            if entry_name == name:
                return index
        return -1

    def absolute(self, index):
        return self.container.data_offset + self.offsets[index]

    def claim(self, index, slice_index):
        """Section 2.5.3, computed in Python: the last declared axis is the outermost, so each of
        its indices owns one contiguous byte plane."""
        _, _, _, dims, _ = self.entries[index]
        if slice_index is None:
            return self.absolute(index), self.sizes[index]
        last = dims[-1]
        assert self.sizes[index] % last == 0, (dims, self.sizes[index], last)
        plane = self.sizes[index] // last
        return self.absolute(index) + plane * slice_index, plane

    def tensor_expect(self, index, role, slice_index=None):
        _, _, name, dims, type_id = self.entries[index]
        elements = 1
        for extent in dims:
            elements *= extent
        block_size, type_bytes = GGML_GEOMETRY[type_id]
        claimed_offset, claimed_nbytes = self.claim(index, slice_index)
        return {
            "name": name,
            "role": role,
            "type": type_id,
            "type_name": GGML_NAMES[type_id],
            "n_dims": len(dims),
            "dims": list(dims),
            "n_elements": elements,
            "block_size": block_size,
            "type_bytes": type_bytes,
            "nbytes": self.sizes[index],
            "offset": self.offsets[index],
            "absolute_offset": self.absolute(index),
            "claimed_absolute_offset": claimed_offset,
            "claimed_nbytes": claimed_nbytes,
        }

    def block_expect(self, block_index, kind, layer, expert, members):
        """`members` is a list of (role, tensor index, slice index or None)."""
        tensors = [self.tensor_expect(index, role, slice_index)
                   for role, index, slice_index in members]
        byte_size = sum(t["claimed_nbytes"] for t in tensors)
        first = min(t["claimed_absolute_offset"] for t in tensors)
        end = max(t["claimed_absolute_offset"] + t["claimed_nbytes"] for t in tensors)
        return {
            "index": block_index,
            "kind": kind,
            "layer": layer,
            "expert": expert,
            "tensor_count": len(tensors),
            "byte_size": byte_size,
            "first_absolute_offset": first,
            "end_absolute_offset": end,
            "contiguous": end - first == byte_size,
            "tensors": tensors,
        }

    def blocks_expect(self):
        blocks = []
        index = 0
        blocks.append(self.block_expect(index, "WeightBlock", -1, -1,
                                        [("token_embd", self.index_of("token_embd.weight"), None)]))
        index += 1
        for layer in range(self.p["n_layer"]):
            attention = [(role, self.index_of(gptoss_role_name(role, layer)), None)
                         for role in GPTOSS_ATTENTION_ROLES if role not in self.drop_roles]
            blocks.append(self.block_expect(index, "AttentionBlock", layer, -1, attention))
            index += 1
            router = [(role, self.index_of(gptoss_role_name(role, layer)), None)
                      for role in GPTOSS_ROUTER_ROLES if role not in self.drop_roles]
            blocks.append(self.block_expect(index, "RouterBlock", layer, -1, router))
            index += 1
            for expert in range(self.p["n_expert"]):
                members = [(role, self.index_of(gptoss_role_name(role, layer)), expert)
                           for role in self.expert_roles if role not in self.drop_roles]
                blocks.append(self.block_expect(index, "ExpertBlock", layer, expert, members))
                index += 1
        output_source = "token_embd.weight" if self.tied else "output.weight"
        blocks.append(self.block_expect(
            index, "WeightBlock", -1, -1,
            [("output_norm", self.index_of("output_norm.weight"), None),
             ("output", self.index_of(output_source), None)]))
        return blocks

    def block_count(self):
        return self.p["n_layer"] * (2 + self.p["n_expert"]) + 2

    def quant_expect(self):
        rows = []
        for type_id in sorted(set(entry[4] for entry in self.entries)):
            members = [i for i, entry in enumerate(self.entries) if entry[4] == type_id]
            rows.append({
                "type": type_id,
                "type_name": GGML_NAMES[type_id],
                "tensor_count": len(members),
                "bytes": sum(self.sizes[i] for i in members),
            })
        return {
            "file_type": 15,
            "file_type_present": True,
            "type_counts": rows,
            "total_tensor_bytes": self.total_bytes,
        }

    def model_expect(self, rope_dim=None, scaling=None):
        return {
            "arch": self.arch,
            "n_layer": self.p["n_layer"],
            "n_embd": self.p["n_embd"],
            "n_head": self.p["n_head"],
            "n_head_kv": self.p["n_head_kv"],
            "head_dim": self.head_dim,
            "head_dim_source": self.head_dim_source,
            "n_ff": self.p["n_ff"],
            "n_ff_exp": self.ff_exp,
            "n_ff_exp_source": self.ff_exp_source,
            "n_vocab": self.p["n_vocab"],
            "n_expert": self.p["n_expert"],
            "n_expert_used": self.p["n_expert_used"],
            "expert_ffn_layout": "fused" if self.fused else "split",
            "context_length": self.p["context_length"],
            "sliding_window": self.p.get("sliding_window"),
            "sliding_window_pattern": self.p.get("sliding_window_pattern"),
            "rms_eps": marker_f32(f32_bits(1e-06)),
            "rms_eps_bits": "%08x" % f32_bits(1e-06),
            "rope": {
                "type": 2,
                "type_name": "neox",
                "type_source": "architecture",
                "freq_base": marker_f32(f32_bits(1000000.0)),
                "freq_base_bits": "%08x" % f32_bits(1000000.0),
                "dim_count": self.head_dim if rope_dim is None else rope_dim,
                "dim_count_source": "derived" if rope_dim is None else "metadata",
                "scaling_type": scaling,
            },
        }

    def coverage_expect(self):
        return {
            "tensor_count": len(self.entries),
            "assigned_tensor_count": len(self.entries),
            "unassigned_tensors": [],
            "block_count": self.block_count(),
            "data_offset": self.container.data_offset,
            "total_tensor_bytes": self.total_bytes,
            "computed_end": self.container.data_offset + self.total_bytes,
            "file_size": len(self.bytes),
            "size_sum_ok": True,
        }

    def source_expect(self):
        # The header and the tensor table of every fixture here fit inside one window, so the walk
        # issues exactly one `pread`: `bytes_read` is the whole file when the file is smaller than
        # the window and exactly one window otherwise. Section 4.6's secondary metric is that the
        # derivation never starts reading the data section.
        return {
            "gguf_version": 3,
            "alignment": DEFAULT_ALIGNMENT,
            "file_size": len(self.bytes),
            "data_offset": self.container.data_offset,
            "tensor_count": len(self.entries),
            "metadata_kv_count": len(self.container.kvs),
            "bytes_read": min(len(self.bytes), WINDOW_BYTES),
        }

    def positive(self, name, file_name, rope_dim=None, scaling=None, with_blocks=True, **extra):
        case = {
            "name": name,
            "file": file_name,
            "bytes": self.bytes,
            "exit": 0,
            "source": self.source_expect(),
            "model": self.model_expect(rope_dim=rope_dim, scaling=scaling),
            "quant": self.quant_expect(),
            "coverage": self.coverage_expect(),
            "arch": "gpt-oss",
        }
        if with_blocks:
            case["blocks"] = self.blocks_expect()
        case.update(extra)
        return case


def gptoss_build(out_dir):
    """The section 4.1 gpt-oss corpus: the positive fixtures including both expert layouts, and one
    negative fixture per new or extended row of section 2.6."""
    cases = []

    def negative(name, file_name, payload, code, detail, **extra):
        case = {"name": name, "file": file_name, "bytes": payload, "exit": 1,
                "error": {"code": code, "detail": detail}, "arch": "gpt-oss"}
        case.update(extra)
        cases.append(case)
        return case

    # ---- positive: the complete synthetic gpt-oss container ------------------------------------
    full = GptOssModel()
    assert len(full.bytes) < 1048576, len(full.bytes)
    assert full.container.data_offset + full.total_bytes == len(full.bytes)
    # Section 4.1's arithmetic, asserted rather than assumed.
    assert full.total_bytes == 787136, full.total_bytes
    assert len(full.entries) == 41, len(full.entries)
    assert full.block_count() == 22, full.block_count()
    assert sum(b["tensor_count"] for b in full.blocks_expect()) == 125
    # `head_dim` is 64 from the declared key while `n_embd / n_head` is 32, so the two rules MUST
    # disagree in the base fixture: a frontend that silently fell back to the division would expect
    # a `[256, 256]` `attn_q.weight` against this file's `[256, 512]` and fail.
    assert full.head_dim == 64 and full.p["n_embd"] // full.p["n_head"] == 32
    assert [row["type"] for row in full.quant_expect()["type_counts"]] == [0, 8, 12, 14, 39]
    cases.append(full.positive(
        "gptoss-full", "gptoss-full.gguf",
        bytes_read=len(full.bytes),
        field_order=True,
        expert_tiling=True,
    ))

    # `attention.key_length` absent: `head_dim` falls back to `n_embd / n_head` and every attention
    # width narrows with it.
    derived = GptOssModel(p={"key_length": None, "value_length": None})
    assert derived.head_dim == 32
    cases.append(derived.positive("gptoss-headdim-derived", "gptoss-headdim-derived.gguf"))

    # `expert_feed_forward_length` absent: `n_ff_exp` falls back to `n_ff`.
    ff_absent = GptOssModel(p={"n_ff_exp": None})
    assert ff_absent.ff_exp == GPTOSS_BASE["n_ff"] and ff_absent.ff_exp_source == "derived"
    cases.append(ff_absent.positive("gptoss-ffexp-absent", "gptoss-ffexp-absent.gguf"))

    # Both optional sliding-window keys absent: reported as `null`, never interpreted.
    no_window = GptOssModel(p={"sliding_window": None, "sliding_window_pattern": None})
    cases.append(no_window.positive("gptoss-optional-absent", "gptoss-optional-absent.gguf"))

    # Section 2.5.4's fused expert feed-forward layout, with the fused bias present.
    fused = GptOssModel(fused=True)
    cases.append(fused.positive("gptoss-variant-fused", "gptoss-variant-fused.gguf",
                                expert_tiling=True))

    # The same layout with `ffn_gate_up_exps.bias` absent. Only the fused **weight** is attested by
    # the installed artifacts (`blk\.\d*\.ffn_gate_up(_exps)?.weight`), so the fused bias is an
    # optional member like the router bias: dropped from each `ExpertBlock`, never an error. Each
    # `ExpertBlock` therefore carries three members instead of four, and the tiling oracle still
    # holds over the remaining stacked tensors.
    fused_nobias = GptOssModel(fused=True, drop_roles=("ffn_gate_up_exps_bias",))
    fused_nobias_case = fused_nobias.positive(
        "gptoss-variant-fused-nobias", "gptoss-variant-fused-nobias.gguf", expert_tiling=True)
    assert all(block["tensor_count"] == 3
               for block in fused_nobias_case["blocks"] if block["kind"] == "ExpertBlock"), \
        "fused-nobias ExpertBlock member count"
    cases.append(fused_nobias_case)

    # The optional `RouterBlock` member: an absent `ffn_gate_inp.bias` is dropped, not an error.
    no_router_bias = GptOssModel(drop_roles=("router_bias",))
    cases.append(no_router_bias.positive("gptoss-router-bias-absent",
                                         "gptoss-router-bias-absent.gguf"))

    # The data section grouped by role across layers, so at least one ExpertBlock is non-contiguous
    # while the size-sum and claim-tiling oracles both still hold.
    def role_major(entries):
        return sorted(range(len(entries)),
                      key=lambda i: (entries[i][0], entries[i][1] if entries[i][1] is not None else -1))

    permuted = GptOssModel(layout=role_major)
    permuted_case = permuted.positive("gptoss-permuted", "gptoss-permuted.gguf", expert_tiling=True)
    assert any(not block["contiguous"] for block in permuted_case["blocks"]), "layout is contiguous"
    cases.append(permuted_case)

    # Tied embeddings: `token_embd.weight` is claimed whole by two blocks, which is the branch of the
    # claim-tiling rule that a partition cannot express.
    tied = GptOssModel(tied=True)
    tied_case = tied.positive("gptoss-tied", "gptoss-tied.gguf", expert_tiling=True)
    tied_case["tied"] = True
    cases.append(tied_case)

    # `bounded-work`: 8 layers and 64 experts give 530 blocks and 3,179 claims inside the existing
    # budget. Its document is asserted structurally rather than field by field, because a per-record
    # expectation for 3,179 claims would make the manifest, not the derivation, the slow part.
    wide_types = {role: 0 for role in GPTOSS_TYPES}
    for role in ("ffn_gate_exps", "ffn_up_exps", "ffn_down_exps", "ffn_gate_up_exps"):
        wide_types[role] = 39
    wide = GptOssModel(
        p={"n_layer": 8, "n_expert": 64, "n_expert_used": 4, "n_embd": 64, "n_head": 8,
           "key_length": 8, "value_length": 8, "n_ff": 32, "n_ff_exp": 32},
        types=wide_types)
    assert wide.block_count() == 530, wide.block_count()
    cases.append(wide.positive("gptoss-wide", "gptoss-wide.gguf", with_blocks=False,
                               bounded_work=True, expert_tiling=True,
                               blocks_len=530, claim_count=3179))

    # ---- negative corpus: one fixture per new or extended section 2.6 row ----------------------
    def bare(p=None, drop=(), overrides=None, extra=None):
        """A container whose metadata is complete enough to reach the step under test and whose
        tensor table is one tensor, so an implausible expert count does not have to be materialized
        as half a million tensors."""
        params = dict(GPTOSS_BASE)
        params.update(p or {})
        return Container(
            gptoss_kvs(params, drop=drop, overrides=overrides, extra=extra),
            [Tensor("token_embd.weight", [256, 32], 0, 0)],
            data_len=32768,
        )

    negative("gptoss-expert-zero", "gptoss-expert-zero.gguf",
             bare(p={"n_expert": 0, "n_expert_used": 0}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "gpt-oss.expert_count", blocks_len=0)

    negative("gptoss-expert-huge", "gptoss-expert-huge.gguf",
             bare(p={"n_expert": 4096}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "gpt-oss.expert_count", blocks_len=0)

    negative("gptoss-expert-missing", "gptoss-expert-missing.gguf",
             bare(drop=("gpt-oss.expert_count",)).bytes,
             "R1_MISSING_KEY", "gpt-oss.expert_count", blocks_len=0)

    negative("gptoss-expert-type", "gptoss-expert-type.gguf",
             bare(overrides={"gpt-oss.expert_count": strv("8")}).bytes,
             "R1_KEY_TYPE_MISMATCH", "gpt-oss.expert_count", blocks_len=0)

    negative("gptoss-expert-used-zero", "gptoss-expert-used-zero.gguf",
             bare(p={"n_expert_used": 0}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "gpt-oss.expert_used_count", blocks_len=0)

    negative("gptoss-expert-used-high", "gptoss-expert-used-high.gguf",
             bare(p={"n_expert_used": GPTOSS_BASE["n_expert"] + 1}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "gpt-oss.expert_used_count", blocks_len=0)

    # `n_layer * (2 + n_expert) + 2 = 525,314`, well past MAX_BLOCKS, with both operands individually
    # inside their own bounds. The guard is tested in non-wrapping form before the product.
    explosion = bare(p={"n_layer": 512, "n_expert": 1024, "n_expert_used": 4})
    assert 512 * (2 + 1024) + 2 > MAX_BLOCKS
    negative("gptoss-block-explosion", "gptoss-block-explosion.gguf", explosion.bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "gpt-oss.expert_count", blocks_len=0)

    negative("gptoss-keylength-mismatch", "gptoss-keylength-mismatch.gguf",
             bare(p={"value_length": 32}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "gpt-oss.attention.value_length", blocks_len=0)

    negative("gptoss-keylength-absent-value", "gptoss-keylength-absent-value.gguf",
             bare(drop=("gpt-oss.attention.value_length",)).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "gpt-oss.attention.value_length", blocks_len=0)

    # A derived `head_dim` that does not divide exactly.
    negative("gptoss-headdim-indivisible", "gptoss-headdim-indivisible.gguf",
             bare(p={"key_length": None, "value_length": None, "n_head": 3, "n_head_kv": 1}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "gpt-oss.embedding_length", blocks_len=0)

    def reshape_dims(entries, name, dims):
        return [(role, layer, entry_name, dims if entry_name == name else entry_dims, type_id)
                for (role, layer, entry_name, entry_dims, type_id) in entries]

    # The stacked-tensor rule: the expert axis must be the last declared axis with extent exactly
    # `n_expert`. Blocks completed before the failure: embedding, attention 0, router 0.
    stacked_axis = GptOssModel(
        mutate=lambda e: reshape_dims(e, "blk.0.ffn_gate_exps.weight", [32, 256, 4]))
    negative("gptoss-stacked-axis", "gptoss-stacked-axis.gguf", stacked_axis.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "blk.0.ffn_gate_exps.weight", blocks_len=3)

    stacked_ndims = GptOssModel(
        mutate=lambda e: reshape_dims(e, "blk.0.ffn_gate_exps.weight", [32, 256]))
    negative("gptoss-stacked-ndims", "gptoss-stacked-ndims.gguf", stacked_ndims.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "blk.0.ffn_gate_exps.weight", blocks_len=3)

    router_shape = GptOssModel(
        mutate=lambda e: reshape_dims(e, "blk.0.ffn_gate_inp.weight", [256, 4]))
    negative("gptoss-router-shape", "gptoss-router-shape.gguf", router_shape.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "blk.0.ffn_gate_inp.weight", blocks_len=2)

    # Neither the split pair nor the fused tensor: the diagnostic names variant 0's first missing
    # required member, because that is the form the plan prefers.
    variant_none = GptOssModel(drop_roles=("ffn_gate_exps",))
    negative("gptoss-variant-none", "gptoss-variant-none.gguf", variant_none.bytes,
             "R1_MISSING_TENSOR", "blk.0.ffn_gate_exps.weight", blocks_len=3)

    # An MXFP4 tensor whose first axis is not a multiple of 32 is unrepresentable and is never sized.
    # The defect is patched into the written bytes because the generator's own sizing asserts the
    # row rule it is testing.
    row_unaligned = patched(
        full, full.container.tensor_offsets[full.index_of("blk.0.ffn_gate_exps.weight")]["dims"],
        struct.pack("<Q", 48))
    negative("gptoss-mxfp4-row-unaligned", "gptoss-mxfp4-row-unaligned.gguf", row_unaligned,
             "R1_TENSOR_SHAPE_UNALIGNED", "blk.0.ffn_gate_exps.weight", blocks_len=0)

    # NVFP4 (id 40) has a name in no table and a geometry in none: it must stay
    # `R1_UNKNOWN_TENSOR_TYPE` exactly like an id GGML has never used.
    unknown = patched(
        full, full.container.tensor_offsets[full.index_of("blk.0.attn_norm.weight")]["type"],
        struct.pack("<I", 40))
    negative("gptoss-unknown-type", "gptoss-unknown-type.gguf", unknown,
             "R1_UNKNOWN_TENSOR_TYPE", "40", blocks_len=0)

    wrong_arch = GptOssModel(arch="qwen2")
    negative("gptoss-wrong-arch", "gptoss-wrong-arch.gguf", wrong_arch.bytes,
             "R1_MISSING_KEY", "qwen2.block_count", blocks_len=0, arch="qwen2")

    extra_expert = GptOssModel(mutate=lambda e: e + [
        ("ffn_gate_exps", 9, "blk.9.ffn_gate_exps.weight", [32, 256, 8], 39)])
    negative("gptoss-extra-expert", "gptoss-extra-expert.gguf", extra_expert.bytes,
             "R1_UNASSIGNED_TENSOR", "blk.9.ffn_gate_exps.weight",
             unassigned=["blk.9.ffn_gate_exps.weight"])

    size_sum = GptOssModel(trailing=64)
    negative("gptoss-size-sum", "gptoss-size-sum.gguf", size_sum.bytes,
             "R1_SIZE_SUM_MISMATCH",
             "%d!=%d" % (size_sum.container.data_offset + size_sum.total_bytes,
                         len(size_sum.bytes)))

    # ---- precedence: the earlier section 2.6 row wins ------------------------------------------
    precedence_key = GptOssModel(
        overrides={"gpt-oss.embedding_length": strv("256")},
        mutate=lambda e: reshape_dims(e, "blk.0.ffn_gate_exps.weight", [32, 256, 4]))
    negative("gptoss-precedence-key-shape", "gptoss-precedence-key-shape.gguf",
             precedence_key.bytes, "R1_KEY_TYPE_MISMATCH", "gpt-oss.embedding_length", blocks_len=0)

    # An out-of-bounds `expert_used_count` (step 7) and a zero vocabulary (step 9): the expert row.
    precedence_expert = GptOssModel(
        p={"n_expert_used": GPTOSS_BASE["n_expert"] + 1},
        mutate=lambda e: reshape_dims(e, "token_embd.weight", [256, 0]))
    negative("gptoss-precedence-expert-vocab", "gptoss-precedence-expert-vocab.gguf",
             precedence_expert.bytes, "R1_KEY_VALUE_IMPLAUSIBLE", "gpt-oss.expert_used_count",
             blocks_len=0)

    for case in cases:
        write(out_dir, case["file"], case.pop("bytes"))
    return cases


# =================================================================================================
# R1C-OLMOE-MOE-IR corpus (`docs/specs/r1c-olmoe-moe-ir.md` section 4.1).
#
# The generator is extended, not replaced: `GGML_GEOMETRY` and `GEOMETRY_TYPES` are untouched, so no
# existing R0, R1, or R1B fixture's bytes change. Every expected `nbytes`, every per-expert claim,
# and every block byte total is computed here in Python from the bytes this file writes, which is
# what makes the claim-tiling oracle a differential check rather than a mirror of the derivation.
#
# **Every key name, tensor name, and shape below is MEASURED** on a real 3.92 GiB model (section
# 2.1). The fixture deliberately mirrors the real model's shape *relationships* rather than its
# extents: MHA (`n_head == n_head_kv`), no declared `attention.key_length`, no declared
# `expert_feed_forward_length`, no bias of any kind, no `attn_sinks`, and no fused
# `ffn_gate_up_exps`.
# =================================================================================================

OLMOE_BASE = {
    "n_layer": 2, "n_embd": 256, "n_head": 8, "n_head_kv": 8,
    "n_ff": 64, "n_expert": 8, "n_expert_used": 3,
    "n_vocab": 32, "context_length": 512,
}

# `attn_output` is Q8_0, `attn_q` / `attn_k` / `token_embd` / the stacked gate and up projections are
# Q4_K, `attn_v` and `output` are Q6_K, and every norm, both QK-norms, and the router are F32 — four
# ascending `quant.type_counts` rows (ids 0, 8, 12, 14).
#
# `ffn_down_exps` is `[n_ff_exp, n_embd, n_expert]` = `[64, 256, 8]`, and `64 % 256 != 0`, so a K-
# quantized `ffn_down_exps` is `R1_TENSOR_SHAPE_UNALIGNED` at these extents: the row rule bites. It
# is therefore F32 in the base fixture, and the per-layer mixed-type pattern that matters is carried
# by `olmoe-mixed-quant`, whose own extents make both K-quantizations representable.
OLMOE_TYPES = {
    "token_embd": 12, "output_norm": 0, "output": 14,
    "attn_norm": 0, "attn_q": 12, "attn_q_norm": 0, "attn_k": 12, "attn_k_norm": 0,
    "attn_v": 14, "attn_output": 8, "ffn_norm": 0, "router": 0,
    "ffn_gate_exps": 12, "ffn_up_exps": 12, "ffn_down_exps": 0,
}

OLMOE_GLOBAL_ROLES = ["token_embd", "output_norm", "output"]
# The emission order of section 2.5.3: both QK-norms ride in the `AttentionBlock`, beside the
# projection whose output they normalize.
OLMOE_ATTENTION_ROLES = [
    "attn_norm", "attn_q", "attn_q_norm", "attn_k", "attn_k_norm", "attn_v", "attn_output",
]
OLMOE_ROUTER_ROLES = ["ffn_norm", "router"]
OLMOE_EXPERT_ROLES = ["ffn_gate_exps", "ffn_up_exps", "ffn_down_exps"]
OLMOE_LAYER_ROLES = OLMOE_ATTENTION_ROLES + OLMOE_ROUTER_ROLES + OLMOE_EXPERT_ROLES
# The roles the plan slices: their expert axis is the last declared one, with extent `n_expert`.
OLMOE_SLICED = set(OLMOE_EXPERT_ROLES)

OLMOE_SUFFIX = {
    "attn_norm": "attn_norm.weight", "attn_q": "attn_q.weight",
    "attn_q_norm": "attn_q_norm.weight", "attn_k": "attn_k.weight",
    "attn_k_norm": "attn_k_norm.weight", "attn_v": "attn_v.weight",
    "attn_output": "attn_output.weight", "ffn_norm": "ffn_norm.weight",
    "router": "ffn_gate_inp.weight",
    "ffn_gate_exps": "ffn_gate_exps.weight", "ffn_up_exps": "ffn_up_exps.weight",
    "ffn_down_exps": "ffn_down_exps.weight",
}


def olmoe_head_dim(p):
    if p.get("key_length") is not None:
        return p["key_length"]
    return p["n_embd"] // p["n_head"]


def olmoe_ff_exp(p):
    if p.get("n_ff_exp") is not None:
        return p["n_ff_exp"]
    return p["n_ff"]


def olmoe_role_shape(role, p):
    """The measured shape table of section 2.5.3: the dense convention of `src/frontend_qwen.align`
    plus an expert axis, which is the reverse of the gpt-oss frontend's assumed order."""
    head_dim = olmoe_head_dim(p)
    ff = olmoe_ff_exp(p)
    e, v, x = p["n_embd"], p["n_vocab"], p["n_expert"]
    q, kv = p["n_head"] * head_dim, p["n_head_kv"] * head_dim
    return {
        "token_embd": [e, v], "output": [e, v], "output_norm": [e],
        "attn_norm": [e], "attn_q": [e, q], "attn_q_norm": [e],
        "attn_k": [e, kv], "attn_k_norm": [e], "attn_v": [e, kv],
        "attn_output": [q, e], "ffn_norm": [e], "router": [e, x],
        "ffn_gate_exps": [e, ff, x], "ffn_up_exps": [e, ff, x], "ffn_down_exps": [ff, e, x],
    }[role]


def olmoe_role_name(role, layer):
    if layer is None:
        return {"token_embd": "token_embd.weight", "output_norm": "output_norm.weight",
                "output": "output.weight"}[role]
    return "blk.%d.%s" % (layer, OLMOE_SUFFIX[role])


def olmoe_kvs(p, arch="olmoe", drop=(), overrides=None, extra=None):
    """The metadata block, in the order a converter plausibly writes it. Presence, type, and value
    are all validated in the section 2.6 order, so the file order below is deliberately not that
    order."""
    overrides = overrides or {}
    rows = [
        ("general.architecture", strv(arch)),
        ("general.file_type", u32v(15)),
        ("general.quantization_version", u32v(2)),
        ("olmoe.block_count", u32v(p["n_layer"])),
        ("olmoe.context_length", u32v(p["context_length"])),
        ("olmoe.embedding_length", u32v(p["n_embd"])),
        ("olmoe.feed_forward_length", u32v(p["n_ff"])),
        ("olmoe.expert_feed_forward_length",
         u32v(p["n_ff_exp"]) if p.get("n_ff_exp") is not None else None),
        ("olmoe.expert_count", u32v(p["n_expert"])),
        ("olmoe.expert_used_count", u32v(p["n_expert_used"])),
        ("olmoe.attention.head_count", u32v(p["n_head"])),
        ("olmoe.attention.head_count_kv", u32v(p["n_head_kv"])),
        ("olmoe.attention.key_length",
         u32v(p["key_length"]) if p.get("key_length") is not None else None),
        ("olmoe.attention.value_length",
         u32v(p["value_length"]) if p.get("value_length") is not None else None),
        ("olmoe.rope.freq_base", f32v(10000.0)),
        ("olmoe.attention.layer_norm_rms_epsilon", f32v(1e-05)),
        ("tokenizer.ggml.tokens", Array(STRING, [strv("t%d" % i) for i in range(p["n_vocab"])])),
    ]
    out = []
    for key, value in rows:
        if value is None or key in drop:
            continue
        out.append(Kv(key, overrides.get(key, value)))
    for key, value in (extra or []):
        out.append(Kv(key, value))
    return out


class OlmoeModel:
    """A synthetic olmoe container plus every expected value of its `R1_MODEL_IR` document."""

    def __init__(self, p=None, types=None, layer_types=None, tied=False, arch="olmoe", drop=(),
                 overrides=None, extra=None, layout=None, trailing=0, mutate=None,
                 drop_roles=()):
        self.p = dict(OLMOE_BASE)
        self.p.update(p or {})
        self.types = dict(OLMOE_TYPES)
        if types:
            self.types.update(types)
        # Section 2.5.5: the same role may carry a different GGML type in different layers, which is
        # llama.cpp's ordinary `Q4_K_M` mixed-precision scheme and which neither the R1 nor the R1B
        # corpus contains. `{role: {layer: type_id}}`.
        self.layer_types = {role: dict(rows) for role, rows in (layer_types or {}).items()}
        self.tied = tied
        self.drop_roles = set(drop_roles)
        head_dim = olmoe_head_dim(self.p)
        self.head_dim = head_dim
        self.head_dim_source = "metadata" if self.p.get("key_length") is not None else "derived"
        self.ff_exp = olmoe_ff_exp(self.p)
        self.ff_exp_source = "metadata" if self.p.get("n_ff_exp") is not None else "derived"

        # ---- tensor table, in file order ------------------------------------------------------
        self.entries = []          # (role, layer, name, dims, type_id)
        for role in OLMOE_GLOBAL_ROLES:
            if role == "output" and tied:
                continue
            if role in self.drop_roles:
                continue
            self.entries.append((role, None, olmoe_role_name(role, None),
                                 olmoe_role_shape(role, self.p), self.type_of(role, None)))
        for layer in range(self.p["n_layer"]):
            for role in OLMOE_LAYER_ROLES:
                if role in self.drop_roles:
                    continue
                self.entries.append((role, layer, olmoe_role_name(role, layer),
                                     olmoe_role_shape(role, self.p), self.type_of(role, layer)))
        if mutate:
            self.entries = mutate(self.entries)

        # ---- data-section layout --------------------------------------------------------------
        # Every tensor's byte size is a multiple of the 32-byte container alignment, and for a
        # sliced tensor so is every expert plane, or a contiguous placement could not also be
        # alignment-correct and the size-sum oracle would be unsatisfiable.
        sizes = [nbytes_of(dims, type_id) if type_id in GGML_GEOMETRY else 0
                 for (_, _, _, dims, type_id) in self.entries]
        order = layout(self.entries) if layout else list(range(len(self.entries)))
        offsets = [0] * len(self.entries)
        cursor = 0
        for position in order:
            assert cursor % DEFAULT_ALIGNMENT == 0, (position, cursor)
            offsets[position] = cursor
            cursor += sizes[position]
        self.sizes = sizes
        self.offsets = offsets
        self.total_bytes = cursor

        tensors = [Tensor(name, dims, type_id, offsets[index])
                   for index, (_, _, name, dims, type_id) in enumerate(self.entries)]
        kvs = olmoe_kvs(self.p, arch=arch, drop=drop, overrides=overrides, extra=extra)
        self.container = Container(kvs, tensors, data_len=cursor + trailing)
        self.bytes = self.container.bytes
        self.arch = arch

    def type_of(self, role, layer):
        per_layer = self.layer_types.get(role)
        if per_layer is not None and layer in per_layer:
            return per_layer[layer]
        return self.types[role]

    def index_of(self, name):
        for index, (_, _, entry_name, _, _) in enumerate(self.entries):
            if entry_name == name:
                return index
        return -1

    def absolute(self, index):
        return self.container.data_offset + self.offsets[index]

    def claim(self, index, slice_index):
        """Section 2.5.4, computed in Python: the last declared axis is the outermost, so each of
        its indices owns one contiguous byte plane."""
        _, _, _, dims, _ = self.entries[index]
        if slice_index is None:
            return self.absolute(index), self.sizes[index]
        last = dims[-1]
        assert self.sizes[index] % last == 0, (dims, self.sizes[index], last)
        plane = self.sizes[index] // last
        return self.absolute(index) + plane * slice_index, plane

    def tensor_expect(self, index, role, slice_index=None):
        _, _, name, dims, type_id = self.entries[index]
        elements = 1
        for extent in dims:
            elements *= extent
        block_size, type_bytes = GGML_GEOMETRY[type_id]
        claimed_offset, claimed_nbytes = self.claim(index, slice_index)
        return {
            "name": name,
            "role": role,
            "type": type_id,
            "type_name": GGML_NAMES[type_id],
            "n_dims": len(dims),
            "dims": list(dims),
            "n_elements": elements,
            "block_size": block_size,
            "type_bytes": type_bytes,
            "nbytes": self.sizes[index],
            "offset": self.offsets[index],
            "absolute_offset": self.absolute(index),
            "claimed_absolute_offset": claimed_offset,
            "claimed_nbytes": claimed_nbytes,
        }

    def block_expect(self, block_index, kind, layer, expert, members):
        """`members` is a list of (role, tensor index, slice index or None)."""
        tensors = [self.tensor_expect(index, role, slice_index)
                   for role, index, slice_index in members]
        byte_size = sum(t["claimed_nbytes"] for t in tensors)
        first = min(t["claimed_absolute_offset"] for t in tensors)
        end = max(t["claimed_absolute_offset"] + t["claimed_nbytes"] for t in tensors)
        return {
            "index": block_index,
            "kind": kind,
            "layer": layer,
            "expert": expert,
            "tensor_count": len(tensors),
            "byte_size": byte_size,
            "first_absolute_offset": first,
            "end_absolute_offset": end,
            "contiguous": end - first == byte_size,
            "tensors": tensors,
        }

    def blocks_expect(self):
        blocks = []
        index = 0
        blocks.append(self.block_expect(index, "WeightBlock", -1, -1,
                                        [("token_embd", self.index_of("token_embd.weight"), None)]))
        index += 1
        for layer in range(self.p["n_layer"]):
            attention = [(role, self.index_of(olmoe_role_name(role, layer)), None)
                         for role in OLMOE_ATTENTION_ROLES if role not in self.drop_roles]
            blocks.append(self.block_expect(index, "AttentionBlock", layer, -1, attention))
            index += 1
            router = [(role, self.index_of(olmoe_role_name(role, layer)), None)
                      for role in OLMOE_ROUTER_ROLES if role not in self.drop_roles]
            blocks.append(self.block_expect(index, "RouterBlock", layer, -1, router))
            index += 1
            for expert in range(self.p["n_expert"]):
                members = [(role, self.index_of(olmoe_role_name(role, layer)), expert)
                           for role in OLMOE_EXPERT_ROLES if role not in self.drop_roles]
                blocks.append(self.block_expect(index, "ExpertBlock", layer, expert, members))
                index += 1
        output_source = "token_embd.weight" if self.tied else "output.weight"
        blocks.append(self.block_expect(
            index, "WeightBlock", -1, -1,
            [("output_norm", self.index_of("output_norm.weight"), None),
             ("output", self.index_of(output_source), None)]))
        return blocks

    def block_count(self):
        return self.p["n_layer"] * (2 + self.p["n_expert"]) + 2

    def claim_count(self):
        return 1 + self.p["n_layer"] * (7 + 2 + 3 * self.p["n_expert"]) + 2

    def quant_expect(self):
        rows = []
        for type_id in sorted(set(entry[4] for entry in self.entries)):
            members = [i for i, entry in enumerate(self.entries) if entry[4] == type_id]
            rows.append({
                "type": type_id,
                "type_name": GGML_NAMES[type_id],
                "tensor_count": len(members),
                "bytes": sum(self.sizes[i] for i in members),
            })
        return {
            "file_type": 15,
            "file_type_present": True,
            "type_counts": rows,
            "total_tensor_bytes": self.total_bytes,
        }

    def model_expect(self, rope_dim=None, scaling=None):
        """Section 2.4's normative olmoe field list: the gpt-oss list minus `expert_ffn_layout`,
        `sliding_window`, and `sliding_window_pattern`, each omitted for a stated reason."""
        return {
            "arch": self.arch,
            "n_layer": self.p["n_layer"],
            "n_embd": self.p["n_embd"],
            "n_head": self.p["n_head"],
            "n_head_kv": self.p["n_head_kv"],
            "head_dim": self.head_dim,
            "head_dim_source": self.head_dim_source,
            "n_ff": self.p["n_ff"],
            "n_ff_exp": self.ff_exp,
            "n_ff_exp_source": self.ff_exp_source,
            "n_vocab": self.p["n_vocab"],
            "n_expert": self.p["n_expert"],
            "n_expert_used": self.p["n_expert_used"],
            "context_length": self.p["context_length"],
            "rms_eps": marker_f32(f32_bits(1e-05)),
            "rms_eps_bits": "%08x" % f32_bits(1e-05),
            "rope": {
                "type": 2,
                "type_name": "neox",
                "type_source": "architecture",
                "freq_base": marker_f32(f32_bits(10000.0)),
                "freq_base_bits": "%08x" % f32_bits(10000.0),
                "dim_count": self.head_dim if rope_dim is None else rope_dim,
                "dim_count_source": "derived" if rope_dim is None else "metadata",
                "scaling_type": scaling,
            },
        }

    def coverage_expect(self):
        return {
            "tensor_count": len(self.entries),
            "assigned_tensor_count": len(self.entries),
            "unassigned_tensors": [],
            "block_count": self.block_count(),
            "data_offset": self.container.data_offset,
            "total_tensor_bytes": self.total_bytes,
            "computed_end": self.container.data_offset + self.total_bytes,
            "file_size": len(self.bytes),
            "size_sum_ok": True,
        }

    def source_expect(self):
        return {
            "gguf_version": 3,
            "alignment": DEFAULT_ALIGNMENT,
            "file_size": len(self.bytes),
            "data_offset": self.container.data_offset,
            "tensor_count": len(self.entries),
            "metadata_kv_count": len(self.container.kvs),
            "bytes_read": min(len(self.bytes), WINDOW_BYTES),
        }

    def positive(self, name, file_name, rope_dim=None, scaling=None, with_blocks=True, **extra):
        case = {
            "name": name,
            "file": file_name,
            "bytes": self.bytes,
            "exit": 0,
            "source": self.source_expect(),
            "model": self.model_expect(rope_dim=rope_dim, scaling=scaling),
            "quant": self.quant_expect(),
            "coverage": self.coverage_expect(),
            "arch": "olmoe",
        }
        if with_blocks:
            case["blocks"] = self.blocks_expect()
        case.update(extra)
        return case


def olmoe_build(out_dir):
    """The section 4.1 olmoe corpus: the positive fixtures and one negative fixture per reachable
    row of section 2.6."""
    cases = []

    def negative(name, file_name, payload, code, detail, **extra):
        case = {"name": name, "file": file_name, "bytes": payload, "exit": 1,
                "error": {"code": code, "detail": detail}, "arch": "olmoe"}
        case.update(extra)
        cases.append(case)
        return case

    # ---- positive: the complete synthetic olmoe container --------------------------------------
    full = OlmoeModel()
    assert full.container.data_offset + full.total_bytes == len(full.bytes)
    # Section 4.1's arithmetic, asserted rather than assumed.
    assert len(full.entries) == 27, len(full.entries)
    assert full.block_count() == 22, full.block_count()
    assert full.claim_count() == 69, full.claim_count()
    assert sum(b["tensor_count"] for b in full.blocks_expect()) == 69
    # `head_dim` is derived and the division is exact, which is the opposite of the gpt-oss fixture
    # and is what the real model does (`2048 / 16 = 128`).
    assert full.head_dim == 32 and full.head_dim_source == "derived"
    assert full.ff_exp == OLMOE_BASE["n_ff"] and full.ff_exp_source == "derived"
    assert [row["type"] for row in full.quant_expect()["type_counts"]] == [0, 8, 12, 14]
    # Section 6's correction to section 4.1: the F32 `ffn_down_exps` the row rule forces is 524,288
    # bytes per layer, so this container is ~1.7 MiB rather than "well under 1 MiB". The
    # alignment-and-representability constraints are the load-bearing half of that sentence and are
    # what is asserted here.
    assert len(full.bytes) < 2 * 1048576, len(full.bytes)
    for index, (role, _, _, dims, type_id) in enumerate(full.entries):
        assert full.sizes[index] % DEFAULT_ALIGNMENT == 0, (role, dims, type_id)
        if role in OLMOE_SLICED:
            assert full.sizes[index] % (dims[-1] * DEFAULT_ALIGNMENT) == 0, (role, dims)
    cases.append(full.positive(
        "olmoe-full", "olmoe-full.gguf",
        # The container is larger than one window, so the walk reads exactly one window and never
        # the data section — which is the section 4.5 secondary metric, stated exactly.
        bytes_read=min(len(full.bytes), WINDOW_BYTES),
        field_order=True,
        expert_tiling=True,
        claim_count=69,
        slice_declaration=True,
    ))

    # `attention.key_length` present and disagreeing with the division: the declared key wins and
    # every attention width widens with it, so a frontend that always divided would fail here.
    head_meta = OlmoeModel(p={"key_length": 64, "value_length": 64})
    assert head_meta.head_dim == 64 and head_meta.p["n_embd"] // head_meta.p["n_head"] == 32
    assert head_meta.head_dim_source == "metadata"
    cases.append(head_meta.positive("olmoe-headdim-metadata", "olmoe-headdim-metadata.gguf",
                                    expert_tiling=True))

    # `expert_feed_forward_length` present and narrower than `n_ff`: every stacked shape narrows, so
    # a frontend that ignored the key would fail.
    ff_present = OlmoeModel(p={"n_ff_exp": 32})
    assert ff_present.ff_exp == 32 and ff_present.ff_exp_source == "metadata"
    cases.append(ff_present.positive("olmoe-ffexp-present", "olmoe-ffexp-present.gguf",
                                     expert_tiling=True))

    # Section 2.5.5, the real model's pattern at fixture scale: `attn_v` and `ffn_down_exps` are
    # Q6_K in layer 0 and Q4_K in layer 1, so one role carries two types and two blocks of the same
    # kind have different `byte_size`s. `n_ff` is 256 here because `ffn_down_exps` is
    # `[n_ff_exp, n_embd, n_expert]` and a K-quantized first axis must be a multiple of 256.
    mixed = OlmoeModel(
        p={"n_ff": 256, "n_expert": 2, "n_expert_used": 2},
        types={"ffn_down_exps": 14},
        layer_types={"ffn_down_exps": {1: 12}, "attn_v": {1: 12}})
    mixed_case = mixed.positive("olmoe-mixed-quant", "olmoe-mixed-quant.gguf",
                                expert_tiling=True, mixed_quant=True)
    mixed_blocks = mixed_case["blocks"]
    assert len({b["byte_size"] for b in mixed_blocks if b["kind"] == "AttentionBlock"}) == 2
    assert len({b["byte_size"] for b in mixed_blocks if b["kind"] == "ExpertBlock"}) == 2
    assert len(mixed.bytes) < 1048576, len(mixed.bytes)
    cases.append(mixed_case)

    # Tied embeddings: `token_embd.weight` is claimed whole by two blocks, which is the branch of the
    # claim-tiling rule a partition cannot express. The real model is untied; the rule costs one
    # optional lookup and this is the fixture that keeps it honest.
    tied = OlmoeModel(tied=True)
    tied_case = tied.positive("olmoe-tied", "olmoe-tied.gguf", expert_tiling=True)
    tied_case["tied"] = True
    cases.append(tied_case)

    # The data section grouped by role across layers, so an `AttentionBlock` and a `RouterBlock` are
    # also non-contiguous while both oracles still hold.
    def role_major(entries):
        return sorted(range(len(entries)),
                      key=lambda i: (entries[i][0],
                                     entries[i][1] if entries[i][1] is not None else -1))

    permuted = OlmoeModel(layout=role_major)
    permuted_case = permuted.positive("olmoe-permuted", "olmoe-permuted.gguf", expert_tiling=True)
    kinds = {block["kind"] for block in permuted_case["blocks"] if not block["contiguous"]}
    assert {"AttentionBlock", "RouterBlock", "ExpertBlock"} <= kinds, kinds
    cases.append(permuted_case)

    # `bounded-work`: 4 layers and 64 experts give 266 blocks and 807 claims inside the existing
    # budget. Everything is F32 but the stacked expert weights, which are Q8_0, so the container
    # stays under a megabyte at 64 experts.
    wide_types = {role: 0 for role in OLMOE_TYPES}
    for role in OLMOE_EXPERT_ROLES:
        wide_types[role] = 8
    wide = OlmoeModel(
        p={"n_layer": 4, "n_embd": 32, "n_head": 8, "n_head_kv": 8, "n_ff": 32,
           "n_expert": 64, "n_expert_used": 8},
        types=wide_types)
    assert wide.block_count() == 266, wide.block_count()
    assert wide.claim_count() == 807, wide.claim_count()
    assert len(wide.bytes) < 1048576, len(wide.bytes)
    cases.append(wide.positive("olmoe-wide", "olmoe-wide.gguf", with_blocks=False,
                               bounded_work=True, expert_tiling=True,
                               blocks_len=266, claim_count=807))

    # ---- negative corpus: one fixture per reachable section 2.6 row -----------------------------
    def bare(p=None, drop=(), overrides=None, extra=None):
        """A container whose metadata is complete enough to reach the step under test and whose
        tensor table is one tensor, so an implausible expert count does not have to be materialized
        as half a million tensors."""
        params = dict(OLMOE_BASE)
        params.update(p or {})
        return Container(
            olmoe_kvs(params, drop=drop, overrides=overrides, extra=extra),
            [Tensor("token_embd.weight", [256, 32], 0, 0)],
            data_len=32768,
        )

    # `olmoe-ir-error-sentinels` rides this case: a derivation that failed at step 7 must still
    # render every field of the olmoe `model` object explicitly, with `n_vocab` at its `-1`
    # sentinel because step 9 never ran and with the values steps 5 and 6 did read reported as
    # read. The field list and order are asserted strictly, so a failed derivation cannot emit a
    # different object from a successful one.
    negative("olmoe-expert-zero", "olmoe-expert-zero.gguf",
             bare(p={"n_expert": 0, "n_expert_used": 0}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "olmoe.expert_count", blocks_len=0,
             model={
                 "arch": "olmoe",
                 "n_layer": OLMOE_BASE["n_layer"],
                 "n_embd": OLMOE_BASE["n_embd"],
                 "n_head": OLMOE_BASE["n_head"],
                 "n_head_kv": OLMOE_BASE["n_head_kv"],
                 "head_dim": OLMOE_BASE["n_embd"] // OLMOE_BASE["n_head"],
                 "head_dim_source": "derived",
                 "n_ff": OLMOE_BASE["n_ff"],
                 "n_ff_exp": OLMOE_BASE["n_ff"],
                 "n_ff_exp_source": "derived",
                 "n_vocab": -1,
                 "n_expert": 0,
                 "n_expert_used": 0,
                 "context_length": OLMOE_BASE["context_length"],
                 "rms_eps": marker_f32(f32_bits(1e-05)),
                 "rms_eps_bits": "%08x" % f32_bits(1e-05),
                 "rope": {
                     "type": 2,
                     "type_name": "neox",
                     "type_source": "architecture",
                     "freq_base": marker_f32(f32_bits(10000.0)),
                     "freq_base_bits": "%08x" % f32_bits(10000.0),
                     "dim_count": OLMOE_BASE["n_embd"] // OLMOE_BASE["n_head"],
                     "dim_count_source": "derived",
                     "scaling_type": None,
                 },
             })

    negative("olmoe-expert-huge", "olmoe-expert-huge.gguf",
             bare(p={"n_expert": 4096}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "olmoe.expert_count", blocks_len=0)

    negative("olmoe-expert-missing", "olmoe-expert-missing.gguf",
             bare(drop=("olmoe.expert_count",)).bytes,
             "R1_MISSING_KEY", "olmoe.expert_count", blocks_len=0)

    negative("olmoe-expert-type", "olmoe-expert-type.gguf",
             bare(overrides={"olmoe.expert_count": strv("8")}).bytes,
             "R1_KEY_TYPE_MISMATCH", "olmoe.expert_count", blocks_len=0)

    negative("olmoe-expert-used-zero", "olmoe-expert-used-zero.gguf",
             bare(p={"n_expert_used": 0}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "olmoe.expert_used_count", blocks_len=0)

    negative("olmoe-expert-used-high", "olmoe-expert-used-high.gguf",
             bare(p={"n_expert_used": OLMOE_BASE["n_expert"] + 1}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "olmoe.expert_used_count", blocks_len=0)

    # `n_layer * (2 + n_expert) + 2 = 525,314`, well past MAX_BLOCKS, with both operands individually
    # inside their own bounds. The guard is tested in non-wrapping form before the product.
    assert 512 * (2 + 1024) + 2 > MAX_BLOCKS
    negative("olmoe-block-explosion", "olmoe-block-explosion.gguf",
             bare(p={"n_layer": 512, "n_expert": 1024, "n_expert_used": 4}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "olmoe.expert_count", blocks_len=0)

    negative("olmoe-zero-layer", "olmoe-zero-layer.gguf",
             bare(p={"n_layer": 0}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "olmoe.block_count", blocks_len=0)

    # A derived `head_dim` that does not divide exactly. `n_head % n_head_kv == 0` still holds, so
    # the earlier row does not fire and the head count is the divisor the diagnostic names.
    negative("olmoe-headdim-indivisible", "olmoe-headdim-indivisible.gguf",
             bare(p={"n_head": 3, "n_head_kv": 1}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "olmoe.attention.head_count", blocks_len=0)

    negative("olmoe-keylength-mismatch", "olmoe-keylength-mismatch.gguf",
             bare(p={"key_length": 64, "value_length": 32}).bytes,
             "R1_KEY_VALUE_IMPLAUSIBLE", "olmoe.attention.value_length", blocks_len=0)

    def reshape_dims(entries, name, dims):
        return [(role, layer, entry_name, dims if entry_name == name else entry_dims, type_id)
                for (role, layer, entry_name, entry_dims, type_id) in entries]

    # The stacked-tensor rule: the expert axis must be the last declared axis with extent exactly
    # `n_expert`. Blocks completed before the failure: embedding, attention 0, router 0.
    stacked_axis = OlmoeModel(
        mutate=lambda e: reshape_dims(e, "blk.0.ffn_gate_exps.weight", [256, 64, 4]))
    negative("olmoe-stacked-axis", "olmoe-stacked-axis.gguf", stacked_axis.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "blk.0.ffn_gate_exps.weight", blocks_len=3)

    stacked_ndims = OlmoeModel(
        mutate=lambda e: reshape_dims(e, "blk.0.ffn_gate_exps.weight", [256, 64]))
    negative("olmoe-stacked-ndims", "olmoe-stacked-ndims.gguf", stacked_ndims.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "blk.0.ffn_gate_exps.weight", blocks_len=3)

    # Section 5.3: the gpt-oss axis order, declared on an olmoe file, is rejected. This pins section
    # 2.5.3's axis-order decision as a contract rather than a comment, so the two frontends cannot
    # drift into agreement by accident. The role is F32 in this fixture only, because a Q4_K
    # `[64, 256, 8]` is `R1_TENSOR_SHAPE_UNALIGNED` at step 8 and would never reach step 10.
    stacked_transposed = OlmoeModel(
        types={"ffn_gate_exps": 0},
        mutate=lambda e: reshape_dims(e, "blk.0.ffn_gate_exps.weight", [64, 256, 8]))
    negative("olmoe-stacked-transposed", "olmoe-stacked-transposed.gguf", stacked_transposed.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "blk.0.ffn_gate_exps.weight", blocks_len=3)

    router_shape = OlmoeModel(
        mutate=lambda e: reshape_dims(e, "blk.0.ffn_gate_inp.weight", [256, 4]))
    negative("olmoe-router-shape", "olmoe-router-shape.gguf", router_shape.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "blk.0.ffn_gate_inp.weight", blocks_len=2)

    # The two appended roles are **required** members of every `AttentionBlock`: an absent one is
    # `R1_MISSING_TENSOR` and never a silently smaller block.
    qknorm_missing = OlmoeModel(drop_roles=("attn_q_norm",))
    negative("olmoe-qknorm-missing", "olmoe-qknorm-missing.gguf", qknorm_missing.bytes,
             "R1_MISSING_TENSOR", "blk.0.attn_q_norm.weight", blocks_len=1)

    qknorm_shape = OlmoeModel(
        mutate=lambda e: reshape_dims(e, "blk.0.attn_k_norm.weight", [128]))
    negative("olmoe-qknorm-shape", "olmoe-qknorm-shape.gguf", qknorm_shape.bytes,
             "R1_TENSOR_SHAPE_UNEXPECTED", "blk.0.attn_k_norm.weight", blocks_len=1)

    # No bias role is declared, so a file that carries one is `R1_UNASSIGNED_TENSOR` — the correct
    # fail-closed outcome for a tensor the plan cannot place — and never silently ignored.
    extra_bias = OlmoeModel(mutate=lambda e: e + [
        ("ffn_gate_exps_bias", 0, "blk.0.ffn_gate_exps.bias", [64, 8], 0)])
    negative("olmoe-extra-bias", "olmoe-extra-bias.gguf", extra_bias.bytes,
             "R1_UNASSIGNED_TENSOR", "blk.0.ffn_gate_exps.bias",
             unassigned=["blk.0.ffn_gate_exps.bias"])

    wrong_arch = OlmoeModel(arch="qwen2")
    negative("olmoe-wrong-arch", "olmoe-wrong-arch.gguf", wrong_arch.bytes,
             "R1_MISSING_KEY", "qwen2.block_count", blocks_len=0, arch="qwen2")

    size_sum = OlmoeModel(trailing=64)
    negative("olmoe-size-sum", "olmoe-size-sum.gguf", size_sum.bytes,
             "R1_SIZE_SUM_MISMATCH",
             "%d!=%d" % (size_sum.container.data_offset + size_sum.total_bytes,
                         len(size_sum.bytes)))

    # ---- precedence: the earlier section 2.6 row wins -------------------------------------------
    precedence_key = OlmoeModel(
        overrides={"olmoe.embedding_length": strv("256")},
        mutate=lambda e: reshape_dims(e, "blk.0.ffn_gate_exps.weight", [256, 64, 4]))
    negative("olmoe-precedence-key-shape", "olmoe-precedence-key-shape.gguf",
             precedence_key.bytes, "R1_KEY_TYPE_MISMATCH", "olmoe.embedding_length", blocks_len=0)

    # An out-of-bounds `expert_used_count` (step 7) and a zero vocabulary (step 9): the expert row.
    precedence_expert = OlmoeModel(
        p={"n_expert_used": OLMOE_BASE["n_expert"] + 1},
        mutate=lambda e: reshape_dims(e, "token_embd.weight", [256, 0]))
    negative("olmoe-precedence-expert-vocab", "olmoe-precedence-expert-vocab.gguf",
             precedence_expert.bytes, "R1_KEY_VALUE_IMPLAUSIBLE", "olmoe.expert_used_count",
             blocks_len=0)

    for case in cases:
        write(out_dir, case["file"], case.pop("bytes"))
    return cases


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
        # An absent `general.architecture` is `null` in the document and `-` in the summary block.
        "summary_architecture": "-",
    })

    # ---- positive: architecture presence and summary-line safety ------------------------------
    # A present-but-empty `general.architecture` is not an absent one: the document carries `""`
    # and the summary prints an empty line, leaving `-` to mean absent/non-STRING/non-UTF-8.
    architecture_empty = Container(
        [Kv("general.architecture", strv(""))], [Tensor("t.e", [4], 0, 0)],
    )
    cases.append({
        "name": "architecture-present-empty",
        "file": "architecture-empty.gguf",
        "bytes": architecture_empty.bytes,
        "exit": 0,
        "top": architecture_empty.top_expect("@PATH@"),
        "metadata": architecture_empty.metadata_expect(),
        "summary_architecture": "",
    })

    # A container-controlled architecture carrying control bytes must not inject lines into the
    # positionally read summary block.
    architecture_newline = Container(
        [Kv("general.architecture", strv("line1\nstatus:\tERROR\x7fline2"))],
        [Tensor("t.n", [4], 0, 0)],
    )
    cases.append({
        "name": "architecture-control-bytes",
        "file": "architecture-newline.gguf",
        "bytes": architecture_newline.bytes,
        "exit": 0,
        "top": architecture_newline.top_expect("@PATH@"),
        "metadata": architecture_newline.metadata_expect(),
        "summary_architecture": "line1\\x0astatus:\\x09ERROR\\x7fline2",
    })

    # A non-STRING `general.architecture` is absent for the purposes of the top-level field.
    architecture_non_string = Container(
        [Kv("general.architecture", u32v(7))], [Tensor("t.x", [4], 0, 0)],
    )
    cases.append({
        "name": "architecture-non-string",
        "file": "architecture-non-string.gguf",
        "bytes": architecture_non_string.bytes,
        "exit": 0,
        "top": architecture_non_string.top_expect("@PATH@"),
        "summary_architecture": "-",
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
    # A magic that is not valid UTF-8 at all: `magic` cannot hold the bytes, so it stays `""` and
    # the remaining three header fields stay unset, exactly as for `GGUF_TOO_SMALL`.
    cases.append({
        "name": "error-bad-magic-invalid-utf8",
        "file": "bad-magic-invalid-utf8.gguf",
        "bytes": patched(full, 0, b"\xff\xfe\xfd\xfc"),
        "exit": 1,
        "error": {"code": "GGUF_BAD_MAGIC", "offset": 0},
        "top": {"header": {"magic": "", "version": -1, "tensor_count": -1,
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

    # A tensor offset that is representable, alignment-correct, and so large that `data_offset +
    # offset` wraps negative in two's complement. The containment test must be written so that it
    # cannot wrap; a `data_offset + offset > file_size` form reports `status: "ok"` and exit 0 here.
    OVERFLOW_OFFSET = 0x7FFFFFFFFFFFFFE0
    assert OVERFLOW_OFFSET % DEFAULT_ALIGNMENT == 0
    assert OVERFLOW_OFFSET >> 63 == 0
    overflow_one = Container(
        [Kv("general.architecture", strv("overflowarch"))],
        [Tensor("t.overflow", [4], 0, OVERFLOW_OFFSET)],
        data_len=32,
    )
    assert (overflow_one.data_offset + OVERFLOW_OFFSET) - (1 << 64) < 0
    cases.append({
        "name": "error-tensor-offset-overflow",
        "file": "tensor-offset-overflow.gguf",
        "bytes": overflow_one.bytes,
        "exit": 1,
        "error": {"code": "GGUF_TENSOR_OUT_OF_RANGE",
                  "offset": overflow_one.tensor_offsets[0]["offset"]},
        "tensors_count": 1,
        # An absolute offset that is not representable as `i64` renders `-1`, never a wrapped value.
        "tensor_absolute_offsets": [-1],
    })
    # The same defect at index 1, so the loop cannot pass by only checking the first entry.
    overflow_second = Container(
        [Kv("general.architecture", strv("overflowarch2"))],
        [Tensor("t.zero", [4], 0, 0), Tensor("t.overflow", [4], 0, OVERFLOW_OFFSET)],
        data_len=32,
    )
    cases.append({
        "name": "error-tensor-offset-overflow-second-entry",
        "file": "tensor-offset-overflow-second.gguf",
        "bytes": overflow_second.bytes,
        "exit": 1,
        "error": {"code": "GGUF_TENSOR_OUT_OF_RANGE",
                  "offset": overflow_second.tensor_offsets[1]["offset"]},
        "tensors_count": 2,
        "tensor_absolute_offsets": [overflow_second.data_offset, -1],
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
        # The R1 corpus is a separate list so `run-gguf-smoke` keeps driving exactly the R0 cases
        # while `run-model-ir-smoke` drives all four.
        "model_ir_cases": qwen_build(out_dir),
        "model_ir_gptoss_cases": gptoss_build(out_dir),
        "model_ir_olmoe_cases": olmoe_build(out_dir),
    }


def main(argv):
    # One positional operand and nothing else. An option-shaped argument — `--help` above all — is
    # rejected rather than silently taken as a directory name to create.
    if len(argv) != 2 or argv[1].startswith("-"):
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
