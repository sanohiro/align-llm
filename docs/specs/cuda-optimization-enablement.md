# CUDA optimization enablement

Status: CUDA-KV-F16 correctness and local performance qualified, 2026-09-14.
Required hosted CI and PR merge remain active. The user also requested a new Q/K/V
parallelism investigation after this independent KV qualification. The user has requested implementation,
verification, PR publication and merge following the completed design inspection.
Inspection base: `4bf8011` (including dispatch optimization `5efd7a0`).
[GPU performance](gpu-runtime-performance.md) owns the performance floors and historical evidence;
this document owns the CUDA enablement contract. The qualified local KV result is
recorded below; it is separate from the deferred graph-concurrency experiment.

## Shipping scope after native production qualification

**CUDA-KV-F16 is the active shipping candidate. CUDA-GRAPH-ENABLE is deferred.**
The implementation checkpoints `2f1b69c` (graph only) and `ae6eac7` (graph plus KV)
pass all 7 Qwen and 9 OLMoE independent session requests. A manifested Qwen trace
on `2f1b69c` records 431 CUDA Graph launches, 6 begin/end captures and one
instantiation; a manifested OLMoE trace on `ae6eac7` records 502 launches and
6 captures. Both execute kernels on a single CUDA stream. The pinned concurrency
validator reports `Writes overlap` for the reshaped/permuted/contiguous branch
and clears the proposed concurrent event map. The minimal native witness's three
streams are therefore insufficient production evidence.

Do not ship the graph environment default, tensor tagging, canonical snapshots,
mode identity or extra metadata reservations. Their experimental code remains
reproducible at the named commits; the final implementation preserves the existing
shared callback and allocator behavior. Resume Q/K/V concurrency only with a
source-bound production allocation/lifetime solution and actual concurrent kernels,
then repeat its declared correctness and performance gates. This is a ggml/backend
allocation concern, not an Align language or standard-library gap.

The sections below retain the graph contract as deferred design. Its proposed FFI
queries and native smoke are not present in the shipping source. The local paired
measurement now compares **KV-only** against the unchanged `4bf8011` control;
there is no accepted graph candidate and no combined speed claim. Graph-specific
single-shot, CUDA event/stream allocation and Metal shared-planner qualifications
are not shipping requirements after removing that shared behavior change. The
session independent, real F16/attention, host-capacity and paired-performance
owners remain required for KV. Metal retains the original prefill writer, attention
selector, graph callback, graph metadata sizing and topology identity.

## 1. Current state

| Mechanism | State at the inspection base | Consequence |
| --- | --- | --- |
| CUDA build, graph capture and Flash Attention | `gpu_backend_recipe.py::BACKEND_FLAGS["cuda"]` already selects `GGML_CUDA=ON`, `GGML_CUDA_GRAPHS=ON`, `GGML_CUDA_FA=ON`, architecture 89. The retained CUDA bundle has the same flags. | No missing CMake ON switch. Actual capture/replay still needs device evidence. |
| MMQ/cuBLAS selection | Both `FORCE_MMQ` and `FORCE_CUBLAS` are OFF. | These disable forced dispatch, not the kernels. Retain backend selection. `FA_ALL_QUANTS=OFF` and `NCCL=OFF` are not missing requirements for the existing F16-attention, single-GPU consumer. |
| Backend optimization callback | `ggml_shim.c::align_gpu_graph_prepare` now calls `align_gpu_graph_optimize` for both backends, before workspace allocation. | The recent callback integration is already shared with CUDA. |
| CUDA Q/K/V graph optimization | Pinned `ggml_backend_cuda_graph_optimize` opts in through `GGML_CUDA_GRAPH_OPT=1`. There is no repository assignment; `qualification_environment` passes only owned HOME/TMPDIR and locale/timezone. The inspected shell also has no CUDA optimization overrides. | The qualified launch environment leaves this optimization OFF. A shell export alone does not reach qualification workers. This switch is distinct from capture and ordinary fusion. |
| Optimizer eligibility | The CUDA optimizer recognizes a three-way, single-row fork with `attn_norm` in its tensor name. Our node walkers' `label` arguments are fault details; the shim never calls `ggml_set_name`. | Setting the environment alone cannot make our unnamed attention fork eligible. Name the actual graph tensor, not its diagnostic string or weight. |
| Retained F16 KV | `runtime_generation::admit_olmoe_shapes_at` selects policy 2 only for Metal OLMoE sessions; CUDA uses policy 0/1. The retained-half native test also has an MTL-only guard. | CUDA has not adopted or qualified O1. |
| CUDA F16 prefill write | O1's `align_gpu_kv_write_prefix` uses `ggml_set_inplace`. At the pin, CUDA SET admits same-type F32/I32 only; CUDA SET_ROWS admits F32 source, F16 destination and I32/I64 indices. | Removing the Metal selector alone fails operation admission. Use a shipped CUDA-supported row-write path. |
| Shared dispatch work | Topology/observation/input lookup caching, direct tensor input writes and sampler changes from `5efd7a0` have no Metal backend gate. Capped-read loaders are also shared. | Do not port or reimplement these. Their benefit and correctness on the current CUDA candidate remain to be qualified. |

