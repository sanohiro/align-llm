# Session handoff

Read `CLAUDE.md` first. This file records durable capability state; GitHub owns transient pull
request checks, reviews, findings, and attestations.

## Current state

- Branch: `agent/fresh-image-capability`, based on `origin/main` merge commit
  `1e759732fb7d5737c744b35691ea2fb9900c9065` (PR #59).
- Active goal: merge the reviewed consumer-complete FRESH-IMAGE capability, then start
  FRESH-WORKER without splitting it into helper-only pull requests.
- Complete implementation checkpoint: `e17160948908e0a21238976e6417ff4ed23108ae` installs the Ubuntu
  24.04 image, static supervisor and fixed bootstrap, schema-2 manifest, external image and run
  signing boundaries, protected runtime/cgroup profile, and a hosted installed-image qualification.
  Its consolidated review repair closes FIFO deadline, non-root ownership, installed-platform
  coverage, native environment/descriptor isolation, and atomic cleanup findings. The hosted
  qualification also handles both cgroupfs and systemd Docker drivers while entering the same fixed
  delegated cgroup before the native supervisor runs as the repository uid. Its hosted capable
  environment enables nested user namespaces only for the qualification and restores the runner's
  original AppArmor restriction afterward.
- FRESH-IMAGE has not merged yet. FRESH-WORKER implementation has not started.

## Next actions

1. Satisfy GitHub merge readiness for the current head and merge FRESH-IMAGE after final integration
   evidence is green. No persisted artifact in this slice requires a nonstandard integration method.
2. Refresh `main`, perform the bounded post-merge retrospective, and start FRESH-WORKER as the next
   consumer-complete capability. Its core end-to-end smoke must use the installed FRESH-IMAGE trust
   root; focused security, race, resource, mutation, and failure-injection qualification stays out
   of routine `make ci`.

## Latest verification

- `git diff --check`, Python AST parsing for changed Python owners, and Ruby YAML parsing for
  `.github/workflows/ci.yml`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-attestation-wire-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-image-control-smoke`: PASS, including
  deterministic ELF construction, static supervisor identity, sealed descriptors, exact argument
  admission, loader-variable rejection, and bounded FIFO handling.
- `PYTHONDONTWRITEBYTECODE=1 scripts/run-fresh-image-profile-smoke`: PASS on Docker/Ubuntu 24.04,
  including two reproducible LLVM builds, root-owned immutable inputs, uid 12345 execution, runtime
  binding rehashing, retained tool descriptors, namespace/overlay/no-symlink/read-only-tools probes,
  an actually limited cgroup child, cleanup refusal without partial mutation, external distinct
  Ed25519 keys, and canonical trust/runtime/tool mutation rejection.
- Static cgroup-driver parsing and launch-argument checks: PASS for both cgroupfs and systemd; the
  full local profile passed both its detected cgroupfs path and the forced systemd-style
  launcher/temporary-leaf path.
- Workflow YAML parsing and shell syntax checks for the nested-user-namespace setup and restoration:
  PASS; a local nested user namespace probe also passed without changing host policy.
- `PYTHONDONTWRITEBYTECODE=1 make ALIGN_REPO=<detached pinned Align worktree> ci`: PASS at Align
  revision `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.
- `actionlint` and `shellcheck`: N/A because neither command is installed. The changed workflow was
  parsed as YAML, its shell blocks ran through the installed profile path where applicable, and the
  repository's own aggregate topology check passed.

## Blockers and decisions

- No implementation blocker is known. `.align-revision` remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; FRESH-IMAGE does not adopt a new Align surface.
- The implementation and consolidated review repair remain one capability because the supervisor,
  bootstrap, manifest, deployment signer, runtime provisioner, installed image, and external
  profile smoke form one signed trust tuple. Splitting them would create unusable intermediate
  contracts and repeat the same expensive image qualification.
- The installed image profile is a focused hosted job, not a permanent transitive child of routine
  `make ci`.
- The separate primary worktree has intentional uncommitted state, including `HANDOFF.md`; do not
  discard or overwrite it while this clean worktree is active.
