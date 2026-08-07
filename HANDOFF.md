# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-adoption-contract-v4`, with redesigned content complete at
  `2db67e8` (full head is recorded after this handoff commit), based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`. This handoff-only metadata update follows that
  design commit; no design content follows it.
- Active goal: finish and merge the redesigned Request 6 focused-adoption contract, then implement
  the separately gated installed profile and authenticated adoption. Request 7 registration and
  other independent planning may continue; Request 6 adoption and consumer implementations remain
  blocked until their named image and worker profiles merge.
- The v4 design enters through trusted image-owned
  `fresh-supervise --mode ordinary-adoption`, which authenticates the fixed manifest, retains the
  Request 6 dispatcher at FD 14, creates a fresh sealed nonce at FD 15, and invokes it with
  `execveat(AT_EMPTY_PATH)`; legacy bootstrap/run-capsule flow is explicitly separate. The signed
  `ordinary-adoption/v1` capsule and sealed worker use exact sealed memfd contracts on FDs 12/13,
  bind the nonce, and reject replay.
  The worker executes exactly
  `/usr/bin/python3 -I -B /proc/self/fd/13 --project-root-fd 4 --capsule-fd 12 --invocation-nonce-fd 15`,
  owns bwrap/cgroup/staging setup, remounts `/` read-only before children, and passes the seals to
  an image-owned helper that owns exactly the three fixed Make vectors and their complete argv/env
  child plans. Every manifest tool is
  retained into the namespace-owned read-only `/tools` inventory; setup-only
  `/private-tool-inventory` is detached before children. Project scripts remain interpreter/data
  arguments, Cargo admission uses the 24 GiB materialization bound with metadata reserve, and the
  exact nonce-bearing capsule predicate/PAE golden is recorded. The complete `raw-tree/v1` preimage,
  `HANDOFF.md` exclusion, absolute-to-relative `ALIGN_REPO` normalization, direct public `execve`,
  FD-27 bwrap closure, two-stage output grammar, and milestone exemption for the prerequisite image
-  profile are all explicit. Authority descriptors close before Make children, whose only inherited
  descriptors are 0/1/2; the exact first-vector, FD14-dispatch, staging-source, and cleanup phase
  precedence is explicit. FRESH-IMAGE-REQUEST6 remains a separate installed-profile prerequisite.
- PR #62 is superseded and must not be merged. The v2 design was rejected by its final review and
  is not a candidate for publication. The v3 redesign was also rejected by the fresh final reviews
  for authority-FD leakage, incomplete seals/helper plans, phase and milestone ambiguity, and the
  self-test dispatch contradiction; those findings were redesigned in v4 and must not be patched on
  the v3 branch.
- Expected post-merge checkpoint: refresh `main` safely, perform the bounded design retrospective,
  and create `agent/request6-image-profile-extension` for the separately reviewed installed-profile
  gate. After that profile extension merges, create `agent/request6-adoption-implementation`; the
  implementation branch must not reuse PR #62's direct ordinary Make command.

## Next steps, in priority order

1. Run one fresh comprehensive independent review of the current v4 branch HEAD after this handoff
   commit; do not publish the v4 design until the review is clean.
2. Record both final review dispositions on PR #62, close it as superseded, publish the v4 design
   PR, and complete its review/fix/merge evidence.
3. Refresh `main`, record the bounded retrospective, implement and merge the FRESH-IMAGE-REQUEST6
   profile extension on its own branch, then implement Request 6 on a new branch; review, repair,
   merge, refresh `main`, and continue to the next eligible roadmap gate.

## Latest verification

- `make gate-topology-check`: PASS at `2db67e8`.
- `python3 scripts/check-gate-topology --self-test`: PASS at `2db67e8`.
- `git diff --check`: PASS at `2db67e8`.
- `for file in docs/align-requests.md docs/specs/check-gate-topology.md; do awk '/^```/ { count++ } END { if (count % 2 != 0) exit 1; print FILENAME ": " count }' "$file"; done`: PASS (98, 76) at `2db67e8`.
- The v4 seal, helper-plan, and phase-contract edits are docs-only; their executable owners remain
  deferred to the separately gated image-profile and adoption implementation slices.
- The design-only gate does not run source tests, `make check`, `make build`, or `make ci`; those
  checks are deferred until executable implementation or an executable contract boundary exists.

## Constraints and intentional state

- Keep repository source, documentation, commits, and PR metadata in English.
- The shipped Align revision for Request 6 is
  `e65448b744c04e3868d079eef8b45ce0d43ac8ee`; `.align-revision` remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` until the reviewed implementation branch consumes it.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted `HANDOFF.md`; do
  not discard or overwrite it.
- Diagnostic worktrees and branches are retained for evidence; never merge diagnostic-only
  instrumentation.
