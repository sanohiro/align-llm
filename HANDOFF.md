# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-adoption-contract-v2`, with corrected design content complete at
  `af7b2016c17e09f9db6dfa1517070fe93d31d297`, based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`. This handoff-only metadata update follows that
  design commit; no design content follows it.
- Active goal: finish and merge the corrected Request 6 focused-adoption design, then implement
  the ordinary launcher, focused target and fixtures, shipped Align pin, fresh adoption vector,
  baseline ancestry, and final fresh `make ci` on a new branch. Request 7 and later consumers stay
  blocked on this gate.
- The corrected design enters through trusted image-owned
  `fresh-supervise --mode ordinary-adoption`, which authenticates the fixed manifest, retains the
  Request 6 dispatcher at FD 14, and invokes it with `execveat(AT_EMPTY_PATH)`; the dispatcher
  authenticates the project snapshot and sealed worker before any repository Make code runs. The
  cgroup start gate remains on FDs 10/11, while the signed `ordinary-adoption/v1` capsule and sealed
  worker use the disjoint FDs 12/13. The worker executes exactly
  `/usr/bin/python3 -I -B /proc/self/fd/13 --project-root-fd 4 --capsule-fd 12`, owns bwrap/cgroup/
  staging setup, and passes those seals to `adoption-namespace`, which owns only the three fixed
  Make vectors. Every manifest tool is retained into the namespace-owned read-only `/tools`
  inventory; its setup-only `/private-tool-inventory` mount is detached before children start.
  Project scripts remain interpreter/data arguments, Cargo admission uses the 24 GiB materialization
  bound with the metadata reserve, and the exact capsule predicate/PAE golden is recorded in the
  adoption gate. The capsule now defines the complete `raw-tree/v1` preimage and exact
  `HANDOFF.md` exclusion; `/usr/bin/bwrap` is the retained FD-27 pre-namespace executable; the
  public ordinary profile is a direct runner `execve` with no preceding shell or `/usr/bin/env`;
  `ordinary-adoption` is present in the supervisor ledger; and deferred golden/closure owners are
  explicitly not claimed as passed by the docs-only gate. FRESH-IMAGE-REQUEST6 is a separate
  installed-profile prerequisite. A fresh independent review of `af7b2016` is required.
- PR #62 is superseded and must not be merged. The replacement design PR must include the corrected
  vectors and current handoff state.
- Expected post-merge checkpoint: refresh `main` safely, perform the bounded design retrospective,
  and create `agent/request6-image-profile-extension` for the separately reviewed installed-profile
  gate. After that profile extension merges, create `agent/request6-adoption-implementation`; the
  implementation branch must not reuse PR #62's direct ordinary Make command.

## Next steps, in priority order

1. Run one fresh independent adversarial review of `af7b2016`, then update the design PR with its
   SHA-bound review envelope and merge it only after checks and all findings are resolved.
2. Record the final review disposition on PR #62, close it as superseded, publish the replacement
   design PR, and complete its review/fix/merge evidence.
3. Refresh `main`, record the bounded retrospective, implement and merge the FRESH-IMAGE-REQUEST6
   profile extension on its own branch, then implement Request 6 on a new branch; review, repair,
   merge, refresh `main`, and continue to the next eligible roadmap gate.

## Latest verification

- `make gate-topology-check`: PASS at `af7b2016`.
- `git diff --check`: PASS at `af7b2016`.
- `for file in docs/align-requests.md docs/specs/check-gate-topology.md; do awk '/^```/ { count++ } END { if (count % 2 != 0) exit 1; print FILENAME ": " count }' "$file"; done`: PASS (96, 76) at `af7b2016`.
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
