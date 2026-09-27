# Qwen3.5 hierarchical Metal greedy trial (2026-09-27)

## Decision

Withdraw the post-synchronization GPU argmax integration. It selects the correct
token and removes the full-logit `ggml_backend_tensor_get`, but the connected
2B request comparison does not show a repeatable improvement. A new command
buffer, encoder and wait are paid for each generated token. The ordinary
Align-owned greedy path remains the control. The predeclared contract and
cost ceiling are in [the runtime performance plan](specs/gpu-runtime-performance.md).
The candidate [integration patch source](../eval/benchmarks/qwen35-hierarchical-greedy-2026-09-27/integration.patch.b64),
[Metal helper](../eval/benchmarks/qwen35-hierarchical-greedy-2026-09-27/helper-source.mm),
and [local screen](../eval/benchmarks/qwen35-hierarchical-greedy-2026-09-27/bench-post.mm)
are retained with the receipts. Decode the patch source with `base64 -D`, then
apply it to the clean `32ad975e`
checkpoint and place the helper at `scripts/metal_hier_greedy.mm`. Compile it
as an Objective-C++ dynamic library with Foundation and Metal, using the pinned
llama.cpp `ggml/include`, `ggml/src` and `ggml/src/ggml-metal` include roots;
the local integration used `clang++ -O3 -std=c++17 -fobjc-arc -dynamiclib`.
The model/pack/IR, options and oracle identities are
recorded below and in the receipts; local logs remain under the Git common
directory. No experimental runtime flag or helper is shipped from this trial.

## What was tested

The pinned ggml Metal argmax uses one threadgroup for a 248,320-element Qwen3.5
row. The trial helper used two reductions over the **actual shared Metal output
buffer**, 1,024 values per first-stage group and a second-stage group over the
partial maxima. Its size comes from the row length, not a model name. It
preserved Align's lowest-index tie rule and refusal of every NaN or infinity.
The runtime trial created one queue, pipelines and at most 12 KiB of partial
scratch per GPU owner, reused them across requests, and waited for each command
buffer before returning one I32 token to Align. It did not copy the full row,
skip ggml graph synchronization or change model computations. It added roughly
8 KiB to the device owner's host structure; pipeline memory was not isolated.

The independent local screen used three captured real 2B F32 rows. Their
SHA-256 digests are `1883760d6c55814ae77496aae421897141831eb329e1b8ce8ed0d4949f1cda99`,
`bbb120bd05d31b387c651fd941027ac9a9943aed620c353b6593945ae7321bac`,
and `8282380daf93d31c42f74986d55036c8a7e4a430da0cd4cbbf35e06602f1a335`.
The diagnostic and integrated helper had byte-identical Metal kernel source.
All real rows, constructed equal maxima, NaN and infinity checks passed before
timing. A GPU blit refreshed the shared row in both arms. With the extra
post-sync command buffer used by the actual integration, 100 warmups and 100
alternating measured pairs gave these medians in milliseconds:

| Captured row | CPU scan | Hierarchical GPU | Median paired reduction | Faster pairs |
| --- | ---: | ---: | ---: | ---: |
| 0000 | 0.5711 | 0.5010 | 0.0707 | 90/100 |
| 0001 | 0.5639 | 0.4974 | 0.0709 | 91/100 |
| 0002 | 0.6188 | 0.5199 | 0.1034 | 94/100 |

Putting both reductions into the producing command buffer won 96–97 of 100
local pairs by 0.230–0.283 ms, but that scheduling was not available through
the existing output/readback boundary. These are local screens, not inference
speed claims. The post-sync [raw pairs](../eval/benchmarks/qwen35-hierarchical-greedy-2026-09-27/post-sync.csv)
retain every observation.

## Real-model correctness and measurement

