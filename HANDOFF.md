# Session handoff

A living continuity note for resuming align-llm on another machine or in a fresh Claude Code or
Codex session. Read `CLAUDE.md` first, then this file, then the relevant specifications named below.
Conversation history and per-machine memory are not project state.

_Last updated: 2026-07-28. Repository-governance work is active on
`agent/autonomous-execution-policy`, policy commit `d919cec`, based on merged main commit
`5311bac`. The current checkpoint includes this handoff update and expects a clean worktree. It
adopts design-before-implementation, long-running progress, and autonomous PR convergence rules
from the sibling Align repository before C6 design begins._

## Current position

The repository has completed C0 through C5. The current enabling slice updates the shared agent
policy only; no C6 product implementation has started.

- PR #9 (C3) merged at `5f883f8`; PR #10 (hosted Actions capability fix) merged at `a95c530`.
- PR #11 (C4) merged at `17da92c`. C4 adds `src/verification_loop.align` and
  `--verify-loop <task.json> <result.json>`, with candidate evaluation/application, bounded
  build/targeted/full verification, captured diagnostics, repair prompts, and one deterministic
  repair patch.
- C5 commit `05dbf75` adds `src/failure_memory.align`, optional `memory_profile` task input, append-only
  JSONL events, and matching-event injection into repair prompts. Profile failures are non-blocking
  after the result file is written.
- `scripts/run-verification-loop-smoke` now proves persistence, same-task reuse, and the existing
  invalid-repair `REPAIR_FAILED` path. `failure-memory-smoke` is the named C5 make target.
- Hosted Actions ran the supported C5 smoke successfully; no new external retry loop is
  warranted. The unavailable nested user-namespace `coding-v1` sandbox and stale C0 baseline check
  remain local/capable-runner gates only.

## Next steps

1. Commit this handoff checkpoint, verify the final base diff, push the branch, and open the
   autonomous-execution repository-governance PR with the preflight findings and checks recorded.
2. Review the final pushed PR diff independently, resolve valid findings, rerun affected checks,
   wait for required GitHub checks, and merge.
3. Refresh `main`, create a fresh C6 design branch, write the C6 public contract and acceptance
   matrix, and merge it only after independent design review.
4. Implement C6 in the smallest reviewed vertical slices. Do not rerun an unchanged full CI or
   external-service request after a documented capacity failure.

Do not rerun a failing external service request indefinitely. The Codex “high demand” message is a
service-capacity condition, not a repository or Actions failure. The central metric remains time to
a passing patch.

## Current governance verification

Verified on 2026-07-28:

```text
git diff --check                 PASS
independent adversarial review  6 findings; all addressed
fresh adversarial re-review     2 findings; all addressed; final clean recheck pending
```

## Completed bootstrap

PR #1, `Bootstrap the measured align-coder development cycle`, merged these intentionally
integrated bootstrap surfaces:

- `AGENTS.md` — Codex compatibility symlink to the canonical `CLAUDE.md`.
- `CLAUDE.md` — shared repository policy, English collaboration rules, mandatory
  PR-review-before-merge workflow, and handoff operation.
- `docs/align-requests.md` — Align responses and align-llm verification for the three shipped
  requests.
- `.align-revision`, `.github/`, `Makefile`, `scripts/`, and `docs/review-checklist.md` — pinned
  compiler, unified local/CI gate, pull request workflow, and shared review checks.
- `eval/tasks/`, `eval/expected/`, and `eval/runners/` — file-backed smoke corpus, deterministic
  score oracle, and runner.
- `src/main.align` — command entry points for the current demonstrations.
- `src/verify.align` — captured, timeout-bounded verification primitives.
- `src/eval.align` — declared JSON corpus loader and first deterministic C0 scorecard slice.
- `src/repair.align` — first provider-independent verify/repair loop skeleton.

The first executable evaluation, loop, CI, request lifecycle, and handoff rules were reviewed as one
bootstrap PR under the one-time exception in `CLAUDE.md`. That exception is now consumed: future
work returns to one roadmap gate or enabling slice per branch and PR. Review follow-ups resolved
diagnostic loss, loop bounds and exit coverage, task-identity checks, empty-corpus acceptance, the
effective compiler pin, request lifecycle evidence, and stale handoff state.

## C4 verification

Verified on 2026-07-25 against the current sibling Align checkout:

```text
make fmt                         PASS
make format-check                PASS
make check                       PASS — 14 imported units, including verification_loop
make build                       PASS
bash -n scripts/run-verification-loop-smoke  PASS
make index-smoke                 PASS
make test-selection-smoke        PASS
make patch-eval-smoke            PASS
make provider-smoke              PASS
make verify-loop-smoke           PASS — initial targeted failure repaired to full PASS in 2 iterations; invalid repair persisted as REPAIR_FAILED
git diff --check                 PASS
```

The full `make ci` gate was not rerun for C4. The supported hosted workflow was updated to include
the C4 smoke; no repeated retry is warranted for external service-capacity errors.

## C5 verification

Verified on 2026-07-25 against the current sibling Align checkout:

