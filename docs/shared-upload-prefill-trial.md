# Synchronous weight upload and larger prefill trial

## Scope and decision

This local trial starts at `4f56f410` on `agent/native-metal-ffn-integration`.
It implements two independently selectable changes in actual Qwen3.5 sessions:

- `ALIGN_LLM_SYNC_WEIGHT_UPLOAD=1`: synchronously set each weight chunk into the
  existing backend allocation, without the application's staging copy or an
  asynchronous transfer followed by a per-chunk backend wait.
- `ALIGN_LLM_PREFILL_CHUNK=512` (also accepts 256): allocate input planes for that
  batch width and use it in both normal and streaming prefill.

Defaults remain `0` and `128`. Both changes remain selectable experiments. Direct
upload demonstrates a reproducible startup benefit; its changed OS memory
accounting requires follow-up before default adoption. Larger batches do not yet
establish a repeatable whole-request improvement under this host's variation.
There is no improvement-percentage admission floor. No faster-than-llama.cpp or
coding time-to-passing-patch claim is made.

Align retains configuration, model semantics, memory budgets, loading, graph
construction, session state, reset and generation. The shim adds one scalar
transfer policy and a synchronous backend call. GGML retains the allocations,
tensor representation, GPU operations and command encoding. No independent C++
inference engine, Python production path, mmap or file-lifetime change is added.
Pack authentication and bounded reads remain unchanged; staging stays allocated
and budgeted to isolate the transfer experiment.

## Cause confirmed in the binary and on the device

The previous Metal path already allocated shared buffers. Each weight chunk then
went through application staging, `newBufferWithBytes`, a GPU blit and a backend
wait. The synchronous ggml setter uses `memcpy` for shared Metal storage and the
backend's synchronous implementation for other storage. A synchronization before
policy selection establishes readiness; borrowed input bytes never escape the
upload call. Bounds, upload ordering, counters and failure injection are retained.

Actual candidate shim disassembly at `_align_gpu_weight_upload` confirms the mode
branch at `0x33bc`: direct mode calls `_ggml_backend_tensor_set` at `0x33c4`;
legacy mode calls `_memcpy`, `_ggml_backend_tensor_set_async`, then
`_ggml_backend_synchronize` at `0x33f4`, `0x340c`, `0x343c`. These are CPU host
instructions, not GPU shader ISA. The pinned reference's mapped-weight path is
already documented in `llama-binary-comparison.md`.

At a 200-token prompt, the instrumented pre-first-graph command-buffer count is
1369 in legacy mode and 1 in direct mode. Prefill graphs are 2 at width 128 and 1
at width 512. The remaining initialization command is retained. These counts
establish removal of the transfer sequence, not a decode kernel speedup.

## Correctness

- `scripts/run-gpu-weight-upload-smoke`: legacy/direct chunk contents, unchanged
  direct-mode staging, bounds, lifecycle refusal, owner isolation and forced
  transfer failure pass.
- `LIBRARY_PATH=... scripts/run-gpu-device-smoke`: device ownership, allocation
  failure and cleanup pass. The first invocation lacked the Homebrew crypto
  library search path and failed linking; the configured rerun passed.
- `scripts/run-gpu-attention-policy-smoke SOURCE LIB PLUGIN`: 512-query admission,
  513 refusal, metadata allocation failure, typed fault semantics and existing
  F16 KV/attention arithmetic pass on the real pinned Metal backend.
- Direct-upload 2B generation passes. Combined direct/512 generation and
  `scripts/run-openai-serving-smoke` pass on 2B and 0.8B: exact reference output,
  repeated requests, malformed request recovery, SSE, disconnect and restart.
- Full-logit capture uses 64/16, 200/32, 700/64, 64/16 requests. Direct upload
  equals all 134 raw vectors exactly. Batch and combined modes equal all 128
  token-aligned final-prefill/decode vectors exactly (31,784,960 floats each).
  Legacy has six nonfinal-prefill vectors and width 512 has one; they occur at
  different token positions and are retained, not compared as if equivalent.
  The predeclared 0.01 absolute bound was unchanged; observed maximum is zero.
- Invalid upload/batch environment values are refused at session construction.
  The unchanged defaults pass the 2B generation owner, and direct/256 passes
  the 0.8B generation owner. Managed build, formatting, strict Python boundary
  and `git diff --check` pass.

Request 122 records the non-blocking imported-constant initializer compiler gap.
The application references the defining constant directly inside functions and
uses no proposed language feature.

## Measurement protocol

Apple M1, 16 GiB, macOS 27.0 (26A428); exact 2B Q4_0 GGUF, pack, token IDs and greedy output counts.
Align pin `b20429be50d6ab889496a0589143320683b29aeb`; ggml/llama.cpp pin
`bb4caa7540188872173c44d161602d9271386413`. Native SwiGLU is off in all arms.
The candidate and old binary have distinct shim locations and the same backend
bundle. The reference is the previously inspected pinned driver, with batch and
microbatch 512, four threads and Flash Attention enabled.

