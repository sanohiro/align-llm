# Check gate topology

## 1. Scope

This enabling design makes the repository's aggregate verification targets state their actual
coverage. It does not change scoring semantics, the compiler pin, product behavior, or the
environment requirements of an existing focused check. The implementation necessarily refreshes
the canonical C0 baseline measurement and immutable oracle because `Makefile` is an identity-bound
baseline artifact; retaining the old record after changing that file would make `baseline-check`
fail and would falsely bind the measurement to bytes it did not use.

The implementation slice will update the `Makefile`, add `scripts/check-gate-topology`, and update
the hosted GitHub Actions workflow, contributor documentation, pull request template, and durable
handoff state. It will also use the existing pending-record, immutable-oracle, and finalizer flow to
refresh `eval/baselines/coding-v1-reference.json`,
`eval/expected/coding-v1-reference-oracle.json`, and
`eval/expected/coding-v1-reference.sha256`. It will not add a third-party runner, weaken a failure,
change the evaluation contract, or make an unsupported check optional inside a gate that claims to
run it.

The original topology design was authored against align-llm merge commit
`c20e919f4cbaa493e57ef79a9b638086d181cae0`. Its baseline-identity correction was audited against
merged topology design commit `aad72ff8cf4b944bdd48cdf7052a1faff136d33b`. Both use pinned Align
commit `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| `make gate-topology-check` | Export the three Make-owned lists into `ALIGN_LLM_HOSTED_CHECK_TARGETS`, `ALIGN_LLM_CAPABLE_ONLY_CHECK_TARGETS`, and `ALIGN_LLM_SERIAL_CHECK_AGGREGATES` for this target, then invoke `python3 scripts/check-gate-topology` without interpolating list text into the recipe shell. The script constructs a canonical byte report from those values and compares it with an expected byte string embedded in that script. Fail before claiming an aggregate result if any list drifts without an intentional oracle update. |
| `make hosted-checks` | Run `gate-topology-check`, then consume the compiler selected by `ALIGNC` and run `format-check`, `check`, `build`, `eval-smoke`, `loop-smoke`, `provider-smoke`, `index-smoke`, `test-selection-smoke`, `patch-eval-smoke`, `verify-loop-smoke`, and `failure-memory-smoke` in that order. It does not build Align and does not run `eval-coding` or `baseline-check`. |
| `make capable-checks` | Consume the compiler selected by `ALIGNC` and run the complete `hosted-checks` graph, then `eval-coding` and `baseline-check` in that order. It does not build Align. |
| `make ci` | Verify `.align-revision`, release-build the pinned sibling Align compiler, require that compiler to be executable, and invoke `capable-checks` with `ALIGNC` set to that exact release compiler. This remains the canonical complete local or capable-runner gate. |
| GitHub Actions pull-request gate | Check out `.align-revision`, run `make align-build`, require the resulting release compiler, and invoke `make hosted-checks` with `ALIGNC` set to it. |
| Focused targets | Keep their existing commands and semantics. `failure-memory-smoke` continues to depend on `verify-loop-smoke`; naming both in an aggregate graph does not execute the shared recipe twice in one Make invocation. |
| Canonical C0 baseline | Record two deterministic-reference samples from a clean implementation source commit containing the final `Makefile`; commit the derived immutable oracle; finalize the canonical baseline with that full oracle commit; and keep both source and oracle commits as ancestors of the final reviewed head and merge result. |

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
- The coding-v1 baseline artifact manifest already includes `Makefile`. Therefore any implementation
  commit that changes the check graph is a new baseline source identity even when task verdicts and
  scoring semantics remain unchanged.
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
- `eval/runners/README.md`, `eval/baselines/README.md`,
  `eval/runners/record-baseline.py`, `scripts/finalize-canonical-baseline.py`, and
  `eval/runners/verify-baseline.py` remain authoritative for the general baseline flow,
  finalization, and verification. Section 2.4 fixes the exact oracle projection and commit topology
  for this identity-coupled implementation.

### 2.4 Baseline commit and merge topology

The implementation pull request uses this ordered history:

1. **Implementation source commit** — contains the final state of every recorded baseline artifact,
   including the new `Makefile` topology, plus the current checker, workflow, contributor
   documentation, and durable handoff update. The worktree is clean. Later review changes outside
   the recorded artifact set do not alter the baseline identity.
2. **Pending measurement** — from that clean source commit, run:

   ```text
   python3 eval/runners/record-baseline.py \
     --corpus eval/tasks/coding-v1.json \
     --provider deterministic-reference \
     --model checked-in-patch \
     --prompt-version none \
     --samples 2 \
     --output eval/baselines/.coding-v1-reference.pending.json
   ```

3. **Immutable oracle commit** — project the pending record into
   `eval/expected/coding-v1-reference-oracle.json` using exactly these ordered fields:
   `schema_version`, `baseline_id`, `align_llm_commit`, `align_revision`, `corpus`, `artifacts`,
   `provider`, `environment`, `sample_count`, `runs`, and `aggregate`; write indented UTF-8 JSON
   with one final LF by running:

   ```text
   python3 - \
     eval/baselines/.coding-v1-reference.pending.json \
     eval/expected/coding-v1-reference-oracle.json <<'PY'
   import json
   import sys
   from pathlib import Path

   fields = (
       "schema_version",
       "baseline_id",
       "align_llm_commit",
       "align_revision",
       "corpus",
       "artifacts",
       "provider",
       "environment",
       "sample_count",
       "runs",
       "aggregate",
   )
   pending = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
   oracle = {field: pending[field] for field in fields}
   Path(sys.argv[2]).write_text(
       json.dumps(oracle, indent=2) + "\n",
       encoding="utf-8",
   )
   PY
   ```

   Commit only the oracle.
4. **Canonical finalization commit** — run:

   ```text
   python3 scripts/finalize-canonical-baseline.py \
     --input eval/baselines/.coding-v1-reference.pending.json \
     --oracle-commit <full-immutable-oracle-commit>
   ```

   Remove the pending file after finalization, then commit the canonical baseline and digest.
5. **Review follow-ups and invalidation** —
   - a change to `Makefile` or any other recorded input artifact invalidates the measurement and
     requires a new clean source commit, pending measurement, oracle commit, and finalization;
   - a change to the oracle before finalization requires regenerating the exact projection from the
     same pending measurement, committing only the oracle, and finalizing against the new commit;
   - the canonical baseline and digest are finalizer-owned and may not be edited manually; rerun the
     finalizer before committing them; and
   - after the pending file has been removed and finalization committed, any change to the oracle,
     canonical baseline, or digest restarts the full sequence. A path outside both the recorded input
     manifest and these three owned outputs still requires normal exact-head checks and reviews but
     does not rewrite the baseline.

The pull request must use a merge commit. Squash and rebase merging are forbidden because they would
make the recorded implementation source, immutable oracle, or finalization commit unreachable from
the merged history. Before merge, all three full commits must be ancestors of the exact reviewed
head; after merge, all three must be ancestors of the resulting `main`.

The implementation records full `SOURCE_COMMIT`, `ORACLE_COMMIT`, and `FINALIZATION_COMMIT` values.
The source and oracle values must equal the identities embedded in the finalized baseline, not
merely name another valid ancestor chain. All structural Git inspection runs in an empty
environment with replacement objects and ambient Git configuration disabled, matching the
baseline recorder and verifier's repository-isolation boundary. Run these exact checks before
merge:

```text
clean_git() {
  env -i \
    PATH=/usr/bin:/bin \
    LC_ALL=C \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_ATTR_NOSYSTEM=1 \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_NO_REPLACE_OBJECTS=1 \
    XDG_CONFIG_HOME=/dev/null \
    git "$@"
}
python3 - "$SOURCE_COMMIT" "$ORACLE_COMMIT" <<'PY'
import json
import sys
from pathlib import Path

