# Session handoff

Read `CLAUDE.md` first. This file records durable capability state; GitHub owns transient pull
request checks, reviews, findings, and attestations.

## Current state

- Branch: `agent/fresh-worker-capability`, based on `origin/main` merge commit
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18` (PR #60).
- Active goal: complete, review, and merge the consumer-complete FRESH-WORKER capability, then move
  to the next eligible roadmap capability without another helper-only split.
- In progress: the repository worker now authenticates the sealed invocation and image manifest,
  captures separate project/Align Git identities, admits one protected private root, materializes
  source/tool/runtime/offline-cache inputs, builds the pinned compiler in a first bwrap namespace,
  installs a descriptor/guard/compiler/archive bundle, and launches `capable-checks` through a
  writable overlay in a second namespace. Make and evaluation consumers use the fresh launcher,
  namespace-owned temporary root, nested staged tools, and private baseline Git view. The installed
  image now seeds the authenticated Cargo cache at the pinned Align revision, and its profile smoke
  contains the real no-network aggregate path.
- The implementation source/oracle/finalization baseline history has not started. Any further change
  to a recorded input must precede that three-commit sequence.

## Next actions

1. Finish focused worker qualification and static checks, remove generated `main`, update this
   checkpoint if the durable state changes, and commit the final implementation source.
2. Run the Section 2.4 pending measurement, commit only the projected immutable oracle, finalize
   the canonical baseline against that full oracle commit, remove the pending file, and commit only
   the canonical baseline and digest.
3. Push a pull request, obtain installed Ubuntu 24.04 FRESH-IMAGE/FRESH-WORKER evidence, run one fresh
   independent comprehensive review, consolidate valid repairs, restart the baseline sequence if a
   recorded input changes, rerun affected checks, and merge with a merge commit only.

## Latest verification

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-unit-smoke`: PASS, including canonical
  JSON, structural runtime/cache digests, staged modes, cache policy, SHA-1/SHA-256 source identity,
  linked-worktree source identity, private baseline Git materialization, and public error invariants.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-gate-topology --self-test`: PASS.
- `ALIGNC=../align/target/release/alignc PYTHONDONTWRITEBYTECODE=1 make hosted-checks`: PASS.
- `ALIGNC=../align/target/release/alignc PYTHONDONTWRITEBYTECODE=1 make eval-coding`: PASS, including
  invalid, Git-configuration, timeout, namespace, resource, mutation, and descendant cleanup smokes.
- `git diff --check`: PASS.
- Installed image build/E2E: not run locally because the Docker daemon at the configured endpoint is
  unavailable. The dedicated hosted profile check is the required installed-platform evidence.

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
