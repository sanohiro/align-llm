# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Current state

- Branch: `agent/fresh-worker-capability`, based on `origin/main` merge commit
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18`.
- Open draft pull request: #61, merge-commit-only. Latest product implementation commit:
  `c59e0791e7f50d9ad0c4f952182eadb7f8f9d504`; documentation-only handoff commits follow it.
- Active goal: finish the FRESH-WORKER capability, complete the required review and merge, then
  stop this execution as requested; do not start the next roadmap capability.
- Product repair is complete through the independent review findings: the worker retains
  `CAP_SYS_ADMIN` for nested mount admission before `mount-guard` reduces it, authenticates the
  exact fresh compiler path, bounds reachable and copied Git state, enforces aggregate writable
  stores while the child runs, and validates the published x86_64 ELF dependency closure. The
  qualification command now runs all focused owners and labels installed-profile cases as
  deferred until `--installed-profile` runs in the hosted job. The resource-scan race fix now
  separates scanner construction from context entry without interpreter-version-dependent
  traceback bytecode offsets, and its cleanup-boundary smoke uses a Python-version-stable trace
  boundary. Aggregate quota scanning now reopens the final directory as a readable descriptor
  before enumeration and treats the kernel-owned overlay `work/` metadata directory as opaque
  during live quota polling; the worker unit smoke covers both regressions.
- Local Docker is unavailable; installed-image and capable aggregate evidence must come from the
  hosted Ubuntu 24.04 profile.

## Baseline provenance

- Source/checkpoint: `f1bcda26bdf18b00415b077730212c7d87a9fedf`.
- Immutable oracle: `dbdc3f0ce45163000ac4001e2fd771532071dcda`.
- Finalization: `40c9c41a9da43fb715e5f7285e2ff0c5cc2a5df8`.
- The source commit is followed only by the oracle-only and finalizer-only commits for the
  refreshed coding-v1 baseline. Do not change a recorded evaluation artifact without restarting
  the Section 2.4 measurement sequence.

## Next steps, in priority order

1. Dispatch and complete the product branch's full hosted CI at `c59e079`. Confirm the installed
   profile reaches capable evaluation and that the refreshed baseline and exact aggregate
   capability contract pass. Run `31094357807` reached the repaired aggregate quota descriptor
   scan but still failed while entering kernel-owned `workspace-work/work`; diagnostic run
   `31094926870` isolated that permission error and `c59e079` makes the directory opaque during
   live polling. Earlier run `31087751448` reached the repaired Python 3.12 resource scan but
   exposed a second opcode-trace portability issue fixed in `cce58e6`, while run `31086926485`
   exposed the original resource-scan race before `f1bcda2`. Earlier runs `31081165976` and
   `31081113394` failed at nested `mount_setattr` before the capability repair.
2. Record the initial review's eight finding dispositions and the repair SHA on PR #61. Because the
   repair materially changed behavior, run one conditional final independent review of the final
   diff and record its SHA-bound envelope; no further local repair loop is allowed after a
   non-trivial final-review finding without re-scoping the slice.
3. Mark the PR ready, verify exact head/base ancestry and merge-commit-only policy, then merge with
   the GitHub connector using the exact expected head SHA.
4. After merge, perform the bounded retrospective and refresh main without discarding the
   intentional primary-worktree change. Do not begin another roadmap gate in this execution.

## Latest verification

- `git diff --check`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS after the
  interpreter-stable resource-scan and cleanup-boundary repair (focused; installed profile
  deferred).
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-unit-smoke`: PASS after the
  aggregate quota descriptor-reopen and opaque overlay-work repairs.
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
- Baseline recorder: two deterministic-reference samples PASS from source `f1bcda2` using
  detached Align `d9fb5da`; oracle `dbdc3f0` and finalization `40c9c41` are committed.
- `make baseline-check`: PASS, including canonical oracle, invalid-input, and failure-retention
  smokes.
- `git diff --check`: PASS after the opaque overlay-work repair.
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
- Diagnostic worktrees `/tmp/align-llm-fresh-aggregate-diagnostic` and
  `/tmp/align-llm-fresh-aggregate-diagnostic-v2`, plus their diagnostic branches, are intentionally
  retained for hosted aggregate diagnosis; never merge their diagnostic-only instrumentation.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted `HANDOFF.md`.
  Do not discard or overwrite it.
