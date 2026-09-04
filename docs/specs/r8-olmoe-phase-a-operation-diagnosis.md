# R8 OLMoE phase-A operation diagnosis

Status: designed; implementation pending, 2026-09-05

Roadmap owner: item 71, `R8-OLMOE-PHASE-A-OPERATION-DIAGNOSIS`

## 1. Decision owned

Item 70 measured the shipped fixed request's remaining-decode phase-A graph at a
4,620,020,794-nanosecond median, well above the immutable 871,174,011-nanosecond materiality
floor. That clock covers the complete 37-row graph: attention through the residual value, then FFN
normalization, router scoring, softmax, and argsort. It does not identify an individual operation.
Item 63 already established that replacing the fixed attention width with the live width is not a
shippable intervention, so this capability does not repeat it.

This capability adds an opt-in qualification path that executes the already-built and already-
allocated phase-A graph as two ordered graph slices. The attention slice ends inclusively at decode
table row 31, `ffn_inp`; the router slice contains rows 32 through 36 and ends at
`ffn_moe_argsort`. Both slices contain pointers to the original tensors and use the original tensor
buffers. The two directly measured `ggml_backend_graph_compute` walls distinguish those operation
classes without treating whole-graph time, profiler samples, or a residual subtraction as
individual-operation timing.

