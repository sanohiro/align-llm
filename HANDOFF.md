# Session handoff

A living continuity note for resuming align-llm on another machine or in a fresh Claude Code or
Codex session. Read `CLAUDE.md` first, then this file, then the relevant specifications named below.
Conversation history and per-machine memory are not project state.

_Last updated: 2026-07-29. The validation-worktree unlink-race implementation is active on
`agent/validation-unlink-race-implementation`, based on merged exact-source governance commit
`13177c9`. Its plan of record is `docs/specs/validation-worktree-unlink-race.md`; the runner,
deterministic exact-source regression helper, invalid-smoke integration, documentation, and
identity-coupled baseline refresh were complete at source commit `712b313`, oracle commit
`3bc1ee2`, and finalization commit `e23dd9e`. Preflight found that the integrated helper did not
establish the required bytecode-disabled redirected-cache ambient state and gave five numbered
cases shared rather than independent five-second timer scopes. Both helper defects are corrected;
the replacement chain is source commit `03ce5ba`, oracle commit `976af31`, and finalization commit
`89fe54c`. A fresh preflight closed the timer finding but found that the exact sentinel load still
ran inside ordinary-import normalization and that the production load ran after the synthetic
nondefault ambient state was removed. The loader scopes are now corrected; the exact source →
oracle → finalization replacement is source `883f3f7`, oracle `d05e9f4`, and finalization
`2d05d47`. Full verification passes. Independent preflight was clean, but host preflight found that
the helper's failure injection occurred after successful ordinary loads rather than inside the
ordinary-loader normalization scope. The helper now performs a real missing-source ordinary load
inside that scope and asserts exact restoration. The active replacement is source `924fc58`, oracle
`c291cdb`, and finalization `a795284`; full verification passes and fresh preflight remains.
Post-open host-native review then found a cleanup gap between body-error capture and the manual
iterator-close block. The iterator owner scope now uses a real `finally`, and a seventeenth
exact-source case injects an asynchronous `BaseException` at that boundary and proves close is
attempted. The active replacement is source `a488262`, oracle `0807ce6`, and finalization
`17d6886`; full verification passed. Fresh preflight found a remaining gap between scan acquisition
and entry into that owner scope. The owner scope now starts with an unowned sentinel before
acquisition, and the seventeenth case covers both the post-acquisition and post-capture boundaries.
The active replacement is source `80735f1`, oracle `c3fa251`, and finalization `bea4e8c`; full
verification passed. Fresh preflight then found the remaining call-return-to-variable-store opcode
window. Ownership now transfers through direct context-manager entry, whose exception table owns
cleanup before the entered iterator is stored. The seventeenth case interrupts that exact store
opcode and the later body-error capture boundary. The active replacement is source `03d5651`,
oracle `f63d4c7`, and finalization `e2ce22b`; full verification passed. Fresh preflight found that a
close-time `FileNotFoundError` at the same pre-binding boundary could be mistaken for a queued-scan
disappearance because `entered` was still false. The runner recovered the replaced interruption
from the close exception's context and applied ordinary body-over-close precedence. The opcode case
also covers close failure. That replacement was source `1bf428e`, oracle `1a0763f`, and
finalization `ffbbe87`; full verification passed. Fresh preflight then found that an incidental
exception context created inside scan construction or context entry could be mistaken for the
owner-frame interruption. The active correction authenticates the recovered context by requiring
its traceback to contain the current `validation_worktree_usage` frame and adds construction and
entry counterexamples. The active replacement is source `d840256`, oracle `ea28044`, and
finalization `bef2153`; full verification passed. Fresh preflight found that close could handle an
internal exception before raising `FileNotFoundError`, placing the owner-frame interruption more
than one link deep in the context chain and allowing the close error to enter the queued-directory
skip. The active correction walks that chain with cycle detection, authenticates only the exception
whose traceback contains the current owner frame, and adds nested-cleanup and cyclic-context
regressions. The active replacement is source `f0f32ca`, oracle `a74d304`, and finalization
`f40ac31`; full verification passed. Fresh host-native preflight found that an interruption at the
post-body-capture boundary was still lost when close also failed because the authenticated recovery
ran only before `entered` became true. The active correction applies the same cycle-safe
owner-frame recovery to every uncaptured interruption replaced by close and adds direct and nested
close-failure subcases at the post-capture boundary. The active replacement is source `27a1d09`,
oracle `92bf3cb`, and finalization `7fec276`; full verification passed. Fresh preflight found that
an ordinary `TaskError` at the queued-child store followed by close FNF was correctly excluded from
asynchronous recovery but still misclassified the cleanup FNF as scan-construction disappearance.
The active correction separately records owner-frame context as proof that cleanup replaced body
control, while recovering only exceptional-control-flow `BaseException`; it adds the ordinary-error
counterexample. The active replacement is source `1d2b0a2`, oracle `8275865`, and finalization
`ef2a034`; full verification passes. Fresh host-native preflight found that an interruption after
`body_error` storage but before handler exit still restored the prior body error, and that the
helper's per-case alarm could be swallowed through the same precedence path. The active correction
walks the escaping error even when a body error was already captured, interrupts the exact
post-storage opcode in all three close modes, and records alarm delivery independently from the
raised alarm exception. The active replacement is source `de27964`, oracle `9d278d3`, and
finalization `48ef063`; full verification passes. Fresh independent preflight found that timer
arming still occurred before the per-case cleanup scope, so an arm failure leaked the installed
handler. The active correction protects the arm operation and adds a sentinel that proves arm
failure skips the action, attempts cancellation, and restores the exact prior handler. Its
replacement is source `0fc80f9`, oracle `f7fba1e`, and finalization `110889a`; full verification
passes. Fresh independent preflight found that a cancellation error could still escape before the
recorded timeout or prior action error was re-raised. The active correction captures cancellation
failure separately and applies timeout-delivery, arm/action-error, then cancellation-error
precedence after exact handler restoration; deterministic sentinels cover both competing-error
cases. Its replacement is source `d265500`, oracle `0198362`, and finalization `962b188`; full
verification passes. Before fresh preflight, the cancellation matrix was completed proactively
with cancellation-only and arm-error-plus-cancellation sentinels, covering every primary-error
state against cancellation failure. Its replacement baseline chain remains to be recorded.
The preserved implementation
branch `agent/check-gate-topology-implementation` has a passing complete gate and finalized
baseline, but preflight review found that target-scoped `.NOTPARALLEL` requires GNU Make 4.4 while
the declared Ubuntu 24.04 hosted runner supplies GNU Make 4.3. The same review found checker
validation-precedence and bounded-capture gaps, plus a separate validation-directory unlink race.
Do not update that implementation until the separately scoped runner fix, including its own
identity-coupled baseline refresh, merges. C6 product implementation has also not started. In the
primary worktree, modified
`HANDOFF.md` and untracked
`docs/specs/c6-prompt-context-optimizer.md` intentionally belong to the C6 design draft and must
not be discarded._

