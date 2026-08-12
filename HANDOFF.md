# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-13)

- Branch `agent/cache-cargo-fetch-layout` is based on PR #78 merge commit
  `dea213d69e79fc6c3ef97ad095051b8c4c2dce1a`.
- Active goal: keep the pin-owned Cargo dependency fetch reusable when only fresh-image controller,
  worker, profile, manifest, or self-test inputs change.
- Complete: PR #71 merged proportional development rules. PR #72 merged exact merged-PR check
  reuse; merge-push run `31570429008` completed in 11 seconds versus the 492-second baseline
  (97.8% lower). PR #73 merged shared fresh-image layers and main run `31578101828` published the
  trusted cache while reusing functional checks and skipping image load and qualification. PR #74
  merged the complete Node 24 action migration at `d433e4d66a180e077cb667edcc3ff6050a3f0542`.
  PR #75 merged hardlink-preserving runtime materialization at `530da31d74b9ef79a7cfc2efafbeaee5c927ef4f`.
  PR #76 merged and seeded the verified hosted LLVM archive cache at `c3deab753a3db4e963817917c1105fe110907a99`.
  PR #77 merged the trusted hosted Align compiler bundle at
  `6a48ab797b5c1069342643ef281f7d7fdb2a9b26`; its exact-main seed and clean warm run passed. PR #78
  merged the multi-stage fresh runtime at `dea213d69e79fc6c3ef97ad095051b8c4c2dce1a`, reducing the
  observed image from 6,069,945,116 to 3,215,474,083 bytes (47.0%) while preserving the complete
  installed profile. Its PR run `31633149090` passed; the fresh job's build/export/load took 294
  seconds and installed qualification took 262 seconds. Exact-main trusted-cache publication is in
  progress in run `31634023665`.
- In progress: settle and implement the Docker cache boundary that copies only `.align-revision`
  and completes the exact shallow Cargo fetch after the pinned Git/Rust runtimes but before any
  repository-owned fresh-image source. The public contract and closure owner must be updated before
  the Dockerfile move; the owner regression must prove both sides of that ordering. No runtime,
  manifest, network-source, or installed-image behavior changes.

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
- PR #77 run `31603728854`, exact-main seed run `31604427226`, and clean same-commit warm run
  `31604614372` passed. The warm hosted check job took 28 seconds, including one second to restore
  and one second to verify the bundle; apt, Rust, Align checkout/build, and publication were skipped.
  This is 72% lower than the 100-second bundle baseline. The same warm run's fresh-image job still
  took 430 seconds, including 165 seconds to build/export/load and 222 seconds for installed
  qualification, making image transfer and qualification the remaining workflow bottleneck.
- The rejected first multi-stage candidate was 3,800,869,143 bytes. The rejected hand-pruned repair
  was 3,200,170,355 bytes but retained cryptsetup libraries despite claiming their absence. The
  re-scoped, unpruned image is 3,215,474,083 bytes versus the image-ID-bound 6,069,945,116-byte
  baseline, a 47.0% reduction; `/runtime` is 3,016,219,340 bytes and the Cargo cache 23,056,659
  bytes. Both images share exact Ubuntu base rootfs layer `42724e4`; future apt content remains
  mutable, so exact sizes are recorded observations rather than rebuild guarantees. All 1,303
  transferred Python/libexpat paths had zero dpkg ownership collisions and builder-only Rustup,
  Cargo, LLVM, source, and apt state are absent.

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This workflow branch
  contains none of its product implementation and does not change `.align-revision`.
- Do not modify, rerun, push, merge, or use PR #69 as workflow evidence until the user identifies
  the final Align commit. Closed PRs #64 and #67 remain unmergeable evidence only.

## Next steps

1. Finish PR #78's exact-main cache publication and record its step durations.
2. Commit the Cargo-fetch cache-boundary contract, then move the pin-only layer and add the exact
   Dockerfile ordering regression.
