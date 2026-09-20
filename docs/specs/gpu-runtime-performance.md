# Runtime foundations and GPU performance plan

Current request (2026-09-14): investigate and design CUDA optimization enablement, without
implementation. [CUDA enablement](cuda-optimization-enablement.md) records the current ON/OFF
inventory, the missing Q/K/V optimizer opt-in and tensor names, the CUDA F16 prefill limitation,
and the proposed capability/qualification sequence. It owns that extension's contract; the
historical O1 scope and measurements below remain unchanged until actual CUDA acceptance.

Execution priority (2026-09-13): the user authorized resuming GPU performance work and selected
MoE. Product cutover implementation is complete; its publication remains a separate pending
checkpoint. The bounded diagnosis below selected O1, which now passes its local paired floor.
Existing Metal/CUDA correctness and historical negative performance results remain at their
qualified heads; O1 makes no new competitive llama.cpp or CUDA claim.

### Active entry: resident OLMoE diagnosis

The final CUDA campaign in `../gpu-cuda-final-measurement-result.md` completed all 16 comparisons
with no material win. OLMoE warm cached paired reductions against its frozen newer baseline were
-39.85% (short) and -64.66% (long). The different producer clock boundaries prevent assigning that
gap to GPU kernels. Metal also missed all 16 comparisons. Do not restart G1 or rebuild existing
session/prefix reuse merely because historical delivery prose still says planned.

The initial consumer is an unchanged resident OLMoE session executing the existing four runtime
requests in section 6.1. Diagnose that execution before selecting a kernel or scheduling change.
The local retained Metal kit and model are available; historical temporary candidate binaries are
absent, so rebuild the current exact source with the managed pin and existing manifested builder.
That is a new diagnostic subject, not a byte-identical historical replay.

| Diagnostic contract | Fixed boundary |
| --- | --- |
| Owner / entry | Existing `build-gpu-independent-candidate ... --session`, `gpu_session_client.Session`, and section 6.1 request definitions; macOS `sample` inspects the owned worker. No new product CLI, FFI, persisted schema or Python product driver. |
| Inputs / defaults | OLMoE from retained admitted Metal kit; resident MTL0, 1 GiB host / 6 GB device ceilings; unchanged system, short/long prompts, greedy selection, 128 output tokens, short/short/long/long order. One fresh session. No implicit alternate model/backend. |
| Cost ceiling | Build preparation at most 900 seconds; diagnostic execution at most 600 seconds, each request at most 120 seconds. Sample only the owned process, at 1 ms for at most 60 seconds. No competing candidate/baseline GPU arms. |
| Results / errors | Preserve manifested build/source/compiler/library identities, exact command and requests, complete responses, worker log and profiler output outside Git. Nonzero worker/profiler exit, timeout or invalid response is recorded as incomplete diagnosis; no performance decision. Keep startup separate from request observations. |
| Ownership / cleanup | The existing serial client owns worker pipes, bounded frames, deadlines and process-group cleanup. The diagnostic caller owns and waits for the sampler, including cancellation. No product allocation or ownership change. |
| Evidence / acceptance | Require all four responses to pass the existing integer-sequence and 128-token quality checks before using the run to choose a follow-on. Profiler samples locate host stacks; they do not measure kernel duration or CUDA capture/replay. A new runtime/coding comparison must use its own precommitted paired protocol and unchanged 15% floor. |
| Closure | Construction and early failure use the existing session client's cleanup. Successful execution retains all four responses. Failure retains the completed prefix and fault. Source/input identities are checked before and after execution. No cache/schema migration applies because this step changes no product code. |

Source candidates at `ad94eb5`: `runtime_generation.execute_session` hashes topology identities,
updates device inputs and reads the full logits per token; `align_gpu_graph_compute` walks the
graph and checks payload ownership around backend execution. Decode graph reuse already exists.
Profile before changing any of these, and preserve the session-specific MoE router expansion that
fixed CUDA fusion semantics. These are application/native integration concerns; no new Align gap
has been established. CUDA-specific capture/replay remains an actual RTX-host investigation.

