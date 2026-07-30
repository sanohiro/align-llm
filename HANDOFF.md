# Session handoff

Read `CLAUDE.md` first. This file records only the current durable execution state; GitHub owns
transient pull request checks, reviews, and attestations.

## Current state

- Branch: `agent/json-scan-row-ownership-request`
- Base: `2c3518210cecab3eaada895d57742b088a4976d4` (`origin/main`)
- Relevant content head before this handoff-only finalization:
  `95cd3a519989cd36023bb0836445c305215f510f`
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

The contract covers Copy options in their `Some`, missing, and `null` states; local, imported, and
generic public type spellings; Copy/Move classification after monomorphization; deterministic
validation; allocation-counter isolation; pre-codegen rejection; cache behavior; and unchanged
accepted MIR, LLVM, and runtime ABI. Imported generics receive whole-program and per-unit coverage:
`scan_schema.Wrap<array<i64>>` must retain that exact public spelling without an internal `$` name.

Ordinary decode/encode/drop for `Option<Inner>` where `Inner` owns an array is already shipped.
Known decoded-owner gaps remain in the pinned runtime: optional descriptors are skipped on later
object failure; indexed AoS or SoA speculation can write an owner that fallback overwrites on
success or failure; top-level `array<MoveStruct>` decode does not clean current or completed staged
rows after malformed later elements or trailing garbage; and top-level single-record trailing
garbage leaves required or optional owners live. A follow-up design must audit every transition
after an owner becomes live, including construction, speculative write, replacement/source
nulling, fallback, staging, return, and cleanup, and explicitly own or assign every affected public
path. This does not change Request 6's scanner-only boundary: semantic rejection prevents any Move
row from reaching scanner MIR or runtime construction, so the scanner repair does not depend on a
general decode cleanup repair.

## Verification

Verified on 2026-07-30 at relevant content head
`95cd3a519989cd36023bb0836445c305215f510f` against the pinned sibling Align checkout:

```text
git diff --check                         PASS
ALIGN_REPO=/home/hiro/prj/align make ci  PASS
```

## Exact next steps

1. Rerun exact verification on the final handoff head, push the follow-up, and complete the required
   current-SHA checks and reviews in GitHub. Merge only when all required evidence is clean and
   `origin/main` remains the reviewed base.
2. Refresh `main` and perform the required bounded retrospective for this merged pull request.
3. Rebase the preserved escaped-string branch, renumber that request to Request 7, make
   `json.scan` explicitly N/A under Request 6's boundary, and resume its review.
4. Register decoded-owner transition cleanup, strict numeric grammar if retained, and
   record-array construction as separate reviewed slices before returning to the C6 design branch.
   The cleanup design must audit every transition after an owner becomes live and include
   allocation-count regressions for optional outer failure, successful and failed AoS/SoA fallback
   after a speculative owner write, top-level `array<MoveStruct>` partial staging, and
   trailing-garbage rejection. Do not reopen a blanket `Option<Move record>` descriptor request:
   its ordinary success path is shipped.

## Constraints and intentional state

- The Request 6 design and all contract corrections are committed. The worktree is expected to be
  clean after this handoff-only finalization; do not discard or rewrite the scoped commits.
- The worktree checked out on `agent/c6-json-escape-request` contains the committed escaped-string
  Request 6 plus intentional uncommitted changes to `HANDOFF.md` and
  `docs/align-requests.md`. Preserve those files until this request merges, then renumber/rebase
  the branch and correct its inherited blanket `Option<Move record>` claim to the decoded-owner
  transition classes above.
- `agent/c6-prompt-context-design` preserves the C6 design draft.
- Existing governance, pin-adoption, topology, and Request 5 worktrees belong to earlier scoped
  work; do not modify or remove them.
- Use the repository wrappers with the exact pinned Align checkout. Do not implement C6 against a
  proposed Align surface or introduce an application workaround.
