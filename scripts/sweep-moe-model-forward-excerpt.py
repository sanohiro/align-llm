#!/usr/bin/env python3
"""R5E-MOE-MODEL-PREFILL checked-in transcript excerpt.

`docs/specs/r5e-moe-model-prefill.md` section 5.1. A whole-model `llama-eval-callback` transcript is
27,859 lines and ~1.9 MB, which is too large to check in, so `scripts/run-moe-model-forward` sweeps
the records that carry the capability's structure out of the transcript it just captured:

  * `embd` and `attn_norm-0`, the first two rows of the oracle table;
  * `kq-0`, whose declared `ne0` **is** the instrument's reduction width;
  * the sixteen `l_out-L` records, one per layer, which is the per-layer schedule as the instrument
    sees it;
  * layer 15's attention output projection, matched by its **source weight name** and never by
    `node_NN` (`r5a-dense-layer-forward.md` section 6, correction C21), and the two `GET_ROWS`
    records that follow it — the narrowing, on both residual branches;
  * `ffn_inp-15`, the first `{n_embd, 1}` node of the prefill;
  * `ffn_moe_topk-15`, the last layer's single-token routing decision;
  * `result_norm` and `result_output`, the head's two suffix-free rows.

The excerpt is compared hosted for **grammar, node identity, and layer coverage only** — its numbers
are the qualification's, so a stale excerpt cannot produce a false `PASS`.

    python3 scripts/sweep-moe-model-forward-excerpt.py TRANSCRIPT.txt OUT.txt [N_LAYER]
"""

import sys

PREFIX = "common_debug_cb_eval: "


def records(lines):
    """Every `common_debug_cb_eval:` record as `(name, op, source, start, end)`."""
    out = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith(PREFIX):
            index += 1
            continue
        separator = line.find(" = (")
        name = line[len(PREFIX):separator].strip()
        after = line.find(") ", separator + 4)
        open_paren = line.find("(", after + 2)
        op = line[after + 2:open_paren].strip()
        brace = line.find("{", open_paren)
        source = line[open_paren + 1:brace] if brace > 0 else ""
        start = index
        index += 1
        while index < len(lines) and not lines[index].startswith(PREFIX):
            index += 1
        end = index
        while end > start + 1 and lines[end - 1].strip() == "":
            end -= 1
        out.append((name, op, source, start, end))
    return out


def main(argv):
    if len(argv) not in (3, 4):
        sys.stderr.write(
            "usage: sweep-moe-model-forward-excerpt.py TRANSCRIPT.txt OUT.txt [N_LAYER]\n")
        return 2
    n_layer = int(argv[3]) if len(argv) == 4 else 16
    with open(argv[1], "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.read().split("\n")
    found = records(lines)
    wanted = [("embd", "GET_ROWS"), ("attn_norm-0", "MUL"), ("kq-0", "MUL_MAT")]
    wanted.extend(("l_out-%d" % layer, "ADD") for layer in range(n_layer))
    wanted.extend([("ffn_inp-%d" % (n_layer - 1), "ADD"),
                   ("ffn_moe_topk-%d" % (n_layer - 1), "VIEW"),
                   ("result_norm", "MUL"), ("result_output", "MUL_MAT")])

    picked = []
    seen = set()
    for name, op in wanted:
        for index, (record_name, record_op, _, start, end) in enumerate(found):
            if record_name == name and record_op == op and index not in seen:
                seen.add(index)
                picked.append(index)
                break
        else:
            sys.stderr.write("sweep: %s (%s) is absent from %s\n" % (name, op, argv[1]))
            return 1

    # The attention output projection of the last layer, matched by its **source weight name**: the
    # positional `node_NN` moves with the layer and with the flag set, so it is never the key. The
    # two records that follow it are the narrowing `GET_ROWS` pair, on both residual branches.
    weight = "blk.%d.attn_output.weight" % (n_layer - 1)
    for index, (_, record_op, source, _, _) in enumerate(found):
        if record_op == "MUL_MAT" and source.startswith(weight):
            for offset in range(3):
                if index + offset < len(found) and index + offset not in seen:
                    seen.add(index + offset)
                    picked.append(index + offset)
            break
    else:
        sys.stderr.write("sweep: no MUL_MAT over %s in %s\n" % (weight, argv[1]))
        return 1

    # The instrument's banner, when the capture carries one: `llama-eval-callback` writes it to
    # stderr, so a stdout-only transcript begins with the first record and must not repeat it.
    out = [] if lines[0].startswith(PREFIX) else [lines[0]]
    for index in sorted(picked):
        _, _, _, start, end = found[index]
        out.extend(lines[start:end])
    with open(argv[2], "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")
    sys.stderr.write("sweep: %d records -> %s\n" % (len(picked), argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
