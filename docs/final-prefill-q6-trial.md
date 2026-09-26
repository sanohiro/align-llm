# Final-prefill output elision and native Q6_K trial

## Decision and implementation

This capability starts at `1ae5824a` on `agent/native-metal-ffn-integration`.
Adopt final-chunk-only prefill logits for the qualified Qwen3.5 Metal session.
`ALIGN_LLM_PREFILL_FINAL_LOGITS` defaults to `1`; explicit `0` restores the old
graph/output behavior. Other strings fail before weight allocation. Weight upload
remains legacy, chunk width remains 128, and native SwiGLU remains off by default.
There is no mandatory improvement percentage. This is a useful long-input
prefill/request improvement, not a universal throughput or llama.cpp victory.

Align now selects the graph's required outputs in both normal and streaming
generation. Nonfinal prompt chunks expand every recurrent/KV state commit and
its producer dependencies. They do not expand the final hidden output or
vocabulary head. Consequently the final layer's unused query/attention/output/FFN
tail and output normalization/projection/readback do not execute. The final
chunk and all decode steps still produce logits. The source builder still
constructs unused tail metadata; this change removes graph execution work.
The output mode enters the fixed-length hashed graph identity.

State ownership, synchronization, reset, parity publication and failure handling
are preserved. GGML still owns tensor allocation, device kernels and command
encoding. There is no new retained buffer, state owner, model format, C++ engine
or Python production path. The independent native Q6_K kernel below was tested
but is **not** integrated: its load strategy did not show a repeatable benefit.

The initial `head_only` experiment retained the final hidden root and removed
only the vocabulary head. Its raw results remain in the receipt as a separate
stage. The adopted `state_roots` implementation received fresh correctness and
performance checks; the earlier result is not substituted for those checks.

## Correctness and executed work

- Both Qwen3.5-2B and 0.8B pass the existing exact pinned-llama generation and
  HTTP/SSE owners: retained requests, malformed sampling recovery, one-token
  exit, reset, stream disconnect and server restart.
- The 2B boundary sequence is `128/1, 129/3, 256/3, 257/3, 512/3, 513/3, 700/64,
  64/16` (input/generated tokens), in a retained session. At **each** chunk width
  128, 256 and 512, old versus new same-width final-prefill/decode captures match
  exactly: 96 vectors and 23,838,720 floats per width, 71,516,160 floats total.
  Maximum absolute difference is zero, with identical argmax. The predeclared
  0.01 absolute bound was unchanged. Nonfinal baseline vectors are retained.
- Earlier cross-width comparisons, old 128 versus new 256/512, produced maxima
  0.00507879 and 0.00526619 with identical greedy output. Same-width controls
  isolate these batch-dependent differences from output elision; they are not
  silently treated as an exact result.
- An independent diagnostic hashes **all** 84 resident state planes, including
  both recurrent banks and unused KV tails, after every successful synchronized
  graph in a `200/3, 64/3` session. All 588 plane records/hashes agree at seven
  corresponding graph steps. Plane type, extent and strides also agree. This
  diagnostic adds no graph nodes and is never enabled during timing.
- Rebuilding with default `1` is separately qualified with the flag absent,
  explicit `0` rollback, generation/serving owners and the full state diagnostic.
  Invalid empty, `2`, `true` and `01` values remain refused. The existing 2B
  generation owner also passes with experimental native SwiGLU enabled together
  with default final-only prefill; neither experiment's performance is conflated.

The first nonfinal graph's operation counts directly confirm the work removed:

| Operation | Old | New |
| --- | ---: | ---: |
| MUL_MAT | 187 | 181 |
| CPY | 66 | 61 |
| SET | 12 | 12 |
| SSM_CONV | 18 | 18 |
| GATED_DELTA_NET | 18 | 18 |
| FLASH_ATTN_EXT | 6 | 5 |
| GLU | 24 | 23 |

