# Qwen3.5 shared Metal logits trial (2026-09-27)

## Decision

Continue as a default-off experiment. The real 2B output is already in a Metal
shared buffer. Borrowing that output removes the 993,280-byte `tensor_get` copy
and preserves Align's finite check and first-index tie rule, but the five-pair
request measurements do not establish a repeatable speed gain. It does not
close the gap to pinned llama.cpp. The ordinary copied path remains the default.
The contract and cost ceiling were fixed in
[`gpu-runtime-performance.md`](specs/gpu-runtime-performance.md) before the trial.

## Boundary and correctness

`ALIGN_LLM_SHARED_LOGITS=1` is selected once by the Align Qwen3.5 session. The
shim validates a completed graph output, one contiguous F32 row, exact extent,
shared Metal storage, and pointer bounds. It returns a borrowed pointer only;
`ggml_ffi` ties the view to `GpuDevice` and scans it immediately with the same
Align greedy implementation as the copied path. `runtime_execution.compute`
still synchronizes graph execution. Graph construction, GPU scheduling, weights,
KV state, generation loop, and request cleanup remain with their current owners.
Private/other storage refuses the opt-in mode; `0` or absence uses the original
readback. The probe of the actual 2B output found `MTL0` storage and equality of
all 993,280 bytes between `tensor->data` and the copied readback.

The unchanged `57fd7a6b` binary and this branch produced three bit-identical
full-vocabulary 2B logit vectors and 336 identical resident-state plane hashes.
The borrowed mode's three 993,280-byte views hashed identically to the old
binary, with zero `ggml_backend_tensor_get` calls for those outputs. The real
2B and 0.8B generation owners passed normal, streaming and retained-request
cases against pinned llama.cpp; the 2B HTTP/SSE owner passed. Invalid flags
(`""`, `2`, `true`, `01`) refused before session readiness. An interposed
`MTL0_Private` storage name was refused by mode `1` while mode `0` completed.
Generic Qwen/OLMoE generation smoke passed after the greedy function was
moved to a pure shared module. No tolerance was changed. These results do not
establish safety for a future non-shared Metal allocator or another backend.
The mode replaces the 993,280-byte per-request or per-session host scratch
buffer with four bytes; it adds no retained GPU output or temporary buffer.
Process RSS and total physical-memory change were not isolated.
The comprehensive review found that the first implementation scanned
intermediate prefill outputs when the supported full-logits mode was selected.
The repair scans only the final chunk; the copied mode still performs its
historical intermediate readbacks. After the repair, the 2B generation owner
passed 31-, 200- and 330-token prompts and six retained requests with full
prefill logits enabled. A same-binary 200/16 HTTP/SSE check passed all five
normal and five streaming pairs with exact output.

## Real-model measurement

Apple M1; Qwen3.5-2B Q4_0 GGUF SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`;
Align `b20429be50d6ab889496a0589143320683b29aeb`; pinned ggml/llama.cpp
`bb4caa7540188872173c44d161602d9271386413`. Both arms used the same
Alignpack, geometry, Metal bundle, 128-token prefill chunk, full final logits,
unchanged Q4_0 weights and identical prompt IDs/output counts. Two warmups and
five alternating pairs were retained. Worker phase clocks include graph
synchronization; startup is construction-to-ready with uncontrolled OS cache.
The HTTP/SSE comparison switches the flag in one binary and excludes llama.cpp.
Raw observations and binary/configuration digests are in
[`worker.json`](../eval/benchmarks/qwen35-shared-logits-2026-09-27/worker.json)
and [`http-sse.json`](../eval/benchmarks/qwen35-shared-logits-2026-09-27/http-sse.json).

Worker values below are medians in milliseconds; `wins` counts candidate-faster
pairs out of five. Paired difference means control minus candidate and retains
every outlier.

| Input/output tokens | Control request | Borrowed request | Pinned llama.cpp request | Paired difference / wins | Control decode | Borrowed decode | Pinned llama.cpp decode |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 64/16 | 574.549 | 572.263 | 550.945 | +1.383 / 3 | 434.398 | 432.580 | 425.733 |
| 200/32 | 1292.508 | 1288.627 | 1243.831 | +4.182 / 3 | 881.199 | 877.993 | 861.603 |
| 330/64 | 2426.843 | 2426.037 | 2361.938 | +2.787 / 3 | 1783.813 | 1785.472 | 1763.545 |

Worker prefill medians were 124.843→124.950, 383.152→383.801 and
597.895→598.132 ms. The 64/16 worker request has a retained candidate-slower
pair of 89.545 ms. Startup medians vary by workload and order; no construction
benefit is established. The candidate remains behind pinned llama.cpp in every
request median. The worker's sampled output and actual token work matched.

| Input/output tokens | HTTP paired difference / wins | SSE paired difference / wins |
| --- | ---: | ---: |
| 64/16 | +4.080 ms / 4 | -0.245 ms / 2 |
| 200/32 | +2.960 ms / 3 | -2.870 ms / 2 |
| 330/64 | +1.126 ms / 3 | +4.252 ms / 4 |

The copy disappears but CPU scanning the just-written shared GPU output still
reads the same 993,280 bytes. The hypothesis that the removed copy dominates
request latency is rejected on this host; CPU cache effects are a possible
explanation, not measured attribution. Next test a GPU-side reduction with
multiple threadgroups and strict finite/tie semantics, or a larger fused
operation, only after a local real-logit benchmark shows enough room to offset
integration and synchronization costs. The dominant Q6_K output projection is
also a separate candidate; a diagnostic graph that omits it is invalid for
inference and does not establish a speedup.

The view mechanism is conditional on storage properties, not the model name.
Another Qwen size can use it after its output shape and allocator pass the same
checks. Gemma needs a semantic model implementation and its own generation
qualification before it can consume this path. CPU/CUDA need their own safe
storage and synchronization contracts. The current mode does not make any of
those admissions.
