# R6-DECODE-KV-STEP1

Status: design contract, 2026-08-28

## 1. Decision and boundary

### 1.1 What this capability is

R5B computes a whole Qwen2 prefill and stops. Every K and V it produces is a graph-internal node
that dies with its graph, so the model can answer "what are the logits for the prompt" and cannot
answer "what are the logits for the next token". This capability ships the smallest change that
makes the second question answerable: **one decode step at `n_past = T`, reading a KV plane the
prefill produced, on CPU, on the dense Qwen2.5-Coder-7B Q4_K_M.**

Concretely it adds:

- an **Align-owned KV plane**: host bytes that carry every layer's post-RoPE K and its V across the
  graph boundary the prefill cannot cross;
- a **decode graph shape**: one token in, positions `[n_past]`, a `{KV_WIDTH, 1}` mask, and the new
  column concatenated onto the plane's columns;
- one new ggml op wrapper, `op_concat`, with its real shim body and its stub kernel;
- a **split of token ids from positions**, which are one buffer today;
- a lift of `MAX_PREFILL_TOKENS` from 6 to 8; and
- a new arm `--decode-step`, a new focused qualification, and a new golden.

### 1.2 Why a design gate is triggered

Three of the gate's four triggers fire. The change adds a **public CLI surface** (`--decode-step`
and its operand grammar); it adds an **exchanged format** (the KV plane's layout, which is a
contract between the prefill pass and the decode pass and between the arm and its fixture); and it
adds a **coordinated invariant across more than three modules** — `src/decode_step.align`,
`src/layer_qwen2.align`, `src/model_forward.align`, `src/ggml_ffi.align`, `scripts/ggml_shim.c`,
and `scripts/ggml_shim_stub.c` must agree on the plane's layout, the slot numbering, and the
op-code numbering or the arm computes a wrong answer silently.

It does **not** add an ownership/process/network boundary: the plane is ordinary Align host memory
in one process, and nothing is persisted.

### 1.3 Declared boundary

**In scope.** Dense Qwen2.5-Coder-7B Q4_K_M; CPU only; **exactly one** decode step; the plane held
in memory for the lifetime of one process; `KV_WIDTH` supplied by the caller exactly as
`--model-forward` supplies it today.

**Out of scope, declared non-goals.** More than one step; any eviction, tiering, or invalidation
policy; NVMe or GPU residency of the plane; the Metal arm; OLMoE and any routed architecture; a
growing `KV_WIDTH` (the plane is allocated once at the declared width); batch size above one;
and **any TTFT or throughput claim**. R6 is a correctness capability. Its gate is correctness, and
section 5 records timings as characterization only.

The second step is deliberately excluded. Everything a second step needs beyond the first is a
write-back of the decode graph's own K and V into the plane at column `n_past`; the first step
proves the read path, the plane layout, and the oracle, and those are what R5B section 5.4 named as
unfinished. Shipping step 1 and step *N* together would make the oracle work — which section 3
shows is the hard part — indistinguishable from the loop work.

## 2. Public-contract ledger

Fields marked `N/A` carry their reason. Every surface below is exact.

### 2.1 The arm and its operands

| Field | Contract |
| --- | --- |
| Surface | `ggml-spike --decode-step` — the first operand and nothing else selects the arm, exactly as `--layer-forward`, `--model-forward`, `--model-forward-gpu`, and `--moe-layer-forward` do (`src/ggml_spike.align:1576-1595`). The dispatch arm is inserted **above** the `starts_with("--")` catch-all at `src/ggml_spike.align:1596`, or the flag becomes `Err(Error.Invalid)` |
| Owner module | `src/decode_step.align`, new. It owns the arity guard, the validation order, the document, and the plane's lifetime. `src/ggml_spike.align` gains one `import decode_step` and the three-line dispatch arm and nothing else |
| Operand grammar | `--decode-step PACK GEOMETRY TOKENS DOCUMENT REFERENCE TRANSCRIPT KV_WIDTH LOGITS` |
| Arity | `args.len()` of 5, 6, 7, 9, or 10. `8` is `R6_ARITY`, inherited verbatim from `--model-forward`'s rule (`src/model_forward.align:4435-4436`) and for the same reason: `KV_WIDTH` travels with the transcript, so a transcript without a width refuses itself |
| `PACK` | `args[2]`, an alignpack v1 container. Non-empty, `R6_PATH` otherwise |
| `GEOMETRY` | `args[3]`, an `R1_MODEL_IR` v2 document. Non-empty, `R6_PATH` otherwise |
| `TOKENS` | `args[4]`, a comma-separated token-id list. Its **length is `T`, the prefill length**; the decode step is at `n_past = T` and its input token is defined by `NEXT` below. `1 <= T <= MAX_PREFILL_TOKENS`; `R6_TOKENS` otherwise |
| `NEXT` | **Not a separate operand.** The decoded token is the prefill's own `argmax`, computed by the arm from its own logits. Section 3.3 records why: an operand would let a caller pass a token llama.cpp did not sample, and the transcript oracle would then compare two different sequences and still report `PASS` |
| `DOCUMENT` | `args[5]`, the output path, or `-` for stdout. Optional |
| `REFERENCE` | `args[6]`, the byte-plane self-reference source. Optional |
| `TRANSCRIPT` | `args[7]`, an `llama-eval-callback` transcript, or `-`. Optional |
| `KV_WIDTH` | `args[8]`. **Fail-closed, no default**, exactly as `--model-forward` (`src/model_forward.align:2745`, `:2767-2768`). Range `T + 1 <= KV_WIDTH <= MAX_ATTENTION_WIDTH` (`src/layer_qwen2.align:1034`, value 4096). `R6_KV_WIDTH` otherwise. The lower bound is `T + 1`, not `T`: the decode step's own column must fit |
| `LOGITS` | `args[9]`, a `llama-debug --save-logits` blob. Optional. Section 3.3 records that it references the **prefill's** final position, not the step's |
| Defaults | There are none. Every optional operand is absent-or-supplied; no operand acquires a value the caller did not write |

### 2.2 The KV plane — ownership and allocation on every path

This is the capability's central object and the one the closure matrix in section 4 is built
around.

| Field | Contract |
| --- | --- |
| What it is | One Align-owned `buffer`, host memory, holding every layer's post-RoPE K and its V for positions `0 .. KV_WIDTH-1` |
| Why Align-owned | Verified, not assumed: `src/model_forward.align:1956-1958` opens **three fresh `ggml_context`s per graph** (`weight_ctx`, `input_ctx`, `graph_ctx`) and the release path frees them at the end of that graph. A tensor created in graph *g*'s context does not exist in graph *g+1*. K and V are graph-internal nodes (`src/layer_qwen2.align:1372-1414`, rows 9–12: the two `RESHAPE_3D`s and the two `ROPE`s), so **there is no ggml object that can carry them across the boundary.** The established precedent for crossing it is the residual, which is read back with `slot_get` and uploaded with `slot_set` (`src/model_forward.align:2049`, `:1575-1585`) |
| Layout | Layer-major, then tensor, then column. For layer `l` in `0..n_layer`, K occupies `[stride*(2*l) .. stride*(2*l) + stride)` and V occupies `[stride*(2*l+1) .. )`, where `stride = KV_WIDTH * n_head_kv * head_dim * 4`. Within a tensor the order is exactly ggml's own for a `{head_dim, n_head_kv, KV_WIDTH}` f32 tensor: `head_dim` fastest, then `n_head_kv`, then column |
| Size | `n_layer * 2 * KV_WIDTH * n_head_kv * head_dim * 4`. For this model at `KV_WIDTH` 256: `28 * 2 * 256 * 4 * 128 * 4` = **29,360,128 B (28 MiB exactly)** |
| Element type | f32, and only f32. `-ctk f32 -ctv f32` is already contractual on both instruments (`scripts/run-model-forward`, the flag set at its `FLAGS_P` block); a quantized plane would be a different oracle and is deferred in section 7 |
| Allocated by | `src/decode_step.align`, once, before the prefill pass begins, with `buffer(plane_bytes)`. **Never reallocated and never grown** |
| Allocation failure | The existing window discipline: the arm takes `.bytes()`, checks `.len()` against the computed `plane_bytes`, and on mismatch emits `R6_PLANE_UNAVAILABLE` — the same shape as `R4_WINDOW_UNAVAILABLE` at `src/model_forward.align:3478` |
| Initial contents | Zero-filled before the prefill writes it. Zero is not merely tidy: columns `>= T` are masked `-inf` in every graph, so a zeroed tail is the only value that can never change an answer, and a non-zero tail that *did* change an answer would be a masking bug this choice makes visible |
| Written by | The **prefill** pass, one layer at a time. Each layer graph marks its post-RoPE K and its V with `slot_mark_output` (`src/ggml_ffi.align:753-759`) before compute, and after compute reads them with `slot_get` into the plane at that layer's K and V offsets, columns `0 .. T-1`. **The two nodes are row 12 and row 10**, established by reading the table rather than by name: row 9 reshapes `n+5` and row 12 ropes it, so `n+5` is K; row 10 reshapes `n+7` and nothing ropes it, so `n+7` is V (`src/layer_qwen2.align:1390-1413`). Only Q and K are roped, which is what distinguishes them |
| Read by | The **decode** pass, one layer at a time, uploading that layer's K and V slices with `slot_set` into two new input tensors |
| Freed by | Align, at the end of `decode_step.run`'s scope. It is an ordinary `buffer`; there is no manual free and no ggml lifetime involved |
| Crossing the FFI | **By value, never by handle.** `slot_get` and `slot_set` both take `borrow bytes: slice<u8>` with an explicit `offset` and `size` and bounds-check against the slice's own `.len()` in C (`scripts/ggml_shim.c:1175-1221`). No plane pointer is ever smuggled through an `i64` |
| Aliasing | The plane is never both a `slot_get` destination and a `slot_set` source in one call. The prefill only writes it; the decode pass only reads it. This is the whole reason step 2 is out of scope: a write-back at column `n_past` would make it both, in one graph |

### 2.3 Slot numbering

| Field | Contract |
| --- | --- |
| New slots | `MF_SLOT_KPAST := 64` and `MF_SLOT_VPAST := 65` in `src/layer_qwen2.align` |
| Why 64/65 | Node slots are `MF_SLOT_NODE_BASE + row` with `MF_SLOT_NODE_BASE := 16` (`src/layer_qwen2.align:1050`) and at most 36 rows, so the prefill's high-water is 52 against a capacity of 128 — the value R5B asserts. Choosing 64/65 rather than renumbering the input block (`MF_SLOT_CUR` 12 … `MF_SLOT_OUT_IDS` 15) means **the prefill arm allocates neither slot and its `slot_high_water` stays 52**, so no existing R5A/R5B/R5C/R5D golden moves |
| New high-water | The decode arm's own `slot_high_water` is **66**, recorded in its document, asserted in its own golden, and in no other |
| Capacity | Unchanged at 128. 66 < 128, so `slot_capacity` moves nowhere |

### 2.4 The node table delta

