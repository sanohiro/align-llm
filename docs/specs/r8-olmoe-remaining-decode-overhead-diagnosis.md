# R8 OLMoE remaining-decode overhead diagnosis

Status: active design, 2026-09-04

Roadmap owner: item 57, `R8-OLMOE-REMAINING-DECODE-OVERHEAD-DIAGNOSIS`

## 1. Decision owned

Item 56 isolated the sampled provider comparison from a resident llama.cpp process and still
measured a 149.273-second runtime median versus 13.197 seconds local. Its four seed-5 runtime
provider intervals had a 29,332,992,999-nanosecond median. Item 55's fixed full request assigned
24.803 seconds to remaining decode, while claim reads and graph compute accounted for only about
8.46 seconds of that interval. Construction was bounded at 0.272 seconds and cannot close the gap.

This capability partitions item 55's remaining-decode boundary before any optimization is chosen.
It retains the same fixed prompt, seed 5, maximum 128, partial-LRU budget, output/token identity,
fresh helper process, two-token conditioning request, and absence of the matching llama.cpp model
process. Four conditioned full requests provide medians. The shared runtime outcome adds only the
clocks needed to divide every successfully completed remaining decode step into pre-pass,
decode-pass, and post-pass intervals and to project the existing pack/resident staging, claim,
compute, routing, and KV-plane clocks onto the decode-pass interval.

