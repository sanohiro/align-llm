# Qwen3.5 Q6_K four-row mapping screen (2026-09-27)

## Decision

Withdraw this local four-output-rows-per-SIMD mapping. It reproduces the actual
2B Q6_K output projection exactly on the captured final-prefill and two decode
activations, but its paired local timings do not establish a repeatable gain.
It was never connected to production inference; the pinned ggml graph remains
the control and runtime path. This result does not rule out a different data
layout, a larger fusion boundary, or another device.

## Mechanism and correctness

The 2B tied output head has shape `[2048, 248320]` and 417,177,600 Q6_K
weight bytes. The pinned Metal kernel and the prior independent paired-load
probe assign two output rows to each 32-lane SIMD group. This variant assigns
four, while retaining the same Q6_K bytes, F32 input, quantized dot arithmetic,
64-thread group, and full F32 output. It halves the group count from 62,080 to
31,040. The exact local [patch](../eval/benchmarks/qwen35-q6-four-row-2026-09-27/four-row.patch)
applies to the checked-in independent Q6_K probe. It is a developer experiment,
not an inference engine hidden in C++.

The three captured real inputs were checked before timing. All 248,320 logits
and the 257-row tail matched both the captured result and the pinned ggml
result with maximum absolute difference **zero**. First-index argmax was
identical: 16, 220, and 17. The predeclared 0.01 absolute bound was not changed.
The [check receipt](../eval/benchmarks/qwen35-q6-four-row-2026-09-27/check.jsonl)
contains every comparison. The ggml and native arms each hold one 417 MB shared
weight buffer, so the local setup has two copies; it does not establish a
production memory ceiling.

## Local timing and read diagnostic

Apple M1, 16 GiB, pinned ggml `bb4caa7540188872173c44d161602d9271386413`,
unchanged GGUF bytes, and the copy-specialized Metal bundle used in the
2026-09-27 2B campaign. [SHA256 identities](../eval/benchmarks/qwen35-q6-four-row-2026-09-27/identities.json)
bind the capture, sources, binaries, and plugin. After twelve warmups per arm,
each activation had five alternating pairs of twenty synchronized operations
per arm. Positive paired ggml-minus-native time favors the four-row kernel.
All [samples](../eval/benchmarks/qwen35-q6-four-row-2026-09-27/timing.jsonl)
are retained.

| Captured activation | Median ggml / four-row wall, ms | Paired difference, ms | Four-row wins | Paired range, ms |
| --- | ---: | ---: | ---: | ---: |
| Final prefill | 7.663 / 7.660 | +0.003 | 3/5 | -0.210 to +0.072 |
| Decode 1 | 7.659 / 7.652 | -0.021 | 2/5 | -0.214 to +0.038 |
| Decode 2 | 7.652 / 7.684 | -0.050 | 2/5 | -0.136 to +0.034 |

The native command-buffer GPU interval medians were 7.287, 7.279 and
7.305 ms, respectively. A later, separate [two-row timing
campaign](../eval/benchmarks/qwen35-q6-four-row-2026-09-27/two-row-timing.jsonl)
also passed the actual-output checks, but host timing drifted; its results are
not a simultaneous four-row/two-row comparison. The alternating pinned-ggml
comparison above is the decision evidence. No complete request or llama.cpp
benchmark was run for this rejected local candidate.

A checked CPU/GPU checksum probe read every 32-bit word of the same 417,177,600
bytes contiguously, with one shared weight buffer and a small checksum output.
After twelve warmups, five batches of twenty synchronized operations gave a
median GPU command interval of 7.758 ms, or 53.77 GB/s of *listed* bytes per
interval. Its [source](../eval/benchmarks/qwen35-q6-four-row-2026-09-27/bench-q6-stream.mm)
and [receipt](../eval/benchmarks/qwen35-q6-four-row-2026-09-27/stream.jsonl)
are retained. The actual projection's interval is shorter than this checksum
scan. The diagnostic therefore does **not** define a bandwidth roof or an
achievable speedup. It does show that a plain contiguous reread is not an
obvious replacement for this projection. Previous whole-GPU counter samples
also associate Q6_K and Q4_0 decode work with high buffer-read pressure, but
those samples do not count physical bytes for this kernel.

## Next GPU hypothesis

The Q6_K output head is one large shader; Q4_0 projections have the larger
aggregate decode time. Pinned Q4_0 already reads neighboring quantized blocks
across lanes and handles four rows per SIMD group. A one-to-one arithmetic
rewrite and gate/up/SwiGLU-only fusion have already been tested. The next
useful local experiment must change a concrete transfer or dependency:
screen a **lossless resident weight layout** for a representative actual Q4_0
projection, and account for its upload conversion, resident bytes, lane read
addresses, GPU read counters where available, GPU interval, and exact output
against the unchanged GGUF. Reject it locally if
the extra bytes or transformation cost overwhelm any read gain. Only a
repeatable local gain warrants a reversible real-model trial with full
logits/state and whole-request comparisons. Keep Qwen/Gemma model semantics in
Align and select any eventual device specialization by type, shape, and layout.

To reproduce this screen, build `scripts/bench-metal-q6-projection.mm` against
the pinned ggml headers and plugin, then apply the linked four-row patch to an
isolated copy and compile it with the same flags. Run `--check-only`, followed
by the default five-pair timing mode, on the retained actual capture. Build
the linked checksum source with `clang++ -O3 -std=c++17 -fobjc-arc -framework
Foundation -framework Metal` and pass the same captured `weights.bin`.
