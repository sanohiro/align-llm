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

The active implementation adds the fixed hosted, capable-only, and serialized target sets to the
Makefile; rejects aggregate-plus-anything invocations at parse time; runs aggregate children through
one deterministic recursive Make boundary; and adds a Python topology oracle/self-test with
bounded child capture, deadline and process-group cleanup, mutation coverage, hostile-value
transport checks, and aggregate concurrency probes. Hosted CI uses that canonical aggregate. The
developer guide, evaluation guide, and pull request template distinguish aggregate evidence from
focused diagnostic checks.

The topology source and documentation are implemented but the strict C0 baseline commit chain has
not started. No image was built or published, no package database was introduced, and the existing
local LLVM 22.1.8 installation was neither installed nor modified by this work.

## Exact next steps

1. Commit the audited source state, then record the required two-sample pending baseline from that
   exact clean source commit.
2. Commit the projected immutable oracle separately, finalize the canonical baseline in a third
   commit, and verify source/oracle/finalization ancestry and negative cases.
3. Run `make ci`, open the implementation pull request, complete the required comprehensive review,
   apply at most one consolidated repair, and merge only with passing checks and no valid finding.
4. Refresh `main`, run the bounded retrospective, then redesign the locked-input and audit slice on
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
```

The self-test also passed its GNU Make 4.4.1 `--shuffle=reverse -j8` child-isolation regression.
The canonical baseline chain, full `make ci`, and pull request review are not yet complete.

## Constraints and intentional state

- Preserve the strict baseline source -> oracle -> finalization commit chain and merge it with a
  merge commit so the recorded source and oracle commits remain ancestors of the exact merged head.
- Keep the target order and exact topology oracle synchronized across the Makefile, checker,
  workflow, and design of record.
- Do not update `.align-revision`, begin dependent adoption work, build or publish a compatibility
  image, or alter the host LLVM installation in this slice.
- The active worktree intentionally contains the uncommitted topology implementation until the
  source-commit audit is complete; do not discard it.
