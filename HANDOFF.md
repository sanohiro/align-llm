# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-prompt-context-redesign`, based on `origin/main` commit
  `736cd4cfaff62489e7096f6d696d117d2e57f077` (merged PR #36; PR #34 is also included).
- Current branch merge commit: `27712de`; C6 repair commit is `6a09347` (`Close C6 design review
  findings`), and design content is in `80b8f7b` (`Redesign C6 prompt optimizer contract`), on
  top of `22186b8` (`Record C6 final-review redesign stop`).
- Active goal: make the C6 design merge-ready, open one focused design PR, merge it, and then
  start the first eligible implementation slice. C6 product implementation has not started.
- C0 through C5 are complete. PR #34 delivered the merged fixture-only prompt renderer; it did
  not complete C6.
- Plan of record: `docs/specs/c6-prompt-context-optimizer.md`.
- Pinned Align revision: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` (#672).

## Completed in the active redesign

- Added Request 13 as the exact prerequisite for recursive owned C6 JSON artifact graphs; C6
  persistence now has an explicit bounded-reader, `.clone()`, owner-lifetime, and Request 12/13
  boundary.
- Replaced direct child-supplied environment identity with explicit probe carriers and a
  non-circular evaluator-owned `EnvironmentIdentityCore` preimage, including `None` for an
  unavailable logical CPU count.
- Closed explicit byte/count bounds for identifiers, paths, command vectors, endpoints,
  environment policy, workspaces, task inputs, and expanded trees.
- Defined one-shot proposal credential lifetime, pre-truncation redaction, and the content-bound
  seed capability attestation.
- Defined bounded derived IDs, tagged corpus revision identity, and TREE root metadata.
- Added a closure table mapping the ten previous final-review classes to the first owning slice and
  exact acceptance fixture names.

## Exact next steps

1. Push the merge-dependent Handoff correction and obtain fresh base-tip integration evidence for
   PR #35; its comprehensive review envelope is already recorded and does not need to be repeated.
2. Merge PR #35 after its final check passes. The separate verification-timing governance PR #36
   already merged at `736cd4c`.
3. Refresh `main`, perform one bounded retrospective, and begin the first eligible C6b
   implementation slice. Do not code against proposed Align APIs; a blocked slice resumes only
   after the named Align commit is release-built, pinned, and verified through `make ci`.

## Latest durable verification

- `git diff --check`: passed after consolidated repair commit `6a09347`.
- Markdown fenced-block parity: passed (`70` C6-spec fences; `82` request-register fences).
- Canonical digest vector: passed (`21780af056f4245f2796e186c88064abe911ea287094dd22b4b3b9c8c07c4328`).
- Independent adversarial review: completed against head `e187f82`; four valid findings were
  fixed together in `6a09347` (unknown-field canonicalization, credential injection, seed-base
  provenance, and C6g1 slice prerequisites).
- Governance PR #36 hosted supported check: PASS (`30725231172`); its workflow now keeps the
  required check name while routing documentation-only changes to static verification.
- Full `make ci` has intentionally not been rerun for the current documentation-only redesign;
  it is reserved for the applicable implementation/adoption or final integration gate.

## Constraints and decisions to preserve

- Request 5 blocks provider proposal/real-provider work; Request 7 blocks C6 artifact work;
  Requests 8 and 10 own recursive runtime construction; Request 11 owns bounded child capture;
  Request 12 owns bounded canonical encoding; Request 13 owns recursive owned artifact graphs.
  Requests 6 and 9 remain independent of C6.
- C6 must not use a borrowed JSON view after its input buffer expires, concatenate JSON fragments,
  invent a private wire format, or target any proposed Align API.
- Full tests and CI are evidence gates for coherent implementation/adoption slices, not an edit
  loop. Docs-only edits use structural/document checks; targeted tests run after a coherent code
  slice; full `make ci` runs only at the explicitly applicable final/integration gate.
- Review is one comprehensive pass. Consolidate valid findings, rerun only affected verification,
  and require another review only for a material behavior/design/contract expansion.
- The explicit verification-timing and review-convergence rule is recorded in `CLAUDE.md` and
  enforced by the merged CI scope guard from PR #36; keep future governance and product slices
  separate.
- Source, documentation, diagnostics, commits, pull requests, reviews, and releases remain in
  English.
