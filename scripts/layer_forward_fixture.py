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
    def __init__(self, name, role, role_id, block_kind, dim0, dim1, values,
                 n_dims=2, dim2=1, dim3=1, slice_index=-1, slice_count=-1):
        self.name = name
        self.role = role
        self.role_id = role_id
        self.block_kind = block_kind
        self.type_id = TYPE_F32
        self.dim0 = dim0
        self.dim1 = dim1
        # R5D: a **claim** is one plane of a stacked tensor, so its record declares three dims whose
        # third is the sliced axis's own extent and whose `nbytes` is the plane's, not the stack's
        # (`docs/specs/moe-prereq-discharge.md` section 1.1). The defaults are the dense form and
        # reproduce every R5A and R5B fixture byte for byte.
        self.n_dims = n_dims
        self.dim2 = dim2
        self.dim3 = dim3
        self.slice_index = slice_index
        self.slice_count = slice_count
        self.values = values
        self.nbytes = dim0 * dim1 * 4
        self.payload = struct.pack("<%df" % len(values), *values)
        self.source_offset = 0
        self.pack_offset = 0
        self.name_start = 0


class Block:
    def __init__(self, kind, layer, members, expert=-1):
        self.kind = kind
        self.layer = layer
        self.expert = expert
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
        struct.pack_into("<II", raw, base + 40, member.type_id, member.n_dims)
        struct.pack_into("<QQQQ", raw, base + 48, member.dim0, member.dim1,
                         member.dim2, member.dim3)
        struct.pack_into("<iiQ", raw, base + 80, member.slice_index, member.slice_count, 0)
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
    # The bit patterns that are legal eight-hex-digit strings and illegal floats. `rms_eps_bits`
    # reaches `ggml_rms_norm`, which asserts `eps >= 0.0f` inside ggml, and `GGML_ASSERT` is
    # `abort()`: without step 7's refusal each of these takes the process down at step 24 with no
    # document and no error code. `freq_base` must additionally be positive.
    for name, bits in (("nan", "7fc00000"), ("neg-inf", "ff800000"),
                       ("negative", "bf800000"), ("all-ones", "ffffffff")):
        broken = json.loads(json.dumps(base))
        broken["model"]["rms_eps_bits"] = bits
        out.append(("geometry-eps-" + name, broken))
    for name, bits in (("nan", "7fc00000"), ("inf", "7f800000"),
                       ("negative", "bf800000"), ("zero", "00000000")):
        broken = json.loads(json.dumps(base))
        broken["model"]["rope"]["freq_base_bits"] = bits
        out.append(("geometry-rope-base-" + name, broken))
    return out


# ---------------------------------------------------------------------------------------------
# The corpus
# ---------------------------------------------------------------------------------------------


def write_corpus(directory, model=False, moe=False):
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

    # `R5_ORACLE_MISSING` by shortfall, not by absence: every record's header survives, so every
    # oracle node matches by name and by declared shape and then carries no element at all. Before
    # the review repair this was a `PASS` over zero compared elements.
    headers = [line for line in lines
               if line.startswith("common_debug_cb_eval:") or line.startswith("build: ")
               or line.startswith("number of input tokens")]
    emit("transcript-headers.txt", "\n".join(headers) + "\n")

    # The same shortfall for exactly one node: `l_out-0`'s value block is deleted and its header
    # and `sum` line are kept, which is what a truncated capture of one large tensor looks like.
    end = next(i for i, line in enumerate(lines[start:], start)
               if line.startswith("    sum = "))
    emit("transcript-novalues.txt",
         "\n".join(lines[:start + 1] + lines[end:]) + "\n")

    emit("transcript-garbage.txt", bytes(range(256)) * 8)

    if model:
        write_model_corpus(directory, emit)

    if moe:
        write_moe_corpus(directory, emit)

    return written


def main(argv):
    model = "--model" in argv[1:]
    moe = "--moe" in argv[1:]
    rest = [a for a in argv[1:] if a not in ("--model", "--moe")]
    # One positional operand and nothing else. An option-shaped argument — `--help` above all — is
    # rejected rather than silently taken as a directory name to create, which is the guard
    # `scripts/gguf_fixture.py` already carries.
    if len(rest) != 1 or rest[0].startswith("-"):
        sys.stderr.write("usage: layer_forward_fixture.py OUTDIR [--model] [--moe]\n")
        return 2
    for path in write_corpus(rest[0], model=model, moe=moe):
        print(path)
    return 0



# =============================================================================================
# R5B-MODEL-PREFILL-FORWARD (`docs/specs/r5b-model-prefill-forward.md` section 5.1)
#
# The same generator, extended to a whole **two-layer, thirty-two-token-vocabulary model**: six
# blocks, twenty-seven members, all F32, and a pure-Python forward pass over the entire prefill —
# the embedding gather, both layers, the narrowing inside the last one, and the head — which is what
# makes the logits oracle stub-reachable at all. A second implementation computing the same model is
# the only way section 4.4's `IDENTICAL` cell can be checked on a host with no model.
#
# The geometry is chosen so `n_vocab` (32) differs from `n_ff` (16) and from `n_head * head_dim`
# (8): a fixture whose dimensions collide cannot catch a transposed head.
# =============================================================================================

MODEL_TOKENS = [3, 17, 5]
# `r5b-model-prefill-forward.md` section 6, correction C23. The one token list whose
# runtime-width logit 0 is -3.69e-05 — exactly zero ten-thousandths — which is the only primary
# value that makes `primary - reference` wrap to `i64`'s minimum against a saturated reference.
# Swept out of the generator's own second implementation, which agrees with the engine to zero
# ten-thousandths.
MODEL_ABORT_TOKENS = [1, 25, 5]
MODEL_KV_WIDTH = 8

ROLE_OUTPUT_NORM = 13
ROLE_OUTPUT = 14

