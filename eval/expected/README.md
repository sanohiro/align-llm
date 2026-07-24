# Expected outcomes

Define observable acceptance criteria for each task, including required checks, forbidden unrelated changes, and any performance boundary. Keep expected patches optional so semantically valid alternatives can pass.

Checked-in `*-summary.json` files are the deterministic score oracle for fixed corpora. Per-task
JSON Lines include duration metadata, but the final summary contains only stable score data:

```json
{"schema_version":1,"corpus_id":"smoke-v1","task_count":2,"pass_count":2,"fail_count":0}
```

The runner fails if any task is not `PASS`, if the ordered task IDs differ from the checked-in
`*-task-ids.txt` oracle, or if the final summary differs byte-for-byte from the expected file. The
ID oracle detects omissions, substitutions, duplicates, and reordering; the summary independently
checks the counts.
