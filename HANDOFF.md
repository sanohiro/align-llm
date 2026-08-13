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
- The active prerequisite is the full FRESH-IMAGE-REQUEST6 installed adoption profile. Its earlier
  implementation remains on paused PR #69 at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`, based on an
  obsolete tree and compiler. Treat that branch only as migration input; none of its old hosted or
  adoption results apply to this branch.
- FRESH-IMAGE, FRESH-WORKER, and FRESH-IMAGE-REQUEST6-BOUNDARY are merged. The compatible compiler
  now satisfies the blocker that paused the full profile, so migrate its net behavior onto current
  `main`, preserve the new pin, and rerun every owner from current source.

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
- Local `/usr/bin/make` is GNU Make 3.81, below the supported Make 4.3 floor, and cannot parse the
  repository's target-specific `override export` assignments. Use a capable profile for Make gates;
  do not weaken the Makefile for this host.

## Next actions

1. Commit the latest Align pin and this durable checkpoint as the first internal C6/adoption commit.
2. Audit and migrate the paused PR #69 net profile onto current `main`; remove obsolete diagnostics
   and retain only behavior required by the current Section 9 contract.
3. Run the narrow profile/control/worker owners, then the ordinary and authenticated fresh Request 6
   adoption vectors with the `25b1201b...` compiler.
4. Update Request 6 lifecycle evidence, run one final capable `make ci`, perform one comprehensive
   review, and publish the consumer-complete profile/adoption candidate.

## Recovery and preservation

- The intentional uncommitted files before the first checkpoint commit are `.align-revision` and
  `HANDOFF.md`.
- Preserve the paused PR #69 branch and its GitHub record until the migrated candidate supersedes it.
- Do not use destructive checkout/reset or broad cleanup. Keep code, documentation, commits, pull
  request metadata, review records, and diagnostics in English.
