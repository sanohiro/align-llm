# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-boundary-design`, based on merged `main` commit
  `11262a785f4c994ecfae2d9d95f67f32d7056108`.
- Active goal: correct the Request 6 delivery order after PR #64's independent review. The
  current design adds a separate non-evidence `FRESH-IMAGE-REQUEST6-BOUNDARY` enabling checkpoint;
  the full `ordinary-adoption` transport and consumer remain deferred.
- PR #64 was closed without merge after review found an unsafe partial worker/helper path, a weak
  parent-authentication fallback, a broken socket endpoint handoff, and inconsistent scope claims.
  Its review envelope and findings are recorded in GitHub PR #64; do not patch or merge that branch.
- The boundary contract is intentionally limited to image/manifest binding, strict
  `ordinary-adoption-boundary` argv/env/fd validation, retained FD14 dispatch, absolute Align FD18
  identity, and pre-Make rejection of absent, present, or malformed workers. It creates no nonce,
  channel, capsule, worker memfd, proof, bwrap child, namespace helper, or repository-controlled
  child.

## Next steps, in priority order

1. Run the design checks and one fresh independent adversarial review of this correction.
2. Open and merge the design correction PR, then create a new implementation branch from its merge.
3. Implement only the boundary contract, run the focused and hosted installed boundary checks, and
   complete one comprehensive implementation review before merging.
4. Refresh `main`, perform the bounded retrospective, and start the full consumer-complete
   FRESH-IMAGE-REQUEST6 slice only after its prerequisites remain satisfied.

## Latest verification

- `git diff --check`: PASS after the design correction.
- `make gate-topology-check`: PASS (`check gate topology: PASS`).
- Markdown fence parity: PASS for `docs/align-requests.md` and
  `docs/specs/check-gate-topology.md`.
- No executable source, image, compiler pin, or Align source has changed on this branch.

## Constraints and intentional state

- Keep repository source, documentation, commits, PR metadata, and diagnostics in English.
- Do not change `.align-revision` in the boundary design or implementation slices.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted `HANDOFF.md`; do
  not discard or overwrite it.
- Diagnostic worktrees and branches are retained for evidence; never merge diagnostic-only
  instrumentation.
