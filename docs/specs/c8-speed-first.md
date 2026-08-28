# C8 Speed-first optimization

Status: reopened for one bounded tenth consumer capability. The ninth,
`C8-SELECTION-SINGLE-GIT-QUERY`, merged as PR #120 on `main` at
`92c0979`, with a measured 10,793 ppm reduction on the fixed task (section 11). The user explicitly
prioritized `C8-OPTIONAL-TARGETED-STAGE` on 2026-08-28 after its fresh 326,093 ppm cost ceiling
and shipped Align prerequisite satisfied both section 12 re-entry conditions. The standalone ledger
is `docs/specs/c8-optional-targeted-stage.md`.
This document owns performance claims and acceptance measurements for C8 optimizations.

## 1. Metric and scope

C8 optimizes time to a passing patch, not model tokens per second or an isolated helper call. Each
capability must preserve its existing correctness contract, name the changed path, and provide a
paired fixed-task benchmark before claiming an improvement. Benchmarks are focused qualification:
they run when their owned performance path changes or during an explicit audit, not in ordinary CI
and not once per platform unless the implementation or claim is platform-specific.

The first capability, `C8-TEST-SELECTION-LINEAR`, changes only related-test ranking in
`repo_index.select_tests`. `patch_eval.evaluate` consumes that ranking before the verification loop
applies and validates a candidate, so the fixed benchmark measures the complete first-attempt
passing-patch path through `main --verify-loop`.

**The ppm-floor rule.** A performance capability records its cost ceiling — the profiled or measured
ppm share of the fixed-task total that the change can remove — in the ledger's optimization row
before implementation. A seam whose ceiling is below the shipping floor is recorded in the deferred-
surfaces section instead of being implemented; a measured result far below its recorded ceiling is
reported as a ceiling-estimation miss, not only as a rejected candidate.

The shipping floor for C8 is **2,000 ppm on the fixed task**. It is calibrated from this wave's own
measured spread rather than chosen in advance.

Below the floor: the `agent/c8-move-process-argv` candidate measured 283 ppm over 201 pairs and
regressed over 31 pairs. It was rejected without a pull request, and because its ceiling had never
been estimated, the paired benchmark was the first and only signal that the seam was too small — the
measurement cost the whole diagnosis. Two capabilities did ship below the floor, the third at
1,941 ppm (section 5) and the sixth at 1,808 ppm (section 8). The rule is forward-looking and does
not retract them, but a ceiling recorded before implementation would have deferred both, and that is
the point: each still paid the full paired-benchmark cost to establish a fifth of a percent.

Above the floor: the eighth capability shipped at 3,913 ppm (section 10) and the ninth at
10,793 ppm (section 11). The ninth's recorded ceiling — the roughly 1.2 ms `rev-parse` spawn out of
the ~46 ms fixed-task total, about 26,000 ppm — was more than twice its measured result. That is a
ceiling-estimation miss, and the rule requires it to be reported as one rather than being quietly
absorbed into a passing claim.

The floor therefore sits an order of magnitude above the rejected candidate and just above the two
smallest shipped results, which is the band where the cost of measuring exceeded the value of the
result.

## 2. Capability ledgers

### 2.1 Linear related-test ranking

| Field | Contract |
| --- | --- |
| Consumer | `patch_eval.evaluate` and the C4 verification loop |
| Input | Git root, changed path, and timeout already accepted by `repo_index.select_tests` |
| Output | Existing schema-1 selection document; candidate path, score, reason, order, counts, status, and errors are unchanged |
| Ranking | Basename match contributes 100 and same-directory match contributes 20; the only possible scores are 120, 100, 20, and 0 |
| Ordering | Descending score; within one score, preserve the NUL-delimited `git ls-files` order |
| Ownership/allocation | Four function-local builders own the four score buckets; the final builder concatenates them in rank order and no cache survives the call |
| Failure behavior | The existing `rev-parse` then `ls-files` validation order and exact failure documents remain unchanged |
| Optimization | Replace 121 complete tracked-file scans with one scan and four deterministic buckets: `O(121N)` becomes `O(N)` for `N` tracked paths |
| Correctness owner | `scripts/run-test-selection-smoke`, covering all four buckets and their exact order; `scripts/run-patch-eval-smoke` and `scripts/run-verification-loop-smoke` cover both consumers |
| Performance owner | `scripts/run-c8-test-selection-benchmark PARENT_BINARY CANDIDATE_BINARY [SAMPLES]` |
| Platform scope | Platform-independent Align and Git path processing; no target-local implementation or platform-specific speed claim |

Changing either score weight must update the bucket set and the four-bucket owner in the same
capability. An unrecognized score cannot arise from the current formula; the lowest bucket is the
explicit zero-score case, not a general sorting fallback.

### 2.2 Compute related-test signals once

`C8-TEST-SELECTION-SIGNALS-ONCE` is the second consumer-complete capability. The linear
selector currently evaluates basename and directory equality once to compute the score and again
to compute the reason for every test candidate. The optimization computes the two booleans once per
candidate and derives both existing fields from them.

| Field | Contract |
| --- | --- |
| Consumer | `repo_index.select_tests`, `patch_eval.evaluate`, and the C4 verification loop |
| Input and output | The existing root, changed path, timeout, schema-1 selection document, patch-evaluation document, verification result, status, counts, candidate bytes, and order are unchanged |
| Changed boundary | Only the function-local computation of basename-match and same-directory signals for one already-classified test path |
| Ownership/allocation | Both booleans are non-owning scalar locals; builders, strings, subprocesses, and persisted artifacts are unchanged |
| Failure behavior | Existing `rev-parse` then `ls-files` order, timeout handling, error documents, and no-repository behavior are unchanged |
| Correctness owner | `scripts/run-test-selection-smoke`, with `scripts/run-patch-eval-smoke` and `scripts/run-verification-loop-smoke` covering both downstream consumers |
| Performance owner | `scripts/run-c8-selection-signal-benchmark baseline BINARY [SAMPLES]` before implementation and `scripts/run-c8-selection-signal-benchmark compare PARENT_BINARY CANDIDATE_BINARY [SAMPLES]` after implementation |
| Acceptance | On the fixed coding task, the candidate median time to a first-attempt passing patch is lower; normalized result documents match and all five real stage commands pass |
| Platform scope | Platform-independent Align path/string computation; no target-local implementation or platform-specific speed claim |

No memoization or persisted cache is introduced. A future change to either signal must update the
single computation and the existing four-bucket owner rather than restoring separate score/reason
paths.

### 2.3 Compute changed-path components once

`C8-TEST-SELECTION-CHANGED-PATH-ONCE` is the third consumer-complete capability. After the second
capability, the selector still derives the unchanged changed path's stem and directory once for
every test candidate. The optimization derives both components once before the tracked-file loop;
each candidate continues to derive its own stem and directory exactly once.

| Field | Contract |
| --- | --- |
| Consumer | `repo_index.select_tests`, `patch_eval.evaluate`, and the C4 verification loop |
| Input and output | The existing root, changed path, timeout, schema-1 selection document, patch-evaluation document, verification result, status, counts, candidate bytes, and order are unchanged |
| Changed boundary | Only function-local derivation of the changed path's stem and directory moves before the existing tracked-file loop |
| Ownership/allocation | Two function-local `str` views borrow the changed stem and directory from `changed_path`; they allocate nothing, remain valid for the `select_tests` call, and do not escape it |
| Failure behavior | Existing `rev-parse` then `ls-files` order, timeout handling, error documents, and no-repository behavior are unchanged |
| Correctness owner | `scripts/run-test-selection-smoke`, with `scripts/run-patch-eval-smoke` and `scripts/run-verification-loop-smoke` covering both downstream consumers |
| Performance owner | `scripts/run-c8-selection-signal-benchmark baseline BINARY [SAMPLES]` before implementation and `scripts/run-c8-selection-signal-benchmark compare PARENT_BINARY CANDIDATE_BINARY [SAMPLES]` after implementation |
| Acceptance | On the fixed coding task, the candidate median time to a first-attempt passing patch is lower; normalized result documents match and all five real stage commands pass |
| Platform scope | Platform-independent Align path/string computation; no target-local implementation or platform-specific speed claim |

