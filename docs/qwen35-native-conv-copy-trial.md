# Independent Metal convolution-state copy trial

Status: selectable Qwen3.5 Metal experiment on Apple M1. The ordinary ggml
graph and the previously qualified native DeltaNet-only route remain available.
This work uses the unmodified pinned ggml bundle. It adds no ggml source patch.

## Mechanism and scope

`ALIGN_LLM_NATIVE_CONV_COPY=1` requires `ALIGN_LLM_NATIVE_STATE_COPY=1`.
Align identifies the convolution-state producer, expands that source as a graph
root, omits its ggml `CPY` node, and still owns the decode plan, resident parity,
session state, generation and failure policy. The shim validates F32 shape,
layout, shared Metal backing and checked spans. A native Metal compute pass
copies all 18 strided convolution sources into the inactive resident plane
after the ggml producer graph. It shares one command buffer and completion
dependency with the 18 native DeltaNet blits. There is no second state plane,
per-token CPU readback, or model-name predicate. The only reusable new buffer
is a 2,048-byte descriptor array; the Metal pipeline is created once per
selected session. A three-element row copies three 32-bit words per thread;
other widths use the generic element path. The selected session fails rather
than silently changing execution modes if a source cannot be admitted.

The actual 2B Q4_0 model produces F32 convolution state views shaped
`[3,6144,1,1]` with source byte strides `[4,16,98304,98304]`; the resident
destination is contiguous with `[4,12,73728,73728]`. This shape selected the
local three-element row specialization; it is not built into model loading or
the high-level graph. The 0.8B generation owner also exercises the path. A
different Qwen shape can use the same checked descriptor and generic Metal
kernel when its semantics and storage meet the contract. Gemma needs its own
architecture-specific model definition and graph operations; the borrowed
buffer, command, descriptor and completion mechanics can be reused where a
matching operation exists. CUDA requires a separate stream/event and buffer
admission before this seam can be selected there.

## Correctness

On the final row-specialized build, two repeated 2B requests of 16 tokens each
produced 32 identical complete 993,280-byte logit-row hashes and 2,688
identical resident-state plane hashes between native DeltaNet-only and mixed
copy modes. The state tracer waits for native completion before reading each
plane. Both modes produced the same text and token counts. Each of the 30
decode graphs removes exactly 18 additional `CPY` nodes in mixed mode. Invalid
mode values and convolution mode without native DeltaNet mode were refused
before session readiness. The 2B and 0.8B generation owners passed 31-, 200-
and 330-token inputs, retained requests and malformed-request recovery against
pinned llama.cpp greedy output. No comparison tolerance was widened.

The standalone Metal owner passed a 37-row, five-element odd shape through the
generic path and a 6,144-row, three-element shape through the specialization.
It checked every copied byte, destination guards, descriptor reuse and invalid
stride refusal. Test-only native submit and completion faults were each run in
mixed mode on the real 2B model. In both cases the ordinary graph completed
two tokens; the selected native mode emitted the exact `failed` envelope,
published no result or token, and exited 2 after the matching native and
request-path markers. This tests failure propagation, not a hardware fault.

## Measurement

The measured model is Qwen3.5-2B Q4_0, GGUF SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
All arms use the same saved Align binary, pack, Model IR, runtime options,
prompt token IDs, greedy conditions and unmodified pinned ggml `bb4caa7`
bundle. The two Align arms in each campaign differ only in explicit native
copy flags and share the same shim digest. The reference is pinned llama.cpp
`bb4caa7` on the same GGUF and prompt IDs. Each worker processes three equal
requests after warm-up; the third is timed. Five pairs alternate execution
order. An instrumented phase campaign is kept separate from untraced request
measurements. Startup is construction to ready and is subject to OS file-cache
variation. A process footprint sample does not represent total GPU/system
memory.

The first final untraced campaign isolates the convolution addition against
the DeltaNet-only route. The complete
[receipt](../eval/benchmarks/qwen35-native-conv-copy-2026-09-27-wall-delta.json)
retains the five individual pairs per workload and the same-arm pinned
llama.cpp results. `Delta minus mixed` is the median of paired differences,
so it need not equal the difference of arm medians.

| Prompt / output | Delta-only median | Mixed median | Pinned llama median | Delta minus mixed | Mixed wins vs Delta / llama |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64 / 16 | 518.668 ms | 511.834 ms | 543.482 ms | +6.412 ms | 5/5 / 5/5 |
| 200 / 32 | 1199.293 ms | 1187.001 ms | 1254.480 ms | +12.673 ms | 5/5 / 5/5 |
| 330 / 64 | 2241.344 ms | 2215.344 ms | 2362.604 ms | +14.190 ms | 5/5 / 5/5 |

The individual Delta-minus-mixed ranges were +5.664 to +9.460 ms,
+8.967 to +29.085 ms, and +3.105 to +40.980 ms. Both arms used Align binary
SHA-256 `61f55dbbf00824159b07c6bfe6c6a38aae66f856e9045d6a206c80ba85e9ae4e`
and real shim SHA-256
`27f2d1995a86b42b03e4288ccfbe773051c35b9f0c9083b6909db8488e476c4a`.
The saved executable's dynamic library identity names that exact shim path;
the measurement caller verifies the binding before timing.

