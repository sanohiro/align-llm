# CLAUDE.md

This is the canonical repository guide for Claude Code and Codex. `AGENTS.md` is a compatibility
symlink. Keep shared project rules here and tool-specific permissions, hooks, skills, and plugins in
their native configuration.

## Start here

1. Read `HANDOFF.md` for the current branch, checkpoint, blockers, and next action.
2. Read only the source of truth that owns the planned change:
   - `docs/specs/align-llm.md` for architecture and principles;
   - `docs/specs/roadmap.md` for delivery order and evaluation gates;
   - `docs/align-development.md` for the local Align toolchain;
   - `docs/review-checklist.md` when designing a triggered high-risk surface or reviewing a stable
     candidate.
3. Before writing or reviewing Align code, read `../align/CLAUDE.md` and the relevant checked-in
   specification, guide, example, compiler test, or package plan in that repository.

The named Align commit and its compiler tests define Align's implemented surface. The sibling
checkout remains the source of truth when actively coordinating Align changes, but ordinary
align-llm commands use the exact `.align-revision` toolchain. Do not invent a manifest, resolver,
test runner, standard-library API, or language feature that Align does not ship.

## Product and delivery order

This repository implements a local LLM coding system in Align:

- `align-coder`: repository-aware generation, verification, repair, evaluation, and learning;
- `align-runtime`: local inference across GPU memory, system memory, and NVMe.

Deliver `align-coder` against existing providers before making it depend on the custom runtime. The
primary metric is time to a passing patch. Any optimization claim needs a reproducible baseline and
measurement against that metric or a named secondary metric.

Roadmap work is organized as a **consumer-complete capability**: the smallest coherent change that
lets a real caller perform useful end-to-end behavior. Design, implementation, owner tests, and
directly required automation normally belong in that capability. Split only for an independently
usable consumer boundary or a distinct failure domain; an internal checkpoint is a commit or test,
not automatically a pull request.

## Choose the workflow before working

Classify the changed surface first and follow only its row. Reclassify when the diff grows.

| Change | During development | Before publication | Review |
| --- | --- | --- | --- |
| Classifier-eligible non-normative Markdown additions/modifications | Relevant consistency check | `python3 scripts/pre-pr` | Not required |
| Classifier-eligible authoritative specification or governance additions/modifications | Author consistency check | `python3 scripts/pre-pr` | One comprehensive review |
| Local implementation checkpoint | Narrow owner test after a coherent batch | Do not publish; reclassify as an executable consumer capability first | No repeated full-diff review |
| Executable consumer capability | Narrow owner tests; named qualification when its boundary changes | `python3 scripts/pre-pr --owner-test LABEL -- COMMAND ...` | One comprehensive review |
| Performance claim | Owner test plus reproducible benchmark, whose baseline includes a cost ceiling recorded before implementation (the ppm-floor rule in `docs/specs/c8-speed-first.md` section 1) | Applicable row above, with baseline and result | Include measurement risk |

`scripts/pre-pr` is the shared final classifier. Its `--plan` mode explains the selected checks but
is not evidence. The successful stamp belongs to the exact unchanged `HEAD`; commit, amend, or
rebase invalidates it. Do not replace a required installed profile with a Docker skip or an ambient
`DOCKER_HOST` endpoint.

The Markdown rows apply only when the classifier selects `docs`. Deletions, renames, unknown
statuses, and other fail-closed cases select executable preflight and require an applicable owner
command; review remains determined by the changed content. Any implementation checkpoint selected
for publication must first become a consumer-complete executable row, including its preflight and
review requirements.

This table is the normal path. Do not promote an isolated incident into a permanent gate without a
recurring failure class, an identified owner, and maintenance value greater than its cost.

## Continuity

`HANDOFF.md` is durable execution state, not a transcript. Update it when the active capability,
blocker, resume condition, next action, or durable verification checkpoint changes, and before
moving work to another environment. Keep it concise and record:

- branch and relevant commit;
- complete, active, and not-started work;
- exact next actions in priority order;
- latest durable verification commands and results;
- blockers, constraints, decisions, and intentional uncommitted files.

GitHub owns transient review, check, and pull-request metadata. Do not commit a handoff update for
each push, rerun, comment, or merge-status change. Architecture and ordering remain in `docs/specs/`.
Do not record credentials, local secrets, disposable paths, or a session diary. When no work is
active, say so and identify the next roadmap item.

## Implementation discipline

Use the repository wrapper so work follows the exact `.align-revision` toolchain:

```text
make check
make run
make fmt
make build
```

The wrapper resolves the authenticated fresh compiler when required, then an explicit `ALIGNC`,
then an explicit `ALIGN_REPO`, and otherwise materializes the managed pinned release toolchain
outside Git through `scripts/align-toolchain`. It never selects `../align` or `alignc` on `PATH`
implicitly. Use `scripts/align-toolchain ensure compiler` to prepare it explicitly. Set `ALIGNC` or
`ALIGN_REPO` only when intentionally testing a different compiler or active Align checkout. Run the
narrow owning check after a coherent semantic batch and `make fmt` before committing Align source.
Run aggregates at the gates defined below, not after every edit.

