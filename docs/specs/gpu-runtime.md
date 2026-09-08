# G1 GPU runtime: resident Metal and CUDA generation

Status: implementation checkpoint, 2026-09-08; G1 qualification remains incomplete.

Resident provider generation and qualification infrastructure are implemented on the development
branch. Request 61 shipped and native numeric-stream production passes its byte/state owner.
Request 62 shipped through Align `305926b423da9be1f13b0129a7232626e6704d95`;
observed generation passes its native owner. Final qualifier integration remains pending. Real Metal and CUDA qualification and populated calibration/profile
evidence remain required to close G1. No runtime performance, full numeric qualification or CUDA
correctness claim follows from the current implementation checkpoint.

This is the authoritative public contract for roadmap item 80 (G1). It records delivery order and
non-negotiable principles for items 81–85, but those later consumers must extend the contract,
closure matrix and evidence schema at their own triggered design gates. In particular, schema 1
does not predeclare offload, overlap, performance-comparison or coding-retry formats.

[GPU performance plan](gpu-runtime-performance.md) owns the comparison with llama.cpp, the G1
execution requirements below, the subsequent reusable coding session, and the improvement sequence.
G1 correctness is the first checkpoint in that sequence; it is not the final competitiveness verdict.

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
available validation hosts are an Apple M1 / 16 GiB Mac and the user's RTX 4070 Ti PC running
WSL2 (Pengwin / Debian 13), with reported NVIDIA driver 610.62. The CUDA qualifier must record
the actual host/device/driver observations; the reported configuration is not passing evidence. These device
names are qualification profiles, never product allowlists. Runtime selection queries the named
backend registry and exact device; it does not choose a generic first GPU.

Native Linux and WSL2 are separate evidence environments. WSL2 uses the Linux Align toolchain and
the Windows-provided NVIDIA driver; no native-Windows support is claimed. Follow NVIDIA's WSL
toolkit guidance and keep initial model/build inputs in the Linux filesystem.
G1 declares no vendor-wide minimum driver/SDK range: support attaches only to the exact recorded
bundle, OS, driver and GPU architecture tuple that passes. Evidence from a newer tuple is a new
qualification, not proof for an older or untested tuple.

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
| Configuration API | Add `ProviderConfig.runtime_options_path: str`. Empty preserves CPU behavior. Nonempty is a borrowed UTF-8 path, 1–4096 bytes with no NUL, consumed synchronously only by `provider_runtime.generate`. Network providers require empty. Runtime token-count/info calls carry but never read the path or touch a device; `stream` remains unsupported. Every constructor initializes the field explicitly. The caller retains the path through the call. |
| Generation CLI | Extend `main --provider align-runtime MODEL PACK GEOMETRY PROMPT RESULT [MAX_TOKENS] [CACHE_BUDGET_BYTES]` with the optional terminal pair `--runtime-options OPTIONS.json`. Strip it before existing positional parsing. Duplicate, misplaced or valueless options fail. The maximum-token default remains 64. |
| Options | Strict schema-1 JSON in §3.1, read once into owned bounded data. Missing/unknown/duplicate keys, invalid UTF-8, boolean-as-integer, fraction, overflow, invalid enum and trailing document fail before model/device work. |
| Models and sampling | Exact existing `qwen2` and `olmoe` model, pack, geometry, prompt, context and request checks. Qwen remains greedy. OLMoE retains greedy and temperature 0.3 with every signed-i64 seed. |
| Legacy cache budget | Preserve Qwen-zero / OLMoE-positive `runtime_cache_budget_bytes`. For G1 resident execution the positive OLMoE value remains an admitted host expert-cache ceiling but may allocate zero bytes. It must not exceed `host_budget_bytes`. |
| Result and errors | Existing owned `Result<string, Error>` and CLI schema 2 remain. GPU refusal maps to `Error.Invalid` without partial output. Qualification retains the internal category/stage. |
| Device and bundle | Resolve one exact registry and device from the verified immutable backend bundle. Read the manifest and every artifact through `fs.open_beneath_single_link`; decode the manifest from owned reader bytes. After Request 56 ships, the application staging owner uses `fs.create_private_temp_dir` to create one collision-resistant directory with permissions no broader than `0700`, copies each manifest-bounded artifact into a file created only through `fs.create_exclusive_beneath`, completes and drops its writer, reopens that staged file through `fs.open_beneath_single_link`, and verifies its finalized size/digest before passing only its private absolute path to the native registry. The directory and paths are never exposed to another application branch. Their owner and every loaded library survive through safe native release or transfer together to the process-owned poisoned quarantine until exit; neither the original path nor an ambient search path reaches the loader. Ambiguous, unavailable, incompatible or mismatched identities fail. |
| Ownership | `runtime_device` owns native state through a package-defined opaque Move resource. `runtime_execution` borrows it only inside one request. Explicit fallible synchronization/release precedes success; exactly-once Drop is the safety fallback. No raw handle or device view escapes. |
| Memory | Full model weights, request-capacity KV and reusable compute workspace are device resident. KV capacity is exactly `prompt_token_count + maximum_tokens - 1`, bounded by the model context; it covers every K/V row this request can write without reserving unused model-context tail rows. `host_budget_bytes` and `device_budget_bytes` cover application-managed allocations using checked arithmetic. Metal aliases are charged once physically and reported separately. |
| State | One GPU generation at a time per process. A native atomic guard rejects overlap before device side effects. Safe completion persists no invocation resource. The first successfully initialized bundle pins its manifest digest; a later different bundle fails before loading. If failure after native side effects cannot prove safe unload, the native handles and their staging owner transfer atomically to a process-owned poisoned quarantine, reject every later GPU admission, and remain until process exit; this is the only persisted failure state. CPU calls neither initialize nor replace it. |
| Validation order | Provider/request syntax; bounded options; model/pack/geometry/prompt/context; bundle identity; exact registry/device; op/buffer capability; admission; allocation/upload; prefill/decode; output validation; synchronization/release; success publication. Failure prevents later stages. |
| Qualifier | `scripts/gpu-runtime-qualify --profile PROFILE.json --suite generation --output NEW_DIRECTORY`. Schema 1 accepts only `generation`. It builds reviewed source in isolation and publishes §3.8 evidence. An absent requested backend is FAIL, never passing N/A. |
| Cache identity | Request-local weights bind model/pack/geometry, member/plane, quant layout, bundle/device and request generation. KV additionally binds prompt, position, rope/mask/context and precision. No persisted device cache is introduced. |
| Acceptance | Model-free matrix owners plus real `generation` PASS on Metal and CUDA. Device-specific evidence may be pending while independent implementation proceeds, but Metal cannot close CUDA. |
| Metrics | Correctness, ownership and budget compliance only. Timings are observations. Schema 1 decision is always `unmeasured`; no post-run metric selection can create a performance claim. |

The first real Qwen consumer admission exposed why request capacity is part of the contract rather
than an optimization: its `131072`-row F32 KV footprint was `15032385536` bytes, and its immutable
weights were another `4677120000` bytes. That exceeds both the 16 GiB host and the Metal device's
recommended working set before workspace, even though the admitted request can touch at most 4096
rows. Reserving only those reachable rows preserves generation semantics and makes the declared M1
qualification physically possible.

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

Categories are `CONFIG`, `SOURCE_IDENTITY`, `PREPARATION`, `BUILD`, `BACKEND_UNAVAILABLE`,
`DEVICE_UNAVAILABLE`, `BUNDLE_IDENTITY`, `UNSUPPORTED_CAPABILITY`, `MEMORY_BUDGET`,
`ALLOCATION`, `TRANSFER`, `COMPUTE`, `NONFINITE`, `DEVICE_LOST`, `BUSY`, `PROCESS`,
`PUBLICATION`, and `CLEANUP`. Stages are `options`, `source`, `compiler`, `runtime`,
`candidate_build`, `shim_build`, `cpu_reference_build`, `model`, `device`, `plan`, `allocate`,
`upload`, `prefill`, `decode`, `readback`, `synchronize`, `release`, `case_spawn`, `publication`,
and `qualifier_cleanup`.

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
and rechecked before publication. Symlinks and aliases fail. Mutation before or during the bounded
reader-to-private-stage copy fails identity validation; mutation or replacement of the original
after that copy cannot affect the staged bytes used by the native loader. The private directory and
files are never shared, reopened for writing, or exposed as caller inputs; this ownership boundary,
not the point-in-time link-count check alone, makes the loaded artifact immutable for G1.

Record limits are:

| Record | Canonical limit and arrays |
| --- | --- |
| `GPU_SOURCE_MANIFEST` | 16 MiB; 1–100,000 tracked rows |
| `GPU_RUNTIME_PROFILE` | 256 KiB; exactly 2 models, exactly 1 option, 16–256 cases |
| `GPU_BACKEND_BUNDLE` | 256 KiB; 1–32 GPU architecture entries, 0–128 flags, 1–128 artifacts; each artifact is 1 byte–512 MiB and their checked aggregate is at most 512 MiB |
| `GPU_NUMERIC_CALIBRATION` | 1 MiB; 2–32 cases per model, at most 64 across a profile |
| `GPU_RUNTIME_EVIDENCE` | 8 MiB result; 0–256 cases and 0–8,191 retained files (8,192 including `result.json`) |
| retained data | 4 MiB per log, 512 MiB total directory |

`FileRef` is `path,sha256`; `Identity` is `name,version,sha256`; `ArtifactRef` is
`role,path,bytes,sha256`. `ProducedIdentity` is `state,name,version,sha256`.
`state="available"` requires 1–256 UTF-8 bytes for name, 1–4,096 for version and a digest.
`state="unavailable"` requires three empty strings, is valid only in FAIL evidence, and means its
production step did not complete.
Each checked-in backend recipe defines whether an `Identity.sha256` covers one executable/file or
a canonical toolchain probe transcript and fixes the exact probe command and byte framing. Build
and qualification recompute it before use. Evidence replay verifies the attested identity and
produced artifact digests; schema 1 does not claim a bit-reproducible SDK/toolchain closure.
Qualification host admission resolves installed tools once, preserves executable aliases, and runs
the recipe's exact version probes through the bounded closed-environment process owner. It requires
an exact match of all four bundle toolchain identities before constructing preparation commands.
macOS selects Clang, Clang++, ar, ranlib and ld through the admitted `xcrun --find`, binds the
`macosx` SDK root and `SDKSettings.json`, and confirms the root selection again after the probes.
Linux/WSL2 select cc, c++, ar, ranlib and ld, bind `/` with resolved `/etc/os-release` metadata, and
probe ldd and nvcc as the CUDA recipe specifies. CMake and Ninja are explicit installed inputs on
both hosts. Lookup uses the caller's executable search path only during admission; `CC`, `CXX`,
`CUDACXX` and build/search environment variables do not select qualifier tools or survive into a
child. Missing tools, profile/host mismatch, malformed output, timeout, SDK drift, or any identity
mismatch fail admission. These read-only admission probes attest host inputs; the five recorded
preparation commands still own all helper/compiler/runtime/shim/candidate/reference production.
`gpu-qualification-cli` owns fixture probe agreement and each admission refusal;
`gpu-cpu-reference-build` corroborates admission against the real recipe probe framing.
The generated application also consumes installed OpenSSL and Zstandard static support archives.
Host admission runs the admitted `pkg-config --variable=libdir openssl` and
`pkg-config --variable=libdir libzstd` with the same closed environment, then binds the bounded
single-link `libcrypto.a`, `libssl.a` and `libzstd.a` files in those directories. Compiler
materialization copies and digest-verifies them beneath its private work root before native-driver
construction. The driver replaces only the corresponding exact `-lcrypto`, `-lssl` and `-lzstd`
arguments with those private archives; SSL additionally resolves against the same private crypto
archive after its callers. System zlib and platform support libraries remain SDK inputs. There is
no dynamic OpenSSL/Zstandard search path, fetch, or fallback for a missing archive. These are host
toolchain inputs, not a new persisted schema or an Align capability request. The model-free driver
owner may omit all three archives when its caller has no such capability. Partial sets fail before
construction. The CLI owner covers discovery and malformed/missing inputs; the explicit-driver
owner covers private copying and refusal; the real CPU-reference owner runs SHA-256 and verifies
that the executable has no dynamic ggml/OpenSSL/Zstandard dependency. Publication ownership and the
shared preparation timeout cover failure/early-exit cleanup of all copied support files.
Validation order is framing; version/kind; exact keys/types/bounds; tagged presence; references;
digests; semantic invariants; aggregate and directory closure.
Regular-file admission opens with no-follow and nonblocking flags before descriptor type checks;
an unconnected FIFO cannot stall before validation or consume an unbounded preparation interval.
`gpu-special-file-admission` covers retained input read/digest, source replay, staged backends,
executable identity, produced artifacts, numeric streams and kit copying with bounded FIFO/socket/directory/
symlink refusals and regular-file controls. It is a focused owner, not new aggregate membership.

### 3.4 Source manifest schema 1

`GPU_SOURCE_MANIFEST` key order is
`schema_version,artifact_kind,source_kind,repository,object_format,commit,commit_object_sha256,tree,files`.
Constants are 1 and `GPU_SOURCE_MANIFEST`; `source_kind` is `align-llm|ggml`. The first requires
repository `https://github.com/sanohiro/align-llm.git`; the second requires
`https://github.com/ggml-org/llama.cpp.git`. Object format is `sha1|sha256`.

File rows are `path,mode,bytes,git_oid,sha256`, sorted by raw UTF-8 path bytes. Modes are
`100644|100755|120000`; submodules and other modes fail. Distinct paths may share content. Evidence
stores each distinct blob once as regular `source/<source_kind>/blobs/<sha256>`, including symlink
target bytes without following them, and retains the raw commit body as
`source/<source_kind>/commit`.

Replay recomputes blob Git objects, every nested tree and the commit OID, and requires exact
manifest/blob closure. Snapshot identity is SHA-256 of ASCII `GPU_SOURCE_SNAPSHOT`, NUL,
`source_kind`, NUL, canonical manifest bytes, then each row's raw 32-byte SHA-256. This permits
cross-host replay without trusting local ancestry. The evaluated align-llm commit must still be
reachable from the exact merging head at publication. The bundle's ggml commit and source-manifest
digest must equal the `ggml` record, whose commit/tree/blob objects are retained and replayed by the
same rules; neither repository may borrow the other's manifest.

The bundle producer disables Git replacements and grafts, applies fixed no-fsmonitor/no-hook Git
options to every source query, and rejects a nonempty replacement-ref namespace before status or
worktree reads. It recomputes the captured commit, tree and blob closure before materializing the
private build tree or invoking CMake. Repository-local command configuration and a replacement tree
therefore cannot execute or become build input before source admission.

The shared capture owner also accepts `align-llm` with an explicit full commit identity; ggml
defaults remain the fixed recipe commit and repository. Capture admits the clean root and exact
origin/HEAD before reading, addresses commit/tree queries by that fixed identity, verifies every
working blob against Git, then rechecks root/origin/HEAD/cleanliness before returning. Linked
worktrees use Git queries rather than assuming `.git` is a directory. `gpu-source-capture` owns
both source kinds, SHA-1/SHA-256, linked-worktree equivalence, dirty/ignored/wrong-origin/commit
refusals and mutation during capture; `gpu-source-replay` independently owns retained replay.
The shared staging writer validates the complete captured closure before acquiring a new private
directory, writes blobs as regular files (including symlink-target bytes), and replays the result.
An occupied path is preserved; write/replay failure removes only the newly acquired directory.
`gpu-source-capture` also owns these acquisition and cleanup branches. The caller owns final
publication; the backend recipe continues to recheck source replay immediately before publication.

### 3.5 Qualification profile schema 1

Top-level key order is
`schema_version,artifact_kind,profile_id,platform,source,bundle_manifest,models,runtime_options,cases,deadlines_ns`.
Constants are 1 and `GPU_RUNTIME_PROFILE`; platform is `macos|linux|wsl2`; source is
`commit,manifest_sha256` and must resolve a `source_kind=align-llm` manifest; bundle manifest is a
`FileRef`.

The internal profile assembler consumes frozen source, bundle, calibration and runtime-option
records plus explicit paths, cache budgets and deadlines. It derives record hashes, model bindings
and the complete ordered CPU/GPU repeat expansion through the existing record owner, then validates
the assembled profile before returning canonical bytes. It does not choose tolerances or invent
expected token/output values. `gpu-profile-assembly` compares its result byte-for-byte with the
independent normative vector and owns normalization and malformed/cross-record refusal cases.

The profile file's retained parent directory is the qualification input root. Every profile path
resolves beneath that root without following a symlink component. The two complete source closures
are fixed at `source/align-llm/{manifest.json,commit,blobs/<sha256>}` and
`source/ggml/{manifest.json,commit,blobs/<sha256>}`. `bundle_manifest.path`, every model, pack,
geometry and calibration path, and every source-closure file is a single-link regular file. The
qualifier reads each bounded record through its opened descriptor, replays both exact Git closures,
streams and rechecks the three model-input digests per model, and validates every cross-record
identity before creating the evidence staging directory or touching a device. Unreferenced input
files are ignored and never copied or executed.

Models contain exactly `qwen2` then `olmoe`. A row is
`model_id,model_path,model_sha256,pack_path,pack_sha256,geometry_path,geometry_sha256,calibration_path,calibration_sha256,runtime_cache_budget_bytes`.
Every path/digest binds a regular input. Its calibration binds the same model, backend and bundle.
The cache budget is zero for Qwen and positive for OLMoE, and cannot exceed the selected runtime
option's `host_budget_bytes`.
Calibration case IDs are unique across both documents and total at most 64.

