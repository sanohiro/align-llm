# C8 optional targeted stage: re-entry plan and evidence ledger

Status: **REVIEWED CANDIDATE — implementation, owners, pin adoption, paired acceptance, and
comprehensive review pass after one documentation repair; exact-head preflight and publication
pending.**

This document preserves the useful contract and implementation evidence from
`agent/c8-optional-targeted-test` without treating that stale branch as a merge candidate. The user
explicitly prioritized re-entry on 2026-08-28, so implementation is on
`agent/c8-optional-targeted-stage` from `main` `e15e3d3`. Track B resumes after this bounded
consumer capability merges.

## 1. Decision and entry gate

The capability remains worth considering. The fresh current-parent baseline at `e15e3d3` measured
the complete targeted process at 14,311,285 ns of a 43,886,999 ns fixed-task median, or 326,093 ppm
(32.61%). Parent binary SHA-256 is
`10ff55c084f35ee079f19c4b85fdc835abac0350642485d4d298d84dfffacc16`; the command was
`scripts/run-c8-selection-signal-benchmark baseline-atomic BINARY 15`. This is far above C8's 2,000
ppm shipping floor. The earlier evidence-branch baseline was 14,719,833 ns of 45,955,119 ns
(320,309 ppm), which independently points to the same boundary. The fixed full-test command executes
the targeted assertion before its independent assertion, so the proposed benchmark removes a
demonstrably redundant process rather than weakening the fixed task's acceptance gate.

The compiler prerequisite also exists. Align PR #892 merged as
`3a34febe912db5096c58c74fede36ff53f223e04` and repairs the array-to-slice view reached below a
borrowed sum projection. Replaying the prototype in a temporary worktree with a sibling compiler
containing that merge produced these investigation results on 2026-08-28:

```text
make ALIGN_REPO=<sibling-align> check             PASS
make ALIGN_REPO=<sibling-align> build             PASS
make ALIGN_REPO=<sibling-align> verify-loop-smoke FAIL: INVALID, code 2
```

The owner failure is expected evidence of incompleteness: the checked-in owner still writes schema
version 1, while the prototype accepts exactly schema version 2. It is not a compiler failure.

Re-entry is allowed by both exceptions in the C8 closure rule: the recorded ceiling exceeds the
floor, and implementation exposed a genuine Align compiler request that has since shipped. The user
made the required explicit prioritization decision on 2026-08-28.

## 2. Evidence inventory and salvage boundary

| Evidence | Durable value | Reuse rule |
| --- | --- | --- |
| Design commits `4ddabc2`, `74fac36`, and `950bcbb` | Original ledger, four accepted design-review findings, validation order, closure matrix, and named wire vectors | Read as design history; transplant reconciled decisions into this standalone plan or its successor, not the old section number |
| Uncommitted `src/verification_loop.align` | Working schema-v2 decode, validation, stage suppression, and the real Align compiler reproduction | Use as a behavioral sketch; reimplement against current `main` after resolving the ownership mismatch below |
| Uncommitted `src/failure_memory.align` | Verification-result schema-v2 admission guard | Reuse with the complete result and memory owner matrix |
| Uncommitted `docs/align-requests.md` | Historical request text and Align PR #892 evidence | Do not apply: its Request 21 identifier collides with current `main`'s `std.fs.open_ro` Request 21 |
| Align PR #892 / merge `3a34febe` | Shipped compiler prerequisite and focused compiler owners | Adopt through `.align-revision` in the consumer capability and verify with the real client |
| Fixed-task baseline | Current parent: 14,311,285 ns targeted stage within a 43,886,999 ns median; evidence branch: 14,719,833 ns within 45,955,119 ns | Current cost-ceiling gate passed; use the fixed current-parent binary for the final paired comparison |

At current `main` on 2026-08-28, the relevant `verification_loop.align` and
`failure_memory.align` source blobs are still byte-identical to the prototype's committed parent.
The concept is therefore not superseded in those modules. The surrounding owner, documentation,
request register, roadmap, and C8 ledger have advanced and must be reconciled rather than replaced.

Do not cherry-pick or merge the stale branch. In particular:

- current `main` already uses C8 section 2.9 for `C8-SELECTION-SINGLE-GIT-QUERY` and records C8 as
  closed after nine shipped capabilities;
- the current request register already assigns Request 21 to another surface;
- the prototype branch is 103 commits behind the inspected `main` head `e15e3d3`;
- the prototype has no schema-v2 fixtures, complete owner changes, user documentation, pin adoption,
  or paired comparison; and
