# CUDA optimization enablement

Status: CUDA-KV-F16 correctness and local performance qualified, 2026-09-14.
PR publication and merge remain active. The renewed Q/K/V lifetime experiment is
complete and NOT_MET; the qualified shipping scope remains F16 KV only. The user has requested implementation,
verification, PR publication and merge following the completed design inspection.
Inspection base: `4bf8011` (including dispatch optimization `5efd7a0`).
[GPU performance](gpu-runtime-performance.md) owns the performance floors and historical evidence;
this document owns the CUDA enablement contract. The qualified local KV result is
recorded below; it is separate from the deferred graph-concurrency experiment.

Status note 2026-09-20: the inspection rows below reflect base `4bf8011`. Since `ae6eac7`
(PR #243) CUDA OLMoE sessions select policy 2 (`src/runtime_generation.align:398`) and the
retained-half native test has no MTL-only guard. Current per-backend state, including the
Qwen-on-CUDA leftover, is in `../backend-parity.md`.

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
control, or the control commit a dated campaign paragraph below nominates instead,
same host/model/tokenizer/quantization/bundle/compiler, greedy 128-token output, and the
exact system/short/long prompts and short/short/long/long request sequence from
`gpu-runtime-performance.md` §6.1. Run Qwen then OLMoE. Each arm is a fresh resident session under
1 GiB host and 6,000,000,000-byte device limits. Use five pairs with arm order control/candidate,
candidate/control, control/candidate, candidate/control, control/candidate; no concurrent GPU arms.
Freeze each implementation candidate's clean commit and source hashes before its run. Isolate
graph enablement first; use the accepted graph candidate as a second control for KV attribution
only if it shipped, and retain the original-control comparison for the combined result.

A dated subsection below may settle one additional protocol with its own case list,
metrics and budget; `request` remains the default and its measured workload, ordering,
clocks and decisions are unchanged by that addition.

Preparation/owner execution ceiling is 3600 seconds per bounded invocation. One diagnostic trace
is at most 60 seconds, within a 600-second process deadline. Each paired model campaign is at most
2400 seconds and each construction/request at most 300 seconds. No profiler runs during timing.
Preserve useful output and resume unfinished owner phases rather than repeating complete owners
after a timeout. A timed-out or incomplete pair does not produce a passing performance decision.

Primary local target for the shipping F16 campaign is the OLMoE long cached request's client wall
time: median per-pair reduction at least 15% and candidate faster in at least four of five pairs.
A dated campaign paragraph below may nominate one different model/case as its primary row under the
same thresholds; every other row stays a guardrail. All 40 responses per model must
pass the existing fixed-output quality check and pairwise exact outputs/counts. Other request
cases on both models are guardrails: no greater than 5% median per-pair regression. Record every
startup, request wall time, worker elapsed time and token count separately. Preserve all pairs,
failed outputs and raw identities; do not mix worker processing clocks with client wall clocks.
Keep only performance-specific complexity that clears its declared floor.

The historical `scripts/run-gpu-session-measurement --campaign cuda-final` deliberately rejects
changed runtime sources beyond `688232c`. It cannot measure this candidate unchanged. Do not edit
its frozen nominations or old receipts; a current-tree comparison against the two retained
`llama-server` baselines uses the separate `--campaign cuda-current` nomination settled in
`gpu-runtime-performance.md` §6.3, which leaves `cuda-final` untouched. The implementation owner must package the local paired
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
executes only a measurement protocol settled in this section. `--protocol
{request,startup}` selects it and defaults to `request`, the four-case sequence of the
lead paragraph above compared on request client wall time; `startup` is the one-request
loader protocol settled in its own dated subsection below. The protocol owns the case
list, the compared metrics, the default primary row and the measured-clock budget. The
control must be the clean commit nominated by `--control-commit SHA` (default the full
40-character lowercase hex of `4bf8011`; short forms are refused), and `--primary
MODEL:CASE` selects the one primary row within the selected protocol's cases,
defaulting to that protocol's settled row (`olmoe:warm-long-cached` for `request`,
`olmoe:cold-short` for `startup`); every other model/case/metric stays a guardrail. All
three values must already be settled by a dated campaign paragraph in this section
before a campaign runs, and all three are recorded as `policy.protocol`,
`policy.control_commit` and `policy.primary` in the receipt; `policy.primary` itself
carries `model`, `case` and `metric`, and each `comparisons[]` row carries `metric` and
a `primary` boolean. These options replace the earlier practice of editing the tool's
`CONTROL` constant on an experimental branch. Both builds and their complete source
closures are verified before and after the run, with identical Align/compiler/bundle
and non-shim libraries. The admitted profile owns model/tokenizer/options; input
identities are rechecked. The caller owns the fresh output directory. `result.json`
`schema_version` 2 adds a required `protocol` field and retains identities, every arm,
startup/client/worker clocks, per-arm worker `rchar`/`read_bytes`, host `/proc/meminfo`
state, the model directory filesystem types, full outputs/counts, per-metric comparison
reductions and PASS/FAIL, including partial failure evidence. No consumer in
`scripts/` or `eval/` parses receipts, which is why the bump is additive-but-required;
schema 1 receipts remain valid historical evidence. Worker logs are bounded to 16 MiB
per arm; workers are serial and closed on failure. No product imports this measurement
tool. Exit 0 requires quality, exact paired outputs/counts, the primary floor and every
guardrail; other results exit 1. `--self-test` checks reduction decisions on both
metrics, missing pairs, missing clocks, output mismatch, quality refusal, a selected
non-default primary row, the `/proc/io`, `/proc/meminfo` and `/proc/mounts` parsers
against fixture text, refusal of an unknown protocol or of a primary case outside the
selected protocol, and refusal of a control build that is not the nominated commit, all
without models. The tool and this plan are digest-bound in the receipt.

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
quiet, transient-reset, permanent-busy and cancellation owners. The fresh comprehensive
review of `3549a20` is complete; its sole portable-path finding is repaired in `4a4f39a`.

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

