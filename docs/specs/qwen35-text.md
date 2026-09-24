# Qwen3.5 text support

Status: active. This plan owns the `qwen35` extension; the existing Qwen2 and OLMoE contracts remain in their own plans.

## Evidence and delivery order

The first real consumer is `ggml-org/Qwen3.5-0.8B-GGUF`, file `Qwen3.5-0.8B-Q4_0.gguf` (563,036,064 bytes; SHA-256 `57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`). Its GGUF inspection at the current `.llama-revision` reports architecture `qwen35`, 24 layers, 320 tensors, embedding width 1024, feed-forward width 3584, vocabulary 248320, context 262144, full attention every fourth layer, and 18 recurrent Gated DeltaNet layers. The six full-attention layers and 18 recurrent layers have distinct tensor sets. The file declares `tokenizer.ggml.pre = qwen35` and has a tied output embedding. Before #294, `--model-ir` refused it with `R1_UNSUPPORTED_ARCH`; #294 completed the first boundary.

The first independently useful consumer boundary is `--model-ir` plus `--pack` for this real GGUF. It permits validated model inspection, complete tensor coverage, and an owned layout artifact without claiming inference. The next boundary is `--tokenize` and `--detokenize` on this GGUF, with exact pinned llama.cpp token parity. The existing `--prepare-prompt` command then provides real text-only Qwen3.5 chat input IDs. Text-only native `align-runtime` prefill and decode through `--provider align-runtime` uses that tokenizer plus hybrid recurrent/attention state. Vision, MTP/speculative heads, MoE, and 27B are later consumers. Do not infer their support from a passing 0.8B case. No speed claim is made by this work.

## Public contract ledger

| Dimension | First boundary: Model IR and alignpack | Native text boundary |
| --- | --- | --- |
| Surface and defaults | Existing `--model-ir GGUF [JSON]` and `--pack GGUF PACK [JSON]` accept exact architecture `qwen35` without a new flag. Existing arity and output placement apply. | Existing `--provider align-runtime` and `--runtime-session` accept the Qwen3.5 pack and geometry. Text only; existing options and defaults apply. |
| Input and validation | GGUF v3 with required `qwen35` metadata, `tokenizer.ggml.model = gpt2`, `tokenizer.ggml.pre = qwen35`, STRING token and merge arrays, INT32 token-type array, token and type counts equal to the embedding vocabulary, and a nonempty merge array. Require all 320 named tensors for the 0.8B reference and no unknown or unclaimed tensor. Reject absent, malformed, mistyped, implausible, or incompatible keys before writing a pack. An optional `output.weight` aliases `token_embd.weight`. Recurrent and full-attention block shapes are validated separately. | The pack must be source-bound to the GGUF and geometry exactly as existing Qwen2 sessions are. Reject unsupported model options and dimensions before device allocation. |
| Result and errors | `R1_MODEL_IR` schema 2 and `R4_ALIGNPACK` schema 1 are retained. `model.arch = qwen35` discriminates architecture-specific model fields; role ids append to the frozen table. Reuse existing R1/R4 error codes with first-error precedence. | Existing provider result and session observation formats remain; failures use existing `Error.Invalid` unless a distinct public diagnostic is justified in the implementation plan. |
| Ownership and allocation | `gguf` owns one read-only table. The new frontend owns its derived plan; neutral `model_ir` and `alignpack` own rendering, copy, and cleanup. `--pack` writes only after full model validation. | Align owns graph construction, model/recurrent/KV state, device placement, generation, and cleanup. C remains the thin ggml ABI. Recurrent state is explicit per session and cannot leak across requests. |
| Identity and version | GGUF source identity, pack layout identity, and existing schema fields remain authoritative. A `qwen35` artifact cannot be read as `qwen2` because the architecture is part of the geometry and layout. | Topology identity includes architecture, geometry, shape, and backend via the existing key contract. |
| Prerequisites | Pinned ggml already supplies the Qwen3.5 model reference and the Gated DeltaNet, SSM convolution, and Metal operations. Adopt a newer pin only for a demonstrated missing consumer requirement. | A real reference run at the same pinned llama.cpp revision and a stable text prompt oracle precede native acceptance. |
| Acceptance and metrics | Exact real-file `--model-ir` success, all tensors claimed once except the tied embedding alias, byte-identical `--pack` verification, malformed-key and wrong-shape refusals, unchanged Qwen2/OLMoE owners. No performance metric. | Prefill and multistep decode token parity against the reference under named prompts, then an actual provider request with text and token counts; correctness before any performance comparison. |

The intermediate tokenizer consumer retains existing `--tokenize GGUF INPUT MODE` and
`--detokenize GGUF IDS MODE` arity, JSON results and error vocabulary. It accepts only the
`gpt2/qwen35` tokenizer profile on a `qwen35` GGUF and derives a distinct tokenizer identity from
profile, classifier, tokens, types, and merges. The model loader owns the arrays, the tokenizer
owns temporary index and regex allocations, and every command releases them at return. GGUF
metadata is read before allocation and malformed profiles fail with the existing `R7` errors.
The native provider need not accept Qwen3.5 until its graph and state boundary passes. Acceptance
for this intermediate consumer is exact token ids from the pinned llama.cpp tokenizer on ASCII,
Unicode combining marks, Japanese text, whitespace, punctuation, and control-token cases, plus
detokenization parity and unchanged Qwen2/OLMoE tokenizer smoke. Its owner is
`scripts/run-qwen35-tokenizer-smoke`; the observed real model hash above identifies the corpus.

### Tokenizer closure matrix

| Phase | Implementation and exact regression |
| --- | --- |
| Construction | `tokenizer_qwen2.tokenizer_profile` checks `gpt2/qwen35` and `general.architecture = qwen35` before array allocation; `scripts/run-tokenizer-smoke` exercises a synthetic accepted and mismatched profile. |
| Success | `tokenizer_qwen2.qwen_pieces` includes Unicode marks only for Qwen3.5 and the identity uses a distinct profile domain; `scripts/run-qwen35-tokenizer-smoke` compares eight real-file paired cases with pinned llama.cpp and round-trips their bytes. |
| Failure and malformed input | The existing `R7` errors reject absent or mismatched metadata and invalid arrays before tokenization; `scripts/run-tokenizer-smoke` covers both directions of architecture/profile mismatch and its existing malformed corpus. |
| Early exit and cleanup | `--tokenize` and `--detokenize` retain the existing bounded read, result, and temporary allocation lifecycle; `scripts/run-tokenizer-smoke` covers failed and repeated operations. |
| Reused modules | `main` retains verb arity and `gguf` reader ownership; existing Qwen2/OLMoE tokenizer owners run unchanged alongside the Qwen3.5 cases. |

