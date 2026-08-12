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

Update `HANDOFF.md` at a durable capability checkpoint, when a blocker or next action changes, and
before handing work to another environment or agent. Do not update it for each commit, review
comment, check rerun, or pull request metadata change. Keep it concise and current rather than
appending a session transcript. It must identify:

- the current branch and relevant commit;
- the active goal and what is complete, in progress, or not started;
- the exact next steps in priority order;
- the latest verification commands and results;
- blockers, constraints, and decisions that the next session must preserve;
- any intentional uncommitted files that must not be discarded.

`HANDOFF.md` owns durable branch and project continuity plus the expected post-merge next work.
Transient pull request checks, reviews, and attestations live in GitHub and must not be mirrored by
follow-up branch commits. Recording or updating non-content pull request metadata is not a project
state change.

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

## Delivery throughput and documentation proportionality

Organize roadmap work around **consumer-complete capabilities**: the smallest coherent change that
lets a real caller perform a useful new end-to-end behavior. A contract cell, helper, fixture set,
adoption record, or design checkpoint is normally a commit or an acceptance item inside that
capability, not a pull request boundary of its own. Split a capability only when the pieces have
independent consumers, can be verified independently without temporary compatibility behavior, or
belong to genuinely different failure domains such as host-image provisioning and repository code.

Design before coding, but keep design proportional to the decision being made:

- Update an authoritative specification when a public contract, persisted format, ownership or
  process boundary, or cross-module invariant changes. Implementation of an already settled
  contract does not need another narrative design document.
- A separate design pull request is exceptional. Use one when external coordination must consume
  the decision before implementation, or when several independent consumers depend on the same
  broad contract. Otherwise review design and implementation together in the capability branch.
- `HANDOFF.md`, request registers, review evidence, and planning prose support implementation; they
  are not product progress by themselves and must not become an append-only execution journal.
- Line count and elapsed time are diagnostics, never quotas, quality gates, or reasons to pad a
  diff. As a planning expectation, sustained implementation should normally produce a compiling,
  owner-tested checkpoint within roughly eight active hours. Over roughly 24 active hours, a
  capability-sized task should usually deliver a substantial usable result; when its natural scope
  supports it, roughly 5,000-15,000 changed hand-written production-and-test lines can be
  reasonable, and a genuinely large capability may contain around 10,000 production-source lines.
  Report production source, tests/automation, and documentation separately; documentation volume
  does not substitute for working product behavior. If progress is materially smaller, inspect
  design churn, repeated verification, review loops, blockers, and over-splitting before creating
  another smaller pull request.

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
- `ALIGN_LLM_VERIFIED` means every original named focused acceptance target and one final `make ci`
  pass against the same pinned Align revision and final align-llm integration head.
- `CLOSED` means the Align response, ownership model, limits, shipped commit or pull requests, and
  align-llm verification evidence are recorded in the request register.

For a blocking request, stop only the consumer capability that requires the missing functionality.
Do not invent a local compatibility layer, fragile workaround, or code against a proposed API. Record the
blocker and resume condition in both the request and `HANDOFF.md`. Continue independent roadmap work
when it remains valid and does not pre-commit the blocked design. Stop the whole project only when no
safe independent work remains.

For a non-blocking request, record its first expected consumer and continue the current gate. If that
consumer is reached before the request is `ALIGN_MERGED`, reclassify the request as blocking and
pause that dependent consumer.

Resume a blocked consumer only after the capability is merged at a named Align commit, the sibling
release compiler and runtime are rebuilt, `.align-revision` is updated, every original named
focused acceptance target passes, and one final `make ci` passes against that same pin and
integration head. A passing Align test or `make ci` alone does not close the request; align-llm must
verify the capability as the real client.

When several merged Align requests are prerequisites for the same next consumer, adopt them in one
pin update and one real-client verification capability. Request lifecycle entries remain separately
traceable, but they do not require one align-llm pull request each.

