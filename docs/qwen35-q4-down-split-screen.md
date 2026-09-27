# Independent Metal Q4_0 down split-K screen

## Decision

Withdraw the tested two/four-way hidden-axis split-K mappings. They pass the
predeclared numerical check on actual Qwen3.5-2B down projections, but neither
beats the independent unsplit four-row kernel on the measured Apple M1. The
unsplit kernel itself beat pinned ggml's isolated down operation in 19/20 paired
wall comparisons across two runs and two captured layers. That local result
warrants testing an independent **complete FFN** command with gate/up/SiLU and
unsplit down together, avoiding an extra ggml-to-Metal boundary. It is not a
real-model request speed claim or a shipping decision. The production graph
and existing selectable native routes remain unchanged.

## Boundary and correctness

The [probe](../scripts/bench-metal-q4-down-split.mm) reads the unchanged GGUF's
captured F32 gated vector and Q4_0 down weights for layers 3 and 23, each
`[6144,2048]` with 7,077,888 weight bytes. It independently rebuilds the
pinned ggml Metal down graph and requires its entire output to match the
captured output byte for byte. Each native arm has its own exact-weight shared
Metal buffer and one upload before timing; no timed operation uploads weights,
reads output on the CPU, or recomputes gate/up. The unsplit arm uses one
dispatch; the split arms write 16/32 KiB of partials and reduce them in a
second dispatch with an explicit buffer barrier. Output storage is 8 KiB. The
local A/B process holds separate buffers for fairer cache comparison; a runtime
would keep only its selected arm.

The declared local bound was `0.005 + 0.0005 * abs(ggml output)`. All values
were finite. Maximum absolute differences on layer 3 were `3.53903e-8`,
`3.72529e-8`, and `3.91155e-8` for one/two/four splits; on layer 23 all three
were `2.38419e-7`. A synthetic `[160,64]` Q4_0 case checks nonmultiple split
partitions and a split with no assigned blocks; its maximum difference was
`1.86265e-7`. Twenty additional untimed reused commands per arm were checked
one by one, and each timed pair's final output was checked outside its clock.
No tolerance was changed. Layers 0–2 use Q4_1 down and are outside this screen.

## Paired local timing

Apple M1, macOS 27.0, pinned ggml
`bb4caa7540188872173c44d161602d9271386413`, plugin SHA256
`a901a131109e42de39919c74562947ad8783b32d63c2ce88be13e9812b07fdf5`.
The captured weights/input are from the unchanged 2B GGUF with SHA256
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
The source SHA256 is
`3aaea226998f77d30d41d324dcb983021bceddd8160c164450381eabfee48bef`.
The exact capture hashes and preceding weight-identity validation are in the
[tile FFN receipt](../eval/benchmarks/qwen35-native-q4-tile-ffn-2026-09-28.json);
this screen also checks every captured size and rebuilt output at run time.

Each arm ran twelve warmups. Each of two process runs then measured five
alternating pairs of twenty synchronized complete down operations per arm.
Positive paired `control - candidate` favors the candidate. Raw
[run D](../eval/benchmarks/qwen35-q4-down-split-2026-09-28-d.txt) and
[run E](../eval/benchmarks/qwen35-q4-down-split-2026-09-28-e.txt) retain every
pair, GPU command interval, setup time and correctness check. GPU intervals
include both dispatches for split arms; ggml GPU intervals were not available.

| Layer / comparison | D paired median ms | E paired median ms | Candidate wall wins | Candidate GPU wins |
| --- | ---: | ---: | ---: | ---: |
| 3: ggml vs unsplit | +0.0139 | +0.0199 | 9/10 | N/A |
| 23: ggml vs unsplit | +0.0597 | +0.0362 | 10/10 | N/A |
| 3: unsplit vs split 2 | -0.0024 | -0.0116 | 3/10 | 5/10 |
| 23: unsplit vs split 2 | -0.0127 | -0.0205 | 1/10 | 1/10 |
| 3: unsplit vs split 4 | -0.0220 | -0.0291 | 0/10 | 0/10 |
| 23: unsplit vs split 4 | -0.0257 | -0.0270 | 2/10 | 2/10 |

The unsplit GPU command medians were about `0.211–0.226 ms`; split 2 was
`0.221–0.239 ms`, and split 4 `0.233–0.236 ms` in the direct native pairs.
These command intervals are not isolated shader clocks or hardware counters.
The extra dispatch, partial write/read and changed work mapping together cost
more than the exposed split parallelism saved on this M1; the experiment does
not identify which of those costs dominates. The ggml-versus-split wall
comparisons were mixed for layer 3 and often favored split on layer 23, but
the unsplit native mapping was the stronger local candidate. Warm setup clocks
vary with library and pipeline caches and are not comparable cold-start
numbers. Full request, prefill, whole decode, startup/load, total device memory,
and pinned llama.cpp were not measured for this rejected split mapping.

## Next experiment

Use the unsplit down kernel after a native gate/up/SiLU producer in one Metal
command, with the gated vector resident and a necessary buffer barrier.
Compare the complete FFN with the unchanged pinned ggml graph on actual
captured layers before an opt-in real-model route. If it wins locally, Align
must own selection, graph boundaries and state publication; the runtime trial
must measure the connection cost and real 2B/0.8B requests. Another Qwen size
needs its actual shape/quantization, and Gemma needs activation and graph
semantics qualified separately. CUDA requires a separate implementation.

Reproduce this screen with:

```sh
GGML_INCLUDE=... GGML_BUNDLE=... CAPTURE_DIR=... \
  scripts/run-native-q4-down-split-screen
```

`CAPTURE_DIR` is local development data, not part of the repository.
