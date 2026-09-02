# R8 partial LRU expert cache

Status: design checkpoint; implementation not started

## 1. Decision and boundary

R8's reset-per-request measurement selected the simple LRU policy at a 975,175,680-byte expert
budget. This capability makes that decision executable in the existing real OLMoE consumer:
`ggml-spike --moe-decode-step`. It extends the already-shipped dense-resident mode with one
Align-owned partial expert cache shared by prefill and every decode step of one invocation.

This is a consumer-complete runtime/cache boundary, but not the final align-coder performance
claim. It must reduce physical expert pack reads while preserving the exact logits, routing,
oracles, and resource balances of the `dense` leg. Elapsed time is reported only as a diagnostic;
no time-to-passing-patch or decode-latency improvement is claimed until the cache is consumed by a
provider task and measured against the named local baseline.

The selected public operand is `dense+lru:BUDGET_BYTES` at the existing optional position 13.
`BUDGET_BYTES` is canonical unsigned decimal, greater than zero, and no larger than the existing
8-GiB window ceiling. `-` and `dense` retain their schema-2 behavior. No default changes.

## 2. Public-contract ledger

| Field | Settled contract |
| --- | --- |
| Surface | `ggml-spike --moe-decode-step PACK GEOMETRY TOKENS OUTPUT REFERENCE TRANSCRIPT KV_WIDTH LOGITS STEPS KV_SAVE KV_LOAD RESIDENT`; `RESIDENT` additionally accepts `dense+lru:BUDGET_BYTES` |
| Defaults | Omitted position 13 is still `-`; cache mode is never implicit |
| Result | a valid cache-mode request selects `R6_MOE_DECODE_STEP` schema 3 even if a later stage fails; schema 2 remains byte-identical for `-`, `dense`, and existing early refusals |
| Errors | `R8_CACHE_MODE` for malformed mode/budget; `R8_CACHE_BUDGET` before allocation when the budget cannot hold one key, exceeds 8 GiB, or cannot hold the model's routed width; existing earlier KV refusal precedence is unchanged |
| Ownership | one dense region, one claim window, and one expert cache buffer are owned by `execute`; cache metadata is owned by `schedule_decode`; no cache view escapes |
| Allocation | cache storage is `floor(BUDGET_BYTES / key_bytes) * key_bytes`, never above the requested budget, plus at most the existing alignment over-reservation; metadata is O(`n_layer * n_expert`) integers |
| Geometry | every expert key is the three compact claim planes; schema 3 refuses cache mode unless that byte size is positive and uniform across layers, matching the measured OLMoE model and making the byte-budget replay exact |
| Identity | key is `layer * n_expert + expert`; one slot holds one complete key in gate/up/down order |
| Policy | deterministic LRU; hit updates recency, miss evicts minimum `(last_use, key)`, and routed experts are demanded in the existing ascending per-layer order |
| Lifetime | empty before prefill, shared through prefill and all decode steps, released at invocation return; no cross-request, process-global, persisted, or network state |
| Validation order | reserved KV save, reserved KV load, residency grammar, ordinary inputs/pack/geometry, cache geometry and budget, allocations, backend/graphs |
| Schema | a valid cache-mode request uses schema 3 and adds unconditional `weights.expert_cache`; older modes and all refusals before valid cache-mode selection stay schema 2 without that member |
| Owner module | `src/moe_decode_step.align`; shared scalar output storage remains in `moe_model_forward.Outcome` and is not rendered by other arms |
| Acceptance | cache and dense normalized documents agree outside the enumerated cache/read counters and timings; all existing oracles pass; cache accounting reconciles requests = hits + misses and physical bytes = miss bytes |
| Real evidence | one fixed real prompt, 16 greedy steps, paired `dense` and `dense+lru:975175680`; exact logits/routing equality and at least 50,000 ppm fewer decode expert pack bytes |
| Primary metric | time to a passing patch remains deferred until provider consumption; this capability's named secondary metric is `weights.step_expert_pack_bytes` |
| Persisted/cache identity | N/A: invocation-local only; no artifact or cache survives return |
| Schema version | 3 after the new mode and its budget parse successfully; existing schema-2 consumers are not forced to accept a changed document |

### 2.1 Cache evidence

Schema 3 adds this object after the existing `weights` counters:

