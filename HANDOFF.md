# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-14)

- Branch `agent/c6-lifecycle-latest-align` is based directly on `origin/main`
  `350ea497fbf14b4780ac3d0e1cf8b15c6d4f3663` (PR #83).
- Align PR #786 merged the checked-HIR `string.clone()` compatibility repair as
  `25b1201b3a4181f6a90921227596bdcb76ab715e`. `.align-revision` now selects that exact merged
  commit, and its managed release compiler/runtime materialized successfully under `dev-v1`.
- The managed compiler passes `./scripts/alignc check-per-unit src/main.align`: all 15 units pass
  with the three existing lossy-conversion/large-copy warnings.
- The FRESH-IMAGE-REQUEST6 installed adoption profile is implemented and passes its complete local
  native ARM profile. Its net implementation from paused PR #69 at
  `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687` is migrated onto current `main`; the old branch remains
  historical input, and none of its hosted or adoption results apply to this branch.
- FRESH-IMAGE, FRESH-WORKER, and FRESH-IMAGE-REQUEST6-BOUNDARY are merged. The migrated profile
  preserves current authenticated cgroup cleanup, phase tracking, multistage image construction,
  and the `25b1201b...` pin while adding the ordinary adoption dispatcher, namespace helper,
  compiler handoff, installed-profile bindings, fixtures, and owner tests.
- The installed profile is being extended as one native-platform capability for Linux `x86_64`
  and `aarch64`. The immutable Ubuntu OCI index, native Rust/Debian/ELF/loader tuple, manifest
  admission, runtime roots, controller, worker, Docker owner, and CI matrix now reject
  architecture mismatch; emulation is explicitly non-acceptance evidence.
- Native implementation checkpoints are `00d7faaf550f` (dual-native Request 6 profile),
  `ad59e63e5cd0` (execute the focused payload after its variable-length handoff prefix), and
  `b5e485b87802` (use the image-owned Git for installed mutation fixtures). Review repair
  `b82d3b97ec83` defers ordinary result emission until cleanup, preserves the primary phase through
  cleanup failure, reserves fixed bwrap bind descriptors before tool/source identity opens, and
  gives each outer process owner a bounded deadline margin.
- The native ARM installed profile now passes image attestation, lifecycle, self-test, trust
  mutations, runtime replacements, the valid ordinary Request 6 consumer, the complete boundary
  rejection matrix, the worker aggregate, and cleanup.
- Baseline commits `db2c88d24574` and `cceaf15fdf0c` intentionally remain historical failed
  measurement evidence: the first ARM helper lacked `/usr/bin/bwrap`, so both recorded tasks were
  non-passing and remain unacceptable as baseline evidence.
- The failed chain and its first passing replacement were superseded after a later full-profile run
  exposed a separate resource bug: after roughly 8.5 GB of authenticated runtime copying, Cargo
  inherited all eight Docker CPUs and `rustc align_sema` was killed with `SIGKILL` in the 8 GB VM.
  Source `cbcde22600e7` fixes `CARGO_BUILD_JOBS=1` in both fresh compiler build paths; native ARM
  oracle `12cce0199762` records two passing samples, and finalization `be0131f85c3c` owns the matching
  canonical baseline and digest. `scripts/check-baseline-chain` passes on that exact chain.

## Contract and decisions to preserve

- `.align-revision` is the only implicit compiler selector. Ordinary commands use the managed exact
  pin; `ALIGNC` and `ALIGN_REPO` remain explicit overrides.
- ALIGN-ADOPTION is an ordered checkpoint inside the next consumer capability, not a pin-only pull
  request. Request 6 cannot advance to `ALIGN_LLM_VERIFIED` until the full installed profile,
  ordinary and authenticated-fresh acceptance vectors, and one final fresh `make ci` all pass.
- C6-LIFECYCLE remains blocked from product implementation on Align Requests 7, 8, 10, 12, and 13,
  which are still `PROPOSED`. Do not consume or imitate those APIs. The Request 6 profile is safe
  independent prerequisite work while those consumer cells remain blocked.
- Preserve the exact fresh-image trust, descriptor, namespace, cgroup, source-identity, and cleanup
  boundaries in `docs/specs/check-gate-topology.md`. Reclassify and update its closure matrix if the
  migrated diff changes those contracts.

## Latest durable verification

- Align `cargo build --release --workspace` at #786 final source: PASS.
- Align focused owner
  `scripts/cargo.sh test -p align_driver --test m5 owned_string_clone_duplicates_locals_and_fields -- --exact`:
  PASS.
- Align #786 preflight: PASS (owner, lint ratchet, 16-binary bounded gate, Clippy); all required
  hosted checks passed before merge.
- `scripts/align-toolchain ensure compiler` for `25b1201b...`: PASS; managed compiler path is
  `~/.cache/align-llm/align/dev-v1/25b1201b.../target/release/alignc`.
- `./scripts/alignc check-per-unit src/main.align`: PASS, 15 units.
- Latest pinned compiler Request 6 matrix: four owned-row fixtures reject with the exact Copy-row
  diagnostic; `copy-row.align`, `decode-owned.align`, and `decode-owned-option.align` run with the
  exact expected output.
- `python3 scripts/run-fresh-focused-adoption-smoke`: PASS in Linux; `./scripts/check-format`, Python
  syntax parsing, the FRESH-WORKER qualification inventory, and the migrated ordinary cgroup cleanup
  unit cases: PASS.
- Native Linux `aarch64` focused evidence on Docker Desktop: `run-fresh-image-control-smoke`,
  `run-fresh-worker-unit-smoke`, and the complete `run-fresh-worker-qualification` all PASS. The
  ARM run exposed a same-size post-copy mutation whose filesystem timestamps did not change; the
  worker now re-digests the retained source after materialization and the existing regression passes.
- Native Linux `aarch64` installed profile through `boundary-profile`: PASS. This run exposed and
  repaired the focused-row prefix slicing and bare-Git fixture setup bugs; the focused adoption
  owner passes after both repairs. Warm signed-image builds reuse the architecture/toolchain layers,
  reducing the observed image-build phase from 1,065,794 ms to roughly 20-31 seconds.
- Native ARM diagnostics reproduced ordinary `align-build-only` as Cargo exit 101 and captured the
  exact failing child: `rustc align_sema` exited on `SIGKILL` after the authenticated runtime copy.
  The same pinned compiler builds natively in about 40 seconds when the runtime is bound without
  the preceding copy pressure; compiler/archive type, mode, size, and Cargo hard-link identity are
  valid. Fixed single-job Cargo contract and fresh-worker unit owners: PASS. The repaired native
  ARM ordinary adoption completed with canonical PASS in 225,474 ms, followed by cleanup PASS.
- Native ARM baseline source `cbcde22600e7`, oracle `12cce0199762`, and finalization
  `be0131f85c3c`: PASS. Both deterministic-reference samples pass under native `aarch64` bubblewrap;
  time to passing patch is 135,683,334-174,716,542 ns with median 155,199,938 ns. The canonical
  digest and baseline chain pass.
- `python3 scripts/run-fresh-image-profile-smoke --require-docker --align-repo
  <clean-pinned-Align-checkout>` at `be0131f85c3c`: PASS on native Linux `aarch64`. Boundary profile
  passed in 282,213 ms, worker aggregate in 190,201 ms, and cleanup in 3,345 ms.
- Comprehensive `codex review --base origin/main` reviewed `dae654a` against base tip and merge base
  `350ea497fbf1`. It found three valid ordinary-lifecycle defects: success could be emitted before
  outer cleanup, cgroup cleanup could replace an active build/fixture phase, and equal nested
  deadlines let an outer owner preempt inner cleanup. `b82d3b97ec83` repairs all three; the newly
  visible cleanup failure additionally exposed and repaired fixed bind-FD collision with retained
  Git/tool descriptors. The repair stayed within the reviewed ordinary lifecycle and timeout
  contract, and its focused delta was inspected without triggering another comprehensive review.
- `python3 scripts/run-fresh-image-profile-smoke --require-docker --align-repo
  <clean-pinned-Align-checkout>` at `b82d3b97ec83`: PASS on native Linux `aarch64` after the review
  repair. Image build passed in 23,143 ms, boundary profile in 257,071 ms, worker aggregate in
  174,881 ms, and cleanup in 3,983 ms. Success is now emitted only after the worker-owned root,
  source views, tools, bind placeholders, and cgroup are cleaned.
- The first ARM baseline recorder invocation completed but produced two FAIL samples solely because
  its helper did not install `/usr/bin/bwrap`; schema inspection rejected it as canonical evidence.
- `python3 scripts/test-development-preflight`: PASS in the native Linux `aarch64` capable helper;
  `docker build --check -f image/fresh/Dockerfile .`: PASS with no warnings.
- Local `/usr/bin/make` is GNU Make 3.81, below the supported Make 4.3 floor, and cannot parse the
  repository's target-specific `override export` assignments. Use a capable profile for Make gates;
  do not weaken the Makefile for this host.
- Docker Desktop is native Linux `aarch64`. Do not run or cite an `amd64`-emulated container as
  installed-profile evidence; the native ARM owners are the local acceptance route.

## Next actions

1. Obtain the separate native `x86_64` CI owner alongside the native `aarch64` owner, then pass one
   final capable `make ci` with the `25b1201b...` compiler.
2. Publish the consumer-complete profile/adoption candidate with the reviewed-head envelope, all
   three finding dispositions, repair commit `b82d3b97ec83`, and exact final verification evidence.

## Recovery and preservation

- The failed non-passing baseline chain is superseded evidence, not an accepted checkpoint. Preserve
  its commits in history and replace it through the required source -> oracle -> finalization chain;
  do not amend or rewrite it.
- No generated compiler, image, cache, seed, or signing material belongs in Git.
- Preserve the paused PR #69 branch and its GitHub record until the migrated candidate supersedes it.
- Do not use destructive checkout/reset or broad cleanup. Keep code, documentation, commits, pull
  request metadata, review records, and diagnostics in English.
