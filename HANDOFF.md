# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-design-v2`, based on main `32bfeba` (`Add C7 persisted-result design gate (#53)`). The initial design commit is `578807e`; the reviewed repair checkpoint is `4eb878b`.
- Active goal: re-scope the Linux x86_64 fresh-compiler check-topology design after the conditional final review; no dependent implementation or Align pin adoption may start.
- Complete: Section 8 of `docs/specs/check-gate-topology.md` now defines the controller trust root, canonical manifest, source/Git identity boundary, private cache and build namespace, compiler descriptor/interposition, process ownership, status grammar, closure matrix, constants, and delivery order.
- In progress: redesigning the reviewed contract around the missed snapshot, host-runtime, wire-schema, namespace, and cleanup invariants. The conditional final review found substantive P1/P2 issues, so this branch is not merge-ready and must not enter another repair/re-review loop.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Create a new design/re-scope slice, not an implementation repair on this reviewed head. It must make the worker and compiler descriptor immutable snapshots, make fresh enforcement mandatory, define host-side interpreter and dynamic-loader identity, restore writable cleanup authority, and close `/target/tmp` construction.
2. Complete the canonical JSON definitions before coding: representable mode encoding, recursive digest-manifest tree, cache-manifest placement, complete `CompilerDescriptor` nested fields, and golden vectors for each wire boundary.
3. Reopen the closure matrix for exact cleanup-failure status/output semantics and the full host-versus-namespace process topology. Only after that redesigned contract receives its own review may a dependent implementation slice be created; do not push, open, or merge without user authorization.

## Latest verification

- `git diff --check`: passed at the reviewed repair checkpoint `4eb878b`.
- Markdown fence checks: passed for `HANDOFF.md` (0), `docs/align-requests.md` (86), and `docs/specs/check-gate-topology.md` (28).
- Conditional final comprehensive review: completed against `4eb878b`; it found 6 P1 and 6 P2 design findings. The review evidence remains external; this handoff records the durable redesign classes only.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks: N/A for this documentation/specification-only checkpoint; no executable contract has been changed.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- The current reviewed topology is not accepted: it claims only Ubuntu/Linux x86_64, and C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice requires an externally installed fixed bootstrap, authenticated manifest, closed executable inventory, private Cargo cache, and identity-bound C0 baseline refresh.
- The final-review blockers are: immutable worker and compiler-descriptor snapshots; mandatory fresh-mode interposition; staged host-side `env`/`sh` and dynamic-loader/runtime identity; writable cleanup staging with post-child restoration; explicit `/target/tmp`; representable mode and recursive digest-manifest schemas; cache manifest placement; and exact cleanup-failure bytes/status.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none on this design branch. Main's existing uncommitted `HANDOFF.md` is intentional and must not be discarded.
