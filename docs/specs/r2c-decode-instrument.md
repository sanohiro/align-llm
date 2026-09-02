# R2C-DECODE-INSTRUMENT

Status: implementation contract, 2026-08-28

## 1. Decision and boundary

R2A proved two limitations in llama.cpp's unmodified `llama-eval-callback` at build 10566: it
prints only the first and last three entries of each tensor axis, so an `ffn_moe_topk` width above
six loses router slots, and it evaluates the prompt once without evaluating any generated token.
Those limitations leave R2c's decode measurement open and prevent R6 from obtaining a real sequence
of decode graphs. This capability ships the smallest external measurement dependency that removes
both limitations:

- llama.cpp is pinned to commit `bb4caa7540188872173c44d161602d9271386413`;
- one checked-in patch changes only `common/debug.cpp` and
  `examples/eval-callback/eval-callback.cpp`;
- the existing R2A parser admits either build-10566's compact axes or R2c's full router axes and
  reports which form it actually observed;
- one managed, out-of-tree tool builds and verifies `llama-eval-callback`; and
- a deterministic smoke owns the pin, patch, tool contract, and refusal paths, while a focused
  qualification owns a real compiled instrument and the R2A parser boundary.

The patch is an align-llm measurement instrument, not a forked runtime and not an upstream API
promise. No llama.cpp source or generated binary is committed. R2c originally left R2A's
`R2_ACTIVATION_TRACE` at schema 1 because graph segmentation, the three-valued phase rule,
selection identities, and truncation fields already described the additional observations.
R8-SCORE-BASED-CACHE advances that document to schema 2 and adds the selected router weight to each
row; this instrument now exposes both router families in full for that consumer. The R2A prose said
a patched transcript needed no parser change, but its implementation enforced exactly six values
whenever an axis exceeded six and derived both truncation flags from extent alone. R2c corrected
that contradiction as part of the same consumer boundary; otherwise the shipped patch would
produce a transcript the shipped client rejects.

This capability does not yet claim decode locality, choose an R6 KV layout, add a runtime
dependency to an Align module, capture a multilingual/task/repository corpus, or alter an existing
R2/R3 qualification silently. Those are consumers of the instrument. The first next consumer is a
bounded R6 decode workload and TTFT baseline.

The proportional design gate is triggered because this adds a fetched external source/build
boundary, a persistent cache identity, and a coordinated invariant across the pin, patch, builder,
smoke, qualification, and documentation.

## 2. Public-contract ledger

### 2.1 Checked-in identities

| Field | Contract |
| --- | --- |
| Upstream pin | `.llama-revision` is exactly one lowercase 40-hex SHA followed by LF. Its value is `bb4caa7540188872173c44d161602d9271386413` |
| Patch | `patches/llama.cpp/r2c-decode-instrument.patch`, LF zero-context unified diff, applies with `git apply --unidiff-zero` to a clean checkout at the pin |
| Patch scope | Exactly `common/debug.cpp` and `examples/eval-callback/eval-callback.cpp`; no third tracked path and no untracked source path is admitted |
| Patch identity | SHA-256 `32fb1eb9dd6a24d2e9a503c8b30bc3a65a8ed4c4866179296e25bbe31afc502a`, 2,610 bytes |
| Cache generation | `r2c-v2`. A generation change is required for any incompatible cache layout, build recipe/flags, or verification rule; v2 adds the explicit Metal-off recipe and HEAD-relative tracked-source admission |
| Effective cache identity | generation + full upstream SHA + full patch SHA-256. Two patches at one upstream commit cannot alias |
| Instrument contract | llama.cpp build number 10566 and short commit `bb4caa7`; both are passed explicitly to CMake because a one-commit fetch cannot derive the historical build count |

The revision and patch are independent inputs. Updating either requires updating this ledger,
re-running the focused qualification, and reviewing the external diff. A patch digest change with an
unchanged ledger is a hard verification failure, not an implicit new build.

### 2.2 Instrument behavior

The patch has exactly two semantic changes.

1. `common_debug_cb_eval` retains the upstream print limit of three for every tensor except the
   exact node families `ffn_moe_topk` and `ffn_moe_weights` (the name is either the family itself or
   the family followed by `-`). For those families the limit is the largest tensor extent, so every
   axis is printed in full. This admits every router identity and its aligned selected weight without
   increasing unrelated tensor output. Transcript size remains caller-owned and the qualifications
   retain file and time bounds. R8-SCORE-BASED-CACHE owns the added weights consumer contract.
