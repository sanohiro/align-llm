# Runners

Add deterministic setup, execution, timeout, cleanup, and scoring adapters here. Runners must preserve command output needed to reproduce a failure and must not depend on unrecorded machine state.

`run-fixed.sh` executes a corpus through the built align-llm binary, preserves its JSON Lines on
stdout, rejects non-passing verdicts, and compares the final summary with the checked-in oracle.
Run it through `make eval-smoke` or as part of `make ci`; direct invocation is supported for
diagnosis:

```text
eval/runners/run-fixed.sh eval/tasks/smoke-v1.json
```
