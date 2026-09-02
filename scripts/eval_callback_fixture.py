#!/usr/bin/env python3
"""R2A-EXPERT-TRACE-CAPTURE synthetic corpus (`docs/specs/r2a-expert-trace.md` section 4.1).

The generator renders llama.cpp eval-callback transcripts from its own copy of the section 2.2
format string and computes every expected value — every selection and every locality aggregate —
in Python. It imports nothing from `src/` and re-derives nothing from the parser under test, which
is the whole point: two independent implementations of one stated grammar.

Usage: eval_callback_fixture.py OUTPUT_DIR
"""

import json
import os
import sys
from pathlib import Path

WINDOW_BYTES = 1048576
MAX_LINE_BYTES = 65536
MAX_TRANSCRIPT_BYTES = 68719476736
MAX_GRAPHS = 65536
MAX_NODES_PER_GRAPH = 8192
MAX_LAYERS = 1024
MAX_EXPERTS = 1024
MAX_EXPERTS_USED = 64
MAX_TOKENS_PER_GRAPH = 1048576
MAX_SELECTIONS = 1048576
MAX_REUSE_WINDOW = 64
MAX_NAME_BYTES = 256
CONTRACT_BUILD = 10566
TRUNCATION_HALF = 3
TRUNCATION_PRINTED = 6
WINDOWS = (1, 2, 4, 8, 16, 32, 64)

# Section 2.2 finding 6, byte for byte.
A3_OPEN = "    ["
A3_CLOSE = "    ]"
A2_OPEN = "        ["
A2_CLOSE = "        ],"
A2_TRUNC = "        ..., "
A1_TRUNC = "            ..., "
ROW_OPEN = "            ["
ROW_CLOSE = "  ],"
A0_MARK = "   ..."


def printed_indices(ne):
    if ne <= TRUNCATION_PRINTED:
        return list(range(ne))
    return [0, 1, 2, ne - 3, ne - 2, ne - 1]


def truncated(ne):
    return ne > TRUNCATION_PRINTED


def fmt_dims(dims):
    return ", ".join(str(d) for d in dims)


class Block:
    """One callback record: its header fields and the value block that follows it."""

    def __init__(self, name, dtype, op, src0, src1, ne, value=None, full_axes=()):
        self.name = name
        self.dtype = dtype
        self.op = op
        self.src0 = src0
        self.src1 = src1
        self.ne = list(ne)
        # `value(i0, i1, i2, i3) -> float`; defaults to a deterministic ramp.
        self.value = value or (lambda i0, i1, i2, i3: 0.0)
        # R2c's patched `ffn_moe_topk` prints selected axes in full. Every other block retains the
        # build-10566 three-plus-three form. The expected document consumes this fixture-owned
        # choice directly; it does not infer it from the parser under test.
        self.full_axes = frozenset(full_axes)

    def indices(self, axis):
        if axis in self.full_axes:
            return list(range(self.ne[axis]))
        return printed_indices(self.ne[axis])

    def axis_truncated(self, axis):
        return self.ne[axis] > TRUNCATION_PRINTED and axis not in self.full_axes

    def header(self):
        src0 = "%s{%s}" % (self.src0[0], fmt_dims(self.src0[1]))
        src1 = "" if self.src1 is None else "%s{%s}" % (self.src1[0], fmt_dims(self.src1[1]))
        # `%s: %24s = (%s) %10s(%s{%s}, %s}) = {%s}` with the `%s{%s}` source-operand helper.
        return "common_debug_cb_eval: %24s = (%s) %10s(%s, %s}) = {%s}" % (
            self.name, self.dtype, self.op, src0, src1, fmt_dims(self.ne))

    def body(self):
        ne0, ne1, ne2, ne3 = self.ne
        lines = []
        total = 0.0
        for i3 in range(ne3):
            lines.append(A3_OPEN)
            for position, i2 in enumerate(self.indices(2)):
                if self.axis_truncated(2) and position == TRUNCATION_HALF:
                    lines.append(A2_TRUNC)
                lines.append(A2_OPEN)
                for row_position, i1 in enumerate(self.indices(1)):
                    if self.axis_truncated(1) and row_position == TRUNCATION_HALF:
                        lines.append(A1_TRUNC)
                    parts = []
                    for element_position, i0 in enumerate(self.indices(0)):
                        if self.axis_truncated(0) and element_position == TRUNCATION_HALF:
                            parts.append(A0_MARK)
                        element = self.value(i0, i1, i2, i3)
                        total += element
                        parts.append("%12.4f" % element)
                    lines.append(ROW_OPEN + ", ".join(parts) + ROW_CLOSE)
                lines.append(A2_CLOSE)
            lines.append(A3_CLOSE)
        lines.append("    sum = %f" % total)
        return lines

    def lines(self):
        return [self.header()] + self.body()


def render(graphs, trailing_newline=True, separator=""):
    """One transcript. `separator` is the ignorable line emitted between blocks; the real instrument
    emits one empty line, which lands in `source.skipped_line_count`."""
    out = []
    for blocks in graphs:
        for block in blocks:
            out.extend(block.lines())
            if separator is not None:
                out.append(separator)
    text = "\n".join(out)
    if trailing_newline:
        text += "\n"
    return text


# ---------------------------------------------------------------------------------------------
# Graph shapes.

def dense_graph(n_layer, n_tokens, embd=3584):
    blocks = [Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [embd, 152064, 1, 1]),
                    ("inp_tokens", [n_tokens, 1, 1, 1]), [embd, n_tokens, 1, 1])]
    for layer in range(n_layer):
        blocks.append(Block("attn_norm-%d" % layer, "f32", "RMS_NORM",
                            ("embd", [embd, n_tokens, 1, 1]), None, [embd, n_tokens, 1, 1]))
        blocks.append(Block("ffn_norm-%d" % layer, "f32", "RMS_NORM",
                            ("attn_norm-%d" % layer, [embd, n_tokens, 1, 1]), None,
                            [embd, n_tokens, 1, 1]))
        blocks.append(Block("ffn_gate-%d" % layer, "f32", "MUL_MAT",
                            ("blk.%d.ffn_gate.weight" % layer, [embd, 18944, 1, 1]),
                            ("ffn_norm-%d" % layer, [embd, n_tokens, 1, 1]),
                            [18944, n_tokens, 1, 1]))
        blocks.append(Block("ffn_up-%d" % layer, "f32", "MUL_MAT",
                            ("blk.%d.ffn_up.weight" % layer, [embd, 18944, 1, 1]),
                            ("ffn_norm-%d" % layer, [embd, n_tokens, 1, 1]),
                            [18944, n_tokens, 1, 1]))
        blocks.append(Block("ffn_swiglu-%d" % layer, "f32", "SWIGLU",
                            ("ffn_gate-%d" % layer, [18944, n_tokens, 1, 1]), None,
                            [18944, n_tokens, 1, 1]))
        blocks.append(Block("l_out-%d" % layer, "f32", "ADD",
                            ("ffn_swiglu-%d" % layer, [18944, n_tokens, 1, 1]),
                            ("embd", [embd, n_tokens, 1, 1]), [embd, n_tokens, 1, 1]))
    blocks.append(Block("result_norm", "f32", "RMS_NORM", ("l_out", [embd, 1, 1, 1]), None,
                        [embd, 1, 1, 1]))
    blocks.append(Block("result_output", "f32", "MUL_MAT",
                        ("output.weight", [embd, 152064, 1, 1]),
                        ("result_norm", [embd, 1, 1, 1]), [152064, 1, 1, 1]))
    return blocks


