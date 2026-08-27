# R1C-OLMOE-MOE-IR: olmoe frontend, the first real MoE model, and the `BlockPlan` test

Status: plan of record for the third Track B R1 capability. It is authoritative for the R1C public
contract: the `olmoe` arm of the architecture dispatch behind `main --model-ir`, `main --pack`, and
`main --pack-verify`; the new `src/frontend_olmoe.align` owner module; and the two roles appended to
the frozen `role_id` list in `src/alignpack.align` and its `scripts/alignpack_reader.py` mirror.

`docs/specs/r1b-gptoss-moe-ir.md` remains authoritative for everything this document does not amend:
`R1_MODEL_IR` at `schema_version: 2`, the `claimed_absolute_offset` / `claimed_nbytes` contract, the
`BlockPlan` surface, the neutral builder `src/model_ir.align`, the claim-tiling oracle, and the
per-expert granularity decision. `docs/specs/r1-qwen-model-ir.md` remains authoritative for the
`GgufTable` producer surface, the CLI grammar, the geometry and overflow rules, and the size-sum
oracle. `docs/specs/r4-alignpack-layer-major.md` remains authoritative for the pack format and the
frozen role list this document appends to. `docs/specs/r0-gguf-inspection.md` remains authoritative
for the GGUF container contract.

This document triggers the `CLAUDE.md` proportional design gate on one count: it adds a public
module (`src/frontend_olmoe.align`) whose block plan and role table are a new public contract, and
it appends to a frozen persisted identity (the `role_id` list, which travels in every `.alignpack`).
It does **not** change a versioned exchanged format, an ownership boundary, or a coordinated
invariant across three or more modules — which is itself the finding section 1.5 records. The ledger
is therefore small and the closure matrix covers two modules rather than five.

**Every hyperparameter, tensor name, shape, and byte count in this document is measured on a real
model.** There is no assumption banner. Section 2.1 records the probe.

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

Turn `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` — a real, locally present, 4,213,512,192-byte
mixture-of-experts model with 64 experts and top-8 routing — into the same two intermediate
representations R1B produces for a synthetic gpt-oss file, and thereby:

1. give `align-coder` its first Model IR and Block IR derived from a MoE model that exists;
2. replace R1B's ASSUMED generic-MoE mechanics with measured evidence (section 2.9);
3. execute the test `docs/specs/r1b-gptoss-moe-ir.md` section 5.5 set for itself — that a second MoE
   architecture "should require no change to `src/model_ir.align`", recorded there as "a design
   intent rather than a guarantee".

### 1.2 In scope

1. `src/frontend_olmoe.align`: the olmoe hyperparameters, ordered validation, role/shape/name
   tables, the olmoe `model` object, and the per-layer block plan with one `RouterBlock` and 64
   `ExpertBlock`s.
2. `olmoe` as a third accepted value of `general.architecture` at all three dispatch sites in
   `src/main.align` (`--model-ir`, `--pack`, `--pack-verify`).
3. Two roles appended to the frozen `role_id` list: `attn_q_norm` (27) and `attn_k_norm` (28), in
   `src/alignpack.align` and mirrored in `scripts/alignpack_reader.py`.
4. A synthetic olmoe corpus in `scripts/gguf_fixture.py` and its cases in
   `scripts/run-model-ir-smoke`.
5. An `olmoe` comparison row set in `scripts/run-model-ir-parity`, with the expected values of
   section 4.4 measured on this host.
6. The size-sum oracle and the claim-tiling oracle run against the real file, recorded in the pull
   request as the first real-MoE evidence for both.

### 1.3 Non-goals

- **No new GGML geometry row.** The model uses `F32` (0), `Q4_K` (12), and `Q6_K` (14) only, all of
  which `src/gguf.align` already sizes. `docs/specs/r1-qwen-model-ir.md` section 5.5's gate is not
  triggered.
- **No schema change.** `R1_MODEL_IR` stays at `schema_version: 2`. Section 2.4 argues that the
  discriminated `model` object is exactly the seam that makes a third architecture additive.
- **No change to `src/model_ir.align`.** Section 1.5 and section 3.1 record this as a result rather
  than a constraint: if implementation finds a required change, that is a falsification of
  R1B section 5.5 and is recorded as such, not worked around.
- **No layout plan, no residency tier, no prefetch policy.** Unchanged from R1B section 1.3. R1C
  observes that all 1,024 `ExpertBlock`s of the real model are non-contiguous (section 2.5.6) and
  takes no action on it; acting is R2 and R3.
- **No expert trace and no router observation.** R2A owns those. Section 2.9 records the one R2A
  precondition this model discharges (`n_expert_used = 8 > 6`) and stops there.
- **No packing of the real model in this capability's probes.** `--pack` accepts `olmoe` because
  leaving two of three dispatch sites two-way would silently derive a real olmoe file as qwen2; but
  a 3.92 GiB pack is not produced by any test or probe here. Section 4.4.
- **No tokenizer and no vocabulary materialization.** Unchanged; Request 22 stays unconsumed.
- **No interpretation of the MoE gating parameters.** Unchanged from R1B section 5.4. The model
  declares none of them anyway (section 2.1).
- **No architecture beyond `qwen2`, `gpt-oss`, and `olmoe`.**

### 1.4 Gate statement

The roadmap gate for R1 is *Model IR and Block IR can be produced*. R1 discharged the dense half and
R1B discharged the MoE half against a synthetic corpus only — its section 7 states plainly that
"the gpt-oss frontend is validated against the synthetic corpus and the two in-program oracles
only". R1C discharges the MoE half **against a real model**, in three parts:

1. `make model-ir-smoke` — the same self-contained owner, extended with the olmoe corpus.
2. The size-sum oracle and the claim-tiling oracle, computed in-program on the real file. Section
   4.3 records both as already passing at design time from the probe's own arithmetic.
3. `make model-ir-parity` against `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` — the roadmap gate's
   external check, which R1B could only record as `N/A`. Section 4.4 gives its expected values.

### 1.5 What this document's length is evidence for

`docs/specs/r1b-gptoss-moe-ir.md` section 5.5 claims that `BlockPlan` "is the surface that makes
each of them a table rather than a rewrite, and adding one should require no change to
`src/model_ir.align`". R1C is the first test of that claim, and the design outcome is:

| Module | R1B's change | R1C's change |
| --- | --- | --- |
| `src/gguf.align` | one geometry row, one name row | **none** |
| `src/model_ir.align` | created; owns every neutral mechanic | **none** — section 3.1 |
| `src/frontend_qwen.align` | reduced to qwen2 knowledge | **none** |
| `src/frontend_gpt_oss.align` | created | **none** |
| `src/frontend_olmoe.align` | — | created: one role table, one shape table, one plan builder |
| `src/main.align` | two-way dispatch at one site | one arm added at each of three sites |
| `src/alignpack.align` | twelve appended roles | two appended roles |
| `scripts/alignpack_reader.py` | mirrored | mirrored |

The claim holds **as stated** — `src/model_ir.align` needs no change — and holds with one
qualification the claim did not anticipate: the frozen `role_id` list of
`docs/specs/r4-alignpack-layer-major.md` is a **second seam**, and it is not free. It grows by
append, it is duplicated in a Python mirror, and a role the list does not name becomes
`0xFFFFFFFF` in a persisted pack rather than a compile error. That seam did not exist when R1B
section 5.5 was written. Section 2.5.2 states the appending rule; section 5.2 records what would
make it safer.

## 2. Public-contract ledger

### 2.1 Real-model evidence

Every value below is measured. The probe is out of tree and recorded in the pull request, following
the precedent `docs/specs/r1b-gptoss-moe-ir.md` section 2.8.2 sets:

```text
./main --inspect-gguf $HOME/models/OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf
llama-cli -v -m $HOME/models/OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf -n 0 -p x --no-warmup -ngl 0
```

built from this repository at the pinned toolchain, and llama.cpp `version: 0.2.0 (build 10566,
commit bb4caa754)` — the same reference build `scripts/run-model-ir-parity` already compares
against.

**Container.** GGUF v3, `tensor_count` 195, `metadata_kv_count` 28, `alignment` 32 (`default`),
`data_offset` 1,781,760, `file_size` 4,213,512,192. `metadata_end` 1,769,577,
`tensor_table_end` 1,781,729.

**The 28 metadata keys, complete and in file order:**

```text
general.architecture=olmoe   general.type=model   general.name=Open_Instruct_Dev
general.organization=Allenai   general.size_label=64x577M
olmoe.block_count=16   olmoe.context_length=4096   olmoe.embedding_length=2048
olmoe.feed_forward_length=1024   olmoe.attention.head_count=16
olmoe.attention.head_count_kv=16   olmoe.rope.freq_base=10000.0
olmoe.attention.layer_norm_rms_epsilon=1e-05
olmoe.expert_used_count=8   olmoe.expert_count=64
tokenizer.ggml.model=gpt2   tokenizer.ggml.pre=olmo
tokenizer.ggml.tokens[50304]   tokenizer.ggml.token_type[50304]   tokenizer.ggml.merges[50009]
tokenizer.ggml.bos_token_id=50279   tokenizer.ggml.eos_token_id=50279
tokenizer.ggml.padding_token_id=50280
tokenizer.ggml.add_bos_token=false   tokenizer.ggml.add_eos_token=false
tokenizer.chat_template   general.quantization_version=2   general.file_type=15
```

The absences are load-bearing and are each a *design input*, not an oversight:
`olmoe.attention.key_length` and `.value_length` are **absent**, so `head_dim` is derived;
`olmoe.expert_feed_forward_length` is **absent**, so `n_ff_exp` falls back to `n_ff`;
`olmoe.rope.dimension_count` is **absent**, so `rope.dim_count` is derived; and every
`attention.sliding_window*` key and every MoE-gating key is **absent**.

**The 195 tensors, complete, as twelve per-layer patterns plus three global ones.** `xN` is the
number of layers carrying that pattern; where two rows share a name they differ only in type.

| Name | `n_dims` | `dims` | Type | Count |
| --- | --- | --- | --- | --- |
| `token_embd.weight` | 2 | `[2048, 50304]` | Q4_K (12) | 1 |
| `output_norm.weight` | 1 | `[2048]` | F32 (0) | 1 |
| `output.weight` | 2 | `[2048, 50304]` | Q6_K (14) | 1 |
| `blk.N.attn_norm.weight` | 1 | `[2048]` | F32 | 16 |
| `blk.N.attn_q.weight` | 2 | `[2048, 2048]` | Q4_K | 16 |
| `blk.N.attn_q_norm.weight` | 1 | `[2048]` | F32 | 16 |
| `blk.N.attn_k.weight` | 2 | `[2048, 2048]` | Q4_K | 16 |
| `blk.N.attn_k_norm.weight` | 1 | `[2048]` | F32 | 16 |
| `blk.N.attn_v.weight` | 2 | `[2048, 2048]` | Q6_K | 8 |
| `blk.N.attn_v.weight` | 2 | `[2048, 2048]` | Q4_K | 8 |
| `blk.N.attn_output.weight` | 2 | `[2048, 2048]` | Q4_K | 16 |
| `blk.N.ffn_norm.weight` | 1 | `[2048]` | F32 | 16 |
| `blk.N.ffn_gate_inp.weight` | 2 | `[2048, 64]` | F32 | 16 |
| `blk.N.ffn_gate_exps.weight` | 3 | `[2048, 1024, 64]` | Q4_K | 16 |
| `blk.N.ffn_up_exps.weight` | 3 | `[2048, 1024, 64]` | Q4_K | 16 |
| `blk.N.ffn_down_exps.weight` | 3 | `[1024, 2048, 64]` | Q6_K | 8 |
| `blk.N.ffn_down_exps.weight` | 3 | `[1024, 2048, 64]` | Q4_K | 8 |

`3 + 16 * 12 = 195`. **There is no bias tensor of any kind in the file**, no `attn_sinks`, and no
fused `ffn_gate_up_exps`.

**`llama-cli -v` `print_info`, verbatim for every row the parity runner reads:**

```text
arch = olmoe          n_layer = 16          n_embd = 2048
n_head = 16           n_head_kv = 16        n_gqa = 1
n_rot = 128           n_embd_head_k = 128   n_embd_head_v = 128
n_ff = 1024           n_expert = 64         n_expert_used = 8
n_ctx_train = 4096    n_vocab = 50304       n_swa = 0
rope type = 2         freq_base_train = 10000.0
f_norm_rms_eps = 1.0e-05
file type = Q4_K - Medium   file size = 3.92 GiB (4.87 BPW)   model params = 6.92 B
llama_model_loader: - type  f32:   81 tensors
llama_model_loader: - type q4_K:   97 tensors
llama_model_loader: - type q6_K:   17 tensors
```

The reference build prints **no `n_ff_exp` row** for this architecture, which section 4.4 turns into
a row-set decision rather than a parse failure.

### 2.2 CLI surface and dispatch

Unchanged in grammar at all three verbs. `--model-ir MODEL_GGUF [MODEL_IR_JSON]`,
`--pack MODEL_GGUF PACK [DOC]`, and `--pack-verify MODEL_GGUF PACK [DOC]` keep their arity rules,
their `MAX_PATH_BYTES` guards, their byte-identical documents across forms, and their exit mappings.
There is no `--arch` flag, for the reason `docs/specs/r1b-gptoss-moe-ir.md` section 2.2 gives: the
file is the subject.

| `general.architecture` | Frontend |
| --- | --- |
| `"gpt-oss"` | `src/frontend_gpt_oss.align` |
| `"olmoe"` | `src/frontend_olmoe.align` |
| everything else, including absent, non-STRING, and non-UTF-8 | `src/frontend_qwen.align`, whose step-4 re-check produces `R1_UNSUPPORTED_ARCH` |

Each site becomes a three-way chain rather than a two-way `if`, keeping
`docs/specs/r1b-gptoss-moe-ir.md` section 7 item 2's rule intact: the qwen2 frontend is still the
fall-through, so every wrong-architecture document keeps the qwen2 `model` object and its sentinels
and no fixture's bytes change. **The observable behavior change is exactly one value**: a file
declaring `olmoe` stops producing `R1_UNSUPPORTED_ARCH` with detail `olmoe` and starts producing a
document. That is measured today:

```text
$ ./main --model-ir OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf
{"schema_version":2,...,"status":"error","error_code":"R1_UNSUPPORTED_ARCH","error_detail":"olmoe",...
```