The tokenizer implementation maps to `tokenizer_qwen2.tokenizer_profile`,
`tokenizer_qwen2.identity`, and `tokenizer_qwen2.qwen_pieces`. After the accepted review finding,
the profile rejects both `qwen35` tokenizer on a different architecture and `qwen35`
architecture with a different tokenizer. `scripts/run-tokenizer-smoke` passes its synthetic
positive and malformed corpus; `scripts/run-qwen35-tokenizer-smoke` passes eight paired real-file
cases against pinned llama.cpp, including control-token modes and detokenization. This closes the
intermediate tokenizer boundary only; the native text matrix remains open.

### Text-only generation prompt boundary

The existing `--prepare-prompt GGUF SYSTEM USER` command accepts the exact 0.8B GGUF chat
template SHA-256 `273d8e0e683b885071fb17e08d71e5f2a5ddfb5309756181681de4f5a1822d80`.
It renders one leading system message, one user message, and an assistant generation prefix with
thinking disabled. Both contents use the pinned llama.cpp Jinja `strip` behavior: C-locale byte
`isspace` removes ASCII space, tab, line breaks, form feed, and vertical tab at the ends; UTF-8
whitespace such as U+3000 remains. Tools, images, message
history, and thinking-enabled prompts remain outside this command's two-message text contract.
The pinned `common_chat_templates_apply` Jinja renderer was also invoked directly with a
vocabulary-only load: it removed U+000B vertical tabs and retained leading/trailing U+3000 in
both message contents, confirming the actual implementation rather than generic Jinja behavior.
The full source template is 7,755 bytes, so metadata admission permits 8,192 bytes but still
requires its exact hash and the `gpt2/qwen35` profile. This boundary retains the command arity,
JSON token result, existing `R7` errors, and tokenizer ownership. The rendered fixed length is
99 bytes before trimmed content; input files remain bounded independently and the final prompt
retains the existing 1 MiB ceiling. `scripts/run-qwen35-tokenizer-smoke` pairs five real-file
system/user cases with pinned llama.cpp tokenization of the template's text-only branch;
`scripts/run-prompt-smoke` checks the admitted 8,192-byte template limit and 8,193-byte refusal;
`scripts/run-tokenizer-smoke` retains Qwen2/OLMoE prompt and error coverage. This supplies a
stable prompt oracle for the native graph; it makes no inference or speed claim.

The first boundary adds these stable role ids after 28: `post_attention_norm` 29, `attn_qkv` 30, `attn_gate` 31, `ssm_conv1d` 32, `ssm_dt` 33, `ssm_a` 34, `ssm_beta` 35, `ssm_alpha` 36, `ssm_norm` 37, `ssm_out` 38. Existing ids never move. The frontend uses the GGUF's declared `attention.key_length` and `attention.value_length`; it does not derive either from `embedding_length / head_count`. The pinned llama.cpp reference selects interleaved M-RoPE (`GGML_ROPE_TYPE_IMROPE = 40`), which the Model IR records. `rope.dimension_sections` is an array of four INT32 values and is validated in the native text boundary before graph construction. The model's `full_attention_interval` fixes the block type; no inferred tensor fallback is permitted.

## Closure matrix for the first boundary

| Phase | Owner and exact regression |
| --- | --- |
| Construction and validation | `frontend_qwen35.prepare` validates the architecture, required metadata and per-layer roles; `run-model-ir-smoke` covers the real 0.8B file and synthetic malformed metadata. |
| Success and format | `main` dispatches `--model-ir` and `--pack`; `model_ir` retains one renderer; `alignpack` maps appended roles. Real-file owner asserts schema, 320-tensor coverage and packed layout verification. |
| Failure and malformed input | The frontend returns the first existing R1 error before any pack write. Focused fixtures remove a required key/tensor and change one tensor shape. Existing Qwen2 and OLMoE smoke owners remain unchanged. |
| Early exit and cleanup | The borrowed GGUF table and partially built plan end with the command. `alignpack` retains its existing atomic write/cleanup path; failed derivation creates no pack. Focused owner asserts refusal and no destination. |
| Reused modules | `gguf` parses the same table once, `model_ir` consumes the plan without architecture dispatch, and `alignpack` resolves every appended role. `run-model-ir-smoke` and `run-alignpack-smoke` own consistency. |

Before publishing each boundary, map these cells to the final diff and passing commands or an explicit deferral here.

## Native text closure matrix

The next generation consumer is one Qwen3.5-0.8B text-only provider request with prefill and multiple decode
steps. The pinned llama.cpp
`qwen35` graph and tokenizer are the oracle; do not treat Qwen2 graph geometry or token splitting
as interchangeable.

| Phase | Implementation owner | Exact regression target |
| --- | --- | --- |
| Construction | `tokenizer_qwen2` supplies the qualified `qwen35` prompt identity; `runtime_qwen35_geometry`, `runtime_qwen35_load`, and `runtime_qwen35_generation` validate geometry and allocate hybrid state before acknowledging the session. | `scripts/run-qwen35-generation-smoke` uses the source-bound real pack and model geometry; the geometry and load owners check invalid metadata and state sizing. |
| Success | `runtime_qwen35_model` builds full-attention and Gated DeltaNet layers; `runtime_qwen35_generation` executes prompt chunks and retains decode parity graphs; `provider_runtime` routes one-shot and framed requests. | `scripts/run-qwen35-generation-smoke` compares three greedy tokens for 31-, 200-, and 330-token prompts with pinned llama.cpp and verifies six retained requests. |
| Failure and malformed input | `provider_runtime` rejects malformed framing, unsupported sampling, and invalid prompt bounds before state mutation; `runtime_qwen35_generation` poisons a session after execution failure, and the worker terminates after a failed frame. | The real generation owner checks unsupported sampling followed by a valid request. A focused execution-failure injection remains deferred because no new failure mechanism is introduced by this session route; the existing GPU owner covers compute failure. |
| Early exit and rollback | A completed request clears the resident KV before the next request; max-one and EOG exits end without further decode. Execution failure closes the session instead of promising rollback of in-flight GPU writes. | The real generation owner checks a max-one request followed by a full request with identical output to a fresh one-shot result. |
| Cleanup | `runtime_qwen35_generation` invalidates the transient prefill graph; owned device and retained decode graphs release when the worker exits. | The same owner closes the six-request worker after exact output checks; the GPU attention owner checks KV reset and refusal. |
| Reused modules | `ggml_ffi` exposes only thin wrappers for shipped pinned ggml operations, with owner state and shapes in Align; existing Qwen2/OLMoE dispatch remains explicit. | `scripts/run-layer-forward-smoke`, `scripts/run-tokenizer-smoke`, and `scripts/run-runtime-provider-smoke` remain regression owners. |

