# Contiguous F32 Metal copy trial (2026-09-27)

This is a retained historical experiment. Its measured result is unchanged,
but current development uses the [independent Metal state-copy trial](qwen35-native-state-copy-trial.md)
against an unmodified ggml bundle. The source patch is not the intended
deployment route.

## Hypothesis and implementation

The actual Qwen3.5-2B final decode graph has 18 DeltaNet state copies of
1,048,576 bytes each and 18 convolution state copies of 73,728 bytes each.
The DeltaNet source and destination are contiguous F32; the convolution source
is strided. Pinned ggml's generic `kernel_cpy_f32_f32` converts its flattened
source coordinate back into destination dimensions with integer divisions.
The patch in [`metal-linear-copy.patch`](../scripts/metal-linear-copy.patch)
uses one linear index for F32-to-F32 copies of at least 262,144 elements when
both physical strides are contiguous. Every other layout and type keeps the
generic code. The predicate uses type, size and layout, not the model name.

The patch changes one Metal shader in pinned ggml
`bb4caa7540188872173c44d161602d9271386413`. Align still owns the
Qwen3.5 model graph, recurrent state, buffer allocation, failure publication,
generation and kernel selection at the graph level. The existing ggml graph,
Metal dispatch, command-buffer scheduling, shared buffers and synchronization
remain. There is no new CPU/GPU copy, retained tensor or ABI call. The
developer recipe offers `--linear-copy` as a default-off, digest-bound bundle
variant; the preceding adjacent-range bundle and the generic shader are the
comparison and rollback. The specialization is also independent of the
earlier adjacent-range scheduler patch, although this recipe requires that
patch and its verified core-reuse base to construct this trial bundle.

The actual 2B decode graph admits the linear path for the 18 DeltaNet copies,
or 18,874,368 bytes per generated token. Its 18 strided convolution copies
remain on the generic path. This is an inspection of real graph bindings, not
an assumption based on GGUF tensor metadata. The GGUF remains Q4_0; state
copies are F32. Their count, destination buffers and launch shapes do not
change. The common state buffers in the control and candidate are Metal shared
storage. The fast path removes address arithmetic; it does not reduce the
required state bytes or delete a synchronization point.

## Correctness and reproducibility

The fixed 2B GGUF SHA256 is
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
Both Align arms used the same binary SHA256
`b62a2d5d7e88dee85b4f3f672b4b4dca15a74d24fc5e89df5791cf277c6a0450`,
pack, Model IR, prompt token IDs, output count and execution flags. Native
SwiGLU, graph greedy, mapped weights and shared-logits modes were disabled;
prefill chunk width was 128 and final-chunk logits were enabled. Control
bundle ID was `a414d11a2fc9bd437550e35666c3115bf7253d0fecbce1b8069d58871e508527`.
The measured recipe trial bundle ID was
`79ec2cf34b45bd90239df29e6944c6c306ca32b489359fe639d138efb7e56ba8`,
with patch SHA256
`91d1de81a9ef63076fbd90d309766636c6529c6951cdc03d962b187686a2e798`.
The final checked-in patch removed two blank context lines that triggered the
repository whitespace check; its SHA256 is
`5ecb87bb7e2cca3fa2135ec1fb04443fe45d7fe80952e436856242a63b4e4abc`.
The rebuilt clean bundle ID is
`8467e3decec541f6d4b637df4cede3c7ca6e4981b9ac07eb3f42e2f88d3a03b8`.
The pinned llama.cpp executable SHA256 was
`f384a6a64603479cf5c675ba587aeafbd64a500c3129a0afdcd271dcf532717d`.

The discovery, measured recipe and clean final bundles have identical four
ggml core artifacts, plugin executable code and embedded Metal library;
only the plugin `__TEXT,__cstring` section differs, in temporary source-build
path strings. The exact
section comparison is in
[`binary-comparison.json`](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/binary-comparison.json).
The discovery bundle's three full 248,320-element 2B logit rows and 336
semantic resident-state hashes matched the unchanged control byte for byte,
without any relaxed tolerance. Both discovery and measured recipe bundles passed the
existing 2B and 0.8B generation owners, including six retained requests per
model, invalid-request recovery, and exact pinned llama.cpp output. The clean
final bundle repeated both model owners and contains the same executable
Metal code as the exact-vector and timed trials.
The backend recipe smoke, Python-boundary check, and patch identity checks
passed. CPU, CUDA and Gemma correctness are not asserted by these Metal tests.

