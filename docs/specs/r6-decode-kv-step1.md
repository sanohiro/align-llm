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
| 14 | transcript's declared width equals `KV_WIDTH` | `R6_KV_WIDTH` | `kq[<n>]ne0[<n>]` |
| 15 | self-reference byte plane, when supplied | `R6_REFERENCE_MISMATCH` | `node[<id>]` |
| 16 | logits blob, when supplied | `R6_LOGITS` | `bytes[<n>]` |

`R6_PLANE_MISMATCH` (step 12) is the one code with no R5 ancestor and it is the capability's own
acceptance check: see section 3.3, oracle B.

### 2.9 Document, schema, and identity

| Field | Contract |
| --- | --- |
| `kind` | `R6_DECODE_STEP` |
| `schema_version` | **1**. New document kind, so it starts at 1 |
| Shape | R5B's document with three additions: a `plane` object (`bytes`, `stride`, `layers`, `columns_written`, `readback_ns`, `upload_ns`, `roundtrip_verdict`, `roundtrip_bytes_compared`), a `decode` object (`n_past`, `token_id`, `argmax`, `top_k`, `sha256`, `bit_sum`), and `oracle_decode` (section 3.3's oracle A) |
| Float fields | Never floats on the wire. `sha256` over exact little-endian f32 bytes, `bit_sum` over the same, tolerances in integer ten-thousandths — R5B's rule at its section on digests, unchanged |
| Persisted identity | **N/A — nothing is persisted.** The plane lives in one process's memory for the duration of one `run` call and is never written to disk, never memory-mapped, never named, and never reused across invocations. There is consequently no cache key, no generation counter, and no compatibility rule to break. This is a deliberate scope choice, not an oversight: a persisted plane is a residency question and section 7 defers it |
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

| Claim | Evidence |
| --- | --- |
| The decode step is arithmetically right | Oracle A: every comparable node of llama.cpp's own decode graph matches at 1 ten-thousandth, 28 layers plus the head, four prompts × three runs |
| The plane crosses the graph boundary losslessly | Oracle B: `roundtrip_verdict == "IDENTICAL"`, every written byte of all 28 layers' K and V equal on read-back, `R6_PLANE_MISMATCH` unreachable in a passing run |
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
in both. It is **batch-size-dependent kernel selection**. `MUL_MAT` with a 7-column right operand
takes a different accumulation path from the same op with a 1-column right operand (this build
reports `LLAMAFILE = 1`), and the difference compounds through 28 layers. The first eight layers
agree to four printed decimals because the divergence is still below 0.00005 there.

**Consequence, and it invalidates one of the two oracles the brief proposed.** The proposed
self-reference — "our T=7 single-shot prefill's final position versus our KV-path step at position
6, byte-identical on CPU at matched width" — cannot hold. Our arm runs on the same ggml with the
same kernel-selection behaviour, so our own 7-column prefill and our own 1-column decode step will
diverge for exactly the reason llama.cpp's do. Asserting byte-identity there would be asserting
something false; asserting it with a tolerance wide enough to pass would be a tolerance in which any
real bug could hide. **It is dropped as an acceptance oracle** and kept only as a characterization
measurement (section 3.4).

### 3.3 The oracle set

Three oracles. A and B are acceptance; C is characterization.

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

**Oracle C — the single-shot comparison (characterization, NOT acceptance).**
The arm optionally computes its own `T+1`-token single-shot prefill and reports `max_abs_diff` and
`top_k_agreement` against its decode step, with verdict `WITHIN`. This is the exact analogue of
R5B's runtime-width pass, which R5B also recorded as "a characterization of a declared non-goal,
not an acceptance criterion". Its tolerance is section 3.4's.

**Determinism.** Three consecutive runs of the arm must be byte-identical, and the qualification
runs four prompts × three runs.

### 3.4 The tolerance rule

