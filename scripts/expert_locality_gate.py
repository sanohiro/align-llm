"""The R2 locality gate's aggregation function.

`docs/specs/roadmap.md` section R2 asks one question — 条件付き局所性が存在するか、数値で判断できること,
that conditional locality exists and can be judged numerically. `docs/specs/r2a-expert-trace.md`
shipped the per-transcript `R2_ACTIVATION_TRACE` document; this module pools many of those documents
into one verdict.

It is a pure function of a list of already-parsed documents, deliberately separate from
`scripts/run-expert-locality-gate` so that `scripts/run-expert-trace-smoke` can exercise it on the
synthetic corpus with generator-known expert ids and no model, no network, and no instrument.

Every number it produces is an integer per mille. Floating point appears only inside the Wilson
bound, and its two outputs are floored to per mille before any comparison, so the verdict is a
comparison of integers and is bit-reproducible.
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
    token_positions = 0
    for index, document in enumerate(documents):
        phases = {row["ordinal"]: row["phase"] for row in document["graphs"]}
        if any(row.get("tokens_truncated") for row in document["graphs"]):
            truncated_documents += 1
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

    per_layer = []
    layers_clearing = 0
    for layer in sorted(layer_groups):
        l_pairs, l_numerator, l_denominator = _reuse_triple(layer_groups[layer])
        l_low, l_high = wilson_bounds(l_numerator, l_denominator)
        l_low_per_mille = int(l_low * 1000)
        clears = bool(l_denominator and l_low_per_mille > null_per_mille)
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
    excludes_null = low_per_mille > null_per_mille
    materially_above = per_mille * 2 >= null_per_mille * 3
    verdict = "LOCALITY" if (excludes_null and materially_above) else "NO_LOCALITY"

    return {
        "verdict": verdict,
        "excludes_null": excludes_null,
        "materially_above_null": materially_above,
        "document_count": len(documents),
        "documents_with_pairs": documents_with_pairs,
        "truncated_documents": truncated_documents,
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
    "token contributes a printed subset of its experts and the estimate is biased low",
    "the final layer is token-reduced by the instrument (the output-token GET_ROWS runs before its "
    "feed-forward) and contributes nothing to any aggregate",
    "the printed slots within one token are drawn without replacement, so the Wilson interval's "
    "independence assumption is approximate",
    "the verdict is judged against k/n, the null for the full top-k set; the null for the printed "
    "subset is smaller, which makes the threshold conservative",
)
