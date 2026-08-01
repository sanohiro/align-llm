# Session handoff

Read `CLAUDE.md` first. This file records only durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-prompt-context-design`, based on `origin/main` commit
  `4e1482e8e4942b70a9576f96285c0bf02aaaaae9` (Request 9 PR #33 merge).
- Relevant commits: `bdcd1f6` (`Draft C6 prompt optimizer contract`), `29694d6` (`Align C6 design
  with current prerequisite register`), `15b3d95` (`Record C6 design verification`), and
  `52bf28a` (`Close C6 design review gaps`), the current repaired design head.
- Active goal: complete the C6 prompt/context optimizer design, merge it, then continue through the
  eligible enabling and implementation slices.
- C0 through C5 are complete. The current product slice is design only; no C6 Align source exists.
- Plan of record: `docs/specs/c6-prompt-context-optimizer.md`.
- Pinned Align revision: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` (#672).
- Request 5 remains `PROPOSED` and blocks the C6 provider-proposal and real-provider gates.
- Request 6 is recursively-Copy `json.scan` row eligibility, Request 7 is escaped strings in
  declared-record JSON, Request 8 is merged as PR #32 but not adopted by a real consumer, and
  Requests 10, 11, and 12 now own C6's recursive evaluator fields, bounded child capture, and
  bounded canonical encoding. Request 9 is merged as PR #33 at
  `4e1482e8e4942b70a9576f96285c0bf02aaaaae9` but is not a C6 dependency. C6 must use the current
  numbering and must not target any proposed Align API.

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
- Closed the design-review repair classes for explicit adapter requests, environment isolation and
  identity production, recursive record ownership, physical paths, compatibility floor, commit
  reachability, operation overlap, syntax-fixture deferral, and the three new Align requests.
- Recovered the worktree from earlier C6/Git-compatibility-image index conflicts without altering
  separate branches.

## Exact next steps

1. Run a fresh complete adversarial review of the repaired C6 design at `52bf28a`; do not edit
   content while that review is in progress.
2. Open and merge the design PR after its review evidence and final integration checks are
   recorded.
3. Continue with the first eligible post-design slice. C6a waits for Request 7 and Request 12;
   C6f2 waits for Requests 8, 10, and 11; no code may target a proposed Align API.

## Latest durable verification

The repaired design is committed as `52bf28a`. The author consistency pass, `git diff --check`,
Align-pin/reference checks, canonical SHA-256 vector, and `make ci` passed on the repaired tree
(pinned Align release build, topology, format, existing unit/smoke gates, coding-task boundaries,
timeout, and baseline validation). The fresh final adversarial review and design PR remain pending.

## Constraints and intentional state

- Preserve the C6 design draft on `agent/c6-prompt-context-design`.
- Preserve `/home/hiro/prj/align-llm-governance` and the other registered worktrees; they belong to
  other branches and are not scratch directories for C6.
- Request 5 owns bounded HTTP response reception. Request 7 owns escaped JSON strings. Request 8
  owns the separate record-builder base, Request 10 owns recursive evaluator fields, Request 11
  owns bounded child-process capture, Request 12 owns bounded canonical encoding, and Request 9
  owns direct owned JSON fields.
- Do not code against a proposed Align API. A blocked slice resumes only after the named Align
  commit is merged, release-built, pinned, and verified through the original align-llm gate.
- Source, documentation, diagnostics, commits, pull requests, reviews, and releases remain in
  English.
- There are no intentional uncommitted files after the repair commit; generated CI cache
  directories were moved outside the repository.
