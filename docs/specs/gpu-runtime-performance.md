# Runtime foundations and GPU performance plan

## Current inference optimization policy (2026-09-26)

The objective is an Align-owned fast inference engine spanning Qwen and Gemma
generations, sizes, and architectures. Qwen3.5-2B is the current real-model
validation target, not a permanent architecture limit. Align owns model semantics,
execution plans, specialization selection, memory policy, sessions, and generation.
Device kernels and thin host/ABI connections may use Metal/CUDA/C/C++; Python stays
in independent validation and developer tooling.

There is no mandatory percentage improvement for starting an experiment, integrating
it with a real model, or adopting it. The former 15% floor and fixed win-count
admission rule are withdrawn, without substituting another universal percentage.
Historical measurements and decisions remain historical evidence. An experiment
needs a concrete hypothesis and test; trial integration needs credible local
correctness and a reason to measure the real boundary; adoption needs demonstrated
useful effect, correctness, uncertainty, workload coverage, regression, memory and
maintenance assessment. Whole-request evidence is produced by trial integration;
it is never a prerequisite for permitting that integration.
For a continuing independent GPU path, retain a correct native baseline and
compare each revision with that baseline as well as ggml. A reproducible
incremental native gain may be retained even while the native path remains
slower than ggml; a local ggml loss does not bar guarded real-model trial
integration. Default routing decisions still use complete request evidence.

GGML is one implementation option. Reuse, modify, fuse, or replace operations,
buffer management, scheduling, or a whole execution path when supported by an
experiment. Keep the established path for comparison and compatibility during
migration. No permanent ggml dependency is required for new paths. Single-kernel
losses do not establish a ceiling for independent backends.

Keep model semantics, operation/fusion patterns, and device implementations
separate. Select specializations by shape, quantization, activation, layout, token
count, and device capability. Preserve architecture-specific normalization,
attention, position representation and activation; Gemma is not a shape alias of
Qwen. Extend existing Model IR only when a real consumer needs it.

Predeclare numerical tolerances and cost ceilings. Keep exact compatibility
owners; label rounding-changing trials explicitly. Compare unchanged Align,
candidate Align, and pinned llama.cpp with identical weights, prompt IDs and
actual generation work. Retain all alternating paired samples after warm-up;
report local, connected, prefill, decode, whole-request, startup/load and memory
separately. Do not infer request gains from isolated kernels or change tolerance
after observing failures.

This section supersedes historical percentage-based admission/shipping prose
elsewhere in this repository. Historical receipts must not be rewritten.

### Native CUDA Q4_0 FFN screen (2026-09-29)

The CUDA host has an RTX 4070 Ti. At the start of this capability the Qwen3.5
session and its real-model correctness owner admitted Metal only. Test the
independent Q4_0 gate/up/SwiGLU/down kernel on CUDA before changing admission.
The pinned ggml CUDA graph remains the control and the product default.

| Contract | Definition |
| --- | --- |
| Consumer and selection | `scripts/run-native-cuda-q4-ffn-screen GGML_SOURCE GGML_LIB GGML_CUDA_PLUGIN` builds and runs the independent CUDA screen. No product flag, public inference API, cache or persisted schema is added (`N/A`: no product adoption at this stage). The runner requires three explicit pinned inputs and writes no model artifact. |
| Inputs and outputs | Q4_0 matrices with dimensions 2048×6144, 2048×6144 and 6144×2048, plus one F32 input row. The owner generates deterministic packed Q4_0 weights and an F32 activation, uploads one quantized copy per matrix, and compares every intermediate and final F32 result with the same-source ggml CUDA graph. Shape and format are checked before launch. The result prints host/device identity, maximum absolute error, and five alternating per-arm pairs. |
| Ownership and errors | The native CUDA helper owns its stream and scratch/output buffers; the caller owns weights and input. The ggml backend owns its separate graph and buffers. On CUDA allocation, launch, synchronization, numerical or ggml failure the screen exits nonzero and emits no performance verdict. All allocations and the stream are released on exit. No pointer is retained by the helper after its call. |
| Numerical and measurement gate | Require finite native values and each element to satisfy `abs(native - ggml) <= 0.005 + 0.0005 * abs(ggml)` before timing. Warm both arms 12 times, then run five alternating pairs of 20 complete FFNs, including device completion in both timings. Record all pairs; report a local result, never a request or llama.cpp speed claim. Preparation <=900 s, measurement <=120 s, and device scratch <=32 KiB beyond its F32 intermediate and final outputs. |
| Later consumer | The real Qwen3.5 CUDA session is admitted separately below. This FFN screen lost complete local comparisons and has no product selection. A future FFN specialization needs real weights, exact logits/state parity, failure and cleanup owners, then paired complete requests against unchanged Align and pinned llama.cpp before enabling it. A local loss or gain alone cannot decide product adoption. |

| Closure case | Owner |
| --- | --- |
| Construction / malformed input | Runner argument/path checks; helper rejects unsupported dimensions and null pointers. |
| Success / repeated execution | Screen compares complete intermediate and final rows before and after warmup, then checks both arms after every measured pair. |
| Failure / early exit | Every CUDA and ggml status is checked; failed execution stops before a speed verdict. |
| Cleanup | Helper releases stream/scratch on every return; screen frees its separate CUDA and ggml allocations. |

### Native CUDA recurrent-state copy trial (2026-09-29)

Once the ordinary CUDA Qwen3.5 session passes the real-model owner, reuse its
existing `ALIGN_LLM_NATIVE_STATE_COPY=1` selection for a CUDA device copy of
contiguous DeltaNet state. The Metal route and the `0`/absent ggml route keep
their current semantics. This trial does not depend on the standalone FFN
screen's speed result.

| Contract | Definition |
| --- | --- |
| Public selection | The existing `ALIGN_LLM_NATIVE_STATE_COPY` variable admits `0` (default ggml graph) and `1` (device copy) for a Qwen3.5 resident CUDA session. Invalid values or an unavailable native CUDA build fail before weight upload. The shim's existing state-copy ABI and graph-kind registration are reused. No new options, result, model, cache or pack schema (`N/A`: all are unchanged). |
| Operation | On decode graph construction, Align registers each complete contiguous F32 DeltaNet next-state source and equally shaped resident destination. The ggml graph produces the source and all other model operations; it omits only those registered ggml `CPY` nodes. After synchronous ggml graph compute, the native CUDA module submits checked device-to-device copies on one owned stream. Align waits before state parity, next dependent graph or token publication. Prefill and strided convolution copies stay on ggml. |
| Ownership and validation | ggml owns source workspace and destination KV allocations. The native module borrows bounded pointers, owns only the CUDA stream and retains no state payload. Require selected sole `CUDA0`, CUDA buffer types, in-buffer extents, equal shape/bytes, nonoverlap and at most 64 registered pairs. Workspace rebuild, invalidation and close drain the stream before ggml frees memory. A submission/completion fault poisons the request; no error-driven fallback. |
| Acceptance and cost | Actual 2B CUDA 31/200/330-token generation and repeated-session outputs must match the pinned llama.cpp oracle; compare all active recurrent-state planes and complete logits against mode `0` before timing. Run forced submission/completion failures with no published token. Then measure unchanged ggml mode, native mode and pinned llama.cpp in five alternating request pairs for each length. Build/owner preparation <=3600 s, each paired campaign <=900 s, each request <=180 s. Native module reserves no model-sized buffer. |

| Closure case | Owner |
| --- | --- |
| Construction / invalid mode / allocation | Qwen3.5 config reader, native device admission and real session owner. |
| Success / repeated requests | Real CUDA provider/session oracle, complete logits and state comparison, five-pair request measurement. |
| Malformed registration / changed graph | Real-shim native copy owner with wrong extent, duplicate destination and invalidation after pending work. |
| Submit/completion failure / early exit / cleanup | Injected real-shim owner; native stream drain and reverse device teardown. |

**RTX 4070 Ti result.** The authenticated 2B owner passed exact normal/native
full-logit and valid-state hashes at all three prompt lengths, repeated exact
generated IDs against pinned llama.cpp, default and native generation/serving,
and injected submission/completion failures. A batched CUDA copy reduced traced
copy submissions, but two preliminary five-pair campaigns at each of 56/16,
200/32 and 330/64 won only 12/30 native versus ordinary Align pairs. The
reference-executable-digest-bound repeat won 5/15 against ordinary Align and
13/15 against pinned llama.cpp. Keep the selection
default-off. Conditions and failed variants are in
`docs/cuda-native-optimization-log.md`; other CUDA hosts and models remain
unmeasured.

### Independent CUDA Q6_K four-column output-head screen (2026-09-29)

The ordinary CUDA 200/32 trace has 32 full-vocabulary Q6_K projections. The
first belongs to final prefill and the remaining 31 to decode. The pinned
kernel's median interval is about 0.885 ms for a 417,177,600-byte weight.
Metal's independent four-column Q6_K attempt was correct but lost its complete
operation comparison, so CUDA must test actual bytes and completed work before
any graph connection. This developer screen tests compressed-weight reuse over
four activations; it does not select product inference.

| Contract | Definition |
| --- | --- |
| Consumer and selection | `scripts/run-native-cuda-q6-batch4-screen GGML_SOURCE GGML_BUNDLE CAPTURE_DIR` builds the independent CUDA probe against the pinned ggml headers and libraries and runs it with an explicit CUDA plugin. The real-model capture is produced separately by `scripts/capture-q6-projection.c` with `LD_PRELOAD`; capture never runs during timing. No product flag, API, cache, schema or persistent model format changes (`N/A`: developer-only screen). |
| Inputs and results | Require the `q6-capture-v1` geometry of 2,048 inputs and 248,320 outputs, exactly 417,177,600 packed Q6_K weight bytes, and three finite 2,048-element F32 activations plus their complete captured outputs. Form a fourth column by repeating the first input. Compare every output of pinned ggml's four-column graph and the native CUDA kernel to the corresponding single-column captured output, and compare their greedy indices. Report the model weight digest, CUDA device, every alternating pair, numeric maximum and per-arm complete-operation medians. |
| Ownership and failure | The probe owns one independent CUDA stream and quantized weight, input and output device allocations; the pinned ggml backend owns a separate buffer and graph. No allocation crosses the two arms. Reject missing/malformed capture, unsupported device/geometry, launch or synchronization failure, nonfinite/mismatched result before any timing verdict. Release all buffers and stream on normal exit. The capture helper never changes the real model's selected path and fails on ambiguous projection or stale session weights. |
| Numeric and cost ceiling | Predeclare `abs(candidate - captured) <= 0.01` for every F32 logit, with an exact lowest-index greedy choice; this allows rounding changes but no output disagreement outside that bound. Keep one quantized 417 MB weight per arm, no dequantized weight or model-sized scratch, and <=16 MiB per-arm activation/output memory. After 12 warmups, measure five alternating pairs of 20 complete operations with device completion, all samples retained. Preparation <=900 s, measurement <=120 s. This correct independent kernel is a baseline for an opt-in connected real-model trial even if its local timing loses to ggml. Compare each improvement with the preceding independent kernel as well as unchanged ggml. Product default selection needs accepted logits/state, failure/cleanup and paired whole requests against ordinary Align and pinned llama.cpp, with no fixed improvement percentage. |

| Closure case | Owner |
| --- | --- |
| Construction and malformed capture | Probe validates geometry, exact file sizes and finite inputs before device work; capture refuses ambiguous/missing real projection. |
| Success and repeated execution | Complete captured-output/ggml/native F32 and greedy checks before and after warmup and after every pair. |
| Launch, synchronization and early failure | Checked CUDA and ggml status; no timing verdict after failure. |
| Cleanup | Independent stream and allocations are released after complete probe; process exit also covers fail-fast diagnostic paths. |

**RTX 4070 Ti result.** The Linux capture recovered the same 417,177,600-byte
weight digest as the earlier Metal capture. Its three activation values came
from this CUDA host and passed complete four-column output and greedy checks.
The F32-direct first mapping failed the predeclared `0.01` absolute bound,
because the pinned CUDA path converts activations to Q8_1. After the CUDA
probe implemented that conversion, its best DP4A mapping reached a maximum
absolute difference of `1.91e-6` across all four full output columns. Five
alternating complete-operation pairs yielded a median paired native gain of
`-0.004725 ms` and only two native wins. The final source owner repeat lost
all five pairs with `-0.033346 ms` median paired gain. A second mapping with
two rows per warp also lost all five pairs. This screen alone does not change
the product graph; the next capability connects a guarded opt-in route for
real-model profiling and incremental optimization. The complete measurements
and profiling limits are in `docs/cuda-native-optimization-log.md`. Another
CUDA device and a connected request remain unmeasured.

### Opt-in connected CUDA Q6_K output-head trial (2026-09-29)

The first connected step runs an independent one-column Q6_K projection over
the actual resident model buffers after the synchronized ggml graph and replaces
that graph's F32 output. This intentionally duplicates the projection while
establishing a real-request ownership, numerical and failure baseline. A later
step removes the duplicate ggml projection once the independent boundary is
qualified. The original ggml graph remains the default and comparison control.
The one-column screen passed all 248,320 actual logits with maximum absolute
error `1.91e-6`; two five-pair local host repeats gave median paired gains of
`+0.013978` and `-0.007316 ms`. A separate Nsight Systems run measured median
native and ggml GPU projection intervals of `893.088` and `886.848 us`.
These are local observations, not a request-speed claim.

| Contract | Definition |
| --- | --- |
| Selection and owner | Align reads `ALIGN_LLM_NATIVE_Q6_HEAD=0|1`, default `0`, before Qwen3.5 session construction and passes the selected mode through `ggml_ffi`. Mode `1` requires a single CUDA device, Q6_K output weight `[2048,248320]`, one contiguous F32 normalized activation and one contiguous F32 output row. Invalid mode, backend or geometry fails before session publication; an unsupported graph shape fails before its execution. The graph key includes the mode. Existing state-copy selection is independent. No persisted artifact, network change or schema version (`N/A`: process-local experimental selection). |
| Results and errors | For each final-prefill or decode graph with one output row, run the existing synchronized ggml graph, then the native Q8_1/DP4A projection over the borrowed CUDA weight and activation into the borrowed output. The native launch and completion must succeed before any logits, token or state are published. A failed registration, pointer/extent check, launch or completion poisons the workspace and returns the existing compute/config fault. Mode `0` has no native submission. Four-row target-verification graphs are outside this first trial and must refuse mode `1` before executing such a graph. |
| Ownership and cost | The ggml backend owns weights, activations, logits, graph workspace and their lifetime. The CUDA helper owns one nonblocking stream and at most 16 KiB of reusable Q8_1 scratch; it retains no borrowed tensor pointer between calls and allocates no second model weight or full-logit buffer. Graph invalidation and owner Drop drain native work before ggml storage is released. Preparation <=3600 s; each local or request comparison <=900 s; individual request <=180 s. The duplicate graph projection is counted and removed in the next optimization step, not hidden from timings. |
| Acceptance and measurement | On the authenticated 2B artifact, compare every F32 logit of three real final-prefill/decode outputs under the fixed `abs(candidate - ggml) <= 0.01` bound and exact lowest-index greedy choices, then exact generated IDs and active state over short/chunked/wider prompts and a retained session. Force submit/completion failures and require no published token/result. Profile the connected native projection and record whole-request alternating pairs against mode `0` and pinned llama.cpp with the same weights/prompt IDs. Retain all samples and losses. No fixed percentage floor; this mode remains opt-in until a later nonduplicated request path has a useful measured effect and full correctness coverage. |

| Closure case | Implementation and owner |
| --- | --- |
| Construction and invalid selection | `runtime_qwen35_execution`, `runtime_qwen35_generation`, `ggml_ffi` and `ggml_shim` validate mode, backend and geometry before session publication; `run-qwen35-native-q6-head-smoke` exercises invalid values and non-CUDA/shape refusal. |
| Graph build and success | `runtime_qwen35_model` registers the exact Q6_K weight, normalized activation and output row. `ggml_shim` checks borrowed tensor storage after allocation and calls `native_cuda_q6_head` after ggml compute. `run-qwen35-native-q6-head-smoke` checks full logits, greedy IDs and valid state for prefill/decode and retained requests. |
| Launch, completion, early exit | `native_cuda_q6_head` checks each CUDA operation; `ggml_shim` poisons failures before publication. The smoke owner injects submit and completion faults and checks no output or token is published. |
| Invalidate and cleanup | `ggml_shim` drains the helper before graph workspace rebuild/invalidate and owner destruction; the smoke owner rebuilds a graph and executes again after the prior storage is gone. |

#### Remove the duplicate projection on the selected CUDA path

The first connected request measured a median 16.317/26.797/68.096 ms loss
at 56/16, 200/32 and 330/64. Nsight Systems counted one ggml plus one native
Q6_K projection per output token. Keep this correctness checkpoint, then make
mode `1` execute the independent projection once while mode `0` retains the
original graph and readback.

| Contract | Definition |
| --- | --- |
| Graph and result | In mode `1`, construct the Q6_K output tensor only as checked shape/format metadata. Mark the normalized single-row F32 activation as the graph output so ggml computes all upstream layers and state writes but does not schedule its Q6_K projection. The native CUDA helper writes all 248,320 F32 logits to its own bounded device output. Align selects the native full-logit read ABI at every normal-generation read point; mode `0` keeps `gpu_slot_get` from ggml. The four-row target graph remains unsupported in mode `1`. |
| Owner, allocation and failure | The ggml owner retains the weight and normalized activation through synchronized graph completion. The helper owns one 993,280-byte output and 2,304-byte Q8_1 scratch plus one stream; no second weight or dequantized matrix. Align reserves the exact 995,584 bytes before memory admission; the shim includes them in the admitted device total and observed device peak, opens the helper only after admission succeeds, and the CUDA source statically checks the allocation size against that shared reservation. It stores no borrowed pointer across calls. A graph compute failure, missing registration, invalid CUDA pointer, launch/read failure or stale output returns a checked fault before token/state publication. A new graph compute clears prior native-output readiness. Invalidation and Drop drain the helper before releasing ggml storage. |
| Identity, validation and metrics | The existing `ALIGN_LLM_NATIVE_Q6_HEAD=0|1` mode and graph key distinguish this topology; no new public flag, persisted/cache schema or network contract (`N/A`). Validate mode/backend/geometry, register exact tensor metadata, allocate graph workspace, then check CUDA pointer extents at compute and exact output length/readiness at read. Count the native projection as one model operation per logit graph while `graph_nodes` continues to count only ggml nodes. Reuse the three-prompt complete-logit/state/retained/failure owner and reprofile to verify zero ggml Q6_K output launches in mode `1`. Repeat five alternating paired request comparisons against the previous duplicated native checkpoint, unchanged Align and pinned llama.cpp. Preparation <=3600 s, campaign <=900 s, request <=180 s. Retain every pair; adopt an unambiguous useful gain without a universal percentage floor. |

