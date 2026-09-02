# R7-RUNTIME-PROVIDER

## 1. Consumer outcome and boundary

R7-PROMPT ends at exact prompt token ids and the resident dense runtime begins at those ids, but no
real `ModelProvider` caller can yet select that runtime or receive completion text. This capability
closes that consumer boundary for the pinned dense Qwen2.5-Coder model: one ordinary
`GenerationRequest { system, user }` is rendered and tokenized from a retained GGUF snapshot, run
greedily through the resident CPU decode loop, stopped at EOG or the declared maximum, decoded back
to UTF-8, and returned by `provider.generate`.

The capability also owns R7's provider-swap gate. One fixed `python-inclusive-range` coding request
is submitted through both the shipped local OpenAI-compatible provider and the new in-process
provider. Both use the same system text, user text, temperature, and completion bound; both existing
schema-2 `GenerationRecord` values are retained; and both completions must pass the existing coding
task validator after the gate's deterministic raw-or-single-fence diff extraction.

This is not a general sampler or a new inference engine. Streaming, temperature other than zero,
seeded sampling, runtime cancellation/timeouts, prefix-store reuse, GPU execution, MoE execution,
tool calls, chat history, and completion repair are deferred. Existing `--decode-step` semantics and
its persisted schema stay byte-for-byte unchanged.

## 2. Authoritative public-contract ledger

This section is the single authority for every changed public API, CLI, identity boundary, result,
error, validation order, owner, and acceptance target in this capability.

### 2.1 Capability record

| Field | Contract |
| --- | --- |
| Capability | `R7-RUNTIME-PROVIDER` |
| Consumer | `provider.generate`, then the existing provider CLI/result writer and fixed-task gate |
| Model | the same dense Qwen2.5-Coder-7B Q4_K_M GGUF used by R5-R7 |
| Execution | CPU, resident weights, greedy argmax |
| Primary observable | returned completion UTF-8 and existing `GenerationRecord` schema 2 |
| Termination | first generated EOG token, excluded from text; otherwise exactly `max_tokens` generated ids |
| Owner modules | `tokenizer_qwen2`, `alignpack`, `decode_step`, `provider_runtime`, `provider`, `model`, `main` |
| Hosted owner | `make runtime-provider-smoke` |
| Regression owners | `make tokenizer-smoke layer-forward-smoke provider-smoke runtime-provider-smoke` |
| Real qualification | `make runtime-provider-gate` |
| Publication owner | `python3 scripts/pre-pr --owner-test R7-RUNTIME-PROVIDER -- make tokenizer-smoke layer-forward-smoke provider-smoke runtime-provider-smoke` |
| Prerequisites | merged R7-PROMPT and `.align-revision` `27770420555d19b98eced133369c168e9c6d4a2f` |
| Persisted/cache identity | no new persisted format or cache; the CLI writes unchanged `GenerationRecord` schema 2; alignpack remains format 1 and is source-bound by its existing source record |
| Schema version | N/A for new surfaces: all new values are in-memory; existing result schema stays 2 |
| Network boundary | only the comparison leg uses the existing loopback OpenAI-compatible provider; align-runtime opens no socket |
| Performance claim | none; the gate has a maintenance ceiling, not a speed claim |
| Build boundary | `make build` / `make run` own the now-unconditional runtime FFI link through `scripts/run-main-with-shim`; hosted builds embed the unavailable-engine stub, while explicit ggml inputs build the real shared shim |

### 2.2 Provider data and dispatch

`src/model.align` adds one enum arm and two explicit provider-configuration paths:

```text
pub ProviderKind { CloudOpenAI, LocalOpenAI, LlamaCpp, AlignRuntime }

pub ProviderConfig {
  kind: ProviderKind,
  endpoint: str,
  model: str,
  api_key: str,
  timeout_ns: i64,
  tokenize_endpoint: str,
  max_response_bytes: i64,
  runtime_pack_path: str,
  runtime_geometry_path: str,
}
```

