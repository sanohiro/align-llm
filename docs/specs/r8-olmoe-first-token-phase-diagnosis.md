# R8 OLMoE first-token phase diagnosis

Status: active design, 2026-09-04

Roadmap owner: item 55, `R8-OLMOE-FIRST-TOKEN-PHASE-DIAGNOSIS`

## 1. Decision owned

Item 54 measured a 2.025-second median full-request penalty while the same pinned llama.cpp model
was resident and idle. Its measured repeated-setup lower bound was 0.132 seconds, but its
conservative upper bound was the entire 30.617-second solo request. That interval includes prompt
prefill and every generated token, so it cannot distinguish reusable construction from work every
request must perform.

This capability instruments the shipped invocation-local OLMoE generation path and repeats the
fixed full sampled request in four balanced solo/co-resident pairs. It replaces the old upper bound
with provider preparation plus the engine's completed pre-prefill construction. It also partitions
prefill, first decode, remaining decode, claim I/O, and compute so the next investment follows the
phase that actually moved. It does not retain a model, cache, backend, or buffer; change provider
lifetime; or claim an R8 performance win.

`prefill` includes selection of the first output token from the prompt logits. `first_decode`
consumes that first output token and selects the second. The existing `first_token_ns` counter is
left byte- and meaning-compatible even though its historical placement is inside that first decode;
no existing renderer or provider response gains a field.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Shared source counters | `moe_model_forward.Outcome` gains signed 64-bit nanosecond fields `construction_ns`, `prefill_ns`, `first_decode_ns`, `remaining_decode_ns`, `teardown_ns`, `prefill_claim_pread_ns`, `first_decode_claim_pread_ns`, `remaining_decode_claim_pread_ns`, `prefill_compute_ns`, `first_decode_compute_ns`, and `remaining_decode_compute_ns`; `empty_outcome` initializes every field to zero |
| Construction boundary | starts at `execute_mode` entry and ends immediately after backend creation, optional resident dense fill/wrap, and schedule-owned buffer/table construction, just before `prefill_pass`; it includes validation, pack/source verification, plan construction, allocations, and resident fill |
| Prefill boundary | starts immediately before `prefill_pass` and ends after successful prompt-logit digest, top-k construction, sampled first-token selection, and optional prefill-logit comparison, immediately before `decode_loop` |
| Decode boundaries | `first_decode_ns` records the first successfully completed decode iteration; `remaining_decode_ns` sums every later successfully completed iteration; each iteration includes its oracle preparation, graph execution, selection, accounting, and row construction; an EOG or maximum check before an iteration records no interval |
| Teardown boundary | starts after `decode_loop` returns and includes resident-wrap/backend release, balance checks, final counter publication, and schedule-owned result construction; the small return-to-`execute_mode` elapsed publication remainder is not assigned |
| Claim/compute attribution | prefill values are exact deltas of the existing `Outcome.claim_pread_ns` and prefill-side `Outcome.compute_ns`; first/remaining decode values are exact deltas for successfully completed decode iterations; on a successful run the three claim fields sum to `claim_pread_ns`, `prefill_compute_ns` equals `compute_ns`, and the two decode compute fields sum to `decode_compute_ns` |
| Failure semantics | counters describe completed boundaries only; the existing error, cleanup, lifetime, and partial-step semantics remain authoritative; the qualification emits no complete result for any helper failure or incomplete phase accounting |
| Existing consumers | `--moe-model-forward`, `--moe-decode-step`, provider output, token generation, sampling, EOG, cache behavior, and existing JSON schemas remain unchanged because none renders the new fields |
| Qualification helper | `olmoe_first_token_phase_gate MODEL PACK GEOMETRY PROMPT MAX_TOKENS 5`, where the runner uses maximum 2 only for fixed untimed candidate conditioning and 128 for evidence; it follows item 54's production-order preparation and generation sequence and emits one schema-1 record with fixed request evidence, provider phases, engine phase walls, per-phase claim/compute clocks, existing totals, and lifetime balance |
| Runner | `scripts/run-olmoe-first-token-phase-diagnosis`; no arguments runs the opt-in real diagnosis and `--self-test` runs model-free schema, schedule, decision, cleanup, and refusal tests |
| Conditions | four balanced pairs in orders solo/co-resident, co-resident/solo, co-resident/solo, solo/co-resident; every leg runs one untimed maximum-2 seed-5 candidate helper followed by one timed maximum-128 seed-5 helper; the conditioning output must be the timed output's exact two-token prefix; solo refuses any matching llama.cpp model process |
| Co-resident protocol | one owned pinned build-10566 CPU llama-server, four threads, context 512, no prompt cache; warm once before the untimed candidate helper and again immediately after it, then require RSS at least 2 GiB immediately before the timed helper, record RSS immediately after, and run no server inference during the timed helper; eight server warmups total |
| Candidate conditioning | one complete untimed two-token invocation immediately before every timed helper, eight total; it pays the same invocation-local construction path and establishes a comparable warm filesystem/process-launch regime without retaining any candidate process state |
| Fixed identity | item 54's exact model, alignpack, geometry, task, prompt, sampling policy, cache budget 975,175,680 bytes, Align revision/compiler, ggml shim/libraries, C compiler, and llama-server identities; the clean align-llm head and all file identities are rechecked after measurement |
| Output/repeatability | all eight helpers reproduce item 53's 86 completion tokens plus stripped terminal EOG, exact token ids, output SHA-256 `aac1d1158144da0b3afd4f4cdff7c10df240adaa85529b8a21839a0c89777e52`, non-time engine counters, and balanced native lifetimes |
| Old bounds | recorded lower 132,272,208 ns and upper 30,616,675,916 ns from item 54 are immutable comparison evidence, not recomputed aliases |
| New setup interval | each solo lower bound is snapshot + model IR + geometry + source identity + tokenizer + resident fill; each solo upper bound is those five provider phases + `construction_ns`; integer medians over four samples; complete evidence requires `lower <= upper < 30,616,675,916` |
| Pressure penalty | paired co-resident helper wall minus solo helper wall for each pair; record all four signed differences and their integer median; directional pressure requires all four differences positive |
| Decision | with the existing 50,000-ppm strict deadband: `CO_RESIDENT_PRESSURE_EXCEEDS_CONSTRUCTION` only when all penalties are positive and their median exceeds the new upper bound; `REPEATED_CONSTRUCTION_EXCEEDS_PRESSURE` only when the new lower bound exceeds `max(0, penalty median)`; otherwise `MIXED_OR_UNRESOLVED` |
| Phase diagnosis | record solo and co-resident medians plus paired differences for construction, prefill, first decode, remaining decode, and their claim/compute subclocks; these locate follow-up work but do not override the bound-based decision |
| Schema/validation | one canonical schema-version-1 JSON document; exact keys; booleans are not integers; validate identity and protocol, pair order, helper shape/nesting/accounting, RSS, output repeatability, narrowed bounds, decision, cleanup, and unchanged source in that order |
| Deadline | one monotonic 12-minute ceiling covers preparation, helper build, four server lifetimes/eight warmups, eight conditioning helpers, eight timed helpers, aggregation, and cleanup; individual child bounds are narrower |
| Ownership/allocation | new counters are scalars in the invocation-owned outcome; the helper and runner allocate only invocation/process-local state; every native owner remains balanced and released before its existing owner scope ends |
| Prerequisites | the same six explicit capability variables as item 54; a missing variable prints exactly one capability-specific `N/A` line and exits successfully before materialization or process creation |
| Acceptance evidence | `gmake fmt`; pinned helper build; `gmake layer-forward-smoke`; `gmake runtime-provider-smoke`; Python compilation; runner self-test; one complete real diagnosis; `git diff --check`; one comprehensive review; exact-head `scripts/pre-pr --owner-test R8-OLMOE-FIRST-TOKEN-PHASE-DIAGNOSIS -- scripts/run-olmoe-first-token-phase-diagnosis --self-test` |