Runtime-option rows are
`option_id,schema_version,backend,device,backend_bundle,placement,host_budget_bytes,device_budget_bytes,prefetch`.
There is exactly one row. Its last eight fields have §3.1 semantics; bundle path resolves to the declared manifest directory.
Every row names the bundle's backend and one exact device from that registry. Metal profiles require
`platform=macos`; CUDA requires `linux|wsl2`. The empty option sentinel below is the only exception
to the identifier grammar.


The CPU-reference preparation command runs the checked-in
`scripts/gpu_cpu_reference/build.cmake` through an explicitly bound CMake executable. Its absolute
inputs are the admitted ggml tree, Align entry and compiler, shim source, native project, parent C
driver, C/C++ compilers, archiver, ranlib, linker, Ninja and SDK; its new private output root is
invocation-owned. It configures and builds with two workers, within the shared preparation deadline.
The native project fixes static ggml/base/CPU and shim archives, `GGML_BACKEND_DL=OFF`, CPU on, all
GPU/BLAS/Accelerate/OpenMP/remote backends off, native CPU tuning/repacking/KleidiAI off, and
floating-point contraction off. It disables Git/tool-cache discovery rather than querying another
checkout. A generated native C driver passes the exact CPU archives to the parent driver when
linking the release Align reference. Intermediate archives and the generated driver are private
build products; the resulting CPU-reference executable contains them and is the retained produced
identity. No separate CPU shared library or backend plugin is a runtime dependency.

`ALIGN_GGML_STATIC_CPU_ONLY` is set only for this reference's shim. Its registry opener uses the
statically registered CPU backend and performs no plugin-directory or environment search. The
ordinary application shim keeps its existing registry behavior. The owning
`gpu-cpu-reference-build` qualification builds the real pinned source, runs an Align caller against
the CPU registry, verifies the lack of dynamic ggml dependencies, and places a constructor-bearing
plugin beside the executable to prove that it is not loaded. This is build/registry evidence;
model numeric and generation coverage remains owned by the complete generation suite. Construction,
invalid inputs and failed native/Align subcommands are owned by the same helper; every nonzero
subcommand aborts the CPU-reference step and its existing preparation/publication owner retains the
bounded failed-command streams. The helper accepts no shell strings, ambient build flags or network
fetch. SDK content reproducibility and performance claims remain N/A for the reasons above.


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
`case_order_sha256` in evidence is SHA-256 of ASCII `GPU_CASE_ORDER`, NUL, then canonical compact
JSON bytes of this exact `cases` array without a final LF.

`deadlines_ns` is `preparation,generation`: positive and respectively at most
3,600,000,000,000 and 900,000,000,000 ns. No extension is allowed after observing results.
The runner validates every byte and cross-reference before device or output-directory side effects.

### 3.6 Backend bundle schema 1

`GPU_BACKEND_BUNDLE` key order is
`schema_version,artifact_kind,bundle_id,backend,ggml,target,toolchain,build_flags,artifacts`.
Constants are 1 and `GPU_BACKEND_BUNDLE`; `bundle_id` is SHA-256 of canonical bytes with that
field replaced by 64 zeroes. Backend is `metal|cuda`. `ggml` is
`commit,source_manifest_sha256,version` and binds an immutable complete checkout through the
`source_kind=ggml` manifest from §3.4. The bundle input includes that manifest, raw commit and every
distinct content-addressed blob; qualification copies them into evidence before temporary cleanup.

`target` is `os,arch,gpu_architectures`; OS is `macos|linux`, arch is
`aarch64|x86_64`, and architectures are nonempty compiled targets. `toolchain` is
`c_compiler,cxx_compiler,sdk,toolkit`, each an `Identity`. An inapplicable component is
`name="none",version="none"` with SHA-256 of empty bytes.

Build flags are the exact ordered argv suffix after fixed tool arguments, never a shell string.
Artifacts are `role,path,bytes,sha256`, sorted by role/path with roles
`shared_library|backend_plugin|kernel_binary|shader_library|metadata`. The array covers every
loadable file. The original manifest path is never a load path. Runtime loading is restricted to
the private staged paths whose finalized size and digest match the manifest; their owners outlive
the registry and loaded library.

The first successful native initialization pins bundle ID and manifest digest. Same-bundle
sequential requests reuse it. Different bundles fail before load. Failure after any registry/plugin
side effect poisons GPU admission. When safe unload cannot be proved, the native process state takes
ownership of the loaded handles and complete staging tree before the invocation returns failure and
keeps both until exit; invocation cleanup must neither unload nor remove that transferred tree.

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

Comparison treats each finite binary32 value as its exact real number. For CPU reference `r`, GPU
candidate `c`, absolute tolerance `A`, relative tolerance `R`, and binary32 minimum-normal
`M=2^-126`, define `d=abs(c-r)`, `s=max(abs(r),abs(c),M)`. The scalar passes iff
`d <= max(A,R*s)`, with exact-real multiplication/comparison; signed zero therefore passes and
subnormals use `M` as the scale floor. NaN or infinity on either side fails `NONFINITE` before this
predicate. Evidence maximum absolute error is the maximum `d`; maximum relative error is the
maximum `d/s`; each is rounded once to binary64 round-to-nearest-ties-even for its recorded bits.
`mismatch_count` counts scalar positions failing this predicate.
`gmake gpu-numeric-compare` is the focused scalar owner. It checks streamed maxima and decisions
against an independent exact-rational oracle, including exponent extremes, cancellation, signed
zero, subnormals, nonfinites and tolerance boundaries. Its binary64 comparison filter resolves
ambiguous threshold equality and potential relative maxima exactly; recorded error bits never use
a double-rounded relative quotient.

For OLMoE routing, form the reference boundary group from all expert IDs whose reference score is
within the exact-real near-tie tolerance of the kth selected reference score. If the kth-to-first-
excluded gap exceeds that tolerance, selected IDs and order must match exactly. Otherwise both
selected sets must contain the same exact IDs outside the boundary group, may differ only within
that group, and every corresponding weight still passes the scalar predicate above.
`near_tie_count` counts token/layer routing boundaries admitted by this second rule, not individual
experts. No GPU-derived score may enlarge the boundary group.
Selected IDs must be unique, in range and a descending top-k of their own score vector; exact
score ties may retain either order. Within an admitted boundary group, compare selected weights by
their ordered selected slot, while the ordered subsequence of IDs outside that group remains
identical. An ID/order failure is a routing failure, separate from scalar `mismatch_count`.
Only a boundary whose scalar and selection comparisons pass increments `near_tie_count`.
`gpu-numeric-compare` owns exact boundary membership, substitutions, outside-group order, malformed
selections, weight tolerance and refusal to enlarge a group with GPU scores.

Cases are
`case_id,role,prompt_utf8,prompt_sha256,prompt_token_ids,teacher_forced_token_ids,sampler_mode,temperature_micros,seed,maximum_tokens,expected_token_ids,expected_output_utf8,expected_output_sha256`.
Each `case_id` matches `[a-z0-9][a-z0-9._-]{0,48}`, reserving 15 characters for the longest derived
`.gpu_resident.1` suffix. There is at least one `calibration` and one `holdout`. Prompts are at most 65,536 bytes and at
most 4,096 nonnegative i32 token IDs. Teacher-forced IDs are nonempty. Greedy uses zero
temperature/seed; seeded uses 300000 micros and any signed-i64 seed. Maximum tokens is 1–128.
Expected IDs are the nonempty same-build CPU sampling result, including the terminal EOG
when sampled. Immediate EOG therefore has one expected ID and empty decoded output text.
Expected output is the exact generated UTF-8 byte sequence for those IDs. Its digest is SHA-256 of
those bytes with no added LF; both CPU repeats and both GPU repeats reproduce the bytes and digest.

The Python case planner reads geometry as a bounded strict JSON object in the existing R1
format, which does not require a terminal LF. GPU record LF framing is not imposed on model IR.
The native provider still checks the original complete geometry bytes against its own frontend.
The CLI owner uses no-LF geometry and preserves its original digest when constructing all cases.

Relocatable model inputs preserve the geometry document's recorded display path. The shared R7/R8
provider derives every geometry field from the actual GGUF table using that recorded path, requires
complete byte equality, and independently verifies the actual model/pack source identity. It never
opens the recorded path. The provider trace owner executes unchanged geometry/pack bytes with
copied models and refuses scalar drift; no persisted schema or calibration hash rewrite is needed.

The private `runtime_calibration_seed` driver obtains CPU expectations before GPU holdout execution.
Its positional inputs are model, pack, geometry, stream root/name, architecture, prompt and cache
budget bytes (a nonnegative JSON integer); it uses
an empty system prompt, greedy sampling and two maximum output tokens. The ordinary CPU owner
requires zero cache budget for Qwen and enough expert slots for OLMoE; fixture-sized cache budgets
are not assumed sufficient for real models. The output is the owning production `TraceResult` with actual
prompt/sample IDs and UTF-8 text, plus its completed production-only numeric stream (16 MiB cap).
It admits the actual model architecture and cannot select GPU options. It does not freeze a
calibration, infer tolerances, compare devices or declare qualification PASS. The provider trace
owner compares its CPU output and IDs with the independently executed native case for both models
and immediate-EOG fixtures. Schema/cache identity and public CLI are N/A: this is an internal
expectation-acquisition tool consumed when assembling the frozen records.

Tolerances and expected outputs are frozen before holdout execution and cannot be enlarged after a
failure. Teacher forcing compares common layer/router/final-logit positions so an early generated
token difference cannot hide later numeric drift. Both repeated GPU executions must match the
sampler expectation; fixed RNG alone does not establish device repeatability.

### 3.8 Evidence schema 1 and directory

The qualifier creates a sibling staging directory and exclusively renames it to a new destination.
Malformed input or occupied destination creates no output. After validation, a functional failure,
build failure, crash, signal, timeout, missing result or cleanup failure publishes a bounded FAIL
bundle when the parent remains able to do so.

The directory contains only `result.json`, canonical profile/bundle/calibration manifests,
`source/align-llm/manifest.json`, `source/align-llm/commit`,
`source/align-llm/blobs/<sha256>`, `source/ggml/manifest.json`, `source/ggml/commit`,
`source/ggml/blobs/<sha256>`, `artifacts/<sha256>`, and
`logs/<three-digit-ordinal>.stdout|stderr`. Models/packs/geometry are identified but not copied.
Files are single-link regular files. Logs record original count/digest and retain their first 4 MiB;
truncation fails the case. When a started preparation command fails, its complete bounded streams
are required at `logs/<three-digit preparation ordinal>.stdout|stderr`; no earlier successful
preparation stream is retained. Preparation has no case row, so these names cannot collide with a
case log in the same evidence bundle.

`GPU_RUNTIME_EVIDENCE` top-level key order is
`schema_version,artifact_kind,status,suite,profile_id,source,host,bundle,inputs,preparation_commands,files,cases,aggregate,cleanup,failure,elapsed_ns`.
Constants are 1, `GPU_RUNTIME_EVIDENCE`, and `generation`; status is `PASS|FAIL`.

- `source` is
  `commit,source_manifest_sha256,source_snapshot_sha256,align_revision,align_compiler,align_runtime,qualifier,candidate,shim,cpu_reference`.
  The first three bind the `source_kind=align-llm` record and snapshot. The last six are
  `ProducedIdentity`. Each records availability only after that preparation/build
  step completed; failure before or during a step uses the unavailable tag. PASS requires all.
- `host` is
  `platform,os_version,kernel,arch,wsl,cpu,logical_cpus,host_total_bytes,host_free_bytes,backend,device_state,registry_device,device_description,driver,gpu_architecture,device_total_bytes,device_free_bytes`.
  Baseline host fields are always present. `device_state="available"` requires the four device
  strings nonempty, positive total bytes, and free bytes between zero and total. `device_state="unavailable"` requires four
  empty strings and two zeroes, is valid only in FAIL evidence, and truthfully represents discovery
  failure before a device identity exists.
  Host facts come from bounded installed-system probes under the existing closed process owner:
  macOS uses `sysctl`, `sw_vers` and `vm_stat`; Linux/WSL use bounded `/etc/os-release`,
  `/proc/cpuinfo` reads and system page counts. Free host bytes mean currently free pages,
  excluding reclaimable caches. These admission probes share the preparation deadline and are
  not additional build commands. Device enrichment shares the generation deadline. CUDA queries
  `nvidia-smi` for PCI bus ID, name, driver version and compute capability, matches the native
  device's PCI ID uniquely (normalizing a zero-extended domain), and refuses malformed or
  ambiguous rows. The observed architecture must occur in the admitted bundle target. The
  `gpu-host-observation` focused owner covers real local host facts, reordered CUDA enumeration,
  duplicate/mismatched PCI IDs, malformed probes and changing native device identity. Host
  observation failure cannot fabricate baseline facts or a passing device observation.
  Final source rechecks use descriptor-relative, no-follow directory traversal and bounded
  single-link file reads. Exact file and directory closure, executable modes, symlink payloads,
  content digests and stable directory identities must remain valid after child execution.
  `gpu-source-materialization` owns post-execution FIFO, extra-directory, changed-content and
  replaced-root refusals as well as initial construction.
- `bundle` is
  `manifest_sha256,bundle_id,ggml_source_manifest_sha256,ggml_source_snapshot_sha256,loaded_artifact_sha256s`;
  its source values match §3.6 and replay §3.4, and loaded hashes are a unique manifest subset in
  actual load order.
- `inputs` is `profile_sha256,models,calibration_ids,case_order_sha256`; model rows contain
  `model_id,model_sha256,pack_sha256,geometry_sha256`.
- `preparation_commands` contains 0–16 `Command` objects in the fixed actual order
  compiler materialization, runtime materialization, shim build, candidate build, then CPU-reference
  build. The shim must exist before Align links the candidate. FAIL permits the
  constructed/executed prefix; PASS requires the runner-derived complete sequence and all
  successful identities. An unstarted preparation failure (including exhaustion of the shared
  preparation deadline between steps) names the next step in `failure.stage`, leaves its produced
  identity unavailable, and retains only the successful command prefix with no logs for that step.
  A started failure additionally retains its constructed command and both bounded logs. Earlier
  identities must be available and later identities unavailable in both cases; neither has cases.
  `gpu_qualification_run` owns this distinction and one monotonic deadline for all five steps;
  no step starts after it expires and each started step receives only the remaining duration.
  The `gpu-preparation-evidence` owner exercises every unstarted slot, deadline exhaustion,
  a reduced remaining child timeout, the successful sequence, and refusal to resume after failure.
  Command factories may bind a completed earlier output only when their own slot is reached;
  construction failure or an already-expired deadline is an unstarted failure with no invented
  command/log. Compiler materialization includes native-driver compilation in the same owned
  process group before it publishes the copied compiler. Its checked-in Python helper receives
  explicit compiler, linker, SDK and source/output paths, uses the four-entry environment, and
  leaves descendant capture and the shared deadline to the outer owner. It does not start a nested
  process group or fetch/build Align. The prepared managed compiler is a prerequisite.
  `gpu-preparation-evidence` covers lazy binding, skipped later factories and factory failure;
  `gpu-explicit-driver` covers the real grouped bootstrap and refusal to publish after its failure.
  Before native bootstrap, that helper reuses `align-toolchain.verify` with a supplied bounded
  executor: the input must be `target/release/alignc` beneath the exact clean managed source
  revision, both compiler/runtime outputs must exist, and the compiler version probe must pass.
  Git uses the admitted executable with replacements, filesystem monitors, hooks and external diff
  disabled; all verification subprocesses remain in the same outer group and environment.
  `scripts/test-align-toolchain` continues to own ordinary managed verification semantics;
  `gpu-explicit-driver` owns the grouped executor, revision refusal and real managed adoption.
- `files` rows are
  `role,path,bytes,sha256,original_bytes,original_sha256,truncated`, sorted by path and covering
  every retained file other than `result.json`. Roles are
  `profile|bundle_manifest|calibration|align_source_manifest|align_source_commit|align_source_blob|ggml_source_manifest|ggml_source_commit|ggml_source_blob|helper|shim|backend_artifact|stdout|stderr`.

