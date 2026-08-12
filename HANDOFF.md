# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations;
this file records durable project state.

## Active continuation checkpoint (2026-08-12)

- Branch `agent/local-preflight` is at reviewed repair commit
  `ff6bea1e453163a55620e3098988be8698f7da44`, based on `main` commit
  `d17e474b365df447593ba91764cf6662489835de`.
- Active goal: deliver the local development-preflight capability before resuming Request 6. It
  gives local and hosted execution one verification classifier, exact-HEAD local evidence,
  required local Docker behavior, non-duplicated installed qualification, and permanent phase
  timings. The public contract and closure matrix are in `docs/specs/development-preflight.md`.
- Complete: shared `docs` / `hosted` / `fresh-image` classification, local `scripts/pre-pr` plan
  and stamp path, CI adoption, installed-profile-only execution, required-Docker handling, phase
  records, owner regression, full pinned-source reuse/cache, `cgroupfs` boundary isolation, and the
  clean-worktree repair are implemented. Focused and installed qualification both pass.
- Complete: the matrix-to-diff pass and one high-effort comprehensive review of candidate
  `5e93bb2` are complete. Its two valid findings were consolidated in `ff6bea1`: executable
  self-test leakage into docs-only CI and a non-comparable performance claim. No final review is
  required because the repair only implements those recorded findings.
- In progress: final exact-HEAD preflight and publication. No pull request has been published.

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

1. Execute the full local preflight against the isolated pin so
   its stamp belongs to the final exact HEAD. Publish only after that local evidence is complete.
2. After this workflow capability merges, refresh `main`. Keep PR #69 paused until the user names
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
- `env -u DOCKER_HOST python3 scripts/run-fresh-worker-qualification
  --installed-profile-only --require-docker --align-repo
  /tmp/align-llm-preflight-full-align`: PASS in 198.572 seconds. The valid full-source boundary
  passed in 36.441 seconds and the worker aggregate passed in 104.677 seconds. The initial
  full-network baseline failed after 681.372 seconds; its boundary phase took 435.077 seconds.
- `make hosted-checks ALIGN_REPO=/tmp/align-pin-fetch.noHVWR`: PASS against the exact pin.
- `make eval-coding baseline-check ALIGN_REPO=/tmp/align-pin-fetch.noHVWR`: PASS. This diagnostic
  checkout was shallow and was used only for host checks; it was correctly rejected as installed
  worker source and is not the final preflight checkout.
- `git diff --check`: PASS. Python compilation passed. `actionlint` and PyYAML are unavailable, so
  workflow syntax currently relies on the owner topology test and later hosted parsing.
- `codex review --base main`: complete at high effort for candidate `5e93bb2`; two P2 findings,
  both accepted and repaired in `ff6bea1`. The affected owner regression passes after repair.
- Full exact-HEAD preflight is not yet complete.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional uncommitted `HANDOFF.md` and untracked `io_copy`.
  They are not part of this branch and must not be discarded or committed here.
- Keep all source, documentation, commits, PR text, diagnostics, and timing fields in English.
- This branch has no intentional uncommitted product file after the handoff checkpoint is committed.
