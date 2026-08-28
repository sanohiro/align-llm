# R3-RESIDENCY-SIM

Status: implementation candidate. This document is the authoritative public-contract ledger,
closure matrix, and acceptance plan for the first R3 consumer capability.

## 1. Capability boundary

R2 established a measured prefill demand signal: adjacent-token expert reuse is 286 per mille
against a 125 per mille null on the real OLMoE model. R1C supplies the other input a cache decision
needs: each `(layer, expert)` `ExpertBlock` costs either 3,538,944 or 4,079,616 bytes on that model.
R3 consumes those two facts without changing either producer.

The consumer-complete path is:

```text
R2 selections[] + R1 ExpertBlock byte_size + explicit hardware cost model
  -> R3_RESIDENCY_TASK
  -> main --residency-sim
  -> R3_RESIDENCY_RESULT comparing seven policies under one identical cold-cache schedule
```

The capability answers one question: under the declared cache capacity and cost model, which of
the required policy families has the lowest simulated residency penalty, and is it strictly better
than LRU? The result is a deterministic comparison, not a measured runtime-speed claim.

### 1.1 Included

- one Align-owned simulator and CLI adapter;
- schema-1 task and result documents;
- LRU, LFU, recent-reuse, score-based, top-k-prefetch, impact-prefetch, and CPU-fallback rows;
- byte-capacity eviction over heterogeneous expert sizes;
- separate prefill and decode counters, with ambiguous first-token graphs in neither phase;
- an adapter that joins existing R2/R1 documents without changing their schemas;
- a hosted synthetic end-to-end owner and an opt-in real-model qualification.

### 1.2 Explicitly deferred

- execution, allocation, transfer, ggml compute, or mutation of an `.alignpack` file;
- a second DRAM/NVMe cache tier, persistent cache state, concurrent requests, and async I/O;
- router-score capture, which R2A section 5.4 assigns to a future R2 schema 2;
- task/language/repo profiles, because R2b has not produced them;
- decode-policy claims, unless a supplied task contains `phase: "decode"` rows;
- a throughput, TTFT, decode-latency, or time-to-passing-patch claim.

Those are separate failure domains. This capability may exceed roughly 1,000 hand-written changed
lines because splitting the task codec, simulator, seven-policy comparison, and owner would leave a
dormant format with no useful caller and duplicate the same validation and review proof.

## 2. Public-contract ledger

### 2.1 CLI

```text
main --residency-sim TASK_JSON [RESULT_JSON]
```

Exactly two or three arguments follow the executable. Both paths use the existing Track B lexical
path rule: non-empty, at most 4,096 bytes, no embedded NUL. All path validation happens before the
task is opened. The two-argument machine form prints the canonical result and one newline, and
nothing else. The three-argument file form writes the same bytes to `RESULT_JSON` and prints this
stable positional summary:

```text
residency simulation:
status:
OK | ERROR
baseline:
lru
best policy:
<policy | ->
verdict:
IMPROVED | BASELINE | ERROR
demands:
<integer>
baseline cost ns:
<integer | ->
best cost ns:
<integer | ->
```

A semantic task defect produces a schema-1 `status: "error"` result, writes or prints it, then maps
to `Error.Invalid`. A JSON/UTF-8/decode failure returns the decoder error with no result bytes and
does not touch `RESULT_JSON`. A result write failure returns the filesystem error with no summary.
There is no environment input and no default hardware profile.

### 2.2 Task format — `R3_RESIDENCY_TASK`, schema 1

Canonical declaration order:

```json
{
  "schema_version": 1,
  "kind": "R3_RESIDENCY_TASK",
  "task_id": "olmoe-prefill-target-a",
  "trace_sha256": "64 lowercase hexadecimal digits",
  "model_ir_sha256": "64 lowercase hexadecimal digits",
  "model_id": "olmoe-q4-k-m",
  "n_layer": 16,
  "n_expert": 64,
  "n_expert_used": 8,
  "tokens_truncated": false,
  "token_reduced_layer_count": 40,
  "hardware": {},
  "blocks": [],
  "demands": []
}
```

The typed decoder follows Align's existing JSON contract: every declared field appears exactly
once, duplicate declared fields fail, unknown fields are grammar-validated and ignored, the whole
input is valid UTF-8, and trailing bytes are rejected. Unknown fields do not enter task identity
and are not preserved in the result.

