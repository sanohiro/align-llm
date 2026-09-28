# Qwen3.5 continuous prompt-lookup trial (2026-09-28)

## Purpose and prior cost ceiling

The three-draft local screen in `docs/qwen35-lookup-draft-screen.md` found
complete-group savings of 62.0–63.5 ms and first-draft mismatch losses of
52.0–52.3 ms on real Qwen3.5-2B Q4_0 M1 prefixes. One bug-fix continuation
had ten complete groups before its first mismatch; the other two tasks had
one and zero. These are a cost hypothesis for a **default-off continuous
request trial**, not a predicted request speedup. Before implementation, the
cost ceiling for this trial is one abandoned four-row target group per
request, no second weights/KV arena, one four-row F32 logits staging buffer
(3,973,120 bytes at this model), and at most one live verification graph in
the existing prefill graph slot. Additional request-owned target input staging
is bounded by 16 token bytes, 64 position bytes, `16 * mask_capacity` mask
bytes and one 1,040-byte slot table. The copied history never exceeds prompt
length plus `max_tokens`; report actual graph workspace separately. Compare
complete request time with the
current mixed-native Align and pinned llama.cpp; there is no fixed percent
admission floor.

The trial targets the existing real Qwen3.5 generation path. It does not
generalize the Qwen2 R9 five-row design or add a model-name conditional to
generic lookup. A later model and backend need separate graph/state evidence.

## Contract ledger

| Field | Contract |
| --- | --- |
| Exact surfaces | `runtime_qwen35_generation.generate_session_lookup_trial(session, prompt, eog, max_tokens) -> Result<LookupTrialResult, Error>` is an explicit diagnostic API; `generate_session` remains the normal path and streaming remains unchanged. `LookupTrialResult` owns `token_ids: array<i64>` and counters for lookup attempts, available drafts, verification groups, complete groups, discarded groups, generated draft tokens, prefill, ordinary serial decode, lookup, graph build, target compute and readback time. An Align diagnostic executable takes the same GGUF/pack/options and explicit prompt IDs as the normal GPU session and emits schema-1 JSON. |
| Inputs/defaults | Three lookup IDs after the already selected token; suffix lengths 3 then 2; a draft requires all three IDs. Trial is never inferred from normal options or model name and has no default-on mode. At least four output slots and four resident KV positions must remain. An EOG ID in any draft refuses that group. No draft, short remaining output, insufficient KV capacity and the first discarded group all continue through the unchanged one-token path. |
| Results/errors | A complete group accepts all three drafts, appends those three IDs and the final target-row greedy ID, advances valid state by four inputs, and continues with that last ID pending decode. Any mismatch discards the entire target result, restores the prefix recurrent parity, uses one ordinary decode of the current ID and disables further verification for that request. Extra candidate KV rows remain outside valid length and are masked. A failed graph, readback or state finish poisons the session and returns an error; it is not retried. Output stops at the first EOG and never exceeds `max_tokens`. |
| Ownership/allocation | Align owns the history, lookup, graph, greedy comparison, state commit/discard and generation loop. The trial uses the existing prefill graph kind after prefill completes and the existing two decode parity kinds. Its four-row logits buffer and target input/mask buffers are request-owned and released with the call. No Python or C/C++ inference logic, second weight payload, extra KV arena or ggml patch. Pinned ggml still executes model matrices. |
| Owner | `src/runtime_qwen35_generation.align` implements the trial; `runtime_generation.prompt_lookup_draft` already owns n-gram selection; the explicit Align smoke constructs a real session; a developer-only measurement script performs independent comparisons and paired timing. The product provider and options schema do not change. |
| Persisted/cache identity | The diagnostic's JSON receipt is schema 1 and written only on complete success; no product wire or options schema changes. Verification graphs use the existing process-local prefill graph slot and a key including shape, position, parity and all-row output semantics. Invalidating the prior prefill graph and rebuilding a changed target graph are charged to the request. Existing decode graph keys remain unchanged. |
| Validation order | Validate request and device/model identity; load the same weights; run prefill; before each decode, check output/KV capacity and one-strike flag, then perform lookup. On a hit, write all four token/position/mask inputs, prepare and compute the target graph, read all four F32 rows, compare draft IDs in order, then either commit all or restore prefix parity and take the ordinary decode step. Publish token IDs and counters only after final synchronization. |
| Prerequisites | Merged lookup-source screen and its actual-weight acceptance-state screen. No new Align compiler API. Existing strict-compatible normal path stays selectable. |
| Acceptance evidence | For publication of this explicit default-off trial: real 2B same-GGUF complete generated IDs, full and mismatch at each draft position, EOG/max-token boundaries, repeated requests, and five alternating complete requests versus mixed-native Align and pinned llama.cpp at more than one prompt/output length, with load and trial prefill/decode separated. Existing actual-weight local acceptance screens supply selected/next F32 and valid-state bounds. Product admission additionally requires connected intermediate logits/state samples, injected graph/readback failure cleanup and connected resource profiling. These are deferred because the present trial remains unreachable from normal product callers; `HANDOFF.md` names the next action. Other Metal generations, CUDA and Gemma are recorded unmeasured. |
| Metrics | Complete request wall and actual generated tokens are primary. Report prefill, target compute, graph build, ordinary decode, startup/load, draft lookup, acceptance/discard distribution, memory and order variance separately. The local cost ceiling above is diagnostic, not a fixed adoption threshold. |

## Closure matrix

| Condition | Implementation | Direct check |
| --- | --- | --- |
| Construction and ordinary path | Separate explicit trial API; unchanged `generate_session` caller and graph keys | Existing Qwen3.5 generation owner plus same-binary control |
| Full acceptance | Commit target active state, append three drafts and one bonus ID | Real model full-group ID, F32 and active-state comparison |
| Mismatch at draft 1/2/3 | Restore pre-target parity, discard all draft progress, one serial decode, disable trial | Constructed cases at each position and next-row/state trace |
| No lookup or insufficient remaining capacity | Ordinary decode without preparing target graph | Unit fixture and request counters |
| EOG and output limit | Refuse group containing EOG; stop at selected EOG; refuse group with fewer than four output slots | End-of-generation and max-token owner cases |
| Compute/readback/final sync failure | Poison session, publish no result and do not retry | The error path is implemented but forced GPU failure is deferred until product admission; `HANDOFF.md` tracks it. |
| Repeated requests | Zero resident state through current session lifecycle; clear one-strike/counters per request | Back-to-back short/long/short real requests |
| Other model/backend | No normal-path change; trial is only qualified on Qwen3.5-2B Q4_0 Metal M1 | Explicit deferral in `docs/backend-parity.md` and handoff |
