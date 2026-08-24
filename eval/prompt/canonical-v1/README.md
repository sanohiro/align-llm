# `canonical-v1` frozen scope assets

This directory holds the section 4.4 freeze set named by section 11.3 of
`docs/specs/c6-prompt-context-optimizer.md`. C6g1 finalizes, reviews, and freezes these files;
C6g2 must not mutate them after measuring against them.

| File | Record | Notes |
| --- | --- | --- |
| `base-prompt.json` | `PromptTextArtifact`, kind `BASE_PROMPT`, `base-v1` | human-owned agent policy |
| `repo-prompt.json` | `PromptTextArtifact`, kind `REPO_PROMPT`, `repo-v1` | human-owned rules for the `prompt-v1-fixture` family |
| `prompt-acceptance-policy.json` | `PromptAcceptancePolicy`, `prompt-acceptance-v1` | the section 7 checked-in thresholds, unchanged |
| `generation-policy.json` | `GenerationPolicy`, `prompt-v1-generation-v1` | `PAIRED_FIXED`, `temperature_micros: 0`, `seed_base: 20260824` |
| `corpus-file-set.manifest` | canonical `FILE_SET` manifest | the exact corpus membership, modes, and file digests |
| `corpus.json` | `PromptEvaluationCorpus`, `prompt-v1` | pins the three `eval/tasks/prompt-v1/` manifests and the `FILE_SET` revision |
| `scope.json` | `PromptScope` | binds the corpus revision and the generation, acceptance, base, and repo digests |
| `prompt-activation-baseline-v1.json` | `PromptActivationResult`, `baseline-v1` | `BASELINED`/`BASELINE`, empty parent and accepted fields, empty learned append |

`evaluation-provider-control.json` is intentionally absent; see "Open bindings" below.

## Identity

Each record's `content_sha256` is SHA-256 over its canonical encoding with `content_sha256` replaced
by the empty string, so a file may be pretty-printed without changing its identity. Current digests:

```text
base-prompt.json                     a9c23b5ab11aa3b03514db43d4b994ad2f79dbc0040376231f4931e41ff9da0a
repo-prompt.json                     1be40aada3352a4622eed7446820cacd1127b0ffaecc74a3a796aeba5fcd1d21
prompt-acceptance-policy.json        7b7070aa292b404908c1a6cac66aa8ec93db1e247971ad3832cddda34793ccc3
generation-policy.json               2429bbf591fa2315ac031eb5eb55f1d986becbe9fdce04c21e0d50fca8a987e3
corpus-file-set.manifest (raw bytes) 7e6cc468e50951f9e7d8b1d4faf820ee3c1f51766fe241ea3e4078779413c508
corpus.json                          03e83d7c1f94bdcc0af572a1c371435ce0819c8e37a38af350621d2542a6637d
scope.json                           ad57d6778fb380155b02c61701b88b97da1bb3227571932e0b45a7681aa7b825
prompt-activation-baseline-v1.json   d134f5087b9bb33bf34735c4f5c0a67ba31fc143eb672ba448e98322a4f05e57
```

`base-prompt.json` states the section 11.3 measurement response format: whole-file `FILE:` blocks,
never a diff, and only the paths the task prompt declares editable. The task prompts under
`eval/tasks/prompt-v1/` repeat the same contract with each task's exact allowlist.

The corpus revision is `FILE_SET`, not `GIT_COMMIT`: the task files are checked into this repository,
so no commit that contains them can be named from inside them. `corpus-file-set.manifest` is a
separate regular file, is excluded from its own membership, and lists every declared corpus and task
source file — the three task manifests, each task's runner descriptor, task prompt and context
sources, `eval/runners/run-coding-task.py`, `scripts/prompt-measurement-adapter.py`,
`scripts/prompt-fixed-adapter.py`, `scripts/prompt-snapshot-helper.py`, and every file in the three
fixture repositories. The fixed adapter is no longer any task's measurement adapter, but the shipped
evaluator still requires it and the snapshot helper to be declared task source, so it stays a corpus
member.

The baseline variant uses `variant_id: baseline-v1` and `candidate_id: BASELINE` with an empty
learned append and a fully disabled `ContextPolicy` (every flag false, every limit zero). The shipped
evaluator's renderer currently rejects any enabled context section for a fixed corpus, so the
disabled policy is the only reviewable baseline today; enabling a section is a candidate-side change
that the renderer must accept before the `ContextPolicy` lever can be measured.

## Open bindings

The set is internally consistent and every digest is real, but it is not yet a final freeze:

- `evaluation-provider-control.json` is not authored. The provider decision — endpoint, model, and
  service revision — is pending.
- `generation-policy.json` therefore carries `provider_control_sha256` as 64 zeros, which is a
  deliberately unbound digest, and `pending-provider-decision` for the endpoint identity, model, and
  service revision.
- `generation-policy.json` and `scope.json` declare `evaluation_provider_kind: FIXTURE`. The
  artifact codec accepts only `FIXTURE`, `CLOUD_OPENAI`, `LOCAL_OPENAI`, or `LLAMA_CPP`, so a
  "pending" label is not representable; `FIXTURE` is the fail-closed choice because section 8 makes
  a `FIXTURE` provider gate-ineligible. No accepted gate result can be produced from this scope.
Recording the provider decision rewrites `generation-policy.json`, and therefore `scope.json` and
`prompt-activation-baseline-v1.json`. Replacing the measurement adapter additionally rewrites every
task manifest, `corpus-file-set.manifest`, and `corpus.json`. Regenerate the affected files together
and re-review; do not repair one digest in isolation.

The measurement-adapter binding is closed: every task now binds the provider-backed
`scripts/prompt-measurement-adapter.py` through `cmd`/`argv` and `measurement_adapter_runtime`, and
declares its validation runner, task definition, and validation argv as parameterized inputs.

`prompt-activation-baseline-v1.json` is the repository's canonical human-owned baseline envelope. It
is not the C6d fixture envelope under `eval/fixtures/`, and it cannot satisfy a real-provider
acceptance until the bindings above are closed and a pilot run has exercised the corpus end to end.
