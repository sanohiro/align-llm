# C4-REPAIR-MEASURED: one bounded model repair attempt in the provider-backed measurement path

Status: **implemented; measurement recorded in section 10.** This document remains the
authoritative plan. Section 10 records the ledger-to-diff mapping, the deviations the
implementation discovered, and the measured gate result. This document is the authoritative plan; the proportional design gate in `CLAUDE.md` triggered on a
persisted format change (`PROMPT_TASK_ROW` grows per-attempt identity), on a new frozen corpus
scope, and on a coordinated invariant across the evaluator, the Align scorer, and the corpus
assets. Branch `agent/c4-repair-measured`, based on `main` `3df063b`.

`docs/specs/c6-prompt-context-optimizer.md` remains the source of truth for every artifact this
capability reuses unchanged — the scope, the acceptance policy, the context policy, the adapter
contract, the generation child, the gate validator, and the frozen `eval/prompt/canonical-v1/`
assets. This document owns only what C4-REPAIR-MEASURED adds: the second attempt, the repair prompt,
the `PROMPT_TASK_ROW` schema-2 shape, the new corpus freeze, the provider topology, and the C4 gate.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

The C4 roadmap gate (`docs/specs/roadmap.md`, "C4: Verification Loop") reads:

```text
少なくとも一部の固定タスクで、初回失敗から自動修正してtest passまで到達すること。
```

At least some fixed tasks must reach a passing test by automatic repair from a first failure. Today
that gate is met only by a **scripted** repair: `src/repair.align` drives a
`fn (str, str, i64) -> bool` provider, `src/verification_loop.align` orders the stages, and
`make verify-loop-smoke` proves the loop with a checked-in deterministic repair patch.
`docs/align-development.md` states the boundary plainly: "The repair patch is deliberately an input
boundary, not a model implementation."

Meanwhile the C6-MEASURED wave built the only provider-backed measurement path this repository has,
and deliberately pinned it to a single shot. `docs/specs/c6-prompt-context-optimizer.md` §9
requires the gate corpus to

```text
- set each initial C6 gate task's `maximum_repair_loops` to zero and make exactly one bound provider
  generation call per sample, so the independently verified `GenerationRequestIdentity` covers the
  complete model-request path; deterministic scorer fixtures still exercise nonzero repair counts;
```

So the repository has a real model that produces patches and never repairs them, and a real repair
loop that has never been driven by a model. **This capability joins the two, once, under
measurement.** After a first-attempt validation `FAIL`, the run feeds its *own* diagnostics — the
validation exit code, the diagnostic summary naming the files it edited, and the redacted validation
stdout and stderr — into a second `prompt generate` call, validates the result again, and
records per-attempt identity and timing. `generation_to_passing_patch_ns` then means what
`c6-prompt-context-optimizer.md` §5.2 already contracts it to mean and has never yet had to:

> It includes all provider latency, patch decoding/application, build and test verification,
> diagnostics used for repair, subsequent repair provider calls, and re-verification.

The distinction that matters: the CANDIDATE variant's context policy already sets
`include_diagnostics: true`, but the diagnostics it renders are **canned** text checked into
`eval/tasks/prompt-v1/<task>/context-sources.json`. The repair attempt renders the diagnostics the
run itself just produced. That is the difference between a prompt that talks about failure and a
loop that reacts to one.

### 1.2 In scope

1. One bounded repair attempt per (task, sample, variant), driven by the evaluator, after a
   first-attempt validation `FAIL`. The repair prompt carries the failing attempt's **exit code,
   diagnostic summary, and redacted validation stdout and stderr**. It does **not** carry the
   failing edit set; section 2.7 records the constraint that removes it and section 5.4 its resume
   condition.
2. `PROMPT_TASK_ROW` and `PROMPT_EVALUATION_RESULT` at `schema_version: 2`, carrying an ordered
   per-attempt list with each attempt's own generation-request identity, seed attestation, edit set,
   diagnostics, status, and timing. Schema 1 stays decodable, byte-for-byte, forever.
3. A repair-prompt content contract: a sealed template, fixed section order, exact truncation
   bounds, and a re-derivation rule that makes the repair prompt a pure function of persisted
   evidence.
4. A new frozen corpus scope, `eval/prompt/canonical-v1r/`, over the same three tasks and the same
   fixtures, differing from `canonical-v1` only in `maximum_repair_loops`, the repair template, and
   the observed provider service revision.
5. The provider topology for this host: validation in `bwrap` inside a Linux container, generation
   against the host `llama-server`, and the evidence that records which server actually answered.
6. One measured gate run and its checked-in evidence — including a measured negative.

### 1.3 Non-goals

1. **No provider module changes.** `src/provider_llama.align`, `src/provider_openai.align`, and
   `src/model.align` are untouched. The repair attempt is a second ordinary generation call.
2. **No change to `scripts/prompt-measurement-adapter.py` or `eval/runners/run-coding-task.py`.**
   Both are byte-frozen `FILE_SET` corpus members of `canonical-v1`; changing either would break
   `make prompt-gate-check` against the merged C6 evidence. Section 3.1 is built on this constraint.
3. **No mutation of `eval/prompt/canonical-v1/`, `eval/prompt/gate/`, or
   `eval/tasks/prompt-v1/*.json`.** `c6-prompt-context-optimizer.md` §4.4 forbids it: "C6g1 first
   finalizes, reviews, and freezes the canonical corpus… C6g2 must not mutate those scope assets
   after measuring against them."
4. **No second repair.** The cap is one repair attempt (two attempts total). Section 5.4 records why
   and what would reopen it.
5. **No corpus expansion.** The three existing tasks are the corpus. A larger corpus is a later
   Track A capability; no `C9` label exists in this repository today and this document does not
   create one.
6. **No prompt-quality claim.** This capability does not claim the CANDIDATE prompt is better, does
   not claim repair makes anything faster, and does not accept or roll back an activation.
7. **No change to `src/repair.align` or `src/verification_loop.align`.** The Align repair loop keeps
   its scripted-provider boundary. This capability measures repair on the C6 evaluation path, which
   is a different process topology. Section 5.4 records the convergence question.
8. **No failure-memory feedback.** C5 memory events are not written or read across attempts.

### 1.4 Gate statement

**The C4 gate is met when, on the three-task corpus × two variants × two paired samples at
`temperature_micros: 0` and `seed_mode: PAIRED_FIXED`, at least one (task, variant) pair records
attempt 1 `FAIL` and attempt 2 `PASS` in *both* of its paired samples.**

Formally, the corpus aggregate gains `repair_recovery_paired_count`, defined as the number of
(task, variant) pairs for which, for every `sample_index` in `1..sample_count`, the row satisfies

```text
attempts[0].attempt_kind == INITIAL   and attempts[0].status == FAIL
attempts[1].attempt_kind == REPAIR    and attempts[1].status == PASS
```

The gate is `MET` when `repair_recovery_paired_count >= 1` and `NOT_MET` otherwise.

**A `NOT_MET` result is a delivered result, not a failure to deliver.** The evidence document, the
per-attempt repair prompts' digests, the realized diagnostics, and the analysis of why the model did
not recover are checked in exactly as a `MET` run would be. Section 5.3 fixes what is reported in
each case. Nothing about the mechanism is conditional on the model succeeding; a run in which every
repair attempt is made, is measured, and fails proves the loop and refutes the model.

**What this gate is not.** It is not the C6 acceptance decision. The evaluation still computes
`status` (`IMPROVED` / `REGRESSED` / …) and `gate_eligible`, and those are recorded, but the C4 gate
does not consume them. Section 3.7 explains why a repairing candidate can legitimately look *worse*
on the C6 acceptance policy and why that is not repaired by weakening the policy.

---

## 2. Probe record

No provider run was performed for this design. Everything below is a static read of checked-in
bytes or a host probe that neither starts `llama-server` nor loads the model.

### 2.1 What the frozen C6 evidence actually contains

`eval/prompt/gate/prompt-evaluation-improved.json` (283,727 bytes, `evaluation_id: c6g2-measure`)
holds 12 rows — 3 tasks × 2 variants × 2 samples. Read directly:

| Task | PARENT s1 | PARENT s2 | CANDIDATE s1 | CANDIDATE s2 |
| --- | --- | --- | --- | --- |
| `duration-half-away-from-zero` | FAIL | FAIL | **PASS** | **PASS** |
| `layer-precedence-frozen-module` | FAIL | FAIL | FAIL | FAIL |
| `record-codec-round-trip` | FAIL | FAIL | FAIL | FAIL |

`corpus_aggregate`: `parent_pass_count: 0`, `candidate_pass_count: 2`, `paired_pass_count: 0`,
`completion_gain_count: 2`, `parent_repair_loop_count: 0`, `candidate_repair_loop_count: 0`,
`repair_loop_regression_count: 0`. Result `status: IMPROVED`, `gate_eligible: true`.

**Ten of the twelve rows fail at attempt 1**: all six PARENT rows, plus the four CANDIDATE rows of
`layer-precedence-frozen-module` and `record-codec-round-trip`. Only the two CANDIDATE rows of
`duration-half-away-from-zero` pass first try. Those ten failures are exactly the repair attempts
this capability would run — a substantial arm, not a corner case. Section 5.2's cost estimate uses
22 provider calls: 12 initial plus 10 repair.

The two passing rows carry the only real timings this repository has for this path:

```text
rows[1]  duration-half-away-from-zero  sample 1  CANDIDATE
         prompt_preparation_ns                    20,000,000
         measurement.generation_to_passing_patch_ns  81,123,017,079   (81.12 s)
         time_to_passing_patch_ns                 81,143,017,079

rows[2]  duration-half-away-from-zero  sample 2  CANDIDATE
         prompt_preparation_ns                    20,000,000
         measurement.generation_to_passing_patch_ns  23,395,804,636   (23.40 s)
         time_to_passing_patch_ns                 23,415,804,636
```

`time_to_passing_patch_ns == prompt_preparation_ns + generation_to_passing_patch_ns` holds exactly
in both rows, as `c6-prompt-context-optimizer.md` §5.2 requires.

`prompt_preparation_ns` is identical in all twelve rows because **it is a hard-coded constant**,
`preparation_ns = 20_000_000` at `scripts/prompt-evaluate.py:3790`, not a measured span. That
deviates from §5.2's prose, which says the evaluator starts and stops a clock around context
selection and rendering. This capability neither relies on it nor silently repairs it: section 3.6
keeps `prompt_preparation_ns` exactly as it is, and section 5.4 records fixing it as a separate
concern with its own owner.

**The 3.5× spread between two samples of the same prompt at temperature 0 is the single most
important measurement fact in this design.** Same task, same variant, same rendered prompt digest,
`temperature_micros: 0`, greedy decoding — 81.12 s and 23.40 s. The two samples differ only in
`paired_seed`, which is `seed_base + sample_index - 1` = 20,260,824 and 20,260,825
(`scripts/prompt-evaluate.py:3473`), and a seed cannot change a greedy decode's output. Whatever
varies, it is not the sampling distribution; it is server state, prompt-cache reuse, and host
contention. Any per-attempt or per-run timing in this capability inherits that spread, and section
5.3 refuses to make a speed claim because of it.

### 2.2 The frozen-corpus constraint, read from the manifest

`eval/prompt/canonical-v1/corpus-file-set.manifest` declares 27 regular files with mode, length,
kind, and SHA-256. Its members include, verbatim from the manifest's third column:

```text
eval/runners/run-coding-task.py
eval/tasks/prompt-v1/duration-half-away-from-zero.json
eval/tasks/prompt-v1/layer-precedence-frozen-module.json
eval/tasks/prompt-v1/record-codec-round-trip.json
scripts/prompt-fixed-adapter.py
scripts/prompt-measurement-adapter.py
scripts/prompt-snapshot-helper.py
```

plus the eleven fixture-repository files and the twelve per-task `task.json`, `task-prompt.json`,
and `context-sources.json` files.

`c6-prompt-context-optimizer.md` §9 describes how `make prompt-gate-check` consumes them: the
validator "reads the locator's manifest, hashes its exact canonical bytes, verifies every listed
regular file beneath the corpus root, and requires the manifest digest and membership to equal the
evidence's expected source identity." The corpus root is the align-llm checkout **at the derived
actual CI head** — today's head, not the evaluated commit `762b1d0f…`, which is separately proved
reachable by `merge-base --is-ancestor`.

**Therefore: editing any of those 27 files at any future head breaks `make prompt-gate-check`
against the merged C6-MEASURED evidence.** This is not a soft preference. It is the constraint that
selects section 3.1's surface.

Each task manifest independently pins the same files by digest in its `artifacts` list — including
`scripts/prompt-measurement-adapter.py` at `a9d82f7b…` — and carries
`measurement_adapter_runtime: "PYTHON:2d3796db…"`. A task manifest cannot name a different adapter
without changing its own `content_sha256`, which changes the corpus source digest, the scope, and
the frozen baseline activation. A new corpus is the only way to name anything new.

### 2.3 The runner is already a single-attempt, stateless function

