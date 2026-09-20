# CPU inference baseline on a named platform profile

Status: contract settled; baseline recorded 2026-09-20 on `linux-x86_64-v1` (section 7).

Register owner: `docs/backend-parity.md` section 6, item C0

## 1. Baseline owned

Item 69 (`docs/specs/r8-olmoe-post-optimization-sampled-runtime-decision.md`) last measured the
legacy per-layer OLMoE CPU path against llama.cpp's CPU server on 2026-09-05, and item 78 repeated
that protocol on 2026-09-06 with the shipped native staging path. Both ran on one Apple M1 host and
both owners are bound to it: `.dylib` library digests, Apple toolchain digests, a Docker validator
identity that Linux resolves as `native`, Align pin `8cefc803`, and, in item 78, an explicit
`EXPECTED_HOST` with `os: Darwin` and a `platform.system() == "Darwin"` refusal. Nothing CPU-side
has been measured since. The item 69 owner additionally no longer runs at current `main`: its
`--self-test` fails with `item 68 source chain drifted`, because one byte-pinned chain file changed
without any change to the workload it defines.

This capability adds one Linux-capable owner that re-establishes the same baseline. It reproduces
item 69's protocol byte-for-byte wherever the protocol is what makes two runs comparable, and
replaces only host-binding identity with a checked-in platform-profile table. It changes no product
behavior and it has no gate: a baseline is not `MET`/`NOT_MET`.

**Results are not comparable across hosts.** Each host class gets its own local arm, its own
runtime arm, and its own paired ratio, measured in the same run under the same balanced pair
schedule. A Linux runtime median may never be compared with a Darwin local median, and neither
absolute median may be carried between profiles. Only the within-run paired ratio and a later run
of the *same* profile on the *same* host are comparable quantities.

