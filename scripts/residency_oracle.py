#!/usr/bin/env python3
"""Independent oracle for `R3_RESIDENCY_SIM` (`docs/specs/r3-residency-sim.md`).

Written from the plan's sections 2.2 through 2.8, never from `src/residency_sim.align`, in the
tradition of `scripts/expert_locality_gate.py`. It renders the whole document so the owner smoke can
compare every integer of the Align result against a second implementation rather than against a
checked-in constant.

Usage: residency_oracle.py [--reset] TRACE_LIST MODEL_IR.json BUDGET_BYTES
"""

import json
import os
import sys
from pathlib import Path

CONTINUING_SCHEMA_VERSION = 2
RESET_SCHEMA_VERSION = 3
KIND = "R3_RESIDENCY_SIM"
MARGIN = 50
MAX_RESIDENCY_KEYS = 16384
MAX_DEMANDS = 262144
MAX_TRACE_PATHS = 4096
MAX_DOCUMENT_BYTES = 33554432
MAX_PATH_BYTES = 4096
MAX_LAYERS = 256
MAX_GRAPHS = 4096
MAX_TOKENS = 262144
MAX_SLOTS = 128
MAX_SIMULATION_STEPS = 1 << 32
I64_MAX = (1 << 63) - 1
# The largest prefetch degree section 2.4 ships, used by the byte-total overflow bound.
MAX_PREFETCH_DEGREE = 8
# The ceiling on every byte quantity and on the BUDGET_BYTES operand: `I64_MAX // 1000`, because
# every ratio is an integer per mille and each total is multiplied by 1000 before it is divided.
MAX_BYTE_TOTAL = I64_MAX // 1000

POLICIES = (
    ("null", 0),
    ("compulsory", 0),
    ("belady", 0),
    ("lru", 0),
    ("lfu", 0),
    ("router_weight_lfu", 0),
    ("recent_reuse_w2", 2),
    ("recent_reuse_w8", 8),
    ("recent_reuse_w32", 32),
    ("topk_prefetch_k1", 1),
    ("topk_prefetch_k8", 8),
)
POLICY_NAMES = [name for name, _ in POLICIES]
CANDIDATES = [
    "lfu",
    "router_weight_lfu",
    "recent_reuse_w2",
    "recent_reuse_w8",
    "recent_reuse_w32",
    "topk_prefetch_k1",
    "topk_prefetch_k8",
]
ORDERS = ("token_major", "layer_major")


class Fault(Exception):
    def __init__(self, code, detail=""):
        super().__init__(code)
        self.code = code
        self.detail = detail


def valid_path(text):
    return 0 < len(text.encode()) <= MAX_PATH_BYTES and "\0" not in text


def parse_budget(text):
    if not text or any(c not in "0123456789" for c in text):
        raise Fault("R3_BUDGET_MALFORMED", "")
    value = int(text)
    if value > MAX_BYTE_TOTAL:
        raise Fault("R3_BUDGET_MALFORMED", "")
    return value


def read_document(path, unreadable, too_large, detail, state):
    """Reads whole, then enforces the cap: there is no `fs.size` at this pin, so the Align owner
    cannot check the size before the read either (section 6, correction 3)."""
    try:
        text = Path(path).read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        raise Fault(unreadable, detail)
    if len(text.encode("utf-8", "surrogateescape")) > MAX_DOCUMENT_BYTES:
        raise Fault(too_large, detail)
    size = len(text.encode("utf-8", "surrogateescape"))
    state["bytes_read"] += size
    return text, size


def read_trace_list(path, state):
    if not valid_path(path):
        raise Fault("R3_PATH", "")
    try:
        text = Path(path).read_text()
    except OSError:
        raise Fault("R3_TRACE_LIST_UNREADABLE", "")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    state["listed"] = len(lines)
    if not lines:
        raise Fault("R3_TRACE_LIST_EMPTY", "")
    if len(lines) > MAX_TRACE_PATHS:
        raise Fault("R3_TRACE_LIST_TOO_MANY", "")
    seen = {}
    for ordinal, line in enumerate(lines, 1):
        if not valid_path(line):
            raise Fault("R3_PATH", str(ordinal))
        if line in seen:
            raise Fault("R3_TRACE_LIST_DUPLICATE", str(ordinal))
        seen[line] = ordinal
    return lines


