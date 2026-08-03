# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on redesign checkpoint `d4c9060` from main `32bfeba` (`Add C7 persisted-result design gate (#53)`). Historical design checkpoint `4eb878b` is retained and superseded.
- Active goal: complete the successor Linux x86_64 fresh-compiler design before any dependent implementation or Align pin adoption.
- Complete: Section 9 of `docs/specs/check-gate-topology.md` now defines sealed worker/compiler snapshots, schema-2 manifest and descriptor wires, recursive digest identity, staged loader/interpreter closure, two empty-root namespaces, source/cache boundaries, fd-based interposition, cleanup status, and the reopened closure matrix.
- In progress: author-side ledger-to-prose and closure-matrix consistency audit before the fresh independent design review.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Finish the author-side consistency audit, including exact aggregate workspace output paths and all current script temporary-file call sites.
2. Commit the coherent design slice and run one fresh independent comprehensive review against main; apply no implementation changes before that review completes.
3. If the design review is clean, prepare the separate bootstrap/image and implementation slices; do not push, open, or merge without user authorization.

## Latest verification

- `git diff --check`: passed for the current redesign draft.
- Markdown fence checks: passed for `docs/align-requests.md` (86) and `docs/specs/check-gate-topology.md` (52); the branch handoff fence count is 0.
- The prior conditional final review of `4eb878b` found 6 P1 and 6 P2 findings; Section 9 is the redesign response and has not yet received its own review.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks: N/A for this documentation/specification-only draft; no executable contract has been changed.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice requires an externally installed fixed bootstrap, authenticated schema-2 manifest, closed executable inventory, private Cargo cache, two bwrap namespaces, sealed fd handoff, and identity-bound C0 baseline refresh.
- The author audit must preserve the redesign decisions: no pathname-only worker or compiler identity, staged `/usr/bin/env`/`/bin/sh`/loader closure, read-only workspace plus explicit `/workspace/main` output mount, writable owner-only staging directories, external cache manifest, and exact cleanup-failure bytes/status.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none on this design branch. Main's existing uncommitted `HANDOFF.md` is intentional and must not be discarded.
