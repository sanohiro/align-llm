# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-13)

- Branch `agent/c6-lifecycle-latest-align` is based directly on `origin/main`
  `350ea497fbf14b4780ac3d0e1cf8b15c6d4f3663` (PR #83).
- Align PR #786 merged the checked-HIR `string.clone()` compatibility repair as
  `25b1201b3a4181f6a90921227596bdcb76ab715e`. `.align-revision` now selects that exact merged
  commit, and its managed release compiler/runtime materialized successfully under `dev-v1`.
- The managed compiler passes `./scripts/alignc check-per-unit src/main.align`: all 15 units pass
  with the three existing lossy-conversion/large-copy warnings.
- The active prerequisite is the full FRESH-IMAGE-REQUEST6 installed adoption profile. Its net
  implementation from paused PR #69 at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687` is now migrated
  onto current `main`; the old branch remains historical input, and none of its hosted or adoption
  results apply to this branch.
- FRESH-IMAGE, FRESH-WORKER, and FRESH-IMAGE-REQUEST6-BOUNDARY are merged. The migrated profile
  preserves current authenticated cgroup cleanup, phase tracking, multistage image construction,
  and the `25b1201b...` pin while adding the ordinary adoption dispatcher, namespace helper,
  compiler handoff, installed-profile bindings, fixtures, and owner tests.
- The installed profile is being extended as one native-platform capability for Linux `x86_64`
  and `aarch64`. The immutable Ubuntu OCI index, native Rust/Debian/ELF/loader tuple, manifest
  admission, runtime roots, controller, worker, Docker owner, and CI matrix now reject
  architecture mismatch; emulation is explicitly non-acceptance evidence.

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
- `python3 scripts/test-development-preflight`: PASS in the native Linux `aarch64` capable helper;
  `docker build --check -f image/fresh/Dockerfile .`: PASS with no warnings.
- Local `/usr/bin/make` is GNU Make 3.81, below the supported Make 4.3 floor, and cannot parse the
  repository's target-specific `override export` assignments. Use a capable profile for Make gates;
  do not weaken the Makefile for this host.
- Docker Desktop is native Linux `aarch64`. Do not run or cite an `amd64`-emulated container as
  installed-profile evidence; the native ARM owners are the local acceptance route.

## Next actions

1. Finish the native ARM product-image build and complete installed profile; repair any
   current-source failure without reusing PR #69 evidence.
2. Commit the migrated dual-native profile as the next internal C6/adoption checkpoint, then obtain
   the separate native `x86_64` CI owner alongside the native `aarch64` owner.
3. Pass the ordinary and authenticated fresh Request 6 adoption vectors with the `25b1201b...`
   compiler and one final capable `make ci`.
4. Update Request 6 lifecycle evidence, perform one comprehensive
   review, and publish the consumer-complete profile/adoption candidate.

## Recovery and preservation

- The migrated profile diff is intentional until its internal checkpoint commit; no generated
  compiler, image, cache, seed, or signing material belongs in Git.
- Preserve the paused PR #69 branch and its GitHub record until the migrated candidate supersedes it.
- Do not use destructive checkout/reset or broad cleanup. Keep code, documentation, commits, pull
  request metadata, review records, and diagnostics in English.