3. Run the proportional owner and installed acceptance, obtain one fresh comprehensive review, and
   publish the consumer-complete cache-layout capability. Keep PR #69 paused until the final Align
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
- Complete preflight at implementation checkpoint `8872b17`: bundle/development owner 8.294s,
  pinned Align build 15.333s, hosted graph 3.059s, focused qualification 20.428s, and installed
  profile 207.512s. Complete preflight also passed reviewed head `5d53224`: owner 8.523s, pinned
  Align build 0.602s, hosted graph 3.081s, focused qualification 20.277s, and installed profile
  198.491s. Complete preflight passed consolidated repair `a8fb07d`: owner 8.742s, pinned Align
  build 0.604s, hosted graph 3.066s, focused qualification 20.260s, and installed profile 195.803s.
- PR #77's clean warm run `31604614372` passed at merge head
  `6a48ab797b5c1069342643ef281f7d7fdb2a9b26`: hosted bundle restore plus verification took two
  seconds and the complete hosted job took 28 seconds. The full run passed in 434 seconds because
  the unchanged fresh-image job remained dominant.
- Multi-stage implementation head `060b956` passed `scripts/test-development-preflight`, Dockerfile
  build checks, complete focused fresh qualification in 20.305 seconds, and `make hosted-checks`.
  The candidate installed profile passed every phase through both boundaries, then failed worker
  aggregate. An exact `origin/main` control under the same refreshed `--pull` environment failed
  the same aggregate phase. Both used the exact clean full-history Align revision
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; only refreshed systemd library files differed from
  the earlier passing manifest. Hosted complete-profile evidence remains required.
- Initial comprehensive review covered exact head `4780747aa67b7b4dca12544cca5274849181ef49`
  against base and merge base `6a48ab797b5c1069342643ef281f7d7fdb2a9b26` and requested the
  three changes described above. The consolidated repair's static development owner, Dockerfile
  build check, fixed-base image build, footprint inventory, package-ownership intersection, and
  unreachable-library inventory pass. Intermediate installed probes correctly used the committed
  pre-repair worker and therefore are diagnostic only. The first committed repair installed profile
  passed once, then reproduced the end-of-aggregate race; a temporary diagnostic head identified
  `CleanupError('owned child process tree remained')`. The bounded-drain owner regression passes.
  After removing all temporary child-output diagnostics, complete preflight passed repair checkpoint
  `fde4fad7f1d8dc7f93d6a0a8182131125a76b54f`: development owner 9.107s, pinned Align build 0.608s,
  hosted graph 3.152s, focused qualification 20.452s, installed profile 204.412s, image build 2.200s,
  boundary profile 38.314s, and worker aggregate 107.594s. A separate installed-only repetition also
  passed in 205.722s with a 108.711s aggregate. Complete preflight also passed exact final-review
  head `d3d39325e4e4ce8677eb356396482377a592961a` and wrote its external stamp: installed profile
  204.661s and worker aggregate 107.242s. The final reviewer incorrectly reported this stamp absent;
  that finding is rejected by the existing stamp file. Its four remaining findings are accepted:
  retained `libcryptsetup.so.12*`, a stale measurement tag, stale validation precedence, and
  contradictory cleanup prose. Repository policy ended that repair cycle and required this redesign.
- Re-scoped image `sha256:eb9162ba3d17494b41673635166dfd6eb23457bebfd9fd24e558049852024152`
  passed its final-stage build checks and inventory probes. It is 3,215,474,083 bytes; `/runtime` is
  3,016,219,340 bytes; Cargo cache is 23,056,659 bytes; its first rootfs layer matches the baseline;
  all named builder roots and apt lists are absent; and retained cryptsetup libraries demonstrate
  that this capability preserves rather than hand-prunes the manifest-bound runtime tree.
- Complete preflight passed re-scoped measurement checkpoint
  `791c9d5c518b7301bf5fa6ee19e76892fc637c53`: development owner 9.514s, pinned Align build 0.799s,
  hosted graph 3.633s, focused qualification 22.223s, installed profile 217.113s, image build 3.202s,
  boundary profile 41.554s, worker aggregate 105.110s, and cleanup 1.192s. Complete preflight also
  passed exact comprehensive-review head `bc2623b613b5ba4ed60b2484da7933f13465aec5`: installed
  profile 200.836s and worker aggregate 104.604s. Its canonical mode-0600 external stamp records
  exact base `6a48ab7`, head, owner `development-preflight`, and `fresh-image` scope.
