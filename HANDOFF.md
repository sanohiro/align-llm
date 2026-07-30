# Session handoff

Read `CLAUDE.md` first. This file records only the current durable execution state; GitHub owns
transient pull request checks, reviews, and attestations.

## Current state

- Branch: `agent/json-scan-row-ownership-request`
- Base: `2c3518210cecab3eaada895d57742b088a4976d4` (`origin/main`)
- Relevant committed head before preflight follow-up:
  `3c3bf614cd142d6be4763be66db9b36b6c31dc49`
- Active goal: register and merge the independently demonstrated non-blocking `json.scan` owned-row
  safety request before returning to the C6 escaped-string request.
- Product implementation: not started.
- Pinned Align commit: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`
- C6 escaped-string request branch: preserved as `agent/c6-json-escape-request`.
- C6 design draft: preserved separately on `agent/c6-prompt-context-design`.

Review of the escaped-string request demonstrated a separate existing correctness gap. The pinned
compiler admits `json.scan` row schemas with owned array fields, while its one reusable row slot is
zeroed before each decode and is never dropped after a successful row. An owned field can therefore
be allocated and then overwritten without cleanup even when the pipeline projects a different
field.

Request 6 chooses the smallest idiom-consistent repair: give `json.scan` a scanner-specific semantic
gate using Align's canonical recursive Move classification and reject a Move row. Recursively Copy
rows preserve the documented no-arena, borrowed-input model and require no new runtime branch or
ABI. The general `json.decode` surface is unchanged. No current C6 artifact consumes `json.scan`,
so the request is non-blocking and names a future Copy-row streaming evaluator/log consumer whose
acceptance includes a fail-closed Move-row negative. A consumer that needs owned rows belongs to a
separate per-row ownership request. This branch changes only `docs/align-requests.md` and this
durable handoff.

## Verification

Verified on 2026-07-30 at committed head
`3c3bf614cd142d6be4763be66db9b36b6c31dc49` against the pinned sibling Align checkout:

```text
git diff --check                         PASS
ALIGN_REPO=../align make ci               PASS
```

## Exact next steps

1. Commit the preflight follow-up in `HANDOFF.md` and `docs/align-requests.md`, then finalize this
   handoff with the resulting relevant content head and a clean-worktree statement.
2. Rerun exact verification on the final committed head and run a fresh independent adversarial
   preflight against the full immutable base diff.
3. Resolve every valid refreshed-preflight finding before opening a focused draft pull request.
4. Publish current-SHA preflight, host-native, independent-adversarial, and check evidence; merge
   only after every envelope is clean and `origin/main` remains the reviewed base.
5. Refresh `main`, rebase the preserved escaped-string branch, renumber that request to Request 7,
   make `json.scan` explicitly N/A under Request 6's boundary, and resume its review.
6. Register the remaining C6 blockers (`Option<Move record>` JSON, strict numeric grammar if
   retained, and record-array construction) as separate reviewed slices before returning to the
   C6 design branch.

## Constraints and intentional state

- The current branch intentionally has uncommitted preflight follow-up changes in `HANDOFF.md` and
  `docs/align-requests.md`; do not discard them.
- The worktree checked out on `agent/c6-json-escape-request` contains the committed escaped-string
  Request 6 plus intentional uncommitted changes to `HANDOFF.md` and
  `docs/align-requests.md`. Preserve those files until this request merges, then renumber/rebase
  the branch.
- `agent/c6-prompt-context-design` preserves the C6 design draft.
- Existing governance, pin-adoption, topology, and Request 5 worktrees belong to earlier scoped
  work; do not modify or remove them.
- Use the repository wrappers with the exact pinned Align checkout. Do not implement C6 against a
  proposed Align surface or introduce an application workaround.
