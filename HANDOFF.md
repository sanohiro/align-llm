# Session handoff

Read `CLAUDE.md` first. Architecture and ordering live in `docs/specs/`.

## Current checkpoint

Branch: `agent/align-request-publication`, based on `origin/main` `4dc80ce2`.
Active capability: publish the upstream tracking and complete consumer evidence for Align Requests
117–119. This is documentation-only: the Align pin stays at `8c8bfbc7`; adopting `dfcfd11f` remains
blocked by Request 118 / sanohiro/align#1157. Request 117 is tracked by #1159 and the new
non-blocking fixed-array producer-certification Request 119 is tracked by #1158.
PR #282 merged at `58f5176`: recorded Align responses and merges for requests 92–95, 99, 100, 103, 104, 105, 106, 110, 113, and 115.
PR #281 merged at `4eb0f60e`: settled designs for CPU resident session, ready frame schema 2, GPU-side greedy selection, and prompt-lookup speculation.
PR #280 merged at `2cfbae00`: platform-profiled OLMoE sampled runtime baseline owner and Linux CPU baseline results.
PR #279 merged at `e535d7d0`: recorded capped-read loader startup result on CUDA.
PR #278 merged at `486d1b2c`: selected retained F16 KV policy 2 for Qwen sessions on CUDA.
PR #277 merged at `4921f060`: added backend parity register and rule for CPU/Metal/CUDA differences.
PR #276 merged at `0457a7d4`: recorded Align responses and merges for requests 64, 95, and 97–116.
PR #275 merged at `251d52b8`: registered binary optimization audit requests 97–116 in `docs/align-requests.md` and recorded Align issues #1069–#1088.
PR #274 merged at `f8a4095`: optimized hot logits loops in `greedy` and `select` (`f32.to_bits()`), preallocated builder capacity in `tokenizer_qwen2` (`array_builder(count)`), registered Align Requests 92–96 in `docs/align-requests.md`, and filed upstream Align issues #1063–#1067.
PR #273 merged at `ae2fecd`: adopted latest Align compiler and runtime (`8c8bfbc7a3169e84ecc8415f5149ab8c61afe863`), adopted typed slice writers, buffer.filled, array_builder capacity, in-place array truncate, integer match range/value patterns, is_char_boundary, and verified all suites.
Align #1062 is merged at `8c8bfbc7a3169e84ecc8415f5149ab8c61afe863` (permit disjoint record field borrows at call sites #1050).
Align #1061 is merged at `400137f30f5155c1601cdd6e3f1b0aa318fb8d72` (`array.truncate`, typed slice writers, bulk fill, owned field replacement).
Align #1060 is merged at `5f9c31ac62b54dacf3ef8462adb2ea04768f1211` (match range patterns).
Align #1059 is merged at `ec091852b95cef49b288e970dc32c92a6e9da6ce` (caller-result copy elimination).
Align #1058 is merged at `241035ba97b2a679ce6589f2df66630cdcc2c691` (`str.is_char_boundary`).
Align #1056 is merged at `61b2de79576fde043d5f310c1300370c02250fc3` (plan 65: float inspection, filled buffers, builder capacity).
Align #1046 is merged at `da20aefe1e4054cd132fbbf852217d5ee2c240ac` (plan 64: composed byte-loop proofs, stable descriptor snapshots).
The managed pin is updated to `8c8bfbc7a3169e84ecc8415f5149ab8c61afe863`.

Completed work:
- Binary and compiler optimization audit across x86-64 and ARM64:
  - Discovered missed SIMD vectorization in 152k logits scan (`greedy` and `select`).
  - Discovered missing `exp` intrinsic causing libc dynamic `pow@GLIBC` / `_pow` calls in Softmax.
  - Discovered cross-module inlining suppression under default per-unit compilation without ThinLTO.
  - Discovered per-token heap allocation storm in decode loop (`mf_decode_layer_node_table`).
  - Discovered `tokenizer_qwen2.filled_i64` capacity reallocations.
  - Discovered compiler verifier bug in `alignc explain-opt src/decode_step.align` (`dropdeep` invalid empty `!dbg !{}`).
