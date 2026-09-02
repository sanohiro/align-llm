# R8 OLMoE provider boundary

Status: merged as PR #170 on 2026-09-03

## 1. Decision and boundary

R8 now has exact OLMoE prompt ids and an invocation-local partial LRU expert cache, but the public
`AlignRuntime` provider still hard-codes the dense Qwen frontend and decoder. This capability joins
those shipped surfaces into one useful consumer: greedy OLMoE text generation through the existing
provider API and CLI.

The provider dispatches only exact `qwen2` and `olmoe` GGUF architectures. Qwen retains its current
dense generation behavior and requires a zero cache budget. OLMoE requires an explicit positive
cache budget and executes the existing `dense+lru` policy. The capability adds no provider kind,
sampling mode, persisted cache, concurrency, benchmark result, latency claim, or coding-task
quality claim.

This document is authoritative because the change adds a public configuration field and CLI
operand and coordinates provider, tokenizer, frontend, and decoder behavior.

## 2. Public-contract ledger

| Field | Settled contract |
| --- | --- |
| Capability | `R8-OLMOE-PROVIDER` |
| Consumer | an existing `ModelProvider` caller performing bounded greedy generation with the pinned OLMoE model |
| Public API | `ProviderConfig.runtime_cache_budget_bytes: i64`; `0` selects Qwen dense generation and a positive value selects OLMoE partial-LRU generation after architecture validation |
| Public CLI | `main --provider align-runtime MODEL PACK GEOMETRY PROMPT RESULT [MAX_TOKENS] [CACHE_BUDGET_BYTES]`; omitted budget is `0` |
| Dispatch | complete GGUF first, then exact architecture: `qwen2` requires budget `0`; `olmoe` requires budget `> 0`; every other pairing is invalid |
| Generation | existing system/user prompt preparation; greedy argmax; returned ids include the prefill argmax and each completed decode argmax, ending at the first EOG id inclusive or `max_tokens` |
| EOG | the tokenizer's bounded canonical EOG set from model metadata and admitted control spellings; the terminal EOG id is removed before text decode |
| Cache | invocation-local deterministic LRU; budget must produce at least `n_expert_used` fixed maximum-key slots and remain within the existing runtime window ceiling |
| Results/errors | existing provider `Result<string, Error>` and schema-2 CLI record; configuration, architecture, geometry, source identity, prompt, runtime, and decode failures remain `Error.Invalid` with no partial text |
| Validation order | provider kind/network-only fields and common bounds; paths/request; GGUF; architecture/budget pairing; architecture frontend; exact geometry; pack source identity; prompt/EOG; context bound; generation; decode/identity/response bound |
| Ownership | cache, KV plane, graph state, and generated ids are invocation-local; only an owned output string escapes |
| Persisted/cache identity | N/A: no cache survives a call; exact geometry and pack source identity are revalidated by the inference opener |
| Schema version | API record gains one required field; CLI result remains schema 2; diagnostic MoE document and CLI are unchanged |
| Prerequisites | R8-PARTIAL-LRU-CACHE and R8-OLMOE-TEXT merged; Align pin `8cefc803d5c7f883a8db5b67250ed4ed069b43a4` |
| Acceptance | focused synthetic Qwen/OLMoE API and CLI owner; one fixed real OLMoE generation compared to pinned llama.cpp token ids and decoded bytes |
| Metric | correctness only; focused synthetic owner ceiling five minutes, real qualification approximately fifteen minutes |

The CLI parses the optional cache budget before dispatch and writes no result on malformed arity or
number text, matching its existing operand behavior. A parsed zero is equivalent to omission.
Negative values, a positive budget on Qwen, zero on OLMoE, unsupported architecture, insufficient
slots, and over-ceiling budgets fail without generation. Network provider construction sites set
the new field to zero and their wire behavior is unchanged.

OLMoE generation shares the diagnostic decoder's arithmetic, graph, KV plane, and partial-cache
implementation. Generation is a mode of that implementation, not a subprocess or JSON round trip.
It reopens and compares the exact geometry bytes and verifies the still-open AlignPack source
record. It checks EOG before building the next graph, so `max_tokens == 1` and immediate EOG perform
prefill only. The diagnostic `--moe-decode-step` path retains its exact requested-step semantics,
document shape, and token-id meaning.

## 3. Closure matrix

| Owner / path | Construction | Success | Failure / malformed | Early exit | Cleanup | Regression |
| --- | --- | --- | --- | --- | --- | --- |
| config and CLI | required API scalar; optional final CLI integer | zero Qwen or positive OLMoE budget | arity/text/sign/profile mismatch | before runtime allocation | Copy scalar | API constructors and CLI matrix |
| architecture dispatch | complete snapshot architecture | exact frontend and decoder | unsupported/crossed budget | before prompt/runtime | snapshot flows to identity and tokenizer | Qwen unchanged plus OLMoE synthetic models |
| EOG set | tokenizer metadata and admitted controls | first EOG stops before another graph | empty/range/oversize set refuses | immediate EOG is prefill-only | owned bounded ids drop | immediate, after-one, and max-token cases |
| MoE generation | prompt ids, exact geometry/source, positive budget | prefill plus bounded decode ids | drift, context, cache, graph, or nonfinite failure | no partial ids/text escape | one converged graph/backend/cache teardown | forced engine and failure injections |
| diagnostic decoder | existing operands and mode | byte-identical document semantics | existing codes/order | existing partial-step rules | existing teardown | current MoE/cache owner unchanged |
| output decode | terminal EOG removed, controls skipped | owned bounded UTF-8 text | tokenizer identity or byte cap mismatch | after successful generation only | temporary ids/result drop | exact completion bytes/counts |
| real qualification | pinned model, pack, compiler, llama.cpp | one prompt's generated id chain and decoded bytes agree | missing opt-in is N/A; wrong named input fails | one task only | signal-aware server teardown and disposable artifacts | bounded runner self-test and real run |

## 4. Author consistency pass

The ledger and matrix define one architecture discriminator, one explicit cache scalar, one shared
MoE generation mode, and one output rule. They preserve every Qwen and diagnostic surface, expose
no partial state, and make no performance statement requiring a benchmark.

## 5. Candidate evidence and ledger mapping

| Contract / closure cells | Candidate implementation and evidence |
| --- | --- |
| config, CLI, dispatch, Qwen preservation, EOG, failures, and output | `src/model.align`, `src/main.align`, `src/provider_runtime.align`; `gmake runtime-provider-smoke` passes 61 assertions over Qwen and OLMoE |
| MoE generation, cache ownership, early exit, and diagnostic preservation | `src/moe_decode_step.align`; focused provider owner passes and `gmake layer-forward-smoke` passes the diagnostic/cache boundary |
| exact emitted ids and decoded bytes | the fixed real-model gate reads the generation seam's actual ids and matches pinned llama.cpp prompt count 47, ids `[1992,4993]`, and bytes `To fix` in 22.62 seconds |
| qualification cleanup | signal-aware server teardown plus its forced terminate-to-kill self-test |

The comprehensive review found two P2 qualification defects: re-tokenized output did not prove the
emitted id chain, and SIGTERM could bypass server cleanup. Both are repaired above without changing
the provider contract or runtime behavior, so the repair does not trigger another full review.
