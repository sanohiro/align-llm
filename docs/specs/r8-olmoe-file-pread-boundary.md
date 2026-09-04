# R8 OLMoE file-pread boundary

Status: active, implementation complete; qualification pending, 2026-09-05

Roadmap owner: item 65, `R8-OLMOE-FILE-PREAD-BOUNDARY`

## 1. Decision owned

Item 64 measured the fixed OLMoE request's remaining-decode claim-file `pread` calls at a
1,945,780,694-nanosecond median, the largest child of the 3,756,637,232-nanosecond claim-I/O
parent. The current path reads every missed ExpertBlock through a maximum-sized temporary buffer
and then copies its three member ranges into the claim window.

The candidate uses the shipped pinned-Align `fs.read_bytes_view` surface to map the validated
AlignPack once for an OLMoE provider-generation invocation. A cache miss takes bounded slices from
that mapping and copies the same three ranges to the same claim destinations. It therefore removes
the file-to-temporary `pread` copy and the block temporary from the provider path without changing
the cache, claim window, graph, routing, sampling, or output. The diagnostic `--moe-decode-step`
API retains its existing `pread` path and exact schema/counter meanings.

Item 62's full-helper walls `[18059864416,18927732709,20639199375,19605385750]` ns and
19,266,559,229-ns integer median are immutable. This ledger precommits the inherited 50,000-ppm
floor of 963,327,962 ns and candidate ceiling of 18,303,231,267 ns. Four fresh-process fixed
requests must preserve all inherited semantic and ownership evidence and have a median no greater
than the ceiling. Otherwise the production mapping and its production-owner tests are removed
before publication.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-FILE-PREAD-BOUNDARY`; production owners are `src/moe_decode_step.align` and the existing provider-generation call chain; qualification owners are `src/olmoe_file_pread_gate.align` and `scripts/run-olmoe-file-pread-boundary` |
| Consumer | OLMoE `provider_runtime.generate`, through `moe_decode_step.generate_resident` or `generate_resident_sampled`; the CLI diagnostic `execute` remains on `pread` |
| Fixed request | inherit item 62 exactly: model, AlignPack, geometry, 975,175,680-byte cache budget, fixed task/prompt, temperature 300,000 micros, seed 5, maximum 128, EOG behavior, exact 87-token id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Immutable baseline | item 62's four walls and 19,266,559,229-ns median above; candidate samples never replace it |
| Shipping gate | 50,000 ppm rounded up is 963,327,962 ns; candidate ceiling is 18,303,231,267 ns; `MET` iff the four-sample candidate wall median is at or below the ceiling |
| Mapping construction | after the existing path grammar, geometry, source identity, AlignPack index, budget, allocation, ggml-availability, and ABI checks, enter one arena and call `fs.read_bytes_view(pack_path)` exactly once before the decode schedule |
| Mapping validation | require mapped length to equal the already validated AlignPack `total_bytes`; mapping/open failure remains `R4_PACK_UNREADABLE`; length mismatch is the existing `R4_PACK_TRUNCATED` and no graph or cache mutation occurs |
| Claim source | provider generation reads every cache-miss ExpertBlock from the mapped byte view at the already validated `expert_pack_offset` and `expert_pack_bytes`; each requested role uses the existing validated relative start and size and the existing `window_put` destination |
| Copy count | one mapped-pack-to-claim copy per requested role remains; the old file-to-block-temporary copy is removed; hit, claim-to-cache, and cache-to-claim copies are unchanged |
| Cache accounting | requests, hits, misses, evictions, bytes served, logical miss bytes, and `expert_cache_bytes_fetched` retain their exact values; `bytes_fetched` counts the validated mapped block spans sourced on misses rather than requiring a syscall |
| Syscall accounting | provider-generation claim `pread` count/bytes and `claim_file_pread_ns` are zero; the diagnostic CLI retains its existing nonzero `expert_pread_bytes`, `step_expert_pack_bytes`, reader counters, and schema meanings because it does not select mapping |
| Existing public result | HTTP success/error shape and generated text are byte-unchanged; `GenerationParts` keeps its type. Its diagnostic `Outcome` truthfully reports zero claim-file-pread work and unchanged cache-source bytes on the mapped provider path |
| Ownership/lifetime | the mapping is borrowed only inside one enclosing arena that also encloses the complete schedule; arena cleanup unmaps it after converged ggml/cache teardown and before `execute_mode` returns; no mapped slice enters a result, cache, native ggml tensor, closure, or global |
| File stability | the caller owns an immutable regular AlignPack for the complete invocation. Replacement or mutation after validation is unsupported; concurrent truncation has pinned Align's documented process-level `SIGBUS` behavior. The provider already treats model assets as immutable and the fixed qualification pins pack identity before and after every run |
| Allocation/resource | remove the per-prefill and per-decode maximum-ExpertBlock temporary on provider generation. The read-only virtual mapping adds no Align buffer and the OS may retain mapped pages in its normal file cache; the existing explicit 975,175,680-byte expert-cache budget is unchanged and does not claim to bound OS file cache |
| Persisted/cache identity | N/A: no pack, geometry, provider response, persisted cache, or migration format changes; cache keys and contents remain the same copied claim bytes |
| Schema version | production HTTP and diagnostic CLI schemas unchanged; qualification result is exact schema 1 |
| Validation order | existing ordered refusals; map and exact length; schedule; semantic/cache/lifetime checks; four-repeat aggregate and immutable gate; final identity/head checks; cleanup; publication |
| Failure | nonzero with no complete qualification document for malformed input, map/length failure, range failure, output/cache/lifetime drift, identity mutation, process contamination, timeout, cleanup failure, or ceiling excess |
| Prerequisites | item 64's selection; pinned Align `8cefc803d5c7f883a8db5b67250ed4ed069b43a4` with shipped `fs.read_bytes_view`; fixed capable host and model assets; no Align request or hypothetical surface |
| Cost ceiling | one monotonic 8-minute qualification ceiling covers exact-source build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; individual children retain narrower bounds |
| Acceptance evidence | author consistency pass; `make fmt`; pinned helper build; mapped-length and source-range owner regressions; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation and model-free runner self-test; one clean-head four-repeat qualification; `git diff --check`; one comprehensive review; exact-head preflight with the focused self-test |

The capability makes one model/request/host latency claim only. Cross-host, GPU, throughput,
arbitrary-task, OS-page-cache residency, individual-page-fault, and whole-R8 claims are N/A.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Provider map | one arena and one `read_bytes_view` after existing validation | exact `total_bytes` view reaches schedule | missing/unreadable maps to `R4_PACK_UNREADABLE`; wrong length to `R4_PACK_LEN` | no schedule/cache mutation | arena unmaps once | synthetic missing/short mapping plus real fixed pack |
| Expert range | checked plan offset/span selects one block view | same three relative member slices | negative, overflow, or beyond-view range returns existing pack fault before copy | current layer fails through existing `take_pack` | view has no independent owner | small-pack mapped/pread equality and explicit bad span |
| Cache miss | mapped scatter precedes admission | same claim bytes copied into one slot | source/copy failure cannot evict or admit | failed demand is not a hit later | existing cache buffer | forced miss contents/accounting plus real counts |
| Cache hit | mapping unused | existing slot-to-claim copy | existing window failure | no new mutation | unchanged | inherited cache owner and exact real counts |
| Prefill/decode handoff | one mapping spans both passes | one cache state and one source view | failure uses converged schedule teardown | partial step remains uncommitted | mapping outlives all graph consumers | exact output and lifetime balances |
| Diagnostic CLI | mapping flag is false | existing `pread` scatter byte-for-byte | existing refusals/counters | unchanged | existing buffers/files | unchanged golden and layer-forward owner |
| Provider result | existing generation API chooses mapping | text/token ids unchanged | existing provider error shape | no mapped view escapes | arena ends before return | runtime-provider smoke and fixed output hash |
| Native graph | claim bytes are copied before wrap/placement | graph sees same aligned claim window | existing FFI failures | converged graph teardown | mapping is never given to ggml | native lifetime balances |
| Repetition | fixed host, clean process, pinned identities | four exact conditioned pairs | any drift aborts without result | no partial result | signal/deadline cleanup | twelve isolation checks and final identity recheck |
| Gate | immutable baseline plus four walls | integer median at/below ceiling is `MET` | malformed arithmetic/baseline rejects | N/A | N/A | below/at/above vectors |

Persistence, migration, network connection ownership, asynchronous calls, source moves, and generic
monomorphization are N/A. The synchronous provider owns an immutable model asset, and the mapped
view neither escapes its arena nor becomes a native tensor.

## 4. Implementation and verification map

1. Add a bounds-checked mapped ExpertBlock scatter beside the existing `pread` scatter.
2. Thread one borrowed mapped view and one provider-only selection bit through the schedule, passes,
   and layer owner. Keep the diagnostic path on the old reader.
3. Enter the mapping arena only in generation mode, validate exact pack length, and run the whole
   schedule before the arena ends. Preserve cache fetched-byte accounting independently of syscall
   counters.
4. Extend the narrow owner with mapped/pread content equality, failure-before-admission, unchanged
   diagnostic counters, and provider mapping failures.
5. Add the item-65 helper and bounded runner by inheriting item 64's fixed request but independently
   pinning the complete transitive source/runner/toolchain chain and immutable item-62 gate.
6. Run the narrow owners and clean-head real qualification. Record `MET` or `NOT_MET`; remove the
   production intervention and its owner changes before publication on `NOT_MET`.
7. Complete one comprehensive review, consolidate valid findings, rerun affected evidence and the
   exact-head preflight, publish, merge, and continue.

No `make ci`, installed platform profile, 40-prompt corpus, stress suite, or unrelated benchmark is
selected.

## 5. Author consistency pass

The ledger and matrix agree that only provider generation changes claim source, while the CLI
diagnostic remains the syscall-accounting oracle. The mapping is constructed after all existing
bounded metadata and ABI validation, lives longer than every schedule consumer, and is destroyed
after their converged teardown. Every mapped range comes from the already validated plan and is
checked again against the mapped view before slicing. Cache-source bytes retain their numerical
meaning while syscall fields become zero only on the provider path. The immutable baseline,
963,327,962-nanosecond floor, and 18,303,231,267-nanosecond ceiling are fixed before production
code changes.
