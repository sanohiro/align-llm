# R8 OLMoE decode-pass other-work diagnosis

Status: complete, 2026-09-04

Roadmap owner: item 60, `R8-OLMOE-DECODE-PASS-OTHER-DIAGNOSIS`

## 1. Decision owned

Item 59 partitioned the post-staging decode-pass residual and, after review repair, measured a
4,143,730,497-ns residual median on the pinned Apple M1 host. Its explicit unassigned remainder was
the largest bucket at 2,877,094,540 ns and 694,324 ppm. Every directly named item 59 bucket missed
the unchanged 921,450,866-ns materiality floor, so no implementation seam is authorized yet.

This capability partitions only item 59's unassigned remainder into KV-plane round-trip comparison,
graph-member/spec construction, per-layer/pass accounting, and an explicit remainder. It retains
item 59's exact request, model, provider mode, output/token chain, cache budget, fresh-process
isolation, native lifetimes, host fingerprint, four conditioned repetitions, and cleanup-inclusive
ceiling. A direct bucket may select an implementation contract only when its four-sample median
clears the inherited materiality floor. This diagnosis changes no graph, ownership, provider,
cache, token, output, comparison, or failure behavior and makes no performance-win claim.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-DECODE-PASS-OTHER-DIAGNOSIS`; `scripts/run-olmoe-decode-pass-other-diagnosis`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | the next R8 investment decision after item 59, selecting one directly measured sub-bucket or another narrower diagnosis |
| Fixed request | item 59's byte-identical task/system/user prompt, OLMoE model, AlignPack, geometry, partial-LRU budget 975,175,680 bytes, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | four sequential fresh-process repetitions; each maximum-2 result is the exact prefix of the following maximum-128 result; zero processes matching both pinned llama-server and model paths before, between, and after each pair |
| Shared counters | add signed 64-bit totals `plane_roundtrip_compare_ns`, `graph_member_spec_ns`, and `layer_step_accounting_ns`, plus three corresponding `remaining_decode_*` totals; `empty_outcome` initializes all six to zero |
| Plane round-trip comparison | time the complete decode-only `verify_plane` call for each routed layer, including K/V concat shape reads, both concat `slot_get` operations, byte comparison, and comparison-result accounting; exclude `capture_plane`, its existing `plane_readback_ns`, plane upload, graph transfers, and transcript/routing oracles |
| Graph-member/spec construction | time only `decode_embed_members`, each `build_layer_members`, and each layer's `last`/`wide` derivation plus `spec_for`; exclude graph-result/routing initialization, dense or claim reads, KV stage allocation/upload, graph work, and accounting |
| Per-layer/pass accounting | time decode-pass-local updates after embedding, each routed layer, and head execution: activation accounting, node/compute/high-water and lifetime-balance updates, dense/expert/claim/cache/reader counters, routed-id append/final build, and pass result totals; exclude outer decode-loop sampling, row rendering, union/oracle accounting, every prior clock, plane comparison, and graph-member/spec construction |
| Success semantics | broad totals may include an attempted pass; each `remaining_decode_*` field adds only the exact broad-counter delta of one successfully completed step after the first at the existing commit point; first decode, EOG/maximum exits, and failed partial steps add zero |
| Exact accounting | item 59's `pass_residual.other_ns` equals plane comparison plus graph-member/spec construction plus per-layer/pass accounting plus `other_ns`; all four values are nonnegative and the three direct clocks are disjoint subsets of item 59's unassigned remainder |
| Qualification helper | new `olmoe_decode_pass_other_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; maximum is only 2 or 128; preserve item 59's exact helper record and add one exact `pass_other` object without changing prior helpers or schemas |
| Helper detail | `pass_other` has exact keys `total_ns`, `plane_roundtrip_compare_ns`, `graph_member_spec_ns`, `layer_step_accounting_ns`, and `other_ns`; maximum 2 requires all zero, maximum 128 requires a positive total and direct clocks plus the exact equation |
| Fixed baseline | item 59 replacement `OTHER_PASS_RESIDUAL` samples `[2882960092,2754901085,2871228989,2926947473]`, integer median 2,877,094,540 ns; item 59 full-helper samples `[18669300333,18063563792,18698163917,18994733625]` and 18,683,732,125-ns median remain immutable identity evidence |
| Materiality floor | inherit item 59's precommitted fixed-host floor unchanged: 921,450,866 ns per full request |
| Opportunity/decision | take four-sample medians of `PLANE_ROUNDTRIP_COMPARE`, `GRAPH_MEMBER_SPEC`, `LAYER_STEP_ACCOUNTING`, and `OTHER_PASS_REMAINDER`; choose the largest with ties in that order; below floor yields `NO_MATERIAL_BUCKET`; a direct winner yields `MEASURED_BUCKET_ELIGIBLE`; `OTHER_PASS_REMAINDER` yields `OTHER_PASS_REMAINS_UNRESOLVED` |
| Result | one exact-key schema-1 `R8_OLMOE_DECODE_PASS_OTHER_DIAGNOSIS` JSON document on stdout and one concise stderr summary; no complete document on failure |
| Inputs/identity | independently pin imported item 59 workload/evidence values, predecessor runner and old/new helper sources, decode/outcome sources, model, pack, geometry, server, Align revision/compiler, ggml libraries, C compiler/version, task, prompt, exact token chain, built helper/shim, clean head, and item 59's exact baseline-host fingerprint |
| Validation order | argument/prerequisite precedence; scrubbed environment/linker search; fixed host, clean head, process absence, imported and external identities; exact-source build; four conditioned records; schema/accounting/output/lifetime/repeatability; aggregate/decision; final identities/head; exit helper and temporary contexts; cleanup-inclusive ceiling; validation; publication |
| Failure | nonzero and no complete document for invalid arguments, identity/host/source/process drift, malformed or overlapping clocks, failed accounting, output/lifetime drift, child failure, source mutation, cleanup failure, or ceiling excess; missing prerequisites keep the one declared N/A path |
| Ownership/allocation | counters are scalars in the invocation-owned outcome; no new native owner; helper/runner/temp state is invocation-local and removed by its current owner before publication |
| Persisted/cache identity | N/A: no production, cache, model, result, or prior helper schema changes; stdout evidence is not persisted by the runner |
| Cost ceiling | one monotonic 8-minute ceiling covers helper/shim build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; each child retains a narrower bound |
| Acceptance evidence | `make fmt`; pinned new-helper build; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation; item 59 and item 60 focused self-tests; one complete real diagnosis; `git diff --check`; one comprehensive review; exact-head `scripts/pre-pr --owner-test R8-OLMOE-DECODE-PASS-OTHER-DIAGNOSIS -- scripts/run-olmoe-decode-pass-other-diagnosis --self-test` |

