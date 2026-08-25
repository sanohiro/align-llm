# Developing align-llm with Align

Align is developed in parallel with this project. There is no Align project manifest, package registry, general test runner, or configurable source search path yet. A program starts from one `.align` entry file, and imports resolve to files beneath that entry file's directory.

## Managed local toolchain

Ordinary align-llm development does not use an ambient sibling Align checkout. `.align-revision`
contains the exact compiler source commit. The wrapper materializes that commit outside Git at:

```text
${XDG_CACHE_HOME:-$HOME/.cache}/align-llm/align/dev-v1/<full-commit-sha>/
  target/release/alignc
  target/release/libalign_runtime.a
```

`scripts/alignc` selects a compiler in this order:

1. The authenticated `/tools/fresh-alignc` when the fresh profile requires it.
2. The executable named explicitly by `ALIGNC`.
3. The release, then debug compiler under an explicitly supplied `ALIGN_REPO`.
4. The managed release compiler for `.align-revision`.

There is no implicit `../align` or `PATH` fallback. `make check`, `run`, `build`, `fmt`, and their
recursive smoke targets therefore use the same pin after one file changes. The first command fetches
and release-builds the pin; later commands validate and reuse the checkout. Prepare it directly
with:

```sh
scripts/align-toolchain ensure compiler
```

`ALIGN_TOOLCHAIN_ROOT` changes the absolute cache base. `ALIGN_TOOLCHAIN_REPOSITORY` changes the
source remote, and `CARGO` changes the build command. This is trusted, mutable, single-user
development state: the first build intentionally uses the developer's ordinary Cargo/Rust
environment, it is not a reproducible artifact or hostile-process boundary, and changing those
inputs requires removing that revision directory before rebuilding. Generation `dev-v1` keeps the
checkout separate from earlier cache contracts. Active cross-repository development remains explicit:

```sh
make check ALIGNC=../align/target/release/alignc
make check ALIGN_REPO=../align
```

These overrides deliberately bypass the managed default. Use them only when testing Align work that
has not yet become the repository pin.

## What to read

Use the Align repository as the source of truth. When coordinating live Align changes, the sibling
checkout remains the convenient documentation and implementation workspace:

- Start with `../align/CLAUDE.md` for current implementation status and invariants.
- Read `../align/draft.md` for the authoritative language design.
- Read `../align/docs/guide/` for supported day-to-day syntax and APIs.
- Search `../align/examples/` and compiler tests for compiling examples.
- Check `../align/docs/open-questions.md` before depending on unsettled behavior.
- For HTTP work, read `../align/docs/impl/15-pkg-web-plan.md`, `../align/docs/impl/pkg-design/web.md`, and `../align/apps/web/pkg/`.

Do not copy the in-progress web package into this repository merely to make imports resolve. Until Align gains a package mechanism, either keep an application independent of it or coordinate an explicit vendoring decision with version and update rules.

## Supported development loop

```sh
make check
make fmt
make run
```

`check-per-unit` validates imported modules through their public interfaces. The formatter rewrites only meaningless syntax variation and should run before a commit. Use `emit-mir`, `emit-llvm`, `explain-opt`, and `size` directly through the wrapper when validating performance claims:

```sh
./scripts/alignc emit-mir src/main.align
./scripts/alignc explain-opt src/main.align --verbose
./scripts/alignc size src/main.align --profile tiny
```

Before publishing an executable branch, run the shared local preflight with the narrow owner
command. A Markdown additions/modifications branch omits the owner arguments only when `--plan`
classifies it as `docs`:

```sh
python3 scripts/pre-pr --owner-test provider-smoke -- make provider-smoke
python3 scripts/pre-pr
```

Markdown deletions and renames fail closed to executable preflight and therefore require an
applicable owner command; the classifier remains authoritative when path shape is ambiguous.

