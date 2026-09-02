# R8-RESET-CACHE-DECISION

Status: implementation contract, 2026-09-02

## 1. Decision and boundary

R8-SCORE-BASED-CACHE made selected router weights replayable, but its first real decode-corpus
measurement does not justify a runtime `router_weight_lfu` cache. At the 25 per cent expert-byte
budget it fetches more bytes than LRU on every decode-bearing arm: 208,706,912,256 against
176,661,381,120 on `mixed`, 164,826,513,408 against 134,615,285,760 on `decode_only`, and
37,437,652,992 against 33,722,744,832 on `decode_head4`.

Those arms pool forty prompts through one continuing cache. The current runtime owns one cache per
`--moe-decode-step` invocation, so a runtime implementation would reset between those prompts. This
capability closes that lifetime mismatch before allocating roughly one gigabyte to an expert cache:

- add `main --simulate-residency-reset TRACE_LIST MODEL_IR.json BUDGET_BYTES [OUT.json]`;
- emit `R3_RESIDENCY_SIM` schema 3 with `stream.pooling: "reset_per_trace"`;
- replay the unchanged eleven policies with every policy state reset at each admitted trace;
- extend the independent oracle and focused owner over the reset boundary; and
- extend the existing real decode-residency runner with reset versions of its four projections,
  using the same capture rather than another forty model invocations.

The existing `--simulate-residency` command and every schema-2 byte remain unchanged. This is a
runtime cache decision, not a runtime cache: it moves no model bytes, changes no decode CLI, and
makes no latency claim. A later partial-cache capability is eligible only if reset evidence shows a
material byte reduction against streaming and selects its policy and budget before implementation.

The proportional design gate is triggered by a new public CLI verb, schema 3 of an exchanged
document, and one invariant spanning the Align simulator, CLI, independent oracle, smoke owner, and
real-model runner. This document is the authoritative public-contract ledger and closure matrix.

## 2. Public-contract ledger

### 2.1 CLI and compatibility

```text
main --simulate-residency-reset TRACE_LIST MODEL_IR.json BUDGET_BYTES
main --simulate-residency-reset TRACE_LIST MODEL_IR.json BUDGET_BYTES OUT.json
```

Arity, lexical path checks, budget grammar, stdout/file forms, summary text, exit status, and
validation precedence are identical to `--simulate-residency`. Arity is checked before path work;
the optional destination is checked before either input is opened. The new verb calls
`residency_sim.simulate_reset`; the existing verb continues to call `residency_sim.simulate`.

`simulate` remains the schema-2 continuing producer. `simulate_reset` is the schema-3 reset
producer. There is no pooling flag and therefore no ambiguous fifth operand, ambient default, or
way to relabel a continuing result as reset.

### 2.2 Reset replay

Each trace-list line is one session. Immediately before its first demand, all state belonging to
the selected policy is empty: resident membership and bytes, last use, frequency, cumulative router
weight, recent-reuse ring state, prefetch history, and Belady next-use state. Totals and per-layer
statistics accumulate across sessions; `resident_key_high_water` is the maximum resident key count
within any session, not a sum. Token ordinals and source order remain the existing corpus-wide
values in the document, but no ordinal or score crosses a session boundary.

Both `token_major` and `layer_major` use boundaries derived while admitting their own ordered
columns. A reset boundary is an index into the exact replay column, not inferred from a token id or
graph ordinal. Leave-one-trace-out jackknife omits one complete session and retains reset before
every remaining session. The pooled 50-per-mille materiality floor, candidate ordering, budget
sweep, and verdict vocabulary remain unchanged; rule version is 3 because cache lifetime changed.

Belady remains miss-optimal within each session. Its reverse next-use construction is also reset at
every session end, so a use in the next trace cannot keep a victim resident in the previous trace.
Top-k prefetch does not consult frequency from an earlier trace. `compulsory` fetches each distinct
key once per trace rather than once per corpus.

### 2.3 Schema 3

Schema 3 preserves schema 2's field order and values except for:

