# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-12)

- Branch `agent/cache-hosted-align-bundle` is based on PR #76 merge commit
  `c3deab753a3db4e963817917c1105fe110907a99`.
- Active goal: replace the measured 36-second cached dpkg replay and 6-second Rust download with a
  trusted hosted Align compiler bundle that lets normal checks start directly from a verified
  `alignc`, runtime archive, and LLVM shared library.
- Complete: PR #71 merged proportional development rules. PR #72 merged exact merged-PR check
  reuse; merge-push run `31570429008` completed in 11 seconds versus the 492-second baseline
  (97.8% lower). PR #73 merged shared fresh-image layers and main run `31578101828` published the
  trusted cache while reusing functional checks and skipping image load and qualification. PR #74
  merged the complete Node 24 action migration at `d433e4d66a180e077cb667edcc3ff6050a3f0542`.
  PR #75 merged hardlink-preserving runtime materialization at `530da31d74b9ef79a7cfc2efafbeaee5c927ef4f`.
  PR #76 merged and seeded the verified hosted LLVM archive cache at `c3deab753a3db4e963817917c1105fe110907a99`.
- In progress: design the compiler bundle contract before implementation. A local real-client probe
  copied only `alignc`, `libalign_runtime.a`, and `libLLVM.so.22.1` (183,999,150 bytes total), bound
  the shared library through `LD_LIBRARY_PATH`, and passed the complete `hosted-checks`. The bundle
  cache will be keyed by the pinned Align revision, exact runner image, OS/architecture, Rust
  version, LLVM major, and manual schema generation. Pull requests restore but never publish;
  exact main misses build, consume, verify, save, exact-lookup, and require literal cache hit.

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
- PR #76 miss run `31597025980` passed: the check job took 85 seconds, apt resolution/install 17
  seconds, Rust 7 seconds, and supported checks 49 seconds. The fresh job took 422 seconds; image
  build/export/load took 137 seconds and installed qualification 243 seconds.
- Main seed run `31597640816` passed the exact archive consumer, save, lookup, and literal-hit gates.
  Its check job took 85 seconds; the cache-only fresh job took 81 seconds and image build/export
  took 62 seconds, meeting the 75-second cache-only build target.
- Clean warm run `31597786779` passed but disproved the archive replay performance target: restore
  took 3 seconds, cached dpkg install 36 seconds, Rust 6 seconds, supported checks 39 seconds, and
  the check job 100 seconds. The full fresh job took 405 seconds, including 114 seconds for image
  build/export/load and 242 seconds for installed qualification. Apt repository downloads no longer
  repeat, but replay remains too slow. The replacement bundle target is restore plus verification
  at most 10 seconds and a complete normal check job at most 60 seconds (`n=1`, same runner image).

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This workflow branch
  contains none of its product implementation and does not change `.align-revision`.
- Do not modify, rerun, push, merge, or use PR #69 as workflow evidence until the user identifies
  the final Align commit. Closed PRs #64 and #67 remain unmergeable evidence only.

## Next steps

1. Finish the hosted compiler-bundle public ledger and closure matrix, then perform the author
   consistency/risk pass.
2. Implement strict create/verify/key ownership, workflow hit/miss/publication routing, and focused
   regressions. Preserve the archive path as the miss fallback.
3. Run proportional preflight, independent review, PR miss, exact-main seed, and one clean warm
   measurement before claiming the 60-second check target.
4. Continue with a multi-stage builder/runtime image. Keep PR #69 paused until the final Align
   revision is named.

## Latest durable evidence

- PR #76 final review passed at `fa56846af74af9208abdd01ecc72a6437f05d267` with no findings after
  one consolidated repair. Complete preflight passed: apt owner 4.421s, pinned Align build 0.647s,
  installed profile 206.879s, and worker aggregate 109.049s.
- PR, exact-main seed, and clean warm GitHub runs `31597025980`, `31597640816`, and `31597786779`
  all passed. The clean warm run is the evidence that redirects the next capability from archive
  replay toward the verified compiler bundle.
- Local bundle probe: exact three-file bundle, 183,999,150 bytes; `LD_LIBRARY_PATH` resolved
  `libLLVM.so.22.1` from the bundle; `alignc --version` and complete `make hosted-checks` passed.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional modified `HANDOFF.md` and untracked `io_copy`, plus
  the paused Request 6 worktree's untracked `prompt_model_smoke`. They are outside this branch.
- Keep source, documentation, commits, pull-request text, diagnostics, and timing fields in English.
- This branch has no intentional uncommitted artifact outside the workflow capability files.