`eval/runners/run-coding-task.py` `main()` accepts exactly `[--retained-inputs] TASK_JSON
CANDIDATE_PATCH`. `_validate_candidate` (line 1591) does, in order: run the validation command on
the pristine pinned checkout and require a **non-zero** exit ("pinned fixture unexpectedly passes
before repair"); prove the checkout is still pristine; `git apply --check` then `git apply` the
candidate patch; check the allowed-edit set; snapshot worktree and index; run the validation command
again; re-check the allowed edits and prove the validation did not mutate the worktree or the index;
raise `CandidateValidationFailed` if the second run is non-zero.

Two consequences.

1. **A second attempt is a second ordinary invocation.** The runner constructs its own fresh pinned
   checkout each time and asserts the fixture fails before the patch. Nothing carries over. The
   repair attempt is not a resumption of attempt 1; it is an independent validation of a different
   patch against the same pinned fixture. This is what makes an evaluator-owned loop possible
   without touching the runner.
2. **Naming collision, resolved now.** The runner already prints `pre-repair validation` and
   `post-repair validation`, where "repair" means "the model's edit". Those strings appear verbatim
   inside `measurement.diagnostic_stdout` of every existing row. This document uses **attempt** for
   the outer loop and never reuses the runner's word. `attempt_kind` is `INITIAL` or `REPAIR`; the
   runner's own vocabulary is left alone so the frozen diagnostics stay readable.

The runner also bounds captured output: `MAX_COMMAND_OUTPUT_BYTES = 64 * 1024` with a
`b"\n[output truncated]"` marker. The adapter narrows further to `DIAGNOSTIC_LIMIT = 16_384` and
`SUMMARY_LIMIT = 4_096`. Section 4 builds the repair prompt on the adapter's already-bounded,
already-redacted strings for exactly this reason.

### 2.4 The adapter receives a rendered prompt; it does not render one

`scripts/prompt-measurement-adapter.py` `REQUEST_FIELDS` (line 654) declares the
`TASK_ADAPTER_REQUEST` field order. The prompt-bearing fields are `rendered_prompt_path` and
`rendered_prompt_sha256`; the adapter decodes a sealed `RENDERED_PROMPT` artifact, verifies its
digest against the request, and hands its text to the derived `./main prompt generate` child. The
adapter's own docstring is explicit: "It owns workspace orchestration, sealed input admission,
contained execution of the validation runner, `TaskMeasurement` assembly, and redaction, and it
performs no provider wire serialization."

`c6-prompt-context-optimizer.md` §4.5 fixes the ownership: "The evaluator, not the task adapter,
writes task/sample/variant/input identities into the final row. The measurement adapter returns only
the measured payload plus its `EnvironmentProbe` and seed attestation."

**The evaluator already owns rendering.** That is the hinge of section 3.1: the repair prompt is
rendered by `scripts/prompt-evaluate.py`, which is not a corpus member and may change freely.

### 2.5 Host probe — the provider is not the recorded provider

Run on this host, without starting a server or loading a model:

```text
$ ls -l /opt/homebrew/bin/llama-server
lrwxr-xr-x  /opt/homebrew/bin/llama-server -> ../Cellar/llama.cpp/0.2.0/bin/llama-server

$ shasum -a 256 /opt/homebrew/bin/llama-server
b6ff7e912a9690ffec38878cad25b9ec1424a5537bd72010effe2fc9bfe64f74

$ /opt/homebrew/bin/llama-server --version
version: 0.2.0 (build 10566, commit bb4caa754)
built with AppleClang 21.0.0.21000101 for Darwin arm64

$ ls -l ~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf
4683073536 bytes

$ docker version --format '{{.Server.Version}}'
28.5.1
```

`eval/prompt/canonical-v1/generation-policy.json` records:

```text
provider_service_revision:
  llama.cpp/b10610+a14dba686aaafba3a2d6b5eb8820b0df5c5d2d92;
  server-sha256:e3905073c4322ff33c7b365c9ea10aadbc776fe3eab372869694555d8f5693a8;
  model-sha256:509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c
```

**The available server is not that server.** Build 10566 at commit `bb4caa754` versus build
`b10610` at `a14dba686…`; SHA-256 `b6ff7e91…` versus `e3905073…`; and a Darwin arm64 binary where
the recorded one was reachable from inside the Linux evaluation container. Reusing
`canonical-v1/generation-policy.json` unchanged would persist a false claim about which service
answered. Section 3.5 mints a new generation policy carrying the observed revision and makes the
mismatch a fail-closed check rather than a comment.

Build 10566 at `bb4caa754` is, incidentally, the same llama.cpp commit the R2c decode instrument
pins (`docs/align-development.md`, "recorded instrument build 10566"), so this host's Homebrew
formula and Track B's pinned source build agree on the upstream commit.

### 2.6 The failing edit set is not reachable, and this narrows the capability

`TASK_MEASUREMENT` has 21 fields and none of them is the model's output. The adapter parses the
generation response's `FILE:`-plus-fence blocks, builds a whole-file-replacement unified diff, hands
it to the runner, and **drops both when `measurement()` returns**. What survives into the row is
`patch_size_bytes`, `rendered_prompt_sha256`, and the three diagnostic strings. The evaluator never
holds the model's edits or the derived patch at any point.

So an evaluator-owned repair prompt **cannot contain the failing edit set** without changing the
adapter — and the adapter cannot change (2.2). The shipped repair prompt carries the four status
labels, the diagnostic summary, and the two diagnostic streams. It is a diagnostics-driven second
attempt, not a patch-plus-diagnostics repair.

Two things soften this, and one does not.

- `diagnostic_summary` already names the edited paths. The frozen evidence's value is verbatim
  `"provider-backed candidate patch failed validation; applied edits: src/duration.py"`, so attempt
  2 learns *which* file attempt 1 touched even though it cannot see *what* it wrote.
- The response format is whole-file, not a diff (`c6-prompt-context-optimizer.md` §11.3), and the
  fixture files are small, so attempt 2 rewrites the file from the task prompt's own source context
  rather than patching a diff it cannot see.
- What is genuinely lost is the model's ability to see its own mistake. A repair prompt that shows
  the failing edit next to the failing assertion is a strictly stronger signal, and this capability
  does not deliver it.

**This is a narrowing of the intended boundary and it is recorded as one**, not absorbed. Section
5.4 carries it as a deferral with an explicit resume condition, and section 5.7 states the two
alternatives that would restore it and why neither is taken now.

C4's roadmap gate is still addressed in substance: "初回失敗から自動修正してtest passまで到達" asks
for automatic correction from a first failure to a passing test, driven by the run's own real
diagnostics. That is exactly what ships. The edit set would make it stronger, not different.

### 2.7 The evaluator has a hard size budget

`src/prompt_evaluate.align:8` pins `scripts/prompt-evaluate.py` byte-exactly:

```text
EVALUATOR_SOURCE_SHA256 = 5d792743a54c7d95ebc64564e632758c3f196f53ae94c833ddcf0c05368aa43e
```

and `src/prompt_evaluate.align:163-166` rejects the evaluator unless its length is strictly greater
than `EVALUATOR_ARG_CHUNK_BYTES * 2` and at most `EVALUATOR_ARG_CHUNK_BYTES * 3`, with
`EVALUATOR_ARG_CHUNK_BYTES = 65_536`. The admissible window is **131,073 to 196,608 bytes**. The
file is **185,093 bytes** today, leaving **11,515 bytes of headroom**.

The pin itself must change — the file changes — and that is routine. The *window* is the constraint:
the attempt loop, the repair-prompt assembly, the version-2 row assembly, and the new aggregates
must fit in 11,515 bytes, or `src/prompt_evaluate.align` must widen the window to four chunks
(262,144 bytes). Widening is legal — `src/prompt_evaluate.align` is not a corpus member — but it is
a public change to the evaluator launch contract and it belongs in the ledger before implementation,
not as a surprise at the end. Section 3.11 records both.

### 2.8 What the probes settle

1. The repair loop must live in `scripts/prompt-evaluate.py`; the adapter and the runner cannot
   move (2.2, 2.3, 2.4).
2. A new corpus freeze is mandatory, because `maximum_repair_loops` lives in a corpus member (2.2).
3. The repair prompt must be built from the adapter's already-bounded, already-redacted diagnostic
   strings, or it is not re-derivable from persisted evidence (2.3, section 4.4).
4. The repair prompt cannot contain the failing edit set, and the capability is narrowed and
   labelled accordingly (2.6).
5. A per-attempt timing field is mandatory, because a failing attempt's measurement carries `None`
   for `generation_to_passing_patch_ns` by the §5.2 state machine, so the repair total cannot be
   assembled from adapter-reported values alone (2.1, section 3.6).
6. The provider service revision must be re-derived and checked, not inherited (2.5).
7. No timing claim in this capability may rest on a single measurement (2.1).
8. The whole addition has an 11,515-byte budget or an explicit window widening (2.7).

---

## 3. Public-contract ledger

This ledger is the contract. If implementation discovers a different public promise, update this
table, the closure matrix, code, fixtures, and directly affected documentation together, before
review.

### 3.1 The surface decision: an evaluator-owned attempt loop

| Surface | Exact contract |
| --- | --- |
| Loop owner | `scripts/prompt-evaluate.py`. For each (task, sample, variant) it renders the initial prompt, seals it, invokes the measurement adapter, and — only when the returned `TaskMeasurement.status` is `FAIL` and the task's `regression_limits.maximum_repair_loops >= 1` — renders a repair prompt from that measurement, seals it, and invokes the **same unchanged adapter** a second time with a fresh workspace and result path. |
| Adapter | `scripts/prompt-measurement-adapter.py` is **byte-identical**. It performs one generation call and one validation per invocation, exactly as `c6-prompt-context-optimizer.md` §11.3 contracts. Its `TASK_ADAPTER_REQUEST` shape, field order, digests, sealing, and `TaskMeasurement` output are unchanged. |
| Validation runner | `eval/runners/run-coding-task.py` is **byte-identical**. The repair attempt is a second ordinary invocation against a fresh pinned checkout (§2.3). |
| Generation | Each attempt is one derived `./main prompt generate` child call. No provider module, endpoint, wire format, credential path, or seed-attestation mechanism changes. |
| Repair selection | Purely a corpus property: `regression_limits.maximum_repair_loops >= 1` in the task manifest. There is **no new CLI flag and no new environment variable.** `eval/prompt/gate/environment-policy.json` allows exactly `LANG`, `LC_ALL`, `PATH`, `PYTHONDONTWRITEBYTECODE`, `PYTHONNOUSERSITE`; it is reused byte-identical, so no new environment input is admissible. |
| Attempt bound | At most `1 + min(maximum_repair_loops, 1)` attempts per row. The corpus sets `maximum_repair_loops: 1`, so at most two. A task declaring `0` behaves exactly as today, which is how `canonical-v1` keeps working under the new evaluator. |

The alternative — a repair-capable adapter, or a wrapper adapter composing two adapter runs — was
rejected. The repair prompt is a function of attempt 1's realized output, so its producer must be
whoever also owns rendering, sealing, and expected-input identity. That is the evaluator (§2.4). A
repair-capable adapter would additionally have to be a new corpus member, duplicating 1,445 lines of
sealed-input, containment, and redaction logic whose whole value is that it has been reviewed once.

### 3.2 `PROMPT_TASK_ROW`, `schema_version: 2`

Declared field order. Fields marked **new** do not exist at version 1.

```text
PromptTaskRow:
  schema_version                      2
  artifact_kind: PROMPT_TASK_ROW
  evaluation_id
  task_id
  sample_index
  variant: PARENT | CANDIDATE
  variant_id
  variant_sha256
  prompt_preparation_ns
  repair_loop_count: i64                                   new
  generation_to_passing_patch_ns: Option<i64>              new
  time_to_passing_patch_ns: Option<i64>
  attempts: [TaskAttemptRecord]                            new
  evaluation_input: EvaluationInputIdentity
  measurement: TaskMeasurement
  content_sha256
```

```text
TaskAttemptRecord:
  schema_version                      1
  artifact_kind: TASK_ATTEMPT_RECORD
  attempt_index: i64                       1-based, dense, ascending
  attempt_kind: INITIAL | REPAIR
  status: PASS | FAIL | POLICY_VIOLATION | ERROR | SKIPPED
  skip_reason: NONE | REPAIR_PROMPT_BUDGET | REPAIR_NOT_ELIGIBLE | REPAIR_INPUT_UNAVAILABLE
  rendered_prompt_sha256
  repair_prompt_source: Option<RepairPromptSource>   Some exactly when attempt_kind == REPAIR
  adapter_request_sha256
  snapshot_request_sha256                  present iff the attempt ran
  before_snapshot_result_sha256            present iff the attempt ran
  after_snapshot_result_sha256             present iff the attempt ran
  input_snapshot_sha256                    present iff the attempt ran
  generation_request: GenerationRequestIdentity
  seed_attestation: SeedCapabilityAttestation
  paired_seed: i64
  measurement: TaskMeasurement             the adapter's verbatim v1 document for this attempt
  repair_preparation_ns: i64               0 for attempt 1
  adapter_elapsed_ns: i64
  adapter_overhead_ns: Option<i64>         Some exactly on a PASS attempt
  measurement_sha256
  content_sha256
```

```text
RepairPromptSource:
  schema_version                      1
  artifact_kind: REPAIR_PROMPT_SOURCE
  template_sha256                          the sealed corpus template
  source_attempt_index: i64                the attempt whose output was consumed
  source_measurement_sha256
  included_sections: [STATUS | SUMMARY | STDOUT | STDERR]   fixed order, subset
  dropped_sections: [ ... ]                fixed order, disjoint from included
  assembled_bytes: i64                     <= generation_policy.max_prompt_bytes
  content_sha256
```

**The four trace digests are the attempt's own contained invocation.** Each attempt seals its own
prompt and runs the validation runner in its own workspace, so it produces its own
`SNAPSHOT_REQUEST`, its own before/after `SNAPSHOT_RESULT`, and its own `TASK_INPUT_SNAPSHOT`.
`snapshot_attestations` stays **one record per row** because its schedule check binds it
positionally, so it reaches the first invocation only; without these four, a repair invocation's
trace records would be referenced by nothing. Naming is not sufficient and is not the rule: each
digest must resolve to **exactly one** persisted record of that row's task, the before and after
results must be the same observation, both must be closed over the resolved request, and the input
snapshot must be that task's and carry the snapshot's own artifact digests — the same checks the
row's attestation is held to (`verifier_attempt_trace_cross_valid`,
`src/prompt_score.align`). The `input_snapshots` upper bound therefore moves from one per row to
one per **invocation**; at version 1 that is the same bound, because a version-1 row runs exactly
once.

**A `SKIPPED` attempt carries only identity, not a run.** `rendered_prompt_sha256`,
`adapter_request_sha256`, the four trace digests, `generation_request`, `seed_attestation`,
`measurement`, `measurement_sha256`, and `adapter_overhead_ns` are all absent;
`adapter_elapsed_ns` is `0`;
`repair_preparation_ns` records the assembly work that reached the skip decision;
`repair_prompt_source` is present with its `dropped_sections` when the skip was
`REPAIR_PROMPT_BUDGET`, and absent otherwise. A `SKIPPED` attempt is never counted in
`row.repair_loop_count` and never contributes to any timing sum.

**Every attempt carries its own full `TaskMeasurement`,** and `row.measurement` is byte-equal to the
final attempt's — ladder row 18 asserts it. One measurement is duplicated per multi-attempt row,
which is deliberate: version-1-shaped consumers keep reading `row.measurement` unchanged, and the
per-attempt copy keeps attempt 1's status, diagnostics, and patch size retrievable after attempt 2
overwrites the row-level view. At 22 measurements the measured gate run's result document is
614,440 bytes against the frozen 283,727 — **2.17x**, not the "roughly three times" this section
estimated before the run — far inside `RESULT_LIMIT` (268,435,456), with the evidence sidecar at
16,754 bytes inside `EVIDENCE_LIMIT` (8,388,608), so `compact_oversized_result`'s
`PROMPT_TRACE_OVERFLOW` path is not reached and is not relied upon.

`PROMPT_EVALUATION_RESULT` moves to `schema_version: 2` in lockstep. **A document's rows must all
carry the container's version**; a version-2 result containing a version-1 row, or the reverse, is
invalid. This keeps the two frozen version-1 documents (`prompt-evaluation-improved.json` and its
evidence sidecar) uniformly version 1 and decodable forever.

`PROMPT_EXPECTED_INPUT_DIGEST` moves to `schema_version: 2`, gaining `attempt_index` and becoming
one record **per attempt** rather than per row. §4.5's binding rule — "no duplicate, missing, or
extra identity" — extends to (task, sample, variant, attempt_index).

`TASK_MEASUREMENT` **does not change**. It stays `schema_version: 1` with its existing 21 fields.
Each attempt's `measurement` is the adapter's verbatim output, and `row.measurement` is the
**final** attempt's measurement — so every existing consumer that reads `row.measurement.status`,
`build_status`, `test_status`, `patch_size_bytes`, `unrelated_diff_count`,
`public_api_change_count`, `policy_violation_count`, `cleanup_passed`, `containment_passed`, or
`benchmark_regression_ppm` keeps working with no change and no re-derivation.

### 3.3 One producer per field

The rule that makes the schema safe is that no field has two writers.

| Field | Sole producer | Rule at version 2 |
| --- | --- | --- |
| `attempt.measurement` and `measurement_sha256` | the adapter | verbatim; the evaluator never edits an adapter document |
| `attempt.measurement.repair_loop_count` | the adapter | **must be 0** on every attempt; each adapter invocation is single-attempt (`scripts/prompt-measurement-adapter.py:1323` emits the literal `0`). A non-zero value is `ERROR`/`ADAPTER`. |
| `row.repair_loop_count` | the evaluator | count of attempts with `attempt_kind == REPAIR` and `status != SKIPPED` |
| `attempt.paired_seed` | the evaluator | `seed_base + sample_index - 1`, identical for both attempts of a row; greedy decoding makes it a transport fact, not an output determinant |
| Diagnostics, status labels, `patch_size_bytes` | read through `attempt.measurement.*` | never copied to a second field, never re-truncated, never re-redacted |
| `attempt.generation_request`, `seed_attestation` | the adapter (which copies them from the generation child) | the evaluator re-derives `rendered_prompt_sha256` independently and requires equality before wrapping, exactly as §5.2 requires today |
| `attempt.repair_preparation_ns`, `adapter_elapsed_ns` | the evaluator | monotonic clock, evaluator-observed |
| `row.generation_to_passing_patch_ns`, `time_to_passing_patch_ns` | the evaluator | checked addition, section 3.6 |
| `repair_prompt_source.*` | the evaluator | section 4 |

At version 1 the authority is unchanged: `row.measurement.repair_loop_count` is the repair count and
`row.measurement.generation_to_passing_patch_ns` is the generation total. **A version-1 row has no
`attempts`, no row-level `repair_loop_count`, and no row-level `generation_to_passing_patch_ns`, and
must not be given compatibility defaults for them.** The scorer selects by version, not by presence.

**Decode dispatch is by version, before field decoding, and it is a real constraint on the Align
side.** The pinned `json.decode` requires every declared field exactly once while skipping
undeclared keys, so a record whose version-2 members were *required* would reject every version-1
row, and one that simply omitted them would drop fields that still contribute to `content_sha256`.

**One record with `Option` members ships, and there is no `PromptTaskRowV2`.** This is what is in
the tree, and it is stated here rather than in the deviation list alone (section 10.2 deviation 10
records how the choice was reached). `src/prompt_artifacts.align` declares a single
`PromptTaskRow` whose version-2 members — `repair_loop_count`, `generation_to_passing_patch_ns`,
and `attempts` — are `Option`. The canonical encoder omits an `Option::None`, so the frozen
version-1 documents decode and re-encode byte-identically and their persisted digests still
verify. The contract is:

- `PromptTaskRow` decodes both shapes; every version-2 member is `Option` on the wire.
- **Presence is never how the version is detected.** The scorer reads `schema_version` first and
  then requires every version-2 member to be present at version 2 and absent at version 1,
  rejecting either mismatch (`verifier_row_v2_members_absent`). There is no compatibility default
  and no presence sniffing.
- A row whose own `schema_version` disagrees with the container's is rejected before any field
  decode.
- Neither shape is ever migrated into the other, per `c6-prompt-context-optimizer.md`'s
  schema-version-1 rule.

The version peek this section once flagged as a possible Align gap is a non-issue under that
design: the row's own `schema_version` is an ordinary decoded field, read before any version-2
member is consulted. No unshipped Align surface is consumed.

### 3.4 New and reused corpus assets

Every new file. Nothing under `eval/prompt/canonical-v1/`, `eval/prompt/gate/`, or
`eval/tasks/prompt-v1/` is modified, moved, or deleted.

| Path | Contents |
| --- | --- |
| `eval/tasks/prompt-v1r/duration-half-away-from-zero.json` | byte-for-byte the `prompt-v1` manifest except `regression_limits.maximum_repair_loops: 1`, `generation_policy_path` pointing at `canonical-v1r`, the added `repair_template_path` / `repair_template_sha256` pair, and the recomputed `content_sha256`. `task_prompt_path`, `context_sources_path`, `task_definition_path`, `repo_path`, `repo_revision`, `validation_runner_path`, `validation_runner_sha256`, `argv`, `measurement_adapter_runtime`, and the whole `artifacts` list are identical to `prompt-v1`'s. |
| `eval/tasks/prompt-v1r/layer-precedence-frozen-module.json` | as above |
| `eval/tasks/prompt-v1r/record-codec-round-trip.json` | as above |
| `eval/prompt/canonical-v1r/repair-template.json` | `REPAIR_PROMPT_TEMPLATE`, `schema_version: 1`. Section 4.2. |
| `eval/prompt/canonical-v1r/generation-policy.json` | `canonical-v1`'s policy with `generation_policy_id: prompt-v1r-generation-v1` and the observed `provider_service_revision` of section 3.5. `max_prompt_bytes`, `max_tokens`, `temperature_micros: 0`, `seed_mode: PAIRED_FIXED`, `seed_base: 20260824` are unchanged. |
| `eval/prompt/canonical-v1r/corpus.json` | `corpus_id: prompt-v1r`, naming the three `prompt-v1r` task files |
| `eval/prompt/canonical-v1r/corpus-file-set.manifest` | 29 entries: `canonical-v1`'s 24 unchanged members with identical digests, the 3 new task manifests, the repair template, and the new generation policy. `eval/runners/run-coding-task.py`, `scripts/prompt-measurement-adapter.py`, `scripts/prompt-fixed-adapter.py`, and `scripts/prompt-snapshot-helper.py` appear with the **same digests as in `canonical-v1`** — that identity is the machine-checkable statement that this capability did not move them. |
| `eval/prompt/canonical-v1r/scope.json` | `corpus_id: prompt-v1r`, the new `corpus_revision`, the new `generation_policy_sha256`, and `acceptance_policy_sha256`, `base_prompt_sha256`, `repo_prompt_sha256` **identical to `canonical-v1`'s** |
| `eval/prompt/canonical-v1r/prompt-activation-baseline-v1r.json` | the baseline activation over the new scope; the effective variant is byte-identical to `baseline-v1`'s |
| `eval/prompt/canonical-v1r/README.md` | what is frozen, what is reused by digest, and the rule that it is never edited after measurement |
| `eval/prompt/c4-repair-gate/` | the measured evidence: `c4-repair-evaluation.json`, `c4-repair-evaluation-evidence.json`, `c4-repair-gate-manifest.json`, `README.md`. A separate directory; `eval/prompt/gate/` stays C6's. |

Reused **by path, unmodified**: `eval/prompt/canonical-v1/base-prompt.json`,
`repo-prompt.json`, `evaluation-provider-control.json`, `prompt-acceptance-policy.json`;
`eval/prompt/gate/environment-policy.json`; every `eval/tasks/prompt-v1/<task>/` artifact; every
`eval/fixtures/prompt-v1-*/repository/` file; `eval/runners/run-coding-task.py`;
`scripts/prompt-measurement-adapter.py`; `scripts/prompt-snapshot-helper.py`.

`maximum_repair_loops: 1`, not 4. The validator's structural ceiling is 64
(`src/prompt_score.align:274`, `bounded_nonnegative(limit.maximum_repair_loops, 64)`; the same bound
appears at `scripts/prompt-evaluate.py:781`), and the C6 corpus sets 0. Setting the new corpus to
exactly 1 makes the **manifest itself** the cap: a second repair attempt would raise
`repair_loop_count` to 2 and be scored as a `REPAIR_LOOPS` policy violation
(`src/prompt_score.align:706` and `:998`) rather than silently permitted. A value of 4 would leave
three loops of unenforced headroom that no code path can reach and no test can exercise. Raising it
is section 5.4's deferral.

### 3.5 Provider topology and provider-revision evidence

