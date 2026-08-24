# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active checkpoint (2026-08-24)

- C6-MEASURED (C6e/C6g1/C6g2) is implemented on branch `agent/c6-measured`, head
  `1d9daedc1ca5459507234ae3edafffefb5235780`, and is not yet published. The measured gate is real
  and green: `scripts/prompt-gate-validator.py` exits 0 against the checked-in `eval/prompt/gate/`
  bundle with all five explicit inputs.
- The frozen `eval/prompt/canonical-v1/` scope now names a real provider: `LOCAL_OPENAI` on
  `http://127.0.0.1:18080/v1/chat/completions`, model `qwen2.5-coder-7b-instruct-q4_k_m`,
  `api_key_env: null`. `provider_service_revision` carries llama.cpp `b10610` /
  `a14dba686aaafba3a2d6b5eb8820b0df5c5d2d92`, the `llama-server` digest, and the model digest.
- Measured result (`c6g2-measure`): `IMPROVED`, `gate_eligible: true`, zero serious regressions,
  completion gain 2. `duration-half-away-from-zero` moves 0/2 -> 2/2 under a model-proposed
  candidate that enables the context sections; the other two tasks fail in both variants. A
  parent-vs-parent null replicate over the same corpus flipped no cell.
- The gate run found and repaired five shipped defects no fixture reaches: three canonical
  `Option::None`-omission mismatches (experiment-result decode, aggregate optional set, and the
  activation-lineage identity the gate validator compared against the envelope instead of the
  nested activation), a stale `c6-prompt-state` fixture that left `prompt-state-smoke` red on the
  hosted lane at `52aefeb` and `19c6bed`, an overlapping automatic snapshot path set, and a 2 MiB
  sealed-input cap that could never admit the derived generation child. Repairing the measurement
  adapter rebound the frozen digest chain; only digest bindings moved.
- Next actions, in order: (1) one comprehensive review of the branch; (2) publish the pull request
  with the measured claim, the per-cell matrix, and the validator transcript; (3) wire the
  `C6_GATE_*` values into a real `make ci` gate target, which is still `@exit 1`.
- The measurement environment is a privileged `linux/arm64` container (`c6g2-measure:latest`) with
  `bubblewrap` installed at run time; the image does not ship it and the validation runner requires
  it. Docker's default seccomp/AppArmor blocks the runner's user namespaces, so the container needs
  `--privileged`. Both are environment facts, not repository state.
- C6-EVALUATION merged as align-llm PR #100
  (`282062bf00416f5e0df678b8bd885709084b4e16`); its final capable integration gate passed at head
  `049172f5be57002c2426f012fe23038f570f5069` in pull-request CI run 32490981785, including both
  installed native profiles; main push run 32493880784 reused that exact evidence on the merge
  commit. `.align-revision` remains pinned to Align
  merge `19c3db144c462bf7d6784f88d64cc124229b7ec2`. The next eligible roadmap capability is
  C6-MEASURED (C6e, C6g1, C6g2).
- Align-llm PR #94 merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`, with the C6a1/C6a2
  graph-and-codec capability pinned to Align merge `a440970ac81118ed2169f600b2b3c06fcb9cde7`.
- The register records Requests 7, 8, and 10–18 as `ALIGN_LLM_VERIFIED`; the merged C6-EVALUATION
  gate advanced Requests 11 and 14. Requests 2 and 9 remain `ALIGN_MERGED` for their later named
  consumers (C6e/C6g1 provider timeouts and the C7 owned-JSON consumer); both surfaces are already
  contained in the current pin, so no pin bump is required to adopt them. Every open Align request
  now has a merged Align-side surface; no request is `PROPOSED`, `ACCEPTED`, or `IMPLEMENTING`.
- The merged C6-EVALUATION capability drives the deterministic two-task corpus through source/workspace verification,
  alternating parent/candidate execution, fixed contained adapters, before/after snapshots, strict
  prefix verification, and immutable result/evidence publication. Invalid pre-execution inputs are
  result-only; operational failures retain the exact valid trace prefix and paired evidence. Its
  review reopened exact interpreter identity, descendant ownership, FILE_SET physical traversal,
  nested deadline hierarchy, pre-allocation result binding, validation precedence, and capable-gate
  execution as one runtime-containment axis. The final ownership review additionally reopened exact
  per-invocation workspace admission, cleanup-before-pair construction, immediate publication-owner
  retirement, and bounded FILE_SET decimal decoding on that same axis. The merged implementation binds
  and descriptor-launches the exact CPython/helper/Git bytes, gives nested owners cleanup/report
  margins, streams canonical result binding, proves private process-group absence, admits only the
  current invocation's four workspace names, constructs terminal evidence after owned cleanup,
  retains FILE_SET roots/manifests/final files, and executes the complete evaluator adoption owner
  inside capable-only `make ci`. The later exact-head review reopened the inner retained-input and
  admission-bounds axis: the fixed adapter now executes sealed admitted runner bytes and passes
  sealed task/patch descriptors, artifact schemas are complete before side effects, reviewed TREE
  enumeration is bounded while it occurs, and publication uses a fixed-size content-bound sibling.
  The replacement review then reopened semantic consumption; prompt limits, complete persistent
  drift, snapshot declaration caps, unavailable-source non-gate execution, and containment-first
  measurement validation now follow the already-settled contract.
