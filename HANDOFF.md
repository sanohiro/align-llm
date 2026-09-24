# Session handoff

Read `CLAUDE.md` first. Architecture and ordering live in `docs/specs/`.

## Active local OpenAI serving capability (2026-09-24)

Branch: `agent/openai-serving-next`, based on merged PR #298 (`77f42a55`). The
Qwen3.5-0.8B multi-turn history prerequisite is merged. The active consumer is
loopback-only `--serve-openai` with non-stream and per-token SSE chat over one
retained native Metal session. Code, real-model owner, plan map and backend parity
are in progress; no serving commit or PR is published yet. The root `main`
worktree's unrelated `docs/align-requests.md` modification remains untouched.

Next actions: finish the real owner including startup refusal, disconnect and
restart; build after formatting; run the existing Qwen3.5 generation owner and
Python boundary guard; commit; run executable `scripts/pre-pr` with the serving
owner; conduct one comprehensive review and repair findings; publish and merge
after checks, then refresh main and select the next small-model capability.
Align Request 120 records that pinned `std.http.accept()` allocates the whole
request body before application validation, so the current 1 MiB HTTP body cap
is post-read. The endpoint stays loopback-only until Align supplies a bounded
inbound accept and the consumer verifies it. The existing same-pin Metal
speed gap versus llama.cpp remains unresolved; no faster-than-llama.cpp claim
is active. CUDA and CPU Qwen3.5 serving are unmeasured/deferred in
`docs/backend-parity.md`.

The current real owner has passed pinned llama.cpp two-turn three-token output,
SSE parity and termination, wrong-model/unsupported-input refusals, and one
disconnect followed by a correct fresh request. A sample on Apple M1 observed
0.735 s startup, 0.114 s non-stream completion, 0.064 s first stream content
and 0.099 s stream completion; this is a functional owner observation, not a
speed claim or paired benchmark. `gmake build`, `gmake fmt`, and
`python3 scripts/check-python-boundary` passed before the latest owner-script
extension. Rerun the affected commands at the coherent checkpoint.

## Prior Qwen3.5 text capability checkpoint (2026-09-24)

Branch: `agent/qwen35-prefill-next`, based on merged PR #297 (`8080f542`). Active user priority is
staged Qwen3.5 native text correctness and measured optimization on small and middle-size models,
then a normally usable OpenAI-compatible local endpoint. Large models, including Qwen3.8-27B and
Qwen3.5-35B-A3B, are deferred. `docs/specs/qwen35-text.md`
owns the model contract; `docs/specs/roadmap.md` owns the delivery order. The active work is
Qwen3.5-0.8B multi-turn prompt history as the first local HTTP serving prerequisite. The
same-pin GPU speed gap remains unresolved; further speed changes need an operation-level
hypothesis or a usable kernel trace. The local HTTP contract is settled but serving
implementation has not started.

The first independently usable boundary is merged: `--model-ir`, `--pack`, and
`--pack-verify` accept a real Qwen3.5-0.8B Q4_0 GGUF. Its SHA-256 is recorded in the plan;
Model IR claims all 320 tensors, has 50 blocks, and passes its size-sum check. The synthetic
frontdoor owner passes positive IR/pack/verify and missing-key, wrong-shape, and wrong-tokenizer
refusals. Existing model IR and alignpack smoke owners pass. One comprehensive Codex review found
missing tokenizer-vocabulary validation; the full tokenizer metadata class was repaired and its
focused owners passed again. Final-head preflight and all three hosted checks passed for #294.
The Qwen3.5 tokenizer CLI merged in #295 with eight paired real-file cases against pinned
llama.cpp and all three hosted checks. Text-only `--prepare-prompt` merged in #296 with five
paired prompt cases, reference bottleneck diagnostics, review disposition, final-head preflight
and all three hosted checks. Native `align-runtime` generation is the active boundary.

Retained Qwen3.5 sessions merged in #297. The batch reuses decode graphs and clears resident KV
in one backend call while preserving full-vector finite-logit validation. The six-request real
smoke passes against pinned llama.cpp, including malformed-input recovery and max-one early exit.
Final-head local preflight and all three hosted checks passed. One comprehensive review found
that GPU argmax lost nonfinite-logit refusal; the path was removed. A later preflight caught
stale stub ABI context-size goldens from batched prefill; all seven corpora changed only those
sizes and the normal layer-forward owner passed before merge.

Next actions in priority order:
1. Continue the 0.8B prefill bottleneck investigation. A same-pin diagnostic on Apple M1 used
   identical 200 prompt IDs, 16 greedy tokens, matching output, and five samples after two warm
   requests: retained align-llm median 519.44 ms and llama.cpp median 478.13 ms. These were
   sequential runs, not five alternating pairs, and do not support a shipping speed claim.
   Align host sampling during repeated requests placed about 84% of main-thread samples in
   Metal command-buffer completion waits; GPU kernel attribution remains unresolved. A separate
   five-pair alternating 200-prompt/32-output diagnostic used identical input IDs and output
   text after two warm requests per process: align-llm/llama.cpp medians were 851.45/805.13 ms,
   with align-llm slower in all five pairs. An earlier sequential 32-output run misleadingly
   favored align-llm, so do not use that run for a speed claim. Metal graph logs showed 187
   matrix multiplications and 18 Gated DeltaNet operations in each decode graph for both
   implementations; raw node counts alone do not identify the cost. The contemporary llama.cpp
   HEAD `53ed051c` accepted the same GGUF, prompt IDs, and 32-token output. Five alternating
   pairs measured align-llm/current llama.cpp medians of 841.30/748.39 ms, with align-llm slower
   in all pairs. A scratch current-ggml bundle and shim built, but the old shim's private Metal
   graph-optimization call hits a new allocation-dependency callback assertion. Skipping that
   optimization for a diagnostic produced correct text at a warmed 845.24 ms median, not a
   speed gain. The optimization really registers dependencies for this Qwen3.5 graph, so a pin
   bump requires an allocator/scheduler integration that preserves those dependencies and full
   backend parity work; do not ship the no-optimization probe. The current scheduler appends
   dependency nodes to its allocation graph after Metal optimization; the shim's private ABI and
   direct `gallocr` path have no equivalent. Next, obtain a trace with shader rows or a graph-level
   operation timing breakdown before choosing another kernel or graph optimization. A temporary
   dyld interpose on the pinned shim measured four retained 200-prompt/32-output requests; after
   the first, graph compute consumed about 791-804 ms of 845-859 ms wall, with prefill about
   187-188 ms, decode about 603-617 ms, and full-logit reads about 3 ms. A follow-up
   same-pin, same-output, five-pair alternating phase probe instrumented both paths after two
   warm requests per process. Align/pinned llama.cpp medians were 762.73/710.02 ms wall,
   743.41/687.10 ms graph execution, 196.48/178.23 ms prefill, and 546.73/508.76 ms decode;
   Align was slower in all five pairs. The absolute wall times moved with host conditions, but
   this paired phase result locates the same-pin gap mainly inside graph execution: about 18 ms
   in prefill and 38 ms over 31 decode steps. Instrumentation includes scheduler and synchronization
   calls and is not a per-kernel GPU profile. The first independent prefill chunk and the fixed
   attention decode view are known graph differences, but neither is proven to explain the gap.
   A rounded indexed-KV view candidate preserved the six-request real-model owner but measured
   768.23/766.71 ms control/candidate request medians, three candidate wins, and
   545.07/546.38 ms decode-graph medians in five alternating pairs. It missed the floor and was
   reverted. Pinned Metal decode logs show equal 187 matrix multiplies, 18 Gated DeltaNet, and
   six Flash Attention operations; Align has 18 `CONT` and 42 `CPY` versus llama.cpp's six and
   36, but llama.cpp has more `GET_ROWS`. Optimized emitted LLVM IR confirms vectorized
   four-lane greedy scanning and shows per-decode key builder/SHA-256/string clone calls;
   the only reported 184-byte geometry copy is at session creation. Neither the extra graph
   operations nor the host hash is individually timed. Next, compare the six full-attention
   blocks and recurrent state operations at kernel level or with a bounded per-block ablation;
   do not infer a speed fix from graph counts alone.
   Matching llama.cpp's Q/V/K graph registration order passed the six-request real owner but
   measured 784.79/788.69 ms control/candidate request medians and three candidate wins;
   it was reverted. Align's decode graph has fewer nodes tagged concurrent (194 versus 286),
   yet a five-pair concurrency-disabled toggle produced inconsistent performance and did not
   establish causality. The generated LLVM IR shows the hot greedy scan is vectorized; the
   observed structural differences include KV-cache views/conversions and state access,
   which require operation-level timing before changing production code.
   Five alternating pinned-ggml graph-optimizer default/disabled pairs measured
   776.13/794.68 ms for Align (four default wins) and 737.93/751.05 ms for llama.cpp
   (five default wins). The optimizer helps both and is not the cause of the gap.
   The decode debug graph's only differing operation counts are Align/llama.cpp
   `CONT` 18/6, `CPY` 42/36, `GET_ROWS` 1/37, and `MUL` 42/43; actual kernel
   duration remains unavailable. A detailed Metal tensor trace identifies the six
   excess `CPY` operations as repeated F32-to-F16 conversions of the same
   attention mask, one per full-attention layer. The twelve excess `CONT`
   operations are explicit K/V permutation materializations; `slot_copy` only
   transfers tensor handles. The shared 36 `CPY` operations update recurrent
   state. These arise in the align-llm graph/shim and do not establish an Align
   language gap. Continue with operation-level GPU timing or a tightly bounded
   shared-mask/attention ablation before another production optimization.
   The shared-mask candidate passed the six-request real owner and reduced decode
   `CPY` from 42 to 37, but five alternating control/candidate pairs measured
   752.80/786.32 ms request medians and three candidate wins. It missed the
   material speed floor and was reverted. The remaining K/V `CONT` operations
   were tested with a llama.cpp-like token-major cache layout: the real owner
   passed and decode `CONT` fell from 18 to six, but five alternating pairs
   measured 772.08/774.50 ms control/candidate medians with two wins. The
   candidate was reverted. Both implementations' 187 decode matrix products
   match in quantized weight type/shape and F32 input shape/stride; the main
   Gated DeltaNet and convolution input shapes/strides also match. A temporary
   eight-command-buffer build of each pinned Metal backend produced matching
   text and GPU traces, but M1 exported no shader timing rows and the split
   changes execution. The specific slower kernel remains unknown. Keep the
   established same-pin baseline; resume speed work on a kernel-level trace or
   an independently testable operation hypothesis. The next concrete serving
   prerequisite is ordered multi-turn Qwen3.5 prompt rendering.
   Five alternating
   contemporary llama.cpp default/Metal-optimization-disabled pairs, using the third request
   after two warm requests per process, had 747.07/754.01 ms medians and three default wins.
   This does not explain the Align/current-reference gap. A five-pair
   256-token chunk trial and a five-pair state-only intermediate prefill trial both missed the
   15% floor and were reverted. The latter measured
   521.16/515.26 ms control/candidate medians and three candidate wins. Temporary timing placed
   retained prefill near 200 ms and decode near 300 ms. No faster-than-llama.cpp claim is active.
   The root `main` worktree's `docs/align-requests.md` edit remains untouched.
