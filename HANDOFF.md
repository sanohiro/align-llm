# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6c2-adoption-timeout-reason-rescope`, based on the terminal source/trace design
  checkpoint `86b40aa793b9c7f4e74dfe3bff319178cc3a1abd` and merged `main` commit
  `67f36ebaaaf0ae5d7ec644c607b51a77c3fc5dcf`.
- Current source checkpoint: `34be593` (`Close C6c2 design review findings`), based on the
  previously reviewed design checkpoint `b485fb8` and merged `main` commit above.
- Active goal: finish PR #49 with a re-scoped C6c1p/C6c2 design. The current PR head is a review
  checkpoint and is not merge-ready; reopen the closure matrix before any further implementation or
  review cycle. This branch resolves the initial review findings and carries the earlier design
  decisions: runtime-derived clean CI-head binding through the explicit
  validated Git executable and cleared environment, a content-bound native source-verifier/Git
  boundary with raw-byte FILE_SET traversal, explicit `ADAPTER_FAILED` terminal attestations, a
  bounded `RESULT_TOO_LARGE` trace envelope, C6c2-specific Request 8/10 adoption gates, fixed
  source-verifier timeout, a deterministic scorer reason capacity, repository-local replacement/graft/
  alternate rejection, explicit pre/post baseline-drift attestations, observed-identity binding for
  every `VERIFIED` source, and deterministic result/evidence pair cleanup.
  Implementation is not started and must wait for this design plus the C6a1/C6a2 decoded-record and
  Align adoption prerequisites.
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
- Complete: the terminal PR #49 review findings are addressed in one consolidated design repair;
  repository-local Git replacement/graft/alternate mechanisms are rejected through the resolved
  common directory, baseline drift has explicit persisted states, `VERIFIED` carries equal observed
  identities, and result/evidence finalization has no-replace order plus cleanup/recovery behavior.
- In progress: reopen the C6c2 closure matrix and redesign the current slice before any further
  repair/review loop. The latest final-review evidence is recorded in GitHub; its durable blockers
  are mode-specific gate-head versus evaluated-commit semantics, neutralization or rejection of
  executable repository-local Git configuration, and complete replacement-ref namespace inspection
  including packed/ref-backend storage. Do not merge the current PR head.
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

1. Reopen the C6c2 closure matrix in the plan of record and assign each of the three final-review
   blockers an owner, exact contract change, and regression fixture before editing the design again.
2. Re-scope or split the design slice so the gate head/ancestor proof, Git local-configuration
   isolation, and complete replacement-ref enumeration are independently coherent. Keep the current
   PR head as the terminal review checkpoint until that redesign is ready; do not begin another
   repair/review loop against the unchanged checkpoint.
3. After the redesigned slice is independently reviewable, use the repository's required review and
   merge workflow; only then continue with C6c1p and the documented Align adoption prerequisites.
4. Implement and merge C6c1p first; implement C6c2 only after C6a1/C6a2 provide content-validated
   decoded records and Requests 7/8/10/12/13 are adopted at named Align revisions. Otherwise record
   the dependency blocker and continue only with safe independent roadmap work.
5. Do not start JSON/document binding or failure-memory JSONL adoption until Request 7 is accepted,
   merged at a named Align commit, the pinned release is rebuilt, `.align-revision` is updated, and
   `make ci` passes the original acceptance gate.

## Latest verification

- C6c1 final evidence remains PASS: focused smoke, `make check`, `make fmt`, format/static checks,
  and `make ci` all passed before the merged `main` checkpoint.
- The previous C6c2 design branches are terminal, unmerged checkpoints; do not repair or merge them.
- Current corrected design verification: `git diff --check b485fb8..34be593` PASS, the targeted
  contract assertions for replacement/graft/alternate rejection, drift states, observed identities,
  pair cleanup, and their named regressions PASS, and the exact Markdown fence check over
  `docs/specs/c6-prompt-context-optimizer.md` and `docs/align-requests.md` reports
  `markdown_fences=172` (even). Source tests and `make ci` are N/A because this remains
  documentation/specification-only; PR #49 requires hosted documentation/static checks. The working
  tree is clean at this checkpoint. The conditional final review is recorded in GitHub and is not
  merge-ready; the next verification must follow the closure-matrix redesign rather than patching
  this checkpoint in place.

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
  states for align-llm, external Align, and corpus. A complete gate requires all three states to be
  `VERIFIED` with observed identities equal to the expected identities; `UNVERIFIED` remains a valid
  non-gate comparison. `PromptEvaluateRequest` owns the explicit source paths and expected
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
  `C6_GATE_GIT_EXECUTABLE_PATH` revalidation. The FILE_SET manifest is bounded and canonical, with
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
- Intentional uncommitted files: none at the last committed checkpoint; the next handoff must
  preserve the clean tree and this corrected design/review boundary.
