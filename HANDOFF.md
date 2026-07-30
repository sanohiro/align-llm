# Session handoff

Read `CLAUDE.md` first. This file records only durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-prompt-context-design`, rebasing onto `origin/main` commit
  `4e1482e8e4942b70a9576f96285c0bf02aaaaae9` (Request 9 PR #33 merge).
- Relevant commit: the C6 design commit is being replayed; record its new SHA after the rebase
  completes. The intentional C6 design change is `docs/specs/c6-prompt-context-optimizer.md`.
- Active goal: complete the C6 prompt/context optimizer design, merge it, then continue through the
  eligible enabling and implementation slices.
- C0 through C5 are complete. The current product slice is design only; no C6 Align source exists.
- Plan of record: `docs/specs/c6-prompt-context-optimizer.md`.
- Pinned Align revision: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` (#672).
- Request 5 remains `PROPOSED` and blocks the C6 provider-proposal and real-provider gates.
- Request 6 is recursively-Copy `json.scan` row eligibility, Request 7 is escaped strings in
  declared-record JSON, Request 8 is merged as PR #32 but not adopted by a real consumer, and
  Request 9 is merged as PR #33 at `4e1482e8e4942b70a9576f96285c0bf02aaaaae9` but is not a C6
  dependency. C6 must use the current numbering and must not target any proposed Align API.

The common fresh-compiler check-gate topology and the locked Git 2.45 compatibility-input design
are merged on `main`. Request 8's bounded retrospective found no separate governance slice to
queue: descriptor identity, finite-wire representation, lifecycle blocking, borrow boundaries,
and zero-sized cases are now covered by the review checklist and Request 8 matrix. Its regular
merge preserved the request and Handoff commits as ancestors.

## Completed in the active slice

- Defined the four-command CLI, prompt hierarchy, immutable artifact identity, activation DAG,
  deterministic validation/error order, A/B measurement contract, acceptance policy, rollback,
  ownership, gate evidence, contract ledger, closure matrix, and split delivery order.
- Audited the draft against the parent specifications, review checklist, pinned Align JSON/fs/
  process/crypto surfaces, and independent adversarial reviews.
- Resolved review classes covering missing Align prerequisites, escaped text, Move options, runtime
  record arrays, physical workspace containment, per-run input attestations, secret redaction,
  primary timing boundaries, canonical acceptance/rollback evidence, filesystem error behavior,
  tree topology, and oversized pull-request boundaries.
- Normalized the dependency numbering so Request 7 owns escaped JSON strings and Request 8 owns
  runtime construction of evaluator record arrays; Request 9 is not a C6 dependency.
- Recovered the worktree from earlier C6/Git-compatibility-image index conflicts without altering
  separate branches.

## Exact next steps

1. Finish the rebase onto `origin/main`, restore the intentional uncommitted C6 design edit, and
   record the new design commit SHA in this Handoff.
2. Run the author ledger-to-prose and closure-matrix consistency pass, then verify all literal
   references against the pinned Align checkout and `git diff --check`.
3. Run a fresh full adversarial review of the rebased C6 design, resolve valid findings in one
   consolidated repair, and complete the SHA-bound review workflow.
4. Continue with the first eligible post-design slice. C6a waits for Request 7 to reach
   `ALIGN_MERGED`; no code may target a proposed Align API.

## Latest durable verification

Before this rebase, the C6 draft passed `git diff --check`. Fresh verification is required after
dependency normalization and the merge-base change.

## Constraints and intentional state

- Preserve the C6 design draft on `agent/c6-prompt-context-design`.
- Preserve `/home/hiro/prj/align-llm-governance` and the other registered worktrees; they belong to
  other branches and are not scratch directories for C6.
- Request 5 owns bounded HTTP response reception. Request 7 owns escaped JSON strings. Request 8
  owns the separate record-builder capability, and Request 9 owns direct owned JSON fields.
- Do not code against a proposed Align API. A blocked slice resumes only after the named Align
  commit is merged, release-built, pinned, and verified through the original align-llm gate.
- Source, documentation, diagnostics, commits, pull requests, reviews, and releases remain in
  English.
