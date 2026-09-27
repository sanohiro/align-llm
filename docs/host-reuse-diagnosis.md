# Retained host-work experiment — 2026-09-26

## Implementation and scope

Baseline is `6124e90bfda9b33539177697926c5e7b598b45c9`. Both binaries use the
same four-accumulator/128-thread Metal bundle, with native FFN fusion disabled.
The compiler and ggml pins, authenticated 2B weights, quantization, options,
tokenizer and greedy generation are unchanged. This tests the host-work
hypothesis raised by inspecting the generated Mach-O, not another FFN kernel.

`runtime_qwen35_generation` now computes the existing full graph key only when
its parity/attention-width cache misses. Backend, bundle, geometry, token count
and graph position (`width - 1`) are invariant for the retained entry. Invalidated
keys are empty and force reconstruction even if the remembered width matches.
No key format, mathematical operation, state reset or synchronization changes.

Each session owns reusable stream scalar, position, mask and logits buffers.
Their payload costs `n_vocab * 4 + mask_capacity * 4 + 20` bytes (1,002,516 bytes
for this 2B configuration), plus four buffer headers and two width integers.
The original nonstream request-local buffers remain. Stream inputs and logits
are overwritten before use, and scratch is never shared between sessions.
Buffer destruction follows the existing session owner. A compiler limitation
requires local stream input writes and renewed views after the mutable position
helper; Request 121 records the concrete resource/sibling-view witness.

Align continues to own graph identity, storage lifetimes, state and generation.
GGML continues to own device allocation, graph encoding and mathematical kernels.
No new production C/C++/Python path exists. No Align language extension was used.
The same host reuse applies to other admitted Qwen3.5 sizes; broader Qwen and
Gemma still need their model-specific semantics and native admission.

## Correctness and measurements

Results are recorded after the complete campaign below. Every measured output
must exactly match; no numerical tolerance was changed. The HTTP/SSE campaign
has two warmups per mode and five alternating pairs, including a decode that
crosses width 256 and a return from width 512 to width 256. Both servers stay
resident, but only one request executes at a time. SSE count evidence is inferred
from exact text/length-finish agreement with the counted nonstream response.