The focused [copy geometry owner](../scripts/metal-linear-copy-geometry.cpp)
ran against the pre-copy control and the clean final plugin. All six cases
passed with every destination F32 bit matching an independent CPU copy oracle:
262,143 elements just below the threshold; 262,144 at the threshold; a
contiguous four-dimensional view; nonzero source/destination offsets; and
large strided source and destination views. The offset and strided cases also
checked untouched destination sentinels. Complete control and final
[geometry receipts](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/geometry-clean.jsonl)
are retained alongside the [control receipt](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/geometry-control.jsonl).

## Measurements

The Apple M1 16 GiB host ran five alternating
control/trial/pinned-llama pairs per case after two warm requests per process.
Each Align process executed three identical requests; the final warm request
was recorded. All arms used identical 2B GGUF bytes, input IDs and generated
token counts. `wall.json` and `final-wall.json` had no phase interposer;
`phase.json` measured synchronized graph-compute boundaries separately.
Control-minus-trial paired deltas are positive when the trial is faster.
Arm medians and paired deltas are distinct statistics. Every individual pair,
including adverse samples, remains in the receipts.

| Bundle / condition | Paired request delta median, range (ms) | Trial wins | Control / trial / llama request medians (ms) |
| --- | ---: | ---: | ---: |
| Discovery, 64 / 16 | +40.279, +22.813 to +41.023 | 5/5 | 557.184 / 517.550 / 548.988 |
| Discovery, 200 / 32 | +92.466, +82.440 to +100.002 | 5/5 | 1282.624 / 1189.204 / 1245.261 |
| Discovery, 330 / 64 | +184.232, +59.181 to +191.243 | 5/5 | 2414.635 / 2228.643 / 2378.798 |
| Measured recipe, 64 / 16 | +52.866, +49.784 to +57.974 | 5/5 | 590.590 / 537.751 / 575.620 |
| Measured recipe, 200 / 32 | +99.577, +70.820 to +108.201 | 5/5 | 1346.354 / 1248.917 / 1322.290 |
| Measured recipe, 330 / 64 | +193.448, +158.645 to +237.385 | 5/5 | 2548.918 / 2342.828 / 2506.181 |

The preceding control is the already experimental adjacent-range bundle. A
further **same-binary, uninstrumented** campaign compared the clean final
bundle directly with the pre-adjacent Metal bundle (ID
`8ae9b7ac9429d393c48f93f54bbe36417f2c0dd788937f307965c5e20b447965`)
and the same pinned llama.cpp. In-graph greedy was disabled in both Align arms;
all other request, bundle-core, weight, token, state and storage conditions
matched. The complete [base comparison receipt](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/base-vs-clean-wall.json)
retains all output/count checks, order and samples.