Worker campaigns use five alternating three-arm groups per workload, two warm
requests per process, then the measured third request. Startup is process
construction to ready; first-ready latency adds the first request. OS file and
pipeline caches are uncontrolled; these are not disk-cold measurements. The
upload campaign disables the phase interposer. The batch campaign uses the
existing phase interposer, with transfer mode fixed to direct in both Align arms.
Phase clocks include synchronization and differ from shader-only clocks.
HTTP/SSE uses two retained servers, two warmups and five alternating pairs per
mode/case. All outputs and actual token counts must match; all samples are kept.

The desktop remained active (WindowServer, terminal and browser activity), and
system swap usage was about 1.5 GiB during observation. Large slow samples affect
both Align and the reference. No sample was excluded or replaced. Small latency
differences cannot be separated confidently from this host variation.

## Worker results

Median milliseconds, five pairs per row. Upload trial: old Align versus direct
upload at unchanged batch 128, plus pinned llama.cpp. Phase clocks are omitted
because this campaign is uninstrumented.

| Input/output | Old startup | Direct startup | llama startup | Old warm | Direct warm | llama warm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 64/16 | 1027.31 | 494.14 | 458.06 | 573.17 | 570.57 | 547.51 |
| 200/32 | 1001.41 | 578.02 | 477.90 | 1316.33 | 1318.30 | 1261.42 |
| 330/64 | 1077.72 | 531.50 | 495.11 | 2638.14 | 2598.42 | 2624.41 |

Direct startup is faster in all 15 pairs. Paired median startup reductions are
52.09%, 42.28%, and 50.46%; construction-to-first-response reductions are 33.20%,
18.23%, and 17.79%, also 15/15 positive. Warm-request paired ranges cross zero in
all workloads: no decode/request speedup is established by direct upload alone.
The 330/64 median happens to beat this reference median, but the changing host
conditions and mixed pair outcomes do not support a competitive speed claim.

Batch trial: same candidate binary/bundle, direct upload in both arms. Below,
triplets are width 128 / width 512 / pinned llama.cpp. These are separate later
measurements and must not be subtracted from the upload campaign.

| Input/output | Prefill ms | Decode ms | Warm request ms |
| --- | --- | --- | --- |
| 64/16 | 141.67 / 137.41 / 138.61 | 475.09 / 466.29 / 457.12 | 626.85 / 616.10 / 602.42 |
| 200/32 | 543.52 / 523.09 / 538.18 | 1010.01 / 1004.89 / 1004.48 | 1573.98 / 1546.13 / 1525.78 |
| 330/64 | 986.55 / 1041.01 / 1045.59 | 2102.67 / 2256.77 / 2181.49 | 3115.74 / 3325.87 / 3227.69 |

At 200/32, paired median prefill improvement is 4.02% (range -0.19% to +4.92%),
and request improvement is 1.77% (range -0.83% to +4.80%), four wins each. At
64/16 both arms execute the same actual 64-token graph, yet timings also move;
this provides a useful variation control. The 330/64 candidate includes a
4147.41 ms sample and has a slower median. Width 512 remains an experiment;
neither the positive small result nor the negative noisy result is generalized.


## HTTP/SSE results

Old Align 0/128 versus candidate 1/512. Median milliseconds, five alternating
pairs after two warmup pairs; the repeated short row follows the long request.
Positive paired percentages mean faster. Every paired range crosses zero.

| Input/output | Mode | Old ms | Combined ms | Paired median change | Paired range | Faster pairs |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| 64/16 | HTTP | 856.41 | 973.97 | -4.94% | -21.13% to +4.91% | 2/5 |
| 64/16 | SSE | 968.39 | 981.93 | -0.41% | -10.92% to +8.94% | 2/5 |
| 200/64 | HTTP | 2765.74 | 2753.10 | +0.46% | -7.79% to +3.14% | 3/5 |
| 200/64 | SSE | 3165.20 | 3022.77 | -1.59% | -13.79% to +11.21% | 2/5 |
| 330/64 | HTTP | 3716.26 | 3477.54 | +9.68% | -2.87% to +15.55% | 4/5 |
| 330/64 | SSE | 3666.56 | 3494.03 | -2.81% | -5.55% to +9.86% | 2/5 |
| 700/64 | HTTP | 5865.70 | 6027.59 | -2.91% | -8.03% to +4.28% | 1/5 |
| 700/64 | SSE | 6302.86 | 6457.13 | -2.23% | -3.52% to +8.81% | 2/5 |
| 64/16 | HTTP | 1118.06 | 1120.29 | -0.49% | -1.61% to +2.09% | 2/5 |
| 64/16 | SSE | 1107.22 | 1114.23 | -0.10% | -0.94% to +0.80% | 1/5 |

The 700-token case is slower in four of five HTTP pairs and three of five SSE
pairs. Even when marginal medians favor the candidate, paired medians can be
negative as host conditions move. These regressions stay in the receipt; combined
mode is not adopted as the new default. Output, completion length, reset and
streaming agreement pass in every warmup and measured request.

