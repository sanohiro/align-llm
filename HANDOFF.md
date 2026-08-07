# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-adoption-contract-v2`, with design content complete at
  `f96bad37a07e16f0d48b8b0bb12c1bc1e69ae2f8`, based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`. This handoff-only metadata update follows that
  design commit; no design content follows it.
- Active goal: finish and merge the corrected Request 6 focused-adoption design, then implement
  the ordinary launcher, focused target and fixtures, shipped Align pin, fresh adoption vector,
  baseline ancestry, and final fresh `make ci` on a new branch. Request 7 and later consumers stay
  blocked on this gate.
- The latest design repair passes every manifest tool through retained FD-backed setup into the
  namespace-owned read-only `/tools` inventory, fixes the ordinary executable-resolution ledger,
  reserves non-overlapping tool descriptors at FD 400 onward, adds the separate
  FRESH-IMAGE-REQUEST6 installed-profile prerequisite, and raises Cargo home to 24 GiB with a
  page-rounded materialization bound and 2 GiB metadata reserve. The earlier private
  `align-build-only` vector, in-namespace child ownership, namespace-owned sealing, outer
  cgroup/host-root ownership, and post-build compiler digest handoff remain in force. A fresh
  independent review is required.
- PR #62 is superseded and must not be merged. The replacement design PR must include the corrected
  vectors and current handoff state.
- Expected post-merge checkpoint: refresh `main` safely, perform the bounded design retrospective,
  and create `agent/request6-image-profile-extension` for the separately reviewed installed-profile
  gate. After that profile extension merges, create `agent/request6-adoption-implementation`; the
  implementation branch must not reuse PR #62's direct ordinary Make command.

## Next steps, in priority order

1. Run one fresh independent adversarial review of `f96bad3`, then update the design PR with its
   SHA-bound review envelope and merge it only after checks and all findings are resolved.
2. Close PR #62 as superseded, publish the replacement design PR, and complete its review/fix/merge
   evidence.
3. Refresh `main`, record the bounded retrospective, implement and merge the FRESH-IMAGE-REQUEST6
   profile extension on its own branch, then implement Request 6 on a new branch; review, repair,
   merge, refresh `main`, and continue to the next eligible roadmap gate.

## Latest verification

- `make gate-topology-check`: PASS at `f96bad3`.
- `git diff --check`: PASS at `f96bad3`.
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
