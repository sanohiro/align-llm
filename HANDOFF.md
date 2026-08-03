# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on main `32bfeba` (`Add C7 persisted-result design gate (#53)`). The current committed checkpoint is `836b489`; the source/pin, baseline-Git, mode/cache, status, and C7 re-scope is uncommitted and will receive a new design checkpoint. Historical checkpoints `d4c9060` and `4eb878b` are retained and superseded.
- Active goal: close the latest independent review's four P1 and four P2 gaps in the successor Linux x86_64 fresh-compiler design; no dependent implementation or Align pin adoption may start.
- Complete: `c6b58d4` records the prior coherent redesign with executable runtime modes, retained source post-copy proof, retained common-Git identity, sealed fd-7 handoff guard, namespace-owned no-symlink aggregate tmpfs, C7 platform-profile synchronization, cache bounds, and validation-before-copy ordering. `6b5dfaa` adds supported Ubuntu 24.04 bwrap inherited-fd handling, retained-descriptor tool probing, complete Git hardening/private object-copy rules, `io_uring` descriptor-operation denial, and explicit `ALIGNC_CACHE=off`. `5cab02f`/`836b489` add the preceding bwrap, runtime, source-mode, Python, utility, mount, and Cargo-cache redesign; the fresh review then identified the remaining source-tree, pin, baseline-Git, mode/cache-wire, status, and C7-contract gaps now being repaired together.
- In progress: complete the coherent Section 9 redesign, update the synchronized Request 9/C7 records and this handoff, commit the design checkpoint, and obtain a fresh comprehensive review.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Finish the source/pin, source-manifest wire, private baseline-Git, raw/staged mode, cache-manifest, status-grammar, and C7 command updates in Section 9 and its ledgers.
2. Run focused documentation and contract checks, commit the design checkpoint, then run one fresh comprehensive review; do not implement against it until that review is clean.
3. Only after a clean reviewed design may the separate bootstrap/image and implementation slices be prepared; do not push, open, or merge without user authorization.

## Latest verification

- Latest focused checks: `git diff --check`: PASS; balanced Markdown fences: PASS (`HANDOFF.md` 0, `docs/align-requests.md` 86, `docs/specs/c7-persisted-result.md` 16, `docs/specs/check-gate-topology.md` 58); five Section 9 JSON vectors parsed; runtime digest, external cache-manifest, source-manifest, and compiler-descriptor golden vectors: PASS; source/pin, `/align-src`, private baseline-Git, raw/staged mode, cache wire, canonical escaping, exact status grammar, fd-denial, cache-off, and C7 synchronization assertions: PASS.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks: N/A for this documentation/specification-only draft; no executable contract has been changed.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked on a reviewed design that separately authenticates the align-llm project and sibling Align source roots, proves `ALIGN_REPO` HEAD/tree/index/cleanliness against `.align-revision`, stages `/align-src`, defines exact source-manifest wire bytes, provides normal and negative private baseline-Git views, defines raw-to-staged runtime/cache modes and the external cache wire format, fixes the exact status grammar, and synchronizes C7's fresh `make ci`, together with the inherited-fd, retained-tool, bwrap-before-probe, Git hardening/private-object, fd-denial, cache-off, runtime-mode, source post-copy, common-Git identity, fd-7 guard, aggregate overlay/tmpfs, C7 platform-profile, cache-bound, and validation-order decisions.
- Do not consume `6b5dfaa` as an implementation contract until the successor design is reviewed clean. Preserve the valid decisions—no pathname-only worker/compiler identity, staged `/usr/bin/env`/`/bin/sh`/loader closure, overlay publication, staged `/tools`, explicit descriptor propagation (now fds 5/6/7), private Git refs, and exact cleanup-failure bytes/status—while preserving the current re-scoped design decisions above.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files in this worktree: `HANDOFF.md`, `docs/align-requests.md`, `docs/specs/c7-persisted-result.md`, and `docs/specs/check-gate-topology.md` contain the current redesign and must not be discarded before the design checkpoint commit. Main's separate uncommitted `HANDOFF.md` is intentional and must not be discarded.
