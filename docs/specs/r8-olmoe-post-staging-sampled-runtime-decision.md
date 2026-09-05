# R8 OLMoE post-staging sampled runtime decision

Status: active; ledger committed before implementation, 2026-09-05.

Roadmap owner: item 78, `R8-OLMOE-POST-STAGING-SAMPLED-RUNTIME-DECISION`.

Item 77 measured `MET`: all four paired savings were positive, median paired saving was
1,047,849,541 ns / 66,571 ppm, control median was 15,740,152,645 ns, and candidate median was
14,626,648,395 ns. Those are complete fixed-request measurements, not time to a passing patch.
After that implementation merges, this capability follows item 69's accepted, capability-specific
precedent: measure accumulated shipped behavior through the fixed coding caller. It introduces no
universal remeasurement gate for rejected optimizations. The latest historical primary measurement
was item 69: local median 13,992,706,375 ns, runtime median 91,415,902,187 ns, `NOT_MET`, complete
elapsed 506.52 seconds. Only this capability's new four local/runtime pairs decide its result.

## Authoritative public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Capability/owner | Add `scripts/run-olmoe-post-staging-sampled-runtime-decision`. No arguments performs the opt-in real decision; `--self-test` performs the model-free owner. No other argument is accepted. The authoritative plan is `docs/specs/r8-olmoe-post-staging-sampled-runtime-decision.md`. |
| Consumer | One coding caller seeking its first passing patch through the shipped `openai-local` or `align-runtime` `ModelProvider` arm after merged item 77. There is one current-source helper/shim build used by both arms; this is not an old-source/current-source A/B comparison. |
| Reuse/changed modules | Reuse item 53's candidate construction, extractor, validator command, portfolio measurement/validation, repeatability and aggregate functions from `scripts/run-olmoe-sampled-runtime-decision` and its `scripts/run-olmoe-coding-decision` dependency; reuse item 56's workload, schema and process-match rules from `scripts/run-olmoe-isolated-sampled-runtime-decision`. Reuse item 76's strict-parser, tracked-snapshot, runtime-identity and process-group algorithms in the new owner with this ledger's parameters. Own current orchestration, exact identities, coordinated child/server/container lifetimes, result extension and tests in the new runner. Do not invoke a historical real `main`, rewrite historical pins/results, or silently disable their validation. No changes to Align, C, FFI, provider helper, evaluator, previous runners, Makefile, aggregate membership or toolchain pin. |
| Shipped source | `MERGED_SOURCE_BASE = 62f6f96747947078a048cbf32a3dd8c948db6743`; real execution requires a clean exact current tracked HEAD descended from this base. The runtime remains the ordinary shipped unsplit path including item 77's V transpose. No diagnostic mode, test flag, alternate cache/graph policy, or production source mutation. |
| Model/task | The exact `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 4,213,512,192 bytes, SHA-256 `4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f`. Task is `eval/tasks/coding-v1/python-inclusive-range/task.json`; its fixture is `eval/fixtures/python-inclusive-range-v1/repository`, task source revision `1adf3697ea82a2da6fa9b9aa76f24fb51625ffca`. Use the identical system/user prompt, strict extractor, patch restrictions, validation arguments and task timeout. |
| Request/portfolio | Maximum 128 completion tokens, temperature 300,000 micros, ordered seeds `[1,2,3,4,5,6,7,8]`, maximum eight candidates per arm/portfolio, stop immediately at first passing patch, cache budget 975,175,680 bytes. Reuse `src/runtime_provider_gate.align`: `local-sampled ENDPOINT olmoe 300000 SEED PROMPT RECORD` and `runtime-olmoe-sampled MODEL PACK GEOMETRY 975175680 128 300000 SEED PROMPT RECORD`. Preserve the existing system text and supplied prompt bytes. Each runtime helper invocation owns its request-local cache. |
| Measured outcomes | Preserve `PASS`, `INVALID_PATCH`, `FAILING_PATCH`, nullable portfolio fields, duration nesting, strict extraction, within-arm portfolio-signature repeatability and integer arithmetic exactly. `NO_PASSING_PATCH` after all eight seeds is measured data. Candidate index 5, its output text/hash and the historical successful patch are not pinned expected generated results; the known-good validator control is independently fixed. Provider/refusal/infrastructure failures are errors, not failed-patch samples. No cross-arm equality requirement beyond the inherited protocol. |
| Pair order | `(local,runtime)`, `(runtime,local)`, `(runtime,local)`, `(local,runtime)` in chronological order. One portfolio at a time, four fresh local servers total; at most 64 provider candidates total. There are no extra short conditioning requests and no item-77 AB/BA request schedule. |
| Local baseline | Before each local arm prove zero processes matching both canonical configured server and model paths. Start exactly one pinned server with `-m MODEL --alias olmoe --host 127.0.0.1 --port PORT --device none -ngl 0 -t 4 -c 512 -np 1 --jinja --no-warmup`. Preserve default enabled prompt caching within that one portfolio. Wait ready; require the sole matching PID is the invocation-owned server; keep it alive through the portfolio; require it still alive before teardown. Stop/reap its group, close the log, and prove zero matches before continuing. No server survives between portfolios. |
| Runtime isolation | Prove zero matching server/model processes immediately before and after each runtime portfolio, including its failure path. Contamination causes refusal; never terminate an unowned matching process. Preserve item 56's ten exact per-pair isolation fields and baseline scope metadata. |
| Primary metric | Use the inherited `measure_portfolio` timer: immediately before its first candidate/helper work through completion of first-passing-patch validation. Its command and validator durations remain nested in the portfolio time. Local startup/readiness and teardown are excluded from this metric and included in complete qualification elapsed. No subtraction of instrumentation, build, validator, process overhead or unsuccessful attempts inside this timer. |
| Gate | Recompute item 53's aggregate from the four new samples. For each arm, sort its four positive passing times and set median `(second+third)//2`; `gain_ppm = (local_median-runtime_median)*1000000//local_median`. `MET` iff both arms pass all four portfolios, runtime time is strictly smaller in every pair, and `gain_ppm >= 50000`. `NOT_MET` iff both arms pass all four but the speed rule fails. Otherwise `NOT_ELIGIBLE`, preserving inherited null medians/gain and false direction field. A tie fails the every-pair rule. The 871,174,011-ns secondary floor and 16,552,306,197-ns fixed-request ceiling do not apply. |
| Inputs/prerequisites | Canonicalize the six configured inputs, in order: `ALIGN_LLM_OLMOE_MODEL`, `ALIGN_LLM_MOE_ALIGNPACK`, `ALIGN_LLM_MOE_GEOMETRY`, `ALIGN_LLM_GGML_INCLUDE`, `ALIGN_LLM_GGML_LIB`, `ALIGN_LLM_LLAMA_SERVER`. The first unset input prints exactly `R8-OLMOE-POST-STAGING-SAMPLED-RUNTIME-DECISION: N/A (NAME unset)` and returns zero before compiler materialization or child creation. A configured unusable path fails. `ALIGN_LLM_RUNTIME_GATE_IMAGE` defaults to `c4-repair-measure:latest` but must resolve to the exact pinned image ID. Darwin requires the inherited canonical ordered `LIBRARY_PATH`; preserve environment scrubbing and reject unsupported host/identity changes. |
| Known-good validator | On this fixed Darwin arm64 host, resolve the Docker validator image to `sha256:33fa9e4446ab1a5ca849c57ea49e2e2e4585488aa1cd4d7b2940801bad84cb54`. Preserve the existing Linux arm64 validator command/options, evaluator and task. Before measured portfolios validate the exact inherited `KNOWN_GOOD_PATCH` whose SHA-256 is `5d6b107e706a5a55c945bc0b41296e255013a1516e0a6211ccc9da65001252dc`; it must pass. Validator exit 0 is pass, 4 is a valid failing patch, and every other status is infrastructure failure. A failing control is fatal. No installed-profile substitution, task relaxation, image rebuilding or Docker skip. |
| Independent current pins | Freeze an independently enumerated current `SOURCE_PATHS`/digest table in the new runner after merge and before real execution. Include the complete transitive imported Python owner closure, all tracked `src/*.align`, both shims, `scripts/build-ggml-shim`, `.align-revision`, `scripts/alignc`, `scripts/align-toolchain`, `scripts/fresh-align-compiler`, `eval/runners/run-coding-task.py`, the exact task and every tracked file in its fixture repository. Validate expected names/count/order and bytes; changing every imported owner together must still fail. The new runner's own bytes are bound separately to its clean tracked HEAD to avoid a self-hash cycle. An existing owner's historical `EXPECTED_SOURCE_IDENTITIES` is evidence for that owner, not the current-source allowlist. |
| External/tool pins | Independently retain item 56's exact model, pack, geometry, server binary/build, task/prompt, Align revision/compiler, C compiler/version, canonical linker search, ggml libraries and validator image identities. Also freeze item 76/77's exact consumed ggml header manifest and host fingerprint. Bind the adjacent consumed managed `libalign_runtime.a` independently: SHA-256 `7a36c1eb075b74b7c61a5d7ed229d684e5759fce2f35d32455e07bbad5aba38f`; require the actual regular non-symlink archive, not only the compiler digest. Before/after checks use the same absolute resolved compiler/archive and external inputs. |
| Build/snapshot | Materialize invocation-owned regular tracked files at exact evaluated HEAD using Git object bytes and modes, with no symlink/traversal extraction. Include the build closure and validator/task/fixture files. Build the real dynamic shim and unchanged `src/runtime_provider_gate.align` inside that isolated tree using the exact managed compiler, default pinned C compiler, headers/libraries and linker search. Run both arms with this exact helper/shim and loader paths. The validator consumes the same immutable task/evaluator/fixture snapshot through the inherited command. Do not create or replace the checkout's `runtime_provider_gate`; no build product survives cleanup. Record/recheck helper/shim and snapshot identities. |
| Process ownership | One invocation coordinates two independent live slots: a synchronous child process group and a persistent local-server process group. Start both group leaders with `start_new_session=True`; record ownership across Popen/signal-launch races. The server slot may coexist with helper/validator/ps children, so item 76's single `active` slot cannot represent both. On error or signal stop the active group and the server group, escalate and reap, check group absence even when the leader already exited, then finish exact owned container cleanup. Never use only a direct PID or assume an outer group contains separately sessioned descendants. Refuse new measured work after interruption; only required cleanup commands and process-absence probes may run within the shared cleanup deadline. |
| Docker ownership | Keep one unique CID file per validator invocation, registered before launching Docker, for the control and every admitted candidate. Always read/check its exact 64-hex ID and remove that container with the inherited `docker rm -f CID` cleanup, even if the Docker CLI died or its group was killed. Missing CID before container creation is permitted; malformed CID or non-`No such container` removal failure is fatal. Do not enumerate/remove unrelated containers. OS group cleanup does not replace daemon-owned container cleanup. Retain CID/work/log paths until their owning cleanup completes. |
| Deadlines/cleanup | One monotonic 1,500-second complete-result budget begins after argument/unset-prerequisite handling and includes source/host checks, compiler materialization, known-good control, build, every server lifecycle, all providers/validations, final identity checks, successful cleanup and result validation. Clamp each inherited narrower subprocess/readiness bound to the remaining result deadline without rounding it upward. Success must finish cleanup and publication eligibility inside 1,500 seconds. Timeout, signal or any failure may use at most one additional 50-second nonpublishing cleanup grace: up to 15 seconds for active-group cleanup, 15 for server-group cleanup and 15 for Docker CID cleanup, with five seconds margin. Share one cleanup deadline, do not grant 50 seconds separately per owner, and continue attempting other owned cleanup if one fails. Cleanup escalation must terminate/reap its own commands as well. A late result never publishes. |
| Strict parsing | Decode actual task and provider-record bytes as strict UTF-8; reject duplicate keys at every depth, nonstandard NaN/Infinity constants, trailing/extra JSON documents and malformed input before semantic validation. Reuse item 76's `strict_json` behavior. Preserve provider schema-2 type/provider/status/timing checks after strict decoding. Apply the same parser to serialized complete-result input in tests/evidence validation. Do not claim parser closure from only synthetic dictionaries or from strict outer JSON while inherited `base.parse_record` still accepts duplicate keys. Scoped parser/process/path delegation must be restored on success, exception, timeout and signal; never mutate Python's global `json.loads`. |
| Validation order | Arguments; canonical prerequisites; start complete clock and handlers; scrubbed environment/linker/host; clean head/common directory/base ancestry; independent source/runner identities; materialize exact snapshot; tool/external/task/validator identity; known-good validator control with cleanup; helper/shim build; scheduled per-arm isolation, portfolio and cleanup; schema/determinism/recomputed aggregate; unchanged head/ancestry/runner/imported source/snapshot/external/helper/shim/validator identities; all owned cleanup and restored scoped state; final elapsed/result validation; one publication. No measured portfolio precedes the control and identity checks. |
| Result/error | Exactly one compact schema-1 JSON line with artifact `R8_OLMOE_POST_STAGING_SAMPLED_RUNTIME_DECISION`, status `COMPLETE`, and the exact extension below, then one concise stderr summary. No output/patch bodies, local paths, PIDs or credentials in evidence. Invalid arguments, identity/source drift, contamination, provider/validator/process/parser/schema failures, failed cleanup or ceiling excess return nonzero without a complete JSON document. `NOT_MET`/`NOT_ELIGIBLE` are complete measured results, not invocation errors. |
| Ancestry/publication | Resolve one Git common directory, set `GIT_NO_REPLACE_OBJECTS=1`, reject replacement refs and common-directory grafts, and support ordinary clones and linked worktrees. Require `62f6f96747947078a048cbf32a3dd8c948db6743` ancestral to evaluated and final merging HEAD; after qualification preserve the exact evaluated ancestor and source/build identity through publication. Merge-only integration; no squash/rebase. A publication metadata commit may record evaluated HEAD/raw evidence while the real qualifier remains replayable from that immutable evaluated head. A publication self-test validates ancestry and evaluated source pins without treating changed result documentation as a new measurement. |
| Terminal meaning | `MET` closes R8 only for this fixed model/task/host/sampled consumer under the existing primary gate. `NOT_MET`/`NOT_ELIGIBLE` records the remaining primary gap and informs the next evidence-based capability without authorizing an optimization or unchanged rerun. Item 77's independently qualified native change remains shipped regardless of this primary result. Preserve the complete raw record and SHA-256 in the PR, verify retrieval, and record concise authoritative results/next action. |
| Classification/limits | Application-owned measurement, source identity and resource lifecycle; no missing Align language/compiler/runtime/library surface encountered. No new capability request or public product API. Persisted production/cache formats, handwritten math, native graph ownership and production platform behavior are N/A because unchanged. Cross-task, cross-host, GPU, throughput, quality-rate, cold-cache, persistent-provider and general speedup claims are N/A. |

