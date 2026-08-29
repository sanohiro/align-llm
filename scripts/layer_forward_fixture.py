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

import hashlib
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
# Where the synthetic source blob's "tensor data" begins: `build` lays every member out from this
# offset, so `[0, SOURCE_DATA_OFFSET)` is the region the pack's source-identity digest covers.
SOURCE_DATA_OFFSET = 4096

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
    source_cursor = SOURCE_DATA_OFFSET
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
        "source_record_offset": source_record_offset,
        "members": members,
        "blocks": blocks,
        "total_bytes": total_bytes,
    }

    # R6-KV-PERSIST section 2.4. The pack's own source-identity record, in
    # `docs/specs/r4-alignpack-layer-major.md` section 2.4.6's field order. Before this capability
    # the fixture left the region zero, which made the `akvp` container's model identity a digest of
    # nothing: a bug that handed the writer an empty identity would have compared equal to the
    # file's and passed. It is written here so the hosted identity is non-degenerate, and it moves
    # **no** offset and no document field -- the region was already reserved and no arm's renderer
    # names it.
    image = source_image(layout)
    struct.pack_into("<QQQQ", raw, source_record_offset, len(image), SOURCE_DATA_OFFSET,
                     len(members), 0)
    struct.pack_into("<II", raw, source_record_offset + 32, 3, 32)
    struct.pack_into("<Q", raw, source_record_offset + 40, SOURCE_DATA_OFFSET)
    raw[source_record_offset + 48:source_record_offset + 80] = \
        hashlib.sha256(image[:SOURCE_DATA_OFFSET]).digest()
    struct.pack_into("<Q", raw, source_record_offset + 80,
                     sum(m.nbytes for m in members))
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

    if moe and model:
        write_moe_model_corpus(directory, emit)

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

# `r6-step-n.md` section 4.7. **The reference loop's greedy ids must not be constant.** With the
# unmodified generator the chain is a fixed point — vocabulary row 24 is the prefill's argmax and
# also its own step's argmax, so the three hosted ids are `24, 24, 24` and a decode loop that fed
# step 1's token to every later step would satisfy every per-step assertion the fifth smoke block
# makes. One row is therefore re-seeded to break the fixed point, and the chain becomes
# `24 -> 9 -> 27`.
#
# **Row 24 and only row 24**, because no prefill case gathers it: the token lists in play across the
# whole corpus are `3,17,5` (`MODEL_TOKENS`), `1,25,5` (`MODEL_ABORT_TOKENS`), and `1..8`
# (`mf-tokens-seven-transcript` / `-eight-no-transcript`), and the out-of-range lists are refused
# before a gather. Every prefill-derived golden row is therefore byte-unchanged and only the
# decode-step documents move. The seed is `weight_values`' own per-index shape, `"role@index"`,
# which `model_tensor` already uses for per-layer tensors.
MODEL_DECODE_RESEEDED_ROWS = (24,)

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
    tensor = Tensor([dim0, dim1], weight_values(seed, dim0 * dim1))
    if role == "token_embd":
        # `MODEL_DECODE_RESEEDED_ROWS`' reason, in one place so the pack and the reference forward
        # cannot disagree: both read this function and neither holds a copy of the row.
        for row in MODEL_DECODE_RESEEDED_ROWS:
            tensor.data[row * dim0:(row + 1) * dim0] = weight_values("%s@%d" % (role, row), dim0)
    return tensor


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

    # R6-KV-PERSIST section 2.4. A pack whose source-identity digest is thirty-two zero bytes
    # carries **no** model identity, and an all-zero digest compares equal to the all-zero digest a
    # container written against such a pack would carry — so the identity check would pass over
    # nothing. This pack is otherwise valid; only the digest slot is degenerate.
    zero_identity = bytearray(base)
    at = layout["source_record_offset"] + 48
    zero_identity[at:at + 32] = bytes(32)
    emit("model-pack-zero-identity.alignpack", bytes(zero_identity))

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

    write_decode_corpus(g, embed, layers, head, records, logits, base, layout, emit)


# =============================================================================================
# R6-DECODE-KV-STEP1 (`docs/specs/r6-decode-kv-step1.md` section 5.1) and R6-STEP-N
# (`docs/specs/r6-step-n.md` section 4.7)
#
# The same generator, extended from the **second call** to a **loop of `DECODE_STEPS` calls**:
# prefill, then one decode step per iteration at `n_past = T + k - 1`, each appending its own K and V
# column to the plane before the next reads it. It is a second implementation of R6 section 2.4's
# decode layer — the offset mask, the two concat axes, the pad back to `KV_WIDTH`, and now the
# write-back — and it is the only way oracle A' can be checked on a host with no ggml and no model.
#
# The transcript it emits holds `DECODE_STEPS + 1` graphs, prefill then one per step, exactly as
# `llama-eval-callback -n N` emits them, so the arm's own "skip `k` graphs" rule is exercised at
# three different offsets rather than assumed.
#
# **Hosted `K` is 3, not 16.** Three steps prove the recurrence: step 1 is R6's exact case, step 2 is
# the first that *reads* a written-back column, and step 3 is the first where two written-back
# columns are read. A loop correct for `1 -> 2 -> 3` is correct for `k -> k+1` by the same code path,
# and 16 would multiply a pure-Python fixture corpus and the smoke's runtime for no new closure cell.
# The real `N = 16` is the qualification's.
# =============================================================================================

DECODE_STEPS = 3


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

    # R6-STEP-N section 2.4's write-back, in the reference. The plane grows by exactly one column of
    # this layer's post-RoPE K and its reshaped V — the same two nodes the prefill captured, at
    # `t = 1` — **after** the concats above read the plane as it was. The two byte ranges are
    # disjoint and the order is upload, compute, write, which is the invariant the arm claims.
    planes[layer] = (concat_tensor(plane_k, kr, 2), concat_tensor(plane_v, v3, 2))
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


def write_decode_corpus(g, embed, layers, head, prefill_records, prefill_logits, pack_bytes,
                        layout, emit):
    """R6-STEP-N section 4.7's decode corpus: the `K+1`-graph transcript, its ids, and the mutations."""
    n_past = len(MODEL_TOKENS)
    planes = []
    # The prefill is recomputed with the planes captured; its records are the ones already emitted,
    # so the two agree by construction rather than by inspection.
    replayed, replayed_logits = model_forward(embed, layers, head, g, MODEL_TOKENS,
                                              MODEL_KV_WIDTH, planes)
    assert replayed_logits.data == prefill_logits.data
    token = max(range(prefill_logits.count()), key=lambda i: prefill_logits.data[i])
    # The reference loop. Step `k` consumes `d_k` and produces `d_{k+1}`, and the plane it reads at
    # step `k+1` is the one step `k` wrote — which is what makes step 2 the first iteration that
    # exercises the write-back at all.
    decode_records = []
    consumed = []
    decode_logits = prefill_logits
    per_step = []
    for step in range(DECODE_STEPS):
        consumed.append(token)
        records, decode_logits = model_decode(
            embed, layers, head, g, planes, token, n_past + step, MODEL_KV_WIDTH)
        per_step.append(records)
        decode_records.extend(records)
        token = max(range(decode_logits.count()), key=lambda i: decode_logits.data[i])
    lines = model_transcript(prefill_records + decode_records, MODEL_TOKENS)
    emit("model-decode-transcript.txt", lines)
    emit("model-decode-logits.bin",
         struct.pack("<%df" % decode_logits.count(), *decode_logits.data))
    # One id per line, `K` lines: the ids the reference loop **consumed**, which is exactly what
    # `decode.token_ids` publishes. The smoke asserts the two agree element for element, making "the
    # arm decoded the tokens the reference decoded" an assertion rather than a coincidence.
    #
    # **And the `K` ids must differ**, or that assertion is satisfiable by an arm that decoded step 1
    # and then re-consumed its own first token forever. `MODEL_DECODE_RESEEDED_ROWS` exists to make
    # them differ; this is the check that says so at the point the fixture is generated, so a later
    # geometry or weight change cannot silently restore the fixed point.
    assert len(set(consumed)) == len(consumed), \
        "the reference decode loop is degenerate: %r" % (consumed,)
    emit("model-decode-tokens.txt", "".join("%d\n" % i for i in consumed))

    # A transcript holding only the **prefill** graph. The arm skips the first graph, so every
    # oracle row is then missing and the run is `R6_ORACLE_MISSING` rather than a silent comparison
    # against the wrong graph — which is the failure this fixture exists to make visible.
    emit("model-decode-transcript-onegraph.txt", model_transcript(prefill_records, MODEL_TOKENS))

    # A transcript one graph short of what `STEPS = K` needs: prefill plus `K - 1` decode graphs. The
    # first `K - 1` steps compare normally and step `K` finds no graph `K + 1`, so the refusal names
    # the step it happened at rather than the run.
    emit("model-decode-transcript-short-for-steps.txt",
         model_transcript(prefill_records + [r for s in per_step[:-1] for r in s], MODEL_TOKENS))

    # A tolerance breach inside the **first decode** graph: one printed element of its `l_out-0`
    # moved by 0.0003, three times section 3.4's threshold. It is graph 2 and therefore step 1's, so
    # the case is refused at the first step whatever `STEPS` is.
    rows = lines.split("\n")
    marker = "common_debug_cb_eval:"
    hits = [i for i, line in enumerate(rows) if line.startswith(marker) and " l_out-0 = " in line]
    perturbed = list(rows)
    row = hits[1] + 3
    original = perturbed[row]
    first = original.index("[") + 1
    value = float(original[first:first + 12])
    perturbed[row] = original[:first] + ("%12.4f" % (value + 0.0003)) + original[first + 12:]
    emit("model-decode-transcript-perturbed.txt", "\n".join(perturbed))

    # `kq-0` of the first **decode** graph declaring a reduction width the operand does not name.
    kq_hits = [i for i, line in enumerate(rows) if line.startswith(marker) and " kq-0 = " in line]
    widened = list(rows)
    widened[kq_hits[1]] = widened[kq_hits[1]].replace(
        "= {%d, " % MODEL_KV_WIDTH, "= {%d, " % (MODEL_KV_WIDTH - 1))
    emit("model-decode-transcript-kv-width.txt", "\n".join(widened))

    # R6-KV-PERSIST section 4.6. The known-good container and one file per mutation. The geometry
    # text is the **exact bytes** the corpus writes to `geometry.json`, because that is what the
    # arm digests: a digest of a re-serialization would bind the container to this generator's
    # formatter rather than to the document the caller supplied.
    geometry_text = json.dumps(geometry_document(g), separators=(",", ":")) + "\n"
    source_record_offset = layout["source_record_offset"]

    def container(mutation=None, text=geometry_text, tokens=MODEL_TOKENS):
        return kv_container(g, planes, tokens, prefill_logits, MODEL_KV_WIDTH, pack_bytes,
                            source_record_offset, text, mutation=mutation)

    emit("model-kv-good.akvp", container())
    for mutation in KV_MUTATIONS:
        emit("model-kv-%s.akvp" % mutation, container(mutation))
    # `ds-kv-tokens-count` is **not** a byte patch, and the canonical-layout rule is why: shortening
    # `token_count` in the header without moving the three regions after it produces a container no
    # layout can explain, which section 2.3.1's rule now refuses at L7 before the token count is ever
    # compared. The honest defect is a perfectly well-formed container for a **shorter prompt**, and
    # that is what this emits -- refused at L12 because the run asked for three ids and the file
    # holds two.
    emit("model-kv-tokens-count.akvp", container(tokens=MODEL_TOKENS[:2]))
    # `ds-kv-identity-geometry`'s honest form: a container written against a **different geometry
    # document**, so the refusal is a real second identity rather than a flipped byte. Both are
    # emitted, because the flipped byte proves the field is read and this proves the field means
    # what it says.
    emit("model-kv-foreign-geometry.akvp", container(text=geometry_text + " "))

    # `ds-kv-too-large`. Section 2.5's bound is 512 MiB and the synthetic model's plane is 512 B, so
    # the only way to reach `R6_KV_TOO_LARGE` from a hosted corpus is a geometry whose declared
    # depth makes the plane unpersistable: `4097 * 2 * 4096 * 1 * 4 * 4` is 537,001,984, which is 131,072
    # bytes above `MAX_KV_PLANE_BYTES`. Step 6a fires **before the pack is opened**, so no pack
    # needs to describe this model -- which is the point: a caller who asks for an unpersistable
    # configuration learns it in milliseconds.
    huge = json.loads(json.dumps(geometry_document(g)))
    huge["model"]["n_layer"] = 4097
    emit("geometry-kv-too-large.json", json.dumps(huge, separators=(",", ":")) + "\n")


