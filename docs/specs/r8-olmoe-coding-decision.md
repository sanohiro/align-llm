# R8 OLMoE coding decision

Status: measured implementation candidate, 2026-09-03

## 1. Decision and boundary

R8 now exposes the partial-LRU OLMoE runtime through `ModelProvider`, but the byte reduction that
selected that cache is not an end-to-end performance result. This capability measures the first
real consumer question: whether the shipped in-process OLMoE provider reaches a passing patch
faster than the pinned local llama.cpp provider on the existing `python-inclusive-range` task.

The capability adds a reproducible measurement owner and records one decision. It does not change
provider behavior, runtime arithmetic, cache policy, public product CLI/API, task content, or model
output. A negative result is a valid investment decision and does not fail publication; malformed
evidence, identity drift, nondeterministic output, or an incomplete run does.

This document owns the performance protocol and pre-implementation cost ceiling. The existing
provider, coding-task, `GenerationRecord` schema 2, and OLMoE correctness contracts remain
authoritative for their surfaces.

## 2. Measurement-contract ledger

| Field | Settled contract |
| --- | --- |
| Capability | `R8-OLMOE-CODING-DECISION` |
| Consumer | one fixed coding task run through the shipped local OpenAI-compatible and `AlignRuntime` OLMoE provider arms |
| Task | checked-in `eval/tasks/coding-v1/python-inclusive-range/task.json` and R7's exact one-file prompt and patch extractor |
| Subject model | `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 4,213,512,192 bytes, SHA-256 `4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f` |
| Baseline | llama.cpp build 10566 commit `bb4caa754`, loopback server, CPU-only, four threads, context 512, no server warmup |
| Candidate | shipped in-process `AlignRuntime`, exact clean align-llm head and managed pinned compiler, measured helper/shim/ggml identities, exact supplied AlignPack and geometry, invocation-local LRU budget 975,175,680 bytes |
| Request | identical system/user text, greedy temperature zero, no seed, maximum 128 completion tokens |
| Opt-in inputs | `ALIGN_LLM_OLMOE_MODEL`, `ALIGN_LLM_MOE_ALIGNPACK`, `ALIGN_LLM_MOE_GEOMETRY`, `ALIGN_LLM_GGML_INCLUDE`, `ALIGN_LLM_GGML_LIB`, and `ALIGN_LLM_LLAMA_SERVER` |
| Samples | four pairs in fixed leg orders `local,runtime`, `runtime,local`, `runtime,local`, `local,runtime` |
| Primary metric | per-leg time to a passing patch: monotonic wall time from helper launch through successful existing task validation |
| Diagnostics | provider-owned `GenerationRecord.elapsed_ns`, validation elapsed time, completion token count, patch SHA-256, and total command wall time |
| Success result | every leg returns an OK schema-2 record, admits one complete fixed-task patch, passes the existing validator, and is deterministic within its provider arm |
| Gate floor | `MET` only when all eight legs succeed, candidate time is lower in every pair, and candidate median time to a passing patch is at least 50,000 ppm below baseline median |
| Negative results | `NOT_ELIGIBLE` when either arm does not reach a passing patch in every sample; otherwise `NOT_MET` when timing misses the floor or pairwise direction |
| Validator control | before model/server work, the existing exact known-good one-line patch must pass once; later ordinary generated-patch rejection is a measured no-passing-patch outcome |
| Result | canonical `R8_OLMOE_CODING_DECISION` schema 1 JSON on stdout plus one concise stderr summary; no result is committed as a machine-local artifact |
| Failure | nonzero exit for prerequisite or mid-run identity drift, malformed records, nondeterminism, timer/accounting errors, validator infrastructure failure, cleanup failure, or ceiling excess |
| Ownership | the runner owns the server process, temporary shim/helper/results/patches, and validation workspaces; all are released on every exit |
| Persisted/cache identity | N/A: the supplied model/pack/geometry are immutable inputs; the runner creates no reusable runtime cache or committed result |
| Owner | `scripts/run-olmoe-coding-decision --self-test`; real decision is `scripts/run-olmoe-coding-decision` with the named opt-in environment |
| Cost ceiling | approximately 15 minutes for the complete four-pair real decision, including one build and server startup; stop and diagnose material excess |

The 50,000-ppm floor is fixed before measurement. It is intentionally modest because the primary
metric includes validation and provider boundary work in addition to inference, but it still
requires a material end-to-end reduction and forbids a win that exists only in the median while
one fixed pair regresses.

Server construction, model identity hashing, helper compilation, and temporary shim construction
are setup diagnostics outside each sample. The baseline server remains resident across samples;
this matches the existing local-provider deployment. `AlignRuntime` retains its shipped
per-invocation validation, model mapping, cache construction, and teardown, all of which are inside
the candidate sample because a real caller pays them. The comparison therefore measures shipped
provider configurations rather than claiming equal internal kernel or residency strategies.

Median for four values is the integer floor of the sum of the two middle sorted values divided by
two. Gain is `(baseline_median - candidate_median) * 1_000_000 // baseline_median`; durations must
be positive and the baseline median must be nonzero. A leg that does not reach a passing patch has
no primary duration and cannot contribute a synthetic infinity or zero.

