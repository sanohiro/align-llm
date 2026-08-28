# R5D-MOE-LAYER-FORWARD: one OLMoE MoE layer computed from Align-owned expert claims

Status: design of record for the R5D capability.
Owner document for the **MoE half** of stage 2 of `docs/specs/roadmap.md` section R5's gate.
Align pin: `.align-revision` = `3a34febe912db5096c58c74fede36ff53f223e04`, adopted at
reconciliation from the merged PR #134. Every number in this document was first taken at
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` and re-taken at the new pin; correction C22 records the
re-run and the one quantity that moved.
Predecessors, whose contracts this capability extends rather than duplicates:
[`r5a-dense-layer-forward.md`](r5a-dense-layer-forward.md) (the node-slot store, the one-op
wrappers, the transcript oracle and its tolerances, the summary block, the validation ladder),
[`moe-prereq-discharge.md`](moe-prereq-discharge.md) (a claim is one plane of a stacked tensor, and
`R4_5_SLICE`), and [`r4-5-external-buffer.md`](r4-5-external-buffer.md) (the shim, the FFI module,
the alignment contract, and the teardown order).
Inputs consumed verbatim: [`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md) section
2.4's container, [`r1c-olmoe-moe-ir.md`](r1c-olmoe-moe-ir.md) section 2.4's `model` object and
section 2.5.3's block order, and [`r2a-expert-trace.md`](r2a-expert-trace.md) section 2.2's
transcript line grammar.

This document triggers the proportional design gate of `CLAUDE.md` on four counts: a new public CLI
arm, a new versioned exchanged document (`R5_MOE_LAYER_FORWARD`), a new ownership boundary (a graph
whose *topology depends on data the graph itself produces*, split across two computations with an
Align-owned decision between them), and a coordinated invariant across five modules. Section 3 is
the single public-contract ledger, section 4 is the closure matrix, and section 5 owns fixtures,
qualification, metrics, deferrals, risks, and candidate Align requests.

Section 2 is the probe record and it is first on purpose. Every contract in section 3 was chosen
after the probe. Six of this design's decisions exist **only** because a probe refuted the plan this
document started with: the QK-norm is taken over `n_embd` and not per head, the router's weights are
never renormalized, the top-k node is an `ARGSORT` plus a `VIEW` and not `ggml_top_k`, the expert
planes need no restacking copy at all, four different nodes in one OLMoE layer print under the same
transcript name, and the residency win this capability exists to demonstrate is a **decode**
property that has almost vanished by eighteen prefill tokens.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

`docs/specs/roadmap.md` section R5's gate is three stages in order: **単一block、単一layer、最小モデル**.
R4.5 discharged stage 1 for a dense member; `moe-prereq-discharge.md` discharged it for an **expert
claim** — one plane of a stacked expert tensor, addressed at its claimed offset, computed as one
`mul_mat`, bit-identical to the same plane read into ggml-owned memory. R5A discharged stage 2 for a
Qwen2 **dense** layer, and R5B stage 3 for a Qwen2 model.

Every one of those results is about a layer whose weight set is known before the layer runs.

R5D is **stage 2 for a routed layer, and only that**: one prefill of at most six tokens through
OLMoE `blk.0`, computed by ggml over attention weights and **only the routed experts' planes** held
in Align-owned buffers, checked against llama.cpp's own numbers for the same tokens.

The question stage 2-MoE answers is not "can ggml read one expert plane" — the MoE prerequisite
answered that. It is: **when the set of weights a layer needs is not known until the layer has
already half-run, and Align owns both the decision and the bytes, is the result still the layer
llama.cpp computes?** A router that picks the right experts but sums them in the wrong order, or an
expert stack that is compacted without remapping its ids, produces a layer that is plausible,
finite, and wrong. Section 2.4 measures exactly how wrong, and section 2.6 shows that the property
being bought is smaller than it looks.

The capability that answers it is **R5D-MOE-LAYER-FORWARD**: a new arm of the existing `ggml-spike`
executable that reads OLMoE `blk.0`'s attention and router members out of an alignpack v1 container
into Align-owned aligned windows, computes the layer up to the router in one graph, **decides in
Align which expert claims the tokens actually reached**, reads only those claims into three more
Align-owned windows, computes the expert half in a second graph, and emits an
`R5_MOE_LAYER_FORWARD` document carrying per-node digests, the selected expert ids, the bytes it
read against the bytes the layer contains, and **three independent oracle verdicts**.

### 1.2 In scope

- One new Align module, `src/layer_olmoe.align`, owning the OLMoE MoE-layer topology as data: two
  node tables (one per phase), the member-role and claim-role tables, the shape rules, the scalar
  derivations, and the routing decision. It contains no `extern` declaration and no `unsafe` block.
- Five new entry points in `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c` with their
  declarations in `src/ggml_ffi.align` — `argsort`, `mul_mat_id`, `view_2d`, a 3-D stacked-tensor
  constructor, and a 2-D i32 constructor — plus one **widened** existing symbol (`soft_max_ext` with
  no mask). Section 2.8 is why that is the whole boundary change and section 3.5 is the contract.
- One new CLI arm, `ggml-spike --moe-layer-forward`, and the `R5_MOE_LAYER_FORWARD` document at
  `schema_version: 1`.
- Three oracles, all defined in section 3.6: a **bit-exact self-reference** oracle (the same two
  graphs over the same bytes placed in ggml-allocated memory), a **routing-identity** oracle (the
  selected expert ids must equal the transcript's `ffn_moe_topk-0`), and a **tolerance oracle**
  against a checked-in `llama-eval-callback` transcript excerpt.
- One owner test that runs without ggml and without a model, against a synthetic OLMoE pack with
  `n_expert` 8, and one named focused qualification that runs with the real model and real ggml.
- The residency measurement this capability exists to produce: expert bytes read against the layer's
  whole expert footprint, reported as two integers in the document, per prefill length.

### 1.3 Non-goals

- **No loader.** R5D reads what one layer's routing decision names, once, and holds it for one
  graph. Residency, tiering, eviction, cache score, and prefetch remain the R5 loader's, exactly as
  `r4-5-external-buffer.md` section 5.4 and `r4-alignpack-layer-major.md` section 5.1 defer them.
  R5D produces the *measurement* a residency policy would need; it does not implement one.
- **No decode.** The routing decision is taken once, for a prefill of at most six tokens. Section
  2.6 is explicit that the interesting residency regime is decode, and that R5D deliberately does
  not reach it. This is the single largest honest limit of this capability.
- **No KV cache.** The attention is computed over the prefill's own positions. Section 2.2 records
  the one consequence this has for the oracle, inherited unchanged from R5A section 2.3.
- **No second layer and no model.** `l_out-0` is the last node. A whole MoE model is stage 3's own
  consumer boundary and section 5.4 says what would have to be true first.
- **No `LAYER` operand.** The arm computes layer 0. Section 5.4 records the coverage this costs —
  OLMoE's `ffn_down_exps` is Q6_K on layers 0, 1, 4, 7, 10, 13, 14, 15 and Q4_K on the other eight,
  and R5D reaches only the Q6_K form — and what adding the operand would cost, which is small.
- **No GPU arm.** `r5c-metal-prefill.md` owns the Metal boundary for the dense graph; a routed graph
  on Metal adds a tie-ordering question (section 5.6) that CPU evidence cannot settle. Section 5.4
  keeps it deferred.
- **No gpt-oss.** The six-member `ExpertBlock`, MXFP4 geometry, split expert biases, and fused
  `ffn_gate_up_exps` stay where `moe-prereq-discharge.md` section 5.5 leaves them.
- **No new container version.** R5D reads alignpack v1 with the claim member form that
  `moe-prereq-discharge.md` already admits, and writes nothing to it.
- **No microbenchmarks A and C.** R5D measures B, on the CPU, for one routed layer, and section 5.3
  says so as a number.

### 1.4 Gate statement

Each stage is discharged, partly discharged, or deferred **individually**, with the probe that
settles it named.

| Gate stage | Verdict | Evidence |
| --- | --- | --- |
| 単一block — a single block, dense | **Discharged by R4.5.** Not re-litigated here | `r4-5-external-buffer.md` section 1.4 |
| 単一block — a single block, expert claim | **Discharged by MOE-PREREQ-DISCHARGE.** Not re-litigated here | `moe-prereq-discharge.md` section 1.1 |
| 単一layer — a single layer, dense | **Discharged by R5A** | `r5a-dense-layer-forward.md` section 1.4 |
| 単一layer — a single layer, **routed** | **Dischargeable, CPU, prefill.** All twenty-six oracle nodes of OLMoE `blk.0` agree with `llama-eval-callback` to the last digit it prints; the forty-eight selected expert ids agree exactly; and the routed graph over compacted Align-owned claims is byte-identical to the same graph over the whole 64-plane tensors | Section 2.4 (max sampled `\|Δ\|` = 5.0e-5, the print-rounding bound, over 2,376 elements; 28 of 28 node dumps byte-identical against the whole-tensor arm), section 2.5 (28 of 28 byte-identical against ggml-owned weights) |
| 最小モデル — a smallest model, routed | **Deferred.** R5D stops at `l_out-0` | Section 5.4 |
| required microbenchmark A — transfer + GPU compute | **Deferred.** No GPU arm and no transfer tier exist here | Section 5.4 |
| required microbenchmark B — CPU compute, routed layer | **Discharged at 9.4 ms typical** for one MoE layer, six tokens, warm, over two graphs: phase A 3.59 ms and phase B 5.77 ms median of five probe runs. The whole-tensor arm, which must hold all sixty-four planes, takes 11.0 ms in one graph | Section 2.4, section 5.3 |
| required microbenchmark C — async prefetch + GPU compute | **Deferred.** Prefetch is a loader property | Section 5.4 |
| **residency win in bytes** — the claim this capability exists to test | **Measured and smaller than the plan assumed.** At six prefill tokens the union of routed experts is 25 of 64 and R5D reads **101,990,400 of 261,095,424** expert bytes, 39.1%. At one token it is 8 of 64 and 12.5%. At eighteen tokens it is 47 of 64 and 73.4% | Section 2.6 |

The honest summary is: **R5D discharges stage 2 of three on the CPU for a routed layer, and
microbenchmark B, and it measures the residency win rather than assuming it.** It leaves stage 3,
benchmarks A and C, the Metal arm, decode, and every layer but 0 where their own evidence puts them.

---

## 2. Probe record

Everything in this section was executed on this host before section 3 was written. Commands are
given exactly as run. Probe sources live outside the work tree and are not part of the capability;
what ships is section 3's design, and section 5.2's qualification is the probe made reproducible.

### 2.1 Host, toolchain, model, and the oracle instrument

| Item | Value |
| --- | --- |
| Host | `MacBookAir10,1`, Apple M1, 16 GiB, `darwin/arm64` |
| Align compiler | the managed pinned release toolchain at `3a34febe912db5096c58c74fede36ff53f223e04` (design and first measurement at `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`; correction C22) |
| llama.cpp | `0.2.0 (build 10566)`, Homebrew |
| ggml | `0.21.0`, Homebrew, headers in `/opt/homebrew/include`, backends `dlopen`ed from `libexec` |
| Model | `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 4,213,512,192 bytes |
| Backend selected | `CPU`, through R4.5's registry path; `ggml_backend_buft_get_alignment` = `32` |

The geometry the probe read from the container, and which `r1c-olmoe-moe-ir.md` section 2.4 already
publishes as a document: `arch` olmoe, `n_layer` 16, `n_embd` 2048, `n_head` 16, `n_head_kv` 16
(MHA, `n_gqa` 1), `head_dim` 128, `n_ff` 1024, `n_ff_exp` 1024, `n_vocab` 50304, `n_expert` 64,
`n_expert_used` 8, `context_length` 4096, `rms_eps` 1e-05, `rope.type` 2 (NEOX), `rope.freq_base`
10000.0, `rope.dim_count` 128, `rope.scaling_type` `null`.

The oracle instrument is `llama-eval-callback`, R2A's instrument, on a six-token prompt. The prompt
is not R5A's: OLMoE's tokenizer turns `def add(a, b):` into **seven** ids, and section 2.2 explains
why seven is one too many.

```text
$ llama-tokenize -m OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf -p "def add(a, b" --ids
[1545, 823, 9, 66, 13, 270]

$ llama-eval-callback -m OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf -p "def add(a, b" -n 1 -t 4 -ngl 0 \
    -fa off -ctk f32 -ctv f32 -nr -c 512 > transcript.txt 2> log.txt
number of input tokens = 6
  1545 823 9 66 13 270
```

The flag set is R5A section 2.2's, unchanged and for R5A's reasons: `-fa off` keeps the attention
unfused so its intermediates print, `-ctk f32 -ctv f32` keeps the cache unquantized, `-ngl 0` keeps
the graph on the CPU, and `-nr` suppresses the reasoning wrapper.

### 2.2 Probe 1 — the transcript, and five facts the plan got wrong

`blk.0` of the real graph is forty-two callback lines. The names and shapes below are transcribed
from the run above, not from a reading of llama.cpp.

**Fact 1 — the QK-norm is an RMS norm over `n_embd`, applied before the head reshape.** The plan
assumed a per-head norm over `head_dim`, which is what several other QK-norm architectures do. Build
10566 emits:

```text
Qcur-0        = (f32)  MUL_MAT(blk.0.attn_q.weight{2048, 2048, 1, 1}, attn_norm-0{2048, 6, 1, 1}}) = {2048, 6, 1, 1}
norm-0        = (f32) RMS_NORM(Qcur-0{2048, 6, 1, 1}, }) = {2048, 6, 1, 1}
Qcur_normed-0 = (f32)      MUL(norm-0{2048, 6, 1, 1}, blk.0.attn_q_norm.weight{2048, 1, 1, 1}}) = {2048, 6, 1, 1}
Qcur_normed-0 (reshaped) = (f32) RESHAPE(Qcur_normed-0{2048, 6, 1, 1}, }) = {128, 16, 6, 1}
Qcur-0        = (f32)     ROPE(Qcur_normed-0 (reshaped){128, 16, 6, 1}, leaf_6{6, 1, 1, 1}}) = {128, 16, 6, 1}
```

`ggml_rms_norm` normalizes over `ne[0]`, and `ne[0]` here is 2048. The order is therefore
**project → RMS-norm over `n_embd` → scale by `attn_q_norm.weight` → reshape to `{head_dim, n_head,
T}` → RoPE**, and the same five steps for K with `attn_k_norm.weight`. A per-head norm would have
been arithmetically different and would have passed every shape check in the plan. Section 3.5 fixes
the order as data.

**Fact 2 — the router does not renormalize.** The plan carried a "top-k probabilities, renormalized
to sum to one" assumption from the general MoE literature. The graph says otherwise:

```text
ffn_moe_logits-0  = (f32)  MUL_MAT(blk.0.ffn_gate_inp.weight{2048, 64, 1, 1}, ffn_norm-0{2048, 6, 1, 1}}) = {64, 6, 1, 1}
ffn_moe_probs-0   = (f32) SOFT_MAX(ffn_moe_logits-0{64, 6, 1, 1}, }) = {64, 6, 1, 1}
ffn_moe_probs-0 (reshaped) = (f32) RESHAPE(ffn_moe_probs-0{64, 6, 1, 1}, }) = {1, 64, 6, 1}
ffn_moe_argsort-0 = (i32)  ARGSORT(ffn_moe_probs-0{64, 6, 1, 1}, }) = {64, 6, 1, 1}
ffn_moe_topk-0    = (i32)     VIEW(ffn_moe_argsort-0{64, 6, 1, 1}, }) = {8, 6, 1, 1}
ffn_moe_weights-0 = (f32) GET_ROWS(ffn_moe_probs-0 (reshaped){1, 64, 6, 1}, ffn_moe_topk-0{8, 6, 1, 1}}) = {1, 8, 6, 1}
```

`ffn_moe_weights-0` is a plain gather out of the full 64-way softmax. There is no second softmax, no
division by a partial sum, and no `ffn_moe_weights_sum` node. The measured proof is arithmetic:
`ffn_moe_probs-0` sums to `6.000000` over six tokens, exactly one per token, while
`ffn_moe_weights-0` sums to `2.735722` — 0.456 per token, not 1.0. A renormalizing implementation
would have produced `6.000000` there too. In llama.cpp's `build_moe_ffn` vocabulary this is
`norm_w = false`, `scale_w = false`, gating op softmax; the probe reads it off the numbers rather
than off the source.

**Fact 3 — the top-k node is `ARGSORT` + `VIEW`, not `ggml_top_k`.** ggml 0.21.0 ships three
spellings: `ggml_argsort`, `ggml_argsort_top_k` (argsort then view), and `ggml_top_k`, whose header
comment states **"the resulting top k indices are in no particular order"**. The transcript shows
`ARGSORT` then `VIEW`, so the slot order of `ffn_moe_topk-0` is descending probability. Fact 6 shows
that slot order is load-bearing to the last bit, so this is not a cosmetic choice: an
implementation that reached for `ggml_top_k` because it is the obviously named function would have
produced a different reduction order and a different `ffn_moe_out-0`.

**Fact 4 — the expert sum is a chain of eight views and seven adds, in slot order.**

```text
ffn_moe_gate-0     = (f32) MUL_MAT_ID(blk.0.ffn_gate_exps.weight{2048, 1024, 64, 1}, ffn_norm-0 (reshaped){2048, 1, 6, 1}}) = {1024, 8, 6, 1}
ffn_moe_up-0       = (f32) MUL_MAT_ID(blk.0.ffn_up_exps.weight{2048, 1024, 64, 1},   ffn_norm-0 (reshaped){2048, 1, 6, 1}}) = {1024, 8, 6, 1}
ffn_moe_swiglu-0   = (f32)     SWIGLU(ffn_moe_gate-0{1024, 8, 6, 1}, ffn_moe_up-0{1024, 8, 6, 1}}) = {1024, 8, 6, 1}
ffn_moe_down-0     = (f32) MUL_MAT_ID(blk.0.ffn_down_exps.weight{1024, 2048, 64, 1}, ffn_moe_swiglu-0{1024, 8, 6, 1}}) = {2048, 8, 6, 1}
ffn_moe_weighted-0 = (f32)        MUL(ffn_moe_down-0{2048, 8, 6, 1}, ffn_moe_weights-0{1, 8, 6, 1}}) = {2048, 8, 6, 1}
ffn_moe_weighted-0 (view) = (f32) VIEW(ffn_moe_weighted-0{2048, 8, 6, 1}, }) = {2048, 6, 1, 1}   × 8
node_56 .. node_61 = (f32)        ADD(...)                                                        × 6
ffn_moe_out-0      = (f32)        ADD(node_61{2048, 6, 1, 1}, ffn_moe_weighted-0 (view){2048, 6, 1, 1}}) = {2048, 6, 1, 1}
l_out-0            = (f32)        ADD(ffn_moe_out-0{2048, 6, 1, 1}, ffn_inp-0{2048, 6, 1, 1}}) = {2048, 6, 1, 1}
```

Slot `i` is `ggml_view_2d(weighted, n_embd, T, weighted->nb[2], i * weighted->nb[1])` and the adds
chain left to right from slot 0. Seven of the eight intermediate names are `node_NN`, which
`r2a-expert-trace.md` section 2.2 finding 3 already establishes as unstable; only the endpoints are
named. Section 3.6 therefore matches the endpoints and marks the chain uncompared by contract.

**Fact 5 — four different nodes in one OLMoE layer print under the name `norm-0`.** R5A's oracle
matched `norm-L` by first occurrence because a Qwen2 layer has two. An OLMoE layer has four: after
`embd`, after `Qcur-0`, after `Kcur-0`, and after `ffn_inp-0`. Matching by ordinal across four
same-named nodes is a silent-miscompare hazard, so section 3.6 excludes the bare `norm-0` nodes
from the oracle by contract and matches the four unambiguous `MUL` products instead —
`attn_norm-0`, `Qcur_normed-0`, `Kcur_normed-0`, `ffn_norm-0` — each of which is the RMS norm's only
consumer and therefore proves it.

**Fact 6 — six tokens is the cap, and `ffn_moe_topk-0` is structurally truncated even there.**
`r2a-expert-trace.md` section 2.2 finding 6 fixes the instrument's print rule: an axis of extent
`ne` prints in full when `ne <= 6` and otherwise prints `{0, 1, 2, ne-3, ne-2, ne-1}`. At `T = 6`
every token row prints in full, which is why the prompt has six tokens and not the seven OLMoE's
tokenizer produces for R5A's string. But `ffn_moe_topk-0` is `{8, 6}`: its **slot** axis is 8, so
slots 3 and 4 of every token are never printed. The oracle sees 36 of 48 expert ids directly, plus
the block's exact integer sum `1471.000000`, which pins the twelve unprinted ids in aggregate.
Section 3.6 states this as a contract rather than leaving it as an unnoticed gap; it is R2A's
`slots_truncated: true`, reaching a consumer for the first time.

### 2.3 Probe 2 — the C harness, and the three shapes an expert computation can take

A C harness built OLMoE `blk.0` for the same six tokens with the weights in a `posix_memalign`ed
caller buffer handed to `ggml_backend_dev_buffer_from_host_ptr`, exactly as R5A section 2.3's
harness does, with `ggml_get_data(t)` asserted equal to the window offset for every weight so the
arm cannot silently degrade to a copy. Three arms differ only in how the expert half is computed.

- **`full`** — the whole `{2048, 1024, 64}` gate and up tensors and the `{1024, 2048, 64}` down
  tensor are read into the window and `ggml_mul_mat_id` runs with the graph's own `ffn_moe_topk-0`.
  This is llama.cpp's own shape and exists to be the reference the other two are measured against.
  It reads **261,095,424** expert bytes.
- **`claim`** — the router runs first in its own graph; the harness reads its decision back, forms
  the ascending union of selected experts, reads **only those planes** into three compact windows,
  and runs `ggml_mul_mat_id` over `{2048, 1024, U}` and `{1024, 2048, U}` tensors with ids remapped
  from global expert id to compact slot.
- **`split`** — the same two-phase read, but the expert half is one `mul_mat` per `(token, slot)`
  pair over a 2-D view of one plane, `swiglu_split`, a second `mul_mat`, a scale by that slot's
  router weight, and a chain of adds in slot order. Forty-eight triples, 474 graph nodes.

The first thing the probe measured is that **`claim` needs no restacking copy**. The plan had
budgeted one: read the planes, then copy them into a contiguous stack for `mul_mat_id`. That is
unnecessary, because a stacked 3-D tensor over `U` planes is exactly `U` plane-sized regions laid
end to end, and the read is free to place each claim directly at its own slot in the window. The
"restack" is a choice of destination offset, not a memcpy. This removes the entire copy cost and
the entire second copy of the expert bytes from the design.

The second thing it measured is the answer to the question the capability was built to ask.

| Comparison, all twenty-eight dumped nodes | Result |
| --- | --- |
| `claim` vs `full`, byte-for-byte | **28 of 28 identical**, including all seven `ffn_moe_*` nodes and `l_out-0` |
| `split` vs `full`, the six columns of `ffn_moe_out-0` | **6 of 6 identical**, 0 of 2048 elements differing per column |

Both alternatives are bit-identical to llama.cpp's own shape. Compacting the expert stack and
remapping the ids changes nothing, because `mul_mat_id`'s per-row dot product does not depend on how
many planes the stack holds; and the per-pair form is identical too, because the accumulation order
within a dot product is the row's, and the accumulation order across slots was chosen to be
llama.cpp's.

That last clause is not decoration. Re-accumulating `full`'s own `ffn_moe_weighted-0` in **reversed**
slot order, in f32, changes **1,189 of 2,048** elements of token 0's `ffn_moe_out-0`, with a worst
absolute difference of 1.49e-8. Slot order is load-bearing to the last bit, and section 3.5 makes it
a normative property of the node table rather than an accident of a loop direction.

**The decision is `claim`**, on three grounds and not on correctness, since both arms are exact:

| | `claim` | `split` |
| --- | --- | --- |
| phase-B graph nodes | **22** | 474 |
| phase-B compute, five runs (ms) | 5.81, 5.77, 6.77, 5.69, **4.87** — median **5.77** | 7.40, 9.45, 7.90, 8.96, **7.36** — median **7.90** |
| graph size as a function of `T` | constant | `O(T · n_expert_used)` |
| new FFI symbols beyond the shared four | `mul_mat_id`, a 3-D constructor | a plane-selecting `view_2d`, and `n_expert_used · T` extra slot indices per layer |

`split` is slower, grows its node table with the prompt, and would put 474 slot indices into the
node-slot store for one layer of one model. `claim` is the design. `split` is recorded here because
it is the fallback if a future backend's `mul_mat_id` diverges (section 5.6), and it is now known to
be exact rather than hypothetical.

### 2.4 Probe 3 — the transcript oracle

The `full` and `claim` arms were both compared against the transcript with R5A section 2.3's
comparator, extended for i32 blocks: the instrument prints every element through `%12.4f`, so an
integer expert id prints as `      57.0000` and is parsed as an integer, never as a float
(`r2a-expert-trace.md` section 2.2 finding 5).

Twenty-six nodes matched, 2,376 elements compared.

```text
node                n    max|diff|    max rel          sum(tr)          sum(us)      sumdiff
embd               36     0.000048   4.43e+01         1.342047         1.342049     0.000002
attn_norm-0        36     0.000050   1.92e-01         5.488234         5.488233     0.000001
Qcur_pre-0         36     0.000048   2.16e+01         3.762854         3.762869     0.000015
Qcur_normed-0      36     0.000047   4.73e+01       276.451843       276.451862     0.000019
Qcur_rope-0       216     0.000050   4.22e+01       242.221283       242.221427     0.000144
Vcur-0             36     0.000049   1.91e-01        -0.614304        -0.614304     0.000000
Kcur_pre-0         36     0.000049   4.39e+01        -0.170024        -0.170025     0.000001
Kcur_normed-0      36     0.000046   2.28e+01        23.798388        23.798357     0.000031
Kcur_rope-0       216     0.000049   3.23e+01       -21.750244       -21.750223     0.000021
kqv-0             216     0.000049   3.38e-01         0.923157         0.923153     0.000004
kqv_out-0          36     0.000049   1.37e-01         0.923154         0.923153     0.000001
node_32            36     0.000050   2.28e+01         0.752945         0.752946     0.000001
ffn_inp-0          36     0.000049   3.34e-01         2.094993         2.094995     0.000002
ffn_norm-0         36     0.000050   8.56e-03        41.125698        41.125706     0.000008
ffn_moe_logits-0   36     0.000050   8.24e-04      -314.662903      -314.663002     0.000099
ffn_moe_probs-0    36     0.000050   1.05e-02         6.000000         6.000000     0.000000
ffn_moe_argsort-0  36     0.000000   0.00e+00     12096.000000     12096.000000     0.000000
ffn_moe_topk-0     36     0.000000   0.00e+00      1471.000000      1471.000000     0.000000
ffn_moe_weights-0  36     0.000047   1.77e-03         2.735722         2.735722     0.000000
ffn_moe_gate-0    216     0.000050   2.69e+01     -6427.178711     -6427.208036     0.029325
ffn_moe_up-0      216     0.000050   1.57e-01       -68.727715       -68.727793     0.000078
ffn_moe_swiglu-0  216     0.000050   4.34e+01         7.152205         7.152186     0.000019
ffn_moe_down-0    216     0.000050   4.61e-01        18.623728        18.623908     0.000180
ffn_moe_weighted-0 216     0.000050   4.69e+01         1.459490         1.459498     0.000008
ffn_moe_out-0      36     0.000048   4.36e+01         1.459494         1.459498     0.000004
l_out-0            36     0.000048   1.48e+01         3.554496         3.554493     0.000003
WORST max abs diff over all sampled elements = 0.000050
```

**5.0e-5 is the largest disagreement the comparison can produce when every element agrees.**
`llama-eval-callback` prints with `%12.4f`, so a printed value carries an inherent ±5.0e-5. Every
one of the 2,376 sampled elements agreed with the harness to the last digit printed. The `max rel`
column is large where the printed value rounds to zero and is not a fault. This is R5A section 2.3's
result reproduced on a routed layer, and section 3.6 reuses R5A's element threshold unchanged
because the measurement is the same.

**The two integer rows are the routing-identity oracle.** `ffn_moe_argsort-0` and `ffn_moe_topk-0`
agree element-for-element on every printed id and their sums — `12096` and `1471` — are exact
integers, not rounded prints. `12096` is `6 · (0 + 1 + … + 63)`, the identity every permutation
satisfies and therefore weak; `1471` is the sum of the forty-eight actually-selected ids and is the
one that binds. The selected sets are:

```text
t0: 57 55 33 35 51 16 43  7      t3: 21  6 54 53 40 13  0 32
t1: 55 21 57 43 33 39  7 38      t4:  6 21 54 32 36  4 14 53
t2: 33 43  6 59  7 48 61 21      t5: 21 36  6 40  0 15 32 14
```

The sums were also checked against R5A section 3.6's **sequential f32 accumulation in element
order**, which is what the shipped contract compares. The worst absolute residual over sixteen
checked nodes is **3.0e-5** (`ffn_moe_logits-0`, whose sum is -314.66) and the worst relative
residual is **5.35e-7** (`ffn_moe_swiglu-0`). R5A's rule `|Δ| <= max(1.0e-3, 1.0e-5 · |Σ|)` clears
the worst absolute case by 33× and the worst relative case by 19×, so section 3.6 reuses it
unchanged rather than inventing a MoE-specific number.

### 2.5 Probe 4 — the bit-exact self-reference oracle

The same two graphs were built a second time with every weight tensor allocated by
`ggml_backend_alloc_ctx_tensors` and filled from the same Align window with
`ggml_backend_tensor_set`, so ggml owns the bytes and the harness owns nothing ggml can see. The
harness asserts that the reference tensors' data pointers are **not** the window's, so the arm
cannot pass by accident.

**28 of 28 node dumps byte-identical**, including all seven `ffn_moe_*` nodes, the i32
`ffn_moe_argsort-0` and `ffn_moe_topk-0`, and `l_out-0`. Placing a routed layer's weights — dense
members and expert claims alike — in an Align-owned buffer changes no bit of the result.

### 2.6 Probe 5 — the residency win is a decode property, and the plan overstated it

This is the probe that most changed the document. The plan's premise was that a top-8-of-64 layer
touches an eighth of its experts. That is true for **one** token. It is not true for a prefill,
because the union grows with every token and the graph must hold every plane any token reached.

The union of selected experts for OLMoE `blk.0`, and the bytes R5D therefore reads, as a function of
prefill length, over the prefix of one real prompt:

| `T` | distinct experts `U` of 64 | expert bytes read | of 261,095,424 |
| --- | --- | --- | --- |
| 1 | 8 | 32,636,928 | **12.5%** |
| 2 | 11 | 44,875,776 | 17.2% |
| 4 | 21 | 85,671,936 | 32.8% |
| 6 | 25 | 101,990,400 | **39.1%** |
| 8 | 31 | 126,468,096 | 48.4% |
| 12 | 35 | 142,786,560 | 54.7% |
| 18 | 47 | 191,741,952 | **73.4%** |

At eighteen tokens the residency win is 27% and falling. The design consequence is stated in section
1.3 and section 5.4 and is not hedged: **claim-level expert residency is a decode-time property.**
R5D's job is to prove the mechanism is exact and to publish the curve, not to claim a prefill win it
does not have. A loader that wants the win has to work per decode step, and that is the loader's
capability, not this one's.

Two secondary facts fall out of the same measurement. The union is a **layer-0** union; nothing here
says layers agree, and `r2a-expert-trace.md`'s locality aggregates are the owner of that question.
And `U` is data-dependent, so the phase-B graph's `ne2` is data-dependent: section 3.5 makes `U` a
node-table parameter resolved between the phases rather than a constant.

### 2.7 Probe 6 — the claim bytes, and what the pack buys

The probe reads each plane at `member.source_offset + slice_index · plane_bytes`, which is
`moe-prereq-discharge.md` section 1.1's arithmetic. It reproduces that document's numbers exactly:
`blk.0.ffn_gate_exps.weight` begins at **264,894,464**, its plane is **1,179,648** bytes, and expert
63's claim is at **339,212,288** — the value that document derives by hand.

A real pack was then built and the two read paths compared over the same twenty-five selected
experts.

```text
$ main --pack OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf $TMPDIR/olmoe.alignpack $TMPDIR/olmoe-pack.json
elapsed ns: 8761362084   src ranges: 3106   pack ranges: 1058
src ampl ppm: 39337715   pack ampl ppm: 1000000   destination: WRITTEN
   → 4,212,193,280 bytes, 1,058 blocks

