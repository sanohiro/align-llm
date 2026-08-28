"""Trace-list projections for the R3 decode residency arms.

`scripts/run-decode-residency-gate` replays one full-axis R2c capture three times, and the three
arms differ only in which graphs of each `R2_ACTIVATION_TRACE` reach the simulator:

    mixed         every admitted graph, the document exactly as captured
    decode_only   graph 0 projected away, so the stream is generated tokens and nothing else
    prefill_only  every graph but graph 0 projected away, so the stream is prompt tokens and
                  nothing else, at the same full router axes as the other two

A projection is a projection *for the simulator*, not a re-derived R2A document: exactly the two
arrays `main --simulate-residency` reads — `graphs` and `selections` — are filtered, and every other
block (`input`, `graph`, R2A's own `locality`) still describes the whole captured transcript. That
is stated in the runner's caveats rather than silently repaired, because re-deriving those blocks
would make the result a second R2A document rather than a projection of one.

**The graph ordinals are kept as captured.** Renumbering the decode-only list would turn its first
graph into a one-token graph at ordinal 0, which `docs/specs/r2a-expert-trace.md` section 2.5.6
classifies as `single_token_first_graph` — "the transcript cannot tell a one-token prompt from a
decode step" — and the arm would then be measuring a phase it does not have.

This module is the one implementation of those projections. `scripts/run-decode-residency-gate`
applies it to real captures and `scripts/run-residency-sim-smoke` applies it to synthetic ones and
checks the result against `scripts/residency_oracle.py`, so the arm the hosted owner exercises is
the arm the real-model runner replays rather than a second copy that can drift from it.

No `json` round trip is used to copy a document: the two filtered arrays are rebuilt and every other
key is carried over by reference, so a caller must treat the result as read-only.
"""

# Graph 0 is the prompt's prefill graph in an R2c capture. `docs/specs/r2a-expert-trace.md` section
# 2.5.6 assigns the phase names from the ordinal and the token count, and this module never renames
# a graph: it only decides which ordinals survive.
PREFILL_ORDINAL = 0

# The arm names, in the order the runner reports them. `mixed` is the identity projection and is
# listed here so a caller can drive every arm from one table.
ARM_NAMES = ("mixed", "decode_only", "prefill_only")


def _select(document, keep):
    """`document` with `graphs` and `selections` restricted to the ordinals `keep` admits.

    Only the two arrays the simulator reads are rebuilt; every other key is carried over unchanged.
    """
    projected = dict(document)
    projected["graphs"] = [row for row in document.get("graphs") or [] if keep(row.get("ordinal"))]
    projected["selections"] = [row for row in document.get("selections") or []
                               if keep(row.get("graph"))]
    return projected


def project_mixed(document):
    """The identity projection: the captured document, graphs and all."""
    return _select(document, lambda ordinal: True)


def project_decode_only(document):
    """The captured document with graph 0 projected away and every ordinal left as captured."""
    return _select(document, lambda ordinal: ordinal != PREFILL_ORDINAL)


def project_prefill_only(document):
    """The captured document with every decode graph projected away.

    This is the arm that separates the two things R2c changed at once. Section 8's mixed and
    decode-only arms both differ from section 7.4's recorded stream in *two* ways — the router slot
    axis went from a printed six-of-eight subsample to all eight, and real decode graphs appeared —
    and a result that moved could be caused by either. This arm holds the corpus, the budget, the
    admission rule, and the full slot axis fixed and removes only the decode graphs, so a verdict
    that still differs from section 7.4's is a coverage effect and not a decode effect.
    """
    return _select(document, lambda ordinal: ordinal == PREFILL_ORDINAL)


PROJECTIONS = {
    "mixed": project_mixed,
    "decode_only": project_decode_only,
    "prefill_only": project_prefill_only,
}


def declared_demands(document):
    """The demands one document contributes: every selection naming a declared, untruncated graph.

    This mirrors `src/residency_sim.align`'s admission rather than counting `selections` blindly, so
    a caller's a-priori bound is the number the simulator will actually allocate. Because admission
    is decided per graph and a projection only removes whole graphs, the three arms partition one
    capture exactly: `mixed` = `prefill_only` + `decode_only`, demand for demand.
    """
    admitted = {row["ordinal"] for row in document.get("graphs") or []
                if not row.get("tokens_truncated")}
    return sum(1 for row in document.get("selections") or [] if row.get("graph") in admitted)
