# GPU runtime: Metal, CUDA, Vulkan and HIP

Status: design only, 2026-09-06. No capability in this document is implemented by this change.
This is the authoritative GPU contract and delivery plan for roadmap items 80–85. The user requested
planning before implementation. The current CPU result remains historical evidence, not GPU evidence.

## 1. Outcome and evidence

A caller must be able to generate text through `AlignRuntime` using an explicitly selected GPU,
keep weights and KV on that device, and use bounded CPU/DRAM/AlignPack offload when the model does
not fit. Metal, CUDA, Vulkan and HIP share the same application contract. Backend-specific kernels
come from ggml; Align owns model semantics, routing policy, placement, budgets, cache decisions,
scheduling and generation. Calling a GPU-enabled llama-server remains a useful control, but does
not implement this in-process runtime.

The existing sources establish the starting point:

- `gpu_forward.align` and R5C implement dense Qwen prefill on Metal; PR #129 includes real-device
  correctness evidence. Its window wrapping and diagnostic readbacks do not define a production
  decode architecture or establish end-to-end speedup.
- `moe_decode_step.align` opens `ggml_ffi.device_open`; `align_ggml_device_open` in `ggml_shim.c`
  explicitly returns the CPU device. GPU support therefore needs a generation consumer, not only
  another backend library in the build.
- CPU generation already supplies Qwen greedy and OLMoE greedy/seeded sampling, EOG handling,
  tokenization, geometry/source checks, an expert cache and provider integration. Reuse those
  semantics and their fixtures. Audit host-pointer assumptions before sharing execution machinery.
- R8 items 49–79 qualify a CPU implementation and fixed-host optimization sequence. They do not
  discharge the architectural R8 CPU/GPU scheduling and prefetch objectives.
- At consumer Align `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`, the installed ggml 0.21.0
  `ggml-backend.h` supplies device properties, buffer types/allocation, tensor transfers,
  supports-op checks, synchronization, events and a multi-backend scheduler. These are native APIs;
  most are not yet exposed by this application's shim/FFI. The exact build must be pinned before
  use; a header declaration alone does not prove backend support or a recoverable failure path.

Upstream's [build documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)
documents Metal, CUDA, Vulkan and HIP builds. It is discovery evidence; implementation recipes must
replace moving branch references with immutable revisions and tested SDK/compiler combinations.
No custom CUDA/Metal shader or second model frontend is a prerequisite of this program.

## 2. Hardware and platform scope

Selection is by backend and device identity, never by a hard-coded GPU model. Query actual memory,
allocation limits, supported operations, buffer accessibility and synchronization facilities.
Compile GPU code for the explicitly recorded target architectures; reject a missing compatible
device binary instead of treating every NVIDIA or AMD generation as supported.

| Backend | Target family | Initial validation environment | Evidence still required |
| --- | --- | --- | --- |
| CPU | supported host CPUs | existing macOS and Linux owners | unchanged CPU behavior throughout |
| Metal | Apple Silicon unified memory | available Mac, currently Apple M1 / 16 GiB | generation, resident KV, offload, lifetime and performance |
| CUDA | compatible NVIDIA GPUs | user's RTX 4070 Ti; native Linux or WSL2 Linux | actual driver/toolkit/device inventory and every GPU acceptance suite |
| Vulkan | compatible NVIDIA, AMD and Intel devices | first NVIDIA PC where Vulkan compute is exposed | AMD/Intel require separate devices; WSL2 Vulkan is not inferred from CUDA access |
| HIP | ROCm-supported AMD GPUs | no AMD device currently available | build recipe plus real supported AMD GPU/OS/driver qualification |

The RTX 4070 Ti is a representative test device, not a product restriction. NVIDIA lists the
non-SUPER card with [12 GB memory](https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4070-family/).
Discover the installed device rather than deriving capacity from that name. Start the test profile
with a 9-GiB device-allocation budget only if admission allows it; also test 2-GiB and 4-GiB constrained
budgets. Those values belong to fixtures/profiles, never runtime defaults or backend dispatch.
Host RAM, usable GPU memory, driver, filesystem and toolkit remain inventory inputs to collect.

