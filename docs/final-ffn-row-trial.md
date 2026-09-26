# Qwen3.5 final-layer one-row FFN trial

## Decision

Keep `ALIGN_LLM_PREFILL_LAST_FFN_ROW=1` as a selectable experiment. The absent
setting and explicit `0` use the established graph. The real-model prefill phase
improved in four of five worker pairs in each tested case, but the whole HTTP/SSE
request effect is mixed and small. A negative-control request with a one-row
final chunk also shows timing movement. The evidence does not justify changing
the default or claiming a llama.cpp request win. No fixed percentage gate was
used. The full raw worker and HTTP/SSE samples, prompt IDs, independent summary,
numerical checks and identities are in
`../eval/benchmarks/final-ffn-row-metal-2026-09-26.json`.

This branch starts the trial at `9e1719c9`. The preceding default-on
final-prefill output elision stays in force. The new Align session choice is read
once before weight allocation. Normal and streaming generation select the last
row only in the final prompt graph with `count > 1` and requested logits. The
model builder takes views of both the last input residual row and last attention
output row after all attention/state-producing work has been built. The final
FFN and output head then consume one row. Earlier layers, intermediate chunks,
one-row chunks and decode use the existing graph. The actual row choice enters
the graph cache identity; explicit `0` preserves the prior identity. Unsupported
builder combinations and invalid environment values fail early.

Align owns the graph selection, session, model semantics and generation loops.
GGML still supplies graph allocation, Metal kernels and synchronization; the
views use its existing thin ABI. No new retained device buffer, weight copy,
state owner, Python inference path or Metal kernel was introduced. The pinned
llama.cpp Qwen3.5 builder contains an optional earlier output-row selection, but
ordinary context initialization leaves that guard false. This experiment tests
the idea in the current Align consumer, with its own correctness and cost record.

## Correctness and execution evidence

The 2B and 0.8B exact pinned-llama generation and HTTP/SSE owners pass with the
new flag. Their coverage includes repeated requests, sampling recovery, one-token
exit, reset and stream disconnect. The 2B generation owner also passes with the
native SwiGLU experiment enabled together with this flag; timing never combines
them. Empty, `2`, `true` and `01` flag values refuse before allocation. The old
binary versus the new binary with the flag off is bit-identical across 96 captured
vectors at chunk width 128.

Actual 2B full-vocabulary logits were captured for retained requests
`128/1, 129/3, 256/3, 257/3, 512/3, 513/3, 700/64, 64/16` (input/generated
tokens). For each of chunk widths 128, 256 and 512, same-binary off/on comparison
checks 96 vectors and 23,838,720 floats, or 71,516,160 floats in total. Maximum
absolute difference is 0.00361634, below the **predeclared** 0.01 bound; every
argmax agrees. All 88 decode vectors per width are bit-identical. Only five to
seven final-prefill vectors per width differ. This is a rounding-changing trial,
not an exact-logit claim. Nonfinal baseline vectors and all raw captures remain
in the Git-common-directory diagnostic archive.

An independent diagnostic hashes every one of the 84 resident state planes after
each synchronized graph in a `200/3` then `64/3` retained session. All 588
matching full-plane metadata and hashes agree. The first nonfinal graph is 1,115
nodes in both modes; the final prefill graph is 1,148 off and 1,150 on. Both have
187 `MUL_MAT` operations and the same persistent `CPY`/`SET` counts. The two
additional nodes are row views; the matrix shape and selected Metal kernel,
rather than the operation count, change. Decode graph nodes are unchanged.

The instrumented final-prefill trace saw an additional
`kernel_mul_mv_q4_0_f32_nsg=2` specialization when enabled, two command buffers
per graph in both arms, and equal reported peak Metal resource allocation of
1,290,174,464 bytes. One intrusive graph interval was 168.58 ms off versus
165.897 ms on. Shader compilation and full-state hashing contaminate this
diagnostic; it is **not** a repeatable shader or request timing result. Equal
reported allocation does not establish equal physical RAM pressure.

## Real-model measurement

