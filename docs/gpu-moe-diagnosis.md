# Resident OLMoE GPU diagnosis

The first 2026-09-13 host profile supports investigating GPU graph execution before optimizing
host topology hashing or input preparation. It does not yet identify an expensive GPU kernel,
prove GPU saturation, or establish a speedup against llama.cpp. Product code is unchanged.

## Subject and method

Apple M1, 16 GiB, macOS 26.6.2. The subject is current executable source
`ad94eb5a18e49695a0c2321da7c9c37bd7ddd2f7`, built with managed Align
`f502fe3da00ce0b39c4eeec40586b11688627fbd` and the retained admitted Metal v4 kit.
The build is marked dirty because the investigation plan/handoff were edited; its complete
executable-source map was checked before and after execution. Historical temporary binaries
were absent. This newly built subject is not a byte-identical replay of the old Metal campaign.

The existing session client ran the four fixed section 6.1 runtime requests in order:
short, same short, changed long, same long; greedy OLMoE, 128 completion tokens, one resident
session, 1 GiB host and 6 GB device limits. All four passed the existing integer-sequence/output
count check. macOS `sample` attached after readiness for 60 seconds at a 1 ms interval.
Sampling includes inter-request and post-request input waits, which are identified separately.
It is statistical host-stack occupancy, not CPU utilization or GPU-kernel duration.

| Main-thread stack | Samples | Share after excluding input-frame waiting |
| --- | ---: | ---: |
| GPU graph compute wrapper | 26,549 | 96.16% |
| Backend completion wait, included in graph compute above | 26,180 | 94.82% |
| GPU input update wrapper | 518 | 1.88% |
| Topology helper | 328 | 1.19% |

There are 51,593 main-thread samples, including 23,984 under `runtime_session_io.read_frame`.
The displayed denominator is therefore 27,609. Nested counts must not be added to their parents.
Backend waiting is `ggml_backend_graph_compute -> ggml_metal_synchronize -> waitUntilCompleted`.
It can include GPU compute, memory traffic and scheduling dependencies; a host sample cannot
separate them. The topology samples predominantly reach SHA-256, consistent with rehashing the
approximately 1.1 MB geometry JSON for each invocation. That source issue exists, but this profile
does not support making it the first material-win candidate. No speedup ceiling is inferred from
these approximate sample fractions.

For diagnostic context only, the four internal request observations were 4.989, 4.537, 12.331
and 10.712 seconds. Startup was separately 13.830 seconds; the complete diagnostic lasted
85.183 seconds, including profiler completion and identity rechecks. These instrumented single
observations are not benchmark medians, an intervention result, or a new historical baseline.

## Retained evidence

Artifacts remain outside Git in `moe-diagnosis-20260913` and
`moe-diagnosis-20260913-build`. The independent diagnostic driver, exact requests/command,
complete responses, worker log and profiler output are retained. It uses existing validation
and measurement definitions and does not add a Python product path.

| Artifact | SHA-256 |
| --- | --- |
| Build manifest | `de00d2e88ad5ea38cfc876bd67e6b3af7019cd133e411056abf4e1cf71549793` |
| Executable `main` | `72c45ec8f0947159309cee4fca27cf9e9322111f4ca18f7dd2899517ea0b1ca0` |
| Host diagnostic receipt | `3fd92b9bc2efa3c10bc74d4c9c84eb7180f5d3ac60206e9ac3bb04ea7adcb411` |
| Host sample | `31fce239423ab6f8c82e3d34e8d2d256e2618e4ca58967a78d27276c9ccb904e` |

Build command, with the retained role paths supplied explicitly:

```sh
LIBRARY_PATH="$OPENSSL_LIB:$ZSTD_LIB" scripts/build-gpu-independent-candidate \
  "$PINNED_GGML_SOURCE" "$METAL_KIT/profile.json" "$NEW_BUILD" --session
python3 "$DIAGNOSIS/diagnose.py"
```

