# Qwen3.5 Metal adjacent-range scheduling trial (2026-09-27)

## Finding and change

The pinned ggml Metal scheduler records tensor memory intervals as half-open
`[p0,p1)` ranges, including the allocation extent for placed tensors. Its
intersection predicate in `ggml-metal-common.cpp` used `mr.p1 >= cmp.p0`, so
one range ending exactly where another begins was classified as a dependency.
`ggml-metal-ops.cpp` responds to a failed dependency check by inserting a
`memoryBarrierWithScope:MTLBarrierScopeBuffers` and resetting the range set.
The one-line patch changes that comparison to `mr.p1 > cmp.p0`. Real overlaps
still cause a barrier. This changes Metal graph scheduling, not shaders,
quantization, model semantics, weights, tensor layouts, or the CPU/GPU storage
mode.

The independent Metal API interposer counted the final Qwen3.5-2B decode
graph. Control and trial each dispatched 663 kernels; buffer barriers fell from
469 to 399. The pinned llama.cpp reference dispatched 682 kernels and used 393
buffer barriers for its corresponding decode graph. The reproducible recipe
bundle independently reproduced 399 barriers and 663 dispatches. These are API
call counts, not GPU duration or proof that every removed barrier stalled the
device. The diagnostic logs remain in the Git common directory; the compact
identity and result record is in
[`verification.json`](../eval/benchmarks/qwen35-metal-adjacent-range-2026-09-27/verification.json).

The trial adds `gpu_backend_recipe.py --adjacent-ranges --base-bundle BASE/bundle`.
It applies the independent Metal patch to the pinned clean ggml source and
records the patch digest. A fresh ordinary build changes the shared ggml core
dylib hashes and the resident runtime refuses it against the already loaded
core. The trial recipe therefore verifies source, target, toolchain, nontrial
flags and every artifact in the base bundle, then retains those exact
core bytes and the new Metal plugin. The default bundle is untouched. No new
runtime mode, Python inference path, buffer copy, device allocation, or session
owner is introduced. Align still owns the model, graph, state and generation;
ggml continues to execute the graph. The patch only changes the existing
Metal dependency scheduler.

## Correctness and comparison setup

