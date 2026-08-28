"""The R2 locality gate's aggregation function.

`docs/specs/roadmap.md` section R2 asks one question — 条件付き局所性が存在するか、数値で判断できること,
that conditional locality exists and can be judged numerically. `docs/specs/r2a-expert-trace.md`
shipped the per-transcript `R2_ACTIVATION_TRACE` document; this module pools many of those documents
into one verdict.

It is a pure function of a list of already-parsed documents, deliberately separate from
`scripts/run-expert-locality-gate` so that `scripts/run-expert-trace-smoke` can exercise it on the
synthetic corpus with generator-known expert ids and no model, no network, and no instrument.

Every number it produces is an integer per mille. Floating point appears only inside the Wilson
bound and the design effect, and every output is floored to per mille before any comparison, so the
verdict is a comparison of integers and is bit-reproducible.

The trials the interval is computed over are *not* independent: one prompt contributes every layer
and every token position it has, and those observations share a prompt, a tokenization, and a
router state. The gate therefore reports two intervals — the naive Wilson interval, and a
cluster-robust interval that widens Wilson by the measured design effect with the prompt as the
cluster — and the verdict uses the cluster-robust lower bound.
"""

TRUNCATION_PRINTED = 6
TRUNCATION_HALF = 3

# The 95% two-sided normal quantile. The gate reports one interval and one verdict; a configurable
# confidence level would be a knob with no consumer.
Z_95 = 1.959963984540054

# Section 2.5.7's working-set windows, restricted to the ones a `printed = min(ne, 6)` transcript can
# ever sample (section 6, "One finding, not a correction").
OBSERVABLE_WINDOWS = (1, 2, 4)


class GateError(Exception):
    """An instrument or corpus problem, never a verdict. The gate is a measurement: it exits
    nonzero only when it could not measure."""


def printed_count(extent):
    return extent if extent <= TRUNCATION_PRINTED else TRUNCATION_PRINTED


def require_compact_router_axes(documents, labels=None):
    """Admit only the compact router-slot observations used by the historical R2/R3 gates.

    R2c deliberately prints every router slot. Replaying the already-recorded locality and
    residency measurements with that instrument would therefore change their input streams even
    when decode is disabled with ``-n 0``. These gates fail closed instead: a caller that wants
    full-axis or decode evidence must use R2c's own qualification or a new measured capability.
    """
    if labels is None:
        labels = [str(index) for index in range(len(documents))]
    if len(labels) != len(documents):
        raise GateError("document and label counts differ")

    for label, document in zip(labels, documents):
        moe = document.get("moe") or {}
        used = moe.get("n_expert_used")
        if document.get("status") != "ok" or not moe.get("present") \
                or not isinstance(used, int) or isinstance(used, bool) or used <= 0:
            # The owning consumer reports the more specific document/router error. This helper
            # only owns admission of the print form once those fields are meaningful.
            continue
        expected = set(range(used)) if used <= TRUNCATION_PRINTED else {
            0, 1, 2, used - 3, used - 2, used - 1,
        }
        if used > TRUNCATION_PRINTED and moe.get("slots_truncated") is not True:
            raise GateError(
                "%s: historical gate requires compact router axes; full-axis R2c input refused"
                % label)
        groups = {}
        for row in document.get("selections") or []:
            key = (row.get("graph"), row.get("layer"), row.get("token"))
            groups.setdefault(key, set()).add(row.get("slot"))
        for key, slots in groups.items():
            if slots != expected:
                raise GateError(
                    "%s: historical gate requires compact router axes; group %r has slots %r"
                    % (label, key, sorted(slots)))


def wilson_bounds(hits, trials, z=Z_95):
    """The Wilson score interval for a binomial proportion, returned as floats in [0, 1].

    Wilson rather than Wald because the null proportion here is 0.125 and a Wald interval is
    badly behaved that far from one half; it also stays inside [0, 1] at every count.
    """
    if trials <= 0:
        return (0.0, 1.0)
    phat = hits / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (phat + z2 / (2.0 * trials)) / denominator
    margin = (z / denominator) * (
        (phat * (1.0 - phat) / trials + z2 / (4.0 * trials * trials)) ** 0.5)
    return (max(0.0, center - margin), min(1.0, center + margin))


def design_effect(clusters, hits, trials):
    """The design effect of clustering the Bernoulli trials by prompt, or `None` when it cannot be
    estimated from the data.

    `clusters` is a list of `(hits, trials)` pairs, one per cluster. `p^` is the ratio estimator
    `sum(hits) / sum(trials)`, whose cluster-robust variance is the standard linearized form

        var = C / ((C - 1) * N^2) * sum((h_c - p^ * n_c)^2)

    and the design effect is that variance divided by the binomial variance `p^(1 - p^) / N` the
    Wilson interval assumes. One cluster estimates no between-cluster variance, and a degenerate
    proportion has no binomial variance to divide by; both return `None`.
    """
    usable = [(hits_c, trials_c) for hits_c, trials_c in clusters if trials_c > 0]
    if len(usable) < 2 or trials <= 0:
        return None
    phat = hits / trials
    binomial = phat * (1.0 - phat) / trials
    if binomial <= 0.0:
        return None
    count = len(usable)
    residual = sum((hits_c - phat * trials_c) ** 2 for hits_c, trials_c in usable)
    return (count / ((count - 1) * float(trials) ** 2) * residual) / binomial