The retained driver names the admitted local assets and the existing source tree. For a new
run, use a new external evidence directory and explicitly bind any relocated paths; do not
overwrite this diagnostic receipt. The build manifest binds the compiler, native libraries,
backend bundle and source closure. The driver receipt binds its own bytes and the plan used.

## Device tracing checkpoint

A separate Metal System Trace repeated all four requests successfully. Its 60-second capture
reached the time limit, but trace finalization exceeded the diagnostic driver's 90-second wait
after the last response. The driver terminated/reaped the tracer and closed the worker. Keep
`moe-trace-20260913` as INCOMPLETE; receipt SHA-256
`6fd5f81642ed8896f4b36196f1c88959cea5f0814db34e18b92c3b99f7ca1142`.
No kernel attribution is taken from the incomplete trace.

The subsequent 10-second capture, with a 300-second finalization allowance, completed and saved
successfully in `moe-trace-20260913-short`. All four responses again passed quality, and the
worker/tracer were reaped. It samples the beginning of the sequence, not all four complete GPU
executions. The export includes other desktop GPU processes; the summary filters to the owned
worker, PID 6916, before counting any interval.

- 578 compute intervals total 9.628146454 seconds, with no overlap among those selected intervals.
  Their observed extent is 0.474562083 through 10.882772666 seconds in trace time. Do not divide
  by the nominal 10-second recording limit; exported intervals can extend past that boundary.
- 1,298 blit intervals total 0.008582833 seconds. This measures the exported blit execution
  intervals, not host synchronization, queue latency or every possible memory cost.
- There are 802 trace-wide shader-list rows (44 for the worker), but **zero shader-duration rows and zero GPU shader samples**.
  Kernel names alone cannot attribute time to expert matmuls versus attention or routing.

| Successful trace artifact | SHA-256 |
| --- | --- |
| Receipt | `bb8fa01b6529403242107f264fcf59016d1f96dcd6cdf6641e12ad4b4b0b5bc8` |
| Complete trace file digest manifest | `92e223af207e92098dfc6b3241e774952cf6f15faa91f05a1f78b0f649a7da8d` |
| GPU/encoder/shader-list XML | `97249d107f62f765d65e140d98440784629a2508725cfe933b633aaeec68ae73` |
| Derived interval summary | `a7a5263778ee56a3cd90d4e658a4a8c5c5488adff525434cf1d5beaecdbc6dc9` |

## Counter-enabled attribution and selected consumer

Adding the installed `Metal GPU Counters` instrument to the same 10-second capture produced
shader timeline rows. `moe-trace-20260913-counters` completed with all four responses passing
quality. Filtering the export to the owned worker, PID 7942, gives 40,450 shader timeline rows
and 6.964104450 seconds of summed **sample duration**. These are sampled GPU attribution,
not exact per-dispatch stopwatch timings; the capture covers an initial part of the request
sequence, mixes prefill/decode, and has profiler overhead. Do not weight durations by the
reported percent-of-kick again or treat these fractions as an end-to-end speedup prediction.

| Shader | Summed sample duration | Share of worker shader sample duration |
| --- | ---: | ---: |
| `kernel_cpy_f32_f16` | 3.205688537 s | 46.03% |
| `kernel_mul_mv_id_q4_K_f32` | 1.741478656 s | 25.01% |
| `kernel_mul_mv_id_q6_K_f32` | 0.579991727 s | 8.33% |

Source explains a concrete conversion candidate: `align_ggml_op_flash_attention` casts complete
bounded K and V views from F32 to F16 on every invocation. The same shader also performs other
F32/F16 copies, so the table alone does not attribute all conversion samples to KV. Test retaining
the already-consumed F16 representation and converting only appended rows before considering
a replacement expert kernel. This supersedes the earlier lack of shader attribution, not the
historical benchmark results or the completed host observations.

