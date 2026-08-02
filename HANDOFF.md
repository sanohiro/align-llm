# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6c2-verifier-design`; the branch is based on merged `main` commit
  `67f36ebaaaf0ae5d7ec644c607b51a77c3fc5dcf`.
- Current source checkpoint: merged C6c1 implementation at
  `1029eec641bce338c5ba7b878101b7a0daab28e9`; the consolidated C6c2 design repair is committed at
  `c7e4a1f7f25c041e4466f2db13c3246baeec1b21` and the implementation slice has not started.
- Active goal: design, independently review, and merge the pure C6c2 evaluation-document verifier
  before opening its implementation slice. C6c1 implementation, review repair, final verification,
  and merge are complete.
- Complete: `src/prompt_score.align`, its deterministic scalar-column smoke, the `prompt-score-smoke`
  Make target, the topology oracle update, the review repair rejecting benchmark values on `ERROR`
  rows, and the required merge-commit integration.
- Complete: the identity-bound baseline refresh is complete with source commit
  `4b3019a83598cfbae7feecdc88732b855c2e31c4`, immutable oracle commit
  `5338951e77415a21c42fbe030494c55d015f3542`, and finalization commit
  `bc386d8`.
- Complete: baseline structural verification, the local implementation/adoption integration gate,
  the consolidated review repair, its final-head `make ci` rerun, hosted CI, and the bounded
  post-merge retrospective.
- In progress: consolidate the C6c2 design-review repair, run its conditional final review, and
  merge the design before implementation.
- Not started: C6c2 implementation, its focused smoke/topology registration, and its implementation
  pull request.
- The working tree is clean after the consolidated design repair; no generated binaries, model
  weights, credentials, or machine-specific paths may be committed.
- Plan of record: `docs/specs/c6-prompt-context-optimizer.md`.
- Pinned Align revision: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` (#672).

## C6c1 implementation boundary

- `prompt_score` is pure and allocation-free at the public boundary. It accepts borrowed `Copy`
  rows and task limits, validates exact alternating row order and the complete row state machine,
  computes task/corpus counts, paired medians, ppm metrics, and complete ordered reasons, and
  writes only caller-owned primitive output columns.
- The pinned compiler accepts `slice<Struct>` input and whole-struct reads but rejects whole-element
  and field-level stores through `out slice<Struct>`. The implementation therefore uses the merged
  scalar-column contract and does not add a compatibility layer or target a proposed Align API.
- Any malformed or undersized call returns before output mutation. Structurally valid `ERROR` rows
  return `EVALUATION_ERROR`; malformed rows return `INVALID_INPUT`.
- The smoke covers passing odd/even medians, ppm rounding, paired and corpus repair/time reasons,
  benchmark reasons, mixed PASS/FAIL/POLICY rows, valid ERROR rows, row/order/plan failures, task
  and reason output capacity failures, and sentinel-preserving early exits.
- The implementation retains no filesystem, process, network, JSON, provider, persistence, or
  failure-memory behavior. Request 7 remains `PROPOSED`; its escaped-string JSON gap still blocks
  the later failure-memory adoption slice.

## Exact next steps

1. Commit and push the consolidated C6c2 design repair, update the PR disposition, run the required
   conditional final comprehensive review, and merge the design pull request before implementation.
2. Create the C6c2 implementation branch from the merged design, add the pure verifier and its
   document smoke/topology target, then run the focused and final aggregate gates. Do not start
   failure-memory JSONL adoption until Request 7 is accepted, merged at a named Align commit, the
   pinned release is rebuilt, `.align-revision` is updated, and `make ci` passes the original gate.

## Latest verification

- `./scripts/alignc check-per-unit src/prompt_score.align`: PASS; only the expected large
  `ScoreResult` Copy-return warnings remain because the public contract requires plain Copy results.
- `make prompt-score-smoke`: PASS; deterministic validation, medians, ppm, reasons, capacity, and
  untouched-output checks all pass, including malformed benchmark data on an `ERROR` row.
- `make gate-topology-check`: PASS after registering `prompt-score-smoke` in the Makefile and its
  embedded topology oracle.
- `python3 scripts/check-gate-topology --self-test`: PASS.
- `python3 eval/runners/record-baseline.py ... --samples 2`: PASS; pending measurement binds to
  source commit `4b3019a83598cfbae7feecdc88732b855c2e31c4`.
- `python3 scripts/finalize-canonical-baseline.py ... --oracle-commit
  5338951e77415a21c42fbe030494c55d015f3542`: PASS; canonical baseline and digest were committed in
  `bc386d8`, and the pending file was removed.
- `make check`: PASS (15 existing main units; the repository's pre-existing compiler warnings are
  unchanged).
- `make baseline-check`: PASS, including canonical provenance, immutable oracle, malformed-input,
  and Git isolation checks.
- `make ci`: PASS with the pinned release compiler; topology, all hosted/capable focused checks,
  coding-v1, `prompt-score-smoke`, and baseline verification all passed.
- Post-merge SHA and ancestry: merge commit `67f36ebaaaf0ae5d7ec644c607b51a77c3fc5dcf` preserves
  C6c1 source `4b3019a83598cfbae7feecdc88732b855c2e31c4`, oracle
  `5338951e77415a21c42fbe030494c55d015f3542`, and finalization
  `bc386d8297d21bc0dc125fe71002f019108ea28e` as ancestors.
- `make fmt`, `./scripts/check-format`, and `git diff --check`: PASS.
- C6c2 design repair commit `c7e4a1f7f25c041e4466f2db13c3246baeec1b21` and `git diff --check`: PASS;
  source tests, `make check`, `make build`, and `make ci` are N/A until the implementation slice
  exists because this repair changes documentation only.

## Constraints and decisions to preserve

- Request 5 blocks provider proposal/real-provider work; Request 7 blocks C6 artifact and
  failure-memory JSON work; Requests 8 and 10 own recursive runtime construction; Request 11 owns
  bounded child capture; Request 12 owns bounded canonical encoding; Request 13 owns recursive
  owned artifact graphs. Requests 6 and 9 remain independent.
- C6 must not use a borrowed JSON view after its input buffer expires, concatenate JSON fragments,
  invent a private wire format, or code against any proposed Align API.
- C6c2's pure verifier now requires caller-owned `PromptVerifierTrust` and an independent expected
  producer-input digest table, and requires embedded experiment/parent-activation records beside
  their references. It validates `FIXTURE` as non-gate, preserves strict `IMPROVED` as a valid
  non-gate comparison, enforces status-specific error families, and closes the attestation trace at
  the first failing invocation. A document-only caller cannot supply authenticating evidence from
  the result file itself; future acceptance must provide the same external trust/evidence inputs or
  fail closed.
- Verification is evidence for coherent slices: use focused checks after implementation coherence
  and run full `make ci` only at the named adoption/integration gate. Keep one comprehensive review
  and one consolidated repair; a material redesign requires re-scoping and another review.
- Retrospective lesson: the C6c1 review caught a missing optional-measurement/state combination;
  the existing Cartesian-coverage rule was sufficient once the missing `ERROR` benchmark fixture
  was added. Treat state × optional-field combinations as mandatory evidence in C6c2 and later
  verifier reviews; no separate governance change is queued because the rule and regression now
  exist in the design and smoke contract.
- All source, diagnostics, developer documentation, commits, pull requests, and review records
  remain in English.
