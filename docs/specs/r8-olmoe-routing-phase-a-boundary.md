# R8 OLMoE routing phase-A boundary

Status: complete, 2026-09-05

Roadmap owner: item 63, `R8-OLMOE-ROUTING-PHASE-A-BOUNDARY`

## 1. Decision owned

Item 62 measured the existing OLMoE decode phase-A graphs, which contain attention,
normalization, router scoring, and argsort, at a 2,939,392,017-nanosecond median. It did not
attribute that wall to an individual operation. A bounded stack sample of the unchanged full
request subsequently observed 536 samples below `ggml_compute_forward_pad`, 229 below regular
matrix multiplication, 196 below concat, 184 below graph barriers, and 344 below
`ggml_compute_forward_mul_mat_id`. Those counts are directional sampling evidence, not operation
timings or a performance claim.

The selected intervention removes fixed-request-width zero padding from decode attention's K and V
inputs. Each decode step constructs its phase-A graph at the exact live attention width
`n_past + 1`, consumes the corresponding prefix of the existing causal-mask row, and connects the
live concat results directly to KQ and KQV. The canonical K/V plane allocation, column stride, and
full request width remain fixed. Prefill, selected-expert phase B, routing arithmetic, output head,
cache policy, provider behavior, and native ownership do not change.

Item 62's four full-helper walls `[18059864416,18927732709,20639199375,19605385750]` ns and
19,266,559,229-ns integer median are immutable. This ledger precommits a 50,000-ppm floor of
963,327,962 ns and candidate ceiling of 18,303,231,267 ns before production implementation. The
intervention ships only when four conditioned fresh-process repetitions preserve every inherited
correctness boundary and produce a candidate median no greater than that ceiling. Otherwise the
production intervention and its production owner changes are removed before publication.

Exploratory evidence does not satisfy that gate. Global ggml CPU thread counts 1, 2, 4, and 8
produced single full-helper walls of 29.173, 20.843, 16.824, and 29.651 seconds respectively, so
thread tuning is rejected and the default four-thread behavior is retained. Two uncommitted
live-width probes produced 17,937,155,959-ns and 18,391,417,042-ns walls and exact output/lifetime
evidence. They justify the candidate but are not shipping measurements.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-ROUTING-PHASE-A-BOUNDARY`; `scripts/run-olmoe-routing-phase-a-boundary`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | the fixed item-62 OLMoE decode request and its next R8 investment decision |
| Fixed request | inherit item 62 exactly: byte-identical task/system/user prompt, model, AlignPack, geometry, 975,175,680-byte partial-LRU budget, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/isolation | four sequential fresh-process pairs; each maximum-2 result is the exact prefix of the following maximum-128 result; zero processes matching both pinned llama-server and model paths before, between, and after each pair |
| Immutable baseline | item 62 full-helper walls `[18059864416,18927732709,20639199375,19605385750]` ns and integer median 19,266,559,229 ns; never recompute them from candidate samples |
| Shipping gate | 50,000 ppm of baseline, rounded up, is 963,327,962 ns; candidate ceiling is baseline minus floor, 18,303,231,267 ns; `MET` iff the four-sample candidate wall median is at or below the ceiling |
| Fixed plane | request allocation width, `kv_columns`, canonical K/V byte layout, per-token column stride, capture, writeback, verification, and cleanup remain item 62's full-width behavior |
| Live attention width | for each decode step, `live_width = n_past + 1`; validate `1 <= live_width <= kv_columns`; construct the phase-A table/spec and graph mask input at that width only |
| Mask semantics | supply the exact `live_width` prefix of the existing fixed-width row for that decode step; every included value is the same unmasked zero and only the excluded fixed tail contains the existing negative-infinity padding |
| K/V graph semantics | concat produces the exact live K and V tensors; rows 18 and 24 retain their general `WHEN_WIDE` PAD form but are not issued when source and requested widths are equal; KQ and KQV consume concat directly in rows 19 and 25 on the production decode path |
| Graph topology | the decode phase-A table remains 37 rows and graph order is unchanged except that two PAD nodes per routed layer per decode step are unissued; for `n_layer = L` and `n_expert_used = U`, each successful MoE decode-step graph contains `L * (41 + 2 * U) + 6` issued nodes; graph count is unchanged |
| Numerical behavior | live K/V columns and mask values are byte-identical to the corresponding prefix of the old padded graph; excluded zero/negative-infinity columns cannot contribute; token ids, logits/sampling outcome, cache state, and final output must remain exact |
| Transcript/oracle compatibility | retain the fixed full-width external transcript and its coverage. KQ and KQ-softmax rows remain explicitly shape-incomparable as before; every comparable row remains exact, so live graph width does not weaken the existing oracle |
| Existing public result | production provider and CLI schemas are unchanged; existing qualification `steps[].node_count` and aggregate `decode.node_count` truthfully decrease by two per routed layer per completed decode step; phase-A and total compute timers retain their existing meanings |
| Qualification helper | add `olmoe_routing_phase_a_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; maximum is only 2 or 128; preserve the item-62 helper record exactly and expose no new production state |
| Candidate result | one exact-key schema-1 `R8_OLMOE_ROUTING_PHASE_A_BOUNDARY` JSON document with immutable baseline, gate, exact candidate intervention/identity, four inherited short/full pairs, candidate wall and phase-A samples/medians, gain ns/ppm, and `MET` or `NOT_MET`; stdout has no complete document on failure |
| Inputs/identity | independently pin item 62's runner and complete helper/source chain, workload and baseline values, new helper/runner, model, pack, geometry, server, Align revision/compiler, ggml libraries and consumed headers, C compiler/version, task, prompt, exact token chain, built helper/shim, clean align-llm head, and item 62's fixed host fingerprint |
| Validation order | arguments/prerequisites; scrubbed environment/linker search; fixed host, clean head, process absence, imported and external identities including headers; exact-source build; four conditioned records; schema/topology/output/cache/lifetime/repeatability; aggregate/gate; final identities/head; cleanup-inclusive ceiling; publication |
| Failure | nonzero and no complete document for invalid arguments, bounds or topology failure, identity/host/source/process drift, malformed input, output/cache/lifetime drift, child failure, source mutation, cleanup failure, or ceiling excess; missing prerequisites retain the single declared N/A path |
| Ownership/allocation | no new native owner; live-width table/spec and mask view are invocation-local, the fixed plane remains request-owned, and helper/runner/temp state is removed by its existing owner |
| Persisted/cache identity | N/A: no production schema, persisted cache, model, pack, geometry, or migration changes; qualification stdout is not persisted by the runner |
| Schema version | production schemas N/A because unchanged; qualification result is exact schema 1 and unknown/missing/duplicate keys fail |
| Prerequisites | item 62 merged result, pinned managed Align compiler, fixed capable host/model assets, ggml toolchain, and no matching external server process |
| Cost ceiling | one monotonic 8-minute ceiling covers helper/shim build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; every child keeps a narrower bound |
| Acceptance evidence | author consistency pass; `make fmt`; pinned helper build; exact live-width/topology regression in `make layer-forward-smoke`; unchanged transcript coverage; `make runtime-provider-smoke`; Python compilation; focused inherited self-test; one complete four-repeat real qualification; `git diff --check`; one comprehensive review; exact-head `python3 scripts/pre-pr --owner-test R8-OLMOE-ROUTING-PHASE-A-BOUNDARY -- scripts/run-olmoe-routing-phase-a-boundary --self-test` |