- its owner test fails, so it is not a consumer-complete checkpoint.

## 3. Public-contract ledger

This ledger is the re-entry contract. If implementation discovers a different public promise,
update this table, the closure matrix, code, fixtures, and directly affected documentation together
before review.

| Surface | Exact contract |
| --- | --- |
| Task input | `VerificationTask` moves to schema version 2. `targeted_test` changes from `CommandSpec` to `Option<CommandSpec>`. An object is `Some`; an absent field or JSON `null` is `None`. `build` and `full_test` remain required. Schema version 1 rejects rather than creating a compatibility path. |
| Result output | `LoopMeta.schema_version` becomes 2. Field order, status labels, integer widths, stage record shape, diagnostics, and duration semantics are unchanged. A targeted stage appears only when it executed; no `NOT_RUN` or placeholder record is emitted. |
| Acceptance ownership | `full_test` is the complete acceptance owner. `targeted_test` is only an earlier fast-fail diagnostic. The caller explicitly chooses `None`; the verifier does not infer command equivalence or coverage. |
| `Some` order | First attempt: `candidate-apply`, `build`, `targeted-test`, `full-test`. Repaired attempts retain the existing already-applied behavior. A targeted failure stops before full and owns the repair diagnostic. |
| `None` order | First attempt: `candidate-apply`, `build`, `full-test`. Repaired attempts: `build`, `full-test`. Full failure owns the repair diagnostic. No targeted command, record, allocation, or side effect exists. |
| Validation | Before patch evaluation or any mutable worktree/profile effect: schema; task ID; root; candidate patch; repair patch; optional memory path; positive timeout and iteration bound; build command; present targeted command; full command. Boundary strings are NUL-free, commands are non-empty, argv arrays are non-empty, and argv elements are NUL-free in ordinal order. Invalid input writes only the exact `INVALID`, code 2 result with zero attempts and repairs. |
| Decode and text | UTF-8 JSON decodes in one explicit arena. Malformed JSON or a structurally missing required field keeps the existing decode failure and creates no result. JSON input field order is irrelevant; output remains compact deterministic UTF-8 JSON. |
| Ownership | The decoded task stays alive in its arena through validation, all attempts, result persistence, and optional memory persistence. Borrow the task and the selected `Some` payload through the shipped Align projection surface. Do not move the option merely to select a branch, clone command/argv data, or pass full-test data as an inactive targeted placeholder. `None` carries no substitute owner. |
| Cleanup | Validation failure drops the decoded arena without process or profile work. Every executed process retains `verify.run` ownership and timeout cleanup. Captured stage owners drop once after result encoding; result persistence finishes before optional memory persistence and arena exit. |
| Failure memory | `failure_memory.remember` accepts exactly verification-result schema 2 while memory events remain schema 1. It selects the first actually emitted failure, so `full-test` may be first when targeted is absent. Invalid tasks never read or write memory. |
| Persisted/cache identity | Task and result wire identity change with schema 2. Memory-event identity does not change. No cache, interface, compiler ABI, runtime ABI, or provider protocol changes. |
| Owner modules | `verification_loop` owns decode, validation, stage selection, result encoding, and attempt transitions. `failure_memory` owns result admission and first-failure selection. `main` owns unchanged CLI routing. |
| User documentation | `README.md` and `docs/align-development.md` change with the schema. `docs/specs/roadmap.md` records the explicitly reopened and measured capability. The current C8 section 2.9 is not renamed or overwritten. |
| Prerequisite | `.align-revision` selects a shipped Align revision containing merge `3a34febe`; its managed compiler/runtime materializes and verifies before consumer evidence is accepted. |
| Correctness evidence | `verify-loop-smoke` plus its `failure-memory-smoke` alias cover schema, wire, validation, Some/None stage order, repair, failure, cleanup, and memory behavior. |
| Performance evidence | A paired fixed-task comparison removes only the redundant targeted process, projects the declared schema/stage difference, rejects every other semantic difference, and must repeatably exceed the current 2,000 ppm floor. |
| Platform scope | Platform-independent command orchestration and Align ownership. No target-local implementation or platform-specific performance claim; no native platform profile is selected by this capability alone. |

The ownership row deliberately resolves a mismatch in the abandoned prototype. The reviewed branch
ledger described moving and nulling the `Some` payload, while the compiler reproduction and source
prototype borrowed it. The re-entry implementation must use the shipped borrowed projection and
must not retain the prototype's `targeted_enabled` plus full-command placeholder argument pattern.

