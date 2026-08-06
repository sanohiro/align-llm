# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Current state

- Branch: `agent/fresh-worker-capability`, based on `origin/main` merge commit
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18`.
- Open draft pull request: #61, merge-commit-only. Current head:
  `3b22497e601b3d11289351fbf35936fcacc45456`.
- Active goal: finish the FRESH-WORKER capability, complete the required review and merge, then
  start the next eligible roadmap capability (`C6-LIFECYCLE`).
- Product work is complete through the aggregate capability boundary: the worker launches the
  capable namespace as UID/GID 0 with `CAP_SYS_ADMIN` and `CAP_SETFCAP`; `mount-guard` applies
  the no-symlink attribute, retains only `CAP_SETFCAP`, sets `no_new_privs`, and execs Make so
  nested validation bwrap can map UID 0 without retaining mount authority. The fresh sandbox
  probe guards only `/target/tmp`; validation setup guards `/target/tmp`, `/tmp`, and `/dev/shm`
  after nested mounts exist. Aggregate fixture scripts clear the inherited project Git view.
- Local Docker is unavailable; installed-image and capable aggregate evidence must come from the
  hosted Ubuntu 24.04 profile.

## Baseline provenance

- Source/checkpoint: `9f3541bffe6b89226a68e71b560368506d197a28`.
- Immutable oracle: `9c9e535386fb570b5f275ba0a14d43621f19b99c`.
- Finalization: `3b22497e601b3d11289351fbf35936fcacc45456`.
- The source commit is followed only by the oracle-only and finalizer-only commits for the
  refreshed coding-v1 baseline. Do not change a recorded evaluation artifact without restarting
  the Section 2.4 measurement sequence.

## Next steps, in priority order

1. Inspect diagnostic run `31080479832` on branch `agent/fresh-worker-aggregate-diagnostic`
   (current diagnostic head `7c475452bb67028d270cd60df18c016df711e97e`). Its pinned job passed;
   the installed job is testing the probe-only `/target/tmp` guard and reports cgroup residue if
   the compiler leader exits successfully but its owned cgroup is still populated. Diagnostic
   instrumentation must not enter PR #61.
2. Dispatch and complete the product branch's full hosted CI. Confirm the installed profile reaches
   capable evaluation and that the refreshed baseline and exact aggregate capability contract pass.
3. Update PR #61 with the final head, baseline tuple, hosted evidence, and the known diagnostic
   history. Run one fresh independent adversarial review of the complete diff, record the
   SHA-bound review envelope with `none` or every finding and disposition, and apply valid findings
   in one consolidated repair. Rerun affected checks; restart baseline provenance if a recorded
   artifact changes.
4. Mark the PR ready, verify exact head/base ancestry and merge-commit-only policy, then merge with
   the GitHub connector using the exact expected head SHA.
5. After merge, perform the bounded retrospective, refresh main without discarding the intentional
   primary-worktree change, and begin the reviewed `C6-LIFECYCLE` design gate.

## Latest verification

- `git diff --check`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-unit-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-image-control-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-index-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-test-selection-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-patch-eval-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-verification-loop-smoke`: PASS.
- Baseline recorder: two deterministic-reference samples PASS from the source commit above.
- `make baseline-check`: PASS, including canonical oracle, invalid-input, and failure-retention
  smokes.
- Prior hosted diagnostic runs through `31079703787` established and repaired linker runtime
  bindings, compiler-output hardlink materialization, descriptor-relative overlay cleanup, UID/GID
  and `CAP_SYS_ADMIN` aggregate admission, staged shell/interpreter paths, and aggregate fixture
  Git isolation. Run `31080479832` is the current diagnostic evidence for the remaining nested
  validation boundary.

## Constraints and intentional state

- Keep all source, documentation, diagnostics, commits, and PR metadata in English.
- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no Align language request is
  opened by this capability.
- The PR must use a merge commit so source, oracle, and finalization ancestry remains reachable.
- Diagnostic worktree `/tmp/align-llm-fresh-aggregate-diagnostic` and branch
  `agent/fresh-worker-aggregate-diagnostic` are intentionally retained for hosted aggregate
  diagnosis; never merge their diagnostic-only instrumentation.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted `HANDOFF.md`.
  Do not discard or overwrite it.
