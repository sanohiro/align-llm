# R8 OLMoE V preparation boundary

Status: complete; `NOT_MET`, production removed before publication, 2026-09-05.
Roadmap owner: `R8-OLMOE-V-PREPARATION-BOUNDARY` (item 75).
Control revision: `36183a342d2f87bcf153dfd1d347d38efc08b9a1`.

Item 73 measured `VALUE_PREPARATION` rows 21–24 at 988,706,344 ns, above the inherited
871,174,011-ns eligibility floor. Item 74's K candidate preserved semantics but produced only two
positive paired gains and a 3,851,438-ns median saving, so its production was removed. This
capability selects V alone: replace only rows 23/24 with separate CPU custom concat/pad nodes.
Rows 21/22, every K operation, full width, source order and marked outputs remain exact. The
four-row diagnostic duration is not an estimate of removable copy cost. The evaluated intervention
combines bulk row copies and one active copy worker; its result cannot attribute savings to either
part separately. No K operation is restored and no live-width intervention is reopened.

The following ledger records the evaluated candidate at
`248e2314ebbb429e4027c5cb249e680a15cec310`. Its V operations, native ABI and native fixture
are removed from the publication tree. The retained runner is self-test-only here and names that
evaluated ancestor for real replay. The terminal evidence below owns the final decision.

## Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Consumer/owner | Normal OLMoE CPU decode, including the existing sampled provider. Production owners are `src/layer_olmoe.align`, `src/moe_decode_step.align`, `src/ggml_ffi.align`, `scripts/ggml_shim.c`, and `scripts/ggml_shim_stub.c`. No runtime experiment flag, alternate generation entry or global thread change. |
| Public operation identifiers | Add `layer_olmoe.OP_V_CONCAT_F32 := 19` and `OP_V_PAD_F32 := 20`. Values 17/18 are left unused: item 74 used them for evaluated K operations, and distinct values avoid conflating historical source/evidence vocabulary. These table integers are not a persisted/wire format; this choice adds no K symbols or compatibility aliases. Generic `OP_CONCAT=16` and `OP_PAD=15` remain unchanged. |
| Exact table delta | In the decode phase-A table replace row 23's op only and row 24's op only. Row 23 retains `a=MM_SLOT_VPAST`, `b=MM_A_NODE_BASE+22`, `p0=0`, `when=WHEN_DECODE`. Row 24 retains its original source `MM_A_NODE_BASE+22`, `p0=width-(n_past+1)`, `alt_when=WHEN_DECODE`, `alt_a=MM_A_NODE_BASE+23`. Every other column/slot/condition and all 37 row identities remain exact. The dedicated V operations fix column axis 0. |
| Construction/dispatch | `build_decode_nodes` calls the exact wrappers below, passing row 24's padding from `p0`. Each wrapper calls shipped `ggml_custom_4d` exactly once and stores one result tensor/node. Row 24 still constructs a separate node when padding is zero. Rows 21/22 and prefill tables stay unchanged. Shapes, source dependencies, graph traversal/node counts and output marks stay exact; the two actual ggml op kinds become `GGML_OP_CUSTOM`. |
| V concat result | F32 `past={N,D,H,1}` and `current={1,D,H,1}` produce `{N+1,D,H,1}`. For each flattened row `r=h*D+d`, copy exactly `4*N` bytes from `past+r*4*N` to `dst+r*4*(N+1)`, then exactly four bytes from `current+r*4` into that destination row's last column. No float load, arithmetic, conversion, finite filtering or padded source read. K's per-head plane offsets do not apply to V. |
| V pad result | F32 source `{L,D,H,1}` and padding `P` produce `{L+P,D,H,1}`. For each row `r`, copy `4*L` leading bytes from `source+r*4*L` to `dst+r*4*(L+P)` and zero exactly `4*P` trailing bytes. `P=0` still constructs a separate node and copies the input. Preserve every copied F32 bit, including signed zero, subnormals, infinities and NaN payloads; appended zeros have positive-zero bits. |
| Numeric/size domain | Require F32, `D>0,H>0`, `N>=1`, `L>=1`, `0<=P<=4096`, every input/final column count `<=4096`, and `ne3=1`. Concat therefore admits past `N<=4095`. Check every sum/product against `INT64_MAX` and `SIZE_MAX` before using it; input and result element counts must be `<=ALIGN_GGML_MAX_PAD_ELEMENTS=16777216`. Use `unsigned char *`, `memcpy`, and `memset`; no four-byte data-pointer alignment precondition. |
| Exact layout | For each source/result `{C,D,H,1}`, require `nb0=4`, `nb1=4*C`, `nb2=4*C*D`, `nb3=4*C*D*H`, and `ggml_nbytes==4*C*D*H`, including singleton dimensions. Concat requires current columns exactly 1 and matching D/H. Validate result type, all dimensions, exact strides and extent before storing its handle. Row 22 supplies the canonical current-V strides; row 21 alone is not an admitted replacement. |
| Constructor validation/errors | Order: (1) nonnull context (`R5_GGML_INIT` if absent), then valid slot-store magic/capacity, in-range output/input slots, present inputs and output slot distinct from each input (`R5_SLOT`); (2) every input F32 type (`R5_TYPE_UNSUPPORTED`); (3) positive dimensions, fixed axes, compatible D/H and padding bounds; (4) checked arithmetic, width/element caps and exact strides/extents; (5) one custom constructor (`R5_GGML_INIT` if null); (6) exact result metadata, then slot store. Steps 3/4/6 map to `R5_SHAPE` through existing `r5_result` and the original node label. A refused operation never overwrites the output slot. No validation-only heap allocation; metadata checks precede any ggml constructor that can abort. Stub engine matches precedence and actual custom-stride rejection; unavailable stub keeps existing unavailable behavior. |
| Callback dispatch | Static native callbacks have the shipped signature below and receive `userdata=NULL`. Pass `n_tasks=1` as a scheduling hint. ggml 0.21 can still invoke every graph worker: validate `nth>=1`, `0<=ith<nth`, and null userdata; workers `ith>0` return before reading even the tensor pointer or its bytes. Worker 0 validates tensor/storage invariants and loops over all `D*H` rows. No architecture-specific instructions or global backend thread policy change. |
| Ownership/allocation | ggml owns result metadata in the existing graph context and result storage in the existing phase-A gallocr. The constructor's local `args` array is copied into `result->src`; callbacks have static program lifetime and retain no local pointer/closure. No callback or ggml struct crosses Align FFI. No new heap, persistent state, intermediate buffer, source mutation, source/output alias, native owner or teardown path. Independent graph instances share callback code only. |
| Compute/storage failure | After successful existing gallocr allocation, worker 0 revalidates source/result F32 metadata, constructor-proven spans, host-visible allocated buffers, nonnull data and destination byte ranges distinct from each source (with checked pointer-range arithmetic). Unexpected task/metadata/storage invariants abort before byte access; `void` callbacks cannot emit a recoverable status. Existing compute-status failures remain `R5_COMPUTE` and converge on common teardown; no subsequent layer/step is committed. Constructors do not reject unallocated data pointers before graph allocation. |
| Observable invariants | Preserve exact K/V plane bytes, logits, routing/cache decisions, token ids/output, all accounting and native lifetime relations. Keep row 13's plane output and row 23's separately marked concat, readable after downstream work. Never fuse the two nodes. Row 25 retains its full-width reduction length. Normal execution stays unsplit. Item-71/72/73 diagnostic counts and memberships stay exact, including VALUE_PREPARATION before QK_PREPARATION in item 73; exposed row-23/24 descriptors become `V_CONCAT_F32`/`V_PAD_F32`. Every K and generic/prefill operation retains control behavior. |
| Capability classification | Application/native CPU graph operation. Existing pinned Align raw handles, typed scalar C FFI and `Result` suffice; no Align capability request or `.align-revision` change. GPU dispatch, cross-host performance and asynchronous callbacks are N/A. |
| Qualification CLI/owner | `scripts/run-olmoe-v-preparation-boundary` with no arguments runs the fixed-host comparison; `--self-test` runs the model-free record/identity/gate owner. Unknown arguments fail. Missing prerequisites emit exactly one declared N/A line and no result. Reuse item 74's measurement/schema controls without depending on its removed production or changing its retained replay contract. |
| Two exact builds | A/control is an immutable tracked-source snapshot of `36183a342d2f87bcf153dfd1d347d38efc08b9a1`; B/candidate is a tracked-source snapshot of current clean HEAD. Build both isolated temporary trees with unchanged entry `src/olmoe_exact_safe_decode_gate.align` and argument grammar. Each owns its helper/shim, separately hashed. Use the same pinned Align compiler/runtime, C compiler/version/flags, ggml libraries and all consumed headers. No shared root binary or implementation-switch macro. |
| Build/source identities | Independently pin every consumed Python/helper/source/build input and the focused owner, fixed model/pack/geometry/server, task/prompt/token chain, compiler/revision and inherited host fingerprint. Allowed compiled-source differences are exactly the five production owners above; all other compiled/helper/build bytes must equal control. Record sorted path/byte/hash manifests for each arm and every allowed difference; refuse undeclared source differences. The helper/driver entry bytes remain equal to control. Recheck current head/worktree, snapshots/manifests and external inputs after measurement. |
| Fixed request | Inherit item 73 byte-for-byte: exact model/pack/geometry/task/prompt, seed 5, temperature 300000 micros, maximum 128, terminal EOG, 975175680-byte cache, 87-id chain, 86 completion tokens and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52`. Every full record retains 11940 cache requests, 7325 hits, 4615 misses, 4376 evictions, 17656872960 fetched bytes and zero cache-to-claim copies. |
| Pair/order/isolation | Four contemporaneous arm pairs run chronologically `AB, BA, AB, BA`. Each arm leg has its own fresh-process short-2 request immediately followed by its own fresh-process full-128 request: eight independent conditioning/full legs, sixteen requests. Each short output equals that leg's full prefix. Require zero matching pinned model/server processes before short, between short/full, and after full for each leg: 24 checks. Each record and short/full pair retains native lifetime validation. Both arms execute normal unsplit phase A. |
| Measurement | For pair i, `gain_i=control_i-candidate_i`, using complete subprocess `full_helper_wall_ns` measured by the same parent monotonic boundary in both arms and containing helper `phases.elapsed_ns`. Chronological order is recorded separately from arm arrays. Median of four integers is floor of the sum of sorted middle values divided by two, including negative gains. No aggregate follows semantic/cache/lifetime/identity/isolation failure. This is the named complete-request secondary project metric, not time-to-passing-patch evidence. |
| Shipping gate | Unchanged from item 74: `required_gain_ns=max(871174011, ceil(control_median_ns*50000/1000000))`. `MET` requires all four paired gains strictly positive, median paired gain `>=required_gain_ns`, and candidate median `<=16552306197`. Zero is not positive. The ceiling remains item 68's 17423480208-ns median minus its ceiling-rounded 871174011-ns floor. Current relative and historical absolute tests both apply; neither item 73's split time nor item 74's unsuccessful time resets the gate. |
| Result/schema | Exact-key schema-1 JSON with `kind="R8_OLMOE_V_PREPARATION_BOUNDARY"`, printed once to stdout only after successful cleanup; concise stderr summary. Top-level keys are `schema_version,kind,control,candidate,boundary,fixed_request,environment,pair_order,pairs,aggregate,decision,elapsed_ns`. Exact nested shapes are specified below and inherit item 74's strict validators. Reject boolean/out-of-range integers; gains admit signed i64, clocks nonnegative i64 and full walls positive. Final elapsed contains all eight full walls and is at most 480 seconds. |
| Cost/validation order | One monotonic eight-minute ceiling includes both builds, sixteen requests, validation/rechecks and cleanup. Order: arguments/prerequisites; inherited/source constants; environment/linker scrub; host/clean head/ancestry/process absence/external identity; two isolated builds; ordered pairs; records/output/cache/lifetimes/accounting/repeatability; aggregate; final source/head/external identity; child/snapshot cleanup; elapsed ceiling; publication. Timeout, signal, mutation, contamination, malformed record, cleanup failure or ceiling excess returns nonzero without a complete result. |
| Ancestry/integration | Control `36183a342d2f87bcf153dfd1d347d38efc08b9a1` must remain an ancestor of evaluated candidate and final merging HEAD. The evaluated candidate must remain an ancestor of publication/merged HEAD, including source-removal commits after `NOT_MET`. Merge commits only; refuse squash/rebase. Resolve one Git common directory, disable replacements, reject replacement refs/grafts, and verify both required ancestors from the exact merging head. Publish both source revisions with evidence. |
| Persisted state | No model/cache/provider/container format changes. Table ids are source-level symbols, not exchanged data. The runner persists no production state; stdout is caller-owned evidence. Source revisions/manifests identify reproducibility inputs. No model, machine-local path, credential or generated artifact enters Git. |
| Terminal decision | `MET` ships only the named candidate with passing owners/evidence. `NOT_MET` keeps this ledger, immutable evidence and qualification owner but removes every candidate production and candidate-only native/source owner change before publication. Restore the three candidate-only specification clarifications as well. Verify exact restored production/spec bytes against control and remove newly added candidate-only files. Publication mode is self-test-only and names the evaluated ancestor for real replay. Semantic drift similarly rejects/removes the candidate and emits no fabricated timing aggregate. |
| Acceptance | `make fmt`; narrow pinned helper type-check; strict real, engine-stub and unavailable-stub C builds; shared-region identity; native owner in stub, real and real UBSan modes; `scripts/test-olmoe-attention-core`; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation and runner self-test; clean-head paired qualification; restoration comparison if required; `git diff --check`; comprehensive stable-candidate review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-V-PREPARATION-BOUNDARY -- scripts/run-olmoe-v-preparation-boundary --self-test`. No new aggregate membership or `make ci`. |

