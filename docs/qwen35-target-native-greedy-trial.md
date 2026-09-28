# Independent Metal target-row greedy trial (2026-09-28)

## Decision

Keep the explicit `trialnative` path as a default-off developer experiment.
Do not adopt it for product generation. The independent Metal reduction is
correct on the measured Qwen3.5-2B Q4_0 requests, but its connected command
and wait are not repeatably faster than the old readback and Align CPU scan.
Fresh-process whole-request comparisons varied substantially across two
campaigns while other software may have been active. After the user stopped
the heaviest other application, the final-binary rerun found only a small
mixed effect against the old trial, and the same-session bug-fix comparison
lost 7/10 pairs.
The existing three-draft trial and ordinary generation remain available.

Align owns the target graph, lookup, acceptance, rollback, session and token
publication. Pinned ggml still computes the model graph and provides the
shared F32 output allocation. The independent Metal kernel reduces four
rows of logits to four I32 IDs through a checked, borrowed-buffer ABI. There
is no ggml source patch, copied weight/KV arena, Python inference path or
product-default change. The two-dispatch reduction, explicit buffer barrier,
command completion wait and finite/first-index result validation are in
`scripts/native_metal_state_copy.mm` and
`scripts/native_metal_target_greedy_kernel.h`.

## Local actual-weight screen

The capture came from the checked-in Qwen3.5 continuation diagnostic after
the exact 200-token prefix and the pinned four target IDs. Its four complete
F32 rows are 3,973,120 bytes, SHA-256
`0a5b10d4e0ac0899331a613ec6905250874918c22095544bec8ea48c9281eb3f`.
The raw capture stays outside Git because it is derived from model weights.
`runtime_qwen35_target_continuation_smoke --target-continuation` writes this
capture; the input fixture is
[`eval/fixtures/qwen35-target-continuation-200.json`](../eval/fixtures/qwen35-target-continuation-200.json).

The [local receipt](../eval/benchmarks/qwen35-target-native-greedy-local-2026-09-28.json)
comes from `bench-native-metal-target-greedy CAPTURE 4 248320 100 5` on
Apple M1. Both arms used the same preloaded input. The CPU arm copied the
bytes and used a finite first-index scalar scan; the native arm submitted one
command with two dispatches, a buffer barrier and a completion wait. The
benchmark checked all four actual IDs `[220,17,220,18]` on every sample,
plus synthetic ties, nonfinite values and a nonmultiple width before timing.
Scratch was 11,680 bytes. Five alternating pairs of 100 evaluations gave:

| Cost per four rows | Range across five pairs |
| --- | ---: |
| C++ CPU copy and scan | 0.693–0.778 ms |
| Metal submit and completed result | 0.446–0.479 ms |
| Metal GPU command interval | 0.208–0.224 ms |

CPU minus native paired median was +0.289 ms per group. The separate
[Align CPU scan receipt](../eval/benchmarks/qwen35-target-native-greedy-align-cpu-2026-09-28.json)
timed the shipped `runtime_generation.greedy` on the same four rows, with a
nonwinning input changed between repetitions: 0.311–0.321 ms per group in
five runs of 100 repetitions, excluding readback. The C++ CPU control is
therefore not a proxy for the connected Align CPU cost.

## Connected Qwen3.5-2B result

The explicit Align `trialnative` arm uses the same four-row graph and
three-draft policy as the prior `trial` arm. It allocates only a 16-byte
host result buffer in place of the trial's 3,973,120-byte host logits buffer.
The checked shim requires a ready, contiguous F32 output of exact shape,
shared Metal storage and a valid borrowed allocation extent. The helper
reuses the session-owned device/queue and cached view/scratch. If native
prefill state copy is enabled, Align finishes it before reduction. The
ordinary trial keeps its original readback-before-finish order.

The [first request campaign](../eval/benchmarks/qwen35-target-native-greedy-connected-first-2026-09-28.json)
and [second request campaign](../eval/benchmarks/qwen35-target-native-greedy-connected-2026-09-28.json)
each contain five alternating fresh-process pairs for each coding prompt
against unchanged normal Align, old three-draft Align and pinned llama.cpp
`bb4caa7540188872173c44d161602d9271386413`. The same GGUF, pack,
Model IR, F16 KV policy, prompt IDs, exact output IDs/counts and execution
options were used. Native state and convolution copy were enabled, native
SwiGLU disabled. Each arm was primed before recording; loaded generation,
prefill, serial decode, target compute, result boundary and fresh-process
wall/startup were recorded separately. Positive paired values favor native.
The two campaigns used diagnostic binary hashes recorded in their receipts;
the second preserves the old trial's state-copy wait ordering when that
optional mode is enabled. It was disabled in these measurements.

| Prompt/output | First: old trial − native generation | Second: old trial − native generation | First: llama.cpp − native generation | Second: llama.cpp − native generation |
| --- | ---: | ---: | ---: | ---: |
| Function 61/96 | -0.5 ms; 2/5 | +150.6 ms; 4/5 | +163.0 ms; 5/5 | +554.7 ms; 5/5 |
| Bug fix 99/75 | +12.2 ms; 4/5 | +47.6 ms; 4/5 | +635.0 ms; 5/5 | +828.0 ms; 5/5 |
| Tests 72/96 | +18.9 ms; 4/5 | +254.7 ms; 4/5 | +178.5 ms; 5/5 | -196.0 ms; 1/5 |

