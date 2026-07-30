# Review checklist

Use this checklist for pull requests that change code, evaluation behavior, authoritative designs or
specifications, or repository governance. Scope each section to the diff; it is a risk guide, not a
request for speculative refactoring. The policy and design section is required for authoritative
documentation changes; mark other inapplicable sections as `N/A` rather than inventing evidence.

## Scope and gate

- The pull request names one roadmap gate or enabling slice.
- Unrelated governance, Align request, generated artifact, and product changes are excluded.
- If the one-time initial-bootstrap exception in `CLAUDE.md` applies, its coupled surfaces and
  scoped commits are identified explicitly in the pull request.
- Completion claims cite an observable gate and its evidence.
- Aggregate gate names are checked against their actual command graph. The pull request names any
  relevant focused gate that the aggregate does not invoke instead of inferring coverage from the
  aggregate's name.

## Policy and design integrity

- Instructions are internally executable, non-contradictory, and explicit about terminal
  conditions, required evidence, and applicable or `N/A` contract dimensions.
- A non-trivial public contract has one authoritative ledger, and an author-side consistency pass
  maps every normative promise, field, state combination, ownership/allocation rule, canonical
  encoding rule, identity rule, and prerequisite to a reproducible acceptance test or measurement
  before implementation starts.
- Cross-cutting plans name intended owner modules, failure and cleanup paths, and exact regression
  tests before coding. Their closure matrices cover formation, construction, move and return,
  cleanup, malformed input, affected control-flow joins, interface/per-unit paths, provenance, and
  allocation parity, then map those cells to the final implementation before code review or record
  an explicit deferral with its rationale in the plan of record.
- Compatibility claims are exercised on the minimum declared tool or platform version. Option or
  environment isolation tests prove both that excluded state does not cross the boundary and that
  every documented surviving input retains its exact value and documented source or precedence
  semantics.
- Concurrency closure classifies every combination of individually supported public entrypoints that
  can share state in one process tree, including aggregate-plus-aggregate and
  aggregate-plus-focused operations, and separately defines the policy for concurrent independent
  processes.
- One comprehensive full-diff review reports all findings before repair starts. Findings are
  scrutinized, grouped by root-cause class, and resolved in one consolidated follow-up when
  practical; the history does not contain a review after each individual fix.
- An ordinary repair that implements only recorded findings does not trigger another review. One
  final comprehensive review is required only after a substantial scope expansion, implementation
  approach change, or material behavior, design, specification, or governance change. If that
  final review requires another non-trivial change, the work is re-scoped or redesigned instead of
  entering another review loop.
- The comprehensive review envelope records the reviewed head SHA, base-tip SHA, merge-base SHA,
  reviewer, review kind and scope, verdict, and complete finding list. The pull request records each
  disposition and the consolidated repair commit. A conditionally required final review records the
  same complete SHA-bound envelope, findings, and dispositions. Check evidence separately records
  the final head, tested base-tip, merge-base, and tested integration commit or tree.
- Merge readiness requires the comprehensive review, any conditionally required one-time final
  review, passing final checks, and no unresolved valid finding. Multiple independent review
  envelopes are not required for the same unchanged diff.
- `HANDOFF.md` identifies the active branch and relevant commit, completed and unfinished work,
  exact next actions, durable verification evidence, blockers, intentional uncommitted files, and
  expected post-merge work without mirroring transient pull request status.
- If an artifact requires commits from the current repository to remain reachable, the contract
  names permitted integration methods; the exact reviewed head contains those commits as ancestors,
  and the selected merge method preserves them. External revisions are checked against their named
  repository and reachability rule instead.

## Align correctness

- The code uses only the pinned compiler surface and follows the relevant Align guide or
  compiler-tested example.
- Move values, borrowed views, allocation, failure, and process ownership remain explicit.
- Captured stdout and stderr are cloned before escaping their owning process handle.
- Reused loop inputs are borrowed rather than accidentally moved on the first iteration.
- A newly surfaced language or standard-library gap is recorded in `docs/align-requests.md`, not
  hidden behind a fragile application workaround.

## Evaluation integrity

- Task inputs, repository revision, expected result, timeout, and scoring rule are explicit.
- Corpus ordering and result output are deterministic.
- Empty input, skipped tasks, missing fixtures, and default values cannot silently pass.
- Performance claims include the baseline, hardware, sample count, and reproducible command.
- Provider-specific behavior does not leak into provider-independent scoring.
- Repository-internal test refs and namespaces resolve the Git common directory rather than assuming
  `.git` is a directory, and ordinary-clone, linked-worktree, normal-cleanup, and abnormal-exit
  cleanup paths are exercised when that behavior changes.

## Verification and regression risk

- `make ci` passes with the exact pinned Align revision.
- A regression helper executes repository source under review from its exact bytes; import settings
  alone are not exact-source evidence. When cache behavior is itself the regression subject, the
  helper may additionally exercise a named helper-owned cache only after validating its path,
  ownership, expected cached-versus-source identities, and outcomes. On every exit, caller-owned
  repository cache paths and bytes match their complete pre-run snapshot, including the absence of
  newly created paths; named helper-owned cache fixtures are removed; and modified process-global
  interpreter values are restored to their exact prior values.
- Tests or corpus tasks exercise failure and timeout paths affected by the change.
- Diagnostics needed to reproduce a failure remain available.
- The pull request records valid review findings and explains rejected findings.
- The prior merged pull request received a bounded retrospective. Reusable review, CI, merge, or
  worktree lessons are either represented by this scoped governance/automation change or queued
  explicitly in `HANDOFF.md`; one-off conditions are not promoted into policy.
