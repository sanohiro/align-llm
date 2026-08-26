# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## C8 eighth capability: move completed result documents (2026-08-26)

- C8 atomic patch application PR #118 merged on `main` at
  `185936492dd52453c8df3fe281c82645373a5946`. Its hosted check passed in 1m35s; the unaffected
  x86_64 and aarch64 jobs completed in 5s and 9s with native qualification skipped. The shipped
  101-pair comparison reduced the fixed task by 22,774 ppm (2.28%).
- `agent/c8-move-process-argv` was measured and rejected without a PR: its 201-pair improvement was
  only 283 ppm (0.028%) and its 31-pair comparison regressed. The local branch preserves that
  evidence; do not carry its product change.
- Active work is on `agent/c8-move-result-documents`. `C8-MOVE-RESULT-DOCUMENTS` moves completed
  owned JSON buffers into their sole returned owner rather than cloning them at the terminal
  handoff. The exact 31-sample `baseline-atomic` at merge `1859364` is 45,870,371 ns; its binary
  SHA-256 is `7e00353a3110c16fd802bb935a9d4bf1be784540f23567cdf4704aee728896f3`.
  Implementation `4f7dd62c3bf6d6e4d81216a44c3b4f2f9bf7eb32` passes `loop-smoke`, `index-smoke`,
  `test-selection-smoke`, `patch-eval-smoke`, and `verify-loop-smoke`. Its exact 101-pair comparison
  measured 46,537,217 ns for the parent and 46,355,109 ns for the candidate, a 3,913 ppm (0.39%)
  reduction; a preceding 31-pair run improved by 5,224 ppm. Normalized documents and all four stage
  records agree. The comprehensive review at `f29b312` was clean: every removed clone is a terminal
  ownership transfer with no later source use, the record owners passed again, and the benchmark
  extension enforces identical normalized four-stage results.
- Ordinary `src/` and platform-independent `eval/` changes now select the pinned hosted graph.
  Fresh-image construction, workflow, classifier, Make topology, worker/control, and their
  qualification owners retain the focused plus installed profile. The Linux sandbox runner
  `eval/runners/run-coding-task.py` is an exact target-local exception. Deletions, renames, unknown
  state, and untrusted no-base events retain their existing fail-closed behavior.
- Align requests 1–20 are closed. Request 19 shipped in Align PR #891 as
  `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`; align-llm publication PR #108 merged as
  `75d7cc39b40b287d47b1185306d6bd8e7eb582dc` after all required CI passed.
- `prompt-verifier-smoke` is restored to the hosted lane. The adopted compiler measured 2.214 s /
  126,192 KiB for `check` and 12.786 s / 259,720 KiB for `build` on the named representative host,
  with exact program output.
- Pure compiler-pin adoption now runs the request owner plus exact managed-toolchain verification
  locally and the ordinary hosted graph in GitHub CI. It does not select native installed profiles;
  mixed executable changes retain their normal scope, and deleted or renamed pins fail closed.
- Platform qualification is capability-owned: run it for changed target-local behavior, a
  target-specific claim, a concrete provider-CI gap, or an explicit audit—not for every compiler
  pin. The policy, classifier, owner tests, and final comprehensive review are complete.
- `C8-TEST-SELECTION-LINEAR` is the first C8 capability. Related-test ranking now makes one tracked
  file pass and emits the same four score buckets in the same order instead of scanning the complete
  list for every integer from 120 through 0. The exact public invariant and focused benchmark are in
  `docs/specs/c8-speed-first.md`.
- The paired fixed passing-patch benchmark measured 48,829,180 ns for the parent median and
  12,465,365 ns for the candidate median across 15 samples each on the named x86_64 host, a 74.5%
  reduction. All non-duration result data agreed. This is a path-specific claim, not a platform
  claim, so the benchmark remains out of ordinary CI and native installed profiles.
- The next C8 capability must again start from measured end-to-end cost. Prefer a boundary that uses
  the current Align surface; captured parallel process execution remains deferred unless measurement
  justifies a genuine Align request.

## Resume in another environment

1. Fetch `origin` and resume `agent/c8-move-result-documents`. Read `CLAUDE.md`, then
   `docs/specs/roadmap.md` §C8 and `docs/specs/c8-speed-first.md` §2.8 and §10. The ledger and exact
   baseline, implementation, owner verification, exact comparison, and clean comprehensive review
   are complete. Exact-head preflight is the first unfinished action.
2. Run exact-head preflight with the record owners, then publish the English PR. The handoff-only
   review-state update does not trigger another comprehensive review.
3. After merge, refresh `main` and choose the next measured consumer-complete C8 boundary.
4. Continue against existing providers. Do not make C8 depend on `align-runtime`, and do not open a
   new Align request unless implementation exposes a genuine shipped-language, compiler/runtime,
   or standard-library gap under the request-register rules.

Two maintenance items remain deliberately deferred rather than active work: preserve the
`eval/runners/run-coding-task.py` zombie-counting behavior until a capability already rebinds and
re-measures the frozen coding corpus or revisits its validation-process budget; replace
`c6f2-request14-adoption`'s publication-race polling with a deterministic seam only when that owner
boundary is next changed.

## Merged checkpoint: REQUEST20-PIN — adopt Align's macOS owned-JSON CI repair (2026-08-25)

- Work is on `agent/request20-align-pin-final`, based on align-llm `main` at `0a8b9cf`. Align Request 20
  shipped in Align PR #887 as `fa3f03f15f0b1d876683343233f440bce6ea27c5`; PR #888 then closed
  its upstream handoff. A later docs-only CI merge, PR #889, moved Align `main` to
  `f57b986bc9326ba8d75dad5dbe4c6531c0f872b6`; `.align-revision` now selects that exact latest
  commit. The compiler/runtime source payload is unchanged, but the managed binary and every
  pin-bound record still require evidence against the new identity.
- The upstream response is verified, not inferred from the PR summary: the required `macos-15`
  Apple Silicon job ran `align_driver --test m5_owned_json` and all 10 rows passed. The same PR
  repairs the storage-generation regression that made `JsonOwnedDecode` retain its input and arena
  facts even though the shipped owner is free-standing.
- The managed release compiler/runtime materializes at the selected latest pin on native macOS arm64 with
  `LLVM_CONFIG=/opt/homebrew/opt/llvm@22/bin/llvm-config`. The first original client fixture passes:
  `gmake --no-print-directory c7-owned-record-source-expiry-adoption` reports 3 parsed fixtures,
  12 example rows, and 45 adoption rows.
- The Darwin profile passed at clean latest-pin head `863ab0d333209fbd90bec0dd4e4148ef56f167f7`:
  `check` 4,677 ms, `build` 5,960 ms, direct `check-per-unit` 4,568 ms,
  `persisted-result-smoke` 3,534 ms, and `persisted-result-qualification` 11,138 ms. The attested
  compiler digest is `ea90318886ebcc9ed9e29b11ea3065c9d91160fea61b0be285d3196ffa1d084e`;
  runtime digest is
  `0c26b938060e747d63886f5f98c07953b69b52d2b572a538373642b96cb75211`.
- The first supervised aggregate correctly rejected the canonical baseline's old Align pin. A
  replacement chain was then mistakenly measured on macOS, where the corpus-fixed
  `/usr/bin/python3` is 3.9 and cannot parse the runner's `float | None` annotation. The recorder
  deliberately persisted two complete FAIL samples, and the negative smoke exposed their null
  aggregate timing. That non-passing chain (`026e3b1` -> `7d24042` -> `1a8b026`) is preserved as
  failed evidence and must not be published as canonical proof.
- The latest accepted replacement was recorded as non-root on native Linux aarch64 in the privileged
  `c6g2-measure:latest` helper with CPython 3.12 and bubblewrap. Both deterministic-reference
  samples passed (133,219,500–141,093,417 ns; median 137,156,458 ns). The strict chain is source
  `3714b371e09ca2937981d9098a167c43084bc0f3`, oracle
  `7080b61f9a4b5b6542b77524f0f6c7b42786b801`, and finalization
  `863ab0d333209fbd90bec0dd4e4148ef56f167f7`; `check-baseline-chain` and `verify-baseline.py` pass.
  The preceding `dc321412` Linux chain remains a valid intermediate pin checkpoint, not canonical.
- The final supervised fresh-image profile passes at `863ab0d`. Phases: image build 33,852 ms,
  attestation 3,354 ms, lifecycle 2,426 ms, self-test 14,769 ms, trust mutations 12,336 ms,
  runtime replacements 21,554 ms, boundary profile 274,947 ms, worker aggregate 424,471 ms, and
  cleanup 1,272 ms. Request 20 is `ALIGN_LLM_VERIFIED` at the selected latest pin.
- The first comprehensive review of `2caae5f` found one valid P2: the request register still called
  the earlier `2f33ac5` revision current. The register now names the selected pin and labels Request
  19's filing-time measurement historical. Because Align advanced during review, the accepted
  `dc321412` evidence above is now an intermediate checkpoint rather than publication evidence.
- The final comprehensive review of `c2cb859` found two valid P2 classes: Request 20 still promised
  its owner on every pull request even though the selected PR #889 workflow deliberately exempts
  trusted docs-only `main` diffs, and Requests 16–18 lacked their already-merged align-llm
  publication links. The repair narrows the CI contract to platform-required pull requests with the
  exact fail-closed exception and records PR #98/#99 merge evidence; no executable or baseline-owned
  path moves.
- Pending at this checkpoint: inspect the narrow review-repair commits, run exact-head preflight,
  and publish. `CLOSED` waits for the resulting align-llm merge.

## Merged checkpoint: ADAPTER-ZOMBIE — descendant-scan containment repair (2026-08-25)

- C7-P merged as align-llm PR #105 (`a4f8663`). The active capability is ADAPTER-ZOMBIE on branch
  `agent/adapter-zombie-descendants`, which closes follow-up item 2 below — the latent
  containment-scan defect deferred from PR #103's CI repair `d7f1ff6`.
- **The defect.** Every `/proc` descendant scan counted any entry whose `PPid:` matched a root,
  including entries in `State: Z`. A zombie has already terminated and only holds a process-table
  slot until someone waits for it, so it cannot escape containment. Under `PR_SET_CHILD_SUBREAPER`
  an adopted orphan that has already exited becomes a permanent zombie child of the scanning
  process, so the scan reported a containment failure for a process that no longer runs. Git 2.47
  detaches auto-maintenance before deciding whether any task is due, which is how PR #103 hit it as
  `generation child left a descendant`. `d7f1ff6` treated that one trigger from the harness side;
  this repairs the class in the scan itself.
- **All six candidates named in the PR #103 diagnosis carry the pattern and all six are repaired**
  (`cf9bd75`): `scripts/prompt-measurement-adapter.py`, `scripts/prompt-evaluate.py`,
  `scripts/prompt-fixed-adapter.py`, `scripts/prompt-gate-validator.py`,
  `scripts/prompt-snapshot-helper.py`, and `scripts/prompt-source-verifier.py`. The
  private-group check is a separate contract and is untouched — a zombie still holds its process
  group open — so each end-to-end regression's orphan leads its own session.
- **The exact-head review found that repair too wide, and `563e3ae` narrows it (finding F1).** A
  zombie is not always a terminated process: when a thread-group leader exits while another thread
  in its group keeps running, the leader stays in `State: Z` and cannot be released, yet the worker
  thread continues to execute. Omitting every `State: Z` entry hid that live descendant. Liveness
  is a property of the thread group, not of its leader, so all six scans now omit an entry only at
  `State: Z` **and** `Threads: 1`, read from the `/proc/PID/status` text already in hand — no second
  filesystem read. The visited-set traversal is unchanged, so a live entry parented to an omitted
  one is still reported. The two parse failures are deliberately asymmetric and both the code and
  the specification now say so: a vanished entry or an absent/malformed `PPid:` line is dropped by
  the shared `OSError`/`IndexError` path and **fails open** for that one entry, consciously accepted
  for parse robustness because without a parent link it cannot be placed in the tree at all; an
  absent or malformed `State:`/`Threads:` line **fails closed** and reports the entry.