The retained-lifetime checkpoint `dc13908` passes all 16 independent requests and
both host-capacity owners. Production traces execute Q/K/V on streams 15/16/17.
Qwen has 454 cross-stream overlapping kernel pairs; OLMoE has zero in its captured
workload. Both retain ordinary graph capture/replay. This proves the old allocation
rejection can be removed; it does not establish a speed win for either model.

For the isolated incremental experiment, freeze the measurement control to accepted
F16 source `48f249b` and its `settling-session` build. The experimental measurement
command's CONTROL constant nominates only that exact source; retain all other fixed
workload, quality, pairing, idle/observer and 15% primary / 5% guardrail decisions.
The shipping F16 command remains nominated to `4bf8011`. The graph-specific complete
campaign is retained even if it fails; no partial result establishes adoption.

### Renewed QKV result and shipping decision

The complete quiet campaign on `16a7a1e` against accepted F16 `48f249b` is **NOT_MET**.
All 80 outputs and token counts match exactly. The declared OLMoE long-cached primary
has 1.32% median paired reduction and only three of five faster pairs; it fails the
unchanged 15% and four-of-five floor. All seven <=5% regression guardrails pass.
The external observer records no foreign CPU/CUDA interference. Its combined `valid`
field is false because the measurement command exits 1 for the unmet performance
floor, not because this final campaign has contaminated timing.

[Portable complete rows](../../eval/benchmarks/cuda-qkv-lifetime-2026-09-14.json)
retain the source/compiler/backend identities, all comparisons, exact outputs and
clocks, admission observations and raw receipt hashes. The first `paired-lifetime`
campaign is excluded in its entirety: four author `gh` CI-status calls exceeded the
predeclared external CPU threshold. The final `paired-lifetime-quiet` run uses the
same clean source, inputs, protocol and unchanged thresholds with those calls stopped.
No request or pair is removed or combined across campaigns.

Qwen's trace proves actual concurrent kernels; OLMoE's multiple streams do not prove
kernel overlap. Neither is a material request-time win. Keep CUDA-GRAPH-ENABLE
**deferred**, preserving the existing shipping graph defaults and allocator behavior.
The experimental source is retained as an ancestry-only merge whose tree remains the
qualified F16 tree. Publish this capability with a merge commit (no squash/rebase),
and verify both measured commits are ancestors of the exact merging head.
Future concurrency work needs a new cost-reduction hypothesis and its own predeclared
qualification; do not lower the shipping floor to admit this result.

