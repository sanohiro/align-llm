# R8 OLMoE exact-safe decode boundaries

Status: implemented; decision `MET`, 2026-09-05

Roadmap owner: item 68, `R8-OLMOE-EXACT-SAFE-DECODE-BOUNDARIES`

## 1. Decision owned

Item 67 combined three independently negative decode reductions, but its first full request changed
five routed cache decisions. The execution order attributes that change to item 63's live-width
phase A: routing completes before either item 61's plane comparison or item 66's cache-backed expert
source runs. Items 61 and 66 each preserved the fixed output and exact cache accounting in their
own four-repeat qualifications. This capability therefore evaluates only those two exact-safe,
already-reviewed interventions together; it adds no third optimization.

Item 62's walls `[18059864416,18927732709,20639199375,19605385750]` ns and
19,266,559,229-ns median remain the immutable baseline. The 50,000-ppm floor is 963,327,962 ns and
the candidate ceiling is 18,303,231,267 ns. Four conditioned fresh-process repetitions decide the
candidate. `MET` ships both interventions; `NOT_MET` or any semantic drift removes all production
and production-owner changes before publication.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-EXACT-SAFE-DECODE-BOUNDARIES`; production owners are `src/moe_decode_step.align`, `src/moe_model_forward.align`, `src/ggml_ffi.align`, both ggml shims, and the shim build; direct owners are the layer-forward and runtime-provider smokes; the thin helper and bounded runner own qualification |
| Consumer | item 62's fixed OLMoE provider-generation request, after item 67 isolated live-width routing as semantically unsafe |
| Fixed request | inherit item 62 exactly: pinned model, pack, geometry, prompt, 975,175,680-byte partial-LRU budget, temperature 300,000 micros, seed 5, maximum 128, terminal EOG, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | four fresh-process maximum-2/full pairs; each short output is the exact prefix of its full output; zero matching llama-server/model processes before, between, and after each pair |
| Plane intervention | restore item 61's final reviewed form: compare host-visible concat tensors through validated slots, exact K bytes, and an unaligned-safe AArch64 4-by-4 V success path with the original scalar traversal on mismatch; non-AArch64 remains scalar |
| Cache intervention | restore item 66's final reviewed form: wrap dense plus cache once for eligible provider generation, skip hit copies, re-resolve selected keys to stable cache slots, and place fixed-stride expert tensors over cache bytes; diagnostics, ineligible layouts, and wrap refusal retain compact claims |
| Excluded intervention | item 63 live-width phase A is absent: decode graphs retain the shipped full `KV_WIDTH`, mask, PAD nodes, graph arithmetic, and routed ids |
| Interaction invariant | phase A and routing remain shipped; plane verification completes before cache staging; all selected slots stabilize before phase B construction; neither intervention changes the other's input bytes, mutation order, or owner |
| Native ABI | reuse item 61's validated byte/slot compare calls and item 66's fixed-stride tensor constructor; validate type, offset, stride, span, alignment and host visibility before native access; no ggml struct crosses FFI |
| Numerical/cache behavior | graph arithmetic, plane bytes, expert bytes, routing ids, logits, sampling, token ids, output, LRU keys/recency/victims/hits/misses/evictions/fetched bytes, and cache content remain exact |
| Ownership/allocation | existing plane, dense allocation, cache, claim, metadata and activation owners remain; borrowed comparisons and tensors add no allocation; one run-scope resident wrap covers dense plus cache and is freed before its Align buffer |
| Fallback/failure | original compact path and fault order remain; a validation, graph, cache, identity, isolation, timeout, or cleanup failure emits no complete result and publishes no partial layer/cache admission |
| Existing results | provider and diagnostic schemas remain byte-shaped and meaning-compatible; clocks retain their existing boundaries |
| Qualification | `olmoe_exact_safe_decode_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5` delegates to the detailed helper; `scripts/run-olmoe-exact-safe-decode-boundaries` owns model-free self-tests and one opt-in real run |
| Candidate evidence | four full walls, plane-roundtrip clocks, and cache-to-claim clocks; every full cache-copy clock is zero and every request retains 11,940 requests, 7,325 hits, 4,615 misses, 4,376 evictions, and 17,656,872,960 fetched bytes |
| Result | one exact-key schema-1 `R8_OLMOE_EXACT_SAFE_DECODE_BOUNDARIES` document after complete validation; component clocks are diagnostic and only the full-wall median decides `MET`/`NOT_MET` |
| Identity/order | arguments; scrubbed environment; fixed host and process absence; imported/current/external identities including headers; clean exact-source build; samples; schema/output/cache/lifetimes; aggregate/gate; final identities/head; cleanup-inclusive ceiling; publication |
| Persisted/cache identity | N/A: no persisted format or cache lifetime/schema changes |
| Cost ceiling | one monotonic 8-minute ceiling includes build, four conditioning/full pairs, validation, and cleanup |
| Acceptance evidence | author consistency; native/stub ABI owners; layer-forward and runtime-provider smokes; `make check`; `make fmt`; Python compilation and runner self-test; one clean-head real qualification; removal comparison if not `MET`; `git diff --check`; one comprehensive review; exact-head focused preflight |

Cross-host, GPU, throughput, arbitrary-task, cache-policy, persistent-provider, and whole-R8 claims
are N/A. The capability claims only fixed-request latency if the precommitted gate passes.

## 3. Closure matrix

| Path | Construction | Success | Failure / early exit | Cleanup | Exact evidence |
| --- | --- | --- | --- | --- | --- |
| Plane K/V | validate slots, types, spans, host visibility and layout | exact compared-byte accounting; K then V | original first tensor/column mismatch; phase B not started | borrowed ranges only | real/stub exact, mismatch, unaligned and forced-writeback owners |
| Cache hit | eligible layout and combined wrap | recency/counters update, no claim copy | invalid metadata refuses before slot use | invocation owns cache | repeated key, zero-copy clock and fixed counters |
| Cache miss/eviction | existing read/scatter and victim selection precede admission | identical bytes admitted and selected keys re-resolved | partial admission is not consumed | unchanged claim/cache owners | miss, eviction, reload and sentinel owners |
| Cache fallback | static ineligibility or wrap refusal | original compact tensors/copies | original fault order | original teardown | diagnostic golden and injected refusal |
| Routed layer | shipped full-width phase A, then plane verify, then cache staging | phase B consumes exact selected bytes | first failure prevents later construction | both graphs and one wrap converge | hosted combined request and real conditioning |
| Sample/aggregate | four exact pairs and immutable baseline | exact output/cache/lifetimes; median at ceiling is `MET` | malformed, drifted or above-ceiling evidence refuses or records `NOT_MET` | fresh process per request; cleanup before result | schema mutations, gate boundaries, real four-repeat record |
| Identity/run | pin complete source, toolchain, model and host chain | final identities and head unchanged | mutation, contamination, signal or deadline emits no document | stop children and restore generated helper | self-tests plus clean-head qualification |

## 4. Implementation and verification map

1. Restore only item 61's final reviewed plane implementation and item 66's final reviewed cache
   implementation against current `main`; retain full-width phase A byte-for-byte.
2. Restore their direct malformed/success/fallback owners and add a thin helper plus bounded runner
   that validates the two active interventions and item 62's unchanged gate.
3. Run narrow owners, formatting, and one clean-head four-repeat qualification.
4. Record the decision here, in the roadmap, and in `HANDOFF.md`; remove production changes before
   publication unless the complete-request result is `MET`.
5. Complete one comprehensive review, repair accepted findings, run exact-head preflight, publish,
   merge, and continue.

The ledger and matrix agree that no routing-width change, new cache policy, lifetime extension, or
new optimization is present. The two interventions are ordered, allocation-free views over existing
owned storage and retain their individually reviewed fallbacks. The immutable complete-request gate
alone authorizes shipment.

## 5. Recorded result

Design checkpoint `07516a5` fixed this contract before production changes. Implementation
checkpoint `e7e94e3` restored only the reviewed item-61 and item-66 production forms; qualification
owner checkpoint `80e87d516e21d080f31e13e006c0607e59447a99` added no third intervention. The shipped
`src/layer_olmoe.align` and decode golden remain byte-identical to merged item 67, proving the
live-width phase-A topology and oracle changes are absent.

The clean-head qualification ran on Darwin arm64 25.5.0 with Align
`8cefc803d5c7f883a8db5b67250ed4ed069b43a4`, the pinned Homebrew ggml 0.21.0 libraries and
headers, and the fixed OLMoE model, pack, geometry, task, prompt, server, compiler, and C toolchain.
It completed in 109.426 seconds. The four candidate full-helper walls were
`[17714825083,16684315166,17132135334,21189618042]` ns, with a 17,423,480,208-ns median.
Against the immutable 19,266,559,229-ns baseline, the gain is 1,843,079,021 ns or 95,662 ppm,
exceeding the 963,327,962-ns / 50,000-ppm floor by 879,751,059 ns. The decision is **`MET`**.

Every request reproduced the fixed 87-id chain, 86-token output and SHA-256; every conditioning
request was its full request's exact two-token prefix. All four full requests retained exactly
11,940 cache requests, 7,325 hits, 4,615 misses, 4,376 evictions, and 17,656,872,960 fetched bytes.
Cache-to-claim copy time was `[0,0,0,0]` ns. Plane-roundtrip comparison was
`[796731156,736721629,736683061,991718491]` ns, with a 766,726,392-ns median. Every native owner
balanced, all twelve process-isolation boundaries were clean, and final source/external identities
were unchanged. The two exact-safe interventions therefore ship together; this result makes only
the fixed-request, fixed-host latency claim defined above.