`scripts/pre-pr` computes the merge base with `origin/main`, classifies the exact diff, runs the
owner before its required aggregate, and records a local exact-HEAD stamp only after every selected
gate passes. With no `--align-repo`, the printed plan runs the owner first, then ensures and uses the
same managed full-history source as the wrapper. Use `--plan` to inspect every phase and predicted path without fetching, building,
running commands, or writing the stamp. An explicit `--align-repo` remains available for a named
exact checkout. Fresh-image ownership additionally runs the focused qualification and the installed
profile once each; the installed invocation removes ambient `DOCKER_HOST` and requires a reachable
Docker daemon. The disposable profile clones the selected source without hardlinks and never reads
another active checkout's worktree files.
The classifier and path inventory are shared with GitHub Actions, so local and hosted scope cannot
drift independently. See `docs/specs/development-preflight.md` for the exact commands and failure
behavior.

After a pull request merges, the `main` push jobs reuse its successful CI evidence only when the
merge commit has the exact tested head tree, the tested base as both first parent and parent merge
base, one matching merged pull request, and one matching successful `ci.yml` run containing both
required jobs. Direct pushes, squash/rebase or conflict-resolution merges, failed or stale runs,
and unavailable GitHub evidence run the normal classifier-selected gates. This removes the second
fresh-image execution after an exact merge without weakening direct-push coverage.

Run `make ci` for the complete capable-host gate. It uses the exact managed pinned Align release compiler,
then runs the bounded hosted functional graph, the sandboxed coding corpus, and canonical baseline
verification in a deterministic order. It is complete for that declared graph, not for every
focused qualification script in the repository. Run `make hosted-checks` only on hosts that cannot
provide the coding corpus's nested user namespace; it intentionally omits `eval-coding` and
`baseline-check`. A focused target is diagnostic evidence for that surface, not evidence that
either aggregate completed.

Resource-limit, race, security, fuzz, stress, platform, mutation, and benchmark qualification run
through their named owner commands when the owning boundary changes or an explicit audit requires
them. For example, coding-task resource-monitor qualification is:

```sh
python3 scripts/run-coding-task-resource-scan-smoke
```

It is intentionally not a transitive child of `make eval-coding`.

## Managing language dependencies

When the engine needs a feature that does not compile in the current Align checkout:

1. Confirm the feature is part of the settled language design.
2. Reduce the need to the smallest compiler or standard-library capability.
3. Register it in `docs/align-requests.md` with the lifecycle and blocking metadata required by
   `CLAUDE.md`.
4. If it is blocking, pause only the dependent consumer capability and record the resume condition
   in `HANDOFF.md`. Continue valid independent work without assuming the proposed surface.
5. Implement and test that capability in `../align` as a separate, reviewable change.
6. Update this repository only after the Align change is available at a named commit or release.
7. Batch merged prerequisites needed by the next consumer when practical. Update `.align-revision`
   once, materialize its managed release compiler, run every original request acceptance target and
   one final `make ci`, and record the real-client verification before closing each request.

This separation keeps engine work reproducible and prevents application code from becoming an accidental language specification.

## Provider development

The C1 provider surface lives in `src/model.align` and `src/provider.align`. `model.ProviderConfig`
holds the explicit provider kind, endpoint, model, API key, timeout, and optional llama.cpp
tokenizer endpoint. `provider.generate`, `provider.stream`, `provider.count_tokens`, and
`provider.model_info` dispatch only through the declared `ProviderKind` enum.

The OpenAI adapters send `/v1/chat/completions`; the llama.cpp adapter sends `/completion` and can
use `/tokenize` for exact counts. OpenAI-compatible token counts are deliberately marked as
estimated. Cloud OpenAI requires an `https://` endpoint and reads its bearer key from `std.env`.
Successful and failed calls are persisted through `result.GenerationRecord`, whose
`schema_version` is `2`, whose `error_code` preserves an HTTP status when available, and whose
shape is independent of the adapter.

Use `make provider-smoke` for the focused fixture. It starts a temporary HTTP server, exercises
local OpenAI-compatible and llama.cpp generate/stream calls, checks environment-backed Bearer
authentication, Cloud HTTP rejection, SSE failure handling, exact tokenizer counts, HTTP status
diagnostics, and the shared result records. Real Cloud OpenAI calls require HTTPS.

