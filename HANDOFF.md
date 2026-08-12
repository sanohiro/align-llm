# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-12)

- Branch `agent/simplify-development-rules` is based on `origin/main` merge commit
  `0f82510ef1b2e9e7ee102b1ae96403f3e624273b`.
- Active goal: reduce development-process latency by replacing accumulated always-on prose with a
  change-class workflow and triggered risk checks. This is a governance/documentation capability;
  it does not change product code, CI topology, tests, builds, or `.align-revision`.
- Complete: the shared local preflight capability merged as PR #70 at the base commit above. Its
  classifier is now the executable source for final documentation, hosted, and fresh-image check
  selection.
- In progress: `CLAUDE.md` now routes work through five proportional rows and delegates high-risk
  contract detail to `docs/review-checklist.md`. The PR template and toolchain guide use the same
  routing. The stable candidate still needs its targeted checks, comprehensive governance review,
  and publication flow.

## Paused product checkpoint

- PR #69 remains the paused `FRESH-IMAGE-REQUEST6` installed focused-adoption capability at
  `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This governance branch contains none of its product
  implementation and does not change `.align-revision`.
- PR #69's temporary pin fails the repository link and hosted installed profile. Do not modify,
  rerun, push, merge, or use that branch as workflow evidence while Align development is active.
  Resume only after the user identifies the final Align commit.
- Closed PRs #64 and #67 remain unmergeable evidence only. The merged native-parent and preflight
  contract in `docs/specs/check-gate-topology.md` Section 9.10.3 remains authoritative.

## Next steps

1. Finish the author consistency pass across `CLAUDE.md`, `docs/review-checklist.md`, the pull
   request template, and `docs/align-development.md`.
2. Run documentation/static verification and one comprehensive governance review. Consolidate any
   valid findings and rerun only affected checks.
3. Run the exact-HEAD documentation preflight, publish, wait for required hosted evidence, and
   merge when terminal conditions are satisfied.
4. Refresh `main` after merge. Keep PR #69 paused until the final Align revision is named.

## Latest durable evidence

- Rule inventory: `CLAUDE.md` had grown through about 20 rule-changing commits to 487 lines / 4,463
  words; the first simplified candidate is 267 lines / 2,151 words.
- `git diff --check`: PASS for the first governance candidate.
- Comprehensive governance review and exact-HEAD preflight: not started.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional modified `HANDOFF.md` and untracked `io_copy`, plus
  the paused Request 6 worktree's untracked `prompt_model_smoke`. They are not part of this branch.
- Keep source, documentation, commits, pull-request text, diagnostics, and timing fields in English.
- This branch should contain only governance/documentation changes and has no intentional
  uncommitted product artifact.
