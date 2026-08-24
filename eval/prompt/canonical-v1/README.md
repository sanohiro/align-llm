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
| `evaluation-provider-control.json` | `EvaluationProviderControl`, `prompt-v1-provider-control-v1` | the executable `LOCAL_OPENAI` provider inputs |
| `corpus-file-set.manifest` | canonical `FILE_SET` manifest | the exact corpus membership, modes, and file digests |
| `corpus.json` | `PromptEvaluationCorpus`, `prompt-v1` | pins the three `eval/tasks/prompt-v1/` manifests and the `FILE_SET` revision |
| `scope.json` | `PromptScope` | binds the corpus revision and the generation, acceptance, base, and repo digests |
| `prompt-activation-baseline-v1.json` | `PromptActivationResult`, `baseline-v1` | `BASELINED`/`BASELINE`, empty parent and accepted fields, empty learned append |

The provider decision is recorded; see "Provider binding" below.

## Identity

Each record's `content_sha256` is SHA-256 over its canonical encoding with `content_sha256` replaced
by the empty string, so a file may be pretty-printed without changing its identity. Current digests:

```text
base-prompt.json                     a9c23b5ab11aa3b03514db43d4b994ad2f79dbc0040376231f4931e41ff9da0a
repo-prompt.json                     1be40aada3352a4622eed7446820cacd1127b0ffaecc74a3a796aeba5fcd1d21
prompt-acceptance-policy.json        7b7070aa292b404908c1a6cac66aa8ec93db1e247971ad3832cddda34793ccc3
evaluation-provider-control.json     f8f9043231d8f4213ceb392bf5a05c600e6c2796015deeb44c96436eb77cb469
generation-policy.json               e5887c233dbb21bacad79923c2b9f43eba250c8b0fa2550354f6ffbf8960133e
corpus-file-set.manifest (raw bytes) 7544e743167ddf97167145217b963c8f92bf41348ecb45c935ed38b1b93b1b07
corpus.json                          c051c6f7ab181662a33880c67693bc33f96e2abef4d48f1f5d6b99a3b744254b
scope.json                           e543fc8be4cf5eb5f731550917240362dbea7b2c0afea01a3306816024a7c4f3
prompt-activation-baseline-v1.json   e8d1043370d1ffadb1ece420ad3e25d3f109c4112c28724e53405bc9cf82653a
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

## Provider binding

The provider decision is recorded and every digest is real, so the set is a complete freeze:

- `evaluation-provider-control.json` declares the executable `model.ProviderConfig` inputs:
  `LOCAL_OPENAI`, endpoint `http://127.0.0.1:18080/v1/chat/completions`, endpoint ID
  `local-llamacpp-openai-18080`, model `qwen2.5-coder-7b-instruct-q4_k_m`, `api_key_env: null`
  (this local service has no credential; `LOCAL_OPENAI` makes the name optional),
  `tokenize_endpoint: null` (the OpenAI chat adapter does not use one), `timeout_ns`
  1,800,000,000,000, and `max_response_bytes` 262,144.
- `generation-policy.json` binds that control by digest and repeats its kind, endpoint ID, and
  model, as section 4.5 requires. Its `provider_service_revision` is the one declared
  provider-service identity field and carries the served build and weights:

  ```text
  llama.cpp/b10610+a14dba686aaafba3a2d6b5eb8820b0df5c5d2d92
  ;server-sha256:e3905073c4322ff33c7b365c9ea10aadbc776fe3eab372869694555d8f5693a8
  ;model-sha256:509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c
  ```

  (one 214-byte line in the artifact, inside the 256-byte bound).
- `scope.json` and `prompt-activation-baseline-v1.json` repeat the provider kind and model and bind
  the new generation-policy digest, so the whole chain is `LOCAL_OPENAI` rather than the earlier
  fail-closed `FIXTURE` placeholder. A `FIXTURE` provider is gate-ineligible under section 8; this
  scope can now produce a gate-eligible result.

The endpoint is a loopback address with no userinfo and no credential query, and no timeout,
digest, or model value is machine-specific. The absolute path of the generation child is
deliberately *not* here: it is a per-run evaluate-request and gate input.

## Post-freeze history

These files did not reach their current bytes in a single freeze commit. The exact sequence is:

| Commit | What moved |
| --- | --- |
| `19c6bed0f9b5e7b85fe5e7068bc4578ab212f079` | settled the measurement edit format and retuned the gate corpus after the pilot run — task prompts, task manifests, corpus membership, and every digest that follows them |
| `52aefeb445afe9145eee60ec5f23bf43e5595070` | parameterized the frozen gate manifests and bound the generation-child evidence identity |
| `4d85ccb64aff853c4dd8fe25fcbb9033ffdab606` | replaced the fail-closed `FIXTURE` placeholder with the real `LOCAL_OPENAI` provider decision, rewriting `generation-policy.json`, `scope.json`, and `prompt-activation-baseline-v1.json` |
| `6da28d88327797649bbf229f14be9be1e6dd2d96` | repaired the shipped measurement adapter, which capped every sealed input at 2 MiB and so could never admit the derived generation child; the adapter is a corpus member, a declared task artifact, and each task's `measurement_adapter_runtime`, so only those digest bindings moved |
| `1d27b5f4c5ab3459e1b532859030c0e06df9a53a` | rebound the same three bindings again after the C6-MEASURED review repair changed both adapters' bytes; only each task's two adapter expectations, its `measurement_adapter_runtime`, the `FILE_SET` manifest, `corpus.json`, `scope.json`, and the baseline envelope moved |

`1d27b5f` is the last commit that touched these files, and the checked-in C6g2 measurement was
produced against `c737adcf905cb4662472bc86e8345bbcd9bc1346`, which contains it.
`git diff 1d27b5f HEAD -- eval/prompt/canonical-v1 eval/tasks/prompt-v1` is empty: nothing under the
frozen scope set or the gate corpus was mutated after measuring against it. A rebind is always a
separate commit whose measurement is then re-run against the rebound bytes; the section 11.3 rule is
that C6g2 must not mutate the frozen set *after* measuring, not that the set was never rebound
before a measurement.

Rewriting the provider decision rewrites `generation-policy.json`, and therefore `scope.json` and
`prompt-activation-baseline-v1.json`. Replacing the measurement adapter additionally rewrites every
task manifest, `corpus-file-set.manifest`, and `corpus.json`. Regenerate the affected files together
and re-review; do not repair one digest in isolation.

The measurement-adapter binding is closed: every task now binds the provider-backed
`scripts/prompt-measurement-adapter.py` through `cmd`/`argv` and `measurement_adapter_runtime`, and
declares its validation runner, task definition, and validation argv as parameterized inputs.

`prompt-activation-baseline-v1.json` is the repository's canonical human-owned baseline envelope. It
is not the C6d fixture envelope under `eval/fixtures/`. With the provider binding above closed, it
is the parent activation of the C6g2 measured gate chain.