2. After the original prompt `llama_decode`, a positive common `--predict` / `-n` value is the
   maximum number of additional one-token `llama_decode` calls. Each iteration samples from the
   current logits using the existing common sampling parameters, stops before decoding an EOG token,
   accepts a non-EOG token into that sampler, and decodes it as a batch of one. An omitted, zero, or
   negative value preserves the upstream one-prefill-graph behavior. Decode failure returns the
   example's ordinary nonzero status.

Thus `-n N` means “at most N observed generated-token decode graphs” for this measurement example;
it does not promise exactly N when EOG occurs. A qualification that needs N graphs selects a fixed
model, prompt, seed, and expected graph count. The instrument emits no new delimiter or schema.

The already-recorded R2 locality and R3 residency gates are intentionally prefill-only. Their
runners used `-n 1` only because the unpatched example ignored it; both now pass explicit `-n 0` so
decode cannot enter those replays. Their recorded denominator is also the unpatched compact
first/last-three router-slot sample, so both share a document admission check that rejects R2c's
full-axis output instead of silently recomputing an old verdict over eight slots. Historical replay
therefore requires an unpatched compact-axis instrument. `run-r2c-instrument-qualification` is the
owner of positive-`-n` and full-axis capture.

### 2.3 R2A parser adoption

For `ffn_moe_topk` axes 0, 1, and 2, the value-block grammar accepts exactly one of two complete
forms. Every other tensor retains the compact build-10566 grammar:

- **compact**: when the extent exceeds six, three values, the existing axis-specific ellipsis, and
  the last three values; or
- **full**: exactly `extent` values and no ellipsis.

An extent of six or less has only the full form. A full axis above six on a non-router tensor, an
ellipsis anywhere except after the first three values, a compact form with other than six values, a
full form with other than `extent` values, or mixed compact/full routing rows remains
`R2_ROW_COUNT`. Slot form is consistent across the transcript, token form across the applicable
non-reduced blocks of one graph, and axis-2 slice form across every applicable group and block.
Axis 3 is unchanged because build 10566 never truncates it.

Before an ellipsis, a row ordinal is its axis index. After an ellipsis, the existing three-plus-three
mapping applies. With no ellipsis, every ordinal is its exact index. This rule applies independently
to router slots and token rows, so `selections.slot` and `selections.token` require no schema change.

`moe.slots_truncated` is true only when an accepted `ffn_moe_topk` slot axis actually carried an
ellipsis. Each graph's `tokens_observed`, `tokens_truncated`, and `observed_token_indices` report the
accepted non-reduced `ffn_moe_topk` token-axis form when one exists; a dense graph or graph without
router observations retains the entry tensor's build-10566 compact form. Existing unpatched
transcripts therefore remain byte-for-byte stable, while an R2c transcript with extent eight emits
eight slot rows, `slots_truncated: false`, and indices 0 through 7.

The parser refuses inconsistent print forms rather than taking a union whose denominators differ by
layer. A token-reduced tail layer remains excluded under R2A's existing rule and cannot change the
graph's print-form decision.

### 2.4 Managed tool surface

`scripts/llama-eval-callback-toolchain` is the only managed builder. Its CLI is:

```text
scripts/llama-eval-callback-toolchain path source|instrument
scripts/llama-eval-callback-toolchain ensure source|instrument
scripts/llama-eval-callback-toolchain verify
scripts/llama-eval-callback-toolchain attest instrument
```

| Surface | Result |
| --- | --- |
| `path KIND` | Prints the absolute expected path and performs no fetch, build, verification, or write |
| `ensure source` | Under one identity lock, returns a previously verified cache entry or fetches, patches, builds, verifies, atomically installs, and prints its source path |
| `ensure instrument` | Same materialization, then prints the executable path |
| `verify` | Read-only verification of the existing entry; prints the full upstream SHA on success |
| `attest instrument` | Runs `verify`, then emits one JSON object containing schema version, generation, upstream SHA, patch SHA/bytes, source/instrument paths, instrument SHA/bytes, and the two-line `--version` output |
| Failure | Nonzero status, no stdout contract, and one diagnostic prefixed `llama-eval-callback-toolchain:` on stderr |