This capability does not cache per-test data, change the ranking formula, or combine path parsing
with JSON construction. Those remain separate boundaries if later end-to-end measurement justifies
them.

### 2.4 Prefer related recommendations over generic fallback

`C8-TEST-SELECTION-RELATED-ONLY` is the fourth consumer-complete capability. The selector currently
publishes every recognized test path even when one or more candidates have a positive basename or
directory relationship. The optimization publishes the positive-score buckets when any is
non-empty and publishes the zero-score bucket only when no positive candidate exists.

| Field | Contract |
| --- | --- |
| Consumer | The `--select-tests` CLI, `patch_eval.evaluate`, the C4 verification loop, and failure-memory consumers of recommended tests |
| Input and schema | Root, changed path, timeout, schema version, field order, field types, statuses, and errors are unchanged |
| Related case | When the combined 120, 100, and 20 buckets contain at least one candidate, emit exactly those candidates and omit every score-0 generic candidate |
| Fallback case | When all positive buckets are empty, emit every score-0 candidate so repositories without a path signal retain deterministic fallback recommendations |
| Count and ordering | `candidate_count` and downstream `recommended_test_count` count only emitted candidates; descending score and Git order within each emitted bucket are unchanged |
| Ownership/allocation | The same four function-local builders own candidate bytes; omitted generic bytes never enter the final selection, patch-evaluation, verification, or failure-memory documents, and no cache is introduced |
| Failure behavior | Existing `rev-parse` then `ls-files` order, timeout handling, error documents, and no-repository behavior are unchanged |
| Correctness owner | `scripts/run-test-selection-smoke` covers mixed related/generic input and generic-only fallback; `scripts/run-patch-eval-smoke` covers the direct downstream document; `scripts/run-verification-loop-smoke` asserts the exact filtered evaluation list and the existing string-encoded recommendation payload in both persisted failure memory and reused memory context |
| Performance owner | `scripts/run-c8-selection-signal-benchmark baseline BINARY [SAMPLES]` before implementation and `scripts/run-c8-selection-signal-benchmark compare-related-only PARENT_BINARY CANDIDATE_BINARY [SAMPLES]` after implementation |
| Acceptance | On the fixed coding task, the candidate emits only the exact related test, the parent retains all 4,000 candidates, all other normalized result fields agree, the exact five-stage vector appears in execution order with every stage passing its expected exit code, and candidate median time to a passing patch is lower |
| Platform scope | Platform-independent selection and JSON/context reduction; no target-local implementation or platform-specific speed claim |

This is not a fixed numeric cap. Every positive relationship remains visible, and generic tests
remain the one fallback when path ranking has no information. The full-test verification stage is
unchanged and still owns broad regression coverage after targeted recommendations run.

### 2.5 Defer generic recommendation serialization

`C8-TEST-SELECTION-DEFER-GENERIC` is the fifth consumer-complete capability. After the fourth
capability, the selector omits generic candidates from related output but still JSON-encodes every
generic candidate into a builder before discarding that complete body. The optimization records
only source offsets for generic paths during classification and serializes them after traversal only
when no positive candidate exists.

| Field | Contract |
| --- | --- |
| Consumer | `repo_index.select_tests`, `patch_eval.evaluate`, the C4 verification loop, and failure-memory consumers of recommended tests |
| Input and output | Root, changed path, timeout, schemas, field order, statuses, errors, candidate paths/scores/reasons/counts, ranking order, and related-only/fallback behavior are unchanged |
| Changed boundary | A score-0 candidate records its start/end offsets into the already-owned NUL-delimited Git listing during the one classification pass; positive candidates retain immediate bucket serialization |
| Fallback | If no positive candidate exists, traverse the recorded offsets in Git order and serialize every generic candidate exactly once; if any positive candidate exists, drop the offsets without constructing generic JSON |
| Ownership/allocation | A function-local `array_builder<TestPathOffset>` owns fixed-width copied offsets, never borrowed path views; `files_run.stdout` owns the referenced bytes through fallback rendering; the builder and its buffer are dropped before return and no cache survives the call |
| Failure behavior | Existing `rev-parse` then `ls-files` order, timeout handling, error documents, and no-repository behavior are unchanged; deferred work occurs only after both Git commands succeed |
| Correctness owner | `scripts/run-test-selection-smoke` proves exact mixed related/generic and generic-only fallback documents; `scripts/run-patch-eval-smoke` and `scripts/run-verification-loop-smoke` cover downstream documents and failure-memory propagation |
| Performance owner | `scripts/run-c8-selection-signal-benchmark baseline BINARY [SAMPLES]` before implementation and `scripts/run-c8-selection-signal-benchmark compare PARENT_BINARY CANDIDATE_BINARY [SAMPLES]` after implementation |
| Acceptance | On the fixed coding task, normalized result documents are identical, the exact ordered five-stage vector passes with matching exit codes, and candidate median time to a passing patch is lower |
| Platform scope | Platform-independent selection allocation and JSON construction; no target-local implementation or platform-specific speed claim |

The offset record is an internal traversal checkpoint, not persisted state. It cannot outlive the
Git listing it indexes, and it does not change the full-test stage that follows targeted tests.

### 2.6 Rescan the generic fallback without retaining offsets

`C8-TEST-SELECTION-RESCAN-FALLBACK` is the sixth consumer-complete capability. After the fifth
capability, related selection avoids generic JSON but still allocates, fills, finalizes, and drops an
offset array for every generic test. The optimization omits that array. It scans the already-owned
Git listing a second time only when the first pass finds no positive candidate.

| Field | Contract |
| --- | --- |
| Consumer | `repo_index.select_tests`, `patch_eval.evaluate`, the C4 verification loop, and failure-memory consumers of recommended tests |
| Input and output | Root, changed path, timeout, schemas, field order, statuses, errors, candidate paths/scores/reasons/counts, ranking order, and related-only/fallback behavior are unchanged |
| Changed boundary | The first classification pass serializes positive candidates and discards score-0 candidates without retaining offsets; if the positive count is zero, a second pass parses the same NUL-delimited listing and serializes every recognized test as the generic fallback |
| Fallback | The second pass applies the unchanged `is_test_path` predicate, emits each generic candidate exactly once in Git order, and does not recompute basename or directory signals |
| Ownership/allocation | `files_run.stdout` owns the listing through both function-local passes; no borrowed path view escapes, no generic offset builder or array is allocated, and no cache survives the call |
| Failure behavior | Existing `rev-parse` then `ls-files` order, timeout handling, error documents, and no-repository behavior are unchanged; the fallback rescan occurs only after both Git commands succeed and the first pass finds no positive candidate |
| Cost boundary | Related selection removes `O(G)` fixed-width offset writes and storage for `G` generic tests; no-signal fallback adds one `O(N)` listing parse without path scoring for `N` tracked paths. This capability makes no fallback-speed claim |
| Correctness owner | `scripts/run-test-selection-smoke` proves exact mixed related/generic and generic-only fallback documents; `scripts/run-patch-eval-smoke` and `scripts/run-verification-loop-smoke` cover downstream documents and failure-memory propagation |
| Performance owner | `scripts/run-c8-selection-signal-benchmark baseline BINARY [SAMPLES]` before implementation and `scripts/run-c8-selection-signal-benchmark compare PARENT_BINARY CANDIDATE_BINARY [SAMPLES]` after implementation |
| Acceptance | On the fixed related-selection coding task, normalized result documents are identical, the exact ordered five-stage vector passes with matching exit codes, and candidate median time to a passing patch is lower |
| Platform scope | Platform-independent selection allocation and Git-listing traversal; no target-local implementation or platform-specific speed claim |

