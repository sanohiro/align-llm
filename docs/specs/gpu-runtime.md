# G1 GPU runtime: resident Metal and CUDA generation

Status: design only, 2026-09-06. No GPU capability is implemented by this change.

This is the authoritative public contract for roadmap item 80 (G1). It records delivery order and
non-negotiable principles for items 81–85, but those later consumers must extend the contract,
closure matrix and evidence schema at their own triggered design gates. In particular, schema 1
does not predeclare offload, overlap, performance-comparison or coding-retry formats.

## 1. Consumer outcome and scope

The existing `AlignRuntime` caller gains an explicit opt-in path that generates Qwen2.5-Coder-7B
Q4_K_M greedy text and OLMoE-1B-7B Q4_K_M greedy or seeded text with the complete weight set and KV
cache resident on one selected Metal or CUDA device. Tokenization, prompt templates, EOG behavior,
context limits, sampling order and provider result schema remain the existing CPU contract.

G1 includes the native build/loader, exact device selection, bounded ownership, provider/CLI
integration, model-free owner tests, real-device numerical qualification and a replayable
cross-host evidence package. A backend discovery API, FFI wrapper or stub-only build is not a
consumer result. G1 is correctness enablement and makes no speedup or capacity claim.

The current code establishes the starting point:

- `gpu_forward.align` has real Metal dense-prefill evidence, but its diagnostic readbacks and
  window wrapping do not implement end-to-end generation.
- `moe_decode_step.align` currently opens the CPU device through `align_ggml_device_open`.
- CPU generation already owns Qwen greedy and OLMoE greedy/seeded sampling, tokenizer and source
  checks, expert-cache behavior and provider integration. GPU execution reuses those semantics.
- At Align pin `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`, ggml 0.21.0 exposes devices,
  buffers, transfers, supported-op checks, synchronization and a multi-backend scheduler. Header
  availability is not evidence that an operation or failure path works on a target device.

## 2. Hardware and support identity

G1 targets Apple Silicon Metal and compatible NVIDIA CUDA on native Linux or WSL2 Linux. The first
available validation hosts are an Apple M1 / 16 GiB Mac and the user's RTX 4070 Ti PC. These device
names are qualification profiles, never product allowlists. Runtime selection queries the named
backend registry and exact device; it does not choose a generic first GPU.

Native Linux and WSL2 are separate evidence environments. WSL2 uses the Linux Align toolchain and
the Windows-provided NVIDIA driver; no native-Windows support is claimed. Follow NVIDIA's WSL
toolkit guidance and keep initial model/build inputs in the Linux filesystem.

Support status is keyed by
`(backend, device architecture/name, OS, driver, backend bundle, model, quantization, placement,
prefetch)`. Implementation, build, functional qualification and performance decision are separate
fields with values `planned|implemented`, `unverified|pass|fail`,
`unverified|pass|fail`, and `unmeasured|met|not_met`. G1 fixes placement/prefetch to
`resident/off` and performance to `unmeasured`. Compilation or another device's result cannot
promote an untested tuple.

## 3. Public-contract ledger