The first host sample completed all four quality checks. Its main-thread graph-compute stack
dominates non-input-wait samples; topology hashing and input update are small by comparison.
This supports one further diagnostic on the same unchanged binary and four-request sequence:
use installed `xctrace` / Metal System Trace for at most 60 seconds, with an overall 600-second
execution ceiling, retaining the trace and exit/log evidence outside Git. It is profiling, not
a new benchmark or GPU-kernel speed claim. Keep profiler overhead and post-request idle explicit.
If tracing is unavailable or denied, retain that failure and do not infer per-kernel attribution
from CPU wait samples. The worker/trace process cleanup and input/build identity checks above
continue to apply. No kernel or submission intervention is selected from the host sample alone.

### O1: retained F16 attention KV for Metal OLMoE sessions

The subsequent counter-enabled trace in `../gpu-moe-diagnosis.md` identifies F32/F16 conversion
as the largest sampled shader category. Select this consumer before implementing a custom expert
kernel. The aim is to retain the representation already consumed by Flash Attention, avoiding
repeated conversion of the full valid history. Exact output equivalence is an acceptance target,
not an assumption that changing a storage type is harmless.

| Contract field | O1 decision |
| --- | --- |
| Consumer / default | Existing resident Metal OLMoE and Qwen2 serial sessions, when their admitted attention path is Flash. Align selects internal policy 2 after successful policy 1 selection and before shape planning. CUDA Qwen, single-shot, and decomposed attention retain their existing policy. No CLI option or response schema is added. |
| Internal policy / identity | `gpu_attention_select(owner,2)` requires the existing healthy pre-plan state and current policy 1; other invalid policies still refuse before mutation. `runtime_attention.fused` accepts 1/2; policy 2 is named `flash_f16_cached`, binding graph identities separately from `flash_f32`. No persisted device cache or cross-session identity reuse. |
| Storage / ownership | Policy 2 owns the same two KV planes per layer in the device owner, now F16 with the existing logical capacity and K-style layout for both K/V. Planning and final admission use the backend's exact aligned F16 allocation size, preserving the allocator's exact-consumption invariant and existing budget ceilings; do not claim a capacity increase. Planning, initialization, context reset and final cleanup share this policy. |
| Writes / reads | Prefill writes graph-produced F32 rows through supported in-place SET conversion into F16. Decode uses supported SET_ROWS with F32 source, I32 position and F16 destination. Only the newly written rows convert. Prefix views use actual element sizes and plane strides. F16 is accepted only for K-style writes; existing F32/transposed-V behavior remains valid. |
| Flash / padding | Flash accepts F32 or F16 K/V, validates each actual element stride and casts only F32 operands. Q, accumulation and output remain F32. A zero-padding F16 operation returns the existing tensor; positive padding widens to F32 before the pinned F32-only Metal padding kernel, then Flash performs its ordinary F16 conversion. This exceptional padded path is bounded and measured, not an invented F16 pad kernel. |
| Precision / failure | Preserve the existing rounding boundary at attention input; test actual backend SET/SET_ROWS conversion against full-view casting, including signed zero, finite rounding boundaries and overwritten prefixes. Keep exact serial outputs/counts, seeded behavior and failure poisoning. Unsupported operations fail during pre-upload planning; never switch algorithms after compute failure or relax oracle comparison. |
| Validation order / limits | Existing owner/state, kind/layout, scalar bounds, tensor types/shapes/strides, metadata capacity and operation support checks precede construction/execution. Extend only the named F16 paths. Preserve malformed-view, out-of-range index and metadata exhaustion refusal. |
| Owner modules | `runtime_attention`, `runtime_generation`, `runtime_kv` as needed, `ggml_ffi`, real/stub native shim; existing OLMoE builder consumes the typed prefix views. No new Align primitive or Python product execution. |
| Local acceptance | `run-gpu-attention-policy-smoke` extended with real F16 prefill/decode/padding and negative owners; `run-gpu-session-reuse-smoke` for existing decomposed/Qwen paths; managed real session build and `run-gpu-session-independent` unchanged full Metal sequence; existing host-capacity owner. Retain native real-precision observations rather than treating the deterministic stub as F16 math evidence. |
| Cost / measurement | Before timing, use a clean manifested build of unchanged `ad94eb5` as the local control and manifest the candidate. Both pass the shipping build verifier; additionally bind control checkout/commit/clean state and full source closure, equal managed pin/compiler, bundle and non-shim libraries before/after timing. The original diagnostic build is superseded after review identified its insufficient dirty-source authentication. Five alternating pairs, each fresh session executing the fixed four section 6.1 requests; require all output-quality checks and pairwise exact outputs/counts. Same model, kit, limits and host, no profiling during timing. Record startup separately and request wall/internal clocks separately. Build/owner preparation ceiling 3600 s per attempt; local paired experiment ceiling 2400 s. |
| Shipping interpretation | Local intervention target: at least 15% median paired request-wall reduction and four of five pairs faster for a declared case, with every pair retained. This does not claim superiority to llama.cpp or G6 completion. A competitive claim requires its separately declared contemporary baseline and coding wall-time gate. A failed local target remains NOT_MET and leads to the next material hypothesis. |

