# Session handoff

A living continuity note for resuming align-llm on another machine or in a fresh Claude Code or
Codex session. Read `CLAUDE.md` first, then this file, then the relevant specifications named below.
Conversation history and per-machine memory are not project state.

_Last updated: 2026-07-29. The governance-only retrospective slice is active on
`agent/autonomous-design-retrospective`, based on merged Align #672 adoption commit `65f7766`.
Its substantive rule checkpoint is `617a9f7`; it applies generally reusable design-convergence
rules from `../align` and lessons from PR #15. C6 product implementation has not started. In the
primary worktree, modified `HANDOFF.md` and untracked
`docs/specs/c6-prompt-context-optimizer.md` intentionally belong to the C6 design draft and must
not be discarded._

## Current position

The repository has completed C0 through C5. PR #15 merged with a merge commit at `65f7766`, pins
Align #672 at `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`, refreshes the immutable C0 baseline, and keeps
its recorded source and oracle commits reachable. Its retrospective found three reusable lessons:
Git-internal automation must use the common directory in linked worktrees, historical provenance
must constrain the merge method, and aggregate check names must not be treated as proof that every
focused gate ran. The current governance slice turns those lessons into policy and checklist
coverage without mixing product or request-register changes.

Merged PR #14 records Align Request 5: C6 design review demonstrated that the current `std.http`
provider boundary buffers up to one GiB before an application-level size check can run.
Request 5 asks Align for a caller-selected receive-time response-body cap. Only the provider
proposal and real-provider gate are blocked; artifact, renderer, scorer, activation, and
deterministic evaluator work remain independent.

The bounded-receive contract applies its cap only after method/status-aware body framing. Final
`HEAD`/`204`/`304` responses have zero payload; non-`101` informational heads consume no payload and
continue to the final response without losing co-read bytes, while unsupported `101` upgrades fail
and close. Method tokens are case-sensitive, and Content-Length magnitude comparison normalizes
leading zeroes without target-size conversion. Request 4 and Request 5 share a combined
de-framing/bounded-receive gate; whichever reaches
`ALIGN_MERGED` second owns bodyless, interim-to-final, exact-cap, cap-plus-one, many-tiny-chunks,
trailer-guard, and aggregate-storage integration verification before `ALIGN_LLM_VERIFIED`. If they
ship together, Request 5's bounded-response adoption owns that gate and neither request reaches
`ALIGN_LLM_VERIFIED` until it passes. The numeric ceiling applies to Align HTTP-runtime-owned
response-byte storage; opaque TLS/kernel transport buffers are excluded, while final-header offset
tables and decoder records have separate fixed structural caps. Bounded discovery co-read stays in
one scratch allowance and stops after an excess is recognizable. A named fixed trailer-block wire
guard prevents a continuously arriving unterminated trailer from evading the storage ceiling or
timeout policy; trailer fields are validated incrementally but not retained or exposed. Successful
self-delimited responses remain pool-eligible, read-to-close responses do not, and
`get`/`post`/`request`/`get_many` all preserve the configured cap semantics. `get_many` workers share
one client-cap snapshot and deterministic lowest-index error selection.

- PR #9 (C3) merged at `5f883f8`; PR #10 (hosted Actions capability fix) merged at `a95c530`.
- PR #11 (C4) merged at `17da92c`. C4 adds `src/verification_loop.align` and
  `--verify-loop <task.json> <result.json>`, with candidate evaluation/application, bounded
  build/targeted/full verification, captured diagnostics, repair prompts, and one deterministic
  repair patch.
- C5 commit `05dbf75` adds `src/failure_memory.align`, optional `memory_profile` task input, append-only
  JSONL events, and matching-event injection into repair prompts. Profile failures are non-blocking
  after the result file is written.
- `scripts/run-verification-loop-smoke` now proves persistence, same-task reuse, and the existing
  invalid-repair `REPAIR_FAILED` path. `failure-memory-smoke` is the named C5 make target.
- Hosted Actions ran the supported C5 smoke successfully; no new external retry loop is warranted.
  The unavailable nested user-namespace `coding-v1` sandbox remains a local/capable-runner gate.

