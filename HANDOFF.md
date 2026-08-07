# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active checkpoint (2026-08-07)

- Branch: `agent/request6-image-profile-extension`, based on merged `main` commit
  `11262a785f4c994ecfae2d9d95f67f32d7056108`. The implementation is committed at
  `84490bc` and is not yet published.
- Active goal: merge the separately gated FRESH-IMAGE-REQUEST6 installed profile extension after
  the reviewed Request 6 design PR #63. This slice installs the image-owned dispatcher and
  namespace-helper binding, extends the schema-2 runtime manifest, retains the absolute Align root
  and supervisor channel, signs the ordinary-adoption wire, and rejects the absent consumer worker
  before Make. The complete consumer worker/namespace/build path remains a later slice.
- The profile intentionally proves only the installed image boundary: exact ordinary selector and
  environment, FD 14 retained dispatch, FD 17/18 absolute-path handling, FD 15 nonce and FD 16
  ticket/proof transport, fixed capsule/worker memfd names and seals, raw-tree and
  source-exception goldens, direct entrypoint rejection, and pre-Make revision rejection.
- The implementation is over 1,000 hand-written changed lines by design: dispatcher, retained-FD
  launchers, helper binding, manifest, image smoke, and qualification ownership form one signed
  installed-profile capability and cannot be independently attested as intermediate images.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted `HANDOFF.md`; do
  not discard or overwrite it.

## Next steps, in priority order

1. Push the branch, open the English PR, and record the exact focused checks plus the local Docker
   limitation; hosted Ubuntu 24.04 must run the installed profile smoke.
2. Obtain one fresh independent adversarial comprehensive review of the complete PR diff. Record
   the SHA-bound review envelope and every finding disposition in GitHub.
3. Apply all valid findings in one consolidated repair, rerun affected checks, and merge only after
   the final integration checks and review evidence pass. A material redesign requires a new slice
   and review rather than an indefinite repair loop.
4. Refresh `main`, perform the bounded post-merge retrospective, update the primary handoff, and
   start the next eligible adoption implementation slice.

## Latest verification

- `git diff --check`: PASS before commit.
- `make gate-topology-check`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-attestation-wire-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-manifest-wire-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-image-control-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-focused-adoption-smoke`: PASS. This
  independently checks the 1348-byte raw-tree golden, 1755-byte source-exception golden, 1314-byte
  ordinary predicate golden, and 1385-byte DSSE PAE golden.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS; focused owner
  rows passed and installed-profile rows were explicitly deferred.
- `scripts/build-fresh-image-control --output-dir ... --cc clang`: PASS; all four deterministic ELF
  control outputs built. No generated outputs are tracked.
- `scripts/run-fresh-image-profile-smoke`: not passed locally. Docker image build completed, but the
  first installed `docker run` could not connect to `tcp://0.0.0.0:2375`; the invocation was
  interrupted and must be treated as installed-profile unavailable, not as a failure-free run.
- `make check`, `make build`, `make ci`, and Align source formatting: N/A for this image/profile-only
  slice; `.align-revision` and Align source are unchanged. Hosted installed profile evidence remains
  required before merge.

## Constraints and intentional state

- Keep repository source, documentation, commits, PR metadata, and diagnostics in English.
- Do not change `.align-revision` in this slice. The pinned repository value remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.
- Do not commit model weights, generated binaries, credentials, deployment seeds, or machine paths.
- GitHub owns transient PR checks, review findings, and attestations; do not mirror them in follow-up
  branch commits.