baseline = json.loads(
    Path("eval/baselines/coding-v1-reference.json").read_text(encoding="utf-8")
)
expected = (baseline["align_llm_commit"], baseline["canonical_oracle_commit"])
actual = (sys.argv[1], sys.argv[2])
if actual != expected:
    raise SystemExit(
        "recorded provenance differs: "
        f"expected source/oracle {expected[0]} {expected[1]}, "
        f"received {actual[0]} {actual[1]}"
    )
PY
clean_git merge-base --is-ancestor "$SOURCE_COMMIT" "$ORACLE_COMMIT"
clean_git merge-base --is-ancestor "$ORACLE_COMMIT" "$FINALIZATION_COMMIT"
clean_git merge-base --is-ancestor "$FINALIZATION_COMMIT" HEAD
test "$(clean_git diff-tree --no-commit-id --name-only -r "$ORACLE_COMMIT")" = \
  "eval/expected/coding-v1-reference-oracle.json"
test "$(clean_git diff-tree --no-commit-id --name-only -r "$FINALIZATION_COMMIT")" = \
  "$(printf '%s\n' \
    eval/baselines/coding-v1-reference.json \
    eval/expected/coding-v1-reference.sha256)"
clean_git show "$SOURCE_COMMIT:Makefile" | cmp - Makefile
clean_git show \
  "$ORACLE_COMMIT:eval/expected/coding-v1-reference-oracle.json" | \
  cmp - eval/expected/coding-v1-reference-oracle.json
clean_git show \
  "$FINALIZATION_COMMIT:eval/baselines/coding-v1-reference.json" | \
  cmp - eval/baselines/coding-v1-reference.json
clean_git show \
  "$FINALIZATION_COMMIT:eval/expected/coding-v1-reference.sha256" | \
  cmp - eval/expected/coding-v1-reference.sha256
test -z "$(clean_git log --format=%H "$SOURCE_COMMIT"..HEAD -- Makefile)"
test -z "$(clean_git log --format=%H "$ORACLE_COMMIT"..HEAD -- \
  eval/expected/coding-v1-reference-oracle.json)"
