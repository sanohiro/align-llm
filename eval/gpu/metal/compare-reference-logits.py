#!/usr/bin/env python3
"""Compare all final-logit frames with the independent same-device diagnostic's raw rows."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "scripts"))
from gpu_qualification_stream import NumericStream, MAX_BYTES

if len(sys.argv) != 4:
    raise SystemExit("usage: compare-reference-logits.py MODEL_NUMBER NUMERIC_STREAM REFERENCE_F32")
model = int(sys.argv[1])
reference = pathlib.Path(sys.argv[3])
rows = 0
scalars = 0
with reference.open("rb") as raw, NumericStream(
        pathlib.Path(sys.argv[2]).resolve(), model=model, maximum_bytes=MAX_BYTES) as stream:
    while (frame := stream.read_frame()) is not None:
        compare = frame.kind in (1, 6)
        if compare:
            if reference.stat().st_size % frame.payload_bytes != 0:
                raise SystemExit("reference size does not contain complete vocabulary rows")
            raw.seek(frame.step * frame.payload_bytes)
            rows += 1
            scalars += frame.width
        remaining = frame.payload_bytes
        while remaining:
            chunk = stream.read_payload()
            if compare and raw.read(len(chunk)) != chunk:
                raise SystemExit(f"FAIL: final logits differ at ordinal {frame.ordinal}, step {frame.step}")
            remaining -= len(chunk)
if not rows:
    raise SystemExit("FAIL: no final-logit frames were compared")
print(f"PASS: {rows} production/diagnostic final-logit rows, {scalars} bitwise-identical F32 scalars")
print("Layer and routing frames were structurally consumed; this is not full qualification.")
