# Session handoff

Read `CLAUDE.md` first. This file records durable capability state; GitHub owns transient pull
request checks, reviews, findings, and attestations.

## Current state

- Branch: `agent/fresh-worker-capability`, based on `origin/main` merge commit
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18` (PR #60).
- Relevant review-repair checkpoint: `366dc3d02452c1775b2b97d307ebcdeba155c586`. Subsequent
  non-evaluation commits may contain installed-profile fixes or durable checkpoint corrections; use
  the latest non-evaluation source commit and its valid oracle/finalization descendants recorded by
  the pull request before merge.
- Active goal: complete, review, and merge the consumer-complete FRESH-WORKER capability, then move
  to the next eligible roadmap capability without another helper-only split.
- In progress: the repository worker now cryptographically re-verifies the sealed Ed25519/DSSE
  invocation and image-manifest tuple,
  captures separate project/Align Git identities, admits one protected private root, materializes
  source/tool/runtime/offline-cache inputs, builds the pinned compiler in a first bwrap namespace,
  installs a descriptor/guard/compiler/archive bundle, and launches `capable-checks` through a
  writable overlay in a second namespace. Make and evaluation consumers use the fresh launcher,
  namespace-owned temporary root, nested staged tools, and private baseline Git view. The installed
  image now seeds the authenticated Cargo cache at the pinned Align revision, and its profile smoke
  contains the real no-network aggregate path. Review repair additionally rejects local Git helpers
  before source queries, retains and rechecks Git/common/ref/index/object identity, streams source
  and child output under bounds, kills and reaps the complete cgroup, and makes staging and cleanup
  descriptor-relative so a replacement root is never deleted.
- The original source/oracle/finalization history exists at `8eafdecf24caa7cd9c5c119f08335a77f0972759`,
  `4510138117e1fd612295256ba91f21361b84c3c5`, and
  `ce8a2ab1d42cef33fbbbf8b77893ac57268ff696`. The review repair changes recorded inputs. Merge only
  from a head whose latest non-evaluation source/checkpoint commit is followed by an oracle-only
  commit and a finalizer-only commit; older tuples remain historical ancestors, not merge evidence.

## Next actions

1. If the current source/checkpoint commit does not yet have its final oracle-only and
   finalizer-only descendants, run the Section 2.4 pending measurement and create them. Otherwise,
   do not repeat the measurement.
2. Push the replacement history to the existing capability pull request, record finding
   dispositions, obtain fresh installed Ubuntu 24.04 FRESH-IMAGE/FRESH-WORKER evidence, and merge
   with a merge commit only after every required check passes.
3. After merge, perform the bounded retrospective and begin the next eligible consumer capability.

## Latest verification

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS, batching the
  attestation/image-control owners, worker unit cases, topology oracle, and the complete Section 9.10
  focused-case inventory. Worker cases include forged signatures, supervisor replay, Git helper and
  alternate rejection, packed/linked Git identity, source/common-dir replacement, bounded streams,
  and replacement-root cleanup authority.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-gate-topology --self-test`: PASS.
- `ALIGNC=../align/target/release/alignc PYTHONDONTWRITEBYTECODE=1 make hosted-checks`: PASS.
- `ALIGNC=../align/target/release/alignc PYTHONDONTWRITEBYTECODE=1 make eval-coding`: PASS, including
  invalid, Git-configuration, timeout, namespace, resource, mutation, and descendant cleanup smokes.
- `git diff --check`: PASS.
- Installed image build/E2E: not run locally because the Docker daemon at the configured endpoint is
  unavailable. Hosted attempts identified and fixed the cache seed's explicit `RUSTC` input and the
  seeded Cargo cache's raw-mode normalization. The dedicated hosted profile check must supply fresh
  installed-platform evidence after push.

## Blockers and decisions

- No implementation blocker is known. Local Docker unavailability is an execution condition, not a
  design blocker; hosted Ubuntu 24.04 owns the required installed-profile evidence.
- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; this capability does
  not adopt a new Align surface.
- FRESH-WORKER remains one capability because private admission, two namespaces, the compiler bundle,
  Make interposition, cache/image completion, and the first real consumer aggregate are not useful or
  reviewable as independently shipped helper surfaces.
- The pull request must use a merge commit so the implementation source, immutable oracle, and
  canonical finalization commits remain ancestors of the exact merged head.
- The separate primary worktree has intentional uncommitted state; do not discard or overwrite it
  while this clean worktree is active.
