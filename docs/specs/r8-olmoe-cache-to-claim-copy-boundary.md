# R8 OLMoE cache-to-claim copy boundary

Status: active; implementation complete, fixed qualification pending, 2026-09-05

Roadmap owner: item 66, `R8-OLMOE-CACHE-TO-CLAIM-COPY-BOUNDARY`

## 1. Decision owned

Item 64 measured the fixed OLMoE request's cache-hit copies from the invocation-local LRU slots
into the compact claim window at a 1,072,229,252-nanosecond median. That is above item 62's
unchanged 963,327,962-nanosecond materiality floor. Each hit currently performs three host copies;
phase B then wraps those copied role regions as three contiguous expert tensors whose depth is the
routed union.

The existing cache already holds every selected key before phase B. Its slot layout is fixed-stride:
one slot contains gate, up, and down consecutively, and the next slot begins `key_bytes` later.
Pinned ggml 0.9.5 represents a tensor's expert dimension with `nb[2]`, and its CPU
`mul_mat_id` kernel selects expert `i` at `src0->data + i * nb[2]`. The candidate therefore exposes
each role as a checked 3-D tensor with `nb[2] = key_bytes` and changes phase-B ids from compact-union
indices to the corresponding resident cache-slot indices. It removes hit copies without changing
cache contents, policy, budget, routing, arithmetic order, or output.

