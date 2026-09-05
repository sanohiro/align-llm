# R8 OLMoE expert phase-B operation diagnosis

Status: complete — decision `NO_MATERIAL_EXPERT_OPERATION`

Roadmap owner: item 79, `R8-OLMOE-EXPERT-PHASE-B-OPERATION-DIAGNOSIS`

## Decision and contract

Item 77's exact fixed-request leaf projection measures the shipped decode expert phase-B graph at
a 1,175,633,134-nanosecond median, above the unchanged 871,174,011-nanosecond materiality floor.
That clock covers the complete 24-node top-8 graph and does not identify an operation. This
capability executes the already-built and already-allocated graph as exact checked node-table
ranges so the next R8 decision can select only a measured material child. It makes no optimization
or primary-metric claim.

| Surface | Exact contract |
| --- | --- |
| Owner and CLI | `scripts/run-olmoe-expert-phase-b-operation-diagnosis`; no arguments runs the opt-in fixed-host qualification and `--self-test` runs its model-free owner |
| Consumer | the next R8 implementation ledger or narrower diagnosis selected from item 77's material `EXPERT_PHASE_B` leaf |
| Align API | add `moe_decode_step.generate_resident_sampled_expert_phase_b_operation_diagnosis` with the same arguments, validation, ownership and `GenerationParts` result as its sampled diagnostic siblings; failure remains in the owned outcome with an empty token array |
| Fixed inputs | inherit item 77's exact model, AlignPack, geometry, task and prompt, seed 5, temperature 300,000 micros, maximum 128, EOG rule, 975,175,680-byte cache budget, exact 87-id chain, 86 completion tokens and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Source graph | preserve all 24 top-8 phase-B rows, operands, compact expert ids, cache tensors, output marks, allocation and source topological order |
| Operation membership | `INPUT_PREPARATION` rows 0-2; `GATE_PROJECTION` row 3; `UP_PROJECTION` row 4; `SWIGLU` row 5; `DOWN_PROJECTION` row 6; `EXPERT_WEIGHTING` row 7; `EXPERT_REDUCTION` rows 8-22; `RESIDUAL` row 23. For a general supported `n_expert_used`, reduction is rows 8 through `6 + 2 * n_expert_used` and residual is the final row |
| Selection ABI | reuse `ggml_ffi.graph_select_slot_range`; every populated table-owned output slot in a range must occur exactly once in the source graph and each slice retains source-topological order. Construct all eight slices before any compute and require their node counts to sum to the source graph count |
| Compute order | input preparation, gate projection, up projection, SwiGLU, down projection, weighting, reduction, residual, exactly once each. The source graph is not computed as an additional control |
| Ownership/allocation | one diagnostic context owns eight borrowed graph structures and is freed before the source graph/tensor contexts, allocator and buffers. Slices own no tensors or allocators. Normal and every earlier diagnostic mode retain their existing contexts and execution. Added counters are zero-initialized scalars |
| Failure | context refusal is `R5_GGML_INIT` / `expert_phase_b_operation_context`; selection refusal or wrong counts are `R5_GGML_INIT` / `expert_phase_b_operation_partition`; the first compute failure is `R5_COMPUTE` with `status_expert_input_preparation`, `status_expert_gate_projection`, `status_expert_up_projection`, `status_expert_swiglu`, `status_expert_down_projection`, `status_expert_weighting`, `status_expert_reduction`, or `status_expert_residual`. Later slices are skipped and a failed step is not committed |
| Direct clocks | add eight matching `expert_..._ns` outcome clocks. Their exact sum is `expert_compute_ns`; the phase-B parent remains the sum of direct slice walls, including backend dispatch, and is not a residual subtraction |
| Commit boundary | add eight matching `remaining_decode_` counters at the existing successful-step-after-first commit. Maximum 2 reports all zero; maximum 128 reports all positive and the exact parent equation |
| Qualification helper | `olmoe_expert_phase_b_operation_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; preserve the predecessor record and add exact `expert_phase_b_operations` keys `total_ns`, `input_preparation_ns`, `gate_projection_ns`, `up_projection_ns`, `swiglu_ns`, `down_projection_ns`, `expert_weighting_ns`, `expert_reduction_ns`, and `residual_ns` |
| Accounting | every detail is a nonnegative signed 64-bit integer with booleans rejected; eight children sum exactly to `total_ns`, which equals `decode_compute.expert_ns`; conditioning values are zero and full values are positive |
| Repetition/isolation | four sequential fresh-process short/full pairs; maximum 2 is an exact output prefix of maximum 128; no process matching both the pinned server and model paths exists before, between or after pairs |
| Shipped-state evidence | preserve full-width phase A, native KV staging, cache-backed phase B, exact output, 11,940 requests / 7,325 hits / 4,615 misses / 4,376 evictions / 17,656,872,960 fetched bytes, zero cache-to-claim copies, and balanced native lifetimes. Context/graph counts are validated from each produced record for the new mode |
| Immutable baseline and floor | item 68 full-helper samples `[17714825083,16684315166,17132135334,21189618042]` ns, median 17,423,480,208 ns; 50,000 ppm rounded up is 871,174,011 ns. Item 77's expert median is attribution context, not a new baseline |
| Aggregate and decision | take four-sample integer medians in the operation order above, choose the largest with that order breaking ties, and report its share of the phase-B parent median. A winner below the floor yields `NO_MATERIAL_EXPERT_OPERATION`; material `INPUT_PREPARATION` yields `EXPERT_INPUT_SUBDIAGNOSIS_REQUIRED`; material `EXPERT_REDUCTION` yields `EXPERT_REDUCTION_SUBDIAGNOSIS_REQUIRED`; a material singleton yields `MEASURED_EXPERT_OPERATION_ELIGIBLE` with the selected class |
| Result | one exact-key schema-1 `R8_OLMOE_EXPERT_PHASE_B_OPERATION_DIAGNOSIS` JSON document on stdout and one concise stderr summary; no complete document on failure |
| Source/external identity | independently pin the complete inherited runner/helper/source chain plus the new runner/helper, changed Align sources and focused test, shim/stub/build sources, model/pack/geometry/server, Align revision/compiler, ggml libraries and consumed headers, C compiler/version, task/prompt/token chain, built helper/shim, clean head and item-77 host fingerprint |
| Validation order | arguments and prerequisites; imported constants and source identities; scrubbed environment/linker search; fixed host, clean head, process absence and external identities; exact-source build; four conditioned records; schema/output/cache/lifetime/accounting/repeatability; aggregate; final identity/head rechecks; cleanup-inclusive ceiling; publication |
| Refusal and early exit | invalid arguments, malformed clocks/schema/ranges/counts, source/host/output/cache/lifetime/isolation drift, child failure, mutation, cleanup failure or ceiling excess exit nonzero without a complete document. A missing prerequisite emits exactly one declared N/A line |
| Persisted/cache identity | N/A: no persisted result, provider grammar, cache policy, model, pack or task format changes; qualification stdout is not persisted by the runner |
| Cost ceiling | one monotonic 8-minute ceiling includes build, eight requests, validation, final identities and cleanup; children retain narrower inherited bounds |
| Acceptance | author ledger-to-prose pass; focused allocated-stub slice/order/failure coverage; `make fmt`; helper build; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation and runner self-test; one clean-head fixed-host four-repeat diagnosis; `git diff --check`; one comprehensive review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-EXPERT-PHASE-B-OPERATION-DIAGNOSIS -- scripts/run-olmoe-expert-phase-b-operation-diagnosis --self-test` |

