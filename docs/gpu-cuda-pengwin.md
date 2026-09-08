# G1 CUDA qualification on Pengwin

The user-reported target is WSL2 / Pengwin 26.02.5 (Debian 13 trixie), kernel
`6.18.33.2-microsoft-standard-WSL2`, x86_64, NVIDIA GeForce RTX 4070 Ti at PCI
`00000000:2D:00.0`, driver `610.62`, compute capability `8.9`. The checked-in CUDA recipe targets
Linux x86_64 and `sm_89`. These facts identify the requested qualification; they are not a PASS.

The initial probe found Python, Git, C/C++ and CMake, but no Ninja or nvcc. OLMoE's Q4_K_M GGUF
is present in the user's model directory. Qwen's location remains unconfirmed. Run preparation
inside Pengwin's Linux filesystem. The qualifier later records actual toolchain and device facts.

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

## Remaining execution

Build the CUDA bundle from ggml commit `bb4caa7540188872173c44d161602d9271386413` using
`scripts/gpu_backend_recipe.py --backend cuda --source CHECKOUT --output NEW_DIRECTORY`.
The read-only `--backend cuda --print-plan` form needs neither path. Then build the pinned Align
compiler/runtime and the same-source static CPU reference, capture the real CPU calibration
outputs, and assemble the complete source/bundle/model input kit through the existing owners.
The profile uses `platform=wsl2` and the exact native registry device, with host observation bound
to PCI `00000000:2D:00.0`. Do not infer the registry device name from the PCI number.

Frozen tolerances and distinct calibration/holdout prompts precede GPU execution. Metal's bundle
ID and calibration IDs cannot be relabeled as CUDA evidence. Run the public qualifier on the
populated CUDA kit and replay its retained result. CUDA preparation and qualification remain
pending until the target executes these steps; Metal evidence cannot close this requirement.
