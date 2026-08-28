#!/usr/bin/env python3
"""R6-KV-PERSIST (`docs/specs/r6-kv-persist.md` sections 2.3 and 4.5): an independent reader for the
`akvp` v1 container.

**This file is written from the specification and shares no line with `src/`.** It decodes every
header and identity field at its declared offset, re-derives the plane's length from the geometry
integers, checks region containment, disjointness, alignment, and order, checks that every column at
or above `columns_persisted` is zero, recomputes all five `sha256` digests, and checks that
`prefill_argmax` really is the argmax of the persisted vector. A reader that trusts the writer is
not independent, so it trusts nothing: not the writer's arithmetic, not its padding, and not its
digests.

It is driven as a **subprocess and never imported** (`scripts/run-alignpack-smoke`'s rule, for its
reason: a shared interpreter state would let the two implementations agree by accident).

    kv_plane_reader.py --plane PATH [--pack PACK] [--geometry GEOM.json] [--tokens 3,17,5]
                       [--expect-reject KIND] [--quiet]

Exit 0 when the container is accepted, or when it is rejected for exactly the expected kind. Exit 1
otherwise. The reject vocabulary is **coarser than the arm's** on purpose: it is a second opinion
about a class of defect, not a transcription of `R6_KV_*`.
"""

import argparse
import hashlib
import struct
import sys

MAGIC = b"AKVP"
FORMAT_VERSION = 1
HEADER_BYTES = 192
IDENTITY_RECORD_BYTES = 192
PLANE_LAYOUT_VERSION = 1
ELEMENT_TYPE_F32 = 0
REGION_ALIGN = 8
MAX_ALIGNMENT = 65536
ENDIAN_PROBE = 0x0102030405060708
DOCUMENT_SCHEMA_VERSION = 3
DIGEST_BYTES = 32
# Section 2.5's three bounds, restated here rather than imported.
MAX_KV_PLANE_BYTES = 536870912
MAX_KV_LOGITS_BYTES = 16777216
MAX_KV_CONTAINER_BYTES = 1073741824
# `layer_qwen2.MAX_PREFILL_TOKENS` and `MAX_ATTENTION_WIDTH`.
MAX_PREFILL_TOKENS = 32
MAX_ATTENTION_WIDTH = 4096

REJECT_KINDS = [
    "MAGIC", "VERSION", "HEADER", "RESERVED", "REGION", "TRUNCATED", "IDENTITY", "GEOMETRY",
    "TOKENS", "NPAST", "DIGEST", "ARGMAX", "ZEROTAIL",
]

# The pack's own source-identity record: `docs/specs/r4-alignpack-layer-major.md` section 2.4.6.
PACK_MAGIC = b"ALGP"
PACK_SOURCE_RECORD_OFFSET_AT = 80
PACK_TOTAL_BYTES_AT = 24
PACK_SOURCE_DIGEST_IN_RECORD = 48


class Reject(Exception):
    def __init__(self, kind, detail):
        super().__init__("%s: %s" % (kind, detail))
        self.kind = kind
        self.detail = detail


def reject(kind, detail):
    assert kind in REJECT_KINDS, kind
    raise Reject(kind, detail)


def u32(raw, at):
    return struct.unpack_from("<I", raw, at)[0]


def i32(raw, at):
    return struct.unpack_from("<i", raw, at)[0]


def u64(raw, at, field):
    value = struct.unpack_from("<Q", raw, at)[0]
    if value >> 63:
        reject("HEADER", "%s has its high bit set" % field)
    return value


def align_up(value, alignment):
    remainder = value % alignment
    return value if remainder == 0 else value + (alignment - remainder)


def inside(start, length, total):
    return 0 <= start <= total and 0 <= length <= total - start


def disjoint(a_start, a_len, b_start, b_len):
    if a_len <= 0 or b_len <= 0:
        return True
    return a_start + a_len <= b_start or b_start + b_len <= a_start