class Router:
    """A deterministic router. The expert chosen at `(graph, layer, token, slot)` is a pure function
    of the seed, so the generator knows every selection before the parser has read a byte."""

    def __init__(self, seed, n_expert, n_expert_used):
        self.seed = seed
        self.n_expert = n_expert
        self.n_expert_used = n_expert_used

    def experts(self, graph, layer, token):
        state = (self.seed * 1000003) ^ (graph * 97 + layer * 7919 + token * 104729)
        chosen = []
        while len(chosen) < self.n_expert_used:
            state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 63) - 1)
            candidate = (state >> 17) % self.n_expert
            # A router picks distinct experts; a duplicate would make the reuse denominator lie.
            while candidate in chosen:
                candidate = (candidate + 1) % self.n_expert
            chosen.append(candidate)
        return chosen

    def weight_ten_thousandths(self, graph, layer, token, slot):
        expert = self.experts(graph, layer, token)[slot]
        # A deterministic selected gating weight with exact four-decimal representation. It is
        # deliberately not a function of frequency alone, so the score policy's fixture can
        # distinguish routing mass from demand count.
        return 1000 + ((self.seed * 101 + graph * 211 + layer * 307 + token * 401
                        + slot * 503 + expert * 601) % 8001)


def moe_graph(n_layer, n_tokens, router, graph_ordinal, embd=3584, probs=True, logits=True,
              reduced_tail=0, reduced_layer=None, full_topk=False):
    """`reduced_tail` models build 10566's real MoE shape: llama.cpp applies the output-token
    `GET_ROWS` reduction before the *last* layer's feed-forward, so that layer's `ffn_moe_topk`
    carries a shorter token axis than the graph and the leaf naming the retained tokens is never
    printed.

    `reduced_layer` shortens a **middle** layer's axis instead, which no build 10566 reduction can
    produce. The parser must refuse it with `R2_TOKEN_COUNT` rather than silently drop a whole
    interior layer's routing (section 6, item 20)."""
    n_expert = router.n_expert
    used = router.n_expert_used
    blocks = [Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [embd, 152064, 1, 1]),
                    ("inp_tokens", [n_tokens, 1, 1, 1]), [embd, n_tokens, 1, 1])]
    for layer in range(n_layer):
        layer_tokens = reduced_tail if (reduced_tail and layer == n_layer - 1) else n_tokens
        if reduced_layer is not None and layer == reduced_layer:
            layer_tokens = 1
        blocks.append(Block("ffn_norm-%d" % layer, "f32", "RMS_NORM",
                            ("embd", [embd, n_tokens, 1, 1]), None, [embd, layer_tokens, 1, 1]))
        if logits:
            blocks.append(Block("ffn_moe_logits-%d" % layer, "f32", "MUL_MAT",
                                ("blk.%d.ffn_gate_inp.weight" % layer, [embd, n_expert, 1, 1]),
                                ("ffn_norm-%d" % layer, [embd, layer_tokens, 1, 1]),
                                [n_expert, layer_tokens, 1, 1]))
        if probs:
            blocks.append(Block("ffn_moe_probs-%d" % layer, "f32", "SOFT_MAX",
                                ("ffn_moe_logits-%d" % layer, [n_expert, layer_tokens, 1, 1]), None,
                                [n_expert, layer_tokens, 1, 1]))

        def value(i0, i1, i2, i3, layer=layer):
            return float(router.experts(graph_ordinal, layer, i1)[i0])

        blocks.append(Block("ffn_moe_topk-%d" % layer, "i32", "TOP_K",
                            ("ffn_moe_probs-%d" % layer, [n_expert, layer_tokens, 1, 1]), None,
                            [used, layer_tokens, 1, 1], value,
                            full_axes=(0, 1, 2) if full_topk else ()))

        def weight(i0, i1, i2, i3, layer=layer):
            return router.weight_ten_thousandths(graph_ordinal, layer, i2, i1) / 10000.0

        blocks.append(Block("ffn_moe_weights-%d" % layer, "f32", "GET_ROWS",
                            ("ffn_moe_probs-%d (reshaped)" % layer,
                             [1, n_expert, layer_tokens, 1]),
                            ("ffn_moe_topk-%d" % layer, [used, layer_tokens, 1, 1]),
                            [1, used, layer_tokens, 1], weight,
                            full_axes=(0, 1, 2) if full_topk else ()))
        blocks.append(Block("ffn_moe_out-%d" % layer, "f32", "ADD",
                            ("ffn_moe_topk-%d" % layer, [used, layer_tokens, 1, 1]),
                            ("ffn_norm-%d" % layer, [embd, layer_tokens, 1, 1]),
                            [embd, layer_tokens, 1, 1]))
    blocks.append(Block("result_output", "f32", "MUL_MAT",
                        ("output.weight", [embd, 152064, 1, 1]),
                        ("result_norm", [embd, 1, 1, 1]), [152064, 1, 1, 1]))
    return blocks


# ---------------------------------------------------------------------------------------------
# The expected document, computed from the emitted model rather than by re-parsing it.

def family_of(name):
    cut = name.rfind("-")
    if cut <= 0 or cut + 1 >= len(name):
        return None, -1
    suffix = name[cut + 1:]
    if not suffix.isdigit():
        return None, -1
    return name[:cut], int(suffix)


def token_axis(blocks):
    """The graph's token axis and the set of token-reduced layers, by the parser's own rule: the
    first `embd` or `ffn_moe_topk` block establishes the axis, and a later `ffn_moe_topk` whose
    axis is strictly shorter is token-reduced (section 6, item 20).

    Only a *tail* reduction is representable here: a shorter axis at any layer the graph later
    exceeds is `R2_TOKEN_COUNT`, so it never reaches an expected document."""
    axis = None
    reduced = set()
    for block in blocks:
        family, layer = family_of(block.name)
        is_topk = family == "ffn_moe_topk"
        if block.name != "embd" and not is_topk:
            continue
        claim = block.ne[1]
        if axis is None:
            axis = claim
        elif claim != axis and is_topk and claim < axis:
            reduced.add(layer)
    return axis, reduced


def expected_selections(graphs):
    rows = []
    for ordinal, blocks in enumerate(graphs):
        _, reduced = token_axis(blocks)
        weights = {family_of(block.name)[1]: block for block in blocks
                   if family_of(block.name)[0] == "ffn_moe_weights"}
        for block in blocks:
            family, layer = family_of(block.name)
            if family != "ffn_moe_topk":
                continue
            if layer in reduced:
                continue
            weight_block = weights[layer]
            ne0, ne1 = block.ne[0], block.ne[1]
            for row_position, i1 in enumerate(block.indices(1)):
                for element_position, i0 in enumerate(block.indices(0)):
                    rows.append({
                        "graph": ordinal,
                        "layer": layer,
                        "token": i1,
                        "slot": i0,
                        "expert": int(round(block.value(i0, i1, 0, 0))),
                        "router_weight_ten_thousandths":
                            int(round(weight_block.value(0, i0, i1, 0) * 10000)),
                    })
    return rows


