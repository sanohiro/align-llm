# GPU inference optimization notes

These notes collect observations that can be reused across model and backend
work. A local kernel result is a hypothesis for a connected trial, not a request
speed result. Historical measurements remain in their owning reports.

## Workload and measurement

- Separate construction/load, prefill, decode, and the complete request. Prefill
  can reuse a weight tile across tokens; single-sequence decode generally cannot.
  Changing prompt length or output length changes the useful optimization target.
- Compare the same GGUF, prompt token IDs, generated token count, cache condition,
  and actual execution flags. Keep the unchanged Align binary and pinned
  llama.cpp as distinct controls. Alternate arms after warmup and retain every
  adverse pair. A percentage threshold is not an adoption rule.
- A CPU timestamp around asynchronous dispatch measures submission, not GPU
  completion. A synchronized graph timer includes scheduling and waiting. A
  shader interval or counter sample identifies an attribution candidate but is
  not the marginal time saved by deleting that shader. Measure the connected
  request after each intervention.
- On this Apple M1, `xctrace record --template 'Metal System Trace'
  --instrument 'Metal GPU Counters'` enabled Shader Timeline where Metal System
  Trace alone did not. Check the trace TOC and target PID before interpreting
  exported intervals. The available counters and sample boundaries depend on
  the device and instrument version. Apple describes the supported workflow in
  [Metal tools](https://developer.apple.com/metal/tools/) and
  [Xcode GPU performance analysis](https://developer.apple.com/documentation/xcode/analyzing-the-performance-of-your-metal-app/).

## Follow bytes and dependencies

- Count weight bytes, state bytes, temporary bytes, device dispatches, command
  buffers, barriers and host readbacks before tuning arithmetic. Inspect each
  kernel's grid and adjacent-lane addresses, then check register use, occupancy,
  and bandwidth where counters exist. A shader with low bandwidth can be
  limited by dependency, access pattern, or insufficient parallel work.
- Apple Silicon shared buffers can remove an explicit CPU/GPU copy, but they do
  not remove synchronization or bandwidth cost. In the 2026-09-27 Qwen3.5-2B
  binding census, both Align and llama.cpp state-copy buffers reported Metal
  `storageMode=0` (shared). Their state placement and workspace sizes differed.
  A claim that one path uses private memory or copies across CPU/GPU would need
  separate evidence. Buffer length and offset alone do not establish latency.
- Moving a value into threadgroup memory pays a copy and synchronization cost.
  Apply tiling when reuse exceeds that cost. Fusion removes intermediate traffic
  and dispatch boundaries only within a safe resource budget; large per-thread
  accumulators can spill or reduce occupancy. Specialize on operation semantics,
  shape, type, layout, token count, and device properties rather than a model
  name. Preserve architecture-specific activation, normalization, attention and
  position semantics in the model definition.
- An independent copy or readback optimization needs an end-to-end test. The
  Qwen3.5 shared-logits trial eliminated a real readback copy but did not show a
  repeatable request gain. A later 2B singleton K/V materialization trial
  removed 12 decode dispatches and likewise showed no request gain. These
  negative results narrow those particular boundaries; they do not rule out a
  larger fused graph or a different buffer layout.

## Current Qwen3.5-2B evidence and next test

For two identical Align 200-input/32-output requests, a counter-enabled Metal
trace sampled 9,364 worker shader intervals, including 198.177 ms of
`kernel_cpy_f32_f32` (99.1 ms/request). The matching unchanged-bundle control
sampled 200.573 ms over two requests. A three-iteration pinned llama.cpp trace
sampled 105.947 ms of the same-named copy shader (35.3 ms/request). Align and
llama.cpp Q4_0 and Q6_K matrix-vector samples were close per request: about
384/246 ms versus 387/245 ms respectively. These are instrumented attributions
with different total sample counts, not precise dispatch clocks or a predicted
64 ms improvement. The preceding untraced five-pair result is in
[`qwen35-metal-adjacent-range-trial.md`](qwen35-metal-adjacent-range-trial.md).

The final decode graph contains 18 convolution and 18 DeltaNet state-copy
dispatches in each implementation. Align's observed state destination is one
68,714,496-byte shared buffer with two parity planes; the reference used one
20,201,472-byte shared buffer. The destination role follows the observed Metal
buffer binding and graph copy operation. The parity-major allocation trial in
[`gpu-runtime-performance.md`](specs/gpu-runtime-performance.md) halved the
distance between first and last destination starts from 38,305,792 to
19,152,896 bytes, matching the reference span. The untraced 200/32 and 330/64
paired request medians nevertheless regressed by 3.195 and 18.414 ms. The
source change was withdrawn. This rejects placement as the sole explanation on
this host. The next test inspected the copy's indexing before another
arithmetic-only matvec experiment. Removing
the second parity plane would need a separate failure and ownership contract:
Align currently publishes state only after graph success.

The actual graph showed 18 contiguous 1 MiB DeltaNet F32 copies and 18
smaller convolution copies with strided sources. A Metal specialization that
replaced multidimensional destination division with linear indexing only for
large contiguous F32 source/destination pairs left the strided path intact.
Three full 2B logits rows and 336 resident-state hashes were exact; both 2B
and 0.8B generation owners passed. Two independent measured-recipe/discovery 2B
five-pair campaigns each won all three tested input/output lengths against
the unchanged Align bundle, and the measured recipe bundle beat pinned llama.cpp at
each request arm median. The 0.8B campaign won 14/15 control pairs and retained
one short-case regression. The counter-enabled F32 copy sample total fell from
199.922 to 11.228 ms over two identical 200/32 requests, while the real
untraced request gains were smaller. This is a reusable lesson: inspect the
compiled generic kernel's **address arithmetic** and its actual layout
predicate before assuming that memory bandwidth or buffer sharing is the
whole bottleneck. Trace interval reductions are not a request speed estimate.
The copy identity follows from the F32 type, contiguous strides and element
count; no M1 name or unified-memory capacity enters the kernel predicate.
This makes the address simplification a portable Metal hypothesis, not a
portable speed result. The 262,144-element threshold, compiler lowering,
cache behavior and relative arithmetic/memory cost can change the benefit on
another GPU generation or workload. The other generic copy and conversion
kernels contain similar coordinate divisions, but they also do other work;
profile their real connected cost before specializing them. The complete
evidence and tested-host recommendation are in
[`qwen35-metal-linear-copy-trial.md`](qwen35-metal-linear-copy-trial.md).

The current 262,144-element cutoff equals the observed 1 MiB F32 DeltaNet
copy. It is a scope guard for that measured workload, not a measured
break-even size: the retained trials do not sweep smaller contiguous lengths.
For a new host or a broader specialization, first model the same-byte,
same-dispatch choice as saved address work versus fixed path/selection cost;
then measure paired GPU command and complete-request times over actual
contiguous sizes on both sides of the proposed cutoff. Memory-bound and
launch-bound cases can hide an instruction saving, so no universal element
count follows from the model alone.

### Independent shared-buffer command boundary (2026-09-27)

The independent Metal state-copy trial reused the same shape/layout lesson
without a ggml source patch. Align registered the 18 actual contiguous F32
DeltaNet copies, borrowed their existing shared buffers, and let one native
command publish the next resident state after the ggml producer completed.
The first correct version waited immediately after native submission and lost
all 15 unchanged-Align warm-request pairs. Its instrumented 18-copy command
spent about 0.655 ms on the GPU but 5.498 ms in the immediate wait per decode
step (medians of one 16-token request). A revised version cached the borrowed
views, encoded one blit batch, removed a redundant ggml synchronize and waited
after the independent CPU logits read/sampling work, before parity publication.
Its corresponding final wait was about 0.658 ms. The initial async build won
all 15 warm-request pairs; a subsequent build with a cleaner mode-`0` control
won 14/15 against both unchanged Align and pinned llama.cpp, retaining one
adverse 200/32 pair. The reviewed binary, which also rejects ambiguous Metal
device identity, won 15/15 in a new same-binary campaign on this M1. All three
lengths retained positive paired medians in both later campaigns.
The [native-state report](qwen35-native-state-copy-trial.md) retains the exact
condition-by-condition and adverse results. These four changes were applied
together, so their separate speed contributions remain unmeasured.

The transferable rule is to model the **dependency boundary** as well as the
bytes and shader interval. Shared CPU/GPU memory made zero-copy buffer views
possible, but did not remove command submission or ordering. Independent work
can run while a native command is pending only when the data dependency permits
it; the state publication still waits. The native queue boundary remains a
candidate for removal by owning a larger decode segment. Another GPU, copy
layout or model must remeasure the command scheduling and request result.

### Counter diagnosis after the copy trial (2026-09-27)

The same counter-enabled 200/32 traces also contain raw `gpu-counter-value`
samples. Overlaying their timestamps on single-worker Shader Timeline intervals
gives the following medians. Align's trial trace contains two requests and the
pinned llama.cpp trace contains three. The table reports counter samples, not
independent request repetitions or exact per-dispatch statistics.

| Shader | Arm | Samples | Buffer Read Limiter | GPU read GB/s | F32 utilization | Compute occupancy |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Q4_0 matrix-vector | Align | 17,288 | 100.0% | 49.2 | 10.4% | 20.4% |
| Q4_0 matrix-vector | llama.cpp | 25,626 | 100.0% | 50.1 | 10.6% | 20.4% |
| Q6_K matrix-vector | Align | 12,942 | 98.1% | 52.5 | 6.7% | 32.7% |
| Q6_K matrix-vector | llama.cpp | 18,317 | 99.1% | 55.7 | 7.2% | 32.7% |
| Q4_0 matrix-matrix | Align | 12,734 | 28.0% | 27.2 | 83.1% | 27.1% |
| Q4_0 matrix-matrix | llama.cpp | 19,832 | 34.2% | 54.4 | 82.3% | 27.0% |

Counter IDs and descriptions were checked against each trace's
`gpu-counter-info`. Samples at either shader edge (10 microseconds) and samples
overlapping another worker shader were excluded. The source trace, exports,
local extraction script and compact summaries are retained under the resolved
Git common directory at
`diagnostics/q35-ingraph-greedy-2026-09-27/counter-trace-20260927/`.
Raw `gpu-counter-value` XML can be regenerated with `xctrace export` from the
retained `.trace`; it is not a checked-in benchmark artifact.

These are whole-GPU time samples associated with a worker interval. Background
GPU work, sampling overhead and overlapping commands limit attribution. The
reference uses a different prefill microbatch, so its Q4_0 matrix-matrix read
bandwidth is not a controlled kernel-efficiency comparison. Apple's
[counter guidance](https://developer.apple.com/documentation/xcode/analyzing-apple-gpu-performance-using-a-visual-timeline)
distinguishes limiter, utilization and bandwidth, and its
[occupancy guidance](https://developer.apple.com/documentation/xcode/finding-your-metal-apps-gpu-occupancy)
warns that low occupancy alone does not establish a bottleneck.

Q4_0 and Q6_K decode matrix-vector work is strongly associated with buffer
read pressure in *both* implementations. The trial's Q4_0 plus Q6_K
matrix-vector Shader Timeline totals are about 651 ms per request, 61% of its
worker shader sample total; the remaining F32 copy is about 5.6 ms per request.
This points away from repeating the prior arithmetic-only native Q4_0 kernel
or Q6_K one-to-one rewrite without a new way to reduce weight traffic or improve
useful bytes per read. Q4_0 prefill matrix-matrix has a different signature:
high F32 use and substantially lower read limiter. Its token-tile shape is a
separate experiment; the earlier 128-to-512 chunk trial had mixed connected
results and must not be generalized from these counters.

A same-binary follow-up on the copy-specialized bundle compared prefill width
128 with 256. It reduced prefill graph count for 200 and 330 input tokens.
Synchronized prefill regressed in all five 200-token pairs and improved in all
five 330-token pairs, but a separate uninstrumented whole-request campaign
did not reproduce the 330-token lead. The no-op 64-token control also moved.
The existing 64-by-32-token ggml matrix tile already reuses each dequantized
weight tile across token columns; a wider session chunk alone is not evidence
of another reuse opportunity. The 2B listed weight extent divided by observed
one-token decode graph time is about 48 GB/s, close to the sampled Q4_0/Q6_K
read bandwidth. This is a consistency check, not measured physical traffic or
a lower bound. Full conditions and adverse pairs are in
[`qwen35-prefill-counter-followup.md`](qwen35-prefill-counter-followup.md).

The actual-weight Q4_0 layout screen has now run. Splitting unchanged Q4_0
scale and packed values into two resident streams kept byte extent and output
exact, but its 24-layer rotating-weight GPU intervals had only a +0.007 ms
median with 3/5 wins over the original layout. Two- and eight-row SIMD group
mappings lost to the pinned four-row mapping in GPU intervals. An initial
same-buffer A/B was invalid: the second shader arm benefited from cache
ordering. Separate byte-identical Metal buffers and rotation through 169.9 MB
of real gate weights were needed before comparing row mappings. See
[`qwen35-q4-layout-screen.md`](qwen35-q4-layout-screen.md).

The contiguous-copy specialization also completed six view geometries and a
five-pair process-footprint screen without a resolved memory difference. A
separate direct comparison against the pre-adjacent Metal bundle won every
2B and 0.8B request pair at 64/16, 200/32 and 330/64. The pinned llama.cpp
comparison won 29/30 across both models; the 0.8B long case retained one
-15.966 ms pair. That matters because the adjacent-range control itself was an
experiment, not the ordinary bundle. The explicit faster profile is
recommended for the measured M1 Qwen3.5 workload; total GPU/system memory and
other hosts remain unmeasured. The remaining strided convolution copies total only
1,327,104 bytes per decode token, compared with 18,874,368 contiguous DeltaNet
copy bytes already specialized. A layout-only reorder and a singleton-dispatch
deletion have already failed connected benchmarks, so repeat them only with a
new mechanism and measurable prediction.

A later actual-weight Q6_K output-head screen assigned four rather than two
output rows per SIMD group. Full and tail logits were exact for three captured
activations, but paired projection wall times changed by +0.003, -0.021 and
-0.050 ms (ggml minus four-row median), with only 3/5, 2/5 and 2/5 wins. A
checked read-only pass over the same 417 MB yielded 53.77 GB/s of listed bytes
per GPU command interval and took longer than the projection. This is not a
physical-bandwidth bound: its checksum/grid do different work. It makes a
simple row-count change or contiguous reread an unconvincing next step. Q4_0
has more aggregate decode time and its pinned kernel already reads adjacent
blocks across lanes with four rows per SIMD group. A useful next experiment
must name a different byte/layout/dependency mechanism and include conversion
and resident-memory costs. See [`qwen35-q6-four-row-screen.md`](qwen35-q6-four-row-screen.md).

For a larger change in work per weight read, [speculative
decoding](https://proceedings.mlr.press/v202/leviathan23a.html) verifies several
drafted tokens in one target pass and can preserve the target distribution.
This is a hypothesis for batched weight reuse, not a measured 2B speedup.
Qwen3.5's gated DeltaNet state makes acceptance-prefix publication and rollback
part of correctness; a simple KV-length rewind is insufficient. The
[TreeWY paper](https://arxiv.org/abs/2608.20961) addresses gated-DeltaNet
speculative state handling at larger model scales, but does not establish that
its costs work for this M1 2B workload. Any Align experiment needs an explicit
state transaction, exact output/state owner, draft acceptance measurements and
the combined target/draft memory and time budget before runtime admission.

The earlier projection-pruning diagnostic changed output and is useful only as
cost attribution. Its 3.7–8.0 ms graph differences cannot be adopted as an
inference optimization. See
[`qwen35-decode-attribution.md`](qwen35-decode-attribution.md).

## Decision pattern

1. State a mechanism in bytes, work, or synchronization and define a reversible
   control with a connected cost ceiling.
2. Use local actual-weight and actual-activation checks, then real model logits,
   state and repeated generation. Keep strict-compatible and rounding-changing
   paths distinct.
3. Measure local kernel, connected graph and whole request separately, with
   prefill/decode/load split. Inspect regressions, memory, variance and
   maintenance cost before adoption.
4. Record rejected hypotheses and the next discriminating observation. A local
   loss or win is evidence about that boundary, not a universal backend verdict.
