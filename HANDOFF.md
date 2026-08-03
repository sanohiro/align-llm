# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-design-v2`, based on main `32bfeba` (`Add C7 persisted-result design gate (#53)`). The initial design commit is `578807e`; the consolidated review repair is committed at `dcc3c23`.
- Active goal: finish the Linux x86_64 fresh-compiler check-topology design before any dependent implementation or Align pin adoption.
- Complete: Section 8 of `docs/specs/check-gate-topology.md` now defines the controller trust root, canonical manifest, source/Git identity boundary, private cache and build namespace, compiler descriptor/interposition, process ownership, status grammar, closure matrix, constants, and delivery order.
- In progress: completing the conditional final comprehensive review of the repaired design.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Complete the conditional final comprehensive review and resolve only any valid recorded finding in one final re-scope if required; do not push, open, or merge a pull request without user authorization.
2. Update the intentional uncommitted `main` `HANDOFF.md` with the resulting design checkpoint.
3. Only after the reviewed design merges, create the dependent implementation slice. It must install and attest the fixed bootstrap/toolchain manifest, implement all named closure rows, refresh the identity-bound baseline after its Makefile change, and pass the unchanged-pin local/hosted/capable gates.

## Latest verification

- `git diff --check`: passed after the consolidated repair at `dcc3c23`.
- Markdown fence checks: passed for `HANDOFF.md` (0), `docs/align-requests.md` (86), and `docs/specs/check-gate-topology.md` (28).
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks: N/A for this documentation/specification-only repair; no executable contract has been changed.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- The repaired common topology claims only Ubuntu/Linux x86_64. C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice requires an externally installed fixed bootstrap, authenticated manifest, closed executable inventory, private Cargo cache, and identity-bound C0 baseline refresh.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none on this design branch. Main's existing uncommitted `HANDOFF.md` is intentional and must not be discarded.
