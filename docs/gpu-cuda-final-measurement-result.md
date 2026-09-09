# Final CUDA speed comparison

The formal §6.2 campaign completed all 30 serial arms in 517.206 seconds.
All 120 runtime responses pass the frozen quality gate with exactly 128 generated tokens.
Every one of the 16 model/case/reference comparisons has a slower candidate paired median;
none clears the precommitted 15% material floor. This completes the requested comparison,
with a measured negative result. No further optimization is started in this handoff.

Qwen passes the coding task in all five portfolios on all three systems, always on attempt 1.
OLMoE fails all five portfolios on all three systems, exhausting eight attempts each. Those
failures remain in the denominator; OLMoE time to a passing patch is unavailable, while its
independently qualified runtime speed comparisons are complete.

## Frozen identities and execution

- Campaign: `577a99f78ac418a1505bc6c0caf4f43410228fd3`, reviewed before execution.
- Qualified runtime: `688232c665aafca3cdff940e9e34eac5c7f0509e`; the repaired manifested `session-scoped/main`, unchanged from PR #223's G1/session/host qualification.
- Same-ggml reference: `bb4caa7540188872173c44d161602d9271386413`, ordinary unmodified `llama-server`, F32 KV.
- Current reference: `304665fe7ac957df95e3ff8c8c4ffdf92dd6ffa3`, ordinary unmodified `llama-server`, F16 KV. “Current” is the frozen campaign revision, not an automatically updated branch.
- RTX 4070 Ti, 12,282 MiB, driver 610.62, CUDA 13.3, sm_89; Ryzen 9 5950X, 32 logical CPUs; Pengwin/WSL2 kernel `6.18.33.2-microsoft-standard-WSL2`, 67,379,048,448 bytes physical host memory reported.
- Original admitted Q4_K_M models, CUDA backend bundle and managed Align revision are unchanged from `gpu-cuda-session-repair.md`. Receipt binds their exact hashes, baseline libraries/CMake caches, actual commands and the host snapshot. Candidate caps: 1 GiB host reservation and 6,000,000,000 bytes GPU.
- Five paired repetitions, fixed rotated order, no overlapping GPU arms or competing compiler/qualification runs. Context 2304, microbatch 128, batch 2048, four baseline CPU threads, Flash Attention on, no startup warmup or context shift.
- New schema-2 receipt: `gpu-cuda-final-measurement-v1/result.json`, SHA-256 `5a4787d0c19ea55b01e7d879ff52a43474d7c5c336e94b8895c96be531414465`. Complete arms, attempts, output text, raw clocks, commands and logs remain outside Git in that directory. All admitted source/executable/input identities recheck successfully.

Exact owner invocation (role paths identify the existing admitted kit and manifested builds):

```sh
scripts/run-gpu-session-measurement --campaign cuda-final \
  --profile "$PROFILE" --runtime "$REPAIRED_SESSION/main" \
  --same-server "$SAME_BASELINE/bin/llama-server" \
  --current-server "$CURRENT_BASELINE/bin/llama-server" \
  --output "$NEW_EXTERNAL_DIRECTORY"
```

`PROFILE` is the retained `cuda-kit-28a6fe3` profile; `REPAIRED_SESSION` is the repaired
`session-scoped` build. Both baseline builds are the original clean builds retained by
`gpu-final-cuda-result-v2`. The real invocation cleared ambient `DOCKER_HOST` and selected
the installed CUDA/system tools on PATH. No model download or build time enters a metric.

## Runtime results

Times below are medians of five internal processing observations, in milliseconds.
Request/response transport and service startup are excluded. Candidate `elapsed_ns` starts after
frame reception and includes request decoding, tokenization, generation and output decoding.
Baseline clocks are the unmodified server's `prompt_ms + predicted_ms`; they exclude HTTP handling
and some preparation. These are producer-reported service clocks with different boundaries,
which can penalize the candidate; they are not pure GPU-kernel or identical-boundary timings.
Do not interpret them as end-to-end latency or an exact transport-subtracted wall clock.

“Cold” means the first request in a fresh, ready service with empty KV state, not model loading.
All prompt/completion counts agree across systems for each named case. Quality is 5/5 for
every system/case. The percentage columns are the median of five paired reductions
`(reference - candidate) / reference`; negative values mean the candidate is slower.
They are not the percentage computed from the displayed medians.

| Model | Case | Input / output tokens | Candidate ms | Same-ggml ms | Current ms | Paired reduction vs same | Paired reduction vs current |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen2 | cold-short | 50 / 128 | 1548.762 | 1465.052 | 1446.000 | -5.71% | -8.02% |
| qwen2 | warm-short-cached | 50 / 128 | 1488.111 | 1437.079 | 1408.882 | -3.88% | -5.66% |
| qwen2 | warm-long-changed | 700 / 128 | 1731.960 | 1651.006 | 1568.989 | -4.92% | -10.77% |
| qwen2 | warm-long-cached | 700 / 128 | 1580.640 | 1508.667 | 1433.837 | -4.94% | -10.40% |
| olmoe | cold-short | 52 / 128 | 975.211 | 500.716 | 447.640 | -89.30% | -107.83% |
| olmoe | warm-short-cached | 52 / 128 | 497.534 | 383.536 | 349.199 | -27.53% | -39.85% |
| olmoe | warm-long-changed | 704 / 128 | 737.811 | 576.224 | 484.653 | -26.85% | -51.90% |
| olmoe | warm-long-cached | 704 / 128 | 641.016 | 496.279 | 390.612 | -29.03% | -64.66% |

## Coding outcomes

