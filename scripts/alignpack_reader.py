#!/usr/bin/env python3
"""An independent reader of the alignpack v1 container.

`docs/specs/r4-alignpack-layer-major.md` section 4.3. This file is written from section 2.4 of that
document and shares no line with `src/alignpack.align`. It imports nothing from `src/`, and it is
the answer to "how do you know the writer's own report is true": every layout invariant of section
3.6 is checked here by code the writer never touched, and every section 2.6 statistic is recomputed
with a deliberately naive implementation — an explicit interval merge over an explicit list — rather
than with the sweep the writer uses. Two independent implementations of one definition is what makes
the ppm numbers trustworthy; a transcription of the sweep would share its bugs.

It also parses the source GGUF's own header and tensor table, so the source-identity record and
every member record's geometry are checked against the container they claim to describe rather than
against the pack's own assertions.

Usage:

    alignpack_reader.py --source MODEL.gguf --pack PACK.alignpack
                        [--pack-document DOC.json] [--verify-document VERIFY.json]
                        [--expect-reject KIND] [--quiet]

Exit 0 when every invariant holds (or, with `--expect-reject`, when the named defect class is the
first one found). Exit 1 with a diagnostic on stderr otherwise.
"""

import argparse
import hashlib
import json
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
MAX_ALIGNMENT = 65536
DEFERRED_U32 = 0xFFFFFFFF
MAX_NAME_BYTES = 1024
MAX_NAME_STREAM_BYTES = 16 * 1024 * 1024
MAX_TABLE_BYTES = 128 * 1024 * 1024
MAX_BLOCKS = 1 << 20
MAX_MEMBERS = 1 << 20
PPM = 1_000_000
READ_CHUNK = 4 * 1024 * 1024

# Section 2.4.3's block-kind encoding, which is `src/model_ir.align`'s, unchanged.
BLOCK_KINDS = ["WeightBlock", "AttentionBlock", "MlpBlock", "ExpertBlock", "RouterBlock"]

# Section 2.4.4's frozen role list: the fifteen R1 roles of `docs/specs/r1-qwen-model-ir.md`
# section 2.5.6 in that sentence's order, then the roles `docs/specs/r1b-gptoss-moe-ir.md` adds,
# then the two QK-norm roles `docs/specs/r1c-olmoe-moe-ir.md` section 2.5.2 appends. It mirrors
# `src/alignpack.align`'s `role_id`, index for index; `run-model-ir-smoke`'s `role-list-mirror`
# case asserts the equality, because a one-sided edit is a compile error in neither language.
ROLES = [
    "attn_norm", "attn_q", "attn_q_bias", "attn_k", "attn_k_bias", "attn_v", "attn_v_bias",
    "attn_output", "ffn_norm", "ffn_gate", "ffn_up", "ffn_down", "token_embd", "output_norm",
    "output",
    "attn_output_bias", "attn_sinks", "router", "router_bias",
    "ffn_gate_exps", "ffn_gate_exps_bias", "ffn_up_exps", "ffn_up_exps_bias",
    "ffn_down_exps", "ffn_down_exps_bias", "ffn_gate_up_exps", "ffn_gate_up_exps_bias",
    "attn_q_norm", "attn_k_norm",
]

# GGML block geometry, transcribed from the same shipped library the R1B section 2.8.2 oracle read.
GGML_GEOMETRY = {
    0: (1, 4), 1: (1, 2), 2: (32, 18), 3: (32, 20), 6: (32, 22), 7: (32, 24), 8: (32, 34),
    9: (32, 36), 10: (256, 84), 11: (256, 110), 12: (256, 144), 13: (256, 176), 14: (256, 210),
    15: (256, 292), 24: (1, 1), 25: (1, 2), 26: (1, 4), 27: (1, 8), 28: (1, 8), 30: (1, 2),
    39: (32, 17),
}

# The defect classes `--expect-reject` names. Each maps to the `R4_*` code the shipped verifier
# reports for the same mutation, so the smoke can assert that the two implementations agree about
# what is wrong as well as that both refuse it.
REJECT_KINDS = {
    "MAGIC", "VERSION", "HEADER", "RESERVED", "REGION", "TRUNCATED",
    "NAME", "OFFSET", "PADDING", "CONTENT", "IDENTITY", "BLOCK", "MEMBER",
}