## Exact ABI and source layout

```c
int32_t align_ggml_op_v_concat_f32(
    void *ctx, void *slots, int64_t out, int64_t past, int64_t current);
int32_t align_ggml_op_v_pad_f32(
    void *ctx, void *slots, int64_t out, int64_t source, int64_t padding_columns);
```

```align
pub fn op_v_concat_f32(
  ctx: raw, borrow slots: slice<u8>, out: i64, past: i64, current: i64, label: str,
) -> Result<(), Fault>
pub fn op_v_pad_f32(
  ctx: raw, borrow slots: slice<u8>, out: i64, source: i64, padding_columns: i64, label: str,
) -> Result<(), Fault>
```

Callbacks are `static void align_ggml_v_concat_f32(struct ggml_tensor *dst, int ith, int nth,
void *userdata)` and `static void align_ggml_v_pad_f32` with the same signature. Read source
pointers through `dst->src[0]`/`src[1]`; read public `type/ne/nb` and host-buffer metadata;
use `ggml_get_data`/`ggml_nbytes` for bytes/extents. No ggml struct/callback enters the C/Align ABI.

| Existing tensor | Dimensions | Byte strides |
| --- | --- | --- |
| Row 13 reshaped current V | `{D,H,1,1}` | `{4,4D,4DH,4DH}` |
| Row 21 `PERMUTE(1,2,0,3)` | `{1,D,H,1}` | `{4DH,4,4D,4DH}` |
| Row 22 `CONT_3D` | `{1,D,H,1}` | `{4,4,4D,4DH}` |
| VPAST | `{N,D,H,1}` | `{4,4N,4ND,4NDH}` |
| Row 23 result | `{N+1,D,H,1}` | exact contiguous V strides |
| Row 24 result | `{W,D,H,1}`, `W=N+1+P` | exact contiguous V strides |