```text
"expert_cache": {
  "policy": "lru",
  "budget_bytes": integer,
  "capacity_bytes": integer,
  "key_bytes": integer,
  "slot_count": integer,
  "requests": integer,
  "hits": integer,
  "misses": integer,
  "evictions": integer,
  "resident_keys_final": integer,
  "resident_keys_high_water": integer,
  "bytes_served": integer,
  "bytes_fetched": integer
}
```

`requests`, `hits`, `misses`, `evictions`, `bytes_served`, and `bytes_fetched` cover prefill plus
decode. Each schema-3 `steps[].residency` additionally publishes that step's cache hits, misses,
evictions, bytes served, and bytes fetched. Existing arithmetic `expert_bytes` remains logical
demand; existing `expert_pread_bytes` and `step_expert_pack_bytes` become physical miss traffic in
cache mode. A hit copies the cached claim bytes into the unchanged claim window before phase B, so
the ggml graph and tensor placement do not acquire a cache lifetime.

## 3. Performance and resource gate recorded before implementation

The byte shipping floor is 50,000 ppm fewer `step_expert_pack_bytes` than the paired `dense` run
on the fixed 16-step real task. The prior reset replay predicts 536,000 ppm against streaming, but
that result is not substituted for the executable measurement. If the real paired task misses the
floor or changes any semantic oracle, the mode does not ship.

The added live expert allocation is at most the caller's budget plus 64 bytes of alignment
over-reservation. At the selected 975,175,680-byte budget, total expert-cache capacity must be
exactly that value on the reference model; a hidden whole-expert-footprint copy is forbidden.

| Evidence | Command | Diagnostic ceiling |
| --- | --- | --- |
| Synthetic owner | `make layer-forward-smoke` | 5 minutes |
| Real paired cache qualification | `make moe-partial-lru-qualification` | approximately 15 minutes; stop and diagnose material excess |
| Publication | `python3 scripts/pre-pr --owner-test r8-partial-lru-cache -- make layer-forward-smoke` | no `make ci`, installed profile, stress, or unrelated platform suite |

The real qualification performs only the paired task required by this cache boundary. It does not
repeat the broad historical OLMoE qualification matrix or the 40-prompt residency capture.

## 4. Closure matrix

| Cell | Runtime implementation | Synthetic owner | Real qualification |
| --- | --- | --- | --- |
| Construction | aligned bounded cache plus dense and claim regions | small explicit budget and exact slots | exact 975,175,680-byte capacity |
| First miss | read/scatter one block, copy compact claims into a free slot | miss bytes and contents | physical byte counter |
| Hit | copy slot to the same claim destinations; update recency | repeated key reads zero pack bytes | decode hits present |
| Eviction | minimum `(last_use, key)` slot reused | forced capacity pressure and deterministic victim | eviction count reported |
| Prefill/decode handoff | one metadata state spans both passes | first decode reuses a prefill key | paired run reports aggregate and step counters |
| Success semantics | unchanged phase-B claim window and graphs | whole normalized cache/dense equality | logits, routing, oracle equality |
| Malformed input | ordered grammar/budget refusals before allocation | empty, sign, leading zero, suffix, too small, too wide | N/A |
| Early graph failure | cache is ordinary Align storage; existing converged ggml teardown | forced failure with cache live | N/A |
| Cleanup | cache and metadata drop at invocation return | repeated deterministic invocations | process exits cleanly |
| Older modes | no cache allocation or schema/member change | existing golden byte equality | N/A |

Replacement, move-in/out, ABI records, generic monomorphization, connection-global state,
process-global state, persistence, and network cleanup are N/A: the cache is one local buffer plus
dense integer tables and never crosses those boundaries.

## 5. Implementation map

1. Parse and validate the new residency value without changing the existing two values or refusal
   precedence.
2. Allocate the bounded cache beside the two existing windows and construct dense key-to-slot,
   slot-to-key, and last-use tables in `schedule_decode`.
3. Route `stage_claims` through a cache-aware local staging function. Misses retain the current
   `read_block_scatter`; hits copy the three compact planes into their existing destinations.
4. Thread one cache state through prefill and decode, publish schema-3 aggregate/per-step evidence,
   and preserve schema 2 byte-for-byte elsewhere.
5. Add the synthetic owner cases, the bounded paired real runner, and record the one measurement.
