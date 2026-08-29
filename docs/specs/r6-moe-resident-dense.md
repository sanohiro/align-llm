# R6-MOE-RESIDENT-DENSE: the dense third of a routed decode step, held resident

Status: **design, written and committed before implementation.** Branch
`agent/r6-moe-resident-dense`, stacked on `agent/r6-olmoe-decode` head `bf7c87d`, which is
publishing as roadmap item 32. This branch takes `git merge origin/main` — **never a rebase** — when
that lands, and re-checks the same four things `HANDOFF.md` already records: the roadmap item
number, the document schema number, the next free Align request number, and which goldens
regenerate.

**This document's sections 1 to 6 are committed before the first line of implementation, and that
ordering is a fact about the repository rather than a claim in a document.**
`docs/specs/r6-resident-weights.md`'s preamble records why that matters: its own sections 1 to 4
were written first but its first commit *was* the implementation commit, so nothing in Git
distinguished a ceiling recorded in advance from one written to fit a result. It named the
correction it owed its successor — "**the next Track B performance capability commits its sections 1
to 4 before the first line of implementation**" — and this is that capability. The cost ceiling in
section 3.7, the baseline it is taken against, and the shipping floor it must clear are in the
commit that precedes the `feat` commit.

Sections 1 to 6 will not be edited after implementation. A row implementation moves is marked in
place with a bolded `Shipped:` note, exactly as `r6-resident-weights.md` does, and the deviations
get their own section.

## 1. Decision and boundary

### 1.1 What this capability is

`R6-OLMOE-DECODE` (item 32, `docs/specs/r6-olmoe-decode.md`) measured what a routed decode step
reads. Its section 12.3 is the whole motivation and every number below is calibrated against it:

| Term | Bytes per decode step | Share |
| --- | --- | --- |
| Expert planes, the top-8 claims in all sixteen layers | 487,587,840 | 658,320 ppm |
| Dense layer weights, sixteen layers | 168,558,592 | 227,578 ppm |
| The output head | 84,518,912 | 114,101 ppm |
| One embedding row | 1,152 | 2 ppm |
| **Total** | **740,666,496** | 1,000,000 ppm |

The four shares are rounded to the nearest ppm and therefore sum to 1,000,001; the bytes are exact
and are what the claim is made on.

Two thirds of that is the routing decision and it is the quantity item 32 exists to publish. **One
third of it is re-read weights the previous step already read**, and it is the same 253,078,656 B on
every step of every prompt, because the dense half of a routed model does not depend on the routing.

This capability removes that third. It makes the **dense** members of the pack — the embedding
table, the sixteen layers' attention and norm and router weights, and the output head — resident for
the lifetime of one process, so that after one fill every decode step reads **exactly zero dense
bytes**, while the expert planes keep streaming and `steps[i].residency.expert_bytes` stays
**487,587,840 B on every step, unchanged to the byte**.

**The measurement survives, and that is the point.** `docs/specs/r6-olmoe-decode.md` section 3.9
excluded residency because "an arm that is both resident and measuring reads zero and has measured
nothing". That is true of *whole-model* residency and false of this one: the claim reads and the
dense reads are two disjoint counters through two disjoint code paths — `timings.claim_pread_ns` and
`residency.expert_pread_bytes` are accumulated across `read_block_scatter` calls and nothing else
(item 32 section 3.11), and the dense reads are `fill_members`/`read_into_window` on the dense
window. Zeroing the second cannot move the first, and section 4.4 makes that an asserted invariant
rather than an argument.

**The headline is how little it needs, and how much smaller it is than the dense arm's.**

| Needed by dense residency | State |
| --- | --- |
| A new ggml symbol or shim entry point | **None.** `align_ggml_buffer_from_host` and `align_ggml_slot_place` already place weight tensors at interior offsets of an Align-owned `buffer`, and `R6-RESIDENT-WEIGHTS` cell RW-P1 measured that one wrap accepts tensors from many contexts |
| A new Align language surface | **None.** Section 9 records six continuing gaps; none blocks |
| A larger `buffer` than the pin allows | **No.** The arena is **311,066,624 B** (section 2.2) — 6.6 % of the dense arm's 4,677,533,696 B, and smaller than the claim window plus the plane this arm already reserves |
| A physical-memory preflight and a 12 GiB refusal | **No, and section 3.9 is the whole answer.** Peak footprint grows from 347,451,392 B to 573,997,056 B. A host that runs the streamed arm runs this one |
| A change to the KV plane, the claim window, the node tables, the slot numbering, or the op set | **None** |
| `model_forward.plan_resident` called as it stands | **No, and this is the one real piece of work.** Section 3.5 |

### 1.2 Why a design gate is triggered

Three of the gate's four triggers fire.

- **A changed public CLI surface.** `--moe-decode-step` gains its reserved fourteenth operand and
  its arity set changes from `{5, 6, 7, 9, 10, 11}` to `{5, 6, 7, 9, 10, 11, 14}`.
- **A changed exchanged format.** The `R6_MOE_DECODE_STEP` document goes to **schema 2**: a
  `weights` object is added, and item 32 section 3.10 recorded that object as deliberately
  **absent** — "publishing an object that is always `-` is a field pretending to be a promise". A
  field that was absent by contract becoming present by contract is a format change and is named.
- **A changed ownership/allocation boundary.** The dense window's `buffer`, its per-graph
  `ggml_backend_buffer` wrap, and one lifetime per graph become **one arena at run scope with one
  wrap**, across the `(2 · n_layer + 2) · (1 + N)` graphs the arm counts — **578** at `N = 16` —
  while the **claim window keeps its per-graph wrap unchanged**. Section 3.4 decides one wrap
  against two and section 4.3
  re-establishes the balance invariant at the scope the hoist moves it to.

The fourth trigger — a coordinated invariant across three or more modules — **also fires**, and
unlike item 32 it fires for a boring reason rather than an interesting one: the arena's layout is
computed in `src/model_forward.align`, consumed in `src/moe_model_forward.align`, owned in
`src/moe_decode_step.align`, and must not move `src/decode_step.align`'s meaning of the same shared
code. Four modules must agree on one layout. A closure matrix is built in section 5.

### 1.3 Declared boundary

**In scope.** OLMoE-1B-7B-0125-Instruct Q4_K_M; **CPU only**; the `--moe-decode-step` arm; one
process; the **dense** member set resident from before prefill until the process's own teardown,
filled once, never evicted, never invalidated, never persisted; an explicit budget refusal.

**Out of scope, declared non-goals.**

- **Expert residency, partial or total.** The value `weights` is refused on this arm by name
  (section 3.2). Whole-model residency makes the demand stream zero, and *partial* expert residency
  is a policy whose input is item 32's `steps[].routed` curve; it is the next capability and it is
  not this one. Section 8 defers it with its operand value named.
- **The dense `--decode-step` arm.** `src/decode_step.align` is **byte-unchanged**. Section 5.4 is
  the cell that says so with a regression rather than a sentence.
- **`--moe-layer-forward` and `--moe-model-forward`.** They read the pack once, so the ceiling in
  section 3.7 does not clear the floor for them. Deferred, section 8, with that reason.
- **KV persistence on this arm.** Item 32 section 8 defers it on two exact couplings. This
  capability's arity 14 requires `-` in the two reserved KV positions and refuses anything else
  (section 3.2), which is how a reserved position stays reserved instead of quietly becoming legal.
- **The Metal arm**, eviction, tiering, prefetch, NVMe or GPU residency, a cross-process weight
  cache, a growing pack, a second pack in one process, and reuse of the arena across two
  invocations.
- **Any tokens-per-second or TTFT claim.** This document makes a **bytes-read** claim and a bounded
  **elapsed** claim on one prompt on one host. Section 3.7 states both exactly. The R6 roadmap gate
  — TTFT on repeated coding tasks *sharing a prefix* — stays **unmet**; this capability shares no
  prefix and keys no lookup.

## 2. The dense set, enumerated

Nothing here is asserted. Every figure is read out of the pack document
`model.alignpack`'s own member table for
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, `block_align` 4,096, 1,058 blocks, 3,219 members,
`total_bytes` 4,212,193,280, and is reproduced by the runner in section 5.6 by an independent walk
of that table.

### 2.1 What "dense" covers, member by member

The pack has four block kinds. **Dense is exactly "not an `ExpertBlock`"**, which is 147 members of
the 3,219 and 34 blocks of the 1,058.

| Block kind | Blocks | Members | Roles | Bytes |
| --- | --- | --- | --- | --- |
| `WeightBlock` 0 | 1 | 1 | `token_embd` | 57,950,208 |
| `AttentionBlock` | 16 | 112 | `attn_norm`, `attn_q`, `attn_q_norm`, `attn_k`, `attn_k_norm`, `attn_v`, `attn_output` | 160,038,912 |
| `RouterBlock` | 16 | 32 | `ffn_norm`, `router` | 8,519,680 |
| `WeightBlock` 1057 | 1 | 2 | `output_norm`, `output` | 84,518,912 |
| **dense total** | **34** | **147** | | **311,027,712** |
| `ExpertBlock` | 1,024 | 3,072 | `ffn_gate_exps`, `ffn_up_exps`, `ffn_down_exps` | 3,900,702,720 |
| **pack payload** | **1,058** | **3,219** | | **4,211,730,432** |

Per member, with the `ggml_type` and shape the member table records:

| Role | Count | `ggml_type` | Dims | Bytes each | Bytes total |
| --- | --- | --- | --- | --- | --- |
| `token_embd` | 1 | 12 (Q4_K) | 2048 × 50304 | 57,950,208 | 57,950,208 |
| `attn_norm` | 16 | 0 (F32) | 2048 | 8,192 | 131,072 |
| `attn_q` | 16 | 12 (Q4_K) | 2048 × 2048 | 2,359,296 | 37,748,736 |
| `attn_q_norm` | 16 | 0 (F32) | 2048 | 8,192 | 131,072 |
| `attn_k` | 16 | 12 (Q4_K) | 2048 × 2048 | 2,359,296 | 37,748,736 |
| `attn_k_norm` | 16 | 0 (F32) | 2048 | 8,192 | 131,072 |
| `attn_v` | 16 | **12 and 14** (Q4_K, Q6_K) | 2048 × 2048 | 2,359,296 **or** 3,440,640 | 46,399,488 |
| `attn_output` | 16 | 12 (Q4_K) | 2048 × 2048 | 2,359,296 | 37,748,736 |
| `ffn_norm` | 16 | 0 (F32) | 2048 | 8,192 | 131,072 |
| `router` | 16 | 0 (F32) | 2048 × 64 | 524,288 | 8,388,608 |
| `output_norm` | 1 | 0 (F32) | 2048 | 8,192 | 8,192 |
| `output` | 1 | 14 (Q6_K) | 2048 × 50304 | 84,510,720 | 84,510,720 |

**`attn_v` is not one size and the design must not pretend it is.** Eight of the sixteen layers
carry a Q6_K `attn_v` at 3,440,640 B and eight carry Q4_K at 2,359,296 B —
`8 × 2,359,296 + 8 × 3,440,640 = 46,399,488`, which is the mixed-quantization pattern
`llama.cpp`'s `Q4_K_M` recipe applies. So **the per-layer dense window is not a constant**:

| Layer flavour | Layers | `layer_window_bytes` |
| --- | --- | --- |
| Q4_K `attn_v` | 8 | 9,994,240 |
| Q6_K `attn_v` | 8 | 11,075,584 |
| **sum** | **16** | **168,558,592** |

`8 × 9,994,240 + 8 × 11,075,584 = 168,558,592`, which is exactly item 32 section 3.9's dense-layer
term, and `9,994,240 = 9,461,760` (the `AttentionBlock`) `+ 532,480` (the `RouterBlock`). Every one
of the twelve member sizes above is already a multiple of `block_align` 4,096 **except `output`**
(84,510,720 = 4,096 × 20,632.5), and section 2.2 is where the 2,048 bytes that costs are spent
rather than rounded away.

**Two per-layer quantities coincide on this model and must not be confused in general.**
`Plan.layer_window_bytes[layer]` is the `align_up`-per-member sum the arena is laid out from;
`Plan.layer_member_bytes[layer]` is the raw member sum that `steps[].residency.dense_bytes`
accumulates. Because every dense member size here is already a multiple of 4,096, both are
9,994,240 / 11,075,584 and both total 168,558,592. **The arena uses the aligned one**, and a model
whose dense members are not 4,096-multiples would separate them; section 5.2 names which cell reads
which.

**Head window** = `align_up(8,192, 4096) + align_up(84,510,720, 4096)` = `8,192 + 84,512,768` =
**84,520,960 B**, which is exactly the `window.dense_bytes` the streamed arm publishes today
(`dense_peak_block_index` 1057, `dense_peak_block_kind` 0, `dense_peak_block_bytes` 84,520,960).
That is the free structural check that this document read the right table: the streamed window is
sized by the head, and the head is the largest dense graph.

### 2.2 The arena, computed by the shipped algorithm rather than by hand

`model_forward.plan_resident` (`src/model_forward.align:3282`) computes
`step := max(block_align, MAX_TENSOR_ALIGNMENT)` = `max(4096, 64)` = 4,096 and then walks
`[token_embd table][embed stage][layer 0 … layer 15][head]`, `align_up`-ing each region to `step`.
Run on OLMoE's numbers:

```text
  table  align_up(57,950,208, 4096)                 =   57,950,208   base 0
  stage  align_up(1,152 × 32, 4096) = align_up(36,864)=      36,864   base 57,950,208
  16 layers, 8 × 9,994,240 + 8 × 11,075,584          =  168,558,592   base 57,987,072
  head   align_up(84,520,960, 4096)                  =   84,520,960   base 226,545,664
  ----------------------------------------------------------------
  arena interior                                     =  311,066,624 B
```

| Field | Contract |
| --- | --- |
| `weights.resident_bytes` | **311,066,624** on the reference model. Published, and reproduced independently by the runner from the pack document's 147 dense member records |
| Member payload inside it | 311,027,712 B of weights + 36,864 B of embed stage = 311,064,576 B |
| Padding inside it | **2,048 B**, entirely in the head region, because `output` is the one dense member whose size is not a multiple of 4,096 |
| Base pad | at most `MAX_TENSOR_ALIGNMENT` = 64 B outside the interior, as `R4.5` and `R6-RESIDENT-WEIGHTS` both do |
| `ResidentLayout` index convention | `base[0]` is the **stage**, `base[1 + layer]` is a layer, `base[1 + n_layer]` is the head, and the table is at `table_at = 0`. `n_layer + 2` = **18** entries. Unchanged from the dense arm |
| Embed stage size | `row_bytes × MAX_PREFILL_TOKENS` = `1,152 × 32` = **36,864 B**. `MAX_PREFILL_TOKENS` is **`layer_olmoe`'s** 32, not `layer_qwen2`'s; section 3.5 records why that substitution is load-bearing even though the two constants are equal today |
| Budget | `resident_bytes <= model_forward.MAX_WINDOW_BYTES` (8,589,934,592), the existing constant and the existing idiom. 311 MB leaves 96.4 % headroom |

**A reader should be able to check this without running anything**, so the arithmetic is closed
here: `57,950,208 + 36,864 + 168,558,592 + 84,520,960 = 311,066,624`, and
`311,066,624 − 311,027,712 − 36,864 = 2,048`.

### 2.3 What is not resident, and what that costs

The 3,900,702,720 B of expert planes stay in the pack and keep travelling through the claim window
exactly as they do today: `size_claim_window` reserves `195,821,568 B` at `U_max = min(64, 8 · T)`
= 48 for `T = 6`, the decode phase uses 32,636,928 B of it, and every step's
`read_block_scatter` reads 487,587,840 B and — measured on 64 steps in item 32 section 12.3 — **not
one byte more**. Nothing in this capability touches that path, and section 4.4 asserts it.

