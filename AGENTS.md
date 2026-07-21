# AGENTS.md

## Repository purpose

This repository implements a local LLM coding system in the Align programming language. It has two independently testable components:

- `align-coder`: repository-aware generation, verification, repair, evaluation, and local learning.
- `align-runtime`: efficient local inference across GPU memory, system memory, and NVMe.

The roadmap deliberately starts with `align-coder` and existing model providers. Do not make `align-coder` wait for the custom runtime.

## Align source of truth

Align is under active development in the sibling repository at `../align`. Before writing or reviewing Align code, read `../align/CLAUDE.md` and then the relevant authoritative material there:

- `../align/draft.md` for the complete language specification.
- `../align/docs/language-spec.md` for the condensed specification.
- `../align/docs/design-notes.md`, `history.md`, `non-goals.md`, and `open-questions.md` before proposing language behavior.
- `../align/docs/guide/` for supported syntax and standard-library APIs.
- `../align/examples/` for compiler-tested examples.
- `../align/docs/impl/15-pkg-web-plan.md`, `../align/docs/impl/pkg-design/web.md`, and `../align/apps/web/pkg/` for the in-progress REST framework.

Treat the checked-out compiler and its tests as the implemented surface. Do not invent a manifest, package resolver, test runner, or language feature that Align does not yet support. If this project needs missing Align functionality, document the dependency clearly and make the smallest coordinated change in the Align repository separately.

## Project plans

- `docs/specs/align-llm.md` defines the system architecture and principles.
- `docs/specs/roadmap.md` defines delivery order and evaluation gates.
- `docs/align-development.md` explains the local toolchain integration.

Preserve the central metric: time to a passing patch. Prefer measured, repository-specific improvements over broader but unverified feature coverage.

## Language and international collaboration

- Write all source-code comments in English.
- Write new developer documentation in English. Existing Japanese planning documents may remain in Japanese; keep English translations synchronized when translations are added.
- Write commit subjects and commit bodies in English.
- Write pull request titles, descriptions, review replies, and change summaries in English.
- Use English identifiers, user-facing diagnostic text, test names, benchmark names, and issue references.

## Development workflow

Use the repository wrapper so local development follows the current sibling Align checkout:

```text
make check
make run
make fmt
make build
```

The wrapper resolves the compiler in this order: `ALIGNC`, the sibling release build, the sibling debug build, then `alignc` on `PATH`. Run `make check` after every semantic change and `make fmt` before committing Align source.

Keep modules explicit and data-oriented. One `.align` file is one module, imports define the build graph, public API uses `pub`, fallible work returns `Result`, and allocation or ownership must remain visible.

## Change discipline

- Keep commits small and scoped to one roadmap gate or enabling change.
- Include the relevant check, evaluation, or benchmark result in every PR description.
- Do not claim performance improvements without a reproducible baseline and measurement.
- Do not commit model weights, generated binaries, credentials, local profiles, or machine-specific paths.
- Keep provider-specific behavior behind explicit data and dispatch boundaries.
