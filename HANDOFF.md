# Session handoff

Read `CLAUDE.md` first. This file records durable execution state only; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/convergence-guardrails`
- Base: `d3c30e9e83edd06a7e000f8903465c29f6687220` (`origin/main`)
- Active goal: make pull-request convergence limits externally reviewable so a long sequence of
  small finding-by-finding commits cannot be merged.
- Product implementation: stopped at the user's request.
- Pinned Align commit: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`
- PR #25 merged by squash at `d3c30e9`; it registered Request 7 but required 55 branch commits
  (47 content commits and 8 handoff commits) before merge. That history is the demonstrated failure
  this guardrail addresses.

PR #25's failure was not caused by the roughly one-minute final project check. The branch repeatedly
used broad review to discover contract details, committed findings in small batches, and continued
after the repository's existing root-cause and second-P1 stop rules required a class-wide audit and
re-scope. The existing prose stated the desired behavior but did not require every review envelope
to compare an advance budget with actual paths, lines, commits, and repair rounds.

This governance slice adds that missing enforcement boundary. A reviewer must return `NOT CLEAN`
when the budget is absent or exceeded. Documentation and request/design work defaults to 600
hand-written changed lines, three non-merge commits, and one consolidated repair round. Findings
must be collected before editing and repaired by root-cause class in one commit. Documentation-only
iterations use narrow checks; required full project CI runs once on the final candidate.

## Convergence budget

```text
Immutable base:
  d3c30e9e83edd06a7e000f8903465c29f6687220
Single slice:
  enforce externally reviewable pull-request convergence budgets
Allowed changed paths:
  CLAUDE.md
  HANDOFF.md
  docs/review-checklist.md
Maximum hand-written added-plus-deleted lines:
  600
Maximum non-merge commits:
  2
Maximum review-repair rounds:
  1
Per-iteration verification:
  git diff --check
  convergence count/path commands from CLAUDE.md
Final local verification:
  git diff --check
  test "$(readlink AGENTS.md)" = CLAUDE.md
  convergence count/path commands from CLAUDE.md
Hosted verification:
  required final-head GitHub check
```

No exception or identity-coupled commit topology applies. The initial commit contains the complete
governance change and this handoff. At most one consolidated review repair may follow.

## Exact next steps

1. Run the recorded narrow verification and commit the complete three-file change once.
2. Obtain one fresh independent adversarial preflight that explicitly reports the convergence
   budget and actual counts.
3. Open the governance pull request, obtain the final-head required check plus host-native and
   independent-adversarial reviews, and merge only if each envelope is clean.
4. Stop after this governance merge because the user stopped product work. When product work is
   resumed, refresh `main` and first reconcile the already implemented but unmerged
   `agent/check-gate-topology-implementation` branch before adding the fresh-compiler topology
   design required by Request 7.

## Constraints and intentional state

- `/home/hiro/prj/align-llm` remains the user's `agent/c6-prompt-context-design` worktree; do not
  alter or discard its intentional draft.
- `/home/hiro/prj/align-llm-governance` preserves the older topology implementation branch at
  `7290e37`; this slice does not modify it.
- `/tmp/align-llm-fresh-compiler-topology-design` is an unchanged branch/worktree created at
  `d3c30e9`; it contains no product edits.
- This slice changes repository governance only. Do not mix topology, Request 7, or product code.