2. Finish publication of the `--prepare-history` capability, then implement an Align-owned
   OpenAI-compatible local HTTP endpoint on the passing 0.8B
   runtime, beginning with a real `POST /v1/chat/completions` request. The existing OpenAI provider
   is a client. `docs/specs/roadmap.md` owns this new delivery order and
   `docs/specs/openai-local-serving.md` now owns the initial endpoint contract. Extend the
   qualified prompt renderer to message history before multi-turn serving acceptance. Pinned
   `std.http` already sends SSE with one-write `send_event` and outbound providers already
   consume SSE; `pkg.web` also has fast stream routes but no handler application-state argument.
   The missing piece is a native per-token yield (`provider_runtime.stream` currently refuses).
3. Select a locally viable Qwen3.5 dense 2B or 4B checkpoint and repeat parity, profiling, and
   measured optimization. Treat 9B as conditional on local memory and speed; defer 27B and 35B
   MoE. Existing small OLMoE checks cover generic MoE only. No speed claim is active.

Latest local verification: `gmake build` PASS with the documented Homebrew `LIBRARY_PATH`;
`python3 scripts/qwen35_frontdoor_smoke.py` PASS; `scripts/run-model-ir-smoke` PASS;
`scripts/run-alignpack-smoke` PASS (20,542 assertions; two existing injection N/A cases);
real-model `--model-ir`/`--pack`/`--pack-verify` PASS after review repair;
`python3 scripts/check-python-boundary` PASS. The root `main` worktree's prior
`docs/align-requests.md` modification is intentional and
untouched; this branch is in a separate worktree.

Tokenizer merged verification: `gmake fmt` and `gmake build` PASS (Homebrew
`LIBRARY_PATH` for the latter); `scripts/run-tokenizer-smoke` PASS; real 0.8B
`scripts/run-qwen35-tokenizer-smoke` PASS on eight paired cases against pinned
llama.cpp `bb4caa7`; `python3 scripts/check-python-boundary` PASS. One independent
Codex review found the reverse architecture/profile mismatch; the accepted finding
was repaired with two synthetic refusals and the affected owners passed again.

