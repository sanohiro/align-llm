# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on redesign checkpoint `d4c9060` from main `32bfeba` (`Add C7 persisted-result design gate (#53)`). Historical design checkpoint `4eb878b` is retained and superseded.
- Active goal: re-scope the successor Linux x86_64 fresh-compiler design after its conditional final review found additional contract gaps; no dependent implementation or Align pin adoption may start.
- Complete: commit `a1636ee` applies the first review's six P1 repairs: aggregate overlay upper/work publication, source executable-bit preservation, nested staged-tool/fd propagation, `/target/tmp` loop markers, private baseline Git scratch, and explicit Python descriptor passing. The required conditional final review of that repaired design completed and found six new P1 and two P2 findings. The current uncommitted design repair updates Section 9, the C7 platform prerequisite, the Request 9 ledger, and this handoff with the reopened contract.
- In progress: focused consistency review of the re-scoped contract. It now requires executable runtime staging modes, retained source descriptors with post-copy proof, `GIT_COMMON_DIR` descriptor identity, a sealed fd-7 handoff guard plus seccomp protection for fds 5/6/7, an image-owned `mount-guard`, a namespace-owned 256-MiB no-symlink aggregate tmpfs, C7 platform-profile synchronization, 512-MiB per-file and 20-GiB total cache bounds, and validation-before-copy ordering.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Finish the ledger-to-prose and matrix-to-diff consistency pass, including the aggregate bwrap ordering, fd-8 handoff to bwrap, mount-guard CLI, and C7 numbering.
2. Run focused docs/static checks, commit the coherent successor design repair, and obtain one fresh comprehensive review; do not implement against `a1636ee` until that review is clean.
3. Only after a clean reviewed design may the separate bootstrap/image and implementation slices be prepared; do not push, open, or merge without user authorization.

## Latest verification

- `git diff --check`: passed for the current uncommitted re-scope so far.
- The previous Markdown fence checks passed for `docs/align-requests.md` (86), `docs/specs/check-gate-topology.md` (52), and the prior handoff (0); the current repair still needs the same checks after the final wording pass.
- The previous targeted contract/static checks passed before final review: required Section 9 phrases, schema-2 digest and descriptor golden vectors, and the stale superseded-contract scan. The updated descriptor/guard vectors and platform-prerequisite checks are not yet rerun.
- `codex review --base main` completed at the conditional final gate with exit 0 but a blocking verdict: six P1 and two P2 findings. The design repair loop was intentionally stopped after that review; no fresh review has been run against the current re-scoped contract.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks: N/A for this documentation/specification-only draft; no executable contract has been changed.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked on a reviewed design that additionally preserves executable modes for runtime launchers/loaders, copies only from retained source descriptors with post-copy identity proof, passes retained common-Git identity, prevents descriptor replacement through the worker-bound fd-7 guard and inherited seccomp filter, isolates aggregate `/target/tmp` from `/workspace` symlink traversal, synchronizes C7's non-x86 platform prerequisites, bounds per-file/total cache bytes, and separates cache validation from copy ordering.
- Do not consume `a1636ee` as an implementation contract. Preserve its valid decisions—no pathname-only worker/compiler identity, staged `/usr/bin/env`/`/bin/sh`/loader closure, overlay publication, staged `/tools`, explicit descriptor propagation (now fds 5/6/7), private Git refs, and exact cleanup-failure bytes/status—while preserving the re-scoped design decisions above.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: the current design repair in `docs/specs/check-gate-topology.md`, `docs/specs/c7-persisted-result.md`, `docs/align-requests.md`, and this `HANDOFF.md`; these changes are the re-scoped successor contract and must not be discarded. Main's existing uncommitted `HANDOFF.md` is intentional and must not be discarded.