Timing on a desktop Apple M1/16 GiB is subject to background activity. No timing
samples are removed. Startup includes uncontrolled file-cache effects. Separate
interposer runs identify calls and GPU spans; they are not speedup benchmarks.
Command-buffer GPU start/end intervals include everything inside the buffer,
including memory stalls, barriers and dispatch gaps; they are not shader ALU
utilization. The timestamp semantics follow [Apple's documentation](https://developer.apple.com/documentation/metal/mtlcommandbuffer/gpuendtime).

## Reproduction

Keep the baseline binary before rebuilding, and provide CONFIG with `model`,
`pack`, `geometry`, `control` and `candidate` objects (`binary`, `options`, `lib`),
`control_commit`, and the pinned `llama` reference and `trace` phase interposer
paths used by the existing native trial. All local paths are caller-owned.

```sh
python3 scripts/measure-host-reuse --config CONFIG --output NEW_HTTP_JSON
python3 scripts/measure-native-swiglu --native-disabled --config CONFIG --output NEW_WORKER_JSON
scripts/run-qwen35-generation-smoke
scripts/run-openai-serving-smoke
python3 scripts/check-python-boundary --strict
```

The two owners use the existing `QWEN35_*` environment inputs. The 2B generation
owner additionally supplies its authenticated `QWEN35_EXPECTED_SHA256`; omit it
for the existing 0.8B fixture. Build the diagnostic dylibs using the commands at
the top of `scripts/trace-host-calls.c` and
`scripts/trace-metal-command-buffers.m`. Set `DYLD_INSERT_LIBRARIES` to exactly one
of them only in a separate diagnostic native process; select the same bundle
with `DYLD_LIBRARY_PATH`. Collect stderr, check graph/command status and timestamp
completeness, and associate command-buffer spans with the surrounding graph
markers. Compute interval unions instead of adding overlapping GPU durations.
Use `xcrun llvm-objdump --macho --disassemble BINARY` to inspect generated calls;
Align symbols encode the module/function text in hexadecimal.

## Results

The [raw receipt](../eval/benchmarks/host-reuse-metal-2026-09-26.json) contains
all HTTP warmups/pairs, worker/reference pairs, diagnostic call counts and GPU
timestamps, binary/bundle identities, and interrupted-harness-run limitations.
Both 2B and 0.8B generation owners and serving owners pass: pinned oracle output,
six retained requests, HTTP/SSE equivalence, Japanese text, rejected requests,
disconnect recovery, bounded bodies and shutdown/restart. All completed benchmark
and diagnostic outputs match exactly. `gmake build`, `gmake fmt`, both diagnostic
dylib builds, and `check-python-boundary --strict` pass.

### Actual host work removed

The new Mach-O has zero `buffer_filled` callsites in `stream_next` (previously
four). The unchanged key helper is called only in the two cache-miss branches.
In the final steady decode of the separate 200/32 worker trace, the interval
before graph entry changes as follows. These are intercepted calls/requested
bytes, not resident-memory or physical-memory-traffic measurements.

| Before graph, one steady worker decode | Old | New |
| --- | ---: | ---: |
| malloc calls / bytes | 9 / 576 | 0 / 0 |
| realloc calls / requested bytes | 6 / 304,182 | 0 / 0 |
| memmove calls / bytes | 27 / 102,798 | 4 / 1,048 |
| memset calls / bytes | 4 / 291 | 0 / 0 |

The remaining 1,048 bytes are token, four positions, the active mask prefix and
the recurrent index. In the stream interval between graph completion and logits
readback, two malloc calls requesting 993,328 bytes and one 993,279-byte memset
become zero. The filled-buffer implementation sets its last byte separately;
this is removal of the full 993,280-byte zero fill and its allocation/header.
HTTP/SSE serialization still allocates small objects. The full-vocabulary logits
copy still exists and was not silently skipped. CPU/GPU state updates remain.

### Worker versus pinned reference

Five alternating pairs, two warm requests per process, milliseconds. This uses
the existing graph timing interposer; the HTTP table below is uninstrumented.
Reference framing and context-reservation differences are unchanged from the
[native trial](native-swiglu-trial.md), so reference wall clocks retain those limits.

| Input/output | Old Align wall | New Align wall | Pinned llama.cpp wall | Paired median reduction | Paired range |
| --- | ---: | ---: | ---: | ---: | --- |
| 64/16 | 562.72 | 561.54 | 542.82 | -0.26% | -2.11% to +0.78% |
| 200/32 | 1300.47 | 1306.32 | 1240.48 | -0.21% | -1.97% to +0.08% |
| 330/64 | 2462.98 | 2458.53 | 2374.75 | +0.09% | -6.82% to +11.98% |

| Input/output | Old/new prefill | Old/new decode | Old/new time outside graph | Old/new startup |
| --- | ---: | ---: | ---: | ---: |
| 64/16 | 125.38 / 125.30 | 425.18 / 427.21 | 10.37 / 9.20 | 1065.81 / 1021.54 |
| 200/32 | 399.11 / 400.85 | 878.59 / 887.58 | 20.96 / 17.97 | 1028.69 / 1041.04 |
| 330/64 | 632.21 / 630.63 | 1792.07 / 1795.19 | 38.49 / 33.02 | 1036.28 / 1032.75 |

Outside-graph time is calculated per sample before taking its median, rather
than subtracting independent medians. It decreases in all five 200/32 pairs
(0.66–7.18 ms) and all five 330/64 pairs (4.72–11.16 ms). This is evidence of
reduced host overhead, not a repeatable whole-request gain. GPU variation can
exceed the saved host time. Startup is unchanged in design; its first pair may
also overlap cleanup of the interrupted wrong-selection harness invocation, and
no startup improvement is claimed.

### Uninstrumented HTTP/SSE

| Input/output / order | Mode | Old median ms | New median ms | Paired median reduction | Paired range |
| --- | --- | ---: | ---: | ---: | --- |
| 64/16 first | HTTP | 564.03 | 561.68 | -0.21% | -1.68% to +1.22% |
| 64/16 first | SSE | 562.29 | 561.97 | +0.02% | -0.21% to +0.48% |
| 200/64 | HTTP | 2248.28 | 2241.77 | +0.04% | -0.40% to +0.79% |
| 200/64 | SSE | 2260.00 | 2284.79 | -0.17% | -1.96% to -0.002% |
| 330/64 | HTTP | 2471.36 | 2478.59 | -0.06% | -0.76% to +0.65% |
| 330/64 | SSE | 2490.83 | 2560.33 | -0.60% | -2.79% to +1.18% |
| 64/16 repeated | HTTP | 565.83 | 565.90 | +0.26% | -1.22% to +0.75% |
| 64/16 repeated | SSE | 572.37 | 568.90 | +0.48% | -0.63% to +1.91% |

The 200/64 SSE candidate is slower in all five pairs; retain that regression
observation. The campaign does not establish an overall speedup. Ratios of the
two arm medians differ from medians of paired percentage changes.

### Where the remaining decode time goes

Separate old/new instrumented worker runs, 200/32, two warm requests then one
recorded request. Every graph has exactly two captured command buffers, successful
completion, and nonzero GPU timestamps bounded by its host graph interval.
Medians below cover that final request's 31 decode graphs.

| Per decode graph | Old ms | New ms |
| --- | ---: | ---: |
| Host graph call | 28.346 | 28.331 |
| Union of GPU command-buffer intervals | 27.600 | 27.689 |
| First GPU start to last GPU end | 27.631 | 27.729 |
| Graph entry to first GPU start | 0.349 | 0.360 |
| Last GPU end to graph return | 0.261 | 0.243 |

Most elapsed decode time is inside the GPU command-buffer intervals. CPU
allocation/key work does not explain the approximately 28 ms/token here. These
intervals still cannot separate quantized matrix arithmetic, memory bandwidth,
GPU barriers or gaps *within* a command buffer. Do not interpret them as 98% ALU
utilization or as a shader-level attribution of the llama.cpp difference.

Startup has another concrete path to investigate. At the pinned ggml source,
`ggml_metal_set_tensor_async` creates `newBufferWithBytes` for each upload,
encodes a blit and commits a command buffer. Align has already copied the data
into its staging buffer, then waits after each upload. This explains why shared
memory does not automatically mean zero-copy initialization. It remains unchanged
in this candidate. A future experiment can select a synchronous host-visible
upload under proven loading ownership, or batch transfers with distinct retained
staging regions; merely removing the wait would allow staging reuse before
transfer completion and is not an acceptable optimization.

## Decision and next hypothesis

Retain this local implementation for demonstrated lower host work and exact
compatibility, with approximately 1 MB extra retained scratch per session. It
is not adopted or advertised as a whole-request acceleration; the HTTP/SSE
regression observation remains open before publication or performance adoption.
The small stream-input duplication is bounded and recorded as an Align request.
Do not weaken tests or remove state/transfer synchronization to improve a number.

Next GPU work should measure real Q6_K output-projection time/traffic and the
FFN's whole gate/up/down interval, rather than repeat host-allocation tweaks or
launch-size sweeps. Separately test the identified startup upload path. Native
FFN fusion remains default-off. CPU/CUDA and broader Gemma semantics remain
explicitly deferred; host scratch/key reuse does not implement those models.