| Closure case | Implementation and exact owner |
| --- | --- |
| Construction and malformed shape | `runtime_qwen35_model`, `ggml_ffi` and `ggml_shim` retain exact Q6_K metadata and refuse unsupported graph/shape; `run-qwen35-native-q6-head-smoke` exercises mode refusal and full actual model geometry. |
| Success and repeated use | `runtime_qwen35_model` expands normalized activation, `ggml_shim` launches native once after ggml upstream work, counts the off-graph operation, and `runtime_qwen35_generation` reads the native output; `run-qwen35-native-q6-head-smoke` compares all logits/state and repeated requests. Its traced accounting compares ordinary/native model-operation totals and checks planned allocation equals the configured budget while allocated and peak device bytes stay within it. |
| Compute/read failure and early exit | `native_cuda_q6_head` and `ggml_shim` poison or refuse stale/failed output; the same smoke owner runs submit/completion fault builds and asserts no token/result publication. |
| Invalidate and cleanup | `ggml_shim` clears readiness on new compute/invalidation, drains on workspace rebuild and owner Drop; the retained-request owner crosses graph reuse and new request storage. |

### Independent Q6_K small-batch output-head screen (2026-09-28)

The current four-row target verifier amortizes model weights across candidate
tokens, but its output head still accounts for a large quantized read. Test
whether a shape-selected independent Metal Q6_K projection can reuse each
compressed weight block across four actual F32 activations more effectively
than the pinned ggml four-column path. This is a local developer screen, not a
product switch or a ggml source patch. The existing Q6_K scalar and ggml
paths remain comparison controls.

| Contract | Definition |
| --- | --- |
| Inputs and owner | `bench-metal-q6-projection` accepts an explicit `--batch4` screen. It reads the existing checked actual-weight Q6_K capture and uses its three real activations plus a repeated first activation as four F32 columns. The Metal shader selects by Q6_K block layout, width divisible by 256, and four columns, not model name. The probe owns its temporary buffers and no session state. |
| Result and correctness | Before timing, compare all four complete F32 output columns with the pinned ggml four-column result and their independently captured single-column references using the preexisting `0.01` absolute bound. Also check a nonmultiple output-row tail. Report exact greedy choices for all columns as diagnostic information; this first screen does not replace target acceptance or alter production logits. |
| Cost and measurement | Keep weights quantized in one resident 417 MB Metal buffer, one input buffer and one output buffer per arm; no F16 expansion or model-sized scratch. Measure one completed command per arm with 12 warmups and five alternating pairs of 20 operations, including full command completion, and retain every result. Local trial integration is worthwhile only if the actual-weight timing and correctness show a plausible margin after the previously observed split/interop cost; no fixed percentage floor applies. The connected request remains unmeasured until such integration. |
| Failure and rollback | Reject malformed geometry, missing capture, Metal compile/command failure and any output mismatch before timing. `--batch4` is developer-only; default CLI behavior and product graph remain unchanged. Cache or persisted schema: N/A. |

### Native worker phase-reduction correction (2026-09-28)

The independent `measure-native-swiglu` worker runs three retained requests
per arm and times the third. Its schema-2 phase reducer correctly selected the
third request's graph calls but selected all three requests' native completion
waits. Thus instrumented `native_wait_prefill_ns` and
`native_wait_decode_ns`, and whichever of `prefill_ns` or `decode_ns` includes
those waits, are not per-request values in affected schema-2 receipts. Preserve
those receipts as historical evidence;
their request wall, startup, graph-submit and pinned-reference fields are
unaffected by this reduction defect. Do not use the contaminated phase totals
to explain a whole-request result.

| Contract | Definition |
| --- | --- |
| Surface and owner | `scripts/measure-native-swiglu` remains an independent measurement caller. The corrected JSON receipt has `schema_version: 3`; the CLI, model execution, and product runtime are unchanged. Python never computes a model value. |
| Inputs and result | The existing explicit model, arms, output path, pair count and `--wall-only` inputs retain their defaults and validation. For a phase-instrumented arm, capture the diagnostic log's file-size boundary after each completed request without moving the producer's file offset; parse each request span separately. The third request contributes exactly its own prefill graph count, decode graph count, and native finish count. `graph_submit_*_ns`, `native_wait_*_ns` and derived `prefill_ns`/`decode_ns` refer to that same third request. A mode without native finishes reports a null native-wait field. |
| Validation, failure and identity | Refuse missing or excess graph/finish records within **each** request, including balanced excess/missing records across requests, and any third-request phase sum larger than its measured wall interval. An incomplete run retains `INCOMPLETE` plus its error; no speed verdict is produced. The output path remains create-only. `schema_version: 3`, input and binary digests, and explicit phase-instrumented flag identify corrected receipts. No cache or product persistence is introduced. |
| Acceptance and cost | A real 2B Metal 64/16, 200/32, 330/64 paired campaign must retain exact generated output and counts; a focused synthetic three-request check must reject the former all-request wait reduction. Compare corrected phase values with an independent one-request native-command trace. One campaign <=900 s; each request <=180 s, with no extra model-sized allocation. |

| Closure case | Owner and evidence |
| --- | --- |
| Construction / malformed input | Existing `measure-native-swiglu` argument and arm validation; focused self-check of three-request reduction before model launch. |
| Success / repeated requests | Per-request file-size spans and the third request's graph/finish clocks; focused self-check plus the real 2B paired phase receipt. |
| Failure / early exit | Per-request count/kind and wall-containment checks fail the receipt; existing `INCOMPLETE` error handling retains evidence. |
| Cleanup / rollback | Existing session and reference subprocess scopes; `--wall-only` remains a control without phase interposition. Historical schema-2 files stay immutable. |

### Independent Metal recurrent-state copy trial (2026-09-27)

The first selectable native execution seam replaces the 18 contiguous F32
DeltaNet resident-state copy nodes per Qwen3.5 decode graph with one independent
Metal batch dispatch. Align chooses the seam and retains the source tensors as
graph outputs; ggml continues to compute their producers and the rest of the
graph. After the producer graph completes, the native dispatch copies its
outputs into the inactive resident plane. Only successful completion permits
Align to publish the new parity. Prefill and ineligible strides retain the
existing ggml copies. This trial does not require a ggml source patch and does
not claim a complete ggml-free graph.

| Contract | Definition |
| --- | --- |
| Selection | `ALIGN_LLM_NATIVE_STATE_COPY=1` opts a Qwen3.5 Metal session into the trial; absent or `0` retains the ordinary graph; any other value refuses session construction. Align snapshots the value once and includes it in decode topology identity. CPU, CUDA, unsupported storage, and ambiguous Metal device identity refuse mode `1`. The current borrowed-buffer bridge admits the pinned backend's sole `MTL0` and exactly one physical Metal device with a matching description; other configurations use mode `0`. |
| Native boundary | The checked shim accepts only complete, contiguous F32 source/destination tensors with equal byte extents of at least 1 MiB and no overlap. It stores graph-local pairs without retaining a second tensor payload. A device-only module borrows the existing shared Metal backing allocation by public base/size accessors; it owns its Metal queue and one command buffer per decode step. No ggml source patch or model-specific size is used by the native copy. |
| Ordering / failure | The synchronous ggml producer graph completes before the native command reads its outputs. The independent native command may overlap CPU logits readback and sampling, which do not consume the copied state. Align explicitly waits for its completion before advancing recurrent parity or returning a token. A graph, native dispatch, synchronization or resource failure leaves the session unhealthy and parity unpublished. Rebuild/invalidation drains pending native work and clears graph-local pairs before releasing workspace; close drains and releases the native context before the borrowed allocations. Retained sessions cannot share pending pairs. |
| Correctness / rollback | Require bit-identical DeltaNet destination planes and full logits against the same binary with the mode off, plus the existing 2B/0.8B generation, repeated-request, failure-recovery and serving owners. Keep the ordinary graph as the immediate rollback. The native path may not waive or change a numerical tolerance. |
| Measurement / ceiling | Compare the same saved Align binary with mode off/on on the same unpatched pinned ggml bundle, then the native candidate with pinned llama.cpp, using exact GGUF, pack, Model IR, prompt IDs and generated counts at 64/16, 200/32 and 330/64. Record local batch command interval, connected prefill/decode, whole warm request, startup, command count and memory, with two warmups and five alternating pairs. Build <=900 s, each campaign <=900 s and request <=180 s; at most one small descriptor buffer and one cached borrowed Metal view per backing allocation, with no duplicate resident plane. These are cost bounds, not a required percentage improvement. |

Closure: configuration belongs to Qwen3.5 execution parsing and malformed-mode
owner; graph success and topology reuse belong to the recurrent builder and
decode generation owner; native buffer admission, command failure and cleanup
belong to a focused device owner; exact state/logit parity and repeated requests
belong to the real-model owners. The first local zero-copy shared-buffer probe
passed on the measured M1 host; it proves the bridge's byte semantics only,
not this integrated trial's speed or portability.

| Closure case | Align owner | Shim/device owner | Evidence or deferral |
| --- | --- | --- | --- |
| Construction / malformed mode | `runtime_qwen35_execution.read`, `runtime_qwen35_generation.prepare` | `align_gpu_native_state_copy_mode` refuses unsupported devices/storage | Invalid mode `2` refused before ready; real and stub shim builds passed. |
| Success / repeated use | `runtime_qwen35_recurrent.build_many`, generation and parity | Checked copy registration, borrowed views, one native command and finish | 16-token full logits/state equality, both-size generation owners, 0.8B serving owner, five-pair measurements. |
| Failure / early exit | Session remains unhealthy until copy completion; parity advances only after finish | Command status is checked; close drains pending work | Invalid-request and early-exit generation owners passed. Test-only submit and post-completion failure builds returned `failed` without a result on real 2B decode, exited nonzero, and retained mode-`0` generation. |
| Rebuild / cleanup | Topology invalidation and session close | Wait/reset borrowed views before allocator release; reject ambiguous device identity at construction | Repeated-request generation and process-footprint screens passed; another Metal device remains unmeasured. |

Integrated result: the first synchronous native version lost all 15 paired
warm requests. The revised cached-view asynchronous blit version passed exact
16-token 2B full-logit/state comparison, 2B/0.8B generation, 0.8B serving
and invalid-mode refusal. After review repair, the same-binary unmodified-bundle
campaign won 15/15 unchanged-Align and 15/15 pinned llama.cpp warm-request
pairs on the measured M1, with control-minus-native paired medians +44.636,
+88.505 and +186.868 ms. The pre-repair campaign retained one -5.380 ms Align
pair at 200/32; it remains in the record. Startup remained slower
than llama.cpp. The actual decode graph omitted 18 copy nodes and added one
independent blit command per step. The final process-footprint screen observed
a small +0.109 MiB physical and +0.531 MiB peak increase for native mode,
while the preceding screen had the opposite sign; total GPU/system memory
remains unmeasured.
Keep the route opt-in until another Metal-device qualification. Full
conditions, phase limits, memory scope and receipts are in
`docs/qwen35-native-state-copy-trial.md`.

### Native Metal strided convolution-state copy trial (2026-09-27)

The next GPU trial extends the Align-selected decode state-copy boundary. The
current native mode batches 18 contiguous DeltaNet copies but leaves 18 small
convolution-state copies as separate ggml graph nodes. A real 2B Q4_0,
two-token decode trace found all 18 convolution sources have logical shape
`[3,6144,1,1]`, F32 `nb=[4,16,98304,98304]`, and a 98,300-byte reachable
span; each destination has `nb=[4,12,73728,73728]` and 73,728 logical bytes.
The instrumentation was removed after capture. These observed values define a
test case, not a model-name gate or a universal Qwen/Gemma layout assumption.

| Contract | Definition |
| --- | --- |
| Selection / input | `ALIGN_LLM_NATIVE_CONV_COPY` is absent/`0` by default and `1` only when `ALIGN_LLM_NATIVE_STATE_COPY=1`. Align snapshots both at Qwen3.5 session construction before model weight/workspace setup, rejects every other value or the dependent mode without the parent mode, and includes the choice in decode topology identity. Modes `0` and existing native-Delta-only mode remain comparison/rollback paths. The GGUF, pack, Model IR, runtime options and prompt wire formats do not change. |
| Native operation / validation | Align identifies convolution state by the model's recurrent operation and passes its graph source and inactive resident destination to a new narrow FFI registration. Registration checks F32 type, equal logical shape, a two-dimensional view with singleton outer dimensions, source `nb[0]=4`, row stride greater than or equal to row bytes, contiguous F32 destination, and bounded descriptor count before graph publication. After ggml assigns backing and executes producers, commit checks reachable source/destination spans, non-overlap and shared Metal backing before any native command submission. A mismatch fails the selected session; there is no silent fallback. No Qwen model name or fixed `3×6144` predicate belongs in the implementation. |
| Execution / ownership | The ggml graph still produces source tensors and all other operations; Align expands explicit source roots instead of 18 convolution `CPY` nodes. The native module borrows the admitted shared source and resident buffers and owns one reusable bounded descriptor buffer plus a Metal compute pipeline for strided copies. A three-element row uses one thread per row and three bitwise F32-word transfers; other widths use the generic element path. This is a local shape specialization, not a model-name gate. The existing contiguous blit and new strided compute are encoded into one native command buffer after the synchronous ggml producer graph. Align's existing finish waits for the whole command before advancing either recurrent-state parity or returning a token. Workspace rebuild, failure and close drain pending work before borrowed allocations are released. No second resident plane or per-token host readback is allowed. |
| Results / errors / cache | Registration and command errors follow the existing `Result`/unhealthy-session path. Mode and applicable shape/layout enter graph identity; graph-local registrations are cleared on invalidation. The pending command completes before a request finishes; borrowed Metal views and the descriptor buffer remain session-scoped and can be reused by the next request, then are reset or released before their backing is freed. Public persisted/cache schema: N/A; the only new identity is the in-memory decode graph key. |
| Acceptance / cost ceiling | Before performance measurement, require actual 2B full-logit and state-plane equality with Delta-only mode, 2B and 0.8B generation owners, repeated requests, failure propagation, and an odd-shape local descriptor/kernel check. Compare unchanged Align, Delta-only mode, mixed mode, and pinned llama.cpp under the same GGUF and prompts at 64/16, 200/32 and 330/64 with warm-up and five alternating pairs. Record command count, prefill/decode/whole-request, startup/load and memory; retain adverse pairs. Build <=900 s, each campaign <=900 s and request <=180 s. Permit at most one small reusable descriptor buffer (<=4 KiB), no model-sized allocation or extra model-state host/device copy; measure pipeline construction time and process footprint. Adoption has no universal percentage floor. |

| Closure case | Owner | Evidence to produce |
| --- | --- | --- |
| Construction / malformed mode | `runtime_qwen35_execution`, generation session, Metal mode admission | New `scripts/run-qwen35-native-conv-copy-smoke` checks invalid option/dependency refusal before ready and existing modes. |
| Success / actual layout | Recurrent graph, checked shim descriptor, Metal compute/blit command | `scripts/run-qwen35-native-conv-copy-smoke` checks exact actual 2B logits and both state parts, odd synthetic shape and node/command census; 2B/0.8B `scripts/run-qwen35-generation-smoke` passes. |
| Failure / early exit | Existing unhealthy-session/parity boundary plus mixed native command | `scripts/run-qwen35-native-copy-failure-smoke` in mixed mode checks forced submit/completion failure; `scripts/run-qwen35-generation-smoke` checks one-token and repeated-request controls. |
| Rebuild / cleanup | Graph invalidation, reusable views/descriptor and close | `scripts/run-qwen35-generation-smoke` repeated requests and changed decode width; `scripts/run-qwen35-native-conv-copy-smoke` confirms no stale descriptor content across requests. |
| Performance / portability | Paired worker and pinned llama.cpp callers, backend parity register | Existing Qwen3.5 paired worker/phase/footprint measurement callers record three lengths, startup and memory receipts on M1. Another Metal device and CUDA remain explicitly unmeasured until available. |

### Native Metal prefill recurrent-state copy trial (2026-09-28)

The merged decode trial leaves recurrent state publication inside ggml for
prefill. An actual 2B Q4_0 two-chunk trace at 128 and 71 prompt tokens found
18 convolution and 18 DeltaNet state `CPY` nodes in each prefill graph. The
DeltaNet source/destination are contiguous F32, `[128,128,16,1]` and 1 MiB.
The convolution source/destination are F32 `[3,6144,1,1]`; the source row
stride is 524 bytes for the 128-token chunk and 296 bytes for the 71-token
chunk, while the resident destination row stride is 12 bytes. The same shared
Metal workspace and resident allocations admitted by the decode trial appear
in the trace. These are measured layouts, not fixed model-name conditions.

