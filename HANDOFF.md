# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active: R3-QUALIFICATION-PREREQUISITES (2026-08-28)

Branch `fix/r3-qualification-prerequisites` starts from current `main` `95c47e7`, the merge of R3
PR #135. A second R3 implementation was independently completed before that merge became visible;
its duplicate PR #137 is closed and will not be integrated. Its final review nevertheless exposed
one root-cause class that applies to the merged qualification: the wrapper generated a Model IR but
did not validate it or the requested budget until after every prompt had invoked the external
instrument, so a locally knowable defect could consume up to 40 600-second prompt runs.

**Current checkpoint.** `scripts/run-residency-sim` now validates prompt count in the simulator's
existing `[1, MAX_TRACE_PATHS]` envelope, derives the Model IR and default budget, and asks the
simulator itself to validate both against a one-row probe list whose trace is deliberately absent.
Only exact `R3_TRACE_UNREADABLE` step-8 evidence admits instrument `--version` and prompt capture;
no Model IR or budget validation is duplicated in shell. The hosted owner covers three refusals
with zero fake-instrument calls and one valid admission through `--version` to the first prompt.
`make residency-sim-smoke`, `make residency-sim-qualification` (exact N/A), `make format-check`, and
`make baseline-check` pass. The hardware-name evidence finding from the duplicate implementation is
not applicable because merged R3 has no hardware-profile string input.

**Next actions, in order.** Commit the coherent repair, perform one comprehensive review, run the
owner and exact-head preflight, publish and merge the follow-up, then refresh `main` and start the
next eligible roadmap capability.

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
`model-ir-parity` qualification stays open pending a host with more free disk. Decisions (c) and
(d) below are unchanged and still pending.

1. **Small MoE GGUF, 1-4 GB. — TAKEN.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (3.9 GiB) is on
   this host. It unblocked the R2 locality gate (merged, PR #131), R1C's `olmoe` frontend (merged,
   PR #132), and R4's per-expert half with R4.5's expert matmul (merged, PR #133). R3's residency
   simulation, merged in PR #135 above, follows from the same file rather than from another download.
2. **`gpt-oss-20b-mxfp4.gguf`, 12.1 GB.** Unblocks R1B's real-model `model-ir-parity` qualification
   and every `ASSUMED` row of `docs/specs/r1b-gptoss-moe-ir.md` section 2.5 — including the two
   rows R1C has now contradicted from the olmoe side. **Infeasible on this host** after decision 1
   (disk free ~16 GiB); it stays open pending a host with more free disk.
3. **Build llama.cpp from source at `bb4caa754`** and apply the R2c minimal instrument patch (decode-
   step graphs, untruncated `ffn_moe_topk`). Neither `llama-eval-callback` nor
   `llama-debug --save-logits` can observe a KV cache beyond a handful of positions, so this unblocks
   R6 (Persistent KV) and, through it, R7-R9. It is also what would extend the merged locality gate
   past prefill. Cost: a clone plus a cmake build, a new from-source external dependency, and a
   qualification reproducible only on hosts that repeat the build.
4. **Align Request 41** (non-`Copy` capture in `spawn` closures), Align-side. Unblocks R5's required
   microbenchmark C.

**Align capability requests.** Requests 1-20 CLOSED, Requests 21-43 and 45-46 PROPOSED and
non-blocking, and Request 44 ALIGN_LLM_VERIFIED, closed by PR #134. `.align-revision` now selects
`3a34febe`. Requests 45 and 46 are new, filed by R3-RESIDENCY-SIM (see above) and renumbered from
44 and 45 when PR #134 took 44; Request 45 is priority **high** — an accepted-but-unsound compiler
defect — rather than the medium/low of the rest of this range. Top clients by reference count in
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
numbers and every caveat: `docs/specs/r2a-expert-trace.md` section 8.

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
`agent/r3-residency-sim` and read `docs/specs/r3-residency-sim.md` in full before touching
`src/residency_sim.align`, the oracle, or either runner. Decision 1 is taken; R2's gate, R1C's
frontend, R4's per-expert half, R4.5's expert matmul, and C8's optional targeted stage are all
merged, so R3 waits on no further decision. For the rest: decision 2 -> R1B's `model-ir-parity` qualification (section R1);
decision 3 -> R6 (section R6), R7-R9, and the decode half of R2's gate; decision 4 -> R5's deferred
microbenchmark C (section R5).

**DinD preflight note.** The installed profile requires true Docker-in-Docker on macOS. The recipe
lives in this session's memory, not in the repository, and the scripts that ran it lived only in a
scratchpad and were never committed. Rebuild them from `docs/development-preflight.md` if that file
exists by the time work resumes; otherwise rebuild from the CLAUDE.md rules (the repository wrapper,
`scripts/pre-pr`, and the workflow classifier table) rather than relying on a cached copy.

## Merged checkpoints

Track B, dense local model (R0 → R5C), plus the merged R2 locality gate, the R1C olmoe frontend, and
the MoE prerequisite discharge; C8's optional targeted stage is the one merged Track A re-entry.
The MOE-PREREQ-DISCHARGE, R2, and R5C checkpoints are above; the rest, newest first:

- **GCC14-FP-CONTRACT-PORTABILITY** (PR #136, merge `aad872f`): `#pragma STDC FP_CONTRACT OFF` is
  Clang-only, and GCC 14.2 diagnoses it as unknown while `scripts/build-ggml-shim` compiles with
  `-Werror`; the pragma is now guarded and the cross-compiler `-ffp-contract=off` flag plus the
  behavioural probe stay mandatory. It was discovered by **this capability's** publication preflight
  and merged as its prerequisite.
- **C8-OPTIONAL-TARGETED-STAGE** (PR #134, merge `4f01553`): the targeted verification stage becomes
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
