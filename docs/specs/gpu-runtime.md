# G1 GPU runtime: resident Metal and CUDA generation

Status: design only, 2026-09-06. No GPU capability is implemented by this change.

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
available validation hosts are an Apple M1 / 16 GiB Mac and the user's RTX 4070 Ti PC. These device
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
| `GPU_RUNTIME_EVIDENCE` | 8 MiB result; 0–256 cases and 0–4,096 retained files |
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
Expected IDs are the same-build CPU result and may be empty only for immediate EOG.
Expected output is the exact generated UTF-8 byte sequence for those IDs. Its digest is SHA-256 of
those bytes with no added LF; both CPU repeats and both GPU repeats reproduce the bytes and digest.

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
  strings nonempty and both byte observations positive. `device_state="unavailable"` requires four
  empty strings and two zeroes, is valid only in FAIL evidence, and truthfully represents discovery
  failure before a device identity exists.
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
and a nonempty output digest. Every other terminal uses a nonempty category/stage. `FAIL` has a
nonzero exit code or null when no child started and a null signal; `TIMEOUT` and `MISSING` use null
exit/signal; `CRASH` uses a nonzero exit and null signal; `SIGNAL` uses a null exit and positive
signal. A spawned row always names its command and two log paths. Output digest is nonempty only
when a complete validated output existed before the later failure. Numeric is
`compared,expected_scalar_count,actual_scalar_count,expected_layer_count,actual_layer_count,expected_router_boundary_count,actual_router_boundary_count,expected_final_logit_count,actual_final_logit_count,max_absolute_f64_bits,max_relative_f64_bits,near_tie_count,mismatch_count`.
False requires zero bit patterns/counts and true permits an exact zero error result. CPU rows require
`compared=false`; GPU rows compare against the adjacent same-repeat CPU row and require true. The
expected counts are independently derived from model geometry and case token widths. PASS requires
every actual count to equal its expected count, positive scalar/layer/final-logit counts, zero Qwen
router boundaries and positive OLMoE router boundaries.
Scalar/final-logit counts include both the diagnostic teacher-forced comparisons and production
logits already read at every sampling position, including an EOG decision. These are separate
comparison positions even when their token prefixes coincide. Layer/router counts describe only
diagnostic replay. Errors, nonfinites and mismatches aggregate both paths; neither may hide the
other's failure. Production logits compare to the adjacent CPU run at the same actual token prefix;
divergent generated IDs fail the existing output contract rather than comparing unrelated positions.

`placement` is
`expected_model_operations,gpu_model_operations,cpu_model_operations,expected_layers,gpu_layers,cpu_layers,expected_experts,gpu_experts,cpu_experts,expected_weights_device_bytes,minimum_weights_device_bytes,expected_kv_device_bytes,minimum_kv_device_bytes,expected_weight_upload_count,weight_upload_count,weight_upload_bytes`.
Counts cover only model graph operations from embedding through output projection; tokenizer,
prompt construction, sampling, EOG control and text decode are explicitly outside them. The
reviewed production graph trace derives the three expected counts from exact model geometry,
prompt width, output selection and generated steps; diagnostic teacher-forced work is excluded.
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
`transfers` is
`host_to_device_bytes,device_to_host_bytes,unexpected_device_to_host_bytes,wait_count`. The
unexpected value counts bytes outside declared final-logit and compact-routing readbacks and must
be zero for PASS. Production resident generation does not read routing decisions back to the host;
the compact-routing allowance applies only to diagnostic replay below. `memory` is
`managed_host_peak_bytes,managed_device_peak_bytes,uma_alias_peak_bytes,rss_peak_bytes,driver_peak_bytes`;
the driver value is integer or null when unavailable. `timing` is
`wall_ns,load_ns,ttft_ns,prefill_ns,decode_ns,device_ns,transfer_ns,wait_ns`; wall is positive for a
started case, and other fields are nonnegative integer or null when unavailable. Overlapping
observations are not summed into wall.

