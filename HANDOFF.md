# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6c2-verifier-rescope`, based on merged `main` commit
  `67f36ebaaaf0ae5d7ec644c607b51a77c3fc5dcf` (C6c1 PR #41 merge commit).
- Current source checkpoint: `a27c3de` (`Rescope C6c2 as decoded evaluation verifier`), based on
  merged `main` commit `67f36ebaaaf0ae5d7ec644c607b51a77c3fc5dcf`.
- Active goal: finish, independently review, and merge the re-scoped C6c2 pure decoded evaluation
  verifier design. Implementation is not started and must wait for the reviewed design plus the
  C6a1/C6a2 decoded-record and Align adoption prerequisites.
- Complete: C6c1 implementation, review repair, hosted checks, merge, and the bounded retrospective.
- Complete: superseded PR #42's initial review repair and final-review evidence are recorded on
  GitHub, but PR #42 is intentionally unmerged and not merge-ready.
- In progress: replace the rejected whole-document C6c2 contract with a borrowed
  `verify_result(result, evidence)` contract, explicit independent evidence persistence, embedded
  experiment/parent records, and separate align-llm/Align/corpus reachability states.
- Working tree must be clean at the next checkpoint; no generated binaries, model weights,
  credentials, or machine-specific paths may be committed.
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

1. Finish the C6c2 re-scope in `docs/specs/c6-prompt-context-optimizer.md`, including the contract
   ledger and closure matrix; run `git diff --check` and the targeted Markdown/static checks.
2. Run one fresh independent adversarial design review, open a new draft PR from this branch, and
   record the SHA-bound review envelope and all finding dispositions. PR #42's conditional final
   review found four valid findings and is terminal; do not apply another non-trivial repair there.
3. Merge the new reviewed design PR only after its required checks and review evidence pass. Then
   select implementation only if C6a1/C6a2 provide content-validated decoded records; otherwise
   record the dependency blocker and continue only with safe independent roadmap work.
4. Do not start JSON/document binding or failure-memory JSONL adoption until Request 7 is accepted,
   merged at a named Align commit, the pinned release is rebuilt, `.align-revision` is updated, and
   `make ci` passes the original acceptance gate.

## Latest verification

- C6c1 final evidence remains PASS: focused smoke, `make check`, `make fmt`, format/static checks,
  `make ci`, and hosted final-head CI run `30739108014` all passed before PR #41 merged.
- PR #42 final-review evidence is recorded as GitHub review `4838027797`; its alternate independent
  reviewer found four valid findings. The two long-running primary review attempts were terminated
  after no verdict and are not review evidence.
- Re-scope document edits: `git diff --check` PASS; source tests and `make ci` are N/A for this
  documentation-only design slice unless executable contracts change. The final targeted static
  result will be recorded before the design PR is opened.

## Constraints and decisions to preserve

- Request 5 blocks provider proposal/real-provider work; Request 7 blocks C6 artifact and
  failure-memory JSON work; Requests 8 and 10 own recursive runtime construction; Request 11 owns
  bounded child capture; Request 12 owns bounded canonical encoding; Request 13 owns recursive
  owned artifact graphs. Requests 6 and 9 remain independent.
- C6 must not use a borrowed JSON view after its input buffer expires, concatenate JSON fragments,
  invent a private wire format, or code against any proposed Align API. C6c2 specifically consumes
  only C6a1/C6a2 decoded, content-validated records and never parses or canonical-encodes JSON.
- `PromptEvaluationEvidence` is a separate content-bound sidecar with an explicit acceptance input;
  it binds the result digest, independent per-row producer-input digests, and separate reachability
  states for align-llm, external Align, and corpus. A complete gate requires all three states to be
  `VERIFIED`; `UNVERIFIED` remains a valid non-gate comparison.
- Verification is evidence for coherent slices: use focused checks after implementation coherence
  and run full `make ci` only at the named adoption/integration gate. Keep one comprehensive review
  and one consolidated repair; a material redesign requires re-scoping and another review.
- All source, diagnostics, developer documentation, commits, pull requests, and review records
  remain in English.