| Field | Contract |
| --- | --- |
| Selector | A new `pub WHEN_DECODE := 4` beside `WHEN_ALWAYS`/`WHEN_LAST`/`WHEN_WIDE` (`src/layer_qwen2.align:1039` and the comment at `:487`) |
| Rows replaced | The prefill widens K and V with zeros: row 15 `CONT_3D` + row 16 `PAD` on K, row 21 `PAD` on V, each `when = WHEN_WIDE`, consumed by the `alt_a` redirects on rows 17 and 22 (`src/layer_qwen2.align:1436-1486`). **The decode step replaces zero-padding with real past.** Row 15/16 become `CONT_3D` + `CONCAT(past_k, k_cur, dim=1)` then `PAD` to `KV_WIDTH`; row 21 becomes `CONCAT(past_v, v_cur, dim=0)` then `PAD`. The `alt_a` redirect mechanism is unchanged — only what the redirected slot holds changes |
| Concat axis | K is `{head_dim, tokens, n_head_kv}` after row 15's `CONT_3D`, so the column axis is **1**. V is `{tokens, head_dim, n_head_kv}` after row 20's `CONT_3D`, so its column axis is **0**. The two axes differ and the ledger says so explicitly, because a single shared constant here would be a silent transpose |
| Positions | Row 11 and row 12 `ROPE` take `MF_SLOT_POS` unchanged. Only the **contents** of that slot change: `[n_past]`, one i32, instead of `[0 .. T-1]` |
| Mask | `{KV_WIDTH, 1}` — one row, `0.0` for columns `0 ..= n_past`, `-inf` above. Section 2.6 gives the writer |
| Node count | Derived, not asserted from thin air: the decode layer issues the same rows as a wide prefill layer with one `PAD` exchanged for a `CONCAT` on each of K and V, i.e. **the same count**, 34 per layer and 36 at layer 27. The arm records `graph.node_count_total` and the golden is written from the first passing run, exactly as every prior arm's was |
| Last-layer narrowing | The two `WHEN_LAST` rows (`get_rows(x, [t-1])`) are **kept** at `t = 1`, where they are the identity. Keeping them costs two redundant nodes and keeps one row table for both passes; dropping them would fork the table for no arithmetic gain. llama.cpp's own decode graph has no narrowing at all (its tensors are already one column), so the two nodes have no counterpart in the transcript and are declared excluded from oracle A rather than left to mismatch |

### 2.5 The one new FFI symbol

| Field | Contract |
| --- | --- |
| Symbol | `align_ggml_op_concat(ctx: raw, slots: slice<u8>, out: i64, a: i64, b: i64, dim: i32) -> i32` |
| Align declaration | One new commented sub-block inside the single `extern "C" link("align_ggml_shim")` block, which opens at `src/ggml_ffi.align:139` and closes at `:260`. It must be there and nowhere else: `scripts/run-layer-forward-smoke:75-86` fails the build if an `extern` or an `unsafe {` appears outside `src/ggml_ffi.align` |
| Align wrapper | `pub fn op_concat(ctx, borrow slots, out, a, b, dim: i64, label: str) -> Result<(), Fault>`, modelled on `op_argsort` (`src/ggml_ffi.align:917-926`): validate `dim` in `[0, 3]` and return `Err(r5_fault(STATUS_INIT, label))` otherwise, then narrow `dim as i32` at the call |
| Real shim | `scripts/ggml_shim.c`, **outside** the shared-contract region (`:38-509`), beside the other one-op wrappers. `sb` is fetched before `ALIGN_GGML_OP_PROLOGUE_1` (`:1239-1243`) because the macro emits declarations. Returns `ALIGN_GGML_SHAPE` when any axis other than `dim` differs, then `ggml_concat`, then `align_ggml_slot_store` |
| Stub | `scripts/ggml_shim_stub.c`: `#define ALIGN_STUB_OP_CONCAT 16` after `:639`; a materializing kernel `case` before the `default:` at `:1053`; an entry point that computes the concatenated shape and calls `align_stub_bind`, carrying `dim` in `t->ip[0]`. Stub rule 2 (`:603-605`) forbids a stride trick — the kernel copies |
| Op code | `pub OP_CONCAT := 16` in `src/layer_qwen2.align`, mirroring `ALIGN_STUB_OP_CONCAT` one-for-one as every other op does |
| Dispatchers | One `op_label` arm and one node-walk arm per consuming module — the exemplar to imitate is `OP_PAD`, the previous single-op addition, at `src/model_forward.align:1457` |
| Shared region | **Untouched**, unless a shared bound constant is needed. `scripts/run-layer-forward-smoke:57-64` and `scripts/run-ggml-spike-smoke:55-62` fail if the two files' regions differ by one byte |
| `build-ggml-shim` | **No change.** It enumerates no symbols; there is no export list, no version script, and no symbol count anywhere |
| `abi.table_drift` | **Unaffected.** It is a 25-row ggml *type* table (`scripts/ggml_shim.c:95-96`), not a symbol table. `concat` introduces no new ggml type |
| Uploading the plane | **Needs no new symbol.** `slot_set` (`src/ggml_ffi.align:727-738`) already writes Align host bytes into a slot's tensor with an offset and a size |

### 2.6 Splitting ids from positions

| Field | Contract |
| --- | --- |
| Today | `src/model_forward.align:3437-3445` builds one `index_image` buffer of `0 .. T-1` and its own comment says it is "the gathered ids remapped to `0..T-1` … and the positions, **which are the same vector**". `graph_input_values` then passes that one `positions` parameter as `inp_tokens` for `GRAPH_EMBED` and as `inp_pos` for a layer (`src/model_forward.align:1573-1582`) |
| Why it must split | At a decode step the two are numerically different for the first time. The embedding row index is the **plane-window row** for the decoded token; the position is **`n_past`**. Reusing one buffer would rope the new token at position 0 and produce a confidently wrong answer that every shape check passes |
| Change | `graph_input_values` gains a distinct `borrow token_ids: slice<u8>` parameter; `positions` keeps its name and becomes positions only. The prefill path passes the same two buffers it builds today, so **its behaviour is unchanged** and its goldens do not move |
| Decode values | `token_ids` is the one gathered row index of the decoded token; `positions` is the single i32 `n_past` |
| Mask writer | `mf_write_mask` (`src/layer_qwen2.align:1848-1861`) writes `col <= row` and is correct only when row *r* means position *r*. A decode row is position `n_past` while `row` is 0. A new `pub fn mf_write_mask_offset(window, width, height, row_offset)` writes `col <= row + row_offset`; `mf_write_mask` becomes the `row_offset = 0` case so the prefill's bytes are unchanged by construction |

### 2.7 `MAX_PREFILL_TOKENS`

| Field | Contract |
| --- | --- |
| Today | `src/layer_qwen2.align:43`, value **6**, and its comment says the cap is "the oracle's, not the arithmetic's": `llama-eval-callback` prints every row of a tensor only while `ne1 <= 6` |
| Change | **6 → 8** |
| Why the cap still holds | The reason for 6 is unchanged and still respected. The decode graph's per-token tensors have `ne1 = 1`, so the instrument prints them **in full** at any `T`. The cap now binds only the prefill pass; at `T = 7` a prefill tensor prints 3+3 of 7 rows, which is why section 3.3 does not use a 7-token prefill as an acceptance oracle |
| Why 8 and not 7 | 7 is the smallest value this capability's own fixtures need; 8 leaves one position of headroom so that adding the second step does not immediately re-open a shared constant. It is not a claim that 8 rows are fully printed — they are not |
| **The prefill oracles fail closed above 6** | **New code `R5_ORACLE_TRUNCATED`, owned by the two prefill arms.** The paragraph above is a reason not to *use* a 7-token prefill as an oracle; on its own it is not a mechanism, and the lift would otherwise let `--layer-forward` and `--model-forward` accept `T` of 7 or 8 **with a transcript** and report `PASS` over the six rows `printed_count` clamps to. Both arms therefore refuse that combination at their token stage, before any container or graph work: `o.transcript_present && tokens.count > TRUNCATION_PRINTED` is `R5_ORACLE_TRUNCATED` with detail `tokens[<n>]`. Without a transcript the same token count is admitted, which is precisely what R6 needs — the runner's oracle-C `--model-forward` runs at `T + 1` tokens with `-` in the transcript position. Regressions: `lf-tokens-seven-transcript` and `mf-tokens-seven-transcript` (refused), `lf-tokens-eight-no-transcript` and `mf-tokens-eight-no-transcript` (admitted) |
| `layer_olmoe.align:67` | **Unchanged at 6.** OLMoE is a declared non-goal and a shared lift would widen an arm this capability does not test |

### 2.8 Results, errors, and validation order

Validation is strictly ordered; each step runs only if every earlier one passed. The arm's own
codes are `R6_*`; the ggml seam's `R5_*` codes reach the document unchanged through
`r5_code_for` (`src/ggml_ffi.align:119-133`), which is total and needs no edit.

| # | Step | Code on failure | Detail |
| --- | --- | --- | --- |
| 1 | arm selected, arity in {5,6,7,9,10} | `R6_ARITY` | `operands[<n>]` |
| 2 | every supplied path non-empty and of sane length | `R6_PATH` | the operand's name |
| 3 | `TOKENS` parses, `1 <= T <= MAX_PREFILL_TOKENS` | `R6_TOKENS` | `count[<n>]` |
| 3a | geometry file is readable at all | `R6_GEOMETRY_UNREADABLE` | the `fs` error name |
| 4 | geometry document loads and is `R1_MODEL_IR` v2 | `R6_GEOMETRY` | the field |
| 5 | geometry is dense — `n_expert == 0` | `R6_ARCH_UNSUPPORTED` | `n_expert[<n>]` |
| 6 | `KV_WIDTH` parses, `T + 1 <= KV_WIDTH <= MAX_ATTENTION_WIDTH` | `R6_KV_WIDTH` | `kv_width[<n>]` |
| 7 | pack opens and every needed member is present | `R6_BLOCK_MISSING` | `layer[<n>]role[<n>]` |
| 8 | plane sizes computed; `buffer` view length matches | `R6_PLANE_UNAVAILABLE` | `plane[<n>]` |
| 9 | prefill pass — ggml construction, alloc, compute | `R5_GGML_INIT`, `R5_ALLOC`, `R5_COMPUTE`, `R5_SLOT`, `R5_ALIGNMENT` | as R5B |
| 10 | plane readback — every layer's K and V bytes land | `R6_PLANE_WRITE` | `layer[<n>]tensor[k\|v]` |
| 11 | decode pass — same ggml codes as step 9 | `R5_*` | as R5B |
| 12 | plane round-trip — the decode graph's past columns equal the bytes written | `R6_PLANE_MISMATCH` | `layer[<n>]tensor[k\|v]col[<n>]` |
| 13 | transcript oracle, when a transcript was supplied | `R6_TRANSCRIPT` | the malformed line |
| 13a | the transcript's **second** graph named at least one comparable node | `R6_ORACLE_MISSING` | `layer[<n>]node[<id>]`, or `elements[0]` when the whole comparison is empty |
| 14 | transcript's declared width equals `KV_WIDTH` | `R6_KV_WIDTH` | `kq[<n>]ne0[<n>]` |
| 15 | self-reference byte plane, when supplied | `R6_REFERENCE_MISMATCH` | `node[<id>]` |
| 16 | logits blob, when supplied | `R6_LOGITS` | `bytes[<n>]` |