| Comparison | Rule | Value | Derivation |
| --- | --- | --- | --- |
| Oracle A, per element | absolute | **1 ten-thousandth** | The instrument prints `%12.4f`; a tighter tolerance would be comparing digits that do not exist. Inherited unchanged from R5A/R5B |
| Oracle A, per-tensor sum | absolute, then relative | **1000 millionths**, or **10 ppm** for large sums | Inherited unchanged from R5B |
| Oracle B | **byte identity** | 0 | A byte plane either survives a round trip or it does not. There is no quantity here to be approximately right about, so admitting a tolerance would only admit a bug |
| Oracle C | absolute, `WITHIN` | **5000 ten-thousandths (0.5)** | Measured, not chosen. llama.cpp's own two paths differ by up to 0.1699 in activations and 0.054 at the logits (section 3.2). 0.5 is a floor with roughly 3× headroom over the largest measured divergence, and it is the same number R5B used for its own characterization pass. It gates nothing |
| Oracle C, argmax | equality | argmax and top-10 must agree | The measured divergence is far below the logit gap at the top of this distribution; a disagreement here would mean something other than kernel selection |

**Byte identity is claimed exactly once, in oracle B, and it is claimed about bytes rather than
about arithmetic.** R5B could claim it about logits because `llama-debug` published a blob at a
matched width; section 3.2 shows that route does not exist for a decode step. Saying so plainly is
better than manufacturing a weaker claim in the same words.

## 4. Closure matrix

Every cell names the implementation and the exact regression that covers it. `T` is the prefill
length; the arm under test is `--decode-step`.

### 4.1 `src/decode_step.align` — the arm

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `run` parses operands, loads geometry, sizes the plane, allocates it zeroed | `ds-engine-ok` (golden), `ds-plane-bytes` asserts `plane.bytes == 29360128` at width 256 |
| Success | prefill pass → plane → decode pass → document, `status: ok`, exit 0 | `ds-engine-ok`; qualification asserts `oracle_decode.verdict == "PASS"` |
| Failure | steps 9 and 11 of section 2.8 propagate `R5_*` from the seam | `ds-force-init`, `ds-force-alloc`, `ds-force-compute` via `ALIGN_LLM_GGML_FORCE` |
| Malformed input | steps 1–8 of section 2.8 | `ds-arity-4`, `ds-arity-8`, `ds-arity-11`, `ds-path-*-empty`, `ds-path-long`, `ds-tokens-empty`, `ds-tokens-over-max`, `ds-geometry-missing-*`, `ds-kv-width-zero`, `ds-kv-width-equal-t`, `ds-kv-width-over-max`, `ds-arm-unknown-flag` |
| Early exit | any failing step emits a document with a non-empty `error_code` and a non-zero exit, and **still frees the plane** | `record()`'s universal assertion that `(returncode == 0) == (status == "ok")`; `ds-force-*` cases confirm the plane is freed by completing without leak-check failure |
| Cleanup | the plane is an ordinary `buffer` freed at scope end; ggml contexts/buffers/gallocrs balanced | `lifetime.*_created == *_freed` and `graph_balance_failures == 0`, asserted per case as R5B does |

### 4.2 The KV plane

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `buffer(plane_bytes)` zero-filled; `.bytes().len()` checked | `ds-plane-unavailable` (forced short view) → `R6_PLANE_UNAVAILABLE` |
| Success | 28 layers × K and V written at `stride`-derived offsets, columns `0..T-1` | `plane.columns_written == T`, `plane.layers == 28`; oracle B |
| Failure | a `slot_get` that does not fill the expected byte count | `R6_PLANE_WRITE`, reached by `ALIGN_LLM_GGML_FORCE=engine+slot-empty` |
| Malformed input | `KV_WIDTH <= T` refused before allocation | `ds-kv-width-equal-t` → `R6_KV_WIDTH` |
| Early exit | a prefill failure at layer *k* leaves layers `> k` zeroed; the arm never reads a partially written plane because step 10 gates step 11 | `ds-force-compute` asserts `error_code == "R5_COMPUTE"` and that no `oracle_decode` object is emitted |
| Cleanup | freed at scope end on every path | as 4.1 |