Apple M1, 16 GiB, macOS 27.0 (26A428). The unchanged Qwen3.5-2B Q4_0 GGUF has
SHA256 `cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
The Q6_K output projection remains part of that same GGUF. Align pin is
`b20429be50d6ab889496a0589143320683b29aeb`; llama.cpp/ggml pin is
`bb4caa7540188872173c44d161602d9271386413`. Old/new Align binaries have
SHA256 `9a85befca878f6c2fc4ffbf03b034589c44c5d206bd3555824c007a0b4da3c47`
and `b84d97d88ee8cd4c091060e760872fb72ac278cc3b300b596c1e561469faa114`.
The pinned llama reference binary has SHA256
`f384a6a64603479cf5c675ba587aeafbd64a500c3129a0afdcd271dcf532717d`.
All Align arms use upload 0, chunk 128, final-prefill logits 1 and native SwiGLU 0;
only this flag changes. Prompt IDs, weights, generated counts and outputs match.
The llama reference uses its established 512 batch/microbatch, four threads and
Flash Attention; this batch handling difference is explicit.

Worker protocol: five alternating old/new/llama groups per case, two warm
requests in each process, then one measured request. Prefill and decode include
synchronized graph calls, not isolated shader time. Values below are marginal
medians in milliseconds; the percentage is the **median of paired** old-to-new
improvements and `wins` counts faster new samples.

| Input/output | Old/new prefill | Prefill paired; wins | Old/new decode | Old/new request | Request paired; wins | Llama request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 64/16 | 124.89 / 123.08 | +2.08%; 4/5 | 453.86 / 457.47 | 602.24 / 608.38 | -0.86%; 2/5 | 586.38 |
| 200/32 | 383.13 / 380.07 | +0.86%; 4/5 | 927.18 / 924.84 | 1349.35 / 1345.38 | -0.13%; 2/5 | 1320.23 |
| 330/64 | 603.83 / 594.45 | +1.64%; 4/5 | 1897.87 / 1884.48 | 2581.69 / 2550.20 | +1.37%; 5/5 | 2516.61 |

The old/new startup medians were 1047.55/1138.69, 1060.51/1159.13, and
1066.70/1076.89 ms in case order; llama startup medians were 438.75, 425.81
and 445.93 ms. OS file caching was uncontrolled, so these are construction-to-ready
samples, not disk-cold loading. The trial changes no loader. Decode is unchanged;
the 330/64 decode improvement cannot be assigned to this flag.

HTTP/SSE protocol: the **same candidate binary** runs in two retained servers
with explicit off/on settings. Serial requests have two warmup pairs and five
alternating pairs per mode/case. Numbers are paired median request improvements
in percent (positive favors on), followed by faster-on pairs. Every pair is in
the raw receipt. SSE text and finish match counted nonstream responses; SSE does
not expose a usage field.

| Input/output | HTTP | SSE | SSE first token |
| --- | ---: | ---: | ---: |
| 64/16 | +1.36%; 4/5 | -0.31%; 1/5 | -1.71%; 2/5 |
| 128/1 | +1.78%; 4/5 | +2.15%; 5/5 | +2.18%; 5/5 |
| 129/1 (one-row final chunk) | -0.26%; 2/5 | +0.87%; 5/5 | +1.36%; 5/5 |
| 200/32 | +1.08%; 4/5 | -0.61%; 1/5 | +1.51%; 3/5 |
| 330/64 | -0.26%; 2/5 | +0.03%; 3/5 | +1.83%; 4/5 |
| 700/64 | +0.04%; 4/5 | +0.32%; 3/5 | +0.42%; 4/5 |
| 1536/1 | +0.57%; 5/5 | +0.07%; 3/5 | +0.08%; 3/5 |
| 64/16 return | +0.12%; 3/5 | +1.17%; 3/5 | +1.71%; 3/5 |

The 129/1 case is a negative control: its final chunk has one row, so the
selected graph does not change. Its favorable SSE result demonstrates timing
drift or order effects on this host. Desktop activity was material; scheduling,
clock and power state were not controlled. No sample was excluded. The phase
benefit affects one FFN in the final prefill graph; it leaves decode untouched,
so a small and inconsistent whole-request effect is expected. No request result
shows a defensible repeatable win over pinned llama.cpp.

## Reproduction and next hypothesis

The measurement scripts are `scripts/measure-native-swiglu --native-disabled`
and `scripts/measure-host-reuse`. Use the raw receipt's identities and prompt IDs,
the same GGUF, pinned bundle and binary versions, and explicit execution settings
`sync_weight_upload=0`, `prefill_chunk=128`, `final_prefill_logits=1`,
`final_ffn_row=0/1`. Run with `--config CONFIG --output NEW_PATH`; worker also
accepts `--pairs 5`. The local diagnostic archive under the resolved Git common
directory contains the raw full-logit vectors, state hash log, trace and source/
binary copies with a SHA256 manifest. It is intentionally untracked and contains
no model weights. The tracked receipt holds the complete paired samples.

The next bounded experiment should attribute the real decode-time Q6_K output
projection and the gate/up/SiLU/down sequence across all 24 layers, measuring
device time, command boundaries and attainable memory bandwidth before selecting
a larger fused or relaid-out segment. Earlier isolated Q6_K paired-load work was
exact but showed no stable speedup, so repeating that same mapping is not the
next step. Qwen sizes can reuse the shape/type/layout selection and session
machinery once their semantic graph is admitted; this row selection requires
their own final-output dependency check. Gemma requires architecture-specific
normalization, attention, positional and activation semantics before sharing any
operation or device specialization. CPU/CUDA qualification is deferred.
