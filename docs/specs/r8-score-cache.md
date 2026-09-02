# R8-SCORE-BASED-CACHE

Status: implementation contract, 2026-09-02

## 1. Decision and boundary

R3 measured 453--476 per mille of decode-stream headroom that none of its existing online
policies captures. Its named prerequisite for a score-based policy is the selected router weight,
which the current `R2_ACTIVATION_TRACE` does not exchange. This capability closes that producer to
consumer boundary:

- the managed `llama-eval-callback` instrument prints every axis of both `ffn_moe_topk-N` and
  `ffn_moe_weights-N`;
- `main --expert-trace` emits `R2_ACTIVATION_TRACE` schema 2 with one exact four-decimal router
  weight on every selection;
- `main --simulate-residency` consumes schema 2 and adds one fixed `router_weight_lfu` policy; and
- the independent oracle and narrow owners prove the grammar, pairing, replay, and fail-closed
  boundaries without a model, network, broad aggregate, or timing benchmark.

The policy is an evaluation capability, not yet a runtime cache. It does not choose CPU versus GPU,
prefetch a block, convert bytes to latency, change the runtime provider, or claim that R8's latency
gate is met. Those require the later R5 transfer/compute measurements and a runtime implementation.
The `.align-revision` move from `27770420555d19b98eced133369c168e9c6d4a2f` to
`b6f95a261e1434d705d7de006484ffa66b1542f0` is this consumer branch's internal prerequisite
checkpoint; it changes no Align-request lifecycle.

The proportional design gate is triggered by two exchanged schema changes, the managed external
instrument patch, and the invariant spanning the producer, simulator, oracle, fixtures, and
qualification wrappers. This document is the authoritative public-contract ledger for the
capability. The existing R2A, R2c, and R3 plans retain their historical version-1 contracts and are
updated only where their deferred prerequisite becomes this shipped version-2 boundary.

## 2. Public-contract ledger

### 2.1 Instrument identity and output

| Field | Contract |
| --- | --- |
| Upstream | Existing `.llama-revision` `bb4caa7540188872173c44d161602d9271386413`; no source revision change |
| Patch | Existing `patches/llama.cpp/r2c-decode-instrument.patch`, still limited to `common/debug.cpp` and `examples/eval-callback/eval-callback.cpp` |
| Print families | Exact `ffn_moe_topk` and `ffn_moe_weights` names, or either followed by `-`; all axes print in full. Every other tensor retains the upstream first/last-three rule |
| Decode behavior | Unchanged R2c `-n N` behavior |
| Cache identity | Existing generation `r2c-v2` plus the unchanged upstream SHA plus the new full patch SHA-256. The patch digest already separates the new entry, so no layout generation changes |
| Owner | `scripts/llama-eval-callback-toolchain`, `scripts/run-r2c-instrument-smoke`, and focused `scripts/run-r2c-instrument-qualification` |

The patch digest and byte count are filled into the R2c ledger, tool, and smoke from the final patch
bytes before implementation verification. A digest change with stale constants fails before cache
resolution. The compiled qualification is meaningful because this capability changes actual
instrument output; it is the only external build selected by the change.

### 2.2 `R2_ACTIVATION_TRACE`, schema 2

The CLI arity, status model, field order outside `selections[]`, graph segmentation, locality
aggregates, and summary block remain R2A's contract. The top-level `schema_version` is now `2`.
Every successful MoE document carries this exact selection row in observation order:

```json
{"graph":0,"layer":3,"token":0,"slot":0,"expert":12,
 "router_weight_ten_thousandths":1424}
```

| Field | Type and contract |
| --- | --- |
| `router_weight_ten_thousandths` | Integer in `[0, 10000]`, parsed exactly from the selected `ffn_moe_weights-N` element printed by `%12.4f`; `0.1424` becomes `1424`. It is the printed selected gating weight, not a reconstructed probability and not sufficient to reproduce the model's gating arithmetic |

