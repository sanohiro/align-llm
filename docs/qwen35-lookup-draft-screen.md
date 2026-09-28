# Qwen3.5 coding prompt lookup and connected target cost (2026-09-28)

## Decision

Continue with a default-off, request-level trial of **three** lookup drafts plus
one already selected token. Do not enable prompt lookup for every coding
request. The real bug-fix continuation had enough complete groups to justify
that trial; the other two continuations did not. A one-mismatch backoff is a
testable selector, not a qualified shipping rule. There is no measured complete
request speedup here, and the four-draft/five-row version has no real-model
connected timing.

## Implementation and fixture

`runtime_generation.prompt_lookup_draft` scans the token history backward for
the most recent complete suffix match and appends exactly `k` following IDs.
The developer-only Align lookup entry tries a three-token match, then a
two-token match. It has no model-name condition, extra weight set, GPU copy or
cross-request state. The existing production generator does not call it yet.
The independent measurement script checks every Align draft against its own
backward-scan oracle. Python selects and reduces diagnostic cases; Align owns
the actual real-model candidate comparison, state transaction and graph work.

The [fixture](../eval/fixtures/qwen35-lookup-draft-coding.json) records one
function implementation, one bug fix and one test-writing prompt, their GGUF
token IDs and up to 96 greedy IDs from pinned llama.cpp
`bb4caa7540188872173c44d161602d9271386413`. The bug-fix stream ends at
its first model EOG ID after 75 generated tokens. The other streams contain
96 tokens, with the function's EOG at its last position. A group is attempted
only when the recorded continuation contains its draft positions and the
following target choice. The already selected current token is the first of
the four verification inputs; the three lookup IDs are the drafts. The
four-draft counts below are an offline screen for the planned five-row graph.

| Task | Three-draft groups: accepted 0/1/2/3 | No-draft steps | Four-draft groups: accepted 0/1/2/3/4 |
| --- | ---: | ---: | ---: |
| Function | 11 / 3 / 1 / 3 | 61 | 9 / 2 / 1 / 1 / 2 |
| Bug fix | 2 / 0 / 2 / 12 | 16 | 1 / 1 / 1 / 0 / 10 |
| Tests | 6 / 4 / 5 / 1 | 60 | 5 / 5 / 4 / 0 / 1 |

These counts use the recorded llama.cpp greedy stream. They are not an Align
product acceptance rate: a request may differ after a near-tie, and no
continuous speculative session was run. The Align lookup itself took median
0.50, 0.58 and 0.54 microseconds per visited history for the three-draft
screen, respectively; observed maxima were 0.67, 0.79 and 0.83 microseconds.
This timer surrounds lookup and local builder allocation inside one Align
process; it excludes session integration and graph work. The longest tested
history was below 200 IDs, so this does not bound the 2,175-ID policy maximum.

## Actual GGUF/GPU verification

For each task, the earliest complete three-draft group and the earliest
zero-draft-match group were run on Apple M1 using the same Qwen3.5-2B Q4_0
GGUF, pack, Model IR, Metal bundle and real recorded prefix. Five alternating
process pairs compared four-row target verification plus acceptance/replay
against serial one-token graphs. The connected interval starts after prefix
work and includes graph switching, synchronized target compute/readback,
accepted-state replay and one equal-progress next-token step. Shader startup,
model load and prefix work are separately outside that interval. Each pair
compared the complete selected and next F32 logit rows; an independent trace
compared valid KV and active recurrent state after commitment.

| Task | Accepted lookup drafts | Serial median | Four-row median | Paired serial − four-row median | Four-row wins |
| --- | ---: | ---: | ---: | ---: | ---: |
| Function | 0 | 58.5 ms | 110.4 ms | −52.1 ms | 0/5 |
| Function | 3 | 144.6 ms | 80.8 ms | +63.5 ms | 5/5 |
| Bug fix | 0 | 57.5 ms | 109.7 ms | −52.3 ms | 0/5 |
| Bug fix | 3 | 144.5 ms | 82.5 ms | +62.3 ms | 5/5 |
| Tests | 0 | 58.1 ms | 109.3 ms | −52.0 ms | 0/5 |
| Tests | 3 | 143.5 ms | 81.6 ms | +62.0 ms | 5/5 |

All arm medians, paired deltas and correctness values are from the final
[raw receipt](../eval/benchmarks/qwen35-lookup-draft-2026-09-28.json). The
paired difference is reduced pair by pair; it need not equal the difference
of separately rounded arm medians.

All 60 measured selected/next F32 row comparisons were finite and met the
bound fixed by the acceptance screen; each selected row chose the recorded
greedy token, and both arms agreed on each next-row greedy token:
`abs(batch - serial) <= 0.05 + 0.001*abs(serial)`. Their maximum absolute
difference was 0.001116. For all six independent committed-state traces,
valid KV and active recurrent values met
`0.005 + 0.0005*abs(serial)` with zero violations. Zero-draft-match cases
were value-identical in active state; full-acceptance cases differed by at
most 0.00390625 in valid KV and 0.002306 in active recurrent state. The
ordinary Qwen3.5 product and pinned llama.cpp request baselines were not
part of this local interval comparison.

## Interpretation and next test

The 200-token constructed screen and these six real coding prefixes show
roughly symmetric full-match savings and mismatch losses. The bug-fix stream
began with ten complete three-draft groups before its first mismatch, while
the function stream had one complete group and the test stream had no
complete group before their first mismatch. This motivates a bounded
one-mismatch backoff in a default-off request trial. The three prompts are
too few to establish a general selector. The next trial must run the actual
Align generation loop with the lookup, measured draft cost, repeated graph
reuse, EOG/max-token truncation, state rollback and complete-request timing
against the current mixed-native Align path and pinned llama.cpp. It must
record accepted positions and show where the trial gains or loses. If the
backoff still costs more than it saves, test a smaller/adaptive group or
withdraw prompt lookup for that workload.

The original [Prompt Lookup Decoding implementation](https://github.com/apoorvumang/prompt-lookup-decoding)
uses prompt matching as a model-free draft source. [TurboSpec](https://arxiv.org/abs/2406.14066)
reports that speculative benefits can degrade when misses and overhead are
ignored, and adjusts speculation from runtime feedback. Those sources
motivate testing an adaptive selector; neither is evidence that this M1
implementation or these three prompts gain complete-request speed.

The lookup function can be reused for another Qwen size or Gemma after its
token history is available. The verification graph and transaction are tied
to Qwen3.5's hybrid attention and recurrent state, so other model semantics,
quantization, shape and backend need their own graph/state qualification.
Pinned ggml remains the matrix executor in this screen; the lookup, graph
selection and acceptance/replay are Align-owned. No ggml source patch is used.