rep0 gguf_scattered: 75 reads   66.043 ms | pack_blocks: 25 reads   47.746 ms | bytes=101990400 identical=1
rep1 gguf_scattered: 75 reads   16.045 ms | pack_blocks: 25 reads   11.980 ms | bytes=101990400 identical=1
rep2 gguf_scattered: 75 reads   15.513 ms | pack_blocks: 25 reads   12.082 ms | bytes=101990400 identical=1
```

The bytes are **identical**, which is the property `R5_SOURCE_DIVERGED` exists to defend. The
container's contribution is locality: an `ExpertBlock` holds one expert's gate, up, and down claims
in one contiguous 4,079,616-byte span, so twenty-five experts are twenty-five reads instead of
seventy-five, and the same bytes arrive 25% faster cold and 23% faster warm. The pack was deleted
immediately; section 5.2's qualification rebuilds it.

### 2.8 Probe 7 — what the Align FFI surface allows, verified at the pin

The existing `extern` block in `src/ggml_ffi.align` already carries `op_get_rows`, `op_rms_norm`,
`op_mul`, `op_add`, `op_mul_mat`, `op_reshape_3d`, `op_permute`, `op_cont_3d`, `op_rope_neox`,
`op_soft_max_ext`, and `op_swiglu_split` — the whole attention half of an OLMoE layer, unchanged
from R5A. Reading the two C files at the pin settles what the MoE half still needs.

**`align_ggml_slot_new_tensor_2d` cannot make an i32 tensor.** It gates on
`align_ggml_table_row(type)`, and the twenty-five-row operand table has no entry for `GGML_TYPE_I32`
(26) — which is exactly why `align_ggml_slot_new_i32_1d` exists as its own symbol. The remapped id
tensor is `{n_expert_used, T}`, so R5D needs `align_ggml_slot_new_i32_2d` beside it. Widening the
operand table instead would let a quantized-weight path accept i32, which is the opposite of what
that table is for.

**`align_ggml_op_soft_max_ext` refuses a null mask.** It fetches the mask slot first and returns
`ALIGN_GGML_SLOT` when it is `NULL`, so `ggml_soft_max(ctx, a)` — which is
`ggml_soft_max_ext(ctx, a, NULL, 1.0f, 0.0f)` and what the router needs — is unreachable. This is a
**widened input domain of an existing symbol**, not a new symbol: `mask == -1` means no mask.
`moe-prereq-discharge.md` widened its arm's admitted member shape the same way and added no CLI, and
R5B correction C1 records that the cheapest new shim symbol is the one you do not add.

**`align_ggml_slot_get` is not stride-aware, and that decided the readback design.** It computes
`capacity = ggml_nbytes(tensor)` and calls `ggml_backend_tensor_get(tensor, bytes, off, n)`. For a
strided **view** — which `ffn_moe_topk-0` is, a `{8, T}` window on `{64, T}` rows — `ggml_nbytes`
spans the whole strided region and a naive read of `n_expert_used · T · 4` bytes returns the wrong
row for every token but the first. The probe made exactly this mistake, and it did not crash or
produce a shape error: it produced a plausible expert set (`t1: 39 22 4 21 47 48 17 14` instead of
`t1: 55 21 57 43 33 39 7 38`), a plausible union of 48 experts instead of 25, and an `l_out-0` that
was finite, wrong, and off by O(1). The routing-identity oracle of section 3.6 exists because of
this bug.

The design's answer is to **never read a view back**. `ffn_moe_argsort-0` is contiguous `{n_expert,
T}`; the arm reads it whole with `align_ggml_slot_get` and takes the first `n_expert_used` of each
row in Align, on bytes Align owns. No stride crosses the boundary, `align_ggml_slot_get` needs no
change, and the top-k slicing becomes reviewable Align code instead of a pointer computation in C.

What remains is five new symbols and one widened one, listed in section 3.5. Nothing else about the
boundary moves: no new allocation strategy, no new device path, no change to the slot store's
representation, and no change to `align_ggml_slot_place`, which places a 3-D stacked tensor over a
window the same way it places a 2-D one.

### 2.9 What the probes settle

1. The OLMoE layer's real node names, shapes, and order, transcribed from build 10566 rather than
   assumed — including the QK-norm's width and position (2.2 fact 1).
2. The router is a 64-way softmax gathered at eight descending-probability slots, with **no**
   renormalization (2.2 fact 2), and the top-k is `ARGSORT` + `VIEW` (2.2 fact 3).
3. Compacting the expert stack to the routed union and remapping the ids is **bit-identical** to
   llama.cpp's whole-tensor `mul_mat_id`, and needs no copy (2.3).
4. The per-`(token, slot)` `mul_mat` form is bit-identical too, but slower and `O(T)` in graph size;
   and the slot **order** of the final sum is load-bearing to the last bit (2.3).
5. The transcript oracle reaches 26 nodes and 2,376 elements at the print bound, and R5A's element
   and sum thresholds transfer unchanged (2.4).
6. Align-owned weights change no bit of a routed layer (2.5).
7. The residency win is 12.5% of the layer's expert bytes at one token and 73.4% at eighteen; it is
   a decode property (2.6).
8. The claim arithmetic and the pack agree byte-for-byte with the GGUF, and the container's
   contribution is locality, worth ~25% on the read (2.7).
9. The FFI boundary needs five new symbols and one widened one, and the top-k must be sliced in
   Align out of a contiguous `ARGSORT` rather than read back through a view (2.8).

---

## 3. Public-contract ledger

This section is authoritative. Where a row says "unchanged from R5A" it means the bytes, the code,
and the meaning are R5A's, and R5D re-raises rather than redefines.

### 3.1 The executable, and why this is an arm rather than a new binary

R5D is a fourth arm of `ggml-spike`, beside R4.5's positional arm, `--layer-forward`, and
`--model-forward`/`--model-forward-gpu`. The reason is R5A section 3.1's and R5C's, unchanged: the
arm shares the pack reader, the FFI module, the shim, the slot store, the alignment contract, the
teardown order, and the summary-block shape with three siblings, and a second binary would fork all
six. Arm selection is the first operand and nothing else, before any path work.

The new Align modules are `src/layer_olmoe.align` (the topology as data) and
`src/moe_layer_forward.align` (the arm). `src/layer_qwen2.align` is **not** extended: its
`parse_geometry` refuses `n_expert != 0` and `arch != "qwen2"` by design, and its `Geometry` record
has no `n_expert_used` and no `n_ff_exp`. Widening it would make one module the owner of two
architectures whose attention halves differ (OLMoE has QK-norm and no QKV biases; Qwen2 has biases
and no QK-norm), which is the "second architecture is a second module behind the same node-table
shape" that `r5a-dense-layer-forward.md` section 1.3 already named.

### 3.2 Hyperparameters, and where they come from

Every scalar is read from the `R1_MODEL_IR` document `r1c-olmoe-moe-ir.md` section 2.4 emits.
Nothing is hard-coded from the model, and nothing is derived from the pack.

| Field | Path in the geometry document | Value on this model |
| --- | --- | --- |
| `arch` | `model.arch` | `olmoe` |
| `n_layer` | `model.n_layer` | 16 |
| `n_embd` | `model.n_embd` | 2048 |
| `n_head` | `model.n_head` | 16 |
| `n_head_kv` | `model.n_head_kv` | 16 |
| `head_dim` | `model.head_dim` | 128 |
| `n_ff_exp` | `model.n_ff_exp` | 1024 |
| `n_vocab` | `model.n_vocab` | 50304 |
| `n_expert` | `model.n_expert` | 64 |
| `n_expert_used` | `model.n_expert_used` | 8 |
| `context_length` | `model.context_length` | 4096 |
| `rms_eps` | `model.rms_eps_bits` | `3727c5ac` |
| `rope.type` | `model.rope.type` | 2 (NEOX) |
| `rope.dim_count` | `model.rope.dim_count` | 128 |
| `rope.freq_base` | `model.rope.freq_base_bits` | `461c4000` |
| `rope.scaling_type` | `model.rope.scaling_type` | `null` |

`n_expert_used` and `n_ff_exp` are the two fields R5A's consumer does not read, and both are load
bearing here: the first is the slot count of every MoE tensor and the second is the expert planes'
inner width. `attn_scale_bits` is derived exactly as R5A derives it, `1/sqrt(head_dim)`, and is
`3db504f3` on this model — the same value R5A publishes, because both models have `head_dim` 128.

The geometry kind and version R5D consumes are the ones the code actually declares:
`kind == "R1_MODEL_IR"` and `schema_version == 2`, matching `src/layer_qwen2.align`'s
`GEOMETRY_KIND` / `GEOMETRY_SCHEMA_VERSION` constants.

The five RoPE constants R5A fixes — `ext_factor` 0.0, `attn_factor` 1.0, `beta_fast` 32.0,
`beta_slow` 1.0, `freq_scale` 1.0 — are fixed here for R5A section 3.5's reason and earned by step
9 of section 3.8, which refuses any geometry that does not declare `rope.scaling_type: null`.
`freq_scale_train` is 1 on this model, so the `linear` scaling llama.cpp prints is the identity.

### 3.3 CLI surface

```text
ggml-spike --moe-layer-forward PACK GEOM.json TOKENS
ggml-spike --moe-layer-forward PACK GEOM.json TOKENS DOC.json
ggml-spike --moe-layer-forward PACK GEOM.json TOKENS DOC.json REF.gguf
ggml-spike --moe-layer-forward PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt
ggml-spike --moe-layer-forward PACK GEOM.json TOKENS -        REF.gguf TRANSCRIPT.txt
```

Exactly five, six, seven, or eight operands. `MAX_PATH_BYTES` — non-empty, `<= 4096` bytes, no NUL —
applies to `PACK`, `GEOM`, `DOC`, `REF`, and `TRANSCRIPT` before anything is opened. `-` in the
fifth position means "document to stdout" and is R0's convention.

**There is no `LAYER` operand and the arm computes layer 0.** Section 1.3 records the cost and
section 5.4 records what adding it would take. The block indices are then fixed by
`r1c-olmoe-moe-ir.md` section 2.5.3's order: the embedding `WeightBlock` at 0, the `AttentionBlock`
at 1, the `RouterBlock` at 2, and the `ExpertBlock` of expert `e` at `3 + e`. The arm still locates
every block by `(kind, layer, required role_id)` as R5B section 3.4 does, never by computed index;
the arithmetic above is what the selection is expected to find, not how it finds it.

`TOKENS` is a comma-separated list of **1 to 6** non-negative decimal integers, no spaces, no
trailing comma, each in `[0, n_vocab)`. `MAX_PREFILL_TOKENS` is 6 for R5A section 3.3's reason: the
instrument prints every row of an axis only while its extent is `<= 6`, and an oracle that silently
compares fewer elements as the input grows is worse than one that refuses.

The summary block, in R5A's one-label-per-line shape, printed exactly when a real document path is
given. It is R5A's block with six rows added and one changed; the added rows are the ones a reader
of a routed layer needs and cannot compute from the others.

```text
moe layer forward:
status:                OK | ERROR
verdict:               EXTERNAL | COPIED | UNAVAILABLE
pack path:             <sanitized path>
schema:                1
arch:                  olmoe
layer:                 0
tokens:                <comma-separated ids>
experts routed:        <U>/<n_expert>                 # new
expert ids:            <ascending, comma-separated>   # new
expert bytes read:     <integer>                      # new
expert bytes in layer: <integer>                      # new
dense weight bytes:    <integer>
activation bytes:      <integer>
graph nodes:           <a>+<b>                        # changed: two graphs
backend:               <name>
pread ns:              <integer>
claim pread ns:        <integer>                      # new
build ns:              <integer>
compute ns:            <a>+<b>                        # changed: two graphs
l_out sha256:          <64 hex characters>
l_out bit sum:         <integer>
routing:               MATCH | MISMATCH | -           # new
reference:             IDENTICAL | MISMATCH | -
reference nodes:       <matched>/<total>, or -
transcript:            PASS | FAIL | -
transcript nodes:      <matched>/<total>, or -
max abs diff:          <integer>
max sum diff:          <integer>
released:              <integer>
error:                 <code>
detail:                <identifier>
```

Each label and its value are printed on their own line, as R5A section 3.3 records; the block is
read positionally, by line ordinal. `verdict` retains R4.5's meaning and is `EXTERNAL` only when
**every** weight tensor's data pointer — dense member and expert claim alike — lies at its own
window offset. `COPIED`, `FAIL`, and `MISMATCH` are successful runs; `status: "error"` is reserved
for section 3.8's codes.

### 3.4 The two-phase read shape

The read schedule is the capability. It is in two phases because it has to be: the set of expert
planes the layer needs is a function of the router's output, and the router's output is a function
of half the layer.

**Phase A reads, in this order, into one Align-owned `dense_window`:**

| # | Source | Members | Bytes on this model |
| --- | --- | --- | --- |
| 1 | embedding `WeightBlock`, `role_id` 12 | `token_embd`, **row-gathered**: one `pread` of `row_bytes` per token at `member.pack_offset + id * row_bytes` | 6,912 |
| 2 | `AttentionBlock` at layer 0 | `attn_norm`(0), `attn_q`(1), `attn_q_norm`(27), `attn_k`(3), `attn_k_norm`(28), `attn_v`(5), `attn_output`(7) — one `pread` of `block.pack_bytes` | 10,543,104 |
| 3 | `RouterBlock` at layer 0 | `ffn_norm`(8), `router`(17) — one `pread` of `block.pack_bytes` | 532,480 |

`row_bytes = token_embd.nbytes / n_vocab` must divide exactly and be a positive multiple of
`type_size`; the whole member is 148,635,648 bytes on this model and R5D reads 6,912 of them, which
is R5A section 2.5's finding applied unchanged. Each member is copied to a `block_align`-aligned
window offset rather than used at its interior offset, so every pointer handed to ggml is
`MAX_TENSOR_ALIGNMENT`-aligned by construction. Total dense window content: **11,082,496 bytes**.

**Between the phases, Align decides.** In order, on bytes Align owns:

1. Read `ffn_moe_argsort` back whole with `align_ggml_slot_get`. It is contiguous
   `{n_expert, T}` i32. **No view is ever read back**, for section 2.8's reason.
2. `topk_ids[t][s] = argsort[t][s]` for `s` in `[0, n_expert_used)` — the slice is Align's, not a
   ggml view's.
3. Every id must satisfy `0 <= id < n_expert`, and the `n_expert_used` ids of one token must be
   pairwise distinct. → `R5D_EXPERT_ID`.
4. `routed[]` is the **ascending** distinct union of `topk_ids`, `U = routed.len()`, bounded by
   `min(n_expert, n_expert_used * T)`.
5. `compact_ids[t][s] = position of topk_ids[t][s] in routed[]` — a bijection onto `[0, U)`,
   verified rather than assumed.
6. `claim_window_bytes = U * (align_up(gate_plane, block_align) + align_up(up_plane, block_align)
   + align_up(down_plane, block_align))`, refused above `MAX_CLAIM_WINDOW_BYTES = 2^33` before a byte
   is reserved. → `R5D_CLAIM_BUDGET`.

**Phase B reads, into three Align-owned windows, one per expert role:**

For each `u` in `[0, U)` in ascending order, the `ExpertBlock` at `(kind = ExpertBlock, layer = 0,
expert = routed[u])` is located and its three claim members — `ffn_gate_exps`(19),
`ffn_up_exps`(21), `ffn_down_exps`(23) — are read with one `pread` of `block.pack_bytes` and
scattered to `gate_window + u * gate_stride`, `up_window + u * up_stride`,
`down_window + u * down_stride`.

**The scatter is the whole "restacking" cost, and it is zero.** Section 2.3 established that a
stacked 3-D tensor over `U` planes is `U` plane-sized regions laid end to end. Choosing the
destination offset is not a copy, so the three windows *are* the three `mul_mat_id` operands with no
intermediate. Each window's base and each plane's offset are `block_align`-aligned, so
`ne2`-strided access stays `MAX_TENSOR_ALIGNMENT`-aligned.

A block whose expert is `routed[u]` but which is missing one of the three roles, or whose claim's
`slice_index` is not `routed[u]`, is `R5D_CLAIM_MISSING`. The `slice_index`/`slice_count` pair is
validated by `moe-prereq-discharge.md` section 1.1's steps 7a and 7b, unchanged and re-raised as
`R4_5_SLICE`.

On this model at `T = 6`: `U = 25`, `gate_plane` = `up_plane` = 1,179,648, `down_plane` =
1,720,320, and the three windows hold **101,990,400 bytes** against the layer's **261,095,424**.

### 3.5 The graph as Align-owned data — two node tables, and the FFI boundary

`src/layer_olmoe.align` owns two node tables with R5A's column shape (`id`, `op`, `out_slot`,
`a_slot`, `b_slot`, `c_slot`, four shape parameters, a scalar-bits parameter, a `transcript_name`,
and an `oracle` class). It contains no `extern` and no `unsafe`.

**Phase A — thirty-one rows**, in order: `embd` (get_rows) → `norm` (rms_norm) → `attn_norm` (mul) →
`q_pre` (mul_mat) → `q_norm` (rms_norm) → `q_normed` (mul) → reshape_3d → rope_neox → the same six
for K → `v_cur` (mul_mat) → reshape_3d → two permutes → `kq` (mul_mat) → `kq_soft_max`
(soft_max_ext, masked) → permute → cont_3d → `kqv` (mul_mat) → permute → `kqv_out` (cont_2d) →
`attn_out` (mul_mat) → `ffn_inp` (add) → `norm` (rms_norm) → `ffn_norm` (mul) → `ffn_moe_logits`
(mul_mat) → `ffn_moe_probs` (soft_max_ext, **unmasked**) → `ffn_moe_argsort` (argsort, descending).

**The Q/K order is normative and is section 2.2 fact 1's:** `rms_norm` over `ne[0] == n_embd`, then
the scale, then the reshape to `{head_dim, n_head, T}`, then RoPE. A table that reshapes before
normalizing type-checks, runs, and is wrong.

**Phase B — twenty-four rows**: `probs_r` (reshape_3d to `{1, n_expert, T}`) → `ffn_moe_weights`
(get_rows over `topk_ids`) → `ffn_norm_r` (reshape_3d to `{n_embd, 1, T}`) → `ffn_moe_gate`
(mul_mat_id over the gate window with `compact_ids`) → `ffn_moe_up` (mul_mat_id) →
`ffn_moe_swiglu` (swiglu_split) → `ffn_moe_down` (mul_mat_id over the down window) →
`ffn_moe_weighted` (mul) → eight `view_2d` rows → seven `add` rows, the last named `ffn_moe_out` →
`l_out` (add against the carried `ffn_inp`).

**The eight views and seven adds are in ascending slot order, and that is normative**, for section
2.3's measurement: reversing it changes 1,189 of 2,048 elements. The table encodes the order; no
loop direction is free to choose it.

Four values cross from phase A to phase B, written into ggml-owned input tensors with
`align_ggml_slot_set` exactly as R5B section 3.6 carries its residual: `ffn_norm` `{n_embd, T}` f32,
`ffn_inp` `{n_embd, T}` f32, `ffn_moe_probs` `{n_expert, T}` f32, and `topk_ids` / `compact_ids`
`{n_expert_used, T}` i32. On this model that is 98,304 + 1,536 + 384 bytes. **The router's decision
is an input to phase B, not a node in it**, which is what lets phase B's table be a constant table
over a data-dependent `U`.

`U` is the only data-dependent shape parameter. It enters the three `slot_new_tensor_3d` rows as
`ne2` and nowhere else; every other extent is a geometry field.

**The FFI boundary — five new symbols and one widened one.** Section 2.8 verified each against the
two C files at the pin.

| Symbol | Form | Why |
| --- | --- | --- |
| `align_ggml_op_argsort` | `int32_t (void *ctx, void *slots, int64_t out, int64_t a, int32_t order)` | `order` is `0` ascending / `1` descending, validated; anything else is `ALIGN_GGML_INIT`. `ggml_top_k` is deliberately **not** wrapped, for section 2.2 fact 3's reason |
| `align_ggml_op_mul_mat_id` | `int32_t (void *ctx, void *slots, int64_t out, int64_t as, int64_t b, int64_t ids)` | three slot indices, each checked by the existing prologue |
| `align_ggml_op_view_2d` | `int32_t (void *ctx, void *slots, int64_t out, int64_t a, int64_t ne0, int64_t ne1, int32_t nb1_dim, int32_t offset_dim, int64_t offset_index)` | `nb1 = a->nb[nb1_dim]` and `offset = offset_index * a->nb[offset_dim]`, both dimension **selectors** in `[0, 3]`, never byte counts. Align therefore cannot compute a stride or forge an offset, and the view's extent is checked against `a`'s nbytes in C |
| `align_ggml_slot_new_tensor_3d` | `int32_t (void *ctx, void *slots, int64_t out, int32_t type, int64_t ne0, int64_t ne1, int64_t ne2)` | mirrors `align_ggml_slot_new_tensor_2d`, same operand-table gate, `ne2 >= 1` |
| `align_ggml_slot_new_i32_2d` | `int32_t (void *ctx, void *slots, int64_t out, int64_t ne0, int64_t ne1)` | mirrors `align_ggml_slot_new_i32_1d`; the operand table has no I32 row and must not gain one (section 2.8) |
| `align_ggml_op_soft_max_ext` | **widened**: `mask == -1` means no mask | `ggml_soft_max_ext(ctx, a, NULL, scale, bias)`, which the router needs and which the current `sm == NULL -> ALIGN_GGML_SLOT` check makes unreachable. A widened input domain of an existing symbol, in `moe-prereq-discharge.md`'s style, not a new symbol |

The table's five new rows plus the widened sixth are the complete boundary change. Every one is
added to **both** `scripts/ggml_shim.c` and
`scripts/ggml_shim_stub.c`, and the `BEGIN/END R4.5 SHARED SHIM CONTRACT` region stays byte-identical
between them, which `scripts/run-layer-forward-smoke` already asserts.

`MAX_NODE_SLOTS` stays 128. The two phases share one slot store; phase A's high water is the dense
members plus its inputs plus its nodes, phase B's is the three stacked tensors plus its four carried
inputs plus its nodes, and the arm publishes the maximum.

### 3.6 The three oracles, and the tolerances fixed before the qualification

**Oracle 1 — bit-exact self-reference.** Present in the seven- and eight-operand forms. Both graphs
are built a second time in a second context with every weight tensor — the ten dense members and the
three stacked expert windows — allocated by `ggml_backend_alloc_ctx_tensors` and filled from the
same Align windows with `ggml_backend_tensor_set`. The reference arm asserts that its tensors' data
pointers are **not** the windows', so it cannot pass by aliasing. Every oracle node's bytes must be
byte-identical between the arms. Section 2.5 measured 28 of 28.

Before either graph runs, the pack bytes of every dense member and every read claim are compared
byte-for-byte against the source GGUF at `member.source_offset`; a difference is
`R5_SOURCE_DIVERGED` and stops the arm. Section 2.7 measured identity over all 101,990,400 claim
bytes.

**Oracle 2 — routing identity, new in R5D.** Present in the eight-operand form. The `n_expert_used ·
T` ids Align sliced out of `ffn_moe_argsort` must equal the transcript's `ffn_moe_topk-0` block:
every **printed** id exactly, and the block's exact integer sum. Section 2.2 fact 6 records that the
slot axis is 8 and the instrument prints six of eight, so the direct comparison covers 36 of 48 ids
and the sum pins the other twelve in aggregate. The document reports
`routing.ids_printed_compared`, `routing.ids_total`, and `routing.sum_matches` so a reader sees the
coverage rather than inferring it.

A disagreement is `routing.verdict: "MISMATCH"` and a **successful run**, reported as data — with
one exception. If the routing disagrees, oracle 3 is still evaluated and reported, because a
transcript comparison against a differently-routed layer is exactly the diagnostic a reader needs.
This oracle exists because of the bug section 2.8 records: a wrong routing produces finite,
plausible, wrong numbers, and every shape check in the design passes.

**Oracle 3 — the transcript, with R5A's tolerances unchanged.** Present in the eight-operand form.
The transcript is scanned with `r2a-expert-trace.md` section 2.2's line grammar, reusing
`src/expert_trace.align`'s scanner. Twenty-six nodes are matched.

| `nodes[].id` | transcript name | transcript op | shape |
| --- | --- | --- | --- |
| `embd` | `embd` | `GET_ROWS` | `{n_embd, T}` |
| `attn_norm` | `attn_norm-0` | `MUL` | `{n_embd, T}` |
| `q_pre` | `Qcur-0` | `MUL_MAT` | `{n_embd, T}` |
| `q_normed` | `Qcur_normed-0` | `MUL` | `{n_embd, T}` |
| `q_rope` | `Qcur-0` | `ROPE` | `{head_dim, n_head, T}` |
| `k_pre` | `Kcur-0` | `MUL_MAT` | `{n_embd, T}` |
| `k_normed` | `Kcur_normed-0` | `MUL` | `{n_embd, T}` |
| `k_rope` | `Kcur-0` | `ROPE` | `{head_dim, n_head, T}` |
| `v_cur` | `Vcur-0` | `MUL_MAT` | `{n_embd, T}` |
| `kqv` | `kqv-0` | `MUL_MAT` | `{head_dim, T, n_head}` |
| `kqv_out` | `kqv_out-0` | `CONT` | `{n_embd, T}` |
| `attn_out` | **matched by source weight** `blk.0.attn_output.weight` | `MUL_MAT` | `{n_embd, T}` |
| `ffn_inp` | `ffn_inp-0` | `ADD` | `{n_embd, T}` |
| `ffn_norm` | `ffn_norm-0` | `MUL` | `{n_embd, T}` |
| `ffn_moe_logits` | `ffn_moe_logits-0` | `MUL_MAT` | `{n_expert, T}` |
| `ffn_moe_probs` | `ffn_moe_probs-0` | `SOFT_MAX` | `{n_expert, T}` |
| `ffn_moe_argsort` | `ffn_moe_argsort-0` | `ARGSORT` | `{n_expert, T}` |
| `ffn_moe_topk` | `ffn_moe_topk-0` | `VIEW` | `{n_expert_used, T}` |
| `ffn_moe_weights` | `ffn_moe_weights-0` | `GET_ROWS` | `{1, n_expert_used, T}` |
| `ffn_moe_gate` | `ffn_moe_gate-0` | `MUL_MAT_ID` | `{n_ff_exp, n_expert_used, T}` |
| `ffn_moe_up` | `ffn_moe_up-0` | `MUL_MAT_ID` | `{n_ff_exp, n_expert_used, T}` |
| `ffn_moe_swiglu` | `ffn_moe_swiglu-0` | `SWIGLU` | `{n_ff_exp, n_expert_used, T}` |
| `ffn_moe_down` | `ffn_moe_down-0` | `MUL_MAT_ID` | `{n_embd, n_expert_used, T}` |
| `ffn_moe_weighted` | `ffn_moe_weighted-0` | `MUL` | `{n_embd, n_expert_used, T}` |
| `ffn_moe_out` | `ffn_moe_out-0` | `ADD` | `{n_embd, T}` |
| `l_out` | `l_out-0` | `ADD` | `{n_embd, T}` |

Three classes are **excluded by contract**, each with its own document value in `nodes[].oracle`, so
every exclusion is a field rather than a silent gap:

- `kq-0` and `kq_soft_max-0` — `"shape_incomparable"`, R5A section 3.6's reason unchanged: the
  instrument's `n_kv` is a padded cache width and R5D has no cache.
- the four `norm-0` nodes — `"ambiguous_name"`, section 2.2 fact 5's reason: an OLMoE layer prints
  four different tensors under one name, and each is proved by its unique `MUL` consumer, which
  **is** compared.
- the eight `ffn_moe_weighted-0 (view)` nodes and `node_56` … `node_61` —
  `"unstable_name"`, section 2.2 fact 4's reason. `ffn_moe_out-0`, the chain's last add, is
  compared.

A node matches when the transcript's declared shape equals the node's computed shape; a shape
disagreement is `R5_ORACLE_SHAPE`. A named node absent from the transcript is `R5_ORACLE_MISSING`.
Both are error codes, for R5A section 3.8's reason: an oracle that silently compares nothing is the
failure mode this design most needs to avoid.

**The thresholds are R5A section 3.6's, reused unchanged and re-justified against R5D's own
measurement.**

| Comparison | Threshold | R5D's measurement |
| --- | --- | --- |
| element | `\|round(x · 10^4) - printed_ten_thousandths\| <= 1` | max `\|Δ\|` **5.0e-5** over 2,376 elements and 26 nodes, which is the `%12.4f` print bound: every element agreed to the last digit printed (section 2.4) |
| sum | `\|Δ\| <= max(1.0e-3, 1.0e-5 · \|Σ\|)` in millionths, against a **sequential f32 accumulation in element order** | worst absolute residual **3.0e-5** (`ffn_moe_logits`), worst relative **5.35e-7** (`ffn_moe_swiglu`); the rule clears them by 33× and 19× (section 2.4) |
| integer node (`ffn_moe_argsort`, `ffn_moe_topk`) | **exact**, both the printed elements and the block sum | 36 of 36 printed ids and both sums exact (section 2.4) |

Both float comparisons are integer comparisons and neither renders a float, for
`r4-alignpack-layer-major.md` section 2.3's reason: the transcript's `-0.0190` is parsed to `-190`
and the computed f32 is converted with `(x * 10000.0).round() as i64`. An i32 node's elements are
parsed with `r2a-expert-trace.md` section 2.2 finding 5's rule — reject a leading `-`, require the
fractional part all `0`, parse the integral part with the bounded integer parse — and a violation is
`R2_EXPERT_ID_NOT_INTEGRAL`, re-raised verbatim.

The document reports `oracle.max_abs_diff_ten_thousandths` and `oracle.max_sum_diff_millionths` as
integers whether the verdict is `PASS` or `FAIL`, so a regression is a number that moved rather than
a boolean that flipped.

### 3.7 `R5_MOE_LAYER_FORWARD`, `schema_version: 1`

Canonical UTF-8 JSON in declaration order, in the R0/R1/R2A/R4/R4.5/R5A shape. Fields identical to
R5A's carry R5A's meaning.

```text
schema_version    1
kind              "R5_MOE_LAYER_FORWARD"
pack_path         string
geometry_path     string
reference_path    string, "" when the reference arm did not run
transcript_path   string, "" when the transcript arm did not run
status            "ok" | "error"
error_code        string, "" when ok
error_detail      string, "" when ok
verdict           "EXTERNAL" | "COPIED" | "UNAVAILABLE"

