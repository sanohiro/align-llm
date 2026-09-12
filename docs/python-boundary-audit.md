# Python execution-boundary audit

## Current cutover checkpoint (2026-09-13)

The shipping evaluator, edit/repair chain, snapshots, source checks and validation
supervisor now execute in Align. The Python bootstrap has been removed. All eight
historical implementations are reclassified as `INDEPENDENT_ORACLE`, with unchanged
bytes; 16 immutable command manifests are explicitly replay-only. They are refused
by the normal evaluator's complete pre-dispatch retirement checks, including renamed
copies. No product violation or temporary bootstrap remains in the inventory.

Functional and relocated no-Python qualification pass with the real-linked product:
normal/failing repair rows, provider workers, state changes, repository commands and
three-token local inference. Host Python oracles stay outside the product namespace
and descendant tree; a separate namespace checks one explicitly permitted Python
target test. The strict guard keeps its existing process/literal rule: pure target
filename classification is shared by `source_file_kind`, while JSON renderers keep
explicit impossible-error aborts. The real installed Linux profile passes. One independent
comprehensive review found two source-binding defects; the consolidated repair restores
TREE authentication and repository/source equality, with affected owner evidence recorded
in the current handoff.

## Historical preparation audit

Audit date: 2026-09-09. Application head: `312dd65714036f9587329386b5fdbd65e91b97b9`.
Align pin: `305926b423da9be1f13b0129a7232626e6704d95`.
Sibling observed head: `84b97bce466aeb2ccbc4e0ef34750e90690f27a6`.
This is an implementation-ownership audit and migration plan, not a claim of Python-free operation.
The original preparation changed no product/tooling code. Implementation was subsequently
authorized; the independent A0 guard is now a local checkpoint. Historical evidence and Python
product implementations remain frozen pending the full cutover. The 2026-09-11 adoption selects
Align `f83f5c3c365ac992c6c2dc5a371164c9f7b4339f`; the baseline identifiers above remain historical.
The inventory's Align source hashes were refreshed after inspecting the JSON Result and process
status API changes. Twelve additional product modules import `std.process` solely for explicit
impossible-encoder-error aborts and therefore enter the conservative process-owner inventory;
they launch no child. This does not add a Python allowance. The environment/source-file/tree-snapshot smoke
scripts add three independent Python fixture/OS/digest oracles outside the product runtime.
`scripts/run-prompt-evaluation-provider-smoke` is classified as `CI_OR_DEVELOPER_TOOL` before
implementation. It prepares a deterministic HTTP fixture and checks the actual native evaluator's
requests, edits, evidence and cleanup. Only the test launcher imports the existing HTTP fixture;
neither the product nor its generation worker imports or executes this Python owner.
The native evaluation/cleanup/image/source modules now join the conservative process-owner
inventory. They operate admitted native images and child scopes; none introduces a Python launch.
`prompt_fixture_environment` is digest-bound data for explicitly declared target-project test
environments, including Python isolation variables. It neither discovers nor launches Python.
The native CLI and runtime relocation owners are developer host rows; the latter's Python
references describe absent executables rather than launches. A0 remains distinct from strict
cutover: the eight historical product debts are still frozen and require P8 retirement.
The evaluation relocation owner additionally prepares one explicit target-project Python test
in a separate namespace. Its interpreter is mounted only for that declared external task;
the evaluation, generation and Git namespaces continue to exclude Python. This is developer
qualification of the external-test exception, not a product implementation or bootstrap.

## 1. Complete file inventory

The cutover retirement owner `scripts/run-eval-retirement-smoke` is developer
qualification: it constructs external command manifests, requires pre-dispatch
refusal of frozen implementations, and positively executes one explicitly supplied
Python target test. Its interpreter never implements product decisions.
`scripts/run-align-product-cutover` is also `CI_OR_DEVELOPER_TOOL`: it selects
explicit functional, containment, or relocation qualification commands and fails
on missing prerequisites or a failed owner. It is never imported or launched by
the product. The existing native fixture host's cutover modes reuse an explicit
product binary and run the independent owners before deleting fixture storage.

