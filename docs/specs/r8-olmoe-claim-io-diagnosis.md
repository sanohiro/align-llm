# R8 OLMoE claim-I/O diagnosis

Status: active, 2026-09-05

Roadmap owner: item 64, `R8-OLMOE-CLAIM-IO-DIAGNOSIS`

## 1. Decision owned

Item 63's live-width phase-A candidate missed its post-review full-request gate and was removed.
The shipped item-62 request therefore remains the immutable performance baseline: walls
`[18059864416,18927732709,20639199375,19605385750]` ns, median 19,266,559,229 ns, and a
50,000-ppm materiality floor of 963,327,962 ns. Its next-largest unresolved shipped bucket is the
complete remaining-decode claim-I/O clock at a 3,609,378,007-ns median.

That name does not identify one operation. In partial-LRU mode the clock contains file `pread` on
cache misses, block-transient to claim-window copies, claim-window to cache copies, cache-hit to
claim-window copies, lookup/eviction metadata, builders, and timing overhead. A five-second
directional stack sample of an unchanged full request observed 526 main-thread samples in
`pread` and 374 in `align_ggml_window_copy`; it is not operation timing. The pinned AlignPack has
1,024 expert blocks in two payload sizes, every block has zero padding, and each block's three
claims form one contiguous pack range. Splitting those claims into three reads therefore cannot be
assumed to reduce bytes.