## Current position

The repository has completed C0 through C5. PR #19 merged at `29d2315`, correcting the explicit
hosted, capable, and canonical CI topology design for GNU Make 4.3 portability, supported-input
propagation, aggregate coexistence, checker validation precedence, and bounded child capture.
The implementation branch has the complete topology, the required source → oracle → finalization
history, and a passing `make -j8 ci`. Preflight review then found one portability defect in the
design: target-scoped `.NOTPARALLEL` is a GNU Make 4.4 feature, but the declared Ubuntu 24.04 hosted
runner supplies GNU Make 4.3. The same review found that the checker interleaves the specified
missing/non-ASCII validation phases and buffers self-test child output without the specified bound.
The merged correction preserves the serialized first-failure contract with one explicit `-j1`
recursive Make per aggregate, clears inherited Make option variables at that child boundary, and
closes the checker acceptance coverage. It also requires `hosted-checks`, `capable-checks`, or `ci`
to be the sole goal in a top-level Make invocation and rejects any additional goal before side
effects, because otherwise parent work or separate `-j1` children can still overlap; concurrent
independent Make processes remain unsupported verification evidence. PR #19's retrospective found
two generally reusable rules: test compatibility at the minimum declared version, and close every
state-sharing public-entrypoint combination plus both sides of an option-isolation boundary. PR #20
merged those rules at `34eac17`.