The diagnostic path must reproduce the fixed output, routing/cache accounting, and ownership
evidence. Its largest class may select a successor only when its median reaches the inherited
floor. A material router result identifies the five-row router chain as an implementation seam. A
material attention result remains too broad for implementation and selects a narrower attention
diagnosis. This capability makes no speedup claim and does not close R8.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-PHASE-A-OPERATION-DIAGNOSIS`; `scripts/run-olmoe-phase-a-operation-diagnosis`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | the next R8 implementation ledger or narrower attention diagnosis after item 70 selected `ROUTING_PHASE_A` |
| Fixed request | item 70's inherited item-68 request: identical task/system/user prompt, OLMoE model, AlignPack, geometry, 975,175,680-byte partial-LRU budget, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | four sequential fresh-process pairs; maximum 2 is the exact prefix of maximum 128; zero processes matching both pinned llama-server and model paths before, between, and after each pair |
| Graph boundary | decode phase A retains all 37 rows, fixed request width, operands, output marks, allocation, and topological order. The inclusive split anchor is row 31 / `ffn_inp`; prefix rows 0-31 are `ATTENTION_AND_RESIDUAL`, suffix rows 32-36 are `ROUTER` |
| Slice ABI | add a bounded shim/FFI constructor taking a graph-owning context, source graph, slot store, boundary slot, and prefix/suffix selector. It finds the boundary tensor exactly once among source nodes, rejects a null/empty/end boundary or invalid selector, creates a graph containing the corresponding contiguous node pointer range, and owns no tensor or backend buffer |
| Slice lifetime | one diagnostic context owns both slice graph structures. The source graph, source tensor contexts, slot store, allocator, and backend buffers outlive both slice computes. The diagnostic context is freed before the existing tensor contexts and adds no independent allocator |
| Normal execution | all existing public generation and diagnostic entry points pass `phase_a_operation_diagnosis = false` and execute the original single phase-A graph compute. Only the new qualification helper passes `true` |
| Diagnostic execution | after the full source graph is allocated, compute the prefix once and then the suffix once. Do not compute the full graph as a third control. A failure in either call uses the existing `R5_COMPUTE` family with an attention/router stage label and publishes no successful step |
| Direct clocks | `phase_a_attention_ns` is the sum of prefix `graph_compute` walls over routed layers; `phase_a_router_ns` is the sum of suffix walls. In diagnostic mode their exact sum is the existing routing-compute total. They are graph-slice operation-class walls, not kernel or individual-node attribution |
| Remaining-decode commit | add corresponding remaining-decode totals using the existing successful-step-after-first snapshot/commit. Maximum 2 reports zero for both; maximum 128 reports positive values whose sum equals `remaining_decode_routing_compute_ns` |
| Qualification helper | new `olmoe_phase_a_operation_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; preserve the predecessor helper record and add exact object `phase_a_operations` with `total_ns`, `attention_and_residual_ns`, and `router_ns` |
| Exact accounting | helper requires nonnegative signed 64-bit integers, `attention_and_residual_ns + router_ns == total_ns`, and `total_ns == decode_compute.routing_ns`; conditioning values are all zero and full values all positive |
| Shipped-state evidence | preserve full-width phase A, item 58's K/V staging, item 68's exact plane comparison and cache-backed phase B, exact 11,940 requests / 7,325 hits / 4,615 misses / 4,376 evictions / 17,656,872,960 fetched bytes, zero cache-to-claim copies, output, and balanced native lifetimes. Diagnostic context counts are validated from the produced pair rather than mistaken for the non-diagnostic historical count |
| Immutable baseline | item 68 walls `[17714825083,16684315166,17132135334,21189618042]` ns and median 17,423,480,208 ns; item 70's phase-A median is attribution context only and is not a new baseline |
| Materiality floor | 50,000 ppm of the immutable median, rounded up: 871,174,011 ns per full request |
| Selection | take four-sample integer medians for `ATTENTION_AND_RESIDUAL` then `ROUTER`, choose the larger with the declared order breaking ties, and record its share of the split phase-A median |
| Decision | below the floor yields `NO_MATERIAL_OPERATION_CLASS`; material `ROUTER` yields `MEASURED_ROUTER_SEAM_ELIGIBLE`; material `ATTENTION_AND_RESIDUAL` yields `ATTENTION_SUBDIAGNOSIS_REQUIRED`. The last case cannot authorize another live-width intervention or any broad attention rewrite |
| Result | one exact-key schema-1 `R8_OLMOE_PHASE_A_OPERATION_DIAGNOSIS` JSON document on stdout and one concise stderr summary; no complete document on failure |
| Inputs/identity | independently pin the complete inherited runner/helper/source chain plus the new runner/helper, changed Align sources, shim/stub/build script, model, pack, geometry, server, Align revision/compiler, ggml libraries and consumed headers, C compiler/version, task, prompt, exact token chain, built helper/shim, clean align-llm head, and item-70 host fingerprint |
| Validation order | arguments/prerequisites; imported constants and source identities; scrubbed environment/linker search; fixed host, clean head, process absence, external identities; exact-source build; four conditioned records; helper schema/accounting/output/cache/lifetime/repeatability; aggregate/decision; final identities/head; cleanup-inclusive ceiling; publication |
| Failure | nonzero and no complete document for invalid arguments, slice construction/boundary failure, graph compute failure, malformed/overlapping clocks, equation/output/cache/lifetime/source/host/process drift, child failure, mutation, cleanup failure, or ceiling excess; missing prerequisites retain one declared N/A line |
| Ownership/allocation | production adds only scalar counters initialized to zero. Diagnostic calls add one context per routed layer and two context-owned graph structures; every path converges on the existing layer teardown. Runner/helper/temp state is invocation-local |
| Persisted/cache identity | N/A: no provider, cache, model, pack, task, or persisted-result schema changes; qualification stdout is not persisted by the runner |
| Cost ceiling | one monotonic 8-minute ceiling covers helper/shim build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; each child retains a narrower bound |
| Acceptance evidence | author ledger-to-prose consistency pass; shim slice unit coverage including malformed anchors; `make fmt`; pinned helper build; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation; inherited and focused self-tests; one clean-head fixed-host four-repeat diagnosis; `git diff --check`; one comprehensive review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-PHASE-A-OPERATION-DIAGNOSIS -- scripts/run-olmoe-phase-a-operation-diagnosis --self-test` |

Cross-host, GPU, throughput, arbitrary-task, cache-policy, persistent-state, public-provider,
per-kernel, per-node, and performance-win claims are N/A. Splitting a graph adds one backend
dispatch per routed layer in the qualification process, so the two class walls describe that
diagnostic execution boundary and are not represented as a subtraction from item 70's whole-graph
samples. Any later implementation still needs its own unchanged full-request shipping gate.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Shim slice | validate handles, selector, source count, and unique interior anchor | copy one contiguous range of source tensor pointers in order | null, missing/duplicate/end anchor, bad selector, or allocation returns null | no compute | context owns only graph metadata | direct prefix/suffix node-count/order test plus malformed cases |
| Routed layer, normal | diagnostic flag false | original full graph computed once; new clocks stay zero | existing status/detail unchanged | failed graph does not commit a step | existing four contexts/allocators | old layer/runtime smoke and byte-stable normal helper |
| Routed layer, diagnostic | allocate full graph first, then one extra context and two slices | prefix then suffix, exact output and routing | either status maps to labelled `R5_COMPUTE`; missing slice maps to `R5_GGML_INIT` | second compute skipped after prefix failure | free diagnostic context before graph/tensor contexts | forced construction/compute failure, lifetime balance, real exact output |
| Broad counters | layer returns attention/router walls | their sum becomes the diagnostic phase-A total | negative/overflow impossible in admitted bounded run; helper rejects inconsistency | failed layer never reaches successful-step total | scalars only | zero initialization and full equation |
| Step commit | snapshot both broad counters with existing compute clocks | remaining steps add exact deltas | partial step rolls back with existing outcome semantics | first decode and EOG/maximum exits add zero | locals die per step | maximum-2 zeros, full positives/equality |
| Helper | call only the new opt-in generation entry | preserve inherited record and append exact object | bad arguments/output/equation exits before print | N/A | invocation drops state | pinned build, schema and normal-path regression |
| Repetition | fixed host/process absence; fresh short/full children | exact prefix/output/cache four times | drift aborts without aggregate | no partial sample/result | inherited signal/deadline cleanup | twelve absence checks and repeatability |
| Aggregate | four exact samples and immutable floor | deterministic medians/share/decision | sample count, boolean, negative, arithmetic, baseline, or identity drift rejects | no partial aggregate | N/A | tie, below-floor, router-at-floor, attention-at-floor vectors |
| Identity/publication | pin all transitive inputs before measurement | final hashes/head unchanged; one document | mutation or multiple/malformed output rejects | missing prerequisite emits N/A | restore generated root binary | mutation/head mismatch and real recheck |
| Signal/deadline | handlers installed before real work | N/A | interruption/timeout exits nonzero | no complete JSON | stop child, wait, then kill if required | inherited forced-timeout/restoration tests |

Generic monomorphization, move/source-nulling, concurrent calls, external server ownership,
persisted migration, and production races are N/A. Slice graphs borrow source tensor pointers only
within the synchronous layer frame and cannot escape their owning diagnostic context.

## 4. Implementation and verification map

1. Add the bounded graph-partition shim/FFI surface and direct shim regression before using it from
   the decode schedule.
2. Thread one internal diagnostic boolean from a new qualification-only generation entry to routed
   decode layers. Add direct class clocks and commit their remaining-decode deltas at the existing
   successful-step boundary; leave every existing entry point on the single-graph path.
3. Add the thin helper and runner, pin the full consumed chain, and own exact schema, class
   accounting, medians, selection, cleanup, and mutation regressions.
4. Run narrow owners and one real four-repeat diagnosis. Record either the router implementation
   seam, a narrower attention diagnosis, or no material successor here, in the roadmap, and in
   `HANDOFF.md`.
5. Complete one comprehensive review, consolidate valid findings, rerun affected evidence and
   exact-head preflight, publish, merge, and continue to the selected successor.

No `make ci`, installed platform profile, coding portfolio, 40-prompt corpus, stress suite, cache
replay, live-width retry, or unrelated benchmark is selected. The producer clocks and their exact
qualification consumer form one consumer-complete diagnostic capability.

## 5. Author consistency pass

The ledger and matrix agree that only the opt-in helper splits execution, the normal provider keeps
one graph compute, the split anchor is the residual output rather than a guessed node number, both
classes are directly timed graph boundaries, and their sum—not a historical subtraction—owns the
diagnostic phase-A total. A material attention class explicitly requires further diagnosis, while
only a material router class identifies a sufficiently narrow implementation seam. Neither result
reopens item 63 or claims a speedup.