| 2B input / output | Base minus clean paired median, range (ms) | Clean wins | Llama minus clean paired median, range (ms) | Clean wins | Base / clean / llama arm medians (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64 / 16 | +55.011, +48.614 to +62.198 | 5/5 | +37.731, +31.496 to +39.537 | 5/5 | 559.949 / 506.182 / 542.375 |
| 200 / 32 | +111.526, +90.282 to +117.904 | 5/5 | +74.844, +58.902 to +101.515 | 5/5 | 1280.954 / 1169.142 / 1243.176 |
| 330 / 64 | +224.990, +210.787 to +247.549 | 5/5 | +151.089, +127.964 to +159.982 | 5/5 | 2430.834 / 2196.728 / 2351.591 |

The same direct-baseline protocol on the independently qualified 0.8B Q4_0
model also completed five pairs per condition. The clean bundle beat the
pre-adjacent Align bundle in all 15 pairs. It beat pinned llama.cpp in 14/15;
one 330/64 reference pair was faster by 15.966 ms. The complete
[0.8B direct comparison](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/base-vs-clean-08b-wall.json)
retains that adverse pair, matching outputs, exact processed counts and all
identities.

| 0.8B input / output | Base minus clean paired median, range (ms) | Clean wins | Llama minus clean paired median, range (ms) | Clean wins | Base / clean / llama arm medians (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64 / 16 | +60.626, +38.115 to +99.268 | 5/5 | +27.122, +14.865 to +32.711 | 5/5 | 339.447 / 284.490 / 313.176 |
| 200 / 32 | +110.062, +61.672 to +173.548 | 5/5 | +55.631, +36.555 to +84.283 | 5/5 | 752.395 / 650.602 / 717.178 |
| 330 / 64 | +230.010, +121.704 to +236.243 | 5/5 | +93.469, -15.966 to +133.105 | 4/5 | 1483.007 / 1264.940 / 1358.409 |

The measured recipe's request medians are approximately 7–9% below unchanged
Align and 5–7% below the pinned llama.cpp reference for these warm 2B
conditions. Those percentages describe the observations, not an admission
floor. The second campaign is slower in absolute time on all arms, so only
paired comparisons within each campaign support the conclusion.

The measured recipe bundle also ran five pairs per condition on the real Qwen3.5-0.8B
Q4_0 GGUF (SHA256
`57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`),
with its own pack and Model IR and the same token-count protocol. Its recurrent
state copy geometry satisfies the same contiguous predicate. This is another
Qwen size, not evidence for Gemma semantics.

| 0.8B input / output | Paired request delta median, range (ms) | Trial wins | Control / trial / llama request medians (ms) |
| --- | ---: | ---: | ---: |
| 64 / 16 | +44.761, -11.338 to +46.639 | 4/5 | 336.730 / 291.979 / 326.413 |
| 200 / 32 | +90.590, +51.217 to +90.906 | 5/5 | 751.407 / 661.038 / 721.817 |
| 330 / 64 | +177.847, +167.842 to +187.581 | 5/5 | 1430.705 / 1254.132 / 1390.946 |

The adverse first short pair is retained. Startup paired medians were
+6.079, -11.568 and -68.607 ms; this campaign also does not establish a
construction gain. All three trial request arm medians beat the pinned
llama.cpp arm under this protocol, while the exact 0.8B generation owner is
the correctness evidence.

The separate discovery-bundle phase campaign won 15/15 request pairs. Its
paired control-minus-trial synchronized prefill/decode medians were
+2.003/+40.285 ms at 64/16, +7.453/+74.351 ms at 200/32 and
+8.988/+201.741 ms at 330/64. These clocks include graph submission and
completion waits; they are not isolated shader timings. The larger decode
effect matches a state copy executed for every generated token. The full
phase receipt also retains complete request results and pinned llama.cpp.

A separate counter-enabled Metal System Trace profiled two matched 200/32
requests per Align bundle. The unchanged bundle had 199.922 ms of summed
`kernel_cpy_f32_f32` Shader Timeline samples; the trial had 11.228 ms.
The worker PID was selected independently for each trace. These sampled,
instrumented intervals identify the local mechanism, but are not exact
dispatch clocks or the marginal request saving. Other shader sample totals
also changed; the untraced paired requests above carry the performance claim.
The original trace bundles, exported rows and PID-filtered summaries are in
the resolved Git common directory under
`diagnostics/q35-ingraph-greedy-2026-09-27/counter-trace-20260927/`.
The portable [shader attribution record](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/shader-attribution.json)
retains the selected PIDs, bundle IDs, request counts and copy sample totals.

Measured-recipe paired startup medians (control minus trial) were +15.795,
+0.168 and +16.387 ms for the three conditions. Discovery-bundle startup
medians were +49.632, -18.433 and -108.795 ms. Construction-to-ready includes
uncontrolled OS file-cache effects; a startup improvement is not established.
The measured-recipe first-request paired deltas were +47.931, +96.534 and +208.629 ms,
consistent with the warm direction, but cold load and request costs should
not be conflated. The original campaigns did not measure process memory. The
patch adds no allocation and the graph/state buffer census is unchanged.

A separate five-pair alternating [macOS process footprint screen](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/footprint.json)
used the same saved 2B Align binary, one untimed process per arm, a fixed
200/32 request, three requests per measured process, and control/final bundle
IDs bound in the receipt. All actual token counts and rendered outputs agreed.
After the third request, the control/final process `phys_footprint` arm
medians were 145.345/145.392 MiB, process peak arm medians were
146.860/146.892 MiB, and RSS arm medians were 175.734/175.781 MiB. Paired
control-minus-final medians were +0.078, +0.062 and +0.078 MiB respectively;
individual physical-peak differences spanned -0.219 to +0.109 MiB. Startup
control-minus-final differences ranged -111.253 to +89.479 ms, median
-7.009 ms. This does not establish a startup or footprint change. macOS
`footprint` attributes memory to this worker process; it does not measure
total system or GPU physical memory. No GPU allocation was added in code.

Portable complete receipts:
[`wall.json`](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/wall.json),
[`phase.json`](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/phase.json),
[`final-wall.json`](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/final-wall.json),
[`final-08b-wall.json`](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/final-08b-wall.json),
[`base-vs-clean-wall.json`](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/base-vs-clean-wall.json),
[`base-vs-clean-08b-wall.json`](../eval/benchmarks/qwen35-metal-linear-copy-2026-09-27/base-vs-clean-08b-wall.json).

## Decision and next test

Recommend the explicit clean copy-specialized bundle for local Qwen3.5
inference on the tested Apple M1 host. The patch has exact observed numerics,
no new state owner, a repeatable warm-request benefit on the tested 2B and
0.8B models, and a direct lead over the pre-adjacent Metal bundle in all 30
new pairs. The 2B trial also beat pinned llama.cpp in all 15 new pairs; the
0.8B trial retained one pinned-reference loss. The focused view owner passes and the
measured process footprint is effectively unchanged. Keep the ordinary ggml
bundle as the rollback and retain an explicit bundle selection: startup is
inconclusive, total GPU/system peak is unmeasured, and other hosts/backends and
Gemma semantics need their own admission. No universal default is inferred
from one host. This decision uses the measured workload and remaining risks,
not a fixed percentage.

The type/size/layout predicate and recipe can be reused for another Qwen size
whose state copies satisfy it. Gemma can use this backend operation only after
its architecture-specific model semantics and graph are admitted; its
activation, normalization, attention and position behavior cannot be inferred
from this Qwen trial. CUDA needs an independently implemented kernel and a
qualified host. A follow-up analysis of the retained raw GPU counters now
associates Q4_0 and Q6_K decode matrix-vector work in both implementations
with high buffer-read pressure; its method, samples and attribution limits are
in [`gpu-optimization-lessons.md`](gpu-optimization-lessons.md). A later larger
GPU experiment needs a specific weight-traffic or
prefill compute hypothesis; the remaining strided convolution copy alone is
small after this specialization.

Rebuild from a clean checkout of the pinned ggml commit and a verified base
bundle:

```text
python3 scripts/gpu_backend_recipe.py --backend metal \
  --source PINNED_GGML_SOURCE --output NEW_TRIAL_DIRECTORY \
  --ingraph-argmax --adjacent-ranges --linear-copy \
  --base-bundle BASE_BUNDLE_DIRECTORY
scripts/run-gpu-backend-recipe-smoke
python3 scripts/check-python-boundary
```

Set the trial runtime options `backend_bundle` to the newly built `bundle/`
directory, then run `scripts/run-qwen35-generation-smoke` for both real
model sizes and `python3 scripts/measure-native-swiglu --native-disabled`
with the same binary, control bundle, pinned llama executable and prompt IDs.
The measurement tool retains its historical SwiGLU name; its execution record
shows native fusion disabled in both Align arms.

For the focused owner, compile
[`metal-linear-copy-geometry.cpp`](../scripts/metal-linear-copy-geometry.cpp)
against the pinned ggml headers and the same verified ggml core bundle, then
run the resulting executable once with each plugin path. The source header
contains the exact compiler form; the two JSONL receipts above contain every
case. For the process screen, use a `measure-native-swiglu`-style JSON config
with `model`, `pack`, `geometry`, `control` and `candidate`, each arm specifying
the same native `binary`, its own `options` and `lib`, and the common execution
settings `sync_weight_upload=0`, `prefill_chunk=128`, `final_prefill_logits=1`,
`final_ffn_row=0`, `mapped_weights=0`, `shared_logits=0`,
`graph_greedy=0`. `backend_bundle` must match the corresponding `lib`, and
all other runtime options must match between arms. Then run:

```text
python3 scripts/measure-metal-worker-footprint --config CONFIG.json --output FOOTPRINT.json
python3 scripts/measure-native-swiglu --config CONFIG.json --output WALL.json --wall-only --native-disabled
```

For the direct base comparison, set the config's control bundle to the
pre-adjacent bundle and candidate to the clean copy bundle; include the pinned
`llama` executable and `trace` path required by the existing wall harness.
The footprint screen compares the adjacent-range and clean copy bundles, so
the two receipts answer different baseline questions.
