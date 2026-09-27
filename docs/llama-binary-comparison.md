# Pinned llama.cpp binary comparison — 2026-09-26

This is a diagnostic follow-up to [host reuse](host-reuse-diagnosis.md), not a
new kernel or a speedup claim. Product code is unchanged.

## Inspected artifacts and method

Inspect the actual `bench-native-llama-v3` executable used by the existing
comparison, its loaded `libllama.0.dylib`, `libggml-metal.0.dylib` and
`libggml-base.0.dylib`, rather than stopping at the small driver. The build's
CMake source directory and checkout identify pinned revision
`bb4caa7540188872173c44d161602d9271386413`. Align source is `40cce4a6`; native
fusion is disabled, with the same bundle and 2B Q4_0 weights as the host study.

| Artifact | SHA-256 |
| --- | --- |
| Reference driver | `f384a6a64603479cf5c675ba587aeafbd64a500c3129a0afdcd271dcf532717d` |
| libllama | `42b07b8974d235d85bdad6661bb8daab4cd8929f5a7a13d5bb49dce40fc6fe54` |
| libggml-metal | `9dd4b0267eaa20506d139a0347bf5e9693f830bb4fa3a468ce73b483a279c090` |
| Align executable | `a1a06bd14e8b0849ef6e4fc49e1ca3911d308dbba5ed261ff5eea6ff4211b822` |
| 2B GGUF | `cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1` |

Disassemble with `xcrun llvm-objdump --macho --disassemble BINARY`. The source
cross-check uses `src/llama-context.cpp`, `src/llama-model.cpp`,
`ggml/src/ggml-metal/ggml-metal-context.m` and `ggml-metal-device.m` at the pin.
Runtime probes interpose `llama_decode`, `llama_get_logits`, async tensor get/set,
and `ggml_backend_dev_buffer_from_host_ptr`, and reuse the independent Metal
command-buffer completion hook. No waits or GPU operations are removed.

The diagnostic order is plain llama, traced llama, traced Align, traced llama.
Each process runs three requests; use the final request after two warmups.
All use exactly 200 prompt tokens and 32 generated tokens from the existing
counting fixture. All nine reference ID lists match; their rendered text equals
all three Align outputs, with matching counts. This is not five alternating
performance pairs. Diagnostic callbacks perturb timing, and context reservation
remains different (reference 512, Align retained capacity 2304).

Local assembly dumps, probe source, logs, raw timestamps, output IDs and summary
are retained under `diagnostics/llama-binary-2026-09-26` in the resolved Git
common directory. They are local evidence, not committed portable artifacts.

## What the binary and execution show

### Weight loading uses mapped storage

`llama_model_base::load_tensors` calls `ggml_backend_dev_buffer_from_host_ptr`
at libllama offset `0xa984c`. Metal's buffer wrapper calls
`newBufferWithBytesNoCopy:length:options:deallocator:`. The actual run reports
`CPU_Mapped` and `MTL0_Mapped`, with host-pointer wrapping sizes 417,177,600 and
1,203,911,936 bytes. These are views of the mapped model; summing their sizes
would not establish two independent physical copies.

There are zero intercepted `ggml_backend_tensor_set_async` calls in the reference
run. Before the first `llama_decode`, one Metal command buffer is captured;
Align has 1,369 before its first graph call. These boundaries include startup
and request preparation, not exclusively weight transfer. Source and the earlier
Align call trace identify its staging copy, temporary Metal source-buffer copy,
blit and per-upload wait. The reference's mapped-weight path avoids that sequence.

This establishes a concrete loading-strategy difference. It does not establish
its isolated latency contribution. File caches/page faults are uncontrolled;
plain reference startup was 1.282 s and the following traced startup 0.439 s.
Mapped pages can defer costs until first inference. A startup optimization must
measure construction and cold/warm first request, preserve validation and retain
the mapped-storage owner until every GPU user finishes.

### Async return moves the wait to logits access

The public `_llama_get_logits` disassembly at libllama offset `0x243e0` contains:

