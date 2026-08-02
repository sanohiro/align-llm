# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6c2-git-boundary-redesign`, based on the terminal PR #49 checkpoint
  `75bbdc2` and merged `main` commit `67f36ebaaaf0ae5d7ec644c607b51a77c3fc5dcf`.
- Current source checkpoint: `8905114` (`Address C6c2 design review findings`). The preceding
  design checkpoint is `5212242`.
- Active goal: finish the independently reviewable C6c2 design successor slice in PR #50. The
  terminal PR #49 remains unmerged and is not to be repaired in place. Implementation is not
  started and must wait for this design plus the C6a1/C6a2 decoded-record and Align adoption
  prerequisites.
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
- Complete: the initial successor design review's three findings are accepted in one repair:
  EVALUATION and GATE use mode-specific align-llm head contracts with a separate gate ancestry
  proof; ordinary-clone inert remote/branch metadata is allowed while command-bearing and transport
  affecting settings remain rejected; and Request 14 records the Align-owned exclusive-create and
  no-replace publication capability required by C6f2.
- In progress: publish the consolidated repair and complete PR #50's review evidence. The initial
  independent review is recorded externally; its accepted findings are repaired in `8905114`.
  Because Request 14 materially adds a blocked publication prerequisite, run the one conditional
  final comprehensive review after the repair. Keep PR #49 as the terminal review checkpoint; do
  not merge either branch until PR #50's review, findings, and required documentation checks are
  complete.
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

1. Push `8905114` on `agent/c6c2-git-boundary-redesign`, update PR #50 with the initial review
   envelope and all three finding dispositions, and run the applicable hosted documentation checks.
2. Run the one conditional final comprehensive adversarial review required by the material Request
   14 redesign. If it finds a new non-trivial issue, stop the local repair loop, reopen the closure
   matrix, and re-scope instead of applying another patch cycle.
3. After PR #50 is reviewed, its findings are disposed, and it is merged, refresh `main`, perform
   the bounded retrospective, and implement and merge C6c1p first; implement
   C6c2 only after C6a1/C6a2 provide content-validated
   decoded records and Requests 7/8/10/12/13 are adopted at named Align revisions. Otherwise record
   the dependency blocker and continue only with safe independent roadmap work.
4. Do not start JSON/document binding or failure-memory JSONL adoption until Request 7 is accepted,
   merged at a named Align commit, the pinned release is rebuilt, `.align-revision` is updated, and
   `make ci` passes the original acceptance gate.

## Latest verification

- C6c1 final evidence remains PASS: focused smoke, `make check`, `make fmt`, format/static checks,
  and `make ci` all passed before the merged `main` checkpoint.
- The previous C6c2 design branches are terminal, unmerged checkpoints; do not repair or merge them.
- Current corrected design verification: `git diff --check 75bbdc2..8905114` PASS, the targeted
  mode-head, ordinary-clone local-config, fixed-argv, complete-replacement, and Request 14 contract
  assertions PASS, and Markdown fence counts are 90 for `docs/specs/c6-prompt-context-optimizer.md`
  and 86 for `docs/align-requests.md` (both even). Source tests and `make ci` are N/A because this
  remains documentation/specification-only; PR #50 requires its applicable hosted
  documentation/static checks. The working tree must be clean after this handoff update; the next
  verification is the PR review-evidence and conditional-final-review sequence.

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
  trace and exact error prefix. Its C6c1 adapter uses Request 8/10-shipped temporary record/scalar
  construction only; no fixed-size workaround or duplicated scorer is allowed. C6c1p owns the
  borrowed prefix validator, while C6c1 `aggregate` remains complete-row-only. Explicit verifier
  roots are read-only external inputs with their own physical path exception; source states already
  observed before an early error are preserved. Pre/post baseline drift is retained as explicit
  terminal attestation state, and result/evidence pair finalization uses result-then-evidence
  no-replace renames with reverse cleanup and explicit orphan recovery. The source verifier and gate
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
- All source, diagnostics, developer documentation, commits, pull requests, and review records
  remain in English.
- Intentional uncommitted files: none; preserve the clean tree and this corrected design/review
  boundary.
