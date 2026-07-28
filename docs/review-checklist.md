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

## Policy and design integrity

- Instructions are internally executable, non-contradictory, and explicit about terminal
  conditions, required evidence, and applicable or `N/A` contract dimensions.
- A non-trivial public contract maps every normative promise and field to a reproducible acceptance
  test or measurement before implementation starts.
- Cross-cutting plans name intended owner modules, failure and cleanup paths, and exact regression
  tests before coding, then map them to the final implementation before code review, or record an
  explicit deferral with its rationale in the plan of record.
- Review requirements cover the final pushed state and require another review after material
  behavior, design, specification, or governance follow-ups.
- Each preflight and post-open review envelope independently records the exact head SHA, base-tip
  SHA, merge-base SHA, reviewer, review kind and scope, verdict, and finding dispositions outside
  the branch. Check evidence is separate and cannot substitute for review evidence.
- Merge readiness requires current SHA-bound evidence, passing required checks, clean required
  reviews, no unresolved valid finding, and no later content push.
- `HANDOFF.md` identifies the active branch and relevant commit, completed and unfinished work,
  exact next actions, durable verification evidence, blockers, intentional uncommitted files, and
  expected post-merge work without mirroring transient pull request status.

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

## Verification and regression risk

- `make ci` passes with the exact pinned Align revision.
- Tests or corpus tasks exercise failure and timeout paths affected by the change.
- Diagnostics needed to reproduce a failure remain available.
- The pull request records valid review findings and explains rejected findings.
