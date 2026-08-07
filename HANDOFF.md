# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-adoption-contract-v2`, with design content complete at
  `1f14729784229dfa2fc08f8ecafd1c1ac48cb4f2`, based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`. This handoff-only metadata update follows that
  design commit; no design content follows it.
- Active goal: finish and merge the corrected Request 6 focused-adoption design, then implement
  the ordinary launcher, focused target and fixtures, shipped Align pin, fresh adoption vector,
  baseline ancestry, and final fresh `make ci` on a new branch. Request 7 and later consumers stay
  blocked on this gate.
- The latest design repair adds the private no-prerequisite `align-build-only` vector while
  preserving the developer-facing `align-build: align-revision` contract, and assigns Make-child
  lifecycle ownership to the in-namespace supervisor. A fresh independent review is required.
- PR #62 is superseded and must not be merged. The replacement design PR must include the corrected
  vectors and current handoff state.
- Expected post-merge checkpoint: refresh `main` safely, perform the bounded design retrospective,
  and create `agent/request6-adoption-implementation` from the merged design. The implementation
  branch must not reuse PR #62's direct ordinary Make command.

## Next steps, in priority order

1. Run one fresh independent adversarial review of `1f14729`, then update the design PR with its
   SHA-bound review envelope and merge it only after checks and all findings are resolved.
2. Close PR #62 as superseded, publish the replacement design PR, and complete its review/fix/merge
   evidence.
3. Refresh `main`, record the bounded retrospective, and implement Request 6 on a new branch;
   review, repair, merge, refresh `main`, and continue to the next eligible roadmap gate.

## Latest verification

- `make gate-topology-check`: PASS at `1f14729`.
- `git diff --check`: PASS at `1f14729`.
- Markdown fence parity: PASS (`docs/align-requests.md` 94, `docs/specs/check-gate-topology.md` 76).
- The design-only gate does not run source tests, `make check`, `make build`, or `make ci`; those
  checks are deferred until executable implementation or an executable contract boundary exists.

## Constraints and intentional state

- Keep repository source, documentation, commits, and PR metadata in English.
- The shipped Align revision for Request 6 is
  `e65448b744c04e3868d079eef8b45ce0d43ac8ee`; `.align-revision` remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` until the reviewed implementation branch consumes it.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted `HANDOFF.md`; do
  not discard or overwrite it.
- Diagnostic worktrees and branches are retained for evidence; never merge diagnostic-only
  instrumentation.