## 4. Closure matrix

| Cell | Required implementation | Exact regression or evidence |
| --- | --- | --- |
| Construction | Decode schema-v2 Some, absent None, and null None in one arena; retain required siblings | Three task byte goldens and whole/per-unit build |
| Some success | Run candidate/build/targeted/full in order and emit all actual stages | Exact normalized result golden and existing pass vector |
| None success | Run candidate/build/full and emit no targeted artifact or side effect | Absent/null fixtures, sentinel command, exact normalized result golden |
| Targeted failure | Stop before full; preserve existing repair, give-up, exhaustion, timeout, and spawn mappings | Existing failure matrix parameterized for Some; full-not-run sentinel |
| Full failure | Select full diagnostic and preserve repair/terminal behavior in both option states | Some and None failure/repair rows; exact prompt stage |
| Malformed input | Reject schema 1, empty required values, NUL-bearing boundary strings/argv, invalid commands, and multi-invalid pairs in ledger order | Parameterized invalid table, exact invalid golden, unchanged worktree/profile/process sentinels |
| Early exit | Candidate/build/targeted failures skip every later stage; malformed JSON creates no result; invalid semantic input creates only invalid result | Ordered stage assertions and filesystem/process sentinels |
| Loop and repair | Borrow the decoded task and optional payload across repeated attempts without move, clone, placeholder, or stale view | Two-iteration Some and None repair cases; compiler whole/per-unit execution |
| Cleanup | Drop stage/process/arena owners exactly once across pass, failure, timeout, repair, invalid, and decode error | Existing process cleanup owner plus option-state rows; no new target-local qualification |
| Result wire | Emit deterministic compact schema-v2 Some, None, and Invalid documents with only executed stages | Three result byte goldens after declared path/revision/duration normalization |
| Failure memory | Admit result v2, retain memory event v1, and choose targeted or full from actual stage presence | Existing targeted reuse plus None full-failure, wrong-schema, and invalid unchanged-profile rows |
| Documentation | Keep input examples, stage semantics, schema, roadmap status, and this ledger synchronized | Static consistency search plus `git diff --check` |
| Benchmark | Compare fresh parent/candidate binaries on the same fixed task and host; full must execute the targeted assertion | 31-pair diagnostic followed by 101-pair acceptance when stable; normalized semantic equality and improvement above floor |

Generic monomorphization, compiler-interface serialization, native ABI, provider behavior, shared
state, and runtime inspection are N/A because the changed application record is concrete and the
processes remain explicit and sequential.

## 5. Delivery sequence

1. Start a fresh branch from the then-current `origin/main`. **Complete:**
   `agent/c8-optional-targeted-stage` starts from `e15e3d3`. The evidence branch remains separate.
2. Reconfirm the fixed-task cost ceiling on the current parent. **Complete:** 326,093 ppm at
   `e15e3d3`, above the 2,000 ppm floor.
3. **Complete.** Reconcile this ledger with the current C8 retrospective and roadmap. Register the shipped
   prerequisite as Request 44 and describe Align PR #892 as historical upstream Request 21 evidence
   from the unmerged branch, not as a second current Request 21.
4. **Complete.** Update `.align-revision` to a shipped revision containing `3a34febe`, materialize the managed
   compiler/runtime, and verify their exact identities. Batch only prerequisites for this consumer.
5. **Complete.** Implement the borrowed-task shape directly on current source. Prefer `run_task(borrow task, ...)`
   and `run_attempt(borrow task, ...)` with an explicit match at the stage boundary, so Some borrows
   the real command and None has no dummy command arguments.
6. **Complete.** Add the six wire goldens named by the ledger, extend `run-verification-loop-smoke`, and update
   failure-memory, README, development documentation, roadmap, and this plan in the same capability.
7. **Complete.** Run `make fmt`, the verification/failure-memory owner, managed-toolchain verification required by
   the pin adoption, and the paired benchmark. Do not infer a broad or native platform gate from the
   pin change alone.
8. **Complete.** Perform the ledger-to-diff and matrix-to-evidence pass, then one comprehensive review of the
   stable executable candidate. Publish only if exact-head preflight and the paired performance gate
   pass with no unresolved finding.

## 6. Candidate evidence

