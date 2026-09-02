# R8 partial LRU expert cache

Status: implementation and measurement complete; review findings repaired; publication pending

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
| Ownership | one allocation owned by `execute` contains disjoint dense and expert-cache regions, the claim window remains separate, and cache metadata is owned by `schedule_decode`; no cache view escapes |
| Allocation | cache storage is `floor(BUDGET_BYTES / slot_bytes) * slot_bytes`, never above the requested budget, plus at most the existing alignment over-reservation; `slot_bytes` is the maximum layer key size and metadata is O(`n_layer * n_expert`) integers |
| Geometry | every expert key is the three compact claim planes; their logical byte size may vary by layer, while every physical slot uses the maximum positive layer key size so any key fits without exceeding the byte budget |
| Identity | key is `layer * n_expert + expert`; one slot holds that key's complete gate/up/down bytes and may leave an unused tail below the fixed slot stride |
| Policy | deterministic LRU; hit updates recency, miss evicts minimum `(last_use, key)`, and routed experts are demanded in the existing ascending per-layer order |
| Lifetime | empty before prefill, shared through prefill and all decode steps, released at invocation return; no cross-request, process-global, persisted, or network state |
| Validation order | reserved KV save, reserved KV load, residency grammar, ordinary inputs/pack/geometry, cache geometry and budget, allocations, backend/graphs |
| Schema | a valid cache-mode request uses schema 3 and adds unconditional `weights.expert_cache`; older modes and all refusals before valid cache-mode selection stay schema 2 without that member |
| Owner module | `src/moe_decode_step.align`; shared scalar output storage remains in `moe_model_forward.Outcome` and is not rendered by other arms |
| Acceptance | cache and dense normalized documents agree outside the enumerated cache/read counters and timings; all existing oracles pass; cache accounting reconciles requests = hits + misses and bounds physical bytes around logical miss bytes |
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
  "miss_bytes": integer,
  "bytes_fetched": integer
}
```

`key_bytes` is the fixed maximum slot stride, not a claim that every layer's logical key has that
size. `requests`, `hits`, `misses`, `evictions`, `bytes_served`, `miss_bytes`, and `bytes_fetched`
cover prefill plus decode. Each schema-3 `steps[].residency` additionally publishes that step's
cache hits, misses, evictions, bytes served, logical miss bytes, and physical bytes fetched.
Existing arithmetic `expert_bytes` remains logical demand; existing `expert_pread_bytes` and
`step_expert_pack_bytes` become physical miss traffic in cache mode. A hit copies the cached claim
bytes into the unchanged claim window before phase B, so the ggml graph and tensor placement do not
acquire a cache lifetime.

## 3. Performance and resource gate recorded before implementation

The byte shipping floor is 50,000 ppm fewer `step_expert_pack_bytes` than the paired `dense` run
on the fixed 16-step real task. The prior reset replay predicts 536,000 ppm against streaming, but
that result is not substituted for the executable measurement. If the real paired task misses the
floor or changes any semantic oracle, the mode does not ship.

The added live expert allocation is at most the caller's budget plus 64 bytes of alignment
over-reservation. The reference pack has two logical layer-key sizes, 3,538,944 and 4,079,616 bytes;
the larger is the slot stride. At the selected 975,175,680-byte budget this yields 239 slots and
975,028,224 bytes of capacity. The 147,456-byte remainder stays unallocated, and a hidden
whole-expert-footprint copy is forbidden. This corrects the pre-implementation assumption that the
simulator's 3,809,280-byte average expert equivalent was a uniform runtime tensor size.

| Evidence | Command | Diagnostic ceiling |
| --- | --- | --- |
| Synthetic owner | `make layer-forward-smoke` | 5 minutes |
| Real paired cache qualification | `scripts/run-moe-partial-lru` | approximately 15 minutes; stop and diagnose material excess |
| Publication | `python3 scripts/pre-pr --owner-test r8-partial-lru-cache -- make layer-forward-smoke` | no `make ci`, installed profile, stress, or unrelated platform suite |

The real qualification performs only the paired task required by this cache boundary. It does not
repeat the broad historical OLMoE qualification matrix or the 40-prompt residency capture.

### 3.1 Candidate measurement

The focused paired qualification passed on the reference OLMoE model in 9.75 seconds of measured
model execution (5.29 seconds dense and 4.46 seconds cache; compiler setup was approximately 1.2
seconds). Across the 16 decode steps, dense read 7,801,405,440 expert-pack bytes and cache mode read
2,920,955,904: **625,585 ppm removed**, above the 50,000-ppm shipping floor. The invocation recorded
1,279 hits, 1,112 misses, and 873 evictions while preserving exact generated logits, routing, and
the normalized semantic document. Reported internal elapsed time was 4.407 seconds dense and 4.435
seconds cache, diagnostic only; this capability still makes no elapsed improvement claim.

## 4. Closure matrix

| Cell | Runtime implementation | Synthetic owner | Real qualification |
| --- | --- | --- | --- |
| Construction | aligned bounded cache plus dense and claim regions | small explicit budget and exact slots | exact 975,028,224-byte capacity and 239 slots |
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
2. Derive the maximum positive layer-key size, allocate the bounded fixed-stride cache beside the
   two existing windows, and construct dense key-to-slot and last-use tables in `schedule_decode`;
   eviction recovers the resident key by scanning that bounded key space.
3. Route `stage_claims` through a cache-aware local staging function. Misses retain the current
   `read_block_scatter`; hits copy the three compact planes into their existing destinations.
4. Thread one cache state through prefill and decode, publish schema-3 aggregate/per-step evidence,
   and preserve schema 2 byte-for-byte elsewhere.
5. Add the synthetic owner cases, the bounded paired real runner, and record the one measurement.