### 4.3 `src/layer_qwen2.align` — rows, slots, mask

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `WHEN_DECODE`, `OP_CONCAT := 16`, `MF_SLOT_KPAST/VPAST := 64/65`, `mf_write_mask_offset` | `ds-engine-ok`; `slot_high_water == 66` |
| Success | K concat on axis 1, V concat on axis 0, then `PAD` to `KV_WIDTH` | oracle A on `kqv_out-*`; oracle B on both tensors |
| Failure | a wrong concat axis produces a shape ggml refuses | `R5_SHAPE`, covered by a stub-level `ds-stub-concat-axis` case |
| Malformed input | `mf_write_mask_offset` with `row_offset < 0` | refused at the call; `ds-mask-offset-negative` |
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
| Failure | null context → `ALIGN_GGML_INIT`; empty/out-of-range slot → `ALIGN_GGML_SLOT`; axis mismatch → `ALIGN_GGML_SHAPE` | `ds-force-slot-range`, `ds-force-slot-empty`, `ds-stub-concat-axis` |
| Malformed input | `dim` outside `[0,3]` refused in Align before the call | `ds-concat-dim-invalid` → `R5_GGML_INIT` |
| Early exit | every wrapper returns before any ggml call when a source slot is bad | inherited `ALIGN_GGML_OP_PROLOGUE_1` behaviour, asserted by the two forced slot cases |
| Cleanup | N/A — the shim owns no memory; the no-`malloc` scan enforces it | stated, with reason |

### 4.6 `scripts/layer_forward_fixture.py` — the reference

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | a `--decode` mode emitting a tiny-geometry two-call reference: prefill of `T`, then a step at `n_past = T` | `ds-stub-*` cases consume it |
| Success | `model_layer` gains `n_past` and `past_k`/`past_v`; `rope_neox` positions become `range(n_past, n_past+t)`; the mask becomes `(n_past+t) × t` with past columns unmasked | the emitted transcript is what `ds-stub-transcript` compares against |
| Failure | N/A — the generator is total over its own fixed inputs and reads no external file | stated, with reason |
| Malformed input | mutated fixtures: a transposed plane, a short plane, a wrong-width transcript | `ds-plane-transposed`, `ds-plane-short`, `ds-transcript-kv-width` |
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
| Publication | `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` |
| Formatting | `gmake fmt` before committing Align source; `gmake format-check` and `git diff --check` clean |

**Aggregate membership is unchanged, and the Makefile change is worth its cost.** The precedent is
unambiguous: R5B, R5C, and R5D each added exactly one opt-in qualification target and extended
`run-layer-forward-smoke` in place. Because the owner stays `layer-forward-smoke`, which is already
in `HOSTED_CHECK_TARGETS` (`Makefile:18`), **`scripts/check-gate-topology`'s byte-literal `EXPECTED`
does not change** and `make ci` is not selected by a topology change. The cost is two executable
Makefile lines, one `.PHONY` word, and a comment block; the alternative — no target — would leave
the qualification invocable only by remembering a script path, which is precisely what the four
existing `*-qualification` targets exist to prevent.

The qualification asserts, at minimum: `plane.bytes == 29360128`; `plane.roundtrip_verdict ==
"IDENTICAL"`; `oracle_decode.verdict == "PASS"` with `tolerance_ten_thousandths == 1`;
`decode.n_past == 6`; `decode.token_id == 671`; `graph.graph_count`; `slot_high_water == 66`;
`slot_capacity == 128`; every `lifetime.*_created == *_freed`; `abi.fp_contract_off == true`; and
three consecutive runs byte-identical, over four prompts.

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

The run was performed twice — once before the acceptance rule of the next subsection was written and
once after. **Every recorded value above is identical across the two runs**: the same decoded tokens,
the same oracle A maxima and element counts, the same oracle B byte counts, the same plane size, the
same node counts. Only the elapsed timings moved, which is what makes them a diagnostic.

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

All three are the **same 608,256 bytes**. Our decode step at `n_past = T` reproduces llama.cpp's own
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

**Consequence for the acceptance rule, applied in `scripts/run-decode-step`.** Oracle A `PASS` is
acceptance. An oracle A `FAIL` is admitted only when both of two conditions hold, and never on its
own: the divergence stays inside section 3.4's own characterization bound of 0.5, and **oracle C is
byte-identical**, which says the decode step reproduced this arm's batched path exactly. Oracle C is
therefore promoted from characterization to acceptance — measured byte identity, on every prompt —
and oracle A keeps its ten-thousandth tolerance for the comparison it can honestly make.

Section 7 gains one entry as a result: extending the R2c patch to `examples/debug/debug.cpp` would
give a byte-exact reference for the **incremental** step and would let oracle A's divergence be
attributed rather than argued. It is still the principal open decision, and the digests above mean
it is now a way to measure llama.cpp's own two paths against each other rather than the only route
to a byte-exact claim.

## 5.2 Result — the hosted owner

