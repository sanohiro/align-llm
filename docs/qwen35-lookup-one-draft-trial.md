# Qwen3.5 one-draft lookup trial (2026-09-28)

## Decision

Keep the explicit, default-off one-draft path as a bounded diagnostic for
future target-group selection experiments. Do **not** replace the three-draft
path or enable either path for product requests. One draft improves the
repeated bug-fix task against normal Align, but costs more than three drafts;
it does not remove the short-hit regressions. This is a real-model negative
result for a fixed one-draft policy, not evidence against target verification
or another group-selection rule.

Align owns the lookup, two-row graph selection, acceptance, rollback and
generation loop. The pinned ggml bundle executes model matrices. No ggml
source patch, second weight/KV arena or Python inference path was added.
The ordinary and three-draft entrypoints remain available for comparison.

## Correctness and local two-row result

The tested model is Qwen3.5-2B Q4_0 with the identical GGUF, alignpack and
Model IR on Apple M1 Metal. Native state/convolution copy remained enabled
and native SwiGLU remained disabled in every Align arm. The new
[two-row fixture](../eval/fixtures/qwen35-target-continuation-two-row-200.json)
uses the exact 200-token prefix and first two continuation IDs from the
previously pinned llama.cpp stream. Five alternating actual-weight two-row
versus serial pairs passed complete finite F32 logits under the predeclared
`0.05 + 0.001 * abs(serial)` bound. Both rows selected `[220, 17]` in every
pair. Maximum absolute differences were 0.001009 and 0.001114. The independent
untimed trace of valid KV and active recurrent state passed the predeclared
`0.005 + 0.0005 * abs(serial)` bound, with zero violations across 1,241,088
KV and 5,050,368 recurrent elements. Its maximum absolute differences were
0.003906 and 0.001733. The [raw local receipt](../eval/benchmarks/qwen35-target-continuation-two-row-2026-09-28.json)
contains each pair, input and binary hashes, workspace and trace identity.

The two-row target saved 11.274 ms paired median against two serial steps,
including graph switching and F32 readback, in 5/5 local pairs. Target graph
compute was about 41.4 ms median; the prior separate four-row screen measured
about 46.0 ms for a four-row target at the same prefix. Those separate
campaigns are not a direct paired two-versus-four comparison. The reported
two-row graph workspace was 2,214,976 bytes; the trial's request-owned F32
staging buffer is 1,986,560 bytes. Neither figure is a measured process peak.

The [repeated-request receipt](../eval/benchmarks/qwen35-lookup-one-draft-correctness-2026-09-28.json)
checks first-group acceptance and rejection, three requests per arm, short
output, EOG draft suppression and invalid empty prompt. All successful IDs
matched the pinned greedy stream. A one-pair regression of the prior four-row
continuation owner also passed complete logits and active state. The connected
trial's state has not been traced after every generation step, and a forced
target failure has not been injected; those remain requirements before
product admission.

## Complete-request comparison

The [raw request receipt](../eval/benchmarks/qwen35-lookup-one-draft-2026-09-28.json)
records five alternating pairs per case for one-draft against each of normal
Align, the existing three-draft trial and unmodified pinned llama.cpp
`bb4caa7540188872173c44d161602d9271386413`. Every arm used the same
GGUF, prompt IDs, greedy output IDs/counts and F16 KV policy. Each comparison
had excluded warmups. The separate control campaigns must not be treated as
one simultaneous three-arm sample. Positive paired deltas favor one-draft.

| Prompt / output | Normal Align − one-draft generation | Three-draft − one-draft generation | Pinned llama.cpp − one-draft generation | Pinned llama.cpp − one-draft fresh-process wall |
| --- | ---: | ---: | ---: | ---: |
| Function 61 / 96 | -81.1 ms; 1/5 wins | -23.5 ms; 2/5 | +191.5 ms; 5/5 | -245.0 ms; 0/5 |
| Bug fix 99 / 75 | +118.7 ms; 5/5 | -407.1 ms; 0/5 | +287.6 ms; 5/5 | -165.1 ms; 0/5 |
| Tests 72 / 96 | -42.9 ms; 2/5 | -0.2 ms; 2/5 | +166.9 ms; 5/5 | -273.8 ms; 0/5 |

The pinned-reference comparison uses a loaded-generation timer as well as
the outer fresh-process timer. One-draft won all 15 loaded-generation pairs
against the pinned reference, but lost all 15 fresh-process wall pairs. The
reference was built from the named unmodified revision with Metal GPU layers,
flash attention, context/batch 512 and four CPU threads. The receipt hashes
the executables, GGUF, pack, fixture and options.

One-draft phase medians from the normal-Align comparison, in milliseconds:

| Case | Prefill | Ordinary serial decode | Two-row graph build | Two-row compute | F32 readback | Full / rejected groups |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Function | 144.5 | 2481.7 | 12.6 | 131.6 | 0.6 | 2 / 1 |
| Bug fix | 243.3 | 927.0 | 32.3 | 914.1 | 4.3 | 20 / 1 |
| Tests | 188.5 | 2440.6 | 11.5 | 85.8 | 0.5 | 1 / 1 |

The repeated bug-fix passage needs 20 successful two-row groups, compared
with ten four-row groups in the earlier three-draft trial. The smaller graph
reduces each target's local work, but doubles the number of target graph
executions there. On the short-hit inputs, a rejected group still pays for a
target computation and serial replay. These connected counts and times explain
why the fixed one-draft policy does not improve the observed workload mix;
they do not attribute all latency to an individual Metal shader.

## Reproduction and next hypothesis

Build `src/runtime_qwen35_lookup_trial_smoke.align` and
`src/runtime_qwen35_target_continuation_smoke.align` using `./scripts/alignc`
with the pinned shim on `LIBRARY_PATH`. Run
`scripts/measure-qwen35-lookup-one-draft`,
`scripts/measure-qwen35-target-continuation` with the two-row fixture, and
`python3 scripts/verify-qwen35-lookup-continuous --trial-arm trial1` with the
arguments shown by `--help`. The receipts identify the exact local artifacts
and retain adverse samples. Weights and generated binaries remain outside Git.

The next bounded GPU experiment should select group size from observable
lookup evidence and target cost before submission, then measure the same
three requests. A useful rule must avoid paying for weak first hits without
losing the ten successful three-draft groups on the bug-fix case. Any rule
needs connected state/failure checks and whole-request comparison; the local
two-row gain alone is insufficient. Other Metal generations, CUDA, Qwen
sizes and Gemma remain unmeasured. The Align lookup and bounded
accept/discard control can be reused, while model-specific attention,
recurrent state, activation and graph construction require their own
qualification.
