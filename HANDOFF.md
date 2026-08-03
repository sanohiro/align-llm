# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on redesign checkpoint `d4c9060` from main `32bfeba` (`Add C7 persisted-result design gate (#53)`). Current committed checkpoint is `6b5dfaa`; historical design checkpoint `4eb878b` is retained and superseded.
- Active goal: re-scope the successor Linux x86_64 fresh-compiler design after the latest comprehensive audit found additional contract gaps; no dependent implementation or Align pin adoption may start.
- Complete: `c6b58d4` records the prior coherent redesign with executable runtime modes, retained source post-copy proof, retained common-Git identity, sealed fd-7 handoff guard, namespace-owned no-symlink aggregate tmpfs, C7 platform-profile synchronization, cache bounds, and validation-before-copy ordering. `6b5dfaa` adds supported Ubuntu 24.04 bwrap inherited-fd handling, retained-descriptor tool probing, complete Git hardening/private object-copy rules, `io_uring` descriptor-operation denial, and explicit `ALIGNC_CACHE=off`.
- In progress: one fresh comprehensive design review of the committed successor contract.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Run one fresh comprehensive design review of `6b5dfaa`; do not implement against it until that review is clean.
3. Only after a clean reviewed design may the separate bootstrap/image and implementation slices be prepared; do not push, open, or merge without user authorization.

## Latest verification

- `git diff --check`: passed before `6b5dfaa`.
- Markdown fence checks passed for `HANDOFF.md` (0), `docs/align-requests.md` (86), `docs/specs/c7-persisted-result.md` (16), and `docs/specs/check-gate-topology.md` (52).
- Targeted contract checks passed: schema-2 manifest and descriptor JSON vectors parse, Section 9 contains no `--preserve-fd` command, inherited-fd propagation and `ALIGNC_CACHE=off` are present, aggregate bind/tmpfs ordering is correct, Git hardening/private-object rules and `io_uring` denial are recorded, and the local bubblewrap inherited-fd self-test passed.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks: N/A for this documentation/specification-only draft; no executable contract has been changed.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked on a reviewed design that additionally uses bwrap's supported ordinary inherited-fd channel on the minimum image, probes only retained tool bytes, preserves all fixed Git hardening variables while using copied private objects, denies synchronous and `io_uring` descriptor replacement, and sets `ALIGNC_CACHE=off`, together with the existing runtime-mode, source post-copy, common-Git identity, fd-7 guard, no-symlink aggregate tmpfs, C7 platform-profile, cache-bound, and validation-order decisions.
- Do not consume `6b5dfaa` as an implementation contract until the successor design is reviewed clean. Preserve the valid decisions—no pathname-only worker/compiler identity, staged `/usr/bin/env`/`/bin/sh`/loader closure, overlay publication, staged `/tools`, explicit descriptor propagation (now fds 5/6/7), private Git refs, and exact cleanup-failure bytes/status—while preserving the re-scoped design decisions above.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none in this worktree. Main's existing uncommitted `HANDOFF.md` is intentional and must not be discarded.
