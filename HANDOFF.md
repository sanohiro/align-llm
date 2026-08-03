# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on redesign checkpoint `d4c9060` from main `32bfeba` (`Add C7 persisted-result design gate (#53)`). Current committed checkpoint is `c6b58d4`; historical design checkpoint `4eb878b` is retained and superseded.
- Active goal: re-scope the successor Linux x86_64 fresh-compiler design after the latest comprehensive audit found additional contract gaps; no dependent implementation or Align pin adoption may start.
- Complete: `c6b58d4` records the prior coherent redesign with executable runtime modes, retained source post-copy proof, retained common-Git identity, sealed fd-7 handoff guard, namespace-owned no-symlink aggregate tmpfs, C7 platform-profile synchronization, cache bounds, and validation-before-copy ordering. The current uncommitted repair adds supported Ubuntu 24.04 bwrap inherited-fd handling, retained-descriptor tool probing, complete Git hardening/private object-copy rules, `io_uring` descriptor-operation denial, and explicit `ALIGNC_CACHE=off`.
- In progress: ledger and closure-matrix consistency pass for those new trust-boundary decisions, followed by focused documentation checks and one fresh comprehensive design review.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Finish the ledger-to-prose and matrix-to-diff consistency pass, including ordinary bwrap inherited-fd behavior, retained tool probes, Git hardening/private objects, `io_uring` denial, and `ALIGNC_CACHE=off` propagation.
2. Run focused docs/static checks, commit the coherent successor design repair, and obtain one fresh comprehensive review; do not implement against `c6b58d4` until that review is clean.
3. Only after a clean reviewed design may the separate bootstrap/image and implementation slices be prepared; do not push, open, or merge without user authorization.

## Latest verification

- `git diff --check`: pending for the current uncommitted repair.
- The previous Markdown fence checks passed for `docs/align-requests.md` (86), `docs/specs/check-gate-topology.md` (52), and the prior handoff (0); rerun them after this wording pass.
- The previous targeted contract/static checks passed for the `c6b58d4` design: required Section 9 phrases, schema-2 digest and descriptor golden vectors, aggregate ordering, and the stale superseded-contract scan. The inherited-fd, Git-hardening, cache-off, and async-fd checks still need to run.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks: N/A for this documentation/specification-only draft; no executable contract has been changed.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked on a reviewed design that additionally uses bwrap's supported ordinary inherited-fd channel on the minimum image, probes only retained tool bytes, preserves all fixed Git hardening variables while using copied private objects, denies synchronous and `io_uring` descriptor replacement, and sets `ALIGNC_CACHE=off`, together with the existing runtime-mode, source post-copy, common-Git identity, fd-7 guard, no-symlink aggregate tmpfs, C7 platform-profile, cache-bound, and validation-order decisions.
- Do not consume `c6b58d4` or the current uncommitted repair as an implementation contract until the successor design is reviewed clean. Preserve the valid decisions—no pathname-only worker/compiler identity, staged `/usr/bin/env`/`/bin/sh`/loader closure, overlay publication, staged `/tools`, explicit descriptor propagation (now fds 5/6/7), private Git refs, and exact cleanup-failure bytes/status—while preserving the re-scoped design decisions above.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: the current design repair in `docs/specs/check-gate-topology.md`, `docs/align-requests.md`, and this `HANDOFF.md`; these changes are the re-scoped successor contract and must not be discarded. `docs/specs/c7-persisted-result.md` is already synchronized in `c6b58d4` and has no new edit in this repair. Main's existing uncommitted `HANDOFF.md` is intentional and must not be discarded.