## Scoped inherited paths and call ownership

Use the already imported item-56 module as `isolated`, `sampled = isolated.previous`, and
`coding = sampled.base`. These are separate module instances from copies transitively imported by
item 76; install hooks on the objects that actually execute portfolios. Validate imported workload
constants before entering the snapshot scope and after restoring it. Do not rebind
`sampled.TASK`: item 56's `validate_imported_workload` deliberately checks that captured absolute
original task path. The new runner separately validates the snapshot task's exact bytes.

For the inherited validator command, scope `coding.ROOT` to the immutable snapshot root;
`coding.TASK` and `coding.VALIDATOR` point at its copied task and evaluator. `validation_command`
uses `coding.ROOT` for the Docker read-only mount, retains container cwd `/work/align-llm`, runs
`python3 eval/runners/run-coding-task.py`, passes the relative task path, and mounts the candidate
work directory read-only at `/tmp/align-olmoe-coding-decision` with that `ALIGN_LLM_TEMP_ROOT`.
The evaluator itself derives its project root from `__file__.parents[2]`, not cwd; therefore copy
its original relative location and the task's unchanged `source_dir`. The fixture needs only its
tracked files and modes: `create_pinned_checkout` copies them and constructs/checks the fixed
revision itself. No `.git` directory, task rewriting or evaluator change is needed.