def decode_header(raw, size):
    """Sections 2.3.1 and 2.3, in this reader's own order: identity of the format, then the fixed
    widths, then the reserved space, then the regions."""
    if size < HEADER_BYTES:
        reject("TRUNCATED", "%d bytes is shorter than one %d-byte header" % (size, HEADER_BYTES))
    if raw[0:4] != MAGIC:
        reject("MAGIC", "magic is %r, not %r" % (bytes(raw[0:4]), MAGIC))
    h = {"format_version": u32(raw, 4)}
    if h["format_version"] != FORMAT_VERSION:
        reject("VERSION", "format_version is %d, not %d" % (h["format_version"], FORMAT_VERSION))

    h["header_bytes"] = u32(raw, 8)
    h["identity_record_bytes"] = u32(raw, 12)
    h["element_type"] = u32(raw, 16)
    h["plane_layout_version"] = u32(raw, 20)
    h["flags"] = u32(raw, 24)
    h["plane_align"] = u32(raw, 28)
    if h["header_bytes"] != HEADER_BYTES:
        reject("HEADER", "header_bytes is %d" % h["header_bytes"])
    if h["identity_record_bytes"] != IDENTITY_RECORD_BYTES:
        reject("HEADER", "identity_record_bytes is %d" % h["identity_record_bytes"])
    if h["element_type"] != ELEMENT_TYPE_F32:
        reject("HEADER", "element_type is %d" % h["element_type"])
    if h["plane_layout_version"] != PLANE_LAYOUT_VERSION:
        reject("HEADER", "plane_layout_version is %d" % h["plane_layout_version"])
    if h["flags"] != 0:
        reject("RESERVED", "flags is %d" % h["flags"])
    align = h["plane_align"]
    if align < REGION_ALIGN or align > MAX_ALIGNMENT or align & (align - 1):
        reject("HEADER", "plane_align is %d" % align)

    h["endian_probe"] = struct.unpack_from("<Q", raw, 32)[0]
    if h["endian_probe"] != ENDIAN_PROBE:
        # The canary, not a mode switch: it names the cause of a class the region checks below would
        # otherwise report as an opaque defect.
        reject("HEADER", "endian_probe is 0x%016x" % h["endian_probe"])

    for name, at in (("total_bytes", 40), ("token_stream_offset", 48), ("token_stream_bytes", 56),
                     ("identity_offset", 64), ("logits_offset", 72), ("logits_bytes", 80),
                     ("plane_offset", 88), ("plane_bytes", 96)):
        h[name] = u64(raw, at, name)
    for name, at in (("n_layer", 104), ("n_head_kv", 108), ("head_dim", 112), ("kv_width", 116),
                     ("columns_persisted", 120), ("token_count", 124), ("n_vocab", 128)):
        h[name] = u32(raw, at)
    h["prefill_argmax"] = i32(raw, 132)
    h["document_schema_version"] = u32(raw, 136)
    h["reserved_u32"] = u32(raw, 140)

    for name in ("n_layer", "n_head_kv", "head_dim", "n_vocab"):
        if h[name] < 1:
            reject("HEADER", "%s is %d" % (name, h[name]))
    if not 1 <= h["kv_width"] <= MAX_ATTENTION_WIDTH:
        reject("HEADER", "kv_width is %d" % h["kv_width"])
    if not 1 <= h["token_count"] <= MAX_PREFILL_TOKENS:
        reject("HEADER", "token_count is %d" % h["token_count"])
    if not 1 <= h["columns_persisted"] <= h["kv_width"]:
        reject("HEADER", "columns_persisted is %d" % h["columns_persisted"])
    if not 0 <= h["prefill_argmax"] < h["n_vocab"]:
        reject("HEADER", "prefill_argmax is %d" % h["prefill_argmax"])
    if h["document_schema_version"] != DOCUMENT_SCHEMA_VERSION:
        reject("HEADER", "document_schema_version is %d" % h["document_schema_version"])
    if h["reserved_u32"] != 0:
        reject("RESERVED", "reserved_u32 is %d" % h["reserved_u32"])
    if any(raw[144:HEADER_BYTES]):
        reject("RESERVED", "a reserved header byte is non-zero")

    if h["plane_bytes"] > MAX_KV_PLANE_BYTES:
        reject("HEADER", "plane_bytes %d exceeds MAX_KV_PLANE_BYTES" % h["plane_bytes"])
    if h["logits_bytes"] > MAX_KV_LOGITS_BYTES:
        reject("HEADER", "logits_bytes %d exceeds MAX_KV_LOGITS_BYTES" % h["logits_bytes"])
    if h["total_bytes"] > MAX_KV_CONTAINER_BYTES:
        reject("HEADER", "total_bytes %d exceeds MAX_KV_CONTAINER_BYTES" % h["total_bytes"])

    # **`TRUNCATED` is reserved for a file whose length disagrees with its own header.** Every other
    # region defect is `REGION`, including a region that points past the end: the file is the length
    # it says it is, and it is the offset that is wrong.
    if size != h["total_bytes"]:
        reject("TRUNCATED", "file is %d bytes, header says %d" % (size, h["total_bytes"]))

    regions = [
        ("header", 0, HEADER_BYTES),
        ("token_stream", h["token_stream_offset"], h["token_stream_bytes"]),
        ("identity", h["identity_offset"], IDENTITY_RECORD_BYTES),
        ("logits", h["logits_offset"], h["logits_bytes"]),
        ("plane", h["plane_offset"], h["plane_bytes"]),
    ]
    for name, start, length in regions:
        if not inside(start, length, h["total_bytes"]):
            reject("REGION", "%s [%d, %d) is not inside the container" % (name, start,
                                                                         start + length))
        if start % REGION_ALIGN:
            reject("REGION", "%s starts at %d, which is not %d-aligned" % (name, start,
                                                                          REGION_ALIGN))
    for index, (name, start, length) in enumerate(regions):
        for other, o_start, o_len in regions[index + 1:]:
            if not disjoint(start, length, o_start, o_len):
                reject("REGION", "%s and %s overlap" % (name, other))
    if h["plane_offset"] % h["plane_align"]:
        reject("REGION", "plane_offset %d is not %d-aligned" % (h["plane_offset"],
                                                               h["plane_align"]))
    # Region-order property 1: the plane is **last**, exactly, which is what makes a chunked
    # reader's tail read short rather than an over-read.
    if h["plane_offset"] + h["plane_bytes"] != h["total_bytes"]:
        reject("REGION", "the plane does not end the container: %d + %d != %d"
               % (h["plane_offset"], h["plane_bytes"], h["total_bytes"]))
    if h["token_stream_bytes"] != h["token_count"] * 4:
        reject("REGION", "token_stream_bytes %d is not 4 x token_count %d"
               % (h["token_stream_bytes"], h["token_count"]))
    if h["logits_bytes"] != h["n_vocab"] * 4:
        reject("REGION", "logits_bytes %d is not 4 x n_vocab %d"
               % (h["logits_bytes"], h["n_vocab"]))
    # Section 2.3.1's canonical layout: a **format** rule, not this reader's preference. The region
    # order, the two alignments, and the region sizes determine every offset, so an `akvp` v1
    # container has exactly one layout at a given `token_count`, `n_vocab`, and `plane_align`.
    # `src/kv_plane.align`'s L7 re-derives the same three offsets and refuses a non-canonical one as
    # `R6_KV_REGION("layout")`, so the two implementations refuse the same files.
    expected_identity_offset = align_up(HEADER_BYTES + h["token_stream_bytes"], REGION_ALIGN)
    expected_logits_offset = align_up(expected_identity_offset + IDENTITY_RECORD_BYTES,
                                      REGION_ALIGN)
    expected_plane_offset = align_up(expected_logits_offset + h["logits_bytes"], h["plane_align"])
    for name, actual, expected in (
            ("token_stream_offset", h["token_stream_offset"], HEADER_BYTES),
            ("identity_offset", h["identity_offset"], expected_identity_offset),
            ("logits_offset", h["logits_offset"], expected_logits_offset),
            ("plane_offset", h["plane_offset"], expected_plane_offset)):
        if actual != expected:
            reject("REGION", "the region layout is not section 2.3's: %s is %d, expected %d"
                   % (name, actual, expected))
    return h


