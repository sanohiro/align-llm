# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active: R6-DECODE-KV-STEP1 (2026-08-29)

Branch `agent/r6-decode-kv-step1`, started from `main` at `c21b9e4` and **merged** with `main`
`76246f3` (R3-DECODE-RESIDENCY, PR #142) rather than rebased over it, so its recorded commits stay
reachable. **Three commits and one merge, nothing uncommitted:** `73557dc` is the capability,
`1671810` is the consolidated review repair, and `5445c14` is the narrow repair of the final delta
review's minors. Reviewers read `73557dc` against base tip `76246f3` with merge base `c21b9e4`; the
final delta review read `1671810`.

**Capability.** One decode step at `n_past = T` over an Align-owned KV plane, dense Qwen2.5-Coder-7B
Q4_K_M, CPU. `docs/specs/r6-decode-kv-step1.md` is the authoritative ledger. The design gate is
triggered — new public CLI surface, new exchanged format, coordinated invariant across six modules —
and the design was complete before implementation began.

**Complete and committed.** `align_ggml_op_concat` across the six FFI surfaces; `WHEN_DECODE`,
`OP_CONCAT`, the two plane slots (64/65), `mf_write_mask_offset`, the thirty-eight-row decode layer
table and its oracle map in `src/layer_qwen2.align`; the id/position split in
`src/model_forward.align`; the multi-graph transcript scan in `src/layer_forward.align`;
`src/decode_step.align` and its `--decode-step` arm; the fixture's decode reference and two-graph
transcript; the fifth `layer-forward-smoke` block and `scripts/decode-step-golden.jsonl`;
`scripts/run-decode-step` and the `decode-step-qualification` target; roadmap item 27,
`docs/align-development.md`, and Align Request 49. The real-model qualification is recorded in
ledger section 5.1.

**Review and repair.** One comprehensive review of `73557dc` over two independent reviewers on
disjoint risks. Reviewer B (spec/docs/governance) requested changes: 1 blocker, 4 major, 8 minor.
Reviewer A (Align/C/FFI) approved with 1 major and 6 minor. All 20 findings have a disposition and
are repaired in `1671810`, except the blocker, which is a **publication step** rather than a code
change and is next action 1 below. One final delta review of that repair approved it with three
minors — the R5A/R5B ledgers still described `MAX_PREFILL_TOKENS` as 6 and carried no
`R5_ORACLE_TRUNCATED` row; `verify_plane`'s size-disagreement early return named `k` even when only
the V concat row disagreed; and neither of that function's size guards has a shipped case — and
`5445c14` repairs all three. The repair narrows records and one diagnostic rather than expanding
scope, so no further full review is required.

The repair changes behaviour in two places and both are recorded in the ledger:

1. **A new refusal, `R5_ORACLE_TRUNCATED`** (ledger 2.7). Section 2.7 lifted `MAX_PREFILL_TOKENS`
   from 6 to 8 and documented at the constant that the cap was the oracle's. Documenting it was not
   a mitigation: `printed_count` clamps to six on both sides, so `--layer-forward`/`--model-forward`
   would have accepted `T` of 7 or 8 **with a transcript** and reported `PASS` over six of seven
   rows. Both arms now refuse that combination at their token stage. Without a transcript the same
   token count is admitted, which is what `--decode-step`'s own characterization pass needs.
2. **`graph.slot_high_water` is a maximum again.** `src/decode_step.align`'s copy of
   `model_forward.account` had dropped the `slot_high_water` line, so a run failing inside the
   prefill published 0.

Everything else is consistency: the shipped acceptance rule is now stated **once**, in ledger
section 2.11 (A, B, and C are all acceptance; an oracle A `FAIL` is admitted only inside the 0.5
bound **and** with oracle C byte-identical), with sections 3.3/3.4/5.1/10.2, the runner, the
roadmap, and `docs/align-development.md` pointing at it rather than paraphrasing it.

**Three mutants became shipped cases.** `ds-force-plane-stage-offset` (`R6_PLANE_MISMATCH`, which
was previously reachable only by mutating the source and was absent from `REQUIRED_CODES`),
`ds-force-decode-position`, and `ds-force-mask-offset`. Each is keyed on a slot only the decode
graph writes.

**Verification checkpoint (repair head).** `gmake build`, `gmake check`, `gmake fmt`,
`gmake format-check`, `git diff --check`, `gmake gate-topology-check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` — all five blocks, 40 documented decode-step cases reaching 23 codes —
pass. The four reviewer mutants and the new plane mutant were re-injected at the repair head and all
five still die with their distinct diagnoses: `R5_SHAPE node[24]` / `node[22]`, oracle A `FAIL` at
8092 on `q_rope` / 514 on `kqv`, and `R6_PLANE_MISMATCH layer[0]tensor[k]col[0]`.

**`gmake decode-step-qualification` was re-run on the real model at the repair head and again at the
publication head; both passed.** Every recorded value in ledger 5.1 reproduced on each: decoded
tokens 671/715/2691/526, oracle A `FAIL` at 2391 on `ffn_inp-27` for the first prompt and `PASS` at
0 for the other three over 5,058 elements each, oracle B `IDENTICAL` over 688,128 and 344,064 bytes,
oracle C byte-identical on all four with the argmax pairs 26312/262/1159/11844, `plane.bytes`
29,360,128, nodes 958/1014. Only the timings moved. Ledger 5.1 records all four runs. The
publication-head run took 3 m 48 s wall and was taken concurrently with an unrelated aggregate on
this host; no structural quantity moved.

**Goldens that moved, and why.** Ledger section 5.3 is exact. `gpu-forward-golden.jsonl` and
`moe-layer-forward-golden.jsonl` are byte-unchanged. `layer-forward-golden.jsonl` and
`model-forward-golden.jsonl` each rename one row for the token-cap lift and **add two**
(`*-tokens-seven-transcript` refused, `*-tokens-eight-no-transcript` admitted); no existing row's
bytes change. `decode-step-golden.jsonl` adds the three forced-build rows and changes seven existing
rows in one field, `graph.slot_high_water`, which is repair (2) above.

**Coding-baseline chain, re-recorded — reviewer B's blocker, discharged.** The capability changes
`Makefile`, one of the twenty recorded baseline artifacts, so the chain that shipped with R5D no
longer bound this head. (`scripts/build-ggml-shim` also changes but is **not** a recorded artifact
and does not itself invalidate the chain; an earlier draft of this record said it did.) The
identity-bound chain is now `e4548b1` → `6d1c152` → `1bbacaa` — clean source, immutable oracle
projection, finalization — with the pending measurement recorded on Linux (aarch64, kernel
6.11.11-linuxkit, Python 3.12.3) through the DinD wrapper, exactly as R5D's was. Exactly one of the
twenty artifact digests moved (`Makefile`); `.align-revision` is unchanged at `3a34febe` and the
twenty paths are identical. `gmake baseline-check` passes on Linux at the finalized head.

**Next actions, in order.**
1. `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke`, on the
   unchanged head. The diff touches `Makefile`, `scripts/build-ggml-shim`, and the goldens, so the
   classifier selects the executable row and the installed fresh-image profile; do not substitute a
   Docker skip or an ambient `DOCKER_HOST`.
2. Open the English pull request with the verification table, the review envelope, and the finding
   dispositions. It must be a **merge** commit: squash and rebase would make the three baseline
   commits unreachable from `main`.
3. The next capability is step 2 and the decode loop, which needs a write-back at column `n_past` —
   the one thing that makes the plane both a read and a write target in one graph.

**Deviations from the ledger, recorded rather than hidden.** Ledger section 10 is authoritative and
now carries all of them: the decode layer is **thirty-eight** rows and not thirty-six (10.1); oracle
C is computed by the runner rather than by the arm, though it is acceptance (10.2); there is
deliberately no `R6_ORACLE_SHAPE` and the seam's `R5_ORACLE_SHAPE` reaches the document unchanged
(10.3); the golden rows that moved and why (10.4); the deferred closure cells, now including the
external oracle-C chain the review recommended and why it is deferred (10.5); and the nine
re-implemented functions, **each diffed against its original with every divergence named**,
plus the 1,328-byte `model_forward.Outcome` this created (10.6).

**Open decision for the user, unchanged from the design.** Whether to extend the R2c patch to
`examples/debug/debug.cpp` so a decode step gets a byte-exact external logits reference. It would
close ledger risk 3 at the cost of a new patch digest, a cache-generation bump to `r2c-v3`, and
re-running the R2c qualification. R6 ships without it. It is also the honest route to making the
review's "drive the C chain externally" recommendation possible: the operand `llama-debug` needs is
a prompt **string** and the runner holds token ids, so an external chain today would have to guess
the decoded token's text.

**Numbering, re-checked at the merge with `main` `76246f3`.** Roadmap item **27** and Align Request
**49** are unchanged. `main` now carries roadmap items to **25** — `agent/r3-decode-residency`'s,
merged as PR #142 — and requests still to **46**. `agent/r5e-moe-model-prefill` is **not** merged
and still holds roadmap **26** and requests **47 and 48**, so those numbers are reserved rather than
free and this capability keeps 27 and 49. The roadmap records the reserved gap at item 26 in place.

## Merged checkpoint: R3-DECODE-RESIDENCY (2026-08-28)

PR #142 merged as `76246f3` on `main`. The publication and merge named in the next actions below
are complete; the rest of this record is unchanged.

Branch `agent/r3-decode-residency`, started from `agent/r2d-decode-locality-gate` at `d48bde0` and
**merged** with `main` `c21b9e4` (R2D PR #141, now merged) rather than rebased over it, so its
recorded commits stay reachable. It is the residency consumer of R2D's capture and closes the decode
half of the R3 roadmap gate. No design gate is triggered: no CLI verb, no exchanged document, **no
Align source change**, and no coordinated invariant.

**Current checkpoint. Implementation, the real-model run, one comprehensive review over two
independent reviewers, and the consolidated repair are complete and committed on the branch.**
`scripts/run-decode-residency-gate` is new and opt-in — no `Makefile` target, no aggregate, no CI,
the standing every R2c consumer has. It takes `scripts/run-decode-locality-gate`'s capture flag for
flag (40 prompts, `-n 16 --temp 0 --seed 42 -t 4 -fa off -ctk f32 -ctv f32 -nr -c 512`), derives one
`R2_ACTIVATION_TRACE` per transcript, deletes the transcript, admits the corpus with R2D's
`require_full_router_axes`, and runs `main --simulate-residency` **four** times at section 7.4's own
975,175,680 B budget: the **mixed** list as captured, a **decode-only** list with graph 0 projected
away, a **prefill-only** coverage control with the decode graphs projected away instead, and a
**head-4** stream-length control keeping only decode ordinals 1–4. The ordinals are kept in every
projection. The projections live in `scripts/residency_projection.py`, imported by
both the runner and `scripts/run-residency-sim-smoke`, so the arms the hosted owner proves against
the independent oracle are the arms the real-model runner replays.

The capture logic is still deliberately **duplicated** rather than factored into a shared helper —
the two runners differ in N/A prefixes, per-prompt side work, and post-capture admission, and
`run-decode-locality-gate` is merged and measurement-bearing — but the "flag for flag" claim is now
**enforced**: a `capture-identity` check in the hosted owner extracts the instrument invocation, the
corpus-identity block, and the transcript cap from both files and fails if they differ, and fails if
the extracted invocation stops containing the flags.

**The gate is met in the decode direction and the answer is narrower than the recorded one — and
the two control arms change what that is attributed to.** On the same 40-prompt corpus: mixed
104,960 demands over 832 token positions, decode-only 81,920 over 640, prefill-only 23,040 over 192,
head-4 20,480 over 160, slot coverage 1,000 per mille everywhere. `recent_reuse` beats `lru` by 59
to 238 per mille at 15/31/62/125 per mille of the expert footprint on the mixed and decode-only arms
and by 70 to 200 at 31/62/125 on head-4, and at 250 and 500 per mille **no candidate beats the
baseline at all** on any of the three — all `NO_POLICY_BEATS_BASELINE`, `recent_reuse_w2`
byte-identical to `lru`, `lfu` flipped from a 221-per-mille saving to 152/190/88-per-mille losses.
**But the prefill-only control is `BEATS_BASELINE` at that same 250-per-mille budget**: `lfu` 194
per mille, jackknife tested and stable at a 186-per-mille minimum, `recent_reuse_w32` clearing the
floor at 191. So section 7.4's 223-per-mille win **survives the coverage change** (six printed slots
to eight). **The head-4 arm excludes stream length as well**: at 20,480 demands, eleven per cent
*fewer* than the winning prefill-only arm, it is still `NO_POLICY_BEATS_BASELINE` with a gain of 0.
Two arms of comparable length at the same budget over the same corpus give opposite verdicts and
only the phase differs, so what removes the win is the presence of decode demands — not coverage,
not the working-set ratio, not length. The working-set explanation an earlier draft gave is measured
and **rejected**: the winning control arm sits at 2.14 working sets, the *identical* multiple the
losing mixed arm's own prefill positions sit at (the seven per cent is the distance to a decode
position's 2.00), and both are tighter than section 7.4's 2.86. *Why* frequency loses is **not**
settled: it is consistent with decode's more uniform routing, which `r2a-expert-trace.md` section
9.4 measures as small (4-per-mille entropy gap, up to 0.24 of it estimator bias, ~3 per cent mass
variance), so that is one candidate explanation and not a mechanism. What remains unseparated is
decode's routing statistics from a decode position's wider working set (sixteen layers against
fifteen). 476, 473, and 453 per mille of headroom stay uncaptured by every online candidate on the
three decode arms. Full record, limits, and mutation evidence:
`docs/specs/r3-residency-sim.md` section 8.

**Consequences recorded in the roadmap.** R4B's decode-corpus resume condition is **discharged
negatively** — the decode histogram is more uniform than prefill's (entropy 996) and no prefetch
degree pays on any arm, so hotness ordering and prefetch groups stay deferred as *measured and not
justified*; the only remaining resume path is R2b's stratified corpus. The roadmap now also records
that this negative is about hotness *layout*, not about frequency signal as such, because `lfu` does
win on the prefill-only stream. R6 is ordered **ahead** of a runtime expert-residency policy, and
the control arm strengthens rather than weakens that: the premise fails specifically on streams that
contain decode, which is what a runtime serves.

**Candidate contents.** `scripts/run-decode-residency-gate` (new), `scripts/residency_projection.py`
(new), six cases and two binding checks in `scripts/run-residency-sim-smoke`, one behaviour-neutral
`usedforsecurity=False` keyword in `scripts/run-decode-locality-gate` required by the
`capture-identity` check, `docs/specs/r3-residency-sim.md` section 8, the roadmap R3/R4B/R6
paragraphs and items 23/24/25, the developer-guide section, and this handoff update. **No Align
source change, no `Makefile` change, no aggregate membership change**; `gate-topology-check` passes
unchanged. `scripts/residency_oracle.py`, `src/residency_sim.align`, `src/main.align`, and
`eval/fixtures/residency-sim/sim-basic.golden.json` are all untouched. No intentional uncommitted
files beyond the candidate itself. Per-phase byte accounting is **deferred**: it would need
`R3_RESIDENCY_SIM` `schema_version: 2`, `RESULT_FIELDS` 7 → 9, and an oracle and golden rewrite, and
that is a design gate this capability does not need to answer its question.

**Review and repair.** One comprehensive review of the stable candidate at `eb38ecd`, two
independent reviewers over disjoint risks. Reviewer B (docs/governance) requested changes: 3 major,
5 minor. Reviewer A (scripts) requested changes: 2 major, 6 minor, plus two nits; 4 of 4 injected
mutants killed. All 18 were validated and **accepted**; none was rejected. They are repaired in one
consolidated commit together with the merge of `main` `c21b9e4`.

**The repair was materially more than a repair, and a final delta review was taken.** Reviewer B's
major 2 asked for a third arm or a demotion of the mechanism claim to a hypothesis. The third arm
was built and run, and it **refuted the reading the section had recorded**: the loss at 25 per cent
is not a coverage artefact and not a working-set artefact, it is decode. The final delta review
approved that repair with minors, of which the substantive one was that the section still asserted
a *routing-statistics* mechanism the arms could not separate from stream length. A **fourth arm**
(`decode_head4`) was therefore added and the whole gate re-run on the real model: it excludes length
too, and the mechanism claim is now stated as an intervention plus one candidate explanation.
Section 8.1–8.5, the roadmap item, the roadmap R3/R4B/R6 Japanese paragraphs, the developer guide,
and this record are re-worded to what the evidence supports. The runner gained two arms,
`graph_phases` assertions, partition and subset assertions, budget validation, an imported
projection module, and `jackknife_tested`; the hosted owner gained four cases and two binding
checks.

**Root-cause audit across the diff.** Every `ALIGN_LLM_*` read in `run-decode-residency-gate` is now
validated or has an explicit N/A path, `ALIGN_LLM_RESIDENCY_BUDGET` included. Every positional index
into a reported list is replaced by a name lookup (`by_policy` selects the `orders` block by its
`order` field), and the byte table is guarded so a malformed document reports the structural
findings instead of a `KeyError`. Every per-mille helper in the diff truncates toward zero as
`src/residency_sim.align` does rather than flooring, and the sweep share column prints the
document's own `per_mille_of_expert_bytes` instead of a truncated percent. Every statistic that can
be vacuous is labelled: `jackknife_tested` separates the untested initial zero from a measured fold,
the sweep header states that its rows carry no jackknife, and a mutation audit found that the three
arms' `single_token_first_graph: 0` was itself vacuous — no case produced that label — which
`sim-renumbered-decode-only` now fixes.

One instance of the same env-validation class is recorded and **not** repaired here, because it
belongs to a merged capability outside this diff: `scripts/run-expert-locality-gate` reads
`ALIGN_LLM_LOCALITY_PROMPT_COUNT` without validating it, so `=0` there still yields an empty
measurement. It remains a follow-up for that runner's owner. The pre-existing positional
`document["orders"][0 if ...]` in `scripts/run-residency-sim-smoke`'s own `by_policy` is left as is:
every caller runs after `check_case` has compared the whole document to the independent oracle,
which fails first on any order the index could mis-select.

**Next actions, in order.** Publish the English pull request with the four-arm measurement and the
review envelope, monitor required checks, merge, and then start the next eligible Track B roadmap
item. The comprehensive review is closed: two independent reviewers at `eb38ecd` (18 findings, all
accepted and repaired in `403a4a3`), one final delta review of that repair (approve with minors),
and one narrow repair of those minors, which added the head-4 arm and re-ran the gate. No further
full review is required; the repair narrows a recorded claim rather than expanding scope.

**Latest durable verification.** At the repair head, on this macOS arm64 host with the managed Align
`3a34febe` toolchain:

```text
gmake build                          PASS
gmake residency-sim-smoke            PASS, 2 model IRs, 27 traces, every policy at every sweep
                                     budget against the independent oracle, both CLI forms, the
                                     golden, determinism, the section 2.6 error corpus, and the
                                     six new cases and two binding checks; 8 of 8 mutants killed,
                                     including one that survived before `sim-renumbered-decode-only`
                                     was added and both mutations of the head-4 predicate
gmake expert-trace-smoke             PASS, 108 fixtures / 17 error codes, both aggregators
gmake format-check                   PASS
gmake gate-topology-check            PASS
git diff --check                     clean
scripts/run-decode-residency-gate    MEASURED, exit 0, four arms; mixed, decode-only, and head-4
                                     NO_POLICY_BEATS_BASELINE and prefill-only BEATS_BASELINE at
                                     the requested budget; 531.7 s for 40 captures. Run four times
                                     on this host, the last at this exact head and the only one
                                     carrying the head-4 arm: every line the first three arms print
                                     is identical across all four runs except `elapsed` (509.4 s
                                     under concurrent load, 261.0 s, 219.4 s, 531.7 s). Elapsed is a
                                     load-dependent diagnostic and nothing rests on it
```

`gmake expert-trace-smoke` is run because the repair touches `scripts/run-decode-locality-gate`. The
change is one `usedforsecurity=False` keyword; the corpus identity that runner prints was compared
before and after and is byte-identical (`expert-locality-v1.txt d7fff23f5a1d4f6237e6f848f3318d8b
877 40`), so R2D's recorded measurement is unaffected and was not re-run.

`gmake residency-sim-smoke` was **not** run under a read-only `python:3.12-slim` container: it is
not python-only, needing the built `main` for `--model-ir`, `--expert-trace`, and
`--simulate-residency`. Hosted CI already owns that graph.

## Merged checkpoint: R2D-DECODE-LOCALITY-GATE (2026-08-28)

PR #141 merged as `c21b9e4` on `main`. The exact-head preflight, publication, and merge named in
the next actions below are complete; the rest of this record is unchanged.

Branch `agent/r2d-decode-locality-gate` starts from `main` `89d8721`, the merge of R2c PR #140, and
is merged with `main` `e312bd7` (R5D PR #139) rather than rebased over it, so its recorded commits
stay reachable. It is the first measurement consumer of the patched instrument and it closes the
decode half of the R2 roadmap gate. No design gate is triggered: no CLI verb, no exchanged
document, and no coordinated invariant across three or more modules.

**Current checkpoint.** Implementation, the real-model run, one comprehensive review over two
independent reviewers, and the consolidated repair are complete and committed on the branch. No
intentional uncommitted files. `scripts/run-decode-locality-gate` captures one prompt-plus-decode
transcript per prompt with `-n 16 --temp 0 --seed 42` on top of the R2 flags, derives one
`R2_ACTIVATION_TRACE` per transcript, reads one entry-embedding token fingerprint per observed
position, deletes the transcript, and pools the documents into three verdicts under one rule.
Adjacency is over the sequence rather than inside a graph, because a decode graph holds one token;
the arms are `prefill@8` (all eight router slots), `decode@8` (consecutive decode graphs), and the
prompt-to-generation `boundary` pair. The aggregation lives in a new full-axis path in
`scripts/expert_locality_gate.py` (`require_full_router_axes`, `entry_token_fingerprints`,
`aggregate_decode`, `DECODE_CAVEATS`/`decode_caveats`); the historical compact path and its refusal
are untouched.

**The gate is met in the decode direction.** On the same 40-prompt corpus against
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 40 prefill and 640 decode graphs over 832 token positions,
252.9 s at the repair head and 189.8 s before it — elapsed is a load-dependent diagnostic and every
recorded number is identical across the two runs: all three arms `LOCALITY` against a 125 per mille
null — `prefill@8` 371 per mille, cluster-robust [338, 405], design effect 23.274; `decode@8`
**447** per mille, cluster-robust [426, 468], design effect 35.375, 16 of 16 layers clearing;
`boundary` 364 per mille, cluster-robust [325, 405]. Greedy decode's measured token-repetition rate
is 51 per mille and excluding those pairs leaves the decode arm at 429 per mille, cluster-robust
[408, 451], still `LOCALITY`. An optional 32-step, 8-prompt subset arm reaches 504 per mille and
does not weaken any verdict. The full record, its limits, and the mutation evidence are
`docs/specs/r2a-expert-trace.md` section 9; section 8's prefill gate is untouched and its 286 per
mille is not rewritten.

**Defect repaired in passing.** `scripts/run-r2c-instrument-qualification`'s `parse_trace` raised
on any nonzero status, so the parser-refusal diagnostic below it was unreachable:
`main --expert-trace` exits 2 on `status: "error"` and still writes the document naming the code
and detail. `command()` now takes an `accept` set, `parse_trace` passes `(0, 2)`, and a new
`parse-trace-statuses` case in `scripts/run-r2c-instrument-smoke` proves the refusal diagnostic, an
accepted document, and that every other nonzero status is still a process failure. Without the fix
that case reports `error: code 2`.

**Candidate contents.** The runner, the aggregation path, the qualification fix, the hosted
aggregator cases in `expert-trace-smoke` and the `parse-trace-statuses` case in
`run-r2c-instrument-smoke`, `docs/specs/r2a-expert-trace.md` section 9, the roadmap R2 and item
22/24 updates, the
developer-guide section, and this handoff update. **No `Makefile` change**: like
`run-expert-locality-gate` and `run-r2c-instrument-qualification`, this runner joins no target and
no aggregate, so aggregate topology and the canonical coding baseline artifact set are unchanged.

**Review and repair.** One comprehensive review of the stable candidate at `5a7ace7`, two
independent reviewers over disjoint risks. Reviewer B (docs/governance) requested changes: 1
blocker, 1 major, 4 minor. Reviewer A (executable diff) approved with 7 minor findings. All 13 were
validated and **accepted**; none was rejected. They are repaired in one consolidated commit on this
branch, together with the merge of `main` `e312bd7` (R5D PR #139) that the blocker required. The
repair adds no capability and changes no measured number: `threshold_per_mille` is a reported
diagnostic corrected from the floored to the ceiled quotient (187 -> 188) in both the decode and
the merged compact gate, admission now runs before the router-shape read,
`ALIGN_LLM_LOCALITY_PROMPT_COUNT` is range-checked like `ALIGN_LLM_DECODE_STEPS`, the short-context
caveat is bound to the measured corpus rather than hard-coded, the fingerprint arm names the prompt
and reason it could not be read, and five new owner cases pin the materiality boundary from both
sides, correction 20's token-reduced layer at the real 16-layer shape, a chain gap in the
working-set runs, a refused document's own `error_code`, and the fingerprint reader's block
terminator.

**Root-cause audit across the diff.** Every `ALIGN_LLM_*` read in `run-decode-locality-gate` is now
validated or has an explicit N/A path; every new aggregate function runs behind
`require_full_router_axes`; and the only other per-mille threshold helper — the merged compact
gate's — carried the same off-by-one and is corrected with it. One instance of the same class is
recorded and **not** repaired here, because it belongs to a merged capability outside this diff:
`scripts/run-expert-locality-gate` also reads `ALIGN_LLM_LOCALITY_PROMPT_COUNT` without validating
it, so `=0` there still yields an empty measurement. It is a follow-up for that runner's owner.

**Next actions, in order.** Run exact-head preflight with the owner commands below, publish the
English pull request with the measurement and both review envelopes, monitor required checks, and
merge. A further comprehensive review is not required: the repair is confined to the recorded
findings, adds no behaviour beyond the four named guards, and changes no measured result.

**Latest durable verification.** At the repair head, on this macOS arm64 host with the managed
Align `3a34febe` toolchain:

```text
gmake build                       PASS
gmake expert-trace-smoke          PASS, 108 fixtures / 17 error codes, both aggregator units,
                                  14 of 14 mutants killed by the decode unit alone
gmake format-check                PASS
git diff --check                  clean
scripts/run-decode-locality-gate  MEASURED, three LOCALITY verdicts, 252.9 s; every recorded per
                                  mille, interval, count, and verdict identical to the pre-repair
                                  run (section 9.2). Elapsed is a load-dependent diagnostic; the
                                  pre-repair run took 189.8 s on the same host
scripts/run-r2c-instrument-smoke  PASS, 55 contract groups, on Docker linux/arm64
```

`scripts/run-r2c-instrument-smoke` fails on this macOS host in its pre-existing `cache-contract`
case, which asserts `HOME=/home/test` resolves to `/home/test/.cache/...` while macOS resolves
`/home` through a firmlink to `/System/Volumes/Data/home`. The failure reproduces unchanged on
`main` `89d8721` and is environmental, not a regression; the Docker run above is the evidence for
the changed cases.

## Merged checkpoint: R5D-MOE-LAYER-FORWARD (2026-08-28)

PR #139 merged as `e312bd7` on `main`. The exact-head preflight, publication, and merge named
in the next actions below are complete; the rest of this record is unchanged.

Branch `agent/r5d-moe-layer-forward`, rebased onto `main` `95c47e7` (the merged R3-RESIDENCY-SIM,
PR #135, which sits on PR #136's GCC 14 shim fix, C8's optional targeted stage at PR #134 — a
parallel Codex session's change, not this session's work — and the merged MOE-PREREQ-DISCHARGE at
PR #133), and then **merged** with `main` `1b11245` — PR #138, a parallel Codex session's R3
qualification-prerequisite follow-up — rather than rebased over it, so this branch's recorded
baseline-chain commits stay reachable. The branch is `a85e1fc` (design ledger), `7886cee`
(implementation), `a2e2748` (review repair), and the reconciliation and baseline commits on top;
before the rebase the first three were `3cb8d59`, `e584849`, and `aaedf26`, and the review record on
the pull request names the pre-rebase heads the reviewers read. Design ledger `docs/specs/r5d-moe-layer-forward.md` is authoritative and
now carries the implementation's corrections C1–C22 and the shipped arm's measured section 7.
**The capability is implemented and committed**: `src/layer_olmoe.align` and
`src/moe_layer_forward.align` are new; `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`,
`scripts/layer_forward_fixture.py`, `src/ggml_ffi.align`, and `src/ggml_spike.align` are extended;
`scripts/run-moe-layer-forward`, `scripts/sweep-moe-layer-forward-excerpt.py`,
`scripts/moe-layer-forward-golden.jsonl`, and `eval/fixtures/olmoe-blk0-6tok.txt` are new. No
intentional uncommitted files.

**What it does.** R5's second gate stage for a **routed** OLMoE layer: one prefill of at most six
tokens through `blk.0`, computed by ggml over attention weights and only the routed experts' planes
held in Align-owned buffers, checked against llama.cpp's own numbers. Measured by the shipped arm on
the real model (ledger section 7.1): the routed layer reads **101,990,400 of 261,095,424** expert
bytes (390,625 ppm, 75 of 192 planes, 25 block reads); the self-reference oracle is 46 of 46
byte-identical; the routing-identity oracle is `MATCH` at 36 of 48 printed ids plus the exact sum
1,471; the transcript oracle is `PASS`, 26 nodes, 2,376 elements, max |Δ| 0 ten-thousandths.
**Required microbenchmark B is 5.64 ms** (phase A 1.452 + phase B 4.185, warm means of five) — the
probe's 9.4 ms timed a cold graph per arm and the shipped arm's contractual warm-up is what section
3.5 already required. The residency win is a **decode-time property**: 39% of the layer's expert
bytes at six prefill tokens, 12.5% at one, 73% at eighteen.

The boundary change is five new FFI symbols (`argsort`, `mul_mat_id`, `view_2d`, a 3-D
stacked-tensor constructor, a 2-D i32 constructor) plus one widened existing symbol
(`soft_max_ext` with a null mask). **No new Align capability request was needed.** Four existing
requests gain R5D as a client, all non-blocking: Requests 45 and 46 (R3's, renumbered from 44 and 45
when PR #134 took Request 44, and now on `main` with the merged PR #135) and Requests 37 and 42.
Ledger section 5.5 named all four as to be appended at reconciliation, and the reconciliation commit
appends R5D's client evidence to each of the four register entries.

**Review.** One comprehensive review of the stable candidate, two independent reviewers over
disjoint risks. Reviewer A (source) **approve** with 2 medium and 2 low findings; reviewer B
(governance/record) **approve after repair** with 2 med-high, 3 medium, and 6 low findings. All
fifteen were validated and **accepted**, and all fifteen are repaired in the consolidated repair
commit on this branch; ledger corrections C12–C21 record the contract changes, and
`r5b-model-prefill-forward.md` C26 and `r5c-metal-prefill.md` C22 record the retired
`layer-forward-smoke` and `check-per-unit` acceptance targets. No finding was rejected. The repair
adds one behavioural refusal (a claim plane whose `ggml_type` is not its role's first, reproduced
before and after) and one hosted case, `moe-engine-claim-type-mismatch`; every other change is a
record, a comment, or an assertion.

**Verification, re-run in full at the rebased head against the managed `3a34febe` compiler** that
PR #134 pinned, on this host with `gmake` and
`LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib`:

```text
gmake check                    ok: checked 31 unit(s) per-unit (137 s)
gmake build                    ok
gmake ggml-spike               ok, stub shim and real shim
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases; olmoe 22 blocks /
                               69 members, 16 ExpertBlocks, claim surface PASS
gmake layer-forward-smoke      PASS x3, byte-identical, 28 / 27 / 26 s - 8 no-document and 75
                               documented R5A/R5B cases, 59 model-forward, 28 gpu-forward, and
                               R5D's 8 no-document / 78 documented cases, 29 codes, three oracles
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,302 assertions
gmake residency-sim-smoke      PASS - PR #135's owner, unchanged by this branch
gmake gate-topology-check      PASS
gmake format-check             PASS; gmake fmt leaves no diff; git diff --check clean
```

**No golden byte changed at the new pin.** The R5A, R5B, R5C, R5D, and ggml-spike golden documents
are byte-identical under `3a34febe`, so the pin adoption needs no correction row of its own.

**Baseline chain, re-recorded.** This branch's `Makefile` and `.gitattributes` changes invalidate
the chain that shipped with R3-RESIDENCY-SIM, so the identity-bound chain is re-recorded here as
`7c4830a` -> `c6cee0c` -> `09de0fd` (clean source -> immutable oracle -> finalization), measured on
Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) and checked there with `make baseline-check`
ending `baseline chain: PASS`. Two of the twenty recorded artifacts changed against the R3 chain:
`Makefile`, which gains the opt-in `moe-layer-forward-qualification` target and no
`HOSTED_CHECK_TARGETS` member, and `.gitattributes`, which marks the new olmoe excerpt `-whitespace`.
`.align-revision` is `3a34febe` on both chains, because R3 already adopted PR #134's move. The other
eighteen hashes are unchanged and the twenty paths are identical. The pull request must merge with a
merge commit; squash and rebase merges would make these commits unreachable.

**Next actions, in order.** (1) `python3 scripts/pre-pr --owner-test moe-layer-forward -- make
layer-forward-smoke gate-topology-check` under the installed profile at the exact head, then publish
and merge. Note the preflight lane: R5D adds the `moe-layer-forward-qualification` Makefile target,
so the classifier selects the **executable** row and the installed profile — publication needs the
**fresh-image (Docker-in-Docker)** preflight, not the documentation lane. `HOSTED_CHECK_TARGETS`
membership is unchanged, so `make ci` is *not* selected. (2) After merge, refresh `main` and start
the next eligible roadmap item; R5's deferred microbenchmark C and R6 both wait on pending decisions
(d) and (c) below.

## Merged checkpoint: R3-QUALIFICATION-PREREQUISITES (2026-08-28)

Branch `fix/r3-qualification-prerequisites` merged as PR #138, merge commit `1b11245` on `main`,
authored by a **parallel Codex session** rather than by the session that produced R3 and R5D. It
started from `main` `95c47e7`, the merge of R3 PR #135. A second R3 implementation was independently completed before that merge became visible;
its duplicate PR #137 is closed and will not be integrated. Its final review nevertheless exposed
one root-cause class that applies to the merged qualification: the wrapper generated a Model IR but
did not validate it or the requested budget until after every prompt had invoked the external
instrument, so a locally knowable defect could consume up to 40 600-second prompt runs.
Published and merged as PR #138; R5D merges it in rather than rebasing over it, so this branch's
recorded baseline-chain commits stay reachable.

## Merged checkpoint: R2C-DECODE-INSTRUMENT (2026-08-28)

PR #140 merged as `89d8721`, authored by a **parallel Codex session** rather than by the
session that produced R3 and R5D.
authoritative.

Branch `agent/r2c-decode-instrument` started from `main` `1b11245`, the merge of R3 follow-up
PR #138, and discharged decision (c): a source build of llama.cpp at exact commit
`bb4caa7540188872173c44d161602d9271386413` with the minimal R2c instrument patch. It unblocks R6
and therefore R7-R9, and the active R2D capability above is its first measurement consumer. R5
microbenchmark C remains independently blocked on Align Request 41.

**What it delivers.** The triggered design ledger is `docs/specs/r2c-decode-instrument.md`
(`d8e4818`); the reviewed implementation head is `5f1eb3e`, the first consolidated review repair is
`46432de`, and the final review's three accepted findings are repaired at `76400f5`, the merged
branch tip.
`.llama-revision` and the 2,170-byte patch pin the external source and
two-file diff. The `r2c-v2` managed builder has completed a fresh CPU build with Metal and
llama/ggml shared libraries disabled, verified build 10566 / commit `bb4caa7`, and emitted a
schema-1 attestation. The patch preserves the omitted/nonpositive `-n` one-prefill behavior, emits
up to `-n` one-token decode graphs with common sampling and EOG stop, and prints every
`ffn_moe_topk` axis while leaving all other debug tensors at three-plus-three.

The source-to-client check found and corrected one pre-existing R2A contradiction: prose said a
full-axis R2c transcript needed no parser change, but `src/expert_trace.align` accepted exactly six
values whenever an extent exceeded six and derived truncation flags from extent. Schema 1 now
admits exact compact or full forms based on the ellipsis actually observed. Existing compact
documents remain unchanged; the independent generator now owns full slot/token success and eight
malformed/mixed/non-router refusals. `make check`, `scripts/run-r2c-instrument-smoke` (54 contract
groups at this merge; R2D above adds one), and `scripts/run-expert-trace-smoke` (108 fixtures, 17 error codes) pass. The compiled dense
qualification passes through the product parser: omitted, zero, and negative `-n` each produce one
prefill graph, while `-n 2` produces one prefill plus two decode graphs. The real OLMoE half also
passes: three graphs including decode, 48 full-width groups, 384 selections, and full-axis extent
eight. Independent parity reports 16 layers, 64 experts, top-8, 488 retained selections, and the
known token-reduced final layer. No model or transcript is committed.

**Review envelope.** Host-native Codex (`gpt-5.6-sol`, xhigh) first reviewed
`5f1eb3e7614a8a8e1cfd4ee13e8b31db3b8c26a8` against base tip and merge base
`1b11245cee98bf3bba8ab874683206b4243d1761`. Verdict: four valid findings — two P1 and two P2 — all
accepted, none rejected. That repair compares staged and unstaged tracked source to `HEAD`; disables
Metal and advances the cache recipe to `r2c-v2`; requires an applicable router extent above six;
and downloads the tiny model to a hash-validated temporary sibling before atomic rename. The same
pass corrected the remaining compact-only normative prose in R2A. Deterministic owners and fresh
dense/MoE materialization pass after repair.

The required final comprehensive review covered `46432ded7e8d60d8bca4f4d33fdc80a252099aae`
against the same base tip and merge base. It found three further valid findings, all accepted and
none rejected: R2/R3 historical replays still changed from six to eight observed slots under the
R2c instrument; explicit/XDG/HOME cache roots could resolve inside the checkout; and router axis 2
could change compact/full print form between groups or blocks. The final repair makes historical
gates share an exact compact-axis admission check, rejects lexical and symlink-mediated checkout
cache containment, and settles the axis-2 form across every applicable group/block with a new
`R2_ROW_COUNT` fixture. The repair is limited to those recorded findings and their plan/owner
evidence, so the workflow requires repair-delta inspection and affected owner verification rather
than a third comprehensive review. Both are complete.

**Candidate contents.** The pin, patch, managed builder, deterministic smoke, focused qualification,
R2A parser/source oracle changes, R2A specification correction, roadmap and developer-guide
changes, and this handoff update belong to this capability. `Makefile` and aggregate topology are
intentionally unchanged, so the canonical coding baseline artifact set is unchanged.

**Merge.** Exact-head preflight, publication with both review envelopes and finding dispositions,
and merge are complete; nothing remains on this capability. R5D merged it in rather than rebasing
over it, so that branch's recorded baseline-chain commits stay reachable; `Makefile` and the
canonical baseline artifact set are unchanged by it, so R5D's chain still binds.

**Durable verification at merge.** On WSL2 x86_64 with GNU 14.2.0 and the managed Align
`3a34febe` toolchain:

```text
scripts/run-r2c-instrument-smoke                         PASS, 54 contract groups
make expert-trace-smoke                                  PASS, 108 fixtures / 17 error codes
make residency-sim-smoke                                 PASS, oracle and admission owners
make check                                               PASS, 31 units per-unit
scripts/run-r2c-instrument-qualification                 dense PASS; MoE PASS
scripts/run-expert-trace-parity                          MoE PASS; model read-only proof PASS
scripts/llama-eval-callback-toolchain verify             bb4caa7540188872173c44d161602d9271386413
scripts/llama-eval-callback-toolchain attest instrument  r2c-v2, instrument sha256 2911b1ffed36...
```

## Merged checkpoint: R3-RESIDENCY-SIM (2026-08-28)

PR #135 merged as `95c47e7` after all three GitHub checks passed. Design ledger
`docs/specs/r3-residency-sim.md` remains authoritative. Implementation, real-model qualification,
review, publication, and merge are complete.

**What it delivers.** The R3 roadmap gate, measured. `main --simulate-residency` replays the demand
stream implied by a set of real `R2_ACTIVATION_TRACE` documents against ten expert-residency cache
policies in four families — `lru`, `lfu`, three fixed-window `recent_reuse`, two `topk_prefetch`
degrees, plus the `null` / `compulsory` / `belady` references — at a nine-point budget sweep, with a
leave-one-document-out jackknife over the corpus and a headroom measure against the miss-optimal
offline reference, and emits one `R3_RESIDENCY_SIM` (`schema_version: 1`) document. The design gate
triggered on three counts: a new public CLI verb, a new versioned exchanged format, and a coordinated
invariant across three modules plus the `Makefile`.

**The gate is met.** On the real 40-prompt corpus (`eval/prompts/expert-locality-v1.txt`, md5
`d7fff23f5a1d4f6237e6f848f3318d8b`) against `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`: a stream of
17,280 demands over 938 distinct `(layer, expert)` keys of 1,024, 192 token positions, slot coverage
750 per mille. At the requested budget of 975,175,680 B (250 per mille of the 3,900,702,720 B expert
footprint), verdict `BEATS_BASELINE` — `recent_reuse_w32` fetches 26,033,848,320 B against the `lru`
baseline's 33,532,231,680 B, 223 per mille fewer against a 50-per-mille materiality floor, with a
40-fold jackknife minimum gain of 213 per mille (stable) and 574 per mille of headroom still left to
the offline optimum. Across the sweep: `BEATS_BASELINE` at 1/3/6/12/25 per cent,
`NO_POLICY_BEATS_BASELINE` at 0 and 50 per cent, `NO_HEADROOM` at 100 per cent. Top-k prefetch buys
hits and pays for them with more bytes than it saves: under the shipped MRU insertion rule
`topk_prefetch_k1` issues 219 prefetches of which 102 are later hit (465 per mille) and
`topk_prefetch_k8` issues 3,332 of which 1,590 are (477 per mille), and no `topk_prefetch` cell is
below `lru` at any budget. Roadmap section R3's other three policies — score-based, impact-driven
prefetch, CPU fallback — are deferred with named prerequisites (a router-weight column R2A does not
capture; R4.5's and R5's measured transfer costs; R5's microbenchmark) rather than simulated against
invented constants.

**Committed on the branch.** Nothing is uncommitted. After the rebase onto `4f01553` the branch is
`4951ff6` (design ledger), `424a516` (implementation), `a22f839` (review repair), `2e058f7` (final
review repair), and the reconciliation and baseline commits on top; before the two rebases the first
four were `198850b`, `ff4f76d`, `c7cfe1a`, and `967aadf`, and the review record on the pull request
names the pre-rebase heads the reviewers read. Two prerequisites the branch once carried are now in
`main` and are no longer part of this diff: the merged R2 wave's corrected `src/expert_trace.align`
and its four owners, without which every real OLMoE capture fails `R2_TOKEN_COUNT` on layer 15's
token-reduced `ffn_moe_topk`. **The `Makefile` changes** (`residency-sim-smoke`, a new
`HOSTED_CHECK_TARGETS` member, and `residency-sim-qualification`, in no aggregate), so the classifier
selects executable preflight and the baseline commit chain has to be re-recorded on this branch.

**Integration with PR #134 and PR #136.** C8-OPTIONAL-TARGETED-STAGE merged while this branch was
in publication, and GCC14-FP-CONTRACT-PORTABILITY (PR #136) merged after it — the ggml shim's
Clang-only `#pragma STDC FP_CONTRACT OFF` under GCC 14.2 and `-Werror`, a pre-existing hosted-check
failure this capability's own preflight surfaced; both are merged into this branch. PR #134 moved `.align-revision` from `4b515f8d` to **`3a34febe`** (Align PR #892, its own
Request 44). That renumbered this capability's two register entries — R3's requests are now
**Request 45** (the compiler soundness defect) and **Request 46** (the `borrow mut` array gaps) —
and it invalidated both the first preflight stamp and the first baseline chain, because
`.align-revision` is itself one of the twenty recorded baseline artifacts. Every owner below is
re-run against the managed `3a34febe` compiler; nothing in R3's own behaviour changed with the pin.

**Review envelope.** Two complementary reviewers covered explicitly disjoint risks at the pre-rebase
implementation head `ff4f76d` (`424a516` after the rebases): reviewer A the Align source and the
simulation semantics (1 blocker, 1 major, 4 minor, 1 observation), reviewer B the governance,
contract, and verification surface (1 high, 3 medium, 5 low). **All fourteen findings were accepted**,
none rejected, and all are repaired in one consolidated commit (`c7cfe1a`, `a22f839` after the
rebases), recorded as items 16 to 23 of the ledger's correction register. Two changed shipped
behaviour rather than prose: an `ExpertBlock` with `byte_size: 0` took `SIGABRT` through a
`resident_list` overrun and is now refused with `R3_EXPERT_BLOCK_SIZE`, and `best_policy` could name
a jackknife-**unstable** candidate beside `jackknife_stable: true` and now names the qualifying one.
Six hosted cases and five error-code cases were added, and the prefetch insertion rule is now
specified as MRU — which moved only the two `topk_prefetch` rows and changed no verdict, sweep row,
or non-prefetch policy on the fixtures or on the real corpus. The final review at `c7cfe1a` is
**approve** with five documentation-only findings, all repaired in `967aadf` (`2e058f7` after the
rebases); that repair is documentation-only apart from the smoke's new explicit-template B1
self-check, so no further comprehensive review is required. The reconciliation commits onto the
merged MoE prerequisites and onto PR #134 are documentation-only.

**Verification.** Durable owner evidence at the rebased head, on this macOS host with the recorded
Homebrew `LIBRARY_PATH` and the `CARGO` wrapper the managed `3a34febe` build needs
(`docs/align-development.md`):

```text
gmake check                    ok: checked 31 unit(s) per-unit
gmake build                    ok
gmake residency-sim-smoke      PASS x3, byte-identical - 2 model IRs, 23 traces, every policy at
                               every sweep budget in both orders against the independent Python
                               oracle, both CLI forms, the golden, determinism, the section 2.6
                               error corpus, and CLI arity/isolation
gmake expert-trace-smoke       PASS - 98 fixtures, 17 error codes
gmake model-ir-smoke           PASS - 49 qwen, 31 gpt-oss, 29 olmoe, 62 R0 fixtures re-run
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases; olmoe claim surface PASS
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,300 assertions
gmake verify-loop-smoke        PASS - PR #134's schema-v2 owner, unchanged by this branch
gmake gate-topology-check      PASS
gmake format-check             PASS; gmake fmt leaves no diff; git diff --check clean
```

The focused qualification, on the host that holds the models (MEASURED, in no aggregate):

```text
gmake residency-sim-qualification  BEATS_BASELINE - the numbers above; 40 captures in 55.7-64.1 s
                                   across three post-repair runs, every transcript deleted after
                                   conversion
```

**Measurement.** This is a policy claim about the named MoE model and this corpus, not a platform or
throughput claim. It compares fetched bytes only; elapsed time is printed as a diagnostic. The stream
is prefill-only, replayed in decode order because decode is the regime being modelled and not because
decode was observed; the instrument prints six of eight router slots; the corpus is 40 independent
prompts of at most six tokens, so cross-prompt reuse carries most of the cache pressure. Read the
result as "across a session of many short requests, frequency-aware residency beats recency", not as
"within a generation, expert reuse is high".

**Baseline chain, re-recorded.** The `Makefile` change, plus PR #134's `.align-revision` move that
this branch adopts, invalidate the chain that shipped with C8-OPTIONAL-TARGETED-STAGE, so the
identity-bound chain is re-recorded on this branch as `ec5ca39` -> `e729b68` -> `4bf5976` (clean
source -> immutable oracle -> finalization), measured on Linux (aarch64, kernel 6.11.11-linuxkit,
Python 3.12.3) and checked there with `make baseline-check` ending `baseline chain: PASS`. Three of
the twenty recorded artifacts changed: `.align-revision` (`4b515f8d` -> `3a34febe`, PR #134's, adopted
unchanged), `Makefile`, and `src/main.align`, the latter two this capability's own. The other
seventeen hashes are unchanged and the twenty paths are identical. PR #135 merged with merge commit
`95c47e7`, preserving the recorded source, oracle, and finalization commits.

**Align capability requests.** Implementation added Requests 45 and 46 (filed as 44 and 45 before
PR #134 took 44), both `PROPOSED`, non-blocking, and shipped around with documented workarounds.
**Request 45 is priority high**: a compiler soundness defect, where the region checker accepts a move
of a Move-typed field out of a `json.decode`d record through a two-hop field-access chain with no
diagnostic and the built program corrupts the heap at run time on the decoded record's recursive
`Drop`; the shipped fix is one `.clone()`. Request 46 is two related array-shape gaps
(`borrow mut array<T>` loop invalidation, and no element assignment through an array field). R3 also
strengthened Requests 21, 23, and 26 with new client evidence.

## Merged checkpoint: MOE-PREREQ-DISCHARGE (2026-08-28)

Branch `agent/moe-prereq-discharge` merged as PR #133 at `35a0df6`, preserving its recorded
baseline chain with a merge commit. Design ledger `docs/specs/moe-prereq-discharge.md` remains
authoritative. Implementation, review, publication, and merge are complete.

**What it delivers.** The per-expert half of the R4 and R4.5 gates, measured on the real olmoe
model rather than on the synthetic corpus. Two verdicts stop being constants and become rules over
the block set the run measured:

- `scripts/run-alignpack-qualification` reports the container's `ExpertBlock` improvement —
  1,024 blocks, 3,072 -> 1,024 ranges, 165,368,823,808 -> 3,900,702,720 span bytes,
  42,394,624 -> 1,000,000 ppm, 0 -> 1,024 of 1,024 contiguous;
- `scripts/run-ggml-spike` selects both arms by `role_id` out of the pack document it just wrote
  and computes real expert claims: all three members of the first `ExpertBlock` and member 0 of the
  last (block 1,056, plane 63 of 64), every one `EXTERNAL`, `IDENTICAL`, and bit-identical to the
  same plane read from the original GGUF.

Admitting the claim form required `R4_5_EXTERNAL_BUFFER` `schema_version: 2`, the split of step 7
into 7a (the slice pair) and 7b (the shape by form), and the new `R4_5_SLICE` code — the shipped arm
had refused a real expert claim with `R4_5_SHAPE`, detail `n_dims[3]`, so R4.5's own claim that the
CLI already addressed an `ExpertBlock` with no new surface is refuted and removed. R4's expert
hotness ordering and prefetch groups, and R4.5's GPU expert arm and discrete-VRAM half, stay
deferred and are unchanged.

**Committed on the branch.** Nothing is uncommitted. After the rebase onto `e15e3d3` the branch is
`4656d88` (design ledger), `eed850e` (implementation), `4bf25b8` (review repair), `0dd4ea8` (the
developer guide, which still described both qualifications as they were before this capability
changed them), and the reconciliation and baseline commits on top; the first three were `49f8e4c`,
`ee041a7`, and `5015daf` before the rebase, and the review record below names the pre-rebase head it
read. **The `Makefile`
changes** — `ggml-spike-smoke` gains a `build` prerequisite, because its claim cells are taken from
a container `main --pack` wrote — so the classifier selects executable preflight and the baseline
commit chain has to be re-recorded on this branch.

**Review envelope.** One comprehensive reviewer covered the whole diff at the pre-rebase
implementation head `ee041a7` (`eed850e` after the rebase): verdict **approve**, eight findings —
four minor, two low, two nits. **All eight were accepted**, none rejected, and all are repaired in
one consolidated commit on top of it (`4bf25b8`). The repair is narrow — a reclaim pattern, a
detail token, two documentation corrections, one added qualification run with its digest, a report
count, one assertion strengthened from a prefix to exact lines, and named refusals in the selector —
so it does not trigger a second comprehensive review, and the reconciliation commit onto the merged
R1C is documentation-only.

**Verification.** Durable owner evidence at the rebased head, on this macOS host with the recorded
Homebrew `LIBRARY_PATH` (`docs/align-development.md`):

```text
gmake check                    ok: checked 30 unit(s) per-unit
gmake build                    ok
gmake ggml-spike               ok, stub shim and real shim
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases; olmoe 22 blocks /
                               69 members, 16 ExpertBlocks, n_expert 8, claim surface PASS
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,298
                               assertions; qualification-verdict MoE PASS and dense N/A
gmake model-ir-smoke           PASS - 49 qwen, 31 gpt-oss, 29 olmoe, 62 R0 fixtures re-run
gmake expert-trace-smoke       PASS - 98 fixtures, 17 error codes
gmake layer-forward-smoke      PASS - 59 + 28 documented cases, three oracles
gmake gate-topology-check      PASS
gmake format-check             PASS; gmake fmt leaves no diff; git diff --check clean
```

Both focused qualifications, on the host that holds the models:

```text
gmake alignpack-qualification  PASS (olmoe) - identity, sequential read, and the MoE verdict above
gmake ggml-spike-qualification PASS (olmoe) - dense + three expert claims + the last plane;
                               1 dense, 3 expert, 1 last-plane digest checked
                               PASS (qwen2) - dense arm, expert arm N/A, 1 dense digest checked
```

**Consequence.** R3 residency simulation may now be reconciled onto the merged MoE result and
implemented after the bounded C8 re-entry. R2b's corpus-wide stratification consumes the merged
locality gate's corpus and aggregator.

**Measurement.** The layout numbers are a claim about this container on this named model, not a
platform or throughput claim; neither qualification asserts an elapsed bound.

**Baseline chain, re-recorded.** The `Makefile` change invalidates the chain that shipped with R5C,
so the identity-bound chain is re-recorded on this branch as
`157278c` -> `2dace6c` -> `b2267c7` (clean source -> immutable oracle -> finalization), measured on
Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) and checked there with `make baseline-check`
ending `baseline chain: PASS`. Two of the twenty recorded artifacts changed against the R5C chain:
`Makefile`, and `src/main.align` — the latter from the merged R1C, which changed no `Makefile` and
so required no re-record of its own. The other eighteen hashes are unchanged and the twenty paths
are identical. PR #133 merged with merge commit `35a0df6`, so these commits remain reachable.

## Pending decisions (2026-08-28)

**Decision (a) taken 2026-08-28.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (allenai;
4,213,512,192 B; sha256 `4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f`; arch
`olmoe`; 16 layers, 64 experts, top-8 routing; types F32/Q4_K/Q6_K) is downloaded to the local
models directory (path withheld from this file by convention). Disk free is now ~16 GiB on this
host. **Decision (b) is now infeasible on this host**: `gpt-oss-20b-mxfp4.gguf` at 12.1 GB no
longer fits alongside the downloaded model and its alignpack space; R1B's real-model
`model-ir-parity` qualification stays open pending a host with more free disk. **Decision (c) taken
2026-08-28** by R2C-DECODE-INSTRUMENT (PR #140, merge `89d8721`): the patched `llama-eval-callback`
is pinned, source-built out of Git, and already consumed by R2D-DECODE-LOCALITY-GATE. Decision (d)
below is unchanged and still pending.

1. **Small MoE GGUF, 1-4 GB. — TAKEN.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (3.9 GiB) is on
   this host. It unblocked the R2 locality gate (merged, PR #131), R1C's `olmoe` frontend (merged,
   PR #132), and R4's per-expert half with R4.5's expert matmul (merged, PR #133). R3's residency
   simulation (merged, PR #135), its qualification-prerequisite follow-up (merged, PR #138), and
   R5D's routed layer, in publication above, follow from the same file rather than from another
   download.
2. **`gpt-oss-20b-mxfp4.gguf`, 12.1 GB.** Unblocks R1B's real-model `model-ir-parity` qualification
   and every `ASSUMED` row of `docs/specs/r1b-gptoss-moe-ir.md` section 2.5 — including the two
   rows R1C has now contradicted from the olmoe side. **Infeasible on this host** after decision 1
   (disk free ~16 GiB); it stays open pending a host with more free disk.
3. **Build llama.cpp from source at `bb4caa754`** and apply the R2c minimal instrument patch
   (decode-step graphs, untruncated `ffn_moe_topk`). **TAKEN**, merged as PR #140. It unblocks R6
   (Persistent KV) and, through it, R7-R9, and it did extend the locality gate past prefill:
   R2D-DECODE-LOCALITY-GATE measured `decode@8` at 447 per mille against a 125 per mille null
   (`docs/specs/r2a-expert-trace.md` section 9). The cost recorded when it was proposed stands: a
   from-source external dependency whose qualification is reproducible only on hosts that repeat
   the build, materialized by `scripts/llama-eval-callback-toolchain` into a cache outside Git.
4. **Align Request 41** (non-`Copy` capture in `spawn` closures), Align-side. Unblocks R5's required
   microbenchmark C.

**Align capability requests.** The open range is 21-46: Requests 1-20 CLOSED, Requests 21-43 and
45-46 PROPOSED and non-blocking, and Request 44 ALIGN_LLM_VERIFIED, closed by PR #134.
`.align-revision` selects `3a34febe`. R2C-DECODE-INSTRUMENT and R2D-DECODE-LOCALITY-GATE added
none: neither changed an Align module, so neither met a language, compiler, or standard-library
gap. Requests 45 and 46 are new, filed by R3-RESIDENCY-SIM (see above) and renumbered from
44 and 45 when PR #134 took 44; Request 45 is priority **high** — an accepted-but-unsound compiler
defect — rather than the medium/low of the rest of this range. **R5D added no request and appended
client evidence to four**: Requests 45 and 46 gain `src/layer_olmoe.align`'s `parse_geometry` and its
routing decision (the two R5D could only anticipate before PR #135 merged them), Request 37 gains
R5D's per-unit check times — 15.6 s for the arm's own unit against 0.67 s for the 1,403-line module
beside it, which retires R5B's and R5C's under-10 s single-unit target rather than restating it — and
Request 42 gains the second exact repeat of one region diagnostic. Top clients by reference count in
`docs/align-requests.md` (grep-verified against the register): Request 34 (`Result` payloads beyond
scalars, 9 mentions), Requests 21 and 23 (read-only open; huge-struct-copy lint, 8 each — Request 23
gained R1C's `src/frontend_olmoe.align` and then R3's `residency_sim$Derived`, making six clients
across five wide records), and Requests 33 and 32 (aligned allocation; FFI by-value structs, 6 each);
Requests 32, 33, and 37 are also R5's own named clients.

**R2-LOCALITY-GATE merged checkpoint (PR #131, head `fff5806`, merge `546b5cc`).** The R2 gate is
**met in the prefill direction**. `scripts/run-expert-locality-gate` over
`eval/prompts/expert-locality-v1.txt` (40 prompts, all ≤ 6 tokens, md5
`d7fff23f5a1d4f6237e6f848f3318d8b`), one invocation per prompt, 51.8 s:

```text
verdict=LOCALITY prompts=40 layers=15 layers_clearing=15 pairs=2280 hits=3924 trials=13680
p0_per_mille=125 p_hat_per_mille=286 wilson_lo_per_mille=279 wilson_hi_per_mille=294 clusters=40
deff_per_mille=10460 cluster_lo_per_mille=262 cluster_hi_per_mille=311 ratio_per_mille=2288
entropy_per_mille=992 top8_mass_per_mille=180 truncated_documents=0 token_reduced_documents=40
token_reduced_layers=15
```

Adjacent-token expert reuse is 286 per mille against a 125 per mille null (`k/n` = 8/64), 2.29× the
null against a 1.5× materiality threshold, with all 15 contributing layers clearing the null on
their own stratum. The verdict is judged on the cluster-robust interval `[262, 311]` (design effect
10.460 over 40 prompt clusters), not the naive Wilson `[279, 294]`. The router histogram is nearly
uniform (entropy 992 per mille, all 64 experts used), so the effect is conditional structure rather
than popularity. Working sets grow sublinearly: 10.278 experts over two consecutive tokens where
independence predicts 11.437, 16.495 over four where it predicts 20.830. **Prefill only** — build
10566 evaluates one graph per invocation, `phase_split.decode` is `null`, and nothing there licenses
a decode or cache-policy claim. R2's contingency to shrink repo-expert-profile investment does
**not** fire; R3 has a measured demand signal. The same capability discharged R2A's `MOE-PREREQ`
cells (`expert trace parity (MoE): PASS` over 934 callback blocks) and added correction 20: build
10566 applies the output-token `GET_ROWS` reduction before the last layer's feed-forward, so a
*token-reduced* highest-index layer is parsed and validated but contributes no `selections[]` row
and is listed in the additive `moe.token_reduced_layers` field (`schema_version` stays 1). Full
numbers and every caveat: `docs/specs/r2a-expert-trace.md` section 8. The decode half is now
measured separately by the active R2D capability above and recorded in section 9; it adds to this
result and does not rewrite the 286 per mille, which remains the recorded value of this compact
six-slot measurement.

**R5C merged checkpoint.** Metal microbenchmark A, unified memory: self-reference `IDENTICAL` 479 of
479 nodes over 30 graphs; logits `WITHIN`, max `|Δ|` 2,936 of 6,000 ten-thousandths against R5B's
byte-identical CPU vector, `argmax` 671, top ten identical in order; bit-deterministic across paired
runs (`b6e473e8…` on both passes); transfer 59 wraps at ~12.4 ms each (732 ms total, both passes);
end-to-end wall ratio 0.99×/1.05×/1.31× across three paired runs, recorded **unresolved** rather than
claimed — the spread is `pread`'s. Correction C21 found and repaired a real cross-architecture NaN
sign-bit/payload difference (arm64's default NaN vs. x86-64 SSE's QNaN) surfacing only in the forced
non-finite-readback goldens, masked in golden normalization alone. Full ledger:
`docs/specs/r5c-metal-prefill.md`.

**Resume in another environment.** Fetch `origin`, check out `main`, then check out
`agent/r5d-moe-layer-forward` and read `docs/specs/r5d-moe-layer-forward.md` in full before touching
`src/layer_olmoe.align`, `src/moe_layer_forward.align`, the two C shims, or either runner. Decision 1
is taken; R2's gate, R1C's frontend, R4's per-expert half, R4.5's expert matmul, C8's optional
targeted stage, and R3's residency simulator are all merged, so R5D waits on no further decision. For
the rest: decision 2 -> R1B's `model-ir-parity` qualification (section R1); decision 3 -> R6 (section
R6), R7-R9, and the decode half of R2's gate; decision 4 -> R5's deferred microbenchmark C (section
R5).

**DinD preflight note.** The installed profile requires true Docker-in-Docker on macOS. The recipe
lives in this session's memory, not in the repository, and the scripts that ran it lived only in a
scratchpad and were never committed. Rebuild them from `docs/development-preflight.md` if that file
exists by the time work resumes; otherwise rebuild from the CLAUDE.md rules (the repository wrapper,
`scripts/pre-pr`, and the workflow classifier table) rather than relying on a cached copy.

## Merged checkpoints

Track B, dense local model (R0 → R5C), plus the merged R2 locality gate, the R1C olmoe frontend, the
MoE prerequisite discharge, and the R3 residency simulator; C8's optional targeted stage is the one
merged Track A re-entry. The R3-RESIDENCY-SIM, MOE-PREREQ-DISCHARGE, R2, and R5C checkpoints are
above; the rest, newest first:

- **GCC14-FP-CONTRACT-PORTABILITY** (PR #136, merge `aad872f`): `#pragma STDC FP_CONTRACT OFF` is
  Clang-only, and GCC 14.2 diagnoses it as unknown while `scripts/build-ggml-shim` compiles with
  `-Werror`; the pragma is now guarded and the cross-compiler `-ffp-contract=off` flag plus the
  behavioural probe stay mandatory. It was discovered by **this capability's** publication preflight
  and merged as its prerequisite.
- **C8-OPTIONAL-TARGETED-STAGE** (PR #134, merge `4f01553`): authored and merged by a **parallel
  Codex session**, not by the session that produced the R3 and R5D capabilities above; it is recorded
  here because R3 and R5D both consume its pin move. The targeted verification stage becomes
  optional, `R2`-unrelated, on a fresh fixed-task baseline measuring a 326,093 ppm removable ceiling
  against C8's 2,000 ppm floor; the 101-pair acceptance improves 60,515,456 ns to 40,475,113 ns
  (331,160 ppm). It adopted Align `3a34febe` (Align PR #892) as `.align-revision` and closed
  Request 44 at `ALIGN_LLM_VERIFIED`. Ledger: `docs/specs/c8-optional-targeted-stage.md`.
- **R1C-OLMOE-MOE-IR** (PR #132, head `3580a62`, merge `e15e3d3`): `src/frontend_olmoe.align`, a
  three-way architecture dispatch, and two roles appended to the frozen `role_id` list
  (`attn_q_norm` 27, `attn_k_norm` 28). The real olmoe file reaches `R1_MODEL_IR` at the unchanged
  `schema_version: 2`, the size-sum oracle closes at
  `1,781,760 + 4,211,730,432 = 4,213,512,192`, and the Block IR reaches 1,058 blocks / 3,219 claims;
  `model-ir-parity` PASS against both real models, the first discharged against a real MoE model.
  It also contradicts two of R1B's `ASSUMED` rows — the stacked gate/up/down axis order and the
  required split expert biases — recorded as corrections in `docs/specs/r1b-gptoss-moe-ir.md`
  section 7. Ledger: `docs/specs/r1c-olmoe-moe-ir.md`.
- **R5B-MODEL-PREFILL-FORWARD** (PR #128, head `3470646`, merge `870bf31`): a whole 28-layer Qwen2
  CPU prefill computed over one Align-owned alignpack window, final logits byte-identical to
  `llama-debug --save-logits`. Ledger: `docs/specs/r5b-model-prefill-forward.md`.
- **R5A-DENSE-LAYER-FORWARD** (PR #127, head `0397228`, merge `ccbd8ae`): one Qwen2 dense layer
  computed by ggml over Align-owned weight windows, bit-exact self-reference oracle. Ledger:
  `docs/specs/r5a-dense-layer-forward.md`.
- **R4.5-EXTERNAL-BUFFER-SPIKE** (PR #126, head `d46fce6`, merge `fa567b1`): a ggml matmul over an
  Align-owned quantized DRAM buffer with no silent copy; dense-block gate achieved, expert-block half
  was `MOE-PREREQ`, now unblocked by decision (a) above. Ledger: `docs/specs/r4-5-external-buffer.md`.
- **R4-ALIGNPACK-LAYER-MAJOR** (PR #125, head `a7e72dc`, merge `991eab1`): the alignpack v1
  container, its layer-major layout, and its verifier. Ledger: `docs/specs/r4-alignpack-layer-major.md`.
- **R2A-EXPERT-TRACE-CAPTURE** (PR #124, head `ab5f7d8`, merge `b8e1cb6`): `--expert-trace` CLI
  producing an `R2_ACTIVATION_TRACE` document from a `llama-eval-callback` transcript. Ledger:
  `docs/specs/r2a-expert-trace.md`.
- **R1B-GPTOSS-MOE-IR** (PR #123, head `3bf5c9c`, merge `d8d4ef6`): gpt-oss MoE frontend and
  per-expert Block IR, `R1_MODEL_IR schema_version: 2`; the gpt-oss `model-ir-parity` qualification
  stays open — decision (b) above records it infeasible on this host. Ledger:
  `docs/specs/r1b-gptoss-moe-ir.md`.
- **R1-QWEN-MODEL-IR** (PR #122, head `85a3a97`, merge `08492dc`): Qwen2 Model IR and Block IR,
  `--model-ir`, parity `PASS` against the local Qwen2.5-Coder-7B model. Ledger:
  `docs/specs/r1-qwen-model-ir.md`.
- **R0-GGUF-INSPECT** (PR #121, head `dcd8801`, merge `6640dcf`): read-only `--inspect-gguf`
  inspection, parity `PASS`. Ledger: `docs/specs/r0-gguf-inspection.md`.
- **C8-SPEED-FIRST closed** (final capability PR #120, head `fd78482`, merge `92c0979`): nine
  consumer-complete capabilities, gate met; the ppm-floor rule is the one promoted retrospective
  lesson. Ledger: `docs/specs/c8-speed-first.md`.

Earlier checkpoints, kept for continuity; full evidence lives in the named specs and in git history
at the cited commits:

- **REQUEST20-PIN** (PR #107, head `e1351f8`, merge `eb61086`): adopted Align's macOS owned-JSON CI
  repair; `ALIGN_LLM_VERIFIED` at the selected pin.
- **ADAPTER-ZOMBIE** (PR #106, head `ba02f25`, merge `0a8b9cf`): repaired a zombie/thread-group-leader
  containment-scan defect across six process-containment scanners.
- **C7-P** (PR #105, head `c86ce1e`, merge `a4f8663`): `aarch64-apple-darwin` and
  `aarch64-unknown-linux-gnu` platform profiles for C7 evidence, both discharged.
- **C7-PERSISTED-RESULT** (PR #104, head `e14ba33`, merge `a52b9ac`): `persisted_result.align`
  bounded-bucket-v1 CLI (`persist_file`/`verify_file`) and the Request 9 owned-record adoption
  checkpoint. Ledger: `docs/specs/c7-persisted-result.md`.
- **C6-MEASURED** (PR #103, head `d7f1ff6`, merge `c9a510d`): C6e/C6g1/C6g2 provider proposal and
  measured acceptance gate, `make prompt-gate-check` PASS. Ledger:
  `docs/specs/c6-prompt-context-optimizer.md`.
