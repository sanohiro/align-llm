# C3: resident session on the ggml CPU device

Register item: `docs/backend-parity.md` section 6, row C3. This document is the authoritative plan
for that row and triggers the proportional design gate in `CLAUDE.md` because it changes a public
CLI/exchanged format (`runtime_options` schema 1 `backend` value set, `GPU_BACKEND_BUNDLE` schema 1
`backend` value set), an ownership boundary (host memory admission), and a coordinated invariant
across more than three modules (`runtime_options`, `runtime_bundle`, `runtime_device`,
`runtime_execution`, `runtime_generation`, `ggml_shim.c`, `gpu_backend_recipe.py`).

Evidence references are pinned at the commit that last edited this file.

## 1. Consumer outcome and scope

A caller that today runs the options-less legacy per-layer CPU provider can instead pass a
`backend: "cpu"` runtime-options document and get the resident session: whole-graph topology reuse,
in-graph MoE routing, `flash_attn_ext`, F16 KV, capped-read loaders and `GpuDevice`-owned
weights/KV, on the ggml CPU device, with no GPU present. The consumer-complete capability is
"a CPU host runs `main --runtime-session` and `run-gpu-session-independent` against a CPU bundle and
gets byte-identical text to the upstream CPU oracle".

In scope:

- lifting the three CPU refusals (`src/runtime_options.align:139`, `src/runtime_execution.align:81`,
  `scripts/ggml_shim.c:1248-1256`);
- a CPU backend bundle (`libggml-cpu.so`, registry name `CPU`) produced by the existing recipe;
- host-resident memory admission so one host budget bounds the whole process;
- attention-policy admissibility on the CPU device;
- the CPU arms of the session owner tests and one C0-protocol paired measurement.