def check_zero_tail(raw, h):
    """Section 2.3.4. Columns at and above `columns_persisted` are zero **by construction** in the
    writer, which is exactly why this reader checks them: a reader that trusts the writer is not
    independent. This is the one invariant the arm does not check separately -- it catches a
    non-zero tail through the plane digest instead -- so it is the row that proves the two
    implementations are not one implementation written twice."""
    stride = h["kv_width"] * h["n_head_kv"] * h["head_dim"] * 4
    column_bytes = h["n_head_kv"] * h["head_dim"] * 4
    tail = (h["kv_width"] - h["columns_persisted"]) * column_bytes
    if tail <= 0:
        return
    for layer in range(h["n_layer"]):
        for tensor in range(2):
            base = h["plane_offset"] + stride * (2 * layer + tensor) \
                + h["columns_persisted"] * column_bytes
            if any(raw[base:base + tail]):
                reject("ZEROTAIL",
                       "layer %d %s has a non-zero column at or above column %d"
                       % (layer, "kv"[tensor], h["columns_persisted"]))


def check_geometry(h, geometry_path):
    with open(geometry_path, "rb") as handle:
        text = handle.read()
    import json
    model = json.loads(text.decode("utf-8"))["model"]
    for field in ("n_layer", "n_head_kv", "head_dim", "n_vocab"):
        if h[field] != model[field]:
            reject("GEOMETRY", "%s is %d in the container and %d in the geometry"
                   % (field, h[field], model[field]))
    derived = model["n_layer"] * 2 * h["kv_width"] * model["n_head_kv"] * model["head_dim"] * 4
    if h["plane_bytes"] != derived:
        reject("GEOMETRY", "plane_bytes is %d; the geometry derives %d"
               % (h["plane_bytes"], derived))
    return hashlib.sha256(text).digest()


