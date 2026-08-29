# C4-REPAIR-TEMPLATE: the prompt template and the declared edit policy

Status: **implemented, measured, review-repaired, and owner-verified; final review and publication
pending.** This document
is the authoritative plan and result record. The proportional
design gate in `CLAUDE.md` triggered on an exchanged-format change (the repair-prompt content
contract moves to **version 3**: a sixth section kind and a new sealed template), on a persisted-
format change (`TASK_MEASUREMENT` `schema_version` 2 → 3 carries the refusal code, the retained edit
set, and the bounded completion identity; the task manifest gains a declared `edit_policy` record),
on a new frozen corpus scope with a **third measurement adapter** and **three new task prompts** as
members, and on a coordinated invariant across `scripts/prompt-template-adapter.py`,
`scripts/prompt-evaluate.py`, `scripts/prompt-gate-validator.py`, `src/prompt_score.align`,
`src/prompt_artifacts.align`, and the corpus assets. Branch `agent/c4-repair-template`, stacked on
`agent/c4-repair-editset` at `de56c60`.

`docs/specs/c4-repair-editset.md` is the source of truth for everything this capability reuses
unchanged — the import-by-path adapter contract, `TASK_MEASUREMENT` `schema_version: 2` and its
presence rules, the adapter-selected corpus rules, the `EDITSET` section and the drop ladder, the
`canonical-v1e` freeze, and the gate predicate. `docs/specs/c4-repair-measured.md` is the source of
truth for the evaluator-owned attempt loop, `PROMPT_TASK_ROW` `schema_version: 2`, the repair-prompt
re-derivation rule, the per-attempt timing definition, and the provider topology.
`docs/specs/c6-prompt-context-optimizer.md` remains the source of truth for the layer beneath all
three. This document owns only what C4-REPAIR-TEMPLATE adds.

**It also owns a correction.** Section 1.2 replaces a factual claim that appears in
`c4-repair-measured.md`, `c4-repair-editset.md`, `eval/prompt/c4-editset-gate/README.md`,
`HANDOFF.md`, and roadmap item 34. The correction is derived from the checked-in evidence, it
changes what this capability must do, and it is stated before anything is designed on top of it.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

C4-REPAIR-EDITSET returned a measured negative and named its own successor. Its section 6.4 and its
section 11.4 both point here:

> The next capability is therefore the prompt, the template, and the edit policy — §6.4's named
> fallback — and not further adapter work.

This is that capability. It changes what the model is *told*, in both attempts, and it makes the
one failure mode that has now consumed ten of twenty-two provider calls a **named, counted,
diagnosable** outcome instead of a free-text string that three design documents read wrong.

### 1.2 The measured evidence, corrected

Every figure below is a static read of `eval/prompt/c4-editset-gate/c4-editset-evaluation.json` and
`eval/prompt/c4-repair-gate/c4-repair-evaluation.json` at this branch's base `de56c60`. No provider
run, no `llama-server`, no Docker, and no model load was performed for this design.

**The correction.** `c4-repair-measured.md` §1.2, `c4-repair-editset.md` §1.2, §6.4 and §11.4,
`eval/prompt/c4-editset-gate/README.md`, `HANDOFF.md`, and roadmap item 34 all describe the
`layer-precedence-frozen-module` failures — and, after the C4E run, the two
`duration-half-away-from-zero` PARENT attempt-2 failures — as **"no parsable `FILE:` block"** and
attribute them to `parse_file_blocks`. That is not what happened.

`scripts/prompt-measurement-adapter.py` raises `EditFormatError` from eight distinct sites, and
`str(failure)` becomes `diagnostic_summary` verbatim (`assemble()` line 1338). Read back:

| `diagnostic_summary`, verbatim | Raise site | Rows in C4E | Rows in C4 |
| --- | --- | --- | --- |
| `the response reproduced the pinned files unchanged` | `synthesized_patch`, line 433 | **10** | **8** |
| `the response edits a file outside the editable set: src/legacy.py` | `validated_edit_set`, line 316 | **2** | **2** |
| `the response declares no file block` | `validated_edit_set`, line 311 | **0** | **0** |
| `a FILE header carries no fenced block` | `parse_file_blocks`, lines 279/282 | 0 | 0 |
| `a fenced file block is not terminated` | `parse_file_blocks`, line 295 | 0 | 0 |
| `the response declares too many file blocks` | `parse_file_blocks`, line 297 | 0 | 0 |

**No attempt in either gate run has ever failed to parse.** `synthesized_patch` raises *after*
`parse_file_blocks` returned at least one terminated block and *after* `validated_edit_set` accepted
every declared path against the task definition's `allowed_edits`. The model emitted syntactically
correct `FILE:` blocks, naming allowlisted paths, whose bodies were **byte-identical to the pinned
source**, so `whole_file_hunk` contributed nothing and the synthesized diff was empty.

The C4E per-attempt picture, re-derived row by row:

| Task | Variant | a1 | a1 refusal | a2 | a2 refusal |
| --- | --- | --- | --- | --- | --- |
| `duration-half-away-from-zero` | PARENT ×2 | `FAIL`/`TEST`/716 | — | `FAIL`/`PATCH`/0 | reproduced unchanged |
| `duration-half-away-from-zero` | CANDIDATE ×2 | `PASS`/758 | — | no repair | — |
| `record-codec-round-trip` | PARENT ×2 | `FAIL`/`TEST`/1008 | — | `FAIL`/`TEST`/1008 | — (byte-identical patch) |
| `record-codec-round-trip` | CANDIDATE ×2 | `FAIL`/`TEST`/1008 | — | `FAIL`/`TEST`/1008 | — (byte-identical patch) |
| `layer-precedence-frozen-module` | PARENT ×2 | `FAIL`/`PATCH`/0 | reproduced unchanged | `FAIL`/`PATCH`/0 | reproduced unchanged |
| `layer-precedence-frozen-module` | CANDIDATE ×2 | `FAIL`/`PATCH`/0 | reproduced unchanged | `POLICY_VIOLATION`/`POLICY`/0 | `src/legacy.py` not editable |

**Ten of twenty-two ran attempts were refused by the edit policy**, not by the tests: eight for
reproducing the pinned files unchanged and two for naming a path outside the editable set. That is
the largest single failure class in either run, it is larger than the class C4-REPAIR-EDITSET was
built for, and until this document it had no name, no code, and no counter.

**Three consequences, all of which change the design.**

1. **A stricter `FILE:` block statement is not the fix, because the format was never wrong.** The
   grammar is a hard constraint (§2.3): version 3 changes instruction text only.
2. **The two things the model actually violated are already stated in the attempt-1 prompt** (§2.2),
   and one of them — the unchanged-file refusal — is stated **nowhere at all**, in any prompt, in
   any template, today (§2.2). It is an emergent property of `synthesized_patch`.
3. **`edit_set` is built and then discarded on exactly this path** (§2.4), so the record cannot say
   *which* file was reproduced or what its body was. The mode is diagnosable in principle from one
   line the producer already computed and throws away.

### 1.3 In scope

1. **The declared edit policy.** `PROMPT_EVALUATION_TASK` gains an optional `edit_policy` record
   carrying `maximum_file_blocks` (32), `maximum_edit_bytes` (262,144), and
   `refuse_unchanged_files` (`true`) — today only constants in three scripts and an unstated
   consequence of `synthesized_patch`. Validated before any provider call, refused as
   `INVALID_INPUT`/`EDIT_SET` (§3.4, §3.9).
2. **Repair-prompt content contract version 3.** A sixth section kind, `POLICY`, rendered per task
   from the digest-pinned task definition and the declared policy; a new sealed template with a
   worked example, the unchanged-file refusal stated, and the format requirement restated between
   the preamble and the sections (§4.2, §4.4).
3. **Task prompt version 3.** Three new task prompts under `eval/tasks/prompt-v1t/`, adding the
   unchanged-file refusal, the declared bounds, and a concrete worked example. **This changes
   attempt 1**, symmetrically for both variants, and §4.3 argues why that is required rather than
   tolerated.
4. **`TASK_MEASUREMENT` `schema_version: 3`**, adding `edit_refusal` (a ten-code vocabulary),
   `completion_bytes`, `completion_sha256`, and a conditional bounded `completion_text`; and
   widening the `edit_set` presence rule so the reproduced-unchanged refusal keeps the blocks it
   already built. Versions 1 and 2 stay decodable, byte-for-byte, forever.
5. **`scripts/prompt-template-adapter.py`**, a third adapter that loads
   `scripts/prompt-repair-adapter.py` by path — which loads the frozen base adapter by path — and
   near-copies only `measurement()` and `assemble()` (§3.2).
6. **A new frozen corpus scope**, `eval/prompt/canonical-v1t/` + `eval/tasks/prompt-v1t/`.
7. **One measured gate run and its checked-in evidence**, including a measured negative.
8. **The corrections of §1.2** applied to every document that carries the wrong claim (§9).

### 1.4 Non-goals

1. **No edit of `scripts/prompt-measurement-adapter.py`, `scripts/prompt-repair-adapter.py`,
   `eval/runners/run-coding-task.py`, `scripts/prompt-fixed-adapter.py`, or
   `scripts/prompt-snapshot-helper.py`.** All five are byte-frozen members of at least two corpus
   file-set manifests. `scripts/prompt-repair-adapter.py` is now frozen on exactly the terms
   `c4-repair-editset.md` §2.5 fixed for the base adapter: `eval/prompt/c4-editset-gate/` was
   measured against `canonical-v1e`'s exact scope digest.
2. **No mutation of `eval/prompt/canonical-v1/`, `canonical-v1r/`, `canonical-v1e/`, `gate/`,
   `c4-repair-gate/`, `c4-editset-gate/`, `eval/tasks/prompt-v1/`, `prompt-v1r/`, or
   `prompt-v1e/`.** §9.4 records the one exception and its exact boundary: a factual correction to
   the *prose* of `eval/prompt/c4-editset-gate/README.md`, which is not a file-set member and not a
   measured artifact.
3. **No change to the `FILE:` block grammar.** §2.3 states this as a hard constraint with its
   reason.
4. **No new attempt.** One repair, two attempts, `maximum_repair_loops: 1`.
5. **No provider, model, host, or decoding change.** Same `llama-server`, same build, same model
   digest, `temperature_micros: 0`, `seed_mode: PAIRED_FIXED`.
6. **No change to the evaluator's attempt loop, timing definition, or row schema.**
   `PROMPT_TASK_ROW` stays at `schema_version: 2` (§3.5).
7. **No corpus expansion and no task rewrite.** The three tasks, the three fixture repositories, and
   the three task definitions are byte-identical members. Only the *task prompts* change.
8. **No failure-memory feedback.** C5 memory events are still not written or read across attempts.
9. **No unconditional capture of the raw completion.** §3.3 fixes exactly when the text is
   persisted and §6.4 records why the unconditional form stays deferred.
10. **No prompt-quality, speed, provider-quality, or generality claim.** §6.3.

### 1.5 Gate statement, addressable arm, and the pre-committed counters

**The C4 gate is met when, on the three-task corpus × two variants × two paired samples at
`temperature_micros: 0` and `seed_mode: PAIRED_FIXED`, at least one (task, variant) pair records
attempt 1 `FAIL` and attempt 2 `PASS` in *both* of its paired samples** — the identical predicate
`c4-repair-measured.md` §1.4 fixed and `c4-repair-editset.md` §1.5 restated, unchanged, so all three
runs are directly comparable.

```text
gate MET  <=>  repair_recovery_paired_count >= 1
```

**Measured result, added after the run and corrected after review:** the persisted rows contain a
formal predicate value of 1, but the run made 24 provider calls against the pre-committed maximum
of 22. It therefore does **not** qualify for a `MET` gate verdict; the named qualification stopped
at a cost-contract breach. Independently, the underlying corpus capability is unchanged and the C4
gate is **not closed**. The only observed recovery repairs an
attempt-1 regression introduced by this capability and returns to the same patch that passed
first-shot in both prior runs. Section 11.4 owns the evidence and applies section 1.6 reading (b).

**The addressable arm, stated before the run.** Unlike C4E, whose arm was six of ten repair
attempts, this capability's statement reaches **every ran attempt** — the task prompt changes
attempt 1 and the template changes attempt 2. But the arm it is *built for* is the ten refused
attempts of §1.2. Three (task, variant) pairs are live for the gate:

| Pair | Why it is live |
| --- | --- |
| (`layer-precedence-frozen-module`, PARENT) | 4 of 4 attempts refused for reproducing the pinned file unchanged |
| (`layer-precedence-frozen-module`, CANDIDATE) | 2 attempt-1s refused unchanged; 2 attempt-2s refused for naming `src/legacy.py`, which the repair template never lists |
| (`duration-half-away-from-zero`, PARENT) | attempt 1 produces a real 716-byte patch and fails `TEST`; attempt 2 was refused unchanged in C4E and re-sent an identical patch in C4 |

The two `record-codec-round-trip` pairs are affected but are **not** the arm: their failure is a
byte-identical re-send, which §4.2's "your answer must differ from the answer shown above" addresses
only incidentally. (`duration-half-away-from-zero`, CANDIDATE) already passes at attempt 1 in both
runs and is not addressable by definition.

**Pre-committed secondary counter.** The corpus aggregate gains `edit_refusal_count`, the number of
ran attempts whose `measurement.edit_refusal` is not `NONE`. Its C4E value, **derived from the
`diagnostic_summary` strings because C4E did not persist the quantity, is 10 of 22**. C4T is the
first run that persists it.

```text
stated before the run:   edit_refusal_count < 10 is the secondary target
                         edit_refusal_count is reported whatever the gate says
                         the gate consumes repair_recovery_paired_count only
```

A value of 10 or more means the statement did not change behaviour at all, which is a different and
sharper result than "no recovery".

### 1.6 What a `NOT_MET` result means, fixed before the run

Two readings, and the evidence separates them:

**(a) `edit_refusal_count` falls but `repair_recovery_paired_count == 0`.** The edit policy was the
binding constraint on *format compliance* and is now stated, and what remains is **task difficulty**:
`layer-precedence-frozen-module` asks a 7B model to work around a frozen module through the single
editable file it is allowed to touch, and `record-codec-round-trip` fails by re-sending the same
reasoning, not the same format. The redirect is then a corpus capability — a task set whose
individual solvability by the pinned model is measured before it is used as a repair-gate corpus, so
the gate has a non-zero base rate — or C5 failure memory. It is **not** another prompt capability.

**(b) `edit_refusal_count` does not fall.** The model does not follow an instruction it has now been
given three times, in three positions, in the same prompt. Then neither the adapter (C4E) nor the
prompt (C4T) is the binding constraint, and the remaining axes are the model and the decoding
strategy: a larger model, or n>1 sampling above temperature 0. Both break greedy determinism and
therefore the paired predicate, so either is a **different experimental design**, not a tweak, and
it invalidates every C6 PARENT/CANDIDATE comparison that shares this corpus. That is named honestly
rather than presented as a next step.

**The prompt-size axis is refuted before the run and is not a redirect.** It was the hypothesis this
capability was chartered to test on a negative, and a static probe answers it (§2.8): the largest
repair prompt in either gate run is **16,904 bytes of a 65,536-byte budget (25.8 %)**; no section
was dropped on any of the twenty repair attempts in either run; and the refused
`layer-precedence-frozen-module` rows carry the **smallest** repair prompts in the corpus (8,348 and
11,804 bytes). Prompt size and refusal are anti-correlated in the measured data. No capability
should be spent on it.

---

## 2. Probe record

Static reads of checked-in bytes at `de56c60`. Each probe is reproducible with `python3` and no
network.

### 2.1 The refusal is not a parse failure, and the record cannot say so

`parse_file_blocks` (line 262) returns a list; `validated_edit_set` (line 306) refuses an empty list
and every out-of-allowlist path; `synthesized_patch` (line 428) refuses an empty diff:

```text
raise EditFormatError("the response reproduced the pinned files unchanged")   # line 433
```

`measurement()`'s `except EditFormatError` handler maps every one of these to
`outcome = "PATCH"` and `summary = str(failure)`, so `failure_kind: PATCH` conflates a parse failure,
a duplicate path, an over-large body, and a semantically empty answer. `failure_kind` is the field
every consumer reads; the distinguishing text is a free-form string that no schema constrains and no
aggregate counts. Three design documents read it wrong, which is the strongest available argument
that a code is needed (§3.3).

### 2.2 The task prompt already carries the worked example and the allowlist; the repair template
carries neither, and neither carries the unchanged-file rule

`eval/tasks/prompt-v1/layer-precedence-frozen-module/task-prompt.json` (4,771 bytes of text) ends
with a `Response format` section that already states, verbatim:

````text
For every file you change, emit exactly one block of this form:

FILE: <repo-relative-path>
```
<the complete new content of that file>
```

Rules:
- The path must be one of these editable paths, spelled exactly:
    src/settings.py
- A block naming any other path is rejected before the tests run.
- The block body is the entire file after your change: not a diff, not a
  fragment, and not an excerpt. …
````

So two of the four changes this capability was chartered to make — "one worked example" and "the
editable-path allowlist beside the requirement" — are **already present at attempt 1** and the model
violated them anyway (two `src/legacy.py` rows). What is absent everywhere is the rule the model
actually broke ten times: **a block whose body equals the file's current content is refused.**

`eval/prompt/canonical-v1e/repair-template.json`'s preamble says only "Change only the files the
task prompt declares editable" — it never lists them. The repair prompt is 6.7 KB of diagnostics
downstream of the attempt-1 statement, and the two `POLICY` rows are attempt 2.

### 2.3 The `FILE:` grammar is a hard constraint

`scripts/prompt-measurement-adapter.py` is byte-frozen in four corpora, and
`scripts/prompt-repair-adapter.py`, which calls its `validated_edit_set` verbatim, is byte-frozen in
two. The parser accepted every response it was given in twenty-two calls. **Version 3 must not
change the grammar — header spelling, fence rule, path stripping, block count, or body bound — only
the instruction text and the sections around it.** Any grammar change would mint a fourth adapter
for no measured reason and would break the one thing the evidence says already works.

### 2.4 The edit set is built and then deliberately discarded on the refusal path

`scripts/prompt-repair-adapter.py` `measurement()`:

```text
line 435   edits = frozen.validated_edit_set(response["content"], allowed_edits)
line 437   edit_set, edit_set_total_bytes = edit_set_blocks(frozen, edits, credential_value)
line 438   raw_patch = frozen.synthesized_patch(edits, source_root)      # raises here
…
line 465   except frozen.EditFormatError as failure:
line 466       outcome, generation_ns = "PATCH", None
line 467       edit_set, edit_set_total_bytes, patch_sha256 = None, None, None
```

Line 467 throws away a value line 437 already computed, redacted, and digested. That is not a bug —
it implements `c4-repair-editset.md` §3.3's presence rule, which says `edit_set` is `None` on
`PATCH` — but the rule was written when `PATCH` was believed to mean "nothing parsed". On the
`reproduced unchanged` sub-mode the blocks exist, and they are exactly the evidence that explains
the mode. §3.3 widens the rule, adapter-selected, so version-2 evidence stays valid.