The stdout summary block keeps its exact line set, order, and its `qwen model ir:` header, frozen by
`docs/specs/r1b-gptoss-moe-ir.md` section 7 item 10. On the real model its `blocks:` line reports
**1058**.

### 2.3 Module split — what moves

Nothing moves. The dependency direction of `docs/specs/r1b-gptoss-moe-ir.md` section 2.3.4 is
unchanged and gains one leaf:

```text
src/gguf.align              container + GgufTable + GGML geometry     (imports core.json, std.fs)
src/model_ir.align          BlockPlan -> Model IR + Block IR + document (imports gguf)
src/frontend_qwen.align     qwen2      hyperparameters -> BlockPlan     (imports gguf, model_ir)
src/frontend_gpt_oss.align  gpt-oss    hyperparameters -> BlockPlan     (imports gguf, model_ir)
src/frontend_olmoe.align    olmoe      hyperparameters -> BlockPlan     (imports gguf, model_ir)
src/main.align              three-way dispatch at three verbs          (imports three frontends)
```

`src/frontend_olmoe.align` exposes exactly the two public functions the other frontends expose and
nothing else:

```text
pub fn build_model_ir(borrow table: gguf.GgufTable, path: str) -> model_ir.ModelIr
pub fn prepare(borrow table: gguf.GgufTable) -> model_ir.Prepared
```

No frontend imports another. `src/model_ir.align` imports no frontend. The olmoe frontend copies
neither a byte-size computation, nor a coverage sweep, nor a JSON brace outside its own `model`
object — the same ownership assertion `docs/specs/r1b-gptoss-moe-ir.md` section 3.3 makes of the
qwen frontend, and the one that makes "a table, not a rewrite" checkable rather than rhetorical.

The six named thresholds (`MAX_LAYERS`, `MAX_EMBD`, `MAX_HEADS`, `MAX_FF`, `MAX_CONTEXT`,
`MAX_VOCAB`) plus `MAX_EXPERTS` (1,024) and `MAX_BLOCKS` (65,536) are declared in the olmoe frontend
with the same values `src/frontend_gpt_oss.align` uses. They are per-frontend by design: a threshold
is an architecture's own plausibility claim, and hoisting them into `src/model_ir.align` would make
the neutral module hold architecture knowledge. Section 5.2 records the alternative.

### 2.4 `R1_MODEL_IR` is unchanged at schema 2

R1C adds no field, removes none, reorders none, and retypes none. `schema_version` stays `2`.

This is the payoff of `docs/specs/r1b-gptoss-moe-ir.md` section 2.4.2's **discriminated `model`**
decision. `model.arch` is the discriminator and each frontend's field list is normative in its own
plan section, so a third architecture with a different field set is an *additional* normative list,
not a format change. Had R1B shipped the rejected union object carrying `null` for every
inapplicable field, olmoe would have needed `schema_version: 3` to drop `expert_ffn_layout`,
`sliding_window`, and `sliding_window_pattern` — fields it has no value for.

The neutral field set is untouched: top-level fields and order, `source`, `quant`, `coverage`, the
block record's field list and order, `blocks[].tensors[]`'s fourteen fields including
`claimed_absolute_offset` and `claimed_nbytes`, `role`, `dims` ordering, the escaping boundary, and
the `-1` / `null` sentinel rules.

The olmoe `model` object's field order is normative and is:

```text
arch, n_layer, n_embd, n_head, n_head_kv, head_dim, head_dim_source, n_ff, n_ff_exp,
n_ff_exp_source, n_vocab, n_expert, n_expert_used, context_length, rms_eps, rms_eps_bits, rope
```

with `rope` keeping R1's exact eight-field order. It is the gpt-oss list minus `expert_ffn_layout`,
`sliding_window`, and `sliding_window_pattern`. Each omission is argued rather than inherited:

- **`expert_ffn_layout` is omitted.** It exists in the gpt-oss object because no artifact settled
  whether that architecture ships split or fused expert projections, so the file's answer had to be
  reported. For olmoe the answer is measured: `ffn_gate_exps` and `ffn_up_exps` are both present and
  `ffn_gate_up_exps` is absent (section 2.1). Reporting a constant would be reporting nothing.
- **`sliding_window` and `sliding_window_pattern` are omitted.** Both keys are absent from the file
  and `n_swa` is `0` in the reference. A `null` field for a concept the architecture does not have
  is exactly the "report `n_expert_used: null` for a dense model as if the concept applied" mistake
  section 2.4.2 refuses.
- **`head_dim_source` and `n_ff_exp_source` are kept**, even though both read `"derived"` on this
  file, because both keys are architecture-generic in GGUF: llama.cpp reads `%s.attention.key_length`
  and `%s.expert_feed_forward_length` for any architecture, so a future olmoe-family file may
  declare either. The source marker is what lets a consumer tell a declared value from a derived one,
  and a fixture (`olmoe-headdim-metadata`) makes the `"metadata"` branch reachable.

### 2.5 The olmoe Model IR and Block IR

#### 2.5.1 Hyperparameters

| Field | Source key | Rule | Value on the real model |
| --- | --- | --- | --- |
| `arch` | `general.architecture` | Must be exactly `"olmoe"` | `olmoe` |
| `n_layer` | `olmoe.block_count` | Required `UINT32`, `[1, MAX_LAYERS]` | 16 |
| `n_embd` | `olmoe.embedding_length` | Required `UINT32`, `[1, MAX_EMBD]` | 2048 |
| `n_head` | `olmoe.attention.head_count` | Required `UINT32`, `[1, MAX_HEADS]` | 16 |
| `n_head_kv` | `olmoe.attention.head_count_kv` | Required `UINT32`, `[1, n_head]`, `n_head % n_head_kv == 0` | 16 |
| `head_dim` | `olmoe.attention.key_length` when present, else `n_embd / n_head` | `[1, MAX_EMBD]`; when present, `.value_length` must be present and equal; when derived, `n_embd % n_head == 0` | 128, `derived` |
| `head_dim_source` | derived | `"metadata"` or `"derived"` | `derived` |
| `n_ff` | `olmoe.feed_forward_length` | Required `UINT32`, `[1, MAX_FF]` | 1024 |
| `n_ff_exp` | `olmoe.expert_feed_forward_length` when present, else `n_ff` | `[1, MAX_FF]` | 1024, `derived` |
| `n_vocab` | `token_embd.weight` `dims[1]` | `[1, MAX_VOCAB]`, then cross-checked against `tokenizer.ggml.tokens` length | 50304 |
| `n_expert` | `olmoe.expert_count` | **Required** `UINT32`, `[1, MAX_EXPERTS]` | 64 |
| `n_expert_used` | `olmoe.expert_used_count` | **Required** `UINT32`, `[1, n_expert]` | 8 |
| `context_length` | `olmoe.context_length` | Required `UINT32`, `[1, MAX_CONTEXT]` | 4096 |
| `rms_eps` / `rms_eps_bits` | `olmoe.attention.layer_norm_rms_epsilon` | Required `FLOAT32`; R1's rendering and bits rule | 1e-05 |
| `rope.*` | the `olmoe.rope.*` keys | R1 section 2.5.3's rules, `rope.type` architecture-owned as NEOX (2), `type_source: "architecture"` | `freq_base` 10000.0; `dim_count` 128, `derived` |

Three derivations differ from gpt-oss and each is confirmed by the reference:

**`head_dim` is derived and the division is exact.** `2048 / 16 = 128`, which the reference
corroborates three ways: `n_rot = 128`, `n_embd_head_k = 128`, `n_embd_head_v = 128`. This is the
opposite of gpt-oss, where the division is wrong and the key must win — and it is why the rule is
*prefer the key, fall back to the division*, not *always divide* or *always read the key*. One rule
serves both architectures because both cases are now measured.

**`n_ff` is falsifiable here, unlike in gpt-oss.** `docs/specs/r1b-gptoss-moe-ir.md` section 4.1
records `n_ff` as gpt-oss's one hyperparameter "the step-10 shape contract cannot falsify", because
a pure-MoE layer has no dense feed-forward tensor and `n_ff_exp` was declared separately. On olmoe
`expert_feed_forward_length` is absent, so `n_ff_exp` **is** `n_ff`, and `n_ff` is asserted by every
stacked expert shape. A wrong `olmoe.feed_forward_length` is `R1_TENSOR_SHAPE_UNEXPECTED`, not an
unusable Model IR.

**`n_head == n_head_kv`, so olmoe is MHA, not GQA.** `n_gqa = 1` in the reference. Every attention
projection is `[n_embd, n_embd]`. Section 2.5.3 records the consequence for the QK-norm shape rule.

#### 2.5.2 Roles, and the two appended to the frozen list

Fifteen roles. Thirteen are spelled exactly as the qwen2 and gpt-oss frontends spell them, because a
consumer must not learn a second vocabulary for the same function. Two are new to the repository:

| Role label | GGUF name | `role_id` in `src/alignpack.align` |
| --- | --- | --- |
| `token_embd` | `token_embd.weight` | 12 (existing) |
| `attn_norm` | `blk.L.attn_norm.weight` | 0 (existing) |
| `attn_q` | `blk.L.attn_q.weight` | 1 (existing) |
| `attn_q_norm` | `blk.L.attn_q_norm.weight` | **27 (appended)** |
| `attn_k` | `blk.L.attn_k.weight` | 3 (existing) |
| `attn_k_norm` | `blk.L.attn_k_norm.weight` | **28 (appended)** |
| `attn_v` | `blk.L.attn_v.weight` | 5 (existing) |
| `attn_output` | `blk.L.attn_output.weight` | 7 (existing) |
| `ffn_norm` | `blk.L.ffn_norm.weight` | 8 (existing) |
| `router` | `blk.L.ffn_gate_inp.weight` | 17 (existing) |
| `ffn_gate_exps` | `blk.L.ffn_gate_exps.weight` | 19 (existing) |
| `ffn_up_exps` | `blk.L.ffn_up_exps.weight` | 21 (existing) |
| `ffn_down_exps` | `blk.L.ffn_down_exps.weight` | 23 (existing) |
| `output_norm` | `output_norm.weight` | 13 (existing) |
| `output` | `output.weight`, or `token_embd.weight` when absent | 14 (existing) |

**The appending rule.** `src/alignpack.align`'s `role_id` list is frozen at entries 0 to 26 and
travels in every `.alignpack` as a `u32` in the member record. New roles are **appended only**; an
existing index never moves, is never reused, and is never renumbered for tidiness. Entries 27 and 28
are added at the end, after `ffn_gate_up_exps_bias` (26), and `scripts/alignpack_reader.py`'s
`ROLES` list is extended in the same commit with the same two labels in the same order. The two
lists disagreeing is not a compile error in either language, which is why section 3.3 makes their
equality an asserted regression rather than an assumed one.

Without the append, both QK-norm members would pack as `DEFERRED_U32` — a *stated absence* that the
reader accepts. That is the failure this rule exists to prevent: a pack in which two of every
layer's seven attention members carry no role would be structurally valid, would round-trip, and
would be silently useless to R4.5.

**No bias role is declared, and no bias member is optional.** The file has no bias tensor, and
OLMoE's published configuration sets no attention or MLP bias. Declaring optional bias members that
no artifact names would add eight member slots that can never bind. A future olmoe-family file
carrying a bias therefore fails as `R1_UNASSIGNED_TENSOR` — the correct fail-closed outcome — and
admitting it is one row in `role_required` plus a fixture. This is the same evidence-driven
asymmetry `docs/specs/r1b-gptoss-moe-ir.md` section 7 item 15 settles for the fused gate-up bias,
applied in the direction the evidence points here.

**`output` keeps R1's tied-embedding rule** even though this model is untied (`output.weight` is
present and is `Q6_K` while `token_embd.weight` is `Q4_K`). The rule costs one optional lookup, it
is the one branch that produces the claim-tiling oracle's *whole-tensor-claimed-twice* case, and
`olmoe-tied` is a fixture for it.

#### 2.5.3 Block IR emission order and expected shapes

```text
index 0                                          WeightBlock     layer -1   token_embd
for L in 0 .. 15:
  index 1 + L * 66                               AttentionBlock  layer L
  index 2 + L * 66                               RouterBlock     layer L
  index 3 + L * 66 + e   (e = 0 .. 63)           ExpertBlock     layer L    expert e
index 1057                                       WeightBlock     layer -1   output_norm, output
```

`n_layer * (2 + n_expert) + 2` = **1058** blocks over 195 declared tensors and **3,219** block
tensor records (`1 + 16 * (7 + 2 + 64 * 3) + 2`). Emission order is fixed and is not file order.

| Block | Members (all required) |
| --- | --- |
| embedding `WeightBlock` | `token_embd` |
| `AttentionBlock` (layer L) | `attn_norm`, `attn_q`, `attn_q_norm`, `attn_k`, `attn_k_norm`, `attn_v`, `attn_output` — 7 |
| `RouterBlock` (layer L) | `ffn_norm`, `router` — 2 |
| `ExpertBlock` (layer L, expert e) | slice `e` of `ffn_gate_exps`, `ffn_up_exps`, `ffn_down_exps` — 3 |
| output `WeightBlock` | `output_norm`, `output` — 2 |

**`ffn_norm` belongs to the `RouterBlock`**, unchanged from `docs/specs/r1b-gptoss-moe-ir.md`
section 2.5.2 and for the same reason: it is applied once per token before routing, so attaching it
to any single expert would lie about when it is needed and duplicating it into all 64 would break
claim tiling. Section 2.5.6 shows the real file's byte layout independently supports the grouping.

**The QK-norm tensors go in the `AttentionBlock`**, beside the projection whose output they
normalize. They are per-layer attention state fetched with the attention weights, exactly as
`attn_sinks` is in the gpt-oss plan.

Expected shapes, asserted per member, yielding `R1_TENSOR_SHAPE_UNEXPECTED` on mismatch:

```text
token_embd.weight       [n_embd, n_vocab]                 output.weight       [n_embd, n_vocab]
output_norm.weight      [n_embd]                          attn_norm.weight    [n_embd]
ffn_norm.weight         [n_embd]
attn_q.weight           [n_embd, n_head * head_dim]
attn_k.weight           [n_embd, n_head_kv * head_dim]
attn_v.weight           [n_embd, n_head_kv * head_dim]
attn_output.weight      [n_head * head_dim, n_embd]
attn_q_norm.weight      [n_embd]                          attn_k_norm.weight  [n_embd]
ffn_gate_inp.weight     [n_embd, n_expert]
ffn_gate_exps.weight    [n_embd, n_ff_exp, n_expert]
ffn_up_exps.weight      [n_embd, n_ff_exp, n_expert]
ffn_down_exps.weight    [n_ff_exp, n_embd, n_expert]
```

**The QK-norm shape rule is `[n_embd]`, and the choice is under-determined by this model.** Both
tensors are measured `[2048]`, and OLMoE normalizes the whole projected query and key vector rather
than each head separately, so the extent is the full projection width. But three candidate rules —
`n_embd`, `n_head * head_dim`, and `n_head_kv * head_dim` — all evaluate to 2048 here, because
`n_head == n_head_kv == 16` and `head_dim == 128`. **The file cannot discriminate between them.**
`[n_embd]` is chosen because it is the same expression the three other `*_norm` roles already use,
so the shape table gains no new form, and because it is the only one of the three that stays correct
if a later olmoe-family file changes its head geometry without changing its normalization. The
residual risk is named in section 5.3: were a GQA olmoe-family file to make `attn_k_norm` narrower
than `n_embd`, it would be rejected. That is a rejection, not a mis-derivation, and it is recorded
rather than guarded against by a rule no available model justifies.

**The stacked-tensor rule and the router shape rule are inherited verbatim** from
`docs/specs/r1b-gptoss-moe-ir.md` section 2.5.2: a sliced member declares its expert axis as its
**last** declared axis with extent exactly `n_expert` (`n_dims == 3` here), and
`ffn_gate_inp.weight` must be `[n_embd, n_expert]`. Both hold on the real file:
`[2048, 1024, 64]` / `[1024, 2048, 64]` with `n_expert = 64`, and `[2048, 64]`.

**The axis order is the dense convention plus an expert axis, and it is the reverse of R1B's
assumption.** `src/frontend_qwen.align` expects the dense `ffn_gate` / `ffn_up` as `[n_embd, n_ff]`
and `ffn_down` as `[n_ff, n_embd]`. The measured olmoe stacked shapes are exactly those with
`n_expert` appended. `src/frontend_gpt_oss.align` expects the mirror image — `ffn_gate_exps` as
`[n_ff_exp, n_embd, n_expert]` and `ffn_down_exps` as `[n_embd, n_ff_exp, n_expert]` — which
contradicts its own repository's dense convention. Section 2.9 records this as evidence against a
gpt-oss row that remains ASSUMED; R1C does not change `src/frontend_gpt_oss.align`, because it has
no gpt-oss file and correcting an assumption with a different assumption is not progress.

#### 2.5.4 Slice arithmetic, on the real tensors

Unchanged from `docs/specs/r1b-gptoss-moe-ir.md` section 2.5.3, and reproduced here only with real
numbers so the pull request's oracle run is checkable by hand:

```text
row_bytes    = (d0 / block_size) * type_bytes
plane_bytes  = row_bytes * d1
claimed_absolute_offset = absolute_offset + plane_bytes * slice_index
claimed_nbytes          = plane_bytes
```

| Tensor | Type | `dims` | `row_bytes` | `plane_bytes` | `nbytes` |
| --- | --- | --- | --- | --- | --- |
| `blk.L.ffn_gate_exps.weight` | Q4_K (256/144) | `[2048, 1024, 64]` | `(2048/256)*144 = 1152` | `1152*1024 = 1,179,648` | 75,497,472 |
| `blk.L.ffn_up_exps.weight` | Q4_K | `[2048, 1024, 64]` | 1152 | 1,179,648 | 75,497,472 |
| `blk.L.ffn_down_exps.weight` (8 layers) | Q6_K (256/210) | `[1024, 2048, 64]` | `(1024/256)*210 = 840` | `840*2048 = 1,720,320` | 110,100,480 |
| `blk.L.ffn_down_exps.weight` (8 layers) | Q4_K | `[1024, 2048, 64]` | `(1024/256)*144 = 576` | `576*2048 = 1,179,648` | 75,497,472 |

`plane_bytes * 64 == nbytes` exactly in all four rows, so the claim-tiling oracle's positive side
holds structurally, as section 2.5.3 argues it must. The row rule governs `d0` in both axis orders:
`2048 % 256 == 0` and `1024 % 256 == 0`.

Worked example, expert 0 of layer 0:

```text
ffn_gate_exps  absolute_offset 264,894,464   claimed 264,894,464   claimed_nbytes 1,179,648
ffn_up_exps    absolute_offset 340,924,416   claimed 340,924,416   claimed_nbytes 1,179,648
ffn_down_exps  absolute_offset 154,793,984   claimed 154,793,984   claimed_nbytes 1,720,320
byte_size 4,079,616   first 154,793,984   end 342,104,064   contiguous false
```

#### 2.5.5 Per-layer mixed quantization is new, and nothing keys on role-to-type

Eight of sixteen layers carry `attn_v.weight` and `ffn_down_exps.weight` as `Q6_K` and eight as
`Q4_K` — layers 0, 1, 4, 7, 10, 13, 14, 15 are `Q6_K` — which is llama.cpp's ordinary `Q4_K_M`
mixed-precision scheme. **The same role has a different type in different layers.** Neither R1's nor
R1B's corpus contains that: both mix types *across* roles and keep each role uniform.

Nothing in the design keys a type to a role. `src/model_ir.align`'s `size_tensors` reads
`t.tensor_types[index]` per tensor; `member_claim` reads `g.nbytes[index]` per tensor; the
frontend's `expected_shape` returns extents and a `sliced` flag and no type at all. So mixed
per-layer types are already handled — but "already handled" without a regression is an assumption,
so section 4.1 makes the synthetic corpus reproduce the pattern (`olmoe-mixed-quant`).

The consequence is visible in the document and is worth stating, because a layout planner will meet
it: **two blocks of the same kind have different `byte_size`s.**

| Block | Layers 0, 1, 4, 7, 10, 13, 14, 15 | The other eight layers |
| --- | --- | --- |
| `AttentionBlock` | 10,543,104 | 9,461,760 |
| `ExpertBlock` (each) | 4,079,616 | 3,538,944 |

#### 2.5.6 What the real byte layout looks like

The file is **layer-major, alphabetical within a layer**: `output`, `output_norm`, `token_embd`,
then for each layer `attn_k`, `attn_k_norm`, `attn_norm`, `attn_output`, `attn_q`, `attn_q_norm`,
`attn_v`, `ffn_down_exps`, `ffn_gate_exps`, `ffn_gate_inp`, `ffn_norm`, `ffn_up_exps`. There is no
padding: the 195 tensors tile `[data_offset, file_size)` with zero inter-tensor gaps.

Two consequences fall out of the emission order of section 2.5.3, both computed from the probe and
neither designed for:

| Block kind | Count | `contiguous` |
| --- | --- | --- |
| `WeightBlock` (embedding, output) | 2 | true |
| `AttentionBlock` | 16 | true — the seven `attn_*` names sort together within the layer |
| `RouterBlock` | 16 | true — `ffn_gate_inp` and `ffn_norm` are adjacent in the alphabetical run |
| `ExpertBlock` | 1024 | **false** — three planes drawn from tensors tens of megabytes apart |

**34 of 1,058 blocks are contiguous, and every non-contiguous one is an `ExpertBlock`.** R1B section
5.1 predicted "a real MoE file's experts are almost certainly interleaved rather than grouped, which
`contiguous` will report"; this is that prediction measured. Loading one expert of one layer costs
three separated reads spanning 187 MB. R1C reports it and takes no action; the action is R4's
layer-major pack and R2/R3's residency policy.

That the `RouterBlock` grouping is also *byte*-contiguous is a coincidence of alphabetical ordering,
not a justification for the grouping, which rests on section 2.5.3's argument. It is recorded so
that a later measurement does not mistake it for a designed property.

### 2.6 Validation order and error codes

The order is `docs/specs/r1b-gptoss-moe-ir.md` section 2.6's, unchanged. The first applicable row
wins, tensors are examined in file order, and, **within a step**, metadata keys are examined in the
fixed order of the section 2.5.1 table. The step order below is what orders keys across steps: a
step-7 expert bound is reached only after every step-5 and step-6 row has passed, whatever the
section 2.5.1 table's row order says about the two keys involved. No document and no stdout is
produced before the derivation completes.

Steps 1 and 2 (`src/main.align`), 3 (`gguf.read_table`), 8 and 8b (geometry, stacked-tensor rule),
10 (block assembly), 11 (coverage and claim tiling), and 12 (size-sum oracle) are neutral and are
reached unchanged. The olmoe frontend owns steps 4 through 7 and 9:

4. Architecture re-check: exactly `"olmoe"`, else `R1_UNSUPPORTED_ARCH`.
5. Required metadata presence, then declared type, in R1's two sub-passes. The required set is the
   required `olmoe.*` keys of section 2.5.1; the optional set is `attention.key_length`,
   `attention.value_length`, `expert_feed_forward_length`, and the `rope.*` optionals.
6. Hyperparameter plausibility and derivation, including `head_dim` selection and every divisibility
   requirement.
7. Expert bounds and the block-explosion guard: `n_expert` in `[1, MAX_EXPERTS]`; `n_expert_used` in
   `[1, n_expert]`; `n_layer * (2 + n_expert) + 2 <= MAX_BLOCKS`, tested in non-wrapping form. The
   product has two operands, so the explosion detail names the extreme one — the operand that is the
   larger fraction of its own ceiling, `n_layer / MAX_LAYERS` against `n_expert / MAX_EXPERTS`,
   cross-multiplied — reporting `olmoe.block_count` or `olmoe.expert_count` accordingly, with a tie
   naming `olmoe.expert_count` (section 6 item 11).
9. `n_vocab` derivation, bound, and `tokenizer.ggml.tokens` cross-check.

**No new error code is introduced.** Every olmoe defect maps onto a row
`docs/specs/r1b-gptoss-moe-ir.md` section 2.6 already defines, with the key or tensor name as the
detail: `R1_UNSUPPORTED_ARCH`, `R1_MISSING_KEY`, `R1_KEY_TYPE_MISMATCH`, `R1_KEY_VALUE_IMPLAUSIBLE`,
`R1_MISSING_TENSOR`, `R1_TENSOR_SHAPE_UNEXPECTED`, `R1_TENSOR_SHAPE_UNALIGNED`,
`R1_DUPLICATE_TENSOR`, `R1_UNKNOWN_TENSOR_TYPE`, `R1_SIZE_OVERFLOW`, `R1_VOCAB_MISMATCH`,
`R1_UNASSIGNED_TENSOR`, `R1_BLOCK_CLAIM_MISMATCH`, `R1_SIZE_SUM_MISMATCH`, and `R1_GGUF_ERROR`. A
third architecture needing no new code is the same result section 1.5 records for
`src/model_ir.align`, in the error vocabulary rather than in the module graph.

`R1_BLOCK_CLAIM_MISMATCH` remains defensive and not input-reachable once steps 8 and 8b pass, for
the exactness reason of section 2.5.4. No fixture is invented for it.

### 2.7 Ownership, allocation, and owner modules

| Module | Owns | Imports |
| --- | --- | --- |
| `src/frontend_olmoe.align` | olmoe metadata keys, bounds, derivations, the fifteen-role table, the shape table, the olmoe `model` object, the olmoe `BlockPlan`, expert bounds, and the block-explosion guard | `gguf`, `model_ir` |
| `src/alignpack.align` | the frozen `role_id` list, gaining entries 27 and 28 | unchanged |
| `src/main.align` | three-way dispatch at three verbs | three frontends |
| `src/model_ir.align`, `src/gguf.align`, the other two frontends | unchanged | unchanged |

| Value | Owner | Allocation | Release |
| --- | --- | --- | --- |
| `GgufTable` | one local in `src/main.align` per invocation, borrowed into the frontend | unchanged from R1 | scope `Drop` |
| `BlockPlan` | built by the olmoe frontend, moved into `model_ir.Prepared` | three owned `string`s (`arch`, `model_json`, `names`), seventeen `array<i64>` columns each frozen once from an `array_builder<i64>`, sixteen scalars | scope `Drop` |
| `Geometry` | `model_ir.size_tensors`, called by the frontend after its step 7 | unchanged | scope `Drop` |
| final document | `builder` moved out by `to_string()` | one owned `string` | moved into `ModelIr.document` |

`BlockPlan` is the same 440-byte record, so `src/frontend_olmoe.align` becomes **the third frontend**
at which Request 23's spurious huge-struct-copy lint fires — not the third align-llm site, since the
register already carries `GgufTable`, `BlockPlan`, `TranscriptScan`, and `PackPlan`. That is
additional evidence for an already-`PROPOSED`, non-blocking request; it changes no status and creates
no new request. Section 5.4, and section 6 item 10 for the parameter and the exact sites the
implementation actually produced.

**Work stays bounded, and the real model is the first non-synthetic measurement of the bound.**
`model_ir.build` is `O(n log n)` in tensor count and `O(m log m)` in claim count. Here `n = 195` and
`m = 3,219`, against R1B's synthetic worst case of 530 blocks and 3,179 claims and R1's
50,015-tensor fixture. Both sit inside the existing 3-second `bounded-work` budget with wide margin.
The claim list's packing is unstressed: the slice ordinal reaches 63 against `CLAIM_SLOT_MASK`'s
2,047, and the tensor index reaches 194 against `NAME_INDEX_BITS`'s 2,097,151.

### 2.8 Ledger dimensions