| Surface | Exact G1 contract |
| --- | --- |
| Configuration API | Add `ProviderConfig.runtime_options_path: str`. Empty preserves CPU behavior. Nonempty is a borrowed UTF-8 path, 1–4096 bytes with no NUL, consumed synchronously by `provider_runtime`. Network providers require empty. The caller retains the path through the call. |
| Generation CLI | Extend `main --provider align-runtime MODEL PACK GEOMETRY PROMPT RESULT [MAX_TOKENS] [CACHE_BUDGET_BYTES]` with the optional terminal pair `--runtime-options OPTIONS.json`. Strip it before existing positional parsing. Duplicate, misplaced or valueless options fail. The maximum-token default remains 64. |
| Options | Strict schema-1 JSON in §3.1, read once into owned bounded data. Missing/unknown/duplicate keys, invalid UTF-8, boolean-as-integer, fraction, overflow, invalid enum and trailing document fail before model/device work. |
| Models and sampling | Exact existing `qwen2` and `olmoe` model, pack, geometry, prompt, context and request checks. Qwen remains greedy. OLMoE retains greedy and temperature 0.3 with every signed-i64 seed. |
| Legacy cache budget | Preserve Qwen-zero / OLMoE-positive `runtime_cache_budget_bytes`. For G1 resident execution the positive OLMoE value remains an admitted host expert-cache ceiling but may allocate zero bytes. It must not exceed `host_budget_bytes`. |
| Result and errors | Existing owned `Result<string, Error>` and CLI schema 2 remain. GPU refusal maps to `Error.Invalid` without partial output. Qualification retains the internal category/stage. |
| Device and bundle | Resolve one exact registry and device from the verified immutable backend bundle. Ambiguous, unavailable, incompatible or mismatched identities fail. No ambient plugin search or fallback to another backend. |
| Ownership | `runtime_device` owns native state through a package-defined opaque Move resource. `runtime_execution` borrows it only inside one request. Explicit fallible synchronization/release precedes success; exactly-once Drop is the safety fallback. No raw handle or device view escapes. |
| Memory | Full model weights, KV and reusable compute workspace are device resident. `host_budget_bytes` and `device_budget_bytes` cover application-managed allocations using checked arithmetic. Metal aliases are charged once physically and reported separately. |
| State | One GPU generation at a time per process. A native atomic guard rejects overlap before device side effects. Invocation resources are not persisted. The first successfully initialized bundle pins its manifest digest; a later different bundle fails before loading. Partial initialization poisons later GPU admission. CPU calls neither initialize nor replace it. |
| Validation order | Provider/request syntax; bounded options; model/pack/geometry/prompt/context; bundle identity; exact registry/device; op/buffer capability; admission; allocation/upload; prefill/decode; output validation; synchronization/release; success publication. Failure prevents later stages. |
| Qualifier | `scripts/gpu-runtime-qualify --profile PROFILE.json --suite generation --output NEW_DIRECTORY`. Schema 1 accepts only `generation`. It builds reviewed source in isolation and publishes §3.8 evidence. An absent requested backend is FAIL, never passing N/A. |
| Cache identity | Request-local weights bind model/pack/geometry, member/plane, quant layout, bundle/device and request generation. KV additionally binds prompt, position, rope/mask/context and precision. No persisted device cache is introduced. |
| Acceptance | Model-free matrix owners plus real `generation` PASS on Metal and CUDA. Device-specific evidence may be pending while independent implementation proceeds, but Metal cannot close CUDA. |
| Metrics | Correctness, ownership and budget compliance only. Timings are observations. Schema 1 decision is always `unmeasured`; no post-run metric selection can create a performance claim. |

### 3.1 Runtime options schema 1

The document is at most 16,384 bytes and has exactly these required fields:

| Field | Type and value |
| --- | --- |
| `schema_version` | integer 1 |
| `backend` | `metal|cuda`; later backends require a schema extension |
| `device` | exact registry device name, 1–256 UTF-8 bytes, no NUL |
| `backend_bundle` | verified bundle-directory path, 1–4096 UTF-8 bytes, no NUL |
| `placement` | exactly `resident` |
| `host_budget_bytes` | integer `1..2^63-1` |
| `device_budget_bytes` | integer `1..2^63-1` |
| `prefetch` | exactly `off` |

An explicit CPU options document is invalid; the established empty path selects CPU.

### 3.2 Failure vocabulary

Categories are `CONFIG`, `SOURCE_IDENTITY`, `BACKEND_UNAVAILABLE`, `DEVICE_UNAVAILABLE`,
`BUNDLE_IDENTITY`, `UNSUPPORTED_CAPABILITY`, `MEMORY_BUDGET`, `ALLOCATION`, `TRANSFER`,
`COMPUTE`, `NONFINITE`, `DEVICE_LOST`, `BUSY`, and `CLEANUP`. Stages are `options`,
`model`, `device`, `plan`, `allocate`, `upload`, `prefill`, `decode`, `readback`,
`synchronize`, and `release`.

Preserve the first operation fault and report cleanup failure separately; cleanup failure forbids
success. Native aborts, OS OOM kills and driver hangs are process failures, not guaranteed returned
errors. The qualifier bounds and terminates its own process group. Request 35 continues to own
universal recoverable host-allocation failure.

### 3.3 Canonical record rules

Options, source manifest, profile, bundle, calibration and evidence use strict JSON: UTF-8 without
BOM, exactly one object, exact keys, no duplicates, signed-64 integers, and record-specific bounds.
Canonical output uses the declared key order, stored array order, shortest integers, no insignificant
whitespace, lowercase hex, JSON escaping for quote/backslash/control bytes, direct other Unicode,
and exactly one final LF. Replay decodes, validates, canonically re-encodes and compares bytes.

An identifier matches `[a-z0-9][a-z0-9._-]{0,63}`; a digest is 64 lowercase hex; a Git OID is 40
or 64 lowercase hex according to object format. Retained paths use `/`, are relative and contain
no empty, `.` or `..` component. Inputs are single-link regular files, canonicalized before use
and rechecked before publication. Symlinks, aliases and mutation fail.

Record limits are:

| Record | Canonical limit and arrays |
| --- | --- |
| `GPU_SOURCE_MANIFEST` | 16 MiB; 1–100,000 tracked rows |
| `GPU_RUNTIME_PROFILE` | 256 KiB; exactly 2 models, 1–16 options, 16–256 cases |
| `GPU_BACKEND_BUNDLE` | 256 KiB; 1–32 GPU architecture entries, 0–128 flags, 1–128 artifacts |
| `GPU_NUMERIC_CALIBRATION` | 1 MiB; 2–32 cases per model, at most 64 across a profile |
| `GPU_RUNTIME_EVIDENCE` | 8 MiB result; 0–256 cases and 0–4,096 retained files |
| retained data | 4 MiB per log, 512 MiB total directory |

`FileRef` is `path,sha256`; `Identity` is `name,version,sha256`; `ArtifactRef` is
`role,path,bytes,sha256`. `ProducedIdentity` is `state,name,version,sha256`.
`state="available"` requires 1–256 UTF-8 bytes for name, 1–4,096 for version and a digest.
`state="unavailable"` requires three empty strings, is valid only in FAIL evidence, and means its
production step did not complete.
Validation order is framing; version/kind; exact keys/types/bounds; tagged presence; references;
digests; semantic invariants; aggregate and directory closure.

### 3.4 Source manifest schema 1

`GPU_SOURCE_MANIFEST` key order is
`schema_version,artifact_kind,repository,object_format,commit,commit_object_sha256,tree,files`.
Constants are 1 and `GPU_SOURCE_MANIFEST`; repository is exactly
`https://github.com/sanohiro/align-llm.git`; object format is `sha1|sha256`.

File rows are `path,mode,bytes,git_oid,sha256`, sorted by raw UTF-8 path bytes. Modes are
`100644|100755|120000`; submodules and other modes fail. Distinct paths may share content. Evidence
stores each distinct blob once as regular `source/blobs/<sha256>`, including symlink target bytes
without following them, and retains the raw commit body as `source/commit`.

Replay recomputes blob Git objects, every nested tree and the commit OID, and requires exact
manifest/blob closure. Snapshot identity is SHA-256 of ASCII `GPU_SOURCE_SNAPSHOT`, NUL, canonical
manifest bytes, then each row's raw 32-byte SHA-256. This permits cross-host replay without trusting
local ancestry. The evaluated commit must still be reachable from the exact merging head at
publication.

### 3.5 Qualification profile schema 1

Top-level key order is
`schema_version,artifact_kind,profile_id,platform,source,bundle_manifest,models,runtime_options,cases,deadlines_ns`.
Constants are 1 and `GPU_RUNTIME_PROFILE`; platform is `macos|linux|wsl2`; source is
`commit,manifest_sha256`; bundle manifest is a `FileRef`.

Models contain exactly `qwen2` then `olmoe`. A row is
`model_id,model_path,model_sha256,pack_path,pack_sha256,geometry_path,geometry_sha256,calibration_path,calibration_sha256`.
Every path/digest binds a regular input. Its calibration binds the same model, backend and bundle.
Calibration case IDs are unique across both documents and total at most 64.

Runtime-option rows are
`option_id,schema_version,backend,device,backend_bundle,placement,host_budget_bytes,device_budget_bytes,prefetch`.
The last eight fields have §3.1 semantics; bundle path resolves to the declared manifest directory.
Every row names the bundle's backend and one exact device from that registry. Metal profiles require
`platform=macos`; CUDA requires `linux|wsl2`. The empty option sentinel below is the only exception
to the identifier grammar.

Case rows are
`case_id,calibration_case_id,role,execution,repeat_index,model_id,option_id,maximum_tokens`.
The calibration reference resolves within the named model and `role` equals its
`calibration|holdout` role. Execution is `cpu|gpu_resident`; CPU has empty `option_id`, GPU
resolves an option. Repeat index is 0 or 1 and maximum tokens equals the calibration case.

Cases are a complete derived expansion. For every calibration case, exactly four contiguous rows
appear in this order: `(cpu,0),(gpu_resident,0),(cpu,1),(gpu_resident,1)`. Their IDs are
`<calibration_case_id>.<execution>.<repeat_index>`. No subset or extra case is valid. Thus every
frozen calibration input and unseen holdout executes twice on both same-build CPU and GPU.
Calibration rows must pass but cannot modify tolerances; every holdout GPU row must pass.

`deadlines_ns` is `preparation,generation`: positive and respectively at most
3,600,000,000,000 and 900,000,000,000 ns. No extension is allowed after observing results.
The runner validates every byte and cross-reference before device or output-directory side effects.

### 3.6 Backend bundle schema 1

