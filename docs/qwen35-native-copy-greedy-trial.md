# Native Metal copy-command greedy trial

Status: default-off, selectable Qwen3.5 Metal experiment on Apple M1. The
existing mixed native state-copy mode and ordinary ggml graph remain controls.
The measured ggml Metal bundle is unmodified; this trial adds no ggml source
patch. The GPU argmax is correct on the tested paths but has no reproducible
whole-request gain over the already native mixed mode.

## Mechanism and boundary

`ALIGN_LLM_NATIVE_COPY_GREEDY=1` requires both native state and convolution
copy modes. Align selects it at session construction, keys decode graphs,
registers the decode logit output, waits for the native command, validates and
publishes the token, and advances recurrent state only after completion. Prefill
continues to use the ordinary greedy path. The switch refuses conflicting
shared-logit, NEON and in-graph greedy modes before model setup.

ggml still produces Qwen3.5 activations, recurrent sources and the complete
F32 logit row. Align omits the 18 DeltaNet and 18 convolution ggml state-copy
nodes through the preceding selectable native mode. The shim checks the logit
row's F32 contiguous layout, count, range and shared backing, including its
membership in the producer workspace already borrowed by the state-copy
command. The independent Metal helper adds a partial and final reduction to
that command buffer, with a buffer barrier between dependent dispatches. It
returns the first index of the maximum finite logit and rejects nonfinite
rows. It uses 12,288 bytes of reusable partials and a four-byte result rather
than copying the 993,280-byte 2B row to Align for decode selection. The
borrowed Metal view is page-rounded because the pinned ggml allocator's shared
allocation is page-rounded and real decode logits end inside that last page.
The workspace and state allocations remain owned by their existing owners;
the helper owns only views, pipeline objects and bounded scratch. A failed
registration, command or result stops the selected session. No token is
published from a failed command or a prior request.

The input contract depends on F32, layout, count and shared-buffer identity,
not a model name. Another Qwen size may reuse the checked operation if its
actual logit layout qualifies. Gemma still needs its own model semantics,
graph and state integration; this Metal reduction and borrowed-buffer mechanics
can be reused only where its output contract matches. CUDA needs a separate
allocation/stream/event implementation and qualification.

## Correctness and local checks

The final 2B real-model owner compared the selected mode with the same-binary
mixed native control over short/199-token/short retained requests. It found
48 bit-identical complete logit rows, 4,116 bit-identical resident-state
planes, 49 matching graph steps and zero additional ggml `CPY` nodes. The
diagnostic hashes decode logits after the required native completion even
though the selected generation route reads only a four-byte token. The
standalone Metal owner passed odd-shape and 6,144-by-three state copies,
destination guards and descriptor reuse, plus a 65,537-entry cross-group
first-index tie, NaN/infinity rejection and stale-result rejection. No
tolerance was widened. A first version of the borrowed logit view failed on
the real model because it truncated the final page; the checked page-rounded
view and same-workspace admission fixed that failure before timing.

The final 2B and 0.8B generation owners passed 31-, 200- and 330-token
prompts against pinned llama.cpp output, plus six retained requests, invalid
request recovery and one-token early exit. The 0.8B HTTP/SSE owner passed
oracle parity, disconnect/recovery, refusal and restart. Forced native submit
and completion faults were tested on the real 2B model: the ordinary control
completed two tokens, while each selected fault returned the exact `failed`
envelope, no result/token and controlled worker exit 2 with both device and
request failure markers. The final unforced shim was restored byte-for-byte
after these test-only builds.

## Real-model measurement

The model is Qwen3.5-2B Q4_0, GGUF SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
The compared Align modes use one binary (SHA-256
`cc2ef89cdf5dfdf4391f903ad892ddc829b0dfd732d3e0e880764b9bc1ae93c8`),
one real shim (SHA-256
`7ccb01d08d08407c3274121e4531196a18186e7c42052691621ff8b417467dd9`),
the same pack, Model IR, runtime options, unmodified pinned ggml `bb4caa7`
bundle, prompt token IDs, greedy condition and output count. The third of
three repeated worker requests is timed after warmup. Five pairs alternate arm
order. The pinned llama.cpp `bb4caa7` reference consumes the same GGUF and
prompt IDs. The raw [mixed-mode receipt](../eval/benchmarks/qwen35-native-copy-greedy-2026-09-28-wall-mixed.json)
retains all pairs. Paired differences below are control minus candidate;
positive values favor the candidate. They need not equal a difference of arm
medians.