| Closure cell | Implementation / exact evidence |
| --- | --- |
| Construction / planning / success | Policy 1-to-2 before shape planning; matching real F16 KV initialization; real attention owner, then unchanged independent serial session owner. |
| Prefix reuse / replacement / tail | Real SET/SET_ROWS versus cast owner, including multiple prefill chunks, repeated decode indices and a changed suffix; existing full serial sequence covers caller reuse. |
| Malformed / early refusal | Real attention owner checks invalid policy transition, non-K F16 layout, wrong source type/stride, out-of-bounds prefix and exhausted graph metadata before execution. |
| Compute/readback failure / cleanup | Existing injected session reuse owner preserves poisoning and refuses further computation; existing native device owner releases graph/KV resources. No additional owner or background process is introduced. |
| Capacity / regression boundaries | Retain old reservation ceilings; existing host-capacity owner and real memory accounting. Single-shot G1 and CUDA Qwen selection remain policy 0/1; decomposed owners prove the selector boundary. |

This O1 ledger is the specific exception to historical F32 session-storage prose in the GPU
runtime design. Its single-shot G1 numeric/calibration formats remain unchanged. Author
consistency must map these cells to the final diff and passing evidence before review.

### Startup capped-read loader repair

The retained O1 startup diagnosis found that both resident weight loaders pass a full 16 MiB
staging buffer to `file.pread` and clip the upload only after the syscall. Align's `pread` uses
the buffer capacity as its request size, so the loader can fetch bytes beyond the current tensor
member or OLMoE expert piece. The accepted repair is limited to the two existing loader owners.

| Contract field | Settled decision |
| --- | --- |
| Consumer / default | Existing `runtime_qwen_load.load_file` and `runtime_olmoe_load.load_file` startup paths. The caller's `staging_bytes` value remains the only upper bound and default; no CLI, ABI, pack format or memory-policy option changes. |
| Read window | Keep the traversal cursors outside a capacity-epoch loop. At each epoch, compute `remaining = member_or_piece_bytes - done`, construct one local `chunk := buffer(window_bytes)` for `window_bytes = min(staging_bytes, remaining)`, and pass it directly to `pread`. Reuse it across consecutive reads, members and expert pieces while the capacity is equal; when it changes, finish the epoch so loop backedge cleanup drops the old local before the next epoch allocates its chunk. Preserve the existing pack-piece order, offsets, upload offsets and upload clipping. |
| Success / errors | Require a positive returned count no greater than `window_bytes`; upload exactly the returned prefix, then continue until the declared member or piece is complete. Preserve `pread` OS errors, zero-count/truncation refusal, upload failures, `runtime_weights` transaction state and cleanup. |
| Ownership / allocation | The epoch-local Align `buffer` is created inside the loop body and reused for that epoch's equal-capacity reads. Its loop backedge drops the old local before a later epoch constructs a different-capacity chunk; no assignment-based rebind is used. No buffer ABI, native runtime, async I/O, mmap, cache or kernel change is introduced. Capacity-epoch transitions and allocation cost are measured by the startup protocol. |
| Observer / owner tests | A test-only actual-`pread` observer is tied to the two existing Qwen/OLMoE loader smokes. It checks requested capacities and payload offsets against `min(staging_bytes, remaining)`, records returned counts, and exercises short-read/EOF/error refusal. It is not a generic I/O instrumentation framework; exact output/count equality belongs to the native session owner. |
| Performance cost ceiling | Reuse the O1 manifested-build discipline: 3,600 s for build/owner preparation per attempt and 900 s for the five-pair alternating startup experiment, with the existing 120 s native-session request deadline. No cache flush, profiler, async upload, mmap prototype or competing GPU arm. |
| Matched measurement | Use the clean accepted O1 runtime as control and the committed capped-read candidate as the other native Align session, with the same host, model kit, native framed-client options, placement and greedy request settings. Record readiness/startup and first-request/request clocks separately; require fixed exact output/count equality for every pair. |
| Interpretation | The OLMoE acceptance is at least 15% median per-pair fractional startup reduction with at least four of five candidate-faster pairs. Qwen is a guardrail and must stay within a 5% median regression. This evidence does not claim a llama.cpp comparison, CUDA result, whole-session speedup or time-to-passing-patch improvement. |

