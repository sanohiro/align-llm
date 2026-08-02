# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/verification-scope-push`, based on `main` commit
  `0fc204fb2bb47911707b0759e131cc57363063c1`.
- PR #35 merged the C6 prompt optimizer contract. PR #36 merged the verification-timing and
  review-convergence governance, including the CI scope guard.
- Active goal: close the remaining CI scope gap so documentation-only pushes to `main` use static
  verification instead of automatically running the full suite. No product implementation slice
  is active.
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

1. Validate the workflow change, open one focused governance PR, and run one comprehensive review.
2. Apply all valid review findings in one repair, rerun only affected checks, and merge after the
   workflow change's required hosted check passes.
3. Refresh `main`, record the post-merge state, and only then consider the first eligible C6b
   implementation slice. Keep C6b pure and provider-independent; do not code against proposed
   Align APIs.

## Latest durable verification

- `git diff --check`: passed after consolidated repair commit `6a09347`.
- Markdown fenced-block parity: passed (`70` C6-spec fences; `82` request-register fences).
- Canonical digest vector: passed (`21780af056f4245f2796e186c88064abe911ea287094dd22b4b3b9c8c07c4328`).
- Independent adversarial review for PR #35: completed against head `e187f82`; four valid findings
  were fixed together in `6a09347` (unknown-field canonicalization, credential injection,
  seed-base provenance, and C6g1 slice prerequisites).
- Governance PR #36 hosted supported check: PASS (`30725231172`); its workflow keeps the required
  check name while routing documentation-only changes to static verification.
- Final base-tip integration check for PR #35: PASS (`30725342133`) against head `711cb71` and
  tested base tip `736cd4c`; PR #35 then merged as `0fc204f`.
- Current branch verification: `git diff --check` passed after adding push-diff classification;
  workflow execution is pending the governance PR.
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
