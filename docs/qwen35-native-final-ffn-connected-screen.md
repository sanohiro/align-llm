# Connected final-layer native Q4_0 FFN screen (2026-09-28)

## Decision

Withdraw the final-layer FFN-only integration candidate. The independent
Q4_0 gate/up/SiLU/down kernels passed the previously declared local numerical
bound on real request activations, but none of three connected schedules gave
a repeatable whole-request improvement over the same mixed-native Align
binary. The production graph and the ggml fallback are unchanged. This result
does not rule out a larger Align-owned execution unit or weight reuse across
tokens.

## Actual connection and correctness

The Apple M1 16 GiB host ran the Qwen3.5-2B Q4_0 GGUF with SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
The saved Align binary, pack, Model IR, pinned ggml bundle, mixed native
DeltaNet/convolution copy settings, CPU greedy selection, and tokenized
prompts are the same as the [current bottleneck campaign](qwen35-current-native-mixed-bottleneck.md).
The pinned ggml source is `bb4caa7540188872173c44d161602d9271386413`.
The diagnostic interposer in
[`scripts/bench-metal-q4-final-ffn-request.mm`](../scripts/bench-metal-q4-final-ffn-request.mm)
replaces only the final decode layer's four consecutive Q4_0 FFN graph nodes;
the preceding and following graph slices still execute in ggml. Prefill and
the other 23 layers remain ggml. This is a real request execution, not the
earlier isolated FFN benchmark. It is a developer probe with fixed 2B shapes
and a pinned private ggml Metal buffer/event ABI, not a selectable product
path or an Align-owned complete scheduler.

The allocated decode graph has 1,038 nodes. The final FFN is nodes
1,029–1,032: gate `MUL_MAT`, up `MUL_MAT`, `GLU`, down `MUL_MAT`.
Its result feeds residual `ADD` at 1,033, then final normalization and the
Q6_K vocabulary projection. The actual gate/up/down weights have Q4_0
shapes `[2048,6144]`, `[2048,6144]`, `[6144,2048]`; the input is F32.
The weights occupy an existing shared Metal allocation. The diagnostic uses
their bytes in place. It adds one reusable 24 KiB gated intermediate, not a
second model-weight copy. The original graph allocator aliases the FFN input
and gated output, so writing the gated result into the original tensor while
reading its input corrupts the result. A separate gated intermediate is
required for this fused mapping.

For the synchronous direct-buffer variant, five consecutive real decode
steps were compared against ggml's FFN at the same captured input. The
already declared bound was `abs(native-reference) <= 0.005 +
0.0005*abs(reference)` for every finite output element. The observed largest
absolute down difference in those five steps was `1.90735e-6`; gated output
differences were at most `2.86102e-6`. The shadow comparison restores the
input and output before the request continues. Separate short repeated
requests matched generated text, and every arm in the paired campaigns
produced identical text and exact 64/16, 200/32 or 330/64 work across three
retained requests. Complete logits and recurrent-state vectors were **not**
compared for this discarded candidate, so this is insufficient for production
correctness qualification. The independent complete-FFN capture screen and
existing production regressions remain unchanged.

Borrowing the same host pointer through a second cached `MTLBuffer` appeared
to work for the first decode, then returned stale values on later decodes:
the second gated vector differed from ggml by as much as `46.0315`, and
generated text changed. Creating a new no-copy view each decode restored
the five-step numerical comparisons. Directly borrowing ggml's original
`MTLBuffer` through its pinned internal `ggml_metal_buffer_get_id` avoided
both the stale-view behavior and repeated view construction on this host.
The diagnostic refuses non-shared storage. The failure is a concrete
cross-resource visibility observation for this setup, not a general Metal
guarantee about every shared buffer or device.

## Paired request timing