## 2. Measurement-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `C0-OLMOE-PLATFORM-SAMPLED-RUNTIME-BASELINE`; `scripts/run-olmoe-platform-sampled-runtime-baseline`, with `--platform-profile NAME` required for the opt-in real run, `--print-identity --platform-profile NAME` for the identity table the current host would need, and `--self-test` for the model-free owner. There is no default profile |
| Consumer | one coding caller seeking the first passing patch from item 69's fixed sampled portfolio through either shipped `ModelProvider` arm, on one named host class |
| Fixed workload inherited byte-for-byte | OLMoE GGUF 4,213,512,192 bytes SHA-256 `4ddc0e53…`; alignpack SHA-256 `20423ebf…` (verified identical on both host classes); task `eval/tasks/coding-v1/python-inclusive-range/task.json` SHA-256 `1884f01a…`; prompt SHA-256 `0b3b037f…`; known-good control patch SHA-256 `5d6b107e…`; maximum 128 completion tokens; temperature 300,000 micros; seeds `[1,2,3,4,5,6,7,8]`; stop on first pass; strict patch extractor; cache budget 975,175,680 bytes; provider arguments; llama-server launch line `-m MODEL --alias olmoe --host 127.0.0.1 --port PORT --device none -ngl 0 -t 4 -c 512 -np 1 --jinja --no-warmup`; `server_threads` 4 and `effective_ggml_threads` 4 (the shim never sets `n_threads`, so the runtime arm runs at ggml's own `GGML_DEFAULT_N_THREADS`, which the pinned ggml defines as 4 in `ggml/include/ggml.h`) |
| Pair schedule | `(local,runtime)`, `(runtime,local)`, `(runtime,local)`, `(local,runtime)`; one synchronous arm at a time; one fresh pinned local server per local portfolio |
| Isolation/lifetimes | inherited from item 69 exactly, through `measure_local_isolated` and `measure_runtime_isolated`: zero matching processes before local; one ready solely owned server alive through its portfolio; terminate, reap, prove zero matches; zero matching processes before and after every runtime portfolio, including failure cleanup |
| Page cache | both fixed inputs (GGUF and alignpack) are read once end-to-end before the pair loop, inside the ceiling, and the elapsed time is recorded as `page_cache_preload_ns`. `Buffers`, `Cached`, `SReclaimable`, the `free -g` buff/cache GiB computed from them, and the raw `LC_ALL=C free -g` `Mem:` line are recorded immediately before and after each of the eight legs. Where `/proc/meminfo` does not exist the structured fields are `null` |
| Primary metric | nanoseconds from each portfolio leg's first provider-helper launch through validation of its first passing patch; local server startup/readiness and teardown remain excluded |
| Gate | **none**. The result carries `"gate": "none"` and `"comparable_across_hosts": false`. `aggregate.verdict` is the inherited reduction and is retained byte-identical so the numbers stay comparable with item 69's reduction; for this owner it is informational and carries no `MET`/`NOT_MET` authority |
| Identity split, protocol-essential | model bytes/SHA-256, pack SHA-256, task SHA-256, prompt SHA-256, known-good patch SHA-256, budget, alias, pair orders, seeds, temperature, maximum tokens, thread counts, and the 25-minute ceiling are fixed constants of this owner and identical on every profile |
| Identity split, profile-keyed | `os`, `architecture`, `align_revision`, `compiler_sha256`, `c_compiler_sha256`, `c_compiler_version_sha256`, `linker_search_sha256`, `ggml_libraries`, `geometry_sha256`, `server_sha256`, `server_version`, `validator_kind`, `validator_image_id`, `validator_interpreter_sha256`, `validator_interpreter_version_sha256` |
| Persisted identity | the `PROFILES` table checked into the owner is the persisted identity; its schema version is `PROFILE_SCHEMA_VERSION` = 1, recorded in the result as `platform_profile_schema_version` and in the identity document as `schema_version`. The table is committed **before** a timed run; the owner never self-pins at run time. Adding or removing an identity field is a schema-version change |
| Inherited-contract validation | semantic, not a byte pin on the predecessor files: the owner re-derives the eleven-element workload tuple from the imported modules, and asserts that the source of `isolated.measure_local_isolated`, which builds the server argv, still carries `-t 4`, `-c 512`, `-np 1`, `-ngl 0`, `--jinja` and `--no-warmup`. Any drift is refused by name. Byte-pinning the chain is deliberately not repeated, because that is exactly what made the item 69 owner unrunnable at current `main` while its workload was unchanged |
| Result | one exact-key schema-1 `C0_OLMOE_PLATFORM_SAMPLED_RUNTIME_BASELINE` document on stdout and one concise stderr summary; no partial JSON on failure. It is item 69's schema plus `gate`, `platform_profile`, `platform_profile_schema_version`, `comparable_across_hosts`, `page_cache_preload_ns`, a per-sample `page_cache` block, `baseline.server_threads` and `baseline.effective_ggml_threads` in place of `baseline.threads`, `environment.memory_bytes`, and a four-field `validator` that records the native interpreter identity |
| Validation order | arguments and required profile; profile selection; inherited workload contract; prerequisites (six environment variables, else `N/A`); clean worktree and evaluated head; observed identity against the committed profile; validator resolution; known-good validator control; zero matching processes; model, pack, task and prompt identity; page-cache preload; helper/shim build and built-toolchain identity against the profile; four isolated pairs with per-pair schema, isolation, page-cache and determinism validation; zero matching processes; unchanged head and clean worktree; file identity re-verification; observed identity re-checked against the profile; ceiling; result schema; publication |
| Failure | nonzero exit and no complete document for a missing or unknown profile, invalid arguments, missing/unusable inputs, inherited-contract drift, profile identity drift, unclean or changed worktree, validator or provider failure, process/lifetime failure, malformed schema, nondeterministic portfolio, timeout, signal, or ceiling excess. `--print-identity` exits 3 on mismatch after printing the observed table. `NO_PASSING_PATCH` remains measured data |
| Ownership | the owner owns the four local servers, the built shim and helper, the validator workspaces and the temporary work tree; `isolated.stop_owned_processes()` chains termination on signal and on failure. The generated `runtime_provider_gate` is moved out of the work tree and any pre-existing copy restored by the inherited `built_helper` |
| Cost ceiling | one monotonic 25-minute complete-result ceiling, inherited unchanged from item 69 |
| Performance floor | N/A: this is a baseline, not a gate. The inherited 50,000-ppm floor is retained only inside the inherited reduction and decides nothing here |
| Acceptance evidence | author consistency pass; `--self-test` (model-free); `--print-identity --platform-profile linux-x86_64-v1` reporting `MATCH` on the committed table; a bounded plumbing smoke leg (one local candidate and one runtime candidate) before the timed run; `python3 scripts/check-python-boundary --strict`; one clean-head real baseline per profile; `git diff --check`; one comprehensive review; exact-head `scripts/pre-pr` |

Cross-host comparison, GPU, throughput, quality-rate, arbitrary-task, persistent-provider and
general R8 claims are N/A. This is one fixed model, task and sampled portfolio, measured per host
class.

## 3. Profiles

### 3.1 `linux-x86_64-v1`

Observed with `--print-identity` on this repository's Linux host (WSL2, Ryzen 9 5950X, 32 logical
CPUs, 62 GiB) and committed before any timed run.