def naive_locality(selections, graph_phase, topk_layers):
    """The section 4.3 oracle: nested loops over adjacent pairs and set intersections, deliberately
    unlike the parser's single sorted sweep."""
    by_group = {}
    for row in selections:
        by_group.setdefault((row["graph"], row["layer"], row["token"]), set()).add(row["expert"])

    def triple(keys):
        pairs = numerator = denominator = 0
        for (graph, layer, token) in sorted(keys):
            following = (graph, layer, token + 1)
            if following not in keys:
                continue
            pairs += 1
            numerator += len(by_group[(graph, layer, token)] & by_group[following])
            denominator += len(by_group[following])
        return pairs, numerator, denominator

    def rendered(pairs, numerator, denominator):
        return {
            "adjacent_pair_count": pairs,
            "reuse_numerator": numerator if pairs else None,
            "reuse_denominator": denominator if pairs else None,
            "reuse_per_mille": (numerator * 1000) // denominator if pairs and denominator else None,
        }

    keys = set(by_group)
    pairs, numerator, denominator = triple(keys)

    per_layer = []
    for layer in sorted(set(topk_layers)):
        layer_keys = {k for k in keys if k[1] == layer}
        lp, ln, ld = triple(layer_keys)
        histogram = {}
        for row in selections:
            if row["layer"] == layer:
                histogram[row["expert"]] = histogram.get(row["expert"], 0) + 1
        entry = {"layer": layer}
        entry.update(rendered(lp, ln, ld))
        entry["histogram"] = [[expert, histogram[expert]] for expert in sorted(histogram)]
        per_layer.append(entry)

    working_set = []
    for width in WINDOWS:
        samples = unique_sum = 0
        for (graph, layer, token) in sorted(keys):
            run = [(graph, layer, token - offset) for offset in range(width)]
            if not all(entry in keys for entry in run):
                continue
            samples += 1
            union = set()
            for entry in run:
                union |= by_group[entry]
            unique_sum += len(union)
        working_set.append({
            "window": width,
            "sample_count": samples,
            "unique_sum": unique_sum,
            "unique_mean_per_mille": (unique_sum * 1000) // samples if samples else None,
        })

    phase_split = {}
    for name, code in (("prefill", "prefill"), ("decode", "decode")):
        if code not in graph_phase.values():
            phase_split[name] = None
            continue
        phase_keys = {k for k in keys if graph_phase.get(k[0]) == code}
        phase_split[name] = rendered(*triple(phase_keys))

    document = {"adjacent_pair_count": pairs}
    document.update(rendered(pairs, numerator, denominator))
    del document["adjacent_pair_count"]
    result = {
        "adjacent_pair_count": pairs,
        "reuse_numerator": numerator if pairs else None,
        "reuse_denominator": denominator if pairs else None,
        "reuse_per_mille": (numerator * 1000) // denominator if pairs and denominator else None,
        "per_layer": per_layer,
        "working_set": working_set,
        "phase_split": phase_split,
    }
    return result


def expected_document(path, graphs, text, separator=""):
    names = []
    ops = []
    families = []
    plains = []
    topk_layers = []
    reduced_layers = []
    n_layer = -1
    moe_present = False
    dense_present = False
    n_expert = None
    n_expert_source = None
    n_expert_used = None
    for blocks in graphs:
        _, reduced = token_axis(blocks)
        reduced_layers.extend(reduced)
        for block in blocks:
            if block.name not in names:
                names.append(block.name)
                family, layer = family_of(block.name)
                if family is None:
                    plains.append(block.name)
                else:
                    families.append(family)
            if block.op not in ops:
                ops.append(block.op)
            family, layer = family_of(block.name)
            if family is not None:
                n_layer = max(n_layer, layer + 1)
                if family == "ffn_moe_topk":
                    moe_present = True
                    if layer not in reduced:
                        topk_layers.append(layer)
                    n_expert_used = block.ne[0]
                if family in ("ffn_gate", "ffn_up", "ffn_swiglu"):
                    dense_present = True
    for blocks in graphs:
        for block in blocks:
            family, _ = family_of(block.name)
            if family == "ffn_moe_probs" and n_expert is None:
                n_expert, n_expert_source = block.ne[0], "ffn_moe_probs"
    if n_expert is None:
        for blocks in graphs:
            for block in blocks:
                family, _ = family_of(block.name)
                if family == "ffn_moe_logits" and n_expert is None:
                    n_expert, n_expert_source = block.ne[0], "ffn_moe_logits"
    if not moe_present:
        n_expert = None
        n_expert_source = None
        n_expert_used = None

    graph_rows = []
    graph_phase = {}
    for ordinal, blocks in enumerate(graphs):
        n_tokens, _ = token_axis(blocks)
        observed = printed_indices(n_tokens)
        for block in blocks:
            family, layer = family_of(block.name)
            if family == "ffn_moe_topk" and layer not in token_axis(blocks)[1]:
                observed = block.indices(1)
                break
        phase = "prefill" if n_tokens > 1 else ("single_token_first_graph" if ordinal == 0 else "decode")
        graph_phase[ordinal] = phase
        graph_rows.append({
            "ordinal": ordinal,
            "n_tokens": n_tokens,
            "phase": phase,
            "tokens_observed": len(observed),
            "tokens_truncated": len(observed) != n_tokens,
            "observed_token_indices": observed,
            "node_count": len(blocks),
        })

    selections = expected_selections(graphs)
    encoded = text.encode("utf-8")
    line_count = encoded.count(b"\n") + (0 if encoded.endswith(b"\n") or not encoded else 1)
    callback_lines = sum(len(blocks) for blocks in graphs)
    skipped = line_count - sum(len(block.lines()) for blocks in graphs for block in blocks)

    if moe_present:
        locality = naive_locality(selections, graph_phase, topk_layers)
    else:
        locality = {
            "adjacent_pair_count": 0,
            "reuse_numerator": None,
            "reuse_denominator": None,
            "reuse_per_mille": None,
            "per_layer": [],
            "working_set": [],
            "phase_split": {"prefill": None, "decode": None},
        }

    shape_class = "moe-ffn" if moe_present else ("dense-ffn" if dense_present else "unknown")
    shape_basis = ("ffn_moe_topk present" if moe_present else
                   ("ffn_gate/ffn_up/ffn_swiglu present, ffn_moe_topk absent" if dense_present else
                    "ffn_moe_topk absent, no dense feed-forward family present"))

    return {
        "schema_version": 2,
        "kind": "R2_ACTIVATION_TRACE",
        "path": path,
        "status": "ok",
        "error_code": "",
        "error_detail": "",
        "source": {
            "file_size": len(encoded),
            "line_count": line_count,
            "bytes_read": {"$bytes_read": len(encoded)},
            "callback_line_count": callback_lines,
            "skipped_line_count": skipped,
        },
        "run": {
            "instrument": "llama-eval-callback",
            "build": None,
            "build_source": "absent",
            "contract_build": CONTRACT_BUILD,
            "build_matches_contract": None,
            "version_line": None,
        },
        "graph": {
            "graph_count": len(graphs),
            # A transcript with no `-N` suffixed node supplies no layer count at all, and the
            # document says `null` rather than a sentinel a reader cannot tell from a real value.
            "n_layer": n_layer if n_layer >= 0 else None,
            "node_families": sorted(set(families)),
            "unsuffixed_nodes": sorted(set(plains)),
            "ops": sorted(set(ops)),
            "shape_class": shape_class,
            "shape_class_basis": shape_basis,
        },
        "moe": {
            "present": moe_present,
            "n_expert": n_expert,
            "n_expert_used": n_expert_used,
            "n_expert_source": n_expert_source,
            "topk_layers": sorted(set(topk_layers)),
            "token_reduced_layers": sorted(set(reduced_layers)),
            "slots_truncated": any(
                family_of(block.name)[0] == "ffn_moe_topk" and block.axis_truncated(0)
                for blocks in graphs for block in blocks),
        },
        "graphs": graph_rows,
        "selections": selections,
        "locality": locality,
    }


# ---------------------------------------------------------------------------------------------
# The corpus.

def mutate(text, old, new, count=1):
    if old not in text:
        raise SystemExit("eval_callback_fixture: mutation target %r absent" % old)
    return text.replace(old, new, count)


