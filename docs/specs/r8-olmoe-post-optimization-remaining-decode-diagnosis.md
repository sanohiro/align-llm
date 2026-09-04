# R8 OLMoE post-optimization remaining-decode diagnosis

Status: measured; publication pending, 2026-09-05

Roadmap owner: item 70, `R8-OLMOE-POST-OPTIMIZATION-REMAINING-DECODE-DIAGNOSIS`

## 1. Decision owned

Item 69 remeasured the fixed isolated sampled coding portfolio after the item 58 and item 68
decode reductions. Runtime improved substantially relative to item 56's historical measurement,
but its 91.416-second median remained 6.53 times the current 13.993-second local median. R8
therefore remains open.

The shipped item-68 fixed request is the current diagnostic baseline: full-helper walls
`[17714825083,16684315166,17132135334,21189618042]` ns and an integer median of
17,423,480,208 ns. Its precommitted 50,000-ppm materiality floor is 871,174,011 ns. The existing
helper still reports exact nested clocks for remaining-decode phases, claim I/O, graph compute,
pass residual, and pass-other work. Reusing only a parent partition would double-count these nested
totals and could reselect a boundary already narrowed by items 59, 60, 62, and 64.

This capability therefore re-runs item 68's exact conditioned four-repeat qualification on current
shipped code and flattens the deepest available clocks into one mutually exclusive remaining-decode
leaf partition. A measured leaf selects a successor only when its median reaches the fixed floor.
An explicit remainder selects a narrower diagnosis; a smaller winner records no material bucket.
This is attribution only: it changes no product behavior and makes no speedup or R8-closing claim.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-POST-OPTIMIZATION-REMAINING-DECODE-DIAGNOSIS`; `scripts/run-olmoe-post-optimization-remaining-decode-diagnosis`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | the next R8 diagnosis or implementation ledger after item 69's `NOT_MET` primary-metric decision |
| Fixed request | inherit item 68 exactly: task/system/user prompt, OLMoE model, AlignPack, geometry, 975,175,680-byte partial-LRU budget, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | item 68's four sequential fresh-process pairs; each maximum-2 result is the exact prefix of the following maximum-128 result; zero processes matching both pinned llama-server and model paths before, between, and after every pair |
| Shipped state | item 58's combined K/V staging range plus item 68's unaligned-safe exact in-place plane comparison and fixed-stride cache-backed phase B; retain full-width phase A, exact 7,325 hits / 4,615 misses / 4,376 evictions, 17,656,872,960 fetched bytes, output, and native lifetimes |
| Measurement source | delegate the complete item 68 owner in a child process; validate its exact schema, identities, source chain, equations, samples, cleanup-inclusive ceiling, and current head before reaggregation |
| Leaf partition | for each full sample, replace every nested parent by its deepest shipped children: `PRE_PASS_ORCHESTRATION`; `PACK_OR_RESIDENT_STAGE`; the five claim-I/O leaves; the four compute leaves; `ROUTING_ORCHESTRATION`; `PLANE_UPLOAD`; `PLANE_READBACK`; four direct pass-residual leaves; four pass-other leaves; and `POST_PASS_ORCHESTRATION` |
| Claim-I/O leaves | `FILE_PREAD`, `BLOCK_TO_CLAIM_COPY`, `CLAIM_TO_CACHE_COPY`, `CACHE_TO_CLAIM_COPY`, and `OTHER_CLAIM_IO`; their per-sample sum equals `remaining_decode.claim_pread_ns` |
| Compute leaves | `EMBEDDING`, `ROUTING_PHASE_A`, `EXPERT_PHASE_B`, and `OUTPUT_HEAD`; their per-sample sum equals `remaining_decode.compute_ns` |
| Residual leaves | `CONTEXT_BUFFER_SETUP`, `GRAPH_BUILD_ALLOC`, `GENERIC_TRANSFER_DIGEST`, and `GRAPH_TEARDOWN`, plus pass-other leaves `PLANE_ROUNDTRIP_COMPARE`, `GRAPH_MEMBER_SPEC`, `LAYER_STEP_ACCOUNTING`, and `OTHER_PASS_REMAINDER`; together they equal `remaining_decode.pass_residual_ns` |
| Exact accounting | every leaf is a nonnegative integer; per sample the 23 leaf values sum exactly to `engine_phases.remaining_decode_ns`; parents are validated but never included beside their children |
| Immutable baseline | item 68 walls `[17714825083,16684315166,17132135334,21189618042]` ns and median 17,423,480,208 ns; do not recompute the decision floor from the new instrumented samples |
| Materiality floor | 50,000 ppm of the immutable median, rounded up: 871,174,011 ns per full request |
| Selection | take four-sample integer medians in the declared leaf order and choose the largest, retaining the earlier leaf on ties; record its share of the current remaining-decode median |
| Decision | selected median below the floor yields `NO_MATERIAL_BUCKET`; an at-or-above-floor `OTHER_CLAIM_IO` or `OTHER_PASS_REMAINDER` yields `NARROWER_DIAGNOSIS_REQUIRED`; every other at-or-above-floor leaf yields `MEASURED_BUCKET_ELIGIBLE` and may authorize only a successor ledger with a complete-request shipping gate |
| Result | preserve item 68's exact schema-1 document and evidence, change only its artifact kind to `R8_OLMOE_POST_OPTIMIZATION_REMAINING_DECODE_DIAGNOSIS`, and add one exact `diagnosis` object containing immutable baseline/floor, current walls and remaining-decode values, leaf values/medians, selection/share, and decision; stdout has no complete document on failure |
| Inputs/identity | independently pin item 68's runner and complete transitive source chain, inherited workload/baselines/intervention, model, pack, geometry, server, Align revision/compiler, ggml libraries and consumed headers, C compiler/version, task, prompt, exact token chain, built helper/shim, clean align-llm head, and fixed host fingerprint |
| Validation order | arguments/prerequisites; imported workload, baseline, source, and external constants; delegated item 68 execution; exact inherited result; leaf key/type/equation validation; deterministic aggregate/decision; unchanged evaluated head and source chain; publication |
| Failure | nonzero and no complete document for invalid arguments, malformed/multiple/non-UTF-8 child output, child/timeout/cleanup failure, identity/source/head drift, inherited schema/equation/output/cache/lifetime/isolation failure, boolean/negative/missing/duplicate leaf, leaf-total mismatch, or baseline/floor drift; missing prerequisites retain one declared N/A line |
| Ownership/allocation | this runner owns one child process and transient decoded JSON; all model/helper/shim/temp/native ownership remains with item 68; no production allocation or owner changes |
| Persisted/cache identity | N/A: no production, cache, model, pack, provider, or persisted-result format changes; qualification stdout is not persisted by the runner |
| Cost ceiling | item 68 retains its monotonic 8-minute publication ceiling; the outer wait adds only a 50-second inherited cleanup allowance and rejects a successful delegated result whose item-68 elapsed value exceeds that existing ceiling |
| Acceptance evidence | author ledger-to-prose consistency pass; Python compilation; item 68 and item 70 focused self-tests; one clean-head fixed-host four-repeat diagnosis; `git diff --check`; one comprehensive review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-POST-OPTIMIZATION-REMAINING-DECODE-DIAGNOSIS -- scripts/run-olmoe-post-optimization-remaining-decode-diagnosis --self-test` |