Native text investigation: the pinned `qwen35.cpp` and `delta-net-base.cpp` graph confirms six
full-attention and 18 recurrent layers with a shared post-attention norm/FFN residual order.
The current shim has checked IMROPE, SSM convolution, and final-state DeltaNet wrappers;
the existing session graph supports only Qwen2 or OLMoE and has no recurrent state ownership.
`docs/specs/qwen35-text.md` records the exact 0.8B state geometry and next acceptance oracle.
The local native admission checkpoint in `src/runtime_qwen35_geometry.align` reads the Model IR
geometry and the four sections supplied from the same GGUF snapshot, checks bounded shapes, and
derives six attention and 18 recurrent layers with 18,432 convolution and 262,144 DeltaNet state
elements per recurrent layer. The same owner now writes the pinned four-plane text position
layout and checks its values and bounds. The real C shim has a checked IMROPE call; the hosted
stub explicitly refuses numeric M-RoPE. Its real-file geometry smoke passes. No native graph or provider result is
claimed yet; this local checkpoint is not a publication candidate on its own.
Local checkpoint verification: `gmake fmt`, `./scripts/check-format`, and
`./scripts/alignc run src/runtime_qwen35_geometry_smoke.align
/Users/hiro/models/qwen35-0.8b-model-ir.json
/Users/hiro/models/Qwen3.5-0.8B-Q4_0.gguf` PASS; `git diff --check` PASS. The next native
step is the hybrid role/load plan, graph construction, and explicit state commit. The new SSM
and DeltaNet wrappers check pinned ggml operand shapes and types before its assert-based graph
constructors; the hosted stub refuses their numeric execution.
`runtime_qwen35_state` now maps the six attention KV pairs and both copies of each recurrent
layer's convolution and DeltaNet state to 84 unique resident tensor indices. Its active parity
changes only after a successful step; the real 0.8B geometry smoke covers all indices, boundary
layers, an unsuccessful step, a successful flip, and malformed interval refusal. The next owner
must allocate those shapes, load the role-specific weights, construct both graph paths, and
compare prefill plus multistep decode against pinned llama.cpp before profiling. The focused
geometry smoke, both C shim syntax checks, `ggml_ffi` check, format check, and the ggml-free
`run-ggml-spike-smoke` pass with the documented Homebrew library path. No native Qwen3.5
numeric result or speed claim is established by this checkpoint.
The real 0.8B alignpack has 321 member records but 320 unique source tensors: its final output
member aliases the embedding's source range. `runtime_qwen35_roles` now maps each layer's 11 or
14 members to consecutive device slots, shares the embedding slot for output, and checks the
alias source offset/type/shape/size. Its real-pack smoke passes every role/block and slot,
including an injected alias mismatch. The validated load plan and resident allocation now
follow this map; graph construction remains next.
The next local checkpoint validates every real-pack member shape, builds a 320-weight and
84-resident-tensor Metal allocation plan, and uploads all unique 0.8B weights with the pinned
ggml bundle. `runtime_qwen35_load_smoke` passes on the real Model IR, GGUF, pack, and pinned
Metal bundle: 320 weights uploaded, 84 resident tensors defined, and the tied output omitted
from the upload byte count. The stub GPU cannot define quantized tensors, so this owner uses
the real backend. Native Qwen3.5 graph execution, oracle parity, and any speed claim remain
open. `runtime_qwen35_state_io` also binds the active resident tensor and exposes a staged
same-shape copy into the inactive tensor via the existing KV slot ABI; the real Metal load owner
checks active binding shapes across a parity flip. The graph must expand those copy nodes and
test success-only publication. The one-token recurrent-layer builder now constructs layer 0
from the real 0.8B weights and executes on pinned Metal with a nonzero synthetic hidden input;
its output is nonzero and the convolution/DeltaNet copy nodes are included. This is a layer
operation smoke, not a llama.cpp numeric comparison or full-model result.
The same real Metal smoke now executes the layer-0 post-attention residual, normalization,
SwiGLU FFN, and second residual with real weights. The synthetic block output is nonzero.
The same owner now builds and executes full-attention layer 3 with interleaved Q/gate,
four-plane M-RoPE, resident KV write, masked Flash Attention and the common FFN tail. Its
synthetic output is nonzero. The Flash policy is selected before memory admission and both
KV tensors use sequence-major storage.
The unpublished full-model graph now joins all 24 layers and the tied output head. A same-pin
Metal `llama-eval-callback` build identified a duplicated Q scaling in the fused Gated DeltaNet;
removing it aligned the first recurrent layer and token-0 edge logits. A two-step real Metal
smoke now matches displayed callback edge logits for token IDs 0 and 23066 (`! hello`) within
0.03 per selected F32 value, with state parity flipped only after the first successful compute.
The optional two output paths dump complete logits, and the independent same-pin Metal oracle
`scripts/qwen35_llama_logits_oracle.cpp` compares all 248,320 values per step. Maximum absolute
differences are 0.0004912 and 0.0002388, with matching argmax token IDs 198 and 11.
The next local checkpoint adds a third internal graph kind for the alternate recurrent parity,
fixed 256-token decode views with zero-initialized attention planes, and indexed writes for both
decode graphs. A four-token real Metal smoke `[0, 23066, 0, 0]` passes same-pin full-vector
comparison (maximum absolute differences 0.0004912, 0.0002388, 0.0002618, 0.0005222); the
fourth token reuses a prepared decode graph. The real and stub shim now hold three isolated
graph contexts. This remains unpublished local implementation work.
`gmake fmt`, `./scripts/check-format`, `git diff --check`, real/stub shim C syntax,
`scripts/run-gpu-generation-smoke`, `scripts/run-gpu-session-reuse-smoke`, and
`scripts/run-gpu-device-smoke` with the required Homebrew `LIBRARY_PATH` pass. The post-format
real Metal four-step owner and same-pin full-vector oracle also pass. The earlier
`run-gpu-device-smoke` invocation without `LIBRARY_PATH` stopped at linker `-lcrypto`;
the corrected invocation passed.
An unpublished optimization candidate now uses pinned `ggml_swiglu_split` for the 24 FFNs
and the existing cached-F16 policy for the six attention K/V pairs. The fused FFN made
four-step full-vector Metal logits bit-identical to same-pin llama.cpp; retained F16 preserves
that parity, including the full vector at step 127 in the fixed-token sequence. The focused
`--decode-bench` reads full logits after each of 124 post-warm
token-0 steps. Five alternating F32/F16/llama.cpp triples on Apple M1 measured median
2.375/2.307/2.188 seconds: F16 beat F32 in all five, llama.cpp in none. The 15% material
optimization floor was not met, and this excludes prompt, sampler, and request startup.
Deleting attention Q/K/V `CONT` nodes did not win consistently and was reverted. Next:
identify the remaining Metal decode cost, then complete longer-prompt/provider parity and
the paired full-request comparison. No faster-than-llama claim exists.
The next local checkpoint adds a 128-token batched prefill graph using checked 3-D views and
4-D reshape, with a following decode graph on the staged state. The Apple M1 pinned Metal owner
and same-pin llama.cpp oracle match all 248,320 logits exactly at the last prefill token and
following token 128. Removing an unnecessary recurrent QKV materialization reduced the warmed
prefill diagnostic from about 122 ms to about 109 ms; removing the attention query
materialization brought its five-pair median to 108.08 ms, versus 104.55 ms for llama.cpp.
It remains slower in all five pairs and misses the 15% material floor. The full provider path,
sampler, contemporary reference, and request latency remain open. Next: check batch shape and
failure cases, finish the native provider session, then profile and compare complete requests.
The branch remains an unpublished implementation checkpoint.
The local one-shot Qwen3.5 Metal provider now produces text and exact token counts.
`scripts/run-qwen35-generation-smoke` passes three generated tokens for 31-, 200-,
and 330-token prompts against a same-pin Metal llama.cpp greedy oracle. The latter
two cover multiple prefill chunks and the 256-to-512 attention-width transition.
`provider_runtime` refuses Qwen3.5 numeric trace mode until that stream is supported.
Next: refactor the native path into a retained `--runtime-session` with fresh state
per request; test two requests, early EOG, malformed input and failure recovery;
then measure paired complete requests and profile any remaining speed gap.
Checkpoint verification: `./scripts/alignc check src/provider_runtime.align`,
`gmake fmt`, `./scripts/check-format`, the real-shim `./scripts/alignc build
src/main.align`, `python3 scripts/check-python-boundary`, and
`scripts/run-qwen35-generation-smoke` with the pinned Metal oracle all pass;
`git diff --check` passes. The provider remains Metal-only and has no
complete-request performance claim.
The callback's CPU and Metal builds produce materially different logits, so the Metal oracle is
the valid comparison for this Metal owner. Remaining: longer-prompt output parity,
session/provider routing, then paired speed
measurements against same-pin and contemporary llama.cpp. No faster-than-llama claim exists.
The IMROPE input/ABI checkpoint passed the real-file geometry smoke, `./scripts/alignc check
src/main.align` (3,134 functions), `gmake build` with the documented Homebrew
`LIBRARY_PATH`, `./scripts/check-format`, `git diff --check`, C syntax
checks of the real shim against pinned ggml headers and of the standalone stub, and the
ggml-free shim build. Numeric M-RoPE
has not passed an isolated pinned reference comparison; two complete model steps have passed
the full-vector reference comparison.

Reference bottleneck diagnosis: pinned llama.cpp `bb4caa7` on Apple M1, Qwen3.5-0.8B Q4_0,
three repetitions: CPU 464.98 prompt / 55.32 generation tok/s; Metal 1180.77 / 61.85 with
Flash Attention off and 1195.65 / 63.87 with it. A separate 10-second CPU sample showed
quantized GEMV as the dominant active stack, while the Metal trace did not provide shader rows.
`docs/specs/qwen35-text.md` records commands, scope and the future paired floor;
`docs/backend-parity.md` records backend coverage. The native path remains prerequisite to any
align-llm bottleneck fix or optimization claim.

Prompt verification at final head `ae68abc6`: `gmake fmt`, managed build with the documented
Homebrew library path, `scripts/run-tokenizer-smoke`, `scripts/run-prompt-smoke`, the real-model
`scripts/run-qwen35-tokenizer-smoke` (eight token and five prompt cases), Python boundary check,
and exact-head `scripts/pre-pr --owner-test qwen35-prompt` all passed. All three hosted checks
passed and #296 merged as `53d5a183`. The pinned llama.cpp Jinja renderer was called directly:
it removes vertical tab and retains U+3000; the review's Unicode-trimming assertion was rejected
and the actual vertical-tab mismatch repaired. No Qwen3.5 native inference or align-llm speed
result is claimed by #296.

## Codex binary audit checkpoint (2026-09-23)

Branch: `agent/adopt-align-5c7af9e5`, based on merged PR #292 (`98bbfff1`).
Both repositories were pulled. The managed pin is now Align
`5c7af9e54108fbe3a7b3d698c96a6dbc2da3e9c3`, including #1165/#1166/#1168.
The requested independent macOS audit is complete for its recorded scope:

- Full-image short calls fall 544 -> 283; all 118 `handle_absent` calls vanish.
  Remaining observed classes include explicit Plan 74 exclusions; the broader
  Request 95 target of fewer than 100 is not met.
- `kv_plane.all_zero` now vectorizes. Seven alternating pairs give median
  3.1014 -> 38.6365 GB/s, exceeding the existing 25 GB/s scan floor. Both
  kernels pass 33,153 guard-page cases; this is a kernel-only measurement.
- Request 108 still has a reproduced compiler gap: local allocation disables
  cached headers and its aggregate-load fallback loses the nonnegative length
  fact. The real sampler has the same missing range fact. No source workaround
  is adopted. An upstream comment draft is prepared but not posted.
- The exact old image has 50 syntactic clamps under the reproducible census,
  not the previously recorded 13; the new image has 45. This supersedes the
  earlier count for this comparison. Greedy/sampler binaries are unchanged
  across these pins; their timings establish no improvement.

