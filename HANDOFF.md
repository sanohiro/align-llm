# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on redesign checkpoint `d4c9060` from main `32bfeba` (`Add C7 persisted-result design gate (#53)`). Current committed checkpoint is `6b5dfaa`; historical design checkpoint `4eb878b` is retained and superseded.
- Active goal: re-scope the successor Linux x86_64 fresh-compiler design after the latest comprehensive audit found five P1 and three P2 contract gaps; no dependent implementation or Align pin adoption may start.
- Complete: `c6b58d4` records the prior coherent redesign with executable runtime modes, retained source post-copy proof, retained common-Git identity, sealed fd-7 handoff guard, namespace-owned no-symlink aggregate tmpfs, C7 platform-profile synchronization, cache bounds, and validation-before-copy ordering. `6b5dfaa` adds supported Ubuntu 24.04 bwrap inherited-fd handling, retained-descriptor tool probing, complete Git hardening/private object-copy rules, `io_uring` descriptor-operation denial, and explicit `ALIGNC_CACHE=off`. The fresh review of `6b5dfaa` then identified bwrap pre-authentication, root `main` output, source-mode normalization, Python runtime closure, utility inventory, descriptor staging-path, no-symlink scope, and Cargo-cache writability gaps; these are now being re-designed together.
- In progress: re-open the Section 9 manifest/source/runtime ledgers and closure matrix, apply one coherent design re-scope, and run focused documentation checks before a new comprehensive review.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Complete the coherent Section 9 re-scope for the five P1 and three P2 findings, including the manifest, source-mode, Python/utility closure, descriptor, mount, and Cargo-cache updates.
2. Run focused documentation and contract checks, commit the design checkpoint, then run one fresh comprehensive review; do not implement against it until that review is clean.
3. Only after a clean reviewed design may the separate bootstrap/image and implementation slices be prepared; do not push, open, or merge without user authorization.

## Latest verification

- `git diff --check`: passed after the current re-scope.
- Markdown fence checks passed for `HANDOFF.md` (0), `docs/align-requests.md` (86), `docs/specs/c7-persisted-result.md` (16), and `docs/specs/check-gate-topology.md` (52).
- Targeted contract checks passed after the current re-scope: all Section 9 JSON vectors parse; no actual Section 9 bwrap command uses `--preserve-fd`; inherited-fd propagation, bwrap pre-probe authentication, root `main` exception, raw/staged mode mapping, Python stdlib/extension closure, utility inventory, ordinal runtime paths, `/target/tmp`-only no-symlink mount, `/cargo` read-only binding, `ALIGNC_CACHE=off`, Git hardening/private-object rules, and `io_uring` denial are recorded and asserted. A retained-bwrap ordinary-inherited-fd identity probe passed locally. A pinned Align release build with a read-only private `CARGO_HOME` passed offline in 17 seconds; its test-only temporary directory was removed after restoring its deliberate read-only modes.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks: N/A for this documentation/specification-only draft; no executable contract has been changed.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked on a reviewed design that authenticates bwrap before capability probes, admits only the safe root `main` output exception, defines raw-to-staged source modes, stages Python standard-library/native-extension roots and the complete utility closure, aligns descriptor paths with ordinal runtime objects, applies no-symlink only to `/target/tmp`, and declares read-only `/cargo`, together with the inherited-fd, retained-tool, Git hardening/private-object, fd-denial, cache-off, runtime-mode, source post-copy, common-Git identity, fd-7 guard, aggregate overlay/tmpfs, C7 platform-profile, cache-bound, and validation-order decisions.
- Do not consume `6b5dfaa` as an implementation contract until the successor design is reviewed clean. Preserve the valid decisions—no pathname-only worker/compiler identity, staged `/usr/bin/env`/`/bin/sh`/loader closure, overlay publication, staged `/tools`, explicit descriptor propagation (now fds 5/6/7), private Git refs, and exact cleanup-failure bytes/status—while preserving the current re-scoped design decisions above.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none in this worktree. Main's existing uncommitted `HANDOFF.md` is intentional and must not be discarded.
