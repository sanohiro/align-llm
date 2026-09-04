# R8 OLMoE sampled coding decision

Status: measured implementation candidate, 2026-09-04

## 1. Decision and boundary

R8's first provider-level coding decision did not reach a passing patch because greedy OLMoE
generation chose `range(start, stop, -1)` for the fixed `python-inclusive-range` task. The model
repeated that semantic error when shown the validator diagnostics. A bounded feasibility probe then
showed that non-zero-temperature seeded generation can produce the correct replacement. This
capability turns that observation into one reproducible consumer decision before any sampling path
is added to `AlignRuntime`.

The capability runs the shipped local OpenAI-compatible `ModelProvider` against one resident pinned
llama.cpp server. It tries a fixed ordered portfolio of eight seeds at temperature 0.3, validates
each admitted patch with the unchanged coding-task validator, and stops at the first passing patch.
It does not change provider behavior, the task or prompt, the patch extractor, runtime inference,
or the R8 performance verdict. A `MET` decision selects seeded sampling as the next AlignRuntime
capability. `NOT_MET` redirects the next investment to a different model. Neither verdict is a
generality, quality-rate, or latency claim.

The pre-design probe used the same model and task to establish feasibility, so the decision is
deliberately scoped to this exact local optimization target. It is not holdout evidence and must
not be presented as model-quality evaluation.

## 2. Measurement-contract ledger

| Field | Settled contract |
| --- | --- |
| Capability | `R8-OLMOE-SAMPLED-CODING` |
| Consumer | one bounded ordered candidate portfolio through the shipped local OpenAI-compatible provider and existing coding validator |
| Task and prompt | item 50's byte-identical `python-inclusive-range` task, system text, user text, and strict one-line unified-diff extractor |
| Subject model | `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 4,213,512,192 bytes, SHA-256 `4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f` |
| Provider | llama.cpp build 10566 commit `bb4caa754`, loopback server, CPU-only, four threads, context 512, no warmup |
| Sampling policy | temperature 300,000 micros, seeds `[1,2,3,4,5,6,7,8]` in that order, maximum 128 completion tokens, one request at a time |
| Stop rule | stop immediately after the first validator-passing patch; otherwise consume all eight candidates |
| Gate | `MET` when one candidate reaches a passing patch; `NOT_MET` when all eight well-formed provider attempts complete without one |
| Failure | nonzero exit for prerequisite or identity drift, malformed provider records, seed refusal, duplicate/missing/out-of-order attempts, validator infrastructure failure, cleanup failure, or ceiling excess |
| Result | canonical `R8_OLMOE_SAMPLED_CODING` schema 1 JSON on stdout plus one concise stderr summary; no machine-local result is committed |
| Ownership | the runner owns the server, exact-source helper, temporary unavailable ggml shim, candidate records and patches, validator workspaces, and any Docker containers |
| Persisted/cache identity | N/A: the immutable model and source identities are recorded; the runner creates no reusable inference cache or committed result |
| Owner | `scripts/run-olmoe-sampled-coding --self-test`; real decision is `scripts/run-olmoe-sampled-coding` with `ALIGN_LLM_OLMOE_MODEL` and `ALIGN_LLM_LLAMA_SERVER` |
| Cost ceiling | approximately 10 minutes for build, server load, validator control, and at most eight candidates; no performance floor |

The seed order is part of the contract, not a search knob. The run is executed once and is not
repeated with different temperatures, seed ranges, prompt wording, response normalization, or
validator behavior to obtain a favorable result. A provider error is infrastructure failure, not a
failed candidate. An extracted patch that fails the task is an ordinary candidate failure.

## 3. Schema 1 result

The canonical JSON object has these ordered semantic groups:

```text
schema_version: 1
artifact_kind: "R8_OLMOE_SAMPLED_CODING"
status: "COMPLETE"
source: {align_llm_head, align_revision, compiler_sha256, helper_sha256, shim_sha256}
model: {bytes, sha256, architecture}
provider: {kind, runtime_identity, server_sha256, threads, context, warmup}
task: {task_id, task_sha256, prompt_sha256, maximum_completion_tokens}
sampling: {temperature_micros, ordered_seeds, maximum_candidates, stop_on_first_pass}
validator: {kind, image_id}
environment: {os, release, architecture, cpu_count, c_compiler_sha256,
              c_compiler_version_sha256}
candidates: [{index, seed, status, provider_elapsed_ns, command_wall_ns,
              validation_elapsed_ns, time_to_passing_patch_ns, completion_tokens,
              output_sha256, patch_sha256}]
aggregate: {attempted_count, admitted_patch_count, passing_count,
            selected_candidate_index, selected_seed, selected_patch_sha256, verdict}