Item 62's full-helper walls `[18059864416,18927732709,20639199375,19605385750]` ns and
19,266,559,229-ns integer median remain immutable. The candidate ships only when four fresh-process
fixed requests preserve every inherited semantic/resource boundary and have a median at or below
18,303,231,267 ns, a gain of at least 963,327,962 ns / 50,000 ppm. Otherwise all production and
production-owner changes are removed before publication.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-CACHE-TO-CLAIM-COPY-BOUNDARY`; production owners are `src/moe_decode_step.align`, `src/moe_model_forward.align`, `src/ggml_ffi.align`, `scripts/ggml_shim.c`, and `scripts/ggml_shim_stub.c`; qualification owners are `src/olmoe_cache_to_claim_gate.align` and `scripts/run-olmoe-cache-to-claim-copy-boundary` |
| Consumer selection | only OLMoE provider generation with a valid `dense+lru:BUDGET` cache may select direct cache tensors. Diagnostic CLI execution, reference/transcript modes, non-cache residency, and an ineligible cache layout retain compact claim tensors and copies. |
| Fixed request | inherit item 62 exactly: model, AlignPack, geometry, 975,175,680-byte cache budget, fixed task/prompt, temperature 300,000 micros, seed 5, maximum 128, EOG behavior, exact 87-token id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Immutable baseline | item 62's four walls and 19,266,559,229-ns median above; candidate samples never replace it |
| Shipping gate | 50,000 ppm rounded up is 963,327,962 ns; candidate ceiling is 18,303,231,267 ns; `MET` iff the four-sample candidate wall median is at or below the ceiling |
| Cache layout | preserve the existing LRU key, 4,079,616-byte maximum slot stride, 239-slot / 975,028,224-byte fixed-request capacity, per-layer logical role sizes, role order, unused slot tails, demand order, recency, victim rule, counters, and invocation lifetime |
| Direct eligibility | provider generation, cache enabled, cache base aligned to the linked backend requirement, `key_bytes` and every layer's gate/up/down start aligned, positive role sizes, and `slot_count >= routing.count` for the current layer. Any static layout failure keeps the old copy path; a layer wider than capacity also keeps the old copy path. |
| Hit/miss staging | on an eligible layer, a hit updates cache state but does not touch the claim window. A miss retains the existing read/scatter into the claim window, admission copy, victim selection, metadata update, and counters. Staging completes before ids or tensors are constructed. |
| Selected-key residency | after eligible staging, every routed key must resolve to one slot in `[0, slot_count)`; an impossible missing/out-of-range mapping fails as existing `R5E_CARRY` before graph construction. Capacity at least `routing.count`, ascending demand, and LRU refresh ensure no already-processed selected key is the oldest resident at a later eviction. |
| Phase-B ids | global `topk` remains unchanged for probability gather and published routing. The `mul_mat_id` input is rebuilt in the same token/slot order by mapping each existing compact-union id through `routing.routed` and the layer/key metadata to its resident cache-slot id. Each id is checked before its four-byte encoding. |
| Strided tensor ABI | add `align_ggml_slot_new_strided_tensor_3d(ctx, slots, out, kind, ne0, ne1, ne2, slice_stride)` and safe `ggml_ffi.slot_new_strided_tensor_3d`. It creates one supported-type 3-D tensor, keeps the contiguous row stride, sets expert stride `nb[2]` to `slice_stride`, and stores it in `out`. No pointer, byte offset, allocation, or ownership crosses the Align API. |
| Shim validation order | valid context; positive dimensions/stride; supported left-operand type; checked row and plane byte arithmetic; `slice_stride >= plane_bytes`; checked reachable span `(ne2 - 1) * slice_stride + plane_bytes`; tensor construction; slot store. Invalid type is existing `R5_TYPE_UNSUPPORTED`; invalid/overflowing shape or stride is existing `R5_SHAPE`; slot and placement failures keep existing `R5_SLOT`, `R5_ALIGNMENT`, or `R5_BOUNDS`. |
| Tensor placement | the three role tensors have `{claim_ne0, claim_ne1, slot_count}` and are placed at their role start inside the existing cache storage. Their reachable bytes are exactly `(slot_count - 1) * key_bytes + role_bytes`; role start plus reachable bytes must fit cache capacity. Pointer identity is checked relative to the cache base. |
| Buffer ownership | for an eligible provider invocation, the existing single resident host wrap covers the already contiguous dense-plus-cache allocation instead of only its dense prefix. It remains one run-scope wrap, is freed after every graph and before the Align buffer dies, and does not add an allocation or native handle. If the combined wrap is unavailable, construction retries the original dense-only wrap and uses the old copy path. |
| Claim window | allocation, alignment, miss staging, and non-direct consumers remain unchanged. Eligible phase B neither wraps nor reads it after staging; no hit bytes are required there. |
| Existing public result | provider response text and errors, token ids, sampling, cache schema/counters, routing, and native lifetime schema remain byte-compatible. Diagnostic CLI schemas and `GenerationParts` types do not change. The existing claim-I/O detail truthfully reports zero cache-to-claim copy time only when direct tensors were selected. |
| Persisted/cache identity | N/A: no pack, geometry, response, persisted cache, migration, cache key/content, or schema version changes |
| Validation order | existing request/pack/geometry/budget/allocation/backend checks; direct-layout eligibility and resident wrap; phase A; routing; copy or direct staging; selected-slot validation; tensor construction/placement; phase B; inherited semantic/cache/lifetime checks; four-repeat aggregate; final identity/head checks; cleanup; publication |
| Failure/early exit | pre-staging failures leave cache unchanged as before; miss read/copy failure cannot admit; selected-slot failure builds no phase-B graph; tensor failure uses converged layer/run teardown; no partial qualification result is printed on malformed input, identity drift, process contamination, timeout, cleanup failure, or ceiling excess |
| Allocation/resource | exact cache, dense, claim, metadata, activation, and temporary allocations are unchanged. Direct tensors are context metadata over existing cache bytes; `mul_mat_id` scratch scales from routed depth to 239 fixed-request slots and remains included in measured activation/elapsed evidence. |
| Prerequisites | item 64's measured bucket; item 65's negative mmap decision; pinned Align `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`; pinned ggml 0.9.5 headers/libraries whose public tensor strides and CPU `mul_mat_id` consume `nb[2]`; no Align request or hypothetical language surface |
| Cost ceiling | one monotonic 8-minute qualification ceiling covers exact-source build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; individual children retain narrower bounds |
| Acceptance evidence | author consistency pass; shared real/stub shim contract check; strided constructor exact-span/type/shape/stride/slot/placement vectors; cache-slot id and selected-residency regressions; direct hit/miss/eviction and fallback provider cases; `make check`; `make runtime-provider-smoke`; `make layer-forward-smoke`; `make fmt`; Python compilation and model-free runner self-test; one clean-head four-repeat qualification; `git diff --check`; one comprehensive review; exact-head preflight with the focused self-test |

The capability makes one fixed model/request/host latency claim only. Cross-host, GPU, throughput,
arbitrary-task, other-cache-budget, page-cache, and whole-R8 claims are N/A.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Static eligibility | cache/dense slices and backend alignment are already known | every role start and slot stride is aligned | nonpositive/misaligned layout selects old path | no direct tensor exists | N/A | eligible and misaligned synthetic layouts |
| Combined resident wrap | wrap existing dense-plus-cache allocation once | dense and cache placements share one handle | combined refusal retries dense-only wrap and disables direct path | no graph yet | existing one-wrap teardown | forced refusal plus wrap balance |
| Hit | metadata resolves resident slot | recency/counters update; no claim copy | invalid metadata is caught before ids/graph | no partial graph | ordinary cache storage | repeated key, unchanged claim sentinel, zero copy clock |
| Miss/admission | existing block scatter precedes victim choice | exact bytes copied into selected slot | read/copy failure cannot evict or admit | failed key never becomes a graph id | unchanged buffers | miss contents and failure-before-admission |
| Eviction | current LRU scan and deterministic tie-break | all selected keys resident after final demand | impossible selected-slot absence is `R5E_CARRY` | phase B not built | unchanged metadata | capacity equal to routed width with selected-key eviction/reload |
| Id remap | validated `routing.compact` indexes `routing.routed` | token/slot order maps to exact cache slots | compact, key, or slot out of range fails before encoding | no partial id tensor | temporary array/buffer drops | non-identity slot permutation plus refusal vectors |
| Real strided tensor | checked ggml type/shape/stride; one tensor metadata object | `nb[2] = key_bytes`, exact reachable span | type, shape, overflow, slot, alignment, bounds preserve existing codes | no graph consumes failed tensor | weight context teardown | direct shim vectors and fixed Q4_K/Q6_K roles |
| Stub strided tensor | same semantic validation in ggml-free engine | hosted `mul_mat_id` reads each selected plane at slice stride | same malformed classes refuse | graph not expanded | stub pools reset when idle | synthetic exact graph and shared contract check |
| Phase B | all selected slots stable until graph teardown | arithmetic/order/output equal compact claim graph | compute failure uses existing code | partial layer publishes no row | converged graph teardown | old/direct normalized equality and fixed output hash |
| Fallback | any ineligible layout, reference/diagnostic mode, or combined-wrap refusal | existing hit copies and compact ids/tensors execute byte-for-byte | existing failures/counters | unchanged | unchanged | diagnostic golden and forced fallback |
| Repetition/gate | fixed clean host and pinned identities | four exact conditioned pairs; median meets ceiling | drift/timeout/excess aborts without result | no partial result | signal/deadline cleanup | twelve isolation checks, exact cache/output/lifetime, at/above gate vectors |

Network connection state, asynchronous execution, persistence, source moves, and generic
monomorphization are N/A. The only new native representation is context-owned tensor metadata over
an existing invocation-owned cache buffer.

## 4. Implementation and verification map

1. Add and directly test the checked strided 3-D constructor in both shims and `ggml_ffi`.
2. Add cache-layout eligibility, combined-wrap fallback, selected-slot remapping, and direct cache
   tensor placement while leaving diagnostic/reference and non-cache execution on the old path.
3. Extend the narrow synthetic owners for exact non-identity slot selection, hit/miss/eviction,
   fallback, malformed stride/span, and teardown; preserve all existing goldens.
4. Add the item-66 helper and bounded runner by inheriting item 64's fixed request while pinning the
   complete transitive source/runner/toolchain chain and immutable item-62 gate.
5. Run narrow owners and the clean-head fixed qualification. Record `MET` or `NOT_MET`; on
   `NOT_MET`, remove the production intervention and its production-owner changes before review.
6. Complete one comprehensive review, consolidate valid findings, rerun affected evidence and the
   exact-head preflight, publish, merge, and continue.

No `make ci`, installed platform profile, 40-prompt corpus, stress suite, or unrelated benchmark is
selected.

## 5. Author consistency pass

The ledger and matrix use one ordering: existing validation, static direct eligibility, one
run-scope wrap, phase A/routing, complete cache staging, cache-slot id validation, strided tensor
placement, phase B, and converged teardown. Direct mode changes only where hit bytes are read and
which equivalent expert indices phase B consumes. Global routing and cache policy remain
unchanged; all selected slots are resident and stable before the graph exists. The new shim symbol
owns byte-stride arithmetic and returns existing fault classes before a ggml assertion. The cache
budget and every allocation remain unchanged. The immutable baseline, 963,327,962-nanosecond floor,
and 18,303,231,267-nanosecond ceiling are fixed before production code changes.

## 6. Implementation checkpoint

The implementation adds the checked real/stub constructor, makes the stub kernel consume the
stored expert stride, validates static cache layout before selecting direct mode, wraps the
existing dense-plus-cache allocation once, skips hit copies, re-resolves every selected key to a
cache slot after complete staging, and places the three role tensors over the cache. A refused
combined wrap retries the original dense-only wrap and compact-copy graph.

`make check`, `make runtime-provider-smoke`, and `make layer-forward-smoke` pass with the pinned
toolchain environment. The runtime owner now covers constructor success, reachable span, null
context, zero shape, unsupported type, short stride, row overflow, slot range, direct hosted OLMoE
generation, and injected combined-wrap fallback. A real ggml fixed-model conditioning request also
completed with balanced native resources. The four-repeat shipping qualification remains pending.