def transform_first_topk_row(text, transform):
    lines = text.splitlines(keepends=True)
    in_topk = False
    for index, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if line.startswith("common_debug_cb_eval:"):
            in_topk = "ffn_moe_topk-" in line
        elif in_topk and line.startswith(ROW_OPEN) and line.endswith(ROW_CLOSE):
            body = line[len(ROW_OPEN):-len(ROW_CLOSE)]
            ending = "\n" if raw.endswith("\n") else ""
            lines[index] = ROW_OPEN + transform(body) + ROW_CLOSE + ending
            return "".join(lines)
    raise SystemExit("eval_callback_fixture: no top-k row to transform")


def transform_first_weight_row(text, transform):
    lines = text.splitlines(keepends=True)
    in_weight = False
    for index, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if line.startswith("common_debug_cb_eval:"):
            in_weight = "ffn_moe_weights-" in line
        elif in_weight and line.startswith(ROW_OPEN) and line.endswith(ROW_CLOSE):
            body = line[len(ROW_OPEN):-len(ROW_CLOSE)]
            ending = "\n" if raw.endswith("\n") else ""
            lines[index] = ROW_OPEN + transform(body) + ROW_CLOSE + ending
            return "".join(lines)
    raise SystemExit("eval_callback_fixture: no router-weight row to transform")


def change_first_topk_token_row(text, duplicate):
    lines = text.splitlines(keepends=True)
    in_topk = False
    for index, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if line.startswith("common_debug_cb_eval:"):
            in_topk = "ffn_moe_topk-" in line
        elif in_topk and line.startswith(ROW_OPEN) and line.endswith(ROW_CLOSE):
            if duplicate:
                lines.insert(index, raw)
            else:
                del lines[index]
            return "".join(lines)
    raise SystemExit("eval_callback_fixture: no top-k token row to change")


def emit(cases, root, name, text, expect="error", code=None, detail=None, asserts=None,
         document=None, binary=None):
    target = root / (name + ".txt")
    if binary is not None:
        target.write_bytes(binary)
    else:
        target.write_text(text, encoding="utf-8")
    case = {"name": name, "file": target.name, "expect": expect}
    if code is not None:
        case["error_code"] = code
    if detail is not None:
        case["error_detail"] = detail
    if asserts:
        case["asserts"] = asserts
    if document is not None:
        case["document"] = document
    cases.append(case)


