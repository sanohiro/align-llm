# Qwen3.5 text support

Status: active. This plan owns the `qwen35` extension; the existing Qwen2 and OLMoE contracts remain in their own plans.

## Evidence and delivery order

The first real consumer is `ggml-org/Qwen3.5-0.8B-GGUF`, file `Qwen3.5-0.8B-Q4_0.gguf` (563,036,064 bytes; SHA-256 `57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`). Its GGUF inspection at the current `.llama-revision` reports architecture `qwen35`, 24 layers, 320 tensors, embedding width 1024, feed-forward width 3584, vocabulary 248320, context 262144, full attention every fourth layer, and 18 recurrent Gated DeltaNet layers. The six full-attention layers and 18 recurrent layers have distinct tensor sets. The file declares `tokenizer.ggml.pre = qwen35` and has a tied output embedding. The current `--model-ir` refuses it with `R1_UNSUPPORTED_ARCH`; this is the baseline, not a regression.

The first independently useful consumer boundary is `--model-ir` plus `--pack` for this real GGUF. It permits validated model inspection, complete tensor coverage, and an owned layout artifact without claiming inference. The next boundary is text-only native `align-runtime` prefill and decode through `--provider align-runtime`; it includes Qwen3.5 tokenization, hybrid recurrent/attention state, and reference comparison. Vision, MTP/speculative heads, MoE, and 27B are later consumers. Do not infer their support from a passing 0.8B case. No speed claim is made by this work.

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

The first boundary adds these stable role ids after 28: `post_attention_norm` 29, `attn_qkv` 30, `attn_gate` 31, `ssm_conv1d` 32, `ssm_dt` 33, `ssm_a` 34, `ssm_beta` 35, `ssm_alpha` 36, `ssm_norm` 37, `ssm_out` 38. Existing ids never move. The frontend uses the GGUF's declared `attention.key_length` and `attention.value_length`; it does not derive either from `embedding_length / head_count`. The pinned llama.cpp reference selects interleaved M-RoPE (`GGML_ROPE_TYPE_IMROPE = 40`), which the Model IR records. `rope.dimension_sections` is an array of four INT32 values and is validated in the native text boundary before graph construction. The model's `full_attention_interval` fixes the block type; no inferred tensor fallback is permitted.

## Closure matrix for the first boundary

| Phase | Owner and exact regression |
| --- | --- |
| Construction and validation | `frontend_qwen35.prepare` validates the architecture, required metadata and per-layer roles; `run-model-ir-smoke` covers the real 0.8B file and synthetic malformed metadata. |
| Success and format | `main` dispatches `--model-ir` and `--pack`; `model_ir` retains one renderer; `alignpack` maps appended roles. Real-file owner asserts schema, 320-tensor coverage and packed layout verification. |
| Failure and malformed input | The frontend returns the first existing R1 error before any pack write. Focused fixtures remove a required key/tensor and change one tensor shape. Existing Qwen2 and OLMoE smoke owners remain unchanged. |
| Early exit and cleanup | The borrowed GGUF table and partially built plan end with the command. `alignpack` retains its existing atomic write/cleanup path; failed derivation creates no pack. Focused owner asserts refusal and no destination. |
| Reused modules | `gguf` parses the same table once, `model_ir` consumes the plan without architecture dispatch, and `alignpack` resolves every appended role. `run-model-ir-smoke` and `run-alignpack-smoke` own consistency. |

Before publishing each boundary, map these cells to the final diff and passing commands or an explicit deferral here. The native text boundary needs a separate closure matrix for session construction, recurrent state updates, failure, rollback, and cleanup before its implementation begins.

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