## 3. Schema 1 result

The canonical JSON object has these ordered semantic groups:

```text
schema_version: 1
artifact_kind: "R8_OLMOE_CODING_DECISION"
status: "COMPLETE"
model: {bytes, sha256, architecture}
baseline: {provider, runtime_identity, server_sha256, threads, context, warmup}
candidate: {provider, align_llm_head, align_revision, compiler_sha256, helper_sha256, shim_sha256,
            ggml_libraries: [{name, bytes, sha256}], pack_sha256, geometry_sha256,
            cache_budget_bytes}
task: {task_id, task_sha256, prompt_sha256, maximum_completion_tokens}
validator: {kind, image_id}
environment: {os, release, architecture, cpu_count, c_compiler_sha256,
              c_compiler_version_sha256}
samples: [{pair_index, order, local, runtime}]
aggregate: {local_pass_count, runtime_pass_count, local_median_time_to_passing_patch_ns,
            runtime_median_time_to_passing_patch_ns, gain_ppm, candidate_faster_in_every_pair,
            verdict}
elapsed_ns: integer
```

Each leg object contains `status` (`PASS` or `NO_PASSING_PATCH`), schema-2 provider elapsed time,
command wall time, validation elapsed time, nullable time-to-passing-patch, completion token count,
output SHA-256, and patch SHA-256. Output text, paths, server logs, model bytes, and credentials are
never embedded.
`NOT_ELIGIBLE` uses null medians and null gain when an arm has fewer than four passing samples;
`NOT_MET` and `MET` contain all three integers.

The runner requires a clean worktree and records its exact align-llm head together with input
digests and environment facts, so its numbers cannot be moved to different provider source, model,
task, prompt, compiler pin, or host by relabeling. It is evidence emitted by the runner, not a new
product interchange format or a promise of cross-host equivalence.

The real runner removes Align/compiler selection, shim fault injection, backend discovery, and
common math-thread overrides from the child environments. It resolves only the managed compiler for
`.align-revision`, records the actual compiled helper, shim, C compiler, and every named ggml
library, and re-hashes all executable/model/pack/toolchain inputs after the samples. On non-Linux
hosts it resolves the configured validator image to one immutable Docker image ID before the
control, uses only that ID, and owns the container ID through timeout, interruption, and cleanup.

## 4. Closure matrix

