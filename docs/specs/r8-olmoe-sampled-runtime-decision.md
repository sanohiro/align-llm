# R8 OLMoE sampled runtime decision

Status: implementation contract, 2026-09-04

## 1. Decision and boundary

R8-OLMOE-SAMPLED-CODING established that the fixed local-provider portfolio reaches a passing
patch at seed 5. R8-OLMOE-RUNTIME-SAMPLING then made the selected fixed policy executable through
the shipped in-process `AlignRuntime` provider. This capability closes the remaining consumer
boundary: measure provider-helper launch through the unchanged coding validator for the same
ordered portfolio on both provider arms.

The runner executes four balanced pairs. Each leg tries seeds 1 through 8 at temperature 0.3 and
stops at its first passing patch. The baseline is one resident pinned llama.cpp server reached
through `LocalOpenAI`; the candidate is the shipped partial-LRU OLMoE `AlignRuntime` path with an
invocation-local cache for every candidate request. No provider, sampler, prompt, extractor,
validator, cache, or model behavior changes.

This is R8's provider-level performance decision for the sampled consumer. It is deliberately one
fixed-task result, not a quality-rate, cross-host, throughput, token-parity, or generality claim.

## 2. Measurement-contract ledger

| Field | Settled contract |
| --- | --- |
| Capability | `R8-OLMOE-SAMPLED-RUNTIME-DECISION` |
| Consumer | one coding caller seeking the first passing patch from the fixed sampled portfolio through either shipped `ModelProvider` arm |
| Task and prompt | item 50's byte-identical `python-inclusive-range` task, system text, user text, strict one-line unified-diff extractor, and unchanged validator |
| Subject model | `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 4,213,512,192 bytes, SHA-256 `4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f` |
| Baseline | llama.cpp build 10566 commit `bb4caa754`, loopback `LocalOpenAI`, CPU-only, four threads, context 512, no warmup, one server resident across all pairs |
| Candidate | exact reviewed align-llm source and `.align-revision`, in-process `AlignRuntime`, real ggml shim/libraries, exact pack and geometry, 975,175,680-byte invocation-local expert-cache budget |
| Opt-in inputs | model, pack, geometry, ggml include, ggml library, and server use item 50's six named `ALIGN_LLM_*` variables; Darwin additionally requires an explicit ordered `LIBRARY_PATH`, validated directory by directory and bound by digest without publishing machine paths |
| Portfolio | temperature 300,000 micros, seeds `[1,2,3,4,5,6,7,8]` in order, maximum 128 completion tokens, stop immediately after the first passing patch |
| Pair schedule | `(local,runtime)`, `(runtime,local)`, `(runtime,local)`, `(local,runtime)`; one synchronous leg at a time |
| Primary metric | nanoseconds from each portfolio leg's first provider-helper launch through successful validation of its first passing patch |
| Gate | `MET` only when both arms pass all four legs, runtime is faster in every pair, and runtime median is at least 50,000 ppm below local median; `NOT_MET` when both pass all four but the speed rule fails; `NOT_ELIGIBLE` when either arm has fewer than four passing legs |
| Determinism | within each arm, all four legs must have the same ordered candidate statuses, completion counts, admitted patch digests, selected index, and selected seed; output digests remain evidence but are not a task-workload identity for an `INVALID_PATCH` that never reaches validation |
| Failure | nonzero exit for prerequisite or identity drift, malformed records, provider/seed refusal, missing/duplicate/out-of-order candidates, validator infrastructure failure, nondeterminism, cleanup failure, or ceiling excess |
| Result | canonical `R8_OLMOE_SAMPLED_RUNTIME_DECISION` schema 1 JSON on stdout plus one concise stderr summary; no machine-local result is committed |
| Ownership | the runner owns the server, exact-source helper, dynamic shim, candidate records and patches, validator workspaces, any Docker containers, and all temporary files |
| Persisted/cache identity | no inference or expert cache survives a request; the result binds source, compiler, helper, shim, ggml libraries, model, pack, geometry, server, task, prompt, and immutable validator identities |
| Owner | `scripts/run-olmoe-sampled-runtime-decision --self-test`; the opt-in real decision uses the same command without arguments and the documented model/runtime/linker environment inputs |
| Performance floor | item 50's unchanged 50,000 ppm end-to-end floor plus the every-pair direction rule |
| Pre-implementation opportunity ceiling | item 51's fixed baseline required five candidates while a candidate portfolio can succeed no earlier than candidate one, so portfolio attempt count can remove at most four of five attempts, 800,000 ppm; differing provider cost makes the realized time ceiling lower and is measured rather than assumed |
| Execution cost ceiling | approximately 25 minutes for one build, one server load, four balanced pairs, at most 64 provider attempts, validation, and identity rechecks; stop and diagnose material excess |

The opportunity ceiling exceeds the shipping floor, so the performance decision is eligible. It
does not predict a win: item 50 showed higher per-request runtime cost, while the sampled candidate
may stop at a different seed because Align's shipped Xoshiro stream intentionally does not promise
llama.cpp token parity. Time to a passing patch measures both effects without substituting an
isolated decode counter.

The first pre-result execution exposed one correction to the determinism rule. Local candidate 1
produced two different output digests across repeated portfolios, but both rows had 52 completion
tokens, were rejected by the extractor, and were followed by byte-identical failing and passing
patches at the same seeds. Exact bytes of a completion that never becomes a patch are therefore not
part of the task workload identity. They remain recorded for transparency; status, completion
count, every admitted patch digest, and portfolio selection remain fail-closed repeatability keys.
No complete result or performance verdict existed when this rule was corrected.

Median for four values is the integer floor of the sum of the two middle sorted values divided by
two. Gain is `(local_median - runtime_median) * 1_000_000 // local_median`. Every duration is a
positive integer. A non-passing leg has no primary duration and cannot contribute zero or infinity.