The second scan is deliberately conditional rather than a second classification pass: it does not
derive path signals, change score semantics, or allocate a retained candidate index. Repositories
without a positive path signal keep the complete deterministic fallback at the explicitly recorded
extra traversal cost.

### 2.7 Validate and apply each patch atomically once

`C8-ATOMIC-PATCH-APPLY` is the seventh consumer-complete capability. The verification loop currently
runs `git apply --check --recount` and then starts a second `git apply --recount` process for every
candidate and repair patch. Git's normal no-`--reject` application is whole-patch atomic on an
applicability failure, and `--check --apply` requests validation plus application in one invocation.
The optimization replaces each check/apply pair with that one atomic command.

| Field | Contract |
| --- | --- |
| Consumer | The C4 verification loop, repair prompts, persisted result documents, and failure-memory consumers of their stage arrays |
| Command | Candidate and repair application each run `git apply --check --apply --recount PATCH` once in the task root with the existing timeout |
| Successful candidate stages | `candidate-apply`, `build`, `targeted-test`, `full-test` in that exact order; the removed `candidate-apply-check` record is not synthesized |
| Failed candidate application | Emit one failed `candidate-apply` record and prompt; do not run build or tests, and do not change any path when Git rejects an inapplicable multi-file patch |
| Repair stages | After the failed validation stage, emit one `repair-apply` record. Success returns `REPAIRING`; failure returns `REPAIR_FAILED` with that invocation's exact status, code, summary, stdout, and stderr. The removed `repair-apply-check` and `NOT_RUN` state are not synthesized |
| Existing behavior | Task input, patch bytes, `--recount`, root, timeout, expected code 0, build/test ordering, repair budget, terminal loop status, and every non-application record remain unchanged |
| Atomicity and safety | No `--reject` or `--unsafe-paths` is used. An applicability failure rejects the whole patch without modifying the working tree; the owner includes a multi-file negative control with an earlier valid hunk and a later invalid hunk |
| Timeout and spawn failure | Existing `verify.run` handling and diagnostics remain unchanged. This capability makes no stronger cleanup claim for an externally killed Git process than the previous apply invocation |
| Correctness owner | `scripts/run-verification-loop-smoke` covers valid candidate/repair application, exact stage order, invalid repair, invalid multi-file candidate atomicity, prompt stage naming, and unchanged downstream result/failure-memory behavior |
| Performance owner | `scripts/run-c8-selection-signal-benchmark baseline BINARY [SAMPLES]` before implementation and `scripts/run-c8-selection-signal-benchmark compare-atomic-apply PARENT_BINARY CANDIDATE_BINARY [SAMPLES]` after implementation |
| Acceptance | On the fixed coding task, result documents agree after removing only the parent's successful `candidate-apply-check` record and normalizing durations; the candidate has the exact four-stage order, every retained stage passes with matching exit codes, and candidate median time to a passing patch is lower |
| Platform scope | Platform-independent Git command orchestration and document construction; no target-local implementation or platform-specific speed claim |

