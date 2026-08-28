# R5E-MOE-MODEL-PREFILL: a whole OLMoE prefill streamed through two Align-owned windows and sixteen routing decisions

Status: design of record for the R5E capability.
Owner document for stage 3 of `docs/specs/roadmap.md` section R5's gate **on the routed path**.
Align pin: `.align-revision` = `3a34febe912db5096c58c74fede36ff53f223e04`, adopted at reconciliation
(correction C23); the design and probe record were written at `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`.
Predecessors, whose contracts this capability extends rather than duplicates:
[`r5b-model-prefill-forward.md`](r5b-model-prefill-forward.md) (the streaming per-layer window, the
Align-owned residual carry, the narrowing rows, the KV-width reconciliation, the `--save-logits`
oracle, the arity table, the `schedule[]` document shape) and
[`r5d-moe-layer-forward.md`](r5d-moe-layer-forward.md) (the two-phase routed graph, the compact
expert stack and `mul_mat_id`, the claim window, `(kind, layer, role_id)` block selection, the
routing-identity oracle, and the `R5D_*` code family).
Inputs consumed verbatim: [`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md) section 2.4's
container, [`r1c-olmoe-moe-ir.md`](r1c-olmoe-moe-ir.md) section 2.4's `model` object and section
2.5.3's block order, [`moe-prereq-discharge.md`](moe-prereq-discharge.md)'s claim member form and
`R4_5_SLICE`, and [`r2a-expert-trace.md`](r2a-expert-trace.md) section 2.2's transcript line grammar.

This document triggers the proportional design gate of `CLAUDE.md` on four counts: a new public CLI
arm, a new versioned exchanged document (`R5_MOE_MODEL_FORWARD`), a new ownership boundary — a
weight window whose *size is decided by data the graph itself produces*, reserved once and refilled
sixteen times against sixteen different routing decisions — and a coordinated invariant across six
modules. Section 3 is the single public-contract ledger, section 4 is the closure matrix, and
section 5 owns fixtures, qualification, metrics, deferrals, risks, and candidate Align requests.

Section 2 is the probe record and it is first on purpose. Every contract in section 3 was chosen
after the probe. Six of this design's decisions exist **only** because a probe refuted the plan this
document started with: the router's probability gather takes the **global** expert ids while
`mul_mat_id` takes the compacted ones and the plan conflated them; the reconciliation width changes
the **routing decision** and not merely the arithmetic, which promotes `KV_WIDTH` from optional
metadata to a mandatory operand; R5D's slot-store ceiling binds `n_expert_used` and **not** the
routed union `U`, so no multi-pass and no larger store is needed; the routed union over forty-one
prompts reaches 33 against an arithmetic bound of 48, so the reused claim window must be reserved
for the bound and not for the observation; the whole-model residency win is **33.4%** rather than
R5D's single-layer 39.1%; and R5B's "top ten equal, in order" logits rule is not reachable on this
model at the runtime width, for a measured reason.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

`docs/specs/roadmap.md` section R5's gate is three stages in order: **単一block、単一layer、最小モデル**.
R4.5 discharged stage 1 for a dense member and `moe-prereq-discharge.md` for an expert claim; R5A
discharged stage 2 for a dense layer and R5D for a **routed** layer; R5B discharged stage 3 for a
**dense** model. Every one of those results is about a schedule whose weight set is known before the
schedule runs, or about a single routed layer whose decision is taken once.

R5E is **stage 3 for the routed path, and only that**: one prefill of at most six tokens through the
whole of OLMoE — sixteen MoE layers, `output_norm`, and `output` — computed by ggml over attention
and router weights and **only the routed experts' planes**, all held in Align-owned buffers, with
sixteen independent routing decisions taken in Align between thirty-four graphs, checked against
llama.cpp's own numbers for the same tokens.

The question stage 3-MoE answers is not "can one routed layer be reproduced" — R5D answered that.
It is: **when a model's weight demand is decided sixteen times over, each decision depending on
every decision before it, and one reused window has to hold whatever each decision names, is the
result still the model llama.cpp computes — and how much of the model does it never touch?** A
schedule that routes layer 7 correctly but carries layer 6's residual at the wrong width, or reuses
a claim window before the previous layer's tensors are freed, produces a model that is finite,
plausible, and wrong. Section 2 measures both halves: the answer is byte-identical, and the model
never touches 66.6% of its expert bytes.

The capability that answers it is **R5E-MOE-MODEL-PREFILL**: a new arm of the existing `ggml-spike`
executable that streams OLMoE's blocks out of an alignpack v1 container into two reused Align-owned
windows, computes each layer in two graphs with an Align-owned routing decision between them,
carries the residual stream in Align between every graph, narrows at layer 15's residual add,
computes the head, and emits an `R5_MOE_MODEL_FORWARD` document carrying a per-layer schedule, the
union curve, the final logits, and **four independent oracle verdicts**.

### 1.2 In scope

- One new Align module, `src/moe_model_forward.align`, owning the arm: the schedule, the two
  windows, the sixteen routing decisions, the residual carry, the four oracles, the document, and
  the teardown. Section 5.5 records why it is a new module and not more of
  `src/moe_layer_forward.align`.
- A **`LAYER` operand for `src/layer_olmoe.align`**. R5D's tables name layer 0 and only layer 0:
  the transcript names are literals (`ffn_moe_logits-0`), the member roles are read at layer 0, and
  the shape rules assume one token count. R5E parameterizes all three by `L`, adds the two narrowing
  rows and the three reconciliation-width rows as `node_when` conditions in R5B section 3.6's shape,
  and adds the head table. The module still contains no `extern` and no `unsafe`.
- One new CLI arm, `ggml-spike --moe-model-forward`, and the `R5_MOE_MODEL_FORWARD` document at
  `schema_version: 1`.
- Four oracles, all defined in section 3.7: a **bit-exact self-reference** oracle over every node of
  every graph; a **per-layer transcript** oracle over 227 nodes; a **per-layer routing-identity**
  oracle over 728 selected expert ids; and a **logits** oracle that is byte-identical at the
  instrument's attention width and bounded at the runtime's own.
- The residency measurement this capability exists to produce, at model scale: expert bytes read
  against the model's whole expert footprint, per layer and cumulatively, with the per-layer routed
  union published so a residency policy can be designed against data rather than intuition.
- One owner test — a fifth block in `scripts/run-layer-forward-smoke` against a synthetic two-layer
  OLMoE **full model** — and one named focused qualification, `scripts/run-moe-model-forward`,
  against the real model, real ggml, and both llama.cpp instruments.

### 1.3 Non-goals

- **No loader and no residency policy.** R5E reads what sixteen routing decisions name, once each,
  and holds each for one graph. Cache score, eviction, tiering, and prefetch remain the R5 loader's,
  exactly as `r5b-model-prefill-forward.md` section 5.4 and `r5d-moe-layer-forward.md` section 5.4
  defer them. Section 5.4 is explicit about **why R5E cannot even simulate one**: section 2.9
  measures that within a single prefill no `(layer, expert)` key is demanded twice, so there is
  nothing for a cache to hit. That is `docs/specs/r3-residency-sim.md` section 2's finding, arrived
  at from the other direction.
- **No decode and no KV cache.** The attention is computed over the prefill's own positions.
  `MAX_PREFILL_TOKENS` stays 6 for R5A section 3.3's reason — the instrument prints every row of an
  axis only while its extent is `<= 6`. R6 owns the cache and the instrument it will need.
- **No GPU arm.** `r5c-metal-prefill.md` owns the Metal boundary for the dense graph. Section 5.6's
  tie-ordering risk, inherited from `r5d-moe-layer-forward.md` section 5.6, cannot be settled with
  CPU evidence; section 5.4 keeps it deferred.
- **No gpt-oss and no second MoE architecture.** The six-member `ExpertBlock`, MXFP4 geometry, split
  expert biases, and fused `ffn_gate_up_exps` stay where `moe-prereq-discharge.md` section 5.5
  leaves them.
- **No new container version.** R5E reads alignpack v1 with the claim member form
  `moe-prereq-discharge.md` already admits, and writes nothing to it.
- **No microbenchmarks A and C.** R5E measures B, on the CPU, for a whole routed model, and section
  5.3 says so as a number.
- **No rename to `align-runtime`.** `r5b-model-prefill-forward.md` section 5.4 fixed the condition:
  the rename happens when the executable gains a residency policy. It has not.

### 1.4 Gate statement

Each stage is discharged, partly discharged, or deferred **individually**, with the probe that
settles it named.

| Gate stage | Verdict | Evidence |
| --- | --- | --- |
| 単一block, dense and expert claim | **Discharged by R4.5 and MOE-PREREQ-DISCHARGE.** Not re-litigated | `r4-5-external-buffer.md` section 1.4; `moe-prereq-discharge.md` section 1.1 |
| 単一layer, dense | **Discharged by R5A** | `r5a-dense-layer-forward.md` section 1.4 |
| 単一layer, routed | **Discharged by R5D** | `r5d-moe-layer-forward.md` section 1.4 |
| 最小モデル, dense | **Discharged by R5B** | `r5b-model-prefill-forward.md` section 1.4 |
| **最小モデル, routed** | **Dischargeable, CPU, prefill.** At the instrument's declared attention width the 50,304 final logits are **byte-identical** to `llama-debug --save-logits`, `sha256` `a56195da…`, on four different prompts; all 227 oracle nodes of all sixteen layers and the head agree with `llama-eval-callback` to the last digit it prints over 21,372 elements; all 728 selected expert ids agree; and the whole model over Align-owned compacted claims is byte-identical to the same model over all 1,024 whole expert planes | Sections 2.4, 2.5, 2.6, 2.7 |
| required microbenchmark A — transfer + GPU compute | **N/A here.** `r5c-metal-prefill.md` owns it for the dense graph; no routed GPU arm exists | Section 5.4 |
| required microbenchmark **B** — CPU compute, whole routed model | **Discharged at 121 ms** of graph compute for a six-token prefill of all sixteen layers plus the head, warm, median of five, at the reconciliation width; **399 ms** wall including 267 ms of `pread` | Sections 2.11, 5.3 |
| required microbenchmark C — async prefetch + GPU compute | **Deferred.** Prefetch is a loader property; Request 41 blocks the construct | Section 5.4 |
| **residency win in bytes** — the claim this capability exists to test | **Measured at model scale: 1,301,446,656 of 3,900,702,720 expert bytes, 33.36%**, and 343 of 1,024 `(layer, expert)` keys. Over forty-one prompts of three to six tokens the range is 21.67%–41.24%. The whole prefill reads 1,554,531,072 of the model's 4,213,512,192 bytes, **36.9%** | Sections 2.9, 2.10 |

The honest summary is: **R5E discharges stage 3 of three on the CPU for a routed model, and
microbenchmark B, and it publishes the residency curve rather than a single headline number.** It
leaves benchmarks A and C, the Metal arm, decode, the KV cache, and any residency *policy* where
their own evidence puts them. One R5D limit is closed rather than deferred: R5E computes every
layer, so the eight layers whose `ffn_down_exps` is Q4_K are reached for the first time.

---

## 2. Probe record

Everything in this section was executed on this host before section 3 was written. Commands are
given exactly as run. Probe sources live outside the work tree and are not part of the capability;
what ships is section 3's design, and section 5.2's qualification is the probe made reproducible.

### 2.1 Host, toolchain, model, and the two instruments

| Item | Value |
| --- | --- |
| Host | `MacBookAir10,1`, Apple M1, 16 GiB, `darwin/arm64` |
| Align compiler | the managed pinned release toolchain at `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` at probe time; `3a34febe912db5096c58c74fede36ff53f223e04` from correction C23 onward |
| llama.cpp | `0.2.0 (build 10566)`, Homebrew |
| ggml | `0.21.0`, Homebrew, headers in `/opt/homebrew/include`, backends `dlopen`ed from `libexec` |
| Model | `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 4,213,512,192 bytes, 195 tensors |
| Backend selected | `CPU`, through R4.5's registry path; `ggml_backend_buft_get_alignment` = `32` |
| Free space | 12–13 GiB throughout; **no pack was written** (see below) |

The geometry, read from the container and already published by `r1c-olmoe-moe-ir.md` section 2.4:
`arch` olmoe, `n_layer` 16, `n_embd` 2048, `n_head` 16, `n_head_kv` 16 (MHA), `head_dim` 128,
`n_ff_exp` 1024, `n_vocab` 50304, `n_expert` 64, `n_expert_used` 8, `context_length` 4096, `rms_eps`
1e-05, `rope.type` 2 (NEOX), `rope.freq_base` 10000.0, `rope.dim_count` 128, `rope.scaling_type`
`null`.

Three member facts the probe read and the design depends on:

```text
token_embd.weight    type 12 (Q4_K)   57,950,208 B    row_bytes 1,152
output_norm.weight   type  0 (F32)         8,192 B
output.weight        type 14 (Q6_K)   84,510,720 B    NOT tied to token_embd
```

`output.weight` is a real Q6_K tensor. It is **not** tied, and it is 20× the largest layer's dense
member set — which is what sizes the reused dense window in section 3.5, exactly as it did in
`r5b-model-prefill-forward.md` section 2.1 for Qwen2 at 447 MB.

**The two instruments and one contractual flag set.** `r5b-model-prefill-forward.md` section 2.2
established that `llama-eval-callback` and `llama-debug --save-logits` are an oracle only together
and only when both are pinned by the same flags, `-nr` included. That result is inherited and was
re-confirmed here: with `-nr` the OLMoE logits file has `sha256`
`a56195da2c913d8dd7fa608917a381200c4b59d1c534fae2d4bbb828f80d2383` and without it
`f054e7e31fc7aa8fe94e8558…`, a max `|Δ|` of 0.4217 — with the argmax unchanged, which is exactly why
the flag must be contractual rather than checked.

```text
$ llama-tokenize -m OLMoE-...-Q4_K_M.gguf -p "def add(a, b" --ids
[1545, 823, 9, 66, 13, 270]

$ FLAGS='-p "def add(a, b" -n 1 -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512'
$ llama-eval-callback -m $MODEL $FLAGS > transcript.txt        # 27,859 lines, 1,014 nodes, ~3.0 s
$ llama-debug        -m $MODEL $FLAGS --save-logits --logits-output-dir lg   # 6.3 s
$ ls -l lg/llamacpp-OLMoE-1B-7B-0125-Instruct-Q4_K_M.bin
201216                                    # 50,304 x 4, exactly n_vocab f32 for the final position
```

Two consecutive `llama-debug` runs were byte-identical. `llama-debug`'s own `-tokens.bin` carries
`1545, 823, 9, 66, 13, 270`, identical to `llama-tokenize --ids`, so neither instrument has to be
trusted to have tokenized the same prompt — each publishes what it used.

The prompt is `"def add(a, b"` and not R5A's `"def add(a, b):"`, for
`r5d-moe-layer-forward.md` section 5.2's reason: OLMoE's tokenizer produces **seven** ids for the
latter and `MAX_PREFILL_TOKENS` is 6.

**The probe read the model's own bytes, not a pack's.** This is a deliberate and stated limitation.
A 4.21 GB alignpack of this model was already written and measured during R5D (`R4_ALIGNPACK`:
`block_count` 1,058, `member_count` 3,219, `total_bytes` 4,212,193,280, `block_align` 4,096,
`member_align` 64, `payload_offset` 462,848, layout `model_ir`, zero padding and zero duplication),
and `r5d-moe-layer-forward.md` section 2.7 measured its bytes byte-equal to the GGUF's over all
101,990,400 claim bytes of layer 0. The R5E probe therefore reads each member at its GGUF
`source_offset`, which is the same content the pack's `pack_offset` holds, and section 5.2's
qualification is what measures the real pack's *read shape*. Section 2.11 records the consequence
for the timing table and section 5.6 records the risk.

### 2.2 Probe 1 — where an OLMoE prefill narrows, and what it does to the last layer's routing

`r5b-model-prefill-forward.md` section 2.3 found that Qwen2's prefill narrows to the last token
**inside** the last layer, after the attention output projection, on both branches of the residual
add — not at the last layer's input. `moe-prereq-discharge.md` section 5.6 separately recorded that
OLMoE's `ffn_moe_topk-15` is `{8, 1}` while `embd` is `{2048, 6}`. The probe located the exact node
pair that reconciles the two, because a routed model that narrows one node early or late is not
slower, it is wrong: layer 15's attention still needs all six positions' keys and values, and layer
15's *router* must see one token and not six.

```text
node_977   = MUL_MAT(blk.15.attn_output.weight{2048,2048}, kqv_out-15{2048,6}) = {2048, 6}
node_978   = GET_ROWS(node_977{2048,6},  leaf_227{1})                          = {2048, 1}
node_979   = GET_ROWS(l_out-14{2048,6},  leaf_227{1})                          = {2048, 1}
ffn_inp-15 = ADD(node_978{2048,1}, node_979{2048,1})                           = {2048, 1}
norm-15    = RMS_NORM(ffn_inp-15{2048,1})                                      = {2048, 1}
ffn_norm-15= MUL(norm-15{2048,1}, blk.15.ffn_norm.weight{2048,1})              = {2048, 1}
ffn_moe_logits-15 = MUL_MAT(blk.15.ffn_gate_inp.weight{2048,64}, ffn_norm-15{2048,1}) = {64, 1}
l_out-15   = ADD(ffn_moe_out-15{2048,1}, ffn_inp-15{2048,1})                   = {2048, 1}
norm          = RMS_NORM(l_out-15{2048,1})                                     = {2048, 1}
result_norm   = MUL(norm{2048,1}, output_norm.weight{2048,1})                  = {2048, 1}
result_output = MUL_MAT(output.weight{2048,50304}, result_norm{2048,1})        = {50304, 1}
```

**The narrowing is a pair of `GET_ROWS` inside layer 15, after the attention output projection, on
both residual branches — structurally identical to R5B's Qwen2 finding, and it lands *before* the
last layer's router.** Layers 0 to 14 are `{2048, 6}` throughout; `ffn_inp-15` onward is
`{2048, 1}`. Three consequences the plan did not have:

1. **The last layer's routing is over one token.** `ffn_moe_logits-15`, `ffn_moe_probs-15`,
   `ffn_moe_argsort-15`, and `ffn_moe_topk-15` are all `{·, 1}`, so the routed union at layer 15 is
   exactly `n_expert_used = 8` and layer 15 reads **12.5%** of its expert bytes against 28–44% for
   every other layer. That single fact is worth 2.1 points of the whole-model residency number and
   section 2.9 does not let it hide.
2. **`norm-15` is printed twice under one name at two different shapes** — `{2048, 6}` for the
   attention RMS-norm of layer 15 and `{2048, 1}` for its FFN RMS-norm. This is
   `r5d-moe-layer-forward.md` section 2.2 fact 5's `ambiguous_name` class, now with a *shape*
   ambiguity on top of the name ambiguity, and it is why section 3.7 matches every node by
   `(name, declared shape)` and never by name alone.
3. **The head's three nodes carry no layer suffix** — `norm`, `result_norm`, `result_output` — so
   they are their own oracle rows and not layer 15's, exactly as R5B found.

The attention-output projection is `node_977` under this flag set, `node_914` at layer 14, and
`node_31` in R5D's single-layer run: the positional name moves with the layer and with the flags,
which is the fourth confirmation of `r5a-dense-layer-forward.md` section 2.2's fact 3. Section 3.7
matches it by its source weight name in every one of the sixteen layers.

### 2.3 Probe 2 — the whole-model C harness, and the bug the plan would have shipped

A C harness streamed the model through **two** `posix_memalign` windows — one for dense members,
one for expert claims — wrapping each with `ggml_backend_dev_buffer_from_host_ptr` and placing every
weight with `ggml_backend_tensor_alloc` at its interior offset, carrying the residual stream and the
four phase-A-to-phase-B values in plain host buffers between graphs:

```text
$ ./moemodel MODEL.gguf out mine256.bin 256 6 1545 823 9 66 13 270
HP n_layer=16 n_embd=2048 n_head=16 head_dim=128 n_ff_exp=1024 n_vocab=50304
   n_expert=64 n_used=8 freq_base=10000.0 rms_eps=1e-05 n_ctx_orig=4096 KVW=256 T=6
WINDOW dense=84520960 (emb=8192 maxlayer=11075584 head=84520960) claim_cap=195821568
BACKEND CPU alignment=32
SUMMARY graphs=34 nodes=1031 placements=195 ptr_fail=0 bufs=34/34
```

**All 195 weight placements satisfied `ggml_get_data(t) == base + window_offset`**, so R4.5's gate
clause holds 195 times across two windows rather than once, and every ggml buffer was freed before
the next block's read began — 34 created, 34 freed.

**The plan's bug, which the probe found and which no shape check would have.** The design this
document started with carried *one* id table from phase A to phase B and used it for both
`ggml_get_rows(probs_reshaped, ids)` and the three `ggml_mul_mat_id(stack, x, ids)` calls. That is
wrong, and it is wrong in a way that runs:

```text
ffn_moe_argsort-0   agrees with the transcript exactly           (sum 12096.000000)
ffn_moe_weights-0   mine 0.809123          transcript 2.735722   <-- first divergence
ffn_moe_gate-0      mine -6427.208036      transcript -6427.178711   (agrees)
```

`ffn_moe_weights` gathers rows out of the **`{1, n_expert, T}` probability tensor**, so its index
must be the **global** expert id in `[0, n_expert)`. `mul_mat_id` indexes the **compacted stack**,
so its index must be the remapped id in `[0, U)`. R5D's design says exactly this — section 3.5
carries "`topk_ids` / `compact_ids`" as two tensors — and R5D's own probe never separated them
because it computed the weights in phase A. At model scale, with the phase boundary drawn where
section 3.6 draws it, the two indices are both inputs to phase B and conflating them produces a
model whose every gate, up, swiglu and down node is *correct* and whose expert mixing weights are
garbage. Every shape check passes; `ffn_moe_gate` still agrees with llama.cpp; the logits are finite.
**Section 3.6 therefore makes the two id tables two separately named carried inputs with two
separately validated ranges, and section 3.9 step 26 validates each against its own bound.**

The graph shape, measured rather than assumed:

```text
embedding graph                     1 node    GET_ROWS(token_embd rows, inp_tokens)
layer graph A, L in 0..14          32 nodes   runtime width;  35 at the reconciliation width
layer graph A, L = 15              34 nodes   + two narrowing GET_ROWS; 37 at the reconciliation width
layer graph B, every L             29 nodes   at both widths
head graph                          4 nodes
whole prefill                     983 nodes   runtime width
                                1,031 nodes   reconciliation width
```

The three reconciliation rows are R5B section 2.7's: `cont` and `pad` on K, `pad` on V, +3 per
layer, +48 over the model. Phase B is width-independent, which is the first hint that phase B is not
where the reconciliation cost lives.

### 2.4 Probe 3 — the whole model at the instrument's attention width is byte-identical

llama.cpp reduces attention over `n_kv = 256`, the padded width of its 512-cell KV cache, of which
250 columns are zero and masked; R5E reduces over 6. The *values* are the same and the **f32
reduction length is not**, which is the whole of `r5b-model-prefill-forward.md` sections 2.6 and 2.7.
The harness was re-run with K and V zero-padded to a declared width of 256 and the mask widened to
`{256, 6}` — **not a cache**: nothing persists between graphs, no position is read back, and the
padding is rebuilt from zero in every layer.

```text
$ cmp mine256.bin lg/llamacpp-OLMoE-1B-7B-0125-Instruct-Q4_K_M.bin
(no output)
$ shasum -a 256 mine256.bin lg/llamacpp-...bin
a56195da2c913d8dd7fa608917a381200c4b59d1c534fae2d4bbb828f80d2383   both
```

**The 201,216 bytes are identical.** `bit_sum` 149,873,641,306,457, `argmax` 2262, `nonfinite_count`
0, f32 sequential sum `-111030.031250` — which is the value the transcript prints for
`result_output`, to the last bit. **Three consecutive runs produced byte-identical files**, and the
result reproduced on **four different six-token prompts**:

| Prompt | tokens | reconciliation width 256 |
| --- | --- | --- |
| `def add(a, b` | 1545,823,9,66,13,270 | **byte-identical**, `a56195da…` |
| `git commit -m "fix` | 14769,4514,428,78,346,11097 | **byte-identical** |
| `docker run -it --rm` | 31510,1408,428,262,1969,1109 | **byte-identical** |
| `npm install --save-dev` | 24541,3334,1969,15261,14,3620 | **byte-identical** |

This settles four things at once, none of which a tolerance could have settled:

1. **The topology of all sixteen routed layers, every scalar, the RoPE mode and base, the attention
   scale, the mask, the narrowing point, the head, the row-gathered embedding, the compacted expert
   stack, the two id tables, and the ordering of the eight-way expert reduction are all exactly
   right.** A whole MoE model does not reproduce 50,304 f32 values bit-for-bit by accident, four
   times.
2. **Sixteen data-dependent routing decisions taken in Align reproduce llama.cpp's exactly**,
   including layer 15's single-token decision.
3. **The window reuse is safe.** Two windows refilled 34 times, 195 borrowed placements, and no
   stale pointer — a tensor left alive across a refill would compute the next layer with the
   previous layer's weights and would not survive byte-identity.
4. **R5E can ship a bit-exact end-to-end verdict**, which is a categorically better acceptance
   contract than a tolerance. Section 3.3 makes the width an operand the caller declares rather than
   a constant this repository copies out of llama.cpp.

### 2.5 Probe 4 — the transcript oracle across sixteen layers and the head

At the reconciliation width, against the same transcript, every oracle node of every layer, matched
by `(name, declared shape)` and compared element-wise in `r5a-dense-layer-forward.md` section 3.6's
ten-thousandths units:

```text
NODES matched      = 227 of 227    (14 per layer x 16, plus embd, result_norm, result_output)
ELEMENTS compared  = 21,372
WORST ten-thousandths delta = 0
per-layer max tt   = 0 for every one of the sixteen layers, and 0 for the head
SUM rule failures  = 0 of 227      worst |Δ|/tolerance ratio = 0.523 at ffn_moe_gate-8
```

**Not one of the 21,372 sampled elements differed from the instrument's printed value by a single
unit of the last digit printed.** `llama-eval-callback` prints `%12.4f`, so a printed value carries
an inherent ±5.0e-5 and zero ten-thousandths is the print bound rather than an achievement — but it
is the print bound reached at every node of a whole routed model.

**R5A's sum rule is inherited unchanged and unwidened.** The rule is
`|Δ| <= max(1.0e-3, 1.0e-5 · |Σ|)` in millionths against a sequential f32 accumulation in element
order. Zero of 227 nodes breach it and the worst node uses 52.3% of its allowance. The worst
*absolute* residual is 56,845 millionths at `ffn_moe_gate-11`, whose `|Σ|` is large enough that the
relative arm governs; the worst *relative* residual is 79.7 ppm at `ffn_moe_up-4`, whose `|Σ|` is
2.4 so the 1,000-millionth floor governs. Both arms of the rule are load-bearing on this model,
which is worth recording because R5A's single dense layer exercised only one of them.

The fourteen compared nodes per layer are `attn_norm`, `ffn_inp`, `ffn_norm`, `ffn_moe_logits`,
`ffn_moe_probs`, `ffn_moe_argsort`, `ffn_moe_weights`, `ffn_moe_gate`, `ffn_moe_up`,
`ffn_moe_swiglu`, `ffn_moe_down`, `ffn_moe_weighted`, `ffn_moe_out`, and `l_out`. Section 3.7 fixes
the full table including the exclusions.

### 2.6 Probe 5 — the bit-exact self-reference oracle, 227 of 227

Every weight tensor of every one of the 34 graphs was created in a second context and allocated by
`ggml_backend_alloc_ctx_tensors`, with `ggml_get_data(t)` asserted **not** to equal the host pointer,
so the arm is genuinely ggml-owned and cannot pass by aliasing:

```text
$ ALIGN_R5E_REF=1 ./moemodel MODEL.gguf out_ref ref256.bin 256 6 1545 823 9 66 13 270
$ cmp ref256.bin mine256.bin && for f in out_run256/*.bin; do cmp -s "$f" "out_ref/$(basename $f)" || echo DIFF; done
(no output — the logits and 227 of 227 node dumps byte-identical)
SUMMARY graphs=34 nodes=1031 placements=0 ptr_fail=0 bufs=34/34
```

Peak resident set for the reference arm was **440,926,208 B** against the shipped arm's
341,917,696, because it holds both windows *and* ggml's copy of the current block. Wall was 999 ms
against 399 ms, and compute 145.0 ms against 121.3 ms.

This oracle proves **bytes**, it is version- and kernel-independent, and at model scale it is the
only check that catches a window refilled before its previous tenant was freed.

### 2.7 Probe 6 — the compacted claim stack against the whole tensor, at model scale

`r5d-moe-layer-forward.md` section 5.6 records that the equivalence of a compact `{ne0, ne1, U}`
stack with remapped ids and a `{ne0, ne1, n_expert}` stack with global ids is measured, not
documented, and that a divergence would be a redesign. R5D measured it once, on one layer. R5E
measured it across the whole model:

```text
$ ALIGN_R5E_WHOLE=1 ./moemodel MODEL.gguf out whole256.bin 256 6 1545 823 9 66 13 270
BYTES expert_read=3900702720   pread_count=200   pread_bytes=4153787136
TIME  wall_ms=1342.749 claim_pread_ms=1123.661 compute_ms=124.873
$ cmp whole256.bin mine256.bin
(no output)
```

**Byte-identical**, over sixteen layers, 1,024 planes against 343, and both quantization mixes. The
whole-tensor arm reads **3,900,702,720** expert bytes against the routed arm's **1,301,446,656**,
spends 1,123.7 ms in `pread` against 227 ms, and computes in the same time (124.9 vs 121.3 ms) —
which is the expected result and worth stating: `mul_mat_id` costs what it computes, not what is
resident behind it.

This is a probe arm and not a shipped oracle. Making it one would cost 3.9 GB of reads per
qualification run to re-derive a property the transcript oracle already detects; section 5.6 records
it as the mitigation of record for the `mul_mat_id` version risk, as R5D does.

### 2.8 Probe 7 — the runtime attention width changes the **routing**, not just the arithmetic

R5B's dense model at its own attention width drifted smoothly: layers 0–3 agreed with the instrument
to the last printed digit and the per-layer maximum grew monotonically to 4,899 ten-thousandths at
layer 26. OLMoE does not do that.

```text
layer      0    1    2    3    4     5    6    7     8    9   10   11     12     13    14     15   head
max tt     0    0    0    4   85 10094  333  345 10331  515  640  512  19968  32363  1174  49218    988
```

The discontinuities are not arithmetic. Comparing the two runs' selected expert ids:

```text
routing slots total = 728        differing = 12 (1.6%)      first differing layer = 5
per layer differing: L5:2  L8:2  L12:4  L13:2  L15:2   (all other layers: 0)
routed union sizes: identical at both widths, all sixteen layers
```

**Twelve of 728 `(layer, token, slot)` selections change when the attention reduction length
changes.** A rank-8/rank-9 boundary decided by a probability gap smaller than the drift flips, the
layer then computes a *different expert*, and the affected node's elements move by whole units
rather than by ten-thousandths — 4.92 at layer 15. The union *sizes* happen to be unchanged here,
so `expert_bytes_read` is the same at both widths on this prompt; that is a coincidence of this
prompt and not a property.

Three consequences, and they are the reason section 3.3 does what it does:

1. **The transcript oracle cannot be run at the runtime width at all.** It would not be comparing a
   drifted model, it would be comparing a *differently routed* model. R5B could describe its
   equivalent choice as a preference; R5E's is mandatory.
2. **`KV_WIDTH` is promoted from R5B's optional operand-seven to a mandatory operand-five.** In R5B
   the width changed the arithmetic of the comparison; here it changes which bytes the arm reads.
   An operand that selects the run's I/O is not optional metadata that travels with an oracle, and
   R5B's seven-operand gap disappears with it. Section 3.3 records the difference explicitly rather
   than presenting R5E's arity table as R5B's.
3. **The final logits are nevertheless close**, which is the interesting part. Over four prompts:

| Prompt | max `\|Δ\|` | ten-thousandths | mean `\|Δ\|` | argmax equal | top-10 set equal | top-10 order equal |
| --- | --- | --- | --- | --- | --- | --- |
| `def add(a, b` | 0.347694 | 3,477 | 0.0585 | yes (2262) | yes | **no** |
| `git commit -m "fix` | 0.347270 | 3,473 | 0.0628 | yes (27) | yes | yes |
| `docker run -it --rm` | 0.349059 | 3,491 | 0.0625 | yes (1969) | yes | **no** |
| `npm install --save-dev` | 0.308576 | 3,086 | 0.0506 | yes (1214) | yes | yes |

Zero of 50,304 elements exceed 0.5 on any prompt, against a logit range of 32.3. A twelve-slot
routing change and a 250-column reduction difference together are worth 0.35 of a logit and no
change of chosen token.

**R5B's "top ten equal, in order" rule is not reachable on this model, and the reason is measured.**
On `def add(a, b` the reference's ranks 3 and 4 are ids 13 and 27 at 15.0092 and 14.9319 — a gap of
0.0773 — while the mean drift is 0.0585 and the drift on those two elements is enough to swap them.
The top-ten **set** is equal on 4 of 4 prompts and the argmax on 4 of 4. Section 3.7 therefore
requires the argmax and the top-`k` **set**, publishes `top_k_order_agreement` as a reported number
rather than a criterion, and says why in one line rather than quietly dropping a predecessor's
clause.

### 2.9 Probe 8 — the residency measurement, per layer and cumulative

This is the number the capability exists to produce. `T = 6`, reconciliation width, one prefill:

| L | U | claim bytes | layer expert bytes | % | cumulative expert bytes | cumulative % | `ffn_down_exps` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 25 | 101,990,400 | 261,095,424 | 39.1 | 101,990,400 | 2.61 | Q6_K |
| 1 | 22 | 89,751,552 | 261,095,424 | 34.4 | 191,741,952 | 4.92 | Q6_K |
| 2 | 28 | 99,090,432 | 226,492,416 | 43.8 | 290,832,384 | 7.46 | **Q4_K** |
| 3 | 25 | 88,473,600 | 226,492,416 | 39.1 | 379,305,984 | 9.72 | **Q4_K** |
| 4 | 23 | 93,831,168 | 261,095,424 | 35.9 | 473,137,152 | 12.13 | Q6_K |
| 5 | 23 | 81,395,712 | 226,492,416 | 35.9 | 554,532,864 | 14.22 | **Q4_K** |
| 6 | 24 | 84,934,656 | 226,492,416 | 37.5 | 639,467,520 | 16.39 | **Q4_K** |
| 7 | 21 | 85,671,936 | 261,095,424 | 32.8 | 725,139,456 | 18.59 | Q6_K |
| 8 | 22 | 77,856,768 | 226,492,416 | 34.4 | 802,996,224 | 20.59 | **Q4_K** |
| 9 | 20 | 70,778,880 | 226,492,416 | 31.2 | 873,775,104 | 22.40 | **Q4_K** |
| 10 | 21 | 85,671,936 | 261,095,424 | 32.8 | 959,447,040 | 24.60 | Q6_K |
| 11 | 21 | 74,317,824 | 226,492,416 | 32.8 | 1,033,764,864 | 26.50 | **Q4_K** |
| 12 | 18 | 63,700,992 | 226,492,416 | 28.1 | 1,097,465,856 | 28.14 | **Q4_K** |
| 13 | 20 | 81,592,320 | 261,095,424 | 31.2 | 1,179,058,176 | 30.23 | Q6_K |
| 14 | 22 | 89,751,552 | 261,095,424 | 34.4 | 1,268,809,728 | 32.53 | Q6_K |
| 15 | **8** | 32,636,928 | 261,095,424 | **12.5** | **1,301,446,656** | **33.36** | Q6_K |

```text
expert bytes read  1,301,446,656 of 3,900,702,720          = 33.36%   (333,644 ppm)
keys demanded      343 of 1,024 (layer, expert) keys        = 33.50%
expert planes      1,029 of 3,072                           = 33.50%
dense bytes read   168,558,592 layers + 84,518,912 head + 6,912 embedding rows
whole prefill      1,554,531,072 of 4,213,512,192           = 36.90% of the model file
pread count        1,181 = 6 rows + 144 dense members + 1,029 claim planes + 2 head members
                   -- the probe's GGUF member shape. The shipped arm reads pack *blocks*:
                      6 + 16 + 16 + 343 + 1 = 382 groups carrying the same 1,554,531,072 bytes
```

Three honest readings, all of which belong in the gate table rather than in a footnote:

1. **33.4% is lower than R5D's single-layer 39.1%, and the reason is layer 15.** The narrowing
   collapses the last layer's routing to one token and its union to exactly eight, which alone moves
   the whole-model figure by 2.1 points. A design that reported layer 0's number as the model's
   would be overstating the win by 17%.
2. **Within one prefill, no `(layer, expert)` key is demanded twice.** There are 343 distinct keys
   and 343 claim reads. This is `docs/specs/r3-residency-sim.md` section 2's finding measured from
   the other end, and it is why section 1.3 says R5E cannot simulate a residency policy: within one
   prefill **there is nothing for a cache to hit**. The 66.6% that is never read is a property of the
   routing, not of a policy. Any policy claim needs a *multi-prefill* consumer, which section 5.4
   defers with this measurement as its premise.
3. **The Q4_K `ffn_down_exps` layers are reached.** `r5d-moe-layer-forward.md` section 1.3 named
   this as R5D's largest coverage gap — eight of sixteen layers whose `ffn_down_exps` and `attn_v`
   are Q4_K rather than Q6_K, per `r1c-olmoe-moe-ir.md` section 2.5.5. R5E computes all sixteen and
   the byte-identity of section 2.4 covers both mixes. The gap is closed, not deferred.

### 2.10 Probe 9 — how large the routed union actually gets, over forty-one prompts

`U` is the one data-dependent shape in the design, so the window that has to hold it cannot be sized
from one observation. Forty-one prompts of three to six tokens — code, shell, SQL, English,
Japanese, and compiler diagnostics — were tokenized with `llama-tokenize` and run at the
reconciliation width, giving 656 `(prompt, layer)` pairs:

```text
U over 656 (prompt, layer) pairs:   max = 33     min = 8      mean = 19.9
  T=3   5 prompts   max U = 20     arithmetic bound min(64, 8T) = 24
  T=4  16 prompts   max U = 29     arithmetic bound            = 32
  T=5  11 prompts   max U = 33     arithmetic bound            = 40
  T=6   9 prompts   max U = 33     arithmetic bound            = 48
largest observed:  P37 "Explain quantum computing in", T=5,
  U = [19,29,28,29,29,26,26,26,27,26,31,33,29,31,27,8]
expert bytes read across the 41 prompts:  845,414,400 (21.67%) .. 1,608,646,656 (41.24%)
  by prefill length, mean:  T=3 24.68%   T=4 30.70%   T=5 31.42%   T=6 34.42%
```

**The observed maximum is 33 and the arithmetic bound at `T = 6` is 48.** Section 3.5 reserves the
claim window for **48**, not for 33, and section 3.5 states what that costs: 195,821,568 B reserved
against a 101,990,400 B observed peak, so 93.8 MB of the window is idle on the measured prompt. The
alternative — a window sized per layer after each routing decision — is sixteen reservations, two
more lifetimes per layer, and a peak that is not knowable before the run; section 3.5 rejects it and
section 5.4 keeps "a claim window that shrinks to the decision" as an R6 measurement with these two
integers as its baseline.

**The routed union has no slot-store ceiling, and the plan believed it did.**
`r5d-moe-layer-forward.md` section 6 correction C1 refuses `n_expert_used` above **34**, because
phase B's node table is `2 · n_expert_used + 8` rows at `B_NODE_BASE` 52 in a store of
`MAX_NODE_SLOTS` 128. That bound is on `n_expert_used`, which is 8 here. **`U` enters the graph only
as `ne2` of three stacked tensors — three slots, whatever `U` is** — so it consumes no slot budget at
all, and the design needs neither a larger store nor a multi-pass over the routed union. The only
thing `U` bounds is the claim window's bytes, which section 3.9 step 21 checks against
`MAX_CLAIM_WINDOW_BYTES` before a byte is reserved. R5D's C1 bound is inherited verbatim and applies
unchanged to `n_expert_used`.

### 2.11 Probe 10 — budgets, timings, and the owner test's headroom

Five consecutive runs at the reconciliation width. The first two ran against a cold page cache; the
last three are warm and are what section 5.3 reports.

| Quantity | Measured |
| --- | --- |
| wall, warm, three runs | **390.1 / 398.6 / 399.9 ms** (cold: 780.6 / 708.8 ms) |
| graph compute, five runs | 125.6 / 121.3 / 120.0 / 117.3 / 127.2 ms — median **121.3 ms** |
| dense `pread`, warm | **~40 ms** for 253,084,416 B over 152 reads |
| claim `pread`, warm | **~227 ms** for 1,301,446,656 B over 1,029 scattered plane reads (cold: 510–544 ms) |
| per-layer phase A compute | 2.5–3.4 ms, median **3.1 ms** |
| per-layer phase B compute | 3.3–5.7 ms, median **4.4 ms** |
| layer 15 after the narrowing | A **3.08 ms**, B **1.07 ms** — phase B is 4.1× cheaper |
| per-layer claim read, warm | 11.1–17.9 ms, median **13.6 ms** |
| per-layer dense read, warm | ~**1.5 ms** for 9,994,240 or 11,075,584 B |
| head | `pread` **13.6 ms** for 84,518,912 B, compute **2.2–2.3 ms** |
| `gallocr` peak over 34 graphs | **4,440,064 B** |
| peak RSS, shipped arm, five runs | **341,639,168 – 343,015,424 B** (326 MiB) |
| peak RSS, self-reference arm | 440,926,208 B (420 MiB) |
| peak RSS, whole-tensor arm | 408,240,128 B (389 MiB) |
| `gmake layer-forward-smoke` today | **32.199 s**, four blocks, 34 no-document + 239 documented cases |
| `alignc check-per-unit src/moe_layer_forward.align` | **16.5 s** for 4,660 lines |
| `alignc check-per-unit src/model_forward.align` | **17.6 s** for 4,492 lines |
| `gmake check`, whole graph | **131.5 s**, against the 91.2 s `r5b-model-prefill-forward.md` section 2.9 recorded |
| whole OLMoE transcript | 27,859 lines, ~1.9 MB — too large to check in |
| free space | 12–13 GiB, against a 4.21 GB model; no pack written by the probe |

**The claim read is the cost, and it is 1.9× compute.** 227 ms of scattered plane reads against
121 ms of compute, warm, with the whole file in page cache. That is the number a residency policy
has to beat and it is the reason section 5.3 reports it rather than the compute figure alone.
`r5d-moe-layer-forward.md` section 2.7 measured that reading claims as **pack blocks** rather than as
scattered GGUF planes is cheaper — 12.0 ms against 15.5 ms warm for one layer's 25 claims — so the
shipped arm's 343 expert-**block** reads should beat the probe's 1,029 expert-**plane** reads. That is an extrapolation
from a one-layer measurement and section 5.2's qualification is what turns it into a number; section
5.6 carries the risk.

### 2.12 What the probes settle

1. The whole routed model is reproducible **to the bit** from Align-owned bytes at the instrument's
   attention width — 50,304 logits byte-identical on four prompts, 21,372 elements at zero
   ten-thousandths, 227 of 227 nodes byte-identical against ggml-owned weights.
2. The prefill narrows *inside* layer 15, after the attention output projection, on both residual
   branches, and therefore **before** the last layer's router. Layer 15 routes one token and reads
   12.5% of its experts.
3. At the runtime attention width the **routing decision itself changes** — 12 of 728 slots — so a
   transcript is a valid oracle only for a run computed at the instrument's own width, and
   `KV_WIDTH` is a mandatory operand rather than oracle metadata.
4. The final logits at the runtime width are within 0.35 with the argmax and the top-ten set intact
   on four of four prompts; the top-ten *order* is not, and R5B's ordering clause is replaced with a
   measurement.
5. The router's probability gather takes global expert ids and `mul_mat_id` takes compacted ones.
   Two carried tables, two validated ranges.
6. The routed union reaches 33 over 656 observations against an arithmetic bound of 48; it consumes
   no slot budget; the claim window is reserved for the bound.
7. The model reads **33.36%** of its expert bytes and **36.90%** of its file, and within one prefill
   nothing is demanded twice — so this is a routing property, not a cache result.
8. The claim read is 1.9× compute, warm. Residency has 227 ms per prefill to compete for.

---

## 3. Public-contract ledger

### 3.1 The executable, and why this is still an arm

R5E ships as **`ggml-spike --moe-model-forward`**, for `r5a-dense-layer-forward.md` section 3.1's
four reasons, unchanged and now applying for the fifth time: one link boundary, a discharged
prologue, an `align-runtime` name that should be claimed by the runtime rather than predicted, and a
CLI that already selects on the first operand. The rename remains conditioned on the arrival of a
residency policy, per `r5b-model-prefill-forward.md` section 5.4, and section 1.3 says it has not
arrived.

### 3.2 Hyperparameters

The container carries no hyperparameters, so the arm takes an **`R1_MODEL_IR` document at
`schema_version: 2`** and reads only its `model` object, with `rms_eps_bits` and
`rope.freq_base_bits` as lowercase eight-character hex strings validated by
`bits32_finite_nonnegative` (`r5a-dense-layer-forward.md` section 6, correction C17).

Consumed fields, and the union of R5B's and R5D's uses:

| Field | Use in R5E |
| --- | --- |
| `arch` | must be `"olmoe"`; step 8's precondition |
| `n_layer` | **the schedule**: every `L` in `[0, n_layer)` is computed, in order |
| `n_embd`, `n_head`, `n_head_kv`, `head_dim` | attention shapes; `n_head == n_head_kv` (MHA) |
| `n_ff_exp` | the expert planes' inner dimension |
| `n_vocab` | the head's `ne1`, the logits' element count, and the token-id bound |
| `n_expert`, `n_expert_used` | the router's width, the slot axis, and `U`'s arithmetic bound |
| `context_length` | `n_ctx_orig` for RoPE |
| `rms_eps_bits`, `rope_type`, `rope_dim_count`, `rope_freq_base_bits` | the five fixed RoPE constants, earned by step 8 |

On this model the bit patterns are `rms_eps_bits` `3727c5ac`, `rope_freq_base_bits` `461c4000`, and
the derived `attn_scale_bits` `3db504f3`.

### 3.3 CLI surface

```text
ggml-spike PACK.alignpack BLOCK MEMBER [DOC.json [REF.gguf]]                    # R4.5, unchanged
ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS ...                      # R5A, unchanged
ggml-spike --model-forward PACK GEOM.json TOKENS ...                            # R5B, unchanged
ggml-spike --moe-layer-forward PACK GEOM.json TOKENS ...                        # R5D, unchanged
ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH
ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json
ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json REF.gguf
ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json REF.gguf TRANSCRIPT.txt
ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json REF.gguf TRANSCRIPT.txt LOGITS.bin
ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json REF.gguf -              LOGITS.bin
ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH -        REF.gguf TRANSCRIPT.txt LOGITS.bin
```

**Exactly five, six, seven, eight, or nine operands. There is no gap.**
`r5b-model-prefill-forward.md` section 3.3 has one — seven is `R5_ARITY` — because R5B's `KV_WIDTH`
is optional and has to travel with the transcript that gives it meaning. **R5E's `KV_WIDTH` is
mandatory and is operand five**, and section 2.8 is the whole of the reason: on a routed model the
declared width changes which experts the router selects and therefore which bytes the arm reads. An
operand that selects a run's I/O is not oracle metadata. The change from R5B is deliberate and is
recorded here rather than presented as inheritance.

`MAX_PATH_BYTES` (non-empty, `<= 4096` bytes, no NUL) and `TOKENS` — 1 to 6 comma-separated
non-negative decimal ids, no spaces, no trailing comma, each `< n_vocab` — are
`r5a-dense-layer-forward.md` section 3.3's, verbatim. `MAX_PREFILL_TOKENS` is 6 and section 5.4
keeps lifting it with R6.

**`-` means "this operand is not a path", in exactly two positions**, and each position's effect is
stated rather than inferred. In the **document** position (six) it is R0's convention: write the
document to stdout. In the **transcript** position (eight) it means **the transcript arm does not
run** while the logits arm still does. That second form exists because on a routed model the two
oracles are **not** co-required: section 2.8 established that a transcript is a valid oracle only at
the width the instrument used, while the logits oracle is valid at both widths, so without it the
`WITHIN` verdict of section 3.7 would be unreachable on the real model — the runtime-width
invocation would have to omit `LOGITS.bin` to omit the transcript, and the runner rather than the arm
would own the comparison. `-` in any other position is `R5E_PATH`. `-` in the transcript position of
the **eight**-operand form is legal and degenerate — it leaves the self-reference oracle as the only
one running, which is the seven-operand form's behaviour — and is accepted rather than special-cased,
because refusing a legal operand pattern to prevent a caller from asking for less would be a rule
with no failure behind it.

**`KV_WIDTH` is the attention width the reference instrument used**, a non-negative decimal integer
in `[token_count, MAX_ATTENTION_WIDTH]` with `MAX_ATTENTION_WIDTH = 4096`. Throughout this document
the **reconciliation width** is a `KV_WIDTH` greater than `token_count` — 256 on this model at
`-c 512` — and the **runtime width** is `KV_WIDTH == token_count`; they name two *invocations*, not
two passes of one invocation. `KV_WIDTH == token_count` is legal and means "the instrument reduced
over the prefill". **The arm computes exactly one schedule, at `KV_WIDTH`, always** — there is no
second pass, for section 3.9 step 36's reason. A value outside `[token_count,
MAX_ATTENTION_WIDTH]`, or one that does not parse, is `R5_KV_WIDTH`.

**Deriving `KV_WIDTH` from the transcript remains rejected**, for R5B's reason and one more of
R5E's. R5B's reason: letting the file used as an oracle silently configure the computation it
verifies is the one property no amount of downstream checking repairs. R5E's addition: here that
configuration would also change the *bytes read*, so a transcript could silently change a residency
measurement. The operand is fail-closed; the transcript's `kq-L` `ne0` is instead **validated** to
equal it in every layer, as `R5_ORACLE_SHAPE`.

The summary block is R5A's shape — each label and its value on their own line, read by line ordinal,
printed exactly when a real document path is given:

```text
moe model forward:
status:                OK | ERROR
verdict:               EXTERNAL | COPIED | UNAVAILABLE
pack path:             <sanitized path>
schema:                1
arch:                  olmoe
layers:                <integer>
tokens:                <comma-separated ids>
kv width:              <integer>
experts routed:        <sum of U_L>/<n_layer * n_expert>
expert bytes read:     <integer>
expert bytes in model:  <integer>
dense bytes read:      <integer>
dense window bytes:    <integer>
claim window bytes:    <integer>
claim window peak use: <integer>
residual bytes:        <integer>
activation bytes:      <integer>
graphs:                <integer>
graph nodes:           <integer>
backend:               <name>
pread ns:              <integer>
claim pread ns:        <integer>
compute ns:            <integer>
elapsed ns:            <integer>
logits sha256:         <64 hex characters>
logits bit sum:        <integer>
logits argmax:         <integer>
routing:               MATCH | MISMATCH | -
reference:             IDENTICAL | MISMATCH | -
reference nodes:       <identical>/<compared> | -
transcript:            PASS | FAIL | -
logits oracle:         IDENTICAL | WITHIN | FAIL | -
max abs diff:          <integer>
logit max diff:        <integer>
released:              <integer>
error:                 <code>
detail:                <identifier>
```

`verdict` retains R4.5's meaning and is `EXTERNAL` only when **every** weight tensor of **every**
graph — dense member and expert claim alike — has its data pointer at its own window offset.
`COPIED`, `FAIL`, `MISMATCH`, and `WITHIN` are successful runs; `status: "error"` is reserved for
section 3.9's codes.

### 3.4 Block selection and the per-layer two-phase read schedule

**Thirty-four graphs, thirty-four window fills, and `token_count + 2·n_layer + Σ U_L + 1` `pread`
groups**, into **two** Align-owned buffers — one group per token row of the embedding member and one
per block thereafter. On this model at `T = 6` that is 6 + 32 + 343 + 1 = **382** groups carrying
1,554,531,072 bytes. Section 2.9's probe made 1,181 groups for the same bytes because it read
individual GGUF members and planes rather than pack blocks; the byte totals are identical block for
block — `r1c-olmoe-moe-ir.md` section 2.5.5's `AttentionBlock` 10,543,104 / 9,461,760 plus
`RouterBlock` 532,480 is exactly the probe's 11,075,584 / 9,994,240 per layer, and its `ExpertBlock`
4,079,616 / 3,538,944 is exactly the probe's three plane sizes summed — so only the *count* differs.

Blocks are located by **`(kind, layer, required role_id)`** and never by computed index, per
`r5d-moe-layer-forward.md` section 6 correction C9: an olmoe container carries **two**
`WeightBlock`s at layer `-1` — the embedding at index 0 and the head at index 1,057 — so the
`(kind, layer)` pair alone is ambiguous for both of them. Exactly one block must match; none is
`R5_BLOCK_MISSING` and more than one is `R5_BLOCK_AMBIGUOUS`, each naming the kind, the layer, and
the role. Members are located by `role_id` against `r4-alignpack-layer-major.md` section 2.4.4's
frozen list, never by name and never by position. `r1c-olmoe-moe-ir.md` section 2.5.3's emission
order puts the `AttentionBlock` of layer `L` at `1 + 66L`, the `RouterBlock` at `2 + 66L`, and the
`ExpertBlock` of expert `e` at `3 + 66L + e`; that arithmetic is what the selection is expected to
find, not how it finds it.

**Step 1 — the embedding rows, once.** The `WeightBlock` carrying `role_id` 12, with
`row_bytes = nbytes / n_vocab` required to divide exactly and to be a positive multiple of
`type_size`; one `pread` of `row_bytes` per token at `member.pack_offset + id * row_bytes` into a
`block_align`-padded slot, ids remapped to `0..T-1`. On this model the whole member is 57,950,208 B
and R5E reads **6,912**.

**Step 2 — for each `L` in `0..n_layer-1`, in order, phase A.** The `AttentionBlock` at `L`
(`attn_norm`(0), `attn_q`(1), `attn_q_norm`(27), `attn_k`(3), `attn_k_norm`(28), `attn_v`(5),
`attn_output`(7)) and the `RouterBlock` at `L` (`ffn_norm`(8), `router`(17)), each one `pread` of
`block.pack_bytes` into the reused `dense_window`. On this model 11,075,584 B for the eight layers
whose `attn_v` is Q6_K and 9,994,240 B for the other eight — `r1c-olmoe-moe-ir.md` section 2.5.5's
mixed quantization, which is why the window is a sweep and not a formula.

**Step 3 — between the phases, Align decides**, per layer, on bytes Align owns. In order:

1. Read `ffn_moe_argsort-L` back **whole** with `align_ggml_slot_get`. It is contiguous
   `{n_expert, T_L}` i32. **No view is ever read back**, for `r5d-moe-layer-forward.md` section
   2.8's reason.
2. `topk_ids[t][s] = argsort[t][s]` for `s` in `[0, n_expert_used)`, sliced in Align.
3. Every id must satisfy `0 <= id < n_expert`, and the `n_expert_used` ids of one token must be
   pairwise distinct. → `R5D_EXPERT_ID`, detail `layer[<L>]token[<t>]slot[<s>]`.
4. `routed[]` is the **ascending** distinct union of `topk_ids`, `U_L = routed.len()`, bounded by
   `min(n_expert, n_expert_used * T_L)`.
5. `compact_ids[t][s]` is the position of `topk_ids[t][s]` in `routed[]` — a bijection onto
   `[0, U_L)`, verified rather than assumed. → `R5D_EXPERT_ID`, detail `layer[<L>]remap`.
6. `U_L * (gate_plane + up_plane + down_plane)` must fit the reserved claim window. → the
   fail-closed `R5E_CLAIM_OVERFLOW`, which section 4.5 marks not input-reachable because section
   3.9 step 19 already reserved for the arithmetic bound `U_max`.

**Step 4 — phase B, per layer.** For each `u` in `[0, U_L)` in ascending order, the `ExpertBlock` at
`(ExpertBlock, L, routed[u])` is located and its three claim members — `ffn_gate_exps`(19),
`ffn_up_exps`(21), `ffn_down_exps`(23) — are read with one `pread` of `block.pack_bytes` and
scattered to `gate_region + u * gate_plane`, `up_region + u * up_plane`,
`down_region + u * down_plane` inside the single reused `claim_window`.

**The plane stride is the plane, and the region base is aligned** —
`r5d-moe-layer-forward.md` section 6 correction C3, inherited verbatim and for its reason: a stacked
3-D tensor's planes are contiguous, so `plane_stride == nbytes` for every claim and padding each
plane would make `mul_mat_id` read plane `u` at `u * padded` while the tensor believes it is at
`u * plane`. The three role regions inside the claim window are each `block_align`-aligned; the
planes inside a region are laid end to end.

A block whose expert is `routed[u]` but which is missing one of the three roles, or whose claim's
`slice_index` is not `routed[u]` or whose `slice_count` is not `n_expert`, is `R5D_CLAIM_MISSING`,
detail `layer[<L>]expert[<e>]role[<name>]`. The `slice_index`/`slice_count` pair is validated by
`moe-prereq-discharge.md` section 1.1's steps 7a and 7b and re-raised as `R4_5_SLICE`.

**Step 5 — the head, once.** The `WeightBlock` carrying `role_id` 13 and 14, one `pread`, into the
reused `dense_window`. **Tied embeddings are detected, not assumed**, exactly as
`r5b-model-prefill-forward.md` section 3.4 does: when the head block's `role_id` 14 member names the
same tensor as the embedding block's `role_id` 12 member, `model.output_tied` is `true` and the
head's weight is read into its own window slot from that member's own `pack_offset`. Section 2.1
measured this model as untied.

**Layer coverage is validated before the first read**, and so is expert coverage. Every `L` in
`[0, n_layer)` must have exactly one `AttentionBlock` and one `RouterBlock`, and exactly one
`ExpertBlock` at `(L, e)` for every `e` in `[0, n_expert)` — 1,024 blocks on this model. A gap is
`R5_LAYER_COVERAGE` or `R5D_CLAIM_MISSING` respectively. **Expert coverage is checked before any
routing decision runs**, because discovering a missing expert after the router has chosen it would
make a container defect look like a routing defect.

Each member is copied to a `block_align`-aligned window offset rather than used at its interior
offset, for `r5a-dense-layer-forward.md` section 3.4's reason: every pointer handed to ggml is
`MAX_TENSOR_ALIGNMENT`-aligned by construction.

### 3.5 The two windows, and how they are sized

**Two windows, reserved once each, before anything is read.**

```text
dense_window_bytes = MAX_TENSOR_ALIGNMENT
                   + max over the dense blocks this run will read of
                         Σ align_up(member.nbytes, block_align) over that block's members,
                     where the embedding block contributes align_up(row_bytes * T, block_align)
                       and the attention and router blocks of one layer are summed as a pair