# =============================================================================================
# R6-KV-PERSIST (`docs/specs/r6-kv-persist.md` sections 2.3 and 4.6)
#
# A **third** implementation of the `akvp` v1 container. The arm writes containers, the independent
# reader reads them, and this generator writes them **from the specification without reading
# either** -- which is what makes the format a shared contract rather than the arm's habit.
# `ds-kv-load-fixture` loads a container produced here and must decode the same ids as
# `ds-kv-load-ok`.
#
# It also produces the mutation corpus of section 5.2: one byte-level defect per named refusal,
# applied to a known-good container, so that every `R6_KV_*` code is reached from a malformed file
# rather than from a forced compute failure -- which is why this capability needs no new forced shim
# build.
# =============================================================================================

KV_MAGIC = b"AKVP"
KV_FORMAT_VERSION = 1
KV_HEADER_BYTES = 192
KV_IDENTITY_RECORD_BYTES = 192
KV_PLANE_ALIGN = 4096
KV_REGION_ALIGN = 8
KV_ENDIAN_PROBE = 0x0102030405060708
KV_DOCUMENT_SCHEMA_VERSION = 3
# Section 2.5's three bounds, restated here from the document rather than read from
# `src/kv_plane.align`, because this generator is a third implementation of the format.
KV_MAX_PLANE_BYTES = 536870912
KV_MAX_LOGITS_BYTES = 16777216


def kv_plan(g, width, token_count, n_vocab):
    """Section 2.3's region arithmetic, from the document rather than from `src/kv_plane.align`."""
    token_stream_offset = KV_HEADER_BYTES
    token_stream_bytes = token_count * 4
    identity_offset = align_up(token_stream_offset + token_stream_bytes, KV_REGION_ALIGN)
    logits_offset = align_up(identity_offset + KV_IDENTITY_RECORD_BYTES, KV_REGION_ALIGN)
    logits_bytes = n_vocab * 4
    plane_offset = align_up(logits_offset + logits_bytes, KV_PLANE_ALIGN)
    plane_bytes = g["n_layer"] * 2 * width * g["n_head_kv"] * g["head_dim"] * 4
    return {
        "token_stream_offset": token_stream_offset,
        "token_stream_bytes": token_stream_bytes,
        "identity_offset": identity_offset,
        "logits_offset": logits_offset,
        "logits_bytes": logits_bytes,
        "plane_offset": plane_offset,
        "plane_bytes": plane_bytes,
        "total_bytes": plane_offset + plane_bytes,
    }


def kv_plane_image(g, planes, width, columns):
    """Section 2.3.4, plane layout version 1: layer-major, K then V per layer, each tensor
    column-major over `width` columns with `head_dim` fastest, and every column at or above
    `columns` left zero."""
    head_dim, n_head_kv = g["head_dim"], g["n_head_kv"]
    stride = width * n_head_kv * head_dim * 4
    raw = bytearray(g["n_layer"] * 2 * stride)
    for layer in range(g["n_layer"]):
        for tensor_index, tensor in enumerate(planes[layer]):
            base = stride * (2 * layer + tensor_index)
            for column in range(columns):
                for head in range(n_head_kv):
                    for lane in range(head_dim):
                        value = tensor.data[lane + head_dim * (head + n_head_kv * column)]
                        at = base + (lane + head_dim * (head + n_head_kv * column)) * 4
                        struct.pack_into("<f", raw, at, value)
    return bytes(raw)


def kv_container(g, planes, tokens, logits, width, pack_bytes, pack_source_record_offset,
                 geometry_text, mutation=None):
    """One `akvp` v1 container, and one byte-level defect when `mutation` names it."""
    token_count = len(tokens)
    n_vocab = logits.count()
    plan = kv_plan(g, width, token_count, n_vocab)
    prefill_argmax = max(range(n_vocab), key=lambda i: logits.data[i])

    ids = b"".join(struct.pack("<I", i) for i in tokens)
    logits_image = struct.pack("<%df" % n_vocab, *logits.data)
    plane_image = kv_plane_image(g, planes, width, token_count)

    pack_digest = pack_bytes[pack_source_record_offset + 48:pack_source_record_offset + 80]
    pack_total_bytes = struct.unpack_from("<Q", pack_bytes, 24)[0]
    geometry_digest = hashlib.sha256(geometry_text.encode("utf-8")).digest()

    raw = bytearray(plan["total_bytes"])
    raw[0:4] = KV_MAGIC
    struct.pack_into("<IIIIIII", raw, 4, KV_FORMAT_VERSION, KV_HEADER_BYTES,
                     KV_IDENTITY_RECORD_BYTES, 0, 1, 0, KV_PLANE_ALIGN)
    struct.pack_into("<QQQQQQQQQ", raw, 32, KV_ENDIAN_PROBE, plan["total_bytes"],
                     plan["token_stream_offset"], plan["token_stream_bytes"],
                     plan["identity_offset"], plan["logits_offset"], plan["logits_bytes"],
                     plan["plane_offset"], plan["plane_bytes"])
    struct.pack_into("<IIIIIII", raw, 104, g["n_layer"], g["n_head_kv"], g["head_dim"], width,
                     token_count, token_count, n_vocab)
    struct.pack_into("<iII", raw, 132, prefill_argmax, KV_DOCUMENT_SCHEMA_VERSION, 0)

    raw[plan["token_stream_offset"]:plan["token_stream_offset"] + len(ids)] = ids
    identity = plan["identity_offset"]
    raw[identity:identity + 32] = pack_digest
    raw[identity + 32:identity + 64] = geometry_digest
    raw[identity + 64:identity + 96] = hashlib.sha256(ids).digest()
    raw[identity + 96:identity + 128] = hashlib.sha256(logits_image).digest()
    raw[identity + 128:identity + 160] = hashlib.sha256(plane_image).digest()
    struct.pack_into("<Q", raw, identity + 160, pack_total_bytes)
    raw[plan["logits_offset"]:plan["logits_offset"] + len(logits_image)] = logits_image
    raw[plan["plane_offset"]:plan["plane_offset"] + len(plane_image)] = plane_image

    if mutation is None:
        return bytes(raw)
    return kv_mutate(raw, plan, mutation, g, width, geometry_digest)


