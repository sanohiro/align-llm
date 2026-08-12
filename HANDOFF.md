# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-12)

- Branch `agent/cache-hosted-apt-llvm-v2` is based on `origin/main` merge commit
  `530da31d74b9ef79a7cfc2efafbeaee5c927ef4f`.
- Active goal: replace repeated hosted apt.llvm.org resolution with sibling Align's verified
  replayable archive cache, while using the unchanged Dockerfile as the first exact warm consumer
  of the smaller fresh-image cache.
- Complete: PR #71 merged proportional development rules. PR #72 merged exact merged-PR check
  reuse; merge-push run `31570429008` completed in 11 seconds versus the 492-second baseline
  (97.8% lower). PR #73 merged shared fresh-image layers and main run `31578101828` published the
  trusted cache while reusing functional checks and skipping image load and qualification. PR #74
  merged the complete Node 24 action migration at `d433e4d66a180e077cb667edcc3ff6050a3f0542`.
  PR #75 merged hardlink-preserving runtime materialization at `530da31d74b9ef79a7cfc2efafbeaee5c927ef4f`.
- In progress: the first apt archive candidate was stopped after its conditional final review found
  that manifest membership was not exact and the cleanup ownership model still missed dangling
  symlinks, a conditionally created directory, and retention after cleanup failure. The v2 branch
  reopens the closure matrix around one transactional rule: a cache candidate becomes saveable only
  after exact archive membership, the real hosted consumer, and all non-archive cleanup succeed.
  The redesigned implementation and focused regressions are present locally; complete preflight,
  independent review, publication, cache seed, and clean warm measurement remain.

## Measurement

- Cached-image baseline PR #72 run `31569819343`, job `94029193340`: 502 seconds end to end and
  216,344 ms in `image-build` (`n=1`, GitHub `ubuntu-24.04`).
- A local Buildx `mode=max` probe took 2,076.861 seconds cold under a slow network and 39.568 seconds
  warm with different verifier keys. All 17 pre-key layers were cached; only the final key layer ran.
- PR #73 cold run `31576652775` passed in 17m00s end to end; the fresh job took 16m43s, including
  11m56s to build/export/load and 4m06s for complete installed qualification. It published 19
  BuildKit cache records totaling 3,738,896,174 bytes.
- Main seed run `31578101828` passed in 9m21s end to end; the fresh job took 9m17s, including a
  9m00s cache-only build/export. The reused supported-check job took 7s, and image load plus
  qualification were skipped. Its 19 default-branch BuildKit records total 3,738,896,114 bytes.
- PR #74 warm-cache run `31579614586` passed in 7m52s; the fresh job took 7m48s, image
  build/export/load 182 seconds, and qualification 246 seconds. Heavy instructions were cached,
  but materialization and export/load still moved 1.50 GB and 1.25 GB layers. Overall time improved
  only 6.0%, so the existing 75-second build and 25% overall targets were not met. Main run
  `31580371758` completed its cache-only fresh job in 1m42s, including 88 seconds for build/export.
- The exact local `d433e4d` comparison passed the footprint gate: image size fell from
  10,451,313,589 to 6,069,945,116 bytes (41.9%), `/runtime` from 7,397,588,418 to 3,016,219,340
  bytes (59.2%), and `/runtime/git` from 2,617,299,268 to 83,290,477 bytes (96.8%). Git and
  `git-receive-pack` now share one 142-link inode. The 1,084.585-second cold base build and
  44.283-second warm candidate build are diagnostic only because their cache states differ.
- PR #75 run `31588797654` passed in 9m28s; its fresh job took 9m24s, image build/export/load
  293 seconds, and qualification 225 seconds. Merge run `31589611628` published the smaller trusted
  `main` cache in a 3m03s fresh job while the reused check job took 8s. On PR #75 the normal check
  job took 102 seconds, including 43 seconds for LLVM/native installation; these are the apt-cache
  baseline values (`n=1`, GitHub `ubuntu-24.04`).
- Hosted target: after one exact merge publishes the `main` cache, a subsequent PR completes image
  build in at most 75 seconds and reduces overall run time at least 25% while the full installed
  qualification still passes. A cache-miss source build must also pass.

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This workflow branch
  contains none of its product implementation and does not change `.align-revision`.
- Do not modify, rerun, push, merge, or use PR #69 as workflow evidence until the user identifies
  the final Align commit. Closed PRs #64 and #67 remain unmergeable evidence only.

## Next steps

1. Run the apt archive owner, development-preflight owner, workflow syntax/static checks, and the
   proportional fresh qualification selected by the workflow change.
2. Perform the required independent adversarial review, publish, confirm the PR miss and exact-main
   cache seed, then measure one clean warm run before claiming the 10-second install/75-second check
   targets.
3. Continue with a multi-stage builder/runtime image after merge. Keep PR #69 paused until the
   final Align revision is named.

## Latest durable evidence

- PR #75 independent review: PASS with no findings. Local final installed qualification and hosted
  run `31588797654` both passed; the baseline and candidate toolchain and Cargo manifests were
  identical.
- `scripts/test-apt-llvm`: PASS after adapting sibling Align's cache hit, miss, corruption, repair,
  repository provenance, signing-key, round-trip, cache-key, and argument regression.
- `python3 scripts/test-development-preflight`, `python3 scripts/check-gate-topology --self-test`,
  workflow YAML parsing, Bash syntax, and `git diff --check`: PASS on the uncommitted candidate.
- The stopped candidate's final preflight passed at `7e74856deb964e6cc4b7064a9e07abc90f23aea1`,
  but its final review failed and that evidence is not publication authority.
- On the uncommitted v2 candidate, `scripts/test-apt-llvm`, development preflight, gate-topology
  self-test, workflow YAML parsing, Bash syntax, and `git diff --check`: PASS. The focused owner now
  covers exact manifest membership, symlink targets, borrowed/created keyring-directory ownership,
  and injected cleanup failure at every owned path.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional modified `HANDOFF.md` and untracked `io_copy`, plus
  the paused Request 6 worktree's untracked `prompt_model_smoke`. They are outside this branch.
- Keep source, documentation, commits, pull-request text, diagnostics, and timing fields in English.
- This branch has no intentional uncommitted artifact outside the workflow capability files.