- **The regression is the reviewer's own reproduction, and it is a negative control.** Every owner
  with `descendant_scan_rows` carries it — `prompt-evaluate-smoke`, `test-prompt-fixed-adapter`,
  `test-prompt-snapshot-helper`, `test-prompt-source-verifier`, and `prompt-gate-validator-smoke`'s
  `validator` family — and `e41d9ba` added the same three rows to the measurement adapter's inline
  equivalents (73 rows become 74). The fixture forks a child that starts a worker thread and then
  leaves its own leader thread through `pthread_exit`, which the kernel takes as a plain thread exit
  rather than a group exit; the child settles at `State: Z` with `Threads: 2`. Two alternatives were
  measured first: a raw `SYS_exit` through `ctypes` works but needs a per-architecture syscall
  table, and a compiled-at-test-time C helper needs a toolchain in every image. `pthread_exit` needs
  neither and was verified on `x86_64` and `aarch64` glibc CPython, so it is the portable
  construction.
- **A seventh occurrence exists and is deliberately not repaired here, and the deferral now lives in
  the plan.** `eval/runners/run-coding-task.py` has the same scan, but its consumers are
  `kill_owned_processes`/`kill_adopted_descendants` (signalling a terminated entry is a no-op) and
  `validation_process_usage`, which counts processes against `MAX_VALIDATION_PROCESSES = 256`.
  That is a resource-budget contract, not a containment verdict, so it is a distinct failure
  domain; and the file is a frozen `FILE_SET` corpus member, so touching it forces another chain
  rebind and another provider-backed re-measurement. Review finding F2 required this to be a plan
  decision rather than a handoff note, so §1.2 of `docs/specs/c6-prompt-context-optimizer.md` now
  records it with its owner (the coding runner) and its resume condition. Also tracked as follow-up
  item 2 below.
- **Where the rule is written.** The prose is §1.2 "Runtime ownership and bounded persistence" of
  `docs/specs/c6-prompt-context-optimizer.md`; the descendant-ownership ledger rows are §10.1g and
  §10.1c. `cf9bd75`'s commit message cited "section 11.3" for that ledger row, which is the
  C6-MEASURED public-contract ledger instead; the documents now carry the correct citations.
- **Review envelope.** One comprehensive review at head `8e86a22` returned **request-changes** with
  five findings. Dispositions, all accepted: **F1** (blocking, code — the `State: Z` skip hides a
  live zombie leader) closed in code by `563e3ae` and extended to the sixth owner by `7df41ac`;
  **F2** (spec-section citations, the closure-row owners, and the seventh-occurrence deferral
  belonging in the plan) closed by `563e3ae` and this handoff; **F3** (the movement sentence
  overstated "digest plus wall time") closed by naming the exact moved fields above; **F4** (the
  `IndexError` fail-open behaviour was undocumented) and **F5** (the row docstrings called a direct
  fork child an adopted orphan) closed by `563e3ae`. No finding was rejected. The repair changed
  behaviour in the six shipped scans, so it carried the full rebind and re-measurement chain rather
  than being treated as a narrow documentation fix.
- **Consequence, discharged a second time: the frozen digest chain was rebound again (`762b1d0`).**
  The review repair moved the same three script bytes, so the identical rebind set moved again and
  nothing else. The rebind tool was replayed unchanged against a worktree of the pre-repair commit
  `8e86a22`, where it reproduces the committed chain exactly and reports nothing moved; only then
  was it allowed to write. `EVALUATOR_SOURCE_SHA256` moved with the repair in `563e3ae`, as before.
- **Consequence, discharged: the frozen digest chain was rebound (`bf844f8`).** Three repaired
  scripts are corpus members and declared task artifacts — both adapters and the snapshot helper —
  so each task's `measurement_adapter_runtime`, `snapshot_helper_runtime`, three
  `artifacts[].expected_sha256` entries, and `content_sha256` moved, then
  `corpus-file-set.manifest` (six digest columns), `corpus.json`, `scope.json`, and the
  `prompt-activation-baseline-v1.json` envelope. The rebind uses only the shipped canonical binder
  and the shipped snapshot helper's `canonical_mode`/`digest_file`/`file_expectation_sha256`, and
  asserts that no other field, no membership, no mode, and no path byte moved. This extends
  `1d27b5f`; the snapshot helper is new to this rebind set.
- **Consequence, discharged: `src/prompt_evaluate.align` `EVALUATOR_SOURCE_SHA256`.**
  `scripts/prompt-evaluate.py` is bound by exact digest and executed from those bytes, so the
  repair left `./main prompt evaluate` failing before it could construct any result — exactly the
  `99a6ba7` failure mode, and `prompt-evaluate-smoke` reproduced it. The digest moves in the same
  commit as the repair so that commit is self-consistent.
- **Consequence, discharged: the gate evidence was re-measured**, because the rebind moves every
  digest the checked-in `eval/prompt/gate/` bundle embeds. Result and transcript below.
- **No new Align request.** The whole defect and its repair live in the Python contained-execution
  helpers; nothing here needs a language, compiler/runtime, or standard-library surface Align does
  not ship. `docs/align-requests.md` is unchanged.

## Merged checkpoint: C7-P — aarch64 platform profiles (2026-08-25)

- C7-PERSISTED-RESULT merged as align-llm PR #104 (`a52b9ac`). C7-P was implemented on
  branch `agent/c7p-aarch64-profiles` and merged as align-llm PR #105 (`a4f8663`), the two reviewed
  non-x86 platform profiles that section 11
  of `docs/specs/c7-persisted-result.md` requires before either aarch64 target may provide C7
  evidence. Both are discharged and merged.
- **Settled and implemented: the `aarch64-apple-darwin` profile.** Section 10 of
  `docs/specs/check-gate-topology.md` is the contract. It is deliberately minimal — a process
  boundary plus digest attestation — and explicitly claims no kernel-mediated containment, **no
  `sandbox-exec`**, no fresh compiler, no aggregate membership, and no other target. Trust content
  is the attested identity: managed compiler/runtime digests at the pin, `.align-revision`,
  repository head and cleanliness, Homebrew `llvm`/`openssl@3`/`zstd` identities, the resolved dylib
  digests behind `LIBRARY_PATH`, and host identity including a non-translated `arm64` check.
  `scripts/check-darwin-profile` (behind the `.PHONY` `make darwin-profile-gate`) validates those in
  a fixed order, runs `check`, `build`, a direct `check-per-unit`, `persisted-result-smoke`, and
  `persisted-result-qualification` as bounded children, and emits the identity block itself;
  `scripts/align-toolchain attest compiler` is the toolchain-identity source and reuses `verify()`.
- **Discharged: the `aarch64-unknown-linux-gnu` reuse condition.** Section 9.1's condition ("only
  after this profile's native aarch64 owner passes at the exact C7 head") is met by the
  `Installed Ubuntu 24.04 fresh-image profile (aarch64)` check concluding `success` at the exact C7
  head `e14ba33` (run `32814437108`, job `97699828694`), and the target-local C7 gate then passed
  natively on aarch64 Linux at this branch's head. `docs/specs/c7-persisted-result.md` sections 11.2
  and 11.3 hold both records, including the two emitted attestation blocks.
- **Cadence, deliberately.** Both gates are named focused qualifications — run at a C7 target-local
  owner-boundary change or an explicit audit, not for a pin change alone and not per pull request.
  Neither joins
  `hosted-checks`, `capable-checks`, or `ci`, so `scripts/check-gate-topology`'s `EXPECTED` bytes and
  the topology oracle are untouched and `make gate-topology-check` passes unchanged.
- **The `Makefile` change re-finalized the identity-bound baseline chain.** Adding
  `darwin-profile-gate` changed a recorded baseline artifact. The replacement chain is source
  `9fd3ab64433e526d3af5c647ab933e8bfc365103`, oracle
  `3605b27ccbe1089f5ed2cb06294806a85d247cf1`, and finalization
  `f72e71f077e43d2943f9b9572c4367b9091888c4`; it was appended, never amended, and
  `python3 scripts/check-baseline-chain` reports `baseline chain: PASS` at the branch head on both
  the host and inside the container.
- **New Align request.** `docs/align-requests.md` Request 20 (`PROPOSED`, medium, non-blocking):
  Align CI's `macos-15` matrix leg executes no test binary — the bounded PR test gate is guarded by
  `if: matrix.lint`, and `scripts/test-pr.sh` does not select `m5_owned_json` even there, so
  Request 9's own boundary regressions run only in the ubuntu-only nightly full suite. Request 9's
  contract is target-local, so this asks upstream to run that focused target on the macOS leg.
- **Environment fact for the local preflight on this host, not repository state.** `/usr/bin/make`
  is GNU Make 3.81 and cannot parse this `Makefile` (`Makefile:220: *** multiple target patterns`),
  while the repository requires GNU Make 4.3 or newer. `scripts/pre-pr`'s executable plan invokes a
  bare `make`, so run it with a directory containing a `make` symlink to `gmake` ahead of
  `/usr/bin` on `PATH`. The profile gate itself is unaffected: it resolves `gmake` before `make` and
  rejects anything that does not report GNU Make.
- **Reviewed and repaired.** One fresh comprehensive adversarial review of head `9119549` returned
  request-changes with nine findings (F1-F9); all nine were accepted. The consolidated repair is
  `3e9b27e` — three uncaught-exception paths in `scripts/check-darwin-profile` (empty `--version`
  output, attestation shape drift, a non-ASCII `.align-revision`), the `gmake --version` fall-through
  and the `ALIGN_LLM_FRESH_COMPILER=0` selector, the new failure-path owner
  `scripts/test-check-darwin-profile`, and the specification repairs — followed by the gate
  re-emission commit. `scripts/test-check-darwin-profile` has no Make target, per the
  `scripts/test-align-toolchain` precedent, so the `Makefile` and the identity-bound canonical
  baseline chain are untouched by the repair.
- Published and merged as PR #105 (`a4f8663`) with the sections 11.2/11.3 citations and the
  verification table below.

## Merged checkpoint: C7-PERSISTED-RESULT (2026-08-25)

- C6-MEASURED merged as align-llm PR #103 (`c9a510d`). C7-PERSISTED-RESULT was implemented on
  branch `agent/c7-persisted-result` and merged as align-llm PR #104 (`a52b9ac`), per
  `docs/specs/c7-persisted-result.md`. All three implementation slices are landed — `cb3459b`
  (Request 9 adoption checkpoint), `1d066ff` (product consumer), `1e5797b` (qualification plus lane
  admission) — the lane topology is final for that wave and its identity-bound baseline chain was
  re-finalized on top of it. C7-P then changed the `Makefile` again and re-finalized the chain a
  second time; the current chain is recorded in the active capability above.
- **Landed: the mandatory Request 9 adoption checkpoint.**
  `src/c7_owned_record_source_expiry_adoption.align`,
  `scripts/run-c7-owned-record-source-expiry-adoption`, and the `.PHONY` Make target
  `c7-owned-record-source-expiry-adoption` implement the section 6.1 fixture
  `c7-owned-record-source-expiry-adoption` against the real shipped surface at the unchanged pin
  `2f33ac5c33a898a7894af58322852632ce6ffe42`. It covers section 6.1 source expiry for every
  retained direct field, the three optional-note states, the section 6.3 Move-carrier transfer set,
  the Request 9 normative owned-path golden byte pair, bounded canonical encode at exact fit and
  both rejection rows, and direct `array<string>` cleanup through replacement, move-out, and a
  mid-array recoverable failure. `docs/examples/c7-persisted-result-syntax.align` and
  `docs/examples/c7-persisted-result-lifetime.align` are the section 12.1 checked-in fixtures; the
  runner owns their pinned `alignc fmt` parser-only check together with the normative
  `docs/examples/request9-owned-json-syntax.align`.