The capability makes one fixed-request, one-model, one-host performance claim. Cross-host, GPU,
throughput, arbitrary-task, cache-policy, persistent-state, public-provider, individual-kernel, and
R8 end-to-end claims are N/A. No Align language or standard-library surface is missing.

## 3. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Decode loop | derive `live_width` from admitted `n_past` | one bounded width per step | reject zero, overflow, or width beyond fixed plane | no graph issued | locals die with step | source assertions plus maximum-2/full runs |
| Mask view | take exact prefix from fixed row and fixed stride | live zero prefix is unchanged | invalid range/shape fails before graph construction | no new owner | existing view owner | layer smoke shape/value checks and transcript oracle |
| Phase-A table/spec | construct at live width; keep 37-row schema | two PAD rows are unissued for every routed layer | malformed width/row relation fails existing table validation | `WHEN_LAST` behavior unchanged | existing table/spec teardown | exact table rows and node-count formula |
| K concat/KQ | concat live cached K plus current K; direct KQ input | values and order match old prefix | existing concat/matmul error propagation | failed graph does not commit step | graph/context teardown once | comparable transcript rows and fixed output |
| V concat/KQV | concat live cached V plus current V; direct KQV input | values and order match old prefix | existing concat/matmul error propagation | failed graph does not commit step | graph/context teardown once | comparable transcript rows and fixed output |
| Fixed plane | allocate/write/capture/verify full width | only live prefix is read into graph | existing bounds and first-mismatch behavior | no change | existing plane buffer once | inherited plane/lifetime owners |
| Step/result accounting | use actual issued graph nodes | per-step and aggregate counts follow exact formula | count drift rejects owner/result | failed step remains uncommitted | no new allocation | stub maximum-2/full exact assertions |
| Transcript oracle | retain fixed-width external transcript | all comparable rows remain exact | mismatch keeps existing diagnostic | shape-incomparable KQ rows remain explicit | existing transcript state | `md-oracle-full` capable smoke |
| Helper | item 62 preparation plus candidate identity | one exact inherited record | bad argument/output/topology exits before print | N/A | invocation drops state | pinned build and schema self-test |
| Repetition | fixed host/process absence; fresh short/full children | exact prefix/output four times | any drift aborts without result | no partial sample/result | signal/deadline cleanup | twelve absence checks and repeatability |
| Aggregate/gate | four exact records and immutable baseline | integer medians and gate arithmetic | boolean/missing/duplicate/arithmetic/baseline drift rejects | no partial aggregate | N/A | below/at/above ceiling vectors |
| Identity | pin imports, sources, headers, tools, externals, and head | final values unchanged | any nested value or digest drift fails | missing prerequisite emits N/A | restore generated root binary | imported/nested/header mutants and real recheck |
| Signal/deadline | install handlers before real work | N/A | interruption/timeout exits nonzero | no complete JSON | stop child and restore temp/build state | inherited forced timeout/restoration tests |