| Closure cell | Implementation / exact evidence |
| --- | --- |
| Construction / normal Qwen | Capacity epoch in `src/runtime_qwen_load.align`; existing Qwen loader smoke plus the actual-`pread` observer. |
| Construction / normal OLMoE | Capacity epoch in `src/runtime_olmoe_load.align`; existing OLMoE loader smoke plus the actual-`pread` observer. |
| Exact bytes / order | Existing pack plans and upload state remain unchanged; the observer checks requested capacities, payload offsets and returned-count ledgers, while the native session owner checks exact output/count equality. |
| Short read / EOF / error | Existing loader error path remains fail-closed; observer owner exercises short-read/truncated/error fixtures. |
| Startup / caller regression | Retained native Align startup driver, five alternating pairs per model, one fixed request per launch, exact response/count comparison and separate startup/first-request clocks. |

O1 qualification at `d60e2b6`: real attention owner PASS (including malformed inputs and metadata
exhaustion); session reuse owner PASS (including injected compute/readback failure); unchanged
independent Metal sequence PASS all 16 requests; allocation-count session host-capacity owner
PASS both models. These cover the matrix's construction, prefix replacement, malformed, cleanup
and capacity cells without changing the single-shot/CUDA selector. All five local pairs preserve
exact outputs/counts and clear the 15% floor in all four cases. The complete measurement and
source-bound evidence are in `../gpu-moe-diagnosis.md`; competitive G6 and coding wall-time
qualification remain separate.

Historical foundation status: design and evidence synthesis, 2026-09-06. The O1 section above
adds local intervention measurements; it does not establish a competitive llama.cpp, CUDA or
capacity improvement. Historical CPU results below retain their original owners and scopes.

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
Actual optimization counters/traces are evidence for these owners. The complete same-policy
independent GPU acceptance corpus and relocated replay in `gpu-runtime.md` own shipping correctness;
historical schema-1 CPU/GPU FAILs and their frozen tolerances remain historical evidence.

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

### 6.1 First resident session campaign (Metal, then final CUDA)

This campaign measures the completed G1/G1R resident consumer. It does not implement G2–G6 or
make a capacity claim. Negative or incomparable results remain results; the user-requested stop
is the prepared final CUDA correctness/measurement handoff, before subsequent optimization work.

