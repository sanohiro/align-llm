# Independent Metal Q6_K four-column output-head screen (2026-09-28)

## Decision

Keep `--batch4` as a local developer probe. Do not integrate this kernel into
the real-model graph. It is numerically correct on the captured Qwen3.5-2B
Q4_0 model's Q6_K output weight and three actual activations, but the native
four-column projection is slower than pinned ggml after the first measured
pair. A split graph and external command would add connection cost. There is
no whole-request improvement claim and no change to product inference.

The hypothesis was to read each compressed Q6_K block once while calculating
four activations in one independent Metal dispatch. The shader uses the Q6_K
block layout and a four-column shape, not a Qwen model-name condition. The
fourth column repeats the first captured activation because the existing
capture stores one final-prefill and two decode activations; these are real
model values but not a single four-token target continuation. The existing
ggml route remains the comparison and rollback path.

## Identity and correctness

Apple M1, 16 GiB, pinned ggml source
`bb4caa7540188872173c44d161602d9271386413`, plugin SHA-256
`a901a131109e42de39919c74562947ad8783b32d63c2ce88be13e9812b07fdf5`.
The actual GGUF is `Qwen3.5-2B-Q4_0.gguf`, SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
The captured 2,048-by-248,320 Q6_K weight is 417,177,600 bytes, SHA-256
`06e53b86ebe6f3e7a4b83110fd717e847404acd4bbc4670be1c80f241ff4830e`.
The three F32 activation SHA-256 values are
`d5c98019b000a9143ceab1a10e0944c04bd09feeb7d8aba746a0afb43c500fb9`,
`ce0ed29b54f7a56a5a28198ac5da570f01c70a7d52e6f119ac6a0d2d59246538`,
and `8386b56c52c34476b349a84530f5796a53dc6a1245b886739e53e10c95110516`.
Capture files remain outside Git; `scripts/capture-q6-projection.c` recreates
them from the pinned model and a prompt that produces three tokens. The probe
binary SHA-256 is
`b11fb8b15e703ad56074efb78583dd6641064b03c25fb02e2819932dca80a075`.

The unchanged `0.01` absolute F32 bound was declared by the existing Q6_K
probe before this screen. On all 248,320 output rows of each column, captured
single-column versus pinned ggml four-column maximum absolute difference was
at most `3.34e-6`, and ggml versus native at most `3.82e-6`. The 257-row
tail passed with at most `2.39e-6`. Every column's first-index greedy choice
matched: complete `[727,4752,31057,727]`, tail `[58,220,62,58]`. A separate
three-row capture checked both a complete three-row shape and a two-row tail.
The probe checks every F32 value and token before timing. It does not compare
recurrent state or a connected request, since the candidate was not connected.

## Local timing

Each arm has its own byte-identical Q6_K weight buffer. Inputs and outputs
are separate shared Metal buffers; each completed operation includes submission
and one final wait. This allocation arrangement is a local comparison and
does not model real graph interoperation. Twelve warmups preceded five pairs
of 20 alternating operations. The [uninstrumented receipt](../eval/benchmarks/qwen35-q6-batch4-2026-09-28-timing.jsonl)
retains every sample. Positive ggml minus native favors the candidate.

| Pair | ggml completed wall | Native completed wall | ggml minus native |
| --- | ---: | ---: | ---: |
| 0 | 15.142 ms | 11.413 ms | +3.729 ms |
| 1 | 10.769 ms | 11.457 ms | −0.688 ms |
| 2 | 10.745 ms | 11.455 ms | −0.710 ms |
| 3 | 10.722 ms | 11.440 ms | −0.718 ms |
| 4 | 10.723 ms | 11.431 ms | −0.708 ms |

The all-pair median difference is −0.708 ms, native winning 1/5. The first
pair is an outlier in both campaigns; its cause was not isolated, so the raw
sample remains in the receipt. A separate
[command trace](../eval/benchmarks/qwen35-q6-batch4-2026-09-28-trace.jsonl)
also found 1/5 native wins, with −0.679 ms median completed-wall and
−0.746 ms median GPU-interval differences. The hook changes host wall timing,
so its GPU intervals diagnose the local kernel, rather than establish request
speed. It observed two ggml commands and one native command per operation.
The machine was not exclusively reserved; iTerm still used about one CPU core.
Agreement between the uninstrumented wall and GPU intervals makes a native
kernel gain implausible for this mapping despite that host noise.

The pinned ggml four-column path uses an eight-lane-per-output-row SIMD
mapping and four-by-four dequantized/vector dot chunks. This experiment used
two rows per SIMD group and four scalar accumulators per output, with 64
threads per group. That difference is a plausible cause of the observed
kernel loss, not a measured instruction-level attribution. Copying the same
mapping alone would at best recover the local gap; it would still need to
pay a graph boundary in a connected trial. A future independent producer
needs a materially better four-column mapping or a fused larger unit whose
saved work covers its connection cost. This result does not rule out an
independent Metal backend overall.

## Reproduction and portability

Build the checked-in probe against the named pinned ggml source and bundle,
then run `bench-metal-q6-projection PLUGIN CAPTURE_DIR --batch4 --check-only`
and the same command without `--check-only`. The latter emits all alternating
samples as JSONL. Use `--gpu-trace` for the separate instrumented diagnostic.
No weight or generated binary is checked in. CUDA, other Metal generations,
other Qwen sizes, Gemma semantics and request performance are unmeasured.
The Q6_K shape/layout kernel idea can transfer where that exact format and
four-column workload occur; model semantics and state handling remain owned
by their respective Align model definitions.