Counter receipt SHA-256: `348c828c5339b1d20eb32a012f1bb19d4459e102522cb6ca61933335a9e6c3fd`.
Export SHA-256: `c6ffecd550d666a4d709105124bc0f509dd774b52106bb02ac9ef1f27e6cd08f`.
Derived summary SHA-256: `0e1dc5e2f49724f6871295cf6a9e87b33db085247c9fccf38efd668a5d17ac8c`.

## Initial host-only decision (superseded by counter attribution)

Prioritize device execution attribution for resident OLMoE. The initial host and GPU interval
evidence does not support a material-win campaign centered on geometry-hash caching, small-input
transfer batching or full-logit readback elimination on this Metal workload. It also does not
prove that these mechanisms are immaterial on CUDA or other workloads.

Before choosing a custom expert kernel, obtain actual per-dispatch timing for expert matmuls,
routing and attention, separating prefill and decode. The current trace configuration does not
provide that attribution; explicit backend timestamp/counter instrumentation or an independently
available GPU profiler is the next required diagnostic surface. Its contract must preserve the
production graph/fusion path and disclose observation overhead. Do not serialize every graph
node and present the resulting altered execution as production kernel timing.

Continue using the existing Align session and thin native backend boundary. Retain production
router expansion, exact serial-output owners and all historical NOT_MET results. No speculative
kernel implementation, new Align capability request or relaxed correctness threshold follows
from these observations. The bounded retrospective is to keep raw host waits, GPU interval
occupancy and per-kernel attribution distinct, and bound trace finalization as well as recording.
This is diagnostic guidance, not a new routine publication gate.

## O1 implementation checkpoint

The counter-selected intervention retains half-precision KV in supported Metal OLMoE serial
sessions. New rows convert during writes; Flash consumes existing half views without another
full-history cast. The exact aligned allocation is measured through the existing backend API,
with unchanged logical capacity and budget limits. Positive padding uses the pinned F32-only
kernel through a bounded widening fallback.

The real `scripts/run-gpu-attention-policy-smoke` owner PASS covers incremental half rounding
against actual graph casting, prefix preservation, overwrite, tail padding, invalid policy,
layout/type/stride/extent and metadata-exhaustion refusal, cleanup and exact Flash equality.
`scripts/run-gpu-session-reuse-smoke`, `make fmt` and `git diff --check` PASS. Both native builds
complete, but shipping session acceptance correctly refuses the first uncommitted candidate.
A clean committed build and full independent session qualification precede paired measurement.
No speed improvement is claimed at this checkpoint.

## O1 local paired result

Review found that the original control receipt did not strictly authenticate its dirty source
state. Preserve this initial run as diagnostic evidence, but do not use it as shipping performance
acceptance. The completed repair rebuilds the same `ad94eb5` source in a clean checkout and verifies both
builds, control commit/clean source closure, compiler, pin, bundle and non-shim libraries before
and after repeating the unchanged five-pair protocol. The results below are from that clean-control
rerun. No runtime code changes were required.

The clean `d60e2b6` candidate passes the unchanged independent serial oracle: all seven Qwen2
and nine OLMoE requests match the pinned llama.cpp driver in complete output and exact token
counts, including seeded OLMoE repeats. The allocation-count session owner passes both models;
OLMoE observes 237,296,931 requested host bytes within 324,013,024 reserved bytes, with
17,974,079 native host bytes and a 1,073,741,824-byte host budget.

Five alternating control/candidate pairs on the same Apple M1 16 GiB host and admitted Metal
kit completed in 364.87 seconds, below the predeclared 2,400-second experiment ceiling. Each
fresh session executes all four fixed requests with greedy 128-token output. All 40 responses
pass the fixed quality check and every paired output/count matches exactly. No profiler ran
during timing. Each row reports the median paired reduction; the displayed times are separate
arm medians and are not used to calculate that reduction.