- Validator kind is `native`: `coding.resolve_validator` returns `native` on Linux, so the Docker
  image identity of the Darwin profile has no meaning here. The interpreter that runs
  `eval/runners/run-coding-task.py` is therefore part of the identity, recorded as
  `validator_interpreter_sha256` (the resolved `sys.executable`) and
  `validator_interpreter_version_sha256` (the digest of its `-VV` output).
- The ggml tree has **nine** `libggml*` files, not six: this build sets `GGML_BACKEND_DL=OFF` and
  `BUILD_SHARED_LIBS=ON`, so the CPU backend is a separate `libggml-cpu.so*` trio that `libggml.so`
  names as `DT_NEEDED` with a `RUNPATH` back to its own directory. No backend search path is
  required and none is configured.
- `server_version` is `version: 0.2.0-dev (build 1, commit bb4caa754)`. The llama.cpp worktree that
  produced this CPU-only build carries no tags, so its generated build number is `1` rather than
  the upstream `10566` the Darwin profile records. The source revision `bb4caa754` is the same. The
  profile therefore records the exact printed string rather than the upstream build number, and the
  owner requires the `version:` line to equal it.
- `linker_search_sha256` is `null`: Linux needs no explicit `LIBRARY_PATH`, and
  `sampled.validate_linker_search` requires one only on Darwin.
- `align_revision` is the current repository `.align-revision`,
  `8c8bfbc7a3169e84ecc8415f5149ab8c61afe863`. The owner refuses drift from it.

### 3.2 `darwin-aarch64-v1`

Carried from the item 69 and item 78 owners so the table is complete. **These values were not
re-verified by this capability.** They belong to Align pin `8cefc803`, so the Darwin profile cannot
pass this owner's pin check until someone re-runs `--print-identity` on that host and commits the
result. `server_version` there is recorded as the carried `build 10566, commit bb4caa754`.

## 4. Closure matrix

