# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-12)

- Branch `agent/cache-fresh-image-build` is based on `origin/main` merge commit
  `7a7cdc048cf30e4cd8c5ab85f80fbc14e6c18b1e`.
- Active goal: stop rebuilding and downloading content-identical apt, LLVM, Git, bubblewrap, Rust,
  and Align Cargo layers on every hosted fresh-image job without weakening per-run signing or the
  installed-profile qualification.
- Complete: PR #71 merged the proportional development rules. PR #72 merged exact merged-PR check
  reuse; its merge-push run `31570429008` completed in 11 seconds versus the 492-second baseline
  (97.8% lower) while both jobs bound the same PR, workflow run, and head.
- In progress: the follow-on capability defines a branch-scoped BuildKit cache, prepares fresh
  signing seeds per run, builds the hosted image once, passes the loaded image into the unchanged
  installed owner, and publishes trusted cache state on an exact merge without loading or repeating
  functional verification. The independent review of `78a9c4126d7bb7854309164ae44ac45597c26f44`
  found two valid serialization-boundary issues: partial GitHub output on a non-ASCII path and a
  non-integer marker version accepted through Python equality. One consolidated repair validates
  and renders before side effects, writes one record, and enforces the exact schema type. Affected
  verification and full preflight pass on repair commit
  `135b7c67abb184c5b884b8736abbec96de456cfc`; publication and hosted cold/warm measurements remain.

## Measurement

- Cached-image baseline PR #72 run `31569819343`, job `94029193340`: 502 seconds end to end and
  216,344 ms in `image-build` (`n=1`, GitHub `ubuntu-24.04`).
- A local Buildx `mode=max` probe took 2,076.861 seconds cold under a slow network and 39.568 seconds
  warm with different verifier keys. All 17 pre-key layers were cached; only the final key layer ran.
- Hosted target: after one exact merge publishes the `main` cache, a subsequent PR completes image
  build in at most 75 seconds and reduces overall run time at least 25% while the full installed
  qualification still passes. A cache-miss source build must also pass.

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This workflow branch
  contains none of its product implementation and does not change `.align-revision`.
- Do not modify, rerun, push, merge, or use PR #69 as workflow evidence until the user identifies
  the final Align commit. Closed PRs #64 and #67 remain unmergeable evidence only.

## Next steps

1. Publish the PR with the SHA-bound review, both finding dispositions, and measurement evidence;
   verify the cold PR build and cache-publishing merge, then verify a subsequent warm PR against
   the `main` cache.
2. Keep PR #69 paused until the final Align revision is named.

## Latest durable evidence

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-development-preflight`: PASS. It covers signing
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