`GPU_BACKEND_BUNDLE` key order is
`schema_version,artifact_kind,bundle_id,backend,ggml,target,toolchain,build_flags,artifacts`.
Constants are 1 and `GPU_BACKEND_BUNDLE`; `bundle_id` is SHA-256 of canonical bytes with that
field replaced by 64 zeroes. Backend is `metal|cuda`. `ggml` is
`commit,source_manifest_sha256,version` and binds an immutable complete checkout.

`target` is `os,arch,gpu_architectures`; OS is `macos|linux`, arch is
`aarch64|x86_64`, and architectures are nonempty compiled targets. `toolchain` is
`c_compiler,cxx_compiler,sdk,toolkit`, each an `Identity`. An inapplicable component is
`name="none",version="none"` with SHA-256 of empty bytes.

Build flags are the exact ordered argv suffix after fixed tool arguments, never a shell string.
Artifacts are `role,path,bytes,sha256`, sorted by role/path with roles
`shared_library|backend_plugin|kernel_binary|shader_library|metadata`. The array covers every
loadable file; runtime loading is restricted to verified paths.

The first successful native initialization pins bundle ID and manifest digest. Same-bundle
sequential requests reuse it. Different bundles fail before load. Failure after any registry/plugin
side effect poisons GPU admission and keeps libraries loaded until exit.

### 3.7 Numeric calibration schema 1

`GPU_NUMERIC_CALIBRATION` key order is
`schema_version,artifact_kind,calibration_id,backend,bundle_id,model,precision,comparison,cases`.
Constants are 1 and `GPU_NUMERIC_CALIBRATION`; calibration ID is the zeroed-field self-hash.
`model` is `model_id,model_sha256,pack_sha256,geometry_sha256,quantization`, with initial
quantization `Q4_K_M`; precision is `f32`.

`comparison` is
`absolute_tolerance_f32_bits,relative_tolerance_f32_bits,near_tie_tolerance_f32_bits,nonfinite,reference,layer_scope,topk_rule`.
Tolerances are finite nonnegative binary32 bit patterns. The remaining constants are
`reject`, `cpu-same-build`, `all`, and `same-ordered-ids-or-declared-near-tie`. A routing
boundary is a near tie only when the kth and first excluded reference scores differ within the
frozen tie tolerance; outside that group IDs/order and weights follow the declared tolerances.

Cases are
`case_id,role,prompt_utf8,prompt_sha256,prompt_token_ids,teacher_forced_token_ids,sampler_mode,temperature_micros,seed,maximum_tokens,expected_token_ids`.
There is at least one `calibration` and one `holdout`. Prompts are at most 65,536 bytes and at
most 4,096 nonnegative i32 token IDs. Teacher-forced IDs are nonempty. Greedy uses zero
temperature/seed; seeded uses 300000 micros and any signed-i64 seed. Maximum tokens is 1–128.
Expected IDs are the same-build CPU result and may be empty only for immediate EOG.

Tolerances and expected outputs are frozen before holdout execution and cannot be enlarged after a
failure. Teacher forcing compares common layer/router/final-logit positions so an early generated
token difference cannot hide later numeric drift. Both repeated GPU executions must match the
sampler expectation; fixed RNG alone does not establish device repeatability.

### 3.8 Evidence schema 1 and directory

The qualifier creates a sibling staging directory and exclusively renames it to a new destination.
Malformed input or occupied destination creates no output. After validation, a functional failure,
build failure, crash, signal, timeout, missing result or cleanup failure publishes a bounded FAIL
bundle when the parent remains able to do so.

The directory contains only `result.json`, canonical profile/bundle/calibration/source manifests,
`source/commit`, `source/blobs/<sha256>`, `artifacts/<sha256>`, and
`logs/<three-digit-ordinal>.stdout|stderr`. Models/packs/geometry are identified but not copied.
Files are single-link regular files. Logs record original count/digest and retain their first 4 MiB;
truncation fails the case.

`GPU_RUNTIME_EVIDENCE` top-level key order is
`schema_version,artifact_kind,status,suite,profile_id,source,host,bundle,inputs,files,cases,aggregate,cleanup,failure,elapsed_ns`.
Constants are 1, `GPU_RUNTIME_EVIDENCE`, and `generation`; status is `PASS|FAIL`.

- `source` is
  `commit,source_manifest_sha256,source_snapshot_sha256,align_revision,compiler,runtime,runner,shim,cpu_reference`.
  The last five are `ProducedIdentity`. Each records availability only after that preparation/build
  step completed; failure before or during a step uses the unavailable tag. PASS requires all.
