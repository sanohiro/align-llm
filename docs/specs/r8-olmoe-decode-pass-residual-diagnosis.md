# R8 OLMoE decode-pass residual diagnosis

Status: active, 2026-09-04

Roadmap owner: item 59, `R8-OLMOE-DECODE-PASS-RESIDUAL-DIAGNOSIS`

## 1. Decision owned

Item 58 reduced the selected KV staging boundary and recorded a post-review 18,429,017,312-ns
full-helper median on the pinned Apple M1 host. Its same four records leave 4,172,949,292 ns in the
decode-pass residual after pack/resident staging, claim reads, compute, routing, and KV-plane
transfer are removed. That residual is slightly larger than compute and cannot be named as graph
lifecycle without direct evidence.

This capability partitions only that residual into context/buffer/tensor setup, graph
build/allocation, generic tensor transfer/digest, graph teardown, and an explicit remainder. It
retains item 58's exact request, model, provider mode, output/token chain, cache budget, fresh
process isolation, native lifetime, host fingerprint, and four conditioned repetitions. The
largest median sub-bucket may select a narrower implementation contract only when it clears the
precommitted materiality floor. This diagnosis changes no graph, ownership, provider, cache, token,
or output behavior and makes no performance-win claim.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-DECODE-PASS-RESIDUAL-DIAGNOSIS`; `scripts/run-olmoe-decode-pass-residual-diagnosis`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | the next R8 investment decision after item 58, selecting one directly measured residual sub-bucket or one still narrower diagnosis |
| Fixed request | item 58's byte-identical task/system/user prompt, OLMoE model, AlignPack, geometry, partial-LRU budget 975,175,680 bytes, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | four sequential fresh-process repetitions; each maximum-2 result is the exact prefix of the following maximum-128 result; zero processes matching both pinned llama-server and model paths before, between, and after each pair |
| Shared counters | add signed 64-bit totals `graph_setup_ns`, `graph_build_alloc_ns`, `generic_transfer_digest_ns`, and `graph_teardown_ns`, plus four corresponding `remaining_decode_*` totals; `empty_outcome` initializes all eight to zero |
| Context/buffer setup | time slot reset, context creation, host-buffer wrapping or input-buffer allocation, tensor declaration/placement, alignment and pointer-identity checks; exclude input/output `slot_set`/`slot_get`, graph construction/allocation, compute, claim staging, routing, plane work, and teardown |
| Graph build/allocation | time graph and gallocr creation, node construction, output marking, graph expansion, reserve, allocation, and graph metadata reads; exclude compute and all other buckets |
| Generic transfer/digest | time non-plane, non-routing input/output slot transfers, carry staging, residual/norm/logits digests, and top-k extraction/rendering; exclude claim reads, argsort routing, KV staging/readback, graph work, and teardown |
| Graph teardown | time the existing ordered gallocr/context/buffer teardown calls; ownership, order, counts, and failure convergence remain unchanged |
| Success semantics | broad totals may include any attempted graph; each `remaining_decode_*` field adds only the exact broad-counter delta of one successfully completed step after the first, at the existing successful commit point; first decode, EOG/maximum exits, and failed partial steps add zero |
| Exact accounting | item 58's `pass_residual_ns` equals setup plus graph build/allocation plus generic transfer/digest plus graph teardown plus `other_ns`; all five values are nonnegative and the four direct clocks are disjoint subsets of the old residual |
| Qualification helper | new `olmoe_decode_pass_residual_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; maximum is only 2 or 128; preserve item 57's exact helper record and add one exact `pass_residual` object without changing prior helpers or schemas |
| Helper detail | `pass_residual` has exact keys `total_ns`, `context_buffer_setup_ns`, `graph_build_alloc_ns`, `generic_transfer_digest_ns`, `graph_teardown_ns`, and `other_ns`; maximum 2 requires all zero, maximum 128 requires positive total/direct clocks and the exact equation |
| Fixed baseline | item 58 post-review full-helper walls `[17827657250,17850131083,19007903542,19211017875]`, integer median 18,429,017,312 ns; immutable and never recomputed from item 59 samples |
| Materiality floor | 50,000 ppm of the fixed baseline, rounded up: 921,450,866 ns per full request |
| Opportunity/decision | take four-sample medians of `CONTEXT_BUFFER_SETUP`, `GRAPH_BUILD_ALLOC`, `GENERIC_TRANSFER_DIGEST`, `GRAPH_TEARDOWN`, and `OTHER_PASS_RESIDUAL`; choose the largest with ties in that order; below floor yields `NO_MATERIAL_BUCKET`; direct winner yields `MEASURED_BUCKET_ELIGIBLE`; `OTHER_PASS_RESIDUAL` yields `OTHER_PASS_NEEDS_DIAGNOSIS` |
| Result | one exact-key schema-1 `R8_OLMOE_DECODE_PASS_RESIDUAL_DIAGNOSIS` JSON document on stdout and one concise stderr summary; no complete document on failure |
| Inputs/identity | independently pin imported item 58 workload/evidence values, old and new helper sources, model, pack, geometry, server, Align revision/compiler, ggml libraries, C compiler/version, task, prompt, exact token chain, built helper/shim, clean head, and item 58's exact baseline-host fingerprint |
| Validation order | argument/prerequisite precedence; scrubbed environment/linker search; fixed host, clean head, process absence, imported and external identities; exact-source build; four conditioned records; schema/accounting/output/lifetime/repeatability; aggregate/decision; final identities/head; ceiling; publication |
| Failure | nonzero and no complete document for invalid arguments, identity/host/source/process drift, malformed or overlapping clocks, failed accounting, output/lifetime drift, child failure, source mutation, or ceiling excess; missing prerequisites keep the one declared N/A path |
| Ownership/allocation | counters are scalars in the invocation-owned outcome; no new native owner; helper/runner/temp state is invocation-local and removed by its current owner |
| Persisted/cache identity | N/A: no production, cache, model, result, or prior helper schema changes; stdout evidence is not persisted by the runner |
| Cost ceiling | one monotonic 8-minute ceiling covers helper/shim build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; each child retains a narrower bound |
| Acceptance evidence | `make fmt`; pinned new-helper build; `make layer-forward-smoke`; `make runtime-provider-smoke`; Python compilation; focused self-test; one complete real diagnosis; `git diff --check`; one comprehensive review; exact-head `scripts/pre-pr --owner-test R8-OLMOE-DECODE-PASS-RESIDUAL-DIAGNOSIS -- scripts/run-olmoe-decode-pass-residual-diagnosis --self-test` |

