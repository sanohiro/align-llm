# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-adoption-contract-v5`, with v5 design content complete at
  `4d03a01`, based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`. The current HEAD is the handoff-only commit
  immediately following that content commit; no design content follows it.
- Active goal: finish and merge the redesigned Request 6 focused-adoption contract, then implement
  the separately gated installed profile and authenticated adoption. Request 7 registration and
  other independent planning may continue; Request 6 adoption and consumer implementations remain
  blocked until their named image and worker profiles merge.
- The v5 design keeps ordinary adoption behind trusted image-owned
  `fresh-supervise --mode ordinary-adoption`, which authenticates the fixed manifest, retains the
  Request 6 dispatcher at FD 14, creates a fresh sealed nonce at FD 15, and invokes it with
  `execveat(AT_EMPTY_PATH)`; legacy bootstrap/run-capsule flow is explicitly separate. The signed
  `ordinary-adoption/v1` capsule and sealed worker use fixed-name memfd construction, an observable
  Linux memfd predicate (`S_IFREG`, zero link count, `TMPFS_MAGIC`, fixed `/proc/self/fd` name, and
  exact seals), and an explicit creator trace because Linux exposes no post-hoc
  `MFD_ALLOW_SEALING` bit.
- The v5 authority ledger specifies offset-zero transitions after every read and before every
  supervisor/dispatcher/worker/bwrap/helper edge. It scopes the legacy no-worker-FD rule to legacy
  aggregate paths and permits FD 12/13/15 only through the ordinary namespace helper; all three are
  closed before Make children. It adds an independently hashed `raw-tree-v1` six-entry golden with
  raw-byte/non-UTF-8/symlink coverage and requires the installed-profile gate to regress legacy
  `fresh-supervise --mode self-test` with exact output and no ordinary markers. The existing root
  sealing, fixed helper vectors, complete argv/env plan, phase grammar, output grammar, nonce golden,
  and milestone ordering remain in force.
- PR #62 is superseded and must not be merged. v2 was rejected by its final review; v3 was rejected
  for authority-FD leakage, incomplete seals/helper plans, phase/milestone ambiguity, and self-test
  dispatch; v4 was rejected by the fresh review for an impossible memfd link-count predicate,
  incomplete offset transitions, contradictory descriptor inheritance, missing raw-tree golden,
  missing self-test regression, and stale exact-head handoff evidence. Those findings are redesigned
  in v5 and must not be patched on the superseded branches.
- Expected post-merge checkpoint: refresh `main` safely, perform the bounded design retrospective,
  and create `agent/request6-image-profile-extension` for the separately reviewed installed-profile
  gate. After that profile extension merges, create `agent/request6-adoption-implementation`; the
  implementation branch must not reuse PR #62's direct ordinary Make command.

## Next steps, in priority order

1. Run one fresh comprehensive independent review of the current v5 branch HEAD; do not publish the
   v5 design until the review is clean.
2. Record the v4 review findings and dispositions on PR #62, close it as superseded, publish the v5
   design PR, and complete its review/fix/merge evidence.
3. Refresh `main`, record the bounded retrospective, implement and merge the FRESH-IMAGE-REQUEST6
   profile extension on its own branch, then implement Request 6 on a new branch; review, repair,
   merge, refresh `main`, and continue to the next eligible roadmap gate.

## Latest verification

- `git diff --check`: PASS at v5 content commit `4d03a01`.
- `make gate-topology-check`: PASS at v5 content commit `4d03a01`.
- `python3 scripts/check-gate-topology --self-test`: PASS at v5 content commit `4d03a01`.
- Fence parity command for `docs/align-requests.md` and `docs/specs/check-gate-topology.md`: PASS
  (`100`, `76`) at v5 content commit `4d03a01`.
- `raw-tree-v1-golden` extraction and SHA-256 check: PASS (`1318` bytes,
  `820d928b48c7c8fd88ce69230608143310caa17f020e72f8f2ceb23ff2354f4f`) at v5 content commit
  `4d03a01`.
- This is a docs/specification-only gate. Source tests, `make check`, `make build`, and `make ci`
  are N/A and remain deferred to executable implementation/profile slices.

## Constraints and intentional state

- Keep repository source, documentation, commits, and PR metadata in English.
- The shipped Align revision for Request 6 is
  `e65448b744c04e3868d079eef8b45ce0d43ac8ee`; `.align-revision` remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` until the reviewed implementation branch consumes it.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted `HANDOFF.md`; do
  not discard or overwrite it.
- Diagnostic worktrees and branches are retained for evidence; never merge diagnostic-only
  instrumentation.