[python-boundary-inventory.json](python-boundary-inventory.json) is the authoritative per-file
record. The preparation baseline lists every one of the **265 tracked Python files**, including extensionless Python
shebangs: 15 under `eval/`, 11 under `image/`, and 239 under `scripts/`. Each row records path,
exactly one classification, owned behavior, product reachability, substitution/duplication,
reason for retention, target state, migration owner, acceptance, frozen hash where applicable,
and bootstrap requirements where applicable. It also records **71 non-Python containers** with
Python invocations/references (shell, Make, workflow, image C launchers and Dockerfile); these are
separate host rows, not additional Python files. Embedded-host discovery is conservative: a
reference can be classified without claiming it is necessarily an executed statement.

The A0 implementation inventory now contains **269 Python files** (the baseline, two developer
guard scripts the native HTTP evaluator owner and an independent native-result oracle), **82 embedded hosts**, and 18 digest-bound top-level command manifests.
The two additional hosts are conservative references missed by the preparation scan:
`scripts/test-apt-llvm` names a Python debugger package in diagnostics and
`scripts/ggml_shim_stub.c` names a fixture in a comment. Neither is a newly discovered execution
path. `src/patch_eval.align` also joins the data-only source records for target-test filename
recognition. The table below preserves the preparation baseline; current developer-tool count
is 169 and the eight product violations remain unchanged.

| Classification | Files | Meaning in this audit |
| --- | ---: | --- |
| `INDEPENDENT_ORACLE` | 13 | Independently verifies bytes, records or results; no shipping decision authority. |
| `FIXTURE_OR_GOLDEN_GENERATOR` | 24 | Produces model, corpus, transcript or wire fixtures; not a product data producer. |
| `BENCHMARK_OR_MEASUREMENT` | 44 | Owns a fixed experiment, timing, paired ordering or measurement reduction. |
| `CI_OR_DEVELOPER_TOOL` | 166 | Test launchers, compiler/image provisioning, CI, preflight and their support modules. |
| `EXTERNAL_TEST_ADAPTER` | 10 | The deliberately Python target-project source/tests, not application implementation. |
| `TEMPORARY_PRODUCT_BOOTSTRAP` | 0 | No retrospective bootstrap exemption is granted. |
| `PRODUCT_LOGIC_VIOLATION` | 8 | Executes product decisions or state transitions along the evaluator/task path. |

A file with several test roles receives the class of its owning purpose: a test launcher with
embedded expected values is developer tooling; a reusable independently implemented verifier is
an oracle. A benchmark that scripts retries in a fixed experiment is measurement only if it has
no normal product caller. A file's name, extension, size, or contribution to GitHub statistics
never determines whether its behavior belongs in Align.

## 2. Historical product violations and migration owners

| File | Product behavior currently owned | Migration destination / closure |
| --- | --- | --- |
| `scripts/prompt-evaluate.py` (5,078 lines) | Paired task execution, rendering/repair assembly, attempt eligibility, scoring, source/workspace orchestration and evidence assembly. | `prompt_evaluate` plus existing renderer/scorer and shared Align task/repair owners. The native `prompt_task` owner now covers rendered-prompt and provider-request identity; complete attempt, workspace, repair and publication orchestration remains to be connected. Remove the Python launch and source-chunk bootstrap together. |
| `scripts/prompt-measurement-adapter.py` | Parses provider output into edits, builds a patch, orchestrates its workspace and validation, and produces task measurements. | Align task/edit/validation owners. Calling Align only for provider wire generation does not make the rest an independent oracle. |
| `scripts/prompt-repair-adapter.py` | Extends measurements with the actual validated edit set and repair evidence. | Same task/evidence owner, preserving versioned semantics. |
| `scripts/prompt-template-adapter.py` | Classifies edit refusals and carries completion content used by subsequent repair decisions. | Same task/repair owner; never identify the edit contract by a Python filename. |
| `scripts/prompt-fixed-adapter.py` | Implements the selected fixed-patch task branch and measurement production inside the normal evaluator. | Internal Align `FIXTURE_PATCH` dispatch; historical external fixture adapter may remain frozen. |
| `scripts/prompt-snapshot-helper.py` | Workspace preflight, complete tree/file snapshots, metadata/digests and host observations used for task admission. | Align workspace/source owners consuming the genuine filesystem/host prerequisites. |
| `scripts/prompt-source-verifier.py` | Git configuration/ancestry admission and raw-byte FILE_SET identity consumed by evaluation. | Align source owner; preserve the separately implemented verifier for external historical/gate checks. |
| `eval/runners/run-coding-task.py` | Pristine checkout and edit policy, sandbox/resource configuration, validation and cleanup verdicts. | Align task-validation owner for product use; frozen independent validation may remain for baselines. |

