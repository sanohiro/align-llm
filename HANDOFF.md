# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-13)

- Branch `agent/pinned-local-align-simple-final` is based directly on `origin/main`
  `65cc212058909ce4497d6955425ef481b3a92a82` (PR #82).
- The local Align selection capability is implementation-complete. Source checkpoint
  `6a585bf273a60b6489fc76e9005b2a9f4d52346d`, oracle checkpoint
  `2eb0712fae224f5041db3a97820e7bbf474bdf2e`, and canonical baseline finalization
  `73a13bf1ccaf394ddc0f2787aa1e9c2fa4e05849` form the required direct-parent chain.
- Ordinary local commands no longer use `../align` or an ambient `alignc`. They materialize the
  commit in `.align-revision` below the developer cache and reuse it. Explicit non-empty `ALIGNC`
  and `ALIGN_REPO` remain intentional overrides.
- The earlier hardened-cache candidate at `cce161a1c9c40579062e45a8715fe35452a2a838` is abandoned and
  must not be merged. Its conditionally required final review correctly found no-replace and build
  producer identity gaps. This branch is a deliberate re-scope: the checkout is trusted mutable
  single-user development state, not a security, provenance, artifact, or hostile-concurrency
  boundary. The implementation is about 194 lines instead of the abandoned 700-line helper.
- The compatible Align pin remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`. Align main
  `71e6b40754ac40d25301529bf59f66de5698e0b1` was independently built but fails real align-llm
  HIR-to-MIR checks, so it remains intentionally unadopted until Align supplies a compatible commit.

## Contract and decisions to preserve

- `.align-revision` is the only implicit version selection. Managed checkouts live under
  `${XDG_CACHE_HOME:-$HOME/.cache}/align-llm/align/dev-v1/<revision>` unless
  `ALIGN_TOOLCHAIN_ROOT` explicitly replaces the base.
- The helper verifies exact clean `HEAD`, required release outputs, and a runnable compiler before
  warm reuse. A failed preparation removes only its own temporary directory. An invalid existing
  checkout fails visibly and is not automatically deleted or repaired.
- The first build intentionally inherits the developer's normal Cargo/Rust environment. Changing
  those inputs requires deleting the named revision directory and rebuilding. Non-cooperating
  mutation of cache state is unsupported by design.
- `scripts/pre-pr --plan` is side-effect free. Executable preflight runs its named owner before the
  managed ensure phase; `--align-repo` remains the explicit active-checkout override.
- A later Align upgrade changes `.align-revision`, materializes the new revision, runs every named
  request acceptance target, and passes one final `make ci` against that same pin.

## Latest durable verification

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-align-toolchain`: PASS for pin, warm reuse, dirty
  rejection, compiler/source selection, and explicit overrides.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-development-preflight`: PASS.
- Real `d9fb5d...` `dev-v1` bootstrap: PASS in 37.423 seconds; warm ensure: PASS in 0.134 seconds;
  default managed `make check`: PASS.
- Re-recorded coding baseline at source `6a585bf...`: 2/2 passing with 2 samples, minimum 3.687
  seconds, median 3.697 seconds, and maximum 3.708 seconds.
  `scripts/check-baseline-chain` and `eval/runners/verify-baseline.py` remain to be rerun at the
  finalized head.
- `python3 scripts/check-gate-topology --self-test` and `git diff --check`: PASS before finalization.

## Paused product checkpoint

- PR #69 remains paused at `2d8e10aa66b9d46bb1c9a9f76716827f87ea6687`. This branch contains
  none of Request 6. Do not modify or use PR #69 as evidence until a compatible Align commit is
  named.

## Next steps

1. Commit this checkpoint, rerun baseline/static owners, obtain one fresh comprehensive review of
   this re-scoped candidate, and run exact-head development preflight.
2. Publish a ready pull request only after a clean review, wait for hosted/fresh-image checks, and
   merge when every required check passes.
3. After merge, refresh `main`; resume the paused product capability only when its Align dependency
   is compatible.

## Recovery and preservation

- Preserve the primary worktree `/home/hiro/prj/align-llm` with its modified `HANDOFF.md` and
  untracked `io_copy`.
- Preserve the sibling `/home/hiro/prj/align` and its active uncommitted `pkg.db` work. This branch
  does not modify or build from it.
- Do not use destructive checkout/reset or broad cleanup. Keep code, documentation, commits, pull
  request metadata, and review records in English.