| Contract | Definition |
| --- | --- |
| Selection / input | `ALIGN_LLM_NATIVE_PREFILL_STATE_COPY` is absent/`0` by default and `1` only when both `ALIGN_LLM_NATIVE_STATE_COPY=1` and `ALIGN_LLM_NATIVE_CONV_COPY=1`. Align snapshots the flag at Qwen3.5 session construction; malformed values or unmet dependencies refuse before model weight/workspace setup. Prefill mode enters the graph key. The original ggml prefill graph and native decode modes remain available. No GGUF, pack, Model IR, runtime options or request wire change. |
| Graph / native operation | For the selected prefill graph, Align expands the 36 state sources as explicit roots and registers their inactive resident destinations, omitting only their ggml `CPY` nodes. The existing checked F32 contiguous blit and strided-row Metal compute path handle source shape, stride, bounded span and shared backing. The shim extends its admission to prefill only when this flag is selected; no model-name or fixed `128`/`71` token predicate. Other prefill copies, model operations and logits remain in ggml. |
| Ordering / ownership | The synchronous ggml producer graph completes before the independent native command reads source views. Its 18 blits and 18 strided copies share one command buffer. Align may read logits while it runs, but explicitly waits for native completion before recurrent parity advances, before a next prefill chunk can read that state, and before request return. Failure leaves the session unhealthy; invalidation/close drain pending work before borrowed workspace or resident allocations are released. The descriptor buffer and Metal views remain session-owned and reusable, with no second state plane. |
| Results / cache | Registration, submit and completion failures use the existing `Result`/controlled worker-failure path. Graph-local registrations clear on invalidation; source layout is rechecked on each new graph/commit. The in-memory graph key gains the mode. Persisted schema/version: N/A; no persisted data changes. |
| Correctness / measurement / ceiling | Require exact 2B full logits and all resident planes after each prefill/decode graph, 2B/0.8B generation and repeated requests, invalid-option and native submit/completion fault owners, and actual 128/71 plus short/long chunk shapes before timing. Compare same-binary mixed-decode control with prefill mode on, plus ordinary Align and pinned llama.cpp, using identical GGUF/input IDs/output counts at 64/16, 200/32 and 330/64. Run warm-up and five alternating pairs; separate prefill, decode, whole request, construction/load and process footprint. Keep all adverse samples. Build <=900 s, each campaign <=900 s, request <=180 s; no new model-sized buffer or extra state readback. Adoption is assessed without a universal percentage floor. |

| Closure case | Owner | Evidence to produce |
| --- | --- | --- |
| Construction / malformed mode | `runtime_qwen35_execution`, generation preparation, native mode admission | Existing real-model copy owner with prefill variant checks dependent/invalid modes before ready; ordinary and decode-only controls still run. |
| Success / chunk variation | Recurrent graph, checked shim and native command, generation parity | Trace-based owner compares complete logits/state and counts 36 removed prefill `CPY` nodes for short and chunked requests; 2B/0.8B generation owners pass. |
| Failure / early exit | Native submit/completion plus existing unhealthy session | Test-only fault builds exercise the real first prefill command, require failed envelope/no token/exit 2 and native/request markers; ordinary mode still completes. |
| Rebuild / cleanup | Graph invalidation, borrowed views, descriptor reuse and session close | Repeated short/long/short session owner and full state hashes show no stale source/descriptor across chunk widths; existing close drains pending work. |
| Performance / portability | Same-binary worker/phase/footprint callers, backend parity | Actual 2B M1 campaigns at three lengths record prefill/decode/whole/startup/memory and pinned reference. Another Metal device and CUDA are deferred with explicit backend parity status. |

### Native Metal copy-command greedy trial (2026-09-28)

The separate post-synchronization Metal argmax selected correct tokens but did
not improve real requests consistently. Decode now already submits one native
Metal state-copy command after the synchronized ggml producer. Test whether two
finite, first-index hierarchical argmax dispatches in that same command avoid
the full F32 logits readback and CPU scan without paying for another command.
This is a decode-only GPU experiment; prefill retains its current greedy path.

| Contract | Definition |
| --- | --- |
| Selection / owner | `ALIGN_LLM_NATIVE_COPY_GREEDY` is absent/`0` by default. `1` requires `ALIGN_LLM_NATIVE_STATE_COPY=1` and `ALIGN_LLM_NATIVE_CONV_COPY=1`; malformed values, unmet dependencies and combinations with shared/NEON/in-graph greedy refuse before model setup. Align snapshots selection, keys both decode graphs, controls generation/token publication and retains the old full-row path as rollback. No public CLI, pack, Model IR, persisted format or request schema changes. |
| Input / ABI | Align registers only its completed decode output row: contiguous one-row F32 logits with `1..1,048,576` elements, checked shared Metal backing and bounded extent. The logit row must use the same ggml producer workspace allocation already borrowed by the native copy command. The pinned ggml Metal allocator page-pads its shared allocation; the native view covers that verified page-rounded length so a logit row at the logical tail remains addressable. The shim conveys the borrowed base/offset/count to the session-owned native command. The Metal helper reuses one bounded partial buffer and a four-byte shared result; it implements finite rejection and lowest-index ties. It has no model name, tokenizer, sampling loop or ownership of ggml allocations. |
| Execution / ownership | Synchronous ggml graph completion precedes the native state-copy/argmax command. The two dependent argmax dispatches have an explicit Metal buffer barrier; the strided state copy and argmax share the existing compute encoder. Align waits once for the command before reading the token and advancing recurrent parity or returning a streamed token. A nonfinite input, invalid result, command failure or borrowed-buffer mismatch fails the selected session; no stale token can be published. Workspace rebuild/invalidation/close drain work before freeing borrowed views. Other model graph operations and prefill remain ggml. |
| Verification / ceiling | Before timing, compare exact 2B full logits and every resident state plane with the same-binary mixed-decode route, plus 2B/0.8B generation and 0.8B serving/SSE owners. Locally test finite rows, first-index ties and NaN/infinity. Exercise short/long/short sessions and native submit/completion failures. Compare same GGUF, IDs and generated work at 64/16, 200/32 and 330/64 with two warmups and five alternating pairs against mixed decode, ordinary Align and pinned llama.cpp. Separate local kernel, graph/submit, decode, full request, startup and process footprint. Build/owners <=900 s, campaign <=900 s and request <=180 s; reusable scratch <=16 KiB, no full-row copy or second model-state plane. Assess reproducibility and maintenance without a fixed percentage gate. |

| Closure case | Owner / evidence |
| --- | --- |
| Construction / malformed mode | Config parser and native selection; invalid/dependent/conflicting flags refuse before readiness, old mode still runs. |
| Success / numeric edge | Decode graph registration, shim, Metal partial/final kernels and Align read; actual 2B exact logits/states, 2B/0.8B output, local tie/nonfinite cases. |
| Failure / early exit | Native submission/completion and token read; controlled failed envelope without result/token in forced-failure owners. |
| Rebuild / cleanup | Existing graph invalidation and native reset; repeated short/long/short plus streaming SSE and retained state hashes. |
| Performance / portability | Same-binary 2B paired worker/phase/footprint, pinned llama.cpp and backend-parity register; another Metal host/CUDA explicitly deferred. |

### Independent Metal Q4_0 tile-consumer FFN screen (2026-09-28)

The previous gate/up/SwiGLU-only native path left the down projection and
intermediate vector boundary in ggml. Test a different ownership unit before
another runtime integration: one Metal threadgroup computes a bounded tile of
gate/up hidden rows, applies SiLU, consumes that tile against every output row
of Q4_0 down weights, and writes partial F32 outputs. A second dispatch reduces
the partials. This is an independent local Metal candidate, not a ggml source
patch or a proposed default. The existing real 2B FFN captures and unmodified
pinned ggml backend are the oracle and timing control.

| Contract | Definition |
| --- | --- |
| Admission / semantics | First screen only F32 decode input width 2048, hidden 6144 and actual Q4_0 gate/up/down bytes from captured 2B layers 3 and 23. Those dimensions are local screen arguments, not model-loading conditions. Layers 0..2 use Q4_1 down weights and are outside this kernel's admission; another Qwen size or Gemma needs shape, quantization and activation qualification. Preserve the captured Qwen SiLU multiplication and all bytes. |
| Work and ownership | Each hidden tile's gate/up activation stays in threadgroup memory until its Q4_0 down dot products finish. Output partials and a reduced 2048-element result are separately owned local Metal buffers; ggml owns its independent reference graph. The second dispatch follows an explicit buffer barrier in the same command encoder. No CPU/GPU readback or cross-command wait occurs between producer and consumer. The benchmark owns/tears down all allocations and has no inference or Python product path. |
| Numerical gate | Before timing, compare complete actual layer outputs with the captured ggml result using the predeclared `0.005 + 0.0005 * abs(reference)` local bound from the earlier Q4 FFN trial, report observed maximum differences, reject nonfinite output, and verify repeatability and a nonmultiple/tail local case. Do not change tolerance after seeing results. A connected local advantage is evidence to trial opt-in real-model integration, not proof of whole-request speed; a local loss rejects this mapping only. |
| Measurement / ceiling | Use the same captured weights/input for both arms, twelve warmups and five alternating pairs of twenty synchronized complete FFN operations per arm. Report full ggml FFN versus native two-dispatch wall and GPU intervals if available, startup and scratch. Each local run <=900 s. Partial output <=1 MiB; no second model-weight copy after upload, no full 6144-element gated device tensor in the fused arm. Review connected arithmetic, bandwidth, occupancy and synchronization before deciding whether to integrate. There is no fixed improvement percentage floor. |

Closure: checked capture sizes/types and Metal pipeline/allocator construction;
full finite output and tail correctness; repeated command-buffer reuse;
allocation/encoder failure cleanup; paired timing including complete dispatch
and synchronization; explicit decision. The ordinary ggml model route is
unchanged and remains the rollback. A later real-model integration, if earned,
requires its own Align selection, graph/state failure and full 2B/0.8B owner
qualification before any request-speed claim.

Result: two actual Q4_0 down-weight layers and a synthetic tail passed the
predeclared numerical bound. The fastest tested 512-thread mapping lost all
five complete-operation pairs on both captured layers: paired ggml-minus-native
medians -0.582 and -0.647 ms. A packed-dot rewrite improved the first shader,
but 1024 threads and two output partitions did not close the gap. The final
reviewed owner checked twenty untimed reused outputs and the output after every
timed pair, and lost another 5/5 pairs per layer (paired medians -0.609 and
-0.662 ms). Withdraw
this mapping before runtime integration; retain the reproducible local screen
and full receipt in `docs/qwen35-native-q4-tile-ffn-screen.md`. Next inspect
down projection scheduling/counters without repeating gate/up work. This local
loss does not impose a fixed improvement threshold or rule out other fused FFNs.

### Independent Metal Q4_0 down split-K screen (2026-09-28)

The tile-consumer FFN lost while doing long down-row work in each tile group.
Isolate that scheduling hypothesis without recomputing gate/up: use the captured
F32 gated vector and Q4_0 down weights from actual 2B layers 3 and 23. Compare
the pinned ggml Metal down projection, an independent four-row unsplit Metal
kernel, and two/four-way hidden-axis split-K kernels followed by a reduction.
This is a local device experiment; it does not change runtime selection.

| Contract | Definition |
| --- | --- |
| Admission / semantics | Captured F32 gated vector of length 6144, Q4_0 down matrix `[6144,2048]`, and complete F32 output for layers 3 and 23. Q4_1 layers 0..2 are excluded. The split divides only the reduction axis, preserving the same weight bytes, quantized dot operation and output rows. Shape and quantization are local probe arguments, not model-name predicates in product code. |
| Ownership / execution | Each arm has its own exact-weight shared Metal buffer; input is uploaded once. Native split partials have one owner and a bounded second reduction dispatch in the same command with an explicit buffer barrier. No per-operation CPU/GPU copies, gate/up recomputation or intermediate CPU wait. ggml independently owns its oracle graph. The wrapper owns and releases all probe allocations. |
| Correctness gate | Before timing, match the pinned ggml full output and the captured complete output; reject nonfinite results. Declare the existing FFN local bound `0.005 + 0.0005 * abs(reference)` before the screen, and report actual differences for unsplit and each split. Check repeated command reuse and a synthetic nonmultiple split tail. Do not weaken existing generation checks or call this exact compatibility. |
| Measurement / ceiling | Twelve warmups, then five alternating pairs of twenty synchronized complete down operations per arm on identical bytes. Record host wall and native GPU intervals, dispatch count, setup/upload, partial scratch, all pairs and device identity. A local run must finish within 900 s; split scratch <=64 KiB, one output <=8 KiB, and no second model-weight copy within an arm. Compare unsplit versus split and ggml versus split; a stable local advantage permits an opt-in real-model trial but is not a request-speed claim. A loss withdraws this mapping only. No percentage threshold applies. |

Closure: verify captured sizes/types before allocation; validate both complete
outputs and a split tail; detect command/encoder failure and clean up; check
reused output separately from timing; retain the raw alternating samples and
an explicit integration or withdrawal decision. Any real-model integration
would require a separate Align-owned selection and complete 2B/0.8B
correctness, prefill/decode/request and rollback qualification.

Result: both real captured down outputs matched rebuilt ggml byte for byte,
and unsplit/two/four-way native outputs passed the predeclared bound, including
a 160-wide synthetic tail and repeated reuse. Across two five-pair runs, the
unsplit native arm beat isolated ggml in 19/20 paired wall comparisons. The
two-way split beat unsplit in only 4/20 wall pairs and 6/20 GPU-interval pairs;
the four-way split won 2/20 wall and 2/20 GPU pairs. Withdraw both split
mappings. The unsplit local result justifies a separate complete-FFN command
screen before any real-model integration; it is not a request-speed claim.
Conditions and all samples are in `docs/qwen35-q4-down-split-screen.md`.

### Independent Metal Q4_0 complete-FFN capture screen (2026-09-28)

The unsplit down projection beat isolated ggml in 19/20 local wall pairs,
whereas hidden-axis split-K and a one-group-per-hidden-tile complete FFN lost.
Test the earlier two-dispatch gate/up/SiLU plus unsplit-down design on actual
captured Qwen3.5-2B bytes, rather than relying on its synthetic-input result.
This is an independent Metal command with one explicit producer/consumer
barrier; no ggml source patch or model-runtime change is part of the screen.

| Contract | Definition |
| --- | --- |
| Admission / semantics | Actual captured layers 3 and 23: Q4_0 gate/up `[2048,6144]`, Q4_0 down `[6144,2048]`, F32 input and Qwen SiLU gate. Require exact capture sizes and independently rebuild the pinned ggml graph. Q4_1 down layers 0..2 are excluded. Constants stay in this local probe; any runtime specialization must select by shape/type/activation/layout. |
| Ownership / order | The native arm owns one exact shared Metal buffer per weight, one input, one 6144-F32 gated intermediate and one 2048-F32 result. Upload before timing; gate/up/SiLU and down dispatch in one command encoder with an explicit buffer barrier. Wait once after the complete command. ggml independently owns its oracle graph and allocation. No timed CPU/GPU copy, model-sized duplicate within an arm or omitted state update. |
| Correctness | Before timing, require rebuilt ggml gated/final outputs to match the captures, then compare complete native gated/final vectors under the already declared FFN bound `0.005 + 0.0005 * abs(reference)`, with finite checks. Check twenty reused commands separately and the output after each timed pair. Preserve the existing generation regression suite; this local screen cannot claim generation compatibility. |
| Measurement / ceiling | Twelve warmups per arm, two process runs of five alternating pairs of twenty synchronized complete FFNs per arm. Record ggml and native wall time, native GPU command interval, gate-only versus complete command, setup/upload and scratch. Build plus one run <=900 s; native intermediate <=24 KiB and result <=8 KiB beyond weights/input. A local advantage justifies an opt-in real-model connection trial only if the graph-boundary cost is accounted for; a local loss withdraws this mapping. No percentage gate. |

Before a real-model graph partition, measure its minimum native command cost on
the same captured bytes: run gate/up and down in separate command buffers with
the necessary completion wait between them, versus the same two kernels in one
command with a barrier. Use twelve warmups and five alternating pairs of twenty
complete operations, check the output, and record wall and summed GPU intervals.
This is a boundary diagnostic, not an exact ggml-graph partition measurement.
Also test two command buffers on one Metal queue with default tracked shared
buffers, committing gate/up before down and waiting only for down completion.
Check both command statuses and the complete output after each pair, using the
same warmup/alternation. This tests whether queue order and hazard tracking
can retain correctness while avoiding the intermediate host wait; it does
not imply that the current ggml graph API can use that schedule.
The combined and separate native schedules keep distinct gated/result buffers
so every pair verifies both arms regardless of execution order.

Closure: checked capture identity, construction/allocation and command failure;
complete gated/final and reuse checks; paired samples and honest decision.
Before runtime adoption, Align must own model selection and graph boundaries,
and full 2B/0.8B correctness, prefill/decode/request, startup and rollback
must be measured. A separate ggml graph partition with a per-layer host wait
is not assumed to be free.

Result: rebuilt ggml gated/final vectors matched the captures byte for byte;
independent Metal outputs passed the declared local bound. Across the final
two five-pair runs and both actual layers, the combined native complete FFN
beat isolated ggml in 20/20 wall pairs with paired median advantages of
0.057–0.068 ms. Two commands with an intermediate CPU wait added
0.362–0.423 ms; ordered same-queue submission with only a final wait added
0.030–0.059 ms and passed every output check for both timed arms. The latter
remains close to the local compute gain, so do not claim request improvement or
enable the candidate. Continue with an Align-owned asynchronous schedule or larger
execution unit that avoids per-FFN host waits. Full conditions and samples
are in `docs/qwen35-q4-full-ffn-capture-screen.md`.

### Connected final-layer FFN diagnostic and next decode unit (2026-09-28)

The developer-only real-model connection replaced the final decode layer's
Q4_0 gate/up/SiLU/down sequence with the independent kernel while keeping
the ggml graph for its producer and consumer. It screened three necessary
boundary mechanisms: a fresh no-copy shared-buffer view, direct borrowing of
the pinned ggml Metal buffer, and GPU shared-event ordering with one final
host synchronization. All used the same model, prompt IDs and mixed native
state-copy production binary; the original graph was the control. The local
FFN tolerance remained `0.005 + 0.0005 * abs(reference)`. No product option,
model schema or ggml source patch was added. For any repeat of this diagnostic,
admit at most one 24 KiB gated scratch, no second model-weight payload, <=900 s
per three-condition campaign and <=180 s per request. These are resource and
time bounds, not improvement thresholds.

