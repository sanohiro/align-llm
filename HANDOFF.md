# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Current state

- Branch: `agent/fresh-worker-capability`, based on `origin/main` merge commit
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18`.
- Open draft pull request: #61, merge-commit-only. Current head:
  `fe494d42ed2547c64c0b808ce447a8fd2bfd5aa1`.
- Active goal: finish the FRESH-WORKER capability, complete the required review and merge, then
  start the next eligible roadmap capability (`C6-LIFECYCLE`).
- Product repair is complete through the independent review findings: the worker retains
  `CAP_SYS_ADMIN` for nested mount admission before `mount-guard` reduces it, authenticates the
  exact fresh compiler path, bounds reachable and copied Git state, enforces aggregate writable
  stores while the child runs, and validates the published x86_64 ELF dependency closure. The
  qualification command now runs all focused owners and labels installed-profile cases as
  deferred until `--installed-profile` runs in the hosted job.
- Local Docker is unavailable; installed-image and capable aggregate evidence must come from the
  hosted Ubuntu 24.04 profile.

## Baseline provenance

- Source/checkpoint: `75d716d360875d3038eb0304ae217ae16833d0e9`.
- Immutable oracle: `1c4d61f6fe8d88acd9bb89eeb35c03f1525d0231`.
- Finalization: `fe494d42ed2547c64c0b808ce447a8fd2bfd5aa1`.
- The source commit is followed only by the oracle-only and finalizer-only commits for the
  refreshed coding-v1 baseline. Do not change a recorded evaluation artifact without restarting
  the Section 2.4 measurement sequence.

## Next steps, in priority order

1. Push the repair and finalization commits, then dispatch and complete the product branch's full
   hosted CI. Confirm the installed profile reaches capable evaluation and that the refreshed
   baseline and exact aggregate capability contract pass; the prior product run `31081165976` and
   diagnostic run `31081113394` failed at nested `mount_setattr` before this repair.
2. Record the initial review's eight finding dispositions and the repair SHA on PR #61. Because the
   repair materially changed behavior, run one conditional final independent review of the final
   diff and record its SHA-bound envelope; no further local repair loop is allowed after a
   non-trivial final-review finding without re-scoping the slice.
3. Mark the PR ready, verify exact head/base ancestry and merge-commit-only policy, then merge with
   the GitHub connector using the exact expected head SHA.
4. After merge, perform the bounded retrospective, refresh main without discarding the intentional
   primary-worktree change, and begin the reviewed `C6-LIFECYCLE` design gate.

## Latest verification

- `git diff --check`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-unit-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-image-control-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-coding-task-resource-scan-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-coding-task-git-config-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-baseline-failure-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-gate-topology --self-test`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-index-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-test-selection-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-patch-eval-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-verification-loop-smoke`: PASS.
- `ALIGNC=/home/hiro/prj/align-clean-672/target/release/alignc PYTHONDONTWRITEBYTECODE=1 make hosted-checks`: PASS.
- Baseline recorder: two deterministic-reference samples PASS from source `75d716d` using
  detached Align `d9fb5da`; oracle `1c4d61f6` and finalization `fe494d4` are committed.
- `make baseline-check`: PASS, including canonical oracle, invalid-input, and failure-retention
  smokes.
- Prior hosted diagnostic runs through `31079703787` established and repaired linker runtime
  bindings, compiler-output hardlink materialization, descriptor-relative overlay cleanup, UID/GID
  and `CAP_SYS_ADMIN` aggregate admission, staged shell/interpreter paths, and aggregate fixture
  Git isolation. Hosted product run `31081165976` and diagnostic run `31081113394` are pre-repair
  evidence only; new hosted evidence is required for the current head.

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
