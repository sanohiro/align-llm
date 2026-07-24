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