### Pinned reference mapping for the native boundary

The exact `.llama-revision` `bb4caa7540188872173c44d161602d9271386413` has the reference
in `src/models/qwen35.cpp` and `src/models/delta-net-base.cpp`. Its 0.8B GGUF interleaves six full
attention layers with 18 recurrent layers. Both start with `attn_norm`, add the attention result to
the residual, apply `attn_post_norm`, then add the dense SwiGLU FFN result to that residual. The
full-attention path projects joint Q and gate, normalizes Q and K, applies interleaved M-RoPE with
four declared sections, computes attention, multiplies by sigmoid(gate), and projects the output.
The recurrent path projects mixed Q/K/V and z, sigmoid(beta), softplus(alpha + dt) multiplied by
the stored `ssm_a`, applies causal SSM convolution, L2-normalizes Q and K, runs Gated DeltaNet,
applies gated RMS norm with z, and projects the output. The native graph must preserve these
orders; substituting the Qwen2 head or plain RoPE changes the model.

The pinned text input constructor supplies `ggml_rope_multi` with four contiguous position
planes, each `n_tokens` long. The first three planes contain the same token positions and the
fourth is zero. A one-position-per-token Qwen2 input violates ggml's M-RoPE assertion.
`runtime_qwen35_geometry.write_text_positions` produces this layout with bounded `i32`
positions; its real-model smoke checks all four planes and rejects a short output buffer.
`ggml_ffi.op_rope_imrope` exposes the pinned operation through a thin checked shim;
the ggml-free stub refuses numeric M-RoPE execution explicitly. This is input and ABI
preparation only; the native graph must still consume it and pass oracle parity.

For the first real 0.8B geometry, `ssm_inner_size=2048`, `ssm_group_count=16`,
`ssm_state_size=128`, `ssm_time_step_rank=16`, and `ssm_conv_kernel=4`. Each recurrent layer has
`conv_channels=2048+2*16*128=6144`, a three-position convolution history (18,432 elements), and
a `128*128*16=262,144` element DeltaNet state. These are per-session state, not model weights.
The native admission requires `ssm_inner_size / ssm_time_step_rank == ssm_state_size`, so the
declared state tensor shape and computed state extent cannot diverge.
For the first one-sequence text session, retain six attention KV pairs and two copies each of
the 18 recurrent layers' convolution history and DeltaNet state: 12 + 18 * 4 = 84 resident
F32 tensors. A recurrent layer's convolution state has shape `[3, 6144, 1]` and its DeltaNet
state has shape `[128, 128, 16, 1]`. `runtime_qwen35_state` owns one active parity for all
recurrent layers. Each graph reads the active pair and writes the next pair. Only a successful
full step flips parity and publishes the token prefix; a failed or cancelled step leaves the
active pair and prefix unchanged. The inactive pair may contain partial results and is overwritten
on the next attempted step. The first session does not retain extra DeltaNet snapshots (`K=1`).
`runtime_qwen35_state_io` binds the active resident tensor and stages a same-shape graph copy into
the inactive tensor through the existing GPU KV slot ABI; the graph caller must expand that
copy node and advance parity only after complete execution and publication. The Metal load
owner checks active resident bindings before and after a parity flip. Staged writes and rollback
still require the native graph owner.
The owning smoke must check layer-to-state indices across the 3/4 and 7/8 block boundaries,
84 unique allocations, a successful flip, and unchanged active indices on failure before the
full model oracle is attempted.
The 0.8B pack has 321 member records but 320 distinct source tensors: its final `output`
member repeats `token_embd.weight` (270,172,160 bytes). The native weight plan must validate
that the `output` member has the embedding member's source offset, type, dimensions, and byte
size before binding the output projection to the already loaded embedding tensor. It then loads
one embedding, 18 recurrent layers with 14 members each, six attention layers with 11 members
each, and one output norm: 320 device weight tensors. This avoids a second upload and resident
copy of the tied embedding; it is a loader ownership rule, not a measured speed claim.
`runtime_qwen35_roles` now numbers the 320 unique loaded weights in graph order: embedding at
zero, 14 recurrent or 11 full-attention members per layer, and output norm last. Its owning
real-pack smoke compares all 321 member role ids and block kinds, checks consecutive weight
slots and shapes, and refuses an altered tied-output source offset.
`runtime_qwen35_load` validates the real pack order, role, source alias, shape, and logical byte
count before planning 320 backend-aligned weights and 84 resident F32 tensors. Its focused 0.8B
Metal owner at the exact pinned ggml commit uploads all 320 unique weights, defines all resident
tensors, and confirms the uploaded byte count excludes the repeated output member. This verifies
load ownership and allocation only; whole-model graph execution and numeric parity remain open.
The plan must validate the four rope sections from source GGUF, model/pack identity, block roles,
all state extents and the selected ggml op shapes before graph creation. `ggml_rope_multi`,
`ggml_ssm_conv`, and `ggml_gated_delta_net` exist at the pin and now have checked shim symbols.
The one-token recurrent graph also needs direct `ggml_sigmoid`, `ggml_softplus`, `ggml_silu`,
`ggml_scale`, and `ggml_l2_norm` unary calls. Their shim ABI takes a graph context, slot window,
output and source slot; scale takes a finite F32 factor, and L2 normalization additionally takes
finite positive F32 epsilon bits. The shim
accepts bounded F32 input, checks slot/shape before calling the pinned ggml constructor,
returns the existing `ALIGN_GGML_*` status, and owns no payload. Align owns the operation order,
the source slot map, and graph lifetime. The ggml-free stub refuses numeric execution of these
new operations, as it does for SSM convolution and Gated DeltaNet.
The first text session retains only the final DeltaNet state, so its ABI fixes the snapshot
count at one. The ggml-free stub refuses execution of these three numeric operations explicitly;
passing the shim's shape checks does not establish the native model's numerical correctness.
The first one-token recurrent-layer builder binds ten recurrent attention weights, forms the
causal convolution and staged history write, applies Gated DeltaNet and its staged state write,
then performs gated normalization and output projection. A real pinned-Metal 0.8B owner builds
and executes layer 0 with a nonzero synthetic hidden vector and reads a nonzero output. This
establishes a runnable layer path, not parity with llama.cpp or a full-model speed result.
The common one-token block tail adds the attention result to the layer input, applies the
post-attention RMS normalization and its weight, computes a parallel SiLU-gated FFN, and adds
the FFN result to the first residual. The same Metal owner executes this complete recurrent
block tail with the real layer-0 weights; numeric oracle parity remains a later gate.
The one-token full-attention builder splits the joint query/gate projection by the pinned
head-interleaved stride, normalizes Q and K per head, applies the four-plane text M-RoPE,
and writes K and V into resident sequence-major tensors before masked Flash Attention.
It applies the sigmoid gate and output projection; the common tail then completes the block.
The real pinned-Metal owner executes layer 3 with a synthetic input and nonzero result. It
selects Flash Attention before memory admission and uses a 256-wide masked first-token view.
This is graph execution evidence, not numerical parity or a speed comparison. A decomposed
attention path remains a separate implementation decision after the first Metal oracle.
The first complete one-token graph now chains all 24 layers, applies the output RMS norm and
tied embedding projection, and reads 248,320 logits. The recurrent loader zeroes the active
state explicitly because backend allocation does not guarantee zero fill. The pinned fused
Gated DeltaNet receives the L2-normalized Q directly; applying another inverse-square-root
factor before it changes the layer output and is prohibited. Same-pin Metal callback comparison
for token 0 matches the first and last logits within a bounded floating tolerance. A second
sequential step with token 23066 from `! hello` matches the reference's displayed edge logits
after resident recurrence and KV publication. These displayed samples alone do not establish
full-vector or longer-prompt parity, a reusable decode session, or a speed result. The owner also
accepts two optional output paths for complete F32 logits. The independent
`scripts/qwen35_llama_logits_oracle.cpp`, compiled against the exact pinned llama.cpp headers and
Metal build, loads the same GGUF with all layers offloaded, context 512, and Flash Attention on.
It compares every logit in separate decode calls for token IDs 0 and 23066. The Apple M1 result
is 248,320 finite values per step, maximum absolute differences 0.0004912 and 0.0002388,
and matching argmax IDs 198 and 11. The oracle rejects an absent or wrong-size dump. This
established two-step full-vector Metal parity; the next checkpoint below adds graph reuse.
Longer prompts and provider behavior remain open. Build the oracle with the pinned source's `include` and `ggml/include`
directories and the Metal build's `libllama`; invoke it with `GGUF ALIGN_FIRST ALIGN_SECOND`
after the smoke writes both dumps. The oracle requires a GPU backend at runtime.

