# CLAUDE.md

This file is the canonical repository guide for both Claude Code and Codex. `AGENTS.md` is a
compatibility symlink for Codex. Shared guidance must be edited here, not copied between
tool-specific files.

Tool-specific adapter instructions may translate commands, but must preserve the requirements and
outcomes defined here. Keep tool-specific permissions, sandbox settings, hooks, skills, and plugin
manifests in their native configuration locations.

## Continuity across environments

`HANDOFF.md` is the living source of truth for the current execution state. At the start of a new
session or on a different machine, read `HANDOFF.md` after this guide and before continuing work.
Conversation history and per-machine memory are not durable project state.

Update `HANDOFF.md` after a material change to the active work and before handing work to another
environment or agent. Keep it concise and current rather than appending a session transcript. It
must identify:

- the current branch and relevant commit;
- the active goal and what is complete, in progress, or not started;
- the exact next steps in priority order;
- the latest verification commands and results;
- blockers, constraints, and decisions that the next session must preserve;
- any intentional uncommitted files that must not be discarded.

Architecture and delivery order remain authoritative in `docs/specs/`; `HANDOFF.md` records only the
current position within those plans. Do not put credentials, machine-specific secrets, or disposable
scratch details in it. When no work is active, say so explicitly and name the next roadmap item.

## Repository purpose

This repository implements a local LLM coding system in the Align programming language. It has two
independently testable components:

- `align-coder`: repository-aware generation, verification, repair, evaluation, and local learning.
- `align-runtime`: efficient local inference across GPU memory, system memory, and NVMe.

The roadmap deliberately starts with `align-coder` and existing model providers. Do not make
`align-coder` wait for the custom runtime.

## Align source of truth

Align is under active development in the sibling repository at `../align`. Before writing or
reviewing Align code, read `../align/CLAUDE.md` and then the relevant authoritative material there:

- `../align/draft.md` for the complete language specification.
- `../align/docs/language-spec.md` for the condensed specification.
- `../align/docs/design-notes.md`, `history.md`, `non-goals.md`, and `open-questions.md` before
  proposing language behavior.
- `../align/docs/guide/` for supported syntax and standard-library APIs.
- `../align/examples/` for compiler-tested examples.
- `../align/docs/impl/15-pkg-web-plan.md`, `../align/docs/impl/pkg-design/web.md`, and
  `../align/apps/web/pkg/` for the in-progress REST framework.

Treat the checked-out compiler and its tests as the implemented surface. Do not invent a manifest,
package resolver, test runner, or language feature that Align does not yet support. If this project
needs missing Align functionality, record it in `docs/align-requests.md` and make the smallest
coordinated change in the Align repository separately. align-llm is a driver for discovering
Align's real needs: request missing language capabilities from Align rather than forcing them into
this project.

## Project plans

- `docs/specs/align-llm.md` defines the system architecture and principles.
- `docs/specs/roadmap.md` defines delivery order and evaluation gates.
- `docs/align-development.md` explains the local toolchain integration.

Preserve the central metric: time to a passing patch. Prefer measured, repository-specific
improvements over broader but unverified feature coverage. Establish fixed evaluations and the
provider-independent coding loop before expanding the custom inference runtime. Every optimization
needs a reproducible measurement tied to time to a passing patch or an explicitly named secondary
metric.

## Language and international collaboration

- Write all source code, source-code comments, identifiers, user-facing diagnostics, CLI output,
  test names, benchmark names, and issue references in English.
- Write new developer documentation in English. Existing Japanese planning documents may remain in
  Japanese. When an English original and a Japanese translation both exist, update the English
  original first and keep the translation synchronized.
- Write commit subjects and commit bodies in English.
- Write pull request titles, descriptions, review replies, and change summaries in English.
- Write release notes, release titles, release descriptions, and annotated tag messages in English.
- Do not introduce Japanese into code, development records, or repository automation. Japanese is
  allowed only in explicitly maintained translations and end-user documentation intended to be
  bilingual.

## Development workflow

Use the repository wrapper so local development follows the current sibling Align checkout:

```text
make check
make run
make fmt
make build
```

The wrapper resolves the compiler in this order: `ALIGNC`, the sibling release build, the sibling
debug build, then `alignc` on `PATH`. Run `make check` after every semantic change and `make fmt`
before committing Align source.

Keep modules explicit and data-oriented. One `.align` file is one module, imports define the build
graph, public API uses `pub`, fallible work returns `Result`, and allocation or ownership must remain
visible.

## align-llm as a driver for Align

When align-llm hits a wall, first classify it as a genuine Align language or standard-library gap,
or as an application-level concern.

- Do not force-build a missing language capability into align-llm or rely on a fragile workaround.
  Request it from Align.
