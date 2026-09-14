# Development with Antigravity

Use Antigravity CLI (`agy`), with an authenticated account that lists Gemini 3.8 Flash in
`agy models`. Native integration is qualified with agy 1.2.1. This does not use Gemini CLI.

## Start or resume work

From the repository root:

```sh
agy --add-dir "$PWD" --model gemini-3.8-flash-medium
```

The explicit workspace makes source, `AGENTS.md`, and native agent definitions available to agy.
`AGENTS.md` points to the shared `CLAUDE.md`; do not duplicate those rules in another file.
Use the following initial prompt, adapted to the task:

```text
Read AGENTS.md and HANDOFF.md first. Continue the active capability from its current checkpoint.
Preserve all existing staged, unstaged, and untracked work. Follow the canonical repository
workflow, use the pinned toolchain and narrow owner checks, and update HANDOFF.md at a durable
checkpoint. Do not treat a successful model response as verification or review evidence.
```

For high-effort work select `--model gemini-3.8-flash-high`. The interactive agent uses normal agy
permissions and the existing project rules. agy 1.2.1 remembers model selections in user settings,
so specify the model explicitly for each development or review invocation. This integration does
not replace credentials, plugins, or permission settings. Git, build, test and publication commands
are the same as for Claude Code and Codex.

The default interactive mode asks before applying edits. Add `--mode accept-edits` to approve
file edits automatically during development; shell commands still follow agy's normal permissions.
This mode is separate from the dedicated inspection-only reviewer. A native Medium/accept-edits
fixture probe verified a file repair against the shared guide and three independent assertions.

## Review a stable candidate

After committing a consumer-complete candidate with a clean worktree and passing its owner check:

```sh
scripts/review-agy --base origin/main
```

The command starts a fresh `gemini-3.8-flash-high` conversation with the native
`align-llm-reviewer` agent. It supplies the exact diff and Git identities, permits source inspection,
and validates the returned evidence. It does not run verification or publish a GitHub review.

Evidence is saved under the Git common directory in `agy-reviews/<HEAD>-<base-tip>/`:
`review.log`, `diff.patch`, `prompt.txt`, `events.jsonl`, `stderr.log`, and metadata. It also works in
linked worktrees. `--output DIRECTORY` selects a new directory with an existing parent outside the
worktree. Existing evidence is never overwritten.

- Exit 0: the review completed with CLEAN.
- Exit 2: the review completed with FINDINGS; inspect and resolve every valid finding.
- Other exits: incomplete or invalid invocation; inspect the retained evidence. Missing context,
  denied tools, model mismatch, source mutation and timeout never become CLEAN.

`AGY_REVIEW_TIMEOUT_SECONDS` sets a positive per-invocation ceiling, default 1800 seconds. A timeout
ends that invocation only. Preserve its findings and resume only unfinished scope under the shared
review rules; do not repeatedly launch complete reviews. The standalone command owns only full,
clean textual candidates. Dirty checkpoints and partial continuations use a fresh independent
reviewer with explicitly supplied scope instead of pretending they are a completed full review.

Copy the full review envelope to a native GitHub review or dedicated comment: reviewed HEAD,
base tip, merge base, agy/model, conversation identity, kind/scope, verdict and complete findings.
Record finding dispositions and any repair commit separately. Run the existing required preflight
on final unchanged HEAD. The local review record is neither a preflight stamp nor merge approval.

## Owner verification

```sh
bash scripts/test-agy-review
bash scripts/test-agy-review --live
```

The first command uses isolated Git fixtures and a fake provider to test false-CLEAN refusal,
Git layouts, admission, cancellation and evidence preservation. The optional live command also
uses the authenticated real model to find a known conversion defect in an isolated fixture.
It does not review or change the active product cutover candidate. These are developer-tool owners,
outside product aggregates. See the [contract ledger](specs/agy-development.md).