The attestation schema version is 1. Paths are evidence about this materialization, not portable
identity; the two source digests and instrument digest are the identities. Instrument bytes may
differ by platform/compiler, so no cross-platform binary digest is promised.

### 2.5 Inputs, defaults, and prerequisites

| Input | Default | Validation and meaning |
| --- | --- | --- |
| `ALIGN_LLM_LLAMA_TOOLCHAIN_ROOT` | unset | Absolute cache base; non-empty, no whitespace/NUL. When set, generation is appended. The resolved result must be outside this checkout |
| `XDG_CACHE_HOME` | unset | If the explicit root is unset, absolute base for `align-llm/llama.cpp`; same lexical and resolved checkout-containment rules |
| `HOME` | process environment | Last fallback, producing `$HOME/.cache/align-llm/llama.cpp`; absence, unsafe value, or a resolved result inside this checkout fails |
| `ALIGN_LLM_LLAMA_REPOSITORY` | `https://github.com/ggml-org/llama.cpp.git` | Fetch source; one non-empty argument with no whitespace/NUL. A local repository path is allowed for reproducible offline materialization |
| `CMAKE` | `cmake` | One command path/name with no whitespace/NUL |
| `CMAKE_BUILD_PARALLEL_LEVEL` | CMake default | Passed through by CMake; affects build scheduling, not cache identity or semantics |

`git`, the selected CMake, a C/C++ toolchain, and the selected repository are prerequisites to a
new materialization. `path`, `verify`, and `attest` never fetch. The build is CPU-only and fixed to:

```text
-DCMAKE_BUILD_TYPE=Release
-DBUILD_SHARED_LIBS=OFF
-DGGML_NATIVE=OFF
-DGGML_METAL=OFF
-DGGML_OPENMP=OFF
-DGGML_CCACHE=OFF
-DLLAMA_CURL=OFF
-DLLAMA_BUILD_EXAMPLES=ON
-DLLAMA_BUILD_TESTS=OFF
-DLLAMA_BUILD_NUMBER=10566
-DLLAMA_BUILD_COMMIT=bb4caa7
```

Only target `llama-eval-callback` is built. `GGML_NATIVE=OFF` avoids silently binding the cache to
the machine that first materialized it, and `GGML_METAL=OFF` keeps the CPU-only promise on Apple as
well as other hosts. The cache remains platform-local because compilers, ABIs, and system libraries
are not asserted portable.

### 2.6 Ownership, allocation, and cleanup

The selected cache base resolves to one `r2c-v2` directory outside the align-llm checkout; lexical
or symlink-mediated containment is refused before a path is returned or any write occurs. Under it,
one advisory lock file per effective
identity serializes creators. A completed entry owns sibling `source/` and `build/` directories;
the executable is `build/bin/llama-eval-callback` (with `.exe` on Windows, although Windows is not a
qualified platform in this capability). The tool never writes inside align-llm.

A creator builds in a newly allocated staging directory under the same generation directory and
renames the whole entry only after verification. Fetch, checkout, patch, configure, compile, or
verification failure recursively removes only that resolved staging directory. It does not delete
an existing cache entry. A destination appearing before rename is a controlled failure. Lock files
may persist and carry no build state.

An existing entry is never repaired in place. Wrong revision, staged or unstaged patch drift, extra
source files, missing/non-regular output, a symlinked source/build boundary, or version drift fails
closed so a caller cannot mistake mutable local state for the pinned instrument.

### 2.7 Validation order

Every command first parses its fixed CLI, then reads and validates `.llama-revision`, then validates
the checked-in patch bytes/digest, then resolves the cache root and effective identity. `path` stops
there. `ensure` acquires the identity lock before inspecting or creating the entry. `verify` and
`attest` do not acquire a creation lock and are read-only; they may fail while another process has
not yet atomically installed an entry, but can never see its staging tree as the destination.

Entry verification is ordered as follows:

1. entry, `source/`, and `build/` are real directories and not symlinks;
2. source `HEAD` equals `.llama-revision`;
3. the source has no untracked path, including a path matched by an upstream ignore rule;
4. its tracked diff is byte-identical to the checked-in patch;
5. the instrument is a regular executable file, not a symlink;
6. `--version` exits zero and contains exact build 10566 and commit `bb4caa7` markers.