- **Landed: the product consumer.** `src/persisted_result.align` implements the section 4 records,
  the section 5 `bounded-bucket-v1` algorithm and the six ordered verifier recomputations, the
  section 6 ownership/lifetime boundary, the section 7 whole-file publication limitation, the
  section 8.1/8.2 precedence tables, and the section 3.1 `persist_file`/`verify_file`/
  `VerificationSummary` surface. `src/main.align` adds the two exact selectors, the section 3.3
  seven-line summary, and the valid-semantic-`FAIL` nonzero exit after publication. Six focused
  `.PHONY` smoke targets (`c7-persisted-result-{cli,lifetime,owned-move,wire,noncanonical-input,
  independent-destinations}-smoke`) and `scripts/c7_persisted_result_fixtures.py` are the bounded
  functional evidence; they join no aggregate, so `gate-topology-check` stays green. The section
  4.4 golden vectors reproduce byte-for-byte end to end: `input_sha256` `6de733d4...`,
  `content_sha256` `a0160d36...`, and the external `result_sha256` `8fb29a72...`.
- **Landed: the qualification slice and the bounded functional owner.**
  `scripts/run-persisted-result-qualification` owns its own independent reference (ordered field
  tables, Request 7 escape grammar, `bounded-bucket-v1`; it imports neither the Align module nor
  `scripts/c7_persisted_result_fixtures.py`), the section 10.2 boundary table, the seed-`20260803`
  corpus of 256 PASS + 32 FAIL differential cases, 38 malformed inputs against both a fresh and an
  existing sentinel destination, 29 artifact mutations including digest-consistent semantic
  mutations, and the temporary `else if raw < upper_bound` -> `<=` source mutation built in a
  private copy of the tree. `scripts/run-persisted-result-smoke` drives the six member runners as
  one bounded functional owner and prints its own cost. Both follow the section 9.4 boundary: the
  Make recipe resolves the compiler and product at the repository root and passes them explicitly.
- **Aggregate admission decision: `persisted-result-smoke` is now a hosted member.** Its measured
  cost is 3.6 s for all six runners at the pinned compiler, so section 12's "small stable
  integration regression" test is satisfied. `Makefile`, `scripts/check-gate-topology` (oracle plus
  self-test literals), and `docs/specs/check-gate-topology.md` (prose plus oracle block) changed
  together, and `docs/specs/c7-persisted-result.md` section 12 records the decision.
  `persisted-result-qualification` (8.7 s plus one whole-program compile) stays outside every
  aggregate by design.
- **The qualification found and repaired one real contract deviation.** Sections 8.1/8.2 row 3 and
  the section 8.3 matrix require `Err(Invalid)` for a malformed document, but the shipped
  `core.json` decoder returns its own `Error.Code(_)`, which `decode_input`/`decode_result`
  propagated unchanged — the CLI exited 1 (`NotFound`-class) instead of 2 (`Invalid`) for every
  malformed input and artifact. Both helpers now apply the section 6.3 typed `map_err`; section 8.1
  states the rule explicitly. A genuinely absent file still maps to the row-2 filesystem error
  (exit 1). Negative control: a temporary rebuild with the mapping reverted fails the qualification
  at `malformed input empty-file: exit 1 != 2`.
- **One measured section 9.4 correction.** The 64 KiB per-stream capture bound is unreachable for
  the mutation build: the pinned compiler writes 105,234 bytes of whole-program advisory warnings to
  stderr, and the exact build vector admits no suppressing option. Section 9.4 now keeps 64 KiB for
  product children and sets 1 MiB for a compiler child, with the same overflow -> terminate,
  kill-if-needed, wait, close -> gate failure behavior.
- **Landed: the wrap-up.** The identity-bound canonical baseline chain is re-finalized against the
  final `Makefile`, and the supervised capable gate is green at the repaired head `36c8568`
  (`fresh worker qualification: PASS (installed profile only)`). That run is the capability's final
  `make ci` evidence and it advanced `docs/align-requests.md` Request 9 to `ALIGN_LLM_VERIFIED`.
  What remains is one fresh comprehensive review and the English pull request with the section 12
  evidence.
- **The first supervised run of the admitted lane member found one real defect (`36c8568`).**
  Admitting `persisted-result-smoke` to `HOSTED_CHECK_TARGETS` put it in the capable aggregate for
  the first time, and that aggregate failed with `fresh compiler: ERROR CHILD aggregate` while the
  check graph itself exited 0. `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1` reported
  `DIAGNOSTIC worker stderr captured=38 shown=38` and no aggregate-child output at all, which is
  what located the fault: the `make` child succeeded and the worker's *post*-aggregate overlay check
  rejected the run, because it admits exactly one workspace-overlay entry, `main`.
  `scripts/run-persisted-result-smoke` built its member-runner environment as an explicit map and
  applied section 9.4's product-child rule to the member runners themselves, dropping every
  sandbox-owned value the aggregate exports — including `PYTHONDONTWRITEBYTECODE=1`. Each member
  runner does `import c7_persisted_result_fixtures`, so CPython wrote `scripts/__pycache__/` into
  the workspace overlay and the gate failed on the second entry. The owner now forwards `HOME`,
  `TMPDIR`, `PYTHONHOME`, `PYTHONNOUSERSITE`, and `PYTHONDONTWRITEBYTECODE` when the caller supplies
  them, and section 9.4 records the rule. This is the same root-cause class as `3768ad8`: a child
  launcher rebuilding the environment from fixed literals instead of the aggregate's own values.
  Class audit: `run-persisted-result-qualification` launches only the product and the compiler — no
  `bash`/`python3` child, no import, no workspace write — and stays outside every aggregate, so it
  has no instance of the defect and is unchanged.
- **The section 4.4 golden vectors reproduce exactly.** The decoded C7 input re-encodes
  byte-for-byte to the section 4.4 `input bytes` line, and the Request 9 `OwnedTask` pair
  reproduces its canonical output including `u64::MAX`, embedded NUL, and multibyte text. The
  section 4.4 `input_sha256`, `content_sha256`, and external `result_sha256` values were
  independently recomputed from the document's own literal bytes and match. No Align gap was found;
  no new `docs/align-requests.md` entry is required by this checkpoint.
- **Resolved: the identity-bound canonical baseline chain is re-finalized.** Admitting
  `persisted-result-smoke` to `HOSTED_CHECK_TARGETS` changed `Makefile`, which
  `docs/specs/check-gate-topology.md` records as a baseline artifact, so the previous chain went red
  with `working-tree Makefile differs from the baseline source commit`. The replacement chain is
  source `1e5797b3b451c79a48bd28f78edbd47b8540f9ec`, oracle
  `32e1442a5470f6c25862e290b6c2495ee8c2df0b`, and finalization
  `2fe903625816bd4738293e94497f88d43c42b5d9`; it was appended, never amended, and
  `python3 scripts/check-baseline-chain` reports `baseline chain: PASS` at the final head.
  `make gate-topology-check` is green at the admitted lane state.
- **Platform-profile verdict, now superseded by C7-P.** Section 11 and section 12.1 make
  `aarch64-unknown-linux-gnu` and `aarch64-apple-darwin` *required* C7 acceptance environments, and
  during that wave neither had a reviewed profile, so every run on this macOS host was development
  evidence only. C7-P delivered both profiles and recorded their discharge in sections 11.2 and
  11.3, so a host reproducing the recorded identities now produces C7 acceptance evidence rather
  than development evidence. The x86_64 Section 9 profile still substitutes for neither target.

## Merged checkpoint: C6-MEASURED (2026-08-25)

- C6-MEASURED (C6e/C6g1/C6g2) was implemented on branch `agent/c6-measured` and merged as
  align-llm PR #103 (`c9a510d`). One comprehensive adversarial review returned request-changes at
  `535be1087622dfd05481503d5f5d933555c06953`; every finding was accepted and repaired, and the
  consolidated repair is `baf8c24` (validator bindings, adapter deadline and redaction order),
  `3ca42d8` (claim narrowing and lane/post-freeze records), `1d27b5f` (frozen-chain rebind),
  `99a6ba7` (Align evaluator wrapper digest), `c737adc` (a second credential-code expectation),
  `e935790` (regenerated gate evidence), and `e14c472` (measurement record). The measured gate is
  real and green at the repaired head: `make prompt-gate-check` with all five explicit `C6_GATE_*`
  values exits 0 (`prompt gate validator: PASS`) against the regenerated `eval/prompt/gate/` bundle.
- **Resolved: the supervised fresh-worker `make ci` passes.** At head
  `3768ad8af68bb50ee3129ff392f6ba86ac89e071`,
  `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker
  --align-repo <path-to-sibling-align-checkout>` exits 0 with `fresh worker qualification: PASS
  (installed profile only)`. The blocker had two independent causes, both C6-MEASURED lane
  additions that the supervised aggregate had never exercised — its last green run predates them —
  so both were pre-existing wave gaps rather than review-repair regressions.
- **Cause 1, removed: resource pressure from `prompt-verifier-smoke`.** A high-fidelity
  reproduction of the exact aggregate environment ran `make capable-checks` to `exit=0` in 890 s
  with a clean workspace-upper (only `./main`), of which roughly 780 s was that one smoke. The
  pinned compiler needs about 720 s and a 1,525,732 KiB peak resident set to code-generate
  `src/prompt_verifier_smoke.align`, against 0.494 s for `alignc check` of the same unit. The
  member was demoted to a named focused qualification (see the lane entry below), and the aggregate
  cost came back inside its historical band.
- **Cause 2, removed: `prompt-measurement-adapter-smoke` could not find `git`.** Its patch row
  builds a pinned checkout and runs `git apply` over the adapter's synthesized bytes, and it
  launched that fixture with a hard-coded child `PATH=/usr/bin:/bin` plus a bare `git` argv. Python
  resolves a bare program name against the *child* environment's PATH, and the fresh aggregate puts
  only its staged tool root on PATH, so the row died with
  `prompt measurement adapter: FAIL: [Errno 2] No such file or directory: 'git'` and took
  `capable-checks` down with `make[1]: *** [Makefile:129: prompt-measurement-adapter-smoke] Error 1`.
  `3768ad8` resolves that fixture PATH from `ALIGN_LLM_TOOL_ROOT`, exactly as
  `scripts/check-baseline-chain` already does, with the previous fixed host directories as the
  default. The whole class was audited across the aggregate's goal list: every other bare-name child
  launch in the lane either inherits the aggregate environment or already derives its PATH from the
  tool root, and the remaining hard-coded `/usr/bin:/bin` occurrences launch absolute paths the
  aggregate provides.
- **The aggregate diagnostic seam is now reachable end to end (`e4c7e45`).** One optional entry,
  `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1`, is forwarded — never synthesized — across every launch
  boundary that previously rebuilt the environment from fixed literals: `fresh-supervise.c` beside
  its five-variable allowlist, `fresh-bootstrap.c` beside its five fixed entries,
  `fresh_image_control.py`'s bootstrap and worker environments, and the worker's
  `EXPECTED_ENVIRONMENT` admission via `environment_admitted()`. On failure the worker emits the
  bounded tail of the aggregate child's streams and the controller emits the bounded tail of the
  worker's stderr, both before the canonical `fresh compiler: ERROR <category> <phase>` line and
  both capped at 8,192 bytes. With the entry absent every environment, stream, status, and byte of
  output is exactly what it was before. This is what named cause 2: the diagnostic run printed the
  failing target and its error verbatim. `run-fresh-image-control-smoke` and
  `run-fresh-worker-unit-smoke` pin both halves, and
  `docs/specs/check-gate-topology.md` records the contract. Use it by exporting the variable before
  the qualification; it costs one extra qualification run and nothing else.
  `run-fresh-worker-qualification` forwards it only to the installed-profile owner
  (`run-fresh-image-profile-smoke`), the one phase that reaches the worker aggregate; the focused
  owners keep their unchanged qualified environments.