Evidence and reproducible fixtures:
`eval/benchmarks/codex-binary-audit-2026-09-23/README.md` and `results.json`.
Durable verification: managed-toolchain verification PASS; `gmake check`
155 units PASS; `gmake build` PASS; tokenizer smoke PASS; alignpack smoke
20,541 assertions PASS (existing window-unavailable injection N/A); both
benchmark owners PASS and all 42 paired measurement invocations PASS.

Next actions in priority order:
1. Coordinate the Request 108 uncached-header correction with Align using the
   prepared reproducer; repeat its IR owners after a merged correction.
2. Disposition Request 95's aggregate target against the explicit exclusions,
   and complete Request 112's wider remark-census qualification when resuming
   full request closure. Both remain `ALIGN_MERGED`.
3. Keep Linux real-ggml diagnosis with its separate checkpoint below. The audit
   supplies no Linux, Metal, CUDA or end-to-end inference performance claim.

The older macOS checkpoint below is historical and superseded by this section;
its outstanding Linux owners remain active.

## Linux real-ggml qualification checkpoint

Branch: `agent/linux-real-ggml-qualifications`, based on `main` `6149e993`.
Active capability: qualify the pending Linux real-ggml decode owners at managed
Align `d9b0df32` on Linux x86_64 under WSL2. Both owners ran real models and
failed their C' single-shot prefill comparisons; neither is accepted as a pass.

Completed work:
- Materialized and verified the exact managed compiler, rebuilt `main`, and
  prepared the pinned R2C `llama-eval-callback` plus a same-flag `llama-debug`
  and shared ggml build. The arm and `llama-debug` load the same ggml-base
  object. The model hashes are in the Request 94/103 qualification notes;
  SHA-256 prefixes are `d0e25b99` for `llama-debug`, `d83375c0` for the patched
  callback, and `1a9ae09b` for the shared ggml-base object.
- `scripts/run-decode-step` ran four Qwen prompts at 16 steps. G, B and A'
  passed; C' differed at k=1, 8 and 16 in every prompt and the KV load path.
  Its resident/streamed timing remains diagnostic because the owner failed.
- `scripts/run-moe-decode-step` ran OLMoE at 16 steps. Prompts 1 and 2 passed;
  prompt 3 failed C' at k=16 (prefill argmax 15741, decode argmax 4149), before
  prompt 4. The patched and debug llama instruments agreed before the arm ran.
- The MoE runner used a hard-coded `/usr/bin/time` absent on this host and
  misparsed Linux `ldd`'s soname as a resolved object. This branch changes the
  two timing sites to Bash `time -p` and fixes the resolved-path extraction;
  the second full owner run used the timing repair. A focused one-prompt,
  16-step rerun passes with the identity parser repair and the MRD owner.

Next actions in priority order:
1. Diagnose the dense C' disagreement at k=1 with one bounded prefill/decode
   comparison, then classify it as ggml numeric behavior or a client defect.
2. Diagnose OLMoE prompt 3 k=16's argmax swap, including the two near-tied
   logits and the C' tolerance rule. Repeat only affected owners after a fix
   or an explicitly revised acceptance rule.
3. Run exact-head publication preflight and publish the reviewed Linux
   measurement disposition when the candidate is stable.

Latest durable verification:
- `scripts/align-toolchain verify`: PASS at `d9b0df32`.
- `make build`: PASS, `main` SHA-256
  `2dab916e8871f1d78a1d540d7a4529a65380331de55768c5954d73c9b9fe0f43`.
- `scripts/run-decode-step`: FAIL only C' at all 12 named checkpoints.
- `scripts/run-moe-decode-step`: FAIL C' at prompt 3 k=16; prompts 1 and 2 PASS.
- `ALIGN_LLM_MOE_DECODE_STEP_PROMPTS=1 scripts/run-moe-decode-step`: PASS at
  16 steps with the timing and library-identity repairs, including MRD.
- `bash -n scripts/run-moe-decode-step` and `git diff --check`: PASS.

Blockers and decisions:
- Both real-ggml owners are measured but not verified. Keep Requests 94 and 103
  at `ALIGN_MERGED`; Requests 106 and 109 consume the same failed owners.
- No cross-host speedup is claimed from these runs. Do not turn the failed
  correctness run's resident timing into an accepted performance result.

## Concurrent macOS checkpoint

Branch: `agent/record-align-residual-corrections`, based on merged PR #289 at
`d2dab0b6`. Active capability: adopt the merged Align residual corrections and
repeat the remaining macOS-only consumer qualifications without taking the
separately owned Linux/real-ggml measurements.

Completed work:
- PR #288 merged the managed `d9b0df32` pin and request reconciliation; all
  three hosted checks passed.
- `scripts/run-tokenizer-smoke` passes its full matrix and
  `scripts/run-alignpack-smoke` passes 20,541 assertions at the adopted pin.
- The current release image reduces the old length-clamp census from 351 to
  13, but the named `kv_plane$all_zero` witness still loads its borrowed-slice
  length without `!range`, calls `llvm.smax.i64`, and remains a 12-instruction
  scalar loop with no vector body.
- Replacing only `view.u8(at)` with direct `view[at]` leaves the same residual,
  so the experiment was reverted. Exact evidence is posted to reopened Align
  #1080 (comment `5782592151`) and #1084 (comment `5782592441`).
- Align PRs #1165, #1166 and #1168 merged the provider corrections for #1066,
  #1080 and #1084. They are recorded in `docs/align-requests.md` but are not yet
  adopted by the managed align-llm toolchain.

Next actions in priority order:
1. Repin the managed toolchain to a single Align revision containing PRs #1165,
   #1166 and #1168, then materialize and verify it.
2. Repeat the #1066 same-source call-site census and the #1080/#1084 function-
   scoped IR, release-image and throughput checks.
3. Leave Linux/real-ggml owners, including #1065/#1075 and the decode owners of
   Requests 106/109, to the separately assigned capable environment.

Latest durable verification:
- `scripts/run-tokenizer-smoke`: PASS.
- `scripts/run-alignpack-smoke`: PASS, 20,541 assertions.
- `alignc emit-llvm src/kv_plane.align --stage optimized --profile release
  --no-rt-lto --export all_zero`: residual reproduced at exact `d9b0df32`.

Blockers and decisions:
- Requests 95, 108 and 112 remain `ALIGN_MERGED`; their provider corrections
  are available, but named client acceptance still requires a managed repin and
  remeasurement. Do not adopt a source-style workaround.
- Whole-program verbose remark counts use a different source/module population
  from the original eight-module baseline and are not a valid performance
  comparison. No performance claim is made.

## Completed capability: Align inline/ABI follow-up adoption

Branch: `agent/align-inline-abi-followup`, based on `origin/main` `29e5cda1`.
Active capability: adopt Align PR #1163 through managed pin
`d9b0df32a831c165b9b070242e168b3f10c721c7`, reconcile the provider issue
dispositions, and complete the remaining macOS consumer measurements. Linux and
real-ggml qualification are explicitly assigned to another environment and are
not part of this session.

Completed work:
- PR #286 is merged at `29e5cda1`; its three required jobs pass. The old
  request-batch/CI repair below is a completed checkpoint.
- Materialized and verified the exact `d9b0df32` compiler/runtime with explicit
  Homebrew LLVM 22/OpenSSL/zstd paths. `gmake check` passes all 155 whole/per-unit
  units, and `scripts/run-runtime-provider-smoke` passes the self-test, shim
  matrix, sampler vectors, and 61 CLI assertions.
- Rebuilt the same current source under old `df14e8bd` and new `d9b0df32`
  release/no-ThinLTO compilers. The decoded <=8-instruction Align-to-Align call
  census changes only 545 -> 544. `runtime_attention$fused` falls 11 -> 0, but
  `ggml_ffi$handle_absent` remains 118 calls. Exact new image SHA-256 is
  `87da7e83c997d3d25a54878e2c1ed39fe258967214fb11ffe7b3156aed5338ec`.
- Reduced the residual to a two-unit provider case: the real
  block/unsafe/explicit-return `handle_absent` shape retains a release call,
  while the provider test's expression-bodied spelling removes it. Plan 74
  admits both; align-llm does not adopt the source-style workaround. Evidence is
  posted to Align #1066 in comment `5781323584`.
- Completed Request 103's corrected same-source/same-target comparison using
  align-llm `1e9ea492` and Align `0aab8796` -> `1a446e5e`. Both
  `mm_row_issued_at` sites change three boundary masks to zero; required argument
  register moves remain, so instruction count is unchanged. Exact images are
  `15cfaf48...` and `1ed37284...`. Evidence is posted to Align #1075 in comment
  `5782094218`; no residual scalar-ABI defect is established.
