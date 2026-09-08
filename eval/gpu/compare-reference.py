#!/usr/bin/env python3
"""Compare the complete candidate traversal with an independent pinned GPU acquisition."""
from __future__ import annotations

import collections
import hashlib
import json
import math
import pathlib
import stat
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts"))
from gpu_backend_recipe import RecipeError
from gpu_qualification_deadline import checked, finite_f32, sha256_file
from gpu_qualification_records import parse_json_object, exact_keys, require_i32_array, bounded_text
from gpu_qualification_stream import Frame, NumericStream
from gpu_qualification_traversal import Router, Traversal


def regular(path, maximum):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= maximum:
        raise RecipeError("reference artifact is not a bounded single-link file")
    return info.st_size


class Reference:
    def __init__(self, root, traversal, deadline=None):
        self.deadline = deadline
        self.root = root
        self.traversal = traversal
        self.groups = collections.defaultdict(list)
        self.cursors = collections.Counter()
        self.used = set()
        self.hashes = {}
        self.identities = {}
        regular(root / "index.jsonl", 16 * 1024**2)
        raw = (root / "index.jsonl").read_bytes()
        self.index_sha256 = hashlib.sha256(raw).hexdigest()
        if not raw.endswith(b"\n"):
            raise RecipeError("reference index is truncated")
        for ordinal, line in enumerate(raw.splitlines()):
            row = parse_json_object(line, 65536)
            if set(row) != {"file", "step", "name", "type", "shape", "bytes"} \
                    or row["file"] != f"{ordinal}.bin" or type(row["step"]) is not int \
                    or not 0 <= row["step"] <= traversal.positions:
                raise RecipeError("reference index row identity is invalid")
            shape = row["shape"]
            if not isinstance(shape, list) or len(shape) != 4 \
                    or any(type(n) is not int or n < 1 for n in shape) \
                    or type(row["bytes"]) is not int or row["bytes"] != math.prod(shape) * 4 \
                    or regular(root / row["file"], 64 * 1024**2) != row["bytes"]:
                raise RecipeError("reference tensor shape or size is invalid")
            if type(row["type"]) is not int or type(row["name"]) is not str:
                raise RecipeError("reference tensor type/name is invalid")
            self.identities[row["file"]] = (root / row["file"]).stat()
            key = (row["step"], row["name"])
            self.groups[key].append(row)
        expected = set()
        for step in range(traversal.positions + 1):
            for layer in range(traversal.layers):
                columns = traversal.prompt if step == 0 and layer < traversal.layers - 1 else 1
                specs = [(f"l_out-{layer}", 0, traversal.embedding, (1, 1))]
                if traversal.model == 2:
                    specs += [(f"ffn_moe_probs-{layer}", 0, traversal.experts, (1, 1)),
                              (f"ffn_moe_topk-{layer}", 26, traversal.selected, (1, 1)),
                              (f"ffn_moe_weights-{layer}", 0, 1, (traversal.selected, 1))]
                for name, dtype, width, axes in specs:
                    key = (step, name)
                    expected.add(key)
                    rows = self.groups.get(key, [])
                    observed = 0
                    for row in rows:
                        shape = row["shape"]
                        valid = shape[0] == width and shape[3] == 1 and row["type"] == dtype
                        if name.startswith("ffn_moe_weights-"):
                            valid = valid and shape[1] == axes[0]
                            observed += shape[2]
                        else:
                            valid = valid and shape[2] == 1
                            observed += shape[1]
                        if not valid:
                            raise RecipeError("reference tensor does not match model geometry")
                    if observed != columns:
                        raise RecipeError("reference tensor columns are missing or duplicated")
            key = (step, "logits")
            expected.add(key)
            rows = self.groups.get(key, [])
            if len(rows) != 1 or rows[0]["shape"] != [traversal.vocabulary, 1, 1, 1] or rows[0]["type"] != 0:
                raise RecipeError("reference vocabulary row is missing or malformed")
        if set(self.groups) != expected:
            raise RecipeError("reference index has unexpected tensors")
        if sum(row["bytes"] for rows in self.groups.values() for row in rows) > 4 * 1024**3:
            raise RecipeError("reference closure exceeds its byte ceiling")

    def finish(self):
        if hashlib.sha256((self.root / "index.jsonl").read_bytes()).hexdigest() != self.index_sha256:
            raise RecipeError("reference index changed during comparison")
        for name, before in self.identities.items():
            path = self.root / name
            regular(path, 64 * 1024**2)
            after = path.stat()
            fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode", "st_nlink")
            if any(getattr(before, field) != getattr(after, field) for field in fields):
                raise RecipeError("reference tensor changed during comparison")

    def read(self, frame):
        if self.deadline is not None:
            self.deadline.check()
        names = {1: "logits", 6: "logits", 2: f"l_out-{frame.layer}",
                 3: f"ffn_moe_probs-{frame.layer}", 4: f"ffn_moe_topk-{frame.layer}",
                 5: f"ffn_moe_weights-{frame.layer}"}
        key = (frame.step, names[frame.kind])
        rows = self.groups[key]
        total = sum(row["bytes"] for row in rows)
        offset = 0 if frame.kind in (1, 6) else self.cursors[key] % total
        self.cursors[key] += frame.payload_bytes
        remaining = frame.payload_bytes
        result = bytearray()
        for row in rows:
            if offset >= row["bytes"]:
                offset -= row["bytes"]
                continue
            take = min(remaining, row["bytes"] - offset)
            path = self.root / row["file"]
            # Bound each read to one frame. Hash each independently acquired tensor once.
            if row["file"] not in self.hashes:
                self.hashes[row["file"]] = sha256_file(path, self.deadline)
            with path.open("rb") as source:
                source.seek(offset)
                data = source.read(take)
            if len(data) != take:
                raise RecipeError("reference tensor was truncated")
            result.extend(data)
            remaining -= take
            offset = 0
            if not remaining:
                self.used.add(key)
                return bytes(result)
        raise RecipeError("reference tensor does not contain the requested frame")


