# `eval/prompt/canonical-v1u/` — repaired, unqualified C4-REPAIR-TEMPLATE scope

Status: **UNQUALIFIED**. `docs/specs/c4-repair-template.md` section 11.7 is authoritative. This
scope has new paths and identities because review repair changed the template adapter after the
only provider run. The three artifacts in `eval/prompt/c4-template-gate/` bind `prompt-v1t`, never
this scope. Its current 24-call topology exceeds the fixed 22-call ceiling and the gate rejects it
before a provider call; a later qualification needs a separately reviewed topology at or below 22.

## Why it exists

Read both prior gate runs' evidence and the largest failure class is not what three design
documents said it was. Every `failure_kind: PATCH` row carries `diagnostic_summary: "the response
reproduced the pinned files unchanged"` — `synthesized_patch`'s refusal, raised *after*
`parse_file_blocks` returned terminated blocks and *after* `validated_edit_set` accepted every
declared path. No attempt in forty-four provider calls has ever failed to parse. Ten of twenty-two
ran attempts in each run were refused by the edit policy: eight for reproducing the pinned files
unchanged and two for naming a path outside the editable set. **The rule the model actually broke
is stated in no prompt in this repository.**

Stating it changes the task prompt and the repair template, both of which are corpus members, and
adds a third measurement adapter, which is also one. `canonical-v1e` cannot be extended:
`eval/prompt/c4-editset-gate/` was measured against its exact scope digest.

## What is new, and it is only this

- `scripts/prompt-template-adapter.py` — the third measurement adapter and the second hop of an
  import chain. It **loads `scripts/prompt-repair-adapter.py` by path**, over bytes it verified
  against a hard-coded digest, and reaches the frozen base adapter through *that* module's
  accessor, so exactly one frozen module object exists per process. It emits `TASK_MEASUREMENT` at
  `schema_version: 3` with a ten-code `edit_refusal`, the completion's bounded identity, a
  conditional bounded completion excerpt, and — the point of the capability — the edit set on the
  reproduced-unchanged refusal, which the repair adapter builds one line before the raise and then
  discards. It reports **its own** runtime identity.
- `eval/tasks/prompt-v1u/<task>/task-prompt.json` — `prompt-v1`'s three task prompts plus two
  rules and a worked example. **Attempt 1 changes**, identically for both variants: six of the ten
  refusals are attempt-1 refusals, and `render()` takes the task prompt independently of the
  variant, so the C6 PARENT/CANDIDATE contrast is preserved.
- `eval/tasks/prompt-v1u/*.json` — `prompt-v1e`'s three manifests with `cmd`/`argv` naming the
  template adapter, `measurement_adapter_runtime` at its digest, the three paths pointing here, an
  added `edit_policy` record, and all three adapters plus the new task prompt in `artifacts`.
- `repair-template.json` — the sealed `REPAIR_PROMPT_TEMPLATE` with a sixth section kind,
  `POLICY`, rendered per task from the digest-pinned task definition and the declared policy, and
  **never dropped**. The preamble states the unchanged-file refusal and carries a worked example.
- `generation-policy.json` — `canonical-v1e`'s policy with a new id and the **observed** provider
  service revision, re-derived at freeze time and never inherited. `max_prompt_bytes`,
  `max_tokens`, `temperature_micros: 0`, `seed_mode: PAIRED_FIXED`, and `seed_base` do not move.

## What is reused by digest, and is proved unmoved

The 22 members this corpus carries from `canonical-v1e` appear there and in measured
`canonical-v1t` at the **same digests**:
`eval/runners/run-coding-task.py`, all four scripts including both earlier adapters, every
`eval/fixtures/prompt-v1-*/repository/` file, and every `eval/tasks/prompt-v1/<task>/task.json` and
`context-sources.json`. Twenty-one members carry identical digests in all five manifests;
`scripts/prompt-repair-adapter.py` is shared by `canonical-v1e`, measured `canonical-v1t`, and this
scope only, because it did not exist before the third freeze.
`scripts/freeze-canonical-v1u` asserts both loaded adapters' digests against every earlier manifest
and against the constants that own them before it mints anything.

The three `eval/tasks/prompt-v1/<task>/task-prompt.json` files are **not** members here: this
corpus reads its own. They are unmodified and remain members of the three earlier manifests.

`eval/prompt/canonical-v1/base-prompt.json`, `repo-prompt.json`,
`evaluation-provider-control.json`, `prompt-acceptance-policy.json`, and
`eval/prompt/gate/environment-policy.json` are reused by path, unmodified. The acceptance policy in
particular is **not** relaxed: if the run records a repair-loop regression, that is the measured
result.

## Regenerating

`scripts/freeze-canonical-v1u --provider-service-revision <revision>` writes every file here and
under `eval/tasks/prompt-v1u/`. `--check` asserts the tree already matches without writing. The
digest cascade — template-adapter bytes to the task manifests to the file-set manifest to its raw
digest to the corpus revision to the scope to the baseline activation — is regenerated as a whole.
Do not repair one digest in isolation.
