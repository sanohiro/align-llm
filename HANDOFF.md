# Session handoff

Read `CLAUDE.md` first. This file records durable execution state only; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/check-gate-topology-implementation-v2`
- Base: `a29d707aa76872ed280780022c329c2cced1e480` (`origin/main`)
- Active goal: implement and merge the reviewed common check-gate topology on current `main` before
  any compiler-pin adoption or locked-input image work.
- Design of record: `docs/specs/check-gate-topology.md`, merged at `e0c37a7` and subsequently
  amended on `main`.
- The earlier implementation branch `agent/check-gate-topology-implementation` is preserved as
  historical evidence but is not a merge source: it predates current `main`, used obsolete
  serialization, and omitted the current `ci` aggregate contract.
- C6 product implementation and every `.align-revision` change remain blocked on this common
  prerequisite.
- Baseline source commit: `9b9e9b83f045596697feb800eac7acaa7416b7d9`.
- Immutable oracle commit: `2f00046a6353ec1574cc1b62811d28b40f1a76a1`.
- Canonical finalization commit: `28906f192c6b914205dd2db44e21923cbe34f706`.

The active implementation adds the fixed hosted, capable-only, and serialized target sets to the
Makefile; rejects aggregate-plus-anything invocations at parse time; runs aggregate children through
one deterministic recursive Make boundary; and adds a Python topology oracle/self-test with
bounded child capture, deadline and process-group cleanup, mutation coverage, hostile-value
transport checks, and aggregate concurrency probes. Hosted CI uses that canonical aggregate. The
developer guide, evaluation guide, and pull request template distinguish aggregate evidence from
focused diagnostic checks.

The topology implementation and strict C0 baseline chain are complete. The positive provenance
block, all specified scalar and linear negative cases, all four merge-hidden path cases, and the
capable aggregate pass. Post-launch child setup is inside the fail-closed cleanup guard, synthetic
child rejection tests isolate their intended discriminator, and oversized diagnostics have an exact
regression. Review attestations and check status remain in GitHub rather than this file. No image
was built or published, and the existing local LLVM 22.1.8 installation was neither installed nor
modified by this work.

## Exact next steps

1. Complete the external review and check workflow for the exact branch state, and merge with a
   merge commit only after every check passes and no valid finding remains.
2. Verify the three baseline commits remain ancestors of refreshed `main` and rerun the structural
   block.
3. Run the bounded retrospective, then redesign the locked-input and audit slice on
   top of the merged topology. The redesign must use a direct fixed-name command boundary rather
   than raw Make command-line value transport and must declare the minimum hosted Python/platform
   contract.

## Verification

Verified on 2026-07-31 in the active worktree:

```text
python3 -B scripts/check-gate-topology --self-test   PASS
make gate-topology-check                             PASS
make -j8 ALIGNC=<sibling release alignc> \
  hosted-checks                                      PASS
section 2.4 positive provenance block                PASS
isolated scalar/linear provenance negatives          PASS (15 categories)
isolated merge-hidden provenance negatives           PASS (4 path classes)
make -j8 ci                                          PASS
```

The self-test also passed its GNU Make 4.4.1 `--shuffle=reverse -j8` child-isolation regression.
The refreshed deterministic-reference samples were 1,139,986,113 ns and 1,193,505,562 ns with a
1,166,745,837 ns median. This identity refresh makes no performance claim.

## Constraints and intentional state

- Preserve the strict baseline source -> oracle -> finalization commit chain and merge it with a
  merge commit so the recorded source and oracle commits remain ancestors of the exact merged head.
- Keep the target order and exact topology oracle synchronized across the Makefile, checker,
  workflow, and design of record.
- Do not update `.align-revision`, begin dependent adoption work, build or publish a compatibility
  image, or alter the host LLVM installation in this slice.
- The branch is expected to be clean after this handoff update is committed.