Local hardware inspection found an RTX 4070 Ti (compute capability 8.9, 12,282 MiB), driver 610.62,
and installed CUDA 13.3 tools including `nvcc` and `nsys`. Retained CUDA models, bundle and reference
source exist. Availability is not a new acceptance result: no model was run during this design.
The old repaired session passed Qwen 7/7 and OLMoE 9/9 at `688232c`; it does not qualify `4bf8011`.

The fixed backend source is `bb4caa7540188872173c44d161602d9271386413`; the retained checkout was
checked at that exact clean Git revision. Relevant upstream owners are
[CUDA optimization and execution](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/ggml/src/ggml-cuda/ggml-cuda.cu),
[CUDA graph/stream state](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/ggml/src/ggml-cuda/common.cuh),
[SET](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/ggml/src/ggml-cuda/set.cu),
and [SET_ROWS](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/ggml/src/ggml-cuda/set-rows.cu).
Use these pinned sources rather than current upstream defaults when implementing.

## 2. Delivery order and boundaries

1. Establish a clean manifested CUDA control from `4bf8011` with the current managed Align pin
   `f502fe3da00ce0b39c4eeec40586b11688627fbd`. Run the existing real correctness owners. Any failure
   in the recently shared dispatch changes is a baseline defect, to isolate before enablement.
2. **CUDA-GRAPH-ENABLE:** make the existing Q/K/V optimization effective for eligible resident
   CUDA decode graphs, with coherent allocator/stream lifetimes, then qualify and measure it.
   Environment setup, actual tensor naming, native lifecycle work and its owners are one usable
   capability. An environment-only patch is not completion.
3. **CUDA-KV-F16:** adopt retained-half KV for resident CUDA OLMoE sessions using supported indexed
   prefill writes, then qualify and measure it separately. This is independently useful and has a
   different precision/storage failure domain; it may proceed if graph optimization is blocked.
4. After individual acceptance, qualify their combination and the actual coding caller. A negative
   runtime result or the historical OLMoE coding-quality failure stays visible. G6 is not complete.

No backend/Align pin update, custom CUDA kernel, new capture engine, extra GPU vendor, multi-GPU
support, offload policy or Python product execution is selected. Missing tensor naming and policy
integration are application concerns. CUDA SET type support and shared optimizer state are ggml
backend limitations, not Align language gaps. Sibling Align `881076ce` and its checked-in FFI guide
were inspected; the proposal needs no new language feature. Record any actual new Align gap found
during implementation in `../align-requests.md` before consuming a workaround or hypothetical API.

## 3. Proposed contract ledger

These are target decisions for the implementation owner, not descriptions of shipped behavior.

Implementation detail settled before coding: canonical order is retained with shipped
`ggml_graph_dup` in the graph's admitted metadata context, never in separately uncharged storage.
New `gpu_graph_context_bytes(borrow owner: GpuDevice, node_capacity: i64) -> i64` returns the
existing context size plus one graph snapshot's metadata only for enabled CUDA owners; invalid
owner/capacity returns -1. New `gpu_graph_optimization(borrow owner: GpuDevice) -> i64` returns
0/1 (invalid owner -1), without allocation. The native signatures use an opaque owner and i64
capacity/result. Both have real/stub counterparts. The mode is preserved through plan finish
and cancellation. A native topology key remains associated with that immutable owner mode;
the Align topology's shape digest also includes the mode/revision through its caller. These
additions are internal FFI, not product CLI or persisted schema changes. The private header is
included from the supplied pinned `ggml/include` tree via its sibling `src` directory; manifested
builders already require that exact clean source closure.