Attestation hashes outputs only after all six checks pass.

## 3. Verification contract

### 3.1 Deterministic owner

The deterministic owner is `scripts/run-r2c-instrument-smoke`, `make expert-trace-smoke`, and
`make residency-sim-smoke`, in that order. The first requires no network, model, compiler, or
cached llama.cpp tree; it loads the tool module in-process, uses temporary paths and controlled
subprocess answers, and owns:

- exact pin and patch digest/size/scope;
- cache identity, path derivation, and the exact CMake recipe;
- CLI arity and kind refusal;
- absolute/safe cache and repository inputs, including checkout containment through symlinks;
- exact entry validation order and each refusal class;
- attestation fields and file digests;
- existing-entry reuse, atomic staging publication, collision refusal, and cleanup after each
  injected preparation failure; and
- patch semantics by checking the external diff contains the two named source files, the exact
  family guard, unchanged default limit, sampling loop, EOG stop, and one-token decode.

The existing parser owner adds full-slot, full-token, mixed slot/token/axis-2 form,
misplaced-marker, short-full, overlong-full, and non-router-full fixtures. Its independent Python
oracle derives indices and truncation flags from the fixture's selected print form rather than
importing the Align implementation. The locality owner proves a full-axis schema-1 document is
refused by the shared historical compact-axis admission, and the residency wrapper reuses that
check after invoking its selected compact instrument with explicit `-n 0`.

All three commands form the publication owner passed to `scripts/pre-pr`. No new target is added to the
`Makefile` or any aggregate: the parser owner is already hosted, and R2c's fetched measurement
dependency must remain opt-in. Keeping aggregate topology unchanged also avoids invalidating the
unrelated canonical coding baseline.

### 3.2 Focused compiled qualification

`scripts/run-r2c-instrument-qualification` first calls `ensure instrument`, `verify`, and `attest`.
It then runs two halves:

1. **Dense decode half (required).** It uses upstream's SHA-256-pinned
   `tinyllamas/stories15M-q4_0.gguf`, downloading it through the pinned checkout's
   `cmake/download-models.cmake` only when absent. The download targets a unique temporary sibling
   and is hash-validated before atomic rename, so interruption cannot publish a partial cache file.
   With prompt `hello`, seed 42, CPU execution, and
   `-n 2`, the parser must report one prefill graph followed by two decode graphs. Omitted `-n`,
   `-n 0`, and `-n -1` must each report exactly one prefill graph. Model hash, instrument version,
   attestation, graph rows, time bound, transcript size bound, and transcript cleanup are asserted.
2. **MoE full-axis half (capable-host).** `ALIGN_LLM_GGUF_MODEL` names a real MoE GGUF. Unset or
   absent prints one exact N/A line and exits zero after the dense half passes. When present, the
   fixed prompt/seed and `-n 2` capture must parse as `moe: true`, contain at least one decode graph,
   report `slots_truncated: false`, observe `n_expert_used` slots for every retained
   `(graph, layer, token)` selection group, and exercise at least one retained router slot or token
   axis with extent greater than six. The model size and mtime must be unchanged.

Any attempted half that cannot build, download, execute, parse, or meet its assertions fails
nonzero; it never becomes N/A. The qualification makes no latency or locality claim. Its elapsed
time is diagnostic.

## 4. Closure matrix

