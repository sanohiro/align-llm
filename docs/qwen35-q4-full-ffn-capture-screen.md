# Independent Metal Q4_0 complete-FFN capture screen

## Decision

Continue the independent Metal backend with an execution plan that can submit
dependent GPU work without an intermediate CPU wait. The native two-dispatch
gate/up/SiLU/down command passed actual captured Qwen3.5-2B intermediate and
final output checks and beat the unmodified pinned ggml complete FFN in all
20 paired local comparisons across two layers and runs. Its paired median
advantage was `0.039–0.069 ms` per FFN. Separating those same kernels into two
commands with a CPU wait between them added `0.313–0.382 ms`; submitting both
on one queue and waiting only after down added `0.014–0.043 ms`. The latter is
near the entire local compute gain, so no request-speed claim or production
adoption follows. The production graph and selectable native routes are
unchanged.

## Tested work and correctness

The independent [Metal probe](../scripts/bench-metal-q4-full-ffn-capture.mm)
uses unchanged Q4_0 gate/up/down weights from real 2B layers 3 and 23, each
7,077,888 bytes, and the captured first-decode F32 input. Its gate/up kernel
computes the Qwen SiLU gate and writes one 24 KiB gated vector. An explicit
Metal buffer barrier precedes the unsplit Q4_0 down kernel when both run in
one command; that kernel writes one 8 KiB result. The pinned ggml Metal graph
independently rebuilds `gate`, `up`, `swiglu_split`, and `down` and its complete
gated/final vectors match the captures byte for byte. Native weights and input
are uploaded once before timing. The A/B arms own separate exact-weight
buffers. No timed operation copies data between CPU and GPU or reads output on
the CPU.

For the queued two-command arm, both buffers use Metal's default resource
hazard tracking on one command queue. Gate/up is committed before down, and
the host waits on the down command only; it then checks both command statuses
and the full output. Apple's [command-buffer
contract](https://developer.apple.com/documentation/metal/mtlcommandbuffer)
describes same-queue scheduling order, and [resource
fundamentals](https://developer.apple.com/documentation/metal/resource-fundamentals)
describes default hazard tracking. The CPU-wait arm commits gate/up, waits for
completion, then commits and waits for down. These are local command
schedules, not ggml graph partitions.

The numerical bound `0.005 + 0.0005 * abs(ggml reference)` was declared before
this screen. Native maximum absolute gated/final differences were
`2.98023e-7 / 8.9407e-8` for layer 3 and `1.81794e-6 / 7.15256e-7` for
layer 23. All compared values were finite. Twenty additional untimed native
commands per layer were checked one by one, as were the outputs after every
measured pair outside the clock. This is a local numerical bound, not
bit-exact generated-token compatibility. Layers 0–2 have Q4_1 down weights
and are outside this screen.

## Paired local timing

Apple M1, macOS 27.0, pinned ggml
`bb4caa7540188872173c44d161602d9271386413`, Metal plugin SHA256
`a901a131109e42de39919c74562947ad8783b32d63c2ce88be13e9812b07fdf5`,
GGUF SHA256 `cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
Probe source SHA256:
`e3f2092a0ab22226c00ab39d73644f5ca0a34662f5dadb6fd7313a61f746a89e`.
The captured file hashes and weight-identity validation are bound in the
[earlier complete FFN receipt](../eval/benchmarks/qwen35-native-q4-tile-ffn-2026-09-28.json);
this probe verifies every file size and rebuilt ggml output. The
[run H](../eval/benchmarks/qwen35-q4-full-ffn-capture-2026-09-28-h.txt) and
[run I](../eval/benchmarks/qwen35-q4-full-ffn-capture-2026-09-28-i.txt) receipts
retain every sample, setup time, and correctness result.

Twelve warmups per arm preceded each campaign. Each of two process runs
measured five alternating pairs of twenty synchronized operations per arm.
Positive paired `ggml - native` favors native; positive `separate - combined`
is the added command-boundary cost. GPU intervals come from native Metal
command timestamps. The separate GPU interval sums the two command
intervals and excludes the gap; wall clocks include the final completion
wait, and the CPU-wait arm includes its intermediate wait.

| Layer / measure | Run H paired median | Run I paired median | Positive pairs |
| --- | ---: | ---: | ---: |
| 3 gated, ggml minus native | +0.0445 ms | +0.0402 ms | 10/10 |
| 23 gated, ggml minus native | +0.0524 ms | +0.0536 ms | 10/10 |
| 3 complete FFN, ggml minus native | +0.0401 ms | +0.0677 ms | 10/10 |
| 23 complete FFN, ggml minus native | +0.0391 ms | +0.0686 ms | 10/10 |
| 3 separate with CPU wait minus combined | +0.3681 ms | +0.3134 ms | 10/10 |
| 23 separate with CPU wait minus combined | +0.3822 ms | +0.3799 ms | 10/10 |
| 3 queued, final wait only, minus combined | +0.0416 ms | +0.0141 ms | 8/10 |
| 23 queued, final wait only, minus combined | +0.0426 ms | +0.0422 ms | 10/10 |

The combined complete native command's GPU interval medians were
`0.654–0.665 ms` in full-FFN pairs. The queued two-command arm's summed GPU
interval medians were `0.659–0.683 ms`; the CPU-wait arm's were
`0.670–0.677 ms`. Most of the CPU-wait arm's extra wall time is outside the
GPU intervals. The queued arm removes most of that host gap while still
paying for a second command. Warm setup clocks varied with library/pipeline
caches and are not comparable cold-start numbers. The isolated process holds
both ggml and native copies of three 7 MB matrices for A/B measurement; no
model-level peak memory conclusion follows. Prefill, full decode, whole
request, startup/load, pinned llama.cpp and another device were not measured
for this local candidate.

## Next GPU hypothesis

A stand-alone FFN saves tens of microseconds here. An intermediate CPU wait
costs hundreds; ordered queued submission reduces that cost to tens. The next
independent route must keep multiple dependent operations in an Align-owned
Metal schedule, borrow or own the same resident buffers safely, and avoid a
CPU wait at every FFN. This local result does not establish that current ggml
graph execution can be split and queued without waiting. A larger layer/model
execution unit or an explicit asynchronous graph handoff is the relevant
prototype. Before any adoption, it needs actual 2B/0.8B full logits,
recurrent-state and repeated-request checks, plus prefill/decode and complete
request comparisons against unchanged Align and pinned llama.cpp. Qwen sizes
need shape/quantization admission; Gemma requires separate activation,
normalization, attention and position semantics. CUDA requires its own
implementation. The existing ggml route remains the rollback.

Reproduce with the checked-in wrapper and local captured bytes:

```sh
GGML_INCLUDE=... GGML_BUNDLE=... CAPTURE_DIR=... \
  scripts/run-native-q4-full-ffn-capture-screen
```