Case rows are
`ordinal,case_id,calibration_case_id,role,execution,repeat_index,model_id,option_id,terminal,category,stage,exit_code,signal,command,output_sha256,token_ids,nonfinite_count,numeric,placement,transfers,memory,timing,stdout_path,stderr_path`.
The internal case sequence consumes the complete derived command schedule lazily under one
generation deadline. Its case consumer retains each spawned command's logs and validates the
profile-bound output/numeric records before allowing the next factory. A failed child is still
delivered for termination/log evidence; construction or spawn refusal has no invented child/log.
The first process/validation/deadline failure fixes a terminal prefix, including elapsed validation
time, and the sequence cannot resume. It does not replace case/evidence validation or construct a
successful numeric result. `gpu-case-sequence` owns real child execution, ordered validation,
unstarted failures, nonzero exits, consumer refusal/exception, timeout cleanup and shared-deadline
exhaustion during validation. The integrating case consumer owns the profile identities and the
retained results; the sequence itself does not accumulate all successful case logs in memory.
Ordinals and identity fields equal the profile. Terminal is
`PASS|FAIL|TIMEOUT|CRASH|SIGNAL|MISSING`; exit code/signal are integer or null. Missing output uses
an empty digest. `PASS` uses empty category/stage, exit code zero, null signal, a constructed command
and a nonempty output digest. Every other terminal uses a nonempty category/stage. `FAIL` preserves the actual
integer exit code when a child completed (including zero when subsequent numeric/output validation
failed), or null when no child started, and has a null signal; `TIMEOUT` and `MISSING` use null
exit/signal; `CRASH` uses a nonzero exit and null signal; `SIGNAL` uses a null exit and positive
signal. A spawned row always names its command and two log paths. Output digest is nonempty only
when a complete validated output existed before the later failure. Numeric is
`compared,expected_scalar_count,actual_scalar_count,expected_layer_count,actual_layer_count,expected_router_boundary_count,actual_router_boundary_count,expected_final_logit_count,actual_final_logit_count,max_absolute_f64_bits,max_relative_f64_bits,near_tie_count,mismatch_count`.
False requires zero bit patterns/counts and true permits an exact zero error result. CPU rows require
`compared=false`; passing GPU rows compare against the adjacent same-repeat CPU row and require
true. A GPU case that fails before a complete comparison reports false with zero numeric fields,
while separately retaining any observed nonfinite count. A failed completed comparison retains
true and its actual counts/errors. No failed or missing stream is presented as a comparison. The
expected counts are independently derived from model geometry and case token widths. PASS requires
every actual count to equal its expected count, positive scalar/layer/final-logit counts, zero Qwen
router boundaries and positive OLMoE router boundaries.
Scalar/final-logit counts include diagnostic generation-reproduction and teacher-forced comparisons
and production logits already read at every sampling position, including an EOG decision. These are separate
comparison positions even when their token prefixes coincide. Layer/router counts describe only
diagnostic replay. Errors, nonfinites and mismatches aggregate all three traversals; none may hide
another's failure. Production logits compare to the adjacent CPU run at the same actual token prefix;
divergent generated IDs fail the existing output contract rather than comparing unrelated positions.

`placement` is
`expected_model_operations,gpu_model_operations,cpu_model_operations,expected_layers,gpu_layers,cpu_layers,expected_experts,gpu_experts,cpu_experts,expected_weights_device_bytes,minimum_weights_device_bytes,expected_kv_device_bytes,minimum_kv_device_bytes,expected_weight_upload_count,weight_upload_count,weight_upload_bytes`.
Counts cover only model graph operations from embedding through output projection; tokenizer,
prompt construction, sampling, EOG control and text decode are explicitly outside them. The
reviewed production graph trace derives the three expected counts from exact model geometry,
prompt width, output selection and generated steps; all diagnostic work is excluded.
For the pinned decomposed graphs, an operation is a materializing graph node: NONE, VIEW, RESHAPE,
PERMUTE, resident-KV CPY and SET_ROWS are excluded. CONT, zero-extent PAD and the two highest-layer
GET_ROWS remain counted. This is a graph-operation count, not a GPU kernel-launch count.
The independent projection is `(24+P)*L+6` Qwen prefill and `27*L+6` per Qwen decode;
OLMoE uses `(29+K+P)*L+6` prefill and `(32+K)*L+6` per decode, where `L` is layer count and
`K` selected experts. `P` is three when the context-clipped 256-position attention bucket is
wider than the prompt (K CONT, K PAD and V PAD), otherwise zero. Indexed resident writes
replace both decode CONCAT operations without adding counted model operations. The constant six is embedding/head plus two highest-layer selection nodes.
Native execution counts only nodes in successfully executed graphs, never the requested table size.
Each layer is observed at its down projection by matching the node's first source to original
weight ordinal `12*(layer+1)` in the immutable `3+12*L` layout. For OLMoE MUL_MAT_ID down
projections, the checked product of output selected-expert and token-column extents counts actual
expert invocations. Expected layers are `L*positions`; expected expert invocations are
`K*((L-1)*prompt_tokens+1+L*(positions-1))` (zero for Qwen). Both counters use actual graph
membership and are compared independently; no host routing readback is added.
A passing GPU row requires each expected count equal its
GPU count and every CPU count zero. Expected weights are the exact immutable model footprint;
expected KV is the request-capacity footprint derived from geometry and the case's admitted prompt
token count and maximum-token bound. The minimum observed live
payload at every boundary from completed upload/binding through final decode equals each
expectation; allocator padding and reservations are charged separately to managed memory.
Weight upload count counts first device bindings of distinct tensor identities and equals the
independently derived tensor count. CUDA upload bytes equal the weight footprint. Metal may bind
verified UMA aliases once with zero copied bytes; `weight_upload_bytes` records actual copies,
and retained binding identities prove full coverage without counting an alias as a transfer.
Rebinding, streaming and early release fail. Expected operations/layers and both
resident byte counts are positive, including prompt KV for an immediate-EOG case. Qwen has zero
expected/GPU experts; OLMoE counts every selected expert application and must have a positive exact
match.
The exit code and signal fields are strict integers or null; booleans cannot impersonate zero or
one. Functional failure after a zero-exit child retains its command/logs and validated output
digest when available, with the real failure category/stage. `validate_case` owns this distinction;
`gpu-result-replay` covers a zero-exit comparison failure and rejects boolean or unspawned exit
claims, while the native case sequence owner covers stopping before the next child. This fixes a
schema-1 validation gap during G1 integration without adding fields or changing successful records.

`transfers` is
`host_to_device_bytes,device_to_host_bytes,unexpected_device_to_host_bytes,wait_count`. The
unexpected value counts bytes outside declared final-logit and compact-routing readbacks and must
be zero for PASS. Production resident generation does not read routing decisions back to the host;
the compact-routing allowance applies only to diagnostic replay below. `memory` is
`managed_host_peak_bytes,application_host_reserved_bytes,managed_device_peak_bytes,uma_alias_peak_bytes,rss_peak_bytes,driver_peak_bytes`.
`application_host_reserved_bytes` is the conservative separate capacity reservation; it is not
an observed peak. Native peak plus that reservation must fit the declared host cap.
Managed peaks describe the production device owner's admitted native allocation domain, as do
production placement and transfer counters; they are not whole-process heap peaks. CPU rows have
no allocation in that GPU-managed domain and report zero there. Diagnostic invocations independently
enforce the same managed caps, and whole-child RSS includes production, diagnostics, language-runtime
storage and envelope handling. The current loader copies into owned device buffers and has no
retained host-weight UMA alias, so alias bytes are zero even on Metal. The driver value is integer
or null when unavailable. Explicit native synchronize calls own `wait_count`; it does not claim
to count internal driver stalls. `timing` is
`wall_ns,load_ns,ttft_ns,prefill_ns,decode_ns,device_ns,transfer_ns,wait_ns`; wall is positive for a
started case, and other fields are nonnegative integer or null when unavailable. Overlapping
observations are not summed into wall.

The process owner collects per-child `wait4` resource usage when it reaps the exact started PID.
`OwnedCommandResult.rss_peak_bytes` normalizes macOS bytes and Linux/WSL2 KiB to bytes. The value
is the kernel's child lifetime maximum, including any waited-descendant usage accounted by that
kernel; it is not a summed process-group peak. Native case children do not launch descendants.
RSS is not sampled from `/proc` or a cumulative previous-child maximum. The measured child uses
the existing `Popen` spawn and pipes with public `poll`/`wait` overrides; one lock owns wait/reap,
timeout/signal cleanup retains the measured result, and no environment or command wrapper changes.
Injected alternate spawn implementations may report unavailable (`None`); that is never coerced to
a measured zero. The process owner tests positive success/failure/timeout samples, repeated waits,
and a large child followed by a small child to detect cumulative-maximum contamination. Existing
capture/interruption/descendant cleanup owners remain required for this boundary.

`Command` is `kind,argv,environment,sha256`, where kind is
`compiler_materialize|runtime_materialize|candidate_build|shim_build|cpu_reference_build|case`.
The runner resolves every executable by its verified
absolute path, starts from an empty environment, and inserts exactly `HOME=<owned-empty-home>`,
`LC_ALL=C`, `TMPDIR=<owned-temp>`, and `TZ=UTC`, in that canonical name order. No ambient name
survives: in particular `PATH`, compiler/linker flags and search paths, cache variables and
`CUDA_VISIBLE_DEVICES` are unset. Compiler/SDK inputs are absolute verified argv; runtime artifacts
load the selected plugin from its invocation-owned private staged absolute path. The already linked
ggml core is an explicit immutable executable prerequisite, verified as described below; loader
search variables are unnecessary. These fixed sources override rather than merge with the parent
environment.

Evidence retains the complete logical argv and `NAME=value` environment arrays for every
preparation and case command. Machine-local input paths become
`<logical-id>:sha256:<digest>` and invocation-owned directory/output paths become
`<logical-id>:owned`; secrets are not accepted as qualifier inputs. A path may also be the entire
value of one CMake definition: `-DNAME=<logical-path>`, `-DNAME:PATH=<logical-path>`, or
`-DNAME:FILEPATH=<logical-path>`, with `NAME` matching `[A-Z][A-Z0-9_]*`. The definition prefix
is literal and retained unchanged; the runner substitutes and rechecks exactly one mapped path
value. No suffix or multi-path expansion is accepted. `gpu-command-environment` owns acceptance,
malformed prefixes/values, unchanged literal flags, mapping mismatch and digest refusal before
spawn. Host SDK directories are the sole non-file `:sha256:` mapping: the build resolver
supplies a resolved absolute directory and a bounded single-link metadata file within it. The
logical digest covers that metadata file. `gpu_qualifier_process.ToolchainDirectory` captures the
root's device/inode/mode/mtime/ctime and verifies those fields plus the metadata digest before each
preparation spawn; relative roots, metadata outside the root, changed roots/metadata, and SDK
bindings in case commands fail before spawn. The bundle's SDK probe identity is checked separately
by host toolchain admission. The preparation sequence also rechecks the same bound SDK immediately
before spawning a compiler whose selected C driver supplies the SDK indirectly. This attests the
selected installed SDK, not a snapshot of every SDK
file; complete SDK content closure remains N/A under schema 1's explicit non-reproducible-toolchain
limit. Installed compiler/build-tool executables may preserve an absolute alias path (for example,
`clang++` or `ranlib`) whose basename selects tool behavior. `ToolchainExecutable` binds that
path to its resolved regular executable and byte digest, permits the host installation's hard
links, and rechecks the same resolved target, digest and execute permission before preparation
spawn. It is refused for case commands. The ordinary single-link/no-follow rule still owns
application model, source, bundle, produced-helper and output paths; host tool admission is not a
way to relax those inputs. `gpu-command-environment` covers alias behavior, target replacement,
byte drift, non-executable input, case refusal and unprefixed executable selection.
The native preparation driver appends only its selected private library root, SDK and linker
directory, preserves caller argument boundaries, and executes its admitted compiler with the same
four-entry environment. Its generated bytes bind those absolute selections. Preparation commands
also carry the compiler/linker executable dependencies for a pre-spawn digest/alias recheck when
those tools are reached indirectly through Align or the CPU-reference driver. Case commands reject
such dependencies. `gpu-command-environment` owns dependency drift and case refusal;
`gpu-explicit-driver` and `gpu-cpu-reference-build` own the real candidate/reference links and
environment preservation. Construction refuses occupied outputs and invalid private roots; failed
bootstrap compilation leaves no usable driver, and the invocation owns all generated files.
`gpu-command-environment` covers SDK construction, mutation/replacement, case refusal and valid
CMake substitution. The hash preimage is ASCII `GPU_QUALIFIER_COMMAND`, NUL, then kind as a
little-endian u64 UTF-8 byte length plus bytes, little-endian u32 argv count, each argv with the same
u64 framing, little-endian u32 environment count, then each retained environment entry with the
same u64 framing. A constructed command has nonempty
argv, exactly four environment entries and a digest. If construction was never reached all three
trailing fields are empty arrays/empty string and `kind=""`; that sentinel is valid only on a
nonpassing case. Replay recomputes the digest and the
runner rechecks each logical path/digest mapping immediately before spawn.

`aggregate` is
`case_count,passed_count,failed_count,managed_host_peak_bytes,managed_device_peak_bytes,decision`.
Pass/fail counts partition cases into terminal PASS versus every other terminal, peaks are exact
maxima or zero for no case, and decision is always
`unmeasured`. Schema 1 has no performance comparison. `cleanup` is
`descendants_before,descendants_after,owned_paths_removed,invocation_state_safe,source_unchanged,inputs_unchanged`.
`failure` is `category,stage,case_ordinal,detail`, with empty/-1 PASS values and bounded redacted
FAIL detail. Elapsed time is positive, starts before invocation admission, and ends immediately
before final publication is called, after evidence preparation, source/input rechecks and invocation
cleanup. Final evidence serialization, filesystem publication and replay are outside that value;
schema 1 makes no end-to-end performance claim.

PASS requires every profile case present and passing, both model holdout sets passing on GPU,
nonzero GPU operations, exact expected output bytes, complete numeric comparison coverage,
weights/KV resident within budgets, one retained device binding per weight tensor, no undeclared readback, exact
source/input rechecks and safe cleanup. FAIL may contain zero or a profile-order prefix of case rows; missing suffix rows are
represented by the top-level failure rather than fabricated timings. The CLI returns zero only for
PASS. The final CLI binds its launcher and every loaded project Python helper to the admitted
Align source snapshot before preparation and rechecks them before publication. Its private native
entrypoint is `src/runtime_case.align`. `gpu-execution-evidence` owns the native/device/failure-prefix
assembly, and the final CLI owner covers failure publication/replay and occupied-output preservation.
The first failure is authoritative; subsequent cleanup/source failures retain their own false cleanup
flags without replacing it. Failure before complete baseline host identity cannot publish an invented
host record and returns nonzero without evidence.

### 3.9 Canonical positive vectors

The following eight lines are the normative schema-1 positive fixture. Their self-identities, Git
object IDs, content hashes, cross-references, array minima and derived 16-case expansion are real,
not placeholders. The final evidence row is a valid pre-case device-discovery failure: it retains
both source closures and every produced artifact while using the unavailable device/CPU-reference
tags. The pure record validator accepts every line; the evidence-directory replay owner additionally
materializes the declared `files` byte map during G1 implementation.

Decode plus canonical encode reproduces each line with one final LF byte-for-byte; reordered input
canonicalizes to the same line. Duplicate keys, uppercase digests, BOM, missing document boundary
and a second document fail. `case_order_sha256` is SHA-256 of ASCII `GPU_CASE_ORDER`, NUL, then the
canonical compact JSON bytes of the profile's `cases` array without a final LF.