- Record every genuine language or standard-library request in `docs/align-requests.md`, in English,
  with motivation, current-state evidence from `../align`, a proposed idiom-consistent surface, and
  acceptance criteria. Write it so Align's own tooling can implement it in Align's design
  discipline: a specification under `../align/docs/impl/std-design/` or the relevant design
  directory, followed by implementation and tests.
- Respect Align's existing design when deciding what to request. For example, do not ask for a
  dynamic JSON value type: Align deliberately requires declared record types, and `std.json`
  already covers nested structs, `Option<T>`, enums, and unknown-field ignore.

### Request blocking and lifecycle

Every new or reopened entry in `docs/align-requests.md` must declare:

```text
Status:
Priority:
Blocking: yes | no
Blocked gate or slice:
Independent work that may continue:
Resume condition:
Align commit or pull request:
align-llm verification:
```

Use this lifecycle:

```text
PROPOSED
  -> ACCEPTED
  -> IMPLEMENTING
  -> ALIGN_MERGED
  -> ALIGN_LLM_VERIFIED
  -> CLOSED
```

- `PROPOSED` means align-llm has demonstrated a genuine gap but Align has not accepted a design.
- `ACCEPTED` means Align has accepted the need and recorded the intended design or implementation
  direction.
- `IMPLEMENTING` means a separate Align change is in progress. Do not write align-llm code against
  its hypothetical surface.
- `ALIGN_MERGED` means the capability is available at a named Align commit. Run the required Align
  release build, update `.align-revision`, and adopt the shipped surface.
- `ALIGN_LLM_VERIFIED` means the original acceptance gate passes in align-llm with `make ci`.
- `CLOSED` means the Align response, ownership model, limits, shipped commit or pull requests, and
  align-llm verification evidence are recorded in the request register.

For a blocking request, stop only the gate or slice that requires the missing capability. Do not
invent a local compatibility layer, fragile workaround, or code against a proposed API. Record the
blocker and resume condition in both the request and `HANDOFF.md`. Continue independent roadmap work
when it remains valid and does not pre-commit the blocked design. Stop the whole project only when no
safe independent work remains.

For a non-blocking request, record its first expected consumer and continue the current gate. If that
consumer is reached before the request is `ALIGN_MERGED`, reclassify the request as blocking and
pause that dependent slice.

Resume a blocked slice only after the capability is merged at a named Align commit, the sibling
release compiler and runtime are rebuilt, `.align-revision` is updated, and the original
acceptance gate passes through `make ci`. A passing Align test alone does not close the request;
align-llm must verify the capability as the real client.

## Change discipline

- For roadmap work, use one branch per gate or enabling slice. Do not mix repository-governance
  changes, Align request records, and product implementation in one pull request when they can be
  reviewed independently.
- Keep commits small and scoped to one roadmap gate or enabling change.
- Include the relevant check, evaluation, or benchmark result in every pull request description.
- Do not claim performance improvements without a reproducible baseline and measurement.
- Do not commit model weights, generated binaries, credentials, local profiles, or machine-specific
  paths.
- Keep provider-specific behavior behind explicit data and dispatch boundaries.

## Pull request review and merge workflow

Review is mandatory before merging any pull request that changes code. Opening a pull request is not
completion, and an agent must not open and immediately merge it.

1. Run the checks, evaluations, or benchmarks appropriate to the change.
2. Open the pull request with an English title and description. Include the exact verification
   results and any relevant baseline or measurement.
3. Review the open pull request before merging. Use high review effort for any non-trivial change.
   Apply `docs/review-checklist.md` to the changed surface.
   When the tooling supports subagents, also use an independent adversarial reviewer for
   non-trivial changes to look for correctness, ownership, error-handling, test-coverage, and
   regression risks.
4. Scrutinize every finding against the code. Apply valid findings; do not apply suggestions
   blindly. Record a concrete reason for rejecting any finding.
5. Push the review follow-up. Re-run affected verification, and repeat review when the follow-up
   materially changes behavior or design.
6. Merge only after required checks pass and no valid review finding remains unresolved.

### Claude Code review adapter

- A human starts the dedicated review with `/code-review`.
- When Claude drives the pull request flow autonomously, use an available model-invocable review
  command such as `/review` and an independent adversarial subagent.
- Do not silently skip review when a particular command is unavailable.

### Codex review adapter

- A human starts the dedicated reviewer with `/review`.
- Non-interactive automation may use `codex review --base <branch>`,
  `codex review --uncommitted`, or `codex review --commit <sha>`.
- When Codex drives the pull request flow autonomously, inspect the pull request or base diff and
  use a fresh independent adversarial subagent. Do not pretend to invoke a user-only composer
  command from inside an agent turn.
