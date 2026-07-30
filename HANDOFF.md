# Session handoff

Read `CLAUDE.md` first. This file records only the current durable execution state; GitHub owns
transient pull request checks, reviews, and attestations.

## Current state

- Branch: `agent/json-scan-row-ownership-request`
- Base: `2c3518210cecab3eaada895d57742b088a4976d4` (`origin/main`)
- Relevant content head before this handoff-only finalization:
  `bdfb3f1646337682d8375b35a0fd76b5ae8eab0e`
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
so the request is non-blocking. Its first concrete consumer is the post-`ALIGN_MERGED` adoption
target, which includes a Copy-row aggregate and fail-closed Move-row negatives; no product consumer
is currently planned. A consumer that needs owned rows belongs to a separate per-row ownership
request. This branch changes only `docs/align-requests.md` and this durable handoff.

The fresh immutable-head reviews found eight acceptance and continuity gaps. Five are resolved in
the committed follow-up: the register no longer overstates general `Option<T>` support;
the rich Copy-row fixture observes `Option<CopyStruct>` `Some`/missing/`null` states separately;
imported and generic row diagnostics require public source spellings instead of internal names;
resolved generic `Wrap<T>` monomorphs receive Copy/Move coverage; and the pre-codegen diagnostic
assertion is scoped to owning-row fixtures rather than conflicting multi-invalid fixtures.
The committed final follow-up closes the final three: the adoption target is the concrete
first consumer instead of an invented future product feature, unsupported Option forms have exact
lifecycle wording, and the post-merge sequence includes the required bounded retrospective.

## Verification

Verified on 2026-07-30 at relevant content head
`bdfb3f1646337682d8375b35a0fd76b5ae8eab0e` against the pinned sibling Align checkout:

```text
git diff --check                         PASS
ALIGN_REPO=../align make ci               PASS
```

## Exact next steps

1. Rerun exact verification on the final handoff head and complete a fresh independent adversarial
   preflight against the full final immutable base diff.
2. Resolve every valid refreshed-preflight finding before opening a focused draft pull request.
3. Publish current-SHA preflight, host-native, independent-adversarial, and check evidence; merge
   only after every envelope is clean and `origin/main` remains the reviewed base.
4. Refresh `main` and perform the required bounded retrospective for this merged pull request.
5. Rebase the preserved escaped-string branch, renumber that request to Request 7, make
   `json.scan` explicitly N/A under Request 6's boundary, and resume its review.
6. Register the remaining C6 blockers (`Option<Move record>` JSON, strict numeric grammar if
   retained, and record-array construction) as separate reviewed slices before returning to the
   C6 design branch.

## Constraints and intentional state

- The Request 6 design and all preflight follow-ups are committed. The worktree is expected to be
  clean after this handoff-only finalization; do not discard or rewrite the scoped commits.
- The worktree checked out on `agent/c6-json-escape-request` contains the committed escaped-string
  Request 6 plus intentional uncommitted changes to `HANDOFF.md` and
  `docs/align-requests.md`. Preserve those files until this request merges, then renumber/rebase
  the branch.
- `agent/c6-prompt-context-design` preserves the C6 design draft.
- Existing governance, pin-adoption, topology, and Request 5 worktrees belong to earlier scoped
  work; do not modify or remove them.
- Use the repository wrappers with the exact pinned Align checkout. Do not implement C6 against a
  proposed Align surface or introduce an application workaround.