| Field | CUDA-GRAPH-ENABLE |
| --- | --- |
| Consumer / defaults | Existing resident CUDA Qwen2 and OLMoE generation/session entrypoints. Attempt Q/K/V optimization on eligible decode graphs; leave prefill untagged for this first capability. Keep ordinary fusion and capture enabled. Metal retains its existing callback policy. No new product CLI or RuntimeOptions field. |
| Environment boundary | At the first valid CUDA owner acquisition, before backend initialization or an optimization callback, establish `GGML_CUDA_GRAPH_OPT=1` if absent. Accept exact `0` or `1` as explicit process-launch controls; reject other values with existing CONFIG/device failure before backend load. The thin native device boundary owns the ggml environment adaptation; Align still owns backend selection. Controlled acceptance uses absent input and verifies effective 1. Explicit 0 is the diagnostic control, with ordinary capture/fusion unchanged. |
| Process lifetime / failure | ggml caches this choice in a function-local static. Latch it for the process: no per-request toggle or temporary set/restore. Validate text, budgets, busy state and bundle compatibility before committing the policy; an accepted policy remains fixed even if subsequent backend initialization fails. Later opens must agree with that policy, or refuse CONFIG. Failed concurrent acquisition remains BUSY and changes nothing. Metal never establishes the CUDA setting. Independent processes may use different settings. |
| Other environment controls | Preserve upstream semantics for explicit `GGML_CUDA_DISABLE_GRAPHS` and `GGML_CUDA_DISABLE_FUSION`; do not silently override a diagnostic launch. Such launches cannot count as normal optimized acceptance. The graph-disable variable acts on presence, including a value of `0`. Run each comparison/control in a fresh process and record these three inputs. Do not broaden the qualification environment to arbitrary inherited variables. |
| Native callback boundary | Replace the handwritten `align_ggml_backend_i`/`align_ggml_backend` layout copies with the exact pinned `ggml-backend-impl.h` definitions for callback access. The manifested builder must bind that private header/include closure to the existing pinned source and core libraries. This remains a thin, pin-specific backend adapter; no new public ggml function is assumed. |
| Proposed internal naming API | Add `gpu_tag_attention_norm(borrow owner: GpuDevice, kind: i64, borrow slots: slice<u8>, index: i64) -> Result<(), Fault>` in `ggml_ffi`, plus real/stub counterparts. Its native call takes owner, fixed-width kind/index and slot pointer; it copies the fixed ASCII name `attn_norm` with shipped `ggml_set_name`, requiring no caller string, new allocation or borrowed-name lifetime. Validate live owner, decode kind, unprepared current graph context, valid occupied slot and membership in that context before mutation; failures use existing CONFIG. |
| Semantic placement | The Qwen/OLMoE resident decode builders tag the weighted attention-normalization activation consumed by Q/K/V, after its construction and before forward expansion. Derive the slot from the owning node table and assert the three projection consumers in the focused owner. Never tag every RMS_NORM, rename a weight, or assume fault labels reach native tensors. Keep the session-only MoE router expansion from `688232c` intact. |
| Graph / allocation ownership | One device still owns at most the existing prefill/decode graph pair. Optimization runs before lifetime-based sizing/allocation. Preserve a bounded canonical node-order snapshot per retained graph, charged to host reservation; restore it before each optimizer/planner pass because CUDA compute can restore a different node order for fusion. Reserve and allocate every live graph using the same optimized order. No unbounded per-token snapshots. |
| Active graph / stream state | Pinned CUDA keeps concurrent stream events per backend context, while capture entries are graph-keyed. Treat the optimizer's event map as belonging to only the active graph. On a graph switch or rebuild, synchronize, restore the target's canonical order and refresh its optimization state before execution. Untagged prefill must clear stale decode events. Repeat this preparation for all live graphs before any shared allocator rebuild, and finish with the target graph active. Reuse without a switch must preserve that target's event state. |
| Capture / invalidation | Preserve stable graph/input/KV/workspace addresses while reusing a topology. Workspace replacement, context reset, bucket/shape change and graph invalidation invalidate dependent optimization preparation. Use the backend's compatibility/warmup logic; do not forge graph UIDs or count Align's reuse counter as CUDA replay. A synchronizing MUL_MAT_ID path may legitimately execute uncaptured. |
| Failure / resource ceiling | Unsupported patterns run the original supported GPU path. An actual preparation/compute/readback failure poisons the session according to existing rules; do not retry after partial KV mutation. Extra node-order storage, CUDA events/streams, backend scratch and any extended tensor lifetimes must fit existing host/device ceilings. Reject an inadmissible plan before weight upload. Retain process cleanup even when native CUDA reports a fatal error. |
| Feasibility stop | Before widening the default, the native two-graph witness must prove the order/allocation/event transitions above using shipped APIs, including graph reset and reuse. If safe clearing/rebinding cannot be expressed at the pin, keep this capability BLOCKED with an exact ggml witness; do not reach into or copy the backend's CUDA context or add a second capture implementation. CUDA-KV-F16 remains independent. |
| Identity / schemas | Bind execution mode and policy revision in internal topology identity; record mode, source/compiler, header, library and bundle identities in qualification evidence. No persisted graph cache, cross-process pointer identity, model format or product response-schema change. Existing GPU_BACKEND_BUNDLE remains schema 1. Control and candidate builds must remain distinguishable. |

