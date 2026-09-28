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
- When a worker repeats requests and times the last one, slice every phase
  clock, completion wait and operation count to that same request. Check that
  phase clocks fit inside its wall interval. The schema-2 Qwen3.5 native phase
  reducer accidentally summed three requests of native waits; historical
  affected phase totals remain marked invalid, while the corrected schema-3
  caller and uninstrumented wall measurements are separate evidence.
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
- For asynchronous native commands, a failure marker at device completion can
  also be emitted during cleanup after an unrelated request error. A fault owner
  should prove that both the device injection and the request's explicit finish
  path ran, and require the expected worker envelope and controlled exit. The
  [state-copy failure trial](qwen35-native-state-copy-trial.md) found this false
  positive in its first owner version.
- A small strided state copy can be worth moving only when its graph and command
  boundaries are included in the trial. On the 2026-09-27 M1 Qwen3.5 run,
  Align kept the ggml state producer but replaced 18 convolution `CPY` nodes
  with one native Metal compute pass in the already required DeltaNet command.
  The real source had three F32 words per row and a 16-byte row stride;
  assigning one thread per row avoids repeated row division. The generic
  odd-width path remains. Exact logits/state and five alternating untraced
  pairs at three lengths showed a small repeatable request gain over the
  Delta-only route. This does not establish the row mapping's isolated gain;
  the connected change also removed graph nodes and changed scheduling.
  Pipeline compilation is additional setup and startup medians were slower;
  its isolated contribution remains unmeasured. This matters for short-lived
  sessions. See [the convolution-copy trial](qwen35-native-conv-copy-trial.md).
- The same copy operation can reverse sign when moved to a different execution
  boundary. On M1, adding 36 native state copies to each Qwen3.5 prefill graph
  shortened the synchronized producer graph/submission call but added a separate native
  command and a required completion wait before the next chunk. At 200/32 and
  330/64, the five-pair untraced request medians regressed against the already
  native decode route. A single real 199-token request measured 1.861 and
  0.900 ms of GPU work for its two prefill native commands, while host waits
  were 9.479 and 6.392 ms. These intervals are diagnostic, not additive savings
  or a universal Metal rule. Keep command submission, queue scheduling and
  dependency publication in the cost model; test a larger producer/consumer
  unit if an isolated replacement loses. See the
  [prefill state-copy trial](qwen35-native-prefill-copy-trial.md).
- Removing a large host readback can lose a useful overlap. On the 2026-09-28
  M1 Qwen3.5 decode, the existing CPU logit read/scan ran before the required
  native state-copy wait. Adding a two-dispatch finite argmax to that native
  command removed the 993,280-byte Align decode readback but made the token
  depend on command completion. Three alternating local command pairs measured
  about 0.019–0.027 ms more GPU command work and a larger host wait, while
  five-pair untraced request comparisons at three lengths showed no stable
  incremental gain. Treat overlap and publication dependency as measured parts
  of a fusion proposal; bytes removed alone do not predict speed. The borrowed
  Metal view also had to include ggml's page-rounded shared allocation after
  a real logit row landed in the logical workspace's last page. Check the
  producer allocator and exact reachable span when borrowing a buffer, and
  insert an explicit buffer barrier between dependent reduction dispatches.
  See the [copy-command greedy trial](qwen35-native-copy-greedy-trial.md).
- Fusing a producer with a large consumer can trade away parallelism even when
  it removes the intermediate vector. A local M1 Q4_0 FFN computed 64 gate/up
  rows per group, kept the gated tile in threadgroup memory and immediately
  multiplied all 2,048 down output rows. Real captured layers 3 and 23 passed
  the declared numerical bound, but the complete native two-dispatch operation
  lost every paired comparison in the final screen and its rerun against pinned
  ggml. Going from 256 to 512
  threads helped modestly; 1024 threads and two output partitions regressed.
  The extra work from recomputing gate/up tiles and the long down-row loop are
  concrete suspects, not isolated counter findings. Measure the whole fused
  operation and its work distribution before assuming saved intermediate bytes
  exceed lost parallelism. See the [tile-consumer screen](qwen35-native-q4-tile-ffn-screen.md).
- A split reduction axis must recover more GPU work than its partial writes,
  reduction dispatch and barrier add. On M1, actual Q4_0 FFN down projections
  from 2B layers 3 and 23 passed complete-output checks. Two/four-way split-K
  lost the direct unsplit GPU-interval comparison in 14/20 and 18/20 pairs,
  respectively, across two runs; wall results also favored unsplit. The
  independent unsplit arm beat isolated pinned ggml in 19/20 wall pairs, but
  that does not include a gate/up connection or model request. Test a complete
  native FFN command with this unsplit down mapping before changing the runtime.
  See the [down split screen](qwen35-q4-down-split-screen.md).
- Count host waits separately from Metal command boundaries. A complete
  independent Q4_0 gate/up/SiLU/down command beat isolated ggml on actual 2B
  FFN layers 3 and 23 in 20/20 paired local comparisons, by only
  0.057–0.068 ms at paired medians. Splitting the same native kernels into two
  commands and waiting after gate/up added 0.362–0.423 ms. Committing both to
  one tracked Metal queue and waiting only after down passed every output
  check and added 0.030–0.059 ms at paired medians. Thus a per-FFN host wait
  can overwhelm a real kernel win, while ordered queued submission preserves
  the dependency with much lower wall cost. The queued cost is still the same
  order as the gain, and the current ggml graph API was not tested with this
  schedule. See the [complete FFN capture screen](qwen35-q4-full-ffn-capture-screen.md).

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

