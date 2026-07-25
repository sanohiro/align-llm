# Session handoff

A living continuity note for resuming align-llm on another machine or in a fresh Claude Code or
Codex session. Read `CLAUDE.md` first, then this file, then the relevant specifications named below.
Conversation history and per-machine memory are not project state.

_Last updated: 2026-07-25. Active work is PR #3 on `c0-real-task-baseline`, with canonical
baseline source commit `fae2e8e`, immutable oracle commit `3558f2e`, and refreshed result commit
`b2e502d`. Resume at the PR head until it is merge-committed; after that, no implementation is
active until the user asks to resume, with C1 as the next roadmap slice._

## Current position

The repository has completed the C0 implementation and is ready to begin C1 after PR #3 merges:

- C0 now has both the evaluator smoke corpus and `coding-v1`, a real off-by-one repair task.
  The coding runner creates the exact pinned Git revision, proves the pre-repair failure, applies a
  separately supplied candidate, enforces allowed edits before and after validation, runs validation
  in a bubblewrap namespace with only its temporary checkout worktree writable and its `.git`
  metadata read-only, retains timeout diagnostics, kills its owned descendant process tree, and
  cleans its temporary checkout. It probes the required bubblewrap namespaces and fails closed when
  Linux child-subreaper support, bubblewrap, or the validation resource wrapper is unavailable;
  validation also has bounded address space, CPU time, file size, process count, open files, tmpfs,
  and writable-worktree size/file-count limits. Post-validation host Git checks cannot be configured
  by the candidate.
- `eval/baselines/coding-v1-reference.json` is the first canonical machine-readable baseline. It was
  recorded twice from clean commit `fae2e8e` after rebuilding `main` with the verified pinned Align
  compiler. It binds the complete declared evaluation artifact set to both SHA-256 digests and the
  source commit, including the verifier itself, while enumerating source inputs explicitly so new
  unrelated modules do not invalidate C0. It records the requested and resolved Python runtime used
  for measurement and is checked against immutable oracle commit `3558f2e`. This deterministic
  reference validates scoring and timing, not model quality.
- The refreshed baseline passed 2/2 attempts at 238,306,613 ns and 244,407,813 ns, with median time
  to a passing patch of 241,357,213 ns on the recorded WSL2/AMD Ryzen 9 5950X environment.
- A verify/repair control-loop spike exists in `src/repair.align`, backed by captured and
  timeout-bounded process execution in `src/verify.align`. This is enabling work shaped like the
  later C4 Verification Loop, not completion of C1. C1's provider abstraction, multiple provider
  implementations, and common persisted result format are not implemented.
- `src/main.align` exposes `--eval`, `--loop`, and `--selfcheck` demonstrations for these slices.
- `.align-revision`, `make ci`, `.github/workflows/ci.yml`, the pull request template, and
  `docs/review-checklist.md` now make the local check, pinned compiler, fixed evaluation, review, and
  merge expectations executable across environments.
- `CLAUDE.md` and `docs/align-requests.md` define the Align request lifecycle, mandatory blocking
  metadata, dependent-slice pause rule, independent-work rule, and real-client resume/closure gate.
- All three capabilities requested from the sibling Align repository in
  `docs/align-requests.md` are shipped in Align v0.4.0. Requests 1 and 3 have real-client closure
  evidence. Request 2 remains non-blocking at `ALIGN_MERGED` until the C1 provider HTTP client
  supplies plaintext and TLS timeout fixtures. No open Align request currently blocks C1.

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

make ci
# PASS — pinned Align revision matches
# PASS — pinned Align compiler and runtime release build is current
# PASS — formatter output matches every Align source file
# PASS — 5 units checked per-unit: project, verify, eval, repair, main
# PASS — executable built as ./main
# PASS — smoke-v1: 2 tasks, 2 PASS, 0 failed; identity and summary oracles match
# PASS — an empty corpus is rejected
# PASS — coding-v1: pinned fixture repair 1/1 PASS; disallowed edits and validation side effects
# rejected, including index-flag-, stat-cache-hidden-, and special-mode mutations; ignored fixture
# inputs and validation side effects rejected; ambient Git and Python settings and corpus interpreter
# dispatch isolated; timeout and normal-completion process-tree cleanup, descendant reaping, and
# temporary checkout cleanup verified; missing child-subreaper, bubblewrap namespace, or resource
# wrapper support fails closed; validation cannot mutate the host filesystem or Git metadata; Git
# replacement objects are ignored; pre-validation byte/mode and untracked/ignored mutations are
# rejected; validation tmpfs, process/file/address-space limits, and writable-worktree quotas are
# enforced; non-UTF-8 diagnostics retained and bounded before buffering; non-passing baseline stdout
# and stderr diagnostics are persisted
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

## Next steps

1. Push the final C0 follow-up, repeat PR #3 review after the validation-containment and resource
   hardening changes, require GitHub CI to pass with full checkout history, and merge with a merge
   commit so the canonical baseline source commit remains reachable.
2. Stop after PR #3 is merge-committed. When work resumes, start one C1 branch for the explicit
   provider boundary and common persisted result format.

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
- Source, comments, diagnostics, commits, pull requests, reviews, and releases are written in
  English.

## Read next

- `docs/specs/roadmap.md` — delivery order and gates.
- `docs/specs/align-llm.md` — architecture and system principles.
- `docs/align-requests.md` — shipped Align capability details and ownership limits.
- `docs/align-development.md` — local sibling-compiler workflow.