Dense documents remain successful with `selections: []`. A MoE graph must pair each
selection-producing `ffn_moe_topk-N` block with exactly one later `ffn_moe_weights-N` block at the
same layer. The weight shape is exactly `{1, n_expert_used, topk_tokens, 1}`. Its axis 1 is the
top-k slot and axis 2 is the top-k token; the accepted printed indices must equal the corresponding
top-k indices. Compact historical blocks are accepted when both blocks carry the same first/last
three index set. The patched full form carries every slot and token. A token-reduced tail pair is
grammar- and shape-validated but contributes no selection or weight because its original token
identity is unavailable.

The producer allocates one additional `i64` column bounded by `MAX_SELECTIONS` (8 MiB at the
existing maximum). It does not retain the full probability tensor. Pairing is performed against the
already-recorded selection run for that graph and layer; no quadratic lookup is permitted.

Two new fail-closed codes join R2A's ordered validation after value-block structure and before the
selection table is rendered:

| Code | Condition | Detail |
| --- | --- | --- |
| `R2_ROUTER_WEIGHT_VALUE` | A weight is not the exact fixed-decimal form, is negative, has other than four fractional digits, or is greater than `1.0000` | `ffn_moe_weights-N` |
| `R2_ROUTER_WEIGHT_MISMATCH` | A weight block precedes its top-k block, is duplicated or missing, has a wrong shape, printed index set, count, graph, or layer, or a graph closes with an unmatched top-k block | offending family-layer name; the unmatched top-k name for a missing block |

When several defects exist, the first line-order grammar/value/duplicate defect wins. Missing
weights are checked when the next graph begins and at EOF. Existing earlier R2 validation steps
retain precedence. Error documents use schema 2 and preserve only the truthful prefix as before.

### 2.3 `R3_RESIDENCY_SIM`, schema 2

The CLI and operands remain:

```text
main --simulate-residency TRACE_LIST MODEL_IR.json BUDGET_BYTES
main --simulate-residency TRACE_LIST MODEL_IR.json BUDGET_BYTES OUT.json
```

Every admitted trace must be `R2_ACTIVATION_TRACE` schema 2 and every selection must contain the
bounded integer weight above. Schema 1 is refused as `R3_TRACE_SCHEMA`; there is no synthesized
default score. A decoded integer outside `[0, 10000]` is refused as `R3_ROUTER_WEIGHT_RANGE` with
the one-based trace-list ordinal as detail, after trace shape validation and before expert/block
range validation. A missing or non-integer member is a structural `R3_TRACE_DECODE` failure. The
simulator output has `schema_version: 2`, reports
`inputs.trace_schema_version: 2`, and advances `verdict.rule_version` to `2` because the fixed
candidate set changes from ten to eleven policies.

`router_weight_lfu` is inserted after `lfu` and before the three `recent_reuse` rows. It is a
candidate, participates in the budget sweep and jackknife, and uses this fixed online rule:

1. Start every expert's cumulative router score at zero.
2. After each demand is serviced, add that selection's `router_weight_ten_thousandths` to the
   demanded expert's score. Scores survive eviction and re-admission, exactly as R3's LFU counts do.
3. On a miss requiring eviction, evict the resident expert with the lowest cumulative score before
   this demand; break ties by least recent use, then lowest packed `(layer, expert)` key.
4. The policy never prefetches and charges the same demanded expert bytes as every other
   demand-driven policy.

The maximum score is `MAX_DEMANDS * 10000 = 2,621,440,000`, within `i64`. The two replay orders
carry a weight column aligned one-for-one with their keys. Token-major sorting uses a second packed
array `(observation_order << 14) | weight`; the existing unique observation order makes its
independent sort align exactly without a lookup. Layer-major uses the source-order weight column.
Any count or order disagreement is an internal construction failure owned by the narrow smoke,
not a recoverable document condition.