These eight are one transitive product consumer, not eight publication items. The inventory
freezes their exact audit bytes and assigns `ALIGN-PRODUCT-CUTOVER` to all eight. Retention after
cutover means external replay only; it does not preserve a callable Python product backend.

Observed execution paths:

```text
main prompt evaluate
  -> prompt_evaluate.evaluate_file
  -> /usr/bin/python3 -c <verified, four-chunk prompt-evaluate.py source>
     -> declared snapshot/source helpers
     -> fixed / measurement / repair / template task adapter
        -> Align prompt generate (provider serialization already in Align)
        -> Python run-coding-task.py (checkout/edit/validation policy)

main --eval eval/tasks/coding-v1.json
  -> eval.run_suite -> verify.run
  -> task.cmd/argv -> /usr/bin/python3 eval/runners/run-coding-task.py ...
```

The second path matters: searching `src/` for interpreter literals alone misses a manifest-driven
launch. The current default `--eval` smoke corpus invokes Git, not Python. The explicit coding-v1
corpus currently invokes product behavior. Cutover must refuse that old normal CLI path before
any task child, including its copied/renamed frozen launch descriptors; merely changing the
advertised corpus is insufficient. P8 of the migration ledger owns admission and the replacement
Align coding/evaluation corpus. The old corpus remains only for independent historical replay;
ordinary external target-project tests and Git smoke retain their meaning.

Normal `verify`/`--verify-loop` commands intentionally execute user-supplied build/test programs.
They may test a Python project. The distinction is ownership: foreign tests expose exit/output;
the Align application decides what to edit, retry, score, save and accept. Relabeling the bundled
coding runner as a foreign test tool would not remove its product policy.

## 3. Product source, build and native closure

The recursive local import closures of `src/main.align` and `src/ggml_spike.align` contain **71
distinct Align modules**. Inspection of `std.process` imports finds two production owners:
`src/verify.align` (explicit task/tool execution) and `src/prompt_evaluate.align` (Python
delegation). `src/c6f1_request11_adoption.align` also imports it, but is a separate test entry and
not in either product graph. Do not treat every file named `smoke` as unreachable by definition;
the entry graph, not filename filtering, establishes this distinction.

`prompt_score.align` contains Python adapter names to validate historical schema variants.
`repo_index.align` recognizes `python` as the language of target files. Their exact bytes are
recorded as data-only references, not process owners. The future checker needs both this narrow
distinction and full runtime observation; a grep for `.py` would report target code and historical
data as if they were interpreter invocations.

The build path is `make build -> run-main-with-shim -> scripts/alignc -> scripts/align-toolchain`
with optional `build-ggml-shim` Python hashing. Toolchain preparation is legitimate developer
Python. Runtime acceptance tests the resulting executable outside these launchers and outside the
checkout. Default build uses the unavailable-runtime native stub; a real inference row must use
the explicit real backend build. Successful stub execution cannot prove real model inference.

Native shipping behavior was checked across the FFI callsites and `scripts/ggml_shim.c`:

| Boundary | Evidence and decision |
| --- | --- |
| Graph/model policy | `layer_qwen2`, `layer_olmoe`, `qwen_nodes`, `olmoe_nodes` and `runtime_generation` select geometry, operation order and execution phases in Align. Retain. |
| Sampling, KV, memory policy | `runtime_sampler`, `runtime_kv`, `runtime_memory`, `runtime_execution` and their callers own sampling, budgets and identities. Retain. |
| Native resource/backend operations | `ggml_ffi`/shim wrap ggml calls, pointers, allocation and native lifetime/error translation. The shim also validates every graph node's device support in `align_gpu_graph_supported`; this is already implemented. Retain these low-level state machines. |
| Test/image C/C++ | Independent reference acquisition, fault probes and fresh-compiler controllers are outside shipping logic. Their presence does not justify new product orchestration in C. |