```text
bl  llama_context::synchronize()
bl  llama_context::output_reorder()
ldr x0, [x19, #0x100]
ret
```

The generated code returns the retained logits pointer after synchronization.
It does not allocate a fresh vocabulary buffer on this path. `output_reserve`
only allocates/clears when capacity is insufficient. During decode, the library
calls `ggml_backend_tensor_get_async`; the actual trace records 96 transfers of
993,280 bytes for three 32-output requests. Metal encodes a readback blit into a
third command buffer, after two compute command buffers. `newBufferWithBytesNoCopy`
wraps the readback destination; it does not mean the blit was omitted.

For the final request of the repeated trace, median `llama_decode` return is
1.382 ms and median `llama_get_logits` duration is 25.563 ms. The median complete
interval from decode entry through logits readiness is 27.063 ms. Medians do
not add exactly. Comparing only `llama_decode` against Align's synchronous graph
call would incorrectly attribute GPU waiting to one implementation alone.

### Prefill batches differ

The reference driver has `n_batch=n_ubatch=512`. The trace confirms one 200-token
`llama_decode`, followed by 31 one-token decodes, per request. Align executes
128- and 72-token prefill graphs, then 31 one-token graphs. Thus the reference
has 96 decode calls over three requests and Align has 99 graphs.

The final-request prefill GPU interval union is 379.14 ms for repeated llama and
398.27 ms across Align's two graphs. Larger batches change matrix and recurrent
kernel specializations as well as launch boundaries. Batch size is a concrete
next controlled experiment, not a proven explanation for this entire difference.
The 128-vs-200 prefill distinction was already recorded in the earlier handoff;
this inspection confirms it in the running comparison rather than rediscovering
an unimplemented language optimization.

### The remaining decode difference is visible inside GPU intervals

Medians over the final request's 31 decode steps, milliseconds:

| Boundary | First llama trace | Align trace | Repeated llama trace |
| --- | ---: | ---: | ---: |
| Decode entry through logits readiness / Align graph call | 27.080 | 28.422 | 27.063 |
| Union of GPU command-buffer intervals | 26.347 | 27.797 | 26.424 |
| First GPU start through last GPU end | 26.442 | 27.841 | 26.505 |

The reference GPU union includes the readback command (median about 0.028 ms);
Align's synchronous CPU logits copy follows its graph call and is outside its
GPU intervals. All 192 reference decode records and 99 Align graph records have
successful command completion and nonzero timestamps inside their enclosing
host intervals. Each reference decode captures three command buffers, each Align
graph two. GPU intervals include internal stalls/barriers and are not ALU use.

Between logits readiness and the next decode entry, the reference driver spends
about 0.592 ms (median); Align's graph-return-to-next-graph interval is 0.218 ms,
including its logits copy. These intervals include different ancillary work and
are not a pure argmax microbenchmark. The reference driver's argmax at
`0x100000ab8` is a scalar `ldr s1 / fcmp / fcsel / csel` loop; Align's generated
argmax uses vector loads/comparisons. This observation is about this comparison
driver, not every llama.cpp sampler. It does not support blaming slow Align
host lowering for the observed GPU-interval difference.

The runtime logs still select different Flash Attention stride specializations:
`ns10/ns20=512` for llama and `256` for Align. Prior exact-layout local attention
measurements did not explain the whole graph gap; do not repeat that experiment
without a new hypothesis. This host disassembly is not disassembly of Metal GPU
machine code and does not yet attribute the remaining difference to one shader.

## Consequence for the next experiment

1. Test a larger Align prefill batch with the same weights, prompt and generation,
   preserving recurrent/attention state and exact compatibility checks.
2. Separately trial mapped or synchronous host-visible weight loading with
   explicit ownership and preserved validation, measuring startup plus first use.
3. Attribute the remaining decode GPU gap to real output-projection/FFN work and
   data placement. A faster host loop or a removed logits copy alone is not an
   evidenced explanation for the measured gap.

No production changes, new precision policy, or whole-request improvement are
claimed by this investigation.