| Path | Construction/precondition | Success | Failure/malformed | Early exit/cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- |
| Arguments | `--platform-profile` is required and has no default | the named profile is selected | missing, unknown, empty or unexpected argument rejects | no side effect | `--self-test` command-surface cases |
| Profile table | exactly the 15 identity fields per profile | selection returns the row | a profile with drifted fields rejects | N/A | `--self-test` profile-selection cases |
| Identity | observe the host, compare field by field | zero mismatched fields | any single-field drift rejects and is named | no measurement starts | `--self-test` drift matrix over library digest, compiler digest, Align pin, geometry sha, server version string, server digest, C compiler digest, validator kind, interpreter digest and OS |
| `--print-identity` | same prerequisites, no build and no model run | observed table on stdout, `MATCH` on stderr, exit 0 | `MISMATCH (fields)` on stderr, exit 3, table still printed | no server or model run started (it invokes `scripts/align-toolchain ensure compiler`, `cc --version`, `llama-server --version` and `python -VV` only) | `--self-test` document-shape case; host run recorded in section 6 |
| Inherited contract | re-derive the workload tuple from the imported owners and read back the server launch line | tuple equals the committed contract and every launch-line token is present | any element or launch-line token drift rejects and is named | N/A | `--self-test` mutation of `sampled.MAX_TOKENS`, of the inherited pack digest, and of each of the six launch-line tokens in the observed `measure_local_isolated` source |
| Local leg | zero matching processes, one fresh pinned server | ready, solely owned, alive, terminated, reaped, zero matches after | any lifetime or process-pressure failure rejects | inherited `stop_process` and after-check run in `finally` | inherited item 69 isolation self-test plus the real run |
| Runtime leg | zero matching processes | portfolio measured in-process | any provider or validator failure rejects | after-check runs in `finally` | inherited item 69 isolation self-test plus the real run |
| Validation | native validator with an owned `ALIGN_LLM_TEMP_ROOT` | known-good control passes, candidates classified | an infrastructure exit other than 0/4 rejects | Docker cid cleanup retained for the Darwin profile | control patch in the real run; smoke leg |
| Page cache | preload both inputs, observe around every leg | eight complete observations | a malformed or missing observation rejects the sample | N/A | `--self-test` meminfo parsing and missing-`page_cache` cases |
| Result | build after all identity re-checks | exact-key schema-1 document | extra key, wrong artifact kind, wrong profile, wrong gate, comparable flag, schema version or negative preload rejects | no partial JSON | `--self-test` result-schema mutation matrix over both profiles |
| Ceiling | monotonic clock from the first validation step | elapsed at or below 1,500 s publishes | above it rejects | inherited per-command deadlines already refuse | `--self-test` ceiling and expired-deadline cases |

Public product API ownership, exchanged provider schemas, cache policy, graph arithmetic, numerical
semantics and allocation/move rules are N/A: this is a qualification-only composition of
already-shipped provider behavior.

## 5. Implementation and verification map

1. Add one owner that imports the item 69 chain, owns its own run loop and its own identity
   validation, and never edits the frozen predecessors.
2. Commit the profile table from `--print-identity` before the timed run.
3. Run `--self-test`, `--print-identity`, and one bounded plumbing smoke leg.
4. Run one clean-head real baseline per profile and record the result in section 6, in
   `docs/backend-parity.md` and in `HANDOFF.md`.
5. This baseline authorizes no product change. It is the control that items C1, C2 and C3 of the
   register are measured against, each on its own host profile.

`sampled.measure_candidate` and `sampled.measure_portfolio` are reimplemented in this owner rather
than imported. They call the module-global `sampled.validate_patch`, which runs the validator under
`sampled.decision_environment()`, and that function scrubs `ALIGN_LLM_TEMP_ROOT`. On Linux the
validator resolves as `native` and refuses an external patch without an owned temporary root
("candidate patch escapes the project and temporary roots"), so validation is routed through
`coding.validate_patch`, whose `env=` keyword carries the owned root and which also retains Docker
container cleanup for the Darwin profile. Everything else is imported:
`isolated.measure_local_isolated`, `isolated.measure_runtime_isolated`,
`isolated.validate_isolation`, `isolated.require_no_matching_process`, `isolated.verify_identities`,
`isolated.stop_owned_processes`, `sampled.built_helper`, `sampled.decision_environment`,
`sampled.validate_linker_search`, `sampled.run_process`, `sampled.candidate_command`,
`sampled.validate_candidate`, `sampled.validate_portfolio`, `sampled.validate_repeatability`,
`sampled.aggregate`, `sampled.synthetic_portfolio`, and the `coding` digest, prerequisite,
record-parsing, patch-extraction, library-identity and validator helpers.

