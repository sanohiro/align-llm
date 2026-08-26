# Review checklist

Use this checklist in two situations:

- while designing a surface that triggers `CLAUDE.md`'s proportional design gate; or
- for the one comprehensive review of code, authoritative design/specification, or governance.

Review only the sections triggered by the diff. An untriggered section is omitted, not expanded
into speculative `N/A` evidence. Within a triggered contract ledger or closure matrix, however,
every listed dimension must be answered or marked `N/A` with a concrete reason.

## Every reviewed change

- The pull request delivers one consumer-complete outcome and excludes unrelated failure domains.
- Completion names an observable consumer path and exact evidence. Aggregate coverage is checked
  against the command graph; focused targets outside it are named explicitly.
- Instructions and contracts are internally consistent, executable, and clear about terminal
  conditions, errors, evidence, and ownership.
- The diff uses the narrowest durable regression owner and does not add expensive qualification to
  a routine aggregate merely for reachability.
- Findings are complete before repair begins, validated rather than accepted blindly, grouped by
  root-cause class, and dispositioned. Repairs do not contain unrelated behavior.
- Verification matches the changed owners and publication lane. Performance claims include the
  baseline, hardware/environment, sample count, and reproducible command.
- `HANDOFF.md` changes only when durable execution state changed; GitHub retains transient review
  and check evidence.

## Public contract ledger

Trigger this section only for a changed public CLI/API, persisted or exchanged format,
ownership/process/network boundary, or coordinated invariant across three or more modules.

- Exact commands, types, and signatures; inputs and defaults; results, statuses, errors, and
  deterministic multi-invalid precedence are authoritative in one ledger.
- Public arguments and results define validation, ownership, lifetime, allocation, construction,
  move-in/out, source nulling, replacement, return, and cleanup or `Drop`.
- Text and wire boundaries define encoding, embedded-NUL behavior, validation before side effects,
  scalar widths and tags, record/sequence order, malformed-input rejection, and semantic-to-byte
  plus byte-to-semantic golden vectors.
- Persisted and cache identity define schema/version, producer and consumer, nominal versus
  structural fingerprinting, and the complete reachable definition graph when structural.
- CLI, build, option, and environment inputs are explicit. Isolation is tested in both directions:
  excluded state cannot cross, and documented surviving inputs retain exact values and source or
  precedence semantics.
- Every combination of detail level, discriminator, verification state, and option state defines
  field presence, row order, ordinal, and unavailable-value behavior.
- Runtime-inspection fields have producer-owned data or thunks, without hidden reflection or
  artifact/source reads.
- Normative examples have syntax checks and distinguish declarations from positional calls.
- Minimum supported tool/platform versions have required acceptance evidence; evidence from newer
  environments is supplementary.
- Milestones do not consume a decision or capability assigned to a later slice.
- Every promise maps to an acceptance test, focused qualification, or named metric/benchmark.

## Cross-cutting closure matrix

Trigger this section when the design gate spans ownership, shared state, external processes, or
three or more implementation modules.

- Each affected type and module covers formation/validation, construction, success, failure,
  malformed input, early exit, move-in/out, source nulling, replacement, return, and cleanup.
- Every affected `if`, `match`, `else`, `?`, `map_err`, branch join, loop join, and error path has a
  named implementation owner and regression test.
- Generic monomorphization, interface serialization, whole-program and per-unit compilation,
  runtime ownership provenance, and allocation parity are covered when applicable.
- Shared process/connection state classifies every supported entrypoint pairing, including
  aggregate-plus-aggregate and aggregate-plus-focused, as serialized, rejected before side
  effects, or unsupported. Concurrent independent-process policy is stated separately.
- Exhaustion, a failed second operation, error cleanup, and restoration order leave no stale
  process-global or connection-global state.
- The final matrix-to-diff pass points every applicable cell to implementation and passing evidence
  or to an explicit deferral in the plan of record.

## Align correctness

Trigger this section for Align source or an Align surface adoption.

- Code uses only the pinned compiler surface and follows the relevant sibling guide, compiling
  example, or compiler test.
- Move values, borrowed views, allocation, failure, and process ownership remain explicit.
- Captured stdout/stderr are cloned before escaping an owning process handle; reused loop inputs are
  borrowed rather than moved on the first iteration.
- A real language or standard-library gap follows `docs/align-requests.md`; no local workaround or
  hypothetical API is introduced.

## Evaluation and repository integrity

Trigger the applicable bullets for evaluation, corpus, Git plumbing, or exact-source helpers.

- Task input, repository revision, expected result, timeout, scoring rule, corpus order, and output
  are explicit and deterministic. Empty input, skipped tasks, missing fixtures, and defaults cannot
  silently pass.
- Provider-specific behavior does not leak into provider-independent scoring. Failure and timeout
  paths affected by the change are exercised and retain useful diagnostics.
- Repository-internal refs resolve the Git common directory and cover ordinary clones, linked
  worktrees, normal cleanup, and abnormal cleanup.
- Exact-source regression helpers execute the reviewed bytes. A helper-owned cache is allowed only
  when cache behavior is the subject and path, ownership, expected identities, outcomes, cleanup,
  caller-owned cache snapshots, and process-global restoration are verified.
- Artifacts requiring in-repository ancestry name permitted integration methods and are reachable
  from the exact merging head; external revisions use their own named repository and rule.

## Verification and terminal state

- Focused owner checks pass. `make ci` appears only for a named integration/adoption gate, aggregate
  membership or topology change, changed integration behavior, or fresh base-integration evidence;
  a pin change alone does not select it.
- Required security, resource, race, fuzz, stress, platform, mutation, or benchmark qualification
  runs under its named owner command when its boundary changed.
- The pull request contains the comprehensive review envelope, every finding disposition, any
  consolidated repair commit, and separate final integration check evidence required by
  `CLAUDE.md`.
- A final review occurred only if the repair materially triggered it. If that review found another
  non-trivial issue, the capability was redesigned or re-scoped rather than patched through another
  loop.
- Required checks pass and no valid finding remains unresolved.
