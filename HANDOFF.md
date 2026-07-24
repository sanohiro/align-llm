# Session handoff

A living continuity note for resuming align-llm on another machine or in a fresh Claude Code or
Codex session. Read `CLAUDE.md` first, then this file, then the relevant specifications named below.
Conversation history and per-machine memory are not project state.

_Last updated: 2026-07-25. Active work is PR #1 on
`agent/bootstrap-development-cycle`. The pushed review-fix series starts at `c9d47e5`; use
`git rev-parse HEAD` for its latest commit._

## Current position

The repository is at the first align-coder delivery gates:

- C0 has an initial file-backed deterministic evaluation slice. `eval/tasks/smoke-v1.json`
  manifests two task files, `src/eval.align` loads them through declared `core.json` records, and
  `eval/runners/run-fixed.sh` rejects non-passing verdicts or a summary that differs from the
  checked-in oracle. This proves the corpus and scoring mechanism, but the C0 gate is not complete:
  reproducible coding-task fixture setup, pinned target-repository revisions, canonical result
  storage, and a baseline over real repair tasks are still missing.
- A verify/repair control-loop spike exists in `src/repair.align`, backed by captured and
  timeout-bounded process execution in `src/verify.align`. This is enabling work shaped like the
  later C4 Verification Loop, not completion of C1. The roadmap's C1 provider abstraction, multiple
  provider implementations, and common persisted result format are not implemented.
- `src/main.align` exposes `--eval`, `--loop`, and `--selfcheck` demonstrations for these slices.
- `.align-revision`, `make ci`, `.github/workflows/ci.yml`, the pull request template, and
  `docs/review-checklist.md` now make the local check, pinned compiler, fixed evaluation, review, and
  merge expectations executable across environments.
- `CLAUDE.md` and `docs/align-requests.md` define the Align request lifecycle, mandatory blocking
  metadata, dependent-slice pause rule, independent-work rule, and real-client resume/closure gate.
- All three capabilities requested from the sibling Align repository in
  `docs/align-requests.md` are shipped in Align v0.4.0. Requests 1 and 3 have real-client closure
  evidence. Request 2 remains non-blocking at `ALIGN_MERGED` until the provider HTTP client supplies
  plaintext and TLS timeout fixtures. No open Align request currently blocks C0 or the
  provider-independent loop.

The central metric remains time to a passing patch. Do not start align-runtime work before the
fixed evaluation and provider-independent coding-loop gates establish a measurable baseline.

## Active pull request

PR #1, `Bootstrap the measured align-coder development cycle`, contains the following intentionally
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

The subjects remain separate commits for review, but the first executable evaluation, loop, CI,
request lifecycle, and handoff rules cross-reference one another and are being reviewed as one
bootstrap PR under the one-time exception in `CLAUDE.md`. This is not a precedent for mixing
independently reviewable governance, request, and roadmap work after the foundation merges. Review
found and the follow-up addresses diagnostic loss, loop bounds and exit coverage, task-identity
checks, the effective compiler pin, request lifecycle evidence, and stale handoff state.

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
# PASS — loop spike: pass, give-up, stdout-driven repair/reverify, exhaustion, timeout, and
# zero-budget paths match their oracle

bash -n eval/runners/run-fixed.sh scripts/run-loop-smoke scripts/check-align-revision
# PASS

python3 -m json.tool <each smoke-v1 task, manifest, and expected summary>
# PASS
```

## Next steps

1. Finish the final PR #1 follow-up review, rerun the local and GitHub gates, and merge only with no
   valid finding open.
2. Finish the C0 gate with at least one real coding-task fixture. Pin its source revision, make setup
   and cleanup reproducible, define allowed edits and validation, and retain a canonical
   machine-readable result from a clean align-llm commit.
3. Record the first baseline with the metadata required by `eval/baselines/README.md`, then repeat it
   to prove stable scoring before accepting any provider or prompt optimization.
4. After the C0 gate is measured, implement C1's explicit provider boundary and common persisted
   result format. Preserve the current verify/repair loop as a C4-oriented spike until C1 provides a
   real provider to drive it.
5. Before merging code, follow `CLAUDE.md` exactly: open the PR, run review with high effort for
   non-trivial changes, scrutinize and reflect findings, push the follow-up, re-verify, then merge.

## Constraints to preserve

- Use `make check`, `make run`, `make fmt`, and `make build`; do not invent an Align manifest or
  package workflow.
- `make ci` requires a clean sibling checkout at `.align-revision`, builds its release compiler,
  and forces all project gates to use that exact executable. Change the pin deliberately and rerun
  the full gate when adopting a newer Align compiler.
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
