# GPU runtime: Metal, CUDA, Vulkan and HIP

Status: design only, 2026-09-06. No capability in this document is implemented by this change.
This is the authoritative GPU contract and delivery plan for roadmap items 80–85. The user requested
planning before implementation. The current CPU result remains historical evidence, not GPU evidence.

## 1. Outcome and evidence

A caller must be able to generate text through `AlignRuntime` using an explicitly selected GPU,
keep weights and KV on that device, and use bounded CPU/DRAM/AlignPack offload when the model does
not fit. Metal, CUDA, Vulkan and HIP share the same application contract. Backend-specific kernels
come from ggml; Align owns model semantics, routing policy, placement, budgets, cache decisions,
scheduling and generation. Calling a GPU-enabled llama-server remains a useful control, but does
not implement this in-process runtime.

The existing sources establish the starting point:

- `gpu_forward.align` and R5C implement dense Qwen prefill on Metal; PR #129 includes real-device
  correctness evidence. Its window wrapping and diagnostic readbacks do not define a production
  decode architecture or establish end-to-end speedup.
- `moe_decode_step.align` opens `ggml_ffi.device_open`; `align_ggml_device_open` in `ggml_shim.c`
  explicitly returns the CPU device. GPU support therefore needs a generation consumer, not only
  another backend library in the build.
- CPU generation already supplies Qwen greedy and OLMoE greedy/seeded sampling, EOG handling,
  tokenization, geometry/source checks, an expert cache and provider integration. Reuse those
  semantics and their fixtures. Audit host-pointer assumptions before sharing execution machinery.
- R8 items 49–79 qualify a CPU implementation and fixed-host optimization sequence. They do not
  discharge the architectural R8 CPU/GPU scheduling and prefetch objectives.
- At consumer Align `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`, the installed ggml 0.21.0
  `ggml-backend.h` supplies device properties, buffer types/allocation, tensor transfers,
  supports-op checks, synchronization, events and a multi-backend scheduler. These are native APIs;
  most are not yet exposed by this application's shim/FFI. The exact build must be pinned before
  use; a header declaration alone does not prove backend support or a recoverable failure path.

Upstream's [build documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)
documents Metal, CUDA, Vulkan and HIP builds. It is discovery evidence; implementation recipes must
replace moving branch references with immutable revisions and tested SDK/compiler combinations.
No custom CUDA/Metal shader or second model frontend is a prerequisite of this program.

## 2. Hardware and platform scope

Selection is by backend and device identity, never by a hard-coded GPU model. Query actual memory,
allocation limits, supported operations, buffer accessibility and synchronization facilities.
Compile GPU code for the explicitly recorded target architectures; reject a missing compatible
device binary instead of treating every NVIDIA or AMD generation as supported.

| Backend | Target family | Initial validation environment | Evidence still required |
| --- | --- | --- | --- |
| CPU | supported host CPUs | existing macOS and Linux owners | unchanged CPU behavior throughout |
| Metal | Apple Silicon unified memory | available Mac, currently Apple M1 / 16 GiB | generation, resident KV, offload, lifetime and performance |
| CUDA | compatible NVIDIA GPUs | user's RTX 4070 Ti; native Linux or WSL2 Linux | actual driver/toolkit/device inventory and every GPU acceptance suite |
| Vulkan | compatible NVIDIA, AMD and Intel devices | first NVIDIA PC where Vulkan compute is exposed | AMD/Intel require separate devices; WSL2 Vulkan is not inferred from CUDA access |
| HIP | ROCm-supported AMD GPUs | no AMD device currently available | build recipe plus real supported AMD GPU/OS/driver qualification |

The RTX 4070 Ti is a representative test device, not a product restriction. NVIDIA lists the
non-SUPER card with [12 GB memory](https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4070-family/).
Discover the installed device rather than deriving capacity from that name. Start the test profile
with a 9-GiB device-allocation budget only if admission allows it; also test 2-GiB and 4-GiB constrained
budgets. Those values belong to fixtures/profiles, never runtime defaults or backend dispatch.
Host RAM, usable GPU memory, driver, filesystem and toolkit remain inventory inputs to collect.