| Contract | Frozen value |
| --- | --- |
| Owner / CLI | `scripts/run-gpu-session-measurement --profile PROFILE --runtime CANDIDATE/main --same-server SAME/llama-server --current-server CURRENT/llama-server --output NEW_DIRECTORY`; schema 1 JSON receipt plus per-arm logs and request/response records. The output must be outside the source checkout. No existing output is overwritten. |
| Candidate / references | G1R production executable from `12a633d` (or a descendant with identical runtime source, identified by its build manifest). Same-ggml unmodified llama.cpp `bb4caa7540188872173c44d161602d9271386413`; current unmodified llama.cpp `304665fe7ac957df95e3ff8c8c4ffdf92dd6ffa3`. Release builds, CPU and the declared GPU backend enabled; no diagnostic tensor readbacks. Capture executable, local library and CMake-cache hashes before execution and recheck afterward. |
| Inputs / admission | Existing fully admitted G1 profile with exactly Qwen and OLMoE and one resident/prefetch-off option. Model, pack, geometry, tokenizer and bundle identities come from that profile. The candidate must have passed independent session qualification and actual coding retries before timing. Both references use the same original GGUF files. All executable paths are absolute. |
| Baseline policy | One serial server slot, all model layers on the selected GPU, context 2304, batch 2048, microbatch 128, 4 CPU threads, Flash Attention on, no startup warmup or context shifting. Same-ggml uses F32 K/V; current uses F16 K/V. Both receive equivalent prompt-cache opportunities. No external draft model or concurrent requests. These are two explicitly configured resident baselines, not a claim of exhaustive upstream tuning. |
| Resource envelope | Same physical machine and original Q4_K_M weights. Candidate uses a 1-GiB host reservation ceiling and 6,000,000,000-byte GPU ceiling. The admitted profile must allow at least these values, and its legacy expert-cache ceiling must fit 1 GiB. Larger profile ceilings are lowered only in the measurement's owned options file; the retained kit is unchanged. Record host/GPU identity and total memory, baseline placement/allocation logs and context/KV settings. Shared Metal memory is counted once; OS/page-cache use is not an application allocation. This campaign makes no comparative memory-capacity or managed-host-allocation claim for llama.cpp. |
| Fixed runtime requests | System: `You are a helpful assistant. Follow the output format exactly.` Short user: `List the integers from 1 through 500 in ascending order, separated by single spaces. Output only the integers.` Long user prefixes that exact short user with `Repository context (irrelevant to this formatting task):\n` followed by exactly 128 repetitions of `alpha beta gamma delta\n` and one extra newline. Temperature 0, no seed, maximum 128 tokens. No EOS suppression or tokenizer changes. |
| Runtime sequence / cache | In each fresh arm: short (cold), same short (warm cached), long (warm changed prefix), same long (warm cached). Each system keeps exactly one reusable prefix within that sequence. Cold latency begins before worker/server construction and ends at the first complete response; other request clocks cover caller submission through complete response. Release the arm before the next system starts. Record startup separately; it is already included in cold latency. |
| Runtime quality / comparison | A response must contain only whitespace-separated ascending integers starting at 1, at least 16 complete integers, and exactly 128 completion tokens. A trailing incomplete integer may be removed only when it is a prefix of the next expected integer. Failure, early EOS, timeout or count mismatch stays in the denominator and prevents a material-win decision for that model/case. This synthetic fixed-output workload diagnoses runtime latency; it is not coding quality. |
| Coding lifecycle | A separate fresh session/server per arm runs the existing `python-inclusive-range` task, original prompt, strict patch extractor and actual validator, with at most 8 attempts and the same actual-feedback repair prompt. Qwen is greedy; OLMoE temperature 0.3 uses seeds 1..8 with top-k 40, top-p 0.95, min-p 0.05, then temperature, with repetition penalties disabled. Each implementation retains its shipped RNG; equal seed numbers do not promise identical samples. Maximum 128 output tokens. The validator's known-good control runs before timed portfolios. Include worker/server startup, generation, retries and actual validation in time to a passing patch. Every failed attempt remains recorded. |
| Ordered paired repetitions | Models in order Qwen, OLMoE. Five repetitions per model; system order is `[candidate,same,current]`, `[same,current,candidate]`, `[current,candidate,same]`, `[current,same,candidate]`, `[candidate,current,same]`. Each arm completes its runtime sequence and coding portfolio before release. GPU arms never overlap. No other benchmark, compiler or qualification runs during timing. |
| Metrics / decision | Report every raw latency and count; median paired percentage reduction `(reference-candidate)/reference` separately for each model, runtime case and reference. A named runtime case clears the material floor only if all ten responses pass quality, median paired reduction is at least 15%, and at least four of five pairs are faster. No averaging across models/cases hides a regression. Coding reports successes/attempts and paired times, but this single-task campaign cannot establish G6's multi-task material-win gate. |
| Bounds / failures | Entire campaign at most 7200 seconds, each construction/request at most 300 seconds, baseline health requests at most 2 seconds, normal cleanup 10 seconds then TERM/KILL and reap. Retain at most 16 MiB of logs per arm; a larger log fails the arm rather than yielding valid timing evidence. Malformed admission creates no output. SIGINT/SIGTERM tear down owned workers and retain a failure receipt. After execution starts, publish available records and explicit failure on an ordinary exception; never turn missing rows into PASS. No automatic retuning or rerun replaces a negative result. |
| Evidence / schema | Receipt fields: schema_version=1, artifact_kind=GPU_SESSION_MEASUREMENT, status=PASS or FAIL (execution completeness), decision=measured or incomplete, identities, policy, arms, comparisons, failure, elapsed_ns. Runtime comparison decisions are met, not_met or invalid_quality independently of execution completeness. The campaign requires a clean committed source and records/rechecks its executable-source closure and plan digest. Paths are local execution inputs; hashes and frozen revisions identify the measured artifacts. This is an inspectable campaign receipt, not G1's relocated tensor-replay format. |
| Closure / owner tests | `run-gpu-session-measurement-smoke` covers model/identity admission, fixed order/counts, integer-quality boundaries, paired aggregation with failed/missing rows, HTTP response validation and bounded process cleanup. Real Metal is the named platform/performance owner; final CUDA uses the same campaign after its correctness owners pass. |