- Align-llm PR #96 merged as `df8b872d1ed766b5bbca643729bb2dfdb08bde3`. C6d now builds on that
  decoded verifier: `prompt accept` verifies result/evidence before constructing an immutable
  activation, `prompt rollback` validates immutable lineage, and both commands use retained-root
  reads plus exclusive result creation. Evaluator/provider execution remains in the named later
  waves.
- The managed exact-pin compiler materializes successfully. PR #94's owner wave, hosted checks,
  fresh-focused qualification, and both installed native profiles passed at head
  `954258e24d93300dcdb78f8280de8868cf1ced56`; main push CI run `32111007638` reused that exact
  evidence on merge commit `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`.
- Align PR #812 merged the bounded `std.http` response implementation as
  `5aa5b23ace02109ad5ef9c36ba6d2acaba9ae7ad`. PR #90 pins that exact merge, adopts the shipped
  bounded/chunked provider surface, and closes Requests 4 and 5.
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
  `c37d79a180612c345551e259091b0b5acf2cb9cd`. Requests 4 and 5 are `CLOSED`; Requests 8, 10, 11,
  and 12 are `ALIGN_LLM_VERIFIED`; Request 11 advanced when the merged C6-EVALUATION gate passed
  in PR #100.
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

- `align-llm` is a continuing real-client testbed for Align. During every capability, record any
  genuine Align language, compiler/runtime, or standard-library requirement in
  `docs/align-requests.md`, even when non-blocking or temporarily avoidable in the application; do
  not let an application workaround hide a language-owned gap.
- `.align-revision` is the only implicit compiler selector. Ordinary commands use the managed exact
  pin; `ALIGNC` and `ALIGN_REPO` remain explicit overrides.
- ALIGN-ADOPTION remains an ordered checkpoint inside a consuming capability, not a pin-only pull
  request. The merged bounded provider-response consumer applies the cap, switches real provider
  fixtures to chunked framing, and owns the combined Requests 4/5 acceptance gate.
- C6-LIFECYCLE has completed the Request 7/8/10/12/13/15 adoption wave in PR #94, Requests 16/17
  through the real decoded verifier, and Request 18 through the C6d retained-root lifecycle owner.
  The public verifier keeps its settled borrowed signature and no compatibility API was added.
  Requests 11 and 14 are adopted by the contained evaluator and pair-publication owners. Requests
  4–6 are closed with real-client and native installed-profile evidence.
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

- `make provider-smoke` at the exact pin `19c3db144c462bf7d6784f88d64cc124229b7ec2` on native
  Linux `x86_64` (WSL2, 2026-08-24): PASS, including adapters, chunked SSE, framing failures, the
  bounded-response matrix with the `Error.Code(-1)` limit sentinel, HTTP 413, status diagnostics,
  exact prompt count, and the common result format. This re-verifies the adopted Request 5
  transport at the current pin for the C6-MEASURED ledger. `make check` at the same pin: PASS,
  20 units per-unit.