def compare(root, candidate, geometry, case, *, deadline=None):
    traversal = Traversal.derive(geometry, case)
    reference = Reference(root, traversal, deadline)
    regular(root / "production.json", 2 * 1024**2)
    production = exact_keys(parse_json_object((root / "production.json").read_bytes(), 2 * 1024**2),
        ("token_ids", "prompt_ids", "text", "tensor_records", "tensor_bytes"), "reference production")
    require_i32_array(production["token_ids"], "reference output tokens", minimum=1, maximum=128)
    require_i32_array(production["prompt_ids"], "reference prompt tokens", minimum=1, maximum=2048)
    bounded_text(production["text"], 0, 1048576, "reference output text")
    rows = [row for group in reference.groups.values() for row in group]
    if type(production["tensor_records"]) is not int or production["tensor_records"] != len(rows) \
            or type(production["tensor_bytes"]) is not int or production["tensor_bytes"] != sum(row["bytes"] for row in rows):
        raise RecipeError("reference production tensor closure differs")
    if production["token_ids"] != case["expected_token_ids"] \
            or production["prompt_ids"] != case["prompt_token_ids"] \
            or production["text"] != case["expected_output_utf8"] \
            or case["teacher_forced_token_ids"] != case["expected_token_ids"]:
        raise RecipeError("reference production does not match the frozen case")
    counts, mismatches = collections.Counter(), collections.Counter()
    with NumericStream(candidate, model=traversal.model, maximum_bytes=traversal.maximum_bytes, deadline=deadline) as stream:
        for instruction in traversal.instructions():
            if isinstance(instruction, Router):
                frames = [Frame(kind, instruction.layer, instruction.step, width, 1, width * 4,
                                instruction.ordinal + offset)
                          for offset, (kind, width) in enumerate(((3, instruction.experts),
                                                                  (4, instruction.selected), (5, instruction.selected)))]
            else:
                frames = [instruction]
            for expected in frames:
                if stream.read_frame() != expected:
                    raise RecipeError("candidate traversal differs from the independent projection")
                actual = bytearray()
                while len(actual) < expected.payload_bytes:
                    actual.extend(stream.read_payload())
                baseline = reference.read(expected)
                counts[expected.kind] += expected.width * expected.height
                if expected.kind != 4:
                    if not finite_f32(actual, deadline) or (actual != baseline and not finite_f32(baseline, deadline)):
                        raise RecipeError("nonfinite reference or candidate value")
                if actual != baseline:
                    mismatches[expected.kind] += sum(a != b for a, b in zip(
                        checked(struct.iter_unpack("<I", actual), deadline), checked(struct.iter_unpack("<I", baseline), deadline)))
        if stream.read_frame() is not None:
            raise RecipeError("candidate has extra frames")
        candidate_sha256 = stream.sha256
    if reference.used != set(reference.groups):
        raise RecipeError("independent reference has unconsumed tensors")
    reference.finish()
    return {"bitwise_equal": not mismatches, "scalar_counts": dict(counts),
            "bitwise_mismatches": dict(mismatches), "candidate_sha256": candidate_sha256,
            "reference_index_sha256": reference.index_sha256, "reference_tensors": reference.hashes}


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("usage: compare-reference.py REFERENCE_ROOT CANDIDATE_STREAM GEOMETRY CASE_JSON")
    result = compare(pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve(),
                     json.loads(pathlib.Path(sys.argv[3]).read_bytes()), json.loads(pathlib.Path(sys.argv[4]).read_bytes()))
    print(json.dumps(result, separators=(",", ":")))
    raise SystemExit(0 if result["bitwise_equal"] else 1)
