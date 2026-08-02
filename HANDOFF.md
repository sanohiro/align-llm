# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6c1-score-kernel-impl`; implementation is based on merged `main` commit
  `95670134f6f7c503aeae15c7cbebe38434bdc617`.
- Current source checkpoint: `4b3019a83598cfbae7feecdc88732b855c2e31c4` (`Implement C6c1 scoring
  kernel`), based on merged design checkpoint `95670134f6f7c503aeae15c7cbebe38434bdc617`.
- Active goal: implement, verify, review, and merge the independently testable pure C6c1 row
  validation and aggregation kernel. The C6c1 design and its pinned-Align contract repair are
  merged; implementation is the active slice.
- Complete: `src/prompt_score.align`, its deterministic scalar-column smoke, the `prompt-score-smoke`
  Make target, and the topology oracle update are implemented in the working source checkpoint.
- Complete: the identity-bound baseline refresh is complete with source commit
  `4b3019a83598cfbae7feecdc88732b855c2e31c4`, immutable oracle commit
  `5338951e77415a21c42fbe030494c55d015f3542`, and finalization commit
  `bc386d8`.
- Complete: baseline structural verification and the local implementation/adoption integration
  gate.
- In progress: prepare the implementation pull request and complete its independent review.
- Not started: hosted review checks, merge, and the bounded post-merge retrospective before C6c2
  selection.
- Working tree is expected to be clean at the source checkpoint; no generated binaries, model
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

1. Open one implementation pull request with English description and exact verification results;
   obtain one fresh independent comprehensive review, apply valid findings in one repair, rerun
   affected checks, and use the required native GitHub review envelope and merge commit.
2. After merge, perform the bounded retrospective, refresh `main`, and select the next eligible
   C6c2 slice. Do not start failure-memory JSONL adoption until Request 7 is accepted, merged at a
   named Align commit, the pinned release is rebuilt, `.align-revision` is updated, and `make ci`
   passes the original acceptance gate.

## Latest verification

- `./scripts/alignc check-per-unit src/prompt_score.align`: PASS; only the expected large
  `ScoreResult` Copy-return warnings remain because the public contract requires plain Copy results.
- `make prompt-score-smoke`: PASS; deterministic validation, medians, ppm, reasons, capacity, and
  untouched-output checks all pass.
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
- `make fmt`, `./scripts/check-format`, and `git diff --check`: PASS.

## Constraints and decisions to preserve

- Request 5 blocks provider proposal/real-provider work; Request 7 blocks C6 artifact and
  failure-memory JSON work; Requests 8 and 10 own recursive runtime construction; Request 11 owns
  bounded child capture; Request 12 owns bounded canonical encoding; Request 13 owns recursive
  owned artifact graphs. Requests 6 and 9 remain independent.
- C6 must not use a borrowed JSON view after its input buffer expires, concatenate JSON fragments,
  invent a private wire format, or code against any proposed Align API.
- Verification is evidence for coherent slices: use focused checks after implementation coherence
  and run full `make ci` only at the named adoption/integration gate. Keep one comprehensive review
  and one consolidated repair; a material redesign requires re-scoping and another review.
- All source, diagnostics, developer documentation, commits, pull requests, and review records
  remain in English.