The second final untraced [receipt](../eval/benchmarks/qwen35-native-conv-copy-2026-09-27-wall-ordinary.json)
compares that same mixed mode with the ordinary ggml graph. It includes the
DeltaNet-copy improvement already established by the previous trial, so its
entire difference must not be credited to the convolution change alone.

| Prompt / output | Ordinary Align median | Mixed median | Pinned llama median | Ordinary minus mixed | Mixed wins vs ordinary / llama |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64 / 16 | 576.102 ms | 534.656 ms | 558.410 ms | +39.954 ms | 5/5 / 5/5 |
| 200 / 32 | 1312.239 ms | 1227.373 ms | 1277.044 ms | +86.327 ms | 5/5 / 5/5 |
| 330 / 64 | 2474.478 ms | 2296.657 ms | 2399.863 ms | +177.939 ms | 5/5 / 5/5 |

The paired ordinary-minus-mixed ranges were +19.764 to +44.286 ms,
+64.635 to +92.521 ms and +147.844 to +181.848 ms. Pinned llama minus
mixed paired medians were +23.834, +42.577 and +103.205 ms. Construction to
ready was slower for the mixed Align arm than ordinary Align in this campaign:
arm medians were 1323.700 versus 1281.291 ms, 1305.101 versus 1230.245 ms,
and 1277.016 versus 1250.352 ms. Pinned llama startup medians were about
411–413 ms. These startup differences include pipeline compilation and
uncontrolled OS cache conditions; they are not isolated shader build costs.

The final [phase receipt](../eval/benchmarks/qwen35-native-conv-copy-2026-09-27-phase-delta.json)
uses a diagnostic graph interposer and compares DeltaNet-only to mixed mode.
Paired medians below are control minus mixed. This graph timer includes the
ggml producer and native submission, but the native completion may occur
later; it is not a shader-only clock or a full decode decomposition.

| Prompt / output | Prefill graph | Decode graph | Whole request | Mixed whole-request wins |
| --- | ---: | ---: | ---: | ---: |
| 64 / 16 | +0.121 ms | +9.440 ms | +9.209 ms | 4/5 |
| 200 / 32 | -0.433 ms | +11.593 ms | +7.552 ms | 3/5 |
| 330 / 64 | -0.218 ms | +38.501 ms | +28.950 ms | 5/5 |

The instrumented run retained whole-request adverse pairs of -1.671 ms at
64/16 and -19.562 ms at 200/32. Prefill differences were small and mixed,
as expected from a decode-only graph change. The untraced comparisons above
are the request-speed evidence and retain no adverse pairs in their tested
workloads. No universal improvement claim follows from three input/output
conditions on one M1.

The five-pair [process-footprint receipt](../eval/benchmarks/qwen35-native-conv-copy-2026-09-27-footprint.json)
compares DeltaNet-only and mixed mode after three 200/32 requests in each
worker. The paired median control-minus-mixed current physical footprint was
0 bytes after the requests; peak was +24 bytes, far below this instrument's
resolution for claiming a real difference. Ready-time current footprint was
98,280 bytes larger in mixed mode by paired median. The 2,048-byte descriptor
buffer is the only explicit additional data buffer, but a compiled Metal
pipeline also consumes driver-managed memory. Process footprint does not
measure total system/GPU use. Startup was 63.935 ms slower for mixed mode by
paired median in this screen; the untraced request campaigns also showed
variable startup regressions. No model-sized duplicate allocation was added.

A separate [native-command receipt](../eval/benchmarks/qwen35-native-conv-copy-2026-09-27-native-command.json)
used one worker per mode and three repeated 16-token requests, with actual 2B
state buffers and `ALIGN_LLM_NATIVE_COPY_TRACE=1`. The third request contained
15 decode native commands. DeltaNet-only commands contained 18 blits; mixed
commands contained those 18 blits plus 18 strided copies and one compute
dispatch. Median GPU intervals were 0.632 ms versus 0.736 ms per command,
respectively. The extra 0.104 ms native interval is an instrumented local
observation, not the net request cost: the mixed graph has 18 fewer ggml copy
nodes per decode. Host wait medians were 0.533 versus 0.771 ms, also diagnostic
rather than additive latency savings.

## Decision and limits

Keep the mixed path as a selectable experiment and retain the ordinary ggml
graph and DeltaNet-only native path as controls. The real-model correctness,
failure propagation and untraced connected gains support further use of this
independent Metal seam. The current evidence is from one Apple M1, one 2B
quantization and the 0.8B generation owner; it does not establish a default
for every Metal generation or Gemma, or prove total GPU memory parity. The
additional startup cost matters for short-lived sessions. A separate host
and a longer-running workload should be qualified before making this the
default. Next, target a larger Align-owned producer/consumer subgraph so the
ggml graph-to-native command boundary is crossed less often, while continuing
to compare the selectable paths on identical workloads. No ggml source patch
is required or proposed as the product goal.