The capability makes one fixed-request, one-model, one-host attribution. Cross-host, GPU,
throughput, arbitrary-task, cache-policy, persistent-state, public-provider, and speedup claims are
N/A. The new helper and result are qualification-only JSON text; no production renderer exposes the
new counters. Interface deserialization and embedded-NUL behavior are unchanged because the new
record extends only runner-validated JSON emitted by the qualification helper.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Shared outcome | six zeroed `i64` scalars | broad timers accumulate only the three named disjoint operation sets | no new error; invalid delta cannot publish | failed/first steps add no remaining total | no owner | zero/positive source assertions, compile owner, real accounting |
| Plane comparison | one clock immediately outside each existing `verify_plane` call | complete successful K/V comparison is charged once | existing first mismatch/error and detail remain unchanged | skipped when decode/previous operation failed | existing graph teardown still runs once | decode smoke mismatch paths plus exact helper equation |
| Member/spec construction | clocks wrap only the three named constructors/derivations | every successful decode pass charges embed plus one member/spec set per layer | constructor behavior and existing failure sink remain unchanged | no later graph begins after failure | values retain current lexical lifetime | compile owner and real positive clock |
| Layer/pass accounting | clocks wrap existing post-operation update blocks only | activation, counters, routed ids, and final pass totals retain exact values | existing balance/accounting failures keep first error | partial pass may affect broad clock but never remaining total | builders/buffers keep current lexical cleanup | old golden/smoke owners plus real output/lifetime equality |
| Step commit | snapshot three broad counters before `decode_pass` | successful remaining step adds exact deltas | negative/overlapping subtotal rejects helper | first decode and partial step add zero | locals die per step | maximum-2 zero, full positive/equality, malformed mutants |
| Helper modes | base, item 59 detail, or item 60 detail selected only by fixed entrypoint | prior two records remain exact; new helper adds one exact object | bad arguments/output/accounting exits before print | N/A | invocation drops state | all three helper schemas built or self-tested |
| Repetition | fixed host/process absence; fresh short/full children | exact prefix/output four times | drift aborts without result | no partial sample/result | inherited signal/deadline cleanup | twelve absence checks and repeatability |
| Aggregate | four exact full records and immutable item 59 baseline | medians and deterministic decision | boolean/missing/duplicate/arithmetic/baseline drift rejects | no partial aggregate | N/A | each decision class, tie, below/at floor |
| Identity | pin imports, sources, host, tools, externals, and head | final values unchanged | any nested value or digest drift fails | missing prerequisite emits N/A | restore generated root binary | imported/nested/host mutants and real recheck |
| Signal/deadline | inherited handlers and one monotonic deadline | N/A | timeout/interruption exits nonzero | no complete JSON | stop child, restore build output, remove temp tree, then test ceiling | inherited forced timeout/restoration plus finalization mutants |