Cross-host, GPU, throughput, arbitrary-task, cache-policy, persistent lifetime, public-provider,
kernel, and performance-win claims are N/A. The delegated item-68 record is current measurement
evidence, but its historical performance decision is not reopened by this attribution capability.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Delegated owner | spawn the exact item-68 runner with inherited environment and pipes | one UTF-8 JSON line, zero exit | nonzero, multiple lines, malformed JSON, or timeout rejects | no adapted result | terminate; wait full 50-second inherited cleanup budget; then kill | success/failure/shape/timeout/escalation self-tests and real run |
| Inherited evidence | validate item 68 before projection | all output/cache/lifetime/isolation/source equations remain exact | any inherited drift rejects | N/A | owned by item 68 | item-68 self-test plus nested mutation |
| Leaf projection | read only deepest fields from each full record | exactly 23 nonnegative integer values | boolean, negative, missing, duplicate, or unknown field rejects | conditioning is retained only as inherited evidence | no owner | exact-key/type and malformed-clock mutants |
| Accounting | sum leaf values after inherited parent equations pass | equals remaining-decode total in every sample | overlap/omission rejects before aggregate | no partial aggregate | N/A | equality mutant and synthetic exact partition |
| Aggregate | four exact samples plus immutable baseline/floor | deterministic medians, selection, share, and decision | sample count, arithmetic, baseline, or output drift rejects | no partial result | N/A | tie, below-floor, at-floor direct, and at-floor remainder vectors |
| Identity/head | pin item 68 plus its full source chain before delegation | recheck hashes and exact evaluated head afterward | any source/head drift rejects | missing prerequisite emits N/A | no owner | source mutation and head mismatch self-tests; real recheck |
| Publication | adapt only artifact kind and add diagnosis | one exact complete document | validation failure prints no JSON | N/A | child already reaped | round-trip projection and exact-key self-test |
| Signal/deadline | install handlers before real work | N/A | interruption exits nonzero | no complete JSON | same terminate/wait/kill path | active-child signal cleanup owner |

Generic monomorphization, move/source-nulling, concurrent calls, external-server ownership,
persisted migration, and production races are N/A. The new consumer is synchronous and adds no
borrow or native lifetime.

## 4. Implementation and verification map

1. Add one thin runner which imports item 68, independently pins its complete consumed chain, and
   owns child execution, schema projection, the exact leaf map, medians, decision, and cleanup.
