# R8 OLMoE KV-plane staging transfer

Status: complete, 2026-09-04

Roadmap owner: item 58, `R8-OLMOE-KV-PLANE-STAGING-TRANSFER`

## 1. Capability owned

Item 57 measured the fixed isolated OLMoE request's remaining decode at a 25.267-second median.
The largest directly measured bucket was `KV_PLANE_TRANSFER` at 11.555 seconds, of which the
existing scalar CPU K/V staging loops contributed 11.548 seconds and plane readback only 0.008
seconds. Those loops read one little-endian `u32` from the canonical KV plane and append it to an
Align buffer for every scalar of every past token in every layer.

This capability replaces only those two scalar loops with one bounded call to the repository-owned
C shim. The call transposes the canonical K and V ranges into one caller-owned, pre-sized staging
range; it does not change the plane layout, graph input layouts, ggml graph, cache policy, provider
lifetime, sampling, tokens, or output. The shim already owns the repository's unavoidable native
FFI boundary, and the shipped Align surface cannot express an overwrite of a pre-sized buffer
without it. This is an application concern, not a new Align capability request.

The implementation may ship only if item 57's exact conditioned four-repeat workload reproduces
the fixed output and balanced lifetimes and reduces its immutable 30,450,856,583-nanosecond full
helper wall median by at least 50,000 ppm. A candidate median above 28,928,313,753 nanoseconds does
not ship.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-KV-PLANE-STAGING-TRANSFER`; production owner `moe_decode_step.decode_pass`; model-free owner `gmake layer-forward-smoke`; performance owner `scripts/run-olmoe-kv-plane-staging-transfer` with no arguments for the opt-in real run and `--self-test` for its model-free contract |
| Consumer | each OLMoE decode layer that turns the invocation-owned canonical KV plane into ggml's K-past and V-past graph inputs |
| Native API | `align_ggml_stage_kv(const void *plane, int64_t plane_bytes, int64_t k_base, int64_t v_base, void *stage, int64_t stage_bytes, int64_t head_dim, int64_t n_head_kv, int64_t n_past) -> int32_t`; declared once in `ggml_ffi.align` and implemented byte-identically in the shared real/stub shim region |
| Input layout | canonical plane bytes remain layer-major, then K/V, then `{head_dim, n_head_kv, column}` f32 little-endian scalars; `k_base` and `v_base` name the current layer ranges and plane capacity remains the existing caller-owned slice length |
| Output layout | `stage_bytes` must equal `2 * head_dim * n_head_kv * n_past * 4`; first half is K `{head_dim, n_past, n_head_kv}`, second half is V `{n_past, head_dim, n_head_kv}`, byte-identical to the removed scalar loops |
| Bounds/overflow | pointers must be non-null; bases, byte lengths, and dimensions must be nonnegative; dimensions must be positive; every multiplication, base-plus-span, and pointer-range calculation must fit its owning signed or address-sized type; both complete source ranges and the exact destination range are validated before any write |
| Aliasing | source and destination address ranges must not overlap; overlap is `ALIGN_GGML_BOUNDS`, checked before any write. The production caller uses distinct invocation-owned allocations |
| Native implementation | K copies one contiguous `head_dim * 4` block per head/column; V copies one four-byte scalar per head/lane/column because its required column-major graph input is a transpose. The shim allocates, opens, retains, or frees nothing |
| Align wrapper | `ggml_ffi.stage_kv` supplies actual slice lengths, performs one unsafe foreign call, and maps the status through the existing R5 result vocabulary. No caller-provided length can exceed a borrowed view |
| Allocation | one invocation-owned `buffer(2 * past_bytes)` replaces two `buffer(past_bytes)` values per layer. The existing zero-chunk priming helper materializes its exact logical length before native overwrite; the buffer dies after that layer's graph call |
| Timing | the existing `Plane.upload_ns` begins before priming and ends after the native staging call, so allocation materialization and all staging work remain visible rather than being moved outside the selected clock |
| Failure | validation failure returns before writing any destination byte; the Align wrapper yields the existing `R5_SHAPE` family with the layer staging label; `decode_pass` records its existing plane-unavailable failure and constructs no layer graph from partial staging |
| Validation order | existing geometry/plane/past-size validation; allocate staging capacity; start upload clock; prime exact output length; call native validation in pointer, signed-domain, checked-size, exact-output, source-bounds, then non-overlap order; stop upload clock; require exact two-half views; construct graph |
| Existing behavior | plane writes/readback, graph nodes and shapes, token order, output digest, cache identity/policy, provider API, native owner counts, CLI modes, and existing JSON schemas are byte- and meaning-unchanged |
| Persisted/cache identity | N/A: staging is ephemeral and invocation-owned; no persisted or cache format changes |
| Fixed baseline | item 57 full helper walls `[28322991875,30172193417,30729519750,30967544875]`, integer median 30,450,856,583 ns; immutable and never recomputed from candidate samples |
| Shipping gate | four candidate full helper walls under item 57's exact fresh-process conditioning/isolation protocol; `gain_ppm = (baseline_median - candidate_median) * 1,000,000 // baseline_median`; ship only for `gain_ppm >= 50,000`, equivalently candidate median at most 28,928,313,753 ns, with exact output and balanced lifetimes in all repetitions |
| Result | one exact-key schema-1 `R8_OLMOE_KV_PLANE_STAGING_TRANSFER` JSON document on stdout and one concise stderr summary; decision `MET` or `NOT_MET`; no complete document on failure |
| Inputs/identity | independently pin item 57's workload, baseline, model, pack, geometry, server, Align revision/compiler, ggml libraries, C compiler/version, task, prompt, exact token chain, helper, shim, linker search, and clean align-llm head |
| Cost ceiling | one monotonic 8-minute ceiling covers helper/shim build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; each child retains a narrower bound |
| Acceptance evidence | `gmake fmt`; `gmake layer-forward-smoke`; `gmake runtime-provider-smoke`; Python compilation; focused performance self-test; one complete real four-repeat qualification; `git diff --check`; one comprehensive review; exact-head `scripts/pre-pr --owner-test R8-OLMOE-KV-PLANE-STAGING-TRANSFER -- scripts/run-olmoe-kv-plane-staging-transfer --self-test` |