Keep modules explicit and data-oriented. One `.align` file is one module, imports define the build
graph, public APIs use `pub`, fallible work returns `Result`, and allocation and ownership remain
visible. Keep provider-specific behavior behind explicit data and dispatch boundaries.

Do not commit weights, generated binaries, credentials, local profiles, or machine-specific paths.
Do not assume `.git` is a directory: repository-internal refs and namespaces must use one resolved
Git common directory and cover ordinary clones, linked worktrees, and abnormal cleanup. A persisted
artifact that requires in-repository ancestry must define allowed integration methods and verify
reachability from the exact merging head.

## Proportional design gate

Update the authoritative plan under `docs/specs/` before coding only when changing a public CLI or
API, persisted or exchanged format, ownership/process/network boundary, or coordinated invariant
across three or more modules. Implementing an already-settled contract does not require another
narrative design or a design-only pull request.

For a triggered design gate:

1. Keep one public-contract ledger authoritative. Record exact surfaces, inputs/defaults,
   results/errors, ownership/allocation, owner module, persisted/cache identity, schema version,
   validation order, prerequisites, acceptance evidence, and metrics. Mark genuinely inapplicable
   fields `N/A` with a reason.
2. For cross-cutting work, add a closure matrix for construction, success, failure, malformed input,
   early exit, cleanup, and each affected module. Name the implementation and exact regression test
   for each applicable cell before coding.
3. Perform one author ledger-to-prose consistency pass, then implement the smallest
   consumer-complete vertical capability.
4. Before review, map applicable ledger and matrix cells to the final diff and passing evidence or
   to an explicit deferral in the plan.

Use the triggered contract and closure questions in `docs/review-checklist.md`; they are not tasks
for changes outside this gate. A separate pre-implementation review is exceptional: use it only
when external coordination must consume the contract first or several independent consumers would
be invalidated by a later change.

Keep the plan authoritative. When implementation changes a public promise, update plan, code,
tests, and directly affected documentation together. Review validates a settled candidate; it is
not the primary contract-discovery loop.

## Align capability requests

Treat `align-llm` as a continuing real-client testbed for discovering what Align itself must ship.
Classify every missing capability encountered—not only an active blocker—as an application concern
or a genuine Align language, compiler/runtime, or standard-library gap. Record the genuine gap even
when it is non-blocking or an application workaround appears possible; a workaround is not a reason
to hide a language-owned requirement. Do not build a compatibility layer or write against a
proposed API. Record genuine gaps in `docs/align-requests.md` with current sibling evidence, an
Align-consistent proposed surface, acceptance criteria, and these fields:

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

The lifecycle is:

```text
PROPOSED -> ACCEPTED -> IMPLEMENTING -> ALIGN_MERGED -> ALIGN_LLM_VERIFIED -> CLOSED
```

- Do not consume a hypothetical surface during `PROPOSED`, `ACCEPTED`, or `IMPLEMENTING`.
- At `ALIGN_MERGED`, name the shipped Align commit, update `.align-revision`, materialize its managed
  release compiler/runtime, and adopt the real surface.
- `ALIGN_LLM_VERIFIED` requires every originally named acceptance target that owns the changed
  consumer boundary and the final integration owner named by that request. A pin change alone does
  not add `make ci`, a platform profile, or another qualification to the request.
- `CLOSED` records the shipped surface, ownership, limits, links, and client evidence.

A blocking request pauses only its dependent consumer. Record the blocker and resume condition in
the register and `HANDOFF.md`, and continue safe independent work. If a non-blocking request reaches
its first consumer before merge, reclassify it as blocking. Batch merged prerequisites for the same
consumer into one pin update and real-client verification capability.

## Verification

Verification is evidence for a coherent checkpoint, not an edit-loop ritual.

- Classifier-eligible Markdown additions/modifications run `git diff --check` plus applicable static
  consistency checks. They do not run source tests or aggregates unless they change an executable
  contract boundary such as a workflow, Makefile, build input, fixture/corpus, `.align-revision`,
  or `.gitattributes`. Deletions and renames fail closed as described above.
- Local implementation runs the narrow compiler, unit, fixture, or smoke owner once the batch is
  coherent.
- `scripts/pre-pr` runs every publication check selected by the shared classifier. Do not manually
  duplicate its aggregate sequence.
- A pure `.align-revision` adoption runs the request owner plus managed-toolchain materialization
  and verification locally; ordinary hosted CI owns the broad consumer graph. It does not select
  the installed platform profile. Any other executable path retains its normal classifier scope.