claim_window_bytes = MAX_TENSOR_ALIGNMENT
                   + Σ over the three expert roles of
                         align_up(region_base) + U_max * max over L of plane_bytes(role, L)
                     where U_max = min(n_expert, n_expert_used * token_count)
```

On this model at `T = 6`:

```text
dense_window   84,520,960 B    sized by the head (output_norm 8,192 + output 84,510,720)
                               against 11,075,584 for the largest layer pair and 8,192 for the rows
claim_window  195,821,568 B    U_max = 48; planes 1,179,648 + 1,179,648 + 1,720,320 = 4,079,616
                               observed peak use 101,990,400 B at layer 0, U = 25
peak resident weight bytes    280,342,528 B   against 4,213,512,192 for the model — 6.65%
```

**Both windows are sized by a worst case that the measured run does not reach, and the design
accepts that, stated rather than hidden.**

The dense window is sized by the head at 7.6× the largest layer pair, which costs 73 MB of idle
window during the sixteen layers, for `r5b-model-prefill-forward.md` section 3.5's three reasons
unchanged: a second window is a second lifetime, a second alignment argument, and a second set of
counters for one graph out of thirty-four; the peak is unchanged either way because the head runs
last; and a runtime whose window is sized by the model's largest block is the shape a residency
policy inherits.

The claim window is sized by the **arithmetic** bound `U_max = 48` and not by the **observed**
maximum of 33 (section 2.10), which costs 93.8 MB against the measured prompt's peak use. The
alternative was considered and rejected: sizing per layer after each routing decision means sixteen
reservations, sixteen extra ggml buffer lifetimes, a peak that cannot be checked before the run
begins, and a `MAX_CLAIM_WINDOW_BYTES` guard that fires in the middle of a schedule rather than
before it. A window that is reserved once, checked once, and refilled sixteen times is the same
shape as R5B's, and `claim_window.peak_use_bytes` publishes the slack per run so the trade is a
document field rather than a paragraph. Section 5.4 keeps "a claim window that shrinks to the
decision" as an R6 measurement against these two integers.

`R5_WINDOW_BUDGET` refuses a computed dense window above `MAX_WINDOW_BYTES = 2^33` and
`R5D_CLAIM_BUDGET` refuses a computed claim window above `MAX_CLAIM_WINDOW_BYTES = 2^33`, both
before a single byte is reserved, so a malformed member record cannot ask the process for a
terabyte.

### 3.6 The graph as Align-owned data — four node tables, a condition column, and a `LAYER` operand

`src/layer_olmoe.align` gains a `LAYER` operand, **two new tables** — the embedding graph's and the
head's — and R5B's `node_when` column on the two R5D already owns. R5A's column shape is unchanged:
`node_id`, `node_op`, `node_a`, `node_b`, `node_c`, `node_out`, four shape parameters, a scalar-bits
parameter, `transcript_name`, `oracle`, and `node_when`.

```text
EMBED_TABLE_ROWS   :=  1                       GET_ROWS(token_embd window, inp_tokens)
LAYER_A_TABLE_ROWS := 35                       R5D's 31 rows, minus the GET_ROWS that becomes the
                                               embedding graph, plus 2 narrowing and 3 width rows;
                                               30 of the 35 are unconditional
