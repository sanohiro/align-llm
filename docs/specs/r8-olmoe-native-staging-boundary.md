# R8 OLMoE native staging boundary

Status: complete; fixed-host shipping gate MET, 2026-09-05; publication pending.
Roadmap owner: item 77, `R8-OLMOE-NATIVE-STAGING-BOUNDARY`.
Prerequisite: item 76 merged as `d32d3cbc2939e1525f452056e8e720946930d4df` (PR #198).

## Decision and public-contract ledger

Item 76 evaluated clean head `ae77649ee1019238f8db8b1d1e3695012ecfd2a2` and selected
`NATIVE_STAGING` at 1,533,218,558 ns median, 745,249 ppm of the 2,057,323,354-ns upload parent.
Priming was 524,104,795 ns, below the unchanged 871,174,011-ns floor, so priming reuse is excluded.
All semantic, cache, native-lifetime and isolation conditions passed in 93.883 seconds.

The selected child is the existing checked `ggml_ffi.stage_kv` call and Result dispatch. It is
sufficiently direct for one bounded implementation trial at that call boundary. Its K copy,
validation and V transpose have not been timed separately: no claim assigns all 1.533 seconds to
V, calls that time removable, or predicts a shipping result. The proposed change only tiles the
existing V transpose. Items 74/75's rejected graph concat/pad replacements remain removed.

| Surface | Exact contract |
| --- | --- |
| Consumer/production scope | Each OLMoE decode layer's existing canonical-plane-to-stage transfer. Only `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c` change production bytes, identically inside the shared contract region. Replace only `align_ggml_stage_kv`'s V scalar-copy implementation on AArch64 with exact 4-by-4 byte-lane transpose tiles plus scalar tails. Keep its signature, validation prefix and complete K block-copy loop byte-identical to control. Keep `align_ggml_compare_kv_plane`, its existing helpers, all other native functions, every Align/helper/build source and compiler pin unchanged. |
| Ordinary execution | Both qualification arms use unchanged `src/olmoe_exact_safe_decode_gate.align` and `claim_detailed_main`, hence normal unsplit phase A. No new mode, graph node, custom callback, worker/task hint, environment switch, tensor mark, width, cache policy or priming change. Item-71/72/73/76 diagnostic entries retain their current semantics. |
| Native API | Existing `int32_t align_ggml_stage_kv(const void *plane, int64_t plane_bytes, int64_t k_base, int64_t v_base, void *stage, int64_t stage_bytes, int64_t head_dim, int64_t n_head_kv, int64_t n_past)`. Existing Align `ggml_ffi.stage_kv` continues supplying actual borrowed-view lengths and mapping status to `Result<(), Fault>`; no new FFI or exported native symbol. |
| Layout | Let `D=head_dim`, `H=n_head_kv`, `N=n_past`, `B=4*D*H*N`. Canonical K and V each index `[column][head][lane]`. Stage is exactly `2*B` bytes: K first in `[head][column][lane]`, V second in `[head][lane][column]`. Exact offsets and tile formulas are below. Preserve every four-byte pattern without floating-point interpretation, conversion, contraction or normalization. |
| Validation/refusal order | Preserve the actual existing order: (1) null plane or stage → `ALIGN_GGML_INIT=-6`; (2) negative lengths/bases or nonpositive D/H/N → `ALIGN_GGML_BOUNDS=-7`; (3) checked D*H, then *N, then *4, then *2; (4) exact stage length; (5) complete K then V source-range bounds; (6) plane/stage lengths fitting SIZE_MAX; (7) whole plane/stage pointer extents fitting UINTPTR_MAX; (8) base pointer arithmetic; (9) stage overlap with either used source span. No byte read/write occurs before all checks pass. No new refusal, alignment requirement or post-write failure. Success remains zero. |
| Exact alias contract | Destination `[stage,stage+2B)` must not overlap either used source span `[plane+k_base,plane+k_base+B)` or `[plane+v_base,plane+v_base+B)`. Preserve allowed touching endpoints, overlapping K/V source spans, and a stage placed in unused plane storage when it is disjoint from both used source spans. Do not strengthen this to a ban on overlap with the entire plane allocation. Both used source spans remain unchanged; with a distinct stage allocation, the whole plane remains unchanged. |
| Write order/ownership | Complete unchanged K copying before V begins. All validation precedes the first K write. V's internal tile write order may change because the call exposes no partial-result callback and admits no source/destination overlap; its final byte image remains identical. No heap/stack scratch array, native owner, thread, callback, retained pointer, file or allocation is added. SIMD locals are values. Existing invocation/layer buffers and teardown remain authoritative. |
| AArch64 path | Use existing `#if defined(__aarch64__)` capability and already included `<arm_neon.h>`. Load through `vld1q_u8(const unsigned char*)`, reinterpret to uint32 lanes, use the shipped exact-safe comparison's `vtrnq_u32` plus `vtrn1q_u64`/`vtrn2q_u64` shuffle sequence, and store through `vst1q_u8(unsigned char*, vreinterpretq_u8_u32(...))`. No cast to uint32_t*/uint64_t*/float*, aligned typed dereference, or strengthened alignment precondition. The four load/store sequences can remain local to the V block, avoiding changes to the comparison helper. |
| Fallback/tails | Full tiles cover `D4=D-D%4`, `N4=N-N%4`. For each tiled group of four lanes, copy columns N4..N-1 for all four lanes with existing four-byte memcpy semantics; afterward copy lanes D4..D-1 across all columns. These three regions partition every (head,lane,column) exactly once. If D<4 or N<4, tails cover all values without vector access. Non-AArch64 retains the complete original V head/lane/column scalar implementation under the other conditional branch. No runtime dispatch flag. |
| Source rationale | Item 68 already ships an unaligned-safe AArch64 4-by-4 exact V comparison using integer lane transposes. This candidate applies the same shuffle to the inverse data direction and stores the result. It does not alter that comparison or add an arithmetic/model kernel. The item-58 ABI, allocation and failure contract remain; this ledger supersedes only its AArch64 V implementation row if the candidate ships. |
| Qualification CLI | New `scripts/run-olmoe-native-staging-boundary`; no arguments runs the opt-in fixed-host comparison, `--self-test` runs the model-free source/record/gate owner. Unknown arguments reject. Missing prerequisites produce one declared N/A line and no complete result. Reuse validated item-75 pairing machinery without importing its removed production or its terminal publication restriction. |
| Two source/build identities | Control A is an immutable tracked snapshot of `d32d3cbc2939e1525f452056e8e720946930d4df`; candidate B is an independently materialized tracked snapshot of exact current clean HEAD. Build both isolated temporary trees with identical helper/driver entry bytes, pinned Align compiler/runtime, C compiler/version/flags, ggml libraries/consumed headers and linker inputs. Each tree owns and hashes its own helper and shim. No shared root executable, source-switch macro or runtime candidate flag. |
| Allowed source delta | Sorted per-arm `path,bytes,sha256` manifests cover all tracked `src/*.align`, both shim files, build script and `.align-revision`. Only the two declared C paths may differ, and both must contain the same shared-contract edit. All other compiled/helper/build bytes equal control. Independently pin actual consumed Python dependencies and new owner/fixture; bind own runner bytes to clean HEAD and recheck them. Structural owner verifies the validation prefix, K loop, scalar fallback and unchanged comparison against control. |
| Helper-hash equality | Record and validate both independently produced `helper_sha256` values but **permit them to be equal**: all Align/helper source is unchanged in this C-only intervention. Require distinct evaluated source revision/tree and shim identity, plus the exact declared source delta. Do not copy item 75's requirement that helper hashes differ. |
| Fixed workload/state | Inherit item 76's pinned OLMoE model/pack/geometry/server/task/system/user prompt, Align revision `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`, compiler/runtime and host. Seed 5; temperature 300000 micros; maximum 128; terminal EOG; cache budget 975175680 bytes; exact 87-id chain, 86 completion tokens, output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52`. Every full record retains 11940 cache requests, 7325 hits, 4615 misses, 4376 evictions, 17656872960 fetched bytes and zero cache-to-claim copies. |
| Pairs/isolation | Four contemporaneous pairs run chronologically `AB,BA,AB,BA`. Each arm leg independently performs fresh-process short-2 then fresh-process full-128: eight legs, sixteen requests total. Each short equals its own full prefix. Before short, between short/full and after full, record absence of processes matching pinned model/server: 24 checks. Validate each short/full record's native contexts, buffers, backends, allocators and resident-wrap balance and release-before-owner-scope-end evidence. |
| Measured metric | Complete parent-measured `full_helper_wall_ns`, containing helper `phases.elapsed_ns`, is the named secondary metric. Per-pair gain is control_i minus candidate_i. Median of four signed integers is floor of the sorted middle-pair sum divided by two, including negative gains. No timing aggregate follows semantic, cache, isolation, identity or lifetime failure. The item-76 native wall is eligibility evidence only; it is not the gate denominator. |
| Shipping gate | `required_gain_ns=max(871174011,ceil(control_median_ns*50000/1000000))`. `MET` iff all four paired gains are strictly positive, median paired gain is at least required_gain_ns, and candidate full-helper median is at most 16552306197 ns. Zero is not positive. The absolute ceiling is immutable item-68 median 17423480208 minus floor 871174011; current control and diagnostic medians never reset it. Otherwise an exact completed comparison records `NOT_MET`. |
| Result format | Exact-key schema 1, `kind="R8_OLMOE_NATIVE_STAGING_BOUNDARY"`; one complete JSON on stdout only after successful cleanup; concise stderr summary. Top-level keys: `schema_version,kind,control,candidate,boundary,fixed_request,environment,pair_order,pairs,aggregate,decision,elapsed_ns`. Exact nested shapes below. Integers reject booleans and out-of-i64 values; clocks are nonnegative, full walls positive, gains signed. Elapsed must contain all eight full walls and not exceed 480000000000 ns. |
| Identity/validation/ceiling | One monotonic eight-minute ceiling includes both builds, sixteen requests, validation, final identity checks and cleanup. Order: arguments/prerequisites; fixed/source contracts; scrubbed environment/linker inputs; host, clean head, ancestry, process absence and external identities; isolated exact builds; ordered requests; records/output/cache/lifetimes/accounting/repeatability; aggregate; final source/head/external checks; owned child/temp cleanup; elapsed ceiling; publication. Use item 76's strict actual helper/task JSON parsing and invocation-owned process groups, including descendants, launch races, timeout, signal and forced-termination cleanup; do not inherit item 75's immediate-child-only cleanup. Restore any scoped delegation/handlers. Duplicate-key, malformed or multiple JSON, mutation, contamination, timeout, signal, child failure, cleanup failure or excess returns nonzero without a complete result. |
| Ancestry/integration | `d32d3cbc2939e1525f452056e8e720946930d4df` must be an ancestor of evaluated candidate and final merging HEAD; evaluated candidate must remain an ancestor of publication/merged HEAD even after rejection/removal. Merge integration only; no squash/rebase. Resolve one Git common directory, disable replacements, reject replacement refs/grafts and validate ancestry from the exact merging head. Ordinary clones and linked worktrees are supported. |
| Terminal behavior | `MET` retains only declared production changes with passing owners/evidence and records the next roadmap decision. `NOT_MET` restores both production C files exactly to control and removes `scripts/test-olmoe-native-staging` plus `scripts/fixtures/olmoe-native-staging-native.c`; retain this ledger, immutable result and qualifier with publication-only self-test/replay-at-evaluated-head behavior. Semantic drift similarly removes the candidate and publishes no fabricated timing aggregate. No unchanged rerun or addition of priming/K/graph work rescues a miss inside this capability. |
| Persisted state/classification | No production persisted/cache/model/provider format change; stdout is caller-owned evidence. Application-owned native byte transfer at an existing boundary; shipped Align views, scalar FFI and Result suffice. No Align request, pin change, ggml tensor API, new floating-point kernel or aggregate member. Cross-host/GPU/throughput/time-to-passing-patch claims are N/A. |

## Exact tile and range formulas

All symbols below refer to nonnegative values after the unchanged validator succeeds. For
`0<=h<H`, `0<=c<N`, `0<=l<D`, the scalar reference is:

```text
K source = k_base + 4*((c*H+h)*D+l)
K target =          4*((h*N+c)*D+l)
V source = v_base + 4*((c*H+h)*D+l)
V target = B      + 4*((h*D+l)*N+c)
```

For each `h`, `l=0,4,...,D4-4`, `c=0,4,...,N4-4`, let
`S=v_base+4*((c*H+h)*D+l)`, `T=B+4*((h*D+l)*N+c)`, `RS=4*H*D`, `RT=4*N`.
Load four 16-byte vectors from `source+S+i*RS`, i=0..3. Each is four adjacent lanes for
one token column. Transpose the four-by-four uint32 lane matrix using the already shipped
shuffle sequence; output vector j contains columns c..c+3 of lane l+j. Store its exact 16 bytes
to `destination+T+j*RT`, j=0..3. Input is canonical plane and output is stage, the inverse
direction of the comparison's transpose. Do not copy the comparison's source/destination strides.

Every vector load stays inside four validated lanes of one source column; every vector store
stays inside four validated columns of one destination lane. The checked total B and valid tile
indices bound all offset products and additions inside the already validated used source/stage
spans. Do not round extents upward, read padding, use typed aligned pointers, or skip scalar tails.
Preserve K-before-V completion, all existing validation precedence and all admitted alias cases.
The existing AArch64 comparison remains byte-identical, including scalar mismatch-priority fallback.

## Exact evidence records

`control` and `candidate` have keys `align_llm_head,source_tree,source_files,helper_sha256,shim_sha256`.
Manifest rows are sorted repository-relative `path,bytes,sha256` records. The two helpers are built
independently even if their bytes match; the two source trees and shims must differ as declared.

`boundary` has exactly:

```json
{"native_symbol":"align_ggml_stage_kv","changed_region":"V_TRANSPOSE","tile_lanes":4,"tile_columns":4,"fast_path":"AARCH64_NEON_BYTE_LOAD_STORE","fallback":"SCALAR","k_copy":"UNCHANGED","validation":"UNCHANGED","priming":"UNCHANGED","execution":"NORMAL_UNSPLIT_PHASE_A"}
```

`fixed_request` inherits item 75's exact keys/values (`model_bytes,model_sha256,pack_sha256,
geometry_sha256,server_sha256,align_revision,compiler_sha256,ggml_libraries,ggml_headers,task_id,
task_sha256,prompt_sha256,maximum_tokens,temperature_micros,seed,cache_budget_bytes,
full_output_sha256`) and adds `runtime_sha256` fixed to item 76's
`7a36c1eb075b74b7c61a5d7ed229d684e5759fce2f35d32455e07bbad5aba38f`.
`environment` retains item 75's exact host fingerprint, C compiler/version and linker-search
shape/identities. Source dependency hashes are refreshed for this owner rather than checked against
obsolete historical source manifests. Inherited helper semantic validators remain authoritative.

`pair_order` is exactly `["AB","BA","AB","BA"]`. Each pair has `index,order,control,candidate,gain_ns`;
each arm leg has `short,full,full_helper_wall_ns,isolation`, using the existing exact item-68 helper
schema and 3-check isolation representation. `aggregate` has exactly
`control_values_ns,candidate_values_ns,paired_gains_ns,control_median_ns,candidate_median_ns,
median_gain_ns,positive_pairs,required_gain_ns,historical_ceiling_ns,gain_ppm`.
`gain_ppm=floor(median_gain_ns*1000000/control_median_ns)`. The four gain values and every aggregate
are independently recomputed; `decision` follows only the precommitted gate above.

## Closure matrix and native owner

New focused owner `scripts/test-olmoe-native-staging` uses
`scripts/fixtures/olmoe-native-staging-native.c`, an independent scalar byte-layout oracle calling
the actual exported stage function. It must not derive expected bytes through the candidate's
shuffle helper. No arguments builds strict unavailable-stub and engine-stub flavors and runs the
same direct vectors against both; `--real` builds/runs against configured pinned ggml headers/libs;
`--real --ubsan` checks the real native boundary with undefined-behavior instrumentation and
nonrecovering sanitizer errors. Unknown flags reject. Tests own only temporary build artifacts.
All three ordinary C flavors use C11, `-Wall -Wextra -Werror`, and existing contraction-off flags.
The owner asserts exact equality of the real/stub shared-marker region. No new aggregate membership.

| Owner/path | Construction/success | Malformed/failure/early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- |
| Shared source/unchanged region | Only V block changes; real/stub edit identical; comparison, validation and K copy unchanged | Undeclared source, helper/build change or shared-region drift rejected | No product resources added | Native owner `shared_region_identity`, `unchanged_validation_k_and_compare`; qualifier `declared_source_delta` |
| K bytes and V tile | Unequal D/H/N; D=N=4; multiple complete tiles; H=1 and H>1; K reference unchanged | Any byte mismatch fails the owner | Owned native test allocations released | `legacy_d2_h2_n3`, `tile4_exact`, `multihead_multitile`, `k_block_copy_unchanged` |
| Tail/edge partition | D/N in 1,3,4,5,8,9; cover no full tile, lane tail, column tail and both tails; every destination byte matches independent reference | Missing or out-of-range writes are detected by exact byte images and guards; exactly-once coverage follows from source inspection of the three nonoverlapping loop regions | Same | `no_tile_edges`, `lane_tail`, `column_tail`, `both_tails`, `tile_boundary_shapes` |
| Bit/unaligned ABI | Distinct patterns include +0/-0, min/max subnormal, normal extrema, +/-infinity, quiet/signaling NaN payloads and arbitrary uint32 bits | Any normalization or alignment UB rejects | No borrowed owner escapes | `special_bits_exact`, `unaligned_source_and_stage` (all source/stage byte offsets 0..15 on a multihead 5x5 vector); real ARM UBSan |
| Exact range ownership | Guard bytes around both source windows/stage; source unchanged; exact tile/tail endpoints at protected-page boundaries | Overread, overwrite and cross-head/row access fail, including SIMD paths | Test mmap/allocation owners always released | `guarded_tile_bounds`, `guarded_tail_bounds`, `source_unchanged`, `stage_sentinels` |
| Admission and refusal | Positive geometry and exact stage length; used source ranges may overlap each other; touching destination endpoints and unused-plane destination admitted | Null plane/stage dominates bad scalars; negative lengths/bases, nonpositive D/H/N, every multiplication stage overflow, exact-length mismatch, K/V OOB, SIZE_MAX/pointer overflow and used-span overlap → original code before any write | No allocation/work on rejected native call | `null_precedence`, `scalar_bounds`, `product_overflow`, `stage_exact_size`, `source_bounds`, `pointer_extent`, `source_overlap_allowed`, `touching_endpoints_allowed`, `stage_in_unused_plane_allowed`, `destination_overlap_refused`; sentinel unchanged after every refusal; SIZE_MAX-only cases N/A on 64-bit when unreachable from signed i64 |
| Architecture fallback | Actual AArch64 builds exercise SIMD and tails; non-AArch64 retains scalar code and same vectors | No test-only product dispatch override or unsupported intrinsic leakage | Same call-level ownership | Strict real/stub C builds; `scalar_reference_parity`; normal hosted non-AArch64 focused execution when available, with host evidence stated |
| Existing decode consumers | Ordinary and item-76 APIs preserve output/graph/cache evidence; item-73 core topology/order remains exact | First/late staging/compute refusal keeps existing labels and no failed-step commit | Existing native lifetime equations/teardown | Unchanged `scripts/test-olmoe-plane-upload`, `scripts/test-olmoe-attention-core`; `make layer-forward-smoke`; `make runtime-provider-smoke` |
| Source/build identities | Two exact snapshots; same helper source/compiler/runtime; separate actual builds/hashes | Undeclared delta, altered pin/host/library/header/source or wrong ancestry rejected; equal helper hashes alone accepted | Both temporary builds removed | Qualifier self-test `equal_helper_hashes_allowed`, `same_shim_rejected`, `manifest_delta`, `source_mutation`, `ancestry_linked_worktree`, `inherited_identity` |
| Pair semantics/gate | Chronological AB/BA/AB/BA, independent short prefixes, exact output/cache/lifetimes, 24 isolation checks | Bad order/count/prefix/cache/lifetime/isolation prevents timing aggregate; zero/negative gain, insufficient relative/absolute gain and ceiling excess produce NOT_MET | Every child reaped | Qualifier `pair_order_and_conditioning`, `inherited_semantic_rejections`, `all_four_positive`, `signed_median_floor`, `absolute_and_relative_floor`, `historical_ceiling`, `gate_boundaries`; complete real 16-request comparison |
| Publication/removal | Final head/source/external identities and aggregate revalidated; exact C restoration/removal after NOT_MET | Malformed result, signal/child/timeout/cleanup failure, late deadline, restoration drift or missing evaluated ancestry prevents publication | Cleanup before final elapsed check; no surviving temp/child | Qualifier `strict_json_and_process_groups`, `cleanup_failure_no_document`, `cleanup_inclusive_ceiling`, `terminal_restoration_and_removal`, `evaluated_ancestry`; final owner self-test and exact-head preflight |

Acceptance: the three focused native commands above; existing plane-upload/core/layer/provider
owners; Python compilation and qualifier `--self-test`; both exact helper/shim builds and the
clean-head 16-request qualification; `git diff --check`; terminal restoration checks if required;
one comprehensive review of the stable candidate with measurement/unaligned-memory risk; and
exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-NATIVE-STAGING-BOUNDARY -- scripts/run-olmoe-native-staging-boundary --self-test`.
No Align source changes means source formatting and another standalone Align type-check are N/A;
the required exact helper builds and existing consumer owners still validate the pinned graph.
No `make ci`, extra portfolio run, generic stress suite, new standalone graph qualification or
separate pre-implementation review is selected. Real fixed-request qualification owns exact cache
and native-lifetime behavior; the focused direct test owns the changed byte-transfer boundary.

The ledger and matrix agree on one existing scalar ABI, two changed C files, K/validation/comparison
preservation, unaligned-safe vector accesses, complete tails, scalar platform fallback, and the
strict full-request gate. Existing Requests 35/38 remain unrelated nonblocking public-buffer gaps;
this byte-transfer implementation neither consumes a proposed Align API nor requires a new gap.

This capability keeps the native transfer change, direct bit/layout owner, paired consumer gate and
terminal restoration together. Splitting them would expose a dormant or unqualified native change
and duplicate exact-source/byte-ownership proof without an independently useful consumer.

## Candidate verification checkpoint

The only production delta is the declared 67-line AArch64 V branch in each shim. The direct owner
reconstructs both complete control files by replacing the new conditional block with its retained
scalar branch, proving the validation, K copy, comparison and other native bytes unchanged.
The tile, column-tail and lane-tail index ranges are disjoint and cover the scalar domain; this
source inspection owns exactly-once coverage, while runtime images and guards own byte/range parity.

All three native owner commands passed on the pinned Apple M1 host: default strict unavailable and
engine flavors, `--real`, and `--real --ubsan`. These exercised actual AArch64 SIMD/tails and the
separately compiled immutable scalar control. Non-AArch64 dispatch execution is N/A locally;
this focused owner is not reached by ordinary hosted CI. The original fallback is byte-identical.
The 72 dimension vectors, 256 source/stage offset combinations, special and position-dependent
bit patterns, protected pages, source immutability, alias admission and refusal cases all passed.

Unchanged `scripts/test-olmoe-plane-upload`, `scripts/test-olmoe-attention-core`,
`gmake layer-forward-smoke` (77.317 seconds) and `gmake runtime-provider-smoke`
(sampler vectors plus 61 CLI assertions) passed. Strict C11 warning-as-error compilation passed
for unavailable, engine and real flavors. Python compilation and `git diff --check` passed.
`scripts/run-olmoe-native-staging-boundary --self-test` passed with 129 current source pins
(102 Align and 27 other inputs), including actual dispatch/strict JSON, paired gate boundaries,
equal helper hashes, mutation refusal, linked-worktree ancestry, process groups and terminal cleanup.
The clean-head paired qualification passed below; stable-candidate comprehensive review remains pending.


## Measured result and next consumer

Clean evaluated head `3fb3f11f677d07e02693801a6eff3e405a670858` completed in
183,452,238,333 ns. Control was exact merged head
`d32d3cbc2939e1525f452056e8e720946930d4df`; both independently built helpers and shims were
hashed, all declared source/toolchain/host identities passed before and after execution, and all
sixteen fresh requests and 24 pair isolation checks passed. Every full output and 87-id chain,
86 completion tokens, exact cache counts/fetched bytes, zero cache-to-claim copies and native
lifetime equations matched. No result was omitted or retried.

| Pair/order | Control full wall (ns) | Candidate full wall (ns) | Paired saving (ns) |
| --- | ---: | ---: | ---: |
| 1 / AB | 14,113,690,708 | 13,977,930,667 | 135,760,041 |
| 2 / BA | 15,609,164,208 | 14,152,154,541 | 1,457,009,667 |
| 3 / AB | 15,871,141,083 | 15,101,142,250 | 769,998,833 |
| 4 / BA | 16,562,474,500 | 15,236,774,250 | 1,325,700,250 |

Control median is **15,740,152,645 ns** and candidate median **14,626,648,395 ns**. Median
paired saving is **1,047,849,541 ns / 66,571 ppm**, with **four positive pairs**, exceeding
required **871,174,011 ns**. Candidate median is below the immutable **16,552,306,197-ns**
ceiling. The exact precommitted decision is **MET**. This is a fixed-host, fixed-request secondary
metric result; no primary-metric, cross-host or V-only cost claim follows from it.

Keep the two declared native changes and direct owner/fixture. All Align/helper/build/pin bytes
remain unchanged. Complete original raw JSON is **73,695 bytes**, SHA-256
`0ec1732dd6f13ce81ac95925e08062cfdc2ac7c9431d47dd23fb4098ed439c65`, to be preserved and
retrieved/hash-verified in the pull request. The runner records the evaluated ancestor and retains
current-source self-tests; merge integration must preserve both named ancestors.

Item 78 now owns a current-source remeasurement of item 69's sampled provider portfolio and
**time to a passing patch** against the isolated local server. It refreshes the actual source/runtime
closure and server/validator cleanup while keeping that primary protocol and shipping gate.
This item's nanosecond floor and absolute helper ceiling do not transfer to the primary decision.

The bounded retrospective is that keeping the existing byte ABI while changing only the exact
transpose produced a passing complete-request improvement after the two graph-copy candidates
failed. Balanced contemporary controls remain necessary: pair gains range from 135.760 to
1,457.010 milliseconds. Preserve this evidence and existing gate; no new routine aggregate is added.