Scope `sampled.run_process` to the coordinated synchronous-group adapter, with snapshot cwd and
explicit environment. This reaches provider helpers, inherited `validate_patch` and item 56's
`matching_processes`. Scope `coding.run_checked` separately so `resolve_validator` image inspection
is also group-owned and receives the scrubbed environment. Scope `coding.cleanup_container` to
exact-CID cleanup under the coordinated cleanup deadline; its original implementation calls
`subprocess.run` directly. Register a CID before the Docker launch, by wrapping the inherited
`coding.validation_command` result or the validation scope, so top-level cleanup retains ownership
if a launch/cleanup signal occurs. Own the local server in the new coordinator, without calling
old `measure_local_isolated`, `stop_owned_processes`, old builders or old real mains.

The strict provider parser must run at the actual `coding.parse_record` call used by
`sampled.measure_candidate`; retaining the old parser underneath a separate pre-parse is not the
promised single actual-input boundary. A module-local JSON adapter that supplies strict `loads`
to the original parser is permitted when its exception semantics remain normalized, or the new
owner can provide the corresponding strict record parser. Do not replace the shared standard
library's `json.loads`. Restore every changed function/module-local JSON reference/path and both
original SIGINT/SIGTERM handlers in `finally`, after group/CID cleanup but before temp removal;
leave original module active/server globals untouched. The new owner's Git checks explicitly use
the real checkout cwd and must never accidentally resolve `.git` from the snapshot.