| Field | CUDA-KV-F16 |
| --- | --- |
| Consumer / default | Extend O1 policy 2 only to qualified CUDA OLMoE serial sessions after Flash probes and before planning. Qwen, single-shot, decomposed attention and Metal retain their current policy selection. This is an explicit future extension of O1's current Metal-only contract. |
| Prefill write | Generalize existing `gpu_kv_write_indexed_prefix` to the prefill case for policy 2/K layout. Reuse the existing absolute I32 prefill-position input and its current-chunk view in `runtime_olmoe`; issue shipped `ggml_set_rows` from F32 chunk into the F16 plane. Its result views the whole destination and is the dependency of the valid-prefix view, so attention cannot run before the write. No additional position tensor or CPU KV copy is required. |
| Index admission | The new prefill branch accepts 1..selected_chunk_width rows; indices must be the registered position input, with exact I32 contiguous shape and values `position..position+count-1`, all in capacity. Validate bytes before upload and require current input acceptance before compute. Reject gaps, duplicates, negative/out-of-range values, partial/misaligned writes, wrong ownership and stale accepted inputs. SET_ROWS itself does not make overlapping row writes safe. Preserve the existing one-row decode branch. |
| Precision / storage | Keep F32 source/Q/output, F16 K/V, existing plane layout, policy name `flash_f16_cached`, aligned allocation accounting and context capacity. Convert new rows only. Keep O1's positive-padding F32 path until its own CUDA evidence justifies a different implementation. No blanket relaxation of exact output/count or F16-rounding checks. |
| Planning / errors | Probe the actual SET_ROWS, prefix, padding and Flash graph shapes on the selected CUDA device before weight upload, including tail chunks and all attention buckets. Operation refusal and capacity exhaustion retain existing failure categories. A compute failure cannot fall back to policy 1. |
| Ownership / identity | Existing GpuDevice owns both KV planes; graph views borrow them. Policy 2 is part of topology identity. Input, graph and KV reset/invalidation stay coordinated across `runtime_generation`, `runtime_olmoe`, `runtime_kv`, `runtime_attention` and real/stub FFI. Product options, responses, model/pack and cache schemas are unchanged; no new persisted artifact. |
| Bounds / independence | Retain 1 GiB host / 6,000,000,000-byte device campaign limits and existing admission reservations. Prove exact aligned F16 consumption and no accumulation across repeated requests. Qualify this capability with graph optimization fixed to a declared mode, then qualify the combined accepted modes separately. |

The internal query `gpu_kv_prefill_indexed(borrow owner: GpuDevice) -> bool` selects
only policy 2 on a CUDA device (native i32 0/1, no allocation, invalid owner false).
`runtime_kv::prefill_chunk` takes the owning caller's existing position-input index;
Qwen and Metal retain the original prefix writer. In the indexed branch, `width` is
the valid prefix end, so the source row count determines the exact start. Registration
is shared across layers of the current prefill graph, cleared on graph invalidation,
and made stale after each compute. Input bytes must be accepted again before reuse.

## 4. Closure and acceptance

The following new test names are planned owners, not existing commands or passing evidence.
Extend existing owners where they already discriminate the failure; do not add a routine aggregate.