PR #21 merged at `93bab2f`, establishing the reviewed validation-worktree unlink-race contract and
its identity-coupled implementation boundary. Its retrospective found that regression helpers
which execute repository source must bind execution to the exact reviewed bytes rather than assume
import configuration defeats valid stale caches, and must restore cache and interpreter-global
state on success and failure. The active governance follow-up adds that reusable review rule before
the runner implementation begins. The ledger-order finding needs no additional rule because the
existing authoritative-ledger and consistency-pass requirements detected and closed it. PR #22
merged the resulting exact-source, complete cache/interpreter restoration, and immutable-base
full-diff review rules at `13177c9`. Its retrospective found no further reusable policy beyond the
rules already merged.
After the runner correction merges, the topology implementation must integrate refreshed `main`
and re-record the canonical baseline again because `Makefile` is an identity-bound artifact. The
checker correction remains in that same topology source commit but is not itself in the recorded
artifact manifest.

PR #16 merged at `c20e919`, adding the applicable Align
design-convergence rules and the bounded post-merge retrospective. Its review caught and fixed
transient PR mechanics in `HANDOFF.md`; the existing durable-state rule and the new checklist item
now cover that reusable lesson, so no additional governance slice is queued. That rule port was
checked against the `../align` `CLAUDE.md` changes between the former Align pin `db942d2` and
current pin `d9fb5da`; Align-specific Rust, release, and repository-script commands were
intentionally not copied.

PR #15 merged with a merge commit at `65f7766`, pins
Align #672 at `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`, refreshes the immutable C0 baseline, and keeps
its recorded source, oracle, and finalization commits reachable. Its retrospective found three
reusable lessons:
Git-internal automation must use the common directory in linked worktrees, historical provenance
must constrain the merge method, and aggregate check names must not be treated as proof that every
focused gate ran. The merged governance slice turned those lessons into policy and checklist
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

1. Commit the complete timer-cancellation matrix, run the focused helper in default and
   redirected-cache ambient states, and record and finalize its exact replacement baseline.
2. Rerun full `make ci` and the complete positive and negative provenance harness, then run fresh
   full-diff host-native and independent-adversarial preflight against that exact chain.
3. Push the replacement source/oracle/finalization chain to PR #23, complete separate host-native
   and independent-adversarial post-open reviews for the new exact SHA set, and merge only with a
   merge commit that preserves all three recorded identities. Recheck the focused helper, baseline,
   provenance block, and pending absence on refreshed `main`.
4. After merge, summarize PR #23 and the reusable-rule candidates, then stop as requested. Do not
   start a governance follow-up or resume the preserved topology or C6 branches in this run.

Do not rerun a failing external service request indefinitely. The Codex “high demand” message is a
service-capacity condition, not a repository or Actions failure. The central metric remains time to
a passing patch.

## Current validation-worktree implementation verification

Verified on 2026-07-29:

```text
git diff --check                         PASS
make format-check                        PASS
python3 scripts/run-coding-task-resource-scan-smoke PASS
scripts/run-coding-task-invalid-smoke    PASS
make eval-coding                         PASS
make baseline-check                      PASS
ALIGN_REPO=<clean Align d9fb5da> make ci PASS
section-2.4 positive and negative provenance harness PASS
```