## 3. Public-contract ledger

Fields marked `N/A` carry their reason. Rows item 32, `R6-RESIDENT-WEIGHTS`, `R6-STEP-N`, and
`R6-DECODE-KV-STEP1` settled are restated only when they change.

### 3.1 The arm

| Field | Contract |
| --- | --- |
| Surface | `ggml-spike --moe-decode-step` — unchanged; the first operand and nothing else selects the arm |
| Owner module | `src/moe_decode_step.align`. `src/ggml_spike.align` is **byte-unchanged**: the dispatch arm forwards `args` and does not enumerate arity |
| Operand grammar | `--moe-decode-step PACK GEOMETRY TOKENS DOCUMENT REFERENCE TRANSCRIPT KV_WIDTH LOGITS STEPS KV_SAVE KV_LOAD RESIDENT` |
| Arity | `args.len()` of 5, 6, 7, 9, 10, 11, or **14**. **8 remains refused** for R6's own reason — a transcript without a width refuses itself. **12, 13, and 15 and above remain refused.** The shipped guard is one line, `if count < 5 \|\| count == 8 \|\| count > 11`, and it becomes `if count < 5 \|\| count == 8 \|\| (count > 11 && count != 14) \|\| count > 14` |
| **How an arity refusal presents** | `Err(Error.Invalid)` — **no document, non-zero exit**, the `NO_DOCUMENT` class the seventh smoke block already uses for `md-arity-4`, `md-arity-8`, `md-arity-12`. **There is no `R6M_ARITY` constant in the source**; the name appears in item 32's prose and in `docs/align-development.md` only, and this document does not introduce one. Section 11 item 10 records the discrepancy rather than propagating it |
| Operands 1–11 | Unchanged from item 32 sections 3.2 and 3.8 |
| Codes | `R6M_`-prefixed, unchanged in rule. Two new: `R6M_RESIDENT`, `R6M_RESIDENT_BUDGET`. One new for the reserved positions: `R6M_KV_UNSUPPORTED`. All three are **document-carrying**, unlike the arity refusal |

### 3.2 The `RESIDENT` operand, and the two positions in front of it

| Field | Contract |
| --- | --- |
| `RESIDENT` | `args[13]`, the fourteenth operand — **the index the dense arm uses**, which is the reservation item 32 section 3.2 and `docs/align-development.md` both published in writing |
| Values | **`-` means streaming**, the shipped behaviour, and is what an absent operand means. **`dense` means the dense member set is resident.** Any other value, including the empty string, is `R6M_RESIDENT` with detail `resident[<text>]` bounded to 256 bytes by `bounded_detail` |
| **`weights` is refused by name** | `resident[weights]`, the same `R6M_RESIDENT` code. The dense arm accepts that value and this arm must not: whole-model residency makes `residency.expert_bytes` unreachable and this arm exists to publish it. A value that is legal on a sibling arm and illegal here is refused explicitly rather than falling through a default, and the refusal is a shipped regression (`mdr-resident-weights-refused`) |
| `KV_SAVE`, `KV_LOAD` | `args[11]`, `args[12]`. **Must both be `-`.** Anything else is `R6M_KV_UNSUPPORTED` with detail `kv[save]` or `kv[load]`, raised **before** any path work. KV persistence on a routed arm is deferred on item 32 section 8's two exact couplings, and this is how the deferral stays a deferral |
| Why arity 14 and not arity 12 | Taking `args[11]` for `RESIDENT` would be one fewer placeholder and would break the promise item 32 published — that positions 11, 12, and 13 hold `KV_SAVE`, `KV_LOAD`, and `RESIDENT` "at the same indices the dense arm uses", so that "a command line cannot be silently reordered between them". A caller who moves a `--decode-step` line to this arm would then get residency where they asked for a KV save path. The two `-` placeholders are the price of that property and they are cheap |
| Defaults | One, and it is `STEPS`'s shape: absent is `-`. Its hazard — a caller who wants residency and forgets the operand silently gets streaming — is closed by publishing `weights.mode` in **every** document, including error documents |
| Why a value rather than a flag | `dense` names *what* is resident. The capability that adds partial expert residency extends the value set (`dense+experts`, or a policy name) without changing the arity or the grammar |
| Refusal precedence | `R6M_ARITY` (arity), then `R6M_KV_UNSUPPORTED` (positions 11 and 12, save before load), then `R6M_RESIDENT` (position 13), then item 32's existing order — `R6M_TOKENS`, `R6M_STEPS`, `R6M_KV_WIDTH`, then path content. Residency grammar precedes every path-content check, so an unknown residency mode is refused before a file is opened and `weights.mode` is still published in that document. This is the order `src/decode_step.align:3063` already establishes |

### 3.3 The arena — layout, ownership, and lifetime

This is the ownership/allocation boundary the gate fired on. Every field is exact.

| Field | Contract |
| --- | --- |
| What it is | One `buffer` local in `moe_decode_step`'s owning frame, over-reserved by `model_forward.MAX_TENSOR_ALIGNMENT` (64) exactly as the dense window is today, with the interior slice starting at the first 64-byte boundary (`base_mod`) |
| Who allocates | The same frame that allocates the dense window today, once, **in dense mode instead of the dense window** rather than in addition to it. In streaming mode nothing changes |
| Who frees | The owning frame, at its exit, **after** the run-scope wrap is freed. There is no path on which the arena outlives its wrap; section 5.1's early-exit cell is the closure cell |
| Layout | Section 2.2, computed by the routed planner of section 3.5 |
| Size on the reference model | **311,066,624 B** |
| Budget | `resident_bytes <= model_forward.MAX_WINDOW_BYTES` (8,589,934,592), the existing constant. Refused as `R6M_RESIDENT_BUDGET`, detail `bytes[<n>]`, **before any allocation** — which is also what catches the `-1` a `plan_resident`-style overflow poisons the total with |
| Refusal on a degraded reservation | `R6M_RESIDENT_UNAVAILABLE`? **No — `R5_WINDOW_UNAVAILABLE`, unchanged.** The observable-consequence guard on `weights.bytes().len() != pad + region_bytes` already exists on this arm for the dense window and already carries that code. Adding a second code for the same condition on the same buffer would be two names for one thing, which is exactly what item 32 section 3.2 refuses for seam codes. Not input-reachable while Request 35 stands; deferred on the same terms |
| Lifetime relative to graphs | The arena and its wrap live for the **whole run**, across `o.graph_count = (2 · n_layer + 2) · (1 + N)` = **578** graphs at `N = 16`, which is **306 dense-window wraps** replaced by one. The four ggml contexts per routed layer, every tensor, the claim window's wrap, and the input buffers stay **per graph** |
| Mutation after fill | **None**, except the 36,864-byte embed stage, which is rewritten by each graph that gathers rows. Every other byte is immutable, which is what makes one wrap safe across 578 graphs |
| Interaction with the claim window | **None.** Two buffers, two lifetimes, two budgets, two wraps. Section 3.4 |

### 3.4 One wrap or two — the decision, and it is two

The question the gate actually poses: the routed arm uploads expert claims into a **separate**
window per step, so does the resident arena and the claim window become one `buffer` under one
`ggml_backend_buffer` wrap, or two?

**Two.** One run-scope wrap over the arena, and the claim window's per-graph wrap unchanged.

| Reason | Detail |
| --- | --- |
| A wrap is one contiguous host range | `ggml_backend_dev_buffer_from_host_ptr` wraps one address and one length. Two Align `buffer`s cannot be one wrap without becoming one `buffer`, and making them one `buffer` is the merge this row is deciding against |
| Their lifetimes differ in kind, not degree | The arena is written once and is read-only for 578 graphs; the claim window is rewritten every layer of every step from `p.claim_start[]`/`p.claim_source[]`. "Written once, immutable" is precisely the property that makes one run-scope wrap safe, and folding a per-step-mutated 195,821,568 B region into it would spend that property to save one allocation |
| Their budgets and refusals are separate contracts | `R5D_CLAIM_BUDGET` against `MAX_CLAIM_WINDOW_BYTES` and `R6M_RESIDENT_BUDGET` against `MAX_WINDOW_BYTES` are two ceilings on two quantities. One buffer means one budget, and the merged refusal could not say which region overflowed |
| Their published accounting is separate and is the deliverable | `window.claim_bytes`, `claim_u_max`, `claim_peak_use_bytes`, `claim_decode_peak_use_bytes` are item 32's fields and a residency policy reads them. Merging deletes the boundary those fields measure |
| The counter design already anticipates it | `R6-RESIDENT-WEIGHTS` section 4.3 splits the per-graph pair from a run-scope pair so the per-graph check keeps its **exact** meaning instead of being loosened. With two wraps the claim window's per-graph wrap keeps incrementing `ggml_buffers_created`/`_freed` exactly as today, and only the arena's wrap moves into `resident_wraps_created`/`_freed` |
| The cost of two | One extra `buffer_from_host` call for the whole run and one extra handle in the teardown. That is the entire cost |

**What "two" does *not* mean.** It does not mean two wraps per graph. In `dense` mode the dense
window's wrap disappears — the graph adopts the run-scope arena wrap and counts nothing, exactly as
`src/decode_step.align:885` does — and only the claim window's wrap is created per layer.

The arm's wrap accounting today, counted per **pass** (one prefill pass plus `N` decode passes, 17
at `N = 16`): each routed layer wraps the dense window once and the claim window once (after the
routing decision) and takes one `alloc_remaining` input buffer; each of the two end graphs — the
embedding gather and the head — wraps the dense window once and takes one input buffer, and never
touches the claim window.

| Per pass | `-` (stream) | `dense` |
| --- | --- | --- |
| Dense-window wraps | 16 layers + 2 ends = **18** | **0** |
| Claim-window wraps | 16 | 16, unchanged |
| Input buffers (`alloc_remaining`) | 18 | 18, unchanged |
| `ggml_buffers_created` per pass | **52** | **34** |

| At `N = 16` (17 passes) | `-` (stream) | `dense` |
| --- | --- | --- |
| Run-scope arena wraps | 0 | **1** |
| `lifetime.ggml_buffers_created` | **884** | **578** |
| `weights.wrap_count` (weight-region wraps) | **306** | **1** |
| Graphs | 578 | 578 |

> **Shipped:** these counts are arithmetic on `o.graph_count = (2 · n_layer + 2) · (1 + N)` and on
> the per-graph wrap sites, and they are written to be checked against the diff rather than
> believed. If implementation finds a different wrap site, the totals move and the decision does
> not.

### 3.5 The routed resident plan — why `plan_resident` cannot simply be called

Item 32 section 3.9 deferred this capability with the reason "`model_forward.plan_resident`
describes a dense `Plan`/`Ends` with a per-layer constant window, and a routed layer's window is not
constant". **That reason is directionally right and mechanically wrong, and getting it right is what
this section is for.**

`plan_resident` (`src/model_forward.align:3282`) indexes `p.layer_window_bytes[layer]` per layer and
`align_up`s each extent independently. It has **never** assumed a constant per-layer window, and it
would compute OLMoE's `8 × 9,994,240 + 8 × 11,075,584` correctly if it could be called at all. The
three real obstacles are:

| Obstacle | What it is |
| --- | --- |
| **Type** | `plan_resident` is typed on `model_forward.Plan` and `model_forward.Ends`. `moe_model_forward.Plan` is a different named type in a different module — it carries `n_expert`, `router_index`, `expert_index`, `claim_start`, `claim_source`, `plane_bytes`, and has no `mlp_index`/`mlp_offset`. Align has no generics at this pin, so the function cannot be applied to it |
| **Constant** | `plan_resident` sizes the embed stage with `layer_qwen2.MAX_PREFILL_TOKENS`. The routed arm's cap is `layer_olmoe.MAX_PREFILL_TOKENS`. **Both are 32 today**, which is exactly why calling the dense function would work by accident and break the day one of them moves |
| **Second region** | A routed layer's weights live in **two** windows — the dense window and the routing-dependent claim window — and `ResidentLayout`'s `base`/`span` is `n_layer + 2` entries with no place for the second |

**What ships.** A routed twin, `moe_model_forward.plan_resident_dense`, taking
`moe_model_forward.Plan` and `moe_model_forward.Ends` and `layer_olmoe.MAX_PREFILL_TOKENS`,
returning the **same** `model_forward.ResidentLayout` record, with `model_forward.stream_layout`,
`model_forward.empty_resident_layout`, `model_forward.stage_embed_row`,
`model_forward.read_into_window`, `model_forward.window_put`, `model_forward.prime_window`,
`model_forward.base_mod`, and `model_forward.fill_zero` all **reused unchanged**.

| Field | Contract |
| --- | --- |
| New function | `moe_model_forward.plan_resident_dense(borrow p: Plan, borrow e: Ends, block_align: i64) -> model_forward.ResidentLayout` |
| Why a twin and not a shared generic | Align has no generics at the pin, and a `borrow`-taking cross-module call cannot be parameterized over two record types. This is Request 49's shape and section 9 records it as one more client — **no compatibility layer is built and no hypothetical surface is consumed** |
| Why it returns `model_forward.ResidentLayout` | The record is architecture-free: an offset table of `n_layer + 2` entries. Duplicating it would mean duplicating `stream_layout` and `stage_embed_row` too, and every one of those is byte-reusable. The **type** is shared; only the **producer** is duplicated |
| Third region | **N/A, and this is the decision.** The claim window is not in the layout. It keeps its own buffer, its own sizing (`size_claim_window`), its own budget, and its own per-graph wrap. Section 3.4 |
| Duplicated lines | Approximately 40 — the walk of section 2.2 — against the roughly 3,600 lines Request 49 already forces `moe_decode_step.align` to duplicate. The request's evidence gains this function and its arithmetic constant |
| What `model_forward.align` gains | **Nothing, and that is a contract.** `plan_resident`, `stream_layout`, `stage_embed_row`, `graph_weights`, `graph_identity`, `stage_window`, and `fill_members` are **byte-unchanged**, so the dense arm's goldens cannot move. Section 5.3 is the cell |

**The per-graph base offset needs no new mechanism.** `graph_weights` keeps `m.window[at]`
graph-relative and the caller takes the slice: `window[base[1 + layer] .. base[1 + layer] + span]`.
The C shim bounds-checks the absolute address against the wrap's base and calls
`ggml_backend_tensor_alloc`, which is why placing tensors into a sub-slice of a wrap over the whole
arena works with zero edits — `R6-RESIDENT-WEIGHTS` proved that on 339 members per graph and this
capability re-proves it on 147.

### 3.6 The embedding row, and why "zero dense bytes per step" is exactly true

The one dense read that is *not* a fixed member is the embedding row gather: `fill_members` reads
`pieces` rows of `stride` bytes at `m.pack[at] + tokens.ids[piece] * span`, so its source offset
depends on the token. At `T = 6` that is 6,912 B; per decode step it is one row, **1,152 B**
(2,048 Q4_K elements = `2048 / 256 × 144`).

1,152 B is not zero, and a claim of "zero dense bytes per step" that quietly excluded it would be
false. The arena therefore holds the **whole 57,950,208 B `token_embd.weight` table**, and the
gather becomes `model_forward.stage_embed_row` — an arena-to-arena `window_copy`, no `pread`.

| Field | Contract |
| --- | --- |
| Embed stage | `layer_olmoe.MAX_PREFILL_TOKENS × row_bytes` = `32 × 1,152` = **36,864 B**, at `layout.base[0]` |
| Cost per decode step | **1,152 B copied, 0 B read** |
| Cost per prefill | `T × 1,152 B`, at most 36,864 B |
| Bound on the destination | `stage_embed_row`'s existing guard bounds the write by the stage's **own** span, not the arena's, so a slot past `MAX_PREFILL_TOKENS` cannot overwrite a layer's resident weights. Unchanged, and newly load-bearing |
| Why the whole table for 1,152 B | Because the claim is "zero", and 57,950,208 B is 18.6 % of an arena this small. On the dense arm the same decision cost 306,561,024 B of 4.68 GB; here it costs less in absolute terms and more in relative terms, and it is taken for the same reason: an exact claim is worth more than a smaller number |