| Dimension | Contract | Owner | Acceptance |
| --- | --- | --- | --- |
| Exact command/API | Section 2.2: three verbs, unchanged grammar, `olmoe` added to the dispatch on the container's own field. `pub fn build_model_ir(borrow table, path) -> model_ir.ModelIr` and `pub fn prepare(borrow table) -> model_ir.Prepared` in the new frontend; no other public surface, no alias, no flag | `src/main.align`, `src/frontend_olmoe.align` | `dispatch-olmoe`, `model-ir-smoke` CLI cases |
| Inputs and defaults | One model path; optional destination. `head_dim` defaults to `n_embd / n_head`; `n_ff_exp` defaults to `n_ff`; `rope.type` is architecture-owned; `output` falls back to `token_embd`. No ambient options, no environment input | `src/frontend_olmoe.align` | `olmoe-defaults`, `olmoe-headdim-metadata`, `olmoe-ffexp-present`, `olmoe-tied` |
| Results and errors | `Ok` + `status: "ok"`; `Ok` + `status: "error"` for every model defect; `Err` only for argument or OS failure. Section 2.6's table is complete, ordered, and adds no row | `src/frontend_olmoe.align`, `src/model_ir.align` | one fixture per reachable row |
| Multi-invalid precedence | Section 2.6 is strictly ordered; within a step, file order for tensors and section 2.5.1 order for keys | `src/frontend_olmoe.align` | `olmoe-precedence-key-shape`, `olmoe-precedence-expert-vocab` |
| Ownership and lifetime | Section 2.7. `BlockPlan` and the document are moved into their sole owners; no accessor returns a view derived from a `borrow` parameter | `src/frontend_olmoe.align` | `document-move`, ownership review |
| Allocation | Section 2.7's table; one `GgufTable`, one `Geometry`, one `BlockPlan`, one document per invocation | `src/frontend_olmoe.align` | `bytes_read` bound, `repeat-model-ir` |
| Bounded work | `O(n log n)` in tensors, `O(m log m)` in claims; unchanged bounds, first measured on a real MoE (195 tensors, 3,219 claims) | `src/model_ir.align` | `bounded-work`, extended with `olmoe-wide` |
| Owner module | Section 2.7. One architecture per frontend; one renderer for the format; one container reader | this document | `make check` (`check-per-unit`), import-graph review |
| Persisted/cache identity | The `role_id` list is persisted identity: it travels as a `u32` in every `.alignpack` member record. Entries 27 and 28 are **appended**; no existing index moves. Otherwise `N/A`: `R1_MODEL_IR` has no persisted form, no digest-addressed artifact, and no cache | `src/alignpack.align`, `scripts/alignpack_reader.py` | `role-list-mirror`; `pack-verify` round-trip on an olmoe fixture |
| Schema version | **Unchanged at `schema_version: 2`.** Section 2.4: the discriminated `model` object makes a third architecture an additional normative field list, not a format change. The olmoe list is normative and is asserted | `src/model_ir.align` | `field-order-olmoe`; a third `MODEL_ORDER` entry |
| Validation order | Section 2.6, deterministic and side-effect ordered; no output before derivation completes | `src/frontend_olmoe.align` | ordered malformed corpus, untouched-destination assertion |
| Prerequisites | The pinned `.align-revision` toolchain. No `PROPOSED` Align surface is consumed; Requests 21–24 remain `PROPOSED` and unconsumed. **No capability prerequisite**: unlike R1B, the real model is present and every ASSUMED row is already settled (section 2.1) | `src/frontend_olmoe.align` | `make check`, `make build` |
| Acceptance evidence | `model-ir-smoke` for correctness and the error corpus; the two in-program oracles on the real file; `model-ir-parity` against the real model — the first time this qualification is a PASS rather than an `N/A` for a MoE architecture | section 4 | sections 4.2, 4.3, 4.4 |
| Metrics | Primary: correctness — both oracles hold on every positive fixture and on the real model, and parity passes. Secondary: coverage (195 of 195 tensors, 1,058 blocks, 3,219 claims) and `bytes_read` (unchanged bound). **No performance claim**; section 4.5 | section 4.5 | oracle assertions, `bytes_read` bound |
| Text/wire boundary | Canonical UTF-8 JSON, declaration order, through `gguf.json_string`. Unchanged: a non-UTF-8 tensor name never reaches the document and surfaces as `R1_UNASSIGNED_TENSOR` | `src/model_ir.align` | `wire-escapes` over the olmoe corpus |
| Runtime-inspection fields | Every field is decoded from the file or derived by a stated formula from decoded values, except `rope.type` (architecture-owned) and the source markers `head_dim_source`, `n_ff_exp_source`. No reflection, no source read, no environment read | `src/frontend_olmoe.align` | producer-provenance review, `env-perturbation` |
| Platform scope | Platform-independent derivation; the container codec assumes a little-endian host, which Align already assumes. No target-local boundary changes, so this capability selects no platform profile | `src/frontend_olmoe.align` | no target-local claim |
| Milestone ordering | R1C consumes no R2, R3, R4, or R4.5 decision: no layout, no ordering, no residency tier, no prefetch policy, no trace. It emits per-expert byte ranges and `contiguous` as observations. Section 2.9 lists what it *supplies* to those slices | this document | section 5 |
| Normative examples | The shape table of section 2.5.3 and the arithmetic of section 2.5.4 are declarations, not positional calls. Unlike R1B's, their extents are **measured**, and section 4.3's oracle run is their check | this document | section 4.3 |

### 2.9 What R1B assumed, and what a real MoE settles

`docs/specs/r1b-gptoss-moe-ir.md` section 2.5 carries an assumption banner over every tensor name,
shape, and hyperparameter, and its section 7 records that no row was settled by real-model
inspection. R1C cannot settle a *gpt-oss* row — that still needs a gpt-oss file. What it settles is
the **generic MoE mechanics** R1B had to assume in order to design at all. Each row below names
what R1B assumed, what this model measures, and which downstream slice was waiting on it.

| Assumed mechanic | R1B's basis | Measured on OLMoE | Status |
| --- | --- | --- | --- |
| A MoE GGUF ships experts **stacked** in one tensor per projection, not one tensor per expert | llama.cpp `blk.%d.ffn_*_exps` name templates | `[2048, 1024, 64]`, `[1024, 2048, 64]` — one tensor per projection per layer, 64 experts stacked | **CONFIRMED** |
| The **expert axis is the last declared axis** | inference from GGML row-major layout | `dims[2] == 64 == n_expert` on all three stacked roles, all 16 layers | **CONFIRMED** |
| `plane_bytes * n_expert == nbytes` exactly, making claim tiling structural | arithmetic argument (section 2.5.3 consequence 1) | exact in all four type/shape combinations (section 2.5.4) | **CONFIRMED** |
| The router is `ffn_gate_inp.weight`, shaped `[n_embd, n_expert]` | llama.cpp name template | `[2048, 64]` F32, one per layer | **CONFIRMED** |
| `ffn_norm` is per layer and precedes routing, so it belongs to the `RouterBlock` | architectural argument | one `ffn_norm.weight` `[2048]` per layer; no per-expert norm | **CONFIRMED** |
| A router bias may be absent, so `router_bias` must be optional | absence of evidence (section 2.5.2) | absent | **CONFIRMED** — required would have rejected this file |
| The split expert biases (`ffn_{gate,up,down}_exps.bias`) are **required** members | llama.cpp's `ffn_gate(_exps)?.bias` quantization-exclusion regex | absent from a real split-layout MoE | **FALSIFIED as a generic rule.** The regex attests the *spelling*, never the *presence*. Section 5.3 |
| Stacked gate/up are `[n_ff_exp, n_embd, n_expert]` and down is `[n_embd, n_ff_exp, n_expert]` | assumption | the reverse: gate/up `[n_embd, n_ff_exp, n_expert]`, down `[n_ff_exp, n_embd, n_expert]` — the dense convention of `src/frontend_qwen.align` plus an expert axis | **CONTRADICTED for olmoe; the gpt-oss row stays ASSUMED.** Section 5.3 |
| One role has one type across layers | never stated, but every fixture assumed it | `attn_v` and `ffn_down_exps` are Q6_K in 8 layers and Q4_K in 8 | **NEW.** Handled by construction; section 2.5.5 makes it a regression |

Four downstream slices are unblocked by this, and naming them is how R1C avoids being a
documentation-only result:

1. **R4 (`.alignpack` layer-major), the per-expert half.** R4 lays out a `BlockPlan` without
   importing a frontend. Until now its only MoE input was synthetic. R1C gives it a 1,058-block,
   3,219-member plan from a real 3.92 GiB model, with 1,024 non-contiguous `ExpertBlock`s — which is
   precisely the layout pathology a layer-major pack exists to fix, and the first case where the
   improvement is measurable rather than argued.
2. **R4.5 (expert matmul).** It needs the byte range of one expert of one layer. Section 2.5.4
   supplies it, measured, with the two axis orders distinguished. The two appended QK-norm roles are
   a hard precondition here: without them R4.5 would read two of every seven attention members as
   `DEFERRED_U32`.
3. **R2A (`--expert-trace`), the `slots_truncated` branch.** `docs/specs/r2a-expert-trace.md` sets
   `moe.slots_truncated` to `true` when `n_expert_used > 6`, losing slot ids `3 .. n_expert_used-4`.
   OLMoE routes **top-8**, so it is the first real model that reaches the truncated branch; every
   existing exercise of it is synthetic. R1C does not implement or change the trace — it makes the
   branch reachable with a real model, and records that R2A's real-model qualification must assert
   `slots_truncated: true` rather than `false` when run against this file.
4. **R2 / R3 (residency and cache policy).** Per-expert `byte_size` values that differ by layer
   (section 2.5.5) and a 100 %-non-contiguous `ExpertBlock` population (section 2.5.6) are the two
   facts a residency planner and a cache simulator would otherwise have had to assume.

## 3. Closure matrix

Every applicable cell names its implementation owner and the exact regression that closes it. `N/A`
carries a concrete reason. Regression names are cases inside `scripts/run-model-ir-smoke` unless
another runner is named. Cells that R1 and R1B closed and R1C does not change are marked
**inherited** and are re-proved by re-running the existing corpora, not by new cases.

The matrix covers **two** modules with behavior changes (`src/frontend_olmoe.align`,
`src/alignpack.align`) plus one dispatch site set (`src/main.align`) and the verification graph.
`src/model_ir.align` and `src/gguf.align` have no cell because they have no change; section 3.1
states that as a claim to be falsified rather than an omission.

### 3.1 `src/model_ir.align` and `src/gguf.align` — the no-change claim

This is not an empty table. It is the section 1.5 test, and each row is a mechanic that could have
forced a change and does not.

| Mechanic R1C exercises | Why no change is needed | Falsification |
| --- | --- | --- |
| Block kinds `WeightBlock`, `AttentionBlock`, `RouterBlock`, `ExpertBlock` | all four are already rows of `block_kind_label`; `MlpBlock` is simply unused by this plan | a fifth kind would need a row |
| 3-axis stacked slice on the **other** axis order (`[n_embd, n_ff_exp, n_expert]`) | `member_claim` reads `d0` for the row rule and the last declared axis for the expert axis; it never names an axis semantically | an expert axis that was not last |
| 64 slice ordinals | `CLAIM_SLOT_MASK` is 2,047 | more than 2,048 experts, which `MAX_EXPERTS` (1,024) already excludes |
| 195 tensors, 1,058 blocks, 3,219 claims | `NAME_INDEX_BITS` 21; `MAX_BLOCKS` 65,536 | none within stated bounds |
| Same role, different type across layers | nothing in the neutral module maps a role to a type; `size_tensors` and `member_claim` are per tensor index | a type derived from a role |
| Optional member dropped when absent | `member_required` already drives it | none |
| Whole tensor claimed twice (tied embedding) | already the first branch of the tiling rule | none |
| Three GGML types, all already sized and named | `F32`, `Q4_K`, `Q6_K` are R0 rows | a new type id |
| A third `model` field list | `model_json` is an opaque owned `string` the frontend renders | a neutral renderer for `model` |

**If implementation changes either module, that is a falsification of
`docs/specs/r1b-gptoss-moe-ir.md` section 5.5** and is recorded as an implementation correction
naming the mechanic and why the seam did not cover it — not silently absorbed.

Everything else in both modules is **inherited** and re-proved by re-running the R0, R1, and R1B
corpora unchanged.