`self_test_scoped_snapshot_paths` verifies the actual inherited Docker argv/mount/cwd, copied
validator/project/fixture resolution, no root helper write, hooks on the executing module instance,
CID registration and restoration after success, exception and signal. It is reached by the new
`--self-test` alongside the matrix tests below.

## Exact result extension and arithmetic

Keep item 56's schema-1 exact shapes for `model`, `baseline`, `candidate`, `task`, `sampling`,
`validator`, `environment`, `samples`, `aggregate` and `elapsed_ns`. Add one top-level
`provenance` object; no existing field changes meaning. The exact top-level key set is:

```text
schema_version artifact_kind status model baseline candidate task sampling validator
 environment samples aggregate elapsed_ns provenance
```

`provenance` has exactly:

```text
merged_source_base source_tree source_files runner_sha256 runtime_sha256 ggml_headers
host_fingerprint_sha256
```

`merged_source_base` is the fixed item-77 merged SHA; `source_tree` is the Git tree OID of the
recorded candidate head. `source_files` is a sorted nonempty array of exact-key
`{path,bytes,sha256}` rows for the independently pinned current closure plus the runner itself;
paths are unique, relative, safe and complete; bytes are non-boolean nonnegative integers and
hashes are lowercase 64-hex. This manifest identifies actual consumed source and its independently
pinned expected manifest; a mutually mutated manifest and files cannot pass. The snapshot's build
and validator subset also preserves each Git blob/mode. The runner row matches `runner_sha256`.
`ggml_headers` is the exact inherited header name/size/hash manifest. Runtime and host hashes must
equal the new owner's independently frozen fixed values. All SHA-1 OIDs are lowercase 40-hex.