LAYER_B_TABLE_ROWS := 2 * n_expert_used + 8    R5D's phase-B table, unchanged; 24 at this geometry
HEAD_TABLE_ROWS    :=  3                       RMS_NORM, MUL(output_norm), MUL_MAT(output)
```

Removing the embedding gather from the layer table and making the residual an *input* is
`r5b-model-prefill-forward.md` section 2.4's decision, inherited for its reason: it is what makes all
sixteen phase-A graphs the same table walked sixteen times with different weights, which is the
property a residency policy will need.

**What the `LAYER` operand buys.** R5D's tables name layer 0 as a literal: `transcript_name` is
`"ffn_moe_logits-0"`, the member roles are read at layer 0, and the shape rules assume one token
count. R5E parameterizes all three by `L`:

- `transcript_name(row, L)` renders the suffix, so `norm-L`, `ffn_moe_topk-L`, and the rest are
  derived rather than stored, and the head rows render **no** suffix (section 2.2, consequence 3);
- `expected_dims(role, L, borrow g)` reads the member shapes of layer `L`, so the mixed
  quantization of `r1c-olmoe-moe-ir.md` section 2.5.5 is a per-layer lookup and never a per-role
  constant;
- `T_in(L)` and `T_out(L)` are `token_count` for `L < n_layer - 1` and `token_count` / `1` at the
  last layer, so every shape downstream of the narrowing is derived from the table rather than
  special-cased in the walk.

**The `node_when` column**, an `i64` per row, in `r5b-model-prefill-forward.md` section 3.6's shape:

| `node_when` | The row is issued | Rows |
| --- | --- | --- |
| `0` | always | the 30 unconditional phase-A rows, and every phase-B row |
| `1` | only when `L == n_layer - 1` | `GET_ROWS(attn_out, out_ids)`, `GET_ROWS(cur, out_ids)` |
| `2` | only when `KV_WIDTH > token_count` | `CONT(K permuted)`, `PAD(K)`, `PAD(V)` |

One loop walks the table and skips a row whose condition does not hold. Encoding the narrowing and
the reconciliation as **data** rather than as `if` statements inside the walk is what keeps section
4's "the topology is a table a test can assert on" true; `moe-node-table-shape` gains the assertion
that every `node_when` is one of the three and that the rows reachable at each condition form a
well-ordered graph.

**ggml's node counts are not the table row counts, and both are published**, for
`r5d-moe-layer-forward.md` section 3.7's reason: ggml materializes some rows as nodes and folds
others, and publishing only one of them would make the slot budget unauditable. `table_rows_a` and
`table_rows_b` are the design constants above; `graph.node_count_total` and
`schedule[].node_count_a` / `node_count_b` are ggml's own counts, recorded as goldens at first run.

The probe measured, for a run computing one width:

```text
                       KV_WIDTH == T   KV_WIDTH > T
embedding graph              1               1
layer A, L in 0..14         32              35
layer A, L = 15             34              37
layer B, every L            29              29
head graph                   4               4
whole prefill              983           1,031
```

**The shipped arm's counts will be lower than the probe's, and the reason is a probe artifact rather
than a design difference**: the probe allocated every carried tensor and the residual at the full
`token_count` and took a `{·, T_out}` view of each inside the graph, which materializes extra view
nodes at every layer and in the head. The arm sizes each carried tensor to `T_out(L)` (section 3.10)
and does not. The probe's numbers are recorded here as the probe's; section 5.2 asserts
`table_rows_a` and `table_rows_b` as constants and records `node_count_total` as a golden.

Phase B is width-independent at every layer, which is where the three conditional rows do and do not
land: `+3` per layer at the reconciliation width, `+2` once at the last layer, and nothing in
phase B.

**The residual is an input, not a node**, and so is every value that crosses a phase boundary. Each
layer's phase-A graph takes `cur` — an f32 `{n_embd, T_in}` tensor Align writes with
`align_ggml_slot_set` and reads back with `align_ggml_slot_get` — and each phase-B graph takes
**five** carried inputs:

| Carried input | Shape | Bytes at `T = 6` | Consumer |
| --- | --- | --- | --- |
| `ffn_inp` | f32 `{n_embd, T_out}` | 49,152 | the `l_out` add |
| `ffn_norm` | f32 `{n_embd, T_out}` | 49,152 | the three `mul_mat_id` calls, reshaped to `{n_embd, 1, T}` |
| `ffn_moe_probs` | f32 `{n_expert, T_out}` | 1,536 | `get_rows`, reshaped to `{1, n_expert, T}` |
| `topk_ids` | i32 `{n_expert_used, T_out}` | 192 | **`get_rows` only** — global ids in `[0, n_expert)` |
| `compact_ids` | i32 `{n_expert_used, T_out}` | 192 | **`mul_mat_id` only** — compacted ids in `[0, U_L)` |

**`topk_ids` and `compact_ids` are two tensors and never one**, for section 2.3's reason. Their
ranges are validated separately at section 3.9 step 31 and both are published in the document, so a
reader can re-derive the bijection.

**Scalar ownership** is `r5a-dense-layer-forward.md` section 3.5's, unchanged: every scalar crosses
as an `i32` bit pattern, the mask is written from `0x00000000` and `0xFF800000` with `put_u32_le`,
the five RoPE constants are compiled in behind step 8's validated precondition, and no float crosses
the FFI in either direction. The mask's width is `KV_WIDTH` and its height is `T`.

**No new shim symbol.** R5A shipped twenty-five, R5B added `pad` and `cont_2d`, R5D added `argsort`,
`mul_mat_id`, `view_2d`, `slot_new_tensor_3d`, `slot_new_i32_2d` and widened `soft_max_ext`. R5E's
four tables use only those; the `LAYER` operand and the `node_when` column are Align-side data.
`align_ggml_graph_context_bytes` is called with `MAX_NODE_SLOTS` as R5A does; the largest graph is
phase A at the last layer at the reconciliation width, and the slot high-water is the dense members
plus the inputs plus the nodes, published as `graph.slot_high_water` against a capacity of 128.

### 3.7 The four oracles, and the tolerances fixed before the qualification

**Oracle 1 — bit-exact self-reference.** Present in the seven-, eight-, and nine-operand forms. Per
graph, the same table is built a second time with that graph's weights created in a second context,
allocated by `ggml_backend_alloc_ctx_tensors`, and **filled by copy** from the same Align windows.
Before the first byte is copied, every reference tensor's data offset within the window it is about
to be filled from is asserted to lie **outside** that window — `< 0` or `>= window.len()`, the same
`slot_data_offset` primitive `graph_identity` uses for the opposite conclusion — so the oracle
cannot pass by aliasing: two graphs reading one byte range would agree trivially. A violation is
`R5_REFERENCE_MISMATCH` with detail `aliased[<role>]`. **Every oracle node of every graph must be byte-identical.** Section 2.6 measured 227 of
227 plus the logits. Before each block's graph runs, its members' pack bytes are compared
byte-for-byte against the source GGUF at `member.source_offset` — for dense members and for every
read claim, where `source_offset` is already the claimed absolute offset per
`moe-prereq-discharge.md` section 1.1 — and a difference is `R5_SOURCE_DIVERGED`.

**Oracle 2 — the transcript, across all sixteen layers and the head.** Present in the eight- and
nine-operand forms. Fourteen nodes per layer, plus `embd`, `result_norm`, and `result_output` —
**227 rows**, matched by `(transcript name, declared shape)` and never by `node_NN`:

| `nodes[].id` | transcript name | transcript op | shape |
| --- | --- | --- | --- |
| `embd` | `embd` | `GET_ROWS` | `{n_embd, T}` |
| `attn_norm` | `attn_norm-L` | `MUL` | `{n_embd, T_in}` |
| `ffn_inp` | `ffn_inp-L` | `ADD` | `{n_embd, T_out}` |
| `ffn_norm` | `ffn_norm-L` | `MUL` | `{n_embd, T_out}` |
| `ffn_moe_logits` | `ffn_moe_logits-L` | `MUL_MAT` | `{n_expert, T_out}` |
| `ffn_moe_probs` | `ffn_moe_probs-L` | `SOFT_MAX` | `{n_expert, T_out}` |
| `ffn_moe_argsort` | `ffn_moe_argsort-L` | `ARGSORT` | `{n_expert, T_out}` |
| `ffn_moe_weights` | `ffn_moe_weights-L` | `GET_ROWS` | `{1, n_expert_used, T_out}` |
| `ffn_moe_gate` | `ffn_moe_gate-L` | `MUL_MAT_ID` | `{n_ff_exp, n_expert_used, T_out}` |
| `ffn_moe_up` | `ffn_moe_up-L` | `MUL_MAT_ID` | `{n_ff_exp, n_expert_used, T_out}` |
| `ffn_moe_swiglu` | `ffn_moe_swiglu-L` | `SWIGLU` | `{n_ff_exp, n_expert_used, T_out}` |
| `ffn_moe_down` | `ffn_moe_down-L` | `MUL_MAT_ID` | `{n_embd, n_expert_used, T_out}` |
| `ffn_moe_weighted` | `ffn_moe_weighted-L` | `MUL` | `{n_embd, n_expert_used, T_out}` |
| `ffn_moe_out` | `ffn_moe_out-L` | `ADD` | `{n_embd, T_out}` |
| `l_out` | `l_out-L` | `ADD` | `{n_embd, T_out}` |
| `result_norm` | `result_norm` | `MUL` | `{n_embd, 1}` |
| `result_output` | `result_output` | `MUL_MAT` | `{n_vocab, 1}` |

Four classes are **excluded by contract**, each with its own value in `nodes[].oracle`, so every
exclusion is a field rather than a silent gap:

- `kq-L` and `kq_soft_max-L` — `"shape_incomparable"`, R5A section 3.6's reason: the instrument's
  `n_kv` is a padded cache width and R5E has no cache. Their declared `ne0` **is** validated to equal
  `KV_WIDTH` in every layer, which is the one thing they are good for.
- the `norm-L` nodes — `"ambiguous_name"`. `r5d-moe-layer-forward.md` section 2.2 fact 5's reason,
  plus section 2.2's own finding that at the last layer the same name is printed at two different
  shapes. Each is proved by its unique `MUL` consumer, which **is** compared.
- the `ffn_moe_weighted-L (view)` rows and the intermediate adds of the reduction chain —
  `"unstable_name"`, published as `ffn_moe_weighted-L (view)` and the wildcard `node_*`
  (`r5d-moe-layer-forward.md` section 6 correction C2). `ffn_moe_out-L`, the chain's last add, is
  compared.
- the attention interior — `Qcur`, `Kcur`, `Vcur`, `kqv`, `kqv_out`, and the attention output
  projection — is **compared where R5D compares it and only there**. R5E compares fourteen nodes per
  layer rather than R5D's twenty-six, because the whole-model document is a per-layer schedule and
  not a per-node dump; section 3.8 explains the trade and `oracle.worst_layer` / `worst_node` is what
  localizes a failure. R5D's twenty-six-node coverage of one layer is not withdrawn; it is the
  narrower capability's evidence and it stands.

**The transcript oracle is meaningful only when the run was computed at the instrument's own width,
and on a routed model that is not a preference.** Section 2.8 measured that at the runtime width
twelve of 728 routing slots change, so a run at `KV_WIDTH == token_count` compared against a
transcript the instrument produced at 256 would be comparing a *differently routed* model and would
produce per-layer deltas up to 49,218 ten-thousandths that mean nothing. The arm does not police
this — `KV_WIDTH` is the caller's declaration of what the instrument used, and step 37 validates it
against every `kq-L`'s printed `ne0`, which is exactly the check that catches a caller who declared
the wrong one.

**A node matches when the transcript's declared shape equals the node's computed shape.** A shape
disagreement is `R5_ORACLE_SHAPE`; a named node absent from the transcript, or contributing fewer
elements than its printed shape implies, is `R5_ORACLE_MISSING` — both error codes, and
`r5a-dense-layer-forward.md` section 6 correction C19's element-count rule is inherited verbatim.
At whole-model scale the rule matters sixteen times over: a transcript that lost one layer's value
blocks would otherwise report `PASS` over 15 of 16 layers.

**The thresholds are R5A's, reused unchanged and unwidened, and re-justified against R5E's own
measurement**:

| Comparison | Threshold | R5E's measurement |
| --- | --- | --- |
| element | `\|round(x·10^4) - printed_ten_thousandths\| <= 1` | **0** over 21,372 elements and 227 nodes (section 2.5) |
| sum | `\|Δ\| <= max(1.0e-3, 1.0e-5·\|Σ\|)` in millionths, against a sequential f32 accumulation in element order | **0 of 227 breach it**; worst `\|Δ\|`/tolerance ratio **0.523** at `ffn_moe_gate-8`. Both arms of the rule are load-bearing (section 2.5) |
| integer node (`ffn_moe_argsort`) | **exact**, printed elements and block sum | exact at every layer |

Both float comparisons are integer comparisons and no float is rendered anywhere, for
`r4-alignpack-layer-major.md` section 2.3's reason. An i32 node's elements are parsed with
`r2a-expert-trace.md` section 2.2 finding 5's rule and a violation is `R2_EXPERT_ID_NOT_INTEGRAL`.

**Oracle 3 — routing identity, per layer.** Present in the eight- and nine-operand forms.
`r5d-moe-layer-forward.md` section 3.6's oracle, run sixteen times: the `n_expert_used · T_L` ids
Align sliced out of `ffn_moe_argsort-L` must equal the transcript's `ffn_moe_topk-L` block, every
printed id exactly and the block's exact integer sum. On this model the slot axis is 8 and the
instrument prints six of eight, so at `T = 6`:

```text
layers 0..14   36 of 48 ids printed each     = 540
layer 15        6 of  8 ids printed          =   6      (the narrowing: T_out = 1)
total         546 of 728 ids compared element-wise, and 16 exact block sums
```

The document reports `routing.ids_printed_compared`, `routing.ids_total`, and
`routing.sums_matched` so a reader sees the coverage rather than inferring it. A disagreement is
`routing.verdict: "MISMATCH"` and a **successful run**, with `routing.first_difference_layer`
naming where — and oracle 2 is still evaluated and reported, because a transcript comparison against
a differently-routed layer is exactly the diagnostic a reader needs. This oracle exists because of
the failure class `r5d-moe-layer-forward.md` section 2.8 records and section 2.3 above reproduces at
model scale: a wrong routing produces finite, plausible, wrong numbers and every shape check passes.

**Oracle 4 — the logits.** Present in the nine-operand form. `LOGITS.bin` must be exactly
`n_vocab * 4` bytes (`R5_LOGITS_SHAPE`) and readable (`R5_LOGITS_UNREADABLE`).

| `compared_pass` | Verdict | Threshold | Justification |
| --- | --- | --- | --- |
| reconciliation | `IDENTICAL` | **byte-identical**, all `n_vocab * 4` bytes | Section 2.4 measured byte-identity over 50,304 f32 on **four** prompts and three consecutive runs, `sha256` `a56195da…`. Anything less is a regression, not a tolerance |
| runtime | `WITHIN` | `\|Δ\| <= 5000` ten-thousandths **and** `argmax` equal **and** the top ten equal **as a set** | See below |

**The 5,000 bound is R5B's, reused rather than re-derived, and the reuse is the finding.** Section
2.8 measured 3,086–3,491 ten-thousandths across four prompts — a spread of 13% around a mean of
3,382 — against R5B's measured 2,738 on Qwen2. R5B's bound is 1.8× its measurement and 1.43× R5E's,
and the tighter headroom was accepted rather than widened for three reasons. The bound is not the
acceptance contract: byte-identity at the reconciliation width is, and the runtime verdict is a
characterization of a declared non-goal. The measured spread is narrow and the mechanism is
understood — a 250-column reduction difference plus twelve routing flips. And a shared threshold
that two capabilities have both measured against is worth more than two nearby constants; if a fifth
prompt breaches 5,000, that is a finding to record, not a number to raise.

**R5B's "top ten equal, in order" clause is replaced by set equality, and this is a weakening with a
measurement behind it.** Section 2.8 measured order agreement on 2 of 4 prompts and set agreement on
4 of 4; the failure is ranks 3 and 4 separated by 0.077 against a mean drift of 0.059. Requiring an
order that the declared non-goal demonstrably perturbs would make the runtime verdict fail for a
reason that is not a defect. `oracle_logits.top_k_order_agreement` is published as a number
alongside `top_k_set_agreement` so the property is visible without being a criterion.

**One pass is computed and one verdict is reported.** `oracle_logits.compared_pass` is
`"reconciliation"` when `KV_WIDTH > token_count` and `"runtime"` otherwise, naming the single
schedule the run actually computed; section 5.2 obtains both verdicts by invoking the arm twice with
two widths. On a routed model the two widths read different bytes, so a run that reported both
verdicts would carry two complete schedules and two residency measurements in one document — which
is exactly the ambiguity `residency.*` must not have.

Both are reported as numbers whether they pass or fail:
`oracle_logits.max_abs_diff_ten_thousandths`, `argmax_primary`, `argmax_reference`,
`top_k_set_agreement`, `top_k_order_agreement`.

### 3.8 `R5_MOE_MODEL_FORWARD`, `schema_version: 1`

Canonical UTF-8 JSON in declaration order, in the R0/R1/R2A/R4/R4.5/R5A/R5B/R5D shape.

```text
schema_version    1
kind              "R5_MOE_MODEL_FORWARD"
pack_path, geometry_path, reference_path, transcript_path, logits_path   strings, "" when absent
status            "ok" | "error"
error_code, error_detail                                                 strings, "" when ok
verdict           "EXTERNAL" | "COPIED" | "UNAVAILABLE"