| Cell | Measurement runner | Helper/provider | Evidence |
| --- | --- | --- | --- |
| Construction | validate all named paths, resolve the immutable validator, and isolate ambient overrides before setup | build exact source with the managed compiler and real ggml shim | self-test prerequisite/isolation precedence; real identity fields |
| Validator control | validate the fixed known-good patch once before model/server work | existing task runner and unchanged task | control must pass or the run fails before samples |
| Baseline success | resident pinned server, loopback request | existing local provider and schema-2 record | four extracted and validated patches |
| Candidate success | exact supplied pack/geometry and budget | existing OLMoE provider path | four extracted and validated patches |
| No passing patch | retain bounded digest/count diagnostics | a well-formed provider error or successful record with invalid patch text is an ordinary measured outcome | `NOT_ELIGIBLE`, not harness failure |
| Malformed evidence | reject wrong schema/status/types/ranges | no inferred or repaired record | self-test malformed-record matrix |
| Determinism | compare patch digest and completion count within each arm | temperature zero, no seed | all four samples agree or runner fails |
| Timing | one monotonic interval per command and validator | provider interval comes from existing record | positive nested accounting and exact median oracle |
| Pair order | fixed balanced four-pair schedule | no ambient randomization | self-test exact schedule |
| Early exit | stop after first infrastructure/identity failure | no later sample is reported | partial evidence is never labelled complete |
| Cleanup | signal-aware server termination, owned Docker container force-removal, and temporary directory cleanup | ordinary provider teardown per invocation | forced server escalation and container-target self-tests; clean real exit |
| Ceiling | whole runner monotonic deadline | per-command bounds remain narrower | fail with observed elapsed time above approximately 15 minutes |

Public API ownership, replacement/move semantics, generic monomorphization, network credentials,
persisted cache cleanup, and concurrent provider calls are N/A: no product surface or shared runtime
state changes, the loopback baseline carries no credential, and the runner executes one leg at a
time.

## 5. Implementation and acceptance map

1. Extend the existing qualification-only provider helper with an explicit OLMoE runtime mode and
   positive cache budget; do not change the public provider or its CLI.
2. Reuse the existing fixed-task prompt, extractor, Linux validator routing, pinned llama.cpp
   identity, real-shim build, and signal-aware server cleanup.
3. Add the four-pair runner, canonical result construction, median/floor decision, bounded
   diagnostics, and a model-free self-test for calculation, malformed evidence, N/A precedence,
   and cleanup escalation.
4. Run the focused synthetic owners once, then one opt-in real decision. Record the exact result in
   this document and the roadmap; do not rerun to search for a favorable sample.
5. Run publication preflight with the focused owner. No `make ci`, installed profile, platform
   matrix, broad OLMoE corpus, cache-policy replay, stress suite, or unrelated benchmark is selected.

Completion requires the focused owner, one complete real decision, one comprehensive review,
exact-head publication preflight, and required GitHub checks. A `NOT_MET` or `NOT_ELIGIBLE` result
orders the next optimization or product decision from its observed failure; it does not authorize
repetition with changed prompts, samples, flags, or output repair.

## 6. Recorded decision

The one complete real decision ran on clean align-llm head
`8c9a7e40d8d1c47b316bd1ec52123dd3bc575b89` and finished in 147.288 seconds on Darwin 25.5.0,
arm64, with 8 logical CPUs. It returned **`NOT_ELIGIBLE`**: local and runtime pass counts were both
0 of 4, so primary medians and gain are null and no performance shipping claim is made.

Both arms were deterministic and emitted byte-identical output in every sample (output SHA-256
`4939911998ecc4b4b4893437be1a1e448fc0e8a482fd31c6d6d9204c6aa8ea59`). The extractor admitted the
same one-line patch in all eight legs (patch SHA-256
`a64bfacadea8cc00cc6b82880db2685d8eb925831971b02b1c83f6f3a17d73ef`), but the unchanged validator
rejected it every time. The local arm reported 55 completion tokens and provider intervals from
1.884 to 3.610 seconds; the runtime arm reported 87 completion tokens for the same bytes and
provider intervals from 24.600 to 27.516 seconds. Validator intervals were 0.388 to 0.692 seconds.

The remaining identities were Align
`8cefc803d5c7f883a8db5b67250ed4ed069b43a4`, AlignPack SHA-256
`20423ebf5a9080eacb11c12b9107b52912b6c7ad4d45a94f92a7cead6c7df6ae`, geometry SHA-256
`1f828d2c601e62311a4d7e5cd6b9f5cd9295fd1513b9b4c35f0119ad82d11ada`, and llama-server SHA-256
`98c3c05a1c2689295335b4cd01364fb2f3f7c6956c051b0dfaa5e52812fdf72c`. The evidence says not to
invest in provider-level OLMoE performance on this task yet: the first unmet consumer boundary is
model/prompt patch correctness, shared by both provider implementations.