The first campaign's normal Align minus native generation medians were
-7.8, +494.9 and -49.1 ms for function, bug fix and tests (1/5, 5/5 and
0/5 wins). The second were +171.2, +685.0 and +531.1 ms (3/5, 5/5 and
3/5 wins). Fresh-process wall comparisons against llama.cpp were not
consistently favorable: first campaign 0/5, 3/5, 0/5 native wins; second
1/5, 5/5, 0/5. The second campaign's tests condition slowed from about
2.7-second to 3–5-second generations across all arms. The user later
reported that other software may have run during this period. Treat the second
campaign and the same-session comparison as interference-affected evidence,
not a clean estimate of the candidate's effect. These results do not
establish a repeatable request win over old trial or llama.cpp.

On the first bug-fix campaign, median old F32 readback was 11.37 ms over
11 groups; native reduction/command/wait was 11.00 ms. The latter includes
greedy selection; the former excludes Align's CPU scan. On the second, the
respective costs were 6.34 and 8.68 ms. Prefill and target compute were
similar within each campaign; serial decode varied with host conditions.

The [interference-affected same-session bug-fix receipt](../eval/benchmarks/qwen35-target-native-greedy-session-bugfix-2026-09-28.json)
contains one warmup request per arm followed by ten pairs in alternating
order on a reused session, with all 22 outputs matching the pinned stream.
Its old-trial minus native generation median was **-151.7 ms**, with native
winning 4/10 pairs. Several pairs differed by hundreds of milliseconds or
more, so that median is not an inference about steady-state speed. Over the ten measured requests per
arm, old F32 readback had a 4.79 ms median across 11 groups, versus 9.64 ms
for the native command and wait. The separately measured Align scan adds
about 0.31 ms per four-row group to the old path; adding it to this receipt
would be a cross-measurement estimate, not an observed paired boundary.
The extra Metal command, dispatch and completion boundary is a plausible
cause of the connected cost, despite the 4 MB CPU readback eliminated.

## Correctness, limits and next hypothesis

The [final correctness receipt](../eval/benchmarks/qwen35-target-native-greedy-correctness-2026-09-28.json)
uses the final diagnostic binary. It checks first-group acceptance after
0/1/2/3 matching drafts, with three repeated native and normal requests
per case; short outputs, a draft containing EOG and an empty-prompt refusal
also passed. All successful generated IDs matched the pinned reference.
The earlier four-row graph qualification established predeclared complete
logit and valid active-state numerical bounds for the unchanged graph.
Stepwise state comparison and injected native target submit/completion
failures have not been run on this connected path; they remain required
before product adoption. Other Metal generations, CUDA, other Qwen sizes
and Gemma are unmeasured.

## Lower-load final-binary rerun

After the heaviest other software stopped, the
[fresh-process receipt](../eval/benchmarks/qwen35-target-native-greedy-connected-quieter-2026-09-28.json)
used the final diagnostic SHA-256
`394b3a9fd0339754574beba5f1303c55db088985eaca05d6379b9d6d9256a555`
and the same GGUF, options, prompt IDs, generated IDs and five-pair alternating
protocol. The [reused-session receipt](../eval/benchmarks/qwen35-target-native-greedy-session-bugfix-quieter-2026-09-28.json)
used that exact binary and shim with one warmup per arm and ten alternating
pairs. All outputs matched the pinned stream. This is a lower-load rerun;
the host was not reserved exclusively, and iTerm/WindowServer still had
background CPU activity.

| Prompt/output | Normal Align − native generation | Old trial − native generation | llama.cpp − native generation | llama.cpp − native fresh-process wall |
| --- | ---: | ---: | ---: | ---: |
| Function 61/96 | -7.8 ms; 1/5 | +0.3 ms; 3/5 | +226.9 ms; 5/5 | -249.8 ms; 0/5 |
| Bug fix 99/75 | +466.1 ms; 5/5 | +1.5 ms; 4/5 | +643.2 ms; 5/5 | +172.8 ms; 5/5 |
| Tests 72/96 | -46.8 ms; 1/5 | -3.1 ms; 1/5 | +137.3 ms; 5/5 | -450.4 ms; 0/5 |

These are loaded-generation paired medians except the last wall column.
The native route's large bug-fix gain against normal Align belongs to the
preexisting target lookup path; the new argmax changes that trial by only
about 1.5 ms in these fresh processes. At 11 bug-fix groups, old F32
readback cost 4.69 ms median and native reduction with command completion
cost 6.38 ms; old CPU greedy scans are additional. Target compute medians
were 501.17 and 500.49 ms, prefill 236.70 and 235.83 ms, and serial decode
855.64 and 857.22 ms for old and native respectively. Startup/load medians
were 982.13 and 949.45 ms in that comparison; the separate process wall
timer includes loading and is not a cached-session result.

The lower-load same-session bug-fix run gave old-trial minus native generation
**-7.8 ms** paired median, with native winning 3/10 pairs. Old readback
was 4.69 ms median across 11 groups; native command and wait was 9.67 ms.
The five fresh-process pairs and ten reused-session pairs therefore disagree
on the sign of a few-millisecond whole-request effect, while neither shows
a robust native improvement. This closes the current adoption question:
retain only the explicit experiment. A future combined state-copy/greedy
command or larger fused target execution unit needs its own local and
connected trial.

The reusable part is the shape/width-driven finite first-index reduction,
checked shared-buffer borrowing and Align-owned selection/rollback boundary.
Qwen/Gemma model semantics and graph construction remain architecture
specific. A future attempt should reduce a larger execution unit or share
the already necessary state-copy command/queue boundary, then measure the
same connected costs. A faster isolated scan alone is not enough to justify
another per-group completed Metal command.