- `make ci` is the complete capable-host integration graph, not every qualification. Run it when a
  request changes aggregate membership, check topology, or integration behavior, when its accepted
  ledger names the aggregate, or for explicit fresh base-integration evidence. Do not select it for
  an otherwise unrelated `.align-revision` change.
- Security, resource, race, fuzz, stress, platform, mutation, and benchmark suites remain named
  focused qualifications. Run them only when their owner boundary changes or an explicit audit
  requires them. Changing `.align-revision` alone is not a change to every such owner.
- Align CI owns the compiler's supported-platform correctness. An align-llm adoption adds a native
  platform qualification only when it changes an align-llm target-local boundary, makes a
  target-specific performance claim, or records a concrete gap in the provider's CI coverage.
- Adding a regression does not automatically add it to an aggregate. Prefer the narrowest stable
  owner and document focused commands not reached by an aggregate.

Every pull request records exact commands and results or a concrete `N/A` reason. Do not claim that
an aggregate covers a focused target without checking its actual command graph.

## Review and merge

Code, authoritative design/specification, and governance require review before merge. Use one
comprehensive review of the stable candidate and apply `docs/review-checklist.md` only to the risks
present in the diff.

1. Finish a coherent candidate and its owner verification.
2. Complete one fresh high-effort review before content repair begins. One reviewer covers the
   whole diff; complementary reviewers are allowed only for explicitly disjoint risks in a very
   large change.
3. Validate findings rather than applying them blindly. Audit each accepted root-cause class across
   the complete diff and consolidate repairs when practical. Record reasons for rejected findings.
4. Rerun affected owner verification and inspect the repair delta for unrelated behavior. A narrow
   repair of recorded findings does not require another full review.
5. A single final comprehensive review is required only if repair substantially expands scope,
   changes approach, or materially changes behavior, design, specification, or governance. If it
   finds another issue needing non-trivial change, re-scope or redesign instead of starting another
   repair/review loop.
6. Publish the English pull request with exact verification, measurement when applicable, and the
   review envelope. Merge only after required checks pass, every finding has a disposition, and no
   valid finding remains unresolved.

The comprehensive review record contains reviewed head, base-branch tip, merge base, reviewer,
kind/scope, verdict, and complete findings (`none` when clean). The pull request records finding
dispositions and the consolidated repair commit. Check evidence separately identifies final head,
tested base tip, merge base, tested integration commit/tree, check names, results, and links. Use a
synthetic merge or equivalent tree when the tested head is not directly based on the tested base
tip.

Record the review envelope in a native GitHub review or dedicated comment. Checks are verification,
not review. A repair push does not invalidate the original review when findings, dispositions, and
repair commit remain bound and the repair did not trigger the final-review rule. A base-tip change
requires fresh integration evidence, but another review only when it materially changes the
reviewed risks. Metadata updates do not modify the branch or trigger review.

## Execution and convergence

When asked to continue roadmap work, a merged pull request is a checkpoint, not a stopping
condition. Refresh `main`, start the next eligible consumer capability, and correct merge-dependent
handoff details in that branch. Stop only when asked, the roadmap has no eligible work, or no safe
independent work remains after blockers are recorded.

For long work, inspect process state and new evidence at least once per minute and report the active
phase. A timeout ends only that invocation. Preserve useful output and resume at the first unfinished
phase. Redirect only on evidence of a stall, repeated analysis, scope drift, external capacity
failure, or tool failure; do not repeat an unchanged failure without new evidence.

Time and line count are diagnostics, not quotas. If roughly eight active hours pass without a
compiling owner-tested checkpoint, audit the dominant cost. If roughly 24 hours pass without a
consumer-usable result or substantial implementation, reconsider the capability boundary; the
answer may be to combine prematurely split producer and consumer work rather than split again.

After a capability or meaningful CI/review/merge incident, perform one bounded retrospective.
Promote only reusable lessons into the smallest valuable rule, test, or automation guard. Keep
one-off evidence in the pull request, do not create routine retrospective-only pull requests, and
do not use documentation volume as product progress.

## Language and collaboration

Write source, comments, identifiers, diagnostics, CLI output, tests, benchmarks, internal developer
documentation, commits, pull requests, reviews, releases, and issue references in English. Existing
Japanese planning documents may remain. When an English original and Japanese translation both
exist, update English first and keep the translation synchronized. Japanese is allowed only in
explicit translations and intentionally bilingual end-user documentation.

### Claude Code review adapter

- A human starts `/code-review`.
- Autonomous work uses an available model-invocable review command or one fresh independent
  adversarial reviewer. Do not silently skip review when a command is unavailable.

### Codex review adapter

- A human starts `/review`.
- Non-interactive work may use `codex review --base <branch>`, `codex review --uncommitted`, or
  `codex review --commit <sha>`.
- Autonomous work uses one host-native review or one fresh independent adversarial reviewer; it
  does not pretend to invoke a user-only composer command.
