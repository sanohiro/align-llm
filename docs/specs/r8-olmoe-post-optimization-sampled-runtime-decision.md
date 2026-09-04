# R8 OLMoE post-optimization sampled runtime decision

Status: decision recorded, 2026-09-05

Roadmap owner: item 69, `R8-OLMOE-POST-OPTIMIZATION-SAMPLED-RUNTIME-DECISION`

## 1. Decision owned

Item 56 measured the isolated sampled coding portfolio before the decode work selected by its
result. The local arm reached a passing patch in a 13.197-second median and AlignRuntime required
149.273 seconds. Items 58 and 68 subsequently shipped two complete-request improvements on the
same model and host: combined K/V staging reduced the fixed seed-5 request from 30.451 seconds to
18.429 seconds, then the exact-safe plane/cache combination reduced item 62's 19.267-second
baseline to 17.423 seconds. The primary project metric is time to a passing patch, so the next
decision must measure the accumulated shipped runtime rather than infer provider-level progress
from those single-request results.

This capability repeats item 56's exact task, prompts, ordered seeds, provider arguments,
validator, fresh local-server isolation, four balanced pairs, primary metric, and 50,000-ppm gate.
It changes no product behavior. `MET` closes R8 for this fixed consumer; `NOT_MET` or
`NOT_ELIGIBLE` records the remaining provider-level gap and selects the next evidence-based
capability without authorizing a new optimization seam.

## 2. Measurement-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | `R8-OLMOE-POST-OPTIMIZATION-SAMPLED-RUNTIME-DECISION`; `scripts/run-olmoe-post-optimization-sampled-runtime-decision`, with no arguments for the opt-in real run and `--self-test` for the model-free owner |
| Consumer | one coding caller seeking the first passing patch from item 56's fixed sampled portfolio through either shipped `ModelProvider` arm after items 58 and 68 |
| Fixed workload | inherit item 56 byte-for-byte: task, system/user prompt, maximum 128 completion tokens, temperature 300,000 micros, seeds `[1,2,3,4,5,6,7,8]`, strict extractor, validator, stop-on-first-pass rule, provider arguments, and 975,175,680-byte cache budget |
| Pair schedule | `(local,runtime)`, `(runtime,local)`, `(runtime,local)`, `(local,runtime)`; one synchronous arm at a time; one fresh pinned local server per local portfolio |
| Isolation/lifetimes | inherit item 56 exactly: zero matching processes before local; one ready solely owned server alive through its portfolio; terminate, reap, and prove zero matches; zero matching processes before and after every runtime portfolio, including failure cleanup |
| Primary metric | item 56's nanoseconds from each portfolio leg's first provider-helper launch through validation of its first passing patch; local startup/readiness and teardown remain excluded |
| Gate | `MET` only when both arms pass all four legs, runtime is faster in every pair, and runtime median is at least 50,000 ppm below local median; `NOT_MET` when both pass four but speed fails; `NOT_ELIGIBLE` when either arm has fewer than four passing legs |
| Prior evidence | item 56's recorded 13.197-second local and 149.273-second runtime medians are diagnostic historical context only; the decision is formed solely from the four new paired samples |
| Shipped candidate | current `main` after item 68, including item 58's K/V staging transfer and item 68's exact-safe plane comparison plus cache-backed phase B; full-width phase A remains shipped |
| Identity | independently pin item 56's owner/workload contract, item 68's final qualification owner, and its complete transitive shipped source chain; the delegated result records the clean evaluated head and freshly built helper/shim and rechecks all inherited external identities |
| Result | one exact-key schema-1 `R8_OLMOE_POST_OPTIMIZATION_SAMPLED_RUNTIME_DECISION` document on stdout and one concise stderr summary; its fields are item 56's schema with only the artifact identity changed; no partial JSON on failure |
| Validation order | arguments; prerequisites; imported workload and current source identities; clean head and item 56's full external/tool/validator controls; four isolated pairs; inherited schema/determinism/aggregate; unchanged head and source identities; ceiling; publication |
| Failure | nonzero exit and no complete document for invalid arguments, missing/unusable inputs, imported or current source drift, malformed delegated output, identity drift, process/lifetime failure, validator/provider failure, timeout, signal, or ceiling excess; `NO_PASSING_PATCH` remains measured data |
| Ownership | the item 69 runner owns one delegated item 56 process and forwards bounded termination; that process retains ownership of servers, helpers, validator workspaces, containers, logs, and cleanup |
| Persisted/cache identity | N/A: neither product cache/lifetime behavior nor a persisted format changes; the result is printed and not stored by the runner |
| Performance floor | unchanged 50,000-ppm paired time-to-passing-patch floor and every-pair direction rule |
| Cost ceiling | one monotonic 25-minute delegated decision ceiling; the wrapper adds only bounded identity/schema validation and cannot extend the delegated deadline |
| Acceptance evidence | author consistency; Python compilation; item 56 and item 68 owner self-tests; focused model-free self-test; one clean-head real decision; `git diff --check`; one comprehensive review; exact-head focused preflight |

Cross-host, GPU, throughput, quality-rate, arbitrary-task, persistent-provider, and general R8 claims
are N/A. This is one fixed model, task, host, and sampled portfolio.

## 3. Schema and closure matrix

