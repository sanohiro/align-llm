# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Current state

- Branch: `agent/fresh-worker-capability`, based on `origin/main` merge commit
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18`.
- Open draft pull request: #61, merge-commit-only. Latest product implementation commit:
  `19809d2`; a handoff update follows it before the required baseline refresh.
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
  during live quota polling; the worker unit smoke covers both regressions. The latest repair
  provisions one aggregate-owned descendant user namespace before capability reduction, writes
  `setgroups=deny` and the exact `0 0 1` UID/GID maps, and passes its namespace descriptor to the
  nested coding-task bwrap with explicit non-user namespace flags. The descriptor is reused for
  the capability probe and both validation runs, then closed on success or failure; the helper
  follows the aggregate parent's death signal. The worker and mount-guard contracts, static
  qualification, and invalid-task smoke cover the new boundary.
- Local Docker is unavailable; installed-image and capable aggregate evidence must come from the
  hosted Ubuntu 24.04 profile.
- The installed profile exposed two post-review integration defects: the nested forwarder did not
  preserve `--userns <fd>` until `ceedd05`, and a read-only source volume copied fixture files as
  `0444`/`0555`, which is fixed by `19809d2` before the next baseline and hosted run.

## Baseline provenance

- Previous source/checkpoint: `32f1a26ae92c33f38935eaf58fc4ffe9f0d051cd`.
- Previous immutable oracle: `ae941b4a658e8b8bc1a81a98ce08478930997063`.
- Previous finalization: `4e828e5d0fb9d9764f0200f799909961ba04cf07`.
- The runner changed after that finalization; restart the Section 2.4 source, pending-measurement,
  oracle, and finalization sequence from the clean handoff source commit before hosted evidence.

## Next steps, in priority order

1. Commit this handoff as the clean source checkpoint, run the Section 2.4 two-sample baseline
   refresh, and pass `make baseline-check`.
2. Push and complete hosted CI for the refreshed head; confirm the installed profile reaches
   capable evaluation and the exact aggregate capability contract passes.
3. Finish the independent comprehensive review, record the initial eight finding dispositions and
   the final SHA-bound envelope on PR #61, then mark ready and merge with the GitHub connector
   using the exact head SHA and merge method `merge`.
4. After merge, perform the bounded retrospective, refresh main without discarding the intentional
   primary-worktree change, and stop this execution. Do not begin another roadmap gate.

## Latest verification

- `git diff --check`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile eval/runners/run-coding-task.py scripts/run-fresh-worker-qualification`: PASS.
- `gcc -std=c11 -Wall -Wextra -Werror -O2 -static -o /tmp/align-llm-mount-guard-test image/fresh/mount-guard.c`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-coding-task-invalid-smoke`: PASS, including missing
  bubblewrap, probe failure, prepared-userns FD, validation quota, and Git replacement cases.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS after the
  nested validation namespace repair (focused; installed profile deferred).
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-unit-smoke`: PASS after the
  aggregate quota, opaque overlay-work, and nested validation namespace repairs.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-image-control-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-coding-task-resource-scan-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 bash scripts/run-coding-task-git-config-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile eval/runners/run-coding-task.py`: PASS after
  read-only fixture mode normalization.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-coding-task-invalid-smoke`: PASS after read-only
  fixture mode normalization.
- The latest hosted run `31104118223` passed the pinned job but the installed profile failed at
  coding evaluation: nested validation was then fixed by `ceedd05`, and the remaining
  read-only-fixture mode issue is fixed by `19809d2`; new hosted evidence is required.
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
  smokes, after the two-sample refresh from source `32f1a26`.
- `git diff --check`: PASS after the nested validation namespace repair.
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