## Change discipline

- For roadmap work, use one branch per consumer-complete capability. Keep distinct failure domains
  separate, but combine the design, implementation, owner tests, integration, and directly required
  automation that make one capability usable.
- Repository governance, Align request records, and product implementation may share a pull request
  only when they jointly establish that capability and are separated into comprehensible commits.
  Otherwise keep them independent so each pull request has one observable outcome.
- Keep commits scoped to reviewable internal checkpoints. Commit size is not a pull request size
  limit, and an internal checkpoint does not need its own branch or review cycle.
- Include the relevant check, evaluation, or benchmark result in every pull request description.
- Do not claim performance improvements without a reproducible baseline and measurement.
- Do not commit model weights, generated binaries, credentials, local profiles, or machine-specific
  paths.
- Keep provider-specific behavior behind explicit data and dispatch boundaries.
- Do not assume `.git` is a directory. Automation that intentionally creates repository-internal
  refs or namespaces must resolve the absolute Git common directory once, use that same resolved
  location for setup and cleanup, and verify ordinary-clone, linked-worktree, and abnormal-exit
  cleanup behavior.
- When a persisted artifact records a commit from the current repository or otherwise requires
  in-repository ancestry, define the permitted integration methods as part of the artifact contract.
  Before merging, verify every commit whose contract requires that reachability is an ancestor of
  the exact head and that the selected merge method preserves it. External repository revisions
  require their own repository and reachability rule.

## Design before implementation

Do not use implementation or repeated full-diff review to discover the contract for a non-trivial
consumer capability. Before coding a change that adds a public CLI, persisted format, ownership
boundary, external process or network boundary, or coordinated behavior across three or more modules:

1. Write or update the plan of record under `docs/specs/` and keep one public-contract ledger
   authoritative while drafting. For every public surface, record the exact command, type, or
   signature; inputs and defaults; statuses and errors; ownership, lifetime, and allocation;
   implementation owner; persisted and cache identity; schema version; deterministic validation
   order; prerequisite gate; acceptance test; metric or benchmark; and every source of truth that
   must agree. Mark fields that do not apply as `N/A` with a concrete reason instead of inventing a
   contract.
2. Perform an author-side ledger-to-prose consistency pass before independent review. Every
   normative promise must appear in the public contract, every field must have defined semantics,
   and every acceptance claim must map to a reproducible test or measurement.
3. For cross-cutting implementation, add a closure matrix covering construction, success, failure,
   cleanup, early exit, malformed input, and every affected module. Before coding, each applicable
   cell must name its intended owner module and exact regression test or benchmark, or be explicitly
   deferred.
4. Perform a risk-focused author review before coding. Obtain a separate pre-implementation design
   review only when the contract will be merged for external coordination or when changing it after
   implementation begins would invalidate several independent consumers. Otherwise the capability's
   comprehensive review covers both the settled design and implementation.
5. Implement the smallest consumer-complete vertical capability. A large diff requires clear commit
   structure, owner tests, and review ownership, not an automatic split. Split only at an
   independently usable boundary or a distinct failure domain; never leave `main` with a dormant
   producer, a hypothetical consumer, or duplicated temporary behavior solely to reduce line count.

For applicable surfaces, the contract ledger and closure matrix must also cover:

- public argument and result ownership, lifetime, allocation, validation, construction, move-in,
  move-out, source nulling, replacement, return, and cleanup or `Drop`;
- text and wire encoding, embedded NUL handling, deterministic error precedence, and validation
  before side effects;
- canonical persisted or exchanged scalar widths, tags, field and sequence order, malformed-input
  rejection, and independently checked semantic-to-byte and byte-to-semantic golden vectors;
- explicit CLI and build inputs without unnamed ambient configuration;
- overlap exclusion for process-global or connection-global state, failed-second-operation
  behavior, exhaustion, error, and cleanup restoration order;
