# R6-STEP-N

Status: implemented and measured, 2026-08-29

Stacked on `R6-DECODE-KV-STEP1` (`docs/specs/r6-decode-kv-step1.md`, branch
`agent/r6-decode-kv-step1` head `1671810`). That document is the ledger this one extends; every
section below that says "unchanged" means unchanged **from it**, and a row it does not restate is
still in force.

## 1. Decision and boundary

### 1.1 What this capability is

R6-DECODE-KV-STEP1 computes **one** decode step at `n_past = T` over an Align-owned KV plane and
stops. The plane is written once, by the prefill, and only read afterwards. So the model can answer
"what is the next token" and cannot answer "what are the next *N* tokens" — which is the question
every consumer of a coding model actually asks.

This capability ships the smallest change that makes the second question answerable: **an N-step
greedy decode loop over the same plane, grown in place one column per step, on CPU, on the dense
Qwen2.5-Coder-7B Q4_K_M**, gated on the **token ids** llama.cpp itself produces at `--temp 0 -s 0`.

**What it does not need is the headline.** R6's design pays off here almost completely:

| Needed by an N-step loop | State |
| --- | --- |
| A new ggml op or FFI symbol | **None.** `op_concat` ships; `slot_get`/`slot_set` already move plane bytes by value |
| A new node row or a change to the decode row table | **None.** `mf_decode_layer_node_table(g, n_past, width)` is already parameterised by `n_past` |
| A new slot | **None.** 64/65 are the plane slots; the high-water stays 66 |
| A new mask writer | **None.** `mf_write_mask_offset(window, width, height, row_offset)` already takes the offset |
| A change to `src/ggml_spike.align` | **None.** The dispatch arm exists |

What it does need is exactly four things: a **`STEPS` operand**, a **write-back** of each step's own
K and V column into the plane, **per-step iteration** of the three things that depend on `n_past`
(the node table, the offset mask, the position image), and a **token-id gate** — which section 3
shows is the hard part, and which the probe in section 3.1 changed.

### 1.2 Why a design gate is triggered

Two of the gate's four triggers fire.

- **A changed public CLI surface.** `--decode-step` gains a tenth operand and its arity set changes;
  `LOGITS` gains a `-` form; `MAX_PREFILL_TOKENS` moves again.
- **A changed exchanged format.** The `R6_DECODE_STEP` document goes to **schema 2**: a per-step
  array replaces a single `decode` object, and `plane`'s round-trip fields become cumulative.

It does **not** add an ownership/process/network boundary — the plane is still ordinary Align host
memory in one process, still never persisted. Whether it is a "coordinated invariant across three or
more modules" is arguable and is answered honestly rather than claimed: the change touches
`src/decode_step.align`, `src/model_forward.align` (one new column set), `src/layer_qwen2.align`
(two constants), `scripts/layer_forward_fixture.py`, and `scripts/run-decode-step`, but the
*invariant* they must agree on — the plane's layout, the slot numbering, the op codes — is R6's and
is unchanged. The third trigger is therefore recorded as **not fired**, and the closure matrix in
section 4 is built anyway, because the write-back introduces a new ordering invariant inside one
graph and that is precisely what a closure matrix is for.

### 1.3 Declared boundary

**In scope.** Dense Qwen2.5-Coder-7B Q4_K_M; CPU only; **N greedy steps**, `N` supplied by the
caller, `1 <= N <= MAX_DECODE_STEPS` and `T + N <= KV_WIDTH`; the plane held in memory for the
lifetime of one process and grown in place, never reallocated; `KV_WIDTH` supplied by the caller
exactly as today.

**Out of scope, declared non-goals.** Any sampler but greedy `argmax`; EOS/stop handling (section
2.12 records what the loop does instead, and why that is the honest choice for a correctness gate);
any eviction, tiering, invalidation, or prefetch policy; NVMe or GPU residency of the plane;
resident weights across steps (section 6, risk 1 — this is the capability that *measures* why they
are wanted, and deliberately does not build them); the Metal arm; OLMoE and any routed architecture;
a growing `KV_WIDTH`; batch size above one; **any TTFT or tokens-per-second claim.**

**Text is out of scope, and this is a decision, not an omission.** The gate is on **token ids**, not
on decoded text. There is no tokenizer or detokenizer in this repository: `src/gguf.align` reads the
*declared length* of `tokenizer.ggml.tokens` and materialises none of it, because indexing an array
of `string` is **Align Request 22**, `PROPOSED` and deliberately **non-blocking**. Gating on text
would make Request 22 blocking and would pull a BPE implementation into a runtime capability. It is
recorded here as a continuing client of Request 22 and **its status does not change**: this
capability introduces no consumer of a hypothetical string-array surface, and the one place text
would be useful — the external `llama-debug` corroboration leg of section 3.5 — stays
**hand-measured**, exactly as R6 section 10.5 left it.

## 2. Public-contract ledger

Fields marked `N/A` carry their reason. Every surface below is exact. Rows R6 already settled are
restated only when they change.

### 2.1 The surface decision: one arm, one more operand

The alternative was a second arm, `--decode-steps`, with its own document kind and its own golden.
It is rejected, with reasons, because the decision is load-bearing for every row below.

| Consideration | `--decode-step` + `STEPS` (**chosen**) | New `--decode-steps` arm |
| --- | --- | --- |
| Code paths for the same arithmetic | One. `N = 1` is the loop's first iteration, so "step 1 still works" is a property of the loop rather than a duplicated body | Two, diverging on first repair |
| The copy debt R6 section 10.6 records | Unchanged | Multiplied. That section already documents seven functions copied because Align Request 49 forbids the call; forking the arm forks the copies too |
| Golden churn | `scripts/decode-step-golden.jsonl` is rewritten at schema 2. It is **this capability's own file**, created by R6 and consumed by nothing else, which R6 section 10.4 already names as exempt from the non-regression rule | None on that file, but a second 40-row golden to maintain forever |
| The name | Free | **Taken.** `ds-arm-unknown-flag` passes the literal string `--decode-steps` as the flag that must be rejected (`scripts/run-layer-forward-smoke:2681`). Shipping the arm would silently turn a negative case positive |
| Consumer breakage | None. `ggml-spike` is an internal spike binary; `--decode-step`'s only callers are `scripts/run-decode-step` and the fifth smoke block, both in this repository | None |

The last row is why this is allowed at all: R6 section 7 names "step 2 and the decode loop" as the
natural next capability, so R6-STEP-N is entitled to generalise the arm rather than sit beside it.

`ds-arm-unknown-flag` keeps its role and changes its flag to `--decode-stepped`, which is not and
will not be an arm. It is a `NO_DOCUMENT` case and carries no golden row, so **that change costs
zero golden bytes** — verified against `scripts/decode-step-golden.jsonl`, whose forty rows are
listed in section 5.3 and contain no `ds-arity-*`, `ds-path-*`, or `ds-arm-*` case.

### 2.2 The arm and its operands

| Field | Contract |
| --- | --- |
| Surface | `ggml-spike --decode-step` — unchanged; the first operand and nothing else selects the arm |
| Owner module | `src/decode_step.align`, unchanged. `src/ggml_spike.align` is **byte-unchanged**: the dispatch arm and the arity set it forwards are already in place |
| Operand grammar | `--decode-step PACK GEOMETRY TOKENS DOCUMENT REFERENCE TRANSCRIPT KV_WIDTH LOGITS STEPS` |
| Arity | `args.len()` of 5, 6, 7, 9, 10, or **11**. **8 is still `R6_ARITY`**, for R6's own reason (a transcript without a width refuses itself). 12 and above are `R6_ARITY` |
| `PACK`, `GEOMETRY`, `DOCUMENT`, `REFERENCE`, `TRANSCRIPT` | Unchanged from R6 section 2.1 |
| `TOKENS` | Unchanged in form. Its bound moves with section 2.5's constant: `1 <= T <= MAX_PREFILL_TOKENS`, now 32. `R6_TOKENS` otherwise |
| `KV_WIDTH` | `args[8]`. Fail-closed, no default, unchanged. Its range **generalises**: `T + N <= KV_WIDTH <= MAX_ATTENTION_WIDTH` (4096). At `N = 1` this is R6's `T + 1 <= KV_WIDTH`, character for character. `R6_KV_WIDTH` otherwise |
| `LOGITS` | `args[9]`, a `llama-debug --save-logits` blob **or `-`**. The `-` form is new and exists only so that `STEPS` is reachable without a blob — `TRANSCRIPT` has used `-` for the same reason since R5B, so the convention is inherited, not invented. Empty string remains `R6_PATH` (`ds-path-logits-empty` is unchanged); `-` is `logits_present = false` |
| `STEPS` | `args[10]`, the decimal step count `N`. **Absent means 1** |
| Defaults | R6 section 2.1 says "there are none". **This capability adds exactly one, and it is recorded rather than absorbed:** `STEPS` absent is `N = 1`. It exists so that every schema-1-era invocation keeps its exact meaning, and its hazard — a caller who forgets the operand silently gets one step — is closed by publishing `decode.steps_requested` in **every** document, including error documents, so the count is never implicit in the output. No other operand acquires a value the caller did not write |

`STEPS` is last rather than earlier because every earlier position is spoken for and moving one
would change the meaning of an existing invocation silently. The cost of last position is the `-`
form of `LOGITS`, which is one ledger row and one case.

### 2.3 `STEPS` — range, cap, and the two refusals

| Field | Contract |
| --- | --- |
| Parse | Decimal, no sign, no whitespace. Unparseable is `R6_STEPS` detail `steps[<text>]` bounded to 256 bytes by `bounded_detail` |
| Range | `1 <= N <= MAX_DECODE_STEPS`. `R6_STEPS` detail `steps[<n>]` otherwise |
| `MAX_DECODE_STEPS` | New, `src/layer_qwen2.align`, value **64**. It is a fail-fast guard, not the real limit: the real limit is `T + N <= KV_WIDTH` and it is checked separately. 64 is chosen because beyond it the arm is a benchmark rather than a correctness check — at 64 steps one run is roughly sixty-four full passes over the weight set (section 6, risk 1) — and this capability makes no performance claim. A typo of `--decode-step ... 100000` must not allocate an hour |
| Plane bound | `T + N <= KV_WIDTH`, checked at validation step 6 as part of `KV_WIDTH`'s own range and raising **`R6_KV_WIDTH`**, not `R6_STEPS`. The condition is "the plane is too narrow for this run", and R6 already owns that sentence; two codes for one condition is how two documents come to disagree. Detail `kv_width[<n>]` unchanged |
| Precedence | `R6_STEPS` (parse and cap) is decided **before** `R6_KV_WIDTH` (plane bound), because `N` must be a number before `T + N` is one. With both invalid — `STEPS` of `0` and `KV_WIDTH` of `2` at `T = 3` — the code is `R6_STEPS`. `ds-steps-zero-and-narrow` asserts exactly that ordering |

### 2.4 The plane — growth, ownership, and the ordering invariant

The plane's layout, size, element type, allocator, zero-fill, and FFI crossing are **unchanged from
R6 section 2.2**. Two rows change and one is new.

| Field | Contract |
| --- | --- |
| Allocated by | `src/decode_step.align`, once, before the prefill, at the **declared `KV_WIDTH`** — unchanged, and this is why "grown in place" is not a reallocation. The buffer is already `KV_WIDTH` columns wide and zero-filled; growth means *writing further into it*, never resizing it. **Never reallocated and never grown in the allocator's sense** |
| Written by | The prefill, columns `0 .. T-1` (unchanged), **and now each decode step `k`, column `T + k - 1`**, one column of one layer's K and one of its V |
| Write-back source | The decode graph's **rows 12 and 10** — the post-RoPE K and the reshaped V of the new token, `{head_dim, n_head_kv, 1}` — read with `slot_get` after compute. These are the same two rows `capture_plane` already reads for the prefill, at `t = 1` instead of `t = T`. **The concat outputs (rows 16 and 22) are deliberately not the source:** row 22's V is transposed, so its new column is strided, and a strided write-back would be a second layout to get wrong. `capture_plane` gains a `first_column` parameter and nothing else |
| Columns written | `plane.columns_written == T + N` on a complete run |
| **Ordering invariant** (new) | R6 section 2.2 states "the plane is never both a `slot_get` destination and a `slot_set` source in one call", and names that as the whole reason step 2 was out of scope. **The invariant that replaces it is disjointness, not exclusion.** Within step `k`'s graph, in this order: (1) **before compute**, the plane's columns `0 .. n_past-1` are a `slot_set` **source**, uploaded into `MF_SLOT_KPAST`/`MF_SLOT_VPAST`; (2) compute; (3) **after compute**, the plane's column `n_past` — and only that column — is a `slot_get` **destination**. The two byte ranges are disjoint by construction and separated by a completed compute. No call is ever both, and no graph reads a column it also wrote |
| Aliasing | Follows from the row above and is asserted, not asserted-by-assertion: oracle B at step `k` compares the graph's concatenated operand against the plane over `T + k` columns, which is every column the plane holds. A write that landed in an uploaded column would be caught at the same step |
| Freed by | Align, at the end of `schedule_decode`'s scope. Unchanged |

**Every written column is verified inside the step that wrote it.** R6's `verify_plane` compares
`n_past` columns of an `n_past + 1`-wide operand, leaving the new column unchecked until — under
R6 — never. Here the write-back happens **before** verification and the comparison bound moves from
`n_past` to `n_past + 1`. That is a one-term change to `compare_past_k`/`compare_past_v`'s loop
bound and it closes a gap R6 shipped: the column the graph produced and the column the plane holds
are compared through two different nodes, so a write-back that lands one lane off is caught at
step `k` rather than at step `k+1` or not at all. Sections 3.4 and 4.2 record it.

### 2.5 `MAX_PREFILL_TOKENS`, again

