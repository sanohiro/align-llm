# `prompt-v1` gate corpus

`prompt-v1` is the C6g1 gate corpus required by section 9 of
`docs/specs/c6-prompt-context-optimizer.md`. It holds three fixed coding tasks over one repository
family, `prompt-v1-fixture`. Each task is a `PromptEvaluationTask` manifest at
`eval/tasks/prompt-v1/<task-id>.json`; its per-task inputs live in `eval/tasks/prompt-v1/<task-id>/`:

| File | Record |
| --- | --- |
| `task.json` | the coding-runner descriptor consumed by `eval/runners/run-coding-task.py` (source fixture, pinned revision, edit allowlist, validation command) |
| `task-prompt.json` | `PromptTextArtifact` with kind `TASK_PROMPT` |
| `context-sources.json` | `ContextSources` with a non-empty patch evaluation, failure-memory JSONL, and both diagnostic streams |

The frozen membership, the corpus revision, and every scope digest live in
`eval/prompt/canonical-v1/`.

## Task designs

Every task is an information failure, not a reasoning ceiling: an unaided model can plausibly write
a patch, and the patch is rejected for a reason that a learned prompt append or an enabled
`ContextPolicy` section can supply.

### `layer-precedence-frozen-module`

Fixture `eval/fixtures/prompt-v1-layer-precedence/repository`, revision
`45c279855bc9cd7b7d9e51e5e8a800d1e353b7b9`, allowlist `src/settings.py`.

`resolve_settings` delegates layer precedence to `merge_layers` in `src/legacy.py`, and
`merge_layers` applies the layers in the historical order, so defaults win over file values and
environment values win over nothing. The defect is observable in `src/legacy.py`, which is outside
the allowlist; the repair must compose the layers inside the editable caller. The expected
unaided parent failure is a policy violation (an out-of-allowlist edit), not a test failure. The
lever is a learned append that states the repair-in-the-caller rule, or the patch-evaluation
context section, which already records one rejected out-of-allowlist attempt.

### `duration-half-away-from-zero`

Fixture `eval/fixtures/prompt-v1-duration-rounding/repository`, revision
`b6bae7e3872680fc847f4603484a07cbd18932c0`, allowlist `src/duration.py`.

`round_to_minutes` uses the built-in rounding helper, so an exact half minute rounds to even instead
of away from zero. The obvious replacement, `math.floor(seconds / 60 + 0.5)`, fixes the positive
half minute and still fails the negative one. The checked-in failure-memory JSONL records exactly
that prior wrong attempt under this task ID, so an enabled failure-memory section is the lever. The
same file carries one event for a different task ID, so a correct renderer must select by `task_id`
alone.

### `record-codec-round-trip`

Fixture `eval/fixtures/prompt-v1-record-codec/repository`, revision
`4597a448a14a5cfb48521f9c9a796d9686cd510e`, allowlist `src/encode.py` and `src/decode.py`.

The encoder escapes the delimiter but not the escape character or an embedded newline, and the
decoder has no matching unescape rule for either. The repair must change both sides of one shared
escaping contract. This is the headroom hedge: a moderate multi-file repair whose failure mode is an
ordinary test failure rather than a policy violation.

## Fixture rules

Every fixture repository is a Python package with `src/` and `tests/`, a `.gitattributes` holding
`* -text`, and no other content. Tests are stdlib `unittest` modules with alphabetically ordered
test methods and no clock, network, filesystem, environment, or random access. Validation is
exit-code only, through `python3 tests/<module>.py -v`. Each fixture is far below the 128-file
snapshot bound, and no expectation covers a `__pycache__` entry because the runner sets
`PYTHONDONTWRITEBYTECODE`.

Each `repo_revision` is the deterministic commit produced by the `eval/runners/run-coding-task.py`
pinned-checkout recipe: copy the fixture tree, normalize modes, `git init --object-format=sha1
--initial-branch=main`, disable `core.autocrlf`, enable `core.filemode`, then commit under the
frozen `FIXTURE_GIT_ENV` identity and date. Re-running that recipe over an unchanged fixture must
reproduce the recorded SHA; the runner asserts it.

## Bindings that are not final

These manifests are the reviewed C6g1 candidate. Two bindings are deliberately not final, and
each one fails closed rather than silently degrading:

- `provider_control_path` names `eval/prompt/canonical-v1/evaluation-provider-control.json`, which
  does not exist yet. The provider decision (kind, endpoint identity, model, service revision) is
  pending.
- `environment_policy_path` names `eval/prompt/gate/environment-policy.json`. Section 11.3 keeps the
  environment policy out of the frozen scope set; it travels with the C6g2 gate evidence.
Replacing either binding changes the task bytes, and therefore the corpus `FILE_SET` digest,
the scope digest, and the `baseline-v1` envelope digest. Regenerate all of them together.

## Settled measurement bindings

`cmd`/`argv` and `measurement_adapter_runtime` bind `scripts/prompt-measurement-adapter.py`, the
provider-backed measurement adapter. The shipped evaluator additionally requires
`scripts/prompt-fixed-adapter.py` and `scripts/prompt-snapshot-helper.py` to appear in the declared
task source, so all three are listed in every task's `artifacts` array and are corpus members; the
fixed adapter is retained source only and is no longer any task's adapter.

The section 11.3 task-parameterized inputs are declared: `validation_runner_path`/`_sha256` name
`eval/runners/run-coding-task.py`, `task_definition_path`/`_sha256` name that task's `task.json`
runner descriptor, `validation_argv` is `["--retained-inputs", "%TASK%", "%PATCH%"]`, and the
`patch_path`/`patch_sha256` pair is `null` because the patch comes from the generation response
rather than from a checked-in fixture patch.