- `host` is
  `platform,os_version,kernel,arch,wsl,cpu,logical_cpus,host_total_bytes,host_free_bytes,backend,device_state,registry_device,device_description,driver,gpu_architecture,device_total_bytes,device_free_bytes`.
  Baseline host fields are always present. `device_state="available"` requires the four device
  strings nonempty and both byte observations positive. `device_state="unavailable"` requires four
  empty strings and two zeroes, is valid only in FAIL evidence, and truthfully represents discovery
  failure before a device identity exists.
- `bundle` is `manifest_sha256,bundle_id,loaded_artifact_sha256s`; loaded hashes are a unique
  manifest subset in actual load order.
- `inputs` is `profile_sha256,models,calibration_ids,case_order_sha256`; model rows contain
  `model_id,model_sha256,pack_sha256,geometry_sha256`.
- `files` rows are
  `role,path,bytes,sha256,original_bytes,original_sha256,truncated`, sorted by path and covering
  every retained file other than `result.json`. Roles are
  `profile|bundle_manifest|calibration|source_manifest|source_commit|source_blob|helper|shim|backend_artifact|stdout|stderr`.

Case rows are
`ordinal,case_id,calibration_case_id,role,execution,repeat_index,model_id,option_id,terminal,category,stage,exit_code,signal,command_sha256,output_sha256,token_ids,nonfinite_count,numeric,placement,transfers,memory,timing,stdout_path,stderr_path`.
Ordinals and identity fields equal the profile. Terminal is
`PASS|FAIL|TIMEOUT|CRASH|SIGNAL|MISSING`; exit code/signal are integer or null. Missing output uses
an empty digest. Numeric is
`compared,max_absolute_f64_bits,max_relative_f64_bits,near_tie_count,mismatch_count`; false requires
zero bit patterns/counts and true permits an exact zero result. CPU rows require `compared=false`;
GPU rows compare against the adjacent same-repeat CPU row and require true.

`placement` is
`gpu_operations,cpu_operations,gpu_layers,cpu_layers,gpu_experts,cpu_experts,weights_device_bytes,kv_device_bytes`;
all are nonnegative and a passing GPU row requires positive GPU operations, weight bytes and KV
bytes, including prompt KV for an immediate-EOG case.
`transfers` is `host_to_device_bytes,device_to_host_bytes,wait_count`. `memory` is
`managed_host_peak_bytes,managed_device_peak_bytes,uma_alias_peak_bytes,rss_peak_bytes,driver_peak_bytes`;
the driver value is integer or null when unavailable. `timing` is
`wall_ns,load_ns,ttft_ns,prefill_ns,decode_ns,device_ns,transfer_ns,wait_ns`; wall is positive for a
started case, and other fields are nonnegative integer or null when unavailable. Overlapping
observations are not summed into wall.

`command_sha256` hashes ASCII `GPU_CASE_COMMAND`, NUL, little-endian u32 argv count, then each
argv as little-endian u64 UTF-8 byte length plus bytes, little-endian u32 environment count, then
each scrubbed `NAME=value` with the same u64 framing sorted by raw ASCII name. Names match
`[A-Z_][A-Z0-9_]*` and are unique. Secrets and machine-local input paths become
`<logical-id>:sha256:<digest>` before sorting/hashing. Empty is allowed only when no command could
be constructed and that case cannot pass.

`aggregate` is
`case_count,passed_count,failed_count,managed_host_peak_bytes,managed_device_peak_bytes,decision`.
Pass/fail counts partition cases into terminal PASS versus every other terminal, peaks are exact
maxima or zero for no case, and decision is always
`unmeasured`. Schema 1 has no performance comparison. `cleanup` is
`descendants_before,descendants_after,owned_paths_removed,invocation_state_safe,source_unchanged,inputs_unchanged`.
`failure` is `category,stage,case_ordinal,detail`, with empty/-1 PASS values and bounded redacted
FAIL detail. Elapsed time is positive and includes validation through cleanup/publication.

PASS requires every profile case present and passing, both model holdout sets passing on GPU,
nonzero GPU operations, weights/KV resident within budgets, exact source/input rechecks and safe
cleanup. FAIL may contain zero or a profile-order prefix of case rows; missing suffix rows are
represented by the top-level failure rather than fabricated timings. The CLI returns zero only for
PASS.

### 3.9 Canonical codec vectors

The following are exact UTF-8 bytes with one final LF per line. Decode plus canonical encode must
reproduce each line byte-for-byte; reordered input canonicalizes to the same line. Duplicate keys,
uppercase digests, BOM, missing final document boundary and a second document fail. Empty required
collections exercise codec shape only and fail the semantic array bounds in §§3.3–3.8.

