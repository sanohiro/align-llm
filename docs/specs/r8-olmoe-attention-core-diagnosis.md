# R8 OLMoE attention core diagnosis

Status: implemented and measured; review/publication pending, 2026-09-05

Roadmap owner: item 73, `R8-OLMOE-ATTENTION-CORE-DIAGNOSIS`

## Decision and contract

Item 72's repaired measurement selected attention core (rows 14–27) at a 2,525,763,020-ns
median, above the immutable 871,174,011-ns floor. This capability separates that class into
six direct graph-compute walls so a successor can select a concrete operation boundary.
It makes no speedup claim. Item 63's rejected live-width intervention remains forbidden.

| Surface | Exact contract |
| --- | --- |
| Owner and CLI | `scripts/run-olmoe-attention-core-diagnosis`; no arguments runs the opt-in fixed-host qualification; `--self-test` runs the model-free owner |
| Consumer | the next R8 implementation ledger for the selected material operation sequence; R8 remains open |
| Align API | `moe_decode_step.generate_resident_sampled_attention_core_diagnosis(pack_path: str, geometry_path: str, expected_geometry: str, source_identity: alignpack.SourceIdentity, borrow prompt_token_ids: array<i64>, borrow eog_token_ids: array<i64>, max_tokens: i64, cache_budget_bytes: i64, seed: i64) -> GenerationParts`; identical input validation/ownership to the item-72 sibling; owned result contains outcome and token JSON, with failure in outcome code/detail and empty token array |
| Fixed inputs | inherit item 72's exact model, pack, geometry, task/prompt, seed 5, temperature 300,000 micros, maximum 128, EOG rule, 975,175,680-byte cache budget, 87-id chain, 86 completion tokens and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Execution | new qualification-only mode constructs nine borrowed graph slices over the already-built and allocated full-width phase-A source graph: projection 0–13; six core slices below; output/residual 28–31; router 32–36. All slices exist before any compute. Source tensor operations, operands, marks and allocator remain unchanged |
| Core selection order/membership | `QK_PREPARATION` rows 14–18 (Q/K permutations, K contiguous conversion, concatenation, padding); `SCORE_MATMUL` row 19; `MASKED_SOFTMAX` row 20; `VALUE_PREPARATION` rows 21–24 (V permutation, contiguous conversion, concatenation, padding); `VALUE_MATMUL` row 25; `OUTPUT_PACKING` rows 26–27 (permutation and contiguous conversion) |
| Compute order | projection, VALUE_PREPARATION, QK_PREPARATION, SCORE_MATMUL, MASKED_SOFTMAX, VALUE_MATMUL, OUTPUT_PACKING, output/residual, router. V preparation precedes the score branch to retain the source core traversal and allocator lifetimes; selection tie order remains table order |
| Selection ABI | reuse `ggml_ffi.graph_select_slot_range`; exact populated table-owned slots occur once in the source graph and retain its internal topological order. Core node counts are exactly 5, 1, 1, 4, 1, 2; all nine slices total the source count. Output/residual has 4 nodes only on the last layer, otherwise 2 |
| Ownership/allocation | one diagnostic context owns all nine graph structures and is freed before source graph/tensor contexts, allocator and buffers. No slice owns tensors or allocators. Allocate sufficient diagnostic context bytes for nine graph structures; normal/item-71/item-72 allocation and execution remain unchanged. Added outcome counters are zero-initialized scalars |
| Compute failure | `R5_GGML_INIT` / `phase_a_operation_context` for context construction refusal or `attention_core_partition` for malformed/missing selections or wrong counts; `R5_COMPUTE` with `status_qk_preparation`, `status_score_matmul`, `status_masked_softmax`, `status_value_preparation`, `status_value_matmul`, or `status_output_packing` for the first failing core compute; skip later computes and never commit a failed step |
| Direct clocks | `attention_qk_preparation_ns`, `attention_score_matmul_ns`, `attention_masked_softmax_ns`, `attention_value_preparation_ns`, `attention_value_matmul_ns`, `attention_output_packing_ns`; their sum is `attention_core_ns`. Existing projection/core/output sum and attention/router sum remain exact |
| Commit boundary | matching `remaining_decode_` counters accumulate only successful steps after the first decode step. Maximum 2 has all-zero core detail; maximum 128 has all-positive clocks |
| Helper | `olmoe_attention_core_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; preserve every item-72 record field and add `attention_core_operations` with exact keys `total_ns`, `qk_preparation_ns`, `score_matmul_ns`, `masked_softmax_ns`, `value_preparation_ns`, `value_matmul_ns`, `output_packing_ns` |
| Accounting | all detail values are nonnegative signed 64-bit integers (booleans rejected); six children sum to `total_ns`, which equals `attention_operations.attention_core_ns`; inherited parent equations remain enforced |
| Shipped-state evidence | preserve exact output and cache counts (11,940 requests, 7,325 hits, 4,615 misses, 4,376 evictions, 17,656,872,960 fetched bytes, zero cache-to-claim copies), repeatability and balanced native lifetimes; require balanced context/buffer/backend/allocator counts in each produced short and full record |
| Repetition/isolation | four sequential fresh-process short/full pairs, short maximum 2 an exact full-output prefix; zero matching pinned model/server processes before, between and after each pair |
| Immutable baseline/floor | item 68 full-helper samples `[17714825083,16684315166,17132135334,21189618042]` ns, median 17,423,480,208 ns; ceiling-rounded 50,000-ppm floor 871,174,011 ns. Item 72's diagnostic medians do not reset the baseline |
| Aggregate/decision | four-sample integer medians in the six-class order above; largest median wins, earlier class breaks ties; share is winner median / core-parent median in ppm. Below floor: `NO_MATERIAL_CORE_CLASS`; otherwise: `MEASURED_CORE_SEAM_ELIGIBLE`, with the selected class naming only its exact row sequence |
| Result schema | exact-key schema-1 `R8_OLMOE_ATTENTION_CORE_DIAGNOSIS` JSON on stdout, concise stderr summary. Reuse item 72's top-level keys; boundary describes the six exact ranges and outer ranges; aggregate uses `core_values_ns` / `core_median_ns` in place of its parent's attention values/median |
| Source/external identity | independently pin every transitively consumed runner/helper/source plus new helper, all changed Align sources and regression owner, shim/stub/build scripts, fixed model/pack/geometry/server, compiler/revision, ggml libraries and consumed headers, C compiler/version, task/prompt/token chain, built helper/shim, clean head and inherited host fingerprint |
| Validation order | arguments/prerequisites; inherited constants/source identities; scrubbed environment/linker inputs; fixed host, clean head, process absence and external identities; exact-source build; four pairs; record schema/output/cache/lifetimes/accounting/repeatability; aggregate; final head/source/external rechecks; cleanup-inclusive ceiling; publication |
| Refusal/early exit | nonzero with no complete document for malformed clocks/schema/ranges/counts, compute failure, source/host/output/cache/lifetime/isolation drift, child failure, mutation, cleanup failure or ceiling excess. Missing prerequisite emits exactly one declared N/A line |
| Cost ceiling | one monotonic 8-minute ceiling includes helper/shim build, eight requests, validation, final identities and cleanup; narrower child bounds inherited |
| Persisted/cache identity | N/A: no persisted production format, cache policy, provider grammar or model format change; runner stdout is not persisted by the runner |
| Acceptance | `make fmt`; helper type-check/build; `scripts/test-olmoe-attention-core`; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation and focused self-test; clean-head fixed-host four-repeat qualification; `git diff --check`; comprehensive review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-ATTENTION-CORE-DIAGNOSIS -- scripts/run-olmoe-attention-core-diagnosis --self-test` |

