# Session handoff

Read `CLAUDE.md` first. This file records only durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-record-array-request`, based on `origin/main` commit
  `b90e4f769fd6f4067706472ccb4cc6fb801926b2`.
- Relevant commit: `6048d2e` (`Register standalone declared-record array builder request`), based on
  `b90e4f769fd6f4067706472ccb4cc6fb801926b2`; the working tree is clean after that documentation
  commit.
- Active goal: register and merge the standalone Align Request 8 prerequisite for runtime
  construction of view-free declared-record arrays; no consumer-specific JSON or C6 dependency is
  authoritative on this branch.
- Product implementation has not started. Consumer designs must not consume this proposed surface
  until this request reaches `ALIGN_LLM_VERIFIED`.
- Pinned Align revision: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` (#672).
- Current plan of record: `docs/specs/roadmap.md` and `docs/specs/align-llm.md`; a concrete consumer
  design must be merged before it becomes a dependency.

Request 8 is `PROPOSED` and currently non-blocking because no concrete consumer has named this slice.
The current pin's `core.array_builder` accepts only scalar elements and owned `string`; it has no
general mutable builder for view-free declared-record elements. The request defines a closed
recursive `HeapRecord(S)` predicate for non-empty records, rejects `layout(C)` and explicit
alignment, specifies a versioned `RecordBuilderDescV1`, canonical recursive cleanup, deterministic
eligibility/validation order, and explicit `FreeStanding(e)` nested-owner checks, while keeping
dynamic-array fields, `Option`, sums, empty records, and the planned `RegionPlain` region-builder
design out of scope. Existing `.to_array()` support for whole Copy-record pipeline shapes remains
unblocked. A future concrete consumer must reclassify this request as blocking for its named slice.

The documentation contract has completed an author-side consistency pass. The current standalone
repair keeps the heap/region boundary, exact natural-alignment and representation rejection, closed
aggregate predicate, nested allocation-mode checks, descriptor/cache identity, distinct
capacity-versus-allocator-failure policy, scalar/string compatibility boundaries, deterministic
validation order, and durable verification commands. Consumer-specific wire, fixture, and adoption
requirements are deliberately deferred until a later design names them. The record builder follows
Align's existing `borrow mut` contract once L2e ships; the positive helper regression is not
available at the current compiler pin, while direct local builder use remains independently scoped.

## Exact next steps

1. Push the committed documentation slice after the repaired author checks and `make ci` pass.
2. Open the focused draft PR with exact check
   results; the completed comprehensive review findings must be dispositioned in the PR metadata.
3. Merge only after the required SHA-bound review/check evidence is recorded and every finding is
   disposed. A later concrete consumer may then reclassify this request as blocking and add its own
   adoption gate.
4. Do not implement the proposed builder in align-llm or use a hypothetical Align API.

## Latest durable verification

The request entry was written from the pinned Align checkout at `d9fb5da` on 2026-08-01. The
compiler source confirms `Ty::ArrayBuilder(Scalar)`, the `resolve_type` scalar/string-only type
branch, constructor inference, and scalar/string-specific MIR/runtime builder operations. The
repaired standalone contract and repository gates passed the checks below on 2026-08-01:

```text
git diff --check                                      PASS
python3 -B -c "Request 8 revised-contract assertions" PASS
python3 -B -c "Request 8 reference/pin assertions"     PASS
test "$(git -C ../align rev-parse HEAD)" = d9fb5da2b73f6ea649bf17ed9237069ca4baf06e PASS
make ci                                                PASS: all repository gates
```

The contract and reference commands above are the read-only assertions used for this handoff; they
include the repaired `layout(C)`, non-empty-record, zero-field-descriptor, and `borrow mut` contract
boundaries.

```bash
python3 -B - <<'PY'
from pathlib import Path
import re
import subprocess

s = Path('docs/align-requests.md').read_text()
i = s.index('## Request 8 —')
b = s[i:s.index('\n## Not requested', i)]
required = [
    'Status:', 'Priority:', 'Blocking:', 'Blocked gate or slice:',
    'Independent work that may continue:', 'Resume condition:',
    'Align commit or pull request:', 'align-llm verification:',
    '### Motivation', '### Current-state evidence at the pinned Align revision',
    '### Requested capability', '### Ownership closure matrix',
    '### Align acceptance gate', '### References', 'HeapRecord(S)',
    'FreeStanding(e)', 'RecordBuilderDescV1', 'natural alignment at most 8',
    'explicit `align(N)`', 'layout(C)', 'non-empty', 'zero-field',
    'ScalarRecord { id: i64, active: bool }',
    'OwnedRecord { id: i64, name: string }', 'array<string>', 'array<str>',
    'array_builder(out)',
    'record_builder_field_predicate_rejects_dynamic_array_option_sum_and_cycle',
    'record_builder_descriptor_golden_and_definition_edit_revert_identity',
    'record_builder_allocator_failure_terminal_child',
    'record_builder_same_instance_alias_rejected',
    'record_builder_empty_or_c_layout_rejected_before_allocation',
    'record_builder_borrow_mut_helper_non_consuming',
    'record_builder_validation_precedence_local_and_imported',
    'record_builder_validation_precedence_cache_replay',
    'record_builder_enclosing_record_failure',
    'rebuild both the sibling release compiler and runtime',
]
missing = [x for x in required if x not in b]
assert not missing, missing
assert b.count('Status: PROPOSED') == 1 and 'array_builder(out)' in b
print('Request 8 revised-contract check: PASS')
PY
python3 -B - <<'PY'
from pathlib import Path
import re
import subprocess

s = Path('docs/align-requests.md').read_text()
i = s.index('## Request 8 —')
b = s[i:s.index('\n## Not requested', i)]
pin = 'd9fb5da2b73f6ea649bf17ed9237069ca4baf06e'
paths = set(re.findall(r'(?:\.\./align|docs)/[A-Za-z0-9_./-]+', b))
for raw in sorted(paths):
    path = raw.rstrip('.,:;')
    if path.startswith('../align/'):
        rel = path[len('../align/'):]
        subprocess.run(['git', '-C', '../align', 'cat-file', '-e', f'{pin}:{rel}'], check=True)
    else:
        assert Path(path).exists(), path
assert subprocess.check_output(['git', '-C', '../align', 'rev-parse', 'HEAD'], text=True).strip() == pin
assert 'docs/specs/roadmap.md' in paths and pin in b
print('Request 8 reference/pin check: PASS')
PY
test "$(git -C ../align rev-parse HEAD)" = d9fb5da2b73f6ea649bf17ed9237069ca4baf06e
```

The verification is documentation-only and does not build against the proposed builder API. The
worktree is intentionally limited to the two documentation changes; commit/push and the focused
draft PR are the next gate.

## Constraints and intentional state

- This branch changes only `docs/align-requests.md` and `HANDOFF.md`.
- Keep Request 8 separate from consumer designs and Align implementation work.
- Do not update `.align-revision`, build against a proposed API, or add a compatibility layer in
  this register slice. After a named `ALIGN_MERGED` commit, adoption must rebuild both the sibling
  release compiler and runtime, update `.align-revision` to that commit, run the named consumer
  adoption target, and pass `make ci` before the blocked consumer resumes.
- The common fresh-compiler topology is already merged on `main`; any later pin-changing adoption
  must use it and pass the original align-llm gate.
- Source, diagnostics, commits, pull requests, reviews, and releases remain in English.