| Boundary | Construction/success owner | Refusal/failure/cleanup owner |
| --- | --- | --- |
| Candidate and baseline admission | `baseline_identity`, existing `verify_build` and profile admission bind pinned sources, weights and configuration | `run-gpu-session-measurement-smoke` rejects missing models, wrong revision, dirty baseline and changed binary; post-run source/identity mismatch invalidates every comparison |
| Serial worker/server | `service`, `Server`, existing `Session` retain one arm at a time and record actual commands | HTTP deadline owner, nonzero shutdown owner, context-manager cancellation teardown; close/reap before the next arm |
| Runtime/coding outcomes | `runtime_sequence`, `coding_portfolio` keep fixed request order and every attempt; existing patch extractor/validator own useful success | Integer-quality boundary owner and actual validator refusal remain outcomes; an execution exception retains partial rows and incomplete status |
| Aggregation and publication | `comparison` requires all five pairs for the named model/case/reference | Missing, duplicate, failed-quality and inconsistent rows cannot meet a floor; no median silently omits a failed coding portfolio |

The author consistency pass binds the prompts, schedule, bounds, sampler and decision rules above
to the implementation before the first timing run. A changed runtime hypothesis requires a new
campaign; bookkeeping or a broken harness is repaired transparently without discarding prior output.

### 6.2 Final CUDA comparison without model transport time

The user's final comparison request supersedes the earlier stop after the CUDA repair. This is a
new, precommitted campaign, not a rerun or replacement of the historical Metal measurement.
Run the complete comparison and publish negative/quality-limited outcomes without further tuning.

| Contract | Frozen value |
| --- | --- |
| Owner / CLI / receipt | The §6.1 command with `--campaign cuda-final`; schema 2 `GPU_SESSION_MEASUREMENT`. Default `--campaign original` retains §6.1 behavior and schema 1. Same fresh external output ownership, identity rechecks, failure retention and cleanup as §6.1. |
| Candidate / prerequisites | CUDA only, repaired runtime `688232c665aafca3cdff940e9e34eac5c7f0509e` or a manifested descendant with identical runtime sources. Its G1 19×2, session 16/16 and both host-capacity qualifications pass; receipts are in `docs/gpu-cuda-session-repair.md`. The known coding-retry quality failure is a recorded outcome, not an execution prerequisite for this campaign. No correctness threshold or coding task is relaxed. |
| Inputs / references / limits | Exactly §6.1 models, original GGUFs, two unmodified upstream revisions, resource ceilings, prompts, sampler, quality rule, four ordered runtime cases, eight-attempt coding portfolio and five paired system orders. Thirty serial arms, at most 7200 seconds total and 300 seconds per request/construction; no competing GPU or compiler work. |
| Runtime metric | Reported internal processing latency, excluding model request/response transport and service construction. Candidate: existing worker `elapsed_ns`, starting after its complete request frame is read and ending before response serialization/transport. References: unmodified server response `timings.prompt_ms + timings.predicted_ms`, converted to nanoseconds. Preserve raw timings and token counts. All components must be finite, nonnegative numbers; total must be positive. Missing/invalid clocks invalidate the campaign, never fall back to caller wall time. |
| Metric limits | Candidate includes request decoding/tokenization and CPU sampling; llama.cpp's slot clocks cover prompt processing and generation but exclude HTTP handling and some preparation. These are producer-reported internal service clocks, not identical instruction boundaries or pure GPU kernel timings. The asymmetry can penalize the candidate; report it with every conclusion. Do not claim end-to-end request latency or transport-normalized exact parity. No subtraction of estimated network latency is permitted. |
| Cold / warm | Keep the §6.1 sequence; `cold-short` is the first request in a fresh ready service, with empty KV state. Its internal latency excludes model loading/startup. Record construction-to-ready wall time separately as operational context, never combine it into the internal comparison or material-floor decision. |
| Coding metric | Retain every attempt and actual native validation. Report success counts, attempts and `processing_to_passing_patch_ns`: sum of each attempt's internal generation time plus the existing native validator's measured wall time through the first passing patch. This includes validation process/filesystem work, excludes model transport, service startup and caller orchestration, and is not wall time to a passing patch. Failed portfolios keep null latency; no successful-only average hides failures. Use the native validator, whose known-good control must pass. |
| Decisions | §6.1 paired runtime rule unchanged: all five pairs pass quality, median paired reduction at least 15%, at least four pairs faster. Runtime decisions are independent of coding success. Coding pair reductions exist only when both portfolios pass; report a median only when all five pairs exist. A measured negative or incomparable result completes this experiment; it does not qualify failed quality or claim G6 success. |
| Identity / validation order | Admit profile and CUDA backend, bind the selected candidate and both baselines, require clean campaign source, then capture host/plan/validator identities before any arm. Record `policy.campaign` and `policy.timing_basis`. No new runtime API, allocator, cache format or network endpoint; all such ownership remains with §6.1. |