Steps 3a and 13a are the two codes the first draft of this table omitted; both are shipped and both
have a case (`ds-geometry-unreadable`, `ds-transcript-onegraph`). Step 13a is not decoration: the
arm skips the transcript's first graph by contract, so a prefill-only transcript would otherwise
compare nothing and report a verdict about it.

`R6_PLANE_MISMATCH` (step 12) is the one code with no R5 ancestor and it is the capability's own
acceptance check: see section 3.3, oracle B. Its shipped regression is the forced build
`engine+plane-stage-offset` (section 4.2).

### 2.9 Document, schema, and identity

| Field | Contract |
| --- | --- |
| `kind` | `R6_DECODE_STEP` |
| `schema_version` | **1**. New document kind, so it starts at 1 |
| Shape | R5B's document with three additions: a `plane` object (`bytes`, `stride`, `layers`, `columns_written`, `readback_ns`, `upload_ns`, `roundtrip_verdict`, `roundtrip_bytes_compared`), a `decode` object (`n_past`, `token_id`, `argmax`, `top_k`, `sha256`, `bit_sum`), and `oracle_decode` (section 3.3's oracle A) |
| Float fields | Never floats on the wire. `sha256` over exact little-endian f32 bytes, `bit_sum` over the same, tolerances in integer ten-thousandths — R5B's rule at its section on digests, unchanged |
| Persisted identity | **N/A — nothing is persisted, and "persisted" is the wrong word for this plane anywhere it appears.** (The first commit's subject line says "a persisted KV plane"; it means *held across the graph boundary*, which is what section 2.2 calls it, and the subject line is history that cannot be corrected in place.) The plane lives in one process's memory for the duration of one `run` call and is never written to disk, never memory-mapped, never named, and never reused across invocations. There is consequently no cache key, no generation counter, and no compatibility rule to break. This is a deliberate scope choice, not an oversight: a persisted plane is a residency question and section 7 defers it |
| Cache identity | **N/A**, same reason |
| Timing fields | Zeroed by the smoke's `normalize` before the golden compare, as every prior arm's are (`scripts/run-layer-forward-smoke:404-412`) |

### 2.10 Prerequisites

| Prerequisite | State |
| --- | --- |
| An alignpack v1 pack and an `R1_MODEL_IR` v2 document | Shipped (R4, R1) |
| A whole-model prefill whose logits are byte-identical to llama.cpp at a matched width | Shipped (R5B) |
| A decode-graph instrument | **Shipped (R2C), and this is its first consumer.** R2C section 1 names "a bounded R6 decode workload" as its first next consumer |
| `llama-eval-callback`, R2C-patched, at the pin | Required for the qualification |
| `llama-debug` at build 10566 | Required for the qualification, and section 3.2 records exactly what it can and cannot supply |
| Align language features | None new. Section 6 lists the gaps encountered; none blocks this capability |

### 2.11 Acceptance evidence and metrics

**The shipped acceptance rule, stated once.** Three oracles, and **all three are acceptance** — the
design proposed C as characterization and section 5.1 records the measurement that promoted it. In
the exact form `scripts/run-decode-step` implements:

> Oracle B must be `IDENTICAL` on every prompt, and oracle C must be byte-identical on every prompt,
> unconditionally. Oracle A must be `PASS`, **or** `FAIL` with **both** of `max_abs_diff <= 5000`
> ten-thousandths (section 3.4's characterization bound) **and** oracle C byte-identical on that
> prompt. Any other combination fails the qualification.

Oracle C's byte identity is therefore load-bearing twice: on its own, and again as the condition
that attributes an A `FAIL` to llama.cpp's own decode-versus-prefill kernel selection rather than to
this arm's arithmetic. Sections 3.3, 3.4, 5.1, and 10.2 refer to this rule; they do not restate it.

| Claim | Evidence |
| --- | --- |
| The decode step is arithmetically right | Oracle A: every comparable node of llama.cpp's own decode graph matches at 1 ten-thousandth, 28 layers plus the head, four prompts × three runs, admitted under the rule above |
| The plane crosses the graph boundary losslessly | Oracle B: `roundtrip_verdict == "IDENTICAL"`, every written byte of all 28 layers' K and V equal on read-back, `R6_PLANE_MISMATCH` unreachable in a passing run |
| The step is the `T+1` prefill's own final position | Oracle C, **acceptance**: the arm's `--decode-step` logits at `n_past = T` are byte-identical to its own `--model-forward` logits at `TOKENS,<decoded>` and the same width, on every prompt |
| The arm is deterministic | Three consecutive runs byte-identical, the check every prior arm carries (`scripts/run-layer-forward-smoke:613-617`) |
| The failure paths are real | Every `R6_*` code reachable, each by a named forced build or malformed input, asserted in the golden beside the document |
| Cost | Characterization only: `plane.bytes` 29,360,128; `plane.readback_ns`; `plane.upload_ns`; decode-graph `compute_ns` against the prefill's. **No TTFT claim, no optimization claim, no comparison to llama.cpp's wall time** |

## 3. Oracles

### 3.1 The probe, and its result

The design brief carried one unverified assumption: that `llama-debug --save-logits -n 1` writes a
second blob holding the step-1 logits. **It was probed and it is false.** Both by source reading and
by running it:

```text
$ llama-debug -m qwen2.5-coder-7b-instruct-q4_k_m.gguf -p "def add(a, b):" \
    -n 1 -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512 \
    --save-logits --logits-output-dir lg
Token ids (6): def(750) add(912) (a(2877) ,(11) b(293) ):(1648)
Data saved to lg/llamacpp-qwen2.5-coder-7b-instruct-q4_k_m.bin
Data saved to lg/llamacpp-qwen2.5-coder-7b-instruct-q4_k_m.txt
Prompt saved to lg/llamacpp-qwen2.5-coder-7b-instruct-q4_k_m-prompt.txt
Tokens saved to lg/llamacpp-qwen2.5-coder-7b-instruct-q4_k_m-tokens.bin
```

Exactly **four files, one logits blob**: `.bin` of 608,256 B = 152,064 f32, `.txt` (the same values
as text), `-prompt.txt`, and `-tokens.bin` of 24 B = six i32. There is no second blob.

The source says why, and says it more strongly than the file listing does.
`examples/debug/debug.cpp`'s `run()` performs **exactly one** `llama_decode` over the whole prompt
and then saves `llama_get_logits_ith(ctx, tokens.size() - 1)` — the prefill's final position.
`params.n_predict` is never read. **`-n 1` is inert for `llama-debug`.** And the R2C patch
(`patches/llama.cpp/r2c-decode-instrument.patch`) touches exactly `common/debug.cpp` and
`examples/eval-callback/eval-callback.cpp`; it adds the sampling-and-decode loop to
*eval-callback only*. R5B section 5.4 had already recorded the same fact in prose —
"`llama-debug --save-logits` publishes only the final position" — and the probe confirms it.

**Instrument provenance is load-bearing, and this was found the hard way.** The Homebrew
`llama.cpp 0.2.0 (build 10566, commit bb4caa754)` — the exact `.llama-revision` pin — reproduces
R5B's recorded reference exactly:
`sha256 d2e48620ae3e31e2066a6172aa32c19c974d996d232ab91b118335e3d245bf74`.
A locally configured source build of the same commit with `-DGGML_METAL=OFF` produced
`sha256 580bc24232b7203797f142281e32dbda30fc10bc2e1b40426d8542552e88f4dd` for the same 608,256
bytes. **The blob is build-sensitive.** The qualification therefore uses the pinned instrument that
`scripts/run-model-forward` already resolves, and section 6 records this as a risk.

Two further probe findings, neither of which was in the brief and both of which change the design:

**The decode graph exists, and it is the second of exactly two graphs.**
`llama-eval-callback -n 1` on this prompt emits one prefill graph (`inp_tokens{6,1,1,1}`) and one
decode graph (`inp_tokens{1,1,1,1}`). The decode graph's shapes are exactly what section 2.4
specifies: `cache_k_l0 (view) (permuted) = {128, 256, 4}`, `attn_inp_kq_mask = {256, 1, 1, 1}`,
`kq-0 = MUL_MAT(cache_k{128,256,4}, Qcur{128,1,28}) = {256, 1, 28}`. **llama.cpp's KV width is 256
in the decode graph and in the prefill graph alike**, so a matched-width comparison is available.

**The decode graph is not reproducible unless the sampler is pinned.** R2C section 2.2 requires a
qualification to fix "a fixed model, prompt, seed, and expected graph count", and the probe shows
why in the strongest terms. Two runs with default sampling parameters produced **byte-identical
prefill graphs and different decode graphs** — they diverge at the decode graph's very first node,
because a different token was sampled:

```text
$ cmp head-28511 run_default.txt  head-28511 run_greedy.txt      # the prefill graph
(identical)
$ diff <(sed -n '28512,28530p' greedy) <(sed -n '28512,28530p' default)
<     sum = 1.153733
>     sum = -1.364160
```

With `--temp 0 -s 0` two consecutive runs were **byte-identical over both graphs**. The
qualification therefore pins `--temp 0 -s 0`, which makes the decoded token the prefill's `argmax`,
**671**, independent of the seed — and that is why section 2.1 derives `NEXT` from the arm's own
argmax instead of taking it as an operand.

### 3.2 What is available, and one thing that is not

> **Read section 5.1 with this section.** Everything measured below is correct and was re-measured
> at the repair head. Its *conclusion* — that no byte-exact reference exists for a decode step — was
> **falsified for this arm** by the real-model run: our decode step at `n_past = T`, our own
> single-shot `T+1` prefill, and `llama-debug`'s blob on the extended prompt are the **same 608,256
> bytes**. The divergence this section measures is llama.cpp's own, between its two paths, and this
> arm's two paths do not have it. Section 5.1 gives the three digests and the reason, and section
> 2.11 states the acceptance rule that follows. Do not cite the paragraph below as a limit of this
> capability without citing that one.

An external **byte-exact** logits reference for the decode step would be the best possible
acceptance criterion, and it is the standard R5B set. It is worth stating precisely why it is not
available, because a plausible route exists and it was tested and rejected.

Token 671 is `" #"`, so the prompt `"def add(a, b): #"` should tokenize to the six prefill tokens
plus the sampled token. **It does**, exactly:

```text
$ llama-debug -m MODEL -p "def add(a, b): #" ... --save-logits
Token ids (7): def(750) add(912) (a(2877) ,(11) b(293) ):(1648) #(671)
```

That yields a 608,256-byte blob of llama.cpp's logits at position 6 — apparently an external
byte-exact reference for the decode step. **It is not one.** llama.cpp's own single-shot 7-token
prefill and its own incremental decode step disagree:

| Quantity | decode step (graph 2) | 7-token prefill, position 6 |
| --- | --- | --- |
| first three logits | `4.3862, 1.8351, 1.9865` | `4.4403, 1.8092, 2.0117` |
| last three logits | `-7.0827` ×3 | `-7.1015` ×3 |
| f32 sequential sum | `-418463.437500` | `-418214.812500` |

Max `|Δ|` on the printed logits is about **0.054**, five hundred times the 1-ten-thousandth
transcript tolerance. Comparing the two transcripts node by node over the 553 unambiguously aligned
per-token vectors (decode `{N,1,1,1}` against prefill `{N,7,1,1}`, last printed row = token 6) gives
the whole curve:

| Node | max `\|Δ\|` over printed values |
| --- | --- |
| `attn_norm-0` … `l_out-7` | **0.0000** (172 of 553 nodes are exactly 0) |
| `l_out-8` | 0.0045 |
| `l_out-9` | 0.0179 |
| `l_out-14` | 0.0337 |
| `l_out-19` | 0.0554 |
| `l_out-23` | 0.1229 |
| `ffn_inp-26` | **0.1699** (the maximum) |

The cause is not a bug and not a cache difference: the K and V for positions 0–5 are the same bytes
in both. It is **batch-size-dependent kernel selection**: `MUL_MAT` with a 7-column right operand
takes a different accumulation path from the same op with a 1-column right operand, and the
difference compounds through 28 layers. The first eight layers agree to four printed decimals
because the divergence is still below 0.00005 there. The mechanism is inferred rather than measured
directly — the evidence for it is the shape of the curve above plus the `LLAMAFILE = 1` line this
build prints in its own header, quoted in section 3.1's probe beside `cache_k_l0 (view) (permuted)`
— and section 7's `llama-debug` patch is what would let it be attributed rather than argued.

**Consequence as the design read it — and section 5.1 corrects it.** The proposed self-reference
— "our T=7 single-shot prefill's final position versus our KV-path step at position 6,
byte-identical on CPU at matched width" — looked unable to hold: our arm runs on the same ggml with
the same kernel-selection behaviour, so our own 7-column prefill and our own 1-column decode step
would diverge for exactly the reason llama.cpp's do. **The real-model run measured otherwise**
(section 5.1): every operand this arm hands ggml is a contiguous F32 tensor and both of its own
paths take the same kernel, so the two are byte-identical and the oracle holds. It is therefore
**acceptance** — the promotion is recorded in section 5.1 and the rule is section 2.11's — and the
paragraph above stands only as the correct measurement of *llama.cpp's* two paths.

### 3.3 The oracle set

Three oracles, **all three acceptance** in the shipped rule. Section 2.11 states that rule once and
this section describes what each oracle measures. The design proposed C as characterization only;
section 5.1 records the measurement that promoted it and section 10.2 records where it is computed.

**Oracle A — the decode transcript (external, primary, acceptance).**
`llama-eval-callback`, R2C-patched, at the pin, invoked
`-p PROMPT -n 1 -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512 --temp 0 -s 0`. The arm parses the
**second** graph and compares every node it can name against its own decode graph, at R5A's element
tolerance of **1 ten-thousandth**, the instrument's `%12.4f` print precision. This is apples to
apples: llama.cpp's single-column decode step against ours, both at KV width 256, both with the
same K and V for positions 0–5. It is the oracle R5B section 5.4 said R6's first task was to name.

Coverage: 28 layers plus `result_norm` and `result_output`. Nodes whose shape the instrument prints
ambiguously across axes — `kq`, `kq_soft_max`, and the `cache_*` views — are declared
`shape_incomparable` exactly as R5A already declares `kq` and `kq_soft_max`, and are counted as
excluded rather than silently skipped. The two identity narrowing rows of section 2.4 join that
declared set for the same reason: they have no counterpart in llama.cpp's decode graph, so they are
excluded by name and counted, never quietly dropped.

**Oracle B — the plane round trip (internal, byte-exact, acceptance).**
For every layer, the K and V bytes the decode graph actually consumed in columns `0 .. T-1` must be
**byte-identical** to the bytes the prefill pass wrote into the plane. Implementation: after the
decode graph computes, read back the concatenated K and V nodes with `slot_get` and compare their
first `T` columns against the plane region, byte for byte, all 28 layers. `roundtrip_verdict` is
`IDENTICAL` and `R6_PLANE_MISMATCH` is unreachable in a passing run.

This is the oracle that actually tests **what this capability adds**. Oracle A tests the whole
forward; oracle B tests the readback, the layout, the offsets, the upload, and the concat axis —
the six places a KV plane can be wrong. A transposed axis, an off-by-one stride, or a K/V swap
fails B loudly and might survive A's printed precision.

**Oracle C — the single-shot comparison (acceptance; proposed as characterization).**
A `T+1`-token single-shot prefill of `TOKENS,<decoded>` at the same width, compared against the
decode step's logits. The design gave it to the arm and gave it a `WITHIN` tolerance, expecting
section 3.2's divergence; **it is computed by the runner from two documents** (section 10.2) and
**it is byte identity, on every prompt** (section 5.1). Section 2.11 states the rule it participates
in. Its measured-but-unused tolerance is section 3.4's.

**Determinism.** Three consecutive runs of the arm must be byte-identical, and the qualification
runs four prompts × three runs.

### 3.4 The tolerance rule

| Comparison | Rule | Value | Derivation |
| --- | --- | --- | --- |
| Oracle A, per element | absolute | **1 ten-thousandth** | The instrument prints `%12.4f`; a tighter tolerance would be comparing digits that do not exist. Inherited unchanged from R5A/R5B |
| Oracle A, per-tensor sum | absolute, then relative | **1000 millionths**, or **10 ppm** for large sums | Inherited unchanged from R5B |
| Oracle B | **byte identity** | 0 | A byte plane either survives a round trip or it does not. There is no quantity here to be approximately right about, so admitting a tolerance would only admit a bug |
| Oracle C | **byte identity** | 0 | Measured (section 5.1): this arm's decode step at `n_past = T` and its own single-shot `T+1` prefill produce the same 608,256 bytes on all four prompts. The 0.5 the design planned for is not the bound this oracle runs at |
| The 5000 ten-thousandths (0.5) bound | absolute | **5000 ten-thousandths** | Retained, but it is **oracle A's admission bound**, not oracle C's tolerance. Derived exactly as before: llama.cpp's own two paths differ by up to 0.1699 in activations and 0.054 at the logits (section 3.2), and 0.5 is a floor with roughly 3× headroom over the largest measured divergence. Section 2.11 states where it applies; it is no longer true that it "gates nothing" |
| Oracle C, argmax | equality | argmax and top-10 must agree | Implied by byte identity and reported anyway, because a future prompt where byte identity did not hold would need the weaker statement to say what it lost |

**Byte identity is claimed twice and the two claims are about different things.** Oracle B claims it
about **bytes** — a plane either survives a round trip or it does not. Oracle C claims it about
**arithmetic**, and the design did not expect to be able to: section 3.2 argued the route did not
exist for a decode step, and section 5.1 measured that for this arm it does. The prefill's own
logits oracle against `llama-debug` is R5B's, unchanged, and is a third byte-identity claim
inherited rather than added here.

## 4. Closure matrix

Every cell names the implementation and the exact regression that covers it. `T` is the prefill
length; the arm under test is `--decode-step`.

### 4.1 `src/decode_step.align` — the arm

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `run` parses operands, loads geometry, sizes the plane, allocates it zeroed | `ds-engine-ok` (golden) asserts `plane.bytes == 512`/`stride == 128` on the hosted geometry; the qualification asserts `plane.bytes == 29360128` at width 256. There is no `ds-plane-bytes` case: the assertion is a property of every engine row, not a row of its own |
| Success | prefill pass → plane → decode pass → document, `status: ok`, exit 0 | `ds-engine-ok`; qualification asserts `oracle_decode.verdict == "PASS"` |
| Failure | steps 9 and 11 of section 2.8 propagate `R5_*` from the seam | `ds-force-init`, `ds-force-alloc`, `ds-force-compute` via `ALIGN_LLM_GGML_FORCE` |
| Malformed input | steps 1–8 of section 2.8 | `ds-arity-3`, `ds-arity-8`, `ds-arity-11`, `ds-path-*-empty`, `ds-path-long`, `ds-tokens-empty`, `ds-tokens-trailing`, `ds-tokens-nine`, `ds-tokens-oob`, `ds-geometry-missing-n_layer`, `ds-kv-width-absent`, `ds-kv-width-empty`, `ds-kv-width-negative`, `ds-kv-width-equal-t`, `ds-kv-width-over-max`, `ds-arm-unknown-flag` — the shipped names; the draft's `ds-arity-4`, `ds-tokens-over-max`, and `ds-kv-width-zero` were never case names |
| Early exit | any failing step emits a document with a non-empty `error_code` and a non-zero exit, and **still frees the plane** | `record()`'s universal assertion that `(returncode == 0) == (status == "ok")`; `ds-force-*` cases confirm the plane is freed by completing without leak-check failure |
| Cleanup | the plane is an ordinary `buffer` freed at scope end; ggml contexts/buffers/gallocrs balanced | `lifetime.*_created == *_freed` and `graph_balance_failures == 0`, asserted per case as R5B does |

### 4.2 The KV plane

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `buffer(plane_bytes)` zero-filled; `.bytes().len()` checked | `plane.bytes`/`plane.stride` on every engine row; the `R6_PLANE_UNAVAILABLE` guard itself is **deferred** (10.5) — no forced build reaches it |
| Success | 28 layers × K and V written at `stride`-derived offsets, columns `0..T-1` | `plane.columns_written == T`, `plane.layers == 28`; oracle B |
| Failure | a `slot_get` that does not fill the expected byte count | `R6_PLANE_WRITE`, **deferred** (10.5) — the arm's own sizing makes it unreachable and no forced build produces it |
| Malformed input | `KV_WIDTH <= T` refused before allocation | `ds-kv-width-equal-t` → `R6_KV_WIDTH` |
| Early exit | a prefill failure at layer *k* leaves layers `> k` zeroed; the arm never reads a partially written plane because step 10 gates step 11 | `ds-force-compute` asserts `error_code == "R5_COMPUTE"`, `plane.roundtrip_verdict == "-"`, and `plane.layers == 0`. It fails at the **embedding** graph, so `k` is 0 and the partially-written case at `k > 0` is **deferred** (10.5) |
| Cleanup | freed at scope end on every path | as 4.1 |

### 4.3 `src/layer_qwen2.align` — rows, slots, mask

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `WHEN_DECODE`, `OP_CONCAT := 16`, `MF_SLOT_KPAST/VPAST := 64/65`, `mf_write_mask_offset` | `ds-engine-ok`; `slot_high_water == 66` |
| Success | K concat on axis 1, V concat on axis 0, then `PAD` to `KV_WIDTH` | oracle A on `kqv_out-*`; oracle B on both tensors |
| Failure | a wrong concat axis produces a shape ggml refuses | `R5_SHAPE`, covered by the forced build `ds-force-concat-axis`; a wrong axis is a compiled-in column of the row and no operand can produce it |
| Malformed input | `mf_write_mask_offset` with `row_offset < 0` | refused at the call; met by construction and **deferred** as a case (10.5). The *positive* off-by-one is shipped: `ds-force-mask-offset` |
| Early exit | N/A — the row table is pure; it returns a row description and performs no I/O and no allocation | stated, with reason |
| Cleanup | N/A — pure, allocates nothing | stated, with reason |
| **Non-regression** | `mf_write_mask` is `mf_write_mask_offset(.., 0)`; prefill rows unchanged | **every existing R5A/R5B/R5C/R5D golden must be byte-identical after this change** — the strongest available evidence that the prefill did not move |

### 4.4 `src/model_forward.align` — the id/position split

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `graph_input_values` gains `token_ids`; callers pass two buffers | existing `mf-*` goldens unchanged |
| Success | prefill passes the same buffer twice, preserving today's behaviour exactly | `model-forward-golden.jsonl` byte-identical |
| Failure | a length mismatch between `token_ids` and `T` | `R5_SLOT` from `slot_set`'s own bounds check |
| Malformed input | covered by the callers' existing validation | existing `mf-*` malformed cases |
| Early exit | unchanged | existing |
| Cleanup | unchanged | existing |

### 4.5 `src/ggml_ffi.align`, `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | extern decl, `op_concat` wrapper, real body, stub id + kernel + entry | shared-region byte-identity check (`run-layer-forward-smoke:57-64`); `unsafe`/`extern` confinement scan (`:75-86`); no-`malloc` scan (`:65-68`) |
| Success | `ggml_concat` on the real path, a materializing copy on the stub | `ds-stub-*` cases run the whole arm with no ggml at all |
| Failure | null context → `ALIGN_GGML_INIT`; empty/out-of-range slot → `ALIGN_GGML_SLOT`; axis mismatch → `ALIGN_GGML_SHAPE` | `ds-force-init`, `ds-force-slot-range`, `ds-force-concat-axis`. There is no `ds-force-slot-empty` case: `engine+slot-empty` targets a slot this arm's schedule does not reach |
| Malformed input | `dim` outside `[0,3]` refused in Align before the call | `ggml_ffi.op_concat`'s own guard; **deferred** as a case (10.5) — `dim` is a compiled-in column of the row table |
| Early exit | every wrapper returns before any ggml call when a source slot is bad | inherited `ALIGN_GGML_OP_PROLOGUE_1` behaviour, asserted by the two forced slot cases |
| Cleanup | N/A — the shim owns no memory; the no-`malloc` scan enforces it | stated, with reason |

### 4.6 `scripts/layer_forward_fixture.py` — the reference

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | a `--decode` mode emitting a tiny-geometry two-call reference: prefill of `T`, then a step at `n_past = T` | `ds-stub-*` cases consume it |
| Success | `model_layer` gains `n_past` and `past_k`/`past_v`; `rope_neox` positions become `range(n_past, n_past+t)`; the mask becomes `(n_past+t) × t` with past columns unmasked | the emitted transcript is what `ds-stub-transcript` compares against |
| Failure | N/A — the generator is total over its own fixed inputs and reads no external file | stated, with reason |
| Malformed input | mutated fixtures: a wrong-width transcript, a prefill-only transcript, a perturbed transcript, a garbage transcript | `ds-transcript-kv-width`, `ds-transcript-onegraph`, `ds-transcript-perturbed`, `ds-transcript-garbage`. The transposed and short *plane* fixtures are replaced by the stronger forced build `ds-force-plane-stage-offset` (10.5) |
| Early exit | argv guard rejects an option-shaped operand, as today (`:818`) | existing |
| Cleanup | N/A — writes files into `OUTDIR` the harness owns and removes | stated, with reason |

### 4.7 `scripts/run-layer-forward-smoke` and `scripts/run-decode-step`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | a fifth heredoc block with its own `ARM`, four case tables, `normalize`, `ORDER` | the block's own `SystemExit(1)` |
| Success | `scripts/decode-step-golden.jsonl` matches case for case | golden compare |
| Failure | any case's document differs, or a code differs from the table's expectation | `describe_difference` output |
| Malformed input | the `NO_DOCUMENT` table — operands rejected before any file work | `ds-arity-*`, `ds-path-*` |
| Early exit | the smoke **never** skips; the qualification prints one `N/A` line naming the missing input and exits 0 | `run-decode-step`'s `na()`, mirroring `run-model-forward:33-34` |
| Cleanup | the qualification removes the pack, both instrument outputs, and the tree on **every** exit path including a signal, and restores the unforced shim | the `trap cleanup EXIT HUP INT TERM` pattern, copied from `run-model-forward` |

## 5. Verification

| Scope | Command |
| --- | --- |
| Owner, during development | `gmake layer-forward-smoke` — the owner for R5A–R5D and now R6, already a member of `HOSTED_CHECK_TARGETS` |
| Focused qualification | `gmake decode-step-qualification` → `scripts/run-decode-step`, opt-in, capable-only, **outside every aggregate** |
| Coding-baseline chain | `gmake baseline-check`, **re-recorded before publication.** This capability changes `Makefile` and `scripts/build-ggml-shim`, both of which the chain covers, so the recorded source → oracle → finalization chain at the merge base does not describe this head. Re-record it, then re-run `gmake baseline-check` at the exact publication head |
| Publication | `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke`, on the unchanged head the baseline chain was recorded against |
| Formatting | `gmake fmt` before committing Align source; `gmake format-check` and `git diff --check` clean |

**Aggregate membership is unchanged, and the Makefile change is worth its cost.** The precedent is
unambiguous: R5B, R5C, and R5D each added exactly one opt-in qualification target and extended
`run-layer-forward-smoke` in place. Because the owner stays `layer-forward-smoke`, which is already
in `HOSTED_CHECK_TARGETS` (`Makefile:18`), **`scripts/check-gate-topology`'s byte-literal `EXPECTED`
does not change** and `make ci` is not selected by a topology change. The cost is two executable
Makefile lines, one `.PHONY` word, and a comment block; the alternative — no target — would leave
the qualification invocable only by remembering a script path, which is precisely what the four
existing `*-qualification` targets exist to prevent.

The qualification asserts, at minimum, and these are the assertions `scripts/run-decode-step`
actually makes rather than a wish list: `plane.bytes == 29360128`; `plane.layers == model.n_layer`;
`plane.roundtrip_verdict == "IDENTICAL"` over a positive byte count; `oracle_decode` at
`tolerance_ten_thousandths == 1` against `instrument_graph == 2` at `instrument_kv_width == 256`,
with every named node and every layer matched, admitted under section 2.11's rule;
`oracle_logits.verdict == "IDENTICAL"` and `byte_identical`; `decode.n_past ==
selection.token_count`; `decode.token_id == output.argmax`; `decode.slot_high_water == 66` and
`graph.slot_capacity == 128`; `decode.sha256 != output.sha256`; every `lifetime.*_created ==
*_freed` with `graph_balance_failures == 0`; `abi.fp_contract_off == true`; oracle C byte-identical;
and three consecutive runs byte-identical, over four prompts. The prompt-specific values — `n_past`
6, token 671, and the graph counts — are **reported**, not asserted as constants: they are
properties of one prompt on one model, and section 5.1 is where they are recorded.

## 5.1 Result — the real-model run (2026-08-29)

`gmake decode-step-qualification` on `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (4,683,073,536 B),
Apple M1, CPU, `KV_WIDTH` 256, instruments the Homebrew `llama-debug` build 10566 (`bb4caa754`) and
the R2c-patched `llama-eval-callback` at the same commit. Four prompts, three runs each; every run's
document is byte-identical to its two siblings after the timing fields are zeroed.

| Prompt | T | tokens | decoded | oracle A | oracle B | oracle C | prefill logits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `def add(a, b):` | 6 | 750,912,2877,11,293,1648 | **671** | `FAIL`, max **2391**/1e-4 at `ffn_inp-27` | `IDENTICAL`, 688,128 B | byte-identical | `IDENTICAL` |
| `class Foo:` | 3 | 1040,33428,25 | 715 | `PASS`, max **0**/1e-4 | `IDENTICAL`, 344,064 B | byte-identical | `IDENTICAL` |
| `# TODO:` | 3 | 2,5343,25 | 2691 | `PASS`, max **0**/1e-4 | `IDENTICAL`, 344,064 B | byte-identical | `IDENTICAL` |
| `int main(` | 3 | 396,1887,7 | 526 | `PASS`, max **0**/1e-4 | `IDENTICAL`, 344,064 B | byte-identical | `IDENTICAL` |

Every run: `plane.bytes` **29,360,128**, exactly section 2.2's arithmetic; `plane.layers` 28;
`decode.slot_high_water` **66** against a capacity of 128; `graph.node_count_total` 958 for the
prefill and `decode.node_count` **1014** for the decode pass; every `lifetime.*_created` equal to
its `*_freed` with `graph_balance_failures` 0; `abi.fp_contract_off` true; `decode.token_id` equal
to the prefill's own `argmax` on all four. The decoded token for the first prompt is **671**, which
is the token section 3.1's probe measured with `--temp 0 -s 0`.

Cost, characterization only and no claim attached, from the recorded run: `plane.readback_ns`
249,625–325,915 and `plane.upload_ns` 540,960–3,634,416 across the four prompts, against a prefill
of 264–456 ms and a decode graph of 114–157 ms. The two crossings together are between 0.8 ms and
4.0 ms; the 3.6 ms upload is one prompt on one run and the other three are under 1 ms, so the figure
is load-dependent and no ratio is claimed from it.

The run was performed three times — twice around the writing of the acceptance rule, and once more
at the review-repair head. **Every recorded value above is identical across all three**: the same
decoded tokens (671, 715, 2691, 526), the same oracle A verdicts and maxima (`FAIL` at 2391 on
`ffn_inp-27` for the first prompt, `PASS` at 0 for the other three, 5,058 elements each), the same
oracle B byte counts (688,128 and 344,064), the same `plane.bytes` 29,360,128, and the same node
counts 958/1014. Oracle C is byte-identical on all four prompts in every run, with the argmax pair
agreeing (26312, 262, 1159, 11844). Only the elapsed timings moved, which is what makes them a
diagnostic: the repair-head run measured `plane.readback_ns` 108,961–386,167 and `plane.upload_ns`
882,083–1,000,464 against prefills of 252–493 ms and decode graphs of 111–127 ms, inside the ranges
the paragraph above records and confirming that the 3.6 ms upload was load, not structure.

### The finding that changes section 3.2

Section 3.2 concluded that no byte-exact external reference exists for a decode step, because
llama.cpp's own single-shot `T+1` prefill and its own incremental decode step disagree by up to
0.1699 in activations and 0.054 at the logits. **That measurement is correct and its conclusion does
not apply to this arm**, which the first prompt's failure made visible and the following three
digests settle:

```text
our --decode-step logits at n_past = 6          sha256 08fc04573429c88e289cdbea…
our --model-forward at 7 tokens, width 256      sha256 08fc04573429c88e289cdbea…
llama-debug --save-logits on "def add(a, b): #" sha256 08fc04573429c88e289cdbea…
```

All three are the **same 608,256 bytes**. **The third line is one prompt.** The first two are
oracle C and are byte-identical on all four prompts, asserted every run; the `llama-debug` leg was
measured once, by hand, on `"def add(a, b): #"`, because it needs a prompt that tokenizes to the
prefill's tokens plus the decoded one and the qualification does not construct that text. It is a
corroboration of the pair above, not a fifth assertion, and section 10.5 records the option of
making it one. Our decode step at `n_past = T` reproduces llama.cpp's own
seven-token single-shot prefill exactly, byte for byte, on the real model — which is a stronger
external acceptance than section 3.2 believed was available, and it is the one this capability
actually has.

What oracle A measures at `T = 6` is therefore **llama.cpp's own decode-versus-prefill divergence**,
not this arm's arithmetic. Section 3.2's own curve says so: it rises with depth — `l_out-19` 0.0554,
`l_out-23` 0.1229, `ffn_inp-26` 0.1699 — and the arm's worst node is `ffn_inp-27` at 0.2391, the
next point on that curve. llama.cpp's decode graph takes a different `MUL_MAT` accumulation path
from its own prefill at seven columns (`LLAMAFILE = 1`); every operand this arm hands ggml is a
contiguous F32 tensor and both of its own paths take the same one, so its decode step lands on the
prefill's answer and llama.cpp's does not.

At `T = 3` the two llama.cpp paths agree — four columns is below the point where its kernel
selection changes — and oracle A is then exactly **0** over 5,058 compared elements and 479 of 479
matched nodes. That is the strongest form of the comparison and it is what three of the four prompts
report.

**Consequence for the acceptance rule.** Oracle C is promoted from characterization to acceptance:
measured byte identity, on every prompt, unconditionally. Oracle A keeps its ten-thousandth
tolerance for the comparison it can honestly make, and an oracle A `FAIL` becomes admissible — but
only inside section 3.4's bound of 0.5 **and** with oracle C byte-identical on that prompt.
**Section 2.11 states that rule once and is the only place it is stated;**
`scripts/run-decode-step` implements it and its comment quotes it. Sections 3.3, 3.4, and 10.2
point at it rather than paraphrasing it, because the first draft of this document paraphrased it in
six places and three of them disagreed.

Section 7 gains one entry as a result: extending the R2c patch to `examples/debug/debug.cpp` would
give a byte-exact reference for the **incremental** step and would let oracle A's divergence be
attributed rather than argued. It is still the principal open decision, and the digests above mean
it is now a way to measure llama.cpp's own two paths against each other rather than the only route
to a byte-exact claim.

## 5.2 Result — the hosted owner

`gmake layer-forward-smoke`, all five blocks, on Apple M1 with no ggml, no model, and no instrument.
The fifth block is 10 no-document cases and **40** documented cases reaching **23** codes. The three
cases the review added are the forced builds of the next subsection.

- Oracle A `PASS` with `max_abs_diff_ten_thousandths` **0** over 218 elements and 37 of 37 nodes,
  against a transcript holding **two graphs** produced by a pure-Python second implementation of the
  decode step. The arm skips the first graph; the `ds-transcript-onegraph` case proves it, because a
  prefill-only transcript is `R6_ORACLE_MISSING` and not a silent comparison against the wrong graph.
- Oracle B `IDENTICAL` over 192 bytes — both tensors of both layers, all three past columns.
- `decode.slot_high_water` **66**, `graph.slot_capacity` 128, and `--model-forward`'s own
  `slot_high_water` still **52**, asserted in the same block.
- The prefill's logits digest is **byte-identical** to `--model-forward`'s at the same width, and the
  decode step's is asserted **different** from the prefill's, so a step that recomputed the prompt
  would be caught.
- Three consecutive runs byte-identical; both output forms byte-identical.

### Mutants, and the three that became shipped cases

Five source mutations, each run through the whole hosted owner and each dying with a distinct
diagnosis. The first two are shape refusals from the seam; the middle two are oracle A; the last is
oracle B doing exactly what it exists for. **Three of the five now have a shipped forced build** and
are regressions rather than a table, which is what the review asked for: a mutation someone has to
re-apply by hand is evidence that decays.

| Mutation | Result | Shipped as |
| --- | --- | --- |
| Drop the K `CONCAT` — the `PAD` consumes the new column alone | `R5_SHAPE` `node[24]` | — (no forced build; the row table is Align source) |
| Concatenate V on axis 1 instead of axis 0 | `R5_SHAPE` `node[22]` | `ds-force-concat-axis` (`engine+concat-axis`) |
| Rope the decoded token at position 0 instead of `n_past` | oracle A `FAIL`, max **8092**/1e-4, worst `q_rope-1` | **`ds-force-decode-position`** (`engine+decode-position`) |
| Write the offset mask at `n_past - 1` | oracle A `FAIL`, max **514**/1e-4, worst `kqv-1` | **`ds-force-mask-offset`** (`engine+mask-offset`) |
| Stage the K plane in V's transposed order | **`R6_PLANE_MISMATCH`** `layer[0]tensor[k]col[0]` | **`ds-force-plane-stage-offset`** (`engine+plane-stage-offset`), which shifts the staged past K by one lane rather than transposing it — the same class, reachable from the shim |

Each of the three new builds is keyed on a slot **only the decode graph writes**: 64
(`MF_SLOT_KPAST`), and 13/14 (`MF_SLOT_POS`/`MF_SLOT_MASK`) discriminated by the decode graph's
one-column shape. The smoke asserts more than the code: `ds-force-plane-stage-offset` must name
`layer 0`, tensor `k`, column `0`; the other two must be `status: ok` with an oracle A `FAIL` and an
oracle B still `IDENTICAL`, which is what says the mutation stayed inside the graph.

## 5.3 Result — the goldens that moved

Three files, and every change is named. `scripts/gpu-forward-golden.jsonl` and
`scripts/moe-layer-forward-golden.jsonl` are **byte-unchanged**, which is section 4.3's
non-regression cell met.

`scripts/layer-forward-golden.jsonl` — one row renamed and two rows added, no existing row's bytes
changed:

- `lf-tokens-seven` → `lf-tokens-nine`, section 2.7's lift (the cap is 8, so the over-cap fixture is
  nine tokens);
- `+ lf-tokens-seven-transcript`, the new `R5_ORACLE_TRUNCATED` refusal;
- `+ lf-tokens-eight-no-transcript`, the same token count admitted without a transcript, which is
  what makes the refusal about the oracle rather than about the arithmetic.

`scripts/model-forward-golden.jsonl` — the same three, one for one: `mf-tokens-seven` →
`mf-tokens-nine`, `+ mf-tokens-seven-transcript`, `+ mf-tokens-eight-no-transcript`.

`scripts/decode-step-golden.jsonl` — three rows added and **seven existing rows changed in exactly
one field**, `graph.slot_high_water`:

| Case | was | is | why |
| --- | --- | --- | --- |
| `ds-engine-source-diverged`, `ds-logits-short`, `ds-logits-missing` | 0 | 52 | the prefill completed; 52 is its own high-water |
| `ds-engine-alignment`, `ds-force-compute`, `ds-force-slot-range` | 0 | 17 | the run stopped inside the embedding graph |
| `ds-force-concat-axis` | 17 | 52 | the prefill completed and the decode graph refused |
| `+ ds-force-plane-stage-offset`, `+ ds-force-decode-position`, `+ ds-force-mask-offset` | — | new rows | section 5.2's three forced builds |

All seven are the repair of one defect and not a behaviour change anyone asked for: this module's
`account` had dropped `model_forward.account`'s `slot_high_water` maximum, so a run that failed
inside the prefill published `0` and said nothing about how far the schedule got. `ds-engine-ok`,
`ds-engine-transcript`, and every other passing row still report **66**, the maximum over the
prefill's 52 and the decode pass's 66, and `--model-forward`'s own high-water is still asserted at
**52** in the same block.


## 6. Risks

1. **Instrument provenance silently changes the answer.** Measured, not hypothesized: the same
   commit built two ways gave two different 608,256-byte blobs (section 3.1). *Mitigation:* the
   qualification uses only the pinned instrument `scripts/run-model-forward` already resolves, and
   asserts the reference blob's own `sha256` before using it, as `run-model-forward` does.
2. **The sampler is stochastic by default and the decode graph is not reproducible without pinning
   it.** Measured (section 3.1). *Mitigation:* `--temp 0 -s 0` is contractual in the runner; the arm
   derives the decoded token from its own argmax rather than accepting it as an operand, so a
   transcript from a different token cannot be compared against silently — step 13's parse would
   have to match a `token_id` the arm did not produce.
3. **No external byte-exact acceptance for the *incremental* step.** Section 3.2, as corrected by
   section 5.1: there is no instrument that publishes llama.cpp's own decode-step logits, so oracle
   A's floor against llama.cpp remains the instrument's four printed decimals. *Mitigation:* oracle
   B carries a byte-exact claim about the part this capability adds, and oracle C carries one about
   the step's arithmetic against this arm's own single-shot prefill — which section 5.1 corroborated
   once against `llama-debug` on an extended prompt. *Residual risk accepted:* an error below 1e-4
   at every printed node **and** identical in both of this arm's own paths would pass. Section 7
   names the patch that would close it.
4. **A concat axis or stride error that is numerically plausible.** K and V concatenate on
   *different* axes (2.4). *Mitigation:* oracle B compares bytes, not values, and the
   forced build `engine+plane-stage-offset` asserts the failure is detected rather than absorbed:
   `ds-force-plane-stage-offset` shifts the staged past K by one lane and oracle B reports
   `R6_PLANE_MISMATCH layer[0]tensor[k]col[0]`.
5. **Lifting `MAX_PREFILL_TOKENS` weakens the prefill oracle at `T = 7`.** The constant's comment
   says the cap is the oracle's, and documenting the lift at the constant is not a mitigation:
   `printed_count` clamps to six on both sides, so a 7- or 8-token prefill *with a transcript* would
   have compared six of seven rows and reported `PASS`. *Mitigation, shipped:* `--layer-forward` and
   `--model-forward` refuse that combination at their token stage with `R5_ORACLE_TRUNCATED`
   (section 2.7), with a refused case and an admitted case per arm. The range is open for arithmetic
   and closed for comparison, which is what the constant's original reason asks for.
6. **Plane size grows linearly with `KV_WIDTH`.** At 4096 the plane is 469,762,048 B, comparable to
   the weight window. *Mitigation:* the qualification runs at 256; the arm records `plane.bytes` in
   its document so growth is visible rather than surprising; a policy is section 7's.
7. **`ggml_concat` is new to this repository.** `grep` confirms no existing use anywhere.
   *Mitigation:* the stub kernel gives the whole arm a no-ggml path, so the concat's semantics are
   exercised by the hosted smoke and not only by the opt-in qualification.

## 7. Deferred

- **Step 2 and the decode loop.** Needs a write-back at column `n_past`, which makes the plane both
  a read and a write target in one graph (2.2). It is the natural next capability.
- **Extending the R2C patch to `llama-debug`.** Adding a post-decode `--save-logits` to
  `examples/debug/debug.cpp` would give a byte-exact external reference for the step and close risk
  3. Cost: a new patch digest, a cache-generation bump to `r2c-v3`, and a re-run of the R2C
  qualification. **This is the principal open decision** and is deliberately not taken here.
- **A quantized KV plane** (`-ctk q8_0` and friends). A different oracle and a different tolerance.
- **Residency for the plane** — eviction, tiering across GPU/system/NVMe, prefetch. The plane is the
  first object in this repository whose size grows with the conversation rather than the model, so
  it is the natural subject of the residency policy `docs/specs/align-llm.md` already designs.
- **The Metal decode arm**, and OLMoE/routed decode. Both are declared non-goals here.
- **Any TTFT or tokens-per-second claim.** R6 measures correctness. The baseline for a decode-time
  claim is R5B section 5.3's, and a claim needs its own capability with its own benchmark.

## 8. Align capability requests

Encountered while designing, classified per `CLAUDE.md`. **None blocks this capability.**

| Gap | Classification | Status |
| --- | --- | --- |
| `raw` may not be a struct field or array element, forcing the node-slot store | Genuine Align gap, already recorded | Existing request; this capability is one more client, cited as evidence |
| `buffer(n)` has no alignment guarantee, forcing over-reservation and an aligned interior | Genuine Align gap, already recorded | Existing request; the plane inherits the same workaround |
| By-value structs and `bool` do not cross the C FFI, forcing the shim | Genuine Align gap, already recorded | Existing request |
| `alignc check` is not a superset of `alignc build` | Genuine Align gap | Request 42, unchanged |
| Release of rebound `buffer` allocations before frame exit | Genuine Align gap | Request 39 — relevant because the plane is 28 MiB held across two passes; a workaround exists (scope it) and is used |

**Numbering hazard, recorded because it has already bitten this repository twice.** `main` carries
requests through **46**. The `agent/r5e-moe-model-prefill` branch **holds 47 and 48** and they are
not free; this capability therefore takes **49**. If that branch merges with different numbers, or
another branch claims 49 first, this request is renumbered at reconciliation — the number is not a
contract. The same applies to the roadmap item number in section 9.

## 9. Reconciliation — applied

The drafts this section carried are **written into their owning documents** and are not repeated
here. Roadmap item **27** is in `docs/specs/roadmap.md`; the `HANDOFF.md` active block is written;
`docs/align-development.md` carries the arm, its operand grammar, its environment inputs, and the
`MAX_PREFILL_TOKENS` lift.

The numbering hazard section 8 recorded was real and both numbers moved. `main` carries roadmap
items to **24** and requests to **46**; `agent/r3-decode-residency` claims roadmap **25** and
`agent/r5e-moe-model-prefill` claims roadmap **26** and requests **47/48**. This capability therefore
takes roadmap **27** and Align Request **49**, and both must be re-checked at reconciliation against
whatever has merged by then.

## 10. Deviations from this ledger, and why

Every one of these is a place the implementation disagrees with the plan. They are recorded here
rather than quietly absorbed, because the plan is authoritative until it is corrected.

### 10.1 The decode layer is thirty-eight rows, not thirty-six

Section 2.4's node-count sentence — "one `PAD` exchanged for a `CONCAT` on each of K and V, i.e.
**the same count**" — is **wrong**, and its own neighbouring sentence is right: the rows are
`CONT_3D` + `CONCAT` + `PAD` on K and `CONT_3D` + `CONCAT` + `PAD` on V, which is one row more than
the prefill on each tensor.

The arithmetic forces it. `ggml_concat` appends `b` at the **end** of `dim`, so `concat(past, new)`
puts the new column at index `n_past` — which is exactly where section 2.6's offset mask unmasks it
— and the operand is then `n_past + 1` columns wide, not `KV_WIDTH`. Something has to widen it, and
that something is the `PAD` the prefill already has. The alternative the "same count" sentence
implies — a `KV_WIDTH - 1`-wide past concatenated with the new column and no pad — puts the new
column at index `KV_WIDTH - 1` and answers a different question.

Measured on the hosted two-layer fixture: the prefill issues **74** nodes (1 + 34 + 36 + 3, R5B's
own reconciliation count) and the decode pass issues **78** (1 + 36 + 38 + 3). Both are recorded in
the document and asserted in `scripts/decode-step-golden.jsonl`. The slot high-water is **66**,
exactly as section 2.3 predicted, because 38 node rows reach slot 53 and the two plane slots at
64/65 are above them.

### 10.2 Oracle C is computed by the runner, not by the arm

Section 3.3 gives oracle C to the arm: "the arm optionally computes its own `T+1`-token single-shot
prefill". It does not. `scripts/run-decode-step` runs `--model-forward` at `TOKENS,<decoded>` and
compares the two documents' `argmax` and digests, and reports the result as one characterization
line per prompt.

The reason is proportion, not difficulty. Computing it inside the arm means a second whole
thirty-graph schedule — another full pass over the weights — and two documents produced by two arms
that already exist carry the same information.

**Where it is computed did not change; what it is worth did.** The design also called oracle C
characterization, and section 5.1 measured byte identity and promoted it to acceptance. Section 2.11
states the resulting rule once. So the deviation recorded here is narrow and only about
**location**: the runner owns oracle C, the arm does not, and `--decode-step` therefore publishes no
single-shot comparison of its own. A consumer that wants oracle C without the runner has to run
`--model-forward` at `TOKENS,<decoded>` itself, which is exactly what `scripts/run-decode-step`
does.

### 10.3 The seam's codes reach the document unchanged

Section 2.8 names `R6_BLOCK_MISSING` at step 7. The arm emits the container reader's own
`R5_BLOCK_MISSING`, `R5_LAYER_COVERAGE`, `R5_MEMBER_MISSING`, `R5_SHAPE`, and `R4_PACK_*` unchanged,
exactly as it emits the ggml seam's `R5_*` codes unchanged — because it **calls that reader** rather
than reimplementing it, and renaming a code at a module boundary would make two documents disagree
about one condition. The codes this arm owns are the ones it decides itself: `R6_ARITY`, `R6_PATH`,
`R6_TOKENS`, `R6_GEOMETRY`, `R6_GEOMETRY_UNREADABLE`, `R6_ARCH_UNSUPPORTED`, `R6_KV_WIDTH`,
`R6_PLANE_UNAVAILABLE`, `R6_PLANE_WRITE`, `R6_PLANE_MISMATCH`, `R6_TRANSCRIPT`, and
`R6_ORACLE_MISSING`. All twelve are reachable in the hosted owner except `R6_PLANE_WRITE` and
`R6_PLANE_UNAVAILABLE`, which are deferred in 10.5. `R6_PLANE_MISMATCH` is reached by
`ds-force-plane-stage-offset` and is in the block's `REQUIRED_CODES`.

**There is deliberately no `R6_ORACLE_SHAPE`.** An early draft declared the constant and never used
it; a transcript node whose printed axes disagree with the arm's own is `R5_ORACLE_SHAPE`, raised
inside `model_forward.compare_transcript_graph` and reaching this document unchanged like every
other seam code. The dead constant is removed rather than given a second meaning for one condition.

### 10.4 The checked-in golden rows that moved

Section 4.3 asks that "every existing R5A/R5B/R5C/R5D golden must be byte-identical after this
change". Section 5.3 lists every row that is not, exactly, and there are two causes and no third:

1. **Section 2.7's lift**, on one row per prefill file: `lf-tokens-seven` and `mf-tokens-seven`
   become `lf-tokens-nine` and `mf-tokens-nine`, because those cases exist to assert the cap and the
   cap is 8 now. Two further rows per file are **added** by the `R5_ORACLE_TRUNCATED` refusal the
   lift required; no existing row's bytes change for them.
2. **The `slot_high_water` repair of section 5.3**, on seven rows of `decode-step-golden.jsonl`
   alone. That file is this capability's own and did not exist before it, so the non-regression cell
   is unaffected.

**Nothing else moved.** `scripts/gpu-forward-golden.jsonl` and
`scripts/moe-layer-forward-golden.jsonl` are byte-unchanged; every other row of
`layer-forward-golden.jsonl` and of `model-forward-golden.jsonl` is byte-unchanged; and the fifth
smoke block asserts `--model-forward`'s `slot_high_water` is still **52**, which is section 2.3's
whole reason for choosing slots 64 and 65.

### 10.5 Deferred closure cells

- **`R6_PLANE_UNAVAILABLE` and `R6_PLANE_WRITE` are not reached by a case.** Both are guards on
  conditions the arm's own validation makes unreachable — a `buffer` view shorter than the size the
  arm computed, and a `slot_get` that fills fewer bytes than the node declares — and neither has a
  forced build. They are dead in the shipped arm by construction, which is what the ledger asks of a
  guard, but section 4.2's cells for them are **deferred** rather than met.
- **`ds-plane-transposed` and `ds-plane-short`** as *fixture* mutations are not shipped, because a
  stronger equivalent is: the forced build `engine+plane-stage-offset` shifts the staged past K by
  one lane inside the slot only the decode graph writes, and oracle B reports
  `R6_PLANE_MISMATCH layer[0]tensor[k]col[0]`. It is a shipped case (`ds-force-plane-stage-offset`),
  not a mutation someone has to re-apply.
- **Neither of `verify_plane`'s two size guards is reached by a case.** Oracle B's own early
  returns — a span that does not fit the node window, and a `CONCAT` row whose `slot_nbytes`
  disagrees with the span the arm computed — publish `R6_PLANE_MISMATCH` with
  `roundtrip_verdict: "MISMATCH"` and `col[-1]`, the extent-level column. Both conditions are
  arithmetic the arm derives from the same geometry it built the graph with, so no operand and no
  forced build reaches them, and **the `col[-1]` form of the detail is therefore unexercised**; the
  shipped `R6_PLANE_MISMATCH` case, `ds-force-plane-stage-offset`, reaches the *comparison* path and
  reports a real column. The guards stay because they are the difference between a wrong answer and
  a refusal if a future row table changes a shape, and they are deferred rather than met — like
  `R6_PLANE_UNAVAILABLE` and `R6_PLANE_WRITE` above and for the same reason.
- **`ds-concat-dim-invalid`** is deferred. `dim` is a compiled-in column of the row table and no
  operand reaches `op_concat`'s `[0,3]` guard; the *axis* refusal it is adjacent to is shipped as
  `ds-force-concat-axis`.
- **`ds-mask-offset-negative`** is not a case. `mf_write_mask_offset` returns without writing on a
  negative offset and no caller can supply one, so the cell is met by construction and not by a run.
  The positive off-by-one — the one a real bug looks like — is shipped as `ds-force-mask-offset`.
- **A prefill failure at layer `k > 0`** is not exercised. Section 4.2's early-exit cell says layers
  above the failing one stay zeroed; the only forced build that fails inside the prefill
  (`engine+compute`) fails at the **embedding** graph, so `k` is 0 and `plane.layers` is 0. What is
  asserted is the property the cell exists to protect — an error document publishes no plane and no
  round-trip verdict — on every stub and forced case. A build that failed at a chosen layer index
  would be a new discriminator in the shim for one cell, and it is deferred rather than built.
- **Making oracle C's `llama-debug` leg an assertion.** Section 5.1's third digest was measured by
  hand on one prompt, because it needs a prompt whose tokenization is the prefill's tokens plus the
  decoded one and the runner does not construct that text. Deferred: it would need the runner to
  detokenize, and the pair it corroborates is already asserted on all four prompts every run.
- **Driving the C chain externally.** The review recommended making oracle C an external comparison
  — have the runner call `llama-debug --save-logits` on the prompt plus the decoded token and pass
  the resulting blob as the single-shot run's `LOGITS` operand. It is deferred for the same reason
  as the item above and it is the same missing piece: the operand `llama-debug` needs is a **prompt
  string**, not a token list, and the runner holds token ids. Constructing that string means either
  detokenizing (no instrument here does it) or assuming the decoded token's text, which is what
  section 5.1 did by hand for one prompt and is exactly what should not be automated on an
  assumption. Section 7's `llama-debug` patch is the honest route and is already the principal open
  decision.

### 10.6 Functions re-implemented rather than imported, and how they differ

`src/decode_step.align` carries its own `fail`/`fault_into`/`pack_fault_into`/`take`/`take_pack`,
its own `account` and `check_types`, its own `top_k`, and a compact prefill logits comparison, and
`src/model_forward.align` gained one new borrow-free entry point, `stage_plan_owned`, beside the
`stage_plan` this arm could not call. None of that was the plan; all of it is one measured Align
region-checker gap, now Align Request **49**, whose evidence is that 161 of the 178 errors in the
first cross-module draft were the single diagnostic "cannot retain a shorter-lived view through this
mutable borrow" and every one disappeared when the callee was moved into the calling module
unchanged.

**A copy that has drifted is worse than a call, so each copy is diffed against its original and
every divergence is named here.** This is the audit the review asked for and its result:

| Copy | Original | Divergence |
| --- | --- | --- |
| `fail`, `bounded_detail` | `model_forward.fail`, `model_forward.bounded_detail` (both `pub`) | none. Same body, same 256-byte cap |
| `fault_into`, `pack_fault_into`, `take`, `take_pack` | `model_forward.*` (all `pub`) | none |
| `check_types` | `model_forward.stage_types` (`pub`) | none but the name. It is a rename, and the name here is the worse of the two; the original says *when* it runs |
| `top_k` | `model_forward.top_k` (`pub`) | none. It calls `model_forward.zero_column` and `model_forward.TOP_K` rather than re-declaring them |
| `compare_prefill_logits` | `model_forward.compare_logits` | intentional and narrower: the reconciliation branch only. This arm's prefill always runs at the declared `KV_WIDTH`, so the runtime-width `WITHIN` path has no caller here. Every conversion, including `logit_ten_thousandths`'s non-finite refusal, is called from the original |
| `account` | `model_forward.account` | **two**, one of them a defect. (a) The `slot_high_water` maximum was missing; that is the repair of section 5.3 and it moved seven golden rows. (b) `o.reference_compute_ns += r.reference_compute_ns` is deliberately absent: this arm runs no second ggml context — its self-reference oracle is the byte-plane source comparison — so `run_step_graph` never sets that field and accumulating it would be dead code. Recorded rather than added |

**One further cost this created, recorded rather than hidden.** `model_forward.Outcome` grew the
plane's and the step's fields and is now **1,328 bytes**, passed by value at roughly twenty-five new
call sites here and at every existing one in `src/model_forward.align`. The compiler warns about it
and the warning is correct. It is not split here for two reasons: the arm is a correctness
capability with no throughput claim, and the record is what the region checker forced this shape on
in the first place (a second out-parameter is the exact refusal Request 49 describes), so splitting
it now would be building around a gap that request asks to close. If Request 49 lands, the split and
the deletion of this section's whole table are one change; if it does not, the split is its own
capability with its own measurement. Section 7 does not list it as deferred work because it is a
cost, not a feature.


## 11. Ledger and closure matrix mapped to the diff

Every applicable cell of sections 2 and 4, with the file that implements it and the test that covers
it. `deferred` rows are section 10.5's, and each one says why there.

### 11.1 The ledger (section 2)

| Ledger row | Implementation | Evidence |
| --- | --- | --- |
| 2.1 arm and operand grammar | `src/ggml_spike.align` dispatch arm; `decode_step.run` | `ds-arity-*`, `ds-path-*`, `ds-arm-unknown-flag` (no document, non-zero exit) |
| 2.1 arity {5,6,7,9,10}, 8 is `R6_ARITY` | `decode_step.run` | `ds-arity-8` |
| 2.1 `NEXT` is the prefill's own argmax | `schedule_decode`, `decoded_token` | `ds-engine-ok` asserts `decode.token_id == EXPECTED_TOKEN`; qualification asserts it equals `output.argmax` |
| 2.1 `KV_WIDTH` fail-closed, `T+1 .. 4096` | `stage_inputs` | `ds-kv-width-absent/-empty/-negative/-equal-t/-over-max` |
| 2.2 plane layout, size, ownership | `plane_stride`, `plane_bytes_for`, `capture_plane` | `plane.bytes == 512` hosted, **29,360,128** on the real model |
| 2.2 zero-filled before the prefill writes | `prime_window(plane, plane_bytes)` | oracle B, and the masked tail is asserted by oracle A's `PASS` |
| 2.2 written by the prefill, rows 12 and 10 | `capture_plane`, `PREFILL_K_ROW`/`PREFILL_V_ROW` | `plane.layers`, `plane.columns_written`; **`ds-force-plane-stage-offset`** → `R6_PLANE_MISMATCH layer[0]tensor[k]col[0]` |
| 2.2 read by the decode pass with `slot_set` | `stage_past_k`/`stage_past_v`, `decode_layer_values` | oracle B |
| 2.2 freed by Align at scope end | `schedule_decode`'s `mut plane: buffer` | `lifetime.*` balance on every case including every `ds-force-*` |
| 2.2 crossing by value, never by handle | `ggml_ffi.slot_get`/`slot_set` only | the `unsafe`/`extern` confinement scan |
| 2.3 slots 64/65, high-water 66, capacity 128 | `MF_SLOT_KPAST`/`MF_SLOT_VPAST` | `ds-engine-ok` asserts 66/128 **and** `--model-forward`'s 52 |
| 2.4 `WHEN_DECODE`, the concat rows, the two axes | `mf_decode_layer_node_table` | mutants `drop-k-concat` and `v-axis-swapped`, both `R5_SHAPE` |
| 2.4 positions are `[n_past]` | `decode_pos_image` | **`ds-force-decode-position`**, oracle A `FAIL` with oracle B still `IDENTICAL` |
| 2.4 mask `{KV_WIDTH, 1}` with offset | `mf_write_mask_offset` | **`ds-force-mask-offset`**, oracle A `FAIL` with oracle B still `IDENTICAL` |
| 2.4 node count derived and recorded | `graph.node_count_total`, `decode.node_count` | golden; **corrected in 10.1** — 38 rows, not 36 |
| 2.4 last-layer narrowing kept at `t = 1` | rows 28/29 `WHEN_LAST` | oracle A `PASS`; no oracle row names them, so they are excluded by construction |
| 2.5 `op_concat` across six surfaces | `ggml_shim.c`, `ggml_shim_stub.c`, `ggml_ffi.align`, `OP_CONCAT`, `build_decode_nodes` | shared-region byte-identity, `unsafe`/`extern`, no-`malloc` scans; `ds-force-concat-axis` |
| 2.5 shared region untouched, no `build-ggml-shim` symbol list | both C files | the smoke's region comparison |
| 2.6 `token_ids` split from `positions` | `model_forward.graph_input_values` | `mf-*` goldens byte-unchanged; `ds-engine-ok` decodes at `n_past` |
| 2.7 `MAX_PREFILL_TOKENS` 6 → 8 | `src/layer_qwen2.align` | `lf-tokens-nine`, `mf-tokens-nine`, `ds-tokens-nine`; `layer_olmoe` unchanged at 6 |
| 2.7 the prefill oracles fail closed above 6 | the token stage of `layer_forward` and `model_forward` | `lf-/mf-tokens-seven-transcript` → `R5_ORACLE_TRUNCATED`; `lf-/mf-tokens-eight-no-transcript` admitted |
| 2.8 validation order, steps 1–16 | `run`, `stage_inputs`, `execute`, `schedule_decode` | the `REQUIRED_CODES` set: **23** codes reached, `R6_PLANE_MISMATCH` among them |
| 2.9 document kind, schema 1, three new objects | `decode_step.render` | every case asserts kind/schema; the golden is the shape |
| 2.9 no float on the wire | `render_plane`, `render_decode` | golden |
| 2.9 persisted identity `N/A` | nothing is persisted | stated; no cache key exists to test |
| 2.11 the acceptance rule (A, B, C; the A-`FAIL` conjunction) | `scripts/run-decode-step` | the qualification's own failure list; section 5.1's four prompts |
| 2.11 determinism | — | three consecutive runs byte-identical, hosted and on the real model |

### 11.2 The closure matrix (section 4)

| Cell | Evidence |
| --- | --- |
| 4.1 construction / success | `ds-engine-ok`; qualification asserts `plane.bytes == 29360128` |
| 4.1 failure (`R5_*` from the seam) | `ds-force-init`, `ds-force-alloc`, `ds-force-compute`, `ds-force-slot-range` |
| 4.1 malformed input | 20 `STUB_CASES` plus the 10 no-document cases |
| 4.1 early exit | `record()`'s `(returncode == 0) == (status == "ok")` on every case; every stub case asserts the plane is **not** published |
| 4.1 cleanup | `lifetime.*_created == *_freed`, `graph_balance_failures == 0`, per case |
| 4.2 plane construction | `plane.bytes`/`stride` asserted; the `R6_PLANE_UNAVAILABLE` guard **deferred** (10.5) |
| 4.2 plane success | `plane.layers`, `plane.columns_written`; oracle B |
| 4.2 plane failure (`R6_PLANE_WRITE`) | **deferred** (10.5) — no forced build reaches it |
| 4.2 plane failure (`R6_PLANE_MISMATCH`) | `ds-force-plane-stage-offset`, asserted on code, layer, tensor, and column |
| 4.2 `KV_WIDTH <= T` refused before allocation | `ds-kv-width-equal-t` |
| 4.2 early exit gates step 11 | `ds-force-compute` emits no plane and no `oracle_decode` verdict; the `k > 0` half is **deferred** (10.5) |
| 4.3 rows, slots, mask | `ds-force-concat-axis`, `ds-force-decode-position`, `ds-force-mask-offset`; the dropped-K-concat mutation stays a source mutation (5.2) |
| 4.3 wrong concat axis is a shape refusal | `ds-force-concat-axis` |
| 4.3 `mf_write_mask_offset(.., 0)` is `mf_write_mask` | by definition; `mf-*` goldens byte-unchanged |
| 4.3 **non-regression** | 10.4: two golden lines moved, both the token-cap lift; GPU and MoE goldens byte-unchanged |
| 4.4 id/position split | `mf-*` goldens byte-unchanged; `ds-prefill-matches-r5b` asserts the same logits digest |
| 4.5 shim/stub construction | the three source scans |
| 4.5 stub success | every `ds-*` case runs with no ggml at all |
| 4.5 `dim` outside `[0,3]` refused in Align | `ggml_ffi.op_concat`; **deferred** as a case (10.5) |
| 4.6 mutated *plane* fixtures | replaced by `ds-force-plane-stage-offset` (10.5) |
| 4.6 fixture decode mode | `ds-engine-transcript` consumes it; oracle A `max 0` |
| 4.6 mutated transcript fixtures | `ds-transcript-onegraph`, `ds-transcript-kv-width`, `ds-transcript-perturbed`, `ds-transcript-garbage` |
| 4.7 the fifth smoke block | 40 documented cases, its own `SystemExit(1)` |
| 4.7 the qualification never skips silently | `na()` prints one line and exits 0 |
| 4.7 cleanup on every exit path | `trap cleanup EXIT HUP INT TERM`, and the shim is restored |