def kv_mutate(raw, plan, mutation, g, width, geometry_digest):
    """One defect per named case of section 5.2. Each is the **smallest** edit that reaches its own
    refusal: a mutation that tripped an earlier check would assert the earlier check twice and the
    named one never."""
    identity = plan["identity_offset"]
    if mutation == "truncated-header":
        return bytes(raw[:100])
    if mutation == "magic":
        raw[0] = raw[0] ^ 0xFF
    elif mutation == "version":
        struct.pack_into("<I", raw, 4, 2)
    elif mutation == "header-bytes":
        struct.pack_into("<I", raw, 8, 128)
    elif mutation == "identity-record-bytes":
        struct.pack_into("<I", raw, 12, 128)
    elif mutation == "element-type":
        struct.pack_into("<I", raw, 16, 1)
    elif mutation == "layout-version":
        struct.pack_into("<I", raw, 20, 2)
    elif mutation == "flags":
        struct.pack_into("<I", raw, 24, 1)
    elif mutation == "plane-align":
        struct.pack_into("<I", raw, 28, 3)
    elif mutation == "endian-probe":
        struct.pack_into("<Q", raw, 32, 0x0807060504030201)
    elif mutation == "doc-schema":
        struct.pack_into("<I", raw, 136, 2)
    elif mutation == "reserved":
        raw[160] = 1
    elif mutation == "reserved-u32":
        struct.pack_into("<I", raw, 140, 1)
    elif mutation == "identity-reserved":
        raw[identity + 175] = 1
    elif mutation == "high-bit":
        # `plane_offset` with bit 63 set: refused at L5, before any offset it would address.
        struct.pack_into("<Q", raw, 88, plan["plane_offset"] | (1 << 63))
    elif mutation == "truncated-total":
        return bytes(raw[:len(raw) - 64])
    elif mutation == "region-overlap":
        # The identity record moved back into the token stream. Containment and alignment still
        # hold, so disjointness is the check that fires.
        struct.pack_into("<Q", raw, 64, plan["token_stream_offset"])
    elif mutation == "region-outside":
        struct.pack_into("<Q", raw, 88, plan["total_bytes"])
    elif mutation == "region-misaligned":
        # **Minus** eight, not plus: a forward shift would leave the plane past `total_bytes` and
        # assert containment instead of alignment.
        struct.pack_into("<Q", raw, 88, plan["plane_offset"] - 8)
    elif mutation == "plane-not-last":
        struct.pack_into("<Q", raw, 96, plan["plane_bytes"] - 128)
    elif mutation == "region-noncanonical":
        # A layout that satisfies containment, alignment, disjointness, and "the plane is last" and
        # is still **not** section 2.3.1's: the plane pushed one whole `plane_align` forward, with
        # the gap left zero so the padding rule cannot be what refuses it. Before the canonical rule
        # was enforced on both sides the arm accepted this file and the independent reader refused
        # it, which is a format with two meanings.
        gap = KV_PLANE_ALIGN
        shifted = bytearray(raw[:plan["plane_offset"]]) + bytearray(gap) \
            + bytearray(raw[plan["plane_offset"]:])
        struct.pack_into("<Q", shifted, 88, plan["plane_offset"] + gap)
        struct.pack_into("<Q", shifted, 40, plan["total_bytes"] + gap)
        return bytes(shifted)
    elif mutation == "padding-nonzero":
        # One byte of the `logits -> plane` padding made non-zero. **No digest covers the gaps**, so
        # this is the defect that shows the padding rule is enforced rather than implied: the five
        # digests all still recompute correctly.
        raw[plan["logits_offset"] + plan["logits_bytes"] + 3] = 1
    elif mutation == "longer-total":
        # The other side of `truncated-total`: a file **longer** than its own `total_bytes`. The
        # header is untouched, so the only disagreement is the length.
        return bytes(raw) + bytes(64)
    elif mutation == "plane-too-large":
        # Section 2.5's bound, declared rather than materialized: the header claims a plane one byte
        # above `MAX_KV_PLANE_BYTES`, which is refused before the claim is compared against the
        # file's own length. Materializing a 512 MiB fixture to reach the same refusal would cost
        # the corpus half a gigabyte and prove nothing more.
        struct.pack_into("<Q", raw, 96, KV_MAX_PLANE_BYTES + 1)
    elif mutation == "logits-too-large":
        struct.pack_into("<Q", raw, 80, KV_MAX_LOGITS_BYTES + 4)
        struct.pack_into("<I", raw, 128, (KV_MAX_LOGITS_BYTES + 4) // 4)
    elif mutation == "geometry-layers":
        struct.pack_into("<I", raw, 104, g["n_layer"] + 1)
    elif mutation == "geometry-head-dim":
        struct.pack_into("<I", raw, 112, g["head_dim"] * 2)
    elif mutation == "geometry-plane-bytes":
        # The plane region genuinely shortened, so `plane_offset + plane_bytes == total_bytes` still
        # holds and L8's derivation from the geometry integers is what refuses it.
        shrunk = plan["plane_bytes"] - 128
        struct.pack_into("<Q", raw, 96, shrunk)
        struct.pack_into("<Q", raw, 40, plan["plane_offset"] + shrunk)
        return bytes(raw[:plan["plane_offset"] + shrunk])
    elif mutation == "identity-pack":
        raw[identity] = raw[identity] ^ 0xFF
    elif mutation == "identity-pack-size":
        struct.pack_into("<Q", raw, identity + 160,
                         struct.unpack_from("<Q", raw, identity + 160)[0] + 1)
    elif mutation == "identity-geometry":
        raw[identity + 32] = raw[identity + 32] ^ 0xFF
    elif mutation == "tokens-id":
        at = plan["token_stream_offset"] + 8
        struct.pack_into("<I", raw, at, struct.unpack_from("<I", raw, at)[0] + 1)
        raw[identity + 64:identity + 96] = hashlib.sha256(
            bytes(raw[plan["token_stream_offset"]:
                      plan["token_stream_offset"] + plan["token_stream_bytes"]])).digest()
    elif mutation == "digest-tokens":
        raw[identity + 64] = raw[identity + 64] ^ 0xFF
    elif mutation == "npast":
        struct.pack_into("<I", raw, 120, 2)
    elif mutation == "argmax":
        struct.pack_into("<i", raw, 132,
                         (struct.unpack_from("<i", raw, 132)[0] + 1) % g["n_vocab"])
    elif mutation == "digest-logits":
        raw[plan["logits_offset"]] = raw[plan["logits_offset"]] ^ 0xFF
    elif mutation == "digest-plane":
        raw[plan["plane_offset"]] = raw[plan["plane_offset"]] ^ 0xFF
    elif mutation == "zero-tail":
        # A column at or above `columns_persisted` made non-zero. The arm refuses it through the
        # plane digest and the independent reader through its own zero-tail invariant, which is the
        # one row where the two refuse for **different reasons** -- and therefore the row that
        # proves the reader is not a transcription of the arm.
        stride = width * g["n_head_kv"] * g["head_dim"] * 4
        column_bytes = g["n_head_kv"] * g["head_dim"] * 4
        at = plan["plane_offset"] + (width - 1) * column_bytes
        struct.pack_into("<f", raw, at, 1.5)
        assert stride > 0 and at < plan["plane_offset"] + plan["plane_bytes"]
    elif mutation == "magic-and-truncated":
        raw[0] = raw[0] ^ 0xFF
        return bytes(raw[:100])
    else:
        raise SystemExit("layer_forward_fixture: unknown kv mutation %r" % mutation)
    return bytes(raw)


# Every mutation this generator emits, with the file name suffix each one is written under. The
# smoke consumes them by name; a mutation with no case and a case with no mutation are both
# failures the two lists make visible.
KV_MUTATIONS = [
    "truncated-header", "magic", "version", "header-bytes", "identity-record-bytes",
    "element-type", "layout-version", "flags", "plane-align", "endian-probe", "doc-schema",
    "reserved", "reserved-u32", "identity-reserved", "high-bit", "truncated-total",
    "region-overlap", "region-outside", "region-misaligned", "plane-not-last", "geometry-layers",
    "geometry-head-dim", "geometry-plane-bytes", "identity-pack", "identity-pack-size",
    "identity-geometry", "tokens-id", "digest-tokens", "npast", "argmax",
    "digest-logits", "digest-plane", "zero-tail", "magic-and-truncated",
    "region-noncanonical", "padding-nonzero", "longer-total", "plane-too-large",
    "logits-too-large",
]


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
    tensor = Tensor([dim0, dim1], weight_values(seed, dim0 * dim1))
    if role == "token_embd" and expert is None:
        # `MOE_MODEL_DECODE_RESEEDED_ROWS`' reason, in one place so the pack and the reference
        # forward cannot disagree: both read this function and neither holds a copy of the row.
        for row in MOE_MODEL_DECODE_RESEEDED_ROWS:
            tensor.data[row * dim0:(row + 1) * dim0] = weight_values("%s@%d" % (role, row), dim0)
    return tensor


def soft_max_plain(a):
    """`ggml_soft_max(ctx, a)`: unit scale, **no mask**, and no renormalization anywhere."""
    zero = Tensor([a.ne[0], 1], [0.0] * a.ne[0])
    return soft_max_ext(a, zero, 1.0)


def argsort_desc(a):
    """`ggml_argsort(..., GGML_SORT_ORDER_DESC)`: the permutation of indices, not the values.

    This matches the stub shim's stable insertion sort exactly, and it is deliberately *not* a
    claim about ggml: ggml 0.21.0's CPU `argsort` is a `std::sort` over the index array, whose tie
    order above the introsort insertion threshold is unspecified. No corpus row holds an exact tie.
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




# =============================================================================================
# R5E-MOE-MODEL-PREFILL (`docs/specs/r5e-moe-model-prefill.md` section 5.1)
#
# The same generator, extended to a whole **two-layer routed olmoe model**: twenty-two blocks — one
# embedding `WeightBlock`, then per layer an `AttentionBlock`, a `RouterBlock`, and eight
# `ExpertBlock`s with `slice_index` `0..7` and `slice_count` 8, then the head `WeightBlock` — and a
# pure-Python forward pass over the entire routed prefill: the embedding gather, both layers'
# routing decisions, the narrowing inside the last one, and the head.
#
# **A second implementation computing the same routed model is what makes the `IDENTICAL` logits
# verdict stub-reachable at all**, and it is also what makes the id-table swap a real test rather
# than a shape check: the Python reference gathers probabilities by **global** id, so a build that
# passed the compacted ids to `get_rows` produces a document that differs at `ffn_moe_weights` in
# both layers while `ffn_moe_gate` still agrees.
#
# At `n_expert_used = 3` the router's slot axis is 3, which is `<= 6`, so this corpus is the **only**
# place the routing oracle's full element-wise print coverage is reachable across a whole model: all
# twelve ids are compared, where the real model prints 546 of 728.
#
# The geometry keeps `n_vocab` (32) distinct from `n_ff_exp` (16), from `n_expert` (8), and from
# `n_head * head_dim` (8), so a fixture whose dimensions collide cannot hide a transposed head or a
# confused expert axis.
# =============================================================================================

GEOMETRY_MOE_MODEL = GEOMETRY_MOE
# Chosen by sweeping the generator's own forward. `docs/specs/r5e-moe-model-prefill.md` section 5.1
# proposes `[3, 17, 5]`; that list routes **all eight** experts at layer 0, which makes
# `U == n_expert`, `compact_ids == expert_ids`, and the layer's residency fraction 1 — the three
# properties this corpus exists to exercise. `[3, 17, 16]` routes six of eight at layer 0 with three
# distinct per-token slot orders and three of eight at the narrowed layer 1, so `U < n_expert` at
# both depths, the compact ids differ from the global ids, and the union curve is a real fraction.
MOE_MODEL_TOKENS = [3, 17, 16]
MOE_MODEL_KV_WIDTH = 8

# R6-OLMOE-DECODE's decode corpus. `K` is 3 and not 16 on purpose, R6-STEP-N's reason unchanged: the
# loop's correctness is a property of the **second** iteration — the first step reads a plane the
# prefill wrote and the second reads one a step wrote — and sixteen synthetic steps buy nothing the
# third does not.
MOE_DECODE_STEPS = 3

# `MODEL_DECODE_RESEEDED_ROWS`' fixed-point hazard, met again on the routed model — and **measured
# to be absent**, which is why this tuple is empty and the routed pack is byte-unchanged.
#
# The hazard is real and the check for it is not optional: if the decoded chain were a fixed point, a
# loop that fed step 1's token to every later step would satisfy every per-step assertion the seventh
# smoke block makes. The dense corpus needed one re-seeded row to break it; this one does not, and
# the chain is `6 -> 9 -> 16` on the unmodified generator. `write_moe_decode_corpus` asserts that at
# the point the fixture is generated, so a later geometry or weight change cannot silently restore
# the fixed point — and the lever to fix it is here, empty, rather than invented at that moment.
#
# Keeping it empty is what makes `moe-model-pack.alignpack` and every other pre-existing corpus file
# byte-identical to its pre-R6-OLMOE-DECODE self, which is in turn what makes "the two MoE goldens
# move by exactly the rows section 6.3 predicts" a property of the diff rather than a hope.
MOE_MODEL_DECODE_RESEEDED_ROWS = ()


def moe_model_head_dims(role, g):
    return {
        "output_norm": (g["n_embd"], 1),
        "output": (g["n_embd"], g["n_vocab"]),
    }[role]


def moe_model_head_tensor(role, g):
    dim0, dim1 = moe_model_head_dims(role, g)
    return Tensor([dim0, dim1], weight_values(role, dim0 * dim1))


def moe_model_layer(cur, dense, experts, g, tokens, width, mask, last, records, layer,
                    planes=None):
    """One routed layer of section 3.6's thirty-five-row phase-A table and its phase-B table.

    `planes` is R6-OLMOE-DECODE's addition and its only one: when a list is supplied, this layer's
    post-QK-norm post-RoPE K and its reshaped V are appended to it, which is exactly the pair
    `layer_olmoe.MM_K_ROW` and `MM_V_ROW` name and exactly what the arm writes into its plane."""
    t = len(tokens)
    head_dim, n_head = g["head_dim"], g["n_head"]
    n_embd, n_expert, n_used = g["n_embd"], g["n_expert"], g["n_expert_used"]
    eps, freq_base = g["rms_eps"], g["rope_freq_base"]
    positions = list(range(t))
    suffix = "-%d" % layer

    norm_in = rms_norm(cur, eps)
    attn_norm = broadcast(norm_in, dense["attn_norm"], lambda x, y: x * y)
    q_pre = mul_mat(dense["attn_q"], attn_norm)
    norm_q = rms_norm(q_pre, eps)
    q_normed = broadcast(norm_q, dense["attn_q_norm"], lambda x, y: x * y)
    q_rope = rope_neox(reshape(q_normed, [head_dim, n_head, t]), positions,
                       g["rope_dim_count"], freq_base)
    k_pre = mul_mat(dense["attn_k"], attn_norm)
    norm_k = rms_norm(k_pre, eps)
    k_normed = broadcast(norm_k, dense["attn_k_norm"], lambda x, y: x * y)
    k_rope = rope_neox(reshape(k_normed, [head_dim, n_head, t]), positions,
                       g["rope_dim_count"], freq_base)
    v_cur = mul_mat(dense["attn_v"], attn_norm)
    v3 = reshape(v_cur, [head_dim, n_head, t])
    kp = permute(k_rope, [0, 2, 1, 3])
    qp = permute(q_rope, [0, 2, 1, 3])
    # The three `node_when == 2` rows: `cont` and `pad` on K, `pad` on V. `ggml_pad` writes the
    # source at the start of each padded axis and the mask's extra columns are `-inf`, so the padded
    # lanes contribute nothing but the f32 reduction length matches llama.cpp's.
    if width > t:
        kp = pad_tensor(cont(kp, [head_dim, t, n_head]), 0, width - t, 0, 0)
    kq = mul_mat(kp, qp)
    kqs = soft_max_ext(kq, mask, f32(1.0 / math.sqrt(head_dim)))
    vt = cont(permute(v3, [1, 2, 0, 3]), [t, head_dim, n_head])
    if width > t:
        vt = pad_tensor(vt, width - t, 0, 0, 0)
    kqv = mul_mat(vt, kqs)
    kqv_out = cont(permute(kqv, [0, 2, 1, 3]), [n_embd, t, 1])
    attn_out = mul_mat(dense["attn_output"], kqv_out)
    # The narrowing: a pair of `GET_ROWS` inside the last layer, after the attention output
    # projection, on **both** residual branches — and therefore *before* the last layer's router.
    residual = cur
    narrowed = attn_out
    if last:
        narrowed = get_rows(attn_out, [t - 1])
        residual = get_rows(cur, [t - 1])
    ffn_inp = broadcast(narrowed, residual, lambda x, y: x + y)
    norm_ffn = rms_norm(ffn_inp, eps)
    ffn_norm = broadcast(norm_ffn, dense["ffn_norm"], lambda x, y: x * y)
    t_out = ffn_norm.ne[1]

    logits = mul_mat(dense["router"], ffn_norm)
    probs = soft_max_plain(logits)
    argsort = argsort_desc(probs)
    topk = [int(argsort.data[token * n_expert + slot])
            for token in range(t_out) for slot in range(n_used)]
    topk_tensor = Tensor([n_used, t_out], [float(v) for v in topk])
    probs_r = reshape(probs, [1, n_expert, t_out])
    weights = get_rows_3d(probs_r, topk_tensor)
    ffn_norm_r = reshape(ffn_norm, [n_embd, 1, t_out])
    gate = mul_mat_id(experts["ffn_gate_exps"], ffn_norm_r, topk, n_used)
    up = mul_mat_id(experts["ffn_up_exps"], ffn_norm_r, topk, n_used)
    swiglu = swiglu_split(gate, up)
    down = mul_mat_id(experts["ffn_down_exps"], swiglu, topk, n_used)
    weighted = broadcast(down, weights, lambda x, y: x * y)
    views = [slot_view(weighted, slot) for slot in range(n_used)]
    moe_out = views[0]
    for slot in range(1, n_used):
        moe_out = broadcast(moe_out, views[slot], lambda x, y: x + y)
    l_out = broadcast(moe_out, ffn_inp, lambda x, y: x + y)

    if planes is not None:
        planes.append((k_rope, v3))

    records.extend([
        ("norm" + suffix, "RMS_NORM", "embd" if layer == 0 else "l_out-%d" % (layer - 1), norm_in),
        ("attn_norm" + suffix, "MUL", "norm" + suffix, attn_norm),
        ("Qcur" + suffix, "MUL_MAT", "blk.%d.attn_q.weight" % layer, q_pre),
        ("norm" + suffix, "RMS_NORM", "Qcur" + suffix, norm_q),
        ("Qcur_normed" + suffix, "MUL", "norm" + suffix, q_normed),
        ("Qcur" + suffix, "ROPE", "Qcur_normed%s (reshaped)" % suffix, q_rope),
        ("Kcur" + suffix, "MUL_MAT", "blk.%d.attn_k.weight" % layer, k_pre),
        ("norm" + suffix, "RMS_NORM", "Kcur" + suffix, norm_k),
        ("Kcur_normed" + suffix, "MUL", "norm" + suffix, k_normed),
        ("Kcur" + suffix, "ROPE", "Kcur_normed%s (reshaped)" % suffix, k_rope),
        ("Vcur" + suffix, "MUL_MAT", "blk.%d.attn_v.weight" % layer, v_cur),
        ("kq" + suffix, "MUL_MAT", "Kcur%s (permuted)" % suffix, kq),
        ("kq_soft_max" + suffix, "SOFT_MAX", "kq" + suffix, kqs),
        ("kqv" + suffix, "MUL_MAT", "Vcur%s (transposed)" % suffix, kqv),
        ("kqv_out" + suffix, "CONT", "kqv%s (permuted)" % suffix, kqv_out),
        ("node_%d" % (200 + layer), "MUL_MAT", "blk.%d.attn_output.weight" % layer, attn_out),
        ("ffn_inp" + suffix, "ADD", "node_%d" % (200 + layer), ffn_inp),
        ("norm" + suffix, "RMS_NORM", "ffn_inp" + suffix, norm_ffn),
        ("ffn_norm" + suffix, "MUL", "norm" + suffix, ffn_norm),
        ("ffn_moe_logits" + suffix, "MUL_MAT", "blk.%d.ffn_gate_inp.weight" % layer, logits),
        ("ffn_moe_probs" + suffix, "SOFT_MAX", "ffn_moe_logits" + suffix, probs),
        ("ffn_moe_argsort" + suffix, "ARGSORT", "ffn_moe_probs" + suffix, argsort),
        ("ffn_moe_topk" + suffix, "VIEW", "ffn_moe_argsort" + suffix, topk_tensor),
        ("ffn_moe_weights" + suffix, "GET_ROWS", "ffn_moe_probs%s (reshaped)" % suffix, weights),
        ("ffn_moe_gate" + suffix, "MUL_MAT_ID", "blk.%d.ffn_gate_exps.weight" % layer, gate),
        ("ffn_moe_up" + suffix, "MUL_MAT_ID", "blk.%d.ffn_up_exps.weight" % layer, up),
        ("ffn_moe_swiglu" + suffix, "SWIGLU", "ffn_moe_gate" + suffix, swiglu),
        ("ffn_moe_down" + suffix, "MUL_MAT_ID", "blk.%d.ffn_down_exps.weight" % layer, down),
        ("ffn_moe_weighted" + suffix, "MUL", "ffn_moe_down" + suffix, weighted),
        ("ffn_moe_out" + suffix, "ADD", "node_%d" % (300 + layer), moe_out),
        ("l_out" + suffix, "ADD", "ffn_moe_out" + suffix, l_out),
    ])
    return l_out, topk


def moe_model_forward(embed, layers, experts, head, g, tokens, width, planes=None):
    """The whole routed prefill: one embedding graph, two layers of two graphs, and the head."""
    t = len(tokens)
    mask = Tensor([width, t], [0.0 if c <= r else float("-inf")
                               for r in range(t) for c in range(width)])
    records = []
    embd = get_rows(embed, tokens)
    records.append(("embd", "GET_ROWS", "token_embd.weight", embd))
    cur = embd
    routings = []
    for layer in range(g["n_layer"]):
        cur, topk = moe_model_layer(cur, layers[layer], experts[layer], g, tokens, width, mask,
                                    layer == g["n_layer"] - 1, records, layer, planes)
        routings.append(topk)
    norm = rms_norm(cur, g["rms_eps"])
    result_norm = broadcast(norm, head["output_norm"], lambda x, y: x * y)
    result_output = mul_mat(head["output"], result_norm)
    records.append(("norm", "RMS_NORM", "l_out-%d" % (g["n_layer"] - 1), norm))
    records.append(("result_norm", "MUL", "norm", result_norm))
    records.append(("result_output", "MUL_MAT", "output.weight", result_output))
    return records, routings, result_output


def moe_model_members(g):
    """`(tag, Member)` pairs in the container's own order: embedding, then per layer the attention
    block, the router block and eight expert blocks, then the head."""
    out = []
    out.append(("embed", Member("token_embd.weight", "token_embd", 12, KIND_WEIGHT,
                                *moe_dense_dims("token_embd", g),
                                moe_tensor("token_embd", -1, g).data)))
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
    out.append(("head", Member("output_norm.weight", "output_norm", ROLE_OUTPUT_NORM, KIND_WEIGHT,
                               *moe_model_head_dims("output_norm", g),
                               moe_model_head_tensor("output_norm", g).data, n_dims=1)))
    out.append(("head", Member("output.weight", "output", ROLE_OUTPUT, KIND_WEIGHT,
                               *moe_model_head_dims("output", g),
                               moe_model_head_tensor("output", g).data)))
    return out


def moe_model_blocks(members, g, drop_expert=None, drop_router_layer=None,
                     duplicate_embedding=False, drop_head=False, drop_role=None,
                     drop_expert_role=None):
    grouped = {}
    for tag, member in members:
        grouped.setdefault(tag, []).append(member)
    blocks = [Block(KIND_WEIGHT, -1, list(grouped["embed"]))]
    if duplicate_embedding:
        # Two blocks answering to `(kind 0, layer -1)` and **both** carrying `role_id` 12: the
        # ambiguity section 3.4 refuses. Fresh records, because `build` assigns each member exactly
        # one `pack_offset`.
        blocks.append(Block(KIND_WEIGHT, -1,
                            [Member(m.name, m.role, m.role_id, m.block_kind, m.dim0, m.dim1,
                                    m.values, n_dims=m.n_dims, dim2=m.dim2, dim3=m.dim3,
                                    slice_index=m.slice_index, slice_count=m.slice_count)
                             for m in grouped["embed"]]))
    for layer in range(g["n_layer"]):
        rows = grouped["layer%d" % layer]
        blocks.append(Block(KIND_ATTENTION, layer,
                            [m for m in rows if m.block_kind == KIND_ATTENTION
                             and not (layer == 1 and m.role == drop_role)]))
        if layer != drop_router_layer:
            blocks.append(Block(KIND_ROUTER, layer,
                                [m for m in rows if m.block_kind == KIND_ROUTER]))
        for expert in range(g["n_expert"]):
            if layer == 1 and expert == drop_expert:
                continue
            claims = list(grouped["expert%d_%d" % (layer, expert)])
            if layer == 1 and drop_expert_role is not None and expert == drop_expert_role[0]:
                claims = [m for m in claims if m.role != drop_expert_role[1]]
            blocks.append(Block(KIND_EXPERT, layer, claims, expert=expert))
    if not drop_head:
        blocks.append(Block(KIND_WEIGHT, -1, list(grouped["head"])))
    return blocks


def moe_model_geometry_document(g):
    document = moe_geometry_document(g)
    document["path"] = "synthetic-olmoe-model.gguf"
    return document


def write_moe_model_corpus(directory, emit):
    """Section 5.1's whole routed-model corpus: the base pack, one mutation per code the arm can
    reach hosted, the transcript at the reconciliation width, and the two logits blobs the fourth
    oracle compares against."""
    g = GEOMETRY_MOE_MODEL
    members = moe_model_members(g)
    base, layout = build(moe_model_blocks(members, g))
    emit("moe-model-pack.alignpack", base)

    # `R5_ALIGNMENT`. `block_align = 1` packs the member windows tight, but at this geometry every
    # dense member is a whole number of 32-byte rows, so tightness alone cannot put one off a
    # `TENSOR_ALIGNMENT` boundary. Halving layer 0's `attn_norm` declared `nbytes` makes every later
    # window offset in that layer `16 mod 32`. The dims are untouched, which is what keeps the fault
    # an *alignment* fault and not a shape one, and `graph_alignment` runs before `graph_weights`.
    tight, tight_layout = build(moe_model_blocks(moe_model_members(g), g),
                                block_align=1, member_align=1)
    emit("moe-model-pack-tight.alignpack",
         patch(tight, member_field(tight_layout, 1, 24), "<Q", 16))

    no_head, _ = build(moe_model_blocks(moe_model_members(g), g, drop_head=True))
    emit("moe-model-pack-no-head.alignpack", no_head)

    ambiguous, _ = build(moe_model_blocks(moe_model_members(g), g, duplicate_embedding=True))
    emit("moe-model-pack-ambiguous.alignpack", ambiguous)

    coverage, _ = build(moe_model_blocks(moe_model_members(g), g, drop_router_layer=1))
    emit("moe-model-pack-coverage.alignpack", coverage)

    no_expert, _ = build(moe_model_blocks(moe_model_members(g), g, drop_expert=5))
    emit("moe-model-pack-no-expert.alignpack", no_expert)

    no_qnorm, _ = build(moe_model_blocks(moe_model_members(g), g, drop_role="attn_q_norm"))
    emit("moe-model-pack-no-qnorm.alignpack", no_qnorm)

    role_missing, _ = build(moe_model_blocks(moe_model_members(g), g,
                                             drop_expert_role=(3, "ffn_up_exps")))
    emit("moe-model-pack-expert-role.alignpack", role_missing)

    # Member indices are arithmetic over the block skeleton, because `build` writes members in block
    # order: one embedding member, then per layer seven attention members, two router members, and
    # three claims per expert, then the head's two.
    dense_attention = len([r for r, _, k in MOE_DENSE_ROLES if k == KIND_ATTENTION])
    per_layer = dense_attention + 2 + g["n_expert"] * len(MOE_EXPERT_ROLES)
    layer1_base = 1 + per_layer
    router_index = layer1_base + dense_attention + 1
    claim_base = layer1_base + dense_attention + 2
    output_index = len(layout["members"]) - 1

    emit("moe-model-pack-router-shape.alignpack",
         patch(base, member_field(layout, router_index, 56), "<Q", g["n_expert"] - 1))
    emit("moe-model-pack-shape.alignpack",
         patch(base, member_field(layout, output_index, 56), "<Q", g["n_vocab"] - 1))
    emit("moe-model-pack-type.alignpack",
         patch(base, member_field(layout, output_index, 40), "<I", 4))
    # `R5_TYPE_UNSUPPORTED`: **every** expert of layer 1 declares a ggml type the operand table
    # does not carry, because one plane stride and one type serve the whole compact stack and a
    # single dissenting expert is caught by the plane-consistency check below instead.
    claim_type = base
    for expert in range(g["n_expert"]):
        claim_type = patch(
            claim_type,
            member_field(layout, claim_base + expert * len(MOE_EXPERT_ROLES), 40), "<I", 4)
    emit("moe-model-pack-claim-type.alignpack", claim_type)
    # `R5_SHAPE`: one expert of a layer disagreeing with its neighbours about a plane's ggml type.
    # `mul_mat_id` reads plane `u` at `u * plane` and one stride serves the whole stack, so a layer
    # whose experts disagree cannot be stacked at all.
    #
    # The mutated expert is a **later** one and the type it declares is a different but perfectly
    # **supported** one (F16 == 1) at an unchanged `nbytes`, which is R5D correction C12's shape,
    # not the unsupported-type shape of `claim-type` above: the plane still fills its region, the
    # stack is still exactly `U` planes, and only the encoding the stack was built from is wrong --
    # which no oracle can see, because all four read the stack the arm built. Patching expert 0 to
    # an unsupported type would be refused by `stage_claim_types` even if the plane-consistency
    # check were deleted, so it would not pin this check at all.
    emit("moe-model-pack-claim-type-mixed.alignpack",
         patch(base, member_field(layout, claim_base + len(MOE_EXPERT_ROLES), 40), "<I", 1))
    emit("moe-model-pack-slice.alignpack",
         patch(base, member_field(layout, claim_base, 84), "<i", g["n_expert"] - 1))
    emit("moe-model-pack-slice-index.alignpack",
         patch(base, member_field(layout, claim_base, 80), "<i", 1))
    emit("moe-model-pack-truncated.alignpack", base[:len(base) - 64])

    # The two window-budget probes of section 4.5, which measure the **order** of the guards rather
    # than the guards themselves. A member record declaring 2^40 bytes was the fixture section 4.5
    # promised for `R5_WINDOW_BUDGET` and `R5D_CLAIM_BUDGET`; it cannot reach either, because
    # `alignpack_read.member_at` refuses a member whose `[pack_offset, pack_offset + nbytes)` leaves
    # its block, and `open_pack` refuses a container whose `total_bytes` is not the file's own
    # length. Both codes are therefore fail-closed guards on an arithmetic no input can produce, and
    # these two cases are what keep that true (section 6, correction C17). Offset 24 is
    # `member.nbytes`.
    emit("moe-model-pack-dense-nbytes.alignpack",
         patch(base, member_field(layout, 1, 24), "<Q", 1 << 40))
    emit("moe-model-pack-claim-nbytes.alignpack",
         patch(base, member_field(layout, claim_base, 24), "<Q", 1 << 40))

    emit("moe-model-source.bin", source_image(layout))
    emit("moe-model-source-short.bin", b"\0")

    for name, document in moe_geometry_corpus(g):
        emit("moe-model-" + name[len("moe-"):] + ".json",
             json.dumps(document, separators=(",", ":")) + "\n")

    embed = moe_tensor("token_embd", -1, g)
    layers = [{role: moe_tensor(role, layer, g) for role, _, _ in MOE_DENSE_ROLES
               if role != "token_embd"} for layer in range(g["n_layer"])]
    experts = [{role: [moe_tensor(role, layer, g, expert=e) for e in range(g["n_expert"])]
                for role, _ in MOE_EXPERT_ROLES} for layer in range(g["n_layer"])]
    head = {"output_norm": moe_model_head_tensor("output_norm", g),
            "output": moe_model_head_tensor("output", g)}

    records, routings, logits = moe_model_forward(
        embed, layers, experts, head, g, MOE_MODEL_TOKENS, MOE_MODEL_KV_WIDTH)
    transcript = moe_transcript(records, MOE_MODEL_TOKENS)
    emit("moe-model-transcript.txt", transcript)
    emit("moe-model-logits.bin", struct.pack("<%df" % logits.count(), *logits.data))
    emit("moe-model-logits-short.bin", b"\0\0\0\0")
    emit("moe-model-logits-perturbed.bin",
         struct.pack("<%df" % logits.count(), *[f32(v + 1.0) for v in logits.data]))

    # The runtime-width forward, whose logits the `WITHIN` verdict is measured against. Section 2.8
    # is why it differs at all on a routed model: the reduction length changes the **routing**, not
    # only the arithmetic.
    runtime_records, runtime_routings, runtime_logits = moe_model_forward(
        embed, layers, experts, head, g, MOE_MODEL_TOKENS, len(MOE_MODEL_TOKENS))
    emit("moe-model-logits-runtime.bin",
         struct.pack("<%df" % runtime_logits.count(), *runtime_logits.data))

    def logits_with(*pairs):
        values = list(runtime_logits.data)
        for index, value in pairs:
            values[index] = value
        return struct.pack("<%df" % len(values), *values)

    emit("moe-model-logits-huge.bin", logits_with((0, 3.4e38), (1, -3.4e38)))
    emit("moe-model-logits-nan.bin", logits_with((3, float("nan"))))
    emit("moe-model-logits-neg-inf.bin", logits_with((0, float("-inf"))))

    # Section 3.7's order clause, made observable: the two adjacent top-ten ranks whose gap is
    # smallest have their **values** swapped, so the index *set* is unchanged, the argmax is
    # unchanged, and the order is not. The gap is asserted below the bound, so a `WITHIN` verdict
    # with `top_k_order_agreement < 10` is what the case observes.
    order = sorted(range(runtime_logits.count()), key=lambda i: -runtime_logits.data[i])[:10]
    best = min(range(1, 9),
               key=lambda r: abs(runtime_logits.data[order[r]] - runtime_logits.data[order[r + 1]]))
    swapped = list(runtime_logits.data)
    a, b = order[best], order[best + 1]
    swapped[a], swapped[b] = swapped[b], swapped[a]
    emit("moe-model-logits-order-swap.bin",
         struct.pack("<%df" % len(swapped), *swapped))

    # `R5_SOURCE_DIVERGED` must corrupt a claim the run actually **reads**: a plane no routing
    # decision names is never compared, so the mutation is placed on layer 0's first routed expert's
    # gate plane, which the schedule reads at `u = 0`.
    layer0_expert = sorted(set(routings[0]))[0]
    layer0_claim = 1 + dense_attention + 2 + layer0_expert * len(MOE_EXPERT_ROLES)
    emit("moe-model-source-diverged.bin", source_image(layout, corrupt=layer0_claim))

    lines = transcript.split("\n")

    def header_at(name, op):
        return next(i for i, line in enumerate(lines)
                    if line.startswith("common_debug_cb_eval:")
                    and (" %s = " % name) in line and ("%s(" % op) in line)

    # `R5_ORACLE_MISSING`, detail `layer[1]node[l_out]`: layer 1's `l_out-1` record is deleted.
    start = header_at("l_out-1", "ADD")
    end = next(i for i, line in enumerate(lines[start:], start) if line.startswith("    sum = "))
    emit("moe-model-transcript-missing.txt", "\n".join(lines[:start] + lines[end + 1:]) + "\n")

    # `R5_ORACLE_SHAPE`: `kq-1` declares a reduction width the operand does not name. This is the
    # check that stops the oracle from configuring the thing it verifies — and on a routed model
    # from silently changing which bytes the arm reads.
    kq = header_at("kq-1", "MUL_MAT")
    widened = list(lines)
    widened[kq] = widened[kq].replace("= {%d, " % MOE_MODEL_KV_WIDTH,
                                      "= {%d, " % (MOE_MODEL_KV_WIDTH - 1))
    emit("moe-model-transcript-kv-width.txt", "\n".join(widened) + "\n")

    # A tolerance breach at layer 0: one printed element of `l_out-0` moved by 0.0003, three times
    # section 3.7's threshold, so `oracle.verdict` becomes `FAIL` with `worst_layer` 0 while
    # `status` stays `ok` and the routing verdict stays `MATCH`.
    l_out0 = header_at("l_out-0", "ADD")
    perturbed = list(lines)
    row = l_out0 + 3
    original = perturbed[row]
    first = original.index("[") + 1
    value = float(original[first:first + 12])
    perturbed[row] = original[:first] + ("%12.4f" % (value + 0.0003)) + original[first + 12:]
    emit("moe-model-transcript-perturbed.txt", "\n".join(perturbed) + "\n")

    headers = [line for line in lines
               if line.startswith("common_debug_cb_eval:") or line.startswith("build: ")
               or line.startswith("number of input tokens")]
    emit("moe-model-transcript-headers.txt", "\n".join(headers) + "\n")

    novalues_start = header_at("l_out-1", "ADD")
    novalues_end = next(i for i, line in enumerate(lines[novalues_start:], novalues_start)
                        if line.startswith("    sum = "))
    emit("moe-model-transcript-novalues.txt",
         "\n".join(lines[:novalues_start + 1] + lines[novalues_end:]) + "\n")

    emit("moe-model-transcript-garbage.txt", bytes(range(256)) * 8)

    # Every `sum = ` line removed but the file's last. The element comparison still passes on every
    # node, so the run is `status: ok` with `oracle.verdict: PASS` — and thirty of oracle 2's
    # thirty-one block sums are simply gone, which before `oracle.sums_expected`/`sums_matched`
    # existed produced a document indistinguishable from a complete one (section 6, correction
    # C19). The final record keeps its sum because that line is what closes the last block: a
    # transcript with no sums at all ends inside a block and is `R5_TRANSCRIPT`, a grammar fault
    # `mm-transcript-garbage` already owns.
    sum_rows = [i for i, line in enumerate(lines) if line.startswith("    sum = ")]
    emit("moe-model-transcript-nosums.txt",
         "\n".join(line for i, line in enumerate(lines)
                   if i == sum_rows[-1] or not line.startswith("    sum = ")) + "\n")

    # `routing_oracle.verdict: MISMATCH` on a **successful** run: one printed expert id of
    # `ffn_moe_topk-1` is moved to another expert and the block sum moves with it, so both halves of
    # oracle 3 disagree while oracle 2 is still evaluated and reported.
    topk_header = header_at("ffn_moe_topk-1", "VIEW")
    id_row = topk_header + 3
    mismatch = list(lines)
    original = mismatch[id_row]
    first = original.index("[") + 1
    was = int(float(original[first:first + 12]))
    now = (was + 1) % g["n_expert"]
    mismatch[id_row] = original[:first] + ("%12.4f" % now) + original[first + 12:]
    sum_row = next(i for i, line in enumerate(mismatch[topk_header:], topk_header)
                   if line.startswith("    sum = "))
    mismatch[sum_row] = "    sum = %f" % (sum(routings[1]) - was + now)
    emit("moe-model-transcript-routing.txt", "\n".join(mismatch) + "\n")

    # `R2_EXPERT_ID_NOT_INTEGRAL`: an i32 element the instrument could not have printed.
    nonintegral = list(lines)
    original = nonintegral[id_row]
    nonintegral[id_row] = original[:first] + ("%12.4f" % (was + 0.5)) + original[first + 12:]
    emit("moe-model-transcript-nonintegral.txt", "\n".join(nonintegral) + "\n")

    # The routing the generator's own second implementation produced, per layer, so the runner
    # asserts the document's `schedule[]` against an independent computation of the same routed
    # model rather than against itself.
    plane_bytes = sum(moe_claim_dims(role, g)[0] * moe_claim_dims(role, g)[1] * 4
                      for role, _ in MOE_EXPERT_ROLES)
    used = g["n_expert_used"]
    rows = []
    for layer, topk in enumerate(routings):
        t_out = len(topk) // used
        routed = sorted(set(topk))
        rows.append({
            "layer": layer,
            "t_out": t_out,
            "expert_ids": [topk[i * used:(i + 1) * used] for i in range(t_out)],
            "routed": routed,
            "routed_count": len(routed),
            "compact_ids": [[routed.index(e) for e in topk[i * used:(i + 1) * used]]
                            for i in range(t_out)],
            "claim_bytes": len(routed) * plane_bytes,
        })
    emit("moe-model-routing.json", json.dumps({
        "tokens": MOE_MODEL_TOKENS,
        "kv_width": MOE_MODEL_KV_WIDTH,
        "layers": rows,
        "expert_bytes_read": sum(r["claim_bytes"] for r in rows),
        "expert_bytes_in_model": g["n_layer"] * g["n_expert"] * plane_bytes,
        "planes_read": sum(r["routed_count"] for r in rows) * len(MOE_EXPERT_ROLES),
        "planes_in_model": g["n_layer"] * g["n_expert"] * len(MOE_EXPERT_ROLES),
        "keys_demanded": sum(r["routed_count"] for r in rows),
        "cumulative_expert_bytes": [sum(r["claim_bytes"] for r in rows[:i + 1])
                                    for i in range(len(rows))],
        "logits_order_swap_gap": abs(runtime_logits.data[a] - runtime_logits.data[b]),
    }, separators=(",", ":")) + "\n")

    write_moe_decode_corpus(g, embed, layers, experts, head, records, routings, logits, emit)


# =============================================================================================
# R6-OLMOE-DECODE (`docs/specs/r6-olmoe-decode.md` sections 5.6 and 6.1)
#
# The routed decode corpus: a `K + 1`-graph transcript exactly as `llama-eval-callback -n K` emits
# one, the ids the reference loop consumed, the per-step routed demand stream, and the four
# transcript mutations the seventh smoke block scores against.
#
# It is a **second implementation of the same routed decode step**, in Python, over the same
# synthetic two-layer model: the concatenated past, both concat axes, the offset mask, the router,
# the compact stack, `mul_mat_id`, and the plane's growth by one column per layer per step. The arm
# is never its own oracle.
#
# `n_expert_used = 3 <= 6` keeps the routing oracle's element-wise coverage complete even against a
# compact-axis printer, so this block does **not** depend on the R2C patch — which is the property
# that lets a hosted owner gate a capability whose real oracle needs a patched instrument.
# =============================================================================================


def moe_model_decode_layer(cur, dense, experts, g, planes, n_past, width, mask, last, records,
                           layer):
    """One routed decode layer: the thirty-seven-row decode phase-A table and its phase-B table."""
    head_dim, n_head, n_head_kv = g["head_dim"], g["n_head"], g["n_head_kv"]
    n_embd, n_expert, n_used = g["n_embd"], g["n_expert"], g["n_expert_used"]
    eps, freq_base = g["rms_eps"], g["rope_freq_base"]
    suffix = "-%d" % layer
    plane_k, plane_v = planes[layer]

    norm_in = rms_norm(cur, eps)
    attn_norm = broadcast(norm_in, dense["attn_norm"], lambda x, y: x * y)
    q_pre = mul_mat(dense["attn_q"], attn_norm)
    norm_q = rms_norm(q_pre, eps)
    q_normed = broadcast(norm_q, dense["attn_q_norm"], lambda x, y: x * y)
    # The position is `n_past`, not 0: the embedding row index and the RoPE position are two
    # different numbers, which is the whole reason the arm carries two one-element inputs.
    q_rope = rope_neox(reshape(q_normed, [head_dim, n_head, 1]), [n_past],
                       g["rope_dim_count"], freq_base)
    k_pre = mul_mat(dense["attn_k"], attn_norm)
    norm_k = rms_norm(k_pre, eps)
    k_normed = broadcast(norm_k, dense["attn_k_norm"], lambda x, y: x * y)
    k_rope = rope_neox(reshape(k_normed, [head_dim, n_head_kv, 1]), [n_past],
                       g["rope_dim_count"], freq_base)
    v_cur = mul_mat(dense["attn_v"], attn_norm)
    v3 = reshape(v_cur, [head_dim, n_head_kv, 1])
    kp = permute(k_rope, [0, 2, 1, 3])
    qp = permute(q_rope, [0, 2, 1, 3])
    # Rows 16 to 19: `cont`, `concat` on axis 1, `pad` to `KV_WIDTH`, `mul_mat`. The concatenation
    # is what `WHEN_WIDE` cannot express: `ggml_pad` writes its source at index 0, and this step's
    # new column belongs at `n_past`.
    kcont = cont(kp, [head_dim, 1, n_head_kv])
    kcat = concat_tensor(plane_to_past_k(plane_k, head_dim, n_head_kv, n_past), kcont, 1)
    kpad = pad_tensor(kcat, 0, width - (n_past + 1), 0, 0)
    kq = mul_mat(kpad, qp)
    kqs = soft_max_ext(kq, mask, f32(1.0 / math.sqrt(head_dim)))
    # Rows 21 to 25: the V path, whose column axis after `cont` is **0** and not 1. One shared
    # constant here would be a silent transpose that every downstream shape check accepts.
    vt = cont(permute(v3, [1, 2, 0, 3]), [1, head_dim, n_head_kv])
    vcat = concat_tensor(plane_to_past_v(plane_v, head_dim, n_head_kv, n_past), vt, 0)
    vpad = pad_tensor(vcat, width - (n_past + 1), 0, 0, 0)
    kqv = mul_mat(vpad, kqs)
    kqv_out = cont(permute(kqv, [0, 2, 1, 3]), [n_embd, 1, 1])
    attn_out = mul_mat(dense["attn_output"], kqv_out)
    # The two `WHEN_LAST` rows are kept at `t = 1`, where `get_rows(x, [0])` is the identity. A
    # decode graph does not narrow — section 2.2 measured that on the real model — so they compute
    # nothing; they are not load-bearing and they are not free to be wrong.
    narrowed = get_rows(attn_out, [0]) if last else attn_out
    residual = get_rows(cur, [0]) if last else cur
    ffn_inp = broadcast(narrowed, residual, lambda x, y: x + y)
    norm_ffn = rms_norm(ffn_inp, eps)
    ffn_norm = broadcast(norm_ffn, dense["ffn_norm"], lambda x, y: x * y)

    logits = mul_mat(dense["router"], ffn_norm)
    probs = soft_max_plain(logits)
    argsort = argsort_desc(probs)
    topk = [int(argsort.data[slot]) for slot in range(n_used)]
    topk_tensor = Tensor([n_used, 1], [float(v) for v in topk])
    probs_r = reshape(probs, [1, n_expert, 1])
    weights = get_rows_3d(probs_r, topk_tensor)
    ffn_norm_r = reshape(ffn_norm, [n_embd, 1, 1])
    gate = mul_mat_id(experts["ffn_gate_exps"], ffn_norm_r, topk, n_used)
    up = mul_mat_id(experts["ffn_up_exps"], ffn_norm_r, topk, n_used)
    swiglu = swiglu_split(gate, up)
    down = mul_mat_id(experts["ffn_down_exps"], swiglu, topk, n_used)
    weighted = broadcast(down, weights, lambda x, y: x * y)
    views = [slot_view(weighted, slot) for slot in range(n_used)]
    moe_out = views[0]
    for slot in range(1, n_used):
        moe_out = broadcast(moe_out, views[slot], lambda x, y: x + y)
    l_out = broadcast(moe_out, ffn_inp, lambda x, y: x + y)

    # The write-back, in the reference. The plane grows by exactly one column of this layer's
    # post-QK-norm post-RoPE K and its reshaped V — the same two nodes the prefill captured, at
    # `t = 1` — **after** the concats above read the plane as it was. The two byte ranges are
    # disjoint and the order is upload, compute, write, which is the invariant the arm claims.
    planes[layer] = (concat_tensor(plane_k, k_rope, 2), concat_tensor(plane_v, v3, 2))

    records.extend([
        ("norm" + suffix, "RMS_NORM", "embd" if layer == 0 else "l_out-%d" % (layer - 1), norm_in),
        ("attn_norm" + suffix, "MUL", "norm" + suffix, attn_norm),
        ("Qcur" + suffix, "MUL_MAT", "blk.%d.attn_q.weight" % layer, q_pre),
        ("norm" + suffix, "RMS_NORM", "Qcur" + suffix, norm_q),
        ("Qcur_normed" + suffix, "MUL", "norm" + suffix, q_normed),
        ("Qcur" + suffix, "ROPE", "Qcur_normed%s (reshaped)" % suffix, q_rope),
        ("Kcur" + suffix, "MUL_MAT", "blk.%d.attn_k.weight" % layer, k_pre),
        ("norm" + suffix, "RMS_NORM", "Kcur" + suffix, norm_k),
        ("Kcur_normed" + suffix, "MUL", "norm" + suffix, k_normed),
        ("Kcur" + suffix, "ROPE", "Kcur_normed%s (reshaped)" % suffix, k_rope),
        ("Vcur" + suffix, "MUL_MAT", "blk.%d.attn_v.weight" % layer, v_cur),
        ("kq" + suffix, "MUL_MAT", "cache_k_l%d (view) (permuted)" % layer, kq),
        ("kq_soft_max" + suffix, "SOFT_MAX", "kq" + suffix, kqs),
        ("kqv" + suffix, "MUL_MAT", "cache_v_l%d (view) (permuted)" % layer, kqv),
        ("kqv_out" + suffix, "CONT", "kqv%s (permuted)" % suffix, kqv_out),
        ("node_%d" % (200 + layer), "MUL_MAT", "blk.%d.attn_output.weight" % layer, attn_out),
        ("ffn_inp" + suffix, "ADD", "node_%d" % (200 + layer), ffn_inp),
        ("norm" + suffix, "RMS_NORM", "ffn_inp" + suffix, norm_ffn),
        ("ffn_norm" + suffix, "MUL", "norm" + suffix, ffn_norm),
        ("ffn_moe_logits" + suffix, "MUL_MAT", "blk.%d.ffn_gate_inp.weight" % layer, logits),
        ("ffn_moe_probs" + suffix, "SOFT_MAX", "ffn_moe_logits" + suffix, probs),
        ("ffn_moe_argsort" + suffix, "ARGSORT", "ffn_moe_probs" + suffix, argsort),
        ("ffn_moe_topk" + suffix, "VIEW", "ffn_moe_argsort" + suffix, topk_tensor),
        ("ffn_moe_weights" + suffix, "GET_ROWS", "ffn_moe_probs%s (reshaped)" % suffix, weights),
        ("ffn_moe_gate" + suffix, "MUL_MAT_ID", "blk.%d.ffn_gate_exps.weight" % layer, gate),
        ("ffn_moe_up" + suffix, "MUL_MAT_ID", "blk.%d.ffn_up_exps.weight" % layer, up),
        ("ffn_moe_swiglu" + suffix, "SWIGLU", "ffn_moe_gate" + suffix, swiglu),
        ("ffn_moe_down" + suffix, "MUL_MAT_ID", "blk.%d.ffn_down_exps.weight" % layer, down),
        ("ffn_moe_weighted" + suffix, "MUL", "ffn_moe_down" + suffix, weighted),
        ("ffn_moe_out" + suffix, "ADD", "node_%d" % (300 + layer), moe_out),
        ("l_out" + suffix, "ADD", "ffn_moe_out" + suffix, l_out),
    ])
    return l_out, topk


def moe_model_decode(embed, layers, experts, head, g, planes, token, n_past, width):
    """One routed decode graph set: the embedding gather, the layers, and the head."""
    mask = Tensor([width, 1], [0.0 if c <= n_past else float("-inf") for c in range(width)])
    records = []
    embd = get_rows(embed, [token])
    records.append(("embd", "GET_ROWS", "token_embd.weight", embd))
    cur = embd
    routings = []
    for layer in range(g["n_layer"]):
        cur, topk = moe_model_decode_layer(cur, layers[layer], experts[layer], g, planes, n_past,
                                           width, mask, layer == g["n_layer"] - 1, records, layer)
        routings.append(topk)
    norm = rms_norm(cur, g["rms_eps"])
    result_norm = broadcast(norm, head["output_norm"], lambda x, y: x * y)
    result_output = mul_mat(head["output"], result_norm)
    records.append(("norm", "RMS_NORM", "l_out-%d" % (g["n_layer"] - 1), norm))
    records.append(("result_norm", "MUL", "norm", result_norm))
    records.append(("result_output", "MUL_MAT", "output.weight", result_output))
    return records, routings, result_output


def write_moe_decode_corpus(g, embed, layers, experts, head, prefill_records, prefill_routings,
                            prefill_logits, emit):
    """The `K + 1`-graph routed transcript, its ids, its demand stream, and its four mutations."""
    n_past = len(MOE_MODEL_TOKENS)
    planes = []
    # The prefill is recomputed with the planes captured; its records are the ones already emitted,
    # so the two agree by construction rather than by inspection.
    replayed, replayed_routings, replayed_logits = moe_model_forward(
        embed, layers, experts, head, g, MOE_MODEL_TOKENS, MOE_MODEL_KV_WIDTH, planes)
    assert replayed_logits.data == prefill_logits.data
    assert replayed_routings == prefill_routings
    token = max(range(prefill_logits.count()), key=lambda i: prefill_logits.data[i])

    decode_records = []
    consumed = []
    per_step = []
    step_routings = []
    decode_logits = prefill_logits
    for step in range(MOE_DECODE_STEPS):
        consumed.append(token)
        records, routings, decode_logits = moe_model_decode(
            embed, layers, experts, head, g, planes, token, n_past + step, MOE_MODEL_KV_WIDTH)
        per_step.append(records)
        step_routings.append(routings)
        decode_records.extend(records)
        token = max(range(decode_logits.count()), key=lambda i: decode_logits.data[i])
    lines = moe_transcript(prefill_records + decode_records, MOE_MODEL_TOKENS)
    emit("moe-model-decode-transcript.txt", lines)
    emit("moe-model-decode-logits.bin",
         struct.pack("<%df" % decode_logits.count(), *decode_logits.data))
    assert len(set(consumed)) == len(consumed), \
        "the reference routed decode loop is degenerate: %r" % (consumed,)
    emit("moe-model-decode-tokens.txt", "".join("%d\n" % i for i in consumed))

    # A transcript holding only the **prefill** graph. The arm skips the first graph, so every oracle
    # row is then missing and the run is `R6M_ORACLE_MISSING` rather than a silent comparison against
    # the wrong graph — which is the failure this fixture exists to make visible.
    emit("moe-model-decode-transcript-onegraph.txt",
         moe_transcript(prefill_records, MOE_MODEL_TOKENS))

    # A transcript one graph short of what `STEPS = K` needs. The first `K - 1` steps compare
    # normally and step `K` finds no graph `K + 1`, so the refusal names the step it happened at.
    emit("moe-model-decode-transcript-short-for-steps.txt",
         moe_transcript(prefill_records + [r for s in per_step[:-1] for r in s], MOE_MODEL_TOKENS))

    rows = lines.split("\n")
    marker = "common_debug_cb_eval:"

    def graph_hits(name, op):
        return [i for i, line in enumerate(rows)
                if line.startswith(marker) and (" %s = " % name) in line and ("%s(" % op) in line]

    # A tolerance breach inside the **first decode** graph: one printed element of its `l_out-0`
    # moved by 0.0003, three times the threshold. It is graph 2 and therefore step 1's, so the case
    # is refused at the first step whatever `STEPS` is.
    hits = graph_hits("l_out-0", "ADD")
    perturbed = list(rows)
    row = hits[1] + 3
    original = perturbed[row]
    first = original.index("[") + 1
    value = float(original[first:first + 12])
    perturbed[row] = original[:first] + ("%12.4f" % (value + 0.0003)) + original[first + 12:]
    emit("moe-model-decode-transcript-perturbed.txt", "\n".join(perturbed))

    # `kq-0` of the first **decode** graph declaring a reduction width the operand does not name.
    kq_hits = graph_hits("kq-0", "MUL_MAT")
    widened = list(rows)
    widened[kq_hits[1]] = widened[kq_hits[1]].replace(
        "= {%d, " % MOE_MODEL_KV_WIDTH, "= {%d, " % (MOE_MODEL_KV_WIDTH - 1))
    emit("moe-model-decode-transcript-kv-width.txt", "\n".join(widened))

    # `routing_oracle.verdict: MISMATCH` on a **successful** run: one printed expert id of the first
    # decode graph's `ffn_moe_topk-1` is moved to another expert and the block sum moves with it, so
    # both halves of oracle R disagree while oracle T is still evaluated and reported beside it.
    topk_hits = graph_hits("ffn_moe_topk-1", "VIEW")
    header = topk_hits[1]
    id_row = header + 3
    mismatch = list(rows)
    original = mismatch[id_row]
    first = original.index("[") + 1
    was = int(float(original[first:first + 12]))
    now = (was + 1) % g["n_expert"]
    mismatch[id_row] = original[:first] + ("%12.4f" % now) + original[first + 12:]
    sum_row = next(i for i, line in enumerate(mismatch[header:], header)
                   if line.startswith("    sum = "))
    mismatch[sum_row] = "    sum = %f" % (sum(step_routings[0][1]) - was + now)
    emit("moe-model-decode-transcript-routing.txt", "\n".join(mismatch))

    # The demand stream the generator's own second implementation produced, per step and per layer,
    # so the runner asserts the document's `steps[].routed` against an independent computation of
    # the same routed model rather than against itself.
    plane_bytes = sum(moe_claim_dims(role, g)[0] * moe_claim_dims(role, g)[1] * 4
                      for role, _ in MOE_EXPERT_ROLES)
    used = g["n_expert_used"]
    prefill_keys = set()
    for layer, topk in enumerate(prefill_routings):
        for expert in set(topk):
            prefill_keys.add(layer * g["n_expert"] + expert)
    seen = set(prefill_keys)
    step_rows = []
    for step, routings in enumerate(step_routings):
        layers_out = [sorted(set(routings[layer])) for layer in range(g["n_layer"])]
        keys = [layer * g["n_expert"] + expert
                for layer in range(g["n_layer"]) for expert in layers_out[layer]]
        new = [k for k in keys if k not in seen]
        seen.update(keys)
        step_rows.append({
            "index": step + 1,
            "n_past": n_past + step,
            "token_id": consumed[step],
            "layers": layers_out,
            "keys_demanded": sum(len(x) for x in layers_out),
            "new_keys": len(new),
            "new_bytes": len(new) * plane_bytes,
            "union_keys_after": len(seen),
            "union_bytes_after": len(seen) * plane_bytes,
            "expert_bytes": sum(len(x) for x in layers_out) * plane_bytes,
            "claim_planes_read": sum(len(x) for x in layers_out) * len(MOE_EXPERT_ROLES),
        })
    decode_demands = sum(r["keys_demanded"] for r in step_rows)
    decode_distinct = len(seen - prefill_keys)
    in_prefill = 0
    for step, routings in enumerate(step_routings):
        for layer in range(g["n_layer"]):
            for expert in sorted(set(routings[layer])):
                if layer * g["n_expert"] + expert in prefill_keys:
                    in_prefill = in_prefill + 1
    # R6-OLMOE-DECODE section 3.7's tightened ceiling, which the synthetic geometry cannot reach on
    # its own: `n_expert` is 8 there, so `n_expert_used <= 8` always and the decode arm's bound of 30
    # is unreachable. These two documents declare a wide router instead — `n_expert` 64 with
    # `n_expert_used` 30 and 31 — so the **decode** arm admits the first and refuses the second while
    # `--moe-model-forward` admits both. Nothing else in the corpus changes, and the pack is not
    # described by either: both are refused (or admitted and then refused on the container) before a
    # graph is built, which is the point — the ceiling is a geometry precondition and not a node walk.
    for used in (30, 31):
        wide = json.loads(json.dumps(moe_model_geometry_document(g)))
        wide["model"]["n_expert"] = 64
        wide["model"]["n_expert_used"] = used
        emit("moe-model-geometry-decode-used-%d.json" % used,
             json.dumps(wide, separators=(",", ":")) + "\n")

    emit("moe-model-decode-routing.json", json.dumps({
        "tokens": MOE_MODEL_TOKENS,
        "kv_width": MOE_MODEL_KV_WIDTH,
        "steps": MOE_DECODE_STEPS,
        "token_ids": consumed,
        "plane_bytes": plane_bytes,
        "prefill_keys": sorted(prefill_keys),
        "rows": step_rows,
        "decode_keys_demanded": decode_demands,
        "decode_keys_in_prefill_union": in_prefill,
        "decode_expert_bytes": sum(r["expert_bytes"] for r in step_rows),
        "union_keys_final": len(seen),
        "union_bytes_final": len(seen) * plane_bytes,
        "step_reuse_per_mille": ((decode_demands - decode_distinct) * 1000 // decode_demands)
        if decode_demands else 0,
    }, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