**So the claim is exact:** in `dense` mode a decode step reads **0 dense bytes** from the pack,
copies **1,152 bytes** of host memory, and reads **487,587,840 expert bytes**. All three are
published rather than argued.

### 3.7 The performance claim — baseline, ceiling, floor, and metric

`CLAUDE.md`'s Performance-claim row applies. The cost ceiling is recorded **here, in the commit
before implementation**, and the owning performance document is named.

**Who owns Track B decode performance.** `docs/specs/r6-resident-weights.md` section 3.4, which took
that ownership from `docs/specs/c8-speed-first.md` (whose section 1 excludes model throughput in its
first sentence and whose 2,000 ppm floor is calibrated on a ~46 ms task). This capability **records
its ceiling against that document and adopts its floor unchanged**. It does not become a second
owner and it does not move the floor.

**Baseline.** Item 32 section 12.3, the qualification of record, on the reference host (Apple M1,
8 cores, 16 GiB, macOS 26.5.2, `darwin/arm64`), pin `3a34febe912db5096c58c74fede36ff53f223e04`,
`KV_WIDTH` 256, `N = 16`, weights streamed, warm page cache:

| Prompt | `T` | `timings.elapsed_ns` at `N = 16` |
| --- | --- | --- |
| 1 `def add(a, b` | 6 | **3.63 s** |
| 2 `The capital of` | 3 | 3.39 s |
| 3 `import os` | 2 | 3.26 s |
| 4 `return x +` | 3 | 3.06 s |

**The fixed task is prompt 1 at `N = 16`**, the slowest and therefore the least flattering
denominator. All four are reported.

**The baseline is re-taken before the result is claimed**, on the same host in the same session,
with the legs **interleaved** (`repeat` outside, `mode` inside) and three repeats per point, for the
reason `r6-resident-weights.md` section 3.4 measurement risk 4 records: taking one leg's repeats and
then the other confounds the leg with the clock, and the whole of any monotone drift lands on one
side of the subtraction. The **conservative reading is the worst of the repeats**, not the median,
and section 6 states the verdict rule.

**Primary metric — exact and noise-free.** `weights.step_dense_pack_bytes`, the **dense** pack bytes
read by the decode steps alone.

| Point | Streamed baseline | `dense` target |
| --- | --- | --- |
| `N = 1` | 253,078,656 | **0** |
| `N = 4` | 1,012,314,624 | **0** |
| `N = 16` | **4,049,258,496** | **0** |

This is a counter, not a clock, it is identical across runs, and it carries the claim.

**Co-primary invariant — the measurement must not move.** `steps[i].residency.expert_bytes` and
`expert_pread_bytes` are **487,587,840 on every step in both legs**, `expert_read_amplification_ppm`
is 0, `keys_demanded` is 128, `claim_planes_read` is 384, and `weights.step_expert_pack_bytes` is
`487,587,840 × N` in both legs. Section 4.4 makes this an acceptance clause, because a residency
capability that quietly changed the number the arm exists to publish would have removed the reason
for the arm.

**Secondary metric — elapsed.** `timings.elapsed_ns` at `N = 16` on the fixed task, three
interleaved repeats, worst-of-N reported as the verdict with the whole spread printed.

**Cost ceiling, recorded before implementation.** Residency removes dense `pread` time and adds a
one-time fill. Both terms are measured, not estimated:

```text
  removable bytes  16 steps × 253,078,656 B                    = 4,049,258,496 B
  added bytes      fill 311,027,712 B against the streamed
                   prefill's 253,084,416 B                     =    57,943,296 B
  net                                                          = 3,991,315,200 B

  dense read rate, measured on this arm at N = 2 on this host:
    759,241,728 B / 190,606,005 ns = 3.983 GB/s   (timings.pread_ns, warm)
    759,241,728 B / 195,287,333 ns = 3.888 GB/s   (second warm probe)
    759,241,728 B / 352,161,833 ns = 2.156 GB/s   (cold)

  removable time at 3.983 GB/s, the FASTEST warm rate           = 1.002 s
```

**Ceiling = 1.002 / 3.63 = 276,000 ppm** of the `N = 16` fixed task. Predicted result ≈ **2.63 s**
elapsed.

Three things about that number are stated rather than left to a reader:

1. **The fastest measured rate is the conservative choice.** A faster dense read means less time to
   remove, so quoting 3.983 GB/s rather than 3.888 or 2.156 makes the ceiling *smaller*. At the cold
   rate the same bytes would be 1.851 s and the ceiling 510,000 ppm; the design does not claim that.
2. **The ceiling is prompt-dependent only through its denominator.** The removable term is
   prompt-independent because the dense set is. On prompts 2, 3, and 4 the same 1.002 s is 296,000 /
   307,000 / 328,000 ppm. Prompt 1 gives the smallest ceiling and is the fixed task.
3. **A measured result far below the ceiling is reported as a ceiling-estimation miss**, per
   `docs/specs/c8-speed-first.md` section 1 and the threshold `r6-resident-weights.md` section 3.4
   fixed: **the `miss` label applies only below one half of the recorded ceiling**, i.e. below
   138,000 ppm — which is also below the floor, so on this capability a miss and a floor failure
   coincide. The runner prints the result as a percentage of the ceiling on **every** run.

**Shipping floor — 150,000 ppm, adopted from `r6-resident-weights.md` section 3.4 unchanged.** A
capability does not get to lower a floor because its own seam is small. Two consequences are taken
rather than argued around:

- **The margin is 1.84×, not 3.9×.** The dense arm's ceiling was 3.9× its floor; this one is
  `276,000 / 150,000 = 1.84×`. That is a thinner seam and it is recorded as one. If the measured
  result lands below 150,000 ppm the capability does **not** ship an elapsed claim; it ships the
  byte claim and records the elapsed leg as below the floor, which is what the floor is for.
- **The claim is made at `N = 16` only.** The net removable bytes at `N = 1` are
  `253,078,656 − 57,943,296 = 195,135,360` (≈ 0.049 s, ≈ 20,000 ppm of a ~2.5 s run) and at `N = 4`
  are `954,371,328` (≈ 0.240 s, ≈ 82,000 ppm). Both are **wins** — unlike the dense arm, which is
  reliably slower at `N = 1` because its fill is 4.68 GB — and both are **below the floor**. They
  are published as diagnostics at `N ∈ {1, 4, 16}`, with the byte metric exact at all three, and no
  elapsed claim is made at 1 or 4. **There is no crossover on this arm**, which is worth saying
  plainly because the dense arm has one and a reader will expect one.

**The cost, stated beside the benefit.** Peak footprint grows by exactly
`311,066,624 − 84,520,960 = 226,545,664 B`, from 347,451,392 B to 573,997,056 B of weight windows
plus plane — a factor of **1.65**, against the dense arm's 9.4. Section 3.9.

**Measurement risks, with direction.**

1. **Page-cache state dominates the streamed baseline** and this arm is more exposed to it than the
   dense arm was. Item 32 section 12.5 measured the *same tree* at 1 min 23 s and 5 min 41 s
   depending on whether the 4.2 GB pack was resident in the page cache. A cold baseline would
   **flatter** residency. *Mitigation:* baseline and result back to back, one session, one host,
   pack already read once, legs interleaved; and the primary metric is a byte counter the page cache
   cannot move.
2. **The baseline is 3.63 s where the dense arm's was 18.235 s, so the same absolute noise is five
   times larger in ppm.** Item 32's own per-run shell timings show it: prompt 3 spread 4.34/4.34/4.51
   (≈ 39,000 ppm) but prompt 2 spread 5.30/6.17/8.15 (≈ 440,000 ppm, larger than this capability's
   whole ceiling). Direction is **unknown**, which is worse than a known direction. *Mitigation, and
   it is pre-committed rather than decided after the fact:* if the streamed leg's own spread at the
   fixed task exceeds the recorded ceiling of 276,000 ppm, the elapsed leg is reported
   **`INDETERMINATE`** — printed, not discarded — and the capability ships on the byte metric alone.
   The runner asserts this and the rule is in the ledger before any number exists.
3. **The measuring host compresses memory under pressure.** `r6-resident-weights.md` section 2.4
   measured 1.25 GB of a 4.37 GB footprint compressed. At 574 MB peak this arm is far below that
   pressure, so the risk is **smaller here than there** — but it is not zero and it is not assumed
   away. *Mitigation:* `vm_stat` (Darwin) / `/proc/vmstat` (Linux) compressor counters recorded
   before and after every timed run and **printed with the result**. Nothing is discarded or
   retaken, for the reason `r6-resident-weights.md` section 3.4's `Shipped` note gives: a mitigation
   that silently drops the runs it dislikes is a filter on the measurement.
4. **`N = 16` is one point on one prompt on one host in one thermal environment.** *Mitigation:* the
   byte metric is reported at `N ∈ {1, 4, 16}` on four prompts and is exact at all twelve points;
   the elapsed claim is explicitly secondary and explicitly bounded to the reference prompt on the
   reference host. Nothing here establishes the result on a fanned host, on a host with more memory,
   or on a Linux page cache, and section 7 records that as an unmitigated clause.
5. **The expert path could move and be mistaken for noise.** *Mitigation:* `timings.claim_pread_ns`
   and `residency.decode_expert_pread_bytes` are reported on **both** legs. The bytes must be
   identical; the time is a diagnostic whose movement, if any, is reported rather than absorbed.

### 3.8 The document — `R6_MOE_DECODE_STEP`, schema 2

| Field | Contract |
| --- | --- |
| Schema | `schema_version` becomes **2**. `scripts/moe-decode-step-golden.jsonl` (59 rows) is rewritten on item 32's own recorded exemption: it is that capability's file, created by it and consumed by nothing else |
| `weights` | **New object, present in every document including error documents.** Item 32 section 3.10 recorded it as deliberately absent; this capability is the reason it stops being absent, so the change is a contract change and not a churn |
| `weights.mode` | `"stream"` or `"dense"`. Never implicit |
| `weights.resident_bytes` | The arena's interior size — 311,066,624 in `dense` mode, 0 in `stream` |
| `weights.fill_ns`, `fill_pread_count`, `fill_bytes` | The one-time fill. `fill_bytes` is **311,027,712** (the 147 members; the stage is not filled from the pack). 0 in stream mode |
| **`weights.step_dense_pack_bytes`** | **The primary metric, and it is a syscall counter.** It accumulates the decode steps' **own dense** `alignpack_read.Counters.bytes_read` — the counters object the dense `fill_members`/`read_into_window` calls write — and **not** `claim_counters`, which `decode_pass` already keeps as a separate frame-local for `expert_pread_bytes`. Exactly **0** in `dense` mode; `253,078,656 × N` in `stream` mode. Two disjoint counters through two disjoint code paths is what makes "residency cannot move the expert measurement" a mechanism rather than an assurance |
| **`weights.step_expert_pack_bytes`** | Expert pack bytes read by decode steps only, `Σ steps[i].residency.expert_pread_bytes`. `487,587,840 × N` in **both** modes |
| Why not reuse `residency.dense_bytes_read` as the metric | Because it is **arithmetic**: `o.dense_bytes_read` accumulates `plan.layer_member_bytes[layer]` plus the head and embed member sizes, not what the reader read. Item 32 section 3.11 built the arithmetic/syscall pair deliberately, and a residency claim measured on the arithmetic side would be a claim about what a graph needs rather than about what a process read |
| `weights.step_pack_bytes` | Their sum. **This field keeps `r6-resident-weights.md` section 3.5's exact meaning** — "pack bytes read by decode steps only" — so the same name means the same thing on both decode arms. On this arm it is therefore `487,587,840 × N` in `dense` mode and **not** 0, and a reader comparing the two arms is not misled. The claim's metric got its own name instead |
| `weights.wrap_count` | Wraps created over the **weight** region: **1** in `dense` mode, **306** at `N = 16` in `stream` mode (section 3.4). Claim-window wraps and input buffers keep counting into `lifetime.ggml_buffers_created`/`_freed` exactly as today |
| `weights.resident_wraps_created`, `_freed` | Section 4.3 |
| `pack.reader_pread_count`, `reader_bytes_read` | Unchanged in meaning: totals over the whole run |
| `residency.*`, `steps[].residency.*`, `steps[].routed.*` | **Unchanged in meaning and, for every `*_bytes` field, unchanged in value.** Section 4.4 |
| `window.pointer_identity_failures` | Unchanged field, **new reach**: in `dense` mode the dense placements are against the arena. A non-zero value means a tensor did not land where the layout said, and it is the free structural oracle for the whole design |
| `normalize` | Zeroes `weights.fill_ns` in addition to everything item 32 section 3.10 already zeroes. `weights.resident_bytes`, `fill_pread_count`, `fill_bytes`, `step_dense_pack_bytes`, `step_expert_pack_bytes`, `step_pack_bytes`, `wrap_count`, and both wrap counters are **not** normalized: they are deterministic and they are the claim |
| Path-valued fields | None added. The temp-path golden failure class stays inapplicable |

### 3.9 The memory ceiling, and why no host preflight ships

| Object | `stream` | `dense` |
| --- | --- | --- |
| Dense window / arena | 84,520,960 | **311,066,624** |
| Claim window | 195,821,568 | 195,821,568 |
| KV plane at `KV_WIDTH` 256 | 67,108,864 | 67,108,864 |
| **Sum** | **347,451,392** | **573,997,056** |

| Host | Behaviour |
| --- | --- |
| The reference host (16 GiB), `RESIDENT=dense` | Resident. 574 MB of windows plus ggml's activations |
| Any host, `RESIDENT=-` or absent | **Streaming, unchanged.** The shipped behaviour is the default and no host regresses |
| A pack whose dense sum exceeds 8 GiB | `R6M_RESIDENT_BUDGET` before any allocation. A document, not a crash |
| A host that cannot hold 574 MB | It cannot hold 347 MB either, so it cannot run the streamed arm. **There is no host on which this operand is the difference between a document and an abort** |

**Three consequences, and two of them differ from the dense arm's.**

1. **No physical-memory preflight ships.** `scripts/run-decode-step` refuses its resident leg below
   12 GiB and prints one `N/A` line, because there a failed 4.68 GB reservation aborts the process
   inside the runtime's `Vec` growth (Request 35). Here the delta is 227 MB on top of a run that
   already reserves 347 MB, so a preflight would be a check that cannot fire, and a gate that cannot
   fire is a gate a reader has to reason about for nothing. `scripts/run-moe-decode-step`'s existing
   scratch-space preflight is unchanged.
2. **Request 50 gains no client here, and that is recorded rather than assumed.** The proposed
   `std.os.physical_memory()` exists in the register because a 4.68 GB arena needs it. A 311 MB
   arena does not. Section 9 says so by name so that a later reader does not count this capability
   as evidence for a request it does not use.
3. **Request 35 is cited, not sharpened.** `buffer(cap)` still cannot report a failed reservation,
   and the observable-consequence guard (`weights.bytes().len()`) still stands in for it. At this
   size the consequence is an unreachable guard rather than a process abort, which is the state that
   request was already recorded in.

### 3.10 Ownership, allocation, lifetime, and bounded memory