2. Run item 68 and item 70 self-tests, commit a clean implementation checkpoint, and execute one
   fixed-host four-repeat diagnosis with the pinned local artifacts.
3. Record the selected successor here, in the roadmap, and in `HANDOFF.md` without changing product
   code or relabelling the result as a speedup.
4. Complete one comprehensive review, consolidate valid findings, rerun affected evidence and
   exact-head preflight, publish, merge, and continue to the selected successor.

No Align source, `make ci`, installed platform profile, coding portfolio, 40-prompt corpus, stress
suite, cache replay, or unrelated benchmark is selected. Existing current clocks plus one exact
consumer form the smallest useful end-to-end diagnostic capability.

## 5. Author consistency pass

The ledger and matrix agree that the immutable item-68 median owns the floor, each current parent
is replaced by—not added to—its deepest children, every sample must close exactly to remaining
decode, explicit remainders cannot directly authorize implementation, and item 68 retains all
model/native cleanup. No text turns nested timers into an additive hierarchy, changes product
behavior, or claims that a measured leaf is fully removable.

## 6. Fixed-host result

The clean-head run at `7704d9f18ea4d41681c984420ea7e591450f4a79` completed in
125,969,460,750 ns. Full-helper walls were
`[20098090084,22297438083,23257008916,22355763250]` ns, with a current median of
22,326,600,666 ns. Remaining decode measured
`[14740449453,16733289713,16776725004,15902827210]` ns, with a 16,318,058,461-ns median.
The current wall median does not replace item 68's immutable 17,423,480,208-ns diagnostic
baseline or the precommitted 871,174,011-ns floor; this capability makes no new performance claim.

Every maximum-2 request was the exact prefix of its maximum-128 pair. All four full requests
reproduced the fixed token/output identity, exact 11,940 cache requests, 7,325 hits, 4,615 misses,
4,376 evictions, 17,656,872,960 fetched bytes, zero cache-to-claim copies, balanced native
lifetimes, and zero matching processes at all twelve isolation boundaries. Every sample's 23 leaf
values summed exactly to its remaining-decode total.

| Leaf | Median (ns) |
| --- | ---: |
| `PRE_PASS_ORCHESTRATION` | 1,089,208 |
| `PACK_OR_RESIDENT_STAGE` | 285,036 |
| `FILE_PREAD` | 2,582,700,546 |
| `BLOCK_TO_CLAIM_COPY` | 399,100,251 |
| `CLAIM_TO_CACHE_COPY` | 708,634,028 |
| `CACHE_TO_CLAIM_COPY` | 0 |
| `OTHER_CLAIM_IO` | 38,352,848 |
| `EMBEDDING` | 1,654,350 |
| `ROUTING_PHASE_A` | 4,620,020,794 |
| `EXPERT_PHASE_B` | 1,755,611,568 |
| `OUTPUT_HEAD` | 222,480,002 |
| `ROUTING_ORCHESTRATION` | 17,342,259 |
| `PLANE_UPLOAD` | 2,710,801,676 |
| `PLANE_READBACK` | 13,012,534 |
| `CONTEXT_BUFFER_SETUP` | 57,895,992 |
| `GRAPH_BUILD_ALLOC` | 163,450,911 |
| `GENERIC_TRANSFER_DIGEST` | 1,154,918,793 |
| `GRAPH_TEARDOWN` | 400,513,311 |
| `PLANE_ROUNDTRIP_COMPARE` | 1,177,068,085 |
| `GRAPH_MEMBER_SPEC` | 11,901,065 |
| `LAYER_STEP_ACCOUNTING` | 2,140,088 |
| `OTHER_PASS_REMAINDER` | 25,854,036 |
| `POST_PASS_ORCHESTRATION` | 187,032,963 |

`ROUTING_PHASE_A` is the deterministic winner at 4,620,020,794 ns, 283,123 ppm of current
remaining decode and 3,748,846,783 ns above the fixed materiality floor. The decision is
`MEASURED_BUCKET_ELIGIBLE`. Item 63 already showed that removing fixed-width K/V PAD by changing
the graph to live width neither preserved exact cache decisions in combination nor reliably
cleared the complete-request gate alone. Item 71 therefore owns a narrower phase-A operation
diagnosis before another implementation seam is chosen. The existing 37-row phase-A graph and all
shipped item-68 behavior remain unchanged.

## 7. Review record

One comprehensive Codex CLI review covered head
`b2c97f8ea0bf198f524d07bca5e85f4649d3b4c2` against base tip and merge base
`cc2b080a4241c0cb37e254c4a4e17f286c401c54`, using gpt-5.6-sol at high effort over the complete
diff. It found one valid P2: `HANDOFF.md` still told a resumed session to commit the result even
though the reviewed head already contained that commit. Consolidated repair
`828b173613c85943d97b3acb430ec210beca5d41` removes the completed action. The repair changes no
schema, measurement, decision, or product behavior, so neither a real rerun nor a second
comprehensive review is required.
