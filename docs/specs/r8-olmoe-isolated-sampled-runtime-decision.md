# R8 OLMoE isolated sampled runtime decision

Status: decision recorded, 2026-09-04

Roadmap owner: item 56, `R8-OLMOE-ISOLATED-SAMPLED-RUNTIME-DECISION`

## 1. Decision owned

Item 53 measured the fixed sampled coding portfolio with one llama.cpp server resident across all
four local/runtime pairs. AlignRuntime was slower in every pair, but item 55 later showed that an
idle co-resident server added a 3.052-second median penalty to one full AlignRuntime request while
repeated pre-prefill construction was bounded at 0.272 seconds. The item-53 provider-level result
therefore mixed the candidate's request-local cost with avoidable co-resident model pressure.

This capability repeats item 53's exact task, prompt, seed order, provider arguments, validator,
four balanced pairs, metric, and 50,000-ppm gate while changing only server scope. Every local leg
owns one fresh pinned llama.cpp server, starts its portfolio after readiness, and terminates and
reaps that server before the next arm. Every runtime leg begins and ends with no matching server and
model process. Server startup and teardown remain outside the local time-to-passing-patch metric,
as they were in item 53; total qualification elapsed time still contains them.

No provider, helper, sampler, extractor, validator, model, pack, geometry, cache, or production
lifetime changes. `MET` closes R8 for this fixed consumer. `NOT_MET` or `NOT_ELIGIBLE` records the
isolated result and selects the next evidence-based roadmap work without authorizing persistent
provider state.