pack        format_version, block_align, member_align, block_count, member_count,
            total_bytes, payload_offset, reader_pread_count, reader_bytes_read
model       arch, n_layer, n_embd, n_head, n_head_kv, head_dim, n_ff_exp, n_vocab,
            n_expert, n_expert_used, context_length, rms_eps_bits, rope_type,
            rope_dim_count, rope_freq_base_bits, attn_scale_bits
selection   layer, embedding_block_index, attention_block_index, router_block_index,
            token_count, tokens[]
members[]   role, role_id, name, ggml_type, ne0, ne1, nbytes, blck_size, type_size,
            pack_offset, window_offset, window_alignment, tensor_data_offset,
            pointer_identity (bool), read_bytes, pread_count
routing     expert_ids[][]          # [token][slot], the global ids, in slot order
            routed[]                # the ascending distinct union
            routed_count            # U
            compact_ids[][]         # [token][slot], remapped into [0, U)
            slot_order_normative (bool, always true)
claims[]    expert, block_index, role, role_id, name, ggml_type, ne0, ne1, ne2,
            slice_index, slice_count, nbytes, pack_offset, window_offset,
            plane_stride, pointer_identity (bool), read_bytes, pread_count
residency   expert_bytes_read, expert_bytes_in_layer, expert_bytes_read_ppm,
            dense_bytes_read, planes_read, planes_in_layer,
            claim_pread_count, block_pread_count
