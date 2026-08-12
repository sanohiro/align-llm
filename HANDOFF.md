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
  implements a fail-closed selector plus workflow and owner-test adoption.
- In progress: owner regression, a live historical PR #71/merge #71 API query, and the complete
  local fresh-image preflight pass. The stable candidate still needs comprehensive review, final
  exact-HEAD preflight after this durable handoff update and any review repair, publication, and
  hosted PR/merge measurement.

## Measurement

- Baseline PR #70 run `31561096413`: 496 seconds end to end; the installed job took 492 seconds and
  its installed profile phase took 453.493 seconds.
- Duplicate merge-push run `31561600798`: 492 seconds end to end for the identical PR-head tree;
  its installed job took 488 seconds and repeated the same installed qualification.
- Candidate target: both merge-push jobs finish successfully in under 25 seconds while reporting
  the same reused PR number, head SHA, and PR workflow run. The PR run itself remains unchanged.

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This workflow branch
  contains none of its product implementation and does not change `.align-revision`.
- Do not modify, rerun, push, merge, or use PR #69 as workflow evidence until the user identifies
  the final Align commit. Closed PRs #64 and #67 remain unmergeable evidence only.

## Next steps

1. Complete one comprehensive review, consolidate valid findings, and rerun affected evidence.
2. Run the final exact-HEAD shared preflight, including required fresh-image qualification.
3. Publish the pull request, confirm its normal jobs pass, merge, and measure the merge-push reuse.
4. Refresh `main`; keep PR #69 paused until the final Align revision is named.

## Latest durable evidence

- `python3 scripts/test-development-preflight`: PASS. It covers exact reuse and fallback for wrong
  base, forced push, failed latest workflow, failed job, API failure, and changed merge tree.
- Live historical query: merge `2d9426e` selected PR #71 head `ecbfba9`, PR #71, and workflow run
  `31563707883` from Git identities plus GitHub API evidence.
- Full `python3 scripts/pre-pr --owner-test development-preflight -- python3
  scripts/test-development-preflight`: PASS on candidate `38ae7e5`. Phase timings were owner 0.340
  seconds, pinned Align build 3.832 seconds, hosted graph 4.107 seconds, focused qualification
  20.052 seconds, and installed profile 205.024 seconds. The installed worker aggregate took
  100.927 seconds.
- `git diff --check`, Python syntax, Ruby YAML parsing, `check-gate-topology --self-test`, and focused
  fresh-worker qualification: PASS for the current implementation batch.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional modified `HANDOFF.md` and untracked `io_copy`, plus
  the paused Request 6 worktree's untracked `prompt_model_smoke`. They are outside this branch.
- Keep source, documentation, commits, pull-request text, diagnostics, and timing fields in English.
- This branch has no intentional uncommitted artifact outside the workflow capability files.
