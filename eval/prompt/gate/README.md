# C6-MEASURED checked-in gate evidence

This directory holds the section 9 gate evidence named by section 11.3 of
`docs/specs/c6-prompt-context-optimizer.md`: one human-owned `PromptGateManifest` and the
artifacts it references. Everything here except the manifest and this file was produced by a real
provider-backed run against the frozen `eval/prompt/canonical-v1/` scope assets.

| File | Record | Producer |
| --- | --- | --- |
| `prompt-gate-manifest.json` | `PromptGateManifest` with its embedded `PromptGateSourceLocator` | human-owned; no command emits it |
| `environment-policy.json` | `EnvironmentPolicy`, `prompt-v1-gate-environment-v1` | human-owned; travels with the gate evidence, not with the frozen scope set |
| `prompt-activation-baseline-v1.json` | `PromptActivationResult`, `baseline-v1` | a copy of the canonical baseline envelope in `eval/prompt/canonical-v1/` |
| `prompt-evaluation-improved.json` | `PromptEvaluationResult`, `c6g2-measure` | `./main prompt evaluate` |
| `prompt-evaluation-improved-evidence.json` | `PromptEvaluationEvidence`, `c6g2-measure` | the same `prompt evaluate` run's independent sidecar |
| `prompt-activation-accepted.json` | `PromptActivationResult`, `c6g2-accept-v1` | `./main prompt accept` |
| `prompt-activation-rolled-back.json` | `PromptActivationResult`, `c6g2-rollback-v1` | `./main prompt rollback` |

The chain is `baseline-v1` -> `c6g2-accept-v1` -> `c6g2-rollback-v1` over one shared scope. The
accepted activation carries the evaluated candidate variant; the rollback restores the baseline
variant and names the baseline as its target. Lineage inside each `PromptActivation` uses the
nested activation ID and digest, per section 4.4.

`environment-policy.json` is not a corpus member: the frozen task manifests bind it by path, and the
`FILE_SET` corpus manifest does not list it.

## What the locator does and does not pin

`source_locator` records bundle-relative paths and content identities only. The Python interpreter,
the Git tool, and the derived generation child are explicit per-run inputs supplied on the command
line, so no absolute or machine-specific path is frozen here. The generation child is built, never
committed, so the locator records its digest alone.

## Running the validator

The gate validator takes five explicit values; the working directory must be the clean, non-shallow
CI checkout whose `HEAD` contains this directory:

```text
<python3.12> scripts/prompt-gate-validator.py \
  --source-bundle-root <absolute-bundle-root> \
  --python-executable-path <absolute-physical-python3.12> \
  --git-executable-path <absolute-git> \
  --generation-child-path <absolute-built-./main> \
  --generation-child-sha256 <its-digest>
```

The source bundle holds `align-llm/` (a clean checkout at the tested head, which is also the
`FILE_SET` corpus root), `align/` (a clean checkout at `.align-revision`),
`scripts/prompt-source-verifier.py`, and `source-verifier-policy.json` — the same content-bound
policy document the evaluate request consumed. The validator is Linux-only: it execs through
`/proc/self/fd` and scans `/proc` for descendants.
