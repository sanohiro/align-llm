# Independent Metal prefill state-copy trial

Status: retained as a default-off experiment on Apple M1. The faster mixed
decode mode remains the preferred tested path. The ordinary ggml graph is the
fallback. No ggml source patch is used.

## Execution boundary

`ALIGN_LLM_NATIVE_PREFILL_STATE_COPY=1` requires both
`ALIGN_LLM_NATIVE_STATE_COPY=1` and `ALIGN_LLM_NATIVE_CONV_COPY=1`. Align selects
the mode before weight allocation, keys the graph separately, expands the 18
DeltaNet and 18 convolution state sources as roots in each prefill graph, and
omits only their ggml `CPY` nodes. The checked C shim registers F32 contiguous
or strided views over borrowed shared Metal allocations. The independent Metal
command performs 18 blits and one compute dispatch for 18 strided copies after
the ggml producer graph. Align waits for completion before publishing recurrent
parity or starting another chunk, in both ordinary and streaming generation.
The native command, descriptor and views reuse the existing decode-owned
resources; there is no second resident state plane or model-sized conversion.

The actual 2B Q4_0 prefill has 18 contiguous 1 MiB DeltaNet copies and 18
convolution copies shaped `[3,6144,1,1]` in each chunk. Convolution source row
strides are 524 bytes at 128 tokens and 296 bytes at 71 tokens; destinations
have 12-byte rows. The shim checks shape, type, span and shared backing rather
than a Qwen model name. ggml still executes the model graph, produces these
source tensors and handles other prefill work. This seam does not yet make the
full model independent of ggml.

## Correctness and failure

The final 2B test compared mixed decode with the prefill experiment over a
short / 199-token / short sequence. The 199-token request exercised actual
128- and 71-token prefill chunks. All 48 complete 993,280-byte logit rows and
4,116 resident-state planes matched by SHA-256 after each of 49 graphs. Every
prefill graph removed exactly 36 `CPY` nodes; decode topology was unchanged.
Invalid values and unmet mode dependencies were refused before session ready.
The 2B and 0.8B generation owners compared 31-, 200- and 330-token requests,
retained sessions and recovery with pinned llama.cpp. The 0.8B serving owner
also passed SSE, disconnect and restart recovery. No tolerance was widened.

Test-only submit and completion failures at the first real prefill native
command each produced the controlled `failed` envelope with no result or token
and worker exit 2. The ordinary graph control still generated two tokens.
During phase instrumentation, an extra decode completion call and a missing
streaming prefill completion call were found. Both were repaired before the
final binary and all measurements reported below. The initial timings and
incomplete phase receipts remain in the uncommitted Git diagnostic directory,
not in the accepted results.

## Real-model measurement