| Cell | Construction / owner | Exact evidence |
| --- | --- | --- |
| Clean construction | fetch exact SHA, detached checkout, `git apply`, fixed CMake configure/build | smoke controlled prepare; compiled qualification `ensure` |
| Existing success | verify complete entry, return selected path without writes | smoke reuse case; two consecutive `ensure` calls |
| Concurrent construction | one effective-identity advisory lock; second creator re-verifies installed entry | smoke lifecycle-marker and existing-entry reuse cases |
| Fetch failure | staging removed, destination absent, diagnostic names `git` failure | smoke injected fetch failure |
| Wrong fetched revision | refuse before patch/build; staging removed | smoke wrong-revision case |
| Patch does not apply | refuse before configure; staging removed | smoke injected apply failure; compiled qualification on exact pin is the positive |
| Configure failure | staging removed; no destination | smoke injected CMake configure failure |
| Compile failure | staging removed; no destination | smoke injected CMake build failure |
| Verification failure | staging removed; no destination | smoke wrong version/output/diff cases |
| Destination collision | never overwrite or merge; refuse and preserve both existing destination and staging cleanup rule | smoke collision case |
| Malformed pin | refuse before cache resolution | smoke pin grammar cases |
| Patch identity drift | refuse before cache resolution/build | smoke digest and byte-count cases |
| Unsafe cache/repository/CMake input | refuse before subprocess launch, including explicit, XDG, HOME, and symlink-mediated cache roots inside this checkout | smoke environment and cache-boundary cases |
| Symlink or non-directory boundary | refuse before Git/output inspection | smoke boundary cases |
| Dirty or extra source | compare the whole tracked tree to `HEAD`, including staged changes, and refuse extra paths before output/version admission | smoke staged/unstaged tracked-diff and untracked cases |
| Missing/non-regular/non-executable instrument | refuse before running version | smoke output cases |
| Version mismatch | refuse after file admission, before hashing/attestation | smoke version cases |
| Legacy prefill success | omitted/nonpositive `-n` evaluates prompt once | dense qualification omitted, zero, and negative runs |
| Decode success | positive `-n` produces one-token graphs until count or EOG | dense qualification fixed 3-graph result; MoE capable half |
| Decode EOG | stop without decoding EOG; fewer than requested graphs is valid instrument behavior | smoke patch semantic assertion; fixed dense qualification avoids EOG |
| Decode failure | upstream example returns nonzero with decode-step diagnostic | source review; N/A to input-driven qualification because no stable GGUF forces this path |
| Historical prefill gates | R2 locality and R3 residency require one prefill graph per prompt and the original compact router slots; full-axis R2c documents fail rather than changing the recorded demand stream | tool smoke exact `-n 0` and shared compact-admission source assertions; locality full-axis refusal |
| Non-router tensor | upstream print limit remains three | smoke patch semantic assertion; dense transcript remains truncated in the ordinary way |
| Router tensor | all axes printed, no middle slot or token omitted, with at least one applicable extent above the old six-value threshold | MoE capable qualification threshold; new R2A full-axis synthetic fixtures |
| Compact parser input | six values plus exact ellipsis maps to first/last indices; existing document bytes do not change | complete existing expert-trace corpus |
| Full parser input | extent values, no ellipsis, direct indices, false truncation fields | full-slot/full-token fixtures and independent expected documents |
| Mixed/malformed parser input | misplaced marker, short/long full axis, non-router full axis, or inconsistent slot, token, or axis-2 routing form is `R2_ROW_COUNT` | focused malformed fixtures |
| Transcript overflow / timeout | bounded capture fails nonzero and temporary transcript is removed | qualification implementation review; successful qualification reports both files below the bound |
| Tiny-model download failure | partial bytes remain only below a unique temporary sibling and are removed; the final cache path stays absent and a retry can succeed | smoke interrupted-download then retry case |
| Normal cleanup | every transcript/document temp tree removed; managed cache retained | qualification post-run assertion |
| Signal / early exit | qualification temporary context removes its tree; tool preparation `finally` removes staging | smoke injected `KeyboardInterrupt` cleanup; qualification source review |
| Attestation | only admitted entry hashed; JSON includes every ledger field | smoke attestation case; compiled qualification records output |

## 5. Acceptance and handoff

The capability is complete when:

1. the ledger-to-prose consistency pass is clean;
2. the checked-in patch is byte-identical to the diff of the exact pinned source;
3. deterministic tool smoke and the extended `expert-trace-smoke` pass with no network or
   pre-existing llama.cpp cache;
4. a fresh managed build passes `verify` and emits a schema-1 attestation;
5. dense qualification proves legacy one-graph and patched multi-graph behavior through
   align-llm's existing parser;
6. the real OLMoE capable half either passes on a host holding the already-named model or is
   recorded as exact N/A without weakening items 1-5;
7. one comprehensive review covers the pin, external patch, builder security/cleanup, verification
   oracle, and this contract; and
8. exact-head executable preflight passes with the three-command deterministic owner.

After merge, `main` refreshes and R6 may consume
`scripts/llama-eval-callback-toolchain ensure instrument` as its pinned decode-graph source. R6 must
still define its own workload identity, KV persistence boundary, invalidation rules, TTFT metric,
and local baseline before implementation.
