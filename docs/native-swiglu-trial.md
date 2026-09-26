# Native Metal SwiGLU trial — 2026-09-26

Decision: keep the opt-in experiment; do not enable it by default. Real-model
correctness passes, but the measurements do not establish a repeatable request
improvement. This is a measured integration result, not a conclusion about the
viability of an independent backend.

The [policy and trial ledger](specs/qwen35-text.md#native-metal-swiglu-trial-ledger-2026-09-26)
withdraw the old fixed-percentage admission/shipping rule. The
[raw receipt](../eval/benchmarks/native-swiglu-metal-2026-09-26.json) retains
all measurements, including unsuccessful trials and variability.

## Implementation and ownership

Align selects the trial through `ALIGN_LLM_NATIVE_SWIGLU=1`; unset/0 keeps the
reference graph, and other values refuse graph construction. The new
`ggml_ffi.op_native_swiglu_gate` creates the same checked matrix multiplication
and marks it for the device specialization. Model definitions, graph construction,
normalization, attention/recurrent state, session reset, generation and selection
remain in Align. The C shim only transports the request.

`scripts/native-metal-swiglu.patch` adds one native Metal gate/up/SiLU kernel
inside the pinned backend's existing encoder. It replaces three dispatches with
one when the marked subgraph has no external intermediate consumers and meets
its dtype, layout, dimension and single-token constraints. Shape parameters are
runtime values, not Qwen3.5-2B constants. The backend validates SiLU semantics;
it cannot silently substitute this operation for Gemma's different activation.
Encoder boundaries, incompatible types/layouts and input/output storage overlap
fall back to the original graph. Overlap uses backing addresses because Metal
can expose overlapping storage through distinct buffer objects.

GGML still owns tensor allocation, the command encoder, other operations and the
down projection. The authenticated 2B GGUF has Q4_0 gate/up weights in all 24
layers, but Q4_1 down weights in layers 0..2 and Q4_0 down in layers 3..23.
The trial preserves those exact bytes and formats. It adds no weight conversion,
CPU/GPU copy, temporary tensor, command buffer, CPU wait or session state. Existing
buffers are borrowed with their offsets; dependency checks and synchronization
remain. The original allocator still reserves the unfused intermediate tensors,
so this is not a memory-reduction claim.

The first connected version conservatively inserted an unconditional GPU barrier.
The next version checks all dependencies and reuses the encoder's prior barrier
when sufficient. Both versions were measured. This integration is a backend
extension, not a permanent requirement that future native paths use ggml.

## Correctness and limits

- All 72 captured FFN weight tensors match their original GGUF byte ranges.
- All 24 real 2B FFNs pass intermediate/final comparisons on actual activation
  vectors. Maximum absolute differences are 0.000001818 (gated) and
  0.000000656 (down); the local unfused results reproduce captured model outputs
  exactly. The existing predeclared bound is `0.005 + 0.0005 * abs(reference)`.
- A synthetic `[1024,3584]` FFN passes; a deliberately aliased square input/output
  takes the fallback and matches exactly.
- The unchanged real generation owner passes on 2B and 0.8B: 31-, 200- and
  330-token prompts, three greedy outputs, six retained requests, invalid request
  recovery and early exit. The new opt-in value also rejects malformed input.
- A 128-token request, a different three-token request, then the repeated
  128-token request match the control exactly. All 261 full F32 logit vectors
  (64,811,520 elements) are finite, have identical greedy argmax, and have maximum
  absolute difference 0.002984 under the existing 0.01 logit bound. Mean absolute
  difference is 0.0001166. These are rounding-changing experimental results, not
  bit-identical compatibility. No tolerance was increased after comparison.
- A three-token 2B graph trace confirms 48 native fusions across its two decode
  graphs. Prefill remains on the original operations for the measured chunk sizes.
- The existing layer-forward owner and strict Python-boundary guard pass.
  Measurement aggregation passes the GPU session smoke and the portable CUDA
  policy/parser self-test. The full CUDA self-test needs Linux `/proc`; no CUDA
  host execution is claimed.

The long-logit and local timing campaign preceded the final backing-address
overlap guard refinement; the shader and arithmetic were unchanged. The final
guard narrows admission. Final alias fallback, 0.8B generation, 2B fusion traces
and both complete request campaigns exercised the final guard.

Python additions are independent capture checks and measurement/build tools.
Normal product inference has no added Python dependency. CPU/CUDA native fusion
is deferred; the [parity register](backend-parity.md) records the scope.

## Measurement interpretation

Hardware: Apple M1, 16 GiB unified memory, macOS 27.0. Model: the authenticated
`Qwen3.5-2B-Q4_0.gguf` named in the ledger. Align compiler and llama.cpp/ggml
revisions are fixed in the receipt. We use counting prompts with exactly 64,
200 or 330 input tokens and 16, 32 or 64 generated tokens. All outputs and
actual counts match. Each arm gets two warm requests and five alternating
measured pairs; all samples are retained. No build or other qualification runs
concurrently with performance measurement.

The independent llama.cpp reference checks the exact prompt IDs, uses greedy
selection, F16 KV and Flash Attention, and records startup separately. Align's
request clock includes the session transport and normal prompt work; the llama
reference's request clock is inside its native driver and starts before reset
and tokenization of the already-rendered prompt. These clocks include different
wrapper work, which is part of the reported limitation, not attributed to the
fusion. Align phase clocks cover graph compute/synchronization; reference phase
clocks also include host work. Neither is shader-only time. Reference context
reservation is 512 and Align's bounded session reservation is 2304; the attended
history and generated work are identical. Startup is process-to-ready with an
uncontrolled OS file cache, not cold-storage latency. These choices preserve the
prior pinned-reference diagnostic; they do not establish a serving benchmark.

The strongest isolation is the same-binary, same-bundle OFF/ON comparison. It
holds all wrappers, allocations and core library builds fixed. Adoption is based
on that experiment together with correctness and the full comparison, without
using a percentage floor.

### Same binary and bundle, native OFF/ON

| Input/output tokens | OFF request ms | ON request ms | Median paired reduction | ON faster pairs | Paired range |
| --- | ---: | ---: | ---: | ---: | --- |
| 64/16 | 624.04 | 620.60 | +0.55% | 3/5 | -1.78% to +1.16% |
| 200/32 | 1354.77 | 1399.52 | -0.98% | 2/5 | -7.94% to +2.51% |
| 330/64 | 2493.16 | 2491.26 | +1.35% | 4/5 | -6.52% to +3.74% |

The ratio of arm medians is not the median of paired reductions; both are retained.
Positive paired reduction means faster. All three ranges cross zero.

### Final source against unchanged Align and pinned llama.cpp

Request medians in milliseconds, with the clock-scope limitations above:

| Input/output | Unchanged Align | Native trial | Pinned llama.cpp |
| --- | ---: | ---: | ---: |
| 64/16 | 599.98 | 585.78 | 559.61 |
| 200/32 | 1363.60 | 1350.31 | 1321.16 |
| 330/64 | 2543.15 | 2547.08 | 2370.30 |

Phase medians (milliseconds); Align columns are graph compute/synchronization,
while reference columns include host work in that phase:

| Input/output | Control prefill/decode | Native prefill/decode | Reference prefill/decode |
| --- | ---: | ---: | ---: |
| 64/16 | 125.02 / 447.96 | 124.31 / 435.96 | 125.56 / 434.05 |
| 200/32 | 399.80 / 918.10 | 396.69 / 906.90 | 385.85 / 933.14 |
| 330/64 | 625.38 / 1840.26 | 627.70 / 1838.89 | 594.86 / 1772.86 |

Startup medians (process construction to ready, milliseconds):

| Input/output campaign | Control | Native | Reference |
| --- | ---: | ---: | ---: |
| 64/16 | 1121.60 | 997.04 | 480.33 |
| 200/32 | 1121.88 | 1030.16 | 456.11 |
| 330/64 | 1031.35 | 1063.46 | 456.58 |

Startup variation is substantial despite unchanged loading logic; these warm-file
process starts support no startup optimization claim.

### Local captured FFNs

Five alternating pairs of 20 synchronized executions after 12 warm-ups per arm.
Medians in milliseconds; weights/activation upload is outside timing:

| Layer / down format | Gate/up/SiLU control/native | Full FFN control/native | Native FFN wins |
| --- | ---: | ---: | ---: |
| 0 / Q4_1 | 0.6780 / 0.6116 | 0.9447 / 0.9146 | 2/5 |
| 3 / Q4_0 | 0.6611 / 0.6404 | 0.9234 / 0.8858 | 4/5 |
| 23 / Q4_0 | 0.7193 / 0.7343 | 0.9173 / 0.9382 | 2/5 |

Local improvement is inconsistent across layers and does not survive as a reliable
request gain. The real-model connection uses no extra copy or CPU synchronization;
the remaining hypotheses concern kernel work distribution and graph scheduling,
not an assumed upload/download bottleneck.


One separate 200/32 one-shot memory observation with fusion OFF/ON reported the
same peak RSS, 195,493,888 bytes; process footprint was 163,431,504/163,251,280
bytes. macOS process RSS/footprint do not account for every Metal allocation.
Together with the unchanged graph storage and absence of native allocations,
this supports no observed added per-request storage; it does not establish a
GPU-memory reduction.

The kernel is reusable for contiguous Q4_0 gate/up, F32 vector input and SiLU
split semantics within its declared shape bounds. Another Qwen size can reuse
that operation; 0.8B generation and the alternate local shape already pass.
Additional quantization formats, batched prefill specializations, other devices,
and full Gemma model semantics still need their own implementation and owners.
Gemma normalization, activation, attention and position rules must come from its
model definition; there is no blanket Gemma-support claim.

Next hypothesis: tune threadgroup/rows-per-SIMD work distribution using the
captured real FFNs and then the same request A/B owner. The fused projection
changes register pressure and scheduling relative to two independent matvecs;
current data do not isolate either as the cause. If that does not improve requests,
test a larger normalization/FFN/down/residual boundary and its allocation/dependency
handling. Fewer dispatches alone were insufficient here. The unconditional-barrier
trial already shows why local kernel gains must be tested after connection.

## Reproduction

Use a clean GGML checkout at `.llama-revision`; the recipe refuses a dirty source.
Keep GGUF, pack, captures and generated artifacts outside Git. Set `GGML_SOURCE`,
`BASE_BUNDLE`, `TRIAL_ROOT`, `REFERENCE_LIB`, `MODEL`, `PACK`, `IR`, and tool output
paths to your local prepared inputs. `REFERENCE_LIB` must contain llama.cpp built
from the same pin. On this macOS host the repository needs GNU make (`gmake`).
The normal native dependency/library search setup is in
[Align development](align-development.md).

```sh
python3 scripts/gpu_backend_recipe.py --backend metal --native-swiglu \
  --source "$GGML_SOURCE" --output "$TRIAL_ROOT"
ALIGN_LLM_GGML_INCLUDE="$GGML_SOURCE/ggml/include" \
ALIGN_LLM_GGML_LIB="$TRIAL_ROOT/bundle" \
ALIGN_LLM_GGML_SHIM_DIR="$TRIAL_ROOT/shim" gmake build

clang++ -O3 -std=c++17 -I"$GGML_SOURCE/include" -I"$GGML_SOURCE/ggml/include" \
  -L"$REFERENCE_LIB" -Wl,-rpath,"$REFERENCE_LIB" -lllama -lggml \
  scripts/bench-native-llama.cpp -o "$LLAMA_BENCH"
clang++ -O3 -std=c++17 -I"$GGML_SOURCE/ggml/include" \
  -L"$TRIAL_ROOT/bundle" -Wl,-rpath,"$TRIAL_ROOT/bundle" -lggml -lggml-base \
  scripts/bench-native-swiglu.cpp -o "$FFN_BENCH"
clang -dynamiclib -undefined dynamic_lookup scripts/trace-native-ffn.c -o "$TRACE"
```

Build the unchanged control from `ca609a41` in a separate checkout against the
base bundle and its own shim directory. Copy the normal runtime-options document
for each arm and set its `backend_bundle` to that arm's bundle. Supply CONFIG as:

```json
{
  "model": "GGUF_PATH", "pack": "PACK_PATH", "geometry": "MODEL_IR_PATH",
  "control_commit": "FULL_CONTROL_COMMIT",
  "control": {"binary": "CONTROL_MAIN", "options": "CONTROL_OPTIONS", "lib": "BASE_BUNDLE"},
  "candidate": {"binary": "CANDIDATE_MAIN", "options": "CANDIDATE_OPTIONS", "lib": "TRIAL_BUNDLE"},
  "llama": "LLAMA_BENCH", "trace": "TRACE_DYLIB"
}
```

```sh
python3 scripts/measure-native-swiglu --config "$CONFIG" --output "$NEW_RESULT"
python3 scripts/measure-native-swiglu --native-ab --config "$CONFIG" --output "$NEW_AB_RESULT"
```

For captures, compile `scripts/capture-native-ffn.c` as its header describes.
Run a normal control request with `ALIGN_FFN_CAPTURE` naming an existing directory
and `DYLD_INSERT_LIBRARIES` naming that capture library. It retains activation
lifetimes and saves the first decode FFNs; never load it during timing. Then run:

```sh
python3 scripts/check-native-captures weights "$MODEL" "$IR" "$CAPTURE"
"$FFN_BENCH" "$TRIAL_ROOT/bundle/libggml-metal.so" "$CAPTURE" 0 2048 6144 3
"$FFN_BENCH" "$TRIAL_ROOT/bundle/libggml-metal.so" "$CAPTURE" 3 2048 6144 2
"$FFN_BENCH" "$TRIAL_ROOT/bundle/libggml-metal.so" - 0 1024 3584 2 --check-only
"$FFN_BENCH" "$TRIAL_ROOT/bundle/libggml-metal.so" - 0 1024 1024 2 --alias-input
```

Repeat `--check-only` for all layers, using down type 3 for layers 0..2 and 2 for
3..23. For paired logits, use the trace library with `ALIGN_FFN_LOGITS_DIR` and
`ALIGN_FFN_LOGITS_BYTES=993280`, run identical requests on each arm, and compare
with `python3 scripts/check-native-captures logits CONTROL_DIRECTORY CANDIDATE_DIRECTORY`.
Existing `scripts/run-qwen35-generation-smoke` uses its documented `QWEN35_*`
inputs; enable the candidate environment for that unchanged owner.

Bounded retrospective: actual kernel selection needs evidence, not just an opt-in
label. Existing FFI labels were diagnostics, so the explicit fusion-request ABI
and graph trace are essential to this trial. Real GGUF byte/type checks also
prevented extending the synthetic all-Q4_0 down assumption into the mixed-format
model. These owners stay with this capability rather than becoming global gates.