Every existing construction site sets both runtime paths to `""`. An `AlignRuntime` construction
sets `model` to the GGUF path, the two runtime fields to the alignpack and exact model-IR document
paths, and `endpoint`, `api_key`, and `tokenize_endpoint` to `""`. Existing provider modules reject
`AlignRuntime`; prompt experiment/generation HTTP encoders cannot parse it from their manifests and
their exhaustive internal matches reject it. This capability does not silently make the in-process
provider eligible for evaluation formats whose provider identity and seed-attestation contracts do
not yet declare it.

`provider` dispatch is:

| Operation | `AlignRuntime` behavior |
| --- | --- |
| `generate(config, request)` | runs `provider_runtime.generate`; returns owned UTF-8 completion |
| `stream(config, request)` | `Err(Error.Invalid)` before artifact/model I/O |
| `count_tokens(config, text)` | exact Qwen2 count from `config.model`; tokenizer failure propagates or maps to `Invalid` |
| `count_prompt(config, request)` | exact prepared prompt count; any failure returns `{ count: -1, exact: false }` |
| `model_info(config)` | provider `align-runtime`, endpoint `in-process`, stream false, seed false, token count exact true |

All existing provider arms retain their wire bytes and behavior. Supplying either runtime path to a
non-runtime provider is rejected by that provider's existing kind validation only where that module
already validates configuration; the fields otherwise remain inert. The in-process arm requires
both fields and never interprets existing endpoint fields as paths.

### 2.3 Runtime request and configuration contract

`provider_runtime.generate` accepts only the following configuration/request subset, in this exact
first-applicable order. Every refusal is `Err(Error.Invalid)` and occurs before the next row's side
effect.

| Step | Validation | Side effect admitted after success |
| --- | --- | --- |
| 1 | `kind == AlignRuntime` | none |
| 2 | endpoint, API key, and tokenizer endpoint are empty; `timeout_ns == 0` | none |
| 3 | GGUF, pack, and geometry paths each satisfy the existing non-empty, at-most-4096-byte, no-NUL grammar | none |
| 4 | `max_response_bytes` is in `1..=1,048,576` | none |
| 5 | `temperature == 0.0`, `seed == None`, and `max_tokens` is in `1..=128` | none |
| 6 | one `GgufSnapshot` opens and its table is structurally valid | one retained file description |
| 7 | Qwen frontend derivation succeeds and the supplied geometry is at most 16,777,216 bytes and exactly equals its complete `R1_MODEL_IR` schema-2 document | one bounded geometry read; no pack payload read |
| 8 | alignpack header/regions/source record are valid and source identity exactly matches that retained snapshot | bounded pack metadata reads; no weight payload read |
| 9 | chat template, prompt size, tokenizer, and EOG metadata/token set validate through `prepare_generation_snapshot` | bounded tokenizer arrays and prompt ids |
| 10 | prompt count plus `max_tokens - 1` fits the Qwen prefill/context/attention bounds | no inference allocation |
| 11 | the reopened geometry bytes still equal step 7, the exact opened pack handle still carries step 8's source identity, resident prefill/decode succeeds, and every published logit plane is finite | one bounded geometry read, bounded pack metadata reads, then resident arena and ggml objects, all run-scoped |
| 12 | generated non-EOG ids decode under a tokenizer whose `tokenizer_id` equals step 9 | one fail-closed path reopen; owned completion text |
| 13 | completion bytes do not exceed `max_response_bytes` | returned owned text |

Exact float equality to `0.0` admits `-0.0`, which has the same greedy meaning. A positive timeout
is not accepted and not ignored: the runtime has no cancellation primitive at this Align pin. A
seed is not accepted and not ignored: greedy execution has no seeded twin record and
`model_info.supports_seed` is false.

The geometry comparison is exact bytes, not a field subset. It binds every scalar consumed by
`layer_qwen2.parse_geometry`, including RoPE and RMS values that alignpack member-table validation
alone cannot bind. Inference compares its reopened geometry image to those retained bytes before
parsing the same reopened image, and checks the source identity against the exact pack handle that
the arena will consume. Atomic replacement of either public artifact path therefore cannot retarget
validated inference. In-place mutation through another handle remains outside the immutable-input,
single-writer precondition shared by the existing resident runtime. Detokenization reopens the GGUF
path only after the resident arena has dropped; its published tokenizer digest must equal the
retained snapshot's digest or the call fails without returning text.

