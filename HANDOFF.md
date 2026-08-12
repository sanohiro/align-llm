# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-12)

- Branch `agent/update-checkout-action` is based on `origin/main` merge commit
  `2b0bd32ce0006a5e2cf0117d28afbe3c19c58903`.
- Active goal: replace the checkout action's deprecated Node 20 runtime with the latest stable,
  commit-pinned Node 24 release and use the resulting fresh-image PR as the first independent
  consumer of the trusted default-branch BuildKit cache.
- Complete: PR #71 merged proportional development rules. PR #72 merged exact merged-PR check
  reuse; merge-push run `31570429008` completed in 11 seconds versus the 492-second baseline
  (97.8% lower). PR #73 merged shared fresh-image layers and main run `31578101828` published the
  trusted cache while reusing functional checks and skipping image load and qualification.
- In progress: both checkout call sites use the official v7.0.1 commit. Owner/static checks,
  publication, and the hosted warm-cache measurement remain.

## Measurement

- Cached-image baseline PR #72 run `31569819343`, job `94029193340`: 502 seconds end to end and
  216,344 ms in `image-build` (`n=1`, GitHub `ubuntu-24.04`).
- A local Buildx `mode=max` probe took 2,076.861 seconds cold under a slow network and 39.568 seconds
  warm with different verifier keys. All 17 pre-key layers were cached; only the final key layer ran.
- PR #73 cold run `31576652775` passed: 16m43s overall, 11m56s to build/export/load, and 4m06s
  for complete installed qualification. It published 19 cache records totaling 3,738,896,174 bytes.
- Main seed run `31578101828` passed in 9m17s. Its cache-only build/export took 9m00s; the reused
  supported-check job took 7s, and image load plus qualification were skipped. The default-branch
  cache totals 3,757,595,376 bytes including the pre-existing unrelated cache record.
- Hosted target: after one exact merge publishes the `main` cache, a subsequent PR completes image
  build in at most 75 seconds and reduces overall run time at least 25% while the full installed
  qualification still passes. A cache-miss source build must also pass.

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This workflow branch
  contains none of its product implementation and does not change `.align-revision`.
- Do not modify, rerun, push, merge, or use PR #69 as workflow evidence until the user identifies
  the final Align commit. Closed PRs #64 and #67 remain unmergeable evidence only.

## Next steps

1. Run the proportional workflow owner/static checks, publish the checkout update, and verify that
   its hosted image build imports the `main` cache in at most 75 seconds with no Node 20 annotation.
2. Record the warm result in pull-request metadata and the next substantive capability checkpoint.
3. Keep PR #69 paused until the final Align revision is named.

## Latest durable evidence

- On PR #73, `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-development-preflight`: PASS. It covers signing
  material ownership, modes, disclosure, cleanup, partial failure, CLI behavior, prepared-image
  forwarding, cache topology, exact-merge publication, and the existing selector matrix.
- Real prepared-image owner invocation with the pinned `/tmp/align` checkout: PASS in 192.336
  seconds; image admission was 29 ms and worker aggregate was 104.657 seconds. The immediately prior
  invocation reached the aggregate but returned the existing `ERROR CHILD aggregate`; the identical
  path passed on retry, so retain this as a flaky-candidate observation rather than cache evidence.
- `python3 scripts/check-gate-topology --self-test`, Python syntax parsing, Ruby YAML parsing,
  `git diff --check`, and no repository bytecode: PASS. Full preflight on reviewed head `78a9c41`
  passed: owner 1.287 seconds, pinned Align build 0.744 seconds, hosted graph 3.316 seconds, focused
  qualification 20.677 seconds, and installed profile 204.399 seconds. After the review repair,
  `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-development-preflight`, Ruby YAML parsing,
  `git diff --check`, and no bytecode pass. Full preflight on repair commit `135b7c6` also passed:
  owner 1.538 seconds, pinned Align build 0.696 seconds, hosted graph 3.138 seconds, focused
  qualification 20.094 seconds, and installed profile 204.536 seconds.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional modified `HANDOFF.md` and untracked `io_copy`, plus
  the paused Request 6 worktree's untracked `prompt_model_smoke`. They are outside this branch.
- Keep source, documentation, commits, pull-request text, diagnostics, and timing fields in English.
- This branch has no intentional uncommitted artifact outside the workflow capability files.
