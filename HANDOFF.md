# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-prompt-renderer`, based on `origin/main` at `4e1482e8e4942b70a9576f96285c0bf02aaaaae9`.
- Relevant commits: `345adc4` (initial renderer) and `a18e7e4` (`Keep prompt renderer
  fixture-private`).
- Active goal: publish the repaired fixture-private C6 renderer PR #34, with the one completed
  review's findings fixed, and stop this work.
- The implementation adds `src/prompt_render.align` and a fixture-only
  `src/prompt_render_smoke.align` executable. It does not add a product CLI, call a provider,
  write artifacts, or mutate activation state.
- The earlier documentation-only C6 design work is intentionally outside this branch and must not
  be pulled into this PR.
- Pinned Align revision: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.

## Completed in the active slice

- Implemented the ordered base/repo/task/learned/context prompt hierarchy as a pure Align
  renderer with explicit context inclusion policy.
- Added a fixture-only executable smoke that checks exact section order, delimiters, learned text,
  omitted failure memory, and diagnostic streams.

## Exact next steps

1. Push `a18e7e4` and update PR #34 with the repair and disposition of all three findings.
2. The comprehensive review is complete. No second review is needed: the repair only removes the
   unreviewed public surface, separates the smoke from the hosted topology, and removes unrelated
   governance changes.
3. Merge PR #34 after the focused check is recorded; this final diff does not change the product
   CLI, build graph, or CI gate, so full `make ci` is not required.

## Latest verification

```text
./scripts/run-prompt-render-smoke                 PASS
git diff --check                                 PASS
make ci                                          not applicable to the final fixture-only diff
```

## Constraints and intentional state

- Do not add provider calls, persistence, activation mutation, or the parked C6 design to this
  implementation slice.
- Review findings must be fixed completely; ordinary finding repairs do not trigger a second
  review.
- Source code, diagnostics, commits, pull requests, and developer documentation remain in English.