## 2. Measurement-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-ISOLATED-SAMPLED-RUNTIME-DECISION`; `scripts/run-olmoe-isolated-sampled-runtime-decision`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | one coding caller seeking the first passing patch from the fixed sampled portfolio through either shipped `ModelProvider` arm, with candidate measurement isolated from a matching resident baseline model |
| Fixed workload | item 53's byte-identical task, system/user prompt, maximum 128 completion tokens, temperature 300,000 micros, seeds `[1,2,3,4,5,6,7,8]`, strict extractor, validator, stop-on-first-pass rule, provider arguments, and cache budget 975,175,680 bytes |
| Subject model | `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 4,213,512,192 bytes, SHA-256 `4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f` |
| Pair schedule | `(local,runtime)`, `(runtime,local)`, `(runtime,local)`, `(local,runtime)`; one synchronous arm at a time; four local server instances total |
| Local server scope | before each local leg require zero processes whose command contains both canonical configured server and model paths; start exactly one pinned build-10566 CPU server with four threads, context 512, one slot, item 53's default enabled prompt cache, and `--no-warmup`; require readiness and that the sole matching process is the owned PID; measure one local portfolio; require the server still alive; then terminate, escalate to kill if bounded wait expires, reap, close its log, and require zero matches |
| Runtime isolation | immediately before and after each runtime portfolio require zero matching server/model processes; a runtime failure still executes the after check and produces no complete result |
| Primary metric | unchanged item-53 nanoseconds from a portfolio leg's first provider-helper launch through validation of its first passing patch; local server startup/readiness and teardown are excluded; total qualification elapsed includes them |
| Gate | unchanged item-53 rule: `MET` only when both arms pass all four legs, runtime is faster in every pair, and runtime median is at least 50,000 ppm below local median; `NOT_MET` when both pass four but speed fails; `NOT_ELIGIBLE` when either arm has fewer than four passing legs |
| Portfolio semantics | reuse item 53's candidate schema, ordered seed validation, `PASS`/`INVALID_PATCH`/`FAILING_PATCH`, stop, duration nesting, within-arm determinism, median, gain, and eligibility semantics; outputs are measured behavior, not pinned expected results |
| Fixed input identity | model size/hash, pack, geometry, server binary/version, task, prompt, validator image, Align revision/compiler, ggml libraries, C compiler/version, and canonical linker-search digest are pinned to the current item-53/55 chain and refused before timed portfolios; the clean current align-llm head and newly built helper/shim are recorded and rechecked |
| Opt-in inputs | item 53's six canonicalized model/runtime `ALIGN_LLM_*` paths, optional `ALIGN_LLM_RUNTIME_GATE_IMAGE` defaulting to `c4-repair-measure:latest`, and Darwin's required ordered `LIBRARY_PATH`; a missing required path emits one capability-specific `N/A` line before materialization or process creation |
| Result | one exact-key schema-1 `R8_OLMOE_ISOLATED_SAMPLED_RUNTIME_DECISION` JSON document on stdout and one concise stderr summary; no partial JSON on failure |
| Sample isolation evidence | every pair adds exact-key `isolation`: `local_server_instances: 1`, `local_ready: true`, `local_sole_owned_match: true`, `local_alive_after_portfolio: true`, `local_terminated: true`, `local_reaped: true`, `matching_before_local: 0`, `matching_after_local: 0`, `matching_before_runtime: 0`, and `matching_after_runtime: 0`; paths and PIDs are never emitted |
| Baseline metadata | item 53 baseline identity plus `server_scope: "one-local-portfolio"`, `server_instances: 4`, `startup_in_primary_metric: false`, and `teardown_in_primary_metric: false` |
| Validation order | canonical prerequisites; scrubbed environment and linker search; clean head; validator identity and known-good control; pinned model/artifact/tool identities; exact-source helper build; for each scheduled arm its isolation precondition, portfolio, and cleanup/postcondition; pair/schema/determinism/aggregate; unchanged head/files; ceiling; publication |
| Failure | nonzero exit and no complete document for invalid arguments, unusable/missing configured value, identity drift, malformed helper/result data, provider/seed refusal, validator infrastructure failure, process mismatch, premature server exit, cleanup/reap failure, source mutation, or ceiling excess; `NO_PASSING_PATCH` remains measured data and can produce `NOT_ELIGIBLE` |
| Ownership | the runner owns four non-overlapping server processes/logs, the exact-source helper and shim, validator workspaces/containers, records, patches, and temporary files; every server and child is terminated and reaped before its ownership scope ends |
| Persisted/cache identity | N/A: no inference, expert cache, server process, generated helper, patch, or validator workspace survives the run; the JSON evidence is printed and not stored by the runner |
| Performance floor | item 53's unchanged 50,000-ppm end-to-end floor and every-pair direction rule; baseline is item 53's recorded 12.710-second local and 189.005-second co-resident-runtime medians, while this capability's decision uses only its new four isolated pairs |
| Cost ceiling | one monotonic 25-minute ceiling covers validator control, helper/shim build, four server startups and teardowns, at most 64 provider candidates, validation, aggregation, identity rechecks, and cleanup; each child has a narrower bound |
| Acceptance evidence | Python compilation; predecessor owner self-test; focused self-test; one complete real decision; `git diff --check`; one comprehensive review; exact-head `scripts/pre-pr --owner-test R8-OLMOE-ISOLATED-SAMPLED-RUNTIME-DECISION -- scripts/run-olmoe-isolated-sampled-runtime-decision --self-test` |

The inherited fixed SHA-256 values are AlignPack
`20423ebf5a9080eacb11c12b9107b52912b6c7ad4d45a94f92a7cead6c7df6ae`, geometry
`1f828d2c601e62311a4d7e5cd6b9f5cd9295fd1513b9b4c35f0119ad82d11ada`, server
`98c3c05a1c2689295335b4cd01364fb2f3f7c6956c051b0dfaa5e52812fdf72c`, task
`1884f01a329752c1383081342c65d062241aefaefff2f206f6604008bde74940`, prompt
`0b3b037f2063731dec7c5ea0c8acd8b2ffeff4b940a6b32716ac91207c9e284b`, compiler
`f972b4a196ed5608a0c52cc02dbf8267cfc236065359315a572d601aa04ea541`, C compiler
`179301dcb41ea78accc3fa0048a7e6f6710d891945a751a34addd622020c1818`, C compiler version
`ea3037e0630fa16798079372fdc24f6542d021dadda4915cc979799682d78295`, canonical linker
search `5cb52d849e4b5dd2e0380c9fd272279c8b3e572dc563691f60fc8ecbf72d92cf`, and validator
image `sha256:33fa9e4446ab1a5ca849c57ea49e2e2e4585488aa1cd4d7b2940801bad84cb54`.
The Align revision is `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`. The ggml list contains
`libggml-base.0.21.0.dylib`, `libggml-base.0.dylib`, and `libggml-base.dylib`, each 506,160 bytes
with SHA-256 `5d193ff57adff4912c686903b38a2802a716639d2240cebd4275faeee4d94574`, followed by
`libggml.0.21.0.dylib`, `libggml.0.dylib`, and `libggml.dylib`, each 60,272 bytes with SHA-256
`c3d660fbd37d5bae33e68371d27aab78b9875ccb5676532d3f1cfe1cea6f8734`. The runner owns this
canonical ordered list rather than accepting any uniformly changed library directory.

The capability is a one-task, one-model, one-host performance decision. Cross-host, GPU,
throughput, token-parity, arbitrary-task, concurrent-provider, persistent-cache, and first-ever cold
startup claims are N/A. The local server's model load can warm the host filesystem cache, but the
balanced arm order controls that order effect while the exact decision target is process-resident
model pressure, not cold-cache performance.

## 3. Schema 1

The result preserves item 53's `model`, `candidate`, `task`, `sampling`, `validator`,
`environment`, portfolio, candidate, and aggregate shapes. Its top-level exact keys are:

```text
schema_version
artifact_kind
status
model
baseline
candidate
task
sampling
validator
environment
samples
aggregate
elapsed_ns
```

Each sample has exact keys `pair_index`, `order`, `local`, `runtime`, and `isolation`. `local` and
`runtime` are unchanged item-53 portfolio objects. `isolation` has the ten fields named in the
ledger. Its counts are non-boolean integers, every matching count is exactly zero, and every
lifecycle proof is exactly true. Item 53's duration and nullable-field rules remain unchanged.
Existing candidate output and patch text remain excluded.

## 4. Closure matrix

| Path | Construction/precondition | Success | Failure/malformed | Early exit | Cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Whole run | validate/canonicalize inputs, scrub Git/native routing, clean head, fixed identities, validator control, helper build | four exact pairs and one complete schema-1 document | fail before publication on identity, source, schema, validator, or ceiling drift | missing prerequisite is one N/A line | restore root helper; remove exact validator containers; stop active child/server | predecessor self-test, focused command/environment/identity tests, real result |
| Local leg | require zero matches; start one server; wait ready; require sole owned match | item-53 portfolio while server stays alive | wrong/multiple match, startup exit, provider error, or premature exit fails | portfolio stops only on first pass | terminate/kill, wait/reap, close log, require zero matches in `finally` | process parser, ready/sole-owner, premature-exit, escalation, and four real lifetimes |
| Runtime leg | require zero matches immediately before first helper | item-53 runtime portfolio | any matching process or provider/schema failure rejects | portfolio may end on first pass or after seed 8 | require zero matches in `finally`; active helper follows predecessor cleanup | before/after mutation tests and eight real absence observations |
| Pair schedule | exact balanced order; local creates only its own server | one local and one runtime portfolio plus isolation record | missing/duplicate/out-of-order arm or isolation key fails | no partial pair publication | local scope ends before loop advances | four-pair schema/order self-test and real samples |
| Portfolio/candidate | reuse item-53 construction and validation | unchanged statuses, stop, timing, determinism, aggregate | predecessor malformed/nondeterministic/provider cases fail | `NO_PASSING_PATCH` is valid measured completion | request-local runtime cache and candidate files die with scopes | predecessor owner plus MET/NOT_MET/NOT_ELIGIBLE vectors |
| Identity | pin inherited values before timed work; capture new helper/shim/head | final hashes and head unchanged | uniform artifact/tool drift fails rather than being re-baselined | N/A | no persisted identity state | fixed-identity and mutation self-tests; real before/after check |
| Signal/deadline | install handlers before real work; one monotonic deadline | N/A | interruption/timeout exits nonzero | no complete JSON | stop active helper then owned server, escalating and reaping | forced-timeout and active-owner cleanup self-tests |

Public product API ownership, move/source-nulling semantics, generic monomorphization, exchanged
provider schemas, and concurrent shared-process pairings are N/A because this runner only composes
already-shipped synchronous provider/helper contracts in separate processes.

## 5. Implementation and verification map

1. Add one focused runner that imports item 53's candidate, portfolio, validator, aggregate,
   helper-build, and environment owners rather than copying them.
2. Add only the local per-leg server context, runtime absence boundary, exact isolation schema,
   inherited input pinning, and capability-specific result wrapper.
3. Run item 53's owner and the new model-free owner. Then run exactly one complete real decision and
   record the result here, in the roadmap, and in `HANDOFF.md`; do not change the order, seeds,
   floor, or workload after observing the result.
4. Perform one comprehensive review, consolidate accepted findings, rerun affected owners, run
   exact-head preflight and required GitHub checks, merge, then continue to the selected roadmap
   work.

No `make ci`, installed profile, broad OLMoE matrix, corpus, cache-policy replay, stress suite,
unrelated benchmark, or native platform qualification is selected. This qualification makes no
new target-specific product claim; it measures the fixed provider-level decision on the same host.

The capability exceeds 1,000 hand-written lines only when its authoritative ledger is counted with
the 924-line runner. The runner imports item 53's provider, portfolio, validator, and aggregate
implementation; its remaining size is the consumer-owned exact identity/schema proof, four
non-overlapping external-process lifetimes, signal/failure cleanup, and model-free closure tests.
Splitting those pieces would create a schema or lifecycle producer without an independently usable
measurement consumer and would duplicate the same process and identity failure domain.

## 6. Recorded decision

The complete isolated decision ran at clean align-llm head
`ee3ca3d691a91bac06f2e41e4b8fa4fc05f3e00f` with Align
`8cefc803d5c7f883a8db5b67250ed4ed069b43a4` on Darwin arm64 25.5.0. It bound every model,
pack, geometry, server, task, prompt, validator, compiler, C toolchain, linker-search, and ggml
identity named above. The newly built helper was
`5ddb391724a2edbb2a76330d112f307db2952073a421777e584574db3d719ebe`; its dynamic shim was
`9ec6fa6116d3f5241f230d14e829e86b9a004c6a168a6619c8ceec91658faddc`. The run completed in
724.144 seconds, below the precommitted 25-minute ceiling.

Both arms passed all four portfolios at candidate 5, seed 5, with the same passing patch SHA-256
`5d6b107e706a5a55c945bc0b41296e255013a1516e0a6211ccc9da65001252dc`. Each local portfolio
recorded `INVALID_PATCH`, `FAILING_PATCH`, `FAILING_PATCH`, `INVALID_PATCH`, then `PASS`; each
runtime portfolio recorded four `FAILING_PATCH` candidates, then `PASS`. Thus output rendering
differed before the common successful candidate, but candidate count did not explain the timing
difference.

The local arm retained item 53's default enabled llama.cpp prompt cache within each five-candidate
portfolio; the fresh server boundary prevented that cache from crossing portfolios. This is part of
the exact inherited baseline behavior and helps explain why candidate count alone is not a timing
model for the two implementations.

Local pair times were 13.421, 13.294, 13.100, and 13.045 seconds, for a 13.197-second median.
Runtime pair times were 152.302, 150.714, 147.029, and 147.832 seconds, for a 149.273-second
median. Runtime was slower in every pair and gain was -10,310,731 ppm, so the decision is
**`NOT_MET`**. Across the twenty candidates per arm, provider-time medians were 1.814 seconds local
and 29.300 seconds runtime; validator medians were 0.434 and 0.501 seconds. The R8 performance gate
remains open.

Every pair proved one ready, solely owned local server that remained alive for the portfolio, was
then terminated and reaped, and left zero matching processes. Every runtime boundary also observed
zero matching processes before and after its portfolio. Compared with item 53's 189.005-second
co-resident-runtime median, isolation recovered 39.732 seconds, or 210,218 ppm of that old median,
but left runtime 11.31 times the new local median. This comparison is diagnostic because only the
new isolated pairs own this capability's decision.

Item 55's isolated full-request median assigned only 0.237 seconds to construction and measured
24.803 seconds in remaining decode. Within that remaining-decode interval, its recorded claim-read
and compute medians account for about 8.46 seconds, leaving the largest absolute observed interval
without a decision-grade subdivision. Persistent provider state cannot plausibly close the present
gap from the 0.272-second construction upper bound. The next capability is therefore a focused
remaining-decode overhead diagnosis that separates graph/context lifecycle, data transfer and
readback, and routing/sampling/accounting before selecting an optimization seam. It must precommit
each candidate seam's opportunity ceiling and shipping floor; this result alone authorizes no
runtime behavior change.

This remains one fixed task, model, host, and bounded sampled portfolio. It establishes neither a
general model-speed ratio nor a throughput result.