- Slice E landed the final integration wiring. The section 11.3 owner targets are now
  `HOSTED_CHECK_TARGETS` members — `prompt-seed-attestation-smoke`, `prompt-experiment-smoke`,
  `prompt-generate-smoke`, `prompt-measurement-adapter-smoke`, `prompt-credential-lifetime-smoke`,
  the nine `prompt-gate-*-smoke` fixtures, and `c6e-request2-adoption` — and
  `scripts/check-gate-topology`'s literal `EXPECTED` lane bytes were refreshed in the same commit
  `6f937fb4bb4a596afd0540b5b37415d65d5dbb3c`, per the section 11.1 precedent.
- `prompt-gate-check` is the C6-MEASURED gate target. It takes the five explicit `C6_GATE_*`
  command-line values, fails closed before the validator starts when any is missing or empty, and
  maps them to `--source-bundle-root`, `--python-executable-path`, `--git-executable-path`,
  `--generation-child-path`, and `--generation-child-sha256`. The declared interpreter is also the
  launcher, so the target never reaches the validator through an ambient Python or Git.
- **Closed: the gate is a named capable qualification.** `prompt-gate-check` stays out of
  `CAPABLE_ONLY_CHECK_TARGETS`. Section 9 and section 11.3 of
  `docs/specs/c6-prompt-context-optimizer.md` previously required the gate to run as
  `make ci C6_GATE_...=...`, but the settled FRESH-WORKER caller contract in
  `docs/specs/check-gate-topology.md` admits exactly `make --no-print-directory ci` **with no
  variable assignments**, and the worker runs the `capable-checks` graph inside bwrap under a
  cleared, fixed environment, so the five explicit values cannot cross that boundary. Both sections
  now name `make prompt-gate-check` with the five explicit `C6_GATE_*` values as the measured
  gate's named capable qualification — a focused qualification the supervised aggregate does not
  reach — leaving the FRESH-WORKER contract and the `make ci` goals unchanged.
- The Makefile change invalidated the identity-bound canonical baseline chain, which requires the
  working-tree `Makefile` to equal its source commit's blob. The chain was already red at
  `19c5d5c` because earlier C6-MEASURED commits changed the Makefile without re-finalizing. The
  replacement chain is source `6f937fb4bb4a596afd0540b5b37415d65d5dbb3c`, oracle
  `182fa3c9a537884f59cf9257d91c884d3732d1ca`, and finalization
  `7273f65bfc1a2604daf37b2bd7748a46d2bd59f2`; it was appended, not rewritten. Adding
  `prompt-render-parity-smoke` to the lane changed the `Makefile` again, so the next chain was
  source `ba47abdb01776d10f041c0d3e3f36edc67034993`, oracle
  `656a5bf9609762b899c4e841de7529bfde2ec5c2`, and finalization
  `8ddea8a03b817404e68a23e8ce1f39534b7abd13`; it was appended the same way. Removing
  `prompt-verifier-smoke` from the lane changed the `Makefile` once more, so the **current** chain
  is source `ebcc8d5c384c9a6c30619637018c7c9d07270192`, oracle
  `f5158d5741bc912dbc0324f5138eb7e8c216a6dd`, and finalization
  `55282a8` — appended, never amended — recorded on native Linux `aarch64` in the privileged
  `c6g2-measure:latest` container with `bubblewrap` installed, non-root, `umask 022`,
  `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of the source commit. Both deterministic-reference
  samples pass: 134,471,000-140,342,375 ns, median 137,406,687 ns.
  `scripts/check-baseline-chain` passes on it.
- **`prompt-verifier-smoke` is no longer a hosted-lane member.** It stays a `.PHONY` public target
  and the direct C6c2 owner with unchanged coverage, and is now a **named focused qualification**
  owned by the section 10 verifier boundary in `src/prompt_score.align`: run
  `make prompt-verifier-smoke` when that boundary changes and before publishing such a change. It
  is not reached by `hosted-checks`, `capable-checks`, or `ci`. The same change refreshed the
  `Makefile` list, `scripts/check-gate-topology`'s `EXPECTED` bytes and `exact_environment()`
  self-test copy, the `docs/specs/check-gate-topology.md` `hosted=` oracle and prose, section 11.3
  of `docs/specs/c6-prompt-context-optimizer.md`, and the baseline chain. The compiler-side gap is
  recorded as `docs/align-requests.md` Request 19 (`PROPOSED`, non-blocking); the member rejoins the
  lane when it closes.
- **Closed: `prompt-render-parity-smoke` is no longer an orphan.** It is now a
  `HOSTED_CHECK_TARGETS` member beside `prompt-model-smoke`, section 11.3 names it as the
  renderer-parity owner, and the same change refreshed the `EXPECTED` lane bytes, the
  `exact_environment()` self-test copy, and the baseline chain.
- `c6f2-request14-adoption` is timing-flaky on a fast, quiet host. Its publication-race fixtures poll
  for a staged temporary file inside a five-second window; when the fixture binary completes before
  the poll observes staging, the run reports "publication race did not reach evidence staging" or
  "result-only cleanup fixture did not reach staging". It passed on retry in the final capable gate
  and it is a pre-existing C6-EVALUATION owner, not a Slice E regression, but the fixture needs a
  deterministic seam rather than a poll.
- The frozen `eval/prompt/canonical-v1/` scope now names a real provider: `LOCAL_OPENAI` on
  `http://127.0.0.1:18080/v1/chat/completions`, model `qwen2.5-coder-7b-instruct-q4_k_m`,
  `api_key_env: null`. `provider_service_revision` carries llama.cpp `b10610` /
  `a14dba686aaafba3a2d6b5eb8820b0df5c5d2d92`, the `llama-server` digest, and the model digest.
- Measured result (`c6g2-measure`): `IMPROVED`, `gate_eligible: true`, zero serious regressions,
  completion gain 2. `duration-half-away-from-zero` moves 0/2 -> 2/2 under a model-proposed
  candidate that enables the context sections; the other two tasks fail in both variants.
  `paired_pass_count` is 0 for every task and for the corpus, so the evidence carries **no** paired
  timing and therefore no time-to-passing-patch comparison; acceptance is the section 8
  completion-gain path alone. Section 11.3's "What the measured claim is and is not" states the
  narrowed claim.
- Reproducible baseline: the parent-vs-parent null replicate `c6g2-replicate`, same frozen corpus,
  same command and provider environment, distinct variant identifiers over a byte-identical rendered
  prompt. Result `NO_IMPROVEMENT`, `gate_eligible: false`, every task 0/2 in both variants, corpus
  `completion_gain_count: 0` — it flipped no cell. Reproducing command, inside the privileged
  `c6g2-measure:latest` container at project root `/work/align-llm`:

  ```text
  ./main prompt evaluate run/evaluate-request-replicate.json run/result-replicate.json
  ```

  The request is built by the replicate driver, which copies the parent effective variant into the
  candidate slot under `c6g2-replicate/variant` and `c6g2-replicate/candidate` and otherwise reuses
  the measure request verbatim. At the review-repaired measuring commit
  `c737adcf905cb4662472bc86e8345bbcd9bc1346` the replicate result digest (SHA-256 of the exact
  `run/result-replicate.json` bytes) is
  `b1d68148c5bfc3e86c2a022620d10dc95a79b3f685da8a5ceca4d1341898420d`, its evidence sidecar is
  `c2854e7546e9b31b03f99337ee935f07e99efe7dbbe7aea8aa72c28bc0b69f03`, and wall time is 444.1 s. The
  superseded pre-repair replicate at `6da28d88327797649bbf229f14be9be1e6dd2d96` was
  `e111201e8096ac5a64fb7c5522c0dae2c3b70f81645c4cffe8a5afb85c790eca` with sidecar
  `0aafe8d62e9622c02b5d3baaaa94faf07084daa1bcd14e234235f5c8225a07c5` and wall time 520.2 s, and
  reported the same null result. The replicate artifacts are diagnostics, not repository state, and
  are not checked in.
- The gate run found and repaired five shipped defects no fixture reaches: three canonical
  `Option::None`-omission mismatches (experiment-result decode, aggregate optional set, and the
  activation-lineage identity the gate validator compared against the envelope instead of the
  nested activation), a stale `c6-prompt-state` fixture that left `prompt-state-smoke` red on the
  hosted lane at `52aefeb` and `19c6bed`, an overlapping automatic snapshot path set, and a 2 MiB
  sealed-input cap that could never admit the derived generation child. Repairing the measurement
  adapter rebound the frozen digest chain; only digest bindings moved.
- Next actions, in order: (1) publish the C6-MEASURED pull request with the narrowed measured
  claim, the per-cell matrix, the validator transcript, the named-qualification status of
  `prompt-gate-check`, and the green supervised fresh-worker qualification recorded above — the
  earlier `capable-checks` aggregate blocker is resolved, so `make ci` evidence is available;
  (2) after merge, start `C7-PersistedResult` (`docs/specs/roadmap.md` §C7), the owned-result
  verification consumer that adopts Request 9's owned-JSON surface from the current pin.
- The measurement environment is a privileged `linux/arm64` container (`c6g2-measure:latest`) with
  `bubblewrap` installed at run time; the image does not ship it and the validation runner requires
  it. Docker's default seccomp/AppArmor blocks the runner's user namespaces, so the container needs
  `--privileged`. Both are environment facts, not repository state.
- C6-EVALUATION merged as align-llm PR #100
  (`282062bf00416f5e0df678b8bd885709084b4e16`); its final capable integration gate passed at head
  `049172f5be57002c2426f012fe23038f570f5069` in pull-request CI run 32490981785, including both
  installed native profiles; main push run 32493880784 reused that exact evidence on the merge
  commit. `.align-revision` remains pinned to Align
  merge `19c3db144c462bf7d6784f88d64cc124229b7ec2` at that time; C6-MEASURED then bumped it to
  Align merge `2f33ac5c33a898a7894af58322852632ce6ffe42` in commit `f344ea9`, which is the pin every
  Slice E result below was produced against.
- Align-llm PR #94 merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`, with the C6a1/C6a2
  graph-and-codec capability pinned to Align merge `a440970ac81118ed2169f600b2b3c06fcb9cde7`.
- The register records Requests 2, 7, 8, and 10–18 as `ALIGN_LLM_VERIFIED`; the merged C6-EVALUATION
  gate advanced Requests 11 and 14, and C6-MEASURED Slice E advanced Request 2 once
  `c6e-request2-adoption` and the wave's final capable gate both passed. Request 9 advanced to
  `ALIGN_LLM_VERIFIED` in the merged C7-PERSISTED-RESULT wave at the unchanged pin. C6-MEASURED
  added Request 19, a compiler code-generation performance gap, and C7-P added Request 20, the
  missing macOS leg for Request 9's own `m5_owned_json` boundary regressions in Align CI; those two
  are the register's only `PROPOSED` entries and neither blocks. Every other open Align request has
  a merged Align-side surface, and none is `ACCEPTED` or `IMPLEMENTING`.
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