| Case | Control wall median (s) | Candidate wall median (s) | Median paired reduction | Faster pairs | Local target |
| --- | ---: | ---: | ---: | ---: | --- |
| Cold short | 4.909 | 2.749 | 44.00% | 5/5 | MET |
| Warm short, cached | 4.637 | 2.463 | 46.00% | 5/5 | MET |
| Warm long, changed | 12.160 | 4.463 | 63.33% | 5/5 | MET |
| Warm long, cached | 10.546 | 2.761 | 73.82% | 5/5 | MET |

Startup is separate: control/candidate medians are 12.892/12.876 seconds. Request wall and
producer internal nanoseconds are both retained in every response record; no startup saving is
claimed. The control is the clean manifested rebuild of `ad94eb5`, not llama.cpp. Both builds
pass shipping verification with equal managed compiler, pin, bundle and non-shim libraries;
the control commit, clean checkout and complete source closure are checked before and after.
Model, limits and driver are unchanged.
These results meet O1's local intervention floor. They establish neither superiority to a
contemporary llama.cpp baseline, a CUDA improvement, nor time to a passing coding patch.

Retained evidence directories are `moe-f16-clean-20260913-build`,
`moe-reference-20260913-build`, `moe-f16-independent-clean-20260913`,
`moe-f16-host-capacity-20260913`, `moe-control-clean-20260913-build` and
`moe-clean-pairs-20260913` in the local model/evidence store.
The last contains the complete independent measurement script, exact commands, requests,
responses, all pair orders, startup/internal/wall timings and worker logs. Reproduce the local
experiment with `python3 "$PAIR_EVIDENCE/run.py"` after explicitly setting its root/build/kit
locations to the retained immutable artifacts; preserve all build and source verification.
The superseded original run remains in `moe-local-pairs-20260913` with result digest
`58a37693b33bc84ad3fae76bdb7affe74fb8482e28ded957d58a31baba1003ad` for audit only.

| Artifact | SHA-256 |
| --- | --- |
| Clean candidate `build.json` | `6d5033beb0b3a884174a5cd744d9e3baae3968245444d39b98b673a8d63483aa` |
| Clean control `build.json` | `6e100f35a2e9a0d31f7f0e13707c6a6f8d285c594c34317fa615ff53c6048b09` |
| Independent reference `build.json` | `798286d19108bec688cc940e771693f92e6f83b813ccfb0c55ac7a83a01ad9fa` |
| Independent session `result.json` | `f93a68e079a838e16fc31312324450c36b25624786762625dd049d0629e6a420` |
| Host-capacity `result.json` | `cfa24b62c9c2817c21ce02d3fe9ea64a025c10cc85129abc778e4569fc8fff29` |
| Clean local pair `run.py` | `b6dccce1efb680b74f3d048f4292f3dbb5f3d5055cd41b109ee06964ee59bd0e` |
| Clean local pair `result.json` | `8c90e8a564a9164500318a0af3343cf0a149aa4f392ef581b75549607203b369` |

Bounded retrospective: keep exact native allocation accounting when changing storage dtype,
authenticate both clean executable source closures, validate actual conversion arithmetic before
whole-model acceptance, and use paired wall time
to qualify a profiler-selected intervention. Existing owners cover these failure classes; no new
routine aggregate or publication gate is introduced.

## Startup capped-read loader repair

The retained O1 runtime uses a 16 MiB staging limit for both resident loaders. The independent
payload-only probe at accepted commit `d60e2b626ae69837d96df1866c728d4c5864ff40` replayed the
exact Qwen and OLMoE pack-piece orders with a reusable libc `pread` buffer. It changed only the
destination capacity, hashed every consumed prefix and did not load a model, flush caches or run
the GPU. Three alternating pairs per model completed within the 120-second probe budget; all six
pairs had equal consumed-byte counts and equal SHA-256 digests.