Generic monomorphization, move/source-nulling, replacement, concurrent calls, external server
ownership, and persisted migration are N/A. The shared record remains invocation-owned, decode is
synchronous, the new scalars do not add ownership, and concurrent independent processes keep
separate outcome/helper/temp state.

## 4. Implementation and verification map

1. Add the six shared scalar counters and non-overlapping clocks around the exact existing
   operations; snapshot them at the existing successful-step boundary.
2. Extend the qualification helper core with a third fixed entrypoint while keeping the original
   and item 59 JSON byte shape unchanged; add the thin item 60 helper.
3. Add a bounded runner that imports item 59's process/identity primitives, independently pins its
   baseline and sources, and owns the new schema, equations, medians, and decision.
4. Run narrow source owners and one real four-repeat diagnosis; record the selected successor here,
   in the roadmap, and in `HANDOFF.md`.
5. Complete one comprehensive review, consolidate valid findings, rerun affected owners and
   exact-head preflight, publish, merge, and continue to the selected capability.

The consumer-complete diff may exceed 1,000 hand-written lines because the shared counters, exact
helper extension, source-pinned runner, real decision, and owner tests are one usable evidence
boundary. Splitting them would leave dormant counters or an unvalidated record and would duplicate
the same accounting and cleanup proof. No `make ci`, installed platform profile, portfolio, stress
suite, cache replay, or unrelated benchmark is selected.

## 5. Author consistency pass

The ledger and matrix agree on three direct non-overlapping clocks, one explicit remainder, the
existing successful-step commit, item 59's immutable fixed-host baseline, four conditioned repeats,
and the inherited 921,450,866-ns floor. Every new counter has one owner and one helper/result field;
no prose renames residual work or authorizes an optimization before measurement.

## 6. Recorded result

The clean-head run at `1cc8cb48c2d91680ee4ee4b618b33c4472d1f66f` completed in
116.826 seconds on the pinned Apple M1 host. All four repetitions produced the fixed 86-token
completion and output hash, balanced buffers, contexts, backend, allocators, and resident wrap
exactly, released the native model, and found zero matching llama.cpp processes at all twelve
required boundaries.

Full-helper wall samples were `[17704139042,18412456541,19080317000,19520549709]`, with an
18,746,386,770-ns median. The `pass_other` samples and medians were:

| Bucket | Four samples (ns) | Median (ns) |
| --- | --- | ---: |
| `PLANE_ROUNDTRIP_COMPARE` | `[2804882618,2912389855,3032260023,3120889620]` | 2,972,324,939 |
| `GRAPH_MEMBER_SPEC` | `[7296786,7424921,7745205,7449337]` | 7,437,129 |
| `LAYER_STEP_ACCOUNTING` | `[1395066,1393012,1320370,1301033]` | 1,356,691 |
| `OTHER_PASS_REMAINDER` | `[16199166,16721317,16684650,17126913]` | 16,702,983 |

The complete `pass_other` totals were `[2829773636,2937929105,3058010248,3146766903]`, with a
2,997,969,676-ns median. `PLANE_ROUNDTRIP_COMPARE` supplied 991,445 ppm of that median and cleared
the inherited 921,450,866-ns materiality floor by 2,050,874,073 ns. The decision is therefore
`MEASURED_BUCKET_ELIGIBLE / PLANE_ROUNDTRIP_COMPARE`.

Inspection maps the winner to the scalar `compare_past_k` and `compare_past_v` loops after each
concat `slot_get`. Item 61 is selected to preserve the exact byte/layout oracle and first-mismatch
column while moving those reads to a validated, allocation-free shared-shim comparison. This
diagnosis does not itself establish a performance win.
