# Qwen3.5 shared-row NEON greedy trial (2026-09-27)

## Decision

Keep `ALIGN_LLM_NEON_GREEDY=1` as a default-off experiment. Its numeric scan is
reproducibly faster on three real captured rows and the real 2B/0.8B inference
owners pass, but the complete-request comparisons are mixed. In particular,
the 330/64 HTTP/SSE measurements do not establish a gain and pinned llama.cpp
is faster on all three worker request medians. Do not claim a production or
competitive win. The [predeclared contract and ceiling](specs/gpu-runtime-performance.md)
do not use a fixed percentage floor.

## Boundary and correctness

Align selects the mode once per Qwen3.5 session and retains the model graph,
execution plan, generation loop, greedy token publication, recurrent/KV state
and request cleanup. The real ggml path retains weight placement, graph
allocation, Metal command encoding and all model computations. The C shim
validates the completed, contiguous F32 output row in a shared `MTL` buffer
and runs a bounded AArch64 NEON finite/argmax numeric kernel on that borrowed
row. The kernel chooses the lowest index of an equal finite maximum and
refuses NaN/infinity. It holds no pointer after returning and adds no Metal
command buffer, synchronization, GPU scratch or retained state. The ordinary
full-logit copy and Align greedy remain the default. The prior scalar shared
mode is a separate, mutually exclusive opt-in control. Other storage or
unsupported hosts refuse the NEON mode; there is no silent fallback.

Actual 2B and 0.8B generation owners passed 31-, 200- and 330-token prompts,
three oracle-matching greedy tokens and six retained requests with invalid
request recovery. The 2B serving owner passed normal and SSE output, usage,
disconnect/recovery and malformed-request checks against pinned llama.cpp.
The 200/3 2B trace matched all 336 previous resident-state plane hashes
exactly. The model graph and F32 logits arithmetic are unchanged; the output
readback interposer recorded zero `ggml_backend_tensor_get` calls for the three
sampled rows. Full 248,320-element GPU output still exists and the CPU scans
it; the eliminated step is the extra full-row copy. Invalid flag strings `""`,
`"2"`, `"true"`, `"01"` and simultaneous scalar-shared/NEON modes refused
before session readiness. The existing shared mode also passed exact HTTP/SSE
responses after the common admission check was factored. No tolerance was
changed.

The independent screen used three actual 2B F32 rows after a GPU blit and
synchronization in both arms. Its source and [100 alternating pairs per row](../eval/benchmarks/qwen35-hierarchical-greedy-2026-09-27/neon-screen.csv)
are retained with the preceding hierarchy trial. The same lowest-index tie,
NaN and infinity tests passed before timing. A further 1,027-element and
248,317-element prefix of a real row passed those checks, including the NEON
tail. The local paired median scan reductions were 0.2459, 0.2478 and
0.2489 ms, with 98/100, 96/100 and 97/100 faster pairs. The production
`-O2` shim disassembly at local diagnostics shows one shared-row admission
call followed by 128-bit loads and vector comparisons; no per-token allocator,
shader compile or `ggml_backend_tensor_get` call appears in that function.
This is a local screen, not a connected speed claim.

## Real-model comparison