| Model | Members / `pread` calls | Useful bytes | Current fetched | Capped fetched | Current / capped median wall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5-Coder 7B Q4_K_M | 339 / 565 | 4,677,120,000 | 9,473,210,368 | 4,677,120,000 | 3.456 s / 2.625 s |
| OLMoE 1B-7B Q4_K_M | 3,219 / 3,227 | 4,211,730,432 | 54,123,923,456 | 4,211,730,432 | 10.196 s / 2.084 s |

The repair on `agent/capped-read-loader-repair` keeps the accepted pack plans and upload state
unchanged. Each lexical capacity epoch constructs one local buffer at
`min(staging_bytes, remaining_member_or_piece_bytes)` and reuses it until that capacity changes;
the loop backedge drops the old epoch local before the next allocation. The syscall therefore
cannot fetch bytes beyond the current declared payload prefix, while consecutive equal-sized
expert pieces share the allocation. Existing positive-count, short-read and upload error handling
remains fail-closed. The two existing loader smokes passed after the source change; the test-only
observer owner checks requested capacities, payload offsets, returned counts and fault refusal.
Exact output/count equality is owned by the matched native Align session. This is startup/read-
amplification evidence; it is not a whole-session, llama.cpp or CUDA performance claim.

Probe artifacts are retained outside Git under the retained model-artifact directory
`o1-capped-read-probe-20260913`: `capped_read_probe.py`, `result.json` and
`raw.jsonl`. The fresh committed candidate also passes the required independent session owner
(seven Qwen2 and nine OLMoE requests, exact output and token-count equality) in
`capped-read-session-independent-20260913`.

The bounded startup campaign used the same admitted Metal kit and native Align framed-session
options for the clean `d60e2b6` control and committed capped-read candidate. It launched one fresh
process per arm, alternated control/candidate order across five pairs per model, issued one fixed
greedy 128-token request, and recorded readiness/startup and first-request clocks separately. The
campaign completed in 272.56 seconds under the 900-second ceiling. Every pair had exact response
and token-count equality.

| Model | Pairs | Control startup median (s) | Candidate startup median (s) | Median paired startup reduction | Candidate faster | Control first-request median (s) | Candidate first-request median (s) | Guardrail / target |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Qwen2.5-Coder 7B Q4_K_M | 5 | 3.803 | 2.889 | 24.05% | 5/5 | 11.799 | 11.809 | MET, median regression -24.05% |
| OLMoE 1B-7B Q4_K_M | 5 | 11.688 | 4.481 | 61.58% | 5/5 | 2.732 | 2.709 | MET, >=15% and >=4/5 |

The startup result receipt is retained as `capped-read-startup-20260913/result.json` with SHA-256
`6a0dc12d5c99262187154cd285093c3caadf8f5d4f2fbbf7316e28837008ea95`; its external driver
`run.py` has SHA-256 `21f832d9c2a6e4faf3600cc3d77d06846b6d00763cac8de732ff884038d50c57`.
The session-independent receipt is `capped-read-session-independent-20260913/result.json` with
SHA-256 `6088e53da7859f3ed986f8278e93ca133d02bb1415100669f385fb2bd4c8c448`.

| Build identity | Source commit | `build.json` SHA-256 | `main` SHA-256 |
| --- | --- | --- | --- |
| Clean control | `d60e2b6` | `6d5033beb0b3a884174a5cd744d9e3baae3968245444d39b98b673a8d63483aa` | `c5f833798762c54285e24a47fe2ee358f0c620dd130389ed5bee048fd3b39f7b` |
| Capped-read candidate | `ebeabac` | `1a4eb31b09a738b2bb24170e07967e2698ca5f5a84e27868c884e3240138cb32` | `e8b8b418804c45f135fb48a208656518756cb32be2e210c0f851c3b4c0e851eb` |

These are native Align startup/read-amplification results. They do not claim a llama.cpp or CUDA
comparison, a whole-session decode speedup, or a coding wall-time improvement.