def phase_of(n_tokens, ordinal):
    # `docs/specs/r2a-expert-trace.md` section 2.5.6's total function of two fields R3 already reads.
    if n_tokens is None:
        return None
    if n_tokens > 1:
        return "prefill"
    if ordinal > 0:
        return "decode"
    return "single_token_first_graph"


def decode_model_ir(path, state):
    if not valid_path(path):
        raise Fault("R3_PATH", "")
    text, size = read_document(path, "R3_IR_UNREADABLE", "R3_IR_TOO_LARGE", "", state)
    try:
        doc = json.loads(text)
    except ValueError:
        raise Fault("R3_IR_DECODE", "")
    if not isinstance(doc, dict):
        raise Fault("R3_IR_DECODE", "")
    if doc.get("kind") != "R1_MODEL_IR" or doc.get("schema_version") != 2:
        raise Fault("R3_IR_SCHEMA", "")
    if doc.get("status") != "ok":
        raise Fault("R3_IR_STATUS", "")
    model = doc.get("model") or {}
    n_layer = model.get("n_layer") or 0
    n_expert = model.get("n_expert") or 0
    n_expert_used = model.get("n_expert_used") or 0
    if n_layer <= 0 or n_expert <= 0:
        raise Fault("R3_IR_NOT_MOE", "")
    if n_layer > MAX_LAYERS or n_expert > MAX_RESIDENCY_KEYS \
            or n_layer > MAX_RESIDENCY_KEYS // n_expert:
        raise Fault("R3_KEY_SPACE_TOO_LARGE", "")
    sizes = {}
    total = 0
    for block in doc.get("blocks") or []:
        if block.get("kind") != "ExpertBlock":
            continue
        key = (block["layer"], block["expert"])
        if not (0 <= key[0] < n_layer) or not (0 <= key[1] < n_expert):
            raise Fault("R3_EXPERT_BLOCK_RANGE", "%d:%d" % key)
        if key in sizes:
            raise Fault("R3_EXPERT_BLOCK_DUPLICATE", "%d:%d" % key)
        size = block["byte_size"]
        # A block of no bytes is not a residency unit, and a negative one is not a size at all.
        # Both are refused here rather than misreported later as a missing block (section 6,
        # correction 16). Align's arithmetic wraps with no trap, so the running total is guarded
        # before every addition (correction 18); the oracle refuses at the same block.
        if size <= 0:
            raise Fault("R3_EXPERT_BLOCK_SIZE", "%d:%d" % key)
        if total > MAX_BYTE_TOTAL - size:
            raise Fault("R3_BYTE_TOTAL_OVERFLOW", "%d:%d" % key)
        total += size
        sizes[key] = size
    if not sizes:
        raise Fault("R3_IR_NOT_MOE", "")
    state["model_ir_schema_version"] = 2
    state["model"] = {
        "arch": model.get("arch") or "",
        "n_layer": n_layer,
        "n_expert": n_expert,
        "n_expert_used": n_expert_used,
        "expert_block_count": len(sizes),
        "total_expert_bytes": sum(sizes.values()),
        "smallest_expert_bytes": min(sizes.values()),
        "largest_expert_bytes": max(sizes.values()),
        "uniform_expert_bytes": min(sizes.values()) == max(sizes.values()),
    }
    return sizes


