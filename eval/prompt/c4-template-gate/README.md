# `eval/prompt/c4-template-gate/` — the C4-REPAIR-TEMPLATE gate evidence

Measured, published, and never edited after the fact. `docs/specs/c4-repair-template.md` is the
authoritative plan; section 11.4 carries the analysis.

## Verdict

**Qualification failed: the provider-call ceiling was breached.** The rows contain
`repair_recovery_paired_count: 1` against the predicate
`repair_recovery_paired_count >= 1`, which `c4-repair-measured.md` section 1.4 fixed and
`c4-repair-editset.md` section 1.5 restated unchanged, so all three runs compare directly.
12 rows, 24 provider calls (12 initial + 12 repair), 700.452 s against a recorded 60-minute
ceiling, from the clean committed head `7ba2027` with `align_llm_clean: true`. Section 6.2 also
pre-committed a maximum of 22 provider calls. The run exceeded that independent ceiling, so its
formal predicate value is observational evidence and **not a `MET` qualification verdict**.

The immutable gate record incorrectly says `addressable_ran_attempts: 22`; the driver wrote a
literal rather than deriving the 24 ran attempts. It also records a mutable image tag without the
required immutable image ID or exact make command. The JSON artifacts are preserved as produced;
the authoritative correction is this README and `docs/specs/c4-repair-template.md` section 11.4.

**The pre-committed secondary was not met.** `edit_refusal_count: 10` against a target of `< 10`
and a C4E baseline of 10 of 22. The count did not move.

## Read the two numbers together, because they disagree

The predicate is satisfied by one (task, variant) pair: `duration-half-away-from-zero` CANDIDATE recovers in
both paired samples, attempt 1 `FAIL` at 724 B and attempt 2 `PASS` at 758 B.

**That pair passed at attempt 1 in both prior runs**, first-shot, at 758 B. Under version 3 it
fails attempt 1 and recovers to the same 758-byte patch at attempt 2. `candidate_pass_count` is 2
here and was 2 in C4E; `completion_gain_count` is 2 in both. **No task passes here that did not
pass before.** The recovery the gate counts is recovery from a regression this capability's own
attempt-1 change introduced — section 4.3 item 4 recorded that confound before the run, and this is
it landing. The honest statement is that the predicate is satisfied and the underlying capability
of the corpus is unchanged.

## What did change, and it is not nothing

- **`PATH_NOT_EDITABLE` went 2 -> 0.** Both C4 and C4E refused two attempts for naming
  `src/legacy.py`, a path the repair template never listed. The `POLICY` section lists the
  editable paths per task and no attempt named an out-of-allowlist path again. Those two rows now
  fail as `UNCHANGED_FILES` instead, which is why the total is unchanged at 10.
- **The refusal is now a named, counted, diagnosable outcome.** `edit_refusal_breakdown` is
  `{"UNCHANGED_FILES": 10}` — a fact no prior run could state, and the correction section 1.2 made
  is now machine-checkable rather than an argument about a free-text string.
- **`POLICY` was carried on all 12 repair attempts** and the drop ladder never fired.
- **Whole-answer identity is measurable.** `completion_sha256` shows all four
  `layer-precedence-frozen-module` rows re-sent a byte-identical answer at attempt 2
  (`same_answer: true`), while `record-codec-round-trip` changed its answer and still produced a
  byte-identical patch. The two paired samples agree on every (task, variant) pair.

## What it does not show

The unchanged-file statement did not reduce refusals. Eight of the ten refused attempts are
`layer-precedence-frozen-module`, where the model reproduces the pinned file on all four rows and
on both attempts, having been told three times in the same prompt not to. Section 1.6 reading (b)
applies: neither the adapter nor the prompt is the binding constraint on that task, and the
remaining axes are the model and the decoding strategy.

No speed claim. Attempt-1 timings are not comparable to C4 or C4E because attempt 1 itself changed.

## Files

- `c4-template-evaluation.json` — `PROMPT_EVALUATION_RESULT`, schema 2, 12 rows, version-3
  measurements.
- `c4-template-evaluation-evidence.json` — `PROMPT_EVALUATION_EVIDENCE`, 24 expected inputs.
- `c4-template-gate-record.json` — the run record: host, image, privileges, provider probe, in-band
  model id, wall clock against the ceiling, the pre-committed counters, and the per-row table.