`decode_layer_inputs` and `stage_kv` already provide the exact past-V layout. Upstream ggml
0.21's F32 [concat](https://github.com/ggml-org/ggml/blob/v0.21.0/src/ggml-cpu/ops.cpp#L2033)
and non-circular [pad](https://github.com/ggml-org/ggml/blob/v0.21.0/src/ggml-cpu/ops.cpp#L8061)
perform per-element selection/copy or zeroing; the proposed nodes preserve their admitted V
results with explicit byte copies. The shipped
[constructor](https://github.com/ggml-org/ggml/blob/v0.21.0/src/ggml.c#L6094) copies its source
array into the result. The [graph-worker dispatch](https://github.com/ggml-org/ggml/blob/v0.21.0/src/ggml-cpu/ggml-cpu.c#L3093)
requires the explicit idle-worker return even with `n_tasks=1`; native qualification covers it.

## Evaluated specification clarification (removed with the candidate)

Update `docs/specs/r5a-dense-layer-forward.md` section 1.3 to scope “No dequantization, no kernel”
to original R5A dense prefill and state that R8 item 75 separately authorizes two CPU byte-copy
custom nodes for OLMoE decode V concat/pad, with no dequantization or floating-point arithmetic
kernel. Preserve its one-op-per-wrapper rule and unchanged R5A graph/qualification. Clarify the
real shim's header rule 4 and `docs/specs/r4-5-external-buffer.md`/R5A references to admit only the
named callbacks' public metadata reads above, retaining accessor-based bytes/extents and existing
ownership. Update `docs/specs/r6-olmoe-decode.md` row-23/24 vocabulary to the new V identifiers,
with all semantic shapes/marks unchanged. These are V-only clarifications; do not restore item
74's K permissions or describe custom nodes as generic ggml CONCAT/PAD kernels.

## Closure matrix and owner map

The native owner is `scripts/test-olmoe-v-preparation`, backed by
`scripts/fixtures/olmoe-v-preparation-native.c`. No arguments exercises the engine stub;
`--real` uses configured pinned ggml include/libraries; `--real --ubsan` checks the same native
fixture for undefined behavior. Shared validators/byte helpers, if used, remain inside the
existing byte-identical shim contract region and are exercised through actual real/stub exported
constructors. The model-free runner self-test may invoke stub-native cases. Final source-diff inspection and the existing attention-core owner cover the table and mode
invariants; its source remains unchanged.

| Owner/path | Construction/success | Malformed/failure/early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- |
| Table and decode dispatch | rows 23/24 use V ops 19/20; correct p0/operands/conditions; all 37 rows, counts and normal-unsplit execution unchanged | changed K/prefill/row21/22 metadata, wrong axis/operand/condition or missing zero-pad node rejected | existing graph scope | final row-only source-diff inspection; existing `scripts/test-olmoe-attention-core` mode/order/count owner; layer smoke |
| Concat C/Align wrappers | unequal N/D/H, N=1 and N=4095; one/multiple heads and lanes; exact last column in every row | `vprep-concat-null-context`, `-slot-precedence`, `-out-alias`, `-type`, `-shape`, `-current-columns`, `-stride`, `-overflow`, `-cap`; output sentinel unchanged | no owned state on refusal | `vprep-concat-bits`, `vprep-concat-row-layout`, corresponding malformed cases; real/stub exported constructor parity |
| Pad C/Align wrappers | L>=1, P=0/1/maximum allowed by final width; every row's source/zero tail exact | `vprep-pad-null-context`, `-slot-precedence`, `-out-alias`, `-type`, `-shape`, `-negative`, `-width`, `-stride`, `-overflow`, `-cap`; output sentinel unchanged | same | `vprep-pad-bits`, `vprep-pad-zero-width-delta`, `vprep-pad-row-layout`, malformed cases; real/stub parity |
| Layout/byte boundary | canonical row22/VPAST layouts; singleton and unequal dimensions; copied bits include +/-0, subnormals, +/-inf, signaling/quiet NaN payloads | noncanonical singleton strides, corrupt source/result metadata, overlapping destination/source, mismatched declared extents or absent storage refused before byte access; no source mutation | no allocation or retained byte pointer | `vprep-special-bits`, `vprep-current-contiguous`, `vprep-unaligned-byte-kernel`, `vprep-sentinels`; real UBSan |
| Callback dispatch/lifetime | one active worker with a four-worker mixed native graph; constructor stores src pointers; stack overwrite after construction; static callbacks/null userdata | invalid ith/nth/userdata/null tensor/source/type/stride/data/host-buffer/alias abort before access; ith>0 with inaccessible dst returns safely | allocator/context own results until teardown | `vprep-task-count`, `vprep-idle-worker`, `vprep-callback-invariant`, `vprep-callback-lifetime`; real native/UBSan |
| Graph/output lifetime | real candidate concat/pad exactly match generic originals; distinct allocations; marked row23 remains readable after downstream consumers | null custom constructor, forced compute failures and late step failure produce no successful-step commit | existing contexts/allocators/buffers balance and free before Align owners | `vprep-original-graph-parity`, `vprep-marked-concat`, `vprep-init-failure`; existing attention-core six-slice/late-failure owner; tiny-model and real full outputs |
| Both shims and inherited provider | default unavailable behavior; engine/real agree on refused inputs; old forced CONCAT/PAD failures still reach owning errors; generic K and prefill exact | unsupported type, existing numerical/shape/cache/oracle errors retain owning precedence | unchanged common teardown | native owner; strict three-flavor C builds; shared-region identity; `make layer-forward-smoke`; `make runtime-provider-smoke`; attention-core owner |
| Exact builds/identity | immutable two-arm snapshots, same helper/toolchain/external inputs, independent hashes and allowed V-only delta | mutated source/header/library/helper; misbound arm; undeclared delta; wrong ancestry/replacements/grafts refused | terminate/reap children; remove each snapshot; root generated artifacts unchanged | `vprep-build-arm-binding`, `vprep-source-mutation`, `vprep-external-mutation`, `vprep-ancestry`, `vprep-root-unchanged`; exact build records |
| Paired measurements | AB BA AB BA, sixteen independently conditioned requests, 24 absence checks; exact prefix/cache/output/lifetime records | wrong order/index/count, wrong live-run arm binding/identity, malformed/boolean/overflow clocks and semantic drift refused | every child terminated/reaped | `vprep-pair-order`, `vprep-arm-schema`, `vprep-prefix`, `vprep-isolation`; inherited schema mutations |
| Gate/result | signed floor median, all four positive, equality at floor/ceiling passes; full subprocess timing contains internal elapsed | any zero/negative pair, one-ns floor/ceiling failure, clock containment failure, cleanup/time ceiling failure | no complete document until cleanup and elapsed validation | `vprep-signed-median`, `vprep-all-four-positive`, `vprep-gate-boundaries`, `vprep-cleanup-ceiling`; full paired result |
| Terminal source/publication | MET candidate or exact control restoration; both source ancestors retained | removed-candidate real mode refuses with evaluated ancestor; absent control/evaluated ancestry refuses | candidate-only owners/spec clarifications removed/restored; no generated artifact committed | `vprep-not-met-removal`, `vprep-publication-replay`, `vprep-post-merge-ancestry`; comprehensive review and exact-head preflight |

Generic callbacks from Align, asynchronous escape, source-nulling moves, shared mutable callback
state and GPU dispatch are N/A: callbacks are static synchronous native functions over CPU
graph-owned tensors. Independent graphs may execute separately without sharing mutable state.
Every applicable matrix cell must map to passing final evidence before review; no measurement results are
claimed before qualification.

## Exact evidence records

`control` and `candidate` have exact keys `align_llm_head,source_tree,source_files,helper_sha256,
shim_sha256`. `source_files` is path-sorted rows with `path,bytes,sha256`, covering all tracked
`src/*.align`, both shim sources, `scripts/build-ggml-shim`, and `.align-revision` in each snapshot.
Records contain repository-relative paths only. Independently pin the imported Python chain and
hash the runner and focused regression owners before/after the run. Both source identities are
actual snapshots, never alternate labels for one shared build.

`boundary` is exactly `concat_row=23,pad_row=24,concat_op=V_CONCAT_F32,pad_op=V_PAD_F32,
callback_tasks=1,execution=NORMAL_UNSPLIT_PHASE_A`. `callback_tasks` records the constructor hint,
not the number of callback invocations. `fixed_request` has exact keys
`model_bytes,model_sha256,pack_sha256,geometry_sha256,server_sha256,align_revision,compiler_sha256,
ggml_libraries,ggml_headers,task_id,task_sha256,prompt_sha256,maximum_tokens,temperature_micros,
seed,cache_budget_bytes,full_output_sha256`. `environment` retains item 73/74's exact inherited
host/C-compiler/linker fingerprint keys and validation. External record shapes remain unchanged.

`pair_order` is exactly `[AB,BA,AB,BA]`. Each `pairs` member has exact keys
`index,order,control,candidate,gain_ns`; its indexed order matches `pair_order`. Each arm leg has
`short,full,full_helper_wall_ns,isolation`; short/full are unchanged exact
`olmoe_exact_safe_decode_gate` records validated by the original owner, and isolation is exactly
`matching_before=0,matching_between=0,matching_after=0`. Live execution binds each leg to its built
helper/shim/library identities. Caller-owned JSON is evidence rather than a cryptographic
execution attestation; identical valid payloads alone cannot authenticate their origin. No helper
arm tag or measurement-path change is introduced.

`aggregate` has exact keys `control_values_ns,candidate_values_ns,paired_gains_ns,control_median_ns,
candidate_median_ns,median_gain_ns,positive_pairs,required_gain_ns,historical_ceiling_ns,gain_ppm`.
`gain_ppm=floor(median_gain_ns*1000000/control_median_ns)`. `decision` is exactly `MET` or
`NOT_MET`; incomplete/malformed measurements emit neither. Schema version remains 1 for this new
artifact kind. The full result and evaluated source identity are recorded before terminal handling.

The author ledger-to-prose consistency pass confirms the V axis/strides, row23/24 table changes,
scalar FFI, worker dispatch, exact source inventory and paired gate agree. No K source is adopted.

## Evaluated implementation checkpoint

At the evaluated ancestor, the five production owners implement only the V concat/pad operations
and scalar FFI. The native/Align evidence in this section belongs to that checkpoint. The final
source-diff inspection confirms rows 23/24 change only their operation identifiers; every operand,
condition, source, width, K/prefill operation and row21/22 remains intact.

The pinned helper per-unit check passed 17 units. Real, engine-stub and unavailable-stub C builds
passed with warnings as errors; the shared contract region is byte-identical. `gmake fmt`,
`scripts/test-olmoe-attention-core` (exact source order/output, all existing modes, six compute
failures, late failure, selection refusal and lifetime balance), `gmake layer-forward-smoke`
(193.931 seconds), and `gmake runtime-provider-smoke` (sampler vectors and 61 CLI assertions) passed.
The native owner passed stub, `--real`, and `--real --ubsan`, including actual PERMUTE/CONT input
construction, exact generic-op parity, special-value bits, width/element caps, refusal precedence,
four-worker dispatch, 26 callback invariant faults and lifetime/sentinel checks. Raw row21's
noncanonical singleton strides are tested with real ggml; the stub's materializing permutation is
not represented as identical metadata behavior. Separate native graph materialization chains avoid
assuming that the stub deduplicates shared computed nodes across separate graph expansions.

Python compilation, the paired runner self-test and exact control snapshot inventory checks passed.
The terminal fixed-host result follows. These owner checks establish exact semantics; they do
not establish a performance improvement. Preserve the complete raw result in retrievable PR
evidence and verify its decoded bytes/hash before publication completes.

## Terminal paired evidence and disposition

The clean-head qualification at `248e2314ebbb429e4027c5cb249e680a15cec310` completed sixteen
requests and twenty-four isolation records in 192,761,384,792 ns. Control is the immutable item-74
merge `36183a342d2f87bcf153dfd1d347d38efc08b9a1`. Both isolated normal-mode builds used the
same exact toolchain, ggml headers/libraries, C compiler, model/pack/geometry, prompt and host
fingerprint. Every exact output/token/hash, cache accounting, native lifetime, source/external
identity, isolation and cleanup boundary passed. Raw schema-1 record SHA-256:
`90ec26172c3ce7205fef855fadcacb02fa11aaab435698d21d2eaea87eba5057` (73,240 bytes).

| Pair | Order | Control full wall (ns) | Candidate full wall (ns) | Paired saving (ns) |
| --- | --- | ---: | ---: | ---: |
| 1 | AB | 15458388000 | 16168868125 | -710480125 |
| 2 | BA | 17107525625 | 16613487958 | 494037667 |
| 3 | AB | 17248785542 | 17554601042 | -305815500 |
| 4 | BA | 17615545166 | 17341640291 | 273904875 |

Control and candidate medians were 17,178,155,583 ns and 16,977,564,124 ns. Median paired saving
was **-15,955,313 ns / -929 ppm**, below the unchanged 871,174,011-ns required saving. Only two
pairs improved, and candidate median exceeded the immutable 16,552,306,197-ns ceiling. The result
is **`NOT_MET`**. The lower candidate arm median is not the paired statistic, and no directional V
benefit or speedup is established.

All five production files and the three candidate-only specification clarifications are restored
byte-for-byte to control; both native-owner files are removed. The retained runner sets
`PUBLICATION_ONLY=True` and `EVALUATED_HEAD=248e2314ebbb429e4027c5cb249e680a15cec310`.
Its self-test checks exact production/specification restoration, removed-owner absence and both
required ancestors from the current head. Real mode refuses with the evaluated replay commit;
merge integration must preserve its ancestry.

The closure matrix has no deferred production promise. The evaluated implementation checkpoint
owns native/Align, topology, modes and failure tests. The full comparison owns exact model output,
cache/lifetime/accounting, source/external identity, isolation and cleanup evidence. The runner
self-test owns record/source mutations, gate boundaries and terminal restoration/replay; final
ordinary and linked-worktree verification and the review/preflight remain publication work.

**Next selected boundary.** K and V copy candidates both failed their paired gates; neither is
carried into a combined candidate. Item 70 still identified material plane-upload, expert-phase-B
and transfer/digest buckets, so attention-copy failures do not imply that R8 has no material work.
Project these newly captured control records onto item 70's exact leaf map before another model
run, then select the existing plane-upload priming and native-staging boundaries for a focused
subdiagnosis. A new ledger must define those clocks, exact behavior and materiality decision before
implementation. No speedup is inferred from a parent clock or from either rejected copy candidate.

**Bounded retrospective.** Real PERMUTE/CONT construction and independent native reference graphs
caught a fixture assumption about stub graph expansion without changing production semantics.
The balanced paired statistic again prevented a lower arm median from being called a speedup.
Existing exactness, publication and shipping rules determined removal; no permanent policy gate
is added for this result.