Bounded retrospective: the measurement observer correctly rejected even short author
CI calls. Keep such calls outside future timing windows; no new permanent repository
gate is needed. Native optimizer eligibility, actual kernel overlap and useful request
latency are separate pieces of evidence and must remain separately reported.

### Qwen F16 KV CUDA campaign (2026-09-20)

Settled before implementation of its measurement run. The intervention under test is the
retained F16 KV policy 2 for Qwen sessions on CUDA (`ba9ea4f` on `agent/cuda-qwen-f16-kv`
and its committed successor); the mechanism is fewer retained KV bytes and eliminated
per-layer casts, so the primary row moves to the request where retained KV dominates.

- CONTROL: clean `0457a7d4d4645bb733b4cbf96126c5d79c4da31d` (`main`), built on the current
  Align pin `8c8bfbc7` and already carrying the shipped OLMoE F16 policy 2 on CUDA. It is the
  merge base of this branch with `main`; the intervening commits `27d13fd` and `02e1fc7`
  change only documentation (`git diff --stat 0457a7d 02e1fc7 -- src scripts eval
  .align-revision Makefile` is empty), outside the measured source closure (`src/`,
  `scripts/`, `eval/`, `.align-revision`, `Makefile`), so the pair isolates the Qwen
  selection alone.
- CANDIDATE: the clean committed head of this branch, rebuilt after any source edit so its
  closure matches `build.json`.
- PRIMARY: `qwen2` `warm-long-cached`, the 700-token cached prompt where retained KV bytes
  are largest. Target: median paired reduction at least 15% and candidate faster in at
  least four of five pairs.
- GUARDRAILS: the other seven model/case rows, each at no greater than 5% median per-pair
  regression, exactly as today. `olmoe warm-long-cached` is a guardrail in this campaign.
- PROTOCOL: unchanged. Five pairs alternating control/candidate, the four fixed cases,
  greedy 128 tokens, fixed-output quality and pairwise exact outputs/counts, 2400 seconds
  per model campaign, 300 seconds per construction/request, fixed inter-arm cooldown and
  coordinated idle settling, 1 GiB host and 6,000,000,000-byte device budgets, no
  concurrent GPU arms and no profiler during timing.
- INVOCATION: the owner above with `--control-commit 0457a7d4d4645bb733b4cbf96126c5d79c4da31d
  --primary qwen2:warm-long-cached`.

The shipping F16 default `4bf8011` cannot serve as this campaign's control: that commit
pins Align `f502fe3d` in its own `.align-revision`, while the current pin is `8c8bfbc7`.
The owner requires the control and candidate builds to share `align_revision`,
`compiler_sha256` and `bundle_id`, so a `4bf8011` build can never pair with a
current-pin candidate. Rebuilding `4bf8011` sources against `8c8bfbc7` would not be that
commit and would confound the compiler change with the intervention. `0457a7d` is the
nearest clean ancestor on the current pin and is therefore the correct control.

Interpretation: a PASS is a local intervention result on this WSL2 CUDA host only. It is
not a competitive llama.cpp claim and not a time-to-passing-patch result; those need
separately frozen baselines and the performance plan's coding-quality gate. A guardrail
failure or an unmet primary floor is recorded in full, with no pair dropped or combined.

### Result (2026-09-20)

The campaign ran twice against clean control `0457a7d` on the current pin `8c8bfbc7`,
candidate build `source_commit` `82dab13`, the pre-rebase form of `f874c10` with an
identical measured closure (`git diff --stat 82dab13 e2f4d15 -- src scripts eval
.align-revision Makefile` is empty); `source_dirty` false. Both runs pass all seven
guardrails and all paired exact outputs/counts; the primary floor is NOT_MET both times.

| Case | Run 1 median | Run 2 median | Faster pairs (primary) |
| --- | ---: | ---: | --- |
| qwen2 cold-short | +1.91% | +4.40% | |
| qwen2 warm-short-cached | +2.39% | +2.55% | |
| qwen2 warm-long-changed | +6.72% | +6.37% | |
| qwen2 warm-long-cached (primary) | +6.71% | +6.69% | 5/5 both runs |
| olmoe cold-short | +3.00% | +7.25% | |
| olmoe warm-short-cached | -3.00% | +4.24% | |
| olmoe warm-long-changed | +1.21% | -1.62% | |
| olmoe warm-long-cached | +0.29% | +0.97% | |