graph_a     node_count, table_rows, weight_bytes, activation_bytes, context_bytes,
            compute_status
graph_b     node_count, table_rows, weight_bytes, activation_bytes, context_bytes,
            compute_status
graph       slot_capacity, slot_high_water, backend_name, carried_bytes
nodes[]     id, phase ("a" | "b"), op, transcript_name, transcript_op,
            ne0, ne1, ne2, ne3, element_count, ggml_type,
            sha256 (64 hex), bit_sum, f32_sum_millionths, nonfinite_count,
            oracle ("compared" | "shape_incomparable" | "ambiguous_name"
                    | "unstable_name" | "absent")
output      sha256 (64 hex), bit_sum, element_count, nonfinite_count      # l_out
reference   present (bool), verdict, nodes_compared, nodes_identical,
            first_difference_node, first_difference_index,
            first_difference_primary_bits, first_difference_reference_bits
routing_oracle
            present (bool), verdict ("MATCH" | "MISMATCH"), instrument,
            ids_total, ids_printed_compared, ids_printed_matched,
            sum_expected, sum_observed, sum_matches (bool),
            first_difference_token, first_difference_slot
oracle      present (bool), verdict, instrument, nodes_expected, nodes_matched,
            elements_compared, max_abs_diff_ten_thousandths, max_sum_diff_millionths,
            tolerance_ten_thousandths, sum_tolerance_millionths,
            sum_tolerance_relative_ppm, worst_node, worst_element_index,
            transcript_lines, transcript_callback_lines
timings     pread_ns, claim_pread_ns, decide_ns, build_a_ns, build_b_ns,
            reserve_ns, compute_a_ns, compute_b_ns, reference_compute_ns,
            oracle_ns, elapsed_ns
lifetime    ggml_buffers_created, ggml_buffers_freed, contexts_created, contexts_freed,
            backends_created, backends_freed, graphs_created, gallocrs_created,
            gallocrs_freed, released_before_owner_scope_end (bool)
abi         tensor_alignment, table_drift, slot_magic_ok (bool), fp_contract_off (bool),
            graph_context_bytes
