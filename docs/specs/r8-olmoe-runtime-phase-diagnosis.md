# R8 OLMoE runtime phase diagnosis

Status: attribution repair awaiting measurement, 2026-09-04

## 1. Decision and boundary

R8-OLMOE-SAMPLED-RUNTIME-DECISION recorded a 189.005-second runtime median for the fixed
five-candidate portfolio, versus 12.710 seconds through resident llama.cpp. Runtime candidate
intervals also rose from 27.928 to 40.243 seconds while the two model implementations were
co-resident. That result cannot attribute the gap: every `AlignRuntime` request reconstructs its
provider preparation, dense resident fill, expert cache, KV plane, graphs, and native owners, while
the baseline server keeps another copy of the model resident.

This capability makes the smallest controlled diagnosis before either lifetime or cache behavior
changes. It runs the fixed seed-5 request with a two-token short completion and the full 128-token
maximum, both with no matching llama.cpp model process and with one owned pinned server resident but
idle. A qualification-only Align helper times the existing provider preparation and publishes the
existing runtime phase and lifetime counters without adding a persistent provider, retaining cache
state, or changing generation.

The result brackets repeated setup and compares those bounds with the co-resident full-request
penalty. It is a single-host diagnosis and next-investment decision, not a shipped latency
improvement, throughput claim, general benchmark, or persistent-provider design.

## 2. Measurement-contract ledger

| Field | Settled contract |
| --- | --- |
| Capability | `R8-OLMOE-RUNTIME-PHASE-DIAGNOSIS` |
| Consumer | the next R8 implementation choice between reducing request-local setup, removing co-resident memory pressure from the benchmark, or investigating the decode tail |
| Fixed task | item 53's exact system text, user prompt, OLMoE model, AlignPack, geometry, partial-LRU budget 975,175,680 bytes, temperature 0.3, and seed 5 |
| Qualification helper | `olmoe_runtime_phase_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS SEED`; accepts only maximum 2 or 128 and seed 5, executes the same snapshot, OLMoE frontend, geometry, source-identity, tokenizer, sampled generation, EOG stripping, and decode sequence as `provider_runtime.generate`, and emits one schema-1 JSON record |
| Conditions | `solo` requires no process whose command contains both the canonical pinned server and model paths; `co_resident` owns one pinned llama.cpp build-10566 CPU server loaded with the same model, context 512, and four threads; immediately before each timed helper it sends exactly one untimed fixed-prompt, seed-5, temperature-0.3, one-token warmup and requires server RSS of at least 2,147,483,648 bytes; it sends no inference during the timed helper and records server RSS immediately afterward |
| Schedule | four environment pairs `(solo,co_resident)`, `(co_resident,solo)`, `(co_resident,solo)`, `(solo,co_resident)`; length order inside the two legs is respectively `(short,full)`, `(full,short)`, `(full,short)`, `(short,full)` |
| Short/full | short is maximum 2 and its ids must equal the first two full ids; its decoded-output digest must repeat; full maximum 128 must reproduce item 53's exact output digest `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52`, whose extracted patch had the recorded known-good digest, and must stop on EOG |
| Timed interval | each helper wall interval contains one complete process and request; the helper separately reports snapshot, model-IR, geometry, source-identity, tokenizer preparation, sampled engine, output decode, and total intervals |
| Existing runtime evidence | engine outcome reports elapsed, first-token, dense resident-fill, pack/claim reads, routing decision, total/decode compute, graph counts, cache counters, and balanced native-owner counters; no production counter semantics change |
| Repeated setup bounds | lower bound: per sample, helper phases before the engine plus `resident_fill_ns`; these measured intervals recur in every fresh helper request but leave process startup, allocation, native-owner construction, and other cache work unassigned. Conservative upper bound: the complete solo full helper wall interval, which contains every reconstructive and compute cost in that request |
| Co-resident penalty | paired full-request wall time `co_resident - solo`; all four differences and the median are recorded, and a negative value remains evidence rather than being clamped |
| Decision | `CO_RESIDENT_PRESSURE_EXCEEDS_SETUP` only when all four penalties are positive and median penalty is more than 50,000 ppm above the conservative median setup upper bound; `REPEATED_SETUP_EXCEEDS_PRESSURE` only when the median measured setup lower bound is more than 50,000 ppm above the positive part of median penalty; otherwise `MIXED_OR_UNRESOLVED` |
| Next action | co-resident pressure selects an isolated-baseline R8 decision; repeated setup selects a bounded persistent-lifetime design only after the measured setup fields identify its owner; mixed/unresolved selects one narrower phase instrument and no lifetime API |
| Result | canonical `R8_OLMOE_RUNTIME_PHASE_DIAGNOSIS` schema 1 JSON on stdout and a concise summary on stderr; machine-local evidence is not committed |
| Inputs and identity | item 53's six canonicalized model/runtime path variables; Darwin additionally requires the same explicit ordered `LIBRARY_PATH`; no validator is used; result binds source, Align revision, compiler, helper, shim, ggml libraries, model, pack, geometry, task, prompt, and server identities, and records each timed helper's immediately-before and immediately-after server RSS without paths |
| Ownership | runner owns each helper, temporary record, generated build product, dynamic shim, server process/log, and all cleanup; the helper owns each snapshot, generated arrays, cache, KV plane, graph, and native owner for exactly one invocation |
| Failure | nonzero without `COMPLETE` for prerequisite/source/identity drift, a matching process in `solo`, server failure, malformed helper record, generation/output drift, counter imbalance, schedule drift, nonpositive timing, or the whole-run ceiling |
| Owner | `scripts/run-olmoe-runtime-phase-diagnosis --self-test`; the same command without arguments is the opt-in real diagnosis |
| Performance ceiling | N/A for optimization opportunity: this capability changes no runtime behavior and makes no improvement claim; one complete diagnostic is capped at approximately 20 minutes |