The final layer's input and ggml gated output alias in its allocated workspace.
The native fusion needs separate scratch. A second cached `MTLBuffer` wrapper
over that workspace returned stale values on subsequent decodes in this
setup; recreating the wrapper or borrowing ggml's original Metal buffer
restored local numerical correctness. Five real decode steps passed the
declared local FFN bound with the direct-buffer variant. Three-request
generation outputs matched across all 15 paired conditions per mode. A shared
8-byte diagnostic counter confirmed `completion_tokens - 1` native FFN
substitutions after every request, including each timed third request. Full
logits/state and fault propagation were not qualified for a product path.

With five alternating pairs at 64/16, 200/32 and 330/64, rewrapping won
0/5, 0/5 and 0/5; direct borrowing won 1/5, 0/5 and 0/5; GPU events won
1/5, 0/5 and 0/5, respectively. The paired median control-minus-native
request differences were −27.005/−64.104/−152.384 ms for rewrapping,
−10.515/−29.923/−63.976 ms for direct borrowing, and
−3.403/−15.798/−37.003 ms for GPU events. Withdraw final-layer-only
substitution. The pinned private
Metal buffer/event ABI is diagnostic and cannot be made an implicit permanent
ggml dependency of a native scheduler. Full receipts, phase limits and
reproduction commands are in `docs/qwen35-native-final-ffn-connected-screen.md`.

The next decode capability should first screen weight reuse across target
tokens or an Align-owned unit large enough to amortize graph/queue crossings.
For speculative verification, before normal generation changes, the owner
must identify a real draft source and measure accepted tokens per target
batch, batched target logits, DeltaNet/KV state transaction, rejection replay,
extra memory and target-plus-draft wall time. Retain exact-output/state
comparison and ordinary single-token generation as rollback. A cheap local
batch timing alone is an experiment trigger, not production adoption. Qwen
and Gemma model semantics remain explicit in Model IR; reusable kernels and
schedulers select on shape, quantization, activation, layout and device.

The first feasibility screen completed without changing the product graph.
On the real 2B M1 worker, prompts lengthened by 4/8/16 tokens while emitting
only the final logit row cost paired medians of +2.562/+2.400/+6.684 ms
versus a 200/1 base request; generating 4/8/16 tokens by serial decode cost
+121.676/+230.490/+438.319 ms. The longer prompts are not exact token-ID
continuations of the base: the chat-template suffix moves, leaving only 191
common initial tokens. These are shape-cost observations, not a formal lower
bound for verifying the base request's next tokens. On captured actual Q6_K
output weights and three hidden activations, batched 4/8/16-row head projection beat serial
one-row projections in all five pairs per shape, with numerical and greedy
checks passing. These independent screens establish a reason to test an
actual multi-row target graph; they do not establish speculative inference
speed or correct state acceptance. Conditions and receipts are in
`docs/qwen35-target-batch-feasibility.md`.

For that next consumer, cap an initial target group at 16 tokens, add no
second model-weight payload, and budget at most one additional 16-row F32
vocabulary result (15,892,480 bytes for this 2B vocabulary) plus explicitly measured
state transaction storage. Build <=900 s, one paired campaign <=900 s and
each worker request <=180 s. Select any group size by actual token count,
quantization/layout and device admission rather than model name. Before
timing, compare every target logit row under a predeclared bound, exact greedy
acceptance, complete committed recurrent/KV state after full and partial
acceptance, repeated requests and rejection fault cleanup. Production
adoption requires combined target-plus-draft request evidence, not a fixed
percentage improvement.

The first consumer of the all-row graph is a focused, developer-only real-model
probe in `runtime_qwen35_load_smoke`, selected by `--target-rows OUTPUT`.
The same smoke's `--serial-target-rows OUT0 OUT1 OUT2 OUT3` arm emits the
four one-token reference rows without the older 0.8B-only hard-coded oracle
ranges; it retains the ordinary full graph and token sequence. Each arm warms
its exact graph path once, resets resident state, then times synchronized
compute separately from output readback. The serial arm writes the timed
replay's four logits rows.
`runtime_qwen35_model.build_tokens_all_logits` admits a prefill graph with
`1 < count <= 16`, no last-FFN-row shortcut and no in-graph greedy. It returns
an F32 `[vocabulary, count]` output slot while retaining every recurrent and
attention state commit. The caller owns the output file and all temporary
buffers; no model, weight, session, or persisted format changes. For the first
screen, use the existing real-model four-token reference sequence
`[0, 23066, 0, 0]` and compare every row against the existing one-token
smoke's four outputs before timing interpretation. Predeclare
`abs(batch - serial) <= 0.05 + 0.001 * abs(serial)` for every finite logit and
require the same lowest-index greedy token; this local bound does not relax
the product regression. Record graph compute time, output readback, actual
allocation and shape, and keep the ordinary one-row graph as control. A
passing empty-prefix four-row screen is a graph feasibility result, not a
target-continuation, state-transaction or speculative-speed claim. Malformed
mode/arguments and graph construction/compute/readback failures must return
errors without publishing an output file. The existing 16-row and time/byte
ceilings above remain the upper limits for subsequent continuation trials.
An independent state diagnostic may compare the valid first four KV positions
and the active recurrent parity after the two arms. Before inspecting values,
use `abs(batch - serial) <= 0.005 + 0.0005 * abs(serial)` for every finite active
state element; inactive parity and unused KV capacity are outside this local
comparison. A failure is a feasibility finding, not grounds to widen the bound.
The completed M1 four-row screen met both local bounds and won all five
paired synchronized-compute comparisons, while adding about 2 MB of graph
workspace. Its empty-prefix and missing-draft limits are recorded in
`docs/qwen35-target-all-rows-screen.md`; the production gate above remains open.

The next developer-only continuation screen consumes JSON arrays of 1..508
prefix token IDs and exactly four target token IDs. On the same resident
session, it first executes the identical prefix, then either one four-row
prefill target graph or four one-token target graphs. The Align smoke owns
input validation, position/mask construction, recurrent parity, the graph
switch and synchronized computation. The current pinned ggml shim holds only
one prefill graph context; this probe must invalidate and rebuild that context
for the batched target graph and charge the rebuild to the connected target
cost. Its only output is a complete F32
target-logit file (batched) or four staged F32 row files (serial), plus JSON
timings for prefix, graph switching, target computation, readback and graph
workspace. Failed validation, graph execution or readback publishes no target
file. No production session or model format changes. The comparison uses the
same token IDs, weights, prefix state, graph/backend settings and retained
output rows, with the same predeclared local logit and active-state bounds as
the empty-prefix screen; compare KV only over prefix plus four valid tokens.
Run five alternating pairs, preserving setup and slower samples. The first
real fixture is the existing recorded 200-token prompt plus its pinned
reference's `[16, 220, 17, 220]` continuation. Cost ceiling: one extra
four-row F32 logits result, no second weight payload, <=508 prefix tokens,
four target tokens, <=900 s build/campaign and <=180 s per worker. An exact
continuation result remains a diagnostic until partial acceptance/rejection,
fault cleanup, draft cost and complete-request speed are qualified.
The recorded fixture may declare its source prefix and expected oracle greedy
IDs; other valid token sequences need only the bounded arrays and are compared
between batch and serial without requiring a greedy continuation.

### Qwen3.5 target acceptance-state screen (2026-09-28)

The exact-prefix four-row screen established bounded full-acceptance state but
did not test rejection. Add one developer-only `--verify-acceptance PREFIX_JSON
TARGET_JSON OUTPUT` arm to the existing Align smoke. It admits 1..507 prefix
tokens and four candidate IDs; the one-token continuation diagnostic must fit
the existing 512-position resident capacity. Model pack and Metal graph
selection remain the same.
After computing the prefix and all four target rows, Align compares candidate
0 with the prefix greedy ID and candidates 1..3 with rows 0..2, stopping at
the first mismatch. The selected next-token distribution is the prefix row
when zero candidates match or target row `accepted - 1` otherwise; full
acceptance uses target row 3 as a bonus prediction. The arm writes only that
complete F32 row after state resolution and reports accepted count, selected
greedy ID and separate prefix/target/graph-switch/replay intervals. It then
runs one synchronized decode of that selected token from the committed state
and appends its complete F32 logits as a second row in the same output file;
this next step has separate timing and is included in the equal-progress
connected interval. No public generation or model schema changes.

For four accepted candidates, the all-row graph's active recurrent plane and
valid KV positions become the committed state. For zero accepted candidates,
Align restores the prefix parity without a replay; extra candidate KV rows
remain outside the valid length. For one to three accepted candidates, Align
restores the prefix parity and replays only the accepted token IDs through
ordinary synchronized one-token graphs. Replay overwrites the inactive
recurrent plane and the accepted KV positions. The next attention graph must
mask out candidate KV positions beyond the committed length. A failed graph,
readback, replay or state finish publishes neither row nor a usable state.
One warm path followed by a zeroed timed replay keeps every accepted case
comparable. Report initial decode-graph preparation separately; the connected
interval includes candidate updates, prefill-to-target graph switching,
compute, replay and readback. No omitted synchronization or speculative speed
claim is allowed.

The first owner constructs five real 2B Q4_0 fixtures from the 200-token
oracle sequence: one each with first mismatch after 0, 1, 2, 3 accepted
tokens and the all-accepted case. Compare the chosen complete F32 row, greedy
ID, first `prefix + accepted` valid KV positions and active recurrent plane
against serial execution of the same accepted prefix. Use the predeclared
continuation bounds above; compare the next-token row with serial execution
for all five cases to detect hidden stale-state consumption.
Fault injection must show zero published output on a replay failure. Charge
graph setup and replay cost for every case. No second weight payload; the
diagnostic may stage three F32 rows in addition to the four-row target result
and original prefix row, with no persistent extra model state. Build/campaign
<=900 s and each worker <=180 s. Another Metal device, CUDA and other model semantics remain
unmeasured. This screen is a prerequisite for a later default-off product
trial with a measured draft and complete-request comparison, not its adoption.

A matching developer-only `--serial-acceptance PREFIX_JSON TARGET_JSON OUTPUT`
control uses the same greedy comparison but evaluates only each accepted token
and then the selected token through ordinary one-token graphs. It publishes
the same selected and next complete rows. Pair the two arms at each of the
five first-mismatch cases with alternating order, warm each exact path, and
record graph preparation, accepted-step work, next-step work and total
connected intervals separately. This establishes the cost of rejected target
work against equal actual token/state progress; it excludes draft generation.
The completed M1 screen found five of five paired connected wins only when
all four candidates matched; every first-mismatch case lost all five pairs.
The local correctness and timing limits are in
`docs/qwen35-target-acceptance-screen.md`. This is not product adoption.

### Qwen3.5 prompt lookup draft-source screen (2026-09-28)

Use the existing roadmap n-gram lookup contract as a draft-source hypothesis
before changing the Qwen3.5 product session. The Align diagnostic exposes
`runtime_generation.prompt_lookup_draft` on a bounded recorded history,
trying match lengths 3 then 2 and requiring all requested draft IDs. It
screens three drafts with the existing four-row target graph and separately
counts four-draft candidates for the planned five-row shape. The independent
developer measurement validates every draft against a backward-scan oracle
over pinned real-model greedy IDs, then selects one first mismatch and one
complete group per coding task for five alternating real-GGUF connected
pairs. The owner compares selected and next complete F32 rows, greedy ID,
valid KV and active recurrent state under the already declared acceptance
bounds. The cost ceiling is the roadmap's at-most-2,175-ID host scan; any
session integration must still charge its actual draft time and graph work.

The completed M1 screen found complete three-draft group counts of 3/18,
12/16 and 1/16 for function, bug-fix and test-writing continuations. One
early rejection per task lost 52.0–52.3 ms paired median; a complete group
gained 62.0–63.5 ms. Every measured pair and committed-state trace passed.
See `docs/qwen35-lookup-draft-screen.md` and the raw receipt. A default-off
continuous Align generation trial with a bounded rejection backoff remains
the next admission step; this screen does not establish whole-request speed
or general draft quality. The four-draft case has no connected five-row
timing, so its acceptance counts must not be converted into a speed claim.
The explicit default-off trial implementation and its predeclared cost ceiling
are tracked in `docs/specs/qwen35-lookup-continuous-trial.md`. Its M1 complete
request, repeated-session and pinned-reference results are recorded in
`docs/qwen35-lookup-continuous-trial.md`. The normal product route is unchanged
while the trial's workload-dependent losses and remaining qualification are
assessed.

### Final-chunk logits trial (2026-09-26)

Remove unused intermediate-prefill output work on the current 2B consumer. The
earlier 0.8B state-only experiment in `qwen35-text.md` is historical, including its
withdrawn percentage gate; it is not evidence for this implementation or model.

| Contract | Definition |
| --- | --- |
| Input / owner | `runtime_qwen35_execution.read` snapshots `ALIGN_LLM_PREFILL_FINAL_LOGITS`: `1` default emits logits only for the final prompt chunk, `0` preserves all chunk outputs for comparison/compatibility; any other value returns `Error.Invalid` before allocation. Align generation owns selection in normal and streaming sessions. The initial trials explicitly set the flag; default adoption follows exact state/output qualification, unchanged peak device allocation and measured long-input request/TTFT gains, not a percentage gate. |
| Graph / identity | `runtime_qwen35_model.build_tokens_output` accepts an explicit `emit_logits` boolean; false is admitted only for prefill. Existing `build_tokens` and decode callers retain full output. Every recurrent/KV commit remains an explicit graph root; their complete producer dependencies execute. A nonfinal chunk does not expand the final hidden tensor or vocabulary head, so the final layer's unused attention/FFN tail is not executed. Its logits slot is absent and must not be read. Output mode enters the prefill graph key. |
| Ownership / failure | No new buffer, ABI, state owner or retained weight copy. Borrowed slots retain existing lifetime. Publish recurrent parity only after successful synchronized compute and, when requested, logits readback; errors retain existing unhealthy-session/reset behavior. Final and one-chunk requests always produce logits. |
| Correctness | Existing exact generation and HTTP/SSE owners on 2B/0.8B, repeated short/long/short requests, 128/256/512 boundaries and one-token generation. Compare final-prefill/decode logits against the unchanged binary with the existing predeclared absolute bound 0.01 and identical argmax; report observed differences. Raw nonfinal baseline vectors remain retained. |
| Measurement / ceiling | Same weights, chunk width, upload mode, native-FFN setting and prompt IDs; old/new plus pinned llama.cpp, two warmups and at least five alternating pairs. Record prefill, decode, whole request, startup, graph/readback counts and memory. Each campaign <=900 seconds, each request <=180 seconds; no extra retained device allocation is allowed. Adoption is an explicit assessment without a percentage floor. |
| Formats / prerequisites | No product CLI, persisted format or model-IR change. Measurement tools record the explicit flag; the independent capture oracle aligns one final-prefill vector when enabled. Managed pinned compiler and existing Metal model kit are available. |

Closure: parser malformed-input probes; model's existing state-commit roots
and full producer dependencies; both generation loops and mode-aware graph keys;
2B/0.8B generation/serving owners; captured vector/count checks and alternating
worker/HTTP campaigns. Construction, cleanup, early exit and failure reuse the
existing session owner, with no new allocation lifetime. Author consistency:
output elision never controls state publication or removes a state producer.
The initial isolated trial retained the final hidden root and removed only the
head. Preserve its binary and measurements as `head_only`; the next bounded
trial removes that unused root as well. Every layer still contributes its
recurrent/KV state, including the final layer. Recheck all vectors and boundary
requests before repeating the real-model measurement; do not reuse the earlier
candidate's correctness or speed result for the revised graph.
For the state-root trial, `trace-qwen35-state.c` independently records operation
counts and hashes every retained KV/recurrent plane after successful synchronized
compute. Supply the geometry-derived state count (84 on current 2B); require
bit-identical full-plane hashes at matching graph steps across a 200/3 then 64/3
retained session. The diagnostic uses a 1 MiB CPU read/hash buffer, adds no graph
nodes and is never enabled for timing. It validates the next state index is
absent and fails on missing planes; all state-write nodes must remain. Its C code
uses only the existing thin ABI/backend read interface, with no production path.

Local closure: same-width 128/256/512 logits are exact, 588 full-state hashes
agree, and 2B/0.8B generation/serving owners pass. Adopt default `1` based on
useful long-input HTTP/SSE and first-token gains, unchanged Metal allocation,
small maintenance cost and explicit rollback. Preserve short-input noise,
worker regressions and the absence of a llama.cpp whole-request win. Final
default qualification is separate from explicit-flag timing artifacts; see
`../final-prefill-q6-trial.md` and its complete raw receipt.

### Final-layer single-row FFN trial (2026-09-26)

The current Qwen3.5 final prompt chunk computes the final layer's FFN for all
input rows, although this provider requests logits for only its last row. The
pinned llama.cpp Qwen3.5 builder has an optional `inp_out_ids` selection before
the last residual/FFN; `embeddings_nextn_masked` guards it and the measured
ordinary context initializes that setting false. This is a concrete Align
consumer hypothesis, not evidence of a performance gain.

| Contract | Definition |
| --- | --- |
| Input / validation / owner | `runtime_qwen35_execution.read` snapshots `ALIGN_LLM_PREFILL_LAST_FFN_ROW`: `0` or absent uses the existing graph, `1` enables the trial, every other value returns `Error.Invalid` before weight allocation. Existing upload/chunk/final-logits inputs retain their order and behavior; the new validation follows them. Align generation owns the per-session choice in both normal and streaming paths. |
| Selection / meaning | Only the final prompt prefill graph with `count > 1` and requested logits selects the final token row of **both** the final layer input residual and its completed attention output. Existing attention/recurrent builders still expand every persistent-state producer. The final FFN consumes those one-row views; the output head views row zero of its one-row result. Earlier layers, nonfinal chunks, one-row prefill and decode retain their graphs. Reject an ineligible request at the model builder. The optimization is specific to Qwen3.5's current semantic graph; other model families require their own analysis. |
| Graph / allocation | The actual one-row selection enters the 64-hex SHA256 graph key. A view creates graph metadata but no extra retained device tensor; the current full-row path remains selectable. No new ABI, model IR, weight layout, persistent format, Python product path or session state owner. View span is bounded by the existing strict F32 `op_view_2d` ABI. |
| Correctness | Before timing, compare actual 2B full-vocabulary final-prefill and decode logits with the flag off/on at equal chunk width, using the existing predeclared absolute limit 0.01 and identical argmax. Preserve raw vectors and observed maxima. Verify exact generated output against pinned llama.cpp on 2B and 0.8B, plus normal/streaming repeated and boundary requests. Hash all resident state planes at corresponding graph steps; the optimization must not alter state. A different FFN matrix shape may change floating-point reduction order; report it instead of relabeling an unexplained output mismatch. |
| Measurement / decision | Real unchanged 2B GGUF/pack, prompt IDs, generated counts, upload 0, chunk 128, native FFN 0, final-logits 1. Compare old Align, trial Align and pinned llama.cpp in at least five alternating worker pairs; independently compare the same candidate binary OFF/ON in five HTTP and SSE pairs per case after two warmup pairs. Record prefill, decode, whole request, first-token time, startup, graph operations, memory and adverse pairs. Each campaign <=900 seconds and request <=180 seconds. No percentage floor; default adoption requires useful real-request evidence and acceptable correctness, regression, resource and maintenance costs. |