`gmake layer-forward-smoke`, all five blocks, on Apple M1 with no ggml, no model, and no instrument.
The fifth block is 10 no-document cases and **37** documented cases reaching 22 codes.

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

### Mutants

Five source mutations, each run through the whole hosted owner and each dying with a distinct
diagnosis. The first two are shape refusals from the seam; the middle two are oracle A; the last is
oracle B doing exactly what it exists for.

| Mutation | Result |
| --- | --- |
| Drop the K `CONCAT` — the `PAD` consumes the new column alone | `R5_SHAPE` `node[24]` |
| Concatenate V on axis 1 instead of axis 0 | `R5_SHAPE` `node[22]` |
| Rope the decoded token at position 0 instead of `n_past` | oracle A `FAIL`, max **8092**/1e-4, worst `q_rope-1` |
| Write the offset mask at `n_past - 1` | oracle A `FAIL`, max **514**/1e-4, worst `kqv-1` |
| Stage the K plane in V's transposed order | **`R6_PLANE_MISMATCH`** `layer[0]tensor[k]col[0]` |

## 5.3 Result — the goldens that moved

Two lines, one per file, and both are section 2.7's `MAX_PREFILL_TOKENS` lift rather than any row
work: `lf-tokens-seven` becomes `lf-tokens-nine` and `mf-tokens-seven` becomes `mf-tokens-nine`,
because those two cases exist to assert the cap and the cap is 8 now.
`scripts/gpu-forward-golden.jsonl` and `scripts/moe-layer-forward-golden.jsonl` are byte-unchanged;
every other row of the two files that moved is byte-unchanged. That is section 4.3's non-regression
cell, met.


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
3. **No external byte-exact acceptance for the step.** Section 3.2. Oracle A's floor is the
   instrument's four printed decimals. *Mitigation:* oracle B carries a byte-exact claim about the
   part this capability actually adds. *Residual risk accepted:* an error below 1e-4 that is uniform
   across every printed node would pass. Section 7 names the patch that would close it.
4. **A concat axis or stride error that is numerically plausible.** K and V concatenate on
   *different* axes (2.4). *Mitigation:* oracle B compares bytes, not values, and the
   `ds-plane-transposed` fixture asserts the failure is detected rather than absorbed.
5. **Lifting `MAX_PREFILL_TOKENS` weakens the prefill oracle at `T = 7`.** The constant's comment
   says the cap is the oracle's. *Mitigation:* the lift is documented at the constant, and no
   acceptance oracle uses a 7-token prefill — section 3.2 removed the only one that would have.
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
requests through **46**. The `agent/r5e-moe-model-prefill` branch adds **47** and **48**. Any
request this capability files must be renumbered at reconciliation against whatever has merged by
then, and
must not assume 47/48 are free. The same applies to the roadmap item number in section 9.

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
thirty-graph schedule — another full pass over the weights — inside a capability whose gate is
correctness and whose own section 3.3 says oracle C "gates nothing". Two documents produced by two
arms that already exist carry the same information. Section 3.2's measured curve, which is what
oracle C characterizes, is llama.cpp's own and is already recorded.

### 10.3 The seam's codes reach the document unchanged

Section 2.8 names `R6_BLOCK_MISSING` at step 7. The arm emits the container reader's own
`R5_BLOCK_MISSING`, `R5_LAYER_COVERAGE`, `R5_MEMBER_MISSING`, `R5_SHAPE`, and `R4_PACK_*` unchanged,
exactly as it emits the ggml seam's `R5_*` codes unchanged — because it **calls that reader** rather
than reimplementing it, and renaming a code at a module boundary would make two documents disagree
about one condition. The codes this arm owns are the ones it decides itself: `R6_ARITY`, `R6_PATH`,
`R6_TOKENS`, `R6_GEOMETRY`, `R6_GEOMETRY_UNREADABLE`, `R6_ARCH_UNSUPPORTED`, `R6_KV_WIDTH`,
`R6_PLANE_UNAVAILABLE`, `R6_PLANE_WRITE`, `R6_PLANE_MISMATCH`, `R6_TRANSCRIPT`, and
`R6_ORACLE_MISSING`. All twelve are reachable in the hosted owner except `R6_PLANE_WRITE` and
`R6_PLANE_UNAVAILABLE`, which are deferred in 10.5.