No Python-to-C rewrite is planned. The audit does not require replacing ggml kernels to satisfy
Align ownership. Changes to a native policy boundary during cutover must update its contract and
owner evidence; an unchanged native boundary needs no repeat GPU campaign.

## 4. Legitimate retained Python and independence

- `prompt-gate-validator.py` independently recomputes the evidence chain and score; retain it as
  an oracle and extend it independently for new record versions. The migration ledger defines
  measurement v4 and gate locator v2, including the separate product and oracle identities and
  both new/legacy explicit-input branches. It does not supply the shipping `prompt accept` decision.
- `alignpack_reader.py`, `kv_plane_reader.py`, `residency_oracle.py` and numeric/reference comparison
  modules provide separately implemented byte/arithmetic checks.
- Fixture/golden generators and the external Python coding projects remain. Do not mechanically
  rewrite them into Align or weaken tests to produce a Python-free demonstration.
- `gpu_session_client.py`, `run-gpu-session-coding`, `run-gpu-session-measurement`, the OLMoE
  diagnoses and the qualification framework remain experiment/test infrastructure. Their fixed
  retry and session clients must not become an imported shipping runtime implementation.
- Fresh compiler/image controllers, preflight/classification, CI bundle tools and smoke launchers
  remain developer infrastructure. Installing such a controller as a product dependency would
  change its role and require reclassification.

The current render parity owner loads the Python evaluator's renderer; once that evaluator leaves
the product path, retain the frozen reference algorithm outside the production import graph.
Historical adapters and verifiers can stay at digest-bound paths when current replay depends on
them. New evidence gets a new corpus and real Align producer identities. Do not mutate old hashes,
forge old measurement identities or copy Align-produced values into an allegedly independent oracle.

## 5. Align capability findings

The current pin already provides bounded process capture, binary capture, cwd/env/deadline,
retained-root regular-file opens, single-link admission, exclusive publication, private temporary
root creation, empty-directory removal, directory listing, owned JSON records and ordinary
provider transport. Sibling specs/compiler tests were inspected; no hypothetical API was used and
no compiler tests were run during this documentation task.

| Request | Why it matters now | Preparation decision |
| --- | --- | --- |
| 29 incremental digest | Python currently hashes read chunks and canonical output fragments without accumulating a second whole preimage. | Mark dependent cutover hashing blocked; retain original pack/KV acceptance separately. |
| 53 directory operations | Ordinary directory listing exists; general nested creation/type predicates do not. | Correct historical absence claim and coordinate the remaining operations with 64. |
| 64 retained tree/metadata/byte paths | Ordinary `read_dir` omits non-UTF-8 names and has no metadata/retained-directory contract. Raw FILE_SET and hostile workspace scans need complete observation. | New blocking request, with current sibling evidence and exact client acceptance cases. |
| 65 verified process inputs/containment | Current `command` does not expose retained executable/input descriptors or own nested-session descendants. | New blocking request; preserve isolation instead of substituting an ordinary child run. |
| 66 observed host identity | OS release/architecture/host CPU observations are missing; `process.cpu_count()` is quota-aware and has a different meaning. | New blocking request; do not replace observed facts with caller declarations. |

These are requirements, not shipped APIs or verified failures from new probes. Their register rows
name the current implementation evidence and planned consumer commands. Existing Requests 21, 50
and 63 remain distinct: read-only random access, memory capacity and owned JSON floats are genuine
gaps, but this audit does not automatically make them prerequisites. Current shipped reader and
borrowed-float decoding paths remain available. No Align request lifecycle advances just because
this plan records an application need.

## 6. Static consistency procedure and future enforcement

Preparation validation is read-only and model-free:

1. Enumerate `git ls-files -z`; inspect `.py` files and the first line of every extensionless file
   for a Python shebang. For local checks also consider nonignored untracked sources. Compare the
   exact unique path set with inventory `files`.
2. Validate every row's fields and its single allowed classification; count rows per category;
   hash each violation's current bytes and match `frozen_sha256`. Verify no bootstrap is silently
   inferred. Inspect Python AST docstrings, imports, functions and execution calls together with
   callers/declared task manifests for classification.