```json
{"schema_version":1,"backend":"metal","device":"golden","backend_bundle":"bundle","placement":"resident","host_budget_bytes":1,"device_budget_bytes":1,"prefetch":"off"}
{"schema_version":1,"artifact_kind":"GPU_SOURCE_MANIFEST","repository":"https://github.com/sanohiro/align-llm.git","object_format":"sha1","commit":"0000000000000000000000000000000000000000","commit_object_sha256":"0000000000000000000000000000000000000000000000000000000000000000","tree":"0000000000000000000000000000000000000000","files":[]}
{"schema_version":1,"artifact_kind":"GPU_RUNTIME_PROFILE","profile_id":"golden","platform":"macos","source":{"commit":"0000000000000000000000000000000000000000","manifest_sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"bundle_manifest":{"path":"bundle.json","sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"models":[],"runtime_options":[],"cases":[],"deadlines_ns":{"preparation":1,"generation":1}}
{"schema_version":1,"artifact_kind":"GPU_BACKEND_BUNDLE","bundle_id":"0000000000000000000000000000000000000000000000000000000000000000","backend":"metal","ggml":{"commit":"0000000000000000000000000000000000000000","source_manifest_sha256":"0000000000000000000000000000000000000000000000000000000000000000","version":"golden"},"target":{"os":"macos","arch":"aarch64","gpu_architectures":[]},"toolchain":{"c_compiler":{"name":"golden","version":"golden","sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"cxx_compiler":{"name":"golden","version":"golden","sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"sdk":{"name":"golden","version":"golden","sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"toolkit":{"name":"none","version":"none","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}},"build_flags":[],"artifacts":[]}
{"schema_version":1,"artifact_kind":"GPU_NUMERIC_CALIBRATION","calibration_id":"0000000000000000000000000000000000000000000000000000000000000000","backend":"metal","bundle_id":"0000000000000000000000000000000000000000000000000000000000000000","model":{"model_id":"qwen2","model_sha256":"0000000000000000000000000000000000000000000000000000000000000000","pack_sha256":"0000000000000000000000000000000000000000000000000000000000000000","geometry_sha256":"0000000000000000000000000000000000000000000000000000000000000000","quantization":"Q4_K_M"},"precision":"f32","comparison":{"absolute_tolerance_f32_bits":"00000000","relative_tolerance_f32_bits":"00000000","near_tie_tolerance_f32_bits":"00000000","nonfinite":"reject","reference":"cpu-same-build","layer_scope":"all","topk_rule":"same-ordered-ids-or-declared-near-tie"},"cases":[]}
{"schema_version":1,"artifact_kind":"GPU_RUNTIME_EVIDENCE","status":"FAIL","suite":"generation","profile_id":"golden","source":{"commit":"0000000000000000000000000000000000000000","source_manifest_sha256":"0000000000000000000000000000000000000000000000000000000000000000","source_snapshot_sha256":"0000000000000000000000000000000000000000000000000000000000000000","align_revision":"0000000000000000000000000000000000000000","compiler":{"state":"unavailable","name":"","version":"","sha256":""},"runtime":{"state":"unavailable","name":"","version":"","sha256":""},"runner":{"state":"available","name":"gpu-runtime-qualify","version":"golden","sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"shim":{"state":"unavailable","name":"","version":"","sha256":""},"cpu_reference":{"state":"unavailable","name":"","version":"","sha256":""}},"host":{"platform":"macos","os_version":"golden","kernel":"golden","arch":"aarch64","wsl":false,"cpu":"golden","logical_cpus":1,"host_total_bytes":1,"host_free_bytes":1,"backend":"metal","device_state":"unavailable","registry_device":"","device_description":"","driver":"","gpu_architecture":"","device_total_bytes":0,"device_free_bytes":0},"bundle":{"manifest_sha256":"0000000000000000000000000000000000000000000000000000000000000000","bundle_id":"0000000000000000000000000000000000000000000000000000000000000000","loaded_artifact_sha256s":[]},"inputs":{"profile_sha256":"0000000000000000000000000000000000000000000000000000000000000000","models":[],"calibration_ids":[],"case_order_sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"files":[],"cases":[],"aggregate":{"case_count":0,"passed_count":0,"failed_count":0,"managed_host_peak_bytes":0,"managed_device_peak_bytes":0,"decision":"unmeasured"},"cleanup":{"descendants_before":0,"descendants_after":0,"owned_paths_removed":true,"invocation_state_safe":true,"source_unchanged":true,"inputs_unchanged":true},"failure":{"category":"CONFIG","stage":"options","case_ordinal":-1,"detail":"golden"},"elapsed_ns":1}
```