### 2.4 Snapshot prompt and EOG API

`tokenizer_qwen2` adds:

```text
pub GenerationPromptResult {
  status: TokenizerStatus,
  error_code: string,
  error_detail: string,
  template_id: string,
  tokenizer_id: string,
  vocab_size: i64,
  merge_count: i64,
  system_bytes: i64,
  user_bytes: i64,
  prompt_bytes: i64,
  token_ids: array<i64>,
  eog_token_ids: array<i64>,
}

pub fn prepare_generation_snapshot(
  snapshot: gguf.GgufSnapshot,
  system: str,
  user: str,
) -> Result<GenerationPromptResult, Error>

pub fn prepare_generation_model(
  model_path: str,
  system: str,
  user: str,
) -> Result<GenerationPromptResult, Error>
```

The model wrapper validates/open the path once, then delegates. The snapshot function consumes the
snapshot; callers may borrow its table before the call but cannot use it after. Template validation,
prompt rendering, tokenizer loading, identities, and prompt ids are exactly R7-PROMPT's order and
bytes. `prepare_prompt_model` continues to return its unchanged result and is implemented over the
same private preparation stages; no R7-PROMPT success/error field changes.

After tokenizer load and before regex compilation/encoding, EOG construction adds, deduplicates,
and publishes ids in ascending numeric order from:

1. present integer metadata keys `tokenizer.ggml.eos_token_id`, `eot_token_id`, `eom_token_id`,
   `fim_pad_token_id`, `fim_rep_token_id`, and `fim_sep_token_id`;
2. tokenizer entries whose exact text is in pinned llama.cpp build 10566's EOG vocabulary for this
   supported Qwen2 tokenizer: `<|eot_id|>`, `<|im_end|>`, `<|end|>`, `<|return|>`, `<|call|>`,
   `<|flush|>`, `<|calls|>`, `<end_of_turn>`, `<|endoftext|>`, `</s>`, `<|eom_id|>`, `<EOT>`,
   `_<EOT>`, `[EOT]`, `[EOS]`, `<|end_of_text|>`, `<end_of_utterance>`, `<eos>`, `<turn|>`,
   `<|tool_response>`, `<｜end▁of▁sentence｜>`, and `[e~[`.

The Qwen2 target does not contain the model-family combinations that trigger llama.cpp's Harmony,
Solar, Gemma, or PaddleOCR removal exceptions; encountering `<|return|>` plus `<|call|>` plus
`<|end|>`, `<|calls|>` plus `<|flush|>` plus `<|end|>`, or `<|tool_response>` plus `</s>` is
therefore `R7_EOG_UNSUPPORTED`, not an attempt to generalize this Qwen-only tokenizer. A present
metadata key with the wrong GGUF scalar class, an out-of-vocabulary id, an empty final EOG set, or
more than 256 EOG ids is `R7_EOG_METADATA`. On every error both result arrays are empty; the known
template/tokenizer/count fields follow the transition already reached. Outer path/open failures stay
outer `Err` as in R7-TOKENIZER and R7-PROMPT.

### 2.5 Alignpack source-identity API

`alignpack` adds a retained identity value and two bounded verification seams:

```text
pub SourceIdentity {
  file_size: i64,
  data_offset: i64,
  tensor_count: i64,
  kv_count: i64,
  version: i64,
  alignment: i64,
  total_tensor_bytes: i64,
  header_region_sha256: string,
}

pub fn empty_source_identity() -> SourceIdentity

pub fn verify_source_identity_snapshot(
  borrow snapshot: gguf.GgufSnapshot,
  pack_path: str,
) -> Result<SourceIdentity, Error>

pub fn verify_source_identity_file(
  borrow pack: file,
  borrow expected: SourceIdentity,
) -> Result<(), Error>
```

