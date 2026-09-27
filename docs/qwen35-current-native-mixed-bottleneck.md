# Qwen3.5-2B current Metal request speed and bottleneck (2026-09-28)

## Decision

The tested, default-off mixed native state-copy route remains the fastest
qualified real-model route on this Apple M1. In a fresh uninstrumented campaign,
it beat the same-binary ordinary Align path and pinned llama.cpp in every one
of five pairs at each of 64/16, 200/32 and 330/64 input/output tokens. This
does **not** measure the independent complete-FFN kernel inside a request:
that kernel is still a local probe, while the measured model graph produces
attention, FFN and logits through unmodified ggml.

The current GPU target is the quantized matrix work. A current mixed-mode
Metal System Trace attributed 35.8% of sampled shader intervals to Q4_0
matrix-vector, 23.4% to Q6_K matrix-vector, and 26.1% to Q4_0 matrix-matrix;
F32 copy accounted for 0.7%. The matvec counter samples reported 100.0% and
99.8% median Buffer Read Limiter, with 52.1 and 56.5 GB/s median GPU reads.
These are diagnostic associations, not a physical byte count or exact
per-dispatch latency. They support reducing useful weight traffic and execution
boundaries before another small copy/argmax change. The independent FFN's
local gain remains worth a connected Align-owned scheduling trial; no request
gain is credited to it here.

## Reproducible request comparison

The host is an Apple M1 with 16 GiB memory, macOS 27.0. The actual
Qwen3.5-2B Q4_0 GGUF SHA-256 is
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
The saved Align binary SHA-256 is
`cc2ef89cdf5dfdf4391f903ad892ddc829b0dfd732d3e0e880764b9bc1ae93c8`;
its native shim SHA-256 is
`7ccb01d08d08407c3274121e4531196a18186e7c42052691621ff8b417467dd9`.
The source closure under `src/`, `.align-revision`, `scripts/ggml_shim.c` and
`scripts/native_metal_state_copy.mm` is unchanged from merged PR #312 through
PR #315. Both Align arms use this one binary, the same pack, Model IR, resident
Metal options and unmodified pinned ggml `bb4caa7540188872173c44d161602d9271386413`
bundle ID `0a472538ef35e2722fb9488d677196081ab8f726eff825a4e7837ddade57814b`.
The control disables native state/convolution copy; the candidate enables
both, leaving native prefill copy, GPU greedy and native SwiGLU off. Pinned
llama.cpp's reference SHA-256 is
`f384a6a64603479cf5c675ba587aeafbd64a500c3129a0afdcd271dcf532717d`.

The checked-in [wall receipt](../eval/benchmarks/qwen35-current-native-mixed-2026-09-28-wall.json)
contains every sample, input token ID, output, binary digest and actual token
count. Each worker runs three identical requests and times the third; five
pairs alternate arm order. Every compared arm generated the same text and
exact declared token count. Values below are warm-request medians in ms;
paired differences are medians of individual differences, so they need not
equal differences of arm medians. Positive differences favor mixed native.

| Input/output | Ordinary Align | Mixed native Align | Pinned llama.cpp | Ordinary minus mixed | Llama minus mixed | Mixed wins |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 64/16 | 561.373 | 515.575 | 546.880 | +46.506 | +29.336 | 5/5 vs each |
| 200/32 | 1368.654 | 1214.413 | 1333.616 | +143.161 | +119.203 | 5/5 vs each |
| 330/64 | 2583.281 | 2323.017 | 2453.437 | +281.253 | +157.316 | 5/5 vs each |

The 200/32 ordinary-minus-mixed pairs range from +37.365 to +344.984 ms,
so the median is more informative than the most favorable run. Candidate
construction-to-ready medians were 1.013, 1.138 and 1.129 s for the three
conditions; pinned llama.cpp was 0.468, 0.487 and 0.459 s. Startup includes
uncontrolled file and compiler caches, and the reference driver times its
third request separately. These are construction observations, not a matched
cold first-output comparison. Model quantization and generated work did not
change.

Reproduce the uninstrumented comparison using
`scripts/measure-native-swiglu --native-disabled --wall-only --pairs 5`, an
explicit config for the model/pack/Model IR, the named binary/bundle and the
pinned `scripts/bench-native-llama.cpp` reference. Set common execution to
asynchronous weight upload, prefill chunk 128, final prefill logits on, final
FFN row off, mapped/shared/private weights off, and CPU greedy. Select
`native_state_copy=0,native_conv_copy=0` for control and `1,1` for candidate.
The caller checks equal token IDs and output before reporting speed.
This campaign did not rehash complete logits or recurrent planes; the existing
real-model owners qualified those earlier for the unchanged saved binary.

