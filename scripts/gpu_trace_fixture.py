#!/usr/bin/env python3
"""Independent native-fixture framing, replay and routing checks for CPU/GPU traces."""
import math
from pathlib import Path
import struct
import sys

from gpu_qualification_stream import Frame, NumericStream
from gpu_qualification_traversal import Traversal, Router


def verify_production(root: Path) -> None:
    for model, name in ((1, "qwen-trace"), (2, "olmoe-trace")):
        with NumericStream(root / name, model=model, maximum_bytes=568) as stream:
            for step in range(3):
                assert stream.read_frame() == Frame(1, 0xffffffff, step, 32, 1, 128, step)
                values = struct.unpack("<32f", stream.read_payload())
                assert all(math.isfinite(value) for value in values)
            assert stream.read_frame() is None
            assert stream.verified and stream.consumed_bytes == 568


def verify_complete(root: Path) -> None:
    for model, name, experts, selected in ((1, "qwen-complete", 0, 0), (2, "olmoe-complete", 8, 3)):
        traversal = Traversal(model, 2, 8, 32, experts, selected, 2, 2, (0, 0, 0))
        production = []
        final_count = 0
        with NumericStream(root / name, model=model, maximum_bytes=traversal.maximum_bytes) as stream:
            for instruction in traversal.instructions():
                frames = [instruction]
                if isinstance(instruction, Router):
                    frames = [Frame(kind, instruction.layer, instruction.step, width, 1, width * 4,
                                    instruction.ordinal + offset)
                              for offset, (kind, width) in enumerate(((3, experts), (4, selected), (5, selected)))]
                for frame in frames:
                    assert stream.read_frame() == frame
                    payload = stream.read_payload()
                    assert len(payload) == frame.payload_bytes
                    if frame.kind == 4:
                        ids = struct.unpack("<" + "i" * selected, payload)
                        assert len(set(ids)) == selected and all(0 <= value < experts for value in ids)
                        assert [scores[value] for value in ids] == sorted(scores, reverse=True)[:selected]
                    else:
                        values = tuple(value[0] for value in struct.iter_unpack("<f", payload))
                        assert all(math.isfinite(value) for value in values)
                        if frame.kind == 1:
                            production.append(payload)
                        elif frame.kind == 3:
                            scores = values
                        elif frame.kind == 5:
                            assert values == tuple(scores[value] for value in ids)
                        elif frame.kind == 6:
                            if final_count < 3:
                                assert payload == production[final_count]
                            final_count += 1
            assert stream.read_frame() is None
            assert stream.verified and stream.consumed_bytes == traversal.maximum_bytes


if __name__ == "__main__":
    root = Path(sys.argv[1])
    verify_production(root)
    verify_complete(root)