- Request 102 is reconciled with Plan 70's source-free cold-path boundary and
  closed Align #1074. Request 105's named fresh-whole-local criterion is met;
  the remaining storage classes are outside that capability and Align #1077 is
  closed.
- Current-pin benchmark owners pass but vary: greedy 139/132 us per call and
  sampler 579/361 us per call. Do not make a performance claim from these runs.

Next actions in priority order:
1. Await the provider correction for #1066, then repeat its same-source census.
2. Continue with the next eligible roadmap capability that does not depend on
   #1066 or the separately owned Linux/real-ggml qualifications.
   The real-ggml owners for #1065/#1075 remain with the separate Linux-capable
   environment and are not a local blocker.

Latest durable verification:
- `scripts/align-toolchain ensure compiler` and `scripts/align-toolchain verify`:
  PASS at exact `d9b0df32`.
- `gmake check`: PASS, 155 whole/per-unit units.
- `scripts/run-runtime-provider-smoke`: PASS, including 61 CLI assertions.
- `scripts/bench-runtime-greedy`: PASS, 139 and 132 us/call;
  `scripts/bench-runtime-sampler`: PASS, 579 and 361 us/call.
- `git diff --check`: PASS after the final documentation checkpoint.

Blockers, constraints, decisions:
- Request 95 remains `ALIGN_MERGED`: policy v2 fixes `fused` but misses the
  contract-admitted real `handle_absent` block shape, and the aggregate target
  remains 544 versus `<100`.
- Request 103's macOS static qualification is complete. Do not rerun or claim
  the Linux/real-ggml owner in this environment.
- Local release builds require `LLVM_CONFIG=/opt/homebrew/opt/llvm@22/bin/llvm-config`,
  `LLVM_SYS_221_PREFIX=/opt/homebrew/opt/llvm@22`, and Homebrew LLVM/OpenSSL/zstd
  library paths. Cold full-product release builds took roughly 20 minutes.

## Completed capability: merged Align request batch and CI repair

Branch: `agent/align-request-batch-adoption`, rebased on `origin/main` `1e9ea492`.
Active capability: adopt the merged Align Requests 92–119 consumer surfaces through managed pin
`df14e8bdee748e1f4e2d684a24b36c7b8984b270`. This is an executable consumer capability. Align
#1157–#1159 and PRs #1160–#1162 are merged. Requests 117 and 118 are consumer-verified, but Request
119 is also consumer-verified after rebuilding the stale `main` artifact at the final pin. All four
named consumer smokes pass. The issue audit, stable-candidate review, rebase, request-register
reconciliation, and PR publication are complete. PR #286 is open. Its pinned hosted job reached
`prompt_verifier_smoke` but was cancelled first by the 30-minute ceiling and again by the 45-minute
ceiling after 42m36s in supported checks. The active repair removes that 3,424-line focused owner
from routine CI, switches its semantic execution to Align's `dev` generated-program profile, and
sets a 20-minute hosted hard ceiling with a roughly 15-minute operating target. Issue #287 owns any
remaining test or compiler cost diagnosis; another timeout increase is not accepted.

Completed work:
- Materialized and verified the managed compiler/runtime at exact revision `df14e8bd` using the
  explicit Homebrew LLVM 22/OpenSSL/zstd paths required on this host.
- Adopted scalar `exp`, checked `bytes.view_le<f32>()`, structural mask selection, string literal
  patterns, `buffer.append_filled`, and fixed-array table storage.
- Replaced the Qwen `[i64; 38]` and OLMoE `[i64; 72]` node-table builders with inline arrays, then
  removed the temporary `NodeView` carriers and passed the fixed-array table records directly.
- Adopted Request 117's `pub NULL: raw := raw.null()` surface. The six legacy modules contain zero
  `ggml_ffi.null_handle()` calls.
- `gmake check`: PASS, 155 units in whole and per-unit compilation.
- `gmake fmt`, `scripts/check-format`, and `git diff --check`: PASS.
- Same-pin local benchmark control versus the adopted source on this Apple M1:
  greedy 468 -> 104 us/call over about 152k logits (77.8% reduction); sampler 435 -> 480 us/call
  (10.3% regression). These are one-host consumer measurements, not a cross-backend claim.
- Request 93 is `ALIGN_LLM_VERIFIED`: both originally named benchmarks pass and the corrected
  contract owns checked zero-copy typed views rather than a latency ceiling.
- Requests 96 and 114 are `ALIGN_LLM_VERIFIED`: `explain-opt` completes for all seven formerly
  failing modules, and the two main-less unit owners report their own public inspection roots.
- Current release-image static counts are 325 `str_eq`, 143 `buffer_put`, and 888
  `array_builder_push` calls; `starts_with` has zero calls and `ends_with` has six. The optimized
  `build_eog_set` body has zero `str_eq` calls and ten switches. The formerly blocked tokenizer,
  alignpack and runtime-provider owners now pass at the final rebuilt artifact.
- `scripts/run-decode-step` and `scripts/run-moe-decode-step`: N/A because
  `ALIGN_LLM_GGML_INCLUDE` is unset; the owning modules pass their direct per-unit checks.
- `scripts/run-layer-forward-smoke`: PASS with the checked-in 1,426 `sha256` and 626 `bit_sum`
  goldens.
- `scripts/run-gpu-session-reuse-smoke`: PASS at `df14e8bd`, including both normal phases and the
  forced-failure cases.
- `scripts/run-tokenizer-smoke`: PASS after rebuilding `main` at the final pin.
- `scripts/run-alignpack-smoke`: PASS, 20,541 assertions.
- `scripts/run-runtime-provider-smoke`: PASS, including self-test, shim matrix and 61 CLI assertions.
- Stable-candidate review found that OLMoE's 68-row inline table was four rows too short for the
  accepted 32-expert prefill boundary. It is now 72 rows, and `runtime_generation_smoke` permanently
  constructs and reads the last row of that boundary. The repaired runtime-provider owner passes.
- Publication preflight found that `run-model-ir-smoke`'s role mirror still parsed the historical
  `role_id` if-chain after the consumer adopted a string `match`. The extractor now accepts both
  shipped forms; the focused owner passes all qwen, gpt-oss, OLMoE, and R0 fixtures.
- PR #286's hosted job was cancelled first at 30m24s after 28m17s in supported checks and again at
  45m16s after 42m36s in supported checks, while running `prompt_verifier_smoke`. A cached rerun
  completed the x86_64 and aarch64 native fresh-image jobs in 13m40s and 14m09s. The retained hosted
  logs contain no failed assertion. The fixture has grown from Request 19's 1,573-line admission
  case to 3,424 lines and is not a valid routine-lane member at that cost. It remains a focused
  verifier-boundary owner using Align's `dev` generated-program profile; routine CI keeps the
  smaller scorer, prefix, state, and gate owners. The hosted hard ceiling is 20 minutes and the
  operating target remains roughly 15 minutes.
- The first 20-minute-capped cold rerun then spent more than 17 minutes compiling `src/main.align`
  at the default release/O2 profile and timed out before any assertion. Hosted functional `build`
  and `run` calls now use `scripts/alignc-hosted-test`, which adds `--profile dev` only when the
  caller supplied no profile. This matches Align's native test default; explicit profile owners and
  ordinary local `make build` remain unchanged.
- Audit of Align's build-performance path found that the compiler has default-on content-addressed
  frontend/codegen reuse and pipelined codegen, but align-llm's hosted workflow discarded its
  writable unit cache with every fresh runner and its exact compiler bundle contains no adjacent
  prebuilt cache. The repair persists an explicit runner-temporary `ALIGNC_CACHE` through an Actions
  cache keyed by OS, architecture, and pin; Align's internal source/profile keys still own misses,
  and GitHub branch scope keeps pull-request entries out of trusted `main` state.
- The attempted canonical-baseline refresh exposed a pre-existing cutover contradiction: normal
  `main --eval coding-v1` intentionally refuses the retired corpus, while the old checker still
  required every later Makefile and compiler-pin change to regenerate it. The repair keeps the
  canonical measurement immutable, binds its full artifact manifest and Align revision to its
  recorded source commit, and continues to reject any later change to the seven external replay
  inputs. `verify-baseline.py` and `check-baseline-chain` both pass at the current pin and Makefile.
