# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v4`, based on main `32bfeba55e358d249bab62623e9ea7d5f2cf7c63` (`Add C7 persisted-result design gate (#53)`). The current commit before the re-scoped design edit is `b8bf9aff06352e1bd58f3b42974bb911ff40263`; the re-scoped design is not committed yet.
- Active goal: finish the re-scoped common fresh-compiler topology design, merge it, implement the reviewed topology slice, and consume it for Request 6 adoption. No dependent implementation or Align pin adoption may start until the design and implementation slices merge.
- Durable design state: Section 9 is the only normative fresh-compiler contract. The v4 slice separates the image-owned supervisor/bootstrap plane from the per-reviewed-head repository worker; the fixed image manifest authenticates image tools/runtime only, while a signed run capsule binds the checked-out head and worker digest. It defines the env-scrubbed supervisor boundary, sealed attestation/worker snapshots, descriptor-relative source roots, canonical source/cache/attestation wires, one-root admission lock, fail-closed orphan handling, executable `/tmp`, fixed resource/cardinality limits, complete Make option rejection, phase-5 Cargo configuration ownership, private Git views, read-only compiler/archive bundle, aggregate overlay, output closure, and exact status/cleanup grammar.
- Not started: bootstrap/image installation, controller implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Complete the v4 closure-matrix consistency pass and golden-vector/static checks, then commit the re-scoped design and continuity update as one scoped design checkpoint.
2. Publish the new design slice as its own PR and run one comprehensive review for this re-scoped head; record the SHA-bound review externally.
3. If clean, merge the design slice; install/attest the fixed image supervisor and bootstrap, then create the separate repository implementation slice without changing `.align-revision`.
4. Refresh the identity-bound baseline after the implementation changes Make behavior, run the fresh topology matrix and capable `make ci`, then create the separate Request 6 adoption slice.

## Latest verification

- Before the v4 re-scope, `git diff --check main...b8bf9aff06352e1bd58f3b42974bb911ff40263`: PASS; Section 9 JSON/golden-vector/static consistency checks: PASS. The v4 edits are not yet committed or fully rechecked; run the exact author checks before handoff.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64 with executable `/tmp`, delegated cgroup limits, and the named minimum toolchain. C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked until the v4 design is merged, then the implementation passes its complete review/check gate. Preserve the run-capsule/image-manifest split, exact supervisor argv and environment scrub, fd 5/6 attestation handoff, one-root lock and fail-closed orphan policy, source identity and bounds, private Git views, fixed Cargo configuration, read-only bundle, and exact status grammar.
- Do not consume `6b5dfaa`, `bb9ad1f`, or any unreviewed topology implementation as an implementation contract until this successor design and its dependent implementation merge. Preserve the no-host-fallback, staged interpreter/loader closure, overlay publication, private Git refs, and empty descriptor propagation decisions.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: the v4 design edits and this HANDOFF update in this worktree. Main's separate uncommitted `HANDOFF.md` is intentional and must not be discarded.