```json
{"schema_version":1,"backend":"metal","device":"fixture-device","backend_bundle":"bundle","placement":"resident","host_budget_bytes":1,"device_budget_bytes":1,"prefetch":"off"}
{"schema_version":1,"artifact_kind":"GPU_SOURCE_MANIFEST","source_kind":"align-llm","repository":"https://github.com/sanohiro/align-llm.git","object_format":"sha1","commit":"a23d777430cbc1dfc357d425e29f7715354147d2","commit_object_sha256":"b5d1e58bf66655a5bc612de17cefb55f0cbce22342d8ad52451550a2517b5aeb","tree":"7c7003088534356ae2b7c5eab9f91755214dc776","files":[{"path":"runner.py","mode":"100644","bytes":7,"git_oid":"c33ca062091e8f3ffeed1ee95dd272122529d24c","sha256":"ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e"}]}
{"schema_version":1,"artifact_kind":"GPU_SOURCE_MANIFEST","source_kind":"ggml","repository":"https://github.com/ggml-org/llama.cpp.git","object_format":"sha1","commit":"3a34663d19739a78907425252e3685128f9388c4","commit_object_sha256":"fc31069ce39dffe5f276b9fd80621c0947b4634e8e9b0986b7a5f9b932756460","tree":"3098a23e2ae55378d0dfddd09730da71134ac61b","files":[{"path":"ggml.c","mode":"100644","bytes":5,"git_oid":"1af38368de4ebeb7c776e937699ac5d7dfae5cbd","sha256":"e1df5b4f4e7884f07e600b7e61a71fb3171661050b3281cb675bc06ac644f9d2"}]}
{"schema_version":1,"artifact_kind":"GPU_BACKEND_BUNDLE","bundle_id":"1f6f864bfabb4e0f42155494a56738e0ebb9457b4ee6bb70b28aa395a16021cc","backend":"metal","ggml":{"commit":"3a34663d19739a78907425252e3685128f9388c4","source_manifest_sha256":"a609bc11fe9ff2c7c945f3b45ce9d63148d86d28d3c1a4548d6fdf784d0885da","version":"fixture"},"target":{"os":"macos","arch":"aarch64","gpu_architectures":["apple_m1"]},"toolchain":{"c_compiler":{"name":"cc","version":"fixture","sha256":"a3960f48bb1f93e212cd1ea623b9b58a50d93a1e876f0172b8c07c34824a50f1"},"cxx_compiler":{"name":"cxx","version":"fixture","sha256":"ce83332611f3b5e97402adc3b1ed19ea4768953e4b050070cdbffb1e1cd07c19"},"sdk":{"name":"macos","version":"fixture","sha256":"26e5d2e798113f713318a98981b2df55f52894eddc33fbbaf64deabeeb6706ec"},"toolkit":{"name":"none","version":"none","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}},"build_flags":[],"artifacts":[{"role":"shared_library","path":"libggml.dylib","bytes":7,"sha256":"ef17b7d320f2acc023f2018dab381827ba22f9d01b6c4c97894e1bbfe4928313"}]}
{"schema_version":1,"artifact_kind":"GPU_NUMERIC_CALIBRATION","calibration_id":"620bcd00a373ecdcc1c10438a7c591875dd191b56eb6a28f704e121056ce3b95","backend":"metal","bundle_id":"1f6f864bfabb4e0f42155494a56738e0ebb9457b4ee6bb70b28aa395a16021cc","model":{"model_id":"qwen2","model_sha256":"66c2cd691eaa072e668e6e08895c3d3ac87850e45a6246acb526c818ffa94ce7","pack_sha256":"df1a391299a7dbf3e69914a05012e5c550f13bf6a91152c612c03871b38add05","geometry_sha256":"2254151e52d7a63d4a515fbe4a7b544b71abcbd26df82e53279dcc61121a09bb","quantization":"Q4_K_M"},"precision":"f32","comparison":{"absolute_tolerance_f32_bits":"00000000","relative_tolerance_f32_bits":"00000000","near_tie_tolerance_f32_bits":"00000000","nonfinite":"reject","reference":"cpu-same-build","layer_scope":"all","topk_rule":"same-ordered-ids-or-declared-near-tie"},"cases":[{"case_id":"qwen2-cal","role":"calibration","prompt_utf8":"q-cal","prompt_sha256":"5e07c2bbc17366d7980ffbc28c96b7846f4bf34f41bfe7e45ede7bc375c867a5","prompt_token_ids":[1],"teacher_forced_token_ids":[2],"sampler_mode":"greedy","temperature_micros":0,"seed":0,"maximum_tokens":1,"expected_token_ids":[3],"expected_output_utf8":"q-cal-output","expected_output_sha256":"df9fe78f8602563c7b0a80c56f8c0e7ea3e99dc4b1df9724a471bcd13e429519"},{"case_id":"qwen2-hold","role":"holdout","prompt_utf8":"q-hold","prompt_sha256":"c5b7cdb722b3529ec42eaff080f93231436ac76937b237c1f922167df1d28dea","prompt_token_ids":[1],"teacher_forced_token_ids":[2],"sampler_mode":"greedy","temperature_micros":0,"seed":0,"maximum_tokens":1,"expected_token_ids":[4],"expected_output_utf8":"q-hold-output","expected_output_sha256":"701360c457a04fcb310b7537e5d0385481c2313ef8b99d7694395b30cd339000"}]}
{"schema_version":1,"artifact_kind":"GPU_NUMERIC_CALIBRATION","calibration_id":"b81010e3d96a12ab67e4e4d35291223734927a138bb4dee36ca466f8aad67957","backend":"metal","bundle_id":"1f6f864bfabb4e0f42155494a56738e0ebb9457b4ee6bb70b28aa395a16021cc","model":{"model_id":"olmoe","model_sha256":"6e8fcf187877b71a470da2bfcfdf78483ec486bc84fb2a1b3a24fcd2f16d9c51","pack_sha256":"7de77ae32bf2f41bdbf53f9884a953bf6dc691af305800530f15abf1b4704313","geometry_sha256":"0011b32e89ed81df8b5845741d07753a51ce2b6f522844ab43cfd66b18af36b7","quantization":"Q4_K_M"},"precision":"f32","comparison":{"absolute_tolerance_f32_bits":"00000000","relative_tolerance_f32_bits":"00000000","near_tie_tolerance_f32_bits":"00000000","nonfinite":"reject","reference":"cpu-same-build","layer_scope":"all","topk_rule":"same-ordered-ids-or-declared-near-tie"},"cases":[{"case_id":"olmoe-cal","role":"calibration","prompt_utf8":"o-cal","prompt_sha256":"8a3902d95d85f8cbf4244e9cf4d30e1013e68305baed192320e49ea47478d87c","prompt_token_ids":[1],"teacher_forced_token_ids":[2],"sampler_mode":"greedy","temperature_micros":0,"seed":0,"maximum_tokens":1,"expected_token_ids":[5],"expected_output_utf8":"o-cal-output","expected_output_sha256":"c03ea8f905883ec7493022fdf39fe10b2620fffc012264c368a7748abc0f0296"},{"case_id":"olmoe-hold","role":"holdout","prompt_utf8":"o-hold","prompt_sha256":"d816cd73b31f913b6b5ee77b12f22da83ad9be55029c67851b77e8361d038ef6","prompt_token_ids":[1],"teacher_forced_token_ids":[2],"sampler_mode":"seeded","temperature_micros":300000,"seed":7,"maximum_tokens":1,"expected_token_ids":[6],"expected_output_utf8":"o-hold-output","expected_output_sha256":"fbc8d29077f8060c01aebffcccc57ef5e01977eafd3f6e4b820c503ce0a8c4bf"}]}
{"schema_version":1,"artifact_kind":"GPU_RUNTIME_PROFILE","profile_id":"metal-fixture","platform":"macos","source":{"commit":"a23d777430cbc1dfc357d425e29f7715354147d2","manifest_sha256":"380710b45bc9c6a33d452f3378f69bef555447934966f76d30fafdc5cb5b3dec"},"bundle_manifest":{"path":"bundle/manifest.json","sha256":"4b1456b8815e40b6211ef95193e86bfe1b4f2d4311d648674e70c15836104876"},"models":[{"model_id":"qwen2","model_path":"inputs/qwen2.model","model_sha256":"66c2cd691eaa072e668e6e08895c3d3ac87850e45a6246acb526c818ffa94ce7","pack_path":"inputs/qwen2.pack","pack_sha256":"df1a391299a7dbf3e69914a05012e5c550f13bf6a91152c612c03871b38add05","geometry_path":"inputs/qwen2.geometry","geometry_sha256":"2254151e52d7a63d4a515fbe4a7b544b71abcbd26df82e53279dcc61121a09bb","calibration_path":"calibration/qwen2.json","calibration_sha256":"925a0b3569a67edd15136d4d274c74f3c772b6a9ad79fee81c3e7adc2a9f89cd","runtime_cache_budget_bytes":0},{"model_id":"olmoe","model_path":"inputs/olmoe.model","model_sha256":"6e8fcf187877b71a470da2bfcfdf78483ec486bc84fb2a1b3a24fcd2f16d9c51","pack_path":"inputs/olmoe.pack","pack_sha256":"7de77ae32bf2f41bdbf53f9884a953bf6dc691af305800530f15abf1b4704313","geometry_path":"inputs/olmoe.geometry","geometry_sha256":"0011b32e89ed81df8b5845741d07753a51ce2b6f522844ab43cfd66b18af36b7","calibration_path":"calibration/olmoe.json","calibration_sha256":"97110e5fa52b0d14f05cf7a97b2f805c14112b3f8f225c41b5a82271045b9fe8","runtime_cache_budget_bytes":1}],"runtime_options":[{"option_id":"resident","schema_version":1,"backend":"metal","device":"fixture-device","backend_bundle":"bundle","placement":"resident","host_budget_bytes":1,"device_budget_bytes":1,"prefetch":"off"}],"cases":[{"case_id":"qwen2-cal.cpu.0","calibration_case_id":"qwen2-cal","role":"calibration","execution":"cpu","repeat_index":0,"model_id":"qwen2","option_id":"","maximum_tokens":1},{"case_id":"qwen2-cal.gpu_resident.0","calibration_case_id":"qwen2-cal","role":"calibration","execution":"gpu_resident","repeat_index":0,"model_id":"qwen2","option_id":"resident","maximum_tokens":1},{"case_id":"qwen2-cal.cpu.1","calibration_case_id":"qwen2-cal","role":"calibration","execution":"cpu","repeat_index":1,"model_id":"qwen2","option_id":"","maximum_tokens":1},{"case_id":"qwen2-cal.gpu_resident.1","calibration_case_id":"qwen2-cal","role":"calibration","execution":"gpu_resident","repeat_index":1,"model_id":"qwen2","option_id":"resident","maximum_tokens":1},{"case_id":"qwen2-hold.cpu.0","calibration_case_id":"qwen2-hold","role":"holdout","execution":"cpu","repeat_index":0,"model_id":"qwen2","option_id":"","maximum_tokens":1},{"case_id":"qwen2-hold.gpu_resident.0","calibration_case_id":"qwen2-hold","role":"holdout","execution":"gpu_resident","repeat_index":0,"model_id":"qwen2","option_id":"resident","maximum_tokens":1},{"case_id":"qwen2-hold.cpu.1","calibration_case_id":"qwen2-hold","role":"holdout","execution":"cpu","repeat_index":1,"model_id":"qwen2","option_id":"","maximum_tokens":1},{"case_id":"qwen2-hold.gpu_resident.1","calibration_case_id":"qwen2-hold","role":"holdout","execution":"gpu_resident","repeat_index":1,"model_id":"qwen2","option_id":"resident","maximum_tokens":1},{"case_id":"olmoe-cal.cpu.0","calibration_case_id":"olmoe-cal","role":"calibration","execution":"cpu","repeat_index":0,"model_id":"olmoe","option_id":"","maximum_tokens":1},{"case_id":"olmoe-cal.gpu_resident.0","calibration_case_id":"olmoe-cal","role":"calibration","execution":"gpu_resident","repeat_index":0,"model_id":"olmoe","option_id":"resident","maximum_tokens":1},{"case_id":"olmoe-cal.cpu.1","calibration_case_id":"olmoe-cal","role":"calibration","execution":"cpu","repeat_index":1,"model_id":"olmoe","option_id":"","maximum_tokens":1},{"case_id":"olmoe-cal.gpu_resident.1","calibration_case_id":"olmoe-cal","role":"calibration","execution":"gpu_resident","repeat_index":1,"model_id":"olmoe","option_id":"resident","maximum_tokens":1},{"case_id":"olmoe-hold.cpu.0","calibration_case_id":"olmoe-hold","role":"holdout","execution":"cpu","repeat_index":0,"model_id":"olmoe","option_id":"","maximum_tokens":1},{"case_id":"olmoe-hold.gpu_resident.0","calibration_case_id":"olmoe-hold","role":"holdout","execution":"gpu_resident","repeat_index":0,"model_id":"olmoe","option_id":"resident","maximum_tokens":1},{"case_id":"olmoe-hold.cpu.1","calibration_case_id":"olmoe-hold","role":"holdout","execution":"cpu","repeat_index":1,"model_id":"olmoe","option_id":"","maximum_tokens":1},{"case_id":"olmoe-hold.gpu_resident.1","calibration_case_id":"olmoe-hold","role":"holdout","execution":"gpu_resident","repeat_index":1,"model_id":"olmoe","option_id":"resident","maximum_tokens":1}],"deadlines_ns":{"preparation":1,"generation":1}}
{"schema_version":1,"artifact_kind":"GPU_RUNTIME_EVIDENCE","status":"FAIL","suite":"generation","profile_id":"metal-fixture","source":{"commit":"a23d777430cbc1dfc357d425e29f7715354147d2","source_manifest_sha256":"380710b45bc9c6a33d452f3378f69bef555447934966f76d30fafdc5cb5b3dec","source_snapshot_sha256":"d131a621e907b4b038d32e4f9a6fe330ad8e7651cec34c9430f18a9c74172b91","align_revision":"8cefc803d5c7f883a8db5b67250ed4ed069b43a4","align_compiler":{"state":"available","name":"cc","version":"fixture","sha256":"a3960f48bb1f93e212cd1ea623b9b58a50d93a1e876f0172b8c07c34824a50f1"},"align_runtime":{"state":"available","name":"runtime","version":"fixture","sha256":"fae9d8f386d67956867dedef7c89476199a4a25ee9ffe13560a6bfae7ae6c407"},"qualifier":{"state":"available","name":"gpu-runtime-qualify","version":"fixture","sha256":"ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e"},"candidate":{"state":"available","name":"candidate","version":"fixture","sha256":"1e81270f1a47dce22a2e4985250c74b2e3374443734f1492b03ea2cd2af4ec48"},"shim":{"state":"available","name":"shim","version":"fixture","sha256":"b7c748b4a4d1c37826a11b7bd04068a24094832a969948118b75e48a2dfd23e6"},"cpu_reference":{"state":"unavailable","name":"","version":"","sha256":""}},"host":{"platform":"macos","os_version":"fixture","kernel":"fixture","arch":"aarch64","wsl":false,"cpu":"fixture","logical_cpus":1,"host_total_bytes":1,"host_free_bytes":1,"backend":"metal","device_state":"unavailable","registry_device":"","device_description":"","driver":"","gpu_architecture":"","device_total_bytes":0,"device_free_bytes":0},"bundle":{"manifest_sha256":"4b1456b8815e40b6211ef95193e86bfe1b4f2d4311d648674e70c15836104876","bundle_id":"1f6f864bfabb4e0f42155494a56738e0ebb9457b4ee6bb70b28aa395a16021cc","ggml_source_manifest_sha256":"a609bc11fe9ff2c7c945f3b45ce9d63148d86d28d3c1a4548d6fdf784d0885da","ggml_source_snapshot_sha256":"f3e5d1e376f924d1626485a18138293d4d551ba848c9d008ebeed07a3f703721","loaded_artifact_sha256s":[]},"inputs":{"profile_sha256":"eda8947c479fe4c94881956c3645cf7837013101fd0c99c13c3ce2ddbf9a34dc","models":[{"model_id":"qwen2","model_sha256":"66c2cd691eaa072e668e6e08895c3d3ac87850e45a6246acb526c818ffa94ce7","pack_sha256":"df1a391299a7dbf3e69914a05012e5c550f13bf6a91152c612c03871b38add05","geometry_sha256":"2254151e52d7a63d4a515fbe4a7b544b71abcbd26df82e53279dcc61121a09bb"},{"model_id":"olmoe","model_sha256":"6e8fcf187877b71a470da2bfcfdf78483ec486bc84fb2a1b3a24fcd2f16d9c51","pack_sha256":"7de77ae32bf2f41bdbf53f9884a953bf6dc691af305800530f15abf1b4704313","geometry_sha256":"0011b32e89ed81df8b5845741d07753a51ce2b6f522844ab43cfd66b18af36b7"}],"calibration_ids":["620bcd00a373ecdcc1c10438a7c591875dd191b56eb6a28f704e121056ce3b95","b81010e3d96a12ab67e4e4d35291223734927a138bb4dee36ca466f8aad67957"],"case_order_sha256":"02c1c7a03dbfb99f9cacc1ae481651e210f2e7c6a276f3f002046a8d1eb997cc"},"preparation_commands":[{"kind":"compiler_materialize","argv":["<qualifier>:sha256:ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e","ensure-compiler"],"environment":["HOME=<home>:owned","LC_ALL=C","TMPDIR=<tmp>:owned","TZ=UTC"],"sha256":"322c13a24484df7ca0dc30ab0ba56bd276bd715d6e1b679380e2a54e598eb715"},{"kind":"runtime_materialize","argv":["<qualifier>:sha256:ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e","ensure-runtime"],"environment":["HOME=<home>:owned","LC_ALL=C","TMPDIR=<tmp>:owned","TZ=UTC"],"sha256":"605851f712d5a995df46aa8809f6a0927e6605faa1f7312b434990315e845835"},{"kind":"shim_build","argv":["<cc>:sha256:a3960f48bb1f93e212cd1ea623b9b58a50d93a1e876f0172b8c07c34824a50f1","build-shim","<shim>:sha256:b7c748b4a4d1c37826a11b7bd04068a24094832a969948118b75e48a2dfd23e6"],"environment":["HOME=<home>:owned","LC_ALL=C","TMPDIR=<tmp>:owned","TZ=UTC"],"sha256":"c12003636ed6ad72675586c17665e2e747912d85151bfb6426d34a21818cdb90"},{"kind":"candidate_build","argv":["<align-compiler>:sha256:a3960f48bb1f93e212cd1ea623b9b58a50d93a1e876f0172b8c07c34824a50f1","build-candidate","<align-runtime>:sha256:fae9d8f386d67956867dedef7c89476199a4a25ee9ffe13560a6bfae7ae6c407"],"environment":["HOME=<home>:owned","LC_ALL=C","TMPDIR=<tmp>:owned","TZ=UTC"],"sha256":"9a13126f939591a688e44192dc45848d758438328e8f14086d7e9283fb4f9a21"}],"files":[{"role":"helper","path":"artifacts/1e81270f1a47dce22a2e4985250c74b2e3374443734f1492b03ea2cd2af4ec48","bytes":10,"sha256":"1e81270f1a47dce22a2e4985250c74b2e3374443734f1492b03ea2cd2af4ec48","original_bytes":10,"original_sha256":"1e81270f1a47dce22a2e4985250c74b2e3374443734f1492b03ea2cd2af4ec48","truncated":false},{"role":"helper","path":"artifacts/a3960f48bb1f93e212cd1ea623b9b58a50d93a1e876f0172b8c07c34824a50f1","bytes":3,"sha256":"a3960f48bb1f93e212cd1ea623b9b58a50d93a1e876f0172b8c07c34824a50f1","original_bytes":3,"original_sha256":"a3960f48bb1f93e212cd1ea623b9b58a50d93a1e876f0172b8c07c34824a50f1","truncated":false},{"role":"helper","path":"artifacts/ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e","bytes":7,"sha256":"ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e","original_bytes":7,"original_sha256":"ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e","truncated":false},{"role":"shim","path":"artifacts/b7c748b4a4d1c37826a11b7bd04068a24094832a969948118b75e48a2dfd23e6","bytes":5,"sha256":"b7c748b4a4d1c37826a11b7bd04068a24094832a969948118b75e48a2dfd23e6","original_bytes":5,"original_sha256":"b7c748b4a4d1c37826a11b7bd04068a24094832a969948118b75e48a2dfd23e6","truncated":false},{"role":"backend_artifact","path":"artifacts/ef17b7d320f2acc023f2018dab381827ba22f9d01b6c4c97894e1bbfe4928313","bytes":7,"sha256":"ef17b7d320f2acc023f2018dab381827ba22f9d01b6c4c97894e1bbfe4928313","original_bytes":7,"original_sha256":"ef17b7d320f2acc023f2018dab381827ba22f9d01b6c4c97894e1bbfe4928313","truncated":false},{"role":"helper","path":"artifacts/fae9d8f386d67956867dedef7c89476199a4a25ee9ffe13560a6bfae7ae6c407","bytes":8,"sha256":"fae9d8f386d67956867dedef7c89476199a4a25ee9ffe13560a6bfae7ae6c407","original_bytes":8,"original_sha256":"fae9d8f386d67956867dedef7c89476199a4a25ee9ffe13560a6bfae7ae6c407","truncated":false},{"role":"bundle_manifest","path":"bundle-manifest.json","bytes":1069,"sha256":"4b1456b8815e40b6211ef95193e86bfe1b4f2d4311d648674e70c15836104876","original_bytes":1069,"original_sha256":"4b1456b8815e40b6211ef95193e86bfe1b4f2d4311d648674e70c15836104876","truncated":false},{"role":"calibration","path":"calibration/olmoe.json","bytes":1705,"sha256":"97110e5fa52b0d14f05cf7a97b2f805c14112b3f8f225c41b5a82271045b9fe8","original_bytes":1705,"original_sha256":"97110e5fa52b0d14f05cf7a97b2f805c14112b3f8f225c41b5a82271045b9fe8","truncated":false},{"role":"calibration","path":"calibration/qwen2.json","bytes":1700,"sha256":"925a0b3569a67edd15136d4d274c74f3c772b6a9ad79fee81c3e7adc2a9f89cd","original_bytes":1700,"original_sha256":"925a0b3569a67edd15136d4d274c74f3c772b6a9ad79fee81c3e7adc2a9f89cd","truncated":false},{"role":"profile","path":"profile.json","bytes":4706,"sha256":"eda8947c479fe4c94881956c3645cf7837013101fd0c99c13c3ce2ddbf9a34dc","original_bytes":4706,"original_sha256":"eda8947c479fe4c94881956c3645cf7837013101fd0c99c13c3ce2ddbf9a34dc","truncated":false},{"role":"align_source_blob","path":"source/align-llm/blobs/ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e","bytes":7,"sha256":"ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e","original_bytes":7,"original_sha256":"ab49f3eb142e8e18c94fa79d2017f57b6141b1c4cdc042f1a0d0e3de5297090e","truncated":false},{"role":"align_source_commit","path":"source/align-llm/commit","bytes":166,"sha256":"b5d1e58bf66655a5bc612de17cefb55f0cbce22342d8ad52451550a2517b5aeb","original_bytes":166,"original_sha256":"b5d1e58bf66655a5bc612de17cefb55f0cbce22342d8ad52451550a2517b5aeb","truncated":false},{"role":"align_source_manifest","path":"source/align-llm/manifest.json","bytes":543,"sha256":"380710b45bc9c6a33d452f3378f69bef555447934966f76d30fafdc5cb5b3dec","original_bytes":543,"original_sha256":"380710b45bc9c6a33d452f3378f69bef555447934966f76d30fafdc5cb5b3dec","truncated":false},{"role":"ggml_source_blob","path":"source/ggml/blobs/e1df5b4f4e7884f07e600b7e61a71fb3171661050b3281cb675bc06ac644f9d2","bytes":5,"sha256":"e1df5b4f4e7884f07e600b7e61a71fb3171661050b3281cb675bc06ac644f9d2","original_bytes":5,"original_sha256":"e1df5b4f4e7884f07e600b7e61a71fb3171661050b3281cb675bc06ac644f9d2","truncated":false},{"role":"ggml_source_commit","path":"source/ggml/commit","bytes":161,"sha256":"fc31069ce39dffe5f276b9fd80621c0947b4634e8e9b0986b7a5f9b932756460","original_bytes":161,"original_sha256":"fc31069ce39dffe5f276b9fd80621c0947b4634e8e9b0986b7a5f9b932756460","truncated":false},{"role":"ggml_source_manifest","path":"source/ggml/manifest.json","bytes":535,"sha256":"a609bc11fe9ff2c7c945f3b45ce9d63148d86d28d3c1a4548d6fdf784d0885da","original_bytes":535,"original_sha256":"a609bc11fe9ff2c7c945f3b45ce9d63148d86d28d3c1a4548d6fdf784d0885da","truncated":false}],"cases":[],"aggregate":{"case_count":0,"passed_count":0,"failed_count":0,"managed_host_peak_bytes":0,"managed_device_peak_bytes":0,"decision":"unmeasured"},"cleanup":{"descendants_before":0,"descendants_after":0,"owned_paths_removed":true,"invocation_state_safe":true,"source_unchanged":true,"inputs_unchanged":true},"failure":{"category":"DEVICE_UNAVAILABLE","stage":"device","case_ordinal":-1,"detail":"fixture"},"elapsed_ns":1}
```