### 10.4 `MAX_PREFILL_TOKENS` moved two checked-in golden rows

Section 4.3 asks that "every existing R5A/R5B/R5C/R5D golden must be byte-identical after this
change". Two rows are not, and both are the lift of section 2.7 rather than the row work of section
2.4: `lf-tokens-seven` and `mf-tokens-seven` exist to assert the cap at seven tokens, and the cap is
eight now. They are renamed `lf-tokens-nine` and `mf-tokens-nine` and their operand becomes nine
tokens, which is one past the new cap exactly as seven was one past the old one.

**Nothing else moved.** `scripts/gpu-forward-golden.jsonl` and
`scripts/moe-layer-forward-golden.jsonl` are byte-unchanged; the other 74 rows of
`layer-forward-golden.jsonl` and the other 58 of `model-forward-golden.jsonl` are byte-unchanged;
and the fifth smoke block asserts `--model-forward`'s `slot_high_water` is still **52**, which is
section 2.3's whole reason for choosing slots 64 and 65.

### 10.5 Deferred closure cells

- **`R6_PLANE_UNAVAILABLE` and `R6_PLANE_WRITE` are not reached by a case.** Both are guards on
  conditions the arm's own validation makes unreachable — a `buffer` view shorter than the size the
  arm computed, and a `slot_get` that fills fewer bytes than the node declares — and neither has a
  forced build. They are dead in the shipped arm by construction, which is what the ledger asks of a
  guard, but section 4.2's cells for them are **deferred** rather than met.
- **`ds-plane-transposed`, `ds-plane-short`, and `ds-concat-dim-invalid`** as *fixture* mutations are
  not shipped. The first is covered by a stronger equivalent — a source mutation that transposes the
  K staging, which oracle B catches as `R6_PLANE_MISMATCH layer[0]tensor[k]col[0]`, recorded in the
  verification table below; the other two are deferred.
- **`ds-mask-offset-negative`** is not a case. `mf_write_mask_offset` returns without writing on a
  negative offset and no caller can supply one, so the cell is met by construction and not by a run.

### 10.6 Three functions are re-implemented rather than imported

`src/decode_step.align` carries its own `fail`/`fault_into`/`pack_fault_into`/`take`/`take_pack`,
its own `account` and `check_types`, its own `top_k`, and a compact prefill logits comparison, and
`src/model_forward.align` gained one new borrow-free entry point, `stage_plan_owned`, beside the
`stage_plan` this arm could not call. None of that was the plan; all of it is one measured Align
region-checker gap, now Align Request **49**, whose evidence is that 161 of the 178 errors in the
first cross-module draft were the single diagnostic "cannot retain a shorter-lived view through this
mutable borrow" and every one disappeared when the callee was moved into the calling module
unchanged.


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
| 2.2 written by the prefill, rows 12 and 10 | `capture_plane`, `PREFILL_K_ROW`/`PREFILL_V_ROW` | `plane.layers`, `plane.columns_written`; mutant `k-plane-transposed` |
| 2.2 read by the decode pass with `slot_set` | `stage_past_k`/`stage_past_v`, `decode_layer_values` | oracle B |
| 2.2 freed by Align at scope end | `schedule_decode`'s `mut plane: buffer` | `lifetime.*` balance on every case including every `ds-force-*` |
| 2.2 crossing by value, never by handle | `ggml_ffi.slot_get`/`slot_set` only | the `unsafe`/`extern` confinement scan |
| 2.3 slots 64/65, high-water 66, capacity 128 | `MF_SLOT_KPAST`/`MF_SLOT_VPAST` | `ds-engine-ok` asserts 66/128 **and** `--model-forward`'s 52 |
| 2.4 `WHEN_DECODE`, the concat rows, the two axes | `mf_decode_layer_node_table` | mutants `drop-k-concat` and `v-axis-swapped`, both `R5_SHAPE` |
| 2.4 positions are `[n_past]` | `decode_pos_image` | mutant `wrong-position-offset`, oracle A `FAIL` at 8092 |
| 2.4 mask `{KV_WIDTH, 1}` with offset | `mf_write_mask_offset` | mutant `mask-offset-off-by-one`, oracle A `FAIL` at 514 |
| 2.4 node count derived and recorded | `graph.node_count_total`, `decode.node_count` | golden; **corrected in 10.1** — 38 rows, not 36 |
| 2.4 last-layer narrowing kept at `t = 1` | rows 28/29 `WHEN_LAST` | oracle A `PASS`; no oracle row names them, so they are excluded by construction |
| 2.5 `op_concat` across six surfaces | `ggml_shim.c`, `ggml_shim_stub.c`, `ggml_ffi.align`, `OP_CONCAT`, `build_decode_nodes` | shared-region byte-identity, `unsafe`/`extern`, no-`malloc` scans; `ds-force-concat-axis` |
| 2.5 shared region untouched, no `build-ggml-shim` symbol list | both C files | the smoke's region comparison |
| 2.6 `token_ids` split from `positions` | `model_forward.graph_input_values` | `mf-*` goldens byte-unchanged; `ds-engine-ok` decodes at `n_past` |
| 2.7 `MAX_PREFILL_TOKENS` 6 → 8 | `src/layer_qwen2.align:43` | `lf-tokens-nine`, `mf-tokens-nine`, `ds-tokens-nine`; `layer_olmoe` unchanged at 6 |
| 2.8 validation order, steps 1–16 | `run`, `stage_inputs`, `execute`, `schedule_decode` | the `REQUIRED_CODES` set: 22 codes reached |
| 2.9 document kind, schema 1, three new objects | `decode_step.render` | every case asserts kind/schema; the golden is the shape |
| 2.9 no float on the wire | `render_plane`, `render_decode` | golden |
| 2.9 persisted identity `N/A` | nothing is persisted | stated; no cache key exists to test |
| 2.11 determinism | — | three consecutive runs byte-identical, hosted and on the real model |