### 3.2 `src/frontend_olmoe.align`

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — plan | Every column is built once and frozen once; `block_count == n_layer * (2 + n_expert) + 2`; `member_count == 1 + n_layer * (7 + 2 + 3 * n_expert) + 2` | `prepare` epilogue | `olmoe-block-count` |
| Construction — result | `Prepared` and `ModelIr` are built with every field explicitly initialized, including the sentinels on a failed derivation | `prepare`, `build_model_ir` | `olmoe-ir-error-sentinels` on `olmoe-expert-zero` |
| Success — hyperparameters | Every section 2.5.1 field is read or derived by its stated rule | `read_hyperparameters` | `olmoe-model-fields` against generator-declared golden values |
| Success — `head_dim` | The division is the default and must be exact; a declared `attention.key_length` wins; `head_dim_source` reports which | `derive_shape` | `olmoe-defaults` (`derived`), `olmoe-headdim-metadata` (`metadata`, with the two rules disagreeing) |
| Success — `n_ff_exp` | Absent `expert_feed_forward_length` falls back to `n_ff` and is then asserted by every stacked shape | optional lookup | `olmoe-defaults` (`derived`), `olmoe-ffexp-present` (`metadata`, differing from `n_ff`) |
| Success — block plan | `AttentionBlock`, `RouterBlock`, and `n_expert` `ExpertBlock`s per layer in the section 2.5.3 order with the right kind, layer, expert, and roles; `ffn_norm` in the `RouterBlock`; both QK-norms in the `AttentionBlock` | `build_plan` | `olmoe-block-order`, `olmoe-block-roles` |
| Success — slice declaration | Exactly the three stacked members declare `slice_index` / `slice_count`; no other member does | `build_plan` | `olmoe-slice-declaration` |
| Success — QK-norm members | `attn_q_norm` and `attn_k_norm` are required members of every `AttentionBlock`, shaped `[n_embd]` | role table | `olmoe-block-roles`; `olmoe-qknorm-missing` for the negative |
| Success — mixed per-layer type | One role with two types across layers derives, sizes, and tiles correctly, and its blocks carry different `byte_size`s | none — neutral | `olmoe-mixed-quant` |
| Success — tied embedding | An absent `output.weight` binds `output` to `token_embd.weight`, claimed whole by two blocks | optional lookup | `olmoe-tied` |
| Failure — expert bounds | `n_expert` and `n_expert_used` outside their bounds are `R1_KEY_VALUE_IMPLAUSIBLE` with the key as the detail | step 7 | `olmoe-expert-zero`, `olmoe-expert-used-zero`, `olmoe-expert-used-high`, `olmoe-expert-huge` |
| Failure — block explosion | `n_layer * (2 + n_expert) + 2 > MAX_BLOCKS`, tested non-wrappingly; the detail names the extreme operand | step 7 | `olmoe-block-explosion`, `olmoe-block-explosion-layers` |
| Failure — `head_dim` indivisible | `n_embd % n_head != 0` with no declared key is `R1_KEY_VALUE_IMPLAUSIBLE`, and `n_head % n_head_kv != 0` is the earlier row | step 6 | `olmoe-headdim-indivisible` (`n_head = 3`, `n_head_kv = 1`) |
| Failure — stacked shape | A sliced member whose last axis is not `n_expert`, or whose dimension count is not 3, is `R1_TENSOR_SHAPE_UNEXPECTED` | step 8b | `olmoe-stacked-axis`, `olmoe-stacked-ndims` |
| Failure — transposed expert shape | Gate/up declared `[n_ff_exp, n_embd, n_expert]` — the gpt-oss order — is rejected, pinning section 2.5.3's axis-order decision as a contract rather than a comment | step 10 | `olmoe-stacked-transposed` |
| Failure — router shape | `ffn_gate_inp.weight` not `[n_embd, n_expert]` is `R1_TENSOR_SHAPE_UNEXPECTED` | step 10 | `olmoe-router-shape` |
| Failure — unexpected bias | A file carrying `blk.0.ffn_gate_exps.bias` is `R1_UNASSIGNED_TENSOR`, not silently ignored | step 11 | `olmoe-extra-bias` |
| Failure — wrong arch | A `qwen2` file reaching this frontend is `R1_UNSUPPORTED_ARCH` | step 4 re-check | `olmoe-wrong-arch` |
| Failure — precedence | A file with two defects reports the earlier row | ordered guards | `olmoe-precedence-key-shape`, `olmoe-precedence-expert-vocab` |
| Malformed | Invalid UTF-8 keys and names, duplicates, unknown types, truncation | `src/model_ir.align` | the R0 corpus re-run through `--model-ir` |
| Early exit | A failure at layer 1 of 2 leaves exactly the blocks completed before it | guard returns | `olmoe-ir-partial` |
| Loop joins | The layer, member, and expert loops terminate on count, on failure, and on a zero count | loop guards | `olmoe-zero-layer`, `olmoe-expert-zero` |
| Branch joins | `Ok` / `Error` status construction and the document return have one owner | `build_model_ir` return | `document-move`; both CLI forms byte-identical |
| Move-out | The document is moved into `ModelIr.document`; `BlockPlan` is moved into `Prepared` | epilogue | `document-move`; ownership review against `docs/specs/c8-speed-first.md` section 2.8 |
| Borrow discipline | No helper returns a view derived from a `borrow` parameter; every text result is owned | signatures | `make check` |
| Bounded work | Inside the existing 3-second budget at 64 experts | shared with `model_ir` | `olmoe-wide` |
| Generic monomorphization / shared state / concurrency | `N/A` with `docs/specs/r1b-gptoss-moe-ir.md` section 3.2's reasons: no generic is declared, no process-global state is held, the frontend is read-only over one borrowed table | `N/A` | `repeat-model-ir`, `env-perturbation` |
| Per-unit vs whole-program | Compiles identically imported and whole-program; appears as its own unit | module boundary | `make check` (`check-per-unit`), `make build` |

### 3.3 `src/alignpack.align` and `scripts/alignpack_reader.py` — the appended roles

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction | `role_id` gains exactly two rows, 27 and 28, at the end; no existing index moves | `role_id` | a case asserting the full 29-entry list by label and index |
| Success — mirror equality | The Align `role_id` list and the Python `ROLES` list name the same labels at the same indexes | both lists | `role-list-mirror`: the runner extracts both and compares, so a one-sided edit fails |
| Success — round trip | An olmoe pack's QK-norm members carry `role_id` 27 and 28 and the reader resolves them to the document's `role` strings | `pack`, `pack-verify` | `pack-olmoe`: an olmoe fixture through `--pack` and `--pack-verify` |
| Failure — unnamed role | A role the list does not name packs as `DEFERRED_U32` and the reader accepts it as a stated absence | unchanged | inherited; unchanged behavior |
| Bounded work | `MAX_BLOCKS` in `src/alignpack.align` is 1,048,576; an olmoe plan is 1,058 blocks | unchanged | `pack-olmoe` |
| Everything else | **inherited** from `docs/specs/r4-alignpack-layer-major.md` | unchanged | the R4 corpus re-run |

### 3.4 `src/main.align` — three-way dispatch at three verbs

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — dispatch | The architecture is read once from `gguf.read_table`'s own field before any frontend is entered; the table is read exactly once per invocation, at each of the three verbs | `model_ir_demo`, `pack_demo`, `pack_verify_demo` | `dispatch-single-read`: `bytes_read` numerically unchanged on the qwen and gpt-oss corpora |
| Success — three architectures | A qwen2 file reaches the qwen frontend, a gpt-oss file the gpt-oss frontend, an olmoe file the olmoe frontend, at every verb | all three arms | `dispatch-qwen`, `dispatch-gptoss`, `dispatch-olmoe`; `pack-olmoe` |
| Failure — unknown architecture | Anything else still falls through to the qwen2 frontend and yields `R1_UNSUPPORTED_ARCH` with the architecture or `""` as the detail; no wrong-architecture document's bytes change | fall-through arm | `dispatch-unknown`, `qwen2-wrong-arch`, `qwen2-arch-escapes`, the R0 positive corpus |
| Arm consistency | The three sites select the same frontend for the same architecture; a two-way site would silently derive an olmoe file as qwen2 | all three arms | a case asserting `--model-ir` and `--pack-verify` report the same `model.arch` and block count for one olmoe fixture |
| Byte identity across forms | Both CLI forms emit identical document bytes for the olmoe corpus | `model_ir_demo` | `form-parity` over all four corpora |
| Summary block | The line set, order, and the `qwen model ir:` header are unchanged; `blocks:` reports the assembled count | unchanged | `summary-order`, `summary-control-bytes` |
| Failure mapping | `status: "error"` becomes `Err(Error.Invalid)` after the document is emitted | epilogue | `error-corpus` |
| Everything else | **inherited**: arity, path validation, OS failure, early exit, unknown selector, environment isolation, help text | unchanged | the R1 and R4 CLI cases re-run |

### 3.5 `Makefile` and `scripts/` — build and verification graph

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Target definition | **No new target.** `model-ir-smoke`, `model-ir-parity`, and the R4 pack targets keep their names, dependencies, and aggregate membership; the new module is reached through `check-per-unit $(ENTRY)`, which follows imports and enumerates no source | `Makefile` unchanged | `python3 scripts/check-gate-topology` reports no change |
| Aggregate membership | `model-ir-smoke` stays in `HOSTED_CHECK_TARGETS`: still no model, no network, no reference tool, still seconds | `Makefile` unchanged | `make gate-topology-check` |
| Qualification exclusion | `model-ir-parity` stays outside every aggregate | `Makefile` unchanged | `make gate-topology-check` |
| Preflight profile selection | The `Makefile` is **not** modified, so `FRESH_IMAGE_PATTERNS` does not match and the classifier selects ordinary executable preflight. `python3 scripts/pre-pr --plan` confirms this before the run and is recorded | `scripts/pre-pr` | `--plan` output in the pull request |
| Fixture generation | `scripts/gguf_fixture.py` gains `OlmoeModel` and still writes only into a caller-supplied temporary tree | `scripts/gguf_fixture.py` | the runner's repository leak sweep |
| Fixture independence | The generator derives no value from `src/`; every expected claim is computed in Python | `scripts/gguf_fixture.py` | code review; the import list is unchanged |
| Generator compatibility | Every existing R0, R1, and R1B fixture is **byte-unchanged**: no geometry row is added, so no slot in `GEOMETRY_TYPES` moves | `scripts/gguf_fixture.py` | `make gguf-smoke` before and after; the existing manifests compared |
| Parity arch dispatch | The runner selects its comparison row set from the `model.arch` of the document under test; a third row set joins the two existing ones and the synthetic row-set unit gains a `UNIT_OLMOE` | `scripts/run-model-ir-parity` | the in-runner synthetic row-set unit, extended |
| Parity skip | An unset `ALIGN_LLM_GGUF_MODEL` or `ALIGN_LLM_LLAMA_CLI` prints one exact `N/A` line and exits 0; a parse failure fails closed | `scripts/run-model-ir-parity` | unchanged cases plus the olmoe row set |
| Cleanup | Every fixture path is removed by the `trap` on `EXIT`; the last assertion is that the temp root is still present | `scripts/run-model-ir-smoke` | unchanged shape |
| Documentation | `docs/specs/roadmap.md` section R1 and `HANDOFF.md` name this document; `docs/align-requests.md` Request 23 receives a third client site | integration commit | out of scope for this design-only file; section 5.4 |

## 4. Fixture and qualification design

### 4.1 `scripts/gguf_fixture.py` — the olmoe corpus

The generator is extended, not replaced. A new `OlmoeModel` class mirrors `GptOssModel`'s structure
exactly: `entries` in file order, a contiguous aligned data layout, an oracle assertion before
writing, and `positive()` returning the full expected document including every per-expert claim.
**`GGML_GEOMETRY` and `GEOMETRY_TYPES` are untouched**, so no existing fixture's bytes change — the
one thing R1B could not promise and had to except (`qwen2-geometry`).

**The positive fixture `olmoe-full.gguf`** is a complete, valid v3 container well under 1 MiB whose
extents keep every byte size, and for a sliced tensor every **plane**, a multiple of the 32-byte
container alignment — the constraint `docs/specs/r1-qwen-model-ir.md` section 7 item 5 records:

```text
n_layer 2   n_embd 256   n_head 8   n_head_kv 8   n_ff 64   n_expert 8   n_expert_used 3
n_vocab 32  context_length 512      (no key_length, no expert_feed_forward_length)
```

`head_dim` is `256 / 8 = 32`, `head_dim_source: "derived"`; `n_ff_exp` is `64`,
`n_ff_exp_source: "derived"`. It deliberately mirrors the real model's shape *relationships* rather
than its extents: MHA (`n_head == n_head_kv`), no declared `key_length`, no declared
`expert_feed_forward_length`, and no bias of any kind.

Block count is `2 * (2 + 8) + 2 = 22`; tensor count is `3 + 2 * 12 = 27`; claim count is
`1 + 2 * (7 + 2 + 8 * 3) + 2 = 69`.

| Tensor | Type | Shape | `row_bytes` | `plane_bytes` | `nbytes` |
| --- | --- | --- | --- | --- | --- |
| `ffn_gate_exps.weight`, `ffn_up_exps.weight` | Q4_K | `[256, 64, 8]` | `(256/256)*144 = 144` | `144 * 64 = 9,216` | 73,728 |
| `ffn_down_exps.weight` | Q6_K | `[64, 256, 8]` | — | — | — |

`64 % 256 != 0`, so a Q6_K `[64, 256, 8]` is `R1_TENSOR_SHAPE_UNALIGNED` — the row rule bites at
these extents. `ffn_down_exps` is therefore `F32` in the base fixture
(`row_bytes = 256`, `plane_bytes = 256 * 256 = 65,536`, `nbytes = 524,288`), and the mixed-type
pattern that matters is carried by its own fixture below rather than forced into the base one. This
is the same accommodation `docs/specs/r1b-gptoss-moe-ir.md` section 7 item 8 makes for MXFP4, and it
is recorded here rather than discovered during implementation.

`ffn_gate_inp.weight` is `[256, 8]` F32 (8,192 bytes); the norms and both QK-norms are `[256]` F32
(1,024 bytes each); `attn_q` / `attn_k` / `token_embd` are `Q4_K`; `attn_v` / `output` are `Q6_K`;
`attn_output` is `Q8_0` — four ascending `quant.type_counts` rows (ids 0, 8, 12, 14).

Further positive variants:

| Fixture | What it pins |
| --- | --- |
| `olmoe-headdim-metadata` | `attention.key_length` and `.value_length` both `64` against a division of `32`, so the two rules **must** disagree; `head_dim_source: "metadata"` and every attention width widens |
| `olmoe-ffexp-present` | `expert_feed_forward_length = 32` against `n_ff = 64`; `n_ff_exp_source: "metadata"` and every stacked shape narrows, so a frontend that ignored the key would fail |
| `olmoe-mixed-quant` | `ffn_down_exps` and `attn_v` are `Q6_K` in layer 0 and `Q4_K` in layer 1 — the real model's pattern at fixture scale; asserts the two layers' `ExpertBlock` and `AttentionBlock` `byte_size`s differ |
| `olmoe-tied` | no `output.weight`; the tied rule and the whole-tensor-claimed-twice branch of the tiling oracle |
| `olmoe-permuted` | the data section grouped by role across layers, so an `AttentionBlock` and a `RouterBlock` are also non-contiguous while both oracles still hold |
| `olmoe-wide` | 4 layers, 64 experts — 266 blocks, 807 claims — inside the `bounded-work` budget, with F32 everywhere but the expert weights so the file stays small |

**The negative corpus** adds one file per reachable row:

| Fixture | Defect | Expected |
| --- | --- | --- |
| `olmoe-expert-zero` | `olmoe.expert_count = 0` | `R1_KEY_VALUE_IMPLAUSIBLE`, detail `olmoe.expert_count` |
| `olmoe-expert-huge` | `olmoe.expert_count = 4096` | `R1_KEY_VALUE_IMPLAUSIBLE` |
| `olmoe-expert-missing` | no `olmoe.expert_count` | `R1_MISSING_KEY` |
| `olmoe-expert-type` | `olmoe.expert_count` as `STRING` | `R1_KEY_TYPE_MISMATCH` |
| `olmoe-expert-used-zero` | `expert_used_count = 0` | `R1_KEY_VALUE_IMPLAUSIBLE` |
| `olmoe-expert-used-high` | `expert_used_count = n_expert + 1` | `R1_KEY_VALUE_IMPLAUSIBLE` |
| `olmoe-block-explosion` | `n_layer = 512`, `n_expert = 1024` | `R1_KEY_VALUE_IMPLAUSIBLE`, detail `olmoe.expert_count` — both operands at their ceilings, so the extreme-operand tie-break takes its default |
| `olmoe-block-explosion-layers` | `n_layer = 512`, `n_expert = 128` | `R1_KEY_VALUE_IMPLAUSIBLE`, detail `olmoe.block_count` — the layer count is at its ceiling and the expert count is an eighth of its own, so the layer count is the extreme operand |
| `olmoe-headdim-indivisible` | `n_head = 3`, `n_head_kv = 1`, no `key_length` | `R1_KEY_VALUE_IMPLAUSIBLE`, detail `olmoe.attention.head_count` |
| `olmoe-keylength-mismatch` | `key_length = 64`, `value_length = 32` | `R1_KEY_VALUE_IMPLAUSIBLE`, detail `olmoe.attention.value_length` |
| `olmoe-stacked-axis` | `ffn_gate_exps.weight` `[256, 64, 4]` against `n_expert = 8` | `R1_TENSOR_SHAPE_UNEXPECTED` |
| `olmoe-stacked-ndims` | `ffn_gate_exps.weight` declared 2-axis as `[256, 64]` | `R1_TENSOR_SHAPE_UNEXPECTED` |
| `olmoe-stacked-transposed` | `ffn_gate_exps.weight` `[64, 256, 8]` — the gpt-oss axis order | `R1_TENSOR_SHAPE_UNEXPECTED` |
| `olmoe-router-shape` | `ffn_gate_inp.weight` `[256, 4]` against `n_expert = 8` | `R1_TENSOR_SHAPE_UNEXPECTED` |
| `olmoe-qknorm-missing` | no `blk.0.attn_q_norm.weight` | `R1_MISSING_TENSOR`, detail `blk.0.attn_q_norm.weight` |
| `olmoe-qknorm-shape` | `attn_k_norm.weight` `[128]` against `n_embd = 256` | `R1_TENSOR_SHAPE_UNEXPECTED` |
| `olmoe-extra-bias` | an extra `blk.0.ffn_gate_exps.bias` | `R1_UNASSIGNED_TENSOR` |
| `olmoe-wrong-arch` | `general.architecture = "qwen2"` in an olmoe-shaped file | derives as qwen2 and fails on the qwen2 key set: `R1_MISSING_KEY`, detail `qwen2.block_count` |
| `olmoe-size-sum` | 64 trailing bytes past the data section | `R1_SIZE_SUM_MISMATCH` |
| `olmoe-zero-layer` | `olmoe.block_count = 0` | `R1_KEY_VALUE_IMPLAUSIBLE` |
| `olmoe-precedence-key-shape` | a mistyped key and a wrong stacked shape | the key row |
| `olmoe-precedence-expert-vocab` | an out-of-bounds `expert_used_count` and a zero vocabulary | the expert row |

### 4.2 Owner — `scripts/run-model-ir-smoke`, `make model-ir-smoke`

**One runner, extended.** The olmoe corpus is a new `model_ir_olmoe_cases` list in the manifest, so
`run-gguf-smoke` keeps driving exactly the R0 cases and `run-model-ir-smoke` drives all four lists.
A second `make` target is rejected for `CLAUDE.md`'s reason: the consumer surface is the same CLI,
the fixtures share a generator, and there is no distinct failure domain.

Beyond the closure cells of section 3, the runner:

- adds a third `MODEL_ORDER` entry, `"olmoe"`, and keeps selecting by `document["model"]["arch"]`;
- asserts `schema_version == 2` and the unchanged fourteen-field `BLOCK_TENSOR_ORDER` on every
  olmoe document;
- recomputes every `claimed_absolute_offset` / `claimed_nbytes` from the generator's own layout
  rather than trusting the document's internal consistency;
- performs the claim-tiling assertion in Python independently of the Align one;
- adds `role-list-mirror`, which extracts the label sequence from `src/alignpack.align`'s `role_id`
  and from `scripts/alignpack_reader.py`'s `ROLES` and requires equality — the one guard that makes
  the two-language frozen list of section 2.5.2 safe to append to;
- re-runs the entire R0, R1, and R1B corpora unchanged, with no case removed and no fixture's bytes
  altered;
- keeps the repository leak sweep, temp-root assertion, descriptor budget, `env-perturbation`,
  `repeat-model-ir`, and both CLI forms.

### 4.3 The two in-program oracles, on the real model

Both are computed in-program on any input. Their values on
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` are already known from the probe and are recorded here so
the implementation run is a confirmation rather than a discovery.

**Size-sum oracle** — `data_offset + Σ_{t in tensor table} nbytes(t) == file_size`:

```text
data_offset                1,781,760
Σ nbytes (195 tensors) 4,211,730,432
sum                    4,213,512,192
file_size              4,213,512,192      MATCH
```

The sum is over the tensor table, not over block membership, so per-expert blocks change nothing
about it and the tied-embedding case still counts a shared tensor once. The independent
`--inspect-gguf` walk additionally shows **zero inter-tensor gaps**, so the data section is exactly
tiled and the last tensor ends at `file_size`.

**Claim-tiling oracle** — for every tensor, either one claim is the whole tensor or the distinct
claims tile `[absolute_offset, absolute_offset + nbytes)` with no gap and no overlap. On the real
model 147 tensors take the whole-tensor branch and 48 (the three stacked roles across 16 layers)
take the tiling branch, each with exactly 64 claims of `nbytes / 64` bytes. Section 2.5.4 shows the
division is exact in all four type/shape combinations.

**Coverage**: `assigned_tensor_count == tensor_count == 195`, `unassigned_tensors` empty, over
1,058 blocks and 3,219 claims. `quant.type_counts` is `F32` 81, `Q4_K` 97, `Q6_K` 17 — which
section 4.4 cross-checks against the reference loader's own census.

### 4.4 Focused qualification — `scripts/run-model-ir-parity`

The runner keeps its shape: opt-in, never in an aggregate, never in CI, both inputs required and
explicitly skippable with no default, a hard failure on a nonzero reference exit, a fail-closed
parser, and the `-st` / `</dev/null` / `timeout` / `ulimit -f` wrappers. It reads `model.arch` from
the document it just produced and selects the comparison row set, so `ALIGN_LLM_GGUF_MODEL` serves
all three architectures and there is no second environment variable.

**Unlike R1B's, this qualification is runnable today.** The model is present, it is 3.92 GiB, and
the reference build is installed. Expected values, measured in section 2.1:

| Model IR field | `print_info` key | Expected | Comparison |
| --- | --- | --- | --- |
| `model.arch` | `arch` | `olmoe` | string equality |
| `model.n_layer` | `n_layer` | 16 | integer |
| `model.n_embd` | `n_embd` | 2048 | integer |
| `model.n_head` | `n_head` | 16 | integer |
| `model.n_head_kv` | `n_head_kv` | 16 | integer |
| `model.head_dim` | `n_embd_head_k` | 128 | integer |
| `model.head_dim` | `n_embd_head_v` | 128 | integer |
| `model.n_ff` | `n_ff` | 1024 | integer |
| `model.n_expert` | `n_expert` | 64 | integer |
| `model.n_vocab` | `n_vocab` | 50304 | integer |
| `model.context_length` | `n_ctx_train` | 4096 | integer |
| `model.rope.type` | `rope type` | 2 | integer |
| `model.rope.freq_base_bits` | `freq_base_train` | `10000.0` | `%.1f` of the unpacked f32 |
| `model.rms_eps_bits` | `f_norm_rms_eps` | `1.0e-05` | `%.1e` of the unpacked f32 |
| `model.n_expert_used` | `n_expert_used` | 8 | integer |

plus the loader's type census, which must be `f32: 81`, `q4_K: 97`, `q6_K: 17` against
`quant.type_counts`.

**The olmoe row set is the shared set plus `n_expert_used` only, and the two omissions are
decisions, not oversights.** The reference build prints **no `n_ff_exp` row** for this
architecture — llama.cpp reads `%s.expert_feed_forward_length` only where an architecture declares
it, and olmoe does not — so a row for it would be an unconditional `parity: UNPARSED n_ff_exp`. And
`n_swa` prints `0`, which is llama.cpp's default for an architecture with no sliding window rather
than a value this file declares; the olmoe `model` object has no `sliding_window` field, so there
is nothing to compare. Both omissions are recorded as notes by the runner, never as silent drops,
following the `sliding_window is null` precedent.

`build_rows`'s per-architecture extension therefore stops being `if arch == "gpt-oss"` and becomes a
lookup with three entries. Its synthetic row-set unit gains `UNIT_OLMOE` and asserts that the olmoe
extension is exactly `["n_expert_used"]`, that it does not contain `n_ff_exp` or `n_swa`, and that
it extends the shared set — the same three assertions the gpt-oss set already carries, so a row
leaking between architectures fails on a host with no model at all.

**One parser risk is recorded rather than discovered.** `docs/specs/r1b-gptoss-moe-ir.md`
section 4.4 notes that `n_head` and `n_head_kv` print with `%s` in this build, so an architecture
with per-layer head counts may print a list. Olmoe prints plain scalars (`n_head = 16`,
`n_head_kv = 16`), so the risk does not materialize here; the runner must still fail closed with
`parity: UNPARSED n_head` rather than coerce, which is the existing contract.

**Packing the real model is out of scope for this qualification.** `--pack` accepts `olmoe`
(section 2.2) and `pack-olmoe` exercises it on a fixture, but a 3.92 GiB source producing a pack of
comparable size is not run by any test or probe here: the host has roughly 16 GiB free and the
capability makes no claim that needs it. The real-model pack belongs to whichever R4 or R4.5
capability measures the layout improvement section 2.9 item 1 describes.

### 4.5 Metrics

**Primary — correctness.** Three pass/fail measurements: the size-sum oracle and the claim-tiling
oracle hold on every positive fixture *and on the real model*; and the parity comparison passes
against the real model. None is a speed metric. The third is the one R1B could only record as `N/A`.

**Secondary — coverage.** `assigned_tensor_count == tensor_count` with `unassigned_tensors` empty:
27 of 27 over 22 blocks and 69 claims on `olmoe-full`, and **195 of 195 over 1,058 blocks and 3,219
claims on the real model**.

**Secondary — `bytes_read`.** Inherited unchanged and re-asserted, because a third dispatch arm at
three verbs adds code paths that could start reading more:
`bytes_read < data_offset + WINDOW_BYTES`, with `dispatch-single-read` asserting the qwen and
gpt-oss values are numerically unchanged. On the real model `bytes_read` is 2,097,152 — **two**
windows of `WINDOW_BYTES` (1,048,576) each, because `data_offset` (1,781,760) is past the end of the
first one and the walk stops at the first window boundary at or beyond it. The general rule is that
`bytes_read` is that boundary, capped by the file size; the one-window case of section 6 item 1 is
the special case where `data_offset` happens to fall inside the first window.

**R1C makes no performance claim.** The document grows to 1,058 blocks on the real model and the
derivation does more work; no baseline is established and no threshold is asserted. `bounded-work`
remains a complexity guard, not a performance target. Under `CLAUDE.md` a speed claim would require
a reproducible benchmark and a named baseline, and R1C has neither. The one number worth recording
without a claim attached is section 2.5.6's: 1,024 of 1,058 blocks are non-contiguous, which is a
*measurement of the input*, not of this program.

## 5. Deferred surfaces

### 5.1 Layout, residency, prefetch, and the real-model pack — R2, R3, R4

R1C defines no `.alignpack` layout policy, no reordering, no residency tier, no eviction rule, and
no prefetch plan. It observes the current layout — including that every `ExpertBlock` of the real
model is non-contiguous and that a single expert's three planes span 187 MB — and takes no action.
Producing and measuring a layer-major pack of this model is the first R4 capability with a real MoE
input; section 2.9 item 1 names it, section 4.4 records why it is not run here.

### 5.2 Hoisting the per-frontend thresholds and the frozen role list

Three frontends now declare the same eight `MAX_*` constants, and two declare `MAX_EXPERTS` and
`MAX_BLOCKS` identically. Hoisting them into `src/model_ir.align` would remove the duplication and
would put an architecture's own plausibility claim into the neutral module, which is the boundary
section 2.3 exists to protect. Deferred until a fourth frontend makes the duplication cost real, and
recorded so the choice is visible rather than accidental.

The frozen `role_id` list is the sharper case. Section 1.5 records that it is a second seam
`docs/specs/r1b-gptoss-moe-ir.md` section 5.5 did not anticipate: it is duplicated across Align and
Python, a missing entry degrades silently to `DEFERRED_U32` in a persisted artifact, and it grows
every time an architecture introduces a tensor function the repository has not seen.
`role-list-mirror` (section 4.2) makes the duplication safe; making the *omission* loud — a frontend
supplying a label the list does not name failing at pack time rather than packing a sentinel — is a
change to `docs/specs/r4-alignpack-layer-major.md`'s contract and belongs to R4, not here.

### 5.3 The two rows this model contradicts rather than confirms

Section 2.9 records both; neither is repaired here, and the reason is the same in both cases:
correcting an assumption with a different assumption is not progress.

- **The gpt-oss stacked axis order.** `src/frontend_gpt_oss.align` expects gate/up as
  `[n_ff_exp, n_embd, n_expert]`; the dense convention in this repository and the measured olmoe
  layout are both the reverse. R1C does not change the gpt-oss frontend, because no gpt-oss file is
  present to settle it. What R1C adds is that the assumption is now *contradicted by the only real
  MoE evidence available*, which raises the priority of R1B's own section 4.5 inspection
  prerequisite from "before merge" to "before the gpt-oss frontend is trusted on a real file". The
  `olmoe-stacked-transposed` fixture pins the olmoe direction so the two cannot drift into
  agreement by accident.
- **The required split expert biases.** R1B requires `ffn_{gate,up,down}_exps.bias` in its split
  variant on the strength of a quantization-exclusion regex. The regex attests a spelling, not a
  presence, and a real split-layout MoE has none. The olmoe frontend declares no bias role at all
  (section 2.5.2). Whether gpt-oss's should become optional is a gpt-oss question that its own
  real-model inspection answers.

### 5.4 Align capability requests

No `PROPOSED` surface is consumed and no new genuine Align gap is expected: every operation is
`i64` arithmetic, owned-`string` slicing, and `array<i64>` indexing over surfaces R1 and R1B already
proved at this pin. `src/frontend_olmoe.align` becomes **the third frontend** at which Request 23's
spurious huge-struct-copy lint fires — the register's client count is already four (`GgufTable`,
`BlockPlan`, `TranscriptScan`, `PackPlan`), so "third" counts frontends, not sites — predicted here
on a `borrow BlockPlan` parameter and shipped on `borrow GgufTable` ones (section 6 item 10). That is
additional client evidence for an already-`PROPOSED`, non-blocking request, recorded in
`docs/align-requests.md` by the review-repair commit, and it changes no status. Request 22's
migration note applies to the olmoe plan unchanged, for the same reason it applies to `GgufTable` and
`BlockPlan`: the plan is a stream-plus-columns record precisely so that no `array<string>` is
indexed.

If implementation discovers a genuine gap, it is classified under `CLAUDE.md`'s
Align-capability-request rules before any workaround is written.

### 5.5 Other MoE architectures, and what R1C says about the next one

`qwen3moe`, `deepseek2`, and `mixtral` remain separate frontends under section 2.3's naming
convention, each with its own plan section. R1C is the evidence that
`docs/specs/r1b-gptoss-moe-ir.md` section 5.5's claim is sound for the neutral builder and
incomplete for the repository: adding a MoE architecture is a table for `src/model_ir.align` and
`src/gguf.align`, one arm at three dispatch sites for `src/main.align`, and an append plus a mirror
for the frozen role list. The next architecture that introduces shared experts, expert groups, or
latent attention will test a part of the seam olmoe does not: olmoe's every layer is MoE, its every
expert is routed, and it has no shared expert, so `MlpBlock` and any shared-expert block kind remain
untested by a real model.

### 5.6 Inherited deferrals

Tokenizer and vocabulary (Request 22, unconsumed); `general.file_type` naming; the MoE gating
parameters; non-contiguous and padded containers; big-endian GGUF; multi-shard models; the mmap
arena alternative; Request 21's read-only-open limitation; sub-expert and per-projection
granularity; and every unadded GGML type id. All inherited from
`docs/specs/r1b-gptoss-moe-ir.md` sections 5.2 through 5.6 and the documents they inherit from,
unchanged. R1C introduces no new evidence for or against any of them, with one exception recorded
above: `general.file_type` is `15` on this model and remains reported without interpretation.

## 6. Implementation corrections to this plan

The capability was implemented against this plan at the pinned toolchain, on the host that holds
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`. Every item below is a correction to a promise this document
made, recorded in `docs/specs/r1b-gptoss-moe-ir.md` section 7's format: the section amended, the
correction, the evidence that forced it, and the owner test that now holds it. No item changes
`R1_MODEL_IR`'s `schema_version`, which is `2` as designed.