- Created upstream Align issues on `sanohiro/align`:
  - #1063: [Standard Library & Codegen] Add x.exp() math intrinsic in core.math (lowering to llvm.exp)
  - #1064: [Optimization RFC] SIMD slice argmax and aligned typed float slice views for logit selection
  - #1065: [Language RFC] Support fixed-size inline arrays in structs ([T; N])
  - #1066: [Compiler Optimization] Default ThinLTO on --profile release or small function body exposure for cross-module inlining
  - #1067: [Compiler Bug] Invalid empty !dbg metadata attached to dropdeep loop in align_codegen_llvm causes LLVM verifier failure
- Registered Align Requests 92–96 in `docs/align-requests.md` with links to issues #1063–#1067.
- Implemented immediate application optimizations in `align-llm`:
  - `src/runtime_generation.align`: Eliminated duplicate memory loads (`u32_le` + `f32_le`) in `greedy` by using single `f32_le` load and in-register `value.to_bits()`.
  - `src/runtime_sampler.align`: Eliminated duplicate memory loads in `select` by using single `f32_le` load and in-register `value.to_bits()`.
  - `src/tokenizer_qwen2.align`: Preallocated builder capacity in `copy_i64` and `filled_i64` (`array_builder(count)`), eliminating up to 54 doubling reallocations per piece.
- Formatted and verified all suites.
- Mac-native binary optimization audit of the `--profile release` image at Align pin `8c8bfbc7` (alignc 0.7.5, LLVM 22.1.8), Apple M1 / macOS 27.0, on align-llm `b72b0b48`. Measured, not inferred:
  - Zero-FP-SIMD census: the 5.3 MB release image contains zero floating-point SIMD instructions in any Align-generated function, in all three of `--profile release`, `--target-cpu native` and `--profile fast`; only 73 `vector.body` across 2,108 defined Align functions.
  - `--rt-lto` does not inline at the default `--target-cpu baseline` on aarch64: 1,523 / 162 / 42 `str_eq` / `starts_with` / `ends_with` call sites at the default target against 445 / 0 / 7 at `--target-cpu native`, plus 81 duplicate internal bodies; `--profile fast` is worse (1,580 / 171 / 53).
  - `alignc build src/main.align --thin-lto` is a hard failure (ThinLTO prelink provenance rejection), so there is no working cross-boundary inlining mechanism at default settings today.
  - `alignc explain-opt` crashed on 7 hot modules (`decode_step`, `moe_decode_step`, `gguf`, `tokenizer_qwen2`, `alignpack`, `model_ir`, `main`) at that pin; this is Align #1067, now fixed upstream by PR #1068 (merge `25391cde`). A separate root-model defect leaves a further 4 modules reporting an empty module.
  - Real Metal generation profile (Qwen2.5-Coder-7B Q4_K_M, 128 tokens, ~8.0 tok/s on M1): Align-compiled code is about 0.1% of sampled CPU; the run is GPU-bound in Metal completion waits, and load and prefill are ggml-dominated.
  - Real tokenizer profile (same vocabulary, 55 KB mixed input, 120 repetitions, 161,237 tokens/s): 74.5% of leaf samples are Align-compiled code, with `array_builder_push` plus `ArrayBuilder::reserve` at 14.1% and `align_rt_str_eq` at 4.5%.
  - Audit baselines for the Align-owned CPU kernels on this Mac: greedy 242 us/call over 151,936 logits and sampler 267 us/call over 152,064.
  - Audit artifacts live in the session scratchpad (disposable); nothing is retained in Git.
