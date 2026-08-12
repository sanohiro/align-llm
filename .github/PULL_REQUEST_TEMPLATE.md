Delete optional sections that the diff does not trigger. Use `N/A` only for a required field whose
absence needs explanation; do not manufacture evidence for an unrelated risk.

## Outcome

- Consumer-complete capability:
- Useful end-to-end outcome:
- What is intentionally out of scope:

## Verification

- Changed-owner commands and results:
- Shared preflight command and result:
- Named focused qualification, when its owner boundary changed:
- `make ci`, when an integration/adoption trigger applied:
- Align revision, when changed or adopted:

## Measurement (performance claims only)

- Baseline:
- Hardware/environment:
- Result:

## Risk and review

- Ownership, error-handling, or compatibility risks:

### Comprehensive review envelope

- Record or link:
- Reviewed head SHA:
- Base-tip SHA:
- Merge-base SHA:
- Reviewer:
- Review kind and scope:
- Verdict:
- Complete findings (`none` when clean):
- Finding dispositions:
- Consolidated repair commit (`N/A` when no repair was needed):

### Conditional final review (only when materially triggered)

- Trigger (substantial scope expansion, approach change, or material behavior/design/specification/governance change):
- Record or link:
- Reviewed head SHA:
- Base-tip SHA:
- Merge-base SHA:
- Reviewer:
- Review kind and scope:
- Verdict:
- Complete findings:
- Finding dispositions:

### Check evidence

- Head SHA:
- Tested base-tip SHA:
- Merge-base SHA:
- Tested integration commit or tree (head only when merge-base equals tested base-tip; otherwise
  synthetic merge or equivalent):
- Required check names, statuses, and links:

- [ ] The selected workflow row's review requirement is satisfied
- [ ] A final review was run only if its material-change trigger applied
- [ ] Required checks pass
- [ ] No valid review finding remains unresolved
- [ ] `HANDOFF.md` records durable state if its checkpoint, blocker, or next action changed
