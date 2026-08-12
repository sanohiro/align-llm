# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations;
this file records durable project state.

## Active continuation checkpoint (2026-08-12)

- Branch `agent/local-preflight` is at owner-tested implementation commit
  `646828dca2bf7577ed3d13da53ec960e20d30f2a`, based on `main` commit
  `d17e474b365df447593ba91764cf6662489835de`.
- Active goal: deliver the local development-preflight capability before resuming Request 6. It
  gives local and hosted execution one verification classifier, exact-HEAD local evidence,
  required local Docker behavior, non-duplicated installed qualification, and permanent phase
  timings. The public contract and closure matrix are in `docs/specs/development-preflight.md`.
- Complete: shared `docs` / `hosted` / `fresh-image` classification, local `scripts/pre-pr` plan
  and stamp path, CI adoption, installed-profile-only execution, required-Docker handling, phase
  records, owner regression, documentation, and the clean-worktree repair are implemented. The
  focused qualification passes through the timing wrapper.
- In progress: exact installed-profile verification, the stable-candidate matrix-to-diff pass, and
  the one comprehensive review. No pull request has been published.

## Paused product checkpoint

- PR #69 remains the paused `FRESH-IMAGE-REQUEST6` installed focused-adoption capability at
  `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This workflow branch contains none of its product
  implementation and does not change `.align-revision`.
- PR #69's old temporary pin fails the repository link and its hosted installed profile. Do not
  modify, rerun, push, merge, or use that branch as workflow evidence while Align development is
  active. Resume it only after the user identifies the final Align commit.
- The merged native-parent and preflight contract in `docs/specs/check-gate-topology.md` Section
  9.10.3 remains authoritative. Closed PRs #64 and #67 remain unmergeable evidence only.

## Next steps, in priority order

1. Run the installed-only profile from this changed tree with `DOCKER_HOST` absent and Docker
   required. Use an isolated exact-pin Align checkout for later full preflight; do not build or
   modify the active sibling Align worktree.
2. Perform the matrix-to-diff pass, commit this handoff checkpoint, and run one comprehensive
   stable-candidate review. Apply all valid findings in one consolidated repair if needed.
3. Rerun only affected owners, then execute the full local preflight against the isolated pin so
   its stamp belongs to the final exact HEAD. Publish only after that local evidence is complete.
4. After this workflow capability merges, refresh `main`. Keep PR #69 paused until the user names
   the completed Align revision; workflow completion does not authorize Request 6 resumption.

## Latest verification

- `python3 scripts/test-development-preflight`: PASS after the clean-worktree repair.
- `python3 scripts/run-fresh-worker-qualification`: PASS; all nine focused owners executed once.
  The largest observed owners were `check-gate-topology --self-test` at 5.781 seconds and
  `run-fresh-worker-unit-smoke` at 4.967 seconds.
- `python3 scripts/pre-pr --plan --owner-test development-preflight -- python3
  scripts/test-development-preflight`: PASS on commit `646828d`; selected owner, pinned Align
  build, hosted checks, focused qualification, and installed-only required-Docker qualification in
  that order, with `DOCKER_HOST` removed from the installed step.
- `git diff --check`: PASS. Python compilation passed. `actionlint` and PyYAML are unavailable, so
  workflow syntax currently relies on the owner topology test and later hosted parsing.
- Installed-profile, full preflight, comprehensive review, and hosted checks are not yet complete.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional uncommitted `HANDOFF.md` and untracked `io_copy`.
  They are not part of this branch and must not be discarded or committed here.
- Keep all source, documentation, commits, PR text, diagnostics, and timing fields in English.
- This branch has no intentional uncommitted product file after the handoff checkpoint is committed.
