# R8 OLMoE attention core diagnosis

Status: implementation active, 2026-09-05

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
| Fixed inputs | inherit item 72's exact model, pack, geometry, task/prompt, seed 5, temperature 300,000 micros, maximum 128, EOG rule, 975,175,680-byte cache budget, 87-id chain, 86 completion tokens and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Execution | new qualification-only mode constructs nine borrowed graph slices over the already-built and allocated full-width phase-A source graph: projection 0–13; six core slices below; output/residual 28–31; router 32–36. All slices exist before any compute. Source tensor operations, operands, marks and allocator remain unchanged |
| Core order/membership | `QK_PREPARATION` rows 14–18 (Q/K permutations, K contiguous conversion, concatenation, padding); `SCORE_MATMUL` row 19; `MASKED_SOFTMAX` row 20; `VALUE_PREPARATION` rows 21–24 (V permutation, contiguous conversion, concatenation, padding); `VALUE_MATMUL` row 25; `OUTPUT_PACKING` rows 26–27 (permutation and contiguous conversion) |
| Selection ABI | reuse `ggml_ffi.graph_select_slot_range`; exact populated table-owned slots occur once in the source graph and retain its internal topological order. Core node counts are exactly 5, 1, 1, 4, 1, 2; all nine slices total the source count. Output/residual has 4 nodes only on the last layer, otherwise 2 |
| Ownership/allocation | one diagnostic context owns all nine graph structures and is freed before source graph/tensor contexts, allocator and buffers. No slice owns tensors or allocators. Allocate sufficient diagnostic context bytes for nine graph structures; normal/item-71/item-72 allocation and execution remain unchanged. Added outcome counters are zero-initialized scalars |
| Compute failure | `R5_GGML_INIT` / `attention_core_partition` for malformed/missing selections or wrong counts; `R5_COMPUTE` with `status_qk_preparation`, `status_score_matmul`, `status_masked_softmax`, `status_value_preparation`, `status_value_matmul`, or `status_output_packing` for the first failing core compute; skip later computes and never commit a failed step |
| Direct clocks | `attention_qk_preparation_ns`, `attention_score_matmul_ns`, `attention_masked_softmax_ns`, `attention_value_preparation_ns`, `attention_value_matmul_ns`, `attention_output_packing_ns`; their sum is `attention_core_ns`. Existing projection/core/output sum and attention/router sum remain exact |
| Commit boundary | matching `remaining_decode_` counters accumulate only successful steps after the first decode step. Maximum 2 has all-zero core detail; maximum 128 has all-positive clocks |
| Helper | `olmoe_attention_core_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; preserve every item-72 record field and add `attention_core_operations` with exact keys `total_ns`, `qk_preparation_ns`, `score_matmul_ns`, `masked_softmax_ns`, `value_preparation_ns`, `value_matmul_ns`, `output_packing_ns` |
| Accounting | all detail values are nonnegative signed 64-bit integers (booleans rejected); six children sum to `total_ns`, which equals `attention_operations.attention_core_ns`; inherited parent equations remain enforced |
| Shipped-state evidence | preserve exact output and cache counts (11,940 requests, 7,325 hits, 4,615 misses, 4,376 evictions, 17,656,872,960 fetched bytes, zero cache-to-claim copies), repeatability and balanced native lifetimes; validate diagnostic lifetime counts within each produced short/full pair |
| Repetition/isolation | four sequential fresh-process short/full pairs, short maximum 2 an exact full-output prefix; zero matching pinned model/server processes before, between and after each pair |
| Immutable baseline/floor | item 68 full-helper samples `[17714825083,16684315166,17132135334,21189618042]` ns, median 17,423,480,208 ns; ceiling-rounded 50,000-ppm floor 871,174,011 ns. Item 72's diagnostic medians do not reset the baseline |
| Aggregate/decision | four-sample integer medians in the six-class order above; largest median wins, earlier class breaks ties; share is winner median / core-parent median in ppm. Below floor: `NO_MATERIAL_CORE_CLASS`; otherwise: `MEASURED_CORE_SEAM_ELIGIBLE`, with the selected class naming only its exact row sequence |
| Result schema | exact-key schema-1 `R8_OLMOE_ATTENTION_CORE_DIAGNOSIS` JSON on stdout, concise stderr summary. Reuse item 72's top-level keys; boundary describes the six exact ranges and outer ranges; aggregate uses `core_values_ns` / `core_median_ns` in place of its parent's attention values/median |
| Source/external identity | independently pin every transitively consumed runner/helper/source plus new helper, all changed Align sources and regression owner, shim/stub/build scripts, fixed model/pack/geometry/server, compiler/revision, ggml libraries and consumed headers, C compiler/version, task/prompt/token chain, built helper/shim, clean head and inherited host fingerprint |
| Validation order | arguments/prerequisites; inherited constants/source identities; scrubbed environment/linker inputs; fixed host, clean head, process absence and external identities; exact-source build; four pairs; record schema/output/cache/lifetimes/accounting/repeatability; aggregate; final head/source/external rechecks; cleanup-inclusive ceiling; publication |
| Refusal/early exit | nonzero with no complete document for malformed clocks/schema/ranges/counts, compute failure, source/host/output/cache/lifetime/isolation drift, child failure, mutation, cleanup failure or ceiling excess. Missing prerequisite emits exactly one declared N/A line |
| Cost ceiling | one monotonic 8-minute ceiling includes helper/shim build, eight requests, validation, final identities and cleanup; narrower child bounds inherited |
| Persisted/cache identity | N/A: no persisted production format, cache policy, provider grammar or model format change; runner stdout is not persisted by the runner |
| Acceptance | `make fmt`; helper type-check/build; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation and focused self-test; clean-head fixed-host four-repeat qualification; `git diff --check`; comprehensive review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-ATTENTION-CORE-DIAGNOSIS -- scripts/run-olmoe-attention-core-diagnosis --self-test` |

