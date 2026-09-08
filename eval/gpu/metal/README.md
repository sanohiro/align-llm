# Frozen Metal generation inputs

These schema-1 calibrations bind the local Q4_K_M Qwen2.5-Coder-7B and OLMoE-1B-7B reference
models, their exact packs/geometries, and the pinned Apple M1 Metal bundle. They contain actual
CPU prompt IDs, sampled IDs and output bytes from `runtime_calibration_seed`, with an empty system
prompt, greedy sampling and two maximum output tokens. OLMoE uses a 268435456-byte expert cache;
Qwen uses zero. The calibration and holdout prompts differ for each model.

The static CPU reference uses Align `305926b423da9be1f13b0129a7232626e6704d95`, ggml
`bb4caa7540188872173c44d161602d9271386413` and the checked-in CPU-reference build recipe. Its full
Align source bytes match the `src/` tree at `1e6a1bb`; the production trace driver returns the
recorded values directly. The corresponding CPU repetitions must reproduce them during final
qualification with that profile's actual same-build reference.

Absolute and relative tolerances are the binary32 encoding of 0.001; routing near-tie tolerance
is the binary32 encoding of 0.00001. These were selected before any GPU calibration or holdout
execution and are not observed error maxima. Do not enlarge them after a failed holdout. These
inputs alone do not establish numerical agreement, GPU placement, repeatability or qualification
PASS. The complete public qualifier and its replayed evidence own those claims.

## First real qualification and precision investigation

The public qualifier at `0bc76bb`, with the exact native device `MTL0`, records Qwen calibration
CPU PASS followed by GPU COMPUTE/readback FAIL. Native GPU generation itself exits successfully
and reproduces the frozen output. The complete numeric comparison reports 4,984,483 mismatches
of 5,243,392 scalars, maximum absolute difference 20.6373291015625. Cleanup and input/source
rechecks pass. No GPU holdout was started. The frozen records above remain unchanged.

A separately retained diagnostic pair localizes differences to the first production logits
(maximum absolute difference 0.22494947910308838) and the first layer (0.04968923330307007).
Relocated diagnostic binaries are not qualification evidence.

`precision-probe.cpp` isolates the pinned backend's arithmetic using a 256-by-32 weight matrix
and deterministic sine/cosine inputs. It does not execute Align or application graphs. Link it
against the same CPU-reference build's `libggml-cpu.a` and the Metal bundle's shared ggml/base:

```sh
c++ -O2 -ffp-contract=off -std=c++17 -I "$GGML_CHECKOUT/ggml/include" \
  eval/gpu/metal/precision-probe.cpp "$CPU_BUILD/ggml/src/libggml-cpu.a" \
  -L "$METAL_BUNDLE" -lggml -lggml-base -Wl,-rpath,"$METAL_BUNDLE" \
  -o /tmp/align-metal-precision-probe
/tmp/align-metal-precision-probe "$METAL_BUNDLE/libggml-metal.so"
```

Use ggml commit `bb4caa7540188872173c44d161602d9271386413` for all three inputs; `CPU_BUILD`
is the completed static CPU-reference build directory, and `METAL_BUNDLE` contains the manifest
and its libraries. The observed Apple M1 results with the recorded Metal bundle are:

| Weight type | Input columns | Maximum absolute difference | Scalars outside A=R=0.001 |
| --- | ---: | ---: | ---: |
| F32 | 1 | 0.00000381469727 | 0 / 32 |
| Q4_K | 1 | 0.0372447968 | 32 / 32 |
| Q6_K | 1 | 0.0354576111 | 31 / 32 |
| F32 | 20 | 0.00781154633 | 48 / 640 |
| Q4_K | 20 | 0.0575428009 | 466 / 640 |
| Q6_K | 20 | 0.0608406067 | 469 / 640 |

The pinned CPU type traits select Q8_K activation dot products for Q4_K/Q6_K weights. This
isolated reproduction establishes backend arithmetic differences independent of application
diagnostic retention; it does not certify every application operation. The earlier
[R5C investigation](../../../docs/specs/r5c-metal-prefill.md#25-probe-4--the-per-layer-residual-and-why-it-cannot-be-a-gate)
also documents cross-device logit differences and massive-activation residuals. G1's current
strict profile remains failed. Choosing a different validation contract requires an explicit
design decision and independent acceptance data, not widening these frozen thresholds.