- Filed the audit results upstream on `sanohiro/align`: issues #1069–#1087 (19 issues), the umbrella design issue #1088 ("[Design] Vectorization contract"), and review comments on #1063, #1064 (two comments), #1066 and #1067.
- Registered Align Requests 97–116 in `docs/align-requests.md` (one per issue #1069–#1087 in issue-number order, plus Request 116 for umbrella #1088), all PROPOSED and non-blocking, and recorded the design-review conclusions for #1063 and #1064 under Requests 92 and 93.
- Registered Align Request 117 in `docs/align-requests.md` for the C2 `null_handle` constant gap
  (PROPOSED, non-blocking, tracked by sanohiro/align#1159).
- Expanded Request 118 with the pin-only tokenizer, alignpack, runtime-provider, and GPU-session
  failure matrix recorded on sanohiro/align#1157.
- Registered Request 119 for borrowed fixed-array record producer certification across fallible
  imported calls (PROPOSED, non-blocking, tracked by sanohiro/align#1158).

Next actions in priority order (backend parity items lead; register: `docs/backend-parity.md` sections 5 and 6):
0. When Align fixes #1157: adopt the fixed pin, run the standing owner set plus `run-gpu-session-reuse-smoke` and `run-layer-forward-smoke`, refresh the C0 platform profile (`--print-identity`; it mismatches on `align_revision` and `compiler_sha256` at any new pin) and `docs/python-boundary-inventory.json` `align_revision`, then move the merged requests to ALIGN_LLM_VERIFIED.
1. After this request-only publication merges, resume independent roadmap work at the current pin.
2. Metal items P4, P5 and the P3 Metal leg: the `llama-server` paired rerun at current main (M1).
3. C3 CPU resident session per `docs/specs/cpu-resident-session.md` (scheduled before R9).
4. P9 pinned logits staging (cheap; request protocol).
5. P10 OLMoE host-side per-token attribution.
6. P8 ready frame schema 2 (design merged in #281; implement per `docs/specs/gpu-runtime.md` §3.12).
7. §3.13 GPU-side greedy selection: census step 0 only, delete on any tie.
8. R9 speculation after C3.
9. C1 deferral: record bit identity of the legacy path at 4 vs 16 threads with `scripts/run-moe-decode-step` gate G1 on `linux-x86_64-v1`.

Continued next actions from the previous checkpoint, after the list above:
1. Adopt the Align pin containing PR #1068: update `.align-revision`, materialize and verify the managed toolchain, and confirm `alignc explain-opt` now reports on the 7 modules that crashed at `8c8bfbc7` (Request 96 moves toward ALIGN_LLM_VERIFIED).
2. Application-side improvements available today at the current compiler, ranked by measured effect:
   - Add length pre-checks before string-literal `==` chains (`src/tokenizer_qwen2.align:1754-1767`, `build_eog_set`).
   - Give hot `array_builder()` calls their known capacity.
   - Split `model_forward$Outcome` into a hot per-step record and a cold per-run diagnostics record.
   - Recommend `--target-cpu native` for align-llm's own release builds in `docs/align-development.md` (removes 1,275 call sites and 41 duplicate bodies; the portable compiler default stays settled upstream).
   - Dropped, with the disposition recorded in the register: the 13 member columns (skipped, not structural) and the `best.max`/bits argmax fast path (legacy argmax loops keep explicit compares; see `docs/specs/cpu-baseline-linux.md` §9).
3. Monitor upstream Align responses to issues #1069–#1088 and to the comments on #1063, #1064, #1066 and #1067.

Latest durable verification:
- `python3 scripts/pre-pr --base origin/main --owner-test bundle-owners -- sh -c 'make build >/dev/null && python3 scripts/measure-cuda-optimization --self-test && python3 scripts/run-gpu-session-measurement-smoke && python3 scripts/run-olmoe-platform-sampled-runtime-baseline --self-test && scripts/run-ggml-spike-smoke'`: PASS at the repaired branch head (hosted; owner bundle-owners), rerun after the review repair.
- `make check`: PASS, 155 units.
- `make fmt`: no change.
- `scripts/check-format`: PASS.
- `scripts/run-layer-forward-smoke`: PASS.
- `scripts/run-ggml-spike-smoke`: PASS.
- `scripts/run-runtime-provider-smoke`: PASS.
- `scripts/run-gpu-session-measurement-smoke`: PASS.
- `scripts/measure-cuda-optimization --self-test`: PASS.
- `scripts/run-olmoe-platform-sampled-runtime-baseline --self-test`: PASS (with the new unresolved-name guard).
- `python3 scripts/check-python-boundary --strict`: PASS (after the C2 launch-source digest refresh).
- G1 `run-gpu-independent-acceptance`: PASS (19 cases twice) on the bundle build.
- `run-gpu-session-measurement --campaign cuda-current`: PASS (348.7 s).
- C0-protocol pairs C2 and C1: COMPLETE.

Blockers, constraints, decisions:
- Zero regressions against all smoke and benchmark suites.
- Python boundary launch sources strictly preserved without unverified digest modifications.
- Request 118 is the only blocking Align request (pin adoption); Requests 92–95, 97–117, and 119
  are `Blocking: no`, so every application-side item at pin `8c8bfbc7` may proceed. Do not consume
  any proposed Align surface while those requests are PROPOSED.
- Align #1070 (Request 98) means `--thin-lto` cannot be used on align-llm at all today, and Align #1069 (Request 97) means the default `--target-cpu` loses the `--rt-lto` inline on aarch64; choosing `--target-cpu native` for align-llm's own builds is the only available mitigation.
- The audit's own artifacts are in the session scratchpad (disposable). Re-derive them rather than citing a local path.
- Request 118 (Blocking: yes) pauses every `.align-revision` adoption at or after `2c39850b`; resume when sanohiro/align#1157 is fixed and the reproducer passes; then adopt in one pin update and verify Requests 92–95, 99–100, 102–103, 105–106, 109–110, 112–116.

## Completed capability: latest merged Align adoption

Branch `agent/align-latest-adoption`, based on merged CUDA F16 PR #243
(`4fbc7d2d989fbf1f185db410b8a8e1d8a5234957`). PR #245 merged at `40f0bbf5a64b7d826c6871b93b7f0c43b6b21d1b`. Implementation,
consumer verification, exact-head preflight and required GitHub checks are complete.

The managed pin advances from `f502fe3da00ce0b39c4eeec40586b11688627fbd` to latest
merged Align `21d0cf27fb92166370b2705d5c366c2b269d17a3` (#1042). It includes bounded
byte storage / direct sequential chunks, writable/native byte-view fixes, codec/SSE
view invalidation, computed fixed-array field borrows and active-checkout runtime
build inputs. No client source or public API changes are required.

PASS: `scripts/align-toolchain ensure compiler`, `scripts/align-toolchain verify`,
`make check` (155 units), and `scripts/run-product-cutover-adoption-smoke`. The clean
manifested `46aea33` CUDA session build uses compiler SHA-256
`042e772d0cf3002e852a33dd3463c62386c17ce853c4c7e7d4883bac73db0524`.
`scripts/run-gpu-session-independent` passes all 7 Qwen / 9 OLMoE exact responses
and counts; result SHA-256
`e2fdd1619ad26bed2bd0dc862e4c25c333dc22458a7f60062b947b79a54a981f`.
Retained local receipts are under `gpu-cuda-enablement-20260914/latest-align-*`.

One fresh comprehensive review by `/root/latest_align_adoption_review` covers
`46aea33db0fb13fcf5e815d05c743d350d395ac8` against base/merge base `eaff971`:
CLEAN, no findings. Following changes integrate the same CUDA tree and refresh
this durable checkpoint; the pin and client source remain unchanged. Review/check
metadata and final integration evidence belong in the adoption pull request.

R86's optional-carrier negative still passes both check modes at this new pin.
It remains a recorded nonblocking compiler residual, not verified/closed by adoption.
The user now authorized publication of the previously preserved request note. Sibling
Align's unrelated deleted `.codex/config.toml` remains untouched. No new platform qualification,
aggregate audit or compiler-specific performance claim is selected by this pure pin.

The active worktree uses the adopted pin. Further implementation is outside this
request-note publication; native Mac performance remains explicitly pending.

## Completed CUDA F16 KV capability and concurrency retry

PR #243 is merged at `4fbc7d2`; CI budget prerequisite #244 merged at `810a456`.
Native F16/Flash, explicit prefill interval, session reuse, 16 independent requests
and both host-capacity owners PASS. On historical compiler `f502fe3d`, the complete
clean `48f249b` versus `4bf8011` campaign has 80 exact responses, no external
interference and 27.47% OLMoE long-cached median paired reduction, faster 5/5;
all seven guardrails pass. The accepted portable report is
`eval/benchmarks/cuda-kv-f16-2026-09-14.json`. This old-pin measurement is not a
performance result for the new Align compiler.

The renewed QKV lifetime experiment `16a7a1e` is NOT_MET: the final quiet incremental
campaign gives 1.32% primary reduction, faster 3/5, below the fixed 15% / 4-of-5 floor.
All 80 responses match and all seven guardrails pass. Qwen traces show 454 overlapping
kernel pairs; OLMoE shows none. The first campaign was invalidated by author CI-status
CPU activity and wholly rerun with those calls stopped. Complete negative evidence is
`eval/benchmarks/cuda-qkv-lifetime-2026-09-14.json`. An ancestry-only merge preserves
the experiment without shipping its graph defaults, tagging or allocator changes.
Future QKV work needs a new material hypothesis; no such follow-up is active.

## Completed capability: ALIGN-PRODUCT-CUTOVER

The user requested completion of normal-product Python removal on 2026-09-13.
Branch: `agent/align-product-cutover`. Candidate `edc9bb9` includes `origin/main`
`39b4cdc`; its following consolidated repair binds the authenticated source TREE,
manifest repository and copied validation source. Normal product execution is in Align,
including provider generation, edits, validation, repair, scoring, publication,
acceptance and rollback. There is no active implementation blocker or product Python debt.
Publication and merge are now explicitly requested; final preflight and hosted checks
are the remaining publication work.

The normal external-command evaluator refuses all eight historical implementations by
supported literal launch descriptor, reserved path and unchanged frozen digest, including
renamed copies, before any task/result. Owned task records survive dispatch. Explicit
external Python target tests remain allowed; developer tools and independent replay
oracles remain outside normal product execution. Sixteen historical command manifests
remain immutable replay inputs.

The exact managed Align pin is `f502fe3da00ce0b39c4eeec40586b11688627fbd`
(PRs #1033/#1034). Compiler/runtime materialization and managed verification pass.
R84/R85/R87/R88 are ALIGN_LLM_VERIFIED. R86 remains ALIGN_MERGED and nonblocking:
its optional move-after-use negative still compiles and produces an empty digest.
`eval/fixtures/product-cutover-option-after-move.align` and the request register retain
the witness. Product construction binds the digest before moving its measurement;
the consuming initializer audit found no unsafe product occurrence. Do not claim R86
fully verified or start another provider pin cycle solely for this residual.

## Durable verification

All commands below PASS. `$CUTOVER_BINARY` is the real-linked Linux ARM64 product;
model/library/shim operands identify the explicitly prepared native runtime assets.

- Managed materialization and `scripts/align-toolchain verify`; managed macOS and
  exact-source Linux product builds. `scripts/run-product-cutover-adoption-smoke`
  passes source/per-unit and runtime witnesses on macOS/Linux.
- `python3 scripts/run-align-product-cutover --functional --binary "$CUTOVER_BINARY"`:
  final repaired product. Eight paired rows, sixteen repair attempts, public refusals,
  actual HTTP workers, coding-v2 and independent result checks. Source TREE declaration,
  kind/path/digest, changed source bytes and mismatched repository cases refuse before
  an attempted row. Ordinary external-command error semantics remain intact.
- `python3 scripts/run-align-product-cutover --containment --binary "$CUTOVER_BINARY"
  --align-repo "$PINNED_ALIGN_SOURCE"`: task lifecycle/resource/cleanup owners and actual
  installed Linux Docker profile PASS on reviewed `edc9bb9`, with standard local socket,
  no ambient `DOCKER_HOST` and no Docker skip. Image attestation, lifecycle/self-test,
  trust mutations, runtime replacement, compiler boundary, worker build and profile
  execution pass. The repair changes input binding, not this containment boundary.
- `python3 scripts/run-align-product-cutover --no-python --binary "$CUTOVER_BINARY"
  --models "$CUTOVER_MODELS" --libraries "$CUTOVER_LIBRARIES" --shim "$CUTOVER_SHIM"`:
  final repaired product. Relocated normal/repair/provider evaluation, all eight renamed
  implementation refusals, Git/index/test-selection/patch/verification/failure memory,
  proposal/accept/rollback and real three-token inference. Python and repository scripts
  are absent from product namespaces; full descendant exec traces are inspected.
  Independent Python oracles run outside; a separate namespace verifies an explicit
  external Python target test.
- A1 renderer parity, score, score-prefix, verifier and state owners PASS. The changed
  verifier owner and state CLI pass again after the consolidated input-binding repair.
- `scripts/run-prompt-task-inputs-smoke` and
  `scripts/run-prompt-evaluation-inputs-smoke` PASS after the repair, with complete-list
  ownership and source TREE/repository refusal cases.
- `python3 scripts/run-prompt-gate-validator-smoke FAMILY`: validator, product-version,
  source-bundle and source-revalidation PASS; changed product-version owner passes
  again with missing/wrong-kind/wrong-path TREE refusals. Historical v1 bytes stay intact.
- `python3 scripts/check-python-boundary --strict`: 272 Python files, 83 embedded
  hosts, 157 product modules and zero frozen debts. `python3 scripts/test-python-boundary`:
  all 30 mutation cases PASS. Pure filename policies stay in `source_file_kind` without
  weakening the checker. Final index/selection/patch golden owners PASS.
- `scripts/run-runtime-provider-smoke`: sampler and 61 CLI assertions PASS. No new C ABI,
  GPU performance claim or complete `make ci` audit was required. `make fmt` and
  `git diff --check` PASS.

## Review and repair

One fresh independent high-effort comprehensive inspection reviewed the entire committed
cutover, including code, source/process boundaries, records, tests and governance.
Reviewed head: `edc9bb960c93a8e746a5e5b6ead1aadbd8e7920d`.
Base tip and merge base: `39b4cdc6ed864f39554b618335b4bd89f9346dcc`.
Reviewer: `/root/cutover_review`; verdict FINDINGS; inspection-only.
Complete findings and dispositions:

1. P1: an undeclared source tree could supply validation bytes outside the authenticated
   artifact set (`prompt_task_inputs`, `prompt_score`, source collection/runtime).
   Accepted: require the exact repository TREE for every v2 task in native admission,
   persisted verification and the independent gate; verify its bytes before dispatch.
2. P1: `source_dir` could differ from snapshotted `repo_path`
   (`prompt_evaluation_runtime:216–223`). Accepted: require exact equality during
   complete input admission and again when resolving the runtime source.

Both findings are addressed in the single repair following the reviewed candidate.
The repair delta was inspected for unrelated changes; regression owners cover all
accepted root-cause classes. It restores the settled contract without expanding the
capability or changing its approach, so no second comprehensive review is required.
The bounded retrospective found one reusable lesson: keep source declaration, snapshot
identity and copied execution input tied at admission. Existing owners now test that
invariant; no additional process gate or retrospective-only change was added.

## User-requested speed measurement (2026-09-13)

Completed the controlled old/new fixed-patch evaluator comparison after the user asked
whether cutover improved speed. See `docs/product-cutover-benchmark.md` and
`eval/benchmarks/product-cutover-2026-09-13.json`. Measured application heads are
`9855afe` and `2f25c3f`, using their respective exact Align pins. Nine alternating measured
pairs after two warmup pairs: complete CLI medians 2.145870293 s before and 0.720526833 s
after, a 66.42% reduction; all nine pairs favor native and all 22 invocations pass eight
rows. Native/legacy inputs are controlled semantic counterparts with the same fixed patch
and external tests. No model generation or repair attempt is measured. Historical OLMoE
84.062 s versus llama.cpp 14.174 s remains unchanged; do not turn this evaluator result
into an inference claim. Product source was unchanged during the measurement. The user designated the After arm
as baseline `product-cutover-fixed-patch-2026-09-13`; future candidates rerun this reference
on the same host under the documented protocol. The recorded sample JSON is immutable.

The measurement review found missing durable replay and dependency identities; these
were repaired in `c2e99e0`. Its final review found optimized-Python validation bypass,
unbound reference substitution, unchecked dependency equality and unbound native source.
The owner was re-scoped to frozen historical-pair replay: arbitrary reference/candidate
substitution is removed, both exact source commits and binary hashes are required,
optimized Python is rejected, and source/dependency maps must match before timing.
The immutable original sample JSON stays unchanged; the dependency supplement is a
later capture from retained assets, not a contemporaneous attestation.

Frozen replay passes all 22 invocations with eight rows. Negative owners pass optimized
mode, wrong native commit/binary, reference substitution, dependency mismatch and existing
evidence refusals. Replay qualification timings are not a replacement baseline or speed
claim. Strict boundary passes 272 Python files, 83 embedded hosts, 157 product modules and
zero debts. The portable scripts require retained or exact-byte rebuilt historical binaries;
future candidate automation is outside this narrow frozen owner. Final exact-head preflight
and hosted integration checks remain before merge.

## Next actions

No implementation work remains for the requested cutover. Complete the authorized
publication and merge: run exact-head `scripts/pre-pr --owner-test LABEL -- COMMAND ...` from a
clean named branch/worktree on the capable Linux host, attach the review envelope and
repair disposition, and require all selected checks before merge. The earlier `--plan`
run only identified fresh-image scope; it is not a preflight stamp. Preserve the unrelated
Antigravity working files. The user has now authorized the MoE GPU follow-on below.

## Active MoE GPU diagnosis (2026-09-13)

Branch `agent/moe-gpu-diagnosis`, starting at `ad94eb5`; isolated from the original cutover and
Antigravity working files. The user selected the recommended MoE direction. The active-entry
ledger in `docs/specs/gpu-runtime-performance.md` bounds an unchanged resident OLMoE Metal
session diagnosis and the selected O1 retained-half KV implementation. The unchanged manifested build,
four-request host-sampling run and shorter Metal System Trace all PASS; every response passes
the fixed 128-token/sequence quality check. See `docs/gpu-moe-diagnosis.md` for exact commands,
identities, sampling counts, artifact digests and limits. The first 60-second device trace remains
INCOMPLETE after finalization timeout; the separate 10-second trace saved successfully.

Main-thread non-input-wait samples are dominated by backend completion wait (94.82%); topology
hashing and input update are small. The subsequent counter-enabled trace attributes 46.03% of
owned shader sample duration to F32-to-F16 conversion (instrumented attribution, not wall-time
savings). O1 now retains F16 KV only in supported Metal OLMoE sessions, converting new rows.
Exact backend-aligned allocation preserves the allocator's exact-consumption invariant. Real
Metal `run-gpu-attention-policy-smoke` passes incremental rounding, overwrite, prefix, padding
and direct F16 Flash equality; the extended malformed-input and metadata-exhaustion batch PASS.
`scripts/run-gpu-session-reuse-smoke` and `make fmt` PASS. No new Align gap.

Clean implementation checkpoint: `d60e2b6`. Managed build and unchanged full Metal independent
session oracle PASS (Qwen2 7/7, OLMoE 9/9 exact outputs/counts). Allocation-count host-capacity
owner PASS for both models. Five alternating local pairs PASS all 40 quality checks and all
paired outputs/counts, with median request-wall reductions of 44.00%, 46.00%, 63.33% and 73.82%
against the clean manifested `ad94eb5` rebuild. Every case is faster in 5/5 pairs; all four
meet the predeclared 15% local floor. See the diagnostic report for artifact hashes and limits.
This is not a competitive llama.cpp or CUDA result, or a coding time-to-passing-patch claim.

## Active capped-read loader repair (2026-09-13)

The startup repair is isolated on `agent/capped-read-loader-repair`, based on accepted O1 docs
checkpoint `30f41c9`; the original C1 worktree remains untouched. `runtime_qwen_load.load_file` and
`runtime_olmoe_load.load_file` now use lexical capacity epochs at
`min(staging_bytes, remaining_member_or_piece_bytes)`, including consecutive equal-sized expert
pieces. Traversal cursors persist outside the epoch loop; its backedge drops the old chunk before
the next capacity allocation. Plan order, offsets, upload contents and existing fail-closed errors
remain unchanged. No ABI, pack format, mmap, async I/O or kernel change is present. The settled
scope, cost ceiling and owner matrix are recorded in
`docs/specs/gpu-runtime-performance.md` under “Startup capped-read loader repair”.

The Qwen and OLMoE loader smoke commands, including the test-only actual-`pread` observer, compile
and pass on the managed Align pin `f502fe3da00ce0b39c4eeec40586b11688627fbd`. They cover the
capacity bounds, payload offsets, repeated equal-sized expert reads, short/zero/error refusal and
the normal load path. The clean manifested candidate build and required independent session owner
also pass: all seven Qwen and nine OLMoE requests match exact output and token counts. The bounded
native startup campaign completed in 272.56 seconds with five alternating pairs per model. Qwen's
median paired startup reduction is 24.05% (candidate faster 5/5); OLMoE's is 61.58% (candidate
faster 5/5), meeting the declared OLMoE floor and Qwen guardrail. Receipts and per-arm logs are
retained outside Git under `capped-read-session-independent-20260913` and
`capped-read-startup-20260913`; the diagnosis records their clocks, identities and limits.

The comprehensive native review requested from `gpt-6-astra` at `xhigh` reviewed head
`44aa9af3c3aff16e3a4cf25feec670f1d54c077d` against base tip and merge base
`30f41c91a2b815f3d1983a182f016bc9bb9721ca` and returned `FINDINGS`. Its two P2 findings were
both in the test observer: the OLMoE fault threshold could stop in metadata, and the validators
did not enforce each payload member/piece's exact remaining-byte bound and offset. The committed
repair `c3a57d578b5f37a41a7cbb3577f9f11abc845480` derives the fixture payload boundary, binds
faults to payload traversal, validates exact per-read bounds/offsets while advancing by returned
counts, and covers complete expert-piece traversal. Astra's narrow repair assessment reviewed
that head against `44aa9af3c3aff16e3a4cf25feec670f1d54c077d` and returned `ADOPT` with no new
issues. The capped-read capability is COMPLETE and locally ADOPTED; publication and merge remain
pending the user's publication batch. The bounded lesson is to validate actual payload traversal
for fault cases so metadata failures cannot masquerade as loader coverage; the existing repair
covers it without a new gate.

### Historical O1 review (separate from this repair)

One fresh high-effort review by `/root/moe_review` covered the whole diff and final evidence
documentation. Reviewed head `d60e2b626ae69837d96df1866c728d4c5864ff40`; base tip and merge
base `ad94eb5a18e49695a0c2321da7c9c37bd7ddd2f7`; verdict FINDINGS. Complete findings:
P1 control source authentication was insufficient for a dirty build; accepted and repaired by
strict clean-control rebuild, source/compiler/library verification and a fresh five-pair PASS.
P2 stale specification claimed no new measurements; accepted and corrected to distinguish local
O1 evidence from historical/competitive claims. The consolidated repair is the commit containing
this checkpoint; its evidence/documentation delta was inspected, with no runtime/test changes.
No valid finding remains unresolved; the narrow repair does not require another full review.

Next: complete applicable publication checks when publishing this capability, then qualify its
competitive baseline and coding wall-time consumer before claiming superiority to llama.cpp. Keep
actual CUDA capture/replay separate from Metal observations. Cutover publication remains pending
independently. Implementation and owner tests are committed in `agent/moe-gpu-diagnosis`;
the consolidated review repair records the completed local evidence. No PR/preflight/merge is
claimed for O1 at this checkpoint.

Use `/opt/homebrew/bin/gmake` on macOS and documented Homebrew linker paths. Real ggml
libraries and a relocated shim are required for inference acceptance; the unavailable
stub is not a substitute. Runtime model readers retain R21's private-writable-copy rule.

## Separate local Antigravity capability

Keep `.agents/`, `.codex/`, `scripts/review-agy`, `scripts/agy-review-result.jq`,
`scripts/test-agy-review`, `docs/agy-development.md`, `docs/specs/agy-development.md`,
and the unstaged agy additions in `CLAUDE.md` outside the product commit. The product-language rule is already in the committed candidate; only the unrelated
Antigravity additions remain unstaged in `CLAUDE.md`.
The agy capability's earlier live owner and 36 negative cases PASS; its separate
comprehensive review found two accepted defects, both repaired. Preserve this work.
