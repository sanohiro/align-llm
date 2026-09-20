# Backend parity register

This register records every intentional or unfinished difference between the CPU, Metal and CUDA
execution of align-llm, so that "which backend has this?" is answered here rather than re-derived.
Evidence references are pinned at the commit that last edited this file
(see `git log -1 -- docs/backend-parity.md`); references into files that this branch also edits
use the post-edit line numbers and drift afterwards; update the row, not the reader. The rule
that maintains this file is in `CLAUDE.md`
("Backend parity") and `docs/review-checklist.md`.

Status vocabulary, one value per backend cell:

| Status | Meaning |
| --- | --- |
| `done` | Implemented on that backend and its owner evidence passed there. |
| `unmeasured` | Code reaches that backend, but no measurement or qualification ran on that hardware. |
| `leftover` | Intended for that backend and not yet done; must name a `HANDOFF.md` next action or a deferral reason. |
| `inherent` | A property of that backend (kernel numerics, driver, build system); no port is intended. |
| `n/a` | The item has no meaning on that backend, with the reason in the row. |

"Unmeasured on another backend" is a recorded status, never an omission.

## 1. Execution paths

| Path | CPU | Metal | CUDA | Notes |
| --- | --- | --- | --- | --- |
| Resident GPU session (`runtime_execution`, `runtime_generation`, `runtime_qwen`, `runtime_olmoe`, `runtime_kv`, `runtime_weights`) | `leftover` | `done` | `done` | The session refuses CPU in three places: `src/runtime_options.align:139`, `src/runtime_execution.align:81`, `scripts/ggml_shim.c:1248-1256`. Leftover: CPU plan item C3. |
| Legacy per-layer path (`decode_step`, `moe_decode_step`, `model_forward`, `moe_model_forward`, alignpack claims, host KV planes) | `done` | `n/a` | `n/a` | Selected when no runtime options path is given (`src/provider_runtime.align:183-191`, `:280-320`); opens `DEVICE_KIND_CPU` (`src/decode_step.align:3947`). It is also the G1 numeric reference arm: the qualification's CPU case is the options-less execution of the same Align image linked against a static ggml CPU build, asserted `decomposed` with no GPU observations (`scripts/gpu_qualification_native.py:217-230`, `docs/specs/gpu-runtime.md:284-292`, `:318`). Retiring it requires a replacement deterministic reference first. |

## 2. Code gates and mechanisms

