# First resident Metal campaign result

The frozen campaign completed all 30 arms on Apple M1 / 16 GiB in 2482.387 seconds (41 minutes 22 seconds). Execution and all runtime output-quality checks passed. **None of the 16 runtime comparisons met the shipping floor.** This result does not establish a GPU speedup or close the broader performance roadmap.

Candidate: manifested G1R `12a633d5fe60c3c3f853203c452754a695d908dd`. Campaign: `3b6f200`.
Same-ggml baseline: unmodified `bb4caa7540188872173c44d161602d9271386413`, F32 KV.
Current baseline: unmodified `304665fe7ac957df95e3ff8c8c4ffdf92dd6ffa3`, F16 KV.
Both use the fixed GPU/session settings in `docs/specs/gpu-runtime-performance.md` §6.1.

Median paired latency reduction, five repetitions per cell; negative means the candidate took longer:

| Model / case | Same-ggml | Current upstream |
| --- | ---: | ---: |
| qwen2 / cold-short | -17.52% | -32.18% |
| qwen2 / warm-short-cached | -5.42% | -11.45% |
| qwen2 / warm-long-changed | -5.91% | -24.98% |
| qwen2 / warm-long-cached | -8.17% | -35.23% |
| olmoe / cold-short | -219.70% | -461.77% |
| olmoe / warm-short-cached | 11.48% | -81.38% |
| olmoe / warm-long-changed | -0.47% | -123.18% |
| olmoe / warm-long-cached | -9.74% | -305.63% |

The floor requires at least 15% median reduction and four of five pairs faster, with all output-quality checks passing. OLMoE warm-short-cached improves 11.48% against the same-ggml reference but only three of five pairs are faster; it still fails the fixed floor. Cold means a fresh process/session. Model admission reads the files and the operating-system cache is not flushed; these are not cold-storage latency measurements.

For the single coding task, Qwen passes in all five candidate and reference portfolios. Candidate time to a passing patch is 43.61% longer than same-ggml and 50.81% longer than current upstream by paired medians. OLMoE passes in all five candidate portfolios; both references pass zero of five within eight attempts. Their time-to-passing-patch comparisons are therefore unavailable, not a speedup. Equal seed numbers do not imply identical stochastic samples across these different implementations. This one task is diagnostic and cannot establish the G6 portfolio gate.

The complete retained receipt includes every output, timing, attempt, baseline library/cache digest, host observation and model/bundle identity. Receipt SHA-256: `e5a66bd015b28b61bce43c32600904314a3dc12f33a2cd9f286f37a84121619d`.
Evidence directory label: `g1r-metal-performance-evidence-v1` (retained outside Git). Historical correctness failures remain unchanged.

Reproduction command, using the manifested candidate and ordinary builds from the frozen plan:

```sh
scripts/run-gpu-session-measurement \
  --profile "$METAL_KIT/profile.json" \
  --runtime "$G1R_CANDIDATE/main" \
  --same-server "$SAME_BASELINE/bin/llama-server" \
  --current-server "$CURRENT_BASELINE/bin/llama-server" \
  --output "$NEW_RESULT"
```

The later final-handoff change permits retained profiles with larger capacity ceilings and writes the same fixed 1-GiB/6-GB limits into new measurement options. This Metal profile already used those exact limits; no measured runtime, prompt, schedule or sampling input changes.

The remaining action for this capability is the final combined CUDA run described in [the handoff](gpu-final-cuda.md). Stop at that handoff before further optimization or roadmap implementation, as requested.

Review found that the original receipt omitted the resolved validator identity. It remains unchanged. A separate `validator-supplement.json` binds that receipt to retained container-ID evidence and Docker execution events: immutable image `sha256:33fa9e4446ab1a5ca849c57ea49e2e2e4585488aa1cd4d7b2940801bad84cb54`. The frozen campaign resolves this identity once and reuses it for every portfolio. The retained final OLMoE same-ggml attempt-8 container matches create/start/die/destroy events for that image; event-file SHA-256 is `9a2de5adf66ea85196e24cc31476046609a3c4bab0ba692d06d63938c0a4191e`. This is a transparent historical supplement, not a new timing run. Future receipts directly include the resolved validator identity.