## Next steps

1. Complete author verification and independent preflight for
   `agent/autonomous-design-retrospective`, commit and push the coherent governance diff, and open
   its pull request. Record separate current-SHA host-native and independent-adversarial post-open
   review envelopes, wait for required checks, then merge only if all evidence remains current.
2. In a separate automation slice, make the local capable-runner gate and hosted supported gate
   topology explicit. `make ci` currently omits the C1-C5 focused smokes that PR #15 ran separately,
   while the hosted gate intentionally omits `coding-v1` and the canonical baseline gate.
3. In separate request-register slices, resolve the C6 design review's implemented-surface gaps:
   owned/unescaped typed-JSON strings, optional owned-record JSON payloads, and exclusive file
   creation. Do not hide them behind manual parsing or application-local compatibility layers.
4. Integrate refreshed `main` into the C6 design branch and close its full adversarial review,
   including the required closure matrix and exact implementation boundaries. Implement only
   independently valid slices whose prerequisites have shipped.

Do not rerun a failing external service request indefinitely. The Codex “high demand” message is a
service-capacity condition, not a repository or Actions failure. The central metric remains time to
a passing patch.

## Current governance verification

Verified on 2026-07-29:

```text
git diff --check                         PASS
make format-check                        PASS
test "$(readlink AGENTS.md)" = CLAUDE.md PASS
```

The rule port was checked against the `../align` `CLAUDE.md` changes between the former Align pin
`db942d2` and current pin `d9fb5da`. Align-specific Rust, release, and repository-script commands
were intentionally not copied. Pull request review and check state remains external GitHub metadata
bound to exact SHAs, not a branch commit recorded here.

## Align #672 adoption verification

The canonical baseline was recorded on 2026-07-29 from clean commit `a5de972` with the clean
detached Align checkout at `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`. The oracle is committed
at `bb9c636`, the finalized baseline at `03e6b15`, and the Git-worktree baseline regression fix at
`d3905d0`. Follow-up `cdd90fd` makes abnormal cleanup use the same resolved common Git directory.
The branch merged Request 5 registration commit `f79fb68` at `5dc6c59`, preserving the recorded
baseline source and oracle commits as ancestors.

```text
ALIGN_REPO=<clean detached Align #672 checkout> \
  python3 eval/runners/record-baseline.py \
    --corpus eval/tasks/coding-v1.json \
    --provider deterministic-reference \
    --model checked-in-patch \
    --prompt-version none \
    --samples 2 \
    --output eval/baselines/coding-v1-pin672-pending.json
# PASS — 2 deterministic samples; temporary pending file removed after finalization

python3 eval/runners/verify-baseline.py
# PASS

bash -n scripts/run-baseline-invalid-smoke
make baseline-check
# PASS — canonical, malformed-input, immutable-oracle, replacement-object, and failure retention
```

The first full `make ci` attempt reached the baseline replacement-object regression after all
compile, coding-corpus, timeout, and loop checks passed, then exposed that the smoke assumed
`.git` was a directory. `d3905d0` now resolves the absolute common Git directory, preserving the
same replacement-ref isolation in ordinary clones and linked worktrees.

```text
ALIGN_REPO=<clean detached Align #672 checkout> make ci
# PASS — 15 units check per-unit; build; smoke-v1; coding-v1 and containment/timeout regressions;
# loop paths; canonical baseline, invalid-baseline, replacement-object, and failure retention

ALIGNC=<clean detached Align #672 release alignc> \
  make provider-smoke index-smoke test-selection-smoke patch-eval-smoke failure-memory-smoke
# PASS — C1 provider, C2 index and test selection, C3 patch evaluation, C4 verification loop, and
# C5 failure-memory regression coverage

git diff --check
# PASS
```

## Completed bootstrap

PR #1, `Bootstrap the measured align-coder development cycle`, merged these intentionally
integrated bootstrap surfaces:

- `AGENTS.md` — Codex compatibility symlink to the canonical `CLAUDE.md`.
- `CLAUDE.md` — shared repository policy, English collaboration rules, mandatory
  PR-review-before-merge workflow, and handoff operation.
