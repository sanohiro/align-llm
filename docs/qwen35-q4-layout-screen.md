# Qwen3.5 Q4_0 resident-layout and row-mapping screen (2026-09-27)

## Decision

Do not integrate the tested Q4_0 split-scale layout or two/eight-row SIMD
mappings. They preserve the actual 2B output exactly, but the split layout did
not give a stable local gain and both alternative row mappings lost the
cache-controlled GPU interval comparison with the existing four-row mapping.
The existing ggml execution and already qualified contiguous-copy bundle
remain unchanged. No whole-request or llama.cpp speed claim follows from this
local screen.

## Actual data and implementation

An independent capture interposer recorded the first decode's FFN weights,
inputs, gated values and outputs for all 24 Qwen3.5-2B layers. The existing
`scripts/check-native-captures weights` compared all 72 gate/up/down weight
tensors byte for byte with the unchanged GGUF: **PASS**. The layer-23 gate is
Q4_0 `[2048,6144]`, and its down projection is Q4_0 `[6144,2048]`; each
contains 7,077,888 bytes. The earlier layers 0–2 have Q4_1 down weights, so
they were not silently treated as Q4_0. The [identities](../eval/benchmarks/qwen35-q4-layout-2026-09-27/identities.json)
bind the source model, selected captures, three local probe sources/binaries
and pinned Metal plugin.

The [split probe](../eval/benchmarks/qwen35-q4-layout-2026-09-27/bench-q4-split.mm)
separates every 18-byte Q4_0 block into its unchanged F16 scale and 16 packed
quant bytes. It verifies lossless reconstruction and uses the pinned four-row
SIMD work distribution and dot arithmetic. For all 24 gate matrices the two
new streams occupy 18,874,368 and 150,994,944 bytes, exactly the original
169,869,312 bytes. The measured CPU conversion took 40.75 ms for those 24
gates. These are local allocation extents and one conversion clock, not a
complete model peak-memory or load-time result. Each arm has its own Metal
weight allocation during A/B measurement; production would have to replace
one allocation, not retain both.

The [two-row](../eval/benchmarks/qwen35-q4-layout-2026-09-27/bench-q4-row2.mm)
and [eight-row](../eval/benchmarks/qwen35-q4-layout-2026-09-27/bench-q4-row8.mm)
probes retain the original bytes. They vary only output rows per SIMD group,
which changes group count and register work. Each mapping and the split layout
matched all 24 captured layer inputs' pinned ggml outputs exactly, 6,144
values per layer. The layer-23 down graph also matched the captured output
exactly. The predeclared `0.005 + 0.0005*abs(ggml)` bound was unchanged.

## Paired local result

Apple M1, 16 GiB; pinned ggml `bb4caa7540188872173c44d161602d9271386413`;
same Q4_0 GGUF, actual first-decode activations and copy-specialized bundle.
Each comparison used twelve warmups, five alternating pairs of twenty
synchronized operations per arm. The isolated layer-23 gate/down
[receipts](../eval/benchmarks/qwen35-q4-layout-2026-09-27/gate.jsonl)
are cache-sensitive because the same 7 MB tensor repeats. The
[24-layer gate rotation](../eval/benchmarks/qwen35-q4-layout-2026-09-27/gate-rotate.jsonl)
reads 169.9 MB of distinct real gate weights per arm. Positive paired
difference means the proposed layout or mapping was faster.

| Actual projection / comparison | Median paired wall difference, ms | Wins | Median paired GPU difference, ms | GPU wins |
| --- | ---: | ---: | ---: | ---: |
| Layer-23 gate, ggml minus split | +0.071 | 3/5 | N/A | N/A |
| Layer-23 gate, native raw minus split | +0.007 | 4/5 | -0.006 | 2/5 |
| Layer-23 down, ggml minus split | -0.002 | 2/5 | N/A | N/A |
| Layer-23 down, native raw minus split | +0.005 | 3/5 | +0.007 | 3/5 |
| 24 gate layers, native raw minus split | +0.016 | 3/5 | +0.007 | 3/5 |

The down samples are in the separate [down receipt](../eval/benchmarks/qwen35-q4-layout-2026-09-27/down.jsonl).
For row mapping, an initial version let both native arms read one identical
Metal weight buffer. The second arm then received an order-dependent cache
benefit; its inconsistent result is invalid for choosing a mapping. The final
probes give the arms **separate byte-identical** 169.9 MB weight buffers,
rotate through the 24 layers, and retain all paired samples:

| Mapping versus four rows | Paired wall medians, ms | Paired GPU medians, ms | GPU wins for candidate |
| --- | ---: | ---: | ---: |
| Two rows, one campaign | -0.039 | -0.049 | 0/5 |
| Eight rows, first campaign | -0.063 | -0.029 | 0/5 |
| Eight rows, repeat | +0.045 | -0.017 | 1/5 |

The wall result for the repeated eight-row campaign disagrees with its GPU
interval result; scheduling and host variation remain. The GPU intervals show
no repeatable two/eight-row gain. The complete [two-row](../eval/benchmarks/qwen35-q4-layout-2026-09-27/gate-row2-separated.jsonl),
[eight-row first](../eval/benchmarks/qwen35-q4-layout-2026-09-27/gate-row8-separated-a.jsonl)
and [eight-row repeat](../eval/benchmarks/qwen35-q4-layout-2026-09-27/gate-row8-separated-b.jsonl)
receipts retain every check and sample. The probe's GPU interval is a
command-buffer time, not an isolated shader-instruction profile.

The aggregate decode counter trace already associated Q4_0 work with buffer
read pressure, but neither these local timings nor an ideal entropy estimate
proves a physical bandwidth floor. A simple nibble histogram over the 24
captured gate weights has 3.745 bits per 4-bit symbol; even an ideal independent
symbol code would save at most about 6.4% of quant payload bits before metadata,
indexing and GPU decode cost. This does not establish a useful lossless GPU
codec. Do not adopt a different quantization or relax numerical checks under
this experiment.

## Next action

The already measured contiguous F32 Metal copy specialization is the current
verified GPU improvement. Its geometry and process-footprint qualifications
now support an explicit recommendation for the measured M1 Qwen3.5 profile;
total GPU/system peak and other hosts remain unmeasured. For further decode speed, a new
candidate needs a mechanism beyond row count or scale/quant separation, such
as batched target verification that reuses weights per accepted token. For
Qwen3.5 that requires an exact gated-DeltaNet state transaction and a combined
draft/target cost model; no such speed result is claimed here.