def cluster_bounds(clusters, hits, trials, z=Z_95):
    """The Wilson interval widened by the design effect, as `(low, high, deff, estimated)`.

    Widening is done by deflating the sample size — `N_eff = N / deff`, `hits_eff = p^ * N_eff` —
    rather than by scaling a Wald margin, so the interval keeps Wilson's asymmetry and stays inside
    [0, 1]. The design effect is floored at 1: clustering is allowed to widen the interval and never
    to narrow it, so an unestimable or negative intracluster correlation leaves the naive interval
    unchanged and the verdict no easier to pass.
    """
    measured = design_effect(clusters, hits, trials)
    effective = 1.0 if measured is None or measured < 1.0 else measured
    if trials <= 0:
        return (0.0, 1.0, effective, measured is not None)
    phat = hits / trials
    effective_trials = trials / effective
    low, high = wilson_bounds(phat * effective_trials, effective_trials, z)
    return (low, high, effective, measured is not None)


def entropy_per_mille(counts, n_expert):
    """The Shannon entropy of an expert-use histogram, normalized by `log(n_expert)` so that a
    perfectly uniform router is 1000 and a single-expert router is 0."""
    total = sum(counts)
    if total <= 0 or n_expert <= 1:
        return None
    from math import log
    h = 0.0
    for count in counts:
        if count <= 0:
            continue
        p = count / total
        h -= p * log(p)
    return int(h / log(n_expert) * 1000)


def top_mass_per_mille(counts, top=8):
    total = sum(counts)
    if total <= 0:
        return None
    return sum(sorted(counts, reverse=True)[:top]) * 1000 // total


def _reuse_triple(groups):
    """Adjacent-token reuse over one `(document, graph, layer)` stratum.

    A pair is two token indices differing by exactly one that were both observed. The numerator
    counts experts selected at `t` that are selected again at `t+1`; the denominator counts the
    experts selected at `t+1`. This is section 2.5.7's definition, recomputed here from
    `selections[]` rather than trusted from `locality`, so that the two agree or the gate says so.
    """
    pairs = numerator = denominator = 0
    for key in sorted(groups):
        following = (key[0], key[1], key[2] + 1)
        if following not in groups:
            continue
        pairs += 1
        numerator += len(groups[key] & groups[following])
        denominator += len(groups[following])
    return pairs, numerator, denominator


