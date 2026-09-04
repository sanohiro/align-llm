# R8 OLMoE runtime sampling

Status: implementation candidate, 2026-09-04

## 1. Boundary and decision

R8-OLMOE-SAMPLED-CODING established that the fixed OLMoE coding task is solvable by the existing
local provider's bounded seeded portfolio and selected sampling as the next `AlignRuntime`
capability. This capability makes one such request a real in-process provider operation. It adds a
fixed, reproducible sampler to the shipped OLMoE generation path, exposes it through the existing
`GenerationRequest.temperature` and `.seed` fields, and leaves dense Qwen and every diagnostic
decode document greedy.

This is a correctness and reproducibility capability, not the R8 performance decision. It does not
claim token parity with llama.cpp: the candidate filters match the non-no-op filters used by item
51, but Align deliberately uses its shipped Xoshiro256++ `std.rand` stream rather than llama.cpp's
`std::mt19937` distribution. It also does not add arbitrary temperatures, unseeded sampling,
penalties, concurrent generation, streaming, or a persisted sampler state.

## 2. Public-contract ledger

| Field | Settled contract |
| --- | --- |
| Capability | `R8-OLMOE-RUNTIME-SAMPLING` |
| Consumer | one caller of the existing in-process `ModelProvider.generate` API using the shipped OLMoE model, pack, geometry, and positive invocation-local cache budget |
| Request modes | greedy is exactly `temperature == 0.0` and `seed == None`; sampled is exactly `temperature == 0.3` and `seed == Some(i64)` |
| Architecture scope | OLMoE accepts both modes; Qwen accepts greedy only and refuses a well-formed sampled request after architecture discovery |
| Invalid pairs | any other temperature, positive temperature without a seed, or a seed with zero temperature is `Error.Invalid`; common provider configuration and request bounds retain their existing earlier precedence |
| Sampling filters | for each emitted token: stable top-k 40, top-p 0.95, min-p 0.05, temperature 0.3, then one categorical draw |
| Ordering and ties | candidates are descending by the original F32 logit and ascending token id for equal logits; top-p keeps the shortest prefix whose pre-temperature softmax mass reaches 0.95; min-p then keeps candidates whose pre-temperature probability is at least 0.05 of the maximum, always retaining one |
| Distribution | subtract the maximum logit, apply temperature, exponentiate in F64, round each relative weight to nearest 1,000,000,000th, draw uniformly with `rng.range(0, total_weight)`, and choose the first cumulative weight strictly above the draw |
| RNG | one `rand.seed_with(request.seed)` Xoshiro256++ value per provider invocation, advanced exactly once per emitted token including an EOG token; every signed 64-bit seed is accepted |
| Stop behavior | sample the prefill logits first, then sampled decode logits until the existing maximum-token or EOG rule stops; the terminal EOG id remains in the internal generated-id chain and is omitted from decoded completion text exactly as in greedy mode |
| Diagnostics | `--moe-decode-step`, its schema-2 document, published argmax fields, greedy `generate_resident`, and dense Qwen generation are byte-for-byte unchanged |
| Capability report | `ModelInfo.supports_seed` is true for `AlignRuntime` configurations with a positive cache budget and false for zero-budget dense configurations; model-info remains configuration-derived and performs no file I/O or architecture validation |
| Errors | malformed request pairs fail before model I/O; a valid sampled request against Qwen fails after GGUF architecture discovery; malformed/non-finite logits and empty candidate sets fail closed as `Error.Invalid` through the provider |
| Ownership/allocation | `runtime_sampler` owns temporary candidate ids, logits, and weights and returns the advanced Copy RNG; `moe_decode_step` owns the invocation-local RNG and generated selected-id chain; no state escapes the call |
| Persisted/cache identity | no sampler artifact is persisted; existing model/pack/geometry identities and cache lifetime are unchanged |
| Schema version | N/A: neither `GenerationRequest`, `ModelInfo`, nor `GenerationRecord` changes shape, and no new exchanged document is introduced |
| Owner | `make runtime-provider-smoke`, including pure sampler vectors and synthetic public-provider generation |
| Real qualification | prompt `Fix an off-by-one error in a Python inclusive range.`, maximum 2 tokens, temperature 0.3, seed 5, and cache budget 975,175,680 bytes, repeated twice through `runtime_provider_gate runtime-olmoe-sampled`; require successful byte-identical records against the pinned real OLMoE inputs |
| Cost ceiling | approximately 5 minutes for focused build, synthetic owner, and real repeated qualification on the author host; no performance floor |

The exact temperature is intentionally narrow. Item 51 only established feasibility at 0.3, so a
general numerical sampling API would promise behavior without consumer evidence. A later capability
may widen the accepted policy by updating this ledger, implementation, and owning tests together.

