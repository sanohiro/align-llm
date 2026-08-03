# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on main `32bfeba` (`Add C7 persisted-result design gate (#53)`). The current redesign checkpoint is `f620508` (`Rescope fresh compiler trust and product closure`); historical checkpoints `d4c9060`, `4eb878b`, `5cab02f`, `836b489`, `bb9ad1f`, `1ce3f9e`, `004af2e`, `0247c86`, and `9a48e6f` remain retained and superseded.
- Active goal: finish this PR's successor Linux x86_64 fresh-compiler design review, record a clean checkpoint, and then complete the active goal; no dependent implementation or Align pin adoption may start.
- Complete: the latest fresh review found four P1 and two P2 gaps. The consolidated redesign now binds the toolchain manifest to the fixed trusted runner image, derives authenticated linker/loader/pkg-config paths and checks the generated `main` ELF closure, disables Python bytecode writes in aggregate and nested environments, corrects the cache golden count/digest, leaves unprovable roots untouched after an uncatchable death, and defines the raw Git index digest preimage and semantic vector. It retains the prior fixes for inherited compiler identity fds, private project Git views, root `.git` control, both `target` exceptions, canonical sibling-root opening, Cargo prefixes/configuration, and the read-only `/tools/alignc` plus `/tools/libalign_runtime.a` bundle with write-once handoff files.
- In progress: obtain one new comprehensive review of `f620508`. The prior review is not being treated as clean evidence.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Run one fresh comprehensive review of `f620508`; do not implement against it until the review is clean.
2. If clean, record the final checkpoint and complete the active goal. Bootstrap/image installation, implementation, baseline refresh, and pin adoption remain future slices; do not push, open, or merge without user authorization.

## Latest verification

- Latest focused checks after the redesign: `git diff --check`: PASS; JSON parsing: PASS (6 current Section 9 blocks); cache-manifest v2 digest `44a98ed3b3adf920e6e02a770d83dd6784e4c16fadcb19ec0f78cde1335261a0`: PASS; source-manifest digests `7d9857fe466e5fbae7f39ff38e7925547a5f89b5c569a06a4dec5858fa620d38` and `bbe5614319d31f8aef687fb0506b607d4b8d03d357bf3be56e7f48d6d72ea175`: PASS; raw empty-index SHA-256 `79dc0d556c3c637aad3efa1d3a1906e5abea7aa1ffdbb3d3ed9932eec3bf6954`: PASS; descriptor schema-4 field order/bundle assertions: PASS; fixed image-manifest rejection, derived linker/loader paths, generated-output closure, bytecode-disable, private-Git/read-only-handoff/cleanup assertions: PASS; balanced Markdown fence lines: PASS (`HANDOFF.md` 0, `docs/align-requests.md` 86, `docs/specs/c7-persisted-result.md` 16, `docs/specs/check-gate-topology.md` 60). Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmark checks remain N/A for this documentation/specification-only redesign.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked on a clean review of `f620508`. It must preserve the separately authenticated align-llm and sibling Align source roots, canonical `ALIGN_REPO` opening, exact raw source/index/worktree identities, root `.git` and both `target` exceptions, contained symlink modes, private Git views for every project call, schema-2 cache wire and five prefixes, tracked Cargo configuration, fixed image-attested manifest, derived linker/loader paths and generated-output closure, bytecode-disabled aggregate, read-only compiler/archive bundle, catchable-only cleanup, and exact status grammar before implementation or pin adoption.
- Do not consume `6b5dfaa`, `bb9ad1f`, or the current unreviewed redesign as an implementation contract until the successor design is reviewed clean. Preserve the valid decisions—no host pathname/compiler fallback, staged `/usr/bin/env`/`/bin/sh`/loader closure, overlay publication, staged `/tools`, private Git refs, exact cleanup-failure bytes/status, read-only compiler/archive sibling bundle, and empty descriptor propagation—until the fresh review completes.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none in this worktree. Main's separate uncommitted `HANDOFF.md` is intentional and must not be discarded.
