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

Design PR #28 is open from design root `869164113bf2be3c41f2e7358ccff5e775ed7d7d`.
Its first independent adversarial review accepted eight findings: remove tag-promotion trust,
handle default-private GHCR bootstrap explicitly, close the OCI/record schemas, keep the production
Git parser in the topology slice, narrow process-cleanup claims, name publisher trust and
credential scans, serialize queued dispatches, and remove unexplained OCI attestations. One
consolidated repair addresses that class while retaining Rust 1.96.0 and LLVM 22 because the
declared hosted gate builds the pinned Align compiler. No image has been published.

The repaired design fixes the source lock, GHCR name, one amd64 OCI manifest, exact Git tarball
hash, Rust/LLVM requirements, credential boundary, publisher workflow, canonical external
provenance with a durable registered copy, public digest-only pull gate, registered JSON record,
process/output cleanup, closure matrix, and delivery order. Buildx 0.34.1 is byte-locked and uses
the immutable official BuildKit 0.30.0 manifest plus amd64 child. Implementation is split below the
roughly 1,000-line review boundary into image source, OCI/process tooling, publisher/record
tooling, and non-publishing workflow slices. The common topology branch remains clean and
preserved at `agent/fresh-compiler-topology-design`; it must consume only the reviewed registered
digest.

## Exact next steps

1. Complete the author ledger-to-prose and closure-matrix consistency pass on the consolidated
   repair; verify every fixed digest and pinned action commit.
2. Commit and push that one repair, update PR #28 finding dispositions, and rerun CI.
3. Because the repair changes the publication design materially, run the required fresh
   comprehensive review over the final SHA set. If clean, record its complete envelope and merge
   PR #28 only with current base/check evidence.
4. Refresh `main`, perform the bounded retrospective, then implement/review/merge the image-source
   slice, OCI/process tooling slice, publisher/record tooling slice, and non-publishing workflow
   slice in that order.
5. Obtain explicit authority for public GHCR publication, manually dispatch the
   publisher on the exact merged `main`, and register the resulting immutable digest in the
   separate record slice.
6. Resume `agent/fresh-compiler-topology-design`, bind the registered image, complete and merge the
   fresh-compiler design, then implement it before any `.align-revision` update.

## Verification

Current draft:

```text
Git 2.45.0 canonical tarball SHA-256
  0aac200bd06476e7df1ff026eb123c6827bc10fe69d2823b4bf2ebebe5953429
Rust 1.96.0 cargo component SHA-256
  b691a9e31b1e5498017be91155a1e7501eccf6437e7dc9ff1896e38aa1584dbf
Rust 1.96.0 rust-std component SHA-256
  36e577b66f7b2f8fc6493f97f81329e5f6e1514360d0c6c31d5d8463184e6773
Rust 1.96.0 rustc component SHA-256
  71143d6075582b7e65233992c77e375aadbec4dfda6df2675160bf05b89410f9
Ubuntu 24.04 manifest-list digest
  sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90
Ubuntu 24.04 linux/amd64 child digest
  sha256:52df9b1ee71626e0088f7d400d5c6b5f7bb916f8f0c82b474289a4ece6cf3faf
Buildx 0.34.1 linux/amd64 asset SHA-256
  f1332ddb9010bd0b72628266c3a906d9a6979848033df4c8d9bd2cd113bae12b
BuildKit 0.30.0 manifest digest
  sha256:0168606be2315b7c807a03b3d8aa79beefdb31c98740cebdffdfeebf31190c9f
BuildKit 0.30.0 linux/amd64 child digest
  sha256:57269d1784e49b46228c45a1a1b870fbe40e0a639ab60b37b032d83af5bccdfc
BuildKit 0.30.0 linux/amd64 config/image ID
  sha256:6db049f808b3e0c0694b3522d85b5a9bee4a0248a1dc67559e05f57cc0f68bdd
make check
  PASS (15 units; 3 existing compiler warnings)
```

The Git source, Rust channel plus cargo/rust-std/rustc component archives, LLVM installer, Buildx
asset, Ubuntu manifest/child, BuildKit manifest/child/config, and three action commits were
independently re-fetched or registry/API-resolved and matched the repaired ledger. The helper
framing golden also regenerated exactly. The initial design head passed GitHub Actions run
`30609856487`; that check evidence becomes stale after the repair push. No completion or
image-publication claim has been made.

## Constraints and intentional state

- This branch changes only `docs/specs/git-245-compat-image.md` and `HANDOFF.md`.
- No intentional uncommitted file is expected after the consolidated repair commit.
- Do not publish an image from a pull request or register a tag.
- Do not put `GITHUB_TOKEN`, Docker credentials, package secrets, model data, or machine paths in
  the image, provenance, source lock, or repository.
- Registered image digests are immutable project inputs and have no automated delete path.
- Preserve the existing C6, request, topology, governance, and pin-adoption worktrees; they are not
  scratch directories.
- Do not implement against a proposed Align API or change `.align-revision` before the common
  topology design and implementation merge.