The 50,000-ppm deadband is an attribution stability rule, not R8's shipping floor. A pressure
decision must clear the conservative setup upper bound; clearing only the measured lower bound is
insufficient. A repeated-setup decision must clear the positive pressure penalty using the measured
lower bound. `REPEATED_SETUP_EXCEEDS_PRESSURE` authorizes design work only for the named setup
phases; it does not claim that every unexplained nanosecond is construction.

## 3. Schema 1 records

The helper record is temporary and has these semantic groups:

```text
schema_version: 1
status: "ok"
maximum_tokens: 2 | 128
seed: 5
prompt_tokens: integer
completion_tokens: integer
stopped_eog: boolean
token_ids: [integer]
output_sha256: lowercase SHA-256
phases: {snapshot_ns, model_ir_ns, geometry_ns, source_identity_ns,
         tokenizer_ns, engine_wall_ns, output_decode_ns, elapsed_ns}
engine: {elapsed_ns, first_token_ns, resident_fill_ns, pread_ns,
         claim_pread_ns, decide_ns, compute_ns, decode_compute_ns,
         graph_count, decode_steps_completed, resident_fill_bytes,
         expert_cache_requests, expert_cache_hits, expert_cache_misses,
         expert_cache_evictions, expert_cache_bytes_fetched}
lifetime: {ggml_buffers_created, ggml_buffers_freed, contexts_created,
           contexts_freed, backends_created, backends_freed,
           gallocrs_created, gallocrs_freed, resident_wraps_created,
           resident_wraps_freed, released_before_owner_scope_end}
```

The canonical result contains identity and host groups, the fixed schedule, four pair records with
`solo` and `co_resident` legs, and an aggregate. Each leg records its length order and its
short/full helper records plus helper wall time. Each helper record also contains
`server_rss_before_bytes` and `server_rss_after_bytes`: both are null for `solo`; for `co_resident`,
the before value is at least 2 GiB and the positive after value records any eviction caused by that
helper. The aggregate contains four paired
full penalties, medians for all four condition/length cells, median solo repeated-setup lower and
upper bounds, each bound's share of solo full time, median penalty, penalty ppm against solo full,
and the decision. Paths, prompt or output text, server logs, process identifiers, and credentials
never appear.

All durations are positive integers. Helper total is at least the sum of its seven sequential
phases; helper wall is at least helper total. Engine wall contains engine elapsed. Successful
lifetime counters balance created and freed owners, and `released_before_owner_scope_end` is true.

## 4. Validation and execution order