Verified in the persisted evidence: every `failure_kind: PATCH` row in `c4-editset-gate` carries
`edit_set: null`, `edit_set_total_bytes: null`, `patch_sha256: null` — the canonical encoder omits
an `Option::None`, so the keys are absent from the wire form.

### 2.5 The raw completion is destroyed and no digest survives

`response["content"]` (`PROMPT_GENERATION_RESPONSE.content`) is read exactly once, at line 435, and
never assigned to a record field. The response document lives in
`tempfile.mkdtemp(prefix="prompt-measurement-adapter-")` and the frozen `finally` does
`shutil.rmtree(path, ignore_errors=True)` unconditionally; there is no retention flag, and
`scripts/prompt-evaluate.py` takes only `--request`, `--final-result-relative`, and
`--final-evidence-relative`. `provider_identities()` copies `provider_request_sha256`, which digests
the **request**. **Not one byte and not one digest of any completion exists in either gate's
evidence.**

### 2.6 The declared policy cannot live in the task definition

`eval/runners/run-coding-task.py` `load_task()` (line 378) is byte-frozen in four corpora and does:

```text
if set(task) != required:
    raise TaskError("task descriptor fields do not match schema version 1")
```

An extra key in `eval/tasks/prompt-v1t/<task>/task.json` would make the frozen validation runner
refuse the task. The declared policy therefore belongs on the **task manifest**
(`PROMPT_EVALUATION_TASK`), which the evaluator owns and the runner never reads. The frozen
adapter's `task_edit_policy()` is more tolerant — it uses `value.get(...)` — but the runner is not,
and the runner is the second reader.

### 2.7 The evaluator already loads the task definition

`c4-repair-editset.md` §11.3 deviation 4: `allowed_edits` membership is checked by
`scripts/prompt-evaluate.py` against the manifest-declared, digest-pinned task definition. So the
`POLICY` section's allowlist has a validated in-process source and needs no new file read and no
duplicated field (§4.4 records the rejected alternative).

### 2.8 The prompt-size hypothesis, tested and refuted

Reconstructed statically by loading `scripts/prompt-evaluate.py` as a module and re-running
`render()` and `assemble_repair_prompt()` against the checked-in assets and the persisted
diagnostics. **All 24 reconstructed prompts match the recorded `generation_request.user_text_sha256`
and every recomputed `assembled` matches the recorded `assembled_bytes` exactly.**

| Task | Variant | attempt-1 bytes | C4E attempt-2 assembled | C4 attempt-2 assembled |
| --- | --- | --- | --- | --- |
| `duration-half-away-from-zero` | PARENT | 4,926 | 11,417 | 10,804 |
| `duration-half-away-from-zero` | CANDIDATE | 7,876 | (passes) | (passes) |
| `layer-precedence-frozen-module` | PARENT | 6,721 | **8,348** | 8,123 |
| `layer-precedence-frozen-module` | CANDIDATE | 10,177 | **11,804** | 11,579 |
| `record-codec-round-trip` | PARENT | 5,760 | 15,308 | 13,801 |
| `record-codec-round-trip` | CANDIDATE | 9,833 | 16,904 | 16,129 |

Budget `max_prompt_bytes: 65,536`; `dropped_sections: []` on all twenty repair attempts across both
runs. The maximum is 25.8 % of budget and the refused rows are the smallest. §1.6 records the
consequence: the size axis is closed by evidence, not deferred.

### 2.9 Evaluator source pin and its size window — the tightest constraint in this design

`src/prompt_evaluate.align:8` pins `EVALUATOR_SOURCE_SHA256`; the launch window is four chunks,
`196,609…262,144` bytes. `scripts/prompt-evaluate.py` is **234,347 bytes** at `de56c60`, leaving
**27,797 bytes** of headroom. C4-REPAIR-EDITSET's own evaluator delta was **+17,291 bytes**
(217,056 → 234,347) for a fifth section kind, one renderer, one aggregate, and thirteen ladder rows.

This capability's delta is comparable or larger: a sixth section kind and its renderer, the
`edit_policy` record and its validation, a version-3 field list with presence rules, the ten-code
refusal vocabulary, one aggregate, and its ladder rows. **This is the top ledger risk (§3.11), it is
recorded before implementation, and §3.11 fixes what happens if it is exceeded.**

### 2.10 What the probes settle

1. No attempt in either run failed to parse; the measured mode is a semantically empty answer inside
   a syntactically correct block (2.1).
2. The worked example and the allowlist are already in the attempt-1 prompt and were violated
   anyway; the unchanged-file rule is stated nowhere (2.2).
3. The grammar is frozen and must not move (2.3).
4. The blocks that explain the mode are computed and discarded one line before the raise (2.4).
5. No completion text or digest survives anywhere (2.5).
6. The declared policy cannot go in the task definition; the frozen runner refuses extra keys (2.6).
7. The evaluator already holds the allowlist it needs to render (2.7).
8. The prompt-size hypothesis is refuted by the run's own numbers (2.8).
9. The evaluator has 27,797 bytes of headroom against a comparable prior delta of 17,291 (2.9).

---

## 3. Public-contract ledger

This ledger is the contract. If implementation discovers a different public promise, this table, the
closure matrix, the code, the fixtures, and the directly affected documentation are updated
together, before review.

### 3.1 The surface decision: a third adapter that imports the second

| Surface | Exact contract |
| --- | --- |
| New adapter | `scripts/prompt-template-adapter.py`. Same CLI as both earlier adapters (`--prompt-variant`, `--rendered-prompt`, `--sample-index`, `--paired-seed`, `--adapter-request`, `--result`, `--result-fd`), same `TASK_ADAPTER_REQUEST` shape and field order, same sealing, containment, and redaction. Two observable differences: it emits `TASK_MEASUREMENT` at `schema_version: 3`, and its `environment_probe.runtime_identity` is its **own** digest. |
| Repair adapter | `scripts/prompt-repair-adapter.py` is **byte-identical** and a member of `canonical-v1t`'s file-set manifest at its unchanged digest. Loaded as a module, never edited, never copied. |
| Base adapter | `scripts/prompt-measurement-adapter.py` is **byte-identical**, reached through `repair.base_adapter()` so exactly one frozen module object exists per process and `PR_SET_CHILD_SUBREAPER` has one writer. |
| Validation runner | `eval/runners/run-coding-task.py` is **byte-identical**, a shared member at its unchanged digest. |
| Loop owner | `scripts/prompt-evaluate.py`, unchanged in structure. |
| Adapter selection | Purely a corpus property: the task manifest's `cmd`/`argv` name the adapter and `measurement_adapter_runtime` pins its digest. **No new CLI flag and no new environment variable.** `eval/prompt/gate/environment-policy.json` is reused byte-identical. |
| Attempt bound | Unchanged: `1 + min(maximum_repair_loops, 1)`; the corpus sets `maximum_repair_loops: 1`. |

**Why a third adapter rather than editing the second.** `eval/prompt/c4-editset-gate/` was measured
against `canonical-v1e`'s exact scope digest, and `scripts/prompt-repair-adapter.py` is one of its
thirty-one file-set members. Editing it costs a merged evidence chain — the identical argument
`c4-repair-editset.md` §2.5 made for the base adapter, now applying to the second file for the same
reason. There is also no in-place option in principle: a `prompt-v1t` task must name a different
`argv` and a different `measurement_adapter_runtime`, which changes its own `content_sha256`, which
changes the corpus source digest.

**Why the chain loads the repair adapter, not the base adapter directly.** The template adapter
needs `edit_set_blocks` — the redact-then-digest-then-whole-block-bound sequence
`c4-repair-editset.md` §3.3 settled. Re-implementing it would put a **third** copy of the redaction
order in the tree, which is the exact class §3.2 of that document argued against. Loading the base
adapter separately would create two frozen module objects and two `prctl` writers. Reaching the
frozen module through the repair adapter's existing `base_adapter()` accessor and its `_BASE` guard
keeps one of each.

### 3.2 The import-chain contract