pack        format_version, block_align, member_align, block_count, member_count,
            total_bytes, payload_offset, reader_pread_count, reader_bytes_read
model       arch, n_layer, n_embd, n_head, n_head_kv, head_dim, n_ff_exp, n_vocab,
            n_expert, n_expert_used, context_length, rms_eps_bits, rope_type,
            rope_dim_count, rope_freq_base_bits, attn_scale_bits,
            output_tied (bool), output_ggml_type
selection   token_count, tokens[], embedding_block_index, output_block_index,
            narrow_layer, narrow_index, attention_width, expert_block_count
schedule[]  layer, attention_block_index, router_block_index, dense_bytes,
            attn_v_ggml_type, ffn_down_exps_ggml_type,
            t_in, t_out,
            routed_count, routed[], expert_ids[][], compact_ids[][],
            claim_bytes, claim_block_indices_digest (64 hex), plane_stride_gate,
            plane_stride_up, plane_stride_down,
            pread_ns, claim_pread_ns, decide_ns, compute_a_ns, compute_b_ns,
            node_count_a, node_count_b,
            l_out_sha256 (64 hex), l_out_bit_sum, l_out_f32_sum_millionths,
            l_out_ne0, l_out_ne1, nonfinite_count
residency   expert_bytes_read, expert_bytes_in_model, expert_bytes_read_ppm,
            planes_read, planes_in_model, keys_demanded, keys_distinct,
            dense_bytes_read, head_bytes_read, embedding_bytes_read,
            total_bytes_read, model_bytes, total_bytes_read_ppm,
            cumulative_expert_bytes[]                       # one entry per layer
window      dense_bytes, dense_peak_block_index, dense_peak_block_kind,
            dense_peak_block_layer, dense_peak_block_bytes,
            claim_bytes, claim_u_max, claim_peak_use_bytes, claim_peak_use_layer,
            reuse_count, pointer_identity_failures, member_placements,
            claim_placements, residual_bytes, carried_bytes, logits_bytes
graph       graph_count, node_count_total, embed_node_count, head_node_count,
            table_rows_a, table_rows_b, slot_capacity, slot_high_water,
            activation_bytes_peak, activation_bytes_by_graph[], context_bytes, backend_name
head        output_norm_bytes, output_bytes, pread_ns, compute_ns, node_count,
            result_norm_sha256, result_norm_bit_sum
output      sha256 (64 hex), bit_sum, element_count, nonfinite_count, argmax,
            top_k[] { index, bits }                                       # k = 10
reference   present (bool), verdict, graphs_compared, nodes_compared, nodes_identical,
            first_difference_graph, first_difference_layer, first_difference_node,
            first_difference_index, first_difference_primary_bits,
            first_difference_reference_bits, pread_count, bytes_read
routing_oracle
            present (bool), verdict ("MATCH" | "MISMATCH"), instrument,
            layers_expected, layers_matched, ids_total, ids_printed_compared,
            ids_printed_matched, sums_expected, sums_matched,
            first_difference_layer, first_difference_token, first_difference_slot
oracle      present (bool), verdict, instrument, instrument_kv_width,
            layers_expected, layers_matched, nodes_expected, nodes_matched,
            elements_compared, max_abs_diff_ten_thousandths, max_sum_diff_millionths,
            sums_expected, sums_matched,
            tolerance_ten_thousandths, sum_tolerance_millionths, sum_tolerance_relative_ppm,
            worst_layer, worst_node, worst_element_index,
            transcript_lines, transcript_callback_lines
oracle_logits present (bool), verdict, compared_pass, byte_identical (bool),
            max_abs_diff_ten_thousandths, tolerance_ten_thousandths,
            argmax_primary, argmax_reference, top_k_set_agreement,
            top_k_order_agreement, elements_compared,
            reference_sha256, reference_bit_sum
timings     pread_ns, claim_pread_ns, decide_ns, build_ns, reserve_ns, compute_ns,
            reference_compute_ns, oracle_ns, elapsed_ns
lifetime    ggml_buffers_created, ggml_buffers_freed, contexts_created, contexts_freed,
            backends_created, backends_freed, graphs_created, gallocrs_created,
            gallocrs_freed, released_before_owner_scope_end (bool)
abi         tensor_alignment, table_drift, slot_magic_ok (bool), fp_contract_off (bool),
            graph_context_bytes
```

**`schedule[]` is the capability's real output**, one row per layer rather than one row per node,
for `r5b-model-prefill-forward.md` section 3.8's reason — a whole-model failure is diagnosed by
finding the *first layer* that moved — plus one of R5E's own: **the routing decision is a per-layer
fact and there is no other place to publish it.** `routed[]`, `expert_ids[][]`, and
`compact_ids[][]` per layer are what a residency policy will be designed against, and they are
published **before any oracle runs**, so a reader with no transcript still learns exactly which
experts the tokens reached at every depth. At `n_layer` 16, `n_expert_used` 8 and `T` 6 that is
16 rows of at most 48 + 48 + 48 integers, which is small; a model with 60 layers and 8 experts used
over 6 tokens would still be under 30 KB.

`residency.cumulative_expert_bytes[]` is section 2.9's union curve as a document field, so the
"where does the win come from" question is answered without re-running anything.
`residency.keys_demanded` and `keys_distinct` are **equal** on every prefill — that is section 2.9's
finding, and publishing both is how a future multi-prefill capability will see the moment they stop
being equal. The two are **derived differently**, which is what makes the equality evidence:
`keys_demanded` accumulates each layer's `routing.count`, and `keys_distinct` is the cardinality of
a run-level `(layer, expert)` set built by `merge_keys` (section 6, correction C21).

`oracle.sums_expected` and `sums_matched` publish the second half of oracle 2's evidence.
Every compared node is contracted to carry a printed block sum; a transcript that lost one prints
fewer, and the element comparison alone still reports `PASS`. Without the two counters a
sum that was never compared is indistinguishable from a sum that matched (section 6,
correction C19).

`window.claim_peak_use_bytes` against `window.claim_bytes` publishes section 3.5's over-reservation
per run. `window.reuse_count` is 34 and `window.pointer_identity_failures` is 0 on a healthy run;
the second is what makes `verdict: "EXTERNAL"` a measurement across 195 placements rather than a
claim. Both `verdict` and `reference.verdict` are **conclusions about a completed run**: an error
document carries `verdict: "UNAVAILABLE"` and `reference.verdict: "-"` rather than a judgement
extrapolated from the graphs that happened to run (`r5b-model-prefill-forward.md` section 6,
correction C17).

The reader counters are two independent pairs, for
`r5b-model-prefill-forward.md` section 6 correction C18's reason: `pack.reader_*` is the container's
and is what `timings.pread_ns` and `timings.claim_pread_ns` time; `reference.pread_count` and
`bytes_read` are the source GGUF's, read only by the self-reference oracle's byte-equality
pre-check, and are excluded from both timing fields.

`schema_version` is `1` and nominal; a consumer keys on `kind` plus `schema_version`. Checksums are
never floats: `sha256` is `crypto.sha256` over the exact little-endian bytes, `bit_sum` is the `i64`
sum of the u32 bit patterns, and `f32_sum_millionths` is section 3.7's sequential accumulation
widened to `f64` and rounded (`r5a-dense-layer-forward.md` section 6, correction C10).
`nonfinite_count` is reported and is never a failure condition.

### 3.9 Validation order and error codes

First applicable row wins. Steps 1 and 2 return `Err` with no output at all. Steps 3 onward produce
a `status: "error"` document and then map to `Err(Error.Invalid)`. **No ggml state is created before
step 22, and nothing outside the process is ever written.** Steps 1–21 are therefore fully reachable
under the stub, without ggml, without a model, and without a transcript.

R5E reuses R5A's, R5B's, and R5D's ladders verbatim wherever the check is literally theirs, and owns
an `R5E_` prefix for the faults that are new — the same split `r5c-metal-prefill.md` and
`r5d-moe-layer-forward.md` make.

1. Arm selection and exact arity — five to nine operands. → `R5E_ARITY`
2. Lexical path validation of every path operand; `-` is admitted **only** in positions six and
   eight, with section 3.3's two meanings, and is `R5E_PATH` anywhere else. → `R5E_PATH`
3. `TOKENS` parses: 1–6 non-negative decimal integers, comma-separated, no spaces. → `R5_TOKENS`
4. `KV_WIDTH` parses and is in `[token_count, MAX_ATTENTION_WIDTH]`. → `R5_KV_WIDTH`
5. Geometry document open and read. → `R5_GEOMETRY_UNREADABLE`
6. Geometry parses, `kind == "R1_MODEL_IR"`, `schema_version == 2`. → `R5_GEOMETRY`
7. Every consumed `model` field of section 3.2 present, in range, and — for the two `_bits` fields —
   a finite non-negative pattern with a non-zero `freq_base`. → `R5_GEOMETRY`, detail the field
8. Self-consistency: `n_embd == n_head * head_dim`, `n_head == n_head_kv`, `n_layer >= 1`,
   `n_vocab >= 1`, `n_expert >= 1`, `1 <= n_expert_used <= n_expert`, `n_ff_exp >= 1`, and
   `B_NODE_BASE + b_node_count(n_expert_used) <= MAX_NODE_SLOTS`
   (`r5d-moe-layer-forward.md` section 6 correction C1, inherited verbatim: the ceiling is
   `n_expert_used <= 34`). → `R5_GEOMETRY`, detail the relation
9. Architecture preconditions: `arch == "olmoe"`, `rope.type == 2`, `rope.dim_count == head_dim`,
   `rope.scaling_type == null`. → `R5_GEOMETRY`. **This step earns the five fixed RoPE constants.**
10. Every token id `< n_vocab`. → `R5_TOKENS`
11. Pack open (`fs.open_rw`) and header decode, then region validation. → `R4_PACK_*` verbatim
12. Block selection, role-qualified: exactly one embedding `WeightBlock` carrying `role_id` 12 and
    exactly one head `WeightBlock` carrying `role_id` 13 and 14. → `R5_BLOCK_MISSING` /
    `R5_BLOCK_AMBIGUOUS`, detail `kind[<n>]layer[<n>]role[<name>]`
13. Layer coverage: exactly one `AttentionBlock` and one `RouterBlock` for every `L` in
    `[0, n_layer)`. → `R5_LAYER_COVERAGE`, detail `layer[<n>]`
14. Expert coverage: exactly one `ExpertBlock` at `(L, e)` for every `L` and every `e` in
    `[0, n_expert)`. → `R5D_CLAIM_MISSING`, detail `layer[<n>]expert[<n>]`. **Checked before any
    routing decision runs**
15. Member selection by `role_id` in every dense block. → `R5_MEMBER_MISSING`, detail
    `layer[<n>]role[<name>]`
16. Member shapes against the geometry, each exactly, in every layer; `output` is
    `[n_embd, n_vocab]`, `output_norm` is 1-D at `n_embd`, `router` is `[n_embd, n_expert]`, and
    `row_bytes` divides exactly. → `R5_SHAPE`, detail `layer[<n>]role[<name>]`; a router of the
    wrong width is `R5D_ROUTER_SHAPE`
17. Claim member shapes in every `ExpertBlock` that could be routed: `[n_embd, n_ff_exp]`,
    `[n_embd, n_ff_exp]`, `[n_ff_exp, n_embd]`, each with `slice_index == e` and
    `slice_count == n_expert`. → `R5_SHAPE` / `R4_5_SLICE`
18. Dense window sizing sweep, and `dense_window_bytes <= MAX_WINDOW_BYTES`. → `R5_WINDOW_BUDGET`
19. `U_max = min(n_expert, n_expert_used * token_count)` and the claim window sweep;
    `claim_window_bytes <= MAX_CLAIM_WINDOW_BYTES`. → `R5D_CLAIM_BUDGET`, detail `bytes[<n>]`
20. Window availability: both `buffer(N)` calls published their reserved length.
    → `R4_WINDOW_UNAVAILABLE`
21. Residual, carried-input, and logits buffer sizing, each bounded. → `R5_WINDOW_BUDGET`, detail
    `residual` / `carried` / `logits`
22. `align_ggml_available()`. → `R5_GGML_UNAVAILABLE`, `verdict: "UNAVAILABLE"`. **This is where the
    stub shim stops**
23. `align_ggml_tensor_alignment()` and `align_ggml_table_drift()`. → `R5_ABI`
24. `align_ggml_type_ok(type, ne0)` for every dense member of every block that will be read and for
    the three claim types of every layer, **before the first read**, so a Q6_K `output.weight` or a
    Q4_K `ffn_down_exps` cannot be discovered unsupported after 1.5 GB of I/O.
    → `R5_TYPE_UNSUPPORTED`; `ne0 % blck_size != 0` → `R5_SHAPE`
25. Backend, contexts, slot store, and graph creation; `align_ggml_slots_init`. → `R5_GGML_INIT`
26. The embedding read and graph. → `R4_PACK_UNREADABLE`, then `R5_SLOT` / `R5_ALIGNMENT` /
    `R5_ALLOC` / `R5_COMPUTE`
27. **For each `L` in `0..n_layer-1`, in order**: read the attention and router blocks
    (`R4_PACK_UNREADABLE`); verify every member's window offset is `0 mod tensor_alignment`
    (`R5_ALIGNMENT`, detail `layer[<n>]role[<name>]`); walk the phase-A table (`R5_SLOT`); reserve
    and allocate (`R5_ALLOC`, detail `layer[<n>]reserve_a`/`alloc_a`); compute (`R5_COMPUTE`, detail
    `layer[<n>]status[<n>]`)
28. Read back `ffn_moe_argsort-L` whole and slice the top-k. Every id in `[0, n_expert)`, the
    `n_expert_used` ids of a token pairwise distinct, and the compaction a bijection onto
    `[0, U_L)`. → `R5D_EXPERT_ID`, detail `layer[<L>]token[<t>]slot[<s>]` or `layer[<L>]remap`
29. `U_L * (gate_plane + up_plane + down_plane)` fits the reserved claim window.
    → `R5E_CLAIM_OVERFLOW`, detail `layer[<L>]bytes[<n>]` — a fail-closed guard, not input-reachable
30. Claim selection and reads for `routed[]`, ascending. → `R5D_CLAIM_MISSING` / `R4_5_SLICE` /
    `R4_PACK_UNREADABLE`
31. The five carried inputs: each written at exactly its declared length for this layer's `T_out`,
    and each id table validated against **its own** range — `topk_ids` in `[0, n_expert)` and
    `compact_ids` in `[0, U_L)`. → `R5E_CARRY`, detail `layer[<n>]input[<name>]`
32. Phase-B graph creation, table walk, reserve, allocate, compute, and the `l_out` readback.
    → `R5_GGML_INIT` / `R5_SLOT` / `R5_ALLOC` / `R5_COMPUTE`
33. The residual invariant: the bytes read back are exactly `n_embd * T_out * 4`, and `T_out` is the
    `T_in` the next graph declares. → `R5_RESIDUAL`, detail `layer[<n>]`
34. The head block read and the head graph. → `R4_PACK_UNREADABLE`, then step 27's codes
35. Reference arm (seven-, eight-, nine-operand forms): open the GGUF; read each dense member and
    each read claim at `source_offset` (`R5_SOURCE_UNREADABLE`); compare pack bytes to GGUF bytes
    (`R5_SOURCE_DIVERGED`, detail `layer[<n>]role@<offset>` or `layer[<n>]expert[<e>]role@<offset>`);
    build, compute, and compare every oracle node of every graph bit-exactly
    (`R5_REFERENCE_MISMATCH`, detail `graph[<n>]layer[<n>]node[<id>]@<index>`)
36. *(No second pass.)* **The run computes exactly one schedule, at `KV_WIDTH`.**
    `r5b-model-prefill-forward.md` step 29 runs a second, reconciliation pass because its
    `KV_WIDTH` is optional metadata attached to an oracle. R5E's is the width the run uses, and
    section 2.8 measured that a second pass at a different width would take **different routing
    decisions and read different bytes** — which would make `residency.*` ambiguous about which
    schedule it describes. Section 5.2 obtains both widths' verdicts by invoking the arm twice
37. Transcript arm (eight- and nine-operand forms, unless the transcript operand is `-`): open,
    scan, match every layer.
    → `R5_TRANSCRIPT` / `R5_ORACLE_MISSING` / `R5_ORACLE_SHAPE` / `R2_EXPERT_ID_NOT_INTEGRAL`
38. Transcript arm: routing identity per layer, then section 3.7's thresholds. Neither a routing
    mismatch nor a tolerance breach is an error code; both set a verdict and report numbers
39. Logits arm (nine-operand form): open and size `LOGITS.bin` (`R5_LOGITS_UNREADABLE`,
    `R5_LOGITS_SHAPE`), then compare. A reference element with no ten-thousandths value is a
    malformed input and is refused (`R5_LOGITS_NONFINITE`,
    `r5b-model-prefill-forward.md` section 6 correction C23). A breach of the bound sets
    `oracle_logits.verdict: "FAIL"` and is **not** an error code
40. Teardown in section 3.10's order, then render, then write

| Code | Meaning | Step | Detail |
| --- | --- | --- | --- |
| `R5E_ARITY` | **new.** wrong arm or operand count | 1 | `N/A` — no document exists |
| `R5E_PATH` | **new.** a path operand is empty, too long, or contains NUL | 2 | `N/A` — no document exists |
| `R5E_CARRY` | **new.** a carried phase-A-to-phase-B input has the wrong length, or an id table is out of its own range | 31 | `layer[<n>]input[<name>]` |
| `R5E_CLAIM_OVERFLOW` | **new.** a layer's routed union does not fit the reserved claim window | 29 | `layer[<n>]bytes[<n>]` — fail-closed, not input-reachable |
| `R5_KV_WIDTH` | R5B's, unchanged | 4 | `kv_width[<n>]` |
| `R5_LAYER_COVERAGE` | R5B's, unchanged | 13 | `layer[<n>]` |
| `R5_RESIDUAL` | R5B's, unchanged, now checked sixteen times | 33 | `layer[<n>]` |
| `R5_WINDOW_BUDGET` | R5B's, applied to the dense window and the three activation buffers | 18, 21 | the peak block or the buffer |
| `R5_BLOCK_MISSING`, `R5_BLOCK_AMBIGUOUS` | R5B's, unchanged | 12 | `kind[<n>]layer[<n>]role[<name>]` |
| `R5_LOGITS_UNREADABLE`, `R5_LOGITS_SHAPE`, `R5_LOGITS_NONFINITE` | R5B's, unchanged | 39 | R5B's |
| `R5D_ROUTER_SHAPE` | R5D's, now checked in every layer | 16 | `layer[<n>]ne0[<n>]` / `ne1[<n>]` |
| `R5D_EXPERT_ID` | R5D's, now with a layer in the detail | 28 | `layer[<L>]token[<t>]slot[<s>]` / `layer[<L>]remap` |
| `R5D_CLAIM_BUDGET` | R5D's, now checked once for the whole run at `U_max` | 19 | `bytes[<n>]` |
| `R5D_CLAIM_MISSING` | R5D's, now over `n_layer * n_expert` blocks | 14, 30 | `layer[<n>]expert[<n>][role[<name>]]` |
| `R5_TOKENS`, `R5_GEOMETRY`, `R5_GEOMETRY_UNREADABLE`, `R5_MEMBER_MISSING`, `R5_SHAPE`, `R5_GGML_UNAVAILABLE`, `R5_GGML_INIT`, `R5_ABI`, `R5_TYPE_UNSUPPORTED`, `R5_ALIGNMENT`, `R5_SLOT`, `R5_ALLOC`, `R5_COMPUTE`, `R5_SOURCE_UNREADABLE`, `R5_SOURCE_DIVERGED`, `R5_REFERENCE_MISMATCH`, `R5_TRANSCRIPT`, `R5_ORACLE_MISSING`, `R5_ORACLE_SHAPE` | R5A's, unchanged | as above | R5A's, with a layer prefix where the check is per layer |
| `R4_PACK_UNREADABLE`, `R4_PACK_TRUNCATED`, `R4_PACK_OFFSET`, `R4_WINDOW_UNAVAILABLE`, `R4_5_SLICE` | re-raised verbatim from the container's own contract | 11, 17, 20, 26, 27, 30, 34 | theirs |
| `R2_EXPERT_ID_NOT_INTEGRAL` | an i32 transcript element is not integral | 37 | R2A's |

**The table above is the denominator, and it is exactly thirty-six `R5*` codes** — R5E's four,
R5D's four, and R5A's/R5B's twenty-eight. `R5_INDEX` is **not** among them: an earlier draft of this
row named it and the arm emits it nowhere (section 6, correction C17). The `R4_*` and `R2_*` rows
are inherited contracts owned by `alignpack_read` and R2A; they are counted separately wherever
coverage is reported, because R5E does not own their enumeration. `alignpack_read` declares five
further `R4_PACK_*` codes (`MAGIC`, `VERSION`, `HEADER`, `RESERVED`, `REGION`) that this arm can
also surface from a corrupted container; `alignpack-smoke` owns their coverage.

**Four codes are new, and two of them exist only because the arm computes a whole routed model.**
`R5E_CARRY` is the answer to section 2.3's bug class: five values cross a phase boundary sixteen
times, two of them are id tables whose ranges differ, and a table used against the wrong operand
produces a plausible model. `R5E_CLAIM_OVERFLOW` is the fail-closed complement of step 19's
reservation and is marked not input-reachable rather than fabricated as reachable. `R5E_ARITY` and
`R5E_PATH` are the arm-owned prefix R5C and R5D established.

### 3.10 Ownership, allocation, lifetime, and bounded memory

| Module | Owns | Imports |
| --- | --- | --- |
| `src/alignpack_read.align` | the v1 reader and its `R4_PACK_*` codes | `std.fs` — unchanged by R5E |
| `src/ggml_ffi.align` | the only `extern` and the only `unsafe` in the repository — **unchanged by R5E** | nothing new |
| `src/layer_olmoe.align` | the four node tables, the `node_when` column, the **`LAYER` operand**, the member and claim role tables, the shape rules, the scalar derivations, the routing decision, the oracle tables | `core.json`, `core.math` |
| `src/moe_layer_forward.align` | the R5D arm — **unchanged by R5E** | the three above |
| `src/moe_model_forward.align` | the R5E arm: the schedule, the two windows, the sixteen decisions, the residual carry, the four oracles, the document, the summary block, the teardown | the four above |
| `src/ggml_spike.align` | arm selection and the CLIs | the four arms |

**Weights are Align-owned; the residual stream is Align-owned; the carried phase inputs are
Align-owned; the logits are Align-owned; per-graph activations are ggml-owned.**

- The **dense window** and the **claim window** are two Align `buffer`s, each over-reserved by
  `MAX_TENSOR_ALIGNMENT`, sized by section 3.5's sweeps, and reused 34 times between them. ggml
  holds borrowed pointers into them — 195 placements over the run — each validated to be exactly its
  own window offset, and every ggml buffer wrapping either window is freed before the next block's
  read begins. **A block's bytes are overwritten only after every tensor pointing into them has been
  freed**, which is the invariant the reuse depends on and which the lifetime counters assert:
  `ggml_buffers_created == ggml_buffers_freed` **at every phase boundary**, not only at the end.
- The **residual stream is Align's**, `n_embd * T * 4` bytes, carried between all 34 graphs. ggml
  never sees the same tensor twice, so `gallocr`'s reuse plan reclaims everything the moment a graph
  ends: 34 graphs cost one graph's activations.
- The **five carried inputs are Align's**, re-sized per layer from `T_out(L)`, and the two id tables
  are validated against two different ranges at step 31.
- **Per-graph activations stay ggml-owned**, for `r5a-dense-layer-forward.md` section 3.9's reason;
  `graph.activation_bytes_by_graph[]` publishes the per-graph figure so the choice is visible.
- The **logits buffer** is Align's, `n_vocab * 4` bytes, written once by the head graph's readback.
- The **slot store** is Align's, unchanged from `r5a-dense-layer-forward.md` section 3.5.

**Bounded memory.** Every allocation is a function of the geometry, the token count, and the block
table, computed and checked at steps 18–21 before anything is reserved:

```text
dense window        section 3.5's sweep                             84,520,960 B
claim window        section 3.5's sweep at U_max = 48              195,821,568 B  (peak use 101,990,400)
residual                  n_embd * T * 4                                49,152 B
carried inputs            2*n_embd*T*4 + n_expert*T*4 + 2*n_expert_used*T*4   100,224 B
logits                    n_vocab * 4                                  201,216 B
reference logits          n_vocab * 4                                  201,216 B
node readback       max over graphs of max(node.nbytes)
                      = max(n_embd * n_expert_used * T, n_vocab) * 4  393,216 B
