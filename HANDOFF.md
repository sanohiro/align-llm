# Session handoff

Read `CLAUDE.md` first. This file records durable execution state only; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/git-245-locked-inputs-redesign-v2`
- Base: `4ad70bef2ca757d7174b5f14ff901c31a8c3ae88` (`origin/main`, topology merge)
- Relevant commit: initial design `5adf639fcb848deabe6e0e9d21624739358fa412`; the consolidated
  contract repair follows it in this branch's history.
- Active goal: finish and merge the locked-input/audit design before Git 2.45 compatibility image
  construction.
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

The repaired design distinguishes GNU Make's pre-recipe control plane from the isolated Python
boundary. The focused target locks `/bin/sh` and `-eu -c`, while only the exact option-free direct
command and the topology-owned option-cleared aggregate child count as acceptance evidence. The
audit admits no redirect, uses one 65,536-byte `readinto` buffer, seeks the accepted download
descriptor to zero before scanning, and scopes any leftover-root guarantee to the current
invocation's retained basename. Its pre-dispatch malformed-vector diagnostic is mode-independent.
The implementation is split into an offline hosted slice and a later direct-network-audit slice;
the full sequential matrix covers the audit with each of the three aggregates in both orders.

## Exact next steps

1. Push the consolidated repair after its local commit.
2. Run the conditional final review because the repair materially changes the Make boundary,
   network contract, and implementation split; merge only if it is clean and required checks pass.
3. From refreshed `main`, implement the offline locked inputs, shared parser/self-test executable,
   one Make target, topology oracle update, and identity-coupled baseline refresh as the first
   implementation branch.
4. After that slice merges, implement and accept the direct real-archive network audit as the
   second implementation branch.

## Verification

Verified on 2026-07-31 after the topology merge:

```text
source/oracle/finalization ancestry to origin/main   PASS
section 2.4 post-merge provenance block              PASS
python3 -B scripts/check-gate-topology --self-test   PASS
make gate-topology-check                             PASS
```

Verified on 2026-07-31 for initial design commit `5adf639`:

```text
canonical sources.json bytes/hash/re-encoding            PASS
git diff --check                                         PASS
make -j8 ci                                               PASS
```

Verified on 2026-07-31 for the consolidated repaired design:

```text
ledger/prose/closure author consistency checks            PASS
canonical sources.json bytes/hash/re-encoding             PASS
target-specific shell override prototype                  PASS
git diff --check                                          PASS
make -j8 ci                                               PASS
```

## Constraints and intentional state

- This branch is design-only. Do not add the lock, LLVM installer, audit executable, Makefile
  implementation, Dockerfile, workflow implementation, image, or registry operation here.
- The offline implementation must refresh the Makefile-bound baseline with the strict source ->
  oracle -> finalization sequence and merge with a merge commit. The later audit implementation
  changes no recorded baseline artifact.
- Do not update `.align-revision`, alter the host LLVM installation, or publish/register an image in
  this design slice. Publication and visibility changes require explicit repository-owner authority.
- The branch is expected to be clean after the consolidated repair commit.
