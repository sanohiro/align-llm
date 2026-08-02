# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6c1-score-kernel-impl`; implementation is based on merged `main` commit
  `95670134f6f7c503aeae15c7cbebe38434bdc617`.
- Current source checkpoint: the clean implementation commit at this branch's `HEAD`; its parent
  is the exact merged design checkpoint `95670134f6f7c503aeae15c7cbebe38434bdc617`.
- Active goal: implement, verify, review, and merge the independently testable pure C6c1 row
  validation and aggregation kernel. The C6c1 design and its pinned-Align contract repair are
  merged; implementation is the active slice.
- Complete: `src/prompt_score.align`, its deterministic scalar-column smoke, the `prompt-score-smoke`
  Make target, and the topology oracle update are implemented in the working source checkpoint.
- In progress: commit this coherent implementation checkpoint, then refresh the identity-bound
  baseline through the prescribed source -> immutable-oracle -> finalization sequence.
- Not started: full integration verification, the implementation pull request and review, hosted
  checks, merge, and the bounded post-merge retrospective before C6c2 selection.
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

1. Commit the clean implementation source checkpoint, record its exact SHA here, and run the
   prescribed baseline source -> pending measurement -> immutable oracle -> finalization sequence.
   The Makefile/check graph is identity-bound, so do not skip or manually edit the baseline outputs.
2. Run `make baseline-check`, the focused C6c1 checks, `make check`, `make build`, and the applicable
   full `make ci` integration gate after the baseline sequence. Record exact results here.
3. Open one implementation pull request with English description and exact verification results;
   obtain one fresh independent comprehensive review, apply valid findings in one repair, rerun
   affected checks, and use the required native GitHub review envelope and merge commit.
4. After merge, perform the bounded retrospective, refresh `main`, and select the next eligible
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
- `make check`: PASS (15 existing main units; the repository's pre-existing compiler warnings are
  unchanged).
- `make fmt`, `./scripts/check-format`, and `git diff --check`: PASS.
- Full `make ci` and baseline refresh are pending for this implementation/adoption gate.

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
