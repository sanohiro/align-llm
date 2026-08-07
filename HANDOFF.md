# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-adoption-contract-v6`, based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`. The v6 design content is committed at
  `d211822`; the current HEAD is the handoff-only commit immediately following it.
- Active goal: finish and merge the redesigned Request 6 focused-adoption contract, then implement
  the separately gated installed profile and authenticated adoption. Request 6 adoption and consumer
  implementations remain blocked until their named image and worker profiles merge.
- v6 closes the ordinary evidence path through image-owned `fresh-supervise --mode
  ordinary-adoption`. The supervisor authenticates the fixed manifest, creates FD 15's fresh sealed
  nonce and FD 16's connected channel, forks exactly one dispatcher child, sends one ticket, and
  keeps the parent alive while the child invokes retained FD 14 with `execveat(AT_EMPTY_PATH)` and
  `argv[0] = request6-adoption-entrypoint`. The dispatcher authenticates the current parent PID,
  stable kernel start-time, no-follow executable digest, exact supervisor command line, and ticket;
  direct dispatcher execution cannot produce evidence.
- The ordinary capsule adds `dispatch_ticket_sha256` and `image_attestation_sha256`. FD 12/13/15
  are fixed-name sealed memfds with an observable regular-file/tmpfs/zero-link/name/seal predicate;
  creator flags are explicit trace invariants because Linux exposes no post-hoc origin bits. The
  worker rewinds and supplies them to pinned bwrap only as `--ro-bind-fd` sources; bwrap consumes
  them into `/authority/{capsule,worker,nonce}`, and the helper rehydrates local memfds from those
  fixed bind paths. No authority FD reaches the helper or Make children. Root and copied trees are
  remounted read-only before the first child, and the fixed three-row child plan remains authoritative.
- The raw-tree wire retains the independent six-entry non-UTF-8/symlink golden and exact
  `HANDOFF.md`/`.git` exclusions. Legacy aggregate/self-test dispatch remains separate from the
  ordinary path; the installed-profile milestone explicitly regresses legacy self-test output and
  rejects ordinary markers.
- PR #62 is superseded and must not be merged. v2 was rejected for root sealing, legacy/ordinary
  dispatch separation, helper vectors, output grammar, nonce freshness, and milestone gaps; v3 for
  authority-FD leakage, incomplete seals/helper plans, phase/milestone ambiguity, and self-test
  dispatch; v4 for impossible memfd predicate, missing offset ownership, contradictory descriptor
  inheritance, missing raw-tree/self-test gates, and stale handoff; v5 for bwrap rewind ownership,
  dispatcher parent authentication, missing `argv[0]`, missing image-attestation capsule binding,
  and nonce ownership. Those findings are redesigned in v6; do not patch the superseded branches.
- Expected post-merge checkpoint: refresh `main`, perform the bounded design retrospective, and
  create `agent/request6-image-profile-extension` for the separately reviewed installed-profile
  gate. After that profile extension merges, create `agent/request6-adoption-implementation`.

## Next steps, in priority order

1. Run one fresh comprehensive independent review of the exact v6 HEAD; do not publish until the
   review is clean.
2. Record the v4/v5 final-review findings and dispositions on PR #62, close it as superseded, push
   v6, create its replacement PR, and complete the review/check/fix/merge workflow.
3. Refresh `main`, record the bounded retrospective, implement and merge the FRESH-IMAGE-REQUEST6
   profile extension on its own branch, then implement authenticated Request 6; review, repair,
   merge, refresh `main`, and continue to the next eligible roadmap gate.

## Latest verification

- `git diff --check`: PASS at v6 content commit `d211822`.
- `make gate-topology-check`: PASS at v6 content commit `d211822`.
- `python3 scripts/check-gate-topology --self-test`: PASS at v6 content commit `d211822`.
- Exact Markdown fence parity check: PASS (`102`, `76`) for
  `docs/align-requests.md` and `docs/specs/check-gate-topology.md` at `d211822`.
- `ordinary-adoption-v1-wire-golden`: PASS (predicate 1217 bytes,
  `cf78d4b749ae37d850cca9dbb3751c5cb0080b23b8f1611cb59e6392117e5dd5`; PAE 1288 bytes,
  `4a83ad037ca2bf99fb18f083d2beb9d2f9596b93b07fcb73ae4dada30c510467`) at `d211822`.
- `raw-tree-v1-golden`: unchanged and PASS (1318 bytes,
  `820d928b48c7c8fd88ce69230608143310caa17f020e72f8f2ceb23ff2354f4f`).
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