- `docs/align-requests.md` — Align responses and align-llm verification for the three shipped
  requests.
- `.align-revision`, `.github/`, `Makefile`, `scripts/`, and `docs/review-checklist.md` — pinned
  compiler, unified local/CI gate, pull request workflow, and shared review checks.
- `eval/tasks/`, `eval/expected/`, and `eval/runners/` — file-backed smoke corpus, deterministic
  score oracle, and runner.
- `src/main.align` — command entry points for the current demonstrations.
- `src/verify.align` — captured, timeout-bounded verification primitives.
- `src/eval.align` — declared JSON corpus loader and first deterministic C0 scorecard slice.
- `src/repair.align` — first provider-independent verify/repair loop skeleton.

The first executable evaluation, loop, CI, request lifecycle, and handoff rules were reviewed as one
bootstrap PR under the one-time exception in `CLAUDE.md`. That exception is now consumed: future
work returns to one roadmap gate or enabling slice per branch and PR. Review follow-ups resolved
diagnostic loss, loop bounds and exit coverage, task-identity checks, empty-corpus acceptance, the
effective compiler pin, request lifecycle evidence, and stale handoff state.

## C4 verification

Verified on 2026-07-25 against the current sibling Align checkout:

```text
make fmt                         PASS
make format-check                PASS
make check                       PASS — 14 imported units, including verification_loop
make build                       PASS
bash -n scripts/run-verification-loop-smoke  PASS
make index-smoke                 PASS
make test-selection-smoke        PASS
make patch-eval-smoke            PASS
make provider-smoke              PASS
make verify-loop-smoke           PASS — initial targeted failure repaired to full PASS in 2 iterations; invalid repair persisted as REPAIR_FAILED
git diff --check                 PASS
```

The full `make ci` gate was not rerun for C4. The supported hosted workflow was updated to include
the C4 smoke; no repeated retry is warranted for external service-capacity errors.

## C5 verification

Verified on 2026-07-25 against the current sibling Align checkout:

```text
make fmt                         PASS
make format-check                PASS
make check                       PASS — 15 imported units, including failure_memory
make build                       PASS
bash -n scripts/run-verification-loop-smoke  PASS
make index-smoke                 PASS — C2 regression
make test-selection-smoke        PASS — C2 regression
make patch-eval-smoke            PASS — C3 regression
make provider-smoke              PASS — C1 regression
make failure-memory-smoke        PASS — profile persistence, same-task prompt reuse, legacy task compatibility, and REPAIR_FAILED
git diff --check                 PASS
```

The full `make ci` gate was not rerun for C5. Hosted Actions already exercises the supported
verification-loop smoke; repeated external service-capacity retries remain out of scope.

## Historical verification

Verified on 2026-07-25 with pinned Align commit
`db942d2f705546c7d6b8c0334a462548c6446f84`:

```text
make fmt
# PASS — all Align source formatted; the previous dash-incompatible `read -d` recipe was fixed

make ci (using a clean detached checkout of the pinned Align revision)
# PASS — pinned Align revision matches
# PASS — pinned Align compiler and runtime release build is current
# PASS — formatter output matches every Align source file
# PASS — 5 units checked per-unit: project, verify, eval, repair, main
# PASS — executable built as ./main
# PASS — smoke-v1: 2 tasks, 2 PASS, 0 failed; identity and summary oracles match
# PASS — an empty corpus is rejected
# PASS — coding-v1: pinned fixture repair 1/1 PASS; disallowed edits and validation side effects
# rejected, including index-flag-, stat-cache-hidden-, special-mode, and directory-mode mutations;
# ignored fixture inputs and validation side effects rejected; ambient Git and Python settings and
# corpus interpreter dispatch isolated; system and global Git configuration and attributes disabled;
# timeout
# and normal-completion process-tree cleanup,
# descendant reaping, and temporary checkout cleanup verified; missing child-subreaper, bubblewrap
# namespace, or resource wrapper support fails closed; validation cannot mutate the host filesystem or
# Git metadata; Git replacement objects are ignored; pre-validation byte/mode and untracked/ignored
# mutations are rejected; validation `/tmp` and `/dev/shm` tmpfs, process/file/address-space,
# aggregate RSS, deleted-open-FD,
# adopted-descendant, aggregate file-count, and writable-worktree quotas are enforced with bounded
# scans; NUL-delimited Git path handling and whitespace-path regression isolated; symlink fixture
# preservation and post-validation allowlisted-file mutation rejected; non-UTF-8
# diagnostics retained and bounded before buffering; non-passing baseline stdout and stderr
# diagnostics are persisted; concurrent baseline replacement-ref smoke runs are isolated
# PASS — canonical baseline metadata, source commit, artifact digests, immutable oracle, task identity, summaries,
# corpus task order and expected codes, and strictly typed numeric aggregates verified; malformed
# aggregates and verdicts rejected; measured Python runtime, pin checker provenance, and complete
# non-passing results retained
# PASS — loop spike: pass, give-up, stdout-driven repair/reverify, exhaustion, timeout, and
# zero-budget paths match their oracle

for file in eval/runners/run-fixed.sh scripts/check-* scripts/run-eval-invalid-smoke \
  scripts/run-loop-smoke scripts/run-baseline-invalid-smoke scripts/run-coding-task-*; do
  bash -n "$file"
done
# PASS

python3 -m json.tool <each task, manifest, expected summary, and canonical baseline>
# PASS

git diff --check
# PASS
```

## C1 verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 11 imported units, provider modules included
make build                       PASS — executable built as ./main
bash -n scripts/run-provider-smoke  PASS
./scripts/run-provider-smoke     PASS — provider adapters, env-backed auth, Cloud HTTP rejection, SSE error and DONE-only rejection, timeout, HTTP status 429, exact assembled Llama prompt count, common result format v2
git diff --check                 PASS
```

`make ci` has intentionally not been rerun for this feature slice; the focused provider gate is the
relevant verification, and CI repetition is not useful while the Align chunked-response capability
remains unshipped. The focused smoke uses a temporary HTTP fixture; real Cloud OpenAI calls require
HTTPS and read the key from an environment variable name supplied to the CLI.

## C2 verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 12 imported units, including repo_index
make build                       PASS — executable built as ./main
bash -n scripts/run-index-smoke  PASS
make index-smoke                 PASS — tracked files, NUL-safe path, declarations/imports/tests, revision binding, failure persistence
make provider-smoke              PASS — C1 provider regression smoke
git diff --check                 PASS
```

The full `make ci` gate was not rerun; CI repetition is intentionally out of scope for this
feature implementation.

## C2 lexical-reference verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 12 imported units, including repo_index
make build                       PASS — executable built as ./main
bash -n scripts/run-index-smoke  PASS
make index-smoke                 PASS — qualified/local references, escaped string and comment exclusion, prior C2 coverage
make provider-smoke              PASS — C1 provider regression
git diff --check                 PASS
```

The independent adversarial reviewer did not return within one bounded wait and was shut down;
manual review of the changed surface found no blocking functional finding. The full `make ci` gate
was not rerun.

## C2 semantic-resolution verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 12 imported units, including repo_index
make build                       PASS — executable built as ./main
bash -n scripts/run-index-smoke  PASS
make index-smoke                 PASS — public/local resolution, external and unresolved targets, module declaration check, prior C2 coverage
make provider-smoke              PASS — C1 provider regression
git diff --check                 PASS
```

The independent review CLI completed one bounded run; its verbose internal output was truncated by
the runner, so the changed surface was also manually reviewed against the checklist and pinned
Align module rules. No blocking functional finding remains. The full `make ci` gate was not rerun.