| Field | Contract |
| --- | --- |
| Today | `src/layer_qwen2.align:62`, value **8**, lifted from 6 by R6 section 2.7 |
| Change | **8 → 32** |
| Why it must move | Oracle C′ (section 3.4) runs `--model-forward` at `TOKENS,d_1..d_k`, which is `T + k` tokens. At the qualification's `T <= 6` and `N = 16` the last checkpoint is **22 tokens**, and the arm would refuse its own oracle at 8 |
| Why 32 | The smallest power of two above the qualification's worst case of 22, with headroom for the next capability rather than exactly enough for this one — which is the mistake the 6 → 8 lift made and paid for immediately |
| Why the cap's original reason still holds | Unchanged and undamaged. The cap is the **oracle's**, not the arithmetic's: `llama-eval-callback` prints every row of a tensor only while `ne1 <= 6`. R6 shipped the mechanism that makes the reason enforceable rather than documentary — **`R5_ORACLE_TRUNCATED`**, raised by `--layer-forward` and `--model-forward` when `transcript_present && tokens.count > TRUNCATION_PRINTED`. That refusal is **byte-unchanged** and still fires at 7. The range is open for arithmetic and closed for comparison, at 32 exactly as at 8 |
| What it does **not** change | `--decode-step`'s own transcript oracle. Its decode graphs have `ne1 = 1` and print in full at any `T`; its prefill graph is compared only through R6's inherited path and the qualification runs it at `T <= 6` |
| `layer_olmoe.align:67` | **Unchanged at 6.** OLMoE is a declared non-goal, as in R6 |
| Golden consequence | Three cases exist to assert the cap and their token lists must move: `lf-tokens-nine` → `lf-tokens-33`, `mf-tokens-nine` → `mf-tokens-33`, `ds-tokens-nine` → `ds-tokens-33`. **The over-cap fixture is 33 repetitions of token id 1, not the list `1,2,…,33`:** the hosted geometry's `n_vocab` is 32, so an ascending list would be refused as out-of-vocabulary and the case would stop being about the cap. Section 5.3 records every moved row |

### 2.6 What iterates, and what does not

Three things depend on `n_past` and become per-step; everything else in `schedule_decode` is built
once. The distinction is the whole implementation.

| Object | Per step? | Contract |
| --- | --- | --- |
| `decode_nodes` = `mf_decode_layer_node_table(g, n_past, width)` | **Yes** | Already parameterised by `n_past`. Rebuilt at each step for `n_past = T + k - 1`. The table is pure and allocates nothing |
| `mask_decode` = `mf_write_mask_offset(buf, width, 1, n_past)` | **Yes** | Rewritten in place into the same `width * 4` buffer. `0.0` for columns `0 ..= n_past`, `-inf` above |
| `decode_pos_image` | **Yes** | Rewritten in place, one i32, value `n_past` |
| `decode_ids_image` | No | Constant `0`: it is the row index into the gathered embedding window, and the window holds exactly one row. The **token** changes; the **row index** does not. This is section 2.6 of R6 — the id/position split — doing its job, and it is why the loop needs no fourth per-step object |
| The embedding row itself | **Yes**, and it is a pack read | `decode_embed_members(g, ends, token_id)` then `fill_members(pak, …)`, once per step. This is where the loop's O(N × model bytes) cost lives, and section 6 risk 1 measures it rather than hiding it |
| Plane, slots, backend, weight window, logits buffers, `node_window` | No | Allocated once, reused across every step. `node_window` must be sized for the **widest** step's concat operand, `(T + N) * plane_column_bytes(g)`, not the first step's |
| `scan` / `ranges` (oracle A′) | **Yes** | `layer_forward.scan_transcript_after(path, oracle, k)` for step `k`, selecting transcript graph `k + 1`. Section 6 risk 3 records the cost of `N` rescans and why it is accepted |

### 2.7 Results, errors, and validation order

R6's steps 1–16 are unchanged in order and in code. Three insertions and one widening:

| # | Step | Code on failure | Detail |
| --- | --- | --- | --- |
| 1 | arity in {5,6,7,9,10,11} | `R6_ARITY` | `operands[<n>]` |
| 2 | supplied paths non-empty and of sane length; `LOGITS` of `-` is absent, not a path | `R6_PATH` | the operand's name |
| 3 | `TOKENS` parses, `1 <= T <= MAX_PREFILL_TOKENS` (32) | `R6_TOKENS` | `count[<n>]` |
| **3b** | **`STEPS` parses, `1 <= N <= MAX_DECODE_STEPS`** | **`R6_STEPS`** | `steps[<n>]` |
| 3a–5 | geometry readable, loads, dense | unchanged | unchanged |
| 6 | `KV_WIDTH` parses, **`T + N <= KV_WIDTH <= MAX_ATTENTION_WIDTH`** | `R6_KV_WIDTH` | `kv_width[<n>]` |
| 7–8 | pack members, plane sizing | unchanged | unchanged |
| 9–10 | prefill pass, plane readback of columns `0 .. T-1` | unchanged | unchanged |
| **11′** | **decode step `k`, for `k` in `1 ..= N`** | `R5_*`, `R6_PLANE_WRITE` | **every detail raised inside the loop is prefixed `step[<k>]`** |
| **12′** | **plane round trip at step `k`, over `T + k` columns** | `R6_PLANE_MISMATCH` | `step[<k>]layer[<n>]tensor[k\|v]col[<n>]` |
| 13–13a | transcript oracle at step `k`, graph `k + 1` | `R6_TRANSCRIPT`, `R6_ORACLE_MISSING` | `step[<k>]` prefixed |
| 14 | transcript's declared width equals `KV_WIDTH`, **at every step** | `R6_KV_WIDTH` | `step[<k>]kq[<n>]ne0[<n>]` |
| 15–16 | self-reference plane, logits blob | unchanged | unchanged |

**`R6_STEPS` is the one new code.** There is deliberately no `R6_STEP_FAILED`: a step that fails
fails for a reason that already has a code, and inventing a wrapper would mean every seam code has
two names depending on where it was raised. What the loop adds is a **locator**, and the locator is
the detail prefix. `bounded_detail`'s 256-byte cap is unchanged and `step[<k>]` costs at most nine
bytes against a `k` of at most 64.

### 2.8 Per-step failure — what the document holds

The requirement is that a partial run publishes what it completed. Exactly:

| Field | On a failure inside step `k` |
| --- | --- |
| `status` | `error`; exit code non-zero. R6's universal `(returncode == 0) == (status == "ok")` is unchanged |
| `error_code` / `error_detail` | The raising code, detail prefixed `step[<k>]` |
| `decode.steps_requested` | `N`, always — the operand the caller wrote |
| `decode.steps_completed` | `k - 1` |
| `decode.token_ids` | The `k - 1` ids decoded before the failure, in order. `[]` when `k = 1` |
| `steps[]` | `k - 1` complete objects. **A partial step publishes no object**: a half-filled step row is a row that says a step happened, and no step happened |
| `plane.columns_written` | `T + k - 1` |
| `plane.roundtrip_verdict` | The last completed step's, or `-` when no step completed. **Never `IDENTICAL` on an error document** |
| `oracle_decode` | The aggregate over the `k - 1` completed steps, or the empty record |
| The plane itself | **Freed.** It is an ordinary `buffer` at `schedule_decode`'s scope, freed on every path including this one |

**The stale-plane rule, stated because it is a named prior failure class.** A failure at step `k`
leaves the plane holding columns `0 .. T+k-2` valid and `T+k-1 ..` zero. The document says so
(`columns_written = T + k - 1`) and nothing reads the plane afterwards, because the loop is the only
reader and it has stopped. The R6 case that shipped this property for one step — an error document
publishing no round-trip verdict — is generalised to "an error document's `columns_written` is
exactly the number of columns some completed step verified".

### 2.9 Document, schema, and identity

| Field | Contract |
| --- | --- |
| `kind` | **`R6_DECODE_STEP`, unchanged.** The document describes the same thing — a decode over an Align-owned KV plane — and `N = 1` is a degenerate loop, not a different object. A new kind would force `scripts/run-decode-step` and the smoke to branch on kind for no semantic difference. This is what schema versions exist for |
| `schema_version` | **2** |
| Removed at 2 | The scalar `decode.{token_id, argmax, sha256, bit_sum, element_count, nonfinite_count, compute_ns, node_count}`. They described *the* step and there is no longer exactly one |
| `decode` at 2 | Loop-level only: `steps_requested`, `steps_completed`, `n_past_first`, `n_past_last`, `token_ids` (an array of `steps_completed` integers — **the field the gate reads**), `compute_ns` (sum), `node_count` (sum), `graph_count` (sum), `slot_high_water` (max over steps) |
| `steps[]` at 2 | `steps_completed` objects, in order, each: `index` (1-based), `n_past`, `token_id`, `argmax`, `sha256`, `bit_sum`, `element_count`, `nonfinite_count`, `compute_ns`, `node_count`, `plane_column_written`, and an `oracle` sub-object (`verdict`, `max_abs_diff_ten_thousandths`, `max_sum_diff_millionths`, `elements_compared`, `nodes_matched`, `nodes_expected`, `layers_matched`, `worst_node`, `worst_layer`, `instrument_graph`) |
| `plane` at 2 | R6's fields, with `columns_written` now `T + N`, `roundtrip_bytes_compared` summed over steps, `roundtrip_verdict` `IDENTICAL` **iff every step's was**, `readback_ns`/`upload_ns` summed, and one new `first_mismatch_step` beside the existing layer/tensor/column |
| `oracle_decode` at 2 | The aggregate: `steps_compared`, `verdict` (`PASS` iff every step `PASS`), `max_abs_diff_ten_thousandths` (max), `max_sum_diff_millionths` (max), `worst_step`, `worst_node`, `worst_layer`, `elements_compared` (sum), `nodes_matched`/`nodes_expected` (sums), `instrument_graph_first` (2), `instrument_graph_last` (`N + 1`), `instrument_kv_width`, `tolerance_ten_thousandths` |
| `output`, `oracle_logits`, `graph`, `model`, `selection`, `schedule`, `head`, `timings`, `lifetime`, `abi` | **Unchanged.** They describe the prefill, which this capability does not touch |
| Float fields | **Never floats on the wire, unchanged.** `token_ids` is an integer array; every digest is a hex `sha256` over exact little-endian f32 bytes; every tolerance is in integer ten-thousandths or millionths |
| Field presence | Every field above is present in **every** document, including error documents, with `steps[]` possibly empty, `token_ids` possibly empty, and string fields `-`. There is no conditional-presence rule and no operand-dependent shape: schema 2 is one shape at `N = 1` and at `N = 64` |
| Row order | `steps[]` is ordered by `index`, ascending, with no gaps. `token_ids[i]` is `steps[i].token_id` — the duplication is deliberate, so the gate can read one array without walking objects, and the smoke asserts the two agree on every case |
| Persisted identity | **N/A — nothing is persisted.** Unchanged from R6 section 2.9, including its note that "persisted" is the wrong word for this plane. No cache key, no generation counter, no compatibility rule |
| Cache identity | **N/A**, same reason |
| Timing fields | Zeroed by `normalize` before every golden compare. **New and load-bearing:** `normalize` must also zero `steps[i].compute_ns` for every `i`, and `plane.readback_ns`/`upload_ns`. A per-step timing array is the exact place a golden goes non-deterministic, and section 6 risk 5 records it as a named prior failure class |

### 2.10 Metrics

Characterization only. **No TTFT claim, no tokens-per-second claim, no comparison to llama.cpp's
wall time**, and no cost ceiling recorded in a ledger row, because this capability makes no
performance claim and `CLAUDE.md`'s performance row is therefore not selected.

| Metric | Source | Reported as |
| --- | --- | --- |
| Per-step compute | `steps[i].compute_ns` | The per-step curve, section 5 |
| Plane crossings | `plane.readback_ns`, `plane.upload_ns`, summed over the loop | Totals plus the per-step mean |
| Plane size | `plane.bytes` | 29,360,128 at width 256 on this model, unchanged |
| Bytes verified | `plane.roundtrip_bytes_compared` | `Σ_{k=1..N} 2 · n_layer · (T+k) · n_head_kv · head_dim · 4` |
| **Loop cost against N** | `timings.elapsed_ns` at `N ∈ {1, 4, 16}` on one prompt | Section 5's scaling row. This is the measurement that motivates resident weights and it is the reason to take it |

**Saturation, checked rather than assumed** (a named prior failure class). Every accumulated
quantity is `i64` and every one is bounded by `N <= 64`. The largest is
`roundtrip_bytes_compared`: at `n_layer` 28, `N` 64, `T` 6, `KV_WIDTH` 4096 the sum is under
`2 · 28 · 64 · 4096 · 2048` ≈ 3.0 × 10^10, four orders below `i64`'s range. `elements_compared` is
under `64 · 5058` ≈ 3.2 × 10^5. `compute_ns` over 64 steps of a 7B model is under 10^11 ns. Nothing
here saturates and nothing needs a widened accumulator.

### 2.11 Prerequisites

| Prerequisite | State |
| --- | --- |
| Everything R6 lists | Shipped, unchanged |
| `R6-DECODE-KV-STEP1` merged, or this branch stacked on its head | **Stacked** on `1671810`. If R6 merges with repairs, this capability takes `git merge origin/main` — never a rebase, so R6's recorded commits stay reachable — and re-runs its owner |
| `llama-eval-callback`, R2C-patched, at the pin, honouring `-n N` | **Probed and confirmed** at `-n 4` (section 3.1). Generation `r2c-v2` is unchanged and **no patch change is taken** |
| Align language features | None new. Section 8 records the gaps encountered; none blocks this capability |

### 2.12 Greedy, and no EOS handling