At `MAX_DEMANDS`, each weight column is 2 MiB. The two pooled replay-order columns retain 4 MiB;
while one trace is transferred into them, its sorted token-major and source-order columns add at
most another 4 MiB, for an 8 MiB incremental peak owned by `simulate`. The sweep grows from at most
`2 * 9 * 10 = 180` to `2 * 9 * 11 = 198` ordinary replays; the existing jackknife algorithm and
`R3_SIMULATION_COST` per-replay guard are unchanged. The focused owner measured 3.19 seconds on the
development host, below its predeclared five-minute diagnostic ceiling; no performance claim is
made from that observation.

All existing result-row fields remain unchanged. The policy's value is visible through its ordinary
hits, misses, `bytes_fetched`, per-layer rows, sweep result, and verdict participation; no bespoke
score field is added to the output.

### 2.4 Ownership, identity, and compatibility

| Surface | Producer | Consumer | Identity / compatibility |
| --- | --- | --- | --- |
| Patched transcript | managed llama.cpp instrument | `src/expert_trace.align` | upstream SHA + patch SHA; compact historical print form or full patched form |
| `R2_ACTIVATION_TRACE` v2 | `src/expert_trace.align` | `src/residency_sim.align`, projection and qualification scripts | structural JSON schema version 2; schema 1 is not silently upgraded |
| `R3_RESIDENCY_SIM` v2 | `src/residency_sim.align` | CLI callers and golden/oracle owners | structural JSON schema version 2; policy order and verdict rule version 2 are normative |
| Align toolchain | `.align-revision` + `scripts/align-toolchain` | all Align modules | exact `b6f95a261e1434d705d7de006484ffa66b1542f0` managed compiler/runtime |

No artifact is persisted by either CLI unless the caller supplies its existing output operand.
Builders own returned document strings; borrowed arrays never escape their owning scan/simulation
record. Normal and error cleanup are unchanged because the feature adds no process, descriptor,
thread, socket, or in-repository cache.

### 2.5 Acceptance evidence and cost ceiling

| Evidence | Exact owner | Purpose | Ceiling |
| --- | --- | --- | --- |
| Producer grammar/schema | `make expert-trace-smoke` | compact/full weights, fixed-decimal parsing, pairing, errors, schema/order | 3 minutes on the development host |
| Simulator and independent oracle | `make residency-sim-smoke` | all eleven policies at every swept budget/order, weighted-LFU discriminating cases, schema refusal | 5 minutes on the development host |
| Managed patch boundary | `scripts/run-r2c-instrument-smoke` | patch identity/scope, exact two-family print predicate, cache/refusal behavior | 2 minutes |
| Compiled instrument | `scripts/run-r2c-instrument-qualification` with its documented model inputs | new patch applies, builds, prints full paired axes, and parses to schema 2 | focused only; approximately 15 minutes, stop and diagnose if materially longer |
| Publication | `python3 scripts/pre-pr --owner-test r8-score-cache -- /bin/sh -c 'make expert-trace-smoke residency-sim-smoke && scripts/run-r2c-instrument-smoke'` | classifier-selected exact-head checks plus the three local owners | no `make ci`, installed profile, benchmark, or unrelated platform suite |

The compiled qualification is N/A only when its documented model input is unavailable, using its
existing exact N/A result. Hosted CI owns the ordinary source graph. This capability makes no
latency, throughput, or time-to-passing-patch claim, so no benchmark is selected. A later runtime
policy must establish its own hardware baseline and R8 gate evidence.

## 3. Cross-cutting closure matrix

