# align-llm

`align-llm` is a local LLM coding system written in [Align](https://github.com/sanohiro/align). It aims to improve practical coding performance through fast verification, repository-specific knowledge, and repeated local optimization rather than reproducing a general cloud model stack.

The project has two independently developed parts:

- **align-coder** builds repository indexes, evaluates patches, selects tests, runs repair loops, and learns from verified outcomes.
- **align-runtime** loads and schedules open-weight models across GPU memory, system memory, and NVMe.

Development starts with `align-coder` using existing cloud or local OpenAI-compatible providers. The custom runtime can replace a provider after its value is measured independently.

## Status

This repository is at the project-bootstrap stage. The Align-native entry point compiles with the current sibling Align checkout, and the evaluation directories mirror the first roadmap milestone. The REST framework in Align is still under development and is not yet a dependency of this scaffold.

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
```

`make check` checks the complete import graph one module at a time. `make run` compiles and runs the bootstrap CLI. `make build` writes the `main` executable in the repository root; it is ignored by Git.

Read [Align development notes](docs/align-development.md) before adding language or standard-library dependencies. Read [AGENTS.md](AGENTS.md) for repository conventions, including the English-only policy for code comments, commits, and pull requests.

## Plans

The current detailed plans are written in Japanese:

- [System specification](docs/specs/align-llm.md)
- [Development roadmap](docs/specs/roadmap.md)

English translations can be added alongside them as the design stabilizes.