Processing time accumulates internal generation and measured native validation through the first
passing patch. It excludes model transport, startup and caller orchestration; native validation
includes its process and filesystem work. This is not wall time to a passing patch. The unchanged
known-good validator control passes. Failed portfolios have null time, rather than a fast failure
being scored as success. This single task cannot establish G6 coding competitiveness.

| Model | System | Successful portfolios | Attempts per portfolio | Median processing to passing patch ms |
| --- | --- | ---: | --- | ---: |
| qwen2 | candidate | 5/5 | 1, 1, 1, 1, 1 | 1065.433 |
| qwen2 | same | 5/5 | 1, 1, 1, 1, 1 | 996.592 |
| qwen2 | current | 5/5 | 1, 1, 1, 1, 1 | 992.357 |
| olmoe | candidate | 0/5 | 8, 8, 8, 8, 8 | N/A — no passing portfolio |
| olmoe | same | 0/5 | 8, 8, 8, 8, 8 | N/A — no passing portfolio |
| olmoe | current | 0/5 | 8, 8, 8, 8, 8 | N/A — no passing portfolio |

Qwen paired processing reductions are -6.91% versus same, -7.49% versus current. OLMoE has no passing pair for either reference.

## Raw runtime observations

Milliseconds in repetition order 0–4; each value uses the same internally reported clock as the
summary above. Exact nanoseconds, full counts and responses are in the digest-bound receipt.

| Model | Case | System | Repetitions 0, 1, 2, 3, 4 (ms) |
| --- | --- | --- | --- |
| qwen2 | cold-short | candidate | 1577.754, 1561.999, 1543.044, 1537.503, 1548.762 |
| qwen2 | cold-short | same | 1473.696, 1463.572, 1468.615, 1462.832, 1465.052 |
| qwen2 | cold-short | current | 1451.931, 1446.000, 1451.551, 1434.978, 1432.701 |
| qwen2 | warm-short-cached | candidate | 1491.035, 1494.081, 1487.360, 1488.111, 1484.500 |
| qwen2 | warm-short-cached | same | 1427.503, 1438.239, 1431.481, 1443.397, 1437.079 |
| qwen2 | warm-short-cached | current | 1410.444, 1419.400, 1407.748, 1401.429, 1408.882 |
| qwen2 | warm-long-changed | candidate | 1727.708, 1775.034, 1732.458, 1731.766, 1731.960 |
| qwen2 | warm-long-changed | same | 1645.156, 1648.969, 1651.217, 1651.700, 1651.006 |
| qwen2 | warm-long-changed | current | 1569.170, 1568.989, 1570.368, 1560.277, 1563.539 |
| qwen2 | warm-long-cached | candidate | 1577.931, 1583.191, 1580.640, 1587.418, 1580.198 |
| qwen2 | warm-long-cached | same | 1509.114, 1508.667, 1503.609, 1513.402, 1498.014 |
| qwen2 | warm-long-cached | current | 1435.018, 1434.035, 1423.230, 1420.147, 1433.837 |
| olmoe | cold-short | candidate | 940.384, 976.900, 975.211, 998.393, 911.647 |
| olmoe | cold-short | same | 496.769, 507.597, 529.807, 486.815, 500.716 |
| olmoe | cold-short | current | 436.481, 470.046, 500.317, 444.402, 447.640 |
| olmoe | warm-short-cached | candidate | 479.096, 500.838, 504.890, 494.798, 497.534 |
| olmoe | warm-short-cached | same | 375.671, 374.934, 399.664, 383.536, 404.694 |
| olmoe | warm-short-cached | current | 343.762, 371.311, 349.199, 353.808, 346.880 |
| olmoe | warm-long-changed | candidate | 726.253, 746.659, 737.825, 737.811, 733.697 |
| olmoe | warm-long-changed | same | 572.540, 559.864, 595.755, 582.448, 576.224 |
| olmoe | warm-long-changed | current | 462.366, 491.531, 487.384, 463.368, 484.653 |
| olmoe | warm-long-cached | candidate | 628.746, 641.016, 638.261, 646.992, 644.223 |
| olmoe | warm-long-cached | same | 487.273, 481.511, 511.260, 496.279, 501.303 |
| olmoe | warm-long-cached | current | 381.835, 390.995, 397.699, 390.612, 385.047 |

## Startup context and verification

Startup is retained separately for operational context; these construction-to-ready wall clocks
include local readiness/protocol overhead and are excluded from every speed decision above.
They are not transport-free metrics. Median milliseconds:

| Model | Candidate | Same-ggml | Current |
| --- | ---: | ---: | ---: |
| qwen2 | 2717.904 | 1214.236 | 1217.031 |
| olmoe | 16483.521 | 913.151 | 914.105 |

- `scripts/run-gpu-session-measurement-smoke`: PASS, including transport/startup clock exclusion, malformed/missing clocks, failed-portfolio retention and original admission/HTTP cleanup owners.
- Real protocol admission on both models against both ordinary baseline servers: 4/4 PASS; internal clocks present. These preparation observations are not campaign samples.
- Fresh comprehensive adversarial review of the harness/plan at the campaign head: APPROVE, no findings. GitHub owns the full review and final integration-check envelope.
- Formal owner: PASS, 30/30 arms, 120/120 runtime quality responses, all identities rechecked. Independent summary recomputation agrees with all 16 paired medians and decisions.

The bounded retrospective is that measurement completion and quality success are distinct:
a failed coding portfolio must remain visible without suppressing valid runtime comparisons.
Keep the existing frozen controls and results; do not retune or start another optimization here.
