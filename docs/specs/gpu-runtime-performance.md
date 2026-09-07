# Runtime foundations and GPU performance plan

Status: design and evidence synthesis, 2026-09-06. No new measurements or GPU speed/capacity
claims are made here. Historical CPU results below retain their original owners and scopes.

This is the plan of record for materially exceeding llama.cpp's inference speed on affordable local
hardware and ultimately running larger models at useful speed under the same resource limits.
The repository-aware coding workload is the first real consumer, not a substitute for proving
runtime speed and capacity. [GPU runtime](gpu-runtime.md) remains authoritative for G1's public configuration,
ownership and schema-1 correctness qualification. This document adds execution decisions and
delivery priorities; it does not replace that design or reopen its record formats.

## 1. Objective and limits of the current design

The product objective is substantially faster local inference than llama.cpp on modest hardware,
and eventually a larger practically usable model under the same VRAM, physical RAM and storage
budget. A marginal lead is not the ambition. The project's primary integration metric remains time
to a passing patch, but it cannot stand in for the runtime goal. The program has three separately
reported outcomes:

- **Runtime speed:** prompt processing, time to first token and sustained generation latency at
  declared context depths, using the same model/quantization, prompt and output workload.
- **Useful capacity:** the largest supported model/context combination that completes within
  predeclared latency/throughput and quality limits on the same constrained machine. Merely loading
  a larger file, or generating arbitrarily slowly by paging, does not meet this goal.
- **Coding usefulness:** time to a passing patch and task success under the same attempt/validation
  policy, including preparation, retries and validation. Better prompts or fewer attempts alone
  cannot establish an inference speedup.

G1 removes the largest architectural handicap: CPU execution and repeated movement of weights/KV.
Using the same ggml backend gives access to many of llama.cpp's kernels. It does not automatically
give us llama.cpp's complete graph construction, graph reuse, batching, cache lifetime or server
scheduling. There is no evidence yet for a numerical speed ratio. Matching kernel execution is a
plausible engineering target, not a promised large lead. Larger gains need less work or less data
movement per useful output token, better reuse, or a genuinely better measured kernel/placement
choice. Resident bandwidth-bound single-token decode may leave little overhead to remove; the
constrained-memory path is a first-class target rather than a consolation benchmark.

Two gaps are especially important before implementation:

- `provider_runtime.generate` currently opens and validates model inputs, prepares the tokenizer,
  generates, and decodes within each call. G1 also releases device resources per request. A warm
  llama-server retains its model and can reuse common prompt KV across requests.
- `moe_decode_step` computes phase A, reads router IDs into Align, selects expert claims, and builds
  phase B per layer. `decode_step` also captures/validates host KV planes around layer graphs.
  Those boundaries were useful for CPU/AlignPack work. Carrying them into resident GPU execution
  would add synchronization and copies even when all experts and KV already fit on the device.

G1 must use a GPU execution graph while sharing the existing model semantics. The later reusable
session must connect directly to the coding caller. Neither is a mandate to reimplement mature GPU
kernels or to replace the existing CPU provider.

### 1.1 Existing mechanisms: retain the foundation, evaluate each policy

The architecture's Model/Block IR, AlignPack, explicit ownership, bounded expert working set and
memory-tier policy remain aligned with the speed/capacity goal. They let the application control
which bytes are read, retained and supplied to computation. The evidence does not justify
discarding that foundation, but it also does not establish that every proposed policy is useful
or that the current provider already realizes the architecture's intended efficiency.

[AlignPack](r4-alignpack-layer-major.md) makes layer/expert units independently addressable and
contiguous; [routed model prefill](r5e-moe-model-prefill.md) verifies computation from selected
expert claims rather than a mandatory full-expert allocation. These are useful prerequisites for
bounded larger-model execution, not proof of faster inference than a tuned mmap/offload baseline.
Pack preparation, temporary staging and the storage occupied by source plus packed artifacts remain
real costs. A resident model should not inherit storage-streaming work it no longer needs.

The following records summarize distinct experiments, not one composable speedup:

| Mechanism / evidence owner | Recorded result | What follows, and what does not |
| --- | --- | --- |
| [Partial LRU expert cache](r8-partial-lru-cache.md), §3.1 | Fixed 16-step OLMoE task: expert-pack reads fell from 7,801,405,440 to 2,920,955,904 bytes, a 62.56% reduction, with exact semantics. | Reuse removes application read traffic. This was a byte gate, not a latency win; page-cache-served pack reads are not necessarily physical NVMe traffic. |
| [Reset-lifetime cache decision](r8-reset-cache-decision.md), §5 | On 40 prompts at a 25% expert-cache budget, LRU reduced decode read bytes by 53.6% versus streaming. Weighted LFU was only 0.9% below LRU and did not clear its additional-policy gate. | Cache lifetime must match the real caller. The tested weighted policy was not justified; this does not reject every future score/cost-aware policy. |
| [Persistent prefix TTFT](r6-prefix-ttft.md), §8.3 | Three fixed suffixes, five pairs per suffix/protocol: mean paired reductions were 30.58% and 32.65% in the two named protocols versus our own single-shot path. | Prefix reuse has consumer-level evidence. It is not a llama.cpp comparison, a GPU result or proof that the current generate/repair caller retains a warm session. |
| [Exact-safe decode boundaries](r8-olmoe-exact-safe-decode-boundaries.md), §5 | Four fixed-request repetitions: 19.267 s historical baseline median versus 17.423 s candidate median, 9.57% lower. Cache-to-claim copy clocks were zero. | Direct cache-backed tensors plus the plane-comparison improvement shipped together. The result is for the pair of interventions on one CPU host, not zero-copy alone, the Align language alone, or superiority over llama.cpp. |
| [Post-staging coding decision](r8-olmoe-post-staging-sampled-runtime-decision.md) | Same fixed CPU coding task, four portfolios: runtime median 84.062 s versus llama.cpp 14.174 s; both passed all four at candidate 5. Decision: `NOT_MET`. | The real caller still has a substantial gap. This lifecycle includes request-local runtime setup versus a server retained within each baseline portfolio; it is not a standalone kernel-speed ratio or a GPU forecast. |

Repo-local context, failure memory, prompt improvement and task profiles remain useful application
ideas. Their direct benefit may be fewer tokens, fewer attempts or better task success rather than
faster same-model inference. Runtime reuse and placement can consume relevant workload information
through explicit boundaries, but neither cross-layer benefit nor expert predictability follows
automatically from having repo metadata. Prefix reuse, speculative decoding and CPU/GPU offload
already exist in llama.cpp; differentiation is a measured combination of workload knowledge,
physical layout and execution policy, not a blanket claim that each ingredient is unique.

### 1.2 What Align contributes, and what the application must realize

At consumer pin `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`, Align provides real mechanisms
for efficient data-oriented implementation. This is a technical foundation, not an automatic
performance multiplier over hand-optimized C/C++ using the same native kernels.

| Align capability | Relevant benefit | Limit at the application boundary |
| --- | --- | --- |
| Borrowed views, explicit ownership and pointer-based FFI | Pass existing bytes without a marshaling copy; retain the owner until the consumer completes. Eligible OLMoE generation already wraps resident cache storage as expert tensors. | Zero-copy names a specific boundary. Miss reads, layout conversion, cache fill, output copies and discrete-memory transfers do not disappear because the source language supports borrowing. |
| Fused collection pipelines | Compatible transforms/reductions form one loop without intermediate arrays; `map_into` reuses caller storage. Alias information can help native vectorization. | Collection fusion is not asynchronous I/O/compute pipelining or ggml graph fusion. It does not merge arbitrary FFI calls, remove explicit materialization, or make a data dependency concurrent. |
| Standard `soa<T>` and column operations | Read selected metadata/profile columns contiguously; avoid fetching unused fields and make bulk processing easier to optimize. | SoA is explicit, not an automatic rewrite of every array. Transposition has a cost; whole-row access may prefer AoS. Quantized weight tensors already have backend-defined packing and cannot be relaid out as generic SoA without kernel/format consequences. |
| Explicit, bounded I/O | Cursor-free `file.pread`/`pwrite` expose offsets; reads refill caller-owned buffers, buffered readers/writers coalesce small operations, `io.copy` uses bounded memory, and arena-owned mapped views avoid a separate full-file copy. These fit independently addressable AlignPack blocks and constrained-memory execution. | Buffer capacity bounds a read, but the pinned `pread` cannot choose a smaller length or an offset within the destination buffer. Mapped storage still incurs page faults and physical memory/storage traffic; mapping alone is not a speed or capacity win. |
| Explicit data and task parallelism | `par_map` uses a persistent worker pool and range kernels for supported forms; `task_group` runs independent heterogeneous jobs with scoped lifetime and joined error handling. This provides reusable machinery for parallel preparation and independent work without a new application thread runtime. | `par_map` requires Pure work; `task_group` can perform I/O. At this pin, registered tasks are dispatched at `wait`, and owned-buffer capture remains restricted. Useful parallelism depends on independent work, sufficient task size and coordination with ggml's own CPU workers. |

