# Qwen3.5 Metal private-storage screen (2026-09-27)

## Decision

Do not use ggml's all-private Metal buffer mode for the current Qwen3.5-2B
request path. The same-binary real-model trial passed output and token-count
checks but lost every 64/16 whole-request pair, and its paired medians were
adverse at 200/32 and 330/64. The pinned llama.cpp driver remained faster at
every workload's marginal request median. Keep the shared-storage default.
This is an experiment result, not a claim that a separate private weight buffer,
a fused graph, or an independent backend cannot improve inference.

The causal boundary is clearer than the earlier copy hypothesis. In the pinned
ggml source, the private `ggml_metal_buffer_set_tensor` wraps the host bytes in a
shared source buffer, encodes a Metal blit, and waits for completion; shared
storage uses `memcpy`. The Align shim calls the synchronous setter for each
input update (`scripts/ggml_shim.c`, `align_gpu_input_update`), including token,
position, and mask fields. Its full-logit getter also crosses to the host. The
measured wall time outside the instrumented graph calls grew with generated
length. This is consistent with those extra transfer boundaries, but that
residual also contains other host work and is not an isolated blit timer.

## Local Q6_K screen

The existing checked-in `scripts/bench-metal-q6-projection.mm` used the three
captured real-model F32 activations and the actual 417,177,600-byte Q6_K tied
embedding. It compared the pinned ggml projection with its full-logit oracle
and the existing native kernel. Both shared and private runs passed all 12
full/tail numerical and argmax checks; maximum absolute difference was zero
for these captures. The check bound was the already declared 0.01, unchanged.
Each mode used 12 warmups, five groups of 20 iterations, and actual weight
bytes. These are separate process campaigns, so their small timing differences
are only a screen, not paired mode evidence.

| Activation | Shared ggml projection median ms | Private ggml projection median ms |
| --- | ---: | ---: |
| Final prefill | 7.807 | 7.721 |
| Decode A | 7.764 | 7.851 |
| Decode B | 7.732 | 7.828 |

There is no repeatable local private-storage advantage across activations.
This result also does not isolate a pure shader interval: the untraced ggml
wall measurement includes its synchronized graph call. The complete individual
samples and checks are retained in
[`shared-q6.jsonl`](../eval/benchmarks/qwen35-private-metal-2026-09-27/shared-q6.jsonl)
and [`private-q6.jsonl`](../eval/benchmarks/qwen35-private-metal-2026-09-27/private-q6.jsonl).

## Connected real-model trial

The independent `scripts/measure-native-swiglu` caller gained a per-arm
`private_buffers` setting. It sets the pinned ggml environment switch before
device creation and records it in the receipt. Both arms used the **same**
Align executable SHA-256
`69c3ea0f735bc1fc206a287b39587499d9704f2033af9d1e033c80d120d61ea2`,
same backend bundle, Qwen3.5-2B Q4_0 GGUF SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`,
same Alignpack, Model IR, runtime options, 128-token prefill chunks, final-only
prefill logits, and native FFN/NEON/shared-logits modes off. The model,
tokenizer, quantization, prompt IDs, generated token counts, and text matched
the pinned llama.cpp driver at revision
`bb4caa7540188872173c44d161602d9271386413`. Align was built with
`.align-revision` `b20429be50d6ab889496a0589143320683b29aeb`.

On the Apple M1 16 GiB host, each process made two warmup requests and a third
measured request. Five three-arm groups alternated forward/reverse order for
each workload. All 15 groups passed. The table gives marginal medians in ms;
the paired column is the median of shared minus private within a group, so a
negative value means private was slower. Every sample remains in
[`worker.json`](../eval/benchmarks/qwen35-private-metal-2026-09-27/worker.json).

| Input/output | Shared request | Private request | llama.cpp request | Paired shared minus private | Private wins |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64/16 | 564.946 | 581.220 | 548.178 | -16.351 | 0/5 |
| 200/32 | 1343.441 | 1333.664 | 1250.613 | -35.645 | 2/5 |
| 330/64 | 2742.441 | 2577.251 | 2427.242 | -81.652 | 2/5 |

The 200/32 and 330/64 marginal medians favor private over shared, but their
paired medians and win counts do not. The 330/64 shared arm had a 3078.566 ms
sample in the first group, making its marginal median particularly misleading.
No sample was excluded. Pinned llama.cpp was faster than private on all three
marginal medians.

The separately instrumented prefill/decode medians did not show a stable
private advantage. Prefill shared/private was 125.732/124.698, 389.855/385.448,
and 609.420/604.424 ms. Decode was 432.112/430.223, 937.224/895.918, and
2106.432/1876.769 ms; the latter two marginal differences are dominated by
the changing shared-arm host conditions, with paired decode differences of
only +1.197 and -1.963 ms. The medians of whole-request wall time minus the
two graph-phase clocks were shared/private 7.684/26.349, 15.087/51.109, and
26.320/105.788 ms. Paired shared-minus-private residuals were -19.247,
-36.025, and -79.468 ms, with all five pairs adverse in each workload. This
residual is not a standalone copy benchmark, but its scaling matches the
extra per-input private setter blits and output readback path.

Construction-to-ready marginal medians for shared/private/llama.cpp were
1016/1044/469, 987/1009/446, and 970/1035/511 ms. OS file and pipeline
caches were uncontrolled; these are not disk-cold starts. The trial did not
measure physical-memory pressure, so no memory-footprint benefit is claimed.

## Reproduce and next hypothesis

Build the checked-in Q6 probe against the pinned ggml bundle as documented at
the top of `scripts/bench-metal-q6-projection.mm`; capture the same GGUF's
Q6_K weight and real prefill/decode activations using the procedure in
`docs/final-prefill-q6-trial.md`. Run the probe once with
`GGML_METAL_SHARED_BUFFERS_DISABLE=1` and once without it. For the connected
trial, use `scripts/measure-native-swiglu --native-disabled` with explicit
same-binary `control` and `candidate` entries. Set
`candidate.execution.private_buffers` to `"1"` and control to `"0"`; leave all
other execution settings identical. The caller refuses private storage combined
with mapped weights or either shared-row greedy mode. The measurement caller
SHA-256 at this trial is
`e64d10b05e5e03e4e8470bd065d0ee9a8ae68e07250e40942be7ee594b555b83`.
An invalid private setting was refused before artifact access or session start;
strict Python boundary and `git diff --check` passed.

Apple's [Metal storage-mode guide](https://developer.apple.com/documentation/metal/choosing-a-resource-storage-mode-for-apple-gpus)
explains why shared memory is CPU accessible and private memory is GPU only.
The [BaseRT paper](https://arxiv.org/abs/2607.00501) reports gains from custom
fusion and dispatch on later Apple chips, but it neither isolates this Q6_K
storage switch nor measures this M1/Qwen3.5-2B workload. It is a direction for
new experiments, not evidence that this candidate should ship.

The next bounded experiment should keep input and output storage shared while
testing a larger in-graph Q6_K projection plus partial-top-token consumer, so
it does not add a post-sync Metal command buffer. The exact full-logit and
state oracles remain the control. If its local actual-weight screen cannot
beat the current connected boundary, redirect to a genuinely fused recurrent
or FFN subgraph with different data layout rather than another one-to-one
projection kernel. Other Qwen sizes can reuse the storage-mode measurement
method, but their admitted shapes/quantization may differ; Gemma requires its
own semantic graph and oracle. No CPU/CUDA result is inferred here.