### 11.2 The closure matrix (section 4)

| Cell | Evidence |
| --- | --- |
| 4.1 construction / success | `ds-engine-ok`; qualification asserts `plane.bytes == 29360128` |
| 4.1 failure (`R5_*` from the seam) | `ds-force-init`, `ds-force-alloc`, `ds-force-compute`, `ds-force-slot-range` |
| 4.1 malformed input | 20 `STUB_CASES` plus the 10 no-document cases |
| 4.1 early exit | `record()`'s `(returncode == 0) == (status == "ok")` on every case; every stub case asserts the plane is **not** published |
| 4.1 cleanup | `lifetime.*_created == *_freed`, `graph_balance_failures == 0`, per case |
| 4.2 plane construction | `plane.bytes`/`stride` asserted; `ds-plane-unavailable` **deferred** (10.5) |
| 4.2 plane success | `plane.layers`, `plane.columns_written`; oracle B |
| 4.2 plane failure (`R6_PLANE_WRITE`) | **deferred** (10.5) — no forced build reaches it |
| 4.2 `KV_WIDTH <= T` refused before allocation | `ds-kv-width-equal-t` |
| 4.2 early exit gates step 11 | `ds-force-compute` emits no `oracle_decode` verdict |
| 4.3 rows, slots, mask | mutants 1–4 |
| 4.3 wrong concat axis is a shape refusal | `ds-force-concat-axis` |
| 4.3 `mf_write_mask_offset(.., 0)` is `mf_write_mask` | by definition; `mf-*` goldens byte-unchanged |
| 4.3 **non-regression** | 10.4: two golden lines moved, both the token-cap lift; GPU and MoE goldens byte-unchanged |
| 4.4 id/position split | `mf-*` goldens byte-unchanged; `ds-prefill-matches-r5b` asserts the same logits digest |
| 4.5 shim/stub construction | the three source scans |
| 4.5 stub success | every `ds-*` case runs with no ggml at all |
| 4.5 `dim` outside `[0,3]` refused in Align | `ggml_ffi.op_concat`; **deferred** as a case (10.5) |
| 4.6 fixture decode mode | `ds-engine-transcript` consumes it; oracle A `max 0` |
| 4.6 mutated fixtures | `ds-transcript-onegraph`, `ds-transcript-kv-width`, `ds-transcript-perturbed`, `ds-transcript-garbage`; `ds-plane-transposed` replaced by a stronger source mutation (10.5) |
| 4.7 the fifth smoke block | 37 documented cases, its own `SystemExit(1)` |
| 4.7 the qualification never skips silently | `na()` prints one line and exits 0 |
| 4.7 cleanup on every exit path | `trap cleanup EXIT HUP INT TERM`, and the shim is restored |
