# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-adoption-contract-v8`, based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`. The v8 design content is committed at
  `7eb4b2e7b6c6c98ea9b8362c37f3e1d1433e94ee`; this Handoff update records the current continuity
  commit and the branch is not yet published.
- Active goal: finish and merge the redesigned Request 6 focused-adoption contract, then implement
  the separately gated installed profile and authenticated adoption. Request 6 adoption and consumer
  implementations remain blocked until their named image and worker profiles merge.
- v8 moves all supervisor peer/PID/procfs authentication outside the private PID namespace. The
  namespace helper receives the live channel through the exact `--as-pid-1 --sync-fd 16` bwrap vector,
  consumes the queued proof, and checks only HUP/EOF/protocol liveness. The supervisor component-walks
  absolute `ALIGN_REPO` before channel/FD-14 dispatch and passes the retained root as FD 18.
- v8 replaces the impossible no-follow `/proc/<pid>/exe` hash with one explicitly controlled procfs
  magic-link read, adds a worker-owned fork/`execveat` bwrap launcher so the outer worker retains cgroup
  and cleanup ownership, and binds the complete source-exception vector into the signed
  `ordinary-adoption/v2` capsule.
- Request 6 uses separate `raw-tree/v1` and `source-exception/v2` wires. Legacy source-manifest/v1
  goldens and readers remain unchanged; both project and Align root `HANDOFF.md` are explicit ordinary
  control exceptions, project `main` is optional, and Align `main` is absent.
- PR #62 is superseded and must not be merged. Its v2-v6 findings remain for the PR disposition step;
  do not patch the superseded branches. The v8 branch must receive one fresh comprehensive review
  before publication.
- Expected post-merge checkpoint: refresh `main`, perform the bounded design retrospective, and
  create `agent/request6-image-profile-extension` for the separately reviewed installed-profile gate.
  After that profile extension merges, create `agent/request6-adoption-implementation`.

## Next steps, in priority order

1. Run the required local and independent adversarial comprehensive reviews on the exact v8 HEAD,
   then publish the reviewed design branch.
2. Record all v6 comprehensive-review findings and dispositions on PR #62, close it as superseded,
   push v8, create its replacement PR, and complete the review/check/fix/merge workflow.
3. Refresh `main`, record the bounded retrospective, implement and merge the FRESH-IMAGE-REQUEST6
   profile extension on its own branch, then implement authenticated Request 6; review, repair,
   merge, refresh `main`, and continue to the next eligible roadmap gate.

## Latest verification

- v8 author checks passed: `git diff --check`, `make gate-topology-check`,
  `python3 scripts/check-gate-topology --self-test`, and
  `python3 scripts/run-fresh-source-manifest-wire-smoke`.
- v8 golden recomputation passed for the 1314-byte capsule predicate, 1385-byte DSSE PAE,
  1348-byte raw-tree vector, and 1755-byte source-exception vector with the hashes recorded below.
- The pinned bwrap source and host probe confirm that FD 16 is inherited only when the exact vector
  includes `--as-pid-1 --sync-fd 16`; the negative vector without `--as-pid-1` does not forward it.
- The v8 exception fixture is designed as 1755 canonical bytes with SHA-256
  `0c685027b378e6ef448e8efd807532eb8f056de04f550e884d56a5ef0834ead0`; the raw-tree fixture remains
  1348 bytes with SHA-256
  `8b30014d36e10e32e230fcbbcbe12b6933903da48c8569140cadd62795caad77`.
- The v8 ordinary capsule golden is designed as a 1314-byte predicate with SHA-256
  `2c1cc89bfdc4f48c97a44e7cbf6ec1e9d34daff710ce40972fe37e1f6741f1fd`; its 1385-byte DSSE PAE has
  SHA-256 `92ef881cc93e610563883f54cf06311985caedc9925736a4fca90067c6687f64`.
- This remains a docs/specification-only gate. Source tests, `make check`, `make build`, and `make ci`
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