```text
make fmt                         PASS
make format-check                PASS
make check                       PASS — 15 imported units, including failure_memory
make build                       PASS
bash -n scripts/run-verification-loop-smoke  PASS
make index-smoke                 PASS — C2 regression
make test-selection-smoke        PASS — C2 regression
make patch-eval-smoke            PASS — C3 regression
make provider-smoke              PASS — C1 regression
make failure-memory-smoke        PASS — profile persistence, same-task prompt reuse, legacy task compatibility, and REPAIR_FAILED
git diff --check                 PASS
```

The full `make ci` gate was not rerun for C5. Hosted Actions already exercises the supported
verification-loop smoke; repeated external service-capacity retries remain out of scope.

## Historical verification

Verified on 2026-07-25 with pinned Align commit
`db942d2f705546c7d6b8c0334a462548c6446f84`:

```text
make fmt
# PASS — all Align source formatted; the previous dash-incompatible `read -d` recipe was fixed

make ci (using a clean detached checkout of the pinned Align revision)
# PASS — pinned Align revision matches
# PASS — pinned Align compiler and runtime release build is current
# PASS — formatter output matches every Align source file
# PASS — 5 units checked per-unit: project, verify, eval, repair, main
# PASS — executable built as ./main
# PASS — smoke-v1: 2 tasks, 2 PASS, 0 failed; identity and summary oracles match
# PASS — an empty corpus is rejected
# PASS — coding-v1: pinned fixture repair 1/1 PASS; disallowed edits and validation side effects
# rejected, including index-flag-, stat-cache-hidden-, special-mode, and directory-mode mutations;
# ignored fixture inputs and validation side effects rejected; ambient Git and Python settings and
# corpus interpreter dispatch isolated; system and global Git configuration and attributes disabled;
# timeout
# and normal-completion process-tree cleanup,
# descendant reaping, and temporary checkout cleanup verified; missing child-subreaper, bubblewrap
# namespace, or resource wrapper support fails closed; validation cannot mutate the host filesystem or
# Git metadata; Git replacement objects are ignored; pre-validation byte/mode and untracked/ignored
# mutations are rejected; validation `/tmp` and `/dev/shm` tmpfs, process/file/address-space,
# aggregate RSS, deleted-open-FD,
# adopted-descendant, aggregate file-count, and writable-worktree quotas are enforced with bounded
# scans; NUL-delimited Git path handling and whitespace-path regression isolated; symlink fixture
# preservation and post-validation allowlisted-file mutation rejected; non-UTF-8
# diagnostics retained and bounded before buffering; non-passing baseline stdout and stderr
# diagnostics are persisted; concurrent baseline replacement-ref smoke runs are isolated
# PASS — canonical baseline metadata, source commit, artifact digests, immutable oracle, task identity, summaries,
# corpus task order and expected codes, and strictly typed numeric aggregates verified; malformed
# aggregates and verdicts rejected; measured Python runtime, pin checker provenance, and complete
# non-passing results retained
# PASS — loop spike: pass, give-up, stdout-driven repair/reverify, exhaustion, timeout, and
# zero-budget paths match their oracle

for file in eval/runners/run-fixed.sh scripts/check-* scripts/run-eval-invalid-smoke \
  scripts/run-loop-smoke scripts/run-baseline-invalid-smoke scripts/run-coding-task-*; do
  bash -n "$file"
done
# PASS

python3 -m json.tool <each task, manifest, expected summary, and canonical baseline>
# PASS

git diff --check
# PASS
```

## C1 verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 11 imported units, provider modules included
make build                       PASS — executable built as ./main
bash -n scripts/run-provider-smoke  PASS
./scripts/run-provider-smoke     PASS — provider adapters, env-backed auth, Cloud HTTP rejection, SSE error and DONE-only rejection, timeout, HTTP status 429, exact assembled Llama prompt count, common result format v2
git diff --check                 PASS
```

`make ci` has intentionally not been rerun for this feature slice; the focused provider gate is the
relevant verification, and CI repetition is not useful while the Align chunked-response capability
remains unshipped. The focused smoke uses a temporary HTTP fixture; real Cloud OpenAI calls require
HTTPS and read the key from an environment variable name supplied to the CLI.

## C2 verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 12 imported units, including repo_index
make build                       PASS — executable built as ./main
bash -n scripts/run-index-smoke  PASS
make index-smoke                 PASS — tracked files, NUL-safe path, declarations/imports/tests, revision binding, failure persistence
make provider-smoke              PASS — C1 provider regression smoke
git diff --check                 PASS
```

The full `make ci` gate was not rerun; CI repetition is intentionally out of scope for this
feature implementation.

## C2 lexical-reference verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 12 imported units, including repo_index
make build                       PASS — executable built as ./main
bash -n scripts/run-index-smoke  PASS
make index-smoke                 PASS — qualified/local references, escaped string and comment exclusion, prior C2 coverage
make provider-smoke              PASS — C1 provider regression
git diff --check                 PASS
```

The independent adversarial reviewer did not return within one bounded wait and was shut down;
manual review of the changed surface found no blocking functional finding. The full `make ci` gate
was not rerun.

## C2 semantic-resolution verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 12 imported units, including repo_index
make build                       PASS — executable built as ./main
bash -n scripts/run-index-smoke  PASS
make index-smoke                 PASS — public/local resolution, external and unresolved targets, module declaration check, prior C2 coverage
make provider-smoke              PASS — C1 provider regression
git diff --check                 PASS
```