- **ADAPTER-ZOMBIE review-repaired C6g2 gate, green (native Linux `aarch64`, 2026-08-25).** This is
  the current evidence and supersedes the `b336017` block below. Measured at the rebind head
  `762b1d0f068a10774ff976b1889ddacf483321a5`; the evidence is committed as `6537482`. Same
  environment as both earlier runs: the privileged `c6g2-measure:latest` container with `--init`,
  `bubblewrap` installed at run time, a non-root uid, `umask 022`, `PYTHONDONTWRITEBYTECODE=1`, the
  model copied onto the container filesystem, and `LOCAL_OPENAI` on a co-located `llama-server` at
  `http://127.0.0.1:18080/v1/chat/completions`, model `qwen2.5-coder-7b-instruct-q4_k_m`. The served
  build and weights match the frozen `provider_service_revision` exactly: llama.cpp `b10610` /
  `a14dba686aaafba3a2d6b5eb8820b0df5c5d2d92`, `llama-server`
  `e3905073c4322ff33c7b365c9ea10aadbc776fe3eab372869694555d8f5693a8`, model
  `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c`. The server ran
  `--parallel 1 -c 16384` on 8 threads over the 8 logical CPUs the environment probe records, and
  every prompt reported `truncated = 0`. Generation child built in run:
  `6650e4486ec8b205604e6348cd9dd81f7370b478a7ed1cf7607ce7aa94ff2aba`.
  - **Measure (`c6g2-measure`), 595.0 s: `IMPROVED`, `gate_eligible: true`,
    `serious_regression_reasons: []`, corpus `completion_gain_count: 2`.**
    `duration-half-away-from-zero` 0/2 parent to 2/2 candidate; `layer-precedence-frozen-module`
    and `record-codec-round-trip` fail in both variants. `paired_pass_count` is 0 for every task
    and for the corpus, so this evidence still carries **no paired timing and no
    time-to-passing-patch comparison**; acceptance is the section 8 completion-gain path alone.
    Result `content_sha256`
    `0d8668053654d3f7fef3bcd5b2966dcaaf966315432ec4e9245b4ecb25346267`, evidence sidecar
    `bc7ed85a647a0098fb4812c69adbeb0e87132fc9704d8746bc880db9efd862aa`. Accept then rollback
    reproduce as `ACCEPTED` (`00b3cf42…`) and `ROLLED_BACK` (`cf881026…`). All three source
    reachabilities are `VERIFIED`.
  - **Reproducible baseline, the parent-vs-parent null replicate (`c6g2-replicate`), 493.0 s:**
    `NO_IMPROVEMENT`, `gate_eligible: false`, every task 0/2 in both variants, corpus
    `completion_gain_count: 0` — it flipped no cell. Result digest (SHA-256 of the exact
    `run/result-replicate.json` bytes)
    `dcd4e994f1a44c59a4e0ac96644d8adce0023b86f8e870dd2f7794f08cacd359`, evidence sidecar
    `0b77c94b70d9eae285a24aaca718401d9211c8a6ed2dc03c2c606b8a73867c03`. Same reproducing command as
    below. The replicate artifacts are diagnostics, not repository state, and are not checked in.
  - **The comparison with the superseded evidence is tighter than the previous one: no measurement
    field moved at all.** Movement is confined to digests and runtime identities, to
    `artifact_digests[].byte_count` for the three rebound scripts, and to wall-clock `*_ns` timings
    with the test-duration text they print into `diagnostic_stderr`. Every verdict-bearing cell is
    identical — `status`, `gate_eligible`, `serious_regression_reasons`, every `task_aggregates`
    entry, the whole `corpus_aggregate`, and every row's `measurement.status`. The candidate variant
    is provably the same one: its `content_sha256` `78611fbc…` is byte-identical to the variant both
    earlier measurements consumed. Only the experiment artifact's own frozen-chain references — the
    parent-activation digest and its embedded scope — were rebound with the corpus, giving artifact
    digest `435a34b9…` in place of `01b04b76…`.
  - **Three reproduction preconditions, recorded because rebuilding the lost drivers hit all
    three.** The measurement drivers are diagnostics and were never checked in, so they were
    reconstructed from the embedded copies in the checked-in evidence. (1) `observe_git` requires an
    empty `git status --porcelain=v1 -z --untracked-files=all` in **both** the align-llm and the
    Align repository. The run's own `run/` outputs are untracked and `run/` is not in `.gitignore`,
    so the working clone needs `run/` in `.git/info/exclude` (local, uncommitted). (2) The Align
    checkout must be owned by the running uid, because a root-owned checkout trips git's
    dubious-ownership guard. Either of those degrades the affected reachability to `UNVERIFIED`,
    which silently drops `gate_eligible` to false while still reporting `IMPROVED` with identical
    aggregates — the first attempt produced exactly that and was discarded. (3) The evaluate
    request's `verifier_source_policy_path` must name the **same** `PROMPT_SOURCE_VERIFIER_POLICY`
    document the gate bundle carries, `policy_id: prompt-v1-gate-source-policy-v1`; a
    differently-named policy over identical helper bytes produces a different digest and the
    validator rejects the evidence with `evaluation environment source_verifier_policy_sha256
    disagrees with the gate locator`. That policy id was recovered by solving the previous
    locator's recorded digest against the known helper, interpreter, and Git digests. Only the run
    that satisfies all three is checked in.
- **Superseded: ADAPTER-ZOMBIE re-measured C6g2 gate (native Linux `aarch64`, 2026-08-25).** Kept
  as history; the block above is the current evidence. Measured at
  the rebind head `bf844f821a45464e67ed30eafe025c31dfb2c4e5`; the evidence was committed as
  `b336017`. Environment identical to the superseded run: the privileged `c6g2-measure:latest`
  container with `--init`, `bubblewrap` installed at run time, a non-root uid, `umask 022`,
  `PYTHONDONTWRITEBYTECODE=1`, the model copied onto the container filesystem, and `LOCAL_OPENAI`
  on a co-located `llama-server` at `http://127.0.0.1:18080/v1/chat/completions`, model
  `qwen2.5-coder-7b-instruct-q4_k_m`. Generation child built in run:
  `903f38004ac3c935b0ca41c70f94f77b274bdb84adebe3873a1aec70be59bf72`.
  - **Measure (`c6g2-measure`), 685.2 s: `IMPROVED`, `gate_eligible: true`,
    `serious_regression_reasons: []`, corpus `completion_gain_count: 2`.**
    `duration-half-away-from-zero` 0/2 parent to 2/2 candidate; `layer-precedence-frozen-module`
    and `record-codec-round-trip` fail in both variants. `paired_pass_count` is 0 for every task
    and for the corpus, so this evidence still carries **no paired timing and no
    time-to-passing-patch comparison**; acceptance is the section 8 completion-gain path alone.
    Result digest `1b2164dc8acebf25ae815e87d9aa9b3b9fb25be99917b57658b6462fb1a281cc`, evidence
    sidecar `7c2d48b571377f20918dc2a8d0ce6d68372c2ca440a10bd997009b3f2e8a9f80`. Accept then
    rollback reproduce as `ACCEPTED` and `ROLLED_BACK`.
  - **Reproducible baseline, the parent-vs-parent null replicate (`c6g2-replicate`), 637.6 s:**
    `NO_IMPROVEMENT`, `gate_eligible: false`, every task 0/2 in both variants, corpus
    `completion_gain_count: 0` — it flipped no cell. Result digest
    `56a4f367b054db8471500bb61921e169270b36bc5e7d54ed608eb7272d05c87a`. Reproducing command, in
    the same container at project root `/work/align-llm`:

    ```text
    ./main prompt evaluate run/evaluate-request-replicate.json run/result-replicate.json
    ```

    The replicate artifacts are diagnostics, not repository state, and are not checked in.
  - **The comparison with the superseded evidence is cell for cell identical.** Same verdicts, same
    per-task pass counts, same `completion_gain_count: 2`, same empty serious-regression array,
    same all-zero `paired_pass_count`, and the same null replicate verdict. The candidate variant
    is provably the same one: its `content_sha256` `78611fbc…` is byte-identical to the variant the
    superseded measurement consumed, taken from the checked-in evaluation. Only the experiment
    artifact's own frozen-chain references — the parent-activation digest and its embedded scope —
    were rebound with the corpus, giving artifact digest `01b04b76…` in place of `4dfe5fe7…`.
    **Correction (review finding F3): "everything that moved is a digest plus wall time" was
    wrong.** Besides digests, runtime identities, `align_llm_commit` and timings, two measurement
    fields moved on the `record-codec-round-trip` **parent** row, sample 1 (`rows[8]`, not a
    candidate row): `patch_size_bytes` went 1036 to 1008, and `diagnostic_summary`'s applied-edit
    list went from `src/encode.py` to `src/decode.py, src/encode.py`. Every snapshot's
    `artifact_digests[].byte_count` also moved for the three rebound scripts, since their bytes are
    what the rebind was for. Both variants fail `record-codec-round-trip`, so no verdict-bearing
    cell moved: the verdict-bearing cells were and remain identical.
- **ADAPTER-ZOMBIE review-repair owner verification (2026-08-25).** At the evidence head `6537482`,
  with the working tree carrying only this documentation change. Linux rows ran in the privileged
  `c6g2-measure:latest` image with `bubblewrap` installed at run time, non-root with `umask 022` and
  `PYTHONDONTWRITEBYTECODE=1`; the repaired scans are Linux-only, so all three helper owners fail on
  Darwin for that reason at the base commit too.
  - Repaired-file owners, all **PASS**: `test-prompt-fixed-adapter`, `test-prompt-snapshot-helper`,
    `test-prompt-source-verifier`, `run-prompt-measurement-adapter-smoke` (**74** rows, up from 73),
    `run-prompt-evaluate-smoke`, and all nine `prompt-gate-*` families.
  - Regression neighbours, all **PASS**: `prompt-experiment-smoke`, `prompt-seed-attestation-smoke`,
    `prompt-generate-smoke`, `prompt-credential-lifetime-smoke`, `prompt-render-parity-smoke`
    (58 vectors byte-equal), `prompt-state-smoke`.
  - Host (macOS, managed pinned toolchain), all **PASS**: `gmake check` (23 units per-unit),
    `gmake format-check`, `gmake gate-topology-check` (`check gate topology: PASS`; no lane member
    changed), `gmake provider-smoke`, `gmake persisted-result-smoke`, `git diff --check`, and
    `python3 scripts/check-baseline-chain` (`baseline chain: PASS` — the `Makefile` is untouched, so
    the identity-bound chain stands).
  - **The new row is a negative control in all six files.** With the `Threads:` discriminator
    removed in one scan at a time — `return state == "Z"` in place of
    `return state == "Z" and tasks == 1` — each owner fails with `a zombie leader with a live worker
    thread was not reported as a live descendant` (the measurement adapter reports the same message
    under its `zombie-leader-descendant` label). The evaluator's control also rebinds
    `EVALUATOR_SOURCE_SHA256` for the mutated bytes, so it fails on the row and not on the digest
    gate. In every control the terminated-zombie row and the live-descendant row still pass, so the
    control isolates the discriminator and not the containment guarantee.
