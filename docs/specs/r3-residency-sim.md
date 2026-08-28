# R3-RESIDENCY-SIM: the expert residency replay simulator and the `R3_RESIDENCY_SIM` document

Status: plan of record for the Track B R3 capability named by `docs/specs/roadmap.md` section R3
("R3: Cache Simulator", `align-sim`). It is authoritative for the R3 public contract: the
`main --simulate-residency` CLI arm, the `R3_RESIDENCY_SIM` document at `schema_version: 1`, the new
`src/residency_sim.align` owner module, the demand-stream derivation from `R2_ACTIVATION_TRACE`, the
policy set, the budget sweep, and the verdict rule that answers the roadmap gate numerically.

`docs/specs/roadmap.md` remains authoritative for delivery order and for the R3 gate itself.
`docs/specs/align-llm.md` remains authoritative for the architecture this simulation serves —
section 6's VRAM / DRAM / NVMe tiers, section 7.1's prefill/decode split, section 7.4's score-based
cache, and section 7.5's impact-driven prefetch. `docs/specs/r2a-expert-trace.md` is authoritative
for the input document; R3 reads `R2_ACTIVATION_TRACE` and parses no transcript.
`docs/specs/r1c-olmoe-moe-ir.md` is authoritative for the `ExpertBlock` whose `byte_size` is the
only cost model R3 has; R3 emits no Block IR and reads no GGUF byte.

This document triggers the `CLAUDE.md` proportional design gate on three counts: it adds a public
CLI verb (`--simulate-residency`), it introduces a new versioned exchanged format
(`R3_RESIDENCY_SIM` 1), and it introduces a coordinated invariant across three modules
(`src/residency_sim.align`, `src/main.align`, and the new fixture, oracle, and qualification graph)
plus a `Makefile` change whose preflight consequence is recorded in section 3.3.

The capability is **designed, not implemented**. Section 5 records what it deliberately does not do,
and section 4.5 records the probe run that grounds every expectation in this plan against the real
40-prompt corpus rather than against an assumption.

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

R2 answered *whether* conditional locality exists. R3 answers the only question that follows from a
yes: **given a byte budget on real hardware, which residency policy moves the fewest bytes across
the tier boundary, and by how much.** The unit of placement is the per-`(layer, expert)`
`ExpertBlock`, because R1C measured that unit and R4 packs it.

R3 is an offline replay simulator, not a cache. It consumes documents that already exist — a set of
`R2_ACTIVATION_TRACE` documents and one `R1_MODEL_IR` — derives one deterministic demand stream from
them, and replays that stream against a fixed policy set at a swept set of budgets. It links no
runtime, runs no model, and moves no byte of weight.

Three properties are load-bearing and each is argued below rather than assumed:

- **The demand stream is a derivation, not a transcription.** The trace's own `selections[]` order
  is prefill graph order (layer-major). The regime a residency cache serves is decode
  (`docs/specs/align-llm.md` section 7.1), which is token-major. Section 2.2 defines both orders
  exactly, and section 4.5 measures that the choice changes LRU's hit rate by up to 330 per mille —
  which is why the document reports both and the verdict names one.
- **Bytes, not hits, are the metric.** Experts are not the same size on the real model
  (4,079,616 B against 3,538,944 B, `docs/specs/r1c-olmoe-moe-ir.md` section 2.5.5), and a prefetch
  policy fetches bytes without a demand miss. A hit-rate comparison cannot charge a prefetch for its
  traffic; a byte comparison can. Section 2.8.
- **Every rate carries its denominator and its omissions.** The instrument prints six of eight
  router slots on this model, so the stream is a 750-per-mille subsample of the true demand and
  every rate is conditional on that. Section 2.2.4 makes this a first-class document field rather
  than a footnote.

### 1.2 In scope

1. A new CLI arm `main --simulate-residency TRACE_LIST MODEL_IR.json BUDGET_BYTES [OUT.json]`, in
   the two-form shape `--inspect-gguf`, `--model-ir`, and `--expert-trace` already use
   (section 2.3).
2. A new module `src/residency_sim.align` owning the trace-list reader, the two document decoders,
   the cross-document agreement checks, the demand-stream builder, the packed-key counter tables,
   every policy, the budget sweep, the verdict rule, and the whole document renderer.
3. The demand-stream contract of section 2.2: what is replayed, in what order, what is skipped, and
   how many documents pool into one stream with what cache lifetime.
4. A policy set of ten rows (section 2.4): `null`, `compulsory`, `belady`, `lru`, `lfu`,
   `recent_reuse` at three windows, and `topk_prefetch` at two prefetch degrees. `lru` is the
   declared baseline.
5. The `R3_RESIDENCY_SIM` document at `schema_version: 1`: input identity, stream accounting,
   the per-order per-budget per-policy result matrix, the per-layer breakdown, the jackknife
   stability result, and the verdict (section 2.5).
6. A synthetic corpus built from `scripts/eval_callback_fixture.py`'s existing MoE generator and
   `scripts/gguf_fixture.py`'s existing olmoe builder, plus an independent Python policy oracle
   `scripts/residency_oracle.py` (section 4.1).
7. The owner `scripts/run-residency-sim-smoke` and `make residency-sim-smoke`, and the opt-in
   `scripts/run-residency-sim` and `make residency-sim-qualification` (sections 4.2 and 4.3).
   The script is named `run-residency-sim`, not `run-residency-sim-qualification`; section 6
   item 22 records the rename.

### 1.3 Non-goals

- **No inference, no model, no GGUF read, no transcript parse.** R3's inputs are JSON documents. It
  does not invoke `llama-eval-callback`, does not open a `.gguf`, and does not re-derive anything
  R2A or R1C already derived. A wrong `byte_size` in the Model IR is R1C's bug, not R3's to detect.
- **No cache implementation.** R3 simulates policies; it installs none. The runtime that will hold
  a real expert cache is R5 and later, and nothing in `src/residency_sim.align` is on any inference
  path.
- **No transfer-cost model, no time claim.** R3 counts bytes and events. It does not convert bytes
  to seconds, because that needs the measured NVMe, PCIe, and unified-memory bandwidths R4.5 and R5
  own. Every number in the document is a count; the word "faster" does not appear in it.
  Section 5.3.
- **No score-based policy and no impact-driven prefetch.** Both are named by section R3 and both are
  deferred with reasons in section 5.1: `R2_ACTIVATION_TRACE` carries expert *identities* and no
  router *scores*, and impact requires the transfer-cost model the previous item defers.
- **No CPU-fallback policy.** Deferred in section 5.1 for the same reason: choosing between a
  transfer and a CPU computation is `docs/specs/align-llm.md` section 7.3's explicit
  "判断は実測microbenchmarkに基づく", and that microbenchmark does not exist yet.
- **No decode-phase claim.** Every trace this host can produce is prefill-only
  (`docs/specs/r2a-expert-trace.md` section 2.2, finding 7). R3 *replays* the prefill demand in
  token-major order because that is the shape decode will have, and it says so in the document and
  in every summary line. It does not claim to have measured decode. Section 5.2.
- **No language, task, or repository stratification.** The corpus is 40 unlabelled prompts. Adding a
  label axis is a corpus capability, not a simulator capability. Section 5.4.
- **No policy tuning loop.** The three `recent_reuse` windows and two `topk_prefetch` degrees are
  fixed constants chosen once from the section 4.5 probe and recorded in section 2.4. R3 does not
  search a parameter space, because a policy selected by searching the same 40 prompts it is
  evaluated on is not a measurement.

### 1.4 Gate statement

The roadmap gate for R3 is *対象ハードウェア条件で、baselineより有効なpolicyを特定できること* — that
under a target hardware condition, a policy more effective than the baseline can be identified.

R3 discharges it, and the discharge is a numeric verdict rather than an assertion:

1. **The hardware condition is the `BUDGET_BYTES` operand.** It is the byte budget of the residency
   tier being asked about, supplied by the caller. The document reports the swept context around it
   so that a reader can see whether the answer is a plateau or a cliff.
2. **The baseline is `lru`, declared, not inferred.** `docs/specs/align-llm.md` section 7.4 opens
   with "LRUだけに依存しない", so LRU is the thing R3 must beat for the section to be justified.
3. **The verdict rule is section 2.8**, fixed before the qualification — in the design commit that
   also carries the section 4.5 probe — on bytes fetched, with a 50-per-mille effect floor and a
   leave-one-document-out stability requirement. It was not fixed before *any* measurement: the
   probe came first and the constants were chosen with it in view, which is why section 2.8 states
   what the floor is and is not.
4. **`NO_POLICY_BEATS_BASELINE` and `NO_HEADROOM` are answers, not failures.** The gate asks whether
   a better policy *can be identified*. "At this budget LRU is already within 5 per cent of the
   offline optimum" is a numerically identified answer that would correctly stop investment, and the
   section 4.5 probe returns one of the two non-winning verdicts at three of its eight swept
   budgets.

The gate is discharged by `make residency-sim-qualification` on the real corpus, which records the
verdict. `make residency-sim-smoke` discharges correctness against an independent oracle and needs
no model, no network, and no instrument.

## 2. Public-contract ledger

### 2.1 Verified Align surface at pin `4b515f8d`

Every row was established in this repository at this pin. The three rows marked **probed for R3**
were verified during this design, in the scratch worktree, against the real 1.19 MB `R1_MODEL_IR`
and a real `R2_ACTIVATION_TRACE`; they are the rows the plan would otherwise have had to assume.

| Surface | Status at the pin | Consequence for R3 |
| --- | --- | --- |
| `json.decode(view) -> Result<T, Error>` into a record with `array<Record>` fields | **Shipped.** `src/prompt_artifacts.align:2251`; `src/c6_json_recursive_graph_adoption.align:9` | Both input documents are decoded whole; R3 needs no parser of its own |
| `json.decode` **ignores object members the target record does not declare** | **Shipped — probed for R3.** A four-field `BlockRow {kind, layer, expert, byte_size}` decoded the real `R1_MODEL_IR` and skipped `index`, `tensor_count`, `first_absolute_offset`, `end_absolute_offset`, `contiguous`, and the nested `tensors` array | This is the decision that makes the design simple. R3 declares only the fields it uses, so it never materializes the 3,219 nested tensor records and never depends on R1C's tensor schema |
| `json.decode` on a 1.19 MB document with 1,058 array elements | **Shipped — probed for R3.** Decoded and summed to `3,900,702,720` in 0.5 s wall including compile | No bounded streaming JSON reader is needed, so R2A's `Cursor`/window line reader is **not** reused and section 2.4's argument is not repeated |
| `fs.read_file(path) -> Result<string, Error>` | **Shipped.** `src/eval.align:82` | Whole-document read, bounded by `MAX_DOCUMENT_BYTES` (section 2.7) |
| `array<i64>` field indexed through a `borrow` record parameter; `array_builder<i64>` as `borrow mut` | **Shipped.** `docs/specs/r1-qwen-model-ir.md` section 7 items 1 and 2 | Every counter table and every stream column is an `array<i64>`; section 2.7 |
| `sort()` over `array<i64>` | **Shipped.** `docs/specs/r1-qwen-model-ir.md` section 2.7 | The token-major reordering is one sort of packed `i64` order-plus-payload words; section 2.2.2 |
| `loop { if … { break } }`, `match`, integer `as`, `Result`, `Option` | **Shipped**, unchanged | `while` does not exist in Align; every replay is a `loop` with an explicit break |
| `builder` local + `to_string()` move-out; owned-`string`-returning render helpers | **Shipped.** `src/model_ir.align` | The renderer is `model_ir`'s shape and passes no `builder` across a boundary |
| Hand-rolled decimal integer parse | **Necessary, not preferred.** `docs/align-requests.md` Request 26 records the absent `str`-to-number surface; `docs/specs/r2a-expert-trace.md` section 2.1 records the same gap for the same reason | `BUDGET_BYTES` is a CLI operand string. R3 is Request 26's **second** client and reuses R2A's bounded private parser shape rather than a `json.decode` detour |
| `str.split(...)` | **NOT available** as a `str` method at this pin | The trace list is scanned for `\n` explicitly, exactly as R2A's header parser composes `find` and `[a..b]` |

**No `PROPOSED` request is consumed.** Three existing requests gain a client and none changes status:

- **Request 23** (huge-struct-copy warning on `borrow` parameters): R3 is a **fourth** client. Its
  `Simulation` record is another wide state-plus-columns record read through `borrow` accessors, so
  the same spurious warning fires. Additional evidence, no status change.
- **Request 26** (`str`-to-number): second client, as above.
- **Request 21** (`fs.open_ro`): **not** a client. R3 reads through `fs.read_file`, which does not
  demand `O_RDWR`, so the read-only-input precondition R0 and R2A both carry does not apply here.
  Recording the *absence* of the constraint matters: it means a qualification may consume documents
  from a read-only artifact directory, which R2A's arm cannot.

**Three requests are foreseen as risks and each has a stated fallback**, because the plan must not
be invalidated by one of them biting during implementation:

- **Request 34** (`Result` ok payloads beyond scalars) and **Request 43** (cross-module `borrow mut`
  record out-parameters). A replay naturally wants to return a wide result record from a fallible
  function. The plan does not depend on either: `src/residency_sim.align` is **one** module, so no
  record crosses a module boundary, and every fallible helper returns `Result<i64, Error>` with its
  outputs written into `borrow mut` columns owned by the caller. If both requests later ship, the
  code simplifies; nothing here waits on them.
- **Request 40** (`array_builder<T>` as a struct field type). The stream columns are therefore built
  as function locals and frozen once into `array<i64>` fields, which is exactly what
  `src/model_ir.align` already does for `BlockPlan`. Non-blocking by construction.

Genuine gaps discovered during implementation are recorded in `docs/align-requests.md` by the
orchestrator; this document edits no register.

### 2.2 The demand stream

This is the contract that every number in the document depends on, so it is specified before the CLI
that produces it.

#### 2.2.1 What is admitted

A `(layer, expert)` **demand** is derived from one row of one trace's `selections[]`. A trace
document contributes demands only when all of the following hold; each failure is an error code in
section 2.6, not a silent skip:

| Condition | Failure |
| --- | --- |
| `kind == "R2_ACTIVATION_TRACE"` and `schema_version == 1` | `R3_TRACE_SCHEMA` |
| `status == "ok"` | `R3_TRACE_STATUS` |
| `moe.present == true` | `R3_TRACE_NOT_MOE` |
| `moe.n_expert` and `moe.n_expert_used` equal every other admitted trace's | `R3_TRACE_DISAGREEMENT` |
| `moe.n_expert` equals the Model IR's `model.n_expert`, and `moe.n_expert_used` equals `model.n_expert_used` | `R3_SHAPE_MISMATCH` |
| every selection's `layer` is in `[0, model.n_layer)` and `expert` in `[0, model.n_expert)` | `R3_EXPERT_OUT_OF_RANGE` |
| the Model IR declares an `ExpertBlock` for every demanded `(layer, expert)` | `R3_MISSING_EXPERT_BLOCK` |

Within an admitted trace, a **graph is excluded when `graphs[g].tokens_truncated` is true**, and the
count is reported as `omitted_truncated_graphs`. This is the decision the phrase *only adjacent
observed tokens form a stream* resolves, and it is resolved by exclusion rather than by stitching:

> When `n_tokens > 6` the instrument prints token indices `{0, 1, 2, n-3, n-2, n-1}`
> (`docs/specs/r2a-expert-trace.md` finding 6). Between index 2 and index `n-3` there are `n-6`
> token positions whose demands existed and were never printed. Replaying across that gap would
> credit a policy with retaining an expert through an unknown number of unobserved evictions, which
> **overstates** every hit rate by an amount the document cannot bound. Resetting the cache at the
> gap instead **understates** it by an amount the document also cannot bound. Neither is a
> measurement, so the graph is excluded and counted.

On the section 4.5 corpus this costs nothing — the 40 prompts are five tokens or fewer by
construction, so `tokens_truncated` is false on all 40 documents and 192 of 192 token positions are
replayed. The rule exists so that a longer-prompt corpus fails visibly rather than quietly.

A `(graph, token, layer)` triple that printed no `ffn_moe_topk` block contributes nothing and is
counted in `omitted_layer_positions`. On the real model this is layer 15 of every prompt: the graph
reduces to the last token before the final layer's FFN, so `moe.topk_layers` is `[0 .. 14]` and 15
of 16 layers are ever demanded. That is an instrument property, not a model property, and the
document reports `layers_demanded` explicitly so no reader infers a 15-layer model.

#### 2.2.2 Replay order

The trace lists `selections[]` in observation order, which is transcript order, which is ggml graph
order: **layer-major** — every token of layer 0, then every token of layer 1. That is what prefill
does. Decode issues, for one token, layer 0 through `n_layer-1` in turn: **token-major**.

The document reports **both orders** over the same admitted demand set, because the section 4.5
probe measured that the order changes the answer:

| Budget | LRU hit per mille, token-major | LRU hit per mille, layer-major |
| --- | --- | --- |
| 6 per cent of expert bytes | 0 | 330 |
| 12 per cent | 247 | 330 |
| 25 per cent | 488 | 381 |

Reporting one order and calling it *the* residency result would be a claim about a regime the
document had not examined. The **verdict is defined on `token_major`** (section 2.8), because
`docs/specs/align-llm.md` section 7.1 assigns "expert cache / token間reuse / prefetch" to decode and
assigns "sequential layout / bandwidth" to prefill; `layer_major` is reported beside it as the
prefill-regime sensitivity.

Within one document, the token-major order is `(graph ordinal, token index, layer, slot)`, all
ascending. It is produced by one `sort()` over packed `i64` words:

```text
word = order << 17 | key
key   = layer * n_expert + expert                        17 bits, key < MAX_RESIDENCY_KEYS
order = ((graph * MAX_TOKENS + token) * MAX_LAYERS + layer) * MAX_SLOTS + slot
        graph  < MAX_GRAPHS = 4096      12 bits
        token  < MAX_TOKENS = 262144    18 bits
        layer  < MAX_LAYERS = 256        8 bits
        slot   < MAX_SLOTS  = 128       7 bits                       45 bits
```

62 bits, so every word is a positive `i64` and the sort is the shipped `array<i64>` sort with no
comparator. Documents are **not** merged before sorting: each document is sorted alone and the
results are concatenated in trace-list order, which keeps the packed word inside 62 bits and makes
the list order part of the input identity rather than an implicit detail.

The `layer_major` order is the trace's own `selections[]` order, concatenated in the same list
order, with no sort at all.

#### 2.2.3 Pooling and cache lifetime

The 40 prompts pool into **one continuing stream**: the cache is not reset between graphs and is not
reset between documents. `pooling` is the document field recording this, and its only value at
`schema_version: 1` is `"continuing"`.

The argument is that this is the honest model of the thing being simulated. A residency tier in a
serving process is not flushed between user requests; an expert resident because prompt 7 used it is
genuinely still resident when prompt 8 arrives. The alternative — reset per document — models a cold
process per request, which is the regime R3 is explicitly not optimizing.

The section 4.5 probe measured both, and the difference is the single largest effect in the whole
study:

| Budget | Policy | Continuing hit per mille | Per-document reset hit per mille |
| --- | --- | --- | --- |
| 6 per cent | `lfu` | 226 | 95 |
| 12 per cent | `lfu` | 376 | 241 |
| 25 per cent | `lru` | 488 | 327 |
| 25 per cent | `lfu` | 602 | 327 |
| 25 per cent | `belady` | 782 | 330 |

Under reset, an episode is roughly five token positions and 450 demands, the cache never fills at
any budget above 6 per cent, and `lru`, `lfu`, and `belady` all collapse to the same number: the
measurement stops discriminating between policies at all. That is not evidence that the policies are
equivalent; it is evidence that a five-token episode is too short to exercise a cache. **The pooled
continuing stream is what makes R3 a measurement rather than a compulsory-miss count**, and it is
also, separately, the direct numeric evidence for cross-prompt expert reuse — the thing the R2 gate
could only measure within a prompt.

`reset` is recorded as a deferred second mode in section 5.5 with this table as the reason it is a
different question rather than a variant.

#### 2.2.4 Slot coverage, and what every rate is conditional on

On this model `n_expert_used` is 8 and the instrument prints six slots, `{0, 1, 2, 5, 6, 7}`
(`docs/specs/r2a-expert-trace.md` finding 6, reached for the first time on real data by the R2
gate). Slots 3 and 4 of every token of every layer are **never observed**, so:

- the replayed stream is a 750-per-mille subsample of the true demand;
- `bytes_fetched` understates the true traffic;
- hit rates are biased by an unknown sign — the two hidden experts would add both demands and cache
  pressure.

The document carries `slot_coverage_per_mille` (750 here), `observed_slots` (`[0,1,2,5,6,7]`), and
`n_expert_used` (8) at top level, and every summary line prints the coverage. **No rate in the
document is described as a hit rate without the qualifier "over printed slots".** This is not
correctable by R3; it is correctable only by R2c's instrument patch, and section 5.2 says so.

### 2.3 CLI surface

```text
main --simulate-residency TRACE_LIST MODEL_IR.json BUDGET_BYTES              # document to stdout
main --simulate-residency TRACE_LIST MODEL_IR.json BUDGET_BYTES OUT.json     # to file, plus summary
```

The grammar, arity rules, `MAX_PATH_BYTES` guard on every path operand, byte-identical-document
requirement across the two forms, and exit mapping are `--model-ir`'s and `--expert-trace`'s, reused
verbatim (`src/main.align:531-617`): exit `0` on `status: "ok"`, `Err(Error.Invalid)` on
`status: "error"`, and arity checked before any path or file work so an arity failure produces no
output at all.

**`TRACE_LIST` is a file of paths, one per line, and not a variadic operand list.** The alternative —
`main --simulate-residency MODEL_IR.json BUDGET_BYTES TRACE.json ...` — makes the optional `OUT.json`
ambiguous against a final trace path, which is exactly the arity failure the existing arms are built
to reject before doing any work. A list file keeps the arity fixed at three or four, makes the pooled
corpus an artifact that can be checked in and hashed, and makes the replay order of section 2.2.2
explicit and reproducible rather than shell-glob-dependent. A single-trace run is a one-line list.
The list is read with the same `MAX_PATH_BYTES` guard applied to every line, holds at most
`MAX_TRACE_PATHS` entries, rejects an empty line, and rejects a duplicate path
(`R3_TRACE_LIST_DUPLICATE`) — replaying the same prompt twice would fabricate reuse.

Sniffing the first operand to accept *either* a document or a list is rejected: a JSON document whose
first byte is not `{` and a list whose first path begins with `{` are both constructible, and a
fail-open heuristic on the input that defines the whole measurement is the wrong place to save a
line.

**`BUDGET_BYTES` is a non-negative decimal integer, parsed by the bounded private parser of
section 2.1**, and it is load-bearing rather than decorative even though the document reports a
sweep. It is *the target hardware condition* of the roadmap gate: the sweep is context, and the
verdict is answered at this budget. It appears in the sweep as a ninth point marked
`requested: true`.

**There is no `--policy` flag, no `--order` flag, and no `--window` flag.** A policy flag would let a
caller select the policy that wins on their corpus and report it as a finding, which is the failure
mode section 1.3's "no policy tuning loop" exists to prevent. An order flag is unnecessary because
both orders are always reported. A window flag would make the three `recent_reuse` constants tunable
against the evaluation corpus.

The two-operand summary block, in this exact order:

```text
residency sim:
status:            OK | ERROR
traces:            <integer> admitted of <integer> listed
demands:           <integer> over <integer> token position(s)
slot coverage:     <integer> per mille (<integer> of <integer> slot(s))
experts:           <integer> distinct of <integer>
budget:            <integer> bytes (<integer> per mille of expert bytes)
baseline:          lru <integer> bytes fetched
best:              <policy> <integer> bytes fetched
optimal:           belady <integer> bytes fetched
verdict:           BEATS_BASELINE | NO_POLICY_BEATS_BASELINE | NO_HEADROOM
error:             <code>          # only when status is ERROR
detail:            <identifier>    # only when status is ERROR
```

Every ratio in the block is an integer per mille and every count is exact, reusing the R0 and R2A
convention; `-` is reserved for a value the inputs do not supply.

### 2.4 The policy set

Ten rows. Each is a pure function of the stream, the budget, and the size table; none reads a router
score, a clock, or a bandwidth. Ties in victim selection are broken by **least-recently-used, then
lowest packed key**, uniformly, so every policy is deterministic and the document is reproducible.

| `policy` | Role | Rule |
| --- | --- | --- |
| `null` | Floor | No cache. Every demand is a miss. `bytes_fetched` is the total demanded byte volume, and it is the denominator every saving is measured against |
| `compulsory` | Floor | Unbounded capacity. Misses equal distinct demanded keys. The lower bound no policy at any budget can beat |
| `belady` | Ceiling | Offline optimal: evict the resident key whose next use is furthest away, never-again first. The upper bound on what *any* online policy could achieve at this budget, and therefore the headroom term of section 2.8 |
| `lru` | **Baseline** | Evict least recently used |
| `lfu` | Candidate | Evict least frequently demanded so far; ties to LRU. Counts are never aged |
| `recent_reuse_w2` | Candidate | Evict the key used in the fewest of the last **2** token positions; ties to LRU |
| `recent_reuse_w8` | Candidate | The same at a window of **8** token positions |
| `recent_reuse_w32` | Candidate | The same at a window of **32** token positions |
| `topk_prefetch_k1` | Candidate | LRU eviction, plus: at each token boundary, for each layer, admit the **1** most frequently demanded expert of that layer so far if not resident. Every admission counts its bytes in `bytes_fetched` |
| `topk_prefetch_k8` | Candidate | The same at **k = 8**, one full router width |

Four choices in that table are decisions rather than defaults:

**`lru` is the baseline because `docs/specs/align-llm.md` section 7.4 names it as the thing not to
depend on.** Beating `null` would be trivial and would prove nothing.

**`belady` is included even though it is unimplementable online**, because without it the document
cannot distinguish "no candidate policy beat LRU because none is better" from "no candidate policy
beat LRU because nothing could". Those two produce opposite investment decisions, and section 2.8's
`NO_HEADROOM` verdict exists to separate them.

**`belady` is miss-optimal, not byte-optimal, and the document does not claim otherwise.** It evicts
the resident key whose next use is furthest away without consulting the size table, which is optimal
for *misses*. On a model whose experts differ in size — `uniform_expert_bytes: false`, the real case
— the byte-minimizing offline policy is a different, size-aware schedule, and R3 does not compute
it. So `belady`'s `bytes_fetched` is an **achievable byte total under a miss-optimal reference**,
not the minimum achievable byte total, and section 2.8's `headroom_per_mille` inherits exactly that
property. Section 2.8 records the one-directional consequence for `NO_HEADROOM`.

**`recent_reuse` ships as three fixed windows rather than one tuned window** because the section 4.5
probe showed the window is the dominant parameter — at 25 per cent of expert bytes the policy moves
from exactly LRU's 488 per mille at `w=2` to 603 per mille at `w=32`. A single window would have
hidden that; a searched window would have overfitted 40 prompts. Three fixed windows spanning
sub-episode, episode, and multi-episode scale expose the trend and commit to nothing.

**`topk_prefetch` charges its own traffic**, which is the entire point of including it. The document
also reports `prefetch_fetches` and `prefetch_useful` per policy — prefetched keys later hit before
eviction — so a prefetch that never pays for itself is visible as a ratio and not merely as a worse
total.

**A prefetched block enters the cache as the most recently used**, at the recency of the demand its
token boundary precedes. This is the insertion recency the plan originally left unstated, and it is
a contract because the two available answers are not equivalent: an LRU-position insertion makes a
prefetched block the *next victim*, so under a full cache it is evicted by the very token position
it was fetched for and the policy degenerates into a pure traffic tax that can never hit. MRU
insertion is the ordinary cache semantics — an admitted block has just been brought in — and it is
the only one under which `prefetch_useful` measures the policy rather than the insertion rule. Both
were evaluated; section 6 item 19 records the measured difference and the fact that it changed no
verdict, and section 4.5 finding 4's harmful-prefetch claim is restated there as conditional on this
choice. Ties among blocks admitted at the same boundary are broken by the lowest packed key, as
everywhere else.

### 2.5 Exchanged document — `R3_RESIDENCY_SIM`, `schema_version: 1`

#### 2.5.1 Top level

```json
{
  "schema_version": 1,
  "kind": "R3_RESIDENCY_SIM",
  "trace_list_path": "eval/traces/olmoe-v1.txt",
  "model_ir_path": "artifacts/olmoe-ir.json",
  "status": "ok",
  "error_code": "",
  "error_detail": "",
  "inputs": {},
  "model": {},
  "stream": {},
  "budgets": [],
  "orders": [],
  "verdict": {}
}
```

| Field | Type | Contract |
| --- | --- | --- |
| `schema_version` | integer | Always `1` |
| `kind` | string | Always `"R3_RESIDENCY_SIM"` |
| `trace_list_path`, `model_ir_path` | string | The operands verbatim, JSON-escaped. Never normalized, never absolutized |
| `status` | string | `"ok"` or `"error"`. No third value |
| `error_code` | string | `""` when ok; otherwise exactly one code from section 2.6 |
| `error_detail` | string | `""` when ok; otherwise a bounded, JSON-escaped identifier — a list line ordinal, a `(layer, expert)` pair, or a bounded escaped path basename. Never free prose and never a full path |
| `inputs` | object | Section 2.5.2 |
| `model` | object | Section 2.5.3 |
| `stream` | object | Section 2.5.4 |
| `budgets` | array | Section 2.5.5, ascending, nine entries |
| `orders` | array | Section 2.5.6, exactly two entries: `token_major` then `layer_major` |
| `verdict` | object | Section 2.5.7 |

On `status: "error"` the document is still written and every value derived before the failure is
present and truthful, mirroring R0's failure-persistence behavior, R1's section 2.5.1, and R2A's.

#### 2.5.2 `inputs`

```json
"inputs": {
  "listed_trace_count": 40,
  "admitted_trace_count": 40,
  "trace_schema_version": 1,
  "model_ir_schema_version": 2,
  "bytes_read": 2675149,
  "instrument_builds": [10566],
  "instrument_build_source": "absent"
}
```

`instrument_builds` is the ascending de-duplicated set of every admitted trace's `run.build`, and it
is `[]` when every trace reports `null` — which is the ordinary case
(`docs/specs/r2a-expert-trace.md` finding 8). A mixed set is **recorded, not rejected**, for exactly
R2A's reason: the grammar is the check, the build number is provenance.

#### 2.5.3 `model`

```json
"model": {
  "arch": "olmoe",
  "n_layer": 16,
  "n_expert": 64,
  "n_expert_used": 8,
  "expert_block_count": 1024,
  "total_expert_bytes": 3900702720,
  "smallest_expert_bytes": 3538944,
  "largest_expert_bytes": 4079616,
  "uniform_expert_bytes": false
}
```

`uniform_expert_bytes` is `false` here and it is the field that justifies section 2.8's byte metric:
the real model's per-layer mixed quantization (`docs/specs/r1c-olmoe-moe-ir.md` section 2.5.5) makes
two experts differ by 15 per cent, so a hit-rate tie can still be a byte win or loss.

#### 2.5.4 `stream`

```json
"stream": {
  "pooling": "continuing",
  "demand_count": 17280,
  "token_position_count": 192,
  "distinct_key_count": 938,
  "demanded_byte_total": 65512931328,
  "distinct_key_bytes": 3555803136,
  "layers_demanded": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14],
  "n_expert_used": 8,
  "observed_slots": [0,1,2,5,6,7],
  "slot_coverage_per_mille": 750,
  "one_token_working_set_keys": 90,
  "one_token_working_set_bytes": 341213184,
  "omitted_truncated_graphs": 0,
  "omitted_layer_positions": 192,
  "graph_phases": {"prefill": 40, "decode": 0, "single_token_first_graph": 0}
}
```

`one_token_working_set_bytes` is the distinct byte volume demanded by a single token position, and it
is in the document because it is the *explanatory* variable for the sharpest result in section 4.5:
LRU's hit rate is exactly zero at every budget below it and rises immediately above it. A reader who
has this number can predict the cliff without rerunning anything.

`graph_phases` carries R2A's three-valued `phase` forward unchanged, so a document derived entirely
from prefill graphs says so in a machine-readable field rather than only in prose.

#### 2.5.5 `budgets`

Eight or nine ascending entries. Eight are the swept context, defined without floats as

```text
sweep[i] = max(largest_expert_bytes, total_expert_bytes >> (7 - i))   for i in 0 .. 7
```

giving 1/128 through 1/1 of the model's expert byte footprint, and the ninth is the `BUDGET_BYTES`
operand. When the operand coincides with a sweep point the entry is not duplicated; it is the same
entry with `requested: true`.

```json
{"bytes": 975175680, "per_mille_of_expert_bytes": 250, "expert_equivalents": 256,
 "requested": true}
```

`expert_equivalents` is `bytes / mean_expert_bytes`, an integer, present so a reader can think in
experts rather than in gigabytes. The clamp to `largest_expert_bytes` is what makes the low end
legal: a budget below the largest expert can hold nothing and is `R3_BUDGET_TOO_SMALL` as an
operand, but as a *sweep* point it would be a silently degenerate row, so it is clamped and the
clamp is reported as `clamped: true`.

#### 2.5.6 `orders`

```json
"orders": [
  {"order": "token_major", "verdict_bearing": true, "policies": [ ... ], "per_layer": [ ... ]},
  {"order": "layer_major", "verdict_bearing": false, "policies": [ ... ], "per_layer": [ ... ]}
]
```

`policies` holds one entry per policy per budget:

```json
{"policy": "lfu", "budget_bytes": 975175680,
 "hits": 10410, "misses": 6870, "demands": 17280,
 "hit_per_mille": 602,
 "bytes_fetched": 26100006912, "demanded_byte_total": 65512931328,
 "bytes_fetched_per_mille_of_null": 398,
 "prefetch_fetches": 0, "prefetch_useful": 0,
 "resident_key_high_water": 258}
```

Every rate carries both of its terms: `hits` and `demands` beside `hit_per_mille`, `bytes_fetched`
and `demanded_byte_total` beside `bytes_fetched_per_mille_of_null`. A reader never has to trust a
per-mille value the document could not reconstruct.

`per_layer` holds one entry per layer per budget, with `layer`, `demands`, and `hit_per_mille` for
each policy, so a policy that wins overall while losing on a layer is visible. The section 4.5 probe
found exactly that case: at 25 per cent, `lfu` beats `lru` on 14 of the 15 demanded layers and loses
on layer 1 (415 against 437 per mille).

#### 2.5.7 `verdict`

```json
"verdict": {
  "rule_version": 1,
  "order": "token_major",
  "budget_bytes": 975175680,
  "baseline_policy": "lru",
  "baseline_bytes_fetched": 33532231680,
  "best_policy": "recent_reuse_w32",
  "best_bytes_fetched": 26033848320,
  "gain_per_mille": 223,
  "margin_per_mille": 50,
  "headroom_per_mille": 574,
  "jackknife_folds": 40,
  "jackknife_min_gain_per_mille": 213,
  "jackknife_stable": true,
  "result": "BEATS_BASELINE",
  "sweep_best": [ ... ]
}
```

`sweep_best` repeats `best_policy`, `gain_per_mille`, `headroom_per_mille`, and `result` for each budget
entry, so the gate's answer is available across the sweep and not only at the requested
point.

