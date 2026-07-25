# Developing align-llm with Align

Align is developed in parallel with this project. There is no Align project manifest, package registry, general test runner, or configurable source search path yet. A program starts from one `.align` entry file, and imports resolve to files beneath that entry file's directory.

## Local repository layout

The default development layout keeps the language and engine repositories next to each other:

```text
Projects/
  align/
    target/release/alignc
    docs/
    examples/
    apps/web/pkg/
  align-llm/
    src/main.align
```

`scripts/alignc` selects a compiler in this order:

1. The executable named by `ALIGNC`.
2. `../align/target/release/alignc`.
3. `../align/target/debug/alignc`.
4. `alignc` on `PATH`.

This makes local work track the active language checkout while still allowing packaged compilers and CI-specific paths.

## What to read

Use the sibling repository as the source of truth:

- Start with `../align/CLAUDE.md` for current implementation status and invariants.
- Read `../align/draft.md` for the authoritative language design.
- Read `../align/docs/guide/` for supported day-to-day syntax and APIs.
- Search `../align/examples/` and compiler tests for compiling examples.
- Check `../align/docs/open-questions.md` before depending on unsettled behavior.
- For HTTP work, read `../align/docs/impl/15-pkg-web-plan.md`, `../align/docs/impl/pkg-design/web.md`, and `../align/apps/web/pkg/`.

Do not copy the in-progress web package into this repository merely to make imports resolve. Until Align gains a package mechanism, either keep an application independent of it or coordinate an explicit vendoring decision with version and update rules.

## Supported development loop

```sh
make check
make fmt
make run
```

`check-per-unit` validates imported modules through their public interfaces. The formatter rewrites only meaningless syntax variation and should run before a commit. Use `emit-mir`, `emit-llvm`, `explain-opt`, and `size` directly through the wrapper when validating performance claims:

```sh
./scripts/alignc emit-mir src/main.align
./scripts/alignc explain-opt src/main.align --verbose
./scripts/alignc size src/main.align --profile tiny
```

## Managing language dependencies

When the engine needs a feature that does not compile in the current Align checkout:

1. Confirm the feature is part of the settled language design.
2. Reduce the need to the smallest compiler or standard-library capability.
3. Register it in `docs/align-requests.md` with the lifecycle and blocking metadata required by
   `CLAUDE.md`.
4. If it is blocking, pause only the dependent gate or slice and record the resume condition in
   `HANDOFF.md`. Continue valid independent work without assuming the proposed surface.
5. Implement and test that capability in `../align` as a separate, reviewable change.
6. Update this repository only after the Align change is available at a named commit or release.
7. Rebuild the pinned Align release compiler, update `.align-revision`, run `make ci`, and record the
   real-client verification before closing the request.

This separation keeps engine work reproducible and prevents application code from becoming an accidental language specification.

## Provider development

The C1 provider surface lives in `src/model.align` and `src/provider.align`. `model.ProviderConfig`
holds the explicit provider kind, endpoint, model, API key, timeout, and optional llama.cpp
tokenizer endpoint. `provider.generate`, `provider.stream`, `provider.count_tokens`, and
`provider.model_info` dispatch only through the declared `ProviderKind` enum.

The OpenAI adapters send `/v1/chat/completions`; the llama.cpp adapter sends `/completion` and can
use `/tokenize` for exact counts. OpenAI-compatible token counts are deliberately marked as
estimated. Cloud OpenAI requires an `https://` endpoint and reads its bearer key from `std.env`.
Successful and failed calls are persisted through `result.GenerationRecord`, whose
`schema_version` is `2`, whose `error_code` preserves an HTTP status when available, and whose
shape is independent of the adapter.

Use `make provider-smoke` for the focused fixture. It starts a temporary HTTP server, exercises
local OpenAI-compatible and llama.cpp generate/stream calls, checks environment-backed Bearer
authentication, Cloud HTTP rejection, SSE failure handling, exact tokenizer counts, HTTP status
diagnostics, and the shared result records. Real Cloud OpenAI calls require HTTPS.
