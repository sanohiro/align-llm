# `eval/prompt/canonical-v1e/` — the C4-REPAIR-EDITSET corpus scope

Frozen. `docs/specs/c4-repair-editset.md` is the authoritative plan; this directory is the scope
that plan measures against, and it is never edited after a measurement has run against it.

## Why it exists

C4-REPAIR-MEASURED measured a repair prompt carrying the failing attempt's status labels and
diagnostics but not its edits, and recovered nothing in ten attempts: on all six attempts where
attempt one had produced a validated edit set, attempt two returned a patch of exactly the same
byte count. Showing the model what it wrote requires a second measurement adapter, which is a
corpus member, which requires a corpus. `canonical-v1r` cannot be extended: `eval/prompt/
c4-repair-gate/` was measured against its exact scope digest, and a `prompt-v1e` task must name a
different adapter anyway, which changes its own `content_sha256`.

## What is new, and it is only this

- `scripts/prompt-repair-adapter.py` — the second measurement adapter. It **loads the frozen
  `scripts/prompt-measurement-adapter.py` by path**, over bytes it verified against a hard-coded
  digest, and calls its containment, sealing, redaction, process-ownership, generation, validation,
  and edit-parsing functions unchanged. It emits `TASK_MEASUREMENT` at `schema_version: 2` and
  reports **its own** runtime identity.
- `eval/tasks/prompt-v1e/*.json` — `prompt-v1r`'s three manifests with `cmd`/`argv` naming the
  repair adapter, `measurement_adapter_runtime` at its digest, the two paths pointing here, and
  both adapters in `artifacts`. Everything else, including every fixture and runner expectation, is
  `prompt-v1r`'s.
- `repair-template.json` — the sealed `REPAIR_PROMPT_TEMPLATE` with a fifth section kind,
  `EDITSET`, rendered in the response's own whole-file format and dropped **last**.
- `generation-policy.json` — `canonical-v1r`'s policy with a new id and the **observed** provider
  service revision, re-derived at freeze time and never inherited. `max_prompt_bytes`,
  `max_tokens`, `temperature_micros: 0`, `seed_mode: PAIRED_FIXED`, and `seed_base` do not move.

## What is reused by digest, and is proved unmoved

The 24 members this corpus shares with `canonical-v1` and `canonical-v1r` appear in all three
`corpus-file-set.manifest` files with the **same digests**: `eval/runners/run-coding-task.py`,
`scripts/prompt-measurement-adapter.py`, `scripts/prompt-fixed-adapter.py`,
`scripts/prompt-snapshot-helper.py`, every `eval/fixtures/prompt-v1-*/repository/` file, and every
`eval/tasks/prompt-v1/<task>/` artifact. `scripts/freeze-canonical-v1e` asserts the base adapter's
digest against both earlier manifests and against the repair adapter's own hard-coded constant
before it mints anything.

`eval/prompt/canonical-v1/base-prompt.json`, `repo-prompt.json`,
`evaluation-provider-control.json`, `prompt-acceptance-policy.json`, and
`eval/prompt/gate/environment-policy.json` are reused by path, unmodified. The acceptance policy in
particular is **not** relaxed: if the run records a repair-loop regression, that is the measured
result.

## Regenerating

`scripts/freeze-canonical-v1e --provider-service-revision <revision>` writes every file here and
under `eval/tasks/prompt-v1e/`. `--check` asserts the tree already matches without writing. The
digest cascade — repair-adapter bytes to the task manifests to the file-set manifest to its raw
digest to the corpus revision to the scope to the baseline activation — is regenerated as a whole.
Do not repair one digest in isolation.
