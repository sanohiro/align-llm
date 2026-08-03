# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c7-persisted-result-design`, based on merged main commit `34eb2ad` (`Merge PR #52:
  Add C6c1p score prefix validation`). The C7 design checkpoint is committed at `0de8470`; no C7
  implementation has started.
- In progress: `docs/specs/c7-persisted-result.md` now defines the C7-D design gate, its direct
  owned `string`/`Option<string>` records, explicit Request 9 `canonical.clone()` persistence
  boundary, canonical artifact/digest contract, `bounded-bucket-v1` boundary algorithm,
  ownership/cleanup matrix, deterministic differential/mutation gate, exact CLI/process rules,
  three-target acceptance environment, and future Make/topology adoption. `docs/align-requests.md`
  reclassifies Request 9 as blocking for C7 implementation/adoption; no implementation or Make
  topology change is present.
- Intentional uncommitted lifecycle files: the Request 9 metadata edit in `docs/align-requests.md`
  and this HANDOFF update. Preserve them until the synchronized C7-D lifecycle commit is made.
- Current source/design lineage: the merged C6c2 design from PR #51 and merged C6c1p implementation
  from PR #52; C6c2 implementation remains blocked on C6a1/C6a2 decoded records and the Align
  adoption prerequisites.
- Active goal: design the independent C7-PersistedResult consumer slice before implementation. PR
  #49 and PR #50 remain unmerged historical checkpoints and are not to be repaired in place.
- Complete: C6c1 implementation, review repair, hosted checks, merge, and the bounded retrospective.
- Complete: the superseded C6c2 design checkpoints are retained as unmerged historical checkpoints
  and are not merge-ready; this branch contains the next corrected design instead.
- Complete: the re-scoped design consumes borrowed, decoded, content-validated result and evidence
  records; persists the execution trace contract; takes explicit verifier source paths and expected
  identities; binds expected align-llm commit to the result environment; references the evidence
  sidecar from `PromptGateManifest`; and now delegates incomplete rows to C6c1p `validate_prefix`.
- Complete: the latest design correction keeps expected source identity claims in the environment
  core while recording proof separately as reachability, and defines every C6c1p prefix-result field
  on invalid plans without unchecked multiplication.
- Complete: evaluator FILE_SET validation now has an explicit manifest path and a bounded canonical
  byte grammar for exact membership, raw relative paths, modes, and file digests. Gate locators use
  the same manifest model and require every declared gate task file to be listed.
- Complete: the checked-in gate source bundle has no persisted tested-head self-reference; Make
  passes explicit source-bundle and Git-tool paths to validation, and the validator derives the
  actual clean, non-shallow CI checkout `HEAD` with that validated executable and cleared Git
  environment. It requires the source bundle to equal it and the evidence's evaluated commit to be
  its ancestor, preserving the normal-merge integration rule.
- Complete: source verification has an explicit native helper policy, helper/Git digests, fixed
  argv/environment/cwd/caps, raw-byte FILE_SET traversal, bounded request/result states, and policy
  identity in `EnvironmentIdentityCore`.
- Complete: adapter timeout/process-output/malformed-result paths use `ADAPTER_FAILED` with no
  fabricated row or after snapshot; result-size overflow uses a bounded compact trace digest and
  empty non-scoreable result/evidence shape.
- Complete: `docs/align-requests.md` now marks Requests 8 and 10 as blocking both C6f2 and C6c2
  runtime-sized decoded-record adoption while allowing independent design work.
- Complete: a post-row evaluator cleanup failure retains a valid non-`ERROR` measurement row and
  complete attestation, emits `ERROR/CLEANUP_FAILED`, and is accepted by C6c2 as `VALID_PREFIX`;
  cleanup before a valid row retains none.
- Complete: C6c1p validates all task-limit fields before computing the bounded expected row count;
  invalid plans use the documented sentinel result.
- Complete: C6c2's source-verifier child timeout is fixed at 60,000,000,000 ns and cannot be
  selected by a request, policy, environment, or caller.
- Complete: scorer reason capacity is `R_max = 9 * task_count * sample_count + task_count + 2`,
  at most 9,282 under the declared bounds; C6c1 and C6c2 reject checked overflow/allocation
  failure before output/scorer side effects and never truncate reasons.
- Complete: the reopened C6c2 closure matrix assigns owners, exact contracts, and named regressions
  for the three terminal findings: mode-specific EVALUATION/GATE head semantics with separate
  evaluated-commit ancestry, pre-Git local Git metadata/config isolation with fixed direct argv, and
  complete `refs/replace/` enumeration across loose, packed, and pinned ref-backend storage.
- Complete: the Git source-verifier redesign, its initial review repair, and the durable Request 14
  prerequisite are retained in terminal PR #50; the successor branch carries the next closure-matrix
  rescope rather than changing that checkpoint in place.
- Complete: the successor rescope reconciles scratch allocation failure with the declared terminal
  Align allocator policy, makes pair cleanup ownership-safe under a competing publisher, and makes
  invalid-evaluation evidence output conditional on reaching the paired-evidence boundary. Review
  findings and attestations remain in GitHub; this handoff records only the durable design decisions
  and blockers needed to continue.
- Complete: PR #51 passed its fresh independent adversarial review, all three recorded findings were
  repaired and dispositioned in GitHub, the hosted documentation/static check passed, and the PR was
  merged with merge commit `74601cda`.
- Retrospective decision: the next C6c1p author-side matrix-to-diff pass must keep HANDOFF's content
  checkpoint distinct from the branch head, ensure each validation step only references already
  decoded inputs, and cross-check lifecycle wording against `docs/align-requests.md`; these are
  durable contract checks, not transient review state.
- Complete: C6c1p adds only the borrowed `validate_prefix` API, reuses the merged row-state rules,
  preserves the complete-row aggregate, and covers the declared prefix/error/plan matrix in its
  focused smoke. No C6c2 implementation or decoded-record workaround is in scope.
- Complete: the author-side C6c1p consistency pass corrected the validation-order prose so a row
  after a terminal `ERROR` is `INVALID_INPUT`, matching the public contract, implementation, and
  post-error smoke case.
- Complete: the prefix count guard derives `pair_width` first and checks the declared 2,048-row
  bound before multiplication, preserving valid plans above 1,024 rows and the invalid-plan
  sentinel contract.
- Complete: `prompt-score-prefix-smoke` is the final hosted target; the Makefile graph, topology
  oracle, C6c1p ledger, and topology design now agree that `make hosted-checks`, `make capable-checks`,
  and `make ci` execute the prefix acceptance smoke.
- Complete: because C6c1p adds a Make target, the required clean-source baseline measurement,
  immutable oracle, and canonical finalization are recorded in separate commits; the evaluation
  contract and existing baseline checks remain unchanged. The topology repair's source, oracle, and
  finalization are `b7f0289`, `a7eb307`, and `6811251`; the earlier `f70ea0e` baseline is superseded.
- Complete: PR #52 merged as `34eb2ad` after the required independent review, consolidated repair,
  local pinned `make ci`, hosted checks, baseline verification, review disposition, and merge-method
  ancestry checks. Detailed review and hosted records remain in GitHub; this file keeps only durable
  project state.
- Post-merge retrospective (2026-08-03):
  - Reusable lesson queued: when a focused acceptance target is added, the same change must update
    the authoritative Make graph, topology oracle, focused smoke, and any identity-bound baseline;
    trigger the queued governance improvement before the next Make topology change. Existing
    `docs/review-checklist.md` and `docs/specs/check-gate-topology.md` cover the policy, but the
    cross-file contract is still a queued automation enhancement rather than a new product rule.
  - Reusable lesson queued: public bounded arithmetic should name the contract bound in the code and
    include a boundary fixture for any derived count; trigger this at the next bounded validator or
    persisted-capacity slice. C6c1p's repair fixed the immediate guard; no retrospective-only patch
    is opened.
  - Existing baseline refresh and HANDOFF continuity rules were sufficient; no additional
    governance change is required from the merge mechanics. Review-tool latency was one-off and is
    not promoted into project policy.
- Working tree must be clean at the next checkpoint; no generated binaries, model weights,
  credentials, or machine-specific paths may be committed.
- Plan of record: `docs/specs/c6-prompt-context-optimizer.md`.
- Pinned Align revision: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` (#672).

## C6c1 implementation boundary

- `prompt_score` is pure and allocation-free at the public boundary. It accepts borrowed `Copy`
  rows and task limits, validates exact alternating row order and the complete row state machine,
  computes task/corpus counts, paired medians, ppm metrics, and complete ordered reasons, and
  writes only caller-owned primitive output columns.
- The pinned compiler accepts `slice<Struct>` input and whole-struct reads but rejects whole-element
  and field-level stores through `out slice<Struct>`. The implementation therefore uses the merged
  scalar-column contract and does not add a compatibility layer or target a proposed Align API.
- Any malformed or undersized call returns before output mutation. Structurally valid `ERROR` rows
  return `EVALUATION_ERROR`; malformed rows return `INVALID_INPUT`.
- The smoke covers passing odd/even medians, ppm rounding, paired and corpus repair/time reasons,
  benchmark reasons, mixed PASS/FAIL/POLICY rows, valid ERROR rows, row/order/plan failures, task
  and reason output capacity failures, and sentinel-preserving early exits.
- The implementation retains no filesystem, process, network, JSON, provider, persistence, or
  failure-memory behavior. Request 7 remains `PROPOSED`; its escaped-string JSON gap still blocks
  the later failure-memory adoption slice.

## Exact next steps

1. Commit the docs-only C7-D design checkpoint after the completed consolidated repair and
   author-side documentation checks; no further review loop is planned for this design checkpoint.
2. Open/merge its independently reviewable design PR,
   and preserve the Request 9 blocker and no-implementation boundary.
3. Do not implement C7-PersistedResult until the reviewed design is merged and Request 9 reaches
   `ALIGN_MERGED` with the sibling release rebuild, `.align-revision` update, and original
   align-llm adoption gate. Keep C6c2 paused; continue only with safe independent work.

## Latest verification

- C6c1 final evidence remains PASS: focused smoke, `make check`, `make fmt`, format/static checks,
  and `make ci` all passed before the merged `main` checkpoint.
- The previous C6c2 design branches are terminal, unmerged checkpoints; do not repair or merge them.
- Terminal PR #50 verification remains durable evidence: its documentation/static checks passed for
  the previous design checkpoint, while source tests and `make ci` were N/A for that docs-only slice.
- Successor rescope verification is PASS at merged PR #51: local documentation assertions and
  `git diff --check a1b328b..f770c9d` passed; hosted run `30780277801`, job `91583421617`, passed
  the documentation/static check. Source tests and `make ci` were N/A because that slice changed no
  executable contract boundary.
- Post-merge refresh is PASS: `main` is fast-forwarded to merge commit `74601cda`; the working tree
  is clean before the C6c1p implementation branch.
- C6c1p implementation verification is PASS at `aad17dc`: `make fmt`, `make format-check`,
  `make check`, `make build`, `make prompt-score-smoke`, `make prompt-score-prefix-smoke`,
  `./scripts/alignc check src/prompt_score_prefix_smoke.align`, and
  `./scripts/alignc check-per-unit src/prompt_score_prefix_smoke.align` all passed. The compiler's
  existing huge-struct-copy warnings remain non-fatal and are preserved as visible diagnostics.
- C6c1p baseline verification is PASS: clean-source measurement at `60f6033`, immutable oracle
  commit `1c54151`, canonical finalization `f70ea0e`, `verify-baseline.py`, and
  `PYTHONDONTWRITEBYTECODE=1 make ci` all passed before the topology repair. The prior baseline is
  intentionally superseded because `Makefile` and `scripts/check-gate-topology` changed.
- C6c1p topology baseline verification is PASS: clean-source measurement at `b7f0289`, immutable
  oracle `a7eb307`, canonical finalization `6811251`, pending-file removal, and
  `PYTHONDONTWRITEBYTECODE=1 python3 eval/runners/verify-baseline.py` all passed. The pinned Align
  revision remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; the ordinary sibling checkout's
  ignored local settings file was preserved, so baseline recording used the clean
  `align-clean-672` worktree.
- Final C6c1p aggregate verification is PASS at `63543f5`: `PYTHONDONTWRITEBYTECODE=1 make ci`
  passed the pinned Align build, topology, hosted and capable checks, prefix smoke, coding corpus,
  canonical baseline, and both baseline negative/failure smokes. Existing compiler warnings remain
  non-fatal diagnostics.
- Review-repair aggregate verification is PASS at `4e15ad9`: `PYTHONDONTWRITEBYTECODE=1 make ci`
  passed again after the 2,048-row count-guard repair; focused prefix/scorer smoke, format, check,
  and baseline verification also passed.
- C7 design author verification is PASS: `git diff --check`, balanced Markdown/NUL/trailing-space
  checks, exact golden-vector SHA-256 checks, stale-algorithm/reference checks, and synchronized
  Request 9 lifecycle assertions all passed after the consolidated design repair. Markdownlint is
  N/A because it is not installed; source tests, `make check`, `make build`, and `make ci` are N/A
  for this docs-only design gate.
- C6c1p topology-repair verification is PASS at `fc596e1`: `python3 scripts/check-gate-topology
  --self-test`, `make gate-topology-check`, `make prompt-score-prefix-smoke`, and
  `PYTHONDONTWRITEBYTECODE=1 make hosted-checks` all passed; the aggregate log includes the new
  prefix target. The pinned Align revision remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.
- C6c1p author-side documentation verification is PASS at `fd3d811`: `git diff --check` passed;
  the correction changed no executable contract boundary, so the recorded source verification and
  baseline remain applicable.
- Post-merge refresh is PASS: local `main` fast-forwarded to `34eb2ad`, the new C7 branch was based
  from that exact commit, and the working tree is clean before design work.
- C7-D author checks are PASS so far: `git diff --check`, balanced Markdown fences/reference-file
  checks, and independent SHA-256 verification of the normative input/preimage/result byte vectors.
  `markdownlint` is N/A because it is not installed; no source tests or Make aggregate apply to this
  docs/spec-only checkpoint. The design changed only `docs/specs/c7-persisted-result.md` and the
  Request 9 metadata in `docs/align-requests.md`; its working-tree changes are intentional.
- Final C6c1p evidence remains PASS: `PYTHONDONTWRITEBYTECODE=1 make ci` passed at
  `4e15ad9509f6048221e1852cfbbf1d8ec656d79d`; the final hosted PR check and baseline verification
  also passed. The pinned Align revision remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.

## Constraints and decisions to preserve

- Request 5 blocks provider proposal/real-provider work; Request 7 blocks C6 artifact and
  failure-memory JSON work; Requests 8 and 10 own recursive runtime construction; Request 11 owns
  bounded child capture; Request 12 owns bounded canonical encoding; Request 13 owns recursive
  owned artifact graphs. Requests 6 and 9 remain independent.
- C6 must not use a borrowed JSON view after its input buffer expires, concatenate JSON fragments,
  invent a private wire format, or code against any proposed Align API. C6c2 specifically consumes
  only C6a1/C6a2 decoded, content-validated records and never parses or canonical-encodes JSON.
- `PromptEvaluationEvidence` is a separate content-bound sidecar with an explicit acceptance input;
  it binds the result digest, independent per-row producer-input digests, and separate reachability
  states for align-llm, external Align, and corpus. A gate-eligible evaluation requires all three
  EVALUATION-mode states to be `VERIFIED` with observed identities equal to the expected identities;
  the checked-in gate separately validates its GATE-mode CI head and evaluated-commit ancestry.
  `UNVERIFIED` remains a valid non-gate comparison. `PromptEvaluateRequest` owns the explicit source paths and expected
  identities; `PromptGateManifest` owns the checked-in evidence
  reference. The verifier validates the persisted workspace/snapshot/input-snapshot/attestation
  trace and exact error prefix. Its C6c1 adapter uses Request 8/10-declared temporary record/scalar
  construction only; no fixed-size workaround or duplicated scorer is allowed. C6c1p owns the
  borrowed prefix validator, while C6c1 `aggregate` remains complete-row-only. Explicit verifier
  roots are read-only external inputs with their own physical path exception; source states already
  observed before an early error are preserved. Pre/post baseline drift is retained as explicit
  terminal attestation state, and result/evidence pair finalization uses result-then-evidence
  no-replace renames with reverse cleanup only for evaluator-owned paths and explicit owned-orphan
  recovery; a competing destination is never removed. The source verifier and gate
  validator reject repository-local replacement refs, grafts, and object alternates through the
  resolved Git common directory. `PromptEvaluateRequest` includes the conditional
  canonical FILE_SET manifest path; `EnvironmentIdentityCore` keeps the explicit expected
  align-llm/Align claims even when a source root is unavailable or mismatching; `PromptVerifierTrust`
  reachability is the independent proof state, and only all-`VERIFIED` evidence is gate-eligible.
  The evaluator align-llm source proof uses exact `HEAD` equality; the checked-in gate uses a
  manifest-owned relative source locator, runtime-derived clean tested-head equality, and
  evaluated-commit ancestry through explicit `C6_GATE_SOURCE_BUNDLE_ROOT` and
  `C6_GATE_GIT_EXECUTABLE_PATH` revalidation. Both source and gate boundaries raw-scan `.git`,
  `gitdir`, `commondir`, and local/worktree configuration before any Git child, allow only inert
  ordinary-clone remote/branch metadata, reject command/hook/helper/filter/pager/path/promisor/
  proxy/transport settings, use fixed direct Git argv and cleared environment, and enumerate
  `refs/replace/` through loose, packed, and pinned ref-backend storage. Request 14 blocks C6f2
  result/evidence publication until Align ships exclusive creation and no-replace rename at a named
  commit and the align-llm adoption gate passes; no check-then-create, delete-before-rename, or
  undeclared native workaround is allowed. The FILE_SET
  manifest is bounded and canonical, with
  checked raw-byte membership and no symlink/special entries. A post-row cleanup failure
  retains a valid non-`ERROR` row and uses the verifier's `VALID_PREFIX` cleanup branch. C6c1p validates
  every task-limit field before multiplication and returns `row_count: rows.len()`,
  `expected_row_count: -1`, `error_index: -1`, and `error_code: 1` for invalid plans without
  side effects.
- Verification is evidence for coherent slices: use focused checks after implementation coherence
  and run full `make ci` only at the named adoption/integration gate. Keep one comprehensive review
  and one consolidated repair; a material redesign requires re-scoping and another review.
- The C6c2 source verifier's fixed 60-second timeout is a contract constant rather than a policy
  field; the explicit gate Git executable and cleared Git environment apply to every CI-head and
  ancestry command. C6c2 cannot resume from Request 8/10 `ALIGN_MERGED` until its separate
  `c6c2-request8-adoption` and `c6c2-request10-adoption` targets plus `make ci` pass.
- C6c2 checked-capacity overflow is a recoverable invalid result before scratch allocation; runtime
  allocator failure follows the declared Request 8/10 terminal nonzero process policy and has no
  recoverable-result or cleanup-after-abort promise. Pair publication removes only evaluator-owned
  temporary or finalized paths; a competing destination is never removed or reported as an orphan.
  A pre-execution decoded-request `INVALID_INPUT` writes only the result; evidence is written only
  after the evaluator reaches its paired-evidence boundary.
- All source, diagnostics, developer documentation, commits, pull requests, and review records
  remain in English.
- Intentional uncommitted files: none; preserve the clean tree and this corrected design/review
  boundary.
