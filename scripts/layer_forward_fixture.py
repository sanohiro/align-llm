#!/usr/bin/env python3
"""R5A-DENSE-LAYER-FORWARD synthetic corpus.

`docs/specs/r5a-dense-layer-forward.md` section 5.1. It writes, into one directory and with no
model, no network, and no ggml:

  * a **tiny-geometry alignpack v1 container** whose thirteen members are all F32, so the whole
    layer is hand-checkable and the pack is a few kilobytes;
  * a matching **`R1_MODEL_IR` v1 geometry document**, in the exact shape `main --model-ir` emits;
  * a **synthetic `llama-eval-callback` transcript** in that instrument's own line grammar, carrying
    the twenty oracle nodes at the tiny geometry with values computed here, independently of the
    Align implementation — which is what makes steps 28 and 29, the entire oracle, reachable
    hosted;
  * one mutation per reader, geometry, and oracle fixture of section 4.6.

The reference implementation below is deliberately plain Python: no NumPy, so the corpus builds on
any host that can run this repository's other generators. It computes in double precision and the
implementation under test computes in single, which is two orders of magnitude inside section 3.6's
`1.0e-4` element tolerance for a geometry whose activations are order 1.

Run it directly:

    python3 scripts/layer_forward_fixture.py OUTDIR
"""

import json
import math
import os
import struct
import sys

MAGIC = b"ALGP"
FORMAT_VERSION = 1
DOCUMENT_SCHEMA_VERSION = 1
HEADER_BYTES = 128
BLOCK_RECORD_BYTES = 64
MEMBER_RECORD_BYTES = 96
SOURCE_RECORD_BYTES = 128
REGION_ALIGN = 8
DEFERRED_U32 = 0xFFFFFFFF

BLOCK_ALIGN = 4096
MEMBER_ALIGN = 64

KIND_WEIGHT = 0
KIND_ATTENTION = 1
KIND_MLP = 2

TYPE_F32 = 0

# The tiny geometry of section 5.1. `n_embd = n_head * head_dim` and `n_head % n_head_kv == 0`, so
# it is a legal Qwen2 shape; every extent is small enough that a reader can check a value by hand.
GEOMETRY = {
    "n_layer": 2,
    "n_embd": 8,
    "n_head": 2,
    "n_head_kv": 1,
    "head_dim": 4,
    "n_ff": 16,
    "n_vocab": 32,
    "n_expert": 0,
    "context_length": 128,
    "rms_eps": 1e-05,
    "rope_freq_base": 10000.0,
    "rope_dim_count": 4,
    "rope_type": 2,
}

TOKENS = [3, 17, 5]

# `role_id`s from `r4-alignpack-layer-major.md` section 2.4.4's frozen list, in the slot order
# `src/layer_qwen2.align` refers to them by.
ROLES = [
    ("token_embd", 12, KIND_WEIGHT),
    ("attn_norm", 0, KIND_ATTENTION),
    ("attn_q", 1, KIND_ATTENTION),
    ("attn_q_bias", 2, KIND_ATTENTION),
    ("attn_k", 3, KIND_ATTENTION),
    ("attn_k_bias", 4, KIND_ATTENTION),
    ("attn_v", 5, KIND_ATTENTION),
    ("attn_v_bias", 6, KIND_ATTENTION),
    ("attn_output", 7, KIND_ATTENTION),
    ("ffn_norm", 8, KIND_MLP),
    ("ffn_gate", 9, KIND_MLP),
    ("ffn_up", 10, KIND_MLP),
    ("ffn_down", 11, KIND_MLP),
]


def align_up(value, alignment):
    if alignment <= 1:
        return value
    remainder = value % alignment
    return value if remainder == 0 else value + (alignment - remainder)


def f32(value):
    """`value` rounded to the nearest IEEE-754 single, as a Python float."""
    return struct.unpack("<f", struct.pack("<f", value))[0]


