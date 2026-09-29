# Native CUDA optimization log

This log records reproducible CUDA trials, including losses. The current host is
an NVIDIA GeForce RTX 4070 Ti (sm_89) with CUDA 13.3. The control is the
unchanged CUDA plugin built from pinned llama.cpp `bb4caa7540188872173c44d161602d9271386413`.
The real Qwen3.5-2B Q4_0 artifact used for session work has SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
The isolated FFN screen below instead uses deterministic synthetic Q4_0
weights and one F32 input; its results are **not** a request-speed claim.

## Sources and measurement method

- NVIDIA's [CUDA Graphs guide](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html)
  explains the repeated-launch cost that motivates capturing the four-operation
  native FFN. Both the ggml and native arms in this screen use captured graphs.
- The [Nsight Systems user guide](https://docs.nvidia.com/nsight-systems/UserGuide/)
  documents CUDA graph tracing and `cuda_gpu_kern_sum`. Use
  `--cuda-graph-trace=node` when attributing individual captured kernels;
  graph-level tracing otherwise omits their repeated instances.
- NVIDIA's [integer intrinsic reference](https://docs.nvidia.com/cuda/cuda-math-api/cuda_math_api/group__CUDA__MATH__INTRINSIC__INT.html)
  defines signed four-byte `__dp4a`, used to accelerate the Q4_0 × Q8_1 dot.
- The pinned llama.cpp `ggml/src/ggml-cuda/mmvq.cu` and
  `ggml/src/ggml-cuda/vecdotq.cuh` are the local implementation references.
  Its Q4_0 decode uses quantized Q8_1 input, gate/up fusion and architecture/shape
  dependent warp counts. The screen matches the input quantization and fusion
  semantics while keeping its own kernels and memory ownership.

The screen command is:

```sh
scripts/run-native-cuda-q4-ffn-screen GGML_SOURCE GGML_LIB GGML_CUDA_PLUGIN
```

Here the three arguments are the same-source llama.cpp checkout, its manifested
backend library directory and that directory's CUDA plugin. The 2048 × 6144
gate/up, 6144 × 2048 down, F32 row and Q4_0 formats represent the 2B decode
FFN shape. The owner compares all 6,144 gated and 2,048 final values, warms both
arms 12 times, then alternates five pairs of 20 synchronized complete FFNs.
The screen does not read model weights or include model graph, scheduling,
tokenization, transfer, startup or request overhead.

## 2026-09-29: Q4_0 FFN, scalar dot and DP4A

| Candidate | Numeric check | Median GPU kernel time from 112 captured instances | Five-pair host observation | Decision |
| --- | --- | --- | --- | --- |
| Four rows/block, scalar 32-element dot | Complete gated/down rows bit-identical to pinned ggml for the synthetic input | gate/up 17.057 µs; down 13.504 µs | ggml 0.063182 ms, native 0.082228 ms median per complete FFN | Lost locally; replace dot, not adopt. |
| Four rows/block, `__dp4a` dot | Complete rows bit-identical | gate/up 11.488 µs; down 8.128 µs | ggml 0.046977 ms, native 0.050682 ms | Dot optimization helped, but still lost the five-pair run. |
| Two rows/block, two warps/row, `__dp4a` | Gated maximum absolute difference 1.49e-8; down exact | gate/up 11.424 µs; down 7.936 µs | ggml 0.046471 ms, native 0.047804 ms | Retain as the best current local implementation; no product adoption. |
| One row/block, four warps/row, `__dp4a` | Same numeric check | gate/up 13.089 µs; down 7.648 µs | ggml 0.057145 ms, native 0.060369 ms in instrumented run | Down improved slightly, gate/up regressed; withdrawn. |

The command for kernel attribution is:

```sh
nsys profile --trace=cuda --cuda-graph-trace=node --sample=none --cpuctxsw=none -o REPORT scripts/run-native-cuda-q4-ffn-screen GGML_SOURCE GGML_LIB GGML_CUDA_PLUGIN
nsys stats --report cuda_gpu_kern_sum --format csv REPORT.nsys-rep
```

The native two-warp gate/up median approximately matches pinned ggml's 11.232
µs, but native down remains slower than ggml's 5.921 µs. The quantization
passes are each about 1 µs. Host complete-operation values fluctuate with GPU
clocks and system load; use the paired samples and separate instrumented kernel
attribution, not a single minimum. Captured graphs remove repeated host launch
setup but do not make an individually slower kernel faster. The standalone
result provides no evidence that replacing one FFN inside a full Qwen3.5 graph
will improve a request. A connected trial needs exact real weights and state,
plus a scheduling boundary that avoids an extra whole-graph synchronization.
A final owner rerun after the CUDA session work passed the same numeric checks
and lost all five complete-FFN local pairs (ggml/native medians 0.045148/
0.046924 ms), consistent with the earlier decision.

## Real Qwen3.5 CUDA admission and copy cycle (2026-09-29)

The unchanged ggml CUDA graph initially failed to build F16 attention-cache
prefill because its in-place F32-to-F16 `SET` is unsupported on this backend.
The existing indexed K/V write ABI accepts the same bounded absolute positions,
so CUDA prefill now uses it for both K and V. The existing Metal path retains
its `SET`. On the authenticated 2B artifact, the ordinary and native-copy CUDA
paths passed 31-, 200-, and 330-token prompts with three greedy outputs, plus
six retained requests including malformed and early-exit cases. The existing
Align `runtime_qwen35_lookup_trial_smoke` normal arm additionally returned
exact generated IDs for three repeated requests at each length; all matched
the pinned greedy oracle in modes `0` and `1`. The retained provider owner
also compared rendered output, and the HTTP/SSE serving owner passed both
modes, including invalid requests, disconnect, recovery and restart.
For mode `0` versus mode `1`, a separate real-model trace compared three
complete 248,320-value logit hashes and all 252 valid state-plane hashes per
case exactly. Each decode graph removed 18 ggml `CPY` nodes. Direct device
copy, bounds, overlap and pending-work owners passed, and forced submit and
completion failures returned errors without publishing output.

The first native helper submitted 18 `cudaMemcpyAsync` operations on its own
stream per decode step. Two five-pair warm-request campaigns did not establish
a gain over ordinary Align: the first had native wins in 2/5 pairs at each
56/16, 200/32 and 330/64 condition, with paired median gains of -1.197,
-6.389 and -5.798 ms. A CUDA node trace at 200/32 counted 2,186 async copies
and 1,622 stream synchronizations in the native path; the ordinary path had
1,718 async copies and 1,582 synchronizations. Instrumented device-to-device
copy time rose from 3.464 to 4.601 ms. The trace does not isolate host wait
cost or predict uninstrumented request latency.

The second helper batches the 18 aligned large state planes into one independent
`uint4` CUDA kernel launch; small or unaligned copies retain the checked async
copy fallback. The same 200/32 node trace counted 31 batch kernel instances,
median 43.394 µs each, and 1,628 async copies (558 fewer than the first native
version). Instrumented device-to-device copy time fell to 2.665 ms, while
stream synchronizations remained 1,622. In the ordinary Align 200/32 kernel
timeline, fused and unfused Q4_0 matvec accounted for 29.5% and 13.4% of GPU
kernel time, while the Q6_K output projection accounted for 22.9%; the same
three groups accounted for 29.9%, 12.1% and 22.4% in the batched-copy run.
The new copy kernel itself accounted for 1.0%. These are whole-request,
instrumented kernel-time shares, not request-latency savings or isolated decode
fractions. The first five-pair uninstrumented
Align A/B run favored batching at all three paired medians (+0.819, +3.572,
+2.562 ms; native wins 5/5, 5/5, 4/5); its repeat reversed the first two
medians (-1.184, -1.762, +10.498 ms; 2/5, 2/5, 4/5). This is a useful
copy-launch reduction but not a repeatable whole-request gain.

Two further campaigns alternated the ordinary and batched native Align
sessions with the same-source llama.cpp CUDA reference. Both Align sessions
stayed resident; each llama.cpp sample was the third iteration in a separate
reference process. Every arm used the same model, prompt IDs and requested
output count; both Align outputs and the rendered pinned-reference output
matched in each pair. The timing interval is one warm retained request for
Align and one warmed eval for llama.cpp, excluding startup and model load.
Campaigns 1 and 2 predate an explicit reference-executable digest in the
receipt. Campaign 3 verified the benchmark executable SHA-256
`0aabc02758cf34b086d253d6b164cb6027a2aa2188b17fd66c42f483e608ae29`
before loading the model and verified the pinned source commit above. Its
linked same-source `libllama.so` had SHA-256
`9bcc0ecb30914d0d4cf297044ec561367cae55d37a4734683533e16d8f3ceb22`.
The result is specific to this host, model and these three workloads:

| Campaign | Prompt/output tokens | Native minus ordinary: paired median gain, wins | Native minus llama.cpp: paired median gain, wins |
| --- | --- | --- | --- |
| 1 | 56/16 | -0.342 ms, 2/5 | +13.512 ms, 5/5 |
| 1 | 200/32 | -0.721 ms, 2/5 | +9.663 ms, 4/5 |
| 1 | 330/64 | -3.635 ms, 2/5 | +14.565 ms, 5/5 |
| 2 | 56/16 | -0.507 ms, 2/5 | +15.194 ms, 5/5 |
| 2 | 200/32 | -1.315 ms, 2/5 | +7.429 ms, 5/5 |
| 2 | 330/64 | -1.562 ms, 2/5 | +16.165 ms, 4/5 |
| 3, digest-bound | 56/16 | -0.443 ms, 2/5 | +14.514 ms, 5/5 |
| 3, digest-bound | 200/32 | -2.704 ms, 0/5 | +2.709 ms, 3/5 |
| 3, digest-bound | 330/64 | +0.118 ms, 3/5 | +14.903 ms, 5/5 |

Thus the digest-bound campaign won 13/15 paired samples against the specified
pinned llama.cpp executable but only 5/15 against ordinary Align. The two
earlier preliminary campaigns had 28/30 and 12/30 respectively. Ordinary Align
is already competitive on these cases; the independent copy has no reliable
incremental advantage. Keep `ALIGN_LLM_NATIVE_STATE_COPY=0` as default and
`1` as an explicitly selected experiment. Do not infer a general llama.cpp
victory, a startup gain, or a copy-kernel gain outside these conditions. The
raw local receipts are `native-copy-measure.stdout`,
`native-copy-kernel-measure.stdout`, `native-copy-kernel-repeat.stdout`,
`native-copy-vs-llama.stdout`, `native-copy-vs-llama-repeat.stdout`,
`native-copy-vs-llama-identity.stdout` and the
corresponding Nsight reports under the disposable measurement directory;
they are not committed because they include host-specific artifacts.

Reproduction after building the real shim with `ALIGN_LLM_NATIVE_CUDA=1`,
the pinned model pack and the local binary is:

```sh
QWEN35_GGUF=GGUF QWEN35_ALIGNPACK=PACK QWEN35_MODEL_IR=MODEL_IR \
QWEN35_RUNTIME_OPTIONS=OPTIONS QWEN35_NATIVE_COPY_BINARY=BINARY \
QWEN35_EXPECTED_SHA256=cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1 \
QWEN35_LLAMA_BENCH=PINNED_BENCH \
QWEN35_LLAMA_BENCH_SHA256=0aabc02758cf34b086d253d6b164cb6027a2aa2188b17fd66c42f483e608ae29 \
QWEN35_LLAMA_SOURCE=PINNED_SOURCE scripts/measure-qwen35-native-cuda
```

The remaining real decode target is the quantized matrix work and its graph
scheduling. Batch-copy kernel work alone did not remove the 1,622 recorded
synchronizations. A follow-up should separate prefill and decode Q4_0/Q6_K
device intervals and test a larger independent execution unit or a better Q6_K
output projection under the same real-model correctness and paired request
gates. A new local kernel
must beat the complete operation, including its scheduling boundary, before
product selection.

## Pinned llama.cpp reference attribution

An instrumented pinned llama.cpp 2B Q4_0 run (`qwen35_llama_logits_oracle
GGUF --decode-bench`) completed four setup decode steps plus 124 measured
one-token steps. With Nsight Systems node tracing, the Q4_0 fused matvec
accounted for 34.8% of captured kernel time, Q4_0 unfused matvec for 13.9%,
and the Q6_K output projection for 25.3% (128 instances, 0.886 ms median).
The two Q4_0 groups and the output projection together account for 74.0% of
this reference's instrumented kernel time. This is one llama.cpp profile,
not an uninstrumented request result. The ordinary Align profile above also
finds Q4_0 and Q6_K dominant, but prefill/decode attribution needs separation.
The 0.886 ms projection is a larger per-step target than a single
roughly 0.05 ms FFN, but its 248,320 output rows require a different
partition and reduction design.

The CUDA admission, real copy trial and paired measurements above completed
this cycle. The exact per-step Q4_0/Q6_K profile and a competitive independent
matrix operation remain the next CUDA performance hypothesis.

## Decode split and actual-weight Q6_K four-column cycle (2026-09-29)

The first follow-up used the existing ordinary and native-copy 200/32 Nsight
Systems node traces. In each trace the `mul_mat_vec_q` launch with grid X
248,320 is the full-vocabulary Q6_K projection. There are 32 such launches:
one final-prefill projection and 31 decode projections. Partitioning the
timestamp-sorted kernel rows at the first projection gives the following
ordinary Align attribution. Sums are instrumented kernel intervals, not
whole-request time; the first bucket excludes its final projection.

| Segment and signature | Count | Sum | Median |
| --- | ---: | ---: | ---: |
| Final prefill, all kernels before first Q6_K projection | 1,952 | 17.359 ms | N/A |
| Decode Q4_0 matvec, grid X 6,144 | 1,302 | 35.096 ms | 0.03136 ms |
| Decode Q4_0 matvec, grid X 2,048 | 2,046 | 22.556 ms | 0.00765 ms |
| Decode Q6_K output projection, grid X 248,320 | 31 | 28.374 ms | 0.88468 ms |
| Decode, all kernel signatures | 18,538 | 109.808 ms | N/A |

The two Q4_0 groups plus the Q6_K projection account for about 78% of
summed decode kernel intervals. The Q6_K launch is a useful local target,
though 417,177,600 packed bytes per projection make memory traffic a strong
constraint. The count and grouping were computed from
`CUPTI_ACTIVITY_KIND_KERNEL` and `StringIds` in the local
`align-200-default.sqlite`; the first projection was identified by its grid
and the captured graph's output geometry. Host gaps, transfers and readback
are outside these sums.

The existing [Metal four-column screen](qwen35-q6-batch4-screen.md) showed
that sharing packed output-head weights across related activations could be
numerically valid yet slower after full command completion. On CUDA, the
Linux-capable `capture-q6-projection.c` now captures the same actual
2,048-by-248,320 Q6_K tensor and one final-prefill plus two decode
activations. The weight SHA-256 is
`06e53b86ebe6f3e7a4b83110fd717e847404acd4bbc4670be1c80f241ff4830e`,
identical to Metal's independently captured tensor. The three CUDA input
SHA-256 values are `16c0354900a1c95930b78c17cd2ca088e0b48b70612cd998da842818a68bda06`,
`a3456024b7c061cef13d7e902298fa42ee2ae4247662152b5e572e504f8fc762`
and `ca4b797dc3a94ca130906c5a634ab1d4cd16ae63f6fd2418a56bd802076f0835`.
The model digest is the same authenticated `cd70221b...d9bb1` GGUF named
above; the CUDA plugin digest from the pinned bundle is
`ec1ddd96247a97ba6f2a564301efca6a1e9b479f29b6bdb9d166ead2bbb4f774`.
The capture files, binaries and traces stay outside Git.

The first independent kernel ported the Metal F32 dot path directly. It
failed the predeclared `0.01` all-logit bound at row zero: captured/ggml
`13.9653`, native `13.9546`. The cause was a numerical-path mismatch: this
pinned ggml CUDA Q6_K matvec quantizes each F32 input group to Q8_1 and uses
packed Q6_K × Q8_1 dot products, as seen in pinned
`ggml/src/ggml-cuda/quantize.cu:54-99` and
`ggml/src/ggml-cuda/vecdotq.cuh:627-650,1002-1025`. The first Q8_1
version also failed (`17.2841` at row zero) because its warp maximum was not
broadcast from lane zero. That error was repaired before timing. The
numerically correct scalar-int version took about `1.37 ms` versus ggml's
`0.96 ms`; 128 threads instead of 256 worsened it to about `1.44 ms`.

Packing four signed Q6_K values and using CUDA `__dp4a` for each Q8_1 group
reduced the independent complete operation to about `0.98 ms`. Every value
in all four 248,320-row columns passed the original `0.01` bound and all
four lowest-index greedy choices matched; the worst absolute difference was
`1.91e-6`. Twelve warmups preceded five alternating pairs of 20 completed
operations, including Q8_1 conversion, launch and stream completion for the
native arm. Positive ggml minus native favors independent CUDA.

| Pair | ggml complete | Independent CUDA complete | Difference |
| --- | ---: | ---: | ---: |
| 0 | 0.969943 ms | 0.974669 ms | -0.004726 ms |
| 1 | 0.960306 ms | 0.987474 ms | -0.027168 ms |
| 2 | 0.972798 ms | 0.967053 ms | +0.005745 ms |
| 3 | 0.948140 ms | 0.977703 ms | -0.029563 ms |
| 4 | 0.984654 ms | 0.984211 ms | +0.000443 ms |

Median paired difference is `-0.004725 ms`, with two independent wins.
The final source owner rerun, after the diagnostic edits, found another
five-pair loss: ggml/native medians `1.004149/1.036641 ms`, median paired
difference `-0.033346 ms`, and zero native wins. Its raw stdout is retained
locally as `q6-final-owner.stdout`. Both campaigns support keeping the
candidate outside the graph; neither is hidden by a percentage floor.
Nsight Systems node tracing found median GPU intervals of `0.92092 ms` for
the native projection and `0.90694 ms` for pinned ggml, with native/pinned
Q8_1 conversion `0.00144/0.00166 ms`. This agrees with a small local loss,
not a reproducible gain. A two-rows-per-warp variant lost all five pairs
(median paired `-0.069509 ms`); a 32-register cap lost all five (median
`-0.034834 ms`); `--use_fast_math` won one of five (median `-0.030982 ms`).
No variant is connected to a product request. These comparisons do not
establish a CUDA four-column request benefit or a general architecture
ceiling; another device and a larger fused execution unit remain open.

[NVIDIA's current best-practices guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
explains why warp memory coalescing and register pressure matter for this
mapping. [Nsight Compute's profiling guide](https://docs.nvidia.com/nsight-compute/ProfilingGuide/)
describes the memory and occupancy counters needed to distinguish them.
`ncu --set basic --kernel-name regex:q6_batch4 --launch-count 1` failed here
with `ERR_NVGPUCTRPERM`; the instrumented `ncu` run's wall times are invalid
for comparison, and no counter-based bottleneck is claimed. Nsight Systems
kernel intervals are the available measurement. The pinned ggml CUDA
`mmvq.cu` uses a different warp/row and packed-dot mapping, explaining why
the first scalar port was a poor comparison candidate; it does not prove a
specific remaining bottleneck without counters.

After the source-level comparison, NVIDIA's
[CUDA Binary Utilities guide](https://docs.nvidia.com/cuda/cuda-binary-utilities/)
provided a way to inspect the generated sm_89 cubins without GPU counters.
`cuobjdump --dump-elf-symbols`, `--extract-elf`, `--dump-sass` and
`--dump-resource-usage` identified the exact profiled functions. The native
one-row-per-warp Q6_K kernel used 40 registers, no shared memory and 49
static `LDG` instructions in its disassembly. Pinned ggml's four-column
Q6_K `mul_mat_vec_q` used 80 registers, 3,072 bytes shared memory and 30
static `LDG` instructions. Its grid was 124,160 blocks of 32 threads,
versus the native grid of 31,040 blocks of 256 threads. Static instruction
counts are not executed load counts or measured memory transactions, and
these kernels distribute work across rows differently.

The native SASS used ordinary `LDG.E` while ggml used read-only
`LDG.E.CONSTANT`. An `__ldg` trial changed all 49 native static loads to
the read-only form but had no clear completed-operation gain: two of five
native wins and `-0.024997 ms` median paired difference. Reading aligned
two-byte Q6_K words reduced static loads from 49 to 43; Nsight Systems
median native GPU interval was `0.922066 ms`, versus `0.920925 ms` for the
prior DP4A mapping, while pinned ggml remained `0.906738/0.906940 ms` in
those traces. The two-byte variant also won only two of five local pairs.
The checked-in kernel retains the prior DP4A mapping. These are useful
failures: fewer static loads and read-only cache hints alone did not produce
a measured gain on this device. A connected native path can expose a
different scheduling or fusion bottleneck.

Reproduce the capture outside timing with the authenticated GGUF, pack and
normal mode-0 CUDA binary, an empty capture directory, and the pinned headers:

```sh
cc -O2 -Wall -Wextra -Werror -shared -fPIC -I GGML_SOURCE/ggml/include \
  scripts/capture-q6-projection.c -o CAPTURE_HELPER.so -ldl
ALIGN_Q6_CAPTURE=CAPTURE_DIR LD_PRELOAD=CAPTURE_HELPER.so \
  ALIGN_LLM_NATIVE_STATE_COPY=0 BINARY --provider align-runtime GGUF PACK MODEL_IR \
  Hello RESULT.json 3 --runtime-options OPTIONS.json
scripts/run-native-cuda-q6-batch4-screen GGML_SOURCE GGML_BUNDLE CAPTURE_DIR
```

The default ggml route is retained. The independent Q6_K implementation is
also retained as the native baseline. The next CUDA capability should
connect it behind a guarded opt-in selection on real Qwen3.5 requests,
profile its device and scheduling boundary, and improve it against its own
previous revision, ordinary Align and pinned llama.cpp. A local loss to
ggml does not block that trial connection. Keep measured incremental native
gains even before the native route overtakes ggml; there is no percentage or
win-count floor. Broader Q4_0/normalization/activation fusion remains a
follow-up, informed by the connected profile and the Metal split-FFN loss.
