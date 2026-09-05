# R8 OLMoE K preparation boundary

Status: merged in PR #196; `NOT_MET`, production removed before publication, 2026-09-05.
Roadmap owner: `R8-OLMOE-K-PREPARATION-BOUNDARY`.
Control revision: `e221df396258d2b36c5a7355da721b198e0a9809`.

Item 73 selected `QK_PREPARATION` rows 14–18 at a 1,000,260,743-ns median. This candidate
changes only rows 17 and 18: K concatenation and K zero-padding become separate CPU custom
nodes with per-head bulk byte copies and one active copy worker per node. Rows 14–16, every V row,
full attention width, source dependencies and marked concat identity remain unchanged. The
candidate measures this combined copy/dispatch intervention; it cannot attribute a gain to either
part alone. Item 73's split-graph latency is diagnostic evidence, not the control measurement.

The ledger below records the evaluated candidate, retained for exact replay at
`7c2471575967eb258212ce96a7acfaa240b02611`. Its production ABI, operations and native fixture
are removed from the publication tree. The retained runner permits only `--self-test` here; real
qualification requires that evaluated ancestor. The terminal evidence below owns the final decision.

## Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Consumer/owner | Normal OLMoE CPU decode, including the existing sampled provider. Owners: `src/layer_olmoe.align`, `src/moe_decode_step.align`, `src/ggml_ffi.align`, `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`. No runtime experiment flag or second generation API. |
| Existing public tables | Add `layer_olmoe.OP_K_CONCAT_F32 := 17` and `OP_K_PAD_F32 := 18`. In the decode phase-A table replace row 17's op only and row 18's op only. Row 17 keeps `a=MM_SLOT_KPAST`, `b=MM_A_NODE_BASE+16`, `p0=1`, `WHEN_DECODE`. Row 18 keeps original `p1=width-(n_past+1)`, `alt_when=WHEN_DECODE`, `alt_a=MM_A_NODE_BASE+17`; other columns, slots, conditions and all 37 row identities stay exact. Its dedicated K op fixes axis 1; row 17's existing `p0=1` remains table metadata. |
| Construction/dispatch | `build_decode_nodes` dispatches the two named ops to the exact wrappers below. No prefill table or V dispatch changes. Both custom nodes are constructed even when row 18 pads zero columns. Each wrapper calls `ggml_custom_4d` once, returning one ordinary allocated tensor/node with the same dimensions, contiguous strides and dependency order as its old op. Source graph node counts, traversal and output marks remain unchanged; actual graph op kinds become `GGML_OP_CUSTOM`. |
| K concat result | F32 inputs `past={D,N,H,1}` and `current={D,1,H,1}` produce `{D,N+1,H,1}`. For each head `h`, copy exactly `4*D*N` bytes from that past head, then `4*D` bytes from the current head, into the corresponding result head. No float loads, conversion, finite filtering, arithmetic or padded source reads. |
| K pad result | F32 source `{D,L,H,1}` and `padding_columns=P` produce `{D,L+P,H,1}`. For each head copy exactly `4*D*L` leading bytes and write exactly `4*D*P` trailing zero bytes. `P=0` still makes a separate node and copies its input. All copied F32 bits, including signed zero, infinities and NaN payloads, remain identical; appended zeros are positive-zero bits. |
| Operation-local tasks | Each constructor passes the `n_tasks=1` scheduling hint. ggml 0.21 may still invoke the callback on every graph worker. Require `nth>=1` and `0<=ith<nth`; workers with `ith>0` return without accessing tensor bytes, and only worker 0 loops over all heads. Global backend thread policy, matrix kernels and every other op's scheduling stay unchanged. No architecture-specific instructions or assumptions are introduced. |
| Ownership/allocation | ggml owns each result's metadata through the existing graph context and storage through the existing phase-A gallocr. `args` is a local C array whose tensor pointers `ggml_custom_4d` copies into `result->src`; callback functions have static program lifetime and `userdata=NULL`. No callback pointer or closure crosses Align FFI; no new heap, persistent state, source mutation, input alias, intermediate buffer, native owner or teardown path. Output storage is distinct from both inputs. Existing graph/output lifetimes and concat-plane validation remain authoritative. |
| Numeric/size domain | Require F32, `D>0,H>0`, `N>=1`, `L>=1`, `0<=P<=4096`, final live/width columns `<=4096`, `ne3=1`, exact source layout and exact extents. Validate every multiply/add against `INT64_MAX` and `SIZE_MAX` before performing it; reject final element counts over `ALIGN_GGML_MAX_PAD_ELEMENTS=16777216`. Byte access is through `unsigned char *`, `memcpy` and `memset`; no four-byte pointer-alignment precondition. |
| Metadata/stride domain | Require exact contiguous K strides `nb0=4`, `nb1=4*D`, `nb2=4*D*columns`, `nb3=4*D*columns*H` and `ggml_nbytes==4*D*columns*H` for every source, including unit dimensions. Require matching D/H/ne3 for concat and current columns exactly 1. Validate result dimensions/strides/extent before storing its handle. |
| Validation order/errors | Real constructor: (1) nonnull context plus valid slot-store magic/capacity and in-range out/input slots; missing input or output equal to an input refuses before construction; (2) input F32 types; (3) positive dimensions, fixed axes and padding bounds; (4) checked sums/products, width/element caps and exact strides/extents; (5) one custom constructor; (6) result shape/extent and slot store. Slot failures map to `R5_SLOT`, null context/constructor failure to `R5_GGML_INIT`, type to `R5_TYPE_UNSUPPORTED`, dimension/size/stride to `R5_SHAPE`, using existing `r5_result` and the original node label. No refused construction overwrites an output slot. Stub engine matches precedence; default unavailable stub preserves its existing unavailable behavior. |
| Compute failure model | This consumer selects the existing CPU backend. Callback data access occurs only after existing successful gallocr allocation; metadata is immutable until graph teardown. Callbacks require nonnull, host-visible allocated source/result storage and the constructor-proven spans. Unexpected private-ABI/storage/task invariant failure aborts before byte access, yielding no complete helper result; the `void` callback cannot return a recoverable `R5_*` error. Existing ggml compute status failures retain `R5_COMPUTE` and common teardown. No preconstruction data-pointer check is claimed for unallocated tensors. |
| Stable behavior | Exact K/V plane bytes, logits, route/cache decisions, token ids, sampled output and every accounting/lifetime relation remain required. Context, node, graph and allocator counts remain their normal-mode values. Normal execution remains unsplit. Item-71/72/73 diagnosis entries retain their respective split count/order and select the same slot ranges/counts; row-17/18 operator descriptors explicitly become `K_CONCAT_F32`/`K_PAD_F32` wherever exposed. Generic CONCAT/PAD retain their existing identifiers and behavior, including every V and prefill use. |
| Capability classification | Application/native CPU graph operation, not an Align language gap: the pinned compiler already ships raw handles, typed scalar C FFI and `Result`. No `.align-revision` change. GPU/custom-op portability and cross-host latency claims are N/A. |
| Qualification CLI | `scripts/run-olmoe-k-preparation-boundary` with no arguments runs the fixed-host comparison; `--self-test` runs model-free record/identity/gate tests. Unknown arguments fail. Missing prerequisites emit exactly one declared N/A line and no result. |
| Two exact builds | A/control is an immutable tracked-source snapshot of `e221df396258d2b36c5a7355da721b198e0a9809`; B/candidate is a tracked-source snapshot of current clean HEAD. Materialize two isolated temporary trees and build **both** with entry `src/olmoe_exact_safe_decode_gate.align` and its unchanged argument grammar. Each tree owns its shim and helper; separately record source manifest, helper hash and shim hash. Use the same exact pinned Align compiler/runtime, C compiler/version/flags, ggml libraries and all consumed headers for both. No shared generated root binary or implementation-switch macro. |
| Build/source identities | Independently pin all transitively consumed scripts/helpers/Align sources plus the new runner and native regression owner, both shims/build scripts, fixed model/pack/geometry/server, task/prompt/token chain, compiler/revision and inherited host fingerprint. The exact allowed compiled-source delta is `src/layer_olmoe.align`, `src/moe_decode_step.align`, `src/ggml_ffi.align`, `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`; other compiled/helper/build bytes must equal control. Record exact paths, byte sizes and hashes in each arm's manifest, including every allowed source difference; reject a difference outside the finalized capability inventory. Both helper/driver entry bytes must equal the control bytes. Current head/worktree and both snapshots/manifests are rechecked after measurement. |
| Fixed request | Inherit item 73's exact model/pack/geometry/task/prompt, seed 5, temperature 300000 micros, maximum 128, terminal EOG, 975175680-byte cache budget, 87-id chain, 86 completion tokens, output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52`. Each full record must retain 11940 cache requests, 7325 hits, 4615 misses, 4376 evictions, 17656872960 fetched bytes and zero cache-to-claim copies. |
| Pair/order/isolation | Four contemporaneous arm pairs execute chronologically `AB, BA, AB, BA`. Each arm leg owns a fresh-process short-2 request immediately followed by its own fresh-process full-128 request: 8 independent conditioning/full legs, 16 requests total. A short output must match that leg's full output prefix. Require zero matching pinned model/server processes before short, between short/full and after full for each leg (24 recorded checks); native lifetime checks apply to each record and its own short/full pair. Both arms execute normal unsplit phase A. |
| Primary measurement | For pair i use the complete helper subprocess wall `full_helper_wall_ns`, measured by the same parent monotonic boundary for both arms (and required to contain helper `phases.elapsed_ns`): `gain_i=control_i-candidate_i` as a signed integer. Record chronological order independently of arm-label arrays. Integer median of four values is floor of the sum of sorted middle values divided by two; do not round signed negative medians toward zero. No timing aggregate is formed after semantic/cache/lifetime/identity/isolation failure. |
| Shipping gate | `required_gain_ns=max(871174011, ceil(control_median_ns*50000/1000000))`. `MET` iff **all four paired gains are strictly positive**, median paired gain `>=required_gain_ns`, and candidate median `<=16552306197`. Zero is not positive. The historical ceiling is immutable item-68 median 17423480208 minus its ceiling-rounded 871174011-ns floor. Both paired and historical tests are independently required; no relative gate reset to item 73's split result. |
| Result document | Exact-key schema-1 JSON `kind="R8_OLMOE_K_PREPARATION_BOUNDARY"` on stdout only after successful cleanup; concise stderr summary. Keys: `schema_version,kind,control,candidate,boundary,fixed_request,environment,pair_order,pairs,aggregate,decision,elapsed_ns`. Arm identities contain source revision/tree/manifest and external/compiler/helper/shim identities. Each pair contains `index,order,control,candidate,gain_ns`; each arm leg contains `short,full,full_helper_wall_ns,isolation`. Aggregate keys: `control_values_ns,candidate_values_ns,paired_gains_ns,control_median_ns,candidate_median_ns,median_gain_ns,positive_pairs,required_gain_ns,historical_ceiling_ns,gain_ppm`. `gain_ppm=floor(median_gain_ns*1000000/control_median_ns)`. Other inherited nested schemas remain exact; all scalar integer validators reject booleans and out-of-range values, gains permit signed i64, timings require nonnegative i64 and positive full walls; final elapsed must contain all eight recorded full walls and be at most 480 seconds. |
| Cost/validation order | One monotonic 8-minute ceiling includes both builds, 16 requests, all validation/rechecks and cleanup. Order: arguments/prerequisites; inherited/source constants; environment/linker scrub; host/clean head/ancestry/process absence/external identities; isolated exact builds; ordered pairs; records/output/cache/lifetimes/accounting/repeatability; aggregate; final head/source/external identities; child/snapshot cleanup; elapsed ceiling; publication. Child timeout, signal, mutation, contamination, malformed record, cleanup failure or ceiling excess returns nonzero with no complete document. |
| Ancestry/integration | `e221df396258d2b36c5a7355da721b198e0a9809` must be an ancestor of evaluated candidate and final merging HEAD. After a result the evaluated candidate commit must also remain an ancestor of publication and merged HEAD, including `NOT_MET` source removal. Permit merge commits only; refuse squash/rebase integration. Resolve one Git common directory, disable replacements, reject replacement refs and grafts, verify reachability from the exact merging head, and retain both source revisions in the published evidence. |
| Persisted state | No model/cache/container/provider wire format change. Runner writes no persisted production state; stdout is caller-owned evidence. The two source revisions and manifests identify reproducibility inputs. No weights, local paths or build products enter Git. |
| Terminal decision | `MET` ships only the named production changes with passing owners and evidence. `NOT_MET` retains the ledger, immutable evidence and qualification owner, but removes all candidate production changes and candidate-only native/source owner changes before publication; verify exact restored production bytes against control. Publication mode is self-test-only and names the evaluated ancestor needed for real replay. Semantic drift similarly rejects/removes the candidate and emits no fabricated latency result. |
| Acceptance | `make fmt`; both exact helper builds; `scripts/test-olmoe-k-preparation`; `make layer-forward-smoke`; `make runtime-provider-smoke`; focused real native callback parity/UBSan check; Python compilation and runner `--self-test`; clean-head fixed-host paired qualification; removal comparison when required; `git diff --check`; comprehensive review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-K-PREPARATION-BOUNDARY -- scripts/run-olmoe-k-preparation-boundary --self-test`. No new aggregate membership and no `make ci`. |

The exact new C ABI is:

```c
int32_t align_ggml_op_k_concat_f32(
    void *ctx, void *slots, int64_t out, int64_t past, int64_t current);