## 4. Execution and memory design

`provider_runtime` admits requests and owns text output. `decode_step` and `moe_decode_step`
retain architecture semantics, token/EOG order and sampling. New `runtime_device`,
`runtime_memory` and `runtime_execution` modules own backend-neutral device state, admission and
execution. Extend `ggml_ffi.align` and `ggml_shim.c` only with shaped checked calls and native
resource ownership; do not duplicate model math in backend-specific loops.

Use ggml supported-op and allocation queries for the exact graph. Before allocation, checked
admission includes immutable weights, maximum-context KV, peak activation/workspace, scheduler
copies, metadata and staging. Available-memory probes are advisory. A one-byte-too-small budget
fails before weight upload. Driver/runtime overhead is reported separately from managed caps.

Upload each weight once per invocation. KV and reusable workspaces stay resident through prefill and
all decode steps. Host readback is limited to final logits for the existing sampler and declared
compact routing decisions. Never call a CPU pointer primitive on device-only storage. OLMoE keeps
gate/up/down identity and ordered expert reduction; any compact expert view carries an explicit
global/local map.

Metal may alias host storage only when access/alignment are proven and the host owner outlives
completion. Alias bytes count against the device working set and once against physical host use.
CUDA uses explicit device allocations/copies and bounded host staging. No implicit managed-memory
oversubscription, swap or CPU graph fallback is permitted in `resident`.

Every native submission has an explicit completion boundary before readback, reset or destruction.
No borrowed Align slice survives an FFI call. Scheduler reset invalidates all graph/tensor
references. On failure, drain when possible, preserve the first fault, release in reverse ownership
order and poison process state if native safety cannot be proven.

## 5. Closure matrix and owners

| Owner/boundary | Success | Failure/malformed | Cleanup and exact regression |
| --- | --- | --- | --- |
| config/provider/CLI | empty path preserves CPU; exact terminal option selects GPU | duplicate/misplaced option, bad JSON/enums/budgets, network option | no device side effect; `gpu-config`, provider/CLI smoke |
| bundle/device registry | exact Metal/CUDA device and verified artifact set | wrong backend/device/ABI/hash/arch, missing op, bundle switch | pin once; poison partial init; `gpu-device-select`, `gpu-bundle-reuse`, `gpu-bundle-switch` |
| native owner | construct, move, borrow, explicit completion | failure at each construction prefix and completion stage | exactly-once reverse Drop; `gpu-native-owner` in whole/per-unit builds |
| admission/allocation | exact weights/KV/workspace within both caps; UMA alias accounted once | overflow, zero/one-byte-too-small cap, driver allocation race | release every prefix; `gpu-budget-boundary`, `gpu-uma-alias`, `gpu-allocation-prefix` |
| graph and pointers | supported graph on declared GPU; device-safe transfers | unsupported op/buffer, device pointer passed to CPU, stale reference, nonfinite output | complete before reset/free; `gpu-graph-placement`, `gpu-device-pointer`, `gpu-scheduler-reset` |
| Qwen/OLMoE decode | prefill, >1 decode, resident KV, correct positions/router/expert map | immediate EOG, maximum 1/128, context edge, routing tie, truncated source | KV outlives steps; `gpu-decode-kv`, `gpu-expert-map`, `gpu-eog`, `gpu-context-boundary` |
| invocation guard | sequential same-bundle requests and concurrent CPU independence | concurrent GPU request, different bundle, failed prior native init | guard released only from safe state; `gpu-invocation-busy`, `gpu-second-after-failure` |
| sampler/result | same logits preserve exact greedy/RNG/filter/output behavior | malformed/nonfinite logits, decode error, partial text | no handle escapes; `gpu-sampler-fixed`, `gpu-output-refusal` |
| profile/calibration | exact four-row expansion executes every calibration/holdout twice | omitted/extra/reordered/cross-model case, changed tolerance/expected output | immutable input recheck; `gpu-profile-coverage`, `gpu-holdout-replay` |
| evidence/publication | canonical codecs, complete Git snapshot, available/unavailable build identities, command hash | duplicate/oversize records, source/tree mismatch, compile/crash/timeout, >4,096 files or >512 MiB projected closure | kill/reap owned group, retain bounded diagnostics, exclusive rename; `gpu-schema-codec`, `gpu-source-replay`, `gpu-build-failure-evidence`, `gpu-command-hash`, `gpu-process-cleanup`, `gpu-result-replay` |

Before creating the staging directory, the qualifier computes a conservative closure count/size from
the source manifest, fixed retained inputs, possible produced artifacts and two logs per profile
case. A projection above 4,096 files or 512 MiB fails without output. Runtime streaming
enforces the same limits; unexpected growth publishes FAIL only when still within the hard bound.

