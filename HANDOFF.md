# Session handoff

Read `CLAUDE.md` first. This file records only durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-json-escape-request-v2`
- Base and relevant main commit:
  `54f290154a5f33e476cd17d6770f90b0f3838903` (`origin/main`)
- Relevant Request 7 content head:
  `8e32d5a856b53f12ba4a2a1973d1e5fe4ff0582e`
- Active goal: review and merge Request 7, escaped strings and strict string grammar for declared
  JSON decoding, as the next independently demonstrated Align prerequisite for C6.
- Product implementation: not started.
- Pinned Align commit: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`
- C6 design draft: preserved separately on `agent/c6-prompt-context-design`.
- Original escaped-string work and its completed review follow-up remain preserved on
  `agent/c6-json-escape-request` at `1ef0d37c752eb94ad5457209946a5c587e14322e`.

PR #24 merged the scanner-safety request into the align-llm request register as Request 6. That
request exclusively owns the proposed recursively Copy `json.scan` row boundary. Request 7 now
owns escaped-string materialization for arena-backed declared record, AoS, and SoA decoding plus
shared strict string grammar. Scanner ownership and Move-row diagnostics are N/A here; Request 7
only specifies strict grammar for rows admitted by Request 6 and rejects escaped retained views
because the scanner has no arena.

Ordinary decode, encode, and owner drop for eligible `Option<Move record>` success are already
shipped. A first adversarial preflight proved that strict ignored-string rejection and
outside-arena escaped-view rejection add failure edges after earlier fields may make owners live.
Request 7 may therefore be registered independently but cannot advance to `IMPLEMENTING` until the
next decoded-owner transition cleanup request is `ALIGN_MERGED` at a named commit. That prerequisite
must audit construction, speculative write, replacement and source nulling, fallback success and
failure, staging, return, and cleanup. Demonstrated classes include optional owners followed by
later enclosing-object failure, indexed top-level AoS speculation overwritten by fallback,
top-level `array<MoveStruct>` partial staging, and required or optional top-level record owners
followed by trailing-garbage rejection.

The review follow-up also adds an exact per-path result oracle, hand-authored multi-invalid
precedence cases, a fixed 4,096-case SplitMix64 grammar corpus, and a caller-owned
`cfg(test)`-only probe for failure byte offsets and logical arena allocations. The probe is not a
production ABI or process-global counter.

A second adversarial review found that a proposed joint-delivery exception contradicted the
cleanup-first lifecycle and that align-llm can pin only one Align commit. The final contract removes
joint delivery. A Request 7 implementation branch may start only after the named cleanup commit is
merged, and the final Request 7 commit must retain that cleanup commit as an ancestor. Adoption pins
only the final Request 7 commit in `.align-revision`, records the cleanup commit in a checked-in
fixture, and runs an Align-repository `merge-base --is-ancestor` check before any client fixture.

The bounded retrospective after PR #24 established three reusable decisions:

1. describe ownership defects by owner-live transitions rather than a container-type label;
2. split an independently sound safety boundary before resuming a broader consumer request; and
3. keep attestations in GitHub while recording reproducible verification commands and durable
   branch decisions here.

## Verification

Verified on 2026-07-30 at Request 7 content head
`8e32d5a856b53f12ba4a2a1973d1e5fe4ff0582e` against the exact pinned sibling checkout:

```text
git diff --check                         PASS
ALIGN_REPO=/home/hiro/prj/align make ci  PASS
```

## Exact next steps

1. Run a fresh independent adversarial preflight against the complete final diff and pinned Align
   implementation. Resolve valid findings before opening the pull request.
2. Open a focused draft pull request, publish SHA-bound preflight, host-native,
   independent-adversarial, and check evidence, and merge only when all current-SHA evidence is
   clean against an unchanged base tip.
3. Refresh `main`, run the bounded retrospective, and register decoded-owner transition cleanup
   first, then strict numeric grammar if retained and record-array construction as separate reviewed
   slices. Request 7 implementation remains blocked until the cleanup request reaches
   `ALIGN_MERGED`.
4. Return to the C6 design branch only after its complete prerequisite set is registered; do not
   implement against a proposed Align surface.

## Constraints and intentional state

- This branch changes only `docs/align-requests.md` and this durable handoff. The worktree is
  expected to be clean after this handoff commit.
- The old escaped-string branch is a preserved source checkpoint, not a merge source.
- `agent/c6-prompt-context-design` preserves the C6 design draft.
- Existing governance, pin-adoption, topology, Request 5, and scanner-request worktrees belong to
  earlier scoped work; do not modify or remove them.
- Use the repository wrappers with the exact pinned Align checkout. Do not implement C6 against a
  proposed Align surface or introduce an application workaround.