| Object | Owner | Allocated | Freed | Bound |
| --- | --- | --- | --- | --- |
| The arena | the owning frame in `moe_decode_step`, one `buffer`, over-reserved by 64, `fill_zero` + `base_mod` + `prime_window` + interior slice | once, in `dense` mode, in place of the dense window, before `backend_open` | at that frame's exit, **after** the wrap, on every path | `MAX_WINDOW_BYTES`, `R6M_RESIDENT_BUDGET` |
| The run-scope wrap | the same frame | after the fill, before the first graph | before `backend_close`, on every path including every failure path | one; section 4.3 |
| The dense window | the same frame | **only in `stream` mode**; unchanged | same | `MAX_WINDOW_BYTES`, `R5_WINDOW_BUDGET` |
| The claim window and its per-graph wrap | the same frame | unchanged | unchanged | `MAX_CLAIM_WINDOW_BYTES`, `R5D_CLAIM_BUDGET` |
| The plane | unchanged | unchanged | unchanged | `MAX_PLANE_BYTES`, `R6M_PLANE_UNAVAILABLE` |
| ggml contexts, input buffers, gallocrs | per graph, unchanged — four contexts per routed layer, three per end graph | per graph | per graph, by `teardown_layer`'s existing nine-handle order | `lifetime.*_created == *_freed` after 578 graphs |
| The fill's chunk buffer | `fill_resident_dense`'s own frame | once, `model_forward.CHUNK_BYTES` (1,048,576) | with that frame | 1 MiB |
| The `ResidentLayout` | the owning frame, returned by value | once | with the frame | `n_layer + 2` = 18 entries |
| Move-in/out, source nulling, replacement | **N/A.** No ownership transfer is added; the layout is returned by value and the arena travels as `borrow slice<u8>` + `borrow ResidentLayout` + `resident: bool`, which is the shape Request 49 forces | — | — | — |

### 3.11 Prerequisites

| Prerequisite | State |
| --- | --- |
| Everything item 32, `R6-RESIDENT-WEIGHTS`, `R6-STEP-N`, and `R6-DECODE-KV-STEP1` list | Unchanged |
| Item 32 merged, or this branch stacked on its head | **Stacked** on `bf7c87d`. If it merges with repairs this branch takes `git merge origin/main` — never a rebase — and re-runs its owner |
| `R6-RESIDENT-WEIGHTS`'s cell RW-P1 result | **Shipped and measured**: one wrap over an Align buffer accepts tensors created in two different `no_alloc` contexts and survives their teardown, at 4.68 GB. This capability re-uses that finding at 311 MB and does not re-probe it; cell MRD-P1 (section 5.8) probes the one thing that finding does not cover |
| `llama-eval-callback` at generation `r2c-v2`, `llama-debug --save-logits` on OLMoE, `numpy`, `scripts/decode_step_fingerprint.py` | Unchanged from item 32 section 3.13 |
| A host with ~1 GiB of scratch above the pack | Unchanged. **No physical-memory prerequisite is added**; section 3.9 |
| Align language features | **None new.** Section 9 records six gaps; none blocks |

## 4. Oracles and the acceptance rule

The correctness oracle for this capability is **free**, for the same reason it was on the dense arm:
residency changes where bytes live and changes no arithmetic.

### 4.1 Oracle D — dense-resident/streamed document equality

**It is named D and not R, deliberately.** `r6-resident-weights.md` section 4.1 calls this shape
"oracle R", and item 32 section 4.3 calls its *routing-identity* oracle "oracle R". This document
runs **both**, so one of them has to be renamed here or every later sentence is ambiguous. Item 32's
oracle R is unchanged and keeps its name; the residency-equality oracle is **oracle D**.

| Field | Contract |
| --- | --- |
| Assertion | Run the same invocation twice, `RESIDENT=-` then `RESIDENT=dense`, and compare the two documents after `normalize`. Byte-identical **excluding the `weights` object and exactly ten field names**: `pack.reader_pread_count`, `pack.reader_bytes_read`, `lifetime.ggml_buffers_created`, `lifetime.ggml_buffers_freed`, `window.dense_bytes`, `window.dense_peak_block_index`, `window.dense_peak_block_kind`, `window.dense_peak_block_layer`, `window.dense_peak_block_bytes`, `window.reuse_count` |
| The exclusion list is enumerated, not pattern-matched | Ten names and one object, written out in the runner, extending the dense arm's own `RESIDENT_EXCLUDED_BLOCKS`/`RESIDENT_EXCLUDED_FIELDS` shape by the six `window` fields the dense window's absence moves. Everything else is compared |
| What stays **inside** the compared set, and it is the point | The whole `residency` object — including `dense_bytes_read`, `head_bytes_read`, `embedding_bytes_read`, `total_bytes_read`, `expert_bytes_read`, `union_bytes_final` — because every one of them is **arithmetic** and residency does not change what a graph needs. Also every `steps[i].token_id`, every `steps[i].routed.layers[]`, every `steps[i].residency.*`, every `sha256`, `window.member_placements`, `window.claim_placements`, `window.pointer_identity_failures`, the head's logits, and every error code and detail |
| `timings` | Zeroed by `normalize` already (`*_ns`), so no exclusion is needed and none is added |
| Why it cannot pass vacuously | A document with a non-empty `error_code` compares its code and detail too, so a resident run that failed would not silently match a streamed run that succeeded. And `residency.expert_bytes_read` is **inside** the compared set, not the excluded one — section 4.4 |
| Cost | One extra `--moe-decode-step` run per prompt. Section 6 costs it |

### 4.2 Oracle P — pointer identity, existing and newly load-bearing

`graph_identity` already compares `ggml_ffi.slot_data_offset(slots, at, window)` against
`m.window[at]` for every placed tensor and counts `window.pointer_identity_failures`. In `dense`
mode the comparison is against the arena base plus the layout's offsets, so every dense placement per
graph asserts that ggml is computing out of the resident arena. `pointer_identity_failures == 0` is
the assertion; a resident run that silently fell back to a per-graph copy could not satisfy it, and
`weights.step_dense_pack_bytes == 0` could not either.

`window.member_placements` and `window.claim_placements` are both compared by oracle D, so the split
between resident dense placements and streamed claim placements is checked structurally too.

### 4.3 Oracle B — the balance invariant, re-established at run scope

This is the invariant `docs/specs/r5c-metal-prefill.md` section 5.4 said the hoist would weaken and
`r6-resident-weights.md` section 4.3 re-established. It is re-established here at the same scope, in
the shipped form rather than the drafted one.

| Scope | Assertion |
| --- | --- |
| Per graph, `stream` mode | Unchanged: `ggml_buffers_created == ggml_buffers_freed`, `contexts_created == contexts_freed`, `gallocrs_created == gallocrs_freed` |
| Per graph, `dense` mode | The same three, over the objects that are still per graph — **including the claim window's wrap**, which is why the per-graph check keeps its exact meaning here rather than being loosened. The graph adopts the run-scope arena wrap and counts nothing for it |
| Run scope, `dense` mode | `resident_wraps_created != resident_wraps_freed \|\| resident_wraps_created > 1 \|\| (error_code is empty && resident_wraps_created != 1)` increments `graph_balance_failures`. **The third clause is conditioned on success**, so a run that fails before the wrap exists does not fabricate a leak on a teardown that was in fact perfect |
| Why not `== 1` unconditionally | Because that was `r6-resident-weights.md`'s A-MAJOR review finding: a `== 1` assertion on a failure path reports a leak where there is none. This document adopts the **repaired** condition, not the drafted one, and section 7 risk 1 records the class |
| Ordering | The wrap is freed **before** the arena, on every exit path including every failure path, converging on one teardown as R4.5 rule 2 requires |

### 4.4 The expert invariant — the measurement must not move

This clause exists because it is the one way this capability could succeed at its claim and destroy
the thing it was built to protect.

| Assertion | Value | Where |
| --- | --- | --- |
| `steps[i].residency.expert_bytes` | **487,587,840** on every step, both legs | per step |
| `steps[i].residency.expert_pread_bytes` | **487,587,840** on every step, both legs | per step |
| `steps[i].residency.expert_read_amplification_ppm` | **0** on every step, both legs | per step |
| `steps[i].residency.expert_bytes_ppm` | **125,000** | per step |
| `steps[i].routed.keys_demanded` | **128** | per step |
| `steps[i].residency.claim_planes_read` | **384** | per step |
| `residency.decode_expert_bytes` | `487,587,840 × N` | run |
| `residency.union_keys_final`, `union_bytes_final`, `step_reuse_per_mille`, the `routed.layers[]` ids | **byte-identical between the legs** | oracle D |
| `window.claim_decode_peak_use_bytes` | **32,636,928** | run |
| `steps[i].residency.dense_bytes` | **253,078,656 in both legs** — it is the arithmetic demand of the step's graph, not what the reader read, and residency does not change what a graph needs | per step |
| `steps[i].residency.total_bytes` | **740,666,496 in both legs**, for the same reason | per step |

**The last two rows are the subtle ones and they are decided here rather than discovered.**
`residency.dense_bytes` and `total_bytes` are *arithmetic* fields — item 32 section 3.11 defines the
arithmetic/`pread` pair precisely so the two can disagree — and residency changes the `pread` side
only. Making the arithmetic field track residency would silently redefine a published metric between
two schema versions, which is the failure class item 32's own deviation 13 records (a metric
published under a substituted definition). So `steps[].residency` is **unchanged in every field**,
and the bytes residency actually removed are published in `weights.step_dense_pack_bytes` and in
`pack.reader_bytes_read`. One number, one meaning, one owner.

### 4.5 The inherited gate and oracles

Gate G (token ids against `llama-eval-callback --temp 0 -s 0`, over the measured collision classes
`{45382, 50278}`), oracle R (routing identity, `MATCH` at `128N` of `128N` ids), oracle B (the plane
round trip, `IDENTICAL`), oracle T (transcript structure at every step and numeric at step 1), and
oracle C′ (the self-reference, **characterization**, gating on argmax alone) are **unchanged** and
are re-run on the **`dense`** leg, not only on the streamed one. Oracle D means a passing streamed
leg plus a passing oracle D implies a passing `dense` leg for every field either checks; the gate is
still run against the `dense` document so that the claim is direct rather than transitive.

### 4.6 The shipped acceptance rule, stated once

`--moe-decode-step` with `RESIDENT=dense` is accepted when, on the reference host and model, for
each of the four prompts at `N = 16`:

1. **Gate G** — the `N` ids equal llama.cpp's, no decoded id in a collision class;
2. **Oracle R** — routing identity `MATCH`, `ids_total == ids_printed_compared == 2,048`;
3. **Oracle B** — the plane round trip `IDENTICAL` over a positive byte count;
4. **Oracle T** — structurally complete at every step, numerically admitted at step 1;
5. **Oracle C′** — reported at `k ∈ {1, 8, 16}`, gating on argmax equality alone;
6. **Oracle D** — the two legs' normalized documents byte-identical outside the enumerated
   exclusion list;
7. **Oracle P** — `window.pointer_identity_failures == 0` on the `dense` leg;
8. **Oracle B (balance)** — `graph_balance_failures == 0` and `released_before_owner_scope_end` on
   both legs;
9. **The expert invariant** — every row of section 4.4;
10. **The primary metric** — `weights.step_dense_pack_bytes == 0` on the `dense` leg and
    `253,078,656 × N` on the streamed leg, at `N ∈ {1, 4, 16}`;
11. **Determinism** — three consecutive `dense` runs byte-identical after `normalize`;
12. **The floor** — the elapsed verdict of section 6, or `INDETERMINATE` under measurement risk 2,
    printed either way.

Clauses 1 to 11 are **required**. Clause 12 is the performance claim: `MET` ships the elapsed claim,
`BELOW FLOOR` and `INDETERMINATE` ship the capability on clauses 1 to 11 and record the elapsed leg
as what it was. **The capability is not withdrawn by a failing clause 12**, because the byte metric
is the primary claim and it is exact; this is stated in advance so that a disappointing clock does
not become a reason to re-read the rule.

### 4.7 The goldens

| File | Change |
| --- | --- |
| `scripts/moe-decode-step-golden.jsonl` | Rewritten at schema 2. Every one of the 59 rows gains `"schema_version": 2` and a `weights` object with `"mode": "stream"` and zeros. **No row's existing field changes value**, and a differing row is a finding rather than an expected churn |
| `scripts/decode-step-golden.jsonl` | **Unchanged, all 116 rows.** `src/decode_step.align` and `src/model_forward.align` are byte-unchanged; section 5.3 and 5.4 are the cells |
| Every other golden and fixture | **Unchanged**, for the same reason |

New documented cases predicted in advance, so the diff is reconciled rather than explained
afterwards: `mdr-arity-14`, `mdr-arity-13`, `mdr-arity-15`, `mdr-resident-unknown`,
`mdr-resident-empty`, `mdr-resident-weights-refused`, `mdr-kv-save-unsupported`,
`mdr-kv-load-unsupported`, `mdr-resident-dense-1`, `mdr-resident-dense-steps`,
`mdr-resident-budget`, `mdr-resident-stage-full`, `mdr-force-resident-wrap`. Of these,
`mdr-arity-13` and `mdr-arity-15` carry **no golden row** (they are `NO_DOCUMENT`), and
`mdr-force-resident-wrap` is a forced build; the other ten add rows, so the file goes from 59 to
**69** rows. A different count is a finding.

## 5. Closure matrix

Construction, success, failure, malformed input, early exit, cleanup, and each affected module.

### 5.1 `src/moe_decode_step.align` — the operands and the arena's owner

| Cell | Implementation | Regression |
| --- | --- | --- |
| Formation — arity 14 accepted; 8, 12, 13, and 15+ refused | One line in `run`, before `args[13]` is read | `mdr-arity-14` (documented), plus the `NO_DOCUMENT` cases `md-arity-4`, `md-arity-8`, `md-arity-12` (all three **unchanged**) and the new `mdr-arity-13`, `mdr-arity-15` |
| Malformed — `KV_SAVE`/`KV_LOAD` not `-` | `R6M_KV_UNSUPPORTED`, detail `kv[save]` / `kv[load]`, raised before any path work, save checked before load | `mdr-kv-save-unsupported`, `mdr-kv-load-unsupported` |
| Malformed — `RESIDENT` not `-` and not `dense` | `R6M_RESIDENT`, detail `resident[…]` via `bounded_detail`, raised before any path work | `mdr-resident-unknown`, `mdr-resident-empty`, `mdr-resident-weights-refused` |
| Construction — the arena | `buffer(region_bytes + MAX_TENSOR_ALIGNMENT)`, `fill_zero`, `base_mod`, `prime_window`, interior slice — the same six lines the dense window already uses on this arm, at the sum size instead of the max size | `mdr-resident-dense-1`, `mdr-resident-dense-steps` (synthetic pack, hosted), plus the runner's independent arena recomputation on the real model |
| Failure — over budget | `R6M_RESIDENT_BUDGET`, detail `bytes[<n>]`, before any allocation; also catches an overflow-poisoned `-1` total | `mdr-resident-budget`, via the lowered-limits entry point idiom |
| Failure — degraded reservation | `R5_WINDOW_UNAVAILABLE`, unchanged code on the same buffer | Fail-closed, **not input-reachable** while Request 35 stands. Deferred, section 8, on the terms `R4_WINDOW_UNAVAILABLE` already carries |
| Early exit — a failure between the fill and the wrap | One teardown, no early `return` between the arena's construction and the converged teardown | A forced-build case, `mdr-force-resident-wrap`, on `r6-resident-weights.md` correction 12's terms |
| Cleanup | Wrap freed, then backend closed, then the claim window and the plane and the arena's frame exit | Oracle B, section 4.3 |
| Success | `weights.mode == "dense"`, `weights.step_dense_pack_bytes == 0`, `weights.step_expert_pack_bytes == 487,587,840 × N` | Oracle D, section 4.4 |
| The document | `render_weights` on this arm, schema 2, called unconditionally so error documents carry it | Every golden row |
| Threading | `borrow window: slice<u8>` + `borrow layout: ResidentLayout` + `resident: bool` through the prefill pass, the decode pass, the decode loop, and the head pass, exactly as `src/decode_step.align` threads them | Compilation, plus oracle P |

### 5.2 `src/moe_model_forward.align` — the routed layout and the fill

