# CLAUDE.md

Read and follow `AGENTS.md` before making changes. It is the normative repository guide.

## Required language policy

- All source-code comments must be written in English.
- New developer documentation must be written in English unless a task explicitly updates a Japanese translation.
- Commit subjects and bodies must be written in English.
- Pull request titles, descriptions, review replies, and change summaries must be written in English.
- Identifiers, diagnostics, tests, and benchmark names must use English.

## Align development context

Align is a pre-release language developed in the sibling repository at `../align`. Read `../align/CLAUDE.md`, its language specification, the relevant guide chapters, and compiler-tested examples before using an unfamiliar feature. The local implementation is authoritative for what currently compiles.

Use `make check`, `make run`, `make fmt`, and `make build`; these commands resolve the current compiler through `scripts/alignc`. Do not add an invented project manifest or package workflow while Align has no such supported surface.

Follow `docs/specs/roadmap.md`: establish fixed evaluations and the provider-independent coding loop before expanding the custom inference runtime. Every optimization needs a reproducible measurement tied to time to a passing patch or an explicitly named secondary metric.

## align-llm as a driver for Align

Treat align-llm as a driver whose job is to surface what the Align language and standard library
genuinely need, discovered by building a real client. When align-llm hits a wall, first classify it:
a genuine Align language/stdlib gap, or an app-level concern.

- Do **not** force-build a missing *language* capability into align-llm, and do not lean on fragile
  workarounds for one. Instead, request it from Align.
- Record every genuine language/stdlib request in `docs/align-requests.md` (English), with
  motivation, current-state evidence in `../align`, a proposed idiom-consistent surface, and
  acceptance criteria — written so it can be handed to Align's own tooling and implemented in
  Align's design discipline (a spec under `../align/docs/impl/std-design/`, then implementation and
  tests).
- Respect Align's design when deciding what to request. For example, do not ask Align for a dynamic
  JSON value type: Align deliberately requires declared record types, and `std.json` already covers
  nested structs, `Option<T>`, enums, and unknown-field ignore.