| Cell / implementation owner | Exact regression or qualification owner |
| --- | --- |
| Mode construction, absent/0/1/malformed inputs, failed first initialization, repeated open, BUSY and independent processes; native device boundary | Proposed `scripts/run-cuda-graph-optimization-smoke GGML_SOURCE CORE_LIB BACKEND_PLUGIN`, with separate subprocesses for static environment choices; retain `scripts/run-gpu-device-smoke` and `scripts/run-gpu-backend-recipe-smoke`. |
| Native tensor naming, correct three consumers, foreign/empty/stale slot refusal; resident builders and FFI | Same proposed native owner, using both model graph patterns and a wrong-name control. Verify actual tensor names. No tensor-output instrumentation on the production acceptance arm. |
| Construction and repeated execution with both graphs live; canonical/optimized order and workspace rebuild; native graph lifecycle | Same proposed native owner: prefill→decode→prefill→cached decode, same topology with changed payload, attention bucket transition, forced reallocation, reset/address reuse, early failure and cleanup. Check exact results and allocation bounds, including direct execution before capture warmup. |
| Actual optimization and replay; pinned backend | A separate bounded `nsys` trace of the manifested worker must show eligible concurrent Q/K/V execution; capture evidence additionally needs CUDA capture/instantiate/launch with later reuse. Distinguish no eligible fork, no capture eligibility, warmup and actual replay. Save invocation, tool version, trace and identities. A flag, log label or Align reuse counter is insufficient. |
| F16 construction, success, overwrite, prefix preservation, tail/padding and rounding; KV/attention/native owner | Extend `scripts/run-gpu-attention-policy-smoke GGML_SOURCE CORE_LIB BACKEND_PLUGIN` so `retained_f16_kv` actually runs on CUDA with the proposed indexed prefill path. Include nonzero start, multiple chunks, signed zero/rounding limits, exact old-cast comparison, metadata exhaustion and malformed/duplicate/stale indices. Its current CUDA run skips this retained-half test. |
| End-to-end serial history, seed repeat and failures; generation/session | `scripts/run-gpu-session-reuse-smoke`, then unchanged `scripts/run-gpu-session-independent --profile PROFILE --runtime SESSION/main --reference REFERENCE/session-reference --output NEW_DIRECTORY`: all 7 Qwen and 9 OLMoE requests exactly match. Retain injected compute/readback failure and oversized-refusal-then-reuse cases. |
| Single-shot or shared native dispatch regression | `scripts/run-gpu-independent-acceptance PROFILE CORPUS CANDIDATE REFERENCE NEW_DIRECTORY`: all 19 cases twice. Required for graph enablement's shared path and again if a subsequent KV diff changes that path; a strictly session-only KV change does not automatically repeat unrelated qualifications. |
| Allocation, cleanup and limits | `scripts/run-gpu-session-host-capacity --profile PROFILE --candidate SESSION --align-source PINNED_ALIGN_SOURCE --output NEW_DIRECTORY`, both models; supplement with real CUDA allocation/event/stream peaks for the changed native boundary. Existing Align-only counters cannot account for backend-private allocations. |
| Metal/Qwen/decomposed boundaries | Existing session reuse and attention owners plus real Metal session qualification when shared callback, naming or planner behavior changes. Never infer Metal parity from a CUDA pass, or CUDA F16 math from the stub. |

Build both control and candidate with
`scripts/build-gpu-independent-candidate GGML_SOURCE PROFILE NEW_DIRECTORY --session` and use its
non-session form for G1. Verify clean source closure, the managed toolchain and manifest before
qualification. Preserve the prior CUDA fusion repair: the historical
[session investigation](../gpu-cuda-session-repair.md) shows that diagnostic tensor outputs can
hide production fusion differences. No tolerance or failed request is removed to enable a flag.

## 5. Cost and measurement decision

Before implementation, fix this local intervention protocol: the unchanged manifested `4bf8011`
control, same host/model/tokenizer/quantization/bundle/compiler, greedy 128-token output, and the
exact system/short/long prompts and short/short/long/long request sequence from
`gpu-runtime-performance.md` §6.1. Run Qwen then OLMoE. Each arm is a fresh resident session under
1 GiB host and 6,000,000,000-byte device limits. Use five pairs with arm order control/candidate,
candidate/control, control/candidate, candidate/control, control/candidate; no concurrent GPU arms.
Freeze each implementation candidate's clean commit and source hashes before its run. Isolate
graph enablement first; use the accepted graph candidate as a second control for KV attribution
only if it shipped, and retain the original-control comparison for the combined result.

Preparation/owner execution ceiling is 3600 seconds per bounded invocation. One diagnostic trace
is at most 60 seconds, within a 600-second process deadline. Each paired model campaign is at most
2400 seconds and each construction/request at most 300 seconds. No profiler runs during timing.
Preserve useful output and resume unfinished owner phases rather than repeating complete owners
after a timeout. A timed-out or incomplete pair does not produce a passing performance decision.

Primary local target is the OLMoE long cached request's client wall time: median per-pair reduction
at least 15% and candidate faster in at least four of five pairs. All 40 responses per model must
pass the existing fixed-output quality check and pairwise exact outputs/counts. Other request
cases on both models are guardrails: no greater than 5% median per-pair regression. Record every
startup, request wall time, worker elapsed time and token count separately. Preserve all pairs,
failed outputs and raw identities; do not mix worker processing clocks with client wall clocks.
Keep only performance-specific complexity that clears its declared floor.

The historical `scripts/run-gpu-session-measurement --campaign cuda-final` deliberately rejects
changed runtime sources beyond `688232c`. It cannot measure this candidate unchanged. Do not edit
its frozen nominations or old receipts. The implementation owner must package the local paired
protocol above with its source-bound invocation and evidence; any new measurement CLI/receipt
contract must be settled here before implementing that harness. Python may serve its classified
measurement role only, with the required boundary-audit update/check if changed.

This local test establishes neither a competitive llama.cpp win nor time to a passing patch.
Those require separately frozen baselines and the performance plan's coding-quality gate.
The original design checkpoint marked acceptance NOT_RUN. The current evidence and
remaining performance gate are recorded below; design intent alone is not acceptance.

