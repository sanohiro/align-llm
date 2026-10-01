# Native CUDA optimization log

This log records reproducible CUDA trials, including losses. The current host is
an NVIDIA GeForce RTX 4070 Ti (sm_89) with CUDA 13.3. The control is the
unchanged CUDA plugin built from pinned llama.cpp `bb4caa7540188872173c44d161602d9271386413`.
The real Qwen3.5-2B Q4_0 artifact used for session work has SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
The original isolated FFN screen uses deterministic synthetic Q4_0 weights;
the later actual-weight screen captures one final decode FFN from this 2B
artifact. Neither isolated result is a request-speed claim.

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

## 2026-09-29: actual-weight final Q4_0 decode FFN

After the connected Q6_K head stopped computing the redundant ggml output,
an exact 200-prompt/32-output RTX 4070 Ti Nsight Systems node trace counted
1,581 fused Q4_0 matvec instances (38.577 ms summed GPU intervals), 1,674
unfused Q4_0 instances (16.555 ms), and 32 native Q6_K projections
(30.069 ms). The two Q4_0 groups account for 42.6% of summed GPU kernel
intervals, making them the next target. These intervals overlap host work
and do not equal request latency. The trace used `--trace=cuda
--cuda-graph-trace=node --sample=none --cpuctxsw=none`; the full model was
ordinary ggml except the selected Q6_K head. The pinned Q4_0 implementation
references are `ggml/src/ggml-cuda/mmvq.cu` (one-row, four-warp generic
decode layout and fused gate) and `vecdotq.cuh` (Q4_0/Q8_1 dot). NVIDIA's
[CUDA 13.4 best-practices guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/#coalesced-access-to-global-memory)
describes 32-byte memory transactions for cc 6.0+ and recommends adjacent
warp accesses; that motivates measuring row/warp mapping but does not by
itself predict a win for these 18-byte Q4_0 blocks.

The diagnostic Linux interposer `scripts/capture-q4-ffn.c` selects the last
2048 × 6144 Q4_0 gate/up/GLU/down chain preceding the ordinary 248,320-row
Q6_K output head. It marks only that chain's activation and outputs before
ggml allocation, reads them after successful decode compute, and writes
create-only schema-1 files to an existing empty directory. It is never loaded
for timings. The capture request was the exact CLI prompt `Hello`, maximum two
generated tokens, returning `Hello!`, `prompt_tokens=31` and
`completion_tokens=2`. The interposer captured graph kind `1`, the first
decode step after the prompt's first generated token. The GGUF digest is at
the top of this log; the alignpack and Model IR SHA-256 digests are
`b4b418ebef9f83f911e4d604bdcce03e589fb7d2afa35f7e3bbdff3111b810b1`
and `4c5c87078f7459a6a12ef5eb313f209cbecdd834667eeec4421e7c90384d20d1`.
The runtime options selected `backend=cuda`, `device=CUDA0`,
`placement=resident`, 4,294,967,296 host-budget bytes, 8,000,000,000
device-budget bytes and `prefetch=off`, with `backend_bundle` pointing to the
pinned same-source CUDA library directory. Build the interposer using the
command in its source header and the pinned ggml include directory. With
`GGUF`, `ALIGNPACK`, `MODEL_IR`, `RUNTIME_OPTIONS`, and `GGML_LIB` referring to
those exact artifacts, reproduce the capture with this invocation (`OUT_JSON`
must be outside the empty capture directory):

```sh
mkdir -p "$CAPTURE_DIR"
env ALIGN_Q4_FFN_CAPTURE="$CAPTURE_DIR" LD_PRELOAD="$CAPTURE_INTERPOSER" \
  ALIGN_LLM_NATIVE_Q6_HEAD=0 ALIGN_LLM_NATIVE_SWIGLU=0 \
  ALIGN_LLM_NATIVE_STATE_COPY=0 \
  ./main --provider align-runtime "$GGUF" "$ALIGNPACK" "$MODEL_IR" \
  'Hello' "$OUT_JSON" 2 --runtime-options "$RUNTIME_OPTIONS"
```

The capture directory must already be empty. Then run:

```sh
scripts/run-native-cuda-q4-ffn-screen GGML_SOURCE GGML_LIB GGML_CUDA_PLUGIN CAPTURE_DIR
```

The actual final-decode capture has gate/up/down SHA-256 digests respectively
`aecf2ed2db40e2adb6ea5c13c8906b9109c9effaac4937d5336d116896eabc14`,
`bbfe36a3e2cf525491fadf61508d06b1cf90ed8bb12b1aaf34beb2763dc35d4e`,
and `aad841c012ddff8aa14b4c97a59bf25503337224ec0af526c62f038978e8c530`.
Input, gated and final digests are `a78563211891a93d2f839ca4244b3a44cede7ea2c4e30443fb2125c6501fa2e2`,
`a29b34e4e261e7c6c07aac556d75372ad49a405a1272c9c46e7c4f533da99d87`,
and `d7727937372745110e9f4a9fa392dd3122a54e6e6bf1303277562b02363ecae7`.
No model bytes are checked in. Both standalone ggml and native results match
all captured gated/down values under the predeclared mixed bound; native
versus standalone ggml maximum absolute differences were 1.78814e-6 for
6,144 gated values and 4.76837e-7 for 2,048 down values on the initial
two-warp baseline. The four-warp-down candidate passed with 1.78814e-6 and
2.38419e-7 maximum differences. The standalone screen checks these full
rows after warmup and after each timing pair.
Focused negative probes with a missing `complete.txt`, malformed geometry,
and a zero-length gate weight each failed before CUDA device initialization.

| Trial | Actual-weight observation | Decision |
| --- | --- | --- |
| Two rows/block, two warps/row for gate/up and down | Initial five pairs: ggml/native complete-FFN medians 0.055520/0.058314 ms, native lost all five. Adjacent profiled down median 8.064 µs. | Retain as previous independent baseline. |
| One row/block, four warps/row **only for down** | Full numeric checks pass. Its first five pairs were 0.043653/0.044871 ms; the adjacent Nsight node trace counted 112 down calls at 7.616 µs median versus 8.064 µs for the previous layout (about 0.448 µs less). Gate/up and quantize code are unchanged. | Retain the small down-kernel improvement in the independent screen. Complete FFN remains slower than ggml and is not connected to requests. |
| Four rows/block, one warp/row for gate/up as well | Numeric checks pass; five-pair complete-FFN medians 0.060849/0.064147 ms. The within-run native loss was about 3.3 µs; no improvement was established, so this layout was reverted. | Failed local hypothesis. |

The first four-warp attempt accidentally advanced the down loop by the old
64-lane stride. Its full-row check caught a 0.17475 difference at output zero;
correcting the stride to 128 restored parity before timing. This is why a
mapping change must update both lane assignment and loop stride.

To challenge the small gain under variable GPU clocks, baseline and down-only
executables were built from the same tree except the mapping. Eight alternating
complete-FFN runs, each five paired ggml/native samples, had baseline
ggml/native median pairs of 0.047425/0.047804, 0.059497/0.063424,
0.043998/0.046475, and 0.095330/0.081405 ms; down-only pairs were
0.057153/0.059485, 0.047903/0.048343, 0.043361/0.044738, and
0.045191/0.045816 ms. The last baseline run was an outlier. The complete
operation timing does **not** resolve a repeatable 0.448-µs difference, so
the measured claim is limited to the instrumented down kernel, supported
also by the earlier synthetic one-row/four-warp down result (7.648 versus
7.936 µs). Connecting a native Q4_0 route requires a graph boundary that
preserves complete logits/state and paired whole-request evidence. NVIDIA's
[CUDA Graphs guide](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html)
explains why both local arms capture their repeated work; graph capture does
not eliminate the cost of additional product graph boundaries.

## 2026-09-30: aligned Q4_0 packed loads

The baseline is merged PR #330, `14c05d96e4d41ece4c2e8d0701284cb321da6f7d`.
The independent helper assembled each four-byte packed weight word from four
byte loads. An 18-byte Q4_0 block has only two-byte alignment. Representing
its unchanged 16-byte payload as eight `uint16_t` values lets each dot use
two naturally aligned loads per packed word. Size, alignment and payload
offset are checked statically. Lane mapping, DP4A arithmetic, zero-point
correction, Q8_1 conversion and four-node captured graph are unchanged.
The pinned implementation's `vecdotq.cuh:get_int_b2` uses this same alignment
principle. NVIDIA's [global-memory alignment rules](https://docs.nvidia.com/cuda/archive/12.9.1/cuda-c-programming-guide/index.html#device-memory-accesses)
motivate the experiment; the measurements establish its effect here.

Both arms use the pinned ggml source/plugin, RTX 4070 Ti, sm_89 compiler flags
and exact actual-weight capture documented above. The actual owner passed
every 6,144-element gated and 2,048-element final row before/after warmup and
after each pair; native-versus-ggml maximum absolute differences remain
`1.78814e-6` and `9.53674e-7`. The synthetic owner passed with `1.49012e-8`
and zero. No numerical bound changed.

Two alternating Nsight Systems node-trace comparisons counted 112 instances
of each matvec per arm. Medians are microseconds:

| Trace order | Baseline gate/up | Candidate gate/up | Baseline down | Candidate down |
| --- | ---: | ---: | ---: | ---: |
| Baseline, candidate | 11.392 | 8.640 | 7.104 | 5.760 |
| Candidate, baseline | 11.457 | 8.672 | 7.136 | 5.760 |

Within the same traces, pinned ggml gate/up medians were 11.168/11.200 and
11.233/11.264 microseconds, and its down medians were 5.952/5.952 and
5.984/5.984. Thus the native improvement is not explained by an equally
large change in the control. Native quantization medians stayed near
1.024–1.072 microseconds. `cuobjdump --dump-sass` found 40 static
`LDG.E.U8` and 3 `LDG.E.U16` instructions in the preceding executable's
device code versus zero and 23 in the candidate. This confirms the changed
load width, not executed instruction or memory-transaction counts; Nsight
Compute counters remain denied. Gate/up improves by about 24% and down by
about 19% in these local instrumented intervals.

Five alternating **process** pairs still had substantial timing variation.
Every process performed the existing five ggml/native pairs. Its native
complete-FFN medians were:

| Process pair | Baseline ms | Candidate ms |
| --- | ---: | ---: |
| 0 | 0.052416 | 0.040112 |
| 1 | 0.045996 | 0.042589 |
| 2 | 0.046228 | 0.044180 |
| 3 | 0.049139 | 0.057270 |
| 4 | 0.046640 | 0.057760 |

These process medians alone cannot resolve the complete-operation effect.
An additional retained diagnostic links both helpers into one process,
renaming the four baseline C ABI symbols. It shares immutable packed
weights/input, gives each helper its own stream/graph/scratch, warms both 12
times, then alternates 20 synchronized operations per pair. The unchanged
ggml graph computes untimed reference rows. Both helpers' complete outputs
are checked against ggml, the captured rows and each other after warmup and
every pair. The three five-pair runs below include all samples (milliseconds):

| Run | Pair | Baseline | Candidate |
| --- | ---: | ---: | ---: |
| 0 | 0 | 0.063013 | 0.058696 |
| 0 | 1 | 0.065455 | 0.059227 |
| 0 | 2 | 0.061937 | 0.056374 |
| 0 | 3 | 0.059300 | 0.054689 |
| 0 | 4 | 0.048887 | 0.044472 |
| 1 | 0 | 0.091851 | 0.092553 |
| 1 | 1 | 0.103019 | 0.093275 |
| 1 | 2 | 0.099183 | 0.087763 |
| 1 | 3 | 0.097894 | 0.084001 |
| 1 | 4 | 0.091836 | 0.091980 |
| 2 | 0 | 0.061882 | 0.058244 |
| 2 | 1 | 0.061742 | 0.056169 |
| 2 | 2 | 0.062430 | 0.058119 |
| 2 | 3 | 0.080375 | 0.062788 |
| 2 | 4 | 0.061840 | 0.057077 |

Paired baseline-minus-candidate medians are 4.611, 9.744 and 4.763
microseconds, with 5/5, 3/5 and 5/5 candidate wins. The middle run is much
slower in both arms and includes two small losses; host/clock interference
is unresolved. This supports a useful independent FFN improvement over
the preceding native version together with the repeated device intervals,
without establishing a precise portable percentage or a request speedup.
Keep this implementation; product requests still use ggml Q4_0.

Reproduce the checked-in numeric owner with the three explicit pinned
operands, with and without `CAPTURE_DIR`, as above. The comprehensive review
identified that the additional same-process diagnostic was available only
locally. The repair puts that comparison into the existing checked-in
benchmark and runner without duplicating the driver. To reproduce its
baseline/candidate comparison from a fresh checkout, run:

```sh
git show 14c05d96e4d41ece4c2e8d0701284cb321da6f7d:scripts/native_cuda_q40_ffn.cu > "$BASELINE_SOURCE"
scripts/run-native-cuda-q4-ffn-screen "$GGML_SOURCE" "$GGML_LIB" "$GGML_CUDA_PLUGIN" "$CAPTURE_DIR" "$BASELINE_SOURCE"
```

`BASELINE_SOURCE` is a caller-selected writable `.cu` file outside the
repository. The runner prints its SHA-256, builds both helpers with identical
sm_89 flags and four renamed baseline ABI symbols, then reports all five
`baseline_ms`/`native_ms` pairs. The baseline source digest must match the
one below. In paired mode ggml remains an untimed numeric reference. All
original ggml/native owner modes remain available. Use the documented
node-trace command in alternating orders for separate device attribution.
Raw owner/process/trace/SASS receipts and the historical diagnostic source
are retained outside Git as `q4-packed-loads-20260930`.
The original `bench-paired.cu` SHA-256 is
`cdd3a744b9ebbe6fe1d3bc3296c9f3276923cf3c4866e6c8fcf49e1526d22281`;
the preceding helper source SHA-256 is
`39edfecc974a84f1f3197ec7f208d5a57fea8fd1946e22c574c53772ab4d67e5`.
The repaired checked-in paired runner passed all numeric checks in three
fresh five-pair runs. All post-repair samples are milliseconds:

| Run | Pair | Baseline | Candidate |
| --- | ---: | ---: | ---: |
| 0 | 0 | 0.047524 | 0.044361 |
| 0 | 1 | 0.045402 | 0.041571 |
| 0 | 2 | 0.044280 | 0.040522 |
| 0 | 3 | 0.046134 | 0.041837 |
| 0 | 4 | 0.046752 | 0.041925 |
| 1 | 0 | 0.060434 | 0.099838 |
| 1 | 1 | 0.094532 | 0.090722 |
| 1 | 2 | 0.093819 | 0.092489 |
| 1 | 3 | 0.093205 | 0.092129 |
| 1 | 4 | 0.084362 | 0.101785 |
| 2 | 0 | 0.046016 | 0.040972 |
| 2 | 1 | 0.044229 | 0.040319 |
| 2 | 2 | 0.052468 | 0.046480 |
| 2 | 3 | 0.045868 | 0.042857 |
| 2 | 4 | 0.045942 | 0.041362 |

The repaired runner's paired gain medians are 3.831/1.076/4.580 microseconds,
again 13/15 wins, with substantial outliers in the middle run. The repaired
ordinary ggml/native actual-weight owner passed but its per-arm medians
were 0.054690/0.059447 ms; the synthetic owner passed at
0.043652/0.040967 ms. These retain the uncertainty about complete-FFN
superiority over ggml. A missing baseline file was refused with exit 2
before compilation/device initialization; shell syntax and diff checks pass.
The bounded lesson is to inspect generated load widths before changing
lane mapping again. A larger connected CUDA boundary and its request
correctness/timing remain the next consumer; other GPUs, Qwen sizes and
Gemma are unmeasured.

## Connected native-head CUDA greedy readback (2026-09-30)

The user resumed experiments. The first connected candidate replaces the
native head's full-row CPU greedy scan with a two-stage CUDA reduction and
eight-byte readback, while preserving the complete logits for diagnostics.
The source projection and selection mode remain unchanged. The helper adds
7,768 admitted device bytes; Align, shim and CUDA sizes agree at 1,003,352.
The kernel owner covers cross-warp/block ties, signed zero, extreme/random
finite rows, NaN/infinities, repeated reads and invalidated output. Test
fixture uploads explicitly use and drain the helper stream: a pageable
default-stream upload was not a dependency for its nonblocking stream.

`run-qwen35-native-q6-head-smoke` passed three full logits and 252 resident
planes at 31/200/330 prompt tokens, with maximum error `1.90734863e-6` and
equal model-operation counts (`2058`). Retained short/wider/short requests
and malformed selection passed. Forced submit, completion and greedy
failures each allowed the ordinary control but refused the selected request
without output, worker exit 2. Build, formatter, Python boundary guard and
its 30-case mutation owner passed. This is a local implementation checkpoint;
publication/review remain pending.

Two uninstrumented campaigns used two warmups followed by five alternating
pairs per workload. The preserved full-row native control was built from
`53872693b283a34dcda2ecc77e654f3029060340`, executable SHA-256
`cb82d8fb9f10067bd1f247779d4bafdf92d7f9c6658a2455201e50fdba3e9f20`.
The same model/plugin/pinned llama.cpp identities apply. All outputs matched.
Paired gains below are milliseconds; positive favors the new candidate.

| Run | Prompt/output | Previous native gain / wins | Ordinary Align gain / wins | Pinned llama.cpp gain / wins |
| --- | --- | --- | --- | --- |
| 1 | 56/16 | +3.909 / 4/5 | -1.112 / 2/5 | +15.505 / 4/5 |
| 1 | 200/32 | +4.273 / 5/5 | -0.537 / 2/5 | +11.028 / 5/5 |
| 1 | 330/64 | +3.707 / 4/5 | +9.240 / 4/5 | +18.996 / 4/5 |
| 2 | 56/16 | +6.822 / 3/5 | +0.714 / 3/5 | +16.452 / 5/5 |
| 2 | 200/32 | -0.786 / 2/5 | +2.405 / 3/5 | +7.538 / 4/5 |
| 2 | 330/64 | +4.437 / 3/5 | +1.407 / 3/5 | +14.399 / 5/5 |

The middle-workload reversal and large outliers prevent a general speed
claim. All samples are retained outside Git in `measure-1.log` and
`measure-2.log` under the durable trial evidence. Reproduce with the existing
`measure-qwen35-native-cuda` inputs, `QWEN35_CUDA_MEASURE_MODE=q6-head`, and
optional `QWEN35_CUDA_BASELINE_BINARY` plus its required exact
`QWEN35_CUDA_BASELINE_SHA256`. A wrong baseline digest refuses before sessions.

A separate three-token Nsight Systems trace contains exactly three D2H
copies of eight bytes and no full-row copy. Native projection, partial and
final reduction GPU intervals average 899.229/5.845/2.336 microseconds.
The two decode projection-to-reduction gaps are 54.370 and 47.746
microseconds in this instrumented run. This motivates the next bounded
variant: submit reduction/readback before the projection's existing wait,
then let the token reader consume a completed host result. Instrumented
intervals do not predict uninstrumented request gains.

### Submit greedy selection before the native completion wait

The next candidate submits projection, both reduction kernels and the
eight-byte readback before one stream wait. The token getter consumes a
completed host choice without another CUDA call. The shim accounts that
transfer at graph commit. Plain standalone projection callers retain the
on-demand getter. Device allocation and projection arithmetic are unchanged.
The kernel owner also exercises prefetched fixtures, a complete synthetic
zero-weight projection, repeated reads and failed-projection invalidation.
Complete real-model logits/state, retained requests, malformed mode and all
three forced failure boundaries pass again. The maximum logit error remains
`1.90734863e-6`; admitted/allocated/peak totals rise by exactly 7,768 bytes
from the preserved native control.

A first single-request campaign gave previous-native paired median gains
of +6.502/-4.044/+8.303 ms and ordinary-Align gains of
+0.480/+2.880/+7.171 ms at 56/16, 200/32 and 330/64. The middle-workload
reversal justified a bounded repeat campaign rather than a general claim.
`QWEN35_CUDA_PAIR_REQUESTS=20` averages twenty actual requests per Align arm
within each of five alternating pairs and retains every individual sample.
Pinned llama.cpp retains one warm generation interval per pair; its column
has different repetition uncertainty. All 900 timed Align requests have the
required counts and matching output text. No samples were excluded.

| Prompt/output | Pair | Ordinary Align ms | Candidate ms | Previous native ms | Pinned llama.cpp ms |
| --- | --- | --- | --- | --- | --- |
| 56/16 | 0 | 73.965 | 74.926 | 74.893 | 89.357 |
| 56/16 | 1 | 72.979 | 72.186 | 73.981 | 87.275 |
| 56/16 | 2 | 73.833 | 71.474 | 74.097 | 118.022 |
| 56/16 | 3 | 75.948 | 71.652 | 74.352 | 90.036 |
| 56/16 | 4 | 73.286 | 72.888 | 74.576 | 90.801 |
| 200/32 | 0 | 163.087 | 159.299 | 160.577 | 169.586 |
| 200/32 | 1 | 166.022 | 160.696 | 163.749 | 167.491 |
| 200/32 | 2 | 163.313 | 166.156 | 162.359 | 171.037 |
| 200/32 | 3 | 164.842 | 166.602 | 163.523 | 174.253 |
| 200/32 | 4 | 163.150 | 161.103 | 165.267 | 173.345 |
| 330/64 | 0 | 311.843 | 305.101 | 312.967 | 334.707 |
| 330/64 | 1 | 366.157 | 303.507 | 318.498 | 319.143 |
| 330/64 | 2 | 312.066 | 310.025 | 319.301 | 327.312 |
| 330/64 | 3 | 313.232 | 302.839 | 317.390 | 342.798 |
| 330/64 | 4 | 318.484 | 311.178 | 317.800 | 322.075 |

| Prompt/output | Previous native gain / wins | Ordinary Align gain / wins | Pinned llama.cpp gain / wins |
| --- | --- | --- | --- |
| 56/16 | +1.795 ms / 4/5 | +0.794 ms / 4/5 | +17.913 ms / 5/5 |
| 200/32 | +1.277 ms / 3/5 | +2.047 ms / 3/5 | +7.652 ms / 5/5 |
| 330/64 | +9.277 ms / 5/5 | +7.306 ms / 5/5 | +17.287 ms / 5/5 |

These are medians of paired arithmetic means, not pooled token throughput.
The ordinary 330/64 pair 1 retains a 1,449.975 ms request outlier. The
short/middle differences remain small and variable. The strongest result
is this retained 2B/RTX 4070 Ti 330/64 workload; the route stays default-off.
No cold-load, TTFT, other-model or other-device improvement is established.
The baseline shim SHA-256 is
`e932b6ba478a8969c44dcfe903cea06459d44e55c21c892814deea389a19da89`;
the completed candidate shim is
`58bbf96330a59c362b8287ad81a4c4952e687c9c2790cae2d3da870f930560a4`.
Raw `measure-prefetched-1.log`, `measure-prefetched-batch20.log`, owner/fault
logs and profiler artifacts remain outside Git. Reproduce with the existing
explicit model/binary/plugin/trace inputs and baseline digest above, then
`QWEN35_CUDA_PAIR_REQUESTS=20 scripts/measure-qwen35-native-cuda` in
`q6-head` mode. Invalid repeat counts refuse before sessions.

One comprehensive host-native review found that the new preserved binary
digest did not bind the shared shim containing the CUDA implementation.
The consolidated repair requires an explicit baseline shim path/digest,
checks its hash before sessions, verifies the loaded Linux mapping's exact
path/device/inode after readiness and rechecks the hash before timing.
Wrong hash and wrong loaded path both refuse. The root-cause audit covers
the optional baseline arm's executable/library identity; the existing plugin
and pinned-reference identity checks remain. CUDA arithmetic and scheduling
are unchanged by this measurement repair.

A second complete twenty-request campaign verifies that loaded baseline
identity, retains another 900 timed Align requests and gives:

| Prompt/output | Previous native gain / wins | Ordinary Align gain / wins | Pinned llama.cpp gain / wins |
| --- | --- | --- | --- |
| 56/16 | +3.630 ms / 5/5 | +1.404 ms / 5/5 | +17.907 ms / 5/5 |
| 200/32 | +2.584 ms / 4/5 | +1.317 ms / 4/5 | +7.117 ms / 4/5 |
| 330/64 | +8.462 ms / 5/5 | +3.734 ms / 4/5 | +19.818 ms / 5/5 |

All counts and output text match again. This repeats the strongest gain
against the old native route, while the ordinary-Align gain remains smaller
and variable. Raw pairs and every sample are in
`measure-bound-shim-batch20.log`. Reproduction additionally requires
`QWEN35_CUDA_BASELINE_SHIM` and `QWEN35_CUDA_BASELINE_SHIM_SHA256`, with the
baseline shim digest above. Other controls retain their previous invocation.

The separate 200/32 Nsight Systems trace contains exactly 32 eight-byte D2H
copies and no full-row copy. Native projection averages 894.782 microseconds;
projection-to-partial-reduction gap median is 1.184 microseconds, range
1.088..86.276. This demonstrates the intended scheduling change; the earlier
three-token trace is a different instrumented workload, not a paired timing
control. Q4_0 fused one-column kernels still sum to 38.358 ms, unfused
one-column kernels to 15.633 ms, and native projections to 28.633 ms.
The actual 6144-row fused gate/up instances average 34.229 microseconds,
well above the small repeatedly cached FFN screen. The next hypothesis must
test larger weight working sets before projecting local Q4 gains onto a
whole request. Nsight Compute bandwidth counters remain unavailable.

## Deferred CUDA hypotheses from user-supplied advice (2026-09-30)

This dated shortlist is historical. The greedy scheduling, pressure variants
and larger final tail have since been tested below. The current investigation
and proposed next experiment are in the
[2026-10-01 design](specs/gpu-runtime-performance.md#cuda-next-experiment-design-2026-10-01);
the user authorized preparation and design only.

The user supplied a Claude analysis and explicitly requested recording useful
ideas for later work. These are hypotheses, not new adoption gates or an
instruction to start additional experiments in this capability. Prioritize
them against the actual RTX 4070 Ti (sm_89), Qwen3.5-2B Q4_0/Q6_K traces;
H100/Blackwell figures and claimed universal bandwidth percentages are not
measurements of this host. Metal and CUDA wins remain scoped to the routes,
workloads and controls in their own receipts.

| Priority | Later experiment | Applicability and evidence required |
| --- | --- | --- |
| First | Profile prefill and decode separately, including host submission, synchronization, copies and allocations. | Use the existing 200/32 and short/wider request controls. Q4_0 and Q6_K dominate the current decode trace; do not infer that attention or prefill is the same bottleneck. A wall-time-minus-summed-kernel value includes host work, transfers, idle intervals and possible overlap, so inspect the timestamped critical path before calling it launch overhead. |
| First | Inspect SASS load widths, register count/spills and independent outstanding loads; try bounded unrolling or layout changes. | The aligned Q4_0 loads above already demonstrate the value of inspecting generated code. Keep direct sm_89 compilation and record `-Xptxas=-v` output. Existing Q4_0/Q6_K block strides do not permit unconditional `uint4` loads; any repack needs explicit initialization cost, resident-memory accounting, ownership and reuse measurements. |
| First | Extend native fusion across residual/RMSNorm, Q8 activation quantization and the FFN/output-head boundary. | DP4A, fused gate/up/SiLU and local CUDA Graphs already exist. Measure a larger connected boundary that avoids another ggml/native wait; preserve full logits/state, failure containment and operation/device-memory accounting. Kernel fusion and graph replay address different costs. |
| Next | Capture/replay the connected native tail beyond the completed greedy-readback trial. | The ggml decode graph is already captured; the selected native Q6_K route now reduces on device and reads eight bytes before one completion wait. Measure incremental tail replay only against that completed baseline. Preserve first-index ties, nonfinite policy, exact output/EOG handling and request failure semantics before any device-fed next token. Existing Metal greedy results do not establish a CUDA gain. |
| Conditional | Test streaming-load/cache hints and compute a workload-specific bandwidth estimate. | A small repeatedly executed Q4_0 FFN can reuse L2; bypass/eviction hints may hurt it. The Q6_K head has a much larger weight footprint. Keep useful payload bandwidth distinct from actual DRAM traffic, and include KV/recurrent-state bytes when estimating a whole request. `ncu` DRAM/sectors/occupancy counters need Windows-host permission, currently denied; do not invent their values. |
| Conditional | Split long-context decode attention, share GQA KV reads, or use optimized prefill matrix/attention primitives. | Start only if a length-dependent profile makes attention or prefill material. Qwen3.5 has both recurrent DeltaNet and full-attention layers; generic 32-head/H100 examples do not describe its entire graph. Tensor Core/dequant primitives must match sm_89, actual quantization and token count. KV quantization changes rounding/state representation and needs separate qualification. |
| Later | Revisit small-batch target verification or bounded draft generation with weight reuse across rows. | Existing lookup/acceptance screens have both gains and rejection regressions; inspect their receipts first. CUDA M=2–8 weight reuse is a hypothesis, not an automatic speculative-decoding win. Preserve exact acceptance/replay and measure complete requests. |
| Deferred hardware/complexity | PDL, Blackwell native FP4, and a persistent whole-forward kernel. | NVIDIA documents PDL for compute capability 9.0+, excluding this sm_89 host. Blackwell-only arithmetic is unavailable here. A persistent kernel is deferred until a connected bottleneck justifies explicit scheduling/resource/failure design. |

Primary references for future trials: NVIDIA's
[global-memory/SIMT guide](https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/writing-cuda-kernels.html),
[effective versus actual bandwidth guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/#bandwidth),
[CUDA Graphs guide](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html),
and [PDL availability and synchronization contract](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/programmatic-dependent-launch.html).
No fixed 80–90% kernel/60–70% request bandwidth rule is adopted, and no
automatic 16-byte-load, cache-bypass or all-layer Tensor Core conversion is
assumed to improve this workload. A selected future trial records its own
numerical limits, cost ceiling and owner before implementation.

### Verification of the linked optimization roundup (2026-09-30)

The user also supplied this [optimization roundup](https://note.com/samehadaonsen/n/n8d53b4e1f746).
Its linked upstream changes are useful discovery leads, with these corrections:

- [llama.cpp PR #26079](https://github.com/ggml-org/llama.cpp/pull/26079/files)
  adds hardware/quantization-specific MMVQ-to-MMQ thresholds, not the
  article's `GGML_CUDA_MMVQ_MAX` environment variable. The measured pinned
  source `bb4caa7540188872173c44d161602d9271386413` already contains the change
  in `ggml/src/ggml-cuda/mmvq.cu`. Ada's dense Q4_0 and Q6_K cases retain the
  default threshold. The useful later hypothesis is to measure dispatch
  and weight reuse for actual multirow verification shapes; this change
  does not supply a new setting for our one-column decode.
- [vLLM PR #49750](https://github.com/vllm-project/vllm/pull/49750)
  avoids a contiguous residual copy by accepting strided RMSNorm inputs.
  Its B300, BF16, width-7168 benchmark reports 3.15x at 2,048 tokens and
  1.23x at one token, rather than a 3.1x whole-request or RTX 4070 Ti gain.
  Inspect our copy/normalization boundaries before considering a similar
  change; the larger residual/RMSNorm/Q8 fusion hypothesis above remains
  deferred pending a connected trace and correctness owner.

Keep the roundup as a source of upstream links. Verify implemented APIs,
merge status, workload and hardware in each primary source before selecting
an experiment; neither reported factor predicts our request speed.

## 2026-09-29: Q4_0 half-block lane mapping follow-up

The pinned `vecdotq.cuh` uses two lanes per Q4_0 block in decode: each lane
reads eight packed bytes and two Q8_1 four-byte groups, then subtracts half
of the block's F16-scaled zero-point correction. The preceding independent
CUDA kernel instead gave one lane all 16 packed bytes and four Q8_1 groups.
NVIDIA's current [CUDA Best Practices Guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/#coalesced-access-to-global-memory)
supports testing adjacent lane accesses, but the 18-byte block layout and
register effects make the result empirical. This trial used the unchanged
actual-weight capture digests above, pinned ggml commit `bb4caa7540188872173c44d161602d9271386413`,
its `cuda-kit-28a6fe3` plugin and RTX 4070 Ti. Both arms were compiled with
`nvcc -O3 -std=c++17 -gencode arch=compute_89,code=sm_89`.

The first candidate applied half-block mapping to gate/up and down. Every
captured gated/final element passed the predeclared bound; maximum absolute
native-versus-standalone-ggml differences were `1.66893e-6` and `9.53674e-7`.
Its adjacent 112-instance Nsight node trace reduced the down median from
`7.744` to `7.136` microseconds but increased gate/up from `11.585` to
`11.904` microseconds. Gate/up half-block mapping was reverted. The retained
candidate changes down only; the correction is `-4 * Q8_1.sum` per lane, so
the two lanes recover the original block's `-8 * Q8_1.sum` after reduction.

The down-only actual-weight owner passed all 6,144 gated and 2,048 final
values, with maximum absolute differences `1.78814e-6` and `9.53674e-7`.
The separate synthetic full-row owner also passed, with maxima `1.49012e-8`
and zero. Both used the existing 12 warmups, five alternating pairs of 20
complete FFNs, and output checks after every pair. The adjacent alternating
Nsight node traces gave these GPU medians (microseconds, 112 instances each):

| Trace order | Preceding gate/up | Preceding down | Down-only gate/up | Down-only down |
| --- | ---: | ---: | ---: | ---: |
| Baseline then candidate | 11.489 | 7.681 | 11.552 | 7.168 |
| Candidate then baseline | 11.680 | 7.776 | 11.456 | 7.104 |

Quantize stayed at `1.088` microseconds median in all four traces. Thus the
down kernel improved by `0.513` and `0.672` microseconds in the two adjacent
comparisons, while gate/up remained close to its previous interval. The
first independent complete-FFN run had native/ggml medians `0.044760/0.042882`
ms for the preceding binary; the down-only run had `0.091230/0.094810` ms.
A further five alternating baseline/candidate process pairs had substantial
clock variation: complete native medians ranged `0.042984–0.096308` ms for
baseline and `0.043144–0.058450` ms for candidate. Their paired differences
do not establish complete-FFN speedup. No connected request or general
llama.cpp gain is claimed; the improvement retained here is the repeatable
down-kernel interval only. Raw owner, ten process-arm and four node-trace
receipts are retained outside Git as `q4-halfblock-*` under the local CUDA
evidence directory.

`ncu` counters still fail with `ERR_NVGPUCTRPERM`. NVIDIA's
[Nsight Compute profiling guide](https://docs.nvidia.com/nsight-compute/ProfilingGuide/)
states that WSL counter access must be enabled in the Windows host NVIDIA
Control Panel. Nsight Systems node timing remains available without those
counters. A next experiment should test a larger native Q4_0 boundary, since
this sub-microsecond down gain does not by itself cover an extra graph split.

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
ALIGN_Q6_CAPTURE=CAPTURE_DIR LD_PRELOAD=./CAPTURE_HELPER.so \
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

## Connected one-column Q6_K trial: correctness and duplicate cost (2026-09-29)

Branch `agent/native-cuda-q6-connected` selects the independent Q8_1/DP4A
kernel through Align's default-off `ALIGN_LLM_NATIVE_Q6_HEAD=1` mode. The
kernel borrows the real resident Q6_K weight, the normalized F32 activation
and the ggml output buffer. For this first connection it runs after the
synchronized ggml graph and overwrites the F32 logits. Thus the graph still
performs the same Q6_K projection. This intentional duplicate establishes a
real-request correctness, ownership and failure baseline; it is not a speed
candidate for default routing.

Before connection, replacing four columns with one in the same actual-weight
screen produced maximum absolute logit difference `1.91e-6` and identical
greedy choice. Two uninstrumented five-pair repeats had median paired native
gains of `+0.013978 ms` (3/5 wins) and `-0.007316 ms` (2/5 wins).
Nsight Systems reported 113 instances of each one-column projection:
median native `893.088 us`, ggml `886.848 us`; native and ggml Q8_1
conversion medians were `1.408` and `1.568 us`. This small GPU interval
loss and sign-changing completed-operation result do not establish a local win.

On the authenticated 2B model, three final-prefill/decode graphs at each of
31-, 200- and 330-token prompts passed all 248,320 F32 logits under the
predeclared `0.01` bound, with maximum absolute difference `1.91e-6` in every
case. Greedy output and all 252 valid resident-state hashes per case matched
mode `0`. A short/wider/short retained session also returned the same output
and token counts. Invalid mode `2` returned an error with empty output.
Forced CUDA submit and completion faults left the ordinary ggml control
usable but made the selected session return only a failed envelope and exit 2.
The standalone C/CUDA module owns one stream and 2,304 bytes of Q8_1 scratch;
no second model weight or full-logit device buffer is allocated.

Five alternating warm request pairs per condition used the same 2B GGUF,
prompt IDs, output counts and digest-bound pinned llama.cpp executable
`0aabc02758cf34b086d253d6b164cb6027a2aa2188b17fd66c42f483e608ae29`
from source `bb4caa7540188872173c44d161602d9271386413`. Both Align
sessions stayed resident; each llama.cpp sample was its third warmed
iteration in a fresh process. The timed interval excludes startup and model
load. Every generated output matched. Times are milliseconds:

| Prompt/output | Pair | Ordinary Align | Native Q6_K | Pinned llama.cpp |
| --- | ---: | ---: | ---: | ---: |
| 56/16 | 0 | 78.506 | 94.983 | 89.619 |
| 56/16 | 1 | 72.494 | 90.082 | 93.494 |
| 56/16 | 2 | 72.042 | 88.319 | 92.876 |
| 56/16 | 3 | 72.619 | 88.647 | 89.952 |
| 56/16 | 4 | 72.182 | 88.500 | 104.056 |
| 200/32 | 0 | 157.556 | 189.085 | 168.373 |
| 200/32 | 1 | 167.882 | 188.266 | 171.192 |
| 200/32 | 2 | 160.982 | 187.779 | 174.700 |
| 200/32 | 3 | 170.292 | 191.027 | 168.334 |
| 200/32 | 4 | 164.936 | 208.372 | 167.003 |
| 330/64 | 0 | 330.331 | 366.819 | 328.225 |
| 330/64 | 1 | 317.890 | 386.848 | 330.505 |
| 330/64 | 2 | 305.276 | 373.372 | 325.204 |
| 330/64 | 3 | 312.270 | 379.543 | 318.696 |
| 330/64 | 4 | 304.875 | 382.355 | 332.610 |

Median paired native gain versus ordinary Align was `-16.317`, `-26.797`
and `-68.096 ms`, with 0/5 native wins in each condition. Median paired gain
versus pinned llama.cpp was `+3.412`, `-20.712` and `-49.745 ms`, with
4/5, 0/5 and 0/5 wins. This is expected for a duplicated roughly 0.9 ms
projection per output token, but the request measurements are the evidence;
the isolated kernel interval alone does not predict request wall time.
The retained raw stdout is `q6-connected-measure.stdout` outside Git.

A three-token Nsight Systems node trace counted exactly three pinned ggml
Q6_K output launches and three native `project` launches. Their median GPU
intervals were `886.940 us` and `887.484 us`; native Q8_1 quantization
added three `1.440 us` intervals. The profile establishes the duplicated
device work; it does not attribute all host/request overhead. Nsight Compute
counters remained inaccessible (`ERR_NVGPUCTRPERM`), so there is no claim about
executed memory transactions. The pinned ggml source
`ggml/src/ggml-backend.cpp` confirms that `ggml_backend_graph_compute`
synchronizes before returning; NVIDIA's
[asynchronous execution guide](https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/asynchronous-execution.html)
defines the stream boundary, and its
[best practices guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
distinguishes useful payload bandwidth from measured DRAM traffic.

Reproduce the numeric owner with `QWEN35_GGUF`, `QWEN35_ALIGNPACK`,
`QWEN35_MODEL_IR`, `QWEN35_RUNTIME_OPTIONS`, `QWEN35_NATIVE_Q6_BINARY`,
`QWEN35_STATE_TRACE` and `QWEN35_EXPECTED_SHA256` set, then run
`scripts/run-qwen35-native-q6-head-smoke`. The trace interposer's optional
`ALIGN_LOGIT_DUMP_DIR` writes full F32 vectors only in this diagnostic.
For request timing, set `QWEN35_CUDA_MEASURE_MODE=q6-head` and the existing
digest-bound pinned llama.cpp inputs, then run
`scripts/measure-qwen35-native-cuda`.

## Connected Q6_K without duplicate projection (2026-09-29)

The second connected step makes mode `1` expand the normalized activation as
the ggml graph output. The Q6_K output tensor remains checked metadata but is
not graph-expanded. After synchronized upstream graph completion, the same
native Q8_1/DP4A kernel writes its own 993,280-byte device output, which Align
reads through a checked native ABI. Mode `0` still executes and reads ggml's
Q6_K projection. The helper adds only that output allocation; weights remain
borrowed and compressed. This removes the previous redundant compute without
changing the independent kernel's arithmetic.

The real-model owner again passed three complete 248,320-element F32 logits
rows at each of 31, 200 and 330 prompt tokens, with maximum absolute error
`1.90734863e-6` against mode `0`, exact greedy/rendered output and all 252
state-plane hashes per case. The short/wider/short retained session matched.
Mode `2` was refused with empty output. Forced submit and completion failures
left ordinary requests working and made selected requests fail without output
or token publication, worker exit 2. `make build` passed with the real CUDA
shim, and `make fmt` passed.

An Nsight Systems three-token node trace counted three native `project`
launches and **zero ggml Q6_K output projection launches** in mode `1`;
the native project's median device interval was `890.491 us` and native Q8_1
conversion was `1.280 us`. A separate three-count Q6_K row-gather operation
still occurs elsewhere in the graph; it is not the removed output projection.
The GPU interval is close to the duplicated trial's `887.484 us`, consistent
with the unchanged kernel. Nsight Compute counters are still denied by
`ERR_NVGPUCTRPERM`, so memory-transaction and occupancy causes remain
unmeasured. The profile is `q6-nonduplicate-trace.nsys-rep` outside Git.

The same five alternating warm request pairs used the digest-bound model,
backend and pinned llama.cpp described above. All outputs matched. The
ordinary/native pair executes in retained sessions; each llama.cpp sample is
its third warmed iteration in a fresh process. Times are milliseconds:

| Prompt/output | Pair | Ordinary Align | Native Q6_K | Pinned llama.cpp |
| --- | ---: | ---: | ---: | ---: |
| 56/16 | 0 | 87.101 | 103.029 | 95.927 |
| 56/16 | 1 | 76.056 | 80.354 | 90.486 |
| 56/16 | 2 | 74.495 | 73.825 | 87.671 |
| 56/16 | 3 | 73.138 | 73.942 | 86.540 |
| 56/16 | 4 | 72.151 | 99.736 | 88.357 |
| 200/32 | 0 | 163.332 | 159.320 | 178.903 |
| 200/32 | 1 | 158.209 | 168.646 | 171.565 |
| 200/32 | 2 | 162.083 | 159.317 | 168.879 |
| 200/32 | 3 | 164.269 | 161.927 | 169.249 |
| 200/32 | 4 | 170.560 | 162.146 | 174.040 |
| 330/64 | 0 | 314.904 | 314.497 | 328.154 |
| 330/64 | 1 | 316.016 | 305.641 | 337.118 |
| 330/64 | 2 | 306.973 | 306.837 | 323.212 |
| 330/64 | 3 | 313.001 | 317.722 | 335.263 |
| 330/64 | 4 | 313.181 | 317.702 | 328.173 |

Median paired native gain over ordinary Align was `-4.298`, `+2.766` and
`+0.136 ms`, with 1/5, 4/5 and 3/5 wins. Median gain over pinned llama.cpp
was `+10.132`, `+9.562` and `+16.375 ms`, with 3/5, 5/5 and 5/5 wins. The
56/16 series has large outliers, and the other two ordinary gains are small;
this does not establish a general win over either reference. Full stdout is
`q6-nonduplicate-measure.stdout` outside Git.

To isolate the change from the first connected native version, two resident
sessions used the preserved checkpoint binary/shim and the new binary/shim,
both with mode `1`. Each condition had two matching-output warmups, then five
alternating-order pairs. The paired native gain medians were `+9.357 ms`
(3/5) at 56/16, `+14.351 ms` (5/5) at 200/32 and `+74.555 ms` (5/5) at
330/64. The short series includes a `-25.185 ms` outlier, so its median is
less certain. The longer cases show a useful connected improvement over our
own prior implementation. All 15 pair values are retained in
`q6-duplicate-vs-nonduplicate.stdout` outside Git:

| Prompt/output | Pair | Duplicated native | Nonduplicated native |
| --- | ---: | ---: | ---: |
| 56/16 | 0 | 96.717 | 101.123 |
| 56/16 | 1 | 88.780 | 79.423 |
| 56/16 | 2 | 88.798 | 73.484 |
| 56/16 | 3 | 89.382 | 73.663 |
| 56/16 | 4 | 91.476 | 116.662 |
| 200/32 | 0 | 201.361 | 167.175 |
| 200/32 | 1 | 191.365 | 175.547 |
| 200/32 | 2 | 190.436 | 176.085 |
| 200/32 | 3 | 198.503 | 192.180 |
| 200/32 | 4 | 192.056 | 186.984 |
| 330/64 | 0 | 377.311 | 307.784 |
| 330/64 | 1 | 398.159 | 316.163 |
| 330/64 | 2 | 388.193 | 307.116 |
| 330/64 | 3 | 389.838 | 315.283 |
| 330/64 | 4 | 381.278 | 311.031 |

NVIDIA's current [CUDA Best Practices Guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
prioritizes coalesced global reads and warns that more occupancy does not
automatically improve throughput. Its
[stream synchronization guide](https://docs.nvidia.com/cuda/cuda-programming-guide/03-advanced/advanced-host-programming.html)
recommends explicit event dependencies when work crosses streams. These guide
the next hypotheses; neither proves a bottleneck here without device counters.
The next trial should measure the now nonduplicated request's Q4_0 and Q6_K
cost, then test one bounded kernel or scheduling change at a time against
this native baseline, ordinary Align and the pinned reference. Keep failed
experiments and generated-binary comparisons in this log.

The comprehensive review of `51f67aa` found two connected-accounting defects:
removing the ggml output node also removed one counted model operation, and
the helper's 995,584 device bytes were missing from admission and the reported
peak. The repair counts the off-graph projection, reserves the helper bytes in
Align before admission, includes them in shim budget/observation totals, and
allocates the helper only after a successful admission. The CUDA source
statically checks the actual scratch/output sizes against the reservation.
The extended real-model diagnostic found equal ordinary/native cumulative
model-operation totals (`2058` after three graph executions in each case).
At the 8,000,000,000-byte configured budget, selected-mode planned/allocated/
peak bytes were respectively `8,000,000,000/1,281,449,088/1,281,449,088`
for 31 tokens, `8,000,000,000/1,296,387,200/1,296,387,200` for 200, and
`8,000,000,000/1,308,101,760/1,308,101,760` for 330. A separate local
near-admission probe found ordinary mode succeeded at a 1,809,499,739-byte
budget while selected mode refused before generation; this threshold is
specific to the pinned fixture, current ggml allocator and host, not a
portable constant. The full-logit/state/retained owner and forced
submit/completion faults passed again after the repair. The measured speed
pairs above precede this accounting-only repair. Fresh uninstrumented pairs
on the repaired binary provide the final local speed evidence below.

The repaired binary beat the preserved duplicated native checkpoint in all
15 alternating warm-request pairs, with median gains of `14.453`, `33.427`
and `68.092 ms` at 56/16, 200/32 and 330/64. Both arms stayed resident and
outputs matched; the previous binary and shim were preserved from checkpoint
`8d0828f`. The complete `q6-repair-vs-duplicate.stdout` receipt is outside Git:

| Prompt/output | Pair | Duplicated native | Repaired nonduplicated native |
| --- | ---: | ---: | ---: |
| 56/16 | 0 | 97.262 | 80.508 |
| 56/16 | 1 | 89.330 | 74.877 |
| 56/16 | 2 | 89.287 | 73.505 |
| 56/16 | 3 | 88.898 | 88.713 |
| 56/16 | 4 | 89.955 | 84.748 |
| 200/32 | 0 | 197.197 | 163.770 |
| 200/32 | 1 | 196.153 | 159.239 |
| 200/32 | 2 | 192.037 | 158.277 |
| 200/32 | 3 | 200.333 | 167.179 |
| 200/32 | 4 | 190.117 | 175.900 |
| 330/64 | 0 | 372.283 | 310.167 |
| 330/64 | 1 | 379.947 | 309.502 |
| 330/64 | 2 | 368.114 | 318.861 |
| 330/64 | 3 | 375.125 | 307.032 |
| 330/64 | 4 | 377.074 | 307.342 |

The fresh ordinary Align and pinned llama.cpp campaign used the same
digest-bound model, backend, executable and exact prompts/output counts as
the preceding campaign. Repaired native lost to ordinary Align by `0.705`,
`2.260` and `1.957 ms` paired median (0/5, 1/5, 2/5 native wins), but beat
the pinned llama.cpp warm generation interval by `15.506`, `10.259` and
`10.121 ms` (5/5 wins each). The comparison is scoped to this RTX 4070 Ti,
Qwen3.5-2B Q4_0, three workloads and warm retained requests; it does not
establish startup, other-model or general llama.cpp superiority. The
complete `q6-repair-ordinary-llama.stdout` receipt is outside Git:

| Prompt/output | Pair | Ordinary Align | Repaired native | Pinned llama.cpp |
| --- | ---: | ---: | ---: | ---: |
| 56/16 | 0 | 82.534 | 83.211 | 90.931 |
| 56/16 | 1 | 73.016 | 73.720 | 89.226 |
| 56/16 | 2 | 71.774 | 72.462 | 88.660 |
| 56/16 | 3 | 73.362 | 86.509 | 89.771 |
| 56/16 | 4 | 72.888 | 77.560 | 123.131 |
| 200/32 | 0 | 164.673 | 166.933 | 172.994 |
| 200/32 | 1 | 156.766 | 162.356 | 166.364 |
| 200/32 | 2 | 155.991 | 157.812 | 171.367 |
| 200/32 | 3 | 167.049 | 158.444 | 168.704 |
| 200/32 | 4 | 156.644 | 172.948 | 185.763 |
| 330/64 | 0 | 316.680 | 322.624 | 332.746 |
| 330/64 | 1 | 315.171 | 310.886 | 327.984 |
| 330/64 | 2 | 304.047 | 320.422 | 320.712 |
| 330/64 | 3 | 312.624 | 314.581 | 337.740 |
| 330/64 | 4 | 322.261 | 319.660 | 321.456 |

## Q4_0 cache-pressure qualification and withdrawn mappings (2026-09-30)

The real 200/32 request's 6144-row fused Q4 gate/up instances average
34.229 microseconds, versus about 8.64 in the small repeatedly cached native
screen. The existing independent FFN owner now accepts developer-only
`ALIGN_CUDA_Q4_CACHE_PRESSURE=0|1`, default `0`. Mode `1` touches a separate
128 MiB buffer with explicit uint4 global stores and waits before each arm;
both arms receive identical pressure, excluded from the completed-FFN timer.
The RTX 4070 Ti reports 48 MiB L2, so this exceeds twice its capacity.
This is a cache-pressure diagnostic, not a proven cache-state reset or a
replica of all model layers. Graphs and weight copies are unchanged, with no
allocation in timed work. Other devices require their own qualification.

Synthetic and actual complete intermediate/final rows pass the existing
finite bound, including the captured gated/down rows. Default and pressure
synthetic owners pass (`1.49012e-8` gated error, exact down); pressure actual
error is `1.78814e-6` gated and `9.53674e-7` down. Selectors `2`, `01` and
empty refuse before path resolution/compilation/device initialization;
shell syntax and diff checks pass. The public runner is the reproduction
path, with the same explicit pinned source/library/plugin and capture inputs
already recorded above, prefixed by `ALIGN_CUDA_Q4_CACHE_PRESSURE=1`.

The unchanged aligned-load helper SHA-256 is
`2b55714179b3dc8d6e98d7b4d531d68c9d09c28943bb75227f10f1a25beb46a3`.
Two pressure ggml/native campaigns give paired median gains of 7.038 and
6.396 microseconds, 3/5 and 4/5 wins. All pairs below are completed local
FFNs, milliseconds, with 12 warmups and twenty operations per pair.

| Run | Pair | ggml ms | Native ms |
| --- | --- | --- | --- |
| 1 | 0 | 0.111509 | 0.127721 |
| 1 | 1 | 0.128254 | 0.101331 |
| 1 | 2 | 0.107582 | 0.100544 |
| 1 | 3 | 0.128914 | 0.101374 |
| 1 | 4 | 0.105150 | 0.105521 |
| 2 | 0 | 0.131433 | 0.118315 |
| 2 | 1 | 0.109039 | 0.106589 |
| 2 | 2 | 0.119425 | 0.134733 |
| 2 | 3 | 0.140388 | 0.110313 |
| 2 | 4 | 0.106649 | 0.100253 |

A separate pressure Nsight trace contains 112 instances per matrix kernel
and 224 pressure kernels. Native gate/up averages 41.834 us versus ggml
42.319 us; native down averages 31.898 us versus ggml 21.484 us. Native
activation quantization averages 1.203 us versus ggml 2.467 us. These
instrumented intervals do not establish uninstrumented request speed or
DRAM throughput; hardware counters remain denied. The down penalty and
variable wall samples prevent treating the cached screen as a model win.

Three predeclared standalone variants were screened against the same
digest-identified preceding helper in one process. Every complete gated/down
row passes; all three are withdrawn, leaving the helper byte-identical.

| Variant | Pair | Preceding ms | Variant ms | Condition |
| --- | --- | --- | --- | --- |
| One warp per gate/up row | 0 | 0.107457 | 0.108261 | Pressure |
| One warp per gate/up row | 1 | 0.138989 | 0.115477 | Pressure |
| One warp per gate/up row | 2 | 0.113621 | 0.107399 | Pressure |
| One warp per gate/up row | 3 | 0.103380 | 0.114373 | Pressure |
| One warp per gate/up row | 4 | 0.100828 | 0.099798 | Pressure |
| Streaming packed-payload loads | 0 | 0.124497 | 0.108741 | Pressure |
| Streaming packed-payload loads | 1 | 0.108965 | 0.117698 | Pressure |
| Streaming packed-payload loads | 2 | 0.151193 | 0.122904 | Pressure |
| Streaming packed-payload loads | 3 | 0.123640 | 0.139632 | Pressure |
| Streaming packed-payload loads | 4 | 0.111290 | 0.117504 | Pressure |
| Two rows, whole Q4 blocks for down | 0 | 0.109020 | 0.131061 | Pressure |
| Two rows, whole Q4 blocks for down | 1 | 0.114124 | 0.139848 | Pressure |
| Two rows, whole Q4 blocks for down | 2 | 0.098893 | 0.105214 | Pressure |
| Two rows, whole Q4 blocks for down | 3 | 0.103986 | 0.111470 | Pressure |
| Two rows, whole Q4 blocks for down | 4 | 0.106204 | 0.105390 | Pressure |
| Two rows, whole Q4 blocks for down | 0 | 0.038531 | 0.038425 | Cached |
| Two rows, whole Q4 blocks for down | 1 | 0.044425 | 0.046110 | Cached |
| Two rows, whole Q4 blocks for down | 2 | 0.046572 | 0.044481 | Cached |
| Two rows, whole Q4 blocks for down | 3 | 0.044155 | 0.043371 | Cached |
| Two rows, whole Q4 blocks for down | 4 | 0.046041 | 0.045818 | Cached |

Pressure paired median gains are +1.030/-6.214/-7.484 us, with 3/5, 2/5
and 1/5 wins; the whole-block variant's cached gain is only +0.223 us.
Variant source digests are respectively
`6edb776d8510863da5f62a2f06356a482b3ad1007bf7062621b605b44ca3ad11`,
`eaa6b1903e76ac517da1c585744ba1f6e76db22b98f934dd943449884e99a950` and
`2fa09b71a03a7aca906598e3feeaf504a7b66700aaea6f0cb54b46c614f3e706`.
Raw sources, logs and traces remain outside Git. These are failed local
screens, not reproducible adopted kernel changes. The checked-in pressure
owner makes the useful workload distinction repeatable.

The bounded outcome is to retain the current kernel and request route. The
remaining small mapping/cache-hint changes have no demonstrated useful gain.
Larger weight repacking or a native FFN/residual/norm/head execution unit
remains a separate hypothesis requiring explicit cost, ownership and complete
request/state/failure evidence. A final-layer-only connection cannot multiply
its local gain by all 24 layers. Other models/GPUs and full DRAM counters are
explicitly deferred until available; no new Align gap was encountered.

## Withdrawn connected FFN/residual/norm/head execution unit (2026-09-30)

The larger trial moved the final scalar layer's attention residual, learned
RMS normalization, Q4 gate/up/SwiGLU/down and residual, head normalization,
Q6 projection and greedy reduction into one native CUDA Graph. Align kept
model construction and explicit selection. The ggml prefix expanded the
raw final-layer input and attention result; it did not execute the removed
FFN/head again. Multirow prefill kept the existing ggml FFN/native head.
The trial added exactly 58,368 explicit device bytes: 41,984 Q4 scratch/output
and two 8,192-byte rows, totaling 1,061,720 with the existing head. CUDA graph
driver bookkeeping was not claimed as an exact accounted byte count.

**Withdrawn:** repeated whole-request comparisons did not beat the preceding
native greedy-head route. Its existing performance is retained, with no new
flag, ABI, helper or test in active `src/` or `scripts/`. The complete tested
experiment is preserved in commit
`460eb4d3f5b3edae78dae2e6716c73a002e95666`. That snapshot is a historical
experiment, not an adopted performance improvement or a supported new mode.
The user requested stopping after this PR; no next experiment is active.

Three uninstrumented campaigns used RTX 4070 Ti, CUDA 13.3 and driver 610,
the same authenticated 2B Q4_0 model and pinned ggml bundle as above.
Each case had five alternating pairs and twenty completed requests per
Align arm per pair. Each cell below is the arithmetic mean of those twenty
requests in milliseconds; gain summaries use the median of five paired
mean differences. Every nanosecond sample is retained outside Git. Each
campaign contains 900 timed Align requests, totaling 2,700. All output text,
actual prompt/completion counts and repeated outputs matched. The pinned
llama.cpp arm contributes one warm generation interval per pair, following
two warmups; it excludes model loading and text detokenization. Align's
clock includes the retained worker round trip. These are named warm-request
metrics, not startup, HTTP/SSE, time-to-passing-patch or general backend
superiority claims.

The preserved greedy-head executable SHA256 is
`5b474ca53c23881cc9c876df5cc0497e4007ffd84a020a3eff5912a989df9574`;
its shim is
`58bbf96330a59c362b8287ad81a4c4952e687c9c2790cae2d3da870f930560a4`.
The measurement checked both digests and the actual loaded Linux shim
path/device/inode before timing. The final cache candidate executable is
`d6976aa3de3d0dd066c8f75aa4480efbbb1254769b4cd11b77a9df4209ea9355`,
and its shim is
`341f2a8fdedacb4048c4a726486a0fc02f30c27077b290acc425f9b3ef8b8cbe`.
The model, plugin, reference executable and pinned source identities remain
those recorded earlier in this document; none changed between the arms.

The first campaign was encouraging, but its gains did not survive repeats.
The second campaign used the same scalar arithmetic after excluding failed
last-row prefill; the third also cached CUDA pointer validation. Replay
checked exact pointer/epsilon identities, with owner extents checked at
commit and every native graph destroyed before workspace release. That
removed repeated attribute queries without changing device math. This
revision still lost to the preceding head, so it was also withdrawn.

| Campaign | Prompt/output | Gain vs preceding head (ms) | Wins | Gain vs ordinary Align (ms) | Wins | Gain vs llama.cpp (ms) | Wins |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial | 56/16 | +0.057 | 4/5 | +2.381 | 5/5 | +19.480 | 5/5 |
| Initial | 200/32 | +3.897 | 4/5 | +1.576 | 4/5 | +11.062 | 5/5 |
| Initial | 330/64 | +3.673 | 4/5 | +4.999 | 5/5 | +14.283 | 5/5 |
| Repeat | 56/16 | −1.692 | 1/5 | +0.185 | 3/5 | +13.393 | 5/5 |
| Repeat | 200/32 | +3.646 | 3/5 | +2.524 | 4/5 | +3.589 | 5/5 |
| Repeat | 330/64 | −1.296 | 1/5 | +1.668 | 3/5 | +17.726 | 5/5 |
| Cached validation | 56/16 | −2.066 | 1/5 | +0.074 | 3/5 | +15.700 | 5/5 |
| Cached validation | 200/32 | −5.918 | 2/5 | +1.675 | 3/5 | +8.787 | 5/5 |
| Cached validation | 330/64 | −4.976 | 1/5 | +3.457 | 4/5 | +15.181 | 5/5 |

Positive is control minus candidate. The comparison with ordinary Align or
llama.cpp does not establish added value over the already retained native
head. Timing variation is substantial, and no exact causal split of the
request regression is claimed.

Initial campaign, all pairs:

| Prompt/output | Pair | Ordinary Align | Connected tail | Preceding head | Pinned llama.cpp |
| --- | ---: | ---: | ---: | ---: | ---: |
| 56/16 | 0 | 73.934 | 73.765 | 72.853 | 87.719 |
| 56/16 | 1 | 73.170 | 70.154 | 70.175 | 95.051 |
| 56/16 | 2 | 72.325 | 69.944 | 70.001 | 94.188 |
| 56/16 | 3 | 73.009 | 69.947 | 70.221 | 86.063 |
| 56/16 | 4 | 72.352 | 70.680 | 71.702 | 90.160 |
| 200/32 | 0 | 159.676 | 164.539 | 157.066 | 169.061 |
| 200/32 | 1 | 158.810 | 158.193 | 163.998 | 175.284 |
| 200/32 | 2 | 158.179 | 156.410 | 162.705 | 167.472 |
| 200/32 | 3 | 157.587 | 155.026 | 158.923 | 171.358 |
| 200/32 | 4 | 157.143 | 155.568 | 157.138 | 166.164 |
| 330/64 | 0 | 306.516 | 300.357 | 303.917 | 326.560 |
| 330/64 | 1 | 308.657 | 304.265 | 309.014 | 317.993 |
| 330/64 | 2 | 309.007 | 308.331 | 297.328 | 322.614 |
| 330/64 | 3 | 319.011 | 304.100 | 308.982 | 317.850 |
| 330/64 | 4 | 307.650 | 302.651 | 306.324 | 318.560 |

Repeat campaign, all pairs:

| Prompt/output | Pair | Ordinary Align | Connected tail | Preceding head | Pinned llama.cpp |
| --- | ---: | ---: | ---: | ---: | ---: |
| 56/16 | 0 | 75.203 | 78.710 | 76.024 | 92.118 |
| 56/16 | 1 | 77.610 | 76.737 | 71.645 | 86.651 |
| 56/16 | 2 | 73.295 | 73.110 | 71.532 | 86.503 |
| 56/16 | 3 | 73.269 | 74.089 | 72.397 | 86.740 |
| 56/16 | 4 | 75.119 | 72.146 | 72.607 | 99.068 |
| 200/32 | 0 | 163.307 | 159.928 | 163.574 | 167.667 |
| 200/32 | 1 | 160.908 | 158.384 | 164.701 | 166.984 |
| 200/32 | 2 | 163.865 | 167.125 | 159.680 | 168.196 |
| 200/32 | 3 | 168.901 | 164.368 | 169.861 | 165.196 |
| 200/32 | 4 | 168.791 | 168.282 | 165.927 | 171.870 |
| 330/64 | 0 | 315.099 | 315.579 | 310.527 | 329.143 |
| 330/64 | 1 | 314.724 | 309.814 | 308.788 | 329.070 |
| 330/64 | 2 | 313.942 | 312.274 | 310.978 | 330.000 |
| 330/64 | 3 | 314.238 | 315.959 | 312.711 | 325.729 |
| 330/64 | 4 | 313.789 | 308.247 | 309.525 | 327.558 |

Cached-validation campaign, all pairs:

| Prompt/output | Pair | Ordinary Align | Connected tail | Preceding head | Pinned llama.cpp |
| --- | ---: | ---: | ---: | ---: | ---: |
| 56/16 | 0 | 76.376 | 77.345 | 75.082 | 100.013 |
| 56/16 | 1 | 75.991 | 76.727 | 71.708 | 90.596 |
| 56/16 | 2 | 73.172 | 73.098 | 71.667 | 88.798 |
| 56/16 | 3 | 76.739 | 73.652 | 71.586 | 88.655 |
| 56/16 | 4 | 73.494 | 72.633 | 73.419 | 90.080 |
| 200/32 | 0 | 165.924 | 168.807 | 158.065 | 174.073 |
| 200/32 | 1 | 167.570 | 165.895 | 159.977 | 170.563 |
| 200/32 | 2 | 162.311 | 163.990 | 157.847 | 172.778 |
| 200/32 | 3 | 168.530 | 158.749 | 162.285 | 171.958 |
| 200/32 | 4 | 167.995 | 160.256 | 165.897 | 175.706 |
| 330/64 | 0 | 311.937 | 316.012 | 307.905 | 324.869 |
| 330/64 | 1 | 310.988 | 308.863 | 305.578 | 323.226 |
| 330/64 | 2 | 318.498 | 310.521 | 305.545 | 334.420 |
| 330/64 | 3 | 315.473 | 305.898 | 310.895 | 326.581 |
| 330/64 | 4 | 318.606 | 315.149 | 310.078 | 330.329 |

The raw receipt SHA256 values are:

| Receipt | SHA256 |
| --- | --- |
| `requests.log` | `54736438b81a5a9bd0642894dc4657ca76cbdf2bb0f9303a163ffc389527fe98` |
| `requests-final.log` | `8ed1efbefda58ade35c6a2978a40a1b55ca235681e9d6ec71d711fea94a0baeb` |
| `requests-cache.log` | `79abeb6ddf1db241acf83063b1b5385f60ebd5f48df0554a35cf7b1fbfd53827` |

The final scalar owner passed three full vocabulary rows and 252 exact state
planes for each 31/200/330-token prompt, retained short/wider/short requests,
nine registration challenges per decode graph, five malformed/conflicting
selections, insufficient device budget and forced submit/completion/greedy
failures. Ordinary control remained usable under each fault; selected workers
returned failure without output and exited 2. All scalar logits satisfy the
unchanged 0.01 absolute bound; maximum observed error was 1.90734863e-6.
Cumulative model-operation credit matched ordinary Align at 2,058. At the
8,000,000,000-byte device budget, selected allocated/observed-peak bytes were
1,281,515,224, 1,296,453,336 and 1,308,167,896 respectively. Those are explicit
shim observations, not a claim to account for every opaque driver allocation.

The kernel owner also passed a scalar reference for learned normalization
and residual addition, all three graph kinds, capture/replay, changed-pointer
and epsilon refusal, all-kind reset/reconstruction, ties and stale/nonfinite
read rejection. The Q4 standalone full-row owner and a paired build against
the same source passed with the new borrowed-stream exports renamed in the
baseline object. `make build`, `make fmt`, Python boundary, shell syntax and
diff checks passed for the experiment. None of these tests adopts the route.

A wider optional prefill trial using the existing last-FFN-row selection
failed its full-logit owner: the first offending value was 12.9820556640625
ordinary versus 12.994684219360352 native, a 0.0126285553 difference. Matching
pinned RMS reduction order and fast division did not remove that failure;
both variants were discarded. The final snapshot refuses that combination
before admission. Its precise numeric cause remains unresolved; the bound
was not loosened. The existing plain native head with last-row prefill passed
all three real-model cases independently.

Separate node-level Nsight traces requested 32 tokens for `hello ` repeated
170 times. Both actually returned the same 18 visible tokens plus EOG after
19 projections; this is a 200-token trace with 18 scalar decode tails, not the
200/32 timing workload. Tail trace: 18 native gate/up, 18 native down, 36
native residual/norm and 19 native Q6/reducer executions, with exactly 19
eight-byte D2H copies. The preceding-head trace also has 19 projections and
copies. Its final FFN nodes disappear from the prefix; the corresponding
native nodes execute once. Native gate/up/down medians were 35.186/17.857 us,
versus 35.0265/17.857 us for the preceding graph's final FFN. Device kernel
superiority was not established. The tail trace has three additional native
graph instantiations, consistent with reset/reconstruction of shared ggml
workspace. These instrumented cold traces do not measure warm lifecycle cost
or explain the whole request regression. Hardware counters remain denied on
this host, and other GPUs/models remain unmeasured.

Reproduction requires the archived source. Publication must preserve
`460eb4d` as an ancestor by using a merge commit; squash or rebase that drops
that source checkpoint is unsupported. Verify the final merging head with
`git merge-base --is-ancestor 460eb4d3f5b3edae78dae2e6716c73a002e95666 HEAD`.
Prepare a detached worktree at that commit, use the pinned managed Align
compiler and the authenticated model/bundle inputs already named above,
then run:

```sh
ALIGN_LLM_NATIVE_CUDA=1 \
  ALIGN_LLM_GGML_INCLUDE="$GGML_SOURCE/ggml/include" \
  ALIGN_LLM_GGML_LIB="$GGML_LIB" ALIGN_LLM_GGML_SHIM_DIR="$TRIAL_SHIM" make build
scripts/run-native-cuda-q6-greedy-test
QWEN35_NATIVE_FFN_TAIL=1 scripts/run-qwen35-native-q6-head-smoke
QWEN35_CUDA_MEASURE_MODE=ffn-tail QWEN35_CUDA_PAIR_REQUESTS=20 \
  scripts/measure-qwen35-native-cuda
```

Compile `scripts/trace-qwen35-state.c` from the same archived worktree for the
full-row/registration owner. Set its `QWEN35_STATE_TRACE`, real
`QWEN35_NATIVE_Q6_BINARY`/`QWEN35_NATIVE_COPY_BINARY`, existing authenticated
model/pack/geometry/options variables, pinned llama benchmark/source/digest,
and the preceding binary/shim paths and digests shown above. Do not rebuild
or overwrite either loaded shim during a campaign. Forced fault builds use
`ALIGN_LLM_GGML_FORCE=native-q6-submit|native-q6-complete|native-q6-greedy` in
separate shim directories, `LD_PRELOAD` that shim, and the corresponding
`QWEN35_NATIVE_Q6_FAILURE=submit|complete|greedy` owner selector. Node traces
require `--cuda-graph-trace=node`; aggregate graph traces do not expose the
captured kernels and cannot prove per-node counts.

The bounded lesson is that connecting this final tail into one graph was
numerically qualified for the tested scalar requests, but neither its device
FFN nor complete request beat the preceding route repeatably. A future attempt
needs a separately measured kernel/layout or persistent-workspace hypothesis
before broader integration. No final-layer gain is multiplied by 24, and no
new permanent gate or follow-up task is introduced by this failed screen.

## 2026-10-01: preimplementation investigation

The user requested planning, preparatory work and design, without implementing
another optimization. Source baseline is `687acd3`, containing the withdrawal
of the final FFN tail. The authoritative
[next-experiment design](specs/gpu-runtime-performance.md#cuda-next-experiment-design-2026-10-01)
owns the candidate order, byte layout, proposed diagnostic interface, cost
ceiling, numerical conditions and future owner matrix. No candidate kernel,
selector, model route or new request benchmark was implemented or run here.

### Findings that change the next experiment

- Lossless scale/payload separation is untried in the checked-in **CUDA**
  helper, but was already tried on Metal. The
  [Metal receipt](qwen35-q4-layout-screen.md) reports no stable split-layout
  gain when rotating 24 actual gate matrices, and 40.75 ms CPU conversion.
  That result supplies a negative control, not CUDA conversion cost. The
  CUDA-specific mechanism to test is wider loads with unchanged DP4A/lane
  arithmetic. Three early-layer down matrices are Q4_1; a Q4_0 specialization
  cannot be applied indiscriminately to every FFN.
- The current five-argument CUDA benchmark passes the same weight pointers
  to both native arms. Cached paired runs can favor the second reader. R1
  therefore specifies disjoint native weights and a raw/raw control before
  judging repacking. Existing historical samples are preserved; the pressure
  diagnostic still does not guarantee identical cache state.
- In pinned ggml, `ggml/src/ggml-backend.cpp:ggml_backend_graph_compute`
  calls the asynchronous entrypoint then synchronizes. The application calls
  this function before `align_gpu_native_q6_head_commit`. Public
  `ggml-backend.h` has asynchronous compute and backend-event operations;
  `ggml-cuda.h` has no native stream/event accessor. `ggml_backend_event_wait`
  accepts another ggml backend, not the independent helper's CUDA stream.
  Removing the wait requires a designed backend bridge; swapping the compute
  call alone would allow a producer/consumer race. This is application/backend
  integration work, not an identified Align language or standard-library gap.
- The 417,177,600-byte head and recorded 894.782 us imply 466.23 GB/s of
  useful weight bytes per second. The 504 GB/s specification gives an
  827.73 us full-read estimate. These are calculations from old measurements,
  not new counters or a hard latency floor. The 48 MiB cache, other transfers
  and scheduling prevent treating the difference as an exact speedup budget.

### Rebuilt baseline instruction evidence

Compile-only inspection on the RTX 4070 Ti host used CUDA 13.3.73, sm_89,
`-O3 -std=c++17`, and unchanged helper SHA-256
`2b55714179b3dc8d6e98d7b4d531d68c9d09c28943bb75227f10f1a25beb46a3`.
The local GPU identity query reports driver 610.62; it is not a controlled
clock measurement. No GPU workload was executed for this inspection.

| Kernel | Registers/thread | Stack / spill load / spill store bytes | Static global load instruction sites |
| --- | ---: | --- | --- |
| `gate_up_swiglu` | 40 | 0 / 0 / 0 | 18 `LDG.E.U16`, 9 `LDG.E` |
| `down_matvec` | 26 | 0 / 0 / 0 | 5 `LDG.E.U16`, 5 `LDG.E` |
| `quantize_q81` | 19 | 0 / 0 / 0 | 1 `LDG.E` |

The counts are static SASS sites, not dynamic executed instructions or DRAM
transactions. Neither matrix kernel has a 64/128-bit global load in this
object. Replacing its payload loads is plausible; throughput improvement is
unmeasured. The object SHA-256 is
`90a8107ea53515ad66f2c6ac59321a4d9e49da64a093b1ea48c0c2cc6c3507c1` and
the SASS dump SHA-256 is
`868965669b9d4992a977d207bb88984a83394b8c79cb565e869bd9b481a27d35`.
Compiler-generated symbol names/object digests can change with compiler or
build-path details; the reproduction contract is the source/flags and observed
instruction properties. Raw outputs remain outside Git.

Reproduce from the unchanged helper, with `OUT` an external evidence directory:

```sh
nvcc -O3 -std=c++17 -gencode arch=compute_89,code=sm_89 -Xptxas=-v \
  -c scripts/native_cuda_q40_ffn.cu -o "$OUT/q4-baseline.o" 2> "$OUT/ptxas.log"
cuobjdump --dump-sass "$OUT/q4-baseline.o" > "$OUT/q4-baseline.sass"
```

Nsight Compute's last recorded attempt remains `ERR_NVGPUCTRPERM`; permission
was not changed or retried during this design task. NVIDIA's
[WSL requirements](https://docs.nvidia.com/nsight-compute/ReleaseNotes/topics/system-requirements.html)
place counter access in the Windows host control panel. The source review,
compile-only inspection and future bounded numerical screen do not depend on
obtaining counters. The design contains the first experiment and explicit
deferrals; implementation requires the user to resume it.

## 2026-10-01: CUDA Q4 split-layout implementation

The user explicitly resumed implementation after the design checkpoint. R1
now provides a complete diagnostic consumer: lossless host packing, raw/split
CUDA graphs, disjoint preceding-control weights, full numerical owners,
failure/recovery qualification and identity-bound measurements. The
[contract ledger](specs/gpu-runtime-performance.md#r1-diagnostic-contract-ledger)
owns its interface and limits. Runtime integration is **not selected**: the
cached improvement did not establish a dependable pressure benefit, and the
pressure GPU kernel intervals did not improve. This is not a generation-speed
or coding-time claim. No new Align gap or Python change was required.

### D0 preserved cold-request analysis

Classification corrected by the later warm-request investigation below: the
binary was preserved, but this trace is a one-shot provider invocation,
including cold setup. It is not a warmed retained-session request.

Read-only analysis of the retained greedy-head `prefetched-200x32.sqlite`
(SHA-256 `9e83c1eb113df60f67352263b8b4b91a9b2b4ffbbf896d2d88cd7a657d16325a`)
finds 32 native head quantizations and 32 eight-byte D2H copies. After the
first head, the last dependent ggml RMS-norm producer to native quantization
gap has min/median/max **40.258/52.803/111.556 us** over 31 scalar steps.
The first head's gap is 3,855.417 us and includes initial setup; it is not
steady-state synchronization headroom.

Before the first head, summed kernel intervals are 17.610 ms within an
80.803 ms first-to-last-kernel envelope. From the first head through the last
kernel, the corresponding numbers are 110.309/223.746 ms, covering 32 heads
and 31 scalar forward steps. Q4_0 matvec and native Q6 projection account for
53.990/28.633 ms of that kernel sum. Large decode copies include 558 each
of 73,728 and 1,048,576 bytes, taking 2.166/0.790 ms in summed intervals.
Two ggml graph instantiations, two updates and 28 graph launches occur after
the first head. Runtime API durations overlap GPU intervals; these numbers
must not be added to make a request latency estimate.

The roughly 53 us producer/consumer interval originally nominated R2 as a next
design target; the later warm-request investigation supersedes that priority.
It also includes host dispatch/setup, so eliminating a wait cannot
be assumed to recover the entire interval. The pinned public API still lacks
a stream/event bridge to this independent helper. An asynchronous-call swap
would race; the bridge and its failure/lifetime owner remain deferred.

### Representation, compiler and correctness

The helper uses split-v1's unchanged 21,233,664 weight bytes, the existing
41,984 scratch bytes and the same four kernels, DP4A arithmetic and lane
mapping. All captured gate/up/down bytes reconstruct exactly and every device
upload is read back and compared. The packing self-check covers all 65,536
half-scale bit patterns, including signed zeros and NaNs, without numerically
interpreting them. Corrupted payload or scale bytes are rejected.

CUDA 13.3.73, `-O3 -std=c++17`, sm_89, RTX 4070 Ti/driver 610.62:

| Kernel/layout | Registers | Static loads: U16 / 32 / 64 / 128 bits | Stack/spill bytes |
| --- | ---: | --- | --- |
| Raw gate/up | 40 | 18 / 9 / 0 / 0 | 0 / 0 / 0 |
| Split gate/up | 32 | 2 / 9 / 0 / 2 | 0 / 0 / 0 |
| Raw down | 26 | 5 / 5 / 0 / 0 | 0 / 0 / 0 |
| Split down | 40 | 7 / 35 / 7 / 0 | 0 / 0 / 0 |
| Q8 quantizer | 19 | 0 / 1 / 0 / 0 | 0 / 0 / 0 |

These counts come from the exact candidate object retained by the runner.
The split down loop is compiler-unrolled, so static counts are not directly
comparable to the raw loop's dynamic instruction count. The initial two
stdout summaries mistakenly counted `.64` address operands as 64-bit loads;
the owner was corrected to inspect the instruction opcode. The retained SASS
and subsequent summaries above are authoritative.

All 6,144 gated and 2,048 down values pass the unchanged finite mixed bound
against captured and same-pin ggml rows. Actual maximum absolute errors are
`1.78814e-6`/`9.53674e-7`; synthetic errors are `1.49012e-8`/`0`.
All paired actual raw/raw and raw/split rows are also **F32 bit-identical**
to the preceding native source, before timing and after every pair.

Normal helper SHA-256:
`3303e3330865261a5ef31d7d1995189884ddf6ffda39960fb57ae319d189b2dd`.
Control helper is the source at `687acd3`, SHA-256
`2b55714179b3dc8d6e98d7b4d531d68c9d09c28943bb75227f10f1a25beb46a3`.
ggml is clean `bb4caa7540188872173c44d161602d9271386413`; loaded plugin/base/
ggml hashes are `ec1ddd96247a97ba6f2a564301efca6a1e9b479f29b6bdb9d166ead2bbb4f774`,
`58fe11fee93a0cf48e22af07d462fe9f2a2ef64272cf8d3c39af3093a7ddbfe0` and
`b47b7760ba3a08aa2cc50cdfb718996eaa59a68e8961ccbb00becf119ad577e4`.
Each run records compiler, source/header/benchmark/runner, capture, object,
SASS and executable hashes and verifies loaded canonical path/device/inode.
The build's temporary path affects compiler-generated namespace/object hashes;
source, flags and the retained measured object identify each campaign.

### Completed-operation measurements

Each uninstrumented campaign uses 12 warmups and five alternating pairs of
20 synchronized complete FFNs. Numbers below are microseconds; each cell is
`preceding raw / candidate`. Positive median paired gain favors the candidate.
Pressure stores 128 MiB outside both timers, versus the reported 48 MiB L2;
this remains a diagnostic rather than proof of identical cache state.

| Actual campaign | Pair 0 | Pair 1 | Pair 2 | Pair 3 | Pair 4 | Median paired gain / wins |
| --- | --- | --- | --- | --- | --- | --- |
| Raw/raw cached | 40.070/40.682 | 39.482/40.577 | 41.818/40.150 | 44.412/43.300 | 41.232/40.491 | +0.741; 3/5 |
| Raw/raw pressure | 112.577/126.528 | 101.771/133.285 | 103.153/101.599 | 108.529/123.722 | 103.662/101.832 | -13.951; 2/5 |
| Raw/raw pressure repeat | 107.054/139.306 | 108.398/109.073 | 104.893/133.201 | 136.397/106.913 | 111.131/107.379 | -0.675; 2/5 |
| Final raw/raw cached | 41.412/40.581 | 45.479/49.442 | 41.283/41.155 | 40.274/40.231 | 38.157/38.142 | +0.042; 4/5 |
| Final raw/raw pressure | 109.532/121.282 | 98.765/100.229 | 122.183/107.069 | 99.725/99.613 | 108.178/105.332 | +0.112; 3/5 |
| Raw/split cached | 42.623/40.081 | 40.480/37.239 | 41.207/38.128 | 60.735/45.078 | 50.696/47.159 | +3.241; 5/5 |
| Raw/split cached repeat | 38.610/35.642 | 39.613/36.747 | 40.174/36.989 | 41.557/38.912 | 40.698/37.927 | +2.866; 5/5 |
| Final raw/split cached | 41.275/37.291 | 61.395/53.901 | 74.616/74.666 | 99.470/85.752 | 132.939/75.132 | +7.493; 4/5 |
| Raw/split pressure | 107.923/102.787 | 119.328/101.051 | 107.341/135.785 | 100.749/103.953 | 122.552/103.908 | +5.136; 3/5 |
| Raw/split pressure repeat | 106.904/122.086 | 123.071/100.405 | 101.467/100.762 | 131.496/107.205 | 101.254/102.003 | +0.704; 3/5 |
| Retained-build raw/split pressure | 100.637/132.538 | 98.709/97.939 | 105.281/106.368 | 103.976/103.474 | 118.678/103.389 | +0.502; 3/5 |
| Final raw/split pressure | 110.037/105.260 | 115.104/134.865 | 104.634/103.952 | 141.694/112.670 | 109.919/110.013 | +0.682; 3/5 |

Final raw/raw controls are near zero, but the earlier -13.951 us pressure
control and the final cached outliers show substantial wall-time uncertainty.
No cause was established for that variation. The initial cached repeats are
encouraging; pressure savings near 0.5-0.7 us and 3/5 wins do not establish a
request benefit. The actual split/ggml pressure comparison has pairs
110.744/103.864, 103.992/125.855, 101.863/97.597, 115.426/111.291,
127.757/143.581 us, median paired gain +4.135 us, 3/5 wins; the independent
pooled medians are 110.744/111.291 us. It also fails to establish superiority.
Synthetic cached raw/split and pressure owners pass; their timing is not
used to override the actual-weight result.

In the retained paired pressure trace, the last 100 instances per arm are
the timed operations. Raw/split median gate/up intervals are
**41.778/41.954 us**, down **21.889/21.953 us**. Split gate/up has one
412.693 us outlier; its mean is 45.757 us versus raw 41.977 us. No faster
pressure-conditioned GPU operation is demonstrated. Trace SQLite SHA-256 is
`275eb3477ca4b3344aefda7ebf97f4736d695a0131fe9fe526f7610da550fb1c`.
Instrumented wall timings are excluded from the adoption assessment.

One bounded explanatory check disables down-loop unrolling in an external
candidate: registers fall from 40 to 23, with unchanged rows, but its pressure
pairs are 136.369/118.510, 139.649/112.813, 107.485/107.096,
112.514/135.429, 111.248/110.409 us, median paired gain +0.839 us, 4/5 wins.
This does not resolve the pressure uncertainty; the pragma is not retained.
No warp/cache-hint sweep follows.

Packing plus inverse verification takes approximately 9-12 ms for all three
matrices in these owners. Candidate and control upload and verification are
reported separately by the final harness. First graph capture/launch/wait is
also reported, outside the steady-state pairs. Ordinary complete runner
invocations took 4-8 s in the first campaign, below the 900 s preparation and
120 s owner ceilings. There is no reliable pressure saving to amortize against;
no model break-even point is claimed. Diagnostic cached savings cannot be
multiplied by layer count or treated as TTFT/startup improvement.

### Failure owners and reproduction

Both `ALIGN_CUDA_Q4_TEST_FAILURES=1` builds pass all twelve forced operations,
including partial acquisition, capture/instantiate, first/replay launch and
completion, and both output-copy failures. Failed contexts refuse further
run/read; a fresh context recovers full correct rows. All four changed
dependency pointers refuse without launch, stale read refuses, and valid
replay restores readiness. Premature read preserves caller sentinels; wrong
counts/null outputs refuse. Normal timing objects exclude fault state/branches.
Compute Sanitizer `--tool memcheck --leak-check full --error-exitcode 1` on
the retained split failure build reports **0 errors, 0 bytes/allocations leaked**.

Empty/unknown layout, pressure and failure selectors, arity, missing paths,
wrong source revision/control digest, loader preloads, invalid artifact
destinations, schema/length/completion failures and injected compiler exit
all refuse before device work or timing verdict. Both wrong expected-library
and wrong loaded-library paths refuse; normal identity checks pass.
`bash -n scripts/run-native-cuda-q4-ffn-screen` and `git diff --check` pass.
No source aggregate, Python boundary or platform-publication profile is
selected for this local diagnostic checkpoint.

Use the exact commands and variables in the
[ledger reproduction](specs/gpu-runtime-performance.md#work-sequence-and-closure).
`RAW_SOURCE` is obtained with
`git show 687acd3:scripts/native_cuda_q40_ffn.cu > "$OUT/raw-baseline.cu"`.
The runner refuses any other baseline digest. Preserve one build with
`ALIGN_CUDA_Q4_SCREEN_OUTPUT="$OUT/build"`; the direct retained executable
supports the same selectors plus the runner's internal library-directory
binding. Profile that executable, not the injection-refusing Bash runner.
Raw captures, builds, traces and per-run stdout/stderr remain outside Git.

One fresh comprehensive implementation review covered the entire eight-file
candidate at HEAD/base/merge-base `687acd3312220742ad013595951e0d8c5b966e16`,
patch SHA-256 `44c2720a36dd34308db464c3580fd5ff32ddb1d9217b08fc9186b72b83364807`,
reviewer `/root/cuda_repack_implementation_review`, verdict **FINDINGS**.
Its sole P2 finding is accepted and repaired: the mapping filter skipped
ordinary canonical `.so.0.21.0` targets behind SONAME symlinks. It now
recognizes the canonical expected target and other versioned candidates while
still requiring exact canonical path/device/inode. The versioned symlink
full-row owner and wrong expected/loaded identity owners in both directions
pass; the regular-file full-row owner also passes. The two receipt median
rounding corrections copy the original printed medians. No finding is rejected
or unresolved. The consolidated repair changes identity admission/reporting
only; kernel, timed execution and adoption assessment are unchanged, so another
full review is not required. Full envelope and raw repair owners are retained
outside Git. No commit, publication/preflight or hosted integration is claimed.

The positive compatibility owner creates `.so -> .so.0 -> .so.0.21.0`
links for byte-identical ggml/base copies in an external directory and runs
the same five-argument screen with that directory and a copied CUDA plugin.
Run the loaded-library negative owner with this versioned directory and the
ordinary directory alternately as expected and actual loader locations; both
must refuse. This is the focused regression owner for mapping-filter changes,
not a new aggregate gate.

The bounded lesson is that wider payload loads and a cached win did not
establish a useful pressure-conditioned GPU improvement. Disjoint raw/raw
controls exposed wall-time variance before adoption. Canonical dependency
identity must support the pinned build's normal symlink topology; the repaired
owner covers that topology while retaining wrong-file refusal.

## 2026-10-01 warm-request bottleneck investigation

The user requested bottleneck work beyond kernels, explicitly stopping before
implementation. This checkpoint only inspects source, executes preserved
binaries/settings and records a plan. No optimization, default, kernel, or
checked-in measurement code changed. The preceding R1 implementation remains
intentional uncommitted work. The
[request-bottleneck plan](specs/gpu-runtime-performance.md#cuda-request-bottleneck-plan-2026-10-01)
is authoritative for the new priority, prospective cost/ownership and owners.

### Inputs and reproducibility

Host: RTX 4070 Ti/sm_89, driver 610.62, CUDA 13.3.73, WSL2,
Nsight Systems 2026.1.3. No clock lock or isolation from desktop activity;
hardware counters remain unavailable under the recorded Windows-host permission
constraint. Application source/base is `687acd3`, ggml/llama pin is
`bb4caa7540188872173c44d161602d9271386413`. This is not a comparison against
current upstream llama.cpp or a time-to-passing-patch measurement.

Preserved greedy-head executable SHA-256:
`5b474ca53c23881cc9c876df5cc0497e4007ffd84a020a3eff5912a989df9574`;
its shim: `58bbf96330a59c362b8287ad81a4c4952e687c9c2790cae2d3da870f930560a4`.
Each timed session checks the actual shim mapping's path/device/inode and file
hash. Model SHA-256 is
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`;
Alignpack is `b4b418ebef9f83f911e4d604bdcce03e589fb7d2afa35f7e3bbdff3111b810b1`.
Geometry/options and source bundle libraries are recorded in the external
`input-identities.json`; the CUDA plugin remains
`ec1ddd96247a97ba6f2a564301efca6a1e9b479f29b6bdb9d166ead2bbb4f774`.

External evidence bundle: `bottleneck-plan-20261001`, alongside the earlier
native CUDA evidence. Its drivers are independent `BENCHMARK_OR_MEASUREMENT`
artifacts using the existing `gpu_session_client.Session` and measurement
request/identity functions; they contain no model inference or product policy.
The NVTX shim only brackets caller requests. Key evidence digests:

| Artifact | SHA-256 |
| --- | --- |
| `profile_retained.py` | `1abbfc4e9805891922360eeb820ae832fc265e30e0a8a05e5822ae636e65c6eb` |
| `screen_serial.py` | `efd3c450013ae1b637a47684ebb87dd2a393e86f126cdf5d239e4523ab99ebbe` |
| `retained-200x32.sqlite` | `ab58fc5c4c9263ff2d66c72a4050e648464cff7e935b94682beab232d49301d3` |
| `chunk-serial.jsonl` | `5905ff7abcd739575757410d3ce1e2bbc9bc40fea087400c5519170ea332c883` |
| `llama-200x32.sqlite` | `e94b88a32022d77a166282dd2a075dba611df92c2d9069fe242edf048445942f` |

Use the retained scripts with their explicit local artifact bindings, or rebind
them to the same authenticated files. `EVIDENCE` is this external directory:

```sh
g++ -shared -fPIC -O2 -I/usr/local/cuda/include "$EVIDENCE/mark.cc" -o "$EVIDENCE/mark.so" -ldl
PROFILE_LABEL=unprofiled python3 "$EVIDENCE/profile_retained.py"
PROFILE_LABEL=trace nsys profile --trace=cuda,nvtx,osrt --sample=process-tree \
  --backtrace=dwarf --cuda-graph-trace=node -o "$EVIDENCE/retained-200x32" \
  python3 "$EVIDENCE/profile_retained.py"
nsys export --type=sqlite --output="$EVIDENCE/retained-200x32.sqlite" \
  "$EVIDENCE/retained-200x32.nsys-rep"
python3 "$EVIDENCE/analyze.py"
python3 "$EVIDENCE/screen_serial.py"
```

Use fresh output names when reproducing. The worker command is the preserved
binary's `--runtime-session MODEL PACK GEOMETRY OPTIONS 0`, with native Q6 head
enabled and other native copy modes disabled. Requests are the existing
measurement cases, temperature zero. NVTX wraps two warmups followed by three
200/32 requests; model loading has a separate range. The serial setting screen
uses five pairs, reversing 128/512 process order each pair, with two warmups and
five timed requests per case/arm. Only one GPU session is alive at once. All
150 timed requests and 60 warmups match their case's text/counts. No logits or
state dump is enabled during timing.

### Warm critical path

The three NVTX request wall intervals are 163.116/190.343/191.052 ms. A separate
uninstrumented three-request probe gives 181.566/158.269/158.124 ms, so trace
wall times are attribution, not adoption evidence. For every warm trace:
zero graph instantiations/updates, 31 decode graph launches and 32 native
heads/eight-byte readbacks. The 12.4 ms graph-instantiation cost in the earlier
D0 cold trace therefore cannot be counted as recurring overhead.

| Per 200/32 request | Request 0 | Request 1 | Request 2 |
| --- | ---: | ---: | ---: |
| Before first native head: wall, ms | 33.011 | 60.323 | 51.243 |
| Same phase: union of GPU kernels/copies/memsets, ms | 16.987 | 16.442 | 16.407 |
| First head through response: wall, ms | 130.105 | 130.019 | 139.809 |
| Same phase: GPU activity union, ms | 111.984 | 110.450 | 111.805 |
| Completed choice to next backbone start, sum over 31, ms | 9.588 | 9.215 | 12.499 |
| Last backbone producer to next head, sum over 31, ms | 1.804 | 2.171 | 2.108 |
| Same producer/head gap, median us | 52.644 | 53.091 | 58.628 |

The last two rows describe different boundaries. Source inspection explains
four per-token input updates: token, four positions, mask, KV index.
`align_gpu_input_update` calls `ggml_backend_tensor_set`; pinned CUDA implements
each as memcpy on its per-thread stream followed by stream synchronization.
Clipping API intervals to the choice-to-backbone windows gives
1.191/1.340/1.877 ms memcpy and 3.805/3.447/4.723 ms synchronization time.
These subsets overlap their containing windows and must not be added again.
One batch-completion barrier can target part of this cost without changing the
separate ggml-to-native output-head dependency.

Before the first head there are 1,955 individual `cudaLaunchKernel` calls in
each warm request. `execute` reconstructs each prefill graph; prepare and
invalidate rebuild the shared allocator. Every warm request has four CUDA
malloc/free pairs. CPU sampling reaches ggml graph allocation/fusion checks,
but the samples do not give a precise exclusive CPU budget. Mask building,
tokenization and JSON/framing cannot be blamed for every uncovered interval.
Caller wall minus the worker's elapsed field is only 0.354–0.407 ms in the
three traces; this bounds the additional measured caller/protocol envelope,
not all tokenizer/detokenizer work inside the worker.

The apparent approximately 31 ms `cudaMemcpyAsync` time for 32 eight-byte
readbacks includes waiting for the producer on the pageable D2H path; actual
GPU copy time is about 0.030 ms. It is not a 31 ms copying opportunity.
Likewise a graph-launch correlation is shared by its nodes: joining every
graph copy to the launch and summing that API duplicates launch time.

### Existing prefill setting screen

This is a configuration-only diagnostic on the unchanged executable. No
environment/default is persisted. Values below are medians of the five
per-arm five-request means; gains are paired control minus candidate.

| Actual prompt/output | Chunk 128, ms | Chunk 512, ms | Median paired saving, ms | Wins |
| --- | ---: | ---: | ---: | --- |
| 56/16 | 76.613 | 73.136 | 3.708 | 4/5 |
| 200/32 | 163.618 | 142.395 | 21.223 | 5/5 |
| 330/64 | 303.672 | 276.845 | 26.827 | 5/5 |

Every paired saving in ms:

- 56/16: `3.784647, 3.708101, 6.740874, 1.554805, -4.042609`.
- 200/32: `16.612661, 21.222929, 18.387149, 25.180235, 22.316955`.
- 330/64: `26.826989, 30.777278, 29.822579, 19.446588, 25.629105`.

Middle/wider arm medians are 12.97%/8.83% shorter than the same campaign's
chunk-128 control. Both execute one prefill chunk at 512 instead of two/three;
the short workload still has one, so its small noisy difference is not
evidence for chunk reduction. The mechanism remains a combination of host
preparation, workspace lifetime and GPU shape changes. Output equality does
not establish full-state/numeric parity, first-use cost or broader adoption.

A separate pinned llama benchmark, executable SHA-256
`0aabc02758cf34b086d253d6b164cb6027a2aa2188b17fd66c42f483e608ae29`,
ran three 200/32 iterations under node-level CUDA tracing, without CPU sampling.
Its final warm iteration is 176.787 ms (18.660 prefill, 158.126 decode), with
32 IDs and decoded output matching the native request. This is not a paired
performance campaign and must not replace the preceding saved comparison.
Reproduction: `nsys profile --trace=cuda --sample=none --cpuctxsw=none
--cuda-graph-trace=node -o OUT LLAMA_BENCH MODEL RENDERED_PROMPT IDS 32`.
The existing `prepare_reference` function produced the 200 input IDs.

### Limits, failures and next boundary

The initial multi-session chunk screen stopped during second-session admission
with code 2 and produced no timing verdict. A subsequent isolated chunk-256
probe passed and returned the expected 200/32 output. The completed campaign
therefore runs arms serially; the failed admission does not show that chunk
256 is unsupported. Its exact cause was not diagnosed.

The optional chunk-512 trace later failed when the filesystem reached `ENOSPC`;
partial files are excluded from the evidence. Its stalled profiler was stopped.
Only that run's own unmapped temporary backend bundle was removed; existing
models, source and successful receipts were preserved. At that checkpoint,
external scratch/evidence capacity was a prerequisite for retrying. The later
authorized cleanup and successful additional traces below close that blocker.
The partial trace remains excluded; a second uninstrumented campaign is still open.

The next action is B0 qualification of the existing setting, then B1's bounded
synchronous input batch. Prefill workspace reuse is conditional on the remaining
profile; the output-head bridge moves below these candidates. No new Align gap
was found. The reusable lesson is to separate warm request phases and test
existing execution settings before selecting another kernel experiment.
This documentation checkpoint has an author consistency/diff check only; the
earlier R1 comprehensive review does not cover this new plan. No publication,
merge, implementation or new whole-request adoption claim is made.

### Additional traces after authorized disk cleanup

The user explicitly requested freeing disk space and completing the additional
trace. The sibling Align checkout's ignored Cargo `target/debug/incremental`
cache was removed after confirming no compiler/build process was active.
Source, compiler executables, models, managed toolchains and existing receipts
were preserved. Measured available space increased from 176,214,016 to
5,588,570,112 bytes, freeing **5,412,356,096 bytes (5.41 GB / 5.04 GiB)**.
This was bounded cache cleanup, not deletion of arbitrary temporary directories.
The external `cleanup-receipt.json` records the operation.

The unchanged `profile_chunk.py` first ran chunk 512, then a fresh chunk-128
control, serially with the same CUDA/NVTX/OSRT/DWARF/node tracing options.
Both completed two warmups and three measured 200/32 requests. All ten output
texts/counts match the preceding native/reference result; actual shim mapping
identity is checked in each process. The partial earlier profile was not reused.
New evidence in `bottleneck-plan-20261001`:

| Artifact | SHA-256 |
| --- | --- |
| `profile_chunk.py` | `f25e077b4d5c46713b4ef16251606468c8255b6926a840bbc17c13e9c8ef7faf` |
| `analyze_retry.py` | `a2aba8e60c29e820885dc98e5325089ece42360f6e00a9f2ed37351383179eaf` |
| `chunk512-retry-200x32.sqlite` | `603f876eab1adcf6f9150f7b74e8a22c011a097e8c22e98cb3e7e13f998e446d` |
| `chunk128-retry-200x32.sqlite` | `bb704936598c7a8529e4b1da1553cab488cbfe62907c3fa609628ac8c3912028` |

The `.nsys-rep`, profiler stdout, worker stderr/maps, phase JSON and
`retry-boundaries.json` are retained alongside these files. Reproduce with
fresh output names, using the same external evidence directory and bindings:

```sh
for prefill_chunk in 512 128; do
  SCREEN_CHUNK="$prefill_chunk" PROFILE_LABEL="chunk${prefill_chunk}-retry" \
    nsys profile --trace=cuda,nvtx,osrt --sample=process-tree --backtrace=dwarf \
    --cuda-graph-trace=node --force-overwrite=false \
    -o "$EVIDENCE/chunk${prefill_chunk}-retry-200x32" \
    python3 "$EVIDENCE/profile_chunk.py"
  nsys export --type=sqlite \
    --output="$EVIDENCE/chunk${prefill_chunk}-retry-200x32.sqlite" \
    "$EVIDENCE/chunk${prefill_chunk}-retry-200x32.nsys-rep"
  python3 "$EVIDENCE/analyze_retry.py" "chunk${prefill_chunk}-retry-200x32"
done
python3 "$EVIDENCE/summarize_retry.py"
```

All three post-warmup samples are reported, including the first chunk-512
capture; the last two are separately identified as replay observations.
Times below are instrumented phase attribution, not a new speedup campaign.

| Chunk / request | Request wall, ms | Before first head, ms | Same phase GPU activity union, ms | Individual launch API calls before head | Prefill graph launches / instantiations |
| --- | ---: | ---: | ---: | ---: | --- |
| 128 / 0 | 165.861 | 34.793 | 16.333 | 1,955 | 0 / 0 |
| 128 / 1 | 176.500 | 44.117 | 16.412 | 1,954 | 0 / 0 |
| 128 / 2 | 183.134 | 37.351 | 16.790 | 1,955 | 0 / 0 |
| 512 / 0, first capture | 161.837 | 31.000 | 13.168 | 996 | 1 / 1 |
| 512 / 1, replay | 146.308 | 16.156 | 12.580 | 4 | 1 / 0 |
| 512 / 2, replay | 150.298 | 16.724 | 12.582 | 2 | 1 / 0 |

Chunk 128 executes **1,951 prefill GPU kernels**, all individually launched;
chunk 512 executes **992 prefill GPU kernels**, all in its captured graph
in the three measured requests. API counts include ancillary launch calls
and, during capture, node construction; they are not device kernel counts.
Matrix kernels fall from 367 to 186 and recurrent kernels from 36 to 18,
consistent with two prompt chunks becoming one. Full-request CUDA malloc/free
pairs fall from four to two. These observations establish fewer GPU operations,
less allocation churn and prefill graph replay as mechanisms behind the earlier
setting screen; they do not assign every saved millisecond to one mechanism.

The first chunk-512 prefill instantiation takes **8.086 ms** and occurs in the
third caller request despite two warmups. Its first cold request is also slower
than the control in these instrumented runs (362.413 versus 268.918 ms).
Keep cold/first-use cost separate and do not silently discard the capture
sample. Pinned ggml only enables capture after stable graph properties; source
inspection corroborates delayed capture, but allocator-address changes were
not independently traced.

The new control also corrects any generalization from the first trace's zero
warm graph updates. Its third request performs **two decode recaptures/updates**,
29 graph launches and 2,508 individual launch API calls in the decode-tail phase,
versus 31 graph launches and 124/125 individual calls in the first two requests.
There is no new decode instantiation. Shared-workspace rebuilding is a plausible
cause of unstable properties, not a proven pointer-level attribution. All three
chunk-512 decode tails retain 31 graph launches and zero recaptures/updates.

After chunk-512 capture, pre-head time uncovered by GPU activity is only
3.577/4.142 ms in the two replay samples. Decode choice-to-next-backbone
windows still total 9.577/9.200/11.636 ms, of which memcpy/synchronization
API intersections occupy 4.807/4.552/5.127 ms. Thus B0 qualification remains
first, B1 input completion batching remains the first new-code candidate, and
new prefill caching is conditional on measured varied-shape misses. The existing
backend already replays this same-shape prefill graph.

No optimization implementation or default change was made. Full-logit/state,
varied-shape, first-use/memory qualification and a repeat uninstrumented campaign
remain required before adopting the setting. The disk blocker and additional
trace are complete; the historical incomplete profile is retained as excluded
failure evidence. Documentation consistency/digest checks and `git diff --check`
pass; source hashes remain those of the earlier R1 checkpoint.

## 2026-10-01 synchronous CUDA decode-input batch

The user explicitly resumed implementation. B0's existing chunk-512 setting
fails its numeric gate: the 31-token owner has identical full logits/valid state,
but at 200 tokens logit 0 is 11.1827116013 with chunk 128 and 11.2366828918
with chunk 512. The 0.0539712906 difference exceeds the unchanged 0.01 bound.
The diagnostic stops at that failure; no wider-prompt state qualification,
boundary campaign or B0 adoption is claimed. B1 therefore uses chunk 128.

B1 is connected to ordinary and streaming Qwen3.5 scalar decode behind
`ALIGN_LLM_BATCH_DECODE_INPUTS=0|1`, absent = 0. Align writes a reused session
payload, then borrows immutable views through the new synchronous batch ABI.
The shim validates every descriptor, accounting and dependent row position
before any transfer, queues the four unchanged uploads on the existing backend
stream, waits once, and only then accepts row metadata/accounting. Recoverable
post-submit faults drain and poison the owner. ggml's void/fatal CUDA API does
not supply a recoverable hardware-error status. The additional host buffers total
9,368 bytes at maximum mask width; native descriptors occupy 320 stack bytes.
There is no extra explicit device allocation or new timed buffer allocation.
The non-blocking borrowed-resource/scratch limitation is the already-recorded
Align Request 121; the pin is unchanged and no proposed surface is consumed.

The external evidence bundle is `input-batch-20261001` beside the preserved
Qwen3.5 inputs. It contains `inputs.env`, source/binary/shim identities, every
raw paired request, both mapping receipts, full owner logs, native traces,
SQLite reducers and the B0 failure witness. No generated artifact enters Git.
Source/base is `687acd3312220742ad013595951e0d8c5b966e16`; Align pin is
`b20429be50d6ab889496a0589143320683b29aeb`. Model, pack, IR, CUDA plugin and
llama reference retain the authenticated identities from the preceding receipt.

| Artifact | SHA-256 |
| --- | --- |
| Candidate `main` | `80210ab545e720f342bb570ab430578c06f2202c541107a293c54acf314a3fab` |
| Candidate shim | `a9f52ffacb76d94574881e07f68cb08f6bf4bd3a7a687384a8564f414d14e2a0` |
| Submit-failure shim | `69084d1fc28f2c5b7802676d40a5c44d58beaa2d0927ef7effb8cc5a4aceaa87` |
| Completion-failure shim | `e1934aa90084a839a4c10b5fdda4dccdc5ab9fccef7b10a470ab2b8053d868af` |
| Batch-off SQLite | `7c9ae51bad5e7ffef4eea3de87782b3842c8dfe07a64efb9d2eb2348f9c21698` |
| Batch-on SQLite | `1148b9c5cf0107fe53acdf5cc9e55384b0151ae870f49e985a55f390d085bec0` |

Build with the authenticated pinned `ggml/include`, library directory, and
`ALIGN_LLM_NATIVE_CUDA=1`, setting an external `ALIGN_LLM_GGML_SHIM_DIR`, then
`make build`. Qualification commands and results:

- `make check`: PASS, 169 per-unit modules; the narrow generation owner also
  passes 38 units. `make fmt`, shell syntax, Python syntax, Python boundary and
  `git diff --check` pass. No broad aggregate or publication preflight is claimed.
- `scripts/run-gpu-input-batch-smoke GGML_SOURCE GGML_LIB GPU_PLUGIN`: all three
  real-GPU builds pass. Covers unaligned little-endian golden bytes, framing,
  signed/overflow/extent/duplicate/accounting refusals, malformed last records,
  dependent row positions, unchanged GPU bytes and metadata on refusal,
  1/4/8 transfers with one completion, post-submit/completion poison and cleanup.
- `QWEN35_INPUT_BATCH_OWNER=1 scripts/run-qwen35-native-q6-head-smoke`: PASS.
  All three complete logit vectors per 31/200/330/2048-token input are bit-identical;
  all 252/336/420/1,512 state planes match. Device peaks stay within 8 GB,
  reaching 1,289,242,328 bytes at the maximum mask. Default/off/on retained
  short/wide/short full logits/state, invalid-input recovery, single-token
  early exit, EOG, empty/unknown selectors and tight-budget refusal pass.
- Real-shim `ALIGN_LLM_GGML_FORCE=input-batch-submit` / `input-batch-complete`
  builds, preloaded for `QWEN35_INPUT_BATCH_FAILURE=submit` / `complete` with
  the same owner: disabled controls succeed, selected requests publish only
  the failed envelope and exit 2; diagnostics confirm the forced drain boundary.
- Submit-failure focused C owner under `compute-sanitizer --tool memcheck
  --leak-check full --error-exitcode 1`: zero errors, zero leaked bytes/allocations.
- `ALIGN_LLM_NATIVE_Q6_HEAD=1 ALIGN_LLM_PREFILL_CHUNK=128
  ALIGN_LLM_BATCH_DECODE_INPUTS=1 scripts/run-openai-serving-smoke`: pinned
  oracle parity, HTTP/SSE, refusals, disconnect/recovery and shutdown/restart pass.
  A separate ordinary-head, fixed-chunk-512 comparison has three bit-identical
  logits and 252 identical state planes; it does not qualify 128-versus-512.

An additional legacy `gpu_workspace_allocation_smoke.c` attempt aborts at its
F32 KV fixture admission on line 228, before exercising the changed input path.
Rebuilding it with the exact HEAD shim reproduces the same failure. It is
excluded from successful qualification and deferred as a pre-existing fixture
issue; the new focused batch owner and real-model owners are the B1 evidence.
No unrelated workspace/test repair was added.

### Complete retained request measurements

Two serial campaigns on RTX 4070 Ti / CUDA 13.3.73 / WSL2 use
`QWEN35_CUDA_MEASURE_MODE=input-batch QWEN35_CUDA_PAIR_REQUESTS=20
scripts/measure-qwen35-native-cuda` with the recorded inputs. Each case has two
warmup rounds: two batch-off, four batch-on and two preserved-binary requests,
then five alternating pairs; every arm/pair averages
20 requests and retains all individual samples, including outliers. The native
head is fixed on, chunk is fixed at 128, and only the batch selector changes
between same-binary arms. A third arm is the digest-bound preserved greedy-head
binary/shim. All three loaded mappings match path/device/inode/hash receipts.
There are 1,800 timed Align requests across both campaigns; all output/count
checks and the pinned llama comparisons pass. Campaign files span 196/195 s,
within the 900 s ceiling. No benchmark overlaps a compiler or another GPU owner.

The llama benchmark uses the same pin/model/prompt IDs and reports the third
warm prefill-plus-decode interval per pair, excluding model load and detokenization.
Align includes worker round trip and detokenization, excluding model load.
The clocks retain this established asymmetry. No new kernel-speed claim follows
from the whole-request comparison.

| Campaign; prompt/output | Batch off; on; preserved; llama median pair means (ms) | Median paired saving vs off (wins) | vs preserved (wins) | vs llama (wins) |
| --- | --- | --- | --- | --- |
| 1; 56/16 | 73.050; 71.646; 72.598; 92.471 | 1.198 (5/5) | 1.264 (5/5) | 20.618 (5/5) |
| 1; 200/32 | 160.108; 158.475; 158.873; 167.828 | 2.269 (4/5) | -0.056 (2/5) | 13.029 (5/5) |
| 1; 330/64 | 306.652; 300.262; 306.822; 323.330 | 6.390 (5/5) | 7.667 (4/5) | 23.585 (5/5) |
| 2; 56/16 | 72.427; 70.340; 71.587; 88.664 | 2.087 (5/5) | 1.561 (5/5) | 18.324 (5/5) |
| 2; 200/32 | 161.565; 154.773; 156.366; 167.030 | 5.996 (5/5) | 2.550 (5/5) | 12.009 (5/5) |
| 2; 330/64 | 302.823; 297.859; 305.329; 322.252 | 1.969 (4/5) | 5.906 (4/5) | 25.017 (5/5) |

Every paired off-minus-on saving in milliseconds, preserving pair order:

| Campaign/case | Five paired savings |
| --- | --- |
| 1 short | 3.298, 0.929, 4.525, 0.797, 1.198 |
| 1 chunked | 2.728, 3.348, 2.269, -1.224, 1.633 |
| 1 wider | 5.264, 7.978, 6.390, 9.316, 5.435 |
| 2 short | 2.490, 1.674, 2.511, 0.206, 2.087 |
| 2 chunked | 7.449, 7.778, 5.996, 3.100, 3.174 |
| 2 wider | 7.936, -0.475, 6.485, 1.969, 0.683 |

Raw previous/llama pairs and all 20-request vectors remain in both campaign logs
and `campaign-summary.json`. Llama pair times are printed to 0.001 ms; the
reducer's reconstructed llama differences inherit that rounding. The table uses
the original benchmark's printed median saving (20.618 ms for campaign 1 short),
rather than the reducer's rounded-pair reconstruction of 20.619 ms.
The same-binary mechanism improves all three paired
medians in both runs. Short/wide improvements also survive the preserved-binary
comparison; 200/32's incremental gain against that route is still uncertain.
Retain the qualified opt-in trial with default 0; do not claim uniform gains,
default adoption, other GPU/model qualification or all llama savings as B1 gains.

### Trace mechanism and retained first-use evidence

Serial `SCREEN_BATCH=0` / `1` runs use `profile_batch.py` with
`nsys profile --trace=cuda,nvtx,osrt --sample=process-tree --backtrace=dwarf
--cuda-graph-trace=node --force-overwrite=false`, then SQLite export. The driver
checks the exact candidate binary/shim mappings. All ten responses agree at
200/32, and both SQLite integrity checks pass. In each of three measured
requests, input transfers remain 124 with unchanged byte shapes (4/16/1024/4
per scalar step), while input completion waits become **124 to 31**.
Total decode-tail stream synchronizations become **192 to 99**, exactly 93 fewer.
The per-kernel name/count multisets match: 1,951 prefill and 18,604 decode-tail
kernels, 31 graph launches, zero measured instantiations/updates in both arms.
This confirms wait removal without changing arithmetic or replayed work; it
does not prove graph reuse is stable for all shapes/requests.

Choice-to-next-backbone window sums are 11.192/13.755/9.608 ms off and
10.096/8.226/8.812 ms on. Memcpy/synchronization API intersections occupy
6.019/6.502/4.251 ms off and 4.461/2.828/3.055 ms on. These are instrumented
opportunity measurements, not values to subtract from the uninstrumented benchmark.
Instrumented load takes 1,503/1,650 ms; first request takes 317.138/317.032 ms.
Both warmups and all subsequent requests are retained; first-use samples are
not silently replaced by steady-state timing. Hardware counters remain unavailable
under the previously recorded permission restriction; no unchanged retry was made.

Bounded retrospective: full-vector qualification rejected an attractive chunk
change that text parity missed. The completed batch trial removes the predicted
wait count, but host variation still dominates a small preserved-binary difference
at 200/32. B2 workspace retention and R2 stream bridging remain separate,
conditional work; neither is implemented in this capability.

One fresh independent comprehensive review of the stable B1 candidate found only
the two P3 receipt corrections above (warmup counts and original summary precision).
Both are accepted and corrected together. Code, owners, benchmark selections,
timing samples, ABI and adoption assessment are unchanged; no rerun or expanded
review is required for that documentation repair. The external review envelope
binds HEAD/base/merge base `687acd3` to candidate manifest SHA-256
`cf2c6f8079059ce123ede2b6e9c6d6785b465b772d38cb1bfc3557bc016433c9`, reviewer
`/root/cuda_input_batch_review`, complete findings/dispositions and final file
identities. No finding remains open. This is a local checkpoint, with no commit,
publication preflight, pull request or merge requested.

## 2026-10-01 post-B1 profile and next design

The user requested a fresh profile of remaining headroom and preparation through
the point before implementation. This checkpoint changes documentation only;
the preceding B1 and R1 source/artifact identities remain unchanged. It selects
the implementation-ready B2 retained-workspace contract in
`docs/specs/gpu-runtime-performance.md`, without implementing that contract.

### Subject, scope and reproducibility

Branch/head/base: `agent/cuda-q4-repack-plan` / `687acd3312220742ad013595951e0d8c5b966e16`.
Managed Align pin remains `b20429be50d6ab889496a0589143320683b29aeb`.
RTX 4070 Ti, CUDA 13.3.73, driver 610.62, WSL2 and Nsight Systems 2026.1.3;
Qwen3.5-2B Q4_0, pinned ggml `bb4caa7540188872173c44d161602d9271386413`.
The existing B1 artifact is the subject, not a rebuild:

| Identity | SHA-256 |
| --- | --- |
| B1 executable | `80210ab545e720f342bb570ab430578c06f2202c541107a293c54acf314a3fab` |
| B1 shim | `a9f52ffacb76d94574881e07f68cb08f6bf4bd3a7a687384a8564f414d14e2a0` |
| Loaded CUDA plugin | `ec1ddd96247a97ba6f2a564301efca6a1e9b479f29b6bdb9d166ead2bbb4f774` |
| GGUF | `cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1` |
| First accepted SQLite | `5d0b6cdc01604dea71e285590423adb8364e468884c6fbfdc1a133729f22f9a8` |
| Second accepted SQLite | `c7154e06323bbd642ab28492a4c9c984cbd95cb895d6fe40ef9178b72dca0448` |

External bundle `post-b1-profile-20261001` retains scripts, compiled diagnostic
interposers, every response, raw reports, SQLite, logs, loaded mappings and
`manifest.json`. The second trace's `plain-verified-loaded-identities.json`
verifies mapped path/device/inode/digest for the actual binary, shim and staged
backend artifacts while the worker is alive, including the plugin digest above.
The first trace and host diagnostic verify the loaded shim and executable, retain
maps, and use the same admitted bundle; they do not independently hash every staged
mapping. Model/pack/IR/options and unchanged B1/R1 source hashes are in the manifest.

The driver clears inherited `ALIGN_LLM_*` selections, then sets native Q6 head
and decode-input batch to 1, prefill chunk to 128, and state/conv/prefill-copy and
copy-greedy modes to 0. It uses the existing resident CUDA0 options with 4 GiB
host / 8,000,000,000-byte device ceilings and prefetch off. The system and integer
listing prompt are the existing measurement fixture. The fixed serial sequence is:

1. Three requests each at 56/16, 200/32, 330/64, 56/16, 200/32.
2. One four-output request each at 127/128/129, 255/256/257 and 511/512/513 inputs.
3. 2048/3, then 56/16 again.

All first uses and every repetition are retained. Rows 1/2 in each three-request
group are called repeated requests below; group row 0 is not silently discarded
from the raw data. This is not a steady-state paired speed campaign. Each capture
had a 180-second ceiling and a 1-GiB trace-storage ceiling; actual retained trace
storage is well below that and existing disk capacity sufficed without further
cache cleanup. After profiling, three unused plugin staging directories left by
the failed load attempts were verified against the original artifacts and removed,
recovering 511,184,208 bytes. `cleanup-receipt.json` retains the identities and
no-live-reference checks; models, original plugins and profiling evidence remain.

With `PROFILE_DIR` set to that external bundle, the completed commands are:

```sh
PROFILE_LABEL=baseline-1 python3 "$PROFILE_DIR/profile_shapes.py"
PROFILE_LABEL=baseline-2 python3 "$PROFILE_DIR/profile_shapes.py"
PROFILE_LABEL=plain nsys profile --trace=cuda,nvtx,osrt \
  --sample=process-tree --backtrace=dwarf --cuda-graph-trace=node \
  --force-overwrite=false --duration=180 --output="$PROFILE_DIR/plain" \
  python3 "$PROFILE_DIR/profile_shapes.py"
PROFILE_LABEL=plain-verified nsys profile --trace=cuda,nvtx,osrt \
  --sample=process-tree --backtrace=dwarf --cuda-graph-trace=node \
  --force-overwrite=false --duration=180 --output="$PROFILE_DIR/plain-verified" \
  python3 "$PROFILE_DIR/profile_shapes.py"
nsys export --type=sqlite --force-overwrite=false \
  --output="$PROFILE_DIR/plain.sqlite" "$PROFILE_DIR/plain.nsys-rep"
nsys export --type=sqlite --force-overwrite=false \
  --output="$PROFILE_DIR/plain-verified.sqlite" "$PROFILE_DIR/plain-verified.nsys-rep"
PROFILE_LABEL=clock-host LIFECYCLE=1 python3 "$PROFILE_DIR/profile_shapes.py"
TRACE_LABEL=plain-verified python3 "$PROFILE_DIR/reduce.py"
python3 "$PROFILE_DIR/reduce_cpu.py"
```

Stdout/stderr are retained in correspondingly named JSONL/driver logs. A replay
needs a fresh output destination/labels because reports must not be overwritten.
`lifecycle-clock.so` is built from retained `lifecycle-clock.c` using `cc -shared
-fPIC -O2 -Wall -Wextra -Werror -Wno-misleading-indentation -I "$GGML_SOURCE/ggml/include"
"$PROFILE_DIR/lifecycle-clock.c" -o "$PROFILE_DIR/lifecycle-clock.so" -ldl`;
it only times original prepare/invalidate/compute/zero calls and reads
graph pointer fingerprints and allocation counters. It performs no GPU computation,
allocator mutation or model readback. Its intervals come from a separate run and
must not be subtracted from or added to Nsight durations.

Both accepted SQLite integrity checks pass. Every one of the **130** successful
responses has the expected prompt/output counts and identical output for its
fixture across both baselines, both traces and the host diagnostic. This confirms
diagnostic behavior, not a new full-logit qualification; B1's previous exact
logit/state qualification remains applicable to its unchanged source/artifacts.

### Remaining cost and attribution

| Input/output | Repeated CUDA malloc/free pairs per request | Combined malloc/free API duration across the two traces | Separate host prepare + invalidate duration |
| --- | ---: | ---: | ---: |
| 56/16 | 2 | 1.282–1.432 ms | 2.416–3.026 ms |
| 200/32 | 4 | 2.355–2.734 ms | 4.556–4.830 ms |
| 330/64 | 6 | 3.648–3.925 ms | 6.945–7.432 ms |
| 2048/3; one per run, changed shape | 36 | 20.774 / 21.886 ms | 39.828 ms |

Prepare/invalidate includes allocator sizing, binding and waits as well as the
physical allocation calls. The columns overlap in purpose and were measured
separately; they are not additive savings. For 2048, 32 prepare/invalidate calls
belong to its 16 prefill chunks and four more to replacing the two decode shapes.

The C owner path confirms recurring capacity oscillation: the observable input +
workspace + native-head allocation drops to 3,310,040 bytes after every prefill
invalidation. At 200 tokens it grows to 13,730,008 for the full chunk, falls back,
then grows to 8,683,736 for the partial chunk and falls back again. It reaches
16,613,592 during the 2048 case. Retaining that high water can hold an additional
13,303,552 bytes between requests on this sequence; it is not zero-cost residency.
The proposal keeps this charged against admission and does not reserve the entire
multi-gigabyte workspace ceiling.

Repeated 200/32 requests have 1,951 pre-head kernels and only the 31 decode graph
launches. Repeated 330/64 has 2,880 pre-head kernels and 63 decode launches. In
both traces short prefill eventually captures/replays, while alternating chunks
keep prefill on individual launches. Changed-shape calls show decode recapture;
even the second short-return request in the first trace recaptures two graphs.
It is incorrect to require zero recaptures for all retained requests.

The pinned `ggml_cuda_graph_get_key` uses `cgraph->nodes[0]`; the update predicate
compares node properties, input data pointers/shapes/strides, and warmup requires
a consecutive unchanged invocation. `execute` and `stream_begin` use one prefill
context, invalidating it at every chunk and after the request. The host diagnostic
observes one stable prefill key address but two/three alternating pointer
fingerprints at 200/330, consistent with those differing topologies. This explains
why workspace retention alone cannot provide multi-chunk prefill graph replay.
No full prefill cache, graph UID override or ggml graph-policy patch is implemented.

Representative first-trace `chunk-2` decode spans 126.681 ms with 110.773 ms of
GPU-active interval union. Quantized matvec kernels sum to 60.970 ms and native
projection to 29.172 ms; the remaining kernels, copies and launch gaps also matter.
These figures use different aggregation boundaries and must not be summed into a
request-time decomposition. Repeated producer-to-head gaps total 1.666–2.222 ms
at 200/32 and 3.521–4.620 ms at 330/64 across the traces. They justify retaining
the stream-bridge hypothesis, with a smaller measured envelope than a prefill
rewrite and a separate backend-lifetime prerequisite.

Repeated 200/32 choice-to-next-backbone windows total 7.004–8.860 ms. One example
contains 1.036 ms of stream-synchronize API intersections, 1.128 ms of memcpy
intersections and 2.293 ms of graph-launch intersections. The full window is not
one removable input wait. CPU user-space samples resolve CUDA submission/wait,
allocator planning and graph preparation; many driver frames are unresolved or
have broken backtraces. CPU kernel stacks were refused at `perf_event_paranoid=2`.
No precise tokenizer/IPC percentage or universal CPU ceiling follows from this.

Both uninstrumented baselines remain fully retained, including load times of
4,720.529/1,158.341 ms and first requests of 223.524/190.322 ms. Repeated short,
chunked and wide request ranges are respectively 69.093–80.231, 148.940–184.780
and 289.590–303.536 ms. These are unchanged-binary baselines with retained noise,
not improvement measurements. No fresh llama.cpp speedup is claimed.

### Decision, limitations and verification

There is observed application/backend headroom; the evidence does not establish
that all remaining kernels are at a ceiling. Select B2's single-allocator capacity
retention first, including explicit accounting, output-generation validity,
drain/poison/cleanup and independent off/on qualification. Its contract, exact
planned entrypoints and owner matrix are in the performance specification.
Prefill topology retention follows only after profiling the resulting residual
cost; R2 stream bridging and fused input-plus-compute remain conditional.

Three attempted combined Nsight/interposer captures (`annotated`, `app`, `clock`)
abort during loading before any request completes. The first two terminate under
NVTX interposition; the third records `Expected shared object name, found a path
delimiter`. Their reports and diagnostics are preserved and excluded. Plain
Nsight succeeds twice; the separate C clock interposer succeeds. This is a
profiling-combination limitation, not evidence of a product failure or gain.
CUDA hardware counters still need the previously recorded Windows-host permission
change; the unchanged refusal was not retried and host security settings were not
changed.

Author verification: both trace integrity checks, complete request/graph count and
status assertions, five-run output/count comparison and unchanged product/source
identity checks pass. Documentation consistency, `git diff --check` and the Python
boundary guard are the checkpoint owners; source builds/tests and publication
preflight are not rerun for this documentation-only delta. The old workspace C
owner's F32 KV fixture failure is explained by its 64-byte budget versus the
pinned CUDA buffer's 128-byte alignment; it is not passing B2 evidence. Planned
retention owners must use backend-aligned allocation accounting from construction.

One fresh independent comprehensive review of this five-document checkpoint
found one P2 design issue and no measurement issue: existing native Q6 admission
can allocate its helper during dry planning, while finish/cancel resets the owner
without closing that helper. The accepted repair makes retain-mode dry planning
refuse native-helper combinations before side effects, covers both selection
orders and preserves cleanup ownership. The closure matrix now names finish,
cancel and partial-construction qualifications. This is a design correction;
the legacy mode 0 combination is unqualified, and no source fix is claimed here.
The reviewed candidate, complete finding, disposition and final file identities
are retained in `review-candidate.json`/`review-result.json`; the original evidence
manifest is preserved as `reviewed-evidence-manifest.json`. No finding remains open.

The useful lesson from this bounded investigation is to profile shape transitions
and first uses as well as warmed identical requests. The two successful traces
retain graph-capture variability, and source inspection distinguishes allocation
reuse from topology reuse. No additional permanent repository gate is introduced.

## 2026-10-01 B2 retained workspace implementation

The user authorized implementation of the reviewed post-B1 design. The retained
Qwen3.5 session now exposes `ALIGN_LLM_RETAIN_WORKSPACE=0|1`, absent = 0;
empty/unknown selections refuse before admission. Align admits mode 1 only on
CUDA, for ordinary and HTTP/SSE consumers. Head and decode-input batch selection
remain independent. No default change or publication is selected.

### Implementation and ownership

The native owner keeps its existing single gallocr across graph invalidation,
including the state with no prepared graphs. Rebuild still drains helpers,
clears workspace bindings, measures every live graph, checks the admitted budget,
reserves the actual topology and rebinds all live graphs. The larger retained
capacity is counted against admission. No second device arena, copied weights,
prefill cache or ggml patch is added.

A checked content generation invalidates all old results before rebind or compute;
only successful compute stamps the current graph. Failed/unprepared/stale reads,
including the cached slot fast path, refuse. Native-head readiness is cleared.
Graph execution/reuse counters retain their existing meaning. Device close frees
one allocator after draining. The mode-1 helper/dry-planning exclusion covers
both selection orders, defensive admission/reset refusal, finish/cancel and
partial construction, as settled by the design review.

The C owner adds **40 bytes** versus the preceding state layout, within the
64-byte scalar ceiling. The separate host diagnostic measures gallocr-owned
malloc usable extents using declarations extracted from the exact pinned source:
peak **524,432 bytes** in both arms; final **506,832 / 524,432 bytes** off/on.
This covers the allocator, hash/node/leaf arrays, virtual buffer and dynamic
allocator/chunks; it excludes backend-private CUDA/runtime host storage. It is
not an addition to the fixed metadata observation or an RSS decomposition.
`layout.json`, the probe and diagnostic source preserve the layout provenance.

### Qualification and replay

Branch/head/base remain `agent/cuda-q4-repack-plan` / `687acd3`; Align remains
`b20429be50d6ab889496a0589143320683b29aeb`, ggml
`bb4caa7540188872173c44d161602d9271386413`. Host, model and admitted budgets
are the same RTX 4070 Ti/Qwen3.5-2B Q4_0 subjects as the post-B1 profile.
External bundle `workspace-retain-20261001` preserves the exact prior working-tree
snapshot, B2 diff, source/artifact hashes, inputs, raw traces/responses and logs.

With `B2_DIR` set to that bundle and its authenticated `inputs.env` loaded, the
completed owners are:

```sh
make check
scripts/alignc check-per-unit src/runtime_qwen35_generation.align
make fmt
make build
WORKSPACE_RETAIN_NATIVE_SHIM="$B2_DIR/shim" \
  scripts/run-gpu-workspace-retention-smoke \
  "$QWEN35_LLAMA_SOURCE" "$ALIGN_LLM_GGML_LIB" "$GPU_PLUGIN"
QWEN35_WORKSPACE_RETAIN_OWNER=1 scripts/run-qwen35-native-q6-head-smoke
ALIGN_LLM_RETAIN_WORKSPACE=1 ALIGN_LLM_NATIVE_Q6_HEAD=1 \
  ALIGN_LLM_BATCH_DECODE_INPUTS=1 ALIGN_LLM_PREFILL_CHUNK=128 \
  scripts/run-openai-serving-smoke
python3 scripts/check-python-boundary
git diff --check
```

Build uses the explicitly named pinned ggml include/library directories and
`ALIGN_LLM_NATIVE_CUDA=1`, with its shim in the external bundle. `make check`
checks 169 units; the narrow owner checks 38. C11/O2/warnings-as-errors owners
pass ordinary, reserve, bind and first-allocation-failure builds. They use real
backend-aligned weights/KV/input extents, three distinct graph layouts, known
output values, repeated growth/shrink and both decode kinds, exact/below budgets,
malformed key/selector/state, checked generation exhaustion, cached stale-output
refusal, empty retained capacity and exactly-once allocator release. Partial-bind
failure occurs after the first binding while another live graph remains pending.
Native Q6/copy construction is exercised in both selector orders and after
finish/cancel, including partial metadata and initial allocation failure.

The real owner compares exact complete logits and valid state at 31, 127/128/129,
200, 255/256/257, 330, 511/512/513 and 2048 inputs, then all four head/batch
combinations. Default/off/on retained short/wide/short/max/short, invalid-request
recovery, one-token exit, early EOG and tight-budget refusal pass. HTTP/SSE pinned
oracle parity, disconnect/recovery, refusals, shutdown and restart pass.

Both real `workspace-retain-reserve|bind` shim builds pass their disabled controls
and produce a failed worker envelope without partial output in mode 1. Selected
native-head and native-copy completion faults also pass with retention enabled,
using freshly built B2 shims, not ABI-incompatible older state layouts. The
existing CUDA copy owner plus the external paired copy validator qualifies
native-state-copy interoperability; its legacy chunk-512 fixture is not a new
B0 chunk-size adoption qualification. Focused Compute Sanitizer memcheck/leak-check
on ordinary growth and partial bind reports **0 errors and 0 leaked allocations**.
Fault-build, model-fault, helper, copy and `memcheck-*` logs retain exact results.
Shell/Python syntax, real/unavailable stub builds and Python boundary checks pass;
there is no new Align gap. Publication preflight is N/A: no commit or publication
is requested. All product execution/allocation decisions remain in Align/the shim.

### Allocation and memory result

Two 26-request off/on node traces and two separate 26-request host diagnostics
replay the complete post-B1 shape sequence. All **104** output/count comparisons,
SQLite integrity checks and host status/compute counts pass. All 26 pre-head and
decode kernel-name/count multisets agree off/on. Nsight uses the same CUDA/NVTX
node tracing, with CPU sampling disabled for this allocation comparison; the
host clock/metadata interposer is never combined with Nsight. Replay commands are:

```sh
PROFILE_LABEL=retain0 RETAIN_MODE=0 nsys profile --trace=cuda,nvtx,osrt \
  --sample=none --cuda-graph-trace=node --force-overwrite=false --duration=180 \
  --output="$B2_DIR/retain0" python3 "$B2_DIR/profile_shapes.py"
PROFILE_LABEL=retain1 RETAIN_MODE=1 nsys profile --trace=cuda,nvtx,osrt \
  --sample=none --cuda-graph-trace=node --force-overwrite=false --duration=180 \
  --output="$B2_DIR/retain1" python3 "$B2_DIR/profile_shapes.py"
PROFILE_LABEL=host0 RETAIN_MODE=0 LIFECYCLE=1 python3 "$B2_DIR/profile_shapes.py"
PROFILE_LABEL=host1 RETAIN_MODE=1 LIFECYCLE=1 python3 "$B2_DIR/profile_shapes.py"
```

| Request | CUDA malloc/free calls off → on |
| --- | ---: |
| Repeated 56/16 | 4 → 0 |
| Repeated 200/32 | 8 → 0 |
| Repeated 330/64 | 12 → 0 |
| First 2048/3 after shape growth | 72 → 6 |

A call is one malloc or free; the earlier profile reports pairs. Growth still
requires replacement. Input + workspace + native-head peak remains **16,613,592
bytes** over the complete identical shape sequence. Its final residency changes
from **3,310,040 to 16,613,592 bytes**, an extra **13,303,552 bytes**; small requests
after a larger one can have higher individual residency. Both graph-launch and
changed-shape recapture behavior remain: representative repeats have 15/31/63
decode launches; short-after-max recaptures two decode graphs in both arms.
Prefill topology reuse is not supplied by retaining allocation capacity.

### Complete-request performance and decision

Two campaigns each contain five alternating pairs of twenty requests per arm
at 56/16, 200/32 and 330/64: **1,800 measured Align requests** total across
same-binary off/on and the preserved B1 binary. Exactly two warmup requests per
arm/case are kept; the new mode does not repeat the candidate warmup when
checking the preserved arm. Binary/shim and staged CUDA mapping identities are
verified in all three workers in both campaigns. Every measured output/count
agrees. Original logs and all sample vectors are retained without exclusions.

Positive values below mean candidate saving. The same-binary/prior figures are
checked against exact integer-nanosecond sample vectors. Llama figures retain the
original printed summary, rather than reconstructing it from rounded pair text.

| Input/output | Same-binary saving, campaign 1 / 2 | Off/on wins | Saving vs preserved B1, campaign 1 / 2 | Saving vs pinned llama, campaign 1 / 2 |
| --- | ---: | --- | ---: | ---: |
| 56/16 | 2.292 / 2.277 ms | 5/5; 5/5 | 2.274 / 1.771 ms | 22.266 / 20.620 ms |
| 200/32 | 2.922 / -1.632 ms | 5/5; 2/5 | 3.054 / 0.563 ms | 20.714 / 13.019 ms |
| 330/64 | 1.737 / 1.777 ms | 4/5; 5/5 | 4.131 / 1.114 ms | 24.693 / 29.993 ms |

Preserved-B1 wins are 3/5 then 5/5, 5/5 then 4/5, and 3/5 then 3/5; the wider
preserved-binary comparison remains noisy. All six llama comparisons win 5/5.
The established comparison is asymmetric: Align measures complete retained
JSON request/response wall time; llama's reference interval covers prefill/decode
inside its loaded benchmark, with tokenizer/render/transport work outside it.
No equal-boundary llama speed claim, load gain or hardware-counter claim follows.
Both captures retain first use and changing-shape behavior separately; profile
wall times are not the uninstrumented adoption campaign.

Run each campaign with `QWEN35_CUDA_MEASURE_MODE=workspace-retain`,
`QWEN35_CUDA_PAIR_REQUESTS=20` and the authenticated B1 baseline. The retained
`run_campaign.py campaign-1|campaign-2` adds mapping attestation to the checked-in
`scripts/measure-qwen35-native-cuda` owner; each invocation is bounded by 900 s.
`campaign-summary.json`, `allocation-summary.json`, trace/host summaries and
raw logs own the full samples and uncertainty.

Allocation removal and exact correctness are established. Short and wider
same-binary gains repeat, while the 200/32 timing result does not. Keep the
qualified opt-in trial with default 0; do not claim a uniform/default adoption or
extend it into another optimization. Conditional prefill metadata/topology reuse
and backend stream bridging remain outside this capability.

One fresh independent comprehensive adversarial review of all 15 B2 delta files
against the exact prior start-tree snapshot is **CLEAN**, with complete findings
**none**. Reviewer `/root/workspace_retention_review` verified candidate bytes and
modes, all 107 manifested artifact hashes, campaign reductions, all 104
output/count comparisons and all 26 paired kernel multisets. Reviewed head, base
tip and merge base are `687acd3312220742ad013595951e0d8c5b966e16`; candidate
manifest SHA256 is
`af79b7306191b49fa9298b18a52fb33ec6423a36a855d50b8028769b876f26a5`,
diff SHA256 is
`514b5d94ed326056775696dbdd3fcb1d27f3b5a3074efc30d3b68559734e5a94`,
and evidence manifest SHA256 is
`7c8a30314418a1d698fb1418b2b4a3a4e75aaab332598f7b8487cd94df56e543`.
Inspection did not edit files or run GPU workloads. `review-result.json` retains
the full envelope and final file identities; no finding or implementation repair
remains. The post-review delta only records completion here and in `HANDOFF.md`;
documentation consistency and diff checks pass without repeating source owners.

The bounded lesson is that removing physical allocations establishes the
mechanism, while complete-request gains still need repeated same-binary pairs
and the preserved baseline. Shape transitions and increased retained residency
must remain in the evidence. This adds no permanent gate or follow-on scope.

## 2026-10-01 B3 prefill graph-cache diagnosis and design

The user requested preparation through the point before implementation for
prefill graph reuse. This checkpoint changes five developer documents and runs
external measurement only. The authoritative B3 ledger and closure matrix are
in `docs/specs/gpu-runtime-performance.md`. Product source, the B2 artifact,
compiler/backend pins and the preceding B1/R1 work remain unchanged. No B3
implementation, speedup, publication or default adoption is claimed.

### Subject and evidence

Branch/head/base remain `agent/cuda-q4-repack-plan` /
`687acd3312220742ad013595951e0d8c5b966e16`. The subject is the authenticated
B2 binary SHA256
`93c4e39ee61845710b4233ee13eb90d538ade55bc1ff4de4c5e38dc7a4d730f7`
and shim
`09fbeb900e8e29404a70f9ad5709f69baceb4cabe5c3e60a28ad140f841f20c3`,
with the same RTX 4070 Ti, Qwen3.5-2B Q4_0 model, CUDA 13.3.73/driver 610.62,
WSL2, managed Align pin and pinned ggml as B2. Loaded binary/shim paths and
device/inode/digest mappings are checked while each worker is alive, including
the staged CUDA plugin
`ec1ddd96247a97ba6f2a564301efca6a1e9b479f29b6bdb9d166ead2bbb4f774`.
The six inspected allocator/CUDA/header sources match the named ggml commit.
The checkout's pre-existing `common/debug.cpp` and eval-callback diagnostic
edits are recorded separately; no fresh backend build is used for this evidence.

The existing `retain1` B2 node trace supplies GPU launch evidence; it is not
recaptured or represented as a new trace. Two additional 26-request host
diagnostics use B2 with head/batch/retention 1, chunk 128 and the other native
copy modes 0. The exact sequence is B2's three requests each at 56/16, 200/32,
330/64, 56/16 and 200/32, then 127/128/129, 255/256/257, 511/512/513 with four
outputs, 2048/3 and short-after-maximum 56/16. Every first use is retained.

The diagnostic forwards `align_ggml_graph_new` and `align_gpu_graph_prepare`
unchanged, brackets construction and preparation separately, and reads context
use/capacity, exact key, first-node offset, node count and structural/pointer
fingerprints. The structural FNV fingerprint covers type/op, dimensions,
strides, op parameters, view offsets and source dimensions/strides; it is a
diagnostic, not a replacement for ggml's complete property comparison or the
product's SHA256 key. No metadata, binding, input or graph policy is mutated.
The first run inherits the ggml environment; the confirmation explicitly removes
both `GGML_CUDA_DISABLE_GRAPHS` and `GGML_CUDA_GRAPH_OPT` from the child and
records that selection. All structural/key/metadata observations agree across
both runs. All **52** outputs/counts agree with the prior B2 fixture responses.
This is diagnostic parity, not fresh full-logit/state qualification.

External `prefill-reuse-plan-20261001` contains the start-tree snapshot, diagnostic
sources/binaries, both raw responses/stderr/mappings, reducer, source identities
and evidence manifest. With `B3_DIR` set to a fresh bundle and `GGML_SOURCE` to
the exact pinned checkout, replay is:

```sh
cc -shared -fPIC -O2 -Wall -Wextra -Werror -I "$GGML_SOURCE/ggml/include" \
  "$B3_DIR/topology-clock.c" -o "$B3_DIR/topology-clock.so" -ldl
PROFILE_LABEL=topology RETAIN_MODE=1 LIFECYCLE=1 timeout 180 \
  python3 "$B3_DIR/profile_topology.py" \
  > "$B3_DIR/topology.jsonl" 2> "$B3_DIR/topology-driver.log"
PROFILE_LABEL=topology-confirm RETAIN_MODE=1 LIFECYCLE=1 timeout 180 \
  python3 "$B3_DIR/profile_topology.py" \
  > "$B3_DIR/topology-confirm.jsonl" 2> "$B3_DIR/topology-confirm-driver.log"
python3 "$B3_DIR/reduce_topology.py"
cc -O2 -Wall -Wextra -Werror -I "$GGML_SOURCE/ggml/include" \
  "$B3_DIR/layout-probe.c" -o "$B3_DIR/layout-probe"
"$B3_DIR/layout-probe"
```

Stdout/stderr are retained under each label's JSONL/driver log; the caller writes
the matching worker stderr/mapping files. The retained current caller explicitly
sets the ggml flags for both replay runs; the original first run's inherited
environment is not retrospectively attested. Storage was 4.2 GiB free before
work; the diagnostic adds no Nsight report/model copy and stays below the
1-GiB evidence ceiling. No cleanup or hardware-counter permission change was
needed. Product builds/tests were not rerun for this design-only delta.

### Residual cost and cache choice

The following are rows 1/2 of each initial three-request group. Host columns
come from the separate first diagnostic; GPU columns come from the existing B2
node trace. They must not be added or treated as uninstrumented savings.

| Input/output | Host graph construction, two repeats | Host preparation, two repeats | Pre-head GPU kernels | Pre-head graph launches |
| --- | ---: | ---: | ---: | ---: |
| 56/16 | 0.459 / 0.405 ms | 0.790 / 0.669 ms | 992 / 992 | 0 / 1 |
| 200/32 | 0.832 / 0.867 ms | 1.400 / 1.318 ms | 1,951 / 1,951 | 0 / 0 |
| 330/64 | 1.395 / 1.157 ms | 2.143 / 1.933 ms | 2,880 / 2,880 | 0 / 0 |

The short-return group already replays prefill in both repeated requests; the
200-token return group still does not. Thus B3's principal launch opportunity
is multi-chunk prefill, while short inputs primarily offer metadata reuse.
In the 200/32 repeats, traced pre-head wall time is 34.040/25.738 ms and GPU
union is 16.412/16.453 ms; tracing and unavoidable work occupy the difference.
It is not a prediction that the difference can be removed. The launch API can
overlap GPU work, and its instrumented duration is not an additive opportunity.

Each diagnostic observes **68** prefill builds and **28** exact keys. All
first-node offsets are **82,640 bytes** before and after optimize, and each key
has one structural fingerprint. Maximum context use is **509,488 bytes** and
maximum graph size is **1,159 nodes**. Each decode context's first-node offset
is 83,008 bytes. These support fixed-slot feasibility but do not prove stable
bindings or CUDA replay after implementation.

| Fixed slots, ordinal modulo capacity | Simulated hits / misses over 68 chunks |
| --- | ---: |
| 3 | 29 / 39 |
| **4, selected** | **33 / 35** |
| 8 | 34 / 34 |
| 16 | 34 / 34 |

This is offline exact-key simulation on the observed sequence, not a benchmark
of cache implementations. Four slots cover every chunk of the main 56/200/330
workloads and sacrifice one modeled hit versus sixteen in this sequence. With
fixed chunk 128, the complete <=2048 prompt space has 2,063 possible final or
nonfinal topology keys under the selected final-logits policy; prebuilding them
would be inappropriate. The design keys exact offset/count/KV width/parity and
output form, not just the four-way index or padded width.

Keep the existing **24 MiB** per-context capacity. The observed 0.49 MiB is not a
safe general upper bound: unreferenced construction tensors occupy context
storage, and existing Qwen geometry admits more layers. A smaller arena would
need a separate allocation bound or checked-construction change because pinned
ggml metadata exhaustion is fatal. Four slots raise metadata admission from
96 to **168 MiB**, an added 72 MiB, versus 456 MiB for sixteen. Added bookkeeping is capped at
64 KiB, including one **4,160-byte** Align slot buffer; the exact minimum host
admission is **210,829,312 bytes** with existing staging/application allowances.
This is reserved/allocated capacity; no physical RSS increase is established yet.

The pinned layout probe reports `sizeof(ggml_tensor)=336` and CUDA
`node_properties=1056` bytes. Six possible backend graph identities bound the
number of vectors/graph executables, not their allocated byte sizes. Vector
capacity and CUDA graph/driver memory must be measured during implementation.
The authoritative ledger fixes explicit reservation, +128-MiB RSS and +64-MiB
backend-device qualification ceilings before coding. No budget discount is made
for presumed lazy page residency, and no opaque allocation is called tensor
workspace.

### Implementation boundary and completion conditions

The selected capability adds an explicit default-off graph-cache selector,
four native metadata entries, checked activation and release, persistent Align
slot tables, and the same reuse branch for ordinary and streaming consumers.
Cache hits refresh every input and execute the full graph. Successful request
release clears result/readiness grants while retaining topology; failure recovery
clears all entries, and poisoned owners require teardown. Slot collisions and
workspace growth must rebind every parked graph before it becomes usable.

Before optimization, all four prefill and both decode contexts must retain their
first-node identity; nonzero graph UID shortcuts remain unused. The initial
trial requires ggml graphs enabled and its concurrent graph optimizer disabled.
Backend TTL recapture is allowed. Capture warmup comes from subsequent real
requests, never an extra execution that would mutate recurrent/KV state.
The pinned backend needs no new deletion/stream bridge for this bounded design.
Existing borrowed-buffer and FFI surfaces suffice; no new Align gap was found.

Implementation acceptance explicitly covers both head/batch selections, decode
state-copy interoperability, full logits/state, equal-shape different-content
requests, 513/1024/2048 collisions, growth/stale-result/failure owners, SSE
disconnect/recovery, first use, idle return and complete-request measurements
against same-binary off/on, authenticated B2 and pinned llama. The ledger names
the exact future owner commands; none are claimed run at this checkpoint.
Repeated long prompts can thrash four slots, and unqualified memory overhead
blocks adoption. R2 and further kernel tuning are outside this capability.

Author verification passes: both diagnostic exits, all 52 response/count
comparisons, both runs' exact key/structural/metadata agreement, offline slot
simulation, pinned layout probe, subject/source authentication, ledger/receipt
memory arithmetic, Python boundary and `git diff --check`. Only five Markdown
files differ from the preserved start tree. Source owners and publication
preflight are N/A for this uncommitted design-only checkpoint. The fresh
comprehensive review binds that exact delta and the external evidence manifest.

The bounded lesson is to preserve a proven per-graph allocation allowance and
limit entry count, while measuring actual use separately. A small observed
context does not justify shrinking its safety capacity. No permanent gate or
unrelated optimization is added.

One fresh independent comprehensive adversarial review of the five-document B3
delta and supporting evidence is **CLEAN**, complete findings **none**. Reviewer
`/root/prefill_cache_design_review` independently reproduced the delta/reducer,
verified candidate modes and all manifested/referenced identities, and checked
all 52 output/count/status results and 82 cross-run topology events. Reviewed
head, base tip and merge base are
`687acd3312220742ad013595951e0d8c5b966e16`; candidate SHA256 is
`bd4cd1e38ea2911719d6f91c4e3c0b05ac5d060a715c8eaed499698068ede067`,
diff SHA256 is
`91203374f9adbf2cd5077d51da829d6359b316eb1541c372afbd7d1d7c2b9166`,
and evidence-manifest SHA256 is
`aedc16b2fe52d6dbf6748a1d27d2411e64271f39f1fc4b3c21172cd11080e6ec`.
`review-result.json` retains the full envelope and final identities. Only
completion/status records in this receipt, the ledger and handoff changed after
review; no contract repair or implementation change was required. Final
documentation consistency and diff checks pass. All named implementation
qualifications remain future work, and this user-requested checkpoint stops here.

## 2026-10-01 B3 prefill graph-cache implementation

The user authorized the reviewed four-entry B3 contract. Implementation connects
ordinary retained generation and streaming through the same native cache owner;
selection remains default off. The B3 ledger in
`docs/specs/gpu-runtime-performance.md` remains authoritative. No kernel,
arithmetic, chunk size, model artifact, compiler pin or HTTP format changes.
The existing intentional B1/R1/B2 working-tree changes remain preserved context.

External `prefill-cache-20261001` retains the initial diff/reconstructed start
tree, source identities, native binaries/shims, mapping attestations, every raw
sample, complete state/logit qualification, separate host diagnostics and Nsight
reports. `inputs.env` names the authenticated artifacts; use its recorded values
with the commands below. HEAD/base/merge base remain
`687acd3312220742ad013595951e0d8c5b966e16` on `agent/cuda-q4-repack-plan`.

### Implementation and closure

The three new native/Align ABI surfaces select, activate and release four fixed
24-MiB contexts. Entries copy exact keys and retain graph/native-head/row metadata;
the active PREFILL fields are aliases. Hits drain/advance content generation,
restore topology and invalidate results, then receive fresh 0/1/2/7 inputs. Misses
reset only the selected entry and publish after support/anchor/binding checks.
Rebuild includes every parked entry and both decode graphs, once in stable order.
Successful request release preserves bindings; recovery clears every entry.
Poisoned input/weight/KV/observation/workspace states refuse activation, graph
lookup/compute and release. Partial construction poisons and retains ownership
for exactly-once teardown. Both decode anchors survive invalidation, bounding
backend keys to six without assigning graph UIDs or modifying pinned ggml.

| Contract/closure owner | Passing focused evidence |
| --- | --- |
| Native selector, context spans, copied keys, malformed/pending state, collisions, hit counters, anchors, inactive/stale reads, clear and cleanup | `scripts/run-gpu-prefill-graph-cache-smoke "$GGML_SOURCE" "$GGML_LIB" "$GPU_PLUGIN"`: ordinary/open/publish/reserve/bind variants; all four partial construction positions, shifted first nodes in prefill/both decode, generation/poison refusal, six live bindings and partial bind with parked entries. `final-abi-owner.log` owns the reviewed source run; `repair-abi-owner.log` includes reverse selector/planning preservation and registered-index hit refusals. |
| Complete real-model arithmetic/state and all consumers' shared cache rules | `QWEN35_PREFILL_GRAPH_CACHE_OWNER=1 scripts/run-qwen35-native-q6-head-smoke`: exact full logits/state at 31, 127/128/129, 200, 255/256/257, 330, 511/512/513, 1024/2048; both head/batch values, retained capture/replay/churn and equal-length different text, single output/EOG/reset/refusals, exact host minimum and one byte below. `review-model.log` owns final artifact evidence. |
| Failure and helper interoperability | Fresh real `prefill-cache-open\|publish`, B2 reserve/bind and Q6/copy completion shims; disabled controls pass and selected construction/request fails without ready/partial output. Construction failure uses the existing empty-output startup envelope; runtime failure uses the framed failed envelope. External `qualify_faults.py` / `qualify_copy.py`, `final-fault-owner.log` / `final-copy-owner.log` retain six faults and exact CUDA decode-copy logits/state at 31/200/330. |
| Streaming, disconnect, recovery and shutdown | `ALIGN_LLM_PREFILL_GRAPH_CACHE=1 ALIGN_LLM_RETAIN_WORKSPACE=1 ALIGN_LLM_PREFILL_CHUNK=128 ALIGN_LLM_NATIVE_Q6_HEAD=1 ALIGN_LLM_BATCH_DECODE_INPUTS=1 scripts/run-openai-serving-smoke`: pinned oracle parity, HTTP/SSE, refusals, post-first-token disconnect/recovery, shutdown/restart pass in `final-serving-owner.log`. External `qualify_cancel.py` runs this oracle plus traced pre-first-token cancellation and subsequent ordinary/stream parity; `repair-serving-owner.log` and `repair-cancel-proof.json` qualify both disconnect timings. No serving implementation change is needed. |
| Resource lifetime and malformed allocation paths | Focused `compute-sanitizer --tool memcheck --leak-check full --error-exitcode 99` on ordinary growth/collision/partial construction and parked partial-bind owners: **0 errors, 0 bytes leaked in 0 allocations**. `final-memcheck-ordinary.log` / `final-memcheck-bind.log` identify their exact reviewed owner; `repair-memcheck-ordinary.log` repeats the expanded selector/index owner with the same zero-error/zero-leak result. |
| Compiler/developer boundary | `make check` 169 units; generation `check-per-unit` 38 units; native `make build`, `make fmt`, unavailable static stub build, shell/Python syntax, Python boundary and `git diff --check` pass. No new Align gap or pin adoption. Publication preflight is N/A: no commit/publication requested. |

### Mechanism and cost

Four separate 37-request diagnostics preserve **148** outputs/counts, including
all shape boundaries, repeated 512/513/1024/2048 and an 11-second idle return.
Nsight off/on request, pre-head and decode kernel-name/count multisets match for
all 37 requests; SQLite integrity passes. Instrumentation is excluded from
adoption timing. Host diagnostics show 140 prefill invocations: off rebuilds all
140; cache mode has **50 hits / 90 misses** and 90 prepares. Decode prepares stay
11 per kind. Actual metadata use remains at most 509,488 bytes per context.

| Repeated request's pre-head work | Cache off | Cache on |
| --- | ---: | ---: |
| 56/16, third request | 992 kernels, 1 launch + first capture | 992 kernels, 1 launch, no new capture |
| 200/32, third request | 1,951 kernels, 0 graph launches | 1,951 kernels, 2 graph launches, no new capture |
| 330/64, third request | 2,880 kernels, 0 graph launches | 2,880 kernels, 3 graph launches, no new capture |
| Repeated 1024/2048 | 0 prefill graph launches | 0 prefill graph launches; slots thrash |

The second requests can pay initial capture; idle return can pay TTL warmup and
recapture. Preserve these and adverse changed-shape samples rather than deriving
a request gain from traced intervals. `cache-cost.cu` reads the exact pinned
backend layout without changing it: peak keys/captures rise 3->6; allocated node
property vector capacity rises 4,722,432->7,237,824 bytes, +2,515,392. Fixed arena
reservation adds **72 MiB**, not that small observed used extent. Native state
grows 8,104->9,216 bytes (+1,112); the four-entry table is 4,160 bytes, for 5,272
added explicit bytes before Align handle/allocator overhead, below the 64-KiB
allowance. Exact admitted host minimum remains **210,829,312 bytes**.

Host peak RSS is 527,446,016->556,793,856 bytes, **+29,347,840** (<128 MiB).
Raw CUDA device-used peak is 2,654,470,144->2,677,538,816 bytes,
**+23,068,672** (<64 MiB). CUDA reports shared device use; same-process
peak-minus-after-close is **1,302,331,392 in both arms**, cancelling the 22-MiB
baseline offset. The serial GPU interval has no other compute worker, but display
use/driver context caches remain limits; these are controlled observations,
not a universal opaque allocation guarantee. Explicit tensor accounting and
all model/input payload stay within the unchanged B2 workload admission/peak.

The mechanism traces/first host screen use the identified initial B3 shim;
subsequent closure work only strengthens failure/poison refusal. Final performance
and qualification authenticate the final shim separately. All initial artifacts
and samples remain retained; no failed or slower run is removed.

### Whole-request assessment

Final `main` SHA256 is
`6b9608b6b12f1e64178bac1abe07d627b1435d4bc86a678c54ab0aba8163f44a`;
final shim SHA256 is
`dc440d998a4100b08d77387f68daa5f0d5f7198924ffbcc3c434c60da120cc4a`.
Campaigns 3/4 authenticate both and actual loaded CUDA mappings. Each keeps
900 timed Align requests (three arms), exactly two warmups per arm/case, five
alternating pairs of twenty requests and one loaded llama interval per pair.
All actual work/output checks pass. Campaigns 1/2 are retained exploratory
evidence before final failure-guard consolidation; they are not substituted
for the final 1,800-request result. `reduce_campaigns.py` reproduces every exact
same-binary/B2 median from all 3,600 retained samples and checks printed precision.

| Prompt/output work | Same-binary off minus on, campaigns 3 / 4 | Preserved B2 minus on, campaigns 3 / 4 | Pinned llama minus on, campaigns 3 / 4 |
| --- | ---: | ---: | ---: |
| 56 / 16 | 2.541 / 1.658 ms | 1.888 / 1.787 ms | 20.486 / 22.773 ms |
| 200 / 32 | 10.548 / 11.355 ms | 12.690 / 13.320 ms | 30.751 / 28.978 ms |
| 330 / 64 | 15.503 / 18.008 ms | 16.905 / 19.513 ms | 43.153 / 47.645 ms |

Every comparison wins **5/5 pairs** in both final campaigns. These are paired
median **savings**, not execution durations. Median pair-mean final on latencies
are 67.420/68.010, 143.490/143.296 and 279.773/280.957 ms. Same-binary controls
are 69.707/69.488, 154.361/153.408 and 295.276/298.965 ms; preserved B2 is
69.274/69.798, 154.774/157.504 and 297.835/300.311 ms. Do not subtract unrelated
aggregate medians to recreate the paired statistic. Align measures inclusive
retained JSON request wall time; llama measures its existing loaded inner
prefill/decode interval, excluding rendering/tokenization/transport. No equal-CLI
boundary or first-load/TTFT claim is made.

Final host-screen repetition (`host-final-*`) preserves another 74 outputs/counts,
again 50 hits/90 misses, six keys/captures and identical property-vector bounds.
RSS is 527,171,584->556,318,720 bytes, **+29,147,136**; raw device peak delta is
again 23,068,672 bytes and close-normalized delta zero. Final native failure/copy,
serving and expanded ABI logs are `final-*-owner.log`; final sanitizer logs
cover the frozen lifecycle owner. The Align-only oversized-index execution
fixture is explicitly deferred in the ledger; its checked wrapper and bounded
product derivation are inspected. Native malformed index/key/foreign graph and
exact/below workspace boundaries execute against the real backend.

Retain the qualified default-off opt-in: all three named warm-request benefits
repeat within the trial cost screen, while long-input thrashing, initial capture,
TTL return, other models/hosts and shared driver attribution remain limits.
The sole comprehensive implementation review is complete. Its two P2 findings
identify missing acceptance evidence, not a demonstrated product defect: reverse
selector/planning and invalid cached row indices; and pre-first-token disconnect.
Both are accepted and resolved together in a local owner/validation repair.
No commit/publication is requested. The bounded lesson is to retain topology only after result/row grants
are invalidated, and audit every failed-state family across activation, lookup,
compute and recovery; four failure-family fixtures prevent partial poison checks.

The repair native owner verifies refusals preserve the entire owner state in
both selection orders. CUDA cannot select the excluded Metal-only helpers;
the fixture checks that early refusal and separately injects selected policy
flags to execute the backend-neutral cache guard. This is not Metal execution
evidence. A real indexed KV graph registers four I32 rows, consumes them once,
then refuses missing, malformed/short/offset and stale grants on repeated cache
hits; a fresh refresh computes known changed values with one prepare/two reuses.
All five owner variants pass. The first new fixture invocation exceeded its
64-byte upload staging limit; `repair-abi-initial-fixture.log` is preserved and
the corrected owner uploads in four bounded chunks. No product repair was needed.

External `cancel-trace.c` forwards activation/compute/release unchanged and
records monotonic completion times. `qualify_cancel.py` extends the existing
HTTP/SSE oracle with a long legal prompt, waits for activation in the independent
trace, then resets the socket before reading any response. The proof records
reset before final prefill completion, no decode execution, successful clear-0
release, and exact following ordinary/stream output. The original post-content
disconnect and complete serving owner also pass. Instrumentation is used only
for this qualification, never performance. Product source/binary/shim and every
measurement sample remain byte-identical to the reviewed candidate. The repair
delta stays within the two recorded acceptance cells; no second comprehensive
review is required under the narrow-repair rule.

The fresh independent reviewer is `/root/prefill_cache_implementation_review`;
kind/scope is a comprehensive high-effort adversarial inspection of the complete
16-file B3 implementation/performance delta. Reviewed head, base tip and merge
base are `687acd3312220742ad013595951e0d8c5b966e16`. Original verdict is
**FINDINGS**, with exactly the two P2 evidence findings above and no other
finding; both dispositions are **accepted/resolved**. Candidate SHA256 is
`9925aab05dca260a1cfb846c777788762b5895ced5556ac042cf69808daf43a2`,
diff SHA256 is
`caa682f19c615130d7ed3cc90fd8a4ccdf939139071ffd16d3df7f10b90409fb`,
and original evidence-manifest SHA256 is
`4b7a3753a73462f2c70106c15ec8343f85df803e44f6a8f48a070bf489eeffbe`.
The reviewer reproduced the paired reductions and 222 diagnostic output/count
results, inspected all affected ownership/consumer paths and authenticated
258 source/artifact/subject objects in its final unchanged-identity pass.
`review-result.json` preserves the complete envelope, findings/dispositions,
repair evidence and final file identities. Consolidated repair commit and
publication/integration preflight are `N/A`: this is uncommitted local work.
