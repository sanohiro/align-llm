# Session handoff

Read `CLAUDE.md` first. This file records durable capability state; GitHub owns transient pull
request checks, reviews, findings, and attestations.

## Current state

- Branch: `agent/fresh-image-capability`, based on `origin/main` merge commit
  `1e759732fb7d5737c744b35691ea2fb9900c9065` (PR #59).
- Active goal: review and merge the consumer-complete FRESH-IMAGE capability, then start
  FRESH-WORKER without splitting it into helper-only pull requests.
- Complete implementation checkpoint: `03daa89edd0c581a9cd1ab38686fcf5896a706cd` installs the Ubuntu
  24.04 image, static supervisor and fixed bootstrap, schema-2 manifest, external image and run
  signing boundaries, protected runtime/cgroup profile, and a hosted installed-image qualification.
- FRESH-IMAGE has not merged yet. FRESH-WORKER implementation has not started.

## Next actions

1. Open the FRESH-IMAGE pull request from this stable candidate and run one fresh independent
   comprehensive adversarial review over the complete diff using `docs/review-checklist.md`.
2. Record the SHA-bound review envelope and all finding dispositions in GitHub. Apply any valid
   findings in one consolidated repair commit, rerun only affected checks, and merge after final
   integration evidence is green.
3. Refresh `main`, perform the bounded post-merge retrospective, and start FRESH-WORKER as the next
   consumer-complete capability. Its core end-to-end smoke must use the installed FRESH-IMAGE trust
   root; focused security, race, resource, mutation, and failure-injection qualification stays out
   of routine `make ci`.

## Latest verification

- `git diff --check`, Python AST parsing for changed Python owners, and Ruby YAML parsing for
  `.github/workflows/ci.yml`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-attestation-wire-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-image-control-smoke`: PASS, including
  deterministic ELF construction, static supervisor identity, sealed descriptors, exact argument
  admission, and loader-variable rejection.
- `PYTHONDONTWRITEBYTECODE=1 scripts/run-fresh-image-profile-smoke`: PASS on Docker/Ubuntu 24.04,
  including external distinct Ed25519 keys, installed self-test, uid 0 and uid 12345 profile
  lifecycle, duplicate setup rejection, and canonical attestation/bootstrap/manifest mutation
  rejection.
- `PYTHONDONTWRITEBYTECODE=1 make ALIGN_REPO=<detached pinned Align worktree> ci`: PASS at Align
  revision `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.
- `actionlint` and `shellcheck`: N/A because neither command is installed. The changed workflow was
  parsed as YAML, its shell blocks ran through the installed profile path where applicable, and the
  repository's own aggregate topology check passed.

## Blockers and decisions

- No implementation blocker is known. `.align-revision` remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; FRESH-IMAGE does not adopt a new Align surface.
- The 3,215-added-line implementation remains one capability because the supervisor, bootstrap,
  manifest, deployment signer, runtime provisioner, installed image, and external profile smoke
  form one signed trust tuple. Splitting them would create unusable intermediate contracts and
  repeat the same expensive image qualification.
- The installed image profile is a focused hosted job, not a permanent transitive child of routine
  `make ci`.
- The separate primary worktree has intentional uncommitted state, including `HANDOFF.md`; do not
  discard or overwrite it while this clean worktree is active.