### 2.6 Validation order and error codes

Validation is ordered so that the cheapest and most diagnostic failure fires first, and so that no
document is read before its path is guarded. The order is normative: an input failing two conditions
reports the earlier code.

1. Arity. Three or four operands, else `Err(Error.Invalid)` with **no output at all**.
2. `MAX_PATH_BYTES` guard on `TRACE_LIST`, `MODEL_IR.json`, and `OUT.json` when present — empty,
   over-long, or NUL-bearing is `R3_PATH`, with no output and no read.
3. `BUDGET_BYTES` parse — `R3_BUDGET_MALFORMED` on a non-digit, a sign, an empty operand, or an
   overflow past `i64`.
4. Trace list read and scan — `R3_TRACE_LIST_UNREADABLE`, `R3_TRACE_LIST_EMPTY` (no non-empty line),
   `R3_TRACE_LIST_TOO_MANY` (over `MAX_TRACE_PATHS`), `R3_TRACE_LIST_DUPLICATE`, and `R3_PATH` for a
   guard failure on any line, whose `error_detail` is the one-based line ordinal.
5. Model IR read and decode — `R3_IR_UNREADABLE`, `R3_IR_TOO_LARGE` (over `MAX_DOCUMENT_BYTES`),
   `R3_IR_DECODE`, `R3_IR_SCHEMA` (`kind` not `R1_MODEL_IR`, or an unsupported `schema_version`),
   `R3_IR_STATUS` (`status` not `"ok"`).
6. Model IR shape — `R3_IR_NOT_MOE` when no `ExpertBlock` is declared, `R3_KEY_SPACE_TOO_LARGE` when
   `n_layer * n_expert > MAX_RESIDENCY_KEYS`, `R3_EXPERT_BLOCK_DUPLICATE` when two `ExpertBlock`s
   name the same `(layer, expert)`, `R3_EXPERT_BLOCK_RANGE` when one names a layer or expert outside
   the declared hyperparameters.
7. Budget floor — `R3_BUDGET_TOO_SMALL` when `BUDGET_BYTES < largest_expert_bytes`. This is checked
   against the Model IR and therefore cannot be checked at step 3. A budget that cannot hold the
   single largest expert makes every policy identical to `null`, so the run is refused rather than
   reported.
8. Each trace in list order — `R3_TRACE_UNREADABLE`, `R3_TRACE_TOO_LARGE`, `R3_TRACE_DECODE`,
   `R3_TRACE_SCHEMA`, `R3_TRACE_STATUS`, `R3_TRACE_NOT_MOE`, `R3_TRACE_DISAGREEMENT`,
   `R3_SHAPE_MISMATCH`. `error_detail` is the list ordinal.
9. Selection admission — `R3_EXPERT_OUT_OF_RANGE`, `R3_MISSING_EXPERT_BLOCK`, whose `error_detail`
   is the offending `(layer, expert)` pair; `R3_SELECTION_TOO_MANY` when the pooled stream exceeds
   `MAX_DEMANDS`.
10. Stream non-emptiness — `R3_EMPTY_STREAM` when every graph was excluded or every trace admitted
    zero selections. A simulation over an empty stream would report a hit rate of zero for every
    policy and a verdict of `NO_HEADROOM`, which is a confident wrong answer.
11. Cost guard — `R3_SIMULATION_COST` when the bound of section 2.7 is exceeded.

**A trace that fails admission fails the whole run; it is not skipped.** The alternative — pool the
admissible subset and report the count — would let a corpus silently shrink to the traces that
happen to parse, and the resulting verdict would be a measurement of an unnamed sub-corpus. The one
exception is the *truncated graph* of section 2.2.1, which is excluded by an explicit, counted,
documented rule rather than by a parse failure.

### 2.7 Ownership, bounded memory, and the cost guard

Every table is a pre-sized `array<i64>` indexed by a packed key; Align at this pin has no map type,
and none is needed once the key space is dense and bounded.

```text
key       = layer * n_expert + expert
key_space = n_layer * n_expert                            <= MAX_RESIDENCY_KEYS = 16384
```

`MAX_RESIDENCY_KEYS = 16384` admits 64 layers of 256 experts, which covers every announced MoE model
this repository has planned for, and bounds each per-key table at 128 KB. Eight such tables —
`resident`, `size`, `last_use`, `freq`, `recent_count`, `next_use`, `prefetched`, `resident_list` —
bound the per-key state at 1 MB.

```text
demand_count <= MAX_DEMANDS = 262144
```

Two `i64` columns of `MAX_DEMANDS` — the packed sort words and the Belady next-use column — bound
the stream state at 4 MB. `MAX_TRACE_PATHS = 4096` and `MAX_DOCUMENT_BYTES = 33554432` bound the
input side; only one document is held decoded at a time, because each trace's selections are
appended into the stream columns and the decoded record is dropped before the next path is opened.

**The cost guard is a stated bound, not an optimism.** Victim selection scans the resident set, so
one replay costs at most `demands * resident_high_water` element visits, and the document runs
at most `2 orders * 9 budgets * 10 policies = 180` replays plus `jackknife_folds * 2` more at the requested
budget. The run is refused with `R3_SIMULATION_COST` when

```text
demand_count * min(key_space, budget_bytes / smallest_expert_bytes) > MAX_SIMULATION_STEPS = 2^32
```

On the real corpus this evaluates to `17280 * 275 = 4,752,000`, three orders of magnitude inside the
bound. The guard exists so that a pathological input — a large key space at a large budget with a
long stream — is refused with a named code before it becomes an unbounded run, rather than
discovered as a timeout in CI.

A sorted or heap-ordered resident structure would remove the linear scan, and Align ships neither at
this pin. Building one is not justified by a measurement that finishes in milliseconds; the guard is
the honest alternative, and section 5.6 records the threshold at which the structure would become
necessary.

### 2.8 The verdict rule

Fixed before the qualification — in the design commit that also carries the section 4.5 probe — and
versioned in the document as `rule_version: 1`. It is **not** a rule stated before any measurement:
the probe ran first, and the effect floor and the stability test were chosen knowing roughly what
the candidates do on this corpus. What the rule buys is that it cannot be adjusted *after* the
qualification to make a particular policy win, and that is the property the version number pins.

**Metric.** `bytes_fetched` on the `token_major` order at the requested budget. Not hit rate:
experts differ in size on the real model (section 2.5.3), and a prefetch policy moves bytes without
a demand miss, so only a byte metric charges every policy for everything it does.

**Effect floor.** A candidate policy `P` **beats** the baseline when

```text
1000 * bytes_fetched(P) <= (1000 - MARGIN) * bytes_fetched(lru),   MARGIN = 50 per mille
```

`MARGIN` is 50 per mille — 5 per cent. The simulation is deterministic, so the margin is not a noise
allowance for the replay; it is a *generalization* allowance for the corpus. A 1-per-cent byte
difference on 40 prompts is not a reason to prefer one eviction rule over another in a runtime.

**The floor is a filter against noise, not a demanding bar, and the document should not be read as
if it were one.** On the real corpus at the requested budget an entirely untuned `lfu` — no window,
no aging, no parameter chosen from this corpus — already clears it four times over at 221 per mille
(33,532,231,680 B against 26,100,006,912 B). A `BEATS_BASELINE` verdict therefore says "this
candidate is not within the corpus-generalization band of LRU"; it does not say "this candidate was
hard to find".

**Stability.** A win must survive leave-one-document-out resampling: the inequality above must hold
on all `admitted_trace_count` streams formed by dropping one document. This is an integer comparison
repeated `N` times and needs no distribution, no variance estimate, and no float — which is why it is
the stability test rather than a confidence interval. The R2 gate needed a Wilson interval because it
estimated a proportion from Bernoulli trials; R3 compares two deterministic totals over the same
stream, and the only uncertainty is which prompts are in the corpus.

**Result.** Exactly one of:

| `result` | Condition |
| --- | --- |
| `BEATS_BASELINE` | At least one candidate meets the effect floor and is jackknife-stable. `best_policy` is the lowest-byte such candidate |
| `NO_POLICY_BEATS_BASELINE` | No candidate qualifies, and `headroom_per_mille >= MARGIN` — a better policy may exist and none of these is it |
| `NO_HEADROOM` | No candidate qualifies, and `headroom_per_mille < MARGIN` — `lru` is already within the effect floor of the offline optimum, so **no policy can beat it here** |

with

```text
headroom_per_mille = 1000 * (bytes_fetched(lru) - bytes_fetched(belady)) / bytes_fetched(lru)
```

The `NO_HEADROOM` row is why `belady` is in the policy set. Without it, the two very different
findings *"these candidates are wrong"* and *"nothing could do better"* would report the same value,
and they imply opposite decisions about whether to build a score-based cache.

**`headroom_per_mille` is measured against a miss-optimal reference, not a byte-optimal one.**
`belady` minimizes misses (section 2.4), so on a model with unequal expert sizes the true
byte-minimizing offline schedule can fetch *fewer* bytes than `belady` does, and this term can
therefore understate the real headroom. The consequence is one-directional and worth stating
plainly: `NO_HEADROOM` is **conservative in one direction only**. When it fires, "LRU is already
within the effect floor of a miss-optimal reference" is what has been shown, and a size-aware
offline schedule could still have byte headroom the document did not look for; when it does not
fire, the headroom it reports is genuinely available. A reader deciding *not* to invest on the
strength of a `NO_HEADROOM` row is relying on the weaker of the two directions. Computing the
byte-optimal offline schedule is not deferred for effort — it is a different problem (offline
caching with unequal costs, which is not solved by any furthest-next-use rule) — and it is recorded
as such in section 5.8.

`sweep_best` applies the same rule at each budget entry, so the gate is answered as a curve
rather than as a point.

## 3. Cross-cutting closure matrix

### 3.1 The matrix

`src/residency_sim.align` is one module by design (section 2.1), so the matrix has three affected
units — the module, `src/main.align`'s dispatch, and the fixture/oracle graph — plus the shared
`Makefile` and the document contract.

| Cell | Implementation owner | Regression |
| --- | --- | --- |
| **Construction** — trace list read, path guard, duplicate rejection | `read_trace_list` | `list-empty`, `list-blank-line`, `list-duplicate`, `list-over-cap`, `list-path-too-long` |
| **Construction** — Model IR decode into the subset record | `decode_model_ir` | `ir-unknown-fields-ignored` asserts the real-shaped document with `tensors[]` decodes and the ignored members are absent from every derived value |
| **Formation/validation** — steps 1–11 of section 2.6, in order | `validate` | One fixture per code; `validation-order` asserts that an input failing two conditions reports the earlier one |
| **Success** — demand stream, both orders | `build_stream` | `stream-token-major` and `stream-layer-major` assert the exact demand sequence for a generator-known synthetic trace |
| **Success** — each of the ten policies | `replay` | `policy-oracle` asserts hits, misses, bytes, and prefetch counts against `scripts/residency_oracle.py` for every policy at every sweep budget |
| **Success** — budget sweep, clamp, requested-point merge | `build_budgets` | `budget-clamp` (low end clamps and reports `clamped`), `budget-coincides` (operand equals a sweep point, eight entries not nine) |
| **Success** — verdict, all three results | `decide` | `verdict-beats`, `verdict-no-policy`, `verdict-no-headroom`, each on a fixture constructed to produce that result |
| **Success** — jackknife | `jackknife` | `jackknife-unstable` asserts a corpus where one document flips the sign reports `jackknife_stable: false` and does not report `BEATS_BASELINE` |
| **Failure** — every code of section 2.6 | `validate` | One fixture each; `error-document-truthful` asserts the partial document carries every value derived before the failure |
| **Malformed input** — non-JSON, truncated JSON, wrong `kind`, wrong `schema_version`, `status: "error"` trace | `decode_*` | `malformed-trace`, `malformed-ir`, `trace-status-error`, `schema-future` |
| **Early exit** — arity failure produces no output; path guard failure produces no read | `main` dispatch | `arity-no-output` asserts an empty stdout and an untouched `OUT.json` |
| **Move-in/out, source nulling, replacement** — each decoded document is dropped before the next is opened; stream columns are frozen once | `build_stream` | `stream-single-document-residency` asserts peak decoded-document count is one, by construction review plus a `bytes_read` accounting assertion |
| **Cleanup** — `OUT.json` is written once, whole, and only on a completed render | `write_document` | `output-atomicity` asserts a failed render leaves no partial `OUT.json` |
| **Bounded memory** — every cap of section 2.7 | `validate`, `replay` | `cap-key-space`, `cap-demands`, `cap-trace-paths`, `cap-document-bytes`, `cap-simulation-cost`, each with a fixture one past the cap |
| **Both entrypoint forms** — three-operand and four-operand produce byte-identical documents | `main` dispatch | `two-form-identity`, the assertion `--model-ir` and `--expert-trace` already carry |
| **Determinism** — the same inputs produce a byte-identical document | `replay`, `write_document` | `determinism` runs the smoke twice and diffs |
| **`src/main.align` dispatch** — the new arm does not perturb the existing arms | `main` | The existing `--inspect-gguf`, `--model-ir`, `--expert-trace` smokes, unchanged, are the regression |
| **Fixture/oracle agreement** — the Python oracle and the Align module implement the same policies | `scripts/residency_oracle.py` | `policy-oracle` above; the oracle is written from section 2.4 and never from the Align source |
| **`Makefile`** — a new hosted target and a new opt-in target | `Makefile` | Section 3.3 |

### 3.2 Deferred cells

Three cells are **explicitly deferred** rather than closed, each to a named section: `pooling: "reset"` (section 5.5), the `layer_major` order bearing a verdict (section 2.2.2 fixes it at
`verdict_bearing: false`), and an ordered resident structure replacing the linear victim scan
(section 5.6).

### 3.3 Preflight consequence

`make residency-sim-smoke` joins `HOSTED_CHECK_TARGETS`. It qualifies on the same grounds that
admitted `gguf-smoke`, `model-ir-smoke`, `expert-trace-smoke`, and `alignpack-smoke`: it needs no
model, no network, no instrument, and no GPU; it writes well under a megabyte into a temporary tree
and removes it on every exit path; and it is the only hosted owner of two new public surfaces (the
CLI arm and the document). Adding a member to that list changes aggregate membership, so
`CLAUDE.md`'s verification rule selects one fresh `make ci` for the implementation branch, and
`scripts/pre-pr` selects executable preflight for the whole change.

`make residency-sim-qualification` stays outside `HOSTED_CHECK_TARGETS`,
`CAPABLE_ONLY_CHECK_TARGETS`, and every aggregate. It follows
`scripts/run-expert-locality-gate`'s rule that a qualification which silently passes when its
subject is missing is worse than none, and it is opt-in through **exactly two** variables, which are
the two that name the subject:

| Variable | Owner | Default | Absent |
| --- | --- | --- | --- |
| `ALIGN_LLM_LLAMA_EVAL_CALLBACK` | `scripts/run-residency-sim` | **none** | one exact `N/A` line, exit 0 — unset, or set to something not executable |
| `ALIGN_LLM_GGUF_MODEL` | `scripts/run-residency-sim` | **none** | one exact `N/A` line, exit 0 — unset, or naming a file that is not there |
| `ALIGN_LLM_LOCALITY_PROMPTS` | `scripts/run-residency-sim` | `eval/prompts/expert-locality-v1.txt` | **exit 1.** A missing corpus is a broken checkout, not an absent subject, and it must not read as `N/A` |
| `ALIGN_LLM_LOCALITY_PROMPT_COUNT` | `scripts/run-residency-sim` | `40` | n/a — an ASCII integer in `[1, 4096]`, matching `MAX_TRACE_PATHS`; exit 1 outside that range or when the corpus holds fewer prompts than requested |
| `ALIGN_LLM_RESIDENCY_BUDGET` | `scripts/run-residency-sim` | `total_expert_bytes >> 2`, the section 4.5 probe's 25-per-cent point | n/a |
| `ALIGN_LLM_RESIDENCY_SIM_UPDATE_GOLDEN` | `scripts/run-residency-sim-smoke` | unset | `1` rewrites `eval/fixtures/residency-sim/sim-basic.golden.json` instead of comparing against it. A maintenance switch; never set in CI |

The `N/A` rule is over the first two rows only. `ALIGN_LLM_LOCALITY_PROMPTS` has a checked-in
default, so it is not an opt-in switch, and a run that cannot find the corpus it was pointed at
fails rather than reporting an absent subject (section 6 item 23).

## 4. Verification

### 4.1 Synthetic corpus

The smoke needs a MoE trace with generator-known expert ids and a Model IR with generator-known
`byte_size`s, and both generators already exist.

`scripts/eval_callback_fixture.py` ships `moe_graph(n_layer, n_tokens, router, graph_ordinal, ...)`
with a seeded `router` object that decides each `(graph, layer, token)` selection, and
`expected_selections(graphs)` that names the answer independently. R3's fixture builds transcripts
from it, converts them with the already-verified `main --expert-trace`, and gets traces whose every
selection is known before the simulator runs. Cases:

| Case | Shape | Asserts |
| --- | --- | --- |
| `sim-basic` | 4 layers, 8 experts, top-2, 6 tokens, 4 documents | Every policy against the oracle at every sweep budget |
| `sim-cyclic` | A stream engineered so one token's working set exactly equals the budget | The LRU cliff, and that `belady` and `lfu` are above it |
| `sim-uniform-bytes` | Every expert the same size | `uniform_expert_bytes: true`, and that hit-rate and byte orderings agree |
| `sim-mixed-bytes` | The real model's per-layer Q6_K/Q4_K pattern | A hit-rate tie that is a byte win, which is section 2.8's whole justification |
| `sim-truncated` | One graph with `n_tokens = 9`, so `tokens_truncated` is true | The graph is excluded and `omitted_truncated_graphs` is 1 |
| `sim-single-trace` | A one-line trace list | Pooling of one is not a special case |
| `sim-prefetch-useless` | A stream where the frequent experts are never re-demanded | `prefetch_useful: 0` and a `bytes_fetched` above `lru`'s |
| `sim-no-headroom` | A stream whose working set fits the budget | `headroom_per_mille: 0` and `result: "NO_HEADROOM"` |
| `sim-jackknife-unstable` | 5 documents, one carrying the entire LFU win | `jackknife_stable: false`, and not `BEATS_BASELINE` |
| One fixture per error code | — | Section 2.6, plus `validation-order` |