| Closure | Implementation / acceptance |
| --- | --- |
| Construction and successful clocks | `run`, `Server.generate`, `internal_elapsed_ns`, `runtime_sequence`, `coding_portfolio`; measurement smoke exercises baseline/candidate clocks and delayed transport independently of internal time. |
| Malformed clocks and unsupported backend | Measurement smoke rejects missing clocks, bools, negative/nonfinite/zero totals and non-CUDA final admission; no external output on admission refusal. |
| Quality failure and aggregation | Existing integer-quality, missing/duplicate pair owners remain; a failed coding portfolio retains attempts and null processing time while runtime comparison remains available. |
| Early exit, deadline and cleanup | Existing real HTTP timeout, abnormal shutdown and cancellation owners remain; no timing fallback or change to owned service teardown. |

Author consistency pass: §6.2 reuses the settled workload and bounds, nominates only the qualified
repair, explicitly separates internal clocks from transport/startup, and records quality failure
without suppressing the independently valid runtime comparison. Review the harness before timing.

### 6.3 CUDA current-tree comparison (2026-09-20)

§6.2's result is a frozen historical measurement of runtime `688232c`. It is stale as a statement
about the shipping tree: `688232c..d4438e3` contains 32 `src/` commits, including retained F16
attention KV for OLMoE on Metal (`d60e2b6`) and for Qwen (`234b7fc`), the capped-read resident loader repair
(`594981c`), the GPU dispatch/caching/sampling optimization (`5efd7a0`), the PR #243 CUDA retained
half KV with validated indexed prefill (`ae6eac7`, `2f1b69c`, `1342274`) and Qwen F16 KV policy 2 on
CUDA (`ba9ea4f`). §6.2's OLMoE construction-to-ready median of 16,483 ms is a pre-`594981c` loader
artifact and is separately explained by the capped-read startup measurement in
`cuda-optimization-enablement.md`, which measured OLMoE startup 17.125 s to 1.669 s on CUDA; it is
not evidence about the current loader. This is therefore a new precommitted campaign, not a rerun,
retune or replacement of §6.2, whose nomination, receipt and published result stay frozen.

