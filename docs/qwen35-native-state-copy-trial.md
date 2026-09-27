# Independent Metal recurrent-state copy trial

Status: selectable experiment on Apple M1. The measured version uses an
unmodified pinned ggml Metal bundle. The ggml copy-source patch is not a build
or deployment dependency of this route.

## Boundary and mechanism

Align owns the Qwen3.5 state layout, decode graph, selection, parity, generation
loop and failure policy. On decode, it registers 18 contiguous F32 DeltaNet
state sources and resident destinations, each 1 MiB on the tested 2B model.
The existing ggml graph produces those sources and all other model operations;
its 18 matching copy nodes are omitted. The native Metal module borrows the
ggml-owned shared allocations through checked public buffer base/size accessors
and encodes the 18 copies in one blit command buffer. The module has no model
name or Qwen dimensions. It retains no second state payload.

The pinned `ggml_backend_graph_compute` is synchronous. After it returns,
the native command can run while the CPU reads and samples logits. Align waits
for the native completion before publishing recurrent parity or returning a
token. Workspace rebuild and session close drain the command and release the
borrowed views before ggml frees the underlying allocations. The ordinary
graph remains selected when `ALIGN_LLM_NATIVE_STATE_COPY` is absent or `0`;
`1` selects this experiment, and other values refuse session construction.
Only complete, contiguous, equally sized F32 tensors of at least 1 MiB in
shared Metal buffers are admitted. Prefill and strided convolution copies
remain on ggml. This is an independent execution seam, not a complete
independent inference backend.
The selected ggml device must be the sole `MTL0` entry and match the sole
physical Metal device. An ambiguous device selection refuses mode `1`; mode
`0` remains available. This guard was added after the measured M1 campaign,
whose device meets those conditions.

## Native command failure qualification

On the same M1 and 2B Q4_0 GGUF, two test-only real-shim builds injected failure
at distinct native boundaries. `ALIGN_LLM_GGML_FORCE=native-copy-submit` failed
after validating the actual borrowed shared-buffer views and before committing
a command. `native-copy-complete` committed and drained a real command, then
reported failure after a successful Metal completion. For each build, the
two-token mode-`0` control completed (31 prompt tokens); mode `1` returned the
exact worker envelope `{"schema_version":1,"status":"failed"}`, published no
generation result or token, and exited with code 2. The owner required the
corresponding native fault marker in the worker diagnostic, so an unrelated
failure cannot satisfy it. This checks real-model failure propagation and
cleanup at the process boundary. It does not simulate an actual GPU hardware
error or prove cross-device behavior. No inference timing claim is made from
these instrumented builds.

Reproduce with the same unmodified pinned ggml bundle used above. Set
`QWEN35_GGUF`, `QWEN35_EXPECTED_SHA256`, `QWEN35_ALIGNPACK`, `QWEN35_MODEL_IR`,
`QWEN35_RUNTIME_OPTIONS`, `QWEN35_LIB_PATH`, `ALIGN_LLM_GGML_INCLUDE`, and
`ALIGN_LLM_GGML_LIB` to the matching recorded inputs. For each `fault` in
`submit complete`, set `ALIGN_LLM_GGML_FORCE=native-copy-$fault`, build with
`gmake build`, save that `main` and its shim in a distinct scratch directory,
then run:

```sh
QWEN35_NATIVE_COPY_FAILURE="$fault" QWEN35_NATIVE_COPY_BINARY="<saved-main>" \
  python3 scripts/run-qwen35-native-copy-failure-smoke
```

The saved executable
must remain paired with the shim path recorded in its dynamic-library identity.

## Correctness

- A borrowed-buffer probe copied 1,048,576 bytes bit-identically on the M1.
- For an actual 2B 16-token generation, all 1,344 resident-state plane hashes
  and all 16 complete 993,280-byte logit-row hashes matched mode `0` exactly.
  Both arms produced the same text. No numerical tolerance was changed.
- The real 2B and 0.8B generation owners passed in mode `1`, including prompt
  lengths 31, 200 and 330, retained requests and malformed-request recovery.
  The 2B owner also passed in mode `0`. The 0.8B HTTP/SSE owner passed in mode
  `1`; invalid mode `2` was refused before session readiness.
- After review repair, the 2B generation owner passed again; a focused native
  device probe rejected a mismatched description and accepted the sole M1.

The diagnostic state tracer explicitly waits for the native command before
hashing; otherwise an asynchronous graph return would inspect unpublished
state. No forced Metal command-failure injection was performed. A native
submission or completion failure marks the session unhealthy; the independent
failure path still needs a focused fault-injection owner before default use.
The actual graph census has 66 `CPY` nodes for prefill in both modes, and 42
versus 24 for each decode parity graph (off versus native). Native mode adds
one Metal blit command buffer per decode step, containing 18 copies. This is
an operation/command count, not a latency estimate.

## Real-model comparison