The authoritative contract is the [Git apply documentation](https://git-scm.com/docs/git-apply):
without `--reject`, an applicability failure is atomic, and `--apply` after `--check` performs the
application. The single invocation also removes the check-to-apply process gap rather than caching
an earlier verdict.

### 2.8 Move completed result documents into their owners

`C8-MOVE-RESULT-DOCUMENTS` is the eighth consumer-complete capability. The repository selection,
patch evaluation, stage, attempt, and verification layers currently clone locally completed owned
JSON strings when returning them in their sole owning result record. The optimization moves each
completed string into that record after its last local read instead of allocating and copying an
identical second buffer.

| Field | Contract |
| --- | --- |
| Consumers | Repository index and test selection, patch evaluation, the C4 verification loop, repair prompts, persisted results, and failure-memory consumers |
| Input and output | Schemas, field order and bytes, statuses, counts, recommendations, stage order, prompts, diagnostics, durations, failure precedence, and CLI files are unchanged |
| Moved values | Only a function-local owned `string` whose next and sole owner is the returned result record; borrowed views finish before the move and no source is read afterward |
| Retained copies | Process-output views still clone once into owned stage data; JSON encoders whose result is a region-bound view still clone once; reusable task/profile data and any value with multiple consumers are unchanged |
| Ownership/allocation | Each moved buffer has exactly one owner before and after the change; the capability removes redundant terminal allocations and introduces no cache, alias, or shared mutable state |
| Failure behavior | Existing Git validation order, patch-analysis failure, command timeout/spawn mapping, repair transitions, terminal status, and persisted failure behavior are unchanged |
| Correctness owner | `index-smoke`, `test-selection-smoke`, `patch-eval-smoke`, and `verify-loop-smoke` cover the moved records and their downstream persistence; `loop-smoke` covers the unchanged lower verification primitive |
| Performance owner | `scripts/run-c8-selection-signal-benchmark baseline-atomic BINARY [SAMPLES]` before implementation and `scripts/run-c8-selection-signal-benchmark compare-atomic PARENT_BINARY CANDIDATE_BINARY [SAMPLES]` after implementation |
| Acceptance | On the fixed coding task, normalized result documents and the exact ordered four-stage vector agree, every stage passes with matching exit codes, and candidate median time to a passing patch is repeatably lower |
| Platform scope | Platform-independent Align ownership and JSON result construction; no target-local implementation or platform-specific speed claim |

The capability does not remove a copy merely because two values contain equal bytes. Every removed
clone is a terminal handoff from a local owner to one returned owner, which keeps the ownership
proof mechanical.

### 2.9 Query Git once for evaluation-side test selection

`C8-SELECTION-SINGLE-GIT-QUERY` is the ninth consumer-complete capability. `repo_index.select_tests`
spawns `git rev-parse --verify HEAD` and then `git ls-files -z` on every call. The
`--select-tests` CLI publishes the resulting `revision` field, but `patch_eval.evaluate` consumes
only the candidates array, `candidate_count`, and `status`, and discards the selection document
itself. The optimization splits the selector into a shared tracked-listing core, the existing
revision-bearing CLI entry, and a revision-free evaluation entry that runs only the one Git query
whose output it consumes.

| Field | Contract |
| --- | --- |
| Consumers | `patch_eval.evaluate`, the C4 verification loop, repair prompts, persisted results, and failure-memory consumers of recommended tests. `main --select-tests` keeps the revision-bearing entry |
| Surfaces | `repo_index.select_tests(root, changed_path, timeout_ns) -> TestSelection` is unchanged. `repo_index.select_tests_for_evaluation(root, changed_path, timeout_ns) -> TestSelection` is new. Both delegate to the private `select_tracked_tests(root, changed_path, timeout_ns, revision) -> TestSelection` |
| Owner module | `src/repo_index.align` owns all three; `src/patch_eval.align` owns the single changed call site |
| Input | Root, changed path, and timeout are unchanged for both entries |
| Output | `select_tests` returns the same schema-1 selection document byte for byte, `revision` included. `select_tests_for_evaluation` renders the same schema with an empty `revision`; `patch_eval.evaluate` reads only the candidates array, `candidate_count`, and `status`, so for a repository with a committed HEAD every published patch-evaluation, verification, prompt, persisted-result, and failure-memory byte is unchanged. The Unborn-HEAD contract row below is the one deliberate exception |
| Persisted/cache identity | None. No selection document, revision, or listing is cached, memoized, or persisted between calls; the evaluation entry's document is a function-local value the caller never writes to disk |
| Schema version | Selection schema stays 1 and patch-evaluation schema stays 1; no field is added, removed, reordered, or retyped |
| Validation order | CLI: `rev-parse --verify HEAD`, then `ls-files -z`, unchanged. Evaluation: `ls-files -z` alone, the single query that produces the consumed data |
| Unborn-HEAD contract | Deliberately changed on the evaluation path only. `git rev-parse --verify HEAD` exits 128 in a repository with no commits, while `git ls-files -z` exits 0 and lists the index. The evaluation entry therefore reports `ok` with the real index-derived candidates — zero when the index is empty — instead of the previous `error`/`error_code` 2 patch evaluation and `Invalid` verification result. Validating a revision the path never reads in order to reject a repository whose tracked listing is available is neither honest nor useful, so the contract is now "the evaluation path validates exactly what it consumes". `--select-tests` still fails at `rev-parse` for an unborn HEAD because it publishes `revision` |
| Non-repository behavior | Unchanged and verified, not assumed: `git ls-files -z` exits 128 outside a work tree, so the evaluation entry still returns `IndexStatus.Failed`, `error_code` 128 in the selection document, `error_code` 2 in the patch evaluation, and a nonzero CLI exit |
| Failure behavior | `ls-files` nonzero exit still maps through `process_succeeded` to the existing failure document with that invocation's code, and the non-repository regressions below own it. The `ls-files` timeout and spawn-failure sub-paths are unchanged code inside the moved-but-unedited `select_tracked_tests` body and gain no new regression: N/A, because the capability adds no timeout or spawn behavior and reaching either deterministically needs a process-level fault injector this repository does not ship. The `rev-parse` failure document, its `error_code`, and its status are unchanged on the CLI path |
| Ownership/allocation | The CLI entry owns the trimmed revision `string` for the whole shared call and passes it directly, so it auto-borrows at the core's `str` parameter and the view never outlives the owner; the evaluation entry passes the empty literal. The shared core owns the Git listing, the four bucket builders, and the rendered document exactly as before. No allocation is added and no alias, cache, or shared mutable state is introduced |
| Optimization | Removes one process spawn, wait, and output capture per patch evaluation — roughly 1.2 ms of the section 10 fixed-task total of about 46 ms, or about 26,000 ppm of unconsumed work |
| Prerequisites | None beyond the merged eighth capability; the shipped Align pin already provides everything used |
| Correctness owner | `scripts/run-test-selection-smoke` for the unchanged CLI document — its `revision`, its four-bucket order, its generic fallback, its non-repository failure, and the new unborn-HEAD CLI failure; `scripts/run-patch-eval-smoke` for the evaluation entry's normal, unborn-HEAD, and non-repository cases; `scripts/run-verification-loop-smoke` for the unchanged downstream consumers and its new `verification-loop-unborn-head` case; `scripts/run-index-smoke` for the unchanged `repo_index.build` |
| Performance owner | `scripts/run-c8-selection-signal-benchmark baseline-atomic BINARY [SAMPLES]` before implementation and `scripts/run-c8-selection-signal-benchmark compare-atomic PARENT_BINARY CANDIDATE_BINARY [SAMPLES]` after implementation |
| Acceptance evidence | Section 11. On the fixed coding task, normalized result documents and the exact ordered four-stage vector agree, every stage passes with matching actual and expected codes, and the candidate median time to a passing patch is repeatably lower |
| Metrics | Primary: median time to a passing patch on the section 4 fixed coding task. Secondary: one fewer Git child process per patch evaluation |
| Platform scope | Platform-independent Git command orchestration and document construction; no target-local implementation and no platform-specific speed claim |

#### 2.9.1 Closure matrix

Every applicable cell names its implementation and the exact regression that owns it.

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `select_tracked_tests` runs one `git ls-files -z` and builds the four score buckets, the candidates array, and the schema-1 document; `select_tests` constructs the revision first, `select_tests_for_evaluation` constructs none | `scripts/run-test-selection-smoke` four-bucket ordering case; `scripts/run-patch-eval-smoke` `recommended_tests` case |
| Success | CLI document keeps `revision` and every other byte; evaluation document carries an empty `revision` and identical consumed fields | `scripts/run-test-selection-smoke` `selection["revision"] == git rev-parse HEAD`; `scripts/run-patch-eval-smoke` `recommended_test_count == 1` with the exact `recommended_tests` array |
| Failure | `ls-files` nonzero exit returns `IndexStatus.Failed` with that code from either entry; `rev-parse` failure still returns it from the CLI entry only. The `ls-files` timeout and spawn-failure sub-paths take the same unchanged `process_succeeded` branch and are not separately covered | `scripts/run-patch-eval-smoke` non-repository case (`status == "error"`, `error_code == 2`, nonzero exit); `scripts/run-test-selection-smoke` non-repository case (`error_code == 128`) and unborn-HEAD CLI case (`error_code == 128`). Timeout and spawn failure: N/A — unchanged code paths with no behavior change, and no shipped fault injector can reach them deterministically |
| Malformed input | An untracked or unrelated changed path yields the generic fallback or an empty candidate set rather than an error; an unreadable patch still fails in `patch_eval.evaluate` before any selection | `scripts/run-test-selection-smoke` zero-score generic fallback case; `scripts/run-patch-eval-smoke` missing-patch case |
| Early exit | `patch_eval.evaluate` returns `failed_evaluation` for an unreadable patch, a segment with no path, and a zero-file patch before reaching selection, so no Git child starts on those paths; `primary_path.len() == 0` still skips selection entirely | `scripts/run-patch-eval-smoke` missing-patch case asserting `recommended_tests == []` |
| Cleanup | `verify.run` still owns each Git child's spawn, wait, and stream capture; the capability removes one child rather than adding one, and adds no descriptor, temporary file, or persisted artifact | `scripts/run-verification-loop-smoke` unchanged four-stage vector; `scripts/run-patch-eval-smoke` |
| Module `repo_index` | Three-function split: unchanged public `select_tests`, new public `select_tests_for_evaluation`, private shared `select_tracked_tests`; `build` is untouched | `scripts/run-test-selection-smoke`, `scripts/run-patch-eval-smoke`, `scripts/run-index-smoke` |
| Module `patch_eval` | One call site moves from `repo_index.select_tests` to `repo_index.select_tests_for_evaluation`; document construction, status mapping, and `extract_candidates` are unchanged | `scripts/run-patch-eval-smoke` |
| Module `verification_loop` | No source change. It consumes `patch_eval.evaluate`'s status and document, so the unborn-HEAD status change reaches it as a now-runnable task rather than an `Invalid` result | `scripts/run-verification-loop-smoke` unchanged four-stage vector for the committed-HEAD cases, plus its `verification-loop-unborn-head` case: a repository with a populated index and no commit (asserted unborn through a failing `git rev-parse --verify HEAD`) now reports `status` `PASS`, `evaluation_status` `ok`, the exact `basename-match` recommendation, and both real stage vectors (`candidate-apply`/`build`/`targeted-test`/`repair-apply`, then `build`/`targeted-test`/`full-test`) instead of `Invalid` with code 2 |
| Module `main` | No source change. `--select-tests` keeps `repo_index.select_tests` and its exact output and exit codes | `scripts/run-test-selection-smoke` |

The two entries must not be allowed to drift into separate ranking implementations: any future change
to bucket weights, ordering, or the generic fallback belongs in `select_tracked_tests` alone. Adding
a consumer that needs the revision means calling `select_tests`, not reintroducing `rev-parse` into
the shared core.

### 2.10 Make the targeted stage explicitly optional

`C8-OPTIONAL-TARGETED-STAGE` is the one explicitly reopened tenth capability. It changes verification
task and result schema from version 1 to version 2 and makes `targeted_test` optional while retaining
`full_test` as the complete acceptance owner. Its public-contract ledger, closure matrix, evidence
inventory, stop conditions, and paired benchmark contract are authoritative in
[`c8-optional-targeted-stage.md`](c8-optional-targeted-stage.md). This section intentionally does not
duplicate that contract. The stable candidate's 101-pair acceptance improved the fixed task from
60,515,456 ns to 40,475,113 ns, or 331,160 ppm (33.12%); the runner projected only the result schema
change and removal of the passing targeted stage, while full-test executed the targeted assertion.

## 3. Fixed passing-patch benchmark

The benchmark creates one temporary Git repository with `src/value.py` and 4,000 tracked generic
test files. Its candidate patch changes the function from `return 0` to `return 1`. Build, targeted,
and full-test stages use `/usr/bin/true`, isolating repository analysis while still requiring the
normal candidate apply-check, apply, build, targeted-test, and full-test sequence to finish with
`PASS` in one iteration. Repository setup and `git reset --hard HEAD` happen outside the timed
region.

Parent and candidate run in alternating order for each pair. Two pairs warm the binaries and are
discarded. The runner normalizes only per-stage `duration_ns` and requires every other result value
in the decoded document to agree. It rejects identical binary SHA-256 digests and fails if the
candidate median is not lower.

Reproduce both binaries from detached worktrees so the runner inputs are bound to the recorded
commits. The two commits select the same `.align-revision`:

```text
git worktree add --detach /tmp/align-llm-c8-parent ab155b391cfe12a2d53674179b993fc43fa86120
git worktree add --detach /tmp/align-llm-c8-candidate be5291ef79d9f7a9102d91d86afb7880fc5c7182
make -C /tmp/align-llm-c8-parent build
make -C /tmp/align-llm-c8-candidate build
install -m 0755 /tmp/align-llm-c8-parent/main /tmp/align-llm-c8-parent.bin
install -m 0755 /tmp/align-llm-c8-candidate/main /tmp/align-llm-c8-candidate.bin
sha256sum /tmp/align-llm-c8-parent.bin /tmp/align-llm-c8-candidate.bin
/tmp/align-llm-c8-candidate/scripts/run-c8-test-selection-benchmark \
  /tmp/align-llm-c8-parent.bin /tmp/align-llm-c8-candidate.bin 15
```

The implementation measurement used:

```text
parent:    ab155b391cfe12a2d53674179b993fc43fa86120
candidate: be5291ef79d9f7a9102d91d86afb7880fc5c7182
parent binary SHA-256:    d43b4a87c6282b1b68d4eefe62e3856d94228f27189a088fd4a7bb585dc89520
candidate binary SHA-256: 9c71f3d55d1335a74723c2933c2091945db6a8a827d95ce08739c1ce35ba3561
command:   /tmp/align-llm-c8-candidate/scripts/run-c8-test-selection-benchmark /tmp/align-llm-c8-parent.bin /tmp/align-llm-c8-candidate.bin 15
host:      Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:       AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:   15 parent and 15 candidate measurements after warmup
parent median:    48,829,180 ns
candidate median: 12,465,365 ns
improvement:      744,714 ppm (74.5%)
```

Both binaries were built with the repository's normal `make build` command and the same managed
Align pin. This evidence closes the C8 gate for this capability only; it does not claim that every
repository or the model/provider phase improves by 74.5%.

## 4. Second fixed coding-task baseline

The second benchmark retains 4,000 tracked test candidates but replaces the three `/usr/bin/true`
stages with a real Python source compile, a targeted assertion, and a full assertion that first runs
the targeted test and then checks an independent property. The candidate changes `src/value.py`
from returning zero to returning one. Repository creation, reset, and removal of the preceding
result document remain outside the timed region; every invocation must create a new result.
Baseline and compare modes discard two warmup pairs, use an odd sample count of at least five, and
require every normalized result document to agree. Compare mode additionally rejects identical
binary SHA-256 digests and a non-improving candidate median.

The pre-implementation baseline is:

```text
commit:     4ed50d237e65e164818b3060fe11312296685ec3
binary SHA-256: 9c71f3d55d1335a74723c2933c2091945db6a8a827d95ce08739c1ce35ba3561
command:    scripts/run-c8-selection-signal-benchmark baseline ./main 15
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    15 measurements after two discarded warmup runs
median:     49,910,961 ns
candidate-apply-check median: 1,303,719 ns
candidate-apply median:       1,200,812 ns
build median:                 9,331,491 ns
targeted-test median:        14,732,039 ns
full-test median:            14,887,075 ns
```

The stage medians are diagnostic decomposition, not separate acceptance claims. Only the total
time-to-passing-patch median decides the capability gate.

The exact-commit comparison used:

```text
git worktree add --detach /tmp/align-llm-c8-signals-parent 4ed50d237e65e164818b3060fe11312296685ec3
git worktree add --detach /tmp/align-llm-c8-signals-candidate eaed3e03aac7d07c68851bfb7c684dce959f4ba0
make -C /tmp/align-llm-c8-signals-parent build
make -C /tmp/align-llm-c8-signals-candidate build
install -m 0755 /tmp/align-llm-c8-signals-parent/main /tmp/align-llm-c8-signals-parent.bin
install -m 0755 /tmp/align-llm-c8-signals-candidate/main /tmp/align-llm-c8-signals-candidate.bin
git cat-file blob 980aed5351e1d06acd212ff851104a542eb7ee9e > /tmp/align-llm-c8-signals-benchmark
chmod 0755 /tmp/align-llm-c8-signals-benchmark
sha256sum /tmp/align-llm-c8-signals-parent.bin /tmp/align-llm-c8-signals-candidate.bin
/tmp/align-llm-c8-signals-benchmark compare \
  /tmp/align-llm-c8-signals-parent.bin /tmp/align-llm-c8-signals-candidate.bin 101
```

```text
parent:     4ed50d237e65e164818b3060fe11312296685ec3
candidate:  eaed3e03aac7d07c68851bfb7c684dce959f4ba0
benchmark runner Git blob: 980aed5351e1d06acd212ff851104a542eb7ee9e
benchmark runner SHA-256: 08d2e17ee669bf3095359753a12055530d90d6fde7162d1123bf0694f90e3de5
parent binary SHA-256:    9c71f3d55d1335a74723c2933c2091945db6a8a827d95ce08739c1ce35ba3561
candidate binary SHA-256: 04202b4945c757c2f06f409502ec9c6bb0ad60b685b7846656eab233578cdc17
command:    /tmp/align-llm-c8-signals-benchmark compare /tmp/align-llm-c8-signals-parent.bin /tmp/align-llm-c8-signals-candidate.bin 101
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    101 parent and 101 candidate measurements after two discarded warmup pairs
parent median:    49,926,004 ns
candidate median: 49,650,937 ns
improvement:      5,509 ppm (0.55%)
```

All normalized result documents agreed. The measured reduction is deliberately reported as a
small path-local improvement; it is not generalized to repositories with fewer candidates or to
provider/model time.

## 5. Third fixed coding-task baseline

The third capability reuses the real-stage benchmark and correctness rules from Section 4 without
changing its fixture or timed region. The pre-implementation baseline is:

```text
commit:     a51aa065a2f83f4e88d7734068c6b2598b4bd3a8
binary SHA-256: 04202b4945c757c2f06f409502ec9c6bb0ad60b685b7846656eab233578cdc17
command:    scripts/run-c8-selection-signal-benchmark baseline /tmp/align-llm-c8-path.3OVLZg/parent-a51aa06.bin 31
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    31 measurements after two discarded warmup runs
median:     49,875,826 ns
candidate-apply-check median: 1,300,373 ns
candidate-apply median:       1,174,545 ns
build median:                 9,474,076 ns
targeted-test median:        14,706,220 ns
full-test median:            14,985,312 ns
```

The stage medians are diagnostic decomposition. Only a lower paired total median with identical
normalized result documents can close the third capability.

The exact-commit comparison used:

```text
git worktree add --detach /tmp/align-llm-c8-path-parent a51aa065a2f83f4e88d7734068c6b2598b4bd3a8
git worktree add --detach /tmp/align-llm-c8-path-candidate ab23de1c4fc3bef454b51a4e5c7db8f019a81a72
make -C /tmp/align-llm-c8-path-parent build
make -C /tmp/align-llm-c8-path-candidate build
install -m 0755 /tmp/align-llm-c8-path-parent/main /tmp/align-llm-c8-path-parent.bin
install -m 0755 /tmp/align-llm-c8-path-candidate/main /tmp/align-llm-c8-path-candidate.bin
git cat-file blob 980aed5351e1d06acd212ff851104a542eb7ee9e > /tmp/align-llm-c8-path-benchmark
chmod 0755 /tmp/align-llm-c8-path-benchmark
sha256sum /tmp/align-llm-c8-path-parent.bin /tmp/align-llm-c8-path-candidate.bin
/tmp/align-llm-c8-path-benchmark compare \
  /tmp/align-llm-c8-path-parent.bin /tmp/align-llm-c8-path-candidate.bin 201
```

```text
parent:     a51aa065a2f83f4e88d7734068c6b2598b4bd3a8
candidate:  ab23de1c4fc3bef454b51a4e5c7db8f019a81a72
benchmark runner Git blob: 980aed5351e1d06acd212ff851104a542eb7ee9e
benchmark runner SHA-256: 08d2e17ee669bf3095359753a12055530d90d6fde7162d1123bf0694f90e3de5
parent binary SHA-256:    04202b4945c757c2f06f409502ec9c6bb0ad60b685b7846656eab233578cdc17
candidate binary SHA-256: f9407714e8dff911d7a73e682c2766bd8d4f1115c2ff75433fbaff15c0eabc7c
command:    /tmp/align-llm-c8-path-benchmark compare /tmp/align-llm-c8-path-parent.bin /tmp/align-llm-c8-path-candidate.bin 201
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    201 parent and 201 candidate measurements after two discarded warmup pairs
parent median:    49,577,277 ns
candidate median: 49,481,041 ns
improvement:      1,941 ppm (0.19%)
```

All normalized result documents agreed. Two preceding 101-pair comparisons also improved in the
same direction by 4,313 ppm and 2,717 ppm. The accepted 201-pair result is deliberately reported as
a small path-local improvement; it is not a claim about repositories with fewer test candidates or
about provider/model time.

## 6. Fourth fixed coding-task baseline

The fourth capability reuses the Section 4 real-stage fixture. Before implementation, its one
basename-related test and 3,999 generic tests are all copied into selection, patch-evaluation, and
verification output. The pre-implementation baseline is:

```text
commit:     9cdf1050041c7c1ecf50b753fd48e8744bbd57eb
binary SHA-256: f9407714e8dff911d7a73e682c2766bd8d4f1115c2ff75433fbaff15c0eabc7c
command:    scripts/run-c8-selection-signal-benchmark baseline /tmp/align-llm-c8-related.WwkfjF/parent-9cdf105.bin 31
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    31 measurements after two discarded warmup runs
median:     49,461,240 ns
candidate-apply-check median: 1,275,418 ns
candidate-apply median:       1,202,635 ns
build median:                 9,444,952 ns
targeted-test median:        14,686,911 ns
full-test median:            14,762,036 ns
```

The stage medians are diagnostic decomposition. The comparison owner must validate the intentional
recommendation delta rather than requiring byte-equal result documents.

The exact-commit comparison used:

```text
git worktree add --detach /tmp/align-llm-c8-related-parent 9cdf1050041c7c1ecf50b753fd48e8744bbd57eb
git worktree add --detach /tmp/align-llm-c8-related-candidate ef192576da2f8bf8bce7e31ea2f2bc129fc52fa1
make -C /tmp/align-llm-c8-related-parent build
make -C /tmp/align-llm-c8-related-candidate build
install -m 0755 /tmp/align-llm-c8-related-parent/main /tmp/align-llm-c8-related-parent.bin
install -m 0755 /tmp/align-llm-c8-related-candidate/main /tmp/align-llm-c8-related-candidate.bin
git cat-file blob fc3181b4cad91a8a6911100f01e16b6af9670d9a > /tmp/align-llm-c8-related-benchmark
chmod 0755 /tmp/align-llm-c8-related-benchmark
sha256sum /tmp/align-llm-c8-related-parent.bin /tmp/align-llm-c8-related-candidate.bin
/tmp/align-llm-c8-related-benchmark compare-related-only \
  /tmp/align-llm-c8-related-parent.bin /tmp/align-llm-c8-related-candidate.bin 101
```

```text
parent:     9cdf1050041c7c1ecf50b753fd48e8744bbd57eb
candidate:  ef192576da2f8bf8bce7e31ea2f2bc129fc52fa1
benchmark runner Git blob: fc3181b4cad91a8a6911100f01e16b6af9670d9a
benchmark runner SHA-256: 995092b913220005e39b6491e5cae98791b83bc88b9d4a4d99515adad16be817
parent binary SHA-256:    f9407714e8dff911d7a73e682c2766bd8d4f1115c2ff75433fbaff15c0eabc7c
candidate binary SHA-256: f1c8bf75530ad5155c52e54e919be0f5388f2fd2438c1c4a81964efb567cd045
command:    /tmp/align-llm-c8-related-benchmark compare-related-only /tmp/align-llm-c8-related-parent.bin /tmp/align-llm-c8-related-candidate.bin 101
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    101 parent and 101 candidate measurements after two discarded warmup pairs
parent median:    49,635,644 ns
candidate median: 48,507,915 ns
improvement:      22,720 ppm (2.27%)
```

The parent emitted the exact 4,000-candidate list, the candidate emitted only
`tests/test_value.py` with score 100 and reason `basename-match`, and all other normalized result
fields agreed. The runner also required the exact ordered five-stage vector, `PASS` on every stage,
and matching actual/expected exit codes. A preceding 31-pair comparison improved by 21,068 ppm in
the same direction. This is a path-local claim for a repository with many generic test paths, not a
universal repository or provider/model-time claim.

## 7. Fifth fixed coding-task baseline

The fifth capability reuses the Section 4 real-stage fixture and the exact output/stage validation
strengthened by the fourth capability. Its related result contains one recommendation, but the
current selector still constructs and discards JSON for 3,999 generic candidates. The
pre-implementation baseline is:

```text
commit:     25c964d8df19c4d6571bdfcb353d0608ac07c518
binary SHA-256: f1c8bf75530ad5155c52e54e919be0f5388f2fd2438c1c4a81964efb567cd045
command:    scripts/run-c8-selection-signal-benchmark baseline /tmp/align-llm-c8-defer.MZTl1I/parent-25c964d.bin 31
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    31 measurements after two discarded warmup runs
median:     48,115,210 ns
candidate-apply-check median: 1,229,543 ns
candidate-apply median:       1,140,160 ns
build median:                 9,426,004 ns
targeted-test median:        14,739,588 ns
full-test median:            14,769,219 ns
```

The stage medians are diagnostic decomposition. Only a lower paired total median with identical
normalized result documents can close the fifth capability.

The exact-commit comparison used:

```text
git worktree add --detach /tmp/align-llm-c8-defer-parent 25c964d8df19c4d6571bdfcb353d0608ac07c518
git worktree add --detach /tmp/align-llm-c8-defer-candidate 7c95072b2bfd293911ac01c141c05c0de973c8b1
make -C /tmp/align-llm-c8-defer-parent build
make -C /tmp/align-llm-c8-defer-candidate build
install -m 0755 /tmp/align-llm-c8-defer-parent/main /tmp/align-llm-c8-defer-parent.bin
install -m 0755 /tmp/align-llm-c8-defer-candidate/main /tmp/align-llm-c8-defer-candidate.bin
git cat-file blob fc3181b4cad91a8a6911100f01e16b6af9670d9a > /tmp/align-llm-c8-defer-benchmark
chmod 0755 /tmp/align-llm-c8-defer-benchmark
sha256sum /tmp/align-llm-c8-defer-parent.bin /tmp/align-llm-c8-defer-candidate.bin
/tmp/align-llm-c8-defer-benchmark compare \
  /tmp/align-llm-c8-defer-parent.bin /tmp/align-llm-c8-defer-candidate.bin 101
```

```text
parent:     25c964d8df19c4d6571bdfcb353d0608ac07c518
candidate:  7c95072b2bfd293911ac01c141c05c0de973c8b1
benchmark runner Git blob: fc3181b4cad91a8a6911100f01e16b6af9670d9a
benchmark runner SHA-256: 995092b913220005e39b6491e5cae98791b83bc88b9d4a4d99515adad16be817
parent binary SHA-256:    f1c8bf75530ad5155c52e54e919be0f5388f2fd2438c1c4a81964efb567cd045
candidate binary SHA-256: d4e0de24a5684fb9042cf4bd82a57f0c50bb368bdea3d7b67925c150b6b6a747
command:    /tmp/align-llm-c8-defer-benchmark compare /tmp/align-llm-c8-defer-parent.bin /tmp/align-llm-c8-defer-candidate.bin 101
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    101 parent and 101 candidate measurements after two discarded warmup pairs
parent median:    48,939,615 ns
candidate median: 47,753,423 ns
improvement:      24,237 ppm (2.42%)
```

All normalized result documents agreed. The runner required the exact ordered five-stage vector,
`PASS` on every stage, and matching actual/expected exit codes. A preceding 31-pair comparison
improved by 15,135 ppm in the same direction. This is a path-local claim for related selection in a
repository with many generic test paths, not a universal repository or provider/model-time claim.

## 8. Sixth fixed coding-task baseline

The sixth capability reuses the Section 4 real-stage fixture and the exact output/stage validation
from the fifth capability. Its related result contains one recommendation, but the current selector
still retains 3,999 generic offsets that are never consumed. The pre-implementation baseline is:

```text
commit:     ed76eea9397a66e542a67633cb383d92b71058a8
binary SHA-256: d4e0de24a5684fb9042cf4bd82a57f0c50bb368bdea3d7b67925c150b6b6a747
command:    scripts/run-c8-selection-signal-benchmark baseline /tmp/align-llm-c8-rescan.6DEpCY/parent-ed76eea.bin 31
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    31 measurements after two discarded warmup runs
median:     47,364,361 ns
candidate-apply-check median: 1,140,019 ns
candidate-apply median:       1,147,480 ns
build median:                 9,454,599 ns
targeted-test median:        14,803,122 ns
full-test median:            14,742,235 ns
```

The stage medians are diagnostic decomposition. Only a lower paired total median with identical
normalized result documents can close the related-path performance claim. Generic-only fallback is
covered for exact behavior and is not part of this performance claim.

The exact-commit comparison used:

```text
make build
install -m 0755 ./main /tmp/align-llm-c8-rescan.6DEpCY/candidate-d2e15ad.bin
sha256sum /tmp/align-llm-c8-rescan.6DEpCY/parent-ed76eea.bin \
  /tmp/align-llm-c8-rescan.6DEpCY/candidate-d2e15ad.bin
scripts/run-c8-selection-signal-benchmark compare \
  /tmp/align-llm-c8-rescan.6DEpCY/parent-ed76eea.bin \
  /tmp/align-llm-c8-rescan.6DEpCY/candidate-d2e15ad.bin 201
```

```text
parent:     ed76eea9397a66e542a67633cb383d92b71058a8
candidate:  d2e15ad1f14f0317bb3d6227fa0c6ae8c2c7316c
benchmark runner Git blob: fc3181b4cad91a8a6911100f01e16b6af9670d9a
benchmark runner SHA-256: 995092b913220005e39b6491e5cae98791b83bc88b9d4a4d99515adad16be817
parent binary SHA-256:    d4e0de24a5684fb9042cf4bd82a57f0c50bb368bdea3d7b67925c150b6b6a747
candidate binary SHA-256: f77b3f102ada7d1ce405524cc8f1535dd6514dc501a07084f88f865a2a2b6f20
command:    scripts/run-c8-selection-signal-benchmark compare /tmp/align-llm-c8-rescan.6DEpCY/parent-ed76eea.bin /tmp/align-llm-c8-rescan.6DEpCY/candidate-d2e15ad.bin 201
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    201 parent and 201 candidate measurements after two discarded warmup pairs
parent median:    47,880,342 ns
candidate median: 47,793,764 ns
improvement:      1,808 ppm (0.18%)
```

All normalized result documents agreed. The runner required the exact ordered five-stage vector,
`PASS` on every stage, and matching actual/expected exit codes. Two preceding 101-pair comparisons
improved by 2,115 ppm and 1,219 ppm in the same direction. The accepted result is deliberately
reported as a small related-path improvement, not a fallback, universal repository, platform, or
provider/model-time claim.

## 9. Seventh fixed coding-task baseline

The seventh capability reuses the Section 4 real-stage fixture. The current passing path records and
runs five stages because `candidate-apply-check` and `candidate-apply` are separate Git processes.
The pre-implementation baseline is:

```text
commit:     269aeec8eb3a31ba5e68ee2ebc72583e71df6477
binary SHA-256: f77b3f102ada7d1ce405524cc8f1535dd6514dc501a07084f88f865a2a2b6f20
command:    scripts/run-c8-selection-signal-benchmark baseline /tmp/align-llm-c8-direct.hu4kUN/parent-269aeec.bin 31
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    31 measurements after two discarded warmup runs
median:     47,600,824 ns
candidate-apply-check median: 1,184,847 ns
candidate-apply median:       1,157,644 ns
build median:                 9,479,644 ns
targeted-test median:        14,805,099 ns
full-test median:            14,994,964 ns
```

The stage medians are diagnostic decomposition. The comparison owner must validate the intentional
removal of the successful check record rather than requiring byte-identical result documents.
`baseline` remains the exact five-stage owner for the earlier recorded capabilities;
`baseline-atomic` owns new four-stage baselines after this capability. This keeps every recorded
command reproducible without allowing either stage protocol to satisfy the other's evidence.

The exact-commit comparison used:

```text
make build
install -m 0755 ./main /tmp/align-llm-c8-direct.hu4kUN/candidate-6a08dd7.bin
sha256sum /tmp/align-llm-c8-direct.hu4kUN/parent-269aeec.bin \
  /tmp/align-llm-c8-direct.hu4kUN/candidate-6a08dd7.bin
scripts/run-c8-selection-signal-benchmark compare-atomic-apply \
  /tmp/align-llm-c8-direct.hu4kUN/parent-269aeec.bin \
  /tmp/align-llm-c8-direct.hu4kUN/candidate-6a08dd7.bin 101
```

```text
parent:     269aeec8eb3a31ba5e68ee2ebc72583e71df6477
candidate:  6a08dd788ffc7f80900a0dc3d5f49bd269367567
benchmark runner Git blob: 6312f93270d141f0119a203e0d9e162a82771b28
benchmark runner SHA-256: 8ddc6ea37ff478f20ae9e34be7f4955b6709850ea59f5b6fcc0606d5050fc6a7
parent binary SHA-256:    f77b3f102ada7d1ce405524cc8f1535dd6514dc501a07084f88f865a2a2b6f20
candidate binary SHA-256: 7e00353a3110c16fd802bb935a9d4bf1be784540f23567cdf4704aee728896f3
command:    scripts/run-c8-selection-signal-benchmark compare-atomic-apply /tmp/align-llm-c8-direct.hu4kUN/parent-269aeec.bin /tmp/align-llm-c8-direct.hu4kUN/candidate-6a08dd7.bin 101
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    101 parent and 101 candidate measurements after two discarded warmup pairs
parent median:    47,913,941 ns
candidate median: 46,822,706 ns
improvement:      22,774 ppm (2.28%)
```

After duration normalization, the candidate result equaled the parent result with only the
successful `candidate-apply-check` record removed. The candidate emitted the exact four-stage
vector; every stage passed with matching actual and expected codes. A preceding 31-pair comparison
improved by 26,289 ppm in the same direction. This is a path-local process-elimination claim, not a
platform or provider/model-time claim.

## 10. Eighth fixed coding-task baseline

The eighth capability reuses the Section 4 real-stage fixture and the four-stage protocol shipped
by the seventh capability. The pre-implementation baseline is:

```text
commit:     185936492dd52453c8df3fe281c82645373a5946
binary SHA-256: 7e00353a3110c16fd802bb935a9d4bf1be784540f23567cdf4704aee728896f3
command:    scripts/run-c8-selection-signal-benchmark baseline-atomic /tmp/align-llm-c8-owned-argv.peN7CZ/parent-1859364.bin 31
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    31 measurements after two discarded warmup runs
median:     45,870,371 ns
candidate-apply median: 1,284,880 ns
build median:           9,317,021 ns
targeted-test median:  14,706,435 ns
full-test median:      14,776,505 ns
```

The stage medians are diagnostic decomposition. Only a repeatably lower paired total median with
identical normalized result documents closes the claim. `compare-atomic` requires the exact
four-stage protocol from both binaries and keeps historical five-stage evidence distinct.

The exact-commit comparison used:

```text
make build
install -m 0755 ./main /tmp/align-llm-c8-owned-argv.peN7CZ/candidate-4f7dd62.bin
sha256sum /tmp/align-llm-c8-owned-argv.peN7CZ/parent-1859364.bin \
  /tmp/align-llm-c8-owned-argv.peN7CZ/candidate-4f7dd62.bin
scripts/run-c8-selection-signal-benchmark compare-atomic \
  /tmp/align-llm-c8-owned-argv.peN7CZ/parent-1859364.bin \
  /tmp/align-llm-c8-owned-argv.peN7CZ/candidate-4f7dd62.bin 101
```

```text
parent:     185936492dd52453c8df3fe281c82645373a5946
candidate:  4f7dd62c3bf6d6e4d81216a44c3b4f2f9bf7eb32
benchmark runner Git blob: 492f53db5ca6e934daf8340e6c9998cc7340ddcc
benchmark runner SHA-256: 80618fd088a5e5f75e3772aec60db510ec27fc4f4c0c9024ba0cd0104b08858b
parent binary SHA-256:    7e00353a3110c16fd802bb935a9d4bf1be784540f23567cdf4704aee728896f3
candidate binary SHA-256: 64c40cb4ba967575a40d7e489175ff0703fff4f503f8d967db46c4dbe05309fe
command:    scripts/run-c8-selection-signal-benchmark compare-atomic /tmp/align-llm-c8-owned-argv.peN7CZ/parent-1859364.bin /tmp/align-llm-c8-owned-argv.peN7CZ/candidate-4f7dd62.bin 101
host:       Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:        AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:    101 parent and 101 candidate measurements after two discarded warmup pairs
parent median:    46,537,217 ns
candidate median: 46,355,109 ns
improvement:      3,913 ppm (0.39%)
```

All normalized result documents agreed. Both binaries emitted the exact four-stage vector, and
every stage passed with matching actual and expected codes. A preceding 31-pair comparison improved
by 5,224 ppm in the same direction. This is a path-local allocation improvement, not a platform or
provider/model-time claim.

## 11. Ninth fixed coding-task baseline

The ninth capability reuses the Section 4 real-stage fixture and the four-stage protocol shipped by
the seventh capability. Measurement is owned by the measuring agent; the fields below are filled
from the actual runs recorded here.

The pre-implementation baseline is:

```text
commit:     9bfa372a3bb1d78fbd672740208e702e7db72122
binary SHA-256: 76bfa07a13fd0d9b85484d2ebab9b6ed65caa6f60c212b8e607a681df4b08a78
command:    scripts/run-c8-selection-signal-benchmark baseline-atomic /opt/bench/binary1 31
host:       Linux 6.11.11-linuxkit aarch64 (Docker Desktop linux/arm64 VM on macOS)
cpu:        Apple M1, 8 logical CPUs exposed to the container
samples:    31 measurements after two discarded warmup runs
median:     43,041,708 ns
candidate-apply median: 546,917 ns
build median:           7,506,583 ns
targeted-test median:   15,506,875 ns
full-test median:       15,724,000 ns
```

The exact-commit comparison used:

```text
scratchpad/linux-bench.sh build scratchpad/candidate-e057bf0 scratchpad/bench/candidate-e057bf0.bin
sha256sum scratchpad/bench/parent-9bfa372.bin scratchpad/bench/candidate-e057bf0.bin
scratchpad/linux-bench.sh bench scratchpad/candidate-e057bf0 scratchpad/bench/parent-9bfa372.bin \
  compare-atomic 101 scratchpad/bench/candidate-e057bf0.bin
```

```text
parent:     9bfa372a3bb1d78fbd672740208e702e7db72122
candidate:  e057bf0129e7594de5655be68854952405607407
benchmark runner Git blob: 492f53db5ca6e934daf8340e6c9998cc7340ddcc
benchmark runner SHA-256: 80618fd088a5e5f75e3772aec60db510ec27fc4f4c0c9024ba0cd0104b08858b
parent binary SHA-256:    76bfa07a13fd0d9b85484d2ebab9b6ed65caa6f60c212b8e607a681df4b08a78
candidate binary SHA-256: 976b97c642ec0bfc3d128400d8b11412a400bf5e3bfa55ea69c0457dbf8cbb0a
command:    scripts/run-c8-selection-signal-benchmark compare-atomic /opt/bench/binary1 /opt/bench/binary2 101
host:       Linux 6.11.11-linuxkit aarch64 (Docker Desktop linux/arm64 VM on macOS)
cpu:        Apple M1, 8 logical CPUs exposed to the container
samples:    101 parent and 101 candidate measurements after two discarded warmup pairs
parent median:    42,884,666 ns
candidate median: 42,421,792 ns
improvement:      10,793 ppm (1.08%)
```

All normalized result documents agreed. Both binaries emitted the exact four-stage vector, and
every stage passed with matching actual and expected codes. A preceding 31-pair comparison improved
by 13,749 ppm in the same direction.

The stage medians are diagnostic decomposition. Only a repeatably lower paired total median with
identical normalized result documents closes the claim. The benchmark fixture creates its repository
with an initial commit, so it exercises the committed-HEAD path; the unborn-HEAD contract change in
section 2.9 is owned by `scripts/run-patch-eval-smoke`, not by this benchmark. This is a
path-local process-count improvement, not a platform or provider/model-time claim.

This ninth capability was measured on a different host from Sections 3-10 (an aarch64 Docker
Desktop VM rather than WSL2 x86_64), so its baseline and comparison are only comparable with each
other, not with the Section 3-10 series; the improvement above is a path-specific claim, not a
platform claim.

## 12. Deferred C8 surfaces

The original C8 gate in `docs/specs/roadmap.md` — a shorter median time to a passing patch than the
baseline — was met by all nine shipped capabilities before delivery moved to Track B. The surfaces
below are not a backlog. One reopens as a new capability only when it carries a recorded cost ceiling
above the section 1 shipping floor of 2,000 ppm, or when it becomes a genuine Align capability
request under the `CLAUDE.md` classification rule. `C8-OPTIONAL-TARGETED-STAGE` is the sole current
exception: its fresh 326,093 ppm ceiling exceeds the floor and its Align prerequisite shipped in PR #892,
so the user explicitly prioritized it on 2026-08-28. Every other deferred surface remains closed;
intuition that a seam "looks hot" is still insufficient without a profiled or measured share.

Context reduction, stable-context reuse, parallel checks, small-model routing, and persisted static
analysis remain separate capabilities. In particular, captured concurrent checks require an Align
process surface that the current pin does not provide; this capability does not open an Align request
or weaken verification dependencies to manufacture parallelism.

The `--select-tests` CLI and `repo_index.build` deliberately keep their `git rev-parse --verify HEAD`
invocation because both publish `revision`. Reusing one tracked-file listing across an index build
and a selection in the same process, and caching a listing between invocations, are separate
capabilities that would need their own invalidation contract; neither is in scope here.