```

**`routing` is the capability's real output and it is published before any oracle runs.** A reader
who has no transcript still learns exactly which experts the six tokens reached, in slot order, and
can reproduce the union. `slot_order_normative` is a constant `true` and exists so a future format
that relaxes the order has to change a field rather than a comment.

**`claims[].ne0`, `.ne1`, and `.ne2` are the dims of the tensor R5D *built*** — `ne2` is `U`, the
compact stack's depth — while `slice_index` and `slice_count` are the member record's own, verbatim.
The member record's third dim is `n_expert`; the built tensor's is `U`, and a reader that conflated
them would misread every `plane_stride`.

**`residency` is the measurement.** `expert_bytes_read` against `expert_bytes_in_layer` is section
2.6's number for this run, and `planes_read`/`planes_in_layer` is the same ratio in planes.
`expert_bytes_read_ppm` is the ratio in parts per million as an integer, because this repository has
no float formatting contract.

**`nodes[]` carries `phase`** so the two graphs are distinguishable without knowing the tables, and
`ggml_type` so an i32 node's `sha256` and `bit_sum` are interpretable. Checksums are never floats:
`sha256` is `crypto.sha256` over the exact little-endian bytes, `bit_sum` is the `i64` sum of the u32
bit patterns, and `f32_sum_millionths` is section 3.6's sequential accumulation scaled by 10^6 —
emitted as `0` for an i32 node, whose `bit_sum` **is** its sum.

`graph_a.node_count` and `graph_b.node_count` are ggml's own counts from
`align_ggml_graph_node_count`; `table_rows` is the node table's, 31 and 24. **They are different
numbers**, because ggml materializes some rows as nodes and folds others, and publishing only one of
them would make the slot-capacity budget unauditable. Section 2.3's probe measured 35 and 22 ggml
nodes, at a phase boundary drawn three rows later than section 3.5's: the probe computed
`ffn_moe_weights` and the two reshapes in phase A, and the design computes them in phase B, where
they belong beside the operands they feed.

**Four fields the shipped document carries that this list first omitted** are named here rather
than left to a reader of the JSON (correction C14). `pack.reader_pread_count` and
`pack.reader_bytes_read` are `alignpack_read`'s own counters, published for R4's reason: a
container read that costs more syscalls than it should is visible before any timing is.
`oracle.transcript_lines` and `oracle.transcript_callback_lines` are the scanner's view of the file
it was handed — total lines, and how many of them were instrument records — so an oracle that
matched nothing because it was given the wrong file is distinguishable from one that matched
nothing because the numbers disagreed. All four are producer-owned counters and none is compared.

`schema_version` is `1` and nominal. A consumer keys on `kind` plus `schema_version`.

### 3.8 Validation order and error codes

First applicable row wins. Steps 1 and 2 return `Err` with no output at all. Steps 3 onward produce
a `status: "error"` document and then map to `Err(Error.Invalid)`. **No ggml state is created before
step 16, and nothing outside the process is ever written.** Steps 1–15 are therefore fully reachable
under the stub, without ggml, without a model, and without a transcript.

R5D reuses R5A's `R5_*` ladder verbatim wherever the check is literally R5A's, and owns an `R5D_`
prefix for the five faults that are new — the same split `r5c-metal-prefill.md` makes with its three
`R5C_` codes.

1. Arm selection and exact arity — five to eight operands. → `R5D_ARITY`
2. Lexical path validation of every path operand; `-` in position five is not a path. → `R5D_PATH`
3. `TOKENS` parses: 1–6 non-negative decimal integers, comma-separated, no spaces. → `R5_TOKENS`
4. Geometry document open and read. → `R5_GEOMETRY_UNREADABLE`
5. Geometry parses as JSON and carries `kind == "R1_MODEL_IR"`, `schema_version == 2`.
   → `R5_GEOMETRY`, detail `kind` / `schema_version`
6. Every consumed `model` field of section 3.2 is present and in range. → `R5_GEOMETRY`, detail the
   field name
7. Geometry self-consistency: `n_embd == n_head * head_dim`, `n_head == n_head_kv` (OLMoE is MHA),
   `n_expert >= 1`, `1 <= n_expert_used <= n_expert`, `n_ff_exp >= 1`. → `R5_GEOMETRY`, detail the
   relation
8. Architecture preconditions: `arch == "olmoe"`, `rope.type == 2`, `rope.dim_count == head_dim`,
   `rope.scaling_type == null`. → `R5_GEOMETRY`. **This step is what earns section 3.2's five fixed
   RoPE constants.**
9. `n_layer >= 1`, every token id `< n_vocab`. → `R5_INDEX` / `R5_TOKENS`
10. Pack open and header decode, then region validation. → `R4_PACK_*` verbatim
11. Block selection for phase A: an embedding `WeightBlock`, an `AttentionBlock` at layer 0, a
    `RouterBlock` at layer 0, each matching exactly once by `(kind, layer, required role_id)`. →
    `R5_BLOCK_MISSING` / `R5_BLOCK_AMBIGUOUS`, detail the kind and layer
12. Expert-block coverage: an `ExpertBlock` exists at `(layer 0, expert e)` for every `e` in
    `[0, n_expert)`, exactly once each. → `R5D_CLAIM_MISSING`, detail `expert[<n>]`. **Checked
    before phase A runs**, because discovering a missing expert after the router has chosen it would
    make a container defect look like a routing defect.
13. Member selection by `role_id` for phase A: `token_embd`(12); `attn_norm`(0), `attn_q`(1),
    `attn_q_norm`(27), `attn_k`(3), `attn_k_norm`(28), `attn_v`(5), `attn_output`(7); `ffn_norm`(8),
    `router`(17). → `R5_MEMBER_MISSING`, detail the role
14. Member shapes against the geometry, each exactly: `token_embd` `[n_embd, n_vocab]`,
    `attn_q`/`attn_k`/`attn_v` `[n_embd, n_head * head_dim]`, `attn_output` `[n_embd, n_embd]`,
    `router` `[n_embd, n_expert]`, and `attn_norm`/`attn_q_norm`/`attn_k_norm`/`ffn_norm` 1-D at
    `n_embd`. And `row_bytes = token_embd.nbytes / n_vocab` divides exactly and is a positive
    multiple of `type_size`. → `R5_SHAPE`, detail the role; a router that is not `[n_embd,
    n_expert]` is `R5D_ROUTER_SHAPE`, detail `ne0[<n>]` / `ne1[<n>]`, because a router of the wrong
    width silently produces a valid softmax over the wrong number of experts
15. Window availability and reads for phase A. → `R4_WINDOW_UNAVAILABLE` / `R4_PACK_UNREADABLE`
16. `align_ggml_available()`. → `R5_GGML_UNAVAILABLE`, `verdict: "UNAVAILABLE"`. **This is where the
    stub shim stops.**
17. `align_ggml_tensor_alignment()` and `align_ggml_table_drift()`. → `R5_ABI`, detail the constant
18. `align_ggml_type_ok(type, ne0)` for the ten dense members and the three claim types. →
    `R5_TYPE_UNSUPPORTED`, detail `role[type]`; `ne0 % blck_size != 0` → `R5_SHAPE`
19. Alignment, before any call that can assert: every window base and every member and plane offset
    is `0 mod tensor_alignment`. → `R5_ALIGNMENT`, detail the role
20. Backend, contexts, slot store, and phase-A graph creation. → `R5_GGML_INIT`, detail the object
21. Phase-A node-table walk: every slot index in range, every source slot non-empty. → `R5_SLOT`,
    detail `node[<id>]`
22. Phase-A `ggml_gallocr` reserve and allocate. → `R5_ALLOC`, detail `reserve_a` / `alloc_a`
23. Phase-A compute. → `R5_COMPUTE`, detail `status[<n>]`
24. Read back `ffn_moe_argsort` and slice the top-k. Every id in `[0, n_expert)` and the
    `n_expert_used` ids of a token pairwise distinct. → `R5D_EXPERT_ID`, detail
    `token[<t>]slot[<s>]`
25. Build `routed[]` and `compact_ids`; the remap must be a bijection onto `[0, U)`. →
    `R5D_EXPERT_ID`, detail `remap`
26. `claim_window_bytes <= MAX_CLAIM_WINDOW_BYTES`. → `R5D_CLAIM_BUDGET`, detail `bytes[<n>]`
27. Claim selection and reads: for each `routed[u]`, the `ExpertBlock`'s three roles present, each
    with `slice_index == routed[u]` and `slice_count == n_expert`, its `slice` pair well formed, and
    its dims `[n_embd, n_ff_exp]` / `[n_embd, n_ff_exp]` / `[n_ff_exp, n_embd]`. →
    `R5D_CLAIM_MISSING` / `R4_5_SLICE` / `R5_SHAPE`
28. Phase-B graph creation, node-table walk, reserve, allocate, compute. → `R5_GGML_INIT` /
    `R5_SLOT` / `R5_ALLOC`, detail `reserve_b` / `alloc_b` / `R5_COMPUTE`
29. Reference arm (seven- and eight-operand forms): open the GGUF; read each dense member at
    `source_offset` and each read claim at `source_offset` — where `source_offset` is already the
    claimed absolute offset, per `moe-prereq-discharge.md` section 1.1. → `R5_SOURCE_UNREADABLE`
30. Reference arm: pack bytes equal GGUF bytes, per member and per claim. → `R5_SOURCE_DIVERGED`,
    detail `role@<offset>` or `expert[<e>]role@<offset>`
31. Reference arm: build both graphs, compute, compare every oracle node bit-exactly. →
    `R5_REFERENCE_MISMATCH`, detail `node[<id>]@<index>`
32. Transcript arm (eight-operand form): open, scan, match. → `R5_TRANSCRIPT`, `R5_ORACLE_MISSING`,
    `R5_ORACLE_SHAPE`, `R2_EXPERT_ID_NOT_INTEGRAL`
33. Transcript arm: routing identity, then section 3.6's thresholds. Neither a routing mismatch nor
    a tolerance breach is an error code; both set a verdict and report numbers
34. Teardown in section 3.9's order, then render, then write

| Code | Meaning | Step | Detail |
| --- | --- | --- | --- |
| `R5D_ARITY` | wrong arm or operand count | 1 | `N/A` — no document exists |
| `R5D_PATH` | a path operand is empty, too long, or contains NUL | 2 | `N/A` — no document exists |
| `R5D_ROUTER_SHAPE` | `ffn_gate_inp` is not `[n_embd, n_expert]` | 14 | `ne0[<n>]` / `ne1[<n>]` |
| `R5D_EXPERT_ID` | a routed id is out of range, a token's ids repeat, or the compaction is not a bijection | 24, 25 | `token[<t>]slot[<s>]` / `remap` |
| `R5D_CLAIM_BUDGET` | the routed union's windows exceed `MAX_CLAIM_WINDOW_BYTES` | 26 | `bytes[<n>]` |
| `R5D_CLAIM_MISSING` | an `ExpertBlock` is absent or lacks one of its three roles, or a claim's `slice_index` is not its expert | 12, 27 | `expert[<n>]` / `expert[<n>]role[<name>]` |
| `R5_TOKENS`, `R5_INDEX`, `R5_GEOMETRY*`, `R5_BLOCK_*`, `R5_MEMBER_MISSING`, `R5_SHAPE`, `R5_GGML_*`, `R5_ABI`, `R5_TYPE_UNSUPPORTED`, `R5_ALIGNMENT`, `R5_SLOT`, `R5_ALLOC`, `R5_COMPUTE`, `R5_SOURCE_*`, `R5_REFERENCE_MISMATCH`, `R5_TRANSCRIPT`, `R5_ORACLE_*` | R5A's, unchanged | as above | R5A's |
| `R4_PACK_*`, `R4_WINDOW_UNAVAILABLE`, `R4_5_SLICE` | re-raised verbatim from the reader and the MoE prerequisite | 10, 15, 27 | theirs |
| `R2_EXPERT_ID_NOT_INTEGRAL` | an i32 transcript element is not integral | 32 | R2A's |

**`R5D_EXPERT_ID` is the code that would otherwise not exist**, and it is the answer to section
2.8's bug. Without it, a routing decision read through a stride produces ids that are in range,
distinct within a token, and wrong — and every downstream check passes. The pairwise-distinct check
is what catches it: reading `{8, T}` out of a `{64, T}` row's stride yields ranks 8–15 of token 0
for token 1, which are distinct, and yields a repeat only sometimes. The bijection check at step 25
and the routing oracle at step 33 close the rest.

### 3.9 Ownership, allocation, lifetime, and bounded memory

| Module | Owns | Imports |
| --- | --- | --- |
| `src/alignpack_read.align` | the v1 reader and its `R4_PACK_*` codes | `std.fs` — unchanged by R5D |
| `src/ggml_ffi.align` | the only `extern` and the only `unsafe` in the repository; the five new symbols and the widened one | nothing new |
| `src/layer_olmoe.align` | the two node tables, the member and claim role tables, the shape rules, the scalar derivations, the routing decision, and `R5_GEOMETRY`'s olmoe details | `core.json` for the geometry |
| `src/moe_layer_forward.align` | the arm: operands, the two-phase schedule, the windows, the three oracles, the document, the summary block | the four above |
| `scripts/ggml_shim.c` / `_stub.c` | the C side of the boundary, with the shared contract region byte-identical | ggml, or nothing |

**Four Align-owned windows**, all `buffer`, all released before the owner scope ends:
`dense_window` (11,082,496 B of content on this model), `gate_window`, `up_window`, `down_window`
(29,491,200 + 29,491,200 + 43,008,000 B at `U = 25`). The claim windows are reserved **after** the
routing decision and sized from `U`, which is why `MAX_CLAIM_WINDOW_BYTES` is checked at step 26 and
not earlier.

Teardown order is R4.5's, extended for the second graph and the three extra buffers: gallocr B,
graph B context, gallocr A, graph A context, reference contexts and buffers, the four host buffers'
ggml views, the input context, the backend, then the Align buffers. `lifetime.*` counts every
constructor and destructor and `released_before_owner_scope_end` is asserted, exactly as R5A does.

Peak resident weight bytes are `dense_window + claim_windows`, **113,072,896 B** at `T = 6` on this
model, against **272,171,008 B** for the layer's full weight set. That is the number the capability
exists to produce, and section 2.6 is the honest reading of it.

### 3.10 Ledger dimensions

| Dimension | Answer |
| --- | --- |
| Exact commands and operands | Section 3.3 |
| Inputs and defaults | Section 3.2 (geometry), 3.3 (operands); no environment input, no build option |
| Results, statuses, errors, precedence | Section 3.7 (document), 3.8 (first-applicable-row ladder) |
| Ownership, lifetime, allocation, cleanup | Section 3.9 |
| Text and wire boundary | Canonical UTF-8 JSON, declaration order, no float rendered anywhere; integer comparisons only (3.6) |
| Persisted/cache identity | `kind` + `schema_version` nominal; `sha256` over exact little-endian bytes (3.7) |
| Schema version | `R5_MOE_LAYER_FORWARD` v1; consumer keys on `kind` + `schema_version` |
| Validation order | Section 3.8, steps 1–34 |
| Prerequisites | alignpack v1 with claim members (`moe-prereq-discharge.md`); `R1_MODEL_IR` v2 olmoe geometry; ggml 0.21 CPU |
| Acceptance evidence | Section 5.1 (owner), 5.2 (qualification) |
| Metrics | Section 5.3 |
| Minimum tool/platform versions | ggml 0.21.0, llama.cpp build 10566, Align `3a34febe`; section 5.6 records the version risk |
| Milestones not consuming a later slice | Sections 1.3 and 5.4: no loader, no decode, no model, no GPU, no `LAYER` |
| Runtime-inspection fields | `graph_*.node_count`, `slot_high_water`, `abi.*` — producer-owned counters, no reflection |

---

## 4. Closure matrix

Construction, success, failure, malformed input, early exit, and cleanup for each affected module.
Each cell names its implementation and its regression case. Cases are `scripts/run-layer-forward-smoke`'s
fourth block unless marked **(Q)** for the named qualification of section 5.2.

### 4.1 `src/layer_olmoe.align` — the topology as data

| Cell | Implementation | Case |
| --- | --- | --- |
| construction | `parse_geometry` builds `Geometry` from the `R1_MODEL_IR` v2 document | `moe-geometry-ok` |
| success | both node tables walk, every slot index in range | `moe-forward-ok` |
| failure | `R5_GEOMETRY` for each consumed field and each relation of steps 5–8 | `moe-geometry-*`, one case per detail |
| malformed input | non-JSON, wrong `kind`, wrong `schema_version`, `n_expert == 0`, `n_expert_used > n_expert`, `arch != "olmoe"`, `rope.scaling_type != null` | `moe-geometry-*` |
| early exit | first applicable row wins; a geometry fault emits no ggml call | `moe-geometry-precedence` |
| cleanup | pure data, no allocation beyond the decoded document | covered by `lifetime.*` |
| routing decision | the top-k slice, the ascending union, and the bijection | `moe-routing-ok`, `moe-routing-id-range`, `moe-routing-id-repeat`, `moe-routing-remap` |
| slot order | the eight view rows and seven add rows are table-ordered | `moe-slot-order` compares against the golden `ffn_moe_out` digest |

### 4.2 `src/ggml_ffi.align` and the two C files — the boundary

| Cell | Implementation | Case |
| --- | --- | --- |
| construction | five new `extern` declarations and their `op_*` / `slot_new_*` wrappers | `moe-forward-ok` |
| success | each new symbol returns `STATUS_OK` and stores its slot | `moe-forward-ok` |
| failure | `ALIGN_GGML_SLOT` for an out-of-range or empty slot in each new symbol; `ALIGN_GGML_INIT` for `argsort` `order` outside `{0,1}`, `ne2 < 1`, `nb1_dim`/`offset_dim` outside `[0,3]`, or a `view_2d` extent exceeding `a`'s nbytes | `moe-shim-*` under `ALIGN_LLM_GGML_FORCE` |
| malformed input | `slot_new_i32_2d` with `ne <= 0`; `slot_new_tensor_3d` with a type absent from the operand table | `moe-shim-type`, `moe-shim-extent` |
| early exit | the widened `soft_max_ext` with `mask == -1` takes the null-mask path and no slot is fetched | `moe-softmax-nomask` |
| cleanup | no allocation added; `grep` for `malloc` in either shim still finds none | the smoke's existing shim assertions |
| shared contract | the `BEGIN/END R4.5 SHARED SHIM CONTRACT` region stays byte-identical | the smoke's existing byte-identity assertion |
| sole `unsafe`/`extern` | `src/ggml_ffi.align` remains the only file matching either grep | the smoke's existing assertions |

### 4.3 `src/moe_layer_forward.align` — the arm

| Cell | Implementation | Case |
| --- | --- | --- |
| construction | operand parse, path validation, geometry, pack open | `moe-arity-*`, `moe-path-*` |
| success | both graphs compute, the document renders, `verdict: EXTERNAL` | `moe-forward-ok` |
| failure | every code of section 3.8's table | one case per code, section 4.5 |
| malformed input | `TOKENS` with a space, a trailing comma, seven ids, an id `>= n_vocab` | `moe-tokens-*` |
| early exit | steps 1–2 write nothing at all; steps 3–15 write a document and create no ggml state | `moe-arity-none-written`, `moe-stub-unavailable` |
| cleanup | teardown order of section 3.9; `released_before_owner_scope_end` true on every path including the error paths | `moe-lifetime`, asserted on every case |
| two-phase carry | the four carried tensors are written with `align_ggml_slot_set` and their byte counts published as `graph.carried_bytes` | `moe-carry-bytes` |
| document forms | `-` and a real path emit byte-identical document bytes | `moe-document-forms-identical` |

### 4.4 The oracle cells

| Cell | Implementation | Case |
| --- | --- | --- |
| self-reference success | 28 of 28 nodes byte-identical across both graphs | `moe-reference-ok`, **(Q)** |
| self-reference failure | `R5_REFERENCE_MISMATCH` with the first differing node and index | `moe-reference-perturb` under `ALIGN_LLM_GGML_FORCE=engine+reference` |
| source divergence | `R5_SOURCE_DIVERGED` when a claim's pack bytes differ from the GGUF's | `moe-source-diverged` |
| routing success | every printed id and both sums match | `moe-routing-match`, **(Q)** |
| routing failure | `routing.verdict: "MISMATCH"`, oracle 3 still evaluated and reported | `moe-routing-mismatch` |
| routing coverage | `ids_printed_compared` is 36 and `ids_total` is 48 at `n_expert_used = 8, T = 6`; the synthetic corpus at `n_expert_used = 3` compares all 18 | `moe-routing-coverage`, **(Q)** |
| transcript success | `PASS`, 26 nodes, 2,376 elements | **(Q)** |
| transcript node absent | `R5_ORACLE_MISSING` | `moe-oracle-missing` |
| transcript shape disagreement | `R5_ORACLE_SHAPE` | `moe-oracle-shape` |
| transcript tolerance breach | `oracle.verdict: "FAIL"` with the numbers, not an error | `moe-oracle-fail` |
| integer node non-integral | `R2_EXPERT_ID_NOT_INTEGRAL` | `moe-oracle-nonintegral` |
| exclusions are fields | `kq`/`kq_soft_max` `shape_incomparable`, the four `norm-0` `ambiguous_name`, the chain `unstable_name` | `moe-oracle-exclusions` asserts the exact sets |

### 4.5 Error-code-to-case map, and the final pass

Every code of section 3.8 has one case. Codes reachable only with real ggml are marked **(Q)**;
codes reachable only under a forced shim are marked **(F)**.

| Code | Case |
| --- | --- |
| `R5D_ARITY` | `moe-arity-four`, `moe-arity-nine`, `moe-arity-wrong-arm` |
| `R5D_PATH` | `moe-path-empty`, `moe-path-nul`, `moe-path-long` |
| `R5D_ROUTER_SHAPE` | `moe-router-shape` |
| `R5D_EXPERT_ID` | `moe-routing-id-range` **(F)**, `moe-routing-id-repeat` **(F)**, `moe-routing-remap` **(F)** |
| `R5D_CLAIM_BUDGET` | `moe-claim-budget` (synthetic geometry with a large `n_ff_exp`) |
| `R5D_CLAIM_MISSING` | `moe-expert-block-missing`, `moe-expert-role-missing`, `moe-expert-slice-index` |
| `R5_TOKENS` | `moe-tokens-empty`, `moe-tokens-seven`, `moe-tokens-space`, `moe-tokens-vocab` |
| `R5_GEOMETRY_UNREADABLE` | `moe-geometry-absent` |
| `R5_GEOMETRY` | `moe-geometry-*`, one per detail of steps 5–8 |
| `R5_BLOCK_MISSING` / `R5_BLOCK_AMBIGUOUS` | `moe-block-missing-*`, `moe-block-ambiguous` |
| `R5_MEMBER_MISSING` | `moe-member-missing-*`, including `attn_q_norm` and `router` |
| `R5_SHAPE` | `moe-shape-*` |
| `R4_PACK_*` / `R4_WINDOW_UNAVAILABLE` / `R4_5_SLICE` | re-raised; `moe-pack-*`, `moe-slice-*` |
| `R5_GGML_UNAVAILABLE` | `moe-stub-unavailable` |
| `R5_ABI` / `R5_TYPE_UNSUPPORTED` / `R5_ALIGNMENT` | `moe-abi` **(F)**, `moe-type`, `moe-alignment` |
| `R5_GGML_INIT` / `R5_SLOT` / `R5_ALLOC` / `R5_COMPUTE` | `moe-init` **(F)**, `moe-slot-range` **(F)**, `moe-slot-empty` **(F)**, `moe-alloc` **(F)**, `moe-compute` **(F)**; `alloc`/`reserve` details exercised for both `_a` and `_b` |
| `R5_SOURCE_UNREADABLE` / `R5_SOURCE_DIVERGED` | `moe-source-absent`, `moe-source-diverged` |
| `R5_REFERENCE_MISMATCH` | `moe-reference-perturb` **(F)** |
| `R5_TRANSCRIPT` / `R5_ORACLE_MISSING` / `R5_ORACLE_SHAPE` | `moe-transcript-*`, `moe-oracle-missing`, `moe-oracle-shape` |
| `R2_EXPERT_ID_NOT_INTEGRAL` | `moe-oracle-nonintegral` |

**The final pass.** Before review, every applicable cell of sections 4.1–4.5 maps to the diff and to
a passing case, or to a named deferral in section 5.4. The three cells this design already knows it
cannot close on this host are listed there: the Metal arm, decode, and the Q4_K `ffn_down_exps`
layers.

---

## 5. Fixtures, qualification, metrics, deferrals, risks, and candidate requests

### 5.1 Owner — a fourth block in `scripts/run-layer-forward-smoke`

**R5D adds no smoke target and changes no aggregate membership** (corrected — see C15). It does add
one Makefile target, the opt-in `moe-layer-forward-qualification` of section 5.2, which is in no
aggregate and in neither `HOSTED_CHECK_TARGETS` nor `CAPABLE_ONLY_CHECK_TARGETS`; a Makefile edit
is still an executable-contract boundary, so publication selects the installed profile at preflight
whatever this paragraph says about topology. `layer-forward-smoke` is
already a member of `HOSTED_CHECK_TARGETS`, and `r5b-model-prefill-forward.md` and
`r5c-metal-prefill.md` both extended that one script with a new block for exactly this reason. A new
`moe-layer-forward-smoke` target would change `HOSTED_CHECK_TARGETS`, which
`docs/specs/check-gate-topology.md` and the `Makefile`'s own comment record as a check-topology
change that selects `make ci` for publication. R5D's fourth block keeps the topology fixed and its
publication in the ordinary lane.

The block follows the existing three: `build_shim("engine")` for the forced-failure loop, then
`build_shim(None)` to restore, with the `cleanup` trap rebuilding the default shim. Goldens live in
`scripts/moe-layer-forward-golden.jsonl`, refreshed by the runner's **one** golden variable,
`ALIGN_LLM_LAYER_FORWARD_GOLDEN_UPDATE=1`, which rewrites all four blocks' goldens together
(correction C16).

**The corpus is a new MoE mode of `scripts/layer_forward_fixture.py`, not of `gguf_fixture.py`.**
The two generators have different jobs and only one of them writes numbers: `gguf_fixture.py`
synthesizes olmoe *geometry* with every payload byte `0xA5`, while `layer_forward_fixture.py`
writes an alignpack v1 container directly with real F32 members. Today it is hard-wired to
`"n_expert": 0` and a dense Qwen2 role list. R5D adds `--moe`, producing:

```text
GEOMETRY_MOE = {"arch": "olmoe", "n_layer": 2, "n_embd": 8, "n_head": 2, "n_head_kv": 2,
                "head_dim": 4, "n_ff_exp": 16, "n_vocab": 32,
                "n_expert": 8, "n_expert_used": 3, "context_length": 512}
TOKENS_MOE   = [3, 17, 5]
```

`n_expert` 8 and `n_expert_used` 3 match `gguf_fixture.py`'s `OLMOE_BASE`, so the two corpora
describe the same synthetic model and a reader can cross-check block indices. Every member is
`TYPE_F32`, which keeps the fixture readable and keeps `align_ggml_type_ok` on its F32 row; the
quantized types are the real model's job. The blocks the generator writes are
`r1c-olmoe-moe-ir.md` section 2.5.3's order — one embedding `WeightBlock`, then per layer an
`AttentionBlock`, a `RouterBlock`, and eight `ExpertBlock`s with `slice_index` `0..7` and
`slice_count` 8 — so `R4_5_SLICE`'s two admitted pairs are both exercised.

The block asserts, on `moe-forward-ok`: `verdict: EXTERNAL`, `pointer_identity` true for all ten
dense members and all `3U` claims, `routing.routed_count` equal to the golden `U`,
`routing.compact_ids` a bijection, `residency.expert_bytes_read` and `expert_bytes_in_layer`
matching the golden integers, `graph_a.node_count` and `graph_b.node_count` matching the goldens,
`lifetime.released_before_owner_scope_end` true, and the whole document byte-identical between the
`-` and file forms. At `n_expert_used = 3` the router's slot axis is 3, which is `<= 6`, so the
synthetic corpus is the **only** place the routing oracle's *full* print coverage is reachable —
section 4.4's `moe-routing-coverage` case.

The block never skips: it is ggml-free, model-free, and network-free, exactly as the three blocks
before it.

**The runner's wall clock, measured, and what it costs the R5B/R5C target** (correction C17). Paired
and alternating on the host of section 2.1, three runs each, the fourth block's own commit against
its parent `3cb8d59`:

| Quantity | Result |
| --- | --- |
| `gmake layer-forward-smoke`, three blocks, at `3cb8d59` | **19.41 s** median (19.27–20.54) |
| the same, with R5D's fourth block | **30.57 s** median (27.37–36.12) |
| **R5D's own cost** | **+11.2 s, +58%** — 78 documented cases, 8 no-document cases, and twelve shim builds (one `engine`, ten forced flavours, one restore) |

`r5b-model-prefill-forward.md` section 5.5 and `r5c-metal-prefill.md` sections 5.1 and 6 (C11, C19)
set an acceptance target of **under 15 s** for this runner. **R5D exceeds it and the target is
retired rather than met, split, or excused**; corrections C18 there and here record the decision, and
the reason is stated as arithmetic rather than as a preference. The target was set from an 11.0 s
baseline; this host runs the same three blocks in 19.4 s, so 11.0 + 11.2 = **22.2 s** is outside 15 s
even against the baseline the target was set from. No split of R5D's block recovers it: the
alternative to the fourth block is a fifth `HOSTED_CHECK_TARGETS` member, which is the check-topology
change section 5.1 exists to avoid and which would not reduce the aggregate's own cost by one second.

What replaces it is stated in C18: the runner's budget belongs to `HOSTED_CHECK_TARGETS` as a whole
and to the fresh worker's cap, not to a per-capability wall clock on one developer's laptop.

### 5.2 Named qualification — `make moe-layer-forward-qualification`, `scripts/run-moe-layer-forward`

Opt-in and capable-only, in neither `HOSTED_CHECK_TARGETS` nor `CAPABLE_ONLY_CHECK_TARGETS` and in
no aggregate, exactly as `layer-forward-qualification` and `model-forward-qualification` are not.
The Makefile target is `moe-layer-forward-qualification: build ; ./scripts/run-moe-layer-forward`.

It reads `ALIGN_LLM_GGML_INCLUDE`, `ALIGN_LLM_GGML_LIB`, `ALIGN_LLM_GGUF_MODEL`,
`ALIGN_LLM_LLAMA_EVAL_CALLBACK`, `ALIGN_LLM_MOE_LAYER_FORWARD_TMPDIR`, and
`ALIGN_LLM_MOE_LAYER_FORWARD_EXCERPT_UPDATE`, and skips with
`na() { printf '%s\n' "moe layer forward qualification: N/A $1"; exit 0; }` using
`run-layer-forward`'s detail strings verbatim, plus one of its own:

```text
ALIGN_LLM_GGUF_MODEL is not an olmoe model
```

The free-space guard is `run-layer-forward`'s, `need_kib=$(( model_bytes / 1024 + 1048576 ))`, which
is **5,163,334 KiB** for this model. Section 2.7's probe measured 12,240,252 KiB free before the
pack and 12,221,484 KiB after it was deleted, so the guard has ample headroom on this host and the
pack does not survive the run.

The sequence:

```text
main --pack     $MODEL $W/model.alignpack $W/pack.json
main --model-ir $MODEL $W/geometry.json
$ALIGN_LLM_LLAMA_EVAL_CALLBACK -m $MODEL -p "def add(a, b" -n 1 -t 4 -ngl 0 \
    -fa off -ctk f32 -ctv f32 -nr -c 512 > $W/transcript.txt 2> $W/log.txt
