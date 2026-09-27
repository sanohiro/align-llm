# Qwen3.5 in-graph Metal greedy trial (2026-09-27)

## Decision

Keep `ALIGN_LLM_GRAPH_GREEDY=1` as an **opt-in experiment**. The hierarchical
argmax is faster on captured real logits, the real model and state owners pass,
and the final 330/64 worker request improves by a paired median 5.035 ms
(4/5 pairs). The final same-binary HTTP/SSE gains at 330/64 are 13.916 and
5.769 ms, but HTTP includes a 70.021 ms adverse pair. The candidate is still
slower than pinned llama.cpp on all worker request medians. These observations
support further testing, not a production default or a competitive win. No
fixed percentage floor was used.

## Boundary and correctness

Align selects the mode, builds the Qwen3.5 graph, validates the selected token,
owns retained state and drives ordinary and streaming generation. The ordinary
full-logit graph remains the default and rollback. The thin shim adds a checked
`ggml_argmax` node and refuses mode `1` unless the loaded Metal plugin exports
the trial marker. The separate pinned ggml Metal patch replaces only contiguous
single-row F32 argmax at lengths at least 8,192. Its first 256-thread stage
reduces 1,024 logits per group; its second stage reduces the partials in the
same graph's encoder. It allocates 12 bytes per group after the four-byte output
(2,916 scratch bytes for the 248,320-word 2B row). Other operations and shapes
retain ggml. The special case uses shape and type, not a model-name check.

Three actual 2B output rows selected tokens 16, 220 and 17 exactly. Independent
8,192-, 248,319- and 248,320-word cases chose the first equal maximum and
returned the invalid sentinel for NaN and infinity. The real 2B and 0.8B
generation owners passed 31-, 200- and 330-token prompts, oracle token output,
six retained requests and recovery. The 2B HTTP/SSE serving owner passed output,
usage, refusal, disconnect and recovery checks. A 200/3 trace compared 336
resident-state plane hashes and rendered output exactly between graph mode off
and on. Malformed, conflicting and unpatched-plugin requests exited before
session readiness. A short-vocabulary geometry was also rejected with zero
weight-set calls, before the unsupported graph could be prepared. No tolerance
or model arithmetic was changed.

An independent host-call trace of the same 200/3 request recorded three
993,280-byte logit gets in the control and three four-byte gets in the trial:
2,979,840 versus 12 bytes. A Metal command-buffer interposer recorded 1,377
buffers and four graph boundaries in each arm, including construction and
upload. These intrusive traces establish the readback and command-count
boundary, not speed. Scratch is graph owned, released with its output, and
reused through the existing prepared-graph lifecycle; the mode adds no retained
request-global state.

## Local and connected measurements

