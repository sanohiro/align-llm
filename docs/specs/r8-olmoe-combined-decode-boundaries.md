# R8 OLMoE combined decode boundaries

Status: active; design complete, implementation pending, 2026-09-05

Roadmap owner: item 67, `R8-OLMOE-COMBINED-DECODE-BOUNDARIES`

## 1. Decision owned

Items 61, 63, and 66 each evaluated a correctness-preserving reduction of a different shipped
decode boundary. None cleared a 50,000-ppm complete-request gate alone, so every production change
was removed. Their fixed-request results nevertheless provide independent directional evidence:

- item 61's final unaligned-safe plane comparison reduced the complete plane boundary from
  2,972,324,939 ns to 838,509,258 ns and its full wall by 139,023,395 ns;
- item 63's live-width phase A reduced its measured phase-A median to 1,468,786,181 ns from item
  62's 2,939,392,017 ns and its full wall by 817,443,563 ns; and
- item 66 removed the 1,072,229,252-ns cache-to-claim copy bucket and reduced its full wall by
  210,165,021 ns.

Those full-wall gains are from separate noisy qualifications and are not added into a performance
claim. They do justify one combined candidate because the interventions act at disjoint execution
points: phase-A graph width, post-graph K/V verification, and phase-B expert tensor sourcing. The
candidate reuses the final reviewed form of each intervention without adding a fourth optimization.