The capability makes one fixed-request, one-model, one-host performance claim. Cross-host, GPU,
throughput, arbitrary-task, cache-policy, provider-lifetime, and public-API gains are N/A. The new C
symbol is repository-internal ABI, but it is specified exactly because an unsafe boundary and four
modules must agree on it.

## 3. Qualification schema

The runner reuses item 57's exact helper record validation and emits these exact top-level keys:

```text
schema_version
artifact_kind
status
model
baseline
candidate
task
environment
samples
aggregate
elapsed_ns
```

`baseline` contains `full_helper_wall_values_ns`, `full_helper_wall_median_ns`, `floor_ppm`, and
`candidate_ceiling_ns`. Each of four `samples` contains item 57's exact `index`, `conditioning`,
`full`, `full_helper_wall_ns`, and three-boundary `isolation` record. `aggregate` contains
`candidate_full_helper_wall_values_ns`, `candidate_full_helper_wall_median_ns`,
`candidate_plane_upload_values_ns`, `candidate_plane_upload_median_ns`, `baseline_median_ns`,
`gain_ns`, `gain_ppm`, `floor_ppm`, `candidate_ceiling_ns`, and `decision`.

All numeric fields are non-boolean integers. The fixed output, token prefix, successful-phase
equations, and balanced native lifetime rules are exactly item 57's. `MET` requires nonnegative
`gain_ns`, `gain_ppm >= 50,000`, and candidate median at or below the integer ceiling; otherwise a
valid exact run records `NOT_MET`. A malformed or inexact run is failure, not `NOT_MET`.

## 4. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Shared shim | receive two borrowed ranges and signed scalar geometry | validate all ranges, copy K blocks, transpose V scalars | null, negative/zero, overflow, wrong output size, source OOB, or overlap returns before write | zero work after refusal | owns no allocation | `run-layer-forward-smoke` direct stub-symbol exact K/V vector plus sentinel-preserving refusal vectors; shared-region equality |
| Align wrapper | pass actual slice lengths and one label | one native call maps `OK` | known status maps to existing R5 fault; unknown status remains ABI fault | no second call | borrows only | compile owner plus real fixed request |
| Decode staging | allocate one combined capacity and start existing clock | prime, transpose, split exact K/V views, then build unchanged graph | priming/native/view failure takes existing plane failure; no graph consumes partial data | existing loop stops | combined buffer dies after layer graph | source owner assertions, layer smoke, exact real output/token chain |
| Plane/cache | retain old plane bases, stride, writeback, and readback | graph consumes byte-identical layouts | oracle/lifetime mismatch rejects qualification | existing failure convergence | old native owners unchanged | existing OLMoE decode smoke and four real balanced runs |
| Repetition | require process absence; fresh max-2 then max-128 helpers | exact prefix and full output four times | process/helper/repeatability drift aborts | no partial result | active child follows inherited signal/deadline cleanup | inherited item 57 self-tests plus twelve real absence checks |
| Aggregate | immutable baseline and four candidate walls | integer median/gain and deterministic decision | baseline, ceiling, key, boolean, or arithmetic drift rejects | no partial aggregate | N/A | below/at/above threshold self-test vectors |
| Identity | pin imports before build; capture helper/shim/head | final hashes/head unchanged | predecessor, source, tool, or external drift fails | missing prerequisite emits inherited N/A line | restore root build product | imported-constant mutation and real recheck |
| Signal/deadline | install handlers before real work | N/A | interruption/timeout exits nonzero | no complete JSON | stop child; restore helper/temp state | inherited forced timeout/restoration self-tests |