| Item | Kind | CPU | Metal | CUDA | Reason for the difference | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| F16 KV attention policy 2, OLMoE sessions | code gate | `leftover` (C3) | `done` 2026-09-13 | `done` 2026-09-14 | Legacy CPU planes are F32-only (`src/kv_plane.align:38,348,468,891`). | `src/runtime_generation.align:398`; O1 `d60e2b6`; PR #243 `ae6eac7`. |
| F16 KV attention policy 2, Qwen sessions | code gate | `leftover` (C3) | `done` 2026-09-14 (`0a1c19b`) | `done` 2026-09-20 (`ba9ea4f`); local speed NOT_MET | Legacy CPU planes are F32-only (`src/kv_plane.align:38,348,468,891`); the remaining difference is CPU-only (C3). Commit `0a1c19b` (2026-09-14) narrowed it to Metal on review Finding 1: "exclude CUDA pending dedicated qualification". The inspection at base `4bf8011` additionally recorded CUDA SET admission (same-type only) as a blocker; PR #243 added the indexed SET_ROWS prefill path, and `runtime_kv.prefill_chunk` (`src/runtime_kv.align:102-120`) already branches on `gpu_kv_prefill_indexed` for both models, so the remaining requirement is the dedicated CUDA qualification. Dedicated CUDA qualification passed on 2026-09-20 (see P1 in section 5); the paired campaign measured +6.7% on the long-context Qwen cases, below the 15% floor. | `src/runtime_generation.align:270`; `docs/specs/cuda-optimization-enablement.md:56`. |
| Indexed prefill KV write (SET_ROWS with I32 indices) | code gate | `n/a` (session only) | `unmeasured` (P4) | `done` 2026-09-14 | Enabled only when policy 2 and backend registry name `"CUDA"`; Metal keeps in-place SET conversion, which its pinned backend admits. Whether SET_ROWS is faster on Metal is unmeasured. | `scripts/ggml_shim.c:2632-2636`; `scripts/run-cuda-kv-prefill-smoke`; `src/runtime_kv_prefill_smoke.align:38,47`. |
| Early MoE router-weight expansion | code gate | `n/a` (host routing) | `done` | `done` | Gate is `session_graph` only, not backend; motivated by CUDA softmax/top-k fusion semantics, executes on both session backends. | `src/runtime_olmoe.align:303-305`; `docs/gpu-cuda-session-repair.md:11-25`. |
| Whole-graph reuse keyed by topology | mechanism | `leftover` (C3) | `done` | `done` | Legacy path rebuilds per layer per token: `GRAPH_BUILD_ALLOC` 163 ms, `GRAPH_TEARDOWN` 400 ms per fixed OLMoE request. | `scripts/ggml_shim.c:1077` (graph keys), `:3129` (topology `memcmp`); `docs/specs/r8-olmoe-post-optimization-remaining-decode-diagnosis.md:118-133`. |
| In-graph MoE routing | mechanism | `leftover` (C3) | `done` | `done` | Legacy path reads router IDs into Align and selects claims per layer. | `docs/specs/gpu-runtime-performance.md:167-171`; `src/runtime_olmoe.align:181`. |
| Flash attention (`flash_attn_ext`, F32 precision) | mechanism | `leftover` (C3) | `done` | `done` | Legacy path is decomposed; the qualification asserts the CPU reference arm reports `decomposed`. ggml's CPU backend supports the operation, so a CPU session must keep a decomposed reference arm or extend the calibration contract. | `src/runtime_attention.align:72`; `scripts/gpu_qualification_native.py:226`. |
| Capped-read resident loaders | code | `n/a` (alignpack claim `pread`) | `done` 2026-09-13 | `done` 2026-09-20 (startup −90.25% OLMoE, −30.66% Qwen, 5/5) | Loader code is backend-independent with Darwin and Linux smoke arms; measured on Metal on 2026-09-13 and on CUDA on 2026-09-20. | `src/runtime_qwen_load.align`, `src/runtime_olmoe_load.align`; `docs/gpu-moe-diagnosis.md:230-286`; `docs/specs/cuda-optimization-enablement.md` "Capped-read loader startup measurement on CUDA (2026-09-20)" Result. |
| Dispatch/caching/sampling optimization `5efd7a0` (2026-09-14) | code | `done` (one shared line, `runtime_sampler.finite_f32`; rest `n/a`, session-only) | `unmeasured` (P7) | `unmeasured` (P7) | 13 shim hunks, all inside `align_gpu_*` entry points or `struct align_gpu_device_state`. No document records which host measured it. | `git show --stat 5efd7a0`; `docs/specs/cuda-optimization-enablement.md:58`. |
| Greedy argmax single load and `to_bits` (PR #274) | code | `leftover` (C2) | `done` | `done` | Six legacy loops remain `value > best_value`: `src/decode_step.align:493`, `src/moe_decode_step.align:618`, `src/model_forward.align:2667,2811`, `src/moe_model_forward.align:2464,3046`. `runtime_sampler.select` is shared and done. | `src/runtime_generation.align:681`; `src/runtime_sampler.align:24`. |
| `ggml_ffi.null_handle()` as a `pub` const | code | `leftover` (C2) | `leftover` (C2) | `leftover` (C2) | Call counts are CPU-weighted (`moe_decode_step` 44, `moe_model_forward` 34) but `runtime_generation` has 3. | `HANDOFF.md` next action 2. |
| ggml CPU thread count | code | `leftover` (C1) | `n/a` | `n/a` | The shim never sets `n_threads`; ggml's CPU default applies. Reduction order may change with threads, so the zero-bit CPU reference arm must stay deterministic. | `grep -c n_threads scripts/ggml_shim.c` = 0. |
| `mmap` / demand paging | mechanism | `leftover` (C4; deferred to the G2/R10 constrained-memory lane) | `n/a` | `n/a` | llama.cpp baseline capability; evaluated only under the G2/R10 lane. | `docs/specs/gpu-runtime-performance.md:288,406`. |
| CUDA build flags `GGML_CUDA_GRAPHS=ON`, `GGML_CUDA_FA=ON`, sm_89 | build | `n/a` | `inherent` (own flags `GGML_METAL_EMBED_LIBRARY`, `GGML_METAL_NDEBUG`) | `inherent` | Metal has no graph-capture switch; its backend fuses internally. | `scripts/gpu_backend_recipe.py:69-88`. |
| Flash tolerance 2.5e-4 (CUDA) vs 1e-4 (Metal) | test | `n/a` | `inherent` | `inherent` | Kernel numerics, not an optimization. | `scripts/gpu_attention_policy_smoke.c:35,98,118`; `docs/specs/cuda-optimization-enablement.md:228`. |
| Bundle/platform gates and host probing | build | `n/a` | `inherent` (Darwin/arm64, sysctl) | `inherent` (linux/x86_64, `nvidia-smi`, `nvcc`) | Environment identity. | `src/runtime_bundle.align:340-347`; `scripts/gpu_backend_recipe.py:831-834`; `scripts/gpu_qualification_host_observation.py:82-83,144`. |
| Platform profile gate | qualification | `n/a` | `done` (`darwin-aarch64-v1`) | `leftover` (no Linux/CUDA profile gate; deferral: not required by any accepted ledger) | | `scripts/check-darwin-profile`. |
| Frozen numeric corpus and precision probe | qualification | `n/a` | `done` (`eval/gpu/metal/`) | `leftover` (no `eval/gpu/cuda/`; deferral: CUDA uses the shared 19-case acceptance) | | `eval/gpu/metal/README.md`. |

## 3. Measurements and qualifications

| Item | CPU | Metal | CUDA | Notes |
| --- | --- | --- | --- | --- |
| Paired campaign vs `llama-server` | `done` (darwin-aarch64: item 78, 2026-09-06, 84.062 s vs 14.174 s time to passing patch; item 69, 2026-09-05, 91.4 s vs 14.0 s, 6.53x slower) / `done` (linux-x86_64: C0, 2026-09-20, runtime 17.54 s vs llama-server 11.29 s time to passing patch, 1.55x; per-candidate about 7x) | 2026-09-09, candidate `12a633d`, all 16 comparisons fail the 15% floor; predates O1, capped-read and `5efd7a0`: `unmeasured` at current main (P3) | 2026-09-09, runtime `688232c`, all 16 fail; predates O1, PR #243, capped-read and `5efd7a0`: `unmeasured` at current main (P3); its OLMoE startup of 16,483 ms is explained by the pre-`594981c` loader (P2) | `docs/gpu-metal-campaign-result.md`; `docs/gpu-cuda-final-measurement-result.md`; `docs/specs/roadmap.md:1704-1719`. |
| F16 KV local paired intervention | `n/a` | `done`: 44.00 / 46.00 / 63.33 / 73.82% request-wall reduction, 5/5 (`d60e2b6`) | `done`: 27.47% OLMoE long-cached, 5/5 (`48f249b` vs `4bf8011`, old compiler `f502fe3d`) | `docs/gpu-moe-diagnosis.md:165-229`; `eval/benchmarks/cuda-kv-f16-2026-09-14.json`. |
| Capped-read startup paired campaign | `n/a` | `done`: Qwen 24.05%, OLMoE 61.58%, 5/5 | `done` 2026-09-20: OLMoE 17.125 s → 1.669 s (−90.25%), Qwen 2.777 s → 1.921 s (−30.66%), 5/5 both; rchar 54.48 GB → 4.57 GB OLMoE | `docs/gpu-moe-diagnosis.md:230-286`; `docs/specs/cuda-optimization-enablement.md` "Capped-read loader startup measurement on CUDA (2026-09-20)" Result. |
| GPU per-kernel profile | `n/a` | `done`: Metal GPU Counters, `kernel_cpy_f32_f16` 46.03% (2026-09-13) | `unmeasured` (P6): only CUDA Graph launch/capture counts and `nsys` overlap counts exist | `docs/gpu-moe-diagnosis.md:101-124`; `docs/specs/cuda-optimization-enablement.md:18-26`. |
| Host-side profile | `done`: r8 leaf buckets, 2026-09-05 | `done`: macOS `sample`, backend completion wait 94.82% | `unmeasured` (P6) | `docs/specs/r8-olmoe-post-optimization-remaining-decode-diagnosis.md:116-146`; `docs/gpu-moe-diagnosis.md:19`. |
| Binary/compiler audit | `unmeasured` (x86-64: disassembly observations only; deferral: no accepted ledger requires an x86-64 audit) | `done`: Apple M1 audit at pin `8c8bfbc7` | `n/a` (host-CPU audit; see the CPU cell) | `HANDOFF.md` "Completed work: Mac-native binary optimization audit"; `docs/align-requests.md:442,469,521`. |
| Q/K/V lifetime / stream concurrency | `n/a` | `n/a` (stream concept) | `done`, NOT_MET 1.32% | `eval/benchmarks/cuda-qkv-lifetime-2026-09-14.json`. |
| Latest Align pin adoption (`8c8bfbc7`) | `done` (`make check` only) | `unmeasured` (P5) | `done` on session build `46aea33` | `HANDOFF.md` "## Completed capability: latest merged Align adoption". |
| Independent 16-request session oracle | `n/a` | `done` `d60e2b6` | `done` `688232c`, `46aea33` | Receipts do not record the attention policy (P8). |
| G1 19-case numeric acceptance | `done` (reference arm) | `done` `5ae5351` | `done` `688232c` (19x2) | `docs/specs/gpu-runtime.md:6-7`; `docs/gpu-cuda-session-repair.md:57`. |

## 4. Document staleness recorded here

| Statement | Location | Actual state | Handling |
| --- | --- | --- | --- |
| Policy 2 is Metal-only; the CUDA run skips the retained-half test | `docs/specs/cuda-optimization-enablement.md:56,157` (inspection base `4bf8011`) | Since `ae6eac7` CUDA OLMoE sessions select policy 2 and the guard is removed (`scripts/gpu_attention_policy_smoke.c`, the `MTL` guard around `retained_f16_kv` removed by `ae6eac7`) | Dated status note added 2026-09-20. |
| "CUDA remains pending" | `docs/specs/gpu-runtime.md:3` | CUDA G1 and session qualification passed at `688232c` | Dated status note added 2026-09-20. |
| `scripts/run-cuda-graph-optimization-smoke` | `docs/specs/cuda-optimization-enablement.md:153` | Does not exist; CUDA-GRAPH-ENABLE is deferred | Recorded here; no change until that capability resumes. |

## 5. Open leftovers

Ids are stable labels, not an order. `HANDOFF.md` owns the priority of these items and mirrors
each id as a next action.

| Id | Leftover | Backend | Kind | Owner evidence when done | Known prerequisite / blocker |
| --- | --- | --- | --- | --- | --- |
| P1 | Select F16 KV policy 2 for Qwen sessions on CUDA (`src/runtime_generation.align:270`), verifying CUDA row-write admission for the Qwen prefill path | CUDA | code | Passed 2026-09-20: `run-cuda-kv-prefill-smoke`, `run-gpu-session-reuse-smoke` (deterministic GPU stub, no hardware), `run-gpu-attention-policy-smoke` on CUDA0, `run-gpu-session-independent` 7/7 Qwen and 9/9 OLMoE, `run-gpu-session-host-capacity` both models, `make check`, `check-python-boundary --strict`, `measure-cuda-optimization --self-test`; paired campaign twice against candidate build `source_commit` `82dab13`, the pre-rebase form of `f874c10` with an identical measured closure (`git diff --stat 82dab13 e2f4d15 -- src scripts eval .align-revision Makefile` is empty), primary +6.71% / +6.69%, 5/5 faster, NOT_MET | Done; no rerun scheduled. Both campaign receipts are observer-invalid because the Claude Code CLI process itself exceeded the 0.1-core foreign threshold. Deferral: two consistent runs bound the effect at about 6.7%, below the floor, so a valid receipt is required only if a shipping performance claim is ever made; it would be taken from a terminal without a Claude Code session. |
| P2 | Measure capped-read loader startup on CUDA | CUDA | measurement | `measure-cuda-optimization --protocol startup` receipt `gpu-cuda-parity-20260920/p2-run1/p2-startup/result.json` (local evidence store, outside Git) (schema 2), self-test PASS, `check-python-boundary --strict` PASS | Done 2026-09-20 with the synthetic control `5fbecf17` at the current pin; receipt observer-invalid (Claude Code CLI CPU), same deferral as P1. |
| P3 | Re-run the `llama-server` paired campaigns at current main, CUDA first then Metal, with a fresh precommitted ledger | CUDA, Metal | measurement | `scripts/run-gpu-session-measurement --campaign cuda-final` and the §6.1 Metal campaign | Both existing campaign drivers freeze their candidate commits; a fresh precommitted ledger is required before any run. |
| P4 | Try indexed SET_ROWS prefill on Metal and measure | Metal | code + measurement | Attention policy smoke on MTL plus a paired local campaign; optional, Metal SET works today | none known |
| P5 | Verify pin `8c8bfbc7` on the Mac session build | Metal | qualification | `run-gpu-session-independent` 16 requests on Metal | none known |
| P6 | CUDA per-kernel duration profile and host-side profile of the manifested worker, to match the Metal counter trace and `sample` profile | CUDA | diagnosis | Bounded `nsys` kernel summary on the manifested worker, retained outside Git | none known |
| P7 | Record the host that measured `5efd7a0` or measure it on both | Metal, CUDA | measurement | Paired local campaign; update this register | none known |
| P8 | Record the selected attention policy name in the session ready frame so receipts prove policy selection | CPU, Metal, CUDA | code (exchanged format; design gate) | session reuse smoke, independent session | none known |

## 6. CPU plan

Facts: CPU inference is the legacy per-layer path, is several times slower than llama.cpp's CPU
server on the fixed OLMoE coding request (item 78, 2026-09-06: 84.062 s versus 14.174 s; item 69,
2026-09-05: 6.53x slower), and is also the G1 numeric reference arm.
None of the resident-session mechanisms in section 2 reach it. No document freezes or deprecates
it; `docs/specs/gpu-runtime-performance.md:172-174` retains "the existing CPU provider". The plan
below adds to it and decides its fate on measurement. `HANDOFF.md` owns the order:

| Id | Item | Gate | Owner evidence | Known prerequisite / blocker |
| --- | --- | --- | --- | --- |
| C0 | Re-establish the CPU baseline at current main with the item-69 fixed-request protocol, per host profile; the latest CPU measurement is item 78, 2026-09-06, and nothing CPU-side has been measured since | none (baseline, not `MET`/`NOT_MET`) | `run-olmoe-platform-sampled-runtime-baseline --self-test` PASS; `--print-identity` MATCH; baseline COMPLETE 145 s; `check-python-boundary --strict` PASS | Done 2026-09-20 on linux-x86_64-v1 (receipt `c0-run1/result.json`, outside Git); the Darwin profile is carried at pin `8cefc803` and needs `--print-identity` on the M1 before it can run there. |
| C1 | Set the ggml CPU thread count. Decide between a shim default (physical cores) and a runtime option; an option changes runtime options schema 1 and triggers the design gate. The CPU reference arm must remain deterministic (single-threaded or fixed reduction order) or the zero-bit calibration contract must be revisited | design gate if an option; none for an internal default that keeps the reference arm unchanged | Item-69 protocol paired against C0; G1 19-case acceptance unchanged | none known |
| C2 | Apply the CPU-weighted application items already listed in `HANDOFF.md`, including the shared `null_handle` const: `prime_window` fill via `buffer.filled`, `stage_kv` on the Qwen path, member columns built once, `digest_region` behind the oracle flag, `Outcome` hot/cold split, the six argmax loops | none | Existing CPU smokes and the item-69 protocol | none known |
| C3 | Allow the resident session on the ggml CPU device by lifting the three refusals, so graph reuse, in-graph routing, flash attention, F16 KV and the capped-read loaders reach CPU in one move. The legacy path stays as the numeric reference until the calibration contract defines a deterministic replacement | design gate: runtime options schema (backend allowlist), shim registry boundary, calibration contract | Session reuse smoke and independent session oracle on CPU; item-69 protocol paired against C0 | none known |
| C4 | Evaluate `mmap`/demand paging against llama.cpp's baseline only within the G2/R10 constrained-memory lane | G2/R10 ledger | That lane's protocol | none known |