- Reduced two newly discovered Align gaps and registered them as Requests 118 and 119.
  The previously local Request 117 is filed as Align #1159. Request 118 is filed as Align #1158.
  Request 119 reuses the independently reduced Align #1157;
  the tokenizer, alignpack, runtime-provider, and GPU-session matrix is attached in comment
  `5759259675`. Request 94's consumer checkpoint is attached to Align #1065 in comment
  `5759271198`.

Next actions in priority order:
1. Await provider follow-up on the five remaining open Align issues. #1066 fails with 545 small
   cross-unit call sites against `<100`; #1074 fails with the 37 Align `$fail` sites at 53.4% mean
   position and a 1,820-byte function growth; #1075 fails with 905 boolean masks against `<100`;
   #1077 fails with a 2,080-byte `decode_pass` local frame allocation (2,176-byte total stack-pointer
   movement including callee saves) and 787 remaining whole-program result scratch allocas. #1065's
   static/allocation and GPU owners pass, but its final real-ggml decode owner needs
   a host with the llama instruments. Exact residual comments are on each issue.
2. Commit the bounded topology and frozen-baseline repair, complete one fresh review, push PR #286,
   then require the hosted job to finish within the 20-minute hard ceiling and inspect its measured
   duration before merge.

Latest durable verification:
- `gmake check`: PASS, 155 units, managed Align `df14e8bd`.
- `gmake fmt`: PASS, no remaining format delta.
- `scripts/check-format`: PASS.
- `scripts/align-toolchain ensure compiler` and `scripts/align-toolchain verify`: PASS at the exact
  `df14e8bd` pin.
- `scripts/run-layer-forward-smoke` and `scripts/run-gpu-session-reuse-smoke`: PASS.
- `scripts/run-tokenizer-smoke`: PASS; `scripts/run-alignpack-smoke`: PASS (20,541 assertions);
  `scripts/run-runtime-provider-smoke`: PASS (61 CLI assertions).
- `scripts/run-model-ir-smoke`: PASS after the publication repair (49 qwen, 31 gpt-oss, 29 OLMoE,
  and 62 R0 fixtures). The remaining hosted tail owners (`expert-trace`, `residency-sim`,
  `alignpack`, `ggml-spike`, `layer-forward`, `tokenizer`, and `prompt`) also PASS.
- `python3 eval/runners/verify-baseline.py` and `python3 scripts/check-baseline-chain`: PASS with the
  retired measurement frozen at its recorded source identity.
- Repair verification after the stable review: `check-per-unit src/runtime_generation_smoke.align`,
  `scripts/run-runtime-provider-smoke`, and `gmake check` all PASS. The new regression exercises
  the maximum 72-row OLMoE prefill table and reads row 71.
- Managed compiler SHA-256 is `ea2f3ecfb98a7945c823b96381d8fcae6c49d72f9f22612997aa66ee085c90b4`;
  rebuilt `main` SHA-256 is `5b44026c312f29d012428a883ec20152e1a0acb4cc0e15e9c9b8897e0a1e806b`.
- `scripts/run-decode-step` and `scripts/run-moe-decode-step`: explicit N/A because
  `ALIGN_LLM_GGML_INCLUDE` is unset; the owning modules pass direct per-unit checks.
- `scripts/bench-runtime-greedy`: PASS, 104 us/call after adoption; same-pin unmodified control 468.
- `scripts/bench-runtime-sampler`: PASS, 480 us/call after adoption; same-pin unmodified control 435.
- Direct per-unit checks for `layer_forward`, `model_forward`, `decode_step`, `moe_model_forward`,
  `moe_decode_step`, and the runtime greedy benchmark graph: PASS.
- Optimized IR for `mf_decode_layer_node_table` and OLMoE `mm_table` contains zero builder or heap
  calls; Request 94's GPU-session owner passes at `df14e8bd`.
- Request 115 is `ALIGN_LLM_VERIFIED`: explicit target/SDK 27.0 object metadata is exact, and the
  cached 155-unit release link emits zero newer-macOS warnings.
- Request 98's `--thin-lto` build completes across 155 frontend units and 3,586 backend functions;
  its runtime-provider owner now executes successfully.
- Fresh comprehensive `codex review --uncommitted` of the stable candidate against branch head and
  original merge base `50e89367` completed with two P2 findings: the 68-row OLMoE table did not cover the
  accepted 72-row prefill maximum, and Request 98 retained stale SIGTRAP status despite final-pin
  success. Both are accepted and repaired: storage and a permanent boundary regression now cover
  all 72 rows, and Request 98 is `ALIGN_LLM_VERIFIED`. These narrow repairs do not change the
  approach; their owner checks pass. The later rebase onto `1e9ea492` brought only the request-note
  publication checkpoint into the base; its provider metadata was reconciled without changing the
  reviewed executable surfaces.
- The governance-expanding review of the 45-minute CI repair found one P2: `HANDOFF.md` still
  named already-completed preflight and publication instead of the active CI rerun. This checkpoint
  is the accepted repair; workflow, assertions, and specifications were otherwise internally
  consistent.

Blockers, constraints, decisions:
- Request 119 is `ALIGN_LLM_VERIFIED` and non-blocking. The apparent residual GGUF traps came from
  a stale linked `main`, not a remaining compiler defect. Pin adoption must rebuild consumer
  executables before smoke execution; changing `.align-revision` alone does not invalidate them.
- Requests 117 and 118 are also `ALIGN_LLM_VERIFIED`. Their shipped surfaces and exact local evidence are
  recorded in `docs/align-requests.md`.
- Request 113 is `CLOSED`: a retained-session real Qwen2.5-Coder-7B profile over a deterministic
  56,320-byte input repeated 120 times produced 1,428,720 token ids and 725 leaf samples with zero
  `align_rt_str_eq` samples (0.0% versus the 4.5% baseline). Issue #1085 is closed in comment
  `5771980776`.
- The sampler benchmark regresses 10.3% on this host after replacing `pow(e, x)` with `exp(x)` and
  adopting the typed view. Do not claim a sampler performance improvement without a new measured
  intervention.
- Do not merge PR #286 until the amended exact-head publication preflight and required GitHub checks
  pass under the repaired ceiling.
- The local toolchain build requires explicit Homebrew LLVM 22, OpenSSL and zstd library paths.
  Reuse the successful environment recorded by the current shell history when materializing the
  next Align repair.

## Completed capability: latest merged Align adoption

Branch `agent/align-latest-adoption`, based on merged CUDA F16 PR #243
(`4fbc7d2d989fbf1f185db410b8a8e1d8a5234957`). PR #245 merged at `40f0bbf5a64b7d826c6871b93b7f0c43b6b21d1b`. Implementation,
consumer verification, exact-head preflight and required GitHub checks are complete.