def build_stream(paths, sizes, state, reset_per_trace):
    model = state["model"]
    n_layer, n_expert = model["n_layer"], model["n_expert"]
    token_major, layer_major = [], []
    bounds_tm, bounds_lm = [], []
    tok_tm, tok_lm = [], []
    weight_tm, weight_lm = [], []
    next_tm, next_lm = 0, 0
    observed_slots = set()
    omitted_truncated = 0
    builds = set()
    build_sources = set()
    graph_phases = {"prefill": 0, "decode": 0, "single_token_first_graph": 0}
    for ordinal, path in enumerate(paths, 1):
        detail = str(ordinal)
        text, size = read_document(path, "R3_TRACE_UNREADABLE", "R3_TRACE_TOO_LARGE", detail,
                                   state)
        try:
            doc = json.loads(text)
        except ValueError:
            raise Fault("R3_TRACE_DECODE", detail)
        if not isinstance(doc, dict):
            raise Fault("R3_TRACE_DECODE", detail)
        if doc.get("kind") != "R2_ACTIVATION_TRACE" or doc.get("schema_version") != 2:
            raise Fault("R3_TRACE_SCHEMA", detail)
        if doc.get("status") != "ok":
            raise Fault("R3_TRACE_STATUS", detail)
        moe = doc.get("moe") or {}
        if not moe.get("present"):
            raise Fault("R3_TRACE_NOT_MOE", detail)
        pair = (moe.get("n_expert"), moe.get("n_expert_used"))
        if pair != (n_expert, model["n_expert_used"]):
            raise Fault("R3_SHAPE_MISMATCH", detail)
        # Three states, because "excluded by the documented truncation rule" and "named by a
        # selection but never declared" are different answers (section 6, correction 17).
        truncated = {}
        for graph in doc.get("graphs") or []:
            if not (0 <= graph["ordinal"] < MAX_GRAPHS):
                raise Fault("R3_SELECTION_UNPACKABLE", detail)
            truncated[graph["ordinal"]] = bool(graph["tokens_truncated"])
            if graph["tokens_truncated"]:
                omitted_truncated += 1
            else:
                phase = phase_of(graph.get("n_tokens"), graph["ordinal"])
                if phase is not None:
                    graph_phases[phase] += 1
        rows = []
        observation = []
        orders = set()
        for selection in doc.get("selections") or []:
            graph, layer, token = selection["graph"], selection["layer"], selection["token"]
            slot, expert = selection["slot"], selection["expert"]
            weight = selection.get("router_weight_ten_thousandths")
            if not isinstance(weight, int) or isinstance(weight, bool):
                raise Fault("R3_TRACE_DECODE", detail)
            # A graph ordinal that cannot ride the packed word, and a selection naming a graph the
            # document never declared, both fail closed rather than shrinking the stream silently.
            if not (0 <= graph < MAX_GRAPHS) or graph not in truncated:
                raise Fault("R3_SELECTION_UNPACKABLE", detail)
            if not 0 <= weight <= 10000:
                raise Fault("R3_ROUTER_WEIGHT_RANGE", detail)
            if truncated[graph]:
                continue
            if not (0 <= layer < n_layer) or not (0 <= expert < n_expert):
                raise Fault("R3_EXPERT_OUT_OF_RANGE", "%d:%d" % (layer, expert))
            if (layer, expert) not in sizes:
                raise Fault("R3_MISSING_EXPERT_BLOCK", "%d:%d" % (layer, expert))
            if not (0 <= token < MAX_TOKENS) or not (0 <= slot < MAX_SLOTS) \
                    or layer >= MAX_LAYERS:
                raise Fault("R3_SELECTION_UNPACKABLE", detail)
            observed_slots.add(slot)
            # `MAX_DEMANDS` bounds what is allocated, so it is tested before the element that would
            # exceed it is appended (section 6, correction 21).
            if len(token_major) + len(rows) >= MAX_DEMANDS:
                raise Fault("R3_SELECTION_TOO_MANY", detail)
            order = (graph, token, layer, slot)
            if order in orders:
                raise Fault("R3_SELECTION_UNPACKABLE", detail)
            orders.add(order)
            rows.append((order, (layer, expert), weight))
            observation.append(((graph, token), (layer, expert), weight))
        run = doc.get("run") or {}
        if run.get("build") is not None:
            builds.add(run["build"])
            state["instrument_builds"] = sorted(builds)
        source = run.get("build_source") or ""
        if not build_sources:
            build_sources.add(source)
            state["instrument_build_source"] = source
        elif source not in build_sources:
            build_sources.add(source)
            state["instrument_build_source"] = "mixed"
        state["admitted"] = ordinal
        state["trace_schema_version"] = 2
        rows.sort(key=lambda row: row[0])
        start = len(token_major)
        previous = None
        for (graph, token, _layer, _slot), key, weight in rows:
            if (graph, token) != previous:
                previous = (graph, token)
                next_tm += 1
            token_major.append(key)
            tok_tm.append(next_tm - 1)
            weight_tm.append(weight)
        bounds_tm.append((start, len(token_major)))
        start = len(layer_major)
        previous = None
        for identity, key, weight in observation:
            if identity != previous:
                previous = identity
                next_lm += 1
            layer_major.append(key)
            tok_lm.append(next_lm - 1)
            weight_lm.append(weight)
        bounds_lm.append((start, len(layer_major)))
    if not token_major:
        raise Fault("R3_EMPTY_STREAM", "")
    # Every byte total is an `i64` in the Align owner and its arithmetic wraps with no trap, so the
    # largest total any accumulation below could reach is bounded before the first byte is summed
    # (section 6, correction 18). `demanded_byte_total` charges every demand at most
    # `largest_expert_bytes`; a `topk_prefetch` replay may in addition admit `n_layer * 8` blocks at
    # each of at most `demand_count` token boundaries. Deliberately loose: it refuses a run whose
    # totals *could* wrap rather than measuring which ones do, and it fires before the accounting so
    # the failed document reports an empty stream like every other failure.
    bound = len(token_major) + len(token_major) * n_layer * MAX_PREFETCH_DEGREE
    largest = model["largest_expert_bytes"]
    if largest > 0 and bound > MAX_BYTE_TOTAL // largest:
        raise Fault("R3_BYTE_TOTAL_OVERFLOW", "")
    distinct = set(token_major)
    positions = {(tok_tm[i], token_major[i][0]) for i in range(len(token_major))}
    first = [token_major[i] for i in range(len(token_major)) if tok_tm[i] == 0]
    token_positions = next_tm
    state["stream"] = {
        "pooling": "reset_per_trace" if reset_per_trace else "continuing",
        "demand_count": len(token_major),
        "token_position_count": token_positions,
        "distinct_key_count": len(distinct),
        "demanded_byte_total": sum(sizes[k] for k in token_major),
        "distinct_key_bytes": sum(sizes[k] for k in distinct),
        "layers_demanded": sorted({k[0] for k in distinct}),
        "n_expert_used": model["n_expert_used"],
        "observed_slots": sorted(observed_slots),
        "slot_coverage_per_mille": (
            1000 * len(observed_slots) // model["n_expert_used"] if model["n_expert_used"] else 0
        ),
        "one_token_working_set_keys": len(set(first)),
        "one_token_working_set_bytes": sum(sizes[k] for k in set(first)),
        "omitted_truncated_graphs": omitted_truncated,
        "omitted_layer_positions": token_positions * n_layer - len(positions),
        "graph_phases": graph_phases,
    }
    if reset_per_trace:
        # Schema 3 appends this field after `pooling`; rebuild the mapping to preserve the
        # normative wire order used by the Align renderer and whole-document oracle comparison.
        state["stream"] = {
            "pooling": state["stream"]["pooling"],
            "session_count": len(paths),
            **{key: value for key, value in state["stream"].items() if key != "pooling"},
        }
    return {
        "token_major": (token_major, tok_tm, weight_tm, bounds_tm),
        "layer_major": (layer_major, tok_lm, weight_lm, bounds_lm),
    }