Cross-host, GPU, throughput, arbitrary-task, cache-policy, persistent-state, provider, per-kernel and
performance-win claims are N/A. Eight slices add seven backend dispatches per routed layer versus
normal execution. A selected operation still needs its own unchanged full-request shipping gate.
Existing Align FFI and raw-handle ownership are sufficient; no Align capability request is needed.

## Closure matrix and implementation map

| Owner/path | Construction and success | Failure/malformed and early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- |
| `moe_decode_step` selection | eight exact slot ranges selected after the allocated source graph; expected counts are 3/1/1/1/1/1/15/1 at top-8 and sum to 24 | absent slice, wrong count or non-source/duplicate slot fails before compute | diagnostic context freed first | focused tiny-model pointer-order/count assertions and selection refusal |
| Diagnostic compute | declared dependency order, each slice once, children close to phase-B | first failing class uses its exact label and skips successors; no successful step commit | existing converged layer teardown | eight forced compute failures, late failure, no-later-compute and lifetime balance |
| Existing modes | new flag false leaves one source phase-B compute and all new counters zero | existing statuses and requested-step behavior unchanged | existing owners | normal/helper and runtime-provider smoke plus source-path inspection |
| Outcome and step commit | layer, outcome and remaining-decode counters start at zero; only successful post-first steps add exact deltas | failed/first step cannot enter remaining-decode detail | scalars only | short zeros, full positives, equation and failed-step regression |
| Helper and runner | only the new helper enables the mode; inherited fields and fixed evidence remain exact | bad arguments, schema, boolean/negative/overflow or equation drift reject before print | invocation-owned temporary state | helper build, malformed vectors, source mutation and inherited owner self-tests |
| Aggregate | deterministic medians, tie order, floor and share | wrong sample count/type/baseline/identity aborts without result | N/A | below-floor, tie and each class-at-floor vectors |
| Process and publication | exact-source children, twelve isolation checks, final unchanged identities and one result | interruption, timeout, late mutation or cleanup failure cannot publish | inherited terminate/wait/kill and root-binary restoration | inherited signal/cleanup tests and real qualification |

