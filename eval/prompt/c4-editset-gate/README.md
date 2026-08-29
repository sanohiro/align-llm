# `eval/prompt/c4-editset-gate/` — the C4-REPAIR-EDITSET measured evidence

Frozen. `docs/specs/c4-repair-editset.md` section 11.4 is the analysis; this directory is the
evidence it analyses, and it is never edited after the run.

## The result

**`NOT_MET`.** `repair_recovery_paired_count: 0` over 10 repair attempts, 12 rows, 3 tasks x 2
variants x 2 paired samples at `temperature_micros: 0` and `seed_mode: PAIRED_FIXED`, 22 provider
generation calls, 839.492 s against a recorded 60-minute ceiling — the clock of the run recorded
here, which is the run from the clean committed head `9516e75`. The gate predicate is
C4-REPAIR-MEASURED's unchanged, so the two capabilities' runs are directly comparable.

Three runs of this corpus exist and **every correctness value here is identical in all three** —
verdict, rows, statuses, failure kinds, patch sizes, aggregates, assembled prompt sizes, all four
patch digests, and every `edit_set` block digest. The clocks moved: 839.492 s, 940.931 s, and
823.67 s. So did per-run **environment identity**, which is not a correctness value and not a gate
input: each run gets a fresh sandbox directory, every `unittest` traceback frame in
`diagnostic_stderr` quotes it, and the `STDERR` section of a repair prompt carries that text, so
`rendered_prompt_sha256` on the `REPAIR` attempt differs on six rows between the last two runs,
along with the snapshot and request digests that bind those bytes. Spec section 11.4 names them.
The third run exists because review repair moved the repair adapter's bytes, which every row names
by digest; spec section 11.3 deviation 15 records it.

`repair_editset_attempt_count: 6` — exactly the addressable arm stated before the run. The six
repair prompts that could carry `EDITSET` all carried it; no section was ever dropped, and the
assembled prompts ran 8,348 to 16,904 bytes of a 65,536-byte budget.

## What it settles

On all four rows where both attempts produced a patch, `attempts[1].measurement.patch_sha256`
equals `attempts[0]`'s **exactly**. C4 could only say "the same byte count"; this says the same
bytes. On the two `duration-half-away-from-zero` PARENT rows the model, shown its own rejected
answer, returned the pinned files **unchanged** — a well-formed answer that changes nothing, so
every hunk is empty and no patch is synthesized. That is a mode change from a wrong patch to a
no-op. All eight `failure_kind: PATCH` rows in this run carry
`diagnostic_summary: "the response reproduced the pinned files unchanged"`; none is a parse
failure. Note that `edit_set` is `None` on those rows: the adapter builds the blocks and then
discards them when the patch turns out empty, which spec section 11.3 deviation 14 records as the
gap the next capability closes.

`c4-repair-measured.md` section 5.7's tie-breaker is therefore answered in the negative: on this
model and this corpus the missing edit set was not the binding constraint, and the next capability
is the prompt, the template, and the edit policy rather than more adapter work.

## Files

- `c4-editset-evaluation.json` — `PROMPT_EVALUATION_RESULT` `schema_version: 2`, whose rows carry
  `TASK_MEASUREMENT` at `schema_version: 2` with the realized `edit_set`, `edit_set_total_bytes`,
  `patch_sha256`, and `base_adapter_runtime_identity`.
- `c4-editset-evaluation-evidence.json` — the independently produced expected-input digests, one
  per attempt.
- `c4-editset-gate-record.json` — the run record: verdict, commit, `.align-revision`, image, Docker
  version, forwarder, container privileges, the fail-closed provider probe, the in-band model id,
  wall clock against the ceiling, the corpus aggregate, and the per-row table including
  `same_patch_resent`.

`gate_eligible` is `false` because that is the **C6 acceptance** verdict, which requires `IMPROVED`
with no serious-regression reason; this run's status is `SERIOUS_REGRESSION` from two `POLICY` rows.
The C4 gate does not read it.
