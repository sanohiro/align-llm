#!/usr/bin/env python3
"""The two arms `scripts/run-ggml-spike` measures, selected from an alignpack `--pack` document.

`docs/specs/moe-prereq-discharge.md` section 3.5. The selection is **shape-driven**: it resolves by
`role_id` out of the document the run just wrote, and never from a model path, a file name, or an
environment variable the caller sets, because a qualification whose verdict does not depend on what
it measured is not a qualification (section 1.5 there).

`role_id` and not a tensor name: `docs/specs/r1c-olmoe-moe-ir.md` section 2.5.2 makes the role the
stable identity while a GGUF name is a model's own spelling.

It lives in its own file rather than inside the runner so that the rule has one owner and a hosted
test can run **it** rather than a copy of it: `scripts/run-ggml-spike` refuses before the selection
on any host without ggml, so a companion embedded in that runner could never be reached in CI.

    python3 scripts/ggml_spike_select.py PACK_DOCUMENT.json    # selection JSON to stdout
"""

import json
import sys

ROLE_ATTN_Q = 1


def select(document):
    """`{"dense": {...}, "expert": {...} | None, "identity": <hex>}`, or raise for a `FAIL`."""
    blocks = document["blocks"]

    dense = None
    for block in blocks:
        if block["kind"] != "AttentionBlock":
            continue
        for position, member in enumerate(block["members"]):
            if member["role_id"] == ROLE_ATTN_Q:
                dense = {"block": block["index"], "member": position}
                break
        if dense is not None:
            break
    if dense is None:
        # Every architecture this repository supports has one, so its absence is a defect and not a
        # shape this qualification may skip.
        raise ValueError("the pack holds no AttentionBlock with an attn_q member")

    # A model with no `ExpertBlock` is a legitimate shape — the dense arm still runs and the expert
    # arm prints one `N/A` line — so this is `None` rather than an error.
    expert = None
    for block in blocks:
        if block["kind"] == "ExpertBlock":
            expert = {"block": block["index"], "members": list(range(len(block["members"])))}
            break

    return {"dense": dense, "expert": expert,
            "identity": document["source"]["header_region_sha256"]}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: ggml_spike_select.py PACK_DOCUMENT.json\n")
        return 2
    with open(argv[1], "r", encoding="utf-8") as handle:
        document = json.load(handle)
    try:
        selection = select(document)
    except ValueError as error:
        sys.stderr.write("ggml spike qualification: FAIL %s\n" % error)
        return 1
    json.dump(selection, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
