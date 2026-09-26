# Native SwiGLU follow-up — 2026-09-26

This follow-up tests the source-level dependency-chain hypothesis and broadens
research to implementation reports. It does not change the default inference
path or numerical bounds. The prior trial is in [the original report](native-swiglu-trial.md).

## What changed

The pinned ggml Q4_0 dot product maintains four independent partial sums;
the first native implementation accumulated the same terms into one variable.
The new version uses four partial sums and the reference's final combination
order. The 128-thread launch, four output rows per SIMD group, memory, buffers,
fusion admission and synchronization are unchanged. Compiler reassociation means
this source-level difference is a hypothesis, not proof of the generated
instruction schedule or the measured bottleneck. Both old and new pipeline logs
report `maxTotalThreadsPerThreadgroup=640`; this is not an occupancy measurement.

The independent measurement tool adds `--native-control` to compare an explicitly
supplied old native binary/bundle with the new native build and pinned llama.cpp.
It is exclusive with `--native-ab`. The latter retains the same-binary/bundle
reference-vs-native comparison. No existing receipt is overwritten.

## Correctness

All 24 actual 2B captured FFNs match the unfused gated and down outputs exactly
for this corpus (maximum absolute difference zero), including the three Q4_1 down
layers. Captured unfused outputs also match exactly. Alternate `[1024,3584]`
shape and square alias fallback pass. These observations do not promise bitwise
identity for arbitrary weights, shapes or future compiler versions. Native
pipeline compilation is present in the logs, so zero difference is not evidence
from silently taking the fallback. The unchanged 2B generation owner passes its
31/200/330 prompt cases and six retained requests. A 128-token request, another
three-token request and a repeated 128-token request match. All 261 full logit
vectors (64,811,520 values) are identical to the same-bundle unfused path.
The unchanged 0.01 absolute tolerance and identical-argmax check are retained.

## Measurement conditions

Same M1/16 GiB host, authenticated 2B GGUF, compiler and ggml pins, exact counting
prompts, and output-count checks as the original report. Two warm requests and
five alternating pairs per case. Prefill remains unfused. All samples are retained.
No author build or other qualification was running during timing. A process-state
sample during the first A/B campaign showed active terminal, browser and desktop
compositor processes. `pmset -g therm` reported no recorded warnings. This does
not measure GPU contention or establish its cause; the machine was not an
isolated benchmark host and the broad paired ranges limit small-effect claims.
Old-native/new-native/reference comparisons have the same documented reference
clock/context-reservation differences as the original report.

### Four partial sums, 128 threads: native OFF/ON

| Input/output | Control ms | Candidate ms | Paired median reduction | Faster pairs | Paired range |
| --- | ---: | ---: | ---: | ---: | --- |
| 64/16 | 575.38 | 578.60 | -0.02% | 2/5 | -13.45% to +1.96% |
| 200/32 | 1345.60 | 1427.84 | -0.61% | 1/5 | -6.11% to +12.02% |
| 330/64 | 2678.15 | 2719.82 | -0.23% | 1/5 | -11.85% to +0.08% |

### Original native vs four partial sums (both 128 threads)

| Input/output | Control ms | Candidate ms | Paired median reduction | Faster pairs | Paired range |
| --- | ---: | ---: | ---: | ---: | --- |
| 64/16 | 615.00 | 617.41 | -1.17% | 2/5 | -11.98% to +2.79% |
| 200/32 | 1461.94 | 1433.89 | +0.65% | 3/5 | -1.65% to +1.92% |
| 330/64 | 2573.65 | 2752.11 | -1.29% | 1/5 | -12.46% to +0.33% |

### Four partial sums, 64 threads: native OFF/ON

| Input/output | Control ms | Candidate ms | Paired median reduction | Faster pairs | Paired range |
| --- | ---: | ---: | ---: | ---: | --- |
| 64/16 | 566.76 | 597.83 | -0.03% | 2/5 | -8.72% to +9.35% |
| 200/32 | 1340.37 | 1314.31 | +0.14% | 3/5 | -1.89% to +6.93% |
| 330/64 | 2453.92 | 2454.85 | -0.04% | 2/5 | -7.30% to +0.38% |