Closure: configuration construction/malformed input belongs to execution parsing
and invalid-session probes; graph formation/success belongs to model row selection
and same-width full-logit/state checks; normal/streaming and repeated requests
belong to generation/serving owners. Early exit, failure and cleanup use the
existing session owner; no new allocation lifetime exists. The author consistency
check is that both row views are selected after state-producing attention work,
that only the final layer receives them, and that full-row rollback remains a
genuine same-model control. Performance and adoption will be recorded in a new
trial report and raw receipt, not inferred from this plan.

Local closure: the implementation and existing 2B/0.8B owners pass. At equal
chunk width, 71,516,160 full-logit floats stay within the predeclared 0.01
absolute bound with identical argmax; all 588 full resident-state plane records
match. One actual Q4_0 FFN path selects a matrix-vector Metal kernel, but the
five-pair whole-request HTTP/SSE results are mixed, including adverse cases and
timing movement in the one-row no-op control. Retain the mode as an opt-in
experiment, default `0`, and keep full-row comparison. This decision weighs
small connected gains, variability, unchanged memory report, numerical rounding
and maintenance cost without a percentage floor. See
`../final-ffn-row-trial.md` and its complete raw receipt.

### Actual Q6_K projection probe (2026-09-26)

Independent native Metal experiment, outside production inference: capture the
real final normalized activation and logits for the tied Q6_K output matrix,
then compare pinned ggml with a native implementation using paired aligned
16-bit quant loads. Preserve Q6_K bytes, lane/reduction order, F32 outputs and
the original 64-thread work mapping. The 210-byte quant block stride permits
2-byte, not arbitrary 4-byte, alignment. The compiler may already combine loads;
a speed benefit is a hypothesis.

The C diagnostic capture owns files only and marks the activation output before
graph allocation so its lifetime survives compute. Capture is never enabled in
performance runs. The standalone Objective-C++ probe owns its buffers/queue and
reads exact recorded weights/activations; it is not a product execution path or
an alternative inference engine. Check all vocabulary outputs for at least one
prefill and two decode activations, with the existing absolute bound 0.01 and
identical greedy argmax, before timing. Include a row-tail shape using a subset
of the same real weights. All values must be finite. No post-measurement tolerance
change or weight conversion is permitted.

Ceilings: bounded build <=900 seconds; each measurement campaign <=900 seconds,
five alternating pairs, warmups and synchronized equal invocation counts; at most
two full weight allocations and existing local probe output/input buffers.
Record wall and GPU times where supported, source/artifact hashes, exact inputs
and all samples. CPU/CUDA are deferred; this is a local Metal experiment, not a
whole-model speed claim. Locally promising results may justify selectable graph
integration with real request verification; a local loss rejects this load
strategy only. Root coordinates GPU use to prevent competing measurements.

Local closure: all three real activation/full-vocabulary and row-tail checks
are exact, but every five-pair improvement range crosses zero in traced and
untraced campaigns. Do not integrate this paired-load kernel. Retain the
independent probe and all samples; next attribution/mapping hypotheses are in
`../final-prefill-q6-trial.md`. This result imposes no general backend restriction.
The subsequent real-model decode diagnostic found matching Q6_K and other major
Metal kernel launch signatures in Align and pinned llama.cpp; its deliberately
pruned graph bounds connected projection cost but is not an inference path. See
`../qwen35-decode-attribution.md`. The mapped-weight experiment below tested
the storage hypothesis; its real-model result is in `../mapped-weight-trial.md`.

### Q6_K four-row mapping screen (2026-09-27)

The retained actual-weight Q6_K output projection is one of the largest decode
shaders. The pinned kernel and the prior paired-load probe assign two output
rows per SIMD group. Screen four rows per SIMD group using the same Q6_K bytes,
F32 activation, per-row arithmetic, 64-thread group and output format. This
halves the output-row group count and can reuse the input fragment, but reads
the same weight bytes and may worsen register pressure or occupancy. The
prior two-row source and ggml graph remain the controls; this is a local probe
outside production inference, not an adoption or general-backend claim.

Build ceiling 900 seconds and measurement ceiling 900 seconds. Use the three
captured 2B prefill/decode activations, the full 248,320-row output and a
257-row tail; before timing require finite full-row values within the existing
predeclared 0.01 absolute bound and identical first-index argmax. Keep twelve
warmups, five alternating pairs of twenty synchronized operations per arm,
all samples, the unchanged Q6_K weights and at most the existing two weight
buffers. A local gain only permits a reversible real-model trial with full
logit/state/generation and request checks; a local loss rejects this mapping,
not other GPU layouts or independent backends.

If the four-row mapping has no local gain, measure a read-only ceiling on the
same 417,177,600 captured Q6_K bytes. A Metal shader reads every 32-bit word
contiguously, reduces it to a checked checksum and writes only group sums; it
does not dequantize or produce logits. This isolates attainable contiguous
read throughput as a diagnostic comparison, not a candidate inference path.
Use one Metal weight buffer, twelve warmups and five batches of twenty
synchronized GPU-timed reads; build and measurement each remain <=900 seconds.
Check the complete GPU checksum against a CPU sum before timing. Compare its
effective bytes/time with the real Q6_K projection and the trace counter,
without calling the difference an achievable kernel speedup.

Local closure: the three captured full and tail projections matched the
pinned ggml output exactly. Five paired local comparisons per activation
showed no repeatable four-row gain; the separately checked contiguous read
was slower than the projection and is not a bandwidth roof. Withdraw this
mapping without a runtime trial. Preserve the actual-output oracle and the
ggml path; see `../qwen35-q6-four-row-screen.md` and its complete receipts.
The next bounded Q4_0 screen must change weight layout or bytes, include the
one-time conversion and resident-memory costs, and qualify actual weights
before any real-model integration.

### Q4_0 split-scale resident layout screen (2026-09-27)

The current Q4_0 block is 18 bytes: one F16 scale followed by 16 packed
quant bytes. Screen a lossless resident layout with all F16 scales contiguous
and all 16-byte quant payloads contiguous, preserving each original block's
position and every F32 input. The proposed Metal decode vector kernel can
read aligned quant payloads while retaining the pinned four-row/SIMD work
distribution and Q4_0 dot arithmetic. This is an independent local probe, not
a new GGUF, persisted pack, production backend, or model-name gate.

The existing capture owner must first record one actual 2B decode request's
FFN weights and activations, and `check-native-captures weights` must verify
all captured weight bytes against the source GGUF. Screen actual layer-23 gate
`[2048,6144]` and down `[6144,2048]` Q4_0 projections, using their captured
input and gated activation respectively. Before timing require all finite
outputs within the predeclared `0.005 + 0.0005*abs(ggml)` bound against a
pinned ggml graph; the down graph must also match the captured output under
that same bound. Record conversion time, input/output/weight extents and hashes,
resident bytes, Metal pipeline geometry, twelve warmups and five alternating
pairs of twenty synchronized operations per arm, including all adverse pairs.
Build and each campaign <=900 seconds; at most one original and one converted
Metal weight allocation per tensor. A local gain only permits a reversible
real-model connection with logits/state and whole-request qualification. A
local loss rejects this layout, not another transfer mechanism.

The first same-layer screen is cache-sensitive: a 7 MB tensor repeatedly
invoked alone is not the real 24-layer decode working set. Repeat a lossless
raw/split comparison rotating through all 24 captured gate matrices and their
actual activation vectors, with exact ggml output checks for each layer. Keep
the same three-arm local result and conversion cost visible; judge the layout
by paired raw-versus-split GPU and wall times in the rotated working set.

If split layout does not give a consistent gain, screen the existing Q4_0
layout at two and eight versus four output rows per SIMD group on the same rotating
working set. This changes register pressure and the number of independent
groups while retaining all bytes, four-row ggml/native controls, dot arithmetic,
input, and output. Require exact local outputs before timing, then twelve
warmups and five alternating pairs of twenty operations for each arm. It is a
separate occupancy/parallelism hypothesis, not a claim that low occupancy
alone is a fault. Use separate byte-identical source-weight buffers per arm
while rotating layers; sharing one buffer gave the second arm an order-dependent
cache advantage in an initial invalid comparison. Build and measurement each
remain <=900 seconds.

**Result.** All 72 captured FFN weights matched the GGUF byte for byte. The
lossless split and two/eight-row probes matched all 24 gate outputs exactly;
layer-23 down also matched its captured output. Splitting the 24 gate matrices
kept the same 169,869,312 total resident weight bytes but took 40.75 ms of
local CPU conversion. Its rotated raw-minus-split GPU median was +0.007 ms
with only 3/5 wins. Separate-buffer two/eight-row probes lost to four rows in
GPU intervals, with 0/5, 0/5 and 1/5 candidate wins across the three screens.
No Q4_0 candidate was connected to the real-model runtime, so no whole-request
gain is claimed. Conditions, exact comparisons and receipts are in
[`qwen35-q4-layout-screen.md`](../qwen35-q4-layout-screen.md).

### Mapped Alignpack weight trial (2026-09-26)

This is an opt-in Qwen3.5 Metal resident-session experiment. The existing upload
path remains the comparison and fallback. The local 2B pack has 64-byte member
alignment, is 1,621,209,088 bytes, and can be wrapped as a read-only shared
Metal buffer on the M1. This feasibility check does not establish a speed gain.

| Contract | Definition |
| --- | --- |
| Selection / owner | `runtime_qwen35_execution.read` accepts `ALIGN_LLM_MAPPED_WEIGHTS=0` (default) or `1`; all other values fail before allocation. `runtime_qwen35_generation.prepare` selects the path after bounded pack validation and plan construction. CPU/CUDA and other models retain their existing path. No public CLI, persisted format or cache schema changes. |
| ABI / lifetime | `align_gpu_mapped_weights_open(owner, path, length)` opens and maps the actual pack after admission and before allocation, accepting the same absolute or relative pack path as the existing provider. The descriptor closes after mmap; the shim owns the mapping until the GPU owner is synchronized and released. `align_gpu_weight_add_mapped(..., pack_offset, nbytes)` places a validated tensor in that buffer; it never uploads a copy. The Align plan owns every offset, shape, order and admission decision. Native code only opens, wraps, bounds-checks and places storage. |
| Identity / mutation | The existing `runtime_pack_identity.verify_file_bounded` remains the semantic admission step. The thin map opener checks regular file, exact size and current path; the current loader also does not pin or hash every payload byte against concurrent mutation. This opt-in trial assumes a stable local pack during construction and inference; mapped-file truncation is a known process fault. Production adoption requires a same-descriptor validation or immutable-pack contract. |
| Budget / cleanup | Admission charges the full mapped file extent as weights, not the sum of tensor bytes. There is one mapping, one backend buffer, no second weight allocation and no upload. The descriptor closes immediately after mmap; failure at any later prefix leaves ordinary owner cleanup responsible for buffer free before unmap. Existing graph, KV, input and session state remain owned as before. |
| Performance cost ceiling | One admitted file mapping and one Metal buffer replace one owned weight buffer; no extra full-weight allocation. Build and owner preparation are bounded to 3,600 s per attempt, each alternating campaign to 900 s, and each real request to 180 s. The final report distinguishes any runtime or memory gain from construction and page-fault cost. |
| Correctness / measurement | Compare byte identity of placed tensors, 2B/0.8B generation, repeated requests, logits and recurrent state at the predeclared existing bounds. Then alternate old/new/pinned-llama runs using the same weights, tokens and options. Record load, first request, warm prefill/decode, whole request and physical memory. Small or negative changes are reported as measured; there is no percentage gate. |

| Closure case | Owner / verification |
| --- | --- |
| Valid construction and requests | `runtime_qwen35_generation`, `runtime_qwen_load`, `runtime_weights`, `ggml_ffi`, real shim; focused 2B and 0.8B generation and HTTP/SSE owners. |
| Invalid option, alignment, extent and file | Parser refusal; shim returns CONFIG/UNSUPPORTED/ALLOCATION before tensor placement; focused mapped-weight owner and real-model negative probes. |
| Partial placement, graph fault and early release | Owner destruction synchronizes GPU, frees backend buffer, then unmaps; the file descriptor is already closed. Focused native owner and existing device cleanup owner. |
| Model bytes and state | Full tensor bytes must equal the validated pack slices; existing logit, state and repeated-request captures compare against default-off. |
| Measurement / fallback | Default-off baseline and opt-in candidate share a binary and backend bundle; record all alternating samples and memory observations. |

Local closure: the opt-in path passed 2B/0.8B generation and 2B serving owners,
with 744,960 exact 2B logit values and 258 exact state records. Five-pair worker
and HTTP/SSE campaigns show isolated startup improvement but no stable warm
request or decode gain. Keep default off. A same-descriptor or immutable-pack
contract and physical-memory evidence are prerequisites for production use;
the trial result does not impose a percentage floor on another candidate.
The independent reader compared all 321 members against each source GGUF
(1,621,089,536 bytes for 2B; 822,246,656 bytes for 0.8B); the direct
pack-offset pointer placement is checked in the shim. Full GPU-weight readback,
an isolated load-only clock and whole-system physical-memory attribution remain
explicitly deferred while the mode is experimental and default-off.

### Single-token Qwen3.5 attention layout trial (2026-09-27)

The actual 2B Metal decode trace contains a `permute` plus `contiguous` copy for
each full-attention K and V projection. With one token, a contiguous
`[head_dim, kv_heads, 1]` projection has the same element order as
`[head_dim, 1, kv_heads]`. The Qwen3.5 builder may select a metadata-only reshape
for K after RoPE and V after projection at `count == 1`; multi-token prefill keeps
the existing permute and copy. The shim must reject a noncontiguous reshape
input rather than assume layout. No ABI, retained buffer, state owner, model IR,
format, or public configuration changes. The previous binary is the rollback
control; ggml still runs the remaining graph and compute kernels.

Before timing, compare actual 2B final-prefill and decode logits against the
unchanged binary at the existing predeclared absolute bound 0.01 and identical
argmax, plus exact resident-state hashes and generated output. Include repeated
requests and 0.8B owner qualification. The operation change should preserve
element order exactly; any numerical difference needs investigation. Then run
at least five alternating old/new/pinned-llama real 200/32 requests with the
same GGUF, pack, prompt IDs and options, plus a shorter and longer condition;
report graph dispatch counts, prefill, decode, complete request, load and memory.
The campaign ceiling is 900 seconds, request ceiling 180 seconds, and no extra
retained device allocation is allowed. Adoption depends on measured real effect,
regressions and maintenance cost without a percentage floor. Build failure,
noncontiguous source, or owner failure reverts this trial before timing.

Local closure: the implementation passed 2B/0.8B generation owners; three 2B
full-vocabulary captures were bit-identical and 336 resident-state hashes
matched. Metal decode dispatches fell from 663 to 651, but five-pair worker and
HTTP/SSE measurements found no repeatable request or decode gain. The trial
code was removed; its patch and raw observations remain in local diagnostics.
This rejects the singleton-copy change as a speed optimization on this host,
not a general claim about fusion or an independent backend.

### Qwen3.5 recurrent parity placement trial (2026-09-27)

The current 2B decode graph writes 18 convolution and 18 DeltaNet state tensors
per token. A counter-enabled trace sampled `kernel_cpy_f32_f32` for about
99 ms per Align request versus 35 ms per pinned llama.cpp request after
normalizing two and three identical 200/32 requests respectively. These are
sampled, instrumented shader intervals, not isolated copy clocks or a speedup
prediction. Both paths dispatch the same 36 large state copies and use shared
Metal buffers. An independent binding trace found that Align's inactive state
destinations span about 38 MB because parity is interleaved by layer, while the
reference's single state buffer spans about 20 MB. The previous 2B trial that
removed 12 small K/V materializations did not improve requests. Test state
placement next without weakening success-only publication.

| Trial contract | Boundary |
| --- | --- |
| Selection and rollback | A separately built candidate changes only Qwen3.5 recurrent resident index and allocation order. The unchanged binary and bundle remain the control; no new CLI, environment flag, persisted format, Model IR, or ggml scheduler change. Align retains both parity planes and flips the active index only after a complete successful graph. |
| Placement | Keep the six attention layers' K/V members first. Group all recurrent convolution/DeltaNet tensors of parity zero, then all of parity one, each in layer order. The shape selected for each index must match `recurrent_index`; total resident allocation and tensor types remain unchanged. The existing ggml copy operation and fallback graph remain. |
| Correctness | The geometry owner checks the complete 84-index bijection and both parity directions. Real 2B and 0.8B generation owners cover reset, failed input recovery and early exit. The 2B full-logit and resident-state oracle must match the unchanged binary exactly before speed interpretation. No numerical tolerance is widened. |
| Measurement | Capture one diagnostic copy-binding census to confirm the destination span, then run at least five alternating control/candidate/pinned-llama pairs at 64/16, 200/32 and 330/64 with the same GGUF, pack, prompt IDs and generation settings. Separate prefill, decode, request and construction. Record every adverse pair and memory allocation. Profiled clocks cannot replace the untraced paired request result. |
| Cost ceiling and decision | Preparation and owners: 2,700 seconds; paired campaign: 1,500 seconds; one request: 180 seconds. Keep the trial only if correctness holds and the connected gain survives variability, workload and memory/maintenance assessment. No percentage or win-count floor applies. If the copy sample gap remains after placement, investigate the shared state copy's dependency and memory access pattern rather than attributing it to parity order. |

