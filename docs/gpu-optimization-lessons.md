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
The complete evidence and opt-in decision are in
[`qwen35-metal-linear-copy-trial.md`](qwen35-metal-linear-copy-trial.md).

The next copy question is whether the remaining strided convolution path or
DeltaNet producer-to-resident boundary can be improved while preserving
success-only publication. A layout-only reorder and a singleton-dispatch
deletion have already failed connected benchmarks, so repeat them only with
a new mechanism and measurable prediction.

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