The independent review CLI completed one bounded run; its verbose internal output was truncated by
the runner, so the changed surface was also manually reviewed against the checklist and pinned
Align module rules. No blocking functional finding remains. The full `make ci` gate was not rerun.

## C2 related-test selection verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 12 imported units, including repo_index
make build                       PASS — executable built as ./main
bash -n scripts/run-index-smoke scripts/run-test-selection-smoke  PASS
make test-selection-smoke        PASS — deterministic basename/directory ranking, stable order, revision binding, failure persistence
make index-smoke                 PASS — prior C2 index and semantic-resolution coverage
make provider-smoke              PASS — C1 provider regression
git diff --check                 PASS
```

The full `make ci` gate was not rerun; repeated CI is intentionally out of scope for this feature
implementation.

## C3 patch-evaluator verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 13 imported units, including patch_eval
make build                       PASS — executable built as ./main
bash -n scripts/run-patch-eval-smoke  PASS
make patch-eval-smoke            PASS — diff shape, hunk-context symbols, risk/public-API/unrelated signals, recommended tests, failure persistence
make test-selection-smoke         PASS — C2 related-test regression
make index-smoke                 PASS — C2 index and semantic-resolution regression
make provider-smoke               PASS — C1 provider regression
git diff --check                 PASS
```

The follow-up `053357e` also classifies changed hunk lines that begin with `+++` or `---` as data
after the hunk marker, preserving valid unified-diff content. The full `make ci` gate was not
rerun; repeated CI is intentionally out of scope for this feature implementation.

## Superseded C3 handoff

1. Push `3581c79` and `053357e` on `c3-patch-evaluator`, update PR #9, and review the changed
   surface once.
2. Apply only valid findings, rerun the focused patch-evaluator and C2 verification, and merge with
   a merge commit. Do not repeat the full CI gate or wait on a non-returning reviewer.
3. After merge, continue with C4 Verification Loop. Keep Request 4 limited to real chunked SSE
   acceptance; it does not block the evaluator or verification work.

## Constraints to preserve

- Use `make check`, `make run`, `make fmt`, and `make build`; do not invent an Align manifest or
  package workflow.
- `make ci` requires a clean sibling checkout at `.align-revision`, builds its release compiler,
  and forces all project gates to use that exact executable. Change the pin deliberately and rerun
  the full gate when adopting a newer Align compiler.
- Canonical baseline recording also rebuilds the pinned compiler and `main`; never measure an
  existing ignored binary. Task wrappers must declare all executable inputs in `artifact_paths`.
- PR #3 must use a merge commit rather than squash so the recorded source commit remains reachable.
- A captured process's stdout and stderr are region-bound views. Clone them before returning owned
  diagnostics, as `src/verify.align` does.
- A Move struct with owned `string` fields cannot currently be a `Result` Ok payload. The current
  `Captured` value therefore stores its run outcome as data and returns as a bare Move struct.
- Bind an owned `string` to an explicit `str` view before passing it through an indirect function
  value.
- Reusable command arguments cross loop iterations as `slice<str>` and are materialized for
  `std.process` per run.
- Provider SSE parsing currently depends on Content-Length framing because Align's shipped
  `std.http` client rejects chunked response bodies; do not add a raw-socket compatibility layer.
- C1 is merged at `b7068e6`; the first C2 index slice is merged at `d59c5ce`; the lexical-reference
  slice is merged at `348c3a5`; semantic resolution is merged at `91ec8455f9316a3c702cfbe17f609e376a43cc70`;
  related-test selection is merged at `4cb217b7f901019e689bba36c88a41322d2cf51e`; the current
  patch evaluator is committed at `3581c79`.
- C2 uses Git's tracked-file list (`git ls-files -z`) rather than recursively probing filesystem
  entries; do not replace it with a directory walk that loses repository boundaries or newline
  safety.
- C2 currently parses top-level Align declarations/imports and lexical references, then resolves
  same-file functions and tracked user-module public function/type targets using the importing
  file's directory as the index base. Related-test selection is path-based and deterministic; it
  does not yet use the resolved symbol/reference graph.
- C3 currently parses standard unified-diff markers read-only. It uses hunk context for a bounded
  symbol signal, conservative path heuristics for unrelated diff, and a documented line-signal
  risk score. Do not claim full language-aware diff analysis or patch application until later
  slices ship.
- Source, comments, diagnostics, commits, pull requests, reviews, and releases are written in
  English.

## Read next

- `docs/specs/roadmap.md` — delivery order and gates.
- `docs/specs/align-llm.md` — architecture and system principles.
- `docs/align-requests.md` — shipped Align capability details and ownership limits.
- `docs/align-development.md` — local sibling-compiler workflow.
