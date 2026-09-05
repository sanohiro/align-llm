# R8 OLMoE plane-upload diagnosis

Status: complete; `MEASURED_UPLOAD_SEAM_ELIGIBLE / NATIVE_STAGING`; merged in PR #198 as `d32d3cb`, 2026-09-05.
Roadmap owner: item 76, `R8-OLMOE-PLANE-UPLOAD-DIAGNOSIS`.
Prerequisite: item 75 merged as `d9fd56cd5170a69a6a8a3ac2fc8f6fed76e7bdc3` (PR #197).

## Evidence and selected consumer

Item 75's four contemporaneous control full records were passed through the actual item-70
`leaf_values` function, including its inherited helper-schema validation and exact 23-leaf sum.
Control source was `36183a342d2f87bcf153dfd1d347d38efc08b9a1`; evaluated V candidate was
`248e2314ebbb429e4027c5cb249e680a15cec310`. The complete original document has SHA-256
`90ec26172c3ce7205fef855fadcacb02fa11aaab435698d21d2eaea87eba5057` and is retained in [item 75 raw evidence](https://github.com/sanohiro/align-llm/pull/197#issuecomment-5549037139),
retrieved and hash-verified before merge. This projection requires no new model execution.

Control full-helper walls were `[15458388000,17107525625,17248785542,17615545166]` ns, median
17,178,155,583 ns. Remaining-decode walls were
`[11170839338,12058810920,12175956754,12395145710]` ns, median 12,117,383,837 ns.

| Rank | Existing leaf | Current control median (ns) | Disposition |
| ---: | --- | ---: | --- |
| 1 | `ROUTING_PHASE_A` | 3,204,739,634 | Already narrowed by items 71–73; rejected K and V copy interventions are not eligible unchanged successors. |
| 2 | `PLANE_UPLOAD` | 2,313,750,636 | Largest material parent with an unmeasured, source-defined internal boundary; selected for this diagnosis. |
| 3 | `FILE_PREAD` | 1,847,535,868 | Material; item 65's mapping intervention was rejected. Any future treatment needs a distinct contract. |
| 4 | `EXPERT_PHASE_B` | 1,293,647,944 | Material; item 68 already ships cache-backed phase B. Remaining graph work is an independent future diagnosis. |
| 5 | `GENERIC_TRANSFER_DIGEST` | 948,707,756 | Material; separate future attribution, not included here. |
| 6 | `PLANE_ROUNDTRIP_COMPARE` | 825,781,136 | Below the inherited floor; item 68 already ships the exact-safe comparison. |
| 7 | `CLAIM_TO_CACHE_COPY` | 536,857,860 | Below floor. |
| 8 | `GRAPH_TEARDOWN` | 294,133,969 | Below floor. |
| 9 | `BLOCK_TO_CLAIM_COPY` | 293,966,122 | Below floor. |
| 10 | `OUTPUT_HEAD` | 169,393,437 | Below floor. |
| 11 | `POST_PASS_ORCHESTRATION` | 167,230,583 | Below floor. |
| 12 | `GRAPH_BUILD_ALLOC` | 112,208,259 | Below floor. |
| 13 | `CONTEXT_BUFFER_SETUP` | 33,142,602 | Below floor. |
| 14 | `OTHER_CLAIM_IO` | 23,942,546 | Below floor. |
| 15 | `OTHER_PASS_REMAINDER` | 18,743,412 | Below floor. |
| 16 | `ROUTING_ORCHESTRATION` | 11,935,814 | Below floor. |
| 17 | `PLANE_READBACK` | 8,529,734 | Below floor. |
| 18 | `GRAPH_MEMBER_SPEC` | 8,091,691 | Below floor. |
| 19 | `LAYER_STEP_ACCOUNTING` | 1,235,449 | Below floor. |
| 20 | `EMBEDDING` | 1,195,142 | Below floor. |
| 21 | `PRE_PASS_ORCHESTRATION` | 864,896 | Below floor. |
| 22 | `PACK_OR_RESIDENT_STAGE` | 142,023 | Below floor. |
| 23 | `CACHE_TO_CLAIM_COPY` | 0 | Eliminated by shipped item 68; remains exactly zero. |

Current upload values are `[2030408967,2294958664,2332542608,2363924384]` ns. Its parent wall
is not an estimate of removable cost. Item 74 K and item 75 V each improved only two of four
pairs; their median paired gains were 3,851,438 ns and -15,955,313 ns. Neither is directional
positive evidence and neither may be carried into this capability or combined for a rerun.
Item 63's live-width change remains rejected; item 67 changed exact cache accounting. Item 65's
mapped-file candidate was 2,999,417,313 ns slower at the median and does not become eligible
because file pread is still material. Item 73's other core classes were below the same floor:
score 123,514,742, softmax 26,535,106, value matmul 145,335,829 and packing 11,965,026 ns;
item 71's router and item 72's projection/output-residual classes were also below it.

The next useful consumer is an implementation ledger for a material upload child, not another
attention candidate or an R8-closing claim. Item 69's primary time-to-passing-patch result remains
`NOT_MET` (local median 13,992,706,375 ns; runtime 91,415,902,187 ns). A rejected and restored
candidate does not trigger unchanged portfolio remeasurement. A future shipping ledger must explicitly select its successor; R8 closure still depends on the
primary metric.

## Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Owner/CLI | `scripts/run-olmoe-plane-upload-diagnosis`; no arguments runs the opt-in fixed-host diagnosis; `--self-test` runs its model-free contract owner. No public provider CLI change. |
| Source baseline | `d9fd56cd5170a69a6a8a3ac2fc8f6fed76e7bdc3` is the immutable merged item-75 source base with both rejected copy candidates removed. Require it to be an ancestor of evaluated and publication heads. Build one diagnostic helper and shim from the exact clean evaluated head; this is one-arm attribution, not a control/candidate performance comparison. Preserve the evaluated commit in publication ancestry; use merge integration, not squash/rebase, and resolve ancestry through one Git common directory with replacements/grafts refused. |
| Align API | `moe_decode_step.generate_resident_sampled_plane_upload_diagnosis(pack_path: str, geometry_path: str, expected_geometry: str, source_identity: alignpack.SourceIdentity, borrow prompt_token_ids: array<i64>, borrow eog_token_ids: array<i64>, max_tokens: i64, cache_budget_bytes: i64, seed: i64) -> GenerationParts`. Same input validation, borrowed input lifetimes, owned token JSON/outcome and failure code/detail as `generate_resident_sampled`; no new public input grammar or new error enum. |
| Execution mode | Thread one `plane_upload_diagnosis: bool` through the generation/execution/schedule chain to `decode_pass`. The new entry alone enables it. All existing entries pass false; all three graph-diagnosis flags are false in the new entry. Keep normal unsplit phase A, graph construction/order/counts, full widths, node identities/marks, cache selection and tensor lifetimes. Do not thread this flag into `run_moe_layer`, which owns no part of this staging interval. |
| Existing parent and excluded allocation | In `decode_pass`, preserve `mut stage: buffer := buffer(past_bytes * 2)` before the existing upload start. The capacity-hint constructor lies outside `state.upload_ns` and both new children; do not move it inside, rename it as measured priming, or claim this diagnosis measures its reservation cost. |
| Exact cut points | `t0` is the existing `upload_started` instant after stage construction. Execute unchanged `prime_window(stage, past_bytes * 2)` then `stage.bytes()`. In diagnosis mode only take `t1` immediately before the existing `match ggml_ffi.stage_kv(...)`. `t2` is the existing finish instant after that match. Parent increment is `t2-t0`; priming is `t1-t0`; native staging is `t2-t1`. Capture each endpoint once and share it; no independently retimed parent and no residual subtraction bucket. |
| `STAGING_PRIMING` | Owns `prime_window`'s 65,536-byte temporary chunk construction, scalar zero fill through `fill_zero`, chunked appends into the stage and stage-view extraction, including intervening language-call/clock overhead. Existing allocation and byte-writing order remain unchanged. |
| `NATIVE_STAGING` | Owns offset/argument evaluation, the existing `ggml_ffi.stage_kv` wrapper/native call and its Result dispatch up to `t2`. The shipped native function checks all source/destination geometry and overlap, copies K by head/column blocks and transposes V by head/lane/column scalar byte copies. This child is the whole existing checked call boundary; it neither separates K from V nor measures a kernel alone. |
| Instrumentation cost | Exactly one additional `time.instant()` per admitted routed layer in diagnosis mode; no extra graphs, tensor operations, staging copies or allocations. Existing modes retain their two parent timing instants and leave new counters zero. The timing branch/counter bookkeeping is diagnostic overhead, not a claimed optimization. |
| Counter owners | Add zero-initialized implementation-owned `Plane.priming_ns` and `Plane.native_staging_ns` beside `upload_ns`. Add zero-initialized public Outcome scalars `remaining_decode_plane_priming_ns` and `remaining_decode_plane_native_staging_ns` in `moe_model_forward`. Snapshot these totals with `before_plane_upload`; commit their deltas only at the same successful-step-after-first branch as `remaining_decode_plane_upload_ns`. The existing `pub Plane` visibility is preserved; these totals are not rendered. No whole-run Outcome child clocks are needed. |
| Failure/commit | Preserve staging refusal `R6M_PLANE_UNAVAILABLE` with existing layer-specific `stage` detail. Skip layer compute and later work after the first failure. Internal elapsed totals may include attempted work; never publish a failed step in either remaining-decode child. A failed first/second step leaves new remaining children zero; already completed remaining steps keep their committed evidence. First decode is excluded just like the parent. Buffer capacity failure is not newly observable; no fabricated allocation error path. |
| Helper | New `src/olmoe_plane_upload_gate.align` delegates `main(args)` to new shared-helper `plane_upload_main(args: array<str>) -> Result<(), Error>`. Exact invocation: `olmoe_plane_upload_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`, with maximum only 2 or 128. Extend the shared helper's internal mode arguments and add `PlaneUpload { total_ns: i64, priming_ns: i64, native_staging_ns: i64 }`; append only `plane_upload` to the unchanged item-68 detailed/helper schema (through claim I/O), with no phase-A/attention objects. Old helper schemas remain byte-for-byte structurally identical. |
| Record equations | `plane_upload.priming_ns + plane_upload.native_staging_ns == plane_upload.total_ns == remaining_decode.plane_upload_ns`. Preserve every inherited helper parent equation. Validate clocks as nonnegative signed-64-bit integers, rejecting booleans, missing/extra/duplicate keys and overflow; short-2 detail is all zero, full-128 both children and parent are positive. Helper accounting failure returns `Error.Invalid` before printing; Python owner also validates independently. |
| Fixed request/state | Inherit item 68/73's exact model, pack, geometry, task/system/user prompt, seed 5, temperature 300000 micros, maximum 128, terminal EOG, 975175680-byte cache budget, 87-id chain, 86 completion tokens and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52`. Each full record retains 11940 cache requests, 7325 hits, 4615 misses, 4376 evictions, 17656872960 fetched bytes and zero cache-to-claim copies. |
| Repetition/isolation | Four sequential fresh-process short-2/full-128 pairs: eight requests total. Each short must be the exact prefix of its paired full result. Record absence of processes matching pinned server/model before, between and after each pair (12 checks); validate each record's balanced native context/buffer/backend/allocator/wrap lifetimes and release-before-owner-scope-end evidence. No AB/BA order is applicable because there is one diagnostic arm. |
| Immutable floor | Keep item-68 baseline walls `[17714825083,16684315166,17132135334,21189618042]`, median 17423480208 ns and ceiling-rounded 50000-ppm floor 871174011 ns. Neither item-75 current control nor this diagnostic run resets that floor. The candidate performance ceiling 16552306197 ns is not a diagnosis admission gate; it belongs to a separately precommitted future optimization gate. |
| Aggregate/selection | Integer median of four nonnegative values is floor of the sorted middle-pair sum divided by two. Class order is `STAGING_PRIMING`, then `NATIVE_STAGING`; largest median wins and the earlier class wins ties. Share is floor(winner median * 1000000 / upload-parent median). Below floor yields `NO_MATERIAL_UPLOAD_CLASS`; at/above floor yields `MEASURED_UPLOAD_SEAM_ELIGIBLE` naming only that exact measured child. A below-floor result returns to the other material leaves above; it does not imply R8 has no eligible work. |
| Result document | Exact-key schema-1 `artifact_kind="R8_OLMOE_PLANE_UPLOAD_DIAGNOSIS"`, status `COMPLETE`, stdout only after success/cleanup. Reuse item 71's keys `schema_version,artifact_kind,status,model,baseline,candidate,intervention,boundary,task,environment,samples,aggregate,elapsed_ns`, its item-68 semantic schemas, and its four-sample convention. Baseline exact keys remain `full_helper_wall_values_ns,full_helper_wall_median_ns,floor_ppm,floor_ns`. Aggregate exact keys are `full_helper_wall_values_ns,full_helper_wall_median_ns,upload_values_ns,upload_median_ns,class_values_ns,class_medians_ns,selected_class,selected_class_median_ns,selected_class_share_ppm,floor_ppm,floor_ns,decision`. Class dictionaries have exactly the two declared identifiers. This records attribution, not `MET`/`NOT_MET` speedup. |
| Boundary object | Exact keys/values: `merged_source_base="d9fd56cd5170a69a6a8a3ac2fc8f6fed76e7bdc3"`, `parent="remaining_decode.plane_upload_ns"`, `priming="prime_window_and_stage_view"`, `native_staging="stage_kv_and_result_dispatch"`, `stage_capacity_allocation="EXCLUDED_BEFORE_PARENT_START"`, `execution="NORMAL_UNSPLIT_PHASE_A"`, `additional_instants_per_layer=1`. |
| Source/external identities | Pin the complete actually consumed runner/helper/Align graph, this owner, new helper, focused regression, unchanged real/stub shims and build scripts; fixed model/pack/geometry/server/task/prompt/token chain; Align revision `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`, its compiler/runtime identity, ggml libraries/all consumed headers, C compiler/version/linker search and inherited host fingerprint. Record exact clean head and built helper/shim identities; recheck source/external/head identities after requests. The evaluated runner pins adjacent `libalign_runtime.a` SHA-256 `7a36c1eb075b74b7c61a5d7ed229d684e5759fce2f35d32455e07bbad5aba38f` and refuses missing, symlinked or changed archives before/after measurement. The head-bound constant preserves the existing result schema. Reuse validators without asserting obsolete historical source hashes against changed files; the new owner must pin its complete current dependency closure independently. |
| Cost/order/refusal | One monotonic 8-minute ceiling includes helper/shim build, eight requests, validation, identity rechecks and cleanup. Order: arguments/prerequisites; workload/baseline/source constants; scrubbed environment/linker inputs; host/clean head/ancestry/process absence/external identities; exact-source build; four pairs; record/output/cache/lifetime/accounting/repeatability validation; aggregate; final identities; cleanup; elapsed ceiling; publication. Nonzero/no complete JSON on child failure, malformed data, contamination, drift, mutation, timeout, interruption, cleanup failure or excess; missing prerequisite emits one declared N/A line. |
| Ownership/cache/persistence | Invocation-owned scalars and borrowed existing ranges only; no new native handles, FFI symbols, callbacks, buffers or ownership transfer. Existing item-58 range owners and cleanup remain authoritative. No cache, model, pack, provider, process-sharing or persisted-production schema change; stdout is caller-owned evidence. |
| Acceptance/publication | Scoped `make fmt`; pinned `./scripts/alignc check-per-unit src/olmoe_plane_upload_gate.align` and helper build; `scripts/test-olmoe-plane-upload`; `make runtime-provider-smoke`; focused runner `--self-test` and Python compilation; one clean-head fixed-host four-repeat diagnosis; `git diff --check`; one comprehensive stable-candidate review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-PLANE-UPLOAD-DIAGNOSIS -- scripts/run-olmoe-plane-upload-diagnosis --self-test`. Native tensor/operation contracts do not change, so new native math/UBSan/three-shim-build qualifications and `make ci` are N/A. No aggregate membership changes. |

## Closure matrix and exact owner cases

These case names are the required named regressions in the new focused owners, not existing
passing evidence. The focused model fixture may reuse `scripts/olmoe_provider_fixture.py` and the
existing attention-core owner's isolated build technique. Its wrapper includes the checked-in stub
unchanged and injects staging failures only in the test library; no production test flag is added.
Normal API/schema cases compile the unchanged copied source. Separate malformed-accounting cases
redirect only the new helper call through an isolated fixture adapter that corrupts one returned
counter before the unchanged validation/rendering body. This is fault injection, not an unchanged
helper integration claim; the fixed-host qualification builds the unmodified tracked helper.

| Owner/path | Construction and success | Failure/malformed/early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- |
| `moe_decode_step` mode and interval | Only new API enables midpoint; exact t0/t1/t2 partition around existing priming/staging; normal unsplit execution | Existing API refusals preserved; no stage/compute after staging failure | Existing stage lexical owner and native teardown | `scripts/test-olmoe-plane-upload`: `normal_mode_zero`, `upload_mode_partition`, `normal_unsplit_parity`, `stage_failure_before_compute`; API/source cut-point inspection |
| `moe_model_forward`/Plane counters and schedule | All new fields zero initially; first successful decode excluded; later successful deltas sum to parent | Failed step cannot commit children; successful earlier evidence retained by same schedule branch | Scalars require no separate release | Same owner: `short_prefix_zero`, `successful_remaining_commit`, `stage_failure_after_first_decode`, `late_compute_failure_no_upload_commit`; real short/full equations |
| Shared helper/new entry | Exact inherited base record plus only `plane_upload`; old helpers keep their previous keys; invalid count/maximum/seed refused | Child/accounting mismatch rejects before any complete document | Existing token/model/pack invocation ownership | Same owner: `helper_mode_schema`, `helper_invalid_arguments`; pinned helper check/build; runtime-provider smoke; real records |
| Unchanged byte transfer | Same stage extent/order, K block/V scalar transpose, wrapper status | Refusal still precedes byte writes; injection observes no later compute | No new allocation or C mutation | Same owner: `normal_unsplit_parity`, `stage_failure_before_compute`; existing item-58 owner remains authoritative, no new native implementation |
| Python record validation | Exact helper keys, integer ranges, both child/parent equations and inherited semantics | Boolean, negative, oversized, missing/extra/duplicate fields; wrong parent; short nonzero; full nonpositive refused | No complete result | `scripts/run-olmoe-plane-upload-diagnosis --self-test`: `record_schema_and_integer_edges`, `child_parent_partition`, `short_full_rules`, `inherited_semantics` |
| Python aggregation | Four values, declared tie order, exact median/floor/share; only material child selected | Wrong count/class/boundary, recomputed baseline, wrong decision rejected | Decoded JSON only | Same self-test: `both_at_floor_decisions`, `below_floor_no_class`, `tie_prefers_priming`, `aggregate_recomputation`, `boundary_identity` |
| Runner source/process ownership | Exact current consumed source/external identities, base ancestry, fixed request and four fresh pairs | Source mutation, dirty/changed head, wrong ancestry, process contamination, child/timeout/signal failures reject | Owned process-group cleanup and temporary helper/shim restoration | Same self-test: `source_mutation`, `runtime_identity`, `ancestry_and_linked_worktree`, `repetition_and_isolation`, inherited child cleanup cases; 12 real isolation records |
| Publication | Final head/source/external recheck and validated aggregate; cleanup included in elapsed | Cleanup failure or late ceiling crossing suppresses complete JSON | No owned child/temp artifact survives | Same self-test: `cleanup_failure_no_document`, `cleanup_inclusive_ceiling`; real completed qualification |

## Scope classification and consistency

This is application-owned timing attribution using shipped Align scalars, borrowing, buffers and
`std.time`; it encounters no new blocking language/compiler/runtime requirement. Existing
`docs/align-requests.md` Requests 35 (observable buffer capacity/failure) and 38 (positional writes,
reset and bounded reads) remain recorded nonblocking gaps. The diagnosis neither consumes their
proposed APIs nor hides an allocation refusal behind invented handling. If a selected successor
requires a new buffer operation, classify that actual requirement before its implementation.

The ledger and matrix share exactly two nonoverlapping child intervals, one extra instant, two
non-rendered Plane totals and two committed Outcome counters. The pre-parent capacity constructor is excluded
in both source attribution and boundary metadata. Every normal mode stays unsplit, only completed
remaining steps contribute, and no child result is advertised as removable cost or a speedup.

This capability keeps counter production, consumer JSON, fixed-host selection and their owner tests
together. Splitting those into separate dormant producer and consumer changes would duplicate
source-identity and accounting proof without a useful intermediate consumer.

## Implementation checkpoint and author closure pass

The source/helper implementation and both focused owners are complete. `gmake fmt`, pinned
`./scripts/alignc check-per-unit src/olmoe_plane_upload_gate.align` (17 units),
`scripts/test-olmoe-plane-upload`, `gmake runtime-provider-smoke` (sampler vectors and 61 CLI
assertions), Python compilation, full runner `--self-test` and `git diff --check` passed.
The subsequent fixed-host evidence below closes the remaining measurement cells. This capability
records attribution and makes no speedup claim.

The matrix's API cases exercise actual staging across six failure positions and two late-compute
failures, matching normal token/cache/graph/staged-byte evidence and balanced lifetimes. All eight
old helper schemas and the new short/full schema run unchanged source. Their dedicated fixture
head produces ASCII output while retaining seed 5 and UTF-8 checks; normal API parity keeps the
original fixture. Three separately adapted malformed outcomes fail with `Error.Invalid`, exit 2
and empty stdout. The scalar counters and unchanged native transfer require no new native owner.

Runner cases cover strict actual helper/task parsing, signed-64-bit clock domains, child/parent
partition, short/full rules, inherited semantics, both floor decisions and ties, recomputed results,
133 current source identities, the separate tracked runner/runtime identities, ordinary and linked
Git ancestry, replacement/graft refusal, child groups and launch races, forced termination,
cleanup failure suppression and the cleanup-inclusive ceiling. Every matrix cell has its declared
implementation and named owner; the following clean-head fixed-host qualification closes the
real output/cache/identity/repetition cells. Request 35's evidence now distinguishes the existing internal
runtime capacity symbol from the still-unavailable supported public API; no status or blocker changed.

## Clean-head fixed-host evidence and successor

Evaluated source: `ae77649ee1019238f8db8b1d1e3695012ecfd2a2`, descended from merged item 75
`d9fd56cd5170a69a6a8a3ac2fc8f6fed76e7bdc3`. The no-argument runner completed four fresh short/full
pairs in **93,883,481,250 ns**, including build, all requests, identity rechecks and cleanup.
Every exact output/token chain, cache count/byte, short-prefix, remaining-step partition, native
lifetime, release order and process-isolation boundary passed; all 12 pair isolation records were zero.
The full raw JSON is 25,975 bytes with SHA-256
`12ad135fd526d0bf8ffa0251c83d1a2c417c1ea3d24a8cd891829e29361eed1e`; publication must preserve
and retrieve/hash-verify that exact record. The retained owner now requires the evaluated ancestor.

| Clock | Four values (ns) | Median (ns) |
| --- | --- | ---: |
| Complete helper wall | `[14555812625,15005039583,15825230209,15883507375]` | 15,415,134,896 |
| Plane upload parent | `[1964756337,1998354876,2116291832,2139612627]` | 2,057,323,354 |
| `STAGING_PRIMING` | `[504327041,507249507,540960084,543719044]` | 524,104,795 |
| `NATIVE_STAGING` | `[1460429296,1491105369,1575331748,1595893583]` | 1,533,218,558 |

`NATIVE_STAGING` is largest at **745,249 ppm** of the upload parent median and exceeds the
unchanged **871,174,011-ns** floor: **`MEASURED_UPLOAD_SEAM_ELIGIBLE`**. Priming is below floor,
so its plausible zero-chunk reuse is not an eligible unchanged successor. Each sample partitions
exactly; independently floored medians need not add exactly. The full-helper median is descriptive
of this instrumented run and is not credited as an optimization against a historical run.

Item 77 will own a separately precommitted exact native staging candidate with a contemporary
paired complete-request gate. The existing call includes K block copying, strided V transfer,
checks and Result dispatch; this parent result does not attribute all time to V or make the whole
1,533,218,558 ns removable. Preserve uploaded bits/layouts, refusal precedence, graph execution,
cache/lifetime behavior and full-request cost accounting. Remove any candidate unless its own
complete-request gate passes. Other material leaves remain available; this diagnosis does not close R8.

Bounded retrospective: the small helper fixture needed valid sampled UTF-8 output at fixed seed 5;
a dedicated ASCII-output head owns that test concern without relaxing production decoding. The
new runner independently freezes the actual runtime archive and owns its launched process groups,
closing its own identity/cleanup promises without changing historical owners or adding a global gate.

PR #198 merged as `d32d3cbc2939e1525f452056e8e720946930d4df`, preserving tested integration
tree `aa14ec68e9360b362d3fe7860e9e569885f26726`. Comprehensive review had no findings; exact-head
preflight and all three required checks passed. The [complete original raw JSON](https://github.com/sanohiro/align-llm/pull/198#issuecomment-5549220833)
was retrieved and hash-verified. The merged-head self-test passed with both source/evaluated ancestors.