`scripts/gguf_fixture.py` already builds olmoe-shaped GGUFs (its `olmoe_kvs` / `olmoe_role_shape`
helpers, added by R1C), so the synthetic Model IR is produced by running the already-verified
`main --model-ir` over a small synthetic olmoe file rather than by hand-writing JSON. The fixture
graph therefore contains no hand-authored `R1_MODEL_IR` and cannot drift from R1C's renderer.

### 4.2 The owner: `residency-sim-smoke`

`scripts/run-residency-sim-smoke`, `make residency-sim-smoke`. Builds the corpus, runs the arm over
each case in both forms, and compares against `scripts/residency_oracle.py` — an independent Python
implementation of section 2.4 written from this document, never from the Align source, in the
tradition of `scripts/expert_locality_gate.py` and R2A's aggregate oracle. Every count in the
document is compared exactly; no tolerance is used anywhere, because every value is an integer.

### 4.3 The qualification: `residency-sim-qualification`

`scripts/run-residency-sim`, `make residency-sim-qualification`. Captures the 40
prefill transcripts of `eval/prompts/expert-locality-v1.txt` with the flags and safeguards
`scripts/run-expert-locality-gate` established — `-n 0 -fa off -ctk f32 -ctv f32 -nr -c 512`, a
`ulimit -f` cap, a 600-second timeout, deletion of each transcript immediately after conversion, and
a model size-and-mtime read-only proof — converts each with `main --expert-trace`, derives the Model
IR once with `main --model-ir`, writes the trace list, and runs the arm. Before invoking the
instrument, it validates the prompt count and asks the simulator to validate the generated Model IR
and requested/default budget against a one-row probe list whose trace is deliberately absent. Only
the exact expected `R3_TRACE_UNREADABLE` result admits prompt capture; an earlier model or budget
error fails before external work. It records the corpus
identity, the instrument version block, and the whole verdict, and it exits 0 on every one of the
three `result` values because all three are answers to the roadmap gate. It exits nonzero only when
the instrument, the corpus, or a parser prevented a measurement.

R2c makes positive `-n` values emit decode graphs. The runner therefore uses explicit `-n 0` and,
after conversion, requires R2's original compact first/last-three router-slot form. A pinned R2c
full-axis instrument is a controlled qualification failure rather than a silent change to this
already-recorded six-slot demand stream; R2c's own qualification owns decode and full-axis capture.

### 4.4 What is not run

No security, resource, race, fuzz, stress, platform, mutation, or benchmark suite is selected. R3
adds no process, no thread, no socket, no subprocess, and no timing claim, so none of those owner
boundaries changes. `make ci` is selected once, for the `HOSTED_CHECK_TARGETS` membership change of
section 3.3, and not for anything else in this capability.

### 4.5 Probe evidence

An independent Python simulator was run during this design against the real corpus, so that every
expectation above is grounded and the fixture shapes of section 4.1 are chosen against measured
behavior rather than against a guess. **This is probe evidence, not the capability's verification;**
it is recorded here because a plan whose expectations were never checked is a plan that will be
corrected during review.