**The section 1.5 and section 3.1 no-change claim holds as written.** `src/model_ir.align` and
`src/gguf.align` are byte-unchanged. Every mechanic section 3.1 lists as a possible falsifier —
the other stacked axis order, 64 slice ordinals, 1,058 blocks and 3,219 claims, one role carrying
two GGML types across layers, a whole tensor claimed twice, a third `model` field list — was
exercised and none forced a change. The independent proof is that the two shipped binaries agree
byte for byte: the R1 and R1B corpora were derived with the base-commit binary and with this
capability's binary over all 142 unchanged fixtures through both `--model-ir` and `--inspect-gguf`,
284 invocations, with zero differing bytes and zero differing exit statuses.

| # | Amends | Correction | Evidence | Owner |
| --- | --- | --- | --- | --- |
| 1 | 4.1 | **`olmoe-full.gguf` is 1,777,248 bytes, not "well under 1 MiB", and its `source.bytes_read` is therefore exactly one window.** Section 4.1's own arithmetic settles this against its own sentence: the row rule forces `ffn_down_exps` to F32 at `[64, 256, 8]`, which is 524,288 bytes per layer, so two layers exceed 1 MiB before a single attention tensor is counted. The load-bearing half of that sentence — every byte size, and for a sliced tensor every plane, a multiple of the 32-byte container alignment — is what the generator asserts per tensor; the size claim is dropped. The consequence is the one `docs/specs/r1b-gptoss-moe-ir.md` section 7 item 11(d) already records, stated in its narrow form: a container larger than the 1 MiB window **whose `data_offset` falls inside the first window** reports `bytes_read` of exactly one window, never the file size. It does not generalize to every oversized container — `bytes_read` is the first window boundary at or beyond `data_offset`, capped by the file size, which is why the real model reports two windows and not one (section 4.5) | the generator's own per-tensor alignment assertions and `len(full.bytes) == 1,777,248` | `olmoe-full` with `bytes_read` asserted exactly, plus the standing `bytes_read < data_offset + WINDOW_BYTES` bound |
| 2 | 3.2, 4.1 | **`olmoe-stacked-transposed` declares an F32 `ffn_gate_exps`, because a Q4_K one at the transposed extents never reaches step 10.** The fixture's purpose is to pin the section 2.5.3 axis-order decision as a step-10 `R1_TENSOR_SHAPE_UNEXPECTED`. At the base extents the transposed shape is `[64, 256, 8]`, and `64 % 256 != 0`, so a Q4_K tensor is `R1_TENSOR_SHAPE_UNALIGNED` at step 8 and the shape rule is never consulted — the fixture would pass while testing the wrong row. The role is F32 in this fixture only; every other fixture keeps the section 4.1 type table | the row rule of `docs/specs/r1-qwen-model-ir.md`, which `src/model_ir.align`'s `size_tensors` applies before block assembly | `olmoe-stacked-transposed`, asserting `R1_TENSOR_SHAPE_UNEXPECTED` with detail `blk.0.ffn_gate_exps.weight` and three completed blocks |
| 3 | 4.1 | **`olmoe-mixed-quant` cannot use the base extents and ships at `n_ff = 256`, `n_expert = 2`, `n_expert_used = 2`.** Section 4.1 describes it as the real model's pattern "at fixture scale" over `ffn_down_exps` and `attn_v`, but `ffn_down_exps` is `[n_ff_exp, n_embd, n_expert]`, so its first axis is `n_ff_exp`, and the base fixture's 64 is not a multiple of 256 — neither Q6_K nor Q4_K is representable there, which is the same constraint that makes the role F32 in the base fixture. Widening `n_ff` to 256 makes both K-quantizations legal and narrowing `n_expert` to 2 keeps the container under a megabyte. The pattern asserted is unchanged: `attn_v` and `ffn_down_exps` are Q6_K in layer 0 and Q4_K in layer 1 | `nbytes_of`'s `dims[0] % block_size == 0` assertion, which is `ggml_row_size`'s invariant | `olmoe-mixed-quant`, which asserts that exactly `attn_v` and `ffn_down_exps` carry two type ids and that both `AttentionBlock` and `ExpertBlock` have two distinct `byte_size` values |
| 4 | 4.1 | **`olmoe-wide`'s extents are named here, and its expert weights are Q8_0 rather than F32.** Section 4.1 gives its block and claim counts and says "F32 everywhere but the expert weights so the file stays small" without extents. Shipped: `n_layer = 4`, `n_embd = 32`, `n_head = n_head_kv = 8`, `n_ff = 32`, `n_expert = 64`, `n_expert_used = 8`, with the three stacked roles at Q8_0 and everything else F32. F32 expert weights would be 3.1 MB; Q8_0 at `[32, 32, 64]` gives a 1,088-byte plane, which is both block-legal and container-aligned, and the whole file is 948,352 bytes. The counts are exactly as designed: 266 blocks and 807 claims | the generator's `block_count() == 266`, `claim_count() == 807`, and `len(bytes) < 1048576` assertions | `olmoe-wide` under `bounded-work` |
| 5 | 2.8, 4.2 | **The text/wire boundary is closed by the inherited corpora, not by a new olmoe escape fixture.** Section 2.8's "Text/wire boundary" row names `wire-escapes` over the olmoe corpus. No olmoe fixture declares a name or a key needing escaping, and adding one would test `src/model_ir.align`'s renderer — the sole owner of the boundary, byte-unchanged here — a fourth time. The cell is closed by re-running the R0 and R1 escape cases through `--model-ir` unchanged, together with the olmoe corpus's own strict field-order and field-set comparison. A future olmoe fixture with an undecodable tensor name would still surface as `R1_UNASSIGNED_TENSOR`, which is the contract the row states | `src/model_ir.align` is unchanged, and `qwen2-wire-escapes`, `qwen2-arch-escapes`, and the R0 corpus re-run assert the boundary | `qwen2-wire-escapes` and the R0 corpus through `--model-ir`; `field-order-olmoe` on `olmoe-full` |
| 6 | 4.2 | **`role-list-mirror` compares three lists, not two.** Section 4.2 specifies extracting the label sequence from `src/alignpack.align`'s `role_id` and from `scripts/alignpack_reader.py`'s `ROLES` and requiring equality. Shipped, it also extracts `src/alignpack.align`'s `role_label` — the inverse function in the same file — and requires all three to agree, and it requires every role the olmoe plan actually emits to be named by the list. A one-sided edit inside Align is exactly as silent as a one-sided edit across languages, and the reader resolves a persisted `role_id` through the label direction, so leaving the inverse unchecked would have left the failure mode the case exists to prevent half-open. It also asserts that entries 27 and 28 are the two appended QK-norm roles by name, so a future append cannot displace them | the two functions are independent `if` chains in one file, and neither language rejects a disagreement | `role-list-mirror` in `model-ir-smoke` |
| 7 | 4.4 | **The parity runner's three-entry lookup fails closed on a fourth architecture.** Section 4.4 says `build_rows`'s per-architecture extension "becomes a lookup with three entries". A lookup that silently fell through to the shared set for an unknown key would let a fourth frontend ship with its own rows unchecked, which is the failure `parity: UNPARSED` exists to prevent one level down. `ARCH_EXTENSIONS` is a three-entry dict and a missing key is a hard failure naming the architecture | the runner's own fail-closed contract for an uninterpretable value | the three synthetic row-set units — `UNIT_QWEN`, `UNIT_GPTOSS`, `UNIT_OLMOE` — which run before every comparison on a host with no model at all |
| 8 | 2.5.1, 4.1 | **`R1_KEY_VALUE_IMPLAUSIBLE` for an inexact `head_dim` division names `olmoe.attention.head_count`, which differs from the sibling frontend.** Section 4.1 states the detail and it is implemented as stated; the divergence is recorded rather than silently inherited, because `src/frontend_gpt_oss.align` names `gpt-oss.embedding_length` for the same defect. Both are defensible — the division has two operands — and neither is a contract a consumer branches on, but a reader comparing the two frontends should find the difference recorded rather than discover it | `src/frontend_gpt_oss.align`'s step-6 fallback branch | `olmoe-headdim-indivisible` (`n_head = 3`, `n_head_kv = 1`), asserting the detail exactly |
| 9 | 4.4 | **`ulimit -f` in the parity runner is raised from 8,192 to 262,144 blocks (8 MiB to 256 MiB), because it bounds the reference's Metal shader pipeline cache and not only its log.** `ulimit -f` bounds every file the reference process writes. On a Metal host `llama-cli` writes its compiled pipeline cache as 12-35 MB files, two orders of magnitude above its own log (125 KB for the olmoe model, 237 KB for the qwen one), so an 8 MiB cap killed the recorded build (`0.2.0 (build 10566, commit bb4caa754)`) with SIGXFSZ mid-compile on any run that found the cache cold — surfacing only as `the reference reader exited 153`, with the qwen run failing repeatedly at `kernel_flash_attn_ext_vec_f16_dk128_dv128`. This is not "one incident": the cold-cache state recurs on every new host, after every reference upgrade, and after any cache eviction, and the writer is named rather than guessed. 256 MiB clears the largest observed cache file with wide margin and stays far below the 461 MB runaway log the wrapper exists to bound, so the guard's purpose is preserved | the unmodified runner at the base commit fails identically for both models under the old cap, and both comparisons pass under the new one; the runner's comment and `docs/align-development.md` now name the Metal cache as the bounded writer | `model-ir-parity` against the olmoe model and against the qwen model, both PASS under the shipped cap |
| 10 | 2.7, 5.4 | **The new frontend is the third *frontend* — not the third client — at which Request 23's spurious lint fires, and it fires on `borrow GgufTable`, not on `borrow BlockPlan`.** Sections 2.7 and 5.4 predict the false positive on a `borrow BlockPlan` parameter and call it a "third site"; the register already carries four independent clients (`GgufTable`, `BlockPlan`, `TranscriptScan`, `PackPlan`), so both sections now say "the third frontend" and this row is the shipped detail. A frontend never borrows a plan — it *builds* one and moves it into `model_ir.Prepared` — so the three warnings `src/frontend_olmoe.align` emits are on its two public `borrow table: gguf.GgufTable` parameters and on `kv_text_decodable`'s, at 552 bytes each, beside two return-by-value warnings for `model_ir$ModelIr` (176 bytes) and `model_ir$Prepared` (568 bytes). The evidence value is unchanged and arguably higher: the lint fires on a parameter that is explicitly `borrow` and therefore copies nothing. The status stays `PROPOSED` and non-blocking, no new request is created, and the register is updated by the integration commit rather than by this document. **No genuine new Align gap was encountered**: every operation is `i64` arithmetic, owned-`string` slicing, `builder` writes, and `array<i64>` indexing over surfaces R1 and R1B already proved at this pin | `make check` emits `src/frontend_olmoe.align:64:32`, `:182:37`, and `:189:30` for `gguf$GgufTable`, and no `model_ir$BlockPlan` warning in that file | `make check`; `docs/align-requests.md` Request 23's evidence block, owned by the integration commit |
| 11 | 2.6, 4.1 | **The block-explosion detail names the extreme operand rather than always naming `olmoe.expert_count`.** Section 2.6 step 7 defines the guard as one product and, as first implemented, it reported `olmoe.expert_count` unconditionally. The product has two operands with different ceilings (`MAX_LAYERS` 512, `MAX_EXPERTS` 1,024), so a file with a modest expert count and an absurd layer count was sent to the key it had set correctly — the same defect item 8 records for the `head_dim` division, and it is repaired here rather than only recorded because the guard, unlike that division, has an unambiguous answer. Shipped: the detail names whichever operand is the larger fraction of its own ceiling, compared as `n_layer * MAX_EXPERTS > n_expert * MAX_LAYERS` so no division is needed and neither product can wrap; a tie keeps `olmoe.expert_count`, which preserves the both-at-ceiling case. This is a diagnostic detail, not a new error code and not a new rejection: exactly the same inputs are rejected, with the same `R1_KEY_VALUE_IMPLAUSIBLE` code | `olmoe-block-explosion` is unchanged at `olmoe.expert_count` because `512 * 1024 == 1024 * 512`, and the new `olmoe-block-explosion-layers` (`n_layer = 512`, `n_expert = 128`) asserts `olmoe.block_count` | `olmoe-block-explosion` and `olmoe-block-explosion-layers` in `model-ir-smoke`, both asserting the detail exactly |