`Command` is `kind,argv,environment,sha256`, where kind is
`compiler_materialize|runtime_materialize|candidate_build|shim_build|cpu_reference_build|case`.
The runner resolves every executable by its verified
absolute path, starts from an empty environment, and inserts exactly `HOME=<owned-empty-home>`,
`LC_ALL=C`, `TMPDIR=<owned-temp>`, and `TZ=UTC`, in that canonical name order. No ambient name
survives: in particular `PATH`, compiler/linker flags and search paths, cache variables and
`CUDA_VISIBLE_DEVICES` are unset. Compiler/SDK inputs are absolute verified argv; runtime artifacts
are loaded only from the invocation-owned private staged absolute paths, so loader search variables
are unnecessary. These fixed sources override rather than merge with the parent environment.

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
FAIL detail. Elapsed time is positive and includes validation through cleanup/publication.

PASS requires every profile case present and passing, both model holdout sets passing on GPU,
nonzero GPU operations, exact expected output bytes, complete numeric comparison coverage,
weights/KV resident within budgets, one retained device binding per weight tensor, no undeclared readback, exact
source/input rechecks and safe cleanup. FAIL may contain zero or a profile-order prefix of case rows; missing suffix rows are
represented by the top-level failure rather than fabricated timings. The CLI returns zero only for
PASS.

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

The native producer API below is planned and blocked by Request 61 in `docs/align-requests.md`.
The Python reader/comparison work may proceed under `gpu-numeric-stream-reader`; no consumer uses
hypothetical handle projections. `gpu-numeric-stream` remains the planned combined native owner.

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

`gmake gpu-numeric-stream` owns construction/return/drop, inactive recording, exact golden bytes,
occupied path, shape/nonfinite/byte-budget refusal, poisoned and finished transitions, and the
Python reader's chunk/ordinal/footer/model/link/mutation/early-exit refusals. The source writer and
reader are checked against the same byte vector independently. `gpu-generation-smoke` will own
the production logit hook and reservation; full layer/router production remains in the G1 numeric
case integration. No performance claim or additional aggregate membership is introduced.

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
| evidence/publication | canonical positive codecs, complete align-llm/ggml Git snapshots, available/unavailable build/device identities, exact argv/environment | duplicate/oversize records, source/tree mismatch, ambient-environment injection, compile/crash/timeout, >4,096 files or >512 MiB projected closure | kill/reap owned group, retain bounded diagnostics, replay before exclusive rename; `gpu-schema-codec`, `gpu-source-replay`, `gpu-build-failure-evidence`, `gpu-command-environment`, `gpu-process-cleanup`, `gpu-evidence-publication`, `gpu-result-replay` |

The native resource starts as an invocation-local root and is never returned or placed in an Align
collection. Owners cover construction, move with source nulling, borrow, replacement, early return
and `?`, each construction prefix, explicit completion, ordinary Drop and poisoned cleanup in
whole-program and per-unit builds. A failure that cannot prove safe native unload performs one
explicit terminal transfer of the native handles and staging tree into the native process-state
quarantine before disarming invocation cleanup; no ordinary success or safely released failure can
enter it. GPU/GPU entrypoint pairs serialize by rejection before native side effects; CPU/GPU pairs
are independent except for ordinary host resource contention. Independent processes have
independent registries, quarantine states and admission guards.

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

Each GPU case helper first executes the production path, then an explicitly diagnostic replay with
the same build, model, prompt, sampler inputs and attention policy. The replay may expose layer and
router tensors for complete numeric comparison against the adjacent CPU reference. Case output,
placement, transfer, memory and timing fields describe production execution. `numeric` includes
production-logit and diagnostic internal/logit comparisons as defined in §3.8. Check all production
logits already read for sampling against the adjacent CPU reference with the same frozen scalar
tolerances and nonfinite policy. Matching generated IDs alone cannot qualify production fusion;
diagnostic output markings may disable that fusion. No extra intermediate readback is required.
The case command owns both passes, the case deadline and overall elapsed time include both,
and either pass failing makes the case FAIL. Diagnostic output must match the production output.
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