### Local paired measurement owner

`scripts/measure-cuda-optimization --profile PROFILE --control-source CHECKOUT
--control BUILD --candidate-source CHECKOUT --candidate BUILD --output NEW_DIRECTORY`
executes only the fixed local protocol above. The control must be clean `4bf8011`;
both builds and their complete source closures are verified before and after the run,
with identical Align/compiler/bundle and non-shim libraries. The admitted profile owns
model/tokenizer/options; input identities are rechecked. The caller owns the fresh output
directory. `result.json` schema 1 retains identities, every arm, startup/client/worker
clocks, full outputs/counts, comparison reductions and PASS/FAIL, including partial
failure evidence. Worker logs are bounded to 16 MiB per arm; workers are serial and
closed on failure. No product imports this measurement tool. Exit 0 requires quality,
exact paired outputs/counts, the primary floor and every guardrail; other results exit 1.
`--self-test` checks reduction decisions, missing pairs, output mismatch and quality
refusal without models. The tool and this plan are digest-bound in the receipt.

### CUDA attention analytic oracle qualification

The unchanged `4bf8011` CUDA attention owner fails its Metal analytic absolute
`1e-4` comparison: row 0/head 0/dimension 2 is `0.749894`, expected `0.75`.
The CUDA-only analytic bound is `2.5e-4 * max(1, abs(expected))` for this fixed
zero-query fixture. Metal retains its previous bound. The two actual Flash storage
paths remain byte-exact, as do incremental half rounding, all retained KV bytes,
independent model tokens/counts and paired measurement outputs. This is an existing
CUDA oracle coverage repair, not a relaxation of the F16 adoption comparison.

### Shared-host measurement constraint

The user reports another Codex on this machine. Timing uses an announced quiet window after our builds/owners finish. Without a
user-supplied pause window, independently observe at least 60 seconds of low load
before launch and continue observing throughout the campaign; neither our other
owners nor foreign development/CUDA work may overlap measured arms. The measurement owner records two-second `/proc/stat`
samples and GPU utilization/compute-process observations before and after each arm.
It refuses >=0.5 busy CPU cores, >=0.2 I/O-wait cores, GPU utilization >5% outside the calibrated low-clock display envelope, or any
compute process while the arm is stopped. The display envelope is utilization <=10%,
graphics clock <=300 MHz and memory clock <=500 MHz. Before the first generated
benchmark request, idle calibration showed 5-7% at 210/405 MHz with no compute
process; the original utilization-only check refused admission (zero measured
requests). Preserve that refusal/calibration evidence. This clock-aware admission
correction does not change the workload, timing floor, guardrails or output checks. These are idle admission checks, not proof
that Windows host activity stayed absent; retain external load observations and
invalidate the entire campaign on any known interference (never drop a slow pair).
The external observer retains its invocation and source hash plus 0.5-second process
CPU samples and foreign CUDA-library presence; reject any foreign process above
0.1 CPU cores or any foreign CUDA process. This supplements the built-in boundary
checks; it does not establish isolation from unobservable Windows host activity.
Tool/plan digests are rechecked at completion.

### Consolidated review repairs

The comprehensive review of `1342274` found three P2 issues: explicit prefill position
was not checked in the indexed wrapper; measurement helpers were not source-bound;
and SIGTERM bypassed cleanup. Preserve the prefill API by checking nonnegative start,
positive extent and the source's actual row count before either backend dispatch.
`scripts/run-cuda-kv-prefill-smoke` uses an accepting indexed test boundary so that
negative and mismatched positions fail in the real Align wrapper, with valid controls.
It is a focused owner and is not added to an aggregate.

The measurement command must execute from its exact clean `--candidate-source` tree;
its complete existing source closure (including imported helpers) must match the
candidate manifest before and after execution. SIGTERM/SIGINT become a recorded
cancellation exception and flow through worker closure; repeated cancellation is
ignored during cleanup. `--self-test` includes a real separate-process worker and
SIGTERM cancellation/cleanup witness. These repairs do not alter the workload,
performance floor, exact output checks or permitted measurement role.

### Final-review shutdown ownership decision

The conditional final review of `cb59980` found a remaining first-signal window
during normal `Session.close`: the shared helper relinquishes its process handle
before waiting. Redesign cancellation delivery at this Linux measurement boundary:
a measurement-local Session subclass blocks SIGTERM/SIGINT for the entire inherited
close operation, restoring the previous mask only after owned shutdown/reaping.
This also covers close invoked internally by generation failure; shared product and
qualification helpers remain unchanged. A pending first cancellation is then delivered
and recorded as failure. The focused regression signals the actual shutdown wait and
requires both a failure receipt and a reaped worker. This closes the same accepted
ownership requirement without another comprehensive repair/review cycle or changing
timing acceptance.

