# Session handoff

Read `CLAUDE.md` first. This file records durable capability state; GitHub owns transient pull
request checks, reviews, findings, and attestations.

## Current state

- Branch: `agent/streamline-development-workflow`, based on `origin/main` merge commit
  `552e8bd20524a7a0ae51eda929023ce46c56d145` (PR #58).
- Active goal: make delivery capability-oriented and keep routine verification bounded without
  reducing the C6, C7, or fresh-compiler contracts.
- Complete foundation: PRs #54-#58 merged the Section 9 fresh-compiler design, wire formats, and
  descriptor-relative source identity. They are internal foundations of FRESH-WORKER, not future
  helper-only pull request boundaries.
- Complete on this branch: governance, roadmap, Align-request adoption, C6/C7 delivery boundaries,
  check-topology policy, developer guidance, and coding-task resource qualification ownership are
  synchronized as one workflow capability. The resource/race qualification remains available as a
  direct focused command but is no longer a transitive child of every `eval-coding` run.

## Next actions

1. Publish one workflow pull request, obtain the required comprehensive adversarial review, apply
   any valid findings in one repair, and merge after required checks pass.
2. After merge, begin FRESH-WORKER as one consumer-complete capability: private-root admission,
   source/cache materialization, compiler bundle, process ownership, cleanup, Make integration, and
   core end-to-end functional smoke. FRESH-IMAGE remains a separate operational failure domain.

## Latest verification

- `git diff --check`, `bash -n scripts/run-coding-task-invalid-smoke`, and the balanced Markdown
  fence assertion: PASS.
- `python3 scripts/check-gate-topology --self-test` and `make gate-topology-check`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-coding-task-resource-scan-smoke`: PASS as the
  focused resource/race qualification.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-coding-task-invalid-smoke`: PASS without invoking the
  resource qualification.
- `PYTHONDONTWRITEBYTECODE=1 make eval-coding`: PASS in 21.751 seconds of shell-reported real time.
- `PYTHONDONTWRITEBYTECODE=1 make ci`: PASS at pinned Align revision
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; this workflow change
  does not adopt a compiler or proposed Align surface.
- Specification scope is unchanged. C6/C7 labels and closure rows remain acceptance ownership cells,
  while branches and pull requests are grouped by consumer-complete capability.
- Core aggregates contain bounded functional integration. Security, resource, race, fuzz, stress,
  mutation, platform, and benchmark qualification run through named owner commands when their
  boundary changes or an explicit audit requires them.
- Time and line counts are diagnostic expectations, not gates or quotas. Lack of progress triggers
  a cost and boundary audit; it does not automatically trigger a smaller pull request.
- The separate primary worktree has an intentional uncommitted `HANDOFF.md`; do not discard or
  overwrite it while this clean worktree is active.
