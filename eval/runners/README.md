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
candidate patch, enforces the edit allowlist, and requires validation to pass afterward. Temporary
checkout cleanup is automatic. The CI gate also supplies a patch that changes a forbidden test file
and a passing patch that writes and stages a forbidden file during validation; both must be rejected
against the original fixture commit after execution. Additional regressions prove ambient Git
configuration cannot change the fixture revision and that a timed-out validation retains output,
kills its process group, and removes its temporary checkout.

Record a canonical baseline only from a clean commit:

```text
python3 eval/runners/record-baseline.py \
  --corpus eval/tasks/coding-v1.json \
  --provider deterministic-reference \
  --model checked-in-patch \
  --prompt-version none \
  --samples 2 \
  --output eval/baselines/coding-v1-reference.json
```

The recorder verifies and release-builds the pinned sibling Align compiler, rebuilds `main`, and
rechecks source cleanliness before measurement. It accepts complete non-passing suite results so
provider failures remain measurable; the CI smoke suite exercises that path with a complete failing
JSON Lines result and nonzero evaluator exit.