| Field | Schema-3 reset value |
| --- | --- |
| `schema_version` | `3` |
| `stream.pooling` | `"reset_per_trace"` |
| `stream.session_count` | admitted trace count; present after `pooling` |
| `verdict.rule_version` | `3` |
| policy, per-layer, sweep, and verdict totals | recomputed under reset replay |

On error, schema 3 still names `reset_per_trace`; `session_count` is the number admitted before the
first failure, while the existing failure rule clears successful stream accounting and result
tables. Input schemas, path identity, duplicate-list refusal, byte caps, policy names/order, budget
rows, allocation ownership, and every error code remain unchanged.

The producer owns the returned document string. All replay tables are function-local owned arrays;
no view escapes, no persisted cache is created, and the command has no process, descriptor, thread,
network, or global-state cleanup beyond the existing read/write calls.

### 2.4 Cost and acceptance evidence

| Evidence | Exact owner | Purpose | Diagnostic ceiling |
| --- | --- | --- | --- |
| Simulator and independent oracle | `make residency-sim-smoke` | schema compatibility, both reset orders, state isolation, Belady boundary, jackknife, errors | 5 minutes |
| Real cache decision | `scripts/run-decode-residency-gate` | one capture, continuing and reset results for all four projections | approximately 15 minutes; stop and diagnose if materially longer |
| Publication | `python3 scripts/pre-pr --owner-test r8-reset-cache-decision -- make residency-sim-smoke` | exact-head classifier checks plus the sole changed owner | no `make ci`, installed profile, benchmark, or unrelated platform suite |

The real runner's capture identity, 40 prompts, 16 greedy steps, projections, 25-per-cent requested
budget, and byte-only caveats remain unchanged. It adds four reset simulations after the four
continuing ones and labels pooling on every summary line. Capture remains the dominant cost and is
performed once. This capability makes no elapsed-performance claim, so no benchmark is selected.

## 3. Closure matrix

| Cell | Align simulator / CLI | Independent oracle / owner | Real runner |
| --- | --- | --- | --- |
| Existing continuing success | old verb calls `simulate`; schema 2 and bytes unchanged | existing golden and three-run determinism | existing four rows retained |
| Reset construction | new verb calls `simulate_reset`; schema 3 | exact whole-document equality | same captured documents |
| First session | empty state before demand zero | two traces whose second would otherwise hit | labelled reset rows |
| Later session | clear every policy state at boundary | LRU, LFU, weighted, recent, prefetch, compulsory assertions | forty independent sessions |
| Both orders | boundary columns built with each order | shuffled source/token order case | four projections in token-major verdict |
| Belady | reverse next-use cannot cross trace end | next-trace-only reuse discriminator | ordinary policy row |
| Jackknife | omit one trace, retain other resets | stable and unstable multi-trace cases | forty folds |
| Malformed / early exit | schema 3 truthful prefix; no result table | existing error corpus through new verb | capture failure still stops all simulation |
| Output forms | stdout and file bytes equal | both forms | N/A: runner consumes files only |
| Cleanup | owned arrays released on return | repeated deterministic runs | temporary capture directory removed |

Move-in/out, source nulling, replacement, runtime ABI, generic monomorphization, connection-global
state, and process-global state are N/A: the change is a pure replay over owned decoded documents and
adds no exposed Move container, ABI record, generic public API, process, connection, or mutable
global.

## 4. Completion and decision rule

Completion requires the narrow owner, one real run, one comprehensive review, exact-head
publication preflight, and required GitHub checks. The real result is recorded in this document and
the roadmap once; it is not rerun to search for a preferable answer.

The next runtime capability may implement a partial expert cache only when at least one online
policy at a named budget fetches at least 50 per mille fewer bytes than the `null` streaming row on
the reset `decode_only` arm and the same direction survives all forty leave-one-trace-out folds.
This is an investment rule, not R3's candidate-versus-LRU verdict: LRU itself is eligible when it
materially beats streaming. If no policy clears it, runtime expert caching is deferred and R8 moves
to the next independent hybrid prerequisite.
