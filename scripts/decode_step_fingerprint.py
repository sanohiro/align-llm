#!/usr/bin/env python3
"""Gate G's load-bearing measurement (`docs/specs/r6-step-n.md` section 3.2).

`llama-eval-callback` does not print the token it sampled. What it does print, as the first node of
every decode graph, is

    embd = (f32) GET_ROWS(token_embd.weight{n_embd, n_vocab, 1, 1}, inp_tokens{1, 1, 1, 1})

which is *the embedding row of the token sampled at the previous graph*. `GET_ROWS` is a copy of a
weight row -- no arithmetic happens -- so if two runs agree on the token they agree on those bytes
exactly, and the only question is whether two **different** vocabulary rows can print identically.

That question is a measurement, not an assumption, and this module is where it is taken: it
dequantizes `token_embd.weight` row by row, formats each row exactly as the instrument's
`common_debug_print_tensor` does at a print limit of 3 -- the first three values, the last three,
both at `%12.4f` -- and counts the rows that share a fingerprint. A run may then claim gate G only
if no decoded id is a member of a colliding class, which `scripts/run-decode-step` checks per step.

The `sum = %f` line the instrument also prints is **recorded and not gated**, and that is a
deliberate refinement of the design's seven-field fingerprint. The sum is one `float` sequential
accumulation over `n_embd` dequantized values inside the reference build, so its last printed digit
is exposed to that build's floating-point contraction; the six printed values are copies of weight
bytes and are not. Section 5.1 records the measurement for both keys, and they select the same
classes, so gating on the six costs nothing and assumes less.

Usage:

    decode_step_fingerprint.py MODEL.gguf OUT.json [--ids 1,2,3]

`--ids` asks for the fingerprints of those vocabulary rows as well, which is what the runner
compares against the transcript.
"""

from __future__ import annotations

import collections
import json
import struct
import sys

QK_K = 256
BLOCK_Q4_K = 144
GGML_F32 = 0
GGML_F16 = 1
GGML_Q4_K = 12
TYPE_NAMES = {GGML_F32: "F32", GGML_F16: "F16", GGML_Q4_K: "Q4_K"}

# GGUF metadata value kinds. Only the scalar widths and the two composite kinds are needed to walk
# the header to the tensor table; nothing here interprets a value the tensor table does not need.
_SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<B",
           10: "<Q", 11: "<q", 12: "<d"}
_WIDTH = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