Construction maps `runtime_qwen35_state.recurrent_index` to
`runtime_qwen35_load.add_resident` and its geometry smoke. Success maps
`read_index`, `write_index` and `finish` to exact state/logit and generation
owners. Invalid geometry and malformed requests retain their existing refusal;
failure and early exit retain inactive-state isolation and session cleanup in
the real generation owner. The trial adds no new allocation owner or cleanup
path. CPU/CUDA and Gemma performance remain unmeasured, and Qwen/Gemma model
semantics are unchanged.

**Result and decision.** The parity-major candidate compiled and its geometry
owner passed. On the real 2B Q4_0 model, three complete 248,320-element logit
rows and 336 semantic resident-state hashes matched the unchanged binary
byte for byte; both the 2B and 0.8B generation owners matched pinned llama.cpp
on three prompt lengths and six retained requests, including invalid-input
recovery. The independent binding census confirmed the final decode's 36 large
state-copy destination offsets now span 19,152,896 bytes between first and
last starts, versus 38,305,792 before; the reference span is 19,152,896.
The resident Metal buffer remained 68,714,496 bytes with both parity planes.
The copy dispatch count and launch shapes did not change.

The Apple M1 16 GiB worker ran five alternating control/candidate/pinned-llama
pairs per case after two warm requests per process. Both Align arms used the
same 2B GGUF, alignpack, prompt IDs, generation settings, adjacent-range
bundle and execution flags. Control binary SHA256 was
`b62a2d5d7e88dee85b4f3f672b4b4dca15a74d24fc5e89df5791cf277c6a0450`;
candidate was
`7173db47ce0e78ae371fecd2737125dea3cb96108cf51a3babd94b0b8bdfd99e`.
The paired delta is control minus candidate, so positive favors the trial.
The wall run had no phase interposer; the separate phase run's graph clocks
include synchronization and are not shader-only timings.
The complete portable paired receipts, including all prompt IDs and adverse
samples, are [`wall.json`](../../eval/benchmarks/qwen35-parity-placement-2026-09-27/wall.json)
and [`phase.json`](../../eval/benchmarks/qwen35-parity-placement-2026-09-27/phase.json).

| Input / output | Untraced request paired median (ms), trial wins | Control / trial / llama request medians (ms) | Instrumented prefill / decode paired medians (ms) |
| --- | ---: | ---: | ---: |
| 64 / 16 | +0.397, 3/5 | 565.808 / 567.419 / 555.915 | -0.170 / -5.224 |
| 200 / 32 | -3.195, 2/5 | 1290.215 / 1291.643 / 1255.368 | -1.207 / +2.605 |
| 330 / 64 | -18.414, 1/5 | 2428.006 / 2440.918 / 2379.613 | +1.089 / +1.557 |

The untraced paired ranges were -6.820 to +4.563, -11.984 to +4.746,
and -55.334 to +14.071 ms in table order. The phase run's 330/64 request
paired median was +4.674 ms, but that direction did not survive the untraced
run. Construction-to-ready varied widely: untraced paired startup medians were
+126.899, -8.625, and -27.923 ms, with individual differences as large as
-430.666/+350.061 ms; OS file-cache state was uncontrolled. Pinned llama.cpp
was faster than both Align binaries at every untraced request median. No
isolated physical-memory measurement was made; the unchanged resident buffer
length is the memory fact supported by the binding census.

**Withdraw the parity placement change.** Its intended layout was achieved and
correctness held, but the untraced connected requests did not improve
repeatably, and the long case regressed. The original Align source and binary
were restored. The exact rejected source patch, two binaries, copy-binding
logs, complete worker receipts and owner logs remain under the Git common
directory's
`diagnostics/q35-ingraph-greedy-2026-09-27/counter-trace-20260927/`.
The next GPU hypothesis is that the recurrent producer's separate workspace
output and resident `CPY` form a material execution boundary. Inspect the
DeltaNet output/state write and dependency timeline, then test an opt-in direct
resident-state write or a larger fused operation while preserving success-only
publication and the ggml fallback. The placement result alone cannot establish
the benefit of that fusion.

### Contiguous F32 Metal copy specialization trial (2026-09-27)

The actual Qwen3.5-2B final decode graph contains 36 large F32 state-copy
nodes. An independent graph census found 18 convolution copies of 73,728
bytes with noncontiguous sources and 18 DeltaNet copies of 1,048,576 bytes
with contiguous source and destination (18,874,368 bytes per decode step).
Pinned ggml's generic `kernel_cpy_f32_f32` calculates a destination multidimensional
coordinate with integer divisions for each row. Test whether a linear-index
path for exactly contiguous, equal-type copies improves the connected graph.
The strided copies and every other type/layout retain the generic kernel.

| Trial contract | Boundary |
| --- | --- |
| Selection and rollback | An opt-in, digest-identified pinned ggml Metal backend patch selects only F32-to-F32 copies with at least 262,144 elements and contiguous source and destination. The unchanged adjacent-range bundle and Align binary remain the control. No model-name gate, Align CLI/API change, Python product path, precision change or extra state allocation. |
| Correctness | Test representative contiguous/strided local tensors first, then exact 2B full logits and all resident-state hashes, 2B/0.8B generation owners including failure recovery, and same-model output against pinned llama.cpp. Never assume a fast copy is numerically safe solely because types match. |
| Measurement | Count specialized dispatches in the actual decode graph. Compare local actual-state copy, synchronized prefill/decode, untraced complete requests and construction, with at least five alternating control/trial/reference pairs at 64/16, 200/32 and 330/64. Retain adverse samples and inspect changed buffer ownership, barriers and synchronization. |
| Cost ceiling | Preparation, build and owners <=2,700 seconds; paired campaign <=1,500 seconds; one request <=180 seconds. Assess reproducibility, workload, memory and maintenance rather than a fixed improvement percentage. Withdraw the patch if the connected cost does not improve defensibly. |

The developer recipe CLI adds `--linear-copy` (default off). It requires
`--backend metal --adjacent-ranges --base-bundle PATH`; CUDA, plan-only mode,
and missing prerequisites refuse before build. The new output path must not
exist. The recipe owns patch application and output staging. A successful
bundle retains `metal-linear-copy.patch`, binds its SHA256 through
`-DALIGN_LLM_LINEAR_COPY_PATCH_SHA256` in the existing schema-1 manifest and
bundle identity, and reuses only the verified byte-identical shared ggml core
from the base. The Metal plugin is rebuilt. No product CLI, state owner,
persisted model format or inference cache key changes. Parser errors exit 2;
recipe validation errors exit 1. Source-pinned, toolchain, base artifact,
patch-application and output-existence validation precede publication of a
new bundle. The old bundle and generic copy path are the rollback.

| Closure condition | Implementation | Evidence owner |
| --- | --- | --- |
| Construction / success | `gpu_backend_recipe.py` applies the patch and retains its digest and new plugin; Metal copy kernel checks type, minimum element count and both physical strides before linear indexing | `scripts/run-gpu-backend-recipe-smoke`, real bundle manifest, 2B exact logit/state comparison |
| Malformed input / failure / early exit | CLI prerequisite and base-bundle checks refuse; a failed build leaves no published output; inference keeps existing failure and parity publication paths | `scripts/run-gpu-backend-recipe-smoke`, 2B/0.8B `scripts/run-qwen35-generation-smoke` |
| Cleanup / repeated session | Recipe staging is temporary; successful generation reuses the existing session state without an extra allocation or copy owner | Bundle inspection and both generation owners |

CPU/CUDA and Gemma remain unmeasured for this trial. The Metal kernel
specialization is independent of model name; architecture-specific semantics
remain in the existing model definitions.

**Result and decision.** The pinned 2B final decode binding census confirmed
18 eligible contiguous DeltaNet copies (18,874,368 bytes per token) and 18
ineligible strided convolution sources; buffer ownership, storage mode,
dispatch count and launch shapes did not change. Three actual 2B full-logit
rows and 336 resident-state hashes were bit-identical to the control. The
2B/0.8B generation owners passed on the discovery, measured recipe and clean
final bundles, including retained requests and failure recovery. The
predeclared standalone copy owner passed six full-destination F32 bit
comparisons against its CPU oracle on both control and clean final bundles:
below/at threshold, contiguous four-dimensional and offset views, and
strided source/destination views. This is a focused set, not proof for every
possible view geometry.

On the Apple M1 16 GiB host, two independent five-pair 2B untraced campaigns
at 64/16, 200/32 and 330/64 won all 30 control comparisons. The measured
recipe bundle's paired control-minus-trial request medians were
+52.866, +99.577 and +193.448 ms; its arm medians were also shorter than
pinned llama.cpp's at each condition. The second Qwen size, 0.8B, won 14/15
control pairs; the short case retained one -11.338 ms trial regression.
The separate 2B phase campaign showed most of the gain in decode, and a
counter-enabled trace reduced summed F32 copy Shader Timeline samples from
199.922 to 11.228 ms for two matched requests. Trace samples are attribution,
not marginal request savings. A direct same-binary comparison with the
pre-adjacent Metal bundle won all 15 uninstrumented 2B pairs and all 15
paired comparisons with pinned llama.cpp at the three named lengths. Its
base-minus-final request medians were +55.011, +111.526 and +224.990 ms.
Five alternating 200/32 process-footprint pairs found after-three-request
control/final arm medians of 145.345/145.392 MiB and peak arm medians of
146.860/146.892 MiB; this is process attribution, not total GPU/system memory.
The second-size 0.8B direct-baseline campaign also won all 15 Align pairs;
its pinned llama.cpp comparison won 14/15, retaining one -15.966 ms 330/64
pair. Its base-minus-final paired request medians were +60.626, +110.062 and
+230.010 ms. The previous 0.8B short regression against the adjacent-range
control remains in the earlier receipt.
Startup remains mixed. The patch adds no allocation or copy owner, and the
common shared-buffer bindings remain. Recommend the explicit copy-specialized
bundle for the measured Apple M1 Qwen3.5 local profile, with the ordinary
bundle as rollback; other hosts and architectures remain unadmitted. The exact
conditions, all samples, binary comparison and decision are in
[`qwen35-metal-linear-copy-trial.md`](../qwen35-metal-linear-copy-trial.md)
and its linked receipts. Do not infer a universal speed floor or Gemma/CUDA
support from this host.

The predeclared local geometry owner uses the same pinned Metal bundle family.
It compares the control and specialized bundle against a CPU-computed F32 byte
oracle for contiguous copies immediately below and at the 262,144-element
boundary, a four-dimensional contiguous view, a nonzero-offset contiguous
view, a large strided source, and a large strided destination. Check untouched
destination sentinel elements as well as copied elements. The focused fixture
has a 900-second build/run ceiling and no inference-mode change. Its passing
result narrows the remaining decision to physical memory, startup and host
scope; it does not alone establish those.

The following memory screen uses the same saved 2B binary, prompt IDs,
resident options and 200/32 request in each arm. After one untimed process
per arm, run five alternating control/final-bundle pairs. Record
construction-to-ready time and macOS `footprint` current/peak bytes plus
process RSS both at ready and after three identical requests. Compare paired
distributions; do not count `footprint` as total system or GPU physical memory.
The five-pair campaign has a 900-second ceiling. Neither startup nor memory
needs to improve for adoption, but a defensible regression must be assessed.

Before recommending the combined bundle for the tested host, also compare it
with the pre-adjacent Metal bundle, using the same saved Align binary and
disabled in-graph greedy path. The adjacent-range arm is a valid copy-specific
control but is not the ordinary pre-adjacent baseline. Repeat the existing
five-pair uninstrumented 64/16, 200/32 and 330/64 worker protocol against the
pinned llama.cpp executable; retain all output/count checks and adverse
samples. This additional campaign has a 1,500-second ceiling.
For a recommendation that includes Qwen3.5-0.8B, repeat that direct
pre-adjacent/final/reference protocol with its own GGUF, pack and Model IR.
Keep the earlier adverse 0.8B short pair visible and assess the new direct
baseline separately; one 0.8B campaign has the same 1,500-second ceiling.

### GPU greedy readback trial (2026-09-27)

Current Qwen3.5 greedy generation reads 248,320 F32 logits (993,280 bytes) to
the host after every graph and scans them in Align. Test whether a device
argmax followed by a four-byte readback reduces the actual request boundary.
The existing ggml Metal `ARGMAX` kernel is a local experiment: it selects the
highest index among equal maxima, whereas Align's CPU greedy selects the lowest,
and it does not report nonfinite values in the same way. It therefore cannot be
treated as strict compatibility or adopted by default without a semantics fix.

| Contract | Definition |
| --- | --- |
| Selection / owner | `ALIGN_LLM_GPU_GREEDY=0` or absent keeps full-logit readback and Align's existing greedy scan. `1` opts into the Qwen3.5 Metal trial; other values fail before allocation. Align owns mode selection, graph output, token selection, and the generation loop in normal and streaming sessions. CPU/CUDA and other model families are not admitted to this trial. |
| Graph / ABI | A thin checked `op_argmax` shim wraps `ggml_argmax` only for one contiguous F32 vocabulary row and exposes one I32 scalar slot. The Qwen3.5 builder expands either that scalar or the existing logits output, including every state root. The mode enters all graph keys. The graph compute and memory allocator remain ggml; no separate C/C++ generation engine is added. |
| Readback / lifetime | In mode `1`, Align reads exactly four bytes, checks the decoded index against `n_vocab`, and owns the returned token. Mode `0` retains the full F32 readback and finite-value checks. The scalar output lives through synchronized graph compute/readback; failures leave the existing unhealthy-session cleanup. No persisted or exchanged format changes. |
| Correctness | Before timing, compare exact greedy tokens on real 2B and 0.8B short/chunked/wider prompts, retained repeated and streaming requests, plus full resident-state hashes. Capture baseline full logits separately and confirm all compared vectors are finite and their maximum is unique. The trial remains explicitly non-strict for untested ties/nonfinite values. Do not relax the CPU path's existing rules. |
| Measurement / ceiling | Same GGUF, pack, backend bundle, prompt IDs and generation counts. Five alternating old/new/pinned-llama worker pairs and same-binary HTTP/SSE pairs at 64/16, 200/32 and 330/64 after two warmups. Report GPU graph/readback count, prefill, decode, whole request, startup and memory. Campaign <=900 s, request <=180 s; mode `1` may add one four-byte graph output but no retained full-vocabulary host buffer. No percentage floor. |

Closure: parser and unsupported-backend refusal own construction/malformed
cases; model graph and shim own shape, output lifetime and failure; normal and
streaming generation own token range and state publication; 2B/0.8B owners,
capture/state oracle and alternating measurements own success and regression.
Session destruction and early exit retain existing cleanup. A speed gain only
justifies further work on lowest-index tie and nonfinite behavior; it does not
promote this provisional kernel to strict production use.

Local closure: 2B/0.8B generation owners passed and 336 state hashes matched;
three baseline full-logit vectors were finite with unique maxima. The four-byte
readback was observed, but the existing Metal argmax added decode time: 200/32
worker decode median 878.776 to 890.079 ms, and four of five whole-request
worker pairs slowed. HTTP/SSE was mixed to adverse, including five of five
slower 330/64 HTTP pairs. The trial code was removed; raw evidence and the
replayable patch remain in local diagnostics. A single-threadgroup reduction
over the 248,320-element row is the next kernel hypothesis, not a shipping
result. The shared-output experiment below tests a different boundary.

### Shared Metal logits view trial (2026-09-27)

An actual synchronized 2B output probe found the logits tensor in a `MTL0`
shared buffer; its host pointer matched all 993,280 bytes returned by the
ordinary readback. Test a borrowed view of that exact output so Align's existing
finite-checking, lowest-index-tie greedy implementation scans the same F32
values without a second full-vector copy. This is restricted to a Metal shared
buffer and is not a general backend assumption.

| Contract | Definition |
| --- | --- |
| Selection / owner | `ALIGN_LLM_SHARED_LOGITS=0` or absent keeps the current copied readback; `1` selects the Qwen3.5 trial once per session; other values fail before allocation. Align owns the choice and the greedy scan in normal and streaming generation. Other model providers retain their current paths. |
| Thin ABI / borrow | `align_gpu_slot_shared_view` returns a pointer only for an output node in a successfully executed graph, exactly one contiguous F32 vocabulary row, the expected byte extent, and a Metal shared buffer whose pointer lies within its checked allocation. It refuses private/other buffers. `ggml_ffi` creates a resource-tied borrowed `slice<u8>` from the pointer; the view is consumed immediately before graph reset, reuse, or device mutation. No C sampling or token logic. |
| Lifetime / failure | Existing synchronized `runtime_execution.compute` remains mandatory before the view. The graph output and its owner stay live during Align's scan. The view cannot escape the read-choice call. Unsupported storage or malformed extent fails the opt-in session and uses existing unhealthy-session cleanup; mode `0` remains the rollback. No new retained device allocation, format, IR or graph identity change. |
| Correctness | Before timing, compare real 2B/0.8B normal/streaming/repeated requests with pinned llama.cpp and old Align; 2B full-logit F32 bytes and all resident state hashes must be exact. Check invalid flag and unsupported/private buffer refusal. The CPU greedy function and its tolerance/finite/tie rules are unchanged. |
| Measurement / ceiling | Same GGUF, pack, backend bundle, prompt IDs and output lengths; two warmups and at least five alternating pairs on 64/16, 200/32 and 330/64, with pinned llama worker and same-binary HTTP/SSE. Report copied bytes, prefill, decode, whole request, startup and memory. One campaign <=900 s and one request <=180 s. No percentage floor; adoption weighs actual benefit, regressions and the added borrow contract. |

Closure: parser and shared-buffer refusal cover construction/malformed cases;
the shim's executed-node and bounds checks cover success/failure and stale
views; `ggml_ffi` confines the borrow to the device owner; both generation
loops consume it before state advance; existing request cleanup handles early
exit and failure. The full-logit oracle, state oracle and retained-session owners
cover exactness and cross-request separation. CPU/CUDA and Gemma require their
own storage/semantic admission before this mode can be reused.

