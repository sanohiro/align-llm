# R8 OLMoE plane round-trip boundary

Status: active, 2026-09-04

Roadmap owner: item 61, `R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY`

## 1. Decision owned

Item 60 measured the complete decode-only `verify_plane` call at a 2,972,324,939-ns median and
991,445 ppm of its diagnosed parent. That clock includes concat shape reads, two `slot_get`
operations, scalar K/V comparison, and result accounting; it does not attribute cost among them.

This capability replaces only the scalar comparison implementation with one bounded shared-shim
call per K/V tensor while retaining every other operation in the measured boundary. The choice is
an intervention, not a claim about which sub-operation owns the measured time. It ships only if the
same complete fixed request preserves correctness and improves full-helper wall time by at least
50,000 ppm. A miss records `NOT_MET` and does not authorize the intervention.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY`; production owners are `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`, `src/ggml_ffi.align`, and `src/moe_decode_step.align`; qualification owner is `scripts/run-olmoe-plane-roundtrip-boundary` |
| Consumer | OLMoE sampled decode oracle B after each routed-layer graph; it must still compare the graph-consumed K/V concat against the canonical plane through the just-written column |
| Native ABI | `int64_t align_ggml_compare_kv_plane(const void *consumed, int64_t consumed_bytes, const void *plane, int64_t plane_bytes, int64_t plane_base, int64_t head_dim, int64_t n_head_kv, int64_t columns, int32_t layout)`; no ggml type crosses the ABI |
| Layout tags | `0` is K and `1` is V; every other `int32_t` value is invalid |
| Return encoding | `0` means byte-identical; positive `column + 1` means mismatch at the first column reached by the exact traversal below; negative values are existing shim status codes and this function emits only `ALIGN_GGML_INIT` or `ALIGN_GGML_BOUNDS` |
| Canonical source | `plane_base + (lane + head_dim * (head + n_head_kv * column)) * 4`, for `head = 0 .. n_head_kv`, `column = 0 .. columns`, and `lane = 0 .. head_dim` |
| K consumed layout/order | consumed offset `(lane + head_dim * (column + columns * head)) * 4`; observable first mismatch follows `head`, then `column`, then `lane`; an implementation may compare one contiguous lane row at a time because only its column is returned |
| V consumed layout/order | consumed offset `(column + columns * (lane + head_dim * head)) * 4`; observable first mismatch follows `head`, then `lane`, then `column` |
| Byte semantics | compare the four stored bytes of every F32 lane exactly; no float conversion, tolerance, endianness reinterpretation, or NaN normalization |
| Native validation order | reject a null range with `ALIGN_GGML_INIT`; then reject negative lengths/base, nonpositive dimensions, or an unknown layout with `ALIGN_GGML_BOUNDS`; then checked-multiply `head_dim * n_head_kv * columns * 4`; then require that span within `consumed_bytes` and `[plane_base, plane_base + span)` within `plane_bytes` and representable as `size_t`; read no byte before all checks pass |
| Ownership/allocation | both byte ranges remain borrowed and caller-owned; overlap is allowed because both are read-only; the function writes, allocates, frees, retains, and opens nothing and has no process-global state |
| Align wrapper | `ggml_ffi.compare_kv_plane(...) -> Result<i64, Fault>` passes both slice lengths, maps raw `0` to `Ok(-1)`, raw positive `n` to `Ok(n - 1)`, and a negative status through the existing R5 fault mapping; one `unsafe` block contains the one foreign call |
| Decode integration | retain the existing span and concat-shape checks and both exact `slot_get` calls into the existing `node_window`; replace `compare_past_k` and `compare_past_v` with the wrapper using layout tags K and V; no new allocation or native owner |
| Success | both calls return `-1`; add the unchanged `2 * columns * plane_column_bytes(g)` to `roundtrip_bytes_compared` exactly once |
| Mismatch/failure | preserve the current first K-before-V priority and exact tensor/column detail; a native validation fault is the owning tensor at column `-1` and the existing `R6M_PLANE_MISMATCH`; prior shape and `slot_get` failures keep their current code, detail, and early return |
| Forced regressions | retain `slot_get`, so the checked-in routed writeback-offset perturbation still changes the readback before comparison and must produce the existing layer/tensor/column/step record |
| Existing records | provider output and item 57, item 59, and item 60 helper schemas are byte-shape unchanged; item 60's `plane_roundtrip_compare_ns` continues to time the complete `verify_plane` call, not the native comparison alone |
| Fixed baseline | item 60 full-helper samples `[17704139042,18412456541,19080317000,19520549709]`, integer median 18,746,386,770 ns, on its exact Apple M1 host and fixed request |
| Performance gate | floor 50,000 ppm, rounded-up minimum gain 937,319,339 ns; candidate four-sample median must be at most 17,809,067,431 ns; equality is `MET`, anything slower is `NOT_MET` |
| Qualification | four sequential fresh-process maximum-2/maximum-128 pairs through the unchanged item 60 helper; exact prefix, 86-token output/hash, native lifetimes, twelve isolation boundaries, cache, host, and cleanup all remain mandatory; record candidate full-helper wall and complete plane-boundary medians |
| Result | one exact-key schema-1 `R8_OLMOE_PLANE_ROUNDTRIP_BOUNDARY` JSON document on stdout and one concise stderr summary; no complete document on failure |
| Inputs/identity | independently pin item 60 workload/evidence, predecessor runner and helper chain, decode/outcome/FFI sources, both C shims and their shared region, build script, model, pack, geometry, server, Align revision/compiler, ggml libraries, C compiler/version, task, prompt, exact token chain, built helper/shim, clean head, and baseline-host fingerprint |
| Validation order | argument/prerequisite precedence; scrubbed environment/linker search; fixed host, clean head, process absence, imported and external identities; exact-source build; four conditioned records; schema/output/lifetime/repeatability; performance aggregate; final identities/head; exit helper and temporary contexts; cleanup-inclusive ceiling; validation; publication |
| Failure/cleanup | nonzero and no complete document for invalid ABI input, identity/host/source/process drift, malformed result, output/lifetime drift, child failure, source mutation, cleanup failure, or gate-run ceiling excess; missing prerequisites retain the one declared N/A path; signal and timeout cleanup stop owned children, restore any prior root helper, and remove the temp tree |
| Persisted/cache identity | N/A: no persisted format, cache policy, model, pack, geometry, or provider schema changes; qualification stdout is not persisted by the runner |
| Cost ceiling | one monotonic 8-minute ceiling covers shim/helper build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; each child retains its narrower bound |
| Acceptance evidence | author consistency pass; direct shared-shim exact/mismatch/refusal vectors; `make fmt`; pinned helper build; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation and item 57→61 self-test chain; one complete real qualification; `git diff --check`; one comprehensive review; exact-head `scripts/pre-pr --owner-test R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY -- scripts/run-olmoe-plane-roundtrip-boundary --self-test` |

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
| Real/stub parity | function and tags live inside the byte-identical shared region | both compiled forms expose the same ABI | shared-region drift fails the existing smoke | no owner | shared-region identity owner plus direct stub call |
| Safe wrapper | compiler supplies both slice lengths and one fixed layout tag | `0 -> -1`, positive result subtracts one | negative result maps through existing fault table | borrows only; one unsafe call | pinned executable build and direct wrapper callsite compilation |
| Verify K | existing shape check and `slot_get` precede native compare | equality continues to V | mismatch records K and exact column; fault records K/-1; V is skipped | existing window and graph owners unchanged | current routed success and forced writeback-offset failure |
| Verify V | reached only after successful K | equality commits unchanged byte total | mismatch records V and exact column; fault records V/-1 | existing window and graph owners unchanged | native V vector plus routed success |
| Historical helpers | same shared helper and three fixed entrypoints | item 57/59/60 exact key sets remain | malformed additions still reject | invocation-owned | self-test chain and real maximum-2/full item 60 records |
| Performance repetition | fixed host, clean head, exact item 60 baseline, fresh short/full child pair | four valid samples produce median/gain and `MET` only at/below ceiling | drift or one invalid sample prevents result | twelve absence checks; child reaped | exact/one-ns gate cases, boolean/malformed mutants, real four-repeat run |
| Identity/finalization | pin every imported value and changed source before build | final sources/head/external files match | any mutation or cleanup/ceiling failure prevents publication | result finalized outside helper/temp contexts | identity mutants, forced finalization failures, clean-head real run |

Concurrent calls are independent reads over caller-owned ranges. Overlap needs no exclusion because
the native function writes neither range. Whole-program compilation is the shipped path; per-unit
compilation is N/A because Align modules are built through their importing executable graph.

## 4. Implementation and verification map

1. Add the return/tag/validation contract once inside the byte-identical shared shim region and add
   direct native vectors to the existing layer-forward owner.
2. Add the safe FFI declaration/wrapper and replace only the two scalar compare functions at the
   existing post-`slot_get` callsites.
3. Add the source-pinned item 61 performance runner over the unchanged item 60 helper and validate
   exact gate arithmetic and cleanup-before-publication.
4. Run focused owners and one clean-head four-repeat qualification. Record `MET` or `NOT_MET` here,
   in the roadmap, and in `HANDOFF.md`; ship the intervention only on `MET`.
5. Complete one comprehensive review, consolidate valid findings, rerun affected owners and
   exact-head preflight, publish, merge, and continue to the next eligible roadmap capability.

No `make ci`, installed platform profile, portfolio, stress suite, cache replay, or unrelated
benchmark is selected. The shared-shim ABI, decode consumer, direct owner vectors, full-request
qualification, and performance decision are one consumer-complete capability.

## 5. Author consistency pass

The ledger and matrix agree that item 60 measured the complete `verify_plane` boundary and did not
attribute its sub-operations. The intervention retains shape reads and both `slot_get` calls,
changes only caller-owned byte comparison, and can claim success only through the full-helper gate.
Every return state maps to one wrapper and decode result, all validation precedes reads, both shims
share one byte-identical implementation, and no new owner or schema is introduced.

## 6. Recorded result

Pending implementation, focused verification, and one clean-head four-repeat qualification.