test -z "$(clean_git log --format=%H "$FINALIZATION_COMMIT"..HEAD -- \
  eval/baselines/coding-v1-reference.json \
  eval/expected/coding-v1-reference.sha256)"
```

After merge, the source, oracle, and finalization commits must each be ancestors of refreshed
`main`, and the persisted-identity comparison, four final-tree byte comparisons, and three
no-later-change checks above must still pass with `HEAD` replaced by refreshed `main` in the same
isolated Git environment.

### 2.5 Measurement interpretation

The refreshed record uses the same `coding-v1` corpus, deterministic-reference provider,
checked-in-patch model, `none` prompt version, two samples, and pinned Align commit. Both task
verdicts and both run summaries must remain passing and structurally equal to the fixed corpus
expectation. The pull request reports the prior and refreshed time-to-passing-patch samples,
aggregate, and recorded environment, but makes no performance claim: this is an artifact-identity
refresh, not an optimization experiment. Any improvement or regression claim requires a separate
reproducible comparison with controlled hardware and sample count.

## 3. Coverage and exclusions

The hosted gate excludes only:

- `eval-coding`, because its containment contract requires Linux child-subreaper support, a working
  bubblewrap user namespace, and `prlimit`, and GitHub-hosted runners do not provide the required
  nested user namespace; and
- `baseline-check`, because routine verification and any required identity-coupled refresh belong
  to a capable runner rather than ordinary hosted feature checks. This implementation performs the
  exceptional refresh only because it changes the identity-bound `Makefile`.

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
| Baseline source identity | implementation source commit | final identity-bound `Makefile` is clean and committed before recording | Pending record `align_llm_commit` equals the source commit and its Makefile digest equals `git show <source>:Makefile`. |
| Immutable oracle | oracle commit | exact canonical projection of the pending record | Oracle commit contains only the ordered projection; the existing direct timing-mutation regression proves whole-projection equality is enforced, and final-tree bytes equal the oracle commit. |
| Canonical finalization | finalization commit | finalizer binds full oracle commit and writes digest | `make baseline-check` passes; pending file is absent; canonical digest matches. |
| Baseline commit chain | finalized baseline, source, oracle, finalization, final reviewed head, and merge result | persisted source/oracle fields equal the named commits; strict source → oracle → finalization → head/main ancestry in an isolated Git environment; merge method is `merge` | Exact identity and ancestry checks pass without replacement objects or ambient Git configuration; oracle commit changes only the oracle, and finalization commit changes only canonical baseline plus digest. |
| Post-record input change | author/reviewer | re-record from a new clean source commit | Matrix-to-diff audit compares changed paths with the recorded input manifest; any overlap invalidates the complete prior sequence. |
| Post-record output change | author/reviewer | regenerate through the owning projection/finalizer before finalization; restart the full sequence afterward | Final-tree oracle, baseline, and digest bytes equal their named owner commits; no later commit changes those paths. |
| Measurement interpretation | pull request evidence | two deterministic-reference samples on the recorded environment | Both samples PASS; prior and refreshed timings are reported without a performance claim. |
| Topology-checker persisted format | N/A | its byte oracle is embedded in the script; no topology file is created | N/A. |
| Canonical baseline JSON | existing schema version 1 | recorder emits indented UTF-8 JSON plus final LF; finalizer changes only `canonical_oracle_commit` | `make baseline-check` validates exact fields, identities, aggregates, malformed input, immutable oracle, and digest. |
| Immutable baseline oracle JSON | section 2.4 ordered projection | indented UTF-8 JSON plus final LF, committed before finalization | Projection command is reproducible; final-tree bytes equal `git show <oracle-commit>:<oracle-path>`; timing mutation is rejected. |
| Canonical digest text | finalizer | lowercase SHA-256, two ASCII spaces, canonical baseline path, final LF | `make baseline-check` recomputes and compares the exact line; final-tree bytes equal the finalization commit. |
| Partial baseline output | unchanged finalizer | a failed or interrupted run must not be committed; rerun finalizer and require exact baseline/digest owner paths | DEFERRED fault injection: finalizer behavior is unchanged. Clean-worktree, exact path-set, digest, byte-equality, and `make baseline-check` gates prevent partial output from merging. |
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
- Record, project, commit, and finalize the canonical C0 baseline from the final clean implementation
  source commit using section 2.4. Verify the strict source → oracle → finalization → head chain,
  equality with both commit identities persisted in the finalized baseline, exact per-commit path
  sets, final-tree byte equality, pending-file absence, digest, replacement-object isolation, and
  the existing immutable-oracle timing-mutation regression.
- Obtain a passing hosted required check using `make hosted-checks`.
- Review the full implementation against `docs/review-checklist.md`, including aggregate-name
  accuracy and any shared-target execution or cleanup regression.

The design and implementation are separate pull requests. The implementation and baseline refresh
remain one automation enabling slice because the baseline identity includes `Makefile`: separating
them would leave an intermediate `main` whose canonical baseline fails its own artifact check. The
pull request keeps implementation, oracle, and finalization in separately reviewable commits and
records why this identity-coupled exception cannot be split safely.