The five removed CPY operations are not persistent state writes. All 48 explicit
state-write roots remain: two for each of 18 recurrent layers and two for each
of six attention layers. Attention SET returns the persistent destination view;
recurrent builders explicitly expand convolution and delta-state copies.
Full-plane equality checks the result, not just the node names.

Peak reported Metal resource allocation is **1,290,174,464 bytes in both arms**.
The diagnostic observes 1,383 command buffers in each arm: 1,369 before the first
graph and 14 across seven graph calls. This change removes operations within
the existing boundaries; it does not remove required synchronization. Allocation
equality is not proof of equal OS physical-memory pressure. CPU hash/readback
and vmmap snapshots are diagnostics, not performance measurements.

## Conditions and provenance

Apple M1, 16 GiB, macOS 27.0 (26A428). Identical Qwen3.5-2B Q4_0 GGUF,
weights, prompts, greedy generation and actual output counts. The vocabulary
projection is Q6_K inside this same GGUF; no quantization change is made.
Align pin `b20429be50d6ab889496a0589143320683b29aeb`; llama.cpp/ggml pin
`bb4caa7540188872173c44d161602d9271386413`. All timing arms use native FFN off,
upload mode 0 and Align chunk width 128. The reference uses its established
512 batch/microbatch, four threads and Flash Attention. Different batch handling
is stated explicitly; input IDs, work and weights are the same.

Worker measurements use five alternating old/new/reference groups per case,
two warm requests per process, then the third request. The phase interposer
records complete synchronized graph calls, not shader-only time. Startup is
process construction to ready, with uncontrolled OS caches, not disk-cold load.
HTTP/SSE uses the **same candidate binary** in two retained servers, explicit
flag 0/1, two warmup pairs and five alternating pairs per case/mode. The servers
process requests serially. Every output and actual work count must agree.

The desktop was active; unrelated sibling Align builds/tests and macOS/terminal
activity occurred during later campaigns. Swap was approximately 1.4–1.6 GiB.
The thermal command reported no warning, which does not prove constant clocks.
All measured samples are retained. No startup or decode speed claim is made.

The [primary receipt](../eval/benchmarks/final-prefill-metal-2026-09-26.json)
contains all four raw campaigns, paired summaries and correctness evidence.
Measured state-root binary SHA256 starts `c97a6edb92f0`; it had default 0 and
explicit flag 1. Final default-1 binary starts `9a85befca878`. Their graph path
is the same when enabled; default qualification is recorded separately from
the timing producer. Baseline binary starts `64833fcf3a09`, head-only starts
`97263935589a`. Full identities and source snapshots are in the receipt/local
diagnostic archive. Do not attribute the old timing artifact to the final binary.

## Real-model measurements

Worker medians in milliseconds, **old Align / new Align / pinned llama.cpp**:

| Input/output | Prefill | Decode | Whole request | Startup |
| --- | --- | --- | --- | --- |
| 64/16 | 125.06 / 125.25 / 125.85 | 428.64 / 431.47 / 427.87 | 568.21 / 571.60 / 553.72 | 1002.29 / 1062.29 / 430.31 |
| 200/32 | 522.17 / 491.64 / 499.87 | 1016.74 / 1011.52 / 1017.97 | 1599.43 / 1520.28 / 1507.48 | 1410.13 / 1063.47 / 1019.26 |
| 330/64 | 702.11 / 701.21 / 736.94 | 1905.48 / 1923.57 / 1917.15 | 2675.79 / 2685.41 / 2648.16 | 1237.69 / 1133.95 / 432.75 |

The 64-token case has no unused chunk output to remove. Its timing differences
are a negative control. At 200/32, paired prefill improvement has median 5.36%,
range -3.09% to 25.86%, four positive pairs. The 330/64 whole-request median is
slower, despite less executed work. These worker samples alone do not establish
a general whole-request win, and all three new request medians trail llama.cpp.

Same-binary HTTP/SSE measurements isolate the runtime switch. Marginal medians
are milliseconds; paired improvement is `100 * (off - on) / off` for each pair,
then its median. It is **not** the percentage difference of the two medians.