| Field | Type and rule |
| --- | --- |
| `schema_version` / `kind` | Exactly `1` / `R3_RESIDENCY_TASK` |
| `task_id` / `model_id` | UTF-8, 1..256 bytes, no NUL |
| `trace_sha256` / `model_ir_sha256` | Exactly 64 lowercase hexadecimal bytes. `model_ir_sha256` hashes the exact model-IR file bytes. `trace_sha256` hashes a manifest formed by appending each trace's lowercase SHA-256 hex digest and one `\n`, in operand order |
| `n_layer` | `[1, 512]` |
| `n_expert` | `[1, 4096]` |
| `n_expert_used` | `[1, n_expert]`; provenance only, not a fabricated missing-slot count |
| `tokens_truncated` | True when any contributing R2 graph hid token positions. Always echoed |
| `token_reduced_layer_count` | Non-negative count summed from R2 documents. Omitted layers create no demand row and remain visible here |
| `hardware` | Section 2.3 |
| `blocks` | Section 2.4; 1..2,048 rows |
| `demands` | Section 2.5; 1..65,536 rows |

### 2.3 Hardware cost model

```json
"hardware": {
  "name": "target-a",
  "cache_capacity_bytes": 67108864,
  "transfer_fixed_ns": 1000,
  "transfer_ns_per_kib": 100,
  "cpu_fixed_ns": 1000,
  "cpu_ns_per_kib": 300,
  "prefetch_cost_per_mille": 250,
  "prefetch_count": 8,
  "score_recency_weight": 4,
  "score_frequency_weight": 4,
  "score_impact_weight": 2,
  "score_layer_weight": 1
}
```

`name` follows the identifier rule. Capacity is positive and at most 2^50. Fixed costs and
per-KiB costs are in `[0, 10^12]`. `prefetch_cost_per_mille` is `[0, 1000]`: zero models perfect
overlap and 1000 makes prefetched transfer cost equal demand transfer cost. `prefetch_count` is
`[1, n_expert]`. Score weights are `[0, 10^6]` and at least one is positive. Before any policy
state is allocated, the task must also satisfy
`demands.len() * blocks.len() * prefetch_count <= 100,000,000`; failure is `R3_HARDWARE` with
`hardware.prefetch_work`. This admits the frozen real workload (10,800 demands, 1,024 blocks, and a
prefetch count up to 9) while refusing declarations whose repeated candidate/eviction work would
make an otherwise schema-valid task an unbounded CLI stall.

All arithmetic is checked before addition or multiplication. Transfer cost for `bytes` is:

```text
kib = ceil(bytes / 1024)
transfer_cost = transfer_fixed_ns + kib * transfer_ns_per_kib
cpu_cost = cpu_fixed_ns + kib * cpu_ns_per_kib
prefetch_cost = transfer_cost * prefetch_cost_per_mille / 1000
```

The costs are caller declarations. The simulator never labels them measured.

### 2.4 Block rows

```json
{"layer": 0, "expert": 0, "bytes": 4079616}
```

Rows are strictly ascending by `(layer, expert)`, unique, and within the declared extents. `bytes`
is positive and at most 2^50. A demand must join exactly one row. Blocks not demanded may remain so
prefetch policies can select historically known peers in the next layer.

### 2.5 Demand rows

```json
{"graph": 0, "layer": 0, "token": 0, "slot": 0, "expert": 12, "phase": "prefill"}
```

Rows preserve R2 observation order and are strictly ascending by
`(graph, layer, token, slot)`. Ordinals are non-negative; layer/expert are within declared extents;
`phase` is exactly `prefill`, `decode`, or `single_token_first_graph`. All rows of one graph use one
phase. Slots begin at zero and are strictly increasing inside each `(graph, layer, token)` group;
gaps are allowed because R2 prints `0,1,2,n_expert_used-3,n_expert_used-2,n_expert_used-1` when the
router has more than six slots. An expert appears at most once in a group. R2's unprinted slots are
not invented.

### 2.6 Validation and error precedence

Semantic validation is side-effect-free and uses this exact first-error order:

1. `R3_SCHEMA` — schema version;
2. `R3_KIND` — kind;
3. `R3_ID` — task/model identifiers and both digests;
4. `R3_SHAPE` — declared layer/expert extents and truncation counters;
5. `R3_HARDWARE` — capacity, costs, prefetch count, and score weights;
6. `R3_BLOCK` — block field bounds;
7. `R3_BLOCK_ORDER` — block order or duplicate;
8. `R3_DEMAND` — demand field, phase, slot, or duplicate-expert defect;
9. `R3_DEMAND_ORDER` — observation order, graph-phase mismatch, or non-increasing slot;
10. `R3_JOIN` — a demand without exactly one block;
11. `R3_ARITHMETIC` — any cost/metric upper-bound proof.

