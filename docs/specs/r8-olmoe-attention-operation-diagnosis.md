# R8 OLMoE attention operation diagnosis

Status: review repair measured; final review pending, 2026-09-05

Roadmap owner: item 72, `R8-OLMOE-ATTENTION-OPERATION-DIAGNOSIS`

## 1. Decision owned

Item 71 split the complete decode phase-A graph into direct attention/residual and router graph-
compute walls. Attention/residual measured 2,627,247,387 ns at the four-sample median, 980,342 ppm
of split phase A and well above the immutable 871,174,011-ns floor. Router measured only
52,680,203 ns and is not an eligible implementation seam. The attention result still spans 32
table rows and is too broad to authorize a rewrite.

This capability adds one narrower opt-in qualification path over the same already-built and
already-allocated phase-A graph. It directly computes three attention classes in topological
order: rows 0-13 contain attention normalization and Q/K/V projections, rows 14-27 contain KV
concatenation plus the score/value attention core, and rows 28-31 contain output projection plus
the residual. It then directly computes item 71's rows 32-36 router suffix so the original result
is complete. The three attention walls close exactly to item 71's attention/residual wall; the
router clock remains separate and cannot win item 72's selection.

The largest attention class may select a successor only when its median reaches the inherited
floor. A material output/residual result identifies a four-row implementation seam. Material
projection or attention-core results require a still narrower diagnosis because each combines
multiple distinct matrix and preparation operations. Item 63's rejected live-width phase-A
intervention remains forbidden. This capability makes no speedup claim and does not close R8.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-ATTENTION-OPERATION-DIAGNOSIS`; `scripts/run-olmoe-attention-operation-diagnosis`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | the next R8 implementation ledger or narrower diagnosis selected from item 71's material attention/residual prefix |
| Fixed request | item 71's inherited item-68 request: identical task/system/user prompt, OLMoE model, AlignPack, geometry, 975,175,680-byte partial-LRU budget, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | four sequential fresh-process pairs; maximum 2 is the exact prefix of maximum 128; zero processes matching both pinned llama-server and model paths before, between, and after each pair |
| Source graph | preserve all 37 decode phase-A rows, fixed request width, operands, output marks, allocation, and table/topological order |
| Exact attention boundaries | `PROJECTIONS` is rows 0-13 inclusive and ends at the row-13 V reshape; `ATTENTION_CORE` is rows 14-27 inclusive and ends at the row-27 contiguous attention value; `OUTPUT_RESIDUAL` is rows 28-31 inclusive and ends at `ffn_inp`; `ROUTER` remains rows 32-36 and ends at `ffn_moe_argsort` |
| Slice construction | add one bounded slot-range selection ABI beside item 71's positional partition ABI. For each class, require every populated output slot in its inclusive row range to occur exactly once in the source graph, then copy those node pointers in the source graph's actual topological order. Construct exactly four class graphs. This is necessary because dependency traversal interleaves table row ranges in the source graph |
| Slice lifetime | one diagnostic context owns all four borrowed graph structures. The source graph, source tensor contexts, slot store, allocator, and backend buffers outlive all four computes. The diagnostic context is freed first and adds no allocator or tensor ownership |
| Execution modes | normal mode executes the original one phase-A graph; item-71 mode executes its original attention/residual then router pair; only item-72 mode executes projection, attention-core, output/residual, then router. No mode computes the source graph as an additional control |
| Failure labels | selection failure uses `R5_GGML_INIT` with `attention_operation_partition`; compute failures retain `R5_COMPUTE` with `status_projection`, `status_attention_core`, `status_output_residual`, or item 71's `status_router`. Later computes are skipped after the first failure and no successful step is committed |
| Direct clocks | add `attention_projection_ns`, `attention_core_ns`, and `attention_output_residual_ns`; their sum is `phase_a_attention_ns`. Add the unchanged direct router wall to form `compute_a_ns`. These are graph-slice operation-class walls, not kernel or individual-node attribution |
| Remaining-decode commit | add matching remaining-decode counters at the existing successful-step-after-first commit. Maximum 2 reports zero for every item-72 clock; maximum 128 reports positive values and exact parent equations |
| Qualification helper | new `olmoe_attention_operation_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; preserve the complete item-71 record and add exact object `attention_operations` with `total_ns`, `projections_ns`, `attention_core_ns`, and `output_residual_ns` |
| Exact accounting | helper requires nonnegative signed 64-bit integers; three children sum to `total_ns`; `total_ns == phase_a_operations.attention_and_residual_ns`; adding the unchanged router clock equals `decode_compute.routing_ns`; conditioning values are all zero and full values all positive |
| Shipped-state evidence | preserve item 71's full-width execution, exact output, 11,940 requests / 7,325 hits / 4,615 misses / 4,376 evictions / 17,656,872,960 fetched bytes, zero cache-to-claim copies, isolation, and balanced native lifetimes. Diagnostic context counts are validated from each produced pair rather than compared with item 71's two-slice counts |
| Immutable baseline | item 68 walls `[17714825083,16684315166,17132135334,21189618042]` ns and median 17,423,480,208 ns; item 71's operation medians are attribution context only and are not a new baseline |
| Materiality floor | 50,000 ppm of the immutable median, rounded up: 871,174,011 ns per full request |
| Selection | take four-sample integer medians in declared order `PROJECTIONS`, `ATTENTION_CORE`, `OUTPUT_RESIDUAL`; choose the larger with declared order breaking ties; record its share of the three-class attention median. Router is excluded from selection |
| Decision | below-floor winner yields `NO_MATERIAL_ATTENTION_CLASS`; material `PROJECTIONS` yields `PROJECTION_SUBDIAGNOSIS_REQUIRED`; material `ATTENTION_CORE` yields `ATTENTION_CORE_SUBDIAGNOSIS_REQUIRED`; material `OUTPUT_RESIDUAL` yields `MEASURED_OUTPUT_RESIDUAL_SEAM_ELIGIBLE` |
| Result | one exact-key schema-1 `R8_OLMOE_ATTENTION_OPERATION_DIAGNOSIS` JSON document on stdout and one concise stderr summary; no complete document on failure |
| Inputs/identity | independently pin the complete item-71 runner/helper/source chain plus the item-72 helper and every changed Align source, shim/stub/build script, model, pack, geometry, server, Align revision/compiler, ggml libraries and consumed headers, C compiler/version, task, prompt, exact token chain, built helper/shim, clean align-llm head, and inherited host fingerprint |
| Validation order | arguments/prerequisites; imported constants and source identities; scrubbed environment/linker search; fixed host, clean head, process absence, external identities; exact-source build; four conditioned records; helper schema/equations/output/cache/lifetime/repeatability; aggregate/decision; final identities/head; cleanup-inclusive ceiling; publication |
| Failure | nonzero and no complete document for invalid arguments, empty/duplicate/missing/non-source range member, reversed range, slice construction or compute failure, malformed/overlapping clocks, equation/output/cache/lifetime/source/host/process drift, child failure, mutation, cleanup failure, or ceiling excess; missing prerequisites retain one declared N/A line |
| Ownership/allocation | production adds only zero-initialized scalar counters. Item-72 calls add one context and four context-owned graph structures per routed layer; every path converges on existing teardown. Runner/helper/temp state is invocation-local |
| Persisted/cache identity | N/A: no provider, cache, model, pack, task, or persisted-result schema changes; qualification stdout is not persisted by the runner |
| Cost ceiling | one monotonic 8-minute ceiling covers helper/shim build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; each child retains a narrower bound |
| Acceptance evidence | author ledger-to-prose consistency pass; a branched dependency graph proving noncontiguous slot-class selection plus malformed-range owner coverage; `make fmt`; pinned helper build; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation; inherited validators and focused self-test; one clean-head fixed-host four-repeat diagnosis; `git diff --check`; the comprehensive review and its final-review repair check; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-ATTENTION-OPERATION-DIAGNOSIS -- scripts/run-olmoe-attention-operation-diagnosis --self-test` |

Cross-host, GPU, throughput, arbitrary-task, cache-policy, persistent-state, public-provider,
per-kernel, per-node, and performance-win claims are N/A. Four computed slices add three backend
dispatches per routed layer versus normal execution and two dispatches versus item 71. Their walls
describe only this diagnostic execution boundary. Any later implementation needs its own unchanged
full-request shipping gate.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Operation-class slices | validate every slot member against the source while deriving four graphs | exact ranges 0-13, 14-27, 28-31, and 32-36 retain source topology even when row ranges interleave | null graph, missing/duplicate/non-source member, reversed range, wrong class count, or wrong combined count maps to one init failure | no compute until all slices exist | one diagnostic context owns all four graph tables | branched source-order fixture, exact counts, and range refusal vectors |
| Normal layer | both diagnostic flags false | original source graph computed once; all item-71/72 clocks zero | existing status/detail unchanged | failed graph does not commit a step | existing owners | runtime provider smoke and normal helper validators |
| Item-71 layer | phase-A flag true; attention flag false | original two slices and two clocks remain unchanged | existing item-71 failures/labels unchanged | router skipped after attention failure | existing diagnostic context first | item-71 self-test chain and source-compatible path inspection |
| Item-72 layer | both diagnostic flags true | compute projection, core, output/residual, router exactly once each | first failed compute labels its class and skips successors | failed layer never publishes a successful step | diagnostic context freed before source graph/tensor contexts | forced construction/compute failure plus real exact output/lifetime |
| Counters | layer result and outcome start every new scalar at zero | three attention children close to parent; parent plus router closes routing | helper rejects negative, boolean, overlap, gap, or wrong parent | failed step deltas are not committed | scalars only | zero conditioning, full positive values, exact equations |
| Helper modes | only new helper selects item 72 | item-71 and all older schemas remain byte-shaped as before | invalid argument or equation returns before print | N/A | invocation drops state | pinned new helper plus old runtime/helper owners |
| Repetition | fixed host/process absence; fresh short/full children | exact prefix/output/cache four times | drift aborts without aggregate | no partial sample/result | inherited signal/deadline cleanup | twelve absence checks and repeatability |
| Aggregate | four exact samples and immutable floor | deterministic class medians/share/decision; router excluded | bad count/type/equation/baseline/identity rejects | no partial aggregate | N/A | below-floor, tie, and each class-at-floor vectors |
| Identity/publication | pin the transitive executable chain before measurement | final hashes/head unchanged; one result document | mutation or multiple/malformed output rejects | missing prerequisite emits one N/A line | restore generated root binary | changed-source mutation and real final recheck |
| Signal/deadline | inherited handlers own spawned processes before real work | N/A | interruption or timeout exits nonzero | no complete JSON | terminate, wait, then kill if required | inherited forced-timeout/restoration evidence |

Generic monomorphization, move/source-nulling, concurrent calls, external server ownership,
persisted migration, and production races are N/A. Every slice borrows tensor pointers only during
the synchronous routed-layer frame and cannot escape its diagnostic context.

## 4. Implementation and verification map

1. Extend the item-71 diagnostic branch with an independent item-72 mode. Construct four graphs by
   exact output-slot membership while preserving each class's source-topological order, then execute
   the classes in declared table order. Keep item 71's positional partition ABI unchanged.
2. Add three direct layer/outcome clocks and remaining-decode deltas at the existing successful-
   step commit. Preserve item-71's parent clocks and every existing entry point.
3. Add the thin helper and runner, pin the complete consumed chain, and own exact schema,
   accounting, medians, selection, cleanup, and mutation regressions.
4. Run narrow owners and one clean-head four-repeat diagnosis. Record the selected narrower
   diagnosis, exact output/residual seam, or no-material result here, in the roadmap, and in
   `HANDOFF.md`.
5. Complete one comprehensive review, consolidate valid findings, rerun affected evidence and
   exact-head preflight, publish, merge, and continue to the selected successor.

No `make ci`, installed platform profile, coding portfolio, 40-prompt corpus, stress suite, cache
replay, live-width retry, or unrelated benchmark is selected. The three new clocks and their exact
qualification consumer form one consumer-complete diagnostic capability.

## 5. Author consistency pass

The ledger and matrix agree that item 72 selects exact table-owned operation membership while
retaining the source graph's dependency order, constructs every slice before computation, directly
times three mutually exclusive attention ranges, excludes the already-nonmaterial router from
selection, and preserves both older execution modes. The child clocks close to item 71's attention
parent, while the parent plus router closes the existing routing total. Only an output/residual win
is narrow enough to authorize implementation directly; broader wins select another diagnosis and
never reopen live width.

## 6. Review correction and result

The first comprehensive review covered result-record head `d5b87d5` against base tip and merge
base `ce7493832f7ca8d8ddbb44d89dfc17402b4adcb3` using Codex `gpt-6-astra` at high effort. It
found one P1: the positional partitions followed ggml dependency traversal rather than table-row
order, placing the independent Q/K projection branch inside the alleged attention-core slice. The
first attribution and decision were withdrawn. Consolidated repair `9353f2e` adds exact populated-
slot membership selection, preserves source-topological order within each class, accounts for the
two last-layer-only narrowing rows, and adds a branched dependency regression plus refusal vectors.

The repaired clean-head run at `9353f2e44e7ea1baad4fd71f50987d68becfc330` completed in
95,406,610,208 ns. Full-helper walls were
`[14702982750,15834709417,16180880083,16213551166]` ns, with a 16,007,794,750-ns median.
The corrected direct attention-class values and medians were:

| Class | Four values (ns) | Median (ns) |
| --- | --- | ---: |
| `PROJECTIONS` | `[320151872,349815360,334002561,331798686]` | 332,900,623 |
| `ATTENTION_CORE` | `[2285581142,2511530006,2539996034,2571609454]` | 2,525,763,020 |
| `OUTPUT_RESIDUAL` | `[106581544,119611215,111838391,111285508]` | 111,561,949 |

The attention-parent values were `[2712314558,2980956581,2985836986,3014693648]` ns and their
median was 2,983,396,783 ns. `ATTENTION_CORE` therefore won at 846,606 ppm of its parent and far
above the immutable 871,174,011-ns floor. The repaired decision is
`ATTENTION_CORE_SUBDIAGNOSIS_REQUIRED`; neither projection nor output/residual is an eligible
implementation seam from this evidence.

All four full requests reproduced the exact 86-token output and fixed cache accounting: 11,940
requests, 7,325 hits, 4,615 misses, 4,376 evictions, 17,656,872,960 fetched bytes, and zero
cache-to-claim copies. All twelve process-absence checks passed, every native lifetime balanced,
conditioning clocks remained zero, full clocks were positive, and the three attention children
closed exactly to item 71's attention parent on every sample. This is attribution only and makes no
performance-win claim.