### Reusable one-token decode graph contract

The Qwen3.5 recurrent state has two resident copies. A successful token flips its active
parity; the next decode graph must read the newly active copy and stage writes to the other.
Retain one prepared graph for each decode parity while keeping the existing prefill graph.
The shim's internal graph-kind ABI adds `GPU_GRAPH_DECODE_ALT = 2` with the same indexed KV,
input validation, allocation, compute, and failure behavior as decode kind 1. Kinds 1 and 2
have separate graph contexts, keys, preparation state, and execution counters. Existing Qwen2
and OLMoE sessions continue to use kinds 0 and 1. A malformed kind fails before indexing any
array. The Align FFI and `runtime_execution` admit kind 2 only where decode semantics apply.

For one-token Qwen3.5 decode, graph identity includes recurrent parity and a fixed attention
width bucket. Token ID, text position, indexed KV write position, and causal mask are inputs
updated for each execution; they do not change graph identity within that bucket. The six
attention layers share the same indexed position. A graph reads only committed recurrent
state, stages the opposite parity, and advances parity only after complete compute and output
readback. The prefill graph remains kind 0 with its existing prefix policy. When width changes,
invalidate and rebuild the affected parity graph; a failed step cannot publish recurrent state.

| Case | Implementation | Exact regression |
| --- | --- | --- |
| Construction and malformed kind | `ggml_ffi`, `runtime_execution`, and real/stub shims accept kind 2 as decode semantics with distinct context and key; reject all other new kinds before array access. | `runtime_device_smoke` plus C shim graph owner test exercise independent preparation, bad kind, and row index admission. |
| Success and reuse | `runtime_qwen35_model` and `runtime_qwen35_attention` build fixed-width indexed decode graphs for both parities; `runtime_generation` selects parity and updates all inputs. | Real 0.8B Metal owner executes at least three sequential tokens, compares full logits with the pinned llama.cpp oracle, and observes reuse on a repeated parity. |
| Failure, early exit, and cleanup | `runtime_generation` publishes state only after a successful graph and output read; graph invalidation releases one parity's transient context without touching resident state or the other graph. | The generation owner injects a failed step, checks unchanged parity, then closes and reopens a session without state leakage. |

The focused real Metal smoke now prepares a prefill graph and both decode parity graphs under
one 96 MiB metadata budget. Each decode graph has a fixed 256-token attention view, reads
indexed write positions at execution, and uses a mask for future rows. The loader initializes
the attention planes to zero because the full-width view can include unwritten rows. Four
successive tokens `[0, 23066, 0, 0]` match the same-pin Metal llama.cpp full logits at all
248,320 coordinates: maximum absolute differences are 0.0004912, 0.0002388, 0.0002618,
and 0.0005222. The fourth step reuses decode parity 1's prepared graph once without
invalidation. This is a local graph owner checkpoint. A provider session, longer input,
request latency, and a faster-than-llama claim remain unverified.

### Batched text prefill contract