All arms use the same final Align binary (SHA-256
`6546406a2cd72cfae9583387b711d9d3d3a6ce723aff1c51f02af7e2a98b0ef0`),
shim (SHA-256
`2640eefa98a3fd025f7454e99a6da37c1b6f92eb1bcb1ce3898be7a96993d33c`),
Qwen3.5-2B Q4_0 GGUF (SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`),
pack, Model IR, runtime options, token IDs and greedy settings. The reference
is pinned llama.cpp `bb4caa7` on that GGUF and those IDs. Each Align worker
executes three identical requests after construction; the third is timed.
Five pairs alternate arm order at each length. Startup is construction to
ready with uncontrolled OS file cache; model loading is included but was not
timed separately. The untraced worker wall clock is the
connected performance result; instrumented clocks are kept separate.

The [mixed-decode comparison](../eval/benchmarks/qwen35-native-prefill-copy-2026-09-28-wall-mixed.json)
isolates the prefill addition. Differences are paired control minus candidate
medians, so they need not equal differences of the arm medians.

| Prompt / output | Mixed decode median | Prefill experiment median | Pinned llama median | Mixed minus prefill | Prefill wins vs mixed / llama |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64 / 16 | 538.584 ms | 540.926 ms | 561.290 ms | -4.449 ms | 2/5 / 4/5 |
| 200 / 32 | 1228.878 ms | 1242.131 ms | 1265.346 ms | -17.033 ms | 1/5 / 4/5 |
| 330 / 64 | 2292.974 ms | 2318.109 ms | 2398.259 ms | -17.426 ms | 1/5 / 5/5 |

The short case is variable; both longer cases favor the mixed decode control
in four of five pairs. The prefill experiment still beats pinned llama.cpp in
13 of 15 pairs, but that does not credit the prefill addition. The separate
[ordinary Align comparison](../eval/benchmarks/qwen35-native-prefill-copy-2026-09-28-wall-ordinary.json)
shows the candidate faster in all 15 pairs, with paired medians of +32.808,
+69.805 and +127.334 ms at the same three lengths. That comparison includes
the already established independent decode gains and therefore cannot justify
selecting native prefill. Pinned llama.cpp construction medians were about
412-428 ms versus roughly 1.06-1.16 seconds for Align across these campaigns;
the startup gap remains.

The [phase receipt](../eval/benchmarks/qwen35-native-prefill-copy-2026-09-28-phase-mixed.json)
records synchronized ggml graph calls, including native submission in the
candidate, and native completion waits separately.
It excludes CPU readback and sampling and changes timing through logging. Arm
medians below are milliseconds per request, not pairwise differences.

| Prompt / output | Mixed graph/submit prefill | Candidate graph/submit prefill | Candidate native prefill wait | Mixed total prefill | Candidate total prefill |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64 / 16 | 123.418 | 118.410 | 19.101 | 123.418 | 137.626 |
| 200 / 32 | 382.620 | 372.117 | 53.755 | 382.620 | 425.447 |
| 330 / 64 | 596.613 | 580.960 | 79.198 | 596.613 | 660.939 |

The graph/submission call savings are smaller than the additional completion wait. In a
single [diagnostic 199/2 request](../eval/benchmarks/qwen35-native-prefill-copy-2026-09-28-native-command.json),
the two 36-record prefill commands reported
GPU intervals of 1.861 and 0.900 ms, but host completion waits of 9.479 and
6.392 ms. This single trace is an attribution clue, not a substitute for the
five-pair request result. Each native command is submitted after ggml has
already completed its producer graph, so the separate command and necessary
dependency boundary are the leading explanation for the regression. The exact
contribution of queue scheduling versus CPU wake-up remains unmeasured.

The five-pair [process-footprint screen](../eval/benchmarks/qwen35-native-prefill-copy-2026-09-28-footprint.json)
sampled workers at readiness and after three 200/32 requests. Its paired
control-minus-candidate current physical footprint median after requests was
+0.312 MiB, with individual differences from -1.719 to +1.531 MiB. Peak and
RSS differences also changed sign. The screen resolves no process-memory
benefit or cost; it cannot measure total GPU/system memory. Startup differences
also changed sign, from -98.102 to +65.926 ms in control-minus-candidate
terms, so this screen does not isolate a setup gain.

## Decision and transfer

Do not enable the prefill option by default on this host. Keep the selectable
experimental route for testing a larger Align-owned producer/consumer boundary
and retain mixed decode and ordinary ggml as direct controls. The observed
prefill regression calls for reducing the boundary cost or replacing a larger
subgraph, rather than deleting a required wait. The useful next hypothesis is
to produce and publish recurrent state within one Align-owned Metal execution
unit, then compare that complete unit with the current ggml prefill graph.
This does not assume an independent one-to-one copy kernel must win.

The checked shared-buffer descriptors, command reuse, completion and failure
handling can serve another Qwen size when its actual semantics, F32 layout and
storage pass admission. Gemma needs its own model semantics, graph and state
operations before reusing a matching device seam; its differences cannot be
reduced to shape alone. A CUDA version needs a separate buffer and stream/event
implementation and native Qwen3.5 admission. A second Metal host, total
GPU/system memory and cache-dependent performance remain unmeasured.