## Connected phase and command diagnosis

A separate [schema-3 phase receipt](../eval/benchmarks/qwen35-current-native-mixed-2026-09-28-phase.json)
uses `scripts/trace-native-ffn.c` to time the third request's graph calls and
native completion waits. It has five alternating pairs at each condition and
retains one adverse mixed-versus-reference 200/32 pair. The interposer changes
host timing, so the wall receipt above owns the speed claim. The corrected
phase reducer takes graph and native waits from the **same third request**;
the prior schema-2 reducer erroneously included three requests of waits.

| Input/output | Mixed prefill | Mixed decode, including native wait | Native wait within decode | Decode steps/s |
| --- | ---: | ---: | ---: | ---: |
| 64/16 | 127.172 ms | 392.369 ms | 15.018 ms | 38.2 |
| 200/32 | 391.843 ms | 811.100 ms | 29.073 ms | 38.2 |
| 330/64 | 612.033 ms | 1652.132 ms | 57.469 ms | 38.1 |

There are 15, 31 and 63 decode steps because the first output token is
selected from prefill. Decode-steps/s divides those counts by the phase median;
it is not whole-request output-token throughput. At 200/32, the candidate's
decode graph/submission median was 784.153 ms. The phase clocks omit CPU
token selection and other host work, and independently taken medians are not
an additive decomposition of wall time.

One additional instrumented 200/32 worker issued 31 native commands on its
third request. The [profile receipt](../eval/benchmarks/qwen35-current-native-mixed-2026-09-28-profile.json)
records 25.879 ms summed native GPU command intervals, 32.081 ms summed host
completion waits, 2.846 ms command preparation, and 31 full 993,280-byte
logit reads totaling 1.552 ms. Those intervals overlap in the execution
schedule and must not be added to infer removable request time. The output
SHA-256 matches the paired worker's 200/32 output.

The same profile's counter-enabled Metal System Trace has Shader Timeline
enabled and 10,681 rows for the worker PID across a 3.876 s span covering its
three requests. The table below is the fraction of the sum of sampled shader
interval durations, which may overlap; it is not a fraction of request wall.

| Shader | Sampled interval share | Median Buffer Read Limiter | Median GPU read bandwidth | Median F32 utilization |
| --- | ---: | ---: | ---: | ---: |
| Q4_0 matrix-vector | 35.8% | 100.0% | 52.1 GB/s | 11.0% |
| Q6_K matrix-vector | 23.4% | 99.8% | 56.5 GB/s | 7.3% |
| Q4_0 matrix-matrix | 26.1% | 28.0% | 26.7 GB/s | 83.1% |
| F32 copy | 0.7% | 0.4% | 5.1 GB/s | 0.0% |

Counter names and IDs were checked against this trace's `gpu-counter-info`:
10 is Buffer Read Limiter, 25 GPU Read Bandwidth and 2 F32 Utilization. Counter
samples within ten microseconds of a shader edge or overlapping another
worker shader were excluded. The checked-in compact profile retains sample
counts and medians; the complete `.trace` remains under the Git common
directory's `diagnostics/q35-ceiling-20260928/`, outside Git because of its
size. Background GPU work and sampling overhead remain possible.

## What this establishes

Current mixed decode is principally quantized matrix-vector work, associated
with buffer-read pressure on this M1. Prefill has a distinct Q4_0
matrix-matrix signature with high F32 use. F32 state copies and full-logit
readback are small in the connected profile after the native copy seam.
This does not establish a hard hardware ceiling: the byte traffic, reuse,
launch/synchronization structure and larger fusion units can still change.

The next independent Metal consumer should keep dependent operations queued
inside a larger Align-owned resident execution unit, with buffer ownership,
state publication and errors explicit. The [local complete-FFN
screen](qwen35-q4-full-ffn-capture-screen.md) found only 0.057–0.068 ms per
eligible layer of isolated advantage and showed that an intermediate host wait
costs far more. Integrate it only as part of a path that can test complete
logits/state and full requests without a wait at every FFN. Retain ggml as the
comparison/rollback path. Another Metal generation, other Qwen quantizations
and Gemma semantics remain unmeasured; the kernel and schedule need fresh
admission there.