mask image                KV_WIDTH * T * 4                    <=       98,304 B
slot store                16 + 8 * MAX_NODE_SLOTS                       1,040 B
activation          ggml_gallocr_get_buffer_size, reported not chosen
                      peak over 34 graphs                            4,440,064 B
```

Measured peak resident set: **341,639,168 – 343,015,424 B** for the shipped arm over five runs and
440,926,208 B for the self-reference arm, on a 16 GiB host, for a 4,213,512,192-byte model. **The
process never holds more than 8.1% of the model**, and the *weight* windows are 6.65% of it. That is
the sentence stage 3 for a routed model exists to be able to write.

**Teardown order**, extending `r5d-moe-layer-forward.md` section 3.9's contract and asserted by the
lifetime counters. Per layer: gallocr B → graph-B context → claim-window ggml buffer → claim context
→ gallocr A → graph-A context → dense-window ggml buffer → dense context → the reference pair for
each. At the end of the run: input contexts → backend. The two windows, the residual, the carried
inputs, the logits buffer, and the slot store are Align's and drop with their scopes, *after* every
handle that pointed into them has been freed. `released_before_owner_scope_end` remains a document
field. The probe found that omitting `ggml_backend_free` and the input context leaves a process that
segfaults at exit after producing a correct document, which is a reminder that the teardown order is
a contract and not hygiene.

**`ggml_abort` is `abort()`**, and R5E's exposure is **on the order of a thousand nodes** — the
probe's harness built 983 at the runtime width and 1,031 at the reconciliation width — against
R5D's two graphs and R5B's 874. The design does not claim the
boundary is safe; it makes every *reachable* failure unreachable — validated geometry, validated
layer and expert coverage, validated shapes and types before the first read, validated alignments
per member per layer, validated carried lengths and id ranges per layer, validated residual lengths
per layer, bounds-checked slots and copies, null-checked constructors — and says plainly that the
unreachable ones remain, now at model scale.

### 3.11 Ledger dimensions

| Dimension | Answer |
| --- | --- |
| Public surface | `ggml-spike --moe-model-forward`, section 3.3; `R5_MOE_MODEL_FORWARD` v1, section 3.8 |
| Inputs and defaults | Six path operands, two of them mandatory (`PACK`, `GEOM`); one token list; one mandatory width. **No defaults**, and `KV_WIDTH` in particular has none, for section 2.8's reason. No environment input and no build option |
| Results, errors, precedence | Section 3.9, first applicable row wins, total across multi-invalid inputs |
| Ownership, lifetime, allocation, cleanup | Section 3.10; two windows, residual, carried inputs, logits, and slot store Align-owned; per-graph activations ggml-owned with a stated reason |
| Owner module | `src/moe_model_forward.align` owns the arm; `src/layer_olmoe.align` owns the four topologies and the `LAYER` operand; `src/ggml_ffi.align` owns the boundary and is unchanged |
| Persisted identity | `kind` + `schema_version`, nominal. The pack's identity is `r4-alignpack-layer-major.md` section 2.4.6's, unchanged. `sha256` over exact little-endian bytes |
| Validation order | Section 3.9, forty steps; ggml first touched at step 22; all types validated at step 24 before 1.5 GB of I/O |
| Prerequisites | An alignpack v1 pack with claim members; an `R1_MODEL_IR` v2 olmoe document; for the qualification, ggml 0.21, the model, `llama-eval-callback`, and `llama-debug` |
| Acceptance evidence | Section 5.1 owner, section 5.2 qualification, four oracles, tolerances fixed in section 3.7 |
| Metrics | Section 5.3; microbenchmark B at whole routed model scale only |
| Text/wire boundary | UTF-8 JSON, R0's escaping rules, no float rendered anywhere; integer comparisons only |
| Minimum tool/platform versions | ggml 0.21.0, llama.cpp build 10566, Align `3a34febe` (`4b515f8d` at probe time, correction C23); section 5.6 records the version risk |
| Milestones not consuming a later slice | Sections 1.3 and 5.4: no loader, no residency policy, no decode, no KV cache, no GPU, no gpt-oss |
| Runtime-inspection fields | `graph.*`, `schedule[].node_count_*`, `abi.*` — producer-owned counters, no reflection |
| Inapplicable | Concurrency (single-threaded arm, one process) — `N/A`; network — `N/A`, none; schema migration — `N/A`, v1 is the first version |

---

## 4. Closure matrix

Every cell names an implementation owner and the exact regression that covers it. `S` = reachable
with the stub shim and its engine (`make layer-forward-smoke`), `Q` = requires the qualification.

### 4.1 `src/layer_olmoe.align` — four topologies as data, parameterized by `L`

| Cell | Owner | Regression |
| --- | --- | --- |
| Formation — the four tables well-formed | `embed_node_table`, `layer_a_node_table`, `layer_b_node_table`, `head_node_table` | `S` `mm-node-table-shape`: every index in `[0, MAX_NODE_SLOTS)`, every op known, every `node_out` written once per condition, every `node_when` in `{0,1,2}` |
| Formation — the conditional rows form a graph at each condition | the `node_when` walk | `S` `mm-node-when`: for each of the three conditions, every source of an issued row is itself issued |
| Construction — the `LAYER` operand | `transcript_name(row, L)`, `expected_dims(role, L, borrow g)`, `T_in(L)`, `T_out(L)` | `S` `mm-layer-names` asserts the rendered names for `L = 0`, `L = n_layer-1`, and the head's suffix-free rows; `Q` all 227 names matched in the real transcript |
| Success — per-layer mixed quantization | `expected_dims` reads the member record, never a role-to-type map | `S` the synthetic corpus gives layer 1 a different claim type from layer 0; `Q` `schedule[].ffn_down_exps_ggml_type` is 14 for exactly layers 0,1,4,7,10,13,14,15 |
| Success — the last layer's shapes differ | `T_out(n_layer-1) == 1` | `S` `mm-narrow-shapes`; `Q` `schedule[15].t_in == 6`, `t_out == 1`, `routed_count == n_expert_used` |
| Success — the routing decision | `decide_routing(...)` returning owned `routed`, `topk_ids`, `compact_ids` columns | `S` `mm-routing-bijection` re-derives the bijection from the document at every layer; `Q` all sixteen |
| Failure — a missing or inconsistent geometry field | `geometry_fault` | `S` R5D's sixteen `-missing-*` and fifteen precondition rows, re-pointed at the model arm, including C1's `n_expert_used` ceiling |
| Malformed input — an unusable bit pattern | `bits32_finite_nonnegative` | `S` R5A's eight rows |
| Early exit — unsupported arch or rope | step 9 | `S` `mm-geometry-arch`, `mm-geometry-rope-scaled` |
| Scalars — mask at two widths, attention scale | `mask_image(width, height)`, `attn_scale_bits` | `S` `mm-mask-image` at `{3,3}` and `{8,3}` against checked-in goldens |
| Cleanup | no handle, no file, no `unsafe` | `S` the `unsafe`/`extern` scan names only `src/ggml_ffi.align` |

### 4.2 `src/ggml_ffi.align` and the two C files — the no-change claim

| Cell | Owner | Regression |
| --- | --- | --- |
| Construction — every op R5E needs already exists | R5A's 25 + R5B's 2 + R5D's 5 and one widened | `S` `mm-shim-no-new-symbols`: the shared contract region is byte-identical to R5D's head, and the arm's op set is a subset of the declared symbols |
| Success — status mapping | `r5_code_for` extended with the four new codes | `S` `mm-status-map`: every negative shim status maps to exactly one `R5*` code, none unmapped |
| The two C files agree | the shared-contract marker block | `S` byte-identity assertion, unchanged |
| No `malloc` | neither file allocates | `S` `grep -c malloc scripts/ggml_shim*.c` is `0`, unchanged |
| Contraction off | `#pragma STDC FP_CONTRACT OFF` plus `-ffp-contract=off` | `S` `abi.fp_contract_off` asserted `true` on every document |
| Malformed input — slots | bounds-checked as R5A | `S` `mm-force-slot-range`, `mm-force-slot-empty` |
| Cleanup — per graph | `stage_teardown_graph`, total against null | `S` `mm-teardown-partial`: a failure at layer 1's phase B still runs the full teardown and the counters balance |

**If this section is refuted — if the arm needs a symbol — that is a boundary change and belongs in
a section 6 correction, not a quiet edit here.**

### 4.3 `src/moe_model_forward.align` — the arm