def aggregate(documents, labels=None):
    """Pool `documents` into one locality verdict.

    `documents` are parsed `R2_ACTIVATION_TRACE` objects. Every one must be `status: "ok"` with
    `moe.present` true and the same `(n_expert, n_expert_used)`; anything else is a `GateError`,
    because a gate that averages over two different routers measures nothing.
    """
    if not documents:
        raise GateError("no documents")
    if labels is None:
        labels = [str(index) for index in range(len(documents))]

    n_expert = None
    n_expert_used = None
    for label, document in zip(labels, documents):
        if document.get("status") != "ok":
            raise GateError("%s: status %r (%s)"
                            % (label, document.get("status"), document.get("error_code")))
        moe = document["moe"]
        if not moe["present"]:
            raise GateError("%s: moe.present is false" % label)
        if moe["n_expert"] is None:
            raise GateError("%s: n_expert is null" % label)
        if n_expert is None:
            n_expert, n_expert_used = moe["n_expert"], moe["n_expert_used"]
        elif (moe["n_expert"], moe["n_expert_used"]) != (n_expert, n_expert_used):
            raise GateError("%s: router shape (%s, %s) differs from (%s, %s)"
                            % (label, moe["n_expert"], moe["n_expert_used"], n_expert,
                               n_expert_used))

    require_compact_router_axes(documents, labels)

    observed_slots = printed_count(n_expert_used)
    # The null the roadmap gate is judged against: under a router that picks `n_expert_used` of
    # `n_expert` uniformly at random and independently per token, an expert selected at `t+1` is
    # also among the `n_expert_used` selected at `t` with probability `k/n`.
    null_per_mille = n_expert_used * 1000 // n_expert
    # The null for what is actually *observed*: only `observed_slots` of the `n_expert_used`
    # experts at `t` are printed, so a hit requires membership in the printed subset. This is the
    # smaller, more accurate null; the verdict uses the larger one above, which is strictly
    # conservative.
    observed_null_per_mille = observed_slots * 1000 // n_expert

    # Pooled reuse, per-layer strata, and the histograms, recomputed from `selections[]`.
    all_groups = {}
    layer_groups = {}
    layer_histogram = {}
    phase_groups = {"prefill": {}, "decode": {}}
    documents_with_pairs = 0
    truncated_documents = 0
    token_reduced_layers = set()
    documents_token_reduced = 0
    token_positions = 0
    for index, document in enumerate(documents):
        phases = {row["ordinal"]: row["phase"] for row in document["graphs"]}
        if any(row.get("tokens_truncated") for row in document["graphs"]):
            truncated_documents += 1
        # Section 6 item 20's omission, pooled: every layer any document dropped as token-reduced,
        # and how many documents dropped one. A layer listed here contributed no `selections[]` row
        # and therefore nothing to any number below, which is exactly what has to stay visible.
        reduced = document["moe"].get("token_reduced_layers") or []
        if reduced:
            documents_token_reduced += 1
            token_reduced_layers.update(reduced)
        token_positions += sum(row["tokens_observed"] or 0 for row in document["graphs"])
        local = {}
        for row in document["selections"]:
            key = (index, row["graph"], row["layer"], row["token"])
            local.setdefault(key, set()).add(row["expert"])
            layer_histogram.setdefault(row["layer"], {})
            layer_histogram[row["layer"]][row["expert"]] = (
                layer_histogram[row["layer"]].get(row["expert"], 0) + 1)
        for key, experts in local.items():
            stratum = (key[0], key[1], key[2])
            all_groups[(stratum, 0, key[3])] = experts
            layer_groups.setdefault(key[2], {})[(stratum, 0, key[3])] = experts
            phase = phases.get(key[1])
            if phase in phase_groups:
                phase_groups[phase][(stratum, 0, key[3])] = experts
        if _reuse_triple({(k[0], 0, k[3]): v for k, v in local.items()})[0]:
            documents_with_pairs += 1

    pairs, numerator, denominator = _reuse_triple(all_groups)
    if denominator <= 0:
        raise GateError("no adjacent observed token pair in %d document(s); the corpus cannot "
                        "answer the gate" % len(documents))

    # Cross-check against the parser's own aggregate: this module and `src/expert_trace.align`
    # implement section 2.5.7 independently, and a disagreement is an instrument problem.
    parser_pairs = sum(document["locality"]["adjacent_pair_count"] for document in documents)
    parser_numerator = sum(document["locality"]["reuse_numerator"] or 0 for document in documents)
    parser_denominator = sum(document["locality"]["reuse_denominator"] or 0
                             for document in documents)
    if (parser_pairs, parser_numerator, parser_denominator) != (pairs, numerator, denominator):
        raise GateError("the pooled recomputation %d/%d over %d pairs disagrees with the parser's "
                        "%d/%d over %d pairs"
                        % (numerator, denominator, pairs, parser_numerator, parser_denominator,
                           parser_pairs))

    per_mille = numerator * 1000 // denominator
    low, high = wilson_bounds(numerator, denominator)
    low_per_mille = int(low * 1000)
    high_per_mille = int(high * 1000)

    # The clusters. One prompt contributes every layer and every token position it has, so its
    # trials share a tokenization and a router state and are not the independent draws Wilson
    # assumes. A pair never spans two documents — both of its keys carry the same
    # `(document, graph, layer)` stratum — so partitioning `all_groups` by document partitions the
    # pairs, and the per-document triples sum to the pooled one.
    document_groups = {}
    layer_document_groups = {}
    for key, experts in all_groups.items():
        document_index, _, layer = key[0]
        document_groups.setdefault(document_index, {})[key] = experts
        layer_document_groups.setdefault(layer, {}).setdefault(document_index, {})[key] = experts

    clusters = [_reuse_triple(groups)[1:] for groups in document_groups.values()]
    cluster_low, cluster_high, deff, deff_estimated = cluster_bounds(clusters, numerator,
                                                                    denominator)
    cluster_low_per_mille = int(cluster_low * 1000)
    cluster_high_per_mille = int(cluster_high * 1000)

    per_layer = []
    layers_clearing = 0
    for layer in sorted(layer_groups):
        l_pairs, l_numerator, l_denominator = _reuse_triple(layer_groups[layer])
        l_low, l_high = wilson_bounds(l_numerator, l_denominator)
        l_low_per_mille = int(l_low * 1000)
        l_clusters = [_reuse_triple(groups)[1:]
                      for groups in layer_document_groups.get(layer, {}).values()]
        l_cluster_low, l_cluster_high, l_deff, _ = cluster_bounds(l_clusters, l_numerator,
                                                                  l_denominator)
        l_cluster_low_per_mille = int(l_cluster_low * 1000)
        # A stratum clears the null on the same rule the pooled verdict uses: the cluster-robust
        # lower bound, not the naive one.
        clears = bool(l_denominator and l_cluster_low_per_mille > null_per_mille)
        if clears:
            layers_clearing += 1
        histogram = layer_histogram.get(layer, {})
        counts = list(histogram.values())
        per_layer.append({
            "layer": layer,
            "adjacent_pair_count": l_pairs,
            "reuse_numerator": l_numerator,
            "reuse_denominator": l_denominator,
            "reuse_per_mille": (l_numerator * 1000 // l_denominator) if l_denominator else None,
            "wilson_low_per_mille": l_low_per_mille if l_denominator else None,
            "wilson_high_per_mille": int(l_high * 1000) if l_denominator else None,
            "cluster_low_per_mille": l_cluster_low_per_mille if l_denominator else None,
            "cluster_high_per_mille": int(l_cluster_high * 1000) if l_denominator else None,
            "design_effect_per_mille": int(l_deff * 1000) if l_denominator else None,
            "clears_null": clears,
            "distinct_experts": len(histogram),
            "entropy_per_mille": entropy_per_mille(counts, n_expert),
            "top8_mass_per_mille": top_mass_per_mille(counts, 8),
        })

    phase_split = {}
    for name, groups in phase_groups.items():
        p_pairs, p_numerator, p_denominator = _reuse_triple(groups)
        if not p_denominator:
            phase_split[name] = None
            continue
        phase_split[name] = {
            "adjacent_pair_count": p_pairs,
            "reuse_numerator": p_numerator,
            "reuse_denominator": p_denominator,
            "reuse_per_mille": p_numerator * 1000 // p_denominator,
        }

    # Working-set growth against the null `n * (1 - (1 - k/n) ** w)`, with `k` the number of experts
    # actually *observed* per token, because that is what the union is taken over.
    working_set = []
    for width in OBSERVABLE_WINDOWS:
        samples = unique_sum = 0
        for document in documents:
            for row in document["locality"]["working_set"]:
                if row["window"] != width:
                    continue
                samples += row["sample_count"]
                unique_sum += row["unique_sum"]
        null_unique = n_expert * (1.0 - (1.0 - observed_slots / n_expert) ** width)
        working_set.append({
            "window": width,
            "sample_count": samples,
            "unique_sum": unique_sum,
            "unique_mean_per_mille": (unique_sum * 1000 // samples) if samples else None,
            "null_unique_mean_per_mille": int(null_unique * 1000),
            "deficit_per_mille": ((int(null_unique * 1000) - unique_sum * 1000 // samples)
                                  if samples else None),
        })

    pooled_counts = {}
    for histogram in layer_histogram.values():
        for expert, count in histogram.items():
            pooled_counts[expert] = pooled_counts.get(expert, 0) + count
    pooled_values = list(pooled_counts.values())

    # The verdict, on integers only. Both halves must hold: the interval must exclude the null, and
    # the point estimate must be at least half again the null. The second half is what separates a
    # statistically detectable effect from one large enough to place an expert in a cache tier.
    # The interval half is judged on the *cluster-robust* lower bound, which is never above the
    # naive Wilson bound, so a verdict carried entirely by between-prompt variation cannot pass.
    excludes_null = cluster_low_per_mille > null_per_mille
    materially_above = per_mille * 2 >= null_per_mille * 3
    verdict = "LOCALITY" if (excludes_null and materially_above) else "NO_LOCALITY"

    return {
        "verdict": verdict,
        "excludes_null": excludes_null,
        "materially_above_null": materially_above,
        "document_count": len(documents),
        "documents_with_pairs": documents_with_pairs,
        "truncated_documents": truncated_documents,
        "documents_token_reduced": documents_token_reduced,
        "token_reduced_layers": sorted(token_reduced_layers),
        "token_positions": token_positions,
        "n_expert": n_expert,
        "n_expert_used": n_expert_used,
        "observed_slots_per_token": observed_slots,
        "null_per_mille": null_per_mille,
        "observed_null_per_mille": observed_null_per_mille,
        "threshold_per_mille": null_per_mille * 3 // 2,
        "adjacent_pair_count": pairs,
        "reuse_numerator": numerator,
        "reuse_denominator": denominator,
        "reuse_per_mille": per_mille,
        "wilson_low_per_mille": low_per_mille,
        "wilson_high_per_mille": high_per_mille,
        "cluster_count": len(clusters),
        "design_effect_per_mille": int(deff * 1000),
        "design_effect_estimated": deff_estimated,
        "cluster_low_per_mille": cluster_low_per_mille,
        "cluster_high_per_mille": cluster_high_per_mille,
        "ratio_to_null_per_mille": per_mille * 1000 // null_per_mille,
        "layer_count": len(per_layer),
        "layers_clearing_null": layers_clearing,
        "per_layer": per_layer,
        "phase_split": phase_split,
        "working_set": working_set,
        "pooled_distinct_experts": len(pooled_counts),
        "pooled_entropy_per_mille": entropy_per_mille(pooled_values, n_expert),
        "pooled_top8_mass_per_mille": top_mass_per_mille(pooled_values, 8),
    }


CAVEATS = (
    "prefill only: build 10566 evaluates one graph per invocation, so no decode step is observed "
    "and this measurement supports no decode or cache-policy claim",
    "at most 6 token positions per prompt are ever printed; the corpus is authored to <= 6 tokens "
    "so that no observed position is hidden and every adjacency is real",
    "reuse is measured among OBSERVED slots only: the printer emits 3+3 of n_expert_used, so each "
    "token contributes a printed subset of its experts; restricting the t side can only remove "
    "hits, so that half of the truncation biases p^ low, while the t+1 restriction moves numerator "
    "and denominator together and its direction is not established here",
    "the last layer of each graph is token-reduced by the instrument (the output-token GET_ROWS "
    "runs before its feed-forward) and contributes nothing to any aggregate",
    "the printed slots within one token are drawn without replacement, so the Wilson interval's "
    "independence assumption is approximate",
    "the trials are clustered by prompt: one prompt supplies every layer and token position it "
    "has. The naive Wilson interval assumes independence; the cluster-robust interval widens it by "
    "the measured design effect (prompt as cluster, floored at 1) and is the one the verdict uses",
    "the verdict is judged against k/n, the null for the full top-k set; the null for the printed "
    "subset is smaller, which makes the threshold conservative",
)


# --- R2D: the full-axis, phase-aware decode path (begin) -------------------------------------
#
# Everything above this line is the historical R2/R3 compact-axis gate and is unchanged. R2c's
# patched instrument prints every router slot and evaluates decode graphs, which makes two
# measurements possible that the compact path deliberately refuses: prefill reuse over all
# `n_expert_used` slots, and reuse between the tokens of consecutive decode graphs.
#
# The historical path can never be reused for that, and not only because of the print form. Its
# adjacency is *within one graph*: `_reuse_triple` pairs token `t` with token `t + 1` of the same
# `(document, graph, layer)` stratum. Every decode graph carries exactly one token, so that
# definition finds no decode pair at all — it is why the merged prefill gate reports
# `phase_split.decode` as `null` even on a multi-graph transcript. The decode gate therefore
# defines adjacency over the *sequence*: one chain of observation points per `(document, layer)`,
# ordered by `(graph ordinal, token index)`, where two consecutive points are adjacent when they
# are consecutive token positions of one graph, or the last token of graph `g` and the first token
# of graph `g + 1`.

# The decode gate observes 17 sequence positions per prompt at `-n 16`, so it can afford a wider
# working-set window than the compact path's `printed = min(ne, 6)` ceiling allowed.
DECODE_WINDOWS = (1, 2, 4, 8)

# `graphs[].phase` is three-valued (`docs/specs/r2a-expert-trace.md` section 2.5.5): a one-token
# first graph is `single_token_first_graph`, because the transcript cannot separate a one-token
# prompt from a decode step. A pair touching one is counted and reported, never silently folded
# into prefill or decode.
PAIR_PHASES = ("prefill", "decode", "boundary")


def require_full_router_axes(documents, labels=None):
    """Admit only complete R2c router observations.

    The decode gate's denominator is the full `n_expert_used` set, and its adjacency is only real
    when no token position is hidden. Both are properties of the print form, so both are checked
    here rather than assumed: every retained `(graph, layer, token)` group must carry exactly slots
    `0 .. n_expert_used - 1`, `moe.slots_truncated` must be false, and no graph may report a
    truncated token axis. A compact build-10566 document fails all three, which is the mirror image
    of `require_compact_router_axes` and keeps the two corpora from ever being pooled.
    """
    if labels is None:
        labels = [str(index) for index in range(len(documents))]
    if len(labels) != len(documents):
        raise GateError("document and label counts differ")

    for label, document in zip(labels, documents):
        moe = document.get("moe") or {}
        used = moe.get("n_expert_used")
        if document.get("status") != "ok":
            raise GateError("%s: status %r (%s)"
                            % (label, document.get("status"), document.get("error_code")))
        if not moe.get("present"):
            raise GateError("%s: moe.present is false" % label)
        if not isinstance(used, int) or isinstance(used, bool) or used <= 0:
            raise GateError("%s: n_expert_used is not a positive integer" % label)
        if moe.get("slots_truncated") is not False:
            raise GateError(
                "%s: decode gate requires full router axes; compact R2A input refused" % label)
        for row in document.get("graphs") or []:
            if row.get("tokens_truncated"):
                raise GateError(
                    "%s: graph %r has a truncated token axis; adjacency would not be real"
                    % (label, row.get("ordinal")))
        expected = set(range(used))
        groups = {}
        for row in document.get("selections") or []:
            key = (row.get("graph"), row.get("layer"), row.get("token"))
            groups.setdefault(key, set()).add(row.get("slot"))
        for key, slots in groups.items():
            if slots != expected:
                raise GateError("%s: decode gate requires full router axes; group %r has slots %r"
                                % (label, key, sorted(slots)))


def entry_token_fingerprints(lines):
    """One printed-value fingerprint per token position of every graph, in graph order.

    The `R2_ACTIVATION_TRACE` document carries no token identity, and greedy decode can fall into a
    repetition loop whose adjacent "tokens" are the same token. Distinguishing conditional locality
    from a degenerate loop needs token identity, so this reads the one place the transcript states
    it: the entry `embd = ... GET_ROWS(token_embd.weight..., inp_tokens...)` block, whose row `i` is
    the embedding row of token `i`. The printed values of that row are a deterministic function of
    the token id, so equal fingerprints mean the same token.

    This is a *fingerprint*, not a token id, and it is read for one diagnostic and one sensitivity
    arm only; no headline verdict depends on it. It returns one list of fingerprints per entry
    block, in transcript order, and the caller is required to check that each list has exactly the
    graph's `n_tokens` entries — anything else means the block was truncated or the grammar moved,
    and the caller must then report the arm as unavailable rather than exclude the wrong pairs.
    """
    blocks = []
    current = None
    for line in lines:
        text = line.rstrip("\n").rstrip("\r")
        if text.startswith("common_debug_cb_eval:"):
            if "GET_ROWS(token_embd.weight" in text:
                current = []
                blocks.append(current)
            else:
                current = None
            continue
        if current is None:
            continue
        stripped = text.strip()
        if stripped.startswith("sum ="):
            current = None
            continue
        if not stripped.startswith("[") or not stripped.endswith("],"):
            continue
        body = stripped[1:-2].strip()
        if not body:
            continue
        current.append(",".join(part.strip() for part in body.split(",")))
    return blocks


def _pair_phase(first_phase, second_phase):
    """The phase of one adjacent pair, or `None` when either side is not prefill or decode."""
    if first_phase == "prefill" and second_phase == "prefill":
        return "prefill"
    if first_phase == "decode" and second_phase == "decode":
        return "decode"
    if first_phase == "prefill" and second_phase == "decode":
        return "boundary"
    return None


def _sequence_adjacent(first, second, graphs):
    """True when `second` is the token position immediately after `first` in the real sequence."""
    if first[0] == second[0]:
        return second[1] == first[1] + 1
    if second[0] != first[0] + 1 or second[1] != 0:
        return False
    n_tokens = graphs.get(first[0], {}).get("n_tokens")
    return isinstance(n_tokens, int) and first[1] == n_tokens - 1


def _decode_pairs(documents, fingerprints=None):
    """Every sequence-adjacent observation pair of every `(document, layer)` chain.

    Each record is `(cluster, layer, phase, hits, trials, repeated)`, where `repeated` is `True`
    when both sides carry the same token fingerprint, `False` when they carry different ones, and
    `None` when no fingerprint was supplied for that document.
    """
    records = []
    ambiguous = 0
    for index, document in enumerate(documents):
        graphs = {row["ordinal"]: row for row in document["graphs"]}
        experts = {}
        for row in document["selections"]:
            experts.setdefault((row["graph"], row["layer"], row["token"]), set()).add(row["expert"])
        chains = {}
        for graph, layer, token in experts:
            chains.setdefault(layer, []).append((graph, token))
        marks = fingerprints[index] if fingerprints is not None else None
        for layer, positions in sorted(chains.items()):
            positions.sort()
            for first, second in zip(positions, positions[1:]):
                if not _sequence_adjacent(first, second, graphs):
                    continue
                phase = _pair_phase(graphs[first[0]]["phase"], graphs[second[0]]["phase"])
                if phase is None:
                    ambiguous += 1
                    continue
                before = experts[(first[0], layer, first[1])]
                after = experts[(second[0], layer, second[1])]
                repeated = None
                if marks is not None:
                    left, right = marks.get(first), marks.get(second)
                    repeated = None if left is None or right is None else left == right
                records.append((index, layer, phase, len(before & after), len(after), repeated))
    return records, ambiguous


def _phase_verdict(records, n_expert, n_expert_used, null_per_mille):
    """Pool one phase's pair records into the same verdict the historical gate uses."""
    hits = sum(record[3] for record in records)
    trials = sum(record[4] for record in records)
    if not trials:
        return None

    clusters = {}
    layers = {}
    layer_clusters = {}
    for cluster, layer, _, record_hits, record_trials, _ in records:
        entry = clusters.setdefault(cluster, [0, 0])
        entry[0] += record_hits
        entry[1] += record_trials
        layer_entry = layers.setdefault(layer, [0, 0, 0])
        layer_entry[0] += record_hits
        layer_entry[1] += record_trials
        layer_entry[2] += 1
        layer_cluster = layer_clusters.setdefault(layer, {}).setdefault(cluster, [0, 0])
        layer_cluster[0] += record_hits
        layer_cluster[1] += record_trials

    per_mille = hits * 1000 // trials
    low, high = wilson_bounds(hits, trials)
    cluster_low, cluster_high, deff, deff_estimated = cluster_bounds(
        [tuple(entry) for entry in clusters.values()], hits, trials)
    cluster_low_per_mille = int(cluster_low * 1000)

    per_layer = []
    layers_clearing = 0
    for layer in sorted(layers):
        layer_hits, layer_trials, layer_pairs = layers[layer]
        layer_low, layer_high = wilson_bounds(layer_hits, layer_trials)
        layer_cluster_low, layer_cluster_high, layer_deff, _ = cluster_bounds(
            [tuple(entry) for entry in layer_clusters[layer].values()], layer_hits, layer_trials)
        clears = bool(layer_trials and int(layer_cluster_low * 1000) > null_per_mille)
        if clears:
            layers_clearing += 1
        per_layer.append({
            "layer": layer,
            "adjacent_pair_count": layer_pairs,
            "reuse_numerator": layer_hits,
            "reuse_denominator": layer_trials,
            "reuse_per_mille": layer_hits * 1000 // layer_trials,
            "wilson_low_per_mille": int(layer_low * 1000),
            "wilson_high_per_mille": int(layer_high * 1000),
            "cluster_low_per_mille": int(layer_cluster_low * 1000),
            "cluster_high_per_mille": int(layer_cluster_high * 1000),
            "design_effect_per_mille": int(layer_deff * 1000),
            "clears_null": clears,
        })

    excludes_null = cluster_low_per_mille > null_per_mille
    materially_above = per_mille * 2 >= null_per_mille * 3
    return {
        "verdict": "LOCALITY" if (excludes_null and materially_above) else "NO_LOCALITY",
        "excludes_null": excludes_null,
        "materially_above_null": materially_above,
        "adjacent_pair_count": len(records),
        "reuse_numerator": hits,
        "reuse_denominator": trials,
        "reuse_per_mille": per_mille,
        "wilson_low_per_mille": int(low * 1000),
        "wilson_high_per_mille": int(high * 1000),
        "cluster_count": len(clusters),
        "design_effect_per_mille": int(deff * 1000),
        "design_effect_estimated": deff_estimated,
        "cluster_low_per_mille": cluster_low_per_mille,
        "cluster_high_per_mille": int(cluster_high * 1000),
        "ratio_to_null_per_mille": per_mille * 1000 // null_per_mille,
        "layer_count": len(per_layer),
        "layers_clearing_null": layers_clearing,
        "per_layer": per_layer,
    }


def _graph_phase_histograms(documents, n_expert):
    """The expert-use histogram of every selection, split by the phase of its graph."""
    counts = {"prefill": {}, "decode": {}}
    for document in documents:
        phases = {row["ordinal"]: row["phase"] for row in document["graphs"]}
        for row in document["selections"]:
            bucket = counts.get(phases.get(row["graph"]))
            if bucket is None:
                continue
            bucket[row["expert"]] = bucket.get(row["expert"], 0) + 1
    summary = {}
    for name, histogram in counts.items():
        values = list(histogram.values())
        summary[name] = {
            "selection_count": sum(values),
            "distinct_experts": len(histogram),
            "entropy_per_mille": entropy_per_mille(values, n_expert),
            "top8_mass_per_mille": top_mass_per_mille(values, 8),
        }
    return summary


def _phase_working_sets(documents, n_expert, observed_slots):
    """Working-set growth over `w` consecutive observed positions of one graph phase.

    Recomputed here rather than read from `locality.working_set`, because the document's own
    windows never cross a graph boundary and a decode graph holds one token: every decode window
    above `w = 1` exists only in the sequence view.
    """
    runs = {"prefill": {width: [0, 0] for width in DECODE_WINDOWS},
            "decode": {width: [0, 0] for width in DECODE_WINDOWS}}
    for document in documents:
        graphs = {row["ordinal"]: row for row in document["graphs"]}
        experts = {}
        for row in document["selections"]:
            experts.setdefault((row["graph"], row["layer"], row["token"]), set()).add(row["expert"])
        chains = {}
        for graph, layer, token in experts:
            chains.setdefault(layer, []).append((graph, token))
        for layer, positions in chains.items():
            positions.sort()
            for start in range(len(positions)):
                phase = graphs[positions[start][0]]["phase"]
                if phase not in runs:
                    continue
                union = set()
                for step in range(max(DECODE_WINDOWS)):
                    if start + step >= len(positions):
                        break
                    point = positions[start + step]
                    if graphs[point[0]]["phase"] != phase:
                        break
                    if step and not _sequence_adjacent(positions[start + step - 1], point, graphs):
                        break
                    union |= experts[(point[0], layer, point[1])]
                    width = step + 1
                    if width in runs[phase]:
                        runs[phase][width][0] += 1
                        runs[phase][width][1] += len(union)

    result = {}
    for phase, widths in runs.items():
        rows = []
        for width in DECODE_WINDOWS:
            samples, unique_sum = widths[width]
            null_unique = n_expert * (1.0 - (1.0 - observed_slots / n_expert) ** width)
            rows.append({
                "window": width,
                "sample_count": samples,
                "unique_sum": unique_sum,
                "unique_mean_per_mille": (unique_sum * 1000 // samples) if samples else None,
                "null_unique_mean_per_mille": int(null_unique * 1000),
                "deficit_per_mille": ((int(null_unique * 1000) - unique_sum * 1000 // samples)
                                      if samples else None),
            })
        result[phase] = rows
    return result


def _repetition(documents, fingerprints):
    """The token-repetition rate of every prompt's generated sequence.

    One rate per document over the *sequence*, counted once per position rather than once per
    layer: a repeated token is a property of the decode loop, not of a layer. `boundary` counts the
    single last-prompt-token / first-generated-token pair.
    """
    per_document = []
    pooled = {"decode": [0, 0], "boundary": [0, 0], "prefill": [0, 0]}
    for index, document in enumerate(documents):
        graphs = {row["ordinal"]: row for row in document["graphs"]}
        marks = fingerprints[index]
        points = sorted(marks)
        counts = {"decode": [0, 0], "boundary": [0, 0], "prefill": [0, 0]}
        for first, second in zip(points, points[1:]):
            if not _sequence_adjacent(first, second, graphs):
                continue
            phase = _pair_phase(graphs[first[0]]["phase"], graphs[second[0]]["phase"])
            if phase is None:
                continue
            counts[phase][1] += 1
            if marks[first] == marks[second]:
                counts[phase][0] += 1
        for phase, entry in counts.items():
            pooled[phase][0] += entry[0]
            pooled[phase][1] += entry[1]
        per_document.append({
            "document": index,
            "decode_repeated": counts["decode"][0],
            "decode_pairs": counts["decode"][1],
            "decode_repetition_per_mille": (counts["decode"][0] * 1000 // counts["decode"][1])
                                           if counts["decode"][1] else None,
            "distinct_generated_tokens": len({marks[point] for point in points
                                              if graphs[point[0]]["phase"] == "decode"}),
        })
    summary = {}
    for phase, entry in pooled.items():
        summary[phase] = {
            "repeated": entry[0],
            "pairs": entry[1],
            "repetition_per_mille": (entry[0] * 1000 // entry[1]) if entry[1] else None,
        }
    return {"pooled": summary, "per_document": per_document}


def aggregate_decode(documents, labels=None, fingerprints=None):
    """Pool full-axis multi-graph documents into the three R2D verdicts.

    `fingerprints` is optional and, when given, is one `{(graph, token): fingerprint}` mapping per
    document. It buys the token-repetition diagnostic and the sensitivity arm that excludes every
    pair whose two positions carry the same token; the three headline verdicts never use it.
    """
    if not documents:
        raise GateError("no documents")
    if labels is None:
        labels = [str(index) for index in range(len(documents))]
    if fingerprints is not None and len(fingerprints) != len(documents):
        raise GateError("document and fingerprint counts differ")

    n_expert = None
    n_expert_used = None
    for label, document in zip(labels, documents):
        moe = document["moe"]
        if moe["n_expert"] is None:
            raise GateError("%s: n_expert is null" % label)
        if n_expert is None:
            n_expert, n_expert_used = moe["n_expert"], moe["n_expert_used"]
        elif (moe["n_expert"], moe["n_expert_used"]) != (n_expert, n_expert_used):
            raise GateError("%s: router shape (%s, %s) differs from (%s, %s)"
                            % (label, moe["n_expert"], moe["n_expert_used"], n_expert,
                               n_expert_used))

    require_full_router_axes(documents, labels)

    # With every slot printed the observed null and the top-k null coincide, so the decode gate's
    # threshold is no longer the conservative approximation the merged prefill gate had to use.
    null_per_mille = n_expert_used * 1000 // n_expert
    records, ambiguous_pairs = _decode_pairs(documents, fingerprints)
    if not records:
        raise GateError("no sequence-adjacent pair in %d document(s); the corpus cannot answer the "
                        "gate" % len(documents))

    by_phase = {name: [] for name in PAIR_PHASES}
    for record in records:
        by_phase[record[2]].append(record)

    # The parser owns within-graph adjacency and this module owns the sequence view. Where the two
    # definitions coincide — pairs inside one prefill graph — they must agree exactly, or one of
    # them is wrong and no verdict below means anything.
    parser_hits = parser_trials = parser_pairs = 0
    for document in documents:
        row = (document["locality"].get("phase_split") or {}).get("prefill")
        if row:
            parser_pairs += row["adjacent_pair_count"]
            parser_hits += row["reuse_numerator"] or 0
            parser_trials += row["reuse_denominator"] or 0
    prefill_records = by_phase["prefill"]
    recomputed = (len(prefill_records), sum(record[3] for record in prefill_records),
                  sum(record[4] for record in prefill_records))
    if recomputed != (parser_pairs, parser_hits, parser_trials):
        raise GateError("the pooled prefill recomputation %d/%d over %d pair(s) disagrees with the "
                        "parser's %d/%d over %d pair(s)"
                        % (recomputed[1], recomputed[2], recomputed[0], parser_hits, parser_trials,
                           parser_pairs))

    phases = {name: _phase_verdict(by_phase[name], n_expert, n_expert_used, null_per_mille)
              for name in PAIR_PHASES}

    excluded = None
    repetition = None
    if fingerprints is not None:
        repetition = _repetition(documents, fingerprints)
        kept = {name: [record for record in by_phase[name] if record[5] is not True]
                for name in PAIR_PHASES}
        excluded = {
            "phases": {name: _phase_verdict(kept[name], n_expert, n_expert_used, null_per_mille)
                       for name in PAIR_PHASES},
            "dropped_pairs": {name: len(by_phase[name]) - len(kept[name]) for name in PAIR_PHASES},
            "unknown_pairs": sum(1 for record in records if record[5] is None),
        }

    graph_counts = {"prefill": 0, "decode": 0, "single_token_first_graph": 0}
    token_positions = 0
    truncated_documents = 0
    documents_token_reduced = 0
    token_reduced_layers = set()
    for document in documents:
        for row in document["graphs"]:
            if row["phase"] in graph_counts:
                graph_counts[row["phase"]] += 1
            token_positions += row["tokens_observed"] or 0
        if any(row.get("tokens_truncated") for row in document["graphs"]):
            truncated_documents += 1
        reduced = document["moe"].get("token_reduced_layers") or []
        if reduced:
            documents_token_reduced += 1
            token_reduced_layers.update(reduced)

    return {
        "document_count": len(documents),
        "n_expert": n_expert,
        "n_expert_used": n_expert_used,
        "observed_slots_per_token": n_expert_used,
        "null_per_mille": null_per_mille,
        "threshold_per_mille": null_per_mille * 3 // 2,
        "graph_counts": graph_counts,
        "token_positions": token_positions,
        "ambiguous_pairs": ambiguous_pairs,
        "truncated_documents": truncated_documents,
        "documents_token_reduced": documents_token_reduced,
        "token_reduced_layers": sorted(token_reduced_layers),
        "phases": phases,
        "excluding_repeats": excluded,
        "repetition": repetition,
        "histogram": _graph_phase_histograms(documents, n_expert),
        "working_set": _phase_working_sets(documents, n_expert, n_expert_used),
    }


DECODE_CAVEATS = (
    "greedy decode is the contract: the capture pins --temp 0 --seed 42 with the instrument's "
    "default sampler, so the generated sequence is the model's argmax continuation and not a "
    "sample from its distribution; a sampled continuation may route differently",
    "the context is -c 512 and every prompt is 6 tokens or fewer, so the whole measurement lives "
    "in the first two dozen positions of a sequence and says nothing about long context",
    "the decode arm observes ALIGN_LLM_DECODE_STEPS generated tokens per prompt and stops early on "
    "an end-of-generation token, so a prompt may contribute fewer decode graphs than requested",
    "greedy decode can enter a repetition loop, whose adjacent tokens are the same token and whose "
    "reuse is therefore trivially high; the gate reports the measured repetition rate and repeats "
    "every verdict with those pairs excluded",
    "token identity is a fingerprint of the printed entry-embedding row, not a decoded token id; "
    "it is used only for the repetition rate and the sensitivity arm",
    "prefill and decode are measured on different layer sets: a prefill graph's last layer is "
    "token-reduced by the instrument and contributes nothing, while a one-token decode graph has "
    "no reduction, so the decode arm can carry one layer the prefill arm cannot",
    "the boundary arm holds exactly one pair per prompt and layer, so it is the smallest of the "
    "three and its interval is correspondingly wide",
    "the trials are clustered by prompt: one prompt supplies every layer and every position it "
    "has. Each verdict uses the cluster-robust lower bound, with the design effect measured over "
    "prompt clusters and floored at 1",
    "the prefill arm here is NOT the merged prefill gate of section 8: it observes all "
    "n_expert_used slots rather than the compact printed six, so its number replaces nothing and "
    "the two are not comparable term by term",
)
# --- R2D: the full-axis, phase-aware decode path (end) ---------------------------------------