The next native consumer packs 1..128 prompt IDs in one prefill graph at a validated prefix
position. Token, four-plane text position, and causal mask inputs have shapes `[T]`, `[4,T]`,
and `[W,T]`; `W = attention_width(prefix + T, context)` and the mask excludes all keys after
each query's absolute position. Recurrent convolution joins the committed `(kernel-1)` history
with a contiguous `[T, channels, 1]` projected token block, retaining only its final
`(kernel-1)` values. Gated DeltaNet receives Q/K `[state_size, groups, T]`, V/gate/beta
`[state_size or 1, dt_rank, T]`, and one committed state, with pinned `K=1`; only the final
state is staged. Full-attention layers write all T K/V rows to the retained-F16 cache before
the Flash Attention node reads the valid prefix. Each layer's residual/FFN remains `[n_embd,T]`;
the tied output projection reads only the final token's hidden vector. The graph publishes its
recurrent parity and attention prefix only after a successful complete compute and logits
readback. A failed chunk makes the session unusable until reset; it never advertises an
advanced prefix. Chunk width, start position, attention width, final-output selection, and
parity are part of topology identity. This implements the already-settled provider contract
above, without a new public CLI or artifact format.
The existing thin ggml boundary lacks a strided 3-D view and a 4-D reshape needed to split
head-interleaved Q/gate and convolution Q/K/V across T tokens. Add only `op_view_3d`, with
dimensions and selectors into the source's own strides, and `op_reshape_4d`, with a checked
element product. C derives byte strides and offsets and rejects out-of-range spans before
calling ggml; Align never supplies raw byte arithmetic. The real and stub shims share the
same refusal statuses. These are existing pinned ggml operations, so they require no new
Align language surface.

| Case | Owner and acceptance |
| --- | --- |
| Construction | `runtime_qwen35_recurrent`, `runtime_qwen35_attention`, `runtime_qwen35_ffn`, and `runtime_qwen35_model` build one coherent T-token graph; the owner smoke checks shapes at T=1 and T=128 before compute. |
| Success | A real 0.8B Metal prefill of `[0, 23066, 0, ...]` with T=128 compares all 248,320 last-token logits against one same-pin llama.cpp 128-token prefill and the qualified sequential oracle; a following decode checks state and KV publication. |
| Malformed input and failure | The builder refuses T=0, T>128, prefix overflow, wrong input extents, or mismatched state geometry before ggml's asserts. The generation owner injects a compute failure and checks that no token is returned and no prefix/parity is published. |
| Early exit and cleanup | A final prompt chunk selects one output token, and the session releases graph and buffers on cancellation, EOG, or error. The provider owner runs two requests to check no state leakage. |

Local Metal checkpoint (Apple M1, pinned ggml and llama.cpp `bb4caa7`, 0.8B Q4_0,
128 IDs `[0, 23066, 0, ...]`, 512 context, Flash Attention on): one warmed
batched prefill and the following token-0 decode match the reference at all
248,320 logits with maximum absolute difference zero. The prefill timing starts
after graph preparation and one identical warm compute, and ends before logits
readback. Five alternating align-llm/llama.cpp pairs after removing the extra
recurrent QKV materialization measured 109.78/104.70, 109.87/105.88,
109.27/105.81, 108.93/104.14, and 109.15/104.27 ms. Removing the prefill
attention query materialization then measured 108.76/104.92, 107.80/104.44,
108.08/104.43, 108.16/104.65, and 107.91/104.55 ms. The final medians are
108.08 and 104.55 ms; align-llm remains slower in all five pairs. An initial
three-pair control with the recurrent materialization measured about 122 ms
against 104–106 ms. This focused graph measurement excludes load, tokenizer,
sampler, logits readback, provider startup, and a complete request. Its candidate
improvement is below the 15% material floor and supports no faster-than-llama
claim. CPU and CUDA remain unmeasured pending native session qualification.

The local one-shot `--provider align-runtime` Metal path now loads the source-bound
pack, allocates fresh attention and recurrent state, runs 128-token prompt chunks,
and greedily decodes with two parity graphs. `scripts/run-qwen35-generation-smoke`
compares its output and token counts with the pinned Metal llama.cpp oracle for
31-, 200-, and 330-token prompts, each with three generated tokens; all pass.
The latter two cases cross a chunk boundary and a 256-to-512 attention-width
boundary. The retained `--runtime-session` now uses one weight load and clears its resident
state between requests. Six requests, including malformed-sampling recovery and max-one early
exit, match the same-pin oracle. Execution-failure injection, a strict complete-request speed
comparison, and a contemporary llama.cpp comparison remain open for later qualification; no
faster-than-llama.cpp claim is active.

Align-owned full-model graph construction remains implementation work, not an
upstream Align language request. A same-pin reference transcript should use the 0.8B model and at least
one prompt that crosses prefill and two decode steps. No performance result is inferred from the
tokenizer or Model IR checks.

The local native admission checkpoint `runtime_qwen35_geometry.parse_snapshot` consumes the verified
Model IR document and reads four `snapshot_i32_array` values from the same GGUF snapshot. It checks
the model dimensions, finite normalization epsilon and positive RoPE base bit patterns, and
section sum before deriving the six full-attention layers, 18
recurrent layers, and per-layer state extents. `runtime_qwen35_geometry_smoke` passes on the
real 0.8B GGUF and rejects an altered section sum. Full-model graph execution, state commit,
provider routing, and numeric parity are still open.

### 0.8B reference bottleneck checkpoint (2026-09-24)

Before implementing an optimization, the pinned `bb4caa7` llama.cpp reference was built with
CPU/Accelerate and Metal on an Apple M1. Both builds used the same Qwen3.5-0.8B Q4_0 file,
four CPU threads, 128 prompt tokens or 32 generated tokens, three repetitions, and an explicit
Flash Attention setting. These are reference measurements, not align-llm results or a shipping
speed claim. The CPU build with Flash Attention off measured 464.98 prompt tok/s and 55.32
generation tok/s. The Metal build with all layers offloaded and Flash Attention off measured
1180.77 prompt tok/s and 61.85 generation tok/s; enabling Flash Attention measured 1195.65 and
63.87 tok/s respectively. The three generation samples were 499.74, 503.82, and 551.64 ms
without Flash Attention, versus 504.68, 499.55, and 498.85 ms with it. This short test cannot
establish a stable Flash Attention win.

A separate 1,024-token CPU generation run sampled at 1 ms for 10 seconds attributed the largest
active stacks to quantized GEMV (`ggml_gemv_q8_0_4x4_q8_0`: 8,391 samples;
`ggml_gemv_q4_0_4x4_q8_0`: 6,630); Gated DeltaNet had 212 and SSM convolution 67 top-of-stack
samples. Samples across threads are not a normalized per-kernel time budget. A 10-second Metal
System Trace and host sample were collected, but the exported shader-profiler table had no rows;
host waits cannot attribute GPU kernel duration. Thus changing DeltaNet math, RoPE, or Flash
Attention first has no measured 0.8B decode justification. The native graph should preserve
ggml's quantized matrix operations and reuse the whole graph/session; its measured cost, including
host launch and state handling, is the next actionable bottleneck investigation.

