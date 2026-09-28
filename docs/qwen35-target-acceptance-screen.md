# Qwen3.5 four-row acceptance and rejection cost (2026-09-28)

## Decision

Continue the experiment, but do not integrate speculative generation into the
normal worker from this result. On an Apple M1 and real Qwen3.5-2B Q4_0,
four-row target verification wins when **all four** candidate tokens are
accepted. Rejecting at any of the four positions loses because the target
graph is paid in full and the accepted recurrent prefix must be replayed.
An inexpensive draft with a high rate of complete four-token matches, or a
shorter/adaptive group, is now the discriminating hypothesis. No draft cost,
accepted-token distribution or complete-request comparison was measured.

## Align-owned transaction

The developer-only `--verify-acceptance` mode extends the exact-prefix Align
smoke. It computes the real 200-token prefix and all four target rows, compares
candidate 0 with prefix greedy and candidates 1..3 with the preceding target
row, and stops at the first mismatch. Full acceptance commits the batch's
active recurrent parity. At zero acceptance, it restores the prefix parity;
at one to three, it restores prefix parity and replays only the accepted
tokens through synchronized one-token graphs. KV rows beyond the committed
length remain masked. The chosen distribution predicts the correction token
or the full-acceptance bonus token. The diagnostic then processes that token
once more and writes both complete F32 rows together, after every graph and
readback succeeds. `--serial-acceptance` uses the same candidate comparison,
but processes only accepted tokens plus the chosen token through one-token
graphs. The two arms make equal actual token and state progress.

Align owns token comparison, masks, graph selection, parity, replay and result
publication. Pinned ggml executes the Q4_0/Q6_K matrix and other graph
operations. There is no ggml source patch, second weight payload, product
Python path or product generation mode. The existing production mixed native
state-copy route remains available and was **not** the serial control here.

## Real-model result

The first [fixture](../eval/fixtures/qwen35-target-continuation-200.json)
contains the recorded 200-token prefix and pinned llama.cpp's four oracle
continuation IDs `[16, 220, 17, 220]`. Five case inputs replace only the
first rejected candidate with a different valid token (zero), keeping the
preceding accepted IDs. Each case uses five alternating M1 process pairs,
one exact-path warm replay, the same Q4_0 GGUF/pack/Model IR/Metal bundle and
complete selected plus next F32 rows. The connected interval begins after
prefix computation and ends after the next row's synchronized readback; it
includes candidate input updates, graph switching, target work, acceptance,
replay and the next actual token. Decode graph preparation is reported
separately. The [raw receipt](../eval/benchmarks/qwen35-target-acceptance-2026-09-28.json)
retains all samples and binary/model/backend hashes.

| Accepted candidates | Serial connected median | Batch connected median | Paired serial minus batch median | Batch wins |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 29.428 ms | 84.405 ms | −55.630 ms | 0/5 |
| 1 | 59.604 ms | 114.289 ms | −55.299 ms | 0/5 |
| 2 | 88.726 ms | 142.648 ms | −53.667 ms | 0/5 |
| 3 | 115.945 ms | 173.892 ms | −56.229 ms | 0/5 |
| 4 | 148.759 ms | 85.254 ms | +62.325 ms | 5/5 |

The target graph's synchronized compute median was 45.4–45.9 ms across the
five cases; prefix-to-target graph switching took 8.6–9.1 ms, higher than
the earlier 2.9 ms continuation screen with fewer prepared graphs. Replaying
one, two and three accepted tokens cost medians 28.846, 57.426 and 86.678 ms.
The batch's full-acceptance connected advantage includes its bonus token's
next decode, so both arms advance through the same resulting state. Decoder
graph preparation took about 3.7–4.9 ms per process, outside both connected
intervals; process wall additionally includes weight loading and shader
setup. The diagnostic graph-workspace counters were 4,220,000 B batch and
18,360,544 B serial, reflecting different prepared graph inventories, not a
product memory peak. These five constructed cases are **not** an empirical
acceptance distribution. Even a high full-acceptance fraction must pay for a
real draft and should be assessed per accepted output token, not per target
batch alone.

Every selected and next F32 logit row was finite and within the predeclared
`abs(batch - serial) <= 0.05 + 0.001*abs(serial)` bound across all 25 pairs;
greedy IDs agreed. The largest selected-row difference was 0.001496 and the
largest next-row difference was 0.001173. An independent untimed trace
compared the first `200 + accepted` valid KV positions and the active
recurrent plane at the commitment point in every case. Zero through three
acceptances were exactly equal at the F16/F32 value level. Full acceptance
had maxima 0.00390625 KV and 0.00174713 recurrent, with zero violations of
the separately declared `0.005 + 0.0005*abs(serial)` bound across 1,253,376
valid KV and 5,050,368 active recurrent elements. One subsequent full-logit
decode agreed in every case, exercising the mask over unused candidate KV
rows. Inactive recurrent parity and unused KV capacity are excluded because
the next graph does not read them. These local bounds do not relax ordinary
generation regression.

Four malformed mode arities were rejected. A local interposer failed the
first timed replay graph in the one-accepted case; the process failed with
zero result files published. The diagnostic resets resident state between
warm and timed rounds. It does not establish a product session's repeated
request behavior or failure recovery.

## Reproduction and next test

Build the smoke with the pinned Align compiler and Metal shim/bundle, and use
the independent tracer from `scripts/trace-qwen35-state.c`:

```sh
LIBRARY_PATH="$SHIM:$GGML_BUNDLE:/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib" \
  ./scripts/alignc build src/runtime_qwen35_target_continuation_smoke.align
scripts/measure-qwen35-target-acceptance \
  --binary ./runtime_qwen35_target_continuation_smoke \
  --geometry "$MODEL_IR" --gguf "$QWEN35_GGUF" \
  --pack "$QWEN35_ALIGNPACK" --backend-path "$GGML_BUNDLE/libggml-metal.so" \
  --bundle-id "$GGML_BUNDLE_ID" --library-path "$SHIM:$GGML_BUNDLE" \
  --fixture eval/fixtures/qwen35-target-continuation-200.json \
  --state-tracer "$STATE_TRACER" --pairs 5 --output "$RESULT_JSON"
```

Next measure a genuinely cheap draft source on representative coding prompts
and the fraction of four-token groups accepted completely, rejected early and
replayed. Test a shorter/adaptive group against fixed four and compare actual
request output, latency, prefill/decode/startup and memory with the current
mixed native Align path and pinned llama.cpp under the same weights and IDs.
Only then choose whether to build a default-off product trial. Another Metal
generation, CUDA, other Qwen geometries and Gemma remain unmeasured.