| Cell | Implementation | Regression |
| --- | --- | --- |
| The sum layout | `plan_resident_dense`, section 3.5 — a walk of `[table][stage][layer 0..15][head]` with `align_up` per region, reading **`p.layer_window_bytes[]`** (the aligned sum) and **not** `p.layer_member_bytes[]`, and `layer_olmoe.MAX_PREFILL_TOKENS` for the stage | The runner's independent walk of the pack document's 147 dense member records on the **real** model, asserting 311,066,624; and `RESIDENT_TABLE_BYTES` / `RESIDENT_STAGE_BYTES` structurally in the hosted lane |
| `steps[].residency.dense_bytes` | **Unchanged**, and it keeps reading `p.layer_member_bytes[layer]` — the raw sum, which is what a graph needs rather than what the arena reserves. The two coincide on this model (section 2.1) and the cells are kept separate anyway | Section 4.4 |
| Streaming mode | `model_forward.stream_layout(dense_window_bytes, n_layer)` — every base 0, every span the whole window, so both modes travel one code path | Oracle D; the streamed leg's goldens unchanged |
| The fill, once | `fill_resident_dense`: the table by `read_into_window`, then per layer `fill_members` into `window[base[1+layer] .. +span]`, then the head. **The stage is never filled from the pack** | `weights.fill_pread_count`, `weights.fill_bytes == 311,027,712`, oracle D |
| The per-graph fill, not made | `if !resident { fill_members(...) }` at the layer and head sites; `if resident { stage_embed_row(...) } else { fill_members(...) }` at the embedding site | `weights.step_dense_pack_bytes == 0` |
| The claim path | **Byte-unchanged.** `size_claim_window`, `read_block_scatter`, the per-layer claim fill, `R5E_CLAIM_OVERFLOW` | Section 4.4's invariant, on both legs |
| Malformed — a member whose span exceeds the arena | Existing `R5_SHAPE` and the existing slice bounds; no new code | Unchanged |
| `--moe-layer-forward`, `--moe-model-forward` | **Byte-unchanged in behaviour.** `dense` mode is reachable only from `--moe-decode-step` | `moe-layer-forward-qualification`, `moe-model-forward-qualification` re-run unchanged |

### 5.3 `src/model_forward.align` — the shared arena code, and the Request 49 boundary

**Byte-unchanged, and that is a contract rather than an omission.** `plan_resident`,
`stream_layout`, `empty_resident_layout`, `ResidentLayout`, `stage_embed_row`, `read_into_window`,
`window_put`, `prime_window`, `base_mod`, `fill_zero`, `graph_weights`, `graph_identity`,
`stage_window`, and `fill_members` are all reused **as they are**.

| Cell | Implementation | Regression |
| --- | --- | --- |
| The shared record and helpers | Reused, not modified. The routed producer is a twin in `moe_model_forward`, section 3.5 | `scripts/decode-step-golden.jsonl` all 116 rows unchanged; `decode-step-qualification` unchanged |
| Why not a shared generic producer | Align has no generics at the pin and a cross-module `borrow` call cannot be parameterized over `model_forward.Plan` and `moe_model_forward.Plan`. **Request 49's shape.** No compatibility layer, no hypothetical API | Section 9 |
| The one shared symbol whose meaning must not drift | `ResidentLayout`'s index convention — `base[0]` stage, `base[1 + layer]` layer, `base[1 + n_layer]` head. Two producers now write it and four modules read it. The convention is stated in section 2.2 and asserted by the runner on the real model for **both** arms | The dense arm's `decode-step-qualification` and this arm's `moe-decode-step-qualification`, both in the same wave |
| `stage_embed_row`'s `MAX_PREFILL_TOKENS` | The function takes `stage_bytes` as a parameter and bounds the write by it, so the constant lives in the **caller**. The routed caller passes `layout.span[0]` derived from `layer_olmoe.MAX_PREFILL_TOKENS`. No edit | `mdr-resident-stage-full`, a `dense` prefill of exactly `MAX_PREFILL_TOKENS` distinct ids |

### 5.4 `src/decode_step.align` — byte-unchanged, and why that is a cell

| Cell | Implementation | Regression |
| --- | --- | --- |
| The dense arm | **Byte-unchanged.** No operand, no code, no counter, no document field moves | `scripts/decode-step-golden.jsonl` 116 rows unchanged, `gmake layer-forward-smoke` blocks one to six unchanged |
| Why it is a cell at all | Because the design gate fired on a coordinated invariant across four modules, and the fourth module's contribution is to **not move**. A shared-code change that quietly altered the dense arm's arena would be caught here and nowhere else | `git diff --stat` shows no change to the file, and the dense arm's goldens are the assertion |

### 5.5 `src/ggml_spike.align`, `src/ggml_ffi.align`, `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`, `src/layer_olmoe.align`

**All byte-unchanged.** `buffer_from_host`, `slot_place`, and `window_copy` already express the whole
mechanism; the dispatch arm forwards `args` and does not enumerate arity; `MAX_NODE_SLOTS`, the slot
numbering, the node tables, `OP_CONCAT`, and `WHEN_DECODE` are untouched because tensors stay per
graph. The shared-region byte-identity check between shim and stub that `scripts/run-ggml-spike-smoke`
asserts does not move.

### 5.6 `scripts/run-moe-decode-step` — the qualification

| Cell | Implementation |
| --- | --- |
| Two helpers ported from the dense runner | `scripts/run-moe-decode-step` has **neither** today. `time_invocation()` (`scripts/run-decode-step:190`) and `compressor_state()` (`:125`) are ported unchanged, and the scaling block is placed after the per-prompt loop and before the aggregate render — the same position `run-decode-step:450` occupies |
| Preflight | Unchanged scratch-space and instrument preflights. **No physical-memory preflight**, section 3.9. The missing upper-bound check on `ALIGN_LLM_DECODE_STEPS` (`run-decode-step:169` has one, this runner does not) is **out of scope** and is recorded here rather than fixed in a residency capability |
| Independent arena recomputation | The runner walks the pack document's own member records — every member of every block whose `kind` is not `ExpertBlock` — applies section 2.2's `align_up` rule, and asserts the total against `weights.resident_bytes`. **It does not read the arm's own output to compute the expected value**, which is the fixture co-derivation class section 7 risk 4 records |
| Oracle D | Each prompt runs `RESIDENT=-` then `RESIDENT=dense` and compares the two normalized documents with the exclusion list enumerated inline |
| The two legs, interleaved | `repeat` outside, `mode` inside, three repeats per point, `N ∈ {1, 4, 16}`, one session. The blocked order is not offered as an option |
| Compressor state | `vm_stat` (Darwin) / `/proc/vmstat` (Linux) before and after every timed run, movement printed with the result, nothing discarded |
| The floor verdict | Section 6, printed on every run with the ceiling comparison beside it |
| The `INDETERMINATE` rule | Measurement risk 2, asserted by the runner from the streamed leg's own spread |
| Skip switch | `ALIGN_LLM_MOE_RESIDENT_DENSE=0` skips the `dense` leg and prints one explicit `N/A` line, on the pattern `ALIGN_LLM_RESIDENT_WEIGHTS=0` established |
| Cleanup | The existing `trap cleanup` is unchanged and already covers every exit path including a signal |

### 5.7 `scripts/run-layer-forward-smoke` — the hosted fixture

The hosted lane runs against the **ggml-free stub**, so a resident-versus-streamed *numerical*
equality is not available there and is not claimed. The seventh block's synthetic routed cases cover:

- arity 14's acceptance and the refusal at 8, 12, 13, and 15;
- `R6M_KV_UNSUPPORTED` on each of the two reserved positions;
- `R6M_RESIDENT` on an unknown value, on the empty string, and on `weights`;
- `R6M_RESIDENT_BUDGET` through the lowered-limits path;
- `weights.mode` present in a success document and in an error document;
- `weights.resident_bytes` and `weights.fill_bytes` against the synthetic pack's own member sum,
  asserting the section 2.2 arithmetic **structurally** rather than as a constant;
- the three-consecutive-runs determinism check, unchanged, now over schema 2.

Oracle D on the real model is a **capable-only qualification** oracle, exactly as gate G is.

### 5.8 Cell MRD-P1 — the first implementation step is a probe

`R6-RESIDENT-WEIGHTS` cell RW-P1 already measured that one wrap accepts tensors from two different
`no_alloc` contexts. What it did **not** measure, because the dense arm has one weight window, is
the configuration this arm creates:

**Two live wraps at once — one long-lived wrap over the arena and one per-graph wrap over the claim
window — with tensors from the same context placed into both, computed, and the per-graph wrap freed
while the run-scope wrap stays live and is used again by the next graph.**

Extend R4.5's `probe1.align`: wrap buffer A (long-lived) and buffer B (per graph), create a context,
place one tensor into A and one into B, compute, free B and the context, then create a second
context, place a tensor into A again and a new B, compute, free. If ggml refuses the second use of A
after B's free, or if freeing B invalidates A, the arena must instead be re-wrapped per graph — which
still removes every `pread` and still clears the floor, so **the risk is to the shape of the code,
not to the claim**. Section 7 risk 2. The probe is cheap, the harness exists, and it is the cell that
makes every other cell honest.

## 6. Verification — owner, qualification, and cost

**The hosted owner** is `gmake layer-forward-smoke`, seventh block, extended per section 5.7.
Unchanged aggregate membership.

**The named qualification** is `gmake moe-decode-step-qualification`, extended with the `dense` leg,
the interleaved measurement, and oracle D. It is opt-in, real-ggml, real-model, and two-instrument,
exactly as item 32 shipped it.

**The floor verdict the runner prints**, on every run, in this shape:

```text
moe decode step qualification: MRD primary  streamed step_dense_pack_bytes 4049258496,
  dense 0 -- PASS
moe decode step qualification: MRD invariant  expert_bytes 487587840 and expert_pread_bytes
  487587840 on 16 of 16 steps in both legs, amplification 0 ppm -- PASS
moe decode step qualification: MRD arena 311066624 B, reproduced from the pack document by an
  independent walk of its 147 dense member records
moe decode step qualification: MRD floor  baseline (streamed, this session, worst of 3) ... ns,
  dense (worst of 3) ... ns, removed ... ns = ... ppm of the fixed task
  against a 150000 ppm floor: MET | BELOW FLOOR | INDETERMINATE
moe decode step qualification: MRD ceiling  the recorded cost ceiling was 276000 ppm and the
  measured result is ... ppm = ... % of it
```

**Cost.** Residency makes each `dense` run cheaper and each prompt more expensive, because every
prompt now runs twice.

| Term | Estimate |
| --- | --- |
| Streamed leg, 4 prompts × 3 repeats × 3 points (`N ∈ {1,4,16}`), ~1.5–3.7 s each | ≈ 110 s |
| `dense` leg, same shape, predicted ~1.2–2.7 s each | ≈ 80 s |
| Oracle D document comparisons | ≈ 5 s |
| Oracle C′, 12 whole prefills | ≈ 30 s, unchanged |
| Instrument captures at `-n 16` | ≈ 70 s, unchanged |
| Cell G-P1 | ≈ 1 s, unchanged |
| Packing, geometry, shim build | ≈ 25 s, unchanged |
| **Total** | **≈ 320 s warm against the 1800 s cap**; item 32 measured 1 min 23 s warm and 5 min 41 s with the page cache evicted, and the same spread applies here |

`ALIGN_LLM_DECODE_STEPS` remains the documented fallback, and `ALIGN_LLM_MOE_RESIDENT_DENSE=0`
removes the second leg entirely.

## 7. Risks

1. **A `== 1` counter assertion on a failure path reports a leak that is not there.** This is
   `r6-resident-weights.md`'s A-MAJOR review finding, and this document adopts the **repaired**
   condition in section 4.3 rather than the drafted one — the third clause is conditioned on
   `error_code` being empty. *Mitigation:* the forced-build regression `mdr-force-resident-wrap` is a
   named cell, not a note.
2. **Two live wraps may not be a configuration ggml supports.** RW-P1 measured one wrap and many
   contexts, not two wraps and one context, and this arm needs the second. *Mitigation:* cell MRD-P1
   is the first implementation step. If it fails, the arena is re-wrapped per graph — still zero
   `pread` per step, still the same primary metric, one more wrap per graph, and the run-scope
   counter pair collapses into the per-graph one. The risk is to the code's shape and to the wrap
   table in section 3.4, not to the claim.
3. **The elapsed claim may be lost in this arm's noise.** The baseline is 3.63 s where the dense
   arm's was 18.235 s, and item 32's own run-to-run spread reached 440,000 ppm on one prompt — larger
   than this capability's entire 276,000 ppm ceiling. *Mitigation:* interleaved legs, worst-of-N,
   three repeats, the pre-committed `INDETERMINATE` rule of measurement risk 2, and a primary metric
   that is a byte counter. Section 4.6 clause 12 states in advance that a failing clock does not
   withdraw the capability.
4. **Fixture co-derivation.** If the runner computed the expected arena size from the arm's own
   output, or the hosted fixture asserted a constant the implementation also produced, the check
   would prove nothing. *Mitigation:* the runner walks the **pack document's** member table
   independently (section 5.6) and the hosted lane asserts the arithmetic structurally against the
   synthetic pack (section 5.7). This is the shape `r6-resident-weights.md` section 5.2's `Shipped`
   note recorded as *stronger* than the constant it replaced.
5. **Stale numbers.** Every byte figure in this document is derived from one pack document of one
   model, and item 32's deviation 13 is the local precedent for a published number that was a
   different quantity than its name said. *Mitigation:* section 2.1's table is reproduced by the
   runner on every qualification run; a disagreement is a failure, not a note. And every number here
   is stated with its arithmetic beside it so a reader can check it without running anything.
6. **A `dense` run that silently fell back to streaming would pass most oracles.** *Mitigation:*
   three independent assertions — `weights.step_dense_pack_bytes == 0`, `weights.wrap_count == 1`,
   and `pointer_identity_failures == 0` against arena offsets — none of which a fallback can satisfy.
7. **The routed twin and the dense original drift apart.** Two producers of one `ResidentLayout`
   convention is a duplication Align's missing generics force (Request 49), and duplications diverge.
   *Mitigation:* both arms' qualifications assert the same index convention on their own real models
   in the same wave, and section 5.3 names the convention as the one shared symbol whose meaning must
   not drift. A third architecture makes this a real problem and section 8 says so.
8. **Schema and golden churn twice** if a sibling branch also moves `moe-decode-step-golden.jsonl`.
   *Mitigation:* the merge re-check `HANDOFF.md` already records — item number, schema number, next
   free request number, which goldens regenerate — is run at every `git merge origin/main`.
9. **Every number in this document is from one machine in one thermal environment**, one prompt set,
   one model, one page cache. Nothing here establishes the elapsed result on a fanned host, on a host
   with more memory, or on a Linux page cache. *Mitigation:* the primary metric is a host-independent
   byte counter; the elapsed claim is explicitly secondary and explicitly bounded. A second host is
   deferred with the rest of the platform work rather than claimed.

## 8. Deferred, with the reason each is a deferral and not an omission

- **Partial expert residency.** The capability this whole wave is for, and the one whose input is
  item 32's `steps[].routed` union curve and this capability's freed footprint. Its operand value is
  `dense+experts` or a named policy at the same `args[13]`. Not taken here because a policy that
  chooses *what* to keep is `align-runtime` work with its own eviction contract, its own hit-rate
  metric, and its own gate — and because item 32 section 12.3 measured the reuse at 5.1× to 8.4×
  rather than the probe's 9.2×, so the policy's value needs its own ceiling.
- **Whole-model residency on this arm** (`RESIDENT=weights`). Refused by name in section 3.2: it
  makes `residency.expert_bytes` unreachable.