## 3. Schema 1 result

The canonical result has these ordered semantic groups:

```text
schema_version: 1
artifact_kind: "R8_OLMOE_SAMPLED_RUNTIME_DECISION"
status: "COMPLETE"
model: {bytes, sha256, architecture}
baseline: {provider, runtime_identity, server_sha256, threads, context, warmup}
candidate: {provider, align_llm_head, align_revision, compiler_sha256, helper_sha256,
            shim_sha256, ggml_libraries: [{name, bytes, sha256}], pack_sha256,
            geometry_sha256, cache_budget_bytes}
task: {task_id, task_sha256, prompt_sha256, maximum_completion_tokens}
sampling: {temperature_micros, ordered_seeds, maximum_candidates, stop_on_first_pass}
validator: {kind, image_id}
environment: {os, release, architecture, cpu_count, c_compiler_sha256,
              c_compiler_version_sha256, linker_search_sha256}
samples: [{pair_index, order, local, runtime}]
aggregate: {local_pass_count, runtime_pass_count,
            local_median_time_to_passing_patch_ns,
            runtime_median_time_to_passing_patch_ns, gain_ppm,
            runtime_faster_in_every_pair, verdict}
elapsed_ns: integer
```

Each arm object contains `status` (`PASS` or `NO_PASSING_PATCH`), `attempted_count`,
`admitted_patch_count`, `passing_count`, nullable selected index/seed/patch digest, nullable
`time_to_passing_patch_ns`, and `candidates`. Each candidate contains its one-based index, seed,
status (`PASS`, `INVALID_PATCH`, or `FAILING_PATCH`), provider elapsed time, command wall time,
validation elapsed time, completion token count, output digest, and nullable patch digest.
`NO_PASSING_PATCH` requires all eight attempts and null selection/time fields. `PASS` ends on its
sole passing candidate and measures from the leg start through that validation.

Paths, output text, patch text, model bytes, server logs, credentials, and process identifiers are
never embedded. The record is measurement evidence rather than a persisted product format or a
promise of byte identity between provider arms.

## 4. Validation order

The runner validates configured paths in model, pack, geometry, ggml include, ggml library, then
server order; a configured invalid path is never hidden by a later missing value. It then requires
a clean worktree, validates every explicit Darwin linker-search directory, resolves the validator
to a native boundary or immutable Docker image, validates the known-good control under the same
scrubbed validator environment used by every candidate, checks model and server identity, resolves
the managed compiler, builds the exact-source dynamic shim and helper, starts the server, and
executes the fixed schedule.

Each candidate accepts only a successful, well-formed schema-2 provider record. Provider errors and
seed refusal fail the decision. A syntactically invalid completion is an ordinary `INVALID_PATCH`;
an admitted patch rejected with the validator's task-failure status is `FAILING_PATCH`.
Infrastructure errors stop immediately without a `COMPLETE` result. Persistent inputs, retained
build artifacts, clean source state, and source head are rechecked after all pairs.