These I/O and parallel facilities are part of the foundation, not absent capabilities awaiting the
GPU work. The [pack reader](../../src/alignpack_read.align) already uses positional reads and
accounts for bounded windows; the [pack writer](../../src/alignpack.align) refills retained storage;
the [expert runner](../../src/moe_decode_step.align) reads selected blocks and reuses eligible
cache-backed tensors. Parallel preparation is an opportunity, not a claim that this runner already
overlaps file reads and model computation. Existing [Align requests](../align-requests.md) identify
the narrower remaining boundaries: Request 38 covers bounded positional destination filling, and
Request 41 covers transferring an owned/exclusive window to a prefetch task and demonstrating real
overlap under the shipped scheduler. Neither means Align lacks I/O or task parallelism. G1–G4 and
G5's same-thread host preparation over queued device work remain independent of Request 41.

Pinned Align sources:
[pipeline semantics](https://github.com/sanohiro/align/blob/8cefc803d5c7f883a8db5b67250ed4ed069b43a4/docs/guide/06-pipelines.md),
[columnar layout](https://github.com/sanohiro/align/blob/8cefc803d5c7f883a8db5b67250ed4ed069b43a4/docs/guide/11-data-oriented.md),
[FFI views](https://github.com/sanohiro/align/blob/8cefc803d5c7f883a8db5b67250ed4ed069b43a4/docs/guide/15-unsafe-and-ffi.md),
[I/O and mapped-view contracts](https://github.com/sanohiro/align/blob/8cefc803d5c7f883a8db5b67250ed4ed069b43a4/docs/language-spec.md#standard-library),
[parallel constructs](https://github.com/sanohiro/align/blob/8cefc803d5c7f883a8db5b67250ed4ed069b43a4/docs/guide/10-closures-and-parallelism.md),
[runtime scheduling](https://github.com/sanohiro/align/blob/8cefc803d5c7f883a8db5b67250ed4ed069b43a4/crates/align_runtime/src/lib.rs)
(`align_rt_tg_register` / `align_rt_tg_wait`),
and the [implementation audit](https://github.com/sanohiro/align/blob/8cefc803d5c7f883a8db5b67250ed4ed069b43a4/docs/impl/12-pipeline-closure-memory-io-simd-audit.md).
The pinned `zip_pipeline.rs` and `deep_pipeline.rs` compiler tests check fused-loop/allocation
shape. The audit reports flat numeric loops near equivalent native-loop performance and much
larger gains for favorable column-access comparisons; neither is an LLM throughput benchmark.

Apply these strengths at measured hot boundaries: preserve already-direct cache/weight views,
avoid reconstituting them into temporary buffers, reuse owned I/O storage, keep metadata work
bounded, and parallelize sufficiently large independent work. Check the generated loop/allocation
shape when an Align-owned bulk pass is material; measure actual copy/transfer bytes and full-request
latency when a native boundary is material.
Replacing every explicit loop with pipeline syntax or every record array with SoA is not a goal.
These are implementation considerations within the existing owners, not new universal CI gates.

## 2. Source-grounded comparison

The implementation reference is the existing `.llama-revision`,
`bb4caa7540188872173c44d161602d9271386413`. The R2c checkout carries a diagnostic patch;
unpatched upstream source owns the mechanisms below, and a benchmark uses an uninstrumented build.
Upstream head was also checked on 2026-09-06 at
`74a7c897f049c17e7080423aa2111776eff6ebbf`; it is an observation, not an automatic pin update.
Refresh the competitive baseline before each measurement campaign and freeze it within that
campaign. Keep the same-revision baseline separately for attribution.

| Mechanism in upstream | Our current position | Design consequence |
| --- | --- | --- |
| `llama_context::process_ubatch` reuses compatible graphs and allocator state, otherwise rebuilds; scheduler submission is asynchronous | G1 only said reusable workspace; the current layer runner constructs and computes many separate graphs | G1 gets whole-model graph ownership and bounded topology-aware reuse |
| `build_moe_ffn` keeps routing and selected-expert matrix multiplication in the graph | CPU claim selection crosses the host boundary per layer | G1 resident routing stays on GPU; G2 alone needs host/device expert placement decisions |
| `build_attn` uses `ggml_flash_attn_ext` where compatible; KV is updated with `ggml_set_rows` | no Flash Attention call in our shim; host planes belong to the old execution path | evaluate the shipped fused operation and in-place device KV before designing a custom attention path |
| CUDA backend captures/replays graphs and fuses compatible patterns; Metal has graph optimization and fusion | linking ggml alone does not establish any of these paths are active | pin build switches and preserve graph shapes/lifetimes that permit backend optimizations |
| llama.cpp sets `GGML_CUDA_GRAPHS_DEFAULT=ON`; standalone ggml defaults it to OFF; `GGML_CUDA_FA` defaults ON | a standalone backend recipe could silently lose graph replay | explicitly set `GGML_CUDA_GRAPHS=ON` and `GGML_CUDA_FA=ON`; verify actual use on eligible CUDA graphs |
| prompt batches and physical microbatches differ; output rows can be restricted | existing generation shares diagnostic-oriented graph plumbing | bounded batched prefill, single-token decode, and logits only for requested output positions |
| llama-server supports warm model lifetime, prompt KV reuse, continuous batching and speculative decoding | request-local G1 has no equivalent coding-session lifetime | prioritize a serial reusable coding session after G1; treat batching/speculation as separate workload-dependent investments |
| `llama-bench` separates prompt processing, generation and combined tests, and excludes tokenization/sampling | a generation-only comparison can miss the primary cost | measure inference phases for diagnosis and the real provider/task lifecycle for the decision |

Primary source locations at the pinned revision:

- [context execution and reuse](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/src/llama-context.cpp),
  [model graph/attention/MoE](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/src/llama-graph.cpp),
  [KV updates](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/src/llama-kv-cache.cpp).
- [CUDA execution](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/ggml/src/ggml-cuda/ggml-cuda.cu),
  [Metal execution](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/ggml/src/ggml-metal/ggml-metal-context.m),
  [llama.cpp build defaults](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/CMakeLists.txt),
  [ggml build defaults](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/ggml/CMakeLists.txt).
- [benchmark semantics](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/tools/llama-bench/README.md),
  [server caching and options](https://github.com/ggml-org/llama.cpp/blob/74a7c897f049c17e7080423aa2111776eff6ebbf/tools/server/README.md),
  [speculative decoding](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/docs/speculative.md),
  [mapped model storage](https://github.com/ggml-org/llama.cpp/blob/bb4caa7540188872173c44d161602d9271386413/src/llama-mmap.cpp).

## 3. G1 execution ledger

These are internal execution requirements of the existing G1 provider call. They add no CLI
arguments, persisted cache, wire schema or process lifetime. Source/build identity binds constants
and strategy selection. All allocation remains within G1's admitted host/device budgets. Exact
per-device tuning values are chosen on development inputs before qualification and committed with
the immutable recipe; holdout results cannot change them.

| ID / owner | Decision, inputs and validation | Acceptance and failure behavior |
| --- | --- | --- |
| E1 `runtime_execution`, Qwen/OLMoE graph builders | Build the embedding-to-logits graph across all layers for one prefill microbatch or decode step. Keep residuals, attention, MoE top-k/weights, expert `mul_mat_id` and reductions on GPU. Preserve the existing ordered expert semantics. | `gpu-whole-graph` and `gpu-resident-moe` prove no application host fence/readback between layers and no host expert-selection loop. Unsupported required operations refuse admission. Backend-internal kernel launches may remain multiple. |
| E2 `runtime_execution`, `runtime_memory` | Own at most one prefill graph and one decode graph plus their reserved storage per invocation. Reuse only when backend/bundle, model/layout, attention policy, tensor shapes/strides, buffer generation, mask/position layout and output selection match. Token values and device routing IDs are mutable inputs, not topology keys. | `gpu-graph-reuse` tests repeated compatible steps, changed KV view width/output shape, and rebuild after invalidation. Synchronize before changing input storage still in use. Rebuild after mismatch without keeping stale references or growing a per-token cache. |
| E3 `runtime_memory`, attention builder | Allocate the request's exact admitted KV capacity once: prompt tokens plus at most `maximum_tokens - 1` decode-written rows, never beyond model context. Append K/V by device row updates and attend only to valid positions with the correct causal mask. Reuse reserved workspaces. Do not reserve the unused model-context tail or round-trip/concatenate past KV through host memory each token. | `gpu-kv-in-place` covers prefix preservation, new columns, maximum-one, a model whose full context cannot fit but whose request capacity can, the exact context end, and a one-row-too-small allocation. Graph reset never frees weight/KV owners; buffer-generation change invalidates graph/capture state. |
| E4 model graph builders, `ggml_shim.c` | Keep Q4_K/Q6_K tensors in their native quantized form and use shipped ggml matrix operations. Preserve backend-recognizable norm/multiply, RoPE/KV-write and gated-FFN patterns. Avoid diagnostic output markings on intermediate nodes in production. | `gpu-quantized-graph` checks tensor types and graph patterns; real backend qualification checks results. No permanent full-weight f32 dequantization, invented combined-QKV weight layout, or unconditional `FORCE_MMQ`; backend dispatch owns shape-specific MMQ/cuBLAS/kernel choices. |
| E5 attention builder, backend recipe | Probe Flash Attention on exact model head sizes, masks, strides, types and quantization. Choose a qualified fused path when available and an explicitly qualified GPU decomposed path otherwise, before execution. Any f16 conversion required by the fused operation is explicit, bounded and numerically qualified; schema-1 `precision=f32` describes compared scalar values, not an implicit promise that every internal tensor is f32. | `gpu-attention-policy` covers both graph constructions, capability refusal and numeric drift. Do not silently retry a failed fused computation with another algorithm. Reduced-precision persistent KV is a later contract change, not an unrecorded G1 cache-format change. |
| E6 `runtime_execution`, backend recipe | Use a committed maximum prefill microbatch width. Admission may choose a smaller width from the recipe's ordered candidates using workspace requirements; it never searches by timing during a request. Decode width is one. Intermediate prefill chunks update KV without vocabulary projection/readback; only required output rows reach the sampler. | `gpu-prefill-chunks` covers one token, exact/tail chunks, multi-chunk causality, maximum prompt and matching unchunked semantics under the fixed tolerance/output contract. Refuse if even the smallest allowed width cannot fit. |
| E7 `runtime_device`, `runtime_execution` | Enable CUDA graph support in the recipe and keep pointer/shape lifetimes stable for backend capture/replay. Keep Metal fusion/graph optimization enabled under the controlled environment. Align owns no parallel native CUDA capture engine. | `gpu-backend-replay` checks eligible replay and safe backend uncaptured execution for ineligible shapes. Verify the shipped backend's constraints rather than assuming the CMake label guarantees arbitrary graph compatibility. Record a concrete backend limitation when reuse is unavailable. |
| E8 `runtime_execution`, sampler, qualifier | Host completion waits occur at needed logits, input-storage reuse and teardown. Asynchronous FFI copies use native-owned staging, never borrowed Align memory surviving a call. Keep CPU sampler/tokenizer semantics. Separate diagnostic replay from production as specified by G1. | `gpu-production-trace` detects per-layer fences, intermediate readbacks and accidentally enabled diagnostic markers. `gpu-native-owner` covers delayed completion, first fault, poison and reverse destruction. A single ordinary synchronous whole-graph call is a valid starting implementation. |

E1–E4, E6 and E8 are architectural work in G1, not optional future micro-optimizations. E5/E7
require a supported, qualified backend path or a recorded concrete capability limitation; an
unqualified feature cannot delay all independent work. No speedup is inferred from enabling a flag.
Actual optimization counters/traces are evidence for these owners, while schema-1 generation
qualification remains the correctness gate.

Growing KV length must not accidentally make E2 a rebuild-every-token policy. Use recipe-fixed
bounded KV-view buckets with an explicit valid-position mask where the pinned backend supports
them; reuse within a bucket, rebuild at its boundary, and never attend to uninitialized capacity.
`gpu-graph-reuse` includes several successive decode steps within one bucket and a boundary
crossing. Charge padded attention work to the measurement; using the maximum context for every
short decode is not assumed to be faster. If a backend requires exact-width views, record that
limitation and its rebuild cost rather than claiming successful steady-state graph reuse.

The whole-graph construction remains in Align's explicit model/execution modules; C wraps ggml
operations, resource ownership and bounded native staging. Calling `libllama` to generate on our
behalf is a useful external reference but would not deliver align-runtime's own execution policy.
When adapting upstream code, retain applicable MIT notices and attribution.

### Ownership closure

| Boundary | Construction/success | Failure, early exit and cleanup | Exact owner |
| --- | --- | --- | --- |
| full graph and GPU routing | bind full tensor set, route and reduce without host intervention | reject missing operation before upload; release a partial graph | `gpu-whole-graph`, `gpu-resident-moe` |
| two reusable graph slots | reserve once, mutate inputs only after completion | shape/buffer mismatch replaces one slot; reset destroys graph views before buffers | `gpu-graph-reuse`, `gpu-scheduler-reset` |
| KV and microbatches | device append, valid-prefix mask, final-row output | failed chunk invalidates the invocation; never publish partial text | `gpu-kv-in-place`, `gpu-prefill-chunks` |
| fused/captured execution | preselected supported path with stable buffers | no error-driven algorithm switch; drain/poison before Drop | `gpu-attention-policy`, `gpu-backend-replay`, `gpu-native-owner` |
| production/diagnostic execution | same identities/attention policy, production-only cost observations; already-read production logits and replay internals separately meet CPU tolerances | either path fails the case, including production-only fusion drift with unchanged generated IDs; separate owner state prevents replay contaminating production | `gpu-production-trace`, `gpu-result-replay` |

This matrix supplements G1's existing constructor/move/borrow/replacement/`?`/Drop and
whole-program/per-unit ownership coverage. All named tests are implementation targets, not claims
that those commands already exist.

## 4. Reusable coding session: G1R, immediately after G1

Request-local G1 remains useful for one-shot generation. Before a final comparison with a warm
llama-server, G1R must let the coding caller retain a model, tokenizer, device weights, admitted KV
capacity and graph reservations across its generate/validate/repair sequence. This is an
independently usable consumer boundary, not a process-global cache hidden in `ProviderConfig`.

G1R has an explicit caller-owned session and serial requests. Its first consumer is the existing
coding workflow; an internal session constructor alone is not the deliverable. Model/device/bundle
and memory ceilings are fixed at session construction. Mutable KV, RNG, prompt position and output
belong to one request; the RNG is reset from that request's declared seed. An owned prefix snapshot
may be reused only after a successful request boundary.

Reuse compares actual token prefixes and binds model/pack/geometry, tokenizer and template,
attention/KV layout, position/RoPE/mask policy, bundle/device and prefix contents. Changed suffixes
invalidate the old continuation; changed identity invalidates the entire prefix. A budget miss
evicts owned prefix state and recomputes within the same admitted budget. A malformed request leaves
the session unchanged; failed partial device work invalidates mutable KV, and an unsafe device
state poisons the session. Explicit release drains work and frees it exactly once. No cross-user
cache or persisted GPU pointers are introduced.

The first session uses one serial sequence and one reusable prefix, avoiding a general multi-tenant
server requirement. It keeps repository/system context stable and places changing task, diff and
test output in the suffix where the existing prompt semantics permit. Cache reuse must preserve
the intended prompt; it cannot omit relevant source or conceal a changed working tree.

The exact session API/consumer integration, token-prefix key, failure states and any exchanged
record belong in an extension of the authoritative G1 ledger before G1R code, within that same
implementation PR. It must include `gpu-session-reuse`, `gpu-prefix-invalidation`,
`gpu-session-second-after-failure` and a real multi-attempt coding owner. These details do not block
starting G1 and do not require another standalone design PR.

## 5. Candidate order and the place to win

| Priority | Work and owning capability | Why it is considered; condition for advancing |
| --- | --- | --- |
| First | G1 E1–E8 | Establish efficient resident generation using the same class of kernels and launch structure as the reference. Measure the remaining gap as soon as a real caller runs. |
| Next | G1R reusable coding session | Remove repeated load/upload/tokenizer preparation and repeated prefix evaluation across attempts. Both the candidate and llama-server get equivalent warm/cold opportunities. |
| Then, by measured cost | GPU KV precision/layout and sampling | Evaluate f16 KV and then q8/q4 only with a separate precision/quality contract; attention bandwidth/capacity must justify it. Consider GPU argmax or supported sampling only if full-logit readback/CPU sampling is material, preserving EOG, filters, RNG and seeded distribution. These are not prerequisites for G1. |
| First constrained-memory lane | G2 offload followed by G5 overlap | Start once G1 establishes correct device execution; do not wait for a resident speed win or extra vendors. Exploit measured expert/layer locality and bounded DRAM/AlignPack staging. Compare measured CPU execution cost with transfer plus GPU compute; full-resident models cannot benefit from needless offload. |
| For repetitive coding output | R9 speculative generation | Start with prompt lookup or an independently cheap draft; batch target verification, account for rejected work/KV rollback, and preserve target distribution. llama.cpp already has speculation, so it also gets a qualified configuration. This is an existing R9 goal, not a new requirement to implement every published draft architecture. |
| When real concurrency exists | multi-sequence batching | Continuous batching helps aggregate throughput but can hurt single-user latency. Add it only for a caller with concurrent requests, with an explicit fairness/memory contract. |
| Portability lane | G3 Vulkan and G4 HIP | Expand backend support independently; missing AMD hardware or an unimplemented extra vendor does not postpone the Metal/CUDA performance decision. |
| Last, on a measured kernel gap | specialized layout/kernel work | Reuse upstream improvements first. Add a custom kernel only when a reproducible model/shape bottleneck, an expected material end-to-end gain and a maintenance owner justify it. |

llama.cpp already implements many of these techniques. Our opportunity is not their mere presence,
but integration with stable repository context, short edit/repair sequences, known model shapes
and explicit memory/storage policy. Those are hypotheses until the end-to-end workload improves.
The existing architecture's small number of deeply supported models remains the scope.

### Constrained-memory design hypotheses

G2/G5 must address both weights exceeding VRAM but fitting in physical RAM, and weights exceeding
the admitted RAM working set and requiring NVMe. The latter needs a real larger-model consumer in
the G2/R10 pressure lane: select a concrete supported architecture/geometry and complete its loader,
packer, tokenizer, execution and quality owners together. A simulated smaller budget on today's
models is useful for correctness, but does not establish support for a larger model. Model-family
expansion is deliberately bounded; parameter count, quantized bytes and active MoE bytes are
reported separately.

| Mechanism / owner | Work worth testing | Required counter-evidence and safety |
| --- | --- | --- |
| placement and hot working set / G2 | Retain reused dense layers or experts in VRAM; keep a bounded DRAM cache; choose CPU compute versus staging plus GPU compute using measured costs. Include activation/KV transfers, not just weights. | Compare against tuned llama.cpp offload on the same workload; count misses and actual bytes on each tier. G1's no-host-routing rule applies to resident mode; hybrid routing boundaries are explicit and timed. |
| storage layout and demand reads / G2, R10 | Use AlignPack's independent expert/layer units, coalesced reads and reusable staging to avoid loading inactive experts or repeatedly decoding/repacking weights. | Include load/pack startup and steady-state I/O separately, OS page-cache residency, page faults and physical memory pressure. `mmap` size is not a physical-RAM saving; llama.cpp's demand paging is a real baseline capability. |
| transfer and read-ahead / G5, R10 | Pipeline known dense-layer demand; prioritize predicted expert reads by saved stall time, with bounded double buffers and cancellation. | Future MoE routes are not known exactly. Count misprediction bytes, cache pollution and waits; demand work has priority. Do not overlap operations that exceed PCIe/NVMe bandwidth or require unfinished routing results. Background owned-buffer tasks still wait for Request 41. |
| verified tokens per weight movement / R9 with G2/G5 | Verify a cheap draft or prompt-lookup sequence as a target batch, potentially amortizing streamed weights across accepted tokens. | Report acceptance, rejected compute/transfers, rollback and draft memory. Preserve target distribution; speculation can lose when draft cost or rejection dominates. No speed claim from proposed tokens that were not accepted. |
| KV working set / later precision capability | Evaluate bounded lower-precision KV and layout, especially when long context displaces model weights. | Keep context length and quality explicit. No silent sliding-window truncation, skipped experts, or reduced model precision to manufacture a speed/capacity win. |

Before tuning a streaming candidate, estimate its unavoidable service demand: actual uncached
bytes per generated token divided by measured sustainable NVMe/host/device bandwidth, alongside
compute demand. Overlap can hide independent stages, not remove their byte cost or dependency
chain. If the estimate already violates the useful-speed target, reduce the bytes/round trips or
change the declared supported model profile; do not expect prefetch alone to overcome that bound.
This is why expert locality and accepted multi-token verification deserve attention before tiny
operation-level savings. Dense and sparse models have separate results; a sparse-model advantage
does not imply that an arbitrary oversized dense model will be fast.

## 6. Measurement and iteration contract

Early measurements are diagnostic checkpoints inside the active implementation capability. They
do not each become a PR, extend ordinary CI, or demand a new evidence framework. G1's existing
record remains a correctness result with `decision=unmeasured`; performance measurements use a
separately precommitted campaign owned by the capability making the claim.

Every performance campaign fixes before implementation: candidate and baseline revisions/build
options, model/tokenizer/quantization, input prompts or tasks, context/output lengths, sampler and
seed schedule, memory ceilings, warm/cold and prefix-cache policy, ordered paired repetitions,
timeouts and attempt caps, quality predicate, metric/aggregation and a total execution-cost ceiling.
Use the owning capability's ledger for exact values and byte formats; do not reinterpret old
schema-1 timings or relax the corpus after a poor result.

Use two reference views:

1. A same-ggml-revision, same-model/settings comparison attributes graph/orchestration differences.
2. A current, pinned, properly configured llama.cpp baseline tests competitiveness. It may use
   supported Flash Attention, graph reuse, KV precision, prompt caching and speculation within the
   same hardware/memory/quality envelope. Do not force both to inefficient settings merely to
   simplify parity, and do not use the diagnostic-patched reference binary as the speed baseline.

Measure cold model-to-output time, warm prompt processing, warm decode at more than one context
depth, and the actual generate/validate/repair lifecycle. Report startup/load, tokenization,
prefill, graph preparation, device execution, transfer/wait, sampling and validation where useful;
overlapping times cannot be added as if disjoint. Host output correctness and GPU placement must
pass first. Exclude diagnostic tensor readbacks from timed production paths.

For the primary comparison, hold task content, context-selection policy, validator, sampling/attempt
limits and cache opportunity fixed. A separate declared system experiment may change prompt/context
selection, but then its quality and end-to-end effect must be evaluated for both systems. Schedule
the two GPU arms so they do not contend for the same memory/compute during a pair. Include cold
setup in cold results and amortize warm setup over the declared task sequence for both arms.

The first material-win floor is at least 15% lower paired latency (150,000 ppm); this is a floor,
not the ambition or a reason to stop improving. A 2x runtime speedup is a stretch objective on a
named constrained profile, not a forecast. A campaign must separately fix its runtime metric
(prefill, decode at specified context, or full fixed-output request) and aggregation before tuning.
Passing only prefill does not claim faster decode, and warm prefix reuse does not claim a faster
uncached kernel. G6 separately targets at least 15% lower median paired time to a passing patch,
with no reduction in task success under the same caps. Its implementation ledger must fix the
multi-task corpus, repeated paired schedule and uncertainty/robustness rule before measurement;
a noisy or single-task result cannot establish a material win. Failed or timed-out attempts remain
in the outcome and quality denominator rather than being dropped to improve latency. Runtime and
coding outcomes cannot compensate for one another or be collapsed into an ambiguous overall PASS.

A capacity campaign precommits its model/quantization/context ladder, RAM/VRAM/storage ceilings,
minimum accepted-token throughput, maximum first-token/request latency and quality criteria.
Measure the largest point each system actually meets; compare speed on common feasible points
separately. Both systems get tuned offload, KV and storage/cache settings within those limits.
An out-of-memory baseline is a capacity result, never an infinite speedup; a smaller quantization
or fewer active parameters is not the same-model speed comparison. Report installed physical RAM,
OS/driver use and page cache in addition to managed caps; shared Metal memory is counted once.
No universal claim that llama.cpp cannot run a model follows from one failed configuration.

A `not_met` result ends that candidate's experiment, not the program. Keep correctness-enabling
infrastructure; retain performance-only complexity only with its declared benefit. Use the measured
cost breakdown to pick the next material mechanism in §5, record one hypothesis and expected
recoverable cost, and test another coherent candidate. Multiple independent candidates are allowed.
Do not repeatedly tune on the same holdout; a new hypothesis uses development data and fresh
precommitted confirmation, while past negative results remain visible.

The program's final competitiveness decision is premature while a relevant known high-impact row
is merely unexamined. A row is covered when it ships with evidence, has a measured negative result,
has a concrete backend/quality/resource blocker, or is demonstrably irrelevant to the declared
workload. This is a bounded list of mechanisms, not a requirement to try every flag combination or
chase tiny isolated operations. A win is scoped to the tested workload and machine; continuing to
improve it does not imply superiority on all models, devices or serving workloads.

## 7. Implementation entry and verification

Start G1 now from this settled architecture. Inside that capability: probe pinned operations/build
settings; implement the owning resource plus complete Qwen graph; add device KV/reuse/prefill and
the OLMoE resident graph; connect the provider; then complete model-free owners and real Metal/CUDA
qualification. Local checkpoints may compile/test separately, but publication remains the complete
consumer. G1R follows before the final warm coding comparison. Extend future public contracts only
when their consumer is reached, without reopening G1's unrelated design.

The missing graph construction, Flash Attention wrapper, backend configuration and session policy
are application concerns using shipped ggml and Align FFI/resources. Current evidence does not
establish a new Align language gap. Request 41 still owns background tasks capturing owned I/O
buffers; device submission and same-thread work do not require that capability. Request 35 still
limits universal recoverable host OOM. Record any actual new language gap when a consumer reaches it.

This change runs documentation/source consistency, the unchanged schema-vector check and the docs
publication preflight, followed by one comprehensive review focused on architecture, ordering and
honest measurement. Native/GPU tests and speed measurements are N/A for this design-only PR.