int32_t align_ggml_op_k_pad_f32(
    void *ctx, void *slots, int64_t out, int64_t source, int64_t padding_columns);
```

The exact Align surface is:

```align
pub fn op_k_concat_f32(
  ctx: raw, borrow slots: slice<u8>, out: i64, past: i64, current: i64, label: str,
) -> Result<(), Fault>
pub fn op_k_pad_f32(
  ctx: raw, borrow slots: slice<u8>, out: i64, source: i64, padding_columns: i64, label: str,
) -> Result<(), Fault>
```

Both native callbacks have ggml's shipped signature
`static void NAME(struct ggml_tensor *dst, int ith, int nth, void *userdata)`;
names are `align_ggml_k_concat_f32` and `align_ggml_k_pad_f32`. Read inputs only through
`dst->src[0]`/`src[1]` and read public type/dimension/stride metadata; obtain data and extent through
`ggml_get_data`/`ggml_nbytes`. No ggml struct or callback appears in the cross-language ABI.
The installed ggml 0.21.0 header declares this custom-node API. Its source confirms copied source
pointers and parameter storage, while CPU dispatch calls the stored callback synchronously:
[constructor](https://github.com/ggml-org/ggml/blob/v0.21.0/src/ggml.c#L6094),
[CPU callback](https://github.com/ggml-org/ggml/blob/v0.21.0/src/ggml-cpu/ops.cpp#L11517),
[task count](https://github.com/ggml-org/ggml/blob/v0.21.0/src/ggml-cpu/ggml-cpu.c#L2449),
[graph-worker dispatch](https://github.com/ggml-org/ggml/blob/v0.21.0/src/ggml-cpu/ggml-cpu.c#L3093).
The task hint controls graph planning, not callback invocation count; the mixed-graph native
regression requires four graph workers and exactly one active copy worker per custom node.

## Evaluated specification clarification (removed with the candidate)

Update `docs/specs/r5a-dense-layer-forward.md` section 1.3's “No dequantization, no kernel”
statement to explicitly scope it to the original R5A dense-prefill capability. Add: “R8 item 74
separately authorizes two CPU byte-copy custom nodes for OLMoE decode K concatenation and padding;
it adds no dequantization or floating-point arithmetic kernel. R5A's graph and qualification remain
unchanged.” Its one-op-per-wrapper rule remains: each new wrapper creates exactly one graph node.
Clarify the real shim's header rule 4 and the owning R4.5/R5A references to allow the custom
callbacks' public `type`, `ne`, `nb`, `src` and host-buffer metadata reads; bytes and extents use
accessors. These narrowly named accesses replace neither tensor ownership nor allocator policy.
Update `r6-olmoe-decode.md` row-17/18 vocabulary to the new op identifiers and preserve all semantic
shapes/marks. Do not silently relabel custom callbacks as ordinary ggml CONCAT/PAD kernels.

## Closure matrix and exact owner map

All new native cases belong to `scripts/test-olmoe-k-preparation`; no arguments exercises the
stub engine, while `--real` runs against configured pinned ggml include/library inputs and
`--real --ubsan` enables undefined-behavior checks for the same native fixture. A shared byte kernel/validator, if
used, belongs inside the existing byte-identical shim contract region and is tested through both
actual exported constructors. The runner self-test may invoke its model-free mode; no full model
request enters an aggregate.

| Owner/path | Construction/success | Malformed/failure/early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- |
| `layer_olmoe` table / `moe_decode_step` dispatch | exact row-17/18 replacements; 37 rows, same slots/sources/conditions/counts; normal unsplit execution | wrong op/operand/axis/condition detected; V/prefill remain original | same graph scope | final row-only source-diff inspection; `scripts/test-olmoe-attention-core` exact source order/output and mode/count assertions; layer smoke |
| C/Align concat ABI | D/N/H with one and multiple heads; N=1 and maximum admitted columns; exact last-column placement | `kprep-concat-null-context`, `-slot-precedence`, `-out-alias`, `-type`, `-shape`, `-stride`, `-overflow`, `-cap`; no output overwrite | no owned state on refusal | `kprep-concat-bits`, `kprep-concat-head-layout`, corresponding named malformed cases; real/stub parity |
| C/Align pad ABI | P=0/1/max permitted by width; multiple heads; exact leading source plus zero tail | `kprep-pad-null-context`, `-slot-precedence`, `-out-alias`, `-type`, `-negative`, `-width`, `-stride`, `-overflow`, `-cap` | same | `kprep-pad-bits`, `kprep-pad-zero-width-delta`, `kprep-pad-head-layout`; real/stub parity |
| Callback byte access | all 32-bit patterns copied unchanged; per-head spans do not overlap; one active copy worker | backing-buffer sentinels unchanged; no float conversion or unaligned typed load; corrupt data/task invariant fails before access | static callbacks, NULL userdata, no allocations | `kprep-special-bits` (+/-0, subnormals, +/-inf, signaling/quiet NaN payloads), `kprep-unaligned-byte-kernel`, `kprep-sentinels`, `kprep-task-count`, `kprep-callback-invariant`; real UBSan owner |
| Native graph/allocator lifetime | after constructor returns, graph computes from stored src pointers; marked concat stays readable after pad/score; allocator owns result | null/failed constructor and forced compute failure converge; no later layer/step committed | existing contexts/allocators/buffers balanced and released before Align owners | `kprep-callback-lifetime`, `kprep-marked-concat`, `kprep-init-failure`; `scripts/test-olmoe-attention-core` six compute failures and late failure; tiny-model provider and real full output |
| Inherited behavior | normal old modes keep all clocks/schema fields and exact output/cache counts; diagnostic slice memberships remain valid | existing numerical/shape/cache/oracle errors keep precedence | existing run teardown | `make layer-forward-smoke`, `make runtime-provider-smoke`, item-73 focused mode owner; both arms' real records |
| Isolated builds/identity | two immutable tracked snapshots, same helper/toolchain/external dependencies, separately hashed binaries | current/source/header/library/helper mutation; equal/incorrect arm labeling; unlisted source delta; wrong ancestor; replacement/graft refusal | dispose each child and tree, restore any preexisting root artifacts if build machinery unexpectedly touched them | `kprep-build-arm-binding`, `kprep-source-mutation`, `kprep-external-mutation`, `kprep-ancestry`, `kprep-root-unchanged`; exact-build evidence |
| Pairs/records | exact AB BA AB BA; short/full conditioning independent; 16 requests, 24 isolation records; exact prefixes and lifetimes | wrong order/index/count, misbound live-run arm or inconsistent declared identities, boolean/negative/overflow clocks, output/cache/lifetime drift | child process terminated/reaped | `kprep-pair-order`, `kprep-arm-schema`, `kprep-prefix`, `kprep-isolation`, inherited schema mutation vectors |
| Gate/result | signed floor median; four positive gains; equality at floor and ceiling passes | one zero or negative gain fails; one-ns floor/ceiling violations fail; both inherited and current relative floors enforced | publish only after cleanup and ceiling | `kprep-gate-boundaries`, `kprep-signed-median`, `kprep-all-four-positive`, `kprep-cleanup-ceiling`; full fixed-host paired result |
| Terminal publication | successful candidate or exact production restoration bound to evaluated ancestry | semantic rejection emits no aggregate; removed-candidate real mode refuses; missing ancestor refuses | no binaries/model artifacts committed | `kprep-not-met-removal`, `kprep-publication-replay`, `kprep-post-merge-ancestry`; comprehensive review and preflight |

Generic callbacks from Align, asynchronous escape, source-nulling moves, shared mutable callback
state, concurrent production calls, and GPU dispatch are N/A: these are static synchronous native
callbacks over existing CPU graph-owned tensors. Independent graph instances share code only.
The author consistency pass confirms the table, ABI and measurement rows agree: only two K
operations change; both arms use complete subprocess walls on normal unsplit execution; every gain
must be positive and the paired absolute/relative floor and immutable historical ceiling must pass.
Every matrix cell maps to the named owner; final passing evidence is recorded before review.

## Exact evidence records

`control` and `candidate` each have exact keys `align_llm_head,source_tree,source_files,helper_sha256,
shim_sha256`. `source_files` is path-sorted rows with `path,bytes,sha256` covering all tracked
`src/*.align`, `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`, `scripts/build-ggml-shim` and
`.align-revision`. Records contain repository-relative paths only. The runner independently pins
its imported Python chain and hashes itself and focused regression owners before/after the run.
`boundary` has `concat_row=17,pad_row=18,concat_op=K_CONCAT_F32,pad_op=K_PAD_F32,
callback_tasks=1,execution=NORMAL_UNSPLIT_PHASE_A`. `callback_tasks` records the constructor
scheduling hint; callbacks may run on multiple graph workers, with only worker 0 copying bytes.

`fixed_request` has exact keys `model_bytes,model_sha256,pack_sha256,geometry_sha256,
server_sha256,align_revision,compiler_sha256,ggml_libraries,ggml_headers,task_id,task_sha256,
prompt_sha256,maximum_tokens,temperature_micros,seed,cache_budget_bytes,full_output_sha256`.
`environment` retains the exact inherited item-73 host/C compiler/linker fingerprint keys and
validation. External file/library/header record shapes are unchanged. Each pair leg's `short` and
`full` are exact existing `olmoe_exact_safe_decode_gate` records validated by its original owner;
its `isolation` is exactly `matching_before=0,matching_between=0,matching_after=0`.
`pair_order` is exactly `[AB,BA,AB,BA]`, and every pair's `order` repeats its indexed value.
`decision` is exactly `MET` or `NOT_MET`; incomplete/malformed measurements emit neither.
The live runner binds each leg to its built helper/shim/library identities. Caller-owned JSON is
not a cryptographic execution attestation; identical valid payloads cannot authenticate their
origin independently of the runner. No helper arm tag or measurement-path change is introduced.

## Evaluated implementation checkpoint

The evaluated ancestor implemented the two production operations, scalar-only FFI, and isolated
paired owner. The native/source verification in this section belongs to that evaluated checkpoint.
The final row/dispatch inspection confirms that only decode rows 17/18 change operation identity;
all operands, conditions, widths, V/prefill paths and source graph membership remain intact.
The pinned helper per-unit check passed 17 units. Real, unavailable-stub and engine-stub C builds
passed with warnings as errors; the shared contract blocks remain byte-identical. `gmake fmt`,
`scripts/test-olmoe-attention-core`, `gmake layer-forward-smoke` (82.153 seconds), and
`gmake runtime-provider-smoke` (sampler vectors plus 61 CLI assertions) passed.
`scripts/test-olmoe-k-preparation` passed in stub, `--real`, and `--real --ubsan` modes,
with both real modes using four graph workers. The test explicitly covers the scheduling-hint
correction discovered during implementation: extra workers return without touching tensor storage.
Python compilation and the paired owner's `--self-test` passed. These checks established exact
semantics, not a performance improvement; the terminal result follows.

## Terminal paired evidence and disposition

The clean-head run at `7c2471575967eb258212ce96a7acfaa240b02611` completed all sixteen requests
and twenty-four isolation records in 225,360,473,750 ns. Control was the immutable item-73 merge
`e221df396258d2b36c5a7355da721b198e0a9809`. Both isolated normal-mode builds used the same
pinned toolchain, C compiler, ggml libraries/headers, model/pack/geometry, prompt and host fingerprint.
Every exact output/token/hash, cache accounting, native lifetime, source/external identity and
cleanup boundary passed. The raw schema-1 record is identified by SHA-256
`85cc8aa1b5b702e9dff5fea2e71ce1bc44a24017d7aacbb691aa81db1190b502`.

| Pair | Order | Control full wall (ns) | Candidate full wall (ns) | Paired saving (ns) |
| --- | --- | ---: | ---: | ---: |
| 1 | AB | 18815506125 | 18774986541 | 40519584 |
| 2 | BA | 19940756542 | 19973573250 | -32816708 |
| 3 | AB | 20382475750 | 19005285959 | 1377189791 |
| 4 | BA | 20432217791 | 23379259208 | -2947041417 |

Control and candidate medians were 20,161,616,146 ns and 19,489,429,604 ns. The median of the
paired savings was only 3,851,438 ns (191 ppm), below the contemporary required 1,008,080,808 ns.
Only two pairs improved, and the candidate median also exceeded the immutable 16,552,306,197-ns
historical ceiling. The decision is **`NOT_MET`**; neither a speedup nor a directional K benefit is
established. A difference between the two arm medians is not the paired gain statistic.

All five production files and the three candidate-only specification clarifications were restored
byte-for-byte to control; the two candidate-only native owner files were removed. The retained
runner sets `PUBLICATION_ONLY=True` and binds `EVALUATED_HEAD` to the evaluated commit. Its
self-test checks exact production restoration and control/evaluated ancestry from the current head;
real mode refuses with the replay commit. Merge integration must preserve that ancestry.

The closure matrix is complete for the evaluated candidate: the implementation checkpoint owns
the native/Align and mode/failure cells; the fixed-host result owns the full-model semantic,
identity, isolation, accounting and cleanup cells; the runner self-test owns malformed records,
source mutations, gate boundaries and terminal replay/restoration. There is no deferred production
promise. The final publication owner passed in both the ordinary checkout and a detached linked worktree,
including common-dir ancestry resolution and exact production restoration. Its final result validator
accepted the raw record, and real invocation refused with the evaluated replay SHA. Comprehensive review and classifier-selected publication checks remain the
final merge gates, recorded on the pull request.

**Next selected boundary.** Item 73 also measured V preparation rows 21–24 at 988,706,344 ns,
above the unchanged 871,174,011-ns eligibility floor. Select a V-only exact copy capability for
rows 23/24 after this result merges; keep rows 21/22, marked concat, full width and normal graph
execution unchanged. The mixed K results do not justify including K in that candidate. Its new
ledger must set the contemporaneous control and complete-request shipping gate before coding.

**Bounded retrospective.** The native four-worker regression preserves the concrete dispatch
lesson at the evaluated ancestor. The paired owner prevented ambient timing changes or the
lower candidate arm median from being reported as a qualified speedup. No new permanent gate
is needed; the existing exact-semantics and complete-request rules determined the disposition.

PR #196 merged as `36183a342d2f87bcf153dfd1d347d38efc08b9a1`, preserving the tested tree
`7fdbe644881a8a09a2aa8b8c996e42cefc9f469b`. The [complete raw record](https://github.com/sanohiro/align-llm/pull/196#issuecomment-5548884976)
is durably preserved and was retrieved/decoded/hash-verified before merge. The post-merge owner
self-test passed, including exact restoration and both required ancestors. Item 75 owns the selected V successor.