No product source, Make target, aggregate membership, platform profile gate, stress suite, corpus,
broad `make ci`, or unrelated benchmark is selected.

## 6. Recorded runs

| Date | Profile | Head | Result |
| --- | --- | --- | --- |
| 2026-09-20 | `linux-x86_64-v1` | `465957d` | Timed baseline `COMPLETE` in 145.24 s of the 25-minute ceiling: local median 11.291 s, runtime median 17.543 s, 4/4 passing in both arms, gain −553,718 ppm, gate `none`. Portable receipt `eval/benchmarks/cpu-baseline-linux-2026-09-20.json`; section 7 |
| 2026-09-20 | `linux-x86_64-v1` | `02e1fc7` + this capability | `--print-identity` `MATCH`; `--self-test` PASS; bounded smoke leg: one local candidate 4.36 s (`INVALID_PATCH`, 52 completion tokens), one runtime candidate 15.95 s (`PASS`, 81 completion tokens, patch SHA-256 `5d6b107e…`, native validation 0.345 s), page-cache preload 4.11 s |
| 2026-09-06 | `darwin-aarch64-v1` | item 78 | 84.062 s runtime vs 14.174 s local; carried, not re-verified here |
| 2026-09-05 | `darwin-aarch64-v1` | item 69 | 91.4 s runtime vs 14.0 s local; carried, not re-verified here |

## 7. Result (2026-09-20)

WSL2, Ryzen 9 5950X (32 threads), 62 GB, Align pin `8c8bfbc7`, committed head `465957d`, run via
`scripts/run-olmoe-platform-sampled-runtime-baseline --platform-profile linux-x86_64-v1`.
`--print-identity --platform-profile linux-x86_64-v1` returned `MATCH` (exit code 0) immediately
before the timed run. Result `C0_OLMOE_PLATFORM_SAMPLED_RUNTIME_BASELINE`, status `COMPLETE`,
elapsed 145.24 s of the 25-minute ceiling. Validator kind `native`; `comparable_across_hosts`
`false`; `effective_ggml_threads` 4 on both arms. The portable receipt is
`eval/benchmarks/cpu-baseline-linux-2026-09-20.json`: every measured value of the run, with the
digest of the raw receipt, which is retained outside Git.

| Arm | Pass count | Selected seed | Per-pair times | Median |
| --- | --- | --- | --- | --- |
| Local `llama-server` (CPU-only shared build `bb4caa754`, GCC 14.2.0, `-ngl 0 -t 4 -c 512 -np 1`) | 4/4 | 5 | 11.85 s, 11.06 s, 11.20 s, 11.38 s | 11.291 s (11,291,128,206 ns) |
| Runtime (legacy per-layer CPU path) | 4/4 | 1 | 18.55 s, 16.82 s, 17.44 s, 17.64 s | 17.543 s (17,543,227,406 ns) |

Aggregate: local 4/4, runtime 4/4, gain −553,718 ppm, runtime faster in every pair false; gate none
(baseline). The ratio of runtime median to local median is 1.55x.

Per-candidate note: the runtime arm passed with one 81-completion-token candidate, while the local
arm needed five candidates to reach its passing seed. Over the four pairs the runtime arm's single
candidate cost a mean 17.30 s of command wall against the local arm's mean 2.08 s per candidate, so
the cost is about 8x per candidate (8.3x on this receipt; about 5.6x per completion token, since the
arms emit 52–55 versus 81 tokens). The time-to-passing-patch ratio is smaller only because the
runtime happens to pass at seed 1 on this host while the local arm needs five candidates. Platform
floating-point divergence changes which seed passes, which is why this result is not comparable to
the Darwin M1 result (item 78: 84.06 s vs 14.17 s).

Limits: this is a baseline only, with no `MET`/`NOT_MET` decision, and it is not comparable across
hosts. C1 (thread-count) and C2 (application-item) changes must be paired against this baseline
with the same owner, on the same `linux-x86_64-v1` profile.