The stable tie rule and fixed-point final weights are Align-owned reproducibility rules. Intermediate
filter arithmetic uses F64 over the original F32 logits. The fixed-point conversion prevents the
categorical boundary from depending on a library-specific floating distribution implementation;
the focused vectors keep their cumulative boundaries comfortably away from rounding ambiguity.

## 3. Validation order

`provider_runtime.generate` preserves its existing common validation order: provider kind, forbidden
network fields, required paths, response bound, nonnegative cache budget, token bound, then the
temperature/seed pair. A malformed pair therefore fails without opening any path. A well-formed
sampled pair must open the model to distinguish OLMoE from Qwen; Qwen refusal occurs immediately
after architecture and cache-mode validation and before model IR, geometry, pack identity,
tokenization, or graph construction.

For OLMoE, all existing model, model-IR, geometry, pack, prompt, width, cache, and graph validations
remain in order. Sampling sees a logits buffer only after the existing full-buffer non-finite check.
The sampler nevertheless validates its own byte shape and finite F32 values because it is an
independently tested module and must fail closed if another future caller bypasses that owner.

## 4. Closure matrix

| Cell | Provider | MoE decoder | Sampler | Exact regression |
| --- | --- | --- | --- | --- |
| Construction | classify the request pair and architecture; seed only the sampled OLMoE branch | create one invocation RNG and selected-id builder | allocate at most 40 candidates and return advanced RNG | sampled synthetic provider success and pure fixed vector |
| Greedy success | retain the old dispatch | use prefill/decode argmax and old generated-id rendering | N/A | existing Qwen and OLMoE maximum-token cases remain unchanged |
| Sampled success | dispatch fixed policy with signed seed | use selected token as the next decode operand and render selected ids | stable filters, quantized weights, one draw | same seed repeated, pinned multi-draw sequence, public provider success |
| EOG | retain existing completion stripping | test the selected token before constructing the next graph | EOG has no special sampler treatment | synthetic immediate and post-step sampled EOG cases |
| Maximum one | return one sampled prefill token | render the first selected id even though no decode graph runs | advance once | sampled max-one case |
| Invalid request | reject malformed pair before path I/O; reject sampled Qwen after architecture | never entered | never entered | missing-path precedence and sampled-Qwen API cases |
| Malformed logits | map decoder failure to `Error.Invalid` | preserve existing non-finite failure and reject sampler error | reject empty, misaligned, or non-finite input | pure refusal vectors plus existing non-finite provider fixture |
| Tie/filter boundary | N/A | carry exact selected id without rewriting argmax evidence | stable id tie, rank-41 exclusion, top-p inclusion, min-p exclusion | pinned pure boundary vectors |
| Repeatability | create no hidden state | seed once per invocation and advance returned state once per emitted id | shipped deterministic RNG only | same-seed synthetic and repeated real qualification |
| Different seeds | accept every `i64` seed | separate invocations have separate state | balanced vector exposes divergent pinned choices | pure vector; no statistical claim |
| Early exit | propagate `Error.Invalid`; write no successful record | stop before partial generated-id success | return `Err` without a token | malformed vector and provider error cases |
| Cleanup | existing provider ownership unchanged | temporary builders and RNG die with invocation; expert cache cleanup unchanged | owned arrays die on return | existing smoke lifecycle plus repeated real process exits |

Streaming, concurrent calls, arbitrary policy composition, sampling penalties, sampling-state
serialization, GPU execution, and provider-level passing-patch measurement are N/A because this
capability changes none of those boundaries. The passing-patch portfolio through `AlignRuntime` is
the next measurement capability after this sampler is merged.

## 5. Implementation and acceptance map

1. Add a small `runtime_sampler` module implementing the ledger's fixed policy with pure synthetic
   vectors for deterministic stream, filter boundaries, tie order, and malformed input.
2. Add a sampled twin to MoE resident generation. Preserve true argmax fields for diagnostics while
   carrying selected ids separately for generation operands, EOG decisions, and returned ids.
3. Extend runtime provider validation and architecture dispatch without widening dense Qwen.
   Report seeded capability only for positive-cache `AlignRuntime` configurations.
4. Extend the existing model-free provider owner with sampled OLMoE maximum-token, EOG,
   repeatability, and refusal cases. Existing greedy records must remain unchanged.
5. Extend the qualification-only helper with `runtime-olmoe-sampled` carrying explicit maximum
   tokens, fixed-temperature micros, and seed operands, then run the ledger's fixed real request
   twice and require successful byte-identical results. This is reproducibility evidence only.
6. Run the focused owner, fixed real qualification, one comprehensive review, affected-owner repair
   checks, exact-head publication preflight, and required GitHub checks. `make ci`, installed
   profiles, the 40-prompt corpus, cache replay, stress, and benchmarks are not selected.
