# CUDA resident OLMoE session repair

The three OLMoE serial-output discrepancies reported in `gpu-cuda-campaign-result.md` are fixed.
The unchanged independent session owner now passes Qwen 7/7 and OLMoE 9/9. A separate native
validator admission defect is also fixed. Qwen then passes the real coding retry on attempt 2;
OLMoE exhausts eight attempts, generating an incorrect `stop - 1` patch. Replaying those exact
requests against the independent reference reproduces every candidate output. This remaining
coding-quality failure blocks performance measurement; it is not a remaining output discrepancy.

## Cause and bounded repair

Pinned llama.cpp `bb4caa7540188872173c44d161602d9271386413` expands the gathered MoE router
weights before expert work in `llm_graph_context::build_moe_ffn`. Our resident graph expanded
its complete layer later, letting expert-id dependencies interrupt the contiguous
softmax/reshape/argsort/view/gather sequence required by CUDA's top-k MoE fusion.

The difference affects the numerical path, not just launch cost. A fresh long request agreed,
and the first fresh seed-42 request agreed, but the repeated seed-42 request differed. Disabling
CUDA graph capture did not remove the discrepancy. Disabling fusion gave bitwise-equal logits;
selectively splitting the reference at router softmax did too, while RMS-normalization and
expert-matmul controls did not. The first seed-42 logits differed by up to 0.5802478790283203
with ordinary fusion; all 50,304 values matched in that row with router fusion suppressed.
These are diagnostic controls, never shipping environment overrides or relaxed acceptance.

`runtime_olmoe.build_prefill_chunk` and `build_decode_diagnostic` now expand the gathered router
weights before expert work for explicitly selected session graphs and their pre-upload plans,
matching the pinned graph. Single-shot builders retain their established traversal. No tensor, sampler, global fusion flag,
threshold, CPU path or public format changes. The original failed requests 5, 7 and 8 pass under
the unchanged full serial history. G1's diagnostic tensor observations inhibit the relevant
fusion, explaining why its earlier bitwise acceptance alone did not reveal the production issue.

On native Linux, `validate_patch_details` previously passed an external task-owned patch without
setting `ALIGN_LLM_TEMP_ROOT`, so the validator correctly refused its path. It now supplies the
resolved work directory in a copied child environment, matching the container branch's existing
explicit admission. Caller environments and task allowed-edits/validation policy are unchanged.
The self-test covers inherited and explicit environments, overriding a stale root while preserving
unrelated values and leaving the caller environment unmodified.

## Evidence

Runtime repair checkpoint: `c3426328550c12c38f0877d3452880903c26b363`.
Native validator repair checkpoint: `ffe4232` (runtime source unchanged from `c342632`).
Host/model/bundle/toolchain identities are the same as the original CUDA report. Full evidence
is retained outside Git under `gpu-cuda-session-repair`; exploratory interposed binaries remain
separately under `cuda-session-diagnosis` and are not qualified production artifacts.

- `make fmt`: PASS.
- `scripts/run-gpu-session-reuse-smoke`: PASS, including injected decode/readback failure.
- `python3 scripts/run-olmoe-coding-decision --self-test`: PASS.
- `scripts/run-gpu-session-independent --profile PROFILE --runtime SESSION/main --reference REFERENCE/session-reference --output NEW_DIRECTORY`: PASS, all 16 requests, manifested runtime at `c342632` and unchanged independent reference. Receipt SHA-256 `527b513ed4998a3f585037bc566bd472fef437d4b707c7a5703dbf78f531eb4d`.
- `scripts/run-gpu-session-host-capacity --profile PROFILE --candidate SESSION --align-source PINNED_ALIGN_SOURCE --output NEW_DIRECTORY`: PASS on both models at `c342632`, including oversized-input refusal and subsequent reuse. Receipt SHA-256 `0fa7164c1d0213d052cc611b4336701b8913598c938ca6516649187a459db718`.
- `scripts/run-gpu-session-coding-smoke --profile PROFILE --runtime SESSION/main --output NEW.json`: FAIL after the native-validator repair; Qwen attempt 2 passes, OLMoE attempts 1–8 fail. The original owner produces no success receipt on failure; retain `logs/session-retry-fixed-validator.log`. The diagnostic extraction `retry-failed-attempts.json` binds this log and all eight OLMoE attempts; SHA-256 `84040ae96e0c4f6269a4e4d9f21c1b9ae85edc6843701bdef81508d7a42bbd53`.
- Independent reference replay of the exact eight retry requests, including actual validation feedback: all eight emitted outputs equal the candidate. `retry-reference.jsonl` SHA-256 `7a9786e53c189eb569051f23fde3471a49bccc82b24fddcdab1f66e5146ae2b5`. This is a diagnostic output comparison, not a passing patch result.
- Complete G1 acceptance at `ffe4232`: FAIL at OLMoE calibration after Qwen passes. All 100,608 production-logit scalars differ; diagnostic kinds 2–6 remain bitwise equal. The instrumented reference supplies both expected streams, exposing the unconditional expansion's single-shot regression. The review repair scopes expansion to session graphs without changing tolerances; its full acceptance/replay is pending.

No CUDA performance campaign ran. Historical FAIL receipts and the original Metal campaign remain
unchanged. The frozen measurement candidate still names the original runtime; a future campaign
must explicitly nominate the repaired runtime and satisfy its coding-quality prerequisite before
timing. Download/build time remains outside performance metrics. No new Align capability gap is
evidenced by either defect.

The bounded retrospective confirms the value of production-session qualification alongside
instrumented tensor checks: observation can prevent backend fusion and hide a production-path
difference. Keep the existing real serial regression and native environment self-test; no new
routine aggregate is added.
