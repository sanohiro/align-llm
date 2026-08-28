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


class SelectionError(Exception):
    """A named refusal. Every one of these becomes one `FAIL` line naming what was missing.

    A pack document with a missing or mistyped field is a defect of the producer, not a shape this
    selector may skip, and a `KeyError` traceback is not a qualification verdict: the runner would
    still exit non-zero, but the operator would have to read Python internals to learn that the
    document lacked `blocks`.
    """


def field(record, key, what):
    """`record[key]`, or a named `SelectionError` — never a `KeyError` or a `TypeError`."""
    if not isinstance(record, dict):
        raise SelectionError("%s is %s, not an object" % (what, type(record).__name__))
    if key not in record:
        raise SelectionError("%s has no %r" % (what, key))
    return record[key]


def select(document):
    """`{"dense": {...}, "expert": {...} | None, "identity": <hex>}`, or raise for a `FAIL`."""
    blocks = field(document, "blocks", "the pack document")
    if not isinstance(blocks, list):
        raise SelectionError("the pack document's `blocks` is not an array")

    dense = None
    for position, block in enumerate(blocks):
        where = "block %d" % position
        if field(block, "kind", where) != "AttentionBlock":
            continue
        for member_position, member in enumerate(field(block, "members", where)):
            if field(member, "role_id", "%s member %d" % (where, member_position)) == ROLE_ATTN_Q:
                dense = {"block": field(block, "index", where), "member": member_position}
                break
        if dense is not None:
            break
    if dense is None:
        # Every architecture this repository supports has one, so its absence is a defect and not a
        # shape this qualification may skip.
        raise SelectionError("the pack holds no AttentionBlock with an attn_q member")

    # A model with no `ExpertBlock` is a legitimate shape — the dense arm still runs and the expert
    # arm prints one `N/A` line — so this is `None` rather than an error.
    #
    # `last_block` is the **last** `ExpertBlock`, and it is what gives the real-model arm a plane
    # whose `slice_index` is not zero: every member of the first `ExpertBlock` is plane 0 of its
    # stacked tensor, so without it no real model ever exercises interior addressing at a plane
    # index greater than zero (section 5.4). It is `None` for a container holding exactly one
    # `ExpertBlock`, where the extra run would repeat the first arm rather than add evidence.
    expert = None
    last_expert_index = None
    for position, block in enumerate(blocks):
        where = "block %d" % position
        if field(block, "kind", where) != "ExpertBlock":
            continue
        index = field(block, "index", where)
        if expert is None:
            expert = {"block": index,
                      "members": list(range(len(field(block, "members", where))))}
        last_expert_index = index
    if expert is not None:
        expert["last_block"] = last_expert_index if last_expert_index != expert["block"] else None

    source = field(document, "source", "the pack document")
    return {"dense": dense, "expert": expert,
            "identity": field(source, "header_region_sha256", "the pack document's `source`")}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: ggml_spike_select.py PACK_DOCUMENT.json\n")
        return 2
    try:
        with open(argv[1], "r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        sys.stderr.write("ggml spike qualification: FAIL the pack document %s is unreadable: %s\n"
                         % (argv[1], error))
        return 1
    try:
        selection = select(document)
    except SelectionError as error:
        sys.stderr.write("ggml spike qualification: FAIL %s\n" % error)
        return 1
    json.dump(selection, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
