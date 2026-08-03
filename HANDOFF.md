# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on main `32bfeba` (`Add C7 persisted-result design gate (#53)`). The current redesign checkpoint is `0247c86` (`Rescope fresh compiler handoff and source boundaries`); historical checkpoints `d4c9060`, `4eb878b`, `5cab02f`, `836b489`, `bb9ad1f`, `1ce3f9e`, and `004af2e` remain retained and superseded.
- Active goal: finish this PR's successor Linux x86_64 fresh-compiler design review, record a clean checkpoint, and then complete the active goal; no dependent implementation or Align pin adoption may start.
- Complete: the latest fresh review found three P1 and four P2 gaps. The consolidated redesign now removes inherited compiler identity fds and the conflicting child-close filter, routes every normal project Git call through `/baseline-git`, records root `.git` control and both `target` exceptions in the source wire, canonicalizes the sibling root before no-follow opening, defines the schema-2 five-prefix Cargo cache manifest, accepts only the pinned tracked `.cargo/config.toml` digest/key set, and distinguishes catchable cleanup from next-invocation orphan reclamation. The compiler/archive bundle remains at read-only `/tools/alignc` and `/tools/libalign_runtime.a`, with write-once `/tools/fresh-descriptor` and `/tools/fresh-guard` handoff files.
- In progress: obtain one new comprehensive review of `0247c86`. The prior review is not being treated as clean evidence.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Run one fresh comprehensive review of `0247c86`; do not implement against it until the review is clean.
2. If clean, record the final checkpoint and complete the active goal. Bootstrap/image installation, implementation, baseline refresh, and pin adoption remain future slices; do not push, open, or merge without user authorization.

## Latest verification

- Latest focused checks after the redesign: `git diff --check`: PASS; JSON parsing: PASS (7 current Section 9 blocks); cache-manifest v2 digest `783307cd7665282c8285ae8a49c3022a5c36e7fd3aae4c18c7d469aacb9a9b35`: PASS; source-manifest digests `24088b5ed89886aefce90cde2e1e804e10e3e76c59b60e50bc7acb1918b1efd5` and `c84591ffc62396bf8bfc28015b7e5748c6a753c2ace34fe8c9259d47220c256d`: PASS; descriptor schema-4 field order/bundle assertions: PASS; tracked Cargo-config digest and Section 9 private-Git/read-only-handoff/cleanup assertions: PASS; balanced Markdown fence lines: PASS (`HANDOFF.md` 0, `docs/align-requests.md` 86, `docs/specs/c7-persisted-result.md` 16, `docs/specs/check-gate-topology.md` 60). Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks remain N/A for this documentation/specification-only redesign.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked on a reviewed design that separately authenticates the align-llm project and sibling Align source roots, canonicalizes `ALIGN_REPO` before no-follow opening, proves `ALIGN_REPO` HEAD/tree/index/cleanliness against `.align-revision`, stages `/align-src`, defines exact source-manifest wire bytes including root `.git`, both `target` exceptions, and contained symlink `null` modes, provides normal and negative private baseline-Git views for all project Git calls, defines raw-to-staged modes and the schema-2 five-prefix external cache wire, accepts the pinned tracked Cargo config only, authenticates the read-only compiler/archive bundle and write-once handoff files, fixes catchable/uncatchable cleanup and status grammar, and synchronizes C7's fresh `make ci`, together with retained-tool, bwrap-before-probe, cache-off, runtime-mode, source post-copy, common-Git identity, aggregate overlay/tmpfs, C7 platform-profile, cache-bound, and validation-order decisions.
- Do not consume `6b5dfaa`, `bb9ad1f`, or the current unreviewed redesign as an implementation contract until the successor design is reviewed clean. Preserve the valid decisions—no host pathname/compiler fallback, staged `/usr/bin/env`/`/bin/sh`/loader closure, overlay publication, staged `/tools`, private Git refs, exact cleanup-failure bytes/status, read-only compiler/archive sibling bundle, and empty descriptor propagation—until the fresh review completes.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none in this worktree. Main's separate uncommitted `HANDOFF.md` is intentional and must not be discarded.