## Repository-index development

The current C2 slice is `src/repo_index.align`. It asks Git for the tracked file list with
`ls-files -z`, so repository boundaries and filenames containing newlines remain explicit. For
tracked files it records language classification, line count, readability, and test-path
candidates. `.align` files additionally contribute top-level module, type, function, and import
records, plus lexical references to imported qualified names and local calls. Each reference keeps
the source qualifier, member name, kind, resolution status, target path, target name, and line.
Tracked user-module public symbols and same-file functions resolve to targets; core/std references
are marked external, while private or missing targets remain unresolved. Because the index CLI
receives a repository root rather than one compiler entry file, user-module resolution uses the
importing file's directory as its conservative base. The result is a schema-version-3,
revision-bound JSON document written by:

```sh
./main --index <repo> <index.json> [timeout-ns]
```

Use `make index-smoke` for the focused fixture. It checks declaration/import/reference extraction,
user-module public resolution, local resolution, external and unresolved statuses, a
newline-containing tracked path, string/comment exclusion, test-candidate selection, revision
binding, and persisted failure metadata for a non-repository path.

### Related-test selection

The related-test selector uses the same revision-bound Git `ls-files -z` boundary as the index. It
accepts one changed path and writes a schema-version-1 selection document:

```sh
./main --select-tests <repo> <changed-path> <tests.json> [timeout-ns]
```

Tracked paths recognized as tests are ranked by a deterministic path heuristic. A basename/stem
match contributes 100 points, a shared directory contributes 20 points, and candidates with
neither signal remain at score 0. The JSON includes the score and reason for every candidate;
equal scores retain Git listing order. The selector is intentionally path-based and does not yet
use the resolved symbol/reference graph, so symbol-specific ranking remains a later C2 slice.
Use `make test-selection-smoke` for the fixture covering ranking order, reasons, revision binding,
and persisted failure metadata.

## Patch-evaluator development

The first C3 slice is a read-only unified-diff evaluator. It does not apply the candidate or run a
build; those actions belong to C4. The CLI writes a schema-version-1 document:

```sh
./main --evaluate-patch <repo> <patch.diff> <evaluation.json> [timeout-ns]
```

The document records touched files and hunk-context symbols, additions/deletions, a simple
complexity delta (`if`, `match`, `loop`, `&&`, and `||` signals), public API-line changes, a
deterministic risk score, and the C2 recommended-test candidates for the first non-test file. The
risk score starts with changed lines, adds 20 for a public API change, 25 for a test/documentation/
metadata path flagged as unrelated, and five per positive complexity point. The `unrelated_diff`
flag is deliberately a conservative path heuristic until task-specific allowlists are connected.
The parser currently expects standard unified-diff file markers; patch application and richer
language-aware symbol resolution remain later slices. Use `make patch-eval-smoke` for shape,
symbol, risk, recommended-test, and failure-persistence coverage.

## Verification-loop development

The C4 slice is `src/verification_loop.align`. It turns the read-only C3 report into a bounded,
provider-independent verification loop. A task JSON document has this shape:

```json
{
  "schema_version": 1,
  "task_id": "task-name",
  "root": "/path/to/worktree",
  "candidate_patch": "/path/to/candidate.patch",
  "repair_patch": "/path/to/repair.patch",
  "memory_profile": "/path/to/repo.alignprof",
  "build": { "cmd": "...", "argv": ["..."], "expected_code": 0 },
  "targeted_test": { "cmd": "...", "argv": ["..."], "expected_code": 0 },
  "full_test": { "cmd": "...", "argv": ["..."], "expected_code": 0 },
  "timeout_ns": 10000000000,
  "max_iterations": 3
}
```

Set `repair_patch` to an empty string when the task should stop after the first failing stage.
`memory_profile` is optional. Set it to a repo-local `.alignprof` path to enable failure memory, or
omit it to preserve the C4 behavior without persistence.

Run it with:

```sh
./main --verify-loop <task.json> <result.json>
```