Verdict: **NOT_MET** in both runs. The primary row (`qwen2 warm-long-cached`) reaches
about 6.7% median paired reduction with 5/5 candidate-faster pairs, below the
predeclared 15% floor. Startup medians were unaffected by the intervention (both arms
post capped-read). Run 1: qwen2 control 1.799 s / candidate 1.846 s, olmoe 1.559 s /
1.573 s; run 2: qwen2 1.847 s / 1.832 s, olmoe 1.634 s / 1.598 s. Each run spanned about
13 minutes.

The external clock-aware load observer (the retained 2026-09-14 observer, receipts under
`gpu-cuda-parity-20260920/` and `gpu-cuda-parity-20260920/p1-run2/` in the local evidence
store, outside Git) marked both receipts `valid: false`: the Claude Code CLI process
itself showed 0.14-0.35 CPU cores at a few samples (and `exim4` once), above the
0.1-core foreign threshold. A valid receipt requires running from a terminal with no
Claude Code session. The two consistent runs bound the expected effect at about 6.7% on
the long-context Qwen cases, so a valid rerun is not expected to reach the floor.

Interpretation: the intervention is retained as backend parity and correctness, not as a
shipping performance claim. Qwen now matches OLMoE's F16 KV policy 2 on CUDA (fewer
retained KV bytes, eliminated per-layer casts, and a real memory reduction), but the
measured local speed effect on this host stays well under the 15% floor that would make
it a shipping performance claim. Coverage note: no owner exercises seeded, non-greedy
Qwen sampling under policy 2 (the reuse smoke seeds OLMoE only, the oracle's Qwen
requests are greedy); the change is retained as parity, not as a numeric claim.

### Capped-read loader startup measurement on CUDA (2026-09-20)

Settled before implementation of its measurement run. It closes backend-parity register item P2:
the capped-read resident loaders shipped with a Metal startup campaign only
(`docs/gpu-moe-diagnosis.md:264-286`, Qwen 24.05% and OLMoE 61.58% median paired startup
reduction, 5/5), and their CUDA behaviour is `unmeasured`. The intervention under test is the
capped-read loader change to `src/runtime_qwen_load.align` and `src/runtime_olmoe_load.align`
alone; the mechanism is a staging buffer capped at the declared payload prefix, so the primary
row is session construction, not generation.

| Field | Settled value |
| --- | --- |
| Consumer | `--protocol startup` on the local paired measurement owner above; `--protocol request` stays the default, with its workload, ordering, metric and decisions unchanged (see the readiness-clock note below). |
| Composition | The protocol selects the case list, the compared metrics and the default primary row; `--control-commit` and `--primary` then override the control commit and primary row. |
| CONTROL | `5fbecf176f9488eecad32c90f394d5da48b58a1c`, a synthetic non-ancestor commit at the current pin: the P1 branch head `82dab13` with only `src/runtime_olmoe_load.align` and `src/runtime_qwen_load.align` restored to their `594981c^` (`30f41c91`) content (2 files, 30 insertions, 68 deletions). Built from worktree `/home/hiro/prj/align-llm-prefix`, branch `agent/p2-synthetic-control`. |
| CANDIDATE | The clean committed head of `agent/cuda-startup-measurement`, rebuilt after any source edit so its closure matches `build.json`. |
| INPUTS | One fixed request per arm: the existing `cold-short` case, the unchanged SYSTEM and SHORT prompts, greedy 128 tokens, unchanged `quality()` and pairwise exact outputs/counts. |
| CLOCKS | Startup is monotonic nanoseconds from immediately before `Session` construction to the `ready` frame (`startup_ns`). First request is the single request's `client_ns`; `worker_ns` is retained and never mixed with a client clock. |
| PAIRING | Five pairs per model, Qwen then OLMoE, alternating control/candidate from pair 0, one fresh worker per arm, no concurrent GPU arms. Fixed inter-arm cooldown and coordinated idle settling are unchanged. |
| CEILINGS | The measured clocks (every `startup_ns` plus every request `client_ns`) sum to at most 900 seconds, checked after every arm. The existing 2400-second per-model and 300-second per-construction/request process ceilings remain. Settling, cooldown and host observation stay outside every clock. |
| PRIMARY | `olmoe:cold-short` on `startup_ns`: median paired reduction at least 15% and candidate faster in at least four of five pairs. |
| GUARDRAILS | `qwen2 cold-short` on `startup_ns`, and both models' `cold-short` on `client_ns`, each at no greater than 5% median per-pair regression. The primary model/case on the guardrail metric is a guardrail, not a second primary. |
| BUDGETS | 1 GiB host and 6,000,000,000-byte device limits, resident CUDA placement without prefetch, no profiler during timing, exactly as the `request` protocol. |
| INVOCATION | The owner above with `--protocol startup --control-commit 5fbecf176f9488eecad32c90f394d5da48b58a1c`. |

