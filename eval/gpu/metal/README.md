# Frozen Metal generation inputs

These schema-1 calibrations bind the local Q4_K_M Qwen2.5-Coder-7B and OLMoE-1B-7B reference
models, their exact packs/geometries, and the pinned Apple M1 Metal bundle. They contain actual
CPU prompt IDs, sampled IDs and output bytes from `runtime_calibration_seed`, with an empty system
prompt, greedy sampling and two maximum output tokens. OLMoE uses a 268435456-byte expert cache;
Qwen uses zero. The calibration and holdout prompts differ for each model.

The static CPU reference uses Align `305926b423da9be1f13b0129a7232626e6704d95`, ggml
`bb4caa7540188872173c44d161602d9271386413` and the checked-in CPU-reference build recipe. Its full
Align source bytes match the `src/` tree at `1e6a1bb`; the production trace driver returns the
recorded values directly. The corresponding CPU repetitions must reproduce them during final
qualification with that profile's actual same-build reference.

Absolute and relative tolerances are the binary32 encoding of 0.001; routing near-tie tolerance
is the binary32 encoding of 0.00001. These were selected before any GPU calibration or holdout
execution and are not observed error maxima. Do not enlarge them after a failed holdout. These
inputs alone do not establish numerical agreement, GPU placement, repeatability or qualification
PASS. The complete public qualifier and its replayed evidence own those claims.