| Contract | Frozen value |
| --- | --- |
| Owner / CLI / receipt | The §6.1 command with `--campaign cuda-current`; schema 2 `GPU_SESSION_MEASUREMENT`, distinguished from §6.2 only by `policy.campaign`. `--campaign cuda-final` and `--campaign original` are unchanged. Fresh external output directory, whose parent exists and whose leaf does not; identity rechecks, failure retention and cleanup exactly as §6.1. |
| Candidate / nomination | New driver constant `CUDA_CURRENT_CANDIDATE = d4438e313c59a71a11d0a65ed1735425a0e014e8`, selected through `NOMINATION[args.campaign]`. `CUDA_CANDIDATE` is not edited, and `688232c` ancestry is retained transitively because `d4438e3` descends from it. The candidate is the clean committed head of `agent/parity-minor-batch` that adds, on top of `d4438e3`, only documentation (this paragraph and the pointer added to `cuda-optimization-enablement.md`) and the `cuda-current` driver/smoke change, so its `src/`, `.align-revision` and `scripts/ggml_shim.c` content equals `d4438e3` and the existing frozen-source closure admits it unchanged. Build it with `scripts/build-gpu-independent-candidate PINNED_GGML KIT_PROFILE OUT --session`; `verify_build` already refuses a dirty build. |
| Protocol / references / limits | Exactly §6.1 and §6.2: both retained unmodified `llama-server` baselines (same-ggml `bb4caa7540188872173c44d161602d9271386413` with F32 K/V, current `304665fe7ac957df95e3ff8c8c4ffdf92dd6ffa3` with F16 K/V), original Q4_K_M Qwen and OLMoE, the `cuda-kit-28a6fe3` profile's single resident/prefetch-off CUDA option, 1-GiB host and 6,000,000,000-byte GPU ceilings, context 2304, batch 2048, microbatch 128, four baseline CPU threads, Flash Attention on, no startup warmup or context shifting, the fixed system/short/long requests, 128 output tokens, the four ordered runtime cases, the eight-attempt native-validated coding portfolio, and five paired repetitions in the fixed rotated system order over 30 serial arms. |
| Runtime metric / decision | §6.2's request-level producer internal clocks unchanged: candidate worker `elapsed_ns`, baselines `timings.prompt_ms + timings.predicted_ms`. Missing or invalid clocks invalidate the campaign and never fall back to caller wall time. A named model/case/reference clears the material floor only when all ten responses pass the fixed-output quality rule, the median paired reduction `(reference-candidate)/reference` is at least 15%, and at least four of five pairs are faster. Construction-to-ready wall time is recorded as operational context only. Coding reports successes, attempts and `processing_to_passing_patch_ns`, with null latency for failed portfolios. |
| Cost ceiling | As §6.2: at most 7200 seconds for the whole campaign and 300 seconds per construction or request. §6.2's 30 arms took 517.206 seconds; the capped-read loader removes most of OLMoE's former construction time, so this campaign is expected to finish well inside the same ceiling. One run only; a negative or incomparable result completes it. |
| Host quiet | `run-gpu-session-measurement` records host and GPU inventory but has **no** foreign-load admission of its own; unlike `measure-cuda-optimization`, it cannot refuse a busy host. "No other benchmark, compiler or qualification runs during timing" therefore remains an operator obligation evidenced outside the receipt. Prefer a plain terminal with no agent session. If a Claude Code session is present it is the only permitted background process: its idle load of 0.14–0.35 cores stays below the 0.5-core busy threshold of the shared-host constraint but exceeded the external observer's 0.1-core rule that invalidated the P1 and P2 receipts, so the result note records its presence, and no other benchmark, build, compiler or qualification runs during timing. |
| Evidence binding | The receipt binds `identities.candidate` (build manifest with `source_commit`, `source_dirty` and the full source closure), `identities.campaign_commit`, `identities.campaign_source`, `plan_sha256`, both baseline `cmake_cache_sha256`/executable digests, the profile digest and the host snapshot, and rechecks all of them after the last arm. The driver enforces `merge-base --is-ancestor` plus byte equality for `src/`, `.align-revision` and `scripts/ggml_shim.c` at the nomination; it does not enforce `candidate.source_commit == campaign_commit`, so a reader confirms from the receipt that both name the campaign head. |

Interpretation limits carry over unchanged and must accompany every conclusion. The two clocks are
producer-reported service clocks with different boundaries: the candidate's includes request
decoding, tokenization and CPU sampling, while llama.cpp's slot clocks exclude HTTP handling and
some preparation. The asymmetry can penalize the candidate. These are not identical instruction
boundaries, pure GPU-kernel timings or end-to-end request latency, and no estimated transport is
subtracted. The result is scoped to this host, these two Q4_K_M models, this synthetic fixed-output
workload and this single coding task; it establishes neither G6 coding competitiveness nor a
capacity claim, and a comparison against these two explicitly configured baselines is not a claim of
exhaustive upstream tuning. The frozen-source closure covers `src/`, `.align-revision` and
`scripts/ggml_shim.c` only; other build inputs are bound by the recorded and rechecked campaign and
candidate source closures rather than by the nomination. Because the nomination pins a commit id, a
rebase of this branch invalidates it and requires updating both the constant and this paragraph
before any run.

Author consistency pass: §6.3 changes only the nominated candidate and adds a separate campaign
name; workload, baselines, bounds, sampler, clocks, quality rule and decision rule are byte-for-byte
the §6.1/§6.2 values implemented in the same code paths. `run-gpu-session-measurement-smoke` owns
the new campaign's predicate, nomination selection and non-CUDA admission refusal.

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

The campaign receipt also retains the resolved coding-validator identity (native execution or the immutable Docker image ID), because validation contributes to time to a passing patch. The original Metal receipt predates that field; its separately hashed Docker-event supplement is documented in `docs/gpu-metal-campaign-result.md` without rewriting the measured artifact.
