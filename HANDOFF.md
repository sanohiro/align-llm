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
- Plan of record: `docs/specs/git-245-compat-image.md`.
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
- offline canonical-format and byte-level archive-parser tests; and
- one real author-run HTTPS audit of the four locked archives with exact root ownership, bounded
  parsing, deterministic diagnostics, and cleanup.

It contains no Dockerfile, Docker command, hosted workflow, registry operation, image publication,
or registration. The later Docker design must independently close all Docker/external-process
ownership findings while consuming only the merged locked inputs. This work does not install or
modify LLVM on a developer machine.

## Exact next steps

1. Complete the locked-input/audit author ledger-to-prose-to-matrix pass, stage only the plan and
   handoff, run `git diff --check` and
   `make ci ALIGN_REPO=<sibling pinned Align checkout>`, then commit and open the design pull
   request if it is not already open.
2. Run the one comprehensive high-effort independent-adversarial review required by `CLAUDE.md`,
   disposition all findings, apply any accepted root-cause classes in one consolidated follow-up,
   rerun affected checks, and merge only when ready.
3. Refresh `main`, perform the bounded retrospective, and implement the locked inputs and audit.
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
Prior fixed-archive inspection
  PASS (one expected compression stream and top-level directory; no escaping/special/setid,
  duplicate, hard-link, PAX, sparse, concatenated-stream, or trailing-nonzero record)
Current locked-input/audit design
  Author ledger/prose/closure pass: PASS
  git diff --check: PASS
  make ci ALIGN_REPO=<sibling pinned Align checkout>: PASS
    (pinned release build, 15 units with 3 existing compiler warnings, fixed evaluations,
    loop smoke tests, and baseline validation)
```

The prior archive inspection is fixed-input evidence, not acceptance for the unimplemented audit
target. The implementation slice must produce the named reproducible real-audit result.

## Constraints and intentional state

- This branch intentionally changes only `docs/specs/git-245-compat-image.md` and `HANDOFF.md`.
- No image has been built, published, registered, or added to the source tree.
- Do not publish from a pull request, consume a tag, or infer authority to change package
  visibility.
- Do not commit downloaded archives, model weights, generated images, binaries, credentials,
  tokens, local profiles, or machine-specific paths.
- Preserve the existing C6, request, topology, governance, pin-adoption, and prior image-design
  worktrees; they are not scratch directories.
- Do not change `.align-revision` before the common topology design and implementation merge.