`error_detail` is a bounded ASCII token: the failing field name or `<row-kind>[<ordinal>]`, never a
path or free prose. Invalid results carry zero demands, `best_policy: ""`, `verdict: "ERROR"`, and
an empty `policies` array. `demand_bytes`, `baseline_cost_ns`, and `best_cost_ns` are also zero;
the file-form summary renders both costs as `-`, so no sentinel is presented as a measurement.

### 2.7 Policy semantics

Every policy receives the identical cold cache, block table, demand order, byte capacity, and cost
model. A resident set may never exceed `cache_capacity_bytes`. A block larger than the capacity is
served but never retained.

On a resident demand, the policy records one hit and no transfer cost. On a miss, it evicts whole
blocks until the new block fits, records one demand transfer, and inserts the block. Ties use lower
`(layer, expert)` order. The fixed result order is:

1. `lru` — evict lowest last-access ordinal;
2. `lfu` — evict lowest access count, then LRU;
3. `recent-reuse` — evict the block whose last hit is oldest or absent, then LRU;
4. `score-based` — evict the lowest weighted sum of normalized recency, frequency, transfer impact,
   and inverse layer position; it never invents router or profile scores;
5. `top-k-prefetch` — LRU demand eviction, then prefetch up to `prefetch_count` historically most
   frequent blocks in the structurally known next group's layer;
6. `impact-prefetch` — LRU demand eviction, then prefetch by historical frequency multiplied by the
   block's declared transfer cost;
7. `cpu-fallback` — LRU, except a miss whose declared CPU cost is strictly lower than transfer cost
   executes on CPU and is not inserted. A tie transfers and inserts.

Prefetch runs only after a complete `(graph, layer, token)` group. It may inspect the next group's
graph/layer/token identity but not its expert ids. History includes only demands already processed.
At that boundary each policy snapshots the eligible non-resident candidates and ranks that snapshot
once; evictions caused by applying the ranked list do not add newly non-resident blocks to the same
batch. Candidates with no history are ineligible. A ranking tie selects lower `(layer, expert)` first.
An already resident candidate costs nothing and does not consume the prefetch count. A prefetched
entry becomes useful once when a later demand first hits it before eviction; that hit clears its
prefetched marker. Entries still marked when evicted or when the run ends each add one unused
prefetch. Demand eviction ties choose the lower `(layer, expert)` row as the victim.

The score-based normalized components are each `[0, 1000]`: frequency as
`block_accesses * 1000 / demands_processed`, recency as `1000 / (age + 1)`, transfer impact as
`block_transfer_cost * 1000 / maximum_block_transfer_cost`, and inverse layer position as
`(n_layer - layer) * 1000 / n_layer`. Eviction cannot occur before one demand has been processed,
so the frequency denominator is positive. Each component is multiplied by its named hardware
weight; checked arithmetic precedes the sum.

### 2.8 Result format — `R3_RESIDENCY_RESULT`, schema 1

Canonical top-level order:

```json
{
  "schema_version": 1,
  "kind": "R3_RESIDENCY_RESULT",
  "task_id": "olmoe-prefill-target-a",
  "status": "ok",
  "error_code": "",
  "error_detail": "",
  "trace_sha256": "...",
  "model_ir_sha256": "...",
  "model_id": "olmoe-q4-k-m",
  "hardware": {},
  "tokens_truncated": false,
  "token_reduced_layer_count": 40,
  "score_inputs": "recent+frequency+transfer_cost+layer",
  "baseline_policy": "lru",
  "best_policy": "lfu",
  "verdict": "IMPROVED",
  "demand_count": 270,
  "demand_bytes": 1000000,
  "baseline_cost_ns": 1000,
  "best_cost_ns": 900,
  "policies": []
}
```

`status` is `ok` or `error`. `verdict` is `IMPROVED` only when the selected non-LRU row has a
strictly lower `residency_cost_ns` than LRU, otherwise `BASELINE`; errors use `ERROR`. Winner order
is residency cost, transfer bytes, then the fixed policy order, so a tie retains LRU.

Each policy row has this exact order and integer fields:

```text
policy, demand_count, hit_count, miss_count, hit_per_mille,
hit_bytes, miss_bytes, transfer_bytes, prefetch_bytes,
useful_prefetch_count, unused_prefetch_count, eviction_count,
cpu_fallback_count, residency_cost_ns, peak_resident_bytes,
prefill_demand_count, prefill_hit_count, prefill_hit_per_mille,
decode_demand_count, decode_hit_count, decode_hit_per_mille
```

Per-mille values use integer division. A phase with no demands has `-1`, not zero, for its hit rate.
`transfer_bytes` includes demand and prefetch transfer. `prefetch_bytes` is the subset transferred
before demand. CPU fallback bytes are not transfer bytes. `demand_bytes` is the sum of every
demanded block's bytes regardless of hit or miss. `residency_cost_ns` is demand transfer cost plus
scaled prefetch cost plus CPU fallback cost; ordinary hits add zero. `peak_resident_bytes` is
asserted at or below capacity.

### 2.9 Ownership, allocation, and identity

`fs.read_file` owns the task bytes. Decode occurs inside one arena; task strings borrow those bytes
and task arrays are arena-owned. The simulator borrows the decoded task, creates a validation index
proportional to `demands.len()`, fixed-size scalar columns and boundary ranking arrays proportional
to `blocks.len()`, and exactly seven result rows. No input field is moved on the first policy. The
encoded result is cloned before the arena ends. Success, semantic failure, `?`, and output-write
failure release the task bytes, every decoded array, all index/scalar columns, and the encoded
builder exactly once.

Task identity is the tuple `(schema_version, task_id, trace_sha256, model_ir_sha256, hardware)`.
There is no cache artifact and no compatibility route for future schemas.

## 3. Adapter contract

The adapter command is:

```text
scripts/build-residency-task \
  --task-id ID --model-id ID --hardware HARDWARE_JSON --output TASK_JSON \
  MODEL_IR_JSON TRACE_JSON [TRACE_JSON ...]
```

`HARDWARE_JSON` is exactly the section 2.3 object, not a profile name or environment lookup. The
adapter accepts one schema-2 `R1_MODEL_IR` followed by one or more schema-1
`R2_ACTIVATION_TRACE` documents in caller order. It rejects an occupied output path, duplicate
JSON keys, non-OK documents, a non-`olmoe` model, non-MoE traces, model/trace extent
disagreement, every section 2.3 hardware bound including the task-wide work envelope, malformed
block/demand order, and a missing `ExpertBlock` join. It extracts only
`ExpertBlock` rows, offsets graph ordinals between documents, copies each selection's exact phase
from its owning graph, preserves printed slot ordinals without filling hidden slots, and writes
canonical compact task JSON plus one newline by create-without-replace followed by flush and close.
It derives `tokens_truncated` as OR over every graph and sums the number of
`moe.token_reduced_layers` entries over all traces. No input path is written into the task.

The adapter is a producer of the task format, not a second simulator. An independent Python oracle
in the smoke runner computes all seven rows from the emitted task and compares the complete result.

## 4. Closure matrix

| Surface / path | Construction and success | Failure / early exit / cleanup | Exact owner |
| --- | --- | --- | --- |
| CLI arity and paths | machine and file forms emit identical document bytes | too few/many, empty/NUL/overlong path before open; write failure has no summary | `run-residency-sim-smoke`: `cli-*` |
| Decode | schema-1 task inside one arena; grammar-valid unknown fields are ignored | malformed, invalid UTF-8, missing/duplicate declared field write nothing and preserve destination | `decode-*` |
| Semantic validation | complete ordered block/demand tables join; duplicate-expert index is order-independent | every code and multi-invalid precedence, including duplicate plus out-of-order rows; zero policies on error | `invalid-*`, `precedence-*` |
| LRU / LFU / recent reuse | heterogeneous byte capacity, deterministic ties | oversized block served but not retained; zero-capacity impossible by validation | policy oracle cases |
| Score-based | all four available inputs and weight extremes | zero-total weights rejected; checked product/sum | `score-*`, `arithmetic-*` |
| Prefetch | structural next group only; one frozen/ranked eligible snapshot; useful and unused rows | cold history, already resident, eviction, final unused accounting | `prefetch-*`, complete oracle |
| CPU fallback | cheaper CPU, cheaper transfer, strict tie rule | oversized block and fallback never overfill cache | `cpu-*` |
| Phase split | prefill, decode, ambiguous first graph | absent phase reports `-1`; graph phase mismatch rejected | `phase-*` |
| Seven-policy result | fixed row/order, deterministic winner, LRU tie | arithmetic failure produces no partial rows | complete golden + oracle |
| Adapter | R2/R1 join, graph offset, mixed block sizes | every producer/status/extent/join/hardware/work-envelope refusal before output replacement | adapter fixture matrix |
| Ownership | task borrowed across seven runs; result cloned out | decode, semantic error, loop exit, and write `?` release once | whole/per-unit compilation, repeated smoke |
| Bounded work | binary demand/block joins; `O(demands log demands)` duplicate validation; one `O(blocks log blocks)` candidate ranking per prefetch boundary; victim scans amortized by insertions; and the explicit 100,000,000 `demands * blocks * prefetch_count` envelope | row caps and the work product checked before validation/ranking state or policy work | `limit-*`, adapter refusal, owner elapsed diagnostic |
| Generic/interface/cache | N/A — no generic or exported interface surface | N/A — concrete module only | `make check`, `make build` |
| Process/shared state | N/A — no child process, thread, global cache, or environment | independent processes share no state | CLI isolation case |