## Memory, limits and evidence

At 200/32 the Metal trace reports the same maximum resource allocation for legacy
and direct-only modes: 1,290,174,464 bytes. Width 512 raises this to 1,296,187,392
bytes (6,012,928 extra bytes). This is a sampled Metal allocation counter, not
physical RAM usage or a complete allocator high-water mark.

A separate same-candidate 700/16 snapshot reports OS physical footprint 147.1M
(peak 148.1M) for legacy initialization and 1.3G for direct/combined initialization.
RSS is 181,984 / 1,357,456 / 1,361,568 KiB. The shared-memory virtual extent is
1.2G in all three snapshots; its resident/dirty portion changes from 66.1M to
1.2G. Application buffer ownership and Metal allocation totals do not add a
second weight buffer, but these observations do **not** prove equal system RAM
pressure. CPU/GPU page residency/accounting is a hypothesis to test, not a reason
to dismiss the footprint difference. No constrained-memory qualification or
memory-pressure benefit is claimed.

Apple's [Metal memory analysis guidance](https://developer.apple.com/documentation/xcode/analyzing-the-memory-usage-of-your-metal-app)
distinguishes resource events from VM footprint, and its
[shared-storage contract](https://developer.apple.com/documentation/metal/mtlstoragemode/shared)
requires completion before the other processor accesses a resource. This trial
preserves that ordering. One private-storage compatibility check with
`GGML_METAL_SHARED_BUFFERS_DISABLE=1` produces the same 31/3 output in legacy and
synchronous modes; full private-storage qualification remains deferred.

Raw paired measurements, output/count checks, identities, exact numerical results,
and numeric memory observations are in
[`shared-upload-prefill-metal-2026-09-26.json`](../eval/benchmarks/shared-upload-prefill-metal-2026-09-26.json).
Local diagnostic drivers, configs, disassembly, complete logs and vmmap output
are retained under the resolved Git common directory's
`diagnostics/shared-upload-prefill-2026-09-26`. Large float captures remain outside
Git. Baseline/candidate main SHA-256 values are
`a1a06bd14e8b0849ef6e4fc49e1ca3911d308dbba5ed261ff5eea6ff4211b822` /
`64833fcf3a09ce18d001c1a3a4cdaf9550b73c05de4c873171b9eee00078b6cc`.
The receipt binds each linked shim and changed implementation/tool source.


## Reproduction and reuse

Build baseline `4f56f410` and this candidate with the managed Align pin, the same
retained four-accumulator backend bundle described in `native-swiglu-followup.md`,
and distinct `ALIGN_LLM_GGML_SHIM_DIR` directories. On macOS use `gmake build` and
the documented Homebrew `LIBRARY_PATH`; preserve each binary's linked shim.

The measurement JSON configuration contains `model`, `pack`, `geometry`, `llama`
and `trace` paths; `control`/`candidate` each contain `binary`, `options`, `lib` and
optional `execution: {"sync_weight_upload":"1","prefill_chunk":"512"}`.
`control_commit` records the baseline, or null for same-candidate comparisons.
Use only the exact admitted 2B artifact, identical runtime options and bundle.

```sh
# upload.json: old 0/128 versus candidate 1/128
python3 scripts/measure-native-swiglu --native-disabled --wall-only \
  --config upload.json --output upload-results.json
# batch.json: candidate 1/128 versus the same candidate 1/512
python3 scripts/measure-native-swiglu --native-disabled \
  --config batch.json --output batch-results.json
# combined.json: old 0/128 versus candidate 1/512, with cases
# [[64,16],[200,64],[330,64],[700,64],[64,16]]
python3 scripts/measure-host-reuse --config combined.json --output http-results.json

# Existing diagnostic captures use the unchanged 0.01 absolute bound.
python3 scripts/check-native-captures logits OLD_CAPTURE BATCH_CAPTURE \
  --requests 64:16 200:32 700:64 64:16 --control-chunk 128 --candidate-chunk 512
```

To exercise the product directly, set the two documented environment variables
before the existing native `--runtime-session` or `--serve-openai` command. No
Python is needed in that execution path. Unset them, or use `0`/`128`, to return
to the established path. The default-off native FFN flag is independent.

The transfer policy is shape/quantization independent and reusable by other
Align-owned model loaders. Batch width and bounded input allocation are reusable
scheduling mechanisms, but another Qwen architecture or Gemma still needs its
own correct attention, recurrence, normalization, activation, position and state
semantics. CPU/CUDA and private Metal storage remain unqualified for this trial;
calling a backend's synchronous API is not a qualification claim.

Next hypotheses are concrete: determine how CPU versus GPU initialization
changes shared-buffer residency/accounting and memory pressure; then remove
unconsumed vocabulary projections and logits readbacks on nonfinal prefill
chunks, while explicitly retaining every recurrent/KV state update. For the
remaining decode GPU gap, isolate the real Q6_K output projection and the larger
FFN consumer, as the earlier binary diagnosis proposed. Neither speculative
optimization is counted as implemented or measured here.
