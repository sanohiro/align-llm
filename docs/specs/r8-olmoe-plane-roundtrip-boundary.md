# R8 OLMoE plane round-trip boundary

Status: complete, `NOT_MET`, 2026-09-05

Roadmap owner: item 61, `R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY`

## 1. Decision owned

Item 60 measured the complete decode-only `verify_plane` call at a 2,972,324,939-ns median and
991,445 ppm of its diagnosed parent. That clock includes concat shape reads, two `slot_get`
operations, scalar K/V comparison, and result accounting; it does not attribute cost among them.

The first intervention replaced only the scalar comparison implementation with one bounded
shared-shim call per K/V tensor. Its clean-head qualification reduced the measured boundary from
2,972,324,939 ns to 1,878,132,280 ns, but full-helper wall improved by only 23,162 ppm, so that
candidate is `NOT_MET` and cannot ship on its own. The remaining boundary still performs two full
`ggml_backend_tensor_get` copies for every routed layer and decode step.

The second intervention retained both concat shape reads but compared each host-visible concat
tensor in place through its slot. It removes the two copies into `node_window` without weakening
validation or oracle semantics. Its clean-head boundary median was 1,835,826,340 ns and its
full-helper median was 19,122,598,458 ns: `NOT_MET`, so it cannot ship on its own.

Disassembly of that exact real shim shows the V path still executes the original scalar
`head -> lane -> column` loop, approximately 30 million four-byte comparisons for the fixed
request. The third intervention added an AArch64 exact-success fast path over 4-by-4 transpose tiles.
It compares every byte but batches sixteen lanes per tile; if any tile differs it reruns the
existing scalar traversal to recover the same first mismatch column. Non-AArch64 and tile remainders
use scalar comparison. This is still an intervention over item 60's complete measured boundary,
not an attribution claim. It ships only if the same complete fixed request preserves correctness
and improves full-helper wall time by at least 50,000 ppm against the immutable item 60 baseline.
A pre-review qualification measured `MET`, but comprehensive review found that its typed NEON loads
added an undeclared alignment precondition to the byte-range ABI. The repaired candidate uses
byte-aligned vector loads and preserves the emitted instructions, but its required clean-head
qualification measured only a 7,416-ppm full-helper gain: `NOT_MET`. Per the precommitted decision
rule, all three production interventions were removed before publication.

## 2. Public-contract ledger