| Surface | Exact contract |
| --- | --- |
| Load mechanism | Identical to `c4-repair-editset.md` §3.2, applied one level up: read `scripts/prompt-repair-adapter.py` once into memory through the bounded read, digest those exact bytes, refuse unless equal to `REPAIR_ADAPTER_SHA256`, then execute **those same bytes** as a module. Verify-then-execute on one byte sequence; no read-hash-read window. |
| `REPAIR_ADAPTER_SHA256` | The digest of `scripts/prompt-repair-adapter.py` at `de56c60`, hard-coded in `scripts/prompt-template-adapter.py`. |
| `BASE_ADAPTER_SHA256` | **Not redeclared.** The template adapter asserts `repair.BASE_ADAPTER_SHA256` equals the `canonical-v1t` manifest's entry for the base adapter. One constant, one owner; a second literal would be a second place to drift. |
| Frozen module | Obtained as `frozen, raw = repair.base_adapter()`. The template adapter never calls `execute_base_adapter` itself and never sets or clears `PR_SET_CHILD_SUBREAPER`; it reads `frozen.CHILD_SUBREAPER_ENABLED` and refuses when false. |
| Four independent pins per file | For each of the two loaded files: (a) the hard-coded constant (base adapter's living in the repair adapter), (b) `canonical-v1t/corpus-file-set.manifest`, (c) each `prompt-v1t` task manifest's `artifacts` entry, verified by the snapshot helper **before and after every invocation**, and (d) for the base adapter, the three earlier manifests. All must agree; disagreement is fail-closed at ladder rows 2–5. |
| `__file__` | The repair module's `__file__` is set to its resolved path, so `repair.runtime_identity()` and the `project = Path(__file__).resolve().parent.parent` idiom resolve as they do standalone. Neither loaded module's `main()` is ever called. |
| Identity, cross-derived | `repair_adapter_runtime_identity` is computed from the verified in-memory bytes and asserted equal to `repair.runtime_identity()`, which re-reads the file. `base_adapter_runtime_identity` is taken from `repair`'s own cross-derivation, unchanged, and persisted at version 3 exactly as at version 2. |
| Own identity | The template adapter defines its own `runtime_identity()` over its own `__file__` and its own `environment_probe()` with `producer: "MEASUREMENT_ADAPTER"` (the role is unchanged) and `runtime_identity: "PYTHON:<own digest>"`. `prompt-v1t`'s `measurement_adapter_runtime` declares that value. Reusing an imported module's probe would persist the imported file's digest while running this file's code — the defect `c4-repair-editset.md` §2.3 found and closed. |
| Import-contract assertion | Immediately after execution, before any request is loaded, every consumed name from **both** modules is asserted present with the expected kind. Missing or wrong-kind is `ERROR`/`BASE_ADAPTER` before any external call. |
| Consumed from `repair` | `BASE_ADAPTER_SHA256`, `EDIT_SET_LIMIT`, `BaseAdapterError`, `base_adapter`, `edit_set_blocks`, `runtime_identity`. Everything else in that module is unused. |
| Consumed from `frozen` | `c4-repair-editset.md` §3.2's consumed-name table, unchanged, plus nothing new. The template adapter adds no name to it. |
| Bounded divergence, asserted | `scripts/run-prompt-template-adapter-smoke` extracts `measurement()` and `assemble()` from the template adapter and from the **repair** adapter, applies the normalizer `c4-repair-editset.md` §11.3 deviation 9 fixed (named functions only, full-line `#` comments removed, blank lines removed, trailing whitespace stripped, nothing else), and asserts the unified diff equals a checked-in golden. The existing repair-vs-frozen golden stays green, untouched. Two goldens, one per hop, each a reviewable artifact. |
| API privacy, restated | Both loaded modules expose undeclared internal APIs. **This capability consumes them and says so.** The mitigation is immutability: both files are digest-verified members of frozen corpora and cannot change without minting a new corpus, which is the same event that would require re-reviewing this file. Residual risk in §6.6. |

### 3.3 `TASK_MEASUREMENT`, `schema_version: 3`

Declared field order. The 23 version-1 fields and the 4 version-2 members are unchanged, in place,
byte-for-byte. New members are appended immediately before `content_sha256`.

```text
TaskMeasurement:
  … the 23 version-1 fields, unchanged (c4-repair-measured.md §3.3) …
  edit_set: Option<[EditSetBlock]>                 at 2
  edit_set_total_bytes: Option<i64>                at 2
  patch_sha256: Option<str>                        at 2
  base_adapter_runtime_identity: Option<str>       at 2
  edit_refusal: Option<str>                        new at 3
  completion_bytes: Option<i64>                    new at 3
  completion_sha256: Option<str>                   new at 3
  completion_text: Option<str>                     new at 3
  content_sha256
```

**`edit_refusal`, the ten-code vocabulary.** Each code maps one raise site of the frozen module:

| Code | Frozen raise site | Outcome |
| --- | --- | --- |
| `NONE` | no refusal | any |
| `NO_FILE_BLOCK` | `validated_edit_set` line 311 | `PATCH` |
| `HEADER_WITHOUT_BLOCK` | `parse_file_blocks` lines 279, 282 | `PATCH` |
| `UNTERMINATED_BLOCK` | `parse_file_blocks` line 295 | `PATCH` |
| `TOO_MANY_BLOCKS` | `parse_file_blocks` line 297 | `PATCH` |
| `DUPLICATE_PATH` | `validated_edit_set` line 318 | `PATCH` |
| `BODY_TOO_LARGE` | `validated_edit_set` line 320 | `PATCH` |
| `UNCHANGED_FILES` | `synthesized_patch` line 433 | `PATCH` |
| `PATH_NOT_EDITABLE` | `validated_edit_set` line 316 | `POLICY` |
| `PATH_ESCAPES_SOURCE` | `pinned_source` line 403 | `POLICY` |

**Mapping mechanism, and its honest limit.** The frozen exceptions carry no code, so the near-copy
maps `str(failure)` by exact prefix. That is fragile against a changing message and **safe here for
exactly one reason: the file is digest-pinned byte-identical in four corpus manifests**, the same
immutability argument §3.2 makes for the undeclared API. Two things make it checked rather than
assumed: the mapping is **total** — an unmapped message is `ERROR`/`ADAPTER`, never a silent `NONE`
— and `scripts/run-prompt-template-adapter-smoke` drives **every one of the nine raise sites against
the real loaded module** and asserts the code. A message change would turn it red before it could
persist a wrong code. The rejected alternative, re-detecting each condition structurally in the
near-copy, duplicates the frozen parser and is refused on §3.1's grounds.

**`edit_set`, widened at version 3, adapter-selected.**

| Member | At 1 | At 2 | At 3 |
| --- | --- | --- | --- |
| `edit_set` | absent | `Some` exactly when the attempt reached `execute_validation`; `None` on every refusal | `Some` exactly when `validated_edit_set` **returned**, which includes the `UNCHANGED_FILES` refusal; `None` on the eight refusals that raise before it returns, on `ERROR`-before-parse, and on the declared-patch path |
| `edit_set_total_bytes` | absent | `Some` iff `edit_set` is `Some` | same |
| `patch_sha256` | absent | `Some` iff `patch_size_bytes > 0` | same |
| `base_adapter_runtime_identity` | absent | always `Some` | same |
| `edit_refusal` | absent | absent | **always `Some`**, `NONE` when no refusal occurred |
| `completion_bytes` | absent | absent | `Some` exactly when a provider response was received |
| `completion_sha256` | absent | absent | `Some` iff `completion_bytes` is `Some` |
| `completion_text` | absent | absent | see below |

The version-2 rule is kept verbatim for version-2 documents rather than retro-fitted, because
`eval/prompt/c4-editset-gate/` is a merged version-2 chain whose `PATCH` rows carry `edit_set`
absent. Requiring the wide rule at version 2 would reject merged evidence — precisely the incident
`c4-repair-editset.md` §11.3 deviation 2 records. The rule is selected by the adapter the corpus
names, in all four owners.

**`completion_text`, conditional by design.** `Some` **exactly when `edit_refusal` is one of the
eight codes for which `validated_edit_set` did not return** — the class where no structured
substitute exists — **and** the encoded result fits (below). `None` on `NONE`, on `UNCHANGED_FILES`,
and on the declared-patch path, because on those paths `edit_set` carries the model's own bodies
already.

This is the decision `c4-repair-editset.md` §6.4 deferred, taken on its own stated terms. That
deferral's resume condition was "a capability whose question is about response format … which would
want the *unparsable* text", and §1.2 shows the text has never yet been unparsable. Persisting it
unconditionally would therefore buy nothing measured and would move every model completion in the
corpus into a persisted artifact. Persisting it only where nothing else can explain the failure
means **the mode can never again be unexplained**, at the smallest disclosure surface that achieves
it. `completion_bytes` and `completion_sha256` are persisted **always**, so copy-forward across
attempts and across paired samples becomes a measured fact at zero disclosure cost, and they are the
trigger that would earn a wider capture later.

**Bounds and the whole-field drop.** `COMPLETION_LIMIT = 32,768`, applied by the frozen
`bounded_text` after `redact_credential`, exactly as the diagnostics are bounded. `completion_bytes`
is the redacted completion's **full** length before bounding; `completion_sha256` digests the full
redacted bytes, not the bounded excerpt, so the digest identifies the response and the excerpt is a
view of it. The producer then encodes the result **without** `completion_text` first and includes it
only if `len(canonical_bytes(value)) <= RESULT_LIMIT` (262,144); otherwise it persists `None` and
the identity fields survive. Whole-field, never partial. Without this rule a control-character-dense
completion could expand under JSON escaping past `RESULT_LIMIT` and turn a real measurement into
`ERROR` — a new failure mode introduced by the capture itself, which is not acceptable.

**Digests are over redacted bytes**, unchanged from `c4-repair-editset.md` §3.3 and for the same
reason: a persisted digest of unredacted bytes is a credential oracle. `LOCAL_OPENAI` uses no
credential, so on this corpus the two are identical.

**Invariants tying the new fields to the old ones**, all checked (§3.9):

```text
edit_refusal == "NONE"            <=>  status in {PASS} or failure_kind in {TEST, CLEANUP, CONTAINMENT, ADAPTER}
edit_refusal in the PATCH class    =>  failure_kind == "PATCH" and patch_size_bytes == 0
edit_refusal in the POLICY class   =>  status == "POLICY_VIOLATION" and failure_kind == "POLICY"
edit_refusal == "UNCHANGED_FILES"  =>  edit_set is Some and patch_sha256 is None
edit_refusal in the eight no-set codes => edit_set is None
completion_sha256 is Some         <=>  completion_bytes is Some
completion_text is Some            =>  edit_refusal is one of the eight no-set codes
completion_text is Some            =>  len(completion_text) <= COMPLETION_LIMIT
diagnostic_summary                 =   the frozen message whose prefix selected edit_refusal, when
                                       edit_refusal != "NONE"
```

The last one is the cheapest cross-check in the design: it holds the code and the string to one
producer decision, and it is what makes the mapping falsifiable in the persisted evidence rather
than only in the smoke.

### 3.4 `EDIT_POLICY`, the declared edit policy

A new record, carried as an optional member of `PROMPT_EVALUATION_TASK` at its unchanged
`schema_version: 1`, under the same optional-member mechanism `repair_template_path` /
`repair_template_sha256` already use (`scripts/prompt-evaluate.py` line 320's per-kind optional
set).

```text
EditPolicy:
  schema_version                1
  artifact_kind: EDIT_POLICY
  maximum_file_blocks: i64      32
  maximum_edit_bytes: i64       262144
  refuse_unchanged_files: bool  true
  content_sha256
```

| Surface | Exact contract |
| --- | --- |
| Presence | `Some` exactly when the task's `argv` names `scripts/prompt-template-adapter.py`; absent otherwise. Adapter-selected, never version-selected, on `c4-repair-editset.md` §11.3 deviation 2's rule. |
| Defaults | The values above are today's constants in `scripts/prompt-measurement-adapter.py` (lines 85-86), `scripts/prompt-gate-validator.py` (lines 398-399), and `scripts/prompt-evaluate.py` (lines 264-265), plus `synthesized_patch`'s unstated refusal. **Declaring them changes no behaviour**; it makes an emergent property a checked contract and gives the renderer one validated source. |
| Not a knob | `maximum_file_blocks` and `maximum_edit_bytes` must **equal** the evaluator's own constants, and `refuse_unchanged_files` must be `true`, because the pinned adapters enforce exactly those values and nothing else. A differing value is refused before any provider call, not silently honoured. Changing a value is a new adapter and a new corpus, which is what is true today; the field says so. |
| Refusals | `INVALID_INPUT` / `EDIT_SET` for every arm (§3.9 rows 8-11). |
| No `editable_paths` member | Rejected. The allowlist already has exactly one owner, the digest-pinned task definition's `allowed_edits`, which the evaluator already loads (§2.7). Copying it into the manifest would create a second writer for one value and a new drift site in the class §3.5 is built to prevent, in exchange for saving nothing. |
| Constant parity | An owner test asserts `MAXIMUM_FILE_BLOCKS` and `MAXIMUM_EDIT_BYTES` are equal across `scripts/prompt-measurement-adapter.py`, `scripts/prompt-repair-adapter.py` (transitively, through its consumed-name pin), `scripts/prompt-template-adapter.py`, `scripts/prompt-evaluate.py`, and `scripts/prompt-gate-validator.py`. Five declarations, one asserted value. This is the first check that the three existing copies agree. |

### 3.5 Persisted rows and evidence: what changes and what does not

Built up front, because the prior incident class is a persisted field list drifting away from what
its producer emits.

| Artifact | Version | Change |
| --- | --- | --- |
| `TASK_MEASUREMENT` | 2 → **3** | Four `Option` members (§3.3) plus the widened `edit_set` rule. Versions 1 and 2 unchanged and permanently decodable. |
| `EDIT_POLICY` | **new, 1** | §3.4. |
| `EDIT_SET_BLOCK` | 1, **unchanged** | Same record; only when it is emitted changes. |
| `REPAIR_PROMPT_TEMPLATE` | 1, **unchanged shape** | `section_headers` gains a `POLICY` key. A new template *file* in a new corpus, not a new schema. |
| `PROMPT_EVALUATION_TASK` | 1, **unchanged** | Gains the optional `edit_policy` member and the new `task_prompt_path`. The field list moves; the version does not, on the mechanism the repair-template pair already uses. |
| `TASK_PROMPT` | 1, **unchanged** | Three new files, same record shape (§4.3). |
| `PROMPT_TASK_ROW` | 2, **unchanged** | No new field. The measurement's version stays decoupled from the row's, as at C4E. |
| `TaskAttemptRecord` | 1, **unchanged** | The refusal and the completion belong to the measurement, whose producer is the adapter. Putting either on the attempt record gives it a second writer and bumps four documents in lockstep for zero new row fields — `c4-repair-editset.md` §3.5's rejected alternative, rejected again on the same grounds. |
| `RepairPromptSource` | 1, **unchanged** | `POLICY` is a new member of the existing `included_sections` / `dropped_sections` vocabulary, not a new field. |
| `TaskAggregate`, `CorpusAggregate` | version-2 `Option` block **extended** | `parent_edit_refusal_count` / `candidate_edit_refusal_count` on the task aggregate, `edit_refusal_count` on the corpus aggregate. Adapter-selected presence, per §3.4's rule. |
| `PROMPT_EVALUATION_RESULT`, `PROMPT_EVALUATION_EVIDENCE`, `PROMPT_EXPECTED_INPUT_DIGEST` | 2, **unchanged** | |
| `ENVIRONMENT_PROBE` | 1, **unchanged** | `producer` stays `MEASUREMENT_ADAPTER`; only `runtime_identity` differs. |
| `TASK_ADAPTER_REQUEST`, `PROMPT_SCOPE`, `GENERATION_POLICY`, `EVALUATION_PROVIDER_CONTROL`, `PROMPT_ACCEPTANCE_POLICY`, `ENVIRONMENT_POLICY`, `PROVIDER_SERVICE_PROBE` | unchanged | |

**The measurement version stays a checked function of the corpus**, extending `c4-repair-editset.md`
§3.5's rule to three adapters:

```text
argv names scripts/prompt-template-adapter.py      => every ran attempt's measurement.schema_version == 3
argv names scripts/prompt-repair-adapter.py        => … == 2
argv names any other adapter                       => … == 1
```

**The field-list parity table, built before implementation.** Every place a `TASK_MEASUREMENT` field
list exists, what it is today, and what it becomes. Fourteen places at C4E; the same fourteen plus
one, because a third producer joins.

| # | Place | File | Role | Today | At version 3 |
| --- | --- | --- | --- | --- | --- |
| 1 | `assemble()`'s literal dict | `scripts/prompt-measurement-adapter.py` | producer | 23 keys, v1 | **frozen; byte-identical** |
| 2 | `assemble()`'s literal dict | `scripts/prompt-fixed-adapter.py` | producer | 23 keys, v1 | **frozen; byte-identical** |
| 3 | `assemble()`'s literal dict | `scripts/prompt-repair-adapter.py` | producer | 27 keys, v2 | **frozen; byte-identical** |
| 4 | `assemble()`'s literal dict | `scripts/prompt-template-adapter.py` | producer | — | **new; emits v3 only, 31 keys** |
| 5 | `TASK_MEASUREMENT_FIELDS` / `_V2_FIELDS` | `scripts/prompt-evaluate.py` | consumer | 23 / 27, version-selected | **`_V3_FIELDS` = 31**, three-way selected |
| 6 | `TaskMeasurement` record | `src/prompt_artifacts.align` | consumer | 27 members | **+4 `Option` members** before `content_sha256` |
| 7 | `verifier_measurement_valid` | `src/prompt_score.align` | validator | `1 or 2` | **`1 or 2 or 3`** + version shape + the widened `edit_set` rule |
| 8 | `verifier_measurement_equal` | `src/prompt_score.align` | field-wise equality | 27 comparisons | **31** — the single highest-value line in the diff, exactly as at C4E |
| 9 | `validate_measurement_version`, `validate_measurement_probe`, `EDIT_SET_BLOCK_FIELDS` | `scripts/prompt-gate-validator.py` | validator | v2 rules, wire-form presence | **+v3 rules, wire-form presence**, plus `EDIT_POLICY_FIELDS` |
| 10 | measurement constructors ×3+ | `src/prompt_verifier_smoke.align` | fixtures | v1 and v2 cases | **+4 `None`** on v2 cases, plus `measurement_v3` and its defect cases |
| 11 | `attempt_measurement` | `scripts/prompt_gate_fixture.py` | fixture | emits v2 | **emits v3**, tasks name the template adapter, one row with the three `Option::None` members **omitted** exactly as the wire omits them |
| 12 | `repair_measurement` / `editset_measurement` | `scripts/run-prompt-evaluate-smoke` | fixture | v1/v2 wrappers | **+`template_measurement` wrapper** |
| 13 | `SYNTHETIC_MEASUREMENT` / `editset_measurement` | `scripts/run-prompt-render-parity-smoke` | fixture | v1/v2 wrappers | **+`template_measurement` wrapper** |
| 14 | §3.3's declared order | this document | contract | 27 | **31** |
| 15 | row-bearing fixtures | `src/prompt_render_smoke.align`, `src/prompt_render_parity_smoke.align`, `eval/fixtures/c6-prompt-state/templates.jsonl` | fixtures | no measurement field list | **untouched**, per C4E's finding (b) |

**Entry 8 is called out because its omission would fail nothing**: ladder row 22 (`row.measurement`
byte-equal to the final attempt that ran) would still pass while comparing 27 of 31 fields. It was
the highest-value line at C4E and it is again.

**Entry 9 carries C4E deviation 13's rule forward without restating it wrongly**: the gate
validator's version-3 presence rule reads the **wire form**, where the canonical encoder omits an
`Option::None`. Only `edit_refusal` is unconditionally present at version 3; `completion_bytes` and
`completion_sha256` are present whenever a response was received; `completion_text` is usually
absent. Entry 11's omitted-member fixture row is what makes that falsifiable.

The two aggregate records are walked the same way: `TaskAggregate` gains two members and
`CorpusAggregate` one, in `src/prompt_artifacts.align`, `scripts/prompt-evaluate.py`,
`scripts/prompt-gate-validator.py`, `scripts/prompt_gate_fixture.py`, and
`src/prompt_verifier_smoke.align` — five places, all five changed together, all adapter-selected.

### 3.6 New and reused corpus assets

Nothing under `eval/prompt/canonical-v1/`, `canonical-v1r/`, `canonical-v1e/`, `gate/`,
`c4-repair-gate/`, `c4-editset-gate/`, `eval/tasks/prompt-v1/`, `prompt-v1r/`, or `prompt-v1e/` is
modified, moved, or deleted, with the single prose exception of §9.4.

| Path | Contents |
| --- | --- |
| `scripts/prompt-template-adapter.py` | §3.1, §3.2. A corpus member, mode `100755`. |
| `eval/tasks/prompt-v1t/<task>/task-prompt.json` ×3 | `TASK_PROMPT`, `schema_version: 1`. Byte-for-byte the `prompt-v1` task prompt except the §4.3 delta and the recomputed `content_sha256`. |
| `eval/tasks/prompt-v1t/<task>.json` ×3 | byte-for-byte the `prompt-v1e` manifest except `argv` and `cmd` naming the template adapter, `measurement_adapter_runtime` at its digest, `task_prompt_path` pointing at the new task prompt, `generation_policy_path` and `repair_template_path` pointing at `canonical-v1t`, the added `edit_policy` record, one added `artifacts` entry for the template adapter (both earlier adapters' entries stay), and the recomputed `content_sha256`. `context_sources_path`, `task_definition_path`, `task_definition_sha256`, `repo_path`, `repo_revision`, `validation_runner_path`, `validation_runner_sha256`, `validation_argv`, `snapshot_*`, `regression_limits`, and the rest of `artifacts` are `prompt-v1e`'s. |
| `eval/prompt/canonical-v1t/repair-template.json` | `REPAIR_PROMPT_TEMPLATE`, `schema_version: 1`, `template_id: prompt-v1t-repair-v1`, **six** section headers. §4.2. |
| `eval/prompt/canonical-v1t/generation-policy.json` | `canonical-v1e`'s policy with `generation_policy_id: prompt-v1t-generation-v1` and the `provider_service_revision` **re-derived at freeze time, never inherited**. `provider_control_sha256`, `max_prompt_bytes: 65536`, `max_tokens: 4096`, `temperature_micros: 0`, `seed_mode: PAIRED_FIXED`, `seed_base: 20260824` unchanged. |
| `eval/prompt/canonical-v1t/corpus.json` | `corpus_id: prompt-v1t`, naming the three `prompt-v1t` manifests |
| `eval/prompt/canonical-v1t/corpus-file-set.manifest` | **31 entries**: 22 members carried from `canonical-v1e` at **identical digests** (11 fixture files, the runner, the three task definitions, the three context-sources files, and four scripts), the 3 new task prompts, the 3 new task manifests, the new repair template, the new generation policy, and `scripts/prompt-template-adapter.py`. Of the 22, **21 carry identical digests in all four manifests**; `scripts/prompt-repair-adapter.py` is shared with `canonical-v1e` only. |
| `eval/prompt/canonical-v1t/scope.json` | `corpus_id: prompt-v1t`, the new `corpus_revision`, the new `generation_policy_sha256`; `acceptance_policy_sha256`, `base_prompt_sha256`, `repo_prompt_sha256` **identical to `canonical-v1e`'s** and therefore to `canonical-v1`'s |
| `eval/prompt/canonical-v1t/prompt-activation-baseline-v1t.json` | the baseline activation over the new scope; the effective variant is byte-identical to `baseline-v1e`'s |
| `eval/prompt/canonical-v1t/README.md` | what is frozen, what is reused by digest, and the rule that it is never edited after measurement |
| `eval/prompt/c4-template-gate/` | the measured evidence: `c4-template-evaluation.json`, `c4-template-evaluation-evidence.json`, `c4-template-gate-record.json`, `README.md` |
| `scripts/freeze-canonical-v1t` | mints the above reproducibly, as `freeze-canonical-v1e` does for `v1e` |
| `scripts/run-c4-template-gate` | the run driver, mirroring `scripts/run-c4-editset-gate` |

**The base and repo prompts are reused byte-identical, and that is load-bearing** (§4.3): they are
what distinguishes PARENT from CANDIDATE, so leaving them untouched is what keeps the C6 contrast
the same contrast it was in three prior runs.

**The acceptance policy is reused byte-identical and is not relaxed**:
`maximum_repair_loop_regression_count: 0`, and a repair-loop regression, if one occurs, is the
measured result.

### 3.7 Provider topology and provider-revision evidence

Unchanged from `c4-repair-editset.md` §3.7 in every particular: `bwrap` inside a Linux aarch64
container built from the C6 measurement image plus `bwrap` and `socat`; generation to a
container-local `socat` forwarder at `127.0.0.1:18080` proxying to the host `llama-server`; the
frozen provider control; `cap-add SYS_ADMIN` plus unconfined `seccomp`, `apparmor`, `systempaths`,
published in the run record; `scripts/probe-provider-service` emitting a fail-closed
`PROVIDER_SERVICE_PROBE`; and the in-band model-id check as the second half of the pair.

**The provider service revision is re-derived at freeze time and never inherited.** If the host
binary or the model file has moved, `canonical-v1t`'s policy records the observed values and the
probe fails closed against them. The measurement-risk note carries over unchanged: neither the host
probe nor the in-band model id observes that the process answering inside the container is the
process whose binary was hashed.

### 3.8 Scoring and aggregates

One new counted quantity, computed by the evaluator and **independently recomputed by the pure Align
verifier**, never trusted from the persisted document:

```text
task_aggregate:      parent_edit_refusal_count, candidate_edit_refusal_count
corpus_aggregate:    edit_refusal_count
```

An attempt contributes when it ran (not `SKIPPED`) and its `measurement.edit_refusal != "NONE"`.
Both extend the existing recomputation in `verifier_task_repair_aggregate_matches`
(`src/prompt_score.align:5266`) and `verifier_corpus_repair_aggregate_matches` (`:5288`). Presence
is adapter-selected: a `canonical-v1e` or earlier corpus recomputes the member as **absent**, never
as zero, because a corpus whose adapter does not persist `edit_refusal` cannot define the quantity.

`repair_recovery_paired_count`, `repair_recovery_count`, `repair_attempt_count`,
`repair_editset_attempt_count`, `repair_loop_regression_count`, the `REPAIR_LOOPS` variant-symmetric
check, and the C6 acceptance arms are all **unchanged in mechanism**. `verifier_reason_capacity`
(`:5191`) does not move: no new per-pair serious-regression reason is added.

**The C4 gate consumes `repair_recovery_paired_count` only.** `edit_refusal_count` is the
pre-committed secondary of §1.5 and the C6 acceptance verdict is recorded alongside as secondary
evidence; neither is a gate input.

### 3.9 Validation order

First applicable row wins. This ladder **extends** `c4-repair-editset.md` §3.9 and, through it,
`c4-repair-measured.md` §3.8; unchanged rows there are not restated. Rows 1–13 run before any
provider call or workspace mutation.

| # | Check | Failure |
| --- | --- | --- |
| 1 | Every row of `c4-repair-editset.md` §3.9 that is unchanged | as recorded there |
| 2 | The template adapter's `REPAIR_ADAPTER_SHA256` equals the digest of the bytes it read, and those bytes are what it executes | `ERROR` / `BASE_ADAPTER` |
| 3 | `REPAIR_ADAPTER_SHA256` equals the `canonical-v1t` manifest's entry for `scripts/prompt-repair-adapter.py`, and that entry equals `canonical-v1e`'s | `INVALID_INPUT` / `SOURCE` |
| 4 | `repair.BASE_ADAPTER_SHA256` equals the `canonical-v1t` manifest's entry for the base adapter, and that entry equals `canonical-v1`'s, `canonical-v1r`'s, and `canonical-v1e`'s | `INVALID_INPUT` / `SOURCE` |
| 5 | Each `prompt-v1t` task's `artifacts` list declares **all three** adapters, and the snapshot helper verifies all three before and after each invocation | `INVALID_INPUT` / `SOURCE` |
| 6 | Every consumed name from both loaded modules exists with the expected kind | `ERROR` / `BASE_ADAPTER` |
| 7 | `frozen.CHILD_SUBREAPER_ENABLED` is true; the template adapter set no `prctl` itself | `ERROR` / `ADAPTER` |
| 8 | `edit_policy` is present exactly when `argv` names the template adapter | `INVALID_INPUT` / `EDIT_SET` |
| 9 | `edit_policy` decodes as `EDIT_POLICY` with the exact field tuple and a valid `content_sha256` | `INVALID_INPUT` / `EDIT_SET` |
| 10 | `edit_policy.maximum_file_blocks == 32` and `maximum_edit_bytes == 262144`, equal to the evaluator's own constants | `INVALID_INPUT` / `EDIT_SET` |
| 11 | `edit_policy.refuse_unchanged_files == true` | `INVALID_INPUT` / `EDIT_SET` |
| 12 | The repair template decodes and its `section_headers` keys equal `("STATUS","POLICY","EDITSET","SUMMARY","STDOUT","STDERR")` exactly, and its digest equals the manifest's `repair_template_sha256`. The four-kind and five-kind sets stay admissible for their own corpora | `INVALID_INPUT` / `TEMPLATE` |
| 13 | The task prompt decodes as `TASK_PROMPT` and its digest matches the manifest's artifact entry | `INVALID_INPUT` / `SOURCE` |
| — | *attempt 1 runs* | |
| 14 | The adapter result decodes as `TASK_MEASUREMENT` with `schema_version` in `{1,2,3}` | `ERROR` / `ADAPTER` |
| 15 | Every version-3 key is present at 3 and absent at 1 and 2, at the **adapter boundary** (the field-tuple check); on the **persisted** document the wire-form rule of §3.5 entry 9 applies | `INVALID_INPUT` / `SCHEMA` |
| 16 | The measurement version equals the version the task's declared adapter runtime requires (§3.5) | `INVALID_INPUT` / `SCHEMA` |
| 17 | `edit_refusal` is `Some` at version 3 and a member of the ten-code vocabulary | `INVALID_INPUT` / `EDIT_SET` |
| 18 | The §3.3 invariants tying `edit_refusal` to `status`, `failure_kind`, `patch_size_bytes`, `edit_set`, and `diagnostic_summary` | `INVALID_INPUT` / `EDIT_SET` |
| 19 | `completion_sha256` is `Some` iff `completion_bytes` is `Some`; when `Some` it is a valid lowercase 64-hex digest; `completion_bytes >= 0` | `INVALID_INPUT` / `EDIT_SET` |
| 20 | `completion_text` is `Some` only for the eight no-set refusal codes, and is at most `COMPLETION_LIMIT` bytes | `INVALID_INPUT` / `EDIT_SET` |
| 21 | Every version-2 rule of `c4-repair-editset.md` §3.9 rows 13-17, with the widened `edit_set` rule at version 3 | as recorded there |
| 22 | Repair eligibility, unchanged: cleanup and containment passed, and at least one of `SUMMARY`/`STDOUT`/`STDERR` is non-empty. **Neither `EDITSET` nor `POLICY` makes a repair eligible** | attempt 2 `SKIPPED` / `REPAIR_INPUT_UNAVAILABLE` |
| 23 | The assembled repair prompt is valid UTF-8 and `<= max_prompt_bytes` after the §4.5 ladder | attempt 2 `SKIPPED` / `REPAIR_PROMPT_BUDGET` |
| 24 | The repair prompt is byte-equal to `assemble(template, attempt 1's persisted fields)`, with `POLICY` re-derived from the digest-pinned task definition and the declared policy, and `EDITSET` from the persisted `edit_set` | `ERROR` / `REPAIR_RENDER` |
| — | *attempt 2 runs; rows 14–21 repeat for it* | |
| 25 | `edit_refusal_count` equals the recomputed count of ran attempts whose `edit_refusal != "NONE"` | `INVALID_INPUT` / `AGGREGATE` |
| 26 | `verifier_measurement_equal` compares **all 31** version-3 fields when both sides are version 3 | `INVALID_INPUT` / `MEASUREMENT_BINDING` |

Rows 22 and 23 are terminal-but-not-error: the row closes with a recorded `SKIPPED` repair attempt
carrying its reason.

### 3.10 Ownership, allocation, lifetime, cleanup

| Surface | Exact contract |
| --- | --- |
| Loaded modules | Two module objects per adapter process — the repair module and, through its `_BASE` guard, the frozen module — created before the request is loaded and living until the process exits. Never reloaded, never mutated, never shared across invocations; each attempt is its own process. |
| Completion bytes | The redacted completion is materialized once, from `response["content"]`, digested at full length, bounded to `COMPLETION_LIMIT`, and encoded into the result. It is never re-read, never written to disk by this adapter, and never retained past `assemble()`. The frozen scratch directory and its `shutil.rmtree` are unchanged. |
| Edit-set bytes | Unchanged from `c4-repair-editset.md` §3.10, with one difference: on the `UNCHANGED_FILES` path the already-built blocks are **kept** rather than discarded. Nothing is re-derived; the value is the one line 437 computed. |
| Patch bytes | Unchanged: `ProducedInput` owns the synthesized patch and the frozen `finally` closes it; `patch_sha256` is computed before construction. On `UNCHANGED_FILES` no patch exists and `patch_sha256` is `None`. |
| Attempt workspaces | Unchanged: one workspace and result path per attempt, fixed-width `-a1`/`-a2` suffixes on a fixed-depth run directory, bounded and asserted components. Prior incident class: `ENAMETOOLONG`. |
| Cleanup order | Unchanged, including the rule that a cleanup failure in attempt 1 suppresses attempt 2 as `SKIPPED`/`REPAIR_INPUT_UNAVAILABLE`. |
| Align side | The four new `Option` members are read through a `borrow` binding (§6.7); `edit_set` continues to be walked with the proven `Option<array<T>>` idiom. |
| Credentials | Unchanged. `credential_env_name` is never rendered, never logged, never enters a prompt. Redaction runs before bounding and before digesting, for the completion exactly as for the diagnostics. |

### 3.11 The evaluator source pin and its size window — the top ledger risk

| Surface | Exact contract |
| --- | --- |
| `EVALUATOR_SOURCE_SHA256` | `src/prompt_evaluate.align:8` is updated to the new `scripts/prompt-evaluate.py` digest in the same commit that changes the file. A stale pin is a hard `INVALID_INPUT` at launch. |
| Size window | Four chunks, `196,609…262,144` bytes. The file is **234,347 bytes** at `de56c60`, so the delta has **27,797 bytes** of headroom. |
| Comparable prior delta | C4-REPAIR-EDITSET's evaluator delta was **+17,291 bytes** for a strictly smaller surface (one section kind, one renderer, one aggregate, thirteen ladder rows). This capability adds a sixth kind and renderer, the `EDIT_POLICY` record and four ladder rows for it, a three-way-selected version-3 field list with presence rules, a ten-code vocabulary and its invariants, one aggregate, and thirteen ladder rows. |
| Checkpoint | **The evaluator side is implemented first**, and its realized delta is measured at the first coherent batch, before the Align side and before the freeze. |
| If the delta exceeds 24,000 bytes | The capability **returns to this ledger before continuing.** The two options are (a) moving rows 17-21 wholly to the Align verifier and the gate validator, leaving the evaluator with the adapter-boundary field-tuple check only, or (b) widening the launch window to five chunks — a public change to the launch contract, which comes back here before it is taken and is not taken silently. |
| What is not acceptable | Splitting the evaluator into a second file to dodge the window. |

### 3.12 Ledger dimensions

| Dimension | Answer |
| --- | --- |
| Exact commands and operands | §3.1 (no new flag, no new environment variable); §6.1 (owners); §6.2 (`make c4-template-gate` and its three explicit inputs) |
| Inputs and defaults | §3.4 (`maximum_file_blocks` 32, `maximum_edit_bytes` 262,144, `refuse_unchanged_files` true); §3.6. `maximum_repair_loops` stays 1; `max_prompt_bytes` stays 65,536; `EDIT_SET_LIMIT` stays 16,384; `COMPLETION_LIMIT` is a new producer-side constant, 32,768; `REPAIR_POLICY_LIMIT` is a new evaluator-side constant, 2,048 (§4.4) |
| Results, statuses, errors, precedence | §3.3 (the ten-code vocabulary and the presence rules), §3.4 (the policy refusals), §3.9 (26-row first-applicable ladder) |
| Ownership, lifetime, allocation, cleanup | §3.10 |
| Owner module | `scripts/prompt-template-adapter.py` owns `edit_refusal` and the three completion members. `scripts/prompt-evaluate.py` owns rendering, `edit_policy` validation, the ladder rows above the adapter boundary, and the aggregate. `src/prompt_score.align` owns independent recomputation. No field has two writers (§3.5) |
| Text and wire boundary | Canonical UTF-8 JSON, declaration order, integer-only comparisons, `Option::None` omitted. `completion_text` is bounded by the frozen `bounded_text`, which appends `TRUNCATION_MARKER` and decodes with `errors="replace"`, so no UTF-8 code point is split and embedded NUL is impossible; the JSON encoder escapes control characters, which is why the whole-field `RESULT_LIMIT` rule of §3.3 exists |
| Persisted/cache identity | `artifact_kind` + `schema_version`, nominal; `content_sha256` over the canonical preimage with only the record's own digest field blanked. No cache is introduced |
| Schema version | `TASK_MEASUREMENT` 2 → 3; `EDIT_POLICY` new at 1; task and corpus aggregates gain one `Option` member each inside their existing version-2 block. Every other record, listed in §3.5, is unchanged |
| Validation order | §3.9 |
| Prerequisites | §6.5 |
| CLI, build, and environment inputs | §3.1. The evaluator reads exactly one environment value today (the provider credential) and continues to. Build inputs change through §3.11's pin and one new `.PHONY` target (§6.2) |
| Acceptance evidence | §6.1 (owner tests, no provider), §6.2 (the named gate qualification) |
| Metrics | §6.3 |
| Cost ceiling | §6.2: **60 minutes wall clock**, recorded before implementation |
| Minimum tool/platform versions | Docker 28.5.1; `c4-repair-measure:latest` on linux/aarch64 with `bwrap`, `prlimit`, `git`, `/usr/bin/python3`, `socat`; llama.cpp build 10566 (`bb4caa754`); Align `3a34febe912db5096c58c74fede36ff53f223e04` per `.align-revision` |
| Milestones not consuming a later slice | §1.4 and §6.4: one repair, three tasks, no memory feedback, no grammar change, no provider change, no corpus expansion |
| Runtime-inspection fields | `edit_refusal`, `completion_bytes`, `completion_sha256`, `completion_text` are producer-owned measured values written by the process that held the bytes; no reflection, no artifact re-read at report time |
| Normative examples | §4.2's template text, §4.3's task-prompt delta, and §4.4's rendered `POLICY` form are the only normative examples; the render-parity smoke turns all three into byte goldens |

**Ledger field completion.** *Cache identity* is `N/A`: no cache is introduced, nothing is memoized
between attempts, and the loaded modules are per-process. *Generic monomorphization,
compiler-interface serialization, native ABI* are `N/A`: the changed records are concrete and no
`extern` symbol, FFI boundary, or compiler surface is touched. *Concurrency and shared process
state* are `N/A`: attempts are strictly sequential within a row and rows within the run; the only
shared resource is the single `llama-server`, whose serialization is its own and is unchanged.
*Platform-local performance claims* are `N/A`: §6.3 makes no speed claim, so no native platform
profile is selected. The `ppm`-floor rule of `docs/specs/c8-speed-first.md` §1 is `N/A` because no
seam is optimized; §6.2's ceiling is a **run-cost** ceiling under the performance row's "cost ceiling
recorded before implementation" clause, not an optimization ceiling. *Minimum-version acceptance
evidence* is supplementary only: the gate runs on one host and claims nothing about others.

---

## 4. The prompt contract, version 3

### 4.1 Principle

Unchanged from `c4-repair-measured.md` §4.1 and `c4-repair-editset.md` §4.1: the repair prompt is a
**pure, total function of bytes the result document already persists**, plus one sealed corpus
template. `POLICY` extends that rather than weakening it: its source is the digest-pinned task
definition and the digest-pinned manifest's `edit_policy`, both of which the evaluator validated at
ladder rows 8-11 before any provider call. It is a function of the corpus, not of the attempt, so it
is identical for both paired samples and both attempts of a task.

### 4.2 The sealed template, version 3

`eval/prompt/canonical-v1t/repair-template.json`, `REPAIR_PROMPT_TEMPLATE`, `schema_version: 1`,
`template_id: prompt-v1t-repair-v1`. The record shape is unchanged; `section_headers` carries six
keys in the §4.4 order.

Three changes to `canonical-v1e`'s text, each argued from §1.2's evidence and nothing else.

**(a) The unchanged-file refusal is stated, because it is stated nowhere today.** The preamble gains,
adjacent to the existing four requirements:

```text
- Your answer must actually change something. A `FILE:` block whose content is identical to
  that file's current content is refused before the tests run, and an answer whose blocks are
  all identical to the current files is not an answer.
```

Ten of twenty-two ran attempts were refused for exactly this, and no prompt in the corpus has ever
mentioned it. This is the single highest-value sentence in the capability.

**(b) A worked example, and the format requirement restated between the preamble and the
sections.** `c4-repair-editset.md` §6.4 asked for "the format reminder repeated *after* the
diagnostics rather than only at the close". A probe corrects that request: `repair_prompt_text`
already appends `closing_text` **after** every section (`scripts/prompt-evaluate.py:1684-1689`), so
the close *is* after the diagnostics. What is genuinely missing is a restatement **before** them,
where the model reads it adjacent to the requirements rather than 8-16 KB later. The preamble
therefore ends with the worked-example block, in the exact grammar `parse_file_blocks` accepts, and
`closing_text` is unchanged.

**(c) The `POLICY` header names the section as binding rules, not advice.** `"--- edit policy: what
your answer must satisfy ---"`.

The preamble's existing paragraph stating that the previous answer was *rejected by the repository's
own validation* is kept verbatim, including "Do not return them unchanged". **§1.2 shows that
sentence backfiring**: the two `duration-half-away-from-zero` PARENT rows obeyed it literally and
returned the *pinned* file instead of their own answer, converting a wrong patch into no patch. It is
kept because removing it would change two things at once and make the run uninterpretable; change
(a) is the specific correction for that failure — "must actually change something" is the missing
half of "do not return them unchanged".

### 4.3 The task prompt, version 3 — and why attempt 1 must change

Three new files, `eval/tasks/prompt-v1t/<task>/task-prompt.json`, byte-for-byte the `prompt-v1`
originals except an addition to the existing `Rules:` list and a worked example:

````text
- The block body must differ from that file's current content, shown above. An answer whose
  blocks reproduce the current files byte-for-byte is refused before the tests run.
- At most 32 blocks, and at most 262144 bytes in any one block.

Worked example, for this task:

FILE: src/settings.py
```
<the entire new content of src/settings.py, from its first line to its last>
```
````

The editable path in the worked example is the task's own; the body is a placeholder, so the example
cannot be copied as an answer.

**Why attempt 1 changes, stated as a decision.**

1. **The refusal it addresses fires at attempt 1.** Six of the ten refusals in §1.2 are attempt-1
   refusals. A repair-template-only change would leave the largest half of the failure class
   untouched and would measure nothing about it.
2. **Time to a passing patch is the primary metric.** A fix at attempt 1 is worth strictly more than
   the same fix at attempt 2, and a capability that could take it and did not would be optimizing
   the wrong attempt.
3. **The paired comparison is preserved, and this is the reason it is safe.** `render()` takes the
   task prompt as an argument independent of the variant
   (`scripts/prompt-evaluate.py:1547-1556`); PARENT and CANDIDATE differ only in `base_prompt`,
   `repo_prompt`, `learned_prompt_append`, and `context_policy`, all of which are byte-identical to
   `canonical-v1e`'s. The task-prompt delta is therefore applied **identically to both arms**, so
   the C6 PARENT/CANDIDATE contrast is the same contrast it was in three prior runs and the C4 gate
   predicate stays a paired one.
4. **What it costs, stated rather than discovered.** Attempt 1 is **not** byte-comparable to the C4
   and C4E runs. This run measures "prompt contract version 3, end to end", not "the repair template
   alone". A design that held attempt 1 fixed would isolate the template but would introduce a
   different confound — the new rule would appear for the first time in the repair prompt, and any
   recovery could be attributed to novelty rather than to content. Neither design is confound-free;
   this one is the one whose confound is on the side of the primary metric.

### 4.4 Sections, order, and bounds

```text
REPAIR_SECTION_KINDS_V3 = ("STATUS", "POLICY", "EDITSET", "SUMMARY", "STDOUT", "STDERR")
```

| # | Section | Source | Bound |
| --- | --- | --- | --- |
| 1 | `STATUS` | attempt 1's `status`, `failure_kind`, `build_status`, `test_status`, one label per line | 128 (`REPAIR_STATUS_LIMIT`) |
| 2 | `POLICY` | the task definition's `allowed_edits` and the manifest's `edit_policy` | 2,048 (`REPAIR_POLICY_LIMIT`) |
| 3 | `EDITSET` | attempt 1's `measurement.edit_set` | 16,384 (`EDIT_SET_LIMIT`, at the producer) |
| 4 | `SUMMARY` | attempt 1's `diagnostic_summary` | 4,096 (`SUMMARY_LIMIT`) |
| 5 | `STDOUT` | attempt 1's `diagnostic_stdout` | 16,384 (`DIAGNOSTIC_LIMIT`) |
| 6 | `STDERR` | attempt 1's `diagnostic_stderr` | 16,384 (`DIAGNOSTIC_LIMIT`) |

`POLICY` sits immediately after `STATUS` and before `EDITSET`: the verdict, then the rules the
answer must satisfy, then what the previous answer was, then why it failed. The four sections
inherited from `canonical-v1e` keep their relative order, so a version-3 prompt with `POLICY` and
`EDITSET` absent has the same section sequence as a `canonical-v1r` prompt.

**The rendered `POLICY` form**, normative:

```text
editable paths, spelled exactly:
  src/settings.py
A FILE: block naming any other path is refused before the tests run.
A FILE: block whose content is identical to that file's current content is refused before the
tests run.
At most 32 FILE: blocks. At most 262144 bytes in any one block.
```

Paths are rendered in the task definition's declared order, one per line, two-space indented. The
bounds are rendered from `edit_policy`, never from the evaluator's constants directly, so the
prompt cannot disagree with the record that ladder row 10 validated.

**`edit_refusal` is not rendered.** The rejected alternative was a fifth `STATUS` label. It is
refused for two reasons: the refusal's human text is already `diagnostic_summary`, which `SUMMARY`
renders verbatim, so a label would duplicate it; and adding a label pushes `STATUS` toward its
128-byte bound, which would force a constant change and a second reason for the two runs' prompts
to differ. `edit_refusal` is persisted evidence and a counted aggregate, not prompt content.

**`completion_text` is never rendered.** Showing the model its own unparsed prose is a different
experiment with a different hypothesis; §6.4 records it as deferred with a named resume condition.

The four bounded sections plus `POLICY` sum to at most 55,424 bytes on top of an attempt-1 prompt.
Against the measured assembled sizes of 8,348-16,904 bytes over 65,536 (§2.8), the expectation is
that the ladder still never fires; §4.5 says what happens when it does.

### 4.5 The drop ladder

```text
REPAIR_DROP_ORDER = ("STDOUT", "STDERR", "SUMMARY", "EDITSET")
```

**Unchanged, and `POLICY` joins `STATUS` as never-dropped.** That is a decision, argued:

*Why `POLICY` is undroppable.* It is the section this capability exists to add, it is bounded at
2,048 bytes, and `STATUS` + `POLICY` together are at most 2,176 bytes — small enough that they can
never be the reason a prompt exceeds 65,536. `EDITSET` is droppable because it can blow the budget by
itself, up to 32 blocks; `POLICY` structurally cannot, so the argument that made `EDITSET` droppable
(`c4-repair-editset.md` §4.4: losing a measurement is worse than a degraded prompt) does not apply.

*Why the order among the other four is unchanged.* Nothing measured suggests it is wrong, and
changing it would make the runs' prompts differ for a second, unrelated reason.

If the prompt exceeds the budget with only the preamble, headers, attempt-1 text, `STATUS`, and
`POLICY`, the repair attempt is `SKIPPED`/`REPAIR_PROMPT_BUDGET` and no provider call is made.
`repair_prompt_source.dropped_sections` names every dropped section, and — per
`c4-repair-editset.md`'s docstring rule, restated because it is easy to get wrong — a section whose
source is empty appears in neither `included_sections` nor `dropped_sections`.

### 4.6 Re-derivability

Given a persisted version-3 row, the sealed template, the digest-pinned task definition, and the
manifest's `edit_policy`, a verifier recomputes

```text
assemble(template,
         attempts[0].measurement.status, failure_kind, build_status, test_status,
         task_definition.allowed_edits, task.edit_policy,
         attempts[0].measurement.edit_set,
         attempts[0].measurement.diagnostic_summary,
         attempts[0].measurement.diagnostic_stdout,
         attempts[0].measurement.diagnostic_stderr,
         included_sections, dropped_sections)
```

and requires the result's SHA-256 to equal `attempts[1].rendered_prompt_sha256` and
`attempts[1].generation_request.user_text_sha256`. Ladder row 24 makes the producer run this against
its own output; the evidence sidecar makes an independent producer run it again.

**What `POLICY` changes about the re-derivation, stated.** Every prior section's source was a field
of the persisted measurement. `POLICY`'s source is two **corpus** documents, both digest-pinned by
the manifest and both verified before the run. The re-derivation therefore needs the corpus as well
as the row — which the evidence sidecar already has, since it verifies the corpus file-set manifest.
It is a wider input, not a weaker claim: the two documents are immutable members of a frozen corpus,
whereas the measurement is model output.

### 4.7 What never enters a repair prompt, and what now does

**Never**, unchanged: any environment-variable value; any credential or credential env name; the
container hostname, `host.docker.internal`, the endpoint, the model path, or any Docker or
bind-mount detail; the `PROVIDER_SERVICE_PROBE`; any path the evaluator or an adapter constructs;
any other task's fixtures or diagnostics; any cross-sample or cross-variant content; and now
explicitly `completion_text`.

**Disclosed and inherited**, unchanged: the sandbox `mkdtemp` suffix already present in the frozen
diagnostics, which originates in the frozen runner and cannot be scrubbed here without breaking
§4.6.

**New in this capability**: nothing enters the prompt that is not already a checked-in corpus
document. `POLICY` renders `allowed_edits`, which the task prompt already prints, and three integers
the code already enforces. The model's own text continues to enter through `EDITSET` under
`c4-repair-editset.md` §4.6's three bounds, unchanged.

**New in the persisted artifact, and worth naming**: on the eight no-set refusal codes, up to
32,768 redacted bytes of the model's raw completion. Three properties bound it. (1) It is persisted
**only** where no structured substitute exists, and no attempt in either prior run would have
triggered it. (2) It passes `redact_credential` before it is bounded or digested. (3) It is
whole-field: present entire, or absent with its identity intact. A reviewer should read any realized
`completion_text` in the gate evidence rather than take that on trust.

---

## 5. Nondeterminism handling

Every quantity this capability introduces is a function of persisted bytes, and none of them is a
timing.

**What the two prior runs measured about nondeterminism.** 22 provider calls each at
`temperature_micros: 0` with greedy decoding. C4: `adapter_elapsed_ns` 7.98-64.67 s, median 18.59 s,
8.1x spread, 824.243 s wall clock. C4E: 8.58-51.54 s, median 19.09 s, 823.67 s wall clock. Three
runs of the same corpus (counting C4's unpublished first run at 8.13-73.82 s) produced three
different ranges with **every correctness value identical**. The two paired samples of a row differ
only in `paired_seed`, and a seed cannot change a greedy decode, so the spread is server state,
prompt-cache reuse, and host contention.

**What follows for this design.**

1. **No timing is a gate input, a threshold, or a claim.** §6.3 refuses a speed claim outright.
2. **The reproducibility requirement is the paired predicate itself.** A recovery counts only when
   both samples of a (task, variant) pair recover.
3. **Content nondeterminism gains a second observable.** `patch_sha256` made "attempt 2 re-sent
   attempt 1's patch" checkable at C4E; `completion_sha256` now makes "attempt 2 re-sent attempt 1's
   *whole answer*" checkable, and "sample 1 and sample 2 produced the same completion" checkable
   across the paired samples. Neither is a gate input; both are reported.
4. **Prompt-cache reuse is a plausible confound and is not controlled.** The repair prompt is a
   strict textual extension of the attempt-1 prompt, so a server caching the shared prefix makes
   attempt 2 cheaper for reasons unrelated to the model. This affects timings only, and no timing is
   claimed.
5. **The attempt-1 prompt changed, so attempt-1 timings are not comparable to C4 or C4E either.**
   Three task prompts grew by roughly 300-400 bytes each. Recorded here so no later reader treats
   the three runs' attempt-1 clocks as a series.
6. **The evaluation is not re-run for a better result.** One gate run is recorded. If it must be
   re-run for an operational failure, the reason and both runs' outcomes are recorded.

---

## 6. Fixtures, qualification, metrics, deferrals, risks

### 6.1 Owner tests — deterministic, offline, no provider

| Owner | Adds |
| --- | --- |
| `scripts/run-prompt-template-adapter-smoke` **(new)** | The import-chain contract: verify-then-execute over one byte sequence for the repair adapter; a mutated repair file rejected; `repair.BASE_ADAPTER_SHA256` cross-checked; every consumed name from both modules present and of the expected kind; exactly one frozen module object and one `prctl` writer; `repair_adapter_runtime_identity` cross-derivation and its mismatch case; `producer` and own-`runtime_identity` values; the §3.2 **bounded-divergence golden** against the repair adapter's `measurement()` / `assemble()`; **every one of the nine frozen raise sites driven against the real loaded module and asserted to map to its `edit_refusal` code**, plus an unmapped message rejected as `ERROR`/`ADAPTER`; the `UNCHANGED_FILES` path asserted to carry `edit_set` `Some`; the conditional `completion_text` rule in both directions; the whole-field `RESULT_LIMIT` drop with the identity fields surviving; and the version-3 `assemble()` shape for each mode, driven by a stub generation child |
| `scripts/run-prompt-evaluate-smoke` | `POLICY` and the declared policy through the loop against `scripts/prompt-fixed-adapter.py` and a v3-emitting stub: the `POLICY` section rendered from a task definition and an `edit_policy`; `edit_policy` present/absent by adapter; ladder rows 8-11, 14-21, and 25 one case each; the three-way-selected `TASK_MEASUREMENT_FIELDS`; `edit_refusal_count`; and the **constant-parity assertion of §3.4** across all five scripts |
| `scripts/run-prompt-render-parity-smoke` | The §4.6 re-derivation as a byte golden with `POLICY` present, with `EDITSET` present and absent, and with a multi-path allowlist; each of the four drop-ladder steps as its own golden, asserting **`POLICY` survives every drop**; the budget-exhaustion `SKIPPED` case with `STATUS`+`POLICY` only; a redaction case; and a nested-fence case |
| `scripts/run-prompt-score-smoke` | Version-3 measurement decode; **version-1 and version-2 decode unchanged**; the present-at-3 / absent-at-1-and-2 rule in both directions; the §3.3 invariants including the widened `edit_set` rule at 3 and the narrow rule at 2; `verifier_measurement_equal` over all 31 fields; the new aggregates |
| `scripts/run-prompt-gate-validator-smoke` | Version-3 evidence carrying version-3 measurements; the new aggregates recomputed by `rescore`; the wire-form presence rule with an omitted-member fixture row; **and the inherited regression asserting that the frozen version-1 chain, the frozen C4 version-2 chain, and the frozen C4E version-2 chain all still validate and rescore byte-identically** |
| `scripts/run-prompt-measurement-adapter-smoke`, `scripts/run-prompt-repair-adapter-smoke` | **Unchanged and must stay green.** Both passing is part of the proof that the two frozen adapters still behave as reviewed while being imported elsewhere, and the repair-vs-frozen divergence golden must not move |
| `make gate-topology-check` | Must pass with its byte-literal `EXPECTED` unmoved. `c4-template-gate` joins no aggregate, and neither does `make prompt-template-adapter-smoke`, per `c4-repair-editset.md` §11.3 deviation 10 |
| `make check`, `make fmt`, `make format-check`, `make build` | The Align side: `src/prompt_artifacts.align`, `src/prompt_score.align`, `src/prompt_model.align`, `src/prompt_evaluate.align` (the §3.11 pin) |
| Row-bearing fixtures | `src/prompt_verifier_smoke.align` gains a defect for each new presence rule and each §3.3 invariant, mutation-tested; `src/prompt_render_smoke.align`, `src/prompt_render_parity_smoke.align`, and `eval/fixtures/c6-prompt-state/templates.jsonl` stay unchanged, per §3.5 entry 15 |

**The frozen-chain regressions are not optional politeness.** **Three** merged evidence chains now
depend on version-1 or version-2 measurement decode, and `make prompt-gate-check` is unavailable on
this host (`c4-repair-editset.md` §2.6, inherited unchanged). The `validate_evaluation_pair` /
`rescore` regression over all three is the only thing standing between a version-3-shaped decoder
and their deletion.

### 6.2 The named qualification and its cost ceiling

```text
make c4-template-gate \
  C4_TEMPLATE_SCOPE=eval/prompt/canonical-v1t/scope.json \
  C4_TEMPLATE_PROVIDER_PROBE=<absolute path to the PROVIDER_SERVICE_PROBE document> \
  C4_TEMPLATE_OUT=eval/prompt/c4-template-gate/
```

A named focused qualification. **It joins no aggregate** — not `make ci`, not `hosted-checks`, not
`capable-checks`. A missing or empty `C4_TEMPLATE_*` value fails before the run starts.

**Cost ceiling, recorded before implementation.** 12 initial attempts, at most 10 repair attempts,
**at most 22 provider generation calls**. C4 took 13.74 minutes and C4E 13.73 minutes for exactly
those 22 calls. The task prompts grow by roughly 300-400 bytes and the repair prompts by roughly
400-600 bytes, which lengthens prefill marginally.

```text
expected gate run time:  12-30 minutes wall clock
recorded cost ceiling:   60 minutes wall clock, single run, this host
per-attempt ceiling:     provider_control.timeout_ns = 1,800,000,000,000 ns (1,800 s)
per-attempt observed:    7.98 s - 64.67 s over 44 calls in two prior runs
```

**If a run exceeds 60 minutes, the capability stops and the boundary is reconsidered** rather than
the ceiling being raised after the fact.

The run records, in the C8 house form: the align-llm commit and whether the tree was clean;
`.align-revision`; the Docker image digest and `docker version`; the forwarder command; the
container privileges; the host `llama-server` version string, binary SHA-256, and model SHA-256; the
exact `make` command; the container's OS, kernel, architecture, and logical CPU count; and the
measured wall clock against the ceiling. **The run is made from a clean committed head**, which C4
and C4E both had to redo (`HANDOFF.md`).

### 6.3 Metrics, and what the measured claim is and is not

**Primary: `repair_recovery_paired_count`** — the §1.5 gate quantity — with `repair_attempt_count`
and `repair_editset_attempt_count` as denominators.

**Pre-committed secondary: `edit_refusal_count`**, against the derived C4E baseline of 10 of 22
(§1.5). Reported with its per-code breakdown whatever the gate says.

**Secondary: `generation_to_passing_patch_ns`**, the evaluator-observed total including the repair,
per row and as a median over rows that reached a pass. Reported, not claimed.

**Reported alongside, and new: answer identity.** For every row, whether
`attempts[1].measurement.completion_sha256` equals `attempts[0]`'s, and whether the two paired
samples' completions agree. C4E could state patch identity; this states whole-answer identity.

**What this capability claims.** That the edit policy the pinned adapters enforce is a declared,
validated, rendered contract rather than three unlinked constants and one unstated refusal; that the
failure mode that consumed ten of twenty-two attempts is now a named code with a counted aggregate
and a persisted explanation; that the repair prompt remains re-derivable from persisted evidence
plus the frozen corpus; and, if the gate is `MET`, that at least one task recovered from a
first-attempt failure reproducibly across both paired samples.

**Measured qualification of that last clause.** Section 11.4 records that its literal predicate is
true only because version 3 first regressed a previously first-shot passing pair. It is not evidence
of a new passing task or a net repair capability, and this document makes no such claim.

**What it does not claim.** **No speed claim of any kind** — §5's spread over 44 calls at
temperature 0 supports no baseline, no floor, and no comparison, and the prompt-cache confound is
uncontrolled. **No prompt-quality claim**: the CANDIDATE variant is not asserted to be better and the
C6 acceptance verdict is secondary evidence only. **No provider-quality claim**: one model, one
build, one host. **No generality claim**: three tasks, one repository family, one language. **No
claim that the edit policy is the binding constraint** — that is the hypothesis under test, and §1.5
and §1.6 fix both readings before the run. **No claim that attempt 1 and attempt 2 are separable in
this run** — §4.3 item 4 states the confound this design accepted and why.

If `repair_recovery_paired_count == 0`, the reported result is: the loop ran, `POLICY` was carried on
N attempts, `edit_refusal_count` was M against a baseline of 10, here is the per-code breakdown, and
here are the realized completion-digest comparisons. §1.6 fixes what that redirects to, in both of
its readings.

### 6.4 Deferred surfaces

| Deferred | Reason | Resume condition |
| --- | --- | --- |
| **Unconditional raw-completion capture** | §3.3 persists the text only where no structured substitute exists. The unconditional form moves every model completion in the corpus into a persisted artifact for a signal `edit_set` already carries on those paths | A run that records a refusal code in the eight no-set class, or a question whose subject is the prose *around* the blocks |
| **Task-difficulty calibration of the corpus** | §1.6 reading (a). If refusals fall and recoveries stay at zero, the corpus's individual solvability by the pinned model is the unmeasured quantity, and no repair gate can be interpreted without it | A `NOT_MET` gate with `edit_refusal_count` materially below 10. It is a corpus capability, not a prompt one, and it has no label today |
| **The model and decoding axes** | §1.6 reading (b). n>1 sampling above temperature 0, or a larger model. Both break greedy determinism and the paired predicate, and a provider change invalidates every C6 comparison sharing this corpus | A `NOT_MET` gate with `edit_refusal_count` at or above 10, plus an explicit decision to give up paired greedy comparability |
| **Rendering `edit_refusal` or `completion_text` into the prompt** | §4.4. Both are different experiments with different hypotheses | A capability whose question is what the model does when shown its own unstructured output |
| **Changing the `FILE:` grammar** | §2.3. It has never failed | A measured parse failure, which has not occurred in 44 calls |
| Scrubbing the sandbox temp path out of persisted diagnostics | Unchanged: it originates in the frozen runner and scrubbing here would break §4.6 | A capability that re-freezes the runner |
| Measuring `prompt_preparation_ns` instead of the hard-coded `20_000_000` | Unchanged: a pre-existing deviation with its own owner | Its own capability |
| More than one repair attempt | Unchanged. Each extra attempt multiplies run cost | A `MET` gate at one repair plus a measured recovery rate showing a second attempt would recover a task the first did not |
| Failure-memory feedback between attempts | Unchanged: it would make attempt 2 depend on prior runs and destroy single-row re-derivability | A design that persists the selected memory events into the attempt record |
| Merging the three adapters | Three adapters now exist in a two-hop import chain. Merging them means re-freezing `canonical-v1`, which costs four evidence chains | A capability that genuinely re-freezes the canonical corpus |
| Converging `src/repair.align` / `src/verification_loop.align` with this loop | Unchanged | After this gate resolves either way |

Each deferral requires a new design review and an acceptance test tied to time to a passing patch or
another explicitly named metric.

### 6.5 Prerequisites

1. `agent/c4-repair-editset` merged, or its head stable after its committed-head gate re-run, since
   this branch is stacked on it and consumes `TASK_MEASUREMENT` version 2, `edit_set_blocks`, the
   import-by-path contract, and the `canonical-v1e` freeze. **The `REPAIR_ADAPTER_SHA256` constant
   is derived from that final head**, so it is written after the re-run lands, not before.
2. `llama-server` running on the host at `127.0.0.1:18080` with
   `~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf` under the model id
   `qwen2.5-coder-7b-instruct-q4_k_m`. Started by the operator; this capability never starts it.
3. The model file present and matching the `model-sha256` frozen into
   `canonical-v1t/generation-policy.json` at freeze time.
4. Docker 28.5.1 and the `c4-repair-measure:latest` linux/aarch64 image.
5. The container-local `socat` forwarder running before the evaluator starts.
6. The managed pinned toolchain at `.align-revision` `3a34febe912db5096c58c74fede36ff53f223e04`.
7. The frozen-chain regressions of §6.1 green over **all three** of `eval/prompt/gate/`,
   `c4-repair-gate/`, and `c4-editset-gate/`.
8. **Host capacity.** Track B runs real-model CPU work in sibling worktrees; check for running model
   processes and free memory before starting `llama-server`, and never kill another agent's process.

No Align capability request is a prerequisite. §6.7 records why.

### 6.6 Risks

| Risk | Prior class | Mitigation |
| --- | --- | --- |
| **The evaluator delta exceeds the four-chunk launch window** | new; the tightest constraint in the design | §3.11: the evaluator is implemented first and measured at the first coherent batch; a delta above 24,000 bytes returns to this ledger before continuing, with two named options, one of which is a public contract change and is not taken silently |
| The `edit_refusal` mapping breaks because a frozen message changes | new; adjacent to "consuming an undeclared internal API" | The mapped file is digest-pinned in four manifests. The mapping is **total** — unmapped is `ERROR`/`ADAPTER`, never silent `NONE` — and all nine raise sites are driven against the real module in the owner smoke. §3.3 states the fragility rather than arguing it away |
| A persisted field list drifts from what its producer emits | persisted field lists vs producer emission | §3.5's fifteen-place parity table is built **before** implementation and re-walked in the author pass and the matrix-to-diff pass. `verifier_measurement_equal` is named explicitly as the one omission that would fail nothing |
| A version-3 presence rule written as key-presence rejects merged evidence | `c4-repair-editset.md` §11.3 deviations 2 and 13, twice each | §3.5 entry 9 fixes the wire-form rule up front; entry 11's fixture emits one row with the members **omitted** as the wire omits them; §3.3 keeps the version-2 `edit_set` rule verbatim and makes the widening adapter-selected |
| The near-copy of `measurement()` diverges from the repair adapter's original | duplicated containment logic, now at two hops | Two bounded-divergence goldens, one per hop, each a checked-in artifact; the primitives are **called**, never copied; both earlier adapter smokes stay green |
| Three adapters and a two-hop import chain are harder to review than two | new | Only `measurement()` and `assemble()` are near-copied at each hop; the second hop consumes six names, listed in §3.2; the frozen module has exactly one object and one `prctl` writer |
| **The template change makes behaviour worse, as the last one did** | measured at C4E: "Do not return them unchanged" turned a wrong patch into no patch on two rows | Not mitigated by construction — it is the hypothesis under test. §1.5 pre-commits the secondary counter so a regression is measured rather than argued, and §4.2 keeps the backfiring sentence and adds its missing half rather than changing two things at once |
| A declared policy field becomes a knob someone sets differently from the adapter | new | §3.4: the values must **equal** the constants; a difference is `INVALID_INPUT`/`EDIT_SET` before any provider call, and the constant-parity owner test asserts all five declarations agree |
| The model's raw completion enters a persisted artifact | new disclosure surface | Conditional on the eight no-set codes only, redacted before bounding and digesting, whole-field, never rendered into a prompt (§4.7). A reviewer reads any realized value rather than trusting it |
| Completion capture turns a real measurement into `ERROR` through `RESULT_LIMIT` | new, introduced by this capability | §3.3's encode-then-check whole-field rule: the text is dropped, the identity fields survive, and the measurement is never lost |
| A version-3-shaped decoder deletes C6's, C4's **and** C4E's merged evidence | evidence loss, now three chains | Version-1 and version-2 decode are explicit owner tests in four smokes, and the frozen-chain `validate_evaluation_pair`/`rescore` regression runs over all three chains (§6.1) |
| Trace records produced by the third adapter are unreferenced in the evidence model | evidence-model referencing | The template adapter produces the **same** snapshot request, before/after results, and input snapshot as both earlier adapters, through the same helper; the gate-validator smoke asserts referencing on a version-3 document explicitly |
| Attempt 1 changed, so the three runs are not a clean series | new, accepted deliberately | §4.3 item 4 and §5 item 5 state it before the run; §6.3 refuses the corresponding claim |
| The answering server is not the recorded server | provider drift | Unchanged: a fail-closed host probe plus an in-band model-id check, with the residual risk stated |
| Per-attempt run paths overflow a path limit | `ENAMETOOLONG` | Unchanged: fixed-width `-a1`/`-a2` suffixes, bounded and asserted components |
| `make gate-topology-check`'s byte-literal `EXPECTED` moves | check topology | Asserted as an owner check; if it moves, that is a topology change selecting `make ci` |
| Evidence measured from an unclean head | C4 and C4E both hit it | §6.2: the run is made from a clean committed head, and `align_llm_clean` is recorded |
| The gate is `NOT_MET` and the work looks wasted | scope pressure | §1.5 and §1.6 fix both readings and the redirect before the run; the correction of §1.2 and the `edit_refusal` vocabulary are delivered value independent of the gate |

### 6.7 Align capability requests

No new request is proposed. The two open items this capability touches are both already filed, and
both have a mitigation reusing a pattern proven at this pin. **The next free number is 53, but Track
B may take it on its own branch; if implementation finds a genuine gap it is filed as 54** under the
normal lifecycle in `docs/align-requests.md`. A workaround is not a reason to hide one.

| Request | Where it bites | Mitigation |
| --- | --- | --- |
| **Request 52** — `match` on an owned record's `Option` field partially moves the payload out with no diagnostic, and a later `json.encode` silently omits the field | Four new `Option` members on `TaskMeasurement` and one on each aggregate, in a module that decodes and re-encodes the persisted artifact. The failure is a silent wrong artifact, not a compile error | Every new `Option` member is read through a `borrow` binding, never a `match` on the owned record — the rule C4-REPAIR-MEASURED and C4-REPAIR-EDITSET both adopted. The rule is stated in the closure-matrix cell, not left to habit, and a review pass over every `match` on an owned record in the diff is a named repair-audit class. This capability adds a **third** client-evidence line |
| **Request 22** — indexing arrays of `Move` element types | `edit_set` is still `Option<array<EditSetBlock>>` and is now `Some` on one more path | Walk the array with the idiom `verifier_attempt_list_references` and the three `verifier_edit_set_*` functions already use. No new indexing form is introduced. Note that `c4-repair-editset.md` §11.3 deviation 8's known limitation — owned field replacement supports only `string` and `Option<string>` leaves — bites again in `src/prompt_verifier_smoke.align`, which builds a third task shape as a parameterized literal |

The new members are three `Option<string>` / `Option<i64>` leaves and one widened existing member,
all shapes proven at this pin by C4-REPAIR-EDITSET's build. If the pinned compiler cannot express
the three-way version-selected presence rule the way it already expresses the two-way one, that is a
genuine gap and is filed rather than routed around with a permissive record.

---

## 7. Closure matrix

Construction, success, failure, malformed input, early exit, and cleanup for each affected module.
Cases are `scripts/run-prompt-template-adapter-smoke` unless marked **(E)** for
`run-prompt-evaluate-smoke`, **(R)** for `run-prompt-render-parity-smoke`, **(S)** for
`run-prompt-score-smoke`, **(G)** for `run-prompt-gate-validator-smoke`, **(V)** for
`src/prompt_verifier_smoke.align`, or **(Q)** for the §6.2 qualification.

### 7.1 `scripts/prompt-template-adapter.py` — the import chain

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | bounded read of the repair adapter, digest over those bytes, execute those bytes; frozen module obtained through `repair.base_adapter()` | load succeeds; exactly one frozen module object observed |
| Success | both namespaces carry every consumed name at the expected kind | name-and-kind assertion passes |
| Failure | digest mismatch against `REPAIR_ADAPTER_SHA256` | a one-byte-mutated copy is rejected, `ERROR`/`BASE_ADAPTER`, before any request load |
| Failure | `repair.BASE_ADAPTER_SHA256` disagrees with the manifest | ladder row 4 |
| Failure | `repair_adapter_runtime_identity` disagrees with `repair.runtime_identity()` | file replaced between the two derivations is rejected |
| Malformed input | a consumed name missing or wrong-kind, in either module | one case per module |
| Early exit | executing either module must not run its `main()` | a marker file a stub `main()` would create is absent after load |
| Cleanup | no module reload, no namespace mutation, one `prctl` writer | second-load attempt rejected; `grep` shows one writer |
| Divergence | `measurement()` / `assemble()` near-copy of the repair adapter's | the §3.2 golden; the repair-vs-frozen golden unmoved |

### 7.2 `scripts/prompt-template-adapter.py` — the version-3 measurement

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `edit_refusal` mapped from the frozen message; completion digested at full redacted length then bounded | all nine raise sites driven against the real module |
| Success | `PASS` and `FAIL`/`TEST` carry `edit_refusal: NONE`, `edit_set` `Some`, `completion_text` `None` | both, against a stub generation child |
| Failure | `UNCHANGED_FILES` carries `edit_set` **`Some`**, `patch_sha256` `None`, `completion_text` `None` | a stub response reproducing the pinned file |
| Failure | each of the eight no-set codes carries `edit_set` `None` and `completion_text` `Some` | one case each |
| Failure | `ERROR` before the parse carries `edit_refusal: NONE` and every completion member as the response allows | a generation-child failure |
| Malformed input | an unmapped frozen message | `ERROR`/`ADAPTER`, never a silent `NONE` |
| Malformed input | a completion whose encoded result would exceed `RESULT_LIMIT` | `completion_text` dropped whole; `completion_bytes` and `completion_sha256` survive; the measurement is not `ERROR` |
| Early exit | the declared-patch path does not parse the response as edits, but generation still returns one | `edit_set` `None`, `edit_refusal: NONE`, `completion_bytes`/`completion_sha256` `Some`, `completion_text` `None`, `patch_sha256` `Some` |
| Cleanup | the completion digest is taken before any input is closed | no read after close |
| Redaction | completion bytes and digest are post-redaction | a credential-bearing stub run leaves no credential in `completion_text` and changes the digest |

### 7.3 `scripts/prompt-evaluate.py` — `POLICY`, the declared policy, and the aggregate

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `REPAIR_SECTION_KINDS_V3` gains `POLICY`; `repair_section_sources` gains its renderer | (R) the byte golden with `POLICY` present |
| Success | the section renders paths in declared order and bounds from `edit_policy` | (R) golden; (R) a multi-path allowlist |
| Success | `edit_policy` validated at rows 8-11 before any provider call | (E) one case per row |
| Failure | `edit_policy` present for a non-template adapter, or absent for the template adapter | (E) both directions |
| Failure | a bound differing from the evaluator's constant; `refuse_unchanged_files: false` | (E) both rejected `INVALID_INPUT`/`EDIT_SET` |
| Malformed input | template `section_headers` not exactly the six kinds; the four- and five-kind sets still admissible for their own corpora | (E) three cases |
| Malformed input | ladder rows 14-21 on a hostile adapter result | (E) one case each |
| Early exit | budget exhaustion after the ladder ⇒ `SKIPPED`/`REPAIR_PROMPT_BUDGET`, no provider call | (E) and (R) |
| Early exit | row 22: neither `EDITSET` nor `POLICY` makes a repair eligible | (E) an attempt with both and all three diagnostics empty is `SKIPPED` |
| Cleanup | unchanged; attempt-1 cleanup failure still suppresses attempt 2 | (E) unchanged case stays green |
| Aggregate | `edit_refusal_count` counts ran attempts with `edit_refusal != NONE`, adapter-selected | (E) a mixed run; (E) a `canonical-v1e` corpus recomputes it **absent**, not zero |
| Constants | all five scripts declare identical bounds | (E) the parity assertion |

### 7.4 The drop ladder

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `REPAIR_DROP_ORDER` unchanged; `POLICY` joins `STATUS` as never-dropped | (R) each of the four steps as its own byte golden |
| Success | no drop at realistic sizes | (R) a C4E-sized fixture assembles with all six sections |
| Failure | `POLICY` survives every drop, including the `EDITSET` drop | (R) a fixture that must drop four sections keeps `STATUS` and `POLICY` |
| Malformed input | a section source present but empty is never "included" | (R) |
| Early exit | `STATUS`+`POLICY` only, still over budget ⇒ `SKIPPED` | (R) |
| Cleanup | `dropped_sections` ordered by `REPAIR_SECTION_KINDS_V3`, disjoint from `included_sections` | (R), (S) |

### 7.5 `src/prompt_artifacts.align`, `src/prompt_score.align`

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `TaskMeasurement` gains four `Option` members; `EditPolicy` is declared | (S) version-3 decode and re-encode |
| Success | version-1 and version-2 decode, re-encode, and verdict are byte-identical | (S), (G) over all three frozen chains |
| Failure | a version-3 member present at version 1 or 2 | (V) a defect per version |
| Failure | a version-3 member absent at version 3 where the wire form requires it | (V) a defect per member |
| Failure | the measurement-version-versus-adapter rule violated, three-way | (V) a defect per adapter |
| Failure | `edit_refusal` outside the ten-code vocabulary | (V) a defect |
| Failure | `edit_refusal: UNCHANGED_FILES` with `edit_set` `None` | (V) a defect — the invariant this capability exists to establish |
| Failure | `completion_text` `Some` on a code outside the eight | (V) a defect |
| Malformed input | the §3.3 invariants, one case each | (S) |
| Malformed input | `verifier_measurement_equal` must compare all 31 fields | (V) a defect differing **only** in a version-3 member |
| Early exit | version peek before member decode; no presence sniffing | (S) a version-2 document with a stray version-3 key is rejected |
| Cleanup | `verifier_reason_capacity` unchanged; no new per-pair reason | (S) capacity assertion unchanged |
| Ownership | every `Option` member read through a `borrow` binding (Request 52) | `make check`; a review pass over every `match` on an owned record in the diff |
| Ownership | the block array walked with the proven `Option<array<T>>` idiom (Request 22) | `make check` |

### 7.6 Corpus assets and the four frozen chains

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `scripts/freeze-canonical-v1t` mints all 31 members reproducibly | re-running it is a no-op on a clean tree; `--check` derives in memory, detects drift, and writes nothing |
| Success | the 22 carried members carry identical digests to `canonical-v1e`; 21 of them to all four manifests | an explicit digest-equality assertion over the four manifests |
| Failure | `REPAIR_ADAPTER_SHA256` or `repair.BASE_ADAPTER_SHA256` disagreeing with any manifest | ladder rows 3 and 4 |
| Failure | a `prompt-v1t` task naming fewer than three adapters in `artifacts` | ladder row 5 |
| Malformed input | a `prompt-v1t` task prompt whose digest disagrees with its artifact entry | ladder row 13 |
| Early exit | `git diff` over the three earlier corpora, the four gate directories, `eval/tasks/prompt-v1{,r,e}/`, `eval/runners/`, and the four frozen scripts is **empty** except §9.4's prose file | a checked assertion in the pull request, not a claim |
| Cleanup | `eval/prompt/c4-template-gate/` is a new directory; nothing is written into an existing gate directory | (Q) |

### 7.7 The run driver and the gate

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `scripts/run-c4-template-gate`, `make c4-template-gate` | (Q) |
| Success | 12 rows, at most 22 calls, evidence published through the Align path, from a clean committed head | (Q) |
| Failure | a missing or empty `C4_TEMPLATE_*` value | fails before the run starts |
| Failure | the provider probe disagrees with the policy revision | fails closed before the first call |
| Malformed input | the in-band model id is not the declared one | fails closed |
| Early exit | wall clock exceeds the 60-minute ceiling | the capability stops; the ceiling is not raised after the fact |
| Early exit | ran provider calls exceed 22 | the qualification fails and publishes no new evidence |
| Cleanup | `make gate-topology-check` passes with `EXPECTED` unmoved | an owner check |

### 7.8 Error-code-to-case map, and the final pass

`ERROR`/`BASE_ADAPTER` and the version-3 `ERROR`/`ADAPTER` cases belong to
`scripts/prompt-template-adapter.py` and its own smoke. `INVALID_INPUT`/`SCHEMA`, `/EDIT_SET`,
`/IDENTITY`, `/AGGREGATE`, and `/MEASUREMENT_BINDING` belong to the Align verifier and the gate
validator. `INVALID_INPUT`/`TEMPLATE` and `/SOURCE` belong to `scripts/prompt-evaluate.py`. Three
owners, assigned from the start, per `c4-repair-measured.md` §10.2 deviation 15.

Before review, every applicable cell above is mapped to the final diff and to passing evidence, or
to an explicit deferral recorded in §6.4.

---

## 8. Author consistency pass

Performed against this document as a whole; findings recorded rather than silently corrected.

1. **The correction is load-bearing and is applied everywhere in this document.** §1.2 replaces "no
   parsable `FILE:` block" with the two measured refusals. §1.3, §1.5, §2.2, §2.3, §4.2, §4.3, and
   §6.4 are all written from the corrected reading, and §9 propagates it to the five documents that
   carry the wrong claim. No section in this document argues from the old reading.
2. **Ledger-to-prose.** §3.3's field list, §3.5's change table and fifteen-place parity table,
   §3.9's ladder, §4.4's section table, and §7.5's cells were walked against each other. The four
   version-3 members appear identically in all five. `edit_refusal` is on the measurement in every
   one; no draft placed it on the attempt record or in `STATUS`.
3. **Gate predicate identity.** §1.5 restates `c4-repair-measured.md` §1.4's predicate verbatim so
   all three runs are comparable. `edit_refusal_count` is a pre-committed **secondary**, never a
   gate input; §1.5, §3.8, and §6.3 agree.
4. **Numbers.** Every figure in §1.2, §1.5, §2.8, §2.9, §5, and §6.2 was read from the checked-in
   evidence or the checked-in file at `de56c60`: 22 calls per run, 10 refusals of 22 in C4E, 10 of
   22 in C4 (8 unchanged + 2 policy), assembled repair prompts 8,348-16,904, attempt-1 prompts
   4,926-10,177, 234,347 evaluator bytes, 27,797 headroom, 17,291 prior delta, 823.67 s and
   824.243 s wall clocks. The 24 reconstructed prompt digests match the recorded ones exactly.
5. **A count corrected while writing.** An early draft called the arm "eight attempts on
   `layer-precedence`". The evidence shows **ten refused attempts across two tasks** — eight
   `UNCHANGED_FILES` plus two `PATH_NOT_EDITABLE` — spanning three live (task, variant) pairs. §1.5
   uses ten and three.
6. **Section order versus drop order are distinct and both are stated.** Order: `STATUS, POLICY,
   EDITSET, SUMMARY, STDOUT, STDERR`. Drop: `STDOUT, STDERR, SUMMARY, EDITSET`, with `STATUS` and
   `POLICY` never dropped. §4.4 and §4.5 do not contradict each other, and §4.5 argues the exclusion
   rather than asserting it.
7. **`prompt-gate-check` is not claimed anywhere.** It is unavailable on this host; §6.1 names the
   substitute and extends it to a third frozen chain; §6.5 lists it as a prerequisite in that
   substituted form.
8. **The frozen-file promise is stated once and enforced four times.** §1.4 states it, §3.2 lists
   the pins, §3.9 rows 2-5 check them, §7.6 regresses them.
9. **Three open items, recorded rather than resolved.** (a) The evaluator size window may not hold;
   §3.11 fixes the checkpoint and the two options, and it is the top risk row. (b) The
   `edit_refusal` mapping is a message-prefix match over a digest-pinned file; §3.3 states the
   fragility and §6.1 makes it total and driven against the real module, but it remains a string
   match. (c) §4.2 keeps a sentence the C4E evidence shows backfiring, and adds its missing half
   rather than removing it; whether that is the right call is exactly what the gate measures.
10. **`N/A` fields.** §3.12's completion paragraph gives a concrete reason for each. None is
    speculative expansion of an untriggered checklist section.
11. **The prompt-size redirect this capability was chartered with is refuted, not deferred.** §1.6
    and §2.8 say so with numbers, so no later reader spends a capability on it.

---

## 9. Reconciliation drafts

Drafts only. They are applied in the implementation branch, not here.

### 9.1 `docs/specs/roadmap.md` — new forward-order item 39

> Items 35 and 36 are claimed on sibling branches (`agent/r6-moe-resident-dense`,
> `agent/mf-single-token-logits`) and item 34 is claimed here; 37 and 38 are reserved for Track B's
> `R6-PREFIX-KEY-CORPUS`, which its own charter note allows to split into `R6-PREFIX-KEY` and
> `R6-PREFIX-TTFT`. Item 39 is numbered on that assumption and corrected at reconciliation if it
> changes. The numbering is a name, not a delivery order — item 36's own precedent.

```text
39. **C4-REPAIR-TEMPLATE — the prompt template and the declared edit policy.** The capability
    item 34 named as its own successor, and the one that corrects the record item 34 wrote.
    **Read the evidence again and it says something else.** Every `failure_kind: PATCH` row in
    both gate runs carries `diagnostic_summary: "the response reproduced the pinned files
    unchanged"` — `synthesized_patch`'s refusal, which fires only *after* `parse_file_blocks`
    returned terminated blocks and `validated_edit_set` accepted every path. The string "the
    response declares no file block" appears in **zero** rows. The model never failed to produce
    a parsable `FILE:` block; it produced correct blocks whose bodies were byte-identical to the
    pinned source. Ten of twenty-two ran attempts in each run were refused by the edit policy —
    eight for reproducing the files unchanged, two for naming a path outside the editable set —
    and that is the largest failure class in either run. Design in
    [`c4-repair-template.md`](c4-repair-template.md), which owns the contract ledger, the
    import-chain contract, the closure matrix, the prompt contract version 3, the cost ceiling,
    and the gate statement. The design gate triggered on the version-3 repair-prompt exchanged
    format, on `TASK_MEASUREMENT` schema 3 and the declared `edit_policy` persisted format, on a
    new frozen scope with a **third adapter** and **three new task prompts** as members, and on a
    coordinated invariant across the new adapter, `scripts/prompt-evaluate.py`,
    `scripts/prompt-gate-validator.py`, `src/prompt_score.align`, and the corpus assets. **The
    rule the model actually broke is stated in no prompt in the repository**: nothing anywhere
    says that a block identical to the file's current content is refused. Version 3 says it, in
    the task prompt and in the repair template, next to a worked example and the editable-path
    allowlist — both of which the task prompt already carried and the model violated anyway, so
    the statement is repeated rather than introduced. **The `FILE:` grammar does not change**: it
    has never failed in 44 calls. `MAXIMUM_FILE_BLOCKS` (32), `MAXIMUM_EDIT_BYTES` (262,144), and
    `synthesized_patch`'s unstated unchanged-file refusal become a declared `EDIT_POLICY` record
    on the task manifest, validated as equal to the constants the pinned adapters enforce and
    refused as `INVALID_INPUT`/`EDIT_SET` otherwise; it cannot live in the task definition,
    because the frozen validation runner refuses any extra key there. `TASK_MEASUREMENT` moves to
    `schema_version: 3` with a ten-code `edit_refusal`, the completion's bounded identity, a
    **conditional** bounded completion excerpt persisted only where no structured substitute
    exists, and a widened `edit_set` rule so the reproduced-unchanged refusal keeps the blocks it
    already built and then threw away. Versions 1 and 2 stay decodable forever and
    `PROMPT_TASK_ROW` does **not** move. `scripts/prompt-template-adapter.py` loads
    `scripts/prompt-repair-adapter.py` by path, which loads the frozen base adapter by path, so
    containment still has exactly one copy and each hop's divergence is a checked-in golden. New
    freeze `eval/prompt/canonical-v1t/` + `eval/tasks/prompt-v1t/`, 32 members, 22 of them at
    digests identical in all four manifests. **Attempt 1 changes too**, identically for both
    variants, because six of the ten refusals are attempt-1 refusals and time to a passing patch
    is the primary metric; the cost, stated before the run, is that this run measures the version-3
    contract end to end rather than the repair template alone. The gate is item 31's predicate
    unchanged, `repair_recovery_paired_count >= 1`, with a pre-committed secondary
    `edit_refusal_count < 10`. **The prompt-size hypothesis is refuted before the run**: the
    largest repair prompt in either run is 16,904 bytes of a 65,536-byte budget, no section was
    ever dropped, and the refused rows carry the smallest prompts. A `NOT_MET` gate has two
    readings and both are fixed in advance: refusals fall and nothing recovers, which points at
    corpus difficulty; or refusals do not fall, which points at the model and the decoding
    strategy and at nothing in the prompt. No speed claim. Recorded run-cost ceiling 60 minutes,
    expected 12-30, at most 22 provider calls. Named focused qualification
    `make c4-template-gate`; it joins no aggregate, and neither does
    `make prompt-template-adapter-smoke`.
```

### 9.2 `HANDOFF.md` — new "Active" section, above the current one

```markdown
## Active: C4-REPAIR-TEMPLATE (2026-08-29)

Branch `agent/c4-repair-template`, stacked on `agent/c4-repair-editset` at `de56c60`. Design
authored; not implemented.

**Capability.** The prompt template and the declared edit policy — the successor
`c4-repair-editset.md` section 6.4 named. `docs/specs/c4-repair-template.md` is the authoritative
ledger.

**A CORRECTION, and it changes the plan.** Both gate runs' `failure_kind: PATCH` rows carry
`diagnostic_summary: "the response reproduced the pinned files unchanged"` — `synthesized_patch`'s
refusal, raised *after* the blocks parsed and after every path passed the allowlist. The string
`"the response declares no file block"` appears in **zero** rows of either run. **The model has
never failed to emit a parsable `FILE:` block.** It emitted correct blocks whose bodies were
byte-identical to the pinned source. `c4-repair-measured.md`, `c4-repair-editset.md`,
`eval/prompt/c4-editset-gate/README.md`, roadmap item 34, and this file all say otherwise and are
corrected in the implementation branch (spec section 9.4).

**The real failure class.** Ten of twenty-two ran attempts in each run were refused by the edit
policy: eight `UNCHANGED_FILES` and two `PATH_NOT_EDITABLE` (`src/legacy.py`). Larger than the class
C4-REPAIR-EDITSET addressed. It had no name, no code, and no counter.

**What version 3 changes, and what it deliberately does not.** The `FILE:` grammar does **not**
change — it has never failed. The task prompt already carries a worked example and the editable-path
allowlist, and the model violated both anyway; the repair template carries neither. **The rule the
model actually broke is stated in no prompt in the repository**: nothing says a block identical to
the file's current content is refused. Version 3 states it in both attempts, adds a `POLICY` section
rendering the allowlist and the declared bounds per task, and restates the format requirement
between the preamble and the sections — the close is already after the diagnostics, contrary to
section 6.4's request.

**Attempt 1 changes.** Three new task prompts under `eval/tasks/prompt-v1t/`. `render()` takes the
task prompt independently of the variant, so the delta applies identically to PARENT and CANDIDATE
and the C6 contrast is preserved. Six of the ten refusals are attempt-1 refusals, and time to a
passing patch is the primary metric. The stated cost: this run measures the version-3 contract end
to end, not the repair template alone.

**Schema.** `TASK_MEASUREMENT` 2 -> 3: a ten-code `edit_refusal`, `completion_bytes`,
`completion_sha256`, and a **conditional** `completion_text` persisted only on the eight refusal
codes where `validated_edit_set` never returned. Plus the widened `edit_set` rule — the repair
adapter builds the blocks one line before `synthesized_patch` raises and then discards them, which
is why the mode is unexplained today. `PROMPT_TASK_ROW` does not move. `PROMPT_EVALUATION_TASK`
gains an optional `edit_policy` record; it cannot go in the task definition, because the frozen
validation runner does `set(task) != required`.

**Adapter.** A third adapter, `scripts/prompt-template-adapter.py`, loading
`scripts/prompt-repair-adapter.py` by path — which loads the frozen base adapter by path. That file
is now frozen on the same terms the base adapter is: `eval/prompt/c4-editset-gate/` was measured
against `canonical-v1e`'s exact scope digest.

**Gate.** `repair_recovery_paired_count >= 1`, unchanged. Pre-committed secondary
`edit_refusal_count < 10` against a C4E baseline derived from the summary strings. Three live
(task, variant) pairs. **The prompt-size hypothesis is refuted before the run**: largest repair
prompt 16,904 bytes of 65,536, no section ever dropped, refused rows carry the smallest prompts.
`NOT_MET` has two pre-fixed readings, in spec section 1.6.

**Top risk.** The evaluator has **27,797 bytes** of headroom in its four-chunk launch window and
C4-REPAIR-EDITSET's comparable delta was **+17,291**. The evaluator is implemented first and
measured at the first coherent batch; a delta above 24,000 bytes returns to the ledger before
continuing.

**Next actions, in order.** (1) Land `agent/c4-repair-editset` and take `REPAIR_ADAPTER_SHA256` from
its final head. (2) Review this design. (3) Implement the evaluator side and **measure the byte
delta** against section 3.11. (4) `scripts/prompt-template-adapter.py` and its smoke, including the
second divergence golden and the nine-raise-site mapping test. (5) `TASK_MEASUREMENT` version 3
across the Align artifacts, the verifier, the gate validator, and the fixtures —
`verifier_measurement_equal` is again the one line whose omission would fail nothing. (6) `POLICY`
assembly and the extended ladder. (7) `scripts/freeze-canonical-v1t`. (8)
`scripts/run-c4-template-gate` and `make c4-template-gate`. (9) The gate run, from a clean committed
head, inside its 60-minute ceiling.

**Blockers.** Prerequisite (1), plus host capacity: Track B's model work contends for memory and the
gate needs `llama-server` with the 4.7 GB model. No Align capability request blocks this design.
Next free number is **53**, but Track B may take it; a genuine gap found here is filed as **54**.
Requests 22 and 52 both bite and both are mitigated by idioms proven at this pin.
```

### 9.3 `docs/align-development.md` — addition after "The failing edit set, and the second adapter"

```markdown
#### The declared edit policy, and what the refusal strings actually said

`docs/specs/c4-repair-template.md` is the authoritative plan. It opens with a correction that is
worth repeating here because three documents got it wrong: `failure_kind: PATCH` does **not** mean
"the response had no parsable `FILE:` block". `scripts/prompt-measurement-adapter.py` raises
`EditFormatError` from eight sites and `measurement()` maps all of them to `PATCH`, so the only
distinguishing signal is the free-text `diagnostic_summary`. Read it in both gate runs and every
`PATCH` row says `"the response reproduced the pinned files unchanged"` — `synthesized_patch`'s
refusal, raised after the blocks parsed and after every path passed the allowlist. **No attempt in
44 provider calls has ever failed to parse.**

Three rules that generalize beyond this capability:

- **A status enum that collapses eight raise sites is not a diagnosis.** `edit_refusal` gives each
  site a code and the corpus aggregate a counter, so the same mistake cannot be made from the
  record again. The code is mapped from the frozen exception's message prefix, which is safe only
  because the file is digest-pinned in four corpus manifests, and the mapping is total: an unmapped
  message is an adapter error, never a silent `NONE`.
- **A constant that three scripts declare and one function enforces implicitly is not a contract.**
  `MAXIMUM_FILE_BLOCKS`, `MAXIMUM_EDIT_BYTES`, and the unchanged-file refusal become a declared
  `EDIT_POLICY` record on the task manifest, validated as *equal to* the constants the pinned
  adapters enforce. It cannot live in the task definition: `eval/runners/run-coding-task.py` is
  byte-frozen and does `set(task) != required`, so an extra key there fails the run.
- **A capability may change attempt 1 when the failure is at attempt 1, and must then say what it
  gave up.** `render()` takes the task prompt independently of the variant, so a task-prompt change
  applies identically to PARENT and CANDIDATE and the C6 contrast survives. What does not survive is
  byte-comparability of attempt 1 across runs, and the design records that before the run rather
  than discovering it after.

`eval/prompt/canonical-v1t/` + `eval/tasks/prompt-v1t/` is the fourth freeze, 32 members, minted by
`scripts/freeze-canonical-v1t`. The third corpus, `eval/prompt/canonical-v1e/` +
`eval/tasks/prompt-v1e/`, minted by `scripts/freeze-canonical-v1e`, is the C4-REPAIR-EDITSET freeze
and was not previously named in this document. The named qualification is `make c4-template-gate`;
like `make c4-repair-gate` and `make c4-editset-gate` it joins no aggregate.
```

Also update, in the same pass: `docs/align-development.md:362`'s "all **three** corpus file-set
manifests" becomes four; the corpus-selection bullets at lines 382-391 gain the six-kind template
and the three-way measurement-version rule; and the evaluator-window paragraph at lines 393-397 is
re-checked against §3.11's realized delta.

### 9.4 The corrections, and their exact boundary

The claim corrected by §1.2 appears in five places. All five are prose; **no measured artifact, no
digest, and no file-set member changes.**

| File | What changes |
| --- | --- |
| `docs/specs/c4-repair-measured.md` | the mode-2 description in §1.2 and §10.3 |
| `docs/specs/c4-repair-editset.md` | §1.2's "mode 2" paragraph, §6.4's deferral row, §11.4's `duration` PARENT paragraph, and the §9.1/§9.2 drafts that quote them |
| `eval/prompt/c4-editset-gate/README.md` | the sentence claiming "no parsable `FILE:` block at all" |
| `docs/specs/roadmap.md` | item 34's "produced no parsable file block on any of eight attempts" |
| `HANDOFF.md` | the C4-REPAIR-EDITSET section's directional-finding paragraph |

`eval/prompt/c4-editset-gate/README.md` is inside a directory §1.4 item 2 declares non-mutable. The
exception is bounded and stated: the README is **not** a corpus file-set member, carries no digest
that any document pins, and is not a measured artifact — it is the human description of the
measurement. Correcting a factually wrong sentence in it is required by `CLAUDE.md`'s rule that plan,
code, tests, and directly affected documentation are updated together; leaving a merged evidence
directory asserting something its own JSON contradicts is worse than the exception. The three JSON
artifacts in that directory are byte-identical, and the pull request asserts that with `git diff`.

---

## 10. Author-side design checks before implementation

1. Re-read `docs/review-checklist.md`'s "Public contract ledger", "Cross-cutting closure matrix",
   "Align correctness", and "Evaluation and repository integrity" sections against §3, §7, §6.7, and
   §7.6 respectively. Sections not triggered by this diff are omitted, not expanded.
2. **Implement the evaluator side first and measure its byte delta against §3.11 before anything
   else is written.** This is the checkpoint that decides whether the capability's shape holds.
3. Re-derive `REPAIR_ADAPTER_SHA256` from `agent/c4-repair-editset`'s **final** head, after its
   committed-head gate re-run lands, and never from `de56c60` if that head moves.
4. Confirm at the pinned compiler, before writing the Align side, that a nested record's `Option`
   members can carry a **three-way** version-selected presence rule the way they already carry the
   two-way one. If they cannot, file it rather than routing around it.
5. Walk §3.5's fifteen-place parity table against the actual files one more time immediately before
   implementation; it is the highest-value table in this document.
6. Re-derive §1.2's refusal counts from both gates' JSON at the merged head, not at `de56c60`, and
   correct §1.5's arm and the pre-committed baseline if the evidence moved.
7. Run `gmake format-check` and `git diff --check` on this document before publication.

---

## 11. Implementation record

Written after implementation, before review. Section 10's author-side checks were performed and
their outcomes are recorded here rather than asserted.

### 11.1 Ledger-to-diff mapping

| Ledger cell | Realized in |
| --- | --- |
| §3.1 new adapter, same CLI, own runtime identity | `scripts/prompt-template-adapter.py` |
| §3.2 import chain, verify-then-execute, one frozen module, consumed names | same file's `repair_adapter()` / `loaded_modules()`; `scripts/run-prompt-template-adapter-smoke` `hop_rows` |
| §3.2 bounded-divergence golden, second hop | `eval/fixtures/c4-repair-template/adapter-divergence.diff`, 116 lines |
| §3.3 version-3 field list and order | `TASK_MEASUREMENT_V3_FIELDS` / `MEASUREMENT_FIELDS_BY_VERSION` (evaluator); `TaskMeasurement` (`src/prompt_artifacts.align`); `V3_FIELDS` (adapter smoke) |
| §3.3 ten-code vocabulary, total mapping | adapter `edit_refusal_code` / `classified_refusal`; smoke `refusal_rows` drives all nine sites against the real module |
| §3.3 widened `edit_set`, `UNCHANGED_FILES` keeps its blocks | adapter `except frozen.EditFormatError`; `valid_measurement_version_three`; `verifier_measurement_version_three_shape`; `validate_measurement_version_three` |
| §3.3 completion identity, conditional text, whole-field `RESULT_LIMIT` drop | adapter `measurement()` / `assemble()`; smoke `launch_rows` `result-limit` case |
| §3.4 `EDIT_POLICY`, presence and equality | `EDIT_POLICY_FIELDS` + the `PROMPT_EVALUATION_TASK` branch; `EditPolicy` (Align); `build_edit_policy` (freeze) |
| §3.4 constant parity across five scripts | `verify_constant_parity_boundary`; adapter `MAXIMUM_FILE_BLOCKS` / `MAXIMUM_EDIT_BYTES` asserted against the frozen module in `loaded_modules()` |
| §3.5 fifteen-place parity table | walked; entries 1-5 and 9-14 changed as declared, entry 15 untouched, entries 6-8 in the Align files |
| §3.5 entry 8 (`verifier_measurement_equal`, all 31) | `src/prompt_score.align`; defect 32 is the only case that fails on its omission after the merged branch's renumbering (§11.3 item 12) |
| §3.6 corpus assets | `scripts/freeze-canonical-v1t`, `eval/prompt/canonical-v1t/`, `eval/tasks/prompt-v1t/`, re-minted over `agent/c4-repair-editset`'s re-frozen `canonical-v1e` |
| §3.8 aggregates, recomputed and adapter-selected | evaluator `row_edit_refusal_count`; `verifier_row_edit_refusals` + both aggregate verifiers; gate validator `rescore` |
| §3.9 ladder rows 2-26 | rows 2-7 in the adapter; 8-13 in `validate_input_artifact_shape` / `validated_repair_template` / the task-prompt membership check; 14-21 in `valid_task_measurement` / `valid_measurement_version_two` / `valid_measurement_version_three`; 22-24 in `repair_eligibility` / `assemble_repair_prompt` / `build_repair_attempt`; 25-26 in the aggregates and `verifier_measurement_equal` |
| §3.11 evaluator size checkpoint | **+16,359 B** (235,059 → 251,418) against the merged `agent/c4-repair-editset` base, threshold 24,000, window headroom 10,726. Neither option (a) nor (b) was needed |
| §4.2 sealed template, three changes | `REPAIR_PREAMBLE` / `REPAIR_HEADERS` in the freeze; asserted by `template_prompt_cases` |
| §4.3 task-prompt delta | `build_task_prompt`; the addition and worked example are byte-checked by the freeze's `--check` |
| §4.4 rendered `POLICY` form | `repair_policy_text`; byte golden in `policy_render_cases` |
| §4.5 `POLICY` never dropped | `REPAIR_DROP_ORDER` unchanged; asserted at every rung in `template_prompt_cases` and in `verify_template_attempt_boundary`; enforced by the gate validator and `verifier_repair_sections_exclude_status` |
| §4.6 re-derivability | `build_repair_attempt`'s producer-side re-derivation with `policy_text`; `template_prompt_cases` re-derives at every rung |
| §6.2 runner and target | `scripts/run-c4-template-gate`, `make c4-template-gate`, in no aggregate |

### 11.2 Closure-matrix cells

Every cell of §7.1-§7.7 maps to a named case. §7.1 and §7.2 are
`scripts/run-prompt-template-adapter-smoke` (`hop_rows`, `refusal_rows`, `launch_rows`); §7.3 and
§7.4 are `verify_template_attempt_boundary`, `verify_constant_parity_boundary`,
`policy_render_cases`, `template_template_cases`, and `template_prompt_cases`; §7.5 is
`src/prompt_verifier_smoke.align` defects 26-33 and 39-40 plus `make check`; §7.6 is §11.5's recompute and
the freeze's `--check`; §7.7 is the §11.4 run.

### 11.3 Deviations from the design, recorded rather than silently taken

1. **§3.3's `edit_set` prose gloss is corrected by its own invariant table.** The gloss says `Some`
   "exactly when `validated_edit_set` **returned**". `PATH_ESCAPES_SOURCE` also raises after that
   return — it fires inside `synthesized_patch` — yet the same section's eight-code table and the
   `completion_text` rule both require `edit_set` `None` for it. The realized rule is the table's:
   `Some` exactly when the refusal is `UNCHANGED_FILES`, which coincides with the gloss on every
   reachable path except that one. The producer implements it by widening only the
   `EditFormatError` handler; the `PolicyViolation` handler discards as it always did.
2. **§7.2's declared-patch cell is corrected by §3.5's presence rule.** That cell says
   `completion_*` is `None` on the declared-patch path. A response *is* received there — the
   generation child runs before `declared_patch` is consulted — so §3.3's "`Some` exactly when a
   provider response was received" makes the identity members `Some`. The ledger is the contract, so
   the realized shape is `edit_refusal: NONE`, `edit_set` `None`, `completion_text` `None`,
   `completion_bytes`/`completion_sha256` `Some`, `patch_sha256` `Some`. Asserted in `launch_rows`.
3. **§3.6's member counts were off by one and are corrected: 31 members, 22 carried, 21 identical
   in all four manifests** (design: 32 / 23 / 22). Two causes, both verified by recomputing the
   manifests directly: `canonical-v1e` carries **11** fixture files, not 12; and the three
   `eval/tasks/prompt-v1/<task>/task-prompt.json` files leave the member set, because this corpus
   reads its own. They are unmodified and remain members of the three earlier manifests.
4. **§6.1 assigns version-3 measurement decode to `scripts/run-prompt-score-smoke`; it went to
   `src/prompt_verifier_smoke.align` instead.** That script carries no `TaskMeasurement` fixture at
   all — every measurement fixture, every presence rule, and the encode/decode round-trip
   regression live in the verifier smoke. Putting the cases where the fixtures are is what the rule
   "prefer the narrowest stable owner" asks for. `make prompt-score-smoke` stays green unchanged.
5. **§3.4 lists the template adapter's participation in constant parity as transitive; it is
   direct.** The parity test could not otherwise name it as a participant, because it consumes the
   bounds through two hops and redeclares nothing. It now declares
   `MAXIMUM_FILE_BLOCKS`/`MAXIMUM_EDIT_BYTES` and `loaded_modules()` asserts them against
   `frozen.MAXIMUM_FILE_BLOCKS`/`MAXIMUM_EDIT_BYTES` at load, before any request. The fifth copy is
   what makes the other four checked rather than one more place to drift. Found by the parity test
   failing on its first run.
6. **§9.4's corrections were already applied to four of the five sites** by
   `agent/c4-repair-editset`'s own review repair, before this branch was cut:
   `c4-repair-editset.md` §1.2, `eval/prompt/c4-editset-gate/README.md`, `HANDOFF.md`, and roadmap
   item 34 all carry the corrected reading already. Only `docs/specs/c4-repair-measured.md` needed
   it, and it has it. The §1.2 correction stands; its propagation was smaller than the design
   expected, and that is a better outcome than the design assumed.
7. **`REPAIR_ADAPTER_SHA256` was provisional and is now discharged.** §6.5 prerequisite 1 and
   §10.3 require the constant to come from `agent/c4-repair-editset`'s final head. That branch's
   review repair moved the edit-set budget to a break-on-first-overflow prefix cut and re-froze
   `canonical-v1e`, moving the adapter from `e54ab3c1…` to **`fa73f9dc…`**. The merge commit
   re-derived the constant, regenerated the second-hop golden, and re-minted `canonical-v1t`; the
   repair adapter now carries **the same digest in `canonical-v1e` and `canonical-v1t`**. The
   widened `edit_set` rule inherited the repaired prefix-cut semantics with no edit, because this
   adapter **calls** `repair.edit_set_blocks` rather than copying it — which is the whole reason
   §3.1 refused to re-implement it. All nine raise sites still map, so the repair moved no message.
8. **`verifier_result_uses_repair_adapter` was widened to include the template adapter.** A
   six-kind template declares `EDITSET` too, so a version-3 corpus defines
   `repair_editset_attempt_count` exactly as a version-2 one does; leaving the predicate at "names
   the repair adapter" would have made the denominator absent for a corpus that renders the
   section. Found by defect 21 failing.
9. **Request 52 gained a narrowing worth more than a third tally mark.** Reading a nested payload's
   own `Option` field — `match attempt.measurement { Some(m) => match m.edit_refusal { … } }` — is
   **rejected** by the pinned compiler as `error: cannot move a field out of a borrowed match
   payload projection`. On a *borrowed* projection the diagnostic exists; the silent move the
   request reports is specific to a `match` on an **owned** record. Recorded in
   `docs/align-requests.md`. No new request is filed; §6.7's judgement holds.
10. **A real defect the mutation exercise surfaced, recorded because the class matters.** The freeze
    script appended `edit_policy` after `content_sha256` rather than inserting it in its declared
    position, producing a manifest the evaluator's declared-order shape check rejects and a digest
    over the wrong preimage. It was invisible while the owner test *restated* the policy rules; it
    died the moment the test drove `validate_input_artifact_shape` against the real frozen file.
    The lesson is the rule, not the bug: **a test that restates a validator's rule passes even when
    the rule has been deleted.** The seven `POLICY`-record cases now drive the real validator.
11. **Ladder row 13 is membership-only, and the digest half was wrong.** The first implementation
    compared `sha256(task-prompt bytes)` against the task's `artifacts[].expected_sha256`. Those are
    different functions: the artifact expectation is a digest over **mode, repository-relative path,
    and content**, minted by `file_expectation()` and owned by `scripts/prompt-snapshot-helper.py`,
    which verifies it before and after every invocation. The comparison rejected every corpus, and
    `make prompt-evaluate-smoke` under the Linux recipe caught it — it is the only owner that runs
    the evaluator end to end, and it failed at `INVALID_INPUT`/`INVALID_DIGEST` where it expected
    `SNAPSHOT_ERROR`. The realized row checks that the declared `task_prompt_path` is a `FILE`
    member of the task's own `artifacts`, which is the half this boundary owns; the digest stays
    with the helper that owns it. **This is the second defect in this capability that only appeared
    when a rule was driven through its real owner rather than restated**, and both were found in
    the same hour.

    A **second** correction to the same row followed, from the same owner. Membership was first
    enforced for every task, and that is also wrong: declaring the task prompt in `artifacts` is a
    `prompt-v1*` convention, not a repository-wide one. `eval/tasks/coding-v1.json` and
    `eval/tasks/smoke-v1.json` carry no `task_prompt_path` at all, and the evaluator smoke's own
    synthetic corpora declare one without listing it, so an unconditional rule rejects corpora this
    capability never touched. Row 13 is therefore **adapter-selected**, exactly as rows 8-12 and 16
    are: a task naming the template adapter must declare its own task prompt, and a task naming any
    earlier adapter is not held to it. The design's own principle — *adapter-selected, never
    version-selected, and never applied to a corpus whose adapter cannot satisfy it* — was the
    answer both times; applying it to this row from the start would have avoided both rounds.

12. **The merge with `agent/c4-repair-editset` renumbered this capability's verifier defects.** That
    branch's review repair added defects 21-25 to `src/prompt_verifier_smoke.align` for edit-set
    path uniqueness and ordering and for three version-1 absence clauses. This capability's seven
    version-3 defects were 21-27 and are now **26-32**, with §7.5's cell map reading against the new
    numbers. `src/prompt_verifier_smoke.align` was rebuilt from the merged side and this
    capability's additions re-applied on top, rather than resolved hunk by hunk, because the two
    branches changed the same five helper predicates.
13. **The second-hop divergence normalizer adopts the merged branch's parser-delimited span.** That
    repair replaced "scan for the next column-0 line" with `ast`, because a column-0 line inside a
    triple-quoted string can end a span early. This file's copy took the same change, so the two
    hops' goldens stay comparable and neither can silently truncate. The golden's byte count is
    unchanged at 116 lines.
14. **The merge broke one of the merged branch's own owner rows, and the fix belongs to this
    capability.** `scripts/run-prompt-gate-validator-smoke`'s `downgrade_measurement` helper — added
    by that branch's repair to drive ladder row 10's version-1 half directly — stripped the four
    version-2 members and set `schema_version: 1`. Once this capability made the gate fixture emit
    version 3, the helper left the four version-3 members behind, so every one of its four stray
    rows was rejected for a member it had not planted. The helper now removes every member above
    version 1, and the same loop gained four rows driving the version-3 members at version 1, which
    completes the absence matrix in both directions. A mutant deleting the below-version-3 absence
    check is killed by the new rows and by nothing else.
15. **A falsifiability gap in this capability's own pre-committed secondary, found by mutation
    after the merge and closed.** Every version-3 defect that recorded a refusal was a *rejection*
    case, so the aggregates were only ever compared against a **zero** refusal count. Zeroing
    `verifier_row_edit_refusals`'s accumulator — and, independently, the fixture's own
    `edit_refusals` helper — left `make prompt-verifier-smoke` green. The recomputation of
    `edit_refusal_count`, the number this capability reports as its secondary result, was therefore
    unverified in its non-zero arm. Defect **33** is the acceptance case that closes it: every row's
    initial attempt records `UNCHANGED_FILES` and **keeps** the blocks its refusal was computed
    from, its repair passes, and the persisted counters are 2 per variant and 4 for the corpus.
    Both mutants now die. This is the same class `c4-repair-editset.md`'s review found five times —
    a clause with no falsifying case — and it is worth stating that the merge is what exposed it:
    reading that branch's repair is what prompted the check.
16. **The gate's first run failed to publish, and the cause was a missing Align record member —
    the exact incident class section 3.5's fifteen-place parity table exists to prevent.**
    `PROMPT_EVALUATION_TASK` gains an optional `edit_policy` member (section 3.4). The Python
    evaluator emitted it and `scripts/prompt-gate-validator.py` validated it, but
    `src/prompt_artifacts.align`'s `PromptEvaluationTask` never declared it — only the new
    `EditPolicy` record type was added. The consequence is worse than an unvalidated field: a
    member the producer writes and the record omits makes the **whole document fail to decode**, so
    `prompt_artifact_io.decode_prompt_evaluation_result_source` refused the result,
    `publish_evaluator_output` never ran, and the run ended `EVALUATION_FAILED` with no
    `result.json` at all. The 22 provider calls had already succeeded.
    **Why every owner test missed it.** `scripts/prompt_gate_fixture.py` set its tasks' `argv` to
    the template adapter but never attached an `edit_policy` record, so no Align decode in any
    smoke ever saw a task carrying the member. The parity table's `PROMPT_EVALUATION_TASK` row was
    walked as "gains the optional member" and satisfied by the Python half alone.
    **The repair is three parts, not one.** The record declares the member; `verifier_task_valid`
    validates it independently through `verifier_edit_policy_valid` (present exactly for a
    template-adapter corpus, bounds equal to the enforced constants, `refuse_unchanged_files`
    true); and the gate fixture now emits it, so every consumer decodes a task that actually
    carries it. Align defects **39** and **40** cover a differing bound and an absent policy, and a
    mutant deleting the new validation is killed by them.
    **The rule worth keeping.** A field-list parity table is satisfied only when *every* named
    place is exercised by a test that would fail if the place were wrong. Three of this
    capability's four defects — the freeze's field order, ladder row 13 twice, and this one — were
    invisible to owner tests that asserted the rule instead of driving the artifact through the
    consumer that enforces it.

17. **Review found that the completed run breached its provider-call ceiling and that the record
    hid the breach.** The evaluation has 12 initial and 12 repair attempts, hence **24** ran provider
    calls against section 6.2's fixed maximum of **22**. `scripts/run-c4-template-gate` nevertheless
    wrote `addressable_ran_attempts: 22` from a literal. The three JSON artifacts remain immutable;
    the correction is recorded here and in their README. The driver now derives the count from rows,
    refuses publication above 22, makes the 60-minute ceiling fail closed, requires the exact make
    invocation, records the inspected immutable image ID, and refuses to call two absent completion
    identities agreement. The historical record's mutable image tag, absent command/image ID, and
    incorrect addressable count are known limitations, not retroactively repaired fields.

### 11.4 Gate result: qualification ceiling breached; observed predicate value 1

The measurement of record is the single completed run from clean committed head
`7ba2027d1403de92936de0eba146f649a35cb59d`, with `align_llm_clean: true`. It published 12 rows
after **24 provider calls** (12 initial and 12 repair) in **700.452 s**. Although that is inside the
3,600 s wall-clock ceiling, it exceeds section 6.2's independently pre-committed maximum of 22
calls. The named qualification therefore **failed its cost contract and has no `MET` verdict**. The
evaluation is `IMPROVED` and gate-eligible under the unchanged C6 scoring contract; those are
properties of the persisted result, not acceptance of this qualification.

**The persisted formal predicate value is 1.** `repair_recovery_count` is 2 and
`repair_recovery_paired_count` is **1**, so the exact predicate in section 1.5 evaluates to `MET`.
Because the run is outside its call ceiling, that arithmetic observation is not promoted to the
gate verdict. Both samples of `duration-half-away-from-zero` CANDIDATE fail attempt 1 with a
724-byte patch and pass attempt 2 with a 758-byte patch.

**That is not a C4 gate closure.** The same pair passed at attempt 1 in both C4 and C4E, with the
same 758-byte patch. Version 3 changed attempt 1, turned that previously passing answer into the
724-byte failure, and then recovered to the old passing answer on attempt 2. The confound accepted
before the run in section 4.3 item 4 therefore landed exactly: the predicate counts recovery from a
regression this capability introduced. `candidate_pass_count` is 2 here and was 2 at C4E;
`completion_gain_count` is 2 in both; no task passes here that did not pass before. The honest
headline is **qualification failed; observed recovery repairs an introduced regression; capability
unchanged**.

| Task | Variant | Both samples, attempt 1 -> attempt 2 | Interpretation |
| --- | --- | --- | --- |
| `duration-half-away-from-zero` | PARENT | `FAIL/TEST/716` -> `FAIL/PATCH/0`, `UNCHANGED_FILES` | A real wrong patch becomes a no-op, as at C4E |
| `duration-half-away-from-zero` | CANDIDATE | `FAIL/TEST/724` -> `PASS/758` | The counted recovery; version 3 regressed the prior first-shot 758-byte pass |
| `layer-precedence-frozen-module` | PARENT | `FAIL/PATCH/0` -> `FAIL/PATCH/0`, both `UNCHANGED_FILES` | The same 414-byte completion is re-sent |
| `layer-precedence-frozen-module` | CANDIDATE | `FAIL/PATCH/0` -> `FAIL/PATCH/0`, both `UNCHANGED_FILES` | The same 414-byte completion is re-sent |
| `record-codec-round-trip` | PARENT | `FAIL/TEST/1008` -> `FAIL/TEST/1008` | Completion changes; the patch is byte-identical |
| `record-codec-round-trip` | CANDIDATE | `FAIL/TEST/1008` -> `FAIL/TEST/1008` | Completion changes; the patch is byte-identical |

The two paired samples agree for all six (task, variant) pairs. That makes the negative reading
reproducible; it does not turn it into an improvement.

**The pre-committed secondary is not met.** `edit_refusal_count` is **10**, not `< 10`, against a
C4E baseline of 10. Its breakdown moves from eight inferred `UNCHANGED_FILES` plus two inferred
`PATH_NOT_EDITABLE` to a persisted `{"UNCHANGED_FILES": 10}`. The `POLICY` section therefore did
remove the out-of-allowlist mode — `PATH_NOT_EDITABLE` is **2 -> 0** — but those two attempts become
unchanged-file refusals, leaving the total fixed. `POLICY` is present on all 12 repair attempts,
`repair_editset_attempt_count` is 12, and the drop ladder fires zero times.

Section 1.6 reading **(b)** applies. Eight of the ten refusals belong to
`layer-precedence-frozen-module`; across both variants, both samples, and both attempts the model
reproduces the pinned file after the rule is stated three times in the prompt. The adapter and the
prompt are not the binding constraint for that task. The remaining named axes are the model and
the decoding strategy, and either requires a different experimental design because it breaks the
paired greedy comparison. No further prompt or adapter capability follows from this result.

The capability still delivers its non-performance contract: the edit policy is declared and
validated, the refusal is named and counted, the blocks behind `UNCHANGED_FILES` persist, all six
repair sections remain re-derivable, and whole-answer identity is observable. It makes **no speed
claim**; attempt 1 changed and its timing is not comparable to either prior run.

Evidence digests:

```text
c4-template-evaluation.json          3e2ca12a2f7776fdbe8a0ec3067d7fa69dc444377889df21608f38adcc342ea2
c4-template-evaluation-evidence.json 38da91e3cb5c203748938baaff8926bdd0af9b646ca57015fb621d65a8bcf954
c4-template-gate-record.json         7bbb578ebf75f7f99185f9d9daf0f7b1f9e36fb56b7985f38e0b9faf084cc86c
```

### 11.5 Verification checkpoint before review

At merged-tree head `0b44c85`, all 13 macOS owner targets pass: `gmake build`, `gmake check`,
`gmake format-check`, `gmake gate-topology-check`, `gmake prompt-verifier-smoke`,
`gmake prompt-score-smoke`, `gmake prompt-gate-validator-smoke`,
`gmake prompt-render-parity-smoke`, `gmake prompt-template-adapter-smoke`,
`gmake prompt-repair-adapter-smoke`, `gmake prompt-measurement-adapter-smoke`,
`gmake prompt-model-smoke`, and `gmake prompt-state-smoke`. `gmake fmt` leaves no diff,
`git diff --check` passes, and `scripts/freeze-canonical-v1t --check` reproduces the frozen scope.
The Linux recipe for `prompt-evaluate-smoke` also passes. The evaluator is 252,067 bytes, leaving
10,077 bytes in the four-chunk launch window; the adapter pin remains `fa73f9dc…`.

### 11.6 Review repair and canonical baseline

Two explicitly disjoint comprehensive reviews read stable merged-tree head `6b73560`, against base
tip and merge base `451aa66`. The adapter/import-chain/version-3-producer review found five issues;
the evaluator/scorer/validator, Align verifier, freeze, gate-evidence, documentation, Makefile, and
baseline-topology review found six. All eleven findings were accepted and repaired together in
`a36b15bfce75eebf2b961906220dcfc7842ba7d6`; the durable finding classes and dispositions are in
`HANDOFF.md`.

At the repair source commit all thirteen macOS owner targets named in section 11.5 pass together.
Linux/aarch64 `run-prompt-evaluate-smoke` and the full `run-prompt-template-adapter-smoke` pass;
`freeze-canonical-v1t --check` and `git diff --check` pass. The repaired evaluator is 252,862 bytes,
leaving 9,282 bytes in the four-chunk launch window, and its Align source pin is `dc1c7eec…`.

Because the repair changes `Makefile`, the canonical coding baseline was measured again from that
clean source and fixed as the required three-commit chain:

```text
SOURCE_COMMIT       a36b15bfce75eebf2b961906220dcfc7842ba7d6
ORACLE_COMMIT       37c09a36b1c79781ec76caa51a2f54c011827f9d
FINALIZATION_COMMIT c1a52b568902fcb246d39ccd96cb916ea04dcc79
```

Linux/aarch64 `gmake baseline-check` passes at the finalized head and ends `baseline chain: PASS`.
The pending measurement was removed after finalization. These three commits must remain ancestors
of the merge commit; this pull request therefore permits only a merge commit, never squash or
rebase.
