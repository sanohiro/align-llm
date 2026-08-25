# Evaluation workspace

Evaluation is the first delivery track because every later optimization needs a stable comparison.

- `tasks/` contains reproducible coding task definitions and fixtures.
- `expected/` contains acceptance criteria and expected outcomes.
- `runners/` contains deterministic task setup, execution, and scoring adapters.
- `baselines/` contains versioned baseline metadata and measurements, not model weights.
- `prompt/` contains the frozen C6 prompt-optimizer scope assets and, later, the checked-in gate
  evidence.

Each task should identify its repository revision, allowed tools, timeout, checks, scoring rules, and cleanup procedure. Never accept a prompt, context, provider, or runtime optimization without comparing it against the fixed task set and recording regressions.

`tasks/prompt-v1/` is the C6g1 gate corpus for the prompt/context optimizer, and
`prompt/canonical-v1/` holds the frozen scope assets and the `baseline-v1` activation envelope that
bind it. Read `eval/tasks/prompt-v1/README.md` and `eval/prompt/canonical-v1/README.md` before
changing either; their digests are chained and must be regenerated together.

`tasks/smoke-v1.json` checks the evaluator itself. `tasks/coding-v1.json` is the first real repair
corpus: its runner constructs a pinned Git repository, proves the defect is observable, applies a
candidate patch under an edit allowlist, and runs the declared validation command inside a
bubblewrap sandbox. The coding corpus currently requires Linux child-subreaper support, a successful
`/usr/bin/bwrap` namespace probe, and `/usr/bin/prlimit`; it fails closed when any containment or
resource-control mechanism is unavailable. Run the complete local gate with:

```text
make ci
```

The gate resolves the managed Align compiler through `.align-revision`, checks and builds all
project units, runs the bounded core C1-C5 functional graph, executes the sandboxed coding corpus,
and verifies the canonical baseline. The revision-keyed managed checkout validates its exact clean
HEAD before reuse, so an ambient sibling compiler cannot survive a pin update.

Use `make hosted-checks` when the host cannot provide the nested user namespace required by
`coding-v1`. It runs the hosted-compatible core checks but deliberately excludes `eval-coding` and
`baseline-check`. Security, resource-limit, race, fuzz, stress, platform, mutation, and benchmark
qualification may remain outside both aggregates and run when their owning boundary changes or an
explicit audit requires them. Name every directly invoked focused command in review evidence rather
than inferring that an aggregate ran it.