## 6. Qualification and acceptance

Model-free owners exercise real application control/ownership branches with delayed completion and
recoverable faults. Backend build/loader checks verify immutable bundles on each target OS. Neither
level claims GPU math.

The real `generation` suite uses populated committed profiles and calibrations for both initial
models. Its complete derived corpus covers prefill, multiple decode steps, immediate EOG, maximum
one and 128, context boundary, Qwen greedy, OLMoE greedy/seeded, and two invocation lifetimes.
Teacher-forced CPU/GPU comparisons cover all layers, router boundaries and final logits using
precommitted tolerances; generated token/output expectations and repeated executions also pass.
Evidence must show nonzero GPU operations, complete resident weights/KV, bounded managed memory and
no hidden all-CPU execution.

G1 ships concrete immutable Metal and CUDA bundle recipes and populated schema-1 profiles and
calibrations before the first real acceptance run. The Mac can qualify Metal locally. The same
runner and replay contract are handed to the PC for CUDA without remote login, credentials, driver
installation or model upload. Missing hardware is a failed requested qualification, not N/A.

The output records actual OS/kernel/WSL, CPU, registry/device/driver/architecture, RAM/VRAM,
toolchains, source/build identities, per-case output/numeric/placement/transfer/memory/timing,
stdout/stderr, exit/signal and cleanup. Monotonic wall time is authoritative; synchronize at each
boundary and record unavailable device timing as null. Timings remain diagnostic.

Ordinary hosted CI stays model-free. Metal and CUDA are named focused qualifications run when their
owner boundary changes. A qualification timeout is 15 minutes per profile; preparation is a
separate maximum 60 minutes. Timeouts retain bounded evidence and do not justify extending the
profile after results are observed.

## 7. Align and native prerequisites

The consumer pin already ships package-defined opaque Move resources with exactly-once destruction
and owner-tied references. G1 uses that real surface and ordinary scalar C FFI. It does not invent a
resource API, capture numeric pointers or hide native I/O in background tasks.

| Requirement | Owner/consequence |
| --- | --- |
| registry, allocation, copies, op checks, synchronization and bundle builds | application plus pinned ggml |
| missing device op/quant support | explicit backend refusal; no fake kernel or silent CPU fallback |
| fallible host reservation | Request 35 remains non-blocking for bounded synchronous G1, blocking before graceful universal host-OOM recovery is promised |
| owned background I/O capture | Request 41 is not consumed by synchronous G1 |
| opaque exactly-once native owner | shipped Align resource; verify in `gpu-native-owner` |
| native Windows executable | separate future Align/platform prerequisite; WSL2 is Linux |

Before implementation, probe the pinned backend for Q4_K/Q6_K graph operations, `mul_mat_id`,
alignment/allocation sizes, KV updates, scheduler accounting, host visibility, status/abort behavior
and synchronization. Record genuine missing Align capabilities in `docs/align-requests.md`.
Feasibility probes and bundle tooling stay inside the first consumer capability, not standalone PRs.

## 8. Later delivery order

| Item | Consumer boundary and required future gate |
| --- | --- |
| 81 / G2 bounded offload | Add deterministic whole-unit layer/expert placement under host/device budgets, bounded AlignPack reads and synchronous `hybrid/off`. Extend options/profile/evidence for placement and eviction before coding. |
| 82 / G3 Vulkan | Add the same working generation/offload consumer and immutable Vulkan bundle. Qualify each device/OS independently. |
| 83 / G4 HIP/ROCm | Add the same consumer for a supported AMD stack. Build work may proceed without hardware; qualification remains pending until real AMD evidence. |
| 84 / G5 overlap | Add bounded same-thread transfer/compute overlap after G2. Precommit the exact full-request metric, paired schedule, incomplete-leg representation and recommendation gate in its own schema before measurement. `prefetch=off` keeps its meaning. |
| 85 / G6 coding decision | Compare the public provider with GPU-enabled llama.cpp and controls. Precommit task corpus, attempt/retry order and cap, validation, first-pass stop rule, lifecycle, primary time-to-passing-patch metric, partial failure states and aggregation before measurement. |

Start implementation with G1. A merged checkpoint is followed by the next eligible consumer. AMD
hardware absence does not block Metal/CUDA or Vulkan work, and no compile-only result closes a
device qualification.

## 9. Current verification

This design-only change requires documentation consistency, canonical-schema inspection,
`git diff --check`, one stable comprehensive review and the documentation publication preflight.
Source tests, compiler adoption, GPU builds and device qualification are N/A until G1 implementation.