The loop samples `argmax` and **does not stop at EOS**. That is a decision with a reason, recorded
rather than left to be discovered:

- The gate compares against `llama-eval-callback --temp 0 -s 0`, whose R2C patch **does** break at
  `llama_vocab_is_eog(vocab, token)` (`patches/llama.cpp/r2c-decode-instrument.patch`). So if a
  prompt reached EOS, llama.cpp would emit fewer than `N + 1` graphs and this arm would emit `N`
  steps, and the two would disagree about the run's length rather than about its arithmetic.
- The honest handling for a **correctness gate** is therefore not to implement EOS but to **detect
  the disagreement**: the runner counts the transcript's graphs and refuses the prompt if it is not
  exactly `N + 1`, naming EOS as the likely cause. That is one assertion, it cannot pass vacuously,
  and it keeps `is_eog` — a vocabulary-metadata question that needs Request 22's surface to answer
  properly — out of a capability that has no tokenizer.
- The four qualification prompts are code fragments at `T <= 6`, and the probe at `-n 4` reached
  four steps without EOS. Section 6 risk 4 records the residual risk that one of them reaches EOS
  before step 16, and the runner's graph-count refusal is its mitigation.
- Real generation needs EOS, a sampler, and stop strings. All three are **deferred** (section 7):
  they belong to the capability that produces text, and that capability needs a detokenizer, and
  that needs Request 22.

## 3. Oracles

### 3.1 The probe, and its result

The brief carried two assumptions. **The first is confirmed and the second is false**, and the
second changes the gate's design.

Run at the exact pin, on the qualification's first prompt, `2026-08-29`:

```text
$ EC=$(python3 scripts/llama-eval-callback-toolchain path instrument)
$ "$EC" -m qwen2.5-coder-7b-instruct-q4_k_m.gguf -p "def add(a, b):" \
    -n 4 -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512 --temp 0 -s 0
```

`5.06 s` wall, `5,252,220 B`, `87,816` lines.

**Confirmed — `-n N` emits exactly `N + 1` graphs.** Five `embd` headers: one prefill
(`inp_tokens{6, 1, 1, 1}`) and four decode (`inp_tokens{1, 1, 1, 1}`). The prefill graph is 28,511
lines and each decode graph is 14,826.

**Confirmed — the width is matched at every step.** `kq-0` is
`MUL_MAT(cache_k_l0 (view) (permuted){128, 256, 4, 1}, Qcur-0 (view) (permuted){128, 1, 28, 1})` in
graphs 2, 3, 4, and 5 alike, and `cache_k_l0 (view)` is `{512, 512, 1, 1}` throughout. llama.cpp
reduces over the full 256 columns at **every** step, masked — which is exactly what this arm's
`PAD`-to-`KV_WIDTH` design does. So oracle A′'s shape assertions are step-invariant and the
`instrument_kv_width == KV_WIDTH` check holds at every `k`.

**False — the transcript does not expose the sampled token, and neither does `result_output`.**
Both routes the brief named were tested and both fail:

1. **`inp_tokens` is a leaf, not a node.** It never appears as a printed tensor. Its *shape* appears
   inside the `embd` header and its *value* appears nowhere. A `grep` for `inp_tokens` at the start
   of a `common_debug_cb_eval:` node line returns nothing across all 87,816 lines.
2. **`result_output`'s argmax is not derivable.** The tensor is `{152064, 1, 1, 1}` and
   `common_debug_print_tensor` is called with a print limit of 3, so the transcript holds the first
   three values, the last three, and a `sum` — six of 152,064. Graph 1 prints
   `[1.5801, 4.2062, 12.7578, ..., -2.7406, -2.7406, -2.7406]` and `sum = -235051.734375`. There is
   no argmax to read.
3. **The instrument's stderr prints only the *prompt* token ids** — `number of input tokens = 6`
   then `750 912 2877 11 293 1648`. Nothing is printed for a sampled token. The R2C patch's decode
   loop (`common_sampler_sample` → `common_sampler_accept` → `llama_decode`) logs nothing.

**The route that does work, and the reason it is exact rather than approximate.** Graph `j`'s first
node is

```text
embd = (f32) GET_ROWS(token_embd.weight{3584, 152064, 1, 1}, inp_tokens{1, 1, 1, 1}) = {3584, 1, 1, 1}
```

which is *the embedding row of the token sampled at graph `j-1`*. `GET_ROWS` is a copy of a weight
row: **no arithmetic happens**, so if two runs agree on the token they agree on those bytes
exactly, and the only question is whether two *different* vocabulary rows can print identically.
The measured fingerprints are well separated:

| Graph | printed `embd` row (first 3 … last 2 of the printed six) | `sum` |
| --- | --- | --- |
| 2 (`d_1`) | `0.0001, -0.0054, 0.0001, …, 0.0198, -0.0169` | `1.153733` |
| 3 (`d_2`) | `0.0126, 0.0070, -0.0206, …, 0.0263, 0.0048` | `0.351714` |
| 4 (`d_3`) | `-0.0085, 0.0019, 0.0070, …, -0.0071, 0.0024` | `-1.503967` |
| 5 (`d_4`) | `0.0025, 0.0199, 0.0069, …, -0.0001, -0.0217` | `-0.402806` |

Section 3.2 turns "well separated on four samples" into a measured claim over the whole vocabulary.

**The counting that follows, and it is exact.** With `-n N` there are `N + 1` graphs. Graph `j`
(`j = 2 .. N+1`) consumes `d_{j-1}`. This arm's step `k` consumes `d_k` and produces `d_{k+1}`.
So **this arm's `N` decode graphs are llama.cpp's graphs 2 through `N+1`, one for one**, and the
`N` ids `d_1 .. d_N` are each exposed exactly once, as the `embd` of the graph that consumed them.
`-n N` is therefore the right instrument invocation for an `N`-id gate — not `-n N+1` — and no id
is left ungated. `d_{N+1}`, which this arm computes at its last step and llama.cpp computes at its
last graph, is consumed by neither and is **excluded by name**, reported in the document as
`steps[N].argmax` and gated by nothing.

### 3.2 Gate G — the token-id gate

The gate is on ids. It has two legs that run every time and one that is named and not taken.

**G1 — `d_1` is byte-exact, and it is inherited.** R6's `oracle_logits` asserts that this arm's
prefill logits are **byte-identical** to `llama-debug --save-logits` on the same prompt at the same
width — 608,256 bytes, `verdict: IDENTICAL`, `byte_identical: true`, on all four prompts, measured
three times (R6 section 5.1). `d_1` is the `argmax` of that vector. An argmax over a byte-identical
vector is llama.cpp's own argmax, **literally, with no tolerance**. So the chain's root is exact and
it is already shipped. This capability changes nothing about it.

**G2 — `d_1 .. d_N` through the `embd` fingerprint.** For each step `k`, oracle A′ compares this
arm's decode graph `k` against transcript graph `k+1`, and the `embd` node of that graph is
`GET_ROWS(token_embd.weight, [d_k])`. If this arm's `d_k` differs from llama.cpp's, the compared
bytes are two different vocabulary rows, and the comparison fails unless those two rows agree on
their first three values, on their last three, and on their whole-row sum.

**That injectivity is a measurement, not an assumption, and this capability takes it.** Before the
gate is claimed, `scripts/decode_step_fingerprint.py` — invoked by `scripts/run-decode-step`, once
per qualification — computes the fingerprint
`(v[0], v[1], v[2], v[n-3], v[n-2], v[n-1], Σv)`, quantised to the instrument's own `%12.4f` and
`%f` precision, for **all 152,064 rows** of `token_embd.weight`, and records the collision classes.

- **If the collision count is 0**, G2 is a token-id equality and the ledger says so without
  qualification.
- **If it is not 0**, the colliding ids are printed by name, and the gate holds unless a decoded
  `d_k` is a member of a colliding class — which the runner checks per step and fails on. The
  fallback beyond that is G3.

**Measured (section 5.1): the count is not 0, and the shape of the answer is what matters.** Over
the qualification model's Q4_K `token_embd.weight` there are **149,710 distinct fingerprints and
exactly one collision class**, and that class is **precisely the 2,355 all-zero rows** — the unused
vocabulary slots of a 151,665-token vocabulary padded to 152,064. Every row with any non-zero
element is unique. So the second bullet applies rather than the first, and it applies in its
strongest form: G2 is a token-id equality on the whole *used* vocabulary, and the one class it
cannot separate is a set of rows an argmax over real logits cannot reach without the model having
already failed. The runner checks membership per step and refuses by name, so the gate cannot pass
by accident on a colliding id. **G3 is therefore not taken.**

**One refinement, and it makes the gate assume less rather than more.** The comparison gates on the
**six printed values** and records the `sum` as corroboration rather than as a condition. The reason
is the sum's provenance: it is one `float` sequential accumulation over 3,584 dequantized values
*inside the reference build*, so its last printed digit is exposed to that build's floating-point
contraction, while the six printed values are copies of weight bytes and are not. The measurement
was taken for **both** keys and they select the same classes — 149,710 distinct either way, one
class either way — so gating on the six costs nothing. Section 5.1 records that the sums also agreed
on every compared graph of every prompt.

Writing the gate without this measurement would be exactly the "vacuous per-step assertion" this
design is required to avoid: a comparison that looks like an id check and is really a hope about a
vocabulary nobody measured.

**The chain property, which is what makes `N` ids gateable at all.** `d_k` is the *input* to this
arm's step `k` and to llama.cpp's graph `k+1`, and this arm's `d_{k+1}` is computed from step `k`'s
logits. So a divergence at step `j` cannot be absorbed later: it changes step `j`'s `embd`, and it
changes every subsequent step's input, `embd`, and logits. The `N` ids are gated as one chain rooted
at G1's byte-exact `d_1`, and a single mismatch anywhere fails the run at the first step it reaches.

**G3 — the exact-id upgrade, named, costed, and not taken.** One line in the R2C patch's decode
loop, logging the sampled token id and the step index, would make the gate a literal integer
comparison. Cost: a new `PATCH_SHA256` and `PATCH_BYTES`, a generation bump `r2c-v2` → `r2c-v3`, a
full rebuild of the cached llama.cpp tree, and a re-run of the R2C qualification. It is **not
taken** because G1 plus a measured-injective G2 carry the claim, and R6 section 7 already holds one
open `llama-debug` patch decision that this capability should not pre-empt with a second. It is
section 7's first deferred item and it is the declared response if section 5's collision count is
not 0.

### 3.3 What is not available, and stays hand-measured

R6 section 5.1 corroborated its oracle C once, by hand, against `llama-debug --save-logits` on the
text `"def add(a, b): #"` — the prompt plus the decoded token's text. That leg **cannot be
automated here and is not attempted**, for the reason R6 section 10.5 already gives and which gets
worse with `N`: `llama-debug`'s operand is a **prompt string**, this arm holds **token ids**, and
turning `d_1 .. d_16` into a string means either detokenizing — which nothing in this repository
does, and which is Align Request 22's surface — or guessing sixteen tokens' text, which is exactly
what should not be automated on an assumption.

So: **the external `llama-debug` text leg stays hand-measured, one prompt, one step, as R6 left it.
Request 22 stays `PROPOSED` and non-blocking, and this capability adds no consumer to it.** It is
recorded here explicitly so that a later reader does not mistake its absence for an oversight.

### 3.4 The oracle set

**Oracle B — the plane round trip (internal, byte-exact, acceptance, per step).**
At step `k`, after the write-back, the K and V the decode graph actually consumed — its two `CONCAT`
nodes read back with `slot_get` — must be **byte-identical** to the plane over columns
`0 .. T+k-1`, on every layer. Two things change from R6:

1. It is **cumulative**. At step `k` the comparison covers the prefill's `T` columns *and* every
   column a previous step wrote, so step `k` re-verifies all of step `k-1`'s work. A write-back that
   is correct at the moment it happens and corrupted later is caught.
2. It **includes the new column** (`T + k` columns, not `T + k - 1`), because the write-back
   precedes verification. The column the graph produced (rows 12/10) and the column the plane
   holds are compared through a *different* node (rows 16/22), so a write-back one lane off, or in
   the wrong tensor, or at the wrong column, dies in its own step. Section 2.4 records this as the
   gap R6 shipped.

`roundtrip_verdict` is `IDENTICAL` iff every step's was; `R6_PLANE_MISMATCH` is unreachable in a
passing run and its detail names the step.

**Oracle C′ — the single-shot self-reference (acceptance, at checkpoints).**
At checkpoint `k`, `--model-forward` at `TOKENS,d_1,…,d_k` and the same `KV_WIDTH`, with `-` in the
transcript position, must produce logits **byte-identical** to `steps[k].sha256`. R6 section 5.1
measured this identity for `k = 1` on all four prompts and promoted the oracle from characterization
to acceptance; the reason it holds is that every operand this arm hands ggml is a contiguous F32
tensor, so its decode path and its prefill path take the same kernel. That reason does not weaken
with `k`, so C′ is acceptance at every checkpoint it runs at.

**Checkpoints are `k ∈ {1, ⌈N/2⌉, N}` — at `N = 16`, `{1, 8, 16}` — and not every step.** Each C′ is
a whole `--model-forward`: thirty graphs and a full pass over the 4.7 GB weight set. Sixteen
checkpoints × four prompts is sixty-four such passes; three × four is twelve. The three are chosen
to bound three regimes rather than to sample uniformly: `k = 1` is the case R6 already measured and
is the only one with a prior result to disagree with; `k = N` is the deepest accumulation and the
one a drift would show in first; `k = ⌈N/2⌉` catches a divergence that begins mid-loop and would be
invisible at both ends. Per-step C′ is deferred (section 7) with its cost recorded here.