The capability makes one fixed-request, one-model, one-host attribution. Cross-host, GPU,
throughput, arbitrary-task, cache-policy, persistent-state, public-provider, and speedup claims are
N/A. The new helper and result are qualification-only JSON text; no production renderer exposes the
new counters.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Shared outcome | eight zeroed `i64` scalars | broad timers accumulate disjoint exact operations | no new error; invalid delta cannot publish | failed/first steps add no remaining total | no owner | zero/positive source assertions, compile owner, real accounting |
| Layer graph | snapshot direct operations around existing calls | two graph phases contribute setup/build/transfer/teardown without compute/claim/routing/plane overlap | existing first error and ordered convergence unchanged | guarded blocks retain old reachability | same teardown once | old smoke/lifetime owners plus exact helper equations |
| End graph | same four timers around embedding/head operations | setup/build/transfer/teardown are disjoint | existing failure path unchanged | guarded blocks retain old reachability | same teardown once | old smoke/lifetime owners plus real balanced counts |
| Step commit | snapshot broad counters immediately before `decode_pass` | successful remaining step adds exact deltas | negative/overlapping subtotal rejects helper | first decode and partial step add zero | locals die per step | maximum-2 zero, full positive/equality, malformed mutants |
| Helper | item 57 preparation and item 59 detail | one exact record | bad arguments/output/accounting exits before print | N/A | invocation drops state | pinned build and schema self-test |
| Repetition | fixed host and process absence; fresh short/full children | exact prefix/output four times | drift aborts without result | no partial sample/result | inherited signal/deadline cleanup | twelve absence checks and repeatability |
| Aggregate | four exact full records and immutable item 58 baseline | medians and deterministic decision | boolean/missing/duplicate/arithmetic/baseline drift rejects | no partial aggregate | N/A | each decision class, tie, below/at floor |
| Identity | pin imports, sources, host, tools, externals, and head | final values unchanged | any nested value or digest drift fails | missing prerequisite emits N/A | restore generated root binary | imported/nested/host mutants and real recheck |
| Signal/deadline | inherited handlers and one monotonic deadline | N/A | timeout/interruption exits nonzero | no complete JSON | stop child and restore temp/build state | inherited forced timeout/restoration tests |

Generic monomorphization, move/source-nulling, concurrent calls, external server ownership, and
persisted migration are N/A. The shared record remains invocation-owned, decode is synchronous,
and timing adds no borrow, allocation, or native lifetime.

## 4. Implementation and verification map

1. Add the eight shared scalar counters and place non-overlapping clocks around the existing graph
   operations; snapshot them at the existing successful-step boundary.
2. Add a qualification-only helper with item 57's old exact record plus the new residual detail.
3. Add a bounded runner that imports item 58's identity/process primitives, independently pins its
   baseline and sources, and owns the new schema, equations, medians, and decision.
4. Run narrow source owners and one real four-repeat diagnosis; record the selected successor in
   this document, the roadmap, and `HANDOFF.md`.
5. Complete one comprehensive review, consolidate valid findings, rerun affected owners and
   exact-head preflight, publish, merge, and continue to the selected capability.

The consumer-complete diff may approach 1,000 hand-written lines because the exact new helper and
runner must ship with the shared counters they alone consume. Keeping the prior helper schemas
unchanged avoids invalidating item 57/58 evidence; splitting producer, helper, and validator would
leave dormant counters or an unvalidated result and duplicate the same accounting proof across PRs.
No `make ci`, installed platform profile, portfolio, stress suite, cache replay, or unrelated
benchmark is selected.

## 5. Author consistency pass

The ledger and matrix agree on four direct non-overlapping clocks, one explicit remainder, the
existing successful-step commit, item 58's immutable fixed-host baseline, four conditioned repeats,
and the 921,450,866-ns floor. Every counter has one owner and one helper/result field; no prose
renames residual work or authorizes an optimization before measurement.