### Four partial sums: 128 vs 64 threads

| Input/output | Control ms | Candidate ms | Paired median reduction | Faster pairs | Paired range |
| --- | ---: | ---: | ---: | ---: | --- |
| 64/16 | 561.32 | 562.14 | +0.03% | 3/5 | -12.91% to +0.38% |
| 200/32 | 1308.87 | 1315.92 | +0.07% | 3/5 | -0.75% to +11.53% |
| 330/64 | 2720.09 | 2717.68 | +0.28% | 4/5 | -1.64% to +4.42% |

All ranges cross zero. The medians of paired changes are not ratios of arm medians.
No samples were removed. The 64-thread launch is withdrawn; the retained opt-in
kernel uses four sums and 128 threads because it matches the reference reduction
structure and removes the observed numeric differences in this corpus. This is
not a performance adoption. Default inference remains unfused.

### Pinned reference comparison

Request medians in ms; each row is one campaign, not a cross-campaign pairing.
Reference clocks/context limits remain those in the original report.

| Variant comparison / input-output | Prior native | Candidate native | Pinned llama.cpp |
| --- | ---: | ---: | ---: |
| one to four sums, 64/16 | 615.00 | 617.41 | 599.41 |
| one to four sums, 200/32 | 1461.94 | 1433.89 | 1371.26 |
| one to four sums, 330/64 | 2573.65 | 2752.11 | 2513.29 |
| 128 to 64 threads, 64/16 | 561.32 | 562.14 | 634.85 |
| 128 to 64 threads, 200/32 | 1308.87 | 1315.92 | 1256.82 |
| 128 to 64 threads, 330/64 | 2720.09 | 2717.68 | 2613.25 |

Prefill, decode and process-to-ready startup samples/medians are retained separately
in the [raw receipt](../eval/benchmarks/native-swiglu-followup-metal-2026-09-26.json).
Comparisons to the unchanged pre-trial Align source remain in the original report.

### Local captured FFNs

Five alternating pairs, 20 executions per pair, after 12 warm-ups per arm.

| Variant / layer | Gate control/native ms | Full FFN control/native ms | Full native wins |
| --- | ---: | ---: | ---: |
| four_accumulator_128, 0 | 0.7595/0.7349 | 0.9686/0.9460 | 3/5 |
| four_accumulator_128, 3 | 0.6912/0.6916 | 0.8721/0.8588 | 3/5 |
| four_accumulator_128, 23 | 0.7944/0.7371 | 0.8344/0.8824 | 2/5 |
| four_accumulator_64, 0 | 0.7396/0.7191 | 0.9085/0.8652 | 3/5 |
| four_accumulator_64, 3 | 0.7527/0.7146 | 0.9510/0.9517 | 3/5 |
| four_accumulator_64, 23 | 0.7399/0.7132 | 0.9183/0.9406 | 1/5 |

## Community research, checked against source