**Oracle A′ — the per-step transcript (external, characterization, with a structural gate).**
`llama-eval-callback`, R2C-patched, at the pin, invoked
`-p PROMPT -n N -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512 --temp 0 -s 0`. At step `k` the
arm compares its decode graph against transcript graph `k+1` at 1 ten-thousandth.

**A′ is demoted from acceptance to characterization at steps 2..N, and the demotion is measured,
not defensive.** R6 section 5.1 measured that at `T = 6, N = 1` oracle A already **`FAIL`s** at
2391/1e-4 on `ffn_inp-27`, and section 3.2 of that document attributes it: llama.cpp's own decode
graph takes a different `MUL_MAT` accumulation path from its own multi-column prefill
(`LLAMAFILE = 1`), and the divergence rises with depth — `l_out-19` 0.0554, `l_out-23` 0.1229,
`ffn_inp-26` 0.1699, `ffn_inp-27` 0.2391. **That is llama.cpp disagreeing with itself, and across
`N` steps it compounds through the KV cache as well as through depth.** Gating acceptance on a
quantity whose growth is a property of the reference implementation would make the qualification
fail for a reason this arm cannot fix and does not own. R6's admission rule — `FAIL` admitted inside
0.5 *and* with oracle C byte-identical — depends on oracle C running on that prompt, and C′ runs at
three checkpoints, not at every step; extending the conjunction to "the nearest checkpoint at or
after `k`" would weaken it into something that reads like a gate and is not one.

**What A′ *does* assert at every step, unconditionally, is structural, and none of it can pass
vacuously:**

| Assertion | What it catches |
| --- | --- |
| `instrument_graph == k + 1` | A mis-aligned graph skip — comparing step 3 against graph 2 |
| `nodes_matched == nodes_expected` and `nodes_expected == 1 + 17·n_layer + MF_HEAD_ORACLE_COUNT` | A truncated transcript, a renamed node, a dropped layer |
| `layers_matched == model.n_layer` | A comparison that quietly covered four layers of twenty-eight |
| `elements_compared > 0` | The empty comparison `R6_ORACLE_MISSING` exists for, now per step |
| `instrument_kv_width == KV_WIDTH` and every `kq` `ne0 == KV_WIDTH` | A width drift mid-loop; confirmed step-invariant by section 3.1's probe |
| `tolerance_ten_thousandths == 1` | A silently widened tolerance |

At **step 1 only**, R6's full admission rule applies verbatim and unchanged, because C′'s first
checkpoint is exactly the prompt-level oracle C that rule was written against: A′ at step 1 must be
`PASS`, **or** `FAIL` with both `max_abs_diff <= 5000` ten-thousandths and C′ at `k = 1`
byte-identical. Section 5 records the per-step curve for steps 2..N as a measurement, and no
acceptance decision is taken from it.

**Determinism.** Three consecutive runs must be byte-identical after `normalize`, over four prompts.

### 3.5 The shipped acceptance rule, stated once

Sections 3.2, 3.4, 4, and 5 refer to this rule; they do not restate it.
`scripts/run-decode-step` implements it and its comment quotes it.

> For every prompt, all of the following, unconditionally:
>
> 1. **Gate G.** `decode.token_ids` has `N` entries and each `d_k` equals llama.cpp's, evidenced by
>    G1 for `d_1` (byte-exact against `llama-debug`) and by G2 for `d_1 .. d_N` (the `embd`
>    fingerprint of transcript graph `k+1`), over a vocabulary whose fingerprint collision classes
>    were measured in this run and none of whose members any step decoded.
> 2. **Oracle B.** `plane.roundtrip_verdict == "IDENTICAL"` over a positive byte count, with every
>    step's own verdict `IDENTICAL`.
> 3. **Oracle C′.** At `k ∈ {1, ⌈N/2⌉, N}`, `steps[k].sha256` equals `--model-forward`'s
>    `output.sha256` at `TOKENS,d_1..d_k` and the same width.
> 4. **Oracle A′, structural.** Every assertion in section 3.4's table, at every step.
> 5. **Oracle A′, numeric, at step 1 only.** `PASS`, or `FAIL` with both `max_abs_diff <= 5000`
>    ten-thousandths and C′ at `k = 1` byte-identical.
> 6. **Determinism.** Three consecutive runs byte-identical after `normalize`.
> 7. **The transcript holds exactly `N + 1` graphs.** Fewer means llama.cpp stopped early — EOS
>    (section 2.12) — and the prompt is refused rather than compared over a shorter run.
>
> A′ at steps 2..N is **characterization**: its per-step maxima are reported, and no acceptance
> decision is taken from them.

### 3.6 The tolerance rule

| Comparison | Rule | Value | Derivation |
| --- | --- | --- | --- |
| Gate G, `d_1` | **exact integer equality** | 0 | An argmax over a byte-identical 608,256-byte vector. No tolerance exists to set |
| Gate G, `d_k` via `embd` | **exact, conditional on a measured property** | 0 | `GET_ROWS` is a copy, not arithmetic; equal ids give equal bytes. The comparison runs at the instrument's `%12.4f` over the six printed values, and section 3.2's collision measurement is what makes "equal printed bytes" mean "equal id". Measured in section 5.1: one collision class, covering only all-zero rows |
| Oracle B | **byte identity** | 0 | A byte plane either survives a round trip or it does not. Admitting a tolerance would only admit a bug. Unchanged from R6 |
| Oracle C′ | **byte identity** | 0 | Measured by R6 section 5.1 at `k = 1` on four prompts and re-measured here at three checkpoints. Unchanged from R6 |
| Oracle A′, per element | absolute | **1 ten-thousandth** | The instrument prints `%12.4f`. Inherited unchanged from R5A/R5B/R6 |
| Oracle A′, per-tensor sum | absolute, then relative | **1000 millionths**, or **10 ppm** for large sums | Inherited unchanged |
| Oracle A′ step-1 admission bound | absolute | **5000 ten-thousandths** | R6 section 3.4's, unchanged and applied only where R6 applied it |
| Oracle A′, steps 2..N | **no numeric bound** | N/A | Deliberate. Section 3.4 gives the measured reason; the structural assertions are what is gated |

**Byte identity is claimed three times about three different things,** and the distinction is R6's:
oracle B claims it about **bytes** crossing a boundary, oracle C′ about **arithmetic** against this
arm's own single-shot prefill, and `oracle_logits` about the **prefill** against llama.cpp. Gate G
adds a fourth claim of a different kind — **integer equality of ids** — and it is the one the
capability is named for.

## 4. Closure matrix

Every cell names the implementation and the exact regression. `T` is the prefill length, `N` the
step count, `k` a step index.

### 4.1 `src/decode_step.align` — the arm and the loop

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `run` parses `STEPS`, validates `N` and `T + N <= KV_WIDTH`, sizes `node_window` for the widest step, allocates the plane once | `ds-engine-ok` (`N` absent ≡ 1, document byte-comparable with R6's shape at schema 2); `ds-steps-3` asserts `steps_requested == 3`, `steps_completed == 3`, `columns_written == T + 3` |
| Success | prefill → plane → `N` × (upload, compute, write-back, verify, decode) → document, `status: ok`, exit 0 | `ds-steps-3`; qualification asserts section 3.5's rule at `N = 16` |
| Failure | any step's seam code, detail prefixed `step[<k>]` | `ds-force-compute-step2` (a forced build keyed on the decode graph's one-column shape **and** `n_past > T`, so it fires at step 2 and not step 1) → `R5_COMPUTE` detail `step[2]` |
| Malformed input | validation steps 1, 2, 3, 3b, 6 | `ds-arity-12`, `ds-steps-empty`, `ds-steps-zero`, `ds-steps-negative`, `ds-steps-over-max` (65), `ds-steps-trailing` (`3,`), `ds-steps-zero-and-narrow` (precedence), `ds-kv-width-narrow-for-steps` (`T=3, N=3, width=5` → `R6_KV_WIDTH`), `ds-logits-dash`, `ds-tokens-33` |
| Early exit | a failing step publishes `steps_completed = k-1`, `steps[]` of `k-1` objects, `token_ids` of `k-1` ids, `columns_written = T+k-1`, non-`IDENTICAL` round trip, and still frees the plane | `ds-force-compute-step2` asserts all six; `record()`'s universal `(returncode == 0) == (status == "ok")` on every case |
| Cleanup | the plane and every per-step buffer are ordinary `buffer`s at `schedule_decode`'s scope; ggml contexts/buffers/gallocrs balanced **after `N` graphs**, not after two | `lifetime.*_created == *_freed` and `graph_balance_failures == 0`, asserted per case; `ds-steps-3` is the case where an unbalanced per-step context would show as `3 × n_layer` leaked |
| Move-in/out, source nulling, replacement, return | **N/A — no ownership transfer is added.** `Plane` and `Decode` are returned by value as R6 section 10.6 records; the new per-step data travels as column sets (4.4), which is the module's existing pattern. No value is moved out of a record and no source is nulled | stated, with reason |