All persisted/cache identity fields are N/A because the result is printed and no model/runtime state
is retained. Encoding and embedded-NUL rules are inherited unchanged from the fixed UTF-8 task,
tokenizer, bounded path, and JSON owners. Concurrent provider calls, GPU execution, other models,
other prompts/seeds, validator behavior, model quality, and throughput are outside this single-host
diagnosis.

## 3. Attribution rules

For solo record `i`:

```text
provider_prepare_i = snapshot + model_ir + geometry + source_identity + tokenizer
setup_lower_i      = provider_prepare_i + resident_fill
setup_upper_i      = provider_prepare_i + construction
```

Construction contains resident fill, so `setup_lower_i <= setup_upper_i` must hold. The upper
bound deliberately includes validation and other pre-prefill work that a persistent provider might
not eliminate; it remains conservative while excluding prefill, decode, output decoding, and
process launch.

For pair `i`:

```text
penalty_i = co_resident_helper_wall_i - solo_helper_wall_i
```

The runner uses integer medians and strict greater-than comparison:

```text
greater_by_deadband(left, right) =
  left > right && (left - right) * 1_000_000 > 50_000 * right
```

If the new upper median does not improve on 30,616,675,916 ns, the instrument has not met its own
purpose and no complete artifact is emitted. A directional result selects the corresponding
isolated-baseline or bounded persistent-construction design. An unresolved result selects only a
phase-specific follow-up justified by the largest reproducible paired phase movement; it does not
authorize persistent state by itself.