Out of scope, with reasons recorded in section 8: retiring the legacy per-layer CPU path; adding a
CPU-session arm to the G1 19-case numeric acceptance; zero-copy weight residency
(`buffer_from_host_ptr`/`mmap`, owned by C4's G2/R10 lane); the ggml CPU thread count (C1);
indexed SET_ROWS prefill on CPU (stays CUDA-gated).

## 2. The reference-arm question (decided)

**Recommendation: keep the legacy options-less path as the G1 numeric reference arm. Do not add a
CPU-session arm to the G1 19-case acceptance in C3. Admit the CPU session through the session-level
independent oracle, exactly as Metal and CUDA are admitted.**

Three reasons, each a checked property of today's code:

1. **The reference arm is defined as plugin-free, and the session is not.** The G1 CPU reference is
   a statically linked CPU-only executable built by `scripts/gpu_cpu_reference/build.cmake` with
   `GGML_BACKEND_DL=OFF`, `ALIGN_GGML_STATIC_CPU_ONLY` set for its shim, and no backend plugin as a
   runtime dependency (`docs/specs/gpu-runtime.md` §3.5, CPU-reference preparation). The
   `gpu-cpu-reference-build` qualification proves the point by placing a constructor-bearing plugin
   beside the executable and showing it is not loaded. A CPU *session* must load `libggml-cpu.so`
   through `ggml_backend_load` from a staged bundle. Making the session the reference would delete
   that property and silently change the reference build identity that
   `comparison.reference = "cpu-same-build"` names.
2. **Reference and candidate would share the graph builder.** The reference arm today executes
   `decode_step`/`moe_decode_step`/`model_forward`/`moe_model_forward`; the candidate executes
   `runtime_qwen`/`runtime_olmoe`. A CPU-session reference would put both arms on the same graph
   construction code, so a graph-construction defect would reproduce identically on both arms and
   the 19-case acceptance would stop detecting it.
3. **The frozen expectations cannot be reused, and tolerances cannot be re-opened.** §3.7 freezes
   `expected_token_ids` as "the nonempty same-build CPU sampling result" and states that tolerances
   and expected outputs cannot be enlarged after a failure. A CPU session selects `flash_attn_ext`
   and F16 KV, a different reduction order and a different KV precision, so every frozen expectation
   would have to be re-derived. Re-freezing a numeric contract is a separate capability, not a side
   effect of lifting a backend allowlist.

Closure. C3 changes nothing in `gpu_qualification_native.py`, the qualification profile schema, the
calibration schema, or `eval/gpu/*` corpora for the `cpu` execution. The existing assertions at
`scripts/gpu_qualification_native.py:217-230` (CPU arm reports `decomposed` and zero GPU
observations) remain literally true because the G1 CPU arm keeps `options_path == ""` and the
options-less path. A regression test locks this: `gpu-cpu-session-not-reference` (closure matrix in section 5, step 10 of section 7)
asserts that `scripts/gpu_qualification_native.py` contains no `cpu_resident` execution and that the
profile `execution` enum is still exactly `{cpu, gpu_resident}`.

Deferral recorded for a later capability, provisionally **C5**: "replace the legacy CPU reference
arm with a deterministic CPU-session reference". Its prerequisites are (a) a fixed, documented CPU
thread count so the reduction order is deterministic (C1), (b) a CPU-session build whose registry
provenance is verifiable the way `ALIGN_GGML_STATIC_CPU_ONLY` is today, (c) a re-freeze of every
calibration `expected_token_ids` under `decomposed` attention and F32 KV, and (d) a different
candidate graph builder or an accepted argument that reason 2 above no longer applies. Until C5
lands, C3 must not remove any legacy CPU code; the parity register row for the legacy path stays
`done`.

## 3. Public-contract ledger

One row per surface. `N/A` carries its reason.

### 3.1 `runtime_options.decode` — `backend` value set

| Field | Contract |
| --- | --- |
| Surface | `pub fn runtime_options.decode(document: str) -> Result<RuntimeOptions, Error>` (`src/runtime_options.align:134`), reached by `load(path)`. |
| Inputs / defaults | `backend` accepts exactly `metal`, `cuda`, `cpu`. No default; the field stays required. Every other field keeps §3.1 semantics. `device` is the exact registry device name, which on the ggml CPU backend is `CPU`. |
| Results / errors | Unchanged: `Ok(RuntimeOptions)` or `Err(Error.Invalid)`. A document naming any fourth backend is still invalid. |
| Ownership / allocation | Unchanged. `decode` owns the decoded record; `read_bounded` keeps the 16,384-byte ceiling. |
| Owner module | `src/runtime_options.align`. |
| Persisted / cache identity | The options document is an input file, not a persisted artifact; it is hashed into `measure-cuda-optimization` receipts and the qualification profile as `runtime_options` rows. Adding a value to an enum does not change any digest of an existing document. |
| Schema version | **Stays 1.** Widening a value set is not a structural change: a schema-1 reader that predates this change refuses a `cpu` document (fail-closed), and every existing `metal`/`cuda` document stays byte-identical and valid. Bumping to 2 would invalidate every checked-in profile row, every bundle, `gpu_independent_corpus.py`'s `schema_version` bound and `measure-cuda-optimization`'s admission, for no reader benefit. `docs/specs/gpu-runtime.md` §3.1 is updated in place: the `backend` row becomes `metal\|cuda\|cpu`, and the sentence "An explicit CPU options document is invalid; the established empty path selects CPU" is replaced by "An explicit `cpu` options document selects the resident session on the ggml CPU device; the established empty path still selects the legacy per-layer CPU provider." **Ordering against R9.** `docs/specs/roadmap.md` R9 (prompt-lookup speculation) bumps this same document to schema 2 by adding a required `speculation` field; C3 does not bump it, and the two are not in conflict. C3 is scheduled first (`HANDOFF.md` next actions name C3; R9 is a later roadmap item). If C3 lands first, R9's bump supersedes this cell and its schema 2 reader carries the widened `backend` value set forward unchanged. If R9 lands first, C3 adopts schema 2 unchanged: it widens the `backend` value set inside the schema 2 reader and its Python validators, and still bumps nothing. |
| Validation order | Unchanged, and the backend check keeps its current position (first clause of the single `if`), before device/bundle/placement/budget checks. |
| Prerequisites | None. |
| Acceptance evidence | `make check` (compiler), then `make gpu-config-smoke` (the `Makefile:80` target, a lexical and exact-key validator that loads no ggml) extended with one accepted `cpu` document and one rejected `vulkan` document. |
| Metrics | N/A — a decoder value set has no runtime metric. |

### 3.2 `runtime_options` budget meaning on a host-resident device

| Field | Contract |
| --- | --- |
| Surface | `host_budget_bytes`, `device_budget_bytes` in the same document; consumed by `runtime_generation.prepare_memory` (`src/runtime_generation.align:153-183`) and `align_gpu_memory_admit`. |
| Inputs / defaults | On `cpu`, `device_budget_bytes` is the **resident-tensor sub-budget**: weights + KV + workspace, exactly as on a GPU, but allocated from host RAM. `host_budget_bytes` becomes the **whole-process ceiling** and must satisfy `host_budget_bytes >= device_budget_bytes + metadata + staging + legacy_cache + application_host_reserved`. No new field. |
| Results / errors | A CPU document whose budgets violate that inequality fails admission with the existing `GPU_STATUS_MEMORY_BUDGET` at stage `plan`, returning `Err(Error.Invalid)`. No new failure category. |
| Ownership / allocation | **Two changes, both required.** (a) `runtime_generation.prepare_memory` must reserve the resident-tensor budget out of the host budget *before* it sizes staging. Today (`src/runtime_generation.align:176-189`) it computes `host_remaining := host_budget_bytes - host_used`, then `each_staging := (host_remaining - 64) / 2`, `staging_bytes := min(each_staging, MAX_STAGING_BYTES)` (16,777,216), then `reserve_application(owner, observation_bytes + staging_bytes + 64)`. When `host_remaining` is below `2 * MAX_STAGING_BYTES + 64` the staging cap does not bind and `host_total` saturates `host_budget_bytes` exactly, which would make the native clause below unsatisfiable for any `device_budget_bytes >= 1`. On `cpu`, therefore: `available := checked_sub(host_budget_bytes, device_budget_bytes)?`, the existing `host_used >= host_budget_bytes` refusal becomes `host_used >= available`, and `host_remaining := available - host_used`. `checked_sub` does not exist anywhere in `src/` today; add it as a local helper beside `checked_add` (`src/runtime_generation.align:33`), in that helper's exact shape. Every other backend keeps `available == host_budget_bytes`, so the arithmetic is one substitution, not a fork. (b) The native clause is the fail-closed second gate so no Align caller can bypass it: in `align_gpu_memory_admit`, when `state->host_resident` is set, additionally require `device_total + host_total <= state->host_budget_bytes`. `state->host_resident` is set in `align_gpu_device_open` when `strcmp(registry_name, "CPU") == 0`. |
| Owner module | `src/runtime_generation.align` (`prepare_memory`, change (a); it is shared by both `create_qwen_*` and `create_olmoe_*` paths, so one edit covers both models) and `scripts/ggml_shim.c` (`align_gpu_device_open`, `align_gpu_memory_admit`, `align_gpu_observe_memory`, change (b)). |
| Persisted / cache identity | N/A — admission is in-process state, never persisted. |
| Schema version | N/A — no schema field changes; the meaning of an existing field is narrowed for one backend value and stated in §3.1's prose. |
| Validation order | (a) runs inside `prepare_memory`, after `workspace_bytes` and `host_used` are computed and before `reserve_application`, so an impossible CPU budget is refused with `GPU_STATUS_MEMORY_BUDGET` at stage `plan` before any native reservation. (b) runs in `align_gpu_memory_admit` after `host_reserve` and before `memory_planned` is set: the existing `device_total > device_budget_bytes || host_total > host_budget_bytes` test gains the combined clause in the same `if`, so a violation is still `ALIGN_GPU_MEMORY_BUDGET` before any mutation of `state`. |
| Prerequisites | 3.1. |
| Acceptance evidence | `./scripts/run-gpu-session-reuse-smoke` CPU arm reaches `plan_begin` and allocates (proves (a) is satisfiable); `./scripts/run-gpu-device-smoke` gains a host-resident admission case that sets `device_budget + host_used > host_budget` and expects `MEMORY_BUDGET` (proves (b)); `./scripts/run-gpu-session-host-capacity --profile CPU_PROFILE ...` (section 7 step 11). |
| Metrics | Whole-session requested-allocation peak versus `host_budget_bytes`, the quantity the host-capacity owner already prints as `observed`/`reserved`/`native`. |

### 3.3 Host peak observation on a host-resident device

| Field | Contract |
| --- | --- |
| Surface | `align_gpu_observe_memory` (`scripts/ggml_shim.c:1639`), read through `ggml_ffi.gpu_observation_state(owner, GPU_OBSERVATION_HOST_PEAK)`. |
| Inputs / defaults | Unchanged signature. When `state->host_resident` is set, `host` becomes `align_gpu_memory_allocated_bytes(state, 0) + align_gpu_memory_allocated_bytes(state, 1)`; otherwise it stays field 0. |
| Results / errors | Unchanged: a negative field poisons `observation_failed`. |
| Ownership / allocation | No allocation. |
| Owner module | `scripts/ggml_shim.c`. |
| Persisted / cache identity | The value reaches `run-gpu-session-host-capacity`'s `result.json` as `native_peak` (schema 1, unchanged shape). |
| Schema version | Unchanged. `result.json` keeps `schema_version: 1`; only the recorded number changes meaning on CPU, which the CPU profile's own row documents. |
| Validation order | Called at the existing two call sites inside `align_gpu_memory_allocate`; no reordering. |
| Prerequisites | 3.2 (`host_resident` flag). |
| Acceptance evidence | `run-gpu-session-host-capacity` CPU arm: its existing assertion `native + reserved <= host_budget_bytes` then bounds the true whole-process ceiling without any Python change. |
| Metrics | Same as 3.2. |

### 3.4 `align_gpu_registry_name` and the CPU device

| Field | Contract |
| --- | --- |
| Surface | `static const char *align_gpu_registry_name(const char *backend)` (`scripts/ggml_shim.c:1248`). |
| Inputs / defaults | `"metal" -> "MTL"`, `"cuda" -> "CUDA"`, **`"cpu" -> "CPU"`**, otherwise `NULL`. `backend_name` stays a `char[6]`, which admits `"cpu"`. |
| Results / errors | Unchanged: `NULL` yields `ALIGN_GPU_CONFIG` before the busy latch is taken. A loaded plugin whose `ggml_backend_reg_name` is not the expected string still yields `ALIGN_GPU_BACKEND_UNAVAILABLE` and poisons the registry on a first load. |
| Ownership / allocation | Unchanged. The staging/bundle-pinning machinery is backend-independent and applies to a CPU plugin unchanged. |
| Owner module | `scripts/ggml_shim.c`. |
| Persisted / cache identity | N/A — a process-local registry name. |
| Schema version | N/A. |
| Validation order | Unchanged: bundle-id and budget checks, then `align_gpu_registry_name`, then the busy latch, then registry state. |
| Prerequisites | 3.5 (a bundle that actually contains `libggml-cpu.so`). |
| Acceptance evidence | `./scripts/run-gpu-device-smoke`; the CPU arm of `run-gpu-session-independent`. |
| Metrics | N/A. |

Non-conflict note: with `GGML_BACKEND_DL=ON` every ggml backend, including CPU, is a separate
loadable plugin, and `COMMON_FLAGS` already sets `-DGGML_CPU=OFF` for the Metal and CUDA bundles.
The session executable therefore links only `libggml`/`libggml-base` and registers no static CPU
backend, so `ggml_backend_load` of `libggml-cpu.so` cannot collide with a compiled-in `CPU`
registry. Step 3 of section 7 verifies this on the built bundle rather than assuming it.

### 3.5 `GPU_BACKEND_BUNDLE` schema 1 — CPU backend

| Field | Contract |
| --- | --- |
| Surface | `docs/specs/gpu-runtime.md` §3.6; `runtime_bundle.verify(root, expected_backend, host_budget_bytes)` (`src/runtime_bundle.align:310`); `runtime_bundle.plugin_name` (`:305`); `scripts/gpu_backend_recipe.py` `BACKEND_FLAGS` / `TARGET` / artifact table (`:69-93`, `:831-853`). |
| Inputs / defaults | `backend` becomes `metal\|cuda\|cpu`. `plugin_name` becomes a three-way map with `cpu -> "libggml-cpu.so"` and no fallback: an unknown backend is unreachable because `verify` refuses it first. `target.os` is `macos\|linux` and `target.arch` is `aarch64\|x86_64`; a CPU bundle may use any combination, so the `metal`/else branch at `:340` becomes a three-way branch whose `cpu` arm requires `valid_none_identity(toolchain.toolkit)` and `(os == "macos" && arch == "aarch64") \|\| (os == "linux" && arch == "x86_64")`. `target.gpu_architectures` must stay 1–32 nonempty entries; for CPU it is exactly one entry, `generic-x86_64` or `generic-aarch64`, matching `target.arch`. That identifier is defined by `gpu_backend_recipe.py`, not by ggml, and pairs with `-DGGML_NATIVE=OFF -DGGML_CPU_ALL_VARIANTS=OFF`. `BACKEND_FLAGS["cpu"]` is `("-DCMAKE_INSTALL_RPATH=$ORIGIN" on Linux / "@loader_path" on macOS, "-DGGML_CPU=ON", "-DGGML_CPU_ALL_VARIANTS=OFF", "-DGGML_METAL=OFF", "-DGGML_CUDA=OFF")`, appended after `COMMON_FLAGS` so its `-DGGML_CPU=ON` is last-wins over the common `-DGGML_CPU=OFF`. The artifact table adds `("backend_plugin", "libggml-cpu.so", ...)` plus the same `libggml-base`/`libggml` shared libraries as the host OS variant. |
| Results / errors | Unchanged: `Err(Error.Invalid)` for any manifest that fails a clause; the plugin must appear exactly once with role `backend_plugin` and the expected path. |
| Ownership / allocation | Unchanged: the manifest reservation, `MAX_ARTIFACTS`, `MAX_ARTIFACT_BYTES` and the staged-tree ownership transfer are backend-independent. |
| Owner module | `src/runtime_bundle.align` and `scripts/gpu_backend_recipe.py`. |
| Persisted / cache identity | `bundle_id` is the zeroed-field self-hash of canonical bytes, unchanged in construction. A CPU bundle gets its own `bundle_id`; existing Metal/CUDA bundle IDs are unaffected because none of their fields change. |
| Schema version | **Stays 1**, same argument as 3.1: the `backend`, `target.os`/`arch` and `gpu_architectures` value sets widen, no key is added, removed or reordered, and a pre-change reader fails closed on a CPU bundle. |
| Validation order | Unchanged: shape and constants, then the backend/target/toolkit branch, then build flags, then the artifact loop, then the plugin uniqueness check, then staging. |
| Prerequisites | None beyond a host that can build ggml. |
| Acceptance evidence | `./scripts/run-gpu-bundle-smoke` extended with a valid CPU manifest and four refusals (wrong plugin name, non-`none` toolkit, `gpu_architectures` mismatching `arch`, `os`/`arch` mismatch); `./scripts/run-gpu-backend-recipe-smoke`. |
| Metrics | N/A — a manifest contract has no runtime metric. |

### 3.6 `runtime_execution.topology_key` — backend value set

| Field | Contract |
| --- | --- |
| Surface | `pub fn runtime_execution.topology_key(borrow identity, borrow invocation) -> Result<string, Error>` (`src/runtime_execution.align:77`). |
| Inputs / defaults | `identity.backend` accepts `metal`, `cuda`, `cpu`. All other admissibility is unchanged. |
| Results / errors | Unchanged. |
| Ownership / allocation | Unchanged. |
| Owner module | `src/runtime_execution.align`. |
| Persisted / cache identity | **This is the one identity that materially changes.** `TopologyRecord.backend` is a field of the canonical JSON whose SHA-256 is the graph-cache key, so a CPU session's keys are disjoint from Metal and CUDA keys by construction. `TopologyRecord.schema_version` stays 1: no key is added and no existing key's encoding changes, so every previously computed Metal/CUDA key is byte-identical after this change. The cache is owner-local and never persisted across processes, so no stored artifact is invalidated. |
| Schema version | Stays 1, per the previous cell. |
| Validation order | Unchanged: the backend clause is the first clause of the same `if`. |
| Prerequisites | 3.1. |
| Acceptance evidence | `make check`; `./scripts/run-gpu-session-reuse-smoke` CPU arm (lookup hit, miss, invalidation). |
| Metrics | Graph reuse hit rate is observed indirectly by the C0-protocol pair in 3.10; no separate counter is added. |

### 3.7 Attention policy admissibility on the CPU device

| Field | Contract |
| --- | --- |
| Surface | `runtime_attention.select` (`src/runtime_attention.align:7`), `runtime_attention.name` (`:44`), and the two policy-2 gates at `src/runtime_generation.align:270` and `:398`. |
| Inputs / defaults | `runtime_attention.select` is already backend-agnostic: it probes `ggml_backend_dev_supports_op` for the F16 casts and `flash_attn_ext`, and selects policy 1 when every prefill and decode width is supported, else policy 0. The ggml CPU backend supports `flash_attn_ext`, `cpy` to F16 and `mul_mat_id`, so a CPU session is expected to reach policy 1 with no change. The two policy-2 gates change from `session_graph && (options.backend == "metal" \|\| options.backend == "cuda") && runtime_attention.fused(owner)` to `session_graph && runtime_attention.fused(owner)`. The `options` parameter of those two functions stays, because `prepare_memory` still consumes it. |
| Results / errors | Admissible CPU policies are therefore `decomposed` (0), `flash_f32` (1) and `flash_f16_cached` (2), the same set as Metal. `align_gpu_attention_select` already refuses policy 2 unless the current policy is 1, so an unsupported CPU device degrades to 0 or 1 without a new error path. |
| Ownership / allocation | Unchanged. Policy 2 changes the KV plane element type to F16, which reduces `kv_bytes` and therefore the resident-tensor budget; it does not change who owns it. |
| Owner module | `src/runtime_attention.align` (probe/name), `src/runtime_generation.align` (the two gates). |
| Persisted / cache identity | `attention_policy` is already a field of `TopologyRecord`, so a policy change already produces a different graph key. |
| Schema version | N/A — no schema field. |
| Validation order | Unchanged: `runtime_attention.select` runs first in both `create_*` paths, then the policy-2 upgrade, then `kv_bytes`, then `plan_begin`/`prepare_memory`. `align_gpu_attention_select` refuses after `memory_planned`, which keeps the ordering enforced natively. |
| Prerequisites | 3.1, 3.4. Indexed SET_ROWS prefill stays CUDA-gated at `scripts/ggml_shim.c:2632-2636`; CPU uses the in-place SET conversion path that Metal uses, so `runtime_kv.prefill_chunk`'s branch needs no change. |
| Acceptance evidence | `./scripts/run-gpu-attention-policy-smoke` on the CPU device (numeric tolerance for the CPU arm is the Metal value, `1e-4`, because `scripts/gpu_attention_policy_smoke.c:35` already keys the looser tolerance off the `CUDA` registry name only); `./scripts/run-gpu-session-independent` CPU arm. |
| Metrics | Request wall time in the C0-protocol pair (3.10). No separate attention metric. |

Numeric effect versus the reference arm, stated so no one re-derives it: the CPU session's attention
is **not** bitwise equal to the legacy CPU path. Policy 1 changes the reduction order relative to the
decomposed `softmax(QK^T)V` chain, and policy 2 additionally stores K/V in F16. This is expected and
is exactly why section 2 keeps the two paths separate. The candidate's correctness evidence is exact
output-text and token-count equality against the upstream CPU oracle in `run-gpu-session-independent`,
which is the same bar Metal and CUDA cleared.

Fallback, pre-agreed so a failure does not become a redesign: if the CPU arm of
`run-gpu-session-independent` fails output equality **only** with policy 2 selected, narrow the
policy-2 gate to `session_graph && runtime_attention.fused(owner) && options.backend != "cpu"`,
record "F16 KV attention policy 2 on CPU" as a new `leftover` row in `docs/backend-parity.md`
section 2 with this document as its evidence, and ship C3 at policy 1. Do not relax the oracle.

### 3.8 Session worker admission of a CPU options document

| Field | Contract |
| --- | --- |
| Surface | `provider_runtime.run_session` / `run_session_observed` (`src/provider_runtime.align:472,478`), reached by `main --runtime-session MODEL PACK GEOMETRY OPTIONS CACHE_BUDGET_BYTES`. |
| Inputs / defaults | Unchanged. The worker already requires a non-empty `runtime_options_path` and delegates every backend decision to `runtime_options.load` and `runtime_device.open`, so it needs **no edit** for CPU. |
| Results / errors | Unchanged, including the ready/ok/invalid/failed frames. |
| Ownership / allocation | Unchanged. |
| Owner module | `src/provider_runtime.align`. |
| Persisted / cache identity | N/A — requests and sessions are not persisted. |
| Schema version | Wire schema stays 1 here. The ready frame's schema 2 is a separate capability, P8, designed in `docs/specs/gpu-runtime.md` §3.12 "Ready frame schema 2: attention policy"; C3 does not depend on it and must not be blocked by it. |
| Validation order | Unchanged (§3.12 "Validation order"). |
| Prerequisites | 3.1–3.7. |
| Acceptance evidence | `./scripts/run-gpu-session-independent` CPU arm; `./scripts/run-gpu-session-host-capacity` CPU arm. |
| Metrics | Session construction wall time, reported by the same owners. |

### 3.9 Deterministic-stub CPU arm

| Field | Contract |
| --- | --- |
| Surface | `src/runtime_session_reuse_smoke.align:15` (hardcodes `backend: "metal"`, `device: "stub-gpu"`), `scripts/ggml_shim_stub.c`, `scripts/run-gpu-session-reuse-smoke`. |
| Inputs / defaults | The smoke gains a second arm that constructs the same fixture options with `backend: "cpu"` and runs the identical load/prefill/decode/selection sequence. **The fixture budgets cannot be copied unchanged.** `src/runtime_session_reuse_smoke.align:17` sets `host_budget_bytes` and `device_budget_bytes` both to 67,108,864, so under 3.2(a) the CPU arm's `available = host_budget_bytes - device_budget_bytes` is 0 and the arm would be refused at `prepare_memory` before it ever reached `plan_begin`, making the identical-token assertion below unsatisfiable. The CPU arm therefore uses `host_budget_bytes: 134217728` with `device_budget_bytes: 67108864`, leaving 64 MiB of headroom for `2 * MAX_STAGING_BYTES` (33,554,432), the observation bytes, the 4,194,304-byte legacy cache the fixture already passes, and the 64-byte remainder. The Metal arm's budgets stay exactly as they are, so the two arms differ only in the backend string and the host ceiling. `ggml_shim_stub.c`'s `align_gpu_device_open` must accept `"cpu"` wherever it accepts `"metal"`; it is a deterministic engine with no real registry, so the change is the backend-string acceptance and nothing else. |
| Results / errors | Both arms must produce identical token sequences, because the stub engine is backend-independent. That equality is the assertion: it proves the CPU backend string reaches graph construction, topology keying and selection without altering any deterministic result. |
| Ownership / allocation | Unchanged. |
| Owner module | `src/runtime_session_reuse_smoke.align`, `scripts/ggml_shim_stub.c`. |
| Persisted / cache identity | N/A — a fixture. |
| Schema version | N/A. |
| Validation order | N/A — the smoke drives the production order. |
| Prerequisites | 3.1, 3.6. |
| Acceptance evidence | `./scripts/run-gpu-session-reuse-smoke` (no hardware, no model download). |
| Metrics | N/A — a correctness stub. |

### 3.10 C0-protocol paired measurement owner

| Field | Contract |
| --- | --- |
| Surface | `scripts/run-olmoe-platform-sampled-runtime-baseline`. It currently accepts only `--platform-profile` and builds the runtime arm's command through `sampled.candidate_command(arm, helper, endpoint, model, pack, geometry, seed, prompt, record_path)`, which has no options path. |
| Inputs / defaults | Add `--runtime-options PATH` (optional, default absent). When present, the runtime arm's candidate command appends the options path and the model's cache budget, and the record's `arm` label becomes `runtime_session` instead of `runtime`; when absent, behavior is byte-identical to today. `--print-identity` and `--self-test` keep their current contracts and must both continue to pass unchanged when the flag is absent. |
| Results / errors | The receipt's `C0_OLMOE_PLATFORM_SAMPLED_RUNTIME_BASELINE` record gains `runtime_options_sha256` (SHA-256 of the options document, or `null` when the flag is absent) and records the runtime arm label. Because this changes the persisted receipt, the record's `schema_version` is **bumped by one** and the reader admits both versions, refusing an unknown one. |
| Ownership / allocation | Unchanged; the owner still owns the temporary root and the clean environment. |
| Owner module | `scripts/run-olmoe-platform-sampled-runtime-baseline`. |
| Persisted / cache identity | `eval/benchmarks/cpu-baseline-linux-2026-09-20.json` stays valid at its existing schema version; the C3 pair writes a new portable receipt `eval/benchmarks/cpu-session-linux-<date>.json`. |
| Schema version | Bumped as stated. This is the only schema bump in C3. |
| Validation order | Options-path resolution and digest happen during identity capture, before the timed run, so a bad path cannot consume measurement time. |
| Prerequisites | 3.1–3.8, and a CPU bundle on the measuring host. |
| Acceptance evidence | `./scripts/run-olmoe-platform-sampled-runtime-baseline --self-test`; `--print-identity --platform-profile linux-x86_64-v1` returning `MATCH`; then the paired run. |
| Metrics | Primary: time to a passing patch, and the per-candidate cost, against `docs/specs/cpu-baseline-linux.md` §7 (runtime median 17.543 s, `llama-server` median 11.291 s, about 8.3x per candidate). Secondary: median per-candidate command wall (C0: 17.30 s runtime, 2.08 s local). |

Two confounds that must be recorded in the result section, not discovered later:

1. **ISA flags.** The C0 legacy arm links the ggml the ordinary build uses; the CPU session arm links
   the bundle's `libggml-cpu.so` built with `-DGGML_NATIVE=OFF -DGGML_CPU_ALL_VARIANTS=OFF`. If those
   differ in vector ISA, the pair conflates session mechanisms with compiler flags. The receipt must
   record both ggml build-flag sets; if they differ, the result is reported as an
   end-to-end-configuration comparison and says so in one sentence.
2. **Thread count.** C0 recorded `effective_ggml_threads` 4 on both arms. C3's pair is comparable to
   C0 only at the same thread count. If C1 lands first, pair against C1's receipt instead and say so.

### 3.11 Python admission of a CPU qualification profile

Without this row, step 9 of section 7 cannot run: every session owner calls
`gpu_qualification_input.admit(profile)`, and four validators hard-code `{metal, cuda}`.

| Field | Contract |
| --- | --- |
| Surface | `scripts/gpu_qualification_records.py:171` (runtime option backend), `:189` (bundle backend), `:215-217` (bundle target `os`/`arch` pair), `:233` (bundle toolkit `is_none`), `:299` (calibration backend); `scripts/gpu_qualification_host_observation.py:76` (backend enum and platform rule); `scripts/gpu_independent_corpus.py:41` (corpus backend); `docs/specs/gpu-runtime.md` §3.5 platform sentence; `scripts/build-gpu-independent-reference` and `eval/gpu/session-reference.cpp` plugin selection. |
| Inputs / defaults | Each of the five enums becomes `{metal, cuda, cpu}`, and two backend-keyed branches in `gpu_qualification_records.py` gain a `cpu` arm. `:215-217` tests the target pair only for `metal` and `cuda`, so a `cpu` bundle record passes it unexamined; the `cpu` arm admits exactly `(macos, aarch64)` and `(linux, x86_64)`, the same two pairs `runtime_bundle.verify`'s `cpu` arm admits (3.5). `:233` tests the toolkit identity only for `metal` and `cuda`, so a `cpu` bundle carrying a CUDA toolkit identity is admitted today; the `cpu` arm requires the `none` identity, like `metal`. The §3.5 platform sentence gains "`cpu` requires `macos\|linux\|wsl2`", i.e. every platform the other two allow. `observe_host` needs no new probe: its existing macOS and Linux branches are selected by `actual_platform`, not by backend. The independent reference driver must be built and linked against the CPU bundle's `libggml-cpu.so` exactly as it is built against `libggml-metal.so`/`libggml-cuda.so` today; the "admitted GPU plugin" wording in §3.12 becomes "the admitted backend plugin". |
| Results / errors | Unchanged `RecipeError` refusals; a fourth backend is still refused. |
| Ownership / allocation | N/A — validators own no resource. |
| Owner module | `scripts/gpu_qualification_records.py`, `scripts/gpu_qualification_host_observation.py`, `scripts/gpu_independent_corpus.py`, `scripts/build-gpu-independent-reference`. |
| Persisted / cache identity | A CPU profile is a new checked-in-or-local artifact with its own digests; no existing profile changes. |
| Schema version | Unchanged everywhere, by the §3.1 widening argument. `gpu_independent_corpus.py`'s `schema_version` bound of 1–2 is untouched. |
| Validation order | Unchanged in each validator; only the enum membership set widens. |
| Prerequisites | 3.5 (a real CPU bundle to bind). |
| Acceptance evidence | `./scripts/run-gpu-profile-assembly-smoke`, `./scripts/run-gpu-profile-coverage-smoke`, `./scripts/run-gpu-host-observation-smoke`, `./scripts/run-gpu-independent-corpus-smoke`, `./scripts/run-gpu-independent-reference-smoke`, and `python3 scripts/check-python-boundary`. |
| Metrics | N/A — admission validators have no runtime metric. |

**Named hazard, so it is not discovered during step 9.** `admit()` requires each profile model row to
name a calibration document, and §3.5 requires that calibration to bind the same backend and bundle.
A CPU profile therefore needs two `GPU_NUMERIC_CALIBRATION` documents with `backend: "cpu"` and the
CPU `bundle_id`. Produce them with the existing `runtime_calibration_seed` driver, which is already
the same-build CPU expectation source. Those documents are **not** a numeric claim about the CPU
session: their expectations come from the legacy per-layer path, and the CPU session does not
reproduce them bitwise (§3.7). The session owners (`run-gpu-session-independent`,
`run-gpu-session-host-capacity`, `run-gpu-session-coding`) admit them structurally and never execute
them. Consequently **`run-gpu-independent-acceptance` must not be run against the CPU profile**;
doing so would execute those cases and fail. Section 7 step 9 lists the three permitted owners
explicitly, and section 8 records reconciling this as part of the C5 deferral.

## 4. What the `gpu_*` owner API calls mean on the CPU device

No `gpu_*` entry point is renamed. The names are historical; this table is the authority on what
each one does when `state->host_resident` is set, so no one re-derives it from ggml.

| Call | On Metal/CUDA | On the ggml CPU device |
| --- | --- | --- |
| `gpu_device_open` | `ggml_backend_load` of `libggml-metal.so`/`libggml-cuda.so`, registry name `MTL`/`CUDA`, exactly one device matching `options.device` | `ggml_backend_load` of `libggml-cpu.so`, registry name `CPU`, the single device named `CPU`. Bundle staging, bundle-ID pinning, the busy latch and registry poisoning are unchanged. |
| `gpu_memory_admit` | device budget bounds VRAM, host budget bounds host allocations | both budgets bound host RAM; the added combined clause in 3.2 makes `host_budget_bytes` the whole-process ceiling |
| `gpu_memory_allocate` | `ggml_backend_buft_alloc_buffer` on the device buffer type | the same call on the CPU buffer type, which is `malloc`-backed host memory. `ggml_backend_buffer_is_host` is true for the weights and KV buffers. The code path is identical. |
| weight upload (`runtime_qwen_load`/`runtime_olmoe_load` capped reads) | `pread` into the staging buffer, then `ggml_backend_tensor_set` DMA to device | `pread` into the staging buffer, then `ggml_backend_tensor_set`, which is a host `memcpy`. The staging buffer is **not** a no-op: it is the loader's bounded read window and it stays, so there is exactly one loader code path. The zero-copy alternative (read directly into the tensor, or `buffer_from_host_ptr` over an `mmap`ed pack) is a real CPU-only optimization and is deferred with its reason in section 8. |
| `align_ggml_buffer_from_host` | used only by the legacy path (`model_forward`, `layer_forward`, `ggml_spike`) | unchanged and unreached by the session; C3 does not touch it |
| KV plane allocation | F16 or F32 rows inside the device KV buffer | the same rows inside a host-resident KV buffer. `initialize_kv` and `runtime_kv` are unchanged. |
| `gpu_device_synchronize` | waits for the backend queue | the ggml CPU backend computes synchronously, so this returns after the last graph; it stays a required call so the state machine is one path |
| `gpu_attention_probe` / `_select` | `ggml_backend_dev_supports_op` on the GPU device | the same call on the CPU device; see 3.7 |
| `gpu_observation_state(HOST_PEAK)` | metadata + staging | metadata + staging + weights + KV + inputs + workspace, per 3.3 |
| `align_ggml_device_props(MEMORY_FREE/TOTAL)` | VRAM free/total | whatever the pinned ggml CPU backend reports for system memory. C3 does not depend on a specific value: nothing in the admission path consults it, and the only consumer, `gpu_qualification_native.py`'s `_observation`, requires only `total >= 1` and `free <= total`, and is not extended to the CPU session (section 2). Step 3 of section 7 records the observed pair in the step log rather than asserting an upstream implementation. |

## 5. Closure matrix

Each cell names the implementation and the exact regression test. Test names are implementation
targets, not passing evidence.

| Module | Construction | Success | Failure | Malformed input | Early exit | Cleanup |
| --- | --- | --- | --- | --- | --- | --- |
| `runtime_options` | `decode` admits `backend: "cpu"` — `make gpu-config-smoke` case `cpu-accepted` | same case asserts every other field round-trips | N/A — `decode` has one error; covered by the malformed column | `make gpu-config-smoke` cases `vulkan-refused`, `cpu-with-empty-device`, `cpu-with-zero-budget` | N/A — no partial state; a single `if` returns before construction | N/A — `read_bounded` ownership is unchanged and already covered |
| `runtime_generation.prepare_memory` (3.2 change (a)) | the CPU branch reserves `device_budget_bytes` before sizing staging — `run-gpu-session-reuse-smoke` CPU arm reaches `plan_begin` and allocates | staging is sized from `available - host_used` and `device_total + host_total <= host_budget_bytes` holds — `run-gpu-session-reuse-smoke` assertion `cpu-budget-closes` | `checked_sub(host_budget_bytes, device_budget_bytes)` underflow returns `Err(Error.Invalid)` with `MEMORY_BUDGET` at stage `plan` — `run-gpu-session-reuse-smoke` case `cpu-device-budget-exceeds-host-budget` | a CPU fixture whose `available - host_used < 66` is refused — same smoke, case `cpu-host-remainder-too-small` | refusal happens before `reserve_application` and before `runtime_memory.admit`, so no native state is mutated — the same two cases assert `gpu_memory_bytes` returns −1 | N/A — `prepare_memory` allocates nothing itself; the device owner's release path is unchanged |
| `runtime_bundle` | `verify` accepts a CPU manifest — `run-gpu-bundle-smoke` case `cpu-valid` | staged plugin path and digest match — same case | `run-gpu-bundle-smoke` case `cpu-plugin-missing` (no `libggml-cpu.so` artifact) | `run-gpu-bundle-smoke` cases `cpu-wrong-plugin-name`, `cpu-toolkit-not-none`, `cpu-arch-mismatch` (`gpu_architectures` vs `arch`), `cpu-os-arch-mismatch` | `run-gpu-bundle-smoke` case `cpu-refused-before-staging` asserts no staged tree exists after refusal | existing `run-gpu-backend-staging-smoke`, extended with a CPU bundle, asserts the staged tree is removed or transferred exactly once |
| `ggml_shim.c` (registry + admission) | `align_gpu_device_open` with `"cpu"` returns a state whose `host_resident` is 1 — `run-gpu-device-smoke` case `cpu-open` | `align_gpu_memory_admit` accepts budgets satisfying 3.2 — `run-gpu-device-smoke` case `cpu-admit` | `run-gpu-device-smoke` case `cpu-admit-combined-over-budget` expects `MEMORY_BUDGET` | `run-gpu-device-smoke` case `cpu-backend-typo` (`"CPU"` uppercase in the options) expects `CONFIG` | the combined clause refuses before `memory_planned` is set — the same case asserts `align_gpu_memory_bytes` still returns −1 | `align_gpu_memory_release` is unchanged and already owns CPU-allocated buffers; `run-gpu-device-smoke` case `cpu-release` asserts a clean close |
| `runtime_execution` | `topology_key` accepts `backend: "cpu"` — `make check` plus `run-gpu-session-reuse-smoke` CPU arm | CPU keys differ from Metal keys for otherwise identical identities — `run-gpu-session-reuse-smoke` assertion `cpu-key-disjoint` | N/A — the only failure is `Error.Invalid`, covered by malformed | `make check` unit case: `backend: "vulkan"` still refused | N/A — pure function, no partial state | N/A — pure function, no resource |
| `runtime_attention` / `runtime_generation` | CPU session reaches policy 1 or 2 — `run-gpu-attention-policy-smoke` on the CPU device | flash and decomposed agree within `1e-4` — same smoke | a CPU device that refuses `flash_attn_ext` falls back to policy 0 — `run-gpu-attention-policy-smoke` case `cpu-unsupported-falls-back`, forced through the probe's existing refusal path | `align_gpu_attention_select(owner, 2)` when the policy is not 1 returns `CONFIG` — existing shim case, re-run on CPU | policy selection happens before `plan_begin`; `run-gpu-device-smoke` case `cpu-select-after-plan` expects `CONFIG` | N/A — policy is a scalar in device state, released with the device |
| `provider_runtime` (worker) | ready frame emitted on a CPU options document — `run-gpu-session-independent` CPU arm | 7 Qwen + 9 OLMoE requests match the CPU oracle exactly — same owner | a compute failure closes the session and exits nonzero — existing `gpu-session-second-after-failure`, re-run on CPU | an oversize request is refused and the session stays ready — `run-gpu-session-host-capacity` CPU arm already does this | EOF between frames drains and releases — `run-gpu-session-host-capacity` CPU arm asserts exit 0 | `native + reserved <= host_budget_bytes` — `run-gpu-session-host-capacity` CPU arm |
| `ggml_shim_stub.c` / `runtime_session_reuse_smoke` | stub accepts `"cpu"` — `run-gpu-session-reuse-smoke` | CPU and Metal stub arms produce identical tokens — same smoke | N/A — the stub has no failure injection for backend strings; the real shim owns that in `run-gpu-device-smoke` | stub refuses `"vulkan"` — `run-gpu-session-reuse-smoke` assertion `stub-refuses-unknown-backend` | N/A — fixture | existing stub teardown assertions, run on both arms |
| Python qualification admission (3.11) | a CPU profile is admitted — `run-gpu-profile-assembly-smoke` case `cpu-profile` | coverage and corpus accept `cpu` — `run-gpu-profile-coverage-smoke`, `run-gpu-independent-corpus-smoke` case `cpu-backend` | a CPU profile whose calibration names `metal` is refused — `run-gpu-profile-assembly-smoke` case `cpu-calibration-backend-mismatch` | a fourth backend is still refused in all five validators — `run-gpu-profile-assembly-smoke` case `vulkan-refused`, `run-gpu-independent-corpus-smoke` case `unknown-backend`, `run-gpu-host-observation-smoke` case `unknown-backend`; and the two new backend-keyed bundle arms refuse a `cpu` bundle carrying a non-`none` toolkit or a target outside the two host pairs — `run-gpu-profile-assembly-smoke` cases `cpu-bundle-toolkit-not-none`, `cpu-bundle-target-mismatch` | refusal happens before any build or device side effect — existing `admit()` ordering, unchanged | N/A — validators own no resource |
| `gpu_backend_recipe.py` | CPU flags/target/artifacts produce a manifest that `runtime_bundle.verify` accepts — `run-gpu-backend-recipe-smoke` case `cpu-manifest` | `-DGGML_CPU=ON` appears after `-DGGML_CPU=OFF` in the argv — same case | a host whose `os`/`arch` is neither supported pair is refused — `run-gpu-backend-recipe-smoke` case `cpu-unsupported-host` | `gpu_architectures` not matching `arch` is refused by the recipe before the build — same smoke | N/A — the recipe builds or refuses; no partial manifest is written | the recipe's existing private-output-root cleanup is unchanged |
| G1 qualification (unchanged, guarded) | N/A — nothing is constructed | N/A | N/A | N/A | N/A | `gpu-cpu-session-not-reference`: assert `scripts/gpu_qualification_native.py` has no `cpu_resident` execution and the profile `execution` enum is exactly `{cpu, gpu_resident}` |
| `run-olmoe-platform-sampled-runtime-baseline` | `--runtime-options` parsed and digested — `--self-test` case `runtime-options-identity` | a paired run records the session arm — the C3 result section | a missing options path fails before the timed run — `--self-test` case `runtime-options-missing` | a non-JSON options document fails at identity capture — same self-test | absent flag reproduces today's behavior byte-for-byte — `--self-test` case `no-options-unchanged` | the owned temporary root is removed on both paths — existing self-test assertions |

## 6. Author ledger-to-prose consistency pass

Performed. Checked and consistent: the backend is admitted as `metal|cuda|cpu` in exactly eleven
places — four in shipping code (`runtime_options.decode`, `runtime_execution.topology_key`,
`runtime_bundle.verify`, `align_gpu_registry_name`) and seven in Python admission, namely the five
enums (`gpu_qualification_records.py:171,189,299`, `gpu_qualification_host_observation.py:76`,
`gpu_independent_corpus.py:41`) plus the two backend-keyed bundle branches
(`gpu_qualification_records.py:215-217,233`) — and this document names all eleven; no schema version
change is owned by C3 except the C0 receipt in 3.10 (R9's runtime-options 1 -> 2 bump has its own
owner; see the ordering sentence in 3.1), and each unchanged version carries the widening argument; `host_budget_bytes` is
the whole-process ceiling on CPU in 3.2, 3.3, 4 and the closure matrix, with the same inequality
each time, and 3.2 states both the Align arithmetic that makes it satisfiable and the native gate
that makes it unbypassable; the policy-2 gate is described identically in 3.7 and the matrix;
section 2's decision is re-stated as a guard test in the matrix so it cannot silently erode; every
owner command named in section 3 reappears in section 7 with the same spelling, and each is either
an existing script in `scripts/` or an existing `Makefile` target.

One deliberate asymmetry: `device_budget_bytes` is retained on CPU rather than being made optional.
Removing it would make the CPU options document a different shape from the Metal/CUDA one, which
would be a real schema change and would fork `prepare_memory`. Keeping it costs one documented
sentence and zero code branches.

## 7. Ordered implementation steps

Each step is a coherent batch with its owner command. Run `make fmt` before committing Align source.

1. **CPU bundle recipe.** `gpu_backend_recipe.py`: `BACKEND_FLAGS["cpu"]`, `TARGET["cpu"]` (two
   host pairs), the CPU artifact table, and the `generic-x86_64`/`generic-aarch64`
   `gpu_architectures` rule. Owner: `./scripts/run-gpu-backend-recipe-smoke`.
2. **Bundle admission.** `src/runtime_bundle.align`: `plugin_name` three-way map, `verify`'s
   `expected_backend` clause, the three-way target/toolkit branch. `docs/specs/gpu-runtime.md` §3.6
   backend/target prose. Owner: `./scripts/run-gpu-bundle-smoke`, then `make check`.
3. **Build a real CPU bundle and record it.** Run the recipe on the measuring host. Record, in this
   document's result section: the built `bundle_id`, `ggml_backend_reg_name` of the loaded plugin,
   whether the session executable registers any compiled-in `CPU` registry (expected: no), and the
   `MEMORY_FREE`/`MEMORY_TOTAL` pair the CPU device reports. Owner:
   `./scripts/run-gpu-backend-staging-smoke` plus the recorded observations.
4. **Shim registry and host-resident admission.** `scripts/ggml_shim.c`: `align_gpu_registry_name`
   `cpu -> "CPU"`; `state->host_resident`; the combined clause in `align_gpu_memory_admit`; the
   host-peak change in `align_gpu_observe_memory`. `scripts/ggml_shim_stub.c`: accept `"cpu"`.
   Owner: `./scripts/run-gpu-device-smoke`.
5. **Align backend allowlists.** `src/runtime_options.align:139`,
   `src/runtime_execution.align:81`. `docs/specs/gpu-runtime.md` §3.1 table row and the replaced
   sentence. Owner: `make check`, then `make gpu-config-smoke`.
6. **Host-budget arithmetic.** `runtime_generation.prepare_memory` change 3.2(a). Owner:
   `make check`, then `./scripts/run-gpu-session-reuse-smoke`.
7. **Policy-2 gate.** `src/runtime_generation.align:270,398`. Owner: `make check`, then
   `./scripts/run-gpu-session-reuse-smoke`.
8. **Stub CPU arm.** `src/runtime_session_reuse_smoke.align` second arm, the identical-token
   assertion, and the four 3.2(a) budget cases. Owner: `./scripts/run-gpu-session-reuse-smoke`.
9. **Python qualification admission.** The five enums, the §3.5 platform sentence and the reference
   driver's plugin selection, per 3.11. Owner: `./scripts/run-gpu-profile-assembly-smoke`,
   `./scripts/run-gpu-profile-coverage-smoke`, `./scripts/run-gpu-host-observation-smoke`,
   `./scripts/run-gpu-independent-corpus-smoke`, `./scripts/run-gpu-independent-reference-smoke`,
   `python3 scripts/check-python-boundary`.
10. **Guard test.** `scripts/run-gpu-cpu-session-not-reference`, a Python guard. It is Python, not
    an Align `src/*_smoke.align` owner, because the asserted property is a property of the Python
    qualification sources themselves: that `scripts/gpu_qualification_native.py` contains no
    `cpu_resident` execution and that the profile `execution` enum is exactly `{cpu, gpu_resident}`
    (`scripts/gpu_qualification_records.py:397`). No Align owner can hold that. Classify it in
    `docs/python-boundary-audit.md` section 4 as retained qualification/test infrastructure. Owner:
    `./scripts/run-gpu-cpu-session-not-reference`, then `python3 scripts/check-python-boundary`.
11. **Real CPU hardware qualification.** Assemble a CPU qualification profile (one `cpu` runtime
    option, both models, two `backend: "cpu"` calibration documents per the 3.11 hazard), build the
    session candidate and the CPU session reference, then run exactly these three owners, in order:
    `./scripts/run-gpu-attention-policy-smoke` on the CPU device;
    `./scripts/run-gpu-session-independent --profile CPU_PROFILE ...` (7 Qwen, 9 OLMoE);
    `./scripts/run-gpu-session-host-capacity --profile CPU_PROFILE ...`. Do not run
    `run-gpu-independent-acceptance` against this profile (3.11 hazard). Apply the 3.7 fallback here
    if and only if policy 2 is the sole cause of an output mismatch.
12. **C0 protocol owner.** `--runtime-options` flag, the arm label, the receipt field and the
    receipt schema bump. Owner: `./scripts/run-olmoe-platform-sampled-runtime-baseline --self-test`,
    then `--print-identity --platform-profile linux-x86_64-v1` returning `MATCH`.
13. **Paired measurement.** Run the C0 protocol with `--runtime-options` against the legacy arm,
    same host profile and same thread count. Write the portable receipt to
    `eval/benchmarks/`, and write a Result section into this document with both ggml build-flag sets
    and the two confounds from 3.10.
14. **Register and handoff.** Update `docs/backend-parity.md`: row C3, the "Execution paths" CPU
    cell, and every section-2 row whose CPU cell is `leftover (C3)`. Add the C5 deferral row.
    `HANDOFF.md` is updated by the implementing branch, not here.
15. **Publication.** `python3 scripts/pre-pr --owner-test cpu-session -- ./scripts/run-gpu-session-independent ...`
    at the exact unchanged `HEAD`, then one comprehensive review.

Steps 1, 2 and 4–10 need no GPU and no model download and are a valid local implementation
checkpoint. Steps 3 and 11–13 require the measuring host. The hardware-free steps alone are not
publishable: they are not consumer-complete until step 11 proves a CPU session actually runs.

## 8. Explicit deferrals

| Deferred | Reason | Where it goes |
| --- | --- | --- |
| Retiring the legacy per-layer CPU path | It is the G1 numeric reference arm; section 2 reasons 1–3 | new item C5 |
| A CPU-session arm in the G1 19-case acceptance | Would require a qualification-profile schema bump, a calibration re-freeze, and would collapse reference and candidate onto one graph builder | new item C5 |
| Reconciling the CPU profile's calibration documents with the CPU session | The 3.11 hazard: they carry legacy-path expectations, so `run-gpu-independent-acceptance` must not run against the CPU profile. Fixing this is the same re-freeze C5 already owns | new item C5 |
| Zero-copy weight residency on CPU (read directly into the host-resident tensor, or `buffer_from_host_ptr` over an `mmap`ed pack) | A genuine CPU-only win, but it forks the loader and overlaps `mmap`/demand paging, which `docs/backend-parity.md` already assigns to C4's G2/R10 constrained-memory lane | C4 / G2-R10 |
| ggml CPU thread count | C1 owns it; C3's pair must be run at C0's thread count to stay comparable | C1 |
| Indexed SET_ROWS prefill on CPU | The CUDA gate at `scripts/ggml_shim.c:2632-2636` is a measured CUDA-specific choice; CPU uses the in-place SET path Metal uses, and whether SET_ROWS is faster on CPU is unmeasured | a new `unmeasured` row alongside P4 |
| Ready-frame attention-policy reporting | P8, designed in `docs/specs/gpu-runtime.md` §3.12; independent of C3 in both directions | P8 |

## 9. Align gap check

Performed against the pinned toolchain in `.align-revision`. **No genuine Align language, compiler,
runtime or standard-library gap is required by this design, and no capability request is proposed.**

Every construct this plan needs is already used in the same modules: string equality in a boolean
chain (`runtime_options.decode`), a three-way `if`/`else if` returning a `str` constant
(`runtime_bundle.plugin_name`), an added `Result` clause, and an extra fixture arm in an existing
smoke. No new Align API is assumed, and nothing here consumes a `PROPOSED`, `ACCEPTED` or
`IMPLEMENTING` request. The one item that could have become a request — a CPU-device query for
system memory — is not needed, because section 4 establishes that no admission decision consults
`MEMORY_FREE`/`MEMORY_TOTAL`.

`docs/align-requests.md` is therefore unchanged by this design.

## 10. Result

Not yet run. Step 11 writes this section.
