# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-15)

- Branch `agent/http-bounded-adoption` is based directly on `main` at
  `ff600629f961f5532525322519e524664ab2b1ca`, the merge commit for align-llm PR #89.
- Align PR #812 merged the bounded `std.http` response implementation as
  `5aa5b23ace02109ad5ef9c36ba6d2acaba9ae7ad`. This branch pins that exact merge and adopts the
  shipped surface at the provider boundary together with Request 4's chunked-response support.
- The managed release compiler/runtime for the new pin materialized under `dev-v1` as a native
  Mach-O `arm64` compiler with `CARGO_BUILD_JOBS=1`. It passes
  `./scripts/alignc check-per-unit src/main.align`: all 15 units pass with the three existing
  lossy-conversion/large-copy warnings.
- The FRESH-IMAGE-REQUEST6 installed adoption profile is merged and passes its complete native
  Linux `aarch64` and `x86_64` profiles. Request 6 is now `CLOSED`.
- Align PR #801 shipped Request 8 as `029e27465d79e24cd36d374aae41dca0ec7e6979`, and Align PR #804
  shipped Request 10 as `3ec710656c7ce7412da14a5c929529cb3e89caa3`. Align PR #800 shipped
  Request 4 as `f04672bce6f8689c9b219d0a20e770571e2d638b`, PR #808 shipped Request 11 as
  `82da9f580cc005fbb78f67af6847c7b4ce6626c4`, and PR #807 shipped Request 12 as
  `c37d79a180612c345551e259091b0b5acf2cb9cd`. Requests 4 and 5 are adopted together on the active
  provider-consumer branch; Requests 8 and 10–12 remain `ALIGN_MERGED` for their named consumer
  capabilities.
- FRESH-IMAGE, FRESH-WORKER, and FRESH-IMAGE-REQUEST6-BOUNDARY are merged. The migrated profile
  preserves current authenticated cgroup cleanup, phase tracking, multistage image construction,
  and the `25b1201b...` pin while adding the ordinary adoption dispatcher, namespace helper,
  compiler handoff, installed-profile bindings, fixtures, and owner tests.
- The installed profile supports one native-platform capability for Linux `x86_64` and `aarch64`.
  The immutable Ubuntu OCI index, native Rust/Debian/ELF/loader tuple, manifest
  admission, runtime roots, controller, worker, Docker owner, and CI matrix now reject
  architecture mismatch; emulation is explicitly non-acceptance evidence.
- PR #84's final reviewed head is `031917b5518170f905793af65b9cb347b837d178`; its consolidated
  repair commit is `d50373fc14afe2994176bc26fdaa55ad5e9c64b2`.
- The native ARM installed profile now passes image attestation, lifecycle, self-test, trust
  mutations, runtime replacements, the valid ordinary Request 6 consumer, the complete boundary
  rejection matrix, the worker aggregate, and cleanup.
- Baseline commits `db2c88d24574` and `cceaf15fdf0c` intentionally remain historical failed
  measurement evidence: the first ARM helper lacked `/usr/bin/bwrap`, so both recorded tasks were
  non-passing and remain unacceptable as baseline evidence.
- The failed chain and its first passing replacement were superseded after a later full-profile run
  exposed a separate resource bug: after roughly 8.5 GB of authenticated runtime copying, Cargo
  inherited all eight Docker CPUs and `rustc align_sema` was killed with `SIGKILL` in the 8 GB VM.
  Source `cbcde22600e7` introduced `CARGO_BUILD_JOBS=1` in both fresh compiler build paths; the
  current policy retains that bound only on native `aarch64`, while native `x86_64` omits the
  override and uses Cargo's default parallelism. Native ARM
  oracle `12cce0199762` records two passing samples, and finalization `be0131f85c3c` owns the matching
  canonical baseline and digest. `scripts/check-baseline-chain` passes on that exact chain.

## Contract and decisions to preserve

- `.align-revision` is the only implicit compiler selector. Ordinary commands use the managed exact
  pin; `ALIGNC` and `ALIGN_REPO` remain explicit overrides.
- ALIGN-ADOPTION remains an ordered checkpoint inside a consuming capability, not a pin-only pull
  request. This branch is the bounded provider-response consumer: it applies the cap, switches real
  provider fixtures to chunked framing, and owns the combined Requests 4/5 acceptance gate.
- C6-LIFECYCLE remains blocked from product implementation on Align Requests 7 and 13 and on the
  consumer adoption of merged Requests 8, 10, and 12. Requests 7 and 13 remain `PROPOSED`; do not
  consume or imitate those APIs. Requests 4–6 are closed by real clients once this branch's final
  fresh `make ci` passes. Request 11 remains merged for the later C6-EVALUATION boundary.
- Preserve the exact fresh-image trust, descriptor, namespace, cgroup, source-identity, and cleanup
  boundaries in `docs/specs/check-gate-topology.md`. Reclassify and update its closure matrix if the
  migrated diff changes those contracts.