Receipt schema 2 adds the required `protocol` field and, per arm, `worker_io` (`rchar` and
`read_bytes` from `/proc/<pid>/io`, read after the request and before `worker.close()`). Every
host observation adds `memory` (`MemTotal`, `MemAvailable`, `Cached`, `Buffers` from
`/proc/meminfo`). `identities` adds `filesystems`, the model directory filesystem type per model
resolved from `/proc/mounts`. Each comparison row carries `metric`, `paired_reductions`,
`median_reduction`, `passed` and `primary`. Startup measurement moved environment preparation
(`qualification_environment`) and the deadline arithmetic out of the timed window for both
protocols; `startup_ns` therefore no longer includes owned-scratch creation. That is the only
behavioural difference the `request` protocol sees, and it removes work that was never part of
the runtime under test.

The campaign does not drop page caches: this is a shared WSL2 host and a cache drop would perturb
the co-resident work the shared-host constraint above already protects. Only pair 0's first arm is
cold-cache; alternating arm order from pair 0 and reporting medians over five pairs absorb it, and
the recorded `/proc/meminfo` state plus per-arm `rchar`/`read_bytes` make the cache condition of
every arm auditable rather than assumed.

Validation order is fixed: policy, then profile admission, then build and source closures, then
identities and filesystem types, then per-arm quiet-window admission, then construction, then the
single request, then `worker_io`, then worker close, then the post-arm quiet window, then the
measured-clock budget, then the per-metric comparisons, then the tool/plan digest and build
identity recheck, and only then the primary floor and guardrails. Preserve all pairs, failed
outputs and raw identities; a timed-out, refused or incomplete pair does not produce a passing
decision and is never dropped, combined or retried into a passing one.

The shipping `4bf8011` default and the capped-read merge base cannot serve as this campaign's
control. `594981c^` (`30f41c91`) pins Align `f502fe3d` in its own `.align-revision` while the
current pin is `8c8bfbc7`, and the owner requires the control and candidate builds to share
`align_revision`, `compiler_sha256` and `bundle_id`. A true ancestor control therefore cannot
share the current pin, and rebuilding an old tree against `8c8bfbc7` would confound the compiler
change with the intervention. The synthetic control is the current head with only the two loader
files reverted, so the pair isolates the loader hunks alone at one compiler. It is deliberately
not an ancestor of the candidate; it exists only to be built and measured, and nothing is merged
from it.

Interpretation: CUDA session construction includes the PCIe host-to-device upload that Metal's
unified memory does not perform, so a smaller startup fraction than Metal's 24.05% and 61.58% is
predeclared here rather than explained afterwards. OLMoE is the target: its 3,219 members and
54.1 GB of fetched bytes against 4.2 GB useful are where capping can pay. NOT_MET is a valid
recorded outcome and is not a defect in the shipped loaders, whose correctness is owned by their
existing smokes and session oracles. A PASS is a local startup intervention result on this WSL2
CUDA host only: it is not a llama.cpp comparison, not a whole-session or decode speedup, and not
a time-to-passing-patch result.

`scripts/measure-cuda-optimization` keeps its `BENCHMARK_OR_MEASUREMENT` classification in
`docs/python-boundary-audit.md`; the startup protocol adds no product surface, and the audit entry
names it explicitly.

