# Independent Metal Q4_0 tile-consumer FFN screen

Status: this mapping is withdrawn before runtime integration. It passes the
predeclared local numerical checks on actual Qwen3.5-2B FFN captures, but its
complete FFN operation is consistently slower than the unmodified pinned ggml
Metal graph on the tested Apple M1. The result does not reject independent FFN
execution or other ways to distribute gate/up and down work.

## Tested boundary

The standalone [screen](../scripts/bench-metal-q4-tile-ffn.mm) reads captured
Q4_0 gate/up/down weights and F32 decode activations from real 2B layers 3 and
23. It leaves the ggml reference graph and model runtime unchanged. In each
native command, a threadgroup computes 64 hidden gate/up rows, applies the
Qwen SiLU gate, keeps the tile in threadgroup memory, and consumes it against
down weights for all output rows. One 786,432-byte partial-output buffer and
one 8,192-byte final-output buffer are the only result allocations. A second
dispatch reduces the 96 tile partials, with an explicit buffer barrier inside
the same compute encoder. Weights and input are uploaded once per local arm;
there is no per-operation upload or intermediate CPU readback. The benchmark
keeps separate reference and native weight allocations because the two arms
are independent.

The selected local mapping uses 512 threads/16 SIMD groups per tile. The
benchmark refuses devices without SIMD32 and enough threads per group. The
shape, Q4_0 type and SiLU semantics are explicit local admission conditions;
they are not installed in model loading. The 2B layers 0..2 have Q4_1 down
weights, so this mapping does not claim to cover them. Another Qwen size needs
its actual geometry/quantization checked, and Gemma needs its architecture's
own activation and graph semantics. CUDA needs a separate implementation.

## Correctness and measurement

The complete [receipt](../eval/benchmarks/qwen35-native-q4-tile-ffn-2026-09-28.json)
records model/plugin/source/capture hashes, every pair, the tested variants
and the admission policy. Captured ggml output matched the rebuilt reference
exactly. The final 512-thread native result's maximum absolute difference from
the ggml reference was `1.78814e-7` for layer 3 and `9.53674e-7` for layer
23. A separate 256-wide/96-hidden synthetic case exercises the 32-element
tail of a 64-element tile; maximum difference was `1.41561e-7` for both runs.
All outputs were finite and passed the bound declared before implementation:
`0.005 + 0.0005 * abs(reference)`. No tolerance was widened. Reusing one
command queue and the same buffers across warmups and timed operations produced
the same output. The tool exits on allocation, encoder or command failure;
process-owned Metal/ggml allocations are released when the local run ends.

All arms use the same captured bytes and pinned unmodified ggml Metal plugin.
After twelve warmups per arm, each of five pairs alternates twenty complete,
synchronized FFN operations per arm. `ggml_ms` and `native_ms` are host elapsed
times including dispatch and completion. `native_gpu_ms` is the Metal command's
GPU interval, not an isolated tile-kernel clock. The reference GPU interval
is unavailable from this benchmark. The table uses the median of pair means;
the paired difference is the median of `ggml_ms - native_ms` and can differ
from the two arm medians.

| Captured layer | ggml median | Native median | Native GPU interval | Paired ggml minus native | Native wins |
| --- | ---: | ---: | ---: | ---: | ---: |
| 3 | 0.775 ms | 1.347 ms | 1.025 ms | -0.582 ms | 0/5 |
| 23 | 0.771 ms | 1.404 ms | 1.102 ms | -0.647 ms | 0/5 |

The first scalar Q4_0 loop was slower still. Reusing the existing packed Q4_0
dot method improved it modestly; 512 threads beat 256 on this local screen,
but 1024 threads regressed. Splitting down output rows across two groups per
hidden tile repeated gate/up work and also regressed. The receipt retains all
twelve five-pair runs, including those unsuccessful variants and a fresh final
owner rerun. The rerun's paired ggml-minus-native medians were -0.657 ms for
layer 3 and -0.508 ms for layer 23, again with 0/5 native wins per layer. This is evidence
that this mapping's gate/up sharing and down-row scheduling fail to recover
the cost of the long per-group work on this M1. It does not isolate the precise
register, occupancy or memory-stall cause; a Metal counter/timeline capture
would be needed to distinguish those contributions.

The measured warm setup values are affected by library and pipeline caches:
the first scalar layer-3 process reported about 220 ms to compile pipelines
and about 10 s to initialize its first ggml Metal reference; subsequent runs
reported much smaller values. These are not comparable cold-start results.
The fused arm uses 786,432 bytes of partials and an 8,192-byte output; total
driver/GPU memory and request-level memory were not measured. No prefill,
decode request, startup or llama.cpp claim follows from this local test.

## Decision and next hypothesis

Do not integrate this 64-hidden-row, one-group-per-tile implementation with
real inference. Its local complete-operation loss is large and repeats on two
actual Q4_0 layers, so connection overhead would only add risk for this exact
mapping. Keep the ggml model path and prior selectable native state-copy path.
Next, isolate the down projection's address/dispatch behavior with counters
and test a schedule that exposes output-row parallelism without recomputing
gate/up tiles. That may use a bounded shared gated vector within a native
command and a specialized down dispatch. It should be compared on the same
captured bytes before another real-model integration; a separate activation or
model family still needs semantic qualification.

Reproduce with the pinned ggml headers and bundle named by the receipt:

```sh
GGML_INCLUDE=... GGML_BUNDLE=... CAPTURE_DIR=... \
  scripts/run-native-q4-tile-ffn-screen
```

The capture is development data and is not committed; it was created by the
existing native FFN capture owner from the GGUF identified in the receipt.