`empty_source_identity` is the inert value used only by the unchanged non-generation diagnostic
path; generation never accepts it because its exact file check fails. The snapshot seam validates
the named pack once and returns the identity derived from the retained GGUF snapshot. The file seam
validates the existing format-1 header and region layout on an
already-open handle, reads its 128-byte source record, and compares `file_size`, `data_offset`,
`tensor_count`, metadata KV count, GGUF version, alignment, header-region byte count,
`total_tensor_bytes`, and SHA-256 of exact snapshot bytes `[0, data_offset)`. Inference calls the
file seam on the exact handle it subsequently consumes. The header region retains the existing
128 MiB ceiling. Neither seam reads alignpack payload or writes anything. Any invalid path,
malformed header/region/source record, I/O failure, nonzero reserved field, or identity mismatch
returns an error; neither weakens or replaces `verify_pack`, whose question is whole-payload
correctness.

### 2.6 Stop-aware resident generation seam

`decode_step` adds this public generation entry point:

```text
pub GenerationParts {
  outcome: model_forward.Outcome,
  token_ids_json: string,
}

pub fn generate_resident(
  pack_path: str,
  geometry_path: str,
  expected_geometry: str,
  source_identity: alignpack.SourceIdentity,
  borrow prompt_token_ids: array<i64>,
  borrow eog_token_ids: array<i64>,
  max_tokens: i64,
) -> GenerationParts
```

It returns the existing scalar `Outcome` plus a bounded owned JSON array of generated ids. The typed
`StepColumns` stays inside `decode_step`: Align Request 43 still refuses a caller in another module
to read a `borrow mut` output record after the foreign call, and this uses the already-shipped R5C
`render_parts` pattern instead of inventing a hypothetical language surface. The prefill argmax
`d1` is `Outcome.argmax`; each completed generation graph contributes its next id to the JSON array.
Its implementation shares the current validation, resident allocation,
prefill, graph, plane, and converged teardown. Internally it uses
`max(1, max_tokens - 1)` as the allocation/legacy-step operand and carries `max_tokens` separately
to the stop-aware loop. The existing `execute` and CLI pass `generation = false` and remain
behavior- and document-identical.

Generation semantics are exact:

```text
d1 = argmax(prefill(prompt_ids))
generated = [d1]
while len(generated) < max_tokens and last(generated) not in EOG:
    next = argmax(decode(last(generated), n_past))
    generated.append(next)
termination = EOG if last(generated) in EOG else MAX_TOKENS
completion_ids = generated without the final id only when termination == EOG
completion_text = detokenize(completion_ids, skip-control)
```

Thus `max_tokens == 1` and immediate EOG execute no decode graph. At most 127 decode graphs run. The
EOG graph is never followed by another graph. An EOG id counts toward the maximum but is never
rendered. An empty completion is a successful immediate-EOG result. Membership is a bounded linear
scan of at most 256 ids and happens before each graph.

The runtime width is `prompt_count + max_tokens - 1`, with a minimum of `prompt_count + 1` only for
the existing allocation grammar; masked unused capacity does not create a graph. Acceptance
requires prompt count `1..=2048`, width within geometry context and the existing 4096 attention
ceiling, every prompt/EOG id in `0..n_vocab`, and the existing pack/geometry validation. Errors use
the existing `Outcome.code/detail`; `provider_runtime` maps any non-empty code to `Error.Invalid`.
No new persisted decode document is emitted by this entry point.

### 2.7 CLI and common result

The existing command gains a distinct runtime grammar:

```text
main --provider align-runtime MODEL.gguf MODEL.alignpack MODEL-IR.json PROMPT RESULT.json [MAX_TOKENS]
```

`MAX_TOKENS` defaults to 64. This arm is generate-only, uses the existing fixed coding-assistant
system text, sets timeout zero and response cap 262,144 bytes, and writes the same
`result.GenerationRecord { schema_version: 2, operation: "generate", ... }` as every provider.
Its provider/model/endpoint fields are `align-runtime`, the supplied GGUF path, and `in-process`.
Prompt, completion, and total token counts are exact on success. Outer CLI arity, numeric, and path
failures write no result. A provider failure writes the existing schema-2 error record with
`status: "error"`, empty output, `error: "invalid"`, and `error_code: -1`.

All earlier `--provider cloud|openai-local|llama ...` positional meanings and defaults are unchanged.
No environment variable, ambient server, API key, endpoint, `DOCKER_HOST`, or tokenizer endpoint is
consulted by the runtime arm.

