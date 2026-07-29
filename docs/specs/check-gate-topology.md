# Check gate topology

## 1. Scope

This enabling design makes the repository's aggregate verification targets state their actual
coverage. It does not change an evaluation oracle, compiler pin, product behavior, or the
environment requirements of an existing focused check.

The implementation slice will update the `Makefile`, add `scripts/check-gate-topology`, and update
the hosted GitHub Actions workflow, contributor documentation, pull request template, and durable
handoff state. It will not add a third-party runner, weaken a failure, or make an unsupported check
optional inside a gate that claims to run it.

The design was authored against align-llm merge commit
`c20e919f4cbaa493e57ef79a9b638086d181cae0` and pinned Align commit
`d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| `make gate-topology-check` | Export the three Make-owned lists into `ALIGN_LLM_HOSTED_CHECK_TARGETS`, `ALIGN_LLM_CAPABLE_ONLY_CHECK_TARGETS`, and `ALIGN_LLM_SERIAL_CHECK_AGGREGATES` for this target, then invoke `python3 scripts/check-gate-topology` without interpolating list text into the recipe shell. The script constructs a canonical byte report from those values and compares it with an expected byte string embedded in that script. Fail before claiming an aggregate result if any list drifts without an intentional oracle update. |
| `make hosted-checks` | Run `gate-topology-check`, then consume the compiler selected by `ALIGNC` and run `format-check`, `check`, `build`, `eval-smoke`, `loop-smoke`, `provider-smoke`, `index-smoke`, `test-selection-smoke`, `patch-eval-smoke`, `verify-loop-smoke`, and `failure-memory-smoke` in that order. It does not build Align and does not run `eval-coding` or `baseline-check`. |
| `make capable-checks` | Consume the compiler selected by `ALIGNC` and run the complete `hosted-checks` graph, then `eval-coding` and `baseline-check` in that order. It does not build Align. |
| `make ci` | Verify `.align-revision`, release-build the pinned sibling Align compiler, require that compiler to be executable, and invoke `capable-checks` with `ALIGNC` set to that exact release compiler. This remains the canonical complete local or capable-runner gate. |
| GitHub Actions pull-request gate | Check out `.align-revision`, run `make align-build`, require the resulting release compiler, and invoke `make hosted-checks` with `ALIGNC` set to it. |
| Focused targets | Keep their existing commands and semantics. `failure-memory-smoke` continues to depend on `verify-loop-smoke`; naming both in an aggregate graph does not execute the shared recipe twice in one Make invocation. |

### 2.1 Inputs and defaults

- `ALIGN_REPO` defaults to `../align`. The hosted workflow supplies its checked-out Align path.
- `ALIGNC` defaults to `./scripts/alignc` for direct `hosted-checks` and `capable-checks` calls.
- `ci` deliberately overrides `ALIGNC` only in its recursive check invocation with
  `$(ALIGN_REPO)/target/release/alignc` after the pin and build gates succeed.
- All task corpora, expected outputs, timeouts, environment requirements, and other focused-target
  inputs remain owned by their existing targets and files.
- `HOSTED_CHECK_TARGETS`, `CAPABLE_ONLY_CHECK_TARGETS`, and `SERIAL_CHECK_AGGREGATES` are
  `override :=` Make variables. Command-line or inherited environment assignments cannot replace the
  checked graph. The `gate-topology-check` target uses target-specific `override export`
  assignments to replace any caller-supplied `ALIGN_LLM_*` topology environment values without
  recipe-shell interpolation.
- `-j` and inherited `MAKEFLAGS` do not parallelize the immediate prerequisites of
  `hosted-checks` or `capable-checks`. The implementation declares both aggregates under GNU Make's
  target-scoped `.NOTPARALLEL`; focused recipes retain ownership of any internal concurrency.
- `-k`/`--keep-going`, `-i`/`--ignore-errors`, `-n`/`--just-print`, and equivalent inherited
  `MAKEFLAGS` are diagnostic caller modes, not valid verification evidence. They deliberately
  change failure or execution semantics and must not appear in a claimed gate command.
- No unnamed configuration input is added. Existing tool and operating-system requirements remain
  explicit in their owning scripts and documentation.

### 2.2 Result, error, ownership, and allocation

- Success is process exit status zero after every target in the selected graph succeeds.
- The first failing prerequisite or recipe makes the aggregate fail nonzero. No aggregate catches,
  retries, downgrades, or replaces a focused failure.
- Diagnostics remain the stdout and stderr of Make and the failing owner command. No new persisted
  result format is introduced.
- The aggregate prerequisite order in the ledger is deterministic even when the caller supplies
  `-j`. This preserves stable first-failure reporting and prevents aggregate-level overlap between
  checks that share the built executable or repository state.
- Process ownership, cleanup, files, and allocation remain with the existing focused targets.
  The aggregate targets introduce no long-lived process, file, cache, or allocation.

### 2.3 Identity, versioning, and sources of truth

- The checked compiler identity remains `.align-revision`; no new schema version or cache identity
  applies.
- The `Makefile` is the authoritative check graph.
- Its named `HOSTED_CHECK_TARGETS`, `CAPABLE_ONLY_CHECK_TARGETS`, and
  `SERIAL_CHECK_AGGREGATES` variables feed both aggregate prerequisites or `.NOTPARALLEL` and the
  three target-specific exported `ALIGN_LLM_*` values read by `scripts/check-gate-topology`.
- `scripts/check-gate-topology` owns an embedded exact byte-string oracle. Changing
  gate membership, order, or serialization therefore requires a visible Makefile-and-script update.
- `.github/workflows/ci.yml` must call the public hosted aggregate rather than repeat its target list.
- `eval/README.md`, `docs/align-development.md`, and `.github/PULL_REQUEST_TEMPLATE.md` describe how
  callers select and report the applicable aggregate or focused target; they must not maintain a
  second normative target list.
- `CLAUDE.md` remains authoritative for when `make ci` is required, especially Align request
  adoption and full semantic verification.

## 3. Coverage and exclusions

The hosted gate excludes only:

- `eval-coding`, because its containment contract requires Linux child-subreaper support, a working
  bubblewrap user namespace, and `prlimit`, and GitHub-hosted runners do not provide the required
  nested user namespace; and
- `baseline-check`, because the immutable C0 artifact is refreshed in a workflow separate from
  feature slices, while its routine verification belongs to the capable gate rather than ordinary
  hosted feature checks.

The capable gate adds exactly those two targets. It also includes every C1-C5 focused target through
the hosted graph. New focused roadmap gates must be assigned deliberately to the hosted graph, the
capable-only set, or both through dependency, with the reason recorded in the owning design and
documentation.

`make ci` is not evidence that an arbitrary future focused target ran unless that target is
reachable in this authoritative graph at the tested commit.

## 4. Determinism and validation order

The aggregate graph performs no new semantic validation. Its deterministic dependency constraints
are:

1. `gate-topology-check` succeeds before the hosted focused checks;
2. `hosted-checks` runs its focused targets in the ledger order;
3. `capable-checks` completes `hosted-checks`, then `eval-coding`, then `baseline-check`;
4. `ci` completes `align-revision` before `align-build`;
5. `ci` completes `align-build` and the compiler executable check before its recursive
   `capable-checks` invocation;
6. focused targets retain their current `build` prerequisites; and
7. `failure-memory-smoke` retains its current `verify-loop-smoke` prerequisite.

Under the supported verification flags, the first failing command in that sequence reports the
aggregate failure and prevents later aggregate prerequisites from running. Within each focused
target, its existing validation and error precedence remain authoritative.

## 5. Topology inputs and oracle

The normal script mode accepts no arguments. It reads exactly the three named `ALIGN_LLM_*`
topology values from its environment in hosted, capable-only, serialized order. Each value must
encode as ASCII. The script constructs exactly these three lines in memory, in this order, with one
LF after every line including the last:

```text
hosted=gate-topology-check format-check check build eval-smoke loop-smoke provider-smoke index-smoke test-selection-smoke patch-eval-smoke verify-loop-smoke failure-memory-smoke
capable-only=eval-coding baseline-check
serialized=hosted-checks capable-checks
```

The field names, `=` delimiter, single ASCII spaces, target order, and final LF are normative.
Non-ASCII input fails before report construction. Empty arguments, leading or trailing spaces,
repeated spaces, extra tokens, missing tokens, duplicate targets, and reordered targets construct a
non-matching report.

`scripts/check-gate-topology` is a Python 3 program. Normal-mode validation and failure precedence
is:

1. a non-empty argument vector: print one English arity diagnostic to stderr and return nonzero;
2. the first missing environment value in hosted, capable-only, serialized order: print one English
   missing-input diagnostic naming that field and return nonzero;
3. the first present value in that order that does not encode as ASCII: print one English
   input-encoding diagnostic naming that field and return nonzero;
4. canonical report bytes unequal to the embedded oracle: print one English mismatch diagnostic
   plus bounded escaped expected and actual byte representations to stderr and return nonzero; and
5. exact match: print `check gate topology: PASS` plus LF to stdout and return zero.

Normal mode reads no stdin, creates no file, launches no child process, and owns only its selected
environment strings and constructed byte arrays. Expected and actual diagnostic inputs are each
capped at 4,096 bytes before escaping, with an ASCII truncation marker inside that cap. This
diagnostic cap does not affect the full byte comparison. Embedded NUL cannot cross the
operating-system environment boundary and therefore cannot reach the script.

With the sole argument `--self-test`, the script feeds synthetic argument vectors and environment
maps through the same validation, construction, comparison, and diagnostic helpers. Self-test mode
returns zero only after the exact three values are accepted and each of these cases is rejected
with its specified error class: wrong arity, missing value, non-ASCII input, one added target, one
removed target, one duplicated target, one reordered target, one removed serialized aggregate,
empty field, leading space, trailing space, and repeated space.

The self-test also creates one temporary directory, invokes
`make --no-print-directory gate-topology-check` through a subprocess argument vector with dangerous
command-line overrides containing backticks, dollar-parenthesis text, quotes, backslashes, and a
marker-writing shell command, and supplies matching dangerous `ALIGN_LLM_*` values in the child
environment. It requires the target to emit the exact normal PASS line while the marker remains
absent. It captures and bounds that child output, removes the temporary directory on success or
failure, and does not modify the repository. On success self-test mode prints `check gate topology
self-test: PASS` plus LF and nothing else.

## 6. Closure matrix

| Path | Owner | Intended implementation | Regression evidence |
| --- | --- | --- | --- |
| Topology success | `scripts/check-gate-topology` | three target-specific exported values, canonical byte construction, and embedded exact oracle | `make gate-topology-check` emits the single PASS line and returns zero. |
| Topology membership drift | script self-test | synthetic environment maps through the production comparator | Add/remove/duplicate/reorder and serialized-set negative cases all return nonzero internally. |
| Topology malformed input | script self-test | synthetic argument vectors and environment maps through production validation helpers | Arity, missing, ASCII, empty, and whitespace negative cases all reach their specified error class. |
| Make-to-shell boundary | `Makefile` plus script self-test | `override :=` lists and target-specific `override export`; recipe contains no list expansion | Dangerous command-line and environment overrides are ignored, the gate passes, and no marker is created. |
| Direct hosted success | `Makefile` | serialized `hosted-checks` prerequisite graph | Run with the pinned compiler; all hosted-compatible focused smokes pass. |
| Direct hosted failure | owning focused target | Make propagates nonzero | Invoke the aggregate with an invalid `ALIGNC`; the graph fails nonzero without fallback. |
| Direct capable success | `Makefile` | `capable-checks` extends hosted graph | Run `make ci` on a capable Linux host; coding and baseline gates plus C1-C5 focused gates pass. |
| Direct capable failure | owning focused target | Make propagates nonzero | Existing focused negative-path regressions remain required; no aggregate suppression exists. |
| Pin mismatch | `scripts/check-align-revision` | unchanged `align-build` prerequisite | DEFERRED: this slice does not change the owner script or prerequisite edge. The implementation review must confirm both are unchanged; automated mismatched-checkout fault injection belongs to a separate pin-hardening slice. |
| Compiler build failure | Align Cargo workspace | unchanged `align-build` recipe | DEFERRED: this slice does not change the Cargo recipe or its shell failure propagation. The implementation review must confirm both are unchanged; fake-toolchain fault injection belongs to a separate pin-hardening slice. |
| Missing built compiler | `ci` recipe | retain executable guard before recursive Make | DEFERRED: the implementation review must confirm the guard remains before `capable-checks`; a clean temporary pinned checkout plus successful fake Cargo build is the future fault-injection fixture, outside this topology slice. |
| Hosted workflow success | `.github/workflows/ci.yml` | build pin, then call `hosted-checks` | Required Actions check passes and its log names the aggregate invocation. |
| Hosted unsupported checks | workflow plus this plan | absent from `hosted-checks` | `make gate-topology-check` proves `eval-coding` and `baseline-check` appear only in the capable-only list. |
| Complete graph membership | `Makefile` | named aggregate prerequisites | `make gate-topology-check` proves the exact hosted list, capable-only additions, and serialized aggregates. |
| Existing focused cleanup | focused scripts | unchanged | Existing ordinary, timeout, and abnormal cleanup regressions continue to own these paths. |
| Parallel invocation | GNU Make `.NOTPARALLEL` | serialize both aggregate prerequisite lists | `make -j8 ci` passes with the declared aggregate order; the topology oracle proves both targets remain in the serialized set. |
| Persisted format | N/A | the oracle is embedded in the script; no file is created | N/A. |
| Internal text boundary | `Makefile` plus `scripts/check-gate-topology` | three shell-uninterpreted environment values become exact labeled LF-terminated bytes | Script self-test covers exact success, arity, missing values, encoding, whitespace, membership, order, and dangerous override text. |
| Argument/result ownership lifecycle | N/A | Make target names and scalar variables are not Align values | N/A. |
| Implementation-only ownership types | N/A | no ownership type is added | N/A. |
| Native boundary and embedded NUL | operating-system environment | N/A: environment values cannot contain NUL; no file or wire input exists | N/A with stated platform reason. |
| Monomorphization, interface, whole/per-unit parity | N/A | no Align code or interface changes | Existing `check` and `build` remain in both graphs. |
| Runtime provenance or allocation parity | N/A | no runtime behavior or allocation change | N/A. |

## 7. Acceptance and pull request boundaries

### Design slice

- This document passes `git diff --check` and documentation formatting checks.
- A fresh independent adversarial review validates the ledger, closure matrix, exclusions,
  implementation boundary, and exact target membership.
- The design merges before Makefile or workflow implementation begins.

### Implementation slice

- Add the two public aggregate targets and route `ci` and GitHub Actions through them.
- Add the non-overridable Make lists, target-specific environment export, `gate-topology-check`, and
  `scripts/check-gate-topology` with its environment boundary, embedded byte oracle, and self-tests.
- Update only the contributor-facing descriptions and pull request reporting fields needed to
  distinguish complete, hosted, and focused verification.
- Run `make gate-topology-check`.
- Run `python3 scripts/check-gate-topology --self-test`; all specified negative cases pass by being
  rejected.
- Run `make hosted-checks` with the pinned release compiler.
- Run `make -j8 ci` on a capable host to prove the aggregate serialization contract under inherited
  parallel Make flags.
- Obtain a passing hosted required check using `make hosted-checks`.
- Review the full implementation against `docs/review-checklist.md`, including aggregate-name
  accuracy and any shared-target execution or cleanup regression.

The design and implementation are separate pull requests. The implementation remains a single
automation enabling slice because the Makefile graph, workflow call site, and contributor-facing
names must change together to avoid an interval with misleading verification claims.
