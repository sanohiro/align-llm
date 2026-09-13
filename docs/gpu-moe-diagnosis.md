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