The loop evaluates the candidate through C3, checks and applies it with `git apply`, then runs
build, targeted-test, and full-test in order. A failed stage is captured with its exit code,
duration, summary, stdout, and stderr. The repair prompt includes that diagnostic and the C3
evaluation document. If a repair patch is configured and the iteration budget permits, it is
checked and applied once, then the next iteration verifies the repaired worktree. The result uses
`PASS`, `GAVE_UP`, `EXHAUSTED`, `REPAIR_FAILED`, or `INVALID` status labels and preserves all
attempts for later provider or failure-memory work.

## Failure-memory development

The C5 slice is `src/failure_memory.align`. When `memory_profile` is configured, each completed
verification appends one JSON object to the profile rather than rewriting a mutable array. The
event records the task and attempted patch, first failed stage/test, root-cause summary, repair
result, successful and unsuccessful strategies, recommended tests, risky symbols, iteration
counts, and risk score. The next run selects up to the three newest events for the same task and
adds them to every repair prompt. A missing or unreadable profile starts with empty context, and a
profile write/decode failure does not replace the already-written verification result.

The fixed smoke proves persistence and reuse by running the same task twice:

```sh
make failure-memory-smoke
```

The checked-in smoke fixture uses a deterministic repair patch to prove the gate without a model
server:

```sh
make verify-loop-smoke
```

The repair patch is deliberately an input boundary, not a model implementation. A future provider
can consume `repair_prompt` and return an equivalent patch without changing verification, timeout,
or result handling.

## Persisted-result development

The C7-PERSISTED-RESULT consumer is `src/persisted_result.align`, specified by
`docs/specs/c7-persisted-result.md`. It decodes one declared verification input into an owned
record, lets the input document and every borrowed view expire, publishes one canonical result
artifact with a content-bound digest, and verifies that artifact with an independent recomputation.

An input document is one canonical `C7_VERIFICATION_INPUT` record:

```json
{
  "schema_version": 1,
  "artifact_kind": "C7_VERIFICATION_INPUT",
  "case_id": "upper-equal",
  "algorithm": "bounded-bucket-v1",
  "left": 4,
  "right": 5,
  "lower_bound": 0,
  "upper_bound": 9,
  "expected": 2,
  "note": "optional, at most 256 bytes"
}
```

The wire is canonical: declaration order, no leading or trailing whitespace, no final newline, and
an omitted `note` for `None`. A decoded record is re-encoded and compared byte-for-byte with the
file, so unknown fields, reordered keys, whitespace, and a `null` optional spelling are all
rejected. Both paths must be nonempty, NUL-free, and at most 4,096 bytes, and the two path strings
must not be byte-identical.

Run the two commands with:

```sh
./main --persist-result <input.json> <result.json>
./main --verify-result <result.json>
```

Each prints the same seven-line summary block (`persisted-result:`, `status:`, `PASS` or `FAIL`,
`expected:`, the value, `observed:`, the value). `PASS` exits 0. A valid semantic `FAIL` is
persisted data: the artifact is written and reloaded and the summary is printed, and only then does
the CLI take its `Error.Invalid` exit. Malformed input, invalid artifact data, path validation, and
operating-system failures return an error with no summary block. Publication uses the whole-file
`std.fs.write_file` boundary, so a failed write may leave the caller-owned destination absent or
partial; nothing is removed or restored on that path.

The bounded functional smokes are focused targets and deliberately join no aggregate:

```sh
make c7-persisted-result-cli-smoke
make c7-persisted-result-lifetime-smoke
make c7-persisted-result-owned-move-smoke
make c7-persisted-result-wire-smoke
make c7-persisted-result-noncanonical-input-smoke
make c7-persisted-result-independent-destinations-smoke
```

Their fixture vectors live in `scripts/c7_persisted_result_fixtures.py`, an independent ordered
field table, escape grammar, and bucket reference. The generated differential corpus, the full
artifact-mutation corpus, and the intentionally mutated source case belong to the separate
`persisted-result-qualification` slice.