This capability partitions the existing clock without moving work. It selects the largest exact
sub-bucket only when its four-sample median reaches the inherited 963,327,962-ns floor. The result
authorizes a successor implementation ledger with its own unchanged item-62 full-request baseline
and 50,000-ppm shipping gate; it does not itself authorize an optimization or claim a speedup.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-CLAIM-IO-DIAGNOSIS`; `scripts/run-olmoe-claim-io-diagnosis`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | the next R8 implementation decision after item 63's removal |
| Fixed request | inherit item 62 exactly: task/system/user prompt, OLMoE model, AlignPack, geometry, 975,175,680-byte partial-LRU budget, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | four sequential fresh-process pairs; each maximum-2 result is the exact prefix of the following maximum-128 result; zero processes matching both pinned llama-server and model paths before, between, and after each pair |
| Existing parent clock | `remaining_decode_claim_pread_ns`; retain its start, stop, successful-step commit point, and meaning exactly |
| `FILE_PREAD` | sum only the monotonic intervals around each successful `file.pread` call made by claim staging; exclude the following scatter copy |
| `BLOCK_TO_CLAIM_COPY` | sum only `window_put` intervals that copy a successfully read block-transient piece into its claim-window destination |
| `CLAIM_TO_CACHE_COPY` | sum only `window_put` intervals that admit a cache-miss claim-window plane into its cache slot |
| `CACHE_TO_CLAIM_COPY` | sum only `window_put` intervals that serve a cache hit from its slot into the claim window |
| `OTHER_CLAIM_IO` | exact parent-clock remainder after the four disjoint clocks above; includes lookup, victim scan, metadata writes, temporary column construction, loop/control work, and timing overhead; it is never measured by an overlapping timer |
| Shared counters | add the five nonnegative totals above and five matching `remaining_decode_*` totals to the invocation-owned outcome; a layer result carries the same five values; no production renderer exposes them |
| Commit semantics | broad totals may include attempted work; remaining-decode totals add the exact broad-counter delta only after one step beyond the first completes successfully, at the existing parent-clock commit point; maximum 2 therefore reports five zeros |
| Exact accounting | on every successful full helper record, the five remaining-decode subclocks sum exactly to `remaining_decode_claim_pread_ns`; each is nonnegative and no subclock exceeds the parent |
| Qualification helper | add `olmoe_claim_io_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; maximum is only 2 or 128; preserve item 62's helper record and add one exact `claim_io` object |
| Helper detail | `claim_io` has exact keys `total_ns`, `file_pread_ns`, `block_to_claim_copy_ns`, `claim_to_cache_copy_ns`, `cache_to_claim_copy_ns`, and `other_ns` |
| Immutable baseline | item 62 walls `[18059864416,18927732709,20639199375,19605385750]` ns and median 19,266,559,229 ns; item 59's shipped claim-I/O median 3,609,378,007 ns; never recompute either from instrumented samples |
| Materiality/decision | floor is 963,327,962 ns; take four-sample integer medians in the order `FILE_PREAD`, `BLOCK_TO_CLAIM_COPY`, `CLAIM_TO_CACHE_COPY`, `CACHE_TO_CLAIM_COPY`, `OTHER_CLAIM_IO`; choose the largest with ties in that order; below floor yields `NO_MATERIAL_BUCKET`, otherwise `MEASURED_BUCKET_ELIGIBLE` |
| Result | one exact-key schema-1 `R8_OLMOE_CLAIM_IO_DIAGNOSIS` JSON document with the immutable baseline, exact instrumented samples, bucket values/medians, selected bucket/share, and decision; stdout has no complete document on failure |
| Existing behavior | read order/count/bytes, LRU keys/hits/misses/evictions, claim/cache/window bytes, graph construction/order, provider schema, tokens, output, and native lifetimes are byte- and meaning-unchanged |
| Inputs/identity | independently pin item 62's full transitive Python runner chain, inherited workload and baselines, complete helper/source chain, model, pack, geometry, server, Align revision/compiler, ggml libraries and consumed headers, C compiler/version, task, prompt, exact token chain, built helper/shim, clean align-llm head, and item 62's host fingerprint |
| Validation order | arguments/prerequisites; scrubbed environment/linker search; fixed host, clean head, process absence, imported/external identities and headers; exact-source build; four conditioned records; schema/equations/output/cache/lifetime/repeatability; aggregate/decision; final identities/head; cleanup-inclusive ceiling; publication |
| Failure | nonzero and no complete document for invalid arguments, identity/host/source/process drift, malformed/negative/overlapping or inexact clocks, output/cache/lifetime drift, child failure, source mutation, cleanup failure, or ceiling excess; missing prerequisites retain one declared N/A path |
| Ownership/allocation | counters are invocation-owned scalars; timing adds no native owner or allocation; helper/runner/temp state remains invocation-local |
| Persisted/cache identity | N/A: no production schema, pack, model, cache format/policy, or persisted result changes; qualification stdout is not persisted by the runner |
| Cost ceiling | one monotonic 8-minute ceiling covers helper/shim build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; every child retains a narrower bound |
| Acceptance evidence | author consistency pass; `make fmt`; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation; focused inherited self-test; one complete four-repeat real diagnosis; `git diff --check`; one comprehensive review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-CLAIM-IO-DIAGNOSIS -- scripts/run-olmoe-claim-io-diagnosis --self-test` |

The capability makes one fixed-request, fixed-host attribution, not a speedup claim. Cross-host,
GPU, throughput, arbitrary-task, cache-policy, public-provider, persisted-state, syscall-throughput,
and individual-kernel claims are N/A.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| File read | start immediately before each existing `pread` | add only returned-call wall | existing pack fault wins | no later copy on failure | existing file/temp owners | source placement plus full positive clock |
| Block scatter | start around each existing block-piece `window_put` | add copy wall only | existing copy fault wins | no later role copy after error | borrows only | source placement and parent equation |
| Cache admission | time each existing claim-to-cache `window_put` | add cache-write wall | existing fault/eviction order unchanged | unread miss is never admitted | existing cache window | cache counters exact in real repeats |
| Cache hit | time each existing cache-to-claim `window_put` | add hit-copy wall | existing fault wins | no graph consumes partial claims | existing windows | fixed hit/miss/byte counts |
| Layer remainder | snapshot parent and four direct totals | subtract only after parent stops | negative remainder rejects helper | failed layer is not committed | no owner | synthetic overlap/negative mutants |
| Step commit | snapshot five broad totals before `decode_pass` | add deltas after successful non-first step | partial/first steps add zero | EOG/maximum unchanged | locals die per step | maximum-2 zero, full exact sum |
| Helper | item 62 preparation plus `claim_io` | one exact inherited record | bad arguments/schema/equation fail before print | N/A | invocation drops state | pinned build and schema self-test |
| Repetition | fixed host/process absence; fresh short/full children | exact prefix/output four times | any drift aborts without result | no partial sample/result | inherited signal/deadline cleanup | twelve absence checks and repeatability |
| Aggregate | immutable baseline/floor and four exact records | deterministic medians/selection | boolean/key/arithmetic/baseline drift rejects | no partial aggregate | N/A | tie, below-floor, at-floor vectors |
| Identity | pin complete import/source/tool/external chain | final values unchanged | any digest/value/head drift fails | missing prerequisite emits N/A | restore root executable | transitive-runner and source mutants |
| Signal/deadline | install before real work | N/A | interruption/timeout exits nonzero | no complete JSON | stop child and restore temp/build state | inherited timeout/restoration tests |

Generic monomorphization, move/source-nulling, concurrent calls, external-server ownership,
persisted migration, and asynchronous races are N/A. Decode remains synchronous and the
instrument adds no borrow that outlives its current layer or step.

## 4. Implementation and verification map

1. Add disjoint clocks around the four existing operation classes and compute the exact layer
   remainder without moving an operation.
2. Aggregate broad totals and successful remaining-step deltas at the existing commit points.
3. Add a thin helper and bounded runner which inherit item 62 behavior, independently pin the full
   consumed chain, and own exact schemas, equations, medians, selection, identity, and cleanup.
4. Run narrow owners and one clean-head four-repeat diagnosis. Record the selected successor here,
   in the roadmap, and in `HANDOFF.md`.
5. Complete one comprehensive review, consolidate valid findings, rerun affected evidence and
   exact-head preflight, publish, merge, and continue to the selected implementation capability.

No `make ci`, installed platform profile, 40-prompt corpus, stress suite, cache replay, or unrelated
benchmark is selected. Counters, helper, validator, and one decision form the smallest useful
end-to-end diagnostic capability.

## 5. Author consistency pass

The ledger and matrix agree that all five subclocks are disjoint parts of the unchanged parent,
that only successfully completed remaining steps reach the selected result, and that item 62's
baseline and floor remain immutable. No text relabels a stack sample as timing, changes cache/read
behavior, or authorizes a production optimization. Every construction, success, failure, early
exit, cleanup, identity, and publication boundary has a named owner and exact evidence.
