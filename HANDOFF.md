# Session handoff

A living continuity note for resuming align-llm on another machine or in a fresh Claude Code or
Codex session. Read `CLAUDE.md` first, then this file, then the relevant specifications named below.
Conversation history and per-machine memory are not project state.

_Last updated: 2026-07-25. Active work is the C3 patch-evaluator slice on
`c3-patch-evaluator` at implementation commit `3581c79`; the working tree has the intentional
handoff update below._

## Current position

The repository has completed C0, C1, and the first C2 index slice and is continuing C2:

- C0 now has both the evaluator smoke corpus and `coding-v1`, a real off-by-one repair task.
  The coding runner creates the exact pinned Git revision, proves the pre-repair failure, applies a
  separately supplied candidate, enforces allowed edits before and after validation, runs validation
  in a bubblewrap namespace with only its temporary checkout worktree writable and its `.git`
  metadata read-only, retains timeout diagnostics, kills its owned descendant process tree, and
  cleans its temporary checkout. It probes the required bubblewrap namespaces and fails closed when
  Linux child-subreaper support, bubblewrap, or the validation resource wrapper is unavailable;
  validation also has bounded address space, aggregate resident memory, CPU time, file size, process
  count, open files, bounded `/tmp` and `/dev/shm` tmpfs mounts, and writable-worktree
  size/file-count limits. Task-controlled IDs cannot influence temporary paths. Deleted-but-open
  files,
  adopted descendants, directory modes, and bounded resource scans are checked. Post-validation host
  Git checks cannot be configured by the candidate. Fixture and baseline Git subprocesses disable
  both system configuration and system attributes, global attributes are disabled with a fixed
  XDG configuration path, replacement objects are ignored, and NUL-delimited Git paths preserve
  whitespace and newlines. Post-repair validation mutations to even allowlisted files or the Git
  index are rejected by comparing the candidate state before and after validation. Fixture
  symlinks are preserved during materialization, and the immutable baseline oracle binds the
  source commit and artifact manifest as well as measured results.
- `eval/baselines/coding-v1-reference.json` is the first canonical machine-readable baseline. It was
  recorded twice from clean commit `f062daf` after rebuilding `main` with the verified pinned Align
  compiler. It binds the complete declared evaluation artifact set to both SHA-256 digests and the
  source commit, including the verifier itself, while enumerating source inputs explicitly so new
  unrelated modules do not invalidate C0. It records the requested and resolved Python runtime used
  for measurement and is checked against immutable oracle commit `42e6082`. This deterministic
  reference validates scoring and timing, not model quality.
- The refreshed baseline passed 2/2 attempts at 250,806,078 ns and 253,289,429 ns, with median time
  to a passing patch of 252,047,753 ns on the recorded WSL2/AMD Ryzen 9 5950X environment.
- A verify/repair control-loop spike exists in `src/repair.align`, backed by captured and
  timeout-bounded process execution in `src/verify.align`. C1 added the provider abstraction,
  three provider adapters, token-count metadata, and a common persisted result format; PR #4 is
  merged at `b7068e6`.
- `src/main.align` exposes `--eval`, `--loop`, and `--selfcheck` demonstrations for these slices.
- `.align-revision`, `make ci`, `.github/workflows/ci.yml`, the pull request template, and
  `docs/review-checklist.md` now make the local check, pinned compiler, fixed evaluation, review, and
  merge expectations executable across environments.
- `CLAUDE.md` and `docs/align-requests.md` define the Align request lifecycle, mandatory blocking
  metadata, dependent-slice pause rule, independent-work rule, and real-client resume/closure gate.
- Requests 1 and 3 have real-client closure evidence; Request 2 is shipped at `ALIGN_MERGED`.
  Request 4 is a new proposed blocker only for real chunked SSE acceptance; non-streaming C1 work
  remains independent.
- PR #5 merged the first C2 repository-index slice at `d59c5ce`. Git tracked files are read with
  `ls-files -z`; all tracked files receive language, line-count, readability, and test-path
  metadata; `.align` files receive top-level module, type, function, and import records.
- PR #6 merged the lexical-reference slice at `348c3a5`. It strips comments, strings, and escaped
  delimiters before recording imported qualified names and local calls in the `references` array.
- Current C2 state: `src/repo_index.align` now adds schema-v3 resolution status and targets.
  Same-file functions resolve locally; tracked user-module public functions/types resolve through
  the importing file's directory; core/std references are external; private, missing, and module
  declaration-mismatch targets remain unresolved. The focused fixture covers all four outcomes,
  newline-containing paths, revision binding, and persisted non-repository failure metadata.
- PR #7 merged the semantic-resolution slice at merge commit
  `91ec8455f9316a3c702cfbe17f609e376a43cc70`.
- The related-test selection slice is implemented at `2bb706d` on `c2-related-tests`. It writes
  a schema-version-1, revision-bound document for a changed path, recognizes tracked test paths,
  ranks basename matches at 100 points, adds 20 points for a shared directory, and preserves Git
  order for ties. The focused fixture covers ranking reasons, ordering, revision binding, and
  persisted non-repository failure metadata.
- PR #8 merged the related-test selection slice at merge commit `4cb217b7f901019e689bba36c88a41322d2cf51e`.
- The C3 patch-evaluator slice is implemented at `3581c79` on `c3-patch-evaluator`. It parses
  standard unified-diff file markers without applying the patch, records touched files and hunk
  symbols, computes additions/deletions, complexity delta, public API and conservative unrelated
  path flags, calculates a deterministic risk score, and reuses C2 to recommend tests. Its branch
  needs push, PR, review, and merge.

The central metric remains time to a passing patch. Do not start align-runtime work before the
fixed evaluation and provider-independent coding-loop gates establish a measurable baseline.

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

## Latest verification

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

The full `make ci` gate was not rerun; repeated CI is intentionally out of scope for this feature
implementation.

## Next steps

1. Push `3581c79` on `c3-patch-evaluator`, open a PR, and review the changed surface once.
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
