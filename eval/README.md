# Evaluation workspace

Evaluation is the first delivery track because every later optimization needs a stable comparison.

- `tasks/` contains reproducible coding task definitions and fixtures.
- `expected/` contains acceptance criteria and expected outcomes.
- `runners/` contains deterministic task setup, execution, and scoring adapters.
- `baselines/` contains versioned baseline metadata and measurements, not model weights.

Each task should identify its repository revision, allowed tools, timeout, checks, scoring rules, and cleanup procedure. Never accept a prompt, context, provider, or runtime optimization without comparing it against the fixed task set and recording regressions.

The first executable corpus is `tasks/smoke-v1.json`. Run the complete local gate with:

```text
make ci
```

The gate pins and release-builds the sibling Align compiler through `.align-revision`, checks and
builds all project units, runs the fixed corpus, compares its machine-readable summary with the
checked-in expectation, and exercises the provider-independent loop spike. Building the pinned
compiler inside the gate prevents a stale local `target/release/alignc` from surviving an Align
checkout update.
