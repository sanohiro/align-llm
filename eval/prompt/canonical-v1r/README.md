# `eval/prompt/canonical-v1r/` — the C4-REPAIR-MEASURED corpus scope

Frozen. `docs/specs/c4-repair-measured.md` is the authoritative plan; this directory is the scope
that plan measures against, and it is never edited after a measurement has run against it.

## Why it exists

`maximum_repair_loops` lives in a task manifest, and every `eval/tasks/prompt-v1/*.json` manifest
is a digest-verified member of `eval/prompt/canonical-v1/corpus-file-set.manifest`. Editing one
would break `make prompt-gate-check` against the merged C6-MEASURED evidence. So enabling a single
bounded repair attempt required a new corpus rather than a new field value in the old one.

## What is new, and it is only this

- `eval/tasks/prompt-v1r/*.json` — the same three tasks with `maximum_repair_loops: 1`, a
  `generation_policy_path` pointing here, and the `repair_template_path` / `repair_template_sha256`
  pair. Every other field, including the whole fixture and adapter `artifacts` list, is
  `prompt-v1`'s.
- `repair-template.json` — the sealed `REPAIR_PROMPT_TEMPLATE`: a preamble, one fixed header per
  section kind, and a closing format reminder. The repair prompt is assembled from this template
  plus the failing attempt's own persisted diagnostics, and from nothing else.
- `generation-policy.json` — `canonical-v1`'s policy with a new id and the **observed** provider
  service revision. `max_prompt_bytes`, `max_tokens`, `temperature_micros: 0`,
  `seed_mode: PAIRED_FIXED`, and `seed_base` do not move.

## What is reused by digest, and is proved unmoved

`eval/runners/run-coding-task.py`, `scripts/prompt-measurement-adapter.py`,
`scripts/prompt-fixed-adapter.py`, `scripts/prompt-snapshot-helper.py`, every
`eval/fixtures/prompt-v1-*/repository/` file, and every `eval/tasks/prompt-v1/<task>/` artifact
appear in this corpus's `corpus-file-set.manifest` with the **same digests** they carry in
`canonical-v1`'s. That identity is the machine-checkable statement that this capability moved
none of them. `eval/prompt/canonical-v1/base-prompt.json`, `repo-prompt.json`,
`evaluation-provider-control.json`, `prompt-acceptance-policy.json`, and
`eval/prompt/gate/environment-policy.json` are reused by path, unmodified. The acceptance policy
in particular is **not** relaxed: if the run records a repair-loop regression, that is the measured
result.

## Regenerating

`scripts/freeze-canonical-v1r --provider-service-revision <revision>` writes every file here and
under `eval/tasks/prompt-v1r/`. `--check` asserts the tree already matches without writing. The
digest cascade — task manifest bytes to the file-set manifest to its raw digest to the corpus
revision to the scope to the baseline activation — is regenerated as a whole. Do not repair one
digest in isolation.