Validate this complete extension, remove only `provenance`, change only `artifact_kind` to
`R8_OLMOE_ISOLATED_SAMPLED_RUNTIME_DECISION`, and call item 56's complete result validator. That
projection must equal the inherited record byte-for-byte in values; never drop a sample, isolation
proof or aggregate field to make validation pass. Recompute aggregate with item 53's function and
require exact equality. `elapsed_ns` is positive, non-boolean, at most 1,500,000,000,000, and covers
all portfolio work and successful teardown/temp cleanup; it is refreshed after cleanup before
final validation/publication.

The existing ten isolation fields remain exact: `local_server_instances=1`, `local_ready=true`,
`local_sole_owned_match=true`, `local_alive_after_portfolio=true`, `local_terminated=true`,
`local_reaped=true`, `matching_before_local=0`, `matching_after_local=0`,
`matching_before_runtime=0`, `matching_after_runtime=0`. Counts are non-boolean integers. Group
absence and Docker cleanup are additionally required completion invariants, exercised by the owner;
they do not weaken or substitute for these inherited process-match proofs.

## Closure matrix and exact focused tests

All new test names below are functions reached by the new runner's `--self-test`; subprocess fault
fixtures are model-free, invocation-owned children created by that owner. Do not add an unrelated
suite or production injection flag. Existing item 56 self-test already calls item 53's self-test.