| Cell | Owner | Regression |
| --- | --- | --- |
| Formation — arm selection | first operand, before path work | `S` `mm-arm-unknown-flag`, and `arm-r5d-unchanged` asserting `--moe-layer-forward` still emits `R5_MOE_LAYER_FORWARD` and `arm-r5b-unchanged` for `--model-forward` |
| Formation — arity, five to nine | `parse_operands` | `S` `mm-arity-four`, `mm-arity-ten` → `R5E_ARITY`, no document, non-zero exit |
| Formation — role-qualified block selection | `find_block_with_role` (`r5d-moe-layer-forward.md` C9's shape) | `S` `mm-block-ambiguous` (two blocks carrying `role_id` 12) → `R5_BLOCK_AMBIGUOUS`; `Q` `embedding_block_index == 0`, `output_block_index == 1057` |
| Formation — layer and expert coverage | `validate_coverage` | `S` `mm-coverage-gap-router` → `R5_LAYER_COVERAGE` detail `layer[1]`; `mm-coverage-gap-expert` → `R5D_CLAIM_MISSING` detail `layer[1]expert[5]`; `Q` `expert_block_count == 1024` |
| Construction — dense window sizing | `size_dense_window` | `S` `window.dense_peak_block_kind` is layer 0's `AttentionBlock` on the synthetic model (correction C8); `mm-dense-nbytes-huge` (a dense member record declaring 2^40 bytes) is refused by the container as `R4_PACK_OFFSET` **before** the sweep runs, which is why `R5_WINDOW_BUDGET` is a fail-closed guard (correction C17); `Q` `dense_bytes == 84520960`, `dense_peak_block_layer == -1` |
| Construction — claim window sizing at `U_max` | `size_claim_window` | `S` every successful case asserts `claim_u_max == min(n_expert, n_expert_used*T) == 8` and `claim_bytes == 12288`; `mm-claim-nbytes-huge` is `R4_PACK_OFFSET` for the same reason as the row above (correction C17); `Q` `claim_bytes == 195821568`, `claim_u_max == 48`, `claim_peak_use_bytes == 101990400`, `claim_peak_use_layer == 0` |
| Construction — the read schedule | `stage_read_block` | `S` `schedule[].pread` counts are 1 per dense block and `U_L` per layer's claims; `Q` 381 `pread` groups, `total_bytes_read == 1554531072` |
| Success — the residual carry | `carry_residual` | `S` `mm-residual` asserts `schedule[L].l_out_ne1` is `T` for `L < n_layer-1` and `1` at the last; `mm-force-residual-short` → `R5_RESIDUAL` detail `layer[<n>]` |
| Success — the five carried inputs and two id ranges | `carry_phase_inputs` | `S` `mm-carry-length` (a forced short write) and `mm-carry-global-id` (a `topk_ids` entry `>= n_expert`) and `mm-carry-compact-id` (a `compact_ids` entry `>= U_L`) → `R5E_CARRY` with the exact `input[<name>]`; `Q` `window.carried_bytes == 100224` |
| Success — global ids feed `get_rows`, compact ids feed `mul_mat_id` | the two table rows in `layer_b_node_table` | `S` `mm-id-table-swap`: a forced build that passes `compact_ids` to `get_rows` fails the transcript oracle at `ffn_moe_weights` on **every** layer while `ffn_moe_gate` still passes — the exact signature of section 2.3's bug |
| Success — the narrowing | the two `node_when == 1` rows | `S` the synthetic model's golden document; `Q` `selection.narrow_layer == 15`, `narrow_index == 5` |
| Success — the head | `head_node_table`, `stage_head` | `S` golden `output.element_count == 32`; `Q` `== 50304`, `head.output_bytes == 84510720` |
| Success — window reuse is safe | every buffer freed before the next read | `S` `lifetime.ggml_buffers_created == ggml_buffers_freed` asserted **per phase**, not only at the end; `mm-force-buffer-leak` fails that assertion |
| Success — the residency accounting | `accumulate_residency` | `S` `residency.keys_demanded == keys_distinct` asserted on every successful case, and `cumulative_expert_bytes[n_layer-1] == expert_bytes_read`; `Q` `expert_bytes_read == 1301446656`, `expert_bytes_in_model == 3900702720`, `expert_bytes_read_ppm == 333644`, `planes_read == 1029` |
| Failure — each error code | `stage_*` | section 4.5 |
| Early exit — `-` document destination | `run` | `S` `mm-doc-stdout-identical` |
| Return — exit mapping | R0's, verbatim | `S` `mm-exit-codes` |
| Cleanup | section 3.10's order | `S` `mm-teardown-partial`; `Q` counters balance and `released_before_owner_scope_end` is `true` |

### 4.4 The four oracles

| Cell | Owner | Regression |
| --- | --- | --- |
| Reference — bytes equal, per block and per claim | `compare_source` | `S` `mm-source-diverged-claim` at layer 1 expert 3 → `R5_SOURCE_DIVERGED` with `layer[1]expert[3]…`; `Q` every dense member and all 343 read claims equal |
| Reference — nodes identical, per graph | `stage_reference_graph` | `S` all nodes of all synthetic graphs; `mm-force-reference` names `graph[<n>]layer[<n>]node[<id>]@<index>`; `Q` **227 of 227** plus byte-identical logits |
| Transcript — grammar | `scan_transcript` | `S` `mm-transcript-garbage` → `R5_TRANSCRIPT` |
| Transcript — every layer matched | `layers_matched` | `S` `mm-transcript-missing-layer` (layer 1's records deleted) → `R5_ORACLE_MISSING` detail `layer[1]node[l_out]`; `Q` `layers_matched == 16` |
| Transcript — matched by `(name, shape)` and not by name | `match_node` | `S` `mm-transcript-norm-ambiguous`: a transcript whose two `norm-L` records are reordered still matches, because neither is sought and each consumer is; `Q` the real transcript's duplicate `norm-15` at two shapes |
| Transcript — the element-count rule | R5A correction C19's rule, per node per layer | `S` `mm-transcript-headers`, `mm-transcript-novalues`; `Q` `elements_compared == 21372` |
| Transcript — `kq-L` `ne0` against `KV_WIDTH`, every layer | step 37 | `S` `mm-transcript-kv-width` (a transcript whose `kq-1` is `{8,…}` against `KV_WIDTH` 16) → `R5_ORACLE_SHAPE` detail `layer[1]` |
| Transcript — excluded classes are fields | `nodes[].oracle` | `S` the exact sets asserted: `shape_incomparable` is `kq` and `kq_soft_max` in every layer, `ambiguous_name` is the `norm-L` rows, `unstable_name` is the reduction chain |
| Transcript — a tolerance breach | step 38 | `S` `mm-transcript-perturbed`: one printed value at layer 9 moved by `0.0003` → `verdict: "FAIL"`, `worst_layer: 9`, `status: "ok"`, routing still `MATCH` |
| Transcript — an exact pass | step 38 | `S` `max_abs_diff_ten_thousandths == 0`; `Q` `== 0` over 21,372 elements and `max_sum_diff_millionths` within the rule |
| Transcript — a sum that was never compared is visible | `compare_transcript_sum` | `S` `mm-engine-transcript` asserts `sums_expected == sums_matched == 31`; `mm-transcript-nosums` (every `sum =` line but the file's last removed) is `status: ok`, `verdict: PASS`, `sums_expected 31`, `sums_matched 1`; `Q` `227` and `227` |
| Reference — the second arm does not alias the window | `outside_window` in `reference_weights` and `reference_claims` | `S` every `mm-engine-reference` placement passes the offset assertion before a byte is copied, and `reference.verdict` is `IDENTICAL`; `Q` 227 of 227 over 34 graphs |
| Routing — success, per layer | `compare_routing` | `S` `mm-engine-transcript` → `MATCH` at both synthetic layers with **full** element-wise coverage at `n_expert_used = 3`; `Q` `MATCH`, `layers_matched == 16`, `ids_printed_compared == 546`, `ids_total == 728`, `sums_matched == 16` |
| Routing — failure is data, not an error | `compare_routing` | `S` `mm-routing-mismatch` → `MISMATCH` on a **successful** run with `first_difference_layer` set and oracle 2 still evaluated |
| Routing — a wrong id is refused before it is used | step 28 | `S` `mm-force-routing-id-range`, `mm-force-routing-repeat`, `mm-force-routing-remap` → `R5D_EXPERT_ID` with the exact `layer[<L>]token[<t>]slot[<s>]` |
| Logits — file shape | step 39 | `S` `mm-logits-short` → `R5_LOGITS_SHAPE`, `mm-logits-missing` → `R5_LOGITS_UNREADABLE` |
| Logits — an unrepresentable reference element | step 39 | `S` `mm-logits-nonfinite`, `mm-logits-nan` → `R5_LOGITS_NONFINITE` detail `elements[1]`; `mm-logits-huge` → `status: "ok"`, `verdict: "FAIL"` |
| Logits — byte-identical at the reconciliation width | `compare_logits` | `S` the synthetic model's synthetic logits blob → `IDENTICAL`; `Q` `byte_identical: true`, `reference_sha256 == a56195da…` |
| Logits — the runtime width verdict | `compare_logits` | `S` `mm-logits-runtime-width` asserts `WITHIN` with argmax equal and the top-ten **set** equal; `Q` `max_abs_diff_ten_thousandths <= 5000` with **3,477** recorded, `argmax_primary == argmax_reference == 2262`, `top_k_set_agreement == 10` |
| Logits — a real failure is not `WITHIN` | `compare_logits` | `S` `mm-logits-perturbed`: a reference blob shifted by 1.0 → `verdict: "FAIL"` with the argmax still equal, so the tolerance alone cannot pass it |
| Logits — the order clause is reported, not required | `compare_logits` | `S` `mm-logits-order-swap`: a reference blob with ranks 3 and 4 swapped → `WITHIN` with `top_k_order_agreement < 10` and `top_k_set_agreement == 10` |
| Tolerances not silently widened | four document fields | `S` goldens assert `1`, `1000`, `10`, and `5000`; a change is a diff in four places |

### 4.5 Error-code-to-fixture map

| Code | Stub-reachable | Fixture |
| --- | --- | --- |
| `R5E_ARITY` | yes | four and ten operands, and one unknown flag |
| `R5E_PATH` | yes | empty, 4097 bytes, embedded NUL, on each of six path operands; a non-UTF-8 operand (section 6, correction C18); and `-` in the pack, geometry, reference, and logits positions |
| `R5E_CARRY` | yes | forced short write; a `topk_ids` entry `== n_expert`; a `compact_ids` entry `== U_L` |
| `R5E_CLAIM_OVERFLOW` | **no — not input-reachable** | `N/A`: step 19 reserves for `U_max = min(n_expert, n_expert_used·T)`, which no routing decision can exceed. Marked as fail-closed defence, in the shape `r5b-model-prefill-forward.md` section 4.5 uses for `R4_WINDOW_UNAVAILABLE` |
| `R5_TOKENS` | yes | ``, `1,`, `1, 2`, seven ids, an id `== n_vocab` |
| `R5_KV_WIDTH` | yes | ``, `-1`, `+8`, `2` (below the token count), `4097` |
| `R5_GEOMETRY_UNREADABLE`, `R5_GEOMETRY` | yes | R5D's thirty-one rows, re-pointed, plus the C1 `n_expert_used` ceiling |
| `R4_PACK_UNREADABLE`, `R4_PACK_TRUNCATED`, `R4_PACK_OFFSET` | yes | an absent pack; a pack cut short by 64 bytes; the two 2^40-byte member records above. `alignpack_read`'s other five `R4_PACK_*` codes are `alignpack-smoke`'s coverage, not this block's |
| `R5_BLOCK_MISSING`, `R5_BLOCK_AMBIGUOUS` | yes | a pack with no head `WeightBlock`; a pack with two blocks carrying `role_id` 12 |
| `R5_LAYER_COVERAGE` | yes | a pack whose layer 1 has no `RouterBlock` |
| `R5D_CLAIM_MISSING` | yes | a pack missing `(layer 1, expert 5)`; and one whose claim `slice_index` is not its expert |
| `R5_MEMBER_MISSING`, `R5_SHAPE`, `R5D_ROUTER_SHAPE` | yes | an omitted `attn_q_norm`; an `output` whose `ne1` is not `n_vocab`; a router that is `[n_embd, n_expert+1]` |
| `R4_5_SLICE` | yes | both admitted `slice` pairs plus one malformed |
| `R5_WINDOW_BUDGET`, `R5D_CLAIM_BUDGET` | **no — not input-reachable** (section 6, correction C17) | `mm-dense-nbytes-huge` and `mm-claim-nbytes-huge` are the promised 2^40-byte member records, and they reach `R4_PACK_OFFSET` instead: the container refuses a member whose byte span leaves its block, and refuses a container whose `total_bytes` is not the file's own length, so no pack under the 8 GiB budget can make either window exceed it. The two cases are kept as the regression on that **ordering** |
| `R4_WINDOW_UNAVAILABLE` | no — not input-reachable | `N/A`, as R5A, R5B and Request 35 record |
| `R4_PACK_UNREADABLE` | yes | a pack truncated inside layer 1's expert 3 |
| `R5_GGML_UNAVAILABLE` | yes | the default stub — the whole owner test's baseline |
| `R5_ABI` | no | `Q`, and only if the linked ggml drifts |
| `R5_TYPE_UNSUPPORTED` | yes | an `output` member carrying ggml type `4`; a claim carrying an unsupported type |
| `R5_ALIGNMENT` | yes | a synthetic pack whose `block_align` is `1` |
| `R5_GGML_INIT`, `R5_SLOT`, `R5_ALLOC`, `R5_COMPUTE` | yes | `ALIGN_GGML_FORCE_*` at layer 9's phase B, detail `layer[9]` |
| `R5D_EXPERT_ID` | yes | forced out-of-range, repeated, and non-bijective decisions at layer 1 |
| `R5_RESIDUAL` | yes | a forced build whose readback is short by four bytes at layer 9 |
| `R5_SOURCE_UNREADABLE`, `R5_SOURCE_DIVERGED` | yes | a one-byte `REF.gguf`; a pack and GGUF disagreeing in one byte of layer 1 expert 3 |
| `R5_REFERENCE_MISMATCH` | yes | `ALIGN_GGML_FORCE_REFERENCE_PERTURBATION` |
| `R5_TRANSCRIPT`, `R5_ORACLE_MISSING`, `R5_ORACLE_SHAPE` | yes | random bytes; a deleted layer; a headers-only transcript; a `kq-1` declaring the wrong `ne0` |
| `R2_EXPERT_ID_NOT_INTEGRAL` | yes | an `ffn_moe_argsort-1` element printed as `3.5000` |
| `R5_LOGITS_UNREADABLE`, `R5_LOGITS_SHAPE`, `R5_LOGITS_NONFINITE` | yes | a missing path; a 4-byte blob; an `-inf` and a NaN |

**Every new code except `R5E_CLAIM_OVERFLOW` is stub-reachable**, and that one is marked
not-reachable with the arithmetic that makes it so rather than being given a fabricated fixture. The
final matrix-to-diff pass maps every cell above to its implementing function and its passing
evidence, or to an explicit deferral in this document, before review.

**Four of the thirty-six declared `R5*` codes are not reached by the fifth block**, and each names
the reason above rather than being counted as covered: `R5_ABI` (`Q` only, and only if the linked
ggml drifts), `R5E_CLAIM_OVERFLOW`, `R5_WINDOW_BUDGET`, and `R5D_CLAIM_BUDGET`. The last three are
fail-closed guards on arithmetic no input can produce. Section 7.5 reports **32 of 36**, and
`scripts/run-layer-forward-smoke`'s fifth block owns the same two sets as executable data, asserted
in both directions so a code that stops being reached and a code reached outside the declaration are
both failures.

---

## 5. Fixtures, qualification, metrics, deferrals, risks, and candidate requests

### 5.1 Owner — a fifth block in `scripts/run-layer-forward-smoke`

**R5E adds no Makefile check target and changes no aggregate membership.** `layer-forward-smoke` is
already a member of `HOSTED_CHECK_TARGETS`, and `r5b-model-prefill-forward.md`,
`r5c-metal-prefill.md`, and `r5d-moe-layer-forward.md` each extended that one script with a new
block for exactly this reason. A new `moe-model-forward-smoke` target would change
`HOSTED_CHECK_TARGETS`, which `docs/specs/check-gate-topology.md` and the `Makefile`'s own comment
record as a check-topology change that selects `make ci` for publication. R5E's fifth block keeps the
topology fixed.

That is the whole of the claim and it is narrower than it sounds: adding the
`moe-model-forward-qualification` recipe and its `.PHONY` entry edits the `Makefile`, which is an
executable contract boundary, so `scripts/verification_scope.py` is what selects the publication
lane and this paragraph is not. What R5E inherits is a scope *selection*, not an exemption.

The block follows the existing four: `build_shim("engine")` for the forced-failure loop, then
`build_shim(None)` to restore, with the `cleanup` trap rebuilding the default shim. Goldens live in
`scripts/moe-model-forward-golden.jsonl`, refreshed by
`ALIGN_LLM_MOE_MODEL_FORWARD_GOLDEN_UPDATE=1`.

**A synthetic two-layer OLMoE *model*, so the whole prefill is hand-checkable.**
`scripts/layer_forward_fixture.py` already gained `--moe` for R5D; R5E adds `--moe --model`,
extending R5D's `GEOMETRY_MOE` with a head and a second layer's worth of everything:

```text
GEOMETRY_MOE_MODEL = {"arch": "olmoe", "n_layer": 2, "n_embd": 8, "n_head": 2, "n_head_kv": 2,
                      "head_dim": 4, "n_ff_exp": 16, "n_vocab": 32,
                      "n_expert": 8, "n_expert_used": 3, "context_length": 512}
TOKENS_MOE_MODEL   = [3, 17, 5]        KV_WIDTH = 8   (so the `node_when == 2` rows are exercised)
```

**Twenty-two blocks** — one embedding `WeightBlock`, then per layer an `AttentionBlock`, a
`RouterBlock`, and eight `ExpertBlock`s with `slice_index` `0..7` and `slice_count` 8, then the head
`WeightBlock` — in `r1c-olmoe-moe-ir.md` section 2.5.3's order, so `R4_5_SLICE`'s two admitted pairs
are both exercised. Every member is `TYPE_F32`, which
keeps the fixture readable and keeps `align_ggml_type_ok` on its F32 row; the quantized types and the
mixed-quant pattern are the real model's job, and section 5.6 says so rather than implying coverage.
**Six graphs** — one embedding, two layers of two, and the head — with the narrowing at layer 1 and
the `node_when == 2` width rows at both layers.

The expected numbers come from the script's **pure-Python forward pass**, importing only `json`,
`math`, `os`, `struct`, and `sys` (`r5a-dense-layer-forward.md` section 6, correction C24), extended
to run the whole routed model including both routing decisions, the narrowing, and the head, and to
write the `32 * 4`-byte logits blob the logits oracle compares against. **A second implementation
computing the same routed model is what makes the `IDENTICAL` logits verdict stub-reachable at all**,
and it is also what makes `mm-id-table-swap` a real test rather than a shape check: the Python
reference gathers probabilities by global id, so a swapped table produces a document that differs
from the golden at `ffn_moe_weights` in both layers.

At `n_expert_used = 3` the router's slot axis is 3, which is `<= 6`, so the synthetic corpus is the
**only** place the routing oracle's *full* element-wise print coverage is reachable — section 4.4's
`mm-engine-transcript` case, inherited from `r5d-moe-layer-forward.md` section 5.1.

The synthetic geometry keeps `n_vocab` (32) distinct from `n_ff_exp` (16), from `n_expert` (8), and
from `n_head · head_dim` (8) so a fixture whose dimensions collide cannot hide a transposed head or
a confused expert axis.

**A checked-in real-model transcript excerpt**, `eval/fixtures/olmoe-model-6tok.txt`: `embd`, `kq-0`,
the sixteen `l_out-L` records, layer 15's attention output projection `node_977`, `node_978`,
`node_979`, `ffn_inp-15`, `ffn_moe_topk-15`, `result_norm`, and `result_output`. It is swept from
the qualification by `scripts/sweep-moe-model-forward-excerpt.py`, which matches the attention output
projection by its source weight name and never by `node_NN`
(`r5a-dense-layer-forward.md` section 6, correction C21). It is compared hosted for **grammar, node
identity, and layer coverage only**; its numbers are the qualification's, so a stale excerpt cannot
produce a false `PASS`.

Every fixture's expected document is a checked-in golden compared **byte for byte** after timing
normalisation, and R5B's per-layer lifetime assertion is inherited and tightened: **`lifetime.*` is
asserted balanced at every *phase* boundary**, not every layer boundary, because R5E has two graphs
and two windows per layer and a leak in one is invisible to a check on the other.

The smoke writes into a `mktemp -d` tree outside the work tree and removes it on every exit path,
with R5A correction C22's shim-restoring trap. The block never skips: it is ggml-free, model-free,
and network-free, exactly as the four blocks before it.

**Budget, measured rather than assumed.** `gmake layer-forward-smoke` is **32.199 s** today for four
blocks, 34 no-document and 239 documented cases, with `gmake build` contributing 0.34 s (cached), so
essentially all of it is the script. The four blocks are close in size, so the marginal cost of a
fifth of comparable case count is **8–11 s**, projecting **40–43 s**.

**The ceiling is 60 s and the decision if it is exceeded is pre-committed here rather than left to
the moment.** If the fifth block pushes `layer-forward-smoke` past ~60 s, the target splits along the
**dense/routed** boundary — `layer-forward-smoke` keeping R5A/R5B/R5C's three blocks and a new
`moe-forward-smoke` taking R5D's and R5E's two — and **the topology change is accepted**: both
targets join `HOSTED_CHECK_TARGETS`, `docs/specs/check-gate-topology.md` is updated, and publication
selects `make ci`. That is the right split because it is the one boundary along which the two halves
share no fixture generator mode, no golden file, and no shim build, so neither half pays for the
other's cases. Splitting to avoid a `make ci` run would be the schedule driving the contract; the
projection says it should not be necessary, and the measurement at implementation time is what
decides.

### 5.2 Named qualification — `make moe-model-forward-qualification`, `scripts/run-moe-model-forward`

Opt-in and capable-only, in **neither** `HOSTED_CHECK_TARGETS` nor `CAPABLE_ONLY_CHECK_TARGETS` and
in no aggregate, exactly as `layer-forward-qualification`, `model-forward-qualification`, and
`moe-layer-forward-qualification` are not. The Makefile target is
`moe-model-forward-qualification: build ; ./scripts/run-moe-model-forward`.

It prints one explicit `N/A` line naming the missing input and exits `0` when any of

```text
ALIGN_LLM_GGML_INCLUDE                ggml headers
ALIGN_LLM_GGML_LIB                    ggml libraries
ALIGN_LLM_GGUF_MODEL                  the OLMoE GGUF
ALIGN_LLM_LLAMA_EVAL_CALLBACK         path to llama-eval-callback
ALIGN_LLM_LLAMA_DEBUG                 path to llama-debug
```

is unset, or the model or either instrument is absent, or `ALIGN_LLM_GGUF_MODEL` is not an olmoe
model, or free space under the scratch root is under the pack's size plus 1 GiB —
`need_kib=$(( model_bytes / 1024 + 1048576 ))`, which is **5,163,334 KiB** for this model.

`ALIGN_LLM_MOE_MODEL_FORWARD_TMPDIR` is **not** in that list. It chooses where the pack is written
and defaults to `TMPDIR`, so it is never an N/A condition; an earlier draft listed it among the
required inputs and the runner never treated it as one.

Otherwise it packs the model, emits the geometry, captures **both** instrument outputs with the
**exact same** flag set section 2.1 established, and runs the arm **twice**:

```text
main --pack     $MODEL $W/model.alignpack $W/pack.json
main --model-ir $MODEL $W/geometry.json
FLAGS='-p "def add(a, b" -n 1 -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512'
$ALIGN_LLM_LLAMA_EVAL_CALLBACK -m $MODEL $FLAGS > $W/transcript.txt 2> $W/log.txt
$ALIGN_LLM_LLAMA_DEBUG         -m $MODEL $FLAGS --save-logits --logits-output-dir $W/lg
./ggml-spike --moe-model-forward $W/model.alignpack $W/geometry.json 1545,823,9,66,13,270 256 \
    $W/recon.json $ALIGN_LLM_GGUF_MODEL $W/transcript.txt $W/lg/llamacpp-OLMoE-...-Q4_K_M.bin
./ggml-spike --moe-model-forward $W/model.alignpack $W/geometry.json 1545,823,9,66,13,270 6 \
    $W/runtime.json $ALIGN_LLM_GGUF_MODEL - $W/lg/llamacpp-OLMoE-...-Q4_K_M.bin
```

The runner asserts the tokenizer produced exactly those six ids before invoking the arm, so a
tokenizer change is a named failure rather than a silent seven-token refusal; and it asserts the two
instruments agree — the f32 sequential sum of the logits file equals the `sum` the transcript prints
for `result_output`, and `llama-debug`'s `-tokens.bin` equals the six ids — **before** running the
arm, so an instrument skew is reported as an instrument skew and not as a failing oracle.

**The second invocation passes `-` in the transcript position**, deliberately and structurally.
Section 2.8 established that a transcript captured at width 256 describes a differently-routed model
from a run at width 6; step 37's `kq-L` `ne0` validation would refuse the pair as `R5_ORACLE_SHAPE`,
which is the design working rather than an inconvenience. The `-` form is what lets the **arm**, not
the runner, produce the runtime-width `WITHIN` verdict against the same reference logits file.

Asserted from the emitted documents, against section 2's recorded values:

| Field | Expected |
| --- | --- |
| `status`, `verdict` | `ok`, `EXTERNAL` |
| `model.*` | `olmoe`, 16, 2048, 16, 16, 128, 1024, 50304, 64, 8, 4096, `3727c5ac`, 2, 128, `461c4000`, `3db504f3`, `output_tied: false`, `output_ggml_type: 14` |
| `selection.embedding_block_index`, `output_block_index`, `expert_block_count` | `0`, `1057`, `1024` |
| `selection.narrow_layer`, `narrow_index`, `attention_width` | `15`, `5`, `256` (and `6` on the second invocation) |
| `schedule[]` length; `schedule[15].t_in`, `t_out`, `routed_count` | `16`; `6`, `1`, `8` |
| `schedule[L].routed_count` | `25,22,28,25,23,23,24,21,22,20,21,21,18,20,22,8` |
| `schedule[0].routed` | `0,4,6,7,13,14,15,16,21,32,33,35,36,38,39,40,43,48,51,53,54,55,57,59,61` |
| `schedule[L].ffn_down_exps_ggml_type == 14` | for exactly layers 0,1,4,7,10,13,14,15 |
| `schedule[L].dense_bytes` | `11075584` for those eight layers, `9994240` for the other eight |
| `residency.expert_bytes_read` / `expert_bytes_in_model` / `_ppm` | `1301446656` / `3900702720` / `333644` |
| `residency.keys_demanded`, `keys_distinct`, `planes_read`, `planes_in_model` | `343`, `343`, `1029`, `3072` |
| `residency.total_bytes_read`, `model_bytes` | `1554531072`; `model_bytes` is **superseded by correction C2** — it is the container's `pack.total_bytes` (`4212193280`), and the runner asserts that equality rather than the file size `4213512192` |
| `residency.cumulative_expert_bytes[15]` | `1301446656`, and `[0] == 101990400` |
| `window.dense_bytes`, `dense_peak_block_layer` | `84520960`, `-1` |
| `window.claim_bytes`, `claim_u_max`, `claim_peak_use_bytes`, `claim_peak_use_layer` | `195821568`, `48`, `101990400`, `0` |
| `window.reuse_count`, `pointer_identity_failures`, `member_placements`, `claim_placements` | `34`, `0`, `147`, `48` — 1 embedding + 144 dense + 2 head, and 16 layers x 3 stacked tensors |
| `graph.graph_count`, `table_rows_a`, `table_rows_b`, `embed_node_count`, `head_node_count` | `34`, `35`, `24`, `1`, `3` |
| `graph.node_count_total` | recorded as a golden at first run, not a checked-in constant (section 3.6); the probe's harness measured 1,031 at width 256 and 983 at width 6 with extra per-layer view nodes the arm does not build |
| `pack.reader_pread_count`, `residency.total_bytes_read` (width-256 run) | `382` is **superseded by correction C3** — the counter also counts the 3,219 member-record reads and measures **3,939**; the runner prints it and asserts `residency.total_bytes_read == 1554531072`, which is the figure the residency claim rests on |
| `graph.slot_capacity` | `128` |
| `graph.activation_bytes_peak` | `4440064` |
| `head.output_bytes`, `head.node_count` | `84510720`, `3` — the head's `output` member is 50,304 x 2,048 of Q6_K, and it is what makes `window.dense_bytes` the head's rather than a layer's |
| `output.element_count`, `argmax`, `sha256`, `bit_sum` | `50304`, `2262`, `a56195da2c913d8dd7fa608917a381200c4b59d1c534fae2d4bbb828f80d2383`, `149873641306457` |
| `reference.verdict`, `graphs_compared`, `nodes_compared`, `nodes_identical` | `IDENTICAL`, `34`, `227`, `227` |
| `routing_oracle.verdict`, `layers_matched`, `ids_total`, `ids_printed_compared`, `sums_matched` | `MATCH`, `16`, `728`, `546`, `16` |
| `oracle.verdict`, `layers_matched`, `nodes_expected`, `elements_compared` | `PASS`, `16`, `227`, `21372` |
| `oracle.max_abs_diff_ten_thousandths`, `tolerance_ten_thousandths` | `0`, `1` |
| `oracle.sum_tolerance_millionths`, `sum_tolerance_relative_ppm` | `1000`, `10` |
| `oracle.sums_expected`, `sums_matched` | `227`, `227` |
| `oracle_logits.verdict`, `byte_identical`, `reference_sha256` | `IDENTICAL`, `true`, `a56195da…` |
| the runtime run: `oracle_logits.verdict`, `max_abs_diff…`, `argmax_primary`, `top_k_set_agreement` | `WITHIN`, `<= 5000` with **3477** recorded, `2262`, `10` |
| `lifetime.*_created == *_freed`, `released_before_owner_scope_end` | equal, `true` |
| `abi.tensor_alignment`, `table_drift`, `fp_contract_off` | `32`, `-1`, `true` |

A forced-failure loop over `for force in init compute` against the **real** shim expects
`R5_GGML_INIT` and `R5_COMPUTE`, as `run-layer-forward`'s and `run-moe-layer-forward`'s do. Then it
removes the pack, both instrument outputs, and the tree — on every exit path, including a signal.

The checked-in transcript excerpt is copied to a writable path before use because the arm opens it
with `fs.open_rw` (Align Request 21).

**`schedule[].l_out_sha256` is recorded and not asserted as a checked-in golden**, for
`r5a-dense-layer-forward.md` section 5.2's reason: sixteen such constants would fail on any ggml
kernel change with a message that reads like corruption. The four oracles are the acceptance
contract; the digests name *which layer* moved when one of them fails.
**`schedule[].routed` and `residency.*` are asserted as exact integers**, because unlike a digest
they are the measurement this capability exists to publish and a change in them is a change in the
claim.

### 5.3 Metrics

| Metric | Definition | Baseline on this host |
| --- | --- | --- |
| microbenchmark **B**, CPU compute, whole routed model | one six-token prefill, sixteen routed layers plus the head, warm, reconciliation width | **121.3 ms** median of five (117.3–127.2); wall **390–400 ms** over three warm runs |
| per-layer phase A compute | median over sixteen layers | **3.1 ms** (2.5–3.4) |
| per-layer phase B compute | median over sixteen layers | **4.4 ms** (3.3–5.7) |
| layer 15 after the narrowing | phase A / phase B | **3.08 / 1.07 ms** — phase B is 4.1× cheaper |
| head compute | `RMS_NORM`, `MUL`, `MUL_MAT` against 84.5 MB of Q6_K | **2.2–2.3 ms** |
| claim `pread`, whole model | 1,029 scattered plane reads from the GGUF | **~227 ms** warm for 1,301,446,656 B — **1.9× compute**; 510–544 ms cold |
| dense `pread`, whole model | 152 reads | **~40 ms** warm for 253,084,416 B |
| reused dense window | section 3.5's sweep | **84,520,960 B** — 2.0% of the model; the largest layer it holds is 11,075,584 B, 0.26% |
| reused claim window | section 3.5's sweep at `U_max` 48 | **195,821,568 B** reserved, **101,990,400 B** peak use — 4.6% and 2.4% of the model |
| peak resident weight bytes | both windows | **280,342,528 B** — **6.65%** of a 4.21 GB model |
| peak RSS | the shipped arm, five runs | **341,639,168 – 343,015,424 B**; self-reference arm 440,926,208 B; whole-tensor arm 408,240,128 B |
| activation, peak | `ggml_gallocr_get_buffer_size` over 34 graphs | **4,440,064 B** |
| residual + carried inputs | Align-owned, between graphs | **49,152 + 100,224 B** |
| **expert bytes read / expert bytes in model**, `T = 6` | the capability's metric | **1,301,446,656 / 3,900,702,720 = 33.36%** |
| same, over 41 prompts of 3–6 tokens | section 2.10 | **21.67% – 41.24%**; by length, `T=3` 24.68%, `T=4` 30.70%, `T=5` 31.42%, `T=6` 34.42% |
| whole prefill bytes read | including dense, head, and embedding rows | **1,554,531,072 / 4,213,512,192 = 36.90%** |
| cost of bit-exactness | the width-256 run minus the width-6 run | **+48 graph nodes** (1,031 against 983); compute difference within the ±4% run-to-run spread; **+0 bytes read on this prompt**, but see section 2.8 — the routing differs in 12 of 728 slots, so a zero here is not a general zero |
| whole-tensor comparison arm | all 1,024 planes resident | **3,900,702,720 B read, 1,123.7 ms of `pread`, 1,342.7 ms wall**, identical compute and identical logits |
| microbenchmark **A** | transfer + GPU compute | **N/A** — no routed GPU arm; `r5c-metal-prefill.md` owns the dense one. Section 5.4 |
| microbenchmark **C** | async prefetch + GPU compute | **N/A** — R5E ships no residency policy, and Request 41 blocks the construct. Section 5.4 |

These are secondary metrics and R5E makes **no** claim on time to a passing patch. Their purpose is
two numbers. **At 227 ms of claim `pread` against 121 ms of compute, a six-token routed prefill of
this model on this CPU is I/O bound even with the whole file in page cache** — that is what a
residency policy has to beat. And **33.36%**: two thirds of this model's expert weights are never
touched by a prefill, which is the property the runtime exists to exploit and which section 2.9
explains is a routing property rather than a cache result.

**Measurement risk, stated as numbers.** Compute is a median of five warm runs on one host at the
CPU backend's default thread count while both instruments ran at `-t 4`; the spread is 117.3–127.2
ms, ±4%. `pread` is far more variable — 227 ms warm against 544 ms cold, a 2.4× spread that is the
page cache and not the read shape, exactly as `r5b-model-prefill-forward.md` section 5.6 records for
R5B. The claim-read figure additionally reflects **scattered GGUF plane reads**, not the pack block
reads the shipped arm performs; `r5d-moe-layer-forward.md` section 2.7 measured pack blocks cheaper
at one-layer scale and section 5.2's qualification is what will measure it here. **The residency
ratios carry no measurement risk at all** — they are exact integers, and they are the metric this
capability should be judged on.

### 5.4 Deferred surfaces

| Surface | Deferred to | Why, with evidence |
| --- | --- | --- |
| **A residency policy, and any cache-hit claim** | a **multi-prefill session** capability | Section 2.9: within one prefill there are 343 demands and 343 distinct keys, so **no cache can hit**. `docs/specs/r3-residency-sim.md` section 2 reaches the same conclusion from the trace side and defines its verdict on a token-major decode order that a prefill does not produce. A policy needs repeated prefills, or decode, before any hit rate is a measurement rather than an artifact. R5E's `schedule[].routed` is that capability's input |
| The KV cache and decode | R6 | R5E computes one prefill. Decode needs a cache tensor, `set_rows`, incremental positions, a second graph shape, and an **instrument**: `llama-eval-callback` prints six elements per row and `llama-debug --save-logits` publishes only the final position. R6's first task is naming the oracle. Section 2.4's byte-identity says what the cache will cost in agreement terms: nothing, at a matched reduction width |
| Lifting `MAX_PREFILL_TOKENS` above 6 | R6 | Same blocker, same owner. Section 2.10 shows what it would buy the measurement: the expert-read fraction is still rising at `T = 6` |
| A claim window that shrinks to the routing decision | R6 | Section 3.5 reserves 195,821,568 B for `U_max = 48` against a 101,990,400 B measured peak. The 93.8 MB is a stated cost with a published field (`claim_peak_use_bytes`), not a correctness question |
| A window per block class | R6 | Section 3.5's dense window is sized by the head at 7.6× the largest layer. `r5b-model-prefill-forward.md` section 5.4's deferral, unchanged, with 84,520,960 B as this model's baseline |
| Microbenchmarks A and C, and a routed Metal arm | `r5c-metal-prefill.md`'s successor | Section 5.6's tie-ordering risk cannot be settled with CPU evidence; `r4-5-external-buffer.md` section 5.4's alignment rule still applies; and Request 41 blocks C's `spawn` construct at this pin |
| gpt-oss and a second MoE architecture | `moe-prereq-discharge.md` section 5.5 | Six-member `ExpertBlock`, MXFP4, split expert biases, fused `ffn_gate_up_exps`; the model is 12.1 GB and infeasible on this host |
| Expert hotness ordering and prefetch groups in the pack | `r4-alignpack-layer-major.md` sections 5.1 and 5.2 | Both are functions of an activation distribution. R5E's per-layer `routed[]` over 41 prompts is an input to that work, not a substitute for it. `r1c-olmoe-moe-ir.md` section 2.5.6's finding that **every** `ExpertBlock` is non-contiguous in the source file is what makes the pack's ordering worth doing at all |
| A slice rule in `--pack-verify` | R4 | `moe-prereq-discharge.md` section 5.5, unchanged |
| Reading the pack and the transcript read-only | Align Request 21 | The arm uses `fs.open_rw`; section 5.2 copies both to writable paths. R5E is the **sixth** client and the first that holds a pack open across 381 reads and 1.5 GB |
| Geometry in the container | R6 | `r5a-dense-layer-forward.md` section 5.4's deferral, and the argument is now strongest: a whole-model routed arm taking two files is the exact shape a loader will not want |
| Renaming to `align-runtime` | when the executable gains a residency policy | `r5b-model-prefill-forward.md` section 5.4's condition, unchanged and still unmet |

### 5.5 Candidate Align capability requests

**This section's original claim — "no new request is expected" — was refuted by the implementation,
and section 6 correction C22 records the retraction.** Two genuine Align gaps were found and are
registered as **Requests 47 and 48** in `docs/align-requests.md`; a third refusal was classified as
an application concern and is recorded below. The paragraph the implementation refuted read: every
construct this design needs compiled in the probe's Align neighbours or exists in R5D's shipped
module — the four node tables are `array<Node>` of a `Copy` record, the sixteen routing decisions are
integer arithmetic over `array<i64>`, the two windows are `buffer`, and the FFI boundary does not
change at all. The last of those is still true: section 3.6 needs no symbol R5D did not ship. The
first is not.

**The two new requests, and why they are 47 and 48.** They were drafted as 46 and 47 while this
branch's register ended at Request 43 and `agent/r3-residency-sim` still held 44 and 45 unmerged.
R3's pair merged first (PR #135) and then took 45 and 46 when PR #134 claimed 44, so the
reconciliation commit renumbers this branch's pair to **47** and **48**. The register carries the
resolved numbering note, and nothing outside it cited either number.

- **Request 47 — a `Borrow` argument must be a stable named local or field.** Measured at the pinned
  `4b515f8d`, and the slice form re-measured unchanged at the adopted `3a34febe`: `f(w[a..b])`, `f(b.build())`, and `f(if c { x } else { y })` are each refused with
  `error: the Borrow argument to 'sink' must be a stable named local or field, not a temporary
  value`, from `crates/align_sema/src/lib.rs:43694`. R5E slices two reused windows on every member
  placement, every reference fill, and every claim plane, so the mitigation — bind the expression to
  a named local on the preceding line — is applied throughout `src/moe_model_forward.align`.
  Genuine Align gap, non-blocking.
- **Request 48 — same-call argument aliasing between a `borrow mut` owner and its own scalar
  field.** `fill(box, box.n)`, where `fill` takes `borrow mut Box` and an `i64`, is refused with
  `error: borrowed argument 1 to 'fill' aliases argument 2, whose mode may invalidate the same
  owner`, from `crates/align_sema/src/lib.rs:30504`. The scalar is `Copy` and is copied at the call.
  The **second client shape folds into the same request**: `take(o, peek(o, 1))`, an outer
  `borrow mut` of the same owner beside a nested read-only borrow of it, **compiles** at the same
  pin — so the analysis is not uniform, and the same root cause gives two different answers. R5E's
  staging functions take an out-parameter record `borrow mut` plus geometry scalars, and the
  mitigation is to copy each scalar to a local first. Genuine Align gap, non-blocking.

**One refusal is an application concern and is recorded here rather than filed.** A function whose
`->` return arrow starts its own line —

```text
fn wide(
  a: i64,
)
-> i64 {
```

— is refused with `error: expected '{'`. The cause is Align's newline-terminated statement rule:
`crates/align_lexer/src/lib.rs:185` makes `)` at end of line emit a statement terminator, and the
parser's `eat(&TokKind::Arrow)` at `crates/align_parser/src/lib.rs:846` then never sees the arrow.
That is the language working as designed, not a gap; **keep the arrow on the signature's closing
line**, which is what `src/moe_model_forward.align` does at every multi-line signature.

Beyond the two it files, R5E is new client evidence for six requests that already exist, and an
anticipated client for two that do not exist in this branch.

- **Request 37 — per-function check time is superlinear in body length.** R5E is its most direct
  client yet, and it **shapes a module boundary before any code is written**. Measured at this pin on
  this host: `alignc check-per-unit src/moe_layer_forward.align` is **16.5 s** for 4,660 lines and
  `src/model_forward.align` is **17.6 s** for 4,492 — both already **above**
  `r5b-model-prefill-forward.md` section 5.5's "under 10 s" acceptance target, which is a regression
  that document's own successor is obliged to record. `gmake check` over the whole graph is
  **131.5 s** today against the **91.2 s** R5B measured. Section 3.10 therefore puts the R5E arm in a
  **new** module, `src/moe_model_forward.align`, rather than in `src/moe_layer_forward.align`, and
  keeps `r5a-dense-layer-forward.md` section 6 correction C8's discipline: no function over two
  hundred lines, every fallible call inside a loop propagating with `?`, never a `match` on a
  `Result` inside a loop. **The acceptance target is that `check-per-unit src/moe_model_forward.align`
  stays under 20 s and `gmake layer-forward-smoke` stays under 60 s**; the first is set from the two
  measurements above rather than from R5B's aspiration, and if either is exceeded the arm splits
  along the schedule/oracle boundary rather than absorbing the cost.
- **Request 42 — `alignc check` as a superset of `alignc build`.** R5E is a further client of the
  same class `r5d-moe-layer-forward.md` section 6 correction C10 hit: a Borrow crossing a
  `borrow mut` must be a parameter of the calling frame, `alignc check` on the single module accepts
  the form and `alignc build` over the import graph refuses it, so the module checks clean and the
  executable does not link. R5E's per-layer block scan, its per-layer member scan, and its
  sixteen-fold claim selection are all that shape. The mitigation is C10's — the scan is its own
  function whose block is a parameter — and it is recorded as an application-side workaround for a
  language-owned constraint, not hidden as a style choice. Non-blocking.
- **Request 34 — `Result` ok payloads beyond scalars.** Larger in degree: the slot store backs four
  node tables across thirty-four graphs and every one of the 1,031 handles the run creates passes
  through it, because `raw` is neither a struct field nor an array element.
- **Request 36 — owned `array<i64>` field replacement.** `schedule[]` is sixteen rows of about
  thirty columns, three of which are themselves nested integer arrays (`routed`, `expert_ids`,
  `compact_ids`), and each is built the way `r5a-dense-layer-forward.md` section 6 correction C9
  forced R5A's columns to be built: one record per column set, assigned as a whole by the stage that
  produces it.
- **Request 33 — aligned heap allocation.** Paid twice rather than R5B's once, because there are two
  windows; both are `MAX_TENSOR_ALIGNMENT` pads on a `buffer(n)` that takes no alignment, and the
  larger is 196 MB.
- **Request 21 — a read-only open.** Section 5.4's sixth client.

**Two requests R5E could only anticipate have since merged, and R5E is now a recorded non-blocking
client of both.** They arrived on `agent/r3-residency-sim` as 44 and 45 while this branch's register
still ended at Request 43, exactly as `r5d-moe-layer-forward.md` section 5.5 records; PR #135 merged
them and PR #134's Request 44 pushed them to **45** and **46**. The reconciliation commit appends
R5E to each client list; R5E takes no dependency on either surface and ships both mitigations:

- **Request 45** (moving a field out of a decoded record double-frees at run time). R5E decodes an
  `R1_MODEL_IR` document and moves fields out of it in `parse_geometry`. Mitigation: clone through a
  `str` view rather than move. Non-blocking.
- **Request 46** (`borrow mut` array locals inside loops, and no element assignment through an array
  field). R5E's sixteen routing decisions want a helper taking the per-token id tables as
  `borrow mut array<i64>` called inside the token loop, and want `schedule[L].compact_ids[t][s] = v`
  through a record field. Mitigation: return owned columns from helpers and write the loop body
  inline. Non-blocking.

Both mitigations become removable in the same verification whenever those requests reach
`ALIGN_MERGED` in Align itself.

**If the implementation refutes this section — as R5A's did, and as R5E's own did — the correction
belongs in a section 6 of this document, not in a quiet edit here.** Correction C22 is that record
for this section.

### 5.6 Risks

| Risk | Mitigation | Residual |
| --- | --- | --- |
| **The two id tables are conflated.** Section 2.3's probe bug: `get_rows` takes global ids and `mul_mat_id` takes compacted ones, and using one for both produces a model whose gate, up, swiglu and down nodes all agree with llama.cpp and whose mixing weights are garbage | Two separately named carried inputs, two separately validated ranges at step 31 (`R5E_CARRY`), a dedicated case `mm-id-table-swap` whose synthetic reference gathers by global id, and a transcript oracle that compares `ffn_moe_weights` in every layer | A build that swapped both tables *consistently* would fail the transcript oracle at `ffn_moe_gate` instead, so the failure is always visible; the risk is that it is visible at a node whose name does not suggest the cause, which is why `oracle.worst_node` is published |
| **The reconciliation width changes the routing**, so "the same model at two widths" reads two different byte sets and the two *invocations'* `residency.*` can differ | `KV_WIDTH` is a mandatory operand with no default, each invocation computes exactly one schedule and names it in `oracle_logits.compared_pass`, and section 5.2 runs the arm twice rather than once | A reader who compares `residency.expert_bytes_read` across the two documents will see two numbers. That is correct and is what section 2.8 documents; the summary block prints `kv width` so no document is ambiguous about which it is |
| **`mul_mat_id` semantics could change across ggml versions.** The whole design rests on a compact `{ne0, ne1, U}` stack with remapped ids being identical to a `{ne0, ne1, n_expert}` stack with global ids | Section 2.7 measured it at ggml 0.21.0 across the **whole model** — 1,024 planes against 343, both quantization mixes, byte-identical logits — where R5D measured one layer. It is still not a documented guarantee | The self-reference oracle runs the same compact stack twice and would not catch a change; the transcript oracle would, and the qualification runs it. `r5d-moe-layer-forward.md` section 2.3's `split` fallback remains the already-measured answer to a divergence |
| **Top-k ties.** `ggml_argsort` on a row with equal probabilities has an implementation-defined order, and R5D section 2.3 showed the slot order is load-bearing to the last bit | R5E and llama.cpp call the **same** `ggml_argsort` on the **same** bytes on the same backend, so a tie is broken identically and the routing oracle still matches. `routing.expert_ids` per layer is published so a tie-induced difference is visible as data | Real for a **different backend**, which is why section 5.4 defers the routed Metal arm. Over sixteen layers × six tokens on this prompt no router row held a duplicate probability |
| **The Q4_K `ffn_down_exps` layers are reached for the first time** — R5D's largest named gap, now closed | Section 2.4's byte-identity covers all sixteen layers; `schedule[].ffn_down_exps_ggml_type` is asserted against `r1c-olmoe-moe-ir.md` section 2.5.5's exact layer list | A pack whose block sizes disagree with its member records is a container defect and `alignpack_read` owns it |
| **The claim window is reserved for 48 and observed at 33.** A prompt could in principle reach 48 | The reservation **is** the arithmetic bound, so it cannot be exceeded; `R5E_CLAIM_OVERFLOW` is the fail-closed guard and section 4.5 marks it unreachable with the arithmetic rather than fabricating a fixture | The cost is 93.8 MB of idle window, published per run as `claim_peak_use_bytes` |
| **Two windows refilled 34 times and a stale pointer is silent.** A tensor alive across a refill would compute the next layer with the previous layer's weights, producing a plausible number | Every ggml buffer wrapping either window is freed before the next read begins, and `lifetime.*_created == *_freed` is asserted **per phase** (section 5.1). The self-reference oracle, which computes from ggml-owned copies, catches any surviving case: 227 of 227 | A leak that happens to free before the next assertion point would pass, which is why the reference oracle is per graph and not per run |
| **The probe read the GGUF and the arm reads a pack.** Section 2.1's stated limitation | The two byte streams are the same content, and R5D section 2.7 measured them byte-equal over 101,990,400 claim bytes; the self-reference oracle's `R5_SOURCE_DIVERGED` pre-check re-establishes it for every member and claim on every qualification run | **The claim-read *timing* in section 5.3 is a GGUF-scattered-plane figure, not a pack-block figure**, and the pack should be faster. Section 5.2's qualification is what turns the extrapolation into a number; until it runs, 227 ms is an upper bound presented as a measurement of the probe's read shape |
| **The 4.21 GB pack does not fit, or evicts the model from page cache** | The qualification refuses with an `N/A` line below the pack's size plus 1 GiB and removes the pack on every exit path including a signal. Free space was 12–13 GiB throughout the probe and the probe wrote no pack | Timings are cache-state dependent and section 5.3 says so: 227 ms warm against 544 ms cold, a 2.4× spread |
| **Around a thousand opportunities for `ggml_abort`** — the probe built 983 and 1,031 at the two widths — against R5D's two graphs and R5B's 874 | Every reachable precondition is validated before the first read — geometry, layer coverage, **expert coverage over 1,024 blocks**, shapes, types, both window budgets — and per-member alignment, carried lengths, id ranges, and residual lengths are re-checked at every layer. Step 24 moving the type check ahead of all I/O exists for exactly this | An internal kernel assertion still takes the process down with no document. The exposure grew; the validated surface grew with it |
| **The runtime-width logits bound is 5,000 ten-thousandths against a measured 3,491**, only 1.43× headroom where R5B had 1.8× | It is not the acceptance contract: the `IDENTICAL` verdict at the reconciliation width is. The bound was reused rather than raised, deliberately (section 3.7), and the spread across four prompts is 13% | A fifth prompt could breach it. Section 3.7 pre-commits: that would be a finding to record, not a number to raise |
| **Dropping R5B's top-ten *order* clause is a weakening** | It is replaced by set equality plus argmax, both measured 4 of 4, and `top_k_order_agreement` is still published as a number. `mm-logits-order-swap` asserts the distinction is observable | A defect that permutes the top ten without moving any logit by more than 0.5 and without changing the set is not constructible through this arm, because the byte-identical run at the instrument's width shares every node with the tolerant one |
| **The synthetic corpus is all-F32 and two layers**, so the mixed quantization, the 1,024-block coverage check, and the head's Q6_K are `Q`-only | Section 5.1 says so rather than implying `S` coverage; section 4.1's mixed-quant cell names the qualification for the real pattern and gives the synthetic corpus a per-layer type *difference* so the lookup path itself is `S`-reachable | A container whose per-layer types are uniform would not exercise the real pattern hosted. That is what `Q` is for |
| **`gmake layer-forward-smoke` grows past its budget** | Section 5.1's measurement (32.199 s today), projection (40–43 s), ceiling (60 s), and **pre-committed split along the dense/routed boundary with the topology change accepted** | If the split happens, `make ci` is selected for publication. `scripts/verification_scope.py`'s verdict decides the lane, not this table |
| **The goldens become a property of one compiler on one target** | R5A correction C15's `#pragma STDC FP_CONTRACT OFF`, `-ffp-contract=off`, and the asserted `abi.fp_contract_off` | Unchanged from R5A/R5B/R5D, now across a whole routed model's worth of stub-engine kernels |

---

## 6. Implementation-forced corrections

Every row below is a place where the implementation refuted section 3, 4, or 5 and the ledger is
corrected rather than the code bent to match it. Nothing here is a preference; each one names the
measurement or the language constraint that forced it.

**C1 — `n_expert_used`'s ceiling is 32 at R5E's slot base, not R5D's 34.** Section 3.9 step 8 says
R5D correction C1 is "inherited verbatim: the ceiling is `n_expert_used <= 34`". R5D's phase-B table
starts at slot 52; R5E's starts at 56, because an R5E layer carries nine dense members, four
attention inputs, three compact stacks and five carried values where R5D's carries ten and eight.
`MM_B_NODE_BASE + 2·u + 8 <= MAX_NODE_SLOTS` therefore gives `u <= 32`. The arm checks **its own**
bound at step 8, naming the field, rather than reaching the node walk and reporting `R5_SLOT` on a
row that is not at fault; `layer_olmoe.parse_geometry`'s R5D bound is untouched, because R5D's arm
still has R5D's store layout. Fixture `mm-geometry-expert-used-huge`.

**C2 — `residency.model_bytes` is the container's `total_bytes`, not the GGUF's file size.** Section
5.2 expects `4,213,512,192`, which is the size of the model **file**; the arm opens the alignpack and
on the ordinary path never opens the GGUF at all. The field is `pack.total_bytes`
(`4,212,193,280` on this model) and `total_bytes_read_ppm` is taken against it, which moves the
whole-prefill figure from 36.90% of the file to **36.91% of the container**. The qualification
asserts the equality rather than a literal, so a repacked model cannot silently move it.

**C3 — the read-group count is 495, and `pack.reader_pread_count` is neither 382 nor 495.** Section
3.4 counts `token_count + 2·n_layer + Σ U_L + 1 = 382` groups on the premise that a layer's
attention and router blocks are each read as one `pread` of `block.pack_bytes`. They are not:
`r5b-model-prefill-forward.md` section 6 correction C6 established that a block image cannot be read
into the reused window — Align's `pread` overwrites from index 0 — so it would have to be staged in a
separate 11 MB temporary and copied out. Dense members are therefore read **individually** into their
own window slots, exactly as R5B reads them, giving `6 + 144 + 2 = 152` dense groups; the claims stay
**block**-shaped at `343` groups, through one reused transient sized to the largest `ExpertBlock`,
with each returned chunk intersected against the three claims' spans and scattered. Total: **495
groups carrying the same 1,554,531,072 bytes.** `pack.reader_pread_count` is R5B's counter and is
larger again — **3,939** measured — because it also counts the 3,219 member-record reads of steps 12
to 17 and the header and table reads. The qualification prints the counter and asserts
`residency.total_bytes_read`, which is the figure the residency claim rests on.

**C4 — step 17 gains a per-layer plane-consistency rule.** The ledger validates each claim's shape
and its `slice` pair. The implementation additionally requires every expert of a layer to declare the
**same** plane byte count and the same ggml type, because `mul_mat_id` reads plane `u` at
`u · plane` and one stride serves the whole compact stack: a single dissenting expert would make the
stack read the wrong bytes for every plane after it. A disagreement is `R5_SHAPE` with
`layer[<L>]expert[<e>]role[<name>]`. This is the same class as the claim `ggml_type` consistency
check R5D's review repair adds, and it is deliberately the same semantics. Fixture
`mm-claim-plane-mixed`; the all-experts mutation `mm-engine-claim-type` still reaches
`R5_TYPE_UNSUPPORTED`.

**C5 — `R5E_CARRY`'s two id-range arms are not input-reachable; only its length arm is.** Section 4.5
gives the code three fixtures. Step 28's `layer_olmoe.decide` already refuses every id outside
`[0, n_expert)` and verifies the compaction is a bijection onto `[0, U_L)` **before** step 31 runs, so
a `topk_ids` entry `== n_expert` and a `compact_ids` entry `== U_L` are `R5D_EXPERT_ID` at step 28 and
can never reach step 31. The two range checks stay as fail-closed defence — the arm does not depend on
having been called in order — and the **length** arm is what makes the code stub-reachable, through
one new stub force flavour. `R5E_CLAIM_OVERFLOW` remains not input-reachable exactly as section 4.5
already records.

**C6 — two stub force flavours are added.** `ALIGN_GGML_FORCE_SHORT_READBACK` under-reports R5B's
slot 51; R5E's `l_out` is slot 69 at the synthetic corpus's `n_expert_used = 3`, so
`engine+moe-residual-short` is a new flavour rather than a reuse, and `engine+moe-carry-short`
under-reports the phase-A `ffn_norm` at slot 52. Section 4.2's no-new-symbol claim stands: the shared
contract region of `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c` is unchanged and still
byte-identical, no declaration moved, and both macros exist only in the stub and only under a `-D`
the ordinary build never passes.

**C7 — `mm-id-table-swap` is a fixture property, not a forced build.** Section 4.3 asks for "a forced
build that passes `compact_ids` to `get_rows`". The two id tables are two rows of
`layer_olmoe.mm_b_node_table` naming two different slots, so swapping them is a source edit and there
is no build the runner can select. What is shipped is the **detection**: the generator's pure-Python
reference gathers probabilities by *global* id, and the transcript oracle compares
`ffn_moe_weights-L` in every layer, so a swapped table fails `mm-engine-transcript` at
`ffn_moe_weights` while `ffn_moe_gate` still passes — section 2.3's exact signature. That was
**measured** during implementation, not argued: pointing `mm_b_row`'s row 1 at `MM_SLOT_COMPACT`
instead of `MM_SLOT_TOPK` and rebuilding gives `status: ok`, `oracle.verdict: FAIL`,
`worst_node: ffn_moe_weights`, `worst_layer: 0`, `max_abs_diff_ten_thousandths: 956`, and
`routing_oracle.verdict: MATCH` — a model whose routing decision is right, whose gate, up, swiglu
and down nodes all agree with the reference, and whose mixing weights are garbage. It is recorded
here rather than checked in, because a case that requires editing the module under test is not a
regression a runner can own.

**C8 — the synthetic corpus's dense-window peak is the layer pair, not the head.** Section 4.3's `S`
cell expects `window.dense_peak_block_kind` to be the head "on the synthetic model too". At
`block_align` 4,096 the head's two members round to 8,192 B while a layer's nine round to 36,864 B,
so the peak is layer 0's `AttentionBlock`. The head-peak property is the **real model's** and is
asserted there: `dense_bytes == 84,520,960` with `dense_peak_block_layer == -1`.
`r5b-model-prefill-forward.md`'s synthetic corpus has the same shape for the same reason.

**C9 — `IDENTICAL` is not stub-reachable.** Section 4.4's logits cell expects `S` byte-identity
against the synthetic blob. The generator's pure-Python second implementation agrees with the stub
engine to **zero ten-thousandths** and not bit-for-bit — exactly as `--model-forward`'s own synthetic
case does, whose golden records the same `verdict: FAIL`, `byte_identical: false`,
`max_abs_diff_ten_thousandths: 0`. The hosted case asserts the zero, the argmax, and the bound;
`IDENTICAL` stays the real model's `Q` cell, where it is measured against `llama-debug --save-logits`
and passes.

**C10 — the oracle table is seventeen rows per layer, and there is no `nodes[]` to publish them in.**
Section 3.7 lists fourteen element-compared rows. The table also needs `kq-L` and `kq_soft_max-L`
(matched, and their declared `ne0` validated against `KV_WIDTH` in every layer) and
`ffn_moe_topk-L`, which oracle 3 reads and oracle 2 must neither compare against a tolerance nor
width-check. That is `1 + 17·n_layer + 2 = 275` rows of which `1 + 14·n_layer + 2 = 227` are
compared, which is the number section 3.7 publishes and `elements_compared == 21,372` confirms. The
third class is a new `ORACLE_ROUTING` value in `src/layer_olmoe.align`; R5D's tables never emit it,
so R5D's scan is unchanged. Section 4.4's "excluded classes are fields" cell names `nodes[].oracle`,
and `R5_MOE_MODEL_FORWARD` has no `nodes[]` array **by design** — 275 rows over sixteen layers is
exactly the per-node dump section 3.8 rejects — so the cell is discharged by `oracle.nodes_expected`
plus `mm-transcript-kv-width`, which proves the `shape_incomparable` rows are matched and
shape-checked.

**C11 — the corpus's token list is `[3, 17, 16]`, not `[3, 17, 5]`.** Section 5.1's list routes **all
eight** experts at layer 0 of the synthetic model, which makes `U == n_expert`,
`compact_ids == expert_ids`, and that layer's residency fraction 1 — the three properties the corpus
exists to exercise. `[3, 17, 16]`, swept out of the generator's own forward, routes six of eight at
layer 0 with three distinct per-token slot orders and three of eight at the narrowed layer 1.

**C12 — `lifetime.phase_balance_failures` is a document field.** Section 3.8's `lifetime` object does
not list it and section 5.1 requires `lifetime.*` asserted balanced at every **phase** boundary. A
per-phase assertion needs a counter; this is `r5b-model-prefill-forward.md`'s `graph_balance_failures`
one scope finer, and `released_before_owner_scope_end` is `false` when it is non-zero.

**C13 — the checked-in excerpt carries `attn_norm-0` as well as section 5.1's list.** Without it the
first unmatched oracle row is `attn_norm-0` and the hosted excerpt case is `R5_ORACLE_MISSING`; with
it the first failing row is `kq-0`, whose declared `ne0` is 256 against the synthetic corpus's
`KV_WIDTH` 8, which is the `R5_ORACLE_SHAPE` the case exists to observe.

**C14 — the dense source comparison runs before each layer's graphs and the claim source comparison
after them.** Section 3.9 step 35 lists both inside the reference arm. The claims are read inside
`run_layer`, and threading the reference path, a second transient and a second counter set into a
function that already takes thirty parameters buys nothing: the reference *node* comparison computes
from the same window bytes and cannot disagree about them, so a pack/GGUF divergence is still
`R5_SOURCE_DIVERGED` and still stops the run. Verified by `mm-source-diverged-claim`, whose mutation
is placed on a plane the schedule actually reads.

**C15 — `residency.expert_bytes_read_ppm` is 333,644, and 333,647 was arithmetically wrong
everywhere it appeared.** `1,301,446,656 · 10^6 / 3,900,702,720` is `333,644` in the integer
arithmetic the document publishes. The percentage the capability claims — **33.36%** — is unchanged.
The correction is applied **in place** at all three sites rather than only here, because a probe
record that carries a number the shipped arm contradicts is not evidence: section 2.9's summary
block, section 4.3's residency cell, and section 5.2's assertion row all now read `333,644`.
Section 4.3's cell additionally said `planes_read == 343`; the plane count is `343 · 3` roles =
**1,029**, and 343 is the `(layer, expert)` key count on the row above it.

**C16 — the shipped arm's timings are single runs against a cold page cache, not the probe's warm
median, and they vary by 2.3x between two consecutive qualifications.** Section 5.3 records
microbenchmark B at **121.3 ms**, a median of five warm runs of a C harness reading the GGUF. The
same qualification, run twice on this host minutes apart with the self-reference arm's 34 extra
graphs competing for the same cores, measured **252.8 ms** and then **109.9 ms** of graph compute for
the same six-token prefill; claim `pread` measured **612.0 ms** and then **519.9 ms**, dense `pread`
160.9 ms and then 106.1 ms, and peak RSS 404,258,816 B and then 358,432,768 B. Section 5.3's baseline
is therefore **not** restated as met or missed on one run. What the two runs do establish, and what
the capability's claim actually rests on, is the *shape*: the claim read is **2.4x and 4.7x compute**
respectively, so on this CPU a six-token routed prefill is I/O bound even with the pack in page
cache, and that is the number a residency policy has to beat. The exact-integer half —
`expert_bytes_read`, `planes_read`, `keys_demanded`, the per-layer union curve — carries no
measurement risk at all and is identical in both runs. A warm repeated-run median is R6's to take.

**C17 — `R5_WINDOW_BUDGET` and `R5D_CLAIM_BUDGET` are not input-reachable, `R5_INDEX` is not
emitted, and the coverage denominator is the thirty-six declared `R5*` codes.** Three separate
places said otherwise and none of them was measured.

*The two budgets.* Section 4.5 promised "a member record declaring 2^40 bytes, on a dense member and
on a claim" as their fixtures. Both mutations were built and run at this pin, and both produce
`R4_PACK_OFFSET` with detail `member[1]` and `member[43]`: `alignpack_read.member_at` refuses a
member whose `[pack_offset, pack_offset + nbytes)` leaves its block, and `open_pack` refuses a
container whose `total_bytes` is not the opened file's own length. Growing the block and the header
to match therefore requires an 8 GiB+ pack, and no smaller container can make either window exceed
its 8 GiB ceiling. The two codes join `R5E_CLAIM_OVERFLOW` and `R4_WINDOW_UNAVAILABLE` as
fail-closed guards, marked with the arithmetic that makes them so rather than given a fabricated
fixture. The two mutations are **kept** as `mm-dense-nbytes-huge` and `mm-claim-nbytes-huge`,
because the guard *ordering* — container containment before window sizing — is a real property and
these are its regression.

*`R5_INDEX`.* Section 3.9's inherited-code row listed it among "R5A's, unchanged". The arm emits it
nowhere; the row is now enumerated code by code with `R5_INDEX` absent.

*The denominator.* Section 7.5 said "34 of the 36" while the runner printed "36 codes reached" — two
different sets, neither defined. The denominator is now fixed once: the **thirty-six `R5*` codes**
section 3.9's table declares (R5E's four, R5D's four, R5A's/R5B's twenty-eight). The fifth block
reaches **32** of them plus **five** inherited `R4_*`/`R2_*` codes, and
`scripts/run-layer-forward-smoke` owns both sets as data and asserts them **in both directions**, so
a code that stops being reached and a code reached outside the declaration are both failures.

**C18 — a non-UTF-8 path operand is refused, and the gap it closes is repository-wide.**
`json_string` renders every path operand through `json.encode`, which escapes the bytes JSON forbids
*as control characters* but copies a non-UTF-8 byte through raw, so a malformed operand produced a
document no conforming JSON reader can decode. R5E adds `utf8_ok` to its own step 2 and refuses such
an operand with `R5E_PATH` and no document at all. The check is **the arm's**, not
`moe_layer_forward.valid_path`'s, so R5A, R5B, R5C and R5D keep the behaviour their goldens record.
**Those four arms inherit the defect**: each renders its own path operands the same way, and each
would emit the same undecodable document. Closing it there is a change to four shipped contracts and
four golden files and belongs to a capability that owns them, not to this one; it is recorded here
so the next arm to touch them has the finding rather than rediscovering it. Fixture
`mm-path-not-utf8`.

**C19 — `oracle.sums_expected` and `sums_matched` are document fields, because an absent block sum
was silently skipped.** Section 3.7 makes the block sum half of oracle 2's contract, and
`compare_transcript_sum` returned early on `sum_present != 1` without recording anything. A
transcript that lost its `sum =` lines therefore produced `verdict: PASS` with
`max_sum_diff_millionths: 0` — indistinguishable from a transcript whose every sum matched. The two
counters are added to the `oracle` object: `sums_expected` counts every compared node and
`sums_matched` counts those whose sum was present and within the rule. Fixture
`mm-transcript-nosums` (`sums_expected 31`, `sums_matched 1`); the real transcript is `227` and
`227`. This is a schema addition to `R5_MOE_MODEL_FORWARD` `schema_version: 1` before it has any
consumer, so the version is not advanced and the R5E goldens are regenerated.

**C20 — the self-reference oracle's non-aliasing property is an assertion, not a description.**
Section 3.7 said "the reference arm asserts its tensors' data pointers are **not** the windows'".
No such assertion existed; the property held because `ggml_backend_alloc_ctx_tensors` allocates its
own buffer, which is an argument and not a check. `outside_window` now runs on every reference
tensor and every reference claim stack immediately before it is filled, requiring
`slot_data_offset` against the window it copies from to be `< 0` or `>= window.len()`. A violation
is `R5_REFERENCE_MISMATCH` detail `aliased[<role>]`. It is the same primitive `graph_identity` uses
to prove the *primary* arm's tensors **are** at their own window offsets, used here for the opposite
conclusion.

**C21 — `residency.keys_distinct` is derived from a run-level set.** Section 3.8 presents
`keys_demanded == keys_distinct` as section 2.9's finding, and the implementation wrote
`o.keys_demanded += routing.count` and `o.keys_distinct += routing.count` on consecutive lines: one
accumulator published twice, whose equality proves nothing and which a multi-prefill consumer would
never see diverge. `keys_distinct` is now the cardinality of `merge_keys`' run-level
`(layer, expert)` set, and `keys_demanded` keeps its accumulation. Both numbers are unchanged on
every prefill — 343 and 343 on the model, 9 and 9 on the synthetic corpus — which is now a measured
equality between two derivations rather than a tautology.

**C22 — section 5.5's "no new request is expected" was wrong, and two requests are filed.**
`docs/align-requests.md` Requests **47** (a `Borrow` argument must be a stable named local or field)
and **48** (same-call aliasing between a `borrow mut` owner and its own `Copy` scalar field) are both
genuine Align gaps, both non-blocking, both with the application-side mitigation R5E ships and with a
minimal probe verified at the pinned `4b515f8d` and sibling line citations. They were drafted as 46
and 47 while this branch's register ended at 43 and `agent/r3-residency-sim` held 44 and 45 unmerged;
correction C23 records the resolved numbering. A third refusal — a
function whose `->` starts its own line — is an **application concern** caused by Align's
newline-terminated statement rule and is recorded in section 5.5, not filed.

**C23 — reconciliation with the merged R5D: the pin moves to `3a34febe`, the two new requests
renumber to 47 and 48, and no golden byte or measured quantity moves.** This capability was designed,
implemented, and reviewed on a branch based on the merged MOE-PREREQ-DISCHARGE, at pin
`4b515f8d`. Between then and publication `main` gained PR #134 (which moved `.align-revision` to
`3a34febe` and took Align Request 44), PR #135 (R3-RESIDENCY-SIM, whose two requests became 45 and
46), PR #136, PR #138, PR #140 (R2C-DECODE-INSTRUMENT), and PR #139 (R5D itself, including its own
review repair). The branch **merges** `main` rather than rebasing over it, so its recorded
baseline-chain commits stay reachable, and it takes main's repaired R5D verbatim: R5D's
`stage_claim_types` refusal, its stable-insertion-sort stub `argsort`, its `view_2d` F32 gate, and
its `moe-engine-claim-type-mismatch` case are main's, unmodified by R5E.

