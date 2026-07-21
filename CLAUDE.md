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