- every combination of individually supported public entrypoints that can share state in one
  process tree, including aggregate-plus-aggregate and aggregate-plus-focused operations; classify
  and test each combination as serialized, rejected before side effects, or explicitly unsupported,
  and separately state the policy for concurrent independent processes;
- compatibility at the minimum declared tool or platform version, exercised by a required acceptance
  environment at that version; newer environments are supplementary evidence, not a substitute;
- every option or environment-isolation boundary in both directions: rejected or cleared state must
  not cross it, while each documented input that must survive it retains its exact value and
  documented source or precedence semantics;
- the Cartesian product of detail levels, discriminators, verification states, and option states,
  including exact field presence, row order, ordinal, and unavailable-value rules;
- nominal versus structural identity for every fingerprint, with the complete reachable definition
  graph included when identity is structural;
- a producer-owned table or thunk for every promised runtime-inspection field, without hidden
  reflection or artifact/source reads;
- syntax checks for normative examples, with declarations shown separately from positional call
  expressions; and
- milestone ordering that prevents any slice from consuming a decision or capability assigned to a
  later slice.

Mark an inapplicable dimension as `N/A` with its reason; omission is not a decision.

Keep the plan authoritative during implementation. When a finding changes the public surface,
update the plan first and propagate that decision through code, tests, and documentation in one
pass. Independent review is a validation gate, not the primary design-completion loop. Before code
review, perform a matrix-to-diff pass: every applicable cell must point to the actual implementation
and a passing regression test or to an explicit deferral in the plan.

For ownership or other cross-cutting implementation, the closure matrix must additionally
enumerate:

- type formation and validation, construction, move-in, move-out, source nulling, `Drop`,
  replacement, and return for every affected implementation-only ownership type;
- every affected control path, including `if`, `match`, `else`, `?`, `map_err`, branch joins, loop
  joins, early exits, and malformed input; and
- generic monomorphization, interface serialization, whole-program and per-unit compilation,
  runtime ownership provenance, and allocation parity.

## Autonomous execution and convergence

When an agent is asked to continue through roadmap work, a completed pull request is a checkpoint,
not a stopping condition. Prepare `HANDOFF.md` on the merging branch to describe the expected
post-merge checkpoint. After the merge, refresh `main` and start the next eligible consumer
capability; correct merge-dependent handoff details in the first commit of that branch. Do not
create a recursive handoff-only pull request solely to record that the previous pull request merged. Stop
only when the user asks, the roadmap has no eligible work, or no safe independent work remains
after blockers are recorded.

Elapsed time is not a stopping criterion for a useful command, review, test, or investigation.

- Inspect actual progress at least once per minute while work is running. Check process state, new
  output, the latest completed phase, and whether the work is producing new relevant evidence.
  Report the current phase and that evidence during extended work.
- Stop or redirect only after evidence of a stall, repeated analysis, scope drift, an external
  capacity failure, or an actual tool failure. Do not repeat an unchanged failing invocation
  without new evidence that it can succeed.
- Treat an automation timeout as the end of that invocation only. Preserve useful logs, findings,
  and completed phases, then resume from the first unfinished area instead of restarting the whole
  scope.
- Keep every iteration evidence-producing: an implemented and owner-tested portion of the same
  capability, a resolved root-cause class, a new measurement, or a recorded blocker. If roughly
  eight active hours pass without a compiling owner-tested checkpoint, audit the dominant cost and
  redirect it. If roughly 24 active hours pass without a consumer-usable result or substantial
  implementation progress, re-evaluate the capability boundary. The correction may be to combine a
  prematurely separated producer and consumer; do not automatically create a smaller pull request.
- When a reviewer finds a bug, audit the complete diff for the same root-cause class and fix that
  class in one pass. If the conditionally required final review finds any issue requiring another
  non-trivial change, stop the local patch loop, reopen the closure matrix, identify the missed
  invariant, and redesign or re-split the pull request before continuing.

