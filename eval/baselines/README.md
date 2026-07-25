# Baselines

Record provider, model, prompt version, hardware profile, repository revision, task results, and timing metadata. Do not commit credentials, private prompts, generated binaries, or model weights.

Every recorded baseline must include:

- the align-llm commit;
- the exact Align commit from `.align-revision`;
- corpus ID and schema version;
- provider, model, and prompt version;
- OS, architecture, and relevant hardware profile;
- per-task verdict and duration;
- captured task stdout and stderr diagnostics;
- aggregate pass count and time-to-passing-patch statistics.

Do not record a baseline from a dirty worktree as a canonical comparison. Raw local experiments may
be retained outside the repository until the producing change has a named commit.

The baseline recorder rejects dirty worktrees and fewer than two samples, verifies and builds the
pinned compiler, and rebuilds the measured executable. Use the command documented in
`eval/runners/README.md`. `deterministic-reference` identifies a
checked-in known-good candidate used to establish the scoring and timing pipeline; it is not a model
quality result and must not be compared as if it were one.

`coding-v1-reference.json` was recorded twice from its named clean commit. `make baseline-check`
validates its commit ancestry, pinned Align revision, corpus and task identity, required metadata,
full evaluation-artifact digest set, independent canonical-record digest, per-run summaries, and
recomputed time-to-passing-patch aggregates without comparing unstable timings against a new
machine. A task wrapper's
`artifact_paths` binds its nested descriptor, fixture, validation runner, candidate producer, and
other executable inputs to the baseline source commit. Global artifacts also bind the compiler pin,
line-ending policy, and recorder that defines measurement semantics. Environment metadata identifies
the requested and resolved Python executable and version that ran the measured task.

The canonical record's SHA-256 is stored separately in
`eval/expected/coding-v1-reference.sha256`; changing the record without updating this independent
oracle is rejected by `make baseline-check`.

Persisted task diagnostics are capped and verified at 64 KiB per stream; oversized output retains a
UTF-8-safe prefix and an explicit truncation marker.
