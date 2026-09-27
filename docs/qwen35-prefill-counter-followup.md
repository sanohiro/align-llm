# Qwen3.5-2B prefill-width follow-up after the Metal copy trial (2026-09-27)

## Question and source inspection

The preceding counter trace associated Q4_0/Q6_K decode matrix-vector work
with high buffer-read pressure, while the prefill Q4_0 matrix-matrix shader had
83% median F32 utilization. Test the already implemented 128-to-256 prefill
width switch with the winning contiguous-copy bundle before designing another
matrix kernel. This is a new same-binary measurement of an existing opt-in
setting, not a new runtime implementation.

The pinned ggml Metal `kernel_mul_mm_q4_0_f32` uses 64-output-row by
32-token tiles, dequantizes a weight tile into threadgroup memory, and applies
SIMD-group matrix multiplies. Width 256 reduces the number of prefill graphs
for these requests but does not itself change Q4_0 weight encoding or the
one-token decode path. Any extra weight reuse inside a graph or different
scheduling is a hypothesis, not a proven benefit of selecting 256.

## Controlled experiment

Apple M1 16 GiB, Qwen3.5-2B Q4_0 GGUF SHA256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
Both Align arms used the same saved binary SHA256
`b62a2d5d7e88dee85b4f3f672b4b4dca15a74d24fc5e89df5791cf277c6a0450`,
the same final linear-copy Metal bundle ID
`79ec2cf34b45bd90239df29e6944c6c306ca32b489359fe639d138efb7e56ba8`,
pack, Model IR, options and prompt token IDs. Native SwiGLU, synchronous
upload, last-FFN-row, mapped weights and GPU greedy were off; final-chunk
logits were on. Only `ALIGN_LLM_PREFILL_CHUNK` changed from 128 to 256.
The pinned llama.cpp reference used its existing 512 microbatch setting.

The existing independent `scripts/measure-native-swiglu` caller ran five
alternating three-arm groups per 64/16, 200/32 and 330/64 request. Each new
process ran two warm requests before its measured third request. The caller
checked actual token counts and identical generated output across both Align
arms and llama.cpp in every group; both campaigns ended `PASS`. The 64-token
case is a variation control: both Align settings execute one prefill graph.
At 200 tokens the graph counts are 2 versus 1; at 330, 3 versus 2.

The first campaign used a local graph-only interposer to measure synchronized
prefill and decode graph calls. It omitted the older backend/tensor interposer
because that interposer did not resolve against this saved binary. The second
campaign omitted all timing interposition. The prior prefill-width plan's
900-second campaign and 180-second request ceilings were observed. The
complete [phase](../eval/benchmarks/qwen35-prefill-counter-followup-2026-09-27/phase.json)
and [wall-only](../eval/benchmarks/qwen35-prefill-counter-followup-2026-09-27/wall.json)
receipts retain every arm, pair and output. The local config, graph-only
interposer and failed attempts remain in the Git common directory under
`diagnostics/q35-prefill-counter-followup-20260927/`.

## Result

Positive paired differences below favor width 256. Times are milliseconds;
each median is the median of five matched control-minus-candidate pairs, not
the subtraction of the arm medians.

| Input/output | Phase campaign prefill | Phase campaign decode | Phase campaign whole request | Wall-only whole request |
| --- | ---: | ---: | ---: | ---: |
| 64/16, same actual width | -2.411 (1/5) | +10.969 (5/5) | +7.397 (4/5) | -1.757 (2/5) |
| 200/32 | -3.163 (0/5) | -1.063 (2/5) | -1.396 (2/5) | -2.609 (2/5) |
| 330/64 | +4.892 (5/5) | +2.708 (3/5) | +10.980 (5/5) | -9.812 (1/5) |

At 200 tokens the larger chunk made synchronized prefill slower in all five
pairs despite removing one graph boundary. At 330 tokens it made synchronized
prefill faster in all five pairs. The uninstrumented whole-request campaign
did not reproduce the 330-token lead: its five paired differences were
`-9.812, +167.301, -50.941, -32.984, -9.759` ms. The 200-token campaign
also had shared slow samples in both Align arms and the reference. No sample
was discarded. Startup varied and is not a supported gain; no new physical
memory high-water measurement was made.

The 2B GGUF lists 1,203,911,936 unique tensor bytes. Dividing that rough
per-token weight extent by the measured width-128 synchronized decode time
per graph gives about 48 GB/s at both 200/32 (31 decode graphs) and 330/64
(63 decode graphs). This is close to the separate trace's 49–52 GB/s median
Q4_0/Q6_K GPU read samples. It is **not** a measurement of physical bytes:
cache effects, tensors that are not read, state traffic and command overhead
are excluded. The agreement supports a weight-streaming hypothesis for this
single-sequence decode workload, without proving a hard speed ceiling.

## Decision

Keep width 128 as the current default and width 256 as an opt-in mode. The
larger prefill width has a small, input-dependent phase effect and no stable
whole-request win in this follow-up. The result also explains why simply
increasing the chunk is not a substitute for a different GPU kernel or data
flow. The already winning contiguous-copy specialization has since passed its
view-geometry and process-footprint screens and is recommended explicitly for
the measured M1 Qwen3.5 profile. A further decode experiment
needs a concrete mechanism for useful weight bytes per read or fewer required
bytes while retaining the same GGUF and exact output; any changed quantization
is a separately controlled experiment. A prefill kernel experiment should
target a measured tile/shape inefficiency and preserve the model's recurrent
and attention semantics, rather than extrapolate this 128/256 result to all
Qwen sizes or Gemma.