Native Linux x86_64 is a first-class target. WSL2 uses the Linux Align toolchain with a Windows
NVIDIA driver; it is a separate performance environment. Follow the
[NVIDIA WSL guidance](https://docs.nvidia.com/cuda/wsl-user-guide/): use the WSL-compatible toolkit
without replacing the Windows-provided driver with a Linux GPU driver inside WSL. Keep model and
build data in the Linux filesystem for the initial WSL profile; a `/mnt` Windows filesystem is a
separate storage experiment. Native Windows is a future compiler/runtime/platform port: current
Align releases cover macOS aarch64 and Linux x86_64/aarch64, not Windows. Lack of WSL is no issue on
native Linux. No Windows-native support is claimed by a WSL result.

AMD has two planned routes: portable Vulkan and native HIP/ROCm. Validate the selected GPU against
the pinned ROCm stack; upstream [AMD integration guidance](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/inference/llamacpp.html)
does not imply every Radeon/APU supports every ROCm release. No AMD hardware blocks AMD-specific
qualification only; it must not block Metal/CUDA delivery or erase the AMD roadmap item.

Support is recorded per `(backend, GPU architecture/device, OS, driver, backend build, model,
quantization, placement mode)` with independent fields for implementation, build evidence,
functional qualification and performance decision. Values are respectively `planned|implemented`,
`unverified|pass|fail`, `unverified|pass|fail`, and `unmeasured|met|not_met`. No GPU is currently
qualified for the new generation contract. Compilation, stubs and another vendor's Vulkan run
cannot promote an untested tuple. Opt-in execution of an unverified tuple may be attempted after
runtime capability checks; absence of prior evidence is reported, not a model-name allowlist.

## 3. Public-contract ledger

These are proposed application surfaces, not available commands or new Align language syntax.
This ledger owns their meaning; capability sections refine internal implementation checkpoints.

| Surface | Contract, owner and acceptance |
| --- | --- |
| Configuration API | Add `ProviderConfig.runtime_options_path: str`. Empty preserves the existing CPU configuration. Nonempty is a borrowed UTF-8 path, 1–4096 bytes, no embedded NUL, consumed synchronously by `provider_runtime`. Network providers require empty. The caller retains path storage through the call. `gpu-config` owns constructors and refusal coverage. |
| Generation CLI | Extend the current `main --provider align-runtime MODEL PACK GEOMETRY PROMPT RESULT [MAX_TOKENS] [CACHE_BUDGET_BYTES]` with an optional terminal pair `--runtime-options OPTIONS.json`. Remove that pair before the existing positional parse; duplicate, misplaced or valueless options fail. Default maximum remains 64. Existing invocations remain CPU. |
| Option document | Strict UTF-8 JSON, maximum 16 KiB, schema 1, exact fields in §3.1; duplicate/unknown/missing keys, boolean-as-integer, fractions, overflow, invalid enums and trailing documents fail before model/device work. Read once into owned bounded data per invocation; do not re-read mutable options during generation. |
| Legacy cache interaction | Preserve the current Qwen-zero / OLMoE-positive `runtime_cache_budget_bytes` rule with either empty or nonempty options. For GPU execution this is a host expert-cache sublimit, must not exceed `host_budget_bytes`, and is charged once inside that total, never added to it. Resident execution may allocate zero host expert-cache bytes despite a positive ceiling. An explicit CPU options file is rejected in schema 1; CPU uses the established path. |
| Provider results | Existing owned text / `Result<string, Error>` and CLI schema 2 remain. Map GPU refusal to `Error.Invalid` with no partial successful output. Internal owned fault detail has stable category and stage strings (§3.2), exposed by qualification evidence. Do not persist raw handles or expose device memory through `str`/`slice`. |
| Model/request scope | Same exact `qwen2` and `olmoe` models, quantized member layouts, tokenizer/template and request bounds. Qwen remains greedy; OLMoE retains greedy and the shipped 0.3-temperature seeded policy. Keep the existing `ModelInfo.supports_seed` report based on the positive OLMoE cache setting; generation validates that setting against the actual model before device work. GPU configuration does not suppress the shipped seeded capability. |
| Device identity | `runtime_device` resolves one exact backend registry plus device name from that registry. Never use generic first-GPU selection. Return actual registry/device/driver/build identifiers in evidence. Ambiguous, unavailable or mismatched devices fail; multiple installed backends must not select another backend implicitly. |
| Memory ownership | `runtime_memory` owns the byte admission plan; `runtime_device` owns native device allocations through a local package resource wrapper using Align's shipped opaque Move resources; `runtime_execution` holds graph references only within the request. Bound all application-managed host/device storage, with UMA de-duplication (§4). Raw FFI stays inside the package's privileged internal boundary. Explicit fallible completion precedes success; exactly-once Drop is the safety fallback, not an error-reporting channel. |
| Fallback | `resident` is strict GPU tensor execution; unsupported graph ops or insufficient capacity fail before compute. `hybrid` permits only the declared CPU placement units and explicit transfers (§4). Never restart partly executed generation on CPU after GPU error. Small host token/sampler/control work is always allowed and identified. |
| Concurrency and state | Initially one generation per process, invocation-local resources, no persistent model/session/KV cache. A second in-process runtime invocation is rejected before native side effects through an atomic native admission guard. Independent processes have separate owners; available-memory probes are advisory and allocation races can fail. The first successfully initialized backend bundle pins its manifest digest for the process. Later sequential GPU invocations must name that same digest or fail `BUNDLE_IDENTITY/device` before registry or allocation side effects. Validation failure before native initialization pins nothing; partial initialization poisons GPU admission for the process. CPU invocations do not initialize or replace the GPU registry. The registry is never unloaded while a request can reference it. |
| Qualification consumer | Proposed `scripts/gpu-runtime-qualify --profile PROFILE.json --suite SUITE --output NEW_DIRECTORY`; suites `generation`, `offload`, `overlap`, `coding`. It builds/executes reviewed sources in isolation and packages §3.8 evidence for user-run PC validation. Explicit requested backend absent is failure, never passing N/A. Ordinary non-GPU CI stays model-free. |
| Build identity | Each backend recipe pins a ggml source commit, headers, shared libraries/plugins, shader/device binaries, target architectures, C/C++ compiler, SDK/toolkit and relevant flags. Record Align revision and compiler/runtime digests separately. `runtime_device` rejects incompatible ABI/build manifests; no ambient plugin search in qualification. Recipe/build tooling ships with its first working backend consumer. |
| Cache identity | Request-local weights: model+pack+geometry identities, member/plane id, quant layout, backend/device, placement and slot generation. KV additionally binds exact prompt/position/rope/mask/context, precision and request generation. No device bytes in existing persisted CPU KV files. Backend build caches additionally bind target/driver/compiler/kernel flags. No persistent application GPU cache format in this program. |
| Validation order | Common provider/request syntax; bounded option parse and conflicting legacy fields; model architecture/identity, pack/geometry, prompt/EOG/context; bundle identity and exact device; op/buffer capabilities; checked admission plan; allocation/transfers; prefill/decode; output validation; synchronize/teardown; successful result publication. Each failure prevents all later steps. |
| Prerequisites | G1–G4 use shipped FFI plus application/backend additions, subject to the probes in §7. Language-owned gaps stay registered and cannot be bypassed through captured numeric pointers or hidden native I/O workers. G5 advanced ownership use must wait on real Align prerequisites if it needs them. |
| Acceptance and metrics | Named matrix cases in §5, device suites in §6 and the capability shipping conditions in §8. This design itself makes no measured speedup or capacity claim. No production changes, toolchain adoption or GPU tests are part of the current design-only change. |

### 3.1 Exact runtime options schema 1

All fields are required. JSON member order is irrelevant; objects have no unspecified fields.

| Field | Type and values |
| --- | --- |
| `schema_version` | integer, exactly 1 |
| `backend` | string, `metal|cuda|vulkan|hip`; no implicit auto selection |
| `device` | string, exact name from the named registry, 1–256 UTF-8 bytes, no NUL |
| `backend_bundle` | path string, 1–4096 UTF-8 bytes, no NUL; prepared immutable build manifest directory |
| `placement` | string, `resident|hybrid` |
| `host_budget_bytes` | signed-64 integer in `1..2^63-1`; all managed host storage, not only expert cache |
| `device_budget_bytes` | signed-64 integer in `1..2^63-1`; all managed device allocation and workspace |
| `prefetch` | string, `off|overlap`; `overlap` requires `hybrid` and the G5 implementation |

G1 accepts only `resident/off`; G2 adds `hybrid/off`; G5 adds `hybrid/overlap`. Selecting a planned
but unimplemented backend or mode produces `UNSUPPORTED_CAPABILITY`, not a silent default.
Every product entrypoint constructing `ProviderConfig`, including the coding loop's provider
construction, must carry the same explicit option path when that entrypoint exposes runtime use.
Do not add a second sampling/configuration grammar to qualification helpers.

### 3.2 Internal failure vocabulary

Categories: `CONFIG`, `SOURCE_IDENTITY`, `BACKEND_UNAVAILABLE`, `DEVICE_UNAVAILABLE`, `BUNDLE_IDENTITY`,
`UNSUPPORTED_CAPABILITY`, `MEMORY_BUDGET`, `ALLOCATION`, `TRANSFER`, `COMPUTE`, `NONFINITE`,
`DEVICE_LOST`, `BUSY`, `CLEANUP`. Stages: `options`, `model`, `device`, `plan`, `allocate`,
`upload`, `prefill`, `decode`, `readback`, `synchronize`, `release`.
Preserve the first operation fault and separately report cleanup failure; cleanup failure forbids
success. Native aborts, OS OOM kills and unrecoverable driver hangs are process failures, not a
guaranteed returned `Error`. Qualifiers must bound and terminate their owned process groups and
report missing results as failures. No claim of universal recoverable OOM is made at the current
Align pin (Request 35). Inject recoverable failures only at API boundaries that can return them.

### 3.3 Canonical JSON and bounded record vocabulary

The runtime options, qualification profile, backend manifest, numeric calibration and evidence
records use strict JSON. Decode at most the byte limit named below as UTF-8 without a BOM, require
exactly one top-level object and reject duplicate or unknown keys, missing keys, trailing data,
boolean-as-integer, fractions and integers outside signed 64-bit range. A path is 1–4096 UTF-8 bytes
with no NUL unless a field explicitly permits the empty absent sentinel. An identifier matches
`[a-z0-9][a-z0-9._-]{0,63}`. A digest is exactly 64 lowercase hexadecimal characters. A Git commit
is exactly 40 or 64 lowercase hexadecimal characters. Arrays retain declared order; identifiers
are unique within their array.

Canonical writers emit UTF-8 without a BOM, the object-key order declared below, array order as
stored, lowercase hexadecimal, JSON's shortest decimal integer spelling, no insignificant
whitespace, and exactly one final LF. Strings escape quote, backslash and U+0000–U+001F with JSON
lowercase `\u00xx`; other Unicode is emitted directly. Parsers do not require member order, but
replay re-encodes and compares canonical bytes. Self-identities use SHA-256 over canonical bytes
with that one digest field replaced by 64 zeroes. Paths in retained evidence use `/`, are relative,
contain no empty, `.` or `..` component, and name a single-link regular file. Runtime input paths
are canonicalized before use; symlinks, aliases between distinct declared inputs and mutation
between first and final identity checks fail.

| Record | Maximum canonical bytes | Array bounds |
| --- | ---: | --- |
| runtime options | 16,384 | no arrays |
| `GPU_SOURCE_MANIFEST` | 16,777,216 | 1–100,000 tracked path rows |
| `GPU_RUNTIME_PROFILE` | 262,144 | 2 models, 1–16 option rows, 1–16 resource rows, 1–256 cases |
| `GPU_BACKEND_BUNDLE` | 262,144 | 1–32 GPU targets, 0–128 flags, 1–128 artifacts |
| `GPU_NUMERIC_CALIBRATION` | 1,048,576 | 2–64 cases; at most 4,096 prompt ids and 128 teacher/expected ids per case |
| `GPU_RUNTIME_EVIDENCE` result | 8,388,608 | 0–256 cases, 0–1,024 retained files |
| retained log/artifact | 4,194,304 per log; 536,870,912 total evidence directory | logs truncate only after recording original byte count and digest; required binaries are never truncated |

Every nested object below has exactly the listed keys in the listed canonical order. `FileRef` is
`path,sha256`; `Identity` is `name,version,sha256`; `ArtifactRef` is
`role,path,bytes,sha256`. Byte counts and nonnegative counts are `0..2^63-1`. An optional duration
or process result is JSON `null` when unavailable, never zero standing for unavailable.
After common framing, every decoder validates version/kind, exact keys, scalar types and bounds,
array bounds and uniqueness, tagged presence rules, cross-references, digests/identities and finally
record-specific semantic invariants, in that order. Replay follows the same order before checking
aggregate arithmetic and directory closure.

### 3.4 Source manifest and snapshot schema 1

Cross-host qualification retains the complete tracked repository tree, not a hand-selected source
closure. `GPU_SOURCE_MANIFEST` has order
`schema_version,artifact_kind,repository,object_format,commit,commit_object_sha256,tree,files`.
The constants are 1 and `GPU_SOURCE_MANIFEST`; `repository` is exactly
`https://github.com/sanohiro/align-llm.git` for this program, with no credential, query or fragment;
`object_format` is `sha1|sha256`; commit and tree widths match it. `commit_object_sha256` binds the
raw decompressed Git commit body retained as `source/commit`.

Each file row is ordered `path,mode,bytes,git_oid,sha256`, sorted by raw UTF-8 path bytes. Paths are
normalized repository-relative names with the §3.3 exclusions. Mode is exactly
`100644|100755|120000`. Bytes are the Git blob bytes: for mode 120000 they are the link-target text,
which replay never follows. `git_oid` is recomputed over the Git `blob <length>\0<bytes>` object and
`sha256` over the bytes alone. Distinct paths may share one content blob. The evidence directory
stores each distinct blob once as `source/blobs/<sha256>` and contains no materialized symlink.

Replay hashes `source/commit` as a Git commit object and requires the declared commit id, parses its
first `tree` header, reconstructs every nested Git tree object from the sorted paths, modes and
recomputed blob ids, and requires the declared tree id. It then requires that every manifest row
has its content-addressed regular file and that neither side has an extra entry. The source snapshot
identity is SHA-256 over ASCII `GPU_SOURCE_SNAPSHOT`, one NUL byte, the canonical manifest bytes,
then each row's raw 32-byte SHA-256 in row order. This maps the reviewed commit to the exact retained
tree without trusting repository ancestry on the replay host. Submodules and unsupported Git modes
are rejected before preparation; generated build products are separately retained as evidence
artifacts, never inserted into this tracked snapshot.
The profile's source commit and manifest digest must equal this record and its canonical SHA-256;
evidence repeats both and the derived snapshot identity. A mismatch is `SOURCE_IDENTITY/options`
before preparation.

### 3.5 Qualification profile schema 1

`GPU_RUNTIME_PROFILE` has top-level order
`schema_version,artifact_kind,profile_id,platform,source,bundle_manifest,references,models,runtime_options,resource_profiles,cases,deadlines_ns`.
`schema_version` is 1; `artifact_kind` is `GPU_RUNTIME_PROFILE`; `platform` is
`macos|linux|wsl2`. `source` is `commit,manifest_sha256`. `bundle_manifest` is a `FileRef`.
`references` is ordered `cpu,llama`; each row is `kind,path,sha256,version`. CPU uses
`kind="same-build"` and three empty strings: the runner builds it from the reviewed source and
records the resulting binary identity in evidence. Llama uses `kind="none"` plus empty strings for
non-coding suites, or `kind="file"` plus a valid path, digest and nonempty version. Coding cases
require the file form. These are the only empty path/digest sentinels.

Each `models` row is ordered
`model_id,model_path,model_sha256,pack_path,pack_sha256,geometry_path,geometry_sha256,calibration_path,calibration_sha256`.
The array contains exactly one `qwen2` then one `olmoe` row. Each path is an input path and every
digest binds its exact regular-file bytes. Each calibration document must bind the same model,
backend and bundle as its row and the selected manifest.

Each `runtime_options` row is ordered
`option_id,schema_version,backend,device,backend_bundle,placement,host_budget_bytes,device_budget_bytes,prefetch`.
The last eight fields have exactly §3.1 semantics; `backend_bundle` resolves to the same manifest
directory as `bundle_manifest.path`. Option identifiers are unique. G1 profiles contain only
`resident/off`; G2–G4 may add `hybrid/off`; G5 may add `hybrid/overlap`.

Each `resource_profiles` row is ordered
`resource_profile_id,threads,context_tokens,host_budget_bytes,device_budget_bytes,lifecycle`.
Threads are 1–256, context is 1–4096, budgets are positive i64, and schema 1 fixes
`lifecycle="reload-per-case"`. Rows are unique. A GPU case's resource budgets equal its runtime
option. CPU and llama controls use the same row as their paired candidate; the qualifier maps the
row to reviewed fixed commands and must refuse a backend that cannot enforce the requested limits.

Each `cases` row is ordered
`case_id,comparison_id,arm,pair_index,pair_slot,execution,cache_state,suite,model_id,option_id,resource_profile_id,input_kind,prompt_utf8,task_path,input_sha256,maximum_tokens,temperature_micros,seed`.
`suite` is `generation|offload|overlap|coding`; `model_id` resolves an earlier row. `execution` is
`cpu|llama|gpu_resident|gpu_sync|gpu_overlap`. A GPU execution resolves `option_id`; CPU/llama use
the empty option sentinel. Resident/off, hybrid/off and hybrid/overlap options must respectively
match the three GPU execution tags. Llama execution requires the file reference from `references`.
`resource_profile_id` resolves a declared row. `cache_state` is
`not_applicable|warm|cold|uncontrolled`; functional suites use `not_applicable`. Performance
comparisons use separate warm and cold comparison ids when OS-cache control is proven, otherwise
the latter is explicitly `uncontrolled` and cannot support a cold-start claim.
For `input_kind=prompt`, `prompt_utf8` is 0–65,536 UTF-8 bytes, `task_path` is empty and
`input_sha256` binds the prompt bytes. For `input_kind=task`, `prompt_utf8` is empty, `task_path` is
a path and the digest binds its bytes. `maximum_tokens` is 1–128. Qwen requires
`temperature_micros=0,seed=0`; OLMoE accepts that greedy pair or
`temperature_micros=300000` with any signed-i64 seed. Cases are in execution order and their exact canonical
array is the corpus identity. The selected CLI suite executes every and only matching row and
requires at least one. `generation`, `offload` and `overlap` each require both models; `coding`
requires every task in the named fixed coding corpus and rejects an unrecognized corpus digest.

An unpaired functional or diagnostic row uses empty `comparison_id`, `arm="single"`,
`pair_index=-1` and `pair_slot="single"`. A measured comparison uses a nonempty identifier,
`arm="control|candidate"`, `pair_index=0..3` and `pair_slot="first|second"`. For each comparison id,
all workload/sampling/resource/cache-state fields are equal and exactly eight contiguous rows appear chronologically: pair 0
control/candidate, pair 1 candidate/control, pair 2 control/candidate, pair 3 candidate/control.
This is AB/BA/AB/BA. Control and candidate each use one execution tag across the group and the tags
must differ. Overlap compares `gpu_sync` with `gpu_overlap`. Coding compares `llama` with one
qualified GPU execution; required `cpu` and any other synchronous GPU controls are additional
unpaired rows and cannot enter the primary aggregate. Generation/offload contain no measured
comparison and use only single GPU rows.

`deadlines_ns` is ordered `preparation,generation,offload,overlap,coding`. Every field is positive
and at most §6.3's corresponding ceiling; preparation is at most 3,600,000,000,000 ns,
generation/offload/overlap at most 900,000,000,000 ns and coding at most 1,800,000,000,000 ns.
The runner uses the profile value without extension after observing a result.

Profile validation order is byte/UTF-8/JSON shape; version/kind; scalar bounds; source and manifest
identity; ordered model files and calibrations; option cross-references and mode availability;
ordered case grammar/corpus identity; deadlines; canonical input recheck. No device or output
directory side effect precedes these checks.

### 3.6 Backend bundle manifest schema 1

The selected directory contains `manifest.json`, a canonical `GPU_BACKEND_BUNDLE` with order
`schema_version,artifact_kind,bundle_id,backend,ggml,target,toolchain,build_flags,artifacts`.
`schema_version` is 1, `artifact_kind` is `GPU_BACKEND_BUNDLE`, and `bundle_id` is the self-identity
defined in §3.3. `backend` is one value from §3.1. `ggml` is ordered
`commit,source_manifest_sha256,version`; the commit is immutable and the source manifest binds the
complete ggml checkout used to build.

`target` is ordered `os,arch,gpu_architectures`. `os` is `macos|linux`; `arch` is
`aarch64|x86_64`; `gpu_architectures` is a nonempty ordered array of identifiers actually compiled
into the bundle. `toolchain` is ordered `c_compiler,cxx_compiler,sdk,toolkit`, each an `Identity`.
The digest binds the exact executable for compilers and a canonical installed-file manifest for an
SDK/toolkit. An inapplicable SDK or toolkit uses `name="none",version="none"` and the SHA-256 of
the empty byte string; it is not omitted.

`build_flags` is the exact ordered argv suffix after tool-owned fixed arguments; no shell string or
ambient flag is accepted. Each artifact row has `role` in
`shared_library|backend_plugin|kernel_binary|shader_library|metadata`, a normalized relative path,
byte count and digest. Rows are sorted by `(role,path)`, paths are unique, and the array covers every
library/plugin/kernel/shader that can be loaded. Runtime loading is restricted to these verified
paths. The manifest parser first validates itself and its self-identity, then every artifact, target
and backend compatibility, before registry initialization.

The first successful registry initialization stores `bundle_id` plus manifest SHA-256 in native
process state. Same-bundle sequential invocations reuse it. A different digest, even for the same
backend/device name, fails before loading; a failed pre-load validation stores nothing. Any failure
after a registry/plugin side effect marks the state poisoned, retains the loaded libraries until
process exit and refuses later GPU requests. `gpu-bundle-reuse`, `gpu-bundle-switch` and
`gpu-second-after-failure` own these three paths.

### 3.7 Numeric calibration schema 1

Each model/backend/bundle has one canonical `GPU_NUMERIC_CALIBRATION` ordered
`schema_version,artifact_kind,calibration_id,backend,bundle_id,model,precision,comparison,cases`.
The first two constants are 1 and `GPU_NUMERIC_CALIBRATION`; `calibration_id` is the §3.3
self-identity. `model` is ordered
`model_id,model_sha256,pack_sha256,geometry_sha256,quantization`; `quantization` is `Q4_K_M` for the
initial models. `precision` is `f32`.

`comparison` is ordered
`absolute_tolerance_f32_bits,relative_tolerance_f32_bits,near_tie_tolerance_f32_bits,nonfinite,reference,layer_scope,topk_rule`.
Each tolerance is an eight-character lowercase finite nonnegative IEEE-754 binary32 bit pattern;
`nonfinite="reject"`, `reference="cpu-same-build"`, `layer_scope="all"`, and
`topk_rule="same-ordered-ids-or-declared-near-tie"`. A routed boundary is a declared near tie only
when the reference kth and first excluded scores differ by no more than the near-tie tolerance and
both selected sets contain only ids in that boundary group; ordered ids and weights outside that
group must match within absolute/relative tolerance. Tolerances are frozen before holdout runs.

Each case is ordered
`case_id,role,prompt_utf8,prompt_sha256,prompt_token_ids,teacher_forced_token_ids,sampler_mode,temperature_micros,seed,expected_token_ids`.
`role` is `calibration|holdout`, with at least one of each. The prompt is at most 65,536 UTF-8 bytes
and its digest is exact; prompt ids are nonnegative i32 values and reproduce tokenization exactly.
Teacher-forced ids are nonempty. `sampler_mode=greedy` requires zero temperature/seed;
`sampler_mode=seeded` requires 300000 micros and accepts every signed-i64 seed. Expected ids are the CPU
same-build sampler result for the supplied prefix, have length at most 128 and may be empty only for
immediate EOG. Case ids and prompt digests cannot cross the calibration/holdout partitions.

### 3.8 Evidence schema 1 and directory

The qualifier exclusively creates the named output directory through a sibling staging directory.
Malformed profile or an occupied destination creates no output. Once input validation succeeds,
functional failure, child crash/signal/timeout, missing result or proven cleanup failure publishes a
bounded failed bundle when the parent can still do so. The final directory contains `result.json`,
canonical copies `profile.json`, `bundle-manifest.json`, `calibration/qwen2.json` and
`calibration/olmoe.json`, `source-manifest.json`, `source/commit`, content-addressed
`source/blobs/<sha256>` and `artifacts/<sha256>`, and
`logs/<three-digit-ordinal>.stdout|stderr`. No other file is permitted. Model, pack and geometry
bytes are identified but never copied. Every retained helper, shim, source snapshot, loaded
plugin/kernel and nonempty log is copied before its temporary owner is removed.

`result.json` is `GPU_RUNTIME_EVIDENCE`, ordered
`schema_version,artifact_kind,status,suite,profile_id,source,host,bundle,inputs,files,cases,aggregate,cleanup,failure,elapsed_ns`.
The constants are 1 and `GPU_RUNTIME_EVIDENCE`; `status` is `PASS|FAIL`; `suite` is one of §3.5.

- `source` is ordered
  `commit,source_manifest_sha256,source_snapshot_sha256,align_revision,compiler_sha256,runtime_sha256,runner_sha256,shim_sha256,cpu_reference_sha256,cpu_reference_version,llama_reference_sha256,llama_reference_version`.
  Llama fields are empty outside coding; every other digest/version is present.
- `host` is ordered
  `platform,os_version,kernel,arch,wsl,cpu,logical_cpus,host_total_bytes,host_free_bytes,backend,registry_device,device_description,driver,gpu_architecture,device_total_bytes,device_free_bytes`.
  `wsl` is a boolean derived by the producer; memory fields are nonnegative observations.
- `bundle` is ordered `manifest_sha256,bundle_id,loaded_artifact_sha256s`; loaded digests are in
  actual load order and must be a duplicate-free subset of the manifest.
- `inputs` is ordered `profile_sha256,models,calibration_ids,case_order_sha256`. Model identity rows
  are ordered `model_id,model_sha256,pack_sha256,geometry_sha256`; calibration ids follow model
  order. No machine-local input path is retained here.
- `files` contains every retained regular file except `result.json`, sorted by path. Rows are
  `role,path,bytes,sha256,original_bytes,original_sha256,truncated`; roles are
  `profile|bundle_manifest|calibration|source_manifest|source_commit|source_blob|helper|shim|backend_artifact|stdout|stderr`.
  Non-log rows repeat bytes/digest as original and set `truncated=false`. A log exceeding 4 MiB is
  streamed through its original count/digest, retains the first 4 MiB and sets `truncated=true`;
  truncation makes its case fail. No extra file, hard link or symlink is accepted by replay.

Each `cases` row is ordered
`ordinal,case_id,comparison_id,arm,pair_index,pair_slot,execution,cache_state,model_id,option_id,resource_profile_id,terminal,category,stage,exit_code,signal,command_sha256,output_sha256,token_ids,nonfinite_count,numeric,placement,transfers,memory,timing,stdout_path,stderr_path`.
Ordinals are contiguous from zero and match profile order. `terminal` is
`PASS|FAIL|TIMEOUT|CRASH|SIGNAL|MISSING`; category/stage use §3.2 or are empty on pass;
`exit_code` and `signal` are integer or null. Output digest is empty only when no complete output
exists; token ids are bounded as in calibration. Comparison, arm, pair, execution, model and option
fields equal their profile row exactly. Cache state and resource profile also match. `command_sha256`
binds domain `GPU_CASE_COMMAND`, one NUL, then each exact argv and scrubbed `NAME=value` environment
entry as length-prefixed UTF-8 in execution order; secrets and machine-local model paths are replaced
by their declared logical id plus digest before hashing. It is empty only when no command could be
constructed; that case cannot pass.

- `numeric` is ordered
  `compared,max_absolute_f64_bits,max_relative_f64_bits,near_tie_count,mismatch_count`; bit strings
  are 16-character lowercase finite nonnegative binary64 patterns. When `compared=false`, both must
  be all zero and both counts zero. When true, zero is a valid exact comparison result.
- `placement` is ordered
  `gpu_operations,cpu_operations,gpu_layers,cpu_layers,gpu_experts,cpu_experts`; counts are
  nonnegative and suite acceptance rejects hidden all-CPU execution.
- `transfers` is ordered `host_to_device_bytes,device_to_host_bytes,alignpack_read_bytes,wait_count`.
- `memory` is ordered
  `managed_host_peak_bytes,managed_device_peak_bytes,uma_alias_peak_bytes,rss_peak_bytes,driver_peak_bytes`;
  the last field is integer or null when the driver exposes no value.
- `timing` is ordered
  `wall_ns,load_ns,ttft_ns,prefill_ns,decode_ns,device_ns,transfer_ns,wait_ns`; wall is positive for a
  started case and the other fields are nonnegative integers or null when unavailable. Overlapping
  durations are not summed to wall.

`aggregate` is ordered
`case_count,passed_count,failed_count,managed_host_peak_bytes,managed_device_peak_bytes,comparisons,decision`.
Counts and peaks are derived, never independent claims: case count is array length, pass/fail counts
partition it by terminal, and each peak is the maximum corresponding case value or zero for no
case. `comparisons` has exactly one row for each nonempty comparison id, sorted by id. A row is
ordered
`comparison_id,cache_state,resource_profile_id,primary_metric,control_execution,candidate_execution,control_values_ns,candidate_values_ns,paired_savings_ns,control_median_ns,candidate_median_ns,median_saving_ns,median_saving_ppm,all_candidate_faster,decision`.
`primary_metric` is `full-request-wall|time-to-passing-patch|decode-latency`. Executions equal the
profile group. Values are extracted in pair-index order from the named case timing field: wall,
complete coding-portfolio wall, or decode respectively. Each arm has exactly four positive values.
Paired saving `i` is `control[i]-candidate[i]`. For four values, median sorts ascending and uses
`(second+third)//2`; every addition/subtraction/multiplication is checked and `//` is mathematical
floor division. Median saving is control median minus candidate median and ppm is
`median_saving*1000000//control_median`. `all_candidate_faster` is true iff every paired saving is
positive.

A comparison is `met` iff all eight rows pass correctness/budget checks,
`all_candidate_faster=true` and ppm is at least 50,000. It is `not_met` when all eight rows pass but
the speed rule fails, and `not_eligible` otherwise; invalid arithmetic rejects the document rather
than producing a decision. Generation/offload have no comparisons and top decision `unmeasured`.
For overlap/coding, top decision is `met` iff every comparison is met, `not_met` iff all are eligible
and at least one is not met, otherwise `not_eligible`. `status=PASS` requires no failed case and a
top decision other than `not_eligible`; a valid slower run is therefore PASS/`not_met`.

`cleanup` is ordered
`descendants_before,descendants_after,owned_paths_removed,invocation_state_safe,source_unchanged,inputs_unchanged`.
Counts are nonnegative and the last four fields are booleans. Any false value forces `FAIL`.
`failure` is ordered `category,stage,case_ordinal,detail`; pass uses empty strings, -1 and empty
detail. Failure uses §3.2, -1 or an existing ordinal, and redacted UTF-8 detail of at most 4,096
bytes. `elapsed_ns` is positive and includes validation, cases, cleanup and publication preparation.
PASS requires every selected case PASS, exact input/source rechecks, safe cleanup and a suite-valid
aggregate. The CLI returns zero only for PASS.

### 3.9 Codec round-trip vectors

These exact one-line documents, including one final LF, are codec/shape goldens. Their empty arrays
exercise an envelope without pretending to be runnable qualification input; semantic validation
then rejects the empty required collections. Decode followed by canonical encode must reproduce the
bytes exactly. Reordered input decodes to the same values and canonicalizes to these bytes; a duplicate
key, uppercase digest, BOM, missing final document boundary or a second document is rejected.

```json
{"schema_version":1,"artifact_kind":"GPU_RUNTIME_PROFILE","profile_id":"golden","platform":"linux","source":{"commit":"0000000000000000000000000000000000000000","manifest_sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"bundle_manifest":{"path":"bundle.json","sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"references":{"cpu":{"kind":"same-build","path":"","sha256":"","version":""},"llama":{"kind":"none","path":"","sha256":"","version":""}},"models":[],"runtime_options":[],"resource_profiles":[],"cases":[],"deadlines_ns":{"preparation":1,"generation":1,"offload":1,"overlap":1,"coding":1}}
{"schema_version":1,"artifact_kind":"GPU_SOURCE_MANIFEST","repository":"https://github.com/sanohiro/align-llm.git","object_format":"sha1","commit":"0000000000000000000000000000000000000000","commit_object_sha256":"0000000000000000000000000000000000000000000000000000000000000000","tree":"0000000000000000000000000000000000000000","files":[]}
{"schema_version":1,"artifact_kind":"GPU_BACKEND_BUNDLE","bundle_id":"0000000000000000000000000000000000000000000000000000000000000000","backend":"metal","ggml":{"commit":"0000000000000000000000000000000000000000","source_manifest_sha256":"0000000000000000000000000000000000000000000000000000000000000000","version":"golden"},"target":{"os":"macos","arch":"aarch64","gpu_architectures":[]},"toolchain":{"c_compiler":{"name":"golden","version":"golden","sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"cxx_compiler":{"name":"golden","version":"golden","sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"sdk":{"name":"none","version":"none","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},"toolkit":{"name":"none","version":"none","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}},"build_flags":[],"artifacts":[]}
{"schema_version":1,"artifact_kind":"GPU_NUMERIC_CALIBRATION","calibration_id":"0000000000000000000000000000000000000000000000000000000000000000","backend":"metal","bundle_id":"0000000000000000000000000000000000000000000000000000000000000000","model":{"model_id":"qwen2","model_sha256":"0000000000000000000000000000000000000000000000000000000000000000","pack_sha256":"0000000000000000000000000000000000000000000000000000000000000000","geometry_sha256":"0000000000000000000000000000000000000000000000000000000000000000","quantization":"Q4_K_M"},"precision":"f32","comparison":{"absolute_tolerance_f32_bits":"00000000","relative_tolerance_f32_bits":"00000000","near_tie_tolerance_f32_bits":"00000000","nonfinite":"reject","reference":"cpu-same-build","layer_scope":"all","topk_rule":"same-ordered-ids-or-declared-near-tie"},"cases":[]}
{"schema_version":1,"artifact_kind":"GPU_RUNTIME_EVIDENCE","status":"FAIL","suite":"generation","profile_id":"golden","source":{"commit":"0000000000000000000000000000000000000000","source_manifest_sha256":"0000000000000000000000000000000000000000000000000000000000000000","source_snapshot_sha256":"0000000000000000000000000000000000000000000000000000000000000000","align_revision":"0000000000000000000000000000000000000000","compiler_sha256":"0000000000000000000000000000000000000000000000000000000000000000","runtime_sha256":"0000000000000000000000000000000000000000000000000000000000000000","runner_sha256":"0000000000000000000000000000000000000000000000000000000000000000","shim_sha256":"0000000000000000000000000000000000000000000000000000000000000000","cpu_reference_sha256":"0000000000000000000000000000000000000000000000000000000000000000","cpu_reference_version":"golden","llama_reference_sha256":"","llama_reference_version":""},"host":{"platform":"linux","os_version":"golden","kernel":"golden","arch":"x86_64","wsl":false,"cpu":"golden","logical_cpus":1,"host_total_bytes":1,"host_free_bytes":1,"backend":"cuda","registry_device":"CUDA0","device_description":"golden","driver":"golden","gpu_architecture":"sm_89","device_total_bytes":1,"device_free_bytes":1},"bundle":{"manifest_sha256":"0000000000000000000000000000000000000000000000000000000000000000","bundle_id":"0000000000000000000000000000000000000000000000000000000000000000","loaded_artifact_sha256s":[]},"inputs":{"profile_sha256":"0000000000000000000000000000000000000000000000000000000000000000","models":[],"calibration_ids":[],"case_order_sha256":"0000000000000000000000000000000000000000000000000000000000000000"},"files":[],"cases":[],"aggregate":{"case_count":0,"passed_count":0,"failed_count":0,"managed_host_peak_bytes":0,"managed_device_peak_bytes":0,"comparisons":[],"decision":"unmeasured"},"cleanup":{"descendants_before":0,"descendants_after":0,"owned_paths_removed":true,"invocation_state_safe":true,"source_unchanged":true,"inputs_unchanged":true},"failure":{"category":"CONFIG","stage":"options","case_ordinal":-1,"detail":"golden"},"elapsed_ns":1}
```

## 4. Execution and memory design

### 4.1 Division of responsibility

`provider_runtime` admits the request and owns text output. `decode_step` / `moe_decode_step` keep
architecture semantics, token order, EOG and sampler sequencing. New `runtime_device` and
`runtime_memory` modules expose backend-neutral data and bounded allocations; `runtime_execution`
coordinates placement and completion. Extend `ggml_ffi.align` and `ggml_shim.c` only for shaped,
checked calls and native resource ownership. Do not duplicate model math in a CUDA-specific loop.

Use ggml's supported graph allocator/scheduler to execute explicitly assigned subgraphs. Probe its
actual split/copy behavior at the pinned revision and count the resulting device/CPU operations.
An automatic scheduler is not permission for invisible CPU fallback or unbudgeted transfer buffers.
Reject a backend integration if mandatory allocations cannot be bounded/observed. Its reset
invalidates allocated tensor references; discard those references before constructing replacements.

In `resident`, upload each immutable model weight once, keep KV and reusable activation/workspace
allocations for the invocation, and run prefill plus every decode step on the selected GPU. Host
readback is limited to final logits needed by the existing sampler, compact routing decisions when
needed and explicit debug output. No full KV or per-node activation readback in normal generation.
The all-expert-resident OLMoE path may use the original expert ids; a compact expert view must carry
an explicit global-to-local map and preserve gate/up/down correspondence and reduction order.

The existing CPU-native KV copy/compare operations require host-visible storage. On device-only
buffers, use ggml tensor operations/transfers; never call a CPU pointer primitive on a device
address. Diagnostic checksums/readbacks remain opt-in and their cost stays outside production
latency claims. Do not move a CPU optimization into GPU execution merely because its signature fits.

### 4.2 Budgets and placement

Use checked arithmetic before every dimension product, padding, stride, cache capacity and transfer
range. Admission includes weights, KV at admitted maximum context, peak activations, scheduler
copies, graph metadata, host staging, slot tables and overlap workspace. Use the selected backend's
actual allocation size/alignment, not only GGUF payload bytes. Demand too large for the minimum
executable unit is a deterministic `MEMORY_BUDGET` refusal before weights are loaded.

Budgets cover application-managed allocations. Report process RSS and driver-reported GPU use
separately because runtime libraries, kernel/driver reservations and OS page cache are not fully
controlled by these caps. Record that residual overhead; do not promise a hard whole-process RSS
or board-wide VRAM ceiling. Memory queries do not reserve space; allocation can still fail after a
successful plan. Never use managed-memory oversubscription or host swapping as implicit capacity.

Metal/UMA may borrow host storage only when the backend proves accessibility and alignment and the
owner remains alive through completion. Charge such bytes once to physical host memory and against
the device working-set budget as an alias; report alias bytes so totals are not falsely added.
CUDA/HIP/discrete Vulkan normally allocate device buffers and explicitly copy. Pinned host staging
counts against host budget, is bounded, and is released after completion. Pageable fallback is
allowed only as an explicitly recorded synchronous strategy. UMA is a capability, not a vendor test.

`hybrid` first uses a deterministic synchronous planner. Pin KV, activations, device dense layers
and minimum expert workspace; use remaining space for device experts. Place whole dense layers on
GPU or CPU, retaining the layer's KV with its attention computation; transfer residuals at layer
boundaries. For routed layers, keep router and attention at their planned owner, obtain real top-k
ids, and choose GPU phase B or whole phase-B CPU fallback using preallocated compatible workspace.
Never split one expert reduction across devices in the first version. Preserve ordered selected
expert ids and weights. Do not assume predicted experts may substitute for actual routing.

Device and host expert caches are separate deterministic LRUs with a shared immutable source key.
Do not evict in-flight slots. Fill misses from the host cache or bounded positional AlignPack reads,
then transfer only missing expert payloads; an eviction drops clean weights without disk writeback.
If a selected set does not fit the available GPU workspace, use the preplanned CPU phase B only in
hybrid mode. CPU fallback itself must fit host budget. Record every placement/fallback and transfer.
G2 acceptance requires successful offload, not speedup or learned placement. Never make fitting a
model dependent on a later learned policy. Synthetic budget limits on the existing models exercise
both device and host misses without requiring a larger model download.

### 4.3 Completion, overlap and failure

A reusable slot follows `FREE -> FILLING -> READY -> IN_FLIGHT -> READY`, with a monotonically
checked generation per new content assignment; invalidate/refuse on generation exhaustion.
Publication of `READY` requires exact completed input and transfer. Consumers bind key+generation,
not a reusable slot index alone. Eviction is permitted only from completed `READY` storage.

G1–G4 use synchronous transfer/compute completion. G5 may enqueue device work, read the next
independent block synchronously on the host, and wait before reusing either slot. All asynchronous
device references point to native-owner buffers or graph state retained by the enclosing request;
do not let a transient borrowed Align slice escape one FFI call. Host bytes are copied into owned
staging synchronously before an asynchronous submission can return. That extra copy is measured.
Use backend events only when supported and proven; a synchronous backend remains usable but
reports overlap unavailable. Submission time is not GPU execution time.

Background Align I/O tasks consuming borrowed/owned buffers remain a separate Request-41-dependent
extension. Current `spawn` registration does not alone establish overlap: at sibling commit
`46664a01352f7a669339c2eae2661d55659b96c2`, `align_rt_tg_register` appends tasks and
`align_rt_tg_wait` dispatches them. A future design must demonstrate concurrent execution as well as
safe capture. No native thread that hides the same missing Align I/O ownership contract is allowed.

On failure stop scheduling, drain known device work before releasing buffers, destroy graph and
allocator owners, then device buffers/events/staging/backends, then application frame storage.
Keep first fault plus cleanup fault. If completion cannot be proven after device loss/hang, report
an unusable invocation and fail the process-level qualifier; do not reuse or free potentially live
storage to make a balance counter pass. Process-global admission is released only after a safe
terminal state; poisoned state cannot admit a second request.

No persistent model session, cross-request GPU KV serialization, multi-GPU tensor parallelism or
distributed execution is included in items 80–85. These need their own public ownership contracts.
They are not required for one GPU plus CPU offload to become useful.

## 5. Closure matrix and planned owners

Names below are proposed cases in `scripts/test-gpu-runtime`; neither it nor the new modules exist
yet. The four suites reuse this owner and real-device qualification rather than adding one script
for every case. Each capability must map its applicable rows to the final diff and passing evidence
before review; later-capability rows remain explicitly deferred.

| Owner / boundary | Construction and success | Failure / malformed / early exit | Cleanup and exact regression |
| --- | --- | --- | --- |
| `model`, `main`, `provider_runtime` | option path at every constructor, old/new CLI, greedy and sampled dispatch | missing/duplicate/unknown fields; crossed budgets; unsupported model/mode; invalid request before I/O | owned parsed options and output; `gpu-config`, `gpu-cli-legacy`, `gpu-provider-mode` |
| `runtime_device`, FFI/shim, build recipe | exact registry/device and bundle identity; same-bundle sequential reuse; allocation-size/capability queries | wrong plugin/SDK/ABI, device absent, switched bundle, missing op/event/host visibility; no fallback | borrowed registry versus owned backend distinguished; `gpu-device-identity`, `gpu-capability-refusal`, `gpu-bundle-mutation`, `gpu-bundle-reuse`, `gpu-bundle-switch` |
| `runtime_memory` | checked host/device/UMA admission and complete allocation accounting | overflow, zero/one-byte-too-small budgets, driver-race refusal, oversized workspace | unwind every allocation prefix; `gpu-budget-boundary`, `gpu-uma-alias`, `gpu-allocation-prefix` |
| graph construction, `runtime_execution` | supported ops placed at declared owners; correct quant offsets and graph lifetime | incompatible buffer, stale graph after scheduler reset, nonfinite output | exactly one owner per graph/allocator; `gpu-graph-placement`, `gpu-device-pointer`, `gpu-scheduler-reset` |
| dense/MoE decoder and KV | prefill and >1 decode, correct positions, mask/rope, router ids and expert map | max-one/EOG before decode, context bound, wrong expert member/offset or routing tie | KV outlives all queued steps; `gpu-decode-kv`, `gpu-expert-map`, `gpu-eog`, `gpu-context-boundary` |
| host/device LRUs and fallback (G2) | miss/fill/reuse/eviction and whole-unit fallback; exact source bytes | host+GPU exhaustion, wrong generation, truncated pack, partial read/transfer | no evict-in-flight or stale success; `gpu-offload-thrash`, `gpu-fallback-plan`, `gpu-slot-generation`, `gpu-short-read` |
| overlap (G5) | bounded two-slot pipeline, dependency events, CPU read while GPU runs | delayed completion, cancellation, transfer/compute failure, unsupported async, generation exhaustion | drain before reuse/free; `gpu-overlap-order`, `gpu-overlap-refusal`, `gpu-drain-failure` |
| invocation admission | repeated sequential requests; correct initialized-registry reuse | concurrent CPU/GPU and GPU/GPU attempts; failed second request; poisoned owner | atomic admission and exactly-once release; `gpu-invocation-busy`, `gpu-second-after-failure` |
| result and sampler | same input logits preserve exact RNG/filter behavior; complete owned UTF-8 output | malformed/nonfinite logits, decode errors, no partial success | no device handle escapes; `gpu-sampler-fixed`, `gpu-output-refusal` |
| paired measurement and aggregate | exact single/control/candidate arms and AB/BA/AB/BA groups; recomputed values/medians/ppm | wrong arm, order, resource/cache state, count or arithmetic; failed pair is not eligible | no timing category is added into wall; `gpu-pair-schedule`, `gpu-aggregate-replay` |
| qualifier and publication | schema codec goldens, complete Git-object snapshot, strict artifacts, deadline, actual backend execution | malformed/duplicate/oversized records, source/tree mismatch, missing device, crash, late source/input drift, timeout and descendant leak | post-cleanup revalidation and exclusive output publication; `gpu-schema-codec`, `gpu-source-replay`, `gpu-evidence-mutation`, `gpu-process-cleanup`, `gpu-result-replay` |

Move-in/out, replacement and source-nulling reuse Align's shipped Move rules and provider owners.
Use a local package-defined opaque resource for request-native state, with its internal destructor
and owner-tied access. Raw handles never live in Copy application records that pretend to own them.
Dependent children cannot outlive their owner; asynchronous work must finish before destruction.
The `gpu-native-owner` regression covers exactly-once destruction across moves, early returns,
partial construction and completion failure. Whole-program and per-unit compiler builds of changed modules are required if both are
supported by the selected pin. Stub allocation failures prove only the application unwind logic;
real-device runs own driver lifecycle evidence.

## 6. Verification, numerics and handoff to another host

### 6.1 Levels of evidence

1. Model-free owners exercise real control/ownership branches with delayed completion and faults.
   They include the cases above and existing CPU owners. A stub may not pretend to measure GPU math.
2. Backend build/loader checks verify an immutable native bundle on each target OS. A missing GPU
   can be reported for discovery, but a requested hardware qualification cannot succeed with N/A.
3. Real `generation` covers Qwen2.5-Coder-7B Q4_K_M and OLMoE-1B-7B Q4_K_M: prefill, multiple
   decode steps, immediate EOG, maximum one and maximum 128, existing context limit, CPU preservation,
   and two repeated invocations. Use the model's checked metadata and current context limits;
   long-context expansion is not smuggled in as GPU enablement.
4. `offload` requires device and host cache misses, constrained budgets, repeated eviction, CPU
   fallback and exact routing/weight identity on the same small real models. Publish reads, copies,
   waits, device placement and peaks, including a counterexample to hidden all-CPU execution.
5. `overlap` requires a trace of actual simultaneous device work and host preparation, plus the
   same output/ownership checks as synchronous mode. No overlap claim from fast submission alone.
6. `coding` compares the real public provider against GPU-enabled llama.cpp on the same host,
   backend, model, prompt/template, bounds and explicit resource profile, plus this runtime's CPU
   and synchronous GPU controls. Verify tasks with the existing fixed validator and sandbox rules.

Cross-backend float arithmetic and MoE routing may differ. Require exact model/quant bytes,
dimensions, prompt ids, masks, positions, expert id/weight correspondence, EOG and sampler semantics.
For numeric qualification, teacher-force a common token prefix through CPU and device arms so one
early token difference cannot change every subsequent comparison. Compare layer outputs, router
logits/top-k boundary and final logits against a same-build reference using frozen absolute/relative
tolerances and near-tie classification. Do not demand CPU/GPU bit equality or reuse the old 87-id
CPU chain as a universal GPU golden. Do not enlarge tolerances after a failing acceptance run.

Before the first implementation's real acceptance run, commit one calibration profile per
model/precision/backend with exact prompts/teacher-forced prefixes, tolerance values, tie rule and
expected sampler behavior. Separate calibration inputs from holdout acceptance prompts. Those
values are presently unmeasured and this plan makes no numerical qualification claim. A device
integration cannot ship as qualified until that profile and its holdout pass exist. Same-backend
repeatability is a separately measured capability; fixed RNG does not prove deterministic GPU math.
Failure to obtain repeatability requires an explicit contract decision before any seeded coding
performance claim; do not silently treat divergent output as reproducible.

### 6.2 User-run qualification package

The future runner accepts the strict profile in §3.5, validates the source, bundle and calibrations
from §§3.4, 3.6 and 3.7, and publishes only the evidence directory from §3.8. The profile carries explicit
model/pack/geometry paths and digests, exact runtime-option contents, native bundle identity,
ordered task/prompt corpus identity and suite deadlines. G1 must add concrete immutable Metal/CUDA
bundle recipes and populated calibration/profile fixtures; it does not revise these schemas merely
to begin implementation.

The package must include one documented command and prerequisite checker for Mac, Linux and WSL2.
It prints actual backend/device/driver/OS/WSL/kernel, host RAM/free memory, VRAM/free memory, storage
filesystem, GPU target architecture, SDK, Align and ggml build identities. The user runs it locally
on the PC and returns the output directory; no remote login, credentials, automatic driver install
or uploading model weights is required. A self-contained replay validates the result on the Mac
without needing that GPU; replay verifies evidence, not the remote device's unobserved behavior.

Evidence must contain ordered case results, complete stdout/stderr, exit/signal, nonfinite counts,
numeric comparisons, actual GPU/CPU operation placement, host/device transfer bytes, peak managed
allocations, RSS/driver memory, timings, model/prompt hashes and source/build identities. Every
timing uses a monotonic clock; synchronize device work at the measured boundary. Record unavailable
device timing as unavailable, never zero. Wall time is authoritative; overlapping category durations
must not be added into a purported wall total.

Build in an immutable source snapshot from the reviewed commit; bind the full compiler/runtime,
helper, shim and transitive source closure, plus loaded plugin and kernel artifacts. Cleanup owns
only invocation-created paths/processes. Preserve diagnostic evidence after failure. Recheck inputs
and source identity after cleanup and before publication; helper/kernel artifacts removed during
cleanup must already have immutable digests and copies in the retained evidence bundle. Publish
exclusively to a new output directory; do not overwrite a previous result. Require the evaluated
commit to remain reachable from the merging head when replay requires repository ancestry.

Unrelated hosted CI remains lightweight. Hardware suites are opt-in named qualifications triggered
by their owning boundary, with no false claim that Linux stubs cover Metal or that CUDA covers HIP.
Use a capability vector to choose supported tests; a required feature missing on a claimed profile
is a failed claim. New profile versions distinguish native Linux and WSL2, GPU architectures and
drivers. AMD remains `functional=unverified` until actual AMD evidence arrives.

### 6.3 Performance decisions and cost ceilings

Correctness enablement G1–G4 can ship opt-in without a speedup claim. Record performance separately;
never remove correctness support because one workload is slower. GPU program completion requires
working generation and offload on Metal and CUDA, implemented Vulkan/HIP consumers, honest
per-device qualification status, and a published coding/performance decision for each available
representative backend. A pending AMD qualification remains open, not silently complete.

For performance qualification use four contemporary pairs in AB/BA/AB/BA order, separately recorded
warm and cold-start conditions, and identical resource/task limits. Do not claim cold disk without
controlling OS cache; label unregulated runs cache-state-uncontrolled. Report load/TTFT, prefill
tokens/s, decode latency/tokens/s, transfer/wait costs and memory as secondary metrics. Primary
metric is time to a passing patch, including load, retries, validation and cleanup at the same
request lifecycle; a GPU-resident session baseline and a reload-every-request candidate are different
lifecycles and must not be mixed without an explicit product comparison.

G5 overlap may be marked recommended for a qualified profile only if all four paired full-request
gains are positive and the median paired saving is at least 5% of the contemporary control median,
without correctness or budget regression. It always remains an explicit `prefetch="overlap"`
selection in schema 1; neither an absent options file nor `off` changes meaning. G6 uses the same 5%
rule for a named primary or secondary performance claim against GPU-enabled llama.cpp. The old CPU
871,174,011-ns attribution floor has no authority here. `not_met` preserves the working explicit
mode and records the limitation; it does not invent a smaller profitable slice or stop unrelated
backend support.

Per-invocation qualification ceilings: G1–G4 `generation`/`offload` 15 minutes per backend/profile;
G5 `overlap` 15 minutes; G6 `coding` 30 minutes. Model-free owners target 5 minutes. Preparation
(dependency build/model conversion) is a separately bounded 60-minute phase, never hidden inside
inference timing or repeated for each case. Each implementation records a preregistered optimization
cost estimate before changing a timed path. No estimate or shipping speedup has been measured in
this design-only change. Timeout is failure with retained evidence, not justification to extend a
budget after looking at results.

## 7. Align prerequisites and native feasibility

The active consumer pin stays unchanged. Sibling evidence checked at
`46664a01352f7a669339c2eae2661d55659b96c2` shows Copy-only closure captures in
`docs/guide/10-closures-and-parallelism.md` and the owned-capture rejection in
`crates/align_sema/src/lib.rs`. Runtime task registration/dispatch is in
`crates/align_runtime/src/lib.rs`. Opaque Move resources already ship at both this sibling and the
consumer pin: `docs/language-spec.md` and `crates/align_driver/tests/resource_ownership.rs` define
and test construction, exactly-once Drop and dependent resource generations. Those implemented
sources supersede the older inference audit's missing-resource statement. Resources remain
non-Send; owning a resource does not authorize background capture or escaped asynchronous borrows.
Classify requirements as follows:

| Requirement | Owner and consequence |
| --- | --- |
| GPU allocation, registry selection, copies/events, op support, library builds | application plus upstream ggml; extend ordinary scalar C FFI, not the Align language |
| Device-specific op/quant missing in ggml | backend gap; explicit hybrid fallback or backend refusal, upstream issue if required; never fake a kernel |
| Fallible host buffer reservation/capacity | existing Request 35; non-blocking bounded synchronous baseline with documented process OOM failure, blocking before promising graceful host OOM recovery |
| Owned/exclusive I/O task capture | existing Request 41; non-blocking for synchronous paths and same-thread device overlap, blocking when an implementation first consumes background Align buffer prefetch |
| Existing raw/sentinel FFI and broader fallible payloads | Request 34 tracks historical payload limitations, not a missing opaque-resource mechanism. G1 uses the actual pinned resource surface and local checked FFI; recheck any newly consumed fallible payload against pinned compiler tests before relying on it. |
| Opaque native owner with exactly-once destruction | already shipped Align package resource; adopt internally in G1 and verify with `gpu-native-owner`. No new language request or public persistent-session API is needed. |
| Windows-native executable/toolchain/OS support | separate Align/platform prerequisite; outside the initial Linux/WSL2 target, not a CUDA limitation |

Before implementation, probe the pinned native backend for each architecture's graph operations,
Q4_K/Q6_K layouts, `mul_mat_id`, alignment/alloc sizes, KV updates, scheduler allocation accounting,
host-pointer visibility, status/abort behavior and events. These are checkpoints within the first
consumer, not standalone infrastructure PRs. Commit the selected immutable backend recipe and
populate the fixed profile/calibration schemas before the first acceptance run. If a required
operation cannot be supported, update this ledger and its exact fallback/acceptance cells first.

## 8. Delivery sequence and completion

| Roadmap / capability | Consumer-complete result | Dependencies and completion |
| --- | --- | --- |
| 80 / G1 GPU generation | Qwen greedy and OLMoE greedy/sampled text through the provider, full weights and KV resident, explicit Metal/CUDA selection; native build/loader, options, ownership and user-run qualifier included | CPU owners plus `generation` on Mac and RTX PC. Add concrete bundle recipes and populated schema-1 profile/calibration fixtures before the first real acceptance run. Device-specific qualification may remain pending while available-host work proceeds; a Metal-only result cannot close CUDA. Backend discovery/FFI alone is not a deliverable. |
| 81 / G2 Bounded GPU offload | same callers generate under device/host budgets that force expert/layer misses, with explicit whole-unit CPU fallback and bounded AlignPack reads | G1; `offload` on Metal/CUDA. Includes transfer/accounting and placement policy; no separate dormant cache/scheduler PR. |
| 82 / G3 Vulkan generation and offload | same provider/options/qualifier on a Vulkan device, same resident/hybrid modes and strict op checks | G2 shared contract; NVIDIA Vulkan is a useful first device, AMD/Intel qualification is recorded separately. Include backend build and consumer in one capability. No claim of WSL Vulkan until exposed and tested. |
| 83 / G4 HIP/ROCm generation and offload | same caller and budgets on ROCm-compatible AMD, including build/loader and reproducible AMD validation instructions | G2; can proceed independently of G3's hardware result. Build/owner work may proceed without AMD hardware; real `generation`/`offload` stay explicitly pending until an AMD contributor/user runs them. |
| 84 / G5 Transfer/compute overlap | bounded same-thread preparation and device pipeline for hybrid requests, with safe slot/event lifetime and measured overlap | G2 per backend; G3/G4 for those backend claims. Synchronous mode remains available on backends without async capability. Request 41 only if scoped background buffer work is selected. `overlap` remains explicit; the 5% gate controls only a profile's recommendation. |
| 85 / G6 GPU coding decision | fixed coding tasks through the public GPU provider compared with GPU-enabled llama.cpp and CPU/synchronous controls; reproducible results on each available backend/host | relevant qualified G1–G5 modes; seed/quality/parity checks and primary result, including honest `not_met`. No CPU-only historical baseline substitution. |

Start with G1. Do not wait for unavailable AMD hardware to implement Metal/CUDA or Vulkan. Do not
mark G4 qualified/complete because it compiles. Measurements
may reveal a necessary backend operation or language prerequisite; record it and continue independent
consumers. R9 speculation and R10 larger-model pressure remain later product directions; GPU
completion is not proof that either is finished.

## 9. Design consistency and current verification

The ledger, matrix and sequence share one explicit device/options contract, two memory budgets,
one invocation lifetime, the same four GPU backends, and one family of device qualification suites.
Hardware names select evidence profiles, not supported-device branches. Strict resident execution,
hybrid fallback and asynchronous overlap are separately observable. Qualification formats are fixed
in §§3.3–3.9; populated numeric calibration/profile fixtures and immutable backend recipes are G1
pre-acceptance checkpoints. No proposed command, numerical tolerance, API or performance outcome is
represented as shipped.

Current verification is documentation consistency, links and `git diff --check`, followed by one
comprehensive design review and the documentation publication preflight. Source tests, compiler
adoption, GPU builds, driver changes and model qualifications are N/A for this planning-only change.
