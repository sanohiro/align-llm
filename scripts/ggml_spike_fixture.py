#!/usr/bin/env python3
"""R4.5-EXTERNAL-BUFFER-SPIKE synthetic alignpack v1 corpus.

`docs/specs/r4-5-external-buffer.md` section 5.1. It writes one small, hand-computable container —
three blocks, five members, well under 64 KiB — plus one mutation per fixture, produced by editing a
copy of the base pack's bytes. Nothing here needs a model, a network, or ggml.

The generator is deliberately independent of `src/alignpack.align`'s writer: it encodes the v1
layout of `docs/specs/r4-alignpack-layer-major.md` sections 2.4.2 to 2.4.7 from that document,
which is what makes `scripts/alignpack_reader.py` a *third* opinion when the smoke compares all
three.

Run it directly to write the corpus into a directory:

    python3 scripts/ggml_spike_fixture.py OUTDIR
"""

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

# The `src/model_ir.align:212` block-kind encoding, unchanged.
KIND_WEIGHT = 0
KIND_ATTENTION = 1
KIND_MLP = 2

# ggml type ids and their Q4_K / F32 geometry, from `ggml.h` at the measured pin.
TYPE_F32 = 0
TYPE_Q4_K = 12
BLCK = {TYPE_F32: 1, TYPE_Q4_K: 256}
TYPE_SIZE = {TYPE_F32: 4, TYPE_Q4_K: 144}


def align_up(value, alignment):
    remainder = value % alignment
    return value if remainder == 0 else value + (alignment - remainder)