Item 62's shipped full-helper walls
`[18059864416,18927732709,20639199375,19605385750]` ns and 19,266,559,229-ns median are the
immutable baseline. The precommitted 50,000-ppm floor is 963,327,962 ns and the candidate ceiling
is 18,303,231,267 ns. Four conditioned fresh-process repetitions must preserve every inherited
semantic, cache, isolation, and lifetime boundary and have an integer median no greater than the
ceiling. Otherwise all production and production-owner changes are removed before publication.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-COMBINED-DECODE-BOUNDARIES`; production owners are `src/layer_olmoe.align`, `src/moe_decode_step.align`, `src/moe_model_forward.align`, `src/ggml_ffi.align`, both ggml shims, and the shim build; directly required owner changes are the layer-forward and runtime-provider smokes; qualification owner is `scripts/run-olmoe-combined-decode-boundaries` |
| Consumer | the fixed item-62 OLMoE provider-generation request and the next R8 shipping decision after three individually negative boundary candidates |
| Fixed request | inherit item 62 exactly: task/system/user prompt, OLMoE model, AlignPack, geometry, 975,175,680-byte partial-LRU budget, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | four sequential fresh-process pairs; each maximum-2 result is the exact prefix of its following maximum-128 result; zero processes matching both pinned llama-server and model paths before, between, and after every pair |
| Immutable baseline | item 62 walls and 19,266,559,229-ns median above; candidate samples never replace them |
| Shipping gate | 50,000 ppm rounded up is 963,327,962 ns; candidate ceiling is 18,303,231,267 ns; `MET` iff the four-sample candidate median is at or below the ceiling |
| Phase-A intervention | restore item 63's reviewed fixed-request behavior: construct each decode phase-A graph at `n_past + 1`, pass the exact existing mask prefix, omit the two now-equal-width K/V PAD nodes, retain the full-width canonical plane and the general wider-table path |
| Plane intervention | restore item 61's final reviewed behavior: compare host-visible concat tensors directly through their slots, use the validated exact-byte K/V primitive, and on AArch64 use unaligned-safe 4-by-4 V transpose tiles only for exact success with the original scalar traversal on mismatch; other architectures remain scalar |
| Cache intervention | restore item 66's reviewed behavior: for eligible provider generation wrap dense plus cache once, skip hit copies, re-resolve routed keys to cache slots, place three fixed-stride expert tensors over cache storage, and retain the compact-copy path for diagnostics, ineligible layouts, and combined-wrap refusal |
| Interaction invariant | phase A completes and routing ids are copied before claim/cache staging; all selected cache slots are stable before phase B is built; plane comparison runs after phase A writeback and before phase-B staging. No intervention changes another intervention's input bytes, cache mutation order, or cleanup owner |
| Native ABI | retain item 61's validated byte/slot plane-compare calls and item 66's validated strided tensor constructor. No ggml struct crosses FFI; all sizes, strides, offsets, types, host visibility, and reachable spans are checked before native reads or tensor placement |
| Fallbacks | non-AArch64 plane comparison is scalar; a plane mismatch reruns the scalar V traversal for the original first-column result; cache direct mode falls back to the compact claim graph on static ineligibility or combined-wrap refusal; diagnostic/reference and non-cache paths remain compact |
| Numerical behavior | phase-A live prefixes, plane bytes, expert bytes, routing ids, graph arithmetic/order, logits, sampling, token ids, and output remain exact; the full transcript oracle retains every comparable row and existing shape exclusions |
| Cache behavior | exact LRU keys, recency, victim order, hits, misses, evictions, fetched bytes, budget, and stored content remain unchanged. Full fixed requests report zero cache-to-claim copy nanoseconds only when direct mode is selected |
| Ownership/allocation | canonical plane, dense allocation, cache, claim window, metadata, activation, and temporary allocations retain their owners and budgets. Direct plane comparison and strided tensors borrow existing storage; the one run-scope resident wrap covers dense plus cache and is freed before its Align buffer dies |
| Existing results | HTTP/provider schemas, diagnostic CLI schemas, `GenerationParts`, and existing qualification records remain byte-shaped and meaning-compatible; timing counters continue to describe their existing complete boundaries |
| Qualification helper | add thin `olmoe_combined_decode_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`, delegating to the existing claim-detailed helper so each record includes `pass_other`, `decode_compute`, and `claim_io` |
| Candidate evidence | record four full walls, phase-A clocks, complete plane-roundtrip clocks, and cache-to-claim clocks. Require every cache-to-claim value to be zero; the other clocks are diagnostic and do not replace the complete-request decision |
| Result | one exact-key schema-1 `R8_OLMOE_COMBINED_DECODE_BOUNDARIES` JSON document with fixed baseline/gate, exact intervention identity, four inherited samples, aggregate clocks/gain, and `MET` or `NOT_MET`; no complete document on failure |
| Inputs/identity | independently pin the item-66 runner and complete helper/source chain, all newly changed sources and owner scripts, model, pack, geometry, server, Align revision/compiler, ggml libraries and consumed headers, C compiler/version, task, prompt, exact token chain, built helper/shim, clean align-llm head, and fixed host fingerprint |
| Validation order | arguments/prerequisites; scrubbed environment/linker search; fixed host, clean head, process absence, imported/current/external identities; exact-source build; four conditioned records; schema/equations/output/cache/lifetime/repeatability; aggregate/gate; final identities/head; cleanup-inclusive ceiling; publication |
| Failure/early exit | native validation and existing first-fault order remain fail-closed; no partial layer, cache admission, graph, or qualification document survives an error; identity drift, contamination, timeout, cleanup failure, or ceiling excess exits nonzero |
| Persisted/cache identity | N/A: no persisted format, model, pack, geometry, provider response, or cache schema change |
| Cost ceiling | one monotonic 8-minute ceiling covers exact builds, four conditioning/full pairs, aggregation, final identity checks, and cleanup |
| Integration | the evaluated candidate commit must remain an ancestor of merged `main`; publication uses a merge commit, never squash or rebase, so a retained negative result can identify the exact executable source |
| Acceptance evidence | author consistency pass; shared real/stub ABI contract checks; restored malformed/success/fallback/topology/plane/cache owners; `make check`; `make runtime-provider-smoke`; `make layer-forward-smoke`; `make fmt`; Python compilation and complete runner self-test; one clean-head four-repeat qualification; production removal comparison on `NOT_MET`; `git diff --check`; one comprehensive review; exact-head preflight with the focused owner |

The capability makes one fixed-request latency claim on one pinned host only if the gate is met.
Cross-host, GPU, throughput, arbitrary-task, cache-policy, kernel, and whole-R8 claims are N/A.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup/state | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Phase A | live width and mask prefix validated before nodes | two PAD nodes omitted; routing/output exact | invalid width or shape retains existing fault | phase B is not built | original graph teardown | exact node formula, full transcript, routed output |
| Plane K/V | slot, type, bytes, host visibility, layout, and plane bounds validate before reads | exact bytes add unchanged compared-byte count | K-before-V and first-column detail preserved; unaligned/range defects refuse | phase B staging not started | borrowed ranges only | real/stub exact, competing mismatch, unaligned, forced writeback cases |
| Cache hit | eligible layout and combined wrap exist | recency/counters update; no claim copy | invalid metadata refuses before slot ids | no phase-B graph | cache owned by invocation | repeated key, zero copy clock, exact cache counters |
| Cache miss/eviction | existing read/scatter and victim choice precede admission | same bytes admitted; selected keys re-resolve | read/copy/slot failure cannot publish partial admission or graph | failed key is not consumed | unchanged claim/cache owners | miss, eviction, selected-key reload, sentinels |
| Cache fallback | static ineligibility or wrap refusal | original compact ids/tensors/copies execute | original fault order | unchanged | original claim wrap/teardown | diagnostic golden and injected refusal |
| Combined routed layer | phase A then plane verify then stable cache staging | phase B consumes exact selected bytes | first failure prevents subsequent construction | no partial layer result | both graphs and one wrap converge | hosted combined request and fixed real conditioning |
| Helper/sample | inherited exact request and three detailed objects | one exact record and exact short prefix | malformed key/equation/output/cache/lifetime rejects | no partial record | fresh process exits | schema and mutation self-tests |
| Aggregate/gate | four exact samples and immutable baseline | median at/below ceiling is `MET` | boolean/arithmetic/identity/zero-copy drift rejects | no partial result | cleanup precedes publication | at/above/below ceiling and malformed-clock vectors |
| Identity/integration | current sources and external inputs pin before build | final values/head unchanged and evaluated head remains reachable | mutation, replacement, graft, or wrong head refuses | no claim | generated helper restored | deep source mutation, clean-head check, post-merge ancestry |
| Signal/deadline | handlers installed before real work | N/A | interruption/timeout exits nonzero | no complete JSON | child stopped and temp/build state restored | inherited timeout/restoration tests |

Concurrent invocations share no mutable runtime state. Generic monomorphization, serialization,
text encoding, and migration are N/A because the changed interfaces are fixed native scalars and
borrowed byte storage inside one synchronous provider invocation.

## 4. Implementation and verification map

1. Restore the final reviewed production and owner-test changes from items 61, 63, and 66, resolving
   their two shared files without changing any individual contract.
2. Add the thin combined helper and a bounded runner that imports item 66's workload/cleanup
   primitives, pins the complete combined source chain, validates all three active interventions,
   and applies item 62's immutable full-request gate.
3. Run the narrow native, layer, provider, formatting, and self-test owners; then run one clean-head
   four-repeat fixed qualification.
4. Record `MET` or `NOT_MET` here, in the roadmap, and in `HANDOFF.md`. On `NOT_MET`, remove every
   production and production-owner change before publication while retaining the decision owner.
5. Complete one comprehensive review, consolidate valid findings, rerun affected evidence and the
   exact-head preflight, publish with merge-only integration, merge, and continue.

No `make ci`, installed platform profile, portfolio, stress suite, cache replay, or unrelated
benchmark is selected. The three already reviewed interventions, their interaction owners, and one
complete-request gate form the smallest candidate that can use their combined measured opportunity.

## 5. Author consistency pass

The ledger and matrix agree that the candidate adds no new optimization beyond the final reviewed
forms from items 61, 63, and 66. Each operates at a distinct ordered boundary and retains its prior
validation, fallback, numerical, cache, and ownership contract. Component clocks are supporting
evidence only; item 62's unchanged complete-request baseline, 963,327,962-ns floor, and
18,303,231,267-ns ceiling solely decide publication. Every construction, success, failure, early
exit, cleanup, identity, and integration cell names an implementation owner and regression before
production code changes.