elapsed_ns: integer
```

Candidate `status` is `PASS`, `INVALID_PATCH`, or `FAILING_PATCH`. `INVALID_PATCH` has a null
`patch_sha256` and zero validation time. `FAILING_PATCH` has a patch digest, positive validation
time, and null time to passing patch. `PASS` has all three timings positive and its
`time_to_passing_patch_ns` measures from whole portfolio start through successful validation. The
aggregate selection fields are all null for `NOT_MET`; `MET` binds them to the sole final candidate
because execution stops immediately.

The runner requires a clean worktree and records the exact align-llm head, managed compiler,
compiled helper, temporary static shim, C compiler, model, server, task, prompt, and immutable
validator image. It re-hashes every persistent input and every retained build artifact after the
portfolio. Paths, model output, patch text, server logs, and credentials never enter the result.

## 4. Closure matrix

| Cell | Runner | Provider helper | Evidence |
| --- | --- | --- | --- |
| Construction | validate model/server, resolve immutable validator, isolate ambient compiler/shim/math overrides, then build exact source | explicit sampled-local mode constructs temperature and seed in `GenerationRequest` | self-test validation precedence and exact helper request |
| Validator control | the existing known-good patch passes once before server/model work | N/A | control failure stops before candidates |
| Candidate success | extract exact existing grammar and validate in an isolated workspace | schema-2 provider record with accepted seed and completion | selected candidate fields and `MET` |
| Invalid patch | record bounded output identity, do not invoke validator | successful provider generation | `INVALID_PATCH` self-test and real row |
| Failing patch | retain patch identity and validator duration | successful provider generation | `FAILING_PATCH` self-test and real row |
| Provider/seed failure | fail the run; never reinterpret it as a candidate | nonzero helper status or malformed/inconsistent record | malformed/error/refusal self-tests |
| Ordering and stop | exact seeds 1 through 8, no gaps; stop on first pass | one synchronous request per invocation | schedule and early-stop self-tests |
| Timing | whole-run and per-command monotonic clocks | provider-owned elapsed interval remains nested in command wall time | positive/nesting self-tests |
| Identity drift | re-read source head and every named digest after candidate work | helper is moved out of the worktree and retained until revalidation | mutation self-tests plus real identities |
| Early exit | first infrastructure failure stops without `COMPLETE` output | no inferred or repaired record | partial-result refusal self-test |
| Cleanup | signal-aware server termination, Docker CID force-removal, and temporary directory cleanup | process-local provider request | forced escalation/container-target self-tests |
| Ceiling | one whole-run deadline covers setup through revalidation | each helper and validation command has a narrower bound | deadline self-test and real elapsed time |

Public product API ownership, runtime sampling, concurrent calls, GPU execution, persisted prefix or
expert caches, generalized task selection, and model comparison are N/A: this capability is a
single fixed decision over an existing network provider and does not change those surfaces.

## 5. Implementation and acceptance map

1. Extend the qualification-only provider helper with an explicit sampled-local mode carrying a
   decimal temperature in micros and one seed. Preserve every existing greedy mode byte for byte.
2. Add the bounded runner by reusing item 50's prompt, extractor, validator routing, source and
   toolchain isolation, server lifecycle, identity binding, and cleanup rules.
3. Add model-free self-tests for schema, schedule, early stop, classification, malformed records,
   identity mutation, deadline, and cleanup behavior.
4. Run the focused synthetic owner once, then one complete real portfolio. Record the exact result
   here and in the roadmap; do not rerun to search for another seed or timing.
5. Run publication preflight with the focused owner. No `make ci`, installed profile, runtime
   provider qualification, OLMoE cache replay, 40-prompt corpus, stress suite, or benchmark is
   selected.

Completion requires the focused owner, one complete real decision, one comprehensive review,
exact-head publication preflight, and required GitHub checks. A `MET` result makes seeded runtime
sampling the next eligible capability but does not itself meet R8's performance gate; that still
requires time to a passing patch or decode latency against the local baseline.

## 6. Recorded decision

The one complete real portfolio ran on clean align-llm head
`e4a01c9529c579ce6cec57f25a45f099f884faa6` and finished in 34.483 seconds on Darwin 25.5.0,
arm64, with 8 logical CPUs. It returned **`MET`** and stopped at candidate 5, seed 5. The passing
patch SHA-256 is `5d6b107e706a5a55c945bc0b41296e255013a1516e0a6211ccc9da65001252dc`,
identical to the existing known-good patch. Time from portfolio start through its successful
validation was 13.176 seconds. This is feasibility evidence, not a performance result.

The candidate sequence was `INVALID_PATCH`, `FAILING_PATCH`, `FAILING_PATCH`, `INVALID_PATCH`,
`PASS`. Candidates 2 and 3 reproduced item 50's greedy wrong-patch digest
`a64bfacadea8cc00cc6b82880db2685d8eb925831971b02b1c83f6f3a17d73ef`; candidates 1 and 4 did
not satisfy the unchanged strict extractor. Three patches were admitted, one passed, and seeds 6
through 8 were correctly not requested after success.

The bound identities were Align `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`, managed compiler
SHA-256 `f972b4a196ed5608a0c52cc02dbf8267cfc236065359315a572d601aa04ea541`, helper
SHA-256 `a9ce76c8bf2ac377ab25c5e31971ef34c4c2fe2ecce944296a7e7ab8070b96e3`, static shim
SHA-256 `64eb3959ebfbf1794f6b7fae080ff6c08f3de4cad4b8c370892ab40487b2a8f6`, and llama-server
SHA-256 `b6ff7e912a9690ffec38878cad25b9ec1424a5537bd72010effe2fc9bfe64f74`.
The immutable validator image was
`sha256:33fa9e4446ab1a5ca849c57ea49e2e2e4585488aa1cd4d7b2940801bad84cb54`.

The decision selects seeded sampling as the next `AlignRuntime` consumer capability. It does not
select this particular five-attempt latency as a floor or claim that the fixed portfolio transfers
to another task, model, prompt, server build, or machine.