### Fixed inter-arm cooldown

The first clock-aware campaign stopped before OLMoE pair 2: GPU utilization was 6%,
graphics 270 MHz and memory 5001 MHz, outside the declared idle envelope. Its external
observer found no foreign-process interference; the entire partial campaign remains
FAIL and is not combined with later pairs. Add a fixed 10-second cooldown before
every two-second boundary observation, both before and after every arm. Cooldown is
outside all measured clocks and identical for both arms/models. Keep idle predicates,
workload, paired order, floors and exact-output checks unchanged; no selective retry
of an arm or timing-based sample deletion is allowed.

### Qualified implementation and pending timing checkpoint

The final product/runtime source is unchanged since `be7b1f2`. Exact manifested
source maps for that independently qualified build and `69dcadf` differ only in
`scripts/measure-cuda-optimization`; compiler identity is identical. Later changes
are confined to measurement cancellation/admission/cooldown and documentation.

| Applicable closure / owner command | Evidence / disposition |
| --- | --- |
| Real CUDA F16 writes, rounding, prefix/tail/padding, malformed/stale inputs, metadata exhaustion; `scripts/run-gpu-attention-policy-smoke GGML_SOURCE CORE_LIB BACKEND_PLUGIN` | PASS; native retained-half and typed supported/allocation/stub probe owners. The fixed CUDA analytic envelope above does not weaken old/new byte equality. |
| Explicit prefill interval; `scripts/run-cuda-kv-prefill-smoke` | PASS; removing wrapper admission makes the malformed-position regression fail. |
| Serial success/failure/reuse; `scripts/run-gpu-session-reuse-smoke` | PASS. |
| Exact independent outputs/counts; `scripts/run-gpu-session-independent --profile PROFILE --runtime SESSION/main --reference REFERENCE/session-reference --output NEW_DIRECTORY` | PASS on repaired `be7b1f2`: 7 Qwen and 9 OLMoE requests, including changed/cached prefixes and seeded repeat. |
| Allocation/cleanup/budget; `scripts/run-gpu-session-host-capacity --profile PROFILE --candidate SESSION --align-source PINNED_ALIGN_SOURCE --output NEW_DIRECTORY` | PASS on repaired `be7b1f2`; Qwen reserved 371,563,528 plus native peak 18,247,871 bytes; OLMoE reserved 324,012,896 plus native peak 17,974,079 bytes. Both sums fit the 1 GiB timing host limit. |
| Unchanged device/recipe seam; `scripts/run-gpu-device-smoke` and `scripts/run-gpu-backend-recipe-smoke` with their documented operands | PASS; no backend bundle or compiler pin change. |
| Source/refusal/cancellation and paired decisions; `scripts/measure-cuda-optimization --self-test` | PASS, including cancellation during generation, log ownership and actual shutdown wait. Removing shutdown deferral fails with a live worker; fixture cleanup then terminates it. |
| Python classification; `python3 scripts/check-python-boundary --strict` | PASS: 273 Python files, 83 embedded hosts, 157 product modules, zero frozen debts. |
| Publication; `python3 scripts/pre-pr --owner-test cuda-measurement -- scripts/measure-cuda-optimization --self-test` | PASS on `69dcadf` (hosted scope); every later HEAD requires its own final stamp. |
| Performance / shared host | INCOMPLETE. Both partial campaigns are FAIL and unusable for a speed claim. |
| Graph-specific shared-path, events/streams and Metal qualification | Deferred with graph enablement; final KV-only scope does not change those owners. |

The cooldown campaign stopped before Qwen pair 5 with GPU utilization 22%, memory
1699 MiB and clocks 210/405 MHz. No foreign Linux CPU/CUDA process was observed, but
this does not exclude Windows host graphics activity. Keep the idle gate unchanged.
Resume only in a coordinated quiet window; rerun the entire fixed campaign, require
all paired comparisons plus continuous external observation, then decide shipping.
No merge or speed improvement is established at this checkpoint.

Retained evidence root is `gpu-cuda-enablement-20260914` outside Git. SHA-256 receipts:

| Artifact | SHA-256 |
| --- | --- |
| `final-v2-independent/result.json` | `508ce283fd00596073edf77edc3321fcbe2f50f239161f21e5964f469798952d` |
| `final-v2-host/result.json` | `90830d8dbac6ecedd4af01a711a5058b7a19c6c349e740b93a1a64b33c5e3b24` |
| `paired-clock-aware/result.json` (FAIL) | `c0b179877fe34c17f91956dc8efeae47b66d6764de2090de1e1cd91aa31f8a27` |
| `paired-cooldown/result.json` (FAIL) | `fc8ecfc0d5f0ba42e5cedca64a5a137fb4f05fe9294484d703428b07f2ec7a59` |