## 5. Closure matrix

| Cell | Measurement runner | Helper/providers | Exact evidence |
| --- | --- | --- | --- |
| Construction | validate ordered prerequisites, explicit linker search, immutable validator, clean source, identities, dynamic shim/helper, then resident server | existing `local-sampled` and `runtime-olmoe-sampled` modes receive the same seed policy and maximum | self-test command grammar, precedence, linker/environment isolation; real identity fields |
| Validator control | known-good patch passes before model/server work in the candidate validation environment | N/A | self-test environment routing; real control |
| Baseline success | run ordered candidates against one resident pinned server | one seeded loopback request per candidate | four complete deterministic local portfolios |
| Candidate success | run ordered candidates with exact model/pack/geometry/budget | one seeded in-process request and invocation-local cache per candidate | four complete deterministic runtime portfolios |
| Invalid patch | record bounded output identity; skip validator | successful provider record | synthetic classification and real candidate rows |
| Failing patch | record patch identity and validator duration | successful provider record | synthetic classification and real candidate rows |
| No passing patch | require all eight ordered attempts and null selection/time | successful provider records only | aggregate `NOT_ELIGIBLE` case |
| Provider or malformed failure | fail without a complete result | nonzero helper exit or malformed/inconsistent schema-2 record | self-test refusal/malformed matrix |
| Ordering and stop | exact pair order and seed order; stop each leg on first pass | one synchronous call at a time | schedule, gap, duplicate, continuation, and early-stop self-tests |
| Determinism | compare status, completion count, admitted patch identity, and selection within each arm; retain but do not key invalid output bytes | explicit seed per request and no hidden runner randomness | repeated-arm equality, invalid-output variation, and semantic mutation self-tests |
| Timing and decision | leg interval includes all attempts and final validation; exact median/gain/faster rule | provider interval remains nested in command wall interval | MET, NOT_MET, NOT_ELIGIBLE, median, nesting self-tests |
| Early exit | first infrastructure or identity failure emits no `COMPLETE` JSON | no inferred or repaired result | malformed, mutation, and deadline self-tests |
| Cleanup | terminate, then kill and reap the owned server/helper; force-remove only the recorded validator container; restore any prior root helper | request-local allocations and cache die with helper invocation | forced escalation, exact container target, and restoration self-tests |
| Ceiling | one monotonic 25-minute deadline covers setup through revalidation | each command has a narrower bound | deadline self-test and recorded real elapsed time |

Public API ownership, move semantics, generic monomorphization, concurrent provider calls, GPU
execution, prefix-cache persistence, arbitrary sampling policy, and cross-task selection are N/A:
the capability changes only a focused measurement runner around already-shipped synchronous APIs.
Network credentials are N/A because the only network boundary is the owned loopback baseline.

## 6. Implementation and acceptance map

1. Add one focused runner that reuses item 50's task, extractor, validator, identity, environment,
   and cleanup utilities and item 51's candidate classification semantics.
2. Build the existing helper from the exact reviewed source against the configured real ggml
   boundary. Do not change either provider/helper mode or any product source.
3. Implement the balanced portfolio schedule, schema validation, determinism checks, exact
   aggregate rule, canonical result, identity recheck, and bounded cleanup.
4. Add model-free self-tests for commands, schema, candidate/portfolio states, schedule,
   deterministic comparison, aggregate verdicts, environment isolation, identity mutation,
   deadline, restoration, and process/container cleanup.
5. Run the self-test once, then the one complete opt-in real decision and record its result here and
   in the roadmap. Do not rerun or change seeds, pair order, prompt, floor, or policy to obtain a
   favorable verdict.
6. Run one comprehensive review, repair accepted root causes, rerun affected owners, then run
   exact-head publication preflight with this focused owner and required GitHub checks.

No `make ci`, installed profile, broad OLMoE matrix, 40-prompt corpus, cache-policy replay, stress
suite, unrelated benchmark, or sampler/token parity qualification is selected. Completion requires
the focused owner, one complete real decision, one comprehensive review, exact-head preflight, and
required GitHub checks. `MET` closes the R8 gate for this fixed task; `NOT_MET` or `NOT_ELIGIBLE`
records the negative performance decision and redirects the next investment from observed evidence.

## 7. Recorded decision

Pending the one complete real measurement. This section will record the exact source and input
identities, environment, arm outcomes, medians, gain, ceiling comparison, verdict, and next action.