These are operation-sequence walls including backend dispatch, not kernel-only timings. Nine
slices add eight dispatches per routed layer versus normal execution and five versus item 72.
Any selected implementation must clear a separately precommitted full-request shipping gate.
Cross-host/GPU/throughput claims, persistent inference, public provider changes and aggregate-only
audits are N/A. Existing shipped Align FFI, raw handles and scalar timing suffice; no new Align
capability is needed.

## Closure matrix and implementation map

| Owner/path | Construction and success | Failure/malformed and early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- |
| `moe_decode_step` graph selection | nine ranges selected by slot membership; exact counts and dependencies | absent slice or wrong count fails before computing | diagnostic context freed first | `scripts/test-olmoe-attention-core` compares exact source node pointers across all six core slices on the allocated tiny model; real fixed output |
| `moe_decode_step` compute | declared compute order; six direct clocks close to parent | first failing class labels status and skips all later work | existing common teardown | `scripts/test-olmoe-attention-core` covers exact compute order, all six failure labels, late failure and selection refusal, with no later compute and balanced lifetimes; real output/lifetime qualification |
| Existing modes | normal source graph; item 71 two slices; item 72 four slices | retain existing errors and requested-step behavior | unchanged owners | runtime-provider smoke; existing layer smoke; source-path inspection |
| `moe_model_forward` / step counters | zero initialization; successful-step-after-first commit | failed steps contribute no remaining-decode counters | scalars only | helper zero short/full positive equations, failed-step inspection |
| Shared helper and new entry | only new helper enables core mode; inherited schemas unchanged | bad arguments/accounting reject before printing | invocation-owned state | helper type-check/build; runtime-provider smoke; full real records |
| Python record/result validators | exact schema, integer range, all parent equations, deterministic median/ties/floor | boolean/negative/overflow/missing/extra keys, child/parent drift, wrong boundary rejected | no complete result on error | focused self-test malformed vectors, six at-floor decisions and below-floor/tie cases |
| Runner identity/repetition | pin complete consumed chain and fixed external identities; four reproducible pairs | drift/mutation/wrong sample count aborts without result | inherited signal/deadline/process cleanup and root binary restoration | focused source mutation and inherited validators; twelve real isolation checks |
| Publication | final unchanged head/identities, exact aggregate | interrupted/late/cleanup failure cannot publish complete JSON | cleanup before elapsed check/publication | focused cleanup-ceiling regression and real completed qualification |