Each worker ran three identical requests and the third was timed. Five
control/native pairs alternated process order for each condition. Both arms
used one saved binary and interposer, selected by `ALIGN_LLM_NATIVE_TAIL_DIAGNOSTIC`.
Positive control-minus-native values favor the candidate. The receipt files
retain every pair, startup clock and generated output:
[rewrapped view](../eval/benchmarks/qwen35-native-final-ffn-connected-2026-09-28-rewrap.json),
[borrowed original buffer](../eval/benchmarks/qwen35-native-final-ffn-connected-2026-09-28-borrow.json),
and [GPU-event ordering](../eval/benchmarks/qwen35-native-final-ffn-connected-2026-09-28-events.json).

| Prompt/output | New no-copy view each decode | Borrow original ggml Metal buffer | Borrow plus GPU events and final synchronization |
| --- | ---: | ---: | ---: |
| 64/16 | −27.879 ms, 0/5 wins | −10.563 ms, 0/5 | −15.214 ms, 1/5 |
| 200/32 | −66.907 ms, 0/5 | −38.149 ms, 2/5 | +0.598 ms, 3/5 |
| 330/64 | −150.855 ms, 0/5 | −58.138 ms, 0/5 | −38.286 ms, 0/5 |

The event arm's 200/32 paired differences span −136.0 to +42.6 ms; its
small positive median is not a reliable speedup. Event ordering preserves
the required dependencies: ggml records completion of the producer slice,
the native queue waits, native signals after its kernels, ggml waits before
the suffix, and the host synchronizes at the end. The diagnostic checks the
native command status but the pinned async ggml completion API does not
return a final status; that is another reason the event arm is not admitted
as a product path. The per-request prefill is unchanged. The added setup for
Metal pipelines/plugin borrowing moves startup measurements and has not
been isolated from system caches; startup differences in the receipts are
not a cold-load improvement claim. No process-footprint campaign was run.

One separate 200/32 direct-buffer diagnostic summed 64 native commands at
49.460 ms (about 0.773 ms per command); its prefix and suffix graph slices
summed 1,117.714 and 509.999 ms, respectively. This instrumented clock is
not a clean GPU kernel interval and is not directly interchangeable with the
paired wall figures. The earlier complete-FFN local advantage of 0.057–0.068
ms per operation did not cover the connected scheduling cost. A synchronous
ggml-only three-way final-FFN partition also lost 4/5 at 200/32 by a
22.422 ms paired median; async ggml-only partition lost 4/5 by 7.329 ms.
Those untracked diagnostic controls used the same real 200/32 request.

## Reproduction and next experiment

Build the interposer against the pinned ggml checkout and run the independent
measurement caller with explicit real-model paths. The source is developer
diagnostic code; it is never loaded in normal inference:

```sh
clang++ -dynamiclib -std=c++17 -O2 -fobjc-arc -undefined dynamic_lookup \
  -framework Metal -framework Foundation \
  -I "$GGML_SOURCE/include" -I "$GGML_SOURCE/src" \
  -I "$GGML_SOURCE/src/ggml-metal" \
  scripts/bench-metal-q4-final-ffn-request.mm -o "$TRIAL_DYLIB"
scripts/measure-metal-q4-final-ffn-request \
  --config "$REAL_MODEL_CONFIG" --interposer "$TRIAL_DYLIB" \
  --mode events --pairs 5 --output "$RESULT_JSON"
```

The next useful decode hypothesis must reduce weight bytes per accepted
token or make the native scheduler own a materially larger dependent unit.
A single FFN with three ggml graph slices does neither. Speculative token
verification is the concrete weight-reuse candidate: first measure a
multi-token target pass and its state transaction with the actual DeltaNet
and KV semantics, including draft cost and rejected-prefix replay, before
adding it to normal generation. The 2B M1 result says nothing about Q4_1
FFN layers, other Qwen sizes, Gemma activation/attention semantics, CUDA,
or another Metal GPU. A Q4_0, F32, SiLU, `[2048,6144]` specialization may be
reused where those attributes truly match; model loading and generation
must not hard-code that shape.