| Path/implementation owner | Construction and success | Failure/malformed | Early exit and cleanup | Exact regression/evidence |
| --- | --- | --- | --- | --- |
| CLI/environment, new runner | Exact no-arg/`--self-test`, canonical fixed inputs and inherited scrubbed environment | Extra args, invalid configured paths, wrong linker order/host refuse | First unset prerequisite emits one N/A line before any child/materialization | `self_test_cli_environment` |
| Independent source contract, new runner | Current closure, clean tracked runner, exact evaluated source tree and merge base | Direct/transitive/uniform dependency mutation, missing/extra source, runner mutation and changed HEAD refuse | Refusal creates no measured request; no historical pin bypass | `self_test_current_source_pins` |
| Git ancestry/snapshot, new runner | Ordinary clone and linked worktree; safe tracked blob/mode materialization | Missing base/evaluated ancestor, replacement ref, graft, unsafe/symlink member, snapshot mutation refuse | No checkout helper overwritten; snapshot removed only after consumers end | `self_test_ancestry_snapshot` |
| Tool/build ownership, new runner | Managed compiler plus consumed archive, pinned real shim and unchanged helper built only in isolated tree | Same compiler with changed/missing/symlink runtime archive, wrong headers/libraries/toolchain or helper/shim mutation refuse | Build exception/signal restores scopes and removes temp products after group cleanup | `self_test_build_runtime_identity`; real build |
| Validator control and command, inherited evaluator plus new owner | Pinned image/task/fixture and known-good patch pass before first portfolio; exact inherited argv/options | Wrong image, failing control, malformed record or infrastructure status prevents measurement | Every admitted candidate and control has owned CID scope; successful/failing patch classifications unchanged | `self_test_validator_control`; real known-good control |
| Actual strict parsing, new runner delegated into inherited candidate path | Valid UTF-8 single task/provider/result objects preserve inherited semantics | Duplicate nested keys, NaN/Infinity, invalid UTF-8, extra document, wrong schema/types/provider or timing refuse | Parser delegation restored on all exits, including when actual candidate invocation writes malformed bytes | `self_test_actual_json_inputs` |
| Local server lifecycle, new runner using item 56 match rules | Exact server args, one ready sole match alive through portfolio, four independent lifetimes | Existing/extra/wrong process, readiness failure, premature exit, surviving descendant refuse | Own group terminated/escalated/reaped, log closed, match count zero; never kill foreign PID | `self_test_server_group_lifecycle`; four real local lifetimes |
| Runtime isolation, item 56 match owner through new coordinator | Zero matches before and after runtime including failures | Matching server introduced at either boundary refuses | After-check actually runs as a bounded cleanup probe when failure/signal has disabled ordinary work; cleanup does not kill contaminator | `self_test_runtime_isolation`; eight real absence observations |
| Concurrent ownership slots, new coordinator | Server persists while synchronous helper/validator/ps child executes; normal child exit proves group absent | Leader exits leaving descendant; SIGINT/SIGTERM during either launch, repeated signal during cleanup, child failure/timeout refuse | Both owned slots cleaned, launched children registered, no new launch after interruption, handlers/delegates restored | `self_test_process_group_coexistence`; `self_test_signal_launch_cleanup` |
| Docker lifetime, inherited command plus new CID cleanup | Unique recorded CID removed for control and each validated candidate | Malformed CID, cleanup failure, CLI exits early or is killed after container creation fail closed | Cleanup targets only exact owned CID even with dead CLI; another owned cleanup failure does not skip this owner | `self_test_docker_cid_cleanup` |
| Portfolio semantics, item 53 | Ordered seeds, first pass, valid eight-seed no-pass, exact statuses/durations/signature | Out-of-order seed, continued-after-pass, bad nullable/status fields, nonrepeatable within-arm signature refuse | No ninth candidate; request cache and patch/record work end in invocation scopes | Item 56 `--self-test` (includes item 53); `self_test_current_orchestration` |
| Pair protocol, new runner/item 56 | LR, RL, RL, LR with exact sample/isolation schema and same helper for both arms | Reordered/duplicate/missing arm, shared server, unmeasured conditioning or foreign build refuses | Each local scope ends before next arm; no partial pair publication | `self_test_current_orchestration`; four real pairs |
| Gate/projection, item 53/56 and new extension | Exact inherited median/gain/direction, metadata projection, recomputed aggregate | 49,999/50,000 ppm boundary, tie, one slower pair, one nonpassing arm, boolean duration, malformed provenance reject or classify exactly | `NOT_MET`/`NOT_ELIGIBLE` remain data; no historical expected output injection | `self_test_result_projection_gate` |
| Deadline and terminal publication, new runner | All source rechecks, group/CID/temp cleanup and result checks finish within complete budget | Deadline expiry before/during/following measurement, final mutation, cleanup failure, successful but late result refuse | One shared 50-second failure-only grace, sequential cleanup budget/escalation, other owners still attempted, no complete JSON | `self_test_deadline_cleanup_publication` |
| Evidence ancestry, new runner | Exact evaluated head/tree/source and raw result retained through metadata publication/merge | Forged result, missing evaluated ancestor, source substitution or recomputed decision drift refuse | Publication replay never starts a model and cannot present later source as evaluated | `self_test_publication_identity`; verified complete raw JSON and retrieval SHA-256 |