Local result: three full 2B output vectors and 336 state-plane hashes matched
the old binary exactly; the opt-in view made zero full-logit `tensor_get` calls.
The 2B/0.8B generation and 2B HTTP/SSE owners passed. Five-pair worker request
medians at 64/16, 200/32 and 330/64 changed 574.549→572.263,
1292.508→1288.627 and 2426.843→2426.037 ms, but only three of five pairs
improved in each condition. SSE slowed in the first two conditions. Pinned
llama.cpp remained faster in all worker request medians. Retain the opt-in mode
for bounded follow-up; do not enable it by default or claim a request speedup.
See `docs/qwen35-shared-logits-trial.md` and its complete receipts. Removing a
copy does not prove that the same cold shared-memory scan is cheaper; the next
performance candidate must address a larger measured part of graph execution.
Review found and repaired intermediate-prefill greedy scanning when the
full-logits mode spans chunks. The copied mode retains its earlier intermediate
readback, while only final-chunk logits are sampled in both modes; the 200/16
same-binary HTTP/SSE and longer real generation owners pass after repair.

### Hierarchical Metal greedy screen (2026-09-27)

The pinned Metal `kernel_argmax_f32` dispatches one threadgroup for a
248,320-value Qwen3.5 output row and assigns each thread roughly 970 serial
values. It also selects the highest index on ties and does not match Align's
nonfinite refusal. Test a two-stage native Metal reduction over real captured
2B logits before adding another runtime path. Stage one reduces disjoint row
tiles; stage two reduces the tile results. Both carry a nonfinite flag and
select the lowest index among equal finite maxima. No model name or fixed
vocabulary count enters the kernel; row length and launch geometry are inputs.

The independent diagnostic may use Objective-C++ to create Metal buffers and
command buffers, but it must not become a product generation path. Compare
the exact same real F32 output against Align's first-index finite greedy rule,
including tied maxima, NaN and infinity refusal before timing. For each arm,
a GPU blit writes a fresh shared result buffer to approximate a graph-produced
output. The control synchronizes then scans that buffer on CPU. The candidate
blits, dispatches both reductions in the same command buffer, synchronizes,
then reads one I32 result. Report GPU-only and synchronized wall intervals
separately; this is a boundary screen, not a connected request benchmark.

At most two 993,280-byte logit buffers and one tile buffer; no weights or
inference state allocation. Build <=900 seconds, campaign <=900 seconds,
100 warmup and 100 alternating measured iterations per actual vector, with
every sample retained and no percentage floor. A local loss ends this kernel
strategy. A local win only warrants a selectable real-model integration with
the old ggml graph/readback path intact, exact logits/state and alternating
prefill/decode/request measurements; it is not a production adoption result.

Local screen: all three actual 2B vectors, first-index ties, NaN and infinity
cases passed. With GPU production and both reductions in one command buffer,
the paired median wall reductions were 0.230–0.283 ms over CPU scanning, with
96–97 of 100 pairs faster. With an extra post-synchronization command buffer,
the reduction was only 0.071–0.103 ms, with 90–94 of 100 pairs faster.
Measured GPU execution increased by about 0.10 ms; the gain comes from moving
the scan off the CPU critical path. Raw samples and source are retained in
local diagnostics. These are screening numbers, not an inference speedup.

### Post-sync hierarchical greedy real-model trial (2026-09-27)

The local screen justifies one selectable real-model integration, including
its extra command buffer. It does not justify replacing ggml graph execution
or skipping graph synchronization. The current output is shared Metal memory;
the pinned Metal plugin exposes the backing `MTLBuffer` and offset through
`ggml_metal_buffer_get_id`. A narrow Metal helper may use that exact buffer,
without copying or rewrapping its pointer, to dispatch the two reductions
after `runtime_execution.compute` has synchronized. The ordinary full-logit
readback and Align greedy remain the default and rollback.

| Contract | Definition |
| --- | --- |
| Selection / ownership | `ALIGN_LLM_HIER_GREEDY=0` or absent uses the existing copied readback; `1` selects this Qwen3.5 session experiment. `ALIGN_LLM_HIER_GREEDY_LIBRARY` supplies an absolute path to the trial Metal helper only in mode `1`; invalid flags or missing/relative paths refuse before session allocation. Align owns the mode, token, normal/streaming generation loop and session lifetime. This mode and shared-CPU-logits mode cannot both be selected. |
| Thin ABI | `align_gpu_slot_hier_greedy` accepts the GPU owner, completed graph output slot, exact expected F32 row bytes and helper path; it checks executed-node identity, contiguous extent, shared Metal buffer and bounds as the borrowed-view trial does. It passes the actual ggml Metal buffer handle/offset to the helper. The helper contains only Metal device/queue/pipelines, two reduction dispatches, bounded scratch and synchronous four-byte result; no model/weight/prompt/tokenizer or generation logic. |
| Lifetime / failure | One helper instance per `GpuDevice` is created lazily and reused across requests, then destroyed before the device and ggml plugin unload. The graph output and backing MTL buffer remain live through helper completion. A failed load, wrong backend/storage/extent, kernel error, nonfinite value or out-of-range index refuses the opt-in request; no silent fallback or partial state publication. Existing unhealthy-session cleanup remains. No persisted format or graph key change. |
| Semantics / evidence | The helper must select the lowest index among equal finite maxima and reject every NaN/infinity. Compare actual 2B/0.8B generation and SSE output with pinned llama.cpp and the old binary, exact 2B full logits and resident state, repeated requests, and malformed flag/path refusal. The helper does not alter any F32 model computation. |
| Measurement / ceiling | Same 2B GGUF, pack, geometry, backend bundle, token IDs and generated counts. At least five alternating control/candidate/pinned-llama worker pairs and same-binary HTTP/SSE pairs at 64/16, 200/32 and 330/64; two warmups. Report standalone, connected decode/prefill, startup, request and memory, including the new command-buffer boundary. One build <=900 s, one campaign <=900 s, request <=180 s; <=16 KiB scratch plus pipeline/queue state, no extra full-logit allocation. Decide with observed variability and maintenance cost, without a percentage floor. |

Closure: Align configuration handles construction and invalid settings;
the shim validates graph/state/storage before helper use; the Metal helper owns
pipeline setup, per-device scratch, completion and error; normal/streaming
generation own token publication; device close owns cleanup on success, early
exit and failure. Real-model owners and paired receipts own correctness and
performance. CPU/CUDA and Gemma remain outside this Metal trial pending their
own semantic and storage admission.

Trial closure: the integrated helper passed 2B/0.8B generation, 2B HTTP/SSE,
336 exact state-plane hashes and zero full-logit `tensor_get` calls. Its extra
post-sync command buffer won the local real-row screen by 0.071–0.103 ms,
but five-pair worker and same-binary HTTP/SSE results were mixed or adverse.
The integration was withdrawn; the default path is unchanged. See
`docs/qwen35-hierarchical-greedy-trial.md` and its raw receipts. This result
tests that boundary only; it does not rule out an in-graph reduction.

### In-graph hierarchical greedy trial (2026-09-27)

The post-sync Metal reduction passed real-row semantics but added a command
buffer and a wait. Test the same two-stage reduction as an opt-in ggml Metal
`ARGMAX` implementation in the command buffer that produces the logits. Align
selects the graph and token and retains the existing full-logit graph as the
control. The specialization is selected by contiguous F32 row shape, with
ordinary ggml behavior for other shapes and backends. The temporary partial
buffer belongs to the graph output allocation, so it lives through both
dispatches without a separate queue or host copy. The kernel must choose the
first maximum and return an invalid sentinel for any nonfinite input; Align
checks the four-byte result before publishing state.

Cost ceiling: one additional graph node, two Metal dispatches, at most
12 bytes per 1,024 logits of graph scratch, no extra full-row allocation,
one build attempt within 3,600 seconds and one alternating real-model campaign
within 900 seconds. Compare captured real rows and tie/nonfinite cases before
timing; then compare exact real 2B/0.8B tokens and resident state, worker and
HTTP/SSE requests, prefill, decode, load, and pinned llama.cpp. Use multiple
alternating samples at 64/16, 200/32, and 330/64. A local result is an
integration screen, not a production adoption criterion; observed variability,
memory, regressions and maintenance decide whether the opt-in should remain.

Closure: configuration rejects malformed/unsupported modes before allocation;
the Align graph builder and shim validate contiguous F32 shape and mode-specific
graph keys; ggml allocates scratch with the output; both Metal stages run in
the producing graph; generation validates the result in ordinary and streaming
paths; failed requests retain existing unhealthy-session cleanup. Existing
full-logit captures serve as the unchanged numeric oracle because the new
node consumes the same projection without changing its arithmetic.
Before weight allocation, the Qwen3.5 session asks the thin shim whether the
selected Metal plugin exports the `align_llm_metal_ingraph_argmax_v1` marker.
Mode `1` refuses an unpatched bundle or a vocabulary shorter than 8,192;
absent/`0` keeps the old graph. The threshold matches the backend's
hierarchical dispatch admission, so the opt-in cannot silently use the older
tie behavior.
The build recipe's `--ingraph-argmax` Metal-only option applies and retains
`scripts/metal-ingraph-argmax.patch` separately from `--native-swiglu`; each
patch digest enters the bundle build flags. Neither option changes persisted
model or session formats. Qualification and timing use the patched bundle
identity recorded with each receipt.

After the single-mode comparison, test the already implemented synchronous
weight upload and final-layer FFN-row options together with graph greedy against
the exact prechange Align binary and the fixed llama.cpp reference. Keep the
128-token prefill chunk, GGUF, quantization, prompt IDs and generated counts
equal. Report each of startup, prefill, decode and whole request from five
alternating pairs at the three representative lengths; finish each campaign
within 900 seconds. The earlier independent trials supply hypotheses, not an
assumption that their gains add. Retain the graph-only arm to distinguish the
new operation from existing options.

### Q6_K producer-side partial-maximum screen (2026-09-27)

The in-graph reduction removes host logit readback but adds two GPU dispatches;
its final-binary 330/64 graph phase is slower even where request wall time
improves. Screen a distinct fused producer epilogue: the actual Q6_K output
projection emits the best finite value and first index for each small output
tile, then one compact reduction selects the token. This is a local screen
before any runtime integration. The comparison is the current patched ggml
Q6_K projection followed by hierarchical argmax, using the same captured 2B
weights and final-prefill/decode activations. The fused arm must not omit work,
change quantization, suppress an invalid value, or use a separate command
buffer between projection and final reduction.

Cost ceiling: retain the existing Q6_K row arithmetic and 64-thread mapping
for this first screen; at most 12 bytes per four vocabulary rows of partial
storage plus four output bytes; no full-logit output in the fused arm; only a
four-byte result readback after synchronization in the timed operation. Qualify
all three captured activations and a
257-row tail against the existing full-logit oracle, requiring the exact
first-index greedy token and finite-input validity before timing. Use twelve
warmups and five alternating pairs with twenty synchronized operations per
arm and activation; finish the local screen within 900 seconds. The existing
full-logit ggml path remains the rollback. Only a reproducible connected local
advantage justifies an opt-in real-model integration; adoption still depends
on real 2B/0.8B output/state/serving and whole-request results, without a
fixed percentage floor. A local loss rejects this mapping, not producer-side
fusion in general.

Result: the captured 2B full and 257-row tail tokens, first-index tie and
nonfinite refusal passed. Five paired local wall medians for the three actual
activations were -0.011, -0.048 and +0.021 ms (ggml minus fused), with 2/5,
1/5 and 5/5 fused wins. Instrumented GPU intervals were also mixed. This
specific four-row mapping is withdrawn before real-model integration; the
complete local record is in `docs/qwen35-q6-fused-top-screen.md`. Continue
GPU work on a larger FFN or graph boundary. No fixed improvement floor was
applied.

### Metal graph barrier census (2026-09-27)

The same pinned Qwen3.5-2B model and 200-input/two-output request produced
613 identical major dispatch signatures in Align and llama.cpp, yet Align's
decode GPU interval was longer. Count Metal buffer barriers in the existing
independent dispatch trace, across the final complete decode graph in each
engine. This is an execution-order diagnostic, not a benchmark. Keep the
existing prompt, weight, ggml revision, and output verification; do not change
either inference graph or skip a barrier. Build only the diagnostic interposer,
run the existing attribution owner once, and finish within 600 seconds. A
barrier-count difference nominates a correctness-preserving scheduling probe;
equal counts redirect attention to placement, data layout or GPU work cost.
Either outcome is recorded without assigning shader time from the count.

The first census found 469 Align versus 393 pinned llama.cpp barriers in the
final decode graph, while the matching major dispatch census remains 613.
The pinned Metal range predicate treats `[p0,p1)` and an adjacent range
starting at `p1` as overlapping (`p1 >= other.p0`). A diagnostic patch may
change only that comparison to `p1 > other.p0`, retaining all genuinely
overlapping dependency barriers. Build a separate bundle with the same pinned
source, Metal flags and in-graph argmax patch, plus this one-line change; keep
the existing bundle as rollback. Cost ceiling: 900 seconds for build and local
checks, 900 seconds for real 2B output/state and five alternating worker pairs
at 200/32 and 330/64. Require unchanged exact output and state before retaining
the candidate; record barrier counts, prefill, decode, whole-request wall,
and adverse samples.
The comparison tests whether boundary false positives matter on this model,
without assuming a gain from the count difference or setting a percentage
floor. If useful, integrate as an explicit pinned Metal patch after verification.

The diagnostic bundle reduced the 2B decode barrier count from 469 to 399
without changing 663 dispatches. The real 200/3 request matched all 744,960
captured logits and 336 retained-state hashes exactly. A phase-instrumented
five-pair campaign improved request wall by paired medians 6.107, 14.614 and
17.971 ms at 64/16, 200/32 and 330/64, with 4/5, 5/5 and 5/5 wins. A separate
untraced campaign gave -2.114, +2.630 and +14.176 ms, with 2/5, 4/5 and 5/5
wins. Both retain adverse samples and pinned llama.cpp remains faster. These
results justify a reproducible opt-in build, not a default performance claim.

| Contract field | Opt-in adjacent-range bundle |
| --- | --- |
| Public developer surface | `gpu_backend_recipe.py --adjacent-ranges --base-bundle BASE/bundle` is false by default and valid only with `--backend metal` in a build invocation. It may combine with `--ingraph-argmax`; CUDA, `--print-plan`, a missing base bundle, or `--base-bundle` without `--adjacent-ranges` fail validation. No inference CLI or request format changes. |
| Build and owner | `scripts/gpu_backend_recipe.py` applies `scripts/metal-adjacent-ranges.patch` to the private pinned source after any independent Metal patches; the new flag digest enters `build_flags`, and the exact patch is retained next to the immutable bundle. The base bundle must match source, target, toolchain and all nontrial flags, and all five of its artifacts must match its manifest; its verified core dylib bytes are copied into the trial bundle. Only the Metal plugin changes, so the same Align binary can compare both bundles under its loaded-core identity check. The existing default bundle remains selectable. |
| Result, errors and cleanup | Successful build produces the existing schema-1 bundle/source snapshot with a distinct content identity. Missing/unapplicable patch or build failure aborts the private staging operation and leaves no published bundle. No new persistent schema, model cache or runtime allocation. |
| Validation order and prerequisites | Require Metal, a real build invocation and a base bundle, then the pinned clean ggml source and existing toolchain checks; apply the patch, build, verify the base manifest and all five artifacts, hash staged artifacts and publish atomically. The runtime continues to verify the selected bundle and loaded core libraries before session allocation. |
| Acceptance and metric | Recipe smoke, strict Python boundary, real 2B generation and full-logit/state equality; compare same-binary control/candidate bundles and pinned llama.cpp on 64/16, 200/32 and 330/64 with five alternating pairs. Report prefill, decode, request, startup and all reversals, without a percentage floor. CPU/CUDA porting is deferred because this patch is in the Metal scheduler; Gemma would reuse the patch only after its own model admission and correctness checks. |

Local closure: the formatted patch's final bundle passes 2B/0.8B generation,
744,960 exact 2B logits and 336 exact state hashes. Its Metal executable text,
embedded shader and four core libraries match the measured recipe bundle;
only embedded temporary source-path strings differ. Five final untraced
330/64 pairs give +12.966 ms median with four wins, a -134.671 ms reversal
and a +586.905 ms control outlier; shorter cases and startup are mixed.
Pinned llama.cpp remains faster in the stable comparisons. Retain the patch
as an opt-in build, not the default. The report and complete receipts are in
`../qwen35-metal-adjacent-range-trial.md` and `../../eval/benchmarks/`.

### Shared Metal row SIMD greedy trial (2026-09-27)

The previous borrowed-row path proves the real Qwen3.5 output is shared Metal
memory and removes an unnecessary full-row readback, but its scalar Align scan
did not yield a repeatable request gain. A bounded independent screen over
three actual 2B output rows found that an AArch64 NEON finite/argmax scan,
after an equivalent GPU blit and synchronization, saves about 0.25 ms per row
in 96–98 of 100 alternating pairs. The next candidate replaces only that
numeric scan. Align still selects the mode, validates model/session policy,
owns greedy generation, state and cleanup; the C shim contains a bounded
device-storage admission and SIMD numeric kernel. It does not add a second
inference engine or change F32 graph math.