R7 makes the resident runtime part of `main`'s import graph, so the repository wrapper also owns its
previously separate `align_ggml_shim` link. `make build` and `make run` route through
`scripts/run-main-with-shim` with exactly two build modes:

| Build input | Shim and result | Allocation / cleanup | Failure |
| --- | --- | --- | --- |
| `ALIGN_LLM_GGML_INCLUDE` unset | compile the ordinary unavailable-engine stub as a temporary static archive and embed it in `main`; non-runtime commands work and runtime dispatch fails through the existing unavailable-backend result | one `mktemp -d` outside the work tree, removed after link/run on every exit and signal; `main` is the only retained product | invalid private static selector, missing `cc`/`ar`, compile/archive/link/run failure |
| `ALIGN_LLM_GGML_INCLUDE` set | existing real shared shim using the explicit include and optional `ALIGN_LLM_GGML_LIB`; `main` can execute align-runtime | explicit `ALIGN_LLM_GGML_SHIM_DIR` or existing `build/lib` default; shared library lifetime remains caller/developer owned | unusable include/lib, incompatible force/static request, compile/link/load failure |

`ALIGN_LLM_GGML_SHIM_STATIC` is a private wrapper-to-builder selector accepting only `0` or `1`;
static `1` refuses a real include or any forced engine/failure mode. `AR` defaults to `ar`, matching
the fresh image's authenticated tool inventory. `ggml_ffi` explicitly records `m` after
`align_ggml_shim` because the pinned ELF driver places its automatic support libraries before user
archives; Align Request 54 owns removing that source-level repetition after the driver repairs its
static-archive order. The default path neither consumes a stale
`build/lib` shim nor leaves an extra fresh-worker overlay entry. No build variable is consulted by
the runtime provider after process start.

The hosted prompt seed-attestation harness imports the exhaustive `provider` dispatcher directly,
so it also reaches the runtime FFI even though it never selects `AlignRuntime`. Its compiler `run`
action routes through the same wrapper and temporary static stub; no other standalone hosted
harness imports `provider` outside a wrapper-owned `main` build.

### 2.8 Fixed coding-task gate and cost ceiling

`make runtime-provider-gate` is opt-in through the same pinned real-model/tool inputs as prompt and
decode parity plus a running or runner-owned pinned llama-server. Absent prerequisites print one
`R7-RUNTIME-PROVIDER: N/A (...)` line and succeed; a configured but unusable prerequisite fails.
The runner verifies exact model/tool revisions before work, derives one alignpack and one exact
model-IR document in a temporary directory, and submits this fixed request to both
`LocalOpenAI` and `AlignRuntime`:

- system: the provider CLI's existing fixed coding-assistant sentence;
- user: the checked-in `python-inclusive-range` source, allowed one-line edit, test intent, and the
  fixed unified-diff prefix through the removed line; the model must generate the added line and no
  completion repair is admitted;
- temperature: `0.0`;
- seed: absent;
- maximum: `128` tokens. The pre-implementation value of 64 was rejected by the first real gate
  attempt: llama.cpp produced the correct patch shape but was truncated at `return sum(range` before
  the closing hunk, so 128 is the smallest power-of-two ceiling that can carry the consumer result.

The runner persists both unchanged schema-2 records, accepts either a raw unified diff or exactly
one Markdown `diff` fence with no surrounding non-whitespace text, and invokes
`eval/runners/run-coding-task.py` against the existing task manifest for each extracted patch. It
requires two `status: ok` records and two passing task results; output equality is not required.
Temporary model-IR, pack, task copies, responses, and server state are removed on every exit.

The 20-minute timer starts as soon as all four configured prerequisites are present, before the
validation-image probe, full model digest, server-version check, scratch check, or any derived work.
The first complete qualification on the 16 GiB Apple reference host passed in 62.7 seconds. Both
the pinned llama.cpp comparison leg and `AlignRuntime` produced a validator-passing patch with
SHA-256 prefix `5d6b107e706a`; equality was observed, not required. Earlier prompt-shape probes are
not qualification evidence: one exposed the 64-token truncation that set the bound, while later
probes either emitted a malformed hunk count or omitted the fixed diff envelope. The final prompt
therefore fixes only that envelope and leaves the replacement line to each provider.

