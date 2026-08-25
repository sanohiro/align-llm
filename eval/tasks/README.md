# Tasks

Store one reproducible coding task per directory. Pin the source revision and describe the failure, constraints, allowed edits, and validation commands without embedding a preferred patch.

A corpus manifest is a declared JSON record:

```json
{"schema_version":1,"corpus_id":"smoke-v1","task_files":["eval/tasks/smoke-v1/example.json"]}
```

Each referenced task file contains one command gate:

```json
{"id":"example","cmd":"git","argv":["git","status","--porcelain"],"cwd":".","timeout_ns":30000000000,"expected_code":0}
```

Keep manifest order stable. `argv[0]` is the process name, matching `std.process`. Paths are resolved
from the repository root; runners must execute from there. Adding a task requires updating the
matching expected corpus summary.

`coding-v1/` contains real repair-task metadata. Its descriptor pins a deterministic Git revision,
declares the source fixture, edit allowlist, validation command, and validation timeout. The task
description states the failure and constraints without embedding a preferred patch. The corpus
adapter chooses the candidate patch or future provider output separately.

`prompt-v1/` is the C6 gate corpus and uses a different, richer record: each task file is a
`PromptEvaluationTask` that additionally pins its measurement adapter, snapshot helper, content-bound
artifact expectations, and regression limits. Its frozen membership lives in
`eval/prompt/canonical-v1/corpus.json`, not in a sibling `prompt-v1.json`. See
`prompt-v1/README.md`.

`empty-invalid.json` is a negative regression fixture: `make eval-smoke` requires the evaluator to
reject an empty corpus before it can emit a passing summary.
