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
```

`make check` checks the complete import graph one module at a time. `make run` compiles and runs the bootstrap CLI. `make build` writes the `main` executable in the repository root; it is ignored by Git.

Read [Align development notes](docs/align-development.md) before adding language or standard-library dependencies. Read [AGENTS.md](AGENTS.md) for repository conventions, including the English-only policy for code comments, commits, and pull requests.

The provider demonstration accepts an explicit endpoint and writes the common result record:

```sh
./main --provider openai-local http://127.0.0.1:8080/v1/chat/completions model - "repair the range" result.json
```

## Plans

The current detailed plans are written in Japanese:

- [System specification](docs/specs/align-llm.md)
- [Development roadmap](docs/specs/roadmap.md)

English translations can be added alongside them as the design stabilizes.
