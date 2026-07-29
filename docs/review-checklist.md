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
- Review requirements cover the final pushed state and require another review after material
  behavior, design, specification, or governance follow-ups.
- Each preflight and post-open review envelope independently records the exact head SHA, base-tip
  SHA, merge-base SHA, reviewer, review kind and scope, verdict, and finding dispositions outside
  the branch. A head or base-tip change after opening requires a full-diff preflight-equivalent
  refresh that replaces the stale pre-open envelope without replacing either post-open review.
  Check evidence separately records the head, tested base-tip, merge-base, and tested integration
  commit or tree and cannot substitute for review evidence. The head is a valid tested integration
  only when its merge base equals the tested base tip; otherwise evidence names the synthetic merge
  or equivalent tree for those exact inputs.
- Merge readiness requires current SHA-bound evidence, passing required checks, clean required
  reviews, no unresolved valid finding, and no later content push.
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
- Tests or corpus tasks exercise failure and timeout paths affected by the change.
- Diagnostics needed to reproduce a failure remain available.
- The pull request records valid review findings and explains rejected findings.
- The prior merged pull request received a bounded retrospective. Reusable review, CI, merge, or
  worktree lessons are either represented by this scoped governance/automation change or queued
  explicitly in `HANDOFF.md`; one-off conditions are not promoted into policy.
