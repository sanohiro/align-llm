# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Current state

- Branch: `agent/fresh-worker-capability`, based on PR #61 base
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18`.
- PR #61 is draft and must merge with method `merge`. The current product head includes the
  single-file runtime repair `1d33b90a4200cc3ba756992bb81b229205d46ec2` and the hosted-baseline
  smoke repair `8ff96a8c0db753a4b278a3b6e5186fcc5e8e4887`; the repaired baseline chain is source
  `83d9117f4519f4cb990d64089163713b8bbc749a`, oracle
  `271783e9f35eb7e3575c753ecbbb4e47a4b60a67`, and finalization
  `09fde6c6f203c49ccd8eea743b8b2f466a0b1862`.
- Active goal: finish the reviewed FRESH-WORKER repair, complete PR review/fix/merge, then start
  the next eligible roadmap gate without waiting for a stop instruction.
- The prior baseline tuple
  `6b2828c3f0353cc5cd66854167f350a58faffb4e` /
  `f095a04d898e2b31aa9c8fd7e77a7f213a367369` /
  `870baf4d7faf03f579dde6256e79b4be91168dec` is invalidated. The replacement baseline includes
  `scripts/check-baseline-chain` in the recorded artifact manifest and passes the full chain gate.

## Review and repair

- A fresh independent adversarial review found four valid non-trivial gaps: tool/Git descendants
  were outside the shared worker owner, cgroup leaves were pathname-owned, private-root cleanup
  closed identity witnesses before removal, and `make baseline-check` did not execute the
  Section 2.4 commit-chain contract.
- Closure plan `b69aff1d6c6d8f5f1ed56742aaabc7fcc0dc7451` records the repair owners and regression
  boundaries.
- Implementation `10bcbdd8f112746756069fd72f765843b4ea286b` routes worker children through the
  bounded owner, hardens cgroup and private-root cleanup, hardens image-control children, and
  adds the executable baseline-chain checker. Source `83d9117` also aligns the recorder's
  artifact manifest with the verifier.
- Repair `1d33b90` fixes descriptor-relative materialization of single-file runtime bindings
  such as `/usr/bin/dash` and adds a regression case; the installed hosted diagnostic had
  exposed the prior `NotADirectoryError` at that boundary.
- Repair `8ff96a8` makes the replacement-object smoke explicitly disable the worker's inherited
  `GIT_NO_REPLACE_OBJECTS` only for the probe that must demonstrate replacement resolution; the
  verifier remains isolated with replacement objects disabled. Hosted diagnostic run `31143014723`
  exposed this inherited-environment mismatch after the runtime repair.
- The diagnostic branch `agent/fresh-worker-current-diagnostic` exposed only the hosted
  `filesystem` category before aggregate failure; diagnostic branch
  `agent/fresh-worker-aggregate-diagnostic-v5` isolated the runtime file-open failure and is
  not product code.

## Next steps, in priority order

1. Push the baseline smoke repair and handoff, obtain passing hosted pinned and installed checks
   for the complete repair, publish the final
   SHA-bound comprehensive review envelope and all finding dispositions, mark ready, and merge
   the exact head with method `merge`.
2. Refresh `main`, perform the bounded retrospective, update this handoff for the post-merge
   checkpoint, and start the next roadmap gate.

## Latest verification

- `make check`: PASS; only existing Align compiler warnings remain.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-image-control-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS after the
  immediate rerun of a transient linked-worktree source-identity smoke failure.
- After `1d33b90`, `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS,
  `run-fresh-image-control-smoke`: PASS, and `run-fresh-worker-qualification`: PASS.
- `make baseline-check`: PASS; canonical baseline, invalid-input smokes, failure smoke, and the
  executable source/oracle/finalization chain checker all passed.
- The source recorder completed two deterministic-reference samples from source `83d9117`.
- `git diff --check`: PASS for the source, oracle, and finalization commits.
- `bash -n scripts/run-baseline-invalid-smoke` and
  `GIT_NO_REPLACE_OBJECTS=1 PYTHONDONTWRITEBYTECODE=1 make baseline-check`: PASS, including the
  inherited-environment replacement-object regression.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS after the hosted baseline
  smoke repair.
- Hosted run `31137327638` passed the pinned job but failed the installed aggregate with
  `filesystem`; diagnostic run `31142031436` exposed the underlying single-file runtime
  `NotADirectoryError`; diagnostic run `31143014723` then exposed the inherited replacement-object
  smoke mismatch. All diagnostic runs are evidence only.

## Constraints and intentional state

- Keep all repository source, documentation, diagnostics, commits, and PR metadata in English.
- `.align-revision` remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no Align language request is open for this gate.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted
  `HANDOFF.md`; do not discard or overwrite it.
- Diagnostic worktrees and branches are intentionally retained for evidence; never merge their
  diagnostic-only instrumentation.
