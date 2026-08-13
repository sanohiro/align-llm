# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-13)

- Branch `agent/pinned-local-align-ready` is based directly on `origin/main`
  `65cc212058909ce4497d6955425ef481b3a92a82` (PR #82).
- The local Align selection capability is complete. Source checkpoint
  `814c7160820c7b4fda0741e7a17b10ff0713d915`, oracle checkpoint
  `1fb389319f5be3cee4b068bbf05022d576d61063`, and canonical baseline finalization
  `031e7aa5ad7e14c0aad30d70bc2cc954ad0d5375` form the required direct-parent chain.
- Ordinary commands no longer use `../align` or ambient `alignc`. They materialize `.align-revision`
  under the Git-untracked developer cache and reuse it. Non-empty `ALIGNC` and `ALIGN_REPO` remain
  explicit overrides; toolchain paths/commands containing whitespace are rejected.
- The abandoned hardened-cache head `cce161a1c9c40579062e45a8715fe35452a2a838` must not merge. Its
  final review found no-replace and producer-identity gaps. This replacement intentionally treats
  the checkout as trusted mutable single-user state, not a security, provenance, artifact, or
  hostile-concurrency boundary, and reduces the helper from about 700 to about 200 lines.
- One fresh comprehensive review covered the re-scoped candidate at `2462428e...` and requested five
  changes. Consolidated source checkpoint `814c716...` closes them: cleanup failure is observable;
  cooperative overlap and failed build/output/probe cases are owner-tested; whitespace paths fail
  at the boundary; docs-only preflight skips toolchain resolution; mutable-cache wording and this
  checkpoint are current. These are recorded-finding repairs and do not trigger another review.
- The compatible Align pin remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`. Align main
  `71e6b40754ac40d25301529bf59f66de5698e0b1` fails real align-llm HIR-to-MIR checks and remains
  intentionally unadopted until Align supplies a compatible commit.

## Contract and decisions to preserve

- `.align-revision` is the only implicit version selector. Checkouts live below
  `${XDG_CACHE_HOME:-$HOME/.cache}/align-llm/align/dev-v1/<revision>` unless the absolute
  whitespace-free `ALIGN_TOOLCHAIN_ROOT` replaces the base.
- Warm reuse requires exact clean `HEAD`, both release outputs, and a runnable compiler. Invalid
  existing state fails visibly and is not automatically deleted or repaired.
- The first build intentionally inherits the developer's ordinary Cargo/Rust environment. Changing
  it requires deleting the named revision directory before rebuilding. Non-cooperating cache
  mutation is unsupported by design.
- Executable preflight constructs its plan without mutation and runs its owner before managed
  ensure. Documentation-only preflight never resolves Align. `--align-repo` is the explicit active
  checkout override.
- A later Align upgrade changes `.align-revision`, materializes it, runs all named request acceptance
  targets, and passes one final `make ci` against that same pin.

## Latest durable verification

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-align-toolchain`: PASS, including cooperative
  one-build reuse, dirty/output/probe rejection, build/output/probe failure cleanup, whitespace
  rejection, and explicit/default selection.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-development-preflight`: PASS.
- Real `d9fb5d...` `dev-v1` bootstrap: PASS in 37.423 seconds; warm ensure: PASS in 0.134 seconds;
  default managed `make check`: PASS.
- Re-recorded coding baseline at source `814c716...`: 2/2 passing, 2 samples, minimum 3.790 seconds,
  median 3.806 seconds, maximum 3.821 seconds.
- Baseline-chain/verifier, topology self-test, diff-check, and exact-head development preflight must
  be run once after this handoff commit. The exact-head stamp is transient and stays outside Git.

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This branch contains
  none of Request 6. Do not modify or use PR #69 as evidence until a compatible Align commit is
  named.

## Next steps

1. Commit this checkpoint, run final static owners and exact-head development preflight.
2. Publish a ready pull request with the complete review envelope and five finding dispositions,
   wait for hosted/fresh-image checks, and merge when all required checks pass.
3. After merge, refresh `main`; resume the paused product capability only when its Align dependency
   is compatible.

## Recovery and preservation

- Preserve `/home/hiro/prj/align-llm` with its modified `HANDOFF.md` and untracked `io_copy`.
- Preserve `/home/hiro/prj/align` and its active uncommitted `pkg.db` work. This branch neither
  modifies nor builds from it.
- Do not use destructive checkout/reset or broad cleanup. Keep code, documentation, commits, pull
  request metadata, and review records in English.