The managed pin is exactly `3a34febe912db5096c58c74fede36ff53f223e04`.
`scripts/align-toolchain ensure compiler` built its release compiler (including the linked Align
runtime), `scripts/align-toolchain verify` returned that exact revision, and the borrowed Some/None
client passes whole and per-unit compilation. `make verify-loop-smoke` passes all six checked-in
wire documents and the validation, repair, cleanup, and memory matrix. In particular, 24 semantic
invalid rows and three decode-error rows leave the worktree, process sentinel, and profile
unchanged; Some and None both select a full-test failure for repair; and the None memory event
remains schema 1 with `failure_stage` and `failed_test` equal to `full-test`. The standalone
failure-memory schema owner rejects an otherwise-decodable verification result at schema 1 without
changing its profile, then admits the same shape at schema 2 and appends one schema-1 event.

The stable candidate binary SHA-256 is
`552790728dea091f6eaa27852bb6be945438b8580a778d0baedbe395df7225b3`; its production source was
unchanged after the build. The paired runner proved that the fixed full command executes the
targeted assertion and accepted only result schema 1→2 plus removal of the passing targeted stage.
The 31-pair diagnostic was:

```text
parent median:       44,430,809 ns
candidate median:    29,651,401 ns
improvement:            332,638 ppm (33.26%)
parent targeted:     14,581,150 ns
```

The 101-pair acceptance was:

```text
parent median:       60,515,456 ns
candidate median:    40,475,113 ns
improvement:            331,160 ppm (33.12%)
parent targeted:     19,632,536 ns
```

Both paired runs used parent binary SHA-256
`10ff55c084f35ee079f19c4b85fdc835abac0350642485d4d298d84dfffacc16`, the same temporary fixture,
alternating order, and two discarded warm-up pairs. The acceptance exceeds the 2,000 ppm shipping
floor by more than two orders of magnitude. They ran on Linux
`6.18.33.2-microsoft-standard-WSL2` x86_64 with an AMD Ryzen 9 5950X and 32 logical CPUs. The
implementation and claim are platform-independent; this environment identifies the measurement
rather than making a target-specific claim. The exact diagnostic and acceptance invocations were:

```text
scripts/run-c8-selection-signal-benchmark compare-optional-targeted /tmp/align-llm-c8-optional-parent-e15e3d3.bin /tmp/align-llm-c8-optional-candidate-uncommitted.bin 31
scripts/run-c8-selection-signal-benchmark compare-optional-targeted /tmp/align-llm-c8-optional-parent-e15e3d3.bin /tmp/align-llm-c8-optional-candidate-uncommitted.bin 101
```

For reproduction, build detached `e15e3d3` and `02c7564` worktrees through each checkout's managed
wrapper, freeze their `main` executables, verify the two SHA-256 values above, and substitute those
paths in the same commands. `02c7564` is the reviewed candidate; the observed temporary filename
predates its commit, but its recorded SHA-256 is byte-identical to the executable built from that
production source before the documentation-only review repair.

The ledger-to-diff pass maps task/result validation and ownership to `verification_loop`, schema-2
memory admission to `failure_memory`, the six wire documents and closure rows to
`run-verification-loop-smoke`, user guidance to README/development docs, prerequisite identity to
`.align-revision` and Request 44, and the performance claim to the paired runner above. No ledger
cell is deferred.

The comprehensive review covered candidate head `02c7564`, base tip and merge base
`e15e3d353abdb00b7a5051063a9db72aad076137`, with Codex `gpt-5.6-sol` at xhigh reasoning through
`codex review --base main`. Verdict: implementation and focused owner pass; one P2 documentation
finding. The finding correctly observed that the performance evidence omitted the exact command and
host/CPU environment, despite recording digests, samples, and medians. It was accepted and repaired
above; the same root-cause class was audited across the other changed performance summaries. No
implementation finding or unresolved finding remains. The documentation-only repair neither
changes approach nor materially changes behavior, so it does not trigger another comprehensive
review. Exact-head publication preflight remains.

## 7. Stop conditions

Keep the work as reference-only if any of these remains true:

- the current parent cost ceiling is below the shipping floor;
- a current full-test owner cannot demonstrate complete acceptance without the separate targeted
  process;
- schema-v2 migration cannot update every direct caller and persisted-result consumer in one
  consumer-complete capability;
- the managed Align revision containing PR #892 cannot materialize and pass the real-client owner;
- the candidate needs command cloning, an inactive placeholder command, hidden coverage inference,
  or a compatibility schema; or
- the paired benchmark does not preserve every semantic field outside the declared schema and stage
  projection or does not repeatably improve the fixed task.