- **Residency for `--moe-model-forward`, `--moe-layer-forward`, `--model-forward`, and
  `--layer-forward`.** They read the pack once, so the ceiling does not clear the floor. The arena
  code is reachable from `moe_model_forward`, which is precisely why the deferral is recorded rather
  than left implicit.
- **KV persistence on this arm.** Item 32 section 8's two exact couplings stand. Positions 11 and 12
  stay reserved and are refused as `R6M_KV_UNSUPPORTED`.
- **`R6M_RESIDENT_BUDGET`'s reachability.** > **Shipped:** added here after implementation, per
  section 13 item 6. The guard is fail-closed and no operand the hosted corpus can write reaches it;
  reaching it needs a lowered-limits entry point of its own, which is a second executable and a
  ceiling threaded through `execute`. Deferred on the same terms as the row below.
- **`R5_WINDOW_UNAVAILABLE`'s forced build on the arena.** Not input-reachable while Request 35
  leaves a degraded reservation unobservable; deferred on the terms `R4_WINDOW_UNAVAILABLE` and
  `R6_PLANE_UNAVAILABLE` already carry.
- **A shared generic layout producer** replacing `plan_resident` and `plan_resident_dense`. Blocked
  on Request 49; risk 7 records the cost of the duplication and names the condition (a third
  architecture) that makes it worth paying for.
- **`ggml_get_rows` over the resident embedding table**, replacing the 1,152-byte staged copy.
  Inherited from `r6-resident-weights.md` section 7, unchanged.
- **The Metal arm**, GPU residency of the arena, the plane, or the claim window; eviction, tiering,
  prefetch, NVMe residency; a cross-process weight cache; reuse of one arena across two invocations.
- **gpt-oss and any second routed architecture.**
- **Any TTFT, tokens-per-second, or throughput claim.** The R6 roadmap gate stays unmet: this
  capability shares no prefix and keys no lookup. Section 3.7 makes a bytes claim and a bounded
  elapsed claim and nothing else.

## 9. Align capability requests

Classified per `CLAUDE.md`. **None blocks this capability. No new request is proposed**, and the
numbering re-check is named rather than assumed.

| Gap | Classification | Status |
| --- | --- | --- |
| A cross-module call with a `borrow mut` argument refuses shorter-lived operands, and there are no generics to parameterize a producer over two record types | Genuine Align gap, already recorded | **Request 49, `PROPOSED`.** One more client, and a *new shape* of client: `moe_model_forward.plan_resident_dense` duplicates roughly 40 lines of `model_forward.plan_resident` purely because the two `Plan` records are different named types. Added to the request's evidence with that framing; **no status change**, `Blocking: no`, and no compatibility layer is built |
| A `Borrow` argument may be a temporary value | Genuine Align gap, already recorded | **Request 47, `PROPOSED`.** The arena's interior slice, the per-graph sub-slices, and the stage view are each bound to a named local on the preceding line, as R5E's mitigation requires. One more client |
| Same-call aliasing between a `borrow mut` owner and its own scalar field | Genuine Align gap, already recorded | **Request 48, `PROPOSED`.** `block_align`, `n_layer`, and the layout's scalars copied to locals before every call that also takes `borrow mut o`. One more client |
| No aligned heap allocation | Genuine Align gap, already recorded | **Request 33, `PROPOSED`.** In `dense` mode this arm pays the 64-byte over-reservation on the arena, the claim window, and the plane — three times, the same count as today, because the arena replaces the dense window rather than joining it. One more client; the compensation is unchanged |
| In-place replacement of owned `array<i64>` record fields | Genuine Align gap, already recorded | **Request 36, `PROPOSED`.** `ResidentLayout`'s `base`/`span` are built once and read, so this capability is a mild client. Cited, no status change |
| A `buffer` cannot be filled by one `pread` above `INT_MAX`, and there is no positional write | Genuine Align gap, already recorded | **Request 38, `PROPOSED`.** The fill chunks through `read_into_window` at `CHUNK_BYTES`. At 311 MB the chunking is 297 `pread`s rather than 4,669, so this is a **weaker** client than the dense arm; cited as continuing evidence and the priority is not raised |
| `buffer(cap)` cannot report a failed reservation and `append` cannot fail | Genuine Align gap, already recorded | **Request 35, `PROPOSED`.** Cited, **not sharpened.** At 311 MB the degrade-to-zero is an unreachable guard rather than the difference between a document and a process abort (section 3.9). This capability is deliberately recorded as a *weak* client so the request's evidence is not inflated |
| A program cannot ask the host how much physical memory it has | Genuine gap, already recorded | **Request 50, `PROPOSED`. Not a client, and section 3.9 says why.** The arena is 311 MB on a run that already reserves 347 MB, so no host inquiry and no preflight is needed. Recorded here so a reader does not count this capability as evidence for it |

**Numbering.** `HANDOFF.md` records the register ending at 52 with **53** the next free number. This
capability takes none. If implementation finds a genuine gap the design did not predict — which is
what happened to R5E, whose section 5.5 predicted no new request and produced two — it takes 53 and
this section is updated at that time. The number is re-checked at every `git merge origin/main`
rather than asserted now.

**No hypothetical surface is consumed.** Every construct this document specifies compiles against the
shipped pin.

## 10. Reconciliation drafts

Written before implementation and kept verbatim afterwards, so the prediction can be read against
the result.

### 10.1 `docs/specs/roadmap.md` — item 35

**Numbering is provisional and the re-check is named.** `main` carries items to **30**. Item **31**
is claimed by `agent/c4-repair-measured`, **32** by `agent/r6-olmoe-decode` (this branch's parent),
**33** and **34** by the branches in flight beside them — `C4-REPAIR-EDITSET` is drafted as 34. This
capability therefore drafts **35**, and re-checks the item number, the document schema number, the
next free Align request number, and which goldens regenerate at every `git merge origin/main` —
never a rebase.

> **35. R6-MOE-RESIDENT-DENSE — the dense third of a routed decode step, held resident, with the
> expert measurement unmoved.** Design in
> [`r6-moe-resident-dense.md`](r6-moe-resident-dense.md). Item 30 made a *dense* model's decode step
> read zero weight bytes and item 32 measured what a *routed* decode step reads: **740,666,496 B**,
> of which 487,587,840 is the top-8 routing decision in all sixteen layers and **253,078,656 is dense
> weight the previous step already read** — the same bytes on every step of every prompt, because the
> dense half of a routed model does not depend on the routing. This capability removes that third. It
> takes item 32's **reserved fourteenth operand**, `RESIDENT` at `args[13]` with the value `dense`
> (arity 14, with `-` required in the two reserved KV positions and `R6M_KV_UNSUPPORTED` otherwise,
> so a reserved position stays reserved), holds the pack's **147 dense members** — the 57,950,208 B
> `token_embd.weight` table, sixteen layers of attention, norms and router at
> `8 × 9,994,240 + 8 × 11,075,584 = 168,558,592`, and the 84,520,960 B head — in **one 311,066,624 B
> arena under one run-scope ggml wrap across all 578 graphs**, replacing 306 per-graph dense-window wraps with one, and leaves the 3,900,702,720 B of expert
> planes streaming through the claim window untouched. **The measurement survives, which is the whole
> point:** `steps[].residency.expert_bytes` and `expert_pread_bytes` stay **487,587,840 on every
> step in both legs** with 0 ppm read amplification, and that is an acceptance clause rather than an
> expectation. `R6_MOE_DECODE_STEP` goes to **schema 2** with a `weights` object item 32 had
> deliberately left absent; the primary metric is the new **`weights.step_dense_pack_bytes`**, exactly
> **0** in `dense` mode against **4,049,258,496** streamed at `N = 16`, while `weights.step_pack_bytes`
> keeps `r6-resident-weights.md`'s exact meaning so one name does not mean two things across two
> decode arms. **`docs/specs/r6-resident-weights.md` section 3.4 remains the owner of Track B decode
> performance**; this capability records its ceiling against it and adopts its **150,000 ppm floor
> unchanged**: baseline 3.63 s at `N = 16` on the fixed prompt, **cost ceiling 276,000 ppm**
> committed in the commit *before* the implementation commit — the process correction item 30 said it
> owed its successor — predicted 2.63 s, measured with the two legs **interleaved**, three repeats,
> **worst-of-N**, and a pre-committed `INDETERMINATE` rule for the case where this arm's 3.63 s
> baseline is noisier than the ceiling is wide. **There is no crossover:** unlike item 30, whose
> 4.68 GB fill loses at `N = 1`, this fill costs only the 57,943,296 B of embedding table the prefill
> did not already read, so `N = 1` and `N = 4` are small wins — below the floor, published as
> diagnostics, and not claimed. Peak footprint grows 347,451,392 → 573,997,056 B, a factor of 1.65
> against item 30's 9.4, **so no physical-memory preflight ships and Align Request 50 gains no
> client**. `src/decode_step.align`, `src/model_forward.align`, `src/layer_olmoe.align`,
> `src/ggml_spike.align`, and both shims are **byte-unchanged**; the one new function is
> `moe_model_forward.plan_resident_dense`, a forty-line twin of `model_forward.plan_resident` that
> Align's missing generics force (Request 49's newest and sharpest-shaped client). Correctness is
> **free**: oracle D compares the two legs' whole normalized documents outside an enumerated
> twelve-name exclusion, and gate G, oracle R, oracle B, oracle T and oracle C′ are all re-run on the
> resident leg. Owner `gmake layer-forward-smoke` seventh block; focused
> `gmake moe-decode-step-qualification`. **What it leaves open:** the R6 gate still asks that TTFT
> improve on repeated coding tasks *sharing a prefix*, and a decode loop that shares no prefix does
> not answer it; the next capability toward it is partial **expert** residency, whose input is item
> 32's union curve and this capability's freed footprint.

### 10.2 `HANDOFF.md` — the active block

> ## Active: R6-MOE-RESIDENT-DENSE (2026-08-29)
>
> Branch `agent/r6-moe-resident-dense`, stacked on `agent/r6-olmoe-decode` head `bf7c87d`, which is
> publishing as item 32. This branch takes `git merge origin/main` — **never a rebase** — when that
> lands, and re-checks the same four things: the roadmap item number (**35**; 31 is claimed by
> `agent/c4-repair-measured`, 32 by the parent branch, 34 by `C4-REPAIR-EDITSET`), the
> `R6_MOE_DECODE_STEP` schema number (**2**), the next free Align request number (**53**; this
> capability takes none), and which goldens regenerate (`scripts/moe-decode-step-golden.jsonl` only).
>
> **Capability.** The dense member set of a routed model held resident across an `N`-step decode
> loop, experts still streamed. CPU only, OLMoE-1B-7B-0125-Instruct Q4_K_M. Authoritative ledger
> `docs/specs/r6-moe-resident-dense.md`. All four design-gate triggers fire.
>
> **State.** Design complete and **committed before implementation**, in its own commit, ahead of the
> `feat` commit — which is the process correction `docs/specs/r6-resident-weights.md`'s preamble
> recorded that its successor owes. Not implemented.
>
> **Performance contract, committed with the design.** Owner `docs/specs/r6-resident-weights.md`
> section 3.4. Baseline 3.63 s (`timings.elapsed_ns`, prompt 1, `N = 16`, `KV_WIDTH` 256, reference
> host, item 32 section 12.3). Primary metric `weights.step_dense_pack_bytes`: 4,049,258,496 → **0**.
> Cost ceiling **276,000 ppm**, floor **150,000 ppm** adopted unchanged, predicted 2.63 s, margin
> 1.84×. Elapsed measured interleaved, three repeats, **worst-of-N**, `INDETERMINATE` if the streamed
> leg's own spread exceeds the ceiling.
>
> **Next actions, in order.** (1) Cell **MRD-P1**, section 5.8: two live wraps — one long-lived, one
> per graph — with tensors placed into both, the per-graph one freed, the long-lived one reused. It
> selects the shape of the code and it is three lines of R4.5's existing probe. (2)
> `src/moe_model_forward.align`: `plan_resident_dense` and `fill_resident_dense`. (3)
> `src/moe_decode_step.align`: arity 14, `R6M_KV_UNSUPPORTED`, `R6M_RESIDENT`,
> `R6M_RESIDENT_BUDGET`, the arena, the run-scope wrap and its counter pair, the `weights` object at
> schema 2, and the `window`/`layout`/`resident` threading through the four passes. (4) The seventh
> smoke block's new cases and the rewritten golden. (5) `scripts/run-moe-decode-step`: the `dense`
> leg, the interleaved measurement, oracle D, the independent arena recomputation, and the floor and
> ceiling prints.
>
> **Blockers.** None. Eight Align gaps are met and all eight are already recorded (Requests 33, 35,
> 36, 38, 47, 48, 49, 50); none blocks, Request 49 gains a new *shape* of client, and Request 50
> gains **no** client — recorded so the register is not inflated.
>
> **Constraints.** CPU only. Experts stay streamed **by design**: whole-model residency would make
> `residency.expert_bytes` unreachable and `RESIDENT=weights` is refused by name on this arm. No
> TTFT or throughput claim; the R6 gate stays unmet.
>
> **Intentional uncommitted files.** None.

### 10.3 `docs/align-development.md` — the `--moe-decode-step` arm section

Two edits inside the existing `## The `--moe-decode-step` arm` section, and its heading gains this
capability's name.

The arity sentence becomes:

> `--moe-decode-step` is selected by its exact first operand and takes five, six, seven, nine, ten,
> eleven, or **fourteen** operands. **Eight is `R6M_ARITY`**, for `--decode-step`'s own reason — a
> transcript without a width refuses itself — and **twelve, thirteen, and fifteen and above are
> `R6M_ARITY`**. Positions 11, 12, and 13 are `KV_SAVE`, `KV_LOAD`, and `RESIDENT` at the same
> indices the dense arm uses; **KV persistence is not implemented on this arm**, so the two KV
> positions must both be `-` and anything else is `R6M_KV_UNSUPPORTED` with detail `kv[save]` or
> `kv[load]`.

The paragraph that reads "**Weights are streamed and there is no `RESIDENT` operand**" is replaced
by:

> **`RESIDENT` is the fourteenth operand:** `-` (stream the weights, the shipped behaviour, and what
> an absent operand means) or **`dense`** (hold the pack's 147 dense members resident for the
> process's lifetime — the embedding table, the sixteen layers' attention, norm and router weights,
> and the output head — while the 3.9 GB of expert planes keep streaming through the claim window).
> **`weights` is refused by name** with `R6M_RESIDENT`: whole-model residency would make
> `residency.expert_bytes` unreachable, and this arm exists to publish it. Any other value, including
> the empty string, is `R6M_RESIDENT` with detail `resident[<text>]`.
>
> In `dense` mode the arm allocates one arena — **311,066,624 B** on the reference model — fills it
> once with 311,027,712 B in one pass before the first graph, wraps it **once** for the whole run
> across all **578** graphs — replacing **306** per-graph dense-window wraps with one — and places every dense tensor of every graph into a sub-slice of it. The claim
> window keeps its own buffer and its own per-graph wrap. Peak footprint of the weight windows plus
> the plane goes from 347,451,392 B to 573,997,056 B, a factor of 1.65, so **no physical-memory
> preflight is needed and none ships**; `ALIGN_LLM_MOE_RESIDENT_DENSE=0` skips the resident leg of the
> qualification and prints one explicit `N/A` line.
>
> `weights.step_dense_pack_bytes` goes from 4,049,258,496 to **0** at `N = 16` while
> `steps[].residency.expert_bytes` stays **487,587,840 on every step**, and
> `weights.step_pack_bytes` keeps `docs/specs/r6-resident-weights.md` section 3.5's exact meaning —
> pack bytes read by decode steps only — so the same field name means the same thing on both decode
> arms. `docs/specs/r6-moe-resident-dense.md` section 3.7 is the performance contract and
> `docs/specs/r6-resident-weights.md` section 3.4 remains the owner of Track B decode performance.

