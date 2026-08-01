# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-prompt-renderer`, based on `origin/main` at `4e1482e8e4942b70a9576f96285c0bf02aaaaae9`.
- Relevant commit: `345adc4` (`Implement pure prompt hierarchy renderer`).
- Active goal: publish one small C6 pure-renderer implementation PR, complete one review, fix all
  valid findings, run the required final verification, and stop this work.
- The implementation adds `src/prompt_render.align`, a focused `--prompt-render` smoke command,
  and the `prompt-render-smoke` hosted check. It does not call a provider, write artifacts, or
  mutate activation state.
- The earlier documentation-only C6 design work is intentionally outside this branch and must not
  be pulled into this PR.
- Pinned Align revision: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.

## Completed in the active slice

- Implemented the ordered base/repo/task/learned/context prompt hierarchy as a pure Align
  renderer with explicit context inclusion policy.
- Added an executable smoke that checks exact section order, delimiters, learned text, omitted
  failure memory, and diagnostic streams.
- Registered the focused smoke in the hosted check topology and synchronized its specification
  oracle.
- Added the repository verification-cadence rule: documentation-only changes do not require
  compilation, tests, or CI; focused verification happens once after a coherent implementation;
  full CI is reserved for changes that actually require it or the final integration point.

## Exact next steps

1. Push `345adc4` and open the implementation PR with the focused verification results.
2. Run one comprehensive review. Fix every valid finding in one consolidated repair; do not
   start another review unless the repair materially changes the design, implementation approach,
   public behavior, or governance.
3. Run the required final `make ci` once after review because this change updates the hosted check
   graph, then record its result in the PR and merge when all findings and checks are complete.

## Latest verification

```text
make prompt-render-smoke                         PASS
make check format-check gate-topology-check      PASS
make fmt                                         PASS
git diff --check                                 PASS
make ci                                          not yet run; reserved for final integration
```

## Constraints and intentional state

- Do not add provider calls, persistence, activation mutation, or the parked C6 design to this
  implementation slice.
- Review findings must be fixed completely; ordinary finding repairs do not trigger a second
  review.
- Source code, diagnostics, commits, pull requests, and developer documentation remain in English.