- Pre-merge C6-EVALUATION owners `gmake --no-print-directory c6-evaluation-adoption`,
  `gmake --no-print-directory c6-prompt-artifact-adoption`, `gmake --no-print-directory check`, and
  `gmake --no-print-directory format-check`: PASS at Align
  `19c3db144c462bf7d6784f88d64cc124229b7ec2` after the reopened
  deadline/allocation/precedence/gate repair and the final ownership-boundary repair. Source
  `163af7baa210`, oracle `549db0052fc2`, and finalization `d8d45c806658` form the ownership-repaired
  passing identity-bound baseline chain. The exact-head review of that chain found the remaining
  cross-process result-boundary class: nested-session descendants, unbounded adapter diagnostics,
  operational runner failures scored as tests, pre-creation child-output ownership, deterministic
  prepared-output cleanup, missing output-parent preflight, invalid-ID result suppression,
  malformed unavailable-source envelopes, behavioral publication gaps, and stale continuity. The
  reopened §10.1g redesign is complete. Source `1b9b98785743`, oracle `a8f4a2990cd3`, and
  finalization `72e931685fa3` form its passing replacement identity-bound baseline chain. Its
  exact-head review found the remaining reviewed-source execution-boundary class: unbound outer
  evaluator bytes, task code before or unrelated to source observation, task-repository Git config,
  late TREE/task bounds, incomplete child-result validation, missing cross-invocation drift,
  incomplete environment-policy validation, and partial result-only publication. The reopened
  §10.1h redesign is complete. Source `c24e82462a64`, oracle `d023c2f9c6d5`, and finalization
  `75cfc9c79b38` form its passing replacement identity-bound baseline chain. The redesigned
  exact-head review found the retained-source/complete-score class: an outer pathname reopen,
  corpus files not proven as commit or FILE_SET members, task-cwd helper resolution, fixture-only
  scoring, incomplete automatic snapshots and child observations, raw-only FILE expectations, and
  generic mismatch errors. The reopened §10.1i redesign is complete. Source `6e52ff04a698`, oracle
  `1e07ffe13553`, and finalization `365249123ec6` form its passing replacement identity-bound
  baseline chain. Its exact-head review at `0c2f24bd7889` found incomplete artifact schemas before
  side effects, runner/task/patch pathname reopen after adapter admission, unbounded reviewed TREE
  enumeration, and overlong publication temporary components. The reopened §10.1j redesign is
  complete. Source `00f7c7964e04`, oracle `2d15069c7d6f`, and finalization `ef174295ce5a` form its
  passing replacement identity-bound baseline chain. Its replacement exact-head review at
  `8fd2dfa5884f` found missing prompt-size enforcement, partial cross-invocation input comparison,
  late static-expectation bounds, unavailable-source aborts, and reversed containment/cleanup
  precedence. Because that revised review found new P1s, §10.1k reopened the semantic axis and
  closed the complete measurement state machine plus the same-class retained patch-size and
  snapshot-result bounds. Source `06e5e28b2892`, oracle `b8f6e0ece59b`, and finalization
  `d40cab8bdbf4` form its passing replacement identity-bound baseline chain. Subsequent gate
  integration made the request fixtures portable, bound fresh tools and the authenticated Git view,
  and preserved the aggregate's output-only overlay contract. Exact-head preflight and the final
  capable gate passed at head `049172f5be57` (CI run 32490981785) before the PR #100 merge; the one
  full-diff review is the §10.1k finding ledger. Focused evidence covers Request 11 exact-cap,
  over-cap, timeout, post-EOF, concurrent, and descendant cleanup; Request 14 collision, competing
  creator, special-file, reverse-cleanup, and exact owned-orphan recovery; source identity and local
  Git isolation; workspace/snapshot mismatch and drift; adapter failure prefixes; result-only
  invalid inputs; content-bound interpreter/helper/Git launch; evaluator/helper/adapter descendant
  cleanup; exact Git-blob and FILE_SET task-source membership; retained evaluator/helper execution;
  automatic identity-input drift; canonical FILE mode/content identity; exact snapshot observation
  closure and mismatch families; every complete score status and gate path; raw-byte FILE_SET
  traversal and physical-alias rejection; schema-v1 byte goldens; complete artifact-schema
  rejection before child launch; exact and cap-plus-one TREE entry/byte enumeration; retained inner
  runner/task/patch replacement races; 255-byte publication basenames; parent/candidate prompt-byte
  limits; complete automatic-input drift; present-mismatched and absent-unverified sources; all
  measurement states and containment-first failure precedence; and lifecycle consumption of the
  evaluator-produced pair.
- C6d owner: `make c6d-request18-adoption` and the final capable `make ci`: PASS at Align
  `19c3db144c462bf7d6784f88d64cc124229b7ec2`. The focused owner covers request and artifact bounds,
  retained-root symlink/special-file rejection, deterministic error precedence, exclusive output
  preservation and creator races, verifier-first acceptance, immutable rollback, and CLI behavior.
- C6c2 and borrowed-projection owners: `make c6-borrowed-option-adoption`,
  `make c6-borrowed-array-adoption`, and `make prompt-verifier-smoke`: PASS at Align
  `cdf333dc0707edbc4984dc8b1cb6b52edf7b48d0`. The verifier owner covers eligible and ineligible
  completion, all incomplete trace states, compact overflow, status/aggregate/reason/gate tampering,
  evidence order/duplication/digest tampering, and caller-owned record reuse.
- C6b-memory candidate owner evidence: `make prompt-model-smoke`, `make failure-memory-smoke`,
  `make check`, `make format-check`, and `git diff --check`: PASS against the exact pinned
  compiler; the owner covers chronological bounded selection, source/schema invalidation, policy
  caps, UTF-8 rendering, and SHA-256 preservation.