### 3.10 Private numeric stream version 1

The invocation-owned native case input is canonical UTF-8 JSON plus one LF, capped at 4 MiB.
`runtime_case` owns its private schema 1 (`artifact_kind="GPU_RUNTIME_CASE_INPUT"`) with exact
field order `schema_version,artifact_kind,model_id,model_path,pack_path,geometry_path,options_path,
cache_budget_bytes,prompt_utf8,maximum_tokens,temperature_micros,seed,expected_prompt_ids,
expected_token_ids,expected_output_utf8,forced_ids,stream_root,stream_name,stream_limit`.
Paths name already admitted invocation inputs; empty options selects the static CPU reference.
Model ID is `qwen2|olmoe` and must match the GGUF architecture. Cache, sampler and token bounds are
the ordinary provider's, with a signed-i64 seed meaningful only for temperature 300000 micros;
greedy uses zero temperature and zero seed. Prompt and expected output each cap at 1 MiB;
prompt IDs are 1–2048, expected sampled IDs including terminal EOG are 1–maximum_tokens, and forced
IDs are 1–4096. IDs are nonnegative i32 and native generators enforce vocabulary/context bounds.
The numeric file uses §3.10's root-relative exclusive creation and independently derived byte ceiling.
Canonical re-encoding rejects extra/duplicate keys, alternate scalar spelling and missing fields.

The helper executes production, validates exact frozen prompt IDs, sampled IDs and output bytes,
then requires independent diagnostic generation to reproduce those values before forced replay.
It finishes the numeric stream only after all three succeed. Each provider call owns its snapshot,
KV and device; all share one scratch writer and the parent's generation deadline. Success prints
one `GPU_RUNTIME_CASE_OUTPUT` schema-1 record plus LF, ordered as `schema_version,artifact_kind,
production,stream_bytes,stream_records`, where production is the provider's `TraceResult` including
its raw observation. This envelope is private scratch output, not schema-1 qualification evidence.
Failures return nonzero and leave no success envelope or finished stream. Admission/source errors
before a writer exists produce no envelope. Once the writer exists, failure prints one private
`GPU_RUNTIME_CASE_FAILURE` schema-1 record ordered `schema_version,artifact_kind,phase,category,stage,
stream_nonfinite_count,stream_bytes,stream_records`. Phase is `production|production_binding|
reproduction|reproduction_binding|forced|forced_binding|finish`; counters report only observations
made by that stream, preserving nonfinite/write progress without claiming complete traversal.
The parent process/case owner classifies the failure and retains bounded logs. No production
placement, peak/minimum memory or timing claim is invented by this helper.

| Native case closure | Implementation | Required owner evidence |
| --- | --- | --- |
| Canonical construction / malformed input | `runtime_case.load` / validation | native case owner unknown/missing/duplicate/bounded-field refusals |
| Source/model and frozen prompt/output binding | shared provider plus exact case comparison | native case owner identity/prompt/token/text mismatch |
| Three successful trajectories / EOG | independent provider calls sharing one stream | native case owner CPU/GPU independent traversal and immediate EOG |
| Reproduction / forced / write failure | propagate before finishing/printing success | native case owner changed expected output, short stream ceiling and forced GPU nonfinite readback |
| Cleanup / early exit | native owners Drop, parent scratch ownership and process deadline | native case owner refusal followed by fresh success; existing process cleanup owner |

`gpu_qualification_native` owns parent construction and validation of these private records. It
builds the input from frozen calibration/geometry and explicit physical paths, deriving the stream
ceiling independently. Success admission checks exact result/production/observation keys and types,
output UTF-8 digest and exact frozen text/IDs, raw GPU reads versus vocabulary/positions, execution
counts, and bundle/device identity. It consumes every expected numeric frame in bounded chunks,
rejects nonfinites and invalid routing/selected-weight data, and retains the verified stream digest
before a paired GPU command may start. Failure admission validates the bounded phase/progress
record without calling it successful numeric evidence. Its native fixture owner exercises actual
child output plus mutated envelope/stream/binding refusals. The existing `CaseSequence` remains
the sole process/deadline owner; this module does not publish evidence or infer placement/peaks.

`gpu_qualification_native_sequence` binds a complete list of native plans to `CaseSequence`.
Adjacent plans must be CPU then GPU for identical model/calibration/repeat identity, frozen input
projection and comparison policy. Factories exclusively create each case's private scratch directory
and canonical input only when their turn arrives. Executable SHA-256 and owned input paths use the
existing closed command environment; no ambient library or credential environment is added.
The CPU stream is completely validated and hashed before the GPU factory runs. GPU comparison
uses that retained digest and independent traversal, and numeric mismatch stops the sequence while
preserving the child's real zero exit code. The consumer receives process logs, validated native
output/raw observations and comparison results or failure progress before approving the next case.
Paired numeric scratch is removed after comparison; early exits remove only acquired case roots.
It does not construct final placement/memory evidence. The native fixture owner covers all 16
CPU/GPU/repeat executions, bounded environment, exact paired results, retained-CPU mutation refusal,
occupied scratch preservation and no next child after a post-process validation refusal; the
existing process owner remains authoritative for timeout/descendant cleanup.

`gpu_qualification_case_records` assembles each profile-bound row from its independently derived
native plan and observed sequence outcome. It retains actual process status, output/IDs only when
native success was validated, completed numeric comparison or the explicit uncompared zero record,
production placement/transfers and native allocation observations, and per-child RSS/wall time.
Unavailable phase timings and driver memory are null. CPU rows have no GPU-managed placement or
transfer observations; their whole-child resource use remains visible in RSS. Unstarted rows have
no command, logs or invented process result. A missing RSS observation or unexpected descendant
prevents PASS. Logs retain complete-stream digests and bounded bytes at distinct case paths.
Construction validates the resulting row through the shared schema owner. This is case evidence
assembly; final source/input/cleanup checks and publication still own the qualification verdict.
Its owner covers CPU/GPU rows, zero-exit numeric failure, pre-comparison nonfinite failure,
unstarted cases, missing measurements, real log identities and profile/plan mismatch refusal.
`CaseRecords` collects consecutive rows/logs and refuses continuation after a failed row. Finishing
against the exact `CaseSequence` appends an unstarted terminal row when no child was constructed,
or turns a previously accepted row into zero-exit PROCESS failure when the shared deadline expired
during validation. It never fabricates a missing suffix. The caller may provide the fresh sequence
state to native execution so acquired-root cleanup failure cannot discard its process checkpoint.
The record owner covers ordered completion, first-failure prefix, validation-deadline demotion,
unstarted suffix failure and refusal of repeated/out-of-order consumption or finish.

`gpu_qualification_cli.native_plans` connects a completed five-step preparation to that sequence.
It rechecks admitted inputs, reads the retained geometry, and binds each exact profile expansion
row to its frozen calibration case and prepared executable digest. The candidate is
`work/runtime_case`; the independently built CPU reference is `work/cpu-reference/runtime_case`.
Both must match the successful preparation identities and application commit. A private runtime
option record preserves every frozen option except removing the profile-only `option_id` and
resolving `backend_bundle` to the admitted staged bundle. CPU cases have no GPU options. Case roots
are distinct direct work children and remain absent until their lazy factory runs. Invocation
cleanup owns the option file, including construction failure; occupied files are never replaced.
The CLI owner verifies full case order and frozen inputs, distinct executable bindings, unchanged
options, uncompleted preparation, executable/input drift and occupied output refusal. This adapter
does not publish evidence or claim that preparation alone qualifies a backend.




Native observation contract (private FFI, no persisted schema): the GPU device owner stores checked
nonnegative counters for successfully executed non-leaf graph nodes, completed explicit readback
bytes/calls, and explicit backend synchronization calls. `gpu_observation_state(owner, field)`
uses fields 0 nodes, 1 readback bytes, 2 readback calls, 3 explicit synchronization calls,
4 managed host allocation peak, 5 managed device allocation peak, 6 resident weight payload
7 resident KV payload, 8 materializing model operations, 9 down-projected layers and
10 selected expert invocations; all
start at zero and invalid selectors or a failed counter return -1. `gpu_slot_get(owner, slots,
index, bytes, offset, size, label)` accepts a positive size no greater than the destination slice,
nonnegative tensor offset, and a complete in-tensor interval; refusal leaves byte/call counts
unchanged. Native counter storage is fixed-size per owner, not a retained event log. Readback takes the device owner explicitly
and requires the selected tensor to occur in one of that owner's prepared, successfully executed
graphs; unrelated CPU tensors cannot be attributed through a global current-owner pointer. Invalid
owner/field/graph/tensor/bounds or counter overflow refuses without a successful observation.
Graph-node counts include native view/copy nodes, so this raw observation is not by itself the
schema-1 model-operation/layer/expert closure proof. Existing weight/input/KV counters own upload
bytes. Diagnostic invocations use separate owners; only the production owner's snapshot feeds
production placement/transfer evidence. The snapshot precedes owner destruction; cleanup evidence
owns teardown after it. No timing or performance claim follows from these counters.

Allocation peaks cover this native owner's admitted metadata/staging and resident device buffers,
starting at successful initial allocation and retaining the maximum across input/workspace
allocation and graph rebuild. The workspace plan is a ceiling, not an allocation request: initial
allocation owns weights and KV only; input planning queries the backend buffer type without a
placeholder buffer, then allocates the measured inputs and graph storage. Host and device accounting remain
separate on UMA; these fields do not measure RSS, driver-private storage, or an unsuccessful initial
allocation prefix. Observation failure is sticky if a current sample is invalid. Current allocation
queries retain their existing meaning. `gpu-device-smoke` owns zero defaults, exact initial peaks,
measured workspace with preserved peak, and graph rebuild; the provider trace owner checks
peak/current ordering and unavailable CPU/diagnostic observations before teardown.

Resident payload observations scan the owner's original ordered metadata tensors after weight/KV
finish, on graph prepare/invalidate/compute boundaries and on snapshot queries. Each completed
tensor must retain a nonempty, nonoverlapping interval within its original live owner buffer;
checked sums exclude allocator padding. A changed completed payload sum or invalid interval poisons
observation and refuses subsequent compute. Unfinished domains report zero. Original metadata and
buffers have one owner and no reset/rebind/release path between finish and device Drop; graph
context reset cannot reset them. This scan supplies payload residency, while model identity and
one-time weight binding coverage remain owned by the pack loader and its independent geometry
projection. The device owner verifies partial defaults, exact payloads, repeated graph boundaries
and a fixture-only displaced-pointer refusal before compute; the provider owner checks positive
payloads below buffer extents across both models. No payload sum substitutes for model-operation
or expert coverage.

The parent independently derives expected residency from the retained successful model IR:
the complete source/coverage tensor count is `3 + 12 * n_layer` for both supported model layouts;
coverage and quantization totals must agree on the immutable payload. The request-capacity F32
K/V payload is `8 * n_layer * head_dim * n_head_kv * (prompt_token_count + maximum_tokens - 1)`.
Native success requires exact observed weight/KV payload and first-binding count, not rounded
buffer extents. Malformed/incomplete coverage, inconsistent totals, overflow and mutated native
payload/counts are rejected by the provider/CLI owners. Forced replay has its own capacity and
does not replace these production expectations.

| Native observation closure | Implementation | Required regression |
| --- | --- | --- |
| Construction / defaults / invalid selector | native device state and `gpu_observation_state` | `gpu-device-smoke` zero and selector refusals |
| Successful compute / repeated graph execution | `align_gpu_graph_compute` | `gpu-device-smoke` node totals across reuse/invalidation |
| Model/layer/expert projection and overflow | native node/source/extent scan and independent `ModelWork` projection | provider owner both models, immediate EOG/decode, mutated counters; native observation owner wrong down source and counter overflow before compute |
| Shared graph dependencies across output expansion | stub expansion preserves existing graph membership, matching pinned ggml | native observation owner alternating graphs, repeated/shared output expansion; provider CPU/GPU stream equality |
| Explicit readback success / malformed bounds or foreign tensor | `gpu_slot_get` and native owner membership check | `gpu-device-smoke` counted bytes/calls and refused unrelated reads |
| Ordinary and diagnostic generation | `runtime_generation` owner-aware logits readback | `gpu-generation-smoke` and provider trace owner |
| Early failure / cleanup / CPU independence | no global current-owner binding; existing device Drop | `gpu-device-smoke` and `runtime-provider-smoke` |