## 5. Acceptance and qualification

The hosted owner is `make residency-sim-smoke`. It builds synthetic OLMoE R1/R2 producers, runs the
adapter, executes the Align CLI, compares the complete document with an independent oracle, covers
every error code and policy branch, and reruns existing R1/R2 owners affected by the join.

The opt-in `make residency-sim-qualification` consumes the real OLMoE model and R2 instrument under
the existing `ALIGN_LLM_GGUF_MODEL`, `ALIGN_LLM_LLAMA_EVAL_CALLBACK`,
`ALIGN_LLM_LOCALITY_PROMPTS`, and `ALIGN_LLM_LOCALITY_PROMPT_COUNT` inputs. It additionally requires
`ALIGN_LLM_R3_HARDWARE`, the section 2.3 JSON object, and `ALIGN_LLM_R3_MEASUREMENT`, one bounded
line naming the measurement source for those declared costs. It records the task digest, hardware
profile, capacity, measurement source, all seven policy rows, winner, and whether decode was
observed. A missing model/instrument/profile/measurement prints one exact `N/A` line. The
qualification is not in an aggregate.

R3's roadmap gate is met only when that focused qualification identifies a strict non-LRU winner
under a hardware profile whose costs are backed by named measurements. Hosted synthetic evidence
ships the simulator but does not by itself claim a target-hardware policy win.

## 6. Author consistency pass

- R2 `selections[]` remains the sequence source; no locality aggregate is substituted.
- R1/R4 remains the byte-size/layout source; no constant expert size is invented.
- Prefill/decode remain separate and an absent decode phase stays `-1`/unclaimed.
- All seven roadmap policy families have one row and deterministic semantics.
- Router/task/language/repo scores are explicitly unavailable rather than zero-filled.
- The CLI, both schemas, validation order, ownership, identity, matrix, owner, and qualification are
  defined in this ledger before implementation.

## 7. Implementation correction ledger

1. The design checkpoint said slots were contiguous. R2's shipped top-8 truncation contract and
   real OLMoE documents contain `0,1,2,5,6,7`; requiring contiguity would reject the exact producer
   R3 is meant to consume. Section 2.5 now requires zero-first, strictly increasing slots and keeps
   gaps, while the adapter still refuses to invent the hidden rows.
2. Comprehensive review found that repeatedly scanning the full block table for each prefetch
   candidate allowed hundreds of billions of comparisons at the independent row caps. Prefetch now
   freezes and ranks one eligible snapshot per boundary, and section 2.3 adds a checked task-wide
   work envelope enforced by both the adapter and simulator before output/policy work.
3. The adapter originally checked hardware types but not section 2.3 ranges, so it could create a
   new task that the simulator immediately refused and leave the create-without-replace destination
   occupied. It now mirrors every hardware range, the model-dependent count, and the work envelope.
4. File mode wrote the encoded JSON without machine mode's trailing newline even though section 2.1
   promised byte identity. File mode now writes the newline and the owner compares exact bytes.
5. Duplicate-expert detection originally stopped at the first different adjacent group and could
   lose `R3_DEMAND` precedence when the same invalid input was also out of order. A bounded sorted
   demand index now detects the duplicate class independently before observation-order validation.
