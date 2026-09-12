# Product cutover evaluation measurement — 2026-09-13

The user requested a before/after speed check after normal product Python retirement.
On this controlled fixed-patch evaluation, the native product reduced median complete
CLI elapsed time by **66.42%**, from **2.145870293 s** to **0.720526833 s** (2.98×).
All nine measured pairs favored the native product. This is an evaluation-orchestration
result, not an inference-throughput or sampled-model coding result.

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
The recorded medians were independently recomputed from the nine non-warmup pairs;
all raw result documents were checked for eight passing, contained and cleaned-up rows.

The local `run/product-cutover-benchmark-20260913/` evidence directory contains the
preparation/measurement scripts, protocol, logs and all raw results. These are independent,
environment-specific measurement artifacts in an ignored developer directory, not product
code. Their hashes are recorded in the machine-readable evidence. The scripts use the
local prepared compiler/library/source locations and need those bindings restored to replay.

Build each product with its named release compiler and the shared real shim through
`scripts/run-main-with-shim "$ALIGNC" build src/main.align`. Then, inside the same capable
Linux host, with `BENCHMARK_DATA_ROOT` selecting a fresh Linux-local directory and
`LD_LIBRARY_PATH` selecting the shared native libraries:

```sh
python3 "$EVIDENCE_DIR/prepare.py"
python3 "$EVIDENCE_DIR/measure.py"
```

Preparation uses the old checked-in smoke fixture's setup code with compilation excluded
from the clock, then performs the documented schema/fixture adaptation. The current product
and original application worktree remain unchanged. No new `make ci` or GPU campaign was run.
