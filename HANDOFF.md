# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-12)

- Branch `agent/slim-fresh-runtime-image` is based on `origin/main` merge commit
  `d433e4d66a180e077cb667edcc3ff6050a3f0542`.
- Active goal: reduce fresh-image transfer and load cost by preserving resolved regular-file
  hardlinks while materializing image-owned runtime trees, without changing manifests, runtime
  paths, worker behavior, or the pinned Align revision.
- Complete: PR #71 merged proportional development rules. PR #72 merged exact merged-PR check
  reuse; merge-push run `31570429008` completed in 11 seconds versus the 492-second baseline
  (97.8% lower). PR #73 merged shared fresh-image layers and main run `31578101828` published the
  trusted cache while reusing functional checks and skipping image load and qualification. PR #74
  merged the complete Node 24 action migration at `d433e4d66a180e077cb667edcc3ff6050a3f0542`.
- In progress: the materializer contract, implementation, synthetic alias/cycle/failure regression,
  Dockerfile enforcement, exact base/candidate image measurement, and installed qualification are
  complete locally. Independent review, publication, and hosted measurement remain.

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
- Hosted target: after one exact merge publishes the `main` cache, a subsequent PR completes image
  build in at most 75 seconds and reduces overall run time at least 25% while the full installed
  qualification still passes. A cache-miss source build must also pass.

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This workflow branch
  contains none of its product implementation and does not change `.align-revision`.
- Do not modify, rerun, push, merge, or use PR #69 as workflow evidence until the user identifies
  the final Align commit. Closed PRs #64 and #67 remain unmergeable evidence only.

## Next steps

1. Run the final development-preflight/static checks, then perform the required independent
   adversarial review and one consolidated repair if needed.
2. Publish the capability, record hosted cache/build/qualification evidence, and merge only when
   checks and review dispositions are complete.
3. Continue with Align-style apt/LLVM archive caching for the normal hosted job after merge; because
   that workflow-only capability leaves the Dockerfile unchanged, it is also the first clean warm
   consumer measurement for this image cache. A multi-stage builder/runtime image follows. Keep
   PR #69 paused until the final Align revision is named.

## Latest durable evidence

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-development-preflight`: PASS after the materializer
  implementation. It now covers true hardlinks, file and directory aliases, preserved bytes and
  modes, dangling links, directory cycles, unsupported types, an existing target, injected link
  failure, Dockerfile ownership, and the existing workflow matrix.
- Complete installed qualification against `/tmp/align` and the candidate image: PASS. On the final
  candidate invocation the installed profile took 191.372 seconds, including a 2.749-second fully
  warm image build and a 102.098-second worker aggregate. An immediately preceding uninstrumented
  invocation reached the aggregate but returned the existing `ERROR CHILD aggregate`; a diagnostic
  reproduction and the final unchanged path both passed, so hosted CI must still confirm the
  aggregate rather than treating the local warm pass as sufficient.
- Python syntax parsing, `git diff --check`, and no repository bytecode: PASS at this local
  checkpoint.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional modified `HANDOFF.md` and untracked `io_copy`, plus
  the paused Request 6 worktree's untracked `prompt_model_smoke`. They are outside this branch.
- Keep source, documentation, commits, pull-request text, diagnostics, and timing fields in English.
- This branch has no intentional uncommitted artifact outside the workflow capability files.
