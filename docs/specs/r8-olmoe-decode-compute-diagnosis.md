# R8 OLMoE decode-compute diagnosis

Status: complete, 2026-09-05

Roadmap owner: item 62, `R8-OLMOE-DECODE-COMPUTE-DIAGNOSIS`

## 1. Decision owned

Item 61 reduced its measured K/V verification boundary but did not clear the fixed-request
50,000-ppm wall-time gate, so every production intervention was removed. The same shipped item 59
request still assigns a 4,104,846,715-nanosecond median to graph compute, ahead of the remaining
3,609,378,007-nanosecond claim-I/O bucket and well above item 58's 921,450,866-nanosecond
materiality floor.

This capability partitions only that compute total into the decoded-token embedding graph, every
layer's routing/attention phase-A graph, every layer's selected-expert phase-B graph, and the output
head graph. It retains item 58's exact request, model, provider mode, output/token chain, cache
budget, fresh-process isolation, native lifetimes, host fingerprint, and four conditioned
repetitions. The largest median sub-bucket may select a narrower implementation contract only when
it clears the inherited materiality floor. This diagnosis changes no graph, provider, cache,
ownership, token, or output behavior and makes no performance-win claim.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-DECODE-COMPUTE-DIAGNOSIS`; `scripts/run-olmoe-decode-compute-diagnosis`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | the next R8 investment decision after item 61, selecting one directly measured decode-compute sub-bucket |
| Fixed request | item 58's byte-identical task/system/user prompt, OLMoE model, AlignPack, geometry, partial-LRU budget 975,175,680 bytes, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | four sequential fresh-process repetitions; each maximum-2 result is the exact prefix of the following maximum-128 result; zero processes matching both pinned llama-server and model paths before, between, and after each pair |
| Shared counters | add signed 64-bit totals `embed_compute_ns`, `routing_compute_ns`, `expert_compute_ns`, and `decode_head_compute_ns`, plus four corresponding `remaining_decode_*` totals; `empty_outcome` initializes all eight to zero |
| Embedding compute | exact `graph_compute` wall for the one decoded-token embedding graph in each admitted decode pass |
| Routing compute | sum of exact phase-A `graph_compute` walls over all routed layers; this graph contains attention, normalization, router scoring, and argsort and is not attributed more narrowly |
| Expert compute | sum of exact phase-B `graph_compute` walls over all routed layers after selected claims and carry values are staged; it is not a kernel-level attribution |
| Head compute | exact `graph_compute` wall for the one output normalization/logits graph in each admitted decode pass |
| Success semantics | broad totals may include an attempted graph; each `remaining_decode_*` field adds only the exact broad-counter delta of one successfully completed step after the first at the existing commit point; first decode, EOG/maximum exits, and failed partial steps add zero |
| Exact accounting | existing `remaining_decode_compute_ns` equals embedding plus routing plus expert plus head compute for every complete helper record; all five values are nonnegative, maximum 2 requires all zero, and maximum 128 requires all positive |
| Existing consumers | graph construction/order, compute calls, provider response, existing helper schemas, output, cache behavior, and native lifetime are byte- and meaning-unchanged because no production renderer exposes the new scalar counters |
| Qualification helper | new `olmoe_decode_compute_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; maximum is only 2 or 128; preserve item 60's exact inherited helper record and add one exact `decode_compute` object |
| Helper detail | `decode_compute` has exact keys `total_ns`, `embedding_ns`, `routing_ns`, `expert_ns`, and `head_ns` and satisfies the exact equation above |
| Fixed baseline | item 58 post-review full-helper walls `[17827657250,17850131083,19007903542,19211017875]`, integer median 18,429,017,312 ns; item 59's published compute median is 4,104,846,715 ns; both are immutable and are not recomputed from item 62 samples |
| Materiality floor | 50,000 ppm of the fixed full-helper baseline, rounded up: 921,450,866 ns per full request |
| Opportunity/decision | take four-sample medians of `EMBEDDING`, `ROUTING_PHASE_A`, `EXPERT_PHASE_B`, and `OUTPUT_HEAD`; choose the largest with ties in that execution order; below floor yields `NO_MATERIAL_BUCKET`, otherwise `MEASURED_BUCKET_ELIGIBLE`. A winner authorizes only an implementation ledger with its own unchanged full-request baseline and 50,000-ppm shipping gate |
| Result | one exact-key schema-1 `R8_OLMOE_DECODE_COMPUTE_DIAGNOSIS` JSON document on stdout and one concise stderr summary; no complete document on failure |
| Inputs/identity | independently pin item 60's predecessor runner and helper chain, item 58/59 workload and baseline values, new helper/source chain, model, pack, geometry, server, Align revision/compiler, ggml libraries and consumed headers, C compiler/version, task, prompt, exact token chain, built helper/shim, clean align-llm head, and item 59's exact baseline-host fingerprint |
| Validation order | argument/prerequisite precedence; scrubbed environment/linker search; fixed host, clean head, process absence, imported and external identities including consumed headers; exact-source build; four conditioned records; schema/accounting/output/lifetime/repeatability; aggregate/decision; final identities/head; cleanup-inclusive ceiling; publication |
| Failure | nonzero and no complete document for invalid arguments, identity/host/source/process drift, malformed or overlapping clocks, failed accounting, output/lifetime drift, child failure, source mutation, cleanup failure, or ceiling excess; missing prerequisites keep the one declared N/A path |
| Ownership/allocation | counters are scalars in the invocation-owned outcome; no native owner is added; helper/runner/temp state is invocation-local and removed by its current owner |
| Persisted/cache identity | N/A: no production schema, cache, model, patch, or result file changes; qualification stdout is not persisted by the runner |
| Cost ceiling | one monotonic 8-minute ceiling covers helper/shim build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; each child retains a narrower bound |
| Acceptance evidence | author consistency pass; `make fmt`; pinned helper build; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation; focused inherited self-test; one complete real diagnosis; `git diff --check`; one comprehensive review; exact-head `scripts/pre-pr --owner-test R8-OLMOE-DECODE-COMPUTE-DIAGNOSIS -- scripts/run-olmoe-decode-compute-diagnosis --self-test` |