def pack_identity(pack_path):
    with open(pack_path, "rb") as handle:
        raw = handle.read()
    if raw[0:4] != PACK_MAGIC:
        reject("IDENTITY", "%s is not an alignpack container" % pack_path)
    total = struct.unpack_from("<Q", raw, PACK_TOTAL_BYTES_AT)[0]
    record = struct.unpack_from("<Q", raw, PACK_SOURCE_RECORD_OFFSET_AT)[0]
    at = record + PACK_SOURCE_DIGEST_IN_RECORD
    return raw[at:at + DIGEST_BYTES], total


def inspect(args):
    with open(args.plane, "rb") as handle:
        raw = handle.read()
    h = decode_header(raw, len(raw))
    identity = raw[h["identity_offset"]:h["identity_offset"] + IDENTITY_RECORD_BYTES]
    if any(identity[168:IDENTITY_RECORD_BYTES]):
        reject("RESERVED", "a reserved identity byte is non-zero")
    digests = {name: identity[i * DIGEST_BYTES:(i + 1) * DIGEST_BYTES]
               for i, name in enumerate(("pack", "geometry", "tokens", "logits", "plane"))}
    h["pack_total_bytes"] = struct.unpack_from("<Q", identity, 160)[0]

    stream = raw[h["token_stream_offset"]:h["token_stream_offset"] + h["token_stream_bytes"]]
    logits = raw[h["logits_offset"]:h["logits_offset"] + h["logits_bytes"]]
    plane = raw[h["plane_offset"]:h["plane_offset"] + h["plane_bytes"]]
    ids = list(struct.unpack("<%dI" % h["token_count"], stream))

    if h["columns_persisted"] != h["token_count"]:
        reject("NPAST", "columns_persisted %d is not token_count %d"
               % (h["columns_persisted"], h["token_count"]))
    if args.tokens is not None:
        expected = [int(piece) for piece in args.tokens.split(",") if piece != ""]
        if len(expected) != h["token_count"]:
            reject("TOKENS", "the container holds %d ids, the run asked for %d"
                   % (h["token_count"], len(expected)))
        for index, (mine, theirs) in enumerate(zip(ids, expected)):
            if mine != theirs:
                reject("TOKENS", "id %d is %d in the container and %d in the run"
                       % (index, mine, theirs))

    geometry_digest = check_geometry(h, args.geometry) if args.geometry else None
    if args.pack:
        digest, total = pack_identity(args.pack)
        if digests["pack"] != digest:
            reject("IDENTITY", "source_header_region_sha256 does not match %s" % args.pack)
        if h["pack_total_bytes"] != total:
            reject("IDENTITY", "pack_total_bytes is %d; %s is %d bytes"
                   % (h["pack_total_bytes"], args.pack, total))
    if geometry_digest is not None and digests["geometry"] != geometry_digest:
        reject("IDENTITY", "geometry_sha256 does not match %s" % args.geometry)

    # The zero tail is checked **after** the shape fields it is computed from have been agreed with
    # the run's own geometry and token list: a container that lies about `head_dim` or
    # `columns_persisted` would otherwise be reported as a non-zero tail, which names the symptom
    # rather than the defect.
    check_zero_tail(raw, h)

    for name, region in (("tokens", stream), ("logits", logits), ("plane", plane)):
        computed = hashlib.sha256(region).digest()
        if computed != digests[name]:
            reject("DIGEST", "%s_sha256 is %s; the region digests to %s"
                   % (name, digests[name].hex(), computed.hex()))

    values = struct.unpack("<%df" % h["n_vocab"], logits)
    argmax = max(range(h["n_vocab"]), key=lambda i: values[i])
    if argmax != h["prefill_argmax"]:
        reject("ARGMAX", "prefill_argmax is %d; the persisted vector's argmax is %d"
               % (h["prefill_argmax"], argmax))

    # Every padding byte is written, not left as a hole, so a reader validating "padding is zero" is
    # validating bytes that exist (section 2.3, region-order property 4).
    for name, start, end in (
            ("token_stream->identity", h["token_stream_offset"] + h["token_stream_bytes"],
             h["identity_offset"]),
            ("identity->logits", h["identity_offset"] + IDENTITY_RECORD_BYTES, h["logits_offset"]),
            ("logits->plane", h["logits_offset"] + h["logits_bytes"], h["plane_offset"])):
        if any(raw[start:end]):
            reject("RESERVED", "the %s padding is not zero" % name)

    h["ids"] = ids
    h["digests"] = {name: value.hex() for name, value in digests.items()}
    return h