def member_dims(role, g):
    q = g["n_head"] * g["head_dim"]
    kv = g["n_head_kv"] * g["head_dim"]
    return {
        "token_embd": (g["n_embd"], g["n_vocab"]),
        "attn_norm": (g["n_embd"], 1),
        "attn_q": (g["n_embd"], q),
        "attn_q_bias": (q, 1),
        "attn_k": (g["n_embd"], kv),
        "attn_k_bias": (kv, 1),
        "attn_v": (g["n_embd"], kv),
        "attn_v_bias": (kv, 1),
        "attn_output": (g["n_embd"], g["n_embd"]),
        "ffn_norm": (g["n_embd"], 1),
        "ffn_gate": (g["n_embd"], g["n_ff"]),
        "ffn_up": (g["n_embd"], g["n_ff"]),
        "ffn_down": (g["n_ff"], g["n_embd"]),
    }[role]


def weight_values(role, count):
    """Deterministic, small, and distinct per role and per position.

    A constant fill would let a byte-identity check pass over a member placed at the wrong offset,
    and a large fill would put the activations outside the range a `%12.4f` transcript resolves.
    """
    seed = sum(ord(ch) for ch in role)
    out = []
    for i in range(count):
        state = (seed * 1103515245 + i * 12345 + 7) & 0x7FFFFFFF
        out.append(f32(((state % 2000) - 1000) / 2000.0))
    return out


# ---------------------------------------------------------------------------------------------
# The reference layer
# ---------------------------------------------------------------------------------------------


class Tensor:
    """A dense row-major f32 tensor in ggml's own index order: `ne[0]` is the fastest axis."""

    def __init__(self, ne, data=None):
        self.ne = list(ne) + [1] * (4 - len(ne))
        n = self.count()
        self.data = list(data) if data is not None else [0.0] * n
        assert len(self.data) == n, (role_of(self), len(self.data), n)

    def count(self):
        return self.ne[0] * self.ne[1] * self.ne[2] * self.ne[3]

    def at(self, i0, i1=0, i2=0, i3=0):
        return self.data[i0 + self.ne[0] * (i1 + self.ne[1] * (i2 + self.ne[2] * i3))]


def role_of(_):
    return "tensor"


def get_rows(a, ids):
    ne0 = a.ne[0]
    out = []
    for row in ids:
        out.extend(a.data[row * ne0:(row + 1) * ne0])
    return Tensor([ne0, len(ids)], out)


def rms_norm(a, eps):
    ne0 = a.ne[0]
    rows = a.count() // ne0
    out = []
    for r in range(rows):
        row = a.data[r * ne0:(r + 1) * ne0]
        mean = f32(sum(v * v for v in row) / ne0)
        scale = f32(1.0 / math.sqrt(mean + eps))
        out.extend(f32(v * scale) for v in row)
    return Tensor(a.ne, out)


def broadcast(a, b, op):
    out = [0.0] * a.count()
    for i3 in range(a.ne[3]):
        for i2 in range(a.ne[2]):
            for i1 in range(a.ne[1]):
                for i0 in range(a.ne[0]):
                    at = i0 + a.ne[0] * (i1 + a.ne[1] * (i2 + a.ne[2] * i3))
                    bt = ((i0 % b.ne[0]) + b.ne[0] * ((i1 % b.ne[1])
                          + b.ne[1] * ((i2 % b.ne[2]) + b.ne[2] * (i3 % b.ne[3]))))
                    out[at] = f32(op(a.data[at], b.data[bt]))
    return Tensor(a.ne, out)