The first native optimization campaign starts only after real 0.8B prefill and multistep decode
parity. Fix the model hash above, pinned ggml, backend, prompt and 128-token generation request;
compare an owner-tested native control with one proposed change in five alternating pairs on the
same host, with exact outputs and token counts. Record startup, prompt, and generation clocks
separately. The material floor is at least 15% lower median paired generation latency with at
least four of five pairs faster, and no more than 5% prompt or startup regression. Preparation
is capped at 3,600 seconds and the paired experiment at 900 seconds, with a 120-second request
limit. A missing parity result or invalid receipt is an unmeasured outcome, not a speedup.
An evaluated candidate was a GPU argmax node after the output projection. Its control reads and
scans all 248,320 F32 logits after each step; the candidate reads one I32 token id. Keep the
full-logit owner path for exact vector parity. Require identical generated ids and text on the
31-, 200-, and 330-token real prompts, including retained requests. Use the same 3,600-second
preparation and 900-second paired-measurement ceilings and the 15% generation-latency floor
above before calling it a material optimization; record full-request latency separately.
The candidate was reverted after review found that reading only an index drops the existing
nonfinite-logit refusal. Its observed complete-request latency also did not meet the material
floor. The retained session continues to read F32 logits and use the checked greedy selector.
The following prefill experiment raised the native chunk ceiling from 128 to 256 tokens so a
200-token coding prompt uses one graph. Its acceptance is exact 31-, 200-, and 330-token
provider and retained-session token parity, a passing 128-token full-vector owner, and no
unsupported Flash probe. Compare the 200-token/16-token request against the unchanged
128-token-chunk control in five alternating pairs under the same preparation, measurement,
15% material floor, and 5% regression limit. Revert the larger chunk if it fails parity or
the paired floor.
On Apple M1 with the same source/model and five alternating retained 200-prompt/16-generation
requests after two warm requests per process, the 128/256 controls measured 496.70/495.02 ms
median. The 256 graph won three of five pairs, missed the 15% floor, and was reverted. The
generated text matched in all ten measured calls. This was an experiment, not a shipping speed
claim or a same-pin llama.cpp comparison.
The next prefill experiment omitted the output normalization, vocabulary projection, and argmax
for every prompt chunk except the last. Intermediate chunks must still execute and commit all
recurrent and attention state nodes. Its control is the owner-tested 128-token session above;
the candidate must preserve exact generated IDs and text on the 31-, 200-, and 330-token
prompts, including retained requests. Compare the 200-token/16-token request in five alternating
pairs under the same 3,600-second preparation and 900-second measurement ceilings. Require the
15% paired generation-latency floor, four of five wins, and at most 5% prompt or startup
regression for a material speed claim. Record the same-pin llama.cpp result separately.
On the Apple M1, the control/candidate 200-prompt/16-generation medians were 521.16/515.26 ms
after two warm requests in each of five alternating pairs. The candidate won three of five
pairs with exact generated text, missed the material floor, and was reverted. Temporary timing
probes placed retained-session prefill near 200 ms and decode near 300 ms; the same-pin llama.cpp
diagnostic placed its prefill and first token near 180 ms and remaining decode near 300 ms. These
are one-host diagnostics, not a faster-than-llama.cpp claim.
After #297, a separate Apple M1 diagnostic used identical 200 prompt IDs and 16 greedy output
tokens with matching text. Five retained requests after two warm requests measured medians of
519.44 ms for align-llm and 478.13 ms for pinned llama.cpp. The runs were sequential rather than
alternating pairs. A 15-second host sample of repeated align-llm requests placed approximately
84% of the main-thread samples in Metal command-buffer completion waits; this cannot identify
which GPU kernels consumed the interval. Obtain shader-level or equivalent graph-operation timing
before selecting a new compute optimization, and compare contemporary llama.cpp separately.
A separate five-pair alternating diagnostic with 200 identical prompt IDs and 32 identical
generated tokens used two warm requests per process. Align-llm/llama.cpp median complete-request
times were 851.45/805.13 ms, with align-llm slower in all five pairs. The earlier sequential
32-output comparison had the opposite ordering and is discarded as speed evidence. Metal graph
debug logs showed 187 quantized matrix multiplications and 18 Gated DeltaNet operations in each
decode graph on both paths; graph node counts alone cannot attribute GPU time. No faster-than-
llama.cpp claim follows from these diagnostics.
Contemporary llama.cpp HEAD `53ed051ce5e8193652e449f43216ca3859454f49` built with Metal
and produced the same 200 prompt IDs and 32-token text. Five alternating pairs on the Apple M1
measured align-llm/current llama.cpp medians of 841.30/748.39 ms; align-llm was slower in all
five. This is a separate reference from the pinned `bb4caa7` comparison. A scratch rebuild of
the existing shim against the contemporary ggml headers and bundle exposed a changed private
Metal graph-optimization ABI: its callback now must register allocation dependencies. The old
two-argument invocation asserts at graph preparation. Omitting optimization in an isolated
diagnostic yielded correct 32-token text but a warmed 845.24 ms median, so merely replacing the
backend binary is not a speed solution. The new optimizer registered dependencies on this dense
Qwen3.5 graph. Any adoption must preserve them through the workspace allocator and requalify
CPU, Metal, and CUDA consumers before a speed or compatibility claim. The contemporary ggml
scheduler adds `GGML_OP_NONE` dependency nodes to its allocation graph after Metal optimization;
the shim currently calls a private backend vtable and allocates its graph directly through
`ggml_gallocr`. A supported scheduler integration or equivalent dependency-preserving allocator
must be designed and qualified before updating the production pin.
An instrumented retained Align run used dyld interposition around
`align_gpu_graph_compute`, `ggml_backend_graph_compute`, and
`ggml_backend_tensor_get` without changing source or output. Four identical
200-prompt/32-output requests took 845-859 ms each. For the last three requests,
the two prefill graphs took 187-188 ms, the 31 decode graphs took 603-617 ms,
and 33 full-logit reads took about 3 ms, totaling 791-804 ms in graph compute.
Interposition adds measurement overhead and these are sequential diagnostics,
not a paired speed claim. They rule out full-logit readback as the primary wall
cost. A follow-up five-pair alternating same-pin probe instrumented Align's synchronous
`ggml_backend_graph_compute` and llama.cpp's scheduler compute plus synchronization,
using the third identical 200-prompt/32-output request after two warm requests per
process. Output text matched on every pair. Align/llama.cpp medians were 762.73/710.02 ms
request wall, 743.41/687.10 ms graph execution, 196.48/178.23 ms prefill, and
546.73/508.76 ms for the 31 decode steps. Align was slower in all five pairs.
The absolute times differ from earlier uninstrumented pairs under changing host
conditions, but the paired phase gap shows that same-pin graph execution accounts
for most of this measured request difference. The graph timings include scheduler
and synchronization work; they do not identify an individual GPU kernel. Align
uses two prefill chunks for 200 tokens while this llama.cpp case uses one, and its
decode graph has a fixed padded attention view. These graph differences are candidates
for the phase gaps, not proven causes. Five alternating contemporary llama.cpp default/Metal-optimization-
disabled pairs used the third request after two warm requests per process. Their
medians were 747.07/754.01 ms, and default won three of five. This does not show
that Metal graph optimization explains the gap to align-llm.