def positive(cases, root, name, graphs, separator="", trailing_newline=True, extra=None,
             asserts=None):
    text = render(graphs, trailing_newline=trailing_newline, separator=separator)
    if extra is not None:
        text = extra(text)
    document = expected_document(str((root / (name + ".txt")).resolve()), graphs, text,
                                 separator=separator)
    emit(cases, root, name, text, expect="ok", document=document, asserts=asserts)
    return text


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: eval_callback_fixture.py OUTPUT_DIR")
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    cases = []

    # 1. Dense. A qwen2-shaped graph is a first-class success: `status: "ok"` with
    #    `moe.present: false` and every locality aggregate `null`.
    for n_layer, n_tokens in ((1, 1), (2, 5), (28, 5), (1, 64), (28, 64)):
        positive(cases, root, "dense-L%d-T%d" % (n_layer, n_tokens),
                 [dense_graph(n_layer, n_tokens)])

    # A graph with no `-N` suffixed node at all: `graph.n_layer` is `null`, not a sentinel.
    positive(cases, root, "dense-zero-layer", [dense_graph(0, 3)])

    # 2. MoE with generator-known ids. This is the corpus that closes every MOE-PREREQ cell
    #    synthetically, and the one a real MoE transcript would replace.
    for n_expert, used in ((4, 1), (8, 2), (32, 4), (128, 8), (8, 8), (1024, 64)):
        positive(cases, root, "moe-E%d-U%d" % (n_expert, used),
                 [moe_graph(4, 5, Router(11, n_expert, used), 0)])

    # A token index at the very top of the packed key's token field. The last token of layer N and
    # the first token of layer N+1 are one apart *as packed integers*, so an adjacency test that
    # compares packed keys alone manufactures a pair across the layer boundary. Every aggregate
    # below comes from the generator's own oracle, so the phantom pair is caught as a value.
    # Section 6, item 20: build 10566 reduces the graph to the output tokens *before* the last
    # layer's feed-forward, so that layer's `ffn_moe_topk` is one token wide, its retained token
    # index is not printed anywhere, and it therefore yields no selection at all.
    positive(cases, root, "moe-token-reduced-tail",
             [moe_graph(3, 5, Router(17, 64, 8), 0, reduced_tail=1)])
    positive(cases, root, "moe-token-reduced-pair",
             [moe_graph(2, 6, Router(19, 16, 4), 0, reduced_tail=2)])
    positive(cases, root, "moe-saturated-token",
             [moe_graph(2, MAX_TOKENS_PER_GRAPH, Router(13, 8, 2), 0)])

    # `n_expert` sources: probs wins, then logits, then absent.
    positive(cases, root, "n-expert-probs",
             [moe_graph(2, 5, Router(3, 16, 4), 0)])
    positive(cases, root, "n-expert-logits",
             [moe_graph(2, 5, Router(3, 16, 4), 0, probs=False)])
    positive(cases, root, "n-expert-absent",
             [moe_graph(2, 5, Router(3, 16, 4), 0, probs=False, logits=False)])

    # 3. Truncated axes. Every combination of full and three-plus-three printing on axes 0 and 1.
    for n_tokens in (6, 7, 8, 64, 1024):
        for used in (4, 6, 7, 8):
            positive(cases, root, "trunc-T%d-U%d" % (n_tokens, used),
                     [moe_graph(2, n_tokens, Router(5, 64, used), 0)])

    # R2c full router axes. The independent oracle consumes each Block's fixture-owned print mode,
    # so these rows prove direct 0..N-1 indices, false truncation fields, and the larger locality
    # denominator without sharing implementation with the Align parser.
    positive(cases, root, "r2c-full-T8-U8",
             [moe_graph(3, 8, Router(37, 64, 8), 0, full_topk=True)])
    positive(cases, root, "r2c-full-multi-graph", [
        moe_graph(2, 8, Router(41, 64, 8), 0, full_topk=True),
        moe_graph(2, 1, Router(41, 64, 8), 1, full_topk=True),
        moe_graph(2, 1, Router(41, 64, 8), 2, full_topk=True),
    ])

    # The new alternative is exact, not a relaxed row counter: short/long full slot and token axes,
    # a marker outside ordinal three, and mixed compact/full top-k layers all fail closed.
    full_graph = [moe_graph(2, 8, Router(43, 64, 8), 0, full_topk=True)]
    full_text = render(full_graph)
    emit(cases, root, "r2c-full-slot-short",
         transform_first_topk_row(full_text, lambda body: ", ".join(body.split(", ")[:-1])),
         expect="error", code="R2_ROW_COUNT")
    emit(cases, root, "r2c-full-slot-long",
         transform_first_topk_row(full_text, lambda body: body + ", " + body.split(", ")[0]),
         expect="error", code="R2_ROW_COUNT")
    emit(cases, root, "r2c-full-slot-marker-misplaced",
         transform_first_topk_row(full_text, lambda body: A0_MARK + ", " + body),
         expect="error", code="R2_ROW_COUNT")
    emit(cases, root, "r2c-full-token-short", change_first_topk_token_row(full_text, False),
         expect="error", code="R2_ROW_COUNT")
    emit(cases, root, "r2c-full-token-long", change_first_topk_token_row(full_text, True),
         expect="error", code="R2_ROW_COUNT")
    mixed_graph = moe_graph(2, 8, Router(47, 64, 8), 0, full_topk=True)
    topk_seen = 0
    for block in mixed_graph:
        if family_of(block.name)[0] == "ffn_moe_topk":
            topk_seen += 1
            if topk_seen == 2:
                block.full_axes = frozenset()
    emit(cases, root, "r2c-mixed-print-form", render([mixed_graph]),
         expect="error", code="R2_ROW_COUNT")
    mixed_axis2_graph = moe_graph(2, 5, Router(53, 64, 8), 0, full_topk=True)
    topk_seen = 0
    for block in mixed_axis2_graph:
        if family_of(block.name)[0] == "ffn_moe_topk":
            block.ne[2] = 8
            topk_seen += 1
            if topk_seen == 2:
                # Slots and tokens stay full in both blocks. Only axis 2 changes from eight slices
                # to the compact first/last three, so this case cannot be caught by their owners.
                block.full_axes = frozenset((0, 1))
    emit(cases, root, "r2c-mixed-axis2-print-form", render([mixed_axis2_graph]),
         expect="error", code="R2_ROUTER_WEIGHT_MISMATCH", detail="ffn_moe_weights-0")
    non_router_full = [[Block(
        "embd", "f32", "GET_ROWS", ("token_embd.weight", [8, 64, 1, 1]), None,
        [8, 1, 1, 1], full_axes=(0,))]]
    emit(cases, root, "r2c-non-router-full-axis", render(non_router_full),
         expect="error", code="R2_ROW_COUNT")

    # R8 schema 2 pairs one exact four-decimal selected weight with every top-k identity. The
    # producer refuses values, missing/duplicate blocks, shape drift, and a full/compact mismatch.
    weight_graph = moe_graph(2, 8, Router(59, 64, 8), 0, full_topk=True)
    weight_text = render([weight_graph])
    emit(cases, root, "router-weight-value",
         transform_first_weight_row(weight_text, lambda body: body.replace("0.", "1.", 1)),
         expect="error", code="R2_ROUTER_WEIGHT_VALUE", detail="ffn_moe_weights-0")
    emit(cases, root, "router-weight-negative",
         transform_first_weight_row(weight_text, lambda body: body.replace("0.", "-0.", 1)),
         expect="error", code="R2_ROUTER_WEIGHT_VALUE", detail="ffn_moe_weights-0")
    emit(cases, root, "router-weight-leading-zero",
         transform_first_weight_row(weight_text, lambda body: body.replace("0.", "00.", 1)),
         expect="error", code="R2_ROUTER_WEIGHT_VALUE", detail="ffn_moe_weights-0")
    emit(cases, root, "router-weight-five-fraction-digits",
         transform_first_weight_row(weight_text, lambda body: body.replace(".", ".0", 1)),
         expect="error", code="R2_ROUTER_WEIGHT_VALUE", detail="ffn_moe_weights-0")
    missing_weight = [block for block in weight_graph if block.name != "ffn_moe_weights-0"]
    emit(cases, root, "router-weight-missing", render([missing_weight]),
         expect="error", code="R2_ROUTER_WEIGHT_MISMATCH", detail="ffn_moe_topk-0")
    duplicate_weight = list(weight_graph)
    weight_index = next(index for index, block in enumerate(duplicate_weight)
                        if block.name == "ffn_moe_weights-0")
    duplicate_weight.insert(weight_index + 1, duplicate_weight[weight_index])
    emit(cases, root, "router-weight-duplicate", render([duplicate_weight]),
         expect="error", code="R2_ROUTER_WEIGHT_MISMATCH", detail="ffn_moe_weights-0")
    wrong_shape = moe_graph(1, 8, Router(61, 64, 8), 0, full_topk=True)
    next(block for block in wrong_shape if block.name == "ffn_moe_weights-0").ne[0] = 2
    emit(cases, root, "router-weight-shape", render([wrong_shape]),
         expect="error", code="R2_ROUTER_WEIGHT_MISMATCH", detail="ffn_moe_weights-0")
    mixed_weight_form = moe_graph(1, 8, Router(67, 64, 8), 0, full_topk=True)
    next(block for block in mixed_weight_form if block.name == "ffn_moe_weights-0").full_axes = \
        frozenset()
    emit(cases, root, "router-weight-print-form", render([mixed_weight_form]),
         expect="error", code="R2_ROUTER_WEIGHT_MISMATCH", detail="ffn_moe_weights-0")

    # Axis 2 and axis 3 exercised by a three- and four-axis tensor.
    axis_blocks = [
        Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [64, 152064, 1, 1]),
              ("inp_tokens", [5, 1, 1, 1]), [64, 5, 1, 1]),
        Block("Qcur-0 (view) (permuted)", "f32", "PERMUTE", ("Qcur-0 (view)", [8, 28, 5, 1]),
              None, [8, 5, 28, 1]),
        Block("cache_v_l0 (view)", "f16", "VIEW", ("cache_v_l0", [512, 119040, 1, 1]), None,
              [8, 4, 256, 1]),
        Block("node_946", "f32", "GET_ROWS", ("l_out-0", [64, 5, 1, 1]),
              ("inp_out_ids", [1, 1, 1, 1]), [64, 1, 1, 1]),
        Block("axis3-0", "f32", "ADD", ("MTL0#embd#0", [4, 3, 2, 3]), None, [4, 3, 2, 3]),
    ]
    positive(cases, root, "axis-shapes", [axis_blocks])

    # Multi-graph: a repeated node name opens the next graph, and the three-valued phase rule
    # separates a genuine decode step from a one-token prompt's prefill.
    router = Router(29, 32, 4)
    positive(cases, root, "multi-graph", [
        moe_graph(3, 5, router, 0),
        moe_graph(3, 1, router, 1),
        moe_graph(3, 1, router, 2),
    ])
    positive(cases, root, "phase-ambiguous", [moe_graph(2, 1, Router(31, 8, 2), 0)])

    # Every expert id 0..255 rendered through `%12.4f` and round-tripped.
    sweep = [Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [64, 152064, 1, 1]),
                   ("inp_tokens", [6, 1, 1, 1]), [64, 6, 1, 1])]
    for layer in range(8):
        sweep.append(Block("ffn_moe_probs-%d" % layer, "f32", "SOFT_MAX",
                           ("ffn_moe_logits-%d" % layer, [256, 6, 1, 1]), None, [256, 6, 1, 1]))
        sweep.append(Block("ffn_moe_topk-%d" % layer, "i32", "TOP_K",
                           ("ffn_moe_probs-%d" % layer, [256, 6, 1, 1]), None, [6, 6, 1, 1],
                           (lambda i0, i1, i2, i3, layer=layer: float((layer * 36 + i1 * 6 + i0) % 256))))
        sweep.append(Block("ffn_moe_weights-%d" % layer, "f32", "GET_ROWS",
                           ("ffn_moe_probs-%d (reshaped)" % layer, [1, 256, 6, 1]),
                           ("ffn_moe_topk-%d" % layer, [6, 6, 1, 1]), [1, 6, 6, 1],
                           (lambda i0, i1, i2, i3: (1000 + i1 * 100 + i2) / 10000.0)))
    positive(cases, root, "expert-id-format", [sweep])

    # A transcript with no callback line at all: every loop join terminates on a zero count.
    empty_graph_text = "".join("ggml_backend_sched: node %d\n" % index for index in range(24))
    emit(cases, root, "zero-graph", empty_graph_text, expect="ok",
         asserts={"graph_count": 0, "callback_line_count": 0, "skipped_line_count": 24,
                  "n_layer": None, "moe_present": False, "selection_count": 0})

    # A `2>&1` capture: interleaved logger lines are ignorable and counted, never an error. The
    # logger writes between callback records, which is the asymmetry section 2.6 records — the same
    # line inside a value block is `R2_VALUE_GRAMMAR`.
    dense = [dense_graph(2, 5)]
    positive(cases, root, "dense-interleave-base", dense)
    logged = ["version: 0.2.0 (build 10566, commit bb4caa754)"]
    for blocks in dense:
        for index, block in enumerate(blocks):
            logged.append("0.02.233.039 I system_info: n_threads = 4")
            logged.extend(block.lines())
            logged.append("")
    emit(cases, root, "interleaved-stderr", "\n".join(logged) + "\n", expect="ok",
         asserts={"same_document_as": "dense-interleave-base", "build": 10566})

    # A transcript need not end in a newline, and CRLF is not silently stripped.
    positive(cases, root, "no-trailing-newline", [dense_graph(1, 3)], trailing_newline=False)
    emit(cases, root, "crlf-transcript", render([dense_graph(1, 3)]).replace("\n", "\r\n"),
         expect="error", code="R2_HEADER_GRAMMAR")
    positive(cases, root, "blank-lines", [dense_graph(1, 3)], separator="")

    # 6. Window boundary. The same logical transcript, prefixed with exactly enough ignorable bytes
    #    that a chosen line starts `k` bytes before offset WINDOW_BYTES and therefore runs off the
    #    end of the first window. A whole-file parser passes these trivially; a streaming one can
    #    fail them silently, which is why section 2.4's choice owns this family.
    boundary_graph = [dense_graph(28, 64)]
    boundary_text = render(boundary_graph)
    positive(cases, root, "window-unpadded", boundary_graph)

    def pad_bytes(count):
        if count <= 0:
            return ""
        out = []
        while count > 64:
            out.append("#" * 63 + "\n")
            count -= 64
        if count == 1:
            out.append("\n")
        else:
            out.append("#" * (count - 1) + "\n")
        return "".join(out)

    def line_offsets(text):
        offset = 0
        for line in text.split("\n"):
            yield offset, line
            offset += len(line.encode()) + 1

    def classify(line):
        if line.startswith("common_debug_cb_eval:"):
            return "header"
        if line.startswith("    sum = "):
            return "sum"
        if line.startswith(ROW_OPEN) and line.endswith(ROW_CLOSE):
            return "row"
        if line in (A1_TRUNC, A2_TRUNC):
            return "marker"
        return "other"

    targets = {}
    for offset, line in line_offsets(boundary_text):
        kind = classify(line)
        if kind != "other" and kind not in targets and offset > 2048:
            targets[kind] = offset
    for kind, offsets in (("header", (1, 2, 40, 200)), ("row", (40,)), ("sum", (40,)),
                          ("marker", (40,))):
        if kind not in targets:
            raise SystemExit("eval_callback_fixture: no %s line to straddle the window" % kind)
        for k in offsets:
            required = WINDOW_BYTES - k - targets[kind]
            text = pad_bytes(required) + boundary_text
            if len(text.encode()) <= WINDOW_BYTES:
                raise SystemExit("eval_callback_fixture: the boundary fixture fits one window")
            emit(cases, root, "window-%s-%d" % (kind, k), text, expect="ok",
                 asserts={"same_document_as": "window-unpadded", "straddles_window": True})

    # 5. Huge line, first and after five hundred blocks.
    long_line = "z" * 200000
    emit(cases, root, "huge-line-first", long_line + "\n" + render([dense_graph(1, 3)]),
         expect="error", code="R2_LINE_TOO_LONG", detail="0",
         asserts={"callback_line_count": 0})
    prefix_blocks = [Block("node_%d" % index, "f32", "ADD", ("embd", [4, 1, 1, 1]), None,
                           [4, 1, 1, 1]) for index in range(500)]
    prefix_text = render([[Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [4, 8, 1, 1]),
                                 ("inp_tokens", [1, 1, 1, 1]), [4, 1, 1, 1])] + prefix_blocks])
    emit(cases, root, "huge-line-late", prefix_text + long_line + "\n",
         expect="error", code="R2_LINE_TOO_LONG", detail=str(len(prefix_text.encode())),
         asserts={"callback_line_count": 501})

    # 4. Malformed: one fixture per row of the section 2.6 table.
    base = render([dense_graph(1, 5)])
    header_line = [line for line in base.split("\n") if line.startswith("common_debug_cb_eval:")][0]

    emit(cases, root, "empty-transcript", "", expect="error", code="R2_TRANSCRIPT_EMPTY",
         detail="")
    # `grammar-drift`: five mutations of a real header line, each refused rather than half-read.
    drifts = [
        ("drift-narrow-name", mutate(base, "common_debug_cb_eval: " + " " * 20,
                                     "common_debug_cb_eval: ")),
        ("drift-missing-brace", mutate(base, "}) = {", ") = {")),
        ("drift-missing-paren", mutate(base, " = (f32)", " = f32)")),
        ("drift-narrow-op", mutate(base, "(f32)   RMS_NORM(", "(f32) RMS_NORM(")),
        ("drift-no-separator", mutate(base, "}, ", "},")),
    ]
    for name, text in drifts:
        emit(cases, root, name, text, expect="error", code="R2_HEADER_GRAMMAR")

    long_name = "n" * (MAX_NAME_BYTES + 1)
    emit(cases, root, "node-name-too-long",
         render([[Block(long_name, "f32", "ADD", ("embd", [4, 1, 1, 1]), None, [4, 1, 1, 1])]]),
         expect="error", code="R2_NODE_NAME_TOO_LONG")

    emit(cases, root, "dims-invalid", mutate(base, "= {3584, 5, 1, 1}", "= {3584, 5, 1}"),
         expect="error", code="R2_DIMS_INVALID", detail="embd")

    emit(cases, root, "value-drift-inside",
         mutate(base, "        ],\n    ]", "        ],\n        stray\n    ]"),
         expect="error", code="R2_VALUE_GRAMMAR")
    positive(cases, root, "value-drift-base", [dense_graph(1, 5)])
    emit(cases, root, "value-drift-outside", base.replace("\n\n", "\n        stray\n\n"),
         expect="ok", asserts={"same_document_as": "value-drift-base", "ignore_source": True})

    emit(cases, root, "sum-missing", base.replace("    sum = ", "    total = ", 1),
         expect="error", code="R2_VALUE_GRAMMAR")
    emit(cases, root, "sum-missing-eof",
         "\n".join(base.split("\n")[:-3]) + "\n", expect="error", code="R2_SUM_MISSING")

    emit(cases, root, "layer-index",
         render([[Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [4, 8, 1, 1]),
                        ("inp_tokens", [1, 1, 1, 1]), [4, 1, 1, 1]),
                  Block("ffn_out-%d" % MAX_LAYERS, "f32", "ADD", ("embd", [4, 1, 1, 1]), None,
                        [4, 1, 1, 1])]]),
         expect="error", code="R2_LAYER_INDEX", detail="ffn_out-%d" % MAX_LAYERS)

    rowcount_base = render([[Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [8, 8, 1, 1]),
                                   ("inp_tokens", [28, 1, 1, 1]), [8, 28, 1, 1])]])
    dropped = rowcount_base.split("\n")
    dropped = [line for index, line in enumerate(dropped) if index != 5]
    emit(cases, root, "rowcount-mismatch", "\n".join(dropped), expect="error",
         code="R2_ROW_COUNT", detail="embd")

    token_mismatch = render([moe_graph(1, 5, Router(2, 8, 2), 0)])
    token_mismatch = mutate(token_mismatch, "ffn_moe_topk-0 = (i32)      TOP_K(ffn_moe_probs-0{8, 5, 1, 1}, }) = {2, 5, 1, 1}",
                            "ffn_moe_topk-0 = (i32)      TOP_K(ffn_moe_probs-0{8, 5, 1, 1}, }) = {2, 6, 1, 1}")
    # The token-reduced exemption is the instrument's *tail* reduction and nothing else. A middle
    # layer whose token axis is short is not a reduction build 10566 can perform, and accepting it
    # would drop an interior layer's whole routing from every aggregate without a refusal. The
    # first suffixed node at a higher layer is what proves the reduced layer was not the last.
    emit(cases, root, "token-reduced-middle",
         render([moe_graph(3, 5, Router(23, 16, 4), 0, reduced_layer=1)]),
         expect="error", code="R2_TOKEN_COUNT", detail="ffn_norm-2")

    emit(cases, root, "token-count", token_mismatch, expect="error", code="R2_TOKEN_COUNT",
         detail="ffn_moe_topk-0")

    id_base = render([moe_graph(1, 5, Router(2, 8, 2), 0)])
    # The detail is the element text verbatim, padding included: it is what the transcript printed,
    # and trimming it would hide a width change that is itself evidence of grammar drift.
    for name, replacement, code in (
        ("expert-fraction", "     12.5000", "R2_EXPERT_ID_NOT_INTEGRAL"),
        ("expert-negative", "     -1.0000", "R2_EXPERT_ID_NOT_INTEGRAL"),
        ("expert-nan", "         nan", "R2_EXPERT_ID_NOT_INTEGRAL"),
        ("expert-inf", "         inf", "R2_EXPERT_ID_NOT_INTEGRAL"),
    ):
        detail = replacement
        rows = id_base.split("\n")
        for index, line in enumerate(rows):
            if line.startswith(ROW_OPEN) and "ffn_moe_topk-0" in rows[index - 4]:
                pass
        marker = rows.index([line for line in rows
                             if "ffn_moe_topk-0" in line and line.startswith("common")][0])
        for index in range(marker, len(rows)):
            if rows[index].startswith(ROW_OPEN):
                parts = rows[index][len(ROW_OPEN):-len(ROW_CLOSE)].split(", ")
                parts[0] = replacement
                rows[index] = ROW_OPEN + ", ".join(parts) + ROW_CLOSE
                break
        emit(cases, root, name, "\n".join(rows), expect="error", code=code, detail=detail)

    bounds = render([moe_graph(1, 5, Router(2, 8, 2), 0)])
    rows = bounds.split("\n")
    marker = rows.index([line for line in rows
                         if "ffn_moe_topk-0" in line and line.startswith("common")][0])
    for index in range(marker, len(rows)):
        if rows[index].startswith(ROW_OPEN):
            parts = rows[index][len(ROW_OPEN):-len(ROW_CLOSE)].split(", ")
            parts[0] = "%12.4f" % 9.0
            rows[index] = ROW_OPEN + ", ".join(parts) + ROW_CLOSE
            break
    emit(cases, root, "expert-out-of-range", "\n".join(rows), expect="error",
         code="R2_EXPERT_BOUNDS", detail="ffn_moe_topk-0")

    over_used = render([[Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [8, 8, 1, 1]),
                               ("inp_tokens", [2, 1, 1, 1]), [8, 2, 1, 1]),
                         Block("ffn_moe_topk-0", "i32", "TOP_K", ("ffn_moe_probs-0", [8, 2, 1, 1]),
                               None, [MAX_EXPERTS_USED + 1, 2, 1, 1])]])
    emit(cases, root, "expert-used-bounds", over_used, expect="error", code="R2_EXPERT_BOUNDS",
         detail="ffn_moe_topk-0")

    inconsistent = [
        Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [8, 8, 1, 1]),
              ("inp_tokens", [2, 1, 1, 1]), [8, 2, 1, 1]),
        Block("ffn_moe_topk-0", "i32", "TOP_K", ("ffn_moe_probs-0", [8, 2, 1, 1]), None,
              [2, 2, 1, 1]),
        Block("ffn_moe_weights-0", "f32", "GET_ROWS",
              ("ffn_moe_probs-0 (reshaped)", [1, 8, 2, 1]),
              ("ffn_moe_topk-0", [2, 2, 1, 1]), [1, 2, 2, 1]),
        Block("ffn_moe_topk-1", "i32", "TOP_K", ("ffn_moe_probs-1", [8, 2, 1, 1]), None,
              [3, 2, 1, 1]),
        Block("ffn_moe_weights-1", "f32", "GET_ROWS",
              ("ffn_moe_probs-1 (reshaped)", [1, 8, 2, 1]),
              ("ffn_moe_topk-1", [3, 2, 1, 1]), [1, 3, 2, 1]),
    ]
    emit(cases, root, "moe-inconsistent-layers", render([inconsistent]), expect="error",
         code="R2_MOE_INCONSISTENT", detail="ffn_moe_topk-1")
    graph_a = [
        Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [8, 8, 1, 1]),
              ("inp_tokens", [2, 1, 1, 1]), [8, 2, 1, 1]),
        Block("ffn_moe_topk-0", "i32", "TOP_K", ("ffn_moe_probs-0", [8, 2, 1, 1]), None,
              [2, 2, 1, 1]),
        Block("ffn_moe_weights-0", "f32", "GET_ROWS",
              ("ffn_moe_probs-0 (reshaped)", [1, 8, 2, 1]),
              ("ffn_moe_topk-0", [2, 2, 1, 1]), [1, 2, 2, 1]),
    ]
    graph_b = [
        Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [8, 8, 1, 1]),
              ("inp_tokens", [2, 1, 1, 1]), [8, 2, 1, 1]),
        Block("ffn_moe_topk-0", "i32", "TOP_K", ("ffn_moe_probs-0", [8, 2, 1, 1]), None,
              [4, 2, 1, 1]),
        Block("ffn_moe_weights-0", "f32", "GET_ROWS",
              ("ffn_moe_probs-0 (reshaped)", [1, 8, 2, 1]),
              ("ffn_moe_topk-0", [4, 2, 1, 1]), [1, 4, 2, 1]),
    ]
    emit(cases, root, "moe-inconsistent-graphs", render([graph_a, graph_b]), expect="error",
         code="R2_MOE_INCONSISTENT", detail="ffn_moe_topk-0")

    # Malformed bytes: a NUL and an invalid UTF-8 byte in a header line are each refused, and the
    # document that reports them is still valid JSON.
    nul_text = base.replace("embd", "em\0d", 1).encode("utf-8")
    emit(cases, root, "nul-in-header", None, expect="error", code="R2_HEADER_GRAMMAR",
         binary=nul_text)
    invalid_utf8 = base.replace("embd", "emXd", 1).encode("utf-8").replace(b"emXd", b"em\xffd", 1)
    emit(cases, root, "invalid-utf8-name", None, expect="error", code="R2_HEADER_GRAMMAR",
         binary=invalid_utf8)

    # Multi-byte UTF-8 at every offset the grammar computes rather than matches. A `str` range slice
    # aborts the process when either offset falls inside a scalar, so each of these lines must be
    # refused as data — a recorded code and a truthful partial document — and never abort. `é` is
    # two bytes and `あ` is three, chosen so the byte that a fixed-width slice would land on is a
    # continuation byte in each case.
    multibyte = [
        # The byte after the `(type)` close paren, which the grammar tests for a single space.
        ("multibyte-type-close", "R2_HEADER_GRAMMAR",
         mutate(base, " = (f32)   RMS_NORM(", " = (f32)é  RMS_NORM(")),
        # The final byte of a header line, which the grammar tests for `}`.
        ("multibyte-header-tail", "R2_HEADER_GRAMMAR",
         mutate(base, "GET_ROWS(token_embd.weight{3584, 152064, 1, 1}, inp_tokens{5, 1, 1, 1}}) = "
                      "{3584, 5, 1, 1}",
                "GET_ROWS(token_embd.weight{3584, 152064, 1, 1}, inp_tokens{5, 1, 1, 1}}) = "
                "{3584, 5, 1, 1}é")),
        # The two bytes after src0's closing `}`, which the grammar tests for `, `.
        ("multibyte-src0-separator", "R2_HEADER_GRAMMAR",
         mutate(base, "{3584, 152064, 1, 1}, ", "{3584, 152064, 1, 1}あ, ")),
        # The final byte of the src1 operand, which the grammar tests for `}`.
        ("multibyte-src1-tail", "R2_HEADER_GRAMMAR",
         mutate(base, "inp_tokens{5, 1, 1, 1}}) = {", "inp_tokens{5, 1, 1, 1}é}) = {")),
    ]
    for name, code, text in multibyte:
        emit(cases, root, name, text, expect="error", code=code)
    # The last four bytes of a value row, which the grammar tests for `  ],`.
    row_rows = base.split("\n")
    for index, line in enumerate(row_rows):
        if line.startswith(ROW_OPEN) and line.endswith(ROW_CLOSE):
            row_rows[index] = ROW_OPEN + "Xéあ"
            break
    else:
        raise SystemExit("eval_callback_fixture: no value row to truncate")
    emit(cases, root, "multibyte-value-row", "\n".join(row_rows), expect="error",
         code="R2_VALUE_GRAMMAR")

    # And the positive half: a transcript whose names, types, operations, and operands all carry
    # multi-byte scalars parses, interns, sorts, and renders normally.
    multibyte_graph = [
        Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [8, 8, 1, 1]),
              ("inp_tokens", [5, 1, 1, 1]), [8, 5, 1, 1]),
        Block("ünïcode_nöde-0", "f³2", "RMS_NÖRM", ("MTL0#embd#0", [8, 5, 1, 1]), None,
              [8, 5, 1, 1]),
        Block("naïve (view) (permüted)", "f16", "PERMÜTE", ("naïve (view)", [8, 5, 1, 1]), None,
              [4, 5, 1, 1]),
        Block("日本語ノード", "f32", "ADD", ("ünïcode_nöde-0", [8, 5, 1, 1]),
              ("embd", [8, 5, 1, 1]), [8, 5, 1, 1]),
    ]
    positive(cases, root, "multibyte-everywhere", [multibyte_graph])

    # Precedence: a transcript defective in two ordered ways reports the earlier row.
    emit(cases, root, "precedence-line-then-header",
         long_line + "\n" + drifts[1][1], expect="error", code="R2_LINE_TOO_LONG", detail="0")
    header_then_rowcount = "\n".join(dropped).replace(
        "common_debug_cb_eval: ", "common_debug_cb_eval:", 1)
    emit(cases, root, "precedence-header-then-rowcount", header_then_rowcount, expect="error",
         code="R2_HEADER_GRAMMAR")

    # `partial-scan`: a defect at block 500 of 1,000 reports the exact callback line count.
    many = [Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [4, 8, 1, 1]),
                  ("inp_tokens", [1, 1, 1, 1]), [4, 1, 1, 1])]
    many += [Block("node_%d" % index, "f32", "ADD", ("embd", [4, 1, 1, 1]), None, [4, 1, 1, 1])
             for index in range(999)]
    partial = render([many]).split("\n")
    target = [index for index, line in enumerate(partial)
              if line.startswith("common_debug_cb_eval:")][500]
    partial[target] = partial[target].replace("}) = {", ") = {")
    emit(cases, root, "partial-scan", "\n".join(partial), expect="error",
         code="R2_HEADER_GRAMMAR", asserts={"callback_line_count": 501})

    # Limits whose real constants a fixture can reach.
    node_limit = [Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [4, 8, 1, 1]),
                        ("inp_tokens", [1, 1, 1, 1]), [4, 1, 1, 1])]
    node_limit += [Block("node_%d" % index, "f32", "ADD", ("embd", [4, 1, 1, 1]), None,
                         [4, 1, 1, 1]) for index in range(MAX_NODES_PER_GRAPH)]
    emit(cases, root, "node-limit", render([node_limit]), expect="error", code="R2_NODE_LIMIT",
         detail="0")

    graph_limit_block = Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [4, 8, 1, 1]),
                              ("inp_tokens", [1, 1, 1, 1]), [4, 1, 1, 1])
    emit(cases, root, "graph-limit",
         render([[graph_limit_block] for _ in range(MAX_GRAPHS + 1)]),
         expect="error", code="R2_GRAPH_LIMIT", detail=str(MAX_GRAPHS))

    # `MAX_SELECTIONS`: 36 printed elements per `ffn_moe_topk` block is the ceiling the truncation
    # rule imposes, so the fixture is the smallest graph count that crosses the bound.
    per_block = TRUNCATION_PRINTED * TRUNCATION_PRINTED
    blocks_needed = MAX_SELECTIONS // per_block + 2
    layers = MAX_LAYERS
    graph_count = (blocks_needed + layers - 1) // layers
    selection_router = Router(7, 64, 6)
    selection_graphs = []
    for ordinal in range(graph_count):
        blocks = [Block("embd", "f32", "GET_ROWS", ("token_embd.weight", [8, 8, 1, 1]),
                        ("inp_tokens", [6, 1, 1, 1]), [8, 6, 1, 1])]
        for layer in range(layers):
            blocks.append(Block("ffn_moe_topk-%d" % layer, "i32", "TOP_K",
                                ("ffn_moe_probs-%d" % layer, [64, 6, 1, 1]), None, [6, 6, 1, 1],
                                (lambda i0, i1, i2, i3, layer=layer, ordinal=ordinal:
                                 float(selection_router.experts(ordinal, layer, i1)[i0]))))
            blocks.append(Block("ffn_moe_weights-%d" % layer, "f32", "GET_ROWS",
                                ("ffn_moe_probs-%d (reshaped)" % layer, [1, 64, 6, 1]),
                                ("ffn_moe_topk-%d" % layer, [6, 6, 1, 1]), [1, 6, 6, 1]))
        selection_graphs.append(blocks)
    emit(cases, root, "selection-limit", render(selection_graphs), expect="error",
         code="R2_SELECTION_LIMIT", detail=str(MAX_SELECTIONS))

    # `MAX_TRANSCRIPT_BYTES` is reached with a sparse file: the guard fires on `f.len()` alone, so
    # not one of its bytes is ever read.
    oversize = root / "oversize-transcript.txt"
    sparse = False
    try:
        with open(oversize, "wb") as handle:
            handle.truncate(MAX_TRANSCRIPT_BYTES + 1)
        sparse = oversize.stat().st_size == MAX_TRANSCRIPT_BYTES + 1
    except OSError:
        sparse = False
    if sparse:
        cases.append({"name": "oversize-transcript", "file": oversize.name, "expect": "error",
                      "error_code": "R2_TRANSCRIPT_TOO_LARGE",
                      "error_detail": str(MAX_TRANSCRIPT_BYTES + 1)})
    else:
        if oversize.exists():
            oversize.unlink()

    manifest = {
        "window_bytes": WINDOW_BYTES,
        "max_line_bytes": MAX_LINE_BYTES,
        "max_selections": MAX_SELECTIONS,
        "max_graphs": MAX_GRAPHS,
        "max_nodes_per_graph": MAX_NODES_PER_GRAPH,
        "contract_build": CONTRACT_BUILD,
        "windows": list(WINDOWS),
        "sparse_oversize": sparse,
        "cases": cases,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=False),
                                        encoding="utf-8")
    print("eval callback fixture: %d cases" % len(cases))


if __name__ == "__main__":
    main()