`runtime_observation.Snapshot` is the provider's owning production-only raw result. Its exact fields
are `available,graph_nodes,read_bytes,read_calls,sync_calls,weight_upload_count,weight_upload_bytes,
kv_upload_bytes,input_upload_bytes,prefill_executions,decode_executions,allocated_host_bytes,
allocated_device_bytes,weights_buffer_bytes,kv_buffer_bytes,managed_host_peak_bytes,
managed_device_peak_bytes,resident_weight_payload_bytes,resident_kv_payload_bytes,
model_operations,model_layers,model_experts,
device_total_bytes,device_free_bytes,bundle_id,device_name,device_description,device_id`.
It captures the existing native state queries before the production device is dropped, validating
nonnegative counters, positive execution/allocation/weight observations and nonempty identity.
Device memory is the selected ggml device's reported total/free capacity at that snapshot; total
is positive and free may be zero but cannot exceed total. It is advisory capacity, not an allocation
peak. `device_id` copies the pinned ggml device property (empty when unavailable); CUDA host
identity probes match its normalized PCI bus ID, never a presumed enumeration ordinal. Metal
uses the observed device description and the installed OS build for its integrated driver identity.
A later GPU observation must preserve bundle, name, description, ID and total capacity; free
capacity may vary. The provider owner checks these bounds and rejects corrupted device-memory fields. The
evidence host uses the first successfully observed GPU device and does not invent availability
from the profile's requested device name. Zero free bytes does not mean an unavailable device.
CPU, ordinary unobserved calls and diagnostic replay return `available=false` with zero/empty fields;
this is absence of a GPU observation, not a claim of zero physical resource use. Current allocation
sizes remain `allocated_*`; separately sampled native peaks are `managed_*_peak_bytes` and must
be at least their current totals. Payload minima and RSS still require their own observations.
`TraceResult` adds this
snapshot as `observation`; no persisted/public schema changes. Failure to capture refuses the trace.
The provider trace owner verifies CPU absence, GPU read bytes/calls against sampled positions and
vocabulary, one prefill plus the actual decode count, bundle/device identity and positive allocations;
ordinary/production/reproduction text and IDs remain equal. Separate owners prevent diagnostic work
from adding to the production snapshot. Native resource failure/teardown stays with the device owner.



The private provider trace entrypoint reuses ordinary provider admission, source/geometry identity,
chat prompt preparation and output decoding. Its inputs are the existing provider configuration and
generation request plus mode 1 (production) or 2 (diagnostic), borrowed forced IDs and a borrowed
mutable stream. Forced IDs are allowed only in mode 2, with the same vocabulary/context bounds as
the native generators. Results own output text, actual sampled IDs (including terminal EOG), and
prepared prompt IDs. Forced replay returns empty text: its predictions are numeric evidence, not
a completion. No persisted schema, cache identity or public CLI is added (N/A). `provider_runtime`
owns this boundary; errors preserve the ordinary `Result<_, Error>` refusal and automatic native
owner teardown. Each call owns an independent snapshot, device and KV lifecycle. The qualifier
passes empty system text and the calibration's prompt UTF-8 as user text, and must compare prepared
IDs with the frozen calibration before accepting a case.

| Provider trace closure | Implementation | Required owner evidence |
| --- | --- | --- |
| Construction / malformed mode and forced IDs | `provider_runtime.generate_trace` / shared admission | provider trace smoke invalid mode/forced controls |
| CPU and GPU production / reproduction | shared `generate_mode` dispatch | provider trace smoke ordinary/observed/reproduced output and token equality |
| Forced success / early EOG | shared bounds, diagnostic native dispatch | provider trace smoke forced replay across EOG |
| Stream failure / cleanup | existing CPU outcome and GPU device owners | native CPU/GPU trace owners plus provider trace smoke failure and subsequent success |
| Source, geometry, prompt and decoding | existing provider admission and tokenizer | `runtime-provider-smoke` plus provider trace smoke prepared prompt binding |

Provider trace owner: `python3 scripts/run-gpu-provider-trace-smoke` passes Qwen/OLMoE greedy
production, reproduction, forced continuation across immediate EOG, exact independent traversal,
CPU/GPU byte equality and stream failure followed by success. Existing seeded CPU/native GPU
owners remain `scripts/run-gpu-cpu-trace-smoke` and `gpu-generation-smoke`. The provider owner also
regresses packed multi-row masks when request KV capacity exceeds prompt width: the stub uses the
real shim's `valid_width * sizeof(float)` row stride instead of the KV backing stride.
`gmake gpu-device-smoke runtime-provider-smoke` passes the affected resource/provider regressions.