The runner reuses item 53's environment isolation, canonical path/linker validation, exact-source
build, immutable input identities, deadline, and process cleanup. It requires a clean worktree,
checks that no matching server/model process exists, builds the helper, validates one synthetic
schema record, and then executes the fixed schedule. Before `solo` it stops any owned server and
rechecks absence. Before `co_resident` it starts one owned server and waits for health. Immediately
before each short/full helper it verifies server identity, sends the declared warmup, requires the
RSS floor, runs the helper without concurrent server inference, and records server RSS immediately
afterward. Repeating the warmup prevents the first helper's memory pressure from silently removing
the intended condition for the second helper.

The helper validates arity, the fixed maximum/seed set, snapshot architecture, model IR, exact
geometry, pack source identity, prompt/EOG/context bounds, engine success, generated-id bounds and
EOG stop, output decode identity, and response bound in the production order. The runner then checks
schema, phase nesting, lifetime balance, exact short/full id prefix, cross-condition repeatability,
and the full output digest already tied to the known-good patch before computing the aggregate.
Persistent inputs and clean source are rechecked after the final pair.

## 5. Closure matrix

| Cell | Runner | Qualification helper | Existing runtime | Evidence |
| --- | --- | --- | --- | --- |
| Construction | canonical inputs, clean source, exact helper/shim, no matching process | validate fixed operands and prepare the production inputs | invocation-local owners only | self-test precedence/environment/path/process cases; real identities |
| Solo success | require matching server/model absence around both lengths | fresh process per request | unchanged sampled generation | four short/full solo legs |
| Co-resident success | own one pinned server; before each helper issue the fixed untimed warmup and require at least 2 GiB RSS; keep it idle during the helper and record RSS afterward | same helper bytes and request | unchanged sampled generation | four short/full co-resident legs, each with before/after RSS |
| Phase accounting | validate positive sequential/nested clocks and derive setup lower/full-request upper bounds | time seven production-order phases | publish existing engine counters unchanged | synthetic boundaries and real records |
| Output identity | compare short prefix and full known-good digest across conditions | publish ids, counts, EOG state, and output digest | fixed seed stream and EOG handling | all sixteen records agree |
| Lifetime | fresh process and record per request | expose existing balanced counters | current teardown remains owner | synthetic imbalance refusal and all real records |
| Decision | exact paired differences, integer medians, 50,000-ppm comparison | N/A | N/A | three decision vectors plus boundary cases |
| Failure/malformed | no complete result; preserve bounded child diagnostic | nonzero before successful record | existing failure tears down | malformed, drift, server exit, deadline self-tests |
| Cleanup | terminate/kill/reap exact helper/server and restore generated file | normal return drops invocation state | balanced existing owners | forced escalation/restoration self-tests |
| Ceiling | one monotonic 20-minute deadline | narrower per-command bounds | bounded maximum 128 | deadline self-test and real elapsed |

Public provider configuration, persistent sessions, cache identity, concurrent calls, GPU execution,
sampling policy, task selection, validator behavior, and model quality are N/A because this is a
qualification-only measurement over already-shipped behavior.

## 6. Implementation and acceptance map

1. Add one qualification-only Align helper that follows the production OLMoE preparation and
   generation sequence and emits the fixed phase/lifetime record.
2. Add one Python runner that reuses item 53's exact build, identity, environment, deadline, and
   cleanup utilities; implement the fixed pair/length schedule and schema validation.
3. Add model-free self-tests for command grammar, schema and clock nesting, prefix/repeatability,
   process-state classification, lifetime balance, decision boundaries, restoration, and cleanup.
4. Run the focused self-test and one complete real diagnosis, then record its source/input
   identities, medians, attribution decision, limits, and next action here and in the roadmap.
5. Run one comprehensive review, repair accepted findings, rerun affected owners, exact-head
   publication preflight, required GitHub checks, and merge before starting the selected next work.

No `make ci`, installed profile, platform matrix, coding validator, 40-prompt corpus, cache replay,
stress suite, or unrelated benchmark is selected. `make fmt` is required before committing the new
Align helper. The existing provider and diagnostic owners are required only if implementation
changes their source rather than merely consuming their public records.

## 7. Recorded diagnosis

The reviewed attribution defect invalidated the original directional classification: the
2.208-second penalty cleared only the 0.121-second measured setup lower bound, not a setup upper
bound. The raw run remains discovery evidence, but no roadmap decision is taken from it. One
complete measurement at the repaired decision contract is pending.