The next bounded decode candidate passes the fixed rounded width to the existing indexed KV
write, so its returned view covers the resident padded prefix and the Flash Attention mask
continues to exclude unwritten positions. This removes the per-layer temporary padding path
without changing the KV ABI, row index, valid prefix, graph key, or output contract. The
candidate must pass four-step full-vector parity, the retained real-model owner including
request reset, and a five-pair 200-prompt/32-output same-pin control comparison. Allow at
most 1,800 seconds for implementation and owner checks and 900 seconds for measurement.
Ship a performance claim only with at least 15% lower paired median, four of five wins,
and no greater than 5% prompt or startup regression; otherwise revert the executable change.
The candidate passed the real six-request generation owner with exact output, but five
alternating instrumented 200-prompt/32-output control/candidate pairs measured
768.23/766.71 ms request medians and three candidate wins. Decode graph medians were
545.07/546.38 ms. It missed the 15% and four-win floors, so the source change was
reverted. This shows that padding the indexed KV write view is not the main decode gap.

The pinned Metal graph debug stream for one decode has the same 187 `MUL_MAT`, 18
`GATED_DELTA_NET`, and six `FLASH_ATTN_EXT` operations on Align and llama.cpp.
It shows 18 versus six `CONT` and 42 versus 36 `CPY` operations respectively;
llama.cpp also has more `GET_ROWS` operations, so total node count is not a cost
ranking. The extra Align continuations are in the six full-attention blocks.
The optimized per-unit LLVM IR for `runtime_qwen35_generation` shows a builder,
SHA-256, hex encoding, and string clone for `key` on every decode iteration.
The optimized `runtime_generation.greedy` path loads four `f32` logits at a time
and uses vector compares/selects without copying an aligned input. The compiler
warns about a 184-byte geometry copy at session creation, not on the decode loop.
These are compiler-output observations, not proof that key creation causes the
Metal graph-time gap.

A second bounded graph-order candidate registers the independent attention Q, V,
and K projection roots before the resident KV writes, matching the pinned llama.cpp
`build_attn` expansion order. It changes graph registration only and must preserve
the four-step full-logit oracle, the six-request real owner, topology/memory admission,
and paired output text. Allow at most 1,800 seconds for implementation and owners
and 900 seconds for five alternating 200-prompt/32-output pairs. Require at least
15% lower paired request median, four of five wins, and no greater than 5% prompt
or startup regression for a material optimization; otherwise revert the change.
The six-request real owner passed after the graph-order change. Five alternating
control/candidate pairs measured 784.79/788.69 ms request medians and three
candidate wins; decode graph medians were 561.29/561.20 ms. The candidate missed
the floor and was reverted. Registration order alone did not close the gap.
The pinned debug logs marked 194 Align versus 286 llama.cpp nodes as concurrent
across their respective decode graph groups, but a separate five-pair
default/concurrency-disabled diagnostic did not give a consistent causal result:
Align medians were 801.07/782.26 ms with two default wins, while llama.cpp medians
were 732.42/740.00 ms with four default wins. Order, thermal state, and changed
kernel scheduling limit that toggle experiment; the node labels cannot be read
as elapsed GPU time.
The same pinned ggml Metal graph-optimization toggle was also paired five times
per implementation, alternating default and disabled, with exact output text.
Align default/disabled medians were 776.13/794.68 ms with four default wins;
llama.cpp medians were 737.93/751.05 ms with five default wins. The optimizer
helps both paths under this diagnostic and does not explain why Align is slower.
In the pinned decode debug graph, the only differing operation counts are Align/
llama.cpp `CONT` 18/6, `CPY` 42/36, `GET_ROWS` 1/37, and `MUL` 42/43.
The detailed Metal tensor trace identifies that intervening `CPY` as the
256-element attention mask conversion from F32 to F16, not a KV-cache copy.
`runtime_qwen35_attention.build_many` calls `runtime_attention.prepare_mask`
in each of the six full-attention layers; the shim implements that call with
`ggml_cast`. The input mask is shared, but the graph currently converts it six
times. The additional twelve `CONT` operations are explicit `ggml_cont_3d`
requests for K and V after permutation in those layers: the indexed KV-write
shim currently requires a contiguous source tensor. Both implementations
also materialize the attention gate once per layer. The shim's `slot_copy`
copies a tensor handle only. The other 36 `CPY` operations write two recurrent
state tensors in each of 18 layers and are present in both graphs. These are
application graph and ggml storage-layout choices, not observed Align compiler
copies or evidence of a missing language feature. Counts alone do not assign
the measured decode latency gap; the padded-view candidate above did not help.

The evaluated bounded candidate converted the shared F32 attention mask to F16 once
per graph in `runtime_qwen35_model`, then passed that borrowed F16 tensor handle
to every full-attention layer. In the candidate,
`runtime_qwen35_attention.build_many` required the prepared mask at its existing
`MASK` slot; its shape, values, graph lifetime,
allocation owner, and error result were unchanged. No persisted format or cache
identity changed. Construction bound the prepared handle before the first
attention layer; successful prefill and decode reused it; invalid shape and
failed graph construction retained the existing refusal and cleanup path. The
real six-request generation owner covers the affected model, attention, and
session boundaries, including reset and malformed request recovery. A Metal
graph trace confirmed that the six F32-to-F16 mask `CPY` nodes became one.
Allow at most 1,800 seconds for implementation and owners and 900 seconds for
five alternating 200-prompt/32-output same-pin control/candidate pairs with
exact output text. Require at least 15% lower paired request median, four of
five wins, and no more than 5% prompt or startup regression for a material
optimization; otherwise revert the executable candidate.
The real six-request generation owner passed against pinned llama.cpp. The
decode Metal graph reduced `CPY` from 42 to 37 while `CONT` stayed at 18.
Five alternating control/candidate 200-prompt/32-output pairs with identical
text measured 752.80/786.32 ms request medians and three candidate wins;
prefill medians were 189.41/201.78 ms and decode graph medians were
535.75/558.65 ms. Host conditions varied across pairs. The candidate missed
the 15% and four-win floors and was reverted. Removing five 256-element mask
conversions did not close the same-pin execution gap.