Bounded retrospective: native minimal concurrency is not production feasibility,
and cancellation tests must reach the shutdown ownership transition. The production
trace and focused shutdown regression cover those lessons without a new process gate.

### Coordinated idle settling protocol

The user confirmed other development stopped. Two further whole campaigns remain
FAIL: one boundary exceeded 0.5 CPU cores while the author was inspecting source,
and one observed 22% GPU utilization at idle 210/405 MHz with no compute process.
Single instantaneous boundary admission does not distinguish transient host display
activity from an unsettled interval. No partial timing is reused.

Keep every CPU/I/O/GPU/compute-process predicate unchanged. After the fixed cooldown,
collect up to ten consecutive two-second observations and require three consecutive
quiet observations before returning ready; a busy observation resets that streak.
Retain all observations, including busy ones, in each existing `host_before` and
`host_after` receipt as `observations`, plus the final sample and ready decision.
Exhaustion refuses the entire campaign. This is bounded unmeasured settling, never
a request retry, filtered pair or changed performance floor. The continuous observer
still invalidates the whole campaign on known foreign CPU/CUDA interference, and
the author performs no builds/source inspection during timing. The owner self-test
checks immediate readiness, reset after a transient, and permanent-busy exhaustion.

### Accepted local F16 KV measurement

The complete settled campaign on clean `48f249b` PASS against unchanged `4bf8011`.
All 80 responses satisfy fixed quality and pairwise exact outputs/counts. The OLMoE
long cached primary is faster in 5/5 pairs; its median paired reduction is **27.47%**,
above the predeclared 15% floor. Every other model/case satisfies the 5% regression
guardrail. The continuously observed campaign records no foreign CPU/CUDA interference.
The user confirmed competing development was stopped. This remains a local WSL2
measurement, not proof that unobservable Windows activity was absent or a competitive
llama.cpp/coding time-to-passing-patch result.

| Model / request | Control median seconds | Candidate median seconds | Median paired reduction |
| --- | ---: | ---: | ---: |
| Qwen / cold short | 1.504935 | 1.499924 | 0.83% |
| Qwen / warm short cached | 1.435791 | 1.434280 | -0.04% |
| Qwen / warm long changed | 1.683817 | 1.687140 | -0.37% |
| Qwen / warm long cached | 1.530555 | 1.533746 | -0.19% |
| OLMoE / cold short | 0.513909 | 0.493569 | 5.38% |
| OLMoE / warm short cached | 0.391899 | 0.349919 | 10.85% |
| OLMoE / warm long changed | 0.627996 | 0.484730 | 22.65% |
| OLMoE / warm long cached | 0.533573 | 0.386864 | 27.47% |

The reduction column is the median of the five paired ratios, not the ratio of
independently computed medians. [Retained portable measurements](../../eval/benchmarks/cuda-kv-f16-2026-09-14.json)
include each arm, output, clock, every idle observation, source/compiler/bundle/tool/plan
identities and SHA-256 links to the original local receipt and external observer receipt.
Machine-specific launch paths are omitted and each response model path is normalized
to its arm model identifier; outputs, counts, clocks and comparisons are unchanged. Original receipts
remain intact under `gpu-cuda-enablement-20260914/paired-settling` and
`settling-external-load-result.json`. Earlier failed campaigns remain separate and
contribute no rows to the accepted result.

The new settling admission was designed before this complete run. It has immediate
quiet, transient-reset, permanent-busy and cancellation owners. A fresh comprehensive
review of this redesigned measurement candidate is required before publication.

### Renewed QKV lifetime experiment (local checkpoint)

The user requested another concurrency attempt after F16 qualification. Test the
hypothesis that round-robin branch ordering still permits allocator reuse across
asynchronous branches of unequal length. In the restored experimental CUDA path only,
temporarily retain all decode graph tensors through graph allocation using the shipped
OUTPUT lifetime flag, restoring every original flag before backend evaluation/fusion.
No extra tensor output is exposed or read back. Apply the same lifetime rule to size
measurement, reserve and allocation; keep prefill and Metal allocation unchanged.
A bounded native scratch vector of original flags is freed on every return; its cost
is four bytes per graph node per allocator call and must fit the existing host owner.

This diagnostic checkpoint is not shipping acceptance. First run the native graph
lifecycle owner, then a source-bound real model trace to distinguish actual parallel
kernels from optimizer log intent. If it works, qualify allocation ceilings, all
independent outputs and the existing graph performance floor before adoption; if it
does not, retain the exact witness and redesign rather than widening a flag alone.
