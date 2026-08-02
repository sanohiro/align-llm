# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-prompt-context-redesign`, based on `origin/main` commit
  `99837e29ec303574956614a1d26439def23e9e8d` (merged PR #34).
- Current repair commit: `6a09347` (`Close C6 design review findings`); design content is in
  `80b8f7b` (`Redesign C6 prompt optimizer contract`), on top of `22186b8` (`Record C6
  final-review redesign stop`). This handoff update is the next commit; the worktree is clean
  after it.
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

1. Publish the focused C6 design PR with the exact structural verification evidence below.
2. Record the one comprehensive review envelope for head `e187f82`, base/merge-base
   `99837e29`, with four findings and consolidated repair commit `6a09347`; do not start another
   review for these ordinary finding fixes.
3. Create the separate governance slice that records verification timing and review-convergence
   rules in `CLAUDE.md`; do not mix it into the C6 design PR.
4. After the required PRs merge, refresh `main`, perform one bounded retrospective, and begin the
   first eligible implementation slice. Do not code against proposed Align APIs; a blocked slice
   resumes only after the named Align commit is release-built, pinned, and verified through
   `make ci`.

## Latest durable verification

- `git diff --check`: passed after consolidated repair commit `6a09347`.
- Markdown fenced-block parity: passed (`70` C6-spec fences; `82` request-register fences).
- Canonical digest vector: passed (`21780af056f4245f2796e186c88064abe911ea287094dd22b4b3b9c8c07c4328`).
- Independent adversarial review: completed against head `e187f82`; four valid findings were
  fixed together in `6a09347` (unknown-field canonicalization, credential injection, seed-base
  provenance, and C6g1 slice prerequisites).
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
- The explicit verification-timing rule still needs to be recorded in `CLAUDE.md` as a separate
  governance slice; do not mix that change into the C6 design PR.
- Source, documentation, diagnostics, commits, pull requests, reviews, and releases remain in
  English.