The actual Qwen3.5-2B Q4_0 GGUF has SHA256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`;
its alignpack, model IR and prompt token IDs were unchanged. The ggml and
llama.cpp source pin was `bb4caa7540188872173c44d161602d9271386413`.
The measured Align binary SHA256 was
`b62a2d5d7e88dee85b4f3f672b4b4dca15a74d24fc5e89df5791cf277c6a0450`
in both arms. Its control backend bundle was
`8ae9b7ac9429d393c48f93f54bbe36417f2c0dd788937f307965c5e20b447965`;
the measured recipe trial bundle was
`ef88bfced485790dc8e1ffb478ec3d1de2f5c280e181eb16446df604cc1c114a`.
Its retained patch SHA256 is
`5ef5bcea8f78d4a66e7fe2643a4b7a99e4e5d22722eaddcebfc0d588da6c7bf3`.
Removing a blank context line from the checked-in patch changed its file hash
without changing the applied C++ line. The final checked-in patch SHA256 is
`f636d7573dcc746cf9b05893f21c72b9fdd65a35276e86f34d62cbcaec550cf3`;
the final bundle is
`a414d11a2fc9bd437550e35666c3115bf7253d0fecbce1b8069d58871e508527`.
All four core artifacts, the plugin's executable text, and its embedded Metal
library are byte-identical between the measured and final recipe bundles.
Fourteen of fifteen file-backed plugin sections match; only `__TEXT,__cstring`
differs, in six temporary source-directory path strings. See
[`binary-comparison.json`](../eval/benchmarks/qwen35-metal-adjacent-range-2026-09-27/binary-comparison.json).
The pinned llama executable SHA256 is
`f384a6a64603479cf5c675ba587aeafbd64a500c3129a0afdcd271dcf532717d`.
Both Align arms disabled native SwiGLU and in-graph greedy, used shared Metal
storage, 128-token prefill chunks, and final-prefill logits. The reference
received identical prompt IDs, generation counts and GGUF.

For the final recipe artifact, three real full-vocabulary 248,320-element
logit vectors (744,960 F32 values) matched the control byte for byte; no
numerical tolerance was needed. All 336 retained-state plane SHA256 records
across four completed graphs matched exactly on the same 200-input/3-output
request. The existing generation owner passed on both the 2B and 0.8B Q4_0
models: three prompt lengths, exact pinned llama.cpp greedy text, six retained
requests per model including invalid-input recovery and early exit. The final
bundle repeated the exact full-logit and state comparison. The recipe smoke
and strict Python boundary check passed. The manually staged discovery bundle
had the same exact 2B logit and state result before the recipe was added.
No CPU, CUDA, or Gemma inference
qualification is claimed.

One comprehensive host-native review found that the recipe validated the
base core but accepted a missing or modified base Metal plugin, leaving no
usable control bundle. The accepted repair validates all five base artifacts
and adds missing-plugin, modified-plugin and modified-core refusal probes.
The recipe smoke, actual base-bundle validation and Python boundary check
passed after the repair. No measured shader or runtime path changed.

The worker benchmark ran five alternating control/trial/reference pairs per
case after two warm requests per process. Each Align session made three equal
requests and recorded the last request. The phase run used an interposer around
synchronized graph compute; the separate wall run omitted that interposer.
`prefill_ns` and `decode_ns` include the graph-compute boundary and its wait,
not individual shader clocks. `startup_ns` is construction to ready with OS
file cache uncontrolled. Paired deltas below are control minus trial, so a
positive value favors the trial. Arm medians are calculated separately from
paired deltas. The raw receipts retain every sample and the actual prompt IDs.

| Bundle / measurement | Input / output | Paired request delta median (ms) | Trial wins | Delta range (ms) | Control / trial / llama request medians (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Discovery, phase | 64 / 16 | +6.107 | 4/5 | -13.792 to +10.213 | 576.532 / 572.701 / 557.463 |
| Discovery, phase | 200 / 32 | +14.614 | 5/5 | +13.621 to +25.433 | 1326.341 / 1306.313 / 1278.716 |
| Discovery, phase | 330 / 64 | +17.971 | 5/5 | +12.004 to +68.991 | 2537.959 / 2523.456 / 2472.443 |
| Discovery, wall | 64 / 16 | -2.114 | 2/5 | -44.147 to +8.158 | 609.039 / 641.148 / 634.098 |
| Discovery, wall | 200 / 32 | +2.630 | 4/5 | -98.100 to +15.795 | 1300.297 / 1297.760 / 1269.366 |
| Discovery, wall | 330 / 64 | +14.176 | 5/5 | +4.002 to +67.159 | 2429.351 / 2406.672 / 2368.914 |
| Recipe, phase | 64 / 16 | -13.531 | 2/5 | -85.001 to +6.844 | 596.634 / 611.289 / 607.460 |
| Recipe, phase | 200 / 32 | -2.484 | 2/5 | -37.700 to +230.860 | 1388.978 / 1369.180 / 1341.816 |
| Recipe, phase | 330 / 64 | +22.264 | 5/5 | +3.181 to +49.392 | 2499.792 / 2485.183 / 2428.697 |
| Recipe, wall | 64 / 16 | +0.648 | 3/5 | -38.317 to +120.782 | 575.200 / 578.955 / 555.311 |
| Recipe, wall | 200 / 32 | -0.487 | 2/5 | -33.540 to +26.544 | 1324.959 / 1315.581 / 1290.495 |
| Recipe, wall | 330 / 64 | +7.674 | 3/5 | -103.731 to +93.587 | 2609.149 / 2644.871 / 2684.691 |
| Final patch, wall | 64 / 16 | +6.583 | 4/5 | -1.704 to +16.342 | 583.827 / 578.161 / 565.275 |
| Final patch, wall | 200 / 32 | +3.628 | 3/5 | -46.030 to +14.072 | 1333.351 / 1329.723 / 1291.268 |
| Final patch, wall | 330 / 64 | +12.966 | 4/5 | -134.671 to +586.905 | 2508.688 / 2499.316 / 2449.983 |

For the measured recipe phase run, paired prefill/decode medians were
-0.703/-11.721 ms at 64/16, +4.577/-14.621 ms at 200/32, and
+3.036/+14.822 ms at 330/64. The 200/32 request median includes a
+230.860 ms pair caused by a slow control arm; it is retained, not treated as
a stable speedup. The recipe wall 330/64 campaign also retained a -103.731 ms
pair. Its llama.cpp median rose to 2684.691 ms, making one trial arm median
appear faster than llama.cpp in that campaign, while both phase runs and the
discovery and final wall runs show llama.cpp faster. The final wall 330/64
campaign retained a +586.905 ms control outlier and a -134.671 ms reversal;
its positive paired median is insufficient for default adoption. There is no
repeatable competitive win. The measured recipe wall 330/64 startup paired
median was -179.628 ms with zero trial wins; final patch startup paired
medians were -62.509, -17.030 and -20.077 ms for the three cases, also mixed
at the individual-pair level. No isolated
load-only or physical-memory measurement was performed. The patch adds no
runtime tensor or explicit copy, but this does not prove unchanged system
memory pressure.

Complete machine-independent receipts:
[`diagnostic-phase.json`](../eval/benchmarks/qwen35-metal-adjacent-range-2026-09-27/diagnostic-phase.json),
[`diagnostic-wall.json`](../eval/benchmarks/qwen35-metal-adjacent-range-2026-09-27/diagnostic-wall.json),
[`recipe-phase.json`](../eval/benchmarks/qwen35-metal-adjacent-range-2026-09-27/recipe-phase.json),
[`recipe-wall.json`](../eval/benchmarks/qwen35-metal-adjacent-range-2026-09-27/recipe-wall.json),
[`final-wall.json`](../eval/benchmarks/qwen35-metal-adjacent-range-2026-09-27/final-wall.json).

## Decision and next GPU question

Retain the one-line correction as a default-off, reproducible Metal bundle
trial. Do not adopt it in the default runtime yet: correctness is strong and
the longer phase case improved, but the untraced request results and startup
are unstable, shorter requests can regress, and the pinned llama.cpp advantage
has not been closed reproducibly. This is a measured scheduling experiment,
not evidence that standalone shader optimization is exhausted.

The remaining 399 barriers and 663 dispatches on the long 2B decode graph
provide a narrower next target. On an isolated host, capture Metal System
Trace and available per-pass counters for matching Align and llama.cpp decode
commands, then separate GPU occupancy/bandwidth from command-buffer gaps and
compare the Q4_0 matrix-vector, DeltaNet, and small unary spans. In particular,
test whether their order or data placement explains the remaining gap before
changing tile sizes or fusing more work. The scheduler patch itself is
shape-independent and can be tested on other Qwen sizes after their model
owners pass. Gemma needs its own semantic model admission and exact oracle;
this patch does not implement its normalization, attention or position rules.

Reproduce the opt-in build using a clean pinned ggml checkout and an existing
validated baseline Metal bundle:

```text
python3 scripts/gpu_backend_recipe.py --backend metal \
  --source PINNED_GGML_SOURCE --output NEW_TRIAL_DIRECTORY \
  --ingraph-argmax --adjacent-ranges --base-bundle BASE_BUNDLE_DIRECTORY
scripts/run-gpu-backend-recipe-smoke
python3 scripts/check-python-boundary
```

Set each runtime options file's `backend_bundle` to its respective `bundle/`
directory, use the same Align binary and model files, and run the existing
`run-qwen35-generation-smoke` and `measure-native-swiglu --native-disabled`
worker owners with both bundles. The `--native-disabled` measurement artifact
kind retains its older SwiGLU name, but its execution record states both arms
have native fusion disabled; only the backend bundle differs.
