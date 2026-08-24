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
base-prompt.json                     dbb55e44b44fd2933d3aa1357f542ff247b645efaddd552df3c7b37f40811b39
repo-prompt.json                     1be40aada3352a4622eed7446820cacd1127b0ffaecc74a3a796aeba5fcd1d21
prompt-acceptance-policy.json        7b7070aa292b404908c1a6cac66aa8ec93db1e247971ad3832cddda34793ccc3
generation-policy.json               2429bbf591fa2315ac031eb5eb55f1d986becbe9fdce04c21e0d50fca8a987e3
corpus-file-set.manifest (raw bytes) 2206cfa59db6c6fa807fc1efc52d6de20c93ac3e2361cb7d01e54efcb3081bd3
corpus.json                          7b1f8bbd7f07d9af341a00714502fc3a72faed61ea66d1d3fc23d99b17e76191
scope.json                           cfeb9aafaa0caa2f1146a33139d6ef2c84dbaaab712464df647652d4f3b7a828
prompt-activation-baseline-v1.json   6b32bbfe5df5a77a0c8310862c76baa6609c53251b52272ccb04cd19ff5302ce
```

The corpus revision is `FILE_SET`, not `GIT_COMMIT`: the task files are checked into this repository,
so no commit that contains them can be named from inside them. `corpus-file-set.manifest` is a
separate regular file, is excluded from its own membership, and lists every declared corpus and task
source file — the three task manifests, each task's runner descriptor, task prompt and context
sources, `eval/runners/run-coding-task.py`, `scripts/prompt-fixed-adapter.py`,
`scripts/prompt-snapshot-helper.py`, and every file in the three fixture repositories.

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
- The corpus tasks bind `scripts/prompt-fixed-adapter.py` as their measurement adapter, which is the
  only adapter that exists and is also required in the declared task source by the shipped
  evaluator. A provider-backed gate adapter must replace it.

Recording the provider decision rewrites `generation-policy.json`, and therefore `scope.json` and
`prompt-activation-baseline-v1.json`. Replacing the measurement adapter additionally rewrites every
task manifest, `corpus-file-set.manifest`, and `corpus.json`. Regenerate the affected files together
and re-review; do not repair one digest in isolation.

`prompt-activation-baseline-v1.json` is the repository's canonical human-owned baseline envelope. It
is not the C6d fixture envelope under `eval/fixtures/`, and it cannot satisfy a real-provider
acceptance until the bindings above are closed and a pilot run has exercised the corpus end to end.