class Reader:
    def __init__(self, handle):
        self.handle = handle

    def u32(self):
        return struct.unpack("<I", self.handle.read(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.handle.read(8))[0]

    def text(self):
        return self.handle.read(self.u64()).decode("utf-8", "replace")

    def value(self, kind):
        if kind == 8:
            return self.text()
        if kind == 9:
            element, count = self.u32(), self.u64()
            if element == 8:
                return [self.text() for _ in range(count)]
            raw = self.handle.read(count * _WIDTH[element])
            return list(struct.unpack("<%d%s" % (count, _SCALAR[element][1]), raw))
        return struct.unpack(_SCALAR[kind], self.handle.read(_WIDTH[kind]))[0]


def locate(path, name):
    """The tensor's dimensions, ggml type, and absolute byte offset in the file."""
    with open(path, "rb") as handle:
        reader = Reader(handle)
        if handle.read(4) != b"GGUF":
            raise SystemExit("decode step fingerprint: %s is not a GGUF file" % path)
        reader.u32()
        tensor_count, kv_count = reader.u64(), reader.u64()
        metadata = {}
        for _ in range(kv_count):
            key = reader.text()
            metadata[key] = reader.value(reader.u32())
        found = None
        for _ in range(tensor_count):
            tensor = reader.text()
            dims = [reader.u64() for _ in range(reader.u32())]
            kind, offset = reader.u32(), reader.u64()
            if tensor == name:
                found = (dims, kind, offset)
        if found is None:
            raise SystemExit("decode step fingerprint: %s holds no %s" % (path, name))
        alignment = metadata.get("general.alignment", 32)
        position = handle.tell()
        data_start = (position + alignment - 1) // alignment * alignment
    dims, kind, offset = found
    return [int(d) for d in dims], int(kind), data_start + int(offset)


def dequantize_q4_k(raw, blocks, numpy):
    """`dequantize_row_q4_K`, vectorised, in ggml's own order and with its own arithmetic.

    A super-block is 256 elements in 144 bytes: `d` and `dmin` as f16, twelve six-bit scale/min
    pairs, and 128 packed nibbles. `get_scale_min_k4` unpacks the pairs, and each half-block is
    `d * sc * nibble - dmin * m` -- the multiply order matters and is ggml's.
    """
    rows = raw.shape[0]
    block = raw.reshape(rows, blocks, BLOCK_Q4_K)
    d = block[:, :, 0:2].copy().view(numpy.float16).astype(numpy.float32).reshape(rows, blocks)
    dmin = block[:, :, 2:4].copy().view(numpy.float16).astype(numpy.float32).reshape(rows, blocks)
    packed = block[:, :, 4:16]
    nibbles = block[:, :, 16:144]
    scale = numpy.empty((rows, blocks, 8), numpy.float32)
    minimum = numpy.empty((rows, blocks, 8), numpy.float32)
    for j in range(8):
        if j < 4:
            scale[:, :, j] = packed[:, :, j] & 63
            minimum[:, :, j] = packed[:, :, j + 4] & 63
        else:
            scale[:, :, j] = (packed[:, :, j + 4] & 0xF) | ((packed[:, :, j - 4] >> 6) << 4)
            minimum[:, :, j] = (packed[:, :, j + 4] >> 4) | ((packed[:, :, j] >> 6) << 4)
    out = numpy.empty((rows, blocks, QK_K), numpy.float32)
    for half in range(4):
        quant = nibbles[:, :, half * 32:(half + 1) * 32]
        low = (quant & 0xF).astype(numpy.float32)
        high = (quant >> 4).astype(numpy.float32)
        d1 = (d * scale[:, :, 2 * half])[:, :, None]
        m1 = (dmin * minimum[:, :, 2 * half])[:, :, None]
        d2 = (d * scale[:, :, 2 * half + 1])[:, :, None]
        m2 = (dmin * minimum[:, :, 2 * half + 1])[:, :, None]
        out[:, :, half * 64 + 0:half * 64 + 32] = d1 * low - m1
        out[:, :, half * 64 + 32:half * 64 + 64] = d2 * high - m2
    return out.reshape(rows, blocks * QK_K)


def measure(path, wanted):
    try:
        import numpy
    except ImportError:
        raise SystemExit("decode step fingerprint: numpy is unavailable, so gate G's injectivity "
                         "cannot be measured; the qualification refuses rather than claiming a "
                         "gate it did not check")
    dims, kind, offset = locate(path, "token_embd.weight")
    if kind not in TYPE_NAMES:
        raise SystemExit("decode step fingerprint: token_embd.weight is ggml type %d, which this "
                         "measurement does not dequantize" % kind)
    n_embd, n_vocab = dims[0], dims[1]
    if kind == GGML_Q4_K:
        if n_embd % QK_K:
            raise SystemExit("decode step fingerprint: n_embd %d is not a Q4_K super-block "
                             "multiple" % n_embd)
        blocks = n_embd // QK_K
        row_bytes = blocks * BLOCK_Q4_K
    elif kind == GGML_F16:
        blocks, row_bytes = 0, n_embd * 2
    else:
        blocks, row_bytes = 0, n_embd * 4

    six = collections.defaultdict(list)
    seven = collections.defaultdict(list)
    zero_rows = set()
    fingerprints = {}
    chunk = 4096
    with open(path, "rb") as handle:
        handle.seek(offset)
        for base in range(0, n_vocab, chunk):
            count = min(chunk, n_vocab - base)
            raw = numpy.frombuffer(handle.read(count * row_bytes), numpy.uint8)
            raw = raw.reshape(count, row_bytes)
            if kind == GGML_Q4_K:
                values = dequantize_q4_k(raw, blocks, numpy)
            elif kind == GGML_F16:
                values = raw.copy().view(numpy.float16).astype(numpy.float32)
            else:
                values = raw.copy().view(numpy.float32)
            # `common_debug_print_tensor` accumulates into a `float`, in index order, before it
            # prints anything. `cumsum` in float32 is that accumulation exactly; `sum` is not,
            # because numpy pairwise-reduces.
            totals = numpy.cumsum(values, axis=1, dtype=numpy.float32)[:, -1]
            head = values[:, 0:3]
            tail = values[:, n_embd - 3:n_embd]
            empty = ~numpy.any(values != 0.0, axis=1)
            for index in range(count):
                identifier = base + index
                printed = ["%12.4f" % head[index, 0], "%12.4f" % head[index, 1],
                           "%12.4f" % head[index, 2], "%12.4f" % tail[index, 0],
                           "%12.4f" % tail[index, 1], "%12.4f" % tail[index, 2]]
                total = "%f" % totals[index]
                key = "|".join(printed)
                six[key].append(identifier)
                seven[key + "|" + total].append(identifier)
                if empty[index]:
                    zero_rows.add(identifier)
                if identifier in wanted:
                    fingerprints[identifier] = {"printed": printed, "sum": total}

    classes = {key: ids for key, ids in six.items() if len(ids) > 1}
    colliding = sorted(identifier for ids in classes.values() for identifier in ids)
    seven_classes = [ids for ids in seven.values() if len(ids) > 1]
    return {
        "tensor": "token_embd.weight",
        "ggml_type": TYPE_NAMES[kind],
        "n_embd": n_embd,
        "n_vocab": n_vocab,
        "distinct_fingerprints": len(six),
        "collision_classes": len(classes),
        "colliding_ids": colliding,
        "colliding_id_count": len(colliding),
        "all_zero_rows": len(zero_rows),
        "colliding_ids_that_are_not_all_zero":
            sorted(identifier for identifier in colliding if identifier not in zero_rows),
        "distinct_fingerprints_with_sum": len(seven),
        "collision_classes_with_sum": len(seven_classes),
        "largest_class": max((len(ids) for ids in classes.values()), default=0),
        "fingerprints": {str(k): v for k, v in fingerprints.items()},
    }


def main(argv):
    if len(argv) < 3:
        raise SystemExit("usage: decode_step_fingerprint.py MODEL.gguf OUT.json [--ids 1,2,3]")
    wanted = set()
    if len(argv) >= 5 and argv[3] == "--ids" and argv[4]:
        wanted = {int(text) for text in argv[4].split(",")}
    report = measure(argv[1], wanted)
    with open(argv[2], "w", encoding="utf-8") as handle:
        json.dump(report, handle, sort_keys=True)
    print("decode step fingerprint: %d rows of %s, %d distinct fingerprints, %d collision "
          "class(es) covering %d ids, of which %d are not all-zero rows"
          % (report["n_vocab"], report["ggml_type"], report["distinct_fingerprints"],
             report["collision_classes"], report["colliding_id_count"],
             len(report["colliding_ids_that_are_not_all_zero"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
