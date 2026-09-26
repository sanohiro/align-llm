# Qwen3.5-2B Metal decode attribution

## Result

There is still a measured performance gap, but this diagnostic does not support
an inference-engine ceiling. The earlier complete-request comparison measured
about 27.8 ms of Align GPU command-buffer intervals versus 26.4 ms for pinned
llama.cpp per decode step on the 200/32 request. This investigation checked
which work actually runs before choosing another kernel. It is **diagnostic**;
its instrumented clocks are not a new whole-request performance claim. The
complete compact receipt is
`../eval/benchmarks/qwen35-decode-attribution-metal-2026-09-26.json`.

On the unchanged Apple M1 16 GiB host and Qwen3.5-2B Q4_0 GGUF, an independent
Metal interposer recorded compute pipeline function names, grid sizes and thread
group sizes. The same 200 prompt IDs and two greedy tokens ran in both binaries.
The Align session used native FFN off, legacy upload, chunk 128, final-prefill
logits on and final-FFN-row off. The pinned llama driver used batch/microbatch
512, four threads and Flash Attention. Both produced the same rendered text in
the normal, unpruned runs; this dispatch diagnostic did not independently
capture Align token IDs. Counts below use the final decode graph after warmup.

| Decode work | Align | Pinned llama.cpp |
| --- | ---: | ---: |
| Total Metal compute dispatches | 663 | 682 |
| Exactly matching function and launch signatures | 613 | 613 |
| Q4_0 matrix-vector | 129 | 129 |
| Q4_1 matrix-vector | 3 | 3 |
| Q5_K matrix-vector | 18 | 18 |
| Q6_K output projection | 1 | 1 |
| Flash-attention vector / reduce | 6 / 6 | 6 / 6 |
| Gated delta / SSM convolution | 18 / 18 | 18 / 18 |

The major matching kernels also have identical grid and thread-group dimensions:
for example, the Q6_K output projection dispatches `62080 × 1 × 1` groups of
`32 × 2 × 1` threads in both. The nonmatching remainder is 50 Align and 69
llama dispatches. Align has 18 additional vector-unary, 12 F32 copies, 12 I32
row writes, six F32-to-F16 copies, one Q6_K row read and one fused RMS-normalize/
multiply. Llama has 37 F32 row reads, 18 scalar-unary, 12 I64 row writes, one
binary fusion and one separate RMS normalization. These are function counts,
not GPU durations or proof of equivalent intermediate semantics. In particular,
fewer dispatches do not imply less GPU time.

An independent, deliberately invalid-output intervention omitted only the last
Q6_K projection node from a **decode** graph. The full graph had 1,110 nodes;
the projection was node 1,109. All earlier graph nodes, including state writes,
remained in the diagnostic graph. Two warmup pairs preceded five alternating
full/pruned pairs for 200 input and two generated tokens. Full/pruned marginal
median synchronized graph times were 30.195/23.973 ms; the paired differences
were 6.855, 5.369, 3.718, 7.999 and 4.129 ms. The skipped arm's second token
is invalid (normal `1 ` versus diagnostic `1 Souls`); it is never an inference
candidate. Changing graph length can also change scheduling. Thus this is an
approximate **connected cost** of the output projection, not a pure shader time
or an achievable optimization. The standalone actual-weight Q6_K kernel probe
had 7.2–7.3 ms traced intervals and showed no repeatable speedup from paired
loads. Both facts point away from repeating that mapping.

Metal System Trace captured the real requests and command encoders. Its exported
recording states `Shader Timeline: Disabled` and has no shader interval rows.
The local M1 reports stage-boundary timestamp sampling, but no dispatch-boundary
counter sampling. The trace therefore cannot assign GPU time to individual
dispatches. The first 25-second recording was interrupted during saving and is
invalid; the complete eight-second recording and exported TOC are retained in
the resolved Git common directory. All intrusive diagnostics remain outside
production and were excluded from the previous request-speed verdict.

## What to test next

The current Align loader reads and uploads every pack member into a ggml-owned
Metal weight buffer. Pinned llama.cpp maps the model and wraps host pages with
`ggml_backend_dev_buffer_from_host_ptr`; source and binary evidence are in
`llama-binary-comparison.md`. The matching dominant kernel launches make weight
placement, page residency and graph scheduling a more useful next hypothesis
than changing the Q6_K instruction sequence alone. This is an **inference from
the combined evidence**, not proof that mapping explains the 1.4 ms decode gap.

The Alignpack has aligned member offsets and is 1,621,209,088 bytes, below this
M1 Metal device's reported 9,534,832,640-byte maximum buffer length. That makes
a reversible mapped-pack trial plausible. Before coding the ownership boundary,
define exact mapping lifetime, checksum/format validation order, tensor placement,
fallback, concurrent-request isolation, and cleanup on every failure. Keep Align
responsible for the selection and session; a thin host mapping/Metal-buffer ABI
may own the raw map and handle. Compare unchanged Align with a same-model mapped
trial and pinned llama.cpp, including construction, first use, warm prefill,
decode, whole request, physical footprint and memory pressure. Retain the current
upload path for rollback. No mapped trial or speed benefit is claimed here.

Qwen sizes can reuse the mapping owner and validated offset placement when their
pack format and semantic graph are admitted. Gemma needs its own model semantics
and pack admission; a similar tensor layout does not make it equivalent to Qwen.
CPU/CUDA behavior remains unmeasured.
