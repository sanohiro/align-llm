# Session handoff

Read `CLAUDE.md` first. Architecture and ordering live in `docs/specs/`.

## Active connected CUDA Q6_K output-head trial (2026-09-29)

Branch `agent/native-cuda-q6-connected` starts from merged `main` `f4f05c1`
(PR #327); checkpoint `8d0828f` connected the default-off independent
Q8_1/DP4A one-column Q6_K path to actual requests but duplicated ggml's
projection. The current uncommitted candidate removes that duplicate in mode
`1` while preserving mode `0`. The authoritative contract is in
`docs/specs/gpu-runtime-performance.md`. Full logits (maximum difference
`1.90734863e-6`), 252 resident-state planes at each 31/200/330-token case,
exact greedy/rendered output, retained short/wider/short requests, malformed
selection and forced submit/completion failures passed. `make fmt`, `make
build` with real CUDA shim and `make check` (169 Align units) passed. Nsight
counted three native projections and zero ggml Q6_K output projections for
three output tokens. Against the duplicated checkpoint, five paired requests
gained 9.357/14.351/74.555 ms median at 56/16, 200/32 and 330/64 (3/5,
5/5, 5/5 wins). Against unchanged Align, native medians were -4.298/+2.766/
+0.136 ms (1/5, 4/5, 3/5 wins); against pinned llama.cpp they were +10.132/
+9.562/+16.375 ms (3/5, 5/5, 5/5 wins). These are scoped warm-request
measurements, not a general speed claim. All 30 native comparison pairs,
sources, failures and limits are in `docs/cuda-native-optimization-log.md`.

Next actions, in order: (1) finish stub shim and Python boundary verification,
check the candidate diff and complete one comprehensive review; (2) run exact
head publication preflight, publish an English PR, record review/integration
evidence and merge after required checks; (3) refresh `main`, profile the
nonduplicated request's Q4_0 and Q6_K cost, and test one bounded improvement
at a time against the current native baseline, ordinary Align and pinned
llama.cpp. Compare SASS when source inspection is insufficient. The local
one-column screen had ambiguous host timing (+0.014 and -0.007 ms paired
medians) and Nsight Systems medians 893.088 us native, 886.848 us ggml.
Nsight Compute counters remain denied (`ERR_NVGPUCTRPERM`).
Other CUDA GPUs, Qwen sizes and Gemma are unmeasured and deferred until the
corresponding hardware/model owner is available. No fixed percentage or
win-count floor governs a useful measured improvement.

## Completed CUDA Q6_K four-column screen (2026-09-29)

PR #327 merged at `f4f05c1`. Linux capture recovered the Metal-matching
417,177,600-byte Q6_K weight and three real activations. A Q8_1/DP4A native
kernel passed all four complete logits rows and greedy choices with maximum
absolute error `1.91e-6`. Five-pair completed-operation comparisons lost to
pinned ggml by `0.004725` and `0.033346 ms` median; two-row/warp, register-cap,
fast-math, read-only and aligned-load variants did not establish a gain. The
200/32 trace attributed about 78% of summed decode kernel intervals to Q4_0
matvec and Q6_K projection. The exact-head owner/preflight, one comprehensive
review with a corrected Linux preload recipe, and all three CI checks passed.
Raw captures, traces and binaries remain outside Git; reproducible details,
failed attempts and NVIDIA/ggml references are in
`docs/cuda-native-optimization-log.md`.

## Completed native CUDA Qwen3.5 capability (2026-09-29)

PR #326 merged at `5f03606`. The authenticated Qwen3.5-2B Q4_0 artifact now
runs ordinary ggml CUDA generation and serving after indexed F16 K/V prefill
writes. Exact pinned-oracle IDs at 31/200/330 prompt lengths, six retained
requests, HTTP/SSE, direct native-copy bounds, complete logits and valid state,
forced submit/completion faults, and `make check` (169 units) passed. The
default-off independent recurrent-state copy batches 18 large decode planes
but the digest-bound campaign won only 5/15 pairs against ordinary Align and
13/15 against pinned llama.cpp. The independent Q4_0 FFN screen passed
numeric comparison but lost its complete operation timing; neither kernel is
a broad speed claim. Final exact-head preflight, comprehensive review and
all three hosted CI checks passed. The older Metal lookup-trial diagnostic
explicitly refuses CUDA before state mutation. Source and receipts are in
`docs/cuda-native-optimization-log.md`; other CUDA hosts and models are
unmeasured.

## Completed current Metal speed and bottleneck qualification (2026-09-28)

Branch `agent/qwen35-current-bottleneck` merged as PR #316 at `29398bda`.
The production source closure is unchanged since PR #312. A fresh same-binary
Qwen3.5-2B M1 campaign completed five uninstrumented
alternating pairs at 64/16, 200/32 and 330/64: the already qualified mixed
native state-copy mode beat ordinary Align and pinned llama.cpp in all 15
pairs against each. Its isolated complete-FFN candidate remains outside the
real request. A corrected schema-3 phase campaign, one native-command trace,
and a complete counter-enabled Metal System Trace found quantized Q4_0/Q6_K
matrix work dominant; details and raw receipts are in
`docs/qwen35-current-native-mixed-bottleneck.md` and `eval/benchmarks/`.
The old schema-2 phase caller summed native waits from three requests; the
corrected caller now validates each request-local diagnostic log span, and
historical-receipt caveats are in this branch. A final five-pair real-model
phase rerun passed with matching outputs and phase containment. One
comprehensive review found the cross-request wait-count loophole; repair
`56278136`, synthetic regression, strict Python boundary guard and mutation
suite passed. Exact-head preflight and all three CI checks passed. The review
envelope and check evidence are on PR #316. Other Metal hosts, CUDA and Gemma
remain deferred as registered in `docs/backend-parity.md`.

## Active Qwen3.5 target verification investigation (2026-09-28)

PR #317 (`agent/native-metal-resident-execution`) merged into `main` at
`5b8669ee`. Its connected final-layer independent Metal FFN lost real
requests in all three boundary modes and was withdrawn; the related-prompt
prefill and actual Q6_K head screens motivated a complete target graph.
Their limits and receipts are in `docs/qwen35-native-final-ffn-connected-screen.md`
and `docs/qwen35-target-batch-feasibility.md`. Product generation remains on
the earlier selectable mixed native state-copy route, with ggml matrix work.

PR #318 merged the four-row graph as `4aa8cccb`. It emits all four full-model target logits rows
for the same real 2B `[0,23066,0,0]` tokens. Five alternating M1 pairs gave
115.456 ms serial versus 44.414 ms batched synchronized compute (5/5 wins),
plus 1,987,456 bytes more reported graph workspace. Every complete logit row
and the valid active KV/recurrent state met their separately predeclared
numeric bounds. The independent state diagnostic ran outside timing. See
`docs/qwen35-target-all-rows-screen.md` and its raw receipt. This is an
empty-prefix graph feasibility result, not a speculative request speedup.

PR #319 merged the exact-prefix continuation screen into `main` at `7c13f7be`.
On the real 2B Q4_0 M1 fixture, five alternating pairs all favored four-row
target verification after the identical 200-token prefix; the connected
target median paired gain was 63.126 ms, including 2.920 ms median graph
switching. Complete logits and valid active state met predeclared bounds.
The review found overly restrictive oracle checks, repaired and verified with
a non-greedy fixture. Exact-head preflight and all three CI checks passed.
See `docs/qwen35-target-continuation-screen.md` and its raw receipt.

PR #320 merged the developer-only Align acceptance/replay diagnostic at
`b66c3f7b`. The real 2B M1 five-case, five-pair screen found all-four
acceptance gained 62.325 ms paired median; rejection after 0/1/2/3 accepted
tokens lost 55.630/55.299/53.667/56.229 ms. Selected/next logits, valid
KV and active recurrent state met predeclared bounds, and a forced replay
failure published no output. See `docs/qwen35-target-acceptance-screen.md`.

The merged `agent/qwen35-lookup-draft-screen` branch started from `b66c3f7b`
and added Align-owned bounded n-gram lookup, a developer-only
entrypoint and three coding-prompt fixture streams. The real 2B M1 campaign
found complete three-draft groups in 3/18 function, 12/16 bug-fix and 1/16
test-writing attempts. Six real-prefix cases, each five alternating pairs,
found complete-group gains of 62.0–63.5 ms and immediate-mismatch losses of
52.0–52.3 ms, with all selected/next logits and committed-state checks
passing. Lookup took 0.50–0.58 microseconds median over the visited short
histories. See `docs/qwen35-lookup-draft-screen.md` and its raw receipt.
PR #321 passed final owner/preflight, a clean comprehensive review and all
three hosted checks. Final check evidence was recorded on the PR, then it
merged into `main` as `70112200`.

PR #322 merged the default-off continuous trial into `main` as `dfb39613`.
It contains the Align-owned route and diagnostic in:
`src/runtime_qwen35_generation.align`,
`src/runtime_qwen35_lookup_trial_smoke.align`,
`scripts/measure-qwen35-lookup-continuous`,
`scripts/verify-qwen35-lookup-continuous`,
`scripts/bench-qwen35-lookup-reference.cpp`,
`docs/specs/qwen35-lookup-continuous-trial.md`,
`docs/qwen35-lookup-continuous-trial.md`, and directly affected policy,
parity and Python-boundary documentation. The Metal device is accessible
after restarting Codex. The default-off trial compiles with the pinned Align
compiler, and the final M1 real-GGUF campaign passed exact IDs against the
pinned stream for all three prompts, five alternating ordinary/trial and
trial/llama.cpp pairs per prompt, plus three repeated requests at first-group
acceptance positions 0/1/2/3. Bug-fix 99/75 generation gained 491.6 ms paired
median against normal Align, 5/5; test-writing 72/96 lost 74.4 ms, 0/5.
The trial beat pinned llama.cpp generation in all 15 paired samples but beat
fresh-process wall time only on the bug-fix case. Phase and startup details,
limits and raw receipts are in `docs/qwen35-lookup-continuous-trial.md`.
The Python boundary guard and its mutation suite, Align formatting,
real-shim product generation owner, exact-head publication preflight, one
clean comprehensive review and all three CI checks passed. Final review and
integration evidence are on PR #322. Repeated-position, EOG-draft and
empty-prompt qualification passed on the final diagnostic binary.
Connected stepwise logits/state and forced target failure remain
unverified, so this route is not enabled for product requests.

PR #323 merged the fixed one-draft diagnostic into `main` as `273f500e`.
Its authoritative plan and report are
`docs/specs/qwen35-lookup-one-draft-trial.md` and
`docs/qwen35-lookup-one-draft-trial.md`. The explicit default-off two-row path,
diagnostic and independent comparison are implemented. Actual-weight full F32
and valid-state checks passed the predeclared bounds; five local pairs favored
two rows over two serial steps by 11.274 ms paired median. Repeated full and
rejected first groups, short output, EOG draft, invalid prompt and the old
four-row owner passed. Five alternating real-model pairs per task/control
found one-draft 118.7 ms faster than normal Align on bug fix but 407.1 ms
slower than three-draft; function and test-writing regressed against normal
Align. All output IDs matched. Keep one-draft diagnostic only; do not replace
three-draft or enable either for product. Raw receipts are in `eval/benchmarks/`.
The Python boundary guard, formatting, real-model owner, exact-head preflight,
one comprehensive review with an accepted fixture-hash repair and all three
hosted checks passed. Review and check evidence are on PR #323. An offline
three-token-only lookup replay still found early rejected groups on the
function and test-writing inputs, so it did not support a new fixed admission
rule; this was not a timed model run.

PR #324 merged the independent target-greedy cost screen into `main` at
`5edb39a7`. Its narrow plan is
`docs/specs/qwen35-target-greedy-cost-screen.md`; the result is in
`docs/qwen35-target-native-greedy-trial.md`. The independent two-dispatch
Metal argmax passed actual four-row F32, tie/nonfinite/tail checks and saved
0.289 ms paired median against C++ copy/scan locally, including its wait.
Align's own scan was 0.311–0.321 ms without readback. The default-off
`trialnative` route now borrows the real output through a checked shim ABI,
returns only four IDs, and leaves ggml source unpatched. Three coding prompts
each had five alternating fresh-process pairs against normal Align, old
three-draft Align and pinned llama.cpp in two campaigns. Repeated first-group
accept/reject, short, EOG and invalid requests matched pinned IDs. The later
campaign and same-session ten-pair bug-fix run had substantial system noise;
the user reported that other software may have been running. The connected
boundary does not show a reliable win after the extra Metal command and wait. Keep this route
developer-only; no product adoption or general llama.cpp victory is claimed.

After the user stopped the heaviest other software, a final-binary
lower-load campaign repeated all three prompts with five alternating pairs
per control. Old trial minus native medians were +0.3/+1.5/-3.1 ms for
function/bug-fix/tests; a ten-pair reused-session bug-fix run gave -7.8 ms,
native 3/10 wins. All IDs matched. The full receipts are in
`eval/benchmarks/`; the connected effect is too small and inconsistent for
product adoption. Exact-head preflight, the clean review, all three hosted
checks and merge completed on PR #324. Connected stepwise state and injected target
failures remain required before any lookup product admission. Other Metal
generations, CUDA, Q4_1 down, five-row verification and Gemma remain
unmeasured/deferred in `docs/backend-parity.md`.
The narrow real-model repeated-request owner, independent local benchmark,
real/stub shim builds, `run-ggml-spike-smoke`, Python boundary guard and
formatting passed. One `codex review --uncommitted` at session
`01a0e7ec-fd86-7e51-ba60-ceadaeadb260` found no actionable bugs; only the
later wording of possible host interference changed after review.

Current branch `agent/qwen35-q6-small-batch-head-screen` starts from merged
`main` at `5edb39a7`. After the user stopped the heaviest other application,
one more 10-pair reused-session bug-fix run of the final #324 binary matched
all 22 output streams but split 5/10 wins; old trial minus native generation
was +5.6 ms paired median. During this run iTerm still used about one CPU core,
and Spotlight/loginwindow were intermittently active. The retained receipt is
`eval/benchmarks/qwen35-target-native-greedy-session-post-app-stop-2026-09-28.json`;
it is additional noisy evidence, not a new native-greedy speed claim. The
independent Q6_K four-activation local screen defined in
`docs/specs/gpu-runtime-performance.md` is implemented and measured. On the
actual 417 MB Q6_K output head, every complete and 257-row tail output met
the predeclared bound and greedy choices matched, but the independent Metal
kernel lost four of five local pairs to pinned ggml after warmup; median
ggml-minus-native completed wall was -0.708 ms. A command trace also found a
-0.746 ms GPU-interval median. The fourth activation repeats the first of
three real-model captures. Receipts and verdict are in
`docs/qwen35-q6-batch4-screen.md`. Do not connect this mapping to a real
request; it has no local advantage to cover an extra graph boundary. The
next actions are one stable-candidate review and exact publication preflight,
then a GPU hypothesis that reduces a larger connected execution boundary or
improves the small-batch dequant/lane mapping by a measured margin. Preserve
the existing ggml route as control. Other Metal hosts, CUDA and Gemma remain
unmeasured or deferred in `docs/backend-parity.md`.

## Completed native Metal Q4_0 complete-FFN capture screen (2026-09-28)

Branch `agent/native-metal-q4-full-ffn-capture` starts from merged `main` at
`b17ba6ce` (PR #314). GPU optimization remains the priority. The independent
two-dispatch gate/up/SiLU plus unsplit-down screen on real captured 2B layers
3 and 23 is implemented; contract, report and raw final pairs are in
`docs/specs/gpu-runtime-performance.md`,
`docs/qwen35-q4-full-ffn-capture-screen.md`, and
`eval/benchmarks/qwen35-q4-full-ffn-capture-2026-09-28-{j,k}.txt`.
Captured and rebuilt ggml gated/final outputs are byte-identical; native
outputs pass the declared bound and complete native FFN wins 20/20 local pairs
with 0.057–0.068 ms paired median gain. An intermediate CPU wait in
two commands adds 0.362–0.423 ms, while ordered same-queue submission with
only a final wait passes both arms' output checks and adds 0.030–0.059 ms. This
is not a request gain. One comprehensive review found an unchecked alternating
arm; the narrow repair in `59a8af8d` separates its buffers and checks both
outputs after every pair. Exact-head preflight and all three CI checks passed;
PR #315 merged as `d67e224a`. Keep captures/weights out of Git. Other Metal
hosts, CUDA, Q4_1 down and Gemma are deferred.

## Completed native Metal Q4_0 down split-K screen (2026-09-28)

Branch `agent/native-metal-q4-down-split-screen` starts from merged `main` at
`c51c0cfe` (PR #313). GPU optimization remains the priority. The independent
down screen and raw two-run result are in `docs/qwen35-q4-down-split-screen.md`
and `eval/benchmarks/qwen35-q4-down-split-2026-09-28-{d,e}.txt`. Actual 2B
layers 3 and 23 and a synthetic tail pass the declared numerical bound;
captured and rebuilt ggml full outputs are byte-identical. Two/four-way
split-K loses direct unsplit GPU-interval and wall comparisons and is withdrawn.
The independent unsplit down arm wins 19/20 isolated ggml wall pairs but has no
complete-FFN or request claim. One comprehensive review and exact-head
preflight passed at `c6e3dce0`, all three PR checks passed, and PR #314 merged
as `b17ba6ce`. Next screen a complete native gate/up/SiLU plus unsplit-down
command using actual captures. Source weights
and captures remain outside Git. Another Metal host, CUDA and Gemma are
deferred until qualified.

## Completed native Metal tile-consumer FFN screen (2026-09-28)

Branch `agent/native-metal-ffn-tile-consumer` starts from merged `main` at
`eee12bdb` (PR #312). GPU optimization remains the priority. The bounded
independent Metal Q4_0 FFN screen is implemented and its complete local result
is in `docs/qwen35-native-q4-tile-ffn-screen.md`, with raw pairs in
`eval/benchmarks/qwen35-native-q4-tile-ffn-2026-09-28.json`. Actual captured
layers 3 and 23, plus a synthetic nonmultiple tile, pass the predeclared
numeric bound. The fastest 512-thread variant loses all five paired complete
FFN operations on both layers: paired ggml-minus-native medians -0.582 and
-0.647 ms; the reviewed final wrapper with twenty untimed reuse checks and
post-pair output checks lost another 10/10 pairs (-0.609 and -0.662 ms).
Scalar/packed loads, 256/512/1024 threads and two output
partitions were screened; the latter increases repeated gate/up work. Withdraw
this mapping before runtime integration; retain ggml fallback and prior native
state-copy route. Final exact-head preflight and all three CI checks passed at
`8abed89b`; PR #313 merged as `c51c0cfe`. Next inspect down projection
scheduling without repeating gate/up work. Q4_1 down
layers, another Metal host, CUDA and Gemma remain deferred until qualified.

## Completed native Metal copy-command greedy trial (2026-09-28)

Branch `agent/native-metal-copy-greedy` merged as PR #312 at `eee12bdb`.
This default-off
finite, first-index Metal argmax is selected by Align inside the native decode
state-copy command; the ordinary full-row and mixed native modes remain.
The contract/cost ceiling and completed result are in
`docs/specs/gpu-runtime-performance.md` and
`docs/qwen35-native-copy-greedy-trial.md`. Final real 2B comparison passed 48
exact complete logits and 4,116 resident planes; local Metal tie/nonfinite,
2B/0.8B generation, 0.8B serving/SSE and both forced fault owners passed.
Five alternating pairs at 64/16, 200/32 and 330/64 found no reproducible
incremental request win over the already native mixed mode. The candidate
still beat ordinary ggml Align in 15/15 pairs, due chiefly to earlier native
copy work. Three local command pairs found ~0.019–0.027 ms additional GPU work
per decode command and a larger required host wait. The default remains off.
Final unforced shim was restored byte-identically after fault qualification.
`gmake fmt`, strict Python boundary, real/stub shim builds, focused owners,
exact-head `scripts/pre-pr` and one comprehensive independent review passed at
`a0e4c342`; CI's hosted and both installed Ubuntu profiles passed. The review
was CLEAN with no findings. Another Metal host, CUDA and Gemma remain
unmeasured.

## Completed native Metal prefill state-copy trial (2026-09-28)

Branch `agent/native-metal-prefill-state-copy` merged as PR #311 at
`21d6a4b2`; its implementation and result are in
`docs/qwen35-native-prefill-copy-trial.md`.

The selectable prefill route removes 36 ggml state `CPY` nodes per prefill
graph, and Align waits for the native command before parity publication in
ordinary and streaming generation. The final 2B owner passed 48 exact full
logits and 4,116 resident planes over short/128+71/short requests; 2B/0.8B
generation, 0.8B SSE/recovery, invalid-mode and both native failure owners
passed. The fixed-binary five-pair 2B untraced comparison versus the already
native mixed-decode route found paired control-minus-prefill medians of
-4.449, -17.033 and -17.426 ms at 64/16, 200/32 and 330/64, with the two
longer conditions losing four of five pairs. Ordinary Align still lost all
15 pairs because the candidate includes the earlier decode improvement.
Instrumented prefill graph/submission call savings were outweighed by native completion
waits; the process-footprint screen resolved no difference. Keep the prefill
option default-off and retain mixed decode as the preferred tested route.

## Completed native Metal convolution-state copy trial (2026-09-27)

Branch `agent/native-metal-conv-state-copy` merged as PR #310 at
`df6d3cdc`. It extended the Align-selected native decode boundary to the 18
strided convolution-state copies while preserving the Delta-only and ordinary
ggml graph controls.
The plan and cost ceiling are in `docs/specs/gpu-runtime-performance.md`; the
implementation and result are in `docs/qwen35-native-conv-copy-trial.md`.

A temporary real-model shim diagnostic (removed from source after capture)
found all 18 2B decode convolution sources shaped `[3,6144,1,1]` with F32
strides `[4,16,98304,98304]`, versus contiguous destination strides
`[4,12,73728,73728]`. Source reachable span was 98,300 bytes, destination
logical size 73,728 bytes; a real two-token provider request completed. The
raw trace is uncommitted diagnostic data under the Git common directory.
The implementation now adds bounded strided descriptors and one compute pass to
the existing native command, selected by Align's separate default-off option.
The final 2B owner passed 32 exact complete logits and 2,688 exact resident
planes, the 2B/0.8B generation owners and mixed submit/completion failure
owners passed, and local 37x5/6144x3 kernels passed. Five alternating untraced
pairs per 64/16, 200/32 and 330/64 condition all favored mixed over Delta-only,
ordinary Align and pinned llama.cpp. Paired Delta-only-minus-mixed medians were
+6.412, +12.673 and +14.190 ms. Instrumented phase results retained three
adverse whole-request pairs; the mixed session's startup was slower, while the
five-pair process-footprint screen found no resolved after-request difference.
All receipts are under `eval/benchmarks/qwen35-native-conv-copy-2026-09-27-*`.
`gmake fmt`, strict Python boundary, focused real-model/failure owners and
`scripts/pre-pr` passed at `e73e9233`. The comprehensive independent review
was CLEAN with no findings; all three PR checks passed before merge. A second
Metal host and CUDA remain unmeasured until device/session support is available.

## Completed independent Metal state-copy failure qualification (2026-09-27)

Branch `agent/native-metal-state-copy-failure` merged as PR #309 at
`9ff42d21`; `fc9ffa7417` introduced the initial native copy seam.
The user requires an Align-owned
independent GPU execution path, with ggml retained only as a selectable
fallback/temporary producer. Do not promote the ggml F32 source patch as the
operating goal. The current opt-in `ALIGN_LLM_NATIVE_STATE_COPY=1` replaces 18
contiguous decode DeltaNet copy nodes with one independent Metal blit command
over borrowed ggml shared allocations. Align controls selection, state parity,
generation and the completion dependency. The ordinary unmodified ggml graph
is mode `0` and rollback. This is one native execution seam, not a completed
independent model backend.

Latest M1 2B generation passed after the device-identity review repair;
2B/0.8B generation and 0.8B serving passed before that narrow repair. The 2B 16-token
comparison has exact 1,344 state-plane hashes and 16 full-logit hashes.
Invalid mode refuses construction. Five alternating, same-binary,
same-**unmodified**-bundle 2B warm-request pairs at 64/16, 200/32 and 330/64
favor the reviewed native route in 15/15 pairs: control-minus-native paired
medians +44.636, +88.505 and +186.868 ms. It also wins 15/15 pinned llama.cpp
request pairs. The pre-review build retained one -5.380 ms Align and -8.367 ms
reference pair at 200/32; both receipts are kept.
Prefill graph differences are within about 1 ms; decode producer graph gains
are +51.364, +102.889 and +200.932 ms but exclude native completion. M1
startup remains about 1.0 s versus llama.cpp about 0.45-0.46 s. The earlier
process-footprint screen observed native +0.109 MiB physical and +0.531 MiB
peak after three requests, while the preceding screen had the opposite sign;
total GPU/system memory is unmeasured. The first synchronous native version
lost every pair;
its retained receipt and the revised version's evidence are in
`docs/qwen35-native-state-copy-trial.md`.

The previous capability passed strict Python boundary, real/stub shim builds,
`make fmt`, owner checks and one fresh native-code review. Two P2 findings were repaired: admit only
the sole selected `MTL0` matching the physical device, and reject mislabeled
state-copy controls in the paired measurement tool. This branch adds test-only
native submit and post-completion failure builds plus a real-model worker owner.
Both fault builds returned the exact `failed` envelope without a result/token
and exited 2 on 2B mode `1`; their mode-`0` two-token controls completed.
`python3 scripts/check-python-boundary --strict`, real forced shim builds and
both focused failure owner runs passed. The normal real-shim build and 2B
generation owner also passed after fault injection was compiled out. The
reviewed candidate passed final preflight and all three PR checks. Qualify
another Metal device when available; keep the route opt-in until then.
CPU/CUDA Qwen3.5 and Gemma semantic admission remain deferred in
`docs/backend-parity.md`. Keep model weights, binaries, raw traces and source
builds outside Git; checked-in benchmark JSON and the report are intentional.

## GPU-only optimization priority (2026-09-27)

The user directs
current work toward GPU inference performance; HTTP transport optimization is
deferred until GPU options are adequately tested. The adjacent-range Metal
scheduling patch remains default-off with no repeatable competitive request
win; see `docs/qwen35-metal-adjacent-range-trial.md`.

The 2026-09-27 counter-enabled Metal System Trace has Shader Timeline enabled.
On matched Qwen3.5-2B 200/32 work it sampled F32 copies at about 99 ms per
Align request and 35 ms per pinned llama.cpp request; Q4_0 and Q6_K matvec
samples per request were close. These are diagnostic attributions, not saved
time. Independent bindings show both use shared Metal buffers and the same
state-copy launch shapes. See `docs/qwen35-decode-attribution.md` and
`docs/gpu-optimization-lessons.md`.

The parity-major recurrent-state placement trial cut the last decode's
36-copy destination start span from 38,305,792 to 19,152,896 bytes, matching
the reference span. Its actual 2B full logits and semantic state hashes were
exact; 2B/0.8B generation owners passed. Five-pair untraced request medians
were +0.397, -3.195 and -18.414 ms at 64/16, 200/32 and 330/64, control
minus trial. Separate phase clocks did not establish a repeatable gain.
The source and root `main` were restored; the exact trial patch, binaries,
owner logs, copy census and complete receipts remain under the resolved Git
common directory's `diagnostics/q35-ingraph-greedy-2026-09-27/counter-trace-20260927/`.
The result and cost ceiling are in `docs/specs/gpu-runtime-performance.md`.

The next large contiguous-copy Metal specialization, built through the
checked-in `--linear-copy` recipe, won all 30 2B control comparisons across
two five-pair 64/16, 200/32 and 330/64 campaigns. The measured recipe
bundle's paired control-minus-trial medians were +52.866, +99.577 and
+193.448 ms, and its
warm request arm medians beat pinned llama.cpp at each length. The real 0.8B
campaign won 14/15 comparisons and retained one -11.338 ms short-case pair.
The 2B actual logits and resident state were byte-identical; both sizes'
generation owners passed. The actual graph has 18 eligible contiguous 1 MiB
DeltaNet copies and 18 ineligible strided convolution sources per decode token.
The summed F32 copy Shader Timeline samples fell from 199.922 to 11.228 ms
over two matching instrumented requests, an attribution result rather than
an isolated marginal saving. Startup remains mixed. A clean checked-in-patch bundle was rebuilt after removing
whitespace from patch context; its executable and embedded Metal library are
byte-identical to the measured bundle, and both model generation owners pass.
The ordinary backend bundle remains the rollback. A six-case copy view owner
passed bit-exactly on control and clean bundles. A five-pair process-footprint
screen found effectively unchanged after-three-request values; the paired
physical-peak difference median was +0.062 MiB (control minus clean), but it
does not measure total GPU/system memory. A direct same-binary pre-adjacent
bundle versus clean campaign won all 15 2B pairs and all 15 pinned llama.cpp
pairs, with base-minus-clean request medians +55.011, +111.526 and +224.990 ms
at the three lengths. A matching 0.8B direct campaign won all 15 Align pairs
and 14/15 pinned-reference pairs; one 330/64 reference pair was faster by
15.966 ms. Its base-minus-clean paired medians were +60.626, +110.062 and
+230.010 ms. The explicit clean bundle is recommended for local
Qwen3.5 inference on the measured M1 host; no universal default is claimed.
Conditions and receipts are in `docs/qwen35-metal-linear-copy-trial.md`.

Follow-up raw GPU counters from the retained 200/32 traces show the Q4_0 and
Q6_K decode matrix-vector shaders at 100%/98% median Buffer Read Limiter and
49.2/52.5 GB/s median GPU read bandwidth in the trial; pinned llama.cpp is
100%/99% and 50.1/55.7 GB/s. These are whole-GPU, instrumented samples
associated with shader intervals, not exact dispatch clocks. Q4_0 prefill
matrix-matrix instead shows 83% median F32 utilization. The measured trial's
Q4_0 plus Q6_K matrix-vector sample total is about 61% of worker shader time;
remaining F32 copy is about 0.5%. The two arms have different prefill chunk
sizes, so their matrix-matrix bandwidth is not a direct efficiency comparison.
Source traces, extraction and caveats are in `docs/gpu-optimization-lessons.md`.
The largest candidate shader gap is about 44 ms near a graph boundary; no
per-token dispatch stall is established by that one gap.

A same-saved-binary, same-linear-copy-bundle 128/256 prefill-width follow-up
completed two five-pair three-arm campaigns against pinned llama.cpp. All
actual prompt/output counts and generated outputs matched. Width 256 removes
one prefill graph at 200 and 330 tokens. Synchronized prefill paired medians
were -3.163 ms (0/5 wins) at 200/32 and +4.892 ms (5/5) at 330/64;
uninstrumented whole-request paired medians were -2.609 ms (2/5) and
-9.812 ms (1/5), with substantial host variation. Width 128 stays default.
The pinned Metal Q4_0 matrix kernel already uses a 64-by-32 tile with
threadgroup weight staging and SIMD-group multiplication; width 256 alone is
not a new weight-reuse mechanism. The listed 2B tensor extent divided by
decode graph time is about 48 GB/s, consistent with separate 49-52 GB/s
matvec GPU read samples but not a physical-byte measurement. See
`docs/qwen35-prefill-counter-followup.md` and its complete receipts.

A new actual-weight Q6_K output-head screen assigned four rather than two
rows per SIMD group. Three captured full/tail output vectors were exact against
both capture and ggml. Five paired local comparisons per activation produced
ggml-minus-four-row medians +0.003, -0.021 and -0.050 ms, with 3/5, 2/5 and
2/5 wins. A checksum-verified contiguous read of the same 417 MB took 7.758 ms
median GPU command time (53.77 GB/s listed bytes), slower than the Q6_K
projection; this is not a bandwidth roof. No runtime integration or complete
request claim follows from this local loss. Source patch and complete receipts
are in `docs/qwen35-q6-four-row-screen.md`.

The real first-decode Q4_0 screen captured all 24 FFN gate weights and
activations, verified all 72 FFN weights against the GGUF, and compared a
lossless split-scale layout plus two/eight-row SIMD mappings against the pinned
four-row layout. The split layout had no stable 24-layer gain; both row changes
lost the GPU interval comparison after independent A/B weight buffers removed
an order-dependent cache artifact. No real-model integration followed. See
`docs/qwen35-q4-layout-screen.md` and its complete receipts.

Latest local verification: `scripts/run-gpu-backend-recipe-smoke` PASS;
`python3 scripts/check-python-boundary --strict` PASS; clean pinned-source
`git apply --check` PASS; 2B and 0.8B `scripts/run-qwen35-generation-smoke`
PASS on the clean bundle; copy geometry owner PASS on both bundles; 2B direct
baseline/reference campaign PASS; process-memory screen PASS; 0.8B direct
baseline/reference campaign PASS. One fresh
`codex review --uncommitted` of the candidate found no actionable issue;
the later changes only add this 0.8B campaign and align its records. A prior
hosted
`scripts/pre-pr` stamp for owner test `gpu-backend-recipe` at exact
`fc9ffa7417` is PASS. Its earlier independent review found no actionable
correctness regression;
the separately found patch-context whitespace was repaired, the bundle was
rebuilt and its executable sections compared before these final checks.

The current fast F32-copy bundle is a measured ggml Metal specialization,
not completion of the requested selectable independent Metal path. The native
SwiGLU opt-in replaces one operation inside ggml's encoder; it is also not an
independent execution path. Preserve both as measured options while pursuing
Align-selected native execution with the existing ggml path as fallback. Do
not treat the copy win or the earlier native FFN request result as a reason to
drop that goal. The next GPU action is to choose a concrete decode weight-reuse,
traffic, or fusion seam for a selectable native trial, then verify actual-model
correctness and connected request cost before considering adoption.
The tested Q4_0 split/row-count variants are withdrawn; do not repeat them
without a new mechanism. Do not repeat the 128/256 chunk
switch as a proxy for a new prefill kernel. The remaining strided convolution
copy is about 1.3 MiB per decode token, so a copy-only rewrite is lower
priority after the contiguous fix. Preserve success-only state publication.
Avoid repeating the rejected singleton K/V copy, parity placement and
arithmetic-only native matvec trials without a new mechanism.
CPU/CUDA/Gemma admission remains deferred in `docs/backend-parity.md`.
Intentional uncommitted files at this diagnostic checkpoint are the updated
performance plan, parity register, lessons, local-chat recipe, Python boundary
classification, copy geometry/footprint developer owners, Q4_0/Q6_K/prefill
reports and their checked-in benchmark receipts. Diagnostic binaries and
large raw captures stay under Git's common directory and are not committed.
No new runtime code, PR or merge is claimed.

## Qwen3.5 in-graph Metal greedy trial (2026-09-27)

Branch `agent/native-metal-ffn-integration`, exact prechange head `9dae952a`;
the implementation/evidence checkpoint is this branch's HEAD. The local opt-in
`ALIGN_LLM_GRAPH_GREEDY=1` candidate is implemented against a
separate pinned ggml Metal patch and a marker-checked Align graph. The old
full-logit graph is the default and rollback. Real 2B/0.8B generation, 2B
serving, 336 exact resident-state hashes, captured-row tie/nonfinite cases,
invalid-mode refusal, stub/real shim builds and Python boundary checks pass.
The 200/3 boundary trace changes three full-row gets (2,979,840 bytes) to
three scalar gets (12 bytes) with the same 1,377 total command buffers.

Five alternating local captured-row pairs reduce synchronized argmax by a
median 0.505 ms. Final repaired-binary same-binary 2B worker paired request
changes are −1.644, +1.691 and +5.035 ms at 64/16, 200/32, 330/64; long
worker wins 4/5. Final HTTP/SSE long paired gains are +13.916/+5.769 ms, but
HTTP has one −70.021 ms pair; pinned llama.cpp remains faster at every worker
median. The pre-repair worker's +21.843 ms long gain did not reproduce. The
pre-repair combined existing sync-upload/final-FFN-row arm improves warm-start
construction by about 0.5 s under the measured cache conditions but also
remains slower than llama.cpp for warm requests. Keep graph greedy default-off.
The exact conditions, adverse samples, raw receipts and next hypothesis are in
`docs/qwen35-ingraph-greedy-trial.md`.

One fresh host-native review covered the full candidate and found two valid
issues: early short-vocabulary refusal and bundle-bound patch identity. Both
were repaired; the final 2B/0.8B generation and 2B serving owners, exact
short-vocabulary pre-upload refusal, patch-tamper refusal, stub owner, strict
Python boundary and final-binary worker/HTTP campaigns pass. The review and
repair diagnostics are in the Git common directory. Next: for further speed work,
screen a Q6_K output projection that emits partial maxima directly in its
producing graph against captured real weights and activations; admit it to the
real model only if the exact full-logit/state oracle survives. Do not repeat
the one-to-one Q6_K mapping or post-sync GPU argmax. CPU/CUDA Qwen3.5 and Gemma
semantic admission remain deferred in the backend parity register. No PR,
preflight or merge is claimed for this local trial.

## Qwen3.5 Metal private-storage screen (2026-09-27)

Branch `agent/native-metal-ffn-integration`, starting from NEON checkpoint
`1ad16a24`. This local screen is complete. The pinned ggml all-private buffer
switch passed the captured real Q6_K projection oracle and the same-binary 2B
worker output/count checks, but did not improve the local projection across
three activations. Five alternating worker pairs at 64/16, 200/32 and 330/64
gave paired shared-minus-private request medians -16.351, -35.645 and
-81.652 ms; private won 0/5, 2/5 and 2/5. Pinned llama.cpp remained faster
on every candidate request median. The graph-external residual grew in every
pair, consistent with pinned ggml's private input-setter blit and completion
wait. Keep shared storage as default; no product buffer mode was added. Read
`docs/qwen35-private-metal-trial.md` and the checked-in raw receipts for the
conditions and uncertainty. Strict Python boundary, invalid-setting refusal,
measurement completion and diff checks passed. No cross-backend claim.

Next: screen an in-graph Q6_K projection plus partial-top-token consumer with
actual captured weights/activations, preserving the exact full-logit/state
oracle. It must reuse the producing command boundary; the post-sync GPU argmax
and one-to-one Q6_K mapping have already lost. If the bounded local screen
does not show a connected advantage, redirect to a larger fused recurrent/FFN
layout. No PR/preflight/merge is claimed for this checkpoint.

## Qwen3.5 shared-row greedy follow-up (2026-09-27)

Branch `agent/native-metal-ffn-integration`, based on shared-logits checkpoint
`32ad975e`; implementation/evidence checkpoint `6d552f4b`. The NEON experiment
is complete as a local default-off trial.
The hierarchical GPU argmax integration passed real correctness but lost its
connected speed case because each token required a second Metal command buffer;
its runtime code was withdrawn. `docs/qwen35-hierarchical-greedy-trial.md`
retains the decision, source patch and complete receipts.

The new default-off `ALIGN_LLM_NEON_GREEDY=1` path uses the same validated
shared F32 output row, but runs a bounded AArch64 NEON finite/first-index
argmax scan without another GPU queue or full-row copy. Align still controls
model, session and generation; ggml still controls graph computation. The
local actual-row screen won 96–98/100 pairs by about 0.25 ms. Real 2B/0.8B
generation, 2B serving, 336 exact state hashes, invalid flag refusal, odd
lengths and real/stub shim builds pass. Five-pair 2B worker and two same-binary
HTTP/SSE campaigns are complete. Worker paired request medians improve by
1.167, 0.074 and 21.514 ms at 64/16, 200/32 and 330/64, but HTTP/SSE and
the scalar-shared comparison have adverse conditions; pinned llama.cpp is
faster on all worker medians. Keep this mode default-off. Read
`docs/qwen35-neon-greedy-trial.md` and the checked-in raw receipts for exact
conditions, phase clocks and limits. No cross-backend speed claim is made.

Verification: managed Align per-unit check and `gmake fmt`; real and stub shim
builds; real 2B/0.8B generation and 2B serving owners; 336 exact state-plane
hashes; invalid-flag and odd-shape checks; strict Python boundary; measurement
config owner; three complete benchmark receipts; and staged whitespace check
pass. One host-native `codex review --uncommitted` covered the complete
candidate and returned CLEAN, findings none. Its local envelope and log are
retained under the Git common directory. The only post-review repair changed
diagnostic artifact packaging and its link, with no runtime behavior change.

Next: for further speed work, first screen a fused
Q6_K output projection plus partial-top-token consumer using captured real
weights/activations and an in-graph execution boundary; retain the full-logit
oracle and existing ggml path. Do not repeat the prior one-to-one Q6_K kernel
mapping or post-sync GPU argmax. CPU/CUDA Qwen3.5 and Gemma graph admission
remain deferred in the backend parity register. No PR/preflight/merge is
claimed at this checkpoint; publication of the completed local experiment is
separate from the next optimization trial.

## Qwen3.5 shared-logits boundary trial (2026-09-27)

Branch `agent/native-metal-ffn-integration`, old-binary control `57fd7a6b`,
implementation/evidence checkpoint `9b9bf9bb`. The committed default-off
`ALIGN_LLM_SHARED_LOGITS=1` trial found that the real 2B output resides in a
shared Metal buffer; the Align-owned
greedy scan can borrow it through a checked thin ABI after synchronized graph
compute. The 993,280-byte copied readback disappears. Three real full-logit
vectors and 336 state-plane hashes match the old binary exactly; 2B/0.8B
generation, 2B HTTP/SSE and generic generation owners pass. Five alternating
2B worker and HTTP/SSE pairs across 64/16, 200/32 and 330/64 have mixed
results; no repeatable request gain and pinned llama.cpp remains faster. Keep
the mode default-off. `docs/qwen35-shared-logits-trial.md` and the checked-in
receipts contain the comparison. The singleton K/V copy elimination and ggml
GPU argmax trials also passed local correctness but lost their real-request
speed tests; their code was removed and their closures are in
`docs/specs/gpu-runtime-performance.md`. Raw diagnostic patches/logs remain
untracked under the resolved Git common directory. The checkpoint has not
been published or merged. One host-native comprehensive `codex review
--uncommitted` found a valid intermediate-prefill scan regression. It was
repaired without changing the trial approach. Real-shim build, 2B generation
with full prefill logits, same-binary 200/16 HTTP/SSE and strict Python
boundary checks pass after repair; the complete review log is in local
diagnostics. Request 123 records the non-blocking Align borrowed-view return
gap.

Next: complete the local checkpoint and choose a larger unit of GPU work. The
paired-load Q6_K projection probe already passed exact real activations but
showed no stable gain, so do not repeat that strategy. Test either a multi-stage
gate/up/activation/down path or hierarchical GPU argmax after a bounded local
real-data test. The latter needs first-index-tie and finite semantics; the
existing single-threadgroup ggml argmax slowed decode. Require exact real
logit/state comparison and alternating whole-request timing at integration.
CPU/CUDA Qwen3.5 admission and Gemma semantics remain deferred in the backend
parity register. Do not infer an M1 speed gain from M3/M4/M5 papers or from
the invalid-output projection-pruning diagnostic.

## Qwen3.5 mapped-weight trial (2026-09-27)

Branch `agent/native-metal-ffn-integration`, baseline `9c61d3f9`, reviewed
implementation/evidence checkpoint `4c4aeaa9`. A default-off
`ALIGN_LLM_MAPPED_WEIGHTS=1` path now maps the actual Alignpack and places its
planned tensors in a host-backed Metal buffer. Align owns mode selection, pack
validation, plan, admission and session lifetime; the thin shim owns mmap,
bounds, buffer placement and release. Current ggml graph/compute and the upload
fallback remain. Read `docs/mapped-weight-trial.md` and its complete benchmark
receipt. The same binary passed 2B/0.8B real generation owners, 2B HTTP/SSE,
744,960 exact F32 logits and 258 exact state records. Five-pair worker and
HTTP/SSE measurements show ~0.4 s faster isolated startup, but no stable warm
prefill/decode/request gain. Pinned llama.cpp remains faster on all three worker
request medians. The mapped and validated files use separate opens; the trial
assumes a stable local pack and stays default-off. Process RSS/vmmap does not
establish total GPU physical-memory savings. Build, formatter, strict Python
boundary and measurement-input owner pass. One comprehensive host-native review
found a relative-pack-path refusal; it was fixed and a real 2B relative-path
request passes. No valid finding remains unresolved. Raw captures and diagnostic
memory logs are retained under the resolved Git common directory. This section supersedes the older
mapped-weight next action below; no publication or merge is claimed.

Next: compare matched endpoint command-buffer and graph preparation costs on
200/32; if device time remains dominant, test a larger
gate/up/activation/down fusion or a different Q6_K mapping with the existing
exact-logit/state oracle. CPU/CUDA admission and Gemma semantics remain
deferred; no new Align language gap was found in this trial.

## Qwen3.5 decode attribution checkpoint (2026-09-26)

Branch `agent/native-metal-ffn-integration`, baseline `aa54a963`, final
diagnostic checkpoint `a71e8799`. Read
`docs/qwen35-decode-attribution.md` and the compact raw receipt. An independent
Metal pipeline/launch census on the actual 2B request found 663 Align versus
682 pinned-llama decode dispatches, with 613 identical function/launch
signatures including every major Q4/Q5/Q6 matrix-vector, attention, recurrent
and convolution kernel. The dominant kernels are not missing from Align. A
diagnostic graph that omits only the last Q6_K output projection (node 1,109 of
1,110) changes paired synchronized decode times by 3.718–7.999 ms, but corrupts
the second token and is not an inference candidate. The M1 trace has no shader
timeline; dispatch-boundary timestamp counters are unavailable. No product code
or inference default changed; compiled probe binaries and full traces remain
untracked. The checked-in probes and fixed input fixture reproduce the 663/682/
613 census. A third five-pair run verifies every unpruned response against the
normal output and records pack, geometry, options and verified bundle identities;
all five pruned-graph deltas remain positive. Strict Python boundary and receipt
identity checks pass. The first comprehensive review found a reproducibility
gap, repaired in `40c2c7a0`; the final full-diff review found two narrow
measurement-integrity issues, repaired in `a71e8799`. No valid finding remains
unresolved. The complete review envelope is in the resolved Git common
directory. This is a local checkpoint; no publication or merge is claimed.

Next: make a bounded mapped-Alignpack weight trial reviewable. First record its
ownership/ABI contract and closure cases under `docs/specs/` because it changes
the pack-file-to-device ownership boundary. Keep Align in charge of selection,
validation and session lifetime, with the current upload path as rollback.
Implement an opt-in real-model path, qualify bytes/logits/state and cleanup, then
measure construction, first use, warm prefill/decode, complete requests and
physical memory under controlled matched conditions. Source/binary evidence
shows pinned llama.cpp maps weight pages while Align currently copies into a
ggml-owned Metal buffer; this remains a causal hypothesis for the decode gap,
not a proven speed gain. No new Align gap has been established yet. CPU/CUDA
Qwen3.5 qualification and Gemma semantic admission remain deferred.

## Final-layer single-row FFN checkpoint (2026-09-26)

Branch `agent/native-metal-ffn-integration`, baseline `9e1719c9`. Implemented
`ALIGN_LLM_PREFILL_LAST_FFN_ROW=1` as an opt-in Align session choice; absent/`0`
retains the full-row graph. It narrows only the final prompt chunk's last FFN
after all state-producing attention work, in both normal and streaming sessions.
Read `docs/final-ffn-row-trial.md` and its complete raw receipt before resuming.
No new Align gap or ABI, retained device buffer, backend-name gate or Python
product path was introduced.

Managed build/format, strict Python boundary, config refusals and 2B/0.8B
generation/serving owners passed. Same-width 128/256/512 comparisons cover
71,516,160 actual full-logit floats: max absolute difference 0.00361634 under
the predeclared 0.01 bound, identical argmax, bit-identical decode; old binary
versus new OFF is exact. All 588 full resident-state hashes match. Native SwiGLU
plus this mode passes the 2B owner. A Q4_0 matrix-vector kernel is selected in
the final graph, with the same command-buffer count and reported Metal peak.

Five alternating old/new/pinned-llama worker groups show prefill improvement in
4/5 pairs at each of 64/16, 200/32 and 330/64, but whole-request effects are
mixed. Same-binary HTTP/SSE has two warmups and five alternating pairs across
eight cases; several requests regress or have no robust gain. Even the no-op
129/1 negative control moves. Keep the mode default-off as an experiment; do
not claim a llama.cpp win. No samples were excluded. Full raw paired evidence
and source/binary identities are in the tracked receipt; 576 full-logit binary
captures and diagnostic logs are in the resolved Git common directory.
Implementation/evidence checkpoint `3f0904d6` received one fresh host-native
comprehensive review (`codex review --commit 3f0904d6`): CLEAN, findings none.
The review envelope is retained in the resolved Git common directory. The
local checkpoint is complete; no publication or merge is claimed.

The subsequent decode diagnostic above completed the Q6_K projection and
dispatch census. It did not establish a new Q6_K kernel gain or per-shader
timing. The top section owns the current next action.

## Final-prefill output / Q6_K checkpoint (2026-09-26)

Branch `agent/native-metal-ffn-integration`, baseline `1ae5824a`. Implemented
`ALIGN_LLM_PREFILL_FINAL_LOGITS=1` by default; `0` restores all chunk outputs.
Nonfinal prefill executes every recurrent/KV state root and its producers, while
omitting the final layer's unused output tail and vocabulary head/readback.
Both generation paths and fixed 64-hex graph identities include the selection.
Read `docs/final-prefill-q6-trial.md` and its two raw receipts before resuming.

Completed: managed build, formatting, strict Python boundary, configuration
refusals, 2B/0.8B generation and HTTP/SSE owners. Same-width old/new captures
at 128/256/512 have zero difference across 71,516,160 floats; seven graphs have
588 identical full resident-state hashes. Cross-width differences remain
separate. Default-1/explicit-0 qualification also passes. Metal peak allocation
is unchanged; nonfinal MUL_MAT falls 187 -> 181 with all state writes retained.

Measured: five alternating worker old/new/pinned-llama groups and same-binary
HTTP/SSE OFF/ON pairs, all samples retained. At 700/64 paired median request
improvements are 2.44% HTTP, 1.45% SSE, first-token 4.78%, all five pairs positive.
1536/1 improves 6.12% HTTP and 5.21% SSE. Worker 330/64 is slower; 200/32 SSE
has a slower marginal median despite a positive paired median. Desktop activity
is material. Adopt for the qualified long-input benefit, exact output/state,
unchanged allocation and low maintenance cost; no universal gain or llama win.

Actual-weight/activation native Q6_K paired-load experiment is complete: full
vocabulary and 257-row-tail checks are exact, but every five-pair range crosses
zero. Keep the independent probe/evidence, do not integrate this kernel.
Implementation/evidence checkpoint `1920cb04` received one fresh independent
comprehensive review: CLEAN, findings none. Source/artifact identities, all
paired statistics and complete state-plane records were independently checked;
the review envelope is retained in the resolved Git common directory. The local
checkpoint is complete; no publication or merge is claimed. No new Align gap.

Next native work: attribute the Q6_K output projection inside real-model decode
and calibrate attainable device-read bandwidth before a different work/layout
mapping; alternatively test bounded tiled gate/up/SiLU/down fusion. Neither is
implemented. Synchronous-upload memory-pressure qualification remains deferred;
this trial fixes upload to legacy. CPU/CUDA Qwen3.5 and Gemma semantic admission
remain deferred under existing restrictions. Older sections below retain their
historical next actions and decisions; this section owns current execution state.

## Synchronous upload / prefill checkpoint (2026-09-26)

Branch `agent/native-metal-ffn-integration`, baseline `4f56f410`. Implemented
independently selectable synchronous weight upload and 128/256/512 prefill.
Defaults remain legacy (`0`/`128`). Align owns policy, loading and graph/state
control; ggml owns buffers and kernels. No mmap, changed weights or Python
product dependency. Read `docs/shared-upload-prefill-trial.md` and its raw
receipt before resuming. All intentional changes belong to this local trial.

Completed: managed build, formatting, strict Python boundary, device cleanup/
allocation faults, direct upload bounds/failure/isolation owner, real 512/513
attention owner, 2B defaults/direct generation, 2B/0.8B combined generation and
HTTP/SSE, 0.8B direct/256 generation, invalid environment refusal, and a private
Metal legacy/direct 31/3 compatibility check. Direct upload equals all 134 raw
logit vectors; batch/combined equal 128 token-aligned vectors across repeated
64/16, 200/32, 700/64, 64/16 requests, maximum difference zero. Six versus one
nonfinal prefill vectors occur at different positions and remain retained.

Measured: startup improves in all 15 alternating pairs, workload medians about
1.00–1.08 s -> 0.49–0.58 s. Pre-first-graph Metal commands fall 1369 -> 1 and
actual shim disassembly confirms the direct branch. Warm inference improvement
is not established. Batch-only 200/32 shows a small mixed result; the 330/64
campaign has a slower median. Combined 700/64 is slower in 4/5 HTTP and 3/5 SSE
pairs. Desktop activity is material; no samples were excluded.

Metal resource maxima are equal for legacy/direct at 200/32 (1,290,174,464 bytes),
but OS footprint at 700/16 is 147.1M versus 1.3G after CPU initialization. Do not
infer equal system RAM pressure from the allocation count. Both knobs stay
experimental; the result is a startup improvement, not a decode victory.

Next: qualify CPU/GPU shared-page residency/accounting under memory pressure;
then skip unused nonfinal-prefill vocabulary projections/readbacks while retaining
all recurrent/KV updates; continue actual Q6_K output-projection/whole-FFN decode
attribution. These follow-ons are not implemented. CPU/CUDA native Qwen3.5 and
full private-Metal qualification remain deferred. Request 122 records the
non-blocking imported-constant initializer gap; direct references work.

The local implementation/evidence checkpoint is `b7ef9bd2`. One fresh comprehensive
review found one P2 in the independent HTTP measurement tool: empty cases could
report COMPLETE. Accepted and repaired with upfront list/pair validation and
`test-host-reuse-config` (18 refusals plus default/recorded acceptance). Runtime
code and the valid measured campaign are unchanged; strict Python boundary and
diff checks pass. Review envelope and finding disposition are retained in the
resolved Git common directory. No valid finding remains unresolved. The local
checkpoint is complete; no publication or merge claimed.

## Retained host-work checkpoint (2026-09-26)

Branch `agent/native-metal-ffn-integration`, implementation/evidence `a00052d6`,
baseline `6124e90b`.
Implemented exact decode-key reuse by parity/attention width and per-session
stream scalar/position/mask/logits scratch. No math, state-reset, device-command
or synchronization change. Added independent HTTP/SSE measurement and host/Metal
trace tools. Read `docs/host-reuse-diagnosis.md` and its raw receipt before work.

Verification: `gmake build`, `gmake fmt`, strict Python boundary, and both
`run-qwen35-generation-smoke` / `run-openai-serving-smoke` on 2B and 0.8B pass.
Old/new worker, HTTP/SSE and diagnostic outputs agree exactly. Decode crosses
width 256 and repeated requests return from width 512 to 256. Binary and call
traces confirm removed key allocations/copies and stream logits zero filling.

Result: 200/32 outside-graph median 20.96 -> 17.97 ms; all five paired outside-
graph reductions are positive, but whole-request improvement is unestablished.
HTTP 200/64 SSE is slower in all five pairs (paired median -0.17%); retain this
regression observation before publication/adoption. Per-decode GPU command-buffer
union is 27.69 ms within a 28.33 ms graph call on the new binary. This does not
identify individual shader time or memory stalls. Retain as local lower-host-work
implementation, not a throughput win; native FFN fusion remains default-off.

One fresh independent comprehensive review of `a00052d6` against `6124e90b`
completed CLEAN, findings none; no repair was needed. Its envelope is retained
in the resolved Git common directory under `reviews/host-reuse-a00052d6.json`.

Completed pinned llama.cpp binary follow-up: inspected actual driver/libllama/
Metal host assembly and runtime paths. Mapped weights avoid Align's upload
sequence; reference prefill uses one 200-token batch versus Align 128+72.
`llama_decode` returns asynchronously and waits in `llama_get_logits`; complete
readiness is about 27.06 ms, not the 1.38 ms decode return. GPU interval union
is 26.42 ms versus Align 27.80 ms in diagnostic runs; no shader-level causal
claim. See `docs/llama-binary-comparison.md`; local raw diagnostics reside in the
resolved Git common directory under `diagnostics/llama-binary-2026-09-26`.

Next: controlled larger-prefill-batch trial; separately mapped/host-visible
weight loading and cold/warm first use; then real Q6_K output-projection/whole-
FFN attribution of the remaining decode GPU gap. Do not
repeat host tweaks or launch-size sweeps without new evidence. Request 121 records
the non-blocking resource/sibling-view compiler limitation. CPU/CUDA native
Qwen3.5 and Gemma semantic admission remain deferred under existing restrictions.
This local checkpoint is complete; no unfinished implementation or unrelated
files remain. No publication or merge claimed.

## Active native FFN integration (2026-09-26)

Branch: `agent/native-metal-ffn-integration`, based on `ca609a41`; initial implementation
and measurements at `d2319d03`, follow-up at `33e0e444`.
The merged synthetic FFN probe is the starting point. The current inference
policy in `docs/specs/gpu-runtime-performance.md` withdraws all fixed improvement
floors and permits real-model trial integration before whole-request evidence.
Earlier handoff sections below are historical, including their old next actions.

Completed: default-off native Q4_0 gate/up/SiLU integration, actual GGUF weights
and activation checks, 2B/0.8B generation owners, longer repeated requests, and
five-pair local and real-request measurements. Align retains model/session/graph
control; ggml retains allocation, command encoding and other operations.

Decision: experimental only. Same-binary/bundle OFF/ON request medians (ms) are
624.04/620.60 for 64/16 tokens, 1354.77/1399.52 for 200/32, and
2493.16/2491.26 for 330/64. Every paired range crosses zero. No repeatable
request improvement or faster-than-llama.cpp claim is established.
See `docs/native-swiglu-trial.md` and its checked-in raw receipt for exact pinned
comparisons, local results, limits and reproduction.

Durable verification: `gmake build`, `gmake fmt`,
`scripts/run-layer-forward-smoke`, native-enabled
`scripts/run-qwen35-generation-smoke` (2B and 0.8B),
`python3 scripts/check-python-boundary --strict`,
`python3 scripts/measure-cuda-optimization --self-test-portable`, and
`python3 scripts/run-gpu-session-measurement-smoke` pass. Actual-weight checks
cover 72 tensors; local checks cover all 24 FFNs and an alternate shape/alias
fallback. 261 full logit vectors pass the unchanged 0.01 absolute bound with
identical greedy argmax; longer/repeated request outputs match exactly.
The full CUDA self-test requires Linux `/proc` and was not qualified on macOS.

One fresh independent comprehensive review of `d2319d03` against `ca609a41`
completed CLEAN, findings none. No content repair was needed.

Completed follow-up: four independent Q4_0 partial sums at 128 threads, plus a
separate 64-thread probe. Four five-pair, three-workload request campaigns do not
establish repeatable speedup. Retain four sums/128 threads as default-off for its
reference-like reduction and zero observed numerical differences; withdraw 64.
The original native bundle and both follow-up variants remain replayable.

Follow-up verification: all 24 captured FFNs, alternate shape and alias checks,
2B/0.8B generation owners, 261 full-logit vectors (maximum difference zero),
48 real decode fusions, and strict Python boundary pass. Measurement tools now
support explicit old-native comparison with `--native-control`. See
`docs/native-swiglu-followup.md` and its raw receipt. Desktop activity limits
small-effect interpretation; no timing samples were removed.

Research expanded to Reddit, Stack Overflow, upstream PRs and Apple guidance.
The IQ3_XXS narrow-row idle-lane fix does not apply to this Q4_0 width-2048 path.
Next: measure the Q6_K full-vocabulary projection with real final activations and
try its load/work mapping; then a tiled gate/up/SiLU/down consumer with bounded
partial-output reduction. Neither is implemented. Do not continue launch-size
sweeps without a new concrete hypothesis. The follow-up at `33e0e444` received
one fresh independent comprehensive CLEAN review against `b1d24207`, findings
none; no repair was needed.
CPU/CUDA fusion and Gemma semantic admission remain explicitly deferred until
a useful Metal specialization is demonstrated. Existing fallbacks remain.
All current changes belong to this capability; no unrelated work was present.
No publication/preflight or merge is claimed at this local checkpoint.

## Historical checkpoints

Earlier next-action and percentage-floor wording below records its dated
checkpoint only. Current work and decisions use the topmost active checkpoint
and the no-fixed-floor policy in `docs/specs/gpu-runtime-performance.md`.

## Active fused Metal FFN probe (2026-09-25)

Branch: `agent/qwen35-metal-fusion-next`, based on merged `main` `ec34abac`
(#302). The root `main` worktree's unrelated `docs/align-requests.md` edit
remains untouched. A standalone native Metal Q4_0 Qwen3.5-2B FFN probe now
fuses gate/up/SwiGLU and computes down with a second dispatch. Both outputs
match pinned ggml/Metal within `1.2e-5` absolute error on deterministic
synthetic inputs. Three five-pair 128-threadgroup runs on Apple M1 measured
isolated full-FFN ggml/native medians of 1.0777/0.9728, 1.0756/1.0137,
and 1.0661/0.9457 ms, with 14/15 native wins. This is not a whole-request
result. The code and exact limits are in `scripts/bench-metal-q4-ffn.mm` and
`docs/specs/qwen35-text.md`.

Historical next action, superseded by the current policy: integrate a
reversible real-model fused GPU seam after local validation, then check exact
output and request timing without a fixed percentage floor. CPU/CUDA 2B and
large models remain deferred.

## Qwen3.5 2B operation-level diagnosis (2026-09-25)

Branch: `agent/qwen35-next` at merged `main` `7c42bb44`. The 2B adoption and
five-pair same-pin baseline merged in #300; the local OpenAI-compatible chat
guide merged in #301. The baseline was Align 1355.28 ms versus pinned
llama.cpp 1306.84 ms for a 200-token prompt and 32-token output on Apple M1,
with Align slower in all five pairs. Instrumented graph medians were
1307.37/1253.79 ms. No faster-than-llama.cpp claim is active. The root `main`
worktree's unrelated `docs/align-requests.md` edit remains untouched.

The pinned Metal decode debug graphs have the same 187 `MUL_MAT`, 18
`GATED_DELTA_NET`, 18 `SSM_CONV`, and six `FLASH_ATTN_EXT` nodes; all matrix
product weight types/shapes and F32 input shapes/strides match. Flash Attention
uses head-major K/V strides `[2,512,1179648]` in Align and token-major
`[2,1024,512]` in llama.cpp, selecting `ns10/ns20=256` and `512` kernel
specializations respectively. A disposable six-attention pinned-Metal graph
with the two exact layouts and identical output measured five alternating
20-invocation pairs: median 0.524/0.540 ms (head/token), three head-major wins.
This isolated result does not account for the approximately 54 ms complete
graph gap. The Metal SSM batch specialization `128`/`256` arises from Align's
128-token versus llama.cpp's 200-token prefill; both use the same unbatched
SSM kernel during decode. Concurrency-disabled paired diagnostics preserved
output but varied with host conditions: Align default won four of five paired
graph timings (median paired advantage 19 ms), while llama.cpp default won
only two of five. They do not identify a single causal operation. An eight
command-buffer llama.cpp probe changed output and timing drastically, so its
split trace is invalid. Apple M1 exposes stage-boundary GPU counters but not
dispatch-boundary counters; existing Xcode traces have no shader rows.

The user requested a direct GPU implementation probe. A standalone native
Metal Q4_0 matvec benchmark now compares its independent compute path with
the pinned ggml/Metal reference on three 2B decode shapes. One full-output
check per shape passed after warm-up. Five pairs of 20 synchronized
invocations per shape measured ggml/native medians of 0.5160/0.6286 ms
(`[2048,6144]`),
0.4752/0.6071 ms (`[6144,2048]`), and 0.3246/0.3520 ms (`[2048,2048]`)
on Apple M1. Native lost all 15 timing pairs. The reproducible source and
measurement limits are in `scripts/bench-metal-q4-matvec.mm` and
`docs/specs/qwen35-text.md`. One comprehensive Codex review found an
overstated output-check count in the documentation; the record now states the
actual one full-output check per shape. This is a developer benchmark, not an
executable runtime candidate.

Next: run the executable pre-publication classifier with the standalone
benchmark as owner, then publish and merge the developer benchmark. A production custom
GPU seam would still need a winning kernel, exact end-to-end output owner,
and paired real-request evidence under the current policy. Do not ship a K/V layout, mask-copy, or
concurrency change from node counts alone. CPU/CUDA 2B qualification and
large models remain deferred.

## Completed Qwen3.5 dense-model checkpoint (2026-09-24)

Branch: `agent/qwen35-dense-next`, based on merged PR #299 (`35bdd024`).
The 0.8B loopback OpenAI-compatible chat endpoint, including token-yield SSE,
merged in #299. All three hosted checks and final-head preflight passed at
`cf464f60`; the real owner checked two-turn output against pinned llama.cpp,
usage, streaming, refusals, disconnect recovery, and restart. Align Request 120
tracks bounded inbound HTTP receive in [issue #1171](https://github.com/sanohiro/align/issues/1171).
The root `main` worktree's unrelated uncommitted `docs/align-requests.md`
remains untouched.

The next consumer is Qwen3.5 dense 2B Q4_0 native text. The source selected for
local evaluation is `unsloth/Qwen3.5-2B-GGUF` at Hugging Face commit
`f6d5376be1edb4d416d56da11e5397a961aca8ae`, member
`Qwen3.5-2B-Q4_0.gguf` (1,214,873,856 bytes; upstream SHA-256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`).
The complete local file matches that SHA-256 and remains outside Git. The official Qwen text configuration
has 24 layers, hidden width 2048, eight attention heads, two KV heads, head
width 256, FFN width 6144, and one full-attention layer every four blocks.
The complete Model IR, pack and byte-identical pack verification passed. Keep
weights and generated packs outside Git.
The first bartowski Q4_0 candidate had 25 blocks including MTP and the text
frontend refused it. The complete Unsloth file reports 24 layers, 50 blocks,
248,320 tokens, all 320 tensors assigned, and a valid source-bound pack.
Its embedded chat template differs from the official one only in the tool-call
branch; the second exact hash is admitted for text-only conversations.

The 2B tokenizer, five prompt cases, two history cases, three native generation
cases and six retained requests pass against pinned llama.cpp. Real HTTP normal
and SSE replies, refusal, disconnect recovery and restart also pass. Five
alternating 200-prompt/32-output pairs on Apple M1 produced identical text;
Align/llama.cpp medians were 1355.28/1306.84 ms, with five Align losses. An
interposed repeat gave 1307.37/1253.79 ms graph medians, split approximately
396.15/375.64 ms prefill and 911.34/878.15 ms decode. No kernel-level cause
or faster-than-llama.cpp claim is established.

Next performance action: investigate a specific same-pin 2B graph operation
before trying a bounded optimization. Keep 27B, 35B MoE and 9B deferred.
CPU and CUDA 2B qualification remain unmeasured on this host.

Durable verification: real 2B Model IR, pack and pack-verify PASS;
`scripts/run-qwen35-tokenizer-smoke` PASS on 2B;
`scripts/run-qwen35-generation-smoke` PASS on 2B;
`scripts/run-openai-serving-smoke` PASS on 2B and regression 0.8B;
`python3 scripts/check-python-boundary` PASS before the latest owner repair.
Final-head publication preflight, comprehensive review, and hosted checks
passed; #300 merged as `c0b30c61`.

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

Original branch: `agent/linux-real-ggml-qualifications`, based on `main`
`6149e993`, merged in PR #291. The focused profile A/B was run from an
isolated checkout of that same source; its result is recorded on
`agent/request103-linux-profile-disposition` for publication.
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
- A bounded prompt-3, k=16 dev/release A/B on the same `6149e993` source,
  Align `d9b0df32`, GGUF, transcript, pack and ggml object reproduces the
  15741/4149 prefill/decode argmax split in both profiles. Both profiles have
  identical decode hashes, identical prefill hashes and identical f32 bits at
  logits 15741 and 4149 within each path. The Linux discrepancy does not
  depend on Align's dev-versus-release optimization setting. No full owner
  pass or scalar-ABI attribution follows from this focused comparison.

Next actions in priority order:
1. Diagnose the dense C' disagreement at k=1 with one bounded prefill/decode
   comparison, then classify it as ggml numeric behavior or a client defect.
2. Publish the focused Linux A/B and Request 103 state in the reviewed
   documentation PR. Align issue #1075 has the complete data and owns the
   provider disposition. If a concrete correction changes the consumer
   boundary, repeat its affected owner once at the merged pin.

Latest durable verification:
- `scripts/align-toolchain verify`: PASS at `d9b0df32`.
- `make build`: PASS, `main` SHA-256
  `2dab916e8871f1d78a1d540d7a4529a65380331de55768c5954d73c9b9fe0f43`.
- `scripts/run-decode-step`: FAIL only C' at all 12 named checkpoints.
- `scripts/run-moe-decode-step`: FAIL C' at prompt 3 k=16; prompts 1 and 2 PASS.
- `ALIGN_LLM_MOE_DECODE_STEP_PROMPTS=1 scripts/run-moe-decode-step`: PASS at
  16 steps with the timing and library-identity repairs, including MRD.
- Focused prompt-3 k=16 `ggml-spike` dev/release A/B: both builds PASS their
  decode and single-shot prefill invocations; both reproduce C' argmax
  15741/4149 with byte-identical hashes and named logit bits across profiles.
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