| Input/output | Mode | OFF median | ON median | Paired median improvement | Positive pairs | Paired range |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 64/16 | HTTP | 584.00 | 581.26 | 0.80% | 4/5 | -0.60% … 1.71% |
| 64/16 | SSE | 595.49 | 592.56 | -0.11% | 2/5 | -0.21% … 2.08% |
| 200/32 | HTTP | 1366.08 | 1346.20 | 1.68% | 5/5 | 0.70% … 2.08% |
| 200/32 | SSE | 1545.92 | 1651.13 | 2.74% | 3/5 | -9.40% … 12.69% |
| 700/64 | HTTP | 4397.54 | 4302.64 | 2.44% | 5/5 | 1.26% … 12.59% |
| 700/64 | SSE | 3545.91 | 3494.37 | 1.45% | 5/5 | 0.50% … 2.77% |
| 1536/1 | HTTP | 4851.70 | 4630.68 | 6.12% | 5/5 | 3.28% … 6.23% |
| 1536/1 | SSE | 4940.46 | 4691.67 | 5.21% | 5/5 | 4.36% … 5.96% |
| Return 64/16 | HTTP | 771.99 | 737.86 | 2.05% | 3/5 | -0.79% … 5.35% |
| Return 64/16 | SSE | 749.92 | 750.73 | 0.03% | 3/5 | -3.41% … 2.90% |

At 700/64, SSE first-token time is 1580.10 → 1520.06 ms; paired median improvement
4.78%, range 3.22–6.46%, five positive pairs. At 1536/1 it is
4937.94 → 4689.69 ms; paired median 5.16%, range 4.27–5.92%, five positive pairs.
The 200/32 SSE first-token marginal median is **worse**, 484.83 → 549.59 ms,
despite paired median +7.77% (four positive pairs, range -13.36–8.95%). Keep
that discrepancy and adverse pair visible; host variation is material.

The useful result is the consistent longer-input reduction across HTTP, SSE
and first-token time, supported by exactly equal output/state and fewer actual
operations. One-chunk/decode gains are unestablished. Default adoption also
considers no extra device allocation, small code/maintenance cost and explicit
rollback. Five samples on one active host are not a population confidence claim.

## Native Q6_K experiment

The [separate Q6 receipt](../eval/benchmarks/q6-projection-metal-2026-09-26.json)
retains all 1,200 timings and 30 paired summaries. Capture uses real 2B tied
`token_embd.weight`, `[2048, 248320]`, 417,177,600 bytes, and one final-prefill
plus two decode normalized activations from a 200/3 request. Every weight byte
agrees with the GGUF. Capture is independent diagnostic tooling and is disabled
for inference timing.

Pinned ggml uses two output rows per SIMD group, two SIMD groups (64 threads),
62,080 threadgroups and eight 256-value blocks per row. The native variant keeps
the same work mapping, quantization, accumulation and reduction order, but uses
paired aligned 16-bit quant loads. Q6_K's 210-byte block stride admits two-byte
alignment; arbitrary four-byte vector loads would be unsafe. The hypothesis is
less byte-load/address/unpack work; a compiler may already combine that work.

Full 248,320-row and 257-row-tail checks on all three captured activations have
maximum absolute difference **zero** and identical argmax (16, 220, 17). The
predeclared absolute limit remains 0.01. Twelve warmups precede five alternating
pairs per activation, twenty synchronized invocations per arm/pair. Separate
untraced and command-buffer-traced campaigns report:

| Activation | Untraced wall median, ggml/native ms | Traced GPU interval union median, ggml/native ms |
| --- | --- | --- |
| Final prefill | 7.5685 / 7.6171 | 7.2045 / 7.2634 |
| Decode 1 | 8.1095 / 7.9819 | 7.2478 / 7.2468 |
| Decode 2 | 8.6648 / 8.1430 | 7.2736 / 7.3201 |