After the final timer repair, the complete gate passed in 75.2 seconds on the same host, including
the validation-image probe, full model digest, server-version check, and scratch check. Both
provider legs again produced the validator-passing patch with SHA-256 prefix `5d6b107e706a`.

**Pre-implementation maintenance ceiling:** 20 minutes wall time for the complete gate after the
model and pinned binaries are already materialized, at most one alignpack construction, one local
server generation, one resident runtime generation, and two task validations on the 16 GiB reference
Apple host. This is a resource ceiling, not a performance baseline or shipping-speed claim. A run
above the ceiling fails and must be re-scoped before merge; no timing improvement is claimed.

## 3. Deterministic validation and error precedence

The complete cross-module order is: provider kind/config/request; snapshot table; exact derived
geometry; pack source identity; chat template; prompt arithmetic; tokenizer; EOG set; runtime token
and width bounds; pack/geometry execution plan; resident allocation; prefill; stop-aware decode;
same-tokenizer detokenization; response cap; result persistence. First failure wins. In particular:

- malformed geometry wins over malformed pack/tokenizer because no pack payload or tokenizer array
  is admitted until geometry is bound;
- pack identity mismatch wins over malformed tokenizer/EOG metadata;
- tokenizer/EOG failure wins over max-width inference refusal after request-level `max_tokens` was
  accepted;
- a non-finite prefill or decode-step logit plane fails generation before any token-id JSON is
  published; the existing diagnostic API continues to report its unchanged counters;
- immediate EOG wins over maximum termination when `max_tokens == 1`, because the generated id is
  classified before the reason is published;
- inference failure returns no partial completion even if one or more ids were produced;
- tokenizer replacement at final decode returns no text rather than decoding under a new vocabulary;
- result-sink failure occurs only after generation and remains the existing CLI `Err` behavior.

## 4. Cross-cutting closure matrix

| Surface | Formation / validation | Success | Failure / malformed | Early exit and cleanup | Exact regression evidence |
| --- | --- | --- | --- | --- | --- |
| `ProviderKind` / config constructors | every match and constructor names runtime fields | one explicit runtime arm | old modules reject it; old fields inert | no artifact I/O before kind/config checks | provider compile graph; provider smoke exhaustive info/dispatch |
| `provider_runtime` request | steps 1-5 in §2.3 | greedy owned text | seed/temp/timeout/field/path/limit matrix | zero file opens on lexical refusal | runtime provider API harness |
| retained GGUF snapshot | open once; table borrowed for IR/identity then moved to tokenizer | one consistent prompt/model identity | structural, replacement, and reopen-tokenizer mismatch | file drops on every `?`/return | tokenizer snapshot replacement; runtime cross-model identity refusal; final digest guard |
| geometry | bounded read; exact newly derived schema-2 bytes, then bounded exact reopened-image comparison | the compared reopened image supplies all execution scalars | truncation, alternate path text, scalar drift, oversized or sparse replacement, atomic replacement | no pack/tokenizer/inference after first mismatch; reopened image drops after parse | runtime exact success, byte-drift and ordinary oversize refusals, plus the 1 TiB sparse replacement API refusal |
| alignpack source identity | format/regions/record then nine identity fields; inference repeats the check on its exact opened handle | no payload read during either check; the checked inference handle supplies weights | header, region, reserved, digest, same-shape-other-model, replacement handle | first-pass handle drops; inference handle drops through converged teardown | existing alignpack malformed corpus, runtime cross-model identity refusal, and exact replacement-handle API refusal |
| prompt/tokenizer/EOG | existing prompt stages then metadata/text EOG set | owned ids and ordered EOG ids | wrong type/range/empty/overflow/unsupported family combination | both arrays empty on data error | tokenizer generation API result-field matrix |
| runtime bounds | ids, prompt, width, vocab before arena | legal prefill + at most 127 steps | OOV prompt/EOG, zero/oversize prompt, context/width | no resident buffer on refusal | generation bounds harness |
| resident arena / ggml | exact geometry image and pack handle rechecked before existing one fill/wrap/backend schedule | finite prefill and steps, one converged teardown | identity failure, non-finite prefill/step, failure in fill, wrap, prefill, step k | created/freed counters balance; no token ids or partial text on generation failure | replacement-handle API refusal, forced non-finite runtime provider case, existing layer-forward forced-failure corpus, and runtime generation successes |
| EOG/max loop | classify d1 before graph; classify every argmax before next graph | exact generated sequence/reason | duplicate EOG ids harmless; empty set refused earlier | zero graph for max1/immediate EOG; no post-EOG graph | deterministic tiny-model argmax cases |
| detokenization | omit terminal EOG, skip controls, compare tokenizer digest | owned UTF-8, empty allowed | invalid id/output/changed tokenizer | resident memory is gone before reopen | immediate/one-step EOG omission, max inclusion, snapshot replacement, provider digest guard |
| `count_tokens` / `count_prompt` | same Qwen tokenizer and prompt contract | exact true | `count_prompt` sentinel; token error propagates | tokenizer arrays drop per call | provider count rows |
| CLI/result | runtime grammar selected before legacy parse | unchanged schema-2 success record | outer no-file failures; existing error record after dispatch | sink failure leaves provider result behavior unchanged | byte/field goldens and legacy provider goldens |
| main and provider-harness build/link | validate wrapper action and static selector before tools; explicit include selects real mode | hosted main, direct prompt evaluator/seed harnesses, opt-in C4 gate generation children, and the direct provider harness embed the unavailable stub; explicit real main resolves the shared shim | selector/tool/compile/archive/link/load failures are nonzero | temporary archive directory drops on success, error, and signal; no hosted overlay artifact beyond the requested executable | clean macOS build without `build/lib`; clean Linux prompt seed and prompt evaluator owners; direct-main-build audit; Linux publication owner and installed aggregate |
| fixed-task runner | prerequisite identity, one temp root, fixed request | two retained records and two passing validations | configured-tool, generation, extraction, validation, timeout | server/process/temp teardown on all signals and exits | runner self-test plus real qualification |
| Makefile/topology | main shim wrapper, one hosted owner, and one opt-in gate; coding-baseline artifacts bind the wrapper, builder, and static stub source | hosted owner reached once | clean-link, omission/duplication/configured N/A mutant | static shim is temporary; qualification excluded from aggregates | clean `make build`; `gate-topology-check`; direct source -> oracle -> finalization baseline chain; `make ci` because membership changes |