- A [Reddit author report](https://www.reddit.com/r/LocalLLaMA/comments/1w46a73/llama_cpp_metal_moe_optimization/)
  led to [llama.cpp PR #28086](https://github.com/ggml-org/llama.cpp/pull/28086).
  The implementation addresses unused lanes in IQ3_XXS rows narrower than 1024
  elements. Our Q4_0 width-2048 kernel has 64 quant blocks, two lanes per block
  and four iterations per lane, so that specific idle-lane condition does not
  apply. Reuse the lesson of geometry-specific work mapping, not the reported
  speedup or the patch itself.
- [llama.cpp PR #7522](https://github.com/ggml-org/llama.cpp/pull/7522) records
  gains from redistributing Metal dot-product work and a regression on Gemma's
  different head dimension. Its 2024 attention kernel is not the current FFN;
  it supports testing launch/work geometry separately, not assuming one setting
  works across model families.
- [Stack Overflow's SIMD-width explanation](https://stackoverflow.com/questions/50093793/metal-compute-shaders-threadgroup-threadexecutionwidth)
  distinguishes SIMD width from threadgroup size. Both 64 and 128 are valid
  multiples of the observed width 32; this is not evidence that either is faster.
  [Apple's Metal Compute talk](https://developer.apple.com/videos/play/tech-talks/10580/)
  independently explains resource pressure and occupancy. A 64-thread follow-up
  keeps four partial sums and all per-SIMD arithmetic fixed to isolate grouping.

## Larger candidates after the bounded kernel experiments

Actual GGUF accounting gives 14,155,776 bytes of gate/up weights per layer and
98,304 bytes of eliminated intermediate gate/up writes plus reads. This excludes
input reuse and launch savings, so it is not a bound on possible total speedup.
The tied Q6_K output matrix is 417,177,600 bytes, versus 1,203,911,936 unique listed
weight bytes. Weight share is not runtime share. Measure that full-vocabulary
projection separately before choosing its shape-specialized implementation.

[FlashFormer](https://arxiv.org/html/2505.22758v1) motivates a more substantial
FFN design: compute a gate/up tile, apply SiLU, immediately consume the tile in
down, then reduce partial outputs. Its H100 results do not establish an M1 gain.
A Metal trial must preserve Q4_0/Q4_1 values, coalesced down-weight access, needed
cross-group synchronization and bounded partial-output storage. Begin with a
separate reduction dispatch rather than assuming a device-wide barrier inside
one kernel. Full engine replacement is not required to test that boundary.
[FlashDecoding++](https://arxiv.org/html/2311.01282v4) motivates shape-specific
work distribution, while [Mirage's RMSNorm/linear example](https://mirage-project.readthedocs.io/en/latest/tutorials/rms-norm-linear.html)
is a separate algebraic-fusion candidate with its own rounding verification.

These sources inform experiments. Unverified user reports, changed quantization,
and different devices/workloads are not evidence that this model is faster.

## Reproduction and disposition

Use the original report's bundle/compiler commands with the retained four-sum
patch. For the old-native comparison, build the original patch at `b1d24207`
and supply that binary/options/bundle as CONFIG's control. Run:

```sh
python3 scripts/measure-native-swiglu --native-ab --config CONFIG --output NEW_AB_JSON
python3 scripts/measure-native-swiglu --native-control --config CONFIG --output NEW_VARIANTS_JSON
```

To reproduce the withdrawn 64-thread probe, change only the patch's launch from
`(hidden * 8 + 127) / 128, 1, 1, 128, 1, 1` to
`(hidden * 8 + 63) / 64, 1, 1, 64, 1, 1`, build a separate bundle/shim/executable,
and use the four-sum 128-thread build as control for `--native-control`.
The raw receipt records both patch digests and every binary/bundle identity.
All experiments preserve the exact GGUF; there is no requantization or state
update omission. Their memory/ownership layout is unchanged from the original
trial; no new memory-saving claim or repeated memory qualification is made.

Verification commands: `gmake build` with each manifested bundle; captured
`bench-native-swiglu ... --check-only` for all 24 layers, alternate shape and
`--alias-input`; unchanged `scripts/run-qwen35-generation-smoke` for 2B and 0.8B
with native enabled; `check-native-captures logits` for the longer sequence;
and `python3 scripts/check-python-boundary --strict`. All pass. A final real
three-token trace shows 48 fusions across two decode graphs. The invalid
`--native-control --native-ab` combination exits 2 before creating output.
No Align source changed, so no new formatting/language qualification is needed.
No CUDA performance or correctness qualification, publication preflight or merge
is claimed by this local experimental checkpoint.

Next implementation boundary: isolate the full-vocabulary Q6_K output projection
with the real final activation, then test its load/work mapping; in parallel at
the design level, plan a tile-consumer FFN including down and a bounded partial
reduction. These are not implemented here. Preserve Align's execution and state
ownership, including model-specific activation/normalization semantics.

Bounded retrospective: the source-level accumulation hypothesis did not establish
a request speedup. Community reports became useful only after checking dtype,
shape and hardware applicability. The explicit old-native comparison option is
retained as the narrow reusable measurement improvement; no global gate is added.