Schema 1 preserves item 56's exact top-level and nested keys, candidate identity, portfolio records,
ten-field isolation proof, and aggregate. Only `artifact_kind` changes from
`R8_OLMOE_ISOLATED_SAMPLED_RUNTIME_DECISION` to
`R8_OLMOE_POST_OPTIMIZATION_SAMPLED_RUNTIME_DECISION`. A validator projects that identity back to
the item 56 artifact and applies the complete inherited validator before accepting the new result.

| Path | Construction/precondition | Success | Failure/malformed | Early exit/cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- | --- |
| Whole run | validate args/prerequisites and pin imported plus shipped sources before delegation | one inherited complete four-pair result with the new artifact identity | reject source, head, output, schema, aggregate, or deadline drift | no partial JSON; terminate and reap delegated owner | predecessor owners, focused projection tests, real result |
| Delegated owner | start item 56 runner with no arguments and the caller environment | unchanged external controls, build, portfolios, lifetimes, cleanup, and result | nonzero status, multiple/malformed stdout records, or invalid UTF-8 rejects | forward termination, then kill/reap only if bounded wait fails | injected success/failure/signal process tests |
| Local/runtime pair | item 56's exact balanced order and isolation preconditions | both arms produce validated portfolios and isolation proof | any provider, validator, process, or schema error rejects | inherited first-pass stop; item 56 cleanup owns server/helper/container state | item 56 self-test and four real pairs |
| Result projection | replace only delegated artifact identity | complete item 56 validator and aggregate accept | any other key/value mutation rejects | N/A | exact-key, artifact, malformed aggregate, and boolean-field tests |
| Identity/head | pin item 56, item 68, transitive sources, and clean evaluated head | source hashes and candidate head unchanged after delegation | any mutation or head mismatch rejects | no persisted state | source/head mutation self-tests and real before/after checks |
| Gate | use four newly measured local/runtime portfolio times | inherited `MET`/`NOT_MET`/`NOT_ELIGIBLE` decision | malformed/non-deterministic samples reject | no result before cleanup | inherited boundary vectors plus real aggregate |

Public product API ownership, exchanged provider schemas, cache policy, graph arithmetic, numerical
semantics, and allocation/move rules are N/A because item 69 is a qualification-only composition of
already-shipped provider behavior.

## 4. Implementation and verification map

1. Add one thin runner that imports and independently pins item 56's workload owner and item 68's
   full shipped source chain.
2. Delegate one complete item 56 run, accept exactly one result, change only its artifact identity,
   and validate the projection with item 56's complete result validator.
3. Run the predecessor owners and focused self-test, then one clean-head real decision. Record the
   exact result here, in the roadmap, and in `HANDOFF.md`.
4. If the result is not `MET`, select the next capability from measured remaining absolute cost;
   this decision alone authorizes no product change.
5. Complete one comprehensive review, consolidate accepted findings, run exact-head preflight and
   required GitHub checks, merge, and continue.

No product source, Make target, aggregate membership, platform profile, stress suite, corpus, broad
`make ci`, or unrelated benchmark is selected.

## 5. Recorded decision

Design checkpoint `a2b73d6` fixed the contract before the focused owner. Implementation checkpoint
`81992f0ac333fb5418c1ded947c099d3af3d179e` added only the qualification wrapper. The complete
run evaluated that clean head on Darwin arm64 25.5.0 with Align
`8cefc803d5c7f883a8db5b67250ed4ed069b43a4` and every item 56 model, pack, geometry, server,
validator, compiler, C toolchain, linker-search, ggml, task, and prompt identity. The delegated
decision completed in 506.356 seconds and the wrapper completed in 506.52 seconds, below the
25-minute ceiling.

Both arms passed all four portfolios at candidate 5, seed 5, and selected the same passing patch
SHA-256 `5d6b107e706a5a55c945bc0b41296e255013a1516e0a6211ccc9da65001252dc`.
Local portfolio times were `[14017794083,14438206625,13967618667,13916119042]` ns, with a
13,992,706,375-ns median. Runtime portfolio times were
`[89506001833,90883117000,91948687375,93119518084]` ns, with a 91,415,902,187-ns median.
Runtime was slower in every pair and the paired gain was -5,533,111 ppm, so the decision is
**`NOT_MET`** and R8 remains open.

The result nevertheless confirms that the shipped decode work materially improved the primary
metric. Against item 56's rounded 149.273-second historical runtime median, the new runtime median
is 57.857 seconds or 387,592 ppm lower. That comparison is diagnostic: only the four new paired
samples decide this capability. Runtime remains 6.53 times the newly measured local median, and
each runtime portfolio still spends roughly five complete provider calls reaching candidate 5.

All four fresh local servers were ready, solely owned, alive through their portfolio, terminated,
reaped, and absent afterward. Every runtime leg began and ended with zero matching processes. The
ordered candidate statuses, selected seed, output hashes, patch hashes, candidate counts, and
within-arm determinism passed the inherited validator. Final head and all independently pinned
source identities remained unchanged.

Persistent provider construction is not selected: item 55 bounded repeated pre-prefill
construction at 0.272 seconds per request, far below the remaining approximately 77.4-second
portfolio gap. Item 70 will instead reaggregate the current fixed request's already-instrumented
remaining-decode buckets after items 58 and 68 and select one directly measured next seam or a
narrower diagnosis. This result authorizes no product change by itself.