After each consumer capability, or after a review/CI/merge incident that exposed a reusable process
problem, perform one bounded retrospective:

- inspect the final review findings and dispositions, CI and local-check failures, merge or
  worktree friction, scope surprises, and commands whose names overstated or understated their
  actual coverage;
- distinguish reusable repository knowledge from one-off execution conditions and preferences;
- for each reusable lesson, add or strengthen the smallest rule, checklist item, regression test,
  or automation guard when its value exceeds its maintenance cost, or queue it with an exact trigger;
  do not create a governance pull request for every ordinary finding; and
- keep the evidence in the merged pull request and checks. Do not rewrite the merged branch, create
  a retrospective-only handoff pull request, or mix the improvement into an unrelated product
  slice.

## Verification timing and review convergence

Classify the changed surface before choosing verification. Verification is evidence for a coherent
capability or internal checkpoint, not an edit-loop ritual.

- A documentation/specification/HANDOFF-only change uses `git diff --check` and the applicable
  Markdown, schema, link/reference, or other targeted static checks available for the changed
  surface; unavailable checks are recorded as `N/A` with a concrete reason. It does not run source
  tests, `make check`, `make build`, `make ci`, or the full hosted check unless it also changes
  executable automation, workflow files, the Makefile, a build or toolchain input, a fixture or
  acceptance corpus, `.align-revision`, `.gitattributes`, or another executable contract boundary.
- A pure or local implementation checkpoint runs its focused compiler, unit, fixture, or smoke
  checks once after it is coherent. Do not run the aggregate suite after each small edit.
- Keep core aggregates bounded to functional integration and stable regressions that every change
  must protect. Security, resource-limit, race, fuzz, stress, platform qualification, and mutation
  suites use named focused commands and run when their owning boundary changes or an explicit audit
  requires them. A focused qualification may remain outside every aggregate; its owner must name
  the exact invocation. Benchmarks run only for a performance claim or a named measurement gate.
- Adding a test does not imply adding it to `make ci`. Prefer the narrowest owner target that catches
  the regression, and do not make one smoke helper invoke an unrelated qualification suite merely
  to obtain aggregate reachability.
- Run the full aggregate (`make ci` locally, or its applicable hosted equivalent) only at a named
  implementation/adoption gate, before a merge that changes integration behavior, after a pin or
  check-topology change, or when fresh base-tip integration evidence is required. A docs-only
  change is not a reason to run it.
- Before publishing a completed branch, use `python3 scripts/pre-pr` with the narrow owner command.
  Its shared classifier selects documentation, hosted, or fresh-image verification, and its stamp
  belongs only to the exact unchanged HEAD. Use `--plan` only to inspect selection; it is not check
  evidence. Do not replace its required installed profile with a Docker-unavailable skip or an
  ambient `DOCKER_HOST` endpoint.
- Batch related edits before verification. After review, apply all valid findings from the one
  comprehensive review in one consolidated repair, then rerun only affected verification. An
  ordinary repair implementing recorded findings does not require another review.
- Use one comprehensive review for a stable capability candidate, preferably before publishing the
  pull request. A second review is allowed only when the repair materially expands or changes
  behavior, design, specification, or governance. If that conditional final review finds another
  non-trivial issue, stop the local repair loop and re-scope or redesign the capability instead of
  repeating review and repair indefinitely.
- Every pull request records exact verification commands and results, or the concrete reason a check
  is `N/A`. `HANDOFF.md` retains only the latest durable evidence needed to resume the capability.

## Pull request review and merge workflow

Review is mandatory before merging any pull request that changes code, an authoritative design or
specification, or repository governance. Opening a pull request is not completion, and an agent
must not open and immediately merge it.

1. Finish a coherent, independently mergeable capability; do not use a draft pull request as a
   scratchpad for basic correctness work.
