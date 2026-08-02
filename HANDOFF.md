# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6b-prompt-context-renderer`, PR checkpoint `0d28a01` with an intentional
  re-scoped working tree; based on `main` commit `ac10ccf6a8a38c4732153da85bf6546159e54bf3`.
- PR #35 merged the C6 prompt optimizer contract. PR #36 and PR #37 merged the verification-timing
  and review-convergence governance, including PR and `main` push scope guards.
- Active goal: publish and merge the independently testable C6b renderer core. The implementation
  has been re-scoped to exclude failure-memory adoption, which is blocked by Align Request 7;
  local focused verification is complete and commit/push plus one fresh review remain. C0 through
  C5 are complete.
- This slice implements fixed prompt hierarchy, learned append validation, bounded patch and
  diagnostic contexts, UTF-8-safe truncation, and SHA-256 identity. It deliberately emits the
  failure-memory section as `(omitted)` without accepting or decoding JSONL. Canonical artifact
  declarations and persistence remain owned by the blocked C6a1/C6a2 slices and are not implemented
  here.
- Intentional uncommitted re-scope files: `Makefile`, the C6 and check-topology specs,
  `scripts/check-gate-topology`, `scripts/run-prompt-model-smoke`, `src/prompt_model.align`, and
  `src/prompt_model_smoke.align`. `src/failure_memory.align` is restored to the C5 baseline.
- Request 7 is still `PROPOSED` and blocks escaped-string declared-record decoding. The pinned
  `json.decode` returns `Err` for valid escaped `MemoryEvent` strings; do not use `json.doc`, a
  hand-written compatibility parser, or another private wire format to bypass the request.
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

1. Commit and push the re-scoped renderer core. The existing terminal review is bound to the old
   scope; run one fresh comprehensive review for this material contract change.
2. Resolve any valid findings in one consolidated repair, rerun only affected focused checks, and
   merge PR #38 after the hosted supported checks and review evidence are complete. Do not start a
   repair/re-review loop for ordinary finding repairs.
3. After Request 7 is merged, rebuild the pinned Align release, update `.align-revision`, and pass
   the deferred failure-memory acceptance through `make ci` before adding that API.

## Bounded post-merge retrospective

- Root cause: the original scope guard handled pull requests but treated every `main` push as a
  full-suite event, so documentation-only merges still caused unnecessary hosted work.
- Reusable rule: classify both pull-request and push ranges; use `--no-renames` and treat checkout
  attributes as executable contract inputs. Keep one comprehensive review and one consolidated
  repair; ordinary finding repairs do not trigger another review.
- The rule is now encoded in `CLAUDE.md` and `.github/workflows/ci.yml`. No additional governance
  slice is queued.

## Latest durable verification

- `git diff --check`: passed after consolidated repair commit `6a09347`.
- Markdown fenced-block parity: passed (`70` C6-spec fences; `82` request-register fences).
- Canonical digest vector: passed (`21780af056f4245f2796e186c88064abe911ea287094dd22b4b3b9c8c07c4328`).
- Independent adversarial review for PR #35: completed against head `e187f82`; four valid findings
  were fixed together in `6a09347` (unknown-field canonicalization, credential injection,
  seed-base provenance, and C6g1 slice prerequisites).
- PR #35 merged as `0fc204f` after its review and integration gate.
- `git diff --check`: passed after consolidated repair commit `de29b56`.
- Ruby YAML parse of `.github/workflows/ci.yml`: passed after `de29b56`.
- The workflow-change hosted check passed once; its transient check evidence remains in GitHub.
- Local full `make ci` was intentionally not rerun for this documentation/governance change; it is
  reserved for the applicable implementation/adoption or final integration gate.
- `make check`: PASS (15 per-unit checks; three pre-existing compiler warnings).
- `make prompt-model-smoke`: PASS (hierarchy, UTF-8-safe bounds including truncation, memory
  selection in the prior scope; the current re-scoped smoke passes hierarchy, UTF-8-safe bounds,
  source validation, invalid input, and SHA-256).
- `scripts/run-prompt-render-smoke`: PASS (C5 legacy renderer remains unchanged).
- `scripts/check-format` and `git diff --cached --check`: PASS before commit.
- Repair commit `835fb07`: policy/source caps, schema-version rejection, `INVALID_INPUT`, and
  focused invalid-input smoke cases; `make check`, `make prompt-model-smoke`, C5 smoke,
  `scripts/check-format`, and `git diff --check` all passed.
- Hosted check for repair head `9fd8e0d`: PASS (`Pinned Align compiler and supported checks`,
  1m27s).
- Conditional final review for head `9fd8e0d`: changes requested; four findings recorded in PR #38,
  with Request 7 as the blocking issue. It is terminal for the old scope; the re-scoped contract
  requires one fresh review.
- Current re-scope focused verification: `make check` PASS with three pre-existing warnings,
  `make prompt-model-smoke` PASS, `make build` PASS, `scripts/run-prompt-render-smoke` PASS,
  `make gate-topology-check` PASS, `scripts/check-format` PASS, and `git diff --check` PASS.

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
  enforced by the merged CI scope guards from PR #36 and PR #37; keep future governance and
  product slices separate.
- Source, documentation, diagnostics, commits, pull requests, reviews, and releases remain in
  English.
