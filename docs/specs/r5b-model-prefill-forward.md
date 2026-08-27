# R5B-MODEL-PREFILL-FORWARD: a whole Qwen2 prefill streamed through one Align-owned window

Status: design of record for the R5B capability.
Owner document for stage 3 of `docs/specs/roadmap.md` section R5's gate.
Align pin: `.align-revision` = `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`.
Predecessor: [`r5a-dense-layer-forward.md`](r5a-dense-layer-forward.md), whose node table, slot store,
shim contract, oracle discipline, tolerance rules, and teardown order this capability extends rather
than duplicates.
Inputs it consumes verbatim: [`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md) section
2.4's container, `src/model_ir.align`'s `R1_MODEL_IR` document at `schema_version: 2`
(`r5a-dense-layer-forward.md` section 6, correction C1), and
[`r2a-expert-trace.md`](r2a-expert-trace.md) section 2.4's transcript line grammar.

This document triggers the proportional design gate of `CLAUDE.md` on four counts: a new public CLI
arm, a new versioned exchanged document (`R5_MODEL_FORWARD`), a new ownership boundary (a residual
stream that Align owns *between* thirty ggml graphs), and a coordinated invariant across six
modules. Section 3 is the single public-contract ledger, section 4 is the closure matrix, and
section 5 owns fixtures, qualification, metrics, deferrals, risks, and candidate Align requests.

Section 2 is the probe record and it is first on purpose. Every contract in section 3 was chosen
after the probe. Five of the design's decisions exist **only** because a probe refuted the plan this
document started with: the model's output projection is not tied to the embedding, the pack holds
*two* blocks that answer to `(kind 0, layer -1)`, the prefill does not narrow at layer 27's input,
the whole-model result is **not** bit-exact at the runtime's own attention width, and it **is**
bit-exact at the instrument's — which turned a tolerance this document was going to have to defend
into a measurement it can explain.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

`docs/specs/roadmap.md` section R5's gate is three stages in order: **単一block、単一layer、最小モデル**
— a single block, a single layer, then a smallest model, each producing correct output. R4.5
discharged stage 1 and R5A discharged stage 2.

R5B is **stage 3 and only stage 3**: one prefill of at most six tokens through the whole
twenty-eight-layer Qwen2 model, computed by ggml over weights that live in **one reused Align-owned
window**, carrying the residual stream in **Align-owned buffers** between per-layer graphs, and
checked against llama.cpp's own final logits for the same tokens.

The question stage 3 answers is not "can Align own a layer's weights" — R5A answered that. It is:
**when the weights are streamed one block at a time through a single window that is 9.5% of the
model — and 3.2% while the twenty-eight layers run, and the activations crossing twenty-nine graph boundaries are Align's, is the model's output
the model llama.cpp computes?** A layer that is right in isolation and a model that is wrong are the
same bug twenty-eight times, and every later stage — a KV cache, a residency policy, a cache score,
a prefetch — is a claim about a loop that stage 3 is the first thing to actually run.

The capability that answers it is **R5B-MODEL-PREFILL-FORWARD**: a new arm of the existing
`ggml-spike` executable that streams the twenty-eight `AttentionBlock`/`MlpBlock` pairs of an
alignpack v1 container through one Align-owned weight window sized from the largest block in the
pack, carries `l_out-L` forward in an Align-owned activation buffer, narrows to the last token where
llama.cpp narrows, applies `output_norm` and `output`, and emits an `R5_MODEL_FORWARD` document
carrying per-layer digests, the final logits' identity, and **three independent oracle verdicts**.

### 1.2 In scope

- One new Align module, `src/model_forward.align`, owning the whole-model plan as data: the block
  schedule, the window-sizing rule, the residual carry, the narrowing point, the head, and the
  three-pass oracle structure. It contains no `extern` declaration and no `unsafe` block. Section
  5.5 records why it is a *new module* rather than four hundred more lines of
  `src/layer_forward.align`.
- Three new node tables in `src/layer_qwen2.align`: a one-row **embedding gather**, a **head**
  (`RMS_NORM`, `MUL`, `MUL_MAT`), and a `node_when` column on the existing layer table that makes the
  narrowing rows and the reconciliation rows conditional data rather than control flow.
- Two new one-op wrappers in `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c` and their
  declarations in `src/ggml_ffi.align`: `pad` and `cont_2d`. Every other op R5B needs is already
  shipped by R5A.
- One new CLI arm, `ggml-spike --model-forward`, and the `R5_MODEL_FORWARD` document at
  `schema_version: 1`.
- Three oracles, all defined in section 3.7: the **bit-exact self-reference** oracle R5A ships, now
  across thirty graphs; the **transcript** oracle, now across all twenty-eight layers and the
  head; and a new **logits** oracle against a `llama-debug --save-logits` file, which is
  byte-identical at the instrument's declared attention width (section 2.7).
- One owner test that runs without ggml, without a model, and without llama.cpp, over a synthetic
  **two-layer, thirty-two-token-vocabulary model**; and one named focused qualification that runs
  with all three.

### 1.3 Non-goals

- **No KV cache and no decode.** R5B computes one prefill. There is no cache tensor, no `set_rows`,
  no incremental step, and no second token. Section 2.7 shows this is exactly the one place where
  R5B's arithmetic and llama.cpp's differ, and section 3.7 makes that difference a measured,
  explained quantity instead of an unexplained tolerance. Decode is R6's, and section 5.4 records the
  instrument gap it will have to close first.
- **No residency policy.** R5B owns a **window**, not a loader. There is no cache score, no
  eviction, no tiering across GPU/system/NVMe, and no prefetch. The residency policy R5B ships is the
  degenerate one — read the block you are about to compute, overwrite it with the next — and section
  5.3 measures it precisely so that the policy R6 designs has a baseline to beat rather than a guess
  to improve on.
- **No GPU arm.** Inherited unchanged from `r4-5-external-buffer.md` section 5.4 and
  `r5a-dense-layer-forward.md` section 1.3.
- **No microbenchmarks A and C.** R5's required list is `A: transfer + GPU compute`, `B: CPU
  compute`, `C: async prefetch + GPU compute`. R5B measures **B at whole-model scale** and only B.
  A and C are claims about a GPU and a prefetcher that R5B deliberately does not have. Section 5.3
  says so as a number, not as prose.
- **No dequantization, no kernel, and no new container version.** R5B reads alignpack v1 as
  `r4-alignpack-layer-major.md` section 2.4 defines it and writes nothing to it. Section 5.4 keeps
  "geometry in the container" deferred exactly where `r5a-dense-layer-forward.md` section 5.4 put it.
- **No MoE and no second architecture.** `r4-alignpack-layer-major.md` section 4.5's **MOE-PREREQ**
  is inherited unchanged, and `src/layer_qwen2.align` remains the *qwen2* dense model.
- **No sampling, no detokenization, no text.** R5B emits logits and their identity. Turning a logit
  vector into a token is a policy, and a runtime that bakes one in before it has a decode loop has
  chosen the policy for reasons that have nothing to do with inference.

### 1.4 Gate statement

R5's gate is one sentence covering three stages, and each is discharged, partly discharged, or
deferred **individually**, with the probe that settles it named.

| Gate stage | Verdict | Evidence |
| --- | --- | --- |
| 単一block — a single block | **Discharged by R4.5.** Not re-litigated here | `r4-5-external-buffer.md` section 1.4 |
| 単一layer — a single layer | **Discharged by R5A.** Not re-litigated here | `r5a-dense-layer-forward.md` section 1.4 |
| 最小モデル — a smallest model | **Discharged, CPU, dense, prefill only.** At the instrument's declared attention width the 152,064 final logits are **byte-identical** to `llama-debug --save-logits`, and every sampled element of all twenty-eight layers plus the head agrees with `llama-eval-callback` to the last digit it prints — **30,042** in the probe, **30,078** in the shipped arm, which compares one node the probe skipped (correction C12). At the runtime's own attention width the same forward gives `argmax` 671 and the same top ten, with max `\|Δ\|` = **0.274** — and section 2.7 shows that entire difference is one known cause | Section 2.7 (byte-identical), section 2.8 (the probe's 30,042 at 0 ten-thousandths), section 7.4 (the arm's 30,078 at 0), section 2.6 (0.274 and the drift curve) |
| required microbenchmark A — transfer + GPU compute | **Deferred.** No GPU arm and no transfer tier exist here | Section 5.4, inheriting `r4-5-external-buffer.md` section 2.5 |
| required microbenchmark B — CPU compute | **Discharged at whole-model scale**: **1.07–1.12 s** wall in the probe, of which **349.6 ms** is compute and **533–905 ms** is `pread` over 4,370,571,072 B on one reused 447 MB window; the shipped arm's own qualification measures **515–648 ms** `pread` over 4,370,608,032 B, compute **779 ms** runtime / **841 ms** reconciliation, and **6.68 s** wall including the reference arm | Section 2.9, section 5.3, section 7.6 |
| required microbenchmark C — async prefetch + GPU compute | **Deferred.** Prefetch is a residency policy and R5B ships none | Section 5.4 |

The honest summary is: **R5B discharges stage 3 of three on the CPU for a dense model at prefill,
and microbenchmark B at whole-model scale.** It leaves benchmarks A and C, the Metal arm, MoE, the
KV cache, decode, and every residency policy where their own evidence already puts them. **R5's gate
is closed for the dense CPU prefill path and for nothing else.**

---

## 2. Probe record

Everything in this section was executed on this host before section 3 was written. Commands are
given exactly as run. Probe sources live outside the work tree and are not part of the capability;
what ships is section 3's design, and section 5.2's qualification is the probe made reproducible.
Every probe artifact — packs, transcripts, logits files, node dumps — was deleted on completion.

### 2.1 Host, toolchain, model, and what the container actually holds

| Item | Value |
| --- | --- |
| Host | `MacBookAir10,1`, Apple M1, 16 GiB, macOS 26.5.2, `darwin/arm64`, 24 GiB free |
| Align compiler | the managed pinned release toolchain at `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` |
| llama.cpp | `build 10566`, Homebrew, providing both `llama-eval-callback` and `llama-debug` |
| ggml | `0.21.0`, Homebrew, headers in `/opt/homebrew/include`, backends `dlopen`ed from `libexec` |
| Model | `qwen2.5-coder-7b-instruct-q4_k_m.gguf`, 4,683,073,536 bytes, 339 tensors |
| Backend selected | `CPU`, through R4.5's registry path; `ggml_backend_buft_get_alignment` = `32` |

The geometry is R5A's, unchanged: `n_embd` 3584, `n_head` 28, `n_head_kv` 4, `head_dim` 128, `n_ff`
18944, `n_vocab` 152064, `n_layer` 28, `context_length` 131072, `rms_eps` 1e-06 (`358637bd`),
`rope.type` 2 (NEOX), `rope.freq_base` 1000000.0 (`49742400`), `rope.dim_count` 128,
`rope.scaling_type` `null`.

**Fact 1 — `output.weight` exists and is not tied to `token_embd.weight`.** The plan assumed a tied
embedding, which would have made the head free. It is a separate tensor, and it is the largest
single member in the model:

```text
token_embd.weight   type 12 (Q4_K)  [3584, 152064]  306,561,024 B  offset 0
output.weight       type 14 (Q6_K)  [3584, 152064]  447,068,160 B  offset 3,446,253,568
output_norm.weight  type  0 (F32)   [3584]               14,336 B  offset 4,677,105,664
```

`src/frontend_qwen.align` already handles the tied case — an absent `output.weight` puts
`token_embd.weight` in two blocks — so R5B validates which case it is and says so in the document
rather than assuming either. On this model it is the untied case, and **the head's 447,082,496 bytes
are 3.0× the largest layer**, which is what makes section 3.5's window-sizing rule a decision rather
than an arithmetic detail.

**Fact 2 — the pack holds two blocks that answer to `(kind 0, layer -1)`.**
`src/frontend_qwen.align` emits, in this fixed order:

```text
index 0                 WeightBlock, layer -1   role token_embd            (alignpack role_id 12)
index 1 + 2*L           AttentionBlock, layer L eight roles                (role_id 0..7)
index 2 + 2*L           MlpBlock, layer L       four roles                 (role_id 8..11)
index 1 + 2*n_layer     WeightBlock, layer -1   roles output_norm, output  (role_id 13, 14)
```

`src/layer_forward.align:1273`'s `find_block(index, KIND_WEIGHT, -1)` returns the **first** match,
which is the embedding block, so R5A is correct today by position. R5B needs both, and selecting the
second by "the other one" would be a hard-coded index in a design whose stated rule is that blocks
are located by `(kind, layer)`. **Section 3.4 therefore qualifies block selection by a required
`role_id`**, and section 3.9 adds `R5_BLOCK_AMBIGUOUS` for the case the qualification cannot resolve.
This is a defect the plan would have shipped: it read the embedding block twice and computed the
head against `token_embd`.

**Fact 3 — the blocks are not uniform, and the window must be sized from the pack, not from a
formula.** `Q4_K_M` quantizes `attn_v` and `ffn_down` as Q6_K in some layers and Q4_K in others:

```text
Q6_K attn_v    layers 0, 1, 2, 5, 9, 11, 14, 17, 20, 23, 24, 25, 26, 27      (14 of 28)
Q6_K ffn_down  layers 0, 1, 2, 5, 7, 12, 14, 17, 20, 23, 24, 25, 26, 27      (14 of 28)

AttentionBlock  16,547,840 B or 17,020,928 B
MlpBlock       114,587,648 B or 132,091,904 B
largest pair   149,112,832 B  (layers 0, 1, 2, 5, 14, 17, 20, 23, 24, 25, 26, 27)
smallest pair  131,135,488 B
output block   447,082,496 B
all 28 pairs    3,923,476,480 B
```

A window sized from layer 0 and reused would be 13.7% too small for nothing and would still be 3.0×
too small for the head. Section 3.5's rule is a **sweep of the block table**, not a product of the
geometry.

### 2.2 Probe 1 — reconciling the two instruments, and the flag set that does it

R5B needs a whole-model oracle. `llama-eval-callback` prints six elements per row of every node
(1,098 nodes, 28,512 lines, 2,040,172 bytes, ~1.9 s) and is the only instrument that can check a
*layer*; `llama-debug --save-logits` writes all 152,064 final logits as raw little-endian f32 and is
the only instrument that can check the *model* to the last bit. They are only an oracle together if
they agree, and by default they do not.

```text
$ llama-debug -m MODEL.gguf -p "def add(a, b):" -n 1 -t 4 -ngl 0 \
      -fa off -ctk f32 -ctv f32 -nr -c 512 --save-logits --logits-output-dir lg_nr
$ ls -l lg_nr/llamacpp-qwen2.5-coder-7b-instruct-q4_k_m.bin
608256                       # 152,064 × 4, exactly n_vocab f32 for the final position
```

**`-nr` must be pinned on `llama-debug` too, and this is the finding.** R5A established four
contractual flags for `llama-eval-callback`. `llama-debug` has the same `--repack` default, and with
repacking enabled its logits are a *different* answer:

| `llama-debug` invocation | max `\|Δ\|` vs `-nr` | f32 sequential sum | argmax |
| --- | --- | --- | --- |
| `-fa off -ctk f32 -ctv f32 -nr -c 512` | — | **-232073.906250** | 671 |
| the same without `-nr` | **0.298542** | -234631.031250 | 671 |

The argmax survives repacking, which is precisely why the flag has to be contractual rather than
checked: an oracle whose *chosen token* agrees while every logit is wrong by 0.3 is an oracle that
would pass a broken implementation.

**With `-nr` on both instruments they agree to the last digit either one publishes.**
`llama-eval-callback`'s printed `result_output` record, and the first three and last three values of
`llama-debug`'s text dump of the same run:

```text
eval-callback: [ 1.5938, 4.1113, 12.6927, ..., -2.7112, -2.7112, -2.7112 ]   sum = -232073.906250
llama-debug:   0: 1.59382   1: 4.11133   2: 12.6927   ...
```

and the **f32 sequential accumulation of the 608,256-byte file is `-232073.906250`, bit-identical to
the sum the transcript prints**. `r5a-dense-layer-forward.md` section 2.3 established that the
instrument accumulates its `sum` in f32 in element order; at 152,064 elements that reproduces to the
last bit, which is a far stronger statement than agreement of a printed sample. Two consecutive
`-nr` runs produced byte-identical files.

**The contractual invocation is therefore one flag set used by both instruments**, and section 5.2
carries it:

```text
-p "def add(a, b):" -n 1 -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512
```

`llama-debug` writes its own `-tokens.bin` alongside the logits: `750, 912, 2877, 11, 293, 1648`,
identical to `llama-tokenize --ids` and to R5A's. The oracle does not have to trust that the two
instruments tokenized the same prompt; it can read what each one used.

### 2.3 Probe 2 — where the prefill narrows, which is not where the plan said

The plan narrowed to the last token at **layer 27's input**. The transcript refutes that, and the
refutation matters because narrowing early is not a slower answer, it is a wrong one: layer 27's
attention needs all six positions' keys and values.

```text
node_1084  = MUL_MAT(blk.27.attn_output.weight{3584,3584}, kqv_out-27{3584,6})  = {3584, 6}
node_1085  = GET_ROWS(node_1084{3584,6}, leaf_398{1})                           = {3584, 1}
node_1086  = GET_ROWS(l_out-26{3584,6},  leaf_398{1})                           = {3584, 1}
ffn_inp-27 = ADD(node_1085{3584,1}, node_1086{3584,1})                          = {3584, 1}
norm-27    = RMS_NORM(ffn_inp-27{3584,1})                                       = {3584, 1}
l_out-27   = ADD(ffn_out-27{3584,1}, ffn_inp-27{3584,1})                        = {3584, 1}
norm          = RMS_NORM(l_out-27{3584,1})                                      = {3584, 1}
result_norm   = MUL(norm{3584,1}, output_norm.weight{3584,1})                   = {3584, 1}
result_output = MUL_MAT(output.weight{3584,152064}, result_norm{3584,1})         = {152064, 1}
```

**The narrowing is a pair of `GET_ROWS`, inside layer 27, after the attention output projection, on
both branches of the residual add.** Layers 0 to 26 are `{3584, 6}` throughout; `ffn_inp-27` onward
is `{3584, 1}`. Section 3.6 reproduces exactly this, as two conditional rows of the layer node
table, and section 5.3 records what it buys: layer 27's compute falls from 13.5 ms to **4.3 ms**,
and the head's `MUL_MAT` against a 447 MB Q6_K matrix runs once instead of six times.

Two consequences the plan did not have. First, `norm-27` in the transcript is `{3584, 1}` while
`norm-L` for every other `L` is `{3584, 6}`, so a shape table indexed by role alone is wrong for the
last layer. Second, the head's three nodes are named `norm`, `result_norm`, and `result_output`
without a layer suffix, so they are their own oracle rows and not layer 27's.

The attention-output node is `node_1084` under this flag set and `node_31` in R5A's single-layer
run: the positional name moves with the layer as well as with the flags, which is the third
confirmation of `r5a-dense-layer-forward.md` section 2.2's fact 3. Section 3.7 matches it by its
source weight name in every one of the twenty-eight layers.

### 2.4 Probe 3 — the whole-model C harness

A C harness streamed the model, one block pair at a time, through **one** `posix_memalign` window
sized from the largest block in the file, wrapping that window with
`ggml_backend_dev_buffer_from_host_ptr` and placing every weight with `ggml_backend_tensor_alloc` at
its interior offset — R4.5's verified path, at model scale — carrying the residual in a plain host
`float` buffer between graphs:

```text
$ ./model MODEL.gguf mine.bin 750 912 2877 11 293 1648
HP n_layer=28 n_embd=3584 n_head=28 n_head_kv=4 head_dim=128 freq_base=1000000.0
   rms_eps=1e-06 n_ctx_orig=131072
TIED output.weight = NO (type=14 nbytes=447068160)
WINDOW emb=12288 layer_max=149127168 head=447086592 -> reused window = 447086592
BACKEND CPU alignment=32
...
TIME  L0  pread_ms=19.464 build_ms=0.060 compute_ms=13.742 nodes=31 act=1536000
TIME  L27 pread_ms=21.388 build_ms=0.092 compute_ms=4.301 nodes=33 act=251904
TIME  HEAD pread_ms=63.032 build_ms=0.039 compute_ms=9.455 act=622592
LOGITS argmax=671 val=17.809780
TOTAL wall_ms=1113.271 pread_ms=595.951 build_ms=1.912 compute_ms=360.415
      bytes_read=4370571072 max_act=1536000 window=447086592
```

Every weight tensor in every one of the thirty graphs satisfied
`ggml_get_data(t) == base + window_offset`, so R4.5's gate clause holds 339 times rather than once.
Peak resident set was **513,638,400 B**, which is the window plus ggml's own overhead: the model is
4.68 GB and the process never held more than 490 MiB of it.

**The graph is uniform, which is what makes the node table possible.** Removing the embedding gather
from R5A's thirty-two-row table and making the residual an *input* leaves **31 nodes** that are the
same for every layer, plus **33** at layer 27 for the two narrowing rows. The embedding gather is its
own one-node graph and the head is its own three-node graph:

```text
embedding graph            1 node    GET_ROWS(token_embd rows, inp_tokens)
layer graph, L in 0..26   31 nodes
layer graph, L = 27       33 nodes   + two GET_ROWS
head graph                 3 nodes   RMS_NORM, MUL, MUL_MAT
whole prefill            874 nodes
```

The embedding gather being a separate graph is not a simplification for its own sake: it is what
makes all twenty-eight layer graphs the *same* table walked twenty-eight times with different
weights, which is the property section 3.6 needs and the property a residency policy will need.

### 2.5 Probe 4 — the per-layer read is the cost, and the head is a third of the window

Per-layer, warm, five-hundred-and-thirty-three milliseconds of the run's 1.11 seconds is `pread`:

| | per layer | whole model |
| --- | --- | --- |
| `pread` | 15.5–21.4 ms, median **18.7 ms** | **532.9 ms** for 3,923,476,480 B |
| compute, layers 0–26 | median **13.50 ms** | 349.6 ms including layer 27 and the head |
| compute, layer 27 | **4.30 ms** — the narrowing | |
| head `pread` | **63.0 ms** for 447,082,496 B | |
| head compute | **9.5–11.2 ms** | |
| `gallocr` per layer | 1,536,000 B | |
| `gallocr`, layer 27 | 251,904 B | |
| `gallocr`, head | 622,592 B | |

At 7.2 GB/s warm, `pread` is 1.5× compute. **This is the number that makes residency worth
designing, and it is the number R5B exists to publish**: a policy that keeps the next block's bytes
in memory has 533 ms per prefill to compete for, and one that does not is I/O bound on a machine
whose page cache happens to hold the file.

### 2.6 Probe 5 — the whole model at the runtime's own attention width

R5B has no KV cache, so its attention is computed over the prefill's own six positions, exactly as
`r5a-dense-layer-forward.md` section 1.3 defines it. Against `llama-debug`'s file:

```text
max |Δ| = 0.273842 at index 90771     mine = -7.044673   llama = -6.770831
mean |Δ| = 0.043759   median 0.035790   p99 0.148204   range of the logits 28.927
argmax   671 both                      top ten identical, in the same order
elements over 0.5: 0                   elements over 1.0: 0
```

The chosen token and the whole top ten agree; every logit is within 0.27 of llama.cpp's. That is a
result a design could ship with a tolerance — and it is exactly the kind of tolerance that hides a
bug, because 0.27 is roughly the same size as the repacking difference of section 2.2, which *is* a
different computation.

**The drift has a shape, and the shape is the argument.** Comparing every printed element of all
seventeen oracle nodes of all twenty-eight layers against the transcript, in R5A's ten-thousandths
units (`0` means every sampled element rounds to the value the instrument printed):

```text
layer  0  1  2  3     4    5    6    7    8 ...  20    21    22    23    24    25    26    27
max tt 0  1  0  0    99  233  188  370  483    957  1432  2292  2980  3056  3616  4899  2190
```

Layers 0 to 3 agree with the instrument to the last digit it prints — R5A's result, three more times.
The first node in the whole model to disagree is `Qcur-bias-4`, one unit of ten-thousandths, while
its own input `attn_norm-4` still agrees exactly. That is not a topology error appearing at layer 4;
it is an error below the print threshold at layers 0 to 3 crossing it, and then growing. Section 2.7
identifies what seeded it, and the identification is not an inference.

### 2.7 Probe 6 — the same model at the instrument's attention width is byte-identical

llama.cpp's attention reduces over `n_kv = 256`, the padded width of its 512-cell KV cache, of which
250 columns are zero and masked. R5B's reduces over 6. The *values* are the same; the **f32
reduction length is not**, and `ggml_vec_soft_max_f32` and the `kqv` `mul_mat` group their partial
sums differently at 6 elements than at 256.

The harness was re-run with K and V padded with zeros to a declared width of 256 and the mask widened
to `{256, 6}` — **not a cache**: nothing persists between graphs, no position is ever read back, and
the padding is rebuilt from zero in every layer. Three extra nodes per layer (`cont` and `pad` on K,
`pad` on V), 34 per layer and 36 at layer 27, 958 in the prefill.

```text
$ cmp padkv.bin lg_nr/llamacpp-qwen2.5-coder-7b-instruct-q4_k_m.bin
(no output)
```

**The 608,256 bytes are identical.** `sha256` `d2e48620ae3e31e2066a6172aa32c19c974d996d232ab91b118335e3d245bf74`,
`bit_sum` 425,868,724,161,277, f32 sequential sum `-232073.906250` — the value the transcript prints
— `argmax` 671. Two consecutive runs were byte-identical to each other.

This settles three things at once, and none of them could have been settled by a tolerance:

1. **The topology, every scalar, the RoPE mode and base, the attention scale, the mask, the
   narrowing point, the head, and the row-gathered embedding are all exactly right.** A whole model
   does not reproduce 152,064 f32 values bit-for-bit by accident.
2. **The 0.274 of section 2.6 has exactly one cause**, and it is the one structural difference
   between R5B and llama.cpp that section 1.3 declares. It is not slack in which a bug could hide;
   it is a measured consequence of a documented non-goal.
3. **R5B can ship a bit-exact end-to-end verdict**, which is a categorically better acceptance
   contract than "within 0.27 of a logit". Section 3.7 makes it one, and section 3.3 makes the width
   an operand the caller declares rather than a constant this repository copies out of llama.cpp.

The cost of the reconciliation pass is small and was measured: per-layer compute rises from a median
of 13.50 ms to **14.57 ms**, whole-model compute from 349.6 ms to **394.1 ms**, wall from 1.08 s to
**1.10 s**. It reads no additional byte, because the weights for a layer are already in the window.

### 2.8 Probe 7 — the transcript oracle across the whole model, and the self-reference oracle

At the reconciliation width, against the same transcript, every oracle node of every layer:

```text
ELEMENTS compared = 30042
WORST max|diff| = 0.000050 at Kcur-bias-5
WORST ten-thousandths delta = 0
layer   0..27   max tt = 0 for every one of the twenty-eight
result_norm     6 elements   max tt 0
result_output   6 elements   max tt 0   |sum diff| 0.000000
```

**`5.0e-5` is the print bound, not an achievement**: `llama-eval-callback` prints `%12.4f`, so a
printed value carries an inherent ±5.0e-5, and not one of the 30,042 sampled elements differed from
it by a single unit of the last digit printed. `result_output`'s f32 sequential sum matched the
printed sum **exactly**, over 152,064 elements.

The self-reference oracle, with all 338 weight tensors created in a second context and allocated by
`ggml_backend_alloc_ctx_tensors` — `ggml_get_data(t)` asserted **not** to equal the host pointer, so
the arm is genuinely ggml-owned:

```text
$ ALIGN_R5B_REF=1 ./model MODEL.gguf ref.bin 750 912 2877 11 293 1648
$ cmp ref.bin padkv.bin && for f in dumpk/*.bin; do cmp -s "$f" "dumpr/$(basename $f)" || echo DIFF; done
(no output — the logits and 479 of 479 node dumps byte-identical)
```

479 dumps: **seventeen** nodes × twenty-eight layers, plus `embd`, `result_norm`, and
`result_output`. R5A's eighteenth oracle node was `embd` itself, which is now the embedding graph's
own row rather than each layer's.
Peak resident set for the reference arm was 960,626,688 B, because it holds the window *and* ggml's
copy of the current block.

One more fact worth recording. The harness's CPU backend used its **default** thread count while
both instruments ran at `-t 4`, and the output was still byte-identical. The reduction is
thread-count-independent for these ops, which is why section 5.2 pins `-t 4` on the instruments and
does not pin a thread count on `ggml-spike`.

### 2.9 Probe 8 — budgets, and the owner test's headroom

| Quantity | Measured |
| --- | --- |
| reused weight window | **447,086,592 B** at 4096 alignment; 447,082,496 B at the pack's `block_align` of 32 |
| bytes read per prefill | **4,370,571,072 B** — 3,923,476,480 layers + 447,082,496 head + 12,096 embedding rows |
| peak RSS, shipped arm | **513,638,400 B** (490 MiB) |
| peak RSS, self-reference arm | 960,626,688 B (916 MiB) |
| wall, warm, three runs | 1,079.9 / 1,071.3 / 1,076.2 ms natural; 1,121.1 / 1,103.6 / 1,108.1 ms reconciliation |
| `make layer-forward-smoke` today | **8.120 s**, 82 cases, 24 of 26 codes |
| `gmake check` today | 91.2 s for 29 units |
| free space | 24 GiB, against a 4.68 GB model and a 4.68 GB pack |
| whole transcript | 28,512 lines, 2,040,172 B — too large to check in |
| `l_out`-only excerpt | 35 records, 460 lines, **31,665 B** — section 5.1's fixture |

### 2.10 What the probes settle

1. The whole model is reproducible **to the bit** from Align-owned bytes, at the instrument's
   attention width: 152,064 logits byte-identical, 30,042 elements at zero ten-thousandths.
2. The one difference at the runtime's own width is the attention reduction length, it is 0.274 at
   worst, and it changes neither the argmax nor the top ten. It is a consequence of a declared
   non-goal, measured.
3. Both instruments must be pinned by the same flags. `-nr` on `llama-debug` is worth 0.30 of a
   logit, and the argmax survives without it.
4. The prefill narrows *inside* layer 27, after the attention output projection, on both residual
   branches. Narrowing at layer 27's input would be wrong, not merely different.
5. `output.weight` is a real Q6_K tensor of 447,068,160 bytes, it is not tied here, and it alone
   sizes the reused window at 3.0× the largest layer.
6. The pack has two blocks at `(kind 0, layer -1)`. Block selection must be role-qualified.
7. Blocks are not uniform: fourteen of twenty-eight layers carry Q6_K in `attn_v` and fourteen in
   `ffn_down`, and the window must be swept from the block table.
8. `pread` is 1.5× compute, warm. Residency has 533 ms per prefill to win.

---

## 3. Public-contract ledger

### 3.1 The executable, and why this is still an arm

R5B ships as **`ggml-spike --model-forward`**, for `r5a-dense-layer-forward.md` section 3.1's four
reasons, unchanged: one link boundary, a discharged prologue, an `align-runtime` name that should be
claimed by the runtime, and a CLI that already selects on the first operand.

Section 3.1 of R5A promised the rename to `align-runtime` "at the R5B boundary, where the loader
arrives". **The loader has not arrived** — section 1.3 keeps residency policy out of R5B — so the
rename is deferred again, and section 5.4 says so with the condition that would trigger it rather
than a new stage number. Renaming an executable because a document predicted a rename would be the
schedule driving the contract.

### 3.2 Hyperparameters

Unchanged from `r5a-dense-layer-forward.md` section 3.2 as corrected by its section 6, correction
C1: the container carries no hyperparameters, so the arm takes an **`R1_MODEL_IR` document at
`schema_version: 2`** and reads only its `model` object, with `rms_eps_bits` and
`rope.freq_base_bits` as lowercase eight-character hex strings validated by
`bits32_finite_nonnegative` (correction C17).

R5B consumes two fields R5A validated but did not use, and adds no other:

| Consumed field | R5A's use | R5B's use |
| --- | --- | --- |
| `n_layer` | bounds the `LAYER` operand | **the schedule**: every `L` in `[0, n_layer)` is computed, in order |
| `n_vocab` | bounds token ids | **the head's `ne1` and the logits' element count** |

The `LAYER` operand is gone. R5B computes all of them, which is what stage 3 means.

### 3.3 CLI surface

```text
ggml-spike PACK.alignpack BLOCK MEMBER [DOC.json [REF.gguf]]                   # R4.5, unchanged
ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS ...                     # R5A, unchanged
ggml-spike --model-forward PACK GEOM.json TOKENS
ggml-spike --model-forward PACK GEOM.json TOKENS DOC.json
ggml-spike --model-forward PACK GEOM.json TOKENS DOC.json REF.gguf
ggml-spike --model-forward PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH
ggml-spike --model-forward PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin
ggml-spike --model-forward PACK GEOM.json TOKENS -        REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin
```

Exactly four, five, six, eight, or nine operands. **Seven is `R5_ARITY`**, and the gap is the
contract: `KV_WIDTH` is not optional metadata beside the transcript, it is what makes the comparison
against that transcript meaningful, so it travels with it.

Arm selection, `MAX_PATH_BYTES`, the `-` document convention, `TOKENS` (1 to 6 comma-separated
non-negative decimal ids, each `< n_vocab`), and `MAX_PREFILL_TOKENS = 6` are
`r5a-dense-layer-forward.md` section 3.3's, verbatim. The cap remains the oracle's rather than the
arithmetic's, and section 5.4 keeps lifting it with R6.

**`KV_WIDTH` is the attention width the reference instrument used**, a non-negative decimal integer
in `[token_count, MAX_ATTENTION_WIDTH]` with `MAX_ATTENTION_WIDTH = 4096`. `KV_WIDTH == token_count`
is legal and means "the instrument reduced over the prefill", in which case the reconciliation pass
is the runtime pass and is not run twice. Anything else is `R5_KV_WIDTH`.

**Deriving `KV_WIDTH` from the transcript was considered and rejected.** `kq-0`'s printed `ne0` *is*
the instrument's width, and R5A already reads declared shapes out of the transcript. But that would
let the file being used as an oracle silently change the computation being checked, and "the oracle
configures the thing it verifies" is the one property no amount of downstream checking repairs. The
operand is fail-closed; the transcript's `kq-L` `ne0` is instead **validated** to equal it, as
`R5_ORACLE_SHAPE`, so a mismatch is loud.

The summary block is R5A's shape — each label and its value on their own line, read by line ordinal,
printed exactly when a real document path is given — with these rows in this order:

```text
model forward:
status:            OK | ERROR
verdict:           EXTERNAL | COPIED | UNAVAILABLE
pack path:         <sanitized path>
schema:            1
arch:              qwen2
layers:            <integer>
tokens:            <comma-separated ids>
window bytes:      <integer>      # the one reused Align-owned window
window peak block: <integer>      # which block sized it
residual bytes:    <integer>      # Align-owned activation carry
activation bytes:  <integer>      # the largest ggml-owned gallocr buffer over all graphs
graphs:            <integer>
graph nodes:       <integer>      # summed over every graph computed
backend:           <name>
pread ns:          <integer>
compute ns:        <integer>
elapsed ns:        <integer>
logits sha256:     <64 hex characters>
logits bit sum:    <integer>
logits argmax:     <integer>
reference:         IDENTICAL | MISMATCH | -
reference nodes:   <identical>/<compared> | -   # self-reference oracle, summed over every graph
transcript:        PASS | FAIL | -
logits oracle:     IDENTICAL | WITHIN | FAIL | -
max abs diff:      <integer>      # ten-thousandths, transcript oracle
logit max diff:    <integer>      # ten-thousandths, logits oracle
released:          <integer>
error:             <code>         # only when status is ERROR
detail:            <identifier>   # only when status is ERROR
```

`verdict` retains R4.5's meaning and is `EXTERNAL` only when **every** weight tensor of **every**
graph's data pointer lies at its own window offset. `COPIED`, `FAIL`, and `WITHIN` are successful
runs; `status: "error"` is reserved for section 3.9's codes.

### 3.4 Block selection and the read schedule

**Thirty window fills and fifty-eight `pread` groups**, in this order, into **one** Align-owned
`buffer`:

1. **The embedding rows.** The `WeightBlock` carrying `role_id` 12, `row_bytes = nbytes / n_vocab`
   required to divide exactly and to be a positive multiple of `type_size`, one `pread` of
   `row_bytes` per token at `member.pack_offset + id * row_bytes` into a `block_align`-padded slot,
   ids remapped to `0..T-1`. `r5a-dense-layer-forward.md` section 2.5's measurement is inherited
   unchanged, and at whole-model scale it matters more, not less: the whole member is 306,561,024 B
   against 12,096 B used.
2. **For each `L` in `0..n_layer-1`, in order: the `AttentionBlock` at `L`, then the `MlpBlock` at
   `L`.** One `pread` of `block.pack_bytes` each — R4.5's read shape, unchanged, 56 times.
3. **The output `WeightBlock`**, carrying `role_id` 13 and 14. One `pread`.

**Blocks are located by `(kind, layer, required role_id)`.** Section 2.1's fact 2 is why the third
term exists: two blocks answer to `(0, -1)` and only the required role distinguishes them. Exactly
one block must match; none is `R5_BLOCK_MISSING` and more than one is `R5_BLOCK_AMBIGUOUS`, each
naming the kind, the layer, and the role. Members are located by `role_id` against
`r4-alignpack-layer-major.md` section 2.4.4's frozen list, never by name and never by position.

**Layer coverage is validated before the first read.** Every `L` in `[0, n_layer)` must have exactly
one `AttentionBlock` and exactly one `MlpBlock`; a gap is `R5_LAYER_COVERAGE`, detail `layer[<n>]`.
A model that silently skips a layer is the failure mode a whole-model arm most needs to refuse,
because its output is plausible.

**Tied embeddings are detected, not assumed.** When the output block's `role_id` 14 member names the
same tensor as the embedding block's `role_id` 12 member, `model.output_tied` is `true`, the head's
weight is read into its own window slot from that member's own `pack_offset`, and the document says
so. Section 2.1 measured this model as untied; the tied case is a data path, not a branch in the
oracle.

Each member is copied to a `block_align`-aligned window offset rather than used at its interior
offset, for `r5a-dense-layer-forward.md` section 3.4's reason: every pointer handed to ggml is
`MAX_TENSOR_ALIGNMENT`-aligned by construction.

### 3.5 The window, and how it is sized

**One window, reused thirty times, sized by a sweep of the block table before anything is
allocated:**

```text
window_bytes = MAX_TENSOR_ALIGNMENT
             + max over the blocks this run will read of
                   Σ align_up(member.nbytes, block_align)   over that block's members,
               where the embedding block contributes align_up(row_bytes * T, block_align)
                   and the attention and mlp blocks of one layer are summed as a pair
```

Section 2.1's fact 3 is why this is a sweep and not a formula, and section 2.1's fact 1 is why the
maximum is the head: **447,082,496 B**, against 149,112,832 for the largest layer pair and 12,096
for the embedding rows.

**The window is sized from the largest block, not from the largest layer, and that costs 298 MB of
resident memory during the twenty-eight layers that do not need it.** The design accepts that,
stated rather than hidden, for three reasons. A second window for the head would be a second
lifetime, a second alignment argument, and a second set of counters for one graph out of thirty.
The peak is unchanged either way, because the head runs last and its bytes have to be somewhere.
And a runtime whose window is sized by the model's largest block is the shape a residency policy
inherits — the policy's job is to decide *what* is resident, not to relitigate how big one slot is.
Section 5.4 records "a window per block class" as an R6 measurement, with this number as its
baseline.

`R5_WINDOW_BUDGET` refuses a computed window above `MAX_WINDOW_BYTES = 2^33` before a single byte is
reserved, so a malformed member record cannot ask the process for a terabyte.

### 3.6 The graph as Align-owned data — three tables and a condition column

`src/layer_qwen2.align` gains two node tables and one column. R5A's table shape is unchanged:
`node_id`, `node_op`, `node_a`, `node_b`, `node_out`, `node_p0..p3`, `node_oracle`.

```text
EMBED_NODE_COUNT := 1     GET_ROWS(token_embd window, inp_tokens)
LAYER_NODE_COUNT := 36    R5A's 32 rows, minus GET_ROWS, plus 2 narrowing rows and 3 width rows
HEAD_NODE_COUNT  := 3     RMS_NORM, MUL(output_norm), MUL_MAT(output)
```

**The new column is `node_when`**, an `i64` per row:

| `node_when` | The row is issued | Rows |
| --- | --- | --- |
| `0` | always | the 31 rows every layer computes |
| `1` | only when `L == n_layer - 1` | `GET_ROWS(attn_out, out_ids)`, `GET_ROWS(cur, out_ids)` |
| `2` | only when the reconciliation width exceeds the token count | `CONT(K permuted)`, `PAD(K)`, `PAD(V)` |

One loop walks the table and skips a row whose condition does not hold. Adding the narrowing and the
reconciliation as **data** rather than as two `if` statements inside the walk is what keeps section
4's "the topology is a table a test can assert on" true; `node-table-shape` gains the assertion that
every `node_when` is one of the three and that the rows reachable at each condition form a
well-ordered graph.

**The residual is an input, not a node.** Each layer graph's first source is `cur`, an f32
`{n_embd, T_in}` tensor whose bytes Align writes with `align_ggml_slot_set` before the graph runs and
reads back with `align_ggml_slot_get` after. That is the boundary section 3.8 owns, and it is why
all twenty-eight layer graphs are the same table.

**Scalar ownership** is `r5a-dense-layer-forward.md` section 3.5's, unchanged: every scalar crosses
as an `i32` bit pattern, the mask is written from `0x00000000` and `0xFF800000` with `put_u32_le`,
the five RoPE constants are compiled in behind step 9's validated precondition, and no float crosses
the FFI in either direction. The mask's width is `KV_WIDTH` for the reconciliation pass and `T` for
the runtime pass; its height is `T` in both.

**New shim symbols — two.** R5A shipped twenty-five, and R5B needs `pad` and `cont_2d`; every other
op in all three tables is already there, including `cont_3d`
(`r5a-dense-layer-forward.md` section 6, correction C4).

| Symbol | Signature | Contract |
| --- | --- | --- |
| `align_ggml_op_pad` | `int32_t (void *ctx, void *slots, int64_t out, int64_t a, int32_t p0, p1, p2, p3)` | `ggml_pad`; each `p` validated `>= 0`, and the result's element count validated against `MAX_ATTENTION_WIDTH * n_embd` before the call |
| `align_ggml_op_cont_2d` | `int32_t (void *ctx, void *slots, int64_t out, int64_t a, int64_t ne0, ne1)` | `ggml_cont_2d`, for the narrowed `kqv_out` at `T = 1` |

`align_ggml_graph_context_bytes` is called with `MAX_NODE_SLOTS` as R5A does; the largest graph is 36
nodes and the slot high-water is 12 weights + 4 inputs + 36 nodes = **52**, against a capacity of 128.

### 3.7 The three oracles, and the tolerances fixed before the qualification

**Oracle 1 — bit-exact self-reference.** Present in the six-, eight-, and nine-operand forms.
`r5a-dense-layer-forward.md` section 3.6's oracle, per graph: the same table is built a second time
with that graph's weights allocated by `ggml_backend_alloc_ctx_tensors` and filled from the same
Align window, and **every oracle node of every graph must be byte-identical**. Section 2.8 measured
479 of 479. Before each block's graph runs, its members' pack bytes are compared byte-for-byte
against the source GGUF at `member.source_offset`; a difference is `R5_SOURCE_DIVERGED`.

This oracle proves **bytes**, it is version- and kernel-independent, and at model scale it is the
only thing that catches a window reused before its previous tenant was done with it.

**Oracle 2 — the transcript, across all twenty-eight layers and the head.** Present in the eight-
and nine-operand forms. R5A's eighteen oracle nodes less `embd`, which becomes the embedding
graph's own row — **seventeen per layer**, 479 in the prefill — matched by R5A's rules — including the
attention output projection matched by its **source weight name** in each layer, never by `node_NN`
— plus `embd`, `result_norm`, and `result_output`. `kq-L` and `kq_soft_max-L` remain **excluded from
element comparison by contract** and carry `oracle: "shape_incomparable"`; their declared `ne0` is
validated to equal `KV_WIDTH`, which is the one thing they are now good for.

`norm-L` is `{n_embd, T_in}` for `L < n_layer - 1` and `{n_embd, 1}` for the last layer, and the head
rows carry no layer suffix. Section 2.3 is why both are contract rather than discovery.

**The transcript oracle compares the reconciliation pass.** Comparing the runtime pass against an
instrument that reduces over a different width would fail from layer 4 onward for a reason that is
not a defect, and widening the tolerance until it passed would destroy the oracle. Section 2.6 is the
measurement that makes this a decision rather than a convenience.

**Oracle 3 — the logits, new.** Present in the nine-operand form. `LOGITS.bin` must be exactly
`n_vocab * 4` bytes (`R5_LOGITS_SHAPE`) and readable (`R5_LOGITS_UNREADABLE`).

| `compared_pass` | Verdict | Threshold | Justification |
| --- | --- | --- | --- |
| reconciliation | `IDENTICAL` | **byte-identical**, all `n_vocab * 4` bytes | Section 2.7 measured byte-identity over 152,064 f32, twice, with `sha256` `d2e48620…`. Anything less is a regression, not a tolerance |
| runtime | `WITHIN` | `\|Δ\| <= 5000` ten-thousandths **and** `argmax` equal **and** the top ten equal, in order | Section 2.6 measured max 2,738 ten-thousandths, mean 438, p99 1,482, over a logit range of 28.927. The bound is 1.8× the measured worst case and 0.017 of the range. It is a characterization of section 1.3's declared non-goal, not slack: the reconciliation arm's byte-identity is what proves nothing else is hiding under it |

**Exactly one pass is compared, and the document names it.** `oracle_logits.compared_pass` is
`"reconciliation"` when `KV_WIDTH > token_count` and `"runtime"` otherwise, so a single run yields a
single verdict and section 5.2 obtains both by invoking the arm twice with two widths. Making one
run report two verdicts would have meant computing the whole model twice for a number that is a
characterization rather than an acceptance criterion.

Both are reported as numbers whether they pass or fail: `oracle_logits.max_abs_diff_ten_thousandths`,
`oracle_logits.argmax_primary`, `oracle_logits.argmax_reference`, `oracle_logits.top_k_agreement`.

**The transcript element and sum thresholds are R5A's section 3.6, unchanged and unwidened**: element
`|round(x * 10^4) - printed_ten_thousandths| <= 1`, sum `|Δ| <= max(1.0e-3, 1.0e-5 × |Σ|)` in
millionths against a **sequential f32 accumulation in element order**. Section 2.8 measured `0` and
`0` at whole-model scale over 30,042 elements, so R5B inherits R5A's tolerance without moving it —
which is the strongest statement a successor capability can make about a predecessor's threshold.

Both comparisons remain integer comparisons and **no float is rendered anywhere**, for
`r4-alignpack-layer-major.md` section 2.3's reason.

### 3.8 `R5_MODEL_FORWARD`, `schema_version: 1`

Canonical UTF-8 JSON in declaration order, in the R0/R1/R2A/R4/R4.5/R5A shape.

```text
schema_version    1
kind              "R5_MODEL_FORWARD"
pack_path, geometry_path, reference_path, transcript_path, logits_path   strings, "" when absent
status            "ok" | "error"
error_code, error_detail                                                 strings, "" when ok
verdict           "EXTERNAL" | "COPIED" | "UNAVAILABLE"

pack        format_version, block_align, member_align, block_count, member_count,
            total_bytes, payload_offset, reader_pread_count, reader_bytes_read
model       arch, n_layer, n_embd, n_head, n_head_kv, head_dim, n_ff, n_vocab,
            context_length, rms_eps_bits, rope_type, rope_dim_count, rope_freq_base_bits,
            attn_scale_bits, output_tied (bool), output_ggml_type
selection   token_count, tokens[], embedding_block_index, output_block_index,
            narrow_layer, narrow_index, attention_width, reconciliation_width
schedule[]  layer, attention_block_index, mlp_block_index, attention_bytes, mlp_bytes,
            attn_v_ggml_type, ffn_down_ggml_type, pread_ns, compute_ns, node_count,
            l_out_sha256 (64 hex), l_out_bit_sum, l_out_f32_sum_millionths,
            l_out_ne0, l_out_ne1, nonfinite_count
window      bytes, peak_block_index, peak_block_kind, peak_block_layer, peak_block_bytes,
            reuse_count, pointer_identity_failures, member_placements,
            residual_bytes, logits_bytes
graph       graph_count, node_count_total, reconciliation_node_count, slot_capacity,
            slot_high_water,
            activation_bytes_peak, activation_bytes_by_graph[], context_bytes, backend_name
head        output_norm_bytes, output_bytes, pread_ns, compute_ns, node_count,
            result_norm_sha256, result_norm_bit_sum
output      sha256 (64 hex), bit_sum, element_count, nonfinite_count, argmax,
            top_k[] { index, bits }                                       # k = 10
reference   present (bool), verdict, graphs_compared, nodes_compared, nodes_identical,
            first_difference_graph, first_difference_node, first_difference_index,
            first_difference_primary_bits, first_difference_reference_bits,
            pread_count, bytes_read
oracle      present (bool), verdict, instrument, instrument_kv_width,
            layers_expected, layers_matched, nodes_expected, nodes_matched,
            elements_compared, max_abs_diff_ten_thousandths, max_sum_diff_millionths,
            tolerance_ten_thousandths, sum_tolerance_millionths, sum_tolerance_relative_ppm,
            worst_layer, worst_node, worst_element_index,
            transcript_lines, transcript_callback_lines
oracle_logits present (bool), verdict, compared_pass, byte_identical (bool),
            max_abs_diff_ten_thousandths, tolerance_ten_thousandths,
            argmax_primary, argmax_reference, top_k_agreement, elements_compared,
            reference_sha256, reference_bit_sum
timings     pread_ns, build_ns, reserve_ns, compute_ns, reconciliation_compute_ns,
            reference_compute_ns, oracle_ns, elapsed_ns
lifetime    ggml_buffers_created, ggml_buffers_freed, contexts_created, contexts_freed,
            backends_created, backends_freed, graphs_created, gallocrs_created,
            gallocrs_freed, released_before_owner_scope_end (bool)
abi         tensor_alignment, table_drift, slot_magic_ok (bool), fp_contract_off (bool),
            graph_context_bytes
```

**`schedule[]` is the capability's real output**, and it is one row per layer rather than one row per
node for a reason section 2.6 makes concrete: a whole-model failure is diagnosed by finding the
*first layer* that moved, and twenty-eight `l_out` digests do that in one document, while 874
per-node digests would be a 40× larger document that answers the same question. Per-node identity is
still reachable — the transcript oracle names `worst_layer` and `worst_node` — but it is a
comparison result, not a bulk field.

`window.reuse_count` is `30` and `window.pointer_identity_failures` is `0` on a healthy run; the
second is what makes `verdict: "EXTERNAL"` a measurement across 339 placements rather than a claim.
Both `verdict` and `reference.verdict` are **conclusions about a completed run** and are reported
only from one: an error document carries `verdict: "UNAVAILABLE"` and `reference.verdict: "-"`
rather than a judgement extrapolated from the graphs that happened to run before the failure
(correction C17).

The reader counters are two independent pairs, because they measure two different files.
`pack.reader_pread_count` and `pack.reader_bytes_read` are the container's — the window fills and
the member records — and are the pair `timings.pread_ns` times. `reference.pread_count` and
`reference.bytes_read` are the source GGUF's, read only by the self-reference oracle's byte-equality
pre-check, and are excluded from `timings.pread_ns`. Summing them into one pair would report 8.7 GB
against the 515–648 ms spent moving 4.37 GB and make every bandwidth figure derived from the pair
twice the truth (correction C18).

`window.residual_bytes` and `window.logits_bytes` publish the two Align-owned activation buffers
section 3.10 sizes at step 18, so the bounded-memory claim is a document field rather than a
paragraph. `oracle.transcript_lines` and `oracle.transcript_callback_lines` publish what the
pre-schedule scan of correction C4 actually read, which is what lets a checked-in transcript fixture
be regression-tested for having been *parsed* rather than merely for having produced a code.

`schema_version` is `1` and nominal. A consumer keys on `kind` plus `schema_version`. Checksums are
never floats: `sha256` is `crypto.sha256` over the exact little-endian f32 bytes, `bit_sum` is the
`i64` sum of the u32 bit patterns, `f32_sum_millionths` is section 3.7's sequential accumulation
widened to `f64` and rounded (`r5a-dense-layer-forward.md` section 6, correction C10).
`nonfinite_count` is reported and is never a failure condition.

### 3.9 Validation order and error codes

First applicable row wins. Steps 1 and 2 return `Err` with no output at all. Steps 3 onward produce a
`status: "error"` document and then map to `Err(Error.Invalid)`. **No ggml state is created before
step 20, and nothing outside the process is ever written.**

1. Arm selection and exact arity — four, five, six, eight, or nine operands. → `R5_ARITY`
2. Lexical path validation of every path operand; `-` in the document position is not a path. →
   `R5_PATH`
3. `TOKENS` parses: 1–6 non-negative decimal integers, comma-separated, no spaces. → `R5_TOKENS`
4. `KV_WIDTH` parses and is in `[token_count, MAX_ATTENTION_WIDTH]`. → `R5_KV_WIDTH`
5. Geometry document open and read. → `R5_GEOMETRY_UNREADABLE`
6. Geometry parses, `kind == "R1_MODEL_IR"`, `schema_version == 2`. → `R5_GEOMETRY`
7. Every consumed `model` field present, in range, and — for the two `_bits` fields — a finite
   non-negative pattern with a non-zero `freq_base`. → `R5_GEOMETRY`, detail the field
8. Self-consistency: `n_embd == n_head * head_dim`, `n_head % n_head_kv == 0`, `n_head_kv >= 1`,
   `n_expert == 0`, `n_layer >= 1`, `n_vocab >= 1`. → `R5_GEOMETRY`, detail the relation
9. Architecture preconditions: `arch == "qwen2"`, `rope.type == 2`, `rope.dim_count == head_dim`,
   `rope.scaling_type == null`. → `R5_GEOMETRY`. **This step earns the five fixed RoPE constants.**
10. Every token id `< n_vocab`. → `R5_TOKENS`
11. Pack open (`fs.open_rw`) and header decode, then region validation. → `R4_PACK_*` verbatim
12. Block selection, role-qualified: exactly one embedding `WeightBlock` carrying `role_id` 12,
    exactly one output `WeightBlock` carrying `role_id` 13 and 14. → `R5_BLOCK_MISSING` /
    `R5_BLOCK_AMBIGUOUS`, detail `kind[<n>]layer[<n>]role[<name>]`
13. Layer coverage: exactly one `AttentionBlock` and one `MlpBlock` for every `L` in `[0, n_layer)`.
    → `R5_LAYER_COVERAGE`, detail `layer[<n>]`
14. Member selection by `role_id` in every one of the 58 blocks. → `R5_MEMBER_MISSING`, detail
    `layer[<n>]role[<name>]`
15. Member shapes against the geometry, each exactly, in every layer; `output` is
    `[n_embd, n_vocab]` and `output_norm` is 1-D at `n_embd`; `row_bytes` divides exactly. →
    `R5_SHAPE`, detail `layer[<n>]role[<name>]`
16. Window sizing sweep, and `window_bytes <= MAX_WINDOW_BYTES`. → `R5_WINDOW_BUDGET`, detail the
    peak block
17. Window availability: `buffer(N)` published its reserved length. → `R4_WINDOW_UNAVAILABLE`
18. Residual and logits buffer sizing: `n_embd * T * 4` and `n_vocab * 4`, both bounded. →
    `R5_WINDOW_BUDGET`, detail `residual` / `logits`
19. The embedding read: one `pread` per row, completing short reads. → `R4_PACK_UNREADABLE`
20. `align_ggml_available()`. → `R5_GGML_UNAVAILABLE`, `verdict: "UNAVAILABLE"`. **This is where the
    stub shim stops, and steps 1–19 are therefore fully reachable without ggml, without a model, and
    without a transcript.**
21. `align_ggml_tensor_alignment()` and `align_ggml_table_drift()`. → `R5_ABI`
22. `align_ggml_type_ok(type, ne0)` for every member of every block that will be read, **before the
    first read**, so a Q6_K `output.weight` cannot be discovered unsupported after 4 GB of I/O. →
    `R5_TYPE_UNSUPPORTED`, detail `layer[<n>]role[type]`
23. Backend, context, slot store, and graph creation; `align_ggml_slots_init`. → `R5_GGML_INIT`
24. The embedding graph: node-table walk, alignment pre-check, `gallocr`, compute. → `R5_SLOT`,
    `R5_ALIGNMENT`, `R5_ALLOC`, `R5_COMPUTE`
25. **For each `L` in `0..n_layer-1`, in order**: read the two blocks (`R4_PACK_UNREADABLE`), verify
    every member's window offset is `0 mod tensor_alignment` (`R5_ALIGNMENT`, detail
    `layer[<n>]role[<name>]`), walk the table (`R5_SLOT`), reserve and allocate (`R5_ALLOC`),
    compute (`R5_COMPUTE`, detail `layer[<n>]status[<n>]`), read `l_out` back into the residual
26. The residual invariant: the bytes read back are exactly `n_embd * T_out * 4`, and `T_out` is the
    `T_in` the next graph declares. → `R5_RESIDUAL`, detail `layer[<n>]`
27. The output block read, and the head graph. → `R4_PACK_UNREADABLE`, then step 25's codes
28. Reference arm (six-, eight-, nine-operand forms): open the GGUF, read each member at
    `source_offset` (`R5_SOURCE_UNREADABLE`), compare pack bytes to GGUF bytes
    (`R5_SOURCE_DIVERGED`), build, compute, compare every oracle node of every graph bit-exactly
    (`R5_REFERENCE_MISMATCH`, detail `graph[<n>]node[<id>]@<index>`)
29. Reconciliation pass (eight-, nine-operand forms), when `KV_WIDTH > token_count`: the same
    schedule at the declared width, off the same window reads
30. Transcript arm (eight-, nine-operand forms): open, scan, match every layer.
    → `R5_TRANSCRIPT` / `R5_ORACLE_MISSING` / `R5_ORACLE_SHAPE`, each detailing
    `layer[<n>]node[<id>]`
31. Transcript arm: compare within section 3.7's thresholds. A breach sets `oracle.verdict: "FAIL"`
    and is **not** an error code
32. Logits arm (nine-operand form): open and size `LOGITS.bin`. → `R5_LOGITS_UNREADABLE`,
    `R5_LOGITS_SHAPE`
33. Logits arm: compare per section 3.7. A breach sets `oracle_logits.verdict: "FAIL"` and is **not**
    an error code
34. Teardown in section 3.10's order, then render, then write.

| Code | Meaning | Step | Detail |
| --- | --- | --- | --- |
| `R5_ARITY` | wrong arm or operand count, including seven | 1 | `N/A` — no document exists |
| `R5_PATH` | a path operand is empty, too long, or contains NUL | 2 | `N/A` — no document exists |
| `R5_TOKENS` | the token list does not parse, is empty, exceeds six, or names an id `>= n_vocab` | 3, 10 | `token[<i>]` |
| `R5_KV_WIDTH` | **new.** `KV_WIDTH` does not parse, is below the token count, or exceeds 4096 | 4 | `kv_width[<n>]` |
| `R5_GEOMETRY_UNREADABLE` | the geometry document could not be opened or read | 5 | the path's failure |
| `R5_GEOMETRY` | not a v2 `R1_MODEL_IR`, a missing/out-of-range/inconsistent field, an unusable bit pattern, or an unsupported architecture | 6–9 | the field or relation |
| `R4_PACK_*` | a container defect, surfaced verbatim from `alignpack_read` | 11, 19, 25, 27 | R4's own details |
| `R5_BLOCK_MISSING` | no block of the required kind, layer, and role | 12 | `kind[<n>]layer[<n>]role[<name>]` |
| `R5_BLOCK_AMBIGUOUS` | **new.** more than one block matches | 12 | the same detail |
| `R5_LAYER_COVERAGE` | **new.** a layer in `[0, n_layer)` lacks an attention or mlp block | 13 | `layer[<n>]` |
| `R5_MEMBER_MISSING` | a required role is absent from its block | 14 | `layer[<n>]role[<name>]` |
| `R5_SHAPE` | a member's dims disagree with the geometry, or a row does not divide | 15, 22 | `layer[<n>]role[<name>]` |
| `R5_WINDOW_BUDGET` | **new.** the computed window, residual, or logits buffer exceeds its bound | 16, 18 | the peak block or the buffer |
| `R4_WINDOW_UNAVAILABLE` | `buffer(N)` degraded | 17 | the window |
| `R5_GGML_UNAVAILABLE` | the stub shim, or no CPU device | 20 | `stub` / `device` |
| `R5_ABI` | an implausible ggml constant, or operand-table drift | 21 | the constant or type id |
| `R5_TYPE_UNSUPPORTED` | a member's ggml type is not a `mul_mat` left operand | 22 | `layer[<n>]role[type]` |
| `R5_GGML_INIT` | a ggml constructor returned `NULL`, or the slot store failed to init | 23 | the object |
| `R5_SLOT` | a slot index out of range, or a read of an empty slot | 24, 25, 27 | `graph[<n>]node[<id>]` |
| `R5_ALIGNMENT` | a pointer handed to ggml would violate `TENSOR_ALIGNMENT` | 24, 25, 27 | `layer[<n>]role[<name>]` — step 25's per-member loop only; `graph_alignment`'s window-level branch is unreachable defence, section 6 correction C22 |
| `R5_ALLOC` | `ggml_gallocr_reserve` or `_alloc_graph` returned false | 24, 25, 27 | `graph[<n>]reserve` / `alloc` |
| `R5_COMPUTE` | `ggml_backend_graph_compute` returned non-success | 24, 25, 27 | `layer[<n>]status[<n>]` |
| `R5_RESIDUAL` | **new.** the carried activation's length disagrees with the next graph's declared input | 26 | `layer[<n>]` |
| `R5_SOURCE_UNREADABLE` | the reference GGUF could not be opened or read | 28 | `layer[<n>]role@<offset>` |
| `R5_SOURCE_DIVERGED` | pack bytes differ from GGUF bytes | 28 | `layer[<n>]role@<offset>` |
| `R5_REFERENCE_MISMATCH` | a node's bytes differ between the two arms | 28 | `graph[<n>]node[<id>]@<index>` |
| `R5_TRANSCRIPT` | the transcript is unreadable or ungrammatical | 30 | offset or line prefix |
| `R5_ORACLE_MISSING` | a named node is absent, or contributed fewer elements than its shape prints | 30 | `layer[<n>]node[<id>]<got>/<expected>` |
| `R5_ORACLE_SHAPE` | a declared shape disagrees, including `kq-L`'s `ne0` against `KV_WIDTH` | 30 | `layer[<n>]node[<id>]` |
| `R5_LOGITS_UNREADABLE` | **new.** the reference logits file could not be opened or read | 32 | the path's failure |
| `R5_LOGITS_SHAPE` | **new.** the file is not exactly `n_vocab * 4` bytes | 32 | `bytes[<n>]/<expected>` |

Thirty-two codes: **twenty-five inherited from R5A unchanged** — its twenty-six less `R5_INDEX`,
which goes with the `LAYER` operand — and **seven new**. `R4_PACK_*` is one family row above and is
counted, as R5A counts it, alongside `R4_PACK_UNREADABLE`. Four of the seven —
`R5_BLOCK_AMBIGUOUS`, `R5_LAYER_COVERAGE`, `R5_RESIDUAL`, `R5_WINDOW_BUDGET` — exist only because the
arm computes a *whole model*: each is a way for a thirty-graph schedule to produce a plausible
answer to the wrong question, and none of them is reachable in R5A's single layer.

**`R5_ORACLE_MISSING` and `R5_ORACLE_SHAPE` are errors while a tolerance breach is not**, and
`r5a-dense-layer-forward.md` section 6, correction C19's element-count rule is inherited verbatim:
every compared node must contribute exactly `Π printed_count(ne_d)` elements. At whole-model scale
the rule matters twenty-eight times more, because a transcript that lost one layer's value blocks
would otherwise report `PASS` over 29 of 30 layers.

### 3.10 Ownership, allocation, lifetime, and bounded memory

| Module | Owns | Imports |
| --- | --- | --- |
| `src/alignpack_read.align` | the v1 reader and its `R4_PACK_*` codes | `std.fs` — unchanged by R5B |
| `src/layer_qwen2.align` | three node tables, the `node_when` column, the role tables, the shape rules, the scalar derivations, the mask image, the oracle node tables | `core.json`, `core.math` |
| `src/ggml_ffi.align` | **every** `extern "C"` declaration and **every** `unsafe` block | none |
| `src/layer_forward.align` | the R5A arm — **unchanged by R5B** | the three above |
| `src/model_forward.align` | the R5B arm: the schedule, the window, the residual carry, the three oracles, the document, the teardown | the four above |
| `src/ggml_spike.align` | arm selection and the CLIs | the two arms |

**Weights are Align-owned; the residual stream is Align-owned; the logits are Align-owned;
per-graph activations are ggml-owned.**

- The **weight window** is one Align `buffer`, over-reserved by `MAX_TENSOR_ALIGNMENT`, sized by
  section 3.5's sweep, and reused thirty times. ggml holds borrowed pointers into it — 339
  placements over the run — each validated to be exactly its own window offset, and every ggml
  buffer wrapping it is freed before the next block's read begins. **A block's bytes are overwritten
  only after every tensor pointing into them has been freed**, which is the invariant the reuse
  depends on and which the lifetime counters assert: `ggml_buffers_created == ggml_buffers_freed`
  at every layer boundary, not only at the end.
- The **residual stream is Align's**, and this is the ownership boundary R5B adds.
  `r5a-dense-layer-forward.md` section 3.9 deferred it explicitly. Between graph `n` and graph
  `n + 1` the activation is `n_embd * T * 4` bytes in an Align `buffer`; ggml never sees the same
  tensor twice, and `gallocr`'s reuse plan is free to reclaim everything the moment a graph ends.
  This is what makes thirty graphs cost one graph's activations instead of thirty.
- **Per-graph activations stay ggml-owned**, for `r5a-dense-layer-forward.md` section 3.9's reason,
  which R5B does not relitigate: `ggml_gallocr` computes the reuse plan for a graph, and
  reimplementing it in Align would be a second allocator with no residency requirement to shape it.
  What changed is the *scope* of that choice — it is now per graph rather than per run, and section
  3.8 publishes `activation_bytes_by_graph[]` so the difference is visible.
- The **logits buffer** is Align's, `n_vocab * 4` bytes, written once by the head graph's readback.
- The **slot store** is Align's, unchanged from `r5a-dense-layer-forward.md` section 3.5.

**Bounded memory.** Every allocation is a function of the geometry, the token count, and the block
table, computed and checked at steps 16 and 18 before anything is reserved:

```text
weight window     = section 3.5's sweep                            447,086,592 B (C21)
  the `buffer` behind it over-reserves by MAX_TENSOR_ALIGNMENT = 64 B, which `window.bytes` excludes
residual, runtime = n_embd * T * 4                                          86,016 B
residual, recon   = n_embd * T * 4                                          86,016 B
logits            = n_vocab * 4                                            608,256 B
reference logits  = n_vocab * 4                                            608,256 B
node readback     = max over graphs of max(node.nbytes) = n_ff * T * 4     454,656 B
mask image        = KV_WIDTH * T * 4                                 <=     98,304 B
slot store        = 16 + 8 * MAX_NODE_SLOTS                                  1,040 B
activation        = ggml_gallocr_get_buffer_size, reported not chosen
                    layers 0..26  1,536,000 B     layer 27  251,904 B     head  622,592 B
                    with the seventeen oracle nodes marked: 2,437,120 / 1,613,824 / 622,592 B
```

Measured peak resident set: **513,638,400 B** for the shipped arm and 960,626,688 B for the
self-reference arm, on a 16 GiB host, for a 4,683,073,536-byte model. **The process never holds more
than 11.0% of the model**, which is the sentence stage 3 exists to be able to write.

**Teardown order**, extending `r5a-dense-layer-forward.md` section 3.9's contract and asserted by the
lifetime counters. Per graph: `gallocr` → graph context → weight buffer → weight context → reference
buffer → reference context. At the end of the run: input contexts → backend. The window buffer, the
residual buffers, the logits buffer, and the slot store are Align's and drop with their scopes,
*after* every handle that pointed into them has been freed. `released_before_owner_scope_end` remains
a document field.

**`ggml_abort` is `abort()`**, and R5B's exposure is **874 nodes** at the runtime width and **958**
at the reconciliation width, against R5A's 32. The design does not claim the boundary is safe; it
makes every *reachable* failure unreachable — validated geometry, validated coverage, validated
shapes and types **before the first read**, validated alignments per member per layer, bounds-checked
slots and copies, null-checked constructors, a validated residual length at every graph boundary —
and says plainly that the unreachable ones remain, now twenty-seven times more often.

### 3.11 Ledger dimensions

| Dimension | Answer |
| --- | --- |
| Public surface | `ggml-spike --model-forward`, section 3.3; `R5_MODEL_FORWARD` v1, section 3.8 |
| Inputs and defaults | Four path operands, one token list, one width. **No defaults.** `KV_WIDTH` has none, deliberately (section 3.3) |
| Results, errors, precedence | Section 3.9, first applicable row wins, total across multi-invalid inputs |
| Ownership and allocation | Section 3.10; window, residual, logits, and slot store Align-owned; per-graph activations ggml-owned with a stated reason |
| Owner module | `src/model_forward.align` owns the arm; `src/layer_qwen2.align` owns the three topologies; `src/ggml_ffi.align` owns the boundary |
| Persisted identity | `kind` + `schema_version`, nominal. The pack's identity is `r4-alignpack-layer-major.md` section 2.4.6's, unchanged |
| Validation order | Section 3.9, thirty-four steps, ggml first touched at step 20, all types validated at step 22 before 4 GB of I/O |
| Prerequisites | An alignpack v1 pack; an `R1_MODEL_IR` v2 document; for the qualification, ggml, the model, `llama-eval-callback`, and `llama-debug` |
| Acceptance evidence | Section 5.1 owner, section 5.2 qualification, three oracles, tolerances fixed in section 3.7 |
| Metrics | Section 5.3; microbenchmark B at whole-model scale only |
| Text/wire boundary | UTF-8 JSON, R0's escaping rules, no float rendered anywhere |
| Inapplicable | Concurrency (single-threaded arm, one process); network (none); schema migration (v1 is the first version) |

---

## 4. Closure matrix

Every cell names an implementation owner and the exact regression that covers it. `S` = reachable
with the stub shim and its engine (`make layer-forward-smoke`), `Q` = requires the qualification.

### 4.1 `src/layer_qwen2.align` — three topologies as data

| Cell | Owner | Regression |
| --- | --- | --- |
| Formation — the three tables well-formed | `embed_node_table`, `layer_node_table`, `head_node_table` | `S` `mf-node-table-shape`: every index in `[0, MAX_NODE_SLOTS)`, every op known, every `node_out` written once per condition, every `node_when` in `{0,1,2}` |
| Formation — the conditional rows form a graph at each condition | the `node_when` walk | `S` `mf-node-when`: for each of the three conditions, every source of an issued row is itself issued |
| Success — shapes derived per layer | `expected_dims(role, L, borrow g)` | `S` `mf-geometry-shapes` on the synthetic model; `Q` the 338 members of the real one |
| Success — the last layer's shapes differ | `norm-L` is `{n_embd,1}` at `L == n_layer-1` | `S` `mf-narrow-shapes`; `Q` the transcript's `norm-27` |
| Failure — a missing or inconsistent geometry field | `geometry_fault` | `S` R5A's fifteen `-missing-*` and ten precondition rows, re-pointed at the model arm |
| Malformed input — an unusable bit pattern | `bits32_finite_nonnegative` | `S` R5A's eight rows |
| Early exit — unsupported arch or rope | step 9 | `S` `mf-geometry-arch`, `mf-geometry-rope-scaled` |
| Scalars — mask at two widths, attention scale | `mask_image(width, height)`, `attn_scale_bits` | `S` `mf-mask-image` at `{3,3}` and `{8,3}` against checked-in goldens |
| Cleanup | no handle, no file, no `unsafe` | `S` the `unsafe`/`extern` scan names only `src/ggml_ffi.align` |

### 4.2 `src/ggml_ffi.align` and the two C files

| Cell | Owner | Regression |
| --- | --- | --- |
| Construction — `pad`, `cont_2d` | one `unsafe` block each | `S` the engine implements both; `Q` the real shim |
| Success — status `0` | `r5_code_for` extended with the seven new codes | `S` `mf-status-map`: every negative shim status maps to exactly one `R5_*`, none unmapped |
| Failure — `pad` bounds | each `p >= 0`, result element count bounded | `S` `mf-force-pad-negative`, `mf-force-pad-oversize` |
| Malformed input — slots | bounds-checked as R5A | `S` `mf-force-slot-range`, `mf-force-slot-empty` |
| Move in/out — no aggregate holds `raw` | named locals only | `S` the record-declaration scan over `src/` |
| Cleanup — per graph | `stage_teardown_graph`, total against null | `S` `mf-teardown-partial`: a failure at layer 13 still runs the full teardown and the counters balance |
| The two C files agree | the shared-contract marker block | `S` byte-identity assertion |
| No `malloc` | neither file allocates | `S` `grep -c malloc scripts/ggml_shim*.c` is `0` |
| Contraction off | `#pragma STDC FP_CONTRACT OFF` plus `-ffp-contract=off` | `S` `abi.fp_contract_off` asserted `true` on every document |

### 4.3 `src/model_forward.align` — the arm

| Cell | Owner | Regression |
| --- | --- | --- |
| Formation — arm selection | first operand, before path work | `S` `mf-arm-unknown-flag`, and `arm-r5a-unchanged` asserting `--layer-forward` still emits `R5_LAYER_FORWARD` |
| Formation — role-qualified block selection | `find_block_with_role` | `S` `mf-block-ambiguous` (two blocks carrying `role_id` 12) → `R5_BLOCK_AMBIGUOUS`; `mf-block-missing-output` → `R5_BLOCK_MISSING`; `Q` `selection.embedding_block_index == 0` and `output_block_index == 57` |
| Formation — layer coverage | `validate_coverage` | `S` `mf-coverage-gap` (a pack missing `MlpBlock` at layer 1) → `R5_LAYER_COVERAGE`, detail `layer[1]` |
| Construction — window sizing | `size_window` | `S` `mf-window-peak`: `window.peak_block_kind` is the output block on the synthetic model too; `mf-window-budget` on a member record declaring 2^40 bytes → `R5_WINDOW_BUDGET`; `Q` `window.bytes == 447082528` and `peak_block_layer == -1` — corrections C11 and C21: `mf-window-budget` is not input-reachable and the measured window is `447086592` |
| Construction — the read schedule | `stage_read_block` | `S` `schedule[].pread_count` is `1` per block and `T` for the embedding; `Q` 58 `pread` groups over 30 window fills, 4,370,571,072 B |
| Success — the residual carry | `carry_residual` | `S` `mf-residual` asserts `schedule[L].l_out_ne1` is `T` for `L < 27` and `1` for `L == 27`; `mf-force-residual-short` → `R5_RESIDUAL`, detail `layer[<n>]` |
| Success — the narrowing | the two `node_when == 1` rows | `S` the synthetic model's golden document; `Q` `selection.narrow_layer == 27`, `narrow_index == 5` |
| Success — the head | `head_node_table`, `stage_head` | `S` golden `output.element_count == 32`; `Q` `== 152064` |
| Success — window reuse is safe | every buffer freed before the next read | `S` `lifetime.ggml_buffers_created == ggml_buffers_freed` asserted **per layer**, not only at the end; `mf-force-buffer-leak` (a build that skips one free) fails the per-layer assertion |
| Failure — each error code | `stage_*` | section 4.5 |
| Early exit — `-` document destination | `run` | `S` `mf-doc-stdout-identical` |
| Return — exit mapping | R0's, verbatim | `S` `mf-exit-codes` |
| Cleanup | section 3.10's order | `S` `mf-teardown-partial`; `Q` counters balance and `released_before_owner_scope_end` is `true` |

### 4.4 The three oracles

| Cell | Owner | Regression |
| --- | --- | --- |
| Reference — bytes equal, per block | `compare_source` | `S` `mf-source-diverged` at layer 9 → `R5_SOURCE_DIVERGED`, detail `layer[9]…`; `Q` all 338 members equal |
| Reference — nodes identical, per graph | `stage_reference_graph` | `S` all nodes of all four synthetic graphs; `mf-force-reference` names `graph[<n>]node[<id>]@<index>`; `Q` **479 of 479** |
| Transcript — grammar | `scan_transcript` | `S` `mf-transcript-garbage` → `R5_TRANSCRIPT` |
| Transcript — every layer matched | `layers_matched` | `S` `mf-transcript-missing-layer` (layer 1's records deleted) → `R5_ORACLE_MISSING`, detail `layer[1]node[norm]`; `Q` `layers_matched == 28` |
| Transcript — the element-count rule | R5A correction C19's rule, per node per layer | `S` `mf-transcript-headers`, `mf-transcript-novalues`; `Q` `elements_compared == 30042` |
| Transcript — `kq-L` `ne0` against `KV_WIDTH` | step 30 | `S` `mf-transcript-kv-width` (a transcript whose `kq-0` is `{8,…}` against `KV_WIDTH` 16) → `R5_ORACLE_SHAPE` |
| Transcript — excluded nodes | `oracle: "shape_incomparable"` | `S` asserted for `kq` and `kq_soft_max` in all layers of the golden |
| Transcript — a tolerance breach | step 31 | `S` `mf-transcript-perturbed`: one printed value at layer 1 moved by `0.0003` → `verdict: "FAIL"`, `worst_layer: 1`, `status: "ok"` |
| Transcript — an exact pass | step 31 | `S` `max_abs_diff_ten_thousandths == 0`; `Q` `== 0` over 30,042 elements |
| Logits — file shape | step 32 | `S` `mf-logits-short` (one byte) → `R5_LOGITS_SHAPE`, `mf-logits-missing` → `R5_LOGITS_UNREADABLE` |
| Logits — byte-identical at the reconciliation width | `compare_logits` | `S` the synthetic model's synthetic logits blob → `IDENTICAL`; `Q` `byte_identical: true`, `reference_sha256 == d2e48620…` |
| Logits — the runtime width verdict | `compare_logits` | `S` `mf-logits-runtime-width` asserts `WITHIN` with `argmax` equal; `Q` `max_abs_diff_ten_thousandths <= 5000` with **2,738** recorded, `argmax_primary == argmax_reference == 671`, `top_k_agreement == 10` |
| Logits — a real failure is not `WITHIN` | `compare_logits` | `S` `mf-logits-perturbed`: a reference blob shifted by 1.0 → `verdict: "FAIL"` with the argmax still equal, so the tolerance alone cannot pass it |
| Tolerances not silently widened | three document fields | `S` goldens assert `1`, `1`, and `5000`; a change is a diff in three places |

### 4.5 Error-code-to-fixture map

| Code | Stub-reachable | Fixture |
| --- | --- | --- |
| `R5_ARITY` | yes | three, seven, and ten operands, and one unknown flag |
| `R5_PATH` | yes | empty, 4097 bytes, embedded NUL, on each of four path operands |
| `R5_TOKENS` | yes | ``, `1,`, `1, 2`, seven ids, an id `== n_vocab` |
| `R5_KV_WIDTH` | yes | ``, `-1`, `+8`, `2` (below the token count), `4097` |
| `R5_GEOMETRY_UNREADABLE` | yes | a path that does not exist |
| `R5_GEOMETRY` | yes | R5A's thirty-three rows, re-pointed |
| `R4_PACK_*` | yes | R5A's mutated-pack corpus, reused |
| `R5_BLOCK_MISSING` | yes | a pack with no output `WeightBlock` |
| `R5_BLOCK_AMBIGUOUS` | yes | a pack with two blocks carrying `role_id` 12 |
| `R5_LAYER_COVERAGE` | yes | a pack whose layer 1 has no `MlpBlock` |
| `R5_MEMBER_MISSING` | yes | a pack whose layer 1 attention block omits `attn_q_bias` |
| `R5_SHAPE` | yes | an `output` member whose `ne1` is not `n_vocab` |
| `R5_WINDOW_BUDGET` | yes | a member record declaring 2^40 bytes |
| `R4_WINDOW_UNAVAILABLE` | no — not input-reachable | `N/A`, as R5A and Request 35 record |
| `R4_PACK_UNREADABLE` | yes | a pack truncated inside layer 1's mlp block |
| `R5_GGML_UNAVAILABLE` | yes | the default stub — the whole owner test's baseline |
| `R5_ABI` | no | `Q`, and only if the linked ggml drifts |
| `R5_TYPE_UNSUPPORTED` | yes | an `output` member carrying ggml type `4` |
| `R5_ALIGNMENT` | yes | a synthetic pack whose `block_align` is `1` |
| `R5_GGML_INIT` | yes | `ALIGN_GGML_FORCE_INIT_FAILURE` |
| `R5_SLOT` | yes | out-of-range and empty-slot forced builds |
| `R5_ALLOC` | yes | `ALIGN_GGML_FORCE_ALLOC_FAILURE`, at graph 14 |
| `R5_COMPUTE` | yes | `ALIGN_GGML_FORCE_COMPUTE_FAILURE`, at graph 14, detail `layer[13]` |
| `R5_RESIDUAL` | yes | a forced build whose readback is short by four bytes |
| `R5_SOURCE_UNREADABLE` | yes | a `REF.gguf` that is one byte long |
| `R5_SOURCE_DIVERGED` | yes | a pack and GGUF that disagree in one byte of layer 9 |
| `R5_REFERENCE_MISMATCH` | yes | `ALIGN_GGML_FORCE_REFERENCE_PERTURBATION` |
| `R5_TRANSCRIPT` | yes | a transcript of random bytes |
| `R5_ORACLE_MISSING` | yes | a deleted layer, a headers-only transcript, a values-free transcript |
| `R5_ORACLE_SHAPE` | yes | a `kq-0` declaring the wrong `ne0` |
| `R5_LOGITS_UNREADABLE` | yes | a path that does not exist |
| `R5_LOGITS_SHAPE` | yes | a blob of 4 bytes |

**Thirty of the thirty-two codes are stub-reachable**, and all seven new ones are. The two that
are not are the two R5A already marked unreachable, both fail-closed guards over conditions no input
can produce. The final matrix-to-diff pass maps every cell above to its implementing function and its
passing evidence, or to an explicit deferral in this document, before review.

---

## 5. Fixtures, qualification, metrics, deferrals, risks, and candidate requests

### 5.1 Owner — `make layer-forward-smoke`, extended

Hosted, ggml-free, model-free, llama.cpp-free. **`layer-forward-smoke` is already a member of
`HOSTED_CHECK_TARGETS`, so R5B adds rows to an existing target and changes no aggregate membership
and no check topology**, and `model-forward-qualification` joins no aggregate, as
`layer-forward-qualification` does not.

That is the whole of the claim, and it is narrower than the one this section first made. R5B does
**not** thereby avoid the fresh-image scope: adding the `model-forward-qualification` recipe and its
`.PHONY` entry edits the `Makefile`, which is an executable contract boundary, and
`scripts/verification_scope.py` classifies the R5B diff as
`{"docs_only": false, "hosted": true, "fresh_focused": true, "fresh_installed": true, "scope":
"fresh-image"}` (`--base ccbd8ae --head <R5B head>`). The classifier's verdict, not this paragraph,
is the evidence, and what R5B inherits from R5A is a scope selection, not an exemption from one.
The true difference from R5A is only that no *aggregate membership* changed and that the new
qualification target is a member of neither `HOSTED_CHECK_TARGETS` nor
`CAPABLE_ONLY_CHECK_TARGETS`.

**A synthetic two-layer model, so the whole prefill is hand-checkable.**
`scripts/layer_forward_fixture.py` gains a `--model` mode writing a pack, a geometry document, a
transcript, and a logits blob for:

```text
n_embd 8   n_head 2   n_head_kv 1   head_dim 4   n_ff 16   n_vocab 32   n_layer 2
rope.type 2   rope.dim_count 4   rope.freq_base 10000.0   rms_eps 1e-05   scaling_type null
tokens: three ids   KV_WIDTH: 8 (so the reconciliation pass is exercised)
```

Six blocks — embedding, two attention/mlp pairs, output — and **twenty-seven** members, every one
F32. Four graphs: `1 + 31 + 33 + 3` = **68** nodes at the runtime width and `1 + 34 + 36 + 3` = **74**
at the reconciliation width. The expected numbers come from the script's **pure-Python
forward pass**, importing only `json`, `math`, `os`, `struct`, and `sys`
(`r5a-dense-layer-forward.md` section 6, correction C24), which now runs the whole model including
the narrowing and the head and writes the `32 * 4`-byte logits blob the logits oracle compares
against. **A second implementation computing the same model is what makes the logits oracle
stub-reachable at all**, and it is the only way section 4.4's `IDENTICAL` cell can be checked on a
host with no model.

The synthetic geometry is chosen so `n_vocab` (32) differs from `n_ff` (16) and from
`n_head * head_dim` (8): a fixture whose dimensions collide cannot catch a transposed head.

**A checked-in real-model transcript excerpt**, `eval/fixtures/qwen2-model-6tok.txt`: `embd`,
`kq-0`, the twenty-eight `l_out-L` records, layer 27's attention output projection `node_1084`,
`ffn_inp-27`, `ffn_norm-27`, `result_norm`, and `result_output` — **35 records, 460 lines,
31,665 bytes**, against the whole transcript's 2,040,172. The two layer-27 records are the
narrowing's first visible pair (correction C3), and `node_1084` is the node correction C12 turned
into a compared one. It is swept from the qualification by
`scripts/sweep-model-forward-excerpt.py`, which matches the attention output projection by its source
weight name and never by `node_NN` (`r5a-dense-layer-forward.md` section 6, correction C21). It is
compared hosted for **grammar, node identity, and layer coverage only**; its numbers are the
qualification's.

Every fixture's expected document is a checked-in golden compared **byte for byte**. R5A's four
non-fixture assertions are inherited unchanged, and R5B adds one: **`lifetime.*_created ==
*_freed` is asserted at every layer boundary**, not only at the end, because window reuse is the one
new invariant a whole-run check cannot see.

The smoke writes into a `mktemp -d` tree outside the work tree and removes it on every exit path,
with R5A correction C22's shim-restoring trap.

**Budget.** `make layer-forward-smoke` measures **8.120 s** today for 82 cases. Section 5.5 records
the module split that keeps it there.

### 5.2 Named qualification — `make model-forward-qualification`, `scripts/run-model-forward`

Opt-in, capable-only, in **neither** `HOSTED_CHECK_TARGETS` nor `CAPABLE_ONLY_CHECK_TARGETS`. It
prints one explicit `N/A` line naming the missing input and exits `0` when any of

```text
ALIGN_LLM_GGML_INCLUDE            ggml headers
ALIGN_LLM_GGML_LIB                ggml libraries
ALIGN_LLM_GGUF_MODEL              the Qwen2 GGUF
ALIGN_LLM_LLAMA_EVAL_CALLBACK     path to llama-eval-callback
ALIGN_LLM_LLAMA_DEBUG             path to llama-debug                        # new
ALIGN_LLM_MODEL_FORWARD_TMPDIR    where the pack is written; defaults to TMPDIR
```

is unset, or the model or either instrument is absent, or free space under the scratch root is under
the pack's size plus 1 GiB. `ALIGN_LLM_LLAMA_DEBUG` is the only new environment input.

Otherwise it builds the real shim, packs the model with `./main --pack`, emits the geometry with
`./main --model-ir`, captures **both** instrument outputs with the **exact same** flag set section
2.2 established, and runs:

```text
$ FLAGS="-p \"def add(a, b):\" -n 1 -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512"
$ $ALIGN_LLM_LLAMA_EVAL_CALLBACK -m $MODEL $FLAGS > $TRANSCRIPT
$ $ALIGN_LLM_LLAMA_DEBUG        -m $MODEL $FLAGS --save-logits --logits-output-dir $LG
$ ggml-spike --model-forward $PACK $GEOM 750,912,2877,11,293,1648 \
      $DOC $MODEL $TRANSCRIPT 256 $LG/llamacpp-qwen2.5-coder-7b-instruct-q4_k_m.bin
```

It first asserts the two instruments agree — the f32 sequential sum of the logits file equals the
`sum` the transcript prints for `result_output`, and `llama-debug`'s `-tokens.bin` equals the six ids
— **before** running the arm, so an instrument skew is reported as an instrument skew and not as a
failing oracle. Then, against section 2's recorded values:

| Assertion | Expected |
| --- | --- |
| `status`, `verdict` | `ok`, `EXTERNAL` |
| `model.n_layer`, `n_vocab`, `output_tied`, `output_ggml_type` | `28`, `152064`, `false`, `14` |
| `selection.embedding_block_index`, `output_block_index` | `0`, `57` |
| `selection.narrow_layer`, `narrow_index`, `attention_width`, `reconciliation_width` | `27`, `5`, `6`, `256` |
| `schedule[]` length; `schedule[0].attention_bytes` + `mlp_bytes` | `28`; `149112832` |
| `schedule[L].attn_v_ggml_type == 14` | for exactly the fourteen layers section 2.1 names |
| `window.bytes`, `peak_block_layer`, `reuse_count`, `pointer_identity_failures` | `447086592` (correction C21), `-1`, `30`, `0` |
| `window.member_placements` | `339` |
| `graph.graph_count`, `node_count_total`, `reconciliation_node_count` | `30`, `874`, `958` |
| `graph.slot_high_water`, `slot_capacity` | `52`, `128` |
| `graph.activation_bytes_peak` | `2437120` |
| `output.element_count`, `argmax` | `152064`, `671` |
| `reference.verdict`, `graphs_compared`, `nodes_compared`, `nodes_identical` | `IDENTICAL`, `30`, `479`, `479` |
| `oracle.verdict`, `layers_matched`, `nodes_expected`, `elements_compared` | `PASS`, `28`, `479`, `30078` (correction C12 supersedes this row's original `30042`) |
| `oracle.max_abs_diff_ten_thousandths`, `tolerance_ten_thousandths` | `0`, `1` |
| `oracle_logits.verdict`, `byte_identical`, `reference_sha256` | `IDENTICAL`, `true`, `d2e48620ae3e31e2066a6172aa32c19c974d996d232ab91b118335e3d245bf74` |
| a second run at `KV_WIDTH` = `6`: `oracle_logits.verdict`, `max_abs_diff_ten_thousandths`, `argmax_primary`, `top_k_agreement` | `WITHIN`, `<= 5000`, `671`, `10` |
| `lifetime.*_created == *_freed`, `released_before_owner_scope_end` | equal, `true` |
| `abi.tensor_alignment`, `table_drift`, `fp_contract_off` | `32`, `-1`, `true` |

Then the ggml-only fixtures of section 4.5, then it removes the pack, both instrument outputs, and
the tree — on every exit path, including a signal.

**`schedule[].l_out_sha256` is recorded and not asserted as a checked-in golden**, for
`r5a-dense-layer-forward.md` section 5.2's reason: twenty-eight such constants would fail on any ggml
kernel change with a message that reads like corruption. The three oracles are the acceptance
contract; the digests name *which layer* moved when one of them fails.

### 5.3 Metrics

| Metric | Definition | Baseline on this host |
| --- | --- | --- |
| microbenchmark **B**, CPU compute, whole model | one six-token prefill, twenty-eight layers plus the head, warm | **349.6 ms** at the runtime width, **394.1 ms** at the reconciliation width; wall **1,071–1,121 ms** over six runs |
| per-layer compute | layers 0–26, median | **13.50 ms** runtime, **14.57 ms** reconciliation — consistent with R5A's 12.97–15.05 ms |
| layer 27 compute | after the narrowing | **4.30 ms** — 3.1× cheaper than a full-width layer |
| head compute | `RMS_NORM`, `MUL`, `MUL_MAT` against 447 MB of Q6_K | **9.5–11.2 ms** |
| `pread`, whole model | 58 `pread` groups | **532.9 ms** for 4,370,571,072 B — **1.5× compute**, warm page cache |
| `pread`, per layer | median | **18.7 ms** for 131–149 MB |
| reused window | section 3.5's sweep | **447,082,496 B** — 9.5% of a 4.68 GB model; the largest layer pair it holds during the twenty-eight layers is 149,112,832 B, 3.2% |
| peak RSS | the shipped arm | **513,638,400 B**; the self-reference arm 960,626,688 B |
| activation, peak | `ggml_gallocr_get_buffer_size`, over 30 graphs | **1,536,000 B**, or 2,437,120 B with the seventeen oracle nodes marked |
| residual carry | Align-owned, between graphs | **86,016 B** |
| cost of bit-exactness | reconciliation minus runtime | **+44.5 ms compute (+12.7%), +0 bytes read** |
| microbenchmark **A** | transfer + GPU compute | **N/A** — no GPU arm and no transfer tier. Section 5.4 |
| microbenchmark **C** | async prefetch + GPU compute | **N/A** — R5B ships no residency policy. Section 5.4 |

These are secondary metrics and R5B makes **no** claim on time to a passing patch. Their purpose is
one number: **at 533 ms of `pread` against 350 ms of compute, a six-token prefill of this model on
this CPU is I/O bound even with the whole file in page cache.** That is the measurement a residency
policy has to beat, and it is the reason R6's policy should be designed against a baseline rather
than against an intuition.

### 5.4 Deferred surfaces

- **The KV cache and decode.** R5B computes one prefill. A decode step needs a cache tensor,
  `set_rows`, incremental positions, and a second graph shape — and it needs an **instrument**:
  `llama-eval-callback` prints six elements per row, so a cache of hundreds of positions is not
  observable through it, and `llama-debug --save-logits` publishes only the final position. R6's
  first task is naming the oracle, not writing the cache. Section 2.7's reconciliation pass is the
  measurement that says what the cache will cost in agreement terms: **nothing**, because at a
  matched reduction width the answer is already byte-identical.
- **Lifting `MAX_PREFILL_TOKENS` above 6.** Same blocker, same owner. R6.
- **A residency policy.** Cache score, eviction, tiering across GPU/system/NVMe, and prefetch.
  Section 5.3 is its baseline. `docs/specs/align-llm.md`'s residency section is the design of record
  and R5B changes none of it.
- **A window per block class.** Section 3.5 accepts 298 MB of idle window during the twenty-eight
  layers because the head sizes the sweep. A second window, or a window that shrinks after the last
  layer, is an R6 measurement against section 5.3's 513,638,400 B peak — not a correctness question.
- **Microbenchmarks A and C, and the Metal arm.** Inherited from `r4-5-external-buffer.md` section
  5.4 with its measurement: Metal accepts the same host pointer with no copy on unified memory but
  does not produce bit-identical output. R5B's logits oracle at a matched width is exactly the
  instrument that arm will need to become a tolerance oracle with a justified bound rather than a
  guessed one.
- **Geometry in the container.** Unchanged from `r5a-dense-layer-forward.md` section 5.4: an
  alignpack v2 carrying the `R1_MODEL_IR` `model` object would make a loader a one-file consumer.
  R5B deliberately does not open a v2, and the argument is now stronger, because a whole-model arm
  taking two files is the exact shape a loader will not want.
- **Renaming to `align-runtime`.** R5A deferred this "to the R5B boundary, where the loader
  arrives". It has not. The condition is now explicit: **the rename happens when the executable
  gains a residency policy**, and `ggml-spike` is retained as a deprecated alias for one release
  when it does.
- **MoE and a second architecture.** `r4-alignpack-layer-major.md` section 4.5's **MOE-PREREQ** and
  `r5a-dense-layer-forward.md` section 5.4's second-architecture condition, both unchanged.
- **A read-only pack open.** The reader still uses `fs.open_rw`. R5B is the **fifth** client for
  Request 21 and the first that holds the file open across 58 reads and 4.4 GB.

### 5.5 Candidate Align capability requests

**No new request is expected.** Every probe in section 2 compiled and ran on the pinned surface, and
the two new shim symbols are one ggml call each behind R5A's existing wrapper contract. R5B is new
client evidence for six requests that already exist:

- **Request 37 — per-function check time is superlinear in body length.** R5B is its most direct
  client, and it **shapes a module boundary before any code is written**. Measured at this pin on
  this host: `make layer-forward-smoke` is **8.120 s** for 82 cases, and `gmake check` is **91.2 s**
  for 29 units. `src/layer_forward.align` is already 3,334 lines. Section 3.10 therefore puts the
  R5B arm in a **new module**, `src/model_forward.align`, rather than in `src/layer_forward.align`,
  and keeps `r5a-dense-layer-forward.md` section 6, correction C8's discipline — no function over
  two hundred lines, every fallible call inside a loop propagating with `?`, never a `match` on a
  `Result` inside a loop. The acceptance target is that `check-per-unit src/model_forward.align`
  stays **under 10 s** and `make layer-forward-smoke` stays under 15 s; if either is exceeded, the
  arm splits again along the schedule/oracle boundary rather than absorbing the cost. This is a
  compiler property dictating an application's module graph, which is precisely why C8 reclassified
  it from client evidence to a request.
- **Request 34 — `Result` ok payloads beyond scalars.** Unchanged in kind, larger in degree: the
  slot store now backs four node tables across thirty graphs, and every one of the 958 handles the
  run creates passes through it because `raw` is neither a struct field nor an array element.
- **Request 33 — aligned heap allocation.** Now paid **once** rather than R5A's thirteen times,
  because there is one window; but the window is 447 MB and the over-reservation is still a
  `MAX_TENSOR_ALIGNMENT` pad on a `buffer(n)` that takes no alignment. The client is bigger and the
  gap is the same.
- **Request 32 — FFI by-value structs and `bool` on AArch64.** Unchanged; two more wrapped call
  sites (`pad` has none, `gallocr` still does).
- **Request 21 — a read-only open**, section 5.4's fifth client.
- **Request 36 — owned `array<i64>` field replacement.** `schedule[]` is twenty-eight rows of
  fourteen columns and is built exactly the way correction C9 forced R5A's columns to be built: one
  record per column set, assigned as a whole by the stage that produces it.

If the implementation refutes this section — as R5A's did, filing two requests from work the design
had declared clean — the correction belongs in a section 6 of this document, not in a quiet edit
here.

### 5.6 Risks

| Risk | Mitigation | Residual |
| --- | --- | --- |
| **The 4.68 GB pack does not fit, or evicts the model from page cache.** The host has 24 GiB free and 16 GiB of RAM; the pack plus the model is 9.4 GB | The qualification refuses with an `N/A` line below the pack's size plus 1 GiB, and removes the pack on every exit path including a signal | Timings are cache-state dependent and the document says so: section 5.3's 533 ms is warm. R5A section 7.7 already measured 55 ms per layer on a freshly written pack against the probe's 19.5 ms, a 2.8× spread that is the cache and not the read shape |
| **958 opportunities for `ggml_abort`**, against R5A's 32 | Every reachable precondition is validated before the first read — geometry, coverage, shapes, **types**, window budget — and per-member alignment is re-checked at every layer. Step 22 moving the type check ahead of all I/O exists for exactly this | An internal kernel assertion still takes the process down with no document. The exposure grew 30×; the mitigation is that the validated surface grew with it |
| **Two instruments must be pinned by the same flags, and one of them was not.** Section 2.2 measured 0.30 of a logit for a missing `-nr`, with the argmax unchanged | The flag set is contractual in section 5.2, used verbatim for both, and the qualification cross-checks the two instruments against each other **before** running the arm | A future build could change a default in one instrument and not the other. The cross-check turns that into a named instrument-skew failure rather than an oracle failure |
| **The window is reused thirty times and a stale pointer is silent.** A tensor left alive across a read would compute the *next* layer's bytes with the previous layer's weights, producing a plausible number | Every ggml buffer wrapping the window is freed before the next read begins, and `lifetime.*_created == *_freed` is asserted **per layer** (section 5.1). The self-reference oracle, which computes from ggml-owned copies, catches any surviving case: 479 of 479 | A leak that happens to free before the *next* assertion point would pass. This is why the reference oracle is per graph and not per run |
| **The reconciliation width is llama.cpp's number and it could change** | It is an **operand** with no default, validated against `kq-L`'s declared `ne0` in the transcript. R5B never contains the value 256 | A build that changes its cache padding changes the qualification's operand, which is a one-line diff and a visible one — and the runtime pass, which is what R5B actually computes, is unaffected |
| **The logits tolerance at the runtime width is 5,000 ten-thousandths, which is large** | It is not the acceptance contract: the `IDENTICAL` verdict at the reconciliation width is. The `WITHIN` verdict additionally requires the argmax and the whole top ten to agree, and `mf-logits-perturbed` proves a 1.0 shift fails it while keeping the argmax | A defect that moves every logit by under 0.5 *and* preserves the top ten *and* survives byte-identity at the matched width is not constructible: the byte-identical arm shares every node with the tolerant one |
| **Non-uniform blocks.** Fourteen of twenty-eight layers differ in two members' types | The window is a sweep, not a formula; `schedule[].attn_v_ggml_type` and `ffn_down_ggml_type` are document fields the qualification asserts against section 2.1's exact layer list | A pack whose block sizes disagree with its member records is a container defect and `alignpack_read` owns it |
| **Tied embeddings.** This model is untied; the packer supports tied | `model.output_tied` is derived from the two members' resolved tensor names, published, and the tied path reads the head's weight from its own member record. The synthetic fixture covers both | No tied Qwen2 GGUF is on this host, so the tied path is `S`-only until one is. Section 4.5 says so rather than implying `Q` coverage |
| **The transcript is 2 MB and the excerpt is 30 KB** | The excerpt is swept from the qualification and is compared hosted for grammar, node identity, and layer coverage only | A stale excerpt cannot produce a false `PASS`, because its numbers are never asserted hosted |
| **`schedule[]` replaces per-node digests and could hide which node moved** | The transcript oracle publishes `worst_layer`, `worst_node`, and `worst_element_index`, and the reference oracle publishes `first_difference_graph` and `first_difference_node` | A failure with **no** oracle running reports only the layer. That is the six-operand form, which no acceptance path uses |
| **The goldens become a property of one compiler on one target** | R5A correction C15's `#pragma STDC FP_CONTRACT OFF`, `-ffp-contract=off`, and the asserted `abi.fp_contract_off` | Unchanged from R5A, and now across a whole model's worth of stub-engine kernels |
| **`make layer-forward-smoke` grows past its budget** | Section 5.5's module split and its stated acceptance target | If the split is insufficient, the owner test itself splits — which changes check topology and re-selects `make ci`. Section 5.1's classifier verdict is what decides, not this table |

---

## 6. Implementation-forced corrections

Section 3 was written after the probes of section 2 and before the implementation. Sixteen of its
statements were refuted by writing the arm, and each one is recorded here rather than quietly edited
above. Six are Align-owned limitations, five are contract changes the plan could not have known
about, and five are measurements that moved.

**C17 to C21 were found by review**, not by writing the arm. They are recorded in the same list and
by the same rule — the plan is corrected here rather than silently rewritten above — and each names
the case that now covers it.

### C1 — the plan's second new shim symbol was never needed

Section 3.6 declared two new symbols, `align_ggml_op_pad` and `align_ggml_op_cont_2d`. The second
does not exist: `align_ggml_op_cont_3d` already covers the narrowed `kqv_out` at `ne2 = 1` **and**
the reconciliation pass's contiguous K, exactly as `r5a-dense-layer-forward.md` section 6 correction
C4 established for R5A and for the same reason. `pad` is the only new *op*. The symbol count is
still two, because correction C5 needed one the plan did not predict.

### C2 — `node_when` alone cannot express a conditional operand

Section 3.6's `node_when` column selects which **rows** a graph issues. It cannot say what the plan
also needs it to say: a condition that adds a row also moves the *operand* of the row that consumes
it. The reconciliation rows produce a padded K and a padded V, and `kq` and `kqv` must read those
instead of the unpadded ones; the two narrowing rows produce a narrowed `attn_out` and a narrowed
residual, and `ffn_inp` must read those instead.

Rewriting the consumer's `node_out` to overwrite its source's slot was rejected: it would make
"every `node_out` written once" — the property section 4.1's `mf-node-table-shape` asserts —
false. The table therefore gains three columns, `node_alt_when`, `node_alt_a`, and `node_alt_b`:
a row whose `alt_when` condition holds reads `alt_a`/`alt_b` instead of `a`/`b`, and `-1` leaves
that operand alone. Exactly three of the thirty-six rows use them.

### C3 — `norm-L` is `{n_embd, T_in}` at **every** layer, including the last

Section 3.7 states that `norm-L` is `{n_embd, 1}` at the last layer, from the `norm-27` record
section 2.3 quotes. That record is the **second** `norm-27`: llama.cpp's `build_norm` emits
`cb(cur, "norm", il)` for the attention norm *and* for the feed-forward norm, so every layer
prints two `norm-L` records, and R5A's first-match rule — inherited unchanged — matches the
attention one. Confirmed against the instrument: `norm-27` contributes **36** printed elements,
which is `{3584, 6}`, not the six of `{3584, 1}`.

The narrowing is visible from `ffn_inp-L` onward and nowhere earlier. The seven nodes that are
`{*, 1}` at the last layer are `ffn_inp-27`, `ffn_norm-27`, `ffn_gate-27`, `ffn_up-27`,
`ffn_swiglu-27`, `ffn_out-27`, and `l_out-27`. Section 4.1's `mf-narrow-shapes` cell is discharged
against those and not against `norm-27`.

### C4 — the transcript is scanned before the schedule, not after it

Section 3.9 puts the transcript arm at steps 30 and 31, after the whole schedule. It cannot be
there. A layer's seventeen oracle nodes live in a `ggml_gallocr` buffer that is freed when that
layer's graph is torn down, and holding thirty graphs alive to compare them at the end is the exact
opposite of the ownership section 3.10 defines — it would cost thirty graphs' activations instead
of one.

The transcript is therefore **scanned once before the first graph** — grammar, the matched set, the
element-count rule of `r5a-dense-layer-forward.md` correction C19, and `kq-L`'s `ne0` against
`KV_WIDTH` — and **compared inside each graph**, against the pre-scanned elements, before that
graph's teardown. The only visible consequence is precedence: a `R5_TRANSCRIPT`,
`R5_ORACLE_MISSING`, or `R5_ORACLE_SHAPE` from the scan now precedes a `R5_COMPUTE` from the
schedule. Steps 30 and 31 are otherwise unchanged, and step 31's tolerance breach is still not an
error code.

### C5 — the reused window cannot be refilled from Align, and that is the second new shim symbol

Section 3.5's "one window, reused thirty times" is not expressible in Align at this pin, and this is
the largest single correction.

An Align `buffer` is append-only. `put_*` and `append` write at the logical length; there is no
offset write, no truncate, and no reset. `f.pread` is the only operation that rewrites a buffer's
contents, and it overwrites **from index 0** and always requests the buffer's **whole capacity**. A
447 MB window that is allocated once and refilled thirty times therefore has exactly three
implementations available, and two of them are wrong:

- refill by `pread` — reads the entire 447 MB window from the pack on **every** layer, 12.5 GB of
  I/O for 3.9 GB of weights;
- refill by reallocation — faults in 447 MB of fresh pages thirty times, and briefly holds two
  windows;
- refill by copying from a bounded transient, which needs a write into the middle of an
  Align-owned range.

The third is what ships. `align_ggml_window_copy(window, window_bytes, offset, source,
source_bytes, n)` is a bounded `memcpy` between two Align-owned byte ranges, added to the shim's
**shared** region so both C files answer it identically. It allocates nothing, opens nothing, and
reads no byte the caller did not hand over, so rule 2 of `scripts/ggml_shim.c` is unchanged. It is
the second of the two new symbols section 3.6 predicted — just not the one it named.

### C6 — the read shape is one group per member, and the transient is one mebibyte

Section 3.4 reads each block whole, "one `pread` of `block.pack_bytes` each, 56 times". With C5 in
force a block image would have to be read into a 132 MB temporary and copied out, which doubles the
resident set for the one graph that already sizes the window. Each **member** is read instead,
straight into its own window slot: the same bytes, in the same order, with a bounded transient.
`window.reuse_count` is still 30 and `bytes_read` is still 4,370,571,072 plus the 36,960 bytes of
member records the reader itself reads.

Two measurements forced the shape of that transient.

**`alignpack_read.read_exact` rebinds its window to a fresh `buffer(n)` on every call**, and at 339
members those allocations are not returned to the process while the caller's frame lives: peak
resident set measured **3,442,016,256 to 4,262,133,760 B** for a 447 MB window. Reading through one
buffer that `f.pread` refills in place brings it to **507,969,536 B** — below section 3.10's
predicted 513,638,400.

**`f.pread` always requests the buffer's whole capacity**, so an oversized transient over-reads the
tail of every member. At 32 MiB that is 5.4 GB of wasted I/O and 2.4 s of `pread`; at 1 MiB it is
339 MB and **515 ms**, which is section 5.3's number. `CHUNK_BYTES` is 1,048,576 for that reason
and no other.

### C7 — `output_tied` is derived from source-tensor identity, not from decoded names

Section 3.4 derives `model.output_tied` from the two members' **names**. Reading a name needs
`alignpack_read.member_at` and then `alignpack_read.member_name`, and at this pin the region checker
refuses to hold the first call's `PackMember` across the second while both take the same
`borrow mut Counters`: *"cannot retain a shorter-lived view through this mutable borrow; copy it
into the destination region first"*. Moving the pair into its own function did not help, because the
refusal is about the two calls, not about the caller.

`output_tied` is the two members' `source_offset` and `nbytes` agreeing instead. That is the same
fact and a stronger one — two members that are the same GGUF tensor carry the same source range
whatever they are called — and it costs two fewer file reads.

### C8 — the reference perturbation stops at slot 11

`ALIGN_GGML_FORCE_REFERENCE_PERTURBATION` flips one bit of every `slot_set` on slots 0 to 12,
which in R5A's slot map is exactly the thirteen reference weights. R5B's slot 12 is the
**Align-owned residual input**, which the primary arm also writes through `slot_set`, so the
unchanged macro would perturb both arms identically and the oracle would see nothing. The range now
stops at 11. R5A is unaffected in outcome: its first differing node is `embd`, which depends on slot
0, and `scripts/layer-forward-golden.jsonl` is byte-unchanged.

### C9 — the hosted logits oracle cannot exercise `IDENTICAL`, and exercises something better

Section 4.4 expects the synthetic model's logits blob to produce `IDENTICAL`. It cannot. The blob
comes from the generator's pure-Python second implementation, and byte-identity would require Python
and the stub engine to agree on `expf`, `sinf`, `cosf`, and `sqrtf` to the last bit, which no
portable pair of libm implementations does. The measured hosted difference is **zero
ten-thousandths** over all thirty-two logits, with the argmax and the whole top ten equal — and the
verdict is still `FAIL`.

That is the stronger hosted assertion, and `scripts/run-layer-forward-smoke` makes it one: at the
reconciliation width a reference that agrees to four decimal places, on the argmax, and on the whole
top ten is refused, which is exactly section 3.7's *"anything less is a regression, not a
tolerance"*. `IDENTICAL` remains `Q`-only, where both sides are ggml and section 5.2 measures it.

### C10 — `-` in the transcript position, or the logits oracle is unreachable at the runtime width

Section 5.2's second invocation runs at `KV_WIDTH` 6 to obtain the `WITHIN` verdict. It cannot: the
nine- and ten-operand forms require a transcript, `KV_WIDTH` travels with it, the transcript's
`kq-L` `ne0` is validated against `KV_WIDTH`, and the instrument only ever produces a transcript at
**its** width. `--model-forward PACK GEOM TOKENS DOC REF TRANSCRIPT 6 LOGITS` refuses itself with
`R5_ORACLE_SHAPE`, correctly.

The transcript position accepts `-` — "no transcript" — exactly as the document position already
does. `KV_WIDTH` keeps its own operand position and stays fail-closed with no default; seven
operands is still `R5_ARITY`.

### C11 — `R5_WINDOW_BUDGET` is not input-reachable

Section 4.5 lists it as stub-reachable from "a member record declaring 2^40 bytes". It is not:
`alignpack_read.member_at` validates a member against its own block's byte range, and the block
against the file, so a member claiming 2^40 bytes is `R4_PACK_OFFSET` long before the window sweep
sees it. The residual and logits bounds are unreachable for the same reason — every dimension they
are computed from is checked against the geometry first.

`R5_WINDOW_BUDGET` joins `R4_WINDOW_UNAVAILABLE` and `R5_ABI` as a fail-closed guard over a
condition no input can produce. **Twenty-nine of the thirty-two codes are stub-reachable**, not
thirty, and section 7 records that as a measurement the runner prints.

### C12 — the transcript oracle compares 479 nodes and 30,078 elements

Section 2.8 measured 478 nodes and 30,042 elements because the probe narrowed its `attn_out` handle
before dumping it, so `attn_out-27` was a shape disagreement the probe skipped. R5B's oracle row
points at the attention output projection **before** the two narrowing rows, which is where the
transcript's `node_1084` is, so it is compared like every other layer's: **479 of 479 nodes, 30,078
elements, max 0 ten-thousandths.** The self-reference oracle's 479 is unchanged.

### C13 — `output_norm`'s shape is checked by its row count

The plan checks `output_norm` is "1-D at `n_embd`". A container's `n_dims` is the packer's choice —
`scripts/layer_forward_fixture.py` writes `2` for every member, and R5A's member table never reads
it — so the check is `dim0 == n_embd && dim1 == 1`, which is the same claim about the same tensor
and does not depend on how a packer counted axes.

### C14 — the stub engine's fixed pools are recycled

`scripts/ggml_shim_stub.c`'s engine was written for R5A's single graph: its tensor pool, graph pool,
and arena are bump-allocated and never released. Thirty graphs times two passes times two arms
exhausts all three. The engine now resets itself the moment no context and no buffer is live, which
is precisely the boundary section 3.10 already requires the arm to reach after every graph — so a
caller that leaks one exhausts a pool and is told, rather than being hidden.

### C15 — both passes run in one invocation, and `member_placements` counts one of them

Section 5.2 asserts `graph.node_count_total` 874 **and** `graph.reconciliation_node_count` 958 in the
same run, which only holds if the runtime pass and the reconciliation pass both execute. They do:
one window fill feeds both, two Align-owned residuals are carried in parallel (section 3.10's
memory table lists both), and the reference arm mirrors whichever pass section 3.7 names as
compared. `timings.compute_ns` and `timings.reconciliation_compute_ns` are the two measurements
this makes possible, and section 5.3 now carries them from the arm rather than from the probe.

`window.member_placements` is counted for the compared pass only. Both passes place the same members
at the same offsets in the same window, so counting both would report 678 where section 5.2 expects
339 and would measure nothing extra.

### C16 — the per-layer lifetime balance is a document field

Section 5.1 requires `lifetime.*_created == *_freed` "at every layer boundary", which a document
reporting only final totals cannot express. `lifetime.graph_balance_failures` counts the graph
boundaries at which any counter was unequal, and `released_before_owner_scope_end` requires it to be
zero. On every passing run, hosted and qualified, it is `0`.

### C17 — a partial run reports no verdict

Section 3.3 defines `verdict` as `EXTERNAL` when every weight tensor of every graph landed at its
own window offset, and section 3.7 defines `reference.verdict` as `IDENTICAL` when every oracle node
of every graph is byte-identical. Both were computed unconditionally from whatever the run had
accumulated when it stopped. An error document therefore claimed `EXTERNAL` and `IDENTICAL` from one
graph of thirty — `mf-engine-alignment`'s golden carried `verdict: "EXTERNAL"` beside
`graph_count: 4`, `node_count_total: 1`, and `status: "error"`.

Both are now gated on the run having produced the measurement they report. `verdict` is
`UNAVAILABLE` whenever an error code is set, and `reference.verdict` additionally requires
`reference.graphs_compared == graph.graph_count`. `verdict` is still settled **before** the two
oracle comparisons: a reference mismatch or a tolerance breach is a divergence in the arithmetic,
not in where the weights landed, and the placement measurement that reached that point is complete.
`mf-force-reference` therefore keeps `verdict: "EXTERNAL"` with `reference.verdict: "MISMATCH"`,
while every early-exit golden now carries `UNAVAILABLE` and `-`.

### C18 — the reference oracle's reads are their own pair of counters

`compare_source` reads the whole model a second time, out of the source GGUF, to prove the pack's
bytes are the model's bytes before any graph runs. It shared the window fills' `Counters`, so
`pack.reader_bytes_read` reported 8,741,179,104 B — both files — while `timings.pread_ns` timed only
the 4,370,608,032 B of window fills. Every bandwidth figure derived from that pair was 2× wrong, and
section 7.3's own "9,111 read groups over 8,741,179,104 B including the reference arm's own 4.37 GB"
is the sentence that had to explain it away.

The source comparison keeps its own counters and publishes them as `reference.pread_count` and
`reference.bytes_read`. `pack.reader_*` is now the container's alone and is the pair
`timings.pread_ns` times. Section 7.6's figures are restated against the corrected pair.

### C19 — `WITHIN` is `min(TOP_K, n_vocab)` ranks, not ten

Section 3.7's `WITHIN` verdict requires "the top ten equal, in order". `top_k` can only yield
`min(TOP_K, n_vocab)` ranks, so the implementation's `agreement >= TOP_K` made `WITHIN` unreachable
by arithmetic — never by measurement — for any model with fewer than ten tokens in its vocabulary.
The requirement is now `agreement >= min(TOP_K, n_vocab)`, which is the same claim ("the whole top
ten, in order") for every vocabulary that has ten.

**No fixture exercises the `n_vocab < 10` branch and this is a deliberate deferral.** Section 5.1's
synthetic geometry picks `n_vocab` 32 precisely so it differs from `n_ff` (16) and from
`n_head * head_dim` (8); a second synthetic model at `n_vocab` 8 would collide with the third of
those and would cost a second pack, geometry, transcript, logits blob, and golden block to cover a
branch that no shipped model reaches. The bound is correct by construction and the deferral is
recorded here rather than implied by an absent case.

### C20 — `window_copy` is bounded by the views, not by the caller's arithmetic

Section 3.5's `align_ggml_window_copy(window, window_bytes, offset, source, source_bytes, n)` takes
both lengths as operands, and `src/model_forward.align` threaded a separately computed
`window_bytes` through `window_put`, `read_into_window`, and `fill_members` to supply the first. A
declared length is a claim; the borrow's own `slice.len()` is the range that actually exists, and a
`memcpy` bounded by the first writes outside the second the moment the two disagree — which is one
arithmetic slip away in a function whose whole job is to compute interior offsets.

The Align wrapper now passes `window.len()` and `source.len()` and no longer accepts either length,
and `window_bytes` is no longer threaded through the read path at all. The C entry point's signature
is unchanged, so both shim files are untouched: the bound is simply always the true one. Every
`mf-engine-*` case is the regression, because every one of them fills the window through this path.

### C21 — the reused window is 447,086,592 B, and the over-reservation is not part of it

Section 3.10's memory table and section 5.2's acceptance row both predicted `447,082,496 + 32` and
called the sum the window. Two things are wrong with that. `window.bytes` is section 3.5's sweep
alone — `MAX_TENSOR_ALIGNMENT` over-reserves the *`buffer`* so the arm can hand ggml an interior
range that starts on a boundary, and never enters the published figure — and `MAX_TENSOR_ALIGNMENT`
is 64, not 32.

The sweep's own maximum is the head, `output_norm.nbytes + align_up(output.nbytes, block_align)`
against `r4-alignpack-layer-major.md` section 2.4's `block_align` of **4096**, which is
**447,086,592 B**. The probe's 447,082,496 is the same tensor rounded to 32 instead. Sections 2.9,
7.3, and 7.6 already carried the measured value; section 5.2's row did not, and because that row was
never implemented as an assertion the disagreement survived to review. It is now the asserted value
and `scripts/run-model-forward` checks it — which is also how sections 5.2's `reference.nodes_
compared` and `oracle.elements_compared` rows, both unimplemented for the same reason, became
assertions of 479 and 30,078 (correction C12).

### C22 — `graph_alignment`'s window-level check is unreachable defence

`graph_alignment` (`src/model_forward.align:1716-1733`) checks the window's own base, then every
member's window offset, both against `alignment` (0 mod `tensor_alignment`). Only the per-member
loop can actually fire in the shipped arm: `graph_alignment` runs only after `o.code.len() == 0`
following `ggml_ffi.buffer_from_host(device, window, window.len())` at line 1792, and that call
already rejects a misaligned `window` base by failing `R5_GGML_INIT`/`weight_buffer` before
`graph_alignment` is ever reached. The window-level `R5_ALIGNMENT`/`window` branch therefore cannot
be exercised by any reachable input; section 3.9 step 25's `R5_ALIGNMENT` row (window offset check,
detail `layer[<n>]role[<name>]`) is the per-member branch, never the window-level one. The branch
stays as defence — if `buffer_from_host`'s own check is ever relaxed or reordered, the per-member
loop below it must not silently assume an aligned base — and is now commented as unreachable rather
than implied live.

---

## 7. Closure-matrix evidence

Every cell of section 4, mapped to the case that discharges it and the value it produced. `S` cases
run in `make layer-forward-smoke` (11.0 s, three consecutive identical runs); `Q` cases run in
`make model-forward-qualification` (34.7 s end to end, scratch removed).

### 7.1 `src/layer_qwen2.align`

| Cell | Evidence |
| --- | --- |
| Three tables well-formed | `S` every `mf-engine-*` case: `graph.slot_high_water` 52 against `slot_capacity` 128, `node_count_total` 68 = 1 + 31 + 33 + 3 |
| Conditional rows form a graph at each condition | `S` `mf-engine-ok` (31 rows), `mf-engine-transcript` (`reconciliation_node_count` 74 = 1 + 34 + 36 + 3); `Q` 874 and 958 |
| Shapes derived per layer | `S` the synthetic model's 27 members; `Q` all 339, `R5_SHAPE` never raised |
| The last layer's shapes differ | `S` `schedule[0].l_out_ne1` 3 and `schedule[1].l_out_ne1` 1; `Q` `schedule[26]` `{3584, 6}` and `schedule[27]` `{3584, 1}` — **not** `norm-27`, correction C3 |
| A missing or inconsistent geometry field | `S` `mf-geometry-missing-n_layer`, `-n_vocab`, `mf-geometry-arch`, `mf-geometry-rope-scaled` → `R5_GEOMETRY` |
| An unusable bit pattern | `S` `mf-geometry-eps-nan` → `R5_GEOMETRY` |
| Early exit — unsupported arch or rope | `S` `mf-geometry-arch`, `mf-geometry-rope-scaled` |
| Scalars — mask at two widths | `S` `mf-engine-runtime-width` (3 x 3) and `mf-engine-transcript` (8 x 3); `Q` 6 x 6 and 256 x 6 |
| Cleanup — no handle, no file, no `unsafe` | `S` the `unsafe {` and `extern "C"` scans name `src/ggml_ffi.align` alone |

### 7.2 `src/ggml_ffi.align` and the two C files

| Cell | Evidence |
| --- | --- |
| Construction — `pad` | `S` `mf-engine-transcript`'s three `WHEN_WIDE` rows; `Q` 84 padded nodes across 28 layers. `cont_2d` was never written (C1) |
| Construction — `window_copy` | `S` every fill; `Q` 339 members, 4,370,571,072 B (C5) |
| Success — status `0` | `S` `mf-status-map` is discharged by the 29 codes the runner reaches; no status reached `R5_ABI` by default |
| Failure — `pad` bounds | `S` `mf-force-pad-negative`, `mf-force-pad-oversize` → `R5_SHAPE` |
| Malformed input — slots | `S` `mf-force-slot-range`, `mf-force-slot-empty` → `R5_SLOT` |
| Move in/out — no aggregate holds `raw` | `S` the record-declaration scan over `src/` |
| Cleanup — per graph | `S` `mf-force-compute` tears down fully; `lifetime.graph_balance_failures` 0 on every run |
| Alignment — per member, per layer, Align-side | `S` `mf-engine-alignment` → `R5_ALIGNMENT`, detail **`layer[0]role[attn_v]`** (C17's sibling: `graph_alignment` runs before `graph_weights`, so the detail is section 3.9's and not the shim's bare role name); `Q` never raised over 339 placements |
| Copy bounds are the views' own | `S` every `mf-engine-*` fills the window through `window_copy`, now bounded by `slice.len()` (C20) |
| The two C files agree | `S` the shared-contract byte-identity assertion |
| No `malloc` | `S` `grep -c malloc scripts/ggml_shim*.c` is `0` |
| Contraction off | `S` `abi.fp_contract_off` asserted `true` on all 55 documents; `Q` asserted `true` |

### 7.3 `src/model_forward.align`

| Cell | Evidence |
| --- | --- |
| Arm selection | `S` `mf-arm-unknown-flag` (no document), `arm-r5a-unchanged` still emits `R5_LAYER_FORWARD` |
| Role-qualified block selection | `S` `mf-block-ambiguous` → `R5_BLOCK_AMBIGUOUS`, `mf-block-missing-output` → `R5_BLOCK_MISSING`, `selection` 0/5; `Q` **0 and 57** |
| Layer coverage | `S` `mf-coverage-gap` → `R5_LAYER_COVERAGE`, detail `layer[1]` |
| Window sizing | `S` `window.peak_block_bytes == window.bytes`; `Q` **447,086,592 B** asserted (C21), peak block 57, `peak_block_layer` -1. `mf-window-budget` is `N/A` (C11) |
| The read schedule | `S` `window.reuse_count` 4; `Q` **30** fills, `pack.reader_*` 4,729 groups over 4,370,608,032 B, with the reference arm's own 4,382 groups over 4,370,571,072 B in `reference.*` (C18) |
| The residual carry | `S` `schedule[].l_out_ne1` 3 then 1; `mf-force-residual` → `R5_RESIDUAL` |
| The narrowing | `S` `selection.narrow_layer` 1, `narrow_index` 2; `Q` **27 and 5**, layer 27 compute 7.28 ms against a 26.55 ms median |
| The head | `S` `output.element_count` 32; `Q` **152,064**, argmax **671** |
| Window reuse is safe | `S` `lifetime.graph_balance_failures` 0; `Q` 0, and the self-reference oracle is `IDENTICAL` over 30 graphs |
| Each error code | section 7.5 |
| `-` document destination | `S` `mf-doc-stdout-identical`: the four-operand, `-`, and file forms are byte-identical |
| Exit mapping | `S` every case asserts `status == "ok"` iff exit 0 |
| No verdict from a partial run | `S` every early-exit golden now carries `verdict: "UNAVAILABLE"` and `reference.verdict: "-"`, `mf-engine-alignment` among them (C17) |
| Cleanup | `S` `released_before_owner_scope_end` true; `Q` true, peak RSS **507,969,536 B** shipped and **938,655,744 B** with the self-reference arm |

### 7.4 The three oracles

| Cell | Evidence |
| --- | --- |
| Reference — bytes equal, per block | `S` `mf-engine-source-diverged` → `R5_SOURCE_DIVERGED`; `Q` all 339 members equal, `reference.pread_count`/`bytes_read` counted apart from the window fills (C18) |
| Reference — nodes identical, per graph | `S` 37 of 37 over 4 graphs; `mf-force-reference` names the node and keeps `verdict: "EXTERNAL"` with `reference.verdict: "MISMATCH"` (C17); `Q` **479 of 479 over 30 graphs**, `nodes_compared` asserted |
| Transcript — grammar | `S` `mf-transcript-garbage` → `R5_TRANSCRIPT` |
| Transcript — every layer matched | `S` `mf-transcript-missing-layer` → `R5_ORACLE_MISSING`; `Q` `layers_matched` **28** |
| Transcript — the element-count rule | `S` `mf-transcript-headers`, `mf-transcript-novalues`; `Q` `elements_compared` **30,078** and `nodes_expected` **479**, both asserted (C12, C21) |
| Transcript — the real-model excerpt is parsed, not merely present | `S` `mf-transcript-excerpt` asserts `oracle.transcript_callback_lines == 35` over `transcript_lines == 460` before `R5_ORACLE_MISSING`, so an emptied or truncated fixture fails |
| Transcript — `kq-L` `ne0` against `KV_WIDTH` | `S` `mf-transcript-kv-width` → `R5_ORACLE_SHAPE`; `Q` 28 `kq-L` and 28 `kq_soft_max-L` all declaring 256 |
| Transcript — excluded nodes | `S` the two per layer are matched and never element-compared: `nodes_expected` is 1 + 17L + 2 |
| Transcript — a tolerance breach | `S` `mf-transcript-perturbed` → `FAIL`, `worst_layer` 0, `worst_node` `l_out`, `status` `ok` |
| Transcript — an exact pass | `S` max 0 over 546 elements; `Q` **max 0 over 30,078 elements**, max sum diff 1 millionth |
| Logits — file shape | `S` `mf-logits-short` → `R5_LOGITS_SHAPE`, `mf-logits-missing` → `R5_LOGITS_UNREADABLE` |
| Logits — byte-identical at the reconciliation width | `Q` **`IDENTICAL`**, `byte_identical` true, `sha256` `d2e48620ae3e31e2066a6172aa32c19c974d996d232ab91b118335e3d245bf74`, `bit_sum` 425,868,724,161,277. `S` asserts the rule's strictness instead (C9) |
| Logits — the runtime width verdict | `S` `mf-engine-runtime-width` → `WITHIN`; `Q` **`WITHIN`, max 2,739 ten-thousandths, argmax 671 both, top-10 agreement 10** |
| Logits — a real failure is not `WITHIN` | `S` `mf-logits-perturbed`: a blob shifted by 1.0 keeps the argmax and the whole top ten and is `FAIL` |
| Tolerances not silently widened | `S` `1`, `1000`, `10`, and `5000` asserted; `Q` the same four |

### 7.5 Error-code evidence

Twenty-seven codes are reached inside a document by `make layer-forward-smoke`'s model block, and
`R5_ARITY` and `R5_PATH` are reached as the absence of one — **29 of 32**. The three that are not:
`R5_WINDOW_BUDGET` (C11), `R4_WINDOW_UNAVAILABLE`, and `R5_ABI`, each a fail-closed guard over a
condition no input can produce, exactly as `r5a-dense-layer-forward.md` section 4.6 records for the
last two. `R5_GGML_INIT` and `R5_COMPUTE` are additionally reached against the **real** shim in the
qualification.

### 7.6 Measured metrics, from the arm

Section 5.3's table was the probe's. These are `ggml-spike --model-forward`'s own, on the same host,
warm, six-token prefill, `qwen2.5-coder-7b-instruct-q4_k_m.gguf`.

| Metric | Probe (section 5.3) | The shipped arm |
| --- | --- | --- |
| wall, shipped arm, no oracles | 1,071–1,121 ms | **1,141–1,275 ms** |
| `pread`, whole model | 532.9 ms | **515–648 ms** for 4,370,608,032 B in 4,729 groups (`pack.reader_*`; the reference oracle's own re-read of the GGUF is `reference.*` and is not in this figure — correction C18) |
| compute, runtime width | 349.6 ms | **484–620 ms** |
| compute, reconciliation width | 394.1 ms | **668–841 ms** |
| per-layer compute, median | 13.50 ms | **20.6–26.6 ms** |
| layer 27 compute | 4.30 ms | **6.5–7.3 ms** |
| head compute | 9.5–11.2 ms | **10.7–11.9 ms** |
| head `pread` | 63.0 ms | **184–209 ms** |
| reused window | 447,082,496 B | **447,086,592 B** — the sweep at the pack's `block_align` of 4096 (correction C21) |
| activation peak | 2,437,120 B | **2,437,120 B** |
| residual carry | 86,016 B | **86,016 B** |
| peak RSS, shipped arm | 513,638,400 B | **507,969,536 B** |
| peak RSS, self-reference arm | 960,626,688 B | **938,655,744 B** |
| qualification wall, both passes, three oracles | — | **6.4–6.7 s**; the whole target 34.7 s including packing and both instruments |

The arm is slower than the C probe at compute because it runs the reference arm's `ggml_set_output`
marks on seventeen nodes per graph — which the probe only did under `ALIGN_R5B_DUMP` — and because
correction C5's transient copies 4.37 GB that the probe read straight into its window. Both costs
are named rather than absorbed. **The conclusion section 5.3 exists for is unchanged and now
measured by the product: `pread` is comparable to compute at the runtime width and below it at the
reconciliation width, so a six-token prefill of this model on this CPU is within a factor of two of
I/O bound with the whole file in page cache, and a residency policy has half a second per prefill to
compete for.**