The explicit pass residual contains graph/context creation, graph construction/allocation/teardown,
generic tensor transfers and digests, and other work not owned by a narrower existing counter. It
is not renamed as graph lifecycle. If that residual dominates, the only authorized next work is a
narrower graph-lifecycle instrument. No result from this diagnosis directly authorizes a product
optimization, persistent provider, cache-policy change, or performance-win claim.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-REMAINING-DECODE-OVERHEAD-DIAGNOSIS`; `scripts/run-olmoe-remaining-decode-overhead-diagnosis`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | the next R8 investment decision after item 56, choosing a directly measured remaining-decode bucket or one narrower pass-residual diagnosis |
| Fixed request | item 55's byte-identical task/system/user prompt, OLMoE model, AlignPack, geometry, cache budget 975,175,680 bytes, temperature 300,000 micros, seed 5, maximum 128, EOG rule, exact 87-id generated chain, 86 completion tokens, and output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52` |
| Conditioning/schedule | four sequential repetitions; each runs one fresh maximum-2 helper followed immediately by one fresh timed maximum-128 helper; the short record must be the exact two-token prefix of the full record; no helper process or runtime state survives an invocation |
| Process condition | require zero processes whose command contains both canonical pinned llama-server and model paths before conditioning, between conditioning and full, and after full in every repetition; no server is created |
| Shared outcome fields | add signed 64-bit `remaining_decode_pre_pass_ns`, `remaining_decode_pass_ns`, `remaining_decode_post_pass_ns`, `remaining_decode_pread_ns`, `remaining_decode_decide_ns`, `remaining_decode_plane_upload_ns`, and `remaining_decode_plane_readback_ns`; `empty_outcome` initializes each to zero |
| Top-level phase boundary | for each admitted decode iteration, pre-pass starts where the existing decode phase starts and ends immediately before `decode_pass`; pass is exactly the `decode_pass` call; post-pass begins immediately after it and ends at the existing successful phase end after selection, accounting, row rendering, and next-token assignment |
| Successful-step semantics | only successfully completed steps after the first contribute to the seven new remaining-decode totals; an EOG/maximum check before a step and any failed partial step contribute zero, matching existing `remaining_decode_ns` semantics |
| Pass subclocks | `remaining_decode_pread_ns` is the exact delta of existing `Outcome.pread_ns`; claim and compute reuse existing `remaining_decode_claim_pread_ns` and `remaining_decode_compute_ns`; decide is the exact delta of `Outcome.decide_ns`; plane upload/readback are exact deltas of the existing `Plane.upload_ns`/`readback_ns`; these six clocks are non-overlapping subsets of pass |
| Meaning limits | `pread_ns` includes the existing pack-or-resident embedding/dense staging timer; `decide_ns` includes argsort readback plus routing; plane upload means the existing CPU K/V staging and plane readback means the existing K/V slot readback. Generic slot transfers, digests, native graph/context lifetime, allocation, and other pass work stay in residual |
| Exact accounting | for every complete full record, `remaining_decode_ns = pre_pass + pass + post_pass`; `pass_residual = pass - pread - claim - compute - decide - plane_upload - plane_readback` and must be nonnegative; helper/runner publish residual as derived evidence rather than a shared mutable counter |
| Existing consumers | generation order, tokens, sampling, EOG, provider response, cache behavior, native lifetime, existing CLI modes, and existing JSON schemas are byte- and meaning-unchanged because no existing renderer exposes the new fields |
| Qualification helper | `olmoe_remaining_decode_overhead_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`; maximum is only 2 or 128; it follows item 55's production-order preparation and generation and emits one exact schema-1 record with the old phase/engine/lifetime evidence plus `remaining_decode` partition evidence |
| Result | one exact-key schema-1 `R8_OLMOE_REMAINING_DECODE_OVERHEAD_DIAGNOSIS` JSON document on stdout and one concise stderr summary; no partial JSON on failure |
| Fixed baseline | item 56's four isolated seed-5 runtime provider intervals `[28920977916,29248835083,29527528125,29417150916]`, integer median 29,332,992,999 ns; they are immutable comparison evidence and are not recomputed from the new samples |
| Shipping floor | 50,000 ppm of the fixed baseline, requiring an integer opportunity of at least 1,466,649,650 ns per full request before a bucket can select follow-up implementation design |
| Opportunity ceilings | each bucket's four-sample median is its conservative removable-work ceiling; buckets are `PACK_OR_RESIDENT_STAGE`, `CLAIM_IO`, `COMPUTE`, `ROUTING`, `KV_PLANE_TRANSFER` (upload plus readback), `PRE_PASS_ORCHESTRATION`, `POST_PASS_ORCHESTRATION`, and `PASS_RESIDUAL`; removing an entire clock is deliberately an upper bound, not a speed prediction |
| Decision | choose the largest median bucket, breaking ties in the order just listed; if it is below the floor, `NO_MATERIAL_BUCKET`; if `PASS_RESIDUAL` wins and clears the floor, `PASS_RESIDUAL_NEEDS_DIAGNOSIS`; otherwise `MEASURED_BUCKET_ELIGIBLE` plus the selected bucket. A directly measured winner authorizes only an implementation contract with its own baseline and 50,000-ppm shipping gate |
| Inputs/identity | item 55's six canonicalized `ALIGN_LLM_*` paths and Darwin ordered `LIBRARY_PATH`; pin and refuse the imported workload constants, model, pack, geometry, server, Align revision/compiler, ggml libraries, C compiler/version, task, prompt, exact token chain, helper, shim, and clean align-llm head |
| Validation order | argument and prerequisite precedence; scrubbed environment/linker search; clean head and no matching process; fixed imported and external identities; exact-source helper build; four conditioned records with absence checks; schema, phase equations, output/lifetime/repeatability; aggregate/decision; unchanged head/files; ceiling; publication |
| Failure | nonzero and no complete document for invalid arguments, missing/unusable configured values except the declared N/A path, identity/source/process drift, malformed helper/result data, output drift, negative/overlapping clocks, partial-step accounting, unbalanced lifetime, helper failure, or ceiling excess |
| Ownership/allocation | new shared fields are scalars in the invocation-owned outcome; helper and runner state is invocation/process-local; existing native owners remain balanced and every child/temp artifact is removed by its current owner |
| Persisted/cache identity | N/A: no generated helper, inference state, cache, patch, or result file survives; stdout evidence is not stored by the runner |
| Cost ceiling | one monotonic 8-minute ceiling covers helper/shim build, four conditioning and four full requests, aggregation, identity rechecks, and cleanup; each child retains a narrower bound |
| Acceptance evidence | `gmake fmt`; pinned helper build; `gmake layer-forward-smoke`; `gmake runtime-provider-smoke`; Python compilation; focused self-test; one complete real diagnosis; `git diff --check`; one comprehensive review; exact-head `scripts/pre-pr --owner-test R8-OLMOE-REMAINING-DECODE-OVERHEAD-DIAGNOSIS -- scripts/run-olmoe-remaining-decode-overhead-diagnosis --self-test` |

The capability makes one fixed-request, one-model, one-host attribution. Cross-host, GPU,
throughput, arbitrary-task, cache-policy, token-parity, persistent-state, and provider-API claims
are N/A. Text inputs inherit item 55's fixed UTF-8 and embedded-NUL refusal boundaries. The result
is JSON text with exact keys and non-boolean integer clocks; it is not a persisted interchange
format consumed by production.

## 3. Schema 1

The helper preserves item 55's top-level `schema_version`, `status`, `maximum_tokens`, `seed`,
`prompt_tokens`, `completion_tokens`, `stopped_eog`, `token_ids`, `output_sha256`, `phases`,
`engine`, `engine_phases`, and `lifetime` groups. It adds:

```text
remaining_decode: {
  pre_pass_ns,
  pass_ns,
  post_pass_ns,
  pack_or_resident_stage_ns,
  claim_pread_ns,
  compute_ns,
  routing_ns,
  plane_upload_ns,
  plane_readback_ns,
  pass_residual_ns
}
```

All fields are non-boolean integers. A maximum-2 conditioning record has zero for every field
because it completes only the first decode iteration. A successful maximum-128 record has positive
pre/pass/post values, positive claim and compute values, nonnegative other subclocks, the two exact
accounting equations, and the unchanged engine/lifetime nesting rules.