3. Inspect executable shell hosts, Make/workflow/image launchers for Python references and match
   the separate `embedded_hosts` set. These include inline code, not just `.py` filenames.
4. Traverse the two product entry import graphs, inspect process imports and interpreter/helper
   literals after excluding comments; compare the recorded launch and data-only source hashes.
   Inspect manifest-selected argv and the documented normal build/CLI paths separately.
5. Check ledger/request/roadmap/handoff consistency and `git diff --check`. No product compile,
   source test, platform qualification or performance measurement is needed for this audit data
   and documentation checkpoint. Publication, if later requested, follows `scripts/pre-pr`'s
   actual classifier; the JSON inventory is not assumed to select its Markdown-only lane.

The [migration ledger](specs/align-product-boundary.md) defines the checker and its
mutation tests, implemented after preparation was approved. It must reject unclassified
Python, new repository-local interpreter delegation, newly selected bundled Python task commands,
packaged/normal Python dependencies, and unrecorded growth of a temporary implementation.
During migration the default check reports frozen debt explicitly; the strict check has no
product exception. Classification changes and frozen-hash updates require a reviewed disposition,
not automatic acceptance from editing the inventory.

Static matching alone cannot prove arbitrary dynamic argv, wrappers, native exec, service
delegation or packaged dependency closure. The final independent acceptance therefore executes
relocated product outputs without Python or repository scripts, observes descendant execution,
and separately exercises a Python target project's explicitly allowed test process. Those tests,
not a language-count statistic or a PATH-only trick, establish the final architectural boundary.

## 7. Preparation review and next action

One fresh independent adversarial high-effort review covered all 14 candidate paths, including
governance, architecture/ordering, every audit classification, wire and closure contracts, and
the Align prerequisites. Reviewer: `boundary_plan_review` (Wegener). Reviewed branch:
`agent/align-product-boundary-plan`, HEAD `312dd65714036f9587329386b5fdbd65e91b97b9` plus its
uncommitted candidate. Base-branch tip (`origin/main`) and merge base were both
`00988ca874824a3aa5a1396dee85aab1ff5574ac`. The reviewed 14-file manifest has SHA-256
`410871bfd6ae33ac7d44ed555f3dc77994c1ab2c325a5b2e4d37b7dfc96924e6`, formed from sorted
`path<TAB>sha256<LF>` entries. That digest identifies the reviewed candidate before repair,
not the current working-tree bytes.

Verdict: changes required. Complete findings and dispositions:

| Finding | Validated evidence | Disposition in the consolidated documentation repair |
| --- | --- | --- |
| P1: measurement producer identity was not migrated | `TaskMeasurement` v2/v3 requires `base_adapter_runtime_identity`; the independent validator requires its `PYTHON:` tag. Request/task/probe changes alone leave new evidence invalid or falsely attributed. | Accepted. P4/section 3.1 now define measurement v4, required Align identity at every attempt, old/new field exclusion, provider/fixture presence rules and A1/A5 golden/mutation cases. |
| P2: independent gate locator/input transition was missing | `PromptGateSourceLocator` v1, source-policy validation, environment binding and the explicit generation-child CLI still require the old helper/interpreter identities. | Accepted. Section 3.1 now defines locator v2, separate oracle/product bindings, explicit product input pair, version/error rules, preserved v1 replay and exact A5 gate owners. |
| P2: historical `--eval` coding execution remained selectable | `eval.run_suite` dispatches the frozen coding-v1 task's Python runner through `verify.run`; advertising a new corpus does not remove it. | Accepted. P8/section 3.3 require complete pre-dispatch admission and legacy refusal, identify the Align coding replacement and retain external target tests. A2/A4 name all refusal and replacement cases. |

No finding was rejected or deferred. The author inspected the repair against the existing source,
checked all ledger/closure/owner references and repeated affected static validation. These repairs
complete the originally reviewed migration scope; they add no implementation or new feature
capability. The review envelope is local preparation evidence; no PR or repair commit exists.

Preparation is complete. When implementation is requested, coordinate the recorded Align
prerequisite wave, then implement the checker and the full consumer cutover on the later
implementation branch. GPU performance work remains deferred.
