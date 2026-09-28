# Qwen3.5 one-draft target trial (2026-09-28)

## Hypothesis and cost ceiling

The continuous three-draft M1 trial gained 491.6 ms on the 99/75 bug-fix
request but lost 74.4 ms on the 72/96 test-writing request. The latter paid
for one rejected four-row group. A two-row graph verifying one lookup draft
may reduce that loss; it also needs more groups to cover a repeated passage.
Offline stream replay suggests 20 successful one-draft groups before a
rejection on the bug-fix continuation, versus ten three-draft groups. This is
a scheduling hypothesis, not a measured speed result or a confidence rule.

Before implementation, bound the new path to one rejected group per request,
one two-row F32 logits staging buffer (1,986,560 bytes for the measured
vocabulary), eight token bytes, 32 position bytes, `8 * mask_capacity` mask
bytes, and one existing 1,040-byte slot table. Reuse the resident weights,
KV/recurrent state and prefill graph slot; no second model arena or ggml source
patch. Record actual graph workspace separately when available. No fixed
percentage floor determines trial integration or adoption.

## Contract ledger

| Field | Contract |
| --- | --- |
| Surface and owner | Add `runtime_qwen35_generation.generate_session_lookup_trial_one(session, prompt, eog, max_tokens) -> Result<LookupTrialResult, Error>` in the existing Align generation module. The established three-draft API, normal path and streaming path retain their contracts. The diagnostic accepts an explicit `trial1` arm; neither product options nor model-name dispatch select it. |
| Inputs/defaults | Require the existing validated real Qwen3.5 session and at least two output slots and two resident positions for a target. Search suffix length 3, then 2, for exactly one draft. A draft containing EOG skips verification. No candidate, too little capacity and the first mismatch continue through ordinary one-token decode. There is no implicit mode. |
| Result/errors | A full match emits its draft and the bonus-row greedy ID, commits two input positions and continues with the bonus pending. A mismatch discards the target result, restores the pre-target recurrent parity, executes one ordinary decode and disables further verification for that request. `LookupTrialResult` retains token IDs and the existing counters and phase clocks; `generated_drafts` counts one per complete group. Errors poison the session and publish no result. |
| Ownership/allocation | Align owns lookup, graph construction/key, all-row greedy comparison, state commit/discard and generation. The request owns the two-row staging buffers. Pinned ggml executes model matrices; the existing optional native Metal state/convolution copy remains fixed in the comparison. Python remains an independent verifier/measurement driver. |
| Cache identity and format | The target graph key includes count 2 as well as model/shape, position, width, parity and all-row semantics. Existing count-4 keys are unchanged. The diagnostic JSON remains schema 1; no persisted product or options format changes. |
| Validation order | Validate request/session; run unchanged prefill; check capacity and one-strike flag; find one candidate; write token/position/mask inputs; invalidate the previous prefill graph, prepare/compute count 2, read both F32 rows and finish required native state work; compare draft, then commit both or restore parity and decode normally. Final synchronization precedes successful return. |
| Acceptance evidence | Real 2B actual-weight acceptance/rejection, selected/next F32 and valid-state comparison under the already declared bounds, EOG/output limit, repeated requests and invalid input. Five alternating complete-request pairs against normal Align and the current three-draft trial on all three coding prompts; compare the candidate with the pinned llama.cpp revision under identical weights/IDs/precision. Separate prefill, target, serial decode and startup/load. Other Metal generations/CUDA/Gemma remain unmeasured and default product admission remains a later decision. |
| Metrics | Paired complete-generation and fresh-process wall time, acceptance/discard counts, graph build/compute/readback, lookup time, startup/load, memory and adverse pairs. A single local target win is insufficient. |

## Closure matrix

| Condition | Owner | Direct check |
| --- | --- | --- |
| Construction and existing modes | Shared bounded count in the Qwen3.5 generation module; `trial1` diagnostic arm | Build with pinned compiler; old three-draft and normal real-model controls |
| Full acceptance | Two-row target state and bonus output | Real-prefix full group, selected/next F32 and active state versus serial |
| First mismatch | Restore prefix parity, discard group, one-strike serial fallback | Real-prefix mismatch and next token/state comparison |
| No draft, short output and EOG draft | Ordinary decode without target | Repeated real-model ID/counter owner |
| Error/cleanup | Preserve session poisoning and final synchronization | Existing return-path owner; injected GPU failure remains a product-admission deferral as in the three-draft trial |
| Other model/backend | No normal-path or generic-model gate | Backend parity deferral and handoff next action |
