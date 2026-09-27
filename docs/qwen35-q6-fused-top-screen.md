# Qwen3.5 Q6_K producer-side top-token screen (2026-09-27)

## Decision

Do not integrate the tested 64-thread, four-row producer-side reduction into
the real-model runtime. It selected the correct token on captured real weights
and activations, but did not establish a reproducible connected local speed
advantage. The existing full-logit graph and opt-in in-graph greedy trial remain
unchanged. This result rejects this mapping, not output-projection fusion or an
independent backend generally. No full-request or llama.cpp speed claim is made
for this local-only candidate.

## Experiment and correctness

[`bench-metal-q6-projection.mm`](../scripts/bench-metal-q6-projection.mm)
adds `--fused-top` to the existing independent developer probe. The native
producer uses the same Q6_K arithmetic and 64-thread/four-output-row mapping
as its previously qualified full-logit variant. It writes one 12-byte
`{value,index,invalid}` partial per four output rows. A second dispatch in the
same Metal command buffer reduces the partials to one token; a buffer memory
barrier preserves the dependency. The ggml control uses the pinned Metal Q6_K
projection followed by the current hierarchical in-graph argmax. Both arms use
the same captured Qwen3.5-2B Q4_0 GGUF output-head Q6_K bytes and activations;
the actual output matrix is 2,048 by 248,320, 417,177,600 bytes. This does not
change quantization or skip the projection. The native arm keeps a separate
shared copy of the weights for this local screen; input upload and weight setup
are outside each timed operation. The baseline is a separate ggml-owned shared
buffer. The native producer and reducer share one queue and one command buffer.

All three final-prefill/decode activations selected captured full-logit tokens
16, 220 and 17, for both the complete 248,320-row output and a 257-row tail.
The pinned ggml projection matched all captured full logits exactly. The
unfused native kernel with the same arithmetic matched all three complete and
tail rows exactly in the independent `--check-only` run. The fused arm emits
only partials and a token, so this test does not establish equality of every
unmaterialized intermediate logit. Synthetic final-reducer cases confirmed
first-index tie selection and refusal of a nonfinite partial. The chosen token
is read only after the command buffer completes.

The comprehensive review found that the original edge-case check addressed a
second partial even when a valid three- or four-row capture allocated only one.
The check now owns a separate two-entry buffer. A three-row capture made from
the first three real Q6_K weight rows and each real activation passed complete
and two-row-tail token checks plus the reducer edge cases; its
[check receipt](../eval/benchmarks/qwen35-q6-fused-top-2026-09-27/three-row-check.jsonl)
is retained. The original full-capture checks also pass after the repair. The
repair changes only the check buffer, so the measured kernels and timed data
path are unchanged. [SHA256 identities](../eval/benchmarks/qwen35-q6-fused-top-2026-09-27/identities.json)
bind the final probe, plugin, and captured input files.

## Local timing

Apple M1 16 GiB, pinned ggml `bb4caa7540188872173c44d161602d9271386413`,
Align checkpoint `14ac45e3`, same compiled probe and captured bytes. Each
activation had 12 warmups per arm, then five alternating pairs of 20
synchronized operations per arm. The table reports median of paired ggml-minus-
fused wall differences; positive favors fusion. Every sample is in the
[untraced receipt](../eval/benchmarks/qwen35-q6-fused-top-2026-09-27/timing.jsonl).

| Activation | ggml / fused median wall, ms | Paired difference, ms | Fused wins | Paired range, ms |
| --- | ---: | ---: | ---: | ---: |
| final prefill | 7.815 / 7.762 | -0.011 | 2/5 | -0.323 to +0.180 |
| first decode | 7.607 / 7.656 | -0.048 | 1/5 | -0.095 to +0.007 |
| second decode | 7.773 / 7.700 | +0.021 | 5/5 | +0.011 to +0.281 |

The paired difference can disagree with the difference of arm medians because
the former preserves the pairing. A separate [instrumented receipt](../eval/benchmarks/qwen35-q6-fused-top-2026-09-27/traced.jsonl)
recorded two ggml command buffers and one native command buffer per operation.
Its paired GPU-interval medians were +0.067, -0.060 and -0.091 ms across the
three activations, with 3/5, 2/5 and 0/5 fused wins. The Objective-C commit
hook perturbs wall timing; these intervals are diagnostic, not throughput
evidence. Both campaigns show a small, inconsistent effect, far below the
approximately 7.7 ms projection-plus-selection cost.

At 248,320 rows, the partials occupy 744,960 bytes, written and read once.
The baseline full-logit row is 993,280 bytes, also written and consumed once.
Compared with the 417 MB Q6_K weight read, the output-traffic saving is small.
This is a plausible explanation for the weak result, not an isolated causal
measurement. Different weight-read mapping, coalescing, or a larger fusion
boundary could change the result.

## Reproduction and next GPU work

Build the checked-in probe against the pinned ggml headers and bundle:

```sh
clang++ -O3 -std=c++17 -fobjc-arc -framework Foundation -framework Metal \
  -I GGML/ggml/include -L BUNDLE -Wl,-rpath,BUNDLE \
  -lggml -lggml-base scripts/bench-metal-q6-projection.mm -o /tmp/bench-q6
/tmp/bench-q6 BUNDLE/libggml-metal.so CAPTURE_DIR --fused-top --check-only
/tmp/bench-q6 BUNDLE/libggml-metal.so CAPTURE_DIR --fused-top > timing.jsonl
/tmp/bench-q6 BUNDLE/libggml-metal.so CAPTURE_DIR --fused-top --gpu-trace > traced.jsonl
```

`CAPTURE_DIR` is the actual Q6_K weight/input/output set produced by the
existing decode-attribution capture. The complete model request did not run
this fused candidate; local speed was insufficient to justify connecting it.
The next GPU screen should first quantify a larger gate/up/SiLU/down boundary
or graph scheduling difference with the existing actual-weight FFN captures.
Preserve full logits, state, and the ggml fallback before any runtime admission.
CPU/CUDA and other Qwen/Gemma model behavior remain unmeasured for this Metal
specialization.