| Surface | Exact contract |
| --- | --- |
| Validation | `bwrap`, unchanged, inside a Linux container. On this macOS host: `docker run --platform linux/arm64` with the repository bind-mounted at `/work/align-llm`, matching the C8 benchmark recipe already used for `baseline-atomic` / `compare-atomic`. `ENVIRONMENT_IDENTITY_CORE` records that container: `os: linux`, `architecture: aarch64`. |
| Generation | The derived `./main prompt generate` child runs **inside the same container** and dials `provider_control.endpoint`. |
| Endpoint | `http://127.0.0.1:18080/v1/chat/completions`, **byte-identical to `canonical-v1`'s** `evaluation-provider-control.json` (`content_sha256: f8f90432…`). It is not changed to `host.docker.internal`. |
| Reachability | A container-local loopback forwarder binds `127.0.0.1:18080` inside the container and proxies to the host: `socat TCP-LISTEN:18080,fork,reuseaddr,bind=127.0.0.1 TCP:host.docker.internal:18080`. `socat` is installed in the evaluation image; it is not required on the macOS host, where it is absent. |
| Container privileges | The evaluation container is granted `cap-add SYS_ADMIN` plus unconfined `seccomp`, `apparmor`, and `systempaths`. `bwrap` builds user, mount, and PID namespaces and re-mounts `proc` inside the namespace the validation runner prepares; Docker's default profile denies the namespace calls, and its masked `/proc` paths deny the re-mount, surfacing as `Can't mount proc on /newroot/proc: Operation not permitted` **after** that row's generation call is already paid for. This widens the *container's* privileges, not the validation sandbox's: `bwrap` still drops all capabilities inside, still contains each fixture command exactly as it does outside Docker, and `containment_passed` is still checked and recorded per attempt. Full `privileged` also works and is deliberately rejected as far broader. The exact grant is published in every run record's `container_privileges`, so a reader can see what the measurement was taken under. |
| Why a forwarder | So that **no machine-specific hostname reaches any persisted artifact.** The provider control stays frozen and digest-identical to C6's, the endpoint stays a loopback address, and the forwarder is topology recorded in the run's check evidence. This is the same discipline as the prior "temp paths in persisted rows" incident class (section 5.6). |
| Provider identity, recorded | `canonical-v1r/generation-policy.json` sets `provider_service_revision` to `llama.cpp/10566+bb4caa754;host:darwin-arm64;server-sha256:b6ff7e912a9690ffec38878cad25b9ec1424a5537bd72010effe2fc9bfe64f74;model-sha256:<computed>`, where `<computed>` is `shasum -a 256` of `~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf` (4,683,073,536 bytes) taken at freeze time. |
| Provider identity, checked | Before the run, on the host, `scripts/probe-provider-service` emits a `PROVIDER_SERVICE_PROBE` document from `llama-server --version`, the resolved binary's SHA-256, and the model file's SHA-256, and **fails closed** unless the three values equal the policy's `provider_service_revision` components. Its output is check evidence, not a corpus member. |
| Provider identity, in-band | Each generation response's advertised model id must equal `qwen2.5-coder-7b-instruct-q4_k_m`. This is the only provider-identity signal available from inside the container and is the second half of the fail-closed pair. |

**Measurement-risk note.** The host probe observes the binary the operator intends to run, and the
in-band check observes the model the server reports; neither observes that the process answering
`127.0.0.1:18080` inside the container is the process whose binary was hashed. A different server
started on the same port would satisfy both checks if it advertised the same model id. The trust
therefore rests on the operator's single-server host and on the two independent checks agreeing, not
on an attested channel. This is a strictly weaker guarantee than C6 recorded, because C6's server
was reachable inside the evaluation environment and this one is not.

### 3.6 Timing

At version 2 the row's totals are evaluator-observed and evaluator-computed:

```text
attempt.adapter_elapsed_ns      monotonic span from immediately before the adapter child is
                                spawned to immediately after it exits and its result is read
attempt.repair_preparation_ns   monotonic span from immediately after the previous attempt's
                                adapter exits to immediately before this attempt's adapter is
                                spawned; 0 for attempt 1
row.generation_to_passing_patch_ns
   = Some( Σ_{i=1..k} (attempts[i].adapter_elapsed_ns + attempts[i].repair_preparation_ns) )
     where k is the index of the first attempt with status PASS
   = None when no attempt passes
row.time_to_passing_patch_ns
   = Some(prompt_preparation_ns + generation_to_passing_patch_ns)  by checked addition
   = None when generation_to_passing_patch_ns is None
```

Every addition is exact `i64` and is bounds-checked before it is persisted, against the **existing**
ceiling that both implementations already enforce: `> 0` and `<= 7_200_000_000_000` ns, two hours
(`scripts/prompt-evaluate.py:1759-1760`; `src/prompt_score.align:2828`, which uses
`checked_add` and returns `Err(Error.Invalid)` on overflow). That ceiling is not raised. Two attempts
bounded by `provider_control.timeout_ns` = 1,800,000,000,000 ns each sum to at most
3,600,000,000,000 ns before validation and preparation, which fits with room to spare. **No
conversion saturates and no sum is clamped**; an out-of-bound total is `INVALID_INPUT`/`TIMING` with
the observed values recorded, because a silently clamped nanosecond count is the prior incident
class this rule exists to prevent (section 5.6).

The evaluator's per-invocation outer adapter timeout,
`nested_owner_timeout(task.timeout_ns + provider_control.timeout_ns)`
(`scripts/prompt-evaluate.py:1955`), is **unchanged**. It bounds one adapter invocation with its two
inner children, and an evaluator-owned loop makes two such invocations rather than one longer one —
another reason the loop belongs to the evaluator rather than inside the adapter.

`adapter_overhead_ns = adapter_elapsed_ns − measurement.generation_to_passing_patch_ns`, present
only on a `PASS` attempt where the adapter reports a `Some` value.

**This is a redefinition and it is deliberate.** At version 1 the metric was the adapter's own
window, which starts immediately before the first provider call and excludes adapter snapshotting,
input decoding, result encoding, and cleanup (`c6-prompt-context-optimizer.md` §5.2 and §11.3). At
version 2 a failing attempt reports `None` for that window by the §5.2 state machine, so the repair
total cannot be assembled from adapter-reported values at all. The evaluator-observed span is the
only value defined for every attempt.

**Measurement-risk note.** Version-2 totals are therefore **not comparable to the frozen version-1
numbers** of section 2.1; they are a superset that includes per-attempt adapter overhead and
evaluator repair-prompt assembly. `adapter_overhead_ns` publishes the size of the difference on
every passing attempt so the gap is measured rather than argued. Within one version-2 run the
overhead is paid symmetrically by both variants and both attempts, so it cannot bias the paired
comparison — the same argument `c6-prompt-context-optimizer.md` §11.3 makes for generation-child
spawn, and with the same limitation: symmetry protects the comparison, not the absolute number.

### 3.7 Scoring, aggregates, and why the acceptance verdict is not the gate

New aggregate fields, all evaluator-computed and all independently recomputed by the pure Align
verifier (never trusted from the persisted document, per §9's rule):

```text
task_aggregate:      parent_repair_attempt_count, candidate_repair_attempt_count,
                     parent_repair_recovery_count, candidate_repair_recovery_count,
                     repair_recovery_paired: bool
corpus_aggregate:    repair_attempt_count, repair_recovery_count,
                     repair_recovery_paired_count
