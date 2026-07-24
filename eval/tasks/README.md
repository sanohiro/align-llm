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