Move-in/out is applicable to the consumed `GgufSnapshot`, tokenizer arrays, generated-id builders,
and completion string and is tested at their module owners. Source nulling is N/A: Align move
semantics make the moved value unavailable rather than exposing a nullable source. Replacement is
applicable to the GGUF, geometry, and alignpack paths: the final tokenizer digest, exact reopened
geometry comparison, and exact inference-handle source check fail closed at their respective
consumption boundaries. Generic monomorphization and interface serialization are N/A: all records
are concrete and Align has no interfaces here. Shared process state is limited to the real gate's
one runner-owned server; hosted owners use independent processes and temporary roots. Concurrent
gate runs are supported only with separate temporary roots and server ports.

## 5. Implementation and acceptance map

1. Add the provider enum/config fields and update every exhaustive match/construction site.
2. Add snapshot-based generation prompt/EOG preparation without changing R7-PROMPT results.
3. Add bounded alignpack source-identity verification over the retained snapshot and exact
   inference handle.
4. Add stop-aware finite-only generation mode behind the unchanged decode CLI/API behavior.
5. Implement `provider_runtime`, exact counting, model info, and runtime CLI/result routing.
6. Add independent synthetic fixtures for EOG, artifact identity, loop termination, provider errors,
   common result bytes, and old-provider isolation; add the hosted target to `make ci` once.
7. Make the public build wrapper self-sufficient for the runtime FFI, then add the opt-in fixed-task
   gate and topology/configuration tests.
8. Run the author ledger-to-prose consistency pass, map every applicable matrix row to final diff
   and passing evidence, then run the publication owner, one comprehensive review, consolidated
   repair, exact-head preflight, PR checks, and merge.

The owner does not claim that `make ci` covers the real-model gate. `runtime-provider-gate` remains
named and focused because it needs a 4.7 GB model, pinned llama.cpp, substantial resident memory,
and up to the recorded 20-minute ceiling.
