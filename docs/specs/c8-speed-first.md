# C8 Speed-first optimization

Status: first two consumer-complete capabilities merged; third capability implemented and measured.
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

## 6. Deferred C8 surfaces

Context reduction, stable-context reuse, parallel checks, small-model routing, and persisted static
analysis remain separate capabilities. In particular, captured concurrent checks require an Align
process surface that the current pin does not provide; this capability does not open an Align request
or weaken verification dependencies to manufacture parallelism.