The managed pin advances from `f502fe3da00ce0b39c4eeec40586b11688627fbd` to latest
merged Align `21d0cf27fb92166370b2705d5c366c2b269d17a3` (#1042). It includes bounded
byte storage / direct sequential chunks, writable/native byte-view fixes, codec/SSE
view invalidation, computed fixed-array field borrows and active-checkout runtime
build inputs. No client source or public API changes are required.

PASS: `scripts/align-toolchain ensure compiler`, `scripts/align-toolchain verify`,
`make check` (155 units), and `scripts/run-product-cutover-adoption-smoke`. The clean
manifested `46aea33` CUDA session build uses compiler SHA-256
`042e772d0cf3002e852a33dd3463c62386c17ce853c4c7e7d4883bac73db0524`.
`scripts/run-gpu-session-independent` passes all 7 Qwen / 9 OLMoE exact responses
and counts; result SHA-256
`e2fdd1619ad26bed2bd0dc862e4c25c333dc22458a7f60062b947b79a54a981f`.
Retained local receipts are under `gpu-cuda-enablement-20260914/latest-align-*`.

One fresh comprehensive review by `/root/latest_align_adoption_review` covers
`46aea33db0fb13fcf5e815d05c743d350d395ac8` against base/merge base `eaff971`:
CLEAN, no findings. Following changes integrate the same CUDA tree and refresh
this durable checkpoint; the pin and client source remain unchanged. Review/check
metadata and final integration evidence belong in the adoption pull request.

R86's optional-carrier negative still passes both check modes at this new pin.
It remains a recorded nonblocking compiler residual, not verified/closed by adoption.
The user now authorized publication of the previously preserved request note. Sibling
Align's unrelated deleted `.codex/config.toml` remains untouched. No new platform qualification,
aggregate audit or compiler-specific performance claim is selected by this pure pin.

The active worktree uses the adopted pin. Further implementation is outside this
request-note publication; native Mac performance remains explicitly pending.

## Completed CUDA F16 KV capability and concurrency retry

PR #243 is merged at `4fbc7d2`; CI budget prerequisite #244 merged at `810a456`.
Native F16/Flash, explicit prefill interval, session reuse, 16 independent requests
and both host-capacity owners PASS. On historical compiler `f502fe3d`, the complete
clean `48f249b` versus `4bf8011` campaign has 80 exact responses, no external
interference and 27.47% OLMoE long-cached median paired reduction, faster 5/5;
all seven guardrails pass. The accepted portable report is
`eval/benchmarks/cuda-kv-f16-2026-09-14.json`. This old-pin measurement is not a
performance result for the new Align compiler.

The renewed QKV lifetime experiment `16a7a1e` is NOT_MET: the final quiet incremental
campaign gives 1.32% primary reduction, faster 3/5, below the fixed 15% / 4-of-5 floor.
All 80 responses match and all seven guardrails pass. Qwen traces show 454 overlapping
kernel pairs; OLMoE shows none. The first campaign was invalidated by author CI-status
CPU activity and wholly rerun with those calls stopped. Complete negative evidence is
`eval/benchmarks/cuda-qkv-lifetime-2026-09-14.json`. An ancestry-only merge preserves
the experiment without shipping its graph defaults, tagging or allocator changes.
Future QKV work needs a new material hypothesis; no such follow-up is active.

## Completed capability: ALIGN-PRODUCT-CUTOVER

The user requested completion of normal-product Python removal on 2026-09-13.
Branch: `agent/align-product-cutover`. Candidate `edc9bb9` includes `origin/main`
`39b4cdc`; its following consolidated repair binds the authenticated source TREE,
manifest repository and copied validation source. Normal product execution is in Align,
including provider generation, edits, validation, repair, scoring, publication,
acceptance and rollback. There is no active implementation blocker or product Python debt.
Publication and merge are now explicitly requested; final preflight and hosted checks
are the remaining publication work.

The normal external-command evaluator refuses all eight historical implementations by
supported literal launch descriptor, reserved path and unchanged frozen digest, including
renamed copies, before any task/result. Owned task records survive dispatch. Explicit
external Python target tests remain allowed; developer tools and independent replay
oracles remain outside normal product execution. Sixteen historical command manifests
remain immutable replay inputs.

The exact managed Align pin is `f502fe3da00ce0b39c4eeec40586b11688627fbd`
(PRs #1033/#1034). Compiler/runtime materialization and managed verification pass.
R84/R85/R87/R88 are ALIGN_LLM_VERIFIED. R86 remains ALIGN_MERGED and nonblocking:
its optional move-after-use negative still compiles and produces an empty digest.
`eval/fixtures/product-cutover-option-after-move.align` and the request register retain
the witness. Product construction binds the digest before moving its measurement;
the consuming initializer audit found no unsafe product occurrence. Do not claim R86
fully verified or start another provider pin cycle solely for this residual.

## Durable verification

All commands below PASS. `$CUTOVER_BINARY` is the real-linked Linux ARM64 product;
model/library/shim operands identify the explicitly prepared native runtime assets.

- Managed materialization and `scripts/align-toolchain verify`; managed macOS and
  exact-source Linux product builds. `scripts/run-product-cutover-adoption-smoke`
  passes source/per-unit and runtime witnesses on macOS/Linux.
- `python3 scripts/run-align-product-cutover --functional --binary "$CUTOVER_BINARY"`:
  final repaired product. Eight paired rows, sixteen repair attempts, public refusals,
  actual HTTP workers, coding-v2 and independent result checks. Source TREE declaration,
  kind/path/digest, changed source bytes and mismatched repository cases refuse before
  an attempted row. Ordinary external-command error semantics remain intact.
- `python3 scripts/run-align-product-cutover --containment --binary "$CUTOVER_BINARY"
  --align-repo "$PINNED_ALIGN_SOURCE"`: task lifecycle/resource/cleanup owners and actual
  installed Linux Docker profile PASS on reviewed `edc9bb9`, with standard local socket,
  no ambient `DOCKER_HOST` and no Docker skip. Image attestation, lifecycle/self-test,
  trust mutations, runtime replacement, compiler boundary, worker build and profile
  execution pass. The repair changes input binding, not this containment boundary.
- `python3 scripts/run-align-product-cutover --no-python --binary "$CUTOVER_BINARY"
  --models "$CUTOVER_MODELS" --libraries "$CUTOVER_LIBRARIES" --shim "$CUTOVER_SHIM"`:
  final repaired product. Relocated normal/repair/provider evaluation, all eight renamed
  implementation refusals, Git/index/test-selection/patch/verification/failure memory,
  proposal/accept/rollback and real three-token inference. Python and repository scripts
  are absent from product namespaces; full descendant exec traces are inspected.
  Independent Python oracles run outside; a separate namespace verifies an explicit
  external Python target test.
- A1 renderer parity, score, score-prefix, verifier and state owners PASS. The changed
  verifier owner and state CLI pass again after the consolidated input-binding repair.
- `scripts/run-prompt-task-inputs-smoke` and
  `scripts/run-prompt-evaluation-inputs-smoke` PASS after the repair, with complete-list
  ownership and source TREE/repository refusal cases.
- `python3 scripts/run-prompt-gate-validator-smoke FAMILY`: validator, product-version,
  source-bundle and source-revalidation PASS; changed product-version owner passes
  again with missing/wrong-kind/wrong-path TREE refusals. Historical v1 bytes stay intact.
- `python3 scripts/check-python-boundary --strict`: 272 Python files, 83 embedded
  hosts, 157 product modules and zero frozen debts. `python3 scripts/test-python-boundary`:
  all 30 mutation cases PASS. Pure filename policies stay in `source_file_kind` without
  weakening the checker. Final index/selection/patch golden owners PASS.
- `scripts/run-runtime-provider-smoke`: sampler and 61 CLI assertions PASS. No new C ABI,
  GPU performance claim or complete `make ci` audit was required. `make fmt` and
  `git diff --check` PASS.

## Review and repair

One fresh independent high-effort comprehensive inspection reviewed the entire committed
cutover, including code, source/process boundaries, records, tests and governance.
Reviewed head: `edc9bb960c93a8e746a5e5b6ead1aadbd8e7920d`.
Base tip and merge base: `39b4cdc6ed864f39554b618335b4bd89f9346dcc`.
Reviewer: `/root/cutover_review`; verdict FINDINGS; inspection-only.
Complete findings and dispositions:

1. P1: an undeclared source tree could supply validation bytes outside the authenticated
   artifact set (`prompt_task_inputs`, `prompt_score`, source collection/runtime).
   Accepted: require the exact repository TREE for every v2 task in native admission,
   persisted verification and the independent gate; verify its bytes before dispatch.
2. P1: `source_dir` could differ from snapshotted `repo_path`
   (`prompt_evaluation_runtime:216–223`). Accepted: require exact equality during
   complete input admission and again when resolving the runtime source.

Both findings are addressed in the single repair following the reviewed candidate.
The repair delta was inspected for unrelated changes; regression owners cover all
accepted root-cause classes. It restores the settled contract without expanding the
capability or changing its approach, so no second comprehensive review is required.
The bounded retrospective found one reusable lesson: keep source declaration, snapshot
identity and copied execution input tied at admission. Existing owners now test that
invariant; no additional process gate or retrospective-only change was added.

## User-requested speed measurement (2026-09-13)

Completed the controlled old/new fixed-patch evaluator comparison after the user asked
whether cutover improved speed. See `docs/product-cutover-benchmark.md` and
`eval/benchmarks/product-cutover-2026-09-13.json`. Measured application heads are
`9855afe` and `2f25c3f`, using their respective exact Align pins. Nine alternating measured
pairs after two warmup pairs: complete CLI medians 2.145870293 s before and 0.720526833 s
after, a 66.42% reduction; all nine pairs favor native and all 22 invocations pass eight
rows. Native/legacy inputs are controlled semantic counterparts with the same fixed patch
and external tests. No model generation or repair attempt is measured. Historical OLMoE
84.062 s versus llama.cpp 14.174 s remains unchanged; do not turn this evaluator result
into an inference claim. Product source was unchanged during the measurement. The user designated the After arm
as baseline `product-cutover-fixed-patch-2026-09-13`; future candidates rerun this reference
on the same host under the documented protocol. The recorded sample JSON is immutable.

The measurement review found missing durable replay and dependency identities; these
were repaired in `c2e99e0`. Its final review found optimized-Python validation bypass,
unbound reference substitution, unchecked dependency equality and unbound native source.
The owner was re-scoped to frozen historical-pair replay: arbitrary reference/candidate
substitution is removed, both exact source commits and binary hashes are required,
optimized Python is rejected, and source/dependency maps must match before timing.
The immutable original sample JSON stays unchanged; the dependency supplement is a
later capture from retained assets, not a contemporaneous attestation.

Frozen replay passes all 22 invocations with eight rows. Negative owners pass optimized
mode, wrong native commit/binary, reference substitution, dependency mismatch and existing
evidence refusals. Replay qualification timings are not a replacement baseline or speed
claim. Strict boundary passes 272 Python files, 83 embedded hosts, 157 product modules and
zero debts. The portable scripts require retained or exact-byte rebuilt historical binaries;
future candidate automation is outside this narrow frozen owner. Final exact-head preflight
and hosted integration checks remain before merge.

## Next actions

No implementation work remains for the requested cutover. Complete the authorized
publication and merge: run exact-head `scripts/pre-pr --owner-test LABEL -- COMMAND ...` from a
clean named branch/worktree on the capable Linux host, attach the review envelope and
repair disposition, and require all selected checks before merge. The earlier `--plan`
run only identified fresh-image scope; it is not a preflight stamp. Preserve the unrelated
Antigravity working files. The user has now authorized the MoE GPU follow-on below.

## Active MoE GPU diagnosis (2026-09-13)

Branch `agent/moe-gpu-diagnosis`, starting at `ad94eb5`; isolated from the original cutover and
Antigravity working files. The user selected the recommended MoE direction. The active-entry
ledger in `docs/specs/gpu-runtime-performance.md` bounds an unchanged resident OLMoE Metal
session diagnosis and the selected O1 retained-half KV implementation. The unchanged manifested build,
four-request host-sampling run and shorter Metal System Trace all PASS; every response passes
the fixed 128-token/sequence quality check. See `docs/gpu-moe-diagnosis.md` for exact commands,
identities, sampling counts, artifact digests and limits. The first 60-second device trace remains
INCOMPLETE after finalization timeout; the separate 10-second trace saved successfully.

Main-thread non-input-wait samples are dominated by backend completion wait (94.82%); topology
hashing and input update are small. The subsequent counter-enabled trace attributes 46.03% of
owned shader sample duration to F32-to-F16 conversion (instrumented attribution, not wall-time
savings). O1 now retains F16 KV only in supported Metal OLMoE sessions, converting new rows.
Exact backend-aligned allocation preserves the allocator's exact-consumption invariant. Real
Metal `run-gpu-attention-policy-smoke` passes incremental rounding, overwrite, prefix, padding
and direct F16 Flash equality; the extended malformed-input and metadata-exhaustion batch PASS.
`scripts/run-gpu-session-reuse-smoke` and `make fmt` PASS. No new Align gap.

Clean implementation checkpoint: `d60e2b6`. Managed build and unchanged full Metal independent
session oracle PASS (Qwen2 7/7, OLMoE 9/9 exact outputs/counts). Allocation-count host-capacity
owner PASS for both models. Five alternating local pairs PASS all 40 quality checks and all
paired outputs/counts, with median request-wall reductions of 44.00%, 46.00%, 63.33% and 73.82%
against the clean manifested `ad94eb5` rebuild. Every case is faster in 5/5 pairs; all four
meet the predeclared 15% local floor. See the diagnostic report for artifact hashes and limits.
This is not a competitive llama.cpp or CUDA result, or a coding time-to-passing-patch claim.

## Active capped-read loader repair (2026-09-13)

The startup repair is isolated on `agent/capped-read-loader-repair`, based on accepted O1 docs
checkpoint `30f41c9`; the original C1 worktree remains untouched. `runtime_qwen_load.load_file` and
`runtime_olmoe_load.load_file` now use lexical capacity epochs at
`min(staging_bytes, remaining_member_or_piece_bytes)`, including consecutive equal-sized expert
pieces. Traversal cursors persist outside the epoch loop; its backedge drops the old chunk before
the next capacity allocation. Plan order, offsets, upload contents and existing fail-closed errors
remain unchanged. No ABI, pack format, mmap, async I/O or kernel change is present. The settled
scope, cost ceiling and owner matrix are recorded in
`docs/specs/gpu-runtime-performance.md` under “Startup capped-read loader repair”.

The Qwen and OLMoE loader smoke commands, including the test-only actual-`pread` observer, compile
and pass on the managed Align pin `f502fe3da00ce0b39c4eeec40586b11688627fbd`. They cover the
capacity bounds, payload offsets, repeated equal-sized expert reads, short/zero/error refusal and
the normal load path. The clean manifested candidate build and required independent session owner
also pass: all seven Qwen and nine OLMoE requests match exact output and token counts. The bounded
native startup campaign completed in 272.56 seconds with five alternating pairs per model. Qwen's
median paired startup reduction is 24.05% (candidate faster 5/5); OLMoE's is 61.58% (candidate
faster 5/5), meeting the declared OLMoE floor and Qwen guardrail. Receipts and per-arm logs are
retained outside Git under `capped-read-session-independent-20260913` and
`capped-read-startup-20260913`; the diagnosis records their clocks, identities and limits.

The comprehensive native review requested from `gpt-6-astra` at `xhigh` reviewed head
`44aa9af3c3aff16e3a4cf25feec670f1d54c077d` against base tip and merge base
`30f41c91a2b815f3d1983a182f016bc9bb9721ca` and returned `FINDINGS`. Its two P2 findings were
both in the test observer: the OLMoE fault threshold could stop in metadata, and the validators
did not enforce each payload member/piece's exact remaining-byte bound and offset. The committed
repair `c3a57d578b5f37a41a7cbb3577f9f11abc845480` derives the fixture payload boundary, binds
faults to payload traversal, validates exact per-read bounds/offsets while advancing by returned
counts, and covers complete expert-piece traversal. Astra's narrow repair assessment reviewed
that head against `44aa9af3c3aff16e3a4cf25feec670f1d54c077d` and returned `ADOPT` with no new
issues. The capped-read capability is COMPLETE and locally ADOPTED; publication and merge remain
pending the user's publication batch. The bounded lesson is to validate actual payload traversal
for fault cases so metadata failures cannot masquerade as loader coverage; the existing repair
covers it without a new gate.

### Historical O1 review (separate from this repair)

One fresh high-effort review by `/root/moe_review` covered the whole diff and final evidence
documentation. Reviewed head `d60e2b626ae69837d96df1866c728d4c5864ff40`; base tip and merge
base `ad94eb5a18e49695a0c2321da7c9c37bd7ddd2f7`; verdict FINDINGS. Complete findings:
P1 control source authentication was insufficient for a dirty build; accepted and repaired by
strict clean-control rebuild, source/compiler/library verification and a fresh five-pair PASS.
P2 stale specification claimed no new measurements; accepted and corrected to distinguish local
O1 evidence from historical/competitive claims. The consolidated repair is the commit containing
this checkpoint; its evidence/documentation delta was inspected, with no runtime/test changes.
No valid finding remains unresolved; the narrow repair does not require another full review.

Next: complete applicable publication checks when publishing this capability, then qualify its
competitive baseline and coding wall-time consumer before claiming superiority to llama.cpp. Keep
actual CUDA capture/replay separate from Metal observations. Cutover publication remains pending
independently. Implementation and owner tests are committed in `agent/moe-gpu-diagnosis`;
the consolidated review repair records the completed local evidence. No PR/preflight/merge is
claimed for O1 at this checkpoint.

Use `/opt/homebrew/bin/gmake` on macOS and documented Homebrew linker paths. Real ggml
libraries and a relocated shim are required for inference acceptance; the unavailable
stub is not a substitute. Runtime model readers retain R21's private-writable-copy rule.

## Separate local Antigravity capability

Keep `.agents/`, `.codex/`, `scripts/review-agy`, `scripts/agy-review-result.jq`,
`scripts/test-agy-review`, `docs/agy-development.md`, `docs/specs/agy-development.md`,
and the unstaged agy additions in `CLAUDE.md` outside the product commit. The product-language rule is already in the committed candidate; only the unrelated
Antigravity additions remain unstaged in `CLAUDE.md`.
The agy capability's earlier live owner and 36 negative cases PASS; its separate
comprehensive review found two accepted defects, both repaired. Preserve this work.
