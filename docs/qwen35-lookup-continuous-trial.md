# Qwen3.5 continuous prompt-lookup trial (2026-09-28)

## Decision

Continue the **explicit, default-off** Align trial. It gives a repeatable
complete-generation gain on the repeated bug-fix continuation, but loses to
ordinary Align generation on the test-writing continuation. Do not enable it
for product requests yet. No ggml source patch is added: Align owns the
lookup, four-row target graph, acceptance, parity rollback and generation
loop; pinned ggml still executes the model matrices. The normal and streaming
product entrypoints remain selected by their callers.

The first mismatch discards all four candidate results, restores prefix
recurrent parity, performs one ordinary decode and disables further target
attempts for that request. Full acceptance commits the three drafts and bonus
token. The implementation uses the existing prefill graph slot and resident
weight/KV allocations. It synchronizes for the target result and native
prefill-state copy before publishing tokens or state.

## Real-model correctness

Apple M1 Metal, Qwen3.5-2B Q4_0 GGUF, its identity-checked alignpack and
Model IR, and the existing mixed native state/convolution-copy options were
used. `ALIGN_LLM_NATIVE_SWIGLU=0` kept the matrix path fixed. The three
coding prompts have 61/96, 99/75 and 72/96 input/output IDs. Every normal,
trial and pinned llama.cpp sample generated the exact recorded greedy IDs.
The bug-fix stream ends in EOG. The trial also handled output limits 1–4
without constructing a target graph, refused a draft containing a selected
EOG despite enough output room, and published no result for an empty prompt.

The [correctness receipt](../eval/benchmarks/qwen35-lookup-continuous-correctness-2026-09-28.json)
uses real continuation prefixes where the first candidate group accepts
0, 1, 2 or 3 drafts. Ordinary and trial generation each ran three successive
requests in one session per case, and every output ID matched the pinned
stream. The receipt checks the expected commit/discard counters. Earlier
[acceptance-state screening](qwen35-lookup-draft-screen.md) compared selected
and next F32 rows and valid KV/recurrent state under predeclared numerical
bounds for actual-weight groups. The connected trial's intermediate state was
not independently traced at every generation step, and a forced graph or
readback failure has not been injected. These remain admission work, rather
than being inferred from matching output IDs.

## Complete-request measurement

The same diagnostic binary alternated ordinary Align and trial Align for five
pairs per case, then trial Align and unmodified pinned llama.cpp
`bb4caa7540188872173c44d161602d9271386413` for five pairs. Each arm had
an excluded warmup; both comparison orders alternated. The pinned reference
loads the identical GGUF, uses GPU layers, F16 K/V (matching the selected
Align attention policy), flash attention, context/batch 512 and four CPU
threads, and checks every greedy ID. The fixture, weights, options, binaries,
generated counts, execution flags and individual samples are in the
[raw receipt](../eval/benchmarks/qwen35-lookup-continuous-2026-09-28.json).
Times below are medians in milliseconds. A positive paired delta favors the
trial; medians are reduced from the individual paired deltas, not subtracted
from separately rounded arm medians.

| Case | Ordinary Align generation | Trial generation | Paired ordinary − trial; wins | Pinned llama.cpp generation | Paired llama − trial; wins | Paired fresh-process llama − trial; wins |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Function 61/96 | 2609.3 | 2633.9 | -4.5; 2/5 | 2843.0 | +177.1; 5/5 | -368.6; 0/5 |
| Bug fix 99/75 | 2213.9 | 1728.7 | +491.6; 5/5 | 2353.4 | +619.9; 5/5 | +93.2; 5/5 |
| Tests 72/96 | 2700.3 | 2772.7 | -74.4; 0/5 | 2892.1 | +120.2; 5/5 | -456.6; 0/5 |

The pinned-reference arm is a separate alternating campaign, so its trial
median is not the same sample set as the ordinary-Align arm. Fresh-process
wall time includes launch, model load, validation and cleanup. It is therefore
materially different from loaded-session generation time. The trial beats
llama.cpp's loaded generation in these 15/15 paired samples, but beats its
fresh-process wall time only for the bug-fix case.