Provenance: host as recorded in `docs/specs/r2a-expert-trace.md` section 2.2;
`llama-eval-callback` build 10566; `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`;
`eval/prompts/expert-locality-v1.txt` (40 prompts, md5 `d7fff23f5a1d4f6237e6f848f3318d8b`, 877 B);
traces produced by `main --expert-trace` at `agent/r2-locality-gate`'s `src/expert_trace.align`
(since merged as PR #131); sizes from `main --model-ir` at `agent/r1c-olmoe-moe-ir` (since merged as
PR #132). All 40 transcripts were deleted after
conversion.

Stream: 40 documents, 40 admitted, 0 truncated graphs, 192 token positions, **17,280 demands**, 938
distinct `(layer, expert)` keys of 1,024, layers 0–14 demanded, slots `{0,1,2,5,6,7}` — 750 per mille
coverage. One token position demands 90 distinct experts and **341,213,184 bytes**.
`total_expert_bytes` 3,900,702,720; `largest_expert_bytes` 4,079,616.

Token-major, continuing. Each cell is `hit per mille / gigabytes fetched`:

| Budget | %  | `null` | `compulsory` | `belady` | `lru` | `lfu` | `recent_w2` | `recent_w8` | `recent_w32` | `topk_k1` | `topk_k8` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30,474,240 | 0 | 0 / 65.5 | 945 / 3.6 | 69 / 61.0 | 0 / 65.5 | 25 / 63.8 | 1 / 65.4 | 12 / 64.7 | 24 / 63.9 | 0 / 76.1 | 0 / 150.4 |
| 60,948,480 | 1 | 0 / 65.5 | 945 / 3.6 | 139 / 56.3 | 0 / 65.5 | 59 / 61.6 | 6 / 65.1 | 44 / 62.6 | 56 / 61.8 | 0 / 75.7 | 0 / 147.8 |
| 121,896,960 | 3 | 0 / 65.5 | 945 / 3.6 | 260 / 48.5 | 0 / 65.5 | 121 / 57.6 | 33 / 63.3 | 112 / 58.2 | 125 / 57.3 | 0 / 74.8 | 0 / 143.1 |
| 243,793,920 | 6 | 0 / 65.5 | 945 / 3.6 | 409 / 38.7 | 0 / 65.5 | 226 / 50.7 | 103 / 58.7 | 210 / 51.7 | 229 / 50.5 | 0 / 73.0 | 0 / 133.2 |
| 487,587,840 | 12 | 0 / 65.5 | 945 / 3.6 | 580 / 27.6 | 247 / 49.3 | 376 / 40.8 | 247 / 49.2 | 335 / 43.5 | 360 / 41.9 | 247 / 54.2 | 246 / 100.3 |
| 975,175,680 | 25 | 0 / 65.5 | 945 / 3.6 | 782 / 14.3 | 488 / 33.5 | 602 / 26.1 | 488 / 33.5 | 520 / 31.4 | 603 / 26.0 | 488 / 35.8 | 488 / 57.7 |
| 1,950,351,360 | 50 | 0 / 65.5 | 945 / 3.6 | 904 / 6.2 | 812 / 12.3 | 812 / 12.2 | 812 / 12.3 | 812 / 12.3 | 807 / 12.6 | 812 / 13.3 | 812 / 20.7 |
| 3,900,702,720 | 100 | 0 / 65.5 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 |

Applying section 2.8's rule:

| Budget | % | Headroom | Best candidate | Gain | `result` |
| --- | --- | --- | --- | --- | --- |
| 30,474,240 | 0 | 68 | `lfu` | 25 | `NO_POLICY_BEATS_BASELINE` |
| 60,948,480 | 1 | 139 | `lfu` | 59 | `BEATS_BASELINE` |
| 121,896,960 | 3 | 259 | `recent_reuse_w32` | 124 | `BEATS_BASELINE` |
| 243,793,920 | 6 | 409 | `recent_reuse_w32` | 229 | `BEATS_BASELINE` |
| 487,587,840 | 12 | 440 | `lfu` | 171 | `BEATS_BASELINE` |
| 975,175,680 | 25 | 574 | `recent_reuse_w32` | 223 | `BEATS_BASELINE` |
| 1,950,351,360 | 50 | 493 | `lfu` | 2 | `NO_POLICY_BEATS_BASELINE` |
| 3,900,702,720 | 100 | 0 | — | 0 | `NO_HEADROOM` |

Six findings the design is built around:

1. **LRU has a hard floor at the one-token working set.** Its hit rate is exactly 0 per mille at
   every budget below 341,213,184 B and rises immediately above it (0 at 90 per cent of the working
   set, 175 at 100 per cent, 246 at 110 per cent). This is the classic cyclic-reference pathology:
   a token touches 15 layers before returning to layer 0, so LRU evicts every expert exactly before
   it is needed again. It is the single strongest argument in the study for
   `docs/specs/align-llm.md` section 7.4's "LRUだけに依存しない", and it is why
   `one_token_working_set_bytes` is a document field.
2. **Frequency wins across the whole practical range and the win is stable.** Leave-one-document-out
   over 40 folds gives a minimum gain of 57 per mille at 1 per cent, 219 at 6 per cent, 164 at
   12 per cent, and 213 at 25 per cent; every fold clears the 50-per-mille floor. At 50 per cent the
   folds span −7 to +19 per mille and the win correctly fails the rule.
3. **The `recent_reuse` window is the dominant parameter**, moving 25-per-cent behavior from exactly
   LRU (488 per mille at `w=2`) to slightly past LFU (603 at `w=32`). Three fixed windows are in the
   contract for this reason.
4. **Top-k prefetch is uniformly harmful on this evidence.** Prefetch usefulness is 0–3 per mille at
   every k and budget: at 25 per cent, `k=1` issues 600 prefetches of which 2 are later hit, and
   `k=8` issues 6,355 of which 0 are. It adds 2.2 to 24.2 GB of traffic for no measurable hit gain.
   The policy stays in the set because a documented negative is the finding, and because it is the
   only row that exercises the `prefetch_fetches` / `prefetch_useful` accounting.

   **This probe ran with the LRU-position prefetch insertion the shipped code later replaced, and
   half of the finding does not survive that change.** Section 2.4 now specifies MRU insertion and
   section 6 item 19 records why. Re-measured on the same corpus with the shipped rule, at 25 per
   cent `k=1` issues 219 prefetches of which 102 are later hit (465 per mille) and `k=8` issues
   3,332 of which 1,590 are (477 per mille) — so "prefetch usefulness is 0–3 per mille" was a
   property of the insertion rule and not of the workload, and it is superseded. What survives is
   the part the verdict rests on: **no `topk_prefetch` cell is below `lru` at any budget in either
   order** (equal at 100 per cent, where headroom is zero), 34.1 GB against 33.5 GB at 25 per cent
   for `k=1` and 43.2 against 33.5 for `k=8`. The finding is therefore restated as *top-k prefetch
   buys hits and pays for them with more bytes than it saves*, which is the same investment answer
   reached for a different reason, and section 7.4 carries the re-measured tables.
5. **Optimal headroom stays large where the candidates win** — 574 per mille at 25 per cent, of
   which `recent_reuse_w32` captures 223. Roughly 60 per cent of the achievable advantage is left on
   the table by every online policy tested, which is direct evidence *for* section 5.1's score-based
   and impact-driven work rather than against it.
6. **Pooling and replay order both change the answer**, by the amounts tabulated in sections 2.2.2
   and 2.2.3. Both are therefore contract fields, both are argued, and one of the two is reported in
   duplicate rather than chosen silently.

**The honest caveat, stated in the document and in every summary line.** This stream is thin and
narrow: 192 token positions across 40 independent prompts of at most six tokens each; six of eight
router slots printed; prefill graphs only, replayed in decode order because decode is the regime
being modelled and not because decode was observed. Cross-prompt reuse carries most of the cache
pressure (section 2.2.3), so the result is properly read as *"across a session of many short
requests, frequency-aware residency beats recency"* and not as *"within a generation, expert reuse
is high"*. The second statement needs the decode traces R2c's instrument patch would produce, and
R3 does not have them. The `recent_reuse` window findings in particular are measured against
episodes of about five tokens, and `w=32` spans multiple prompts — so at this corpus depth `w=32` is
closer to a slowly-aged LFU than to a genuine recency window, and a decode corpus could separate
them differently.

## 5. Deferred, with reasons

### 5.1 Score-based, impact-driven prefetch, and CPU fallback

Section R3 names seven policies and R3 ships four families. The three it does not ship are deferred
because their **inputs do not exist**, not because they are unimportant — and section 4.5 finding 5
is the evidence that they matter.

- **Score-based cache** (`docs/specs/align-llm.md` section 7.4) needs "router score" among its
  terms. `R2_ACTIVATION_TRACE` records the `ffn_moe_topk` node, which is `ggml_top_k`'s output: the
  expert **identities**, not the `ffn_moe_probs` weights. A score-based policy simulated without
  scores would be an arbitrary reweighting of frequency and recency presented under a name that
  implies more. The prerequisite is a trace that also captures `ffn_moe_weights-N`, which is an R2A
  schema extension (a `schema_version: 2` with a per-selection weight column) and is named here as
  R3's first follow-on.
- **Impact-driven prefetch** (section 7.5) prioritizes blocks whose *miss penalty* is largest.
  R3 has no penalty model: it counts bytes, and bytes are not a penalty until a bandwidth converts
  them. The prerequisite is R4.5's and R5's measured transfer costs.
- **CPU fallback** (section 7.3) chooses between transfer-and-GPU-compute and CPU-compute. That
  choice is explicitly "判断は実測microbenchmarkに基づく" and the microbenchmark is R5's. Simulating
  it against invented constants would produce a policy ranking that is a function of the constants.

Each is a named follow-on with a named prerequisite, and none is a `PROPOSED` Align request.

### 5.2 Decode-phase traces

Every trace this host can produce is one prefill graph
(`docs/specs/r2a-expert-trace.md` finding 7), and the instrument prints at most six token positions
per axis (finding 6). R3 replays prefill demands in decode order and says so; it does not claim a
decode measurement. R2c's minimal instrument patch — one graph evaluation per decode step reaching
the callback, and an untruncated `ffn_moe_topk` row — is the prerequisite, and it is the same
prerequisite R2's own gate carries forward. When it lands, R3's arm consumes the resulting traces
with no change: `graph_phases` already distinguishes the three R2A phase values, and a decode graph
is a one-token graph that the token-major order handles identically.

### 5.3 Time, bandwidth, and any performance claim

The document contains no seconds, no bandwidth, and no "faster". `bytes_fetched` is a count of bytes
that would cross a tier boundary under a policy, and converting it to a time needs the measured NVMe,
PCIe, and unified-memory numbers R4.5 and R5 own. `CLAUDE.md`'s performance row is therefore **not**
selected for this capability: there is no optimization claim, no baseline timing, and no benchmark.

### 5.4 Corpus stratification

Section R2's "language別偏り", "task別偏り", and "repo別偏り" each need a labelled corpus.
`eval/prompts/expert-locality-v1.txt` is 40 unlabelled lines that happen to span code, prose, and
several natural languages. Adding a label column and a per-stratum verdict is a corpus capability
that would consume R3's arm unchanged — the trace list would become several trace lists — and it is
not blocked by anything in this design.

### 5.5 `pooling: "reset"`

Per-document cache reset is a real question — it models a cold serving process per request — and
section 2.2.3's table is the reason it is a separate capability rather than a flag. Under reset the
episodes are too short to fill the cache at any interesting budget and the policies stop
discriminating, so a reset-mode document would need a different budget sweep, a different verdict
rule, and probably a longer-prompt corpus. Adding it as a second value of an existing field would
produce a document whose two halves are not comparable.

### 5.6 An ordered resident structure

Victim selection is a linear scan over the resident set, bounded by the cost guard of section 2.7.
The guard fires at `demand_count * resident_high_water > 2^32`; the real corpus is at 4.75 million,
three orders of magnitude inside it. A sorted or heap-ordered structure becomes necessary at roughly
a million-demand stream over a full 16,384-key space — which is a decode corpus of a large model, and
therefore the same moment section 5.2's prerequisite lands. Building it now would be optimizing a
measurement that finishes in milliseconds.

### 5.7 What R3 does not decide

R3 produces a number and a verdict. It does not choose the policy the runtime will implement, does
not write a residency configuration, and does not assign any expert to any tier. The decision that
consumes this document belongs to R5 and to `docs/specs/align-llm.md` section 6, and it should
consume the *curve* in `sweep_best` rather than the single `result`, because section 4.5 shows the
answer changes three times across the sweep.

### 5.8 A byte-optimal offline reference

`belady` is miss-optimal. The offline schedule that minimizes *bytes* on a model with unequal expert
sizes is a different object: weighted offline caching, where the furthest-next-use rule is not
optimal and the natural formulations are not a single backwards pass over a next-use column. R3 does
not compute it, so `headroom_per_mille` is measured against the miss-optimal reference and
`NO_HEADROOM` is conservative in one direction only (section 2.8).

Adding it is a real capability rather than a variant: it needs a second offline algorithm, a second
optimality argument, an independent oracle for it, and a second headroom field so the two references
stay distinguishable in the document. It is worth doing when a `NO_HEADROOM` row is about to stop
investment on a model whose `uniform_expert_bytes` is `false`; it is not worth doing to add a number
beside one that already answers the gate. Until then the document reports what it measured and says
which direction the error runs.

## 6. Correction ledger

The capability is now **implemented**. This section records every place where implementation and
measurement contradicted the plan above, what the shipped contract is, and the exact case that
closes it. Sections 1 to 5 remain authoritative except where a row below supersedes them; each row
names the superseded text. Cases without a runner prefix are cases inside
`scripts/run-residency-sim-smoke`.

| # | Superseded text | Shipped contract | Why | Case |
| --- | --- | --- | --- | --- |
| 1 | Section 2.5.4's "`graph_phases` carries R2A's three-valued `phase` forward unchanged" | The trace decode record declares `ordinal`, `n_tokens`, and `tokens_truncated`, and **recomputes** `phase` with `docs/specs/r2a-expert-trace.md` section 2.5.6's rule: `"prefill"` when `n_tokens > 1`, `"decode"` when `n_tokens == 1 && ordinal > 0`, `"single_token_first_graph"` when `n_tokens == 1 && ordinal == 0` | `Option<string>` cannot be read out of an array element at this pin — "reading a Move-type field `Option<string>` out of an array element is not supported yet" — and copying the whole element out is refused as well: "indexing an array of the Move type `TraceGraphRow` is not supported yet". `phase` is a total function of two fields R3 already decodes, so nothing is invented and no transcript is parsed. Section 7.5 item 2 | `sim-basic` (`graph_phases.prefill` 4), `sim-truncated` (1), `sim-multi-graph` (2), and the real run's `{"prefill": 40, "decode": 0, "single_token_first_graph": 0}` |
| 2 | Section 2.2.1's `R3_TRACE_DISAGREEMENT` row and section 2.6 step 8's code | **Withdrawn.** Every admitted trace is compared against the Model IR's `model.n_expert` and `model.n_expert_used`, so two *admitted* traces cannot disagree; a trace that would disagree fails `R3_SHAPE_MISMATCH` first, whatever the list order. The shipped code set is 31, after items 16 and 18 below added two | A code no fixture can reach is not a contract, exactly as `docs/specs/r2a-expert-trace.md` correction 7 established for `n_expert_source: "router_weight"` | `shape-mismatch`, which mixes an `n_expert = 8` trace with the `n_expert = 2` Model IR |
| 3 | Section 2.6 steps 5 and 8, "no document is read before its path is guarded", read as a size check | The **path** is guarded before the read, as stated; the **byte cap** (`R3_IR_TOO_LARGE`, `R3_TRACE_TOO_LARGE`) is enforced on the materialized document, because neither `fs.size` nor any metadata-only stat exists at this pin — the same absence `src/alignpack.align:1717` already records | Enforcing a cap before the read requires a surface Align does not ship. The oracle enforces it the same way so the two agree. Section 7.3 records that no fixture reaches either code | not closed by a case; section 7.3 |
| 4 | Section 2.8's "`sweep_best` applies the same rule at each budget entry" | `sweep_best` applies the **effect floor and the headroom rule** at each budget; the leave-one-document-out stability test runs at the **requested budget only** and is reported once, in `verdict.jackknife_*` | Section 2.7's cost bound is normative and explicit — "`180` replays plus `jackknife_folds * 2` more at the requested budget". Jackknifing all nine budgets would be 720 extra replays on the real corpus, four times the whole study, for a field the plan never gave a per-budget name | `sim-basic` (`jackknife_folds` 4 with eight `sweep_best` rows), `run-residency-sim` (40 folds, minimum gain 213 per mille) |
| 5 | Section 2.5.1's "every value derived before the failure is present and truthful", read as applying to `stream` | On `status: "error"` the `stream` object is **empty** — zero counts, empty arrays, `pooling: "continuing"` — and `budgets` and `orders` are `[]`. `inputs` and `model` still carry everything settled before the failure | Section 2.6's own rule is that "a trace that fails admission fails the whole run"; a stream pooled from the prefix of the corpus describes a sub-corpus nobody named, which is exactly the silent shrink that rule exists to prevent | every `error_case`, which asserts `stream.demand_count == 0` and empty `budgets`/`orders` |
| 6 | Section 2.2.2's packed-word field widths, which section 2.6 gives no code | New code **`R3_SELECTION_UNPACKABLE`**, in step 9: a graph ordinal at or above `MAX_GRAPHS`, a token index at or above `MAX_TOKENS`, a slot at or above `MAX_SLOTS`, or a layer at or above `MAX_LAYERS` cannot ride the 62-bit word. `error_detail` is the list ordinal | The widths were stated as a contract with no failure mode. `n_layer * n_expert <= MAX_RESIDENCY_KEYS` does **not** imply `n_layer < 256` — 16,384 layers of one expert satisfies it — so the guard is reachable and is not a redundant assertion | `selection-unpackable` (a slot of 128) |
| 7 | Section 2.5.5's "eight ascending entries" | Eight entries, **non-decreasing**: at fixture scale `total_expert_bytes >> 7` is below `largest_expert_bytes`, so several low points clamp to the same value and each reports `clamped: true` | De-duplicating would break the stated entry count and hide that the clamp fired more than once; keeping them makes the clamp visible as a plateau at the bottom of the sweep | `budget-clamp` (eight entries, `clamped: true` at index 0, ascending-or-equal asserted) |
| 8 | Section 2.5.2's `instrument_build_source` | The single value every admitted trace agrees on; `"mixed"` when two admitted traces disagree; `""` when no trace was admitted | Section 2.5.2 gave a disagreement rule for `instrument_builds` and none for its source. "Recorded, not rejected" is the same answer for both fields | the real run reports `absent`; `trace-unreadable` reports `""` |
| 9 | Section 2.5.2's `bytes_read` | The Model IR document plus every trace document actually read. The trace **list** is not counted | The section 2.5.2 example, `2675149`, is exactly `olmoe-ir.json` (1,191,817) plus the forty documents (1,483,332). The example was the contract | `run-residency-sim` reports `2673069` — the same forty documents at a different scratch path, the only host-dependent byte in them |
| 10 | Section 2.5.1's implicit whole-document form | The document carries **no trailing newline**. The three-operand form prints it plus one newline; the four-operand form writes it without one | `--model-ir` and `--expert-trace` both do this, and the two-form byte-identical requirement of section 2.3 is stated against those arms | every `check_case`, which asserts `stdout == file + "\n"` |
| 11 | Section 2.3's column-aligned summary block | The same labels in the same order, one value per line (`print(label)` then `print(value)`), and the two-part rows are printed as `traces: / N / of / M` | `docs/specs/r2a-expert-trace.md` correction 9 fixed this shape for the same reason: a value the inputs control must occupy exactly one line whatever bytes it carries | the smoke asserts the four-operand form opens with `residency sim:` |
| 12 | Section 2.5.1's "`error_detail` … a `(layer, expert)` pair" | The pair is rendered `"<layer>:<expert>"` | Schema 1 needs a form, not a description | `ir-expert-range` (`0:99`), `ir-expert-duplicate` (`0:0`), `expert-out-of-range` (`0:64`), `missing-expert-block` (`0:0`) |
| 13 | Section 2.3's "exit `0` on `status: "ok"`, `Err(Error.Invalid)` on `status: "error"`" | Unchanged in the arm; the **process exit for `Err(Error.Invalid)` is 2**, not 1, which is what the runtime maps it to and what every other arm already produces | The plan named the Align value, not the process status. Recording the observed number keeps the cases honest | every `error_case` and every arity case |
| 14 | Section 2.5.7's `best_policy` with no qualifying candidate | `best_policy` is the lowest-`bytes_fetched` candidate whenever that is strictly below the baseline, and `""` when no candidate is — the `—` of the section 4.5 table's 100-per-cent row. When the jackknife disqualifies the lowest-byte candidate and qualifies a later one, `best_policy` names the **qualifying** one, as section 2.8's `BEATS_BASELINE` row requires. Ties are broken by the section 2.4 row order | Section 2.5.7 gave the field no value for the two non-winning results, and section 4.5's own table needed one | `sim-no-headroom` (`best_policy: ""`, `result: "NO_HEADROOM"`); the real run's 100-per-cent sweep row |
| 15 | Section 3.1's single `replay` owner for the admission path | The eviction-and-insert block is written **twice inside `replay`**, once on the demand path and once on the prefetch path | A shared `admit` helper has to take the eight per-key tables as `borrow mut` parameters, and at this pin passing a local `array<i64>` as `borrow mut` to a function called inside a `loop` invalidates the caller's own later reads of it. Section 7.5 item 1 | `policy-oracle`: every `topk_prefetch` cell agrees with the oracle, whose admission is one function |

Items 16 to 23 are the review repairs. Each names the defect the review found, the shipped contract
that replaces it, and the case that closes it.

| # | Superseded text | Shipped contract | Why | Case |
| --- | --- | --- | --- | --- |
| 16 | Section 1.3's "A wrong `byte_size` in the Model IR is R1C's bug, not R3's to detect", read as licence to admit any integer | New code **`R3_EXPERT_BLOCK_SIZE`**, in step 6 after `R3_EXPERT_BLOCK_DUPLICATE`: an `ExpertBlock` whose `byte_size` is zero or negative is refused, `error_detail` the `(layer, expert)` pair. Residency is tested with `resident_pos[key] >= 0` throughout `replay`, never with `resident_size[key] > 0` | A zero-byte block is not a residency unit: it is admitted into every cache for free and can never be evicted for capacity, so under the old size-as-membership test it was never resident, missed on every demand, and was re-appended to `resident_list` on each one until the list overran its `key_space` and the process took `SIGABRT` ("index out of bounds: the len is 16 but the index is 16"). A negative `byte_size` collided with `sizes`' `-1` "no block declared" sentinel and was misreported as `R3_MISSING_EXPERT_BLOCK`. Both are refusals of the input, not of the simulator. The `resident_pos[key] >= 0` residency test is **defence-in-depth, not a second closure**: once `R3_EXPERT_BLOCK_SIZE` guarantees every admitted key's size is positive, `resident_size[key] > 0` and `resident_pos[key] >= 0` are equivalent, so this half of the correction rests on the same two cases as the input refusal rather than a case of its own | `ir-expert-size-zero` (`0:0`), `ir-expert-size-negative` (`0:0`) |
| 17 | Section 2.2.1's graph-exclusion rule, which named only `tokens_truncated` | The per-trace graph table carries three states — undeclared, declared and truncated, declared and replayed — and a selection naming a graph the document never declared, or one outside `[0, MAX_GRAPHS)`, fails **`R3_SELECTION_UNPACKABLE`** in step 9 with the list ordinal. Only a *declared* truncated graph is the silent, counted exclusion of section 2.2.1 | The old table conflated "excluded by the documented rule" with "never declared", so a selection naming an undeclared graph was dropped and counted by nothing: a 24-demand trace replayed 23 demands and reported `status: "ok"`. That is exactly the silent corpus shrink section 2.6's "a trace that fails admission fails the whole run" exists to prevent | `selection-undeclared-graph` (graph 7 in a one-graph document, detail `1`) |
| 18 | Section 2.7's caps, which bounded counts and never the byte totals they multiply into; and section 2.6 step 3's `R3_BUDGET_MALFORMED`, read as "overflow past `i64`" | One ceiling, **`MAX_BYTE_TOTAL = I64_MAX / 1000 = 9,223,372,036,854,775`**, applied at three guards. Step 3 rejects a `BUDGET_BYTES` operand above it as `R3_BUDGET_MALFORMED`. Step 6 accumulates `total_expert_bytes` under a non-wrapping test (`total > MAX_BYTE_TOTAL - size`) and reports new code **`R3_BYTE_TOTAL_OVERFLOW`** with the pair at which it would wrap. After step 10 and *before* the stream accounting, the same code refuses a run whose `demand_count + demand_count * n_layer * 8` exceeds `MAX_BYTE_TOTAL / largest_expert_bytes` — the loosest bound covering `demanded_byte_total` and every policy's `bytes_fetched`, `topk_prefetch_k8`'s per-boundary admissions included | Align's integer arithmetic wraps with no trap (module rule 5). Sixteen experts of 2^60 bytes made `total_expert_bytes` report `0`, `demanded_byte_total` report `0`, and the whole document arrive as a confident, internally consistent, entirely wrong measurement at `status: "ok"`. The ceiling is `I64_MAX / 1000` rather than `I64_MAX` because **every ratio in the document is an integer per mille**, so each of these totals is multiplied by 1000 before it is divided: bounding the totals once is what makes `per_mille`, the effect-floor comparison `best_bytes * 1000 <= baseline * (1000 - MARGIN)`, and every gain, headroom, and fold term non-wrapping without a guard at each site. The bound is deliberately loose: it refuses a run whose totals *could* wrap rather than measuring which ones do, and it is four orders of magnitude above the real model's 3,900,702,720-byte footprint | `ir-byte-total-overflow` (16 experts of 2^50 bytes, refused on the ninth block), `stream-byte-total-overflow` (4 experts of 2^47, whose 60 demands carry `demanded_byte_total` past the ceiling the four blocks alone do not reach), `budget-above-byte-ceiling` (`MAX_BYTE_TOTAL + 1`, which parses as an `i64` and is still refused) |
| 19 | Section 2.4's `topk_prefetch` rows, which specified what is admitted and not at what recency | A prefetched block enters as the **most recently used**, at the recency of the demand its token boundary precedes; ties among one boundary's admissions break by lowest packed key. Section 2.4 carries the contract | The shipped code inserted at `last_use = -1`, making every prefetched block the immediate next victim — under a full cache it was evicted by the very token position it was fetched for, so the policy could not hit by construction and `prefetch_useful` measured the insertion rule rather than the policy. Both insertions were evaluated. MRU insertion changes only the two `topk_prefetch_*` rows: on `sim-basic`'s requested budget, token-major `topk_prefetch_k1` moves from 6 to 7 hits of 96 demands with `prefetch_useful` 1 to 4, and `topk_prefetch_k8` from 4 to 3 hits with `prefetch_useful` 0 to 3 and 45 more prefetches issued (a prefetched block that survives its own boundary displaces one that would have been re-fetched). **No verdict, no sweep row, and no non-prefetch policy row changes**, in the fixture corpus or on the real 40-prompt corpus. Section 4.5 finding 4's "top-k prefetch is uniformly harmful" therefore stands, but as a claim **conditional on this insertion rule**, and section 7.4 records the re-measured numbers | `sim-prefetch-useless`, plus every `policy-oracle` cell — the oracle carries the identical rule |
| 20 | Correction 14's "when the jackknife disqualifies the lowest-byte candidate and qualifies a later one, `best_policy` names the **qualifying** one" — stated, not implemented | `decide` takes the qualifying candidate and its bytes from the jackknife loop and reports them; `best_policy`, `best_bytes_fetched`, and `gain_per_mille` all belong to that one policy. With no qualifying candidate the fields keep correction 14's non-winning behaviour, and the `sweep_best` rows are unchanged because they run no jackknife | The shipped `decide` recomputed the lowest-byte candidate and reported it beside `jackknife_stable: true`, so a `BEATS_BASELINE` document could name a policy that had **failed a fold** and attribute another policy's stability to it. Measured on the case fixture: the old code reported `recent_reuse_w8` at a 108-per-mille gain with `jackknife_stable: true`, while the 57-per-mille fold minimum it printed belonged to `lfu`; the repaired code reports `lfu` at 76 per mille with the same minimum | `jackknife-second-candidate`, which asserts that `best_policy` is not the lowest-byte candidate, that the lowest-byte candidate does clear the pooled floor, and that `best_bytes_fetched` belongs to `best_policy` |
| 21 | Section 2.6 step 9's `R3_SELECTION_TOO_MANY` | `MAX_DEMANDS` is tested **before** the element that would exceed it is appended, inside the per-document append loop, rather than after the whole document has been appended | A cap on what is allocated that is enforced after the allocation is a report, not a bound | not closed by a case; section 7.3, unchanged in reachability |
| 22 | Sections 1.2 and 4.3's `scripts/run-residency-sim-qualification` | The script is `scripts/run-residency-sim`; the `make` target keeps the name `residency-sim-qualification` | The plan named a file that was never written under that name. The target and the script are allowed to differ; a document naming a path that does not exist is not | `make gate-topology-check`, and `make residency-sim-qualification`, which would not run at all under the other name |
| 23 | Section 3.3's "opt-in through `ALIGN_LLM_GGUF_MODEL`, `ALIGN_LLM_LLAMA_EVAL_CALLBACK`, and `ALIGN_LLM_LOCALITY_PROMPTS` … `N/A` when any is absent" | The `N/A` rule is over the **two** variables that name the subject and have no default. `ALIGN_LLM_LOCALITY_PROMPTS`, `ALIGN_LLM_LOCALITY_PROMPT_COUNT`, and `ALIGN_LLM_RESIDENCY_BUDGET` have checked-in defaults and are overrides; a corpus that is named and missing is exit 1. Section 3.3's table lists all six variables including the smoke's `ALIGN_LLM_RESIDENCY_SIM_UPDATE_GOLDEN` | The script never behaved as section 3.3 described, and the difference matters in the direction that hides a failure: a broken checkout must not read as an absent subject | `make residency-sim-qualification` with no environment at all, which prints the `N/A` line for the instrument and exits 0 |
| 24 | Section 4.3's capture order, which generated a Model IR but did not validate it or the budget until after every prompt had invoked the instrument | Prompt count is validated in `[1, MAX_TRACE_PATHS]`; after Model IR generation and default-budget derivation, the wrapper runs the simulator against one deliberately absent trace and admits capture only on exact `R3_TRACE_UNREADABLE` step-8 evidence. Model and budget failures therefore precede instrument `--version` and prompt work | At the default 40 prompts and 600-second per-prompt timeout, a non-MoE model, malformed/too-small budget, or impossible prompt count could otherwise consume hours before the simulator reported an input defect already knowable without a transcript. Reusing the simulator keeps one validation owner and avoids a shell-side schema copy | `residency-sim-smoke`: `qualification-prompt-count`, `qualification-budget`, and `qualification-model` assert refusal with no fake-instrument invocation; `qualification-admission` asserts valid defaults reach `--version` and the first prompt |

**One finding, not a correction.** The jackknife gain of a fold can be negative when the candidate
loses on that fold, and Align's `/` truncates toward zero while Python's `//` floors. The oracle
therefore truncates toward zero explicitly. Every other ratio in the document has a non-negative
numerator, so this is the only place the two languages could have disagreed —
`budget-inserted` found it at `-90` against `-91`.

## 7. Verification record and unclosed cells

### 7.1 Shipped surface

| Path | Role |
| --- | --- |
| `src/residency_sim.align` | the trace-list reader, both document decoders, the demand-stream builder, the packed-key tables, all ten policies, the budget sweep, the jackknife, the verdict rule, the whole renderer, and every `R3_*` code |
| `src/main.align` | the `--simulate-residency` arm: arity, the path guard on all four operands, the summary block, exit mapping |
| `scripts/residency_oracle.py` | the independent Python implementation of sections 2.2 through 2.8; renders the whole document, and is written from this plan and never from `src/` |
| `scripts/run-residency-sim-smoke` | the narrow durable owner; `make residency-sim-smoke`, in `HOSTED_CHECK_TARGETS` |
| `scripts/run-residency-sim` | the opt-in focused qualification; `make residency-sim-qualification`, in no aggregate |
| `eval/fixtures/residency-sim/sim-basic.golden.json` | the checked-in golden: the whole `sim-basic` document with its **three** host-dependent values normalized — the two path operands and `inputs.bytes_read` — and the 1,440-entry per-layer breakdown pinned by SHA-256. `bytes_read` is normalized because an `R2_ACTIVATION_TRACE` records its own transcript `path`, so every trace document's length grows with the scratch directory's name: the same four-document corpus reports 38,335 B under a 107-character directory and 38,691 B under a 196-character one, and the golden must not pin a number that a longer scratch directory changes. It is still compared against the oracle on every case, which is where that accounting is owned (section 6, correction 9 measured the same effect between the probe and the qualification) |
| `eval/prompts/expert-locality-v1.txt` | the 40-prompt corpus the qualification captures, md5 `d7fff23f5a1d4f6237e6f848f3318d8b`, 877 B |
| `Makefile`, `scripts/check-gate-topology` | the two targets and both pinned aggregate lists |

**The prerequisite this branch once carried is now merged and is no longer part of this diff.**
Implementation began on top of R1C, which predates the R2 locality gate, and the corrected
`src/expert_trace.align` is required before a real OLMoE transcript converts at all: without it
every capture fails `R2_TOKEN_COUNT` on layer 15's token-reduced `ffn_moe_topk`. That module and its
owners — `scripts/eval_callback_fixture.py`, `scripts/run-expert-trace-smoke`,
`scripts/run-expert-trace-parity`, and `scripts/expert_locality_gate.py` — were therefore carried on
the branch verbatim from the R2 wave while it was unmerged. The branch is now rebased onto `main`
`35a0df6`, which contains the merged R2 wave (PR #131), the merged R1C frontend (PR #132), and the
merged MoE prerequisite discharge (PR #133), so those five paths come from `main` and the R3 diff
contains none of them. The qualification still depends on that correction; it is simply no longer
R3's to ship.

### 7.2 Cells closed by a case

Every applicable cell of section 3.1 maps to a passing case in `scripts/run-residency-sim-smoke`
except the rows of section 7.3.

Section 4.1's planned case list is now fully shipped. Five of its rows reached the hosted owner only
with the review repair, and three of those carry a different name than the plan gave them:
`sim-cyclic`, `sim-uniform-bytes`, and `sim-prefetch-useless` keep theirs; the plan's
`sim-jackknife-unstable` ships as **`jackknife-unstable`**, and section 3.1's `verdict-no-policy`
cell ships as a case of that name. `jackknife-second-candidate` is new, has no row in section 4.1,
and exists because correction 20 needed a case that separates the lowest-byte candidate from the
qualifying one.

| Section 3.1 cell | Case |
| --- | --- |
| Construction — trace list read, path guard, duplicate rejection | `list-empty`, `list-blank-line`, `list-blank-middle`, `list-duplicate`, `list-over-cap`, `list-path-too-long`, `list-unreadable` |
| Construction — Model IR decode into the subset record | `sim-basic`: the four-field `IrBlockRow` decodes a real-shaped `R1_MODEL_IR` whose blocks carry `index`, `tensor_count`, `first_absolute_offset`, `end_absolute_offset`, `contiguous`, and a nested `tensors` array, none of which the record declares |
| Formation/validation — steps 1–11, in order | one fixture per reachable code (27 of 31; the four unreachable ones are section 7.3's), plus `order-budget-before-list`, `order-list-before-ir`, `order-ir-before-budget-floor`. The three added by the review repair are `ir-expert-size-zero` / `ir-expert-size-negative` (`R3_EXPERT_BLOCK_SIZE`), `ir-byte-total-overflow` / `stream-byte-total-overflow` (`R3_BYTE_TOTAL_OVERFLOW`, at both guards), and `selection-undeclared-graph` (`R3_SELECTION_UNPACKABLE` on a graph no document declared) |
| Success — demand stream, both orders | `sim-basic`, `sim-multi-graph`, `sim-truncated`: `token_position_count`, `demand_count`, and both `orders[]` entries against the oracle, which sorts and pools independently |
| Success — each of the ten policies | `sim-basic`, `sim-mixed-bytes`, `sim-single-trace`, `budget-*`: hits, misses, bytes, prefetch counts, and `resident_key_high_water` for every policy at every sweep budget in both orders, against the oracle, with no tolerance |
| Success — budget sweep, clamp, requested-point merge | `budget-clamp` (eight entries, `clamped`), `budget-coincides` (eight entries), `budget-inserted` (nine, ascending) |
| Success — verdict, all three results | `sim-no-headroom` (`NO_HEADROOM`), `verdict-no-policy` (`NO_POLICY_BEATS_BASELINE` with no candidate below the baseline at all and headroom at or above the floor), `jackknife-second-candidate` (`BEATS_BASELINE`); `run-residency-sim` on the real corpus produces all three in one document, at six, two, and one sweep points |
| Success — jackknife | `sim-basic` and `sim-mixed-bytes` compare `jackknife_folds`, `jackknife_min_gain_per_mille`, and `jackknife_stable` against the oracle's own fold loop; `budget-inserted` exercises a negative fold gain; `jackknife-unstable` (five documents; a candidate clears the pooled floor, a fold takes it back, `jackknife_stable: false` and not `BEATS_BASELINE`); `jackknife-second-candidate` (the lowest-byte candidate fails a fold and a later, larger one passes, so `best_policy` is not the lowest-byte candidate — section 6, correction 20) |
| Success — the LRU cliff and the prefetch accounting | `sim-cyclic` (a six-key cyclic stream: `lru` hits exactly zero at every sweep budget below `one_token_working_set_bytes` and hits above it, while `lfu` and `belady` clear the cliff at the widest budget under it), `sim-prefetch-useless` (both prefetch degrees issue fetches, none is ever hit before eviction, and both fetch strictly more than `lru`), `sim-uniform-bytes` (a uniform size table makes every non-prefetch policy's bytes exactly its misses times the block size, so the hit and byte orderings are one ordering) |
| Failure — every code of section 2.6 | as above; `error_case` additionally asserts the partial document's `inputs` and `model` against the oracle |
| Malformed input | `ir-decode`, `ir-schema-kind`, `ir-schema-version`, `ir-status`, `trace-decode`, `trace-schema`, `trace-status`, `trace-not-moe` |
| Early exit — arity produces no output; the guard produces no read | four arity cases assert empty stdout and an untouched `OUT.json`; three path-guard cases assert empty stdout |
| Move-in/out — one decoded document at a time | by construction (`trace_load` returns columns and drops the decoded record), plus `inputs.bytes_read` accounted per document against the oracle |
| Cleanup — `OUT.json` written once and whole | the two-form identity assertion on every case; a failed render never reaches `fs.write_file` because the document is rendered before the arm writes |
| Bounded memory | `list-over-cap` (`MAX_TRACE_PATHS`), `ir-key-space` (`MAX_RESIDENCY_KEYS`); the other three caps are in section 7.3 |
| Both entrypoint forms | every `check_case` |
| Determinism | three runs of the whole smoke are byte-identical, and the sim-basic document is compared across three invocations inside it |
| `src/main.align` dispatch | `make gguf-smoke`, `make model-ir-smoke`, `make expert-trace-smoke` unchanged and passing |
| Fixture/oracle agreement | the oracle renders the whole document and every case compares it field for field |
| `Makefile` | `make gate-topology-check` with both pinned lists updated |

### 7.3 Cells not closed, with the reason

| Cell | Status | Reason |
| --- | --- | --- |
| `R3_IR_TOO_LARGE`, `R3_TRACE_TOO_LARGE` | **not closed by a case** | `MAX_DOCUMENT_BYTES` is 32 MiB, so each needs a 32 MiB fixture written and read twice per case — not a hosted-smoke cost for a guard that is two comparisons. Both are implemented and ordered before the decode, and correction 3 records that they fire after the read because Align ships no `fs.size` |
| `R3_SELECTION_TOO_MANY` | **not closed by a case** | `MAX_DEMANDS` is 262,144; the smallest trace document that reaches it is roughly 15 MB of JSON, and `src/expert_trace.align`'s own `MAX_SELECTIONS` binds first on any transcript this repository can produce. Correction 21 moved the test before the append it bounds; the reachability is unchanged |
| a byte-optimal offline reference | **deferred** | Section 5.8. `headroom_per_mille` is measured against `belady`, which is miss-optimal, so `NO_HEADROOM` is conservative in one direction only (section 2.8). The document states the direction rather than claiming a bound it did not compute |
| `R3_SIMULATION_COST` | **bounded by construction** | The guard fires at `demand_count * min(key_space, budget / smallest_expert_bytes) > 2^32`, and `MAX_DEMANDS * MAX_RESIDENCY_KEYS` is `2^18 * 2^14 = 2^32` exactly, so the two caps that *are* fixture-closed bind first everywhere except at both maxima simultaneously. The real corpus evaluates to `17280 * 275 = 4,752,000`, three orders of magnitude inside it |
| `pooling: "reset"` | **deferred** | Section 5.5, unchanged |
| `layer_major` bearing a verdict | **deferred** | Section 2.2.2 fixes it at `verdict_bearing: false`; the qualification prints the whole layer-major table beside the token-major one so the sensitivity is visible |
| an ordered resident structure | **deferred** | Section 5.6, unchanged. The whole 180-replay study plus 80 jackknife replays over the real corpus takes 1.8 s |
| `peak-allocation` | **closed indirectly** | Align at this pin exposes no resident-set measurement. The claim is carried by section 2.7's static bound and by `resident_key_high_water`, which the document reports per policy per budget and the oracle checks |

### 7.4 Commands and results

Host and environment as `docs/align-development.md` records for this machine: GNU make as `gmake`,
`LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib`.

Re-run in full after the review repair (section 6, items 16 to 23); every line below is that run.

```text
gmake check                     PASS   check-per-unit over 31 units, 2 m 40 s
gmake build                     PASS   four `huge struct copy` warnings from this module, all
                                       `docs/align-requests.md` Request 23's, none new
gmake fmt                       PASS   no diff, and idempotent: a second run leaves
                                       src/residency_sim.align byte-identical
gmake format-check              PASS
gmake gate-topology-check       PASS   both pinned lists updated
gmake residency-sim-smoke       PASS   2 synthetic Model IRs, 23 synthetic traces, 10 policies at
                                       8 or 9 budgets in 2 orders against the oracle, both CLI
                                       forms, the golden, determinism, 27 error codes, and CLI
                                       arity/isolation; three consecutive runs byte-identical, and
                                       the B1 self-check's explicit `mktemp -d <long>/tmp.XXXXXXXX`
                                       (68 -> 224 chars; a `TMPDIR` override cannot do this, since
                                       BSD `mktemp -d` on macOS ignores `TMPDIR`) still matches the
                                       checked-in golden apart from `inputs.bytes_read` (38,165 ->
                                       38,801, which the golden already normalizes away per
                                       section 6 correction 9) (section 7.1)
gmake expert-trace-smoke        PASS   98 fixtures, 17 error codes, the real build-10566 excerpt
gmake model-ir-smoke            PASS   49 qwen, 31 gpt-oss, 28 olmoe fixtures, 62 R0 fixtures
gmake gguf-smoke                PASS   unchanged
gmake residency-sim-qualification  MEASURED   the real 40-prompt corpus, three times; the
                                       documents are identical apart from the elapsed diagnostic;
                                       tables below
git diff --check                clean
```

`make ci` is selected for this capability and is the orchestrator's to run: section 3.3 predicted
it, and `residency-sim-smoke` joining `HOSTED_CHECK_TARGETS` is exactly the aggregate-membership
change `CLAUDE.md`'s verification rule names. No security, resource, race, fuzz, stress, platform,
mutation, or benchmark suite is selected: R3 adds no process, no thread, no socket, no subprocess,
and no timing claim.

**The qualification reproduces section 4.5's probe table cell for cell.** Same host, same
instrument (`version: 0.2.0 (build 10566, commit bb4caa754)`), same model
(`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`), same corpus (md5 `d7fff23f5a1d4f6237e6f848f3318d8b`,
877 B, 40 prompts), 55.7 to 64.1 s for 40 captures across three post-repair runs whose documents are
identical apart from that diagnostic, every transcript deleted after conversion, model size and
mtime unchanged. Stream: 40 admitted of 40 listed, 0 truncated graphs, 192 token positions,
17,280 demands, 938 distinct keys of 1,024, layers 0–14, slots `{0,1,2,5,6,7}` — 750 per mille
coverage — one token position demanding 90 experts and 341,213,184 bytes.

Token-major, continuing pooling. Each cell is `hit per mille over printed slots / gigabytes
fetched`:

| Budget | % | `null` | `compulsory` | `belady` | `lru` | `lfu` | `recent_w2` | `recent_w8` | `recent_w32` | `topk_k1` | `topk_k8` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30,474,240 | 0 | 0 / 65.5 | 945 / 3.6 | 69 / 61.0 | 0 / 65.5 | 25 / 63.8 | 1 / 65.4 | 12 / 64.7 | 24 / 63.9 | 0 / 76.4 | 0 / 152.3 |
| 60,948,480 | 1 | 0 / 65.5 | 945 / 3.6 | 139 / 56.3 | 0 / 65.5 | 59 / 61.6 | 6 / 65.1 | 44 / 62.6 | 56 / 61.8 | 3 / 76.1 | 0 / 152.3 |
| 121,896,960 | 3 | 0 / 65.5 | 945 / 3.6 | 260 / 48.5 | 0 / 65.5 | 121 / 57.6 | 33 / 63.3 | 112 / 58.2 | 125 / 57.3 | 17 / 74.2 | 0 / 152.3 |
| 243,793,920 | 6 | 0 / 65.5 | 945 / 3.6 | 409 / 38.7 | 0 / 65.5 | 226 / 50.7 | 103 / 58.7 | 210 / 51.7 | 229 / 50.5 | 34 / 71.0 | 0 / 152.3 |
| 487,587,840 | 12 | 0 / 65.5 | 945 / 3.6 | 580 / 27.6 | 247 / 49.3 | 376 / 40.8 | 247 / 49.2 | 335 / 43.5 | 360 / 41.9 | 264 / 51.2 | 234 / 107.8 |
| 975,175,680 | 25 | 0 / 65.5 | 945 / 3.6 | 782 / 14.3 | 488 / 33.5 | 602 / 26.1 | 488 / 33.5 | 520 / 31.4 | 603 / 26.0 | 492 / 34.1 | 533 / 43.2 |
| 1,950,351,360 | 50 | 0 / 65.5 | 945 / 3.6 | 904 / 6.2 | 812 / 12.3 | 812 / 12.2 | 812 / 12.3 | 812 / 12.3 | 807 / 12.6 | 812 / 12.4 | 811 / 13.5 |
| 3,900,702,720 | 100 | 0 / 65.5 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 |

Layer-major, reported beside it as the prefill-regime sensitivity and bearing no verdict. It
reproduces section 2.2.2's LRU row exactly — 330 per mille at 6 and 12 per cent against
token-major's 0 and 247, and 381 against 488 at 25 per cent:

| Budget | % | `belady` | `lru` | `lfu` | `recent_w2` | `recent_w8` | `recent_w32` | `topk_k1` | `topk_k8` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30,474,240 | 0 | 326 / 44.1 | 213 / 51.6 | 37 / 63.1 | 216 / 51.4 | 97 / 59.2 | 24 / 63.9 | 27 / 224.2 | 20 / 1356.7 |
| 60,948,480 | 1 | 351 / 42.5 | 322 / 44.4 | 71 / 60.8 | 322 / 44.4 | 238 / 49.9 | 62 / 61.4 | 54 / 219.7 | 46 / 1353.6 |
| 121,896,960 | 3 | 390 / 39.9 | 330 / 43.9 | 133 / 56.8 | 330 / 43.9 | 330 / 43.9 | 127 / 57.2 | 351 / 75.7 | 102 / 1346.1 |
| 243,793,920 | 6 | 465 / 35.0 | 330 / 43.9 | 236 / 50.0 | 330 / 43.9 | 330 / 43.9 | 329 / 43.9 | 355 / 53.5 | 201 / 1327.0 |
| 487,587,840 | 12 | 612 / 25.5 | 330 / 43.9 | 386 / 40.2 | 330 / 43.9 | 330 / 43.9 | 330 / 43.9 | 356 / 46.7 | 516 / 252.4 |
| 975,175,680 | 25 | 788 / 13.9 | 381 / 40.5 | 605 / 25.9 | 381 / 40.5 | 381 / 40.5 | 381 / 40.5 | 401 / 41.1 | 532 / 50.0 |
| 1,950,351,360 | 50 | 906 / 6.1 | 813 / 12.3 | 817 / 11.9 | 813 / 12.3 | 813 / 12.3 | 813 / 12.3 | 813 / 12.4 | 813 / 13.5 |
| 3,900,702,720 | 100 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 | 945 / 3.6 |

**Only the two `topk_prefetch_*` columns of both tables moved against section 4.5's probe**, and
they moved because section 2.4 now specifies MRU prefetch insertion (section 6, item 19). Every
`null`, `compulsory`, `belady`, `lru`, `lfu`, and `recent_reuse_*` cell in both orders is identical
to the probe's, as is every verdict, every `sweep_best` row, and the jackknife.

The verdict at the requested budget, and `sweep_best`:

```text
budget           975175680 byte(s)   (250 per mille of the expert footprint, 256 expert equivalents)
baseline         lru 33532231680 byte(s) fetched
best candidate   recent_reuse_w32 26033848320 byte(s) fetched
gain             223 per mille (floor 50)
headroom         574 per mille to the offline optimum
jackknife        40 fold(s), minimum gain 213 per mille, stable yes
result           BEATS_BASELINE
```

| Budget | % | Headroom | Best candidate | Gain | `result` |
| --- | --- | --- | --- | --- | --- |
| 30,474,240 | 0 | 68 | `lfu` | 25 | `NO_POLICY_BEATS_BASELINE` |
| 60,948,480 | 1 | 139 | `lfu` | 59 | `BEATS_BASELINE` |
| 121,896,960 | 3 | 259 | `recent_reuse_w32` | 124 | `BEATS_BASELINE` |
| 243,793,920 | 6 | 409 | `recent_reuse_w32` | 229 | `BEATS_BASELINE` |
| 487,587,840 | 12 | 440 | `lfu` | 171 | `BEATS_BASELINE` |
| 975,175,680 | 25 | 574 | `recent_reuse_w32` | 223 | `BEATS_BASELINE` |
| 1,950,351,360 | 50 | 493 | `lfu` | 2 | `NO_POLICY_BEATS_BASELINE` |
| 3,900,702,720 | 100 | 0 | — | 0 | `NO_HEADROOM` |

Prefetch accounting at the requested budget: `topk_prefetch_k1` issues 219 prefetches of which 102
are later hit before eviction (465 per mille), and `topk_prefetch_k8` issues 3,332 of which 1,590 are
(477 per mille). This is the one place the qualification does **not** reproduce section 4.5's probe,
and the reason is the shipped MRU insertion rule rather than the corpus: under the probe's
LRU-position insertion a prefetched block was the immediate next victim, so it could not be hit and
the same corpus reported 600 fetches with 2 useful and 6,355 with 0. The *investment* answer is
unchanged, because it is a byte answer: `topk_prefetch_k1` fetches 34.1 GB and `topk_prefetch_k8`
43.2 GB against `lru`'s 33.5 GB at this budget, and no `topk_prefetch` cell is below `lru` at any
budget in either order. Section 4.5 finding 4 is restated there accordingly.

**The roadmap section R3 gate is discharged.** At the requested hardware condition a policy more
effective than the baseline is identified numerically, with an effect floor and a stability test
stated before the measurement, and the answer is a curve rather than a point.

Three things differ from section 4.5's probe and each is explained rather than tolerated.
`inputs.bytes_read` is 2,673,069 here against the probe's 2,675,149, because the only host-dependent
bytes in an `R2_ACTIVATION_TRACE` are its `path` field and the probe's scratch directory was 52 bytes
longer per document — the same effect that made the golden's `bytes_read` unpinnable (section 7.1).
`inputs.instrument_builds` is `[]` with `instrument_build_source: "absent"` in both, which is the
ordinary case R2A finding 8 records. And the two `topk_prefetch_*` columns differ, for the MRU
insertion reason recorded above. **Every other hit rate, byte total, verdict, sweep row, and
jackknife bound is identical to the probe's.**

### 7.5 Align limitations met while implementing

Classified, not worked around. The register in `docs/align-requests.md` is the orchestrator's to
edit; this section is the client evidence.

1. **A local `array<i64>` passed as a `borrow mut` parameter is invalidated for every later read in
   the caller once the call sits inside a `loop`.** This is the single largest shape constraint on
   the module and it is a genuine gap, not a style preference. Reduced to three lines:

   ```text
   mut a := filled(4, 0)
   loop { if a[i] == 0 { touch(a, i) } ... }      // touch(borrow mut a: array<i64>, k: i64)
   ```

   fails with "use of invalidated borrow 'a': its source 'a' was moved or reassigned (or its storage
   was reallocated); create a new view from the current source" on the loop's own guard, on the
   assignment after the call, and on every read after the loop. The same call outside a loop is
   accepted. `borrow mut` of a **record** (`src/alignpack_read.align:335`'s `Counters`) and of a
   **`buffer`** both work inside loops, so the gap is specific to `array<T>`; and a record cannot
   substitute, because an `array<i64>` **field** of a record cannot be element-assigned at all —
   `s.table[i] = v` is "invalid assignment target" whether `s` is a local or a `borrow mut`
   parameter. The consequences are all through `src/residency_sim.align`: every helper returns owned
   columns inside a record instead of writing through out-parameters (`ReplayResult`, `BudgetSweep`,
   `IrLoad`, `TraceLoad`, `Verdict`), and correction 15's admission block is written twice.
   Non-blocking — the module is correct and bounded as written — and it is the shape a
   `borrow mut array<T>` parameter, or an element-assignable record field, would remove.
2. **`Option<string>` cannot be read out of an array element, and an array of a Move-type record
   cannot be indexed at all.** `d.graphs[at].phase` is "reading a Move-type field `Option<string>`
   out of an array element is not supported yet"; hoisting with `row := d.graphs[at]` is "indexing
   an array of the Move type `TraceGraphRow` is not supported yet (it would copy the element without
   transferring ownership)". `Option<i64>` in the same position is fine, so the gap is the Move
   payload rather than the `Option`. This is what forced correction 1. It is the fourth client of
   the same family as `docs/align-requests.md` Request 34's ok-payload restriction and is recorded
   here as client evidence, not as a new consumed surface.
3. **A field moved out of a decoded record is freed twice.** `build_source: document.run.build_source`
   compiles cleanly and then aborts the process at `free` with "pointer being freed was not
   allocated" when the decoded `TraceDocument` is dropped — SIGABRT, no message, and, because stdout
   is block-buffered, no output at all, so the failure looks like a hang at whatever the last
   flushed byte was. The fix is one `.clone()` through a `str` view. A partial move out of a record
   is either supported or rejected; being accepted by the checker and unsound at run time is the
   part worth recording.
4. **No `fs.size` and no metadata-only stat.** Correction 3. `src/alignpack.align:1717` already
   records the same absence beside `fs.open_ro`; R3 is the second client, and unlike R0 and R2A it
   does **not** need `fs.open_ro` — `fs.read_file` does not demand `O_RDWR`, so a qualification may
   read documents from a read-only artifact directory, which R2A's arm cannot.
5. **No `str`-to-number conversion** (Request 26). Second client, exactly as section 2.1 predicted:
   `BUDGET_BYTES` is a CLI operand and a `json.decode` detour would accept `-0`, `1e3`, and leading
   whitespace, none of which this operand admits. `parse_budget` is 15 lines with an explicit
   non-wrapping overflow guard.
6. **Huge-struct-copy warnings on `borrow` parameters** (Request 23). Sixth client, counting the
   register's own list:
   `residency_sim$Derived` (440 bytes) warns on the renderer's `borrow` parameter, and
   `residency_sim$ResidencySim` (200 bytes) and `residency_sim$TraceLoad` (184 bytes) warn on the
   returns that own them. Four sites, additional evidence, no status change.
7. **`json.decode` ignores undeclared members, at every nesting depth.** Not a gap — the shipped
   behaviour section 2.1 probed, confirmed on the real 1.19 MB `R1_MODEL_IR`: a four-field
   `IrBlockRow` decodes 1,058 blocks and never materializes the 3,219 nested tensor records, and the
   whole decode-plus-sum runs in 0.4 s. It is what makes this module simple, and it is recorded here
   so the next client can rely on it.

## 8. R3 decode residency measurement

Section 7.4 recorded the R3 gate discharged on a stream that section 5.2 named as its own first
limit: **prefill graphs only, six of eight router slots printed, replayed in decode order because
decode is the regime being modelled and not because decode was observed.**
[`r2c-decode-instrument.md`](r2c-decode-instrument.md) shipped the instrument that removes both
limits and [`r2a-expert-trace.md`](r2a-expert-trace.md) section 9 is its first measurement consumer.
This section records the residency measurement that follows.

It **adds** to section 7.4 and overwrites nothing there. Section 7's 223-per-mille
`recent_reuse_w32` win is the recorded result of *that* capability on *that* stream, and
`scripts/run-residency-sim` still refuses a full-axis document so it cannot be silently restated.
The capability that produced this section is **R3-DECODE-RESIDENCY**: no new CLI verb, no new
exchanged document, no Align source change, and no coordinated invariant, so it triggers no design
gate. It is one opt-in runner, one imported projection module, five cases and two binding checks in
the existing hosted owner, and this record.

### 8.1 Subject, corpus, and the three arms

```text
model      OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf (olmoe, 16 layers, n_expert 64, n_expert_used 8)
instrument llama-eval-callback, version: 0.2.0-dev (build 10566, commit bb4caa7), PATCHED
           r2c-v2 managed build, built with AppleClang 21.0.0.21000101 for Darwin arm64
corpus     eval/prompts/expert-locality-v1.txt
           40 prompts, md5 d7fff23f5a1d4f6237e6f848f3318d8b, 877 bytes
runner     scripts/run-decode-residency-gate
flags      -n 16 --temp 0 --seed 42 -t 4 -fa off -ctk f32 -ctv f32 -nr -c 512,
           one invocation per prompt — R2D's capture, flag for flag
admission  scripts/expert_locality_gate.py require_full_router_axes (R2D's rule, shared verbatim)
budget     975175680 B = 250 per mille of the 3,900,702,720 B expert footprint — section 7.4's point
```

The capture is R2D's: **40 prefill graphs and 640 decode graphs**, 16 of 16 requested steps for
every prompt, over 832 token positions. Every transcript is deleted immediately; the 40 documents
are the evidence.

**Three** trace lists are built from those 40 documents and each is replayed by
`main --simulate-residency` at the same budget:

| Arm | Trace list | Stream |
| --- | --- | --- |
| `mixed` | the documents as captured | 104,960 demands over 832 token positions, 1,024 of 1,024 distinct keys |
| `decode_only` | the same documents with graph 0 projected away | 81,920 demands over 640 token positions, 1,024 of 1,024 distinct keys |
| `prefill_only` | the same documents with every decode graph projected away | 23,040 demands over 192 token positions, 943 of 1,024 distinct keys |

**Why there is a third arm.** R2c changed *two* things at once against the stream section 7.4
recorded: the router axis went from six printed slots to all eight, and real decode graphs appeared.
The mixed and decode-only arms differ from that stream in both respects at once, so any verdict that
moved could be caused by either, and an earlier draft of this section attributed the movement to
decode without excluding coverage. The prefill-only arm is the **control**: same corpus, same
budget, same admission rule, same full eight-slot axis, and *only* the decode graphs removed. It
replays exactly what section 7.4 replayed, at the coverage section 7.4 could not print. A verdict it
shares with the other two arms is a coverage effect; a verdict it does not share is not.

Each list is a **projection for the simulator**, not a re-derived R2A document: exactly the two
arrays the simulator reads — `graphs` and `selections` — are filtered, and every other block
(`input`, `graph`, R2A's own `locality`) still describes the whole transcript. **The ordinals are
kept as captured**, so the sixteen one-token graphs stay `decode`; renumbering would make the first
of them a `single_token_first_graph` (section 2.5.6 of R2A) and `graph_phases` would stop being able
to state what was replayed. The simulator admits the projected forms unchanged — the removed graphs
become undeclared and no retained selection names them — and `sim-full-axis-decode`,
`sim-full-axis-decode-only`, and `sim-full-axis-prefill-only` in `scripts/run-residency-sim-smoke`
are the hosted proof of that, with no model and no instrument. The projections themselves live in
`scripts/residency_projection.py` and are **imported by both** the runner and that owner, so the
arms checked against the independent oracle are the arms replayed here. The runner asserts each
arm's `graph_phases` census and the partition `mixed = prefill_only + decode_only`, demand for
demand.

**What is different from section 7.4's stream.** Two things changed independently — slot coverage
and phase — and the rest follows from phase. Slot coverage is 1,000 per mille rather than 750, so no
rate is a printed subsample any more. Phase brings the other two: the mixed and decode-only streams
demand all sixteen layers rather than fifteen, because a one-token decode graph has no output-token
reduction and layer 15 is demanded for the first time in decode, and the mixed stream is 6.1×
longer, 104,960 demands against 17,280. **The prefill-only arm varies coverage and holds phase**: it
is section 7.4's own phase and corpus at 23,040 demands against 17,280 — the `8/6` slot ratio
exactly — over the same 192 token positions and the same fifteen layers, reaching 943 distinct keys
against 938.

**The one-token working set is a first-position quantity, and the labels matter.**
`one_token_working_set_keys`/`_bytes` are scanned over the pooled stream's *first* token position
only (`src/residency_sim.align`: the scan stops at the first demand whose token ordinal is not 0),
so each arm reports the working set of a token of whichever phase sorts first, not an average over
the arm:

| Position type | Arm(s) reporting it | Keys | Bytes | Budget as a multiple |
| --- | --- | --- | --- | --- |
| a prompt token, six printed slots (section 4.5) | section 7.4's stream | 90 | 341,213,184 | 2.86× |
| a prompt token, all eight slots | `mixed`, `prefill_only` | 120 = 15 × 8 | 454,950,912 | 2.14× |
| a generated token, all eight slots | `decode_only` | 128 = 16 × 8 | 487,587,840 | 2.00× |

The three rows are the same arithmetic at three axis widths: `15 × 6 = 90`, `15 × 8 = 120`, and
`16 × 8 = 128`. Fifteen rather than sixteen layers because the instrument reduces the prefill
graph's last layer token axis; a decode graph carries one token and has no such tail. Both the mixed and the prefill-only arm begin at a prompt token, so
**454,950,912 B is a prefill-position value in both**, and a decode position demands 487,587,840 B
in the mixed arm just as it does in the decode-only arm. The cache is therefore tighter than section
7.4's in every arm — but as section 8.3 shows, that tightening is **not** what decides the result.

Bounds are checked before the instrument runs and asserted before the replays: the decode half of
the capture is `40 × 16 × 16 × 8 = 81,920` demands against `MAX_DEMANDS` 262,144, the exact pooled
totals are 104,960, 81,920, and 23,040, and the section 2.7 cost product is 28,864,000, 22,528,000,
and 6,336,000 against `MAX_SIMULATION_STEPS` 2^32 at a resident bound of 275 keys.

### 8.2 Result at the requested budget

`token_major`, the verdict-bearing order, at 975,175,680 B. Bytes fetched, and hit per mille over
**every** router slot rather than over a printed subset:

| Policy | `mixed` bytes | GB | hit ‰ | `decode_only` bytes | GB | hit ‰ | `prefill_only` bytes | GB | hit ‰ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `null` | 399,406,792,704 | 399.4 | 0 | 312,056,217,600 | 312.1 | 0 | 87,350,575,104 | 87.4 | 0 |
| `compulsory` | 3,900,702,720 | 3.9 | 990 | 3,900,702,720 | 3.9 | 987 | 3,575,660,544 | 3.6 | 959 |
| `belady` | 92,438,200,320 | 92.4 | 769 | 70,931,496,960 | 70.9 | 773 | 19,825,950,720 | 19.8 | 774 |
| **`lru` (baseline)** | **176,661,381,120** | **176.7** | **558** | **134,615,285,760** | **134.6** | **569** | **44,349,947,904** | **44.3** | **492** |
| `lfu` | 203,681,808,384 | 203.7 | 491 | 160,290,471,936 | 160.3 | 487 | **35,730,898,944** | **35.7** | **592** |
| `recent_reuse_w2` | 176,661,381,120 | 176.7 | 558 | 134,615,285,760 | 134.6 | 569 | 44,349,947,904 | 44.3 | 492 |
| `recent_reuse_w8` | 181,278,081,024 | 181.3 | 546 | 140,051,152,896 | 140.1 | 551 | 41,153,101,824 | 41.2 | 529 |
| `recent_reuse_w32` | 183,905,255,424 | 183.9 | 540 | 145,546,985,472 | 145.5 | 534 | 35,873,488,896 | 35.9 | 590 |
| `topk_prefetch_k1` | 183,566,204,928 | 183.6 | 558 | 140,189,368,320 | 140.2 | 568 | 44,798,410,752 | 44.8 | 498 |
| `topk_prefetch_k8` | 291,705,962,496 | 291.7 | 539 | 223,084,412,928 | 223.1 | 552 | 59,583,627,264 | 59.6 | 508 |

The runner's own verdict blocks, pasted verbatim:

```text
  mixed
      baseline       lru 176661381120 byte(s) fetched
      best_policy    - 176661381120 byte(s) fetched (the lowest-byte candidate; it does NOT qualify)
      candidates clearing the pooled floor: none
      gain           0 per mille (floor 50)
      headroom       476 per mille to the offline optimum
      jackknife      NOT tested (no candidate cleared the pooled floor); 40 fold(s) available, minimum gain not measured, stable no
      result         NO_POLICY_BEATS_BASELINE

  decode-only
      baseline       lru 134615285760 byte(s) fetched
      best_policy    - 134615285760 byte(s) fetched (the lowest-byte candidate; it does NOT qualify)
      candidates clearing the pooled floor: none
      gain           0 per mille (floor 50)
      headroom       473 per mille to the offline optimum
      jackknife      NOT tested (no candidate cleared the pooled floor); 40 fold(s) available, minimum gain not measured, stable no
      result         NO_POLICY_BEATS_BASELINE

  prefill-only
      baseline       lru 44349947904 byte(s) fetched
      best_policy    lfu 35730898944 byte(s) fetched (the qualifying candidate)
      candidates clearing the pooled floor: lfu, recent_reuse_w8, recent_reuse_w32
      gain           194 per mille (floor 50)
      headroom       552 per mille to the offline optimum
      jackknife      tested; 40 fold(s) available, minimum gain 186 per mille, stable yes
      result         BEATS_BASELINE
```

**No candidate clears the 50-per-mille effect floor on the mixed or the decode-only arm, and none
even fetches fewer bytes than `lru`**, which is why `best_policy` is `""` there rather than a
named-but-disqualified row (correction 14). On those two arms the reported `jackknife 40 fold(s),
minimum gain 0` of the raw document is the **untested initial value, not a measured fold**: section
2.8 resamples only over candidates that clear the pooled floor, and there are none. The runner
prints `NOT tested` and emits `jackknife_tested=no` in its machine line so the two zeros cannot be
confused; `jackknife_folds` still reports how many folds the stream is partitioned into, which is a
property of the corpus and true either way.

**The prefill-only arm is `BEATS_BASELINE` at the very same budget**, with `lfu` 194 per mille below
`lru`, a jackknife that ran, and a minimum fold gain of 186 per mille — stable. `recent_reuse_w32`,
section 7.4's winner, clears the floor there too at 191 per mille and loses only the tie-break. That
single row is what the rest of this section turns on.

`recent_reuse_w2` is **byte-identical to `lru`** on all three arms, which is section 2.4's own
prediction for a two-position window made visible. The frequency policy changes sign **between
arms, not between capabilities**: `lfu` saves 194 per mille on prefill-only and loses 152 and 190
per mille on mixed and decode-only. Against section 7.4, where `lfu` fetched 26.1 GB to `lru`'s
33.5 GB — a 221-per-mille saving — the prefill-only arm's 194 per mille is the same finding at full
coverage, slightly smaller; the sign flip belongs entirely to the arms that contain decode.

### 8.3 The sweep — the gate is answered as a curve, and the curve moved

| Budget | share | `mixed` best | gain | `mixed` result | `decode_only` best | gain | `decode_only` result | `prefill_only` best | gain | `prefill_only` result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30,474,240 | 7‰ | `lfu` | 23 | `NO_POLICY` | `lfu` | 21 | `NO_POLICY` | `lfu` | 27 | `NO_POLICY` |
| 60,948,480 | 15‰ | `recent_reuse_w32` | 59 | **`BEATS`** | `recent_reuse_w32` | 59 | **`BEATS`** | `lfu` | 61 | **`BEATS`** |
| 121,896,960 | 31‰ | `recent_reuse_w32` | 137 | **`BEATS`** | `recent_reuse_w32` | 134 | **`BEATS`** | `recent_reuse_w32` | 106 | **`BEATS`** |
| 243,793,920 | 62‰ | `recent_reuse_w32` | 238 | **`BEATS`** | `recent_reuse_w8` | 232 | **`BEATS`** | `recent_reuse_w32` | 226 | **`BEATS`** |
| 487,587,840 | 125‰ | `recent_reuse_w32` | 59 | **`BEATS`** | `recent_reuse_w8` | 70 | **`BEATS`** | `lfu` | 78 | **`BEATS`** |
| **975,175,680** | **250‰** | — | 0 | `NO_POLICY` | — | 0 | `NO_POLICY` | **`lfu`** | **194** | **`BEATS`** |
| 1,950,351,360 | 500‰ | — | 0 | `NO_POLICY` | — | 0 | `NO_POLICY` | `recent_reuse_w8` | 0 | `NO_POLICY` |
| 3,900,702,720 | 1000‰ | — | 0 | `NO_HEADROOM` | — | 0 | `NO_HEADROOM` | — | 0 | `NO_HEADROOM` |

`NO_POLICY` and `BEATS` abbreviate `NO_POLICY_BEATS_BASELINE` and `BEATS_BASELINE`; the headroom
columns are omitted here and appear in section 8.2 and in the runner's output. The share column is
the document's own `per_mille_of_expert_bytes` — the 125-per-mille row is **12.5 per cent**, not the
12 per cent an earlier draft of this section rounded it to.

**The R3 gate is met in the decode direction, and its answer is narrower than section 7.4's.** On
the two arms that contain decode, a policy more effective than the baseline is identified at
1.5, 3.1, 6.2, and 12.5 per cent of the expert footprint — `recent_reuse`, peaking at 238 per mille
on the mixed arm — but the win is confined to those budgets, and at section 7.4's own 25-per-cent
operating point it is gone on both. The mixed and decode-only arms agree on every verdict at every
budget, so that answer is not an artefact of pooling the prompt with its generation.

**The mechanism is decode, and the control arm is what establishes it.** An earlier draft of this
section attributed the loss to the tighter cache — the one-token working set grew from 341 MB to
455–488 MB, so the fixed 25-per-cent budget fell from 2.86 working sets to 2.0–2.1 — and that
explanation is now **measured and rejected**. The prefill-only arm sits at 2.14 working sets, within
seven per cent of the mixed arm's own prefill positions and *tighter* than section 7.4's 2.86, and
it is `BEATS_BASELINE` at 194 per mille with a stable jackknife. Slot coverage is likewise excluded:
the prefill-only arm prints all eight slots, the axis change section 7.4 could not make, and the win
survives it — 223 per mille at six slots, 194 per mille at eight. **What removes the win is the
presence of decode demands in the stream, and nothing else this measurement varied.**

The byte table says what decode does to the policies. `lru` is *better* on decode, not worse: it
hits 569 per mille on the decode-only arm and 492 on prefill-only, because a generated token
re-demands the same sixteen-layer working set every step. `lfu` is *worse*: 487 per mille on decode
against 592 on prefill. Frequency has less to exploit because decode's expert distribution is more
uniform — measured independently in `r2a-expert-trace.md` section 9.2 as entropy 996 against
prefill's 992 per mille, top-8 mass 163 against 179, and all 64 experts used. The baseline rises to
meet the offline optimum's reachable band and every candidate falls behind it.

**One confound is not separated and is not claimed away.** Removing the decode graphs also shortens
the stream, 104,960 demands to 23,040 over 192 rather than 832 token positions, so the prefill-only
arm carries less cross-prompt cache pressure as well as no decode. This measurement establishes that
**coverage** is not the cause; it does not separate *decode's routing statistics* from *the longer
stream decode produces*. Both are properties of real generation and both are absent from section
7.4's corpus, so the practical conclusion is unchanged, but a claim about routing statistics alone
would need a length-matched arm this capability does not build.

**The headroom does not go away, and that is the finding worth acting on.** At 25 per cent, 476 and
473 per mille of the baseline's bytes are still recoverable by the offline optimum on the two decode
arms and **no online candidate in the set captures any of them**; at 50 per cent the headroom is
larger still, 593 and 583 per mille, and again no candidate takes it — including on the prefill-only
arm, which wins at 25 per cent and then also reaches `NO_POLICY_BEATS_BASELINE` at 50. Section 4.5
finding 5 measured the same shape with 223 per mille captured; on a stream containing decode the
captured fraction is zero. This is direct evidence **for** section 5.1's score-based and
impact-driven work — the inputs those policies need do not exist yet, and this is now the strongest
single argument for adding them — and against spending further effort on more recency/frequency
variants at this operating point.

`topk_prefetch` is unchanged as an investment answer, for the third time and now on decode data, and
on all three arms: it buys no bytes at either degree, `k=1` fetching 4 per cent more than `lru` on
the mixed arm for the same hit rate and `k=8` fetching 65 per cent more, and losing 10 and 343 per
mille even on the prefill-only arm where a frequency policy wins.

### 8.4 What this measurement does and does not license

- **It does not rewrite section 7.4 — it corroborates it.** That result stands as the recorded
  measurement of the prefill-only, six-slot stream, and `scripts/run-residency-sim` still enforces
  `require_compact_router_axes` so the two corpora can never be pooled under one capability name.
  The `prefill_only` arm here is the nearest thing to a replication that a different admission rule
  allows: the same corpus and the same phase at eight printed slots instead of six, and it reaches
  the same verdict — `BEATS_BASELINE`, 194 per mille against 223, with `recent_reuse_w32` still
  clearing the floor at 191. **Section 7.4's win was not an artefact of the six-slot subsample.**
- **The 25-per-cent point is an inapplicable operating point for the decode arms, not a failed
  gate.** `NO_POLICY_BEATS_BASELINE` is one of section 2.8's three legitimate results and the gate
  question is answered as a curve; the mixed and decode-only arms identify a better policy at four
  of the eight sweep budgets. Nothing here is recorded as `NOT MET`.
- **The coverage confound is excluded; a length confound is not.** Section 8.3 states both. The
  prefill-only arm holds coverage, corpus, budget, and admission fixed and still wins, so the loss
  belongs to decode; but decode also lengthens the stream 4.3×, and this measurement does not
  separate decode's routing statistics from that length.
- **It is one continuation per prompt.** Greedy decode (`--temp 0 --seed 42`), 16 steps, `-c 512`,
  prompts of at most six tokens. A sampled continuation may route differently and nothing here
  measures that.
- **Cross-prompt reuse still carries part of the pressure in every arm.** The pooled stream is
  `pooling: "continuing"` (section 2.2.3) and the decode-only arm still pools 40 generations into
  one cache. It is a session of short requests measured on generated tokens, not a single long
  generation.
- **Layer 15 is a compulsory miss the prefill capture never charged.** The instrument reduces the
  prefill graph's last layer token axis, so on this stream layer 15 is first demanded in decode: the
  prefill-only arm demands fifteen layers and 943 keys, the other two sixteen and 1,024. That is an
  instrument property, reported through `layers_demanded`.
- **`one_token_working_set_*` is a first-position quantity.** It is the working set of the pooled
  stream's first token position, whose phase differs by arm (section 8.1's table). It is never an
  average over an arm, and the two values must not be read as a range across arms.
- **`headroom_per_mille` is still measured against a miss-optimal reference** (sections 2.8 and
  5.8), so the 476 and 473 per mille are conservative in one direction only. Since they are being read
  here as an argument *for* investment rather than against it, that direction is the safe one.
- **The sweep rows carry no jackknife.** Section 2.8 resamples at the requested budget only, so
  every `BEATS_BASELINE` in section 8.3's sweep table has cleared the pooled 50-per-mille effect
  floor and nothing more. Only the 25-per-cent row of the prefill-only arm is jackknife-tested, and
  it is stable at a 186-per-mille minimum.
- **No time, no bandwidth, no throughput claim.** Bytes only, as section 5.3 requires. The elapsed
  219.4 s for 40 captures is a load-dependent diagnostic: the same capture was taken three times on
  this host in one session at 509.4 s, 261.0 s, and 219.4 s, the first with other checks running
  concurrently. **Every other recorded number is byte-identical across the three runs.** Nothing
  rests on the elapsed.

### 8.5 Verification

Host and environment as section 7.4 records: GNU make as `gmake`,
`LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib`,
managed Align `3a34febe` toolchain.

```text
scripts/run-decode-residency-gate  MEASURED, exit 0. mixed and decode-only
                                   NO_POLICY_BEATS_BASELINE at the requested budget and
                                   BEATS_BASELINE at 15/31/62/125 per mille; prefill-only
                                   BEATS_BASELINE at the requested budget, lfu 194 per mille,
                                   jackknife stable at a 186-per-mille minimum. 219.4 s for 40
                                   captures (sections 8.2 and 8.3). Run three times on this host,
                                   the last at this exact head: every line of output is identical
                                   across the runs except `elapsed`, which was 509.4 s under
                                   concurrent load, then 261.0 s, then 219.4 s
gmake residency-sim-smoke          PASS, 2 model IRs, 27 traces, every policy at every sweep budget
                                   against the independent oracle, both CLI forms, the golden,
                                   determinism, the section 2.6 error corpus, and the five new
                                   cases and two binding checks; 6 of 6 mutants killed
gmake expert-trace-smoke           PASS, 108 fixtures / 17 error codes, both aggregators
gmake build                        PASS
gmake format-check                 PASS
gmake gate-topology-check          PASS, no aggregate membership changed
git diff --check                   clean
```

`gmake expert-trace-smoke` is run because the repair touches `scripts/run-decode-locality-gate` —
one behaviour-neutral `hashlib.md5(..., usedforsecurity=False)` keyword required by the new
`capture-identity` check, which compares that runner's corpus-identity block with this one's. The
digest is unchanged, and the corpus identity both runners print for the checked-in corpus was
compared before and after the change and is byte-identical:
`expert-locality-v1.txt d7fff23f5a1d4f6237e6f848f3318d8b 877 40`. That runner's own measurement
(`r2a-expert-trace.md` section 9) is therefore not restated and was not re-run.

`residency-sim-smoke` is **not python-only** — it needs the built `main` for `--model-ir`,
`--expert-trace`, and `--simulate-residency` — so it was not run under a read-only
`python:3.12-slim` container; the Align toolchain and a Linux build of the product are its
prerequisites, and hosted CI already owns that graph.

Five cases and two binding checks were added to `scripts/run-residency-sim-smoke`. None touches the
existing golden or `scripts/residency_oracle.py`.

| Case | Shape | Required |
| --- | --- | --- |
| `sim-full-axis-decode` | four documents, each a 4-token prefill graph followed by five one-token decode graphs at ordinals 1–5, from a `ScriptedRouter` whose selection is a table over the real sequence position | the whole document against the oracle with zero tolerance; `graph_phases` `{prefill: 4, decode: 20, single_token_first_graph: 0}`; 36 token positions; slot coverage 1,000 per mille; a repeated run reproduces `normalized()` exactly, per-layer digest included |
| `sim-full-axis-decode-only` | the same four documents with graph 0 projected away and the ordinals kept | the simulator admits the projection; `graph_phases` `{prefill: 0, decode: 20, ...}`; 20 token positions |
| `sim-full-axis-prefill-only` | the same four documents with every decode graph projected away — the runner's coverage control arm | the simulator admits the projection; `graph_phases` `{prefill: 4, decode: 0, ...}`; 16 token positions |
| `full-axis-admission` | one compact and one full-axis `R2_ACTIVATION_TRACE` at `n_expert_used` 8, both derived by `main --expert-trace` from rendered transcripts | the compact document carries exactly slots `{0,1,2,5,6,7}` with `slots_truncated` true and the full one carries `0..7` with it false; `require_compact_router_axes` admits the first and refuses the second with *full-axis R2c input refused*; `require_full_router_axes` is the exact mirror; and the two runners still bind to their own rule and to neither the other's |
| `projection-binding` | the runner's source | `scripts/run-decode-residency-gate` imports `scripts/residency_projection.py`, drives its arms through `PROJECTIONS[arm]`, defines no projection of its own, and names all three arms — so the arms this file proves against the oracle are the arms the real-model runner replays |
| `capture-identity` | both decode runners' sources | the instrument invocation, the corpus-identity block, and the transcript size cap are extracted from `scripts/run-decode-locality-gate` and `scripts/run-decode-residency-gate` and must be equal, and the extracted invocation must still contain each of the eight contractual flags, so the comparison cannot pass vacuously |
| `sim-renumbered-decode-only` | the decode-only documents with their ordinals renumbered to `0..n-1` — the list the projection deliberately does **not** build | the same demand count as the decode-only arm and a *different* phase census, `{prefill: 0, decode: 16, single_token_first_graph: 4}`, so the design's "keeping the ordinals is the point" is executable rather than prose, and the other three arms' `single_token_first_graph: 0` is an assertion rather than an unreachable branch |

The prefill and decode step counts differ (4 and 5) so that the three arms carry three different
token-position counts: with equal counts a projection that selected the wrong graphs but the right
number of them would satisfy the separation assertions. The three arms are further required to have
three distinct `lru` byte totals on both orders, and the two projections must partition the capture
exactly — `mixed` demands equal `prefill_only` plus `decode_only`.

The two `sim-full-axis-decode` arms assert that a candidate clears the pooled effect floor and that
`jackknife_min_gain_per_mille` differs from `gain_per_mille`, so the jackknife is doing work on the
fixture rather than being trivially satisfied. `sim-full-axis-prefill-only` deliberately does not:
whether one of its 96 demands clears the pooled floor is a property of the fixture's router table
rather than of the simulator, and the other two arms already pin the resampling path.

Six mutations were each applied to a pristine copy of `scripts/residency_oracle.py` or
`scripts/residency_projection.py` and run against the whole smoke, restoring the file from Git
between mutants:

| Mutation | Target | Result | Killed by |
| --- | --- | --- | --- |
| the per-document demand sort loses its graph term, `(graph, token, layer, slot)` → `(token, layer, slot)` | oracle | **KILLED** | `sim-full-axis-decode`, `sim-full-axis-decode-only`, `sim-renumbered-decode-only`, `sim-multi-graph` |
| a `decode`-phase graph is treated as excluded, so decode demands never reach the stream | oracle | **KILLED** | the three decode cases — **and nothing else in the file**, because every other case replays prefill graphs only |
| the jackknife stops resampling: the fold loop runs once over the whole stream | oracle | **KILLED** | all four full-axis cases, `jackknife-unstable`, `jackknife-second-candidate`, and six more |
| `phase_of` never reports `single_token_first_graph`: a one-token graph at ordinal 0 is labelled `prefill` | oracle | **KILLED** | `sim-renumbered-decode-only` — **and nothing else in the file**. Before that case was added this mutant **survived**, which means the three arms' `single_token_first_graph: 0` was being satisfied by an unreachable branch rather than asserted |
| `project_prefill_only` becomes the identity projection | projection | **KILLED** | `sim-full-axis-prefill-only`, `sim-full-axis-decode` |
| `project_decode_only` drops ordinal 1 instead of ordinal 0 | projection | **KILLED** | `sim-full-axis-decode-only`, `sim-renumbered-decode-only`, `sim-full-axis-decode` |

The unmutated smoke passes, and `scripts/residency_oracle.py` and
`eval/fixtures/residency-sim/sim-basic.golden.json` are byte-unchanged in the candidate.