### 4.2 The KV plane, grown

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `buffer(plane_bytes)` at the declared `KV_WIDTH`, zero-filled, once. **Unchanged** | `plane.bytes`/`stride` on every engine row; 29,360,128 on the real model |
| Success | prefill writes `0..T-1`; step `k` writes column `T+k-1` from rows 12/10 at `t = 1` | `plane.columns_written == T + N`; oracle B at every step |
| Failure — write-back short | `slot_nbytes` on rows 12/10 must equal one column | `R6_PLANE_WRITE` detail `step[<k>]layer[<n>]tensor[k\|v]`. **Deferred as a case** (section 7's last bullet): the arm's own sizing makes it unreachable and no forced build produces it, exactly as R6 section 10.5 deferred it for the prefill |
| Failure — round trip | `compare_past_k`/`compare_past_v` over `T+k` columns | `ds-force-plane-stage-offset` (R6's, retained) at step 1; **new** `ds-force-writeback-offset` shifts the step's own written column by one lane and must report `R6_PLANE_MISMATCH step[1]layer[0]tensor[k]col[<T>]` — the column index is `T`, which is what proves the *new* column is compared and not only the past ones |
| Malformed input | `T + N > KV_WIDTH` refused before allocation | `ds-kv-width-narrow-for-steps`; `ds-kv-width-equal-t` unchanged (`T=3, N=1, width=3`) |
| Early exit | a failure at step `k` leaves columns `>= T+k-1` zero; nothing reads them | `ds-force-compute-step2` asserts `columns_written == T + 1` |
| Cleanup | freed at scope end on every path | as 4.1 |
| **Ordering / aliasing** | upload columns `0..n_past-1` → compute → write column `n_past`. Disjoint ranges, separated by a completed compute (2.4) | `ds-force-writeback-offset` and oracle B's inclusion of column `n_past`; a write into an uploaded column changes a column oracle B compares in the same step |

### 4.3 `src/layer_qwen2.align`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `MAX_PREFILL_TOKENS` 8 → 32; `MAX_DECODE_STEPS := 64`. **Nothing else.** No new row, op, slot, selector, or mask writer | `ds-tokens-33`, `lf-tokens-33`, `mf-tokens-33`, `ds-steps-over-max` |
| Success | `mf_decode_layer_node_table(g, n_past, width)` and `mf_write_mask_offset(.., n_past)` called per step with the step's `n_past` | oracle A′ structural at every step; `ds-force-mask-offset` (R6's) retained |
| Failure | N/A — both are pure and total over their inputs | stated, with reason |
| Malformed input | N/A — `n_past` is computed by the arm and bounded by validation step 6 | stated, with reason |
| Early exit / Cleanup | N/A — pure, allocates nothing | stated, with reason |
| **Non-regression** | The prefill row table, `WHEN_DECODE`, `OP_CONCAT`, slots 64/65, and `mf_write_mask` are untouched | **`scripts/gpu-forward-golden.jsonl` and `scripts/moe-layer-forward-golden.jsonl` byte-unchanged; every row of `layer-forward-golden.jsonl` and `model-forward-golden.jsonl` byte-unchanged except the one cap row each** (5.3) |

### 4.4 `src/model_forward.align`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | One new column set, `StepColumns { n_past, token_id, argmax, bit_sum, element_count, nonfinite_count, compute_ns, node_count, plane_column, oracle_max_abs, oracle_max_sum, oracle_elements, oracle_nodes_matched, oracle_nodes_expected, oracle_layers, oracle_graph : array<i64>; sha256, oracle_verdict, oracle_worst_node : array<str> }`, built by `schedule_decode` and handed out as an out-parameter beside `ScheduleColumns`/`TopColumns`/`GraphColumns` | `ds-steps-3`'s golden is the shape |
| **Why a column set and not `Outcome` fields** | R6 section 10.6 records that `model_forward.Outcome` is already **1,328 bytes**, passed by value at ~25 new call sites, and that the compiler warns. Adding `N` per-step scalars would make it grow with an operand. Column sets are the module's existing answer for callee-local `array<i64>` and they keep `Outcome` at its current size | the compiler's own size warning, unchanged in count |
| Success | the prefill path is untouched; `graph_input_values`'s id/position split is R6's, unchanged | `model-forward-golden.jsonl` byte-unchanged but for the cap row |
| Failure | a length mismatch between a column set and `steps_completed` | asserted in `render`: every array in `StepColumns` has `steps_completed` entries or the document is not written |
| Malformed input / Early exit / Cleanup | unchanged | existing `mf-*` cases |

### 4.5 `src/ggml_ffi.align`, `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`

| Phase | Implementation | Regression |
| --- | --- | --- |
| **All phases** | **N/A — byte-unchanged.** No new op, no new symbol, no new wrapper. `op_concat` ships with R6; `slot_get`/`slot_set`/`slot_mark_output` already carry every crossing this loop needs, and the write-back marks two nodes the decode graph already builds | The shared-region byte-identity check (`run-layer-forward-smoke:57-64`), the `unsafe`/`extern` confinement scan (`:75-86`), and the no-`malloc` scan (`:65-68`) all pass **without a diff to check**, which is the evidence that this row is honest |

The only change anywhere near the seam is **two more `slot_mark_output` calls on the decode graph**
(rows 12 and 10), which mark nodes the graph already contains. Node count is unchanged; the
`decode.node_count` per step is R6's 78-node figure for the hosted fixture and is asserted in the
golden.

### 4.6 `src/ggml_spike.align`

| Phase | Implementation | Regression |
| --- | --- | --- |
| **All phases** | **N/A — byte-unchanged.** The dispatch arm forwards `args` and the arity set lives in `decode_step.run` | `ds-arm-unknown-flag` (now `--decode-stepped`) still exits non-zero with no document |

### 4.7 `scripts/layer_forward_fixture.py` — the K-step reference

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `write_decode_corpus` extends its **two-call** reference to a **loop of `K` calls**: prefill, then `K` iterations of `model_decode` at `n_past = T + k - 1`, each appending its own K and V column to `planes` before the next. `model_decode_layer` is unchanged — it already takes `n_past` and `planes` | the emitted `(K+1)`-graph transcript, consumed by `ds-steps-3` |
| **Hosted `K` is 3, not 16** | Three steps prove the recurrence: step 1 is R6's exact case, step 2 is the first that *reads* a written-back column, step 3 is the first where two written-back columns are read. A loop correct for `1 → 2 → 3` is correct for `k → k+1` by the same code path, and 16 would multiply a pure-Python fixture corpus and the smoke's runtime for **no new closure cell**. The real `N = 16` is the qualification's | `ds-steps-3` |
| Success | `model-decode-transcript.txt` holds `K + 1` graphs; `model-decode-argmax.txt` becomes `model-decode-tokens.txt`, one id per line, `K` lines — the generator's own greedy ids, which the smoke asserts against `decode.token_ids` | `ds-steps-3` asserts the two agree element for element, making "the arm decoded the tokens the reference decoded" an assertion rather than a coincidence |
| Failure | N/A — the generator is total over its own fixed inputs and reads no external file | stated, with reason |
| Malformed input | mutated fixtures | `ds-transcript-onegraph` (retained; now "fewer graphs than `N+1`"), **new** `ds-transcript-short-for-steps` (a 3-graph transcript with `STEPS` of 3 → `R6_ORACLE_MISSING` detail `step[3]`), `ds-transcript-kv-width`, `ds-transcript-perturbed`, `ds-transcript-garbage` (all retained) |
| Early exit | argv guard rejects an option-shaped operand, as today | existing |
| Cleanup | writes into `OUTDIR` the harness owns and removes | stated, with reason |

### 4.8 `scripts/run-layer-forward-smoke` (fifth block) and `scripts/run-decode-step`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | the fifth block's four case tables gain the section 4.1 cases; `normalize` gains `steps[i].compute_ns` for every `i` (2.9) | the block's own `SystemExit(1)` |
| Success | `scripts/decode-step-golden.jsonl` matches case for case at schema 2 | golden compare |
| Failure | any case's document differs, or a code differs from the table's expectation | `describe_difference` |
| Malformed input | the `NO_DOCUMENT` table | `ds-arity-*`, `ds-path-*`, `ds-arm-unknown-flag` |
| Early exit | the smoke never skips; the qualification prints one `N/A` line and exits 0 | `run-decode-step`'s `na()` |
| Cleanup | the qualification removes the pack, both instrument outputs, **and every `N`-step transcript**, on every exit path including a signal, and restores the unforced shim | `trap cleanup EXIT HUP INT TERM`, unchanged. Section 6 risk 2 records the transcript's size |
| **Shared process/connection state** | **N/A.** Each `ggml-spike` invocation is an independent process with its own backend, contexts, and plane. There is no process-global or connection-global state to restore between steps, prompts, or runs; the one process-global input is the shim build, which the trap restores | stated, with reason |
| **Concurrent independent processes** | **Unsupported and not attempted.** The loop is sequential by construction. Parallelising per-prompt work would need `spawn` over non-`Copy` captures, which is **Align Request 41** (`PROPOSED`); no workaround is built and no hypothetical surface is consumed | stated, with reason (section 8) |

## 5. Verification

| Scope | Command |
| --- | --- |
| Owner, during development | `gmake layer-forward-smoke` — the owner for R5A–R5D and R6, already in `HOSTED_CHECK_TARGETS` |
| Focused qualification | `gmake decode-step-qualification` → `scripts/run-decode-step`, opt-in, capable-only, **outside every aggregate** — unchanged from R6 |
| Coding-baseline chain | `gmake baseline-check`. **Only if the diff touches `Makefile` or a build input.** As shipped it does not: `Makefile` is byte-unchanged — no new target, no new `.PHONY` word. `scripts/build-ggml-shim` gains two forced-build arms, which are inputs to the **stub** shim and never to an ordinary build; the row is `N/A` on that basis and must be re-checked at the publication head after the merge with `main`, because R5E moved `Makefile` and the baseline artifacts |
| Publication | `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` |
| Formatting | `gmake fmt` before committing Align source; `gmake format-check` and `git diff --check` clean |

**Aggregate membership is unchanged and `make ci` is not selected.** No new target, so
`scripts/check-gate-topology`'s byte-literal `EXPECTED` does not move; the owner stays
`layer-forward-smoke`, already a member. This is not a `.align-revision` change, not an aggregate
membership or topology change, and not a change to integration behaviour.

The qualification asserts section 3.5's rule plus, at minimum: `reference.verdict == "IDENTICAL"`
(the pack is the source GGUF byte for byte, which is what makes reading the GGUF for the fingerprint
measurement equivalent to reading the pack); `plane.bytes == 29360128`;
`plane.layers == model.n_layer`; `plane.columns_written == selection.token_count + 16`;
`decode.steps_requested == 16` and `steps_completed == 16`; `len(decode.token_ids) == 16` and
`token_ids[i] == steps[i].token_id`; `steps[0].token_id == output.argmax` (the chain's root);
`steps[i].n_past == selection.token_count + i`; `decode.slot_high_water == 66` and
`graph.slot_capacity == 128`; every `steps[i].sha256` distinct from `output.sha256` and from every
other step's; `oracle_logits.verdict == "IDENTICAL"` and `byte_identical`; every
`lifetime.*_created == *_freed` with `graph_balance_failures == 0`; `abi.fp_contract_off == true`;
the embedding-fingerprint collision count over all 152,064 rows; and three consecutive runs
byte-identical, over four prompts.

Prompt-specific values — `T`, the sixteen ids, the per-step maxima, the timings — are **reported**,
not asserted as constants. They are properties of four prompts on one model, and section 5.1 is
where the run records them.

### 5.1 Result — `gmake decode-step-qualification`, 2026-08-29

Host: `aarch64-apple-darwin` (Apple M1), Homebrew ggml 0.21.0, `llama-debug` build 10566
(`bb4caa7`), `llama-eval-callback` the R2C-patched instrument at the pinned revision, generation
`r2c-v2`. Model `qwen2.5-coder-7b-instruct-q4_k_m.gguf`, `KV_WIDTH` 256, `N = 16`, CPU only, four
prompts × three runs. **Whole run 8 min 27 s of the 1800 s cap**, so the section 6 risk 1 fallback
to `N = 8` was not taken.

The qualification was run **twice**, ten minutes apart, at two heads that differ only in an
`oracle_decode` bookkeeping guard for documents with no transcript. **Every correctness value below
reproduced exactly** — the same 64 ids, the same gate G verdicts, the same oracle B byte counts, the
same three C′ identities per prompt, and the same per-step A′ maxima to the last digit. Only the
timings moved, and section 5.1's timing table is the second run's.

**The fingerprint measurement, taken before gate G was claimed** (section 3.2, and the one number
the acceptance rule depends on):

| Quantity | Measured |
| --- | --- |
| Rows of `token_embd.weight` (Q4_K, `{3584, 152064}`) | 152,064 |
| Distinct printed fingerprints (six `%12.4f` values) | **149,710** |
| Collision classes | **1** |
| Ids in that class | 2,355 |
| Of those, ids whose embedding row is **not** all zero | **0** |
| Distinct fingerprints including `sum = %f` | 149,710 — the same partition |

The single collision class is exactly the set of **all-zero rows**: the unused slots of a
151,665-token vocabulary padded to 152,064. Every row with any non-zero element has a unique
printed fingerprint, so G2 is a token-id equality on the whole used vocabulary. No step of any
prompt decoded a member of that class, which the runner checks per step. **G3 is not taken.**

**Per prompt.** `T` is the prefill length, the ids are `d_1 .. d_16` in order, and every one is
`decode.token_ids[k-1]` compared against transcript graph `k+1`'s printed `embd` row.

| Prompt | `T` | Gate G | Oracle B | Oracle C′ at `k ∈ {1, 8, 16}` |
| --- | --- | --- | --- | --- |
| `def add(a, b):` | 6 | **PASS**, 16 ids, sums also agree | `IDENTICAL`, 26,607,616 B | byte-identical, byte-identical, byte-identical |
| `class Foo:` | 3 | **PASS**, 16 ids, sums also agree | `IDENTICAL`, 21,102,592 B | byte-identical, byte-identical, byte-identical |
| `# TODO:` | 3 | **PASS**, 16 ids, sums also agree | `IDENTICAL`, 21,102,592 B | byte-identical, byte-identical, byte-identical |
| `int main(` | 3 | **PASS**, 16 ids, sums also agree | `IDENTICAL`, 21,102,592 B | byte-identical, byte-identical, byte-identical |

Oracle B's byte counts are section 2.10's formula exactly:
`Σ_{k=1..16} 2 · 28 · (T+k) · 4 · 128 · 4 = 114,688 · Σ(T+k)`, which is `114,688 × 232` at `T = 6`
and `114,688 × 184` at `T = 3`. The `T + k` rather than `T + k - 1` is the new column, verified
inside the step that wrote it.

**Oracle B is per step, and the total is what proves it.** A single mismatching column at any layer
of any step raises `R6_PLANE_MISMATCH` and stops the run, so a document reporting
`roundtrip_verdict: "IDENTICAL"` over the full `114,688 · Σ(T+k)` bytes is reporting sixteen
consecutive `IDENTICAL` comparisons, the `k`-th of which covered `T + k` columns of both tensors of
all twenty-eight layers — that is, 28 × 2 × (T+k) column comparisons at step `k`, and 12,992
(at `T = 6`) or 10,304 (at `T = 3`) column comparisons over the whole run.
`plane.first_mismatch_step` is `-1` on all four prompts, and `first_mismatch_layer`,
`first_mismatch_tensor`, and `first_mismatch_column` are `-1`, `"-"`, and `-1`.

**The sixteen ids, per prompt.**

```text
def add(a, b):   671, 26312, 264, 729, 311, 912, 1378, 5109, 198, 262, 470, 264, 488, 293, 671, 13451
class Foo:       715, 262, 707, 1304, 2327, 3804, 721, 11, 856, 982, 286, 656, 1993, 284, 856, 271
# TODO:          2691, 1159, 12239, 198, 474, 18617, 438, 7744, 198, 1499, 17987, 3192, 23672, 1159, 5426, 4452
int main(        526, 11844, 11, 1161, 9, 10213, 1294, 873, 341, 262, 442, 4615, 2038, 1588, 198, 262
```

`d_1` reproduces R6 section 5.1's recorded 671/715/2691/526 exactly, which is the chain's byte-exact
root and the one place G1 is asserted rather than inherited.

**Oracle A′, the per-step curve. Characterization at steps 2..16 by section 3.4, and the measurement
is what that section predicted.**

| Prompt | Step 1 (gated) | Steps 2..16 | Structural, every step |
| --- | --- | --- | --- |
| `def add(a, b):` | `FAIL` at **2391**/1e-4 on `ffn_inp-27`; **admitted** — inside the 5000 bound and C′ at `k=1` byte-identical | `FAIL` at every step; max abs 1295–**5878**/1e-4 (step 9), max sum 2.5 × 10^8 – 3.8 × 10^9 millionths | complete |
| `class Foo:` | `PASS` at 0 | `PASS` at 0 at every step; max sum 0–1 millionths | complete |
| `# TODO:` | `PASS` at 0 | `PASS` at 0 at every step | complete |
| `int main(` | `PASS` at 0 | `PASS` at 0 at every step | complete |

**Three of four prompts agree with llama.cpp to the last printed digit at every one of sixteen
steps.** The divergence is confined to the one prompt with `T = 6`, which is exactly the shape
section 3.4 attributes it to: llama.cpp's own multi-column prefill takes a different `MUL_MAT`
accumulation path from its own single-column decode, and the wider the prefill the more the two
paths differ. The `T = 3` prompts do not trip that selection at all. **Step 9 of the first prompt
reaches 5878/1e-4, above the 5000 admission bound** — and it is not an acceptance failure, because
the bound applies at step 1 only, where the measurement is 2391 and C′ is byte-identical. Had A′
been gated numerically at every step, this run would have failed for a property of the reference
implementation, which is the outcome the demotion exists to prevent and the reason it was taken
before the run rather than after it.

Every structural assertion of section 3.4's table held at all 64 compared steps: the graph index is
`k + 1`, `nodes_matched == nodes_expected` (5,058 elements per step over 28 layers plus the head),
`layers_matched == 28`, `elements_compared > 0`, `instrument_kv_width == 256`, and
`tolerance_ten_thousandths == 1`.

**Everything else the qualification asserted, on all four prompts:** `oracle_logits.verdict`
`IDENTICAL` with `byte_identical` (G1's evidence); `reference.verdict` `IDENTICAL`;
`plane.bytes` 29,360,128; `plane.layers` 28; `plane.columns_written` `T + 16`;
`decode.steps_requested` and `steps_completed` 16; `token_ids[i] == steps[i].token_id`;
`steps[0].token_id == output.argmax`; `steps[i].n_past == T + i` and
`plane_column_written == T + i`; `steps[i].argmax == steps[i+1].token_id` at every `i`; sixteen
distinct step digests, none equal to the prefill's; `decode.slot_high_water` 66 against a capacity
of 128; `abi.fp_contract_off`; every `lifetime.*_created == *_freed` with
`graph_balance_failures == 0`; and three consecutive runs byte-identical after `normalize`.

**Timings, reported and not claimed** (run 1 of three, per prompt):

| Prompt | Decode compute, 16 steps | Per step, min–max | Plane readback / upload | Elapsed | Pack bytes read |
| --- | --- | --- | --- | --- | --- |
| `def add(a, b):` | 2.073 s | 110.9–151.7 ms | 1.28 ms / 64.4 ms | 15.64 s | 74,299,583,904 |
| `class Foo:` | 2.450 s | 146.6–161.4 ms | 1.77 ms / 58.4 ms | 31.40 s | 74,299,577,856 |
| `# TODO:` | 2.702 s | 157.7–187.8 ms | 1.15 ms / 65.1 ms | 28.67 s | 74,299,577,856 |
| `int main(` | 3.213 s | 164.8–247.7 ms | 0.90 ms / 75.1 ms | 19.19 s | 74,299,577,856 |

**The elapsed column is dominated by `pread`, not by compute:** sixteen steps compute for 2.1–3.2 s
and the run takes 15.6–31.4 s, because each step refills the weight window over the whole 4.7 GB
pack. That is section 6 risk 1, measured. Both the compute and the elapsed columns carry host
contention — this run overlapped other work at 340 % CPU, and the earlier run of the same head
produced 1.8–2.2 s of compute and 15.7–28.1 s elapsed for the same four prompts — so they are
reported as a range on one host and **no per-token or per-second figure is derived from them**. The
plane's own two crossings are the small terms they were designed to be: readback under 2 ms and
upload under 76 ms across sixteen steps of twenty-eight layers.

### 5.2 Result — the hosted owner, `gmake layer-forward-smoke`

All five blocks pass. The fifth block runs **52 documented cases** reaching **24 error codes**
(23 of R6's plus the new `R6_STEPS`) and 10 no-document cases, against a two-layer synthetic model,
no ggml, no llama.cpp, and no GGUF. The whole owner takes **34.3 s** on this host, of which the
decode-step block is **7.1 s** — 62 cases and eight forced-build shim recompiles. The owner stays a
seconds-scale hosted check, which is what admitted it to `HOSTED_CHECK_TARGETS` in the first place;
the hosted `K = 3` of section 4.7 is the reason it stays there.

- `ds-engine-ok` at `N = 1` (absent `STEPS`): `columns_written` 4 at `T = 3`, oracle B `IDENTICAL`
  over 256 B, `decode.node_count` 78, `graph_count` 4.
- `ds-steps-3` at `N = 3`: `columns_written` 6, oracle B `IDENTICAL` over **960 B**
  (`Σ_{k=1..3} 2·2·(3+k)·1·4·4`), `decode.token_ids` equal to `model-decode-tokens.txt` element for
  element, `steps[i].n_past == 3 + i`, `plane_column_written == 3 + i`, three distinct digests, and
  oracle A′ `PASS` at `max_abs_diff` **0** against transcript graphs **2, 3, and 4** with
  `nodes_matched == nodes_expected` (37 per step, 111 total) and `layers_matched == 2` at each.
- `ds-force-compute-step2`: `R5_COMPUTE` with detail `step[2]layer[0]status[2]`,
  `steps_completed` 1, one `steps[]` row, one id, `columns_written` 4, and a round-trip verdict that
  is **not** `IDENTICAL`.
- `ds-force-writeback-offset`: `R6_PLANE_MISMATCH` with detail `step[1]layer[0]tensor[k]col[3]` and
  `plane.first_mismatch_step` 1 — column **3** is `T`, which is the column that step wrote, and is
  the evidence that oracle B compares the new column and not only the past ones.
- `ds-transcript-short-for-steps`: `R6_ORACLE_MISSING` with detail beginning `step[3]` after two
  completed steps.
- The `STEPS` refusals, with their exact published details:

  | Case | `STEPS` | Code | Detail |
  | --- | --- | --- | --- |
  | `ds-steps-empty` | `""` | `R6_STEPS` | `steps[]` |
  | `ds-steps-zero` | `0` | `R6_STEPS` | `steps[0]` |
  | `ds-steps-negative` | `-1` | `R6_STEPS` | `steps[-1]` |
  | `ds-steps-trailing` | `3,` | `R6_STEPS` | `steps[3,]` |
  | `ds-steps-over-max` | `65` | `R6_STEPS` | `steps[65]` |
  | `ds-steps-zero-and-narrow` | `0`, width `2` | `R6_STEPS` | `steps[0]` — the precedence, asserted |
  | `ds-kv-width-narrow-for-steps` | `3`, width `5`, `T=3` | `R6_KV_WIDTH` | `kv_width[5]` — the plane bound, not `R6_STEPS` |
  | `ds-tokens-33` | absent | `R6_TOKENS` | `token[32]` — the cap at 32, refusing the 33rd |
- The R6 cases are retained and still pass: `ds-force-plane-stage-offset` still names
  `layer[0]tensor[k]col[0]`, and `ds-force-decode-position` / `ds-force-mask-offset` are still
  oracle-A′ `FAIL`s on an otherwise `ok` run with oracle B unmoved.

**Five ledger-named mutants were injected at this head and all five die.**

| Mutant | Diagnosis |
| --- | --- |
| Write-back column off by one (`first_column = n_past + 1`) | `R6_PLANE_MISMATCH step[1]layer[0]tensor[k]col[3]` on every engine case |
| Write-back skipped entirely | the same, on every engine case |
| Plane not grown (`n_past` frozen at `T`) | `columns_written` 4 instead of 6, oracle B over 768 B instead of 960, `n_past` 3..3 instead of 3..5, and per-step A′ `FAIL` at 1520 and 2702/1e-4 |
| Transcript graph skip off by one (step `k` vs graph `k+2`) | `R6_ORACLE_MISSING step[3]layer[-1]node[embd]` plus A′ `FAIL` at 4401/1e-4 on `q_rope` at step 1 |
| Gate G compared against graph `k` or `k+2` | printed rows disagree at step 1 on every prompt (checked offline against the real transcript and the measured fingerprints) |
| Oracle C′ step index off by one | the `--model-forward` digest differs from `steps[k-1].sha256` at every checkpoint |

### 5.3 The goldens that moved — predicted in advance, and reconciled

Named before the run so that an unpredicted movement would be a finding rather than noise. **Every
prediction held and nothing else moved.**

| File | Predicted | Measured |
| --- | --- | --- |
| `scripts/decode-step-golden.jsonl` | every row's document, schema 1 → 2, plus the new cases | **39 rows changed, 13 added, 1 removed** (`ds-tokens-nine` → `ds-tokens-33`); 40 rows become 52 |
| `scripts/layer-forward-golden.jsonl` | `lf-tokens-nine` → `lf-tokens-33`, one row | **exactly that**; 0 other rows changed |
| `scripts/model-forward-golden.jsonl` | `mf-tokens-nine` → `mf-tokens-33`, one row | **exactly that**; 0 other rows changed |
| `scripts/gpu-forward-golden.jsonl` | byte-unchanged | **byte-unchanged** |
| `scripts/moe-layer-forward-golden.jsonl` | byte-unchanged | **byte-unchanged** |
| `scripts/ggml-spike-golden.jsonl` | not predicted to move | **byte-unchanged** |

The thirteen added decode-step rows are `ds-tokens-33`, `ds-steps-empty`, `ds-steps-zero`,
`ds-steps-negative`, `ds-steps-trailing`, `ds-steps-over-max`, `ds-steps-zero-and-narrow`,
`ds-kv-width-narrow-for-steps`, `ds-logits-dash`, `ds-steps-3`, `ds-transcript-short-for-steps`,
`ds-force-compute-step2`, and `ds-force-writeback-offset`.

`lf-tokens-eight-no-transcript` and `mf-tokens-eight-no-transcript` are **byte-unchanged**: eight
tokens are still admitted without a transcript at a cap of 32. `lf-tokens-seven-transcript` and
`mf-tokens-seven-transcript` are **byte-unchanged**: `R5_ORACLE_TRUNCATED` fires on
`tokens.count > TRUNCATION_PRINTED`, which is 6 and does not move. `moe-tokens-seven` is
**byte-unchanged**: `src/layer_olmoe.align`'s own cap stays at 6.

**The arm rename cost zero golden bytes, as section 2.1 predicted.** `ds-arity-11` becomes
`ds-arity-12` and `ds-arm-unknown-flag` moves from `--decode-steps` to `--decode-stepped`; both are
`NO_DOCUMENT` cases and neither carries a golden row.

### 5.4 Result — the scaling measurement (section 2.10)

One prompt (`def add(a, b):`, `T = 6`), `KV_WIDTH` 256, no transcript, no logits blob.
**Characterization. No TTFT and no tokens-per-second claim is made from it.**

| `N` | Elapsed | Decode compute | Pack bytes read | Plane columns |
| --- | --- | --- | --- | --- |
| 1 | 5.313 s | 0.183 s | 8,741,169,024 | 7 |
| 4 | 7.367 s | 0.783 s | 21,852,852,000 | 10 |
| 16 | 18.235 s | 3.049 s | 74,299,583,904 | 22 |

**Pack bytes read is exactly linear in `N`** and it is the invariant of the two runs: the three
byte counts are identical in both, and `(74,299,583,904 − 8,741,169,024) / 15 = 4,370,560,992` — one
4.37 GB pass over a 4.68 GB pack per additional step. Elapsed follows the bytes, not the compute:
compute is **3.5 %, 10.6 %, and 16.7 %** of elapsed at the three points, so more than four fifths of
a sixteen-step run is re-reading weights the previous step already read. Fitting the three points
gives roughly 4.37 GB and 0.86 s of wall time per additional step against a 4.5 s fixed cost; the
earlier run of the same head gave 0.73 s per step on the same 4.37 GB, which is the spread a
contended host produces and is why only the byte count is stated as a property of the design.

**This is the first concrete evidence for resident weights**, which `docs/specs/align-llm.md`
already designs and section 7 defers: a decode loop that held the layer weights across steps would
remove the dominant term, and this measurement is what says how large that term is. It is not a
defect of this capability and it is not hidden — it is the direct consequence of the streaming
window, which is what makes a 7 B model run in a bounded working set at all.

## 6. Risks

1. **The loop's cost is `O(N × model bytes)` of pack reads, and that is the dominant term.** Each
   step calls `decode_embed_members` then `fill_members` and every layer graph refills the weight
   window, so `N = 16` reads roughly sixteen full passes over the 4.7 GB pack. From R6 section 5.1's
   figures a single decode pass computes in 114–157 ms; the pread is what will dominate, and at a
   plausible 2 GB/s a run is tens of seconds. **Estimated qualification cost:** 4 prompts × 3 runs ×
   ~40 s ≈ **480 s**, plus 12 oracle-C′ `--model-forward` passes ≈ 60 s, plus 4 instrument runs at
   `-n 16` ≈ 68 s (extrapolated from the probe's measured 5.06 s at `-n 4`), plus packing ≈ 60 s —
   about **670 s against the 1800 s cap**, with pread bandwidth the dominant uncertainty.
   *Mitigation:* `DECODE_STEPS` is one constant at the top of `scripts/run-decode-step` with a
   documented fallback to 8 if the measured wall time exceeds 900 s, and the fallback halves every
   term. *This is not a defect and it is not hidden:* it is the direct consequence of the streaming
   window, and the scaling row of section 2.10 exists to measure it. **It is also the first concrete
   evidence for resident weights**, which `docs/specs/align-llm.md` already designs and section 7
   defers.
2. **Transcript size.** At `-n 16`, extrapolating the probe's measured 28,511-line prefill and
   14,826-line decode graphs, one transcript is ≈ 265,700 lines and ≈ 16 MB; four prompts are
   ≈ 64 MB under the scratch root. *Mitigation:* the existing `trap cleanup` removes the whole work
   directory on every exit path including a signal, and `run-decode-step` already refuses to start
   unless the scratch root has the pack's size plus 1 GiB free. The free-space check is **raised to
   the pack plus 2 GiB** to cover the transcripts explicitly rather than by luck.
3. **`N` transcript rescans.** `layer_forward.scan_transcript_after(path, oracle, k)` re-reads the
   whole file per step, so oracle A′ costs `O(N × file)` — at `N = 16` and 16 MB, ≈ 256 MB of
   parsing per run. *Mitigation:* accepted and measured (it is reported in `timings`), because the
   alternative — one scan retaining `N` graphs' oracle ranges — holds `N × 5058` element ranges in
   memory and is a new data structure for a cost that section 1 estimates at seconds. A resumable
   single-pass scan is deferred (section 7) with this measurement as its trigger.
4. **A prompt reaches EOS before step `N`.** The R2C patch breaks the decode loop at
   `llama_vocab_is_eog`, so llama.cpp would emit fewer than `N + 1` graphs while this arm emits `N`
   steps. *Mitigation, and it is a refusal rather than a guess:* the runner asserts the transcript
   holds exactly `N + 1` graphs and refuses the prompt by name if not, citing EOS. Section 2.12
   records why implementing EOS here is the wrong answer. The probe reached four steps on the first
   prompt without EOS; the residual risk is that a prompt reaches it between step 5 and 16, and the
   response is to change the prompt, not the gate.
5. **A per-step timing array makes the golden non-deterministic.** A named prior failure class.
   *Mitigation:* `normalize` zeroes `steps[i].compute_ns` for every `i` and both plane timings
   (2.9), and the fifth block's three-consecutive-runs check would fail loudly if one were missed.
   No path in the document carries a filesystem path, so the "temp-path golden" class does not
   apply — verified against schema 2's field list, which contains no path-valued field.
6. **A vacuous per-step assertion.** A named prior failure class, and the reason section 3.4 spells
   out what A′ asserts at steps 2..N instead of leaving "characterization" to mean "unchecked".
   *Mitigation:* every per-step structural assertion in section 3.4's table fails on a real defect —
   a mis-aligned skip, a truncated transcript, a dropped layer, an empty comparison — and
   `elements_compared > 0` per step is the specific guard against a comparison that passes because
   it compared nothing. `R6_ORACLE_MISSING` is already reachable and gains a per-step case.
7. **Gate G rests on a vocabulary property that had not been measured when this was written.**
   Section 3.2's fingerprint injectivity is the load-bearing assumption. *Discharged:* it was
   measured before the gate was claimed and section 5.1 records it — 149,710 distinct fingerprints,
   one collision class, and that class is exactly the 2,355 all-zero (unused) vocabulary rows. The
   runner checks membership **per step**, so the risk that remains is not "the fingerprint might
   collide" but "a run might decode an unused vocabulary slot", which the runner refuses by name.
   G3 is not taken.
8. **Saturating an `i64` accumulator.** A named prior failure class. *Mitigation:* section 2.10
   computes the worst case for every accumulated quantity at `N = 64`, `KV_WIDTH = 4096`; the
   largest is ≈ 3.0 × 10^10.
9. **Instrument provenance and sampler pinning.** R6 risks 1 and 2, unchanged and still live.
   *Mitigation:* unchanged — the pinned instrument, `--temp 0 -s 0` contractual, the reference
   blob's `sha256` asserted before use.

## 7. Deferred

- **The exact-id R2C patch (G3).** One logged line per sampled token would make gate G a literal
  integer comparison. Costed in section 3.2 and **not taken**: section 5.1's measured collision
  class covers only unused all-zero vocabulary rows, which the runner refuses per step, so G1 plus
  a measured G2 carry the claim without a new patch digest and a cache-generation bump.
- **Resident weights across decode steps.** Risk 1 measures the cost this would remove. It is the
  residency work `docs/specs/align-llm.md` designs and R6 section 7 already defers; this capability
  supplies its first real measurement and deliberately does not build it.
- **A resumable single-pass transcript scan.** Risk 3's `O(N × file)` cost is its trigger.
- **Oracle C′ at every step**, rather than three checkpoints. Costed in section 3.4.
- **EOS, a sampler beyond greedy, and stop strings.** Section 2.12. They belong to the capability
  that produces *text*, which needs a detokenizer, which needs Align Request 22.
- **The `llama-debug` text corroboration leg as an assertion.** Section 3.3; unchanged from R6
  section 10.5 and blocked on the same missing detokenizer.
- **A quantized KV plane, the Metal decode arm, OLMoE/routed decode, a growing `KV_WIDTH`, batch
  above one.** All unchanged non-goals from R6 section 7.
- **Any TTFT or tokens-per-second claim.** R6-STEP-N measures correctness. A decode-time claim needs
  its own capability, its own baseline, and its own benchmark.
- **Deferred closure cells, named rather than omitted.** `R6_PLANE_WRITE` (4.2) has no forced build:
  it guards a `slot_get` that fills fewer bytes than the node declares, which the arm's own sizing
  makes unreachable, and R6 section 10.5 defers the identical cell for the prefill path for the
  identical reason. `R6_PLANE_UNAVAILABLE` is deferred on R6's terms, unchanged. A step failing at
  a chosen layer index `k > 0` **within** a step is still not exercised: the forced builds fail at a
  graph boundary, and a per-layer discriminator in the shim for one cell is deferred as R6 deferred
  it. What *is* newly exercised, and was not before, is a failure at a chosen **step** index —
  `ds-force-compute-step2` — which is the axis this capability adds.

## 8. Align capability requests

Classified per `CLAUDE.md`. **None blocks this capability, and no new request is proposed.**

| Gap | Classification | Status |
| --- | --- | --- |
| Indexing arrays of Move element types (`array<string>`) | Genuine Align gap, already recorded | **Request 22, `PROPOSED`, stays non-blocking.** Two distinct contacts, both recorded in that request: the **tokenizer**, which section 1.3 records this capability gates around by comparing ids rather than text, and section 3.3 records stays hand-measured; and `model_forward.StepColumns`, whose three string columns take the stream-plus-column shape (11.3, deviation 1) rather than `array<str>`. **No hypothetical surface is consumed and no new request is proposed**; the avoidance is cited as a fourth client of the existing one |
| A cross-module call with a `borrow mut` argument refuses every shorter-lived operand | Genuine Align gap, already recorded | **Request 49, `PROPOSED`.** This capability is one more client: the per-step data travels as column sets (4.4) rather than as a sixth `borrow mut` out-parameter, for exactly the reason that request describes. Cited as continuing evidence; no new request |
| Non-`Copy` capture in `spawn` closures (`task_group`) | Genuine Align gap, already recorded | **Request 41, `PROPOSED`.** Relevant because the obvious cost mitigation for risk 1 — running four prompts concurrently — needs it. **No workaround is built** and the loop stays sequential (4.8). Cited as evidence that the gap has a second client; no new request |
| `raw` not a struct field; `buffer(n)` alignment; by-value structs across the FFI; `alignc check` parity; release of rebound `buffer` allocations | Genuine Align gaps, already recorded | Existing requests, unchanged. The plane inherits R6's workarounds |

**Numbering, reconciled 2026-08-29.** R5E merged as PR #143 (`main` `5ccc2aa`), so requests **47 and
48 are real on `main`** and roadmap item 26 is R5E. R6-DECODE-KV-STEP1 holds request 49 and roadmap
item **27**, so this capability is roadmap item **28** and the next free request number is **50**.
This capability proposes **no new request**, so 50 stays free and the hazard R6 section 8 records
does not apply. R5E also moved `Makefile`, `.gitattributes`, the baseline artifacts, and
`docs/align-development.md`; none of those is a `MAX_PREFILL_TOKENS` consumer and none conflicts
with this capability's diff, but the merge is still taken as `git merge origin/main` — never a
rebase — after R6 lands, and re-checked then.

## 9. Reconciliation

**Applied.** All three drafts below were written into their owning documents at implementation time
and are reproduced here as the record of what was applied, not as pending work. Numbering assumes
R6-DECODE-KV-STEP1 keeps roadmap item **27**, which it holds on `agent/r6-decode-kv-step1` at
`1671810`; `main` carried roadmap items to 24 when this branch was cut, `agent/r3-decode-residency`
claims 25, and `agent/r5e-moe-model-prefill` claims 26. **This must be re-checked when R6 merges:**
this branch takes `git merge origin/main` — never a rebase, so R6's recorded commits stay reachable
— and if `main` has moved the numbering, item 28 and every cross-reference to it move with it.

### 9.1 `docs/specs/roadmap.md` — item 28, applied

> 28. **R6-STEP-N — an N-step greedy decode loop over the Align-owned KV plane, gated on the token
>     ids llama.cpp produces at `--temp 0 -s 0`.** Design in `docs/specs/r6-step-n.md`. `--decode-step`
>     gains a `STEPS` operand and its document goes to schema 2; the plane is grown in place one
>     column per step and every written column is byte-verified inside the step that wrote it. The
>     loop needs **no new ggml op, FFI symbol, node row, or slot** — R6's decode row table is already
>     parameterised by `n_past`. Acceptance: the `N` decoded ids equal llama.cpp's (byte-exact for
>     `d_1` against `llama-debug`, and per step against the transcript's `embd` fingerprint over a
>     vocabulary whose collision count is measured to be zero); the plane round trip is
>     `IDENTICAL` at every step; and the step-`k` logits are byte-identical to this arm's own
>     single-shot `T+k` prefill at `k ∈ {1, ⌈N/2⌉, N}`. Four prompts × three runs at `N = 16`,
>     `KV_WIDTH` 256, dense Qwen2.5-Coder-7B Q4_K_M, CPU. Owner `gmake layer-forward-smoke`; focused
>     `gmake decode-step-qualification`. **No TTFT or throughput claim** — but the run measures the
>     loop's `O(N × model bytes)` pack-read cost at `N ∈ {1, 4, 16}`, which is the first concrete
>     evidence for the resident-weight work R3/R5 designs.

### 9.2 `HANDOFF.md` — active block, applied

Applied in the shape below, with the implementation and verification state of section 5.1 substituted for "design only".

> ## Active: R6-STEP-N (2026-08-29)
>
> Branch `agent/r6-step-n`, stacked on `agent/r6-decode-kv-step1` at `1671810`, which is in
> publication. **Implemented and owner-tested; nothing committed yet.**
>
> **Capability.** An N-step greedy decode loop over the R6 KV plane, dense Qwen2.5-Coder-7B Q4_K_M,
> CPU, gated on token ids. `docs/specs/r6-step-n.md` is the authoritative ledger. The design gate is
> triggered — a changed public CLI arm and a changed exchanged document schema — and the design is
> complete before implementation begins.
>
> **Probe result (recorded, section 3.1).** The patched `llama-eval-callback -n N --temp 0 -s 0`
> emits exactly `N + 1` graphs (measured at `-n 4`: five graphs, 5.06 s, 5.25 MB) and its KV width
> is 256 in every graph. **It does not print the sampled token**: `inp_tokens` is a leaf whose value
> never appears, `result_output` prints six of 152,064 values so its argmax is not derivable, and
> stderr lists only the prompt's ids. The token is recovered from each graph's
> `embd = GET_ROWS(token_embd.weight, [d_k])`, whose injectivity over the vocabulary is measured as
> part of the qualification.
>
> **Next actions, in order.**
> 1. Land R6-DECODE-KV-STEP1; **merge** `origin/main` into this branch — never rebase.
> 2. Implement in one consumer-complete capability: `STEPS` operand and its two refusals, the
>    write-back and the widened oracle B bound, the per-step iteration of the node table / mask /
>    position, schema 2 and its `normalize` additions, the fixture's `K = 3` loop, the new smoke
>    cases, and the runner's gate G.
> 3. Measure the fingerprint collision count **before** claiming gate G; if it is not 0, take the
>    G3 patch (section 3.2) instead.
> 4. `gmake fmt`, `gmake layer-forward-smoke`, then `gmake decode-step-qualification`.
> 5. Record sections 5.1–5.4; apply the section 9 reconciliation drafts.
>
> **Blockers.** None. R6 publication is a sequencing dependency, not a blocker: the design is
> complete and the implementation merges.
>
> **Constraints.** No new Align request is proposed. Request 22 (tokenizer) stays non-blocking and
> gains no client — the gate is on ids, not text. Requests 41 and 49 gain a cited client each and no
> workaround is built for either.

### 9.3 `docs/align-development.md` — additions, applied

Under **The `--decode-step` arm**, replace the operand list and add the loop paragraphs:

> `--decode-step` is selected by its exact first operand and is five, six, seven, nine, ten, or
> **eleven** operands. **Eight is `R6_ARITY`**, inherited verbatim from `--model-forward`.
>
> ```text
> ./ggml-spike --decode-step PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin STEPS
> ./ggml-spike --decode-step PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH -          STEPS
> ```
>
> `STEPS` is the number of greedy decode steps `N`, `1 <= N <= MAX_DECODE_STEPS` (64), and
> `T + N <= KV_WIDTH`. **Absent means 1**, which is the arm's only default and exists so that every
> pre-schema-2 invocation keeps its meaning; `decode.steps_requested` is published in every document
> so the count is never implicit. `LOGITS` accepts `-` for "absent", the same convention `TRANSCRIPT`
> has used since R5B, so that `STEPS` is reachable without a logits blob.
>
> The document is `R6_DECODE_STEP` at **schema 2**: `decode` carries the loop
> (`steps_requested`, `steps_completed`, `token_ids`, and the summed/maximised totals) and a new
> `steps[]` array carries one object per completed step. A failure at step `k` publishes
> `steps_completed = k - 1` and the ids decoded so far, with the raising code's detail prefixed
> `step[<k>]`.
>
> `MAX_PREFILL_TOKENS` moves **8 → 32** so that the self-reference oracle can run
> `--model-forward` at `TOKENS,d_1..d_16`. The cap's reason is unchanged and still enforced:
> `--layer-forward` and `--model-forward` refuse more than six tokens **with a transcript** with
> `R5_ORACLE_TRUNCATED`, because `llama-eval-callback` prints every row only while `ne1 <= 6`. The
> range is open for arithmetic and closed for comparison.
>
> `scripts/run-decode-step` runs `N = 16` (`DECODE_STEPS`, one constant at the top of the script,
> with a documented fallback to 8) and passes `-n 16 --temp 0 -s 0` to the instrument. The
> instrument emits `N + 1` graphs; the runner refuses a prompt whose transcript holds any other
> number, because a short transcript means llama.cpp stopped at EOS and the two runs would differ in
> length rather than in arithmetic.

## 10. Author consistency pass

One pass, ledger against prose, performed before this document was finished. What it found and what
was changed:

1. **The brief's fallback oracle does not exist.** It said "if the transcript does not expose the
   sampled token, derive from `result_output` argmax per graph". Section 3.1 measured that
   `result_output` prints six of 152,064 values, so that route fails too. The `embd` route replaced
   it and section 3.2 was rewritten around a *measured* injectivity claim rather than an assumed
   one, because an unmeasured fingerprint comparison presented as an id gate is precisely the
   vacuous assertion this design is required to avoid.
2. **Oracle C′ was impossible as first drafted.** It runs `--model-forward` at `T + k` tokens, and
   `MAX_PREFILL_TOKENS` is 8 while `T + N` is 22. Section 2.5 was added — the constant moves to 32 —
   and section 5.3's golden prediction was extended with the three cap rows. Without this pass the
   design would have shipped an acceptance oracle its own arm refuses.
3. **The R6 admission rule does not survive `N` steps.** R6's conjunction ("A `FAIL` admitted inside
   0.5 *and* with oracle C byte-identical on that prompt") assumes oracle C runs wherever A does.
   C′ runs at three checkpoints. Rather than weaken the conjunction to "the nearest checkpoint",
   A′ was demoted to characterization at steps 2..N with an explicit **structural** gate at every
   step (3.4), and R6's rule was kept verbatim at step 1 where its precondition actually holds.
4. **"Grown in place" contradicted R6's "never grown".** Section 2.4 now distinguishes growth in the
   *allocator's* sense (which does not happen — the buffer is `KV_WIDTH` columns from the start)
   from writing further into it (which does), so the two ledgers do not disagree about one word.
5. **R6's aliasing invariant is stated as an exclusion this capability violates.** R6 section 2.2
   says the plane is "never both a `slot_get` destination and a `slot_set` source in one call" and
   names that as why step 2 was out of scope. Section 2.4 replaces it with **disjointness plus
   ordering** and says so explicitly, rather than quietly doing the thing the previous ledger
   forbade.
6. **`plane.columns_written` and the write-back's verification were inconsistent.** An earlier draft
   wrote back after every step and verified `n_past` columns, leaving the final column written and
   unverified. Moving the write-back **before** the verification and widening the bound to
   `n_past + 1` fixed it, gave a `columns_written` of `T + N` with no special case, and closed a gap
   R6 shipped. Sections 2.4, 3.4, and 4.2 agree on it and `ds-force-writeback-offset` is the case
   that proves the new column is compared.
7. **Two codes for one condition.** An earlier draft raised `R6_STEPS` for `T + N > KV_WIDTH`.
   Section 2.3 now raises `R6_KV_WIDTH`, because "the plane is too narrow" is a sentence R6 already
   owns, and states the precedence between the two codes with a case that asserts it.
8. **The third design-gate trigger was claimed and is not true.** Section 1.2 originally asserted a
   coordinated invariant across three or more modules. The *invariant* is R6's and is unchanged;
   only its consumers move. The claim was withdrawn and the closure matrix is kept anyway, with the
   reason stated.
9. **Deferred cells must be marked, not omitted.** `R6_PLANE_WRITE` at 4.2 has no forced build and
   is marked deferred with R6's own reason, rather than given a case name that does not exist.

## 11. Ledger-to-diff mapping, and the deviations

One pass over the final diff, mapping every applicable ledger and closure cell to the code and the
passing evidence, in `r6-decode-kv-step1.md` section 11's shape. A cell with no counterpart in the
diff is named and given its reason rather than omitted.

### 11.1 Ledger rows to the diff

| Ledger row | Where it lives | Evidence |
| --- | --- | --- |
| 2.2 arity {5,6,7,9,10,11}, 8 still `R6_ARITY` | `decode_step.run` | `ds-arity-3`, `ds-arity-8`, `ds-arity-12` (`NO_DOCUMENT`, no golden bytes) |
| 2.2 `LOGITS` accepts `-` | `decode_step.run` | `ds-logits-dash`; `ds-path-logits-empty` unchanged |
| 2.2 `STEPS` absent means 1 | `decode_step.run` (`steps_text := if count == 11 { args[10] } else { "1" }`) | `ds-engine-ok` and every nine-operand golden row publish `steps_requested: 1` |
| 2.2 `steps_requested` in **every** document | `execute`'s probe before validation, plus `publish` | `ds-tokens-33`, `ds-steps-*`, and every stub row carry the field |
| 2.3 `R6_STEPS` parse and range, `MAX_DECODE_STEPS` 64 | `stage_inputs` step 3b; `layer_qwen2.MAX_DECODE_STEPS` | `ds-steps-empty`, `ds-steps-zero`, `ds-steps-negative`, `ds-steps-trailing`, `ds-steps-over-max` |
| 2.3 plane bound raises `R6_KV_WIDTH`, not `R6_STEPS` | `stage_inputs` step 6 (`width < parsed.count + steps`) | `ds-kv-width-narrow-for-steps`; `ds-kv-width-equal-t` unchanged |
| 2.3 precedence: `R6_STEPS` before `R6_KV_WIDTH` | step 3b precedes step 6 in one function | `ds-steps-zero-and-narrow` |
| 2.4 write-back source is rows 12/10 at `t = 1` | `run_step_graph`'s `write_back` arm calling `capture_plane(.., 1, n_past, ..)` | `ds-force-writeback-offset` names `col[3]`, which is `T` |
| 2.4 ordering invariant: upload, compute, write, verify | `run_step_graph` statement order | oracle B at every step; `ds-force-plane-stage-offset` still names `col[0]` |
| 2.4 `columns_written == T + N` | `decode_loop` after a **completed** step | `ds-steps-3` (6 columns at `T=3, N=3`); qualification asserts `T + 16` |
| 2.4 verification covers the new column | `verify_plane` compares `n_past + 1` columns | `ds-force-writeback-offset` |
| 2.5 `MAX_PREFILL_TOKENS` 8 -> 32 | `layer_qwen2.MAX_PREFILL_TOKENS` | `ds-tokens-33`, `lf-tokens-33`, `mf-tokens-33` |
| 2.5 `R5_ORACLE_TRUNCATED` byte-unchanged | not edited | `lf-/mf-tokens-seven-transcript` and `-eight-no-transcript` golden rows byte-unchanged |
| 2.5 `layer_olmoe.align:67` unchanged at 6 | not edited | `moe-tokens-seven` golden row byte-unchanged |
| 2.6 node table, mask, position per step; ids image not | `decode_loop` (`step_nodes`, `mask_all` slice, `pos_all` slice); `decode_ids_image` built once | `ds-steps-3`'s per-step `n_past` and `instrument_graph`; mutant M3 (frozen `n_past`) dies |
| 2.6 `node_window` sized for the widest step | `execute`'s `kv_span` is `width * n_head_kv * head_dim * 4`, and `T + N <= width` | `ds-steps-3` at `T + N = 6` of width 8 |
| 2.7 step 3b inserted; step 6 widened | `stage_inputs` | as 2.3 |
| 2.7 `step[<k>]` detail prefix | `prefix_step`, one call site per exit | `ds-force-compute-step2` (`step[2]...`), `ds-transcript-short-for-steps` (`step[3]...`), `ds-force-writeback-offset` (`step[1]...`) |
| 2.8 partial step publishes no row | `decode_loop` pushes columns only after a completed step | `ds-force-compute-step2`: `steps_completed 1`, one row, one id, `columns_written 4` |
| 2.8 never `IDENTICAL` on an error document | `decode_loop`'s promotion guarded by `o.code.len() == 0` | `ds-force-compute-step2` asserts it |
| 2.9 schema 2, `decode` loop-level, `steps[]`, `token_ids` | `SCHEMA_VERSION`, `render_decode`, `render_steps` | every `decode-step-golden.jsonl` row; `record()` asserts `schema_version == 2` |
| 2.9 `token_ids[i] == steps[i].token_id` | `render_decode` reads `StepColumns.token_id` | asserted in the smoke and in the qualification |
| 2.9 `normalize` zeroes `steps[i].compute_ns` | both runners' `normalize` | three-consecutive-runs check in both |
| 2.9 one shape at `N = 1` and `N = 64` | no conditional field in `render_steps`/`render_decode` | `ds-engine-ok` (N=1) and `ds-steps-3` (N=3) have the same key set |
| 2.10 metrics reported, no TTFT claim | `scripts/run-decode-step`'s scaling block and per-step print | section 5.4 |
| 2.12 no EOS; the runner refuses a short transcript | `scripts/run-decode-step`'s graph count | rule 7; not triggered on these four prompts |
| 3.2 gate G, measured injectivity | `scripts/decode_step_fingerprint.py`, `gate_g` in the runner | section 5.1 |
| 3.4 oracle B cumulative and inclusive | `verify_plane` | `roundtrip_bytes_compared` matches `Σ 2·n_layer·(T+k)·n_head_kv·head_dim·4` in both runners |
| 3.4 oracle C' at `k ∈ {1, ⌈N/2⌉, N}` | the runner's `checkpoints` | section 5.1 |
| 3.4 A' structural at every step | `steps[i].oracle.*`, asserted in both runners | mutants M4a/M4b die |
| 4.5 `ggml_ffi.align` / `ggml_shim.c` byte-unchanged | not edited | `git diff --stat` names neither; the smoke's shared-region, `unsafe`, `extern`, and no-`malloc` scans pass |
| 4.6 `ggml_spike.align` byte-unchanged | not edited | `ds-arm-unknown-flag` on `--decode-stepped` |
| 4.7 fixture `K = 3` loop, `model-decode-tokens.txt` | `write_decode_corpus` | `ds-steps-3` asserts `token_ids` equals the reference loop's ids |
| 5 `Makefile` untouched | not edited | `gmake gate-topology-check`; `baseline-check` is `N/A` |

### 11.2 Closure matrix cells with no counterpart, named

| Cell | Why |
| --- | --- |
| 4.2 `R6_PLANE_WRITE` on a short write-back | **Deferred, as section 7 records.** It guards a `slot_get` filling fewer bytes than the node declares, which the arm's own sizing makes unreachable, and R6 deferred the identical cell for the prefill for the identical reason. No forced build produces it |
| 4.2 `R6_PLANE_UNAVAILABLE` | Deferred on R6's terms, unchanged |
| A step failing at a chosen **layer** index inside a step | Still not exercised: the forced builds fail at a graph boundary, and a per-layer discriminator in the shim for one cell is deferred as R6 deferred it. What **is** newly exercised is a failure at a chosen **step** index, `ds-force-compute-step2` |
| 4.1 move-in/out, source nulling, replacement, return | `N/A` — no ownership transfer is added; the per-step data travels as a column set |
| 4.3 `layer_qwen2` failure / malformed / early exit / cleanup | `N/A` — both constants are values and both writers are pure and total |

### 11.3 Deviations from the ledger, with reasons

Ten, each recorded rather than absorbed.

1. **`StepColumns` carries no `array<str>`.** Section 4.4 declares `sha256, oracle_verdict,
   oracle_worst_node : array<str>`. Indexing an array of a Move element type is **Align Request 22**,
   which section 8 commits this capability to leaving unconsumed, so the digests are one
   fixed-width-sliced string (`ScheduleColumns.digests`' shape since R5B), the worst-node names are
   one string with a start/end column pair (`GraphMembers.names`' shape since R5A), and the verdict
   is the same `i64` code every other verdict on the wire already is. Neither is a new pattern and
   the rendered document is unchanged by the choice.
2. **Gate G compares the six printed values and records the sum.** Section 3.2's fingerprint is a
   seven-tuple. The refinement, its measurement, and its reason are in section 3.2: both keys select
   the same classes, and the sum is the only one of the seven exposed to the reference build's
   floating-point contraction.
3. **The fingerprint measurement reads the source GGUF, not the pack.** Section 3.2 says "from the
   arm's own pack". It is equivalent rather than looser: every member the arm reads is compared byte
   for byte against that same GGUF at its own `source_offset` before its graph runs, and the runner
   asserts `reference.verdict == "IDENTICAL"` on every prompt. Reading the GGUF avoids a second
   container reader in Python.
4. **The dequantizer lives in `scripts/decode_step_fingerprint.py`.** Section 3.2 says
   "`scripts/run-decode-step` computes". It invokes it. A 120-line Q4_K dequantizer embedded in a
   bash heredoc is not reviewable, and the module is independently runnable, which is how the
   measurement was taken before the runner existed.
5. **The per-step transcript scan runs for every step, including step 1, inside the loop.** R6
   prepared one scan before the prefill. Section 2.7 orders steps 13/13a **after** 11'/12', which is
   what the loop now does; the cost is that a malformed transcript is refused after the prefill
   rather than before it, and the benefit is one code path for `N` steps instead of two.
6. **Step 14's detail keeps R6's shape.** Section 2.7 illustrates `step[<k>]kq[<n>]ne0[<n>]`; the
   implementation emits `step[<k>]layer[<n>]node[<id>]`, which is R6's own detail with the prefix
   added. Changing the inner shape would move a detail no reader asked to move.
7. **`plane.roundtrip_verdict` on an error document is `-`, never the last completed step's.**
   Section 2.8 says both "the last completed step's" and "never `IDENTICAL` on an error document".
   The two disagree whenever every completed step passed, and the stronger sentence wins;
   `columns_written` is where the number of verified columns is published.
8. **The per-step mask and position images are one buffer each, sliced per step.** Section 2.6 says
   "rewritten in place". Align's `buffer` is append-only, so the honest form is one buffer holding
   every step's row, written once in order. The bytes and the order are identical and no reservation
   happens inside the loop.
9. **`ds-logits-dash` is an engine case, not a malformed-input case.** Section 4.1 lists it under
   malformed input. `-` is a *valid* operand, so the case succeeds and its golden row is a success
   document; listing it under malformed input would have made a passing case look like a refusal.
10. **Section 8 said this capability adds no client evidence to Request 22; it adds one.** The
    tokenizer half of that claim is unchanged and correct. The other half is not: deviation 1's
    `StepColumns` is a fourth avoidance of the Move-array shape and the first outside a container
    reader, which is exactly the kind of thing that request's entry already tracks. One line was
    added to `docs/align-requests.md` recording it. No hypothetical surface is consumed, the request
    stays `PROPOSED` and non-blocking, and no new request is proposed — number 50 stays free.