class Reject(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        if kind not in REJECT_KINDS:
            raise AssertionError("unknown reject kind %r" % kind)
        self.kind = kind
        self.message = message


def reject(kind, message):
    raise Reject(kind, message)


# ---------------------------------------------------------------------------------------------
# An independent GGUF header and tensor-table parse
# ---------------------------------------------------------------------------------------------

GGUF_MAGIC = b"GGUF"
GGUF_TYPE_WIDTH = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


class GgufReader:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as handle:
            self.head = handle.read(64 * 1024 * 1024)
        self.size = _file_size(path)
        self.at = 0
        if self.head[:4] != GGUF_MAGIC:
            reject("IDENTITY", "source is not a GGUF container")
        self.at = 4
        self.version = self._u32()
        self.tensor_count = self._u64()
        self.kv_count = self._u64()
        self.alignment = 32
        self.architecture = None
        self._read_metadata()
        self.tensors = self._read_tensor_table()
        table_end = self.at
        self.data_offset = _align_up(table_end, self.alignment)
        for tensor in self.tensors:
            tensor["absolute_offset"] = self.data_offset + tensor["offset"]
            tensor["nbytes"] = _tensor_nbytes(tensor["dims"], tensor["type"])
        self.by_name = {}
        for index, tensor in enumerate(self.tensors):
            self.by_name.setdefault(tensor["name"], index)

    def _take(self, n):
        if self.at + n > len(self.head):
            reject("IDENTITY", "source GGUF header region exceeds the reader's window")
        chunk = self.head[self.at:self.at + n]
        self.at += n
        return chunk

    def _u32(self):
        return struct.unpack_from("<I", self._take(4))[0]

    def _u64(self):
        return struct.unpack_from("<Q", self._take(8))[0]

    def _string(self):
        length = self._u64()
        if length > MAX_NAME_STREAM_BYTES:
            reject("IDENTITY", "source GGUF string length %d is implausible" % length)
        return self._take(length)

    def _skip_value(self, type_id):
        if type_id == 8:
            self._string()
            return
        if type_id == 9:
            element_type = self._u32()
            count = self._u64()
            for _ in range(count):
                self._skip_value(element_type)
            return
        width = GGUF_TYPE_WIDTH.get(type_id)
        if width is None:
            reject("IDENTITY", "source GGUF value type %d is unknown" % type_id)
        self._take(width)

    def _read_metadata(self):
        for _ in range(self.kv_count):
            key = self._string()
            type_id = self._u32()
            if key == b"general.alignment" and type_id == 4:
                self.alignment = self._u32()
                continue
            if key == b"general.architecture" and type_id == 8:
                raw = self._string()
                try:
                    self.architecture = raw.decode("utf-8")
                except UnicodeDecodeError:
                    self.architecture = None
                continue
            self._skip_value(type_id)

    def _read_tensor_table(self):
        tensors = []
        for _ in range(self.tensor_count):
            raw_name = self._string()
            n_dims = self._u32()
            dims = [self._u64() for _ in range(n_dims)]
            type_id = self._u32()
            offset = self._u64()
            try:
                name = raw_name.decode("utf-8")
            except UnicodeDecodeError:
                name = None
            tensors.append({
                "name": name, "raw_name": raw_name, "n_dims": n_dims, "dims": dims,
                "type": type_id, "offset": offset,
            })
        return tensors


def _align_up(value, alignment):
    remainder = value % alignment
    return value if remainder == 0 else value + (alignment - remainder)


def _tensor_nbytes(dims, type_id):
    geometry = GGML_GEOMETRY.get(type_id)
    if geometry is None:
        return None
    block_size, type_size = geometry
    if not dims:
        return 0
    elements = 1
    for extent in dims:
        elements *= extent
    if elements == 0:
        return 0
    row_extent = dims[0]
    if row_extent % block_size != 0:
        return None
    row_bytes = (row_extent // block_size) * type_size
    return row_bytes * (elements // row_extent)


def _file_size(path):
    with open(path, "rb") as handle:
        handle.seek(0, 2)
        return handle.tell()


# ---------------------------------------------------------------------------------------------
# The alignpack v1 container
# ---------------------------------------------------------------------------------------------

class Pack:
    def __init__(self, path):
        self.path = path
        self.size = _file_size(path)
        self.handle = open(path, "rb")
        if self.size < HEADER_BYTES:
            reject("TRUNCATED", "pack is %d bytes, shorter than the %d-byte header"
                   % (self.size, HEADER_BYTES))
        self.header = self._read_header()
        self._validate_regions()
        self.name_stream = self.read_at(self.header["name_stream_offset"],
                                        self.header["name_stream_bytes"])
        self.blocks = self._read_blocks()
        self.members = self._read_members()

    def close(self):
        self.handle.close()

    def read_at(self, offset, length):
        if offset < 0 or length < 0 or offset + length > self.size:
            reject("TRUNCATED", "read of %d bytes at %d leaves the %d-byte pack"
                   % (length, offset, self.size))
        self.handle.seek(offset)
        data = self.handle.read(length)
        if len(data) != length:
            reject("TRUNCATED", "short read of %d bytes at %d" % (length, offset))
        return data

    def _read_header(self):
        raw = self.read_at(0, HEADER_BYTES)
        if raw[:4] != MAGIC:
            reject("MAGIC", "magic is %s, not ALGP" % _hex_escape(raw[:4]))
        (format_version, header_bytes, block_align, member_align, flags) = struct.unpack_from(
            "<IIIII", raw, 4)
        if format_version != FORMAT_VERSION:
            reject("VERSION", "format_version is %d" % format_version)
        if header_bytes != HEADER_BYTES:
            reject("HEADER", "header_bytes is %d" % header_bytes)
        if not _power_of_two(block_align) or block_align > MAX_ALIGNMENT:
            reject("HEADER", "block_align is %d" % block_align)
        if not _power_of_two(member_align) or member_align > MAX_ALIGNMENT:
            reject("HEADER", "member_align is %d" % member_align)
        if member_align > block_align:
            reject("HEADER", "member_align %d exceeds block_align %d" % (member_align, block_align))
        if flags != 0:
            reject("RESERVED", "flags is %d; v1 reserves hotness (bit 0) and prefetch (bit 1)"
                   % flags)
        fields = struct.unpack_from("<QQQQQQQQQQ", raw, 24)
        (total_bytes, name_stream_offset, name_stream_bytes, block_table_offset, block_count,
         member_table_offset, member_count, source_record_offset, payload_offset,
         payload_bytes) = fields
        (block_record_bytes, member_record_bytes, source_record_bytes,
         document_schema_version) = struct.unpack_from("<IIII", raw, 104)
        reserved = struct.unpack_from("<Q", raw, 120)[0]
        if block_record_bytes != BLOCK_RECORD_BYTES:
            reject("HEADER", "block_record_bytes is %d" % block_record_bytes)
        if member_record_bytes != MEMBER_RECORD_BYTES:
            reject("HEADER", "member_record_bytes is %d" % member_record_bytes)
        if source_record_bytes != SOURCE_RECORD_BYTES:
            reject("HEADER", "source_record_bytes is %d" % source_record_bytes)
        if document_schema_version != DOCUMENT_SCHEMA_VERSION:
            reject("HEADER", "document_schema_version is %d" % document_schema_version)
        if reserved != 0:
            reject("RESERVED", "header reserved is %d" % reserved)
        if block_count > MAX_BLOCKS:
            reject("HEADER", "block_count %d exceeds the plan bound" % block_count)
        if member_count > MAX_MEMBERS:
            reject("HEADER", "member_count %d exceeds the plan bound" % member_count)
        if total_bytes != self.size:
            reject("TRUNCATED", "header total_bytes %d != file size %d" % (total_bytes, self.size))
        return {
            "format_version": format_version, "header_bytes": header_bytes,
            "block_align": block_align, "member_align": member_align, "flags": flags,
            "total_bytes": total_bytes, "name_stream_offset": name_stream_offset,
            "name_stream_bytes": name_stream_bytes, "block_table_offset": block_table_offset,
            "block_count": block_count, "member_table_offset": member_table_offset,
            "member_count": member_count, "source_record_offset": source_record_offset,
            "payload_offset": payload_offset, "payload_bytes": payload_bytes,
            "block_record_bytes": block_record_bytes,
            "member_record_bytes": member_record_bytes,
            "source_record_bytes": source_record_bytes,
            "document_schema_version": document_schema_version, "reserved": reserved,
        }

    def _validate_regions(self):
        h = self.header
        block_table_bytes = h["block_count"] * BLOCK_RECORD_BYTES
        member_table_bytes = h["member_count"] * MEMBER_RECORD_BYTES
        if block_table_bytes > MAX_TABLE_BYTES or member_table_bytes > MAX_TABLE_BYTES:
            reject("REGION", "a table exceeds the 128 MiB bound")
        if h["name_stream_bytes"] > MAX_NAME_STREAM_BYTES:
            reject("REGION", "name stream exceeds the 16 MiB bound")
        regions = [
            ("header", 0, HEADER_BYTES),
            ("name_stream", h["name_stream_offset"], h["name_stream_bytes"]),
            ("block_table", h["block_table_offset"], block_table_bytes),
            ("member_table", h["member_table_offset"], member_table_bytes),
            ("source_record", h["source_record_offset"], SOURCE_RECORD_BYTES),
            ("payload", h["payload_offset"], h["total_bytes"] - h["payload_offset"]),
        ]
        for name, start, length in regions:
            if start < 0 or length < 0 or start + length > h["total_bytes"]:
                reject("TRUNCATED", "region %s [%d, %d) leaves the file" % (name, start, start + length))
        for i in range(len(regions)):
            for j in range(i + 1, len(regions)):
                a_name, a_start, a_len = regions[i]
                b_name, b_start, b_len = regions[j]
                if a_len <= 0 or b_len <= 0:
                    continue
                if a_start + a_len <= b_start or b_start + b_len <= a_start:
                    continue
                reject("REGION", "regions %s and %s overlap" % (a_name, b_name))
        if h["payload_bytes"] != h["total_bytes"] - h["payload_offset"]:
            reject("REGION", "payload_bytes disagrees with total_bytes - payload_offset")
        if h["payload_offset"] % h["block_align"] != 0:
            reject("REGION", "payload_offset %d is not block_align-aligned" % h["payload_offset"])
        # Every region is 8-byte aligned (section 2.4.2).
        for name, start, _ in regions[:-1]:
            if start % REGION_ALIGN != 0:
                reject("REGION", "region %s starts at %d, not 8-byte aligned" % (name, start))

    def _read_blocks(self):
        h = self.header
        blocks = []
        raw = self.read_at(h["block_table_offset"], h["block_count"] * BLOCK_RECORD_BYTES)
        for index in range(h["block_count"]):
            base = index * BLOCK_RECORD_BYTES
            kind, layer, expert, member_count = struct.unpack_from("<Iiil".replace("l", "I"), raw, base)
            (member_start, pack_offset, pack_bytes, payload_bytes) = struct.unpack_from(
                "<QQQQ", raw, base + 16)
            prefetch_group, hotness_rank = struct.unpack_from("<II", raw, base + 48)
            reserved = struct.unpack_from("<Q", raw, base + 56)[0]
            if prefetch_group != DEFERRED_U32:
                reject("RESERVED", "block[%d].prefetch_group is %d; v1 reserves 0xFFFFFFFF"
                       % (index, prefetch_group))
            if hotness_rank != DEFERRED_U32:
                reject("RESERVED", "block[%d].hotness_rank is %d; v1 reserves 0xFFFFFFFF"
                       % (index, hotness_rank))
            if reserved != 0:
                reject("RESERVED", "block[%d].reserved is %d" % (index, reserved))
            if kind >= len(BLOCK_KINDS):
                reject("BLOCK", "block[%d].kind is %d" % (index, kind))
            if member_count < 1:
                reject("BLOCK", "block[%d].member_count is %d" % (index, member_count))
            if member_start + member_count > h["member_count"]:
                reject("BLOCK", "block[%d] member span leaves the member table" % index)
            blocks.append({
                "index": index, "kind": kind, "layer": layer, "expert": expert,
                "member_count": member_count, "member_start": member_start,
                "pack_offset": pack_offset, "pack_bytes": pack_bytes,
                "payload_bytes": payload_bytes,
            })
        return blocks

    def _read_members(self):
        h = self.header
        members = []
        raw = self.read_at(h["member_table_offset"], h["member_count"] * MEMBER_RECORD_BYTES)
        for index in range(h["member_count"]):
            base = index * MEMBER_RECORD_BYTES
            name_start = struct.unpack_from("<Q", raw, base)[0]
            name_bytes, role_id = struct.unpack_from("<II", raw, base + 8)
            source_offset, nbytes, pack_offset = struct.unpack_from("<QQQ", raw, base + 16)
            ggml_type, n_dims = struct.unpack_from("<II", raw, base + 40)
            dims = list(struct.unpack_from("<QQQQ", raw, base + 48))
            slice_index, slice_count = struct.unpack_from("<ii", raw, base + 80)
            reserved = struct.unpack_from("<Q", raw, base + 88)[0]
            if reserved != 0:
                reject("RESERVED", "member[%d].reserved is %d" % (index, reserved))
            if name_bytes < 1 or name_bytes > MAX_NAME_BYTES:
                reject("NAME", "member[%d].name_bytes is %d" % (index, name_bytes))
            if name_start + name_bytes > h["name_stream_bytes"]:
                reject("NAME", "member[%d] name span leaves the name stream" % index)
            if n_dims > 4:
                reject("MEMBER", "member[%d].n_dims is %d" % (index, n_dims))
            raw_name = self.name_stream[name_start:name_start + name_bytes]
            try:
                name = raw_name.decode("utf-8")
            except UnicodeDecodeError:
                reject("NAME", "member[%d] name span is not valid UTF-8" % index)
            members.append({
                "index": index, "name": name, "name_start": name_start, "name_bytes": name_bytes,
                "role_id": role_id, "source_offset": source_offset, "nbytes": nbytes,
                "pack_offset": pack_offset, "ggml_type": ggml_type, "n_dims": n_dims,
                "dims": dims[:n_dims], "slice_index": slice_index, "slice_count": slice_count,
            })
        return members


def _power_of_two(value):
    return value > 0 and (value & (value - 1)) == 0


def _hex_escape(raw):
    return "".join("\\x%02x" % byte for byte in raw)


# ---------------------------------------------------------------------------------------------
# The layout invariants (section 3.6)
# ---------------------------------------------------------------------------------------------

def check_layout(pack):
    h = pack.header
    if not pack.blocks:
        reject("BLOCK", "the pack declares no block")
    cursor = h["payload_offset"]
    seen_members = 0
    for block in pack.blocks:
        if block["member_start"] != seen_members:
            reject("BLOCK", "block[%d].member_start is %d, expected %d"
                   % (block["index"], block["member_start"], seen_members))
        seen_members += block["member_count"]
        if block["pack_offset"] % h["block_align"] != 0:
            reject("OFFSET", "block[%d].pack_offset %d is not block_align-aligned"
                   % (block["index"], block["pack_offset"]))
        if block["pack_offset"] < cursor:
            reject("OFFSET", "block[%d].pack_offset %d precedes the running cursor %d"
                   % (block["index"], block["pack_offset"], cursor))
        if block["pack_offset"] - cursor >= h["block_align"] and block["index"] > 0:
            reject("OFFSET", "block[%d] leaves %d bytes of gap, more than one alignment unit"
                   % (block["index"], block["pack_offset"] - cursor))
        member_cursor = block["pack_offset"]
        payload = 0
        start = block["member_start"]
        for member in pack.members[start:start + block["member_count"]]:
            if member["pack_offset"] % h["member_align"] != 0:
                reject("OFFSET", "member[%d].pack_offset %d is not member_align-aligned"
                       % (member["index"], member["pack_offset"]))
            if member["pack_offset"] < member_cursor:
                reject("OFFSET", "member[%d].pack_offset %d precedes the running cursor %d"
                       % (member["index"], member["pack_offset"], member_cursor))
            if member["pack_offset"] - member_cursor >= h["member_align"]:
                reject("OFFSET", "member[%d] leaves %d bytes of interior gap"
                       % (member["index"], member["pack_offset"] - member_cursor))
            member_cursor = member["pack_offset"] + member["nbytes"]
            payload += member["nbytes"]
        block_bytes = member_cursor - block["pack_offset"]
        if block["pack_bytes"] != block_bytes:
            reject("BLOCK", "block[%d].pack_bytes is %d, recomputed %d"
                   % (block["index"], block["pack_bytes"], block_bytes))
        if block["payload_bytes"] != payload:
            reject("BLOCK", "block[%d].payload_bytes is %d, recomputed %d"
                   % (block["index"], block["payload_bytes"], payload))
        cursor = member_cursor
    if seen_members != h["member_count"]:
        reject("BLOCK", "blocks cover %d members, the header declares %d"
               % (seen_members, h["member_count"]))
    # Section 2.4.7: no trailing padding — `total_bytes` is the last member's end.
    if cursor != h["total_bytes"]:
        reject("TRUNCATED", "the last member ends at %d, the header declares total_bytes %d"
               % (cursor, h["total_bytes"]))
    # Section 3.1 `stride-addressing`: record `i` is at `table_offset + i * record_bytes`. Seek to
    # each record individually and compare against the full-scan decode.
    for index in (0, h["block_count"] // 2, h["block_count"] - 1):
        raw = pack.read_at(h["block_table_offset"] + index * BLOCK_RECORD_BYTES,
                           BLOCK_RECORD_BYTES)
        if struct.unpack_from("<Q", raw, 24)[0] != pack.blocks[index]["pack_offset"]:
            reject("BLOCK", "block[%d] stride addressing disagrees with the scan" % index)
    for index in (0, h["member_count"] // 2, h["member_count"] - 1):
        raw = pack.read_at(h["member_table_offset"] + index * MEMBER_RECORD_BYTES,
                           MEMBER_RECORD_BYTES)
        if struct.unpack_from("<Q", raw, 32)[0] != pack.members[index]["pack_offset"]:
            reject("MEMBER", "member[%d] stride addressing disagrees with the scan" % index)


def check_padding(pack):
    """Section 2.8 step 19, independently: every byte of the payload region no member claims, and
    the inter-region gap the name stream leaves, must be zero."""
    h = pack.header
    name_stream_end = h["name_stream_offset"] + h["name_stream_bytes"]
    _assert_zero(pack, name_stream_end, h["block_table_offset"] - name_stream_end)
    cursor = h["source_record_offset"] + SOURCE_RECORD_BYTES
    for block in pack.blocks:
        _assert_zero(pack, cursor, block["pack_offset"] - cursor)
        cursor = block["pack_offset"]
        start = block["member_start"]
        for member in pack.members[start:start + block["member_count"]]:
            _assert_zero(pack, cursor, member["pack_offset"] - cursor)
            cursor = member["pack_offset"] + member["nbytes"]
    _assert_zero(pack, cursor, h["total_bytes"] - cursor)


def _assert_zero(pack, offset, length):
    if length <= 0:
        return
    raw = pack.read_at(offset, length)
    stripped = raw.lstrip(b"\x00")
    if stripped:
        reject("PADDING", "padding byte at %d is 0x%02x"
               % (offset + length - len(stripped), stripped[0]))


def check_not_sparse(pack):
    """Section 3.3 `pack-not-sparse`: the padding is written, so the file's allocated size is not
    materially smaller than its logical size. Checked through the block count in stat, which is the
    only allocation view Python offers portably."""
    import os
    stat = os.stat(pack.path)
    allocated = getattr(stat, "st_blocks", None)
    if allocated is None:
        return "N/A (st_blocks is unavailable on this platform)"
    # One filesystem block is 512 bytes for `st_blocks` by POSIX convention. A dense file allocates
    # at least (size - one block) bytes; a sparse one allocates dramatically less.
    if allocated * 512 + 65536 < stat.st_size:
        reject("PADDING", "pack allocates %d bytes for a %d-byte file: the padding is a hole"
               % (allocated * 512, stat.st_size))
    return "dense"


def check_source_identity(pack, gguf):
    raw = pack.read_at(pack.header["source_record_offset"], SOURCE_RECORD_BYTES)
    (file_size, data_offset, tensor_count, kv_count) = struct.unpack_from("<QQQQ", raw, 0)
    gguf_version, alignment = struct.unpack_from("<II", raw, 32)
    header_region_bytes = struct.unpack_from("<Q", raw, 40)[0]
    digest = raw[48:80]
    total_tensor_bytes = struct.unpack_from("<Q", raw, 80)[0]
    payload_present = struct.unpack_from("<Q", raw, 88)[0]
    payload_digest = raw[96:128]
    if payload_present != 0:
        reject("RESERVED", "payload_sha256_present is %d; v1 reserves 0" % payload_present)
    if payload_digest != b"\x00" * 32:
        reject("RESERVED", "payload_sha256 is non-zero; v1 reserves all-zero")
    if header_region_bytes != data_offset:
        reject("IDENTITY", "header_region_bytes %d != data_offset %d"
               % (header_region_bytes, data_offset))
    if file_size != gguf.size:
        reject("IDENTITY", "source_file_size %d != %d" % (file_size, gguf.size))
    if data_offset != gguf.data_offset:
        reject("IDENTITY", "source_data_offset %d != %d" % (data_offset, gguf.data_offset))
    if tensor_count != gguf.tensor_count:
        reject("IDENTITY", "source_tensor_count %d != %d" % (tensor_count, gguf.tensor_count))
    if kv_count != gguf.kv_count:
        reject("IDENTITY", "source_metadata_kv_count %d != %d" % (kv_count, gguf.kv_count))
    if gguf_version != gguf.version:
        reject("IDENTITY", "source_gguf_version %d != %d" % (gguf_version, gguf.version))
    if alignment != gguf.alignment:
        reject("IDENTITY", "source_gguf_alignment %d != %d" % (alignment, gguf.alignment))
    with open(gguf.path, "rb") as handle:
        observed = hashlib.sha256(handle.read(data_offset)).digest()
    if observed != digest:
        reject("IDENTITY", "header_region_sha256 %s != recomputed %s"
               % (digest.hex(), observed.hex()))
    return {
        "header_region_sha256": digest.hex(),
        "total_tensor_bytes": total_tensor_bytes,
    }


def check_member_geometry(pack, gguf):
    """Every member record must describe a tensor the source actually declares, and its claim must
    be either that tensor's whole byte range or one plane of it."""
    for member in pack.members:
        index = gguf.by_name.get(member["name"])
        if index is None:
            reject("MEMBER", "member[%d] names %r, absent from the source tensor table"
                   % (member["index"], member["name"]))
        tensor = gguf.tensors[index]
        if member["ggml_type"] != tensor["type"]:
            reject("MEMBER", "member[%d].ggml_type %d != source %d"
                   % (member["index"], member["ggml_type"], tensor["type"]))
        if member["n_dims"] != tensor["n_dims"]:
            reject("MEMBER", "member[%d].n_dims %d != source %d"
                   % (member["index"], member["n_dims"], tensor["n_dims"]))
        if member["dims"] != tensor["dims"]:
            reject("MEMBER", "member[%d].dims %r != source %r"
                   % (member["index"], member["dims"], tensor["dims"]))
        if member["role_id"] != DEFERRED_U32 and member["role_id"] >= len(ROLES):
            reject("MEMBER", "member[%d].role_id %d is not a frozen role"
                   % (member["index"], member["role_id"]))
        nbytes = tensor["nbytes"]
        if nbytes is None:
            reject("MEMBER", "member[%d] names a tensor the geometry table cannot size"
                   % member["index"])
        if member["slice_index"] < 0:
            expected_offset = tensor["absolute_offset"]
            expected_nbytes = nbytes
        else:
            extent = tensor["dims"][tensor["n_dims"] - 1]
            if member["slice_count"] != extent:
                reject("MEMBER", "member[%d].slice_count %d != last axis extent %d"
                       % (member["index"], member["slice_count"], extent))
            if nbytes % extent != 0:
                reject("MEMBER", "member[%d] slice does not tile its tensor" % member["index"])
            expected_nbytes = nbytes // extent
            expected_offset = tensor["absolute_offset"] + expected_nbytes * member["slice_index"]
        if member["source_offset"] != expected_offset:
            reject("MEMBER", "member[%d].source_offset %d != %d"
                   % (member["index"], member["source_offset"], expected_offset))
        if member["nbytes"] != expected_nbytes:
            reject("MEMBER", "member[%d].nbytes %d != %d"
                   % (member["index"], member["nbytes"], expected_nbytes))
        if member["source_offset"] < gguf.data_offset:
            reject("MEMBER", "member[%d].source_offset precedes data_offset" % member["index"])
        if member["source_offset"] + member["nbytes"] > gguf.size:
            reject("MEMBER", "member[%d] claim leaves the source file" % member["index"])


def check_byte_identity(pack, gguf):
    """Section 3.6 `independent-byte-identity`: re-read every member from both containers and
    compare, without invoking `--pack-verify`."""
    compared = 0
    with open(gguf.path, "rb") as source:
        for member in pack.members:
            remaining = member["nbytes"]
            s = member["source_offset"]
            p = member["pack_offset"]
            while remaining:
                want = min(remaining, READ_CHUNK)
                source.seek(s)
                left = source.read(want)
                right = pack.read_at(p, want)
                if left != right:
                    for delta in range(len(left)):
                        if left[delta] != right[delta]:
                            reject("CONTENT", "%s@%d+%d: source 0x%02x, pack 0x%02x"
                                   % (member["name"], member["source_offset"],
                                      member["nbytes"] - remaining + delta,
                                      left[delta], right[delta]))
                    reject("CONTENT", "%s: windows differ but no byte does" % member["name"])
                s += want
                p += want
                remaining -= want
                compared += want
    return compared


# ---------------------------------------------------------------------------------------------
# The statistics oracle (section 2.6), naive by design
# ---------------------------------------------------------------------------------------------

def merge_intervals(ranges):
    """Explicit interval merging over an explicit sorted list. Deliberately not the sweep
    `src/alignpack.align` uses: two independent implementations of one definition is what makes the
    numbers trustworthy."""
    unique = []
    for item in ranges:
        if item not in unique:
            unique.append(item)
    unique.sort()
    merged = []
    for start, length in unique:
        end = start + length
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return unique, merged


def block_stats(ranges):
    unique, merged = merge_intervals(ranges)
    payload = sum(length for _, length in unique)
    if not unique:
        return {"range_count": 0, "span_bytes": 0, "payload_bytes": 0, "amplification_ppm": 0}
    span = max(start + length for start, length in unique) - min(start for start, _ in unique)
    return {
        "range_count": len(merged),
        "span_bytes": span,
        "payload_bytes": payload,
        "amplification_ppm": _ppm(span, payload),
    }


def _ppm(span, payload):
    if payload <= 0:
        return 0
    return (PPM * span + payload // 2) // payload


def container_stats(pack, key):
    per_block = []
    for block in pack.blocks:
        start = block["member_start"]
        ranges = [(m[key], m["nbytes"])
                  for m in pack.members[start:start + block["member_count"]]]
        stats = block_stats(ranges)
        stats["kind"] = BLOCK_KINDS[block["kind"]]
        per_block.append(stats)
    totals = {
        "range_count": sum(b["range_count"] for b in per_block),
        "span_bytes": sum(b["span_bytes"] for b in per_block),
        "payload_bytes": sum(b["payload_bytes"] for b in per_block),
        "contiguous_block_count": sum(1 for b in per_block if b["range_count"] == 1),
    }
    totals["amplification_ppm"] = _ppm(totals["span_bytes"], totals["payload_bytes"])
    by_kind = []
    for kind in BLOCK_KINDS:
        rows = [b for b in per_block if b["kind"] == kind]
        if not rows:
            continue
        entry = {
            "kind": kind,
            "block_count": len(rows),
            "range_count": sum(b["range_count"] for b in rows),
            "span_bytes": sum(b["span_bytes"] for b in rows),
            "payload_bytes": sum(b["payload_bytes"] for b in rows),
            "contiguous_block_count": sum(1 for b in rows if b["range_count"] == 1),
        }
        entry["amplification_ppm"] = _ppm(entry["span_bytes"], entry["payload_bytes"])
        by_kind.append(entry)
    totals["by_kind"] = by_kind
    return totals, per_block


# ---------------------------------------------------------------------------------------------
# Document cross-checks
# ---------------------------------------------------------------------------------------------

def check_document(pack, document, source_totals, pack_totals, per_source, per_pack, identity):
    h = pack.header
    kind = document.get("kind")
    if kind not in ("R4_ALIGNPACK", "R4_ALIGNPACK_VERIFY"):
        reject("HEADER", "document kind is %r" % kind)
    if document.get("schema_version") != DOCUMENT_SCHEMA_VERSION:
        reject("HEADER", "document schema_version is %r" % document.get("schema_version"))
    fmt = document["format"]
    for field, value in (("format_version", FORMAT_VERSION), ("magic", "ALGP"),
                         ("block_align", h["block_align"]), ("member_align", h["member_align"]),
                         ("flags", 0), ("hotness_ordered", False), ("prefetch_grouped", False),
                         ("block_record_bytes", BLOCK_RECORD_BYTES),
                         ("member_record_bytes", MEMBER_RECORD_BYTES),
                         ("source_record_bytes", SOURCE_RECORD_BYTES)):
        if fmt[field] != value:
            reject("HEADER", "document format.%s is %r, container says %r" % (field, fmt[field], value))
    pack_object = document["pack"]
    for field in ("total_bytes", "name_stream_offset", "name_stream_bytes", "block_table_offset",
                  "block_count", "member_table_offset", "member_count", "source_record_offset",
                  "payload_offset", "payload_bytes"):
        if pack_object[field] != h[field]:
            reject("HEADER", "document pack.%s is %r, container says %r"
                   % (field, pack_object[field], h[field]))
    if document["source"]["header_region_sha256"] != identity["header_region_sha256"]:
        reject("IDENTITY", "document header_region_sha256 disagrees with the container's")
    sequential = document["sequential_read"]
    for side, totals in (("source", source_totals), ("pack", pack_totals)):
        observed = sequential[side]
        for field in ("range_count", "span_bytes", "payload_bytes", "contiguous_block_count",
                      "amplification_ppm"):
            if observed[field] != totals[field]:
                reject("BLOCK", "document sequential_read.%s.%s is %r, oracle says %r"
                       % (side, field, observed[field], totals[field]))
        if observed["by_kind"] != totals["by_kind"]:
            reject("BLOCK", "document sequential_read.%s.by_kind disagrees with the oracle" % side)
    blocks = document["blocks"]
    if len(blocks) != len(pack.blocks):
        reject("BLOCK", "document lists %d blocks, the container has %d"
               % (len(blocks), len(pack.blocks)))
    for index, entry in enumerate(blocks):
        block = pack.blocks[index]
        if entry["index"] != index:
            reject("BLOCK", "document block %d reports index %r" % (index, entry["index"]))
        if entry["kind"] != BLOCK_KINDS[block["kind"]]:
            reject("BLOCK", "document block %d kind disagrees" % index)
        for field in ("layer", "expert", "pack_offset", "pack_bytes", "payload_bytes"):
            if entry[field] != block[field]:
                reject("BLOCK", "document block %d %s is %r, container says %r"
                       % (index, field, entry[field], block[field]))
        if entry["padding_bytes"] != block["pack_bytes"] - block["payload_bytes"]:
            reject("BLOCK", "document block %d padding_bytes disagrees" % index)
        for field, oracle in (("source_range_count", per_source[index]["range_count"]),
                              ("source_span_bytes", per_source[index]["span_bytes"]),
                              ("source_amplification_ppm", per_source[index]["amplification_ppm"]),
                              ("pack_range_count", per_pack[index]["range_count"]),
                              ("pack_span_bytes", per_pack[index]["span_bytes"]),
                              ("pack_amplification_ppm", per_pack[index]["amplification_ppm"])):
            if entry[field] != oracle:
                reject("BLOCK", "document block %d %s is %r, oracle says %r"
                       % (index, field, entry[field], oracle))
        start = block["member_start"]
        for offset, member_entry in enumerate(entry["members"]):
            member = pack.members[start + offset]
            if member_entry["name"] != member["name"]:
                reject("MEMBER", "document block %d member %d name disagrees" % (index, offset))
            for field in ("source_offset", "nbytes", "pack_offset", "ggml_type", "n_dims",
                          "slice_index", "slice_count"):
                if member_entry[field] != member[field]:
                    reject("MEMBER", "document block %d member %d %s is %r, container says %r"
                           % (index, offset, field, member_entry[field], member[field]))
            if member_entry["dims"] != member["dims"]:
                reject("MEMBER", "document block %d member %d dims disagree" % (index, offset))
            expected_role = None if member["role_id"] == DEFERRED_U32 else ROLES[member["role_id"]]
            if member_entry["role"] != expected_role:
                reject("MEMBER", "document block %d member %d role is %r, frozen list says %r"
                       % (index, offset, member_entry["role"], expected_role))
    if kind == "R4_ALIGNPACK":
        layout = document["layout"]
        padding = h["total_bytes"] - h["payload_offset"] - pack_totals["payload_bytes"]
        if layout["payload_bytes"] != pack_totals["payload_bytes"]:
            reject("BLOCK", "document layout.payload_bytes disagrees with the oracle")
        if layout["padding_bytes"] != padding:
            reject("BLOCK", "document layout.padding_bytes is %r, recomputed %d"
                   % (layout["padding_bytes"], padding))
        if layout["block_order"] != "model_ir":
            reject("BLOCK", "document layout.block_order is %r" % layout["block_order"])
        if layout["max_block_bytes"] != max(b["pack_bytes"] for b in pack.blocks):
            reject("BLOCK", "document layout.max_block_bytes disagrees")
        if layout["max_member_bytes"] != max((m["nbytes"] for m in pack.members), default=0):
            reject("BLOCK", "document layout.max_member_bytes disagrees")
    else:
        if document["verdict"] != "identical":
            reject("CONTENT", "verify document verdict is %r" % document["verdict"])
        if document["identity"]["header_region_match"] is not True:
            reject("IDENTITY", "verify document reports no header-region match")
        if document["comparison"]["first_mismatch"] is not None:
            reject("CONTENT", "verify document names a first mismatch")
        if document["comparison"]["bytes_compared"] != pack_totals["payload_bytes"]:
            reject("CONTENT", "verify document compared %r bytes, the oracle expects %d"
                   % (document["comparison"]["bytes_compared"], pack_totals["payload_bytes"]))
        if document["sequential_read"]["source_of_pack_stats"] != "pack_tables":
            reject("BLOCK", "verify document provenance is %r"
                   % document["sequential_read"]["source_of_pack_stats"])


# ---------------------------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------------------------

def run(options):
    gguf = GgufReader(options.source)
    pack = Pack(options.pack)
    try:
        check_layout(pack)
        identity = check_source_identity(pack, gguf)
        check_member_geometry(pack, gguf)
        check_padding(pack)
        sparse = check_not_sparse(pack)
        compared = check_byte_identity(pack, gguf)
        source_totals, per_source = container_stats(pack, "source_offset")
        pack_totals, per_pack = container_stats(pack, "pack_offset")
        for path in (options.pack_document, options.verify_document):
            if path is None:
                continue
            with open(path, "rb") as handle:
                document = json.loads(handle.read().decode("utf-8"))
            check_document(pack, document, source_totals, pack_totals, per_source, per_pack,
                           identity)
    finally:
        pack.close()
    return {
        "blocks": pack.header["block_count"],
        "members": pack.header["member_count"],
        "total_bytes": pack.header["total_bytes"],
        "bytes_compared": compared,
        "allocation": sparse,
        "source": source_totals,
        "pack": pack_totals,
    }


def main(argv):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--pack", required=True)
    parser.add_argument("--pack-document")
    parser.add_argument("--verify-document")
    parser.add_argument("--expect-reject", choices=sorted(REJECT_KINDS))
    parser.add_argument("--quiet", action="store_true")
    options = parser.parse_args(argv[1:])
    try:
        report = run(options)
    except Reject as failure:
        if options.expect_reject:
            if failure.kind == options.expect_reject:
                if not options.quiet:
                    print("alignpack reader: REJECTED %s (%s)" % (failure.kind, failure.message))
                return 0
            sys.stderr.write("alignpack reader: expected %s, rejected %s (%s)\n"
                             % (options.expect_reject, failure.kind, failure.message))
            return 1
        sys.stderr.write("alignpack reader: FAIL %s (%s)\n" % (failure.kind, failure.message))
        return 1
    if options.expect_reject:
        sys.stderr.write("alignpack reader: expected %s, accepted the pack\n"
                         % options.expect_reject)
        return 1
    if not options.quiet:
        print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