LAYER_ROLES = [
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


def pad_tensor(a, p0, p1, p2, p3):
    """`ggml_pad`: zeroes appended at the **end** of each axis, source at the leading positions."""
    ne = [a.ne[0] + p0, a.ne[1] + p1, a.ne[2] + p2, a.ne[3] + p3]
    out = [0.0] * (ne[0] * ne[1] * ne[2] * ne[3])
    for i3 in range(a.ne[3]):
        for i2 in range(a.ne[2]):
            for i1 in range(a.ne[1]):
                for i0 in range(a.ne[0]):
                    out[i0 + ne[0] * (i1 + ne[1] * (i2 + ne[2] * i3))] = \
                        a.data[i0 + a.ne[0] * (i1 + a.ne[1] * (i2 + a.ne[2] * i3))]
    return Tensor(ne, out)


def model_dims(role, g):
    q = g["n_head"] * g["head_dim"]
    kv = g["n_head_kv"] * g["head_dim"]
    return {
        "token_embd": (g["n_embd"], g["n_vocab"]),
        "output_norm": (g["n_embd"], 1),
        "output": (g["n_embd"], g["n_vocab"]),
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


def model_tensor(role, layer, g):
    dim0, dim1 = model_dims(role, g)
    seed = role if layer < 0 else "%s@%d" % (role, layer)
    return Tensor([dim0, dim1], weight_values(seed, dim0 * dim1))


def concat_tensor(a, b, dim):
    """`ggml_concat`: `b`'s coordinates shifted by `a->ne[dim]`, every other axis identical."""
    assert all(a.ne[i] == b.ne[i] for i in range(4) if i != dim), (a.ne, b.ne, dim)
    ne = list(a.ne)
    ne[dim] = a.ne[dim] + b.ne[dim]
    out = Tensor(ne)
    for i3 in range(a.ne[3]):
        for i2 in range(a.ne[2]):
            for i1 in range(a.ne[1]):
                for i0 in range(a.ne[0]):
                    out.data[i0 + ne[0] * (i1 + ne[1] * (i2 + ne[2] * i3))] = \
                        a.data[i0 + a.ne[0] * (i1 + a.ne[1] * (i2 + a.ne[2] * i3))]
    for i3 in range(b.ne[3]):
        for i2 in range(b.ne[2]):
            for i1 in range(b.ne[1]):
                for i0 in range(b.ne[0]):
                    at = [i0, i1, i2, i3]
                    at[dim] += a.ne[dim]
                    out.data[at[0] + ne[0] * (at[1] + ne[1] * (at[2] + ne[2] * at[3]))] = \
                        b.data[i0 + b.ne[0] * (i1 + b.ne[1] * (i2 + b.ne[2] * i3))]
    return out


def plane_to_past_k(plane, head_dim, n_head_kv, n_past):
    """`{head_dim, n_head_kv, column}` to the `{head_dim, n_past, n_head_kv}` the decode graph wants."""
    out = Tensor([head_dim, n_past, n_head_kv])
    for h in range(n_head_kv):
        for c in range(n_past):
            for d in range(head_dim):
                out.data[d + head_dim * (c + n_past * h)] = \
                    plane.data[d + head_dim * (h + n_head_kv * c)]
    return out


def plane_to_past_v(plane, head_dim, n_head_kv, n_past):
    """The same plane as the `{n_past, head_dim, n_head_kv}` the transposed V path wants."""
    out = Tensor([n_past, head_dim, n_head_kv])
    for h in range(n_head_kv):
        for d in range(head_dim):
            for c in range(n_past):
                out.data[c + n_past * (d + head_dim * h)] = \
                    plane.data[d + head_dim * (h + n_head_kv * c)]
    return out


def model_layer(cur, weights, g, tokens, width, mask, last, records, layer, planes=None):
    """One layer of section 3.6's thirty-six-row table, in the order the walk issues it."""
    t = len(tokens)
    head_dim, n_head, n_head_kv = g["head_dim"], g["n_head"], g["n_head_kv"]
    n_embd = g["n_embd"]
    eps, freq_base = g["rms_eps"], g["rope_freq_base"]
    positions = list(range(t))
    suffix = "-%d" % layer

    norm = rms_norm(cur, eps)
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
    if width > t:
        kp = pad_tensor(cont(kp, [head_dim, t, n_head_kv]), 0, width - t, 0, 0)
    kq = mul_mat(kp, qp)
    scale = f32(1.0 / math.sqrt(head_dim))
    kqs = soft_max_ext(kq, mask, scale)
    vp = permute(v3, [1, 2, 0, 3])
    vt = cont(vp, [t, head_dim, n_head_kv])
    if width > t:
        vt = pad_tensor(vt, width - t, 0, 0, 0)
    kqv = mul_mat(vt, kqs)
    kqvm = permute(kqv, [0, 2, 1, 3])
    kqv_out = cont(kqvm, [n_embd, t, 1])
    attn_out = mul_mat(weights["attn_output"], kqv_out)
    residual = cur
    narrowed = attn_out
    if last:
        narrowed = get_rows(attn_out, [t - 1])
        residual = get_rows(cur, [t - 1])
    ffn_inp = broadcast(narrowed, residual, lambda x, y: x + y)
    ffn_norm = broadcast(rms_norm(ffn_inp, eps), weights["ffn_norm"], lambda x, y: x * y)
    ffn_gate = mul_mat(weights["ffn_gate"], ffn_norm)
    ffn_up = mul_mat(weights["ffn_up"], ffn_norm)
    ffn_swiglu = swiglu_split(ffn_gate, ffn_up)
    ffn_out = mul_mat(weights["ffn_down"], ffn_swiglu)
    l_out = broadcast(ffn_out, ffn_inp, lambda x, y: x + y)

    if planes is not None:
        # R6 section 2.2: the plane's two tensors are this layer's **post-RoPE** K and its reshaped
        # V, both `{head_dim, n_head_kv, T}`, which is the plane's own order.
        planes.append((kr, v3))
    weight_name = "blk.%d.attn_output.weight" % layer
    records.extend([
        ("norm" + suffix, "RMS_NORM", "embd" if layer == 0 else "l_out-%d" % (layer - 1), norm),
        ("attn_norm" + suffix, "MUL", "norm" + suffix, attn_norm),
        ("Qcur" + suffix, "ADD", "Qcur" + suffix, q),
        ("Vcur" + suffix, "ADD", "Vcur" + suffix, v),
        ("Kcur" + suffix, "ADD", "Kcur" + suffix, k),
        ("Qcur" + suffix, "ROPE", "Qcur" + suffix, qr),
        ("Kcur" + suffix, "ROPE", "Kcur" + suffix, kr),
        ("kq" + suffix, "MUL_MAT", "cache_k_l%d (view) (permuted)" % layer, kq),
        ("kq_soft_max" + suffix, "SOFT_MAX", "kq" + suffix, kqs),
        ("kqv" + suffix, "MUL_MAT", "cache_v_l%d (view) (permuted)" % layer, kqv),
        ("kqv_out" + suffix, "CONT", "kqv%s (permuted)" % suffix, kqv_out),
        ("node_%d" % (100 + layer), "MUL_MAT", weight_name, attn_out),
        ("ffn_inp" + suffix, "ADD", "node_%d" % (100 + layer), ffn_inp),
        ("ffn_norm" + suffix, "MUL", "norm" + suffix, ffn_norm),
        ("ffn_gate" + suffix, "MUL_MAT", "blk.%d.ffn_gate.weight" % layer, ffn_gate),
        ("ffn_up" + suffix, "MUL_MAT", "blk.%d.ffn_up.weight" % layer, ffn_up),
        ("ffn_swiglu" + suffix, "SWIGLU", "ffn_gate" + suffix, ffn_swiglu),
        ("ffn_out" + suffix, "MUL_MAT", "blk.%d.ffn_down.weight" % layer, ffn_out),
        ("l_out" + suffix, "ADD", "ffn_out" + suffix, l_out),
    ])
    return l_out


def model_forward(embed, layers, head, g, tokens, width, planes=None):
    """The whole prefill: one embedding graph, `n_layer` layer graphs, and the head."""
    t = len(tokens)
    mask = Tensor([width, t], [0.0 if c <= r else float("-inf")
                               for r in range(t) for c in range(width)])
    records = []
    embd = get_rows(embed, tokens)
    records.append(("embd", "GET_ROWS", "token_embd.weight", embd))
    cur = embd
    for layer in range(g["n_layer"]):
        cur = model_layer(cur, layers[layer], g, tokens, width, mask, layer == g["n_layer"] - 1,
                          records, layer, planes)
    norm = rms_norm(cur, g["rms_eps"])
    result_norm = broadcast(norm, head["output_norm"], lambda x, y: x * y)
    result_output = mul_mat(head["output"], result_norm)
    records.append(("norm", "RMS_NORM", "l_out-%d" % (g["n_layer"] - 1), norm))
    records.append(("result_norm", "MUL", "norm", result_norm))
    records.append(("result_output", "MUL_MAT", "output.weight", result_output))
    return records, result_output


def model_transcript(records, tokens):
    lines = [
        "build: 10566 (bb4caa754) with cc for x86_64-unknown-linux-gnu",
        "number of input tokens = %d" % len(tokens),
    ]
    for name, op, source, tensor in records:
        lines.extend(transcript_block(name, op, source, tensor))
    return "\n".join(lines) + "\n"


def model_members(g):
    """Twenty-seven members over six blocks, in the container's own order."""
    out = []
    embed = Member("token_embd.weight", "token_embd", 12, KIND_WEIGHT,
                   *model_dims("token_embd", g), model_tensor("token_embd", -1, g).data)
    out.append(("embed", embed))
    for layer in range(g["n_layer"]):
        for role, role_id, kind in LAYER_ROLES:
            dim0, dim1 = model_dims(role, g)
            out.append(("layer%d" % layer,
                        Member("blk.%d.%s.weight" % (layer, role), role, role_id, kind,
                               dim0, dim1, model_tensor(role, layer, g).data)))
    out.append(("head", Member("output_norm.weight", "output_norm", ROLE_OUTPUT_NORM, KIND_WEIGHT,
                               *model_dims("output_norm", g),
                               model_tensor("output_norm", -1, g).data)))
    out.append(("head", Member("output.weight", "output", ROLE_OUTPUT, KIND_WEIGHT,
                               *model_dims("output", g), model_tensor("output", -1, g).data)))
    return out


def model_blocks(members, g, drop_mlp_layer=None, duplicate_embedding=False, drop_output=False):
    grouped = {}
    for tag, member in members:
        grouped.setdefault(tag, []).append(member)
    blocks = [Block(KIND_WEIGHT, -1, list(grouped["embed"]))]
    if duplicate_embedding:
        # Two blocks answering to `(kind 0, layer -1)` and **both** carrying `role_id` 12: section
        # 2.1 fact 2's ambiguity, made reachable. The members are fresh records rather than the same
        # ones: `build` assigns each member exactly one `pack_offset`, and sharing them would put
        # the second block's records outside its own byte range, which is a container defect the
        # reader refuses first.
        blocks.append(Block(KIND_WEIGHT, -1,
                            [Member(m.name, m.role, m.role_id, m.block_kind, m.dim0, m.dim1,
                                    m.values) for m in grouped["embed"]]))
    for layer in range(g["n_layer"]):
        rows = grouped["layer%d" % layer]
        blocks.append(Block(KIND_ATTENTION, layer,
                            [m for m in rows if m.block_kind == KIND_ATTENTION]))
        if layer != drop_mlp_layer:
            blocks.append(Block(KIND_MLP, layer,
                                [m for m in rows if m.block_kind == KIND_MLP]))
    if not drop_output:
        blocks.append(Block(KIND_WEIGHT, -1, list(grouped["head"])))
    return blocks


def model_geometry(g):
    return geometry_document(g)


def write_model_corpus(directory, emit):
    """Section 5.1's whole-model corpus: the base pack, one mutation per new code, the transcript
    at the reconciliation width, and the logits blob the third oracle compares against."""
    g = GEOMETRY
    members = model_members(g)
    base, layout = build(model_blocks(members, g))
    emit("model-pack.alignpack", base)

    tight, _ = build(model_blocks(model_members(g), g), block_align=1, member_align=1)
    emit("model-pack-tight.alignpack", tight)

    ambiguous, _ = build(model_blocks(model_members(g), g, duplicate_embedding=True))
    emit("model-pack-ambiguous.alignpack", ambiguous)

    no_output, _ = build(model_blocks(model_members(g), g, drop_output=True))
    emit("model-pack-no-output.alignpack", no_output)

    coverage, _ = build(model_blocks(model_members(g), g, drop_mlp_layer=1))
    emit("model-pack-coverage.alignpack", coverage)

    partial = [(tag, m) for tag, m in model_members(g)
               if not (tag == "layer1" and m.role == "attn_q_bias")]
    member_missing, _ = build(model_blocks(partial, g))
    emit("model-pack-member-missing.alignpack", member_missing)

    # The `output` member is the last of the twenty-seven; its `ne1` and its ggml type are the two
    # fields section 4.5 mutates, and both are refused before a single byte of the 447 MB member
    # would be read on a real model.
    output_index = len(layout["members"]) - 1
    emit("model-pack-shape.alignpack",
         patch(base, member_field(layout, output_index, 56), "<Q", g["n_vocab"] - 1))
    emit("model-pack-type.alignpack",
         patch(base, member_field(layout, output_index, 40), "<I", 4))
    emit("model-pack-truncated.alignpack", base[:len(base) - 64])

    emit("model-source.bin", source_image(layout))
    emit("model-source-diverged.bin", source_image(layout, corrupt=14))
    emit("model-source-short.bin", b"\0")

    embed = model_tensor("token_embd", -1, g)
    layers = [{role: model_tensor(role, layer, g) for role, _, _ in LAYER_ROLES}
              for layer in range(g["n_layer"])]
    head = {"output_norm": model_tensor("output_norm", -1, g),
            "output": model_tensor("output", -1, g)}

    records, logits = model_forward(embed, layers, head, g, MODEL_TOKENS, MODEL_KV_WIDTH)
    transcript = model_transcript(records, MODEL_TOKENS)
    emit("model-transcript.txt", transcript)
    emit("model-logits.bin", struct.pack("<%df" % logits.count(), *logits.data))
    emit("model-logits-short.bin", b"\0\0\0\0")
    emit("model-logits-perturbed.bin",
         struct.pack("<%df" % logits.count(), *[f32(v + 1.0) for v in logits.data]))

    # The runtime-width forward, whose logits the `WITHIN` verdict is measured against. Section 2.6
    # is why it differs at all: the reduction length, and nothing else.
    runtime_records, runtime_logits = model_forward(
        embed, layers, head, g, MODEL_TOKENS, len(MODEL_TOKENS))
    emit("model-logits-runtime.bin",
         struct.pack("<%df" % runtime_logits.count(), *runtime_logits.data))
    emit("model-transcript-runtime.txt", model_transcript(runtime_records, MODEL_TOKENS))

    # `r5b-model-prefill-forward.md` section 6, correction C23. Three references whose elements
    # have no integer in ten-thousandths, each one mixed into an otherwise ordinary runtime-width
    # vector so the fixture is a *reference* defect and not a degenerate file. Before C23 the
    # first two wrapped `i64` inside the difference and indexed the histogram with a negative
    # bucket — a `SIGABRT` with no document on either arm — and the third read as `0.0` and could
    # compare within the bound.
    def logits_with(*pairs):
        values = list(runtime_logits.data)
        for index, value in pairs:
            values[index] = value
        return struct.pack("<%df" % len(values), *values)

    #   finite, and beyond every magnitude the comparison represents. Both signs, because the
    #   negative one is the operand that made `primary - reference` wrap.
    emit("model-logits-huge.bin", logits_with((0, 3.4e38), (1, -3.4e38)))
    #   an infinity in element **0**, which is where `MODEL_ABORT_TOKENS` puts a primary logit that
    #   rounds to exactly zero ten-thousandths. `0 - i64::MIN` is `i64::MIN`, so before C23 this
    #   exact pair indexed the histogram with `-9223372036854775808` and aborted the process with no
    #   document on both arms; the index and the token list are chosen so the fixture *is* that
    #   input rather than a neighbour of it.
    emit("model-logits-neg-inf.bin", logits_with((0, float("-inf"))))
    #   a NaN, whose `as i64` conversion is `0` rather than a saturation.
    emit("model-logits-nan.bin", logits_with((3, float("nan"))))

    lines = transcript.split("\n")

    def header_at(name):
        return next(i for i, line in enumerate(lines)
                    if line.startswith("common_debug_cb_eval:") and (" %s = " % name) in line)

    # `R5_ORACLE_MISSING`, detail `layer[1]node[norm]`: layer 1's `norm-1` record is deleted.
    start = header_at("norm-1")
    end = next(i for i, line in enumerate(lines[start:], start) if line.startswith("    sum = "))
    emit("model-transcript-missing.txt", "\n".join(lines[:start] + lines[end + 1:]) + "\n")

    # `R5_ORACLE_SHAPE`: `kq-0` declares a reduction width the operand does not name. This is the
    # check that stops the oracle from configuring the thing it verifies (section 3.3).
    kq = header_at("kq-0")
    widened = list(lines)
    widened[kq] = widened[kq].replace("= {%d, " % MODEL_KV_WIDTH, "= {%d, " % (MODEL_KV_WIDTH - 1))
    emit("model-transcript-kv-width.txt", "\n".join(widened) + "\n")

    # A tolerance breach at layer 0: one printed element of `l_out-0` moved by 0.0003, three times
    # section 3.7's threshold, so `oracle.verdict` becomes `FAIL` with `worst_layer` 0 while
    # `status` stays `ok`.
    l_out = header_at("l_out-0")
    perturbed = list(lines)
    row = l_out + 3
    original = perturbed[row]
    first = original.index("[") + 1
    value = float(original[first:first + 12])
    perturbed[row] = original[:first] + ("%12.4f" % (value + 0.0003)) + original[first + 12:]
    emit("model-transcript-perturbed.txt", "\n".join(perturbed) + "\n")

    headers = [line for line in lines
               if line.startswith("common_debug_cb_eval:") or line.startswith("build: ")
               or line.startswith("number of input tokens")]
    emit("model-transcript-headers.txt", "\n".join(headers) + "\n")

    novalues_start = header_at("l_out-1")
    novalues_end = next(i for i, line in enumerate(lines[novalues_start:], novalues_start)
                        if line.startswith("    sum = "))
    emit("model-transcript-novalues.txt",
         "\n".join(lines[:novalues_start + 1] + lines[novalues_end:]) + "\n")

    emit("model-transcript-garbage.txt", bytes(range(256)) * 8)

    write_decode_corpus(g, embed, layers, head, records, logits, emit)


# =============================================================================================
# R6-DECODE-KV-STEP1 (`docs/specs/r6-decode-kv-step1.md` section 5.1)
#
# The same generator, extended with the **second call**: one decode step at `n_past = T` over the
# KV plane the prefill produced. It is a second implementation of section 2.4's decode layer — the
# offset mask, the two concat axes, and the pad back to `KV_WIDTH` — and it is the only way oracle A
# can be checked on a host with no ggml and no model.
#
# The transcript it emits holds **two graphs**, prefill then decode, exactly as `llama-eval-callback
# -n 1` does, so the arm's own "skip the first graph" rule is exercised rather than assumed.
# =============================================================================================


def model_decode_layer(cur, weights, g, planes, n_past, width, mask, last, records, layer):
    """One decode layer: section 2.4's thirty-eight rows, in the order the walk issues them."""
    head_dim, n_head, n_head_kv = g["head_dim"], g["n_head"], g["n_head_kv"]
    n_embd = g["n_embd"]
    eps, freq_base = g["rms_eps"], g["rope_freq_base"]
    suffix = "-%d" % layer
    plane_k, plane_v = planes[layer]

    norm = rms_norm(cur, eps)
    attn_norm = broadcast(norm, weights["attn_norm"], lambda x, y: x * y)
    q = broadcast(mul_mat(weights["attn_q"], attn_norm), weights["attn_q_bias"],
                  lambda x, y: x + y)
    k = broadcast(mul_mat(weights["attn_k"], attn_norm), weights["attn_k_bias"],
                  lambda x, y: x + y)
    v = broadcast(mul_mat(weights["attn_v"], attn_norm), weights["attn_v_bias"],
                  lambda x, y: x + y)
    q3 = reshape(q, [head_dim, n_head, 1])
    k3 = reshape(k, [head_dim, n_head_kv, 1])
    v3 = reshape(v, [head_dim, n_head_kv, 1])
    # The position is `n_past`, not 0. Section 2.6: the embedding row index and the position are two
    # different numbers for the first time here.
    qr = rope_neox(q3, [n_past], g["rope_dim_count"], freq_base)
    kr = rope_neox(k3, [n_past], g["rope_dim_count"], freq_base)
    qp = permute(qr, [0, 2, 1, 3])
    kp = cont(permute(kr, [0, 2, 1, 3]), [head_dim, 1, n_head_kv])
    kcat = concat_tensor(plane_to_past_k(plane_k, head_dim, n_head_kv, n_past), kp, 1)
    kpad = pad_tensor(kcat, 0, width - (n_past + 1), 0, 0)
    kq = mul_mat(kpad, qp)
    scale = f32(1.0 / math.sqrt(head_dim))
    kqs = soft_max_ext(kq, mask, scale)
    vt = cont(permute(v3, [1, 2, 0, 3]), [1, head_dim, n_head_kv])
    vcat = concat_tensor(plane_to_past_v(plane_v, head_dim, n_head_kv, n_past), vt, 0)
    vpad = pad_tensor(vcat, width - (n_past + 1), 0, 0, 0)
    kqv = mul_mat(vpad, kqs)
    kqv_out = cont(permute(kqv, [0, 2, 1, 3]), [n_embd, 1, 1])
    attn_out = mul_mat(weights["attn_output"], kqv_out)
    # The two `WHEN_LAST` rows are kept at `t = 1`, where `get_rows(x, [0])` is the identity
    # (section 2.4). They have no counterpart in llama.cpp's decode graph and no oracle row names
    # them, so nothing below records them.
    narrowed = get_rows(attn_out, [0]) if last else attn_out
    residual = get_rows(cur, [0]) if last else cur
    ffn_inp = broadcast(narrowed, residual, lambda x, y: x + y)
    ffn_norm = broadcast(rms_norm(ffn_inp, eps), weights["ffn_norm"], lambda x, y: x * y)
    ffn_gate = mul_mat(weights["ffn_gate"], ffn_norm)
    ffn_up = mul_mat(weights["ffn_up"], ffn_norm)
    ffn_swiglu = swiglu_split(ffn_gate, ffn_up)
    ffn_out = mul_mat(weights["ffn_down"], ffn_swiglu)
    l_out = broadcast(ffn_out, ffn_inp, lambda x, y: x + y)

    weight_name = "blk.%d.attn_output.weight" % layer
    records.extend([
        ("norm" + suffix, "RMS_NORM", "embd" if layer == 0 else "l_out-%d" % (layer - 1), norm),
        ("attn_norm" + suffix, "MUL", "norm" + suffix, attn_norm),
        ("Qcur" + suffix, "ADD", "Qcur" + suffix, q),
        ("Vcur" + suffix, "ADD", "Vcur" + suffix, v),
        ("Kcur" + suffix, "ADD", "Kcur" + suffix, k),
        ("Qcur" + suffix, "ROPE", "Qcur" + suffix, qr),
        ("Kcur" + suffix, "ROPE", "Kcur" + suffix, kr),
        ("kq" + suffix, "MUL_MAT", "cache_k_l%d (view) (permuted)" % layer, kq),
        ("kq_soft_max" + suffix, "SOFT_MAX", "kq" + suffix, kqs),
        ("kqv" + suffix, "MUL_MAT", "cache_v_l%d (view) (permuted)" % layer, kqv),
        ("kqv_out" + suffix, "CONT", "kqv%s (permuted)" % suffix, kqv_out),
        ("node_%d" % (200 + layer), "MUL_MAT", weight_name, attn_out),
        ("ffn_inp" + suffix, "ADD", "node_%d" % (200 + layer), ffn_inp),
        ("ffn_norm" + suffix, "MUL", "norm" + suffix, ffn_norm),
        ("ffn_gate" + suffix, "MUL_MAT", "blk.%d.ffn_gate.weight" % layer, ffn_gate),
        ("ffn_up" + suffix, "MUL_MAT", "blk.%d.ffn_up.weight" % layer, ffn_up),
        ("ffn_swiglu" + suffix, "SWIGLU", "ffn_gate" + suffix, ffn_swiglu),
        ("ffn_out" + suffix, "MUL_MAT", "blk.%d.ffn_down.weight" % layer, ffn_out),
        ("l_out" + suffix, "ADD", "ffn_out" + suffix, l_out),
    ])
    return l_out


def model_decode(embed, layers, head, g, planes, token, n_past, width):
    """The decode graph set: one embedding gather for the decoded token, the layers, and the head."""
    mask = Tensor([width, 1], [0.0 if c <= n_past else float("-inf") for c in range(width)])
    records = []
    embd = get_rows(embed, [token])
    records.append(("embd", "GET_ROWS", "token_embd.weight", embd))
    cur = embd
    for layer in range(g["n_layer"]):
        cur = model_decode_layer(cur, layers[layer], g, planes, n_past, width, mask,
                                 layer == g["n_layer"] - 1, records, layer)
    norm = rms_norm(cur, g["rms_eps"])
    result_norm = broadcast(norm, head["output_norm"], lambda x, y: x * y)
    result_output = mul_mat(head["output"], result_norm)
    records.append(("norm", "RMS_NORM", "l_out-%d" % (g["n_layer"] - 1), norm))
    records.append(("result_norm", "MUL", "norm", result_norm))
    records.append(("result_output", "MUL_MAT", "output.weight", result_output))
    return records, result_output


def write_decode_corpus(g, embed, layers, head, prefill_records, prefill_logits, emit):
    """Section 5.1's decode corpus: the two-graph transcript, its logits, and the mutations."""
    n_past = len(MODEL_TOKENS)
    planes = []
    # The prefill is recomputed with the planes captured; its records are the ones already emitted,
    # so the two agree by construction rather than by inspection.
    replayed, replayed_logits = model_forward(embed, layers, head, g, MODEL_TOKENS,
                                              MODEL_KV_WIDTH, planes)
    assert replayed_logits.data == prefill_logits.data
    token = max(range(prefill_logits.count()), key=lambda i: prefill_logits.data[i])
    decode_records, decode_logits = model_decode(
        embed, layers, head, g, planes, token, n_past, MODEL_KV_WIDTH)
    lines = model_transcript(prefill_records + decode_records, MODEL_TOKENS)
    emit("model-decode-transcript.txt", lines)
    emit("model-decode-logits.bin",
         struct.pack("<%df" % decode_logits.count(), *decode_logits.data))
    emit("model-decode-argmax.txt", "%d\n" % token)

    # A transcript holding only the **prefill** graph. The arm skips the first graph, so every
    # oracle row is then missing and the run is `R6_ORACLE_MISSING` rather than a silent comparison
    # against the wrong graph — which is the failure this fixture exists to make visible.
    emit("model-decode-transcript-onegraph.txt", model_transcript(prefill_records, MODEL_TOKENS))

    # A tolerance breach inside the **decode** graph: one printed element of the decode `l_out-0`
    # moved by 0.0003, three times section 3.4's threshold.
    rows = lines.split("\n")
    marker = "common_debug_cb_eval:"
    hits = [i for i, line in enumerate(rows) if line.startswith(marker) and " l_out-0 = " in line]
    perturbed = list(rows)
    row = hits[-1] + 3
    original = perturbed[row]
    first = original.index("[") + 1
    value = float(original[first:first + 12])
    perturbed[row] = original[:first] + ("%12.4f" % (value + 0.0003)) + original[first + 12:]
    emit("model-decode-transcript-perturbed.txt", "\n".join(perturbed))

    # `kq-0` of the **decode** graph declaring a reduction width the operand does not name.
    kq_hits = [i for i, line in enumerate(rows) if line.startswith(marker) and " kq-0 = " in line]
    widened = list(rows)
    widened[kq_hits[-1]] = widened[kq_hits[-1]].replace(
        "= {%d, " % MODEL_KV_WIDTH, "= {%d, " % (MODEL_KV_WIDTH - 1))
    emit("model-decode-transcript-kv-width.txt", "\n".join(widened))


# =============================================================================================
# R5D-MOE-LAYER-FORWARD (`docs/specs/r5d-moe-layer-forward.md` section 5.1)
#
# The same generator, extended to a **routed** olmoe layer: one embedding `WeightBlock`, and per
# layer an `AttentionBlock`, a `RouterBlock`, and eight `ExpertBlock`s whose three members are each
# one plane of a stacked tensor with `slice_index` `0..7` and `slice_count` 8. Every member is
# `TYPE_F32`, which keeps the fixture readable and keeps `align_ggml_type_ok` on its F32 row; the
# quantized types are the real model's job.
#
# `n_expert` 8 and `n_expert_used` 3 match `gguf_fixture.py`'s `OLMOE_BASE`, so the two corpora
# describe the same synthetic model. At `n_expert_used = 3` the router's slot axis is 3, which is
# `<= 6`, so this corpus is the **only** place the routing oracle's full print coverage is
# reachable: all nine ids are compared element-wise, where the real model prints 36 of 48.
#
# The forward pass below is a second implementation of the whole routed layer — the router, the
# descending argsort, the Align-side top-k slice, `mul_mat_id`'s per-`(token, slot)` dot product,
# and the slot-ordered reduction — computed in Python with explicit f32 rounding. A second
# implementation is the only way section 4.4's oracle cells can be checked on a host with no model.
# =============================================================================================

GEOMETRY_MOE = {
    "arch": "olmoe",
    "n_layer": 2,
    "n_embd": 8,
    "n_head": 2,
    "n_head_kv": 2,
    "head_dim": 4,
    "n_ff": 16,
    "n_ff_exp": 16,
    "n_vocab": 32,
    "n_expert": 8,
    "n_expert_used": 3,
    "context_length": 512,
    "rms_eps": 1e-05,
    "rope_freq_base": 10000.0,
    "rope_dim_count": 4,
    "rope_type": 2,
}

# Chosen by sweeping the generator's own forward: these three tokens route to **five** of the
# eight experts, with three distinct per-token slot orders, so `U < n_expert`, the compact ids
# differ from the global ids, and the residency ratio is a real fraction rather than 1.
MOE_TOKENS = [0, 1, 8]

KIND_EXPERT = 3
KIND_ROUTER = 4

# The ten dense roles in `src/layer_olmoe.align`'s own slot order, with `src/alignpack.align`'s
# frozen `role_id`s. `ffn_norm` and the router live in the `RouterBlock` — everything the layer
# needs *before* it knows which experts to fetch.
MOE_DENSE_ROLES = [
    ("token_embd", 12, KIND_WEIGHT),
    ("attn_norm", 0, KIND_ATTENTION),
    ("attn_q", 1, KIND_ATTENTION),
    ("attn_q_norm", 27, KIND_ATTENTION),
    ("attn_k", 3, KIND_ATTENTION),
    ("attn_k_norm", 28, KIND_ATTENTION),
    ("attn_v", 5, KIND_ATTENTION),
    ("attn_output", 7, KIND_ATTENTION),
    ("ffn_norm", 8, KIND_ROUTER),
    ("router", 17, KIND_ROUTER),
]

MOE_EXPERT_ROLES = [
    ("ffn_gate_exps", 19),
    ("ffn_up_exps", 21),
    ("ffn_down_exps", 23),
]


def moe_dense_dims(role, g):
    heads = g["n_head"] * g["head_dim"]
    return {
        "token_embd": (g["n_embd"], g["n_vocab"]),
        "attn_norm": (g["n_embd"], 1),
        "attn_q": (g["n_embd"], heads),
        "attn_q_norm": (g["n_embd"], 1),
        "attn_k": (g["n_embd"], heads),
        "attn_k_norm": (g["n_embd"], 1),
        "attn_v": (g["n_embd"], heads),
        "attn_output": (g["n_embd"], g["n_embd"]),
        "ffn_norm": (g["n_embd"], 1),
        "router": (g["n_embd"], g["n_expert"]),
    }[role]


def moe_claim_dims(role, g):
    """One **plane**'s dims. The stacked tensor's third axis is `n_expert`."""
    if role == "ffn_down_exps":
        return (g["n_ff_exp"], g["n_embd"])
    return (g["n_embd"], g["n_ff_exp"])


def moe_tensor(role, layer, g, expert=None):
    dim0, dim1 = (moe_claim_dims(role, g) if expert is not None
                  else moe_dense_dims(role, g))
    seed = role if layer < 0 else "%s@%d" % (role, layer)
    if expert is not None:
        seed = "%s#%d" % (seed, expert)
    return Tensor([dim0, dim1], weight_values(seed, dim0 * dim1))


def soft_max_plain(a):
    """`ggml_soft_max(ctx, a)`: unit scale, **no mask**, and no renormalization anywhere."""
    zero = Tensor([a.ne[0], 1], [0.0] * a.ne[0])
    return soft_max_ext(a, zero, 1.0)


def argsort_desc(a):
    """`ggml_argsort(..., GGML_SORT_ORDER_DESC)`: the permutation of indices, not the values.

    ggml's kernel is a selection sort with a strict comparison, so equal probabilities keep
    ascending index order; Python's `sorted` is stable, which is the same rule.
    """
    ne0 = a.ne[0]
    rows = a.count() // ne0
    out = []
    for r in range(rows):
        row = a.data[r * ne0:(r + 1) * ne0]
        out.extend(sorted(range(ne0), key=lambda i: (-row[i], i)))
    return Tensor(a.ne, [float(v) for v in out])


def get_rows_3d(a, ids):
    """`ggml_get_rows` with a 3-D source and a 2-D index tensor: `{a.ne0, ids.ne0, ids.ne1}`."""
    nc = a.ne[0]
    out = [0.0] * (nc * ids.ne[0] * ids.ne[1])
    for i1 in range(ids.ne[1]):
        for i0 in range(ids.ne[0]):
            at = i0 + ids.ne[0] * i1
            row = int(ids.data[at])
            base = nc * (row + a.ne[1] * i1)
            out[at * nc:at * nc + nc] = a.data[base:base + nc]
    return Tensor([nc, ids.ne[0], ids.ne[1]], out)


def mul_mat_id(stack, b, ids, n_ids):
    """`ggml_mul_mat_id`. `stack` is a list of `[k, m]` planes, `b` is `[k, b1, T]`.

    The accumulation order is `mul_mat`'s own, which is section 2.3's whole point: a compact stack
    with remapped ids is bit-identical to a whole one because the dot product does not depend on
    how many planes the stack holds.
    """
    k = stack[0].ne[0]
    m = stack[0].ne[1]
    tokens = b.ne[2]
    b1 = b.ne[1]
    out = [0.0] * (m * n_ids * tokens)
    for i2 in range(tokens):
        for i1 in range(n_ids):
            plane = stack[ids[i1 + n_ids * i2]]
            base_b = k * ((i1 % b1) + b1 * i2)
            for i0 in range(m):
                base_a = k * i0
                total = 0.0
                for at in range(k):
                    total = f32(total + f32(plane.data[base_a + at] * b.data[base_b + at]))
                out[i0 + m * (i1 + n_ids * i2)] = total
    return Tensor([m, n_ids, tokens], out)


def slot_view(a, slot):
    """`ggml_view_2d(weighted, n_embd, T, weighted->nb[2], slot * weighted->nb[1])`."""
    ne0, ne1, ne2 = a.ne[0], a.ne[1], a.ne[2]
    out = []
    for i2 in range(ne2):
        base = ne0 * (slot + ne1 * i2)
        out.extend(a.data[base:base + ne0])
    return Tensor([ne0, ne2], out)


def moe_forward(dense, experts, g, tokens):
    """The routed layer, node for node, in the order both node tables issue them."""
    t = len(tokens)
    head_dim, n_head = g["head_dim"], g["n_head"]
    n_embd, n_expert, n_used = g["n_embd"], g["n_expert"], g["n_expert_used"]
    eps, freq_base = g["rms_eps"], g["rope_freq_base"]

    mask = Tensor([t, t], [0.0 if c <= r else float("-inf")
                           for r in range(t) for c in range(t)])
    positions = list(range(t))

    embd = get_rows(dense["token_embd"], tokens)
    norm_embd = rms_norm(embd, eps)
    attn_norm = broadcast(norm_embd, dense["attn_norm"], lambda x, y: x * y)
    # Section 2.2 fact 1: project, RMS-norm over `n_embd`, scale, **then** reshape, then RoPE.
    q_pre = mul_mat(dense["attn_q"], attn_norm)
    norm_q = rms_norm(q_pre, eps)
    q_normed = broadcast(norm_q, dense["attn_q_norm"], lambda x, y: x * y)
    q3 = reshape(q_normed, [head_dim, n_head, t])
    q_rope = rope_neox(q3, positions, g["rope_dim_count"], freq_base)
    k_pre = mul_mat(dense["attn_k"], attn_norm)
    norm_k = rms_norm(k_pre, eps)
    k_normed = broadcast(norm_k, dense["attn_k_norm"], lambda x, y: x * y)
    k3 = reshape(k_normed, [head_dim, n_head, t])
    k_rope = rope_neox(k3, positions, g["rope_dim_count"], freq_base)
    v_cur = mul_mat(dense["attn_v"], attn_norm)
    v3 = reshape(v_cur, [head_dim, n_head, t])
    kq = mul_mat(permute(k_rope, [0, 2, 1, 3]), permute(q_rope, [0, 2, 1, 3]))
    kqs = soft_max_ext(kq, mask, f32(1.0 / math.sqrt(head_dim)))
    vt = cont(permute(v3, [1, 2, 0, 3]), [t, head_dim, n_head])
    kqv = mul_mat(vt, kqs)
    kqv_out = cont(permute(kqv, [0, 2, 1, 3]), [n_embd, t, 1])
    attn_out = mul_mat(dense["attn_output"], kqv_out)
    ffn_inp = broadcast(attn_out, embd, lambda x, y: x + y)
    norm_ffn = rms_norm(ffn_inp, eps)
    ffn_norm = broadcast(norm_ffn, dense["ffn_norm"], lambda x, y: x * y)

    logits = mul_mat(dense["router"], ffn_norm)
    probs = soft_max_plain(logits)
    argsort = argsort_desc(probs)
    topk = [int(argsort.data[token * n_expert + slot])
            for token in range(t) for slot in range(n_used)]
    topk_tensor = Tensor([n_used, t], [float(v) for v in topk])
    probs_r = reshape(probs, [1, n_expert, t])
    weights = get_rows_3d(probs_r, topk_tensor)
    ffn_norm_r = reshape(ffn_norm, [n_embd, 1, t])
    gate = mul_mat_id(experts["ffn_gate_exps"], ffn_norm_r, topk, n_used)
    up = mul_mat_id(experts["ffn_up_exps"], ffn_norm_r, topk, n_used)
    swiglu = swiglu_split(gate, up)
    down = mul_mat_id(experts["ffn_down_exps"], swiglu, topk, n_used)
    weighted = broadcast(down, weights, lambda x, y: x * y)
    views = [slot_view(weighted, slot) for slot in range(n_used)]
    # **Ascending slot order.** Section 2.3 measured a reversed order changing 1,189 of 2,048
    # elements of one token's `ffn_moe_out`.
    moe_out = views[0]
    for slot in range(1, n_used):
        moe_out = broadcast(moe_out, views[slot], lambda x, y: x + y)
    l_out = broadcast(moe_out, ffn_inp, lambda x, y: x + y)

    records = [
        ("embd", "GET_ROWS", "token_embd.weight", embd),
        ("norm-0", "RMS_NORM", "embd", norm_embd),
        ("attn_norm-0", "MUL", "norm-0", attn_norm),
        ("Qcur-0", "MUL_MAT", "blk.0.attn_q.weight", q_pre),
        ("norm-0", "RMS_NORM", "Qcur-0", norm_q),
        ("Qcur_normed-0", "MUL", "norm-0", q_normed),
        ("Qcur-0", "ROPE", "Qcur_normed-0 (reshaped)", q_rope),
        ("Kcur-0", "MUL_MAT", "blk.0.attn_k.weight", k_pre),
        ("norm-0", "RMS_NORM", "Kcur-0", norm_k),
        ("Kcur_normed-0", "MUL", "norm-0", k_normed),
        ("Kcur-0", "ROPE", "Kcur_normed-0 (reshaped)", k_rope),
        ("Vcur-0", "MUL_MAT", "blk.0.attn_v.weight", v_cur),
        ("kq-0", "MUL_MAT", "Kcur-0 (permuted)", kq),
        ("kq_soft_max-0", "SOFT_MAX", "kq-0", kqs),
        ("kqv-0", "MUL_MAT", "Vcur-0 (transposed)", kqv),
        ("kqv_out-0", "CONT", "kqv-0 (permuted)", kqv_out),
        ("node_32", "MUL_MAT", "blk.0.attn_output.weight", attn_out),
        ("ffn_inp-0", "ADD", "node_32", ffn_inp),
        ("norm-0", "RMS_NORM", "ffn_inp-0", norm_ffn),
        ("ffn_norm-0", "MUL", "norm-0", ffn_norm),
        ("ffn_moe_logits-0", "MUL_MAT", "blk.0.ffn_gate_inp.weight", logits),
        ("ffn_moe_probs-0", "SOFT_MAX", "ffn_moe_logits-0", probs),
        ("ffn_moe_argsort-0", "ARGSORT", "ffn_moe_probs-0", argsort),
        ("ffn_moe_topk-0", "VIEW", "ffn_moe_argsort-0", topk_tensor),
        ("ffn_moe_weights-0", "GET_ROWS", "ffn_moe_probs-0 (reshaped)", weights),
        ("ffn_moe_gate-0", "MUL_MAT_ID", "blk.0.ffn_gate_exps.weight", gate),
        ("ffn_moe_up-0", "MUL_MAT_ID", "blk.0.ffn_up_exps.weight", up),
        ("ffn_moe_swiglu-0", "SWIGLU", "ffn_moe_gate-0", swiglu),
        ("ffn_moe_down-0", "MUL_MAT_ID", "blk.0.ffn_down_exps.weight", down),
        ("ffn_moe_weighted-0", "MUL", "ffn_moe_down-0", weighted),
        ("ffn_moe_out-0", "ADD", "node_60", moe_out),
        ("l_out-0", "ADD", "ffn_moe_out-0", l_out),
    ]
    return records, topk


def moe_members(g):
    """`(tag, Member)` pairs in the container's own order."""
    out = []
    embed = moe_tensor("token_embd", -1, g)
    out.append(("embed", Member("token_embd.weight", "token_embd", 12, KIND_WEIGHT,
                                *moe_dense_dims("token_embd", g), embed.data)))
    for layer in range(g["n_layer"]):
        for role, role_id, kind in MOE_DENSE_ROLES:
            if role == "token_embd":
                continue
            dim0, dim1 = moe_dense_dims(role, g)
            name = "blk.%d.%s.weight" % (layer, "ffn_gate_inp" if role == "router" else role)
            out.append(("layer%d" % layer,
                        Member(name, role, role_id, kind, dim0, dim1,
                               moe_tensor(role, layer, g).data,
                               n_dims=1 if dim1 == 1 else 2)))
        for expert in range(g["n_expert"]):
            for role, role_id in MOE_EXPERT_ROLES:
                dim0, dim1 = moe_claim_dims(role, g)
                out.append(("expert%d_%d" % (layer, expert),
                            Member("blk.%d.%s.weight" % (layer, role), role, role_id,
                                   KIND_EXPERT, dim0, dim1,
                                   moe_tensor(role, layer, g, expert=expert).data,
                                   n_dims=3, dim2=g["n_expert"], dim3=1,
                                   slice_index=expert, slice_count=g["n_expert"])))
    return out


def moe_blocks(members, g, drop_expert=None, drop_expert_role=None, drop_router_layer=None,
               duplicate_router=False, drop_role=None):
    grouped = {}
    for tag, member in members:
        grouped.setdefault(tag, []).append(member)
    blocks = [Block(KIND_WEIGHT, -1, list(grouped["embed"]))]
    for layer in range(g["n_layer"]):
        rows = grouped["layer%d" % layer]
        attention = [m for m in rows if m.block_kind == KIND_ATTENTION
                     and not (layer == 0 and m.role == drop_role)]
        blocks.append(Block(KIND_ATTENTION, layer, attention))
        if layer != drop_router_layer:
            blocks.append(Block(KIND_ROUTER, layer,
                                [m for m in rows if m.block_kind == KIND_ROUTER]))
        if duplicate_router and layer == 0:
            # Two blocks answering to `(RouterBlock, layer 0)`: the ambiguity section 3.8 step 11
            # refuses. Fresh records, because `build` assigns each member exactly one `pack_offset`.
            twin = [Member(m.name, m.role, m.role_id, m.block_kind, m.dim0, m.dim1, m.values,
                           n_dims=m.n_dims, dim2=m.dim2, dim3=m.dim3,
                           slice_index=m.slice_index, slice_count=m.slice_count)
                    for m in rows if m.block_kind == KIND_ROUTER]
            blocks.append(Block(KIND_ROUTER, layer, twin))
        for expert in range(g["n_expert"]):
            if layer == 0 and expert == drop_expert:
                continue
            claims = list(grouped["expert%d_%d" % (layer, expert)])
            if layer == 0 and drop_expert_role is not None and expert == drop_expert_role[0]:
                claims = [m for m in claims if m.role != drop_expert_role[1]]
            blocks.append(Block(KIND_EXPERT, layer, claims, expert=expert))
    return blocks


def moe_geometry_document(g):
    """The `model` object exactly as `main --model-ir` emits it for an olmoe container."""
    return {
        "schema_version": 2,
        "kind": "R1_MODEL_IR",
        "path": "synthetic-olmoe.gguf",
        "status": "ok",
        "error_code": "",
        "error_detail": "",
        "model": {
            "arch": g["arch"],
            "n_layer": g["n_layer"],
            "n_embd": g["n_embd"],
            "n_head": g["n_head"],
            "n_head_kv": g["n_head_kv"],
            "head_dim": g["head_dim"],
            "n_ff": g["n_ff"],
            "n_ff_exp": g["n_ff_exp"],
            "n_vocab": g["n_vocab"],
            "n_expert": g["n_expert"],
            "n_expert_used": g["n_expert_used"],
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


MOE_GEOMETRY_FIELDS = [
    "arch", "n_layer", "n_embd", "n_head", "n_head_kv", "head_dim", "n_ff_exp", "n_vocab",
    "n_expert", "n_expert_used", "context_length", "rms_eps_bits",
]
MOE_ROPE_FIELDS = ["type", "dim_count", "freq_base_bits", "scaling_type"]


def moe_geometry_corpus(g):
    base = moe_geometry_document(g)
    out = [("moe-geometry", base)]
    for field in MOE_GEOMETRY_FIELDS:
        copy = json.loads(json.dumps(base))
        del copy["model"][field]
        out.append(("moe-geometry-missing-" + field, copy))
    for field in MOE_ROPE_FIELDS:
        copy = json.loads(json.dumps(base))
        del copy["model"]["rope"][field]
        out.append(("moe-geometry-missing-rope-" + field, copy))
    for name, path, value in (
        ("kind", ("kind",), "R1_OLMOE_MODEL_IR"),
        ("version", ("schema_version",), 1),
        ("arch", ("model", "arch"), "qwen2"),
        ("rope-type", ("model", "rope", "type"), 0),
        ("rope-scaled", ("model", "rope", "scaling_type"), "yarn"),
        ("rope-dims", ("model", "rope", "dim_count"), 2),
        ("inconsistent", ("model", "n_embd"), 9),
        ("head-kv", ("model", "n_head_kv"), 1),
        ("expert-zero", ("model", "n_expert"), 0),
        ("expert-used-high", ("model", "n_expert_used"), 9),
        ("expert-used-huge", ("model", "n_expert_used"), 64),
        ("eps-nan", ("model", "rms_eps_bits"), "7fc00000"),
        ("eps-negative", ("model", "rms_eps_bits"), "bf800000"),
        ("rope-base-zero", ("model", "rope", "freq_base_bits"), "00000000"),
        ("rope-base-inf", ("model", "rope", "freq_base_bits"), "7f800000"),
    ):
        broken = json.loads(json.dumps(base))
        node = broken
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        out.append(("moe-geometry-" + name, broken))
    return out


def moe_transcript(records, tokens):
    lines = [
        "build: 10566 (bb4caa754) with cc for x86_64-unknown-linux-gnu",
        "number of input tokens = %d" % len(tokens),
    ]
    for name, op, source, tensor in records:
        lines.extend(transcript_block(name, op, source, tensor))
    return "\n".join(lines) + "\n"


def write_moe_corpus(directory, emit):
    g = GEOMETRY_MOE
    members = moe_members(g)
    base, layout = build(moe_blocks(members, g))
    emit("moe-pack.alignpack", base)

    # `R5_ALIGNMENT`. `block_align = 1` packs the member windows tight, but at this geometry every
    # dense member is a whole number of 32-byte rows, so tightness alone cannot put one off a
    # `TENSOR_ALIGNMENT` boundary — unlike R5A's corpus, olmoe declares no bias and its smallest
    # member is `n_embd` floats. Halving `token_embd`'s declared `nbytes` makes the row stride 16,
    # so the row-gathered window is 48 bytes and every later window offset is 16 mod 32. The dims
    # are untouched, which is what keeps the fault an *alignment* fault and not a shape one.
    tight, tight_layout = build(moe_blocks(moe_members(g), g), block_align=1, member_align=1)
    emit("moe-pack-tight.alignpack",
         patch(tight, member_field(tight_layout, 0, 24), "<Q", g["n_vocab"] * 16))

    no_router, _ = build(moe_blocks(moe_members(g), g, drop_router_layer=0))
    emit("moe-pack-no-router.alignpack", no_router)

    ambiguous, _ = build(moe_blocks(moe_members(g), g, duplicate_router=True))
    emit("moe-pack-ambiguous.alignpack", ambiguous)

    no_qnorm, _ = build(moe_blocks(moe_members(g), g, drop_role="attn_q_norm"))
    emit("moe-pack-no-qnorm.alignpack", no_qnorm)

    no_expert, _ = build(moe_blocks(moe_members(g), g, drop_expert=5))
    emit("moe-pack-no-expert.alignpack", no_expert)

    # The reference forward, which is also what names the routed union the mutations below target.
    dense = {role: moe_tensor(role, -1 if role == "token_embd" else 0, g)
             for role, _, _ in MOE_DENSE_ROLES}
    experts = {role: [moe_tensor(role, 0, g, expert=e) for e in range(g["n_expert"])]
               for role, _ in MOE_EXPERT_ROLES}
    records, topk = moe_forward(dense, experts, g, MOE_TOKENS)
    routed = sorted(set(topk))
    first_routed = routed[0]

    role_missing, _ = build(moe_blocks(moe_members(g), g,
                                       drop_expert_role=(first_routed, "ffn_up_exps")))
    emit("moe-pack-expert-role.alignpack", role_missing)

    # Member indices are arithmetic over the block skeleton, because `build` writes members in
    # block order: one embedding member, then layer 0's nine dense members, then its experts.
    dense_layer_members = len(MOE_DENSE_ROLES) - 1
    claim_base = 1 + dense_layer_members + first_routed * len(MOE_EXPERT_ROLES)
    router_index = 1 + dense_layer_members - 1

    # `R5D_ROUTER_SHAPE`: a router whose second axis is not `n_expert` silently produces a valid
    # softmax over the wrong number of experts.
    emit("moe-pack-router-shape.alignpack",
         patch(base, member_field(layout, router_index, 56), "<Q", g["n_expert"] - 1))
    # `R5_SHAPE`: `attn_q`'s row count. Member 2 of the container is layer 0's `attn_q`.
    emit("moe-pack-shape.alignpack",
         patch(base, member_field(layout, 2, 56), "<Q", g["n_embd"] + 1))
    # `R4_5_SLICE`: a claim whose `slice_count` is not the sliced axis's own extent.
    emit("moe-pack-slice.alignpack",
         patch(base, member_field(layout, claim_base, 84), "<i", g["n_expert"] - 1))
    # `R5D_CLAIM_MISSING`: a claim that names a plane other than its own expert.
    emit("moe-pack-slice-index.alignpack",
         patch(base, member_field(layout, claim_base, 80), "<i",
               (first_routed + 1) % g["n_expert"]))
    # `R5_TYPE_UNSUPPORTED`: a claim declaring a ggml type the operand table does not carry.
    emit("moe-pack-claim-type.alignpack",
         patch(base, member_field(layout, claim_base, 40), "<I", 4))
    # Correction C12's `R5_TYPE_UNSUPPORTED`: a claim of a **later** routed expert declaring a
    # different, perfectly supported ggml type from the first routed expert's for the same role.
    # `nbytes` is untouched, so the plane still fills its region and the stack the arm builds is
    # still exactly `U` planes; only the encoding the stack was built from is wrong, and no oracle
    # can see that because all three read the stack the arm built. The `claim-type` mutation above
    # patches `routed[0]`, which the first-plane type check already covers; this one patches
    # `routed[1]`, which it did not.
    second_routed = routed[1]
    mismatch_base = 1 + dense_layer_members + second_routed * len(MOE_EXPERT_ROLES)
    emit("moe-pack-claim-type-mismatch.alignpack",
         patch(base, member_field(layout, mismatch_base, 40), "<I", 1))
    emit("moe-pack-truncated.alignpack", base[:len(base) - 64])

    emit("moe-source.bin", source_image(layout))
    emit("moe-source-diverged.bin", source_image(layout, corrupt=claim_base))
    emit("moe-source-short.bin", b"\0")

    for name, document in moe_geometry_corpus(g):
        emit(name + ".json", json.dumps(document, separators=(",", ":")) + "\n")

    transcript = moe_transcript(records, MOE_TOKENS)
    emit("moe-transcript.txt", transcript)

    lines = transcript.split("\n")

    def header_at(name, op):
        return next(i for i, line in enumerate(lines)
                    if line.startswith("common_debug_cb_eval:")
                    and (" %s = " % name) in line and ("%s(" % op) in line)

    # `R5_ORACLE_MISSING`: the `l_out-0` record is deleted outright.
    start = header_at("l_out-0", "ADD")
    emit("moe-transcript-missing.txt", "\n".join(lines[:start]) + "\n")

    # `R5_ORACLE_SHAPE`: `l_out-0` declares one token fewer than the graph computed.
    reshaped = list(lines)
    reshaped[start] = reshaped[start].replace(
        "{%d, %d, 1, 1}" % (g["n_embd"], len(MOE_TOKENS)),
        "{%d, %d, 1, 1}" % (g["n_embd"], len(MOE_TOKENS) - 1))
    emit("moe-transcript-shape.txt", "\n".join(reshaped) + "\n")

    # A tolerance breach: one printed element of `l_out-0` moved by 0.0003, three times section
    # 3.6's threshold, so `oracle.verdict` becomes `FAIL` while `status` stays `ok`.
    perturbed = list(lines)
    row = start + 3
    original = perturbed[row]
    first = original.index("[") + 1
    value = float(original[first:first + 12])
    perturbed[row] = original[:first] + ("%12.4f" % (value + 0.0003)) + original[first + 12:]
    emit("moe-transcript-perturbed.txt", "\n".join(perturbed) + "\n")

    headers = [line for line in lines
               if line.startswith("common_debug_cb_eval:") or line.startswith("build: ")
               or line.startswith("number of input tokens")]
    emit("moe-transcript-headers.txt", "\n".join(headers) + "\n")

    end = next(i for i, line in enumerate(lines[start:], start)
               if line.startswith("    sum = "))
    emit("moe-transcript-novalues.txt", "\n".join(lines[:start + 1] + lines[end:]) + "\n")

    emit("moe-transcript-garbage.txt", bytes(range(256)) * 8)

    # `routing.verdict: MISMATCH` on a **successful** run: one printed expert id of
    # `ffn_moe_topk-0` is moved to another expert and the block sum moves with it, so both halves
    # of oracle 2 disagree while oracle 3 is still evaluated and reported.
    topk_header = header_at("ffn_moe_topk-0", "VIEW")
    id_row = topk_header + 3
    mismatch = list(lines)
    original = mismatch[id_row]
    first = original.index("[") + 1
    was = int(float(original[first:first + 12]))
    now = (was + 1) % g["n_expert"]
    mismatch[id_row] = original[:first] + ("%12.4f" % now) + original[first + 12:]
    sum_row = next(i for i, line in enumerate(mismatch[topk_header:], topk_header)
                   if line.startswith("    sum = "))
    mismatch[sum_row] = "    sum = %f" % (sum(topk) - was + now)
    emit("moe-transcript-routing.txt", "\n".join(mismatch) + "\n")

    # `R2_EXPERT_ID_NOT_INTEGRAL`: an i32 element the instrument could not have printed.
    nonintegral = list(lines)
    original = nonintegral[id_row]
    nonintegral[id_row] = original[:first] + ("%12.4f" % (was + 0.5)) + original[first + 12:]
    emit("moe-transcript-nonintegral.txt", "\n".join(nonintegral) + "\n")

    # The routing the generator's own second implementation produced, so the runner asserts the
    # document's `routing` object against an independent computation rather than against itself.
    plane_bytes = sum(moe_claim_dims(role, g)[0] * moe_claim_dims(role, g)[1] * 4
                      for role, _ in MOE_EXPERT_ROLES)
    used = g["n_expert_used"]
    emit("moe-routing.json", json.dumps({
        "tokens": MOE_TOKENS,
        "expert_ids": [topk[i * used:(i + 1) * used] for i in range(len(MOE_TOKENS))],
        "routed": routed,
        "routed_count": len(routed),
        "compact_ids": [[routed.index(e) for e in topk[i * used:(i + 1) * used]]
                        for i in range(len(MOE_TOKENS))],
        "expert_bytes_read": len(routed) * plane_bytes,
        "expert_bytes_in_layer": g["n_expert"] * plane_bytes,
        "planes_read": len(routed) * len(MOE_EXPERT_ROLES),
        "planes_in_layer": g["n_expert"] * len(MOE_EXPERT_ROLES),
    }, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