The result's exact top-level keys are:

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

`model` contains `bytes`, `sha256`, and `architecture`. `baseline` contains the four fixed item-56
seed-5 provider intervals, their integer median, `floor_ppm`, and `floor_ns`. `candidate` contains
provider, align-llm head, Align revision/compiler, helper/shim, ggml-library, pack, geometry, and
cache-budget identities. `task` contains task/prompt identities, maximum, temperature, and seed.
`environment` contains OS, release, architecture, CPU count, C compiler/version, and canonical
linker-search identities.

Each of four samples has exact keys `index`, `conditioning`, `full`, `full_helper_wall_ns`, and
`isolation`; isolation contains the exact-zero non-boolean integer fields `matching_before`,
`matching_between`, and `matching_after`.
`conditioning` and `full` are helper records with the exact shape above. `aggregate` has exact keys
`full_helper_wall_median_ns`, `engine_wall_median_ns`, `remaining_decode_median_ns`,
`bucket_values_ns`, `bucket_medians_ns`, `selected_bucket`, `selected_bucket_median_ns`,
`selected_bucket_share_ppm`, `floor_ppm`, `floor_ns`, and `decision`. The two bucket objects have
the eight exact uppercase bucket keys in decision tie order; values has one four-element positive or
nonnegative duration array per bucket, while medians has one nonnegative integer per bucket.
`selected_bucket_share_ppm` divides the selected median by `remaining_decode_median_ns`. Paths,
output text, model bytes, process identifiers, and credentials are excluded.

## 4. Closure matrix

| Path | Construction | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Shared outcome | seven zeroed `i64` scalars | successful remaining steps accumulate exact boundaries/deltas | no new error code; incomplete phase cannot form a complete qualification record | first step, EOG, maximum, and failed partial step add zero | no new native owner | zero/positive source owner cases, old smoke owners, real accounting |
| Decode pre/pass/post | snapshot clocks and one timestamp before current step work | reuse three adjacent timestamp boundaries and existing successful commit point | helper rejects negative or unequal partition | loop guard precedes phase start | locals die per iteration | model-free equality/mutation cases and four real records |
| Pass subclocks | snapshot existing outcome/plane counters immediately before pass | exact deltas for pread, claim, compute, decide, upload, readback | any subtotal above pass rejects publication | failed pass adds no remaining total | existing graph teardown remains converged | overlap mutation, zero conditioning, real nonnegative residual |
| Helper | item 55 production preparation with fixed max/seed | one exact record and derived residual | invalid input/output/lifetime/accounting exits before print | N/A | invocation drops all state | pinned build, schema self-test, real records |
| Repetition | require process absence; run short then full in fresh children | exact prefix and full token/output identity four times | process/helper/repeatability drift aborts | no partial sample/result | active child follows inherited signal/deadline cleanup | absence/prefix/repeatability tests and twelve real checks |
| Aggregate | four full exact records and immutable item-56 baseline | integer medians, bucket ceilings, deterministic selection | missing/duplicate bucket, boolean clock, floor/baseline drift rejects | no partial aggregate | N/A | every decision class, tie order, just-below/at-floor vectors |
| Identity | pin inherited values before helper work; capture helper/shim/head | final hashes/head unchanged | uniform predecessor or external drift fails | missing prerequisite emits one N/A line | restore any root build product | inherited/external/tool drift tests and real recheck |
| Signal/deadline | install handlers before real work | N/A | interruption/timeout exits nonzero | no complete JSON | stop active child; restore helper/temp state | forced timeout/restoration self-tests |

Generic monomorphization, move/source-nulling, concurrent calls, external server ownership, and
persisted format migration are N/A: this change adds scalar clocks to an existing invocation value
and a qualification-only synchronous consumer.

## 5. Implementation and verification map

1. Add the seven outcome fields and update them beside the existing successful decode-phase commit,
   without changing an operation's order or adding a new native owner.
2. Add one qualification-only helper that exposes the partition over item 55's fixed request.
3. Add one bounded runner reusing item 55's build/environment/identity/cleanup primitives while
   independently pinning every imported workload value and owning the new schema and decision.
4. Run source owners, focused self-test, and one real four-repeat diagnosis; record the result and
   selected next item here, in the roadmap, and in `HANDOFF.md`.
5. Complete one comprehensive review, consolidate valid findings, rerun affected owners and
   exact-head preflight, publish, merge, and continue to the selected capability.

No `make ci`, installed platform profile, 40-prompt corpus, validator, sampled coding portfolio,
stress suite, cache replay, or unrelated benchmark is selected. This diagnosis changes shared
counter structure but no provider behavior, and its precommitted ceiling/floor prevent a measured
small bucket from becoming an optimization claim.
