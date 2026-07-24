# Review checklist

Use this checklist for pull requests that change code or evaluation behavior. Scope each section to
the diff; it is a risk guide, not a request for speculative refactoring.

## Scope and gate

- The pull request names one roadmap gate or enabling slice.
- Unrelated governance, Align request, generated artifact, and product changes are excluded.
- If the one-time initial-bootstrap exception in `CLAUDE.md` applies, its coupled surfaces and
  scoped commits are identified explicitly in the pull request.
- Completion claims cite an observable gate and its evidence.

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
- `HANDOFF.md` reflects material changes to current state, verification, or next steps.
