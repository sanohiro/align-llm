# Qwen3.5 exact-prefix target continuation screen (2026-09-28)

## Decision

Continue the Align-owned target-verification experiment. A four-row target
graph processes four **actual continuations of the same 200-token prefix**
faster than four serial decode graphs on this M1, even after charging the
current prefill graph switch. Complete logits and the state read by the next
step met predeclared numerical bounds. This is a developer diagnostic, not a
speculative-generation or whole-request speed result. Ordinary generation
still uses its existing selectable path.

## Connected experiment

The Align diagnostic `runtime_qwen35_target_continuation_smoke` builds the
existing Qwen3.5 model graph from the real Qwen3.5-2B Q4_0 GGUF and alignpack.
The 200 prefix IDs are copied from the earlier [target-batch receipt](../eval/benchmarks/qwen35-target-batch-bound-2026-09-28.json);
the pinned llama.cpp `bb4caa754` oracle produced target input IDs
`[16, 220, 17, 220]`. Both arms execute that same prefix, then either one
four-row all-logits graph or four one-token decode graphs. The diagnostic
warms its exact path, zeros resident state, and repeats it before recording
synchronized graph compute and readback. Five process pairs alternate arm
order. The [fixture](../eval/fixtures/qwen35-target-continuation-200.json) and
[raw receipt](../eval/benchmarks/qwen35-target-continuation-2026-09-28.json)
pin the token IDs and binary, model, pack, backend and tracer hashes.

The pinned shim has one prefill graph context. The batched arm therefore
invalidates the prefix graph, constructs and prepares the target graph, and
charges this switch to target time. Neither arm omits state publication or
the required graph synchronization. The batch arm reads four complete F32
logit rows; the serial arm reads the same four rows. Weights and resident
state stay on the same Metal device. The graph, positions, masks, parity and
control flow are Align-owned; pinned ggml executes the graph's matrix kernels.
No ggml source patch, second weight payload or Python inference path was
added.

| Five-pair result | Serial four steps | Batched four rows |
| --- | ---: | ---: |
| Prefix synchronized compute, median | 382.904 ms | 382.953 ms |
| Target synchronized compute, median | 112.109 ms | 45.895 ms |
| Target F32 readback, median | 0.207 ms | 0.502 ms |
| Prefix-to-target graph switch, median | 0 ms | 2.920 ms |
| Diagnostic process wall, median | 1893.583 ms | 1765.881 ms |
| Reported graph workspace | 18,360,544 B | 4,220,000 B |

The paired **serial minus batch connected-target** median, including target
compute, graph switch and four-row readback, was **+63.126 ms**; all five
paired deltas were positive: 64.560, 62.717, 65.523, 63.126 and 62.826 ms.
This measures target verification with four supplied tokens, not the cost of
obtaining those tokens. Process wall includes weight load, graph preparation,
shader setup and the diagnostic's different graph inventory; it is not a
clean startup comparison. The serial diagnostic prepares both decode parity
graphs, whereas the batch path reuses one prefill context. Workspace is the
shim's graph allocation counter, not process peak memory. Neither process
wall nor workspace is a product adoption result.

Every complete logit value in all five pairs was finite and satisfied the
declared `abs(batch - serial) <= 0.05 + 0.001 * abs(serial)` bound. Largest
absolute differences by row were 0.001069, 0.001167, 0.001496 and 0.001380;
both arms chose `[220, 17, 220, 18]`. The independent, untimed state tracer
compared the first 204 positions of the 12 F16 KV planes and the active
parity of the 36 F32 recurrent planes. All 1,253,376 valid KV elements and
5,050,368 active recurrent elements were finite and within the separately
declared `0.005 + 0.0005 * abs(serial)` bound, with maxima 0.00390625 and
0.00174713. Inactive recurrent parity and unused KV capacity are not inputs
to the next token. This establishes bounded local arithmetic, not exact
byte identity or safe partial rollback.

## Reproduction and remaining work

Build with the pinned Align compiler and the same pinned Metal shim/bundle:

```sh
LIBRARY_PATH="$SHIM:$GGML_BUNDLE:/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib" \
  ./scripts/alignc build src/runtime_qwen35_target_continuation_smoke.align
scripts/measure-qwen35-target-continuation \
  --binary ./runtime_qwen35_target_continuation_smoke \
  --geometry "$MODEL_IR" --gguf "$QWEN35_GGUF" \
  --pack "$QWEN35_ALIGNPACK" --backend-path "$GGML_BUNDLE/libggml-metal.so" \
  --bundle-id "$GGML_BUNDLE_ID" --library-path "$SHIM:$GGML_BUNDLE" \
  --fixture eval/fixtures/qwen35-target-continuation-200.json \
  --state-tracer "$STATE_TRACER" --pairs 5 --output "$RESULT_JSON"
```

`$STATE_TRACER` is built from `scripts/trace-qwen35-state.c` with the pinned
ggml headers as described in the [four-row screen](qwen35-target-all-rows-screen.md).
Weights, binary and state dumps remain local, outside Git. The checked-in
driver validates complete extents, finite values, logits, greedy choices and
the active-state trace before it publishes its receipt.
The pinned owner check passed, and four wrong mode arities plus a malformed
three-token target array were rejected. A local graph-compute interposer
forced the first timed serial target step to fail; the diagnostic exited
unsuccessfully with zero of four result files published. These checks do not
exercise a product acceptance transaction.
After review, an independent non-greedy four-token fixture also passed the
same real-model numeric/state check; oracle greedy expectations are now
fixture-specific, so valid supplied target sequences are not rejected merely
because the model would have chosen different tokens.

Next, build an Align-owned bounded acceptance transaction. Full acceptance,
partial acceptance and first-token rejection must preserve the target
distribution and the exact state the next token reads; failures must leave no
published token or reused contaminated state. Measure a cheap draft source,
actual acceptance and rejected work, then compare complete requests with
ordinary Align and pinned llama.cpp. Another Metal generation, CUDA, other
Qwen geometries and Gemma need their own semantic and backend qualification.
