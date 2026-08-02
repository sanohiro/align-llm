# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6c2-verifier-rescope`, based on merged `main` commit
  `67f36ebaaaf0ae5d7ec644c607b51a77c3fc5dcf` (C6c1 PR #41 merge commit).
- Current source checkpoint: `7935d95` (`Rescope C6c2 around decoded trace verification`), based on
  merged `main` commit `67f36ebaaaf0ae5d7ec644c607b51a77c3fc5dcf` (C6c1 PR #41 merge commit).
- Active goal: finish, independently review, and merge the re-scoped C6c2 pure decoded evaluation
  verifier design. The seven findings from the first comprehensive review are repaired in one
  design commit; implementation is not started and must wait for the reviewed design plus the
  C6a1/C6a2 decoded-record and Align adoption prerequisites.
- Complete: C6c1 implementation, review repair, hosted checks, merge, and the bounded retrospective.
- Complete: superseded PR #42's initial review repair and final-review evidence are recorded on
  GitHub, but PR #42 is intentionally unmerged and not merge-ready.
- Complete: the re-scoped C6c2 design now consumes borrowed, decoded, content-validated result and
  evidence records; persists the execution trace contract; takes explicit verifier source paths and
  expected identities; binds expected align-llm commit to the result environment; and references
  the evidence sidecar from `PromptGateManifest`.
- In progress: push repair commit `7935d95`, update PR #43's review disposition, and run the
  conditional final comprehensive design review.
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

1. Push `7935d95` and update draft PR #43 with the initial review envelope `4838096926`, seven
   valid findings, their consolidated-repair disposition, and the repair checkpoint.
2. Run the conditional final comprehensive review against `main`. If it finds another non-trivial
   issue, stop the local repair loop and re-scope/redesign a new slice; do not repair this PR again.
   If it is clean, record the final SHA-bound envelope, wait for the required documentation check,
   and merge PR #43.
3. After the design merge, select C6c2 implementation only if C6a1/C6a2 provide content-validated
   decoded records and Requests 7/8/10/12/13 are adopted at named Align revisions; otherwise record
   the dependency blocker and continue only with safe independent roadmap work.
4. Do not start JSON/document binding or failure-memory JSONL adoption until Request 7 is accepted,
   merged at a named Align commit, the pinned release is rebuilt, `.align-revision` is updated, and
   `make ci` passes the original acceptance gate.

## Latest verification

- C6c1 final evidence remains PASS: focused smoke, `make check`, `make fmt`, format/static checks,
  `make ci`, and hosted final-head CI run `30739108014` all passed before PR #41 merged.
- PR #42 final-review evidence is recorded as GitHub review `4838027797`; its alternate independent
  reviewer found four valid findings. The two long-running primary review attempts were terminated
  after no verdict and are not review evidence.
- PR #43 initial comprehensive review evidence is recorded as GitHub review `4838096926` against
  head `3b4f9595420b58a6f24c544124e8a1aa4f425395`; the reviewer found seven valid findings, all
  addressed by `7935d95`. A conditional final review is still required because the repair materially
  changed the design.
- Current design-slice verification: `git diff --check` PASS and Markdown fence count 82 (even),
  PASS. Source tests and `make ci` are N/A because this remains documentation/specification-only;
  hosted documentation/static checks are required after the repair is pushed.

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
  `VERIFIED`; `UNVERIFIED` remains a valid non-gate comparison. `PromptEvaluateRequest` owns the
  explicit source paths and expected identities; `PromptGateManifest` owns the checked-in evidence
  reference. The verifier validates the persisted workspace/snapshot/input-snapshot/attestation
  trace and exact error prefix. Its C6c1 adapter uses Request 8/10-shipped temporary record/scalar
  construction only; no fixed-size workaround or duplicated scorer is allowed.
- Verification is evidence for coherent slices: use focused checks after implementation coherence
  and run full `make ci` only at the named adoption/integration gate. Keep one comprehensive review
  and one consolidated repair; a material redesign requires re-scoping and another review.
- All source, diagnostics, developer documentation, commits, pull requests, and review records
  remain in English.
- Intentional uncommitted files: none at the last committed checkpoint; the next handoff must
  preserve the clean tree and the PR #43 review boundary.
