# Session handoff

Read `CLAUDE.md` first. This file records only durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-owned-json-request`, based on `origin/main` commit
  `0c712cf459408a29fc697cb392546a98d83c3020`.
- Relevant commit: none yet; the intentional changes are uncommitted in
  `docs/align-requests.md`, `docs/examples/request9-owned-json-syntax.align`,
  `docs/specs/roadmap.md`, and `HANDOFF.md`,
  based on merged Request 8 commit
  `0c712cf459408a29fc697cb392546a98d83c3020`.
- Active goal: finish and merge the standalone Align Request 9 prerequisite for a closed, directly
  owned JSON record shape; its revised contract is still uncommitted.
- Product implementation has not started. Request 8 is merged at `0c712cf459408a29fc697cb392546a98d83c3020`; this branch remains independent and must not consume the proposed owned-JSON API.
- Pinned Align revision: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` (#672).
- Current plan of record: `docs/specs/roadmap.md` and `docs/specs/align-llm.md`; a consumer-specific
  design is not durable on this branch and must be merged before it becomes a Request 9 dependency.

Request 9 is `PROPOSED` (`Blocking: no`) and remains uncommitted. The pinned declared-record JSON codec accepts
borrowed `str` and `array<str>` fields but rejects owned `string`/`array<string>` fields. The revised
contract keeps the existing all-borrowed route, selects a closed direct owned path only when an owned
text leaf is present, keeps that selector separate from scanner and record-array entrypoints, depends
on Request 7's earlier authoritative escape grammar, rejects explicit layout attributes, records
terminal allocator-abort behavior, and makes the natural-layout algorithm and each logical field's
record-base-relative physical payload and optional tag offsets part of `OwnedJsonDescV1` identity. The closure matrix was reopened for the offset-origin invariant: every serialized physical offset is record-base-relative, and an optional field uses `field_base + option_{payload,tag}_offset`. The current closure-matrix design distinguishes the requested
free-standing owned decode inside an arena from arena-backed encode views, records the required
memory-model/spec update before that allocation mode is implementable, and identifies the pinned compiler/tests as
the implementation evidence for the shipped recursive Move `Result` carrier while requiring stale
Move-result prose reconciliation before Align merge, fixes the explicit `0 = signed`/`1 = unsigned`
descriptor mapping, defines the complete 13-class/91-pair same-process matrix including existing-only
pairs, records the new Align-owned top-level bool-array regression, preserves the existing scalar-array
targets, adds bytewise omitted/null/empty optional-note vectors, names the `C7-PersistedResult`
roadmap slice as the first expected consumer, defines the target-ABI baseline and release-target
acceptance environments, defines declaration-order field and ascending element cleanup, separates
recoverable integer-range cleanup from terminal capacity/allocator aborts, records
CLI/build and option/environment boundaries as concrete N/A dimensions, and parser-checks raw-`Result`
and explicitly typed `map_err` syntax in the fixture. The latest review redesign also makes
optional-string tag and payload offsets separate descriptor fields and adds a full-range `u64::MAX`
encode vector and unsigned-writer rule. The design remains documentation-only
and must not add a dynamic JSON value, a private encoder, or an implicit `array<string>` to `array<str>`
conversion. Unsupported optional-owner rejection is scoped to the selected direct owned-text
descriptor and the existing no-owned-leaf route is preserved; the pinned negative test is current-
state evidence of that pre-existing route inconsistency, not a Request 9 acceptance claim. The
requested free-standing JSON allocation inside an arena remains conditional on the named Align
memory-model/spec update and its source-drop, move-out, and failure-cleanup tests.

`0c712cf459408a29fc697cb392546a98d83c3020` is the merged base containing the standalone Request 8
registration. Request 9 remains independent of Request 8's proposed builder surface and must not
consume it; a later consumer must wait for a named Align merge and its real-client adoption gate.

## Exact next steps

1. Rerun the author contract/reference/pin/formatter/diff checks and `make ci` after the descriptor
   record-base offset-origin clarification; update this Handoff with their results.
2. Inspect the final delta for unrelated changes, then commit, push, and open a focused PR with
   exact verification and all finding dispositions. Do not consume the proposed API.
3. Merge only after the SHA-bound review/check evidence is recorded. Do not implement or consume the
   proposed owned-JSON API before a named Align merge and real-client adoption gate.
4. After this Request 9 PR merges, stop roadmap implementation at the user's direction; do not resume
   the separate C6 worktree or start another gate in this session.

## Latest durable verification

The request entry was written from the pinned sibling checkout at `d9fb5da` on 2026-08-01. Source
inspection confirmed the current `json_struct_fields_ok_rec` scalar/`str`/nested/array-struct
domain, shipped Move AoS/union targets, pass-0b-2 rejection of `array<string>` fields, the
existing borrowed `array<str>` ownership model, and the shipped L1b recursive Move `Result` carrier.
The latest author contract/reference/pin checks, parser-only syntax check, diff checks, and `make ci`
all passed on 2026-08-01 after the recoverable integer-range versus terminal capacity/allocator-abort
redesign, the selected-owned-path optional-owner redesign, and the physical-layout identity
redesign, the optional-offset/full-range-unsigned redesign, and the record-base offset-origin
clarification. The latest redesign additionally
records the pinned arena allocation rule and the required Align memory-model/spec update before free-standing JSON materialization inside
an arena. The durable design now
identifies compiler/tests as the pinned Move-result implementation evidence while requiring stale
prose reconciliation, fixes `0 = signed`/`1 = unsigned` in the descriptor and golden vectors, names
the `C7-PersistedResult` roadmap slice, defines the target-local ABI baseline and three release-target
acceptance environments, names the new bool-array regression, defines the complete 13-class/91-pair
same-process matrix including existing-only pairs, specifies declaration-order field and ascending
element cleanup, separates recoverable range-error cleanup from terminal aborts, records the CLI/build
and option/environment dimensions as concrete N/A decisions, and parser-checks the raw-Result and
explicit typed `map_err` examples in the syntax fixture. It scopes unsupported optional-owner
rejection to records that select the new direct owned-text descriptor and preserves the existing
no-owned-leaf route; the pinned `json_option_move_struct_payload_still_rejected` negative test remains
current-state evidence of that pre-existing route inconsistency rather than a Request 9 acceptance
claim. The descriptor now includes the pinned natural-layout algorithm and each logical field's
record-base-relative physical payload and optional tag offsets, with optional offsets explicitly
formed as `field_base + option_{payload,tag}_offset`. The latest review repair also adds the full-range unsigned
writer rule and `u64::MAX` byte vector:

```text
git diff --cached --check                             PASS
git diff HEAD --check                                 PASS
Request 9 contract check                              PASS
Request 9 reference/pin check                         PASS
test "$(git -C ../align rev-parse HEAD)" = d9fb5da2b73f6ea649bf17ed9237069ca4baf06e PASS
make ci                                                PASS: exit 0, all repository gates
alignc fmt docs/examples/request9-owned-json-syntax.align PASS: parser-only syntax check
```

The exact read-only assertions used for the contract and reference checks are:

```bash
python3 -B - <<'PY'
from pathlib import Path

s = Path('docs/align-requests.md').read_text()
i = s.index('## Request 9 —')
b = s[i:s.index('\n## Not requested', i)]
required = [
    'Status: PROPOSED', 'Priority: high', 'Blocking: no',
    'Blocked gate or slice:', 'Independent work that may continue:',
    'Resume condition:', 'Align commit or pull request:', 'align-llm verification:',
    '### Motivation', '### Current-state evidence at the pinned Align revision',
    '### Requested capability', '### Ownership closure matrix', '### Align acceptance gate',
    '### References', 'import core.json', 'json.decode(input: str)', 'json.encode(value: T)',
    'array<string>', 'array<str>', 'existing borrowed/all-borrowed JSON codec',
    'owned text leaf', 'free-standing allocation', 'owned-path `float` rejection',
    'C7-PersistedResult', '0 = signed', '1 = unsigned', 'x86_64-unknown-linux-gnu',
    'aarch64-unknown-linux-gnu', 'aarch64-apple-darwin', 'Ubuntu 24.04', 'Rust 1.96', 'LLVM 22',
    'Option<MoveStruct>', 'Request 7', 'C7 Algorithm Verification',
    'retained_result_with_recursive_move_payload_is_supported', 'pre-L1b',
    'owned_json_copy_scalar_width_sign_range_and_bool', 'm5.rs::json_decode_bool_array',
    'owned_decode_inside_arena_free_standing_result',
    'owned_decode_inside_arena_source_drop_and_move_out',
    'owned_decode_inside_arena_failure_cleanup',
    'Arena allocation-mode source of truth',
    'ordinary arena default', 'docs/language-spec.md',
    'Minimum compiler/platform baseline', 'docs/examples/request9-owned-json-syntax.align',
    "Request 7 remains the source of truth", 'layout_mode', 'natural layout only',
    'allocation mode `0x00`', 'layout_algorithm', 'physical_payload_offset',
    'optional_tag_offset', 'record-base-relative',
    'field_base + option_{payload,tag}_offset', 'field_abi_align', 'stable declaration-index ties',
    'physical layout mismatch', 'u64::MAX', 'full-range unsigned writer',
    'DropPlan', 'OwnedJsonDescV1', 'builder_finish_stack', 'builder_into_string_stack',
    'input UTF-8 bytes:', 'canonical output UTF-8 bytes:', 'value-carrying `break`',
    '`continue` is N/A because Align has no such construct',
    'owned_decode_partial_failure_cleans_every_live_owner',
    'owned_decode_trailing_garbage_cleans_every_live_owner',
    'owned_json_cleanup_order_is_declaration_and_element_order',
    'owned_json_move_source_null_and_return_cleanup', 'owned_json_all_control_flow_cleanup',
    'owned_json_target_abi_descriptor_matches_target', 'owned_json_target_abi_mismatch_rejected',
    'owned_encode_output_region_and_clone_boundary',
    'owned_json_descriptor_golden_and_definition_edit_revert_identity',
    'owned_json_direct_record_target_selects_owned_path',
    'owned_json_direct_record_encode_route',
    'owned_json_non_record_targets_unchanged',
    'owned_json_same_process_entrypoint_matrix',
    'owned_json_record_array_preserves_shipped_move_aos',
    'owned_json_record_array_owned_text_rejected_before_owned_descriptor',
    'owned_json_scanner_target_rejected_before_allocation',
    'owned_json_fixed_struct_array_encode_route_unchanged',
    'owned_json_union_encode_route_unchanged',
    'owned_json_decode_capacity_overflow_terminal_child',
    'owned_json_encode_capacity_overflow_terminal_child',
    'cache_parallel.rs::owned_json_two_processes',
    'm5_owned_json.rs::owned_json_allocator_failure_terminal_child', 'terminal allocator-abort policy',
    'Metric / benchmark: N/A as a performance acceptance claim',
    'CLI/build and option/environment boundaries',
    'Configuration boundaries: CLI/build inputs are N/A',
    'ALIGN_MERGED', 'make ci',
]
missing = [x for x in required if x not in b]
assert not missing, missing
assert b.count('Status: PROPOSED') == 1
print('Request 9 contract check: PASS')
PY
python3 -B - <<'PY'
from pathlib import Path
import re
import subprocess

s = Path('docs/align-requests.md').read_text()
i = s.index('## Request 9 —')
b = s[i:s.index('\n## Not requested', i)]
paths = set(re.findall(r'(?:\.\./align|docs)/[A-Za-z0-9_./-]+', b))
pin = 'd9fb5da2b73f6ea649bf17ed9237069ca4baf06e'
for raw in sorted(paths):
    path = raw.rstrip('.,:;')
    if path.startswith('../align/'):
        rel = path[len('../align/'):]
        subprocess.run(['git', '-C', '../align', 'cat-file', '-e', f'{pin}:{rel}'], check=True)
    else:
        assert Path(path).exists(), path
assert 'docs/specs/roadmap.md' in paths
assert pin in b
assert subprocess.check_output(['git', '-C', '../align', 'rev-parse', 'HEAD'], text=True).strip() == pin
print('Request 9 reference check: PASS')
PY
test "$(git -C ../align rev-parse HEAD)" = d9fb5da2b73f6ea649bf17ed9237069ca4baf06e
../align/target/release/alignc fmt docs/examples/request9-owned-json-syntax.align >/dev/null
```

The revised reference check covers every literal repository path in the standalone Request 9
entry. The worktree remains documentation-only and does not build against the proposed owned JSON
API.

## Constraints and intentional state

- This branch changes only `docs/align-requests.md`, `docs/examples/request9-owned-json-syntax.align`,
  `docs/specs/roadmap.md`, and `HANDOFF.md`; no product implementation or
  proposed Align API is present.
- Keep Request 9 separate from Request 8, consumer designs, and Align implementation work until
  those dependencies are durable and explicitly adopted.
- Do not update `.align-revision`, build against a proposed API, or add an application compatibility
  layer. After a named `ALIGN_MERGED` commit, adoption must rebuild the sibling release compiler and
  runtime, update `.align-revision`, run the named adoption target, and pass `make ci`.
- Request 9 does not close Request 7's borrowed escaped-string lifecycle. Any future wire DTO or view
  conversion requires its own reviewed lifecycle entry rather than an undocumented workaround.
- Source, diagnostics, commits, pull requests, reviews, and releases remain in English.
