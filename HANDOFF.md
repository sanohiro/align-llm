# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on main `32bfeba` (`Add C7 persisted-result design gate (#53)`). The current design checkpoint is `1ce3f9e` (`Define compiler archive and symlink identity contract`); historical checkpoints `d4c9060`, `4eb878b`, `5cab02f`, `836b489`, and `bb9ad1f` are retained and superseded.
- Active goal: finish this PR's successor Linux x86_64 fresh-compiler design review, record a clean checkpoint, and then complete the active goal; no dependent implementation or Align pin adoption may start.
- Complete: `c6b58d4` records the prior coherent redesign with executable runtime modes, retained source post-copy proof, retained common-Git identity, sealed fd-7 handoff guard, namespace-owned no-symlink aggregate tmpfs, C7 platform-profile synchronization, cache bounds, and validation-before-copy ordering. `6b5dfaa` adds supported Ubuntu 24.04 bwrap inherited-fd handling, retained-descriptor tool probing, complete Git hardening/private object-copy rules, `io_uring` descriptor-operation denial, and explicit `ALIGNC_CACHE=off`. `5cab02f`/`836b489` add the preceding bwrap, runtime, source-mode, Python, utility, mount, and Cargo-cache redesign; the fresh review then identified the remaining source-tree, pin, baseline-Git, mode/cache-wire, status, and C7-contract gaps now being repaired together.
- In progress: obtain one fresh comprehensive review of `1ce3f9e`. The latest review found that memfd-only execution hides the pinned Align compiler's adjacent `libalign_runtime.a`, that the tracked root `AGENTS.md -> CLAUDE.md` symlink was rejected, and that symlink mode bytes were unspecified. The committed repair stages and authenticates a read-only `/tools/alignc` plus `/tools/libalign_runtime.a` sibling bundle, retains fd 5 as the sealed compiler identity capsule, admits contained tracked symlinks, and encodes symlink `mode`/`staged_mode` as JSON `null` with a golden vector.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Run one fresh comprehensive review of `1ce3f9e`; do not implement against it until the review is clean.
2. If clean, record the final checkpoint and complete the active goal. Bootstrap/image installation, implementation, baseline refresh, and pin adoption remain future slices; do not push, open, or merge without user authorization.

## Latest verification

- Latest focused checks after the repair: `git diff --check`: PASS; balanced Markdown fences: PASS (`HANDOFF.md` 0, `docs/align-requests.md` 86, `docs/specs/c7-persisted-result.md` 16, `docs/specs/check-gate-topology.md` 60); seven current Section 9 JSON blocks parsed; contained-symlink golden digest `aa24c3c73d318b8466716082b269c8fbba8a63d688fa97489aeb6a90af060c91`: PASS; descriptor schema-3 field-order and bundle assertions: PASS; Section 9 runtime-archive, tracked-symlink, and null-mode assertions: PASS. Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks remain N/A for this documentation/specification-only repair.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked on a reviewed design that separately authenticates the align-llm project and sibling Align source roots, proves `ALIGN_REPO` HEAD/tree/index/cleanliness against `.align-revision`, stages `/align-src`, defines exact source-manifest wire bytes including contained symlink `null` modes, provides normal and negative private baseline-Git views, defines raw-to-staged runtime/cache modes and the external cache wire format, authenticates the read-only compiler/archive sibling bundle at `/tools/alignc` and `/tools/libalign_runtime.a`, fixes the exact status grammar, and synchronizes C7's fresh `make ci`, together with the inherited-fd, retained-tool, bwrap-before-probe, Git hardening/private-object, fd-denial, cache-off, runtime-mode, source post-copy, common-Git identity, fd-7 guard, aggregate overlay/tmpfs, C7 platform-profile, cache-bound, and validation-order decisions.
- Do not consume `6b5dfaa` or `bb9ad1f` as an implementation contract until the successor design is reviewed clean. Preserve the valid decisions—no pathname-only worker/compiler identity, staged `/usr/bin/env`/`/bin/sh`/loader closure, overlay publication, staged `/tools`, explicit descriptor propagation (now fds 5/6/7), private Git refs, exact cleanup-failure bytes/status, and the current private executable-bundle rule—until the fresh review completes.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none in this worktree. Main's separate uncommitted `HANDOFF.md` is intentional and must not be discarded.
