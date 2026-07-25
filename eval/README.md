# Evaluation workspace

Evaluation is the first delivery track because every later optimization needs a stable comparison.

- `tasks/` contains reproducible coding task definitions and fixtures.
- `expected/` contains acceptance criteria and expected outcomes.
- `runners/` contains deterministic task setup, execution, and scoring adapters.
- `baselines/` contains versioned baseline metadata and measurements, not model weights.

Each task should identify its repository revision, allowed tools, timeout, checks, scoring rules, and cleanup procedure. Never accept a prompt, context, provider, or runtime optimization without comparing it against the fixed task set and recording regressions.

`tasks/smoke-v1.json` checks the evaluator itself. `tasks/coding-v1.json` is the first real repair
corpus: its runner constructs a pinned Git repository, proves the defect is observable, applies a
candidate patch under an edit allowlist, and runs the declared validation command inside a
bubblewrap sandbox. The coding corpus currently requires Linux child-subreaper support and
`/usr/bin/bwrap`; it fails closed when either containment mechanism is unavailable. Run the complete
local gate with:

```text
make ci
```

The gate pins and release-builds the sibling Align compiler through `.align-revision`, checks and
builds all project units, runs the fixed corpus, compares its machine-readable summary with the
checked-in expectation, and exercises the provider-independent loop spike. Building the pinned
compiler inside the gate prevents a stale local `target/release/alignc` from surviving an Align
checkout update.