Three consequences are recorded rather than absorbed silently. **(1)** The pin is adopted and every
owner and the real-model qualification are re-run against the managed `3a34febe` compiler; **no
golden byte changed** — the R5A, R5B, R5C, R5D, R5E, and ggml-spike goldens are byte-identical and
`layer-forward-smoke` is byte-identical across three runs — and every exact-integer quantity in
section 7 is identical at the new pin. The Request 47 and 48 probes were re-measured at `3a34febe`:
the slice-form `Borrow` refusal and both halves of the aliasing asymmetry reproduce unchanged.
**(2)** The two requests renumber to **47** and **48**, because R3's pair merged first and then took
45 and 46. **(3)** R5E is appended as a client of Requests 45 and 46 — the two it could only
anticipate while they lived on `agent/r3-residency-sim` — with the same mitigations it already
shipped. The only quantity that moved at all is a timing diagnostic already governed by correction
C16: this qualification measured microbenchmark B at **147.3 ms** and claim `pread` at **560.8 ms**,
inside the 109.9–252.8 ms and 519.9–612.0 ms spreads C16 records, and the claim read is **3.8x**
compute, which is the shape the capability's claim rests on.

---

## 7. Cell-to-case map

Every applicable cell of section 4 against its implementing function and its passing evidence.
`S` is `gmake layer-forward-smoke`'s fifth block, `Q` is `gmake moe-model-forward-qualification`.

