# C8 Speed-first optimization

Status: first consumer-complete capability implemented. This document owns performance claims and
acceptance measurements for C8 optimizations.

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

## 2. Capability ledger

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

## 3. Fixed passing-patch benchmark

The benchmark creates one temporary Git repository with `src/value.py` and 4,000 tracked generic
test files. Its candidate patch changes the function from `return 0` to `return 1`. Build, targeted,
and full-test stages use `/usr/bin/true`, isolating repository analysis while still requiring the
normal candidate apply-check, apply, build, targeted-test, and full-test sequence to finish with
`PASS` in one iteration. Repository setup and `git reset --hard HEAD` happen outside the timed
region.

Parent and candidate run in alternating order for each pair. Two pairs warm the binaries and are
discarded. The runner normalizes only per-stage `duration_ns` and requires every other result byte
represented by the decoded document to agree. It fails if the candidate median is not lower.

The implementation measurement used:

```text
parent:    ab155b391cfe12a2d53674179b993fc43fa86120
candidate: be5291ef79d9f7a9102d91d86afb7880fc5c7182
command:   scripts/run-c8-test-selection-benchmark /tmp/align-llm-c8-parent-ab155b3 ./main 15
host:      Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
cpu:       AMD Ryzen 9 5950X 16-Core Processor, 32 logical CPUs
samples:   15 parent and 15 candidate measurements after warmup
parent median:    48,914,189 ns
candidate median: 12,496,138 ns
improvement:      744,529 ppm (74.5%)
```

Both binaries were built with the repository's normal `make build` command and the same managed
Align pin. This evidence closes the C8 gate for this capability only; it does not claim that every
repository or the model/provider phase improves by 74.6%.

## 4. Deferred C8 surfaces

Context reduction, stable-context reuse, parallel checks, small-model routing, and persisted static
analysis remain separate capabilities. In particular, captured concurrent checks require an Align
process surface that the current pin does not provide; this capability does not open an Align request
or weaken verification dependencies to manufacture parallelism.
