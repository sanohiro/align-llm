# Qwen3.5 full-model four-row target graph screen (2026-09-28)

## Decision

Continue the target-verification experiment. Do not enable speculative
generation from this result. A reversible Align-owned diagnostic graph now
computes all four target logit rows and completes recurrent/KV writes. It beat
four serial complete-model steps in five alternating local comparisons on
Apple M1, with bounded complete logits and active state differences. It has
not processed a continuation after a real prompt, handled partial acceptance
or rejection, paid for a draft, or improved a complete generation request.

## Scope and comparison

`runtime_qwen35_model.build_tokens_all_logits` retains every final hidden row
and projects the existing tied Q6_K output weights over all rows. Align owns
the graph, shape admission, state binding and execution. The same smoke binary
provides `--target-rows OUTPUT` and `--serial-target-rows OUT0..OUT3`; ordinary
generation and its final-row graph remain unchanged. Pinned ggml still runs
the matrix kernels and schedules the graph. No ggml source patch, new weight
copy or Python inference path was introduced.

Both arms use the same real Qwen3.5-2B Q4_0 GGUF, alignpack, Model IR, pinned
Metal bundle and token IDs `[0, 23066, 0, 0]` from an empty prefix. The GGUF
SHA-256 is `cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`;
the [receipt](../eval/benchmarks/qwen35-target-all-rows-2026-09-28.json)
also pins the diagnostic binary, pack, Model IR, backend and state tracer
digests. Each process warms its exact graph path, zeros resident state, then
times synchronized graph compute and output readback separately. The serial
arm replays four one-token graph variants; the batch arm computes one four-row
graph. Five pairs alternate process order. Process wall includes model load,
graph preparation and shader compilation and is not a clean startup measure.

| Metric, five-pair median | Four serial steps | One four-row graph | Paired serial minus batch |
| --- | ---: | ---: | ---: |
| Synchronized complete-model compute | 115.456 ms | 44.414 ms | +71.086 ms; batch wins 5/5 |
| Complete F32 logits readback | 0.396 ms | 0.680 ms | −0.251 ms |
| Whole diagnostic process | 1237.470 ms | 1053.489 ms | +133.741 ms; includes load/setup |
| Reported graph workspace | 2,022,656 bytes | 4,010,112 bytes | +1,987,456 bytes |

The four-row logits allocation is 3,973,120 bytes; each serial row is
993,280 bytes. Graph workspace is the shim's allocated-workspace counter,
not a process memory peak. The batch's extra readback and workspace are
included in the assessment. The compute timing includes backend submission
and required synchronization, so it is a connected graph result rather than
an isolated kernel interval. The process samples contain other startup work
and show more variance; they cannot establish a load improvement. Pinned
llama.cpp and the normal Align worker have no corresponding target-verifier
request in this experiment, so no whole-request comparison is claimed.

All four complete F32 rows were finite and met the predeclared
`abs(batch - serial) <= 0.05 + 0.001 * abs(serial)` bound in every pair.
The largest absolute differences by row were 0.006171, 0.003490, 0.003085
and 0.002620. Greedy IDs `[729, 0, 198, 198]` matched in every pair. These
are local arithmetic bounds; ordinary exact generation regression remains.

An independent, untimed state trace read every resident plane after the timed
replay. Whole-plane hashes differ because the four-token prefill writes the
opposite recurrent parity from four serial steps and because unused KV tails
are outside the valid prefix. The diagnostic therefore compared only the
first four positions of the 12 F16 KV planes and the active parity of the 36
F32 recurrent planes. All 24,576 valid KV elements and 5,050,368 active
recurrent elements were finite and met the separately predeclared
`0.005 + 0.0005 * abs(serial)` bound, with maxima 0.0078125 and 0.0010882
respectively. The trace was run after timing, never injected into a timed arm.
It does not verify a partially accepted state or exact byte identity.

## Reproduction

Build the smoke with the repository's pinned Align compiler and the pinned
ggml shim/backend bundle, then build the optional independent state tracer:

```sh
LIBRARY_PATH="$SHIM:$GGML_BUNDLE:/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib" \
  ./scripts/alignc build src/runtime_qwen35_load_smoke.align
clang -O2 -Wall -Wextra -Werror -Wno-deprecated-declarations \
  -dynamiclib -undefined dynamic_lookup -I "$GGML_SOURCE/ggml/include" \
  scripts/trace-qwen35-state.c -o "$STATE_TRACER"
scripts/measure-qwen35-target-rows \
  --binary ./runtime_qwen35_load_smoke --geometry "$MODEL_IR" \
  --gguf "$QWEN35_GGUF" --pack "$QWEN35_ALIGNPACK" \
  --backend-path "$GGML_BUNDLE/libggml-metal.so" \
  --bundle-id "$GGML_BUNDLE_ID" \
  --library-path "$SHIM:$GGML_BUNDLE" --state-tracer "$STATE_TRACER" \
  --pairs 5 --output "$RESULT_JSON"
```

The binary and tracer are local build artifacts; weights and complete state
dumps stay outside Git. The checked-in script rejects missing output extents,
nonfinite values, numeric/greedy mismatches and missing state planes before
writing its receipt. After review, malformed target-mode arities were
confirmed to fail without output. A separate fault interposer forced failure
on the third timed serial replay graph; the process failed with zero of four
output files published. The five-pair campaign above was rerun after that
repair.

## Next discriminating test

Run the same all-row graph after an **identical** real prompt prefix, and
compare its target logits and active state to sequential continuation. Then
implement a bounded Align-owned acceptance transaction: full acceptance,
partial acceptance, rejection replay, failure cleanup and repeated requests.
Only after a cheap draft source and accepted-token rate are measured can the
combined request be compared with ordinary Align and pinned llama.cpp. A
single M1 four-row result says nothing about another Metal generation, CUDA,
another Qwen shape or Gemma semantics.