- Future resource tuning may replace the temporary architecture-specific Cargo job policy with an authenticated
  `--cargo-build-jobs auto|N` profile input. The candidate automatic policy is the smaller of
  `max(1, effective CPU affinity count - 1)` and a conservative budget derived from the cgroup hard
  memory limit, with physical memory only as an unlimited-cgroup fallback. An explicit value would
  remain bounded by effective CPUs and the qualified memory budget, and the resolved value would be
  recorded in execution and baseline evidence. This is a deferred design note, not an implemented
  or accepted contract. The canonical native ARM profile remains fixed at `CARGO_BUILD_JOBS=1`
  until multi-job memory measurements justify a change; native x86_64 currently uses Cargo's
  default parallelism as qualified by the 128 GiB owner.

## Latest durable verification

- Align `cargo build --release --workspace` at #786 final source: PASS.
- Align focused owner
  `scripts/cargo.sh test -p align_driver --test m5 owned_string_clone_duplicates_locals_and_fields -- --exact`:
  PASS.
- Align #786 preflight: PASS (owner, lint ratchet, 16-binary bounded gate, Clippy); all required
  hosted checks passed before merge.
- Align Request 8 design PR #799: comprehensive review found five valid closure gaps and the
  consolidated repair added checked-HIR rows, reconciled builder transfer and nominal identity,
  added the same-shape nominal twin, completed the Move-source matrix, and parameterized cleanup
  over stack-local and boxed headers. Exact-head docs preflight, native Linux ARM64, Linux x86_64,
  macOS Apple Silicon, PostgreSQL integration, pre-PR attestation, and post-open review all passed;
  merged as `60622c60a4fc21b8586e1f6a907c32c025aa1658`.
- `scripts/align-toolchain ensure compiler` for `5aa5b23a...`: PASS with native ARM and one Cargo
  build job; managed compiler path is under `~/.cache/align-llm/align/dev-v1/5aa5b23a...`.
- `./scripts/alignc check-per-unit src/main.align`: PASS, 15 units. The direct bounded HTTP adoption
  fixture and provider smoke pass locally against the exact pin: exact/cap-plus-one fixed and
  many-tiny-chunk bodies, bodyless/interim framing, exact/cap-plus-one trailers, connection reuse
  and teardown, chunked OpenAI/llama SSE, malformed/truncated framing, limit code `-1`, and HTTP 413.
- Latest pinned compiler Request 6 matrix: four owned-row fixtures reject with the exact Copy-row
  diagnostic; `copy-row.align`, `decode-owned.align`, and `decode-owned-option.align` run with the
  exact expected output.
- `python3 scripts/run-fresh-focused-adoption-smoke`: PASS in Linux; `./scripts/check-format`, Python
  syntax parsing, the FRESH-WORKER qualification inventory, and the migrated ordinary cgroup cleanup
  unit cases: PASS.
- Native Linux `aarch64` focused evidence on Docker Desktop: `run-fresh-image-control-smoke`,
  `run-fresh-worker-unit-smoke`, and the complete `run-fresh-worker-qualification` all PASS. The
  ARM run exposed a same-size post-copy mutation whose filesystem timestamps did not change; the
  worker now re-digests the retained source after materialization and the existing regression passes.
- Native Linux `aarch64` installed profile through `boundary-profile`: PASS. This run exposed and
  repaired the focused-row prefix slicing and bare-Git fixture setup bugs; the focused adoption
  owner passes after both repairs. Warm signed-image builds reuse the architecture/toolchain layers,
  reducing the observed image-build phase from 1,065,794 ms to roughly 20-31 seconds.
- Native ARM diagnostics reproduced ordinary `align-build-only` as Cargo exit 101 and captured the
  exact failing child: `rustc align_sema` exited on `SIGKILL` after the authenticated runtime copy.
  The same pinned compiler builds natively in about 40 seconds when the runtime is bound without
  the preceding copy pressure; compiler/archive type, mode, size, and Cargo hard-link identity are
  valid. Fixed single-job Cargo contract and fresh-worker unit owners: PASS. The repaired native
  ARM ordinary adoption completed with canonical PASS in 225,474 ms, followed by cleanup PASS.
- Native ARM baseline source `cbcde22600e7`, oracle `12cce0199762`, and finalization
  `be0131f85c3c`: PASS. Both deterministic-reference samples pass under native `aarch64` bubblewrap;
  time to passing patch is 135,683,334-174,716,542 ns with median 155,199,938 ns. The canonical
  digest and baseline chain pass.
- `python3 scripts/run-fresh-image-profile-smoke --require-docker --align-repo
  <clean-pinned-Align-checkout>` at `be0131f85c3c`: PASS on native Linux `aarch64`. Boundary profile
  passed in 282,213 ms, worker aggregate in 190,201 ms, and cleanup in 3,345 ms.
