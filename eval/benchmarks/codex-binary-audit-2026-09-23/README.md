# Codex binary optimization audit, 2026-09-23

This is an independent inspection and measurement record, not a product
implementation or an automatic test gate. The accompanying sources are
one-off validation and measurement fixtures.

## Identity and scope

- Client source: `98bbfff16c94b55e593e01a507612329bdc7c656`.
- Candidate Align: `5c7af9e54108fbe3a7b3d698c96a6dbc2da3e9c3`.
- Reference Align: `d9b0df32a831c165b9b070242e168b3f10c721c7`.
- Host: Apple M1, macOS 27.0 build 26A428, LLVM 22.1.8.
- Full image: ordinary `gmake build`, release/O2, baseline CPU, default runtime
  LTO, no ThinLTO, ordinary static unavailable-engine shim. This supports
  inspection of Align-generated code, not an inference or GPU qualification.
- The retained reference image's SHA-256 matches the earlier documented
  `87da7e83c997d3d25a54878e2c1ed39fe258967214fb11ffe7b3156aed5338ec`.
  `git diff --exit-code 3f1a3cee 98bbfff1 -- src scripts/ggml_shim_stub.c`
  confirms unchanged client/shim sources. This audit reuses that identified
  reference image; it does not claim a new full reference rebuild.

## Results

The reported provider corrections take effect in real client code. One
additional uncached-header path still loses the promised length invariant.

| Observation | Reference `d9b0df32` | Candidate `5c7af9e5` |
| --- | ---: | ---: |
| Calls to Align bodies of at most 8 instructions | 544 | 283 |
| Calls to `ggml_ffi$handle_absent` | 118 | 0 |
| Calls to `runtime_attention$fused` / `cached_f16` | 0 / 0 | 0 / 0 |
| Syntactic nonnegative clamps in Align bodies | 50 | 45 |
| FP SIMD arithmetic/comparison instructions | 4 | 4 |
| `kv_plane.all_zero`, median GB/s | 3.1014 | 38.6365 |
| Greedy, median us/call | 51 | 50 |
| Sampler, median us/call | 234 | 238 |

The scan improves **12.46x** in this kernel measurement; every candidate
sample exceeds the pre-existing 25 GB/s floor. Its full-image function changes
from a 12-instruction scalar loop to a 44-instruction vector implementation
with `ldr q`, `cmtst.16b`, `umaxv.16b` and a scalar tail. The emitted IR has
`<16 x i8>` and no `llvm.smax`; the function-scoped optimization remarks
confirm vectorization. Greater instruction count here implements the faster
vector path. No end-to-end inference or time-to-passing-patch speedup is claimed.

Seven alternating reference/candidate pairs were run for each benchmark after
compilation finished. Both built-in benchmarks use their existing five warmups
and 50 timed iterations (greedy vocabulary 151,936; sampler 152,064, seed 42).
CPU frequency was not pinned. Early greedy/sampler samples drift substantially,
and their respective old/new benchmark executables have identical SHA-256
hashes, so their near-equal medians establish no improvement or regression. The scan
samples are stable and all seven pairs favor the candidate. Exact samples,
binary hashes and the census summaries are in [results.json](results.json).

### Remaining calls and SIMD

The earlier Request 95 aggregate target of fewer than 100 short calls is not
met. Short machine code does not by itself imply a missed promised inlining:

- `slot_ne` (25 calls) and `gpu_observation_state` (13) contain guarded
  control flow; Plan 74 excludes these bodies.
- `alignpack_read$new_counters` (21) and
  `prompt_validation_budget$defaults` (7) construct aggregates, also excluded.
- `layer_qwen2$mf_head_output_slot` (6) references same-unit constants,
  rejected by the interface source-closure policy.
- Slice-bearing extern wrappers such as `slot_nbytes` (24) and
  `graph_select_slot_range` (21) need transfer-summary inspection. A minimal
  equivalent wrapper is retained while its raw-pointer counterpart inlines;
  inspecting its checked HIR yields `parallel_transfer=Roots { params: [0],
  captures: [] }`, an explicit Plan 74 exclusion. This is not evidence that
  policy-v3 terminal `unsafe` wrappers are still broken.

