# Product cutover evaluation measurement — 2026-09-13

The user requested a before/after speed check after normal product Python retirement.
On this controlled fixed-patch evaluation, the native product reduced median complete
CLI elapsed time by **66.42%**, from **2.145870293 s** to **0.720526833 s** (2.98×).
All nine measured pairs favored the native product. This is an evaluation-orchestration
result, not an inference-throughput or sampled-model coding result.

## Baseline designation

Baseline ID: **`product-cutover-fixed-patch-2026-09-13`**. The user designated this
measurement as the reference on 2026-09-13. The reference product is the **After** arm
at `2f25c3faba4fc12c0035a5c168b38dc3f0ba935d`: **0.720526833 s** median external
complete-CLI wall time for eight passing rows. The Before arm remains historical
comparison evidence. The immutable sample document has SHA-256
`1d0b1b68e8fca8088b151b5fc774b2d99635f86ccd4c71052953f79e98f622b5`.

Future comparisons must name this baseline, preserve the eight-row fixed-patch workload,
external target tests, success/cleanup checks, Linux-local storage and external clock,
and use two warmup pairs followed by nine alternating measured pairs. Rebuild and rerun
the reference product alongside the candidate on the same host; do not infer a regression
from historical absolute times on different hardware. Record both application/compiler
identities and shared native dependencies, retain every sample, and report median wall
time with passing-row counts. Changed workload or timing boundaries require a separately
named baseline. This designation introduces no shipping threshold and does not replace
the sampled-model inference baseline.

## Inputs and protocol

| Item | Before | After |
| --- | --- | --- |
| Application commit | `9855afe1e3b7e73c758463ed2f32e13bc9b6a550` | `2f25c3faba4fc12c0035a5c168b38dc3f0ba935d` |
| Align compiler/runtime pin | `305926b423da9be1f13b0129a7232626e6704d95` | `f502fe3da00ce0b39c4eeec40586b11688627fbd` |
| Product executable SHA-256 | `c8c9d15061eb10ad3a6b295864011521c7f6d4ad6a72a8f77967389ec1436726` | `b61e4b35d12c1de665921063e7e00f67e2a824239f452dcbbf7114ea8e7d1290` |
| Median CLI wall time | 2.145870293 s | 0.720526833 s |
| Observed minimum–maximum | 2.138149460–2.254050334 s | 0.711608292–0.743237084 s |
| Median child CPU time | 2.160117 s | 0.814431 s |
| Passing rows per invocation | 8 / 8 | 8 / 8 |

Both products ran sequentially on the same Linux ARM64 Docker host
(`6.11.11-linuxkit`). Executables, input documents and workspaces were placed on the
container-local filesystem. Both builds used the same real ggml shim and libraries.
No compiler/build process ran during measurement. Build and fixture preparation time
are excluded; each measured invocation starts a fresh product process.

The workload is two inclusive-range tasks × two samples × parent/candidate, using
the same known-correct patch, original source files and unchanged Python target tests.
No model generation, repair attempt, GPU computation or remote provider is included.
The target test interpreter is an explicitly declared external dependency on both sides.
Source reachability is equally unverified, so neither arm's result can activate a gate.

The schedule was fixed before timing: two warmup pairs, then nine measured pairs,
alternating before/after execution order. A 1,200-second complete measurement ceiling
and 120-second per-invocation ceiling were imposed. External `perf_counter_ns` clocks
enclose `main prompt evaluate REQUEST result.json` through process exit, including
result/evidence publication. Every invocation must exit successfully, produce eight
passing rows, report successful containment/cleanup, leave an empty workspace and
preserve the source-file hashes. All 22 invocations satisfied these conditions.
Raw samples are retained even when an arm is slower; no positive-result filter is used.

## Necessary fixture adaptation and limits

The old smoke fixture deliberately selected a failing patch for its parent arm. To
compare the same successful work, its temporary independent fixture adapter was
configured to select its already-pinned candidate patch for both variants. Only that
path/hash selection and the positive fixture timing field were adjusted; its evaluator,
runner, containment, validation, scoring and publication implementations were retained.
The checked-in historical Python implementations and patch bytes were not modified.

Both arms use task-bound prompt/context identifiers. Native task definitions carry their
matching task IDs and `FIXTURE_PATCH` selects the same patch. Both declare the source TREE;
the native manifests additionally declare their per-task definition files. The request,
policy and result wires retain each version's own required schema and runtime identity.
These are controlled semantic counterparts, not byte-identical requests.