### 10.4 `docs/align-requests.md`

Requests 33, 35, 36, 38, 47, 48, and 49 gain this capability in their `align-llm verification`
evidence, with the framing section 9 gives each — in particular that 35 and 38 are recorded as
**weaker** clients than the dense arm's, and that 49 gains a client of a new shape. **Request 50 is
edited only to record that this capability is explicitly not a client and why**, so that a later
reader counting evidence does not count it. No new request; 53 stays free.

### 10.5 One naming ambiguity, resolved here rather than propagated

`r6-resident-weights.md` calls its residency-equality oracle "**oracle R**". `r6-olmoe-decode.md`
calls its routing-identity oracle "**oracle R**". This document runs both. The residency-equality
oracle is **oracle D** here, item 32's oracle R keeps its name unchanged, and section 4.1 says so at
the point of first use. No existing document is edited for this; the rename is local and is declared.

## 11. Author consistency pass

One pass, ledger against prose, performed before this document was committed. What it found and what
changed:

1. **The deferral reason this capability inherited was mechanically wrong.** Item 32 section 3.9
   deferred it because "`plan_resident` describes a dense `Plan`/`Ends` with a per-layer constant
   window, and a routed layer's window is not constant". `plan_resident` indexes
   `p.layer_window_bytes[layer]` per layer and has never assumed a constant window; it would compute
   OLMoE's `8 × 9,994,240 + 8 × 11,075,584` correctly. Section 3.5 replaces that reason with the
   three real obstacles — the record **type**, the `MAX_PREFILL_TOKENS` **constant**, and the second,
   routing-dependent **region**. Two of the three would have been discovered during implementation
   and the third — the constant — would have compiled silently and been wrong the day
   `layer_olmoe.MAX_PREFILL_TOKENS` moved away from `layer_qwen2`'s.
2. **The primary metric was first written as `weights.step_pack_bytes → 0`,** reusing the dense
   arm's field name. That would have made one field name mean "all weight bytes a step read" on one
   decode arm and "the dense ones only" on the other, which is exactly the two-names-for-one-thing
   failure item 32 section 3.2 refuses for seam codes, inverted. Section 3.8 now publishes
   `step_dense_pack_bytes` (the claim, → 0), `step_expert_pack_bytes` (the invariant), and
   `step_pack_bytes` (their sum, keeping `r6-resident-weights.md`'s exact meaning and therefore **not**
   zero on this arm).
3. **`steps[].residency.dense_bytes` was first listed as going to zero.** It is an *arithmetic*
   field — what the step's graph needs — and residency changes only the `pread` side. Zeroing it
   would have silently redefined a published metric across a schema bump, which is the failure class
   item 32's own deviation 13 records. Section 4.4 now fixes every `steps[].residency` field as
   **unchanged in both legs**, including `dense_bytes` at 253,078,656 and `total_bytes` at
   740,666,496.
4. **The memory ceiling was drafted with the dense arm's 12 GiB preflight and Request 50 as a
   client.** At a 311 MB arena on a run that already reserves 347 MB, the preflight is a gate that
   cannot fire and Request 50 has nothing to inquire about. Section 3.9 now states the arithmetic and
   section 9 records **not a client** by name, so the register is not inflated by a capability that
   does not use it.
5. **The floor was briefly argued down.** A ceiling of 276,000 ppm against a 150,000 ppm floor is a
   1.84× margin where the dense arm had 3.9×, and the first draft proposed a smaller floor calibrated
   on this arm's own baseline. `CLAUDE.md` says the owning performance document defines the floor a
   seam must clear; a capability lowering a floor because its own seam is small is the floor failing
   to do its job. Section 3.7 adopts 150,000 ppm unchanged, records the thinner margin as a fact, and
   adds the `INDETERMINATE` rule so that a noisy clock is reported rather than argued with.
6. **The two oracles were both called R.** Section 4.1 and section 10.5 resolve it: the
   residency-equality oracle is **oracle D** in this document.
7. **The arena size was first computed as the member sum, 311,027,712 B.** That omitted the embed
   stage and the `block_align` padding — the same omission `r6-resident-weights.md` correction 7
   records against its own draft. Section 2.2 now runs the shipped algorithm: `+ 36,864` for the
   stage and `+ 2,048` for `output`, the one dense member whose size is not a multiple of 4,096, for
   **311,066,624 B**.
8. **The ceiling first used the cold read rate.** 2.156 GB/s would have given 510,000 ppm and a
   flattering 3.4× margin. Section 3.7 uses the **fastest** warm rate measured on this arm, 3.983
   GB/s, because a faster dense read means less time to remove and therefore a smaller, harder
   ceiling. The rate, its two alternatives, and the direction of the choice are all printed.
9. **"One wrap or two" was answered before the question was asked.** The first draft simply hoisted
   the dense window's wrap and said nothing about the claim window's. Section 3.4 now decides it as a
   ledger row with six reasons and a wrap-count table, and section 5.8's probe measures the
   configuration that decision creates rather than assuming `R6-RESIDENT-WEIGHTS`'s probe covered it.
10. **The graph count was wrong by a factor of two, and so was every number derived from it.** The
    draft inherited item 32 section 3.12's `1 + (N + 1) · 17` — 290 at `N = 16` — but the shipped arm
    sets `o.graph_count = (2 · n_layer + 2) · (1 + N)` = **578**, because each routed layer is two
    graphs (phase A and phase B) and the dense window is wrapped once per *layer*, not once per
    graph. Section 3.4's wrap table is now built from the actual wrap sites — 18 dense wraps and 16
    claim wraps per pass, `ggml_buffers_created` 884 streamed against 578 in `dense` mode — and
    `weights.wrap_count` in `stream` mode is **306**, not `graph_count`. A design that had shipped
    the drafted numbers would have failed its own runner assertion on the first run.
11. **The primary metric was first specified without naming which counter it reads.** `decode_pass`
    holds two `alignpack_read.Counters` objects — one frame-local for the claim reads, feeding
    `expert_pread_bytes`, and the dense fills' own — and `o.dense_bytes_read` is a *third* quantity
    that is arithmetic rather than syscall accounting. Section 3.8 now says explicitly that
    `weights.step_dense_pack_bytes` accumulates the dense counters and not `claim_counters`, and adds
    the row that says why the arithmetic field is not the metric. Without that, "residency cannot move
    the expert measurement" would have been an assurance instead of a mechanism.
12. **`R6M_ARITY` does not exist.** Item 32's prose and `docs/align-development.md` both name it, and
    the draft's closure matrix cited it as the code the new arity boundaries raise. The source refuses
    arity lexically with `Err(Error.Invalid)` — no document, non-zero exit — and the smoke classes
    those cases `NO_DOCUMENT`. Section 3.1 now records how an arity refusal presents and this
    capability introduces no such constant; inventing one to match the prose would have been a public
    surface change nobody asked for, and correcting the prose belongs to whoever owns those two files.
13. **The oracle-D exclusion list was drafted from what "ought" to differ rather than from what does.**
    Five `residency.*` fields were on it. Every one of them is arithmetic and is therefore
    **identical** between the legs, so excluding them would have deleted five real comparisons —
    including `residency.expert_bytes_read`, which is precisely the number section 4.4 exists to
    protect. Section 4.1 now excludes ten names and one object, and states what stays inside the
    compared set and why.

## 12. Results

### 12.1 Cell MRD-P1 — two live wraps, answered before the first line of the capability

The probe of section 5.8 was the first implementation step and it **passed**. One long-lived
`ggml_backend_buffer` over a 311,066,624-byte Align region and one per-graph wrap over a
195,821,568-byte claim window were live **at the same time**; one context created a tensor placed
into each, `mul_mat` computed over the pair, the per-graph wrap was freed, and the run-scope wrap was
then used again by a second graph with a **fresh** context, at the region's far end
(`pool offset a: 311066560`, `claim offset b: 195821504`). Both graphs returned the correct product
and the bytes ggml wrote were visible through Align's own view of the region. The wrap itself cost
19,042 ns.

The design's shape therefore ships as written and section 7 risk 2's fallback — re-wrapping the
region per graph — is not taken. The probe was thrown away, as R4.5's and `R6-RESIDENT-WEIGHTS`'s
were; what it cost was one bisection against Align's reserved-word list, which is section 13 item 3.

### 12.2 The hosted owner — `gmake layer-forward-smoke`, seventh block

The seventh block gains **fifteen** no-document cases (two of them this capability's,
`mdr-arity-13` and `mdr-arity-15`) and **sixty-nine** documented cases, up from fifty-nine. It runs
against the ggml-free stub engine, so it makes no numerical resident-versus-streamed claim — but the
whole mechanism is reachable there, and every structural clause of section 4.6 is asserted on it.

| What the block measures on the synthetic corpus (`n_layer` 2, `n_expert_used` 3) | `stream` | `dense` |
| --- | --- | --- |
| `weights.mode` | `"stream"` | `"dense"` |
| `weights.step_dense_pack_bytes`, `N = 1` (`md-engine-ok` / `mdr-resident-dense-1`) | 3,904 | **0** |
| `weights.step_dense_pack_bytes`, `N = 3` (`md-steps-3` / `mdr-resident-dense-steps`) | 11,712 | **0** |
| `weights.step_expert_pack_bytes`, `N = 1` | 9,216 | **9,216** |
| `weights.step_expert_pack_bytes`, `N = 3` | 27,648 | **27,648** |
| `weights.step_pack_bytes` | 13,120 / 39,360 | 9,216 / 27,648 |
| `weights.wrap_count` (weight-region wraps) | 8 at `N = 1`, 16 at `N = 3` | **1** at both |
| `weights.resident_bytes` | 0 | 90,112 |
| `weights.fill_bytes` / `fill_pread_count` | 0 / 0 | 4,896 / 21 |
| `weights.resident_wraps_created` / `_freed` | 0 / 0 | **1 / 1** |
| `window.pointer_identity_failures` | 0 | **0** |
| `lifetime.graph_balance_failures` | 0 | **0** |

The two streamed wrap counts are section 3.4's arithmetic at the fixture's own scale —
`(n_layer + 2) x (1 + N)` = `4 x 2` and `4 x 4` — which is the same formula that gives the reference
model's 306 at `n_layer` 16 and `N` 16. `fill_bytes` 4,896 is strictly below `resident_bytes` 90,112
because the staging region is never filled from the pack, and the block asserts that inequality
rather than the constant.

**Oracle D holds on three pairs**: `md-engine-ok` against `mdr-resident-dense-1`, `md-steps-3`
against `mdr-resident-dense-steps`, and the staging-boundary case against a streamed twin run inline.
Each `dense` leg differs from its streamed twin in exactly the `RESIDENT` operand. `mdr-arity-14` is
**byte-identical** to the nine-operand `md-stub-unavailable`, which is "absence is `-`" asserted in
bytes rather than described.

**The goldens.** `scripts/moe-decode-step-golden.jsonl` goes from 59 to **69** rows. Every one of the
59 existing rows gained `"schema_version": 2` and a `weights` object and **nothing else** — checked
field by field against the committed file, not by eye. No other golden or fixture moved:
`scripts/decode-step-golden.jsonl` (116 rows), `layer-forward-golden.jsonl` (77),
`model-forward-golden.jsonl` (61), `gpu-forward-golden.jsonl` (28),
`moe-layer-forward-golden.jsonl` (80), `moe-model-forward-golden.jsonl` (98), and
`ggml-spike-golden.jsonl` (43) are byte-unchanged, which is section 5.3's and 5.4's cell.

**Four ledger mutants, each of which must kill the owner, and each of which did.** Every arm edits
one shipped line, rebuilds, and runs `gmake layer-forward-smoke`; the harness restores from a file
copy between arms (section 13 item 13).

| Mutant | The line | What caught it |
| --- | --- | --- |
| **M1** per-step dense refill (`if !resident` -> `if true`) | `decode_pass`'s layer fill | the counter alone: `a dense run read 2816 dense pack bytes in its decode steps`. Every oracle still passed, which is exactly why the metric is a syscall counter |
| **M2** wrong region base (`layout.base[1 + layer]` -> `layout.base[1]`) | `decode_pass`'s layer view | **oracle D**, on all three pairs, at `steps[].routed.layers[]`, `steps[].sha256`, `residency.union_keys_final` and eight more fields — a resident run computing a different model |
| **M3** the run-scope wrap never freed | `schedule_decode`'s teardown | `graph_balance_failures` 1 and `released_before_owner_scope_end` false, on both `dense` cases, and oracle D beside them |
| **M4** the counter condition written unconditionally (`created != 1` without the success guard) | `schedule_decode`'s balance check | `mdr-force-resident-wrap`: `a failure before the wrap existed reported 1 balance failure(s); the run-scope check is asserting presence, not balance` — which is section 7 risk 1's whole point |

M1 is the load-bearing one: it is the mutant every *correctness* oracle passes. If the primary metric
had been the arithmetic `residency.dense_bytes_read` rather than the reader's own counter, nothing in
this repository would have caught it.

### 12.3 The measurement

**Section 2's arithmetic, reproduced from the pack document alone.** Before any timed run, the
reference model was packed once and its 3,219 member records walked by section 2.2's rule,
independently of the arm and of anything the arm publishes. Every figure section 2 asserts came back
exact:

| Section 2 says | The pack document's own records say |
| --- | --- |
| `block_align` 4,096, 1,058 blocks, 3,219 members | 4,096, 1,058, 3,219 |
| dense is 34 blocks and 147 members | 34, 147 |
| `WeightBlock` 2 blocks / 3 members / 142,469,120 B | 2 / 3 / 142,469,120 |
| `AttentionBlock` 16 / 112 / 160,038,912 B | 16 / 112 / 160,038,912 |
| `RouterBlock` 16 / 32 / 8,519,680 B | 16 / 32 / 8,519,680 |
| `ExpertBlock` 1,024 / 3,072 / 3,900,702,720 B | 1,024 / 3,072 / 3,900,702,720 |
| dense member payload 311,027,712 B | 311,027,712 |
| `row_bytes` 1,152; table 57,950,208; stage 36,864; head 84,520,960 | 1,152 / 57,950,208 / 36,864 / 84,520,960 |
| two layer flavours, 9,994,240 and 11,075,584, summing to 168,558,592 | exactly two distinct values, 9,994,240 and 11,075,584, sum 168,558,592 |
| **region 311,066,624 B** | **311,066,624** |

`scripts/run-moe-decode-step` performs the same walk on every qualification run and asserts it
against `weights.resident_bytes`, so this is a shipped check and not a one-off; section 7 risk 4 is
why it reads the container rather than the arm.

MRD-RESULT-BENCH

### 12.4 Verification, exact commands and results

All on the reference host (Apple M1, 8 cores, 16 GiB, macOS 26.5.2, `darwin/arm64`), pin
`3a34febe912db5096c58c74fede36ff53f223e04`, through the repository wrapper.

| Command | Result |
| --- | --- |
| `gmake build` | PASS |
| `gmake check` | PASS |
| `gmake fmt` | PASS, no reformatting of the diff |
| `gmake format-check` | PASS |
| `gmake gate-topology-check` | PASS |
| `gmake ggml-spike-smoke` | PASS |
| `gmake layer-forward-smoke` | PASS — section 12.2, all seven blocks |
| the four ledger mutants | all four **died**; section 12.2's table |
| `git diff --check` | clean |
| `gmake moe-decode-step-qualification` | MRD-RESULT-QUAL |

**What was not run, and why.** `make ci` is not selected: this capability changes no aggregate
membership, no check topology, and no integration behaviour, and its ledger names no aggregate.
The installed platform profile is not selected for the same reason. `.align-revision` is unchanged.
The security, resource, race, fuzz, stress, mutation, and benchmark suites own boundaries this diff
does not touch. `gmake decode-step-qualification` is **not** re-run by this capability's own
authority — `src/decode_step.align` and `src/model_forward.align` are byte-unchanged here and its
116-row golden is byte-unchanged, which is section 5.4's cell; the merge with `main` moves those
files from the other side and the owner is re-run after it.