### 6.1 Closure cell to shipped case

Section 3 names cells by contract; `scripts/run-model-ir-smoke`, `scripts/run-alignpack-smoke`, and
`scripts/gguf_fixture.py` name cases by fixture. This is the mapping, in section order, so a
reviewer can move from a closure cell to the evidence that closes it without searching. It lists
**every** cell, including the ones whose names already match, so a missing row is a visible gap
rather than an implied match.

| Section 3 cell | Shipped evidence |
| --- | --- |
| 3.1 the whole no-change table | `src/model_ir.align` and `src/gguf.align` are byte-unchanged; the 284-invocation differential run above; `make check` reports 30 units where R1B reported 29 |
| 3.2 Construction — plan | the runner's `expected_blocks = n_layer * (2 + n_expert) + 2` assertion on every positive olmoe document, plus `claim_count` asserted exactly on `olmoe-full` (69) and `olmoe-wide` (807), plus the generator's independent `block_count()` / `claim_count()` assertions |
| 3.2 Construction — result | `olmoe-expert-zero`, whose complete olmoe `model` object is compared strictly — field set, order, and values — with `n_vocab` at its `-1` sentinel because step 9 never ran and with every value steps 5 and 6 did read reported as read |
| 3.2 Success — hyperparameters | `olmoe-full`'s strict `model` comparison against generator-declared goldens, repeated for every positive variant |
| 3.2 Success — `head_dim` | `olmoe-full` (`derived`, `32`) and `olmoe-headdim-metadata` (`metadata`, `64` against a division of `32`, so the two rules must disagree); `olmoe-keylength-mismatch` and `olmoe-headdim-indivisible` for the two rejections |
| 3.2 Success — `n_ff_exp` | `olmoe-full` (`derived`, `64`) and `olmoe-ffexp-present` (`metadata`, `32`, so every stacked shape narrows) |
| 3.2 Success — block plan | `olmoe-block-order` and `olmoe-block-roles` are the runner's per-corpus assertions: the kind, layer, and expert sequences are compared against the emission order, and `AttentionBlock`, `RouterBlock`, `ExpertBlock`, and `WeightBlock` member sets are compared against the exact section 2.5.3 role lists on every positive olmoe document |
| 3.2 Success — slice declaration | `olmoe-slice-declaration`, the `slice_declaration` assertion on `olmoe-full`: a member claims a sub-range if and only if its role is one of the three stacked expert roles |
| 3.2 Success — QK-norm members | the same role-list assertion (both QK-norms in every `AttentionBlock`, in position); `olmoe-qknorm-missing` and `olmoe-qknorm-shape` for the negatives |
| 3.2 Success — mixed per-layer type | `olmoe-mixed-quant`, asserting that exactly `attn_v` and `ffn_down_exps` carry two type ids and that both block kinds have two distinct `byte_size` values; section 6 item 3 records its extents |
| 3.2 Success — tied embedding | `olmoe-tied`, which asserts `token_embd.weight` appears in two blocks with roles `output` and `token_embd` and that the tiling oracle takes its whole-tensor branch |
| 3.2 Failure — expert bounds | `olmoe-expert-zero`, `olmoe-expert-used-zero`, `olmoe-expert-used-high`, `olmoe-expert-huge`, plus `olmoe-expert-missing` and `olmoe-expert-type` for the two earlier rows |
| 3.2 Failure — block explosion | `olmoe-block-explosion` (`n_layer = 512`, `n_expert = 1024`, product 525,314, detail `olmoe.expert_count`) and `olmoe-block-explosion-layers` (`n_layer = 512`, `n_expert = 128`, product 66,562, detail `olmoe.block_count`); section 6 item 11 records the tie-break |
| 3.2 Failure — `head_dim` indivisible | `olmoe-headdim-indivisible`; section 6 item 8 records the detail key |
| 3.2 Failure — stacked shape | `olmoe-stacked-axis` and `olmoe-stacked-ndims`, both with three completed blocks |
| 3.2 Failure — transposed expert shape | `olmoe-stacked-transposed`; section 6 item 2 records its type override |
| 3.2 Failure — router shape | `olmoe-router-shape`, with two completed blocks |
| 3.2 Failure — unexpected bias | `olmoe-extra-bias`, asserting `R1_UNASSIGNED_TENSOR` and the reported `unassigned_tensors` array |
| 3.2 Failure — wrong arch | `olmoe-wrong-arch`, which reaches the qwen2 frontend and fails on `qwen2.block_count`; the frontend's own step-4 re-check is additionally covered by the R0 corpus |
| 3.2 Failure — precedence | `olmoe-precedence-key-shape` and `olmoe-precedence-expert-vocab` |
| 3.2 Malformed | **inherited**: the whole R0 corpus re-run through `--model-ir`, 62 fixtures, unchanged |
| 3.2 Early exit | `olmoe-ir-partial` is the `blocks_len` assertion carried by every step-10 negative: 3 completed blocks for the three stacked-shape cases, 2 for the router case, 1 for the two QK-norm cases, 0 for every pre-derivation failure |
| 3.2 Loop joins | `olmoe-zero-layer` (`block_count = 0`) and `olmoe-expert-zero` (`expert_count = 0`), both rejected before any loop runs |
| 3.2 Branch joins | `document-move` is the per-case assertion that the stdout form is byte-identical to the written document and that both forms agree on the exit status, applied to all 29 olmoe cases |
| 3.2 Move-out | the same assertion, plus `make check`'s ownership analysis over the new module |
| 3.2 Borrow discipline | `make check` (`check-per-unit`), which reports the new unit |
| 3.2 Bounded work | `olmoe-wide`, timed against the 3-second budget |
| 3.2 Generic / shared state / concurrency | `N/A` as designed: no generic is declared, no process-global state is held, the frontend is read-only over one borrowed table. Held by `repeat-model-ir (olmoe)` — 16 repeated derivations, byte-identical — and `env-perturbation (olmoe)` |
| 3.2 Per-unit vs whole-program | `make check` (`check-per-unit`) and `make build` |
| 3.3 Construction | `role-list-mirror`, which requires the extracted list to be dense over `0 .. 28` and asserts entries 27 and 28 by name |
| 3.3 Success — mirror equality | `role-list-mirror`; section 6 item 6 records that it compares three lists |
| 3.3 Success — round trip | `pack-olmoe`: all seven positive olmoe fixtures now run through `--pack`, `--pack-verify`, and the independent reader in `alignpack-smoke`, and the QK-norm members of `olmoe-full` are asserted to carry exactly `role_id` 27 and 28. The reader independently requires each member's document `role` to equal `ROLES[role_id]` |
| 3.3 Failure — unnamed role | **inherited**, unchanged: a role the list does not name is `DEFERRED_U32` and the reader accepts it as a stated absence |
| 3.3 Bounded work | `pack-olmoe` over `olmoe-wide` (266 blocks) against `MAX_BLOCKS` 1,048,576 |
| 3.3 Everything else | **inherited**: the R4 corpus re-run — 27 positive fixtures, 128 negative sources, 20,280 assertions |
| 3.4 Construction — dispatch | `dispatch-single-read`: the `bytes_read` values of the qwen and gpt-oss corpora are numerically unchanged, which the 284-invocation differential run proves byte for byte |
| 3.4 Success — three architectures | `dispatch-qwen`, `dispatch-gptoss`, and `dispatch-olmoe` in `model-ir-smoke`, plus `dispatch-olmoe` at `--pack` and `--pack-verify` in `alignpack-smoke` |
| 3.4 Failure — unknown architecture | `dispatch-unknown` over both `gptoss-wrong-arch` and `olmoe-wrong-arch`; `qwen2-wrong-arch`, `qwen2-arch-escapes`, and the R0 positive corpus, all byte-unchanged |
| 3.4 Arm consistency | the `alignpack-smoke` assertion that `--model-ir`, `--pack`, and `--pack-verify` report the same `arch` and the same block count for `olmoe-full` |
| 3.4 Byte identity across forms | `form-parity` over all four corpora |
| 3.4 Summary block | `summary-order` and `summary-control-bytes` over all four corpora; the `qwen model ir:` header is unchanged, and `blocks:` is asserted against the document's own block count |
| 3.4 Failure mapping | every negative olmoe case asserts a nonzero exit inside `(0, 125]` and a complete parseable failure document |
| 3.4 Everything else | **inherited**: the R1 and R4 CLI cases re-run unchanged |
| 3.5 Target definition | the `Makefile` is unchanged; `git diff --stat` shows no `Makefile` row |
| 3.5 Aggregate membership | `make gate-topology-check`, PASS |
| 3.5 Qualification exclusion | `make gate-topology-check`, PASS |
| 3.5 Preflight profile selection | `python3 scripts/pre-pr --plan`, recorded in the pull request |
| 3.5 Fixture generation | the runner's repository leak sweep, plus the surviving temporary-root assertion |
| 3.5 Fixture independence | the generator imports nothing from `src/`; its import list is unchanged |
| 3.5 Generator compatibility | every pre-existing fixture is byte-identical: 142 of 142 files and all three prior manifest lists compared against the base-commit generator, zero differences; `make gguf-smoke` reports the same 62 fixtures |
| 3.5 Parity arch dispatch | `UNIT_OLMOE` beside `UNIT_QWEN` and `UNIT_GPTOSS`, asserting that the olmoe extension is exactly `["n_expert_used"]`, contains neither `n_ff_exp` nor `n_swa`, extends the shared set, and records both omissions as notes |
| 3.5 Parity skip | the four exact `N/A` lines, unchanged |
| 3.5 Cleanup | the EXIT trap plus the final temporary-root assertion in both runners |
| 3.5 Documentation | this section; `HANDOFF.md`, `docs/specs/roadmap.md`, and `docs/align-requests.md` are updated by the integration commit |

## 7. Corrections applied to `docs/specs/r1b-gptoss-moe-ir.md`

Section 2.9 records what a real MoE model settles and what it contradicts. Two of those rows are
corrections to a promise that document makes, and one is the resolution of a claim it recorded as
untested. All three are **applied**, as items 16, 17, and 18 of that document's section 7, in the
format its section 7 already uses. Neither `src/frontend_gpt_oss.align` nor any gpt-oss fixture
changes: no gpt-oss file is present, and correcting an assumption with a different assumption is
not progress.

1. **Item 16 — the stacked expert axis order.** `docs/specs/r1b-gptoss-moe-ir.md` section 2.5.2
   expects `ffn_gate_exps.weight` and `ffn_up_exps.weight` as `[n_ff_exp, n_embd, n_expert]` and
   `ffn_down_exps.weight` as `[n_embd, n_ff_exp, n_expert]`. The real model declares the reverse,
   which is this repository's own dense convention plus an expert axis. The gpt-oss rows stay
   ASSUMED; what item 16 changes is their standing, raising that document's section 4.5 inspection
   prerequisite from "before merge" to **before the gpt-oss frontend is trusted on a real file**,
   and naming the four `expected_shape` rows that are wrong as shipped if the inspection agrees
   with olmoe. `olmoe-stacked-transposed` pins the olmoe direction as a rejection so the two
   frontends cannot drift into agreement by accident.
2. **Item 17 — the required split expert biases.** That document's section 2.5.4 keeps
   `ffn_{gate,up,down}_exps.bias` required on the strength of llama.cpp's quantization-exclusion
   regex `ffn_gate(_exps)?.bias`. The regex attests a **spelling**, never a **presence**: a real
   split-layout MoE — `ffn_gate_exps` and `ffn_up_exps` present, `ffn_gate_up_exps` absent — carries
   no bias tensor of any kind. Item 17 records the regex as no longer evidence for requiring them
   and leaves the gpt-oss decision to that architecture's own inspection. `src/frontend_olmoe.align`
   declares no bias role at all, and `olmoe-extra-bias` asserts the fail-closed outcome.
3. **Item 18 — section 5.5's untested claim.** "Adding one should require no change to
   `src/model_ir.align`" is now tested, holds exactly as written, and is incomplete: `BlockPlan` is
   not the only seam an architecture crosses. Item 18 records the append-only `role_id` list as the
   second seam and states the whole cost of a new MoE architecture — a table for the neutral
   builder, one arm at three dispatch sites, and an append plus a mirror for the role list. That
   document's section 5.5 now carries the result inline as well, so a reader of the claim meets its
   resolution.

## 8. Publication reconciliation

This branch was rebased onto `main` `546b5cc`, the merge of R2-LOCALITY-GATE (PR #131). The rebase
renamed every commit: the design ledger `5a15fd7` became `83361a9`, the implementation `eb868ba`
became `45e4ced`, and the review repair `58e9ba9` became `4c86336`. The review record names the
pre-rebase head it actually read; every other reference in this repository names the post-rebase
commit. That
capability is the other consumer of the same downloaded `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`,
and it measured the R2 locality gate as **met in the prefill direction** — observed adjacent-token
expert reuse 286 per mille against a 125 per mille null, cluster-robust 95% interval
`[262, 311]` over 40 prompt clusters, all 15 measurable layers clearing the null.

The reconciliation is documentation-only. Nothing in the merged gate touches a surface this ledger
owns: it changed `src/expert_trace.align`, `scripts/eval_callback_fixture.py`, the expert-trace
runners, and the new locality-gate script and prompt corpus, none of which this capability reads or
writes, and it changed no Model IR, Block IR, alignpack, or GGUF surface. The two capabilities meet
only at the model file itself and at R3, which consumes this capability's Block IR and that
capability's demand signal. The owner evidence in section 6 was produced before the rebase and
re-run after it with identical results.

The status prose that the rebase reconciled is in `HANDOFF.md`, `docs/specs/roadmap.md` items 18
and 19 and its Japanese section R1/R2, `docs/align-requests.md`'s status header and narrative, and
`docs/align-development.md`'s R1C paragraph: each described R2-LOCALITY-GATE as in progress and is
now correct against the merged result.
