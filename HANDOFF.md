# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-12)

- Branch `agent/measure-workflow-performance` is based on `origin/main` merge commit
  `2d9426e62c2fe08dbb124f319bcb12b193cb4d13`.
- Active goal: reduce time to final integration evidence without weakening direct-push coverage.
  The measured target is the duplicate CI execution after an exact GitHub merge.
- Complete: PR #71 merged the proportional development rules. The current capability maps CI
  timings, defines exact merged-PR evidence reuse in `docs/specs/development-preflight.md`, and
  implements a fail-closed selector plus workflow and owner-test adoption. The comprehensive review
  of `eb1af874b93eaed155b5ddfc58c911d1e93ee37d` found four valid issues; one consolidated repair now
  binds both source job records to the exact PR/base/head, covers response-read and Git launch
  failures, expands the fail-closed matrix, and makes the baseline reproducible.
- Complete: because the repair materially changed the evidence strategy, the one allowed final
  comprehensive review covered the full repaired capability and passed with no findings.
- In progress: the stable candidate needs its final exact-HEAD preflight, publication, hosted PR
  evidence, merge, and merge-push measurement.

## Measurement

- Baseline PR #70 run `31561096413`: 496 seconds end to end. Duplicate merge-push run
  `31561600798`: 492 seconds end to end for the identical PR-head tree. Each is one sample on
  GitHub's `ubuntu-24.04` hosted environment; duration is `updated_at - created_at`. Reproduce the
  timestamps with the exact command in `docs/specs/development-preflight.md`.
- Candidate target: both merge-push jobs finish successfully in under 25 seconds while reporting
  the same reused PR number, head SHA, and PR workflow run. The PR run itself remains unchanged.

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This workflow branch
  contains none of its product implementation and does not change `.align-revision`.
- Do not modify, rerun, push, merge, or use PR #69 as workflow evidence until the user identifies
  the final Align commit. Closed PRs #64 and #67 remain unmergeable evidence only.

## Next steps

1. Run the final exact-HEAD shared preflight, including required fresh-image qualification.
2. Publish the pull request with both review envelopes and finding dispositions, confirm its normal
   jobs and PR/base/head evidence steps pass, merge, and measure the merge-push reuse.
3. Refresh `main`; keep PR #69 paused until the final Align revision is named.

## Latest durable evidence

- `python3 scripts/test-development-preflight`: PASS after the consolidated review repair. It covers
  exact reuse plus wrong PR base/ref/repository, another PR identity, ambiguous or paginated
  PR/run/job records, missing and failed jobs/evidence, malformed/oversized/incomplete API bodies,
  malformed/oversized events, Git launch failure, output failure, non-main/forced/created/deleted
  pushes, direct pushes, and merge-tree changes.
- Full `python3 scripts/pre-pr --owner-test development-preflight -- python3
  scripts/test-development-preflight`: PASS on candidate `38ae7e5`. Phase timings were owner 0.340
  seconds, pinned Align build 3.832 seconds, hosted graph 4.107 seconds, focused qualification
  20.052 seconds, and installed profile 205.024 seconds. The installed worker aggregate took
  100.927 seconds.
- `git diff --check`, Python syntax, Ruby YAML parsing, `check-gate-topology --self-test`, and focused
  fresh-worker qualification: PASS before review. Affected owner test, Python syntax, YAML parsing,
  and `git diff --check`: PASS after the consolidated repair; final exact-HEAD preflight is pending.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional modified `HANDOFF.md` and untracked `io_copy`, plus
  the paused Request 6 worktree's untracked `prompt_model_smoke`. They are outside this branch.
- Keep source, documentation, commits, pull-request text, diagnostics, and timing fields in English.
- This branch has no intentional uncommitted artifact outside the workflow capability files.