Apple M1, 16 GiB unified memory; unchanged Qwen3.5-2B Q4_0 GGUF SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`;
Align `b20429be50d6ab889496a0589143320683b29aeb`; pinned ggml/llama.cpp
`bb4caa7540188872173c44d161602d9271386413`. Old Align is the unchanged
`57fd7a6b` binary. Both Align arms used the same pack, Model IR, Metal bundle,
options, GGUF tensor formats, 128-token prefill chunks, final-only logits,
prompt IDs and generated counts. Native SwiGLU was disabled. Each arm had two
warmups and five alternating measured pairs. The worker trace includes graph
synchronization but is not shader-only time. Construction-to-ready startup
was measured separately with uncontrolled OS cache and desktop activity.
The same-binary server comparison changes only the greedy mode.

The [worker receipt](../eval/benchmarks/qwen35-neon-greedy-2026-09-27/worker.json)
retains all phase, startup, first-request, output, prompt-ID, binary and bundle
observations. Medians below are milliseconds. `paired` is the median of each
old minus new pair, so it can differ from the difference of arm medians.

| Input/output | Old request | NEON request | Pinned llama.cpp | Paired / NEON wins | Old/NEON prefill | Old/NEON decode |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 64/16 | 583.989 | 582.006 | 570.701 | +1.167 / 3 of 5 | 126.078 / 126.546 | 449.415 / 446.171 |
| 200/32 | 1446.546 | 1445.484 | 1397.756 | +0.074 / 4 of 5 | 394.087 / 392.366 | 1037.328 / 1039.007 |
| 330/64 | 2807.169 | 2798.533 | 2737.186 | +21.514 / 4 of 5 | 614.426 / 612.420 | 2163.780 / 2154.119 |

The [same-binary copied-path versus NEON HTTP/SSE receipt](../eval/benchmarks/qwen35-neon-greedy-2026-09-27/http-sse.json)
contains every two warmup and five measured pair. All text, finish reasons and
actual token counts matched. Request medians and paired results in ms:

| Input/output | Mode | Copied | NEON | Paired / NEON wins |
| --- | --- | ---: | ---: | ---: |
| 64/16 | HTTP | 576.549 | 580.787 | -8.569 / 2 of 5 |
| 64/16 | SSE | 571.324 | 569.415 | +3.266 / 3 of 5 |
| 200/32 | HTTP | 1298.401 | 1292.809 | +10.355 / 4 of 5 |
| 200/32 | SSE | 1314.844 | 1305.225 | +4.070 / 4 of 5 |
| 330/64 | HTTP | 2483.257 | 2469.269 | -12.867 / 2 of 5 |
| 330/64 | SSE | 2782.187 | 2797.218 | -6.061 / 1 of 5 |

SSE first-content-token paired medians were -0.336, -0.366 and +0.564 ms.
The two server startups were 1237.680 and 1167.812 ms, one order-dependent
observation, not a load-speed claim. Worker startup pairs were mixed.
The [same-binary scalar shared-row versus NEON receipt](../eval/benchmarks/qwen35-neon-greedy-2026-09-27/shared-vs-neon.json)
isolates the scan choice after the full-row copy has already been removed:

| Input/output | Mode | Paired reduction / NEON wins |
| --- | --- | ---: |
| 64/16 | HTTP / SSE | +4.031 / 3 of 5; +1.413 / 4 of 5 |
| 200/32 | HTTP / SSE | +14.460 / 4 of 5; -2.815 / 2 of 5 |
| 330/64 | HTTP / SSE | +8.335 / 3 of 5; -51.419 / 2 of 5 |

The 330/64 scalar-versus-NEON SSE paired range was -328.881 to +50.305 ms.
No single run was discarded. These paired ranges and the adverse SSE rows make
a production speed claim premature. The candidate replaces the 993,280-byte
per-request/session Align host scratch with four bytes and adds no retained GPU
allocation; process RSS and total physical-memory savings were not isolated.

## Next boundary

The NEON scan is shape-driven and can be reused for another Qwen size if its
completed output is a bounded contiguous F32 row in coherent shared Metal
storage. Model definition, quantized weights, activation, normalization,
attention and position semantics still require separate admission. Gemma needs
its own semantic graph and tokenizer/session qualification before this numeric
kernel can be selected; a matching vocabulary length alone is insufficient.

The remaining measured gap is in graph execution, especially the Q6_K tied
output projection that an earlier diagnostic placed at roughly 3.7–8.0 ms per
decode token. The next bounded experiment should use the captured real Q6_K
weights and final activation to compare a projection plus partial-top-token
consumer inside one Metal execution boundary, preserving exact finite/tie
semantics and full-logit oracle access for validation. The earlier one-to-one
Q6_K kernel probe did not win, so this hypothesis is about fusion and output
layout, not another launch-size sweep. The current ggml graph path remains the
rollback. CPU/CUDA specialization and Gemma graph semantics remain separate
work, with no cross-backend speed inference from this Apple M1 result.