The active slice is based on merged PR #22 commit `13177c9`. The focused helper passes against exact
runner source bytes and covers the reviewed disappearance, fail-closed, deadline,
iterator-cleanup, ceiling, and root-only `.git` contract. It now also establishes and restores
bytecode-disabled redirected-cache ambient state before loading the production runner and gives
each numbered case a fresh five-second timer. The superseded canonical baseline records
source `712b3138f646592e57944da01e3049d844fc4d6c`, immutable oracle
`3bc1ee222b1d40f21c09fa93f3d2d92f4be0ca06`, and finalization
`e23dd9e33169c89c46c6a120e7368fbcc75f9bda`; both samples and the complete positive and negative
structural harness passed before the helper follow-up. The replacement baseline records source
`03ce5ba56b5c81be268d63f9f75d49f2fb61ed8c`, immutable oracle
`976af313a2a2d9a4e90b27ad500a5e30d1d7a024`, and finalization
`89fe54ca84794116a2c6c0942810db0884d6ef75`; both recorded samples pass. Focused helper verification
passes under default and explicit bytecode-disabled redirected-cache ambient settings, and
`make ci` passes with the pinned Align checkout. The complete positive structural block passes.
The isolated negative harness rejects persisted-source, sample, oracle-order/final-LF, symbolic and
annotated-object identity, linear restore, injected log failure, and all four TREESAME merge-hidden
path classes; pre-owner side history remains accepted. That chain and evidence are superseded by
the loader-scope correction. The active replacement baseline records source
`883f3f7b0b7f90e030c3e424fe5259a1e9f85af4`, immutable oracle
`d05e9f4a45589f5993676f39e68f54f7f34eaf35`, and finalization
`2d05d47ead8abc1257ba16970f11def981bd3b44`; both samples pass. Focused helper verification passes
under default and explicit bytecode-disabled redirected-cache process settings, `make ci` passes
with the pinned Align checkout, and the complete positive and negative provenance harness passes.
The preserved topology implementation head remains `7290e37`; its recorded chain is intentionally
stale until this runner correction and baseline refresh merge. The active `883f3f7` chain is
superseded by the ordinary-loader failure regression. The active replacement baseline records
source `924fc585a27b301e936eadd2b9a686aa598c9083`, immutable oracle
`c291cdb8a27d68633f76ef7e296692aa6923027c`, and finalization
`a795284191925d50578ab997355c8f12bda451c3`; both samples pass. Focused helper verification passes
under default and explicit bytecode-disabled redirected-cache process settings, `make ci` passes
with the pinned Align checkout, and the complete positive and negative provenance harness passes.
This chain is superseded by the post-open iterator-owner cleanup correction; the focused helper now
has 17 cases and proves close is attempted when a `BaseException` interrupts body-error capture.
The active replacement baseline records source
`a4882627b44b43d73bbbf5220bfa041d99fcdd0e`, immutable oracle
`0807ce677c12ddf3390f4a10feab5ded27ea69e9`, and finalization
`17d68864dd7242be040eadb0c057476a7eb0e967`; both samples pass with
min/median/max `1,729,770,721 / 1,736,149,041 / 1,742,527,361 ns` and no performance claim.
Focused helper verification passes under default and explicit bytecode-disabled redirected-cache
process settings, `make ci` passes with the pinned Align checkout, and the complete positive,
scalar/linear negative, merge-hidden, and pre-owner provenance harness passes.
That chain is superseded by the acquisition-boundary owner-scope correction. The active replacement
baseline records source `80735f1a1d8157fc7973fcd783171358a917835c`, immutable oracle
`c3fa251c5b7875e3ac42bd13f426151953d1639d`, and finalization
`bea4e8c4f9231bb8a67a405f4aca971ff6889473`; both samples pass with min/median/max
`1,742,536,793 / 1,746,891,402 / 1,751,246,012 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings,
`make ci` passes with the pinned Align checkout, and the complete positive, scalar/linear negative,
merge-hidden, and pre-owner provenance harness passes.
That chain is superseded by the context-entry ownership correction. The active replacement baseline
records source `03d56513248146a8daf7ddcf5374990de3835289`, immutable oracle
`f63d4c72b2e4ff295a8ab3cfc71b18c4422537b1`, and finalization
`e2ce22b4e00547561c0955f9d621e796b5fc4779`; both samples pass with min/median/max
`1,800,065,211 / 1,829,085,046 / 1,858,104,881 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings,
`make ci` passes with the pinned Align checkout, and the complete positive, scalar/linear negative,
merge-hidden, and pre-owner provenance harness passes.
That chain is superseded by the pre-binding cleanup-classification correction. The replacement
baseline records source `1bf428e45ef0a60d863010334e773b723dde4603`, immutable oracle
`1a0763f3d292132bc1c4004b3195f6942832b93e`, and finalization
`ffbbe87b899e8aadd88001d3e4481bb372a9b1f0`; both samples pass with min/median/max
`1,855,509,925 / 1,857,476,640 / 1,859,443,356 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings,
`make ci` passes with the pinned Align checkout, and the complete positive, scalar/linear negative,
merge-hidden, and pre-owner provenance harness passes. Fresh preflight superseded this chain after
finding that incidental construction/entry exception contexts were not distinguished from an
owner-frame interruption. The active authenticated-context baseline records source
`d84025664a89737affee459bb305f805131e2ddb`, immutable oracle
`ea28044a4a3a5134266d0e8ad12b8cb730c36e1b`, and finalization
`bef21532b78ebaecd7ee5814340a3613e4376a02`; both samples pass with min/median/max
`1,915,692,348 / 1,916,355,108 / 1,917,017,869 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings,
`make baseline-check` and pinned-Align `make ci` pass, and the complete positive, scalar/linear
negative, merge-hidden, and pre-owner provenance harness passes. Fresh preflight remains.
That chain is superseded by the nested-cleanup context-chain correction. The active replacement
baseline records source `f0f32caddc7862327ac6ce085ad38481647414e5`, immutable oracle
`a74d3041f19be7ee54abe2baaed12a2dfc4856ea`, and finalization
`f40ac313d7571b0317c047317391d2d601aa0e8a`; both samples pass with min/median/max
`1,944,084,473 / 1,948,976,768 / 1,953,869,064 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings,
`make baseline-check` and pinned-Align `make ci` pass, and the complete positive, scalar/linear
negative, merge-hidden, and pre-owner provenance harness passes. Fresh preflight remains.
That chain is superseded by the post-capture close-failure correction. The replacement baseline
records source `27a1d0903356b9f889d211eda271dd27d0e226ab`, immutable oracle
`92bf3cbbac9e8ff402f4322e5aad936094b27539`, and finalization
`7fec276fc55c854e6091a5901edf52b58254c670`; both samples pass with min/median/max
`1,959,879,607 / 1,985,010,259 / 2,010,140,912 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings,
`make baseline-check` and pinned-Align `make ci` pass, and the complete positive, scalar/linear
negative, merge-hidden, and pre-owner provenance harness passes. Fresh preflight superseded this
chain with the cleanup-versus-construction classification finding described above.
The active replacement baseline records source
`1d2b0a2cd2eb75766816424b3a748788be700408`, immutable oracle
`8275865c1ad80b364c9090f3eb75908d63eb60dc`, and finalization
`ef2a03413eb6a134aeb547aa654659cba703074a`; both samples pass with min/median/max
`2,000,225,848 / 2,016,281,944 / 2,032,338,040 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings.
`make baseline-check` and pinned-Align `make ci` pass. The complete positive, scalar/linear
negative, merge-hidden, and pre-owner provenance harness passes. The helper covers all six
combinations of the queued-child store and post-body-capture ownership boundaries with close
success, direct `FileNotFoundError`, or nested internal error followed by `FileNotFoundError`;
construction/entry incidental and cyclic contexts; failed entry without exit; and the ordinary
`TaskError` counterexample. Cleanup-path authentication is recorded independently from
exceptional-control-flow recovery, so the ordinary body error followed by close failure remains
fail-closed rather than entering the queued-directory disappearance skip. Fresh exact-chain
preflight superseded this chain after finding the post-capture and swallowed-alarm gaps described
above.
The active replacement baseline records source
`de27964c0ba69b1e3c1f796fa17f53b2cb68bf5b`, immutable oracle
`9d278d3c557c33768c3059dcdb0fa7cd600e555f`, and finalization
`48ef0635b376551ea1eb52a1594bc63691dd234c`; both samples pass with min/median/max
`2,065,180,529 / 2,087,770,044 / 2,110,359,559 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings,
including all six owner-boundary/close-mode combinations at the queued-child store and the
`POP_EXCEPT` immediately after body-error storage. The pre-case swallowed-alarm sentinel proves
alarm delivery remains fatal after the raised `CaseTimedOut` is caught. `make baseline-check` and
pinned-Align `make ci` pass. The complete positive provenance block passes; the isolated negative
harness rejects all 15 scalar/linear categories and all four TREESAME merge-hidden path classes
with simplified/full counts `0 / 2`, while pre-owner side history remains accepted. Fresh
exact-chain preflight superseded this chain after finding the timer-arm cleanup gap described
above.
The active replacement baseline records source
`0fc80f9a3569339cade22527ecd9aae5a06c6fda`, immutable oracle
`f7fba1e0ce2a6e4744dae443262b3757343deb2b`, and finalization
`110889a3869d6b211e90eeb78a44d62c4d0fec0a`; both samples pass with min/median/max
`2,168,944,401 / 2,187,272,249 / 2,205,600,097 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings.
The timer-arm sentinel proves failure skips the action, attempts cancellation, and restores the
exact prior handler; the swallowed-alarm sentinel and all 17 fresh per-case timers remain passing.
`make baseline-check` and pinned-Align `make ci` pass. The complete positive provenance block
passes; the isolated negative harness rejects all 15 scalar/linear categories and all four
TREESAME merge-hidden path classes with simplified/full counts `0 / 2`, while pre-owner side
history remains accepted. Fresh exact-chain preflight superseded this chain after finding the
timer-cancellation precedence gap described above.
The active replacement baseline records source
`d265500c8f6f7c8bf35c772cbf33e1831bf556e7`, immutable oracle
`0198362b23c3d7d5ca7a8ce1e2eaeb0e17bcd722`, and finalization
`962b1888bd9e7795766fbcda1c26f5678a127fd1`; both samples pass with min/median/max
`2,341,263,102 / 2,368,139,670 / 2,395,016,238 ns` and no performance claim. Focused helper
verification passes under default and explicit bytecode-disabled redirected-cache process settings.
Timer sentinels prove arm-failure restoration, swallowed-alarm detection, timeout-over-cancellation
precedence, and action-over-cancellation precedence; all 17 fresh per-case timers remain passing.
`make baseline-check` and pinned-Align `make ci` pass. The complete positive provenance block
passes; the isolated negative harness rejects all 15 scalar/linear categories and all four
TREESAME merge-hidden path classes with simplified/full counts `0 / 2`, while pre-owner side
history remains accepted. This chain is superseded by the complete cancellation-failure matrix
described above.

Pull request review and check state remains external GitHub metadata bound to exact SHAs, not a
branch commit recorded here.

## Align #672 adoption verification

The canonical baseline was recorded on 2026-07-29 from clean commit `a5de972` with the clean
detached Align checkout at `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`. The oracle is committed
at `bb9c636`, the finalized baseline at `03e6b15`, and the Git-worktree baseline regression fix at
`d3905d0`. Follow-up `cdd90fd` makes abnormal cleanup use the same resolved common Git directory.
The branch merged Request 5 registration commit `f79fb68` at `5dc6c59`, preserving the recorded
baseline source, oracle, and finalization commits as ancestors.

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