def mul_mat(a, b):
    k, m = a.ne[0], a.ne[1]
    ne = [m, b.ne[1], b.ne[2], b.ne[3]]
    r2 = ne[2] // a.ne[2]
    r3 = ne[3] // a.ne[3]
    out = [0.0] * (ne[0] * ne[1] * ne[2] * ne[3])
    for i3 in range(ne[3]):
        for i2 in range(ne[2]):
            for i1 in range(ne[1]):
                base_b = k * (i1 + b.ne[1] * (i2 + b.ne[2] * i3))
                for i0 in range(m):
                    base_a = k * (i0 + m * ((i2 // r2) + a.ne[2] * (i3 // r3)))
                    total = 0.0
                    for at in range(k):
                        total = f32(total + f32(a.data[base_a + at] * b.data[base_b + at]))
                    out[i0 + m * (i1 + ne[1] * (i2 + ne[2] * i3))] = total
    return Tensor(ne, out)


def reshape(a, ne):
    return Tensor(ne, list(a.data))


def permute(a, axes):
    ne = [0, 0, 0, 0]
    for i in range(4):
        ne[axes[i]] = a.ne[i]
    out = [0.0] * a.count()
    for i3 in range(a.ne[3]):
        for i2 in range(a.ne[2]):
            for i1 in range(a.ne[1]):
                for i0 in range(a.ne[0]):
                    source = [i0, i1, i2, i3]
                    target = [0, 0, 0, 0]
                    for axis in range(4):
                        target[axes[axis]] = source[axis]
                    out[target[0] + ne[0] * (target[1] + ne[1] * (target[2] + ne[2] * target[3]))] \
                        = a.data[i0 + a.ne[0] * (i1 + a.ne[1] * (i2 + a.ne[2] * i3))]
    return Tensor(ne, out)


def cont(a, ne):
    return Tensor(ne, list(a.data))


def rope_neox(a, positions, n_dims, freq_base):
    out = list(a.data)
    theta_scale = f32(math.pow(freq_base, -2.0 / n_dims))
    for i2 in range(a.ne[2]):
        theta_base = float(positions[i2])
        for i1 in range(a.ne[1]):
            base = a.ne[0] * (i1 + a.ne[1] * i2)
            theta = theta_base
            for i0 in range(0, n_dims, 2):
                cos_theta = f32(math.cos(theta))
                sin_theta = f32(math.sin(theta))
                x0 = a.data[base + i0 // 2]
                x1 = a.data[base + i0 // 2 + n_dims // 2]
                out[base + i0 // 2] = f32(x0 * cos_theta - x1 * sin_theta)
                out[base + i0 // 2 + n_dims // 2] = f32(x0 * sin_theta + x1 * cos_theta)
                theta = f32(theta * theta_scale)
    return Tensor(a.ne, out)


def soft_max_ext(a, mask, scale):
    out = [0.0] * a.count()
    for i3 in range(a.ne[3]):
        for i2 in range(a.ne[2]):
            for i1 in range(a.ne[1]):
                base = a.ne[0] * (i1 + a.ne[1] * (i2 + a.ne[2] * i3))
                row = []
                for i0 in range(a.ne[0]):
                    row.append(f32(f32(a.data[base + i0] * scale)
                                   + mask.data[mask.ne[0] * (i1 % mask.ne[1]) + i0]))
                highest = max(row)
                total = 0.0
                for i0 in range(a.ne[0]):
                    value = f32(math.exp(row[i0] - highest)) if row[i0] != float("-inf") else 0.0
                    out[base + i0] = value
                    total = f32(total + value)
                for i0 in range(a.ne[0]):
                    out[base + i0] = f32(out[base + i0] / total)
    return Tensor(a.ne, out)


def swiglu_split(a, b):
    return Tensor(a.ne, [f32(f32(x / (1.0 + f32(math.exp(-x)))) * y)
                         for x, y in zip(a.data, b.data)])


def forward(weights, g, tokens):
    """The thirty-two-node graph of section 2.2, node for node, in the same order."""
    t = len(tokens)
    head_dim, n_head, n_head_kv = g["head_dim"], g["n_head"], g["n_head_kv"]
    n_embd, n_ff = g["n_embd"], g["n_ff"]
    eps, freq_base = g["rms_eps"], g["rope_freq_base"]

    mask = Tensor([t, t], [0.0 if c <= r else float("-inf")
                           for r in range(t) for c in range(t)])
    positions = list(range(t))

    embd = get_rows(weights["token_embd"], tokens)
    norm = rms_norm(embd, eps)
    attn_norm = broadcast(norm, weights["attn_norm"], lambda x, y: x * y)
    q = broadcast(mul_mat(weights["attn_q"], attn_norm), weights["attn_q_bias"],
                  lambda x, y: x + y)
    k = broadcast(mul_mat(weights["attn_k"], attn_norm), weights["attn_k_bias"],
                  lambda x, y: x + y)
    v = broadcast(mul_mat(weights["attn_v"], attn_norm), weights["attn_v_bias"],
                  lambda x, y: x + y)
    q3 = reshape(q, [head_dim, n_head, t])
    k3 = reshape(k, [head_dim, n_head_kv, t])
    v3 = reshape(v, [head_dim, n_head_kv, t])
    qr = rope_neox(q3, positions, g["rope_dim_count"], freq_base)
    kr = rope_neox(k3, positions, g["rope_dim_count"], freq_base)
    qp = permute(qr, [0, 2, 1, 3])
    kp = permute(kr, [0, 2, 1, 3])
    kq = mul_mat(kp, qp)
    scale = f32(1.0 / math.sqrt(head_dim))
    kqs = soft_max_ext(kq, mask, scale)
    vp = permute(v3, [1, 2, 0, 3])
    vt = cont(vp, [t, head_dim, n_head_kv])
    kqv = mul_mat(vt, kqs)
    kqvm = permute(kqv, [0, 2, 1, 3])
    kqv_out = cont(kqvm, [n_embd, t, 1])
    attn_out = mul_mat(weights["attn_output"], kqv_out)
    ffn_inp = broadcast(attn_out, embd, lambda x, y: x + y)
    ffn_norm = broadcast(rms_norm(ffn_inp, eps), weights["ffn_norm"], lambda x, y: x * y)
    ffn_gate = mul_mat(weights["ffn_gate"], ffn_norm)
    ffn_up = mul_mat(weights["ffn_up"], ffn_norm)
    ffn_swiglu = swiglu_split(ffn_gate, ffn_up)
    ffn_out = mul_mat(weights["ffn_down"], ffn_swiglu)
    l_out = broadcast(ffn_out, ffn_inp, lambda x, y: x + y)
    _ = n_ff
    return [
        ("embd", "embd", "GET_ROWS", embd),
        ("norm", "norm-0", "RMS_NORM", norm),
        ("attn_norm", "attn_norm-0", "MUL", attn_norm),
        ("q_bias", "Qcur-0", "ADD", q),
        ("k_bias", "Kcur-0", "ADD", k),
        ("v_bias", "Vcur-0", "ADD", v),
        ("q_rope", "Qcur-0", "ROPE", qr),
        ("k_rope", "Kcur-0", "ROPE", kr),
        ("kq", "kq-0", "MUL_MAT", kq),
        ("kq_soft_max", "kq_soft_max-0", "SOFT_MAX", kqs),
        ("kqv", "kqv-0", "MUL_MAT", kqv),
        ("kqv_out", "kqv_out-0", "CONT", kqv_out),
        ("attn_out", "node_31", "MUL_MAT", attn_out),
        ("ffn_inp", "ffn_inp-0", "ADD", ffn_inp),
        ("ffn_norm", "ffn_norm-0", "MUL", ffn_norm),
        ("ffn_gate", "ffn_gate-0", "MUL_MAT", ffn_gate),
        ("ffn_up", "ffn_up-0", "MUL_MAT", ffn_up),
        ("ffn_swiglu", "ffn_swiglu-0", "SWIGLU", ffn_swiglu),
        ("ffn_out", "ffn_out-0", "MUL_MAT", ffn_out),
        ("l_out", "l_out-0", "ADD", l_out),
    ]


# ---------------------------------------------------------------------------------------------
# The transcript
# ---------------------------------------------------------------------------------------------

PRINTED = 6
HALF = 3


def printed_positions(extent):
    if extent <= PRINTED:
        return [(i, False) for i in range(extent)]
    rows = [(i, False) for i in range(HALF)]
    rows.append((-1, True))
    rows.extend((extent - HALF + i, False) for i in range(HALF))
    return rows


def transcript_block(name, op, source, tensor):
    """One `common_debug_cb_eval:` record in build 10566's exact grammar.

    The trailing space on the `..., ` truncation markers is the instrument's and is significant:
    `.gitattributes` exempts the checked-in excerpt from whitespace checks for this reason.
    """
    dims = "{%d, %d, %d, %d}" % tuple(tensor.ne)
    lines = ["common_debug_cb_eval: %24s = (f32) %10s(%s%s, }) = %s"
             % (name, op, source, dims, dims)]
    lines.append("    [")
    for i3, mark3 in printed_positions(tensor.ne[3]):
        if mark3:
            lines.append("    ..., ")
            continue
        lines.append("        [")
        for i2, mark2 in printed_positions(tensor.ne[2]):
            if mark2:
                lines.append("        ..., ")
                continue
            for i1, mark1 in printed_positions(tensor.ne[1]):
                if mark1:
                    lines.append("            ..., ")
                    continue
                pieces = []
                for i0, mark0 in printed_positions(tensor.ne[0]):
                    pieces.append("   ..." if mark0 else "%12.4f" % tensor.at(i0, i1, i2, i3))
                lines.append("            [" + ", ".join(pieces) + "  ],")
            lines.append("        ],")
    lines.append("    ]")
    total = 0.0
    for value in tensor.data:
        total = f32(total + value)
    lines.append("    sum = %f" % total)
    return lines


# The source operand each record prints. Only `node_31` is *matched* by it — section 2.2 fact 3 —
# but writing the real names keeps the synthetic transcript readable beside the checked-in excerpt.
SOURCE_NAMES = {
    "embd": "token_embd.weight",
    "norm-0": "embd",
    "attn_norm-0": "norm-0",
    "kq_soft_max-0": "kq-0",
    "ffn_swiglu-0": "ffn_gate-0",
    "l_out-0": "ffn_out-0",
}


def build_transcript(nodes, layer=0):
    lines = [
        "build: 10566 (bb4caa754) with cc for x86_64-unknown-linux-gnu",
        "number of input tokens = %d" % len(TOKENS),
    ]
    for _, name, op, tensor in nodes:
        source = SOURCE_NAMES.get(name, "src0")
        if name == "node_31":
            source = "blk.%d.attn_output.weight" % layer
        lines.extend(transcript_block(name, op, source, tensor))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------
# The container
# ---------------------------------------------------------------------------------------------


class Member:
    def __init__(self, name, role, role_id, block_kind, dim0, dim1, values):
        self.name = name
        self.role = role
        self.role_id = role_id
        self.block_kind = block_kind
        self.type_id = TYPE_F32
        self.dim0 = dim0
        self.dim1 = dim1
        self.values = values
        self.nbytes = dim0 * dim1 * 4
        self.payload = struct.pack("<%df" % len(values), *values)
        self.source_offset = 0
        self.pack_offset = 0
        self.name_start = 0


class Block:
    def __init__(self, kind, layer, members):
        self.kind = kind
        self.layer = layer
        self.expert = -1
        self.members = members
        self.member_start = 0
        self.pack_offset = 0
        self.pack_bytes = 0
        self.payload_bytes = 0


def layer_members(g, layer):
    members = []
    for role, role_id, kind in ROLES:
        dim0, dim1 = member_dims(role, g)
        name = ("token_embd.weight" if role == "token_embd"
                else "blk.%d.%s.weight" % (layer, role))
        members.append(Member(name, role, role_id, kind, dim0, dim1,
                              weight_values(role, dim0 * dim1)))
    return members


def blocks_for(members, layer):
    return [
        Block(KIND_WEIGHT, -1, [m for m in members if m.block_kind == KIND_WEIGHT]),
        Block(KIND_ATTENTION, layer, [m for m in members if m.block_kind == KIND_ATTENTION]),
        Block(KIND_MLP, layer, [m for m in members if m.block_kind == KIND_MLP]),
    ]


def build(blocks, block_align=BLOCK_ALIGN, member_align=MEMBER_ALIGN):
    name_stream = bytearray()
    members = []
    for block in blocks:
        block.member_start = len(members)
        for member in block.members:
            member.name_start = len(name_stream)
            name_stream.extend(member.name.encode("utf-8"))
            members.append(member)

    name_stream_offset = HEADER_BYTES
    name_stream_bytes = len(name_stream)
    block_table_offset = align_up(name_stream_offset + name_stream_bytes, REGION_ALIGN)
    member_table_offset = align_up(
        block_table_offset + len(blocks) * BLOCK_RECORD_BYTES, REGION_ALIGN)
    source_record_offset = align_up(
        member_table_offset + len(members) * MEMBER_RECORD_BYTES, REGION_ALIGN)
    payload_offset = align_up(source_record_offset + SOURCE_RECORD_BYTES, block_align)

    cursor = payload_offset
    source_cursor = 4096
    for block in blocks:
        block.pack_offset = align_up(cursor, block_align)
        cursor = block.pack_offset
        block.payload_bytes = 0
        for member in block.members:
            cursor = align_up(cursor, member_align)
            member.pack_offset = cursor
            member.source_offset = source_cursor
            source_cursor = align_up(source_cursor + member.nbytes, 32)
            cursor = member.pack_offset + member.nbytes
            block.payload_bytes += member.nbytes
        block.pack_bytes = cursor - block.pack_offset
    total_bytes = cursor

    raw = bytearray(total_bytes)
    raw[0:4] = MAGIC
    struct.pack_into("<IIIII", raw, 4, FORMAT_VERSION, HEADER_BYTES, block_align, member_align, 0)
    struct.pack_into("<QQQQQQQQQQ", raw, 24, total_bytes, name_stream_offset, name_stream_bytes,
                     block_table_offset, len(blocks), member_table_offset, len(members),
                     source_record_offset, payload_offset, total_bytes - payload_offset)
    struct.pack_into("<IIII", raw, 104, BLOCK_RECORD_BYTES, MEMBER_RECORD_BYTES,
                     SOURCE_RECORD_BYTES, DOCUMENT_SCHEMA_VERSION)
    struct.pack_into("<Q", raw, 120, 0)
    raw[name_stream_offset:name_stream_offset + name_stream_bytes] = name_stream

    for index, block in enumerate(blocks):
        base = block_table_offset + index * BLOCK_RECORD_BYTES
        struct.pack_into("<IiiI", raw, base, block.kind, block.layer, block.expert,
                         len(block.members))
        struct.pack_into("<QQQQ", raw, base + 16, block.member_start, block.pack_offset,
                         block.pack_bytes, block.payload_bytes)
        struct.pack_into("<IIQ", raw, base + 48, DEFERRED_U32, DEFERRED_U32, 0)

    for index, member in enumerate(members):
        base = member_table_offset + index * MEMBER_RECORD_BYTES
        struct.pack_into("<QII", raw, base, member.name_start,
                         len(member.name.encode("utf-8")), member.role_id)
        struct.pack_into("<QQQ", raw, base + 16, member.source_offset, member.nbytes,
                         member.pack_offset)
        struct.pack_into("<II", raw, base + 40, member.type_id, 2)
        struct.pack_into("<QQQQ", raw, base + 48, member.dim0, member.dim1, 1, 1)
        struct.pack_into("<iiQ", raw, base + 80, -1, -1, 0)
        raw[member.pack_offset:member.pack_offset + member.nbytes] = member.payload

    layout = {
        "block_table_offset": block_table_offset,
        "member_table_offset": member_table_offset,
        "members": members,
        "blocks": blocks,
        "total_bytes": total_bytes,
    }
    return bytes(raw), layout


def member_field(layout, index, offset):
    return layout["member_table_offset"] + index * MEMBER_RECORD_BYTES + offset


def block_field(layout, index, offset):
    return layout["block_table_offset"] + index * BLOCK_RECORD_BYTES + offset


def patch(raw, offset, fmt, *values):
    edited = bytearray(raw)
    struct.pack_into(fmt, edited, offset, *values)
    return bytes(edited)


def source_image(layout, corrupt=None):
    members = layout["members"]
    size = max(m.source_offset + m.nbytes for m in members)
    raw = bytearray(size)
    for member in members:
        raw[member.source_offset:member.source_offset + member.nbytes] = member.payload
    if corrupt is not None:
        member = members[corrupt]
        at = member.source_offset + member.nbytes // 2
        raw[at] = raw[at] ^ 0xFF
    return bytes(raw)


# ---------------------------------------------------------------------------------------------
# The geometry document
# ---------------------------------------------------------------------------------------------


def bits32(value):
    return "%08x" % struct.unpack("<I", struct.pack("<f", value))[0]


def geometry_document(g):
    """The `model` object exactly as `main --model-ir` emits it, inside an `R1_MODEL_IR` v1."""
    return {
        "schema_version": 2,
        "kind": "R1_MODEL_IR",
        "path": "synthetic-qwen2.gguf",
        "status": "ok",
        "error_code": "",
        "error_detail": "",
        "model": {
            "arch": "qwen2",
            "n_layer": g["n_layer"],
            "n_embd": g["n_embd"],
            "n_head": g["n_head"],
            "n_head_kv": g["n_head_kv"],
            "head_dim": g["head_dim"],
            "n_ff": g["n_ff"],
            "n_vocab": g["n_vocab"],
            "n_expert": g["n_expert"],
            "context_length": g["context_length"],
            "rms_eps": g["rms_eps"],
            "rms_eps_bits": bits32(g["rms_eps"]),
            "rope": {
                "type": g["rope_type"],
                "type_name": "neox",
                "type_source": "architecture",
                "freq_base": g["rope_freq_base"],
                "freq_base_bits": bits32(g["rope_freq_base"]),
                "dim_count": g["rope_dim_count"],
                "dim_count_source": "head_dim",
                "scaling_type": None,
            },
        },
    }


GEOMETRY_FIELDS = [
    "arch", "n_layer", "n_embd", "n_head", "n_head_kv", "head_dim", "n_ff", "n_vocab",
    "n_expert", "context_length", "rms_eps_bits",
]
GEOMETRY_ROPE_FIELDS = ["type", "dim_count", "freq_base_bits", "scaling_type"]


def geometry_corpus(g):
    """The base document plus one mutation per consumed field and per precondition."""
    base = geometry_document(g)
    out = [("geometry", base)]
    for field in GEOMETRY_FIELDS:
        copy = json.loads(json.dumps(base))
        del copy["model"][field]
        out.append(("geometry-missing-" + field, copy))
    for field in GEOMETRY_ROPE_FIELDS:
        copy = json.loads(json.dumps(base))
        del copy["model"]["rope"][field]
        out.append(("geometry-missing-rope-" + field, copy))
    broken = json.loads(json.dumps(base))
    broken["kind"] = "R1_QWEN_MODEL_IR"
    out.append(("geometry-kind", broken))
    broken = json.loads(json.dumps(base))
    broken["schema_version"] = 1
    out.append(("geometry-version", broken))
    broken = json.loads(json.dumps(base))
    broken["model"]["arch"] = "llama"
    out.append(("geometry-arch", broken))
    broken = json.loads(json.dumps(base))
    broken["model"]["rope"]["type"] = 0
    out.append(("geometry-rope-type", broken))
    broken = json.loads(json.dumps(base))
    broken["model"]["rope"]["scaling_type"] = "yarn"
    out.append(("geometry-rope-scaled", broken))
    broken = json.loads(json.dumps(base))
    broken["model"]["n_embd"] = 9
    out.append(("geometry-inconsistent", broken))
    broken = json.loads(json.dumps(base))
    broken["model"]["n_head_kv"] = 3
    out.append(("geometry-head-kv", broken))
    broken = json.loads(json.dumps(base))
    broken["model"]["n_expert"] = 4
    out.append(("geometry-expert", broken))
    broken = json.loads(json.dumps(base))
    broken["model"]["rope"]["dim_count"] = 2
    out.append(("geometry-rope-dims", broken))
    return out


# ---------------------------------------------------------------------------------------------
# The corpus
# ---------------------------------------------------------------------------------------------


def write_corpus(directory):
    os.makedirs(directory, exist_ok=True)
    written = []

    def emit(name, payload):
        path = os.path.join(directory, name)
        mode = "wb" if isinstance(payload, bytes) else "w"
        with open(path, mode) as handle:
            handle.write(payload)
        written.append(path)
        return path

    g = GEOMETRY
    members = layer_members(g, 0)
    base, layout = build(blocks_for(members, 0))
    emit("pack.alignpack", base)

    # `block_align = 1` packs the member windows tight, so a member whose `nbytes` is not a multiple
    # of the linked library's `TENSOR_ALIGNMENT` lands off a boundary. `attn_k_bias` is 16 bytes at
    # this geometry, which is exactly that member.
    tight, _ = build(blocks_for(layer_members(g, 0), 0), block_align=1, member_align=1)
    emit("pack-tight.alignpack", tight)

    # A pack with no `MlpBlock` at all — the block is absent from the table rather than present and
    # empty, because a block record declaring zero members is a container defect the reader refuses
    # first and `R5_BLOCK_MISSING` is about a block that is simply not there.
    no_mlp_blocks = [b for b in blocks_for(layer_members(g, 0), 0) if b.kind != KIND_MLP]
    no_mlp, _ = build(no_mlp_blocks)
    emit("pack-no-mlp.alignpack", no_mlp)

    partial = [m for m in layer_members(g, 0) if m.role != "attn_q_bias"]
    no_bias, _ = build(blocks_for(partial, 0))
    emit("pack-no-bias.alignpack", no_bias)

    emit("pack-bad-shape.alignpack", patch(base, member_field(layout, 2, 56), "<Q", 9))
    emit("pack-bad-type.alignpack", patch(base, member_field(layout, 2, 40), "<I", 4))
    # `token_embd.nbytes` no longer divides by `n_vocab`.
    emit("pack-bad-stride.alignpack",
         patch(base, member_field(layout, 0, 24), "<Q", layout["members"][0].nbytes - 4))
    emit("pack-truncated.alignpack", base[:len(base) - 64])

    emit("source.bin", source_image(layout))
    emit("source-diverged.bin", source_image(layout, corrupt=5))
    emit("source-short.bin", b"\0")

    for name, document in geometry_corpus(g):
        emit(name + ".json", json.dumps(document, separators=(",", ":")) + "\n")

    nodes = forward({m.role: Tensor(list(member_dims(m.role, g)), m.values)
                     for m in members}, g, TOKENS)
    transcript = build_transcript(nodes)
    emit("transcript.txt", transcript)

    lines = transcript.split("\n")
    # `R5_ORACLE_MISSING`: the `l_out-0` record is deleted outright.
    start = next(i for i, line in enumerate(lines) if line.startswith("common_debug_cb_eval:")
                 and " l_out-0 " in line)
    emit("transcript-missing.txt", "\n".join(lines[:start]) + "\n")

    # `R5_ORACLE_SHAPE`: `l_out-0` declares one token fewer than the graph computed.
    reshaped = list(lines)
    reshaped[start] = reshaped[start].replace(
        "{%d, %d, 1, 1}" % (g["n_embd"], len(TOKENS)),
        "{%d, %d, 1, 1}" % (g["n_embd"], len(TOKENS) - 1))
    emit("transcript-shape.txt", "\n".join(reshaped) + "\n")

    # A tolerance breach: one printed element of `l_out-0` moved by 0.0003, which is three times
    # section 3.6's threshold, so `oracle.verdict` becomes `FAIL` while `status` stays `ok`.
    perturbed = list(lines)
    row = start + 3
    original = perturbed[row]
    first = original.index("[") + 1
    value = float(original[first:first + 12])
    perturbed[row] = original[:first] + ("%12.4f" % (value + 0.0003)) + original[first + 12:]
    emit("transcript-perturbed.txt", "\n".join(perturbed) + "\n")

    emit("transcript-garbage.txt", bytes(range(256)) * 8)

    return written


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: layer_forward_fixture.py OUTDIR\n")
        return 2
    for path in write_corpus(argv[1]):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
