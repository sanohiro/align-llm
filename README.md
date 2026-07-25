# align-llm

`align-llm` is a local LLM coding system written in [Align](https://github.com/sanohiro/align). It aims to improve practical coding performance through fast verification, repository-specific knowledge, and repeated local optimization rather than reproducing a general cloud model stack.

The project has two independently developed parts:

- **align-coder** builds repository indexes, evaluates patches, selects tests, runs repair loops, and learns from verified outcomes.
- **align-runtime** loads and schedules open-weight models across GPU memory, system memory, and NVMe.

Development starts with `align-coder` using existing cloud or local OpenAI-compatible providers. The custom runtime can replace a provider after its value is measured independently.

## Status

The C0 evaluation and verification foundation is complete. C1 now has an explicit provider boundary
with cloud OpenAI-compatible, local OpenAI-compatible, and llama.cpp adapters; generate/stream
operations; transparent estimated versus exact token counts; and one versioned JSON result format.
The provider smoke fixture exercises all three adapters without requiring a model server. Streaming
currently requires a Content-Length-framed response because the shipped Align HTTP client still
rejects chunked response bodies; that limitation is tracked in `docs/align-requests.md`.
C2 now has a repository-index slice for tracked files, Align declarations/imports, lexical
references, semantic resolution status, and test-path candidates, persisted as one revision-bound
JSON document. It also provides deterministic path-based related-test selection with ranked
candidates and persisted selection metadata. C3 now adds a read-only unified-diff evaluator with
touched-file and symbol records, deterministic risk signals, and recommended tests.
C4 now adds a bounded verification loop: it evaluates and applies a candidate patch, runs build,
targeted-test, and full-test commands with timeouts, records structured diagnostics, generates a
repair prompt, and can apply one deterministic repair patch before re-running the stages. The
repair patch is the provider-independent seam for the fixed-task gate; model-backed repair is a
later integration.

## Prerequisites

Align is pre-release. For compiler prerequisites and installation details, see the [Align getting-started guide](https://github.com/sanohiro/align/blob/main/docs/guide/01-getting-started.md).

For compiler development, keep both repositories adjacent:

```text
Projects/
  align/
  align-llm/
```

Build Align first:

```sh
cd ../align
cargo build --release
cd ../align-llm
```

The project wrapper also accepts an explicit compiler path:

```sh
ALIGNC=/path/to/alignc make check
```

## Development

```sh
make check
make run
make fmt
make build
make provider-smoke
make index-smoke
make test-selection-smoke
make patch-eval-smoke
make verify-loop-smoke
```

`make check` checks the complete import graph one module at a time. `make run` compiles and runs the bootstrap CLI. `make build` writes the `main` executable in the repository root; it is ignored by Git.

Read [Align development notes](docs/align-development.md) before adding language or standard-library dependencies. Read [AGENTS.md](AGENTS.md) for repository conventions, including the English-only policy for code comments, commits, and pull requests.

The provider demonstration accepts an explicit endpoint and writes the common result record:

```sh
./main --provider openai-local http://127.0.0.1:8080/v1/chat/completions model - "repair the range" result.json
# Cloud keys are read from the named environment variable, never from argv.
OPENAI_API_KEY=... ./main --provider cloud https://api.openai.com/v1/chat/completions model OPENAI_API_KEY "repair the range" result.json
```

Build the first repository index slice from a Git worktree:

```sh
./main --index . index.json
```

Select related tests for a changed tracked path:

```sh
./main --select-tests . src/main.align related-tests.json
```

Evaluate a patch without applying it:

```sh
./main --evaluate-patch . candidate.patch patch-evaluation.json
```

Run a bounded verification task from a JSON specification:

```sh
./main --verify-loop task.json verification-result.json
```

The task names the repository root, candidate and repair patch path (use an empty string to disable
repair), and separate build, targeted-test, and full-test commands. Each command has an argv array,
expected exit code, and a shared timeout; `max_iterations` bounds the loop. The result is
schema-versioned JSON containing
the C3 evaluation, every attempt and stage, stdout/stderr, failure summaries, and repair prompts.

## Plans

The current detailed plans are written in Japanese:

- [System specification](docs/specs/align-llm.md)
- [Development roadmap](docs/specs/roadmap.md)

English translations can be added alongside them as the design stabilizes.