The measured named wrapper defect is repaired. The remainder is a mixture
of admitted-policy limits and unclassified sites, not 283 proven compiler
defects. A future compiler-owned scope extension would need authenticated
constant/transfer closure and dedicated positive and refusal tests; no
unshipped surface is consumed here.

The greedy IR already has `<4 x float>` comparisons and index selection.
The sampler remains scalar with ordered top-40 insertion, fallible exits and
array mutation. Those semantics require separate analysis before calling its
scalar shape an optimization defect. The range omission below is independently
demonstrated; it does not explain every remaining sampler cost.

The fixed-table functions `layer_qwen2$mf_decode_layer_node_table` and
`layer_olmoe$mm_table` have no direct dynamic-array builder or allocator call.
The former has no calls; the latter calls its row helper, bounds failure,
`bzero` and `memset`. This is static local evidence, not transitive allocation
measurement or completion of the separate real-ggml qualification.

### Census correction

The previously recorded clamp count of 13 does not reproduce for the exact
identified reference image. The checked-in predicate gives **50 -> 45** on
the two images. This supersedes 13 for this comparison; the historic 351
baseline was not revalidated and is not used for a speedup claim. A syntactic
clamp count does not establish that every remaining clamp is a view-length
bug. The named scan and the residual below have direct IR evidence.

## Verification and remaining scope

- `scripts/align-toolchain verify`: PASS for the managed candidate.
- `gmake check`: PASS, 155 per-unit checks at the preparation checkpoint.
- `gmake build`: PASS; candidate image SHA-256
  `a08af151893efb0171b48dcd434b6aa6a8f2d5db75c49d78b7d2c004adffcf6a`.
- `scripts/run-tokenizer-smoke`: PASS, including text, special-token,
  malformed-model, operation-boundary, EOG and reader cases.
- `scripts/run-alignpack-smoke`: PASS, 27 positive and 128 negative cases,
  20,541 assertions. Existing optional full-filesystem, cleanup-failed and
  window-unavailable cases are N/A on this invocation; dense qualification
  is N/A while the MoE qualification passes.
- `scripts/bench-runtime-greedy` and `scripts/bench-runtime-sampler`: PASS.
- Both scan binaries pass all 33,153 guard-page validation cases; all 42
  paired measurement invocations complete successfully.

This audit does not close Requests 95/108/112 wholesale. The wider historical
18-file early-exit remark census is not repeated. Linux real-ggml failures
remain separately owned, and no Metal/CUDA qualification was run. No upstream
issue comment was posted during this audit; [the draft](upstream-1080-draft.md)
contains the independently reproduced #1080 residual.

## Confirmed remaining compiler gap

`range-residual.align` contains the same byte scan in two functions. The
second allocates an independent one-element local array before scanning and
returns its known length test after scanning. At the candidate revision:

| Function | Borrowed length in raw IR | Optimized IR |
| --- | --- | --- |
| `plain` | Scalar load with `!range !{i64 0, i64 -9223372036854775808}` | `<16 x i8>` vector body; no `llvm.smax` |
| `allocated` | Aggregate header load, then `extractvalue`; no range fact | Unannotated length load; `llvm.smax.i64(len, 0)`; scalar scan |

This reproduces with default release runtime LTO, with `--no-rt-lto`, and
in raw dev IR. The real `runtime_sampler.select_values` vocabulary loop also
reloads its borrowed `slice<f32>` length without `!range`.

The root cause is a bypass of `load_view_part`: `Rvalue::Load` falls back to
an aggregate load when `cached_view_header` is unavailable, and a subsequent
`SliceLen(Value)` uses `extractvalue`. The allocation disables the whole-body
header cache proof. At this exact Align revision, see
`crates/align_codegen_llvm/src/lib.rs:9762`, `:10566`, `:13885`, and `:18889`.
Plan 69 I7 promises nonnegative length metadata independently of caching.

