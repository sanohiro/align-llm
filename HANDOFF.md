# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-adoption-contract-v10`, based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`. The v10 design content is committed at
  `5805331`; this Handoff update records the current continuity commit and the branch is not yet
  published.
- Active goal: finish and merge the redesigned Request 6 focused-adoption contract, then implement
  the separately gated installed profile and authenticated adoption. Request 6 adoption and consumer
  implementations remain blocked until their named image and worker profiles merge.
- v10 keeps all supervisor peer/PID/procfs authentication outside the private PID namespace. The
  namespace helper receives the live channel through the exact `--as-pid-1 --sync-fd 16` bwrap vector,
  consumes the queued proof, and checks only HUP/EOF/protocol liveness. The supervisor opens `/` as
  temporary FD 17, component-walks absolute `ALIGN_REPO` before channel/FD-14 dispatch, retains the
  final root as FD 18, and closes FD 17 before channel creation.
- v10 defines the exact bwrap inheritance set `B` for authority, setup, runtime, and tool descriptors;
  the worker parent forks and starts the cgroup-gated bwrap launcher, while the child only waits and
  executes FD 27 with `execveat`. The worker retains outer cgroup/staging/cleanup ownership.
- v10 defines worker exit statuses `1..6`, the dispatcher-owned `UNOBSERVED_EXIT` result for signal or
  unknown worker death before a final phase result, and the complete source-exception vector bound into
  the signed `ordinary-adoption/v2` capsule.
- Request 6 uses separate `raw-tree/v1` and `source-exception/v2` wires. Legacy source-manifest/v1
  goldens and readers remain unchanged; both project and Align root `HANDOFF.md` are explicit ordinary
  control exceptions, project `main` is optional, and Align `main` is absent.
- v10 limits the offset ledger to byte-bearing memfds `12`, `13`, `15`, and local rehydrated memfds;
  O_PATH FD 18 and other identity-only descriptors use identity, bind, protocol, or exec checks
  without `lseek`/`pread`. The fixed bwrap launcher invokes retained FD 27 with `argv[0] = bwrap`.
- PR #62 is superseded and must not be merged. Its recorded findings and dispositions remain a GitHub
  PR-metadata task; do not patch the superseded branches. v8 and v9 are unpublished superseded designs;
  v10 must receive one fresh comprehensive review before publication.
- Expected post-merge checkpoint: refresh `main`, perform the bounded design retrospective, and
  create `agent/request6-image-profile-extension` for the separately reviewed installed-profile gate.
  After that profile extension merges, create `agent/request6-adoption-implementation`.

## Next steps, in priority order

1. Run the required fresh independent adversarial comprehensive review on exact v10 HEAD, then publish
   the reviewed design branch.
2. Record all superseded PR #62/v8/v9 finding dispositions, close PR #62 as superseded, push v10, create
   its replacement PR, and complete the review/check/fix/merge workflow.
3. Refresh `main`, record the bounded retrospective, implement and merge the FRESH-IMAGE-REQUEST6
   profile extension on its own branch, then implement authenticated Request 6; review, repair,
   merge, refresh `main`, and continue to the next eligible roadmap gate.

## Latest verification

- v10 required design-gate checks passed: `git diff --check`, Markdown fence parity (`104` and `76`
  fence delimiters), and `make gate-topology-check`.
- v10 supplemental author checks passed: `python3 scripts/check-gate-topology --self-test` and
  `python3 scripts/run-fresh-source-manifest-wire-smoke`; these do not claim deferred implementation
  owners.
- The v10 golden vectors are unchanged; prior recomputation passed for the 1314-byte capsule predicate,
  1385-byte DSSE PAE,
  1348-byte raw-tree vector, and 1755-byte source-exception vector with the hashes recorded below.
- The pinned bwrap source and host probe confirm that FD 16 is inherited only when the exact vector
  includes `--as-pid-1 --sync-fd 16`; the negative vector without `--as-pid-1` does not forward it.
- The exception fixture is designed as 1755 canonical bytes with SHA-256
  `0c685027b378e6ef448e8efd807532eb8f056de04f550e884d56a5ef0834ead0`; the raw-tree fixture remains
  1348 bytes with SHA-256
  `8b30014d36e10e32e230fcbbcbe12b6933903da48c8569140cadd62795caad77`.
- The ordinary capsule golden is designed as a 1314-byte predicate with SHA-256
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