Every paired improvement range crosses zero. GGML uses two command buffers per
invocation, native uses one; this alone did not deliver a repeatable improvement.
These local clocks are not an attributed fraction of real-model decode. The
probe holds two weight allocations; reported tensor buffers total 836,359,200
bytes, not a claim about peak OS memory.

The [Apple Silicon quantization profiling paper](https://arxiv.org/html/2508.08531v1)
motivates checking unpack/address work (§§5.3–5.5), but its M2/M4 results do not
establish an M1 benefit. Inspection of [upstream Q6_K source](https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-metal/kernels/mul_mv.metal)
and pinned llama.cpp found the same load/work mapping on this investigation date.
The local offline Metal compiler is unavailable
without the MetalToolchain component; runtime compilation works. No GPU ISA
disassembly or stall attribution is claimed. Prior host-binary findings remain
in [llama-binary-comparison.md](llama-binary-comparison.md).

Reject **this paired-load strategy** for production integration. Next native
work should first attribute the output projection within real-model execution
and establish attainable device-read bandwidth, then test a materially different
mapping or lossless layout. A separate larger candidate is tiled gate/up/SiLU/down
fusion with bounded partial-output reduction. It must preserve Q4_1 down weights
in the first three 2B layers and Q4_0 elsewhere. Neither next hypothesis is
implemented or proven by these results.

## Reproduction and model expansion

Build with the pinned wrapper (`gmake build` on this host); the existing model
kit supplies the authenticated pack, model IR, runtime options and library bundle.
Set `QWEN35_GGUF`, `QWEN35_ALIGNPACK`, `QWEN35_MODEL_IR`,
`QWEN35_EXPECTED_SHA256`, `QWEN35_MODEL_ID`, `QWEN35_RUNTIME_OPTIONS`,
`QWEN35_LIB_PATH`, `QWEN35_LLAMA_ORACLE` and `QWEN35_LLAMA_TOKENIZE` for the kit.

```sh
python3 scripts/run-qwen35-generation-smoke
python3 scripts/run-openai-serving-smoke
ALIGN_LLM_PREFILL_FINAL_LOGITS=0 python3 scripts/run-qwen35-generation-smoke
python3 scripts/check-native-captures logits OLD_CAPTURES NEW_CAPTURES \
  --requests 128:1 129:3 256:3 257:3 512:3 513:3 700:64 64:16 \
  --control-chunk 128 --candidate-chunk 128 --candidate-final-only
python3 scripts/measure-native-swiglu --config worker-config.json --output worker.json --native-disabled
python3 scripts/measure-host-reuse --config http-config.json --output http.json
gmake fmt
python3 scripts/check-python-boundary --strict
git diff --check
```

Measurement configuration follows the existing scripts: binary/options/library
per arm, common model/pack/geometry/reference, explicit
`sync_weight_upload: "0"`, `prefill_chunk: "128"` and `final_prefill_logits: "0"`
or `"1"`. HTTP cases are `[[64,16],[200,32],[700,64],[1536,1],[64,16]]`.
Run GPU campaigns serially. Capture/check all three widths separately. Build and
usage instructions for Q6 capture/probe and state hashing are at the top of their
source files. The local diagnostic archive retains exact scripts/configurations,
producer source snapshots, binaries, logs and capture manifests outside Git.

Final-output selection is independent of model size and device; its safe graph
pruning depends on each model builder making every persistent-state write an
explicit root. Qwen3.5 2B and 0.8B are qualified here. Other Qwen architectures
must establish that dependency contract. Gemma requires its own normalization,
activation, attention and positional semantics; it is not admitted by shape
matching. The Q6 probe parameterizes width/row count, but only width 2048 and the
full/tail row cases were checked. It can be reused for matching quant/layout
cases; other formats or semantics need separate implementation and validation.
CPU/CUDA qualification and Gemma admission remain deferred, explicitly recorded
in the backend register. No new Align language/runtime gap was encountered.