This belongs to existing Request 108 / Align #1080. Preserve the independently
justified length invariant on the uncached typed header path, keeping the
existing alias and foreign-provenance refusals. The missing caching/noalias
facts are separately permitted by the conservative whole-body policy.
Restoring range metadata alone is not claimed to vectorize the sampler.

Reproduce from the repository root:

```sh
scripts/alignc emit-llvm eval/benchmarks/codex-binary-audit-2026-09-23/range-residual.align --stage raw --profile release --no-rt-lto
scripts/alignc emit-llvm eval/benchmarks/codex-binary-audit-2026-09-23/range-residual.align --stage optimized --profile release --no-rt-lto
scripts/alignc emit-llvm src/runtime_sampler.align --stage optimized --profile release --export select
```

## Binary census method

Disassemble each identified image with LLVM 22 `llvm-objdump -d
--no-show-raw-insn IMAGE`, then run `node census.mjs IMAGE.asm RESULT.json`.
The script decodes `_align_fn$LEN$HEX` names, counts decoded instruction lines,
resolves direct `bl` destinations by exact address, and counts calls between
Align bodies whose target has at most eight instructions. Tail branches are
reported separately. This is a static count, not a dynamic hotness estimate.
Short machine code alone does not establish eligibility under Plan 74's
checked-source admission policy.

For Mach-O external calls, resolve stubs with `llvm-objdump --macho
--indirect-symbols IMAGE`; the nearest decorative symbol in ordinary
disassembly can name an unrelated import. Align-to-Align counts above use
exact destination addresses and are unaffected by that annotation.

The nonnegative-clamp census requires `bic xD, xN, xN, asr #63` with equal
source registers in an Align body. It is a syntactic count; not every such
clamp is established to originate in a view length. Runtime and shim bodies
are excluded. FP SIMD counts include vector arithmetic/comparisons and exclude
register moves; zero FP arithmetic would not imply the absence of SIMD byte
or integer operations.

## Scan measurement method

For each compiler revision, emit the unchanged real client witness:

```sh
scripts/alignc emit-llvm src/kv_plane.align --stage optimized --profile release --no-rt-lto --export all_zero > kv.ll
awk '/^; ==== unit: kv_plane ====/{p=1;next} p{print}' kv.ll > kv-unit.ll
llc -O2 -filetype=obj kv-unit.ll -o kv.o
clang -O2 eval/benchmarks/codex-binary-audit-2026-09-23/scan-harness.c kv.o -o scan
./scan check
./scan
```

Use LLVM 22 tools. Select the old compiler explicitly with `ALIGNC` for its
arm. The extracted module is unchanged emitted IR, including the compiler's
C export wrapper; `llc` performs instruction selection without a second IR
optimization pipeline. This measures the exported scan kernel, not the full
CLI or coding time to a passing patch.

The harness validates 33,153 zero/nonzero cases for lengths 0 through 256,
including every possible nonzero position and an inaccessible page directly
after the view. It measures a 1 MiB zero buffer, 20 warmup scans and 2,000 timed
scans, with an externally linked function and checked result count. GB/s uses
decimal bytes/ns. The Request 112 local acceptance floor is 25 GB/s.

For the paired runner, place the two scan executables at `ARTIFACTS/scan-old`
and `ARTIFACTS/scan-new`. Build `src/runtime_greedy_bench.align` with
`scripts/run-main-with-shim scripts/alignc build` and
`src/runtime_sampler_bench.align` with `scripts/alignc build`, once per
compiler. Use absolute source/script paths from separate `ARTIFACTS/old-bench`
and `ARTIFACTS/new-bench` working directories; select each compiler explicitly
with `ALIGNC`. Keep the resulting executable basenames unchanged, then run:

```sh
node eval/benchmarks/codex-binary-audit-2026-09-23/measure.mjs ARTIFACTS new-samples.json
```

The runner alternates arm order, validates each invocation and refuses to
overwrite existing measurements. Keep compilation outside the timed phase.
