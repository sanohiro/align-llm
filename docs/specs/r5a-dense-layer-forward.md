# R5A-DENSE-LAYER-FORWARD: one Qwen2 dense layer computed from an Align-owned alignpack

Status: design of record for the R5A capability.
Owner document for stage 2 of `docs/specs/roadmap.md` section R5's gate.
Align pin: `.align-revision` = `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`.
Predecessor: [`r4-5-external-buffer.md`](r4-5-external-buffer.md), whose shim, FFI module, pack
reader, alignment contract, and teardown order this capability extends rather than duplicates.
Inputs it consumes verbatim: [`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md) section
2.4's container, [`r1-qwen-model-ir.md`](r1-qwen-model-ir.md) section 2.5.3's `model` object, and
[`r2a-expert-trace.md`](r2a-expert-trace.md) section 2.4's transcript line grammar.

This document triggers the proportional design gate of `CLAUDE.md` on four counts: a new public CLI
arm, a new versioned exchanged document (`R5_LAYER_FORWARD`), a new ownership boundary (a graph
whose topology Align owns as data while ggml owns the activations), and a coordinated invariant
across five modules. Section 3 is the single public-contract ledger, section 4 is the closure
matrix, and section 5 owns fixtures, qualification, metrics, deferrals, risks, and candidate Align
requests.

Section 2 is the probe record and it is first on purpose. Every contract in section 3 was chosen
after the probe. Four of the design's decisions exist **only** because a probe refuted the plan this
document started with: the transcript's node names are not the ones the plan assumed, the reference
instrument's default graph is not the one the plan meant to reproduce, the embedding member must not
be read whole, and the graph cannot be held in Align as a table of handles.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

`docs/specs/roadmap.md` section R5's gate is three stages in order: **単一block、単一layer、最小モデル**
— a single block, a single layer, then a smallest model, each producing correct output. R4.5
discharged stage 1: one `mul_mat` over one Q4_K member of one alignpack block, bit-identical to the
same tensor read into ggml-owned memory.

R5A is **stage 2 and only stage 2**: one prefill of at most six tokens through Qwen2 `blk.L`,
computed by ggml over weights that live in Align-owned buffers, checked against llama.cpp's own
numbers for the same tokens.

The question stage 2 answers is not "can ggml read our bytes" — R4.5 answered that. It is: **when
Align owns the weights, owns the graph topology, and owns the scalars, is the layer's output the
same layer llama.cpp computes?** A runtime that gets one matmul right and the layer wrong is a
runtime that has not been tested, and every later stage — a whole model, a KV cache, a residency
policy — inherits whatever convention error stage 2 fails to catch.

The capability that answers it is **R5A-DENSE-LAYER-FORWARD**: a new arm of the existing
`ggml-spike` executable that reads the embedding rows and the two layer blocks a Qwen2 dense layer
needs out of an alignpack v1 container into Align-owned aligned windows, builds the layer's
thirty-two-node graph from an Align-owned node table, computes it on a real backend, and emits an
`R5_LAYER_FORWARD` document carrying per-node checksums and **two independent oracle verdicts**.

### 1.2 In scope

- One new Align module, `src/layer_qwen2.align`, owning the Qwen2 dense-layer topology as data: the
  node table, the member-role table, the shape rules, and the scalar derivations. It contains no
  `extern` declaration and no `unsafe` block.
- New one-op wrappers in `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c`, and their declarations
  in `src/ggml_ffi.align`, covering `get_rows`, `rms_norm`, `mul`, `add`, `mul_mat`, `reshape_3d`,
  `permute`, `cont_2d`, `rope_ext`, `soft_max_ext`, `swiglu_split`, graph construction, `gallocr`
  reserve/alloc, `ggml_backend_graph_compute`, and `ggml_set_output`.
- A **node-slot store**: a small Align-owned byte window holding the graph's `ggml_tensor *` handles,
  addressed from Align by `i64` index. Section 2.6 is why it exists and section 3.5 is its contract.
- One new CLI arm, `ggml-spike --layer-forward`, and the `R5_LAYER_FORWARD` document at
  `schema_version: 1`.
- Two oracles, both defined in section 3.6: a **bit-exact self-reference** oracle (the same graph over
  the same bytes placed in ggml-allocated memory) and a **tolerance oracle** against a checked-in
  `llama-eval-callback` transcript excerpt.
- One owner test that runs without ggml and without a model, and one named focused qualification that
  runs with both.

### 1.3 Non-goals

- **No loader.** R5A reads what one layer needs, on request, and holds it for one graph. Residency,
  tiering, eviction, cache score, and prefetch remain R5B's, exactly as `r4-5-external-buffer.md`
  section 5.4 defers them.
- **No KV cache.** The attention is computed over the prefill's own six positions. There is no cache
  tensor, no `set_rows`, and no incremental decode. Section 2.3 records the one consequence this has
  for the oracle.
- **No second layer and no model.** `l_out-0` is the last node. Stage 3 — a smallest model end to end
  — is deferred with its evidence in section 5.4.
- **No GPU arm.** `r4-5-external-buffer.md` section 5.4 already established that a Metal arm needs a
  different alignment rule and a different acceptance contract. Adding it here would be two
  capabilities wearing one name. Section 5.4 keeps it deferred and inherits R4.5's measurement.
- **No microbenchmarks A and C.** R5's required benchmark list is `A: transfer + GPU compute`,
  `B: CPU compute`, `C: async prefetch + GPU compute`. R5A measures B and only B, because A and C are
  claims about a loader and a GPU that R5A deliberately does not have. Section 5.3 says so as a
  number, not as prose.
- **No dequantization, no kernel, and no new container version.** R5A reads alignpack v1 as
  `r4-alignpack-layer-major.md` section 2.4 defines it and writes nothing to it.
- **No MoE.** A Qwen2 dense layer has no router and no expert. `r4-alignpack-layer-major.md` section
  4.5's **MOE-PREREQ** is inherited unchanged.
- **No architecture dispatch.** `src/layer_qwen2.align` is the *qwen2* dense layer. A second
  architecture is a second module behind the same node-table shape, and section 5.4 says what would
  have to be true first.

### 1.4 Gate statement

R5's gate is one sentence covering three stages. Each stage is discharged, partly discharged, or
deferred **individually**, with the probe that settles it named. A single "R5 passed" verdict would
hide that two of the three stages are not this capability's.

| Gate stage | Verdict | Evidence |
| --- | --- | --- |
| 単一block — a single block | **Discharged by R4.5.** Not re-litigated here | `r4-5-external-buffer.md` section 1.4 |
| 単一layer — a single layer | **Dischargeable, CPU and dense.** All eighteen oracle nodes of Qwen2 `blk.0` agree with `llama-eval-callback` to the last digit it prints, and the same graph over ggml-owned weights is byte-identical | Section 2.3 (max sampled `\|Δ\|` = 5.0e-5, the print-rounding bound), section 2.4 (20 of 20 node dumps byte-identical) |
| 最小モデル — a smallest model | **Deferred.** R5A stops at `l_out-0` | Section 5.4; a model needs `output_norm`, `output`, and a KV cache, which is stage 3's own consumer boundary |
| required microbenchmark A — transfer + GPU compute | **Deferred.** No GPU arm and no transfer tier exist here | Section 5.4, inheriting `r4-5-external-buffer.md` section 2.5 |
| required microbenchmark B — CPU compute | **Discharged at 13.4 ms typical** for one dense layer, six tokens, warm, by the shipped arm: 12.970, 13.350, 13.379, 15.048 ms over four qualification runs. The probe's own harness measured 15.5 ms median | Section 7.7 (shipped), section 2.5 (probe), section 5.3 |
| required microbenchmark C — async prefetch + GPU compute | **Deferred.** Prefetch is a loader property and the loader is R5B's | Section 5.4 |

The honest summary is: **R5A discharges stage 2 of three on the CPU for a dense layer, and
microbenchmark B.** It leaves stage 3, benchmarks A and C, the Metal arm, and MoE where their own
evidence already puts them.

---

## 2. Probe record

Everything in this section was executed on this host before section 3 was written. Commands are
given exactly as run. Probe sources live outside the work tree and are not part of the capability;
what ships is section 3's design, and section 5.2's qualification is the probe made reproducible.

### 2.1 Host, toolchain, model, and the oracle instrument

| Item | Value |
| --- | --- |
| Host | `MacBookAir10,1`, Apple M1, 16 GiB, macOS 26.5.2, `darwin/arm64` |
| Align compiler | the managed pinned release toolchain at `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` |
| llama.cpp | `0.2.0 (build 10566, commit bb4caa754)`, Homebrew |
| ggml | `0.21.0`, Homebrew, headers in `/opt/homebrew/include`, backends `dlopen`ed from `libexec` |
| Model | `qwen2.5-coder-7b-instruct-q4_k_m.gguf`, 4,683,073,536 bytes |
| Backend selected | `CPU`, through R4.5's registry path; `ggml_backend_buft_get_alignment` = `32` |

The geometry the probe read from the container, and which `r1-qwen-model-ir.md` section 2.5.3
already publishes as a document: `n_embd` 3584, `n_head` 28, `n_head_kv` 4, `head_dim` 128, `n_ff`
18944, `n_vocab` 152064, `context_length` 131072, `rms_eps` 1e-06 (`358637bd`), `rope.type` 2
(NEOX), `rope.freq_base` 1000000.0 (`49742400`), `rope.dim_count` 128, `rope.scaling_type` `null`.

**`context_length` is 131072, not the 32768 the plan assumed.** That value is what llama.cpp passes
as `n_ctx_orig` to `ggml_rope_ext`. It is inert at `ext_factor = 0` — the probe matched with 131072
in place and the value never enters the YaRN correction — but the design passes the container's own
value rather than a constant, and section 3.5 records why the other five RoPE scalars are fixed.

### 2.2 Probe 1 — the transcript, and three facts the plan got wrong

The oracle instrument is `llama-eval-callback`, R2A's instrument, on a six-token prompt:

```text
$ llama-tokenize -m MODEL.gguf -p "def add(a, b):" --ids
[750, 912, 2877, 11, 293, 1648]

$ llama-eval-callback -m MODEL.gguf -p "def add(a, b):" -n 1 -t 4 -ngl 0 \
    -fa off -ctk f32 -ctv f32 -nr -c 512 > transcript.txt 2> log.txt
number of input tokens = 6
  750 912 2877 11 293 1648
```

**Fact 1 — the first node is `embd`, not `inp_embd`.** The plan's node list named `inp_embd`. Build
10566 emits:

```text
common_debug_cb_eval: embd = (f32) GET_ROWS(token_embd.weight{3584, 152064, 1, 1}, inp_tokens{6, 1, 1, 1}}) = {3584, 6, 1, 1}
```

`inp_tokens` is the *leaf* name of `GET_ROWS`'s second source, not a printed node. `r2a-expert-trace.md`
section 6's own recorded transcript line shows `embd` as well, so this is not a build difference —
it is a name the plan invented. Section 3.6's oracle table carries the transcript's names, not the
plan's, and the qualification would have failed on every node had this not been probed.

**Fact 2 — the instrument's default graph is not the graph R5A computes, and four flags fix it.**
The first run, with defaults, produced this attention:

```text
node_24 = (f32) FLASH_ATTN_EXT(Qcur-0 (view) (permuted){128, 6, 28, 1}, cache_k_l0 (view) (permuted){128, 256, 4, 1}}) = {128, 28, 6, 1}
cache_k_l0 (view) = (f16) SET_ROWS(...)
```

Build 10566 defaults to `-fa auto`, which selects flash attention, an f16 KV cache, and — with
`REPACK = 1` in `system_info` — repacked quantized weights. None of those three is what R5A
computes, and comparing against them would have made a correct implementation look wrong. Four flags
produce the explicit graph:

- `-fa off` replaces `FLASH_ATTN_EXT` with `MUL_MAT` / `SOFT_MAX` / `MUL_MAT`, so `kq-0`,
  `kq_soft_max-0`, and `kqv-0` become observable nodes;
- `-ctk f32 -ctv f32` removes the f16 rounding of K and V, which R5A (having no cache) never applies;
- `-nr` disables CPU weight repacking, so the `mul_mat` kernel is the one a plain ggml graph reaches;
- `-ngl 0` and `-c 512` keep everything on the CPU and the cache small.

These four flags are **part of the qualification's contract**, not an invocation detail. Section 5.2
carries them, and section 5.6 records the risk that a future build changes a default again.

**Fact 3 — one node in the layer has no stable name.** The attention output projection prints as
`node_31` under `-fa off` and as `node_26` under flash attention: a positional name that moves when
anything upstream changes. Section 3.6 therefore matches that node by its **source weight name**
(`blk.L.attn_output.weight`) and its op, never by `node_NN`.

The resulting `blk.0` graph, in transcript order, is exactly what section 3.5 builds:

```text
embd          GET_ROWS(token_embd.weight, inp_tokens)       {3584, 6}
norm-0        RMS_NORM(embd)                                {3584, 6}
attn_norm-0   MUL(norm-0, blk.0.attn_norm.weight)           {3584, 6}
Qcur-0        MUL_MAT(blk.0.attn_q.weight, attn_norm-0)     {3584, 6}
Qcur-0        ADD(Qcur-0, blk.0.attn_q.bias)                {3584, 6}
Qcur-0        RESHAPE                                       {128, 28, 6}
Qcur-0        ROPE(Qcur-0, leaf_6)                          {128, 28, 6}
Kcur-0/Vcur-0 the same shape with ne0 = 512, RESHAPE to     {128, 4, 6}
kq-0          MUL_MAT(K permuted, Q permuted)               {n_kv, 6, 28}
kq_soft_max-0 SOFT_MAX(kq-0, attn_inp_kq_mask)              {n_kv, 6, 28}
kqv-0         MUL_MAT(V transposed, kq_soft_max-0)          {128, 6, 28}
kqv_out-0     CONT(kqv-0 permuted)                          {3584, 6}
node_31       MUL_MAT(blk.0.attn_output.weight, kqv_out-0)  {3584, 6}
ffn_inp-0     ADD(node_31, embd)                            {3584, 6}
norm-0        RMS_NORM(ffn_inp-0)                           {3584, 6}
ffn_norm-0    MUL(norm-0, blk.0.ffn_norm.weight)            {3584, 6}
ffn_gate-0    MUL_MAT(blk.0.ffn_gate.weight, ffn_norm-0)    {18944, 6}
ffn_up-0      MUL_MAT(blk.0.ffn_up.weight, ffn_norm-0)      {18944, 6}
ffn_swiglu-0  SWIGLU(ffn_gate-0, ffn_up-0)                  {18944, 6}
ffn_out-0     MUL_MAT(blk.0.ffn_down.weight, ffn_swiglu-0)  {3584, 6}
l_out-0       ADD(ffn_out-0, ffn_inp-0)                     {3584, 6}
```

### 2.3 Probe 2 — the C harness, and the numbers

A C harness built the graph above against ggml directly, reading each weight with `pread` into one
4096-aligned `posix_memalign` block, wrapping that block with
`ggml_backend_dev_buffer_from_host_ptr`, and placing every weight tensor with
`ggml_backend_tensor_alloc` at its interior offset — R4.5's verified path, at layer scale:

```text
$ ./layer MODEL.gguf out 750 912 2877 11 293 1648
BACKEND CPU alignment=32
EXTERNAL all 13 weight tensors point into the caller buffer
GRAPH nodes=32
COMPUTE buffer bytes = 2453376
STATUS 0
```

Every one of the thirteen weight tensors satisfied `ggml_get_data(t) == base + window_offset`
exactly, so the gate clause R4.5 discharged for one member holds for all thirteen. The thirteen
members and their types, read from the container:

```text
token_embd.weight      Q4_K  [3584, 152064]  306,561,024      blk.0.attn_output.weight Q4_K [3584,3584]  7,225,344
blk.0.attn_norm.weight F32   [3584]               14,336      blk.0.ffn_norm.weight    F32  [3584]           14,336
blk.0.attn_q.weight    Q4_K  [3584, 3584]      7,225,344      blk.0.ffn_gate.weight    Q4_K [3584,18944] 38,191,104
blk.0.attn_q.bias      F32   [3584]               14,336      blk.0.ffn_up.weight      Q4_K [3584,18944] 38,191,104
blk.0.attn_k.weight    Q4_K  [3584, 512]       1,032,192      blk.0.ffn_down.weight    Q6_K [18944,3584] 55,695,360
blk.0.attn_k.bias      F32   [512]                  2,048
blk.0.attn_v.weight    Q6_K  [3584, 512]       1,505,280
blk.0.attn_v.bias      F32   [512]                  2,048
```

**Two of the layer's members are Q6_K, not Q4_K**, which is what a `Q4_K_M` quantization means and
which R4.5's single-member spike never exercised. Both flow through `align_ggml_type_ok` unchanged;
the shim's checked-in operand table already carries row `{14, 256, 210}`.

The eight attention members sum to 17,020,928 bytes — **exactly** the `AttentionBlock[0]`
`pack_bytes` that `r4-5-external-buffer.md` section 2.3 recorded from the real pack. The container's
block grouping and the layer's member set are the same set, which is the fact that makes section
3.4's "one block, one `pread`" read shape correct rather than convenient.

The comparison against the transcript, all eighteen oracle nodes, every element the transcript
prints (`3+3` per row, `3+3` rows per plane, `3+3` planes), 1,116 sampled elements:

```text
node              n    max|diff|      sum(transcript)          sum(harness)      |Δsum|
embd             36     0.000046            -5.114609             -5.114611    0.000002
norm-0           36     0.000050          -271.164612           -271.165506    0.000894
attn_norm-0      36     0.000048           -52.504883            -52.504921    0.000038
Qcur-0/ADD       36     0.000048          2795.549805           2795.548289    0.001516
Kcur-0/ADD       36     0.000050          4637.266113           4637.268211    0.002098
Vcur-0/ADD       36     0.000050            13.900066             13.900069    0.000003
Qcur-0/ROPE     216     0.000050          2509.360596           2509.371040    0.010444
Kcur-0/ROPE     144     0.000050          4682.393555           4682.385463    0.008092
kqv-0           216     0.000050           -41.610428            -41.610234    0.000194
kqv_out-0        36     0.000049           -41.610420            -41.610234    0.000186
attn_out-0       36     0.000050            11.342892             11.342875    0.000017
ffn_inp-0        36     0.000048             6.228231              6.228263    0.000032
ffn_norm-0       36     0.000050            25.956188             25.956381    0.000193
ffn_gate-0       36     0.000047        -64545.382812         -64545.598306    0.215494
ffn_up-0         36     0.000048           396.480713            396.478587    0.002126
ffn_swiglu-0     36     0.000049            20.250044             20.250256    0.000212
ffn_out-0        36     0.000049             2.572831              2.572810    0.000021
l_out-0          36     0.000045             8.800983              8.801071    0.000088
WORST max abs diff over all sampled elements = 0.000050
```

**`5.0e-5` is not a tolerance the harness happened to achieve — it is the largest value the
comparison can produce when every element agrees.** `llama-eval-callback` prints with `%12.4f`, so a
printed value carries an inherent ±5.0e-5. Every one of the 1,116 sampled elements agreed with the
harness to the last digit printed. The layer is not "close"; within what the instrument publishes,
it is exact. Section 3.6 fixes the shipped threshold from this measurement, before the qualification
exists.

**The `sum` column needed its own investigation, and the answer changed the contract.** The `|Δsum|`
above compares the transcript's printed sum against a double-precision accumulation, and the worst
relative disagreement is 3.3e-6 (`ffn_gate-0`, 0.215 of 64,545). Re-accumulating the harness output
in **sequential f32 order** instead:

```text
node          f32 sequential      transcript        |Δ|
norm-0          -271.164612     -271.164612     0.000000   (bit-identical)
Qcur-0/ROPE     2509.360596     2509.360596     0.000000   (bit-identical)
kq-0         3321309.750000  3321309.750000     0.000000   (bit-identical)
l_out-0            8.800970        8.800983     0.000013
ffn_gate-0    -64545.386719   -64545.382812     0.003907
```

The instrument accumulates its `sum` in f32, in element order. Three of five checked nodes become
**bit-identical** once the accumulation matches; the worst residual is 1.5e-6 relative. Section 3.6
therefore specifies sequential f32 accumulation as part of the oracle rather than leaving the
accumulation order to the implementation, and sets a *relative* sum tolerance.

**Two nodes are excluded from the oracle and the reason is structural, not numerical.** `kq-0` and
`kq_soft_max-0` have shape `{n_kv, n_tokens, n_head}`, and llama.cpp's `n_kv` is the padded KV-cache
width — 256 in this run — while R5A, having no cache, computes `{6, 6, 28}`. The tensors are not the
same shape, so element comparison is undefined. The probe observed their *sums* agreeing anyway
(`kq-0` bit-identical), because llama.cpp zero-initializes the cache and the mask drives the padded
softmax weights to zero; that is an implementation detail of the instrument and the design does not
depend on it. `kqv-0`, the first node downstream of the padding, is in the oracle and agrees.

### 2.4 Probe 3 — the bit-exact self-reference oracle, and determinism

The same harness, with one change: the thirteen weight tensors are created in a second context and
allocated by `ggml_backend_alloc_ctx_tensors`, then filled with `ggml_backend_tensor_set` from the
same host bytes. `ggml_get_data(t)` was asserted **not** to equal the host pointer, so the arm is
genuinely ggml-owned:

```text
$ ALIGN_R5A_REF=1 ./layer MODEL.gguf ref 750 912 2877 11 293 1648
REFERENCE arm: 13 weight tensors in a ggml-allocated buffer
$ for f in out/*.bin; do cmp -s "$f" "ref/$(basename $f)" || echo DIFF; done
(no output — 20 of 20 node dumps byte-identical)
```

All twenty dumped tensors — every oracle node plus `kq-0` and `kq_soft_max-0` — are byte-identical
between the Align-owned-buffer arm and the ggml-owned arm. Two consecutive runs of the external arm
were also byte-identical, so the output is deterministic on this host at this thread count.

This is the oracle that proves **bytes**: it holds regardless of ggml version, kernel choice, or
llama.cpp build, because both arms run the same kernels over the same bits. The transcript oracle
proves **topology**: it is the only thing that can catch a wrong RoPE mode, a missing bias, a
transposed V, or an attention scale of `1/sqrt(3584)`. Neither substitutes for the other, and
section 3.6 ships both.

### 2.5 Probe 4 — the embedding member must not be read whole

The plan read `token_embd.weight` in full. That is 306,561,024 bytes — **67% of everything the layer
reads** — to use six rows of 2,016 bytes. A one-layer executable whose dominant cost is 306 MiB it
does not use would make every timing in this document meaningless and would misrepresent exactly the
residency question R5 exists to answer.

The probe therefore read only the six needed rows, `pread`ing each at
`member.source_offset + id * row_bytes` into its own aligned slot and remapping the ids to `0..T-1`:

```text
$ ALIGN_R5A_ROWS=1 ./layer MODEL.gguf rows 750 912 2877 11 293 1648
W token_embd.weight  type=12  ne=[3584,6]  nbytes=12096
TOTAL window bytes = 149139456
$ for f in out/*.bin; do cmp -s "$f" "rows/$(basename $f)" || echo DIFF; done
(no output — 20 of 20 node dumps byte-identical to the whole-member arm)
```

| | whole member | row-gathered |
| --- | --- | --- |
| weight window | 455,688,192 B | **149,139,456 B** |
| `pread` wall time, warm | 87.0 ms | **19.5–20.9 ms** |
| compute wall time | 28.5–40.6 ms | **15.3–16.6 ms** |
| output | — | **byte-identical** |

Row extraction is valid for every ggml quantization, and the argument is the format's own: a tensor
is only constructible when `ne0 % blck_size == 0`, so a row is always a whole number of blocks and
`row_bytes = nbytes / ne1` divides exactly. It is validated in section 3.8 step 12 rather than
assumed. Row *alignment*, however, is not free — Q4_K rows are 2,016 bytes (32-aligned by luck) but
Q6_K rows of this width are 2,940 bytes and are not — which is why the design copies each row into
its own `block_align`-padded slot instead of pointing ggml at an interior row offset.

Five consecutive row-gathered runs:

```text
compute_ms = 16.588  15.489  15.529  15.323  15.440     (median 15.5)
read_ms    = 20.358  20.937  20.418  19.604  19.490
open_ms    = 29.133  29.332  29.092  29.169  29.048     (GGUF metadata; the pack path replaces this)
COMPUTE buffer bytes = 2,453,376   GRAPH nodes = 32
```

### 2.6 Probe 5 — what the Align FFI surface allows, verified at the pin

Five questions, each answered by compiling the case with the pinned compiler.

**`f32` crosses the FFI, in both directions, and float literals coerce.** The plan's largest open
risk was `ggml_rope_ext`'s six `float` parameters. A nine-argument probe matching its shape:

```text
$ alignc run f32probe.align
1                 # C saw 1000000.0, 1.0, 0.0, 1.0, 32.0, 1.0 exactly, alongside three i32
3.75              # probe_f64(1.5, 2.25f) — mixed f64/f32 arguments
7.0               # probe_ret_f32(3.5f) — an f32 return value
C got n_dims=128 mode=2 n_ctx_orig=131072 fb=1000000.0 fs=1.000 ef=0.000 af=1.000 bf=32.0 bs=1.0
```

A separate probe confirmed `probe_ret_f32(3.5)` — an unsuffixed literal in an `f32` parameter
position — also yields `7.0`, so no cast is required at a call site. **The design nonetheless passes
no float across the boundary**, and section 3.5 gives the reason: `r1-qwen-model-ir.md` section
2.5.3 publishes `rms_eps_bits` and `freq_base_bits` as authoritative IEEE-754 hex precisely because
a rendered float is not authoritative, and reinterpreting the bit pattern in C makes the scalar ggml
receives byte-identical to the one the GGUF stores. The capability records `f32` as *available and
deliberately unused*, with this probe as the evidence that the choice is a choice.

**`bool` is still refused, so `ggml_gallocr_reserve` and `ggml_gallocr_alloc_graph` must be wrapped.**

```text
boolprobe.align:3:28: error: 'bool' is not an FFI-safe return type for an extern
                             (use an integer, float, `raw`, a `layout(C)` struct, or `()`)
```

**`raw` cannot be aggregated, and this is the fact that shaped the design.** A thirty-two-node graph
needs its handles somewhere:

```text
rawagg.align:7:10:  error: struct field type is not supported here, got raw
rawagg.align:11:13: error: array element must be a scalar (composite payloads are not supported yet), got raw
```

So Align can hold `raw` only in named locals. Three designs were considered and section 3.5 records
why the third wins: thirty-five named locals (works, but the topology stops being data and every
node becomes a hand-written line); a single C entry point that builds the whole layer (rejected —
`docs/specs/align-llm.md` assigns execution scheduling to Align, and moving the topology into C
would make the capability prove the opposite of what it claims); or a **node-slot store**, a
`buffer` of 8-byte slots that Align owns and the shim writes handles into, with every node addressed
by an `i64` index. The third keeps `raw` out of every aggregate, keeps the graph as Align-owned
scalar data that a loop can walk, introduces no process-global state, and gives slot exhaustion a
named error code. Section 5.5 records it as new client evidence for Request 34.

**`json.doc` parses the geometry, including floats, and `sqrt` is a method.**

```text
$ alignc run jsonprobe.align       # import core.json, import core.math
1000000.0                          # d.get("rope").get("freq_base").as_f64() -> Option<f64>
0.000001                           # d.get("eps").as_f64()
28                                 # d.get("n_head").as_i64()
11.313708498984761                 # (128.0).sqrt()   — f64
11.313708                          # (128.0 as f32).sqrt()  — f32
```

`core.math`'s float functions are **methods on the scalar**, not free functions: `math.sqrt(x)` and
`sqrt(x)` both fail to resolve, `x.sqrt()` compiles. That is how section 3.5 derives the attention
scale `1/sqrt(head_dim)` in Align rather than in C.

### 2.7 What the probes settle

1. The layer is reproducible. Eighteen nodes, 1,116 sampled elements, zero disagreement beyond the
   instrument's print precision, from Align-owned bytes.
2. Both oracles are real and independent. The bit-exact one passed 20 of 20 tensors; the tolerance
   one passed at 5.0e-5 with a print-rounding bound of 5.0e-5.
3. The instrument must be pinned by flags, not by name. Three of its defaults compute a different
   graph.
4. Two node names in the transcript are not what the plan called them, and one has no stable name at
   all.
5. The embedding must be row-gathered. The whole-member read is 3.1x the bytes and 4.5x the read
   time for a byte-identical answer.
6. The graph cannot be an Align array of handles. The slot store is not a convenience; it is the only
   shape at this pin that keeps the topology in Align.

---

## 3. Public-contract ledger

### 3.1 The executable, and why this is an arm rather than a new binary

R5A ships as **`ggml-spike --layer-forward`**, not as a new `align-runtime` executable. Four reasons,
in decreasing weight:

1. **One link boundary.** `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c` are the repository's
   only C build inputs, and `scripts/build-ggml-shim` selects between them on `ALIGN_LLM_GGML_INCLUDE`.
   A second executable means a second link rule, a second stub/real matrix, and a second way for the
   hosted owner test to pass against a contract the qualification does not run. That failure mode is
   exactly what `r4-5-external-buffer.md` section 5.1's byte-identity assertion between the two C
   files exists to prevent, and doubling the surface halves its value.
2. **The prologue is already discharged.** Device open, backend init, the `TENSOR_ALIGNMENT` probe,
   the operand-table drift guard, the alignment pre-checks, the teardown order, and the lifetime
   counters are `r4-5-external-buffer.md` sections 3.8–3.9 and their closure matrix cells are closed.
   R5A adds nodes to a graph; it does not add a second answer to "who owns the backend".
3. **`align-runtime` should be claimed by the runtime.** `docs/specs/roadmap.md` names `align-runtime`
   as the product that does local inference across GPU memory, system memory, and NVMe. An executable
   with no loader, no residency, no cache slot, and one layer is not that, and taking the name early
   would make the roadmap's own gate unreadable.
4. **The CLI already addresses a block by index.** R4.5's arm proves the selection surface works.

**What this costs, stated rather than hidden.** `ggml-spike`'s name outgrows its content the moment
this arm lands: a "spike" that computes a transformer layer is misnamed. The design accepts that for
R5A and fixes it at the R5B boundary, where the loader arrives and the executable becomes
`align-runtime` with `ggml-spike` retained as a deprecated alias for exactly one release. Section 5.4
carries that as a named deferral rather than leaving it to be discovered.

### 3.2 Hyperparameters, and where they come from

The alignpack v1 container carries **no hyperparameters**. `r4-alignpack-layer-major.md` section
2.4.2's header holds geometry of the *container*; section 2.4.4's member records hold names, roles,
types, dims, and offsets. There is no `rope.freq_base`, no `rms_eps`, and no `n_head_kv` anywhere in
the file, and R5A does not add one — `r4-5-external-buffer.md` section 1.3's "no new container
version" is inherited.

R5A therefore takes one additional input: an **`R1_QWEN_MODEL_IR` document at `schema_version: 1`**,
of which it reads only the `model` object of `r1-qwen-model-ir.md` section 2.5.3. That document
already publishes every scalar the layer needs, already validates every one of them at its own
source, and already carries `rms_eps_bits` and `rope.freq_base_bits` as authoritative IEEE-754 hex.

| Consumed field | Use |
| --- | --- |
| `arch` | must be exactly `"qwen2"`; anything else is `R5_GEOMETRY` |
| `n_layer` | bounds the `LAYER` operand |
| `n_embd`, `n_head`, `n_head_kv`, `head_dim`, `n_ff`, `n_vocab` | every tensor shape and every reshape |
| `context_length` | passed to `ggml_rope_ext` as `n_ctx_orig` |
| `rms_eps_bits` | the `eps` of both `RMS_NORM` nodes, as a bit pattern |
| `rope.type` | must be `2`; `R5_GEOMETRY` otherwise |
| `rope.dim_count` | `n_dims` of both `ROPE` nodes; must equal `head_dim` |
| `rope.freq_base_bits` | `freq_base`, as a bit pattern |
| `rope.scaling_type` | must be `null`; section 3.5 explains what that fact buys |
| `n_expert` | must be `0` |

Deliberately **not** consumed: `rms_eps`, `rope.freq_base`, `rope.type_name`, `type_source`,
`dim_count_source`, and everything outside `model`. A rendered float is a rendering; the `_bits`
field is the value.

This makes R5A a **pure alignpack v1 reader plus one JSON document**, and it makes the synthetic
fixture of section 5.1 a nine-line file rather than a synthetic GGUF. Section 5.4 records "geometry
in the container" as an alignpack v2 item owned by R5B, where a loader that opens one file and needs
nothing else is a real requirement rather than an aesthetic one.

### 3.3 CLI surface

```text
ggml-spike PACK.alignpack BLOCK MEMBER [DOC.json [REF.gguf]]          # the R4.5 arms, unchanged
ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS
ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS DOC.json
ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS DOC.json REF.gguf
ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt
ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS -         REF.gguf TRANSCRIPT.txt
```

**Arm selection is the first operand and nothing else.** A first operand equal to `--layer-forward`
selects this arm; a first operand beginning with `--` and not equal to it is `R5_ARITY`; any other
first operand is R4.5's arm with R4.5's arity rules unchanged. Arm selection happens before any path
work, so a wrong arm produces no output and no file.

Exactly five, six, seven, or eight operands. `MAX_PATH_BYTES` — non-empty, `<= 4096` bytes, no NUL —
applies to `PACK`, `GEOM`, `DOC`, `REF`, and `TRANSCRIPT` before anything is opened, reusing
`src/main.align:624`'s rule. `-` in the sixth position means "document to stdout" and is R0's
convention; it exists so the reference and transcript arms are reachable without naming a document
path.

`LAYER` is a non-negative decimal integer in `[0, n_layer)`, no sign, no leading `+`, no whitespace.

`TOKENS` is a comma-separated list of **1 to 6** non-negative decimal integers, no spaces, no
trailing comma, each in `[0, n_vocab)`. Anything else is `R5_TOKENS`.

**`MAX_PREFILL_TOKENS` is 6, and the bound is the oracle's, not the arithmetic's.**
`llama-eval-callback` prints every row of a tensor only while `ne1 <= 6`; at seven tokens it elides
the middle and the tolerance oracle would silently compare fewer elements while still reporting
`PASS`. An oracle that gets weaker as the input grows is worse than one that refuses, so the CLI
refuses. Section 5.4 records lifting the cap as R5B work, where a KV cache makes longer prefills
meaningful and the oracle needs a different instrument anyway.

The summary block, in this exact order, printed exactly when a real document path is given
(section 6, correction C11). **Each label and its value are printed on their own line** — R4.5's
shape, inherited verbatim, because `print` writes one line and the arm adds no column formatting of
its own. Section 6, correction C23 records that this document originally drew it as an aligned
two-column table it never was:

```text
layer forward:
status:
OK | ERROR
verdict:
EXTERNAL | COPIED | UNAVAILABLE
pack path:
<sanitized path>
schema:
1
arch:
qwen2
layer:
<integer>
tokens:
<comma-separated ids>
weight bytes:
<integer>                     # the Align-owned window, all members
activation bytes:
<integer>                     # the ggml-owned gallocr buffer
graph nodes:
<integer>
backend:
<name>
pread ns:
<integer>
build ns:
<integer>
compute ns:
<integer>                     # warm mean
l_out sha256:
<64 hex characters>
l_out bit sum:
<integer>
reference:
IDENTICAL | MISMATCH | -
reference nodes:
<matched>/<total>, or -
transcript:
PASS | FAIL | -
transcript nodes:
<matched>/<total>, or -
max abs diff:
<integer>                     # ten-thousandths; see section 3.6
max sum diff:
<integer>                     # millionths
released:
<integer>
error:
<code>                        # only when status is ERROR
detail:
<identifier>                  # only when status is ERROR
```

The block is read positionally, by line ordinal rather than by splitting on a colon, which is what
makes a sanitized path containing a colon unambiguous.

`verdict` retains R4.5's meaning and is `EXTERNAL` only when **every** weight tensor's data pointer
lies at its own window offset. Exit is R0's mapping, reused verbatim. Both output forms emit
byte-identical document bytes.

**`COPIED` and `FAIL` are successful runs.** A future ggml that copies the bytes, or a transcript
that disagrees, must be *reported* rather than crashed on. `status: "error"` is reserved for the
codes of section 3.8; an oracle verdict is data.

### 3.4 The read shape

Three container reads, in this order, into one Align-owned `buffer`:

1. **The embedding rows.** The embedding `WeightBlock`'s `token_embd` member gives `nbytes`, `ne1`
   (`= n_vocab`), and `pack_offset`. `row_bytes = nbytes / n_vocab`, required to divide exactly and
   to be a positive multiple of the type's `type_size`. One `pread` of `row_bytes` per token, at
   `member.pack_offset + id * row_bytes`, into a `block_align`-padded slot. The ids handed to
   `GET_ROWS` become `0..T-1`. Section 2.5 is the measurement that made this the shape.
2. **The layer's `AttentionBlock`.** One `pread` of `block.pack_bytes` at `block.pack_offset` — R4.5's
   read shape, unchanged, and the reason `r4-alignpack-layer-major.md`'s layer-major grouping exists.
   Eight members at interior offsets.
3. **The layer's `MlpBlock`.** The same, four members.

Blocks are located by `(kind, layer)` from the block table — `kind` `0` Weight with `layer == -1` for
the embedding, `1` Attention and `2` Mlp with `layer == LAYER` — never by a hard-coded index.
Members are located by `role_id` against `r4-alignpack-layer-major.md` section 2.4.4's frozen role
list, never by name string and never by position. A block or role that is absent is
`R5_BLOCK_MISSING` or `R5_MEMBER_MISSING`, naming what was missing.

Each member is copied to a `block_align`-aligned window offset rather than used at its interior
offset in the block read. This costs one memcpy per member and buys the property section 3.9 needs:
every pointer handed to ggml is `MAX_TENSOR_ALIGNMENT`-aligned by construction, so the abort
`r4-5-external-buffer.md` section 2.4 measured stays unreachable for thirteen tensors rather than
being re-argued for each.

### 3.5 The graph as Align-owned data — `src/layer_qwen2.align` and the slot store

**The node table is the design.** `src/layer_qwen2.align` holds the layer as scalar columns, in the
`GgufTable` / `BlockPlan` / `PackPlan` / `PackIndex` shape this repository has used five times:

```text
pub NODE_COUNT := 32
node_id[]        i64   the R5A-owned stable node identity (section 3.7's `nodes[].id`)
node_op[]        i64   one of OP_GET_ROWS, OP_RMS_NORM, OP_MUL, OP_ADD, OP_MUL_MAT,
                       OP_RESHAPE_3D, OP_PERMUTE, OP_CONT_2D, OP_ROPE, OP_SOFT_MAX, OP_SWIGLU
node_a[]         i64   slot index of the first source
node_b[]         i64   slot index of the second source, or -1
node_out[]       i64   slot index the result is written to
node_p0..p3[]    i64   op-specific integer parameters (reshape extents, permutation, n_dims)
node_oracle[]    i64   index into the oracle table, or -1
```

A single loop walks it and issues one shim call per row. Adding a node is a row; the topology is
data a test can assert on, not control flow. The member-role table and the expected-shape table are
the same shape and are validated against the container before any ggml object exists.

**The slot store is how the handles get out of the way.** Section 2.6 established that `raw` cannot
be a struct field or an array element at this pin, so the graph's thirty-two `ggml_tensor *` values
cannot live in Align. They live in an **Align-owned byte window** that the shim writes into:

```text
capacity          MAX_NODE_SLOTS := 128        (32 nodes + 13 weights + 3 inputs = 48 used)
window bytes      16 + 8 * capacity            (a 16-byte header, then 8-byte slots)
header            u64 magic "ALGNSLOT" | u64 capacity
slot value        a ggml_tensor *, or NULL for empty
base alignment    validated `% 8 == 0` before the first write
```

Every op wrapper takes the slot window as `slice<u8>`, an output index, and source indices; it
validates the magic, the capacity, and each index against the window's own declared capacity, and it
refuses a read of an empty slot. Align holds exactly four `raw` locals for the whole arm — device,
backend, context, graph, plus the `gallocr` — and never aggregates one. Slot misuse is
`R5_SLOT`, a fail-closed code the fixtures reach by asking for an out-of-range index.

**Scalar ownership.** Align computes and owns every scalar; the shim reinterprets, it does not
decide.

| Scalar | Owner | Crosses as |
| --- | --- | --- |
| `eps` of both `RMS_NORM` nodes | the geometry document's `rms_eps_bits` | `i32` bit pattern |
| `freq_base` of both `ROPE` nodes | the geometry document's `rope.freq_base_bits` | `i32` bit pattern |
| `n_dims`, `mode`, `n_ctx_orig` | `rope.dim_count`, `rope.type`, `context_length` | `i32` |
| attention `scale` | Align, `1.0 / (head_dim as f32).sqrt()` | `i32` bit pattern |
| `max_bias` | fixed `0.0` | `i32` bit pattern |
| the causal mask | Align, an f32 `{T, T}` image written with `put_u32_le` | bytes |

The mask is built from bit patterns rather than float arithmetic: `0x00000000` where `col <= row`
and `0xFF800000` (`-inf`) elsewhere. No float parsing, no float formatting, and no dependence on
Align's rendering of infinity.

**Five of `ggml_rope_ext`'s scalars are fixed, and section 3.8 step 9 earns the right to fix them.**
`freq_scale = 1.0`, `ext_factor = 0.0`, `attn_factor = 1.0`, `beta_fast = 32.0`, `beta_slow = 1.0`
are the values llama.cpp uses when a model declares no RoPE scaling. R5A validates
`rope.scaling_type == null` and refuses with `R5_GEOMETRY` otherwise, so the constants are a checked
precondition rather than a hidden assumption. A model with YaRN scaling is out of scope and says so.

**New shim symbols.** One C translation unit, one library, no ggml type in any signature, `0` is
success and negative values map to section 3.8's codes — R4.5's four rules unchanged.

| Symbol | Signature | Contract |
| --- | --- | --- |
| `align_ggml_slots_init` | `int32_t (void *slots, int64_t bytes)` | Writes the header, zeroes the slots, validates 8-alignment and capacity |
| `align_ggml_slot_nbytes` / `_ne` / `_data_offset` | `int64_t (void *slots, int64_t i, ...)` | `ggml_nbytes` / `ne[d]` / pointer delta for slot `i` |
| `align_ggml_slot_new_tensor_1d` / `_2d` | `int32_t (void *ctx, void *slots, int64_t out, int32_t type, int64_t ne0[, int64_t ne1])` | Creates and stores; type validated against the operand table first |
| `align_ggml_slot_place` | `int32_t (void *buffer, void *slots, int64_t i, void *addr)` | R4.5's `tensor_place`, alignment- and bounds-checked, on a slot |
| `align_ggml_slot_set` / `_get` | `int32_t (void *slots, int64_t i, void *bytes, int64_t off, int64_t n)` | R4.5's bounds-checked copies, on a slot |
| `align_ggml_slot_mark_output` | `int32_t (void *slots, int64_t i)` | `ggml_set_output`. **Mandatory for every oracle node**: without it `ggml_gallocr` reuses an intermediate's memory and the node read back is not the node computed |
| `align_ggml_op_get_rows` | `int32_t (void *ctx, void *slots, int64_t out, int64_t a, int64_t b)` | |
| `align_ggml_op_rms_norm` | `... int64_t out, int64_t a, int32_t eps_bits` | `memcpy` of the bit pattern to a `float`, then `ggml_rms_norm` |
| `align_ggml_op_mul` / `_add` / `_mul_mat` | `... int64_t out, int64_t a, int64_t b` | |
| `align_ggml_op_reshape_3d` | `... int64_t out, int64_t a, int64_t ne0, ne1, ne2` | |
| `align_ggml_op_permute` | `... int64_t out, int64_t a, int32_t p0, p1, p2, p3` | |
| `align_ggml_op_cont_2d` | `... int64_t out, int64_t a, int64_t ne0, ne1` | |
| `align_ggml_op_rope_neox` | `... int64_t out, int64_t a, int64_t pos, int32_t n_dims, mode, n_ctx_orig, freq_base_bits` | The five fixed scalars are compiled in; `mode` is validated `== 2` |
| `align_ggml_op_soft_max_ext` | `... int64_t out, int64_t a, int64_t mask, int32_t scale_bits, max_bias_bits` | |
| `align_ggml_op_swiglu_split` | `... int64_t out, int64_t gate, int64_t up` | `ggml_swiglu_split`, the op the instrument emits as `SWIGLU` |
| `align_ggml_graph_context_bytes` | `int64_t (int64_t node_capacity)` | `ggml_tensor_overhead() * capacity + ggml_graph_overhead()`, so Align never guesses a context size |
| `align_ggml_graph_new` | `void * (void *ctx)` | `ggml_new_graph` |
| `align_ggml_graph_expand` | `int32_t (void *graph, void *slots, int64_t i)` | `ggml_build_forward_expand` |
| `align_ggml_graph_node_count` | `int32_t (void *graph)` | |
| `align_ggml_gallocr_new` | `void * (void *backend)` | `ggml_gallocr_new(ggml_backend_get_default_buffer_type(b))` |
| `align_ggml_gallocr_reserve` / `_alloc` | `int32_t (void *galloc, void *graph)` | The `bool` translation section 2.6 requires |
| `align_ggml_gallocr_bytes` | `int64_t (void *galloc)` | `ggml_gallocr_get_buffer_size(g, 0)` |
| `align_ggml_gallocr_free` | `void (void *galloc)` | |
| `align_ggml_graph_compute` | `int32_t (void *backend, void *graph)` | Returns the `ggml_status` verbatim |

`align_ggml_compute` (R4.5's single-tensor form) is retained unchanged for R4.5's arm.

### 3.6 The two oracles, and the tolerance fixed before the qualification

**Oracle 1 — bit-exact self-reference.** Present in the seven- and eight-operand forms. The same
thirty-two-node graph is built a second time in a second context, with the thirteen weight tensors
allocated by `ggml_backend_alloc_ctx_tensors` and filled from the same Align window with
`ggml_backend_tensor_set`, so ggml owns them. Every oracle node's bytes must be **byte-identical**
between the two arms. Section 2.4 measured 20 of 20.

Before the graph runs, the pack bytes of every member are compared byte-for-byte against the source
GGUF at `member.source_offset`; a difference is `R5_SOURCE_DIVERGED` and stops the arm, so a
divergence is reported as what it is rather than as a mismatched output.

This oracle proves **bytes**. It is version-independent and kernel-independent, and it is the one
that would catch a wrong interior offset, a truncated read, or a stale window.

**Oracle 2 — the transcript, with a fixed tolerance.** Present in the eight-operand form. The
transcript is scanned with `r2a-expert-trace.md` section 2.4's line grammar, reusing
`src/expert_trace.align`'s scanner. Eighteen nodes are matched:

| `nodes[].id` | transcript name | transcript op | shape |
| --- | --- | --- | --- |
| `embd` | `embd` | `GET_ROWS` | `{n_embd, T}` |
| `norm` | `norm-L` (first occurrence) | `RMS_NORM` | `{n_embd, T}` |
| `attn_norm` | `attn_norm-L` | `MUL` | `{n_embd, T}` |
| `q_bias` | `Qcur-L` | `ADD` | `{n_head*head_dim, T}` |
| `k_bias` | `Kcur-L` | `ADD` | `{n_head_kv*head_dim, T}` |
| `v_bias` | `Vcur-L` | `ADD` | `{n_head_kv*head_dim, T}` |
| `q_rope` | `Qcur-L` | `ROPE` | `{head_dim, n_head, T}` |
| `k_rope` | `Kcur-L` | `ROPE` | `{head_dim, n_head_kv, T}` |
| `kqv` | `kqv-L` | `MUL_MAT` | `{head_dim, T, n_head}` |
| `kqv_out` | `kqv_out-L` | `CONT` | `{n_embd, T}` |
| `attn_out` | **matched by source weight** `blk.L.attn_output.weight` | `MUL_MAT` | `{n_embd, T}` |
| `ffn_inp` | `ffn_inp-L` | `ADD` | `{n_embd, T}` |
| `ffn_norm` | `ffn_norm-L` | `MUL` | `{n_embd, T}` |
| `ffn_gate` | `ffn_gate-L` | `MUL_MAT` | `{n_ff, T}` |
| `ffn_up` | `ffn_up-L` | `MUL_MAT` | `{n_ff, T}` |
| `ffn_swiglu` | `ffn_swiglu-L` | `SWIGLU` | `{n_ff, T}` |
| `ffn_out` | `ffn_out-L` | `MUL_MAT` | `{n_embd, T}` |
| `l_out` | `l_out-L` | `ADD` | `{n_embd, T}` |

`kq-L` and `kq_soft_max-L` are **excluded by contract**, for section 2.3's structural reason: the
instrument's `n_kv` is a padded cache width and R5A has no cache, so the tensors are different
shapes. The exclusion is a document field (`nodes[].oracle: "shape_incomparable"`), not a silent gap.

A node matches when the transcript's declared shape equals the node's computed shape; a shape
disagreement is `R5_ORACLE_SHAPE`, never a tolerance failure. A named node absent from the
transcript is `R5_ORACLE_MISSING`. Both are error codes, because an oracle that silently compares
nothing is the failure mode this design most needs to avoid.

**The thresholds, fixed here, before any qualification exists.**

| Comparison | Threshold | Justification |
| --- | --- | --- |
| element | `\|Δ\| <= 1.0e-4`, evaluated as `\|round(x * 10^4) - printed_ten_thousandths\| <= 1` | `%12.4f` rounds to ten-thousandths, so a printed value carries an inherent ±5.0e-5. Section 2.3 measured max `\|Δ\|` = **5.0e-5** over 1,116 elements and 18 nodes: every element agreed to the last digit printed. The threshold is 2× the print bound and 2× the measured worst case |
| sum | `\|Δ\| <= max(1.0e-3, 1.0e-5 × \|Σ\|)`, evaluated in millionths as `i64` | The sum is compared against a **sequential f32 accumulation in element order**, which section 2.3 showed makes three of five checked nodes bit-identical. The worst **relative** residual measured was **1.5e-6** (`l_out-0`, 1.3e-5 absolute); the worst **absolute** residual measured was **3.9e-3** (`ffn_gate-0`, whose sum is -64,545, so 6.1e-8 relative). They are different nodes, and that is precisely why the rule is relative with a floor rather than absolute: the threshold is ~7× the measured worst relative case |

**Both comparisons are integer comparisons and neither renders a float.**
`r4-alignpack-layer-major.md` section 2.3 records that this repository has no float formatting
contract, so the transcript's `-0.0190` is parsed to the integer `-190` and the computed f32 is
converted with `(x * 10000.0).round() as i64`. The sum is parsed to millionths the same way. No
float is ever printed by R5A and none needs to be.

The document reports `oracle.max_abs_diff_ten_thousandths` and `oracle.max_sum_diff_millionths` as
integers whether the verdict is `PASS` or `FAIL`, so a regression is a number that moved rather than
a boolean that flipped.

### 3.7 `R5_LAYER_FORWARD`, `schema_version: 1`

Canonical UTF-8 JSON in declaration order, in the R0/R1/R2A/R4/R4.5 shape.

```text
schema_version    1
kind              "R5_LAYER_FORWARD"
pack_path         string
geometry_path     string
reference_path    string, "" when the reference arm did not run
transcript_path   string, "" when the transcript arm did not run
status            "ok" | "error"
error_code        string, "" when ok
error_detail      string, "" when ok
verdict           "EXTERNAL" | "COPIED" | "UNAVAILABLE"

pack        format_version, block_align, member_align, block_count, member_count,
            total_bytes, payload_offset
model       arch, n_layer, n_embd, n_head, n_head_kv, head_dim, n_ff, n_vocab,
            context_length, rms_eps_bits, rope_type, rope_dim_count, rope_freq_base_bits,
            attn_scale_bits
selection   layer, embedding_block_index, attention_block_index, mlp_block_index,
            token_count, tokens[]
members[]   role, role_id, name, ggml_type, ne0, ne1, nbytes, blck_size, type_size,
            pack_offset, window_offset, window_alignment, tensor_data_offset,
            pointer_identity (bool), read_bytes, pread_count
graph       node_count, slot_capacity, slot_high_water, weight_bytes, activation_bytes,
            context_bytes, backend_name, compute_status
nodes[]     id, op, transcript_name, transcript_op, ne0, ne1, ne2, ne3, element_count,
            sha256 (64 hex), bit_sum, f32_sum_millionths, nonfinite_count,
            oracle ("compared" | "shape_incomparable" | "absent")
output      sha256 (64 hex), bit_sum, element_count, nonfinite_count      # l_out
reference   present (bool), verdict, nodes_compared, nodes_identical,
            first_difference_node, first_difference_index,
            first_difference_primary_bits, first_difference_reference_bits
oracle      present (bool), verdict, instrument, nodes_expected, nodes_matched,
            elements_compared, max_abs_diff_ten_thousandths, max_sum_diff_millionths,
            tolerance_ten_thousandths, sum_tolerance_millionths, sum_tolerance_relative_ppm,
            worst_node, worst_element_index
timings     pread_ns, build_ns, reserve_ns, compute_ns, reference_compute_ns,
            oracle_ns, elapsed_ns
lifetime    ggml_buffers_created, ggml_buffers_freed, contexts_created, contexts_freed,
            backends_created, backends_freed, graphs_created, gallocrs_created,
            gallocrs_freed, released_before_owner_scope_end (bool)
abi         tensor_alignment, table_drift, slot_magic_ok (bool), fp_contract_off (bool),
            graph_context_bytes
```

**`members[].ne0` and `.ne1` are the dims of the tensor R5A *built*, not of the member record.** For
`token_embd` that is `[n_embd, token_count]`, because section 3.4 row-gathers it; the member
record's own `ne1` is `n_vocab` and is validated at step 14. `read_bytes` and `pread_count` say what
was actually read, which is the pair that makes the row-gather visible to a reader instead of
inferable.

**`nodes[]` is the capability's real output.** `l_out` alone would make a failure undiagnosable: a
single wrong digit could come from any of thirty-two nodes. Per-node `sha256`, `bit_sum`, and
`f32_sum_millionths` mean the first divergent node is named, which is what turns a red qualification
into a bug report. `nodes[].id` is R5A's own stable identity; `transcript_name` and `transcript_op`
carry the instrument's, so a future build that renames a node changes a data field rather than the
code.

**Checksums are never floats**, for `r4-alignpack-layer-major.md` section 2.3's reason.
`sha256` is `crypto.sha256` over the exact little-endian f32 bytes; `bit_sum` is the `i64` sum of the
u32 bit patterns; `f32_sum_millionths` is the sequential f32 accumulation of section 3.6 scaled by
10^6 and truncated to `i64`. `nonfinite_count` is reported, never a failure condition — a NaN is a
fact about the weights, and R5A does not get to decide otherwise.

`attn_scale_bits` is published so a reader can verify the scale R5A used without recomputing a square
root: on this model it is the bit pattern of `1/sqrt(128)`.

`schema_version` is `1` and nominal. A consumer keys on `kind` plus `schema_version`.

### 3.8 Validation order and error codes

First applicable row wins. Steps 1 and 2 return `Err` with no output at all. Steps 3 onward produce a
`status: "error"` document and then map to `Err(Error.Invalid)`. **No ggml state is created before
step 17, and nothing outside the process is ever written.**

1. Arm selection and exact arity — five to eight operands. → `R5_ARITY`
2. Lexical path validation of every path operand; `-` in position six is not a path. → `R5_PATH`
3. `LAYER` parses as a non-negative decimal integer. → `R5_INDEX`
4. `TOKENS` parses: 1–6 non-negative decimal integers, comma-separated, no spaces. → `R5_TOKENS`
5. Geometry document open and read. → `R5_GEOMETRY_UNREADABLE`
6. Geometry document parses as JSON and carries `kind == "R1_QWEN_MODEL_IR"`, `schema_version == 1`.
   → `R5_GEOMETRY`, detail `kind` / `schema_version`
7. Every consumed `model` field of section 3.2 is present and in range. → `R5_GEOMETRY`, detail the
   field name
8. Geometry self-consistency: `n_embd == n_head * head_dim`, `n_head % n_head_kv == 0`,
   `n_head_kv >= 1`, `n_expert == 0`. → `R5_GEOMETRY`, detail the relation
9. Architecture preconditions: `arch == "qwen2"`, `rope.type == 2`, `rope.dim_count == head_dim`,
   `rope.scaling_type == null`. → `R5_GEOMETRY`. **This step is what earns section 3.5's five fixed
   RoPE constants.**
10. `LAYER < n_layer`, every token id `< n_vocab`. → `R5_INDEX` / `R5_TOKENS`
11. Pack open (`fs.open_rw`) and header decode, then region validation. → `R4_PACK_*` verbatim
12. Block selection: an embedding `WeightBlock`, an `AttentionBlock` at `LAYER`, an `MlpBlock` at
    `LAYER`. → `R5_BLOCK_MISSING`, detail the kind and layer
13. Member selection by `role_id`: `token_embd`; `attn_norm`, `attn_q`, `attn_q_bias`, `attn_k`,
    `attn_k_bias`, `attn_v`, `attn_v_bias`, `attn_output`; `ffn_norm`, `ffn_gate`, `ffn_up`,
    `ffn_down`. → `R5_MEMBER_MISSING`, detail the role
14. Member shapes against the geometry, each exactly: `token_embd` `[n_embd, n_vocab]`, `attn_q`
    `[n_embd, n_head*head_dim]`, `attn_k`/`attn_v` `[n_embd, n_head_kv*head_dim]`, `attn_output`
    `[n_embd, n_embd]`, `ffn_gate`/`ffn_up` `[n_embd, n_ff]`, `ffn_down` `[n_ff, n_embd]`, the four
    norms and three biases 1-D at their widths. And `row_bytes = token_embd.nbytes / n_vocab`
    divides exactly and is a positive multiple of `type_size`. → `R5_SHAPE`, detail the role
15. Window availability: every `buffer(N)` published its reserved length. → `R4_WINDOW_UNAVAILABLE`,
    detail the window
16. Reads: one `pread` per embedding row, one per block, completing short reads. →
    `R4_PACK_UNREADABLE`
17. `align_ggml_available()`. → `R5_GGML_UNAVAILABLE`, `verdict: "UNAVAILABLE"`. **This is where the
    stub shim stops, and steps 1–16 are therefore fully reachable without ggml, without a model, and
    without a transcript.**
18. `align_ggml_tensor_alignment()` and `align_ggml_table_drift()`. → `R5_ABI`, detail the constant
19. `align_ggml_type_ok(type, ne0)` for all thirteen members. → `R5_TYPE_UNSUPPORTED`, detail
    `role[type]`; `ne0 % blck_size != 0` → `R5_SHAPE`
20. **Alignment**, before any call that can assert: the weight window's base and every member's
    window offset are `0 mod tensor_alignment`. → `R5_ALIGNMENT`, detail the role
21. Backend, context, slot store, and graph creation; `align_ggml_slots_init`. → `R5_GGML_INIT`,
    detail the object
22. Node-table walk: every slot index in range, every source slot non-empty, every op parameter
    valid. → `R5_SLOT`, detail `node[<id>]`
23. `ggml_gallocr` reserve and allocate. → `R5_ALLOC`, detail `reserve` / `alloc`
24. `align_ggml_graph_compute`, one warm-up then five timed calls; any non-zero `ggml_status`. →
    `R5_COMPUTE`, detail `status[<n>]`
25. Reference arm (seven- and eight-operand forms): open the GGUF, read each member at
    `source_offset`. → `R5_SOURCE_UNREADABLE`
26. Reference arm: pack bytes equal GGUF bytes, per member. → `R5_SOURCE_DIVERGED`, detail
    `role@<offset>`
27. Reference arm: build, compute, compare every oracle node bit-exactly. → `R5_REFERENCE_MISMATCH`,
    detail `node[<id>]@<index>`
28. Transcript arm (eight-operand form): open, scan, match. → `R5_TRANSCRIPT` for an unreadable or
    ungrammatical transcript, `R5_ORACLE_MISSING` for a named node the transcript does not carry,
    `R5_ORACLE_SHAPE` for a declared shape that disagrees
29. Transcript arm: compare within section 3.6's thresholds. A breach sets
    `oracle.verdict: "FAIL"` and is **not** an error code — the document reports the numbers.
30. Teardown in section 3.9's order, then render, then write.

| Code | Meaning | Step | Detail |
| --- | --- | --- | --- |
| `R5_ARITY` | wrong arm or operand count | 1 | `N/A` — no document exists |
| `R5_PATH` | a path operand is empty, too long, or contains NUL | 2 | `N/A` — no document exists |
| `R5_INDEX` | `LAYER` does not parse or is out of range | 3, 10 | `layer[<n>]` |
| `R5_TOKENS` | the token list does not parse, is empty, exceeds six, or names an id `>= n_vocab` | 4, 10 | `token[<i>]` |
| `R5_GEOMETRY_UNREADABLE` | the geometry document could not be opened or read | 5 | the path's failure |
| `R5_GEOMETRY` | the geometry document is not a v1 `R1_QWEN_MODEL_IR`, is missing a field, is out of range, is self-inconsistent, or declares an unsupported architecture | 6–9 | the field or relation |
| `R4_PACK_*` | a container defect, surfaced verbatim from `alignpack_read` | 11, 16 | R4's own details |
| `R5_BLOCK_MISSING` | no block of the required kind and layer | 12 | `kind[<n>]layer[<n>]` |
| `R5_MEMBER_MISSING` | a required role is absent from its block | 13 | `role[<name>]` |
| `R5_SHAPE` | a member's dims disagree with the geometry, or a row does not divide | 14, 19 | `role[<name>]` |
| `R4_WINDOW_UNAVAILABLE` | `buffer(N)` degraded | 15 | the window |
| `R5_GGML_UNAVAILABLE` | the stub shim, or no CPU device | 17 | `stub` / `device` |
| `R5_ABI` | an implausible ggml constant, or operand-table drift | 18 | the constant or type id |
| `R5_TYPE_UNSUPPORTED` | a member's ggml type is not a `mul_mat` left operand | 19 | `role[type]` |
| `R5_ALIGNMENT` | a pointer handed to ggml would violate `TENSOR_ALIGNMENT` | 20 | `role[<name>]` |
| `R5_GGML_INIT` | a ggml constructor returned `NULL`, or the slot store failed to init | 21 | the object |
| `R5_SLOT` | a slot index out of range, or a read of an empty slot | 22 | `node[<id>]` |
| `R5_ALLOC` | `ggml_gallocr_reserve` or `_alloc_graph` returned false | 23 | `reserve` / `alloc` |
| `R5_COMPUTE` | `ggml_backend_graph_compute` returned non-success | 24 | `status[<n>]` |
| `R5_SOURCE_UNREADABLE` | the reference GGUF could not be opened or read | 25 | `role@<offset>` |
| `R5_SOURCE_DIVERGED` | pack bytes differ from GGUF bytes | 26 | `role@<offset>` |
| `R5_REFERENCE_MISMATCH` | a node's bytes differ between the two arms | 27 | `node[<id>]@<index>` |
| `R5_TRANSCRIPT` | the transcript is unreadable or ungrammatical | 28 | offset or line prefix |
| `R5_ORACLE_MISSING` | a named node is absent from the transcript, or a matched node's printed elements are not exactly what its declared shape yields | 28 | `node[<id>]`, or `node[<id>]<got>/<expected>` for a count that disagrees in either direction |
| `R5_ORACLE_SHAPE` | the transcript's declared shape disagrees with the computed one | 28 | `node[<id>]` |

**`R5_SLOT` is the code that would otherwise not exist**, and it is the answer to section 2.6's
constraint. Without the slot store's bounds check, an out-of-range index is an out-of-bounds write of
a pointer into an Align buffer — silent memory corruption in the one place the design deliberately
put Align's own bytes next to a foreign library.

**`R5_ORACLE_MISSING` and `R5_ORACLE_SHAPE` are errors while a tolerance breach is not**, and the
asymmetry is deliberate. A tolerance breach is the measurement the capability exists to make. An
unmatched node is the *absence* of that measurement, and reporting `PASS` for zero compared nodes is
the failure this design most needs to make impossible.

### 3.9 Ownership, allocation, lifetime, and bounded memory

| Module | Owns | Imports |
| --- | --- | --- |
| `src/alignpack_read.align` | the v1 reader and its `R4_PACK_*` codes | `std.fs` — unchanged by R5A |
| `src/layer_qwen2.align` | the node table, the role table, the shape rules, the scalar derivations, the mask image, the oracle node table | `core.json`, `core.math` |
| `src/ggml_ffi.align` | **every** `extern "C"` declaration and **every** `unsafe` block, and the safe API above them | none |
| `src/expert_trace.align` | the transcript line grammar and scanner | unchanged by R5A; R5A calls it |
| `src/ggml_spike.align` | both arms, the validation order, the documents, the teardown | the four above |

**Weights are Align-owned; activations are ggml-owned; the slot store is Align-owned.**

- The thirteen weight tensors live in one Align `buffer`, over-reserved by `MAX_TENSOR_ALIGNMENT` and
  padded so each member's window offset is `block_align`-aligned. ggml holds thirteen borrowed
  pointers, validated to be exactly those offsets, and every one is freed before the owner's scope
  ends. This is R4.5's contract, thirteen times.
- The **activations live in the `ggml_gallocr` buffer, which ggml owns**, and that is a deliberate
  R5A choice with a stated reason. `ggml_gallocr` is what computes the reuse plan for a thirty-node
  graph; reimplementing that plan in Align would be a second allocator for a lifetime that R5A does
  not need to control, and it would be R5B's allocator written a stage early with no residency
  requirement to shape it. The gate's clause is `align owns buffer lifetime` for the **weights** —
  the bytes that come from the pack and that a loader will one day tier — and that clause is
  discharged. Activations are transient, sized by the graph, and never persisted.
- What R5B changes: the loader owns weight residency across layers, and the activation buffer becomes
  a reused arena sized once for the worst layer rather than reserved per graph. Section 5.4 carries
  it.
- The **slot store is an Align `buffer`**, because section 2.6 left no alternative that keeps the
  topology in Align. Its bytes are Align's, its capacity is Align's, and the shim writes into it only
  after validating the magic, the capacity, and the index.

**Bounded memory.** Every allocation is a function of the geometry and the token count, computed and
checked before anything is reserved:

```text
weight window     = align_up(row_bytes * T, block_align)
                  + Σ align_up(member.nbytes, block_align)  over the twelve layer members
                  + MAX_TENSOR_ALIGNMENT                          (the alignment pad)
activation        = ggml_gallocr_get_buffer_size, reported not chosen
slot store        = 16 + 8 * MAX_NODE_SLOTS                 = 1,040 B
node readback     = one reusable window of max(node.nbytes) = n_ff * T * 4
mask image        = T * T * 4                               <= 144 B
graph context     = align_ggml_graph_context_bytes(MAX_NODE_SLOTS)
```

`graph.weight_bytes` in the document is the padded member-window total **excluding** the alignment
pad, so it is a property of the model and the token count rather than of the allocator, and section
5.2 can assert it as an exact value.

Measured on this model at `T = 6`: weight window **149,139,456 B**, activation **2,453,376 B**, node
readback **454,656 B**. The whole-member read shape section 2.5 rejected would have made the first
number 455,688,192 B.

**Teardown order**, extending R4.5 section 3.9's contract and asserted by the lifetime counters:
`gallocr` → graph context → weight buffer → weight context → reference buffer → reference context →
backend. The slot store is Align's and drops with its scope, *after* every handle it held has been
freed. `released_before_owner_scope_end` remains a document field.

**`ggml_abort` is `abort()`.** A kernel that hits an internal assertion takes the process down with
no unwinding, no `Drop`, no document, and no code. R5A does not claim the boundary is safe; it makes
every *reachable* failure unreachable — validated geometry, validated shapes, validated types,
validated alignments, bounds-checked slots, bounds-checked copies, null-checked constructors — and
says plainly that the unreachable ones remain.

### 3.10 Ledger dimensions

| Dimension | Answer |
| --- | --- |
| Public surface | `ggml-spike --layer-forward`, section 3.3; `R5_LAYER_FORWARD` v1, section 3.7 |
| Inputs and defaults | Five path operands, one index, one token list. **No defaults.** Geometry has no fallback: an absent field is `R5_GEOMETRY`, never an assumed constant |
| Results, errors, precedence | Section 3.8, first applicable row wins, deterministic across multi-invalid inputs because the order is total |
| Ownership and allocation | Section 3.9; weights and slot store Align-owned, activations ggml-owned with a stated reason |
| Owner module | `src/ggml_spike.align` owns the arm; `src/layer_qwen2.align` owns the topology; `src/ggml_ffi.align` owns the boundary |
| Persisted identity | `kind` + `schema_version`, nominal. The pack's own identity is `r4-alignpack-layer-major.md` section 2.4.6's, unchanged |
| Validation order | Section 3.8, thirty steps, ggml first touched at step 17 |
| Prerequisites | An alignpack v1 pack; an `R1_QWEN_MODEL_IR` v1 document; for the qualification, ggml, the model, and `llama-eval-callback` |
| Acceptance evidence | Section 5.1 owner, section 5.2 qualification, both oracles, tolerances fixed in section 3.6 |
| Metrics | Section 5.3; microbenchmark B only |
| Text/wire boundary | UTF-8 JSON, R0's escaping rules, no float rendered anywhere |
| Inapplicable | Concurrency (single-threaded arm, one process); network (none); schema migration (v1 is the first version) |

---

## 4. Closure matrix

Every cell names an implementation owner and the exact regression that covers it. `S` = reachable
with the stub shim (`make layer-forward-smoke`), `Q` = requires the qualification.

### 4.1 `src/layer_qwen2.align` — the topology as data

| Cell | Owner | Regression |
| --- | --- | --- |
| Formation — node table well-formed | a compile-time-sized column set, `NODE_COUNT` rows | `S` `node-table-shape`: every `node_a`/`node_b`/`node_out` in `[0, MAX_NODE_SLOTS)`, every op known, `node_out` written exactly once |
| Formation — geometry parse | `parse_geometry(borrow doc: str) -> Result<Geometry, Fault>` | `S` fixtures for each of steps 6–9 |
| Success — shapes derived | `expected_dims(role, borrow g: Geometry)` | `S` `geometry-shapes`: the thirteen expected shapes for the real geometry, checked against checked-in constants |
| Failure — a missing field | `R5_GEOMETRY` with the field name | `S` one fixture per consumed field, absent |
| Failure — self-inconsistent | `n_embd != n_head * head_dim` etc. | `S` `geometry-inconsistent` |
| Malformed input — not JSON, wrong kind, wrong version | `json.doc` `Err`, then the kind/version checks | `S` three fixtures |
| Early exit — unsupported arch or rope | step 9 | `S` `geometry-arch`, `geometry-rope-scaled` |
| Scalars — mask image, attention scale | `mask_image`, `attn_scale_bits` | `S` `mask-image`: the `{6,6}` byte image compared to a checked-in golden; `attn-scale`: `1/sqrt(128)`'s bit pattern |
| Cleanup | no handle, no file, no `unsafe` | `S` the `unsafe`/`extern` scan of section 5.1 names only `src/ggml_ffi.align` |

### 4.2 `src/ggml_ffi.align` — the boundary

| Cell | Owner | Regression |
| --- | --- | --- |
| Construction — every new wrapper | one `unsafe` block each, returning `Result` or a scalar | `S` the stub returns the failure status for each; `Q` the real one succeeds |
| Success — status `0` | `code_for` extended with the new codes | `S` `status-map`: every negative shim status maps to exactly one `R5_*`, no status unmapped |
| Failure — `bool` translation | `gallocr_reserve` / `_alloc` return `i32` | `S` `alloc-false`: the stub returns false and `R5_ALLOC` is raised |
| Malformed input — null handle, bad slot | every wrapper null-checks and the slot wrappers bounds-check | `S` `slot-out-of-range`, `slot-empty` |
| Move in/out — no aggregate ever holds `raw` | four named locals only | `S` `no-raw-aggregate`: `grep` for `raw` in a struct field or array position in `src/` finds none |
| Cleanup | every close wrapper is total against a null handle | `S` `teardown-partial`: a fixture that fails at step 21 still runs the full teardown and the counters balance |

### 4.3 `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c`

| Cell | Owner | Regression |
| --- | --- | --- |
| Formation — the two files agree | the shared-contract marker block, extended | `S` byte-identity assertion between the markers, as R4.5 |
| Construction — slot store init | `align_ggml_slots_init` validates 8-alignment, magic, capacity | `S` `slot-misaligned`, `slot-bad-magic` |
| Success — one op per wrapper | one call each, no composite behavior | `Q` the qualification's 32-node graph |
| Failure — every index checked | `0 <= i < capacity`, slot non-empty, before any ggml call | `S` `slot-out-of-range` |
| Malformed input — bit patterns | `memcpy` `int32_t` → `float`, never a cast | `Q` `attn-scale`: the document's `attn_scale_bits` round-trips |
| Early exit — alignment | R4.5's pre-check applied to all thirteen placements | `S` `alignment-refused` on a manufactured misaligned window |
| Cleanup — no `malloc` | the shim allocates nothing | `S` `grep -c malloc scripts/ggml_shim*.c` is `0` |
| Contraction is observed, not asserted | `align_ggml_fp_contract_probe` compares `a * b + c` over `volatile` operands against a separately rounded product and sum; `align_ggml_fp_contract_off` returns it under the build define | `S` `abi.fp_contract_off` `true` on all seventy-four documents; `Q` the same (section 6, correction C15) |
| Rope constants | the five fixed scalars, `mode` validated `== 2` | `S` `rope-mode`: a geometry with `rope.type != 2` is refused at step 9 |

### 4.4 `src/ggml_spike.align` — the `--layer-forward` arm

| Cell | Owner | Regression |
| --- | --- | --- |
| Formation — arm selection | first operand, before path work | `S` `arm-unknown-flag`, `arm-r45-unchanged` |
| Construction — read shape | section 3.4's three reads | `S` `read-shape`: `members[].pread_count` is `T` for `token_embd` and `1` for each block |
| Success — document | the full `R5_LAYER_FORWARD` | `S` golden-file byte comparison on the synthetic pack; `Q` on the real model |
| Failure — each error code | section 3.8 | section 4.6's map |
| Malformed input — every fixture | section 5.1's corpus | section 4.6 |
| Early exit — `-` document destination | R0's convention | `S` `doc-stdout-identical`: both forms emit identical bytes |
| Move in/out — windows | `borrow mut buffer` parameters, as R4.5's reference reader | `S` covered by `teardown-partial` |
| Replacement — none | no in-place update, no cache | `N/A` — R5A writes only the document |
| Return — exit mapping | R0's, verbatim | `S` `exit-codes` |
| Cleanup | section 3.9's order | `S` `teardown-partial`; `Q` `lifetime.*` counters balance and `released_before_owner_scope_end` is `true` |

### 4.5 The oracle cells, which are their own section because they are the capability

| Cell | Owner | Regression |
| --- | --- | --- |
| Reference arm — bytes equal | step 26 | `Q` real model; `S` a synthetic pack whose member bytes are perturbed → `R5_SOURCE_DIVERGED` |
| Reference arm — nodes identical | step 27 | `Q` 18 of 18 identical; `S` a shim built with `ALIGN_GGML_FORCE_REFERENCE_PERTURBATION` (R4.5's mechanism) names the exact node and element |
| Transcript — grammar | `src/expert_trace.align`'s scanner | `S` `transcript-garbage` → `R5_TRANSCRIPT` |
| Transcript — a node absent | step 28 | `S` `transcript-missing-node` → `R5_ORACLE_MISSING`. **The fixture deletes `l_out-0`** |
| Transcript — a shape disagreeing | step 28 | `S` `transcript-wrong-shape` → `R5_ORACLE_SHAPE` |
| Transcript — excluded nodes | `nodes[].oracle == "shape_incomparable"` for `kq`/`kq_soft_max` | `S` asserted in the golden document |
| Transcript — a tolerance breach | step 29 | `S` `transcript-perturbed`: one printed value moved by `0.0003` → `oracle.verdict: "FAIL"`, `status: "ok"`, `worst_node` and `worst_element_index` naming it |
| Transcript — an exact pass | step 29 | `S` the synthetic transcript passes at `max_abs_diff_ten_thousandths == 0`; `Q` the real one at `<= 1` |
| Tolerance is not silently widened | `tolerance_ten_thousandths` is a document field | `S` golden document asserts `1`; a change to the threshold is a golden-file diff |

### 4.6 Error-code-to-fixture map, and the final pass

| Code | Reachable with the stub | Fixture |
| --- | --- | --- |
| `R5_ARITY` | yes | four operand counts and one unknown flag |
| `R5_PATH` | yes | empty, 4097 bytes, embedded NUL |
| `R5_INDEX` | yes | `LAYER` = `-1`, `+0`, `1x`, `n_layer` |
| `R5_TOKENS` | yes | ``, `1,`, `1, 2`, seven ids, an id `== n_vocab` |
| `R5_GEOMETRY_UNREADABLE` | yes | a path that does not exist |
| `R5_GEOMETRY` | yes | one fixture per consumed field plus kind, version, arch, rope type, rope scaling, inconsistency |
| `R4_PACK_*` | yes | R4.5's mutated-pack corpus, reused |
| `R5_BLOCK_MISSING` | yes | a pack with no `MlpBlock` at the layer |
| `R5_MEMBER_MISSING` | yes | a pack whose attention block omits `attn_q_bias` |
| `R5_SHAPE` | yes | a member whose `ne1` disagrees; a `token_embd` whose `nbytes` does not divide by `n_vocab` |
| `R4_WINDOW_UNAVAILABLE` | no — not input-reachable | `N/A`, retained as a fail-closed guard, as `r4-5-external-buffer.md` section 6 correction C8 and Request 35 record |
| `R4_PACK_UNREADABLE` | yes | a pack truncated inside the Mlp block |
| `R5_GGML_UNAVAILABLE` | yes | the stub itself — the default path of the whole owner test |
| `R5_ABI` | no | `Q`, and only if the linked ggml drifts; the drift guard reports it |
| `R5_TYPE_UNSUPPORTED` | yes | a member record carrying ggml type `4` (removed) |
| `R5_ALIGNMENT` | yes | a synthetic pack whose `block_align` is `1`, so a member lands off 32 |
| `R5_GGML_INIT` | yes | the stub's `align_ggml_context_open` returns `NULL` under `ALIGN_GGML_FORCE_INIT_FAILURE` |
| `R5_SLOT` | yes | a stub-only entry point that asks for slot `MAX_NODE_SLOTS`, and one that reads an empty slot |
| `R5_ALLOC` | yes | the stub's `gallocr_reserve` returns false under `ALIGN_GGML_FORCE_ALLOC_FAILURE` |
| `R5_COMPUTE` | yes | `ALIGN_GGML_FORCE_COMPUTE_FAILURE`, R4.5's mechanism |
| `R5_SOURCE_UNREADABLE` | yes | a `REF.gguf` that is one byte long |
| `R5_SOURCE_DIVERGED` | yes | a synthetic pack and GGUF that disagree in one member byte |
| `R5_REFERENCE_MISMATCH` | yes | `ALIGN_GGML_FORCE_REFERENCE_PERTURBATION` |
| `R5_TRANSCRIPT` | yes | a transcript of random bytes |
| `R5_ORACLE_MISSING` | yes | a transcript with `l_out-0` deleted |
| `R5_ORACLE_SHAPE` | yes | a transcript declaring `l_out-0` as `{3584, 5}` |

**Twenty-four of the twenty-six codes are stub-reachable**, which is the property that makes the owner
test worth running on a host with no ggml, no model, and no llama.cpp. The final matrix-to-diff pass
maps every cell above to its implementing function and its passing evidence, or to an explicit
deferral in this document, before review.

---

## 5. Fixtures, qualification, metrics, deferrals, risks, and candidate requests

### 5.1 Owner — `make layer-forward-smoke`, `scripts/run-layer-forward-smoke`

Hosted, ggml-free, model-free, in `HOSTED_CHECK_TARGETS`. It builds the stub shim, builds
`ggml-spike`, and runs every stub-reachable fixture of section 4.6.

**A synthetic tiny geometry, so the whole layer is hand-checkable.** A new
`scripts/layer_forward_fixture.py`, in the style of `scripts/ggml_spike_fixture.py`, writes a pack
and a geometry document for:

```text
n_embd 8   n_head 2   n_head_kv 1   head_dim 4   n_ff 16   n_vocab 32   n_layer 2
rope.type 2   rope.dim_count 4   rope.freq_base 10000.0   rms_eps 1e-05   scaling_type null
```

Every member is F32, so the pack is 5,376 bytes of payload and every expected value is computable by
hand or by the fixture script's own independent forward pass — **pure Python**, importing only
`json`, `math`, `os`, `struct`, and `sys`, so the owner's expected numbers come from a second
implementation and the hosted runner takes on no third-party dependency (section 6, correction
C24). Three tokens, so the mask is `{3,3}`.
The pack has three blocks and thirteen members, and one mutation per reader fixture is produced by a
single byte edit on a copy.

**A synthetic transcript**, written by the same script in
`llama-eval-callback`'s exact line grammar and `%12.4f` / `sum = %f` formatting, carrying the
eighteen oracle nodes at the tiny geometry. This is what makes steps 28 and 29 — the entire oracle —
reachable with no ggml and no llama.cpp. Three mutated copies produce `R5_ORACLE_MISSING`,
`R5_ORACLE_SHAPE`, and the `FAIL` verdict.

**A checked-in real-model transcript excerpt**, `eval/fixtures/qwen2-blk0-6tok.txt`: the **twenty**
`blk.0` records of section 2.2's transcript — the eighteen oracle nodes plus `kq-0` and
`kq_soft_max-0`, which are matched and then excluded from element comparison by contract —
verbatim, **460 lines and 33,883 bytes**, with the exact command and the six token ids in a header
comment (section 6, correction C24). It is swept from the pack-and-model qualification
so a change to the oracle's *parsing* is caught hosted, against real formatting, without a 4.7 GB
model. It is compared only for grammar and node identity in the owner test; its numbers are the
qualification's.

Every fixture's expected document is a checked-in golden file compared **byte for byte**, so field
order, presence rules, the `-`/`false`/`0` conventions, and the fixed tolerances of section 3.6 are
regressions rather than intentions.

Four assertions are not about a fixture:

- `grep -c malloc scripts/ggml_shim*.c` is `0` in both files.
- `abi.fp_contract_off` is `true` in every document the corpus produces — a behavioural probe of
  the loaded library, not the build define — so the goldens cannot quietly become a property of one
  compiler's contraction policy. It is necessary and not sufficient: the kernels also call libm, and
  the goldens themselves are what detect any divergence the flag cannot name (section 6,
  correction C15).
- the `unsafe {` and `extern "C"` scans over `src/` each name exactly `src/ggml_ffi.align`.
- no `raw` appears as a struct field or array element anywhere in `src/`.
- the shared-contract marker block is byte-identical between the two C files.

The smoke writes into a `mktemp -d` tree outside the work tree and removes it on every exit path.

**Adding `layer-forward-smoke` to `HOSTED_CHECK_TARGETS` changes aggregate membership**, so
`CLAUDE.md`'s verification rules select `make ci` for this capability's publication — not because a
pin moved, but because the check topology did. `layer-forward-qualification` joins no aggregate and
is named explicitly in the pull request, as `ggml-spike-qualification` is.

### 5.2 Named qualification — `make layer-forward-qualification`, `scripts/run-layer-forward`

Opt-in, capable-only, in **neither** `HOSTED_CHECK_TARGETS` nor `CAPABLE_ONLY_CHECK_TARGETS`,
exactly as `alignpack-qualification` and `ggml-spike-qualification` are not. It prints an explicit
`N/A` line naming the missing input and exits `0` when any of

```text
ALIGN_LLM_GGML_INCLUDE          ggml headers
ALIGN_LLM_GGML_LIB              ggml libraries
ALIGN_LLM_GGUF_MODEL            the Qwen2 GGUF
ALIGN_LLM_LLAMA_EVAL_CALLBACK   path to llama-eval-callback
```

is unset, or the model or instrument is absent, or free space is under the pack's size plus 1 GiB.
The first three are R4.5's, unchanged; the fourth is new and is the only new environment input.

Otherwise it builds the real shim, packs the model with `./main --pack`, emits the geometry with
`./main --model-ir`, captures the transcript with the **exact** flags section 2.2 established, and
runs:

```text
$ $ALIGN_LLM_LLAMA_EVAL_CALLBACK -m $ALIGN_LLM_GGUF_MODEL -p "def add(a, b):" -n 1 -t 4 \
      -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512 > $TRANSCRIPT
$ ggml-spike --layer-forward $PACK 0 $GEOM 750,912,2877,11,293,1648 \
      $DOC $ALIGN_LLM_GGUF_MODEL $TRANSCRIPT
```

and asserts, against the recorded values of section 2:

| Assertion | Expected |
| --- | --- |
| `status`, `verdict` | `ok`, `EXTERNAL` |
| `model.n_embd`, `n_head`, `n_head_kv`, `head_dim`, `n_ff`, `n_vocab` | `3584`, `28`, `4`, `128`, `18944`, `152064` |
| `model.rms_eps_bits`, `rope_freq_base_bits`, `rope_type`, `context_length` | `358637bd`, `49742400`, `2`, `131072` |
| `members[]` count, `pointer_identity` | `13`, all `true` |
| `members[token_embd].ne1`, `.nbytes`, `.pread_count` | `6`, `12096`, `6` |
| `members[attn_v].ggml_type`, `members[ffn_down].ggml_type` | `14`, `14` — the Q6_K members section 2.3 found |
| `graph.node_count`, `graph.weight_bytes`, `graph.activation_bytes` | `32`, `149139456`, `2453376` |
| the eight attention members' `nbytes` sum | `17020928` — R4.5's recorded `AttentionBlock[0]` `pack_bytes` |
| `reference.verdict`, `nodes_compared`, `nodes_identical` | `IDENTICAL`, `18`, `18` |
| `oracle.verdict`, `nodes_expected`, `nodes_matched` | `PASS`, `18`, `18` |
| `oracle.elements_compared` | `1116` |
| `oracle.max_abs_diff_ten_thousandths` | `<= 1` — section 2.3 measured the equivalent of `0` after rounding |
| `oracle.max_sum_diff_millionths` | within section 3.6's relative bound for every node |
| `oracle.tolerance_ten_thousandths` | `1` — asserted so a widened threshold fails here, not silently |
| `lifetime.*_created == *_freed`, `released_before_owner_scope_end` | equal, `true` |
| `abi.tensor_alignment`, `abi.table_drift`, `abi.fp_contract_off` | `32`, `-1`, `true` |
| `graph.slot_high_water` | `48` — scanned from the store: 13 weights, 3 inputs, 32 nodes |

Then the two ggml-only fixtures of section 4.6, then it removes the pack, the transcript, and the
tree.

**`nodes[].sha256` is recorded in the document but is *not* asserted as a checked-in golden**, and
that is a deliberate narrowing of R4.5's practice. R4.5 asserted one exact `output.sha256` for one
`mul_mat`; eighteen such constants across a whole layer would fail on any ggml kernel change with a
message that reads like corruption. The two oracles are the acceptance contract; the digests are
diagnostics that name *which* node moved when one of them fails.

### 5.3 Metrics

| Metric | Definition | Baseline on this host |
| --- | --- | --- |
| microbenchmark **B**, CPU compute | one dense layer, six tokens, mean of five after one warm-up | **12.97–15.05 ms** over four shipped qualification runs, 13.4 ms typical (section 7.7); the probe harness measured 15.5 ms median (15.3–16.6), 32 nodes |
| `pread_ns` | six embedding rows plus two blocks | 19.5–20.9 ms for 149,139,456 B, warm cache |
| weight bytes per layer | the Align-owned window | 149,139,456 B, of which 12,096 B is embedding |
| activation bytes | `ggml_gallocr_get_buffer_size` | 2,453,376 B |
| whole-member read, rejected | section 2.5's refuted alternative | 455,688,192 B / 87.0 ms, for a byte-identical answer |
| external vs ggml-owned weights | the same graph, both arms | byte-identical output; no measurable compute difference |
| microbenchmark **A** | transfer + GPU compute | **N/A** — no GPU arm and no transfer tier. Section 5.4 |
| microbenchmark **C** | async prefetch + GPU compute | **N/A** — prefetch is the loader's. Section 5.4 |

These are secondary metrics. R5A makes **no** claim on time to a passing patch. They exist so R5B can
size a loader against a measured layer rather than a guess: at the shipped ~13.4 ms per layer and 28
layers, a whole-model prefill of six tokens on this CPU is on the order of 0.38 s of compute over
roughly 3.9 GiB of weights, which is the number that makes residency worth designing.

### 5.4 Deferred surfaces

- **Stage 3, the smallest model.** R5A stops at `l_out-0`. A model needs the twenty-seven remaining
  layers, `output_norm`, `output`, and a real KV cache, and the KV cache is the piece that makes the
  attention shape differ from R5A's (section 2.3's `n_kv` exclusion). That is R5B's consumer
  boundary, and it should be one capability, not a per-layer split — `CLAUDE.md`'s "combine
  prematurely split producer and consumer work" applies directly.
- **Microbenchmarks A and C, and the Metal arm.** Inherited from `r4-5-external-buffer.md` section
  5.4 with its measurement: Metal accepts the same host pointer with no copy on unified memory but
  does not produce bit-identical output, so it needs a tolerance oracle and a different alignment
  rule. R5A's transcript oracle is exactly the instrument that arm will need, which is an argument
  for building it here first.
- **Geometry in the container.** The alignpack carries no hyperparameters, so R5A takes a second
  input. An alignpack v2 that carries the `R1_QWEN_MODEL_IR` `model` object verbatim would make a
  loader a one-file consumer. R5B owns the decision; R5A deliberately does not open a v2.
- **`MAX_PREFILL_TOKENS = 6`.** The cap is the oracle's, not the arithmetic's (section 3.3). Lifting
  it needs an instrument that publishes full tensors, or a different oracle. R5B, with the KV cache.
- **Renaming to `align-runtime`.** Section 3.1's stated cost. At the R5B boundary, with `ggml-spike`
  retained as a deprecated alias for one release.
- **A second architecture.** `src/layer_qwen2.align` is the qwen2 dense layer. A second architecture
  is a second module behind the same node-table shape plus a dispatch on `model.arch`, and it should
  wait until a second real model exists on a host — the same **MOE-PREREQ** shape of decision
  `r4-alignpack-layer-major.md` section 4.5 records.
- **A read-only pack open.** The reader still uses `fs.open_rw`. This is the **fourth** client for
  Request 21, and the first where the file opened read-write is one a loader will hold open for the
  life of a process.
- **Align-owned activations.** Section 3.9's stated choice. R5B's arena, sized once for the worst
  layer, is where it belongs.

### 5.5 Candidate Align capability requests

**Two new requests, both raised by the implementation rather than by the design.** The design's own
probes hit no gap `docs/align-requests.md` did not already carry, and this section originally said
"no new request" on that basis. The implementation then hit two more, filed as **Request 36** — an
owned `array<i64>` struct field cannot be replaced in place and a nested struct field cannot be
moved out of its parent (section 6, correction C9) — and **Request 37** — per-function check time is
superlinear in body length, and a `match` on a `Result` inside a loop costs roughly 45× the same loop
with `?` (section 6, correction C8). Both are `PROPOSED`, neither is blocking, and section 6,
correction C25 records this heading's own change. R5A is additionally new client evidence for three
requests that already existed:

- **Request 34 — `Result` ok payloads beyond scalars (`raw`, `buffer`, records).** R5A is its first
  *architecturally load-bearing* client. Request 34's evidence today is that a constructor cannot
  return a handle and a reason; R5A's is stronger — section 2.6 shows `raw` is refused as an **array
  element** as well as a struct field (`error: array element must be a scalar (composite payloads
  are not supported yet), got raw`), and that refusal is why the node-slot store of section 3.5
  exists at all. The register entry should gain the array-element form, this document's section 2.6
  as evidence, and an acceptance criterion that `array<raw>` compiles; the align-llm verification is
  then to delete the slot store and hold the graph's handles directly.
- **Request 32 — FFI by-value structs and `bool` on AArch64.** `bool` is still refused, now with two
  more affected entry points (`ggml_gallocr_reserve`, `ggml_gallocr_alloc_graph`), both wrapped.
  Section 2.6 also records the **positive** half that Request 32 does not claim and that R5A
  verified: `f32` crosses by value in both directions, in a nine-argument mixed-scalar shape, and
  unsuffixed float literals coerce at an `f32` parameter. That is worth adding to the register as a
  measured boundary of the gap.
- **Request 33 — aligned heap allocation.** Unchanged, and now paid thirteen times per run instead of
  once: every member window is over-reserved by `MAX_TENSOR_ALIGNMENT` and padded, because neither
  `buffer(n)` nor `raw.alloc(n)` takes an alignment.
- **Request 21 — a read-only open**, and **Request 35 — observable `buffer` capacity**, both gain a
  client with no change to their text.

None of the five is blocking. R5A ships entirely on the pinned surface, and section 2.6 compiled
every case that says so.

### 5.6 Risks

| Risk | Mitigation | Residual |
| --- | --- | --- |
| **A llama.cpp default changes again and the oracle silently compares a different graph.** Section 2.2 found three such defaults in one build | The four flags are contractual in section 5.2; the document records `oracle.instrument` and the qualification asserts `nodes_matched == nodes_expected == 18` | A future build could rename a node *and* keep the shape. `R5_ORACLE_MISSING` catches the rename; the risk is a rename that collides with another node's name, which no check can see |
| **`node_NN` positional names.** Section 2.2 fact 3 | The attention-output node is matched by its source weight name | If a future build stops printing source names, that match breaks loudly (`R5_ORACLE_MISSING`), not quietly |
| **The tolerance is widened to make a failure go away** | `oracle.tolerance_ten_thousandths` is a document field asserted in golden files and in the qualification | A deliberate change is a visible diff in three places |
| **`ggml_gallocr` reuses an oracle node's memory and the readback is not the node computed** | `ggml_set_output` on every oracle node, section 3.5; the probe hit exactly this before adding it. The stub engine's `gallocr` reuses dead intermediates the same way, so the hosted owner sees a dropped mark: `lf-force-no-mark-output` turns the oracle to `FAIL` (section 6, correction C18) | A node added to the table without `node_oracle` set is not marked; `node-table-shape` asserts every oracle row is marked, and the forced build proves the failure is observable rather than argued |
| **ggml kernel change moves the numbers** | The bit-exact oracle is version-independent; the tolerance oracle compares against the *same* build's transcript | A ggml/llama.cpp version skew between the linked library and the instrument would show as a tolerance failure. The document records both versions so the message is diagnosable |
| **The shim grows into a second implementation.** Twenty-five new symbols is a lot | Every one is one ggml call plus validation; section 4.3's "one op per wrapper" cell is asserted by review, and no wrapper composes two ops | The `rope_neox` wrapper compiles in five constants; step 9 validates the precondition that makes them correct |
| **ABI drift in the operand table** | R4.5's `align_ggml_table_drift` over all 25 rows, now exercised by two more types (Q6_K appears for the first time) | Unchanged from R4.5 |
| **The slot store is a pointer array in Align memory** | Magic, capacity, 8-alignment, and per-index bounds validated in C before every write; `R5_SLOT` | A caller could hand a *different* buffer of the right shape. The magic makes that a refusal, not a corruption |
| **`ggml_abort`** | Section 3.9 | Unchanged from R4.5, and now across thirty-two nodes instead of one |
| **The goldens become a property of one compiler on one target** | Both C files carry `#pragma STDC FP_CONTRACT OFF`, the build passes `-ffp-contract=off`, and `abi.fp_contract_off` — a behavioural probe rather than the build define — is asserted `true` on every document (section 6, correction C15) | Contraction is not the only source of a per-compiler difference, and this is a live exposure rather than a future one: the stub kernels already call `expf`, `sinf`, `cosf`, and `powf`, none of which libm must round correctly. The fixture's 770 such calls over 73 distinct inputs were verified 0-divergent against glibc 2.39, which is a measurement of this corpus and not a guarantee. A host whose libm differs in the last bit fails a golden, which is the detection this design relies on; the repair would be to name a tolerance in the corpus |
| **The checked-in transcript excerpt goes stale** | It is swept from the qualification, which regenerates it; the owner test uses it only for grammar and node identity | A stale excerpt cannot produce a false `PASS` because its numbers are never asserted hosted |

---

## 6. Implementation-forced corrections

Every row below is a place where the implementation refuted section 3's design and the design moved.
None of them changes what the capability proves; each changes how it is expressed, and each is
recorded here rather than absorbed silently, because section 2's whole argument is that a plan
un-refuted by execution is a plan that has not been tested.

| # | Section 3 said | The implementation found | What ships |
| --- | --- | --- | --- |
| **C1** | The geometry input is an `R1_QWEN_MODEL_IR` document at `schema_version: 1`, and `rms_eps_bits` / `rope.freq_base_bits` are the fields to read | R1 ships no such kind. `src/model_ir.align` emits `kind: "R1_MODEL_IR"` at `schema_version: 2`, and both `_bits` fields are **lowercase eight-character hex strings**, not integers | `src/layer_qwen2.align` validates `kind == "R1_MODEL_IR"` and `schema_version == 2` and parses the two hex strings to `u32`. Step 6's detail vocabulary (`kind`, `schema_version`) is unchanged. The plan named a document that does not exist; the qualification feeds `main --model-ir` straight into the arm, which is what section 3.2 actually wanted |
| **C2** | Step 17 is "where the stub shim stops", and section 4.6 nevertheless marks twenty-four codes and both oracles stub-reachable | Both cannot hold. Behind an unavailable shim, steps 18 to 29 are unreachable, so fourteen codes, the reference oracle, and the transcript oracle would all have been `Q`-only — and section 5.1's claim that the synthetic transcript makes "the entire oracle" reachable hosted would have been false | `scripts/ggml_shim_stub.c` gains a **deterministic single-precision engine** selected by `ALIGN_LLM_GGML_FORCE=engine`. The default stub is unchanged and still stops at step 17, which is what `R5_GGML_UNAVAILABLE` and `ggml-spike-smoke` need. The engine implements the eleven f32 ops of one node table over the tiny geometry, materializes every view, allocates from one static arena, and refuses everything else. `scripts/run-layer-forward-smoke` uses nine shim builds |
| **C3** | The thirteen weights and the three inputs are created through the same `new_tensor` entry points | `inp_tokens` and `inp_pos` are `I32`, and the checked-in operand table is the `mul_mat` **left-operand** predicate, which deliberately omits the integer storage types. Routing an index vector through it would have meant widening a table that means something else | `align_ggml_slot_new_i32_1d` is its own entry point and does not consult the table. The table keeps its meaning and `R5_TYPE_UNSUPPORTED` keeps being about weights |
| **C4** | The op set includes `cont_2d` | The transposed V is genuinely three-dimensional (`{T, head_dim, n_head_kv}`), so `cont_2d` cannot express it, and `kqv_out` is the same call with `ne2 = 1` | One wrapper, `align_ggml_op_cont_3d`. `ggml_cont_3d` is `ggml_cont_4d` with `ne3 = 1` and produces the same single `CONT` node, so the graph is unchanged at thirty-two nodes |
| **C5** | Section 3.9's module table gives `src/ggml_spike.align` "both arms, the validation order, the documents, the teardown" | One file holding both arms is 2,700 lines and two unrelated validation orders, and the R4.5 arm has nothing to gain from it | `src/layer_forward.align` owns the R5A arm; `src/ggml_spike.align` keeps arm selection and both CLIs. The boundary costs one import and no contract |
| **C6** | The transcript is scanned "reusing `src/expert_trace.align`'s scanner" | The reuse is not available. `scan` is module-private, its `TranscriptScan` carries no element values and no `sum`, and `parse_header` never captures a node's **source** names — which is precisely how the attention output projection is matched (section 2.2 fact 3). R2A needed none of the three | `src/layer_forward.align` carries a focused parser for the same grammar, read from `r2a-expert-trace.md` section 2.4. It is the only new duplication in the capability and section 7 names the cells it owns |
| **C7** | `ALIGN_GGML_FORCE_REFERENCE_PERTURBATION` perturbs the bytes copied **out** of a tensor, as R4.5 does | R5A reads both arms back through the same entry point, so perturbing the read perturbs both and the comparison still passes. The forced failure would have proved nothing | The macro moves to `align_ggml_slot_set`, which the primary arm never calls on a weight — it *places* its thirteen and copies none — so slots 0 to 12 of a store are exactly the reference weights. One bit of one reference weight is flipped after it lands in ggml's memory, and the comparison names `node[embd]@0`. R4.5's own `tensor_get` perturbation is untouched, and `align_ggml_slot_get` no longer routes through it |
| **C8** | Nothing; the design is silent on how the arm is shaped | The checker's per-function cost is superlinear in body length and, separately, a `match` on a `Result` with block arms **inside a loop** is far more expensive than the same loop with `?`. Measured on this host at this pin: a 400-line body checks in 40 s and a 900-line one does not finish in 600 s; one stage function with two in-loop `match`es takes 90 s and the same function with `?` takes 2 s | The arm is fourteen functions, none over two hundred lines; every fallible call inside a loop propagates with `?`; the dozen top-level ones route through one two-line `take`. `check-per-unit src/layer_forward.align` is **6 s** and `make check` is 86 s for 29 units. Filed as **Request 37** and recorded in section 5.5. It was first written up as new client evidence rather than a request — a compiler performance property is not a missing surface — but a 45× cost that dictates how a module is decomposed is a requirement on the toolchain, and section 6, correction C25 records that reclassification |
| **C9** | The document's columns live in the one `Outcome` record each stage fills in | At this pin an owned `array<i64>` field **cannot be replaced in place** — `error: field replacement of array<i64> is not supported yet ... replace the whole struct` — and a nested struct field cannot be moved out of a struct either | The columns live in six small records (`TokenColumns`, `MemberColumns`, `Layout`, `ReadColumns`, `AbiColumns`, `PlacementColumns`, `NodeColumns`, `OracleStates`), each assigned exactly once and as a whole by the stage that produces it. `Outcome` keeps only scalars and names. Section 5.5 records the gap |
| **C10** | `nodes[].f32_sum_millionths` is the sequential f32 accumulation "truncated to `i64`" | Truncation loses up to one millionth for no benefit and makes the field disagree with the transcript by a unit that is not a disagreement | The accumulation is widened to `f64` and **rounded** to the nearest millionth. The tolerance is unaffected: section 3.6's floor is a thousand millionths |
| **C11** | Section 3.3's CLI table shows an eight-operand form ending in `TRANSCRIPT.txt` and says the summary block is printed "in the six-, seven-, and eight-operand forms" | `-` in the document position is R0's machine form and must not print a summary beside the document it emits | The summary is printed exactly when a real document path is given, which is R4.5's rule verbatim. `-` selects the document alone in every form |
| **C12** | Step 12's `R5_BLOCK_MISSING` fixture is "a pack with no `MlpBlock` at the layer" | A block record declaring zero members is a container defect that `alignpack_read` refuses first, with `R4_PACK_HEADER`, and it is right to | The fixture omits the block from the table entirely. `R5_BLOCK_MISSING` stays about a block that is not there, which is the only thing it can honestly be about |
| **C13** | `R5_SLOT`'s empty-slot fixture empties a weight slot | A weight slot is size-checked against the pack's `nbytes` immediately after creation, so the run stops at `R5_SHAPE` before anything reads it | The forced build empties `inp_pos`, the one slot no size check guards. The first use of it is `R5_SLOT`, which is the code the fixture exists for |
| **C14** | `R4_PACK_LENGTH` is the truncated-pack code | The reader's own code for a file shorter than its header claims is `R4_PACK_TRUNCATED` | The fixture expects what the reader emits. `R4_PACK_*` is surfaced verbatim, exactly as section 3.8 says |
| **C15** | Nothing; the design is silent on how the shim is compiled | The stub engine's kernels are the reference the checked-in golden documents are generated from, and `a * b + c` may be contracted into one fused multiply-add. Whether it is depends on the compiler and the target: Apple clang on `arm64` contracts, GCC 13 on `x86-64` does not, and **twelve of the forty-eight goldens then in the corpus differ between the two**. A hosted check that only reproduces on the machine that generated it is not a check | Both C files carry `#pragma STDC FP_CONTRACT OFF`, `scripts/build-ggml-shim` passes `-ffp-contract=off` and defines `ALIGN_GGML_FP_CONTRACT_OFF`, and the document publishes `abi.fp_contract_off`. **The exported value is a behavioural probe, not the define**: `align_ggml_fp_contract_probe` compares `a * b + c` over `volatile` operands against a separately rounded product and sum on `(1 + 2^-23, 1 + 2^-22, -1)`, whose two answers differ by one ulp, and `align_ggml_fp_contract_off()` returns it. A define says what the build asked for; clang honours `-ffp-contract=fast` over the pragma without touching the define, so provenance alone was not the property the corpus needs. Both runners assert `true` on every document. **`-ffp-contract=off` is necessary but not sufficient.** The stub engine calls libm — `expf` in soft-max and SiLU, `sinf`/`cosf` in RoPE, and `powf` for the RoPE theta scale — and none of those four is required to be correctly rounded, so Apple libm and glibc may differ in the last bit on some inputs. (`sqrtf` in RMS norm is exempt: IEEE-754 requires square root to be correctly rounded.) The owner's fixture makes **770 such calls over 73 distinct inputs**, and every one was verified 0-divergent against glibc 2.39. That is a measured property of this corpus, not a guarantee about libm: **the goldens are the detector** and the flag is the diagnosis for the one cause it can name. The dependency is recorded here rather than left implicit. **Cases:** every one of the seventy-four `S` rows, and `Q` `abi.fp_contract_off` |
| **C16** | `graph.slot_high_water` is a document field | It was assigned `SLOT_NODE_BASE + node_table.count` — a constant derived from the node table, which cannot disagree with the node table. The field measured nothing | `align_ggml_slots_high_water` scans the store for the highest occupied index. **Cases:** `S` every engine row asserts `48`; `Q` asserts `48` (13 weights + 3 inputs + 32 nodes) |
| **C17** | Section 3.5's scalars cross as `i32` bit patterns and "the shim reinterprets, it does not decide" | Reinterpretation without a predicate is a crash. `rms_eps_bits` reaches `ggml_rms_norm`, which asserts `eps >= 0.0f`, and `GGML_ASSERT` is `abort()`: `7fc00000` (NaN), `ff800000` (-inf), `bf800000` (-1.0), and `ffffffff` are all legal eight-hex-digit strings that took the process down with **exit 134, no document, no error code, and no teardown**. Align never interprets the pattern it forwards, so no other step could see it | Step 7 refuses a pattern whose sign bit is set or whose exponent field is `0xff`, for `rms_eps_bits` **and** `rope.freq_base_bits`, and additionally refuses `freq_base` `00000000` because a RoPE base must be positive — `R5_GEOMETRY`, detail the field. `align_ggml_eps_ok` is the same refusal inside both C files, returning `ALIGN_GGML_SHAPE` before the call that would assert. **Cases:** `S` `lf-geometry-eps-nan`, `-eps-neg-inf`, `-eps-negative`, `-eps-all-ones`, `-rope-base-nan`, `-rope-base-inf`, `-rope-base-negative`, `-rope-base-zero` |
| **C18** | `ggml_set_output` is "mandatory for every oracle node", and section 5.6 carries the risk that a node the table forgets is overwritten by `ggml_gallocr` | The hosted owner could not observe that risk at all. The stub engine bump-allocated one block per node and never reused one, so a build with `mark_outputs` removed produced **byte-identical output and a `PASS` verdict**. The one contract that most needs a hosted regression had none | The engine's `align_stub_plan` does what `ggml_gallocr` does: a node's block returns to a free list once its last consumer has run unless it is an output, and the next node that fits takes it. Allocation precedes the frees for that node, so a node never aliases its own source, and first fit by lowest offset keeps the plan deterministic for the goldens. `ALIGN_LLM_GGML_FORCE=engine+no-mark-output` drops the mark. **Cases:** `S` `lf-force-no-mark-output` — `status: "ok"`, `oracle.verdict: "FAIL"`, `worst_node: "norm"`, `max_abs_diff_ten_thousandths` 19,615, against `PASS` and `0` under the old allocator |
| **C19** | "`R5_ORACLE_MISSING` … reporting `PASS` for zero compared nodes is the failure this design most needs to make impossible" | It was possible. A node was "matched" when its **header** was found and its declared shape agreed; nothing required its value block to have been parsed. A transcript of headers alone reported `PASS` over `elements_compared: 0`, and one with a single value block deleted reported `PASS` over 300 of 318 elements | Every compared node must contribute exactly `Π printed_count(ne_d)` elements — each axis prints at most six positions, so the product is what a well-formed record yields. **Any inequality** is `R5_ORACLE_MISSING` with detail `node[<id>]<got>/<expected>`, not only a shortfall: the test in `src/layer_forward.align` is `got != expected`, so a node given extra printed elements reports `24/18` exactly as a truncated one reports `0/18`. A count above the expectation is a record bound twice or printed twice, which is no more a measurement of the node than a count below it. A zero total is refused as a backstop. **Cases:** `S` `lf-engine-transcript-headers` (`node[embd]0/18`), `lf-engine-transcript-novalues` (`node[l_out]0/18`); `Q` `elements_compared == 1116` |
| **C20** | Section 4.1's "a missing field" cell is covered by "one fixture per consumed field, absent" | The fifteen `geometry-missing-*` documents were written by the fixture script on every run and **no case referenced one**. The cell's evidence was a file on disk, not a result | `scripts/run-layer-forward-smoke` carries fifteen `lf-geometry-missing-*` rows, one per consumed `model` field including the four under `rope`, each asserting `R5_GEOMETRY` beside its golden. **Cases:** the fifteen rows; the golden corpus grows from 48 to 74 documented cases with C17's eight and C19's two |
| **C21** | Section 2.2 fact 3: the attention output projection has no stable name and is matched by its source weight | `scripts/sweep-layer-forward-excerpt.py`, which regenerates the checked-in excerpt, matched it as the literal `node_31`. A build that renumbered the node would make the excerpt unregenerable for a reason that has nothing to do with the excerpt — the exact failure fact 3 exists to prevent | The sweep matches the record whose op is `MUL_MAT` and whose first source matches `blk.\d+.attn_output.weight`, keyed as `@attn_output`. **Cases:** re-sweeping the checked-in `eval/fixtures/qwen2-blk0-6tok.txt` through the new matcher reproduces it byte for byte |
| **C22** | Nothing; the design does not say what the qualification leaves behind | `scripts/run-layer-forward`'s forced-failure loop replaces `build/lib/libalign_ggml_shim`, which lives outside the work directory the trap removes. Any early exit inside the loop — a failed assertion, a signal — left a `-DALIGN_GGML_FORCE_*` library in place for whatever ran next | The `EXIT`/`HUP`/`INT`/`TERM` trap rebuilds the ordinary real shim before removing the work directory, guarded by a flag so it does not run before the first build. **Cases:** `Q` the trap is on the same exit path as the pack removal the qualification already proves |
| **C23** | Section 3.3 prints the summary block as an aligned two-column table | The arm prints each label and its value on **separate lines**. That is R4.5's shape inherited verbatim — `print` writes one line — and the block is read by line ordinal, which is what makes a sanitized path containing a colon unambiguous | Section 3.3 shows the shipped shape. No code changed: the document was wrong about the code, not the other way round |
| **C24** | Section 5.1 describes a "twenty-line NumPy reference" and an excerpt of "about 330 lines and 24 KiB" | The fixture's reference forward is pure Python importing only `json`, `math`, `os`, `struct`, and `sys` — the hosted owner takes on no third-party dependency — and the shipped excerpt is **twenty** records, 460 lines, 33,883 bytes | Section 5.1 carries the shipped numbers and names the real reference implementation |
| **C25** | Section 5.5 is headed "No new request", and correction C8 records its own finding as "new client evidence rather than a new request" | Two requests were filed from the implementation: **Request 36** (C9's `array<i64>` field replacement and nested-struct move) and **Request 37** (C8's check-time cost). A heading that says none exists is wrong about the register it points at | Section 5.5 names both, keeps the three existing requests R5A strengthens, and C8's row records the reclassification: a 45× cost that dictates how a module is decomposed is a requirement on the toolchain, not only an observation about it |
| **C26** | Section 5.1 says the owner is hosted, ggml-free, and model-free, and says nothing about which tools it may call | It used `sort` for the two static `unsafe`/`extern "C"` scans. The fresh worker image ships a curated tool set (`image/fresh/Dockerfile`) with no `sort`, and this runner is a `HOSTED_CHECK_TARGETS` member there, so the check would fail inside the fresh aggregate rather than on any developer host. R4.5 hit the same class as its own correction C22 | The scans sort through a one-line `python3` helper, `sorted_paths`. **Cases:** the owner run with `PATH` restricted to exactly the curated set on Linux — PASS, `check gate topology: PASS` beside it, and unchanged on macOS |
| **C27** | Section 5.1 says the smoke writes its corpus into a `mktemp -d` tree removed on every exit path, and does not say where its **builds** go | The nine shim builds went to `build/lib` and the executable to `./ggml-spike`, both inside the work tree. The fresh worker permits the whole aggregate to leave exactly one file, `main`, in `/workspace`, so the owner passing would still fail the aggregate afterwards with no output naming the cause — R4.5's own correction C23 | The shims build into `${work_dir}/lib` through `ALIGN_LLM_GGML_SHIM_DIR` and the executable is moved to `${work_dir}/ggml-spike` in the same step that creates it; `make layer-forward-smoke` is unchanged for developers. **Cases:** `git status --porcelain --ignored` before and after a run names nothing the runner created |

Three of section 3's claims were **confirmed** by the implementation rather than corrected, and they
are worth recording because each was a risk when it was written: `f32` never had to cross the FFI
boundary (every scalar crosses as an `i32` bit pattern and the shim `memcpy`s it, so section 2.6's
`f32` probe stays evidence that the choice is a choice); the node-slot store held the whole graph
with no aggregate anywhere (`raw` appears in no record field and no array in `src/`, asserted by the
owner test); and the thirty-two-row node table needed no control flow — one loop issues one shim
call per row for both arms, and the reference arm is the same table walked twice.

## 7. Closure matrix to implementation

Every applicable cell of section 4, mapped to the function that implements it and the case that
covers it. `S` cases are rows of `scripts/run-layer-forward-smoke`; `Q` cases are assertions in
`scripts/run-layer-forward`. Golden-file rows are additionally covered byte for byte by
`scripts/layer-forward-golden.jsonl`, which carries all **seventy-four** documented cases.

### 7.1 `src/layer_qwen2.align`

| Cell | Implementation | Evidence |
| --- | --- | --- |
| Node table well-formed | `node_table`, `output_slot` | `S` every engine case: `graph.node_count == 32`, and `graph.slot_high_water == 48` — the latter **scanned from the store** by `align_ggml_slots_high_water` rather than derived from the node table, so it can disagree with it. Being a high-water mark, what it can show is a **missing top slot**: it is the highest occupied index plus one, so a walk that skipped a slot below the top still reads 48 and the goldens are what catch that (section 6, correction C16); `Q` the same two numbers |
| Geometry parse | `parse_geometry`, `parse_bits32` | `S` `lf-geometry-not-json`, `lf-geometry-kind`, `lf-geometry-version` |
| Shapes derived | `member_table`, `member_ne0_of`, `member_ne1_of` | `S` `lf-shape`; `Q` the thirteen `members[].ne0`/`ne1` against the real geometry |
| A missing field | `geometry_fault` per consumed field | `S` fifteen `lf-geometry-missing-*` rows, one per consumed `model` field, each asserting `R5_GEOMETRY` beside its golden (section 6, correction C20) |
| Self-inconsistent | step 8's three relations | `S` `lf-geometry-inconsistent`, `lf-geometry-head-kv`, `lf-geometry-expert` |
| Malformed input | `json.doc` `Err`, kind, version | `S` `lf-geometry-not-json`, `lf-geometry-kind`, `lf-geometry-version` |
| A bit pattern that is not a usable float | `bits32_finite_nonnegative`, and `align_ggml_eps_ok` as the shim-side backstop | `S` eight rows: `lf-geometry-eps-nan`, `-eps-neg-inf`, `-eps-negative`, `-eps-all-ones`, `-rope-base-nan`, `-rope-base-inf`, `-rope-base-negative`, `-rope-base-zero`, all `R5_GEOMETRY` (section 6, correction C17) |
| Unsupported arch or rope | step 9 | `S` `lf-geometry-arch`, `lf-geometry-rope-type`, `lf-geometry-rope-scaled`, `lf-geometry-rope-dims` |
| Mask image, attention scale | `write_mask`, `attn_scale_bits` | `S` the oracle `PASS` at `max_abs_diff == 0` is the mask and the scale being right; `Q` `model.attn_scale_bits` |
| Cleanup | no handle, no file, no `unsafe` | `S` the `unsafe {` / `extern "C"` scans name only `src/ggml_ffi.align` |

### 7.2 `src/ggml_ffi.align`

| Cell | Implementation | Evidence |
| --- | --- | --- |
| Construction — every new wrapper | thirty-two `unsafe` blocks, one call each | `S` the default stub answers every one; `Q` the real one succeeds |
| Success — status `0` | `r5_code_for` | `S` twenty-two distinct codes observed in documents |
| `bool` translation | `gallocr_reserve` / `_alloc` return `i32` | `S` `lf-force-alloc` → `R5_ALLOC` |
| Null handle, bad slot | every wrapper null-checks; the slot wrappers bounds-check | `S` `lf-force-slot-range`, `lf-force-slot-empty` |
| No aggregate holds `raw` | four bare locals per arm | `S` the record-declaration scan over `src/` |
| Cleanup | `stage_teardown`, total against null | `S` every engine case asserts `lifetime.*_created == *_freed`; `Q` the same, plus `released_before_owner_scope_end` |

### 7.3 `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c`

| Cell | Implementation | Evidence |
| --- | --- | --- |
| The two files agree | the shared-contract marker block, extended with the slot store | `S` byte-identity assertion on every run |
| Slot store init | `align_ggml_slots_init` validates 8-alignment, magic, capacity | `S` `abi.slot_magic_ok` and `graph.slot_capacity == 128` in every engine case |
| One op per wrapper | one ggml call plus validation, no composite | `Q` the thirty-two-node graph |
| Every index checked | `align_ggml_slot_store` / `_load` | `S` `lf-force-slot-range` (out of range), `lf-force-slot-empty` (empty read) |
| Bit patterns | `align_ggml_bits_to_f32`, `memcpy` and never a cast | `Q` `attn_scale_bits`, `rms_eps_bits`, `rope_freq_base_bits` all round-trip and the oracle passes |
| Alignment | R4.5's pre-check on all thirteen placements | `S` `lf-engine-alignment` on the `block_align = 1` pack |
| No `malloc` | neither file allocates | `S` `grep -q malloc` over both files |
| Contraction is off | `#pragma STDC FP_CONTRACT OFF` in both files plus `-ffp-contract=off` and `-DALIGN_GGML_FP_CONTRACT_OFF=1` in `scripts/build-ggml-shim`, reported by `align_ggml_fp_contract_probe`'s one-ulp comparison rather than by the define | `S` `abi.fp_contract_off` asserted `true` on every one of the seventy-four documents; `Q` the same. Necessary, not sufficient: the kernels' libm calls are recorded in section 6, correction C15, and the goldens are the detector (section 6, correction C15) |
| A `gallocr` that reuses | `align_stub_plan`, allocate-then-free with a free list | `S` `lf-force-no-mark-output`: dropping `ggml_set_output` makes the oracle `FAIL` at `worst_node: "norm"`, and with the previous bump allocator the same build reported `PASS` (section 6, correction C18) |
| Rope constants | five compiled in, `mode` validated `== 2` | `S` `lf-geometry-rope-type`; `Q` the two `ROPE` nodes agree with the instrument |

### 7.4 `src/layer_forward.align` — the arm

| Cell | Implementation | Evidence |
| --- | --- | --- |
| Arm selection | `ggml_spike.main`, first operand, before path work | `S` `lf-arm-unknown-flag`, and the `arm-r45-unchanged` assertion that a non-flag operand still emits `R4_5_EXTERNAL_BUFFER` |
| Read shape | `stage_read` | `S` `members[0].pread_count == 3` and `1` for every block member; `Q` `6` and `1` |
| Document | `render`, `render_members`, `render_nodes` | `S` forty-eight golden documents; `Q` the real model |
| Each error code | `stage_*` | section 7.6 |
| Malformed input | the fixture corpus | section 7.6 |
| `-` document destination | `run` | `S` `doc-stdout-identical` and the `-` form comparison |
| Windows | `borrow mut buffer` parameters | `S` covered by the lifetime assertions |
| Replacement — none | R5A writes only the document | `N/A` |
| Exit mapping | R0's, verbatim | `S` every case asserts `status` against the exit code |
| Cleanup | `stage_teardown` | `S` every engine case; `Q` the counters balance |

### 7.5 The oracles

| Cell | Implementation | Evidence |
| --- | --- | --- |
| Reference — bytes equal | `compare_source` | `S` `lf-engine-source-diverged` → `R5_SOURCE_DIVERGED`, `lf-engine-source-short` and `lf-engine-source-missing` → `R5_SOURCE_UNREADABLE`; `Q` all thirteen members equal |
| Reference — nodes identical | `stage_reference_weights`, `stage_reference_compare` | `S` 20/20 identical on the synthetic pack, and `lf-force-reference` naming `node[embd]@0`; `Q` 20/20 on the real model |
| Transcript — grammar | `scan_transcript`, `parse_header`, `parse_fixed` | `S` `lf-engine-transcript-garbage` → `R5_TRANSCRIPT` |
| Transcript — a node absent | step 28 | `S` `lf-engine-transcript-missing` → `R5_ORACLE_MISSING` |
| Transcript — a node matched but not compared | the per-node printed-element count, step 28 | `S` `lf-engine-transcript-headers` → `R5_ORACLE_MISSING`, detail `node[embd]0/18`, and `lf-engine-transcript-novalues` → detail `node[l_out]0/18`. Before the repair both were `PASS`, the first over **zero** compared elements and the second over 300 of 318 (section 6, correction C19) |
| Transcript — a shape disagreeing | step 28 | `S` `lf-engine-transcript-shape`, and `lf-engine-transcript-excerpt`, which parses the **real** instrument's twenty records and disagrees only about the shape |
| Transcript — excluded nodes | `oracle.compared` | `S` asserted as `["kq", "kq_soft_max"]` in every engine case; `Q` the same |
| Transcript — a tolerance breach | step 29 | `S` `lf-engine-transcript-perturbed`: `status: "ok"`, `oracle.verdict: "FAIL"`, `worst_node: "l_out"` |
| Transcript — an exact pass | step 29 | `S` `max_abs_diff_ten_thousandths == 0` over 318 elements against an independently computed reference; `Q` `<= 1` over 1,116 |
| Tolerance not silently widened | `tolerance_ten_thousandths` is a document field | `S` asserted `== 1` beside the golden; `Q` asserted `== 1`, with the two sum bounds |

### 7.6 Error code to case

| Code | Case | Where |
| --- | --- | --- |
| `R5_ARITY` | `lf-arity-4`, `lf-arity-9`, `lf-arm-unknown-flag` | `S`, no document |
| `R5_PATH` | `lf-path-pack-empty`, `lf-path-geometry-empty`, `lf-path-long`, `lf-path-doc-empty`, `lf-path-reference-empty` | `S`, no document |
| `R5_INDEX` | `lf-index-negative`, `-nonnumeric`, `-leading-zero`, `-plus`, `-oob` | `S` |
| `R5_TOKENS` | `lf-tokens-empty`, `-trailing`, `-space`, `-seven`, `-oob` | `S` |
| `R5_GEOMETRY_UNREADABLE` | `lf-geometry-unreadable` | `S` |
| `R5_GEOMETRY` | thirty-three `lf-geometry-*` rows: ten preconditions, fifteen `-missing-*`, eight bit patterns | `S` |
| `R4_PACK_*` | `lf-pack-truncated` → `R4_PACK_TRUNCATED` | `S` |
| `R4_PACK_UNREADABLE` | `lf-pack-missing` | `S` |
| `R5_BLOCK_MISSING` | `lf-block-missing`, `lf-engine-layer-1` | `S` |
| `R5_MEMBER_MISSING` | `lf-member-missing` | `S` |
| `R5_SHAPE` | `lf-shape`, `lf-stride` | `S` |
| `R4_WINDOW_UNAVAILABLE` | **not input-reachable**, retained as a fail-closed guard | `N/A`, as `r4-5-external-buffer.md` section 6 correction C8 and Request 35 record |
| `R5_GGML_UNAVAILABLE` | `lf-stub-unavailable` and every default-stub row | `S` |
| `R5_ABI` | **not reachable**: it needs a linked ggml whose operand table has drifted | `N/A`; the drift guard reports it and `Q` asserts `table_drift == -1` |
| `R5_TYPE_UNSUPPORTED` | `lf-engine-type` | `S` |
| `R5_ALIGNMENT` | `lf-engine-alignment` | `S` |
| `R5_GGML_INIT` | `lf-force-init` | `S`; `Q` against the real shim |
| `R5_SLOT` | `lf-force-slot-range`, `lf-force-slot-empty` | `S` |
| `R5_ALLOC` | `lf-force-alloc` | `S` |
| `R5_COMPUTE` | `lf-force-compute` | `S`; `Q` against the real shim |
| `R5_SOURCE_UNREADABLE` | `lf-engine-source-short`, `lf-engine-source-missing` | `S` |
| `R5_SOURCE_DIVERGED` | `lf-engine-source-diverged` | `S` |
| `R5_REFERENCE_MISMATCH` | `lf-force-reference` | `S` |
| `R5_TRANSCRIPT` | `lf-engine-transcript-garbage` | `S` |
| `R5_ORACLE_MISSING` | `lf-engine-transcript-missing`, `lf-engine-transcript-headers`, `lf-engine-transcript-novalues` | `S` |
| `R5_ORACLE_SHAPE` | `lf-engine-transcript-shape`, `lf-engine-transcript-excerpt` | `S` |

**Twenty-four of the twenty-six codes are reached by `make layer-forward-smoke`** — twenty-two in a
document and two as the absence of one — and the runner asserts that count rather than claiming it.
The two that are not are the two section 4.6 already marked unreachable, and both are fail-closed
guards over conditions no input can produce.

### 7.7 What the shipped implementation measured

`make layer-forward-qualification` against `qwen2.5-coder-7b-instruct-q4_k_m.gguf`, layer 0, tokens
`750,912,2877,11,293,1648`, the four contractual flags, on the section 2.1 host:

```text
backend                CPU                    graph nodes            32
weight window          149,139,456 B          activation             2,453,376 B
pread                  55.2 ms                build                  0.048 ms
compute                12.970 ms              reference compute      15.460 ms
oracle                 5.267 ms
self-reference         IDENTICAL, 20 of 20 nodes byte-identical
transcript             PASS, 18 of 18 nodes, 1,116 elements
max |element diff|     0 ten-thousandths      max |sum diff|         3,907 millionths
l_out sha256           f601bf855d32ffa8faca2f50d98b2344df44e6b8aeb9b1e46b0d74b58685bdc6
l_out bit sum          45,431,914,068,759
lifetime               buffers 3/3, contexts 5/5, backends 1/1, gallocrs 2/2, released true
```

Three of those numbers are worth reading twice.

**`max |element diff|` is 0, not 1.** Section 3.6 set the threshold at one unit of ten-thousandths
— twice the print bound — from a probe that measured 5.0e-5. The shipped arm rounds every computed
`f32` to the same unit the instrument prints, and over all 1,116 sampled elements of all eighteen
oracle nodes **not one differed by a single unit**. The layer is not within tolerance of
llama.cpp's; at the precision the instrument publishes, it is the same layer.

**`max |sum diff|` is 3,907 millionths and that is a pass.** It is `ffn_gate-0`, whose sum is
-64,545.386719 against a printed -64,545.382812: a relative disagreement of 6.1e-8 against a bound
of 645,453 millionths. Section 3.6's relative rule is what makes a number that looks large a number
that is not, and the document publishes both so a reader does not have to take that on trust.

**`compute` is 12.970 ms against the probe harness's 15.5 ms.** The probe's harness and the
shipped arm build the same thirty-two-node graph over the same bytes, so the 16% is the shipped
arm's own `gallocr` reuse plan and warm-up discipline rather than a different computation — the
self-reference oracle proves the output is byte-identical. Three further qualification runs at the
review-repaired head measured **15.048, 13.350, and 13.379 ms** with the same `l_out` sha256,
`bit_sum`, oracle verdicts, and 3,907-millionth worst sum, so section 5.3's **microbenchmark B** is
discharged at **12.97–15.05 ms per dense layer, six tokens, warm, CPU — 13.4 ms typical over four
runs** rather than at a single number, and the probe's 15.5 ms stands as the probe's, not as a
regression. The run-to-run spread is this host's, not the arm's: every checksum is identical across
all four runs. `pread` is 55.2 ms against the probe's 19.5–20.9 ms
because the qualification reads a pack written seconds earlier on a 95%-full volume rather than a
warm-cached GGUF; it is a cache-state difference, not a read-shape one, and the byte count —
149,139,456 — is identical to the value section 2.5 measured.
