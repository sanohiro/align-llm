# R1B-GPTOSS-MOE-IR: gpt-oss MoE frontend, per-expert Block IR, and `R1_MODEL_IR` schema 2

Status: plan of record for the second Track B R1 capability named by `docs/specs/roadmap.md` section
R1 ("gpt-oss/MoE frontend (`ExpertBlock`/`RouterBlock`) is implemented later as a separate
capability"). It is authoritative for the R1B public contract: the architecture dispatch behind
`main --model-ir`, the `R1_MODEL_IR` document at `schema_version: 2`, the new architecture-neutral
IR builder `src/model_ir.align`, the new `src/frontend_gpt_oss.align` owner module, and the MXFP4
row added to the GGML block-geometry table in `src/gguf.align`.

`docs/specs/r1-qwen-model-ir.md` remains authoritative for everything this document does not amend:
the `GgufTable` producer surface, the CLI grammar, the geometry and overflow rules, the size-sum
oracle, and the qwen2 Model IR. `docs/specs/align-llm.md` remains authoritative for the
architecture, including the `BlockKind` enumeration and the hierarchical-memory tiers this document
finally maps onto real blocks; `docs/specs/roadmap.md` remains authoritative for delivery order.
`docs/specs/r0-gguf-inspection.md` remains authoritative for the GGUF container contract.

This document triggers the `CLAUDE.md` proportional design gate on three counts: it changes a
versioned exchanged format (`R1_MODEL_IR` 1 -> 2), it changes an ownership boundary (the Model IR
derivation moves out of `src/frontend_qwen.align` into a neutral builder), and it introduces a
coordinated invariant across four modules (`src/gguf.align`, `src/model_ir.align`,
`src/frontend_qwen.align`, `src/frontend_gpt_oss.align`) plus `src/main.align` and the fixture
graph.

Section 6 records the amendments this capability owes `docs/specs/r1-qwen-model-ir.md`. Section 7 is
reserved for implementation corrections, following that document's own section 7 convention; it is
empty until the capability is implemented.

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

Turn one real gpt-oss-architecture GGUF file into the same two intermediate representations R1
produces for a dense model, with the two block kinds a dense model cannot produce:

- **Model IR** with `n_expert > 0` and `n_expert_used > 0`, plus the expert feed-forward width and
  the attention geometry gpt-oss declares rather than implies.
- **Block IR** containing one `RouterBlock` per layer and one `ExpertBlock` per **(layer, expert)
  pair**, each `ExpertBlock` naming the exact byte sub-range of the stacked expert tensors that
  belongs to its expert, with coverage complete and the size-sum oracle holding.

Per-expert granularity is the whole point of the capability, and section 2.4.1 argues it rather than
assuming it. `docs/specs/align-llm.md` section 6 places "hot expert" in VRAM, "warm expert" in DRAM,
and "cold expert" in NVMe; section 7.4 scores a cache entry by its router score; and
`docs/specs/roadmap.md` section R2 measures "token-to-token expert reuse" and section R3 simulates
LRU / LFU / recent-reuse / score-based / top-k-prefetch policies. Every one of those consumers has
the individual expert as its unit. A Block IR whose smallest MoE unit is the layer cannot express
any of them.

### 1.2 In scope

1. Architecture dispatch on `general.architecture` inside `main --model-ir`, with `qwen2` and
   `gpt-oss` as the two accepted values and everything else rejected exactly as R1 rejects it today.
2. A new architecture-neutral module `src/model_ir.align` that owns the geometry pass, block
   resolution, block arithmetic, coverage, the size-sum oracle, and the whole document renderer, so
   that one exchanged format has exactly one producer.
3. A **block plan** data surface: each frontend describes its architecture as parallel `array<i64>`
   columns plus one concatenated name stream and hands it to the neutral builder. No traits, no
   generics, no callbacks, no `PROPOSED` Align surface.
4. `src/frontend_gpt_oss.align`: the gpt-oss hyperparameters, the per-layer block plan including
   `RouterBlock` and `n_expert` `ExpertBlock`s, and the gpt-oss `model` object.
5. `R1_MODEL_IR` at `schema_version: 2`, whose only neutral change is two additive fields on the
   block tensor record: `claimed_absolute_offset` and `claimed_nbytes`.
6. One new GGML geometry row: `MXFP4` (id 39, 32 elements per block, 17 bytes per block), whose
   provenance and acceptance are settled in section 2.8.2.
7. A **claim-tiling** check: the block claims over a tensor either include one whole-tensor claim or
   exactly partition its byte range, with no gap and no overlap.
8. A synthetic gpt-oss corpus in `scripts/gguf_fixture.py` and its cases in
   `scripts/run-model-ir-smoke`.

### 1.3 Non-goals

- **No layout plan, no residency tier, no prefetch policy, and no `.alignpack`.** R1B makes
  per-expert residency *expressible*; deciding it is R2 and R3. R1B assigns no tier to any block.
- **No expert trace and no router observation.** R2 observes router tensors through a runtime
  callback. R1B reads no payload byte and links no runtime; it names the router tensor and its byte
  range and stops.
- **No interpretation of the MoE gating parameters.** `expert_gating_func`, `expert_weights_scale`,
  `expert_weights_norm`, and the swiglu clamp keys are not read. Reporting a value R1B cannot
  validate would be worse than omitting it, and no consumer exists yet. Section 5.4.
- **No interpretation of sliding-window attention.** `attention.sliding_window` and
  `attention.sliding_window_pattern` are **reported, never interpreted**, exactly as R1 reports
  `rope.scaling_type`. They change no block, no shape, and no byte.
- **No tensor payload decode and no dequantization**, including no MXFP4 unpacking. R1B adds the
  MXFP4 *geometry* row and never touches an MXFP4 byte. R1's non-goal stands unchanged.
- **No tokenizer and no vocabulary materialization.** Unchanged from R1 section 1.3; Request 22
  stays non-blocking and unconsumed.
- **No architecture beyond `qwen2` and `gpt-oss`.** `qwen3`, `qwen3moe`, `deepseek2`, and the other
  MoE relatives each get their own frontend and their own plan. Section 5.5.
- **No real-model download.** `gpt-oss-20b-mxfp4.gguf` is 12.1 GB and is **not** fetched by this
  capability. Section 4.4 records the parity qualification as an explicit `N/A` and names the
  decision the user owns.

### 1.4 Gate statement

The roadmap gate for R1 is *Model IR and Block IR can be produced*; R1 discharged it for the dense
half. R1B discharges the MoE half in three parts:

1. `make model-ir-smoke` — the same self-contained owner, extended with the gpt-oss corpus. It
   asserts `n_expert`, `n_expert_used`, every `RouterBlock`, every `ExpertBlock`, every per-expert
   claim, the MXFP4 byte sizes, coverage, claim tiling, and the size-sum oracle, with no model and
   no network.
2. The size-sum oracle and the **claim-tiling oracle** (section 4.3), both computed from inside the
   program on any input, real or synthetic.
3. `make model-ir-parity` against a real `gpt-oss` model — the roadmap gate's external check.
   Section 4.4 records it as an opt-in qualification with a concrete `N/A` reason, because the model
   is not present on this host.

## 2. Public-contract ledger

### 2.1 Verified Align surface at pin `4b515f8d`

R1B consumes **no** surface R1 did not already prove. The rows below are the ones R1B leans on
hardest, each with the evidence that it works at the pin, so no reviewer has to rediscover them.

| Surface | Status at the pin | Consequence for R1B |
| --- | --- | --- |
| `array<i64>` field indexed through a `borrow` record parameter (`t.tensor_offsets[i]`) | **Shipped.** `docs/specs/r1-qwen-model-ir.md` section 7, item 1 records the probe that settled it, and every `GgufTable` accessor uses it | `BlockPlan` (section 2.3.3) is the same shape as `GgufTable` and is read the same way |
| Owned `string` field sliced through a `borrow` record parameter (`t.keys[a..b]`), compared inline against a `str` | **Shipped.** Same item | `BlockPlan.names` is one concatenated stream addressed by explicit `[start, end)` spans |
| `array_builder<i64>` as a `borrow mut` parameter | **Shipped.** `docs/specs/r1-qwen-model-ir.md` section 7, item 2 corrects R0's claim: `array_builder<T>` *is* admitted in that position | A frontend's plan-building helpers accumulate columns across function boundaries |
| `builder` as a parameter type | **NOT available.** Same item; Request 24 is `PROPOSED` | The neutral renderer is a set of functions that **return owned `string`** and are spliced by the caller, exactly as `tensor_json` / `source_json` / `dims_json` already do in `src/frontend_qwen.align` |
| 3- and 4-axis tensor dimensions | **Shipped in the producer.** `GgufTable` already carries `tensor_dim0..3` and `tensor_n_dims`, and `gguf.tensor_dim(t, index, axis)` reads any axis | A stacked `[n_ff, n_embd, n_expert]` expert tensor needs no new `GgufTable` field |
| `sort()` over `array<i64>` | **Shipped.** `docs/specs/r1-qwen-model-ir.md` section 2.7 | The claim list of section 2.6 step 11 is sorted once, as the tensor-name index already is |
| `Result<T, Error>`, `Option<T>`, `.clone()` through a borrow, `builder`, integer `as` | **Shipped**, unchanged from R0 and R1 | unchanged |

**No `PROPOSED` request is consumed.** Requests 21, 22, 23, and 24 are all `PROPOSED` in
`docs/align-requests.md` and remain so:

- **Request 21** (`fs.open_ro`): inherited unchanged. R1B opens nothing R1 did not; the model path
  still reaches the filesystem only through `gguf.read_table`.
- **Request 22** (indexing arrays of Move elements): unconsumed. R1B reads no `array<string>` and
  builds no tokenizer. `BlockPlan` deliberately repeats `GgufTable`'s stream-plus-columns shape for
  the same reason, so the Request 22 migration of R1 section 5.4 applies to it unchanged.
- **Request 23** (huge-struct-copy warning on `borrow` parameters): unconsumed, and R1B is **new
  client evidence** for it. `BlockPlan` is wider than `GgufTable`, so the spurious lint will fire on
  every neutral accessor too. That strengthens the existing request; it does not create a new one
  and does not change its status. Recording the additional evidence in Request 23 is a documentation
  follow-on for the implementation commit (section 6, item 4).
- **Request 24** (`builder` as a `borrow mut` parameter): unconsumed. Section 2.3.4 shows the
  neutral renderer does not need it; owned-`string`-returning helpers are the shipped form.

**No new genuine Align gap is expected.** Every operation R1B performs is arithmetic over `i64`,
slicing of owned `string` streams, and `array<i64>` indexing. Sizing reads no payload, so no new
I/O, buffer, or codec surface is reached. If implementation discovers otherwise, the finding is
classified under `CLAUDE.md`'s Align-capability-request rules before any workaround is written.

### 2.2 CLI surface

Unchanged in grammar. `main --model-ir MODEL_GGUF [MODEL_IR_JSON]` keeps both forms, the same
arity rules, the same `MAX_PATH_BYTES` guard, the same byte-identical document across the two forms,
the same stdout summary block for the two-operand form, and the same exit mapping
(`0` on `status: "ok"`, `Err(Error.Invalid)` on `status: "error"`).

**What changes is what the single operand may contain.** There is no `--arch` flag, no
architecture-selection option, and no second CLI verb. Dispatch is on the container's own
`general.architecture` field:

| `general.architecture` | Frontend | Result |
| --- | --- | --- |
| `"qwen2"` | `src/frontend_qwen.align` | `R1_MODEL_IR` schema 2, unchanged fields except section 2.4 |
| `"gpt-oss"` | `src/frontend_gpt_oss.align` | `R1_MODEL_IR` schema 2 with `n_expert > 0` |
| absent, non-STRING, non-UTF-8, or anything else | none | `R1_UNSUPPORTED_ARCH`, `error_detail` = the architecture or `""` |

Adding a flag would create a second source of truth for a fact the file already states, and a
mismatch between the flag and the file would need a code of its own. The file wins because the file
is the subject.

The summary block of `docs/specs/r1-qwen-model-ir.md` section 2.4 keeps its exact line set and
order. It is architecture-neutral already (`arch`, `layers`, `embd`, `blocks`, `status`, `detail`),
so it needs no per-architecture variant; `n_expert` is visible in the document, and adding a line
would change a stable stdout contract for no consumer. Section 6, item 3 records the one
consequence: the `blocks:` line now reports 818 rather than 58 on a real MoE model, which is the
number it was always defined to print.

### 2.3 Architecture dispatch and the module split

This is R1B's first design problem and it is decided here rather than during implementation.

#### 2.3.1 The constraint

Align has no traits, no interfaces, and no inheritance. It has one module per file, `pub` for
export, plain function values of a concrete signature, and records. `docs/specs/r1-qwen-model-ir.md`
section 5.5 states the rule R1B must not break: a second architecture is "a separate frontend under
the section 2.7 naming convention, not a widened `if` in this one".

`src/frontend_qwen.align` is 1,248 lines, of which `build_model_ir` is roughly 720 — one function
containing a `loop { ... break }` ordered-validation state machine and a document epilogue. Of that,
steps 3, 8, 10 (resolution and arithmetic), 11, 12 and the whole renderer are architecture-neutral.
Steps 4 through 7, step 9, the role tables, the shape table, and the `model` object are qwen2's.

#### 2.3.2 Option A — widen `frontend_qwen` with an architecture branch

Rejected. It contradicts R1 section 5.5 directly, it makes one module the owner of two
architectures' knowledge, and every subsequent frontend widens it further. The `if` would not stay
in one place: it would appear in the key prefix, the required-key list, the bounds, the shape table,
the role table, the block plan, and the `model` renderer — seven places, in a function that is
already the longest in the repository.

#### 2.3.3 Option B — a standalone `frontend_gpt_oss` duplicating the neutral machinery

Rejected, for the reason R1 invented `table-inspect-parity` for. Two independent implementations of
one exchanged format will disagree about that format, and unlike the two GGUF walks — which were
forced apart by a compiler restriction (`builder` is not a parameter type) — nothing forces these
apart. The schema bump of section 2.4 has to land in both producers simultaneously; duplicating the
renderer means landing it twice and hoping.

The rejection is on drift, not on line count. A duplicate that could not drift would be acceptable;
this one can.

#### 2.3.4 Option C — chosen: a neutral builder driven by an architecture-supplied block plan

Three modules, and the direction of the dependency is what makes it work:

```text
src/gguf.align              container + GgufTable + GGML geometry     (imports core.json, std.fs)
src/model_ir.align          BlockPlan -> Model IR + Block IR + document (imports gguf)
src/frontend_qwen.align     qwen2 hyperparameters -> BlockPlan          (imports gguf, model_ir)
src/frontend_gpt_oss.align  gpt-oss hyperparameters -> BlockPlan        (imports gguf, model_ir)
src/main.align              --model-ir dispatch on general.architecture (imports both frontends)
```

A frontend never receives a callback and the neutral builder never imports a frontend. The frontend
performs its own ordered validation (steps 4 through 7 and 9), renders its own `model` object as an
owned `string`, and builds a **`BlockPlan`**: a description of every block it wants, expressed
entirely in `array<i64>` columns and one concatenated name stream, in exactly the shape
`GgufTable` already proved works at this pin.

```text
pub BlockPlan {
  arch: string,               // the document's `model.arch`
  model_json: string,         // the fully rendered `model` object, section 2.5.2

  // Scalars the CLI summary and the smoke read without parsing the document.
  n_layer: i64,
  n_embd: i64,
  n_expert: i64,

  names: string,              // every expected tensor name, concatenated, no separator

  // Per-block columns; every column has exactly `block_count` entries.
  block_count: i64,
  block_kind: array<i64>,     // 0 WeightBlock 1 AttentionBlock 2 MlpBlock 3 ExpertBlock 4 RouterBlock
  block_layer: array<i64>,    // -1 when the block is not per-layer
  block_expert: array<i64>,   // -1 when the block is not per-expert
  block_member_start: array<i64>,   // [start, end) into the member columns
  block_member_end: array<i64>,

  // Per-member columns; every column has exactly `member_count` entries.
  member_count: i64,
  member_role: array<i64>,          // index into the plan's own role-label stream
  member_role_start: array<i64>,    // roles are text and ride the same stream as names
  member_role_end: array<i64>,
  member_name_start: array<i64>,
  member_name_end: array<i64>,
  member_required: array<i64>,      // 1 required; 0 optional, and an absent optional member is dropped
  member_variant: array<i64>,       // section 2.5.4: 0 when the block has one member set
  member_n_dims: array<i64>,        // the expected dimension count
  member_dim0: array<i64>,          // expected extents; -1 means "any", used by no shipped plan
  member_dim1: array<i64>,
  member_dim2: array<i64>,
  member_dim3: array<i64>,
  member_slice_index: array<i64>,   // -1 for a whole tensor; else the index along the last declared axis
  member_slice_count: array<i64>,   // -1 for a whole tensor; else that axis's extent
}

pub fn build(borrow t: gguf.GgufTable, borrow plan: BlockPlan) -> ModelIr
```

Four properties make this the right shape.

**It is data, not control flow.** A frontend is a table plus the ordered validation of its own
metadata keys. `src/frontend_qwen.align` shrinks to its qwen2 knowledge; `src/frontend_gpt_oss.align`
is the same size for gpt-oss knowledge; neither contains a byte-size computation, a coverage sweep,
or a JSON brace.

**It uses only proved surfaces.** Concatenated text streams addressed by `[start, end)` spans and
parallel `array<i64>` columns are exactly what `GgufTable` is, and R1 section 7 item 1 proved
reading them through a `borrow` record parameter. `array_builder<i64>` is a `borrow mut` parameter
(R1 section 7 item 2), so a frontend's per-layer helper can push into the plan's columns without
returning nineteen values.

**The renderer needs no `builder` parameter.** `model_ir.build` accumulates the document in one
local `builder` and splices owned `string`s returned by helpers — the shipped pattern of
`tensor_json`, `source_json`, and `dims_json`. Request 24 would make this tidier; nothing here waits
for it.

**It has one seam, and the seam is named.** `role` is already R1's stable,
architecture-independent name for a tensor's function within its block. In `BlockPlan` the role is
literally a span of text the frontend supplies, so a new architecture adds a role by adding a
string, not by editing a neutral table.

The cost is honest and stated: `BlockPlan` is a wide record (nineteen columns), so Request 23's
spurious huge-struct-copy lint fires on every neutral accessor that takes it as `borrow`. That is a
diagnostic-noise cost on an already-`PROPOSED`, non-blocking request, not a correctness cost.

#### 2.3.5 What moves, and what does not

| Concern | Before | After |
| --- | --- | --- |
| Container decode, `GgufTable`, GGML geometry | `src/gguf.align` | unchanged; gains the MXFP4 row |
| Steps 3 (container failure), 8 (geometry pass), 10 (resolution, shape, arithmetic), 11 (coverage + claim tiling), 12 (size-sum oracle) | `src/frontend_qwen.align` | `src/model_ir.align` |
| Document rendering, field order, escaping, sentinels | `src/frontend_qwen.align` | `src/model_ir.align` |
| Tensor-name index, duplicate detection, bounded work | `src/frontend_qwen.align` | `src/model_ir.align` |
| Steps 4–7, 9; role/shape/name tables; the `model` object; thresholds that are architecture facts | `src/frontend_qwen.align` | stays, minus the neutral half |
| `--model-ir` arm | `src/main.align` | gains the two-way dispatch |

`pub fn build_model_ir(path: str) -> Result<QwenModelIr, Error>` keeps its name and signature in
`src/frontend_qwen.align`; `src/frontend_gpt_oss.align` exposes the same shape. The record type
becomes the neutral `model_ir.ModelIr` so that `src/main.align`'s dispatch has one result type to
handle. That is a public rename (`QwenModelIr` -> `model_ir.ModelIr`) with one caller in the
repository, recorded in section 2.8 and in section 6, item 1.

### 2.4 `R1_MODEL_IR` schema 2

#### 2.4.1 The granularity decision, and why it needs a schema change

Two candidate contracts were evaluated for `ExpertBlock`.

**Layer granularity.** One `ExpertBlock` per layer, holding the whole stacked
`blk.L.ffn_*_exps.weight` tensors. It fits `schema_version: 1` exactly as
`docs/specs/r1-qwen-model-ir.md` section 2.8 promises: `kind` is a string and `expert` already
exists, so a layer-granularity `ExpertBlock` sets `expert: -1` and adds no field.

**Per-expert granularity.** One `ExpertBlock` per `(layer, expert)` pair, each naming the byte
sub-range of the stacked tensors that belongs to that expert. `expert` finally carries a real value.
It needs a way to say *which bytes*, and `R1_MODEL_IR` schema 1 has no such field.

The decision is **per-expert**, and the argument is that layer granularity satisfies no stated
consumer:

| Named consumer | Source | Unit it requires |
| --- | --- | --- |
| "hot expert" in VRAM, "warm expert" in DRAM, "cold expert" in NVMe | `docs/specs/align-llm.md` section 6 | the individual expert; three residency tiers cannot be assigned to one layer-wide block |
| Cache score from "router score", "recent activation", "frequency", "miss penalty" | `docs/specs/align-llm.md` section 7.4 | the individual expert; a router emits a score per expert |
| "expert cache", "token-to-token reuse" during decode | `docs/specs/align-llm.md` section 7.1 | the individual expert |
| "token-to-token expert reuse", "bias by language / task / repository" | `docs/specs/roadmap.md` section R2 | the individual expert; the measurement's whole purpose is to find out whether *some* experts are hot |
| LRU / LFU / recent-reuse / score-based / top-k prefetch | `docs/specs/roadmap.md` section R3 | the individual expert; a simulator over layer-wide blocks would model a cache with 24 entries and no expert dimension |
| "initially centred on the layer **and the expert** unit" | `docs/specs/align-llm.md` section 5.2 | both; the expert unit is named as initial scope, not future work |

`docs/specs/r1-qwen-model-ir.md` section 5.3 says block granularity should be refined "when a
measurement, not a preference, asks for it". That rule was written about splitting an
`AttentionBlock` into per-projection sub-blocks, for which no consumer is named anywhere. Here the
measurement is R2, R2's unit is the expert, and R2 is the next roadmap item. Shipping layer
granularity would mean R2's first act is to change the exchanged format it was just handed — which
is the "milestone consumes a decision assigned to a later slice" failure the review checklist names,
run backwards.

Layer granularity also loses information that cannot be recovered downstream without re-deriving
GGML's row arithmetic in every consumer: the byte range of expert `e` is
`row_bytes * ne1 * e` into the tensor, where `row_bytes = (ne0 / block_size) * type_bytes`. That is
precisely the off-by-one hazard `docs/specs/r1-qwen-model-ir.md` section 2.5.6 cites as the reason
`contiguous` is computed in the producer rather than by each consumer.

**Therefore the schema changes.** `docs/specs/r1-qwen-model-ir.md` section 2.5 states the rule
plainly: "Any field addition, removal, reordering, or type change requires `schema_version: 2`." A
sub-range field is an addition. The section 2.8 claim that `kind` and `expert` let a MoE frontend
ship without a bump is **true only for a layer-granularity MoE frontend**, and section 6, item 2
records that correction against R1's plan rather than pretending the claim still holds.

The bump is cheap and this is the moment to take it. `R1_MODEL_IR` is an in-flight exchanged
document with no persisted form, no cache identity, and exactly two consumers in the repository
(`scripts/run-model-ir-smoke` and `scripts/run-model-ir-parity`). Deferring the bump to R2 would
cost more, because R2 will have a layout planner reading it.

#### 2.4.2 The delta, in full

Schema 2 is schema 1 plus **two fields on the block tensor record** and **one refined definition**.
Nothing is removed, renamed, reordered, or retyped.

```json
{
  "name": "blk.0.ffn_gate_exps.weight",
  "role": "ffn_gate_exps",
  "type": 39,
  "type_name": "MXFP4",
  "n_dims": 3,
  "dims": [2880, 2880, 32],
  "n_elements": 265420800,
  "block_size": 32,
  "type_bytes": 17,
  "nbytes": 141004800,
  "offset": 12345344,
  "absolute_offset": 12456704,
  "claimed_absolute_offset": 16863104,
  "claimed_nbytes": 4406400
}
```

The example is expert 1 of an assumed 32: `row_bytes = (2880 / 32) * 17 = 1530`,
`plane_bytes = 1530 * 2880 = 4,406,400`, `nbytes = 4,406,400 * 32 = 141,004,800`, and
`claimed_absolute_offset = 12,456,704 + 4,406,400 * 1`. Its extents are ASSUMED (section 2.5); its
arithmetic is not.

| New field | Type | Contract |
| --- | --- | --- |
| `claimed_absolute_offset` | integer | The absolute byte offset of the first byte **this block** claims of this tensor. Equal to `absolute_offset` when the block claims the whole tensor, which is the case for every dense block and for every non-expert member of a MoE block |
| `claimed_nbytes` | integer | The number of bytes this block claims. Equal to `nbytes` for a whole-tensor claim |

Both are appended after `absolute_offset`, so the neutral fields of `BLOCK_TENSOR_ORDER` keep their
positions and only grow. `n_dims`, `dims`, `n_elements`, and `nbytes` continue to describe the
**tensor as the container declares it**, never the slice. A document that reshaped a declared
3-axis tensor into the 2-axis plane a single expert occupies would contradict `--inspect-gguf` about
the same file, and R1's whole discipline is that every value is decoded or derived by a stated
formula from decoded values.

The tensor-relative form of the claim is deliberately not duplicated: it is
`claimed_absolute_offset - source.data_offset`, and `offset` already carries the tensor's own
tensor-relative start.

**The refined definition.** `blocks[].byte_size`, `first_absolute_offset`, `end_absolute_offset`,
and `contiguous` are now computed over the block's **claims** rather than over its tensors' whole
byte ranges:

```text
byte_size             = Σ claimed_nbytes
first_absolute_offset = min claimed_absolute_offset
end_absolute_offset   = max (claimed_absolute_offset + claimed_nbytes)
contiguous            = (end_absolute_offset - first_absolute_offset == byte_size)
```

For every schema-1 producer the claim equals the whole tensor, so all four values are **byte
identical** to what R1 emits today. The refinement is what makes an `ExpertBlock`'s `byte_size` the
size of one expert rather than of all thirty-two, and what makes its `contiguous` mean something.

**Discriminated `model`.** `model` is the one object whose field set is architecture-determined.
`model.arch` is its first field and is the discriminator; each frontend's exact field list and order
is normative in its own plan section (`docs/specs/r1-qwen-model-ir.md` section 2.5.3 for `qwen2`,
section 2.5.2 below for `gpt-oss`). A single union object carrying `null` for every inapplicable
field was rejected: it would make every future architecture a schema bump, and it would report
`n_expert_used: null` for a dense model as if the concept applied.

**Everything else is unchanged**: top-level fields and order, `source`, `quant`, `coverage`, the
block record's own field list and order, `role`, `dims` ordering, the escaping boundary, the
failure-persistence behavior, and the `-1` / `null` sentinel rules of R1 section 7 item 8.

**`qwen2` documents change in exactly two ways**: `schema_version` reads `2`, and every block tensor
record gains two fields whose values equal `absolute_offset` and `nbytes`. The `model` object, the
block set, the byte arithmetic, and the oracle are untouched.

### 2.5 The gpt-oss Model IR and Block IR

> **Every GGUF key name, tensor name, shape, and hyperparameter value in this section is an
> ASSUMPTION** unless its row cites local evidence. The gpt-oss model is not present on this host,
> and no `gguf-py`, `convert_hf_to_gguf.py`, or model file is installed. Section 4.5 makes
> confirming them by real-model inspection the implementation capability's first act, and section
> 2.5.4 designs the one place where the uncertainty is load-bearing so that it fails loudly instead
> of silently.

**Local evidence that is real.** `/opt/homebrew/Cellar/llama.cpp/0.2.0` is the named revision
(`llama-cli --version` prints `version: 0.2.0 (build 10566, commit bb4caa754)`), and its
`lib/libllama.dylib` contains these format strings, read directly out of the shipped binary:

```text
blk.%d.ffn_gate_inp          blk.%d.ffn_gate_exps        blk.%d.ffn_up_exps
blk.%d.ffn_down_exps         blk.%d.attn_sinks
blk\.\d*\.attn_sinks.weight            blk\.\d*\.ffn_down_exps.bias
blk\.\d*\.ffn_gate(_exps)?.bias        blk\.\d*\.ffn_up(_exps)?.bias
blk\.\d*\.ffn_gate_up(_exps)?.weight   blk\.\d*\.attn_output.bias
%s.expert_count   %s.expert_used_count   %s.expert_feed_forward_length
%s.attention.key_length   %s.attention.value_length
%s.attention.sliding_window   %s.attention.sliding_window_pattern
```

and the architecture name `gpt-oss`. The `blk.%d.*` forms are llama.cpp's tensor-name templates and
the `blk\.\d*\.*` forms are its quantization-exclusion regexes, so the *spelling* of every name
below is evidence-backed. What is **not** evidence-backed is which of them gpt-oss actually uses,
their shapes, and their per-model extents.

#### 2.5.1 Hyperparameters (ASSUMED extents from public documentation of `gpt-oss-20b`)

| Field | Source key | Rule | Assumed value |
| --- | --- | --- | --- |
| `arch` | `general.architecture` | Must be exactly `"gpt-oss"` | `gpt-oss` |
| `n_layer` | `gpt-oss.block_count` | Required `UINT32`, `[1, MAX_LAYERS]` | 24 |
| `n_embd` | `gpt-oss.embedding_length` | Required `UINT32`, `[1, MAX_EMBD]` | 2880 |
| `n_head` | `gpt-oss.attention.head_count` | Required `UINT32`, `[1, MAX_HEADS]` | 64 |
| `n_head_kv` | `gpt-oss.attention.head_count_kv` | Required `UINT32`, `[1, n_head]`, `n_head % n_head_kv == 0` | 8 |
| `head_dim` | `gpt-oss.attention.key_length` when present, else `n_embd / n_head` | `[1, MAX_EMBD]`; when present, `gpt-oss.attention.value_length` must be present and equal | 64 |
| `head_dim_source` | derived | `"metadata"` or `"derived"` | `metadata` |
| `n_ff` | `gpt-oss.feed_forward_length` | Required `UINT32`, `[1, MAX_FF]` | 2880 |
| `n_ff_exp` | `gpt-oss.expert_feed_forward_length` when present, else `n_ff` | `[1, MAX_FF]`; `n_ff_exp_source` records which | 2880 |
| `n_vocab` | derived from `token_embd.weight` `dims[1]` | `[1, MAX_VOCAB]`, then cross-checked against `tokenizer.ggml.tokens` length | 201088 |
| `n_expert` | `gpt-oss.expert_count` | **Required** `UINT32`, `[1, MAX_EXPERTS]` | 32 |
| `n_expert_used` | `gpt-oss.expert_used_count` | **Required** `UINT32`, `[1, n_expert]` | 4 |
| `context_length` | `gpt-oss.context_length` | Required `UINT32`, `[1, MAX_CONTEXT]` | 131072 |
| `rms_eps` / `rms_eps_bits` | `gpt-oss.attention.layer_norm_rms_epsilon` | Required `FLOAT32`; same rendering and bits rule as R1 | — |
| `sliding_window` | `gpt-oss.attention.sliding_window` | Optional `UINT32`; `null` when absent. **Reported, never interpreted** | 128 |
| `sliding_window_pattern` | `gpt-oss.attention.sliding_window_pattern` | Optional `UINT32`; `null` when absent. Reported, never interpreted | 2 |
| `rope.*` | the `gpt-oss.rope.*` keys | Same rules as R1 section 2.5.3, with `rope.type` architecture-owned and `type_source: "architecture"` | — |

**`head_dim` is not `n_embd / n_head` for this architecture, and that is the single most important
derivation difference.** `2880 / 64 = 45`, which is not the head dimension; the container declares
`attention.key_length` instead. R1's qwen2 frontend derives `head_dim` from the division because
qwen2 declares no such key and the division is exact there. The gpt-oss frontend **prefers the
declared key** and records `head_dim_source` so a consumer can tell a declared value from a derived
one — the same discipline R1 applies to `rope.dim_count_source` and `rope.type_source`. When the key
is absent, the division is used and must divide exactly; otherwise `R1_KEY_VALUE_IMPLAUSIBLE`.

Two new named thresholds join R1's list in `src/frontend_gpt_oss.align`:

| Constant | Value | Assumed reality | Rationale |
| --- | --- | --- | --- |
| `MAX_EXPERTS` | 1,024 | 32 | An order of magnitude above any shipping MoE expert count |
| `MAX_BLOCKS` | 65,536 | 818 | The block-explosion guard of section 2.6 step 7. `MAX_LAYERS * MAX_EXPERTS` alone admits half a million blocks and a document no consumer can hold |

The `model` object's field order for `arch == "gpt-oss"` is normative and is:

```text
arch, n_layer, n_embd, n_head, n_head_kv, head_dim, head_dim_source, n_ff, n_ff_exp,
n_ff_exp_source, n_vocab, n_expert, n_expert_used, expert_ffn_layout, context_length,
sliding_window, sliding_window_pattern, rms_eps, rms_eps_bits, rope
```

`expert_ffn_layout` is section 2.5.4's variant marker and is provisional; the rest is settled.

with `rope` keeping R1's exact eight-field order.

#### 2.5.2 Block IR emission order

```text
index 0                                         WeightBlock     layer -1   token_embd.weight
for L in 0 .. n_layer-1:
  index base                                    AttentionBlock  layer L
  index base + 1                                RouterBlock     layer L
  index base + 2 + e   (e = 0 .. n_expert-1)    ExpertBlock     layer L    expert e
index 1 + n_layer * (2 + n_expert)              WeightBlock     layer -1   output_norm, output
```

giving `n_layer * (2 + n_expert) + 2` blocks: **818** for the assumed `gpt-oss-20b` shape, against
459 declared tensors (`3 + 24 * 19`) and 4,923 block tensor records
(`1 + 24 * (10 + 3 + 32 * 6) + 2`). Emission order is fixed and is not file order, exactly as in R1.

| Block | Roles and ASSUMED GGUF names |
| --- | --- |
| embedding `WeightBlock` | `token_embd` = `token_embd.weight` |
| `AttentionBlock` (layer L) | `attn_norm` = `blk.L.attn_norm.weight`; `attn_q` / `attn_q_bias` = `blk.L.attn_q.weight` / `.bias`; `attn_k` / `attn_k_bias`; `attn_v` / `attn_v_bias`; `attn_output` / `attn_output_bias` = `blk.L.attn_output.weight` / `.bias`; `attn_sinks` = `blk.L.attn_sinks.weight` |
| `RouterBlock` (layer L) | `ffn_norm` = `blk.L.ffn_norm.weight`; `router` = `blk.L.ffn_gate_inp.weight`; `router_bias` = `blk.L.ffn_gate_inp.bias` (optional) |
| `ExpertBlock` (layer L, expert e) | slice `e` of `ffn_gate_exps` = `blk.L.ffn_gate_exps.weight`, `ffn_gate_exps_bias` = `.bias`, `ffn_up_exps` = `blk.L.ffn_up_exps.weight`, `ffn_up_exps_bias` = `.bias`, `ffn_down_exps` = `blk.L.ffn_down_exps.weight`, `ffn_down_exps_bias` = `.bias` |
| output `WeightBlock` | `output_norm` = `output_norm.weight`; `output` = `output.weight`, or `token_embd.weight` when absent (R1's tied-embedding rule, unchanged) |

**`ffn_norm` belongs to the `RouterBlock`, not to an `ExpertBlock`.** It is applied once per token
before routing, so attaching it to any single expert would be a lie about when it is needed, and
duplicating it into all 32 would break claim tiling. The `RouterBlock` is therefore "everything the
layer needs before it knows which experts to fetch", which is exactly the residency question R2
asks.

**`attn_sinks` goes in the `AttentionBlock`.** It is per-head attention state and is fetched with
the attention weights.

ASSUMED expected shapes, asserted per member and yielding `R1_TENSOR_SHAPE_UNEXPECTED` on mismatch:

```text
token_embd.weight        [n_embd, n_vocab]        output.weight          [n_embd, n_vocab]
output_norm.weight       [n_embd]                 attn_norm.weight       [n_embd]
attn_q.weight            [n_embd, n_head*head_dim]        attn_q.bias    [n_head*head_dim]
attn_k.weight            [n_embd, n_head_kv*head_dim]     attn_k.bias    [n_head_kv*head_dim]
attn_v.weight            [n_embd, n_head_kv*head_dim]     attn_v.bias    [n_head_kv*head_dim]
attn_output.weight       [n_head*head_dim, n_embd]        attn_output.bias  [n_embd]
attn_sinks.weight        [n_head]
ffn_norm.weight          [n_embd]
ffn_gate_inp.weight      [n_embd, n_expert]               ffn_gate_inp.bias [n_expert]
ffn_gate_exps.weight     [n_ff_exp, n_embd, n_expert]     ffn_gate_exps.bias [n_ff_exp, n_expert]
ffn_up_exps.weight       [n_ff_exp, n_embd, n_expert]     ffn_up_exps.bias   [n_ff_exp, n_expert]
ffn_down_exps.weight     [n_embd, n_ff_exp, n_expert]     ffn_down_exps.bias [n_embd, n_expert]
```

The **stacked-tensor rule**: a member the plan slices must declare its expert axis as its **last**
declared axis, with extent exactly `n_expert`. That is `n_dims == 3` for a stacked weight and
`n_dims == 2` for a stacked bias. The rule is checked before any slice arithmetic
(section 2.6 step 8b).

The **router shape rule**: `ffn_gate_inp.weight` must be `[n_embd, n_expert]`. A router whose second
axis disagrees with `n_expert` is the clearest possible signal that the metadata and the tensors
describe different models, and it is caught as an ordinary shape mismatch.

#### 2.5.3 Slice arithmetic

GGML lays a tensor out row-major with the **fastest-varying axis first**, so the last declared axis
is the outermost and each of its indices owns one contiguous byte plane. For a member with declared
dimensions `[d0, d1, d2]` and expert axis `d2 == n_expert`:

```text
row_bytes    = (d0 / block_size) * type_bytes          // the row rule of R1 section 2.5.7
plane_bytes  = row_bytes * d1                          // one expert's bytes
claimed_absolute_offset = absolute_offset + plane_bytes * slice_index
claimed_nbytes          = plane_bytes
```

and for a 2-axis stacked bias `[d0, d1]` with `d1 == n_expert`, `plane_bytes = row_bytes`.

Three consequences are stated so they are not rediscovered:

1. **Exactness is structural, not incidental.** `nbytes = row_bytes * d1 * d2`, so
   `nbytes = plane_bytes * n_expert` exactly and `nbytes % n_expert == 0` holds by construction once
   the row rule and the stacked-tensor rule have both passed. The claim-tiling check of section 2.6
   step 11 is therefore a *defensive* oracle rather than an input-reachable rejection; section 2.6
   records that honestly rather than inventing a fixture for an unreachable branch.
2. **The row rule still governs `d0`.** MXFP4's block size is 32, so a stacked expert tensor whose
   first axis is not a multiple of 32 is `R1_TENSOR_SHAPE_UNALIGNED` and is never sized. `2880 % 32
   == 0`, so the assumed shape is representable.
3. **Every product is guarded.** `plane_bytes * slice_index` and `absolute_offset + plane_bytes *
   slice_index` are formed in R1's non-wrapping style — `plane_bytes > I64_MAX / slice_index` and
   `absolute_offset > I64_MAX - offset_into_tensor` tested before the operation — with `I64_MAX`
   saturation on the end offset, exactly as R1 section 7 item 19 requires.

#### 2.5.4 The one load-bearing assumption: fused versus split expert feed-forward

`libllama.dylib` contains **both** `blk.%d.ffn_gate_exps` / `blk.%d.ffn_up_exps` and the regex
`blk\.\d*\.ffn_gate_up(_exps)?.weight`. llama.cpp supports architectures that ship the expert gate
and up projections as one fused tensor and architectures that ship them separately, and which form
a gpt-oss GGUF uses cannot be determined from the installed artifacts. Guessing wrong makes the
frontend reject every real gpt-oss file with `R1_MISSING_TENSOR`.

The design does not guess. `BlockPlan` carries `member_variant`, and an `ExpertBlock` declares two
member sets:

| Variant | Members | Reported as |
| --- | --- | --- |
| 0 — split | `ffn_gate_exps` + `ffn_gate_exps_bias` + `ffn_up_exps` + `ffn_up_exps_bias` + `ffn_down_exps` + `ffn_down_exps_bias` | `model.expert_ffn_layout: "split"` |
| 1 — fused | `ffn_gate_up_exps` + `ffn_gate_up_exps_bias` + `ffn_down_exps` + `ffn_down_exps_bias`, with the fused weight expected as `[2 * n_ff_exp, n_embd, n_expert]` | `model.expert_ffn_layout: "fused"` |

The neutral builder selects the **first variant all of whose required members are present**, applies
that variant's shape expectations, and reports the selection. If no variant is satisfiable, the
error is `R1_MISSING_TENSOR` naming the first missing required member of variant 0, so the diagnostic
points at the form the plan prefers rather than at whichever variant failed last.

`model.expert_ffn_layout` joins the gpt-oss `model` field order between `n_expert_used` and
`context_length`. It exists because the fact is a property of the file that a layout planner must
know; it is not a workaround, and it is not present in the qwen2 `model` object.

**This mechanism is provisional.** Section 4.5 makes real-model inspection a prerequisite of the
implementation capability. If inspection shows only one form exists for gpt-oss, the other variant
and `model.expert_ffn_layout` are **deleted before merge**, and the deletion is a schema-2 field
removal that happens before schema 2 has ever been published — which is the entire reason this
decision is being made now rather than after the first release.

### 2.6 Validation order and error codes

The order is R1's, extended. The first applicable row still wins, tensors are still examined in file
order, and metadata keys in the fixed order of the section 2.5.1 table. No document and no stdout is
produced before the whole derivation completes.

1. CLI selector and exact arity. *(`src/main.align`, unchanged)*
2. Path lexical validation. *(unchanged)*
3. `gguf.read_table`; a `status: Error` table becomes `R1_GGUF_ERROR`. *(`src/model_ir.align`)*
4. Architecture: present, UTF-8, and one of `"qwen2"` / `"gpt-oss"`. *(`src/main.align` dispatch;
   each frontend re-checks its own value so neither is usable on the wrong file.)*
5. Required metadata presence, then declared type, in the two sub-passes R1 section 7 item 9
   describes. For gpt-oss the required set adds `gpt-oss.expert_count` and
   `gpt-oss.expert_used_count`; the optional set adds `attention.key_length`,
   `attention.value_length`, `expert_feed_forward_length`, `attention.sliding_window`, and
   `attention.sliding_window_pattern`.
6. Hyperparameter plausibility and derivation, including `head_dim` selection and every divisibility
   requirement.
7. **Expert bounds and the block-explosion guard**, replacing R1's blanket MoE rejection for this
   frontend: `n_expert` in `[1, MAX_EXPERTS]`; `n_expert_used` in `[1, n_expert]`; and
   `n_layer * (2 + n_expert) + 2 <= MAX_BLOCKS`, tested in non-wrapping form.
8. Tensor geometry pass, in file order: duplicate name, type geometry, row alignment, element
   product, running byte total. Unchanged from R1, and now reached with 3-axis tensors present.
   8b. **Stacked-tensor rule**, at block resolution: a sliced member declares its expert axis last,
   with extent exactly `n_expert`.
9. `n_vocab` derivation, bound, and `tokenizer.ggml.tokens` cross-check. *(unchanged)*
10. Block assembly in the section 2.5.2 emission order: variant selection, required member present,
    then shape, then slice arithmetic.
11. Coverage: every tensor claimed by at least one block, **and** the claims over each tensor either
    include a whole-tensor claim or exactly partition its byte range.
12. The size-sum oracle. *(unchanged: `data_offset + Σ nbytes == file_size`, summed over the tensor
    table, not over block membership.)*

**`qwen2` keeps R1's step 7 unchanged**: `qwen2.expert_count` present and nonzero is still
`R1_UNSUPPORTED_MOE`. A qwen3-MoE file is not a gpt-oss file and is still rejected rather than
half-described.

New and changed error rows:

| Code | Condition | Detected in | `error_detail` |
| --- | --- | --- | --- |
| `R1_BLOCK_CLAIM_MISMATCH` | **new.** The claims over one tensor leave a gap, overlap without being identical whole-tensor claims, or fall outside `[absolute_offset, absolute_offset + nbytes)` | step 11 | the tensor name |
| `R1_KEY_VALUE_IMPLAUSIBLE` | **extended.** `n_expert` outside `[1, MAX_EXPERTS]`; `n_expert_used` outside `[1, n_expert]`; the block count above `MAX_BLOCKS`; `attention.key_length != attention.value_length`; `n_embd % n_head != 0` when `head_dim` must be derived | steps 6, 7 | the key |
| `R1_TENSOR_SHAPE_UNEXPECTED` | **extended.** A sliced member whose last declared axis is not `n_expert`, or whose declared dimension count is not the one its variant expects; a router whose shape is not `[n_embd, n_expert]` | steps 8b, 10 | the tensor name |
| `R1_MISSING_TENSOR` | **extended.** No `ExpertBlock` member variant is satisfiable | step 10 | the first missing required member of variant 0 |

**Every other gpt-oss defect maps onto an existing R1 row**, and inventing a code for it would add a
distinction no consumer acts on. `R1_UNSUPPORTED_ARCH`, `R1_MISSING_KEY`, `R1_KEY_TYPE_MISMATCH`,
`R1_DUPLICATE_TENSOR`, `R1_UNKNOWN_TENSOR_TYPE`, `R1_TENSOR_SHAPE_UNALIGNED`, `R1_SIZE_OVERFLOW`,
`R1_VOCAB_MISMATCH`, `R1_UNASSIGNED_TENSOR`, `R1_SIZE_SUM_MISMATCH`, and `R1_GGUF_ERROR` are
unchanged in meaning and in detail.

`R1_BLOCK_CLAIM_MISMATCH` is **defensive and not input-reachable** once steps 8 and 8b have passed,
by the exactness argument of section 2.5.3, consequence 1. It is retained for the reason R1 section
7 item 18 retains step 12's overflow branch: the guard costs one comparison, the arithmetic it
protects is new, and a silent tiling bug would produce a Block IR that passes every other check
while describing bytes that do not exist. Section 3 closes the cell by argument plus the positive
`expert-tiling` assertion, and does **not** invent a fixture for an unreachable branch.

### 2.7 Ownership, allocation, and owner modules

| Module | Owns | Imports |
| --- | --- | --- |
| `src/gguf.align` | container decode, `GgufTable`, GGML geometry including the new MXFP4 row, `json_string` | `core.json`, `std.fs` |
| `src/model_ir.align` | `BlockPlan`, `ModelIr`, the geometry pass, the tensor-name index, block resolution and arithmetic, claim tiling, coverage, the size-sum oracle, the whole document renderer, every neutral error code | `gguf` |
| `src/frontend_qwen.align` | qwen2 metadata keys, bounds, derivations, role/shape/name tables, the qwen2 `model` object, the qwen2 `BlockPlan` | `gguf`, `model_ir` |
| `src/frontend_gpt_oss.align` | the same for gpt-oss, plus expert bounds, the block-explosion guard, and the variant declaration | `gguf`, `model_ir` |
| `src/main.align` | `--model-ir` arity, path guard, architecture dispatch, destination, summary block, exit mapping | both frontends |

No frontend imports another. `src/model_ir.align` imports no frontend, which is what keeps the
neutral builder testable and keeps the dependency acyclic.

| Value | Owner | Allocation | Release |
| --- | --- | --- | --- |
| `GgufTable` | one local in the frontend's `build_model_ir` | unchanged from R1: three owned `string`s and 25 `array<i64>` columns, built once | scope `Drop` |
| `BlockPlan` | built by the frontend, **moved** into `model_ir.build` as a `borrow` argument's owner local | two owned `string`s (`names`, the role stream) plus two owned `string`s (`arch`, `model_json`) and nineteen `array<i64>` columns, each frozen once from an `array_builder<i64>` | scope `Drop` after `build` returns |
| tensor-name index | one local in `model_ir.build` | one `array<i64>`, built and sorted once. Unchanged from R1 section 2.7 | scope `Drop` |
| claim list | one local in `model_ir.build` | one `array<i64>` of packed `(tensor index, claim ordinal)` entries, built once and sorted once | scope `Drop` |
| block and tensor JSON | one `builder` in `model_ir.build` | accumulated once, in emission order | moved out by `to_string()` |
| final document | `builder` moved out by `to_string()` | one owned `string` | **moved** into `ModelIr.document`, then to the caller |

The document is moved, not cloned, following `docs/specs/c8-speed-first.md` section 2.8, as
`GgufInspection` and `QwenModelIr` already do. `model_json` is likewise moved into `BlockPlan` and
spliced into the document without a second copy.

**Work stays bounded.** `model_ir.build` is `O(n log n)` in the tensor count and `O(m log m)` in the
claim count, where `m = Σ block member count`. The claim-tiling check sorts the claim list once by
`(tensor index, claimed offset)` and walks it with one cursor, so it costs one pass, not a scan per
tensor. R1 section 7 item 22's qualification is inherited verbatim: `first_duplicate` remains
quadratic in one equal-hash run's width for adversarially crafted names, never in `tensor_count` of
distinct hashes.

**The claim count is the one new size to bound.** For the assumed gpt-oss-20b shape it is 4,923;
`MAX_BLOCKS` (65,536) times the widest member set (10) bounds it at 655,360, which is well inside
`i64` and inside the packing the claim list uses. That bound is why step 7 exists.

### 2.8 Ledger dimensions

| Dimension | Contract | Owner | Acceptance |
| --- | --- | --- | --- |
| Exact command/API | Section 2.2 (`--model-ir`, two forms, unchanged grammar, architecture dispatch on the container's own field); section 2.3.4 (`model_ir.BlockPlan`, `model_ir.ModelIr`, `model_ir.build`); `pub fn build_model_ir(path: str) -> Result<model_ir.ModelIr, Error>` in each frontend; `gguf.ggml_block_size` / `gguf.ggml_type_size` gain one row and keep their signatures. No aliases, no flags | `src/main.align`, `src/model_ir.align`, both frontends, `src/gguf.align` | `model-ir-smoke` CLI and dispatch cases |
| Inputs and defaults | One model path; optional destination path. `head_dim` defaults to `n_embd / n_head` when `attention.key_length` is absent; `n_ff_exp` defaults to `n_ff`; `sliding_window` and `sliding_window_pattern` default to `null`; `rope.type` is architecture-owned; the `ExpertBlock` member variant defaults to split and is selected by presence. No ambient options, no environment input | `src/frontend_gpt_oss.align` | `gptoss-defaults`, `gptoss-keylength-absent`, `gptoss-variant-*` |
| Results and errors | `Ok` + `status: "ok"`; `Ok` + `status: "error"` for every model defect; `Err` only for argument or OS failure. Section 2.6's table is complete and ordered | `src/model_ir.align`, both frontends, `src/main.align` | one fixture per reachable row |
| Multi-invalid precedence | Section 2.6 is strictly ordered; within a step, file order for tensors and section 2.5.1 order for keys; the first applicable row wins | frontends + `src/model_ir.align` | `gptoss-precedence-*` |
| Ownership and lifetime | Section 2.7. `BlockPlan` and the document are moved into their sole owners; no accessor returns a view derived from a `borrow` parameter | `src/model_ir.align` | `document-move`, ownership review |
| Allocation | Section 2.7's table; one `GgufTable`, one `BlockPlan`, one name index, one claim list, one document per invocation | `src/model_ir.align`, frontends | `bytes_read` bound, descriptor-budget run, `repeat-model-ir` |
| Bounded work | `O(n log n)` in tensor count and `O(m log m)` in claim count; `MAX_BLOCKS` bounds `m`. R1 section 7 item 22's adversarial-hash qualification is inherited | `src/model_ir.align` | `bounded-work`, extended with a wide-MoE fixture |
| Owner module | Section 2.7's table. One architecture per frontend; one renderer for the format; one container reader | this document | `make check` (`check-per-unit`), import graph review |
| Persisted/cache identity | `N/A`. R1B writes one caller-named output document and reads nothing it wrote. No cache, no digest-addressed artifact, no compiler-cache policy change. `BlockPlan` and `ModelIr` are in-process values with no persisted form, so there is no nominal-versus-structural fingerprint question | `N/A` with this reason | no cache behavior is claimed or tested |
| Schema version | **`schema_version: 2`**, emitted by both frontends, for the two additive block-tensor fields of section 2.4.2. The refined `byte_size` / `first_absolute_offset` / `end_absolute_offset` / `contiguous` definitions are byte-identical for every schema-1 producer. `model` is discriminated by `model.arch`, whose per-architecture field list and order are normative. Any further addition, removal, reorder, or type change requires version 3 | `src/model_ir.align` | golden document bytes; per-architecture field-order assertions |
| Validation order | Section 2.6, deterministic and side-effect ordered; no output before derivation completes | `src/model_ir.align`, frontends | ordered malformed corpus, untouched-destination assertion |
| Prerequisites | The pinned toolchain at `4b515f8d`. Every consumed surface is verified present (section 2.1). Requests 21–24 remain `PROPOSED`, non-blocking, and unconsumed. **Two capability prerequisites**: the MXFP4 geometry oracle of section 2.8.2, recorded in the pull request; and the real-model tensor-name inspection of section 4.5, which settles the section 2.5.4 variant question before merge | `src/gguf.align`, `src/frontend_gpt_oss.align` | `make check`, `make build`, the recorded oracle run |
| Acceptance evidence | `model-ir-smoke` for correctness and the error corpus; the size-sum oracle and the claim-tiling oracle for completeness; `model-ir-parity` for the roadmap gate, with the section 4.4 `N/A` | section 4 | sections 4.2, 4.3, 4.4 |
| Metrics | Primary: correctness — the size-sum oracle and the claim-tiling oracle hold on every positive fixture, and parity passes when a real model is supplied. Secondary: coverage (`assigned_tensor_count == tensor_count`, `unassigned_tensors` empty) and `bytes_read` (unchanged R1 bound). **No performance claim**; section 4.6 | section 4.6 | oracle assertions, `bytes_read` bound |
| Text/wire boundary | Canonical UTF-8 JSON, declaration order, through `gguf.json_string`. Unchanged from R1: a non-UTF-8 tensor name never reaches the document and surfaces as `R1_UNASSIGNED_TENSOR` with an escaped, bounded detail | `src/model_ir.align` | `wire-escapes` over both corpora |
| Runtime-inspection fields | Every field is decoded from the file or derived by a stated formula from decoded values, except `rope.type` (architecture-owned, `type_source: "architecture"`) and the source markers `head_dim_source`, `n_ff_exp_source`, `expert_ffn_layout`, which report *which rule was applied*. No reflection, no source read, no environment read | frontends | producer-provenance review, `env-perturbation` |
| Platform scope | Platform-independent derivation. The container codec assumes a little-endian host, which Align already assumes. No target-local boundary changes, so this capability's own content selects no platform profile | frontends | no target-local claim |
| Milestone ordering | R1B consumes no R2 decision: no layout, no ordering, no residency tier, no prefetch policy. It emits `contiguous` and per-expert byte ranges as observations. Conversely it does not defer to R2 a decision R2 cannot take without a format change — section 2.4.1 | this document | section 5 |
| Normative examples | The JSON block of section 2.4.2 and the shape tables of section 2.5.2 are declarations, not positional calls. Their assumed extents are not asserted by any test; the fixture corpus uses its own small extents and the parity qualification owns the real ones | this document | section 4.5's inspection prerequisite |

#### 2.8.1 Deleted promise: "a MoE frontend needs no schema bump"

`docs/specs/r1-qwen-model-ir.md` sections 2.5.6, 2.8, and 5.1 each state that `blocks[].kind` and
`blocks[].expert` were shaped so that adding `ExpertBlock` and `RouterBlock` needs no
`schema_version: 2`. Section 2.4.1 shows the claim holds only for a layer-granularity MoE frontend,
which no consumer wants. The seam those fields cut is still real and still used — `kind` takes two
new string values and `expert` finally takes a non-`-1` value, with no type change to either — but
the sub-range contract needs two fields those two do not provide. Section 6, item 2 records the
correction against R1's plan.

#### 2.8.2 MXFP4 geometry row: provenance and acceptance

`docs/specs/r1-qwen-model-ir.md` section 5.5 gates a new geometry row on two things: "a named GGML
revision as the transcription source **and** the size-sum oracle passing against a real model that
uses the type". R1B satisfies the first outright and substitutes a stronger, locally executable
instrument for the second, because the real model is not present.

**The row.**

```text
id  name    block_size  type_bytes
39  MXFP4   32          17
```

**Provenance, with exact citations.**

1. **The type id is transcribed from the named revision's header.**
   `/opt/homebrew/include/ggml.h:429` reads `GGML_TYPE_MXFP4   = 39, // MXFP4 (1 block)`.
   `/opt/homebrew/include/ggml.h:474` corroborates with `GGML_FTYPE_MOSTLY_MXFP4   = 25`.
2. **The header is the one llama.cpp build 10566 uses.** `/opt/homebrew/include/ggml.h` is a symlink
   to `/opt/homebrew/Cellar/ggml/0.21.0/include/ggml.h`, and
   `otool -L /opt/homebrew/Cellar/llama.cpp/0.2.0/lib/libllama.dylib` reports
   `/opt/homebrew/opt/ggml/lib/libggml-base.0.dylib (current version 0.21.0)`. The reference tool
   `scripts/run-model-ir-parity` compares against — `version: 0.2.0 (build 10566, commit bb4caa754)`
   — therefore sizes MXFP4 tensors with exactly this table.
3. **The geometry is not derivable from the installed headers, and is read from the shipped
   implementation instead.** `ggml-common.h`, which defines `QK_MXFP4` and `struct block_mxfp4`, is
   **not** installed (`/opt/homebrew/include/ggml-common.h` does not exist), and no `gguf-py` type
   table ships with this llama.cpp formula. The values are obtained from the library's own public
   API, which is the implementation rather than a transcription of it:

   ```c
   /* linked with: cc -I/opt/homebrew/include -L/opt/homebrew/lib -lggml-base */
   printf("blck=%lld type_size=%zu\n",
          (long long) ggml_blck_size(GGML_TYPE_MXFP4),
          ggml_type_size(GGML_TYPE_MXFP4));
   ```

   Observed on this host: `blck=32 type_size=17`. The same program reproduces every one of R1's
   twenty existing rows exactly — `f32 1/4`, `q4_0 32/18`, `q4_K 256/144`, `q6_K 256/210`,
   `bf16 1/2`, and the rest — which is what makes it a differential check on the whole table rather
   than a single lookup.

**Acceptance.** The oracle program is an **out-of-tree probe recorded in the pull request as
evidence, not committed**, following the precedent `docs/specs/r1-qwen-model-ir.md` section 2.3.5
sets for the borrow-indexing compile probe. It is not made a `Makefile` target: the geometry table
is static data with no drift source, adding a target would force the fresh-image installed preflight
profile (`scripts/verification_scope.py:23`) on a capability that otherwise does not touch the
`Makefile`, and the probe is re-run when — and only when — a row is added.

**What is still owed, and why the row ships anyway.** Section 5.5's second half — the size-sum
oracle passing against a real MXFP4 model — is **not discharged by this capability**. The row ships
regardless, for three reasons:

1. **Deferring it defeats the capability.** In a gpt-oss MXFP4 file the MXFP4 tensors are exactly
   the expert tensors. Without the row, `--model-ir` on the target model returns
   `R1_UNKNOWN_TENSOR_TYPE` and produces no Block IR at all.
2. **A wrong row cannot be silent.** The size-sum oracle is computed in-program on every input. If
   the geometry were wrong, the first real-model run would fail with `R1_SIZE_SUM_MISMATCH` and an
   exact byte discrepancy. The failure mode is loud, immediate, and self-diagnosing.
3. **The substitute instrument is stronger than the deferred one for this question.** The real-model
   oracle would confirm the row indirectly, through a 4.7-billion-byte sum. The library oracle reads
   the answer out of the implementation that defines it.

The row is therefore recorded in `src/gguf.align` with its provenance comment and the status
**"library-oracle verified; real-model verification pending"**, and section 4.4 keeps the real-model
run as the named opt-in qualification. Section 6, item 5 records the amendment this reasoning owes
R1 section 5.5: the gate becomes a disjunction — a named GGML revision **and** either the real-model
oracle or a recorded library oracle over the shipped implementation of that revision.

**`NVFP4` (id 40, `blck=64`, `type_size=36` from the same probe) is deliberately not added.** It has
no consumer, no fixture need, and no model. Section 5.3.

## 3. Closure matrix

Every applicable cell names its implementation owner and the exact regression that closes it. `N/A`
carries a concrete reason; `DEFERRED` is an intentional decision recorded in section 5. Regression
names are cases inside `scripts/run-model-ir-smoke` unless another runner is named. Cells that R1
already closed and R1B does not change are marked **inherited** and are re-proved by re-running the
existing qwen corpus, not by new cases.

### 3.1 `src/gguf.align` — the MXFP4 geometry row

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction | The row is two literals in the two existing data functions; no other function changes | `ggml_block_size`, `ggml_type_size` | `type-geometry`, extended: id 39 returns `32` / `17` |
| Success — sizing | An MXFP4 tensor's `nbytes` matches the row formula for 1-, 2-, and 3-axis shapes | unchanged `tensor_nbytes` | `mxfp4-geometry`: generator-computed `nbytes` on `[256]`, `[256, 128]`, and `[256, 128, 4]` |
| Success — naming | `ggml_type_name(39)` already returns `MXFP4` and is unchanged | unchanged R0 table | `mxfp4-geometry` asserts `type_name` |
| Failure — neighbours | Ids 38 and 40 still have no geometry and still produce `R1_UNKNOWN_TENSOR_TYPE` | absent rows | `unknown-type` fixture, extended with 40 |
| Malformed — row rule | An MXFP4 tensor whose first axis is not a multiple of 32 is `R1_TENSOR_SHAPE_UNALIGNED` and is never sized | unchanged step 8 | `mxfp4-row-unaligned`: `[48, 128]` |
| Provenance | The row's source is a named revision and a recorded library oracle | comment in `src/gguf.align` | the section 2.8.2 probe, recorded in the pull request |
| Everything else | **inherited** — container decode, `GgufTable`, accessors, spans, float columns, lookup, early exit, cleanup, bounds precondition | unchanged | the whole R0 + R1 corpus re-run |

### 3.2 `src/model_ir.align` — the neutral builder

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — plan intake | Every `BlockPlan` column has exactly `block_count` or `member_count` entries; spans satisfy `0 <= start <= end <= stream.len()` | `build` prologue guard | `plan-column-lengths`, asserted through the emitted document for every fixture in both corpora |
| Construction — result | `ModelIr` is built with every field explicitly initialized, including the section 2.4.2 sentinels | `build` epilogue | `ir-error-sentinels` over both architectures |
| Success — geometry pass | `n_elements`, `block_size`, `type_bytes`, and `nbytes` are computed for every tensor in file order, including 3-axis tensors | `size_tensors` | `tensor-dims-3d`: a 3-axis stacked tensor's `dims` and `n_elements` in the document |
| Success — variant selection | The first variant whose required members are all present is chosen; the choice is reported | `resolve_block` | `gptoss-variant-split`, `gptoss-variant-fused`, `gptoss-variant-none` |
| Success — whole-tensor claim | For every non-sliced member, `claimed_absolute_offset == absolute_offset` and `claimed_nbytes == nbytes` | `resolve_member` | `claim-identity`: asserted on every tensor record of the whole qwen corpus |
| Success — slice arithmetic | `claimed_absolute_offset` and `claimed_nbytes` follow section 2.5.3 for 3-axis weights and 2-axis biases | `slice_claim` | `expert-slice-bytes`: generator-computed claims for every `(layer, expert)` pair |
| Success — block arithmetic | `byte_size`, `first_absolute_offset`, `end_absolute_offset`, and `contiguous` are computed over claims | `close_block` | `expert-block-bytes`; `qwen-block-bytes-unchanged` diffs the qwen documents against schema-1 values for these four fields |
| Success — claim tiling | The claims over each tensor include a whole-tensor claim or exactly partition its range | `check_claims` | `expert-tiling`: every stacked tensor's `n_expert` claims tile it exactly, asserted positively on every positive gpt-oss fixture |
| Success — coverage | Every tensor is assigned; `computed_end == file_size` | `check_coverage` | `size-sum-oracle` on every positive fixture in both corpora |
| Success — document | Field order, escaping, and sentinels match section 2.4 for both architectures | `render_*` | `field-order-qwen`, `field-order-gptoss` |
| Failure — every error code | Each reachable row of section 2.6 is produced by at least one fixture with the correct detail | ordered guards | `error-corpus`, extended with the gpt-oss rows |
| Failure — precedence | A file with two defects reports the earlier row | ordered guards | `gptoss-precedence-key-shape`, `gptoss-precedence-expert-vocab` |
| Failure — overflow class | Every guard of section 2.5.3 is tested before the arithmetic it protects | `slice_claim`, `close_block` | `overflow-corpus`, extended with a stacked tensor whose plane arithmetic would wrap |
| Failure — claim mismatch | `R1_BLOCK_CLAIM_MISMATCH` fires on a gap, an overlap, or an out-of-range claim | `check_claims` | **closed by argument** (section 2.6): unreachable once steps 8 and 8b pass. The positive `expert-tiling` assertion is the evidence the arithmetic is right |
| Malformed — non-UTF-8 name | Unchanged from R1: matches no member, surfaces as `R1_UNASSIGNED_TENSOR`, document stays valid JSON | `check_coverage` | `invalid-utf8-name`, re-run |
| Early exit | On any failure, derivation stops and `blocks` holds exactly the blocks completed before it | guard returns | `gptoss-ir-partial`: a failure injected at layer 1 of 2 asserts the exact block count |
| Bounded work | `O(n log n)` in tensors and `O(m log m)` in claims; `MAX_BLOCKS` bounds `m` | `name_index`, `claim_list` | `bounded-work`, extended with a 64-expert 8-layer fixture inside the existing budget |
| Branch joins | `Ok` / `Error` status construction and the document return have exactly one owner | `build` return | `document-move` for both architectures |
| Loop joins | The block loop, the member loop, the expert loop, the geometry loop, and the claim sweep each terminate on count, on failure, and on a zero count | loop guards | `gptoss-zero-layer`, `gptoss-zero-expert` (both `R1_KEY_VALUE_IMPLAUSIBLE`) |
| Move-out | The document is moved into `ModelIr.document`; `BlockPlan` is moved into `build`'s owner local | epilogue | `document-move`; ownership review against `docs/specs/c8-speed-first.md` section 2.8 |
| Borrow discipline | No neutral helper returns a view derived from a `borrow` parameter; every text result is owned | signatures | `make check` |
| `KVBlock` / `DequantBlock` | `N/A`: neither is backed by a file tensor; both are runtime constructs | `N/A` with R1 section 2.5.8's reason | — |
| Generic monomorphization | `N/A`: no generic type or function is declared | `N/A` with this reason | — |
| Shared/process-global state | `N/A`: no process-global state; the module is pure over its two inputs | `N/A` with this reason | `repeat-model-ir`, `env-perturbation` |
| Concurrency | `N/A`: read-only, no lock; no atomicity claimed for a file mutated during the walk | `N/A` with this reason | documented unsupported caller case |
| Per-unit vs whole-program | The module compiles identically imported and whole-program | module boundary | `make check` (`check-per-unit`), `make build` |

### 3.3 `src/frontend_qwen.align` — reduced to qwen2 knowledge

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Behavior preservation | Every qwen2 document is byte-identical to R1's except `schema_version` and the two new tensor fields | the extraction | `qwen-schema2-diff`: the whole qwen corpus, diffed field by field against the schema-1 expectations, with exactly those differences allowed |
| Ownership | `src/frontend_qwen.align` contains no byte-size computation, no coverage sweep, and no JSON brace outside its `model` object | the extraction | code review; grep for `write_int` outside the `model` renderer |
| Steps 4–7, 9 | Architecture check, key passes, bounds, MoE rejection, `n_vocab` derivation all keep R1's order and codes | unchanged bodies | the entire R1 negative corpus, unchanged |
| Public rename | `QwenModelIr` becomes `model_ir.ModelIr`; the only caller is `src/main.align` | `build_model_ir` signature | `make check`; section 6, item 1 |
| Everything else | **inherited** from `docs/specs/r1-qwen-model-ir.md` section 3.2 | unchanged | the R1 corpus re-run |

### 3.4 `src/frontend_gpt_oss.align` — gpt-oss knowledge

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — plan | The plan's columns are each built once and frozen once; `block_count` equals `n_layer * (2 + n_expert) + 2` | `build_plan` epilogue | `gptoss-block-count` |
| Success — hyperparameters | Every section 2.5.1 field is read or derived by its stated rule | `read_hyperparameters` | `gptoss-model-fields` against generator-declared golden values |
| Success — `head_dim` | The declared `attention.key_length` wins; the division is the fallback; `head_dim_source` reports which | `derive_shape` | `gptoss-headdim-metadata`, `gptoss-headdim-derived` |
| Success — optional keys | Absent `expert_feed_forward_length`, `sliding_window`, `sliding_window_pattern` yield the default or `null`; none is an error | optional lookups | `gptoss-optional-absent`, `gptoss-optional-present` |
| Success — block plan | `AttentionBlock`, `RouterBlock`, and `n_expert` `ExpertBlock`s per layer, in the section 2.5.2 order with the right kind, layer, expert, and roles | `build_plan` | `gptoss-block-order`, `gptoss-block-roles` |
| Success — slice declaration | Every stacked member declares `slice_index` and `slice_count`; no non-stacked member does | `build_plan` | `expert-slice-bytes` |
| Failure — expert bounds | `n_expert` and `n_expert_used` outside their bounds are `R1_KEY_VALUE_IMPLAUSIBLE` with the key as detail | step 7 | `gptoss-expert-zero`, `gptoss-expert-used-high`, `gptoss-expert-huge` |
| Failure — block explosion | `n_layer * (2 + n_expert) + 2 > MAX_BLOCKS` is `R1_KEY_VALUE_IMPLAUSIBLE`, tested non-wrappingly | step 7 | `gptoss-block-explosion` |
| Failure — stacked shape | A sliced member whose last axis is not `n_expert`, or whose dimension count is wrong, is `R1_TENSOR_SHAPE_UNEXPECTED` | step 8b | `gptoss-stacked-axis`, `gptoss-stacked-ndims` |
| Failure — router shape | `ffn_gate_inp.weight` not `[n_embd, n_expert]` is `R1_TENSOR_SHAPE_UNEXPECTED` | step 10 | `gptoss-router-shape` |
| Failure — wrong arch | A `qwen2` file reaching this frontend is `R1_UNSUPPORTED_ARCH` | step 4 re-check | `gptoss-wrong-arch` |
| Malformed | Unchanged from R1: invalid UTF-8 keys and names, duplicates, unknown types, truncation | `src/model_ir.align` | the R0 corpus re-run through `--model-ir` |
| Early exit | A failure before plan construction produces no blocks | guard returns | `gptoss-ir-partial` |
| Generic monomorphization / shared state / concurrency | `N/A` with the section 3.2 reasons | `N/A` | — |
| Per-unit vs whole-program | Compiles identically imported and whole-program | module boundary | `make check`, `make build` |

### 3.5 `src/main.align` — dispatch

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — dispatch | The architecture is read once, from `gguf.read_table`'s own field, before either frontend is entered; the table is read exactly once per invocation | `model_ir_demo` | `dispatch-single-read`: `bytes_read` unchanged from R1 on the qwen corpus |
| Success — both architectures | A qwen2 file reaches the qwen frontend and a gpt-oss file the gpt-oss frontend | `model_ir_demo` | `dispatch-qwen`, `dispatch-gptoss` |
| Failure — unknown architecture | Anything else is `R1_UNSUPPORTED_ARCH` with the architecture as detail, before any frontend runs | `model_ir_demo` | `dispatch-unknown`, reusing R1's `qwen2-wrong-arch` and the whole R0 positive corpus |
| Byte identity across forms | Both CLI forms emit identical document bytes for both architectures | `model_ir_demo` | `form-parity` over both corpora |
| Summary block | The section 2.4 lines keep their order and escaping; `blocks:` reports the assembled count | unchanged | `summary-order`, `summary-control-bytes` |
| Failure mapping | `status: "error"` becomes `Err(Error.Invalid)` after the document is emitted | epilogue | `error-corpus` |
| Everything else | **inherited** from `docs/specs/r1-qwen-model-ir.md` section 3.3: arity, path validation, OS failure, early exit, unknown selector, environment isolation, help text | unchanged | the R1 CLI cases re-run |

### 3.6 `Makefile` and `scripts/` — build and verification graph

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Target definition | **No new target.** `model-ir-smoke` and `model-ir-parity` keep their names, dependencies, and aggregate membership; the new modules are reached through `check-per-unit $(ENTRY)`, which follows imports and enumerates no source | `Makefile` unchanged | `python3 scripts/check-gate-topology` reports no change |
| Aggregate membership | `model-ir-smoke` stays in `HOSTED_CHECK_TARGETS`: still no model, no network, no reference tool, still seconds | `Makefile` unchanged | `make gate-topology-check` |
| Qualification exclusion | `model-ir-parity` stays outside every aggregate | `Makefile` unchanged | `make gate-topology-check` |
| Preflight profile selection | The `Makefile` is **not** modified, so `FRESH_IMAGE_PATTERNS` (`scripts/verification_scope.py:23`) does not match and the classifier selects ordinary executable preflight. `python3 scripts/pre-pr --plan` must confirm this before the run; if any later change touches the `Makefile`, the fresh-image installed profile is expected and must not be replaced by a Docker skip or an ambient `DOCKER_HOST` endpoint | `scripts/pre-pr` | `--plan` output recorded in the pull request |
| Fixture generation | `scripts/gguf_fixture.py` gains the gpt-oss corpus and still writes only into a caller-supplied temporary tree | `scripts/gguf_fixture.py` | the smoke's repository leak sweep |
| Fixture independence | The generator derives no value from `src/`; the MXFP4 row and every expected claim are computed in Python | `scripts/gguf_fixture.py` | code review; the import list is unchanged |
| Generator compatibility | Existing R0 fixtures are byte-unchanged; existing R1 fixtures change only where schema 2 requires | `scripts/gguf_fixture.py` | `make gguf-smoke` before and after; `qwen-schema2-diff` |
| Geometry-table completeness | Adding id 39 to `GGML_GEOMETRY` requires a slot in `GEOMETRY_TYPES`, or the generator's own `covered == set(GGML_GEOMETRY)` assertion fails | `scripts/gguf_fixture.py` | `qwen2-geometry`, extended; the assertion is the regression |
| Cleanup | Every fixture path is removed by the `trap` on `EXIT`; the runner's last assertion is that the temp root is still present | `scripts/run-model-ir-smoke` | unchanged R1 shape |
| Parity arch dispatch | The parity runner selects its comparison row set from the `model.arch` of the document under test, so one runner and one environment variable serve both models | `scripts/run-model-ir-parity` | a synthetic-log unit inside the runner for each row set |
| Parity skip | An unset or absent `ALIGN_LLM_GGUF_MODEL` or `ALIGN_LLM_LLAMA_CLI` prints one exact `N/A` line and exits 0; a parse failure fails closed | `scripts/run-model-ir-parity` | unchanged R1 cases plus the gpt-oss row set |
| Documentation | `docs/specs/roadmap.md` section R1 and `HANDOFF.md` name this document and the schema bump; `docs/specs/r1-qwen-model-ir.md` receives the section 6 amendments; `docs/align-requests.md` Request 23 receives the additional client evidence | integration commit | out of scope for this design-only file; listed in section 6 |

## 4. Fixture and qualification design

### 4.1 `scripts/gguf_fixture.py` — the gpt-oss corpus

The generator is extended, not replaced, and keeps its independence property: it emits container
bytes from its own `struct`-packing tables and computes every expected value — including every
per-expert claim — in Python, importing nothing from `src/`. A new `GptOssModel` class mirrors
`QwenModel`'s structure exactly (`entries` in file order, a contiguous aligned data layout, an
oracle assertion before writing, and `positive()` returning the full expected document).

**Two generator-side changes are prerequisites and are named because forgetting either is a silent
failure:**

1. `GGML_GEOMETRY` gains `39: (32, 17)`. The `qwen2-geometry` fixture asserts
   `covered == set(GGML_GEOMETRY)`, so a slot in `GEOMETRY_TYPES` must accept id 39 in the same
   commit. `attn_k` (`[256, 128]`) works: `(256 / 32) * 17 = 136` bytes per row, `136 * 128 = 17,408`
   bytes, a multiple of the 32-byte container alignment.
2. Every `QwenModel` expectation gains `claimed_absolute_offset == absolute_offset` and
   `claimed_nbytes == nbytes` on every tensor record, and `schema_version` becomes 2.

**The positive fixture `gptoss-full.gguf`** is a complete, valid v3 container well under 1 MiB, with
a real data section of exactly the declared size that the frontend must never decode. Its extents
are chosen so that the size-sum oracle is satisfiable — the constraint that
`docs/specs/r1-qwen-model-ir.md` section 7 item 5 records as the one that broke R1's first fixture:

```text
n_layer 2   n_embd 256   n_head 8   n_head_kv 2   key_length 64   value_length 64
n_ff 256    n_ff_exp 32  n_expert 8  n_expert_used 2
n_vocab 32  context_length 512   sliding_window 64   sliding_window_pattern 2
```

`head_dim` is `64` from the declared key while `n_embd / n_head` is `32`, so the two rules **must**
disagree in the base fixture: a frontend that silently fell back to the division would produce a
`[256, 256]` `attn_q.weight` expectation against the fixture's `[256, 512]` and fail. Attention
widths are `n_head * head_dim = 512` and `n_head_kv * head_dim = 128`.

Block count is `2 * (2 + 8) + 2 = 22`; tensor count is `3 + 2 * (10 + 3 + 6) = 41`; claim count is
`1 + 2 * (10 + 3 + 8 * 6) + 2 = 125`.

**Every byte size must be a multiple of the 32-byte container alignment, and for a sliced tensor so
must every plane**, or a contiguous data section cannot also be alignment-correct and the size-sum
oracle is unsatisfiable — the failure `docs/specs/r1-qwen-model-ir.md` section 7 item 5 records. The
extents above are chosen for it:

| Tensor | Type | Shape | `row_bytes` | `plane_bytes` | `nbytes` |
| --- | --- | --- | --- | --- | --- |
| `ffn_gate_exps.weight`, `ffn_up_exps.weight` | MXFP4 | `[32, 256, 8]` | `(32/32) * 17 = 17` | `17 * 256 = 4,352` | 34,816 |
| `ffn_down_exps.weight` | MXFP4 | `[256, 32, 8]` | `(256/32) * 17 = 136` | `136 * 32 = 4,352` | 34,816 |
| `ffn_gate_exps.bias`, `ffn_up_exps.bias` | F32 | `[32, 8]` | 128 | 128 | 1,024 |
| `ffn_down_exps.bias` | F32 | `[256, 8]` | 1,024 | 1,024 | 8,192 |
| `ffn_gate_inp.weight` / `.bias` | F32 | `[256, 8]` / `[8]` | — | — | 8,192 / 32 |
| `attn_sinks.weight` | F32 | `[8]` | — | — | 32 |

A stacked MXFP4 **bias** would have `plane_bytes = row_bytes = 136`, which is not a multiple of 32,
so expert biases are `F32` in the fixture. `n_head = 8` is also what makes `attn_sinks.weight`
(`[n_head]`, F32) exactly 32 bytes rather than 16.

Quantization types are mixed on purpose: the three stacked expert weights are `MXFP4`; the router,
the norms, `attn_sinks`, and every bias are `F32`; `attn_q` / `attn_k` / `token_embd` are `Q4_K`;
`attn_v` / `output` are `Q6_K`; `attn_output` is `Q8_0` — **five** ascending `quant.type_counts`
rows (ids 0, 8, 12, 14, 39). Total data-section size is 787,136 bytes, keeping the file under 1 MiB
with its header.

**`n_ff` is declared, required, and used by no tensor shape**, because a pure-MoE layer has no dense
feed-forward tensor. It is therefore the one gpt-oss hyperparameter the step-10 shape contract
cannot falsify — the same position `n_vocab` occupies in R1 — and its `[1, MAX_FF]` bound is what
keeps an implausible value a rejection rather than an unusable Model IR.

Further positive variants:

| Fixture | What it pins |
| --- | --- |
| `gptoss-headdim-derived` | no `attention.key_length` and no `attention.value_length`; `head_dim = n_embd / n_head = 32`, `head_dim_source: "derived"`, and every attention shape narrows accordingly |
| `gptoss-ffexp-absent` | no `expert_feed_forward_length`; `n_ff_exp` falls back to `n_ff`, `n_ff_exp_source: "derived"` |
| `gptoss-variant-fused` | `ffn_gate_up_exps.weight` `[64, 256, 8]` (`2 * n_ff_exp` on the first axis) instead of the split pair; `expert_ffn_layout: "fused"` |
| `gptoss-permuted` | the data section grouped by role across layers, so at least one `ExpertBlock` is non-contiguous while the oracle still holds |
| `gptoss-tied` | no `output.weight`; the tied rule and the whole-tensor-claim-twice case, with the oracle and the claim-tiling rule both holding |
| `gptoss-wide` | 8 layers, 64 experts — 530 blocks — inside the `bounded-work` budget |

**The negative corpus** adds one file per new or extended row of section 2.6:

| Fixture | Defect | Expected |
| --- | --- | --- |
| `gptoss-expert-zero` | `gpt-oss.expert_count = 0` | `R1_KEY_VALUE_IMPLAUSIBLE`, detail `gpt-oss.expert_count` |
| `gptoss-expert-huge` | `gpt-oss.expert_count = 4096` | `R1_KEY_VALUE_IMPLAUSIBLE` |
| `gptoss-expert-missing` | no `gpt-oss.expert_count` | `R1_MISSING_KEY` |
| `gptoss-expert-type` | `gpt-oss.expert_count` as `STRING` | `R1_KEY_TYPE_MISMATCH` |
| `gptoss-expert-used-zero` | `expert_used_count = 0` | `R1_KEY_VALUE_IMPLAUSIBLE` |
| `gptoss-expert-used-high` | `expert_used_count = n_expert + 1` | `R1_KEY_VALUE_IMPLAUSIBLE` |
| `gptoss-block-explosion` | `n_layer = 512`, `n_expert = 1024` | `R1_KEY_VALUE_IMPLAUSIBLE`, detail `gpt-oss.expert_count` |
| `gptoss-keylength-mismatch` | `key_length = 64`, `value_length = 32` | `R1_KEY_VALUE_IMPLAUSIBLE`, detail `gpt-oss.attention.value_length` |
| `gptoss-stacked-axis` | `ffn_gate_exps.weight` `[32, 256, 4]` against `n_expert = 8` | `R1_TENSOR_SHAPE_UNEXPECTED` |
| `gptoss-stacked-ndims` | `ffn_gate_exps.weight` declared 2-axis as `[32, 256]` | `R1_TENSOR_SHAPE_UNEXPECTED` |
| `gptoss-router-shape` | `ffn_gate_inp.weight` `[256, 4]` against `n_expert = 8` | `R1_TENSOR_SHAPE_UNEXPECTED` |
| `gptoss-variant-none` | neither the split pair nor the fused tensor present | `R1_MISSING_TENSOR`, detail `blk.0.ffn_gate_exps.weight` |
| `gptoss-mxfp4-row-unaligned` | an MXFP4 tensor with `dims[0] = 48` | `R1_TENSOR_SHAPE_UNALIGNED` |
| `gptoss-unknown-type` | one tensor with `ggml_type` 40 (`NVFP4`) | `R1_UNKNOWN_TENSOR_TYPE`, detail `40` |
| `gptoss-wrong-arch` | `general.architecture = "qwen2"` in a gpt-oss-shaped file | derives as qwen2 and fails on the qwen2 key set: `R1_MISSING_KEY`, detail `qwen2.block_count` |
| `gptoss-extra-expert` | an extra `blk.0.ffn_gate_exps.weight`-shaped tensor named `blk.9.*` | `R1_UNASSIGNED_TENSOR` |
| `gptoss-size-sum` | 64 trailing bytes past the data section | `R1_SIZE_SUM_MISMATCH` |
| `gptoss-precedence-key-shape` | a mistyped key and a wrong stacked shape | the key row |
| `gptoss-precedence-expert-vocab` | an out-of-bounds `expert_used_count` and a zero vocabulary | the expert row |

Plus one deliberate **positive**: `qwen2-moe.gguf` (R1's existing `qwen2.expert_count = 4` fixture)
still yields `R1_UNSUPPORTED_MOE`, because a MoE qwen file is not a gpt-oss file. That case is
re-run unchanged and is the regression that keeps the two frontends from bleeding into each other.

### 4.2 Owner — `scripts/run-model-ir-smoke`, `make model-ir-smoke`

**One runner, extended.** The gpt-oss corpus is a new `model_ir_gptoss_cases` list in the manifest
so that `run-gguf-smoke` keeps driving exactly the R0 cases, and `run-model-ir-smoke` drives all
three lists. A second `make` target was rejected: the consumer surface is the same CLI, the fixtures
share a generator, and splitting would fragment the aggregate for no failure-domain reason
(`CLAUDE.md`: split only for an independently usable consumer boundary or a distinct failure
domain).

Beyond the closure cells of section 3, the runner:

- asserts `schema_version == 2` on every document in every corpus;
- asserts `BLOCK_TENSOR_ORDER` with the two appended fields, and asserts **two** `MODEL_ORDER`
  lists — one per architecture, selected by `document["model"]["arch"]`;
- recomputes every `claimed_absolute_offset` / `claimed_nbytes` from the generator's own layout and
  compares, rather than trusting the document's internal consistency;
- performs the **claim-tiling assertion in Python**: for each tensor, the block claims are collected,
  sorted, and required either to contain one whole-tensor claim or to tile `[absolute_offset,
  absolute_offset + nbytes)` exactly;
- re-runs the entire R0 and R1 corpora, diffing every qwen document against its schema-1
  expectations with exactly the two allowed differences (`qwen-schema2-diff`);
- keeps the existing repository leak sweep, temp-root assertion, descriptor budget,
  `env-perturbation`, `repeat-model-ir`, and both CLI forms.

### 4.3 The two in-program oracles

**The size-sum oracle** is unchanged and remains
`data_offset + Σ_{t in tensor table} nbytes(t) == file_size`. It sums over the **tensor table**, not
over block membership, so per-expert blocks change nothing about it and a shared or sliced tensor is
still counted exactly once. That independence is precisely why it stays strong under MoE: no term of
it is derived from the block plan.

**The claim-tiling oracle** is new and closes the gap the size-sum oracle cannot see. Coverage in R1
asks only "was every tensor claimed by at least one block". With per-expert slicing, a tensor can be
claimed by 32 blocks while the claims leave a gap or overlap — the size sum would still hold, every
tensor would still be "assigned", and the Block IR would describe bytes that are not there. The rule
is:

```text
for every tensor t claimed by at least one block:
    either some claim is exactly [absolute_offset(t), absolute_offset(t) + nbytes(t))
    or the distinct claims, sorted by start, tile that range with no gap and no overlap
```

Both branches are needed: the first admits the tied-embedding case, where two blocks claim the same
whole tensor; the second is the expert case. A violation is `R1_BLOCK_CLAIM_MISMATCH`.

Section 2.6 records that the violation branch is unreachable once the row rule and the
stacked-tensor rule have passed, because `nbytes = plane_bytes * n_expert` holds structurally. The
oracle is therefore retained as a defensive guard on new arithmetic, and its **positive** side —
that the claims do tile — is asserted on every positive fixture by `expert-tiling` in Align and
again, independently, in Python by the runner.

### 4.4 Focused qualification — `scripts/run-model-ir-parity`, and its explicit `N/A`

The runner keeps its shape: opt-in, never in an aggregate, never in CI, both inputs required and
explicitly skippable with no default, a hard failure on a nonzero reference exit, a fail-closed
parser, and the `-st` / `</dev/null` / `timeout` / `ulimit -f` wrappers R1 section 7 items 6 and 21
established.

**One runner, arch-dispatched.** The runner reads `model.arch` out of the document it just produced
and selects the comparison row set. `ALIGN_LLM_GGUF_MODEL` therefore serves both models, and there
is no second environment variable to forget.

Added `print_info` rows for `arch == "gpt-oss"`, on top of R1's shared rows. Every key below was
confirmed present as a format string in the named build's `libllama.dylib`:

| Model IR field | `print_info` key | Comparison |
| --- | --- | --- |
| `model.n_expert` | `n_expert` | integer equality |
| `model.n_expert_used` | `n_expert_used` | integer equality |
| `model.n_ff_exp` | `n_ff_exp` | integer equality |
| `model.sliding_window` | `n_swa` | integer equality when non-`null`; skipped with a recorded note when `null` |
| `model.head_dim` | `n_embd_head_k` **and** `n_embd_head_v` | integer equality against both |

plus the loader's type census, which now must include an `mxfp4` row matching
`quant.type_counts`.

**One parser risk is recorded rather than discovered.** In this build `n_head` and `n_head_kv` print
with `%s`, not `%u` (`%s: n_head                = %s`), so an architecture with per-layer head counts
may print a list rather than a scalar. R1's rows passed on qwen2 because it prints a plain number.
If gpt-oss prints a list, the runner must fail closed with `parity: UNPARSED n_head` rather than
coerce — the existing contract already requires exactly that, and this note is so the failure is
recognized rather than debugged.

**The `N/A`, stated concretely.** `gpt-oss-20b-mxfp4.gguf` is **12.1 GB and is not present on this
host, and this capability does not download it.** The pull request records:

```text
make model-ir-parity (gpt-oss): N/A — no gpt-oss GGUF on this host; ALIGN_LLM_GGUF_MODEL unset.
make model-ir-parity (qwen2):   PASS / N/A — unchanged R1 qualification.
```

**What the user must decide**, named explicitly because the capability cannot decide it:

1. **Whether to download the 12.1 GB model at all.** Without it, the gpt-oss half of the roadmap R1
   gate rests on the synthetic corpus and the two in-program oracles, and the MXFP4 row rests on the
   library oracle of section 2.8.2. That is a defensible position and it is the one this document
   ships with.
2. **Which model, if so.** `gpt-oss-20b` (12.1 GB, 24 layers, 32 experts) is the smaller target;
   `gpt-oss-120b` is roughly 60 GB. The 20b file is sufficient for every row above.
3. **Where it lives and whether it is retained.** The runner never writes to the model and asserts
   its size and mtime are unchanged, but 12.1 GB of local storage is the user's to allocate.

Until (1) is answered yes, the parity qualification for gpt-oss is `N/A` with the reason above, and
it never counts as a pass.

### 4.5 The inspection prerequisite

**Before any implementation commit**, a real gpt-oss GGUF must be inspected once — with
`./main --inspect-gguf`, which reads only the header and tensor table — to settle five questions
this document had to assume:

1. Split (`ffn_gate_exps` + `ffn_up_exps`) versus fused (`ffn_gate_up_exps`). Section 2.5.4's
   variant mechanism exists for this and the losing variant is **deleted before merge**.
2. Which biases exist: `attn_q/k/v.bias`, `attn_output.bias`, `ffn_gate_inp.bias`, and the three
   `*_exps.bias` tensors.
3. `attn_sinks.weight`'s exact shape.
4. Whether the expert axis is genuinely the last declared axis of each stacked tensor.
5. Whether `attention.key_length` is declared and whether `output.weight` is tied.

Each answer replaces an ASSUMED row in section 2.5 and is recorded in section 7 as an
implementation correction, exactly as R1 recorded its own. If the inspection cannot be performed
because the model is not downloaded, the capability's honest terminal state is that the gpt-oss
frontend is validated against the synthetic corpus only — and section 2.5's assumption banner, not a
passing test, is what a reader must rely on.

### 4.6 Metrics

**Primary — correctness.** Three pass/fail measurements: the size-sum oracle and the claim-tiling
oracle hold on every positive fixture in both corpora; and the parity comparison passes when a real
model is supplied (`N/A` today, section 4.4). None is a speed metric.

**Secondary — coverage.** `assigned_tensor_count == tensor_count` with `unassigned_tensors` empty:
41 of 41 over 22 blocks and 125 claims on `gptoss-full`, and an assumed 459 of 459 over 818 blocks
and 4,923 claims on the real model.

**Secondary — `bytes_read`.** Inherited from R0 and R1 unchanged and re-asserted, because dispatch
adds a code path that could start reading more: `bytes_read < data_offset + WINDOW_BYTES`, with the
`dispatch-single-read` case asserting the qwen values are numerically unchanged from R1.

**R1B makes no performance claim.** The document grows from 58 blocks to 818 on the real model and
the derivation does more work; no baseline is established, no threshold is asserted, and the
`bounded-work` budget remains a complexity guard rather than a performance target. Under `CLAUDE.md`
a speed claim would require a reproducible benchmark and a named baseline, and R1B has neither.

## 5. Deferred surfaces

### 5.1 Layout, residency, and prefetch — R2 and R3

Per-expert `ExpertBlock`s with exact byte ranges are precisely the input a residency planner and a
cache simulator need, which is why section 2.4.1 refuses to defer the granularity decision. R1B
still defines **no** `.alignpack` format, no reordering policy, no residency tier, no eviction rule,
and no prefetch plan. It observes the current layout — including that a real MoE file's experts are
almost certainly interleaved rather than grouped, which `contiguous` will report — and takes no
action on it.

### 5.2 Sub-expert granularity

`docs/specs/align-llm.md` section 5.2 names sub-blocks and neuron clusters as future work. R1B ships
layer-and-expert granularity, which is the section's stated initial scope. Splitting an
`ExpertBlock` further, or splitting an `AttentionBlock` into per-projection sub-blocks, is now a
**schema-compatible** change, because `claimed_absolute_offset` / `claimed_nbytes` already express
an arbitrary sub-range and `role` is already the seam. Both should be made when a measurement asks
for them, not before.

### 5.3 Other GGML type ids

`NVFP4` (id 40, `blck=64`, `type_size=36` from the same library oracle), and every `IQ*` / `TQ*`
type, remain absent and remain `R1_UNKNOWN_TENSOR_TYPE`. Adding one is a two-column data change plus
a `type-geometry` fixture, gated on the amended rule of section 6 item 5. Deferred rather than
guessed, and deliberately not batched into this capability: MXFP4 is added because gpt-oss cannot be
described without it, and no other id has a consumer.

### 5.4 The MoE gating parameters

`expert_gating_func`, `expert_weights_scale`, `expert_weights_norm`, `expert_shared_count`,
`expert_group_count`, `swiglu_clamp_exp`, and the rest of the family are neither read nor reported.
Reporting a raw enum this repository cannot validate would repeat the `general.file_type` mistake
`docs/specs/r1-qwen-model-ir.md` section 2.5.4 refuses to make. When R2 needs one to interpret a
router trace, it becomes a field with a stated rule and a schema bump.

### 5.5 Other MoE architectures

`qwen3moe`, `deepseek2`, `mixtral`, and their relatives share the stacked-expert tensor convention
and differ in shared experts, expert groups, latent attention, and gating. Each is a separate
frontend under section 2.7's naming convention with its own plan section — not a widened `if` in
`src/frontend_gpt_oss.align`. `BlockPlan` is the surface that makes each of them a table rather than
a rewrite, and adding one should require no change to `src/model_ir.align`. That claim is untested
until the second MoE frontend exists, and is recorded as a design intent rather than a guarantee.

### 5.6 Inherited deferrals

Tokenizer and vocabulary (Request 22, unconsumed); `general.file_type` naming; non-contiguous and
padded containers; big-endian GGUF; multi-shard models; the mmap arena alternative; and Request 21's
read-only-open limitation. All inherited from `docs/specs/r1-qwen-model-ir.md` sections 5.2, 5.4,
and 5.5 and `docs/specs/r0-gguf-inspection.md` sections 5.3 and 5.4, unchanged. R1B introduces no
new evidence for or against any of them.

## 6. Amendments this capability owes `docs/specs/r1-qwen-model-ir.md`

Recorded here rather than applied, because this is a design-only file. Each is a documentation
change the implementation commit must make together with the code.

1. **Section 2.7's result type.** `QwenModelIr` becomes the neutral `model_ir.ModelIr`, and
   `build_model_ir` returns it. The field list is unchanged except that `n_expert` may now be
   positive and two scalar fields (`n_expert_used`, `block_count`) carry MoE values.
2. **Sections 2.5.6, 2.8, and 5.1's "no schema bump" claim.** True only for a layer-granularity MoE
   frontend. Section 2.4.1 above records the argument and the decision; those three sentences must
   be corrected to say that `kind` and `expert` avoid a *type* change, not a version bump.
3. **Section 2.4's summary block.** The `blocks:` line's value is unchanged in definition and
   changes by three orders of magnitude in practice on a MoE model. No format change; a note.
4. **`docs/align-requests.md` Request 23.** Add `BlockPlan` as a second align-llm client of the
   spurious huge-struct-copy lint. Evidence only; the status stays `PROPOSED` and non-blocking.
5. **Section 5.5's geometry-row gate.** The conjunction "a named GGML revision **and** the size-sum
   oracle passing against a real model that uses the type" becomes: a named GGML revision, **and**
   either the size-sum oracle against a real model **or** a recorded library oracle
   (`ggml_blck_size` / `ggml_type_size` linked against that revision's shipped implementation) that
   reproduces every existing row. Section 2.8.2 records why the substitute is stronger for this
   question and what remains owed.
6. **Section 5.1's "what R1 does not do".** The gpt-oss frontend is no longer deferred; the pointer
   becomes this document.

## 7. Implementation corrections to this plan

Empty. This section is reserved for the corrections implementation forces on the promises above,
recorded in `docs/specs/r1-qwen-model-ir.md` section 7's format: the section amended, the
correction, the evidence that forced it, and the owner test that now holds it. Every ASSUMED row of
section 2.5 that real-model inspection changes lands here.