def build_budgets(state, requested):
    model = state["model"]
    total, largest = model["total_expert_bytes"], model["largest_expert_bytes"]
    mean = total // model["expert_block_count"]
    entries = []
    for i in range(8):
        raw = total >> (7 - i)
        entries.append({"bytes": max(largest, raw), "clamped": raw < largest, "requested": False})
    for entry in entries:
        if entry["bytes"] == requested:
            entry["requested"] = True
            break
    else:
        entries.append({"bytes": requested, "clamped": False, "requested": True})
        entries.sort(key=lambda e: e["bytes"])
    for entry in entries:
        entry["per_mille_of_expert_bytes"] = 1000 * entry["bytes"] // total
        entry["expert_equivalents"] = entry["bytes"] // mean if mean else 0
    return [
        {
            "bytes": e["bytes"],
            "per_mille_of_expert_bytes": e["per_mille_of_expert_bytes"],
            "expert_equivalents": e["expert_equivalents"],
            "clamped": e["clamped"],
            "requested": e["requested"],
        }
        for e in entries
    ]


def replay_continuing(
        keys, toks, weights, sizes, budget, policy, window, topk, n_layer, n_expert, drop=None):
    """Section 2.4. `drop` is the half-open index range of the left-out document, or None."""
    lo, hi = drop if drop else (-1, -1)
    live = [i for i in range(len(keys)) if not (lo <= i < hi)]
    resident = {}
    used = 0
    hits = misses = fetched = prefetches = useful = high_water = 0
    last, freq, router_score, recent, next_use = {}, {}, {}, {}, {}
    prefetched = set()
    per_layer = {}
    nxt = {}
    # `belady` is miss-optimal, not byte-optimal: it evicts the resident key whose next use is
    # furthest away without consulting the size table, so on a model with unequal expert sizes its
    # `bytes_fetched` is an achievable byte total under a miss-optimal reference and not the
    # minimum achievable byte total. Section 2.8's `headroom_per_mille` inherits that: it can
    # understate the true byte headroom, so `NO_HEADROOM` is conservative in one direction only.
    if policy == "belady":
        seen = {}
        for position in reversed(range(len(live))):
            index = live[position]
            nxt[index] = seen.get(keys[index], len(live) + 1)
            seen[keys[index]] = position

    def victim():
        best = None
        best_rank = None
        for key in resident:
            if policy == "lfu":
                primary = freq.get(key, 0)
            elif policy == "router_weight_lfu":
                primary = router_score.get(key, 0)
            elif policy.startswith("recent_reuse"):
                primary = recent.get(key, 0)
            elif policy == "belady":
                primary = -next_use.get(key, len(live) + 1)
            else:
                primary = 0
            rank = (primary, last.get(key, -1), key)
            if best_rank is None or rank < best_rank:
                best, best_rank = key, rank
        return best

    def admit(key, size):
        nonlocal used, high_water
        while used + size > budget:
            loser = victim()
            used -= resident.pop(loser)
            prefetched.discard(loser)
        resident[key] = size
        used += size
        if len(resident) > high_water:
            high_water = len(resident)

    current = None
    ring_lo = 0
    for position, index in enumerate(live):
        key = keys[index]
        if toks[index] != current:
            current = toks[index]
            if policy.startswith("recent_reuse"):
                while ring_lo < position and toks[live[ring_lo]] < current - window:
                    expiring = keys[live[ring_lo]]
                    recent[expiring] -= 1
                    if recent[expiring] == 0:
                        del recent[expiring]
                    ring_lo += 1
            if policy.startswith("topk_prefetch"):
                for layer in range(n_layer):
                    ranked = sorted(
                        (k for k in freq if k[0] == layer),
                        key=lambda k: (-freq[k], k[1]),
                    )[:topk]
                    for candidate in ranked:
                        if candidate in resident or sizes[candidate] > budget:
                            continue
                        admit(candidate, sizes[candidate])
                        # A prefetched block enters as the most recently used, not as the next
                        # victim (section 2.4, section 6 correction 19). `position` is the index of
                        # the demand this token boundary precedes, so the admission is exactly as
                        # recent as an ordinary demand here and no more.
                        last[candidate] = position
                        fetched += sizes[candidate]
                        prefetches += 1
                        prefetched.add(candidate)
        layer = key[0]
        size = sizes[key]
        stat = per_layer.setdefault(layer, [0, 0])
        if policy == "null":
            misses += 1
            fetched += size
            stat[1] += 1
        elif key in resident:
            hits += 1
            stat[0] += 1
            if key in prefetched:
                useful += 1
                prefetched.discard(key)
        else:
            misses += 1
            stat[1] += 1
            fetched += size
            if policy == "compulsory":
                resident[key] = size
                if len(resident) > high_water:
                    high_water = len(resident)
            elif size <= budget:
                admit(key, size)
        freq[key] = freq.get(key, 0) + 1
        router_score[key] = router_score.get(key, 0) + weights[index]
        last[key] = position
        if policy.startswith("recent_reuse"):
            recent[key] = recent.get(key, 0) + 1
        if policy == "belady":
            next_use[key] = nxt[index]
    demands = hits + misses
    return {
        "hits": hits,
        "misses": misses,
        "demands": demands,
        "bytes_fetched": fetched,
        "prefetch_fetches": prefetches,
        "prefetch_useful": useful,
        "resident_key_high_water": high_water,
        "hit_per_mille": (1000 * hits // demands) if demands else 0,
        "per_layer": per_layer,
    }


def replay(
        keys, toks, weights, sizes, budget, policy, window, topk, n_layer, n_expert,
        drop=None, bounds=(), reset_per_trace=False):
    """Replay either one continuing stream or isolated trace sessions.

    Reset mode deliberately combines complete one-trace replays instead of sharing any policy
    state. A jackknife fold omits its complete session before aggregation.
    """
    if not reset_per_trace:
        return replay_continuing(
            keys, toks, weights, sizes, budget, policy, window, topk, n_layer, n_expert, drop,
        )
    total = {
        "hits": 0,
        "misses": 0,
        "demands": 0,
        "bytes_fetched": 0,
        "prefetch_fetches": 0,
        "prefetch_useful": 0,
        "resident_key_high_water": 0,
        "hit_per_mille": 0,
        "per_layer": {},
    }
    for lo, hi in bounds:
        if drop is not None and (lo, hi) == drop:
            continue
        result = replay_continuing(
            keys[lo:hi], toks[lo:hi], weights[lo:hi], sizes, budget, policy, window, topk,
            n_layer, n_expert,
        )
        for field in (
                "hits", "misses", "demands", "bytes_fetched", "prefetch_fetches",
                "prefetch_useful"):
            total[field] += result[field]
        total["resident_key_high_water"] = max(
            total["resident_key_high_water"], result["resident_key_high_water"]
        )
        for layer, stat in result["per_layer"].items():
            aggregate = total["per_layer"].setdefault(layer, [0, 0])
            aggregate[0] += stat[0]
            aggregate[1] += stat[1]
    if total["demands"]:
        total["hit_per_mille"] = 1000 * total["hits"] // total["demands"]
    return total


def window_of(policy):
    return {"recent_reuse_w2": 2, "recent_reuse_w8": 8, "recent_reuse_w32": 32}.get(policy, 0)


def topk_of(policy):
    return {"topk_prefetch_k1": 1, "topk_prefetch_k8": 8}.get(policy, 0)


def render(state, budgets, results, verdict):
    model = state["model"]
    orders = []
    for order in ORDERS:
        rows = []
        per_layer = []
        for budget in budgets:
            for policy in POLICY_NAMES:
                r = results[(order, budget["bytes"], policy)]
                rows.append(
                    {
                        "policy": policy,
                        "budget_bytes": budget["bytes"],
                        "hits": r["hits"],
                        "misses": r["misses"],
                        "demands": r["demands"],
                        "hit_per_mille": r["hit_per_mille"],
                        "bytes_fetched": r["bytes_fetched"],
                        "demanded_byte_total": state["stream"]["demanded_byte_total"],
                        "bytes_fetched_per_mille_of_null": (
                            1000
                            * r["bytes_fetched"]
                            // results[(order, budget["bytes"], "null")]["bytes_fetched"]
                            if results[(order, budget["bytes"], "null")]["bytes_fetched"]
                            else 0
                        ),
                        "prefetch_fetches": r["prefetch_fetches"],
                        "prefetch_useful": r["prefetch_useful"],
                        "resident_key_high_water": r["resident_key_high_water"],
                    }
                )
            for layer in state["stream"]["layers_demanded"]:
                entry = {"budget_bytes": budget["bytes"], "layer": layer, "policies": []}
                for policy in POLICY_NAMES:
                    stat = results[(order, budget["bytes"], policy)]["per_layer"].get(layer, [0, 0])
                    demands = stat[0] + stat[1]
                    entry["policies"].append(
                        {
                            "policy": policy,
                            "demands": demands,
                            "hits": stat[0],
                            "hit_per_mille": (1000 * stat[0] // demands) if demands else 0,
                        }
                    )
                per_layer.append(entry)
        orders.append(
            {
                "order": order,
                "verdict_bearing": order == "token_major",
                "policies": rows,
                "per_layer": per_layer,
            }
        )
    return {
        "schema_version": state["schema_version"],
        "kind": KIND,
        "trace_list_path": state["trace_list_path"],
        "model_ir_path": state["model_ir_path"],
        "status": "ok",
        "error_code": "",
        "error_detail": "",
        "inputs": {
            "listed_trace_count": state["listed"],
            "admitted_trace_count": state["admitted"],
            "trace_schema_version": state["trace_schema_version"],
            "model_ir_schema_version": state["model_ir_schema_version"],
            "bytes_read": state["bytes_read"],
            "instrument_builds": state["instrument_builds"],
            "instrument_build_source": state["instrument_build_source"],
        },
        "model": model,
        "stream": state["stream"],
        "budgets": budgets,
        "orders": orders,
        "verdict": verdict,
    }


def empty_document(state, code, detail):
    stream = state["stream"]
    if state["schema_version"] == RESET_SCHEMA_VERSION and "session_count" not in stream:
        stream = {
            "pooling": stream["pooling"],
            "session_count": state["admitted"],
            **{key: value for key, value in stream.items() if key != "pooling"},
        }
    return {
        "schema_version": state["schema_version"],
        "kind": KIND,
        "trace_list_path": state["trace_list_path"],
        "model_ir_path": state["model_ir_path"],
        "status": "error",
        "error_code": code,
        "error_detail": detail,
        "inputs": {
            "listed_trace_count": state["listed"],
            "admitted_trace_count": state["admitted"],
            "trace_schema_version": state["trace_schema_version"],
            "model_ir_schema_version": state["model_ir_schema_version"],
            "bytes_read": state["bytes_read"],
            "instrument_builds": state["instrument_builds"],
            "instrument_build_source": state["instrument_build_source"],
        },
        "model": state["model"],
        "stream": stream,
        "budgets": [],
        "orders": [],
        "verdict": blank_verdict(
            state["requested"], 3 if state["schema_version"] == RESET_SCHEMA_VERSION else 2
        ),
    }


def blank_verdict(requested, rule_version=2):
    return {
        "rule_version": rule_version,
        "order": "token_major",
        "budget_bytes": requested,
        "baseline_policy": "lru",
        "baseline_bytes_fetched": 0,
        "best_policy": "",
        "best_bytes_fetched": 0,
        "gain_per_mille": 0,
        "margin_per_mille": MARGIN,
        "headroom_per_mille": 0,
        "jackknife_folds": 0,
        "jackknife_min_gain_per_mille": 0,
        "jackknife_stable": False,
        "result": "",
        "sweep_best": [],
    }


def truncating(numerator, denominator):
    """Align's `/` truncates toward zero; Python's `//` floors. Only the jackknife gain of a fold
    where the candidate lost can be negative, and the two must agree there."""
    if denominator <= 0:
        return 0
    if numerator >= 0:
        return numerator * 1000 // denominator
    return -((-numerator * 1000) // denominator)


def sweep_entry(results, order, budget):
    lru = results[(order, budget, "lru")]["bytes_fetched"]
    optimal = results[(order, budget, "belady")]["bytes_fetched"]
    headroom = 1000 * (lru - optimal) // lru if lru else 0
    ranked = sorted(
        (results[(order, budget, p)]["bytes_fetched"], POLICY_NAMES.index(p), p)
        for p in CANDIDATES
    )
    best_bytes, _, best = ranked[0]
    if best_bytes >= lru:
        best, best_bytes, gain = "", lru, 0
    else:
        gain = 1000 * (lru - best_bytes) // lru
    if best and 1000 * best_bytes <= (1000 - MARGIN) * lru:
        result = "BEATS_BASELINE"
    elif headroom < MARGIN:
        result = "NO_HEADROOM"
    else:
        result = "NO_POLICY_BEATS_BASELINE"
    return {
        "budget_bytes": budget,
        "best_policy": best,
        "best_bytes_fetched": best_bytes,
        "gain_per_mille": gain,
        "headroom_per_mille": headroom,
        "result": result,
    }


def decide(state, streams, sizes, budgets, results, requested, reset_per_trace):
    model = state["model"]
    keys, toks, weights, bounds = streams["token_major"]
    lru = results[("token_major", requested, "lru")]["bytes_fetched"]
    optimal = results[("token_major", requested, "belady")]["bytes_fetched"]
    headroom = 1000 * (lru - optimal) // lru if lru else 0
    ranked = sorted(
        (results[("token_major", requested, p)]["bytes_fetched"], POLICY_NAMES.index(p), p)
        for p in CANDIDATES
    )
    folds = len(bounds)
    winner, winner_bytes, minimum, stable = "", lru, 0, False
    tested = False
    for best_bytes, _, policy in ranked:
        if best_bytes >= lru or 1000 * best_bytes > (1000 - MARGIN) * lru:
            continue
        gains = []
        for drop in bounds:
            fold_lru = replay(
                keys, toks, weights, sizes, requested, "lru", 0, 0,
                model["n_layer"], model["n_expert"], drop, bounds, reset_per_trace,
            )["bytes_fetched"]
            fold_best = replay(
                keys, toks, weights, sizes, requested, policy, window_of(policy), topk_of(policy),
                model["n_layer"], model["n_expert"], drop, bounds, reset_per_trace,
            )["bytes_fetched"]
            gains.append(truncating(fold_lru - fold_best, fold_lru))
        if not tested:
            tested = True
            minimum = min(gains)
        if all(gain >= MARGIN for gain in gains):
            winner, winner_bytes, minimum, stable = policy, best_bytes, min(gains), True
            break
    best_bytes, _, best = ranked[0]
    if best_bytes >= lru:
        best, best_bytes, gain = "", lru, 0
    else:
        gain = 1000 * (lru - best_bytes) // lru
    if stable:
        best, best_bytes = winner, winner_bytes
        gain = 1000 * (lru - winner_bytes) // lru
        result = "BEATS_BASELINE"
    elif headroom < MARGIN:
        result = "NO_HEADROOM"
    else:
        result = "NO_POLICY_BEATS_BASELINE"
    return {
        "rule_version": 3 if reset_per_trace else 2,
        "order": "token_major",
        "budget_bytes": requested,
        "baseline_policy": "lru",
        "baseline_bytes_fetched": lru,
        "best_policy": best,
        "best_bytes_fetched": best_bytes,
        "gain_per_mille": gain,
        "margin_per_mille": MARGIN,
        "headroom_per_mille": headroom,
        "jackknife_folds": folds,
        "jackknife_min_gain_per_mille": minimum,
        "jackknife_stable": stable,
        "result": result,
        "sweep_best": [
            sweep_entry(results, "token_major", entry["bytes"]) for entry in budgets
        ],
    }


def simulate(trace_list_path, model_ir_path, budget_text, reset_per_trace=False):
    state = {
        "schema_version": RESET_SCHEMA_VERSION if reset_per_trace else CONTINUING_SCHEMA_VERSION,
        "trace_list_path": trace_list_path,
        "model_ir_path": model_ir_path,
        "listed": 0,
        "admitted": 0,
        "trace_schema_version": 0,
        "model_ir_schema_version": 0,
        "bytes_read": 0,
        "instrument_builds": [],
        "instrument_build_source": "",
        "requested": 0,
        "model": {
            "arch": "",
            "n_layer": 0,
            "n_expert": 0,
            "n_expert_used": 0,
            "expert_block_count": 0,
            "total_expert_bytes": 0,
            "smallest_expert_bytes": 0,
            "largest_expert_bytes": 0,
            "uniform_expert_bytes": False,
        },
        "stream": {
            "pooling": "reset_per_trace" if reset_per_trace else "continuing",
            "demand_count": 0,
            "token_position_count": 0,
            "distinct_key_count": 0,
            "demanded_byte_total": 0,
            "distinct_key_bytes": 0,
            "layers_demanded": [],
            "n_expert_used": 0,
            "observed_slots": [],
            "slot_coverage_per_mille": 0,
            "one_token_working_set_keys": 0,
            "one_token_working_set_bytes": 0,
            "omitted_truncated_graphs": 0,
            "omitted_layer_positions": 0,
            "graph_phases": {"prefill": 0, "decode": 0, "single_token_first_graph": 0},
        },
    }
    try:
        if not valid_path(model_ir_path):
            raise Fault("R3_PATH", "")
        requested = parse_budget(budget_text)
        state["requested"] = requested
        paths = read_trace_list(trace_list_path, state)
        sizes = decode_model_ir(model_ir_path, state)
        if requested < state["model"]["largest_expert_bytes"]:
            raise Fault("R3_BUDGET_TOO_SMALL", "")
        streams = build_stream(paths, sizes, state, reset_per_trace)
        model = state["model"]
        key_space = model["n_layer"] * model["n_expert"]
        smallest = model["smallest_expert_bytes"]
        capacity = min(key_space, requested // smallest if smallest else key_space)
        replay_work = state["stream"]["demand_count"] * capacity
        reset_work = len(paths) * key_space if reset_per_trace else 0
        if replay_work > MAX_SIMULATION_STEPS - reset_work:
            raise Fault("R3_SIMULATION_COST", "")
        budgets = build_budgets(state, requested)
        results = {}
        for order in ORDERS:
            keys, toks, weights, bounds = streams[order]
            for entry in budgets:
                for policy in POLICY_NAMES:
                    results[(order, entry["bytes"], policy)] = replay(
                        keys, toks, weights, sizes, entry["bytes"], policy,
                        window_of(policy), topk_of(policy),
                        model["n_layer"], model["n_expert"], None, bounds, reset_per_trace,
                    )
        verdict = decide(state, streams, sizes, budgets, results, requested, reset_per_trace)
        return render(state, budgets, results, verdict)
    except Fault as fault:
        return empty_document(state, fault.code, fault.detail)


def main(argv):
    reset_per_trace = len(argv) == 5 and argv[1] == "--reset"
    offset = 2 if reset_per_trace else 1
    if len(argv) != offset + 3:
        sys.stderr.write("usage: residency_oracle.py [--reset] TRACE_LIST MODEL_IR.json BUDGET_BYTES\n")
        return 2
    document = simulate(argv[offset], argv[offset + 1], argv[offset + 2], reset_per_trace)
    sys.stdout.write(json.dumps(document, separators=(",", ":"), sort_keys=False) + "\n")
    return 0 if document["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