## C2 related-test selection verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 12 imported units, including repo_index
make build                       PASS — executable built as ./main
bash -n scripts/run-index-smoke scripts/run-test-selection-smoke  PASS
make test-selection-smoke        PASS — deterministic basename/directory ranking, stable order, revision binding, failure persistence
make index-smoke                 PASS — prior C2 index and semantic-resolution coverage
make provider-smoke              PASS — C1 provider regression
git diff --check                 PASS
```

The full `make ci` gate was not rerun; repeated CI is intentionally out of scope for this feature
implementation.

## C3 patch-evaluator verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 13 imported units, including patch_eval
make build                       PASS — executable built as ./main
bash -n scripts/run-patch-eval-smoke  PASS
make patch-eval-smoke            PASS — diff shape, hunk-context symbols, risk/public-API/unrelated signals, recommended tests, failure persistence
make test-selection-smoke         PASS — C2 related-test regression
make index-smoke                 PASS — C2 index and semantic-resolution regression
make provider-smoke               PASS — C1 provider regression
git diff --check                 PASS
```

The follow-up `053357e` also classifies changed hunk lines that begin with `+++` or `---` as data
after the hunk marker, preserving valid unified-diff content. The full `make ci` gate was not
rerun; repeated CI is intentionally out of scope for this feature implementation.

## Superseded C3 handoff

1. Push `3581c79` and `053357e` on `c3-patch-evaluator`, update PR #9, and review the changed
   surface once.
2. Apply only valid findings, rerun the focused patch-evaluator and C2 verification, and merge with
   a merge commit. Do not repeat the full CI gate or wait on a non-returning reviewer.
3. After merge, continue with C4 Verification Loop. Keep Request 4 limited to real chunked SSE
   acceptance; it does not block the evaluator or verification work.

## Constraints to preserve

- Use `make check`, `make run`, `make fmt`, and `make build`; do not invent an Align manifest or
  package workflow.
- `make ci` requires a clean sibling checkout at `.align-revision`, builds its release compiler,
  and forces all project gates to use that exact executable. Change the pin deliberately and rerun
  the full gate when adopting a newer Align compiler.
- Canonical baseline recording also rebuilds the pinned compiler and `main`; never measure an
  existing ignored binary. Task wrappers must declare all executable inputs in `artifact_paths`.
- PR #3 must use a merge commit rather than squash so the recorded source commit remains reachable.
- A captured process's stdout and stderr are region-bound views. Clone them before returning owned
  diagnostics, as `src/verify.align` does.
- Align #672 supports recursive Move `Option`/`Result` and tagged payloads. Existing bare Move
  result forms remain valid; change them only when a reviewed consumer contract benefits from the
  newer surface.
- Bind an owned `string` to an explicit `str` view before passing it through an indirect function
  value.
- Reusable command arguments cross loop iterations as `slice<str>` and are materialized for
  `std.process` per run.
- Provider SSE parsing currently depends on Content-Length framing because Align's shipped
  `std.http` client rejects chunked response bodies; do not add a raw-socket compatibility layer.
- C1 is merged at `b7068e6`; the first C2 index slice is merged at `d59c5ce`; the lexical-reference
  slice is merged at `348c3a5`; semantic resolution is merged at `91ec8455f9316a3c702cfbe17f609e376a43cc70`;
  related-test selection is merged at `4cb217b7f901019e689bba36c88a41322d2cf51e`; the current
  patch evaluator is committed at `3581c79`.
- C2 uses Git's tracked-file list (`git ls-files -z`) rather than recursively probing filesystem
  entries; do not replace it with a directory walk that loses repository boundaries or newline
  safety.
- C2 currently parses top-level Align declarations/imports and lexical references, then resolves
  same-file functions and tracked user-module public function/type targets using the importing
  file's directory as the index base. Related-test selection is path-based and deterministic; it
  does not yet use the resolved symbol/reference graph.
- C3 currently parses standard unified-diff markers read-only. It uses hunk context for a bounded
  symbol signal, conservative path heuristics for unrelated diff, and a documented line-signal
  risk score. Do not claim full language-aware diff analysis or patch application until later
  slices ship.
- Source, comments, diagnostics, commits, pull requests, reviews, and releases are written in
  English.

## Read next

- `docs/specs/roadmap.md` — delivery order and gates.
- `docs/specs/align-llm.md` — architecture and system principles.
- `docs/align-requests.md` — shipped Align capability details and ownership limits.
- `docs/align-development.md` — local sibling-compiler workflow.