Another bounded candidate used the pinned llama.cpp attention-cache layout
for the six full-attention layers: resident K and V each have logical shape
`[head_dim * kv_heads, capacity, 1]`, with all heads of one token adjacent.
`runtime_qwen35_load` owns the resident allocation, and
`runtime_qwen35_attention` reshapes the contiguous projected K/V to that
write shape and presents the written prefix to Flash Attention as a strided
`[head_dim, width, kv_heads, 1]` permutation. The indexed KV-write ABI,
position validation, F16 policy, graph key, total resident bytes, and
success-only state publication remain unchanged; no persisted artifact or
schema changes. Prefill, decode, rounded masked tail, request reset, and
malformed-input recovery must pass the real six-request generation owner.
The graph trace must show twelve fewer K/V `CONT` nodes in decode and the same
six Flash Attention and 18 recurrent operations. Allow 1,800 seconds for the
candidate and owners and 900 seconds for five alternating same-pin
200-prompt/32-output control/candidate pairs. Ship a material speed claim only
at 15% lower paired request median, four of five wins, and no more than 5%
prompt or startup regression; otherwise revert the executable candidate.
The real six-request generation owner passed against pinned llama.cpp, and the
decode graph changed from 18 to six `CONT` nodes while preserving six Flash
Attention and 18 Gated DeltaNet nodes. A detailed trace confirmed that the
Flash Attention K/V strides now match llama.cpp on the three active dimensions.
Five alternating control/candidate 200-prompt/32-output pairs with identical
text measured 772.08/774.50 ms request medians and two candidate wins;
prefill medians were 188.45/189.48 ms and decode graph medians were
551.60/552.89 ms. The change missed the 15% and four-win floors and was
reverted. Eliminating the twelve K/V materializations did not close the gap.
An Apple M1 Metal System Trace diagnostic split both pinned backends into eight
command buffers per graph in disposable builds. Both still produced the same
200-prompt/32-output text. The short GPU intervals were roughly 1.2–1.4 ms
for Align and 1.0–1.3 ms for llama.cpp; the recurring longer intervals were
roughly 5.6 ms for both. This split changes command-submission behavior, and
Xcode's trace exported no shader-profiler rows on this host, so these intervals
do not identify a slower kernel or support a production change. In the normal
unsplit debug graph, all 187 decode matrix multiplications matched the pinned
llama.cpp reference by quantized weight type and shape and by F32 input shape
and stride. The 18 Gated DeltaNet and 18 convolution nodes also matched on
their principal input shapes and strides. The remaining same-pin GPU execution
gap is unresolved; preserve the exact baseline and revisit it when kernel-level
timing or a specific operation-level hypothesis is available.
The first measured seam is retained F16 K/V for the six full-attention layers. The control
retains F32 K/V and casts its fixed 256-token views to F16 before each Flash Attention call;
the candidate uses the already-qualified cached-F16 policy at allocation and indexed-write
boundaries. The experiment costs at most 3,600 seconds of preparation and 900 seconds for five
alternating control/candidate pairs. It must retain four-step full-vector parity and clear the
15% paired generation-latency floor above before it is called a material optimization. A
separate same-pin llama.cpp comparison is required for a faster-than-llama claim.
The focused owner and independent llama.cpp oracle expose `--decode-bench` for diagnosis:
after four matching warm steps `[0, 23066, 0, 0]`, both execute 124 more token-0 steps and
obtain full logits before every next step. The JSON result reports `tokens = 124` and
`elapsed_ns`; it excludes load, prefill, sampling, and session startup. On one Apple M1,
five alternating F32/F16/reference triples yielded median 2.375/2.307/2.188 seconds.
F16 beat F32 in five of five pairs but beat the same-pin llama.cpp reference in zero of five.
Its roughly 3% control improvement misses the 15% material floor. The retained-F16 work
therefore remains a local candidate; this diagnostic does not support a full-request or
faster-than-llama claim. The optional final-logits dump also compares the full 248,320-vector
at step 127 after the same fixed-token sequence; the Metal result was bit-identical to
the same-pin llama.cpp reference. This verifies long sequential state parity, not batched
text prefill or generated-token sampling. An attempted removal of the attention Q/K/V `CONT` nodes kept
four-step exact logits but improved only three of five pairs against F16 and one of five
against llama.cpp, so that change was discarded.
After parity, run a separate five-pair same-model comparison against `llama.cpp` at the pinned
ggml revision and report a contemporary llama.cpp revision as a second, separately labeled
reference. Fix the GGUF hash, token IDs, generated output, context, sampler, backend, GPU
offload, Flash Attention setting, and warm/cold condition for each pair. Report prompt,
generation, complete request, and startup results without combining them. A native-control
versus candidate improvement does not establish a llama.cpp speedup; the real reference pairs
must show it for the named case. Preserve the older Qwen2 campaign's distinction between
same-ggml and current-reference results when interpreting Qwen3.5.

## First-boundary implementation map

`src/main.align` dispatches all three architecture-sensitive frontdoor verbs to
`src/frontend_qwen35.align`. That frontend owns ordered metadata admission, the split
recurrent/full-attention role and shape tables, tied output resolution, and the block plan;
`src/model_ir.align` and the GGUF reader remain unchanged. `src/alignpack.align` appends role ids
29–38 without renumbering prior ids. `scripts/alignpack_reader.py` mirrors the persisted role table.

`python3 scripts/qwen35_frontdoor_smoke.py` covers construction, success, missing vocabulary
metadata, malformed metadata and shape, early refusal without a pack, and pack verification on an independent synthetic four-layer
GGUF. The unchanged `scripts/run-model-ir-smoke` and `scripts/run-alignpack-smoke` retain Qwen2,
gpt-oss, and OLMoE coverage; the role-list assertion now checks all appended ids. The real 0.8B
GGUF passed `--model-ir` (320/320 assigned, 50 blocks, `size_sum_ok: true`), `--pack`, and
`--pack-verify` locally. This is evidence for the first boundary only; the native text matrix and
its oracle remain next work.
