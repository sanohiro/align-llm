# Final CUDA correctness and performance run

Run this after the Metal campaign and final handoff pull request have merged. It is one sequential
run against the retained CUDA kit from [issue #218](https://github.com/sanohiro/align-llm/issues/218).
Keep the old failed evidence unchanged. The new output directory must not already exist and must
be outside the source checkout. Both original GGUF files and the kit's pack/geometry/backend files
must remain at the paths named by its profile.

On the recorded Pengwin / Debian 13 WSL2 host, CUDA 13.3 and Ninja are already installed. Use the
installed system CMake and explicitly expose the CUDA toolkit in this noninteractive shell:

```sh
git switch main
git pull --ff-only
export PATH=/usr/local/cuda-13.3/bin:/usr/bin:$PATH
python3 scripts/run-gpu-final-validation \
  --profile "$CUDA_KIT/profile.json" \
  --output "$HOME/gpu-final-cuda-result"
```

`CUDA_KIT` is the existing kit directory used for issue #218. The wrapper admits its actual GPU
bundle and both model identities before starting. The profile must admit at least 1 GiB of host
capacity and 6 GB of device capacity; the measurement writes those fixed ceilings into its new
owned options file. It does not modify the retained kit. Optional `--same-source` and
`--current-source` arguments reuse clean upstream checkouts at the two exact commits named in
`docs/specs/gpu-runtime-performance.md` §6.1; otherwise the wrapper fetches them automatically.
No weights are downloaded.

The wrapper builds the managed pinned runtime, independent reference and two ordinary upstream
servers. It then acquires and seals all 19 backend-local expectations independently, runs full
G1 tensor/capacity acceptance and relocated evidence replay, checks G1R serial requests, host
capacity and actual coding retries, and runs the frozen five-repeat performance campaign. The
corpus preparation runs before the candidate and is not itself a correctness verdict. The original
CPU/CUDA diagnostic failures remain historical FAILs; they are not replaced by this preparation.

Keep other GPU workloads and local builds idle during the run. Its complete ceiling is eight hours,
including at most three hours for source/build preparation. Individual phases have tighter limits.
The console reports phase starts and completions; `result.json` and `logs/` retain progress and
failure details. A failed phase stops subsequent verification and timing. Do not reuse a partial
output directory for a retry.

The final `result.json` links and hashes each required receipt. Its PASS means execution and required
correctness owners completed; performance decisions are separately recorded in
`measurement/result.json`. Each model, request case and baseline has its own result. Runtime quality
failure makes that comparison invalid, and a missed 15% median reduction is not a speedup claim.
The coding portfolio is one fixed task and does not establish the broader G6 coding-performance gate.
Cold latency means a fresh process/session, not a flushed operating-system file cache.

Retain the entire result directory on the CUDA host. Share the final receipt and measurement receipt
with the issue so correctness, missing evidence and performance can be assessed together. Actual
CUDA graph capture is not proven by build flags alone. Stop here before further implementation;
the user wants to discuss the next direction after this handoff.

The Metal preparation owner completed all 19 independent acquisitions in 215.973 seconds and exactly reproduced the complete checked-in corpus `29bfe85d85aca082e9a841eb394300dc0a4b02750db8fd816eb6908fdc962b73`. This validates backend preparation without deriving expectations from the candidate. Model-free final orchestration tests cover ordered invocation, failure short-circuiting, relocated replay and terminal receipt checks; the combined CUDA execution remains pending on its actual host.