- The redesigned comprehensive review covered exact head
  `bc2623b613b5ba4ed60b2484da7933f13465aec5` against base and merge base
  `6a48ab797b5c1069342643ef281f7d7fdb2a9b26` and requested the three changes described above.
  The consolidated repair `957aa5096d3980d183c92499ed9f1e870492ee7d` passed worker unit,
  image-control, development-preflight, topology self-test, and complete preflight: development
  owner 8.976s, pinned Align build 0.728s, hosted graph 3.351s, focused qualification 20.591s,
  installed profile 244.307s, image build 36.545s, boundary profile 39.255s, worker aggregate
  105.608s, and cleanup 1.211s. The apt, LLVM, Git, Rust toolchain, materialization, runtime, tool,
  Cargo-cache, and transferred system-file layers were cache hits; only the changed control closure
  and downstream random-attestation layers rebuilt.
- Exact evidence head `7040d75eef941900cf49151fb5651309eb8ae9f6` also passed complete
  preflight and has a canonical mode-0600 stamp for base `6a48ab7`, owner
  `development-preflight`, and `fresh-image` scope: development owner 9.063s, pinned Align build
  0.609s, hosted graph 3.141s, focused qualification 20.406s, installed profile 204.156s, warm image
  build 2.147s, boundary profile 37.494s, worker aggregate 108.061s, and cleanup 1.252s. The
  policy-mandated conditional final review nevertheless requested changes: controller forced-kill
  success propagation and descendant-zombie reap were incomplete, controller multi-invalid
  precedence had only static coverage, and the handoff next action was stale. No v2 content may be
  published; v3 must be reviewed as a redesigned candidate.
- V3 design checkpoint `021f8e0` passed `git diff --check`. The coherent implementation candidate
  passed `run-fresh-image-control-smoke`, `run-fresh-worker-unit-smoke`,
  `test-development-preflight`, Python AST parsing, and complete focused
  `run-fresh-worker-qualification` in 22.925s. The controller owner executes a real double-forked,
  session-breaking, TERM-ignoring descendant: the zero-exit direct child cannot produce success,
  production termination selects the authenticated cgroup kill boundary, and the subreaper proves
  `ECHILD`; its natural-drain control sends no kill. Complete preflight passed implementation
  checkpoint `e5dae9097f3447524e2dfb901d8a49d678cb8509`: development owner 9.126s, pinned
  Align build 0.752s, hosted graph 3.266s, focused qualification 22.113s, installed profile
  253.535s, image build 41.411s, boundary profile 40.867s, worker aggregate 106.299s, and cleanup
  1.217s. Apt, LLVM, Git, Rust toolchain, materialization, runtime, tool, Cargo-cache, and transferred
  system-file layers were cache hits; the changed controller and downstream attestation layers
  rebuilt. Its canonical external stamp records exact base `6a48ab7`, head, owner
  `development-preflight`, and `fresh-image` scope.
- Fresh comprehensive review covered exact head
  `236dcbdca1f10e1b04eccebb2be806ed59754037` against base and merge base
  `6a48ab797b5c1069342643ef281f7d7fdb2a9b26` and requested two changes: the public supervisor ran
  project Git before controller runtime/tool admission, and the worker's claimed double-fork
  acceptance remained synthetic. Both findings are accepted; the contract above defines their one
  consolidated repair.
- Consolidated repair `9996837` makes full controller runtime/tool admission precede public project
  Git, reopens the exact runtime-tree Git node into a retained descriptor while preserving its 142
  intentional hardlinks, explicitly preserves FD 4 across bootstrap exec even when it was allocated
  directly, and adds a real worker `run_owned` double-fork lifecycle regression. Image-control,
  worker-unit, development-preflight, topology, and focused qualification owners pass. Installed-only
  qualification passes in 265.057s: image build 34.354s, profile self-test 15.435s, trust mutations
  16.363s, runtime replacements 23.597s, boundary profile 39.724s, worker aggregate 124.136s, and
  cleanup 1.231s. Apt, LLVM, Git, Rust toolchain, runtime materialization, and transferred runtime
  layers were cache hits. A controller-only change still invalidates the later Cargo-fetch layer
  because its Dockerfile `COPY image/fresh` precedes that fetch; moving the pin-owned Cargo fetch
  before controller inputs is the next cache-layout optimization after this capability.