## 13. Deviations from sections 1 to 6, and corrections found during implementation

Sections 1 to 6 are the committed pre-implementation design and were not edited. Everything the
implementation found that differs from them is here.

1. **`moe_model_forward` did not import `model_forward` at all, and section 3.5's reuse list was
   partly a list of functions that were already duplicated.** That section says
   `model_forward.stream_layout`, `empty_resident_layout`, `stage_embed_row`, `read_into_window`,
   `window_put`, `prime_window`, `base_mod`, and `fill_zero` are "reused unchanged". Four of those
   eight — `read_into_window`, `window_put`, `prime_window`, `base_mod` (and `fill_zero`, and
   `fill_members`) — have had `moe_model_forward` twins since R5E, for Request 49's reason, and the
   routed arm calls its own. What ships is therefore: `model_forward.ResidentLayout`,
   `stream_layout`, `empty_resident_layout`, and `stage_embed_row` genuinely shared and reused
   byte-unchanged; everything byte-level already duplicated and left alone.
   **The build-graph consequence is real and section 5.5 did not predict it:** `import model_forward`
   is added to `src/moe_model_forward.align` and to `src/moe_decode_step.align`. It creates no cycle
   (`model_forward` imports `layer_forward`, `layer_qwen2`, `alignpack_read`, `ggml_ffi` and no
   routed module), adds no library to any link line, and `src/ggml_spike.align` already imported both
   sides — but it is a change to two modules' import graphs and it is recorded as one rather than
   left to a reader of the diff.

2. **The twin is roughly 65 lines, not 40, because three arithmetic helpers are private.**
   `model_forward`'s `mul_checked`, `add_checked`, and `align_up_checked` are `fn`, not `pub fn`, so
   `plan_resident_dense` carries character-for-character copies of all three. Section 3.5's "roughly
   40 lines" is right about the *walk* and short about the *function*. Making them `pub` would have
   edited `src/model_forward.align`, which section 5.3 makes a contract; duplicating them is the
   cheaper of the two and it is Request 49's cost showing up in a second place.

3. **`arena` is a reserved word in Align, and cell MRD-P1 walked straight into it.** The probe
   declared `fn one_graph(..., borrow arena: slice<u8>, ...)` and the compiler answered
   `expected ':'` / `expected identifier` at the parameter's column and then **thirty-one** cascading
   top-level errors on later lines, none of which contained a defect. That is exactly repro 1 of
   Align **Request 51**, filed by `R6-RESIDENT-WEIGHTS`, reproduced here by a reader who did not know
   the answer; the request gains a client and no new number is taken. Every identifier this
   capability ships uses `region`, `window`, or `resident_*`, which is ordinary code and not a
   workaround. **The word `arena` survives in this document's prose**, where it is a noun and not an
   identifier; the shipped source calls it the *region*.

4. **Cell MRD-P1 answered YES, and the code kept the shape section 3.4 decided.** Two live wraps are
   accepted: one long-lived wrap over a 311,066,624-byte region and one per-graph wrap over a
   195,821,568-byte claim window, created while the first is live, placed into from **one** context,
   computed, freed — and the long-lived wrap then reused by a second graph with a fresh context, at
   the region's far end. Both graphs computed the correct `mul_mat` and the bytes ggml wrote were
   visible through Align's own view of the region. Section 7 risk 2's fallback — re-wrapping the
   region per graph — is not taken.

5. **`run_moe_layer` and `run_moe_end_graph` needed a second handle each, which section 3.4 states as
   behaviour and not as a local.** "The graph adopts the run-scope wrap and counts nothing" is
   implemented as `weight_buffer` (what the graph places into) beside `owned_weight_buffer` (what the
   graph must free, and which stays `null` in `dense` mode), because `teardown_layer` frees whatever
   handle it is given. It is the same pair `src/decode_step.align:865` already carries under the name
   `owned_buffer`.

6. **`R6M_RESIDENT_BUDGET` ships as a fail-closed guard and is not input-reachable, so
   `mdr-resident-budget` is not among the shipped cases.** Section 5.1 named it "via the
   lowered-limits entry point idiom". That idiom — `src/alignpack_limits_smoke.align` — is a
   **second executable** driving the shipped code with lowered bounds, and reaching this guard the
   same way would mean threading a ceiling parameter through `execute` and adding a second entry
   module and a second build to `scripts/run-layer-forward-smoke`, whose one build already dominates
   that smoke's runtime. The guard covers `resident_bytes > MAX_WINDOW_BYTES` (8 GiB) and the `-1`
   that `plan_resident_dense`'s checked arithmetic poisons an unrepresentable total with; the hosted
   corpus's whole region is 114,688 B and its member sizes come from the container, so no operand the
   block can write reaches either. It is deferred on the terms `R4_WINDOW_UNAVAILABLE` and
   `R6_PLANE_UNAVAILABLE` already carry in this repository, it is listed in the smoke's
   `UNREACHED_R6M_CODES` with that reason beside it, and section 8 gains it as a named deferral.

7. **The golden went from 59 to 69 rows — section 4.7's predicted count — by a different
   composition, and the difference is recorded rather than reconciled silently.** Section 4.7
   predicted ten new rows from a list that included `mdr-resident-budget` (not shipped, item 6) and
   `mdr-resident-stage-full`, and excluded `mdr-force-resident-wrap`. What ships is:
   `mdr-arity-14`, `mdr-resident-unknown`, `mdr-resident-empty`, **`mdr-resident-case`** (new — the
   dense arm pins `ds-resident-case` and this arm had no case-sensitivity case),
   `mdr-resident-weights-refused`, `mdr-kv-save-unsupported`, `mdr-kv-load-unsupported`,
   `mdr-resident-dense-1`, `mdr-resident-dense-steps`, and `mdr-force-resident-wrap`.
   `mdr-force-resident-wrap` **does** carry a row, because this runner puts every forced case in its
   `ORDER`; `mdr-resident-stage-full` carries **none**, on the class `r6-resident-weights.md`
   deviation 9 measured — a 32-token prefill's accumulations differ in the last bit between
   macOS/arm64 and Linux/x86_64, so pinning its digests would make the golden a statement about the
   machine that regenerated it. It is asserted instead by oracle D against its own streamed twin,
   which is a within-host comparison. `mdr-arity-13` and `mdr-arity-15` carry no row, as predicted.
   **No existing row's fields changed value**: every one of the 59 gained `"schema_version": 2` and a
   `weights` object and nothing else, verified field by field against the committed file.

8. **A non-UTF-8 `RESIDENT` operand is refused lexically, which the ledger did not require.**
   `resident_detail` copies the operand into the document as a JSON scalar, and a raw non-UTF-8 byte
   there produces a document no conforming reader can decode — a malformed output from a malformed
   input. This module already applies exactly that rule to every path operand through
   `mm_valid_path`, so `run` refuses a non-UTF-8 `args[13]` with `Err(Error.Invalid)`, in the
   `NO_DOCUMENT` class. It is a **strengthening beyond the ledger** and it changes no accepted or
   named-refused value: `-`, `dense`, `weights`, and the empty string are all valid UTF-8.
   `src/decode_step.align` does **not** do this, and correcting the dense arm belongs to whoever owns
   that file rather than to a routed capability.

9. **`weights.step_pack_bytes` is rendered as the sum of its two terms rather than accumulated.**
   Section 3.8 calls it "their sum"; the implementation writes
   `o.step_dense_pack_bytes + o.step_expert_pack_bytes` at render time rather than keeping a third
   accumulator that could drift from the two it is defined by. The smoke asserts the identity on
   **every** document, which is what makes that a property rather than a coincidence.

10. **Section 3.4's wrap table is confirmed, at the fixture's own scale.** The hosted corpus has
    `n_layer` 2, so the predicted per-pass count is `2 layers + 2 ends = 4` weight-region wraps and
    the run total is `4 × (1 + N)`. The shipped goldens carry `wrap_count` **8** at `N = 1`
    (`md-engine-ok`) and **16** at `N = 3` (`md-steps-3`) in `stream` mode, and **1** in `dense` mode
    at both. The reference model's 306 and 1 are the same arithmetic at `n_layer` 16 and `N` 16.

11. **No `wrap_ns` is measured on this arm, and the field that would have carried it was removed
    rather than left unread.** `src/decode_step.align` times its wraps into `timings.wrap_ns`, and
    the first implementation here copied that. Section 3.8 enumerates the `weights` object's fields
    and does not include it, and this arm's `timings` renderer is item 32's; adding an unlisted field
    to `timings` would be a format change nobody asked for, and keeping a written-but-never-rendered
    field is worse. Both the field and its three accumulations are gone. The wrap **count** is the
    quantity the design actually makes a claim about and it is published.

12. **`weights.wrap_count` counts `buffer_from_host` **calls** over the weight region, not
    successes, and that is `src/decode_step.align`'s semantics adopted verbatim.** Section 3.8's row
    states the value on the paths a contract covers — 1 in `dense` mode, 306 streamed at `N = 16` —
    and says nothing about a refused wrap. On `mdr-force-resident-wrap` the golden therefore carries
    `wrap_count` 1 beside `resident_wraps_created` 0, which is the pair a reader wants: one attempt,
    no wrap. Diverging from the sibling arm here would have made one field name mean two things
    across two decode arms, which is exactly what section 3.8 refuses for `step_pack_bytes`.

13. **`git checkout -- src/moe_decode_step.align` discarded roughly four hundred lines of
    uncommitted implementation**, and it is recorded because the lesson is reusable rather than
    because it is interesting. The first mutant harness restored the tree between arms with
    `git checkout`, which restores from the index — and the implementation was not yet committed. The
    work was re-applied from the edit scripts and re-verified from scratch (`gmake build`,
    `gmake layer-forward-smoke`, the golden compared field by field against the committed file). The
    harness now keeps a **file copy** of the pristine source and restores with `cp`, and a mutant
    harness for uncommitted work should never use a Git command that reads the index.

## 14. Ledger and closure matrix against the diff

Every applicable cell of sections 3 and 5, mapped to where it is implemented and what proves it.
Cells that moved are marked and point at their section 13 item.

| Ledger row | In the diff | Evidence |
| --- | --- | --- |
| 3.1 arity `{5,6,7,9,10,11,14}`; 8, 12, 13, 15+ refused | `moe_decode_step.run`, one line | `mdr-arity-14` (documented), `mdr-arity-13`/`mdr-arity-15`/`md-arity-4`/`md-arity-8`/`md-arity-12` (`NO_DOCUMENT`) |
| 3.1 `src/ggml_spike.align` byte-unchanged | not in the diff | `git diff --stat` |
| 3.1 three new document-carrying codes; no `R6M_ARITY` constant | `CODE_RESIDENT`, `CODE_RESIDENT_BUDGET`, `CODE_KV_UNSUPPORTED` | the smoke's `DECLARED_R6M_CODES` set and its reached/declared reconciliation |
| 3.2 `RESIDENT` at `args[13]`; `-` and `dense` only | `moe_decode_step.run` + `execute` | `mdr-resident-unknown`, `mdr-resident-empty`, `mdr-resident-case` |
| 3.2 `weights` refused by name | `execute`'s grammar check | `mdr-resident-weights-refused`, detail `resident[weights]` asserted |
| 3.2 `KV_SAVE`/`KV_LOAD` must be `-`, save before load, both before `RESIDENT` | `execute`, before any path work | `mdr-kv-save-unsupported`, `mdr-kv-load-unsupported` (the load case also names a refusable `RESIDENT`, so precedence is asserted) |
| 3.2 absence is `-` | `run`'s three defaults | `mdr-arity-14` byte-identical to `md-stub-unavailable` |
| 3.2 `weights.mode` in every document | `render_weights`, called unconditionally | every golden row; the smoke's per-case assertion |
| 3.3 one region, over-reserved by 64, interior slice | `execute` | `mdr-resident-dense-1`, `mdr-resident-dense-steps`; the region's `% block_align == 0` assertion |
| 3.3 budget before any allocation | `execute` | **moved** — section 13 item 6; fail-closed, not input-reachable |
| 3.3 degraded reservation keeps `R5_WINDOW_UNAVAILABLE` | `execute`'s length check | fail-closed, Request 35, deferred |
| 3.3 one wrap for the whole run; claim window unchanged | `schedule_decode`; `run_moe_layer` keeps its per-graph claim wrap | `weights.wrap_count == 1` in `dense`, 8/16 in `stream`; `lifetime.ggml_buffers_created == _freed` |
| 3.4 two wraps, not one | the claim window is untouched by the hoist | cell MRD-P1 (section 13 item 4); `window.claim_placements > 0` on the `dense` leg |
| 3.5 `plan_resident_dense`, a twin | `moe_model_forward.plan_resident_dense` | **moved** — section 13 items 1 and 2 (65 lines, not 40; three private helpers copied) |
| 3.5 `model_forward.align` gains nothing | not in the diff | `git diff --stat`; `scripts/decode-step-golden.jsonl` 116 rows unchanged |
| 3.6 the whole `token_embd` table resident; `stage_embed_row` for the gather | `decode_pass` and `prefill_pass` | `weights.step_dense_pack_bytes == 0`; `mdr-resident-stage-full` at the staging boundary |
| 3.7 the performance contract | `scripts/run-moe-decode-step`'s benchmark block | section 12 |
| 3.8 schema 2 and the `weights` object | `SCHEMA_VERSION`, `render_weights`, `render` | all 69 golden rows; the smoke's identity assertion |
| 3.8 `step_dense_pack_bytes` reads the dense counters and not `claim_counters` | `decode_pass`'s two frame-local `Counters` | `mdr-resident-dense-*`: dense 0, expert unchanged |
| 3.8 `step_pack_bytes` keeps its cross-arm meaning | `render_weights` | **moved** — section 13 item 9 (rendered as the sum, asserted per document) |
| 3.8 `normalize` zeroes `fill_ns` and nothing else new | the smoke's `normalize` | the golden's non-zero `fill_pread_count`/`fill_bytes` |
| 3.9 no physical-memory preflight | `scripts/run-moe-decode-step` gains none | the runner's preflight block is unchanged |
| 3.10 ownership and teardown order | `schedule_decode`: wrap freed, then backend, then the frame's buffers | `released_before_owner_scope_end`; mutant M3 |
| 4.1 oracle D | the smoke's `normalize_resident`; the runner's own copy | `md-engine-ok` vs `mdr-resident-dense-1`, `md-steps-3` vs `mdr-resident-dense-steps`, and the staging-boundary pair; mutant M2 |
| 4.2 oracle P, new reach | `graph_identity`, unchanged | `pointer_identity_failures == 0` with `member_placements > 0` on the `dense` leg |
| 4.3 the run-scope balance, with the success-conditioned third clause | `schedule_decode` | mutants M3 and M4; `mdr-force-resident-wrap` |
| 4.4 the expert invariant | nothing changed on the claim path | `step_expert_pack_bytes` identical between the legs; every `steps[].residency` field inside oracle D's compared set |
| 5.3 `src/decode_step.align` byte-unchanged | not in the diff | `git diff --stat`; `scripts/decode-step-golden.jsonl` unchanged |
| 5.5 `ggml_ffi`, both shims, `layer_olmoe` byte-unchanged | not in the diff | `git diff --stat`; `gmake ggml-spike-smoke` |
| 5.6 the runner's two ported helpers, oracle D, the independent recomputation, the interleaved legs, the skip switch | `scripts/run-moe-decode-step` | section 12 |
| 5.7 the hosted fixture | `scripts/run-layer-forward-smoke` seventh block | `gmake layer-forward-smoke` |
| 5.8 cell MRD-P1 | a throwaway probe, not committed | section 13 item 4 |
