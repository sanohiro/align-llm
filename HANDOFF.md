# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v3`, based on main `32bfeba` (`Add C7 persisted-result design gate (#53)`). The current work is the consolidated repair of the successor fresh-compiler design, based on the reviewed design content checkpoint `d63779d`; historical checkpoints remain retained and superseded.
- Active goal: complete the successor design review, merge the common fresh-compiler topology contract, then implement it and consume it for Request 6 adoption. No dependent implementation or Align pin adoption may start until this design is reviewed and merged.
- Durable design state: Section 9 is the only normative fresh-compiler contract. It binds a supervisor-verified immutable runner-image identity to sealed bootstrap/manifest snapshots; opens both source roots descriptor-relatively; defines source directory/symlink rechecks and fixed resource bounds; specifies object-format-aware source manifests and probe-byte encoding; fixes Make option precedence and concurrent-process policy; and gives exact compiler-output metadata, cleanup, and status contracts. It retains the private Git view, read-only compiler/archive bundle, staged interpreter/runtime closure, bytecode-disabled aggregate, overlay publication, and unprovable-root preservation decisions.
- Not started: bootstrap/image installation, controller implementation, `eval` tool-path implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Run the author-side consistency and golden-vector checks on the consolidated repair, then commit the design and continuity update as one scoped design checkpoint.
2. Run exactly one final comprehensive review of that repaired head against main, record the complete SHA-bound verdict and findings externally, and do not start an open-ended review loop.
3. If clean, publish and merge this design slice; then create the separate implementation slice. Install/attest the fixed image before its acceptance evidence and keep `.align-revision` unchanged until implementation passes.
4. The separate review-gate draft is preserved in `stash@{0}` and must not be mixed into this design slice.

## Latest verification

- Latest focused checks after the consolidated repair: `git diff --check`: PASS; JSON parsing: PASS; cache-manifest v2 digest `44a98ed3b3adf920e6e02a770d83dd6784e4c16fadcb19ec0f78cde1335261a0`: PASS; source-manifest SHA-1/file and symlink digests `f5da8d8bbe02e4a7d32154ebeadd0e73beea213a4c036a08a34b313586007e23` and `14902048674d7363379f6427d8b4b305654794827e9481a3d831b244f0dc77ea`: PASS; object-format tree/file/symlink vector digests `5dc22d576eb870679a1867a89d0b2a5f71c7465d1a5bd3586443105eec64c437` and `f071ae8704196869192b8afe934b667046e0713e658ee909812da0781e874872`: PASS; raw empty-index SHA-256 `79dc0d556c3c637aad3efa1d3a1906e5abea7aa1ffdbb3d3ed9932eec3bf6954`: PASS; image-attestation, descriptor-relative source, directory/symlink recheck, bounds, probe-byte, Make-option, concurrent non-evidence, final-output metadata, and status-precedence assertions: PASS; balanced Markdown fences: PASS. Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmarks remain N/A for this documentation/specification-only redesign.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64; C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked until this repaired design has a clean review attestation and merges. It must preserve the separately authenticated align-llm and sibling Align source roots, canonical component-wise `ALIGN_REPO` opening, exact raw source/index/worktree identities, root `.git` and both `target` exceptions, contained symlink modes, fixed source/runtime/tool/Git/output bounds, object-format wire vectors, private Git views for every project call, schema-2 cache wire and five prefixes, tracked Cargo configuration, supervisor-verified image attestation, derived linker/loader paths and generated-output closure, bytecode-disabled aggregate, read-only compiler/archive bundle, catchable-only cleanup, concurrent non-evidence policy, and exact status grammar before implementation or pin adoption.
- Do not consume `6b5dfaa`, `bb9ad1f`, or any unreviewed topology implementation as an implementation contract until this successor design is reviewed clean and merged. Preserve the no-host-fallback, staged interpreter/loader closure, overlay publication, private Git refs, exact cleanup-failure bytes/status, and empty descriptor propagation decisions.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none in this worktree. Main's separate uncommitted `HANDOFF.md` is intentional and must not be discarded. The separate governance draft is preserved in `stash@{0}`.