## 4. Closure matrix

| Path | Construction | Success/publication | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Shared outcome | eleven zeroed `i64` scalars | successful generation publishes non-overlapping completed clocks | existing error remains owner; partial clocks cannot form a complete helper record | max/EOG before decode leaves absent decode phases zero | no new native owner | existing layer-forward/provider owners plus real accounting equalities |
| Prefill | snapshot total counters before call | wall and exact claim/compute deltas include first output selection | helper refuses nonpositive or inconsistent clocks | failure publishes no qualification record | existing converged teardown | helper schema self-test and real run |
| Decode loop | start one timer only after iteration is admitted | first completed iteration and sum of later iterations; exact counter deltas | failed partial iteration is excluded from new completed-phase counters | EOG/maximum before iteration records nothing | existing loop temporaries die per iteration | source owner, zero/positive schema vectors, real equality checks |
| Teardown | start after loop returns | records converged release/publication wall | existing balance failure rejects helper | prefill/decode failure still converges through teardown | resident wrap then backend; existing balance fields | existing forced lifetime owners and real balance |
| Helper | production-order snapshot through decode | one exact schema record | invalid arguments, identities, token accounting, or engine result fail before print | N/A | invocation drops all state | pinned build, runner synthetic schema/accounting tests, real result |
| Solo leg | assert no matching process | one full helper | any process drift/helper failure aborts artifact | N/A | recheck no match | process classifier self-test and four real legs |
| Co-resident leg | start one owned server and wait ready | server warm, candidate condition, server re-warm, require RSS floor, time helper, record after RSS | malformed warmup, prefix, identity/RSS/process drift, or exit aborts | signal/deadline follows same cleanup | terminate, then kill/reap exact owner | warmup/RSS/process and forced-escalation self-tests plus four real legs |
| Aggregate | require four exact pairs/eight records | medians, bounds, paired phase deltas, decision | key/order/repeatability/accounting/bound drift rejects | no partial result | N/A | three decision vectors, deadband boundaries, non-narrowing refusal |
| Whole run | clean head and immutable identities | one schema-1 COMPLETE document | child diagnostic bounded; no partial JSON | missing prerequisite is one N/A line | restore generated helper; recheck tree/identities | restoration/deadline self-tests and complete real run |

## 5. Implementation and verification map

1. Add the eleven counters to the existing shared outcome and instrument the existing generation
   schedule without changing execution order or renderer output.
2. Add one qualification-only Align helper exposing those counters over the fixed request.
3. Add one bounded runner reusing item 54's pinned identities, environment, server pressure, and
   cleanup primitives; own the reduced eight-helper schedule, schema, accounting, narrowed bounds,
   and decision.
4. Run the source owners, helper build, self-test, and one complete real diagnosis. Record the exact
   result and selected next roadmap item here, in the roadmap, and in `HANDOFF.md`.
5. Run one comprehensive review, repair the complete accepted finding class once, rerun affected
   owners, exact-head publication preflight, required GitHub checks, and merge before starting the
   selected work.

No `make ci`, installed profile, platform matrix, 40-prompt corpus, coding validator, stress suite,
or unrelated benchmark is selected. This is a diagnostic measurement with a precommitted runtime
ceiling, not a product-speed claim.

The capability exceeds 1,000 hand-written lines because its 301-line Align helper must reproduce
the production preparation boundary while its bounded runner owns identity, balanced pressure,
schema, decision, signal cleanup, and model-free tests. Splitting counters, helper, and runner would
leave dormant producers or an unusable measurement consumer and repeat the same identity and
cleanup proof; they therefore ship as one consumer-complete failure domain.

The first implementation-head run is discovery evidence, not a result: the first solo helper paid
an 11.020-second cold construction interval while the other seven construction intervals were
0.231–0.815 seconds. Its first paired helper penalty was consequently -9.400 seconds even though
the other three were positive. The fixed two-token candidate conditioning above removes this
one-time cache state from every timed leg symmetrically; the complete diagnosis must be rerun before
any result is recorded.
