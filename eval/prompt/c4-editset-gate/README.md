# `eval/prompt/c4-editset-gate/` — the C4-REPAIR-EDITSET measured evidence

Frozen. `docs/specs/c4-repair-editset.md` section 11.4 is the analysis; this directory is the
evidence it analyses, and it is never edited after the run.

## The result

**`NOT_MET`.** `repair_recovery_paired_count: 0` over 10 repair attempts, 12 rows, 3 tasks x 2
variants x 2 paired samples at `temperature_micros: 0` and `seed_mode: PAIRED_FIXED`, 22 provider
generation calls, 823.67 s against a recorded 60-minute ceiling. The gate predicate is
C4-REPAIR-MEASURED's unchanged, so the two runs are directly comparable.

`repair_editset_attempt_count: 6` — exactly the addressable arm stated before the run. The six
repair prompts that could carry `EDITSET` all carried it; no section was ever dropped, and the
assembled prompts ran 8,348 to 16,904 bytes of a 65,536-byte budget.

## What it settles

On all four rows where both attempts produced a patch, `attempts[1].measurement.patch_sha256`
equals `attempts[0]`'s **exactly**. C4 could only say "the same byte count"; this says the same
bytes. On the two `duration-half-away-from-zero` PARENT rows the model, shown its own rejected
answer, emitted no parsable `FILE:` block at all — a mode change from a wrong patch to no patch.

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