def nbytes_of(type_id, dim0, dim1):
    return (dim0 // BLCK[type_id]) * TYPE_SIZE[type_id] * dim1


class Member:
    def __init__(self, name, type_id, dim0, dim1, role_id=DEFERRED_U32, pad_before=0):
        self.name = name
        self.type_id = type_id
        self.dim0 = dim0
        self.dim1 = dim1
        self.role_id = role_id
        self.pad_before = pad_before
        self.nbytes = nbytes_of(type_id, dim0, dim1)
        self.source_offset = 0
        self.pack_offset = 0
        self.name_start = 0


class Block:
    def __init__(self, kind, layer, expert, members):
        self.kind = kind
        self.layer = layer
        self.expert = expert
        self.members = members
        self.member_start = 0
        self.pack_offset = 0
        self.pack_bytes = 0
        self.payload_bytes = 0


def minimal_blocks():
    """Three blocks, five members.

    Block 1's second member lands at interior offset 2304 inside its block, which is what makes
    `ggml-spike PACK 1 1` a non-trivial pointer-identity case rather than an offset of zero.
    """
    return [
        Block(KIND_WEIGHT, -1, -1, [Member("token_embd.weight", TYPE_Q4_K, 256, 8, role_id=0)]),
        Block(KIND_ATTENTION, 0, -1, [
            Member("blk.0.attn_q.weight", TYPE_Q4_K, 256, 16, role_id=1),
            Member("blk.0.attn_k.weight", TYPE_Q4_K, 256, 8, role_id=2),
        ]),
        Block(KIND_MLP, 0, -1, [
            Member("blk.0.ffn_gate.weight", TYPE_F32, 4, 4, role_id=3),
            Member("blk.0.ffn_up.weight", TYPE_Q4_K, 512, 4, role_id=4),
        ]),
    ]


def payload_bytes_for(member, index):
    """Deterministic member content, distinct per member and per offset.

    A constant fill would make a byte-identity check pass over a member the writer placed at the
    wrong offset, so every byte carries both its member index and its position.
    """
    seed = (index * 131 + 17) & 0xFF
    return bytes(((seed + (i * 37) + (i >> 8)) & 0xFF) for i in range(member.nbytes))


def build(blocks=None, block_align=BLOCK_ALIGN, member_align=MEMBER_ALIGN):
    """Encode one alignpack v1 container and return `(bytes, layout)`."""
    blocks = minimal_blocks() if blocks is None else blocks

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
            cursor = align_up(cursor + member.pad_before, member_align)
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
        struct.pack_into("<QII", raw, base, member.name_start, len(member.name.encode("utf-8")),
                         member.role_id)
        struct.pack_into("<QQQ", raw, base + 16, member.source_offset, member.nbytes,
                         member.pack_offset)
        struct.pack_into("<II", raw, base + 40, member.type_id, 2)
        struct.pack_into("<QQQQ", raw, base + 48, member.dim0, member.dim1, 1, 1)
        struct.pack_into("<iiQ", raw, base + 80, -1, -1, 0)
        raw[member.pack_offset:member.pack_offset + member.nbytes] = payload_bytes_for(
            member, index)

    layout = {
        "total_bytes": total_bytes,
        "block_align": block_align,
        "member_align": member_align,
        "name_stream_offset": name_stream_offset,
        "name_stream_bytes": name_stream_bytes,
        "block_table_offset": block_table_offset,
        "block_count": len(blocks),
        "member_table_offset": member_table_offset,
        "member_count": len(members),
        "source_record_offset": source_record_offset,
        "payload_offset": payload_offset,
        "blocks": blocks,
        "members": members,
    }
    return bytes(raw), layout


def block_field(layout, index, offset):
    return layout["block_table_offset"] + index * BLOCK_RECORD_BYTES + offset


def member_field(layout, index, offset):
    return layout["member_table_offset"] + index * MEMBER_RECORD_BYTES + offset


def patch(raw, offset, fmt, *values):
    edited = bytearray(raw)
    struct.pack_into(fmt, edited, offset, *values)
    return bytes(edited)


def misaligned_member_pack():
    """A container whose `member_align` is a **valid** power of two smaller than 32.

    `member_align = 16` is legal v1 — the header's alignments are values a reader validates and
    uses, not constants it may assume — so a member can legitimately start 16 bytes into a
    32-aligned block. That is the one input from which `R4_5_ALIGNMENT` is reachable: the weights
    buffer's own base comes from the Align allocator and is not a container property.
    """
    blocks = minimal_blocks()
    blocks[1].members[1].pad_before = 16
    return build(blocks=blocks, member_align=16)


def corpus():
    """Every fixture as `(name, bytes)`, base pack first."""
    base, layout = build()
    misaligned, _ = misaligned_member_pack()
    return [
        ("pack-minimal", base),
        ("pack-bad-magic", patch(base, 0, "<B", 0x58)),
        ("pack-bad-version", patch(base, 4, "<I", 2)),
        ("pack-bad-widths", patch(base, 104, "<I", 63)),
        ("pack-bad-align", patch(base, 12, "<I", 3)),
        ("pack-flags-set", patch(base, 20, "<I", 1)),
        ("pack-len-mismatch", patch(base, 24, "<Q", layout["total_bytes"] + 1)),
        ("pack-region-overlap",
         patch(base, 48, "<Q", layout["name_stream_offset"])),
        ("pack-u64-highbit", patch(base, 32, "<Q", layout["name_stream_offset"] | (1 << 63))),
        ("pack-name-overrun", patch(base, member_field(layout, 2, 8), "<I", 1000)),
        ("pack-offset-nonmonotonic",
         patch(base, block_field(layout, 2, 24), "<Q", layout["blocks"][1].pack_offset)),
        ("pack-reserved-block", patch(base, block_field(layout, 0, 48), "<I", 0)),
        ("pack-reserved-member", patch(base, member_field(layout, 2, 88), "<Q", 1)),
        ("spike-shape-3d", patch(base, member_field(layout, 2, 44), "<I", 3)),
        ("spike-shape-zero", patch(base, member_field(layout, 2, 56), "<Q", 0)),
        ("spike-dimension-bound", patch(base, member_field(layout, 2, 56), "<Q", 1 << 25)),
        ("spike-ne0-not-multiple", patch(base, member_field(layout, 2, 48), "<Q", 100)),
        ("spike-type-unsupported", patch(base, member_field(layout, 2, 40), "<I", 9)),
        ("spike-misaligned-member", misaligned),
    ]


def source_image(layout, corrupt_member=None):
    """A synthetic "original" file holding each member's bytes at its recorded `source_offset`.

    The reference arm reads the member's `nbytes` at `source_offset` and compares them to the pack's
    bytes with `crypto.constant_time_equal`. This is not a GGUF and does not pretend to be one: the
    arm reads a byte range, nothing more, so a range-accurate image is exactly the input the
    equality check consumes. `corrupt_member` flips one byte inside that member's range, which is
    the `R4_5_SOURCE_DIVERGED` fixture.
    """
    members = layout["members"]
    size = max(m.source_offset + m.nbytes for m in members)
    raw = bytearray(size)
    for index, member in enumerate(members):
        raw[member.source_offset:member.source_offset + member.nbytes] = payload_bytes_for(
            member, index)
    if corrupt_member is not None:
        member = members[corrupt_member]
        at = member.source_offset + member.nbytes // 2
        raw[at] = raw[at] ^ 0xFF
    return bytes(raw)


def truncated_source(layout, at):
    """The reference image cut short, for the three ways a reference cannot supply the range.

    `ggml-spike PACK 1 1 - REF` reads the member's `nbytes` at its recorded `source_offset` out of a
    file the caller merely named. A file that is empty, that ends before the member starts, or that
    ends inside it supplies no such range, and the arm must say the **reference** is unreadable at
    that range rather than let a zero-length read reach the container reader's window answer.
    """
    return source_image(layout)[:at]


def write_corpus(directory):
    os.makedirs(directory, exist_ok=True)
    written = []
    for name, raw in corpus():
        path = os.path.join(directory, name + ".alignpack")
        with open(path, "wb") as handle:
            handle.write(raw)
        written.append(path)
    _, layout = build()
    # Member index 2 is `blk.0.attn_k.weight`, the member `PACK 1 1` selects.
    selected = layout["members"][2]
    for name, raw in (("source-identical.bin", source_image(layout)),
                      ("source-diverged.bin", source_image(layout, corrupt_member=2)),
                      ("source-empty.bin", b""),
                      ("source-eof.bin", truncated_source(layout, selected.source_offset)),
                      ("source-mid-member.bin",
                       truncated_source(layout, selected.source_offset + selected.nbytes // 2))):
        path = os.path.join(directory, name)
        with open(path, "wb") as handle:
            handle.write(raw)
        written.append(path)
    return written


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: ggml_spike_fixture.py OUTDIR\n")
        return 2
    for path in write_corpus(argv[1]):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
