# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Current state

- Branch: `agent/fresh-worker-capability`, based on PR #61 base
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18`.
- PR #61 is still draft and must merge with method `merge`; the current pushed product head is
  `870baf4d7faf03f579dde6256e79b4be91168dec`. Local repair work is uncommitted after the
  closure-plan commit `b69aff1`.
- Active goal: finish the reviewed FRESH-WORKER repair, complete PR review/fix/merge, then start
  the next eligible roadmap gate without waiting for a stop instruction.
- The prior baseline tuple
  `6b2828c3f0353cc5cd66854167f350a58faffb4e` /
  `f095a04d898e2b31aa9c8fd7e77a7f213a367369` /
  `870baf4d7faf03f579dde6256e79b4be91168dec` is invalidated by the new baseline-chain gate
  and must be refreshed after the repair reaches a clean source commit.

## Review and repair

- A fresh independent adversarial review found four valid non-trivial gaps: tool/Git descendants
  were outside the shared worker owner, cgroup leaves were pathname-owned, private-root cleanup
  closed identity witnesses before removal, and `make baseline-check` did not execute the
  Section 2.4 commit-chain contract.
- Closure plan `b69aff1` records the repair owners and regression boundaries.
- In progress: route every worker child through the bounded runner; make cgroup and private-root
  cleanup descriptor-relative; harden image-control child ownership; add
  `scripts/check-baseline-chain` to `baseline-check`; update focused regression coverage.
- The diagnostic branch `agent/fresh-worker-current-diagnostic` exposed only the hosted
  `filesystem` category before aggregate failure and is not product code.

## Next steps, in priority order

1. Finish the four repairs and run focused worker, image-control, qualification, source, and
   project checks.
2. Commit the final implementation source, record two deterministic-reference samples, commit the
   immutable oracle, finalize the canonical baseline, remove pending output, and run the complete
   executable baseline-chain gate.
3. Push PR #61, obtain passing hosted pinned and installed checks, publish the final SHA-bound
   comprehensive review envelope and all finding dispositions, mark ready, and merge the exact
   head with method `merge`.
4. Refresh `main`, perform the bounded retrospective, update this handoff for the post-merge
   checkpoint, and start the next roadmap gate.

## Latest verification

- `make check`: PASS; only existing Align compiler warnings remain.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-image-control-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: one transient
  linked-worktree source-identity failure; the focused source-identity smoke passed on immediate
  rerun, so qualification must be rerun before the source commit.
- `git diff --check`: PASS.
- Hosted run `31137327638` passed the pinned job but failed the installed aggregate with
  `filesystem`; diagnostic run `31137864283` reproduced the same category and is evidence
  only.

## Constraints and intentional state

- Keep all repository source, documentation, diagnostics, commits, and PR metadata in English.
- `.align-revision` remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no Align language request is open for this gate.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted
  `HANDOFF.md`; do not discard or overwrite it.
- Diagnostic worktrees and branches are intentionally retained for evidence; never merge their
  diagnostic-only instrumentation.
