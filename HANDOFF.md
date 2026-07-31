# Session handoff

Read `CLAUDE.md` first. This file records durable execution state only; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/git-245-locked-inputs-redesign-v2`
- Base: `4ad70bef2ca757d7174b5f14ff901c31a8c3ae88` (`origin/main`, topology merge)
- Active goal: the locked-input/audit design is authored and locally verified; open, review, and
  merge it before Git 2.45 compatibility image construction.
- Design paths: `docs/specs/git-245-compat-image.md` and the target-list amendment in
  `docs/specs/check-gate-topology.md`.
- Product implementation, Docker construction, hosted image build, publication, provenance, and
  registration have not started.
- Pinned Align commit remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.

PR #30 merged the common deterministic check-gate topology. Its baseline source, immutable oracle,
and canonical finalization commits are respectively
`9b9e9b83f045596697feb800eac7acaa7416b7d9`,
`2f00046a6353ec1574cc1b62811d28b40f1a76a1`, and
`28906f192c6b914205dd2db44e21923cbe34f706`; all remain ancestors of the merge. The exact
post-merge provenance block, topology self-test, and topology Make target pass from a detached
checkout of merged `main`.

The bounded retrospective found three reusable implementation lessons, all already captured by
the merged code or design matrix: every operation after successful process launch belongs inside
the cleanup guard; a negative fixture must prove all non-targeted result dimensions clean before
claiming its intended rejection; and every normative diagnostic bound needs a direct closure-matrix
regression. The old stale topology implementation was not used. No separate governance slice is
queued from that merge.

The closed locked-input design PR exposed three prerequisites for this redesign. The common
topology is now merged. The real archive audit no longer receives raw Make values: its only public
entrypoint is a fixed `/usr/bin/env -i` command with no path or operation argument, and it creates
and owns a random root directly below `/tmp`. The offline unit remains the sole new Make target.
Both modes require the exact empty-derived process environment and explicitly declare Ubuntu 24.04
x86_64, CPython 3.12, and GNU Make 4.3 as the minimum hosted contract; newer author environments
are supplementary.

## Exact next steps

1. Open the design pull request and run the one comprehensive independent review required by
   `CLAUDE.md`.
2. Apply any valid findings in one consolidated repair, run a conditional final review only if its
   material-change trigger applies, and merge only after required checks pass.
3. From refreshed `main`, implement the exact locked inputs, shared production/self-test audit
   executable, one offline Make target, topology oracle update, and identity-coupled baseline refresh
   as the next separate branch.

## Verification

Verified on 2026-07-31 after the topology merge:

```text
source/oracle/finalization ancestry to origin/main   PASS
section 2.4 post-merge provenance block              PASS
python3 -B scripts/check-gate-topology --self-test   PASS
make gate-topology-check                             PASS
```

Verified on 2026-07-31 for the current design diff:

```text
canonical sources.json bytes/hash/re-encoding            PASS
git diff --check                                         PASS
make -j8 ci                                               PASS
```

## Constraints and intentional state

- This branch is design-only. Do not add the lock, LLVM installer, audit executable, Makefile
  implementation, Dockerfile, workflow implementation, image, or registry operation here.
- The later implementation must refresh the Makefile-bound baseline with the strict source ->
  oracle -> finalization sequence and merge with a merge commit.
- Do not update `.align-revision`, alter the host LLVM installation, or publish/register an image in
  this design slice. Publication and visibility changes require explicit repository-owner authority.
- The branch is expected to be clean after the design commit containing this handoff.
