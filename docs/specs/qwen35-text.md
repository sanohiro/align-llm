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
| Construction | `tokenizer_qwen2` supplies the already-qualified `qwen35` prompt identity; `runtime_bundle` and `runtime_generation` derive the hybrid geometry, role table, KV and recurrent state sizes before device allocation. | `scripts/run-qwen35-generation-smoke` compares real-file tokenizer metadata, prompt ids, and rejected geometry. |
| Success | `runtime_qwen35` builds full-attention layers and Gated DeltaNet layers using the pinned ggml operations; `provider_runtime` routes the native request, and `runtime_generation` commits full-attention KV plus recurrent state after a successful step. | `scripts/run-qwen35-generation-smoke` compares real 0.8B prefill and at least two decode tokens with the pinned llama.cpp oracle and checks provider text and token counts. |
| Failure and malformed input | `runtime_bundle` rejects missing roles, invalid rope sections, unsupported quantization, or state dimensions before graph allocation; `runtime_generation` propagates compute and state-update failures. | The same owner changes one role/section and injects one compute failure, asserting an error and no response. |
| Early exit and rollback | The session retains its prior committed KV and recurrent state until a step succeeds; an EOG, cancellation, or error releases in-flight graph/input/output buffers without advancing either state. | The same owner compares a failed or early-ended session with a fresh session on the next request. |
| Cleanup | `runtime_generation` and `runtime_session_io` release session KV, recurrent state, graph, and device allocations on every terminal path; `provider_runtime` closes the request. | The same owner runs two consecutive requests and checks state isolation and allocation counts. |
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
For the first one-sequence text session, retain six attention KV pairs and two copies each of
the 18 recurrent layers' convolution history and DeltaNet state: 12 + 18 * 4 = 84 resident
F32 tensors. A recurrent layer's convolution state has shape `[3, 6144, 1]` and its DeltaNet
state has shape `[128, 128, 16, 1]`. `runtime_qwen35_state` owns one active parity for all
recurrent layers. Each graph reads the active pair and writes the next pair. Only a successful
full step flips parity and publishes the token prefix; a failed or cancelled step leaves the
active pair and prefix unchanged. The inactive pair may contain partial results and is overwritten
on the next attempted step. The first session does not retain extra DeltaNet snapshots (`K=1`).
The owning smoke must check layer-to-state indices across the 3/4 and 7/8 block boundaries,
84 unique allocations, a successful flip, and unchanged active indices on failure before the
full model oracle is attempted.
The plan must validate the four rope sections from source GGUF, model/pack identity, block roles,
all state extents and the selected ggml op shapes before graph creation. `ggml_rope_multi`,
`ggml_ssm_conv`, and `ggml_gated_delta_net` exist at the pin and now have checked shim symbols.
The first text session retains only the final DeltaNet state, so its ABI fixes the snapshot
count at one. The ggml-free stub refuses execution of these three numeric operations explicitly;
passing the shim's shape checks does not establish the native model's numerical correctness.
Align-owned state, role loading, and graph construction remain implementation work, not an
upstream Align language request. A same-pin reference transcript should use the 0.8B model and at least
one prompt that crosses prefill and two decode steps. No performance result is inferred from the
tokenizer or Model IR checks.

The local native admission checkpoint `runtime_qwen35_geometry.parse_snapshot` consumes the verified
Model IR document and reads four `snapshot_i32_array` values from the same GGUF snapshot. It checks
the model dimensions and section sum before deriving the six full-attention layers, 18
recurrent layers, and per-layer state extents. `runtime_qwen35_geometry_smoke` passes on the
real 0.8B GGUF and rejects an altered section sum. This is a construction check only; role
loading, graph execution, state commit, provider routing, and numeric parity are still open.

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