- Complete preflight passed exact evidence head
  `be49ca494f42ae4aed0eba3e9de36c86118c91f5`: development owner 9.980s, pinned Align build
  0.689s, hosted graph 3.778s, focused qualification 29.248s, installed profile 259.501s, warm image
  build 2.707s, profile self-test 17.667s, trust mutations 16.968s, runtime replacements 29.361s,
  boundary profile 43.354s, worker aggregate 138.205s, and cleanup 1.336s. The canonical external
  stamp records exact base `6a48ab7`, head, owner `development-preflight`, and `fresh-image` scope.
- Complete preflight passed v3 final evidence head
  `1ce0b197adddf36a474a32d3cb90aeea3d23a746`: development owner 10.161s, pinned Align build
  0.722s, hosted graph 3.728s, focused qualification 24.122s, installed profile 230.258s, warm image
  build 3.407s, profile self-test 13.174s, trust mutations 15.942s, runtime replacements 24.976s,
  boundary profile 39.716s, worker aggregate 123.048s, and cleanup 1.290s. Its mode-0600 stamp binds
  exact base `6a48ab7`, head, owner `development-preflight`, and `fresh-image` scope.
- The conditionally required v3 final review covered exact head `1ce0b19` against base and merge
  base `6a48ab7` and requested the two contract corrections described in the active checkpoint.
  Both are accepted. No v3 content may be published; v4 is a redesigned candidate and requires one
  fresh comprehensive review after its own final evidence.
- V4 design checkpoint `fcbd8e8` passed `git diff --check`. Contract-owner checkpoint `05bbfd7`
  passed `run-fresh-image-control-smoke`, `run-fresh-worker-unit-smoke`,
  `test-development-preflight`, `check-gate-topology --self-test`, and complete focused
  `run-fresh-worker-qualification` in 25.040s.
- Complete preflight passed v4 implementation evidence head
  `b9b7189c34608fc1fff3b88ba81a504c46eed980`: development owner 9.550s, pinned Align build
  0.768s, hosted graph 3.392s, focused qualification 23.105s, and installed profile 238.407s. The
  cached image build took 3.862s, profile self-test 19.794s, trust mutations 15.542s, runtime
  replacements 24.492s, boundary profile 40.994s, worker aggregate 122.324s, and cleanup 1.267s.
  Apt, LLVM, Git, Rust, Cargo, runtime materialization, and transferred runtime layers were cache
  hits. Its mode-0600 stamp binds exact base `6a48ab7`, head, owner `development-preflight`, and
  `fresh-image` scope.
- Complete preflight also passed exact v4 review head
  `53eb915c45521a8f73d255d3a55cf4467a4c64c1`: development owner 9.710s, pinned Align build
  0.635s, hosted graph 3.375s, focused qualification 23.194s, and installed profile 228.348s. The
  cached image build took 2.148s, profile self-test 13.332s, trust mutations 15.621s, runtime
  replacements 25.440s, boundary profile 37.777s, worker aggregate 124.098s, and cleanup 1.286s.
  The mode-0600 external stamp binds exact base `6a48ab7`, head, owner `development-preflight`, and
  `fresh-image` scope.
- Fresh comprehensive review covered exact head `53eb915` against base and merge base `6a48ab7`.
  Its verdict was changes requested with the four complete findings and accepted dispositions in
  the active checkpoint. The v4-specific runtime-before-invalid-bwrap rule, controller leaf
  grammar, and phase-owned Git/tool/bwrap mappings passed review; the reviewer also reconfirmed the
  `eb9162ba...` image identity, footprint, runtime/Cargo sizes, and absent builder roots/apt lists.

## Constraints and intentional state

- Do not modify the sibling Align source, its active worktree, or the paused Request 6 branch.
- Preserve the primary worktree's intentional modified `HANDOFF.md` and untracked `io_copy`, plus
  the paused Request 6 worktree's untracked `prompt_model_smoke`. They are outside this branch.
- Keep source, documentation, commits, pull-request text, diagnostics, and timing fields in English.
- This branch has no intentional uncommitted artifact outside the workflow capability files.