| Cell | Instrument | Expert trace | Residency simulator / oracle | Regression |
| --- | --- | --- | --- | --- |
| Construction | exact two-family predicate; digest-bound cache entry | allocate bounded weight column with selection columns | construct aligned weight streams and eleven-policy tables | `patch-semantics`, basic schema/oracle cases |
| Success, compact | upstream first/last-three pair | exact compact slot/token index pairing | consume every emitted weighted selection | compact-weight fixture and oracle |
| Success, full | both router families full, unrelated tensors compact | every slot/token gets its paired weight | weighted-LFU differs from LFU on scripted stream | full-weight and `score-discriminates-lfu` |
| Dense | no router family required | schema 2, empty selections | trace admitted only when stream remains valid under existing rules | dense producer cases |
| Token-reduced tail | pair retains reduced shape | validate and omit both ids and weights | omitted accounting unchanged | reduced-tail pair |
| Malformed value | N/A | first bad fixed decimal is `R2_ROUTER_WEIGHT_VALUE` | missing/type is `R3_TRACE_DECODE`; range is `R3_ROUTER_WEIGHT_RANGE` | weight value mutations |
| Missing/duplicate/order/shape | N/A | `R2_ROUTER_WEIGHT_MISMATCH` at line order or graph close | no partial successful stream | pairing mutations |
| Unsupported old schema | N/A | always emits schema 2 | schema 1 is `R3_TRACE_SCHEMA` | future/old schema cases |
| Early exit / cleanup | partial cache entry never admitted | truthful error prefix, owned arrays released | truthful error document, owned arrays released | existing CLI/error owners plus new malformed cases |
| Sorting / loop joins | N/A | one linear pair cursor per block | independently sorted order/weight words remain one-to-one; replay terminates on demand count | shuffled selections, both replay orders, oracle equality |
| Publication / integration | focused compiled patch only | narrow owner | narrow owner | classifier preflight; hosted required check after publication |

Move-in/out, source nulling, replacement, process-global state, concurrent connection state,
generic monomorphization, and runtime ABI serialization are N/A: the changed surfaces are owned
documents and pure array replays, with no exposed Move container, mutable global, connection,
generic public API, or ABI record.

## 4. Final mapping and completion

The stable implementation candidate maps the ledger and closure matrix as follows:

| Contract / closure cells | Final diff | Passing evidence |
| --- | --- | --- |
| Align prerequisite identity | `.align-revision`, toolchain/request/roadmap handoff updates | `scripts/align-toolchain verify` (0.127 s); `make check` (40 units, 2m00.91s) |
| Instrument identity, full pair, cache, refusal, compiled behavior | `patches/llama.cpp/r2c-decode-instrument.patch`, toolchain, smoke, qualification, R2c contract | `scripts/run-r2c-instrument-smoke` (55 groups, 2.63 s); uncached compiled qualification (4m52.38s); cached real OLMoE qualification (3 graphs, 384 weighted selections, 5.09 s) |
| Producer construction, compact/full/dense/reduced/malformed/error cleanup | `src/expert_trace.align`, fixture generator, smoke and parity owners | `scripts/run-expert-trace-smoke` (116 fixtures, 19 codes, 13.15 s); real OLMoE `scripts/run-expert-trace-parity` (488 weighted selections, 24.03 s) |
| Stream construction, old-schema refusal, weighted eviction, both orders, verdict | `src/residency_sim.align`, independent oracle, golden, simulator/gate runners | `scripts/run-residency-sim-smoke` (31 traces, every policy/budget/order, 3.19 s), including `score-discriminates-lfu`, weight decode/range, duplicate-order, and schema-1 refusal cases |
| Current public documentation and compatibility | this contract, R2A/R2c/R3 supersession notes, `docs/align-development.md` | `git diff --check`; shell syntax, Python module syntax, and embedded-Python AST checks |

Completion requires:

1. the exact Align pin materializes and `make check` passes once for the coherent adoption;
2. all three narrow local owners pass within their diagnostic ceilings;
3. the compiled instrument qualification passes or records its exact input-owned N/A;
4. one comprehensive review covers the stable full diff and every finding has a disposition; and
5. exact-head publication preflight and required GitHub checks pass before merge.

The capability is consumer-complete when a real schema-2 trace can flow from the managed instrument
through `--expert-trace` into the eleven-policy simulator. It does not close R8 itself; the next
consumer is the runtime cache decision informed by this measurement.