An initial build of old source with the new compiler failed because process-result and
string APIs changed. Each version therefore uses its own exact pin. The observed gain
cannot be attributed solely to Python removal or to the Align language: it includes the
native integration and compiler/runtime adoption. There is no new optimization or shipping
floor; this is a user-requested measurement of already implemented products.

An untimed shared-folder trial reported changing permissions for generated files across
snapshots. Both workloads were moved to Linux-local storage before any recorded pair.
Input-shape troubleshooting and that failed setup trial are not timed samples.

The old fixture includes a fixed `prompt_preparation_ns` and a fixed adapter generation
subfield. Persisted row clocks are retained as diagnostic data only and are **not** used
for this comparison. Only external complete-CLI wall time and child CPU time are compared.
The evaluator's incidental `IMPROVED` / `NO_IMPROVEMENT` classification compares its own
parent/candidate rows; it is not the before/after benchmark verdict.

This does not replace the historical OLMoE sampled coding result of 84.062 s versus
llama.cpp's 14.174 s. A new run of that model/task protocol is needed to update that result.
This measurement makes no claim about tokens/s, model quality, repair speed, other hosts
or other task sizes.

## Evidence and local replay

[Machine-readable samples and identities](../eval/benchmarks/product-cutover-2026-09-13.json)
contain all 22 timings, warmup labels, row outcomes, source-file digests, compiler and
product identities, the preregistered protocol, and hashes of all raw result documents.
[Dependency identity supplement](../eval/benchmarks/product-cutover-2026-09-13-dependencies.json)
records the shim, linked libraries, loader and target interpreter hashes recovered from
the retained binaries and Linux container after measurement. Both arms resolve identical
dependencies. This is a later capture, not a contemporaneous dependency attestation;
the historical sample JSON remains unchanged. Portable replay records these identities
before timing each new experiment.

The recorded medians were independently recomputed from the nine non-warmup pairs;
all raw result documents were checked for eight passing, contained and cleaned-up rows.

The original local preparation/measurement scripts and full raw results remain in the
ignored `run/product-cutover-benchmark-20260913/` evidence directory, with hashes in
the immutable sample JSON. Portable replay owners are now checked in as
`scripts/prepare-product-cutover-benchmark` and `scripts/measure-product-cutover-benchmark`.
They preserve the original fixture transformations, ordering and clock boundary while
parameterizing local paths; new results do not overwrite the historical measurement.

On a capable Linux host, create checkouts of the two application commits in the table.
Build each with its named release compiler and the shared real shim through
`scripts/run-main-with-shim "$ALIGNC" build src/main.align`. Supply absolute paths to
the resulting binaries, checkouts and a **nonexistent Linux-local** experiment directory:

```sh
export BENCHMARK_BEFORE_SOURCE=/absolute/path/to/historical-checkout
export BENCHMARK_AFTER_SOURCE=/absolute/path/to/native-reference-checkout
export BENCHMARK_BEFORE_BINARY=/absolute/path/to/historical-binary
export BENCHMARK_AFTER_BINARY=/absolute/path/to/native-reference-binary
export BENCHMARK_DATA_ROOT=/absolute/linux-local/path/to/new-experiment
export LD_LIBRARY_PATH=/absolute/path/to/shared-shim:/absolute/path/to/shared-libraries
python3 scripts/prepare-product-cutover-benchmark
python3 scripts/measure-product-cutover-benchmark
```

Run these scripts from the checkout containing this report; the supplied reference
checkout may predate the report. Preparation reconstructs fixtures from exact historical
commit `9855afe1e3b7e73c758463ed2f32e13bc9b6a550` and refuses an existing experiment
directory. The runner refuses an existing `results.json`. It records source revisions,
product hashes, resolved shared-library/loader hashes and all raw invocations. Failed
runs retain evidence and exit nonzero. Dependencies must resolve through `ldd` before
measurement. Native models are not needed for this fixed-patch workload.

These owners replay only the recorded historical pair. They require exact application
commits and product SHA-256 values from the immutable sample record, reject optimized
Python and reject mismatched native dependencies before timing. A rebuilt binary with
a different hash is not silently treated as the historical executable; retain it as a
separately identified build for a new comparison. The recorded executables are local
build artifacts, not committed binaries; exact-byte replay therefore requires retaining
or reproducing those builds as well as the explicit native dependencies.

Future candidate comparisons must implement the same documented paired protocol with
the designated native reference and record their own identities. Arbitrary candidate
substitution is deliberately outside these frozen replay owners. The original baseline
record remains the comparison reference and must not be overwritten.

Preparation and builds remain outside the clock. Product checkouts are unchanged.
No new `make ci` or GPU campaign was run.