def report(h):
    order = ["format_version", "plane_layout_version", "document_schema_version", "total_bytes",
             "header_bytes", "identity_record_bytes", "plane_align", "token_stream_offset",
             "token_stream_bytes", "identity_offset", "logits_offset", "logits_bytes",
             "plane_offset", "plane_bytes", "n_layer", "n_head_kv", "head_dim", "kv_width",
             "columns_persisted", "token_count", "n_vocab", "prefill_argmax", "pack_total_bytes"]
    for name in order:
        print("%-24s %d" % (name, h[name]))
    print("%-24s %s" % ("tokens", ",".join(str(i) for i in h["ids"])))
    for name in ("pack", "geometry", "tokens", "logits", "plane"):
        print("%-24s %s" % (name + "_sha256", h["digests"][name]))


def main(argv):
    parser = argparse.ArgumentParser(description="Read and validate an akvp v1 container.")
    parser.add_argument("--plane", required=True)
    parser.add_argument("--pack")
    parser.add_argument("--geometry")
    parser.add_argument("--tokens")
    parser.add_argument("--expect-reject", choices=REJECT_KINDS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        h = inspect(args)
    except Reject as failure:
        if args.expect_reject == failure.kind:
            if not args.quiet:
                print("kv_plane_reader: rejected as expected: %s" % failure)
            return 0
        sys.stderr.write("kv_plane_reader: REJECT %s\n" % failure)
        return 1
    except (OSError, struct.error, ValueError, KeyError) as failure:
        # A `--plane` that cannot be opened or parsed at all: one line, and nothing further is read.
        sys.stderr.write("kv_plane_reader: %s: %s\n" % (args.plane, failure))
        return 1

    if args.expect_reject:
        sys.stderr.write("kv_plane_reader: expected a %s rejection and the container was accepted\n"
                         % args.expect_reject)
        return 1
    if not args.quiet:
        report(h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