Native Linux x86_64 is a first-class target. WSL2 uses the Linux Align toolchain with a Windows
NVIDIA driver; it is a separate performance environment. Follow the
[NVIDIA WSL guidance](https://docs.nvidia.com/cuda/wsl-user-guide/): use the WSL-compatible toolkit
without replacing the Windows-provided driver with a Linux GPU driver inside WSL. Keep model and
build data in the Linux filesystem for the initial WSL profile; a `/mnt` Windows filesystem is a
separate storage experiment. Native Windows is a future compiler/runtime/platform port: current
Align releases cover macOS aarch64 and Linux x86_64/aarch64, not Windows. Lack of WSL is no issue on
native Linux. No Windows-native support is claimed by a WSL result.

AMD has two planned routes: portable Vulkan and native HIP/ROCm. Validate the selected GPU against
the pinned ROCm stack; upstream [AMD integration guidance](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/inference/llamacpp.html)
does not imply every Radeon/APU supports every ROCm release. No AMD hardware blocks AMD-specific
qualification only; it must not block Metal/CUDA delivery or erase the AMD roadmap item.

Support is recorded per `(backend, GPU architecture/device, OS, driver, backend build, model,
quantization, placement mode)` with independent fields for implementation, build evidence,
functional qualification and performance decision. Values are respectively `planned|implemented`,
`unverified|pass|fail`, `unverified|pass|fail`, and `unmeasured|met|not_met`. No GPU is currently
qualified for the new generation contract. Compilation, stubs and another vendor's Vulkan run
cannot promote an untested tuple. Opt-in execution of an unverified tuple may be attempted after
runtime capability checks; absence of prior evidence is reported, not a model-name allowlist.

## 3. Public-contract ledger

These are proposed application surfaces, not available commands or new Align language syntax.
This ledger owns their meaning; capability sections refine internal implementation checkpoints.

| Surface | Contract, owner and acceptance |
| --- | --- |
| Configuration API | Add `ProviderConfig.runtime_options_path: str`. Empty preserves the existing CPU configuration. Nonempty is a borrowed UTF-8 path, 1–4096 bytes, no embedded NUL, consumed synchronously by `provider_runtime`. Network providers require empty. The caller retains path storage through the call. `gpu-config` owns constructors and refusal coverage. |
| Generation CLI | Extend the current `main --provider align-runtime MODEL PACK GEOMETRY PROMPT RESULT [MAX_TOKENS] [CACHE_BUDGET_BYTES]` with an optional terminal pair `--runtime-options OPTIONS.json`. Remove that pair before the existing positional parse; duplicate, misplaced or valueless options fail. Default maximum remains 128. Existing invocations remain CPU. |
| Option document | Strict UTF-8 JSON, maximum 16 KiB, schema 1, exact fields in §3.1; duplicate/unknown/missing keys, boolean-as-integer, fractions, overflow, invalid enums and trailing documents fail before model/device work. Read once into owned bounded data per invocation; do not re-read mutable options during generation. |
| Legacy cache interaction | Preserve the current Qwen-zero / OLMoE-positive `runtime_cache_budget_bytes` rule with either empty or nonempty options. For GPU execution this is a host expert-cache sublimit, must not exceed `host_budget_bytes`, and is charged once inside that total, never added to it. Resident execution may allocate zero host expert-cache bytes despite a positive ceiling. An explicit CPU options file is rejected in schema 1; CPU uses the established path. |
| Provider results | Existing owned text / `Result<string, Error>` and CLI schema 2 remain. Map GPU refusal to `Error.Invalid` with no partial successful output. Internal owned fault detail has stable category and stage strings (§3.2), exposed by qualification evidence. Do not persist raw handles or expose device memory through `str`/`slice`. |
| Model/request scope | Same exact `qwen2` and `olmoe` models, quantized member layouts, tokenizer/template and request bounds. Qwen remains greedy; OLMoE retains greedy and the shipped 0.3-temperature seeded policy. Keep the existing `ModelInfo.supports_seed` report based on the positive OLMoE cache setting; generation validates that setting against the actual model before device work. GPU configuration does not suppress the shipped seeded capability. |
| Device identity | `runtime_device` resolves one exact backend registry plus device name from that registry. Never use generic first-GPU selection. Return actual registry/device/driver/build identifiers in evidence. Ambiguous, unavailable or mismatched devices fail; multiple installed backends must not select another backend implicitly. |
| Memory ownership | `runtime_memory` owns the byte admission plan; `runtime_device` owns native device allocations through a local package resource wrapper using Align's shipped opaque Move resources; `runtime_execution` holds graph references only within the request. Bound all application-managed host/device storage, with UMA de-duplication (§4). Raw FFI stays inside the package's privileged internal boundary. Explicit fallible completion precedes success; exactly-once Drop is the safety fallback, not an error-reporting channel. |
| Fallback | `resident` is strict GPU tensor execution; unsupported graph ops or insufficient capacity fail before compute. `hybrid` permits only the declared CPU placement units and explicit transfers (§4). Never restart partly executed generation on CPU after GPU error. Small host token/sampler/control work is always allowed and identified. |
| Concurrency and state | Initially one generation per process, invocation-local resources, no persistent model/session/KV cache. A second in-process runtime invocation is rejected before native side effects through an atomic native admission guard. Independent processes have separate owners; available-memory probes are advisory and allocation races can fail. Backend registry initialization is process-scoped once; it is not unloaded while a request can reference it. |
| Qualification consumer | Proposed `scripts/gpu-runtime-qualify --profile PROFILE.json --suite SUITE --output NEW_DIRECTORY`; suites `generation`, `offload`, `overlap`, `coding`. It builds/executes reviewed sources in isolation and packages §6 evidence for user-run PC validation. Explicit requested backend absent is failure, never passing N/A. Ordinary non-GPU CI stays model-free. |
| Build identity | Each backend recipe pins a ggml source commit, headers, shared libraries/plugins, shader/device binaries, target architectures, C/C++ compiler, SDK/toolkit and relevant flags. Record Align revision and compiler/runtime digests separately. `runtime_device` rejects incompatible ABI/build manifests; no ambient plugin search in qualification. Recipe/build tooling ships with its first working backend consumer. |
| Cache identity | Request-local weights: model+pack+geometry identities, member/plane id, quant layout, backend/device, placement and slot generation. KV additionally binds exact prompt/position/rope/mask/context, precision and request generation. No device bytes in existing persisted CPU KV files. Backend build caches additionally bind target/driver/compiler/kernel flags. No persistent application GPU cache format in this program. |
| Validation order | Common provider/request syntax; bounded option parse and conflicting legacy fields; model architecture/identity, pack/geometry, prompt/EOG/context; bundle identity and exact device; op/buffer capabilities; checked admission plan; allocation/transfers; prefill/decode; output validation; synchronize/teardown; successful result publication. Each failure prevents all later steps. |
| Prerequisites | G1–G4 use shipped FFI plus application/backend additions, subject to the probes in §7. Language-owned gaps stay registered and cannot be bypassed through captured numeric pointers or hidden native I/O workers. G5 advanced ownership use must wait on real Align prerequisites if it needs them. |
| Acceptance and metrics | Named matrix cases in §5, device suites in §6 and the capability shipping conditions in §8. This design itself makes no measured speedup or capacity claim. No production changes, toolchain adoption or GPU tests are part of the current design-only change. |

### 3.1 Exact runtime options schema 1

All fields are required. JSON member order is irrelevant; objects have no unspecified fields.

| Field | Type and values |
| --- | --- |
| `schema_version` | integer, exactly 1 |
| `backend` | string, `metal|cuda|vulkan|hip`; no implicit auto selection |
| `device` | string, exact name from the named registry, 1–256 UTF-8 bytes, no NUL |
| `backend_bundle` | path string, 1–4096 UTF-8 bytes, no NUL; prepared immutable build manifest directory |
| `placement` | string, `resident|hybrid` |
| `host_budget_bytes` | signed-64 integer in `1..2^63-1`; all managed host storage, not only expert cache |
| `device_budget_bytes` | signed-64 integer in `1..2^63-1`; all managed device allocation and workspace |
| `prefetch` | string, `off|overlap`; `overlap` requires `hybrid` and the G5 implementation |

G1 accepts only `resident/off`; G2 adds `hybrid/off`; G5 adds `hybrid/overlap`. Selecting a planned
but unimplemented backend or mode produces `UNSUPPORTED_CAPABILITY`, not a silent default.
Every product entrypoint constructing `ProviderConfig`, including the coding loop's provider
construction, must carry the same explicit option path when that entrypoint exposes runtime use.
Do not add a second sampling/configuration grammar to qualification helpers.

### 3.2 Internal failure vocabulary

Categories: `CONFIG`, `BACKEND_UNAVAILABLE`, `DEVICE_UNAVAILABLE`, `BUNDLE_IDENTITY`,
`UNSUPPORTED_CAPABILITY`, `MEMORY_BUDGET`, `ALLOCATION`, `TRANSFER`, `COMPUTE`, `NONFINITE`,
`DEVICE_LOST`, `BUSY`, `CLEANUP`. Stages: `options`, `model`, `device`, `plan`, `allocate`,
`upload`, `prefill`, `decode`, `readback`, `synchronize`, `release`.
Preserve the first operation fault and separately report cleanup failure; cleanup failure forbids
success. Native aborts, OS OOM kills and unrecoverable driver hangs are process failures, not a
guaranteed returned `Error`. Qualifiers must bound and terminate their owned process groups and
report missing results as failures. No claim of universal recoverable OOM is made at the current
Align pin (Request 35). Inject recoverable failures only at API boundaries that can return them.

## 4. Execution and memory design

### 4.1 Division of responsibility

`provider_runtime` admits the request and owns text output. `decode_step` / `moe_decode_step` keep
architecture semantics, token order, EOG and sampler sequencing. New `runtime_device` and
`runtime_memory` modules expose backend-neutral data and bounded allocations; `runtime_execution`
coordinates placement and completion. Extend `ggml_ffi.align` and `ggml_shim.c` only for shaped,
checked calls and native resource ownership. Do not duplicate model math in a CUDA-specific loop.

Use ggml's supported graph allocator/scheduler to execute explicitly assigned subgraphs. Probe its
actual split/copy behavior at the pinned revision and count the resulting device/CPU operations.
An automatic scheduler is not permission for invisible CPU fallback or unbudgeted transfer buffers.
Reject a backend integration if mandatory allocations cannot be bounded/observed. Its reset
invalidates allocated tensor references; discard those references before constructing replacements.

In `resident`, upload each immutable model weight once, keep KV and reusable activation/workspace
allocations for the invocation, and run prefill plus every decode step on the selected GPU. Host
readback is limited to final logits needed by the existing sampler, compact routing decisions when
needed and explicit debug output. No full KV or per-node activation readback in normal generation.
The all-expert-resident OLMoE path may use the original expert ids; a compact expert view must carry
an explicit global-to-local map and preserve gate/up/down correspondence and reduction order.

The existing CPU-native KV copy/compare operations require host-visible storage. On device-only
buffers, use ggml tensor operations/transfers; never call a CPU pointer primitive on a device
address. Diagnostic checksums/readbacks remain opt-in and their cost stays outside production
latency claims. Do not move a CPU optimization into GPU execution merely because its signature fits.

### 4.2 Budgets and placement

Use checked arithmetic before every dimension product, padding, stride, cache capacity and transfer
range. Admission includes weights, KV at admitted maximum context, peak activations, scheduler
copies, graph metadata, host staging, slot tables and overlap workspace. Use the selected backend's
actual allocation size/alignment, not only GGUF payload bytes. Demand too large for the minimum
executable unit is a deterministic `MEMORY_BUDGET` refusal before weights are loaded.

Budgets cover application-managed allocations. Report process RSS and driver-reported GPU use
separately because runtime libraries, kernel/driver reservations and OS page cache are not fully
controlled by these caps. Record that residual overhead; do not promise a hard whole-process RSS
or board-wide VRAM ceiling. Memory queries do not reserve space; allocation can still fail after a
successful plan. Never use managed-memory oversubscription or host swapping as implicit capacity.

Metal/UMA may borrow host storage only when the backend proves accessibility and alignment and the
owner remains alive through completion. Charge such bytes once to physical host memory and against
the device working-set budget as an alias; report alias bytes so totals are not falsely added.
CUDA/HIP/discrete Vulkan normally allocate device buffers and explicitly copy. Pinned host staging
counts against host budget, is bounded, and is released after completion. Pageable fallback is
allowed only as an explicitly recorded synchronous strategy. UMA is a capability, not a vendor test.

`hybrid` first uses a deterministic synchronous planner. Pin KV, activations, device dense layers
and minimum expert workspace; use remaining space for device experts. Place whole dense layers on
GPU or CPU, retaining the layer's KV with its attention computation; transfer residuals at layer
boundaries. For routed layers, keep router and attention at their planned owner, obtain real top-k
ids, and choose GPU phase B or whole phase-B CPU fallback using preallocated compatible workspace.
Never split one expert reduction across devices in the first version. Preserve ordered selected
expert ids and weights. Do not assume predicted experts may substitute for actual routing.

Device and host expert caches are separate deterministic LRUs with a shared immutable source key.
Do not evict in-flight slots. Fill misses from the host cache or bounded positional AlignPack reads,
then transfer only missing expert payloads; an eviction drops clean weights without disk writeback.
If a selected set does not fit the available GPU workspace, use the preplanned CPU phase B only in
hybrid mode. CPU fallback itself must fit host budget. Record every placement/fallback and transfer.
G2 acceptance requires successful offload, not speedup or learned placement. Never make fitting a
model dependent on a later learned policy. Synthetic budget limits on the existing models exercise
both device and host misses without requiring a larger model download.

### 4.3 Completion, overlap and failure

A reusable slot follows `FREE -> FILLING -> READY -> IN_FLIGHT -> READY`, with a monotonically
checked generation per new content assignment; invalidate/refuse on generation exhaustion.
Publication of `READY` requires exact completed input and transfer. Consumers bind key+generation,
not a reusable slot index alone. Eviction is permitted only from completed `READY` storage.

G1–G4 use synchronous transfer/compute completion. G5 may enqueue device work, read the next
independent block synchronously on the host, and wait before reusing either slot. All asynchronous
device references point to native-owner buffers or graph state retained by the enclosing request;
do not let a transient borrowed Align slice escape one FFI call. Host bytes are copied into owned
staging synchronously before an asynchronous submission can return. That extra copy is measured.
Use backend events only when supported and proven; a synchronous backend remains usable but
reports overlap unavailable. Submission time is not GPU execution time.

Background Align I/O tasks consuming borrowed/owned buffers remain a separate Request-41-dependent
extension. Current `spawn` registration does not alone establish overlap: at sibling commit
`46664a01352f7a669339c2eae2661d55659b96c2`, `align_rt_tg_register` appends tasks and
`align_rt_tg_wait` dispatches them. A future design must demonstrate concurrent execution as well as
safe capture. No native thread that hides the same missing Align I/O ownership contract is allowed.

On failure stop scheduling, drain known device work before releasing buffers, destroy graph and
allocator owners, then device buffers/events/staging/backends, then application frame storage.
Keep first fault plus cleanup fault. If completion cannot be proven after device loss/hang, report
an unusable invocation and fail the process-level qualifier; do not reuse or free potentially live
storage to make a balance counter pass. Process-global admission is released only after a safe
terminal state; poisoned state cannot admit a second request.

No persistent model session, cross-request GPU KV serialization, multi-GPU tensor parallelism or
distributed execution is included in items 80–85. These need their own public ownership contracts.
They are not required for one GPU plus CPU offload to become useful.

## 5. Closure matrix and planned owners

Names below are proposed cases in `scripts/test-gpu-runtime`; neither it nor the new modules exist
yet. The four suites reuse this owner and real-device qualification rather than adding one script
for every case. Each capability must map its applicable rows to the final diff and passing evidence
before review; later-capability rows remain explicitly deferred.

| Owner / boundary | Construction and success | Failure / malformed / early exit | Cleanup and exact regression |
| --- | --- | --- | --- |
| `model`, `main`, `provider_runtime` | option path at every constructor, old/new CLI, greedy and sampled dispatch | missing/duplicate/unknown fields; crossed budgets; unsupported model/mode; invalid request before I/O | owned parsed options and output; `gpu-config`, `gpu-cli-legacy`, `gpu-provider-mode` |
| `runtime_device`, FFI/shim, build recipe | exact registry/device and bundle identity; allocation-size/capability queries | wrong plugin/SDK/ABI, device absent, missing op/event/host visibility; no fallback | borrowed registry versus owned backend distinguished; `gpu-device-identity`, `gpu-capability-refusal`, `gpu-bundle-mutation` |
| `runtime_memory` | checked host/device/UMA admission and complete allocation accounting | overflow, zero/one-byte-too-small budgets, driver-race refusal, oversized workspace | unwind every allocation prefix; `gpu-budget-boundary`, `gpu-uma-alias`, `gpu-allocation-prefix` |
| graph construction, `runtime_execution` | supported ops placed at declared owners; correct quant offsets and graph lifetime | incompatible buffer, stale graph after scheduler reset, nonfinite output | exactly one owner per graph/allocator; `gpu-graph-placement`, `gpu-device-pointer`, `gpu-scheduler-reset` |
| dense/MoE decoder and KV | prefill and >1 decode, correct positions, mask/rope, router ids and expert map | max-one/EOG before decode, context bound, wrong expert member/offset or routing tie | KV outlives all queued steps; `gpu-decode-kv`, `gpu-expert-map`, `gpu-eog`, `gpu-context-boundary` |
| host/device LRUs and fallback (G2) | miss/fill/reuse/eviction and whole-unit fallback; exact source bytes | host+GPU exhaustion, wrong generation, truncated pack, partial read/transfer | no evict-in-flight or stale success; `gpu-offload-thrash`, `gpu-fallback-plan`, `gpu-slot-generation`, `gpu-short-read` |
| overlap (G5) | bounded two-slot pipeline, dependency events, CPU read while GPU runs | delayed completion, cancellation, transfer/compute failure, unsupported async, generation exhaustion | drain before reuse/free; `gpu-overlap-order`, `gpu-overlap-refusal`, `gpu-drain-failure` |
| invocation admission | repeated sequential requests; correct initialized-registry reuse | concurrent CPU/GPU and GPU/GPU attempts; failed second request; poisoned owner | atomic admission and exactly-once release; `gpu-invocation-busy`, `gpu-second-after-failure` |
| result and sampler | same input logits preserve exact RNG/filter behavior; complete owned UTF-8 output | malformed/nonfinite logits, decode errors, no partial success | no device handle escapes; `gpu-sampler-fixed`, `gpu-output-refusal` |
| qualifier and publication | snapshot build, strict artifacts, deadline, actual backend execution | missing device, crash, late source/input drift, timeout and descendant leak | post-cleanup revalidation and exclusive output publication; `gpu-evidence-mutation`, `gpu-process-cleanup`, `gpu-result-replay` |

Move-in/out, replacement and source-nulling reuse Align's shipped Move rules and provider owners.
Use a local package-defined opaque resource for request-native state, with its internal destructor
and owner-tied access. Raw handles never live in Copy application records that pretend to own them.
Dependent children cannot outlive their owner; asynchronous work must finish before destruction.
The `gpu-native-owner` regression covers exactly-once destruction across moves, early returns,
partial construction and completion failure. Whole-program and per-unit compiler builds of changed modules are required if both are
supported by the selected pin. Stub allocation failures prove only the application unwind logic;
real-device runs own driver lifecycle evidence.

## 6. Verification, numerics and handoff to another host

### 6.1 Levels of evidence

1. Model-free owners exercise real control/ownership branches with delayed completion and faults.
   They include the cases above and existing CPU owners. A stub may not pretend to measure GPU math.
2. Backend build/loader checks verify an immutable native bundle on each target OS. A missing GPU
   can be reported for discovery, but a requested hardware qualification cannot succeed with N/A.
3. Real `generation` covers Qwen2.5-Coder-7B Q4_K_M and OLMoE-1B-7B Q4_K_M: prefill, multiple
   decode steps, immediate EOG, maximum one and maximum 128, existing context limit, CPU preservation,
   and two repeated invocations. Use the model's checked metadata and current context limits;
   long-context expansion is not smuggled in as GPU enablement.
4. `offload` requires device and host cache misses, constrained budgets, repeated eviction, CPU
   fallback and exact routing/weight identity on the same small real models. Publish reads, copies,
   waits, device placement and peaks, including a counterexample to hidden all-CPU execution.
5. `overlap` requires a trace of actual simultaneous device work and host preparation, plus the
   same output/ownership checks as synchronous mode. No overlap claim from fast submission alone.
6. `coding` compares the real public provider against GPU-enabled llama.cpp on the same host,
   backend, model, prompt/template, bounds and explicit resource profile, plus this runtime's CPU
   and synchronous GPU controls. Verify tasks with the existing fixed validator and sandbox rules.

Cross-backend float arithmetic and MoE routing may differ. Require exact model/quant bytes,
dimensions, prompt ids, masks, positions, expert id/weight correspondence, EOG and sampler semantics.
For numeric qualification, teacher-force a common token prefix through CPU and device arms so one
early token difference cannot change every subsequent comparison. Compare layer outputs, router
logits/top-k boundary and final logits against a same-build reference using frozen absolute/relative
tolerances and near-tie classification. Do not demand CPU/GPU bit equality or reuse the old 87-id
CPU chain as a universal GPU golden. Do not enlarge tolerances after a failing acceptance run.

Before the first implementation's real acceptance run, commit one calibration profile per
model/precision/backend with exact prompts/teacher-forced prefixes, tolerance values, tie rule and
expected sampler behavior. Separate calibration inputs from holdout acceptance prompts. Those
values are presently unmeasured and this plan makes no numerical qualification claim. A device
integration cannot ship as qualified until that profile and its holdout pass exist. Same-backend
repeatability is a separately measured capability; fixed RNG does not prove deterministic GPU math.
Failure to obtain repeatability requires an explicit contract decision before any seeded coding
performance claim; do not silently treat divergent output as reproducible.

### 6.2 User-run qualification package

The future runner accepts a strict, versioned profile containing explicit model/pack/geometry
paths and digests, runtime-options contents, native bundle identity, reference binary identity,
task/prompt corpus identity and suite deadline. All complete profile/evidence schemas, maximum
sizes and golden round-trip vectors must be added to this ledger with the first producing consumer
(G1), before its implementation; the current design does not invent a usable profile file.

The package must include one documented command and prerequisite checker for Mac, Linux and WSL2.
It prints actual backend/device/driver/OS/WSL/kernel, host RAM/free memory, VRAM/free memory, storage
filesystem, GPU target architecture, SDK, Align and ggml build identities. The user runs it locally
on the PC and returns the output directory; no remote login, credentials, automatic driver install
or uploading model weights is required. A self-contained replay validates the result on the Mac
without needing that GPU; replay verifies evidence, not the remote device's unobserved behavior.

Evidence must contain ordered case results, complete stdout/stderr, exit/signal, nonfinite counts,
numeric comparisons, actual GPU/CPU operation placement, host/device transfer bytes, peak managed
allocations, RSS/driver memory, timings, model/prompt hashes and source/build identities. Every
timing uses a monotonic clock; synchronize device work at the measured boundary. Record unavailable
device timing as unavailable, never zero. Wall time is authoritative; overlapping category durations
must not be added into a purported wall total.

Build in an immutable source snapshot from the reviewed commit; bind the full compiler/runtime,
helper, shim and transitive source closure, plus loaded plugin and kernel artifacts. Cleanup owns
only invocation-created paths/processes. Preserve diagnostic evidence after failure. Recheck inputs
and source identity after cleanup and before publication; helper/kernel artifacts removed during
cleanup must already have immutable digests and copies in the retained evidence bundle. Publish
exclusively to a new output directory; do not overwrite a previous result. Require the evaluated
commit to remain reachable from the merging head when replay requires repository ancestry.

Unrelated hosted CI remains lightweight. Hardware suites are opt-in named qualifications triggered
by their owning boundary, with no false claim that Linux stubs cover Metal or that CUDA covers HIP.
Use a capability vector to choose supported tests; a required feature missing on a claimed profile
is a failed claim. New profile versions distinguish native Linux and WSL2, GPU architectures and
drivers. AMD remains `functional=unverified` until actual AMD evidence arrives.

### 6.3 Performance decisions and cost ceilings

Correctness enablement G1–G4 can ship opt-in without a speedup claim. Record performance separately;
never remove correctness support because one workload is slower. GPU program completion requires
working generation and offload on Metal and CUDA, implemented Vulkan/HIP consumers, honest
per-device qualification status, and a published coding/performance decision for each available
representative backend. A pending AMD qualification remains open, not silently complete.

For performance qualification use four contemporary pairs in AB/BA/AB/BA order, separately recorded
warm and cold-start conditions, and identical resource/task limits. Do not claim cold disk without
controlling OS cache; label unregulated runs cache-state-uncontrolled. Report load/TTFT, prefill
tokens/s, decode latency/tokens/s, transfer/wait costs and memory as secondary metrics. Primary
metric is time to a passing patch, including load, retries, validation and cleanup at the same
request lifecycle; a GPU-resident session baseline and a reload-every-request candidate are different
lifecycles and must not be mixed without an explicit product comparison.

G5 overlap is enabled by default on a qualified tuple only if all four paired full-request gains
are positive and the median paired saving is at least 5% of the contemporary control median,
without correctness or budget regression. G6 uses the same 5% rule for a named primary or secondary
performance claim against GPU-enabled llama.cpp. The old CPU 871,174,011-ns attribution floor has
no authority here. `not_met` preserves the working explicit mode and records the limitation; it
does not invent a smaller profitable slice or stop unrelated backend support.

Per-invocation qualification ceilings: G1–G4 `generation`/`offload` 15 minutes per backend/profile;
G5 `overlap` 15 minutes; G6 `coding` 30 minutes. Model-free owners target 5 minutes. Preparation
(dependency build/model conversion) is a separately bounded 60-minute phase, never hidden inside
inference timing or repeated for each case. Each implementation records a preregistered optimization
cost estimate before changing a timed path. No estimate or shipping speedup has been measured in
this design-only change. Timeout is failure with retained evidence, not justification to extend a
budget after looking at results.

## 7. Align prerequisites and native feasibility

The active consumer pin stays unchanged. Sibling evidence checked at
`46664a01352f7a669339c2eae2661d55659b96c2` shows Copy-only closure captures in
`docs/guide/10-closures-and-parallelism.md` and the owned-capture rejection in
`crates/align_sema/src/lib.rs`. Runtime task registration/dispatch is in
`crates/align_runtime/src/lib.rs`. Opaque Move resources already ship at both this sibling and the
consumer pin: `docs/language-spec.md` and `crates/align_driver/tests/resource_ownership.rs` define
and test construction, exactly-once Drop and dependent resource generations. Those implemented
sources supersede the older inference audit's missing-resource statement. Resources remain
non-Send; owning a resource does not authorize background capture or escaped asynchronous borrows.
Classify requirements as follows:

| Requirement | Owner and consequence |
| --- | --- |
| GPU allocation, registry selection, copies/events, op support, library builds | application plus upstream ggml; extend ordinary scalar C FFI, not the Align language |
| Device-specific op/quant missing in ggml | backend gap; explicit hybrid fallback or backend refusal, upstream issue if required; never fake a kernel |
| Fallible host buffer reservation/capacity | existing Request 35; non-blocking bounded synchronous baseline with documented process OOM failure, blocking before promising graceful host OOM recovery |
| Owned/exclusive I/O task capture | existing Request 41; non-blocking for synchronous paths and same-thread device overlap, blocking when an implementation first consumes background Align buffer prefetch |
| Existing raw/sentinel FFI and broader fallible payloads | Request 34 tracks historical payload limitations, not a missing opaque-resource mechanism. G1 uses the actual pinned resource surface and local checked FFI; recheck any newly consumed fallible payload against pinned compiler tests before relying on it. |
| Opaque native owner with exactly-once destruction | already shipped Align package resource; adopt internally in G1 and verify with `gpu-native-owner`. No new language request or public persistent-session API is needed. |
| Windows-native executable/toolchain/OS support | separate Align/platform prerequisite; outside the initial Linux/WSL2 target, not a CUDA limitation |

Before implementation, probe the pinned native backend for each architecture's graph operations,
Q4_K/Q6_K layouts, `mul_mat_id`, alignment/alloc sizes, KV updates, scheduler allocation accounting,
host-pointer visibility, status/abort behavior and events. These are checkpoints within the first
consumer, not standalone infrastructure PRs. Commit the selected immutable backend recipe, profile
schema and calibration contract before implementing their consuming public promise. If a required
operation cannot be supported, update this ledger and its exact fallback/acceptance cells first.

## 8. Delivery sequence and completion

| Roadmap / capability | Consumer-complete result | Dependencies and completion |
| --- | --- | --- |
| 80 / G1 GPU generation | Qwen greedy and OLMoE greedy/sampled text through the provider, full weights and KV resident, explicit Metal/CUDA selection; native build/loader, options, ownership and user-run qualifier included | CPU owners plus `generation` on Mac and RTX PC. Device-specific qualification may remain pending while available-host work proceeds; a Metal-only result cannot close CUDA. Backend discovery/FFI alone is not a deliverable. |
| 81 / G2 Bounded GPU offload | same callers generate under device/host budgets that force expert/layer misses, with explicit whole-unit CPU fallback and bounded AlignPack reads | G1; `offload` on Metal/CUDA. Includes transfer/accounting and placement policy; no separate dormant cache/scheduler PR. |
| 82 / G3 Vulkan generation and offload | same provider/options/qualifier on a Vulkan device, same resident/hybrid modes and strict op checks | G2 shared contract; NVIDIA Vulkan is a useful first device, AMD/Intel qualification is recorded separately. Include backend build and consumer in one capability. No claim of WSL Vulkan until exposed and tested. |
| 83 / G4 HIP/ROCm generation and offload | same caller and budgets on ROCm-compatible AMD, including build/loader and reproducible AMD validation instructions | G2; can proceed independently of G3's hardware result. Build/owner work may proceed without AMD hardware; real `generation`/`offload` stay explicitly pending until an AMD contributor/user runs them. |
| 84 / G5 Transfer/compute overlap | bounded same-thread preparation and device pipeline for hybrid requests, with safe slot/event lifetime and measured overlap | G2 per backend; G3/G4 for those backend claims. Synchronous mode remains available on backends without async capability. Request 41 only if scoped background buffer work is selected. `overlap` plus 5% default-enablement gate. |
| 85 / G6 GPU coding decision | fixed coding tasks through the public GPU provider compared with GPU-enabled llama.cpp and CPU/synchronous controls; reproducible results on each available backend/host | relevant qualified G1–G5 modes; seed/quality/parity checks and primary result, including honest `not_met`. No CPU-only historical baseline substitution. |

Start with G1 after the user resumes implementation. Do not wait for unavailable AMD hardware to
implement Metal/CUDA or Vulkan. Do not mark G4 qualified/complete because it compiles. Measurements
may reveal a necessary backend operation or language prerequisite; record it and continue independent
consumers. R9 speculation and R10 larger-model pressure remain later product directions; GPU
completion is not proof that either is finished.

## 9. Design consistency and current verification

The ledger, matrix and sequence share one explicit device/options contract, two memory budgets,
one invocation lifetime, the same four GPU backends, and one family of device qualification suites.
Hardware names select evidence profiles, not supported-device branches. Strict resident execution,
hybrid fallback and asynchronous overlap are separately observable. Numeric calibration, backend
recipes and complete qualification formats are explicitly named pre-implementation checkpoints in
G1; no proposed command, numerical tolerance, API or performance outcome is represented as shipped.

Current verification is documentation consistency, links and `git diff --check`, followed by one
comprehensive design review and the documentation publication preflight. Source tests, compiler
adoption, GPU builds, driver changes and model qualifications are N/A for this planning-only change.
