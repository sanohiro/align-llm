# CUDA validation result before the performance campaign

The final CUDA run on 2026-09-09 stopped at the independent serial-session correctness gate.
G1 passes all 19 cases, each with two fresh candidate executions, and relocated evidence replay.
G1R passes 13 of 16 requests: Qwen passes 7/7; OLMoE passes 6/9.
**Performance measurement did not start.** There is no CUDA latency comparison, shipping-floor
decision or speedup claim from this run.

## Source and environment

- Tested clean source: `06680249833b46a8c143ee8d076af7bbe3995309` (merged PR #221).
- Managed Align pin: `305926b423da9be1f13b0129a7232626e6704d95`.
- Pengwin / Debian 13, WSL2 `6.18.33.2-microsoft-standard-WSL2`, x86_64.
- AMD Ryzen 9 5950X; NVIDIA GeForce RTX 4070 Ti, 12,282 MiB reported VRAM,
  CUDA0 / sm_89, driver 610.62; CUDA Toolkit 13.3.73.
- Original admitted kit: `cuda-kit-28a6fe3`; model and bundle files unchanged.
- Both frozen upstream servers built successfully: same-ggml
  `bb4caa7540188872173c44d161602d9271386413` and current baseline
  `304665fe7ac957df95e3ff8c8c4ffdf92dd6ffa3`.
- Complete new evidence retained outside Git under `gpu-final-cuda-result-v2`.

## Executed command and receipts

```sh
env -u DOCKER_HOST PATH="/usr/local/cuda-13.3/bin:/usr/bin:$PATH" \
  python3 scripts/run-gpu-final-validation \
  --profile "$HOME/.cache/align-llm/cuda-kit-28a6fe3/profile.json" \
  --output "$HOME/gpu-final-cuda-result-v2"
```

The command exits 1. The ambient Docker endpoint was unreachable; removing `DOCKER_HOST`
selects the working local Docker socket. An earlier invocation was deliberately interrupted
during source preparation to correct that environment, before any correctness or timing run.
Its partial `gpu-final-cuda-result` directory is retained. It is not a failed numerical trial.

| Phase | Result | Execution duration, not a performance comparison |
| --- | --- | ---: |
| Source, toolchain and all six executable builds | PASS | Preparation only |
| Independent CUDA expectation acquisition | PASS, 19 cases | 53.393 s |
| G1 independent tensor/capacity acceptance | PASS, 38 executions; all comparisons bitwise equal; cleanup complete | 851.612 s |
| Relocated G1 replay | PASS, 19 cases | 39.254 s |
| G1R independent serial requests | FAIL, 13/16 | 45.999 s |
| Session host capacity | Not run after failed prerequisite | N/A |
| Actual coding retries | Not run after failed prerequisite | N/A |
| Five-repeat runtime/coding campaign | Not run after failed prerequisite | N/A |

The wrapper's total 4,594.140 seconds includes downloading, building and correctness checks.
It is operational elapsed time, not inference latency or time to a passing patch. As requested,
source downloads and builds are excluded from performance comparisons. The frozen measurement
owner would begin its request/portfolio clocks only after preparation and required correctness
owners; it was never invoked. Request clocks embedded in correctness responses are not a
substitute for the unexecuted paired campaign.

## OLMoE session differences

### Observed request times (diagnostic only)

The user also requested the observed timings. These are single observations from the independent
session correctness run, taken from each candidate response's `elapsed_ns`, not the unexecuted
five-repeat campaign. The clock starts after reading a request frame, includes request decoding,
tokenization, generation and output decoding, and ends before response serialization. It excludes
session construction/model admission, transport, source downloads and builds. The first request
can still include lazy generation setup. No reference latency was recorded by this owner.

| Model | Request (zero-based) | Prompt / completion tokens | Internal request time |
| --- | --- | --- | ---: |
| Qwen | 0: first short request | 33 / 2 | 93.558 ms |
| Qwen | 1: same short request reused | 33 / 2 | 42.226 ms |
| Qwen | 5: long changed prompt | 1936 / 2 | 507.218 ms |
| Qwen | 6: function with explanation | 39 / 127 | 1496.474 ms |
| OLMoE | 0: first short request | 40 / 2 | 429.954 ms |
| OLMoE | 1: same short request reused | 40 / 2 | 17.381 ms |
| OLMoE | 5: long changed prompt, output mismatch | 1944 / 8 | 323.755 ms |
| OLMoE | 6: function with explanation | 47 / 78 | 324.490 ms |

Completion tokens divided by the full internal time for request 6 give about 84.9 token/s for
Qwen and 240.4 token/s for OLMoE. These are descriptive per-request ratios, not isolated decode
throughput, repeatable benchmark estimates or a speedup against either upstream baseline.
Request 6 passes exact output/count comparison for both models; the overall OLMoE session still
fails the three cases below.

### Failed exact comparisons

Request indices below are zero-based, matching `session-evidence/result.json`. All candidate
responses have `status=ok`; the failure is the exact output/count comparison, not a crash or timeout.

| Request | Condition | Candidate | Independent reference |
| --- | --- | --- | --- |
| 5 | Long changed prompt, 1900 repetitions of `hello`, temperature 0; 1944 prompt tokens | `- Beside the first letter of the`, 8 completion tokens | `- Beside the first letter of.`, 8 completion tokens |
| 7 | Python addition function, temperature 0.3, seed 42; 42 prompt tokens | Function wrapped in a Python code fence, 21 completion tokens | Same function without a code fence, 16 completion tokens |
| 8 | Repeat of request 7 within the same session | Same fenced output, 21 completion tokens | Same unfenced output, 16 completion tokens |

The function body in both sampled outputs is `def add_integers(a, b):` followed by
`    return a + b`. The reference records 6, 35 and 41 reused prompt tokens for requests
5, 7 and 8 respectively. All prompt-token counts match. The retained candidate/reference JSON
files and reference input capture the complete serial history; replaying a failing request in
isolation would not reproduce that history.

The failure belongs initially to the application/native session integration or its qualification
boundary. Its root cause is not localized; this evidence does not establish an Align language,
compiler/runtime or standard-library gap. Do not infer that seed differences alone explain it:
request 5 is greedy. Do not relax exact comparison or silently replace failed outputs.

## Evidence identity and next action

| Receipt | SHA-256 |
| --- | --- |
| `result.json` | `c7029a35c9e8e952424670535d9f29b7e052798cad3ac649c4ca8035ef73b3d1` |
| `corpus/result.json` | `b266636f1f9f1d773fbdba758ee72a1f4050905c1cd9e8f54430401499d97a67` |
| `g1-evidence-relocated/result.json` | `b7b461ece344b5257647428178a3f656aa05565de92c0b0213174c649e0acc7e` |
| `session-evidence/result.json` | `404e159049dd6b4809d6ce1563ff390beb2eff2c2470db09b1c6f80b187c76b7` |

The newly acquired backend-local corpus SHA-256 is
`3e22421cd4a9558c44033bfd0275eb50c8c271d9a4ee08436eee96daacc78950`.
The final wrapper leaves its success-only `results` map empty on failure; the individual receipts
above remain available. Historical CPU/CUDA failures and all Metal receipts remain unchanged.

Stop at this result summary, as requested. Before timing can resume, investigate the retained
OLMoE serial cases, resolve their discrepancies under the existing contract, and pass independent
session qualification, host capacity and actual coding retries. A future combined run must use a
new output directory; existing clean frozen upstream source checkouts can be reused through
`--same-source` and `--current-source` to avoid downloading them again.

The bounded retrospective found that the existing failure short-circuit correctly prevented
timing an unqualified session. No new permanent gate or runtime change is warranted by this
measurement attempt alone. This report transfers the result to the primary implementation host;
no runtime repair is included.
