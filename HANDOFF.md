# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/git-245-compat-image-redesign`.
- Branch point and last merged checkpoint:
  `a29d707aa76872ed280780022c329c2cced1e480` (`origin/main` at branch creation). The current
  relevant design checkpoint is the branch tip; its self-referential SHA is intentionally not
  embedded in the commit it identifies.
- Active goal: merge the Git 2.45.0 compatibility-image prerequisites, then deliver Docker/local
  acceptance, hosted minimum-environment acceptance, publication/provenance, registration, and the
  common fresh-compiler topology as separate reviewed slices.
- Current slice: immutable Git/Rust/LLVM inputs plus reproducible locked-archive audit.
- Plans of record: `docs/specs/git-245-compat-image.md` plus the exact hosted-target extension in
  `docs/specs/check-gate-topology.md`.
- Product implementation: not started.
- Pinned Align commit: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.
- C6 design remains preserved separately on `agent/c6-prompt-context-design`.

The prior design combined locked inputs, Dockerfile construction, Buildx/BuildKit orchestration,
image loading, runtime containers, and local acceptance. Repeated comprehensive review exposed new
cross-boundary ownership gaps after material redesigns: exact Dockerfile byte identity, composite
Buildx daemon resources, lexical paths crossing into Docker, and resolved-image/container state.
Repository policy therefore stopped that repair loop and split the work at the first independently
correct boundary.

The current slice owns only:

- canonical Git 2.45.0 and Rust 1.96.0 archive identities;
- the exact reviewed LLVM installer bytes;
- offline canonical-format and byte-level archive-parser tests through the production executable;
  and
- one real author-run HTTPS audit of the four locked archives with exact root ownership, bounded
  parsing, deterministic diagnostics, and cleanup.

It contains no Dockerfile, Docker command, hosted workflow, registry operation, image publication,
or registration. The later Docker design must independently close all Docker/external-process
ownership findings while consuming only the merged locked inputs. This work does not install or
modify LLVM on a developer machine.

## Exact next steps

1. Finish the consolidated locked-input design repair, including the authoritative hosted-target
   topology amendment; run the author ledger/prose/matrix pass and all design checks.
2. Commit and push the one repair, run the required conditional final comprehensive review, resolve
   it under the repository workflow, and merge only when all current evidence is clean.
3. Refresh `main`, perform the bounded retrospective, and implement the locked inputs, single
   production/self-test executable, fixed Make adapters, topology oracle update, and required
   baseline source -> oracle -> finalization chain.
4. Design and implement Docker construction and local no-push acceptance as a separate slice.
5. Design and implement the hosted no-push gate on the exact minimum environment, including
   platform credential recipients and bounded/abrupt cleanup.
6. Design publication/provenance only after the hosted gate merges. Obtain explicit
   repository-owner authority before any GHCR publication or package visibility change.
7. Design and implement registration separately, then resume the common fresh-compiler topology
   using only the merged registered digest.

## Verification

Durable fixed-input evidence:

```text
Canonical source lock
  1301 bytes
  0b27dd188cd4536efe2adb5b92e86d81bfbf23fd7fe87e770d58d03d061459a0
Git 2.45.0 source
  7482988 bytes
  0aac200bd06476e7df1ff026eb123c6827bc10fe69d2823b4bf2ebebe5953429
Rust 1.96.0 cargo
  15645746 bytes
  b691a9e31b1e5498017be91155a1e7501eccf6437e7dc9ff1896e38aa1584dbf
Rust 1.96.0 rust-std
  49703183 bytes
  36e577b66f7b2f8fc6493f97f81329e5f6e1514360d0c6c31d5d8463184e6773
Rust 1.96.0 rustc
  134687636 bytes
  71143d6075582b7e65233992c77e375aadbec4dfda6df2675160bf05b89410f9
Vendored LLVM installer
  8277 bytes
  9474ecd78b52aba6e923976b1e9773f5613027cc7e237b9956986cb536e02a36
Current locked-input/audit design
  Consolidated review repair: complete locally
  Author ledger/prose/closure consistency pass: PASS
  Canonical JSON byte oracle: PASS (1301 bytes; expected SHA-256)
  Raw Make-value transport prototype: PASS
    (literal $(shell ...), quotes, dollars, backticks, spaces, and metacharacters retained;
    no marker side effect)
  Fixed real-archive dialect inspection: PASS
    (Git: 4683 ustar headers, 174458 normalized-path bytes, max path 96;
    cargo: 68 GNU headers, 4455 path bytes, max path 98;
    rust-std: 146 GNU headers including 65 long names, 10648 path bytes, max path 167;
    rustc: 71 GNU headers including one long name, 4837 path bytes, max path 102)
  git diff --check: PASS
  make ci ALIGN_REPO=<sibling pinned Align checkout>: PASS
    (pinned release build, 15 units with 3 existing compiler warnings, fixed evaluations,
    loop smoke tests, and baseline validation)
```

The archive hashes above identify the inputs but are not acceptance for the unimplemented audit
target. The implementation slice must produce the named reproducible real-audit result through the
committed production executable.

## Constraints and intentional state

- This branch intentionally changes only `docs/specs/git-245-compat-image.md`, the exact
  `docs/specs/check-gate-topology.md` hosted-target amendment, and `HANDOFF.md`.
- No image has been built, published, registered, or added to the source tree.
- Do not publish from a pull request, consume a tag, or infer authority to change package
  visibility.
- Do not commit downloaded archives, model weights, generated images, binaries, credentials,
  tokens, local profiles, or machine-specific paths.
- Preserve the existing C6, request, topology, governance, pin-adoption, and prior image-design
  worktrees; they are not scratch directories.
- Do not change `.align-revision` before the common topology design and implementation merge.