2. Run the checks, evaluations, or benchmarks appropriate to the changed owners.
3. Run one comprehensive review of the stable candidate diff. Apply `docs/review-checklist.md` to
   the changed surface and use high review effort plus a fresh independent adversarial reviewer for
   a non-trivial change. The reviewer must finish the assigned scope and report all findings before
   content editing resumes. A very large change may use complementary reviewers with explicitly
   disjoint risk areas; do not ask several reviewers to repeat the same whole-diff review.
4. Scrutinize every finding against the code. Apply valid findings; do not apply suggestions
   blindly. Record a concrete reason for rejecting any finding. Audit each accepted root-cause
   class across the complete diff, then apply all accepted findings in one consolidated follow-up
   commit when practical.
5. Rerun affected owner verification. An ordinary repair that implements only
   findings already recorded by the comprehensive review does not require another review. Verify
   directly that the repair contains no unrelated behavior or scope.
6. Run one final comprehensive review only when the repair substantially expands the reviewed
   scope, changes the implementation approach, or materially changes behavior, design, an
   authoritative specification, or repository governance. Typographical corrections, narrow
   fixes implementing an existing finding, test-only corrections, and review-record metadata do
   not trigger it. This is the last review round: if it finds another issue requiring a non-trivial
   change, stop and re-scope or redesign instead of starting a repair/re-review loop.
7. Open or update the pull request with an English title and description, the exact verification
   results, relevant baseline or measurement, and the review envelope. Publication is a delivery
   checkpoint, not a trigger to repeat a completed review.
8. Merge only after required checks pass, every finding has a disposition, and no valid finding
   remains unresolved.

### Review attestations and terminal merge state

Review evidence is external and immutable with respect to the reviewed branch. The comprehensive
review envelope records the reviewed head SHA, base-branch tip SHA, merge-base SHA, reviewer, review
kind and scope, verdict, and the complete finding list. Use `none` explicitly when there are no
findings. The pull request records every finding disposition and identifies the single consolidated
repair commit, if any. Check evidence separately records the final head SHA, tested base-tip SHA,
merge-base SHA, tested integration commit or tree identity, check name, status, and external
record. The tested integration may be the head commit only when its merge base equals the tested
base tip; otherwise it must identify a synthetic merge or equivalent tree that combines those exact
head and base-tip SHAs.

- Record the comprehensive review envelope in a native GitHub review or dedicated pull request
  comment after publication, including when the review happened before the pull request existed.
  GitHub checks and statuses are check evidence only and never satisfy the review requirement.
- When the conditional final review is required, its external record contains the same complete
  SHA-bound envelope, finding list, and dispositions as the initial comprehensive review.
- Pull request descriptions, reviews, comments, checks, and statuses are non-content metadata.
  Recording them must not modify the branch or trigger another review cycle.
- A repair push does not invalidate the comprehensive review merely because its head SHA changes.
  Bind the recorded findings to their dispositions and repair commit, inspect the final delta for
  unrelated changes, and rerun affected checks. Require the one final review only under step 6.
- A base-tip change requires fresh integration check evidence. It requires another review only
  when its effect meets one of step 6's substantial or material change triggers.

A pull request is merge-ready when it has the comprehensive review envelope, every finding has a
recorded disposition, any required one-time final review is clean, required checks pass for the
final integration, and no valid finding remains unresolved. Do not require multiple independent
review envelopes for the same unchanged diff.

### Claude Code review adapter

- A human starts the dedicated review with `/code-review`.
- When Claude drives the pull request flow autonomously, use an available model-invocable review
  command such as `/review` or an independent adversarial subagent for the one comprehensive
  review.
- Do not silently skip review when a particular command is unavailable.

### Codex review adapter

- A human starts the dedicated reviewer with `/review`.
- Non-interactive automation may use `codex review --base <branch>`,
  `codex review --uncommitted`, or `codex review --commit <sha>`.
- When Codex drives the pull request flow autonomously, use a fresh independent adversarial
  subagent for the one comprehensive review. Do not pretend to invoke a user-only composer command
  from inside an agent turn.
