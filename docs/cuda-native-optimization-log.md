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