## Acceptance and publication

Before real execution, freeze the independent source/external
constants, finish the coherent runner and run:

```text
python3 -m py_compile scripts/run-olmoe-post-staging-sampled-runtime-decision
scripts/run-olmoe-isolated-sampled-runtime-decision --self-test
scripts/run-olmoe-post-staging-sampled-runtime-decision --self-test
```

The first inherited self-test includes the item-53 owner. Do not run item 69's unmodified
`--self-test` on current source: it begins by enforcing its historical item-68 source pins. Reuse
its decision contract and cleanup lessons through the new focused tests, not by weakening that
historical gate. Test-only subprocesses must have bounded cleanup and consume no model CPU.

Commit the complete owner-tested candidate, then run exactly one clean-head no-arg real decision
under the fixed prerequisites. Treat its primary verdict as terminal evidence for this capability;
no workload/floor/order change after observation. Record exact evaluated head, source/runtime/build
identities, raw JSON hash, passing semantics/lifetimes, primary sample vectors and verdict. Perform
one comprehensive stable-candidate review; consolidate accepted repairs and rerun only affected
owners. Finish exact unchanged-head publication with:

```text
python3 scripts/pre-pr --owner-test R8-OLMOE-POST-STAGING-SAMPLED-RUNTIME-DECISION -- scripts/run-olmoe-post-staging-sampled-runtime-decision --self-test
```

The shared classifier owns any additional applicable preflight checks. This capability itself adds
no `make ci`, installed profile, broad native/model matrix or repeated item-77 qualification: product
native source and ABI are unchanged. Keep English PR evidence and review/check envelopes complete,
merge only with required checks passed, then follow the newly recorded roadmap decision.

The author consistency pass binds the inherited portfolio/gate to current-source provenance and
separate child/server/CID ownership. Every changed validation, scoped state, failure and cleanup
path has a named focused owner above; no production or historical qualification contract changes.

## Candidate verification checkpoint

The implementation adds only `scripts/run-olmoe-post-staging-sampled-runtime-decision`. Its
independent closure contains 116 files (102 Align and 14 tool/task/fixture inputs), with the runner
bound separately to exact tracked HEAD bytes. The item-56 self-test, which includes item 53's
portfolio and gate owner, passed. Python compilation and the new complete `--self-test` passed.

The new owner passed strict actual-provider and complete-result JSON cases, exact provenance and
non-boolean scalar checks, snapshot path installation/restoration, the inherited Docker mount and
endpoint, source-manifest mutation refusal, and the unchanged primary gate. Actual subprocess
tests passed for simultaneous server/child groups, descendants, premature/stubborn servers,
SIGINT/SIGTERM launch races, timeout, refusal of new measured work after interruption, the bounded
failure-only process-absence probe, exact Docker CID removal, missing/malformed/refused cleanup,
one shared cleanup deadline and continuation after one owner cleanup error. No model, compiler or
real container was used by these self-tests. Git-object reconstruction remains pending until the
candidate is committed; the real qualification and comprehensive review remain pending.