Request 61 shipped at Align `3fbb74fe7c351e526c997bd4c70bd00cf1a424a0` (PR #982).
The native producer adopts direct borrowed field receivers and optional-writer projections;
`gpu-numeric-stream` is its combined native/independent-reader owner.

The case helper writes numeric tensors to an invocation-owned scratch file; the parent consumes
the adjacent CPU/GPU pair, then removes both streams. These files are not retained evidence,
model caches or public CLI inputs. The schema-1 case result retains their comparison outcome.
`runtime_numeric_stream` owns production, `gpu_qualification_stream` owns framed reading, and
`gpu_qualification_numeric` owns values. The parent independently derives tensor order, shapes and
counts from model geometry and the case; a well-framed file alone never qualifies those semantics.

All integers and scalar payloads are little-endian. The 24-byte file header is:

| Offset | Field |
| --- | --- |
| 0 | 8 ASCII bytes `G1TRACE1`, fixing version 1 |
| 8 | u32 model: 1 Qwen, 2 OLMoE |
| 12 | u32 reserved, zero |
| 16 | u64 total file-byte ceiling, including headers/footer; 108 bytes through 4 GiB |

Every record has a 40-byte header: u32 `kind,layer,step,width,height,reserved` followed by u64
`payload_bytes,ordinal`. Ordinals begin at zero and are consecutive; reserved is zero. Positive
width/height multiply to exactly `payload_bytes / 4`, with at most 64 MiB in one record. Dimension 0
(`width`) varies fastest. Step zero is prefill; diagnostic steps are at most 4,096 and production
sampling steps at most 127. Kinds are 1 production final logits, 2 diagnostic layer output,
3 diagnostic router scores, 4 diagnostic selected IDs, 5 diagnostic selected weights, and
6 diagnostic final logits. Logit records have `layer=0xffffffff,height=1`; other records have a
non-sentinel layer. Kind 4 contains nonnegative i32 IDs; other payloads are binary32. The producer
rejects nonfinites before writing a record and records their count for case failure classification.
The reader preserves raw bits; the independent numeric consumer also rejects nonfinites.

A final 40-byte footer has zero in every field except `ordinal`, which equals the number of data
records. At least one data record is required. Missing footer, trailing bytes, wrong model/version,
invalid tag/shape/ordinal, a file larger than its declared or caller-derived ceiling, and any
file/link identity change fail. The reader opens a single-link no-follow regular file, checks its
identity again at completion, and computes SHA-256 while reading chunks of at most 4 MiB. A caller
may bind a previously observed digest; neither an ignored payload nor early close counts as a
completed stream. The parent retains the CPU digest before launching its paired GPU command.

`gpu_qualification_pair` requires that prior CPU digest and caller-derived frame expectations;
agreement between two files alone cannot establish the correct shape or order. Scalar frames are
compared in bounded chunks. Each routing token uses three adjacent height-one frames (scores, IDs,
weights), ordered by token within the caller's diagnostic layer traversal. Each vector is bounded
by 4 MiB; the pair retains at most six such vectors for a boundary. IDs are decoded as signed i32
and validated by the routing owner. Footer verification rejects extra or missing expected tensors;
an exception poisons the pair and complete comparison cannot be resumed after structural failure.
`gpu-numeric-pair` owns this independent paired-consumption boundary. Geometry-derived traversal
and final case evidence remain part of the pending case integration, not proof supplied by this
internal reader API.

The case traversal is production sampling logits first, then diagnostic generation reproduction,
then a separate diagnostic teacher-forced traversal. Each diagnostic traversal emits prefill and
its decode steps in order. Within a step, layers ascend; each OLMoE layer emits routing triples in
token order, then its layer output. A final-logit frame follows all layers. Prefill layer outputs
and routing have prompt width except the highest layer, whose output selection reduces width to
one in the shipped Qwen/OLMoE builders; every decode layer has width one. Production/reproduction
sampling positions equal the frozen generated-token count, including an EOG token when sampled.
Before paired consumption, the case owner must establish that both actual generated ID sequences
equal the frozen sequence, so no production comparison uses divergent token prefixes. The forced
traversal has one prefill plus one decode position per supplied teacher-forced token; it does not
stop on EOG because those tokens are numeric replay inputs, not sampling decisions.

For layer count L, embedding width E, vocabulary V, prompt width T, production sampling count P,
and forced-token count F, diagnostic layer-column count is
`C = 2 * ((L - 1) * T + 1) + (P - 1 + F) * L`.
Expected layer-frame count is `L * (P + F + 1)` and expected final-logit scalar count is
`V * (2 * P + F + 1)`. Qwen expected scalar count adds `E * C`; OLMoE additionally adds
`(expert_count + selected_count) * C` and has C routing boundaries. Selected integer IDs are not
scalars but contribute `selected_count * C * 4` payload bytes to the exact stream-size bound.
The geometry/case traversal owner computes counts and size before opening streams and iterates
expectations without retaining a tensor-sized manifest. `gpu-case-traversal` owns independent tiny
Qwen/OLMoE byte/count goldens, prefill reduction, multiple decode/forced steps, bounded shapes and
stream size, complete pair consumption and mismatch/nonfinite propagation. This internal plan
does not substitute for the native geometry validator or the actual generated-output precondition.

`runtime_numeric_stream.disabled()` creates an inactive owner with no file and zero payload
capacity. `create(root,relative,model,maximum_bytes,host_budget_bytes)` validates scalars and its
65,576-byte host payload reservation before the shipped exclusive-beneath create. `record(owner,
frame,payload)` borrows payload only for the write; `finish(owner)` writes the footer and flushes.
The reservation is the pinned writer's 64 KiB buffer plus one reusable 40-byte header and is charged
to observed GPU generation metadata before weight upload. Source buffers are never copied into a
second tensor-sized allocation. Inactive recording is a no-op. An active malformed, over-budget or
failed write poisons the owner; no later record or finish can succeed. Finished owners reject
further writes. The Move owner closes its optional writer on drop; partial-file removal belongs to
invocation cleanup. No durability or atomic multi-file publication is claimed for scratch streams.

The following observed entrypoints consume Request 62's shipped imported-borrow surface.
`generate_qwen_observed` and `generate_olmoe_observed` retain the existing generation arguments
and append `borrow mut stream: runtime_numeric_stream.Stream`; the ordinary entrypoints create a
disabled stream. The observed variants charge `reservation(stream)` in metadata admission before
upload and record kind-1 logits at each sampling position. They leave footer/cleanup to the case
owner, which must append the diagnostic traversals before finishing. Return values, sampling,
source identity and GPU ownership remain those of the ordinary entrypoints. A stream failure
propagates `Error` and prevents a successful case; no tensor-sized observation buffer is added.

| Native adoption closure | Implementation | Exact owner |
| --- | --- | --- |
| Construction, return, drop, absent writer | `runtime_numeric_stream.create/disabled` | `runtime_numeric_stream_smoke.golden/main` |
| Golden bytes, repeated writes, footer | `record/finish` | `golden`, independent reader `GOLDEN` |
| Malformed, nonfinite, budget, early failure, terminal transitions | `record/finish/create` | `refusal/main`, reader malformed owners |
| Production Qwen/OLMoE prefill/decode and reservation | Observed entrypoints, `prepare_memory` | `runtime_generation_smoke.observed/observed_refusal`: active/inactive prefill/decode, reservation, pre-upload budget refusal and stream failure; independent reader in `run-gpu-generation-smoke` |
| Diagnostic layer/router and case integration | Native case producer | Deferred within G1; final qualification remains pending |

`gmake gpu-numeric-stream` owns construction/return/drop, inactive recording, exact golden bytes,
occupied path, shape/nonfinite/byte-budget refusal, poisoned and finished transitions, and the
Python reader's chunk/ordinal/footer/model/link/mutation/early-exit refusals. The source writer and
reader are checked against the same byte vector independently. `gpu-generation-smoke` owns
the production logit hook and reservation; full layer/router production remains in the G1 numeric
case integration. No performance claim or additional aggregate membership is introduced.

#### Native diagnostic replay integration

`runtime_diagnostic.Capture` owns one reusable native slot table and one bounded readback buffer.
It is invocation-local, never persisted or exchanged; schema/cache identity is N/A because its
references are reset before each graph construction and consumed before that graph is invalidated.
`disabled()` allocates no payload; `create(layers,embedding,prompt,experts,selected)` validates
positive geometry and the existing 64 MiB tensor ceiling before allocation. Its reservation is
`16 + 8 * 4 * layers + 4 * max(embedding * prompt, experts, selected)` bytes. Qwen uses zero
experts/selected. Generation charges this reservation, plus the existing stream reservation,
before any weight upload. No new native ABI is required.

The Qwen/OLMoE builders have diagnostic variants with one additional borrowed mutable capture.
Ordinary builders pass a disabled capture and mark only final logits. Diagnostic builders retain
and mark each layer output; OLMoE additionally retains the full router probabilities, full argsort
IDs and gathered selected weights before slots are reused. Shape checks precede readback. Router
rows use full-expert strides for argsort, preserving a narrowed top-k view's noncontiguous token
layout. The host retains only one layer output or one routing vector at a time.

`runtime_generation` diagnostic entrypoints preserve observed-generation arguments and append
borrowed teacher-forced IDs. An empty array reproduces production sampling; a nonempty array
executes one prefill and every forced decode token, including EOG, without sampling-based early
exit. They emit the established layer/router/final frames, append no footer, and return the
sampled IDs for reproduction comparison. Production and each diagnostic traversal use separate
native invocation owners and fresh KV. The case process deadline covers all three traversals.
All fallible operations return the existing `Error`; any refusal prevents successful case output.

| Diagnostic closure | Implementation | Discriminating owner |
| --- | --- | --- |
| Construction, geometry, reservation, overflow/byte bounds | `runtime_diagnostic.create/reservation`, generation admission | native diagnostic smoke: disabled, invalid geometry, exact reservation, budget refusal before upload |
| Capture before slot reuse, shape/stride, complete frame order | diagnostic Qwen/OLMoE builders and `runtime_diagnostic.write` | native diagnostic smoke paired with `gpu_qualification_traversal` for both geometries and highest-layer reduction |
| Production isolation and successful reproduction | disabled builder capture, generation mode dispatch | ordinary generation owner plus diagnostic replay ID equality and production-only kind-1 stream |
| Forced tokens, EOG, context, early exit | generation diagnostic loop | multi-step forced replay and out-of-vocabulary/context refusal |
| Readback/write failure, graph invalidation, cleanup | capture reset, synchronous graph compute, existing native owner Drop | native diagnostic malformed shape/stream-limit refusal and subsequent independent invocation |
| CPU reference and final case/publication integration | existing CPU generation owners, native case producer and parent sequencing | pending within G1; the GPU diagnostic checkpoint alone does not close qualification |

CPU tracing extends the existing `decode_step` and `moe_decode_step` generation paths; it does
not replace their math, sampling, cache or teardown. Their qualification-only trace entrypoints
append a mode (`1` production logits, `2` diagnostic), borrowed forced IDs and a borrowed mutable
stream to existing generation inputs. Existing callers use internal mode 0 with a disabled stream.
Forced IDs are valid only in mode 2, validated against geometry/context before execution; the loop
uses them as decode inputs and ignores EOG/the sampling maximum only for that replay. Output
remains the existing owned generation-parts record. CPU layer readbacks and logits use existing
host buffers; OLMoE routing uses bounded diagnostic scratch before graph teardown. Stream failures
set the existing outcome error and converge through normal cleanup. No persistent schema changes.
The native CPU trace owner must compare the complete emitted order/shapes/counts to the independent
traversal, exercise production/reproduction IDs and forced EOG, and retain unchanged ordinary
CPU-generation owner evidence. Final native case/CLI integration remains pending within G1.


### 3.11 Local qualification kit assembly

The internal kit owner accepts canonical profile bytes, both captured source closures and an exact
relative-path mapping of supplied local files or generated record bytes. It creates a private
output-sibling staging directory, writes regular files exclusively and copies large model inputs
in at most 1 MiB chunks. Local file inputs must be single-link no-follow regular files; descriptor
and path identity and original size are checked after copying. Source capture uses the shared
writer from §3.4. No hardlink/symlink to a model input is installed in a kit.

Before publication, ordinary retained-root admission verifies all profile/calibration/bundle/model
hashes and both source closures; its referenced file set must equal the written file set. Missing,
extra, duplicate/prefix-colliding, traversal or reserved profile/source paths fail. Publication uses
the existing no-replace directory rename. An occupied output is preserved; any failed copy,
admission or rename removes only the private stage. The caller retains the supplied inputs and
owns the completed output. No remote transport, credential handling, new CLI or qualification
success is provided by this assembly API. `gpu-kit-assembly` owns actual fixture-kit admission,
large bounded copying, occupied-output preservation, input mutation, malformed/missing/extra paths,
digest refusal and partial-stage cleanup. Real calibration and backend qualification remain G1
integration prerequisites.

## 4. Execution and memory design

`provider_runtime` admits requests and owns text output. `decode_step` and `moe_decode_step`
retain architecture semantics, token/EOG order and sampling. New `runtime_device`,
`runtime_memory` and `runtime_execution` modules own backend-neutral device state, admission and
execution. Extend `ggml_ffi.align` and `ggml_shim.c` only with shaped checked calls and native
resource ownership; do not duplicate model math in backend-specific loops.

Use ggml supported-op and allocation queries for the exact graph. Before allocation, checked
admission includes immutable weights, request-capacity KV, peak activation/workspace, scheduler
copies, metadata and staging. Available-memory probes are advisory. A one-byte-too-small budget
fails before weight upload. Driver/runtime overhead is reported separately from managed caps.

Bind each weight once per invocation, copying only when required. KV and reusable workspaces stay resident through prefill and
all decode steps. Production host readback is limited to logits needed by the existing sampler.

The decomposed attention reduction width is `min(model_context, ceil(valid_tokens / 256) * 256)`,
matching the pinned reference's minimum KV-view bucket. `runtime_inputs.attention_width(valid,
context)` returns this checked positive extent or `Error.Invalid` for nonpositive, out-of-context
or overflowing input. This private helper owns no allocation, persisted state or schema. Physical
KV remains request-sized; the existing model node tables explicitly zero-pad attention operands.
`runtime_generation` reserves masks to the maximum request bucket and uploads each current bucket
densely, with every future/padded position set to negative infinity. `runtime_qwen` and
`runtime_olmoe` use that same width in graph construction and topology identity. Graph metadata
includes the padded nodes. This settles arithmetic shape; it does not claim decode graph reuse.

`ggml_ffi.op_attention_scores(ctx, slots, out, key, query, label) -> Result<(), Fault>` constructs
one F32 matrix product with `GGML_PREC_F32`, matching pinned llama.cpp's explicit KQ precision.
`ctx` owns its tensor metadata; all slot tensors remain borrowed and no payload allocation occurs.
Null context, missing slots, non-F32 inputs and incompatible matrix shapes return the existing
INIT/SLOT/TYPE/SHAPE faults before construction. Qwen/OLMoE node walkers select this operation
only for the matrix product immediately consumed by masked attention softmax; unmasked router
softmax and ordinary matrix products retain their existing precision. No format/schema changes.
`gpu_workspace_allocation_smoke.c` checks native precision metadata, unchanged ordinary products
and malformed input refusal; `gpu-device-smoke` and `gpu-generation-smoke` own both walkers.

The repair closure is: `gpu-device-smoke` owns width validation, exact/boundary/context-tail cases
and both model graphs; `gpu-generation-smoke` owns production/diagnostic invocation success,
maximum-one and allocation refusal; the independent same-device llama.cpp diagnostic owns real
Qwen prefill/decode scalar comparison with matched embedding placement and F32 KV. Existing
failed CPU/GPU calibration evidence remains failed and unchanged. Padded workspace participates
in the existing memory ceiling and must be included in subsequent performance measurements.

### Private first-fault retention repair

The public provider still returns its existing `Error.Invalid`. Its private native case failure
adds `category` and `stage` before the stream counters. A thread-local diagnostic latch retains
only the first GPU fault and its active stage; later synchronization or cleanup cannot replace it.
The latch stores integers, owns no device pointer, and is reset at private case entry and each GPU
request's device-admission entry. Successful admission planning does not clear a recorded fault.
No diagnostic state persists in the public result or replaces the serial GPU owner guard.

| Owner | Contract / closure |
| --- | --- |
| Native shim / `ggml_ffi` | Reset, mark an active lifecycle stage, latch the first nonzero status, and read the stable category/stage. Fallible GPU boundaries mark device/plan/allocation/upload/prefill/decode/readback/synchronization/release before work. Fault conversion latches before returning its existing `Fault`. Explicit pre-upload budget refusals record `MEMORY_BUDGET/plan`; native unsupported operations retain `UNSUPPORTED_CAPABILITY/plan`. Device owner tests cover reset, first-fault precedence and no stale result. |
| `runtime_device` / `runtime_generation` | Bundle refusal and arithmetic budget refusal retain their specific internal category before returning `Error.Invalid`. Ordinary immutable device ownership/cleanup stays unchanged. |
| `runtime_case` / native reader | Emit and strictly consume category/stage with the original traversal phase and stream prefix. Stream nonfinite failures retain `NONFINITE/readback`; output-binding failures are `COMPUTE/readback`. Failures without a specific native status retain a bounded stage-aware fallback, never a fabricated spawn failure. |
| Case records / execution evidence | Prefer the validated child's first category/stage over generic nonzero-exit classification. Keep actual process exit/signal/logs, and record cleanup failure separately. Provider owner injects device, budget, allocation, transfer, prefill and decode failures; case/evidence owners prove first-fault and cleanup precedence. |

The unpublished schema-1 private failure object changes with its owning producer and consumer.
Historical failure objects remain evidence under their captured source version. A crash that never
emits a valid private failure continues to retain its actual process terminal status.

### Executed artifact and case-input binding repair

Every started case has exactly two logical arguments: `<candidate>:sha256:D` for GPU or
`<cpu-reference>:sha256:D` for CPU, followed by `<case-input>:sha256:I`. `D` must equal the
role-specific available produced identity in `source`; `I` is the digest of the exact immutable
owned input bytes passed to that child. A different executable, swapped role, extra argument or
unbound input cannot pass replay. The live process owner verifies both hashed mappings before
launch. Unstarted rows retain their existing empty command and no fabricated input artifact.

| Owner | Contract / closure |
| --- | --- |
| `gpu_qualification_native_sequence` | Hash the exact canonical input written exclusively into the case root; bind that hash in the logical command mapping. Existing complete provider owner plus swapped-input refusal. |
| `gpu_qualification_case_records` | Retain the same input at `case-inputs/NNN.json` with role `case_input`, at most 4 MiB, alongside actual child logs even on failure. The input is evidence only: replay never opens its embedded original physical paths. No model weights are retained. Case-record owner covers started/unstarted and failed prefixes. |
| `gpu_qualification_records` | Validate role-specific command shape, cross-bind executable digest to `source`, input digest to the required retained file, and retained canonical input sampling/prompt/expected/forced fields to the frozen case. Reject missing/changed/wrong-role input artifacts and executable substitutions. Result replay owner owns negative fixtures. |
| `gpu_qualification_publish` | Reserve three files per possible started case (input plus two logs) before preparation; retain existing aggregate byte and file ceilings. Publication/CLI owners verify closure and capacity refusal. |

This repairs the unpublished schema-1 evidence contract. Historical evidence remains bound to its
original captured validator; it is not rewritten or relabeled as newly qualified. Original absolute
paths inside private input artifacts are recorded provenance, not executable replay instructions.
The command itself retains only logical hashes and the existing closed environment.

### Numeric validation deadline repair

The generation sequence passes its original monotonic deadline through native output validation,
stream framing/hashing and paired scalar/router comparison. This does not create a fresh validation
budget. Deadline checks occur before/after bounded work: at most 64 KiB per file read/hash and 1,024
items per scalar, router-score or selected-ID traversal. A deadline refusal closes every reader,
retains the actual child result and consumed failure prefix, removes owned scratch, and prevents
starting the next child. No partial comparison becomes PASS. Persisted schemas and numerical
predicates are unchanged; the private optional deadline argument defaults to absent for offline
replay and existing owner tools. The owning deadline helper validates a positive integer deadline.
`python3 scripts/run-gpu-validation-deadline-smoke` owns interruption inside one scalar chunk,
exact router near-tie construction, delayed payload reads, descriptor cleanup and offline reuse.
`run-gpu-provider-trace-smoke` proves original-deadline propagation through both native and paired
validation, actual zero-exit child retention, scratch cleanup and no subsequent child.

| Owner | Closure |
| --- | --- |
| `gpu_qualification_native_sequence` / `gpu_qualification_cases` | Share the original deadline; retain child outcome and deadline detail; no next child after interruption. Existing case-sequence/provider owners plus deadline regression. |
| `gpu_qualification_stream` | Check bounded framing, reads and hashing; close acquired descriptors on expiry; partial readers remain unverified. Numeric stream owner plus delayed-read regression. |
| `gpu_qualification_native`, `gpu_qualification_pair`, `gpu_qualification_traversal` | Propagate the same deadline through both validation passes, including router payload/ID construction; cleanup on refusal. Native provider and numeric traversal owners. |
| `gpu_qualification_numeric` | Check scalar loops and every potentially large router traversal without changing exact comparison/tie predicates. Deterministic clock regression expires inside scalar and near-tie work, before the complete supplied chunk is processed. |

### Pre-upload exact-shape admission repair

Before allocating device payload or reading weight chunks, generation performs one bounded
metadata-only traversal using the same model builders as execution. The selected owner enters a
planning phase, defines all weight/KV/input shapes, and checks prefill plus every reachable decode
bucket. The real backend uses zero-sized buffer-type descriptors for external leaves, with null
data pointers; no sentinel addresses or GPU payload allocations are permitted. Allocator measurement
therefore excludes resident leaves while retaining exact temporary graph requirements. Every node
and external buffer type must be supported by the exact selected device. The largest measured
workspace plus inputs must fit the already checked request ceiling.

| Surface / owner | Contract and validation | Closure owner |
| --- | --- | --- |
| `runtime_memory.plan_begin/plan_finish` | Begin only on an unplanned device owner. In planning mode, allocation owns metadata only and weight `add/finish` define shapes without accepting bytes. All upload, compute and readback operations refuse. Finish requires successful prepared graphs, frees all planning metadata/descriptors, and restores the same device/bundle/budgets to its initial allocation state. Planning handles never escape the helper. Failure returns through ordinary resource cleanup and never starts payload allocation. Schema/cache identity: N/A, invocation-local state only. | Real workspace owner: zero allocated device bytes/upload/compute, unsupported shape and insufficient workspace, repeated/invalid lifecycle and cleanup |
| Native graph preparation | Walk every exact graph node with `ggml_backend_dev_supports_op`, and admit the selected external buffer type with `ggml_backend_dev_supports_buft`. Measure with `ggml_gallocr_reserve_n_size` before creating a workspace allocator. Refusal is terminal for this owner; ordinary execution also checks the prepared graph. | Real workspace owner: supported graph, injected unsupported operation, allocation ceiling refusal before upload |
| Model load owners | `define` validates the same checked plan and adds the same ordered shapes as ordinary load, without opening or reading payload. Existing streamed upload remains the execution path after admission. | Both model device/generation owners; zero pre-admission uploads |
| `runtime_generation` | Reuse the already validated immutable plan. In a scoped helper, define roots, build prefill and each reachable fixed decode bucket, then discard all shape-only handles before normal allocation/loading. Diagnostic captures remain disabled during planning because they do not alter graph shapes or operations. All buckets, including the final clipped one, are checked. Cost ceiling: at most one prefill plus nine decode shapes for the existing 2048-prompt/128-generation bound; one root and two graph metadata arenas live at once, zero weight reads or GPU compute. | Generation owner: maximum-one, same bucket and boundary crossing; real Qwen/OLMoE final-logit comparison |

This initial admission traversal does not claim bounded prefill microbatch support; its chunk
policy and coverage remain required separately. Execution and planning must use the same eventual
chunk policy. A planning failure never falls through to the ordinary upload path.

### Resident decode graph reuse repair

The decode graph reads a fixed `min(attention_bucket, request_capacity)` resident KV prefix.
It writes the current K/V values using device `set_rows` operations before the dependent attention
views, replacing concatenation of the entire past prefix. Physical K/V layouts remain unchanged.
Both planes are initialized to zero once, so masked unwritten capacity cannot introduce NaNs.
Zero padding beyond request capacity remains explicit. The graph is rebuilt only when the
attention bucket changes; token IDs, positions and causal-mask values are mutable input payloads.

| Surface / owner | Contract and validation | Closure owner |
| --- | --- | --- |
| `runtime_qwen` / `runtime_olmoe` decode builders | Add the request capacity argument; split the existing node walk around K/V writes. KQ and V-attention operands depend on the write result. No past-KV concatenation. Metadata and output slots belong to the current graph context; input/payload owners outlive it. | `gpu-device-smoke`: both model graphs, prefix preservation and dependent readback |
| `qwen_nodes.build_range` / `olmoe_nodes.build_range` | Borrow the existing node table and emit only `[begin,end)`, rejecting invalid bounds. The ordinary full walker delegates to this range. No new persisted table or schema. | `gpu-device-smoke`, `gpu-generation-smoke` |
| `runtime_kv.write_indexed_prefix(owner,index,kind,layout,indices,width,slots,out,source)` | Native F32 single-token write, then a fixed prefix view of the updated plane. K uses one I32 position; transposed V uses one I32 index per head lane over a flattened destination. Reject wrong owner/state/layout/type/shape, out-of-plane prefix, or an index space exceeding I32 before construction. Views and `set_rows` metadata belong to the graph; no payload allocation. | `gpu-device-smoke`: malformed shape/state, K/V writes, exact tail, rebuild and cleanup |
| Native input registration / `runtime_inputs.update` | Indexed writes register their input's plane capacity and lane count. Position payloads must be complete and in range. V payloads must be complete and exactly `lane * capacity + position`; changing the K position invalidates the previous V payload. Validate all values before upload; refuse decode compute until both payloads agree. Input registration must agree across all layers. | `gpu-device-smoke`: negative/out-of-range/partial/mismatched indices, no upload on rejection, refusal before complete inputs |
| `runtime_generation` | Reserve one extra I32 V-index input with `head_dim * n_head_kv` entries. Update it from checked placement arithmetic for each decode; no model value or routing readback. Retain one decode graph/key/output window inside a bucket and invalidate at the boundary. Shape identity binds bucket and actual resident view extent, not the mutable position. | `gpu-generation-smoke`: consecutive reuse, boundary rebuild, maximum-one and diagnostic parity; independent real Metal final-logit comparison |

These private surfaces change no public provider result or persisted format. Their host inputs,
native metadata and bounded workspace remain subject to the existing admission contract. This
repair does not waive pre-upload measurement, operation admission, corpus or performance gates.

OLMoE routing, selected-expert `mul_mat_id`, weighting and reduction stay in the GPU graph; resident
execution must not inherit the CPU path's per-layer router readback and expert-claim boundary.
Never call a CPU pointer primitive on device-only storage. OLMoE keeps gate/up/down identity and
ordered expert reduction; any compact expert view carries an explicit global/local map.
The shaped `op_view_2d` boundary accepts only four-byte `F32` and `I32` sources. G1 takes the
leading `{n_expert_used, tokens}` `I32` view of the descending argsort result with the source's
dimension-1 stride and zero offset, then passes those global IDs directly to the fully resident
`n_expert`-plane stacks. Quantized and other element widths remain invalid, and the real and stub
shims enforce the same type and extent checks.

Before admission, `runtime_weights.allocation_bytes(owner, shape)` asks the selected backend buffer
type for one tensor's allocation size and rounds it to that buffer's alignment. It creates no device
allocation and returns a positive `i64` or `Error.Invalid`; the caller checked-adds every returned
extent to form the exact immutable-weight plan. After allocation and `add`,
`runtime_weights.upload(owner, index, offset, bytes)` accepts one nonempty, in-order chunk. `offset`
must equal the pending tensor's accepted byte count and the chunk end must not exceed its logical
byte extent. Reaching that extent completes the tensor and permits the next `add`; `finish` requires
every declared tensor complete and the exact planned allocation consumed. Invalid index, offset,
empty/oversized chunk, add-before-completion, and finish-before-completion fail without advancing
the upload cursor. A backend transfer failure poisons the owner. The pack reader reuses one bounded
chunk buffer, so no Align allocation grows with an individual tensor.

Build a complete model graph for each prefill microbatch or decode step, leaving intermediates and
KV updates on device. Reuse graph metadata, allocator reservations and input buffers when their
topology identity is unchanged. Update KV in place and attend only to its valid prefix. Completion
is required before host consumption or mutation/release of referenced memory, not after every
operation or layer. The performance plan's G1 rows fix bounded graph reuse, prefill batching,
backend fusion and capture eligibility, and their owner tests before implementation.

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
| bundle/device registry | exact Metal/CUDA device and private staged artifact set made from verified reader bytes | missing Request 55/56 surface, wrong backend/device/ABI/hash/arch, hard link, source replacement or in-place mutation, staged identity drift, missing op, bundle switch | original paths never reach registry; remove every safely releasable staging prefix and its empty directory; transfer the complete staging tree with unsafe native handles to process-owned poisoned quarantine; pin once; `gpu-bundle-identity-race`, `gpu-device-select`, `gpu-bundle-reuse`, `gpu-bundle-switch` |
| native owner | construct, move, borrow, explicit completion | failure at each construction prefix and completion stage | exactly-once reverse Drop; `gpu-native-owner` in whole/per-unit builds |
| admission/allocation | exact weights/KV/workspace within both caps; UMA alias accounted once | overflow, zero/one-byte-too-small cap, driver allocation race | release every prefix; `gpu-budget-boundary`, `gpu-uma-alias`, `gpu-allocation-prefix` |
| weight planning/upload | selected-backend allocation query; exact checked sum; sequential bounded chunks complete each tensor once | invalid type/shape, overflow, empty/out-of-order/oversized chunk, next add or finish before completion, source truncation, transfer failure | invalid input preserves cursor; native failure poisons then reverse-releases; `gpu-weight-chunk` |
| graph and pointers | supported graph on declared GPU; device-safe transfers; bounded F32/I32 views use source-derived strides and extents | unsupported op/buffer/type, forged or out-of-range view, device pointer passed to CPU, stale reference, nonfinite output | complete before reset/free; `gpu-device-smoke`, `gpu-graph-placement`, `gpu-device-pointer`, `gpu-scheduler-reset` |
| Qwen/OLMoE decode | prefill, >1 decode, request-capacity resident KV, correct positions/router/expert map; OLMoE argsort is narrowed to exactly `n_expert_used` global IDs before selected-expert `mul_mat_id` | immediate EOG, maximum 1/128, exact model-context edge, one-row-too-small KV, routing tie, truncated source | KV outlives steps; oversized unused model-context tails are not allocated; `gpu-device-smoke`, `gpu-decode-kv`, `gpu-expert-map`, `gpu-eog`, `gpu-context-boundary` |
| invocation guard | sequential same-bundle requests and concurrent CPU independence | concurrent GPU request, different bundle, failed prior native init | guard released only from safe state; `gpu-invocation-busy`, `gpu-second-after-failure` |
| sampler/result | same logits preserve exact greedy/RNG/filter/output behavior | malformed/nonfinite logits, decode error, partial text | no handle escapes; `gpu-sampler-fixed`, `gpu-output-refusal` |
| profile/calibration | exact four-row expansion executes every calibration/holdout twice | omitted/extra/reordered/cross-model case, changed tolerance/expected output, symlink/hard-link/mutated input | immutable descriptor-based input admission and recheck; `gpu-profile-coverage`, `gpu-input-admission`, `gpu-holdout-replay` |
| evidence/publication | canonical positive codecs, complete align-llm/ggml Git snapshots, available/unavailable build/device identities, exact argv/environment | duplicate/oversize records, source/tree mismatch, ambient-environment injection, compile/crash/timeout, >8,192 total files or >512 MiB projected closure | kill/reap owned group, retain bounded diagnostics, replay before exclusive rename; `gpu-schema-codec`, `gpu-source-replay`, `gpu-build-failure-evidence`, `gpu-command-environment`, `gpu-process-cleanup`, `gpu-evidence-publication`, `gpu-result-replay` |

The native resource starts as an invocation-local root and is never returned or placed in an Align
collection. Owners cover construction, move with source nulling, borrow, replacement, early return
and `?`, each construction prefix, explicit completion, ordinary Drop and poisoned cleanup in
whole-program and per-unit builds. A failure that cannot prove safe native unload performs one
explicit terminal transfer of the native handles and staging tree into the native process-state
quarantine before disarming invocation cleanup; no ordinary success or safely released failure can
enter it. GPU/GPU entrypoint pairs serialize by rejection before native side effects; CPU/GPU pairs
are independent except for ordinary host resource contention. Independent processes have
independent registries, quarantine states and admission guards.

The complete pinned ggml plus application source already requires more than 4,096 files; evidence
therefore allows 8,192 total files while retaining the existing 512 MiB byte and 8 MiB JSON bounds.
Before preparation, the final CLI checks the mandatory input closure and reserves count capacity
for six produced identities, a failed preparation's two logs and two logs per profile case.
`gpu-evidence-publication` owns acceptance above the former limit and refusal beyond the new
bound; `gpu-final-cli` owns refusal before any preparation command when the projection cannot fit.

Before creating the staging directory, the qualifier computes a conservative closure count/size from
the source manifest, fixed retained inputs, possible produced artifacts and two logs per profile
case. A projection above 8,192 total files (including `result.json`) or 512 MiB fails without output. Runtime streaming
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

Each CPU/GPU case helper first executes the production path, then an explicitly diagnostic phase with
the same build, model, prompt, sampler inputs and attention policy. That phase first reproduces
generation and checks its output against production, then separately traverses the frozen
teacher-forced sequence. The two trajectories cannot be conflated: a supplied forced token need
not equal the token generated at that position. Both diagnostic trajectories expose layer and
router tensors for complete numeric comparison against the adjacent CPU reference. Case output,
placement, transfer, memory and timing fields describe production execution. `numeric` includes
production-logit and diagnostic internal/logit comparisons as defined in §3.8. Check all production
logits already read for sampling against the adjacent CPU reference with the same frozen scalar
tolerances and nonfinite policy. Matching generated IDs alone cannot qualify production fusion;
diagnostic output markings may disable that fusion. No extra intermediate readback is required.
The case command owns all three traversals; the case deadline and overall elapsed time include
all of them, and any traversal failing makes the case FAIL. Diagnostic generation output must
match the production output; the forced traversal makes no generated-output claim.
Diagnostic tensor marking/readbacks never enter the performance workload or certify its residency;
production allocation/binding traces own that evidence. Schema-1 timing remains diagnostic only.

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
| G1R reusable coding session | Follow G1 with explicit caller-owned model/graph/KV lifetime and validated prefix reuse through a real coding/repair sequence. Extend the public ledger before that implementation; no process-global cache is implied by G1. |
| 81 / G2 bounded offload | Add deterministic whole-unit layer/expert placement under host/device budgets, bounded AlignPack reads and synchronous `hybrid/off`. Extend options/profile/evidence for placement and eviction before coding. |
| 82 / G3 Vulkan | Add the same working generation/offload consumer and immutable Vulkan bundle. Qualify each device/OS independently. |
| 83 / G4 HIP/ROCm | Add the same consumer for a supported AMD stack. Build work may proceed without hardware; qualification remains pending until real AMD evidence. |
| 84 / G5 overlap | Add bounded same-thread transfer/compute overlap after G2. Precommit the exact full-request metric, paired schedule, incomplete-leg representation and recommendation gate in its own schema before measurement. `prefetch=off` keeps its meaning. |
| 85 / G6 coding decision | Compare the public provider with GPU-enabled llama.cpp and controls. Precommit task corpus, attempt/retry order and cap, validation, first-pass stop rule, lifecycle, primary time-to-passing-patch metric, partial failure states and aggregation before measurement. |

The [performance plan](gpu-runtime-performance.md) orders the competitiveness work: G1R is the
next consumer, constrained-memory G2/G5 need not wait for a resident speed win, and G3/G4 do not
block a qualified Metal/CUDA comparison. Runtime speed, useful larger-model capacity and coding
time have separate measured decisions; one unsuccessful candidate does not end the program.

Start implementation with G1. A merged checkpoint is followed by the next eligible consumer. AMD
hardware absence does not block Metal/CUDA or Vulkan work, and no compile-only result closes a
device qualification.

## 9. Current verification

This design-only change requires documentation consistency, canonical-schema inspection,
`git diff --check`, one stable comprehensive review and the documentation publication preflight.
Source tests, compiler adoption, GPU builds and device qualification are N/A until G1 implementation.

### Linked core admission repair (review R9)

The G1 shared shim links `libggml` and `libggml-base` before Align admission. These two
installed libraries are explicit immutable executable prerequisites for the process lifetime;
they are not claimed to be loaded from the later plugin staging directory. The admitted bundle
must declare the unversioned shared-library entries for both cores. Builds with an explicit ggml
library directory embed their SHA-256 identities. Before loading any plugin, `runtime_device.open`
asks the native `dladdr` owner for the canonical absolute image paths containing `ggml_init`
(base) and `ggml_backend_load` (registry). `runtime_bundle` verifies those actual files through
single-link readers against the declared sizes/digests and the shim's embedded identities.
Missing identity, unavailable image, substituted core, wrong file kind or mismatch refuses with
`BUNDLE_IDENTITY/device` before device initialization, and removes owned staging. Static/ambient
legacy shim builds retain legacy CPU behavior but cannot admit a real G1 device without identities.
The model-free stub has no dynamically linked core and explicitly reports that fact.

| Surface/owner | Inputs and result | Closure and evidence |
| --- | --- | --- |
| Native core observation, `ggml_shim.c`, `ggml_ffi` | Core ordinal 0 base / 1 registry; bounded UTF-8 canonical path and 64-byte build digest, no allocation or transferable handles; invalid ordinal/capacity returns empty failure | `run-gpu-linked-core-smoke`: actual loaded image, exact/small buffers, invalid ordinal, substituted search-path image on ELF and Mach-O |
| Bundle core verification, `runtime_bundle`, `runtime_device` | Verified artifact array, actual path/build digest, existing host budget; hash/size match required; no new public CLI or schema | Same owner: matching bundle succeeds; missing/mismatched core/build identity refuses before plugin load; staging cleanup on every refusal |
| Shim builders, `build-ggml-shim`, `gpu_qualification_build` | Explicit library directory owns unversioned core files; build definitions bind exact bytes; no environment identity override | Same owner and preparation smoke: both definitions retained in physical/logical argv; legacy stub remains available |

No performance claim; admission performs two bounded library reads before model allocation. The
existing single-threaded invocation exclusion and immutable prerequisite lifetime remain required.
This repairs unreleased schema 1 semantics without rewriting historical evidence.

### Managed host accounting repair (review R1)

Admission covers both native allocations and the caller-owned buffers alive beside them. Native
allocation observations retain their explicitly named native domain; a conservative application
capacity reservation is separate from measured allocation peaks. It is never reported as measured
RSS or relabeled driver-private storage. The reservation includes model-plan arrays and their
construction overlap, slots, logits, prompt/decode masks and index images, generated IDs, topology
serialization, numeric stream and diagnostic storage, file-reader windows and allocation shells.
Both the native upload staging allocation and the loader's Align buffer are charged when they
coexist. Diagnostic bytes are not allocated again as unused native metadata.

| Owner / phase | Checked inputs and policy | Closure owner |
| --- | --- | --- |
| `runtime_bundle`, manifest read/decode | Read capacity is bounded by the host budget before reading. Parsing/owned canonical representations reserve 128 bytes per manifest byte plus 128 KiB for bounded reader/path/shell scratch, checked before JSON parsing. This is a conservative capacity bound, not a measured peak. Maximum manifest size/schema unchanged. | `run-gpu-bundle-smoke`: tight cap refusal before staging, malformed manifest, ordinary bundle and cleanup |
| `runtime_bundle`, artifact staging and core verification | Exact declared artifact capacity plus 64 KiB read window and fixed shell/path allowance; checked against remaining budget before allocation. The original artifact buffer is dropped before staged verification; no growing full-file buffer or simultaneous second image. Core verification uses the same bounded reader after manifest ownership has ended. | Same owner and `run-gpu-linked-core-smoke`: exact read, truncation/trailing bytes, digest mismatch, bounded staging and cleanup |
| Generation / model plan / native admission | Checked independent application reservation reduces native admission capacity; shared planning and execution use the same reservation. Smallest nonzero transfer buffer must fit twice. Failure records `MEMORY_BUDGET/plan` before payload upload. | `run-gpu-device-smoke`, `gpu-generation-smoke` and allocation-tracked tight-budget owner for both architectures and diagnostic mode |

The pinned runtime's ordinary allocation families and compiler-emitted ownership define reservation
sizes; no hypothetical budget allocator or incremental hash API is consumed. Request 29 remains
the owner of incremental SHA-256. Borrowed provider inputs remain charged to their existing owner;
new GPU-owned copies and transient construction storage are charged here. Historical evidence is
not rewritten. Final ledger-to-diff mapping must include the independently tracked tight-budget
owner before R1 is dispositioned as repaired.

R1 implementation reservation: `runtime_generation.application_capacity` charges 24 bytes per
potential i64 plan/index/generated element (including builder realloc overlap), 8 plan columns per
resident tensor plus three per OLMoE upload piece, and eight index columns per pack block. The pack
bound is `2 + 2*layers` for Qwen and `2 + (2+experts)*layers` for OLMoE, matching the block IR.
`alignpack_read.open_pack_bounded` checks that bound after structural header validation and before
column construction; its ordinary unbounded-to-consumer wrapper retains the existing format limit.
`runtime_pack_identity` and both resident loaders propagate the same bound. Masks charge all prompt
queries at the maximum reachable attention bucket; decode images charge that width plus V indices;
logits charge vocabulary F32s; stream/capture charge their explicit required capacities. Graph
bookkeeping and fixed-width node tables reserve 2,048 bytes per maximum graph node; geometry and
owned topology text reserve 128 bytes per supplied geometry byte; 256 KiB plus slots covers
reader windows, remaining small shells and paths. These are deliberately conservative bounds.
Native metadata omits the separate stream/capture reservation. The remaining cap after fixed
storage and the 64-byte Align buffer shell is divided between the two simultaneous staging
windows, each at most 16 MiB. `align_gpu_host_reserve` binds the separate capacity before native
memory admission and preserves it across metadata-only shape planning. It has no allocation side
effect and rejects negative/late requests or capacities above the host cap. The private observation
and public per-case memory record carry `application_host_reserved_bytes`; result validation checks
its sum with the native peak. No aggregate treats that reservation as a measured peak.

`run-gpu-host-capacity-smoke <pinned-align-checkout>` uses that pin's existing `alloc-count`
requested-live-byte probes in an isolated test runtime, without changing the managed release.
It measures both resident model loaders, observed and diagnostic generation at a 2 MiB cap,
refuses 512 KiB before upload, rejects an oversized pack index before its columns, and measures
32 MiB artifact staging at a 34 MiB cap. The probe covers Align buffers/builders/C-owned payload;
native owner counters independently cover native metadata/staging. It is a focused owner, not an
aggregate addition or a production runtime ABI dependency.

### Bounded prefill repair (review R5; implementation contract)

Production tries widths `128,64,32,16,8,4,2,1`, clipped to prompt length with duplicates skipped.
Admission evaluates the same metadata-only graph for every chunk (including its final/tail shape)
and every reachable decode bucket before model payload allocation/upload. It may retry a smaller
width only for a capacity refusal; unsupported operations and malformed shapes remain terminal.
A discarded planning attempt releases all metadata and clears only its internal capacity refusal;
no upload or execution may have occurred. The first width that fits host and device capacities wins.
No timing search or per-request backend autotuning is introduced. Width and chunk count are native
observations, distinct from generated positions. The production host mask reservation uses that
physical width. The previous exact request KV capacity and decode bucket policy are unchanged.

`runtime_qwen` and `runtime_olmoe` construct a chunk from absolute prompt offset, positive token
count, valid KV prefix and final-chunk flag. Their existing prefill row tables produce contiguous
K/V; a native `align_gpu_kv_write_prefix` uses pinned `ggml_set_inplace` to write resident K/V and
returns a dependent prefix view. It validates F32 contiguous inputs, both layout axes, capacity,
strides and the pinned SET offset limit before calling ggml. Explicit padding reaches the fixed
attention reduction bucket; masks and RoPE positions use absolute prompt positions. Tokens and
position inputs use bounded views for the final tail. Non-final chunks expand through the highest
layer's K/V writes only: no highest-layer attention/FFN or vocabulary projection is needed for
future tokens. The final chunk selects its last output row and computes one logits vector.
The selected plugin's exact SET operation is included in pre-upload capability admission.

Diagnostic qualification fixes the nominal width `min(128,prompt)`; insufficient capacity refuses
before upload instead of silently changing its canonical traversal. Ordinary production retains
smaller-fit support. Prefill diagnostic frames become chunk-major, then layer-major, using step 0;
non-final chunks contain lower layers only, and the final chunk includes the single highest-layer
output. Routers stay token-major within each layer. The CPU diagnostic emitter slices its complete
prefill observations into that same canonical order without changing CPU arithmetic. Production
logits and all decode frames retain their existing order. This repairs unreleased stream schema 1;
historical failed evidence remains owned by its captured validator and is not rewritten.

| Owner | Success construction | Refusal / early exit / cleanup | Named evidence |
| --- | --- | --- | --- |
| Native KV prefix and input view, real/stub shim and FFI | dependent resident writes, exact valid prefix, contiguous F32 source and clipped input views | wrong layout/shape/stride/capacity/SET offset refuses before native assertion or compute | real Metal workspace owner; device owner; `gpu-prefill-chunks` |
| Both model builders / generation | absolute masks/positions, bounded full/tail chunks, final-only head, shared shape planning | only capacity retries; cancellation releases graph metadata, preserves the original device; failed execution publishes no partial output | `gpu-prefill-chunks`: one/exact/tail/multiple chunks, causal prefix, context end, smaller-fit and no-fit |
| Diagnostic emitter / traversal / work projection | canonical chunk/layer/token ordering, independent CPU slicing; exact production chunk work | wrong width/order/count/refusal fails qualification; diagnostic nominal-width capacity failure is explicit | provider trace, numeric traversal/compare/replay, both real model corpus owners |
| Host reservation / observation | selected physical query width; actual prefill execution count and chosen width | native peak plus separate application capacity remains within cap for every candidate and final execution | tracked host owner, provider trace |

The capacity decision, final graph diff and numeric reference evidence must be mapped back here
before R5 is marked repaired. No speed claim is made by merely splitting a prompt.

R5 local implementation evidence: `scripts/run-gpu-prefill-chunks-smoke` passes both models at
1/128/129/257/2048 prompt tokens against a deliberately unchunked private test build. Final logits
are byte-identical; diagnostic layer/router streams at 129/257/2048 are byte-identical to the
full capture sliced by the CPU writer. A 262144-byte device cap chooses width 16 in production
and refuses the fixed-width diagnostic before uploads; 1024 bytes refuses production before
uploads. Native work counts are independently projected, and production snapshots admit multiple
prefill executions. The real Metal native owner, device owner, provider trace, tracked host
capacity, traversal, numeric-pair and case-record owners pass. Existing short real Qwen and OLMoE
final-logit comparisons remain bitwise identical to pinned same-device llama.cpp (7 rows each);
this is supplementary evidence, not full real corpus or cross-backend qualification. R6 and the
original numerical acceptance failure remain open.
