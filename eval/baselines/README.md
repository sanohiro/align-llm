# Baselines

Record provider, model, prompt version, hardware profile, repository revision, task results, and timing metadata. Do not commit credentials, private prompts, generated binaries, or model weights.

Every recorded baseline must include:

- the align-llm commit;
- the exact Align commit from `.align-revision`;
- corpus ID and schema version;
- provider, model, and prompt version;
- OS, architecture, and relevant hardware profile;
- per-task verdict and duration;
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
full evaluation-artifact digest set, per-run summaries, and recomputed time-to-passing-patch
aggregates without comparing unstable timings against a new machine. A task wrapper's
`artifact_paths` binds its nested descriptor, fixture, validation runner, candidate producer, and
other executable inputs to the baseline source commit. Global artifacts also bind the compiler pin,
line-ending policy, and recorder that defines measurement semantics.