Generic monomorphization, asynchronous escape, move/source-nulling, shared connection state and
concurrent production calls are N/A: synchronous graph slices borrow only existing tensors within
one layer frame. The same source graph remains the allocator's ownership domain; core execution preserves its
original V-before-score traversal so unmarked score/softmax temporaries retain valid lifetimes.

The stub graph pool grows from eight to sixteen entries to hold the source and nine diagnostic
graphs. The focused native test remains outside routine aggregates; `layer-forward-smoke` owns
the existing stub and selector regressions. Its test wrapper includes the unchanged checked-in
stub source and injects failure only in the test library, with no product flag or new FFI ABI.

## Author consistency pass

The six nonoverlapping ranges cover every core row exactly once and each dependency comes from
an earlier compute class or the projection prefix. Singleton score, softmax and value classes expose the
individual matrix/normalization operations; preparation and packing expose only their stated short
sequences. Every class shares the inherited floor and no result authorizes the rejected width
change. The ledger, closure matrix and helper account for the same six clocks and retain all parent
equations. Final evidence will map these cells to the settled diff before review.

## Recorded qualification and closure

Clean implementation head `e18ac5dab88b06b02e38d1504800eb5e50068e0d` completed the fixed-host
four-repeat owner in 91,512,119,125 ns. Full-helper walls were
`[14408481583,15168348459,15659437208,15173171666]` ns, median 15,170,760,062 ns.
Core-parent walls were `[2119821592,2273103164,2374015742,2322065625]` ns, median
2,297,584,394 ns. These diagnostic walls are not a new shipping baseline.

| Class | Four values (ns) | Median (ns) |
| --- | --- | ---: |
| `QK_PREPARATION` | `[926368426,992095052,1038372156,1008426435]` | 1,000,260,743 |
| `SCORE_MATMUL` | `[111255065,120691127,126338358,127724062]` | 123,514,742 |
| `MASKED_SOFTMAX` | `[24557247,25723707,27843173,27346505]` | 26,535,106 |
| `VALUE_PREPARATION` | `[914435133,980679032,1020577467,996733657]` | 988,706,344 |
| `VALUE_MATMUL` | `[132092364,142088932,148582726,149730227]` | 145,335,829 |
| `OUTPUT_PACKING` | `[11113357,11825314,12301862,12104739]` | 11,965,026 |

`QK_PREPARATION` wins at 1,000,260,743 ns, 435,353 ppm of the core-parent median and
129,086,732 ns above the inherited 871,174,011-ns floor. Decision:
`MEASURED_CORE_SEAM_ELIGIBLE / QK_PREPARATION`. The selected successor owns only rows 14–18's
Q/K permutations, K contiguous conversion, K concatenation and K padding. Value preparation also
exceeds the floor but is not the selected winner. No result reopens item 63's live-width candidate.

Every full request reproduced the fixed token chain/output hash and exact cache counts; all twelve
process-absence checks passed, native lifetimes balanced, conditioning detail was zero, full detail
was positive, and every child/parent equation closed. The six-class compute schedule preserved the
source core traversal. The exact source mutation, schema, integer-boundary, inherited evidence,
selection and cleanup-ceiling self-tests passed.

The closure matrix maps to `scripts/test-olmoe-attention-core` for allocated tiny-model execution,
exact core node-pointer order, unchanged normal/item-72 output, six compute failures, a failure
after one successful decode step, selection refusal, no later compute, zero conditioning and
lifetime balance. The public helper type-check passed 17 units; `gmake fmt`, Python compilation,
`gmake layer-forward-smoke` (75.238 seconds), `gmake runtime-provider-smoke` (sampler vectors and
61 CLI assertions), the focused runner self-test and `git diff --check` passed. GNU Make is used
on this macOS host because the system Make cannot parse the repository Makefile. No matrix cell
is deferred. Review and exact-head publication preflight remain pending.