| Input / output tokens | Mixed control median | GPU greedy median | Paired difference | GPU greedy wins |
| --- | ---: | ---: | ---: | ---: |
| 64 / 16 | 528.549 ms | 525.782 ms | +0.558 ms | 3/5 |
| 200 / 32 | 1224.339 ms | 1206.332 ms | -5.583 ms | 2/5 |
| 330 / 64 | 2297.127 ms | 2299.185 ms | +2.452 ms | 3/5 |

The paired ranges are -2.602 to +8.790, -14.582 to +26.628, and -21.439 to
+17.838 ms. There is no stable incremental request gain from argmax. The
candidate beat pinned llama.cpp in 4/5, 4/5 and 5/5 pairs, with paired llama
minus candidate medians +15.523, +26.471 and +96.195 ms. Those wins include
the earlier native state-copy improvement and cannot be credited to argmax.

The [ordinary-mode receipt](../eval/benchmarks/qwen35-native-copy-greedy-2026-09-28-wall-ordinary.json)
uses the same binary and candidate but disables both native state-copy modes
for its control. Ordinary minus candidate paired medians are +35.709,
+83.958 and +177.086 ms at the three workloads, and the candidate wins 5/5
pairs in each. These differences likewise include the earlier native copy
work. Candidate arm medians are 537.485, 1233.150 and 2291.130 ms; ordinary
arm medians are 574.895, 1317.345 and 2466.867 ms. Pinned llama arm medians
are 561.735, 1272.847 and 2389.509 ms.

The separate [phase receipt](../eval/benchmarks/qwen35-native-copy-greedy-2026-09-28-phase-mixed.json)
uses graph and native-wait instrumentation. Correction (2026-09-28): its
schema-2 reducer summed all three retained requests' native waits, so the
following decode graph-plus-wait and native-wait differences are **invalid as
per-request attributions**. The graph-submit, instrumented request wall and
untraced comparison remain separate valid observations. Historical numbers
are retained below without reuse as evidence. Paired mixed-minus-candidate
medians for prefill are +0.111, +0.183 and -0.198 ms; the decode
graph-plus-wait medians are -21.854, -47.947 and -113.366 ms. Native-wait
components are -21.148, -44.405 and -82.926 ms. Instrumented whole-request
differences are +0.694, -7.595 and -37.784 ms. The untraced results above
are the request-speed evidence. The phase clocks omit control-side CPU logit
readback and scan, so they are not an additive decomposition. The control
reads/scans logits before waiting for the native state copy, while the GPU
candidate must wait for the command before it can read the token. Different
overlap remains a hypothesis; the invalid phase reduction cannot measure its
contribution, and a device timeline would be needed for exact attribution.

The [native-command receipt](../eval/benchmarks/qwen35-native-copy-greedy-2026-09-28-native-command.json)
alternated three pairs of real-model workers. Each worker ran three repeated
76-input/16-output requests; the third request contained 15 decode native
commands. The control had 36 state-copy records per command; the candidate
had the same 36 plus one greedy input. Across 45 commands per arm, median GPU
command intervals were 0.734 ms control and 0.754 ms candidate. Per-pair
medians show candidate additions of 0.020, 0.019 and 0.027 ms per command.
Median host waits were 0.729 and 1.056 ms, respectively. These are complete
native-command intervals, not isolated argmax-kernel times or predicted
whole-request savings; the independent local kernel owner checks reduction
semantics but does not time an isolated kernel.

Construction-to-ready medians vary substantially with arm order and cache
conditions. Against mixed control, paired control-minus-candidate medians are
-5.320, -28.327 and -3.779 ms. The candidate has an additional pipeline build
and two bounded buffers, but these startup results do not isolate their cost.
The [five-pair process-footprint screen](../eval/benchmarks/qwen35-native-copy-greedy-2026-09-28-footprint.json)
after three 200/32 requests found paired control-minus-candidate current
physical bytes -49,152, peak bytes +901,096 and ready physical bytes -65,584.
Peak and startup vary more than the explicit scratch; this screen is process
footprint, not total GPU/system memory.

## Decision

Keep the path default-off as a selectable experiment and preserve the mixed
native mode as the preferred tested route. The connected result does not
support making GPU greedy the default on this M1. Its value is a qualified
independent reduction and a concrete counterexample to assuming that removing
a large host readback makes a dependent request faster. Continue GPU work by
testing an Align-owned producer/consumer unit that can reduce the ggml graph to
native-command boundary or expose overlap without violating the recurrent
state and token dependency. Repeat on another Metal generation and Qwen shape
before generalizing; CUDA and Gemma remain unmeasured.