Trial phase medians in milliseconds were:

| Case | Prefill | Ordinary serial decode | Target graph build | Four-row target compute | F32 target readback | Full groups / discarded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Function | 138.8 | 2370.9 | 19.7 | 91.0 | 1.6 | 1 / 1 |
| Bug fix | 236.4 | 918.3 | 50.1 | 500.1 | 11.1 | 10 / 1 |
| Tests | 183.2 | 2522.1 | 12.9 | 46.0 | 0.8 | 0 / 1 |

These are host intervals around dependent GPU work, not GPU shader-time
counters. Trial lookup itself totaled only 0.007–0.011 ms per request. The
trial's process-wall-minus-generation estimate was 0.98–1.09 s across cases;
the pinned caller's independently timed load/context creation was about
0.40 s. Those startup fields have different boundaries, while the paired
fresh-process wall comparison uses the same outer timer. No normal-Align
phase trace was added by this diagnostic; the ordinary and trial paths share
the same prefill implementation, and prior phase profiling remains in
`qwen35-current-native-mixed-bottleneck.md`.

The trial allocates one request-owned four-row F32 logits staging buffer
(3,973,120 bytes for this vocabulary), bounded token/position/mask staging
and a slot table. It does not allocate a second model weight or KV arena.
The earlier independent four-row graph screen measured 1,987,456 additional
workspace bytes at its empty-prefix shape; connected per-request peak memory
and Metal dispatch counts were not captured here. Eleven bug-fix verification
groups copy roughly 44 MB of F32 logits to host; the measured aggregate
readback is 11.1 ms, well below the 500.1 ms target compute interval.

The pinned Align compiler built the diagnostic and real-shim product `main`.
The existing `scripts/run-qwen35-generation-smoke` passed 31-, 200- and
330-token prompts, six retained-session requests, invalid-input recovery and
single-token early exit against pinned llama.cpp. `gmake fmt`, the Python
boundary guard and its mutation suite, script syntax checks, and
`git diff --check` passed. The ordinary `gmake build` uses the repository's
unavailable-engine stub unless explicit ggml inputs are supplied; the product
owner above used a direct pinned-compiler build linked to the real shim.
The pinned llama.cpp source checkout was clean at the named revision; the
measured reference binary and Align diagnostic SHA-256 values are in the raw
receipt. The reference `libllama.dylib` SHA-256 was
`5f22c4fcebfab8ff556c08794eb15c52c76c547d623c57ec0bb2af119b54d07f`.

## Reproduction and next experiment

Build the Align diagnostic with the exact `.align-revision` toolchain and
the current shim on `LIBRARY_PATH`:

```sh
LIBRARY_PATH="$QWEN35_SHIM_DIR:$QWEN35_LINK_LIBS" \
  ./scripts/alignc build src/runtime_qwen35_lookup_trial_smoke.align
```

Compile `scripts/bench-qwen35-lookup-reference.cpp` against the unmodified
pinned llama.cpp headers and libraries. Then run
`scripts/verify-qwen35-lookup-continuous` and
`scripts/measure-qwen35-lookup-continuous --reference-binary ... --pairs 5`
with the fixture, GGUF, pack, Model IR, options, Align diagnostic binary and
library path shown in their `--help`. The receipt hashes identify the exact
artifacts. The local paths in the raw receipt are measurements, not product
configuration.

Next, test a lower-cost first verification group or a measured confidence
condition for the first n-gram hit. The test-writing task loses because its
only attempted four-row group rejects immediately; the bug-fix task wins by
committing ten groups before rejection. A candidate must preserve the
rejection-state and full-logit checks and rerun whole requests; a local
two-row win alone is insufficient. Another Metal generation, CUDA, other
Qwen shapes and Gemma remain unmeasured. The n-gram search and bounded
accept/discard control can be reused, while each architecture needs its own
attention/recurrent semantics, target graph and state qualification.
