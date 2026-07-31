# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/git-245-compat-image-design`.
- Base: `a29d707aa76872ed280780022c329c2cced1e480` (`origin/main`).
- Active goal: design, review, and merge the immutable Git 2.45.0 compatibility image prerequisite,
  then finish the common fresh-compiler topology design and implementation before any new Align pin
  adoption.
- Plan of record: `docs/specs/git-245-compat-image.md`.
- Product implementation: not started.
- Pinned Align commit: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.
- C6 design draft remains preserved separately on `agent/c6-prompt-context-design`.

Request 7 merged in PR #25 at `d3c30e9`. PR #27 then replaced the review-loop policy with one
comprehensive review and one consolidated ordinary repair round. The bounded retrospective found
that the reusable PR #25 convergence lesson is already closed by PR #27; no additional governance
slice is queued.

Request 7 requires the common topology to name an immutable OCI image whose `/usr/bin/git` is
exactly 2.45.0 and whose remaining toolchain can run the hosted gate. Repository, web, and registry
inspection found no suitable already-published image with that exact contract. The image is
therefore a separate external-artifact prerequisite rather than an unnamed placeholder inside the
topology plan.

The draft image design fixes the source lock, GHCR name, single amd64 platform, exact Git tarball
hash, Rust/LLVM requirements, credential boundary, publisher workflow, immutable provenance,
public digest-only pull gate, registered JSON record, process/output cleanup, closure matrix, and
three-slice delivery order. The common topology branch remains clean and preserved at
`agent/fresh-compiler-topology-design`; it must consume only the reviewed registered digest.

## Exact next steps

1. Complete the author ledger-to-prose and closure-matrix consistency pass on
   `docs/specs/git-245-compat-image.md`.
2. Run `git diff --check` and documentation/source-of-truth searches.
3. Open the design pull request, run one comprehensive independent adversarial review over the
   complete diff, disposition every finding, apply one consolidated ordinary repair if needed,
   rerun affected verification, and merge only when clean.
4. Refresh `main`, implement and review the checked-in image source and non-publishing publisher
   workflow, then merge it.
5. Obtain explicit authority if needed for public GHCR publication, manually dispatch the
   publisher on the exact merged `main`, and register the resulting immutable digest in the
   separate record slice.
6. Resume `agent/fresh-compiler-topology-design`, bind the registered image, complete and merge the
   fresh-compiler design, then implement it before any `.align-revision` update.

## Verification

Current draft:

```text
Git 2.45.0 canonical tarball SHA-256
  0aac200bd06476e7df1ff026eb123c6827bc10fe69d2823b4bf2ebebe5953429
Ubuntu 24.04 manifest-list digest
  sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90
Ubuntu 24.04 linux/amd64 child digest
  sha256:52df9b1ee71626e0088f7d400d5c6b5f7bb916f8f0c82b474289a4ece6cf3faf
```

No completion or image-publication claim has been made. Documentation verification and
independent review are pending.

## Constraints and intentional state

- This branch changes only `docs/specs/git-245-compat-image.md` and `HANDOFF.md`.
- Do not publish an image from a pull request or register a tag.
- Do not put `GITHUB_TOKEN`, Docker credentials, package secrets, model data, or machine paths in
  the image, provenance, source lock, or repository.
- Registered image digests are immutable project inputs and have no automated delete path.
- Preserve the existing C6, request, topology, governance, and pin-adoption worktrees; they are not
  scratch directories.
- Do not implement against a proposed Align API or change `.align-revision` before the common
  topology design and implementation merge.