The capability makes one fixed-request, one-model, one-host attribution. Cross-host, GPU,
throughput, arbitrary-task, cache-policy, persistent-state, public-provider, kernel, and speedup
claims are N/A. The new helper and result are qualification-only JSON text; no production renderer
exposes the new counters.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Shared outcome | eight zeroed `i64` scalars | broad timers accumulate the four disjoint compute classes | no new error; invalid delta cannot publish | failed/first steps add no remaining total | no owner | zero/positive source assertions, compile owner, real accounting |
| Embedding/head graphs | existing end-graph result supplies its exact compute wall | classify once after the corresponding call | existing compute failure and convergence remain unchanged | failed step is not committed | existing graph teardown once | old smoke/lifetime owners plus helper equation |
| Routed layer | existing layer result supplies exact A and B compute walls | classify A as routing and B as expert once per layer | existing first error and ordered convergence remain unchanged | failed step is not committed | existing graph teardown once | old routed owners plus helper equation |
| Step commit | snapshot four broad counters immediately before `decode_pass` | successful remaining step adds exact deltas | negative or unequal partition rejects helper | first decode and partial step add zero | locals die per step | maximum-2 zero, full positive/equality, malformed mutants |
| Helper | item 60 production preparation plus compute detail | one exact record | bad arguments/output/accounting exits before print | N/A | invocation drops state | pinned build and schema self-test |
| Repetition | fixed host/process absence; fresh short/full children | exact prefix/output four times | drift aborts without result | no partial sample/result | inherited signal/deadline cleanup | twelve absence checks and repeatability |
| Aggregate | four exact records and immutable baseline/floor | medians and deterministic selection | boolean/missing/duplicate/arithmetic/baseline drift rejects | no partial aggregate | N/A | both decision classes, tie, below/at-floor vectors |
| Identity | pin imports, sources, headers, tools, externals, and head | final values unchanged | any nested value or digest drift fails | missing prerequisite emits N/A | restore generated root binary | imported/nested/header mutants and real recheck |
| Signal/deadline | install handlers before real work | N/A | interruption/timeout exits nonzero | no complete JSON | stop child and restore temp/build state | inherited forced timeout/restoration tests |