#### Result (2026-09-20)

Measured on RTX 4070 Ti under WSL2 at Align pin `8c8bfbc7`, candidate `aad5553` (`source_dirty`
false), control `5fbecf17`, 5 alternating pairs per model, one fresh worker per arm, one
`cold-short` greedy 128-token request, receipt
`gpu-cuda-parity-20260920/p2-run1/p2-startup/result.json` in the local evidence store, outside
Git (schema 2), status PASS.

| Model | Control `startup_ns` median | Candidate `startup_ns` median | Median paired reduction | Faster pairs | `rchar` control -> candidate |
| --- | --- | --- | --- | --- | --- |
| olmoe (primary) | 17.125 s (16.669-17.623) | 1.669 s (1.664-1.714) | 90.25% | 5/5 | 54.48 GB -> 4.57 GB |
| qwen2 (guardrail) | 2.777 s | 1.921 s | 30.66% | 5/5 | 9.84 GB -> 5.05 GB |

`client_ns` first-request guardrails: qwen2 +0.76% (a regression within the 5% guardrail); olmoe
−37.1% (an improvement) (paired 0.429, 0.075, 0.44, 0.325, 0.371). The olmoe first request also
benefits because the worker's page-cache footprint shrinks; this is a side effect of the shared
clock budget, not a decode or whole-session claim. All exact outputs and token counts matched per
pair.

Verdict: MET against the predeclared local intervention target (primary at least 15% median
reduction and candidate faster in at least 4/5 pairs; both exceeded on the primary and the
guardrail model).

The external load observer recorded `valid: false`: the Claude Code CLI process itself exceeded
the 0.1-core threshold at 4 campaign samples, with no other foreign process detected. This is the
same deferral recorded for P1: a valid receipt requires running from a terminal without a Claude
Code session attached. The measured effect (90.25%) is far above the PRIMARY floor, so the
deferred observer validity does not put the verdict in doubt.

This result explains the 2026-09-09 CUDA campaign's OLMoE startup of 16,483 ms against
llama-server's 913 ms: that runtime (`688232c`) predates the capped-read fix `594981c`.

Limits: this is a local startup intervention result on this WSL2 CUDA host only. It is not a
llama.cpp comparison, not a whole-session or decode speedup claim, and not a time-to-passing-patch
result.

#### Kernel-level attribution on CUDA (P6, 2026-09-20)

`nsys` profile of the current-tree session worker on RTX 4070 Ti under WSL2, one run per model,
instrumented; this is attribution, not a benchmark. Evidence:
`gpu-cuda-parity-20260920/p6-run1/summary.md` (local evidence store, outside Git).

CUDA graphs engage on both models: 5 captures, 1 instantiate, 376 graph launches per model; the
`mul_mat_id` capture concern noted elsewhere does not reproduce.

Qwen warm-long-cached kernel time is 93.1% matmul (`mul_mat_vec_q` q4_K 66.6%, q6_K 17.2%, lm_head
9.2%), attention 2.4%, F16 casts 0.05%. OLMoE kernel time splits as expert matmuls 42.9%, dense
24.1%, flash attention 12.1%, and elementwise ops (about 35k tiny launches) 13.8%.

Host/device sync accounts for 83% of the Qwen request wall (the GPU is saturated) but only 51% of
the OLMoE request wall, leaving about 49% (about 1.75 ms/token) as host-side work on OLMoE. Each
model performs one full-logits device-to-host copy per token (Qwen 608 KB, OLMoE 201 KB, about
0.25% of request time), and every one of those D2H copies targets pageable host memory — none of
the staging is pinned. Profiler overhead measured +3-16% warm and +62% on the OLMoE cold path.

Interpretation and derived leftovers, recorded in `docs/backend-parity.md` section 5: P9 (pinned
host staging for the per-token logits readback — all D2H copies are Device→Pageable) and P10
(OLMoE's per-token host-side work, about 1.75 ms/token or 49% of the cached request, needs an
uninstrumented A/B and the session observation counters before any optimization is attempted).
Neither is a performance claim; both require the request protocol before any `MET`/`NOT_MET`
verdict.