Concurrent mutation, generic monomorphization, move/source-nulling, external server ownership, and
persisted migration are N/A. Decode is synchronous, plane and stage are disjoint invocation-owned
ranges, the wrapper borrows both for one call, and no new value outlives the layer iteration.

## 5. Implementation and verification map

1. Add the shared bounded staging symbol and safe Align wrapper, with byte-identical real/stub C.
2. Replace the two scalar staging functions with one combined primed range and preserve the entire
   preparation interval inside `Plane.upload_ns`.
3. Extend the existing hosted layer owner with exact layout and no-partial-write native vectors.
4. Add the bounded item 58 qualification runner by reusing item 57's execution primitives while
   independently pinning the imported workload and owning the new result arithmetic.
5. Run source owners and the real four-repeat qualification. Record `MET` before publishing the
   intervention; if it is `NOT_MET`, remove the production intervention and record the negative
   result without claiming a win.
6. Complete one comprehensive review, consolidate valid findings, rerun affected owners and
   exact-head preflight, publish, merge, and continue to the next eligible roadmap capability.

No `make ci`, installed platform profile, 40-prompt corpus, validator, sampled coding portfolio,
stress suite, cache replay, or unrelated benchmark is selected. This is one consumer-complete
change: separating the native primitive, its only production consumer, its correctness owner, or
its shipping qualification would leave an unsafe or unqualified performance boundary.

## 6. Author consistency pass

The ledger, schema, closure matrix, and implementation map agree on one combined caller-owned
destination, exact K/V byte layouts, validate-before-write behavior, the existing error family and
upload clock, the immutable item 57 baseline, four fresh conditioned repetitions, and the
50,000-ppm gate. No prose authorizes a plane, graph, cache, provider-lifetime, token, or output
change. Section 7 maps every applicable cell to the shipped diff and passing evidence.

## 7. Recorded result and final mapping

The complete run at clean head `b3583fe43f9a7350337264e84220e1a2a5dddd4e` finished in
108.362 seconds and recorded `MET`. All four fresh maximum-2 conditioning requests were exact
prefixes of their maximum-128 requests. All four full requests reproduced the fixed 87-token chain
and output digest, balanced 2,958 ggml buffers, 6,090 contexts, one backend, 2,958 allocators, and
one resident wrap, and recorded zero matching llama.cpp model processes at all twelve required
before/between/after boundaries.

Candidate full helper walls were
`[16405544166,16623844667,17339086750,17880418791]` ns, for a
16,981,465,708-ns median. Against the immutable 30,450,856,583-ns baseline, that removes
13,469,390,875 ns, or 442,332 ppm, and is 11,946,848,045 ns below the precommitted candidate
ceiling. Candidate upload samples were
`[1835600002,1859415586,1969469120,2025707279]` ns, for a 1,914,442,353-ns median: the selected
boundary fell by 9,633,092,741 ns, or 834,212 ppm, from item 57's 11,547,535,094-ns median.
Remaining decode fell from 25,267,487,582 ns to a 12,879,146,307-ns median.

The shared real/stub functions and `ggml_ffi.stage_kv` implement the ledger's exact ABI and
validate-before-write ownership boundary. `moe_decode_step.decode_pass` owns the one combined
primed buffer, timed native call, two exact views, and unchanged failure convergence. The hosted
layer owner exercised the non-square K/V layout and null, negative, zero, overflow, wrong-size,
out-of-bounds, and overlap refusals without partial writes. `gmake layer-forward-smoke`, `gmake
runtime-provider-smoke`, formatting, Python compilation, the focused self-test, and the real run
all passed.

After this intervention, the four sample records give a 3,805,899,547-ns `PASS_RESIDUAL` median,
larger than compute at 3,615,480,386 ns, claim I/O at 3,426,040,742 ns, and KV-plane transfer at
1,921,874,253 ns. Item 57's decision rule therefore selects item 59, a narrower decode-pass
residual diagnosis; this result does not rename the residual or authorize an implementation seam
inside it.
