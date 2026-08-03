# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on redesign checkpoint `d4c9060` from main `32bfeba` (`Add C7 persisted-result design gate (#53)`). Historical design checkpoint `4eb878b` is retained and superseded.
- Active goal: complete the successor Linux x86_64 fresh-compiler design before any dependent implementation or Align pin adoption.
- Complete: Section 9 of `docs/specs/check-gate-topology.md` defines sealed worker/compiler snapshots, schema-2 manifest and descriptor wires, recursive digest identity, staged loader/interpreter closure, two namespaces, source/cache boundaries, fd-based interposition, cleanup status, and the reopened closure matrix. The first comprehensive review of `b74af55` found six unique P1 contract gaps; the working-tree repair now covers all six with an aggregate overlay upper/work pair, executable-bit preservation, nested staged-tool/fd propagation, `/target/tmp` loop markers, private baseline Git scratch, and explicit Python descriptor passing.
- In progress: author-side ledger-to-prose and closure-matrix consistency audit of the consolidated repair before the conditional final design review.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Finish the author-side consistency audit and targeted docs checks for the consolidated repair.
2. Commit the repair as one scoped design commit, then run the required conditional final review against main.
3. If the final review is clean, stop at the reviewed design checkpoint and prepare separate bootstrap/image and implementation slices; do not push, open, or merge without user authorization.

## Latest verification

- `git diff --check`: passed after the six-finding repair.
- Markdown fence checks passed for `docs/align-requests.md` (86), `docs/specs/check-gate-topology.md` (52), and this handoff (0).
- Targeted contract/static checks passed: required Section 9 phrases, schema-2 digest and descriptor golden vectors, and the stale superseded-contract scan.
- The comprehensive review of `b74af55` completed with six unique P1 findings. All six are addressed in the working tree; the conditional final review is still pending.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks: N/A for this documentation/specification-only draft; no executable contract has been changed.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice requires an externally installed fixed bootstrap, authenticated schema-2 manifest, closed executable inventory, private Cargo cache, two bwrap namespaces, a writable aggregate overlay upper/work pair for compiler atomic publication, sealed fd handoff through nested Python/bwrap processes, isolated baseline Git scratch, and identity-bound C0 baseline refresh.
- The author audit must preserve the redesign decisions: no pathname-only worker or compiler identity, staged `/usr/bin/env`/`/bin/sh`/loader closure, read-only lower source plus explicit `/workspace/main` output allowlist, source executable-bit preservation, staged `/tools` and `/target/tmp` in nested validation, explicit Python `pass_fds=(5,6)`, private Git refs, writable owner-only staging directories, external cache manifest, and exact cleanup-failure bytes/status.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: the consolidated design repair in `docs/specs/check-gate-topology.md` and this handoff until the scoped repair commit is created. Main's existing uncommitted `HANDOFF.md` is intentional and must not be discarded.
