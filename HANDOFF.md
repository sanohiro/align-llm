# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-adoption-contract-v7`, based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`. The v7 design content is committed at
  `29be692`; the Handoff update is intentionally still uncommitted.
- Active goal: finish and merge the redesigned Request 6 focused-adoption contract, then implement
  the separately gated installed profile and authenticated adoption. Request 6 adoption and consumer
  implementations remain blocked until their named image and worker profiles merge.
- v7 closes the v6 review gaps. The supervisor sends one fresh ticket over the connected
  `SOCK_SEQPACKET` channel, receives the signed capsule digest `C`, and returns one queued
  worker-admission proof `P` bound to the ticket, fresh nonce, and complete DSSE envelope. The
  dispatcher peeks without consuming it; the namespace helper consumes it before Make and retains
  the live channel through every child row and reverse cleanup. Parent death, HUP, peer/start-time
  change, extra/missing proof, and replay fail closed with an exact phase.
- v7 explicitly clears `FD_CLOEXEC` at the supervisor-to-dispatcher and dispatcher-to-worker edges,
  gives the worker the exact FD allowlist, and makes the worker the owner of image-attested bwrap
  FD 27. The worker invokes FD 27 with `execveat(AT_EMPTY_PATH)`; bwrap/helper never receive it.
  The exact bwrap vector now includes `--as-pid-1 --sync-fd 16 --unshare-ipc`.
- v7 makes project and Align source exceptions one canonical policy: fixed `git,handoff,target,main`
  rows, project root `HANDOFF.md` only, no exception bytes in `raw-tree/v1` entries, and independent
  metadata bytes. It also requires component-by-component no-follow `ALIGN_REPO` admission and
  records the complete input/toolchain/revision/build/fixture/cleanup phase mapping.
- PR #62 is superseded and must not be merged. v2 through v6 findings remain recorded for the PR
  disposition step; do not patch the superseded branches. The v7 design is still unpublished until
  a fresh comprehensive review of this exact HEAD completes.
- Expected post-merge checkpoint: refresh `main`, perform the bounded design retrospective, and
  create `agent/request6-image-profile-extension` for the separately reviewed installed-profile
  gate. After that profile extension merges, create `agent/request6-adoption-implementation`.

## Next steps, in priority order

1. Run one fresh comprehensive independent review of the exact v7 HEAD; do not publish until the
   review is clean.
2. Record all v6 comprehensive-review findings and dispositions on PR #62, close it as superseded,
   push v7, create its replacement PR, and complete the review/check/fix/merge workflow.
3. Refresh `main`, record the bounded retrospective, implement and merge the FRESH-IMAGE-REQUEST6
   profile extension on its own branch, then implement authenticated Request 6; review, repair,
   merge, refresh `main`, and continue to the next eligible roadmap gate.

## Latest verification

- `git diff --check`: PASS at v7 content commit `29be692`.
- `make gate-topology-check`: PASS at v7 content commit `29be692`.
- `python3 scripts/check-gate-topology --self-test`: PASS at v7 content commit `29be692`.
- Existing `python3 scripts/run-fresh-source-manifest-wire-smoke`: PASS; it still exercises the
  shipped schema-1 implementation and does not yet consume v7's new exception projection.
- Exact Markdown fence parity check: PASS (`104`, `76`) for
  `docs/align-requests.md` and `docs/specs/check-gate-topology.md` at v7.
- `ordinary-adoption-v1-wire-golden`: PASS (predicate 1217 bytes,
  `cf78d4b749ae37d850cca9dbb3751c5cb0080b23b8f1611cb59e6392117e5dd5`; PAE 1288 bytes,
  `4a83ad037ca2bf99fb18f083d2beb9d2f9596b93b07fcb73ae4dada30c510467`).
- `raw-tree-v1-golden`: PASS (1348 bytes,
  `8b30014d36e10e32e230fcbbcbe12b6933903da48c8569140cadd62795caad77`).
- `raw-tree-v1-output-exception-golden`: PASS (1406 bytes,
  `f326ceb896ff6224aa3fa1fbdd31c99da0a065d7200508bdccd8e51ca7e0046f`).
- This is a docs/specification-only gate. Source tests, `make check`, `make build`, and `make ci`
  are N/A and remain deferred to executable implementation/profile slices.

## Constraints and intentional state

- Keep repository source, documentation, commits, PR metadata, and diagnostics in English.
- The shipped Align revision for Request 6 is
  `e65448b744c04e3868d079eef8b45ce0d43ac8ee`; `.align-revision` remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` until the reviewed implementation branch consumes it.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted `HANDOFF.md`; do
  not discard or overwrite it.
- Diagnostic worktrees and branches are retained for evidence; never merge diagnostic-only
  instrumentation.
