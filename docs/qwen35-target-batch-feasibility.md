# Qwen3.5 target-batch feasibility screen (2026-09-28)

## Decision

Continue a bounded speculative-verification experiment; do not claim or
enable a speculative generation speedup yet. Real-model prefill and actual
Q6_K output-head screens show substantial weight reuse across token columns,
but neither measures a draft model, all target logits in the complete graph,
acceptance, DeltaNet/KV rollback or combined target-plus-draft request time.
The production generation loop remains unchanged and ggml is its current
matrix executor. The next consumer must keep model semantics, draft choice,
state transaction and generation scheduling in Align.

## Full-model shape-cost comparison

The same Apple M1 16 GiB, Qwen3.5-2B Q4_0 GGUF, saved Align binary, pack,
Model IR and pinned ggml bundle as the
[current mixed-native campaign](qwen35-current-native-mixed-bottleneck.md)
were used. The GGUF SHA-256 is
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
All arms use mixed native decode state copying, a 128-token prefill chunk,
final-chunk-only logits and normal CPU greedy. The prefill arm adds `hello`
text to a user message until the complete templated prompt is `200+K` tokens
and asks for one output; the decode arm uses the 200-token prompt and asks
for `K+1` outputs. The common token prefix is only 191 tokens in all three
cases: appending user text moves the chat-template suffix. Therefore the
long arm is **not** a continuation of the base model state. Paired deltas
compare shape-dependent work on related prompts, not the cost of verifying
the decode arm's exact next `K` tokens. The independent
[`measure-qwen35-target-batch-bound`](../scripts/measure-qwen35-target-batch-bound)
caller times the third of three requests in each worker, rotates the three
arm orders over five pairs, and checks every actual token count. The
[receipt](../eval/benchmarks/qwen35-target-batch-bound-2026-09-28.json)
contains prompt IDs and all paired samples.

| Length difference `K` | Long-prefill minus 200/1, paired median | Serial decode minus 200/1, paired median | Decode minus long-prefill |
| ---: | ---: | ---: | ---: |
| 4 | 2.562 ms | 121.676 ms | 119.114 ms |
| 8 | 2.400 ms | 230.490 ms | 227.800 ms |
| 16 | 6.684 ms | 438.319 ms | 430.652 ms |

These values are a **shape-cost screen**, not a target validator
or a mathematical lower bound for a true continuation:
the current prefill graph emits only its final token's logits. Verification
needs the appropriate logits for each draft token; it may also need an
additional final token, depending on the acceptance algorithm. The prefill
arm has no draft cost or rejected-prefix replay. Its final recurrent state
is for all appended tokens; it does not demonstrate safe partial acceptance.
The non-prefix prompts and different output lengths also mean the arms are
not a quality-equivalent generation comparison. The small paired prefill
deltas reflect this workload and cache state, not a guarantee for an actual
draft continuation, other input lengths or devices.

## Actual-weight Q6_K head screen

The independent
[`bench-qwen35-q6-target-batch.mm`](../scripts/bench-qwen35-q6-target-batch.mm)
probe uses the captured 417,177,600-byte Q6_K output matrix and three
captured F32 hidden activations. It runs ggml Metal on the same weights
with `K` F32 columns at once versus `K` serial one-column projections.
Input columns rotate through the three real activations. Before timing, it
compares every complete batched logit row to its one-column reference under
the declared bound `abs(diff) <= 0.05 + 0.001*abs(reference)` and checks the
greedy token. It then performs 12 warmups and five alternating timed pairs.
The [raw JSON lines](../eval/benchmarks/qwen35-q6-target-batch-2026-09-28.jsonl)
retain every sample.

| Columns `K` | Serial median | Batched median | Paired serial minus batch | Batched wins | Largest absolute logit difference |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 29.098 ms | 10.722 ms | 18.388 ms | 5/5 | 0.000003815 |
| 8 | 58.376 ms | 20.974 ms | 37.263 ms | 5/5 | 0.000003815 |
| 16 | 117.108 ms | 18.980 ms | 98.193 ms | 5/5 | 0.003421128 |

The 16-column backend selects a different matrix path; its lower median
than 8 columns is measured, not an assumed monotonic scaling law. This is
head-only compute/submission on captured activations, not the complete
target pass. The numerical bound is for this screen and does not relax the
existing exact regression path. Other Qwen sizes, Q6_K layouts, Gemma and
CUDA have not been tested.

## Reproduction and next acceptance gate

The full-model caller accepts explicit paths in the same config format as
`measure-native-swiglu`; the Q6_K probe uses the developer capture directory
whose `geometry.txt` declares `q6-capture-v1 2048 248320 14`. Neither
capture nor model weights are committed:

```sh
scripts/measure-qwen35-target-batch-bound \
  --config "$REAL_MODEL_CONFIG" --pairs 5 --output "$BOUND_JSON"
clang++ -O3 -std=c++17 -Wall -Wextra -Werror -fobjc-arc \
  -framework Foundation -framework Metal \
  -I "$GGML_SOURCE/include" -L "$GGML_BUNDLE" \
  -Wl,-rpath,"$GGML_BUNDLE" scripts/bench-qwen35-q6-target-batch.mm \
  -lggml -lggml-base -o "$Q6_BATCH_PROBE"
DYLD_LIBRARY_PATH="$GGML_BUNDLE" "$Q6_BATCH_PROBE" \
  "$GGML_BUNDLE/libggml-metal.so" "$Q6_CAPTURE_DIR"
```

The next test is a default-off Align-owned multi-token target graph that
produces and compares each required logit row and records all state writes.
It must prove that accepted prefixes publish the same DeltaNet and attention
state as ordinary decode; rejection must replay or restore state without
publishing a speculative suffix. Then compare a real draft source's
acceptance lengths, combined time and extra memory with ordinary generation
on 64/16, 200/32 and 330/64. A batch-only timing cannot clear this gate.