- Align Request 13 implementation PR #854 merged as
  `340a3304724fefb56c2b1aa642e6b2b2c169e6d7`; its required
  `cargo build --release --workspace` passed. Align-llm PR #94 then passed the exact C6a1/C6a2
  adoption target and final C6-LIFECYCLE `make ci` at `954258e24d93300dcdb78f8280de8868cf1ced56`,
  and merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`.
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
- align-llm PR #90 merged as `bb86e9f8a1b9e2ab07500152b81e173a13400a06`. Exact-head preflight
  at `0987a2271034881fd1ac27101aa695e94c7729e5` passed the `fresh-image` lane, including the native
  Linux `aarch64` installed profile in 533,103 ms and worker aggregate in 179,830 ms. GitHub's
  pinned checks passed in 2m06s, native `x86_64` in 17m16s, and native `aarch64` in 18m16s.
- `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker --align-repo /Users/hiro/Projects/align`:
  PASS at `0f9e08eee427` on native Linux `aarch64`.
  The installed profile, Request 6 boundary, fresh compiler, worker aggregate, canonical baseline,
  complete `make ci`, resource owners, and cleanup pass; the worker aggregate took 172,039 ms and
  the complete installed profile took 514,222 ms.
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
- The bounded-adoption publication preflight re-exercised the focused owners on a native Linux
  `aarch64` capable helper. A faster tmpfs ordering exposed that the two post-enumeration source
  mutation fixtures accepted only `OSError` as evidence even though the worker's retained-snapshot
  rejection is the documented `ValueError("materialization source changed")`. Both fixtures now
  require their mutation seam and accept either `OSError` or that exact `ValueError`, matching the
  existing same-size post-write row without allowing unrelated validation failures. The same run
  exposed a timing-dependent quota-disappearance fixture; its stat seam now injects exact `ENOENT`
  results and proves one strict and one live mutation. The tmpfs owner then exposed that scanning a
  retained readable directory descriptor can retain an exhausted or pre-population stream offset;
  every private-root quota pass now reopens the admitted directory through its retained descriptor,
  so newly staged entries and repeated scans are visible. Native ARM `run-fresh-worker-unit-smoke`
  passes with the consolidated repair on tmpfs.
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

1. Merge the register/HANDOFF reconciliation branch `agent/reconcile-request-register`, which
   records the passed C6-EVALUATION capable gate and advances Requests 11 and 14.
2. Begin C6-MEASURED (C6e, C6g1, C6g2) as the next consumer capability on a fresh branch: bounded
   provider proposal, declared decoding, secret redaction, real consumer, frozen corpus and
   policies, real parent/candidate comparison, checked-in gate evidence, accept decision, and
   linked rollback. The triggered design gate is satisfied: §11.3 of
   `docs/specs/c6-prompt-context-optimizer.md` is the settled public-contract ledger and closure
   matrix (new `prompt_experiment` surface and `PromptExperimentStatus`, the
   `PromptExperimentRequest` record, reuse of the settled kind-`OPPORTUNITY` text artifact,
   credential/redaction surface, provider error mapping with the `Error.Code(-1)` limit sentinel,
   shared seed extension and `pub` serializer exports, parameterized transport cap, Request 2
   adoption target, C6g asset paths, and the gate-validator identity).
   Implementation may start immediately against that ledger; no further design pull request is
   required.
3. Inside C6-MEASURED, adopt Request 2 (plaintext/TLS provider timeouts) through its named
   C6e/C6g1 owners against the existing pin `19c3db144c46...`; no pin bump is required. Advance
   Request 2 only after its named owners and the wave's final capable gate pass. Do not infer a
   provider-quality claim before this wave's measured gate.
4. After C6-MEASURED, begin C7-PERSISTED-RESULT per `docs/specs/c7-persisted-result.md` and adopt
   Request 9 through the named C7 adoption fixture before product code consumes the owned-JSON
   surface.

## Recovery and preservation

- The failed non-passing baseline chain is superseded evidence, not an accepted checkpoint. Preserve
  its commits in history and replace it through the required source -> oracle -> finalization chain;
  do not amend or rewrite it.
- No generated compiler, image, cache, seed, or signing material belongs in Git.
- PR #84 supersedes paused PR #69; retain GitHub history as provenance, not as active evidence.
- Preserve the untracked primary-worktree `io_copy`; it is outside this docs-only checkpoint.
- The named stash `codex-preserve-local-doc-fixes-before-pull-2026-08-16` is a temporary safety copy
  of the pre-refresh local documents. Drop it only after this checkpoint is merged and its final
  diff is confirmed.
- The named stash `stale-request14-16-17-responses-superseded-by-origin-2026-08-24` holds a
  2026-08-19 local register draft whose Request 14/16/17 responses were superseded by the merged
  register; its only unmerged fact, the complete 40-character Request 16 merge hash
  `8557c1525aefd9a4afef02d1ec5c2f88e16db4e4`, is carried by this reconciliation. Drop the stash
  after this checkpoint merges.
- Do not use destructive checkout/reset or broad cleanup. Keep code, documentation, commits, pull
  request metadata, review records, and diagnostics in English.