Generic monomorphization, asynchronous escape, move/source-nulling, persisted migration, shared
connections and production races are N/A. Every selected graph borrows tensors synchronously inside
one routed-layer frame and cannot escape the diagnostic context. The source allocator remains the
only tensor-buffer owner.

## Author consistency pass

The ledger and matrix define the same eight exhaustive, nonoverlapping table ranges, the same
dependency-valid compute order, the same failure labels and successful-step commit boundary. Only
the qualification helper enables split execution. The direct child sum owns the parent clock, the
unchanged materiality floor governs selection, and no diagnosis result alone claims an optimization.

## Result

Clean head `a0ccf9faf2a3b6a46b4ef85d9fdee4a59da34b8a` completed four sequential short/full
pairs in 110.820 seconds. Every record preserved the exact token chain and output digest, direct
cache request/hit/miss/eviction/fetched-byte evidence, zero cache-to-claim copies, process isolation,
balanced native lifetimes, and the declared parent/child equations. The full-helper walls were
`[18028510875,19398845334,19489354333,19095181334]` ns (median 19,247,013,334 ns), and
the expert parents were `[1730445593,1809969951,1784429671,1752010741]` ns (median
1,768,220,206 ns).

The operation medians were input preparation 27,067,208 ns, gate projection 574,962,948 ns,
up projection 444,561,299 ns, SwiGLU 54,744,079 ns, down projection 531,428,285 ns, expert
weighting 85,859,347 ns, expert reduction 32,087,287 ns, and residual 24,735,486 ns. Gate
projection was largest at 325,164 ppm of the expert parent but remained below the immutable
871,174,011-ns floor. The result is `NO_MATERIAL_EXPERT_OPERATION`; no child is eligible for an
implementation or narrower diagnosis, and this measurement makes no optimization claim.

The final diff maps every ledger and closure-matrix row to `moe_decode_step`'s opt-in construction,
ordered compute and successful-step counters; the qualification helper and runner; or the focused
allocated-stub refusal/failure/lifetime owner. No declared cell is deferred.
