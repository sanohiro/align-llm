# Qwen3.5 target-row greedy cost screen (2026-09-28)

The current Align-owned continuous lookup trial reads four F32 logits rows
after each full-model target graph and scans them on CPU. On the measured 2B
GGUF this is 3,973,120 bytes per group; the repeated bug-fix task has eleven
groups. Test whether an independent Metal four-row finite, first-index argmax
can reduce that boundary's latency after including its command submission and
required completion wait. The hypothesis is limited to this boundary; a local
win does not imply a request win.

The first screen consumes one actual-weight four-row F32 capture from the
existing exact-prefix diagnostic. A developer-only benchmark owns a single
shared input buffer, reusable partial/result buffers and a Metal queue. It
compares (a) a copy into a separate host staging buffer plus the same finite
first-index scan semantics as Align and (b) two native Metal dispatches with
an explicit buffer barrier and a final completion wait. Inputs are uploaded
once before timing; each alternating pair processes the same four rows and
checks all four IDs. Synthetic tie, NaN/infinity and nonmultiple-row cases
must validate the native reduction before timing. Record CPU wall, Metal
submission/wall and available GPU command intervals separately. Preserve all
adverse pairs after warmup; use at least five alternating pairs of repeated
operations. The screen must not omit a needed wait or account an input upload
only to one arm.

Cost ceiling before implementation: one Metal command buffer and two
dispatches per four-row evaluation, one explicit barrier, partial/result
scratch at most 16 KiB for the measured vocabulary, no second model arena,
and no ggml source patch. The captured 3,973,120-byte input and separate CPU
staging buffer belong only to the diagnostic. Build and screen each <=900 s.
No fixed improvement percentage determines the outcome.

If the synchronized native boundary is locally credible, the next part of
this capability is a default-off real-model connection selected by Align,
using the existing borrowed Metal allocation rules, with exact token/state
checks and five alternating complete-request pairs against the unchanged
Align path and pinned llama.cpp. If native loses the boundary, report the
measured result and withdraw this mapping without adding it to product
inference. Other Metal generations, CUDA, Qwen shapes and Gemma remain
unmeasured until separately qualified.

## Connected trial contract

The initial actual-weight local screen returned the same four IDs as Align,
including synthetic tie, nonfinite and tail cases. Five alternating pairs of
100 complete evaluations gave 0.285 ms paired median CPU copy/scan minus
synchronized native command per group. This is sufficient to trial the real
boundary, not an adoption claim. Align's separately timed CPU scan and the
actual target F32 readback are retained as attribution checks, not added as
a fabricated whole-request estimate.

| Field | Trial contract |
| --- | --- |
| Surface and owner | Add an explicit `generate_session_lookup_trial_native_greedy` Align entrypoint and a `trialnative` developer arm. The existing normal, three-draft and one-draft entrypoints retain their selection. No product option or persisted format changes. |
| Device boundary | Add one checked shim ABI `align_gpu_slot_native_target_greedy(owner, slots, output_slot, rows, vocabulary, result, result_bytes) -> i32` with an unsupported stub. It borrows only a contiguous F32 Metal shared output tensor of exact `rows * vocabulary * 4` bytes, checks the backing allocation/offset, and writes exactly `rows` I32 results after a complete native command. The Metal helper reuses the existing session-owned device/queue and a cached borrowed view; Align owns graph construction, matching, state and token publication. |
| Inputs and result | Trial admission requires the existing mixed native state-copy Metal session, three drafts/four target rows, finite logits and valid shape/capacity. If native prefill state-copy is also enabled, Align finishes it before the reduction. The native two-dispatch reduction returns first-index greedy IDs or an error; nonfinite values, invalid IDs, missing shared storage, command failure and malformed count poison the request. An explicit barrier separates partial/final dispatches; a completion wait precedes reading IDs or publishing state. |
| Graph/cache identity | The target graph remains the established all-logits-rows graph; the postgraph native reduction is selected by the explicit Align trial entrypoint. Scratch/view lifecycle is tied to the existing native context; graph invalidation resets borrowed views after draining work. Persisted/cache schema: N/A, no persisted data changes. |
| Allocation and ceiling | One command, two dispatches, one barrier and one completion wait per verified group. Partial/results scratch <=16 KiB at the measured 4x248320 shape. No duplicate logits/weights/KV allocation, no ggml source patch. Build <=900 s and each request <=180 s. Kernel compilation/startup is counted. |
| Correctness and measurement | Exact greedy IDs for actual GGUF real requests; repeat accepted/rejected first groups, short output, EOG draft, invalid request and ordinary-path control. The previous F32/state bounds remain in the independent target screen. Before product admission, connected stepwise state and injected submit/completion faults are required. Compare five alternating pairs on all three pinned prompts against old three-draft Align, normal Align and pinned llama.cpp. Separate target compute, native result command/wait, prefill, serial decode and fresh-process wall. No universal improvement percentage determines the decision. |

If fresh-process samples vary enough to obscure the small boundary change,
the same developer diagnostic may alternate old and native three-draft calls
inside one session after one warmup per arm. It must reset resident state
through the existing session path, retain exact IDs on every request, and
report every pair including adverse ones. This isolates per-request generation
from repeated model loading but does not replace the fresh-process comparison.

| Closure case | Owner and direct evidence |
| --- | --- |
| Construction and malformed input | Native context admission, checked shim extent and Align explicit arm; local tie/nonfinite/tail plus invalid mode/capacity controls. |
| Success and reuse | Same logits graph, synchronized native command and Align acceptance; exact IDs across all three prompts and repeated requests. |
| Rejection and failure | Existing one-strike parity restoration; native refusal/failure returns an error before publishing the request. Connected state and forced device failures remain mandatory before default admission. |
| Invalidation/cleanup | Existing owner reset/close drains commands and clears borrowed views; short/long/short repeated session owner. |
| Other backends/models | Unsupported shim response or no explicit arm; backend parity records M1 evidence and defers other devices/architectures. |