- Comprehensive `codex review --base origin/main` reviewed `dae654a` against base tip and merge base
  `350ea497fbf1`. It found three valid ordinary-lifecycle defects: success could be emitted before
  outer cleanup, cgroup cleanup could replace an active build/fixture phase, and equal nested
  deadlines let an outer owner preempt inner cleanup. `b82d3b97ec83` repairs all three; the newly
  visible cleanup failure additionally exposed and repaired fixed bind-FD collision with retained
  Git/tool descriptors. The repair stayed within the reviewed ordinary lifecycle and timeout
  contract, and its focused delta was inspected without triggering another comprehensive review.
- `python3 scripts/run-fresh-image-profile-smoke --require-docker --align-repo
  <clean-pinned-Align-checkout>` at `b82d3b97ec83`: PASS on native Linux `aarch64` after the review
  repair. Image build passed in 23,143 ms, boundary profile in 257,071 ms, worker aggregate in
  174,881 ms, and cleanup in 3,983 ms. Success is now emitted only after the worker-owned root,
  source views, tools, bind placeholders, and cgroup are cleaned.
- Architecture-specific Cargo job owners at `6438dd4a6181`: PASS. Native `aarch64` selects
  `CARGO_BUILD_JOBS=1`; native `x86_64` omits the variable. The full native Linux `aarch64` image
  profile passes with the fixed ARM policy: boundary profile in 288,027 ms, worker aggregate in
  186,162 ms, and cleanup in 2,846 ms. The later required native `x86_64` 128 GiB CI owner passed
  at the final PR #84 head.
- Comprehensive `codex review --base origin/main` reviewed `fff8370c017a` against base tip and
  merge base `350ea497fbf1`. It found seven valid ordinary-isolation defects: staged input mounts
  and tool directories remained reachable or writable; the child could run before parent-verified
  cgroup admission; session-breaking descendants could escape teardown; a phase-channel failure
  could lose the active row phase; source mutation during staging was classified as `toolchain`;
  platform rejection was classified as `unobserved`; and setup failures were classified as
  `build`. Repair `d50373fc14af` closes all seven findings. It seals staged inputs and the namespace
  root, adds a parent-controlled cgroup start gate, kills all subreaper-owned children, preserves
  the active phase on channel loss, and corrects the three failure mappings. The repair implements
  the already reviewed lifecycle contract without expanding capability scope, so its focused delta
  was inspected without triggering another comprehensive review.
- Native Linux `aarch64` owners at `d50373fc14af`: `run-fresh-focused-adoption-smoke` and
  `run-fresh-worker-unit-smoke` PASS in the pinned capable image; Python syntax parsing,
  `check-format`, `check-baseline-chain`, and `git diff --check` PASS. The complete
  `run-fresh-image-profile-smoke --require-docker` passes against a clean checkout of pinned Align
  `25b1201b...`: image build in 29,701 ms, image attestation in 3,597 ms, profile lifecycle in
  3,173 ms, profile self-test in 14,771 ms, trust mutations in 13,740 ms, runtime replacements in
  22,496 ms, boundary profile in 275,309 ms, worker aggregate in 185,239 ms, and cleanup in
  3,410 ms.
- Exact-head publication preflight at `031917b5518170f905793af65b9cb347b837d178`: PASS. The
  installed boundary profile passed in 274,781 ms, worker aggregate in 179,603 ms, and cleanup in
  3,855 ms. Required native Linux `aarch64` and `x86_64` GitHub jobs passed before PR #84 merged.
- The first ARM baseline recorder invocation completed but produced two FAIL samples solely because
  its helper did not install `/usr/bin/bwrap`; schema inspection rejected it as canonical evidence.
- `python3 scripts/test-development-preflight`: PASS in the native Linux `aarch64` capable helper;
  `docker build --check -f image/fresh/Dockerfile .`: PASS with no warnings.
- Local `/usr/bin/make` is GNU Make 3.81, below the supported Make 4.3 floor, and cannot parse the
  repository's target-specific `override export` assignments. Use a capable profile for Make gates;
  do not weaken the Makefile for this host.
- Docker Desktop is native Linux `aarch64`. Do not run or cite an `amd64`-emulated container as
  installed-profile evidence; the native ARM owners are the local acceptance route.

## Next actions

1. Commit the bounded provider-response candidate, perform one comprehensive review, and consolidate
   any valid findings.
2. Run the exact-head publication preflight and final native ARM installed profile (`make ci`), then
   open, review, and merge the pull request.
3. Refresh `main` and continue the next eligible consumer capability. Preserve ARM compiler builds
   at one job; native x86_64 keeps Cargo's default parallelism on the qualified 128 GiB owner.

## Recovery and preservation

- The failed non-passing baseline chain is superseded evidence, not an accepted checkpoint. Preserve
  its commits in history and replace it through the required source -> oracle -> finalization chain;
  do not amend or rewrite it.
- No generated compiler, image, cache, seed, or signing material belongs in Git.
- PR #84 supersedes paused PR #69; retain GitHub history as provenance, not as active evidence.
- Do not use destructive checkout/reset or broad cleanup. Keep code, documentation, commits, pull
  request metadata, review records, and diagnostics in English.