A fresh [mixed native-copy profile](qwen35-current-native-mixed-bottleneck.md)
on the same M1 checked the real 2B route after removing the 36 decode state
copies. Over three 200/32 requests, Q4_0 and Q6_K matrix-vector work was
59.2% of sampled shader intervals; Q4_0 prefill matrix-matrix was 26.1%, and
F32 copies 0.7%. Matvec Buffer Read Limiter medians were 100.0% and 99.8%,
with 52.1 and 56.5 GB/s GPU read samples. The different prefill signature
remained: Q4_0 matrix-matrix had 83.1% median F32 utilization. This narrows
the next connected hypothesis to weight traffic, reuse and execution
boundaries on this workload; it does not impose an M-series or independent
backend ceiling.
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

The [connected final-layer FFN screen](qwen35-native-final-ffn-connected-screen.md)
put the locally faster independent Q4_0 FFN into real 2B decode requests.
The graph allocator reused the F32 FFN input allocation for the ggml gated
output; an in-place native fusion corrupted it, so the connected kernel needed
24 KiB of separate gated scratch. A second cached Metal view of the ggml
workspace also produced stale values on later decodes in this setup; fresh
views or direct borrowing of the original pinned Metal buffer restored local
numeric agreement. This is a concrete alias/visibility trap when crossing
independently managed Metal resources, not evidence that shared physical
memory removes ownership and ordering work. Direct borrowing cut the
fresh-view campaign's request loss, and GPU events removed intermediate CPU
waits, but the final-layer-only candidate lost at all three conditions in a
campaign that verified each request's native substitution count. The isolated
0.057–0.068 ms FFN win was too
small for this boundary. A larger native unit needs owned buffer lifetimes
and explicit GPU dependencies; a pinned ggml internal buffer/event ABI is
useful for a reversible diagnostic bridge, not a portable engine contract.

The [target-batch feasibility screen](qwen35-target-batch-feasibility.md)
shows a different mechanism from a faster single-token kernel. On the M1
2B worker, lengthening related prompts by 4/8/16 tokens cost
only 2.562/2.400/6.684 ms at paired medians when the graph emitted only its
last logit row; generating those tokens serially cost
121.676/230.490/438.319 ms. The longer prompts share only 191 initial token
IDs with the base, so these figures compare processing shapes and do not bound
an exact target continuation. The existing Q6_K output head also computed
4/8/16 captured activation rows together in 10.722/20.974/18.980 ms,
versus 29.098/58.376/117.108 ms serially, with complete numerical and
greedy checks. Thus weight reuse across token columns is real for the head
and plausibly valuable for the full graph. The prefill screen omits the
other target logit rows, and neither screen includes draft cost or safe
DeltaNet/KV state acceptance. Keep these as feasibility evidence until a
multi-row target graph and transactional state prove an actual request win.

The subsequent [complete four-row graph screen](qwen35-target-all-rows-screen.md)
confirmed the weight-reuse mechanism in an Align-built full-model graph, not
just the Q6_K head. On one M1 with real 2B weights, synchronized compute took
44.414 ms versus 115.456 ms for four serial steps, with all five paired
comparisons favoring the four-row graph. It paid 1,987,456 more workspace
bytes and about 0.251 ms more logits readback. Complete logits and valid
active state met separately declared numerical bounds; whole-plane state
hashes are misleading when active recurrent parity differs and unused KV
tails are included. Compare the state that the next token actually reads.
This empty-prefix graph result still excludes a draft, partial acceptance,
rejection replay and whole-request time; those decide whether weight reuse
can become a generation speedup.

The [exact-prefix continuation screen](qwen35-target-continuation-screen.md)
then ran the same four oracle tokens after an identical 200-token prompt
state. Five alternating M1 pairs gave a 63.126 ms median connected target
advantage after charging the current 2.920 ms graph rebuild and four-row
readback; all five pairs favored the batch. Complete logits and valid active
KV/recurrent state met their predeclared numerical bounds. The mechanism is
weight reuse across token columns, with enough saved graph work to pay the
current context switch. The serial diagnostic retains both decode parity
graphs, so process wall and workspace are not a product comparison. Acceptance
rollback, draft cost and complete-request results still decide adoption.

The [acceptance-state screen](qwen35-target-acceptance-screen.md) measured the
missing rejection cost. With a real 200-token Qwen3.5-2B state on M1, four
accepted candidates saved 62.325 ms at the paired median over equal serial
progress. First rejection after 0, 1, 2 or 3 matches lost 55.630, 55.299,
53.667 or 56.229 ms respectively, each in all five pairs. Partial replay
needed about one 29 ms decode per accepted token; valid KV/recurrent state
and one subsequent complete row agreed with serial. This makes candidate
quality and full-group acceptance a first-order GPU performance input. Measure
a real cheap draft and consider shorter/adaptive groups before product
integration; no local four-row speed result can stand in for accepted-token
throughput.

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