```

`repair_recovery_count` counts rows whose first attempt is `FAIL` and whose repair attempt is
`PASS`. `repair_recovery_paired_count` is the section 1.4 gate quantity.

Existing scoring is unchanged in mechanism and changes in exactly two ways.

1. **Source-of-truth selection.** `src/prompt_score.align:2849` and
   `scripts/prompt-evaluate.py:2939` read `row.measurement.repair_loop_count`. At version 2 they
   read `row.repair_loop_count`. The `REPAIR_LOOPS` reason (`src/prompt_score.align:998`), the
   serious-regression count (`:706`), the corpus regression `max(0, candidate total − parent total)`
   (`scripts/prompt-evaluate.py:2892`), the acceptance limit
   `maximum_repair_loop_regression_count`, and the acceptance timing arm's
   `corpus_candidate_repairs <= corpus_parent_repairs` (`:2958`) are all untouched.
2. **The `REPAIR_LOOPS` limit check becomes variant-symmetric.** Today it is candidate-only:
   `scripts/prompt-evaluate.py:2941-2944` and `scripts/prompt-gate-validator.py:1575-1585` compare
   only the CANDIDATE row's `repair_loop_count` against `maximum_repair_loops`, so a PARENT row
   exceeding the task's declared cap is not checked anywhere. With repair enabled on both arms that
   hole becomes reachable, so at version 2 the check applies to both variants. **No version-1
   verdict changes**: every version-1 row in existence has `repair_loop_count: 0` against a limit of
   `0`, so the extended check is vacuous on the frozen chain, and an owner test asserts that
   rescoring the frozen evidence is byte-identical before and after.

**Repair runs on both variants, symmetrically.** It is a property of the measurement path, not of
the prompt variant. A PARENT row that fails gets a repair attempt on exactly the same terms as a
CANDIDATE row that fails.

**Two honest consequences, neither of which is repaired by weakening a policy.**

1. `eval/prompt/canonical-v1/prompt-acceptance-policy.json` sets
   `maximum_repair_loop_regression_count: 0`. If the CANDIDATE arm repairs strictly more often than
   the PARENT arm across the corpus, the evaluation records a serious regression and
   `gate_eligible` may be false. On the section 2.1 distribution the reverse is expected — PARENT
   fails 6 of 6 and CANDIDATE 4 of 6, so PARENT should repair more — but it is not guaranteed. **The
   acceptance policy is reused byte-identical and is not relaxed.** If the run records a repair-loop
   regression, that is the measured result.
2. A repaired `PASS` costs two generation calls, so its `time_to_passing_patch_ns` is roughly double
   a first-shot `PASS`. A variant that repairs its way to a pass will look *slower* than one that
   passes immediately, and `minimum_time_improvement_ppm: 50000` will not be met by it. **This is
   correct.** Time to a passing patch is the primary metric precisely because it prices repair.

**The C4 gate consumes neither.** It consumes `repair_recovery_paired_count` only (section 1.4). The
C6 acceptance verdict is recorded alongside as secondary evidence and is explicitly not a claim.

### 3.8 Validation order

First applicable row wins. Rows 1–9 run before any provider call or any workspace mutation.

| # | Check | Failure |
| --- | --- | --- |
| 1 | Result/row/expected-input container versions agree; every row's version equals the container's | `INVALID_INPUT` / `SCHEMA` |
| 2 | Scope, corpus, task manifests, repair template, generation policy, provider control, acceptance policy, environment policy decode; every declared digest recomputes | `INVALID_INPUT` / `DIGEST` |
| 3 | `FILE_SET` manifest membership and per-file mode/length/digest verify beneath the corpus root | `INVALID_INPUT` / `SOURCE` |
| 4 | `maximum_repair_loops` is in `0..=64`; the corpus's value is `0` or `1`; a value above 1 is rejected by this capability | `INVALID_INPUT` / `REPAIR_BOUND` |
| 5 | The repair template decodes, is UTF-8, is non-empty, and its digest equals the task manifest's `repair_template_sha256` | `INVALID_INPUT` / `TEMPLATE` |
| 6 | `generation_policy.max_prompt_bytes >= ` the template's own byte length plus the fixed section headers | `INVALID_INPUT` / `TEMPLATE_BUDGET` |
| 7 | Workspace preflight, environment identity, snapshot requests — unchanged | as today |
| 8 | The `PROVIDER_SERVICE_PROBE` document is present, decodes, and matches `provider_service_revision` | `ERROR` / `PROVIDER_IDENTITY` |
| 9 | Prompt rendering and generation-request identity for attempt 1 — unchanged | as today |
| — | *attempt 1 runs* | |
| 10 | The adapter result decodes as `TASK_MEASUREMENT` v1, and — **only when the task's `maximum_repair_loops >= 1`** — with `repair_loop_count == 0` (deviation 1; enforced identically by `scripts/prompt-gate-validator.py` and `src/prompt_score.align`) | `ERROR` / `ADAPTER` |
| 11 | The evaluator's independently rendered prompt digest equals the adapter's `rendered_prompt_sha256` | `ERROR` / `ADAPTER` |
| 12 | If `status != FAIL`, or `maximum_repair_loops == 0`: the row closes with one attempt | — |
| 13 | Repair inputs are available: at least one of `measurement.diagnostic_summary`, `diagnostic_stdout`, `diagnostic_stderr` is non-empty, and attempt 1's cleanup and containment both passed | attempt 2 `SKIPPED` / `REPAIR_INPUT_UNAVAILABLE` |
| 14 | The assembled repair prompt is valid UTF-8 and `<= max_prompt_bytes` after the section-drop ladder of 4.3 | attempt 2 `SKIPPED` / `REPAIR_PROMPT_BUDGET` |
| 15 | The repair prompt is byte-equal to `assemble(template, attempt 1's persisted fields)` — the section 4.4 re-derivation, run by the producer against its own output | `ERROR` / `REPAIR_RENDER` |
| — | *attempt 2 runs; rows 10 and 11 repeat for it* | |
| 16 | `attempt_index` is dense and ascending from 1; exactly one `INITIAL`, at most one `REPAIR` | `INVALID_INPUT` / `ATTEMPT_ORDER` |
| 17 | `row.repair_loop_count` equals the count of non-`SKIPPED` `REPAIR` attempts, and `<= maximum_repair_loops` | `POLICY_VIOLATION` / `REPAIR_LOOPS` |
| 18 | `row.measurement` is byte-equal to the final attempt's measurement | `INVALID_INPUT` / `MEASUREMENT_BINDING` |
| 19 | The section 3.6 sums are exact, within bounds, and `None`/`Some` agrees with the §5.2 state machine | `INVALID_INPUT` / `TIMING` |
| 20 | One `PROMPT_EXPECTED_INPUT_DIGEST` per attempt: no duplicate, missing, or extra identity | `INVALID_INPUT` / `EVIDENCE_BINDING` |
| 21 | Every attempt that ran carries all four trace digests, and a `SKIPPED` attempt carries none of them | `INVALID_INPUT` / `SCHEMA` |
| 22 | Each of the four resolves to **exactly one** persisted record of that row's task; before and after are the same observation; both are closed over the resolved request; the input snapshot is that task's and carries the snapshot's own artifact digests | `INVALID_INPUT` / `SCHEMA` |
| 23 | `input_snapshots` is bounded by the run's **invocation** count, not its row count | `INVALID_INPUT` / `SCHEMA` |

Rows 12, 13, and 14 are terminal-but-not-error: the row closes with a recorded `SKIPPED` repair
attempt carrying its reason. A skipped repair is a measured outcome; it never becomes a silent
single-attempt row.

### 3.9 Ownership, allocation, lifetime, cleanup

| Surface | Exact contract |
| --- | --- |
| Attempt workspaces | Each attempt receives its own workspace and result path. Attempt 2 never reuses attempt 1's workspace; `run-coding-task.py` builds a fresh pinned checkout regardless, and a shared workspace would make the second attempt's containment claim depend on the first attempt's cleanup. |
| Path naming | Run-local paths carry a fixed-width `-a1` / `-a2` attempt suffix on a fixed-depth run directory. Component length is bounded and asserted; no attempt index, task id, or digest is concatenated into an unbounded name. Prior incident class: `ENAMETOOLONG` (section 5.6). |
| Cleanup order | Attempt 1's workspace, adapter child, and sealed inputs are released before attempt 2 is prepared, on both the pass and fail paths. A cleanup failure in attempt 1 is `ERROR`/`CLEANUP` and **suppresses attempt 2**: the repair attempt is recorded `SKIPPED`/`REPAIR_INPUT_UNAVAILABLE`, because a run that could not prove it cleaned up cannot prove the next attempt was contained. |
| Retained strings | The repair prompt is assembled from the already-materialized, already-bounded strings of attempt 1's persisted measurement. Nothing borrows the adapter's process output after its handle is released. |
| Align side | The evaluator's Align consumers decode version-2 documents into owned records with the existing bounded-persistence discipline; the `attempts` list is a bounded slice whose length is checked against `1 + maximum_repair_loops` before allocation. |
| Credentials | Unchanged. `credential_env_name` is never rendered, never logged, and never enters a repair prompt. `LOCAL_OPENAI` uses no credential; the redaction path (`redact_credential`) is reused, not re-implemented. |

### 3.10 The evaluator source pin and its size window

| Surface | Exact contract |
| --- | --- |
| `EVALUATOR_SOURCE_SHA256` | `src/prompt_evaluate.align:8` is updated to the new `scripts/prompt-evaluate.py` digest in the same commit that changes the file. A stale pin is a hard `INVALID_INPUT` at launch, so the two never drift. |
| Size window | `src/prompt_evaluate.align:163-166` admits `EVALUATOR_ARG_CHUNK_BYTES * 2 < len <= EVALUATOR_ARG_CHUNK_BYTES * 3`, i.e. 131,073…196,608 bytes. The file is 185,093 bytes, so the whole addition has **11,515 bytes** of headroom. |
| If the budget is exceeded | `EVALUATOR_ARG_CHUNK_BYTES * 3` becomes `* 4` (262,144 bytes) in `src/prompt_evaluate.align`, and the chunked-argument launch path is exercised at the new chunk count by an owner test. This is a public change to the evaluator launch contract, recorded here **before** implementation rather than discovered at the end. |
| What is not acceptable | Splitting the evaluator into a second file to dodge the window. The pin exists so that exactly one reviewed byte sequence runs; a helper module beside it would be an unpinned second producer. |

### 3.11 Ledger dimensions

| Dimension | Answer |
| --- | --- |
| Exact commands and operands | Section 3.1 (no new flag, no new environment variable); section 5.1 (owners); section 5.2 (the gate command) |
| Inputs and defaults | Section 3.4 (corpus assets and their exact values); `maximum_repair_loops` default stays 0, so `canonical-v1` behaviour is unchanged |
| Results, statuses, errors, precedence | Section 3.2 (`attempt.status`, `skip_reason`); section 3.8 (20-row first-applicable ladder) |
| Ownership, lifetime, allocation, cleanup | Section 3.9 |
| Text and wire boundary | Canonical UTF-8 JSON, declaration order, integer-only comparisons. Repair-prompt truncation is UTF-8-safe at a character boundary and never splits a code point (section 4.3) |
| Persisted/cache identity | `artifact_kind` + `schema_version` nominal; `content_sha256` over the canonical preimage with only the record's own digest field blanked (the existing non-circular pattern). No cache is introduced |
| Schema version | `PROMPT_TASK_ROW` 1→2, `PROMPT_EVALUATION_RESULT` 1→2, `PROMPT_EXPECTED_INPUT_DIGEST` 1→2. New records `TASK_ATTEMPT_RECORD`, `REPAIR_PROMPT_SOURCE`, `REPAIR_PROMPT_TEMPLATE`, `PROVIDER_SERVICE_PROBE` at 1. `TASK_MEASUREMENT`, `PROMPT_EVALUATION_TASK`, `TASK_ADAPTER_REQUEST`, `PROMPT_SCOPE`, `GENERATION_POLICY`, `EVALUATION_PROVIDER_CONTROL`, `PROMPT_ACCEPTANCE_POLICY`, `ENVIRONMENT_POLICY`, `ENVIRONMENT_IDENTITY` unchanged |
| Validation order | Section 3.8, rows 1–20 |
| Prerequisites | Section 5.5 |
| CLI, build, and environment inputs | Section 3.1: no new flag, no new environment variable. The evaluator reads exactly one environment value today (the provider credential) and continues to. Build inputs change only through section 3.10's pin and window. |
| Source pin and size window | Section 3.10 |
| Acceptance evidence | Section 5.1 (owner tests, no provider), section 5.2 (the named gate qualification) |
| Metrics | Section 5.3 |
| Cost ceiling | Section 5.2 |
| Minimum tool/platform versions | Docker 28.5.1; a Linux aarch64 evaluation image with `bwrap`, `prlimit`, `git`, `socat`; llama.cpp build 10566 (`bb4caa754`); Align `3a34febe912db5096c58c74fede36ff53f223e04` per `.align-revision` |
| Milestones not consuming a later slice | Sections 1.3 and 5.4: one repair, three tasks, no memory feedback, no policy change, no provider change |
| Runtime-inspection fields | `adapter_elapsed_ns`, `repair_preparation_ns`, `adapter_overhead_ns`, and every count are producer-owned measured values; no reflection, no artifact re-read at report time |

**Ledger field completion.** Cache identity is `N/A`: this capability introduces no cache, memoizes
nothing between attempts, and deliberately does not reuse attempt 1's workspace or checkout.
Generic monomorphization, compiler-interface serialization, and native ABI are `N/A`: the changed
records are concrete and no `extern` symbol, FFI boundary, or compiler surface is touched.
Concurrency and shared-process state are `N/A`: attempts are strictly sequential within a row and
rows are sequential within the run, exactly as today; the only shared resource is the single
`llama-server`, whose serialization is the server's own and is unchanged from C6. Platform-local
performance claims are `N/A`: section 5.3 makes no speed claim, so no native platform profile is
selected by this capability. The `ppm`-floor rule of `docs/specs/c8-speed-first.md` §1 is `N/A`
because no seam is optimized and nothing is claimed to get faster; the cost ceiling recorded in
section 5.2 is a **run-cost** ceiling under the performance row's "cost ceiling recorded before
implementation" clause, not an optimization ceiling.

---

## 4. The repair-prompt content contract

### 4.1 Principle

The repair prompt must be a **pure, total function of bytes that the result document already
persists**, plus one sealed corpus template. If it is not, then attempt 2's rendered prompt is an
un-auditable artifact of a nondeterministic run and the `GenerationRequestIdentity` coverage
argument that `c6-prompt-context-optimizer.md` §9 protects is lost.

This is achievable because the adapter already redacts and bounds everything the repair needs:
`diagnostic_stdout` and `diagnostic_stderr` at `DIAGNOSTIC_LIMIT = 16_384` bytes each,
`diagnostic_summary` at `SUMMARY_LIMIT = 4_096`. The repair prompt consumes those **exact persisted
strings** — never the adapter's pre-truncation output, never a re-read of a workspace file, never a
freshly captured stream.

### 4.2 The sealed template

`eval/prompt/canonical-v1r/repair-template.json`, `REPAIR_PROMPT_TEMPLATE`, `schema_version: 1`,
fields `template_id`, `preamble_text`, `section_headers` (one fixed header string per section kind),
`closing_text`, `content_sha256`. Its digest is pinned in each `prompt-v1r` task manifest and is a
member of the new file-set manifest, so it is digest-verified exactly like a task prompt.

The preamble states, in English: that the previous attempt's edits failed the repository's own
validation; that the response format is unchanged (one `FILE: <repo-relative-path>` header per
edited file followed by a fenced block holding that file's complete new content); that only the
files named in the task's allowed-edit set may be changed; and that the smallest change that makes
the validation pass is wanted. The closing text repeats the format instruction, because it is the
instruction the model is most likely to drop under a long diagnostic.

The task prompt and the variant's base and repo prompts are rendered **byte-identically to attempt
1** and precede the repair sections. The candidate variant's `learned_prompt_append` and its canned
`context_sources` sections are also rendered identically; the repair sections are appended, not
substituted. So the repair prompt is a strict textual extension of the attempt-1 prompt, which makes
the two attempts' inputs directly diffable in evidence.

### 4.3 Sections, order, and bounds

Fixed order. Each section is emitted only if its source is non-empty. Every source is a field of
attempt 1's persisted `TASK_MEASUREMENT`; nothing is re-captured, re-read, or re-truncated.

| # | Section | Source | Bound |
| --- | --- | --- | --- |
| 1 | `STATUS` | attempt 1's `measurement.status`, `failure_kind`, `build_status`, `test_status`, one label per line | 128 |
| 2 | `SUMMARY` | attempt 1's `measurement.diagnostic_summary` — this is the section that names the edited files | 4,096 (already bounded by `SUMMARY_LIMIT`) |
| 3 | `STDOUT` | attempt 1's `measurement.diagnostic_stdout` | 16,384 (already bounded by `DIAGNOSTIC_LIMIT`) |
| 4 | `STDERR` | attempt 1's `measurement.diagnostic_stderr` | 16,384 (already bounded by `DIAGNOSTIC_LIMIT`) |

There is no `EDIT_SET` section; section 2.6 records why, and section 5.4 records the resume
condition. The raw validation exit code is not a `TASK_MEASUREMENT` field either — the adapter maps
it to `PASS` / `TEST_FAIL` / `ERROR` — but the runner prints
`post-repair validation exit code: N` into its own stdout, so the number reaches the model inside the
`STDOUT` section without being invented at this layer.

Total assembled bytes must not exceed `generation_policy.max_prompt_bytes` = 65,536, which also
bounds attempt 1's prompt. The worst case is comfortably inside it: the four sections sum to at most
36,992 bytes on top of an attempt-1 prompt that already fits. When the assembly nonetheless exceeds
the budget, sections are dropped in this **fixed precedence**, one at a time, re-measuring after each
drop:

```text
STDOUT  ->  STDERR  ->  SUMMARY
```

`STATUS` is never dropped; it is at most 128 bytes and it is the single most load-bearing fact.
Dropping is whole-section, never partial: a half-truncated diagnostic stream would end mid-traceback
and invite the model to repair a failure it can only half see. Every dropped section is listed in
`repair_prompt_source.dropped_sections`. If the prompt still exceeds the budget with only the
preamble, headers, task prompt, and `STATUS`, the repair attempt is `SKIPPED` /
`REPAIR_PROMPT_BUDGET` and no provider call is made.

**`included_sections` and `dropped_sections` are not a partition of the four kinds.** `included` is
what the assembled prompt carries; `dropped` is what this ladder removed. A section whose source is
**empty** was never emitted and was never a drop candidate, so it appears in neither list — the
adapter produced nothing for it, and recording that as a "drop" would report a budget decision that
was never taken. The measured run shows the case: all four `layer-precedence-frozen-module` repairs
have an empty `diagnostic_stdout` and record `included_sections: [STATUS, SUMMARY, STDERR]` with
`dropped_sections: []`. A consumer asking "was this section available at all" must read
`attempt.measurement`; the two lists do not answer it. Re-derivation (section 4.4) is unaffected,
because it consumes `included_sections` and the measurement fields directly.

**Truncation is only ever a whole-section drop, never a byte cut**, so no UTF-8 code point is ever
split by this capability. The adapter's own UTF-8-safe truncation at 16,384 already happened before
these bytes were persisted, with redaction applied first — `bounded_diagnostic` in
`scripts/prompt-measurement-adapter.py` exists precisely to enforce "redact, then bound, never the
other way round", and this capability inherits its output rather than re-running either step.

### 4.4 Re-derivability, and what it buys

Given a persisted version-2 row and the sealed template, a verifier recomputes

```text
assemble(template,
         attempts[0].measurement.status, failure_kind, build_status, test_status,
         attempts[0].measurement.diagnostic_summary,
         attempts[0].measurement.diagnostic_stdout,
         attempts[0].measurement.diagnostic_stderr,
         included_sections, dropped_sections)
```

and requires the result's SHA-256 to equal `attempts[1].rendered_prompt_sha256` and
`attempts[1].generation_request.user_text_sha256`. Row 15 of section 3.8 makes the producer run this
against its own output; the evidence sidecar makes an independent producer run it again.

**Measurement-risk note.** This restores auditability but not independence-from-the-run. The repair
prompt's *content* is a function of the model's own attempt-1 output, so no verifier can derive it
from the frozen assets alone the way it can derive attempt 1's prompt. What stays independently
re-derivable from frozen bytes is the template, the section order, the bounds, the drop ladder, and
the assembly function; what is only *observed* is the attempt-1 output those inputs came from. The
sidecar therefore proves "this prompt is exactly what the recorded assembly of the recorded attempt
produced", not "this prompt was predictable before the run". That is the strongest statement
available for a reactive loop, and stating it is the point.

### 4.5 What never enters a repair prompt, and the one thing that does

**Never:** any environment-variable value; any credential or credential env name; the container
hostname, `host.docker.internal`, the endpoint, the model path, or any Docker or bind-mount detail;
the `PROVIDER_SERVICE_PROBE`; any path the evaluator constructs; any other task's fixtures or
diagnostics; any cross-sample or cross-variant content. The repair prompt sees exactly one attempt
of exactly one (task, sample, variant).

**One thing does, and pretending otherwise would be dishonest.** The persisted diagnostics already
contain a run-specific sandbox temp path. In the frozen C6 evidence,
`rows[0].measurement.diagnostic_stderr` contains verbatim

```text
File "/tmp/align-llm-coding-task-076agahm/repository/tests/test_duration.py", line 13, ...
```

That path is generated by `eval/runners/run-coding-task.py`'s `tempfile.TemporaryDirectory(prefix=
"align-llm-coding-task-")`, is not scrubbed anywhere, and is already inside the preimage of
`row.content_sha256` and therefore of the whole C6 gate chain. It is the residue of the earlier
incident that replaced a task-id-derived prefix with a safe constant one; the *prefix* was fixed and
the *mkdtemp suffix* was not.

This capability **inherits it rather than scrubbing it**, deliberately. Section 4.4's re-derivation
requires the repair prompt to be assembled from the persisted strings byte-for-byte; a scrubbing
pass here would make the prompt underivable from the row and would put a second, divergent copy of
the diagnostics in the evidence. The correct fix is upstream in the runner or the adapter, both
frozen (2.2). It is recorded as a deferral in section 5.4 and as a risk in section 5.6, and it is
disclosed here so no reviewer has to discover it in the evidence.

The residue is a temp directory name, not a secret: it contains no user path, no home directory, no
credential, and no host identity. It is a reproducibility wart, not a leak.

---

## 5. Fixtures, qualification, metrics, deferrals, risks

### 5.1 Owner tests — deterministic, offline, no provider

The narrow owners. None of these calls a provider; all are hosted-check candidates.

| Owner | Adds |
| --- | --- |
| `scripts/run-prompt-evaluate-smoke` | The attempt loop against the deterministic `scripts/prompt-fixed-adapter.py`: a fail-then-pass task (recovery), a fail-then-fail task (no recovery), a pass-first task (one attempt), a `maximum_repair_loops: 0` task (repair never offered), the three `SKIPPED` reasons, the section 3.8 ladder rows 1–20 one case each, the cleanup-failure suppression rule, and `ENAMETOOLONG`-adjacent path-length assertions |
| `scripts/run-prompt-score-smoke` | Version-2 row decode; version-1 row decode **unchanged**; mixed-version container rejection; the row-level vs measurement-level `repair_loop_count` selection; `REPAIR_LOOPS` at `repair_loop_count: 2` against `maximum_repair_loops: 1`; the new aggregates; `repair_recovery_paired_count` on all four sample patterns |
| `scripts/run-prompt-render-parity-smoke` | The section 4.4 re-derivation as a golden: fixed synthetic attempt-1 fields → an exact repair-prompt byte golden; each drop-ladder step as its own golden; the budget-exhaustion `SKIPPED` case; a redaction case proving no credential, endpoint, or evaluator-constructed path survives assembly |
| `scripts/run-prompt-gate-validator-smoke` | Version-2 evidence with one expected-input digest per attempt; duplicate/missing/extra attempt identity rejection; the new aggregates recomputed by `rescore`; the variant-symmetric `REPAIR_LOOPS` check; **and a regression asserting the frozen version-1 chain still validates and rescores byte-identically** |
| `make prompt-gate-check` | **Unchanged and must stay green.** Its passing is the machine-checkable proof that `canonical-v1`, `eval/prompt/gate/`, `run-coding-task.py`, and `prompt-measurement-adapter.py` were not moved. **It was not run on the implementing host** — it needs a source bundle and the Linux process-containment floor. Section 10.3 records the `N/A` and names the substitute evidence for each claim it would have carried; hosted CI owns the full proof |
| `make check`, `make fmt` | The Align side: `src/prompt_model.align`, `src/prompt_artifacts.align`, `src/prompt_score.align`, `src/prompt_evaluate.align` (the section 3.10 pin and window) |
| Row-bearing fixtures | **Narrowed during implementation, and recorded as deviation 18.** `src/prompt_verifier_smoke.align` is the single Align owner of every version-2 row case: it gains thirteen (`complete_result_v2` defects 0-12) and keeps its version-1 cases unchanged. `src/prompt_score_smoke.align` and `src/prompt_score_prefix_smoke.align` are unchanged and stay version-1 owners, because `prompt_score.verify_result` is the one entry point every version-2 rule is reached through, and duplicating the row fixtures across three Align smokes would have produced three copies of one assertion. `eval/fixtures/c6-prompt-state/templates.jsonl` is unchanged: it is a frozen version-1 fixture and deviation 11 records why the repair-template pairing rule is enforced at version 2 only, precisely so it stays frozen |

The version-1 back-compatibility cases are not optional politeness. `prompt-gate-check` re-decodes
the frozen version-1 evaluation with the *current* scorer; a version-2-only decoder deletes C6's
merged acceptance evidence.

### 5.2 The named qualification and its cost ceiling

```text
make c4-repair-gate \
  C4_REPAIR_SCOPE=eval/prompt/canonical-v1r/scope.json \
  C4_REPAIR_PROVIDER_PROBE=<absolute path to the PROVIDER_SERVICE_PROBE document> \
  C4_REPAIR_OUT=eval/prompt/c4-repair-gate/
```

A named focused qualification. **It does not join `make ci`, `hosted-checks`, or `capable-checks`**:
it requires a running `llama-server`, a 4.7 GB model, a Linux container, and tens of minutes. Adding
it to an aggregate would put a provider-dependent, model-dependent, tens-of-minutes step in the
routine path, which `CLAUDE.md`'s verification section forbids.

**Cost ceiling, recorded before implementation.** 12 rows; 12 initial attempts; at most 10 repair
attempts, since 10 of 12 rows fail at attempt 1 in the section 2.1 distribution. That is **at most
22 provider generation calls**. Against the only observed per-call figures — 23.40 s and 81.12 s —
the generation cost is 8.6 min at the fast figure and 29.7 min at the slow one. Validation adds at
most `2 × task.timeout_ns` = 60 s per attempt and typically a few seconds; preparation is 20 ms per
row in the frozen evidence.

```text
expected gate run time:  15-40 minutes wall clock
recorded cost ceiling:   60 minutes wall clock, single run, this host
per-attempt ceiling:     provider_control.timeout_ns = 1,800,000,000,000 ns (1,800 s)
per-attempt observed:    23.40 s - 81.12 s (n=2, section 2.1)
```

**If a run exceeds 60 minutes, the capability stops and the boundary is reconsidered** rather than
the ceiling being raised after the fact. The ceiling is recorded here, before implementation, and
the measured wall clock is recorded against it in the pull request.

The run records, in the C8 house form: the align-llm commit; `.align-revision`; the Docker image
digest and `docker version`; the forwarder command; the host `llama-server` version string, binary
SHA-256, and model SHA-256; the exact `make` command; the container's OS, kernel, architecture, and
logical CPU count; and the measured wall clock. `ENVIRONMENT_IDENTITY_CORE` continues to describe
the evaluation container, and the provider host facts live in `provider_service_revision`, so no new
environment record is needed.

### 5.3 Metrics, and what the measured claim is and is not

**Primary: `generation_to_passing_patch_ns`, including the repair attempt** — section 3.6's
evaluator-observed total. Reported per row, and as the median over rows that reached a pass.

**Secondary: `repair_recovery_paired_count`** — the section 1.4 gate quantity — with
`repair_attempt_count` and `repair_recovery_count` as its denominators.

**What this capability claims.** That the provider-backed measurement path can run a bounded model
repair attempt from its own diagnostics; that the attempt is measured, bounded, contained, and
re-derivable from persisted evidence; and, if the gate is `MET`, that at least one task recovered
from a first-attempt failure reproducibly across both paired samples.

**What it does not claim.** It makes **no speed claim of any kind.** Section 2.1's two samples of
one identical prompt differ by 3.5× at temperature 0; with `n=2` there is no baseline, no spread,
and no floor to clear, and section 3.6's totals are not comparable to the version-1 numbers anyway.
It makes **no prompt-quality claim**: the CANDIDATE variant is not asserted to be better, and the C6
acceptance verdict is recorded as secondary evidence only. It makes **no provider-quality claim**:
one model, one build, one host, one seed. It makes **no generality claim**: three tasks, one
repository family, one language.

If `repair_recovery_paired_count == 0`, the reported result is: the loop ran, N repair attempts were
made and measured, none recovered, and here are the realized repair prompts' digests, the realized
diagnostics, and each attempt's realized `patch_size_bytes`, status, and failure kind. **The
second-attempt edits themselves are not among them** — the patch lives only inside the frozen
adapter (2.6), so the row records its size and its outcome and not its content. That is a
**negative result about this model on these three tasks** and it is published as one; section 10.3
states which conclusions that evidence does and does not support.

### 5.4 Deferred surfaces

| Deferred | Reason | Resume condition |
| --- | --- | --- |
| **The failing edit set in the repair prompt** | The model's edits and the derived patch live only inside the adapter and are dropped when it returns; the adapter is a frozen corpus member (2.2, 2.6). This is the largest gap between this capability and the boundary it was asked to deliver | Section 5.7's option A or B, i.e. a capability that either re-freezes `canonical-v1` or adds a second reviewed corpus-member adapter. A `MET` gate without the edit set makes option B easier to justify; a `NOT_MET` gate makes it more urgent |
| Scrubbing the sandbox temp path out of persisted diagnostics | The residue originates in a frozen runner, and scrubbing at this layer would break section 4.4's re-derivation and duplicate the diagnostics (4.5) | The same re-freeze that unblocks the edit set; the fix belongs in `run-coding-task.py`'s output or the adapter's bounding, not in the evaluator |
| Measuring `prompt_preparation_ns` instead of the hard-coded `20_000_000` | A separate, pre-existing deviation from `c6-prompt-context-optimizer.md` §5.2 with its own owner; fixing it inside this diff would silently change every version-2 row total for an unrelated reason (2.1) | Its own capability, or the next change that already touches the evaluator's timing boundary for a stated reason |
| More than one repair attempt | Each extra attempt multiplies run cost by up to 81 s per row and reopens `c6-prompt-context-optimizer.md` §9's "exactly one bound provider generation call per sample" coverage argument, which this capability already stretches to two | A `MET` gate at one repair, plus a measured recovery rate that shows a second attempt would recover a task the first did not |
| Corpus expansion | Three tasks is the frozen corpus; a fourth is a new fixture, a new freeze, and a new baseline activation | A later Track A capability. No `C9` label exists in this repository today; if one is created it registers in `docs/specs/roadmap.md` §2 |
| Failure-memory feedback between attempts | C5 memory would make attempt 2's prompt depend on prior *runs*, destroying section 4.4's re-derivability from a single row | A design that persists the selected memory events into the attempt record so re-derivation still closes |
| A patch digest, or the patch body, in `TaskMeasurement` | Only `patch_size_bytes` is persisted, so "attempt 2 re-emitted attempt 1's patch" is an inference from equal sizes and identical observable failures, never a verified fact (section 10.3). `TASK_MEASUREMENT` is at `schema_version: 1` and is written by the frozen adapter, so adding a field there is the same frozen-corpus problem as the edit set itself | The same re-freeze or second reviewed adapter that unblocks the edit set. A digest is the cheap half and should land first: it costs one field and settles the question the `NOT_MET` result raised without carrying model output into evidence |
| Raising `maximum_repair_loops` above 1 in the corpus | Unenforced headroom no test can reach (section 3.4) | Multi-repair above |
| Relaxing `maximum_repair_loop_regression_count` | Weakening an acceptance policy to make a measurement look better is exactly backwards (section 3.7) | A design that shows the rule is wrong, not that a run failed it |
| Converging `src/repair.align` / `src/verification_loop.align` with this loop | Two loops now exist: an Align in-process loop with a scripted provider, and an evaluator cross-process loop with a real one. Merging them is a real capability, not a refactor | After this gate resolves either way; the answer may be that the Align loop becomes the provider-backed one |
| The `/proc` live-entry scan deferred in `c6-prompt-context-optimizer.md` §1.2 | Its resume condition names "the next capability that already pays for a frozen-corpus rebind". **This capability does not qualify**: it mints a *new* corpus and leaves `run-coding-task.py` byte-identical, precisely because moving that file would break `make prompt-gate-check` against C6's merged evidence (§2.2). The file still cannot move alone | Unchanged: a capability that genuinely re-freezes `canonical-v1`, or the next revision of the validation process budget |

Each deferral requires a new design review and an acceptance test tied to time to a passing patch or
another explicitly named metric.

### 5.5 Prerequisites

1. `llama-server` running on the host at `127.0.0.1:18080` with
   `~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf` served under the model id
   `qwen2.5-coder-7b-instruct-q4_k_m`. Started by the operator; this capability never starts it.
2. The model file present and matching the `model-sha256` frozen into
   `canonical-v1r/generation-policy.json`.
3. Docker 28.5.1 with a Linux aarch64 evaluation image carrying `bwrap`, `prlimit`, `git`, `python3`
   at `/usr/bin/python3`, and `socat`.
4. The container-local forwarder running before the evaluator starts.
5. The managed pinned toolchain at `.align-revision`
   `3a34febe912db5096c58c74fede36ff53f223e04`, materialized through `scripts/align-toolchain`.
6. `make prompt-gate-check` green at the candidate head, proving the C6 freeze intact.

No Align capability request is a prerequisite. This design consumes no unshipped Align surface; the
new records are ordinary bounded structs and slices of the kind `src/prompt_artifacts.align` already
declares. If implementation discovers a genuine gap it is filed in `docs/align-requests.md` under
the normal lifecycle and this section is updated — a workaround is not a reason to hide one.

### 5.6 Risks

| Risk | Prior class | Mitigation |
| --- | --- | --- |
| A machine-specific path or hostname reaches a persisted row through the repair prompt | temp paths in persisted rows | Partly accepted, and disclosed. `host.docker.internal` never appears because the endpoint stays a loopback address behind a forwarder (§3.5), and no evaluator-constructed path enters the prompt (§4.5, asserted by the render-parity smoke). The sandbox `mkdtemp` suffix already present in the frozen diagnostics **is** carried through, because scrubbing it would break §4.4's re-derivation; §4.5 states it, §5.4 defers the upstream fix |
| The evaluator addition does not fit its 11,515-byte window | new | §3.10 names the widening to four chunks as a ledger item decided **before** implementation, not a late patch; the budget is checked at each implementation checkpoint, not once at the end |
| An Align record cannot dispatch on version before decoding | new | §3.3's two-record contract; if the pinned surface cannot express a version peek, it is a genuine Align gap filed under `docs/align-requests.md`, not routed around with a permissive record |
| Per-attempt run paths overflow a path limit | `ENAMETOOLONG` | Fixed-width `-a1`/`-a2` suffixes on a fixed-depth run directory, bounded and asserted components (§3.9), with an owner-test assertion |
| A nanosecond total saturates or clamps | saturating ns conversions | Exact `i64` addition with an explicit pre-persist bound check that **errors rather than clamps** (§3.6) |
| The answering server is not the recorded server | provider drift | A host probe and an in-band model-id check, both fail-closed (§3.5), with the residual risk stated as a measurement-risk note rather than resolved |
| A model update silently changes behaviour | model regressions | `model-sha256` is frozen into the generation policy and checked before the run; a changed model is a new freeze, not a new run |
| Two samples of one prompt differ by 3.5× at temperature 0 | measurement risk | No speed claim is made (§5.3); the gate is a reproducibility predicate over both paired samples, not a timing threshold |
| A version-2-only decoder deletes C6's merged evidence | evidence loss | Version-1 decode is an explicit owner test in three smokes and `make prompt-gate-check` must stay green (§5.1) |
| The repair attempt makes the candidate look worse and flips the C6 verdict | acceptance coupling | The C4 gate does not consume the C6 verdict (§3.7); the acceptance policy is reused byte-identical and is not relaxed |
| The gate is `NOT_MET` and the work looks wasted | scope pressure | §1.4 and §5.3 fix the reporting for a negative before the run, so the result cannot be re-framed after seeing it |

### 5.7 The two rejected alternatives, and what would change the answer

Both would restore the failing edit set to the repair prompt. Both are rejected **for this
capability**, with reasons that are about cost and risk rather than principle.

**Option A — edit `scripts/prompt-measurement-adapter.py` and re-freeze `canonical-v1`.** The
adapter grows an internal attempt loop, `generation_to_passing_patch_ns` keeps exactly the §5.2
adapter-owned meaning, the edit set never leaves the process that produced it, and the timing
redefinition of section 3.6 disappears entirely. It is the cleanest design on the merits.

It is rejected because the cost is C6's evidence. Changing the adapter changes
`measurement_adapter_runtime` and `artifacts[].expected_sha256` in all three `prompt-v1` task
manifests, the `corpus-file-set.manifest` raw digest `15efa89e…`, `scope.json`'s
`corpus_revision.source_sha256`, `corpus.json`, `prompt-activation-baseline-v1.json`, and then the
entire gate bundle: `prompt-evaluation-improved.json` → its evidence sidecar → the accepted
activation → the rolled-back activation → `prompt-gate-manifest.json`. Every one of those is
**measured** evidence: re-freezing them means re-running the C6-MEASURED gate against a provider
that no longer exists (2.5) and calling the result C6's acceptance. `make prompt-gate-check` would
be permanently red against the merged evidence in the meantime.

**Option B — add a second corpus-member adapter, `scripts/prompt-repair-adapter.py`, in
`prompt-v1r` only.** `canonical-v1` keeps its 27 members and its digests; the new corpus names a new
adapter; the C6 gate stays green. It is rejected because that file would be a near-copy of 1,445
reviewed lines of sealed-input admission, retained-descriptor launch, `bwrap` orchestration,
credential redaction, and containment checking. A second copy of containment logic is a second place
for a containment bug, and `CLAUDE.md`'s "narrowest durable owner" rule points the other way.

**What would change the answer.** If the gate comes back `NOT_MET` and the realized attempt-2 edits
show the model repeating its attempt-1 mistake, that is direct evidence that the missing edit set is
the binding constraint, and option B becomes the obvious next capability — with the duplication paid
knowingly and the two adapters diffed in review. If the gate comes back `MET`, the diagnostics alone
were enough on this corpus and the deferral can stay closed.

---

## 6. Closure matrix

Construction, success, failure, malformed input, early exit, and cleanup for each affected module.
Each cell names its implementation and its regression. Cases are `scripts/run-prompt-evaluate-smoke`
unless marked **(S)** for `run-prompt-score-smoke`, **(R)** for `run-prompt-render-parity-smoke`,
**(G)** for `run-prompt-gate-validator-smoke`, or **(Q)** for the section 5.2 qualification.

### 6.1 `scripts/prompt-evaluate.py` — the attempt loop

| Cell | Required implementation | Exact regression or evidence |
| --- | --- | --- |
| Construction | Per-row attempt list, per-attempt workspace and result path, `TaskAttemptRecord` assembly in declared field order | `attempt-record-order`, `attempt-workspace-distinct` |
| Success | Attempt 1 `PASS` closes the row with one attempt; attempt 1 `FAIL` then attempt 2 `PASS` closes with two and `repair_loop_count: 1` | `attempt-pass-first`, `attempt-repair-recovers` |
| Failure | Attempt 1 `FAIL` then attempt 2 `FAIL`: two attempts, `repair_loop_count: 1`, both time fields `None` | `attempt-repair-fails` |
| Malformed input | Adapter result not `TASK_MEASUREMENT` v1; `repair_loop_count != 0` from the adapter; rendered-prompt digest mismatch; mixed-version container | `attempt-adapter-schema`, `attempt-adapter-repair-count`, `attempt-digest-mismatch`, `attempt-mixed-version` |
| Early exit | `maximum_repair_loops: 0` offers no repair; the three `SKIPPED` reasons each stop before a provider call; ladder rows 1–9 stop before any workspace mutation | `attempt-no-repair-offered`, `attempt-skip-budget`, `attempt-skip-inputs`, `attempt-skip-cleanup`, `ladder-01` … `ladder-09` |
| Cleanup | Attempt 1's workspace, child, and sealed inputs release before attempt 2 on both paths; an attempt-1 cleanup failure suppresses attempt 2 | `attempt-cleanup-order`, `attempt-cleanup-suppresses-repair` |
| Timing | Section 3.6 sums exact and bounds-checked; `None` agrees with the state machine; `adapter_overhead_ns` present exactly on `PASS` | `attempt-timing-sum`, `attempt-timing-bound`, `attempt-timing-none`, `attempt-overhead-presence` |
| Paths | Fixed-width attempt suffix; bounded components | `attempt-path-length` |

### 6.2 Repair-prompt assembly — `scripts/prompt-evaluate.py`

| Cell | Required implementation | Exact regression or evidence |
| --- | --- | --- |
| Construction | Template decode, digest check, fixed section order, `RepairPromptSource` assembly | `repair-template-decode` (R), `repair-sections-order` (R) |
| Success | Byte golden for the full five-section prompt from fixed synthetic attempt-1 fields | `repair-prompt-golden` (R) |
| Failure | Template missing, wrong kind, wrong version, digest mismatch, non-UTF-8 | `repair-template-*` (R) |
| Malformed input | All three diagnostic strings empty; a status/failure-kind pair the state machine forbids; a diagnostic string that is not valid UTF-8 | `repair-input-empty` (R), `repair-input-status` (R), `repair-input-utf8` (R) |
| Early exit | Each drop-ladder step as its own golden; budget exhaustion yields `SKIPPED`/`REPAIR_PROMPT_BUDGET` with no provider call | `repair-drop-stdout`, `repair-drop-stderr`, `repair-drop-summary` (R), `repair-budget-exhausted` (R) |
| Cleanup | Assembly allocates only from persisted strings and holds no process handle | covered by `attempt-cleanup-order` |
| Re-derivation | Ladder row 15 recomputes the prompt against the producer's own output; the sidecar recomputes it independently | `repair-rederive-self` (R), `repair-rederive-sidecar` (G) |
| Redaction | No credential, endpoint, hostname, env value, or evaluator-constructed path survives assembly; the inherited sandbox temp path is asserted **present**, so the §4.5 disclosure cannot rot into a silent scrub | `repair-redaction` (R), `repair-inherits-sandbox-path` (R) |

### 6.3 `src/prompt_score.align`, `src/prompt_model.align`, `src/prompt_artifacts.align`

| Cell | Required implementation | Exact regression or evidence |
| --- | --- | --- |
| Construction | The version-2 members of `PromptTaskRow` as `Option` (deviation 10 — **not** a `PromptTaskRowV2` twin), `TaskAttemptRecord` including its four trace digests, `RepairPromptSource`, `AttemptKind`, `AttemptStatus`, `SkipReason` declarations, version-dispatched decode (§3.3), label mappings, canonical digests | `score-attempt-records` (S), `score-version-dispatch` (S), `score-label-map` (S) |
| Success | Version-2 decode and score; version-1 decode **byte-identical to today**, including a rescore of the frozen gate evidence | `score-v2-decode` (S), `score-v1-unchanged` (S), `score-frozen-rescore` (G) |
| Failure | `REPAIR_LOOPS` at `repair_loop_count: 2` against `maximum_repair_loops: 1`, for **both** variants; repair-loop regression counted unchanged | `score-repair-loops-candidate` (S), `score-repair-loops-parent` (S), `score-repair-regression` (S) |
| Malformed input | Mixed-version container; non-dense `attempt_index`; two `INITIAL`; two `REPAIR` that ran; `row.measurement` not equal to the final attempt's; `attempts` longer than `1 + maximum_repair_loops`; an attempt that ran attesting no trace record; a trace digest that resolves to no record; a persisted trace record nothing references | `score-attempt-*` (S) |
| Early exit | First-applicable ladder order preserved; a version-1 row never consults version-2 fields | `score-ladder-order` (S), `score-v1-no-v2-fields` (S) |
| Cleanup | Bounded slice allocation checked before use; owned records outlive their input buffer as today | `score-attempt-lifetime` (S) |
| Aggregates | Task and corpus repair aggregates recomputed by the pure verifier, never trusted from the document | `score-aggregate-recompute` (S), `score-recovery-paired` (S) |

### 6.4 Corpus assets and the frozen C6 chain

| Cell | Required implementation | Exact regression or evidence |
| --- | --- | --- |
| Construction | The 9 new `canonical-v1r` / `prompt-v1r` files; the 29-entry file-set manifest | `corpus-v1r-manifest` (G) |
| Success | The new scope resolves, every digest recomputes, the baseline activation binds | `corpus-v1r-scope` (G) |
| Failure | A `prompt-v1r` task with `maximum_repair_loops: 2` is rejected by ladder row 4 | `corpus-v1r-repair-bound` (G) |
| Malformed input | A manifest entry whose digest disagrees with the working tree | `corpus-v1r-digest-drift` (G) |
| Early exit | Source verification precedes every adapter and snapshot call, unchanged | inherited, `prompt-gate-source-bundle-smoke` |
| Cleanup | N/A: frozen assets are read-only inputs with no lifecycle | — |
| **Non-mutation** | `canonical-v1`, `eval/prompt/gate/`, `eval/tasks/prompt-v1/*.json`, `run-coding-task.py`, and `prompt-measurement-adapter.py` are byte-identical, and the shared members carry the **same digests** in both manifests | `make prompt-gate-check` green; `git diff --stat` over those paths empty; `corpus-v1r-shared-digests` (G) |

### 6.5 Provider topology

| Cell | Required implementation | Exact regression or evidence |
| --- | --- | --- |
| Construction | `scripts/probe-provider-service` emits `PROVIDER_SERVICE_PROBE` | `provider-probe-shape` |
| Success | Probe matches the policy; the in-band model id matches | (Q) |
| Failure | Version string, binary digest, model digest, or model id mismatch fails closed | `provider-probe-mismatch` × 4 |
| Malformed input | Probe missing, unreadable, wrong kind, wrong version | `provider-probe-malformed` |
| Early exit | Ladder row 8 stops before attempt 1's provider call | `ladder-08` |
| Cleanup | The forwarder is external to the evaluator and is not owned, started, or stopped by it | recorded in (Q)'s run record |

### 6.6 Error-code-to-case map, and the final pass

Every code introduced by section 3.8 — `SCHEMA`, `DIGEST`, `SOURCE`, `REPAIR_BOUND`, `TEMPLATE`,
`TEMPLATE_BUDGET`, `PROVIDER_IDENTITY`, `ADAPTER`, `REPAIR_INPUT_UNAVAILABLE`,
`REPAIR_PROMPT_BUDGET`, `REPAIR_RENDER`, `ATTEMPT_ORDER`, `REPAIR_LOOPS`, `MEASUREMENT_BINDING`,
`TIMING`, `EVIDENCE_BINDING` — has exactly one owning case above, and the smoke asserts coverage in
**both directions**: every declared code is reached by some case, and no case reaches an undeclared
code. Before review, the matrix-to-diff pass replaces each planned case name with its actual file
and line, or records an explicit deferral in this document. **That pass is section 9.2**; the case
names in the tables above are the plan's, and 9.2 is where each one is bound to the file and line
that actually carries it, or to its deferral.

---

## 7. Author consistency pass

One pass, ledger against prose, performed before this document was finished.

1. **`maximum_repair_loops` is 0 today, not 4.** The task brief for this design assumed a standing
   ceiling of 4. All three `eval/tasks/prompt-v1/*.json` set `0`; the structural ceiling is 64
   (`src/prompt_score.align:274`); no file in the repository sets 4 outside an Align smoke fixture
   string. Sections 1.1, 3.4, and 5.4 record the real values and why the new corpus sets exactly 1.
2. **The frozen corpus cannot be edited, so the adapter cannot be edited.** Sections 2.2 and 3.1
   agree: the loop is evaluator-owned because `scripts/prompt-measurement-adapter.py` is a
   digest-verified corpus member. Section 6.4's non-mutation cell is the machine check.
3. **`generation_to_passing_patch_ns` is redefined, and it is said once.** Section 3.6 states the
   redefinition, its reason, and its incomparability with section 2.1's frozen numbers; section 5.3
   repeats the incomparability as a non-claim; no other section implies the two are comparable.
4. **`repair_loop_count` has one producer per version.** Section 3.3 is authoritative; sections 3.2,
   3.7, 3.8 row 17, and 6.3 all defer to it and none introduces a second writer.
5. **The C4 gate and the C6 acceptance verdict are separated everywhere.** Sections 1.4, 3.7, and
   5.3 each state it; no aggregate, ladder row, or matrix cell makes the C4 gate depend on
   `status` or `gate_eligible`.
6. **No new environment variable exists.** Section 3.1's claim is checked against
   `eval/prompt/gate/environment-policy.json`, which admits exactly five variables and is reused
   byte-identical; section 3.5's forwarder is external to the evaluated process tree.
7. **Every cost figure traces to a probe.** 23.40 s / 81.12 s to section 2.1; 22 calls to section
   2.1's 10-of-12 failure distribution; 1,800 s and 30 s to `evaluation-provider-control.json` and
   the task manifests; the provider digests to section 2.5.
8. **Every mandatory ledger dimension is answered or `N/A` with a reason.** Section 3.10 and its
   completion paragraph.
9. **Sections 1.3 and 5.4 do not overlap.** 1.3 lists what this capability does not do; 5.4 lists
   what a later one might, with a resume condition each.
10. **The `/proc` deferral is addressed rather than inherited silently.** Section 5.4's last row
    states why this capability does not discharge `c6-prompt-context-optimizer.md` §1.2's resume
    condition.
11. **The edit set is absent everywhere it was once assumed present.** Sections 1.2, 1.3, 2.6, 4.3,
    4.4, 5.4, 5.7, and 6.2 all describe a four-section, diagnostics-only repair prompt; no field,
    section, ladder row, golden, or matrix cell refers to `candidate_edits_text` or an `EDIT_SET`
    section. The narrowing is stated in the summary (1.1), the scope (1.2), the probe record (2.6),
    and the deferral table (5.4), and the alternatives are priced in 5.7.
12. **Every field named in section 3.2 is reachable.** `TASK_MEASUREMENT`'s 21 fields were checked
    one by one against the attempt record; `validation_exit_code` was removed because the adapter
    maps the exit code to `PASS`/`TEST_FAIL`/`ERROR` and never persists the number, and section 4.3
    says where the number does reach the model instead.
13. **The two-hour ceiling is the existing one, not a new one.** Section 3.6 uses
    `7_200_000_000_000` ns as both implementations already enforce it, rather than the invented
    per-attempt formula an earlier draft carried.
14. **The evaluator size budget is a ledger item, not a footnote.** Sections 2.7, 3.10, 3.11, and
    5.6 agree on 185,093 bytes, 11,515 bytes of headroom, and the four-chunk widening as the named
    escape.
15. **Diagnostics have exactly one home per attempt.** An earlier draft duplicated
    `diagnostic_summary`, `diagnostic_stdout`, `diagnostic_stderr`, and `patch_size_bytes` beside the
    attempt's measurement, creating a second writer for fields section 3.3 says have one. They are
    now read through `attempt.measurement.*` everywhere — sections 3.2, 3.3, 3.8 row 13, 4.3, and
    4.4 — and the only deliberate duplication left is one whole `TaskMeasurement` between
    `attempts[k]` and `row.measurement`, which ladder row 18 asserts is byte-equal.
16. **`SKIPPED` is fully specified.** Section 3.2 fixes which fields a skipped attempt carries,
    section 3.8 rows 12-14 fix when it occurs, section 3.7 excludes it from `repair_loop_count`, and
    section 6.1 names a case per reason.

---

## 8. Reconciliation drafts

**Applied.** These were drafts while this document was design-only; the capability that implements
the plan applied all three, so each block below is kept only as the record of what was drafted.
The shipped text is authoritative and is not here:

- section 8.1 shipped as `docs/specs/roadmap.md` item 31 and the `## C4: Verification Loop`
  addition, both rewritten against the measured result;
- section 8.2's `HANDOFF.md` section was superseded before it was ever applied — the draft below
  describes a design-only branch, and the branch has since implemented, run, and published the
  gate. `HANDOFF.md` at head is the record;
- section 8.3 shipped in `docs/align-development.md`.

### 8.1 `docs/specs/roadmap.md` — new forward-order item 31

Items 27 through 30 are being added on other branches. This entry assumes 29 and 30 land first and
takes 31; the number is corrected at reconciliation if that changes.

```markdown
31. **C4-REPAIR-MEASURED — one bounded model repair attempt in the provider-backed measurement
    path.** The first Track A capability since the C6-MEASURED wave, and the one that closes C4's
    roadmap gate with a model instead of a scripted patch. On branch `agent/c4-repair-measured` off
    `main` `3df063b`. [`c4-repair-measured.md`](c4-repair-measured.md) is the authoritative plan and
    owns the contract ledger, closure matrix, repair-prompt contract, cost ceiling, and gate
    statement; the design gate triggered on the `PROMPT_TASK_ROW` schema-2 per-attempt identity, a
    new frozen corpus scope, and a coordinated invariant across `scripts/prompt-evaluate.py`,
    `src/prompt_score.align`, and the corpus assets. After a first-attempt validation `FAIL`, the
    evaluator renders a repair prompt from the run's **own** redacted validation diagnostics, calls
    `prompt generate` a second time, and validates again;
    `generation_to_passing_patch_ns` then includes the repair, as C6 §5.2 has always contracted and
    never exercised. The repair prompt carries the failing attempt's status, summary, stdout, and
    stderr but **not its edit set**: the model's output lives only inside the adapter and is dropped
    when it returns, so a diagnostics-driven second attempt is what an evaluator-owned loop can
    deliver without breaking the freeze. That narrowing, and the two ways to lift it, are recorded in
    the plan. **The adapter and the validation runner are byte-identical**: both are frozen
    `FILE_SET` members of `canonical-v1`, so the loop is evaluator-owned and the corpus is a new
    freeze, `eval/prompt/canonical-v1r/` over the same three tasks with `maximum_repair_loops: 1`.
    `make prompt-gate-check` staying green is the machine-checkable proof that C6's merged evidence
    was not disturbed. The gate: on 3 tasks × 2 variants × 2 paired samples at temperature 0 and
    `PAIRED_FIXED`, at least one (task, variant) pair fails at attempt 1 and passes at attempt 2 in
    **both** samples. Ten of the twelve frozen C6 rows fail at attempt 1, so the arm is substantial.
    **A measured negative is a published result, not a hidden one.** No speed claim is made: the two
    C6 timings for one identical prompt at temperature 0 differ by 3.5× (81.12 s and 23.40 s), so
    `n=2` supports no baseline. Recorded run-cost ceiling 60 minutes, expected 15-40. Multi-repair,
    corpus expansion, failure-memory feedback, and converging the Align `verification_loop`/`repair`
    modules with this loop are deferred with resume conditions.
```

The Track A `## C4: Verification Loop` section gains, after its `### Gate` block:

```markdown
### First measured consumer: C4-REPAIR-MEASURED

C4's gate was met in mechanism by `make verify-loop-smoke`, whose repair patch is a checked-in
deterministic input rather than a model. `docs/specs/c4-repair-measured.md` is the authoritative
plan for meeting it with a real provider on the C6 measurement path. It is provider-independent —
no provider module changes — and it does not modify `src/repair.align` or
`src/verification_loop.align`; converging the two loops is a named deferral in that document.
```

### 8.2 `HANDOFF.md` — replacement "Active" section

**Obsolete draft, kept as a record.** It was written when the branch was design-only. Every
"will do" below has been done, next action 1 through 5 are complete, and item 4's
`make prompt-gate-check` was **not** run — section 10.3 records that and names the substitute
evidence. Read `HANDOFF.md` at head instead.

```markdown
## Active: C4-REPAIR-MEASURED (2026-08-29)

Branch `agent/c4-repair-measured`, based on `main` `3df063b`. **Design only.** The single commit is
the design ledger `docs/specs/c4-repair-measured.md`; nothing is implemented, no provider run has
happened, and no corpus asset exists yet. Track A re-entry after the Track B R-wave.

**What it will do.** One bounded model repair attempt in the provider-backed measurement path.
After a first-attempt validation `FAIL`, `scripts/prompt-evaluate.py` renders a repair prompt from
that attempt's own redacted validation diagnostics, calls `prompt generate` a second time, validates
again, and records per-attempt identity and timing in `PROMPT_TASK_ROW` at `schema_version: 2`. Cap
is one repair; the new corpus sets `maximum_repair_loops: 1` so the manifest itself is the cap.

**Two constraints found during design, both in the plan's ledger.** (1) The failing **edit set
cannot be in the repair prompt**: the model's output lives only inside the frozen adapter and is
dropped when it returns, so this is a diagnostics-driven second attempt. Spec §2.6 records the
narrowing, §5.4 the deferral, §5.7 the two ways to lift it and why neither is taken now. (2)
`src/prompt_evaluate.align` pins `scripts/prompt-evaluate.py` byte-exactly **and** bounds its length
to 131,073…196,608 bytes; the file is 185,093, so the whole addition has **11,515 bytes** of
headroom or the window widens to four chunks. Spec §3.10.

**The constraint that shaped it.** `scripts/prompt-measurement-adapter.py`,
`eval/runners/run-coding-task.py`, and the three `eval/tasks/prompt-v1/*.json` manifests are
digest-verified members of `eval/prompt/canonical-v1/corpus-file-set.manifest`, which
`make prompt-gate-check` verifies against the **current head's bytes**. Editing any of them breaks
the merged C6-MEASURED gate. So the repair loop is evaluator-owned, the adapter and runner stay
byte-identical, and the corpus is a new freeze at `eval/prompt/canonical-v1r/` over the same three
tasks and the same fixtures. `make prompt-gate-check` staying green is the acceptance evidence for
non-mutation.

**Gate.** 3 tasks × 2 variants × 2 paired samples, temperature 0, `PAIRED_FIXED`: at least one
(task, variant) pair fails at attempt 1 and passes at attempt 2 in both samples. Ten of the twelve
frozen C6 rows fail at attempt 1. A measured negative is published as a result.

**Provider topology, decided.** Validation stays in `bwrap` inside a Linux aarch64 Docker container
(Docker 28.5.1). Generation reaches the host `llama-server` through a container-local
`socat` forwarder on `127.0.0.1:18080`, so `evaluation-provider-control.json` stays byte-identical
and no machine-specific hostname reaches a persisted artifact. The available server is **not** the
one C6 recorded: Homebrew `llama.cpp` 0.2.0, build 10566, commit `bb4caa754`, sha256
`b6ff7e912a9690ffec38878cad25b9ec1424a5537bd72010effe2fc9bfe64f74`, Darwin arm64, against C6's
`b10610+a14dba686…` / `e3905073…`. A new `canonical-v1r/generation-policy.json` records the observed
revision and a fail-closed host probe plus an in-band model-id check enforce it.

**No speed claim.** The two frozen C6 timings for one identical prompt at temperature 0 are
81,123,017,079 ns and 23,395,804,636 ns — a 3.5× spread at `n=2`. Recorded run-cost ceiling is 60
minutes wall clock, expected 15-40, at most 22 provider calls.

**Next actions, in order.**
1. Review this design.
2. Implement the evaluator attempt loop and the repair-prompt assembly; owner tests offline against
   `scripts/prompt-fixed-adapter.py` only.
3. Implement the Align schema-2 decode with version-1 behaviour byte-unchanged; `make check`,
   `make fmt`, `prompt-score-smoke`, `prompt-render-parity-smoke`, `prompt-gate-validator-smoke`.
4. Freeze `eval/prompt/canonical-v1r/` and `eval/tasks/prompt-v1r/`; confirm
   `make prompt-gate-check` still green.
5. Start `llama-server`, run the container and forwarder, run `make c4-repair-gate` once, and check
   in the evidence — `MET` or `NOT_MET`.

**Blockers.** None. The run needs the host `llama-server` and the 4.7 GB model, both present, and a
window when no other agent is benchmarking on this host.

**Align capability requests.** None new. This design consumes no unshipped Align surface.

**Intentional uncommitted files.** None.
```

### 8.3 `docs/align-development.md` — addition after "The repair patch is deliberately an input boundary"

```markdown
### Model-driven repair on the measurement path

`docs/specs/c4-repair-measured.md` specifies the first repair loop driven by a real provider. It
does not change `src/repair.align` or `src/verification_loop.align`; it runs on the C6 evaluation
path instead, where `scripts/prompt-evaluate.py` owns an attempt loop around the unchanged
measurement adapter. After a first-attempt validation `FAIL`, the evaluator renders a repair prompt
from that attempt's own redacted validation status, summary, stdout, and stderr, calls the generation
child a second time, and validates again. It is a diagnostics-driven second attempt: the failing edit
set is not reachable outside the adapter, which is a frozen corpus member.
`PROMPT_TASK_ROW` moves to `schema_version: 2` with an
ordered per-attempt list; version-1 rows keep their exact meaning and are never migrated.

Two repair loops therefore exist, deliberately: the in-process Align loop above, whose provider is a
`fn (str, str, i64) -> bool` input boundary, and the cross-process evaluator loop, whose provider is
the real local model. Converging them is a named deferral in that document, not an oversight.

The named qualification is `make c4-repair-gate`. It requires a running `llama-server`, the model
file, and a Linux container, so it is a focused qualification and joins no aggregate.
```

---

## 9. Author-side design checks before implementation

1. **Ledger-to-prose.** Section 7, ten items, complete.
2. **Matrix-to-diff preparation.** Section 6 names a planned case for every applicable cell and
   section 6.6 fixes the both-directions coverage rule; the pass that replaces planned names with
   actual file and line runs before review. **That pass has now been run** — section 9.2 records
   it, section 6's tables carry the actual file and line or an explicit deferral, and deviations
   15, 16, and 18 record the three cells whose owner moved or whose case is deferred.
3. **Source-of-truth check.** `c6-prompt-context-optimizer.md` keeps ownership of every reused
   artifact; this document owns only the additions of section 1.2. Sections 8.1 and 8.3 are the only
   places other documents change.
4. **Wire check.** Section 3.2 fixes declaration order, versions, and the one-producer rule;
   section 3.8 fixes validation before any side effect; section 4 fixes the text boundary and its
   bounds.
5. **Gate-topology check.** Section 5.2 keeps the provider-dependent qualification out of every
   aggregate; section 5.1 keeps every new owner test offline and deterministic.
6. **Review check.** The diff will contain a persisted-format change, a new frozen corpus, and a
   provider-backed measurement, so `docs/review-checklist.md`'s "Public contract ledger",
   "Cross-cutting closure matrix", "Evaluation and repository integrity", and "Align correctness"
   sections all trigger. One comprehensive review of the stable candidate.

### 9.2 Matrix-to-diff pass

Section 6.6 requires each planned case name to be replaced by its actual file and line, or by an
explicit deferral, before review. This is that pass, run against the repair head. Line numbers are
the head's; the labels are literal strings in the named files, so a moved line is still findable.

**Three planned owners moved, and the moves are deviations 15, 16, and 18.** Section 6 assumed the
`(S)` cases would land in `scripts/run-prompt-score-smoke`. They did not: `prompt_score.verify_result`
is the single entry point every version-2 rule is reached through, so the Align-side row cases live
in `src/prompt_verifier_smoke.align` and the document-level rejections live in
`scripts/run-prompt-gate-validator-smoke`. Nothing was dropped; the owner is different from the
plan's guess and the table below names the real one.

| Planned case | Actual owner |
| --- | --- |
| `attempt-record-order` | `scripts/run-prompt-evaluate-smoke:1181` (declared field order and the skipped shape); `:3113` against a real published document |
| `attempt-workspace-distinct` | `scripts/run-prompt-evaluate-smoke:1360`; `:3189` for the run-local suffix |
| `attempt-pass-first` | `scripts/run-prompt-evaluate-smoke:3113` — every row of the end-to-end fixture run declares `maximum_repair_loops: 0` and closes with one `INITIAL` attempt |
| `attempt-repair-recovers` | `scripts/run-prompt-evaluate-smoke:1259`, at the module boundary, including the assertion that the prompt carries *this* attempt's diagnostics. **Not** an end-to-end `./main prompt evaluate` run: deviation 16 |
| `attempt-repair-fails` | Deferred with deviation 16; the failing arm is covered at the document level by `src/prompt_verifier_smoke.align:2209` (defect 0 is fail-then-pass) and by the measured run, where ten rows repaired and none recovered |
| `attempt-adapter-schema`, `attempt-digest-mismatch` | Unchanged C6 checks. The adapter-result decode and the rendered-prompt digest equality are the same code paths version 1 used, reached by the existing evaluate-smoke fixture run; this capability adds no new rule there |
| `attempt-adapter-repair-count` | `scripts/run-prompt-evaluate-smoke:1370`; document level `scripts/run-prompt-gate-validator-smoke:1043` |
| `attempt-mixed-version` | `scripts/run-prompt-gate-validator-smoke:902`; Align side `src/prompt_verifier_smoke.align:2234` (defect 5) |
| `attempt-no-repair-offered` | `scripts/run-prompt-evaluate-smoke:1169`; end to end `:2086` and `:3113`; Align side `src/prompt_verifier_smoke.align:2197` (defect 7) |
| `attempt-skip-budget` | `scripts/run-prompt-evaluate-smoke:1238` |
| `attempt-skip-inputs` | `scripts/run-prompt-evaluate-smoke:1208` |
| `attempt-skip-cleanup` | `scripts/run-prompt-evaluate-smoke:1227` — the same rule as `attempt-cleanup-suppresses-repair`; the plan named one rule twice |
| `ladder-01` … `ladder-03`, `ladder-07`, `ladder-09` | Unchanged C6 ladder rows; no new rule, no new case |
| `ladder-04` | `scripts/run-prompt-gate-validator-smoke:989` (`v2-repair-bound`) and `:1302` (every `prompt-v1r` task declares exactly one loop) |
| `ladder-05`, `ladder-06` | `scripts/run-prompt-render-parity-smoke:140` (`repair_template_cases`), including `:194` for a non-UTF-8 template |
| `ladder-08` | `scripts/run-prompt-evaluate-smoke:1459`, `:1479` |
| `attempt-cleanup-order` | `scripts/run-prompt-evaluate-smoke:1360` |
| `attempt-cleanup-suppresses-repair` | `scripts/run-prompt-evaluate-smoke:1227` |
| `attempt-timing-sum`, `attempt-timing-none`, `attempt-timing-bound` | `scripts/run-prompt-evaluate-smoke:1300`; document level `scripts/run-prompt-gate-validator-smoke:1013` |
| `attempt-overhead-presence` | `scripts/run-prompt-evaluate-smoke:1370`; document level `scripts/run-prompt-gate-validator-smoke:1025` |
| `attempt-path-length` | `scripts/run-prompt-evaluate-smoke:1340` |
| `repair-template-decode`, `repair-sections-order`, `repair-template-*` | `scripts/run-prompt-render-parity-smoke:140`-`196` |
| `repair-prompt-golden` | `scripts/run-prompt-render-parity-smoke:197` |
| `repair-input-status` | `scripts/run-prompt-render-parity-smoke:204` |
| `repair-input-empty` | `scripts/run-prompt-render-parity-smoke:239` |
| `repair-input-utf8` | **N/A with a reason.** The three diagnostic strings are fields of a `TASK_MEASUREMENT` the evaluator has already decoded from UTF-8 JSON, so a non-UTF-8 diagnostic cannot reach assembly; the decode is the check. `repair-template-utf8` covers the one input that is read as bytes |
| `repair-drop-stdout`, `repair-drop-stderr`, `repair-drop-summary` | `scripts/run-prompt-render-parity-smoke:275`, `:285`, `:291` |
| `repair-budget-exhausted` | `scripts/run-prompt-render-parity-smoke:298` |
| `repair-rederive-self` | `scripts/run-prompt-render-parity-smoke:306`; the producer runs the same re-derivation against its own output at ladder row 15 |
| `repair-rederive-sidecar` | **Deferred, recorded here rather than faked.** `scripts/prompt-gate-validator.py:1550` validates the `REPAIR_PROMPT_SOURCE` record's shape, bounds, section order, and disjointness, but it cannot recompute the prompt bytes: the sidecar never receives attempt 1's rendered text, which the evaluator holds only in the run workspace. Re-derivation is the producer's (`repair-rederive-self`) and stays there until a capability persists the rendered text |
| `repair-redaction`, `repair-inherits-sandbox-path` | `scripts/run-prompt-render-parity-smoke:323` |
| `score-attempt-records` | `src/prompt_verifier_smoke.align:2209` (defect 0, accepted) and the twelve rejection defects below |
| `score-version-dispatch`, `score-v1-no-v2-fields` | `src/prompt_verifier_smoke.align:2234` (defect 5); `verifier_row_v2_members_absent`, `src/prompt_score.align:3196` |
| `score-label-map` | `src/prompt_score.align:2948`-`2960` (`verifier_attempt_kind_valid`, `verifier_attempt_status_valid`, `verifier_skip_reason_valid`); the declared skip-reason set is asserted at `scripts/run-prompt-evaluate-smoke:1205` |
| `score-v2-decode` | `src/prompt_verifier_smoke.align:2209`, plus the round-trip regression at `:2184` |
| `score-v1-unchanged` | `src/prompt_verifier_smoke.align:2188`-`2192` (version-1 round trip and seal) |
| `score-frozen-rescore` | `scripts/run-prompt-gate-validator-smoke:1178` (`frozen_version_one_chain`) |
| `score-repair-loops-candidate`, `score-repair-loops-parent` | `scripts/run-prompt-gate-validator-smoke:1163` (`v2-parent-repair-loops`); the candidate direction is C6's existing check, reused unchanged |
| `score-repair-regression` | `scripts/run-prompt-gate-validator-smoke:1172` (`v2-aggregate-recompute`) |
| `score-attempt-*` (malformed input) | `src/prompt_verifier_smoke.align:2214` (defect 1, sparse index), `:2219` (2, two `INITIAL`), `:2224` (3, measurement not final), `:2229` (4, overlong), `:2239` (6, count skew), `:2245` (8, untraced attempt), `:2252` (9, overlong with a skipped tail), `:2258` (10, two repairs that ran), `:2265` (11, unreferenced trace record), `:2272` (12, unresolved trace digest); document level `scripts/run-prompt-gate-validator-smoke:902`-`1151` |
| `score-ladder-order` | `src/prompt_score.align:5954` — `verify_result` is one statement per predicate, in the ladder's order; the split is recorded there |
| `score-attempt-lifetime` | `src/prompt_score.align:3144` bounds the attempt list before it is walked; the round-trip regression at `src/prompt_verifier_smoke.align:2184` is the owned-record lifetime assertion |
| `score-aggregate-recompute`, `score-recovery-paired` | `scripts/run-prompt-gate-validator-smoke:1172`; Align side `src/prompt_score.align:5386` recomputes every repair aggregate from the attempts and `src/prompt_verifier_smoke.align`'s defects 7, 9, and 10 each move the recomputed values |
| `corpus-v1r-manifest`, `corpus-v1r-shared-digests`, `corpus-v1r-digest-drift`, `corpus-v1r-repair-bound` | `scripts/run-prompt-gate-validator-smoke:1237` (`frozen_corpus_rows`), which asserts the 24 shared members, their identical digests, the exact added set, every member's bytes against its frozen digest, and `maximum_repair_loops: 1` with the pinned template on all three tasks |
| `corpus-v1r-scope` | The section 5.2 qualification (Q). The scope resolved, every digest recomputed, and the baseline activation bound in the measured run; section 10.3 records it |
| `provider-probe-shape`, `provider-probe-mismatch` x4, `provider-probe-malformed` | `scripts/run-prompt-evaluate-smoke:1430`, `:1459`, `:1479` |
| Non-mutation (6.4) | `scripts/run-prompt-gate-validator-smoke:1237`; `git diff 3df063b..HEAD` over `scripts/prompt-measurement-adapter.py`, `scripts/prompt-fixed-adapter.py`, `scripts/prompt-snapshot-helper.py`, `eval/runners/run-coding-task.py`, `eval/tasks/prompt-v1/`, `eval/prompt/canonical-v1/`, and `eval/prompt/gate/` is empty. `make prompt-gate-check` was **not** run; section 10.3 records that and its substitute |
| Section 6.6 both-directions coverage | Deviation 15: the assertion has three owners, not one, and is not faked in the two smoke files |
| `make prompt-evaluate-smoke` itself | **Run, and it caught three defects.** It does not run on the implementing macOS host: the evaluator's retained-executable launch reads `/proc/self/fd`, and the validation runner needs `bwrap`. The recipe is a `linux/arm64` container from `c4-repair-measure:latest` with deviation 17's four privilege values, the checkout bind-mounted **at its own absolute path** (a linked worktree's `.git` names a common directory that must be mounted read-only at its own path, and the worktree's `gitdir` file must resolve), and `ALIGNC` pointed at the pinned Linux compiler. Under that recipe the merge base `3df063b` passes and the capability head did not; deviation 21 records the three defects and their fixes |

---

## 10. Implementation record

### 10.1 Ledger-to-diff mapping

| Ledger surface | Section | Implementation |
| --- | --- | --- |
| Evaluator-owned attempt loop | 3.1 | `scripts/prompt-evaluate.py`, the `run_attempt` closure and `build_repair_attempt` inside `evaluate` |
| Adapter and runner byte-identical | 3.1, 6.4 | `git diff` over `scripts/prompt-measurement-adapter.py`, `scripts/prompt-fixed-adapter.py`, `scripts/prompt-snapshot-helper.py`, `eval/runners/run-coding-task.py`, `eval/tasks/prompt-v1/`, `eval/prompt/canonical-v1/`, `eval/prompt/gate/` is empty; the 24 shared file-set members carry identical digests in both manifests |
| `PROMPT_TASK_ROW` v2 | 3.2 | `scripts/prompt-evaluate.py:4353` row assembly; the single `PromptTaskRow` with `Option` version-2 members in `src/prompt_artifacts.align` (deviation 10) |
| `TaskAttemptRecord`, `RepairPromptSource` | 3.2 | `ATTEMPT_RECORD_FIELDS`, `REPAIR_PROMPT_SOURCE_FIELDS` in `scripts/prompt-gate-validator.py`; `skipped_attempt_record`, `repair_prompt_source_record` in `scripts/prompt-evaluate.py`; `TaskAttemptRecord` in `src/prompt_artifacts.align`. The four declarations of the attempt record's field order — Align record, validator tuple, evaluator literal, fixture literal — are asserted equal against the published document |
| Attempt-owned trace records | 3.2, 3.8 rows 21-23 | `verifier_attempt_trace_cross_valid` and the three resolvers in `src/prompt_score.align:4870`; `ATTEMPT_TRACE_POOLS` and the presence rule in `scripts/prompt-gate-validator.py` |
| One producer per field | 3.3 | `row_repair_loop_count`, `row_generation_ns`, `row_repair_attempted`, `row_repair_recovered` select by version, never by presence |
| New corpus assets | 3.4 | `eval/prompt/canonical-v1r/`, `eval/tasks/prompt-v1r/`, minted reproducibly by `scripts/freeze-canonical-v1r` |
| Provider topology and evidence | 3.5 | `scripts/probe-provider-service`, `scripts/run-c4-repair-gate`, the container-local `socat` forwarder |
| Timing | 3.6 | `attempt_total_ns`, `adapter_elapsed_ns`, `repair_preparation_ns`, `adapter_overhead_ns` |
| Aggregates and variant-symmetric `REPAIR_LOOPS` | 3.7 | `complete_score` |
| Validation ladder | 3.8 | `validated_repair_template` (rows 4-6), `repair_eligibility` (row 13), `assemble_repair_prompt` (row 14), `build_repair_attempt`'s re-derivation (row 15), the attempt checks in `run_attempt` (rows 10-11) and in `src/prompt_score.align` (rows 16-20) |
| Repair-prompt contract | 4 | `eval/prompt/canonical-v1r/repair-template.json`, `repair_prompt_text`, `assemble_repair_prompt` |
| Evaluator source pin and window | 3.10 | `src/prompt_evaluate.align` |
| Named qualification, no aggregate | 5.2 | `make c4-repair-gate`; `make gate-topology-check` still passes with its byte-literal `EXPECTED` unmoved |

### 10.2 Deviations discovered during implementation

Each was found by implementation, is recorded here rather than absorbed, and changes a promise this
document made.

1. **Ladder row 10 is narrowed, in all three implementations.** Section 3.3 requires every attempt's
   `measurement.repair_loop_count` to be `0` and calls a non-zero value `ERROR`/`ADAPTER`. That
   assumed every adapter emits the literal `0`, which the provider-backed
   `scripts/prompt-measurement-adapter.py` does. The deterministic `scripts/prompt-fixed-adapter.py`
   emits `1` on its expected-failure path, and it is a byte-frozen `canonical-v1` corpus member
   whose digest appears in three places per task manifest and in the file-set manifest. Editing it
   would break `make prompt-gate-check` against C6's merged evidence. The check therefore binds
   exactly where double-counting is possible: a task whose `maximum_repair_loops >= 1`. Where no
   repair is offered, the adapter's value is carried verbatim in `attempt.measurement` and simply is
   not the authority, because at version 2 `row.repair_loop_count` is.

   **The Align verifier did not apply the narrowing, and that is deviation 21.** It was written
   with the rule unconditional, which rejected every version-2 document the deterministic adapter
   produced from an expected-failure row. `make prompt-evaluate-smoke` catches it; neither review
   did, because neither ran that owner. See deviation 21.
2. **`PROMPT_EVALUATION_TASK` grows two fields and stays at `schema_version: 1`.** Section 3.11
   listed it as unchanged, but the task manifest is where `repair_template_path` and
   `repair_template_sha256` must live. They are declared `Option`, and the canonical encoding omits
   an `Option::None`, so all three frozen `eval/tasks/prompt-v1/*.json` manifests keep their exact
   bytes and their exact `content_sha256`. No version bump is needed and none is taken.
3. **A `prompt-v1r` task's `artifacts` list is not byte-identical to `prompt-v1`'s.** Section 3.4
   said it was; it gains one entry, the repair template. Section 4.2 requires the template to be
   "digest-verified exactly like a task prompt", and being a declared artifact is what delivers
   that: it is snapshot-verified before and after every adapter invocation, so a template that
   changed mid-run would be caught rather than assumed stable.
4. **`PROMPT_EVALUATION_EVIDENCE` moves to `schema_version: 2`.** The document did not say so. Its
   `expected_inputs` are now `PROMPT_EXPECTED_INPUT_DIGEST` v2 records, one per non-skipped attempt,
   and section 3.2's own rule is that a document's members and its container share one version.
5. **The evaluator size window widened to four chunks.** Section 3.10 named this as the escape and
   required it to be decided before implementation. It was, and it was needed:
   `scripts/prompt-evaluate.py` is now 217,056 bytes against an old ceiling of 196,608. The
   admissible window is 196,609…262,144 bytes and `EVALUATOR_BOOTSTRAP` pops four arguments.
6. **A parent `REPAIR_LOOPS` reason is a new record shape, not the candidate's.** Section 3.7 asked
   only that the check become variant-symmetric. The candidate record keeps its exact existing
   shape (`parent_value: "NONE"`, `candidate_value`: the count) in its exact existing position, so
   no version-1 verdict can change; a parent violation emits a distinguishable record
   (`parent_value`: the count, `candidate_value: "NONE"`).
7. **The gate directory records a `C4_REPAIR_GATE_RECORD`, not a `PromptGateManifest`.** Section 3.4
   named `c4-repair-gate-manifest.json`. A gate manifest is the C6 accept/rollback chain's
   human-owned envelope; this capability accepts and rolls back nothing, so the run record carries
   the topology, the provider probe, the wall clock against the cost ceiling, and the per-row
   attempt outcomes instead.
8. **The evaluation image is new.** Section 5.5 assumed a Linux aarch64 image carrying `bwrap` and
   `socat`. The C6 measurement image on this host carries neither. `c4-repair-measure:latest` is
   built from it by adding exactly those two packages; `/usr/bin/python3`
   (`a7d56a8a764faf7bbf5c164055a48fd072be52287bdeb523a9e07b2042f4e7e1`) and `/usr/bin/git`
   (`aa6540695d076182256dd6e96c8b302e4d56381e3000bbfd5c71bbdfe94a4942`) keep the digests the C6
   gate locator pins, so the source-verifier policy identity is unchanged.
9. **The model file did not move.** Section 2.5 recorded that the available server is not C6's. It
   is not — but `shasum -a 256 ~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf` is
   `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c`, exactly the `model-sha256`
   frozen into `canonical-v1/generation-policy.json`. Only the server binary and build differ. The
   new policy records that honestly rather than reusing C6's string.

10. **The version-2 chain is one record set with `Option` members, not a `PromptTaskRowV2` twin.**
    Section 3.3 required a parallel record on the premise that "one record therefore cannot decode
    both shapes: declaring `attempts` as required would reject every version-1 row, and omitting it
    would silently drop the version-2 fields while they still contribute to `content_sha256`." That
    premise names two options and misses a third. Declaring the new members `Option` has **neither**
    defect, and both halves were verified against the pinned compiler before the choice was taken:
    `Option<array<T>>` compiles and decodes a missing key to `None`, and `encode` omits a `None`, so
    the frozen version-1 documents round-trip byte-identically. The invariant section 3.3 actually
    protects is enforced more strictly than the twin design would have: the scorer reads
    `schema_version` first, and then requires **every** version-2 member to be present at version 2
    and **absent** at version 1 (`verifier_row_v2_members_absent`), so presence can never stand in
    for a version in either direction. The twin would have forced duplicating roughly sixty verifier
    functions across eighty-nine `PromptEvaluationResult` references, including containment and
    snapshot-trace logic — the same duplication section 5.7 refuses for the adapter, and refusing it
    there while accepting it here would be inconsistent. `src/prompt_artifact_io.align` consequently
    needed no change at all. Section 3.3's prose should be corrected to record `Option` as the
    chosen mechanism. Evidence: the frozen C6 result and sidecar decode, re-encode, and verify to
    `ImprovedEligible`, matching C6's recorded `IMPROVED` / `gate_eligible: true`.
11. **The repair-template pairing rule is enforced at version 2 only, on the Align side.** Enforcing
    "`maximum_repair_loops >= 1` implies a declared template" unconditionally rejects the checked-in
    version-1 fixture `eval/fixtures/c6-prompt-state/templates.jsonl`, which declares
    `maximum_repair_loops: 10` with no template. The rule is a property of the `prompt-v1r` corpus,
    and `scripts/prompt-evaluate.py` enforces it at admission for every task it runs.
12. **`verifier_reason_capacity` grows.** The variant-symmetric `REPAIR_LOOPS` check adds a tenth
    per-pair serious-regression reason, so `pairs * 9` becomes `pairs * 10` and the cap `9_282`
    becomes `10_306` (`task_count <= 64`, `sample_count <= 16`, so `1024 * 10 + 64 + 2`).
13. **Single-point mutation coverage, re-measured after review, and one clause that no input can
    reach.** The first implementation reported four attempt invariants with no single-point
    coverage. Review showed the cause was fixture shape rather than the invariants: every defect
    case had a three-attempt row that three separate rules rejected, so weakening any one of them
    left the owner green. Three new `src/prompt_verifier_smoke.align` cases fix that — defect 9 (a
    three-attempt row whose third attempt was skipped, which only the `1 + maximum_repair_loops`
    bound rejects), defect 10 (two repairs that both ran against a task cap of two, which only
    `repair_count > 1` rejects), and defect 11 (a persisted trace record that nothing references,
    which only `verifier_all_trace_records_referenced` rejects) — and defect 12 covers the new
    trace-resolution rule, and defect 13 covers deviation 21(a)'s narrowing. **Seven** mutants were
    injected into `src/prompt_score.align` at the final head and run under
    `make prompt-verifier-smoke`: the attempt-length bound, the repair-count bound, **both
    together**, `verifier_row_references_trace` returning `true` for any row, the attempt-trace
    resolution, and re-imposing `measurement.repair_loop_count == 0` unconditionally all die. The
    seventh, weakening
    `declared_loops > task.regression_limits.maximum_repair_loops` in
    `verifier_row_repair_facts`, **survives and always will**: the walk already bounds
    `repair_count` at one and the list at `1 + maximum_repair_loops`, and the preceding clause pins
    `declared_loops` to `facts.repair_loop_count`, so no document can make that comparison true. It
    is redundant defence in depth, is commented as such at the call site, and single-point coverage
    is not claimed for it. The version-2 expected-input per-attempt binding is covered at the
    document level by `v2-expected-duplicate`, `v2-expected-missing`, and `v2-expected-extra`.

14. **A checked-in smoke fixture had to move off `maximum_repair_loops: 2`.** The fixture corpus in
    `scripts/run-prompt-evaluate-smoke` declared `2`, which ladder row 4 now rejects, so it moved to
    `0`. That is the rule working: `2` was previously unenforced headroom no code path could reach.
15. **The section 6.6 both-directions code-coverage assertion is not in the two smoke files, and is
    not faked.** `scripts/prompt-evaluate.py` only ever emits `ADAPTER_RESULT`, `CLEANUP_FAILED`,
    `SNAPSHOT_ERROR`, `TIMING`, `REPAIR_RENDER`, and the drift and `validation_error_code` families.
    `SCHEMA`, `DIGEST`, `SOURCE`, `REPAIR_BOUND`, `TEMPLATE`, `TEMPLATE_BUDGET`,
    `PROVIDER_IDENTITY`, `ATTEMPT_ORDER`, `REPAIR_LOOPS`, `MEASUREMENT_BINDING`, and
    `EVIDENCE_BINDING` are the Align verifier's and the gate validator's vocabulary, so the
    assertion belongs in those owners. Section 6.6 assumed a single owner and there are three.
16. **Two end-to-end owner cases are deferred, with the reason stated rather than the cases faked.**
    `attempt-repair-recovers` and `attempt-repair-fails` are covered at the module boundary — including
    an assertion that the repair prompt carries *this* run's diagnostics — but not yet as full
    `./main prompt evaluate` runs against a synthetic fail-then-pass adapter, because the Align
    version-2 publish path was still landing when the smokes were written. `attempt-no-repair-offered`
    **is** covered end to end. The route is recorded: a synthetic adapter keyed off the `-a1`/`-a2`
    suffix in `--rendered-prompt`, emitting `repair_loop_count: 0`.

17. **The evaluation container needs an explicit privilege grant for `bwrap`, and it is published
    rather than assumed.** Section 3.5 said validation runs in `bwrap` inside a Linux container and
    did not say what that costs. On Docker it costs four values: the default seccomp profile denies
    the namespace calls `bwrap` makes, and the masked `/proc` paths deny the `proc` re-mount inside
    the user namespace the validation runner prepares — which fails as `Can't mount proc on
    /newroot/proc: Operation not permitted` **after** that row's generation call has already been
    paid for, so the cost of discovering it late is real provider time. The grant is now in section
    3.5's table and in every run record's `container_privileges`. Full `privileged` also works and
    is deliberately rejected as broader. The validation sandbox itself is unchanged: `bwrap` still
    drops all capabilities inside it, and `containment_passed` is still verified per attempt.

18. **The version-2 row cases have one Align owner, not four.** Section 5.1's "Row-bearing
    fixtures" row planned version-2 cases in `src/prompt_score_smoke.align`,
    `src/prompt_score_prefix_smoke.align`, `src/prompt_verifier_smoke.align`, and
    `eval/fixtures/c6-prompt-state/templates.jsonl`. Only the third has them.
    `prompt_score.verify_result` is the single entry point every version-2 rule is reached through,
    so the other two Align smokes would have carried copies of one assertion, and the `jsonl`
    fixture is a frozen version-1 input that deviation 11 exists to keep frozen. The
    document-level rejections that section 6.3 labelled `(S)` live in
    `scripts/run-prompt-gate-validator-smoke` for the same reason. Section 9.2 binds every planned
    case to its real owner.
19. **`TaskAttemptRecord` gained four trace digests after the first completed run, and the
    `input_snapshots` bound moved with them.** Section 3.2 did not have them: the first run
    produced the identical 22 calls and the identical verdict but was rejected by
    `verifier_all_trace_records_referenced`, because `snapshot_attestations` carries exactly one
    record per row and a row can now run twice, so the repair invocation's snapshot request,
    before/after results, and input snapshot were referenced by nothing. The record therefore
    carries `snapshot_request_sha256`, `before_snapshot_result_sha256`,
    `after_snapshot_result_sha256`, and `input_snapshot_sha256`, present exactly on an attempt that
    ran; the per-row `input_snapshots` bound became per **invocation**, which is the same bound at
    version 1. Section 3.2's field order, section 3.8 rows 21-23, and the section 3.11 ledger
    record it. Review then found that naming was all the verifier checked, so the digests are now
    resolved: each must name exactly one persisted record of that row's task, and the resolved
    records are held to the same closure, before/after equality, and artifact-equality rules the
    row's attestation is held to.
20. **`included_sections` and `dropped_sections` are not a partition, and section 4.3 now says
    so.** A section whose source is empty appears in neither list: `included` is what the prompt
    carries and `dropped` is what the budget ladder removed, and an empty section was never a
    candidate for either. All four `layer-precedence-frozen-module` repairs in the measured run
    show it — empty `diagnostic_stdout`, `included_sections: [STATUS, SUMMARY, STDERR]`,
    `dropped_sections: []`. A consumer that needs "was this section available" must read
    `attempt.measurement`, not infer it from the two lists.

21. **`make prompt-evaluate-smoke` was red on the capability head — three defects, none of which
    either review found, because neither ran that owner.** The owner passes at the merge base
    `3df063b` and failed at the capability head. All three are fixed and it passes again.

    **(a) Deviation 1 was applied in only two of its three implementations.**
    `verifier_ran_attempt_valid` in
    `src/prompt_score.align` required `attempt.measurement.repair_loop_count == 0` for **every**
    task, while `scripts/prompt-evaluate.py` and `scripts/prompt-gate-validator.py` bind it only
    where `maximum_repair_loops >= 1`. `scripts/prompt-fixed-adapter.py:612` — a byte-frozen
    `canonical-v1` member — emits `1` on its expected-failure path, so the Align verifier refused
    every version-2 document that fixture corpus produced from such a row:
    `./main prompt evaluate` published nothing and exited `EVALUATION_FAILED`. The three
    implementations now bind the rule identically, and `src/prompt_verifier_smoke.align` defect 13
    is the regression: a task offering no repair, whose attempt carries an adapter-reported repair
    loop, must be **accepted**.

    **(b) A terminal adapter measurement aborted before its own row was persisted, leaving trace
    records referenced by nothing.** At version 1 the evaluator appended the row, its
    expected-input identity, and its `COMPLETE` attestation and only *then* returned the terminal
    `ERROR`/`ADAPTER_RESULT` result, so the failing row stayed in the published document. The
    attempt loop moved that check inside `run_attempt`, before any of them, so the invocation's
    snapshot request, before/after results, and input snapshot were persisted with no row, no
    attempt, and no attestation naming them — and this capability's own "no unreferenced trace
    record" rule then refused to publish the document at all. `scripts/prompt-evaluate.py` now
    raises the terminal error in the caller, after `rows.append(row)`, which is the version-1
    order. The owner asserts the published shape: one row, `measurement.status: ERROR`, one
    `COMPLETE` attestation.

    **(c) The owner itself read an omitted `Option` with `[]`.** A non-passing attempt has no
    `adapter_overhead_ns` key, because the canonical encoder omits an `Option::None`; the
    assertion that overhead is present exactly on a passing attempt raised `KeyError` on the first
    published non-passing row instead of testing anything. It reads `.get(...)` now.

    **How it escaped both reviews, and what that says about the owner.** The owner test that
    catches it does not run on the implementing macOS host: the evaluator's retained-executable
    launch path reads `/proc/self/fd`, and the validation runner needs `bwrap`, which needs the
    four container privilege values of deviation 17. Running it means a Linux container with those
    privileges and the pinned compiler mounted. The merge base `3df063b` passes it under exactly
    that recipe and the capability head did not, which is how the defect was isolated. The recipe
    is recorded in `HANDOFF.md`; it is the substitute for a Linux CI run and should be used before
    any future change to this evaluator or its verifier. Defects (b) and (c) are the direct cost of
    not having run it during implementation: (b) is a published-artifact defect on an error path
    the qualification never reached, and (c) is an assertion that could never have passed.

Nothing here required an unshipped Align surface. The version peek that section 3.3 flagged as a
possible Align gap is a non-issue under deviation 10: the row's own `schema_version` is an ordinary
decoded field, read before any version-2 member is consulted.

Implementation did surface one genuine Align gap, filed as **Request 52** in
`docs/align-requests.md`: `match` on an **owned** record's `Option` field partially moves the
payload out with no diagnostic, and a later `json.encode` of that still-live record silently omits
the field. Because `src/prompt_evaluate.align` decodes the evaluator's output and re-encodes it to
produce the persisted artifact, that is a silent-wrong-artifact hazard rather than a compile error.
Every `Option` member added by this capability is read through a `borrow` binding, which is safe;
the two spellings look interchangeable at the call site and are not. The array-indexing refusal also
hit during implementation is the already-filed Request 22 and is not re-filed.

### 10.3 Measured gate result

**The gate is `NOT_MET`.** `repair_recovery_paired_count` is **0**, and so is `repair_recovery_count`:
across ten repair attempts on the three-task corpus, **not one row recovered**. This is a delivered
result, reported exactly as section 1.4 and section 5.3 fixed before the run. Every figure below is
recomputed from `eval/prompt/c4-repair-gate/c4-repair-evaluation.json` and its gate record.

Run: 12 rows, 3 tasks x 2 variants x 2 paired samples, `temperature_micros: 0`,
`seed_mode: PAIRED_FIXED`, **22 provider generation calls** — precisely the section 5.2 estimate of
12 initial plus 10 repair. Wall clock **824.243 s = 13 min 44 s**, inside the 60-minute recorded
ceiling and inside the 15-40 minute expectation.

**The checked-in evidence is a second run, taken from a clean committed head.** The first run was
made from an uncommitted working tree, so `align_llm_reachability` was `UNVERIFIED` and the
evidence named no reproducible commit. Review asked for a run whose record names one. This run's
`align_llm_commit` is `f0314400d3fdb7f4cac6c1c277c6518a66c02561` with `align_llm_clean: true`, and
all three reachability fields are `VERIFIED`. **Every correctness value reproduced exactly**: the
same twelve rows with the same per-attempt statuses, failure kinds, and `patch_size_bytes`
(716 / 758 / 0 / 1008), the same ten repair attempts, the same zero recoveries, the same aggregates,
and the same 8,123-16,129 assembled prompt bytes with the same per-row section sets. Only the
clocks moved, which is what makes the timing figures below a single-run observation and not a
baseline.

| Task | Sample | Variant | Attempt 1 | Attempt 2 | Loops |
| --- | --- | --- | --- | --- | --- |
| `duration-half-away-from-zero` | 1 | PARENT | FAIL (`TEST`) | FAIL (`TEST`) | 1 |
| `duration-half-away-from-zero` | 1 | CANDIDATE | **PASS** | — | 0 |
| `duration-half-away-from-zero` | 2 | CANDIDATE | **PASS** | — | 0 |
| `duration-half-away-from-zero` | 2 | PARENT | FAIL (`TEST`) | FAIL (`TEST`) | 1 |
| `layer-precedence-frozen-module` | 1 | PARENT | FAIL (`PATCH`) | FAIL (`PATCH`) | 1 |
| `layer-precedence-frozen-module` | 1 | CANDIDATE | FAIL (`PATCH`) | **POLICY_VIOLATION** | 1 |
| `layer-precedence-frozen-module` | 2 | CANDIDATE | FAIL (`PATCH`) | **POLICY_VIOLATION** | 1 |
| `layer-precedence-frozen-module` | 2 | PARENT | FAIL (`PATCH`) | FAIL (`PATCH`) | 1 |
| `record-codec-round-trip` | 1 | PARENT | FAIL (`TEST`) | FAIL (`TEST`) | 1 |
| `record-codec-round-trip` | 1 | CANDIDATE | FAIL (`TEST`) | FAIL (`TEST`) | 1 |
| `record-codec-round-trip` | 2 | CANDIDATE | FAIL (`TEST`) | FAIL (`TEST`) | 1 |
| `record-codec-round-trip` | 2 | PARENT | FAIL (`TEST`) | FAIL (`TEST`) | 1 |

The failure kind is shown on **both** attempts: every `layer-precedence-frozen-module` attempt,
attempt 1 included, failed at `PATCH` with `patch_size_bytes: 0` — the model produced nothing
applicable there from the start, and reading the table as if attempt 1 had produced a patch would
misstate the result.

> **Corrected by `docs/specs/c4-repair-template.md` section 1.2.** "Produced nothing applicable"
> is right; "produced no parsable `FILE:` block" — the reading this document's prose invited and
> that three later documents took — is **wrong**. Every `failure_kind: PATCH` row here carries
> `diagnostic_summary: "the response reproduced the pinned files unchanged"`, which is
> `synthesized_patch`'s refusal, raised *after* `parse_file_blocks` returned terminated blocks and
> *after* `validated_edit_set` accepted every declared path. The string
> `"the response declares no file block"` appears in **zero** rows of this run or of C4E. The model
> emitted syntactically correct blocks naming allowlisted paths whose bodies were byte-identical to
> the pinned source. `failure_kind` collapses eight distinct raise sites into one enum value, which
> is why the distinction was invisible from the field every consumer reads; `TASK_MEASUREMENT`
> version 3's `edit_refusal` gives each site a code so the mistake cannot be made from the record
> again.

The two passes are first-shot CANDIDATE passes on `duration-half-away-from-zero`, reproducing C6's
distribution exactly; they needed no repair and took none. Every one of the other ten rows made its
repair attempt.

`corpus_aggregate`: `parent_pass_count: 0`, `candidate_pass_count: 2`, `repair_attempt_count: 10`,
`repair_recovery_count: 0`, `repair_recovery_paired_count: 0`, `repair_loop_regression_count: 0`
(PARENT repaired 6 times, CANDIDATE 4, so the acceptance policy's zero-regression limit is met
without being relaxed). The C6 acceptance verdict is `SERIOUS_REGRESSION`, from two `POLICY` reasons
— **not** a C4 signal, and recorded only as the secondary evidence section 3.7 says it is.

**What the mechanism proved.** All ten repair prompts assembled from the run's own persisted
diagnostics, re-derived byte-exactly against their own output, and stayed far inside the prompt
budget: **8,123 to 16,129** assembled bytes against 65,536, so **no section was ever dropped** and
the drop ladder never fired in anger. Four of the ten carried three sections rather than four
because `diagnostic_stdout` was empty; section 4.3 records why that is not a drop.

**Timing, recomputed from the 22 attempt records of the checked-in run.**

```text
adapter_elapsed_ns over 22 calls:  min 7.98 s   max 64.67 s
                                   mean 24.82 s  median 18.59 s
                                   max/min 8.1x
sum of the 22 calls:               545.9 s
invocation wall clock:             824.243 s  (13 min 44 s)
adapter_overhead_ns:               91.04 ms and 91.77 ms, on the two passing attempts
                                   0.59 % and 1.00 % of those rows' own elapsed spans
```

The first run's figures were 8.13-73.82 s, mean 27.47 s, median 18.27 s, 9.1x, 604.3 s, 881.673 s,
and 65.74 / 74.11 ms — the same shape, different clocks, which is the point. An earlier draft of
this section reported "11.40 s to 81.19 s, median 27.47 s" and "113.7 ms and 115.2 ms" for that
first run; those were wrong at the time: the range came from the wrong rows, 27.47 s was its
**mean** and not its median, and the two overhead figures were not the persisted ones. Every number
here is recomputed from the artifact in the tree. The section 3.6 redefinition costs about one per
cent of a passing row's total, which is now measured rather than argued.

**Why the model did not recover, and what it means for section 5.7.** This is an inference from
`patch_size_bytes` and the observable failure, and its limits are stated before it is drawn: the
patch body and a patch digest are **not** persisted — only its size is — so "the same patch" is not
directly verifiable from this evidence, and the claim below is scoped to what is.

- **`record-codec-round-trip`, all four rows** (both variants, both samples): attempt 1 and
  attempt 2 each produced `patch_size_bytes: 1008` and each failed identically at `TEST`. A patch
  of the same size failing in the same observable way twice is consistent with the model
  re-emitting its previous answer, and is not proof of it. Persisting a patch digest would settle
  it, and is a named deferral in section 5.4.
- **`layer-precedence-frozen-module`, all four rows**: attempt 1 already produced
  `patch_size_bytes: 0` and failed at `PATCH`. The two CANDIDATE repairs came back
  `POLICY_VIOLATION` with `patch_size_bytes: 0`, and the two PARENT repairs failed at `PATCH` with
  an empty patch. **Nothing here is "repeating attempt 1's mistake"** in the record-codec sense:
  the model produced nothing applicable on either attempt — well-formed blocks reproducing the
  pinned files unchanged, per the correction above — which is a different failure mode, and more
  diagnostics are not obviously the missing input for it.

So the evidence for section 5.7's tie-breaker is real but **narrower** than the first draft claimed:
in the one mode where the model does emit an applicable patch, the second attempt's patch has the
same size and the same observable failure as the first, which is the case where the missing edit
set is the plausible binding constraint. Option B — a second corpus-member adapter that carries the
failing edits into the repair prompt — addresses **that** mode. It does not address the
`layer-precedence-frozen-module` mode, where the blocks parsed and were allowlisted but
reproduced the pinned files unchanged, so no patch was synthesized (see the correction above). The deferral in section
5.4 should be re-read in that light, and a patch digest should land with it so the next run can
answer the question directly instead of by inference.

**No speed claim is made**, and none is available: the 7.98 s to 64.67 s spread over 22 calls at
temperature 0 is an **8.1x** ratio, wider than the 3.5x section 2.1 recorded at `n=2` and drawn
from a sample that mixes three tasks and two prompt lengths. The first run's ratio was 9.1x on the
same corpus and the same seeds, which is itself the measurement: the spread is not stable enough to
support a claim.

**Published through the Align path.** `make c4-repair-gate` completed with `PUBLISHED`; the
artifacts in `eval/prompt/c4-repair-gate/` are the Align publisher's own canonical encoding, with
every `Option::None` omitted rather than written as `null`. Digests:
`c4-repair-evaluation.json` `8793b1ff1c27e52dfc7d6ba1177f7b44683a70590e265d5278d5a9698fcc0c06`;
`c4-repair-evaluation-evidence.json`
`a70a967e441a21cc5c93a088edb077195da3b75abd790b172e97f398cf7c9999`;
`c4-repair-gate-record.json` `18bdf25a770ea51980f837764c11f5c2e8a7d6f6a3559b70feb91de6b00a2588`.

`gate_eligible` is `false`, and **not for the reason an earlier draft of this section gave.** It is
not reachability: all three reachability fields are `VERIFIED` in this run. `gate_eligible` is the
**C6 acceptance** gate, and `verifier_gate_computed` requires `status == "IMPROVED"` with no
serious-regression reason; this run's status is `SERIOUS_REGRESSION` from the two `POLICY` reasons
above. That is the C6 verdict, recorded as the secondary evidence section 3.7 says it is. The C4
verdict consumes `repair_recovery_paired_count` only and does not read it.

**`make prompt-gate-check` was not run: `N/A`, with its reason and its substitute.** Section 5.1
calls it "unchanged and must stay green" and section 8.2's superseded draft listed it as next
action 4. It needs a source bundle and the Linux process-containment floor, neither of which this
macOS host provides, and the containerized path exists only for the gate qualification. What was
run instead, and what each part covers:

| Claim `prompt-gate-check` would carry | Substitute evidence |
| --- | --- |
| The frozen version-1 chain still validates and rescores byte-identically | `scripts/run-prompt-gate-validator-smoke:1178` drives `validate_acceptance_policy` and `rescore` directly against the merged C6 evidence and asserts `IMPROVED` with byte-identical aggregates |
| `canonical-v1`, `eval/prompt/gate/`, `eval/tasks/prompt-v1/`, `run-coding-task.py`, and `prompt-measurement-adapter.py` were not moved | `scripts/run-prompt-gate-validator-smoke:1237` asserts the 24 shared file-set members carry identical digests in both manifests and that every `canonical-v1r` member's bytes still hash to its frozen digest; `git diff 3df063b..HEAD` over those paths is empty |
| The Align scorer still accepts the frozen version-1 documents | `src/prompt_verifier_smoke.align:2188`-`2192` round-trips and re-seals a version-1 document; `make prompt-verifier-smoke` is green |

That is not the same thing as running the gate, and it is not claimed to be. `make prompt-gate-check`
remains the full proof and belongs in hosted CI, where the floor exists.

**The publish defect that this run closed.** The first completed run produced the identical 22
calls and the identical verdict, but `prompt_score.verify_result` rejected the document. Bisecting
the predicate chain isolated `verifier_all_trace_records_referenced`. The cause was a real gap in
the evidence model, not a scoring bug: every trace record must be referenced by a recorded
invocation, `snapshot_attestations` carries exactly one record per row because its schedule check
binds it positionally, and a row can now run **twice** — so the repair attempt's own snapshot
request, before/after results, and input snapshot were referenced by nothing. `TaskAttemptRecord`
therefore gained `snapshot_request_sha256`, `before_snapshot_result_sha256`,
`after_snapshot_result_sha256`, and `input_snapshot_sha256`, present exactly on an attempt that
ran and absent on a skipped one, and the referencing check accepts an attempt record as the
referent. The `input_snapshots` upper bound moved from one-per-row to one-per-invocation, which is
the same bound at version 1 because a version-1 row runs exactly once.

**Review found that naming was not resolving, and the guarantee is now what the comment claims.**
The first implementation checked only that the four digests were well-formed and present. An
attempt could therefore have named a digest belonging to no record, or to another task's record,
and the "no unreferenced trace record" guarantee would have been satisfied by the naming alone.
`verifier_attempt_trace_cross_valid` (`src/prompt_score.align:4870`) now resolves each digest to
**exactly one** persisted record of that row's task and applies the attestation path's own checks
to the resolved records: before and after are the same observation, both are closed over the
resolved request, and the input snapshot is that task's and carries the snapshot's artifact
digests. The rule was validated against this published document before it shipped — all 22 attempts
resolve and cross-validate — so the checked-in evidence is admitted by the tighter verifier, not
grandfathered past it. `scripts/prompt-gate-validator.py` carries the matching shape and pool rules,
and its fixture emits the four digests, which it previously did not: without that, every version-2
attempt case in the validator smoke was vacuous.

`src/prompt_verifier_smoke.align` defects 8, 11, and 12 are the regressions — an attempt attesting
no trace record, a persisted record nothing references, and a well-formed digest that resolves to
nothing — and all three were mutation-tested; deviation 13 records the mutants and the one clause
no input can reach.
