# G1 CUDA qualification on Pengwin

The user-reported target is WSL2 / Pengwin 26.02.5 (Debian 13 trixie), kernel
`6.18.33.2-microsoft-standard-WSL2`, x86_64, NVIDIA GeForce RTX 4070 Ti at PCI
`00000000:2D:00.0`, driver `610.62`, compute capability `8.9`. The checked-in CUDA recipe targets
Linux x86_64 and `sm_89`. These facts identify the requested qualification; they are not a PASS.

The initial missing-tool/model prerequisites have been resolved. The target ran the public
qualifier with both models and CUDA 13.3 / nvcc 13.3.73, as reported in
[issue #218](https://github.com/sanohiro/align-llm/issues/218). Preserve the preparation steps below
for reproducing that environment. The reported result is numerical FAIL, not a missing-tool failure.

## Reported execution evidence

The tested source is `28a6fe382aba2e68f9c5ef1ef9bbd98c7493580b`, now available on
`agent/g1-gpu-generation`. The bundle ID is
`61d557b528275397c81f7a528140199977aa7ef4982d6ae09a90e5f67ace5965`.
The issue reports independent replay of retained result SHA-256
`bf6f6849eed100d3cd27d4fe21dab35e69301ea78468bcc91f0ac10941163f86`.
The complete retained artifact closure remains on Pengwin; the issue contains excerpts and
calibrations, so inspecting it does not constitute another full replay.

Qwen CPU and CUDA produce `Yes.` with IDs `[9454,13]`. Native CUDA observations account for
1,496 GPU model operations, 56 layer executions, zero CPU model operations, and resident weights
and KV. The first GPU calibration case fails COMPUTE/readback with 5,058,161 mismatches among
5,243,392 scalars and maximum absolute difference 120.86090087890625. Nonfinite count is zero;
source/input rechecks and cleanup pass. Later formal cases did not execute.

Supplemental relocated OLMoE binaries produce the expected calibration and holdout text, but
report 1,215,799 / 2,111,728 and 1,286,377 / 2,238,928 scalar mismatches respectively. Each has
472 routing mismatches and zero nonfinite values. These are diagnostics, not formal qualification
evidence, and the observed holdout is no longer unseen data for a redesigned acceptance contract.

Preparation fixes preserve compiler invocation aliases, bind the private linker for GCC, and
quote that linker's path through Ninja and the shell. They do not change runtime arithmetic.
Next localize the first divergent CUDA operation and routing boundary. Preserve all frozen
thresholds and this failure; a passing output string alone does not satisfy G1 numerical acceptance.

## Installed prerequisites

NVIDIA's [Debian installation guide](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html#debian)
lists Debian 13 and its network repository. Its repository publishes `cuda-toolkit-13-3`.
The [WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/) requires the Windows-provided GPU
driver: install the toolkit-only package, never a Linux driver package in WSL.

```sh
sudo apt-get update
sudo apt-get install ninja-build pkg-config libssl-dev libzstd-dev curl ca-certificates
curl -fL https://developer.download.nvidia.com/compute/cuda/repos/debian13/x86_64/cuda-keyring_1.1-1_all.deb \
  -o /tmp/align-cuda-keyring.deb
sudo dpkg -i /tmp/align-cuda-keyring.deb
sudo apt-get update
sudo apt-get install cuda-toolkit-13-3
export PATH=/usr/local/cuda-13.3/bin:$PATH
nvcc --version
ninja --version
```

Keep the CUDA bin directory on the preparation shell's PATH. The bundle recipe records the
installed tools; qualification must admit those same tools. The qualifier requires real static
OpenSSL and Zstandard archives from the installed `pkg-config` directories. Its child processes
use their controlled environment, not ambient CUDA or library-path overrides.

## Model identity

The [official Qwen Q4_K_M file](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/blob/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf)
is the same 4,683,073,536-byte GGUF used by the Metal input. Its SHA-256 is
`509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c`.
The expected OLMoE GGUF SHA-256 is
`4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f`
(4,213,512,192 bytes). Hash the existing files before constructing packs or calibration records.
Do not substitute a different quantization based only on its model name.

## Reproduction and remaining qualification

Build the CUDA bundle from ggml commit `bb4caa7540188872173c44d161602d9271386413` using
`scripts/gpu_backend_recipe.py --backend cuda --source CHECKOUT --output NEW_DIRECTORY`.
The read-only `--backend cuda --print-plan` form needs neither path. Then build the pinned Align
compiler/runtime and the same-source static CPU reference, capture the real CPU calibration
outputs, and assemble the complete source/bundle/model input kit through the existing owners.
The profile uses `platform=wsl2` and the exact native registry device, with host observation bound
to PCI `00000000:2D:00.0`. Do not infer the registry device name from the PCI number.

Frozen tolerances and distinct calibration/holdout prompts precede GPU execution. Metal's bundle
ID and calibration IDs cannot be relabeled as CUDA evidence. Run the public qualifier on the
populated CUDA kit and replay its retained result. Preparation has succeeded on the target; full
passing numerical qualification remains outstanding. Metal evidence cannot close this requirement.
