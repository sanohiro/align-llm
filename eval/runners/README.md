# Runners

Add deterministic setup, execution, timeout, cleanup, and scoring adapters here. Runners must preserve command output needed to reproduce a failure and must not depend on unrecorded machine state.

`run-fixed.sh` executes a corpus through the built align-llm binary, preserves its JSON Lines on
stdout, rejects non-passing verdicts, and compares the final summary with the checked-in oracle.
Run it through `make eval-smoke` or as part of `make ci`; direct invocation is supported for
diagnosis:

```text
eval/runners/run-fixed.sh eval/tasks/smoke-v1.json
```

`run-coding-task.py` materializes a fixture as a deterministic SHA-1 Git commit in a temporary
directory. It checks the pinned revision, requires validation to fail before repair, applies a
candidate patch, enforces the edit allowlist, and requires validation to pass afterward. Candidate
validation runs in a bubblewrap sandbox with isolated process, mount, IPC, and network namespaces;
only the temporary checkout worktree is writable while its `.git` metadata remains read-only, and
execution fails closed unless Linux child-subreaper support and a probe of the required
`/usr/bin/bwrap` namespaces succeed. The validation process has bounded address space, CPU time,
resident memory, process count, and open files; `/tmp` and `/dev/shm` are size-limited tmpfs
mounts, and the runner monitors the writable checkout for bounded file-count and aggregate-size
usage. The monitor also
accounts for deleted-but-open regular files and descendant resident memory, and aborts a resource
scan if it cannot finish within its small polling budget. A scan skips only entries that disappear
between enumeration and metadata inspection and already-observed descendant directories that
disappear before their queued scan; a missing checkout root and iterator, metadata, or cleanup
errors still fail closed. `scripts/run-coding-task-resource-scan-smoke` exercises those races,
deadline precedence, iterator cleanup, exact file and byte ceilings, and root-only `.git` exclusion
against the runner's exact source bytes. Directory modes are snapshotted before validation and
rejected if a candidate or validator changes them, including the checkout root.
Temporary checkout cleanup is automatic. The CI gate
also supplies a patch that changes a forbidden test file
and a passing patch that writes and stages a forbidden file during validation; both must be rejected
against the original fixture commit after execution. Additional regressions prove ambient Git
configuration cannot change the fixture revision and that a timed-out validation retains output,
kills its descendant process tree, and removes its temporary checkout. Fixture setup rejects ignored
inputs, validation command ownership includes cleaning descendants after normal completion, and
pre-validation mutations are compared against the pinned bytes and modes before patch application.
Non-UTF-8 diagnostics are retained with replacement decoding. Runner command output is drained
incrementally and bounded to 64 KiB per stream with a truncation marker, including during timeout
cleanup. Each persisted baseline stdout or stderr stream is bounded and verified at 64 KiB.
Validation receives a minimal
environment without caller credentials, and all provenance-related Git operations disable
replacement objects. The fixed coding corpus dispatches through an absolute system Python path so
ambient `PATH` cannot select another interpreter.

Validation executables must resolve inside the read-only system runtime (`/usr` or the selected
Python installation); fixture-local executables are intentionally rejected until they have an
explicit sandbox mount policy.

Record a pending baseline only from a clean commit. The pending file is intentionally outside the
canonical path until its immutable oracle has been committed:

```text
python3 eval/runners/record-baseline.py \
  --corpus eval/tasks/coding-v1.json \
  --provider deterministic-reference \
  --model checked-in-patch \
  --prompt-version none \
  --samples 2 \
  --output eval/baselines/.coding-v1-reference.pending.json
```

Commit `eval/expected/coding-v1-reference-oracle.json` from the pending result, then finalize the
canonical record with that oracle commit:

```text
python3 scripts/finalize-canonical-baseline.py \
  --input eval/baselines/.coding-v1-reference.pending.json \
  --oracle-commit <full-oracle-commit>
```

The finalizer writes `eval/baselines/coding-v1-reference.json` and its digest. Remove the pending
file after the canonical result is committed.

The recorder verifies and release-builds the pinned sibling Align compiler, rebuilds `main`, and
rechecks source cleanliness before measurement. It accepts complete non-passing suite results so
provider failures remain measurable; the CI smoke suite exercises that path with a complete failing
JSON Lines result and nonzero evaluator exit. Environment metadata records both the requested and
resolved absolute Python executable, plus the version used by the measured corpus task.