| Contract | Definition |
| --- | --- |
| Input / selection | `ALIGN_LLM_NEON_GREEDY=0` or absent uses the existing copied output and Align greedy; `1` selects the experimental shared-row SIMD scan for the Qwen3.5 session. Invalid values refuse before weights are allocated. It cannot be combined with `ALIGN_LLM_SHARED_LOGITS=1`; both modes and rollback remain explicit. Normal and streaming generation use one Align-owned choice function. |
| ABI / admission | A new `ggml_ffi` thin call accepts the completed output slot and expected F32 row bytes. Reuse the existing checked shared-view admission: exact output node, contiguous one-row F32, shared `MTL` buffer, correct bounds and completed graph. The AArch64 NEON kernel reads the borrowed pointer immediately and returns only one index; no copied row, new Metal command buffer, temporary GPU buffer or wait. Unsupported architecture/storage refuses the opt-in request. |
| Numeric semantics | Before performance timing, actual 2B F32 rows and constructed first-index ties, NaN and infinities must agree with the unchanged Align finite greedy rule. For every finite row select the lowest index of its maximum. Return nonfinite as a distinct error; never silently choose a token. The graph, logits, recurrent/KV state and F32 operation order are unchanged. |
| Lifecycle / regression | No retained pointer or new per-owner allocation. Repeated normal and SSE requests, early disconnect, model close and invalid configuration must preserve cleanup. Confirm 2B/0.8B generation against pinned llama.cpp, exact 2B state-plane hashes, and default/shared-mode regression. |
| Measurement / ceiling | Same 2B GGUF, pack, IR, backend, prompt IDs, actual token counts and generation settings. Compare old Align, trial Align and pinned llama.cpp in at least five alternating worker pairs, and same-binary OFF/ON HTTP/SSE after two warmups at 64/16, 200/32 and 330/64. Also compare the scalar shared-row mode with SIMD locally to attribute the scan change. Record startup, prefill, decode, request and TTFT, including adverse pairs. One build <=900 s, campaign <=900 s, request <=180 s. No new device allocation, at most one 4-byte Align scratch instead of a full row, and no fixed percentage floor. |

Closure map before coding: Align config owns construction and malformed input;
`ggml_ffi`/shim own ABI validation and supported-host admission; the numeric
kernel owns finite/tie correctness; generation owns normal/SSE publication;
the existing session owner handles failure, early exit and cleanup. The old
copied path is the exact rollback. CPU/CUDA and Gemma remain separately admitted
by their semantic graph and storage contracts; a Qwen-specific model name must
not enter the kernel.

Trial closure: the opt-in NEON path passed 2B/0.8B generation, 2B HTTP/SSE,
336 exact state-plane hashes, malformed-mode refusal, odd-length local numeric
checks and zero full-logit `tensor_get` calls. The local real-row scan improved
by about 0.25 ms in 96–98/100 pairs. Connected worker, same-binary copied-path
HTTP/SSE and same-binary scalar-shared HTTP/SSE results were mixed: some
200/32 pairs improved, while 330/64 SSE regressed. Pinned llama.cpp stayed
faster on all worker request medians. Keep `ALIGN_LLM_NEON_GREEDY=0` by default
and retain `1` for bounded follow-up; do not claim production adoption or a
competitive win. See `docs/qwen35-neon-greedy-trial.md` and its complete raw
receipts. A larger output-projection consumer is the next hypothesis.

### Metal private-storage screening (2026-09-27)

Hypothesis: on the M1, private ggml Metal storage could lower warm decode GPU
time despite identical Q6_K projection dispatches. This is a reversible backend
allocation experiment using the pinned ggml `GGML_METAL_SHARED_BUFFERS_DISABLE`
switch, not a model or precision change. The independent measurement caller may
select it per explicit arm before device creation; the production default and
Align session contract do not change. Compare identical binary, pack, geometry,
bundle and request text with shared/private storage, preserve all output/count
checks and compare against pinned llama.cpp. Scope is one local Q6_K real-row
screen and up to three real-model workloads with five alternating pairs each;
each process has two warmup requests and the third is measured, with a 180-second
request timeout. The campaign budget is 900 seconds. Record startup, prefill,
decode, whole request and all negative samples. Private storage may add input
and output blits and memory pressure; a local projection win is insufficient for
adoption. No production mode is added unless connected correctness, memory and
request evidence justify it.

### Controlled upload and prefill trial (2026-09-26)

Hypotheses: synchronous tensor upload removes the Metal shared-buffer staging,
blit and per-chunk wait; larger prefill batches reduce graph boundaries. Measure
these independently before combining. Neither changes weights, tokenizer or math
semantics; batch reduction order may change rounding, so exact generation owners
and the existing 0.01 absolute logit bound remain required.

| Contract | Definition |
| --- | --- |
| Inputs / owner | `runtime_qwen35_execution.read` reads `ALIGN_LLM_SYNC_WEIGHT_UPLOAD` (`0` default, `1` opt-in) and `ALIGN_LLM_PREFILL_CHUNK` (`128` default, `256` or `512`) once per Qwen3.5 session before allocation. Other strings fail with `Error.Invalid`; no persisted format changes. |
| ABI | `align_gpu_weight_upload_mode(void *owner, int32_t mode)` accepts 0/1 after memory allocation and before weights begin, outside shape planning. Invalid owner/order/mode returns CONFIG without mutation. Align owns selection; real/stub shims own transfer mechanics. |
| Transfer / lifetime | Mode 1 calls synchronous `ggml_backend_tensor_set` directly on the borrowed chunk. The current Metal shared allocation copies directly; private backends use their synchronous implementation. No borrowed pointer survives return. Mode 0 retains staging + async set + wait. Select after one backend synchronization; all upload bounds, failure injection and counters stay. No mmap or ownership transfer. |
| Memory / ceiling | Existing staging remains allocated and budgeted. One scalar upload mode; one scalar session batch width; at most 512 input rows and the existing device/workspace budget. No additional retained weight copy. Each experiment at most 900 seconds; each request at most 180 seconds; five alternating pairs with all samples retained. |
| Batching / identity | Graph builders reference the shared attention maximum 512; the thin ABI validates the same bound. Actual count, geometry and graph kind already enter graph identity. Token/position/mask buffers match the selected session width. Decode and per-request reset remain unchanged. |
| Results / assessment | Report construction-to-ready, first request and warm request, prefill/decode and traced upload boundaries. OS cache is uncontrolled; do not call a first process disk-cold. Compare upload-only, batch-only and optional combined arms against old Align and pinned llama.cpp. Defaults remain legacy until evidence and review. |

| Closure | Implementation and acceptance |
| --- | --- |
| Configuration / malformed / no mutation | Execution parser and real/stub mode setters; focused C upload owner covers invalid modes, lifecycle order and independent owners; real session invalid-environment probes cover parser refusal. |
| Upload construction / success / failure | `ggml_ffi`, `runtime_weights`, generation prepare and both shims; `run-gpu-weight-upload-smoke` checks multi-chunk payload, bounds, transfer failure, unchanged staging in direct mode, legacy copy and counters. Existing device owner covers resource cleanup. |
| Batch construction / bounds / state | Generation and model/attention/recurrent/FFN builders; `run-gpu-attention-policy-smoke` tests 512 admission, 513 refusal and allocation faults; generation and HTTP/SSE owners on 2B/0.8B, plus repeated requests across a 512-token boundary. Invalid/early exits use existing Session resource cleanup; no new external allocation owner. |
| Real success / regression / cleanup | `run-qwen35-generation-smoke`, `run-openai-serving-smoke`, controlled measurement callers and existing logit oracle. Retained requests cover reset and recovery. No new schema, cache migration or process concurrency policy. |

Local closure: all named owners and paired campaigns completed; see
`../shared-upload-prefill-trial.md` and its raw receipt. Keep defaults unchanged:
startup improves, warm inference is inconclusive and memory accounting remains
a follow-up. A later same-binary 128/256 test on the copy-specialized 2B bundle
found input-dependent prefill changes without a reproduced uninstrumented
whole-request gain; see `../qwen35-prefill-counter-followup.md`. No universal
improvement floor is applied.

Author consistency pass: the synchronous setter borrows bytes only until return;
shared versus private memory is selected by the backend, never inferred from a
host pointer or model name. The batch cap controls admission and allocation alike.

Current measurement output changes (independent tooling, not runtime formats):
`measure-cuda-optimization` reports schema 3, `quality_passed`, `faster_pairs`,
`decision=ASSESSMENT_REQUIRED` and a regression warning; successful quality and
complete measurements may produce PASS without an adoption verdict.
`run-gpu-session-measurement` reports schema 3 and `decision=assessment_required` for complete
quality-valid pairs, preserving `invalid_quality` refusal. `run-prefix-ttft`
reports schema 2, a null `shipping_floor_ppm` and `ASSESSMENT_REQUIRED`, retaining its
separate jackknife uncertainty result. The resident decode owners retain latency
and correctness/resource checks but remove latency-floor failures. Old receipts
keep their original fields/verdicts. The focused aggregation owners are
`python3 scripts/measure-cuda-optimization --self-test-portable` (policy, aggregation
and parser fixtures on any host; the existing full `--self-test` retains live Linux
process/host owners) and
`python3 scripts/run-gpu-session-measurement-smoke`.


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
session/prefix reuse merely because historical delivery prose still says planned. Superseded as a
statement about the shipping tree on 2026-09-20 by §6.3 (measured closure `d4438e3`): that closure
clears the floor against the same-ggml reference on OLMoE `warm-long-changed` (+15.39%) and
`warm-long-cached` (+20.36%), 5/5, and remains 3–9% slower than the current llama.cpp reference.

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
| Evidence / acceptance | Require all four responses to pass the existing integer-sequence and 128-token quality checks before using the run to choose a follow-on. Profiler samples locate host stacks; they do not measure kernel duration or CUDA capture/replay. A new runtime/coding comparison uses its predeclared paired protocol and the current adoption assessment, without a percentage floor. |
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
| Shipping interpretation | Historical O1 receipt target: at least 15% median paired request-wall reduction and four of five pairs faster for a declared case, with every pair retained. This preserves the original `NOT_MET`/`MET` record, not a current admission rule. For any new integration or adoption, use the current inference optimization policy above: assess quality, paired variability, workload, regression, memory and maintenance without a fixed percentage or win-count floor. A competitive claim still needs a contemporary llama.cpp baseline and the relevant coding metric. |

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
| Interpretation | The completed capped-read campaign retained its historical 15% startup target and four-of-five count for its recorded verdict, with Qwen's historical 5% regression guardrail. Those are not current admission or shipping floors. A new decision uses the policy above and reports exact quality, startup and request distributions, regression and memory effects. This evidence does not claim a llama.cpp comparison, CUDA result, whole-session speedup or time-to-passing-patch improvement. |

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

Each campaign fixes its runtime metric (prefill, decode at a specified context,
or full fixed-output request) and aggregation before tuning. Adoption follows
the current policy above with no fixed percentage floor. Passing only prefill
does not claim faster decode; warm prefix reuse does not claim a faster uncached
kernel. G6 separately evaluates paired time to a passing patch without reducing
task success under the same caps. Its ledger fixes the multi-task corpus, repeated
paired schedule and uncertainty rule before measurement. Failed/timed-out attempts
remain in the outcome denominator. Runtime and coding outcomes cannot compensate
for one another or collapse into an ambiguous overall PASS.

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
| Metrics / decision | This frozen §6.1 campaign recorded every raw latency and count and the median paired percentage reduction `(reference-candidate)/reference` separately for each model, runtime case and reference. Its historical `met` verdict required all ten responses to pass quality, at least 15% median paired reduction, and four of five faster pairs. Preserve that verdict only as a past measurement; new experiments and adoption use the current policy above without a fixed improvement or win-count floor. Do not average across models/cases to hide a regression. Coding reports successes/attempts and paired times; this single-task campaign cannot establish broad coding competitiveness. |
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
| Cold / warm | Keep the §6.1 sequence; `cold-short` is the first request in a fresh ready service, with empty KV state. Its internal latency excludes model loading/startup. Record construction-to-ready wall time separately as operational context, never combine it into the internal request comparison. |
| Coding metric | Retain every attempt and actual native validation. Report success counts, attempts and `processing_to_passing_patch_ns`: sum of each attempt's internal generation time plus the existing native validator's measured wall time through the first passing patch. This includes validation process/filesystem work, excludes model transport, service startup and caller orchestration, and is not wall time to a passing patch. Failed portfolios keep null latency; no successful-only average hides failures. Use the native validator, whose known-good control must pass. |
| Decisions | This frozen §6.2 campaign reused §6.1's historical quality and 15%/four-of-five `met` classification in its receipt; that classification is preserved as historical evidence and is not a rule for new adoption. Current decisions follow the policy above, retaining all pairs and assessing variability and regressions. Runtime results are independent of coding success. Coding pair reductions exist only when both portfolios pass; report a median only when all five pairs exist. A measured negative or incomparable result completes this experiment; it does not qualify failed quality or claim G6 success. |
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
| Candidate / nomination | New driver constant `CUDA_CURRENT_CANDIDATE = d4438e313c59a71a11d0a65ed1735425a0e014e8`, selected through `NOMINATION[args.campaign]`. `CUDA_CANDIDATE` is not edited, and `688232c` ancestry is retained transitively because `d4438e3` descends from it. The nomination pins the `d4438e3` source closure, not a branch head: it admits a build whose `src/`, `.align-revision` and `scripts/ggml_shim.c` bytes equal `d4438e3`. The measured candidate was `83c53f0`, the pre-rebase commit of `agent/parity-minor-batch` that carried exactly that closure; it is unreachable from the merging head, and its closure is byte-equal to the reachable `d4438e3` and to `origin/main` `2cfbae0`, which is what keeps the receipt readable from this branch. This branch's later source commits are **not** covered by this campaign: `e3a86ee` (C1, `scripts/ggml_shim.c`) and `6704913` (C2, `src/decode_step.align`, `src/model_forward.align`, `src/moe_layer_forward.align`, `src/moe_model_forward.align`) both leave the `d4438e3` closure, so the driver refuses them and the recorded result says nothing about them. A further run against a later head is a new campaign needing its own nomination constant and its own paragraph here. Build it with `scripts/build-gpu-independent-candidate PINNED_GGML KIT_PROFILE OUT --session`; `verify_build` already refuses a dirty build. |
| Protocol / references / limits | Exactly §6.1 and §6.2: both retained unmodified `llama-server` baselines (same-ggml `bb4caa7540188872173c44d161602d9271386413` with F32 K/V, current `304665fe7ac957df95e3ff8c8c4ffdf92dd6ffa3` with F16 K/V), original Q4_K_M Qwen and OLMoE, the `cuda-kit-28a6fe3` profile's single resident/prefetch-off CUDA option, 1-GiB host and 6,000,000,000-byte GPU ceilings, context 2304, batch 2048, microbatch 128, four baseline CPU threads, Flash Attention on, no startup warmup or context shifting, the fixed system/short/long requests, 128 output tokens, the four ordered runtime cases, the eight-attempt native-validated coding portfolio, and five paired repetitions in the fixed rotated system order over 30 serial arms. |
| Runtime metric / decision | §6.2's request-level producer internal clocks remain: candidate worker `elapsed_ns`, baselines `timings.prompt_ms + timings.predicted_ms`. Missing or invalid clocks invalidate the campaign and never fall back to caller wall time. The frozen §6.3 receipt kept the historical 15%/four-of-five `met` classification with all ten responses passing quality; it remains historical only. Any new decision follows the current policy above without a fixed improvement threshold. Construction-to-ready wall time is operational context. Coding reports successes, attempts and `processing_to_passing_patch_ns`, with null latency for failed portfolios. |
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
rebase of this branch — or any later source commit that changes `src/`, `.align-revision` or
`scripts/ggml_shim.c`, such as C1 `e3a86ee` and C2 `6704913` — invalidates it and requires a new
nomination constant and a new paragraph before any further run.

Author consistency pass: §6.3 changes only the nominated candidate and adds a separate campaign
name; workload, baselines, bounds, sampler, clocks, quality rule and decision rule are byte-for-byte
the §6.1/§6.2 values implemented in the same code paths. `run-gpu-session-measurement-smoke` owns
the new campaign's predicate, nomination selection and non-CUDA admission refusal.

#### Result (2026-09-20)

The campaign ran on the RTX 4070 Ti under WSL2 with Align pin `8c8bfbc7`, candidate build
`source_commit` `83c53f0` (`source_dirty` false; the product tree equals `origin/main` `2cfbae0` and
the §6.3 nomination `d4438e3`), against the same-ggml `llama-server` `bb4caa75` (F32 KV) and current
`llama-server` `304665fe` (F16 KV) baselines, five paired repetitions, 30 arms, 348.7 s, status PASS,
decision "measured".

| Model | Case | vs same-ggml median (faster pairs) | vs current median (faster pairs) |
| --- | --- | --- | --- |
| qwen2 | cold-short | −3.53% (0/5) | −6.08% (0/5) |
| qwen2 | warm-short-cached | −1.06% (0/5) | −3.25% (0/5) |
| qwen2 | warm-long-changed | +0.93% (5/5) | −3.53% (0/5) |
| qwen2 | warm-long-cached | +2.55% (5/5) | −3.50% (0/5) |
| qwen2 | coding (time to passing patch) | −7.71% (0/5) | −7.73% (0/5) |
| olmoe | cold-short | −2.64% (2/5) | −8.20% (1/5) |
| olmoe | warm-short-cached | +6.02% (5/5) | −4.51% (1/5) |
| olmoe | warm-long-changed | +15.39% (5/5) | −8.80% (0/5) |
| olmoe | warm-long-cached | +20.36% (5/5) | −4.49% (0/5) |
| olmoe | coding | unavailable (OLMoE fails the coding task on all systems, as on 2026-09-09) |  |

Startup medians (service readiness): qwen2 candidate 1.808 s vs same 1.216 s vs current 1.116 s;
olmoe candidate 1.525 s vs same 0.912 s vs current 0.913 s (2026-09-09: olmoe 16,483 ms).

Interpretation: against the same-ggml revision, the resident OLMoE long-context rows clear the 15%
floor with 5/5 for the first time (+15.39%, +20.36%), which isolates align-llm's integration (F16 KV
retention, in-graph routing, graph reuse, capped-read loaders) against the same ggml revision (the
same-ggml baseline runs F32 K/V, the candidate F16 K/V); against the current llama.cpp reference
every row is still slower by 3–9%, so no competitive claim is made; Qwen
remains within a few percent of both baselines except the coding row (−7.7%), consistent with the
dense bandwidth roofline; the OLMoE startup gap of 2026-09-09 is closed to 0.6 s and the remaining gap
is loader and upload work; the coding-row gap is the next diagnostic target.

Receipt: `gpu-cuda-parity-20260920/p3-run1/campaign/result.json`, schema 2, in the local evidence
store outside Git. Per §6.3's host-quiet clause, the Claude Code CLI session was present as the only
background process during this run.

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