Apple M1, Qwen3.5-2B Q4_0 GGUF SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`,
the same alignpack, Model IR, prompt IDs and greedy outputs in both arms.
Both Align arms used the same saved binary and the same **unmodified** pinned
ggml `bb4caa7` bundle, with only the native-state-copy selection differing.
The reference was pinned llama.cpp `bb4caa7` using the same GGUF and prompt
IDs. Each process ran three identical requests after warmup; the last request
was timed. Five pairs alternated execution order for each condition. Every
sample and identity is in the [reviewed wall receipt](../eval/benchmarks/qwen35-native-state-copy-2026-09-27-reviewed-wall.json).

| Prompt / output | Align off median | Align native median | Pinned llama median | Off minus native paired median | Native wins vs off / llama |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64 / 16 | 559.424 ms | 512.859 ms | 536.352 ms | +44.636 ms | 5/5 / 5/5 |
| 200 / 32 | 1276.273 ms | 1184.559 ms | 1234.637 ms | +88.505 ms | 5/5 / 5/5 |
| 330 / 64 | 2405.119 ms | 2228.568 ms | 2331.712 ms | +186.868 ms | 5/5 / 5/5 |

Pinned llama minus native paired differences were +22.890, +48.563 and
+103.143 ms. A preceding [wall receipt](../eval/benchmarks/qwen35-native-state-copy-2026-09-27-final-wall.json)
from the build before the device-identity review repair retained one 200/32
adverse pair: native lost 5.380 ms to ordinary Align and 8.367 ms to llama.cpp.
That observation is not removed by the later 15/15 result.
Construction to ready remained slower: candidate medians were 1010.318,
1019.687 and 1034.501 ms versus llama.cpp 457.631, 450.604 and 456.489 ms. Startup has
uncontrolled OS cache variation and was not improved by this decode change.
An earlier build, which differed by an unnecessary native-finish call in
mode `0`, won all 15 pairs against both controls with paired Align gains
+30.677, +71.222 and +157.546 ms. Its complete
[wall receipt](../eval/benchmarks/qwen35-native-state-copy-2026-09-27-async-blit-wall.json)
is retained; the final table above uses the more direct mode-`0` path.

The separate [phase receipt](../eval/benchmarks/qwen35-native-state-copy-2026-09-27-async-blit-phase.json)
is instrumented and used that earlier build. Later builds skip an unneeded
mode-`0` finish call after each decode graph and guard device identity; the
graph topology and native command are the same. Prefill graph paired differences were +0.050, -0.166 and
+0.974 ms; decode **ggml producer graph** differences were +51.364, +102.889
and +200.932 ms. The latter excludes the asynchronous native completion wait,
so it is not the entire decode saving. Whole-request paired gains in this
instrumented run were +32.443, +76.688 and +162.696 ms. The uninstrumented
wall receipt above is the request-speed evidence.

A separate 16-token command diagnostic recorded the first synchronous native
compute version at median 0.172 ms host preparation, 5.498 ms immediate wait
and 0.655 ms GPU interval for one 18-copy batch. The revised cached-view,
asynchronous blit version recorded 0.138 ms preparation, 0.658 ms final wait,
1.025 ms submission-to-completion and 0.647 ms GPU interval. These are
instrumented single-request medians, not a decomposition of the paired
request gain. The first same-binary five-pair campaign lost every Align pair
by 23.214, 37.698 and 71.939 ms paired medians at the three lengths; its
[complete receipt](../eval/benchmarks/qwen35-native-state-copy-2026-09-27-wall.json)
is retained. The improvement followed four combined changes: removing a
redundant ggml synchronize, caching borrowed Metal views, using a blit encoder
and moving the native completion wait after independent logits work. Their
individual contributions have not been isolated.

The [process-footprint receipt](../eval/benchmarks/qwen35-native-state-copy-2026-09-27-final-footprint.json)
used five alternating 200/32 pairs and the pre-review binary with the same
native command and bundle. Ready physical
footprint differed by -0.031 MiB (off minus native). After three requests,
off minus native physical footprint was -0.109 MiB median and physical peak
-0.531 MiB median: a small observed native increase. The preceding build's
[footprint receipt](../eval/benchmarks/qwen35-native-state-copy-2026-09-27-footprint.json)
had instead shown a +2.219 MiB off-minus-native difference. The direction is
not repeatable across these screens. This measures process footprint, not
total GPU/system memory. The native
module has two borrowed Metal views and one command buffer in flight per
session; it does not allocate a duplicate resident plane.

## Decision and expansion

Retain the native route as an opt-in experiment. It is correct on the tested
real-model paths and improves 15/15 reviewed paired warm requests on this M1 against
both unchanged Align and pinned llama.cpp, with positive medians at all three
lengths. Default use still needs focused native failure
injection and qualification beyond this one host; startup remains materially
slower than llama.cpp. The ggml copy-source patch stays a historical local
result, not the operating plan.

The shared-buffer bridge, checked copy descriptors, one-command scheduling,
deferred dependency wait and Align-owned selection can be reused where another
Qwen size has the same operation semantics and admitted F32 layout. Its actual
shape, quantization and state geometry require owner validation. Gemma may not
have DeltaNet state at all; only the device/ownership/scheduling mechanism is
directly reusable. Gemma activation, normalization, attention and position
semantics need separate model admission. The next independent Metal candidate
should own a larger decode segment, reducing the ggml/native queue boundary
while retaining the same exact state/logit and whole-request comparisons.