Apple M1, 16 GiB unified memory; unchanged Qwen3.5-2B Q4_0 GGUF SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`;
Align `b20429be50d6ab889496a0589143320683b29aeb`; pinned ggml/llama.cpp
`bb4caa7540188872173c44d161602d9271386413`. The final argmax-only Metal
bundle ID is `8ae9b7ac9429d393c48f93f54bbe36417f2c0dd788937f307965c5e20b447965`,
with patch SHA-256
`7b1fde56f48aa9190a76be061e39eb834de389664c0375691a7b7e1067f800aa`.
The old Align binary is the exact prechange `9dae952a` build. Both native arms
use the same GGUF, Alignpack, Model IR, prompt IDs, generated counts, quantized
weights, 128-token prefill chunks, final-only prefill logits, and native SwiGLU
off. The candidate changes no quantization or precision. Five alternating
pairs follow two warmups in each condition. The pinned llama.cpp driver uses
the same token IDs and generated count. Its elapsed clock is inside its native
request loop; Align's worker wall clock includes its session protocol, so the
cross-engine numbers are directional rather than an identical API boundary.
The final repaired candidate binary SHA-256 is
`b62a2d5d7e88dee85b4f3f672b4b4dca15a74d24fc5e89df5791cf277c6a0450`.
Its admission repair affects vocabularies below 8,192, outside this 2B run.
The measurement helper now verifies each retained bundle patch against its
manifest digest; a deliberately altered patch was refused. Earlier receipts
remain unchanged and identify their earlier binary.

The [local receipt](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/local-timing.json)
uses captured real row 0, a reused graph, five warmups and 50 synchronized
graph-compute-plus-four-byte-read samples per process. Five alternating process
pairs compare stock Metal argmax in the old plugin with the patched plugin;
both select the same captured token. Process-median times were 0.772–0.791 ms
old and 0.273–0.280 ms new; paired median reduction was **0.505 ms**, 5/5.
This is the local operation boundary, not whole-request speed.

The [final same-binary worker receipt](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/post-review-graph-only.json)
isolates graph mode. Times are ms; paired is the median of each control minus
candidate pair, so it can differ from the difference of arm medians.

| Input/output | Control request | Graph request | Pinned llama.cpp | Paired / graph wins | Control/graph prefill | Control/graph decode |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 64/16 | 563.247 | 563.387 | 547.308 | −1.644 / 2 of 5 | 123.949 / 124.568 | 423.035 / 427.381 |
| 200/32 | 1287.981 | 1286.032 | 1250.582 | +1.691 / 4 of 5 | 383.485 / 383.621 | 876.995 / 882.003 |
| 330/64 | 2431.846 | 2427.672 | 2360.487 | +5.035 / 4 of 5 | 597.843 / 598.307 | 1786.233 / 1795.853 |

The 330/64 paired request range was −3.952 to +15.311 ms. Graph phase clocks
include synchronization, but exclude the token read/choice and protocol. The
final graph's decode median increased by 9.620 ms at 330/64 while request wall
time fell by 4.174 ms between arm medians. The added GPU reductions cost time;
the saved full-row readback and CPU selection offset that cost. This is a
boundary inference, not an attributed shader-time measurement. The
[exact old-binary versus final-binary receipt](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/post-review-before-after.json)
gave paired request changes +1.232 (4/5 wins), +7.411 (3/5), and +10.499 ms
(4/5) at the three lengths. The 64/16 range includes a −80.397 ms candidate
outlier. The graph-only startup result is not stable enough for a claim.

The [final same-binary HTTP/SSE receipt](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/post-review-http-sse.json)
checks actual serving, with exact output, finish reason and usage in every
sample. Paired control-minus-graph request differences in ms:

| Input/output | HTTP / wins | SSE / wins |
| --- | ---: | ---: |
| 64/16 | +4.034 / 4 of 5 | +2.238 / 3 of 5 |
| 200/32 | +1.446 / 5 of 5 | +5.487 / 4 of 5 |
| 330/64 | +13.916 / 4 of 5 | +5.769 / 5 of 5 |

At 330/64, HTTP ranged −70.021 to +46.013 ms and SSE +2.381 to +24.888 ms.
Final control/candidate server construction took 1.249/1.285 seconds in one
order-dependent observation. In the earlier campaign one candidate construction
took 11.418 seconds; a separate first Metal library load took 10.232 seconds,
versus 0.011–0.031 seconds in later local processes. Cache and process state
were not controlled for cold launch, so these are not a stable startup claim.
The graph adds about 2.9 KiB of logical scratch per 2B output; process physical
memory was not isolated.

## Combination and limits

The [pre-repair combined receipt](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/final-combined.json)
compares exact old Align defaults with graph greedy plus the already implemented
synchronous weight upload and final-layer one-row FFN, still with native SwiGLU
off. Warm request paired changes were +5.261, +4.472, +15.256 ms at 64/16,
200/32, 330/64; wins were 5/5, 4/5, 5/5. The 200/32 range includes a −59.351
ms outlier. Construction-to-ready candidate medians were 492, 493 and 495 ms
versus old Align 1,038, 1,100 and 1,030 ms; pinned llama.cpp medians were 429,
434 and 443 ms. This startup effect comes from the pre-existing synchronous
upload option and its warm cache conditions, not from argmax. The combined
request remained slower than llama.cpp at all three medians.

The first argmax-only bundle campaigns are preserved as
[worker](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/final-graph-only.json),
[old/new](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/final-before-after.json)
and [HTTP/SSE](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/final-http-sse.json)
receipts. Their 330/64 paired worker gain was +21.843 ms (5/5), while final
repetition gave +5.035 ms (4/5); first HTTP/SSE gains were only +1.929/+1.700
ms (3/5 each). Keep both rather than selecting the favourable run.

An earlier source-equivalent **diagnostic** bundle combined the FFN and argmax
patches before their build inputs were split. Its
[graph-only worker](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/diagnostic-combined-bundle-graph-only.json),
[native-FFN-plus-graph worker](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/diagnostic-graph-plus-native-ffn.json)
and [HTTP/SSE](../eval/benchmarks/qwen35-ingraph-greedy-2026-09-27/diagnostic-http-sse.json)
receipts are retained rather than selected away. Its graph-only 200/32 paired
result was +26.899 ms, but included a +276.121 ms outlier; the later isolated
bundle campaigns did not reproduce that magnitude. Its long HTTP result ranged −175.770 to
+303.471 ms. These runs reinforce the default-off decision.

The operation, scratch rule, admission marker and Align graph choice can be
reused for another Qwen size when its semantic graph and a contiguous F32
single-row output are admitted. A different vocabulary length changes the
number of reduction groups automatically. Gemma needs its own model definition,
tokenizer, activation, normalization, attention, position and state admission;
matching output shape alone is insufficient. CUDA requires a separate backend
implementation and qualification. The old ggml graph remains available for
all of these cases.

The next bounded hypothesis is to consume a Q6_K output projection's partial
maxima in the same producer, eliminating the first additional reduction
dispatch and full-logit materialization when greedy output alone is needed.
One compact final reduction would remain.
It must first match captured real Q6_K weights/activations and the full-logit
oracle, then pass the same state and HTTP/SSE owners before a request-speed
claim. The previous one-to-one Q6_K rewrite and post-sync argmax losses do not
answer this fusion question. No fused-projection result is claimed here.
The [FlashSampling paper](https://arxiv.org/abs/2603.15854) demonstrates the
general fused LM-head reduction idea on NVIDIA datacenter GPUs; it supplies no
M1/Q6_K performance evidence, so the local real-weight screen remains necessary.

## Reproduction

Build the pinned ggml bundle with `scripts/gpu_backend_recipe.py --backend
metal --ingraph-argmax --source PINNED_GGML --output NEW_DIRECTORY`, then build
Align with `ALIGN_LLM_GGML_INCLUDE`, `ALIGN_LLM_GGML_LIB` and `gmake build`.
Use the documented Qwen3.5 2B/0.8B generation and 2B serving owners with
`ALIGN_LLM_GRAPH_GREEDY=1`. `scripts/measure-native-swiglu --native-disabled`
and `scripts/measure-host-reuse` accept the checked execution setting
`graph_greedy`; their receipts bind binary, bundle, options, model and patch
identities. The local probe is `scripts/bench-metal-ingraph-argmax.cpp`.