./ggml-spike --moe-layer-forward $W/model.alignpack $W/geometry.json 1545,823,9,66,13,270 \
    $W/moe-layer.json $ALIGN_LLM_GGUF_MODEL $W/transcript.txt
```

The prompt is `"def add(a, b"` and **not** `run-layer-forward`'s `"def add(a, b):"`, because OLMoE's
tokenizer produces seven ids for the latter and `MAX_PREFILL_TOKENS` is 6. The runner asserts the
tokenizer produced exactly the six ids above before invoking the arm, so a tokenizer change is a
named failure rather than a silent seven-token refusal.

Asserted, from the emitted document:

| Field | Expected |
| --- | --- |
| `model.*` | `olmoe`, 16, 2048, 16, 16, 128, 1024, 50304, 64, 8, 4096, `3727c5ac`, 2, 128, `461c4000`, `3db504f3` |
| `members` count | 10 |
| `claims` count | 75 (`3U` at `U = 25`) |
| `routing.routed_count` | 25 |
| `routing.routed` | `0,4,6,7,13,14,15,16,21,32,33,35,36,38,39,40,43,48,51,53,54,55,57,59,61` |
| `residency.expert_bytes_read` / `expert_bytes_in_layer` | 101,990,400 / 261,095,424 |
| `residency.expert_bytes_read_ppm` | 390,625 |
| `residency.planes_read` / `planes_in_layer` | 75 / 192 |
| `graph_a.node_count` / `graph_b.node_count` | **31 / 24**, asserted (correction C19); `graph_a.table_rows` / `graph_b.table_rows` are 31 / 24 |
| `graph.slot_capacity` | 128 |
| `verdict` | `EXTERNAL` |
| `reference.verdict` | `IDENTICAL`, 28/28 |
| `routing_oracle.verdict` | `MATCH`; `ids_total` 48, `ids_printed_compared` 36, `sum_expected` 1471 |
| `oracle.verdict` | `PASS`, 26/26, `elements_compared` 2,376 |
| `oracle.tolerance_ten_thousandths` | 1 |
| `oracle.sum_tolerance_millionths` / `sum_tolerance_relative_ppm` | 1000 / 10 |
| `nodes[].oracle == "shape_incomparable"` | exactly `["kq", "kq_soft_max"]` |

A forced-failure loop over `for force in init compute` against the **real** shim expects
`R5_GGML_INIT` and `R5_COMPUTE`, as `run-layer-forward`'s does.

**Peak resident set is measured, best effort** (correction C19). The arm runs under
`/usr/bin/time -l` on BSD/macOS or `/usr/bin/time -v` on GNU, and the runner prints the peak in KiB;
a host with neither prints one explicit `peak RSS unmeasured` line instead of nothing. It is **not**
an assertion and not a gate. Section 3.9's window arithmetic is the bound this capability owns and
it is exact integers; peak RSS additionally holds both readback windows, the reference arm's
ggml-owned copies, and the allocator's slack, so it bounds the window arithmetic from above and
does not check it. Recording it is how a later regression in *total* footprint — the thing a loader
will care about — becomes visible without inventing a threshold nobody has evidence for.

The checked-in transcript excerpt is `eval/fixtures/olmoe-blk0-6tok.txt`, copied to a writable path
before use because the arm opens it with `fs.open_rw` (Align Request 21).

### 5.3 Metrics

| Metric | Value | Source |
| --- | --- | --- |
| Required microbenchmark B — CPU compute, one routed layer, six tokens, warm | **9.4 ms** total: phase A 3.59 ms, phase B 5.77 ms (medians of five), at the probe's phase boundary. Section 3.5 moves three cheap rows from A to B; their combined cost is far below the ±16% spread below, and the total is unchanged | Section 2.4 |
| Same, whole-tensor shape (all 64 planes resident) | 11.0 ms in one graph, plus 41 ms to read 261 MB | Section 2.3 |
| Same, per-`(token, slot)` shape | 3.7 + 7.90 ms, 474 graph nodes | Section 2.3 |
| Claim read, 75 scattered `pread`s from the GGUF | 15.5 ms warm, 66.0 ms cold | Section 2.7 |
| Claim read, 25 block `pread`s from the pack | 12.0 ms warm, 47.7 ms cold | Section 2.7 |
| Dense read, 11,082,496 B | 1.7 ms warm | Section 2.4 |
| **Expert bytes read / expert bytes in layer**, `T = 6` | 101,990,400 / 261,095,424 = **39.06%** | Section 2.6 |
| Same, `T = 1` | 32,636,928 / 261,095,424 = **12.50%** | Section 2.6 |
| Same, `T = 18` | 191,741,952 / 261,095,424 = **73.42%** | Section 2.6 |
| Peak resident weight bytes, `T = 6` | 113,072,896 against 272,171,008 for the whole layer | Section 3.9 |
| Transcript oracle coverage | 26 nodes, 2,376 elements, max `\|Δ\|` 5.0e-5 | Section 2.4 |
| Routing oracle coverage | 36 of 48 ids printed, plus an exact sum | Section 2.4 |
| Self-reference oracle coverage | 28 of 28 node dumps byte-identical | Section 2.5 |

Microbenchmarks A and C are `N/A` for section 1.3's reason: both are claims about a transfer tier
and a GPU that R5D deliberately does not have.

**The measurement risk is stated as a number, not a hedge.** Every timing above is a median of five
warm runs on one host with four threads. Phase B's spread across those five runs is 4.87–6.77 ms,
which is ±16% of its median, so the 9.4 ms total is good to about one significant figure and the
comparison against the whole-tensor arm's 11.0 ms is a ~15% effect measured with a ~16% spread. The
document publishes `timings.*` per run so a consumer can accumulate its own distribution rather than
trust this one. The residency ratios are exact integers and carry no measurement risk at all; they
are the metric this capability should be judged on.

### 5.4 Deferred surfaces

| Surface | Deferred to | Why, with evidence |
| --- | --- | --- |
| Decode-time routing, and the residency regime that matters | The R5 loader | Section 2.6: the win is 12.5% at one token and 73.4% at eighteen. Prefill is the wrong regime and R5D says so rather than reporting the one-token number as if it were the capability's |
| A `LAYER` operand | A follow-on, cheaply | Cost is an operand, an `R5_INDEX` step, and `(kind, layer, role_id)` selection that section 3.3 already performs. What it buys is the eight layers whose `ffn_down_exps` is Q4_K rather than Q6_K — `r1c-olmoe-moe-ir.md` section 2.2 lists the Q6_K layers as 0, 1, 4, 7, 10, 13, 14, 15 |
| The last layer | The same follow-on | `moe-prereq-discharge.md` section 5.6 records that llama.cpp prunes the final layer to the output tokens, so `ffn_moe_topk-15` is `{8, 1}` while `embd` is `{2048, T}`. A `LAYER` operand must handle that shape or refuse `n_layer - 1` |
| A Metal arm | `r5c-metal-prefill.md`'s successor | Section 5.6's tie-ordering risk cannot be settled with CPU evidence, and `r4-5-external-buffer.md` section 5.4's alignment rule still applies |
| A whole MoE model | Stage 3 | Needs `output_norm`, `output`, a KV cache, and a per-layer routing decision — R5B's schedule crossed with R5D's decision, which is its own consumer boundary |
| gpt-oss | `moe-prereq-discharge.md` section 5.5 | Six-member `ExpertBlock`, MXFP4, split expert biases, fused `ffn_gate_up_exps`; the model is 12.1 GB and infeasible on this host |
| Expert hotness ordering and prefetch groups | `r4-alignpack-layer-major.md` sections 5.1 and 5.2 | Both are functions of an activation distribution, which is roadmap item 19's output. R5D's `routing.expert_ids` is an input to that work, not a substitute for it |
| A slice rule in `--pack-verify` | R4 | `moe-prereq-discharge.md` section 5.5, unchanged |
| Reading claims through a read-only pack open | Align Request 21 | The arm uses `fs.open_rw`; the transcript and the pack are both copied to writable paths in section 5.2 |

### 5.5 Candidate Align capability requests

**No new request is expected, and none was found.** Every construct this design needs compiled in
the probe or exists in R5A's shipped module: the node tables are `array<Node>` of a `Copy` record,
the routing decision is integer arithmetic over `array<i64>`, the four windows are `buffer`, and the
FFI additions are five `extern` declarations in the one file that already has them.

Two existing requests gain R5D as an additional client. When this section was written they were
**Requests 44 and 45 and were not in this branch's `docs/align-requests.md`**, because both existed
only on `agent/r3-residency-sim`, which had not merged. That branch has since merged as PR #135, and
PR #134 took Request 44 first, so the two are now **Requests 45 and 46** on `main` and this branch's
reconciliation appends R5D to each of their client lists (correction C22). They are named below by
their original numbers with the current number beside each; R5D takes no dependency on either:

- **Request 44, now Request 45** (compiler soundness: moving a field out of a decoded record double-frees at run
  time). R5D decodes an `R1_MODEL_IR` document and moves fields out of it in `parse_geometry`,
  which is the same shape as the R3 client. R5D's mitigation is R3's: clone through a `str` view
  rather than move. Non-blocking.
- **Request 45, now Request 46** (`borrow mut` array locals inside loops, and no element assignment
  through an array field). R5D's routing decision wants a helper taking the per-token id tables as
  `borrow mut array<i64>` and called inside the token loop, and wants `routing.compact_ids[t][s] = v`
  through a record field. Both are the constructs Request 46 names. R5D's mitigation is R3's: return
  owned columns from helpers and write the loop body inline. Non-blocking.

`agent/r3-residency-sim` merged before R5D, so the branch took the first of the two paths this
section named: the two client lists gain `src/layer_olmoe.align`'s `parse_geometry` and its routing
decision respectively. R5D's mitigations stay in place — removing them needs the Align-side fixes,
not the merge — and R5D **does not** re-register either request.

**Two more existing requests gain R5D as a client, and both were found by writing the code rather
than by planning it** (correction C20). Neither is blocking and neither is edited into
`docs/align-requests.md` from this branch — the register on `main` owns Requests 1–43 and this
branch changes none of them, so both entries below are **to be appended at reconciliation**, in the
same pass that resolves Requests 44 and 45 — done in the reconciliation commit, correction C22.

- **Request 37 — per-function check time is superlinear in body length.** R5D is now its largest
  client. Measured at this pin on the host of section 2.1, warm, with the exact commands:

  | Command | Result |
  | --- | --- |
  | `alignc check-per-unit src/moe_layer_forward.align` (4-unit graph) | **17.02 s** |
  | `alignc check-per-unit src/model_forward.align` (7-unit graph) | **17.21 s** |
  | `alignc check-per-unit src/layer_olmoe.align` | **0.67 s** |
  | `alignc check-per-unit src/ggml_ffi.align` / `src/alignpack_read.align` | **0.18 s** / **0.60 s** |
  | `gmake check`, 30 units | **134 s** |

  The arm's own unit is therefore roughly **15.6 s** of its graph's 17.0 s, against 0.67 s for the
  1,403-line `src/layer_olmoe.align` beside it — a 23× time ratio for a 3.3× line ratio, which is
  the superlinearity Request 37 names, measured again on a module written after it was filed. R5B's
  under-10 s acceptance target for a single arm unit is **exceeded by both** `src/model_forward.align`
  and `src/moe_layer_forward.align`, and correction C18 retires it with the runner target it was
  paired with: R5D already applied the remedy the target was supposed to force — the topology tables,
  the geometry, and the routing decision are a separate module — and the arm unit is still 15.6 s.
  Splitting the arm again would move the cost, not remove it, which is precisely why this is a
  language request and not an application task.
- **Request 42 — `alignc check` as a superset of `alignc build`.** Correction C10 is fresh client
  evidence: `src/moe_layer_forward.align` checked clean per unit and the executable refused to
  link, in the region checker, with

  ```text
  cannot retain a shorter-lived view through this mutable borrow; copy it into the destination
  region first
  ```

  for `alignpack_read.member_at(f, x, block, within, c)` called with a **local** block while the
  same call crosses a `borrow mut Counters`. This is the **third** capability to hit the class and
  the **second** to hit this exact diagnostic: `r5b-model-prefill-forward.md` section 6 correction
  C7 records the same sentence for the same function at the same pin, and `r5c-metal-prefill.md`
  section 6 correction C5 records two other region diagnostics behind the same `check`/`build` gap.
  R5D's mitigation is C10's: the member scan is its own function, `block_carries_role`, whose block
  is a parameter. Whether the recurrence is one request or two — the parity gap, and a separate
  constraint that a Borrow crossing a `borrow mut` must be a parameter of the calling frame rather
  than a local — is for the register on `main` to decide when it is appended; R5D records the
  evidence and takes no dependency on either surface.

### 5.6 Risks

| Risk | Reading | Mitigation |
| --- | --- | --- |
| **`mul_mat_id` semantics could change across ggml versions.** The whole design rests on a compact `{ne0, ne1, U}` stack with remapped ids being identical to a `{ne0, ne1, n_expert}` stack with global ids | Section 2.3 measured it at ggml 0.21.0 on the CPU: 28 of 28 nodes byte-identical. It is not a documented guarantee | The self-reference oracle runs the same compact stack twice and would not catch this; the **transcript** oracle would, and the qualification runs it. Section 2.3 also establishes that the `split` fallback is exact, so a divergence has a known, already-measured answer rather than a redesign |
| **Top-k ties.** `ggml_argsort` on a row with equal probabilities has an implementation-defined order, and a different order changes the slot order, which section 2.3 shows is load-bearing to the last bit | Measured, not assumed: over the eighteen router rows of the longest probe prompt, **no row held a duplicate probability**, and the smallest relative gap across the rank-8/rank-9 boundary — the one that decides membership — was **1.35e-2**. Exact ties are improbable here but not impossible, and a degenerate or freshly-initialized router would make them common | R5D and llama.cpp call the **same** `ggml_argsort` on the **same** bytes on the same backend, so a tie is broken identically and the routing oracle still matches. The risk is real only for a **different backend**, which is why section 5.4 defers the Metal arm rather than adding it. The document publishes `routing.expert_ids` so a tie-induced difference is visible as data |
| **The same ties on the hosted arm, where the two sorts are different programs** (correction C12). The stub engine's `argsort` is not ggml's: ggml 0.21.0's CPU kernel is a `std::sort` over the index array, whose order among equal keys above the introsort insertion threshold is **unspecified**, and `ne0` is 64 on the real model — comfortably above it. The stub is a **stable insertion sort**, agreeing with `scripts/layer_forward_fixture.py`'s independent forward, which is the only order the hosted goldens can be written against | Two different tie orders, and neither corpus can tell them apart today: the real corpus has **0 duplicate probabilities** in its router rows (measured, above), and the synthetic corpus's eight-expert rows are generated from distinct values. The gap is therefore real and currently unobservable, which is exactly the shape of risk that becomes a bug when a model changes | Stated rather than asserted away: the shim comment claims stability for **the stub** and explicitly disclaims it for ggml. The three defenses that catch a wrong routing regardless of its cause — `R5D_EXPERT_ID`'s range and pairwise-distinct checks, the step-25 bijection, and the routing-identity oracle against llama.cpp — are unaffected by tie order, because they compare against the instrument rather than against an assumed order. A tie that the two sorts break differently surfaces as `routing_oracle.verdict: MISMATCH` on the qualification with the exact `(token, slot)`, not as a silent divergence |
| **The transcript oracle's coverage of `ffn_moe_topk` is structurally truncated.** 36 of 48 ids print at `n_expert_used = 8` | Section 2.2 fact 6. The block's exact integer sum pins the remaining twelve in aggregate, which is strong but not element-wise | Stated as a contract in section 3.6 and published as `routing_oracle.ids_printed_compared` / `ids_total`. The synthetic corpus at `n_expert_used = 3` reaches full coverage (section 5.1), so the *comparison logic* is exercised element-wise even though the real model's is not |
| **A wrong routing produces finite, plausible, wrong numbers.** Section 2.8's probe bug did exactly this and passed every shape check | The single most dangerous failure mode in this design | Three independent defenses: `R5D_EXPERT_ID`'s range and pairwise-distinct checks, the step-25 bijection check, and the routing oracle. And the design removes the cause: no strided view is ever read back |
| **One layer, one quantization mix.** Layer 0's `ffn_down_exps` is Q6_K; the Q4_K form is unreachable through this arm | Section 5.4's `LAYER` deferral | Named, with the exact layer list, and cheap to close |
| **The residency claim could be over-read.** A reader who sees "top-8 of 64" may take 12.5% as the capability's number | Section 2.6 is the mitigation and it is in section 1.4's gate table, not buried | The document publishes both integers per run, and section 5.3 lists three prefill lengths rather than one |
| **Measurement spread.** Phase B's five runs span 4.87–6.77 ms | Section 5.3 states it as ±16% | The document publishes per-run `timings.*`; the residency ratios, which are the metric that matters, are exact |

---

## 6. Implementation-forced corrections

Every row below is a place where writing the capability falsified something section 3, 4, or 5
asserted. Each names what the design said, what the implementation found, and what now ships. The
sections above are **not** rewritten: this section is the diff, in `r5a-dense-layer-forward.md`
section 6's shape.

### C1 — `n_expert_used` needs an upper bound, and it is the slot store's

Section 3.8 step 7 bounds `n_expert_used` only by `1 <= n_expert_used <= n_expert`. Section 3.5
makes phase B's table `2 * n_expert_used + 8` rows long, at `B_NODE_BASE` 52 in a store of
`MAX_NODE_SLOTS` 128, so a geometry declaring `n_expert_used` above 34 builds a table the store
cannot hold. The node walk would then report `R5_SLOT` on whichever row first exceeded the capacity
— a row that is not at fault — instead of naming the field that is.

`parse_geometry` therefore refuses `B_NODE_BASE + b_node_count(n_expert_used) > MAX_NODE_SLOTS` as
`R5_GEOMETRY` detail `n_expert_used`, beside the two range relations step 7 already carries. The
bound is the store's own arithmetic and not an invented ceiling: it moves if and only if
`MAX_NODE_SLOTS` or the phase-B table does. `moe-geometry-expert-used-huge` is the case, at
`n_expert_used` 64 against a store that can hold 34.

### C2 — the reduction chain publishes `node_*`, not `node_56`

Section 3.6 excludes `node_56` … `node_61` as `unstable_name` and section 2.2 fact 4 records those
exact numbers for build 10566 on this model. `nodes[].transcript_name` is a published field, and a
row that is never matched publishing a name that is right for one build of one model and wrong
everywhere else is a fact with a decay date. The fourteen excluded reduction rows publish
`ffn_moe_weighted-0 (view)` for the eight views — that name **is** stable, because it is derived
from the tensor it views — and the wildcard `node_*` for the six intermediate adds. The exclusion
class already says the name is not sought; the name field now says the same thing rather than
contradicting it.

### C3 — the plane stride is the plane, and the claim window is one buffer

Section 3.4 sizes the claim windows as `U * (align_up(gate_plane, block_align) +
align_up(up_plane, block_align) + align_up(down_plane, block_align))`. That formula pads **every
plane**. It is a no-op on this model — 1,179,648 and 1,720,320 are both multiples of 4,096 — and it
is wrong in general, because a stacked 3-D tensor's planes are contiguous. That is section 2.3's own
finding ("a stacked 3-D tensor over `U` planes is exactly `U` plane-sized regions laid end to end")
and it is what `ggml_nbytes(stack) == U * plane` asserts; a padded stride makes `mul_mat_id` read
plane `u` at `u * padded` while the tensor believes it is at `u * plane`.

The synthetic corpus caught it on the first end-to-end run: at 512-byte planes and `block_align`
4,096 the self-reference oracle reported `R5_REFERENCE_MISMATCH` at `node[ffn_moe_gate]@0`, because
the reference arm copies plane by plane into ggml-owned memory — contiguously, correctly — while the
primary arm read the padded window in place. **The bug is invisible on the real model and fatal on
any model whose plane size is not a multiple of the container's block alignment**, which is exactly
the class of defect a synthetic corpus exists to find.

What ships: each **region base** is `block_align`-aligned and the planes inside a region are laid
end to end, so `plane_stride == nbytes` for every claim and the budget is
`sum over roles of align_up(base) + U * plane`. Section 3.9's "four Align-owned windows" becomes
**two**: `dense_window`, and one `claim_window` holding three `block_align`-aligned role regions.
Three separate `ggml_backend_dev_buffer_from_host_ptr` wraps of three separate allocations buy
nothing and cost two more ggml buffers, two more alignment pads, and two more teardown branches. The
alignment contract, the pointer-identity contract, `claims[].window_offset`, and the peak resident
weight bytes are unchanged; `lifetime.ggml_buffers_created` is 3 without the reference arm and 4
with it, rather than 5 and 6.

### C4 — the transcript scanner is R5D's own, for the third time

Section 3.6 says the transcript is "scanned with `r2a-expert-trace.md` section 2.2's line grammar,
reusing `src/expert_trace.align`'s scanner". R5A section 6 correction C6 already recorded that this
reuse is not available: `scan` is module-private, it never captures a node's source names, and it
parses no element value and no `sum`. `src/layer_forward.align`'s scanner is that grammar made
reusable — but it is typed against `layer_qwen2.OracleTable`, and R5D's oracle table is a different
nominal type carrying two columns R5A's does not have: `integer`, and a class that says a row is
**never sought**.

`src/moe_layer_forward.align` therefore owns its own scanner. It is R5A's grammar with exactly two
additions: `r2a-expert-trace.md` section 2.2 finding 5's integral-element rule, applied to the two
i32 blocks and raising `R2_EXPERT_ID_NOT_INTEGRAL`; and an `oracle_scanned` gate, so the four
`norm-0` rows and the fourteen reduction rows are not candidates for any header and cannot be bound
by ordinal — which is section 2.2 fact 5's hazard removed by construction rather than by care.

### C5 — two error details are fail-closed guards with no reachable input

`R5D_CLAIM_BUDGET` cannot be produced by any container the reader accepts.
`alignpack_read.member_at` refuses a member whose `[pack_offset, pack_offset + nbytes)` leaves its
own block, so a plane large enough to make `U * plane` exceed `MAX_CLAIM_WINDOW_BYTES` (2^33) would
need an 8 GiB `ExpertBlock` — which no `--pack` writes and no fixture can hold. Section 4.5's
`moe-claim-budget` case is **withdrawn** rather than faked with a mutation the reader rejects first
and for a different reason. The check ships: it is the one arithmetic in this arm that multiplies a
container number by a data-dependent count, and a bound on it is cheaper than reasoning about it.

`R5D_EXPERT_ID` detail `remap` is the same class. `routed[]` and `compact_ids` are computed in one
pass over the same ids — `routed[u]` is the `u`th expert marked present and `compact_ids[t][s]` is
that expert's own position — so the bijection cannot fail without corrupting Align's own integer
arithmetic. The cover check ships as a backstop; the two **reachable** siblings, `token[t]slot[s]`
for an out-of-range id and for a repeat within a token, are exercised by the forced builds C6 adds
and are the two the section 2.8 bug actually produced.

### C6 — six new forced shim flavours, and two existing ones that do not fit

`ALIGN_GGML_FORCE_SLOT_EMPTY` targets slot 14 and `..._POS` targets slot 13; R5D's position vector
is slot 11, so neither fires for this arm. `ALIGN_GGML_FORCE_REFERENCE_PERTURBATION` covers slots 0
to 11, which for R5D is the ten dense weights **plus the token and position vectors** — and the
primary arm writes those two through `slot_set`, so the perturbation would reach both arms and the
mismatch it produced would not be a reference-only mismatch.

`scripts/build-ggml-shim` gains six R5D flavours, each defined in `scripts/ggml_shim_stub.c` alone
and never in an ordinary build:

| Flavour | Macro | Reaches |
| --- | --- | --- |
| `engine+moe-slot-empty` | `ALIGN_GGML_FORCE_SLOT_EMPTY_MOE` | `R5_SLOT` at slot 11, R5D's `inp_pos` |
| `engine+moe-reference` | `ALIGN_GGML_FORCE_REFERENCE_PERTURBATION_MOE` | `R5_REFERENCE_MISMATCH`, by flipping one bit of a **compact expert stack**, which only the reference arm ever writes |
| `engine+moe-argsort-range` | `ALIGN_GGML_FORCE_ARGSORT_RANGE` | `R5D_EXPERT_ID` detail `token[0]slot[0]` |
| `engine+moe-argsort-repeat` | `ALIGN_GGML_FORCE_ARGSORT_REPEAT` | `R5D_EXPERT_ID` detail `token[0]slot[1]` |
| `engine+moe-argsort-order` | `ALIGN_GGML_FORCE_ARGSORT_ORDER` | section 4.2's `argsort` order refusal, as `R5_GGML_INIT` |
| `engine+moe-view-extent` | `ALIGN_GGML_FORCE_VIEW_EXTENT` | section 4.2's `view_2d` extent refusal, as `R5_SHAPE` |

The two remaining section 4.2 malformed-input cells — `slot_new_tensor_3d` with `ne2 < 1` and
`slot_new_i32_2d` with a non-positive extent — stay closed by construction rather than by a case:
`ne2` is `U`, which is at least 1 because a routed union is non-empty, and both id tensors' extents
are geometry fields the validation order has already bounded. Adding a build to make an integer that
cannot be zero be zero would measure the build, not the guard.

### C7 — the stub engine's `get_rows` is ggml's general form, and its tensor record still fits in 128 bytes

`ffn_moe_weights-0` is `get_rows` over a `{1, n_expert, T}` reshape indexed by a **2-D** id tensor,
whose result is `{1, n_expert_used, T}`. R5A's and R5B's index vectors are 1-D, so the stub's kernel
only ever implemented the `b->ne[1] == 1` specialisation. It now implements ggml's own rule —
`src0 + i01*nb01 + i11*nb02` for the id at `(i10, i11)` — of which the 1-D case is a strict subset,
so every R5A and R5B golden is unchanged to the bit.

`mul_mat_id` needs three graph sources, so `align_stub_tensor` gained `src[2]` and **gave up the
never-used third `lp` slot** to stay exactly 128 bytes. That trade is why the record's size is
unchanged, and the size is why nothing else moved: the stub's `align_ggml_graph_context_bytes` is
`node_capacity * sizeof(that record) + 4096`, so a record grown by one pointer **would have moved**
`abi.graph_context_bytes` from 20,480 to 21,504 in twenty-one R5A, seventeen R5B, and fourteen R5C
golden documents — for a change that has nothing to do with any of those arms. It did not, and all
three checked-in golden files are byte-identical after this capability.

### C8 — `ffn_moe_topk` is an oracle row over an input, not over a node

Section 3.6 lists `ffn_moe_topk` among the twenty-six compared nodes, and section 2.8 establishes
that R5D never builds a `VIEW` of `ffn_moe_argsort` at all — the slice is Align's. The tensor the
row observes is therefore phase B's `topk_ids` **input**, at `SLOT_TOPK`, which holds exactly the
ids the transcript's `ffn_moe_topk-0` view holds. Two consequences ship: `mark_outputs` skips it,
because marking a written input as a graph output is meaningless; and `nodes[].op` reports `VIEW`,
which is the transcript's own op rather than a node-table row that does not exist.

### C9 — block selection is `(kind, layer, role_id)`, and R5A's helper is not enough

Section 3.3 says the arm locates every block "by `(kind, layer, required role_id)` … never by
computed index", and section 3.8 step 11 repeats it. R5A's `find_block` takes only `(kind, layer)`,
because a Qwen2 container's two `WeightBlock`s are told apart by a layer index the dense arm has.
**An olmoe container carries two `WeightBlock`s at layer `-1`** — the embedding and the head — so
the pair alone is ambiguous for the one block this arm needs, and a `find_block` that returned the
first match would silently compute the layer from whichever the writer happened to emit first.

The shipped selector scans each candidate block's member records for the required role and refuses a
second carrier as `R5_BLOCK_AMBIGUOUS`. The three phase-A selections are `(WeightBlock, -1,
token_embd)`, `(AttentionBlock, 0, attn_norm)`, and `(RouterBlock, 0, router)`. The real model
reached this for real: before the fix the qualification stopped at `R5_BLOCK_AMBIGUOUS` detail
`kind[0]layer[-1]`, which is the head block being counted as an embedding block.

### C10 — a Borrow crossing a `borrow mut` must be a parameter of the calling frame

`alignpack_read.member_at(f, x, block, within, c)` takes four Borrows and one `borrow mut`. At this
pin the block argument may not be a **local** of the calling function when the mutable counters
cross the same call: `alignc build` refuses it as "cannot retain a shorter-lived view through this
mutable borrow", whether the local is bound by `:=` inside the loop or declared `mut` outside it.
The same call compiles when the block is a parameter, which is why `find_member` has always worked.

`alignc check` on the single module accepts both forms and `alignc build` over the whole import
graph refuses one, so this is only visible at link time — the module checked clean and the executable
did not. The member scan is therefore its own function, `block_carries_role`, whose block is a
parameter; C9's selector calls it. This is an application-side workaround for a language-owned
constraint and it is recorded as one: `docs/align-requests.md` owns the language half, and no
hypothetical surface is consumed.

### C11 — the summary block, as section 3.3 prints it

Section 3.3's block is implemented verbatim, including the three renamed or added byte lines
(`expert bytes read`, `expert bytes in layer`, `dense weight bytes`) and the two `a+b` pairs
(`graph nodes`, `compute ns`). `activation bytes` is the sum of the two graphs' `gallocr` sizes,
because a reader who wants them apart has `graph_a.activation_bytes` and `graph_b.activation_bytes`
in the document and the summary block is read positionally.

### C12 — one type per role, not one type per stack, and the stub sort that was neither

Two findings of the comprehensive review, repaired together because they are the same fact about
this arm's argsort-and-stack path.

**Every plane of a role must declare the role's own `ggml_type`.** Section 3.8 step 18 validates
"the three claim types", and the implementation read that literally: `stage_claim_types` checked
`claims.ggml_type[0..3]`, which are `routed[0]`'s three planes. But **both arms build one compact
stack per role from that first plane's type** — `stage_claim_tensors` and `stage_reference_weights`
both index `claims.ggml_type` by role — so a later plane declaring a different type is staged as if
it carried the first's encoding. Nothing downstream notices. `nbytes` agrees, because the arm's
shape rule is over `nbytes` and F32 at *n* elements and F16 at 2*n* are the same byte count. The
self-reference oracle agrees, because both arms build from the same first type. The transcript
oracle agrees, because it compares the *values the arm computed* from the stack the arm built. A
container that mislabels one plane therefore produced `status: ok`, `verdict: EXTERNAL`, and silently
wrong arithmetic — reproduced before the repair on `moe-pack-claim-type-mismatch.alignpack`.

What ships is a second walk in `stage_claim_types`, over **every** claim, refusing
`claims.ggml_type[at] != claims.ggml_type[its role's first plane]` as `R5_TYPE_UNSUPPORTED` with
detail `expert[<n>]role[<r>]`. Two placement details are load-bearing. It runs **after** the
operand-table rows, so a genuinely unsupported first plane still names its own role rather than the
second plane that disagrees with it — placing the gate earlier, in `stage_claims`, shadowed
`moe-engine-claim-type` and made the operand-table check unreachable, which is a coverage loss
disguised as a fix. And it runs **before** any ggml object exists, so one check covers the primary
arm and the reference arm alike rather than being restated in each.

The case is `moe-engine-claim-type-mismatch` (H) — the reviewer's `moe-claim-type-mismatch`, under
this runner's `moe-engine-` prefix — a container whose `routed[1]` gate plane declares F16 where
`routed[0]`'s declares F32 at an identical `nbytes`. Golden: `R5_TYPE_UNSUPPORTED`, detail
`expert[1]role[ffn_gate_exps]`. Section 7.3's `R5_TYPE_UNSUPPORTED` row now names both cases.

**The stub's `argsort` agreed with neither ggml nor its own comment.** The kernel was an exchange
sort whose comment claimed it was "ggml's own selection sort" and that "equal probabilities keep
ascending index order". Both halves were wrong. Exchange sort is not stable — on `[3, 1, 3, 1]`
ascending it emits indices `1, 3, 2, 0`, putting index 2 before index 0 for equal keys — and ggml
0.21.0's CPU kernel is not a selection sort at all but a `std::sort` over the index array, whose
order among equal keys above the introsort insertion threshold is unspecified, at an `ne0` of 64 on
the real model. What ships is a **stable insertion sort**, which is a claim only about the stub: it
is the order `scripts/layer_forward_fixture.py`'s independent forward produces, and therefore the
only order the hosted goldens can be written against. The comment now says that and explicitly
disclaims ggml's. Section 5.6 gains the honest row: two different tie orders, neither corpus able to
tell them apart today (0 duplicate probabilities measured in the real router rows), and the three
routing defenses unaffected because all three compare against the instrument rather than an assumed
order. No golden moved: neither corpus holds an exact tie.

### C13 — the `view_2d` type gate was in one file of two

`scripts/ggml_shim_stub.c`'s `align_ggml_op_view_2d` refuses a non-F32 source and
`scripts/ggml_shim.c`'s did not, so the two files disagreed about what the boundary accepts — the
one asymmetry section 4.2's "the shared contract region is byte-identical" assertion cannot catch,
because the region is the constants and these are the entry points. The gate matters for the same
reason the extent test does: `ne0` is an element count, `ggml_row_size` is the only place the type
enters the span arithmetic, and a quantized source would make the extent test a statement about
block counts while the node table means elements. Both files now refuse anything but F32, which is
the only type either node table views. No case changes: the node table cannot express a non-F32
view, and manufacturing one would test the manufactured build.

### C14 — four published fields the schema did not list

`pack.reader_pread_count`, `pack.reader_bytes_read`, `oracle.transcript_lines`, and
`oracle.transcript_callback_lines` are emitted by the shipped arm and were absent from section 3.7's
field list. A published field a consumer can read and the schema does not name is an undocumented
promise, so section 3.7 now names all four and says what each is for. No document changed.

### C15 — R5D does add a Makefile target

Section 5.1 asserted "R5D adds no Makefile target and changes no aggregate membership." The second
half is true and the first is false: `moe-layer-forward-qualification` is a new target, and a
Makefile edit is an executable-contract boundary whatever it does to check topology, so publication
selects the installed profile at preflight rather than the documentation lane. Section 5.1 now says
"adds no **smoke** target", which is the claim that was actually load-bearing — `HOSTED_CHECK_TARGETS`
is unchanged and `docs/specs/check-gate-topology.md`'s gate is not tripped — and states the preflight
consequence rather than leaving it to be discovered at `scripts/pre-pr`.

### C16 — the golden variable is the runner's, not this block's

Section 5.1 named `ALIGN_LLM_MOE_LAYER_FORWARD_GOLDEN_UPDATE=1`. No such variable exists.
`scripts/run-layer-forward-smoke` has one golden switch for all four blocks,
`ALIGN_LLM_LAYER_FORWARD_GOLDEN_UPDATE=1`, which is the point of extending the runner rather than
adding one: a reader who refreshes R5D's goldens refreshes R5A's, R5B's, and R5C's in the same run
and sees immediately if any of them moved.

### C17 — the runner's cost, measured, and C18's input

Section 5.1 asserted the fourth block's shape and said nothing about its wall clock. It is
**+11.2 s, +58%** — 30.57 s median against 19.41 s for the same runner at `3cb8d59`, three paired
runs each. Section 5.1 carries the table. This is the measurement C18 acts on.

### C18 — the 15 s `layer-forward-smoke` target is retired, not met

`r5b-model-prefill-forward.md` section 5.5 and `r5c-metal-prefill.md` sections 5.1, 6 (C11), and 6
(C19) set two paired acceptance targets: `make layer-forward-smoke` under **15 s**, and
`check-per-unit` of the arm's own unit under **10 s**. R5D exceeds both — 30.6 s and ≈15.6 s — and
neither is met by any split available to this capability.

The 15 s figure was set from an 11.0 s baseline in R5B's planning session. On this host the
unchanged three-block runner is 19.4 s, so even crediting the whole 8.4 s difference to the host,
11.0 + 11.2 = **22.2 s** is outside 15 s. R5C's C19 already recorded the target being exceeded by
0.08 s and kept it by attributing the overrun to the host; that arithmetic does not survive a second
capability, and repeating it would be choosing which number to report. The 10 s check target is in
the same position: R5D already applied the remedy the target exists to force — the node tables, the
geometry, and the routing decision live in `src/layer_olmoe.align`, checked in 0.67 s — and the arm
unit is still 15.6 s, because the cost is Request 37's superlinearity and not a module boundary.

**Both targets are retired**, with restatements recorded in `r5b-model-prefill-forward.md` section 6
and `r5c-metal-prefill.md` section 6 so the ledgers that set them do not keep asserting them. What
replaces them is not another number: `layer-forward-smoke` is one member of `HOSTED_CHECK_TARGETS`
and its budget belongs to that aggregate and to the fresh worker's cap, neither of which is near.
A per-capability wall clock on one developer's laptop measured the laptop. Section 5.3's discipline
applies here too — a target that is restated after every measurement instead of acted on is not a
gate, and saying so is cheaper than a third excuse.

### C19 — two numbers the qualification printed and did not check, and one it never took

**`graph_a.node_count` and `graph_b.node_count` are asserted, not just printed.** Section 5.2's
table left them as "the goldens recorded from the shipped arm at first run", and section 7.1
recorded 31 and 24; the runner then printed them beside the table rows and compared neither. A
published number nothing compares is not a budget, and section 3.7's whole reason for publishing
both counts is to make the slot-capacity budget auditable. `scripts/run-moe-layer-forward` now
asserts **31** and **24** against the section 7.1 goldens, beside the two `table_rows` it already
asserted.

**Peak resident set is measured, best effort.** Section 5.2 asserted section 3.9's window
arithmetic and measured no process footprint at all.
`scripts/run-moe-layer-forward` now runs the arm under `/usr/bin/time -l` (BSD/macOS) or
`-v` (GNU) and prints the peak in KiB, or one explicit `peak RSS unmeasured` line on a host with
neither. It is best effort and it is not an assertion: the window arithmetic is exact and peak RSS
additionally carries the readback windows, the reference arm's ggml-owned copies, and allocator
slack. Section 5.2 records both the measurement and why it is not a threshold.

### C20 — two more requests gain R5D as a client

Section 5.5 named Requests 44 and 45 as anticipated clients and stopped there. Writing the arm
produced client evidence for two more: **Request 37**, whose per-unit check times are now measured
on this branch's modules and whose 10 s target C18 retires, and **Request 42**, for which correction
C10 is the third capability and the second exact repeat of one diagnostic. Both are recorded in
section 5.5 with their evidence and both are marked **to be appended at reconciliation**: the
register on `main` owns Requests 1–43, this branch edits none of them, and appending a client list
here would fork the register the same way re-registering Requests 44 and 45 would.

### C21 — two overclaims in the final pass itself

Section 7 is the record, so its own inaccuracies are corrections like any other.

Section 7.2 said `released_before_owner_scope_end` is "asserted true on every documented case". It
is not, and it cannot be: the flag is computed by `stage_teardown`, so the 48 cases that stop before
step 20 creates the first ggml object — the whole pre-ggml ladder plus `moe-stub-unavailable`'s
`UNAVAILABLE` verdict and `moe-engine-alignment`'s step-19 refusal — report `false` and always did.
The goldens pin that value; what those cases assert positively is `lifetime.*_created == 0`. The
7.2 rows now state the split, which is exhaustive over all 78 documented cases.

Section 7.3's `R5_GEOMETRY` row said "31 cases" and the geometry corpus is 32: `moe-geometry-absent`
reaches `R5_GEOMETRY_UNREADABLE`, and `moe-geometry-not-json` — a readable file that is not JSON,
which the arm is handed by passing the transcript in the geometry position — reaches `R5_GEOMETRY`
detail `json`. The case existed and ran; only the count and the row it sat under were wrong. Both
rows now name it explicitly, because "a file that opens and does not parse" is the one geometry
fault a reader is most likely to expect under the *unreadable* code.

### C22 — the pin moved under the branch, and the two anticipated requests are now real

R5D was designed, implemented, and reviewed at `.align-revision` `4b515f8d`. Two pull requests
merged into `main` while it was in review: **PR #134**, which moved the pin to `3a34febe` and took
Request 44 for itself, and **PR #135** (R3-RESIDENCY-SIM), which merged the two requests R5D's
section 5.5 could only anticipate — renumbered to **45** and **46** by PR #134's claim on 44.
Reconciliation therefore does four things and each is recorded rather than silently applied.

1. **The pin is adopted, not asserted to be harmless.** Every owner and the real-model qualification
   are re-run at `3a34febe` (`HANDOFF.md` records the exact commands and results). **No golden byte
   changed**: the R5A, R5B, R5C, R5D, and ggml-spike golden documents are byte-identical under the
   new compiler, so this correction is a record and not a behavioural row. Section 7.1 records the
   re-run and the single quantity that moved, which is a timing.
2. **Section 5.5's two anticipated requests are appended for real.** `src/layer_olmoe.align`'s
   `parse_geometry` joins Request 45's client list and its routing decision joins Request 46's, which
   is the first of the two paths section 5.5 named. R5D's mitigations stay: what removes them is the
   Align-side fix, not the merge.
3. **C20's two more requests are appended in the same pass.** Request 37 gains R5D's per-unit check
   times and Request 42 gains correction C10's diagnostic, as C20 said they would.
4. **`.align-revision` is one of the twenty recorded baseline artifacts**, so the pin move invalidates
   the chain that shipped with R5C exactly as this branch's own `Makefile` change does. The chain is
   re-recorded on this branch and `HANDOFF.md` names its three commits.

---

## 7. The final pass: what was measured, and every closure cell's case

### 7.1 What the shipped arm measured on the real model

`make moe-layer-forward-qualification` against `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, one run,
every section 5.2 assertion passing:

| Quantity | Section 5's expectation | Measured by the shipped arm |
| --- | --- | --- |
| routed union | 25 of 64, `0,4,6,7,13,14,15,16,21,32,33,35,36,38,39,40,43,48,51,53,54,55,57,59,61` | **identical**, and every per-token slot row of section 2.4 reproduced in order |
| `residency.expert_bytes_read` / `expert_bytes_in_layer` | 101,990,400 / 261,095,424 | **identical**; `expert_bytes_read_ppm` 390,625 |
| planes, block reads | 75 of 192, 25 reads | **identical** |
| self-reference oracle | "28 of 28" (the probe's dump set) | **46 of 46** — R5D publishes 46 oracle rows, because it publishes its excluded classes as rows rather than omitting them |
| routing-identity oracle | `MATCH`, 36 of 48 printed, sum 1,471 | **identical** |
| transcript oracle | `PASS`, 26 nodes, 2,376 elements, max `\|Δ\|` at the 5.0e-5 print bound | **`PASS`, 26/26, 2,376 elements, max `\|Δ\|` 0 ten-thousandths**, max `\|Δsum\|` 30 millionths against a 1,000-millionth floor |
| graph sizes | tables 31 and 24; ggml counts recorded at first run | ggml counts **31 and 24**, equal to the tables; slot high water 76 of 128. Correction C19 turns these two into runner assertions rather than printed values |
| microbenchmark B | 9.4 ms (probe: A 3.59 + B 5.77, medians of five un-warmed runs) | **5.64 ms** (A 1.452 + B 4.185, warm means of five). The probe timed a cold graph per arm; the shipped arm's contractual warm-up is what section 3.5 already required, and the number is better rather than worse |
| claim read | 12.0 ms warm for 25 block `pread`s (section 2.7) | 45.3 ms cold on this run, dense read 5.1 ms; the run is cold because the pack was written seconds earlier |
| peak resident weight bytes | 113,072,896 against 272,171,008 | 113,072,896 against **272,177,920**. Section 3.9's whole-layer figure omits the 6,912 row-gathered embedding bytes the arm actually holds; the ratio is unchanged to four figures |
| peak resident set of the whole process | not measured by the plan (correction C19) | **500,416 KiB** and **500,624 KiB** over two runs, `/usr/bin/time -l`. Roughly 4.4× the 113 MB of weights: the two readback windows, the reference arm's ggml-owned copy of every weight, `gallocr`'s 0.9 + 1.8 MB of activations, and allocator slack. Reported, not asserted — the exact bound is the row above |

The measurement that matters is unchanged and exact: **the routed layer reads 101,990,400 of
261,095,424 expert bytes, and every node of it agrees with llama.cpp.**

**Re-run at the adopted pin `3a34febe`** (correction C22), same host, same model, same instrument:
every structural quantity in the table above is **identical** — the routed union and each per-token
slot row, 101,990,400 / 261,095,424 at 390,625 ppm, 75 of 192 planes over 25 block `pread`s, the
46-of-46 self-reference oracle, `MATCH` with sum 1,471, `PASS` at 26 of 26 nodes and 2,376 elements
with max `|Δ|` 0 ten-thousandths and max `|Δsum|` 30 millionths, graph nodes 31 + 24, slot high water
76 of 128, and peak resident weight bytes 113,072,896 against 272,177,920. The one quantity that
moved is the timing: microbenchmark B is **4.761 ms** (A 1.260 + B 3.592, warm means of five) against
the 5.64 ms above, a 16% difference that is inside section 5.3's own ±16% run-to-run spread and is a
diagnostic rather than a claim.

### 7.2 Closure cells to cases

`(H)` is the hosted owner, `scripts/run-layer-forward-smoke`'s fourth block. `(Q)` is
`scripts/run-moe-layer-forward`.

| Section 4 cell | Closed by |
| --- | --- |
| 4.1 construction, success | `moe-engine-ok` (H); every `model.*` field asserted (Q) |
| 4.1 failure, malformed input | 16 `moe-geometry-missing-*` and 15 `moe-geometry-*` cases (H), one per consumed field and one per precondition of steps 5–8, including `expert-zero`, `expert-used-high`, and C1's `expert-used-huge` |
| 4.1 early exit | every geometry case runs under the **default stub** and asserts `lifetime.*_created == 0`: a geometry fault emits no ggml call (H) |
| 4.1 cleanup | `lifetime` balance asserted on every **engine** case (H) and (Q); see the 4.3 cleanup row for what the pre-ggml cases assert instead |
| 4.1 routing decision | `moe-engine-ok` asserts `routing.expert_ids`, `routed`, `routed_count`, and `compact_ids` against the generator's **independent** forward, and re-derives the bijection (H); `moe-force-routing-id-range` and `-repeat` reach `R5D_EXPERT_ID` with the exact `(token, slot)` detail (H); `remap` withdrawn per C5 |
| 4.1 slot order | `ffn_moe_out`'s `sha256`, `bit_sum`, and `f32_sum_millionths` are in the golden for every successful case, and the transcript oracle compares it element-wise against a reference that sums the slots in ascending order (H) and against llama.cpp (Q) |
| 4.2 construction, success | `moe-engine-ok` exercises all five new symbols and the widened one (H) and (Q) |
| 4.2 failure | `moe-force-argsort-order` → `R5_GGML_INIT`; `moe-force-view-extent` → `R5_SHAPE`; `moe-force-slot-empty` and `moe-force-slot-range` → `R5_SLOT` (H) |
| 4.2 malformed input | `moe-engine-claim-type` reaches `R5_TYPE_UNSUPPORTED` through a claim declaring a type the operand table does not carry, and C12's `moe-engine-claim-type-mismatch` reaches it through a later routed plane declaring a **supported** type that is not its role's first (H); the two remaining cells closed by construction per C6 |
| 4.2 early exit | the widened `soft_max_ext` takes the null-mask path in every successful run, and `ffn_moe_probs` is compared element-wise by oracle 3 and byte-identically by oracle 1 (H) and (Q) |
| 4.2 cleanup, shared contract, sole `unsafe`/`extern` | the runner's existing `malloc` grep, byte-identity assertion, and two `src/` scans, all four unchanged and all four passing with the new symbols in place (H) |
| 4.3 construction | `moe-arity-four`, `moe-arity-nine`, five `moe-path-*`, `moe-arm-unknown-flag` — eight cases that produce **no document and a non-zero exit** (H) |
| 4.3 success | `moe-engine-ok`: `verdict: EXTERNAL`, `pointer_identity` on all ten members and all `3U` claims (H); the same on the real model with 10 members and 75 claims (Q) |
| 4.3 failure | section 4.5's map below |
| 4.3 malformed input | `moe-tokens-empty`, `-trailing`, `-space`, `-seven`, `-vocab` (H) |
| 4.3 early exit | the eight no-document cases write nothing; `moe-stub-unavailable` creates no ggml state (H) |
| 4.3 cleanup | `released_before_owner_scope_end` asserted **true on every successful case** — the 30 that reach the teardown (H) and (Q). It is `false` on the 48 that stop before step 20 creates the first ggml object, `moe-stub-unavailable` and the `UNAVAILABLE` path included, because the flag is the teardown's own arithmetic and those runs have no teardown to reach. Those cases assert the 4.1 early-exit row instead — `lifetime.*_created == 0` under the default stub — which is the stronger statement for a path that created nothing, and the golden pins the flag's value for all 78 either way. The pair is exhaustive; neither half was ever "every documented case", and correction C21 records that the original wording said so |
| 4.3 two-phase carry | `graph.carried_bytes` asserted equal to the five carried tensors' bytes (H) and (Q) |
| 4.3 document forms | the `-`, bare, and file forms compared byte-for-byte after timing normalisation; three consecutive runs byte-identical (H) |
| 4.4 self-reference success | `moe-engine-reference`, 36 of 36 (H); 46 of 46 (Q) |
| 4.4 self-reference failure | `moe-force-reference` → `R5_REFERENCE_MISMATCH` naming `node[ffn_moe_gate]@0` (H) |
| 4.4 source divergence | `moe-engine-source-diverged` on a **claim** byte, detail `expert[<e>]role[<name>]` (H) |
| 4.4 routing success | `moe-engine-transcript` → `MATCH` (H); `MATCH`, 36 of 48 printed, sum 1,471 (Q) |
| 4.4 routing failure | `moe-engine-routing-mismatch` → `MISMATCH` on a **successful** run, with oracle 3 still evaluated and reporting elements (H) |
| 4.4 routing coverage | 9 of 9 ids compared element-wise at `n_expert_used` 3 (H) — the full coverage the real model's eight-slot axis cannot reach; 36 of 48 plus the exact sum (Q) |
| 4.4 transcript success | `PASS`, 26 nodes, 648 elements (H); `PASS`, 26 nodes, 2,376 elements (Q) |
| 4.4 transcript node absent | `moe-engine-transcript-missing`, `-headers`, `-novalues` → `R5_ORACLE_MISSING`, the last two by element **shortfall** rather than absence (H) |
| 4.4 transcript shape disagreement | `moe-engine-transcript-shape`, and `moe-engine-transcript-excerpt` against the real model's excerpt (H) |
| 4.4 tolerance breach | `moe-engine-transcript-perturbed` → `oracle.verdict: FAIL`, `status: ok`, `worst_node: l_out`, routing still `MATCH` (H) |
| 4.4 integer node non-integral | `moe-engine-transcript-nonintegral` → `R2_EXPERT_ID_NOT_INTEGRAL` (H) |
| 4.4 exclusions are fields | the exact sets asserted in both runners: `shape_incomparable` is `["kq", "kq_soft_max"]`, `ambiguous_name` is the four `norm-0` tensors, `unstable_name` is the reduction chain (4 rows at `n_expert_used` 3, 14 at 8) |

### 7.3 Error codes to cases

| Code | Case | Runner |
| --- | --- | --- |
| `R5D_ARITY` | `moe-arity-four`, `moe-arity-nine`, `moe-arm-unknown-flag` | H |
| `R5D_PATH` | `moe-path-pack-empty`, `-geometry-empty`, `-long`, `-doc-empty`, `-reference-empty` | H |
| `R5D_ROUTER_SHAPE` | `moe-router-shape`, detail `ne1[7]` | H |
| `R5D_EXPERT_ID` | `moe-force-routing-id-range`, `moe-force-routing-id-repeat` | H |
| `R5D_CLAIM_BUDGET` | **withdrawn**, C5 | — |
| `R5D_CLAIM_MISSING` | `moe-expert-block-missing` (step 12, default stub), `moe-engine-expert-role`, `moe-engine-slice-index` | H |
| `R5_TOKENS` | five `moe-tokens-*` | H |
| `R5_GEOMETRY_UNREADABLE` | `moe-geometry-absent`. `moe-geometry-not-json` is its neighbour and **not** this code: the file opens and reads, so it reaches `R5_GEOMETRY` detail `json` at step 5 (correction C21) | H |
| `R5_GEOMETRY` | 32 cases: `moe-geometry-not-json`, 16 `moe-geometry-missing-*`, and 15 `moe-geometry-*` | H |
| `R5_BLOCK_MISSING` / `R5_BLOCK_AMBIGUOUS` | `moe-block-missing`, `moe-block-ambiguous` | H |
| `R5_MEMBER_MISSING` | `moe-member-missing` (`attn_q_norm`) | H |
| `R5_SHAPE` | `moe-shape`, `moe-force-view-extent` | H |
| `R5_GGML_UNAVAILABLE` | `moe-stub-unavailable` | H |
| `R5_TYPE_UNSUPPORTED` | `moe-engine-claim-type` (a type the operand table does not carry), `moe-engine-claim-type-mismatch` (C12: a supported type that is not its role's first, detail `expert[1]role[ffn_gate_exps]`) | H |
| `R5_ALIGNMENT` | `moe-engine-alignment` | H |
| `R5_GGML_INIT` | `moe-force-init`, `moe-force-argsort-order` | H, Q |
| `R5_SLOT` | `moe-force-slot-range`, `moe-force-slot-empty` | H |
| `R5_ALLOC` | `moe-force-alloc`, detail `reserve_a` | H |
| `R5_COMPUTE` | `moe-force-compute` | H, Q |
| `R5_SOURCE_UNREADABLE` / `R5_SOURCE_DIVERGED` | `moe-engine-source-short`, `-missing`, `-diverged` | H |
| `R5_REFERENCE_MISMATCH` | `moe-force-reference` | H |
| `R5_TRANSCRIPT` | `moe-engine-transcript-garbage` | H |
| `R5_ORACLE_MISSING` / `R5_ORACLE_SHAPE` | four transcript cases plus the checked-in excerpt | H |
| `R2_EXPERT_ID_NOT_INTEGRAL` | `moe-engine-transcript-nonintegral` | H |
| `R4_PACK_UNREADABLE` / `R4_PACK_TRUNCATED` | `moe-pack-missing`, `moe-pack-truncated` | H |
| `R4_5_SLICE` | `moe-engine-slice` | H |
| `R5_ABI` | **not reached.** It requires a linked ggml whose operand table or tensor alignment disagrees with the checked-in one; R5A's owner does not reach it either, and manufacturing a drifting library would test the manufactured library | — |

Twenty-nine distinct codes are observed in a document by the hosted owner and two more (`R5D_ARITY`,
`R5D_PATH`) as the documented **absence** of one.