- **ADAPTER-ZOMBIE review-repaired gate qualification, green, at head
  `65374827f4fc901ead4e777b680ce8692d5805e8`.** Same container, clean clone (`dirty=0`), bundle
  built from a clean align-llm mirror at that head plus a clean Align checkout at
  `2f33ac5c33a898a7894af58322852632ce6ffe42` (`dirty=0`). The generation child rebuilt in run
  reproduced the locator's frozen digest
  `6650e4486ec8b205604e6348cd9dd81f7370b478a7ed1cf7607ce7aa94ff2aba` exactly. Both forms pass:

  ```text
  /usr/bin/python3.12 scripts/prompt-gate-validator.py \
    --source-bundle-root /tmp/bundle \
    --python-executable-path /usr/bin/python3.12 \
    --git-executable-path /usr/bin/git \
    --generation-child-path /tmp/bundle/align-llm/main \
    --generation-child-sha256 6650e4486ec8b205604e6348cd9dd81f7370b478a7ed1cf7607ce7aa94ff2aba
  -> prompt gate validator: PASS (exit 0)

  make prompt-gate-check C6_GATE_SOURCE_BUNDLE_ROOT=/tmp/bundle \
    C6_GATE_PYTHON_EXECUTABLE_PATH=/usr/bin/python3.12 \
    C6_GATE_GIT_EXECUTABLE_PATH=/usr/bin/git \
    C6_GATE_GENERATION_CHILD_PATH=/tmp/bundle/align-llm/main \
    C6_GATE_GENERATION_CHILD_SHA256=6650e448...94ff2aba
  -> prompt gate validator: PASS (exit 0)
  ```

  The bundle holds `align-llm/`, `align/`, `scripts/prompt-source-verifier.py` at mode 0644, and the
  `prompt-v1-gate-source-policy-v1` policy document — the same one the evaluate request consumed.
- **Publication preflight, both fresh legs, and the supervised installed profile run at the exact
  publication head and are recorded in the pull request**, not here: a `pre-pr` stamp belongs to an
  unchanged `HEAD`, so it cannot be committed into the head it certifies. This branch changes
  `src/*` and `eval/*`, so the wave classifies `fresh-image` and both compensating legs are re-run
  rather than argued from a head delta.
- **Superseded: ADAPTER-ZOMBIE gate qualification, green, at head
  `b3360171e965568af59aabaec14f89c6b5b60602`.** Same container, clean clone, bundle built from a
  clean align-llm mirror at that head (`dirty=0`) plus a clean Align checkout at
  `2f33ac5c33a898a7894af58322852632ce6ffe42` (`dirty=0`). The generation child rebuilt in run
  reproduced the locator's frozen digest exactly. Both forms pass:

  ```text
  /usr/bin/python3.12 scripts/prompt-gate-validator.py \
    --source-bundle-root /work/bundle \
    --python-executable-path /usr/bin/python3.12 \
    --git-executable-path /usr/bin/git \
    --generation-child-path /work/align-llm/main \
    --generation-child-sha256 903f38004ac3c935b0ca41c70f94f77b274bdb84adebe3873a1aec70be59bf72
  -> prompt gate validator: PASS (exit 0)

  make prompt-gate-check C6_GATE_SOURCE_BUNDLE_ROOT=/work/bundle \
    C6_GATE_PYTHON_EXECUTABLE_PATH=/usr/bin/python3.12 \
    C6_GATE_GIT_EXECUTABLE_PATH=/usr/bin/git \
    C6_GATE_GENERATION_CHILD_PATH=/work/align-llm/main \
    C6_GATE_GENERATION_CHILD_SHA256=903f3800...be59bf72
  -> prompt gate validator: PASS (exit 0)
  ```

  The same qualification was re-run unchanged at the documentation head
  `fd44514212c9989c5c60db1432822fb216f96018` and again after it, each time rebuilding the
  generation child in run to the same digest and each time reporting `prompt gate validator: PASS`.
  Every commit after `b336017` is Markdown only, so no input the validator, the preflight, or
  either fresh leg consumes has moved.

- **ADAPTER-ZOMBIE owner verification (2026-08-25).** Linux rows ran in a privileged
  `python:3.12-bookworm`-derived container with `bubblewrap`, and the Align-dependent rows in the
  `c6g2-measure:latest` image at the pinned compiler; the repaired scans are Linux-only, and all
  three helper owners already fail on Darwin for that reason at the base commit.
  - Repaired-file owners, all **PASS**: `test-prompt-fixed-adapter`,
    `test-prompt-snapshot-helper`, `test-prompt-source-verifier`,
    `run-prompt-measurement-adapter-smoke` (73 rows), `run-prompt-evaluate-smoke`, and all nine
    `prompt-gate-*` families.
  - Regression neighbours, all **PASS**: `prompt-experiment-smoke`,
    `prompt-seed-attestation-smoke`, `prompt-generate-smoke`,
    `prompt-credential-lifetime-smoke`, `prompt-render-parity-smoke`, `prompt-state-smoke`.
  - Host (macOS, managed pinned toolchain), all **PASS**: `gmake check` (23 units per-unit),
    `gmake format-check`, `gmake gate-topology-check` (`check gate topology: PASS`; no lane member
    changed), `gmake provider-smoke`, `gmake persisted-result-smoke`, `git diff --check`, and
    `python3 scripts/check-baseline-chain` (`baseline chain: PASS` — the `Makefile` is untouched,
    so the identity-bound chain stands).
  - **Every regression has a recorded negative control.** With the repair reverted in that one
    file, each owner fails on its new row: the four `owned_descendant_ids` unit rows report `an
    adopted zombie was counted as a live descendant`; `test-prompt-fixed-adapter`'s contained
    runner reports `an adopted zombie descendant was reported as a containment failure`;
    `prompt-measurement-adapter-smoke`'s generation-child row reproduces the exact PR #103
    diagnostic `generation child left a descendant` with `failure_kind: CONTAINMENT`; and
    `prompt-evaluate-smoke` reports `an adopted zombie was treated as an escaped descendant:
    PROCESS`. In every negative control the live-descendant row still passes, so the controls
    isolate the zombie classification and not the containment guarantee.