Generic monomorphization, move/source-nulling, concurrent calls, external server ownership, and
persisted migration are N/A. The shared record remains invocation-owned, decode is synchronous,
and timing adds no borrow, allocation, or native lifetime.

## 4. Implementation and verification map

1. Add the eight shared scalar counters and classify the four already-measured graph compute calls;
   snapshot them at the existing successful-step boundary without moving an operation.
2. Extend the qualification helper internally and add one thin executable that exposes only the
   exact compute partition while preserving every predecessor field.
3. Add a bounded runner that imports item 60's environment/identity/cleanup primitives,
   independently pins its baseline and complete source chain, and owns the new schema, equations,
   medians, and decision.
4. Run narrow owners and one real four-repeat diagnosis; record the selected successor here, in the
   roadmap, and in `HANDOFF.md`.
5. Complete one comprehensive review, consolidate valid findings, rerun affected owners and
   exact-head preflight, publish, merge, and continue to the selected capability.

No `make ci`, installed platform profile, coding portfolio, 40-prompt corpus, stress suite, cache
replay, or unrelated benchmark is selected. Producer counters, exact helper, and validator form one
consumer-complete diagnostic capability.

## 5. Author consistency pass

The ledger and matrix agree that the four clocks partition only existing `graph_compute` walls,
that phase A is not relabelled as routing-only arithmetic, that only successfully completed steps
after the first reach the remaining-decode totals, and that a measured bucket must clear the
921,450,866-nanosecond floor before implementation design is eligible. Every counter has one owner
and one qualification field; no performance claim or graph change is introduced before the result.

## 6. Recorded result

The complete run at clean implementation head `4de73d64765fc31f35f2c08ca00367d327b00705`
finished in 121.268 seconds. All four maximum-2 conditioning records were exact prefixes of their
maximum-128 records. Every full request reproduced the fixed 87-token chain and 86-token output
digest, balanced 2,958 ggml buffers, 6,090 contexts, one backend, 2,958 allocators, and one resident
wrap, and recorded zero matching llama.cpp model processes at all twelve required boundaries.

Full-helper walls were `[18059864416,18927732709,20639199375,19605385750]` ns, for a
19,266,559,229-ns median. Decode-compute totals were
`[4032538022,4200052735,4232013000,4234889692]` ns, for a 4,216,032,867-ns median and these
sub-bucket medians:

| Bucket | Median (ns) |
| --- | ---: |
| `EMBEDDING` | 997,788 |
| `ROUTING_PHASE_A` | 2,939,392,017 |
| `EXPERT_PHASE_B` | 1,114,674,041 |
| `OUTPUT_HEAD` | 151,386,183 |

Every sample's four sub-buckets sum exactly to its decode-compute total. `ROUTING_PHASE_A` is the
deterministic winner at 697,193 ppm of the compute total and exceeds the inherited
921,450,866-ns floor by 2,017,941,151 ns, so the decision is `MEASURED_BUCKET_ELIGIBLE`. Item 63
owns a bounded phase-A implementation contract. Its immutable full-request baseline is this run's
four full-helper walls and 19,266,559,229-ns median; its 50,000-ppm floor is 963,327,962 ns and its
candidate ceiling is 18,303,231,267 ns. The intervention must preserve the fixed output, cache,
isolation, and lifetime evidence and is removed if that complete fixed-request gate is not met.

This result attributes phase A only as the existing attention/normalization/router/argsort graph.
It does not identify an individual op or kernel, predict speedup, or establish the R8 gate.