### 7.1 `src/layer_olmoe.align` (section 4.1)

| Cell | Implementation | Evidence |
| --- | --- | --- |
| Four tables well-formed | `mm_embed_node_table`, `mm_a_node_table`, `mm_b_node_table`, `mm_head_node_table`, all through one `mm_table` loop | `S` every `mm-engine-*` case builds all six graphs; `graph.table_rows_a/b` = 35/14 asserted, `Q` 35/24 |
| Conditional rows form a graph at each condition | `mm_row_issued` + `build_nodes`' `when`/`alt_when` walk | `S` `node_count_a` is 33 at layer 0 and 35 at the last, asserted as a difference of exactly two; phase B is asserted equal at both. `Q` 33/35 over sixteen layers |
| The `LAYER` operand | `mm_oracle_table(g, n_layer)` renders `stem-L`; `build_layer_members(table, plan, layer)` reads layer `L`'s member records; `T_out(L)` is the caller's `spec.t_out` | `S` 31 of 31 names matched at two layers; `Q` **227 of 227** matched in the real transcript |
| Per-layer mixed quantization | `plan_layer_experts` records `plane_bytes`/`plane_type` per `(layer, role)` from the member record | `Q` `ffn_down_exps_ggml_type == 14` for exactly layers 0,1,4,7,10,13,14,15 and `dense_bytes` 11,075,584/9,994,240 accordingly |
| The last layer's shapes differ | the two `WHEN_LAST` rows and `spec.t_out` | `S` `schedule[1].t_in == 3`, `t_out == 1`; `Q` `schedule[15].t_in == 6`, `t_out == 1`, `routed_count == 8` |
| The routing decision | `layer_olmoe.decide`, unchanged from R5D | `S` `schedule[].routed/expert_ids/compact_ids` equal the generator's at both layers; `Q` all sixteen, and the bijection re-derived per layer |
| A missing or inconsistent geometry field | `layer_olmoe.parse_geometry` + step 8's R5E ceiling (C1) | `S` sixteen `mm-geometry-missing-*` and fifteen `mm-geometry-*` cases |
| An unusable bit pattern | `bits32_finite_nonnegative` | `S` `mm-geometry-eps-nan`, `eps-negative`, `rope-base-zero`, `rope-base-inf` |
| Unsupported arch or rope | step 9 | `S` `mm-geometry-arch`, `mm-geometry-rope-scaled`, `mm-geometry-rope-type`, `mm-geometry-rope-dims` |
| Scalars — the mask at two widths | `mm_write_mask(width, height)`, `attn_scale_bits` | `S` `KV_WIDTH` 8 against `T` 3 exercises the wide mask and the three `WHEN_WIDE` rows; `Q` `attn_scale_bits == 3db504f3` |
| Cleanup — no handle, no file, no `unsafe` | the module holds none | `S` the `unsafe`/`extern` scan names only `src/ggml_ffi.align` |

### 7.2 `src/ggml_ffi.align` and the two C files (section 4.2)

| Cell | Implementation | Evidence |
| --- | --- | --- |
| Every op R5E needs already exists | `build_nodes` calls R5A's 25 + R5B's `pad`/`cont` + R5D's `argsort`/`mul_mat_id`/`view_2d`/`slot_new_tensor_3d`/`slot_new_i32_2d` | `S` the shared-contract byte-identity assertion at the top of the runner; **no declaration was added** |
| Status mapping | `ggml_ffi.r5_code_for`, unchanged | `S` every negative status reached by a forced build maps to an `R5*` code |
| The two C files agree | the shared-contract marker block | `S` unchanged; the two new macros (C6) are stub-only and outside it |
| No `malloc` | neither file allocates | `S` `grep -c malloc` is 0, unchanged |
| Contraction off | `-ffp-contract=off` | `S` `abi.fp_contract_off` asserted `true` on every one of the 93 documents |
| Malformed slots | bounds-checked as R5A | `S` `mm-force-slot-range` |
| Cleanup per graph | `teardown_layer`, total against null | `S` every forced case still balances `lifetime.*` and reports `phase_balance_failures: 0` |

### 7.3 `src/moe_model_forward.align` (section 4.3)

| Cell | Implementation | Evidence |
| --- | --- | --- |
| Arm selection | `src/ggml_spike.align`'s first-operand dispatch | `S` `mm-arm-unknown-flag`, and `arm-r5a/r5b/r5d-unchanged` assert the three earlier arms still emit their own `kind` |
| Arity, five to nine | `run` | `S` `mm-arity-four`, `mm-arity-ten` → no document, non-zero exit |
| Path operands are lexically valid **and UTF-8** | `mm_valid_path` = `moe_layer_forward.valid_path` + `utf8_ok` | `S` `mm-path-not-utf8` → no document, non-zero exit; the six empty/long/NUL/`-` cases unchanged (C18) |
| Role-qualified block selection | `find_block_with_role` | `S` `mm-block-missing`, `mm-block-ambiguous`; `Q` `embedding_block_index == 0`, `output_block_index == 1057` |
| Layer and expert coverage | `validate_layer_coverage`, `validate_expert_coverage` | `S` `mm-coverage-gap-router` → `layer[1]`, `mm-coverage-gap-expert` → `layer[1]expert[5]`; `Q` `expert_block_count == 1024` |
| Dense window sizing | `size_dense_window` | `S` the peak is layer 0's pair (C8); `Q` `dense_bytes == 84520960`, `dense_peak_block_layer == -1` |
| Claim window sizing at `U_max` | `size_claim_window` | `S` `claim_u_max == 8 == min(n_expert, n_expert_used·T)`, `claim_bytes == 12288`; `Q` `195821568`, `48`, peak use `101990400` at layer 0 |
| The read schedule | `fill_members` + `stage_claims`/`read_block_scatter` | `S` 6 window fills; `Q` **495 read groups** (C3) carrying `total_bytes_read == 1554531072` |
| The residual carry | `run_layer`'s step-33 block | `S` `l_out_ne1` 3 then 1; `mm-force-residual-short` → `R5_RESIDUAL` `layer[0]` |
| The five carried inputs and two id ranges | `stage_carry` | `S` `mm-force-carry-short` → `R5E_CARRY` `layer[0]input[ffn_norm]`; the two range arms are fail-closed (C5); `Q` `carried_bytes == 100224` |
| Global ids feed `get_rows`, compact ids feed `mul_mat_id` | `mm_b_row` rows 1 and 3/4/6 | C7; `S`/`Q` the transcript oracle compares `ffn_moe_weights-L` in every layer at 0 ten-thousandths |
| The narrowing | the two `WHEN_LAST` rows | `S` golden; `Q` `narrow_layer == 15`, `narrow_index == 5` |
| The head | `mm_head_node_table`, `run_end_graph(GRAPH_HEAD)` | `S` `output.element_count == 32`; `Q` `== 50304`, and `head.output_bytes == 84510720` / `head.node_count == 3` asserted by the runner |
| Window reuse is safe | every ggml buffer freed before the next read | `S` `phase_balance_failures == 0` per phase; `Q` the self-reference oracle at 227/227 |
| The residency accounting | `schedule_model`'s per-layer accumulation, `merge_keys`, `render_residency` | `S` equal to the generator's, `keys_demanded == keys_distinct == 9` from two different derivations (C21); `Q` `1301446656 / 3900702720 = 333644 ppm`, `planes_read == 1029`, `keys_demanded == keys_distinct == 343` |
| Each error code | `stage_*` | section 7.5 |
| `-` document destination | `run` | `S` `mm-doc-stdout-identical` compares the five-operand, `-`, and file forms |
| Exit mapping | R0's, verbatim | `S` every case asserts `status` against the exit code |
| Cleanup | `teardown_layer` in section 3.10's order | `S`/`Q` counters balance, `released_before_owner_scope_end: true` |

### 7.4 The four oracles (section 4.4)

| Cell | Implementation | Evidence |
| --- | --- | --- |
| Reference — bytes equal per block and per claim | `compare_source_members`, `compare_claim_source` | `S` `mm-source-diverged-claim` → `layer[0]expert[1]role[ffn_gate_exps]`; `Q` every dense member and all 343 read claims equal, 2,426 preads for 1,554,531,072 bytes |
| Reference — nodes identical per graph | `compare_reference_rows` | `S` all 31 nodes of all six synthetic graphs; `mm-force-reference` → `graph[1]layer[0]node[attn_norm]@0`; `Q` **227 of 227 over 34 graphs**, and byte-identical logits |
| Reference — the second arm does not alias the window | `outside_window`, in `reference_weights` and `reference_claims` | `S` asserted before every reference fill on every graph, `reference.verdict: IDENTICAL`; `Q` the same over 34 graphs (C20) |
| Transcript — grammar | `moe_layer_forward.scan_transcript`, reused unchanged | `S` `mm-transcript-garbage` → `R5_TRANSCRIPT` |
| Transcript — every layer matched | `prepare_transcript` | `S` `mm-transcript-missing-layer` → `layer[1]node[l_out]`; `Q` `layers_matched == 16` |
| Transcript — matched by `(name, shape)` | `compare_transcript_rows`' four-`ne` check | `Q` the real transcript's duplicate `norm-15` at two shapes is never sought, and every compared row's declared shape equals the computed one |
| Transcript — the element-count rule | `prepare_transcript`'s `printed_count` product | `S` `mm-transcript-headers` (`0/18`), `mm-transcript-novalues` (`0/6`); `Q` `elements_compared == 21372` |
| Transcript — `kq-L` `ne0` against `KV_WIDTH` | `prepare_transcript`'s `ORACLE_SHAPE_INCOMPARABLE` branch | `S` `mm-transcript-kv-width` → `layer[1]node[kq]`, and `mm-transcript-excerpt` → `layer[0]node[kq]` on real instrument formatting |
| Transcript — excluded classes | the three classes in `mm_oracle_table` | C10; `oracle.nodes_expected == 31` hosted and `== 227` on the model |
| Transcript — a tolerance breach | `compare_transcript_elements` | `S` `mm-transcript-perturbed` → `verdict: FAIL`, `worst_layer: 0`, `worst_node: l_out`, `status: ok`, routing still `MATCH` |
| Transcript — an exact pass | `compare_transcript_rows` | `S` `max_abs_diff == 0`, `sums_expected == sums_matched == 31`; `Q` `== 0` over 21,372 elements, `max_sum_diff_millionths == 0`, `sums_matched == 227` |
| Transcript — a sum that was never compared is visible | `compare_transcript_sum`'s two counters | `S` `mm-transcript-nosums` → `status: ok`, `verdict: PASS`, `sums_expected 31`, `sums_matched 1` (C19) |
| Routing — success per layer | `compare_routing_layer` | `S` `MATCH` at both layers with **full** element-wise coverage (12/12) at `n_expert_used = 3`; `Q` `MATCH`, `ids_printed_compared == 546`, `ids_total == 728`, `sums_matched == 16` |
| Routing — failure is data | `schedule_model`'s verdict block | `S` `mm-routing-mismatch` → `MISMATCH` on a `status: ok` run with `first_difference_layer: 1`, oracle 2 still evaluated |
| Routing — a wrong id refused before use | step 28 | `S` `mm-force-routing-id-range` → `layer[0]token[0]slot[0]`, `mm-force-routing-id-repeat` → `layer[0]token[0]slot[1]` |
| Logits — file shape | step 39 | `S` `mm-logits-short` → `R5_LOGITS_SHAPE`, `mm-logits-missing` → `R5_LOGITS_UNREADABLE` |
| Logits — an unrepresentable reference element | `logit_ten_thousandths` + the `nonfinite` refusal | `S` `mm-logits-nonfinite`, `mm-logits-nan` → `R5_LOGITS_NONFINITE elements[1]`; `mm-logits-huge` → `status: ok`, `verdict: FAIL` |
| Logits — byte-identical at the reconciliation width | `compare_logits` | C9; `Q` `byte_identical: true`, `sha256 a56195da…`, `verdict: IDENTICAL` |
| Logits — the runtime width verdict | `compare_logits` | `S` `mm-logits-runtime-width` → `WITHIN`; `Q` `max_abs_diff == 3477 <= 5000`, `argmax 2262 == 2262`, `top_k_set_agreement == 10` |
| Logits — a real failure is not `WITHIN` | `compare_logits` | `S` `mm-logits-perturbed` at the runtime width → `FAIL` with the argmax still equal |
| Logits — the order clause is reported, not required | `compare_logits` | `S` `mm-logits-order-swap` → `WITHIN`, set 10, order 3; `Q` set 10, **order 2** |
| Tolerances not silently widened | four document fields | `S` `1`, `1000`, `10`, `5000` asserted; a change is a diff in four places |

### 7.5 Error-code coverage

`gmake layer-forward-smoke`'s fifth block reaches **32 of the 36 `R5*` codes** section 3.9 declares,
plus **five inherited `R4_*`/`R2_*` codes**, for real, with no ggml, no model, and no network. The
runner prints exactly those numbers and owns both sets as data (correction C17).

The four `R5*` codes it does not reach:

| Code | Why |
| --- | --- |
| `R5_ABI` | `Q`-only, and only if the linked ggml drifts |
| `R5E_CLAIM_OVERFLOW` | not input-reachable: step 19 reserves for `U_max`, which no routing decision can exceed |
| `R5_WINDOW_BUDGET` | not input-reachable: the container refuses a member or block that would make the dense window exceed 8 GiB before the window is sized (correction C17), measured as `mm-dense-nbytes-huge` |
| `R5D_CLAIM_BUDGET` | the same, on the claim window, measured as `mm-claim-nbytes-huge` |

The five inherited codes it does reach are `R4_PACK_UNREADABLE`, `R4_PACK_TRUNCATED`,
`R4_PACK_OFFSET`, `R4_5_SLICE`, and `R2_EXPERT_ID_NOT_INTEGRAL`; `alignpack_read`'s other five
`R4_PACK_*` codes belong to `alignpack-smoke`. Every other code in section 3.9's table has a named
case above. `R5E_CARRY` is reached through its length arm; C5 records why its two range arms are
not.