Generic monomorphization, move/source-nulling, concurrent calls, external server ownership, persisted
migration, and asynchronous races are N/A. Decode remains synchronous and the intervention adds no
borrow, allocation, or native lifetime.

## 4. Implementation and verification map

1. Pass `n_past + 1` as the decode phase-A table/spec width and slice the existing step-mask row to
   that exact prefix while retaining the full plane stride and allocation width.
2. Make decode K/V PAD rows conditional on a wider requested width; connect KQ and KQV to the
   concat result when already exact. Keep the general wider-table behavior valid.
3. Extend the layer-forward owner with the exact issued-node formula and retain the full transcript
   oracle, output, plane, and lifetime assertions.
4. Add a thin item-63 helper and bounded runner which import item 62 behavior, independently pin
   the complete consumed chain and immutable gate, and own schema, topology, identity, cleanup, and
   decision mutants.
5. Run narrow owners and the one real four-repeat qualification. Record `MET` or `NOT_MET` here,
   in the roadmap, and in `HANDOFF.md`; remove production changes before publication on `NOT_MET`.
6. Complete one comprehensive review, consolidate valid findings, rerun affected evidence and
   exact-head preflight, publish, merge, and continue to the selected successor.

No `make ci`, installed platform profile, 40-prompt corpus, stress suite, cache replay, or unrelated
benchmark is selected. The live-width production change, exact topology regression, qualification
helper, and gate runner form one consumer-complete capability.

## 5. Author consistency pass

The ledger and matrix agree that only decode phase A changes width, the canonical plane and its
stride remain fixed, and the exact mask prefix preserves numerical behavior. They do not relabel
item 62's graph-level timing as PAD-only cost: stack samples and two probes select the candidate,
while only the precommitted four-repeat full-helper gate can establish a shippable improvement.
Every changed constructor, success, failure, early-exit, cleanup, topology, transcript, identity,
and publication boundary has one named owner. The immutable baseline, 963,327,962-nanosecond floor,
and 18,303,231,267-nanosecond ceiling are recorded before production code changes.

## 6. Recorded result

The complete run at clean implementation head `dd2fd1f91dbf7823f8a56c35a59071baa9041a16`
finished in 116.615 seconds. Every maximum-2 conditioning record was the exact prefix of its
maximum-128 record. All four full requests reproduced the fixed 87-token chain, 86 completion
tokens, and output SHA-256. Each balanced 2,958 ggml buffers, 6,090 contexts, one backend, 2,958
allocators, and one resident wrap, released before owner-scope exit, with zero matching server
processes at all twelve isolation boundaries.

Candidate full-helper walls were
`[17315490209,18232421375,18082976541,18457679541]` ns, for an 18,157,698,958-ns
integer median. Against the immutable 19,266,559,229-ns baseline, this is a 1,108,860,271-ns /
57,553-ppm gain and is 145,532,309 ns below the precommitted 18,303,231,267-ns ceiling. The
decision is therefore `MET`, and the intervention ships.

Phase-A walls were `[1362582832,1493940595,1430289264,1476465348]` ns, for a
1,453,377,306-ns median, down from item 62's 2,939,392,017-ns diagnosis. Total decode-compute walls
had a 2,747,113,698-ns median. Claim I/O measured 3,778,790,474 ns on the same candidate requests,
so it is now the largest directly measured unresolved remaining-decode bucket and selects item 64.
These comparisons are whole graph/bucket measurements; they do not attribute the gain to an
individual PAD invocation or kernel.

The exploratory probes remain non-shipping evidence. Only the four clean-head repetitions above
satisfy the gate.