This ledger records the evaluated candidate contract. The final `NOT_MET` decision removes every
production surface below; it does not add a public ABI or change the shipped decode consumer.

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY`; evaluated production owners were `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`, `src/ggml_ffi.align`, and `src/moe_decode_step.align`; qualification owner is `scripts/run-olmoe-plane-roundtrip-boundary`. The evaluated production diff does not ship after `NOT_MET`. |
| Consumer | OLMoE sampled decode oracle B after each routed-layer graph; it must still compare the graph-consumed K/V concat against the canonical plane through the just-written column |
| Native ABI | The byte primitive remains `int64_t align_ggml_compare_kv_plane(const void *consumed, int64_t consumed_bytes, const void *plane, int64_t plane_bytes, int64_t plane_base, int64_t head_dim, int64_t n_head_kv, int64_t columns, int32_t layout)`. Production calls `int64_t align_ggml_slot_compare_kv_plane(const void *slots, int64_t index, const void *plane, int64_t plane_bytes, int64_t plane_base, int64_t head_dim, int64_t n_head_kv, int64_t columns, int32_t layout)`. No ggml type crosses either ABI. |
| Layout tags | `0` is K and `1` is V; every other `int32_t` value is invalid |
| Return encoding | `0` means byte-identical; positive `column + 1` means mismatch at the first column reached by the exact traversal below; negative values are existing shim status codes; the byte primitive emits only `ALIGN_GGML_INIT` or `ALIGN_GGML_BOUNDS`, while the slot entry may additionally emit `ALIGN_GGML_SLOT` |
| Canonical source | `plane_base + (lane + head_dim * (head + n_head_kv * column)) * 4`, for `head = 0 .. n_head_kv`, `column = 0 .. columns`, and `lane = 0 .. head_dim` |
| K consumed layout/order | consumed offset `(lane + head_dim * (column + columns * head)) * 4`; observable first mismatch follows `head`, then `column`, then `lane`; an implementation may compare one contiguous lane row at a time because only its column is returned |
| V consumed layout/order | consumed offset `(column + columns * (lane + head_dim * head)) * 4`; observable first mismatch follows `head`, then `lane`, then `column` |
| Byte semantics | compare the four stored bytes of every F32 lane exactly; no float conversion, tolerance, endianness reinterpretation, or NaN normalization |
| V exact-success fast path | On AArch64, compare complete 4-lane by 4-column tiles by loading four contiguous consumed rows, transposing them in registers, and byte-comparing the resulting column vectors with four canonical plane ranges; compare remainder lanes/columns scalarly. Any difference transfers to the unchanged `head -> lane -> column` scalar traversal, so only the exact-success cost changes. Other architectures use that scalar traversal directly. |
| Native validation order | The slot entry resolves the slot or returns `ALIGN_GGML_SLOT`; rejects a null plane with `ALIGN_GGML_INIT`; requires exact tensor bytes `head_dim * n_head_kv * columns * 4`; in the real shim requires a nonnull tensor buffer for which `ggml_backend_buffer_is_host` is true and nonnull data, otherwise `ALIGN_GGML_BOUNDS`; then calls the byte primitive. The primitive rejects a null range with `ALIGN_GGML_INIT`; rejects negative lengths/base, nonpositive dimensions, or an unknown layout with `ALIGN_GGML_BOUNDS`; checked-multiplies the span; requires it within consumed bytes and `[plane_base, plane_base + span)` within plane bytes and representable as `size_t`; and reads no byte before all checks pass. |
| Ownership/allocation | the byte primitive borrows two caller-owned ranges; the slot entry borrows one ggml-owned tensor range and one caller-owned plane range. Overlap is allowed because both are read-only; neither function writes, allocates, frees, retains, or opens anything or has process-global state. |
| Align wrapper | `ggml_ffi.slot_compare_kv_plane(...) -> Result<i64, Fault>` passes the slot slice, index, plane slice/length, and fixed layout; maps raw `0` to `Ok(-1)`, raw positive `n` to `Ok(n - 1)`, and a negative status through the existing R5 fault mapping; one `unsafe` block contains the one foreign call. The byte wrapper remains owner-testable but is no longer a production callsite. |
| Decode integration | retain the existing span and both concat-shape checks; replace each `slot_get` plus byte-wrapper pair with one slot-wrapper call using layout K or V; `node_window` remains owned for the later transcript oracle and no allocation or native owner is added |
| Success | both calls return `-1`; add the unchanged `2 * columns * plane_column_bytes(g)` to `roundtrip_bytes_compared` exactly once |
| Mismatch/failure | preserve the current first K-before-V priority and exact tensor/column detail; slot, host-visibility, or native validation faults are the owning tensor at column `-1` and the existing `R6M_PLANE_MISMATCH`; prior shape failures keep their current detail and early return |
| Forced regressions | the unchanged capture-plane `slot_get` still applies the routed writeback-offset perturbation to the just-written plane column; the same path also preserves the general forced-inf readback behavior. Direct concat comparison must disagree with those perturbed plane bytes and retain the existing observable failure records. |
| Existing records | provider output and item 57, item 59, and item 60 helper schemas are byte-shape unchanged; item 60's `plane_roundtrip_compare_ns` continues to time the complete `verify_plane` call, not the native comparison alone |
| Fixed baseline | item 60 full-helper samples `[17704139042,18412456541,19080317000,19520549709]`, integer median 18,746,386,770 ns, on its exact Apple M1 host and fixed request |
| Performance gate | floor 50,000 ppm, rounded-up minimum gain 937,319,339 ns; candidate four-sample median must be at most 17,809,067,431 ns; equality is `MET`, anything slower is `NOT_MET` |
| Qualification | four sequential fresh-process maximum-2/maximum-128 pairs through the unchanged item 60 helper; exact prefix, 86-token output/hash, native lifetimes, twelve isolation boundaries, cache, host, and cleanup all remain mandatory; record candidate full-helper wall and complete plane-boundary medians |
| Result | one exact-key schema-1 `R8_OLMOE_PLANE_ROUNDTRIP_BOUNDARY` JSON document on stdout and one concise stderr summary; candidate identity includes the exact three ggml headers consumed by the shim build; no complete document on failure |
| Inputs/identity | independently pin item 60 workload/evidence, predecessor runner and helper chain, decode/outcome/FFI sources, both C shims and their shared region, build script, model, pack, geometry, server, Align revision/compiler, ggml libraries, the exact `ggml.h`, `ggml-alloc.h`, and `ggml-backend.h` byte identities, C compiler/version, task, prompt, exact token chain, built helper/shim, clean head, and baseline-host fingerprint |
| Validation order | argument/prerequisite precedence; scrubbed environment/linker search; fixed host, clean head, process absence, imported and external identities including the three consumed ggml headers; exact-source build; four conditioned records; schema/output/lifetime/repeatability; performance aggregate; final source/header/library identities and head; exit helper and temporary contexts; cleanup-inclusive ceiling; validation; publication |
| Failure/cleanup | nonzero and no complete document for invalid ABI input, identity/host/source/process drift, malformed result, output/lifetime drift, child failure, source mutation, cleanup failure, or gate-run ceiling excess; missing prerequisites retain the one declared N/A path; signal and timeout cleanup stop owned children, restore any prior root helper, and remove the temp tree |
| Persisted/cache identity | N/A: no persisted format, cache policy, model, pack, geometry, or provider schema changes; qualification stdout is not persisted by the runner |
| Cost ceiling | one monotonic 8-minute ceiling covers shim/helper build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; each child retains its narrower bound |
| Acceptance evidence | author consistency pass; direct shared-shim exact/mismatch/refusal vectors, including unaligned V tile ranges during review repair; `make fmt`; pinned helper build; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation and item 57→61 self-test chain including header-identity mutation; complete real qualifications before and after review repair; production-diff removal check against item 60; `git diff --check`; comprehensive reviews before and after the materially changed final candidate; exact-head `scripts/pre-pr --owner-test R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY -- scripts/run-olmoe-plane-roundtrip-boundary --self-test` |

The capability claims only fixed-request latency on one pinned host when the gate is met. Cross-host,
GPU, throughput, arbitrary-task, cache-policy, numerical, and public-provider improvements are N/A.
Text encoding and embedded-NUL rules are N/A because no text crosses the new ABI. Generic
monomorphization, interface serialization, move/source-nulling, replacement, and Drop are N/A
because both arguments are borrowed slices and the native function creates no owner.

## 3. Closure matrix

| Path | Construction/validation | Success | Failure/early exit | Cleanup/state | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- |
| Shared native K | validate all scalar and byte bounds before reading | contiguous lane-row comparisons preserve head/column priority | first mismatching row returns `column + 1`; malformed input returns before reads | read-only, allocation-free, no state | non-square exact vector, multiple-column mismatch, null/bounds/overflow/layout cases |
| Shared native V | same complete pre-read validation | four-byte comparisons preserve head/lane/column priority | first mismatch follows traversal, not minimum numeric column | read-only, allocation-free, no state | non-square exact vector with competing mismatch columns |
| AArch64 V tiles | all shared bounds checks precede vector loads; full tiles only | every byte equal returns exact after tiled/remainder scan | any unequal tile or remainder reruns scalar V traversal and returns its column | register-only; no write or owner | exact non-square vector plus competing mismatch vector on AArch64; scalar fallback on hosted x86 |
| Real slot entry | resolve slot, exact size, host-visible buffer, and data before the shared primitive | compares ggml-owned host bytes without a copy | missing slot or non-host/null data returns before reads | borrowed tensor/plane; no owner | CPU routed success plus native refusal vectors |
| Stub slot entry | resolve slot, exact size, and data before the shared primitive | ordinary engine matches real semantics | malformed slot/data refuses before reads; existing capture readback builds perturb the plane independently | borrowed tensor/plane; no owner or lasting state | routed success, writeback-offset, and forced-inf owners |
| Safe wrapper | compiler supplies both slice lengths and one fixed layout tag | `0 -> -1`, positive result subtracts one | negative result maps through existing fault table | borrows only; one unsafe call | pinned executable build and direct wrapper callsite compilation |
| Verify K | existing shape check precedes native slot compare | equality continues to V | mismatch records K and exact column; fault records K/-1; V is skipped | existing window and graph owners unchanged | current routed success and forced writeback-offset failure |
| Verify V | reached only after successful K | equality commits unchanged byte total | mismatch records V and exact column; fault records V/-1 | existing window and graph owners unchanged | native V vector plus routed success |
| Historical helpers | same shared helper and three fixed entrypoints | item 57/59/60 exact key sets remain | malformed additions still reject | invocation-owned | self-test chain and real maximum-2/full item 60 records |
| Performance repetition | fixed host, clean head, exact item 60 baseline, fresh short/full child pair | four valid samples produce median/gain and `MET` only at/below ceiling | drift or one invalid sample prevents result | twelve absence checks; child reaped | exact/one-ns gate cases, boolean/malformed mutants, real four-repeat run |
| Identity/finalization | pin every imported value and changed source before build | final sources/head/external files match | any mutation or cleanup/ceiling failure prevents publication | result finalized outside helper/temp contexts | identity mutants, forced finalization failures, clean-head real run |

Concurrent calls are independent reads over caller-owned ranges. Overlap needs no exclusion because
the native function writes neither range. Whole-program compilation is the shipped path; per-unit
compilation is N/A because Align modules are built through their importing executable graph.

## 4. Implementation and verification map

1. Retain the return/tag/validation contract inside the byte-identical shared shim region and its
   direct native vectors.
2. Retain real/stub slot entries that validate actual host visibility and exact extent before
   calling the byte primitive, the safe FFI wrapper, and both direct callsites.
3. Add the guarded AArch64 4-by-4 V exact-success scan with scalar remainder and mismatch fallback;
   retain the scalar implementation as the complete non-AArch64 path.
4. Retain the source-pinned item 61 performance runner over the unchanged item 60 helper and validate
   exact gate arithmetic and cleanup-before-publication.
5. Run focused owners and one clean-head four-repeat qualification. Record `MET` or `NOT_MET` here,
   in the roadmap, and in `HANDOFF.md`; ship the intervention only on `MET`. The review repair
   changed a qualification-owned source, so its clean-head run is the final decision and overrides
   the earlier pre-review result.
6. Complete one comprehensive review, consolidate valid findings, rerun affected owners and
   exact-head preflight, publish, merge, and continue to the next eligible roadmap capability.

No `make ci`, installed platform profile, portfolio, stress suite, cache replay, or unrelated
benchmark is selected. The shared-shim ABI, decode consumer, direct owner vectors, full-request
qualification, and performance decision are one consumer-complete capability.

## 5. Author consistency pass

The ledger and matrix agree that item 60 measured the complete `verify_plane` boundary and did not
attribute its sub-operations. Intervention A retained shape reads and both copies and missed the
full-helper gate despite reducing the boundary. Intervention B retained shape reads, removed only
the two host-to-host readback copies, and also missed. Intervention C retained that safe direct
boundary and changed only the exact-success V traversal on the measured AArch64 host; a mismatch
always fell back to the original traversal before returning. Review exposed an alignment promise
absent from that implementation. The repaired byte-load form closed the defect, but its clean-head
full-helper result missed the gate. The ledger's removal rule therefore restores item 60's
production behavior; only the decision document and source-pinned qualification owner remain.

## 6. Recorded result

Intervention A was qualified on clean head `9b940fd94acaeea839725f79f7092882e722b057`:

- full-helper samples `[17459817958,18555159375,18069202584,19776245125]`, median
  18,312,180,979 ns, gain 434,205,791 ns / 23,162 ppm: `NOT_MET`;
- complete plane-boundary samples `[1842072817,1789703512,1914191744,1987025254]`, median
  1,878,132,280 ns;
- all four pairs reproduced the fixed 86-token output/hash, exact native lifetimes, twelve clean
  isolation boundaries, fixed cache state, and cleanup.

Intervention B was qualified on clean head `c7f5eadf9229422190b056fa507bf3be8ce91994`:

- full-helper samples `[17512885500,18764484375,19480712541,19627866375]`, median
  19,122,598,458 ns, gain -376,211,688 ns / -20,069 ppm: `NOT_MET`;
- complete plane-boundary samples `[1672093678,1821507431,1850145250,1869787530]`, median
  1,835,826,340 ns;
- all four pairs reproduced the fixed 86-token output/hash, exact native lifetimes, twelve clean
  isolation boundaries, fixed cache state, and cleanup in 109,940,548,500 ns.

Intervention C was qualified before review on clean head
`1e121c41c58f39c584bdc43c864aeccae6b16c04`:

- full-helper samples `[16554919250,17140798625,16882099208,17146960833]`, median
  17,011,448,916 ns, gain 1,734,937,854 ns / 92,547 ppm: `MET`;
- complete plane-boundary samples `[751961094,781287535,778137933,791857277]`, median
  779,712,734 ns, down 2,192,612,205 ns / 737,675 ppm from item 60;
- the candidate was 797,618,515 ns below the precommitted 17,809,067,431-ns ceiling;
- all four pairs reproduced the fixed 86-token output and
  `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52`, exact native
  lifetimes (2,958 buffers/gallocrs, 6,090 contexts, one backend and resident wrap, all balanced and
  released), twelve clean isolation boundaries, fixed cache state, and cleanup in 100,934,477,959
  ns.

Comprehensive review of head `fd9835ffa691e8b5d6d06e777ada6d20cf3327a7` found one valid P2:
typed `uint32_t *` NEON loads violated the byte-range ABI for unaligned inputs. Consolidated repair
`549179f` switched to byte-aligned vector loads and added an unaligned tile regression. Its required
clean-head qualification at `4e1f53d208191d274c4ef9733059afd290bb9c4f` recorded:

- full-helper samples `[16670214417,19040051292,19655093584,18174675459]`, median
  18,607,363,375 ns, gain 139,023,395 ns / 7,416 ppm: `NOT_MET`;
- complete plane-boundary samples `[767843454,888905756,857257604,819760912]`, median
  838,509,258 ns;
- the candidate was 798,295,944 ns above the precommitted 17,809,067,431-ns ceiling;
- all four pairs still reproduced the fixed output/hash, exact native lifetimes, twelve clean
  isolation boundaries, fixed cache state, and cleanup in 108,080,301,708 ns.

The qualification used `ggml.h` (112,592 bytes,
`6fe9b62d3ea48c2de82cce6e9e06d3ae4f0de34f4b5831399c49c099badefb09`), `ggml-alloc.h`
(3,753 bytes, `94e4cd069b9313b2ceb35dacec901981e0bb478d8bb31035b7126be091998c23`), and
`ggml-backend.h` (25,374 bytes,
`46d84cb998105f871240864fd0f55446939a2fe86c5c281afa63a010fb1f65a2`). Final review required
these direct build inputs to become exact candidate fields and to be checked both before the shim
build and after measurement.

The final decision is `NOT_MET`. All three production interventions and their owner-test additions
are removed; no fixed-request performance claim or non-AArch64 claim ships from item 61.