Apple M1, unchanged Qwen3.5-2B Q4_0 GGUF SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`,
Align `b20429be50d6ab889496a0589143320683b29aeb`, pinned ggml/llama.cpp
`bb4caa7540188872173c44d161602d9271386413`. Both Align arms used the
same pack, Model IR, Metal bundle, options, 128-token prefill, full final logits,
GGUF tensor formats and generated token counts. Native SwiGLU was disabled. The old
Align binary was `57fd7a6b`; the same-binary HTTP/SSE comparison changed only
the trial flag. Two warmups preceded five alternating measured pairs per case.
Startup was construction-to-ready with OS cache uncontrolled. Graph phase
clocks include synchronization; they are not shader-only times. Desktop
activity was uncontrolled, and individual pairs varied materially.

Both 2B and 0.8B generation owners matched pinned llama.cpp at 31, 200 and
330 prompt tokens and in six retained requests. The 2B HTTP/SSE owner passed
exact output, usage, disconnect/recovery and malformed-request checks. The
real 2B trace matched all 336 prior resident-state plane hashes exactly;
logit graph computation was unchanged. The output readback interposer observed
zero `ggml_backend_tensor_get` calls for the three sampled logits rows; the
helper read only its four-byte token. No numerical tolerance was changed.

Worker medians are milliseconds. `paired` is the median of each control minus
candidate pair, so it can disagree with the difference of arm medians. Full
startup, prefill, decode and output observations and binary digests are in the
[worker receipt](../eval/benchmarks/qwen35-hierarchical-greedy-2026-09-27/worker.json).

| Input/output | Old Align request | Trial request | Pinned llama.cpp | Paired / trial wins | Old/trial prefill | Old/trial decode |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 64/16 | 633.122 | 642.807 | 617.447 | -12.494 / 1 of 5 | 129.799 / 133.189 | 488.119 / 498.576 |
| 200/32 | 1403.530 | 1386.235 | 1373.976 | -24.470 / 1 of 5 | 393.453 / 398.302 | 977.486 / 958.399 |
| 330/64 | 2763.146 | 2718.405 | 2799.845 | +43.960 / 3 of 5 | 625.122 / 663.040 | 2089.571 / 2019.870 |

The [same-binary HTTP/SSE receipt](../eval/benchmarks/qwen35-hierarchical-greedy-2026-09-27/http-sse.json)
retains two warmup pairs and five measured pairs for each mode. Every response
and actual processed token count matched. Request medians and paired changes:

| Input/output | Mode | Control | Trial | Paired / trial wins |
| --- | --- | ---: | ---: | ---: |
| 64/16 | HTTP | 706.071 | 679.401 | +11.475 / 3 of 5 |
| 64/16 | SSE | 625.488 | 665.826 | -40.338 / 1 of 5 |
| 200/32 | HTTP | 1387.875 | 1422.052 | -17.030 / 2 of 5 |
| 200/32 | SSE | 1439.191 | 1461.724 | -17.590 / 2 of 5 |
| 330/64 | HTTP | 2638.709 | 2672.980 | -14.736 / 1 of 5 |
| 330/64 | SSE | 3066.166 | 3019.342 | -105.430 / 2 of 5 |

SSE first-content-token paired medians were -7.873, -9.111 and -3.704 ms in
the three conditions. The 330/64 SSE paired range was -556.820 to +748.718 ms,
so its arm medians do not support a gain. Startup was measured separately; the
same-binary servers initialized in 1576.981/1237.519 ms, an uncontrolled
single observation, and worker startup pairs were mixed. Host RSS and total
GPU memory were not isolated beyond the bounded explicit allocations above.

The local screen's small advantage does not survive the separate queue and
request variability. An in-graph hierarchical argmax could remove that extra
boundary, but would need a backend scheduling and scratch-lifetime contract and
another real-model trial. A simpler SIMD scan of the already shared F32 row is
the next bounded hypothesis. Its independent real-row local screen passed
tie/NaN/infinity semantics and won 96–98 of 100 pairs by about 0.25 ms; see
the [raw screen](../eval/benchmarks/qwen35-hierarchical-greedy-2026-09-27/neon-screen.csv).
This does not yet establish an inference improvement.