These are operation-sequence walls including backend dispatch, not kernel-only timings. Nine
slices add eight dispatches per routed layer versus normal execution and five versus item 72.
Any selected implementation must clear a separately precommitted full-request shipping gate.
Cross-host/GPU/throughput claims, persistent inference, public provider changes and aggregate-only
audits are N/A. Existing shipped Align FFI, raw handles and scalar timing suffice; no new Align
capability is needed.

## Closure matrix and implementation map

| Owner/path | Construction and success | Failure/malformed and early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- |
| `moe_decode_step` graph selection | nine ranges selected by slot membership; exact counts and dependencies | absent slice or wrong count fails before computing | diagnostic context freed first | layer smoke's branched range fixture extended to singleton/multiple core slices; real fixed output |
| `moe_decode_step` compute | declared class order; six direct clocks close to parent | first failing class labels status and skips all later work | existing common teardown | class-order/failure fixture and real output/lifetime qualification |
| Existing modes | normal source graph; item 71 two slices; item 72 four slices | retain existing errors and requested-step behavior | unchanged owners | runtime-provider smoke; existing layer smoke; source-path inspection |
| `moe_model_forward` / step counters | zero initialization; successful-step-after-first commit | failed steps contribute no remaining-decode counters | scalars only | helper zero short/full positive equations, failed-step inspection |
| Shared helper and new entry | only new helper enables core mode; inherited schemas unchanged | bad arguments/accounting reject before printing | invocation-owned state | helper type-check/build; runtime-provider smoke; full real records |
| Python record/result validators | exact schema, integer range, all parent equations, deterministic median/ties/floor | boolean/negative/overflow/missing/extra keys, child/parent drift, wrong boundary rejected | no complete result on error | focused self-test malformed vectors, six at-floor decisions and below-floor/tie cases |
| Runner identity/repetition | pin complete consumed chain and fixed external identities; four reproducible pairs | drift/mutation/wrong sample count aborts without result | inherited signal/deadline/process cleanup and root binary restoration | focused source mutation and inherited validators; twelve real isolation checks |
| Publication | final unchanged head/identities, exact aggregate | interrupted/late/cleanup failure cannot publish complete JSON | cleanup before elapsed check/publication | focused cleanup-ceiling regression and real completed qualification |

Generic monomorphization, asynchronous escape, move/source-nulling, shared connection state and
concurrent production calls are N/A: synchronous graph slices borrow only existing tensors within
one layer frame. The same source graph remains the allocator's ownership domain; selected slice
execution must preserve all live inputs even when its order differs from the original traversal.

## Author consistency pass

The six nonoverlapping ranges cover every core row exactly once and each dependency comes from
an earlier class or the projection prefix. Singleton score, softmax and value classes expose the
individual matrix/normalization operations; preparation and packing expose only their stated short
sequences. Every class shares the inherited floor and no result authorizes the rejected width
change. The ledger, closure matrix and helper account for the same six clocks and retain all parent
equations. Final evidence will map these cells to the settled diff before review.