- **ADAPTER-ZOMBIE publication preflight and supervised gate, at the final head
  `fd44514212c9989c5c60db1432822fb216f96018` (2026-08-25).** `python3 scripts/pre-pr --owner-test
  descendant-scan -- <the repaired-file owners in a privileged Linux container>` classified the
  wave `fresh-image`, because `eval/*` changed. Phases: `descendant-scan` 18,359 ms **PASS**,
  `managed-align-ensure` 276 ms **PASS**, `pinned-align-build` 100 ms **PASS**, `hosted-checks`
  49,531 ms **PASS**. Its `fresh-focused` leg **cannot run on Darwin**:
  `scripts/run-fresh-source-identity-smoke` reads `/proc/self/fd`, and the identical failure
  reproduces on a clean clone of the base commit `a4f8663`, so it is a pre-existing host
  limitation rather than a wave regression — the same `N/A` reason C7-P recorded. Both fresh legs
  were therefore run where they belong.
  - **Focused leg, native Linux `aarch64`** in the privileged `c6g2-measure:latest` container with
    `--init`, `bubblewrap`, `clang`, and `unzip`, non-root with `umask 022` and
    `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of the exact head:
    `python3 scripts/run-fresh-worker-qualification` **PASS**, exit 0 (focused; installed profile
    deferred).
  - **Installed profile, host Docker:** `python3 scripts/run-fresh-worker-qualification
    --installed-profile-only --require-docker`: **PASS**, `fresh image profile smoke: PASS` then
    `fresh worker qualification: PASS (installed profile only)`. Phases: `docker-daemon` 618 ms,
    `image-build` 22,731 ms, `image-attestation` 3,544 ms, `profile-lifecycle` 2,397 ms,
    `profile-self-test` 15,437 ms, `trust-mutations` 12,301 ms, `runtime-replacements` 21,955 ms,
    `boundary-profile` 302,596 ms, **`worker-aggregate` pass after 365,588 ms**, `cleanup`
    1,313 ms; whole installed profile 749,127 ms. Run with the default environment and no
    diagnostic opt-in. **That is this capability's `make ci` evidence.**
- **C7-P Darwin platform-profile gate, green, re-emitted at the review-repaired head
  `3e9b27e9af04d4eae616dffb812c8db926d938d8` (macOS `aarch64-apple-darwin`, 2026-08-25).** The
  repair changed the gate's own owner, which section 10.4 names as a re-run trigger, so the
  section 11.3 record is the block from this run, not the superseded `41b2f43` one.
  `LIBRARY_PATH="$(brew --prefix)/lib:$(brew --prefix openssl@3)/lib:$(brew --prefix zstd)/lib"
  make darwin-profile-gate`: **PASS**. Five acceptance commands, all exit 0 — `gmake check`
  1,266 ms, `gmake build` 276 ms, direct `alignc check-per-unit src/main.align` 1,166 ms,
  `gmake persisted-result-smoke` 3,534 ms, `gmake persisted-result-qualification` 9,325 ms. Attested
  identity: managed compiler `82e6bea0933332291012f5de43a2a65c02e8dda7dfe990602de3cce3e30c0908`,
  runtime archive `0c26b938060e747d63886f5f98c07953b69b52d2b572a538373642b96cb75211`, pin
  `2f33ac5c33a898a7894af58322852632ce6ffe42`, Homebrew `llvm 22.1.8`, `openssl@3 3.6.3`,
  `zstd 1.5.7_1`, macOS 26.5.2 (`25F84`), Darwin 25.5.0 `arm64`, `proc_translated 0`, GNU Make
  4.4.1. The complete emitted block is section 11.3 of `docs/specs/c7-persisted-result.md`.
- **C7-P publication preflight and fresh-profile evidence (2026-08-25).** At head
  `4d8aa33f3dff5553043ade5ef8eb87712d5a451c`, `python3 scripts/pre-pr --owner-test
  darwin-profile-gate -- python3 scripts/check-darwin-profile` classified the wave `fresh-image`
  (the `Makefile` and `eval/*` artifacts changed) and passed `darwin-profile-gate` (15,388 ms),
  `managed-align-ensure`, `pinned-align-build`, and `hosted-checks` (50,594 ms). Its `fresh-focused`
  leg **cannot run on Darwin**: `scripts/run-fresh-source-identity-smoke` reads `/proc/self/fd`, and
  the identical failure reproduces at the base commit `a52b9ac` in a clean worktree, so it is a
  pre-existing host limitation rather than a wave regression. Both fresh legs were therefore run
  where they belong. **Installed profile, host Docker:** `python3
  scripts/run-fresh-worker-qualification --installed-profile-only --require-docker --align-repo
  <managed-pin-source>`: **PASS**, `fresh image profile smoke: PASS` then `fresh worker
  qualification: PASS (installed profile only)`. Phases: `docker-daemon` 552 ms, `image-build`
  23,200 ms, `image-attestation` 3,680 ms, `profile-lifecycle` 2,405 ms, `profile-self-test`
  14,771 ms, `trust-mutations` 12,064 ms, `runtime-replacements` 21,692 ms, `boundary-profile`
  246,632 ms, **`worker-aggregate` pass after 363,821 ms**, `cleanup` 1,292 ms. That is this wave's
  `make ci` evidence. **Focused qualification, native Linux `aarch64`** in the privileged
  `c6g2-measure:latest` container with `--init`, `bubblewrap`, `clang`, and `unzip`, non-root with
  `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of the same head: `python3
  scripts/run-fresh-worker-qualification` **PASS** (focused; installed profile deferred; 23 focused
  rows including `check-gate-topology --self-test`), `python3 scripts/test-development-preflight`
  PASS, and `python3 scripts/test-align-toolchain` PASS. Both the preflight and the installed
  profile were then re-run at `cab6755b55b6fb6d94317d3fbfa518cb0ed12061` with
  the same results — preflight phases `darwin-profile-gate` 15,143 ms, `hosted-checks` 50,434 ms,
  the same Darwin-only `fresh-focused` failure; installed profile **PASS** with `boundary-profile`
  255,854 ms and **`worker-aggregate` pass after 379,459 ms**.
- **Why the two Linux legs are not re-run for the review repair, stated as a head delta.** Both
  compensating legs are owned by the fresh-image classifier in `scripts/verification_scope.py`. The
  complete delta from `4d8aa33` (focused fresh-worker qualification, native Linux `aarch64`) and
  from `cab6755` (installed profile, host Docker) to the publication head is `HANDOFF.md`,
  `docs/align-development.md`, `docs/specs/c7-persisted-result.md`,
  `docs/specs/check-gate-topology.md`, `scripts/check-darwin-profile`, and the added
  `scripts/test-check-darwin-profile`. `owns_fresh_image()` returns false for every one of them —
  neither the Darwin gate nor its owner test is a `FRESH_IMAGE_PATTERNS` entry — so no input either
  leg consumes has moved and both green runs stand. The publication preflight still classifies the
  wave `fresh-image`, because the `Makefile` and `eval/*` changed earlier in the branch; its
  per-phase table and the Darwin `fresh-focused` `N/A` reason are recorded in the pull request.
- **C7-P target-local aarch64 Linux gate, green, at head
  `09294dec94924e0363f0443cc671751dd8174186` (2026-08-25).** Native Linux
  `aarch64` in the privileged `c6g2-measure:latest` container with `--init`, non-root with
  `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of the committed head, with the
  image's native pinned build presented through the managed toolchain layout (compiler
  `7507770f2d5c36e94730fee3290446d7751d1ea83ecac00801086261ecfcf100`, runtime
  `8718943f29a9a3f9ba12b38c18eeeb3e70db9bbfdb034e78bf03c49a222a755d`). `check-gate-topology
  --self-test` PASS (5,685 ms), `make gate-topology-check` PASS, `make check` 23 units per-unit,
  `make build`, direct `check-per-unit`, `make persisted-result-smoke` **PASS** (747 ms),
  `make persisted-result-qualification` **PASS** (7,179 ms; same corpus counts as the host, with the
  runner's own `target aarch64-linux` observation), and `python3 scripts/check-baseline-chain`
  `baseline chain: PASS`. Section 11.2 holds the full record.
- **C7-P host publication checks at the repaired head `3e9b27e` (macOS, managed pinned toolchain,
  2026-08-25).** `gmake check` (23 units per-unit), `gmake gate-topology-check` (`check gate
  topology: PASS`, the `EXPECTED` lane bytes unchanged because `darwin-profile-gate` joins no
  aggregate), `gmake format-check`, `git diff --check`, `python3 scripts/test-align-toolchain`
  (managed checkout plus the attestation cases), `python3 scripts/test-check-darwin-profile` (the
  new failure-path owner: construction, malformed input, early exit, and cleanup PASS), and
  `python3 scripts/check-baseline-chain` (`baseline chain: PASS`): all PASS. Negative controls for
  the new owner: reverting each of the four repairs it covers makes it fail with the exact escaped
  exception type.
- **C7-P baseline chain re-finalization (2026-08-25).** Recorded on native Linux `aarch64` in the
  privileged `c6g2-measure:latest` container with `--init` and `bubblewrap` installed at run time,
  as a non-root uid with `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean `git clone` of the
  source commit. `check-gate-topology --self-test` and `make gate-topology-check` ran first, both
  PASS. `record-baseline.py` then recorded both deterministic-reference samples as passing:
  134,035,875-140,845,834 ns, median 137,440,854 ns, at the unchanged pin. The replacement chain is
  source `9fd3ab64433e526d3af5c647ab933e8bfc365103`, oracle
  `3605b27ccbe1089f5ed2cb06294806a85d247cf1`, and finalization
  `f72e71f077e43d2943f9b9572c4367b9091888c4` — appended, never amended. The oracle projection
  produced in the container and the copy committed on the host are byte-identical (SHA-256
  `4335765eec6d715349d9239faadf448c449eeb2756c4c01302b14fb19ebdc417`).
- **C7-PERSISTED-RESULT baseline chain re-finalization (2026-08-25).** Recorded on native Linux
  `aarch64` inside the privileged `c6g2-measure:latest` container run with `--init`, `bubblewrap`
  installed at run time, as a non-root `runner` uid with `umask 022` and
  `PYTHONDONTWRITEBYTECODE=1`, with `chown -R runner:runner /opt/align`, on a clean `git clone` of
  the committed source head. In that container `python3 scripts/check-gate-topology --self-test`
  (**PASS**) and `make gate-topology-check` (**PASS**) ran first, proving the admitted lane bytes and
  the `exact_environment()` self-test copy moved together in `1e5797b`. `record-baseline.py` then
  recorded both deterministic-reference samples as passing: 130,939,292-139,880,709 ns, median
  135,410,000 ns, at Align pin `2f33ac5c33a898a7894af58322852632ce6ffe42`. The replacement chain is
  source `1e5797b3b451c79a48bd28f78edbd47b8540f9ec`, oracle
  `32e1442a5470f6c25862e290b6c2495ee8c2df0b`, and finalization
  `2fe903625816bd4738293e94497f88d43c42b5d9` — appended, never amended — and
  `python3 scripts/check-baseline-chain` reports `baseline chain: PASS`. The oracle projection
  produced in the container and the copy committed on the host are byte-identical
  (SHA-256 `4ecff07744fe4fc37c1052304fbe2a9593a0672c23232133b0c52e22678d4191`).
- **C7-PERSISTED-RESULT supervised capable gate, green, at head
  `36c8568897802afe6744edf6177dbb089d887b5a` (2026-08-25).** `python3
  scripts/run-fresh-worker-qualification --installed-profile-only --require-docker`: **PASS**,
  exit 0, `fresh image profile smoke: PASS` then `fresh worker qualification: PASS (installed
  profile only)`. Phases: `docker-daemon` 913 ms, `image-build` 16,526 ms, `image-attestation`
  3,342 ms, `profile-lifecycle` 2,594 ms, `profile-self-test` 14,713 ms, `trust-mutations`
  12,892 ms, `runtime-replacements` 27,036 ms, `boundary-profile` 412,666 ms,
  **`worker-aggregate` pass after 365,567 ms**, `cleanup` 1,380 ms; whole installed profile
  858,251 ms. Run with the default environment and no diagnostic opt-in. This is the first green
  supervised run that includes `persisted-result-smoke`, and it is the capability's final `make ci`
  evidence; the only later commit on the branch is the documentation update, which changes no
  executable input. Per section 11/12.1 it is not C7 platform acceptance evidence: this host is
  `aarch64` with no reviewed C7-P profile.
- **Environment facts learned while getting that run green; none is repository state.** (1) A failed
  installed-profile run leaves `/sys/fs/cgroup/align-llm-fresh/<uid>` behind in the Docker VM, and
  the next run then fails `profile-lifecycle` in about 0.5 s with
  `FileExistsError: '/sys/fs/cgroup/align-llm-fresh/12345'`; remove that directory from a
  `--privileged --cgroupns=host` container before retrying. (2) `boundary-profile` builds the
  pinned Align compiler twice from source and failed twice with the generic
  `json-scan adoption: ERROR toolchain` while the Docker VM had roughly 17 GiB free, then passed at
  412 s with roughly 31 GiB free; treat that message as a capacity signal first. (3) Do not prune
  the BuildKit cache to make room: two consecutive runs then hit the 1,800 s `image-build` budget
  downloading LLVM 22 from `apt.llvm.org`. Warming the cache once with a direct
  `docker build -f image/fresh/Dockerfile` (which fails only at the late build-key layer) restored
  a 16-28 s cached `image-build`.
- **Container environment fact: the topology self-test needs a reaping PID 1.** In the same image
  started **without** `--init`, `python3 scripts/check-gate-topology --self-test` fails
  reproducibly (three of three attempts) with
  `hanging child cleanup failed: ... lifecycle_errors=('process-group-remains',)`, because `sleep
  infinity` as PID 1 never reaps the orphan the case kills, and the zombie keeps its process group
  alive. With `--init` the same command passes. This is an environment fact, not repository state,
  and it is the same unreaped-descendant class as the `d7f1ff6` adapter fix.
- **C7-PERSISTED-RESULT publication host checks at head `36c8568` (macOS `aarch64-apple-darwin`,
  managed pinned toolchain `2f33ac5c33a898a7894af58322852632ce6ffe42`, 2026-08-25).** `gmake check`
  (23 units per-unit), `gmake gate-topology-check` (`check gate topology: PASS`), `gmake
  format-check`, `git diff --check`, `python3 scripts/check-baseline-chain` (`baseline chain:
  PASS`), `gmake persisted-result-smoke` (**PASS**, 3.1 s for six runners), `gmake
  persisted-result-qualification` (**PASS**, same corpus counts as below, 9.2 s), and `gmake
  c7-owned-record-source-expiry-adoption` (**PASS**, 3 parsed fixtures, 12 example rows, 45 adoption
  rows): all PASS. Section 11 names `LIBRARY_PATH` as this host's Align build-gate linker input, so
  every C7 target here runs with
  `LIBRARY_PATH=$(brew --prefix openssl@3)/lib:$(brew --prefix zstd)/lib` exported; without it the
  bounded functional owner fails closed before its first child. The only later commit is the
  documentation update, which is Markdown-only.
- **C7-PERSISTED-RESULT qualification slice, host (macOS `aarch64-apple-darwin`, managed pinned
  toolchain `2f33ac5c33a898a7894af58322852632ce6ffe42`, 2026-08-25).** `gmake check` (23 units
  per-unit), `gmake format-check`, `gmake gate-topology-check` (`check gate topology: PASS` at the
  admitted lane), `git diff --check`, `gmake persisted-result-smoke` (**PASS**, 3.5-3.6 s for six
  runners), `gmake persisted-result-qualification` (**PASS**: 11 boundary, 256 generated PASS, 32
  generated FAIL, 38 malformed inputs, 29 result mutations, 10 golden rows, 0 unexpected
  divergences, source mutation detected with 5 divergent and 38 agreeing cases, 749 bounded
  children, 8.7 s), and the regression set `gmake c7-owned-record-source-expiry-adoption` plus all
  six `c7-persisted-result-*-smoke` targets: PASS. `python3 scripts/check-baseline-chain` was red by
  design at that checkpoint (`working-tree Makefile differs from the baseline source commit`) and is
  green again after the wrap-up re-finalization recorded below.
  `python3 scripts/check-gate-topology --self-test` fails on this host in
  its `reader-start cleanup` process-lifecycle case with `sigkill-PermissionError`; the same failure
  reproduces at the unmodified `HEAD` copy, so it is a pre-existing macOS-host limitation, not a
  lane-admission regression. Per section 11/12.1 this host has no reviewed C7-P profile, so these
  runs are development evidence, not C7 acceptance evidence.
- **C6-MEASURED supervised gate, green, at head `3768ad8af68bb50ee3129ff392f6ba86ac89e071`
  (2026-08-25).** `python3 scripts/run-fresh-worker-qualification --installed-profile-only
  --require-docker --align-repo <path-to-sibling-align-checkout>`: **PASS**, exit 0,
  `fresh image profile smoke: PASS` then `fresh worker qualification: PASS (installed profile
  only)`. Phases: `docker-daemon` 675 ms, `image-build` 21,883 ms, `image-attestation` 3,822 ms,
  `profile-lifecycle` 3,188 ms, `profile-self-test` 14,331 ms, `trust-mutations` 13,151 ms,
  `runtime-replacements` 22,893 ms, `boundary-profile` 270,909 ms, **`worker-aggregate` pass after
  354,739 ms**, `cleanup` 1,883 ms; whole installed profile 708,521 ms. The
  aggregate is legitimately above the 172-192 s historical band because that band predates the
  C6-MEASURED lane members, which this run is the first supervised run to complete. Run with the
  default environment and no diagnostic opt-in.
- The immediately preceding diagnostic run, same command with `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1`
  exported, at head `e4c7e45`: FAIL at `worker-aggregate` after 178,853 ms, and it named the cause
  verbatim — `prompt measurement adapter: FAIL: [Errno 2] No such file or directory: 'git'`,
  `make[1]: *** [Makefile:129: prompt-measurement-adapter-smoke] Error 1`,
  `make: *** [/workspace/Makefile:234: capable-checks] Error 2`. The controller forwarded 8,192 of
  11,037 captured worker stderr bytes and the worker forwarded all 2,669 aggregate-child stderr
  bytes.
- Host (macOS, managed pinned toolchain) at `3768ad8`: `gmake check` (22 units per-unit),
  `gmake gate-topology-check` (`check gate topology: PASS`), `gmake format-check`,
  `git diff --check`, and `python3 scripts/check-baseline-chain` (`baseline chain: PASS`): PASS.
  The `Makefile` is unchanged by this work, so the baseline chain needed no re-finalization.
- Debian bookworm `aarch64` container, privileged, with `clang` and `unzip` installed and
  `PYTHONDONTWRITEBYTECODE=1`, at `e4c7e45`: `python3 scripts/run-fresh-worker-qualification`
  (all ten focused owners including `run-fresh-image-control-smoke` 4,745 ms with the new
  controller-diagnostic case, `run-fresh-worker-unit-smoke` 5,206 ms with the new worker-admission
  case, and `check-gate-topology --self-test`) and `python3 scripts/test-development-preflight`:
  PASS. That focused run also builds both changed native launchers twice and compares them.
- `python3 scripts/run-prompt-measurement-adapter-smoke` at `3768ad8`: PASS on the host (48 rows,
  unchanged documented Linux-only SKIP) and PASS in the container with a tool root that contains
  only `git` and is the whole child PATH (`ALIGN_LLM_TOOL_ROOT=/toolsim`, 64 rows) — the fresh
  aggregate's shape, reproduced outside it.
- C6-MEASURED aggregate-cost repair at head `55282a8` (2026-08-25). Host (macOS, managed pinned
  toolchain): `gmake check` (22 units per-unit), `gmake gate-topology-check`, `gmake format-check`,
  `gmake prompt-seed-attestation-smoke` (now 0 bytes on stderr), `git diff --check`, and
  `python3 scripts/check-baseline-chain` (`baseline chain: PASS`): PASS. A direct probe also proves
  `scripts/check-gate-topology`'s `exact_environment()` self-test copy still reproduces `EXPECTED`
  byte-for-byte after the lane change.
- Native Linux `aarch64` inside the privileged `c6g2-measure:latest` container, non-root with
  `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of `ebcc8d5`:
  `make gate-topology-check`, `python3 scripts/run-fresh-worker-unit-smoke` (includes the new
  aggregate-diagnostic seam case), and `python3 scripts/test-development-preflight`: PASS.
  `make prompt-verifier-smoke` also PASS as a direct invocation, in 719 s with a 1,525,732 KiB peak
  resident set — the measurement behind its demotion.
- `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker
  --align-repo <path-to-sibling-align-checkout>` at head `55282a8`: **FAIL**. Phases:
  `docker-daemon` 540 ms, `image-build` 20,497 ms, `image-attestation` 3,684 ms,
  `profile-lifecycle` 2,657 ms, `profile-self-test` 14,642 ms, `trust-mutations` 12,299 ms,
  `runtime-replacements` 21,970 ms, `boundary-profile` 266,754 ms, **`worker-aggregate` fail after
  191,760 ms**, `cleanup` 1,751 ms; whole installed profile 537,636 ms. Only output:
  `fresh compiler: ERROR CHILD aggregate`. See the two causes in the active checkpoint.
- `python3 scripts/check-gate-topology --self-test` fails in the `c6g2-measure:latest` container
  with `hanging child cleanup failed: ... lifecycle_errors=('process-group-remains',)`. It
  reproduces identically at the pre-change head `cffdda66c6307d3b6abdbee4c27f3fbd14750690`, so it is
  a pre-existing property of that container, not a regression. The image's own fresh profile runs
  the self-test successfully.
- C6-MEASURED review repair at head `e14c472b11abcbb2368a93d1fd4c97d3554f11e4` (2026-08-25).
  Host (macOS, managed pinned toolchain): `gmake check` (22 units per-unit), `gmake format-check`,
  `gmake gate-topology-check`, `gmake prompt-render-parity-smoke` (58 vectors byte-equal),
  `gmake prompt-generate-smoke`, `gmake prompt-experiment-smoke`,
  `gmake prompt-seed-attestation-smoke`, `gmake prompt-credential-lifetime-smoke`,
  `python3 scripts/run-prompt-measurement-adapter-smoke` (48 rows; the Linux launch rows SKIP),
  the six host-capable `prompt-gate-*-smoke` families, `python3 scripts/check-baseline-chain`, and
  `git diff --check`: PASS. `prompt-evaluate-smoke`, `prompt-fixed-adapter-smoke`,
  `prompt-source-verifier-smoke`, and `prompt-snapshot-helper-smoke` are Linux-only owners and fail
  on macOS for platform reasons alone (`child-subreaper containment is unavailable`); they are run
  in the container below.
- Native Linux `aarch64` inside the privileged `c6g2-measure:latest` container, non-root with
  `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of
  `e14c472b11abcbb2368a93d1fd4c97d3554f11e4`: all 24 owner targets PASS — `check`, `format-check`,
  `gate-topology-check`, `prompt-render-parity-smoke`, `prompt-experiment-smoke`,
  `prompt-generate-smoke`, `prompt-measurement-adapter-smoke`, `prompt-credential-lifetime-smoke`,
  `prompt-seed-attestation-smoke`, `prompt-evaluate-smoke`, `prompt-fixed-adapter-smoke`,
  `prompt-source-verifier-smoke`, `prompt-snapshot-helper-smoke`, `prompt-state-smoke`,
  `provider-smoke`, and all nine `prompt-gate-*-smoke` families. `eval-coding` and
  `c6-evaluation-adoption` also PASS. The gate then passed:

  ```text
  make prompt-gate-check \
    C6_GATE_SOURCE_BUNDLE_ROOT=/work/bundle \
    C6_GATE_PYTHON_EXECUTABLE_PATH=/usr/bin/python3.12 \
    C6_GATE_GIT_EXECUTABLE_PATH=/usr/bin/git \
    C6_GATE_GENERATION_CHILD_PATH=/work/align-llm/main \
    C6_GATE_GENERATION_CHILD_SHA256=c2f5be632c8c3c09fa2d47102a844dd78a85aeebe7fc637296381e85b50c7bb9
  ```

  `prompt gate validator: PASS`. The generation child was built in-run by `make build` and its
  SHA-256 reproduces the locator's frozen
  `c2f5be632c8c3c09fa2d47102a844dd78a85aeebe7fc637296381e85b50c7bb9` exactly. The verifier reported
  `align_llm_observed_head` equal to the derived CI head, `align_reachability: VERIFIED`, and
  `corpus_reachability: VERIFIED`. The same command was re-run at
  `07320e47f243e2a8abc7277f785e2d3a76a7a8d3` — which differs from the branch tip only by this
  handoff entry — and exits 0 there with the same generation-child digest, so the transcript holds
  over the documentation commits as well as over the evidence head.
- Container environment fact discovered by the regeneration: the source verifier runs Git with
  `GIT_CONFIG_NOSYSTEM=1` and `GIT_CONFIG_GLOBAL=/dev/null`, so a `safe.directory` exception cannot
  apply. The pinned Align checkout at `/opt/align/<revision>` must therefore be owned by the
  non-root runner, or every Git observation of it fails with dubious ownership and
  `align_reachability` is `UNVERIFIED`. `chown -R runner:runner /opt/align` is environment
  preparation, not repository state.
- The regenerated measurement was produced at `c737adcf905cb4662472bc86e8345bbcd9bc1346`: measure
  819.2 s, replicate 444.1 s, experiment 145.8 s. The re-run experiment used the identical
  opportunity artifact and at `temperature_micros: 0` reproduced the same candidate variant
  `78611fbc8f6f3f895a0ed715ef01800d5335cb5cba61ee2bd43aedc03166dc63`.
- Publication closures at head `8ddea8a03b817404e68a23e8ce1f39534b7abd13` (2026-08-25). Host
  (macOS, managed pinned toolchain): `gmake gate-topology-check`, `gmake check` (22 units
  per-unit), `gmake prompt-render-parity-smoke` (58 vectors byte-equal), `gmake format-check`,
  `git diff --check`, and `python3 scripts/check-baseline-chain`: PASS. Native Linux `aarch64`
  inside the privileged `c6g2-measure:latest` container, non-root with `umask 022` and
  `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of source commit
  `ba47abdb01776d10f041c0d3e3f36edc67034993`: `python3 scripts/check-gate-topology --self-test`,
  `make gate-topology-check`, and `make prompt-render-parity-smoke`: PASS, then
  `eval/runners/record-baseline.py` recorded both deterministic-reference samples as `PASS`
  (121,396,125-128,282,751 ns, median 124,839,438 ns). The self-test is the proof that the
  `EXPECTED` bytes and the `exact_environment()` copy moved together.
- C6-MEASURED Slice E final capable gate at head `7273f65bfc1a2604daf37b2bd7748a46d2bd59f2`
  (2026-08-25): PASS. The complete capable check graph — every `HOSTED_CHECK_TARGETS` member in lane
  order, then `eval-coding`, `baseline-check`, and `c6-evaluation-adoption`, serially at `-j1`, the
  same list and order `capable-checks` runs — completed in 59 s, and `baseline chain: PASS`. The
  wired gate then passed:

  ```text
  make prompt-gate-check \
    C6_GATE_SOURCE_BUNDLE_ROOT=/work/bundle \
    C6_GATE_PYTHON_EXECUTABLE_PATH=/usr/bin/python3.12 \
    C6_GATE_GIT_EXECUTABLE_PATH=/usr/bin/git \
    C6_GATE_GENERATION_CHILD_PATH=/work/align-llm/main \
    C6_GATE_GENERATION_CHILD_SHA256=93e590658253507dc1518275743fd4e30a7f6c234a9a1e3ac4cf096e29474603
  ```

  `prompt gate validator: PASS`. The generation child was built in-run by `make build` and its
  SHA-256 was computed then; it reproduces the locator's frozen
  `93e590658253507dc1518275743fd4e30a7f6c234a9a1e3ac4cf096e29474603` exactly. The source bundle is a
  clean clone of the tested head plus a clean Align checkout at `.align-revision`; the verifier
  reported `align_llm_observed_head` equal to the derived CI head, `align_reachability: VERIFIED`,
  and `corpus_reachability: VERIFIED`.
- Slice E capable host: the privileged `linux/arm64` `c6g2-measure:latest` container with
  `bubblewrap` installed at run time, running as a non-root user with `umask 022` and
  `PYTHONDONTWRITEBYTECODE=1`. All three matter and are environment facts, not repository state.
  Root ignores directory mode bits, so the `c6f2` permission fixtures cannot fail as designed;
  Ubuntu's default `umask 002` produces `0664` checkouts, which the `FILE_SET` corpus manifest
  correctly rejects with `file-set entry type or mode disagrees`; and stray `__pycache__` output
  makes the CI checkout unclean, which the gate validator correctly rejects. This is not a
  `make ci` substitute: the supervised fresh-worker path builds a fresh compiler and runs the graph
  in its own sandbox, and remains publication CI evidence.
- Host checks at the same head: `gmake gate-topology-check`, `gmake format-check`, `gmake check`
  (22 units per-unit), `python3 scripts/check-baseline-chain`, and `git diff --check`: PASS.
  `gmake prompt-gate-check` with no `C6_GATE_*` values fails closed with
  `prompt gate: ERROR explicit C6_GATE_* input`.
- `python3 scripts/check-gate-topology --self-test` is Linux-only; it fails on macOS in the
  reader-start cleanup case with `sigkill-PermissionError`. Run it on a capable profile.

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
- `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker --align-repo <path-to-sibling-align-checkout>`:
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
