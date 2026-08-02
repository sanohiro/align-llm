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

The later Git 2.45 locked-input enabling slice extends this authoritative graph with exactly one
hosted-compatible focused target, `git245-locked-inputs-unit`, immediately after
`gate-topology-check`. That extension is offline, starts CPython through a fixed `/usr/bin/env -i`
boundary, and does not consume the Align compiler. Its implementation therefore refreshes the
Makefile-bound baseline through the same section 2.4 source -> oracle -> finalization sequence and
changes no serialized aggregate or capable-only membership.

The original topology design was authored against align-llm merge commit
`c20e919f4cbaa493e57ef79a9b638086d181cae0`. Its baseline-identity correction was audited against
merged topology design commit `aad72ff8cf4b944bdd48cdf7052a1faff136d33b`. Both use pinned Align
commit `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`. The aggregate-serialization
portability correction was audited against merged baseline-identity design commit
`e0c37a7381c0e2edb57afd133ec95cdf11933f1e`.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| `make gate-topology-check` | Export the three Make-owned lists into `ALIGN_LLM_HOSTED_CHECK_TARGETS`, `ALIGN_LLM_CAPABLE_ONLY_CHECK_TARGETS`, and `ALIGN_LLM_SERIAL_CHECK_AGGREGATES` for this target, then invoke `python3 scripts/check-gate-topology` without interpolating list text into the recipe shell. The script constructs a canonical byte report from those values and compares it with an expected byte string embedded in that script. Fail before claiming an aggregate result if any list drifts without an intentional oracle update. |
| `make hosted-checks` | Run `gate-topology-check`, then clear `MAKEFLAGS` and `GNUMAKEFLAGS`, launch one recursive GNU Make with an explicit `-j1`, and run `git245-locked-inputs-unit`, `format-check`, `check`, `build`, `eval-smoke`, `loop-smoke`, `provider-smoke`, `index-smoke`, `test-selection-smoke`, `patch-eval-smoke`, `verify-loop-smoke`, `failure-memory-smoke`, and `prompt-model-smoke` as that child Make's ordered goals. All targets after the locked-input unit consume the compiler selected by `ALIGNC` where applicable. It does not build Align and does not run `eval-coding` or `baseline-check`. |
| `make capable-checks` | Run `gate-topology-check`, then clear `MAKEFLAGS` and `GNUMAKEFLAGS`, launch one recursive GNU Make with an explicit `-j1`, consume the compiler selected by `ALIGNC`, and run the complete hosted focused-target list followed by `eval-coding` and `baseline-check` as that child Make's ordered goals. It does not invoke `hosted-checks` as a nested aggregate and does not build Align. |
| `make ci` | Verify `.align-revision`, release-build the pinned sibling Align compiler, require that compiler to be executable, and invoke `capable-checks` with `ALIGNC` set to that exact release compiler. This remains the canonical complete local or capable-runner gate. |
| Aggregate coexistence | `hosted-checks`, `capable-checks`, and `ci` are the complete serialized-aggregate set. If a top-level GNU Make invocation requests one of them, that aggregate must be the invocation's sole goal. An aggregate plus any other goal, or a repeated aggregate, fails during Makefile parsing before a prerequisite or recipe runs, with `verification aggregates must be requested alone`. Separate concurrent Make processes are unsupported caller behavior and are not valid verification evidence; this slice adds no cross-process repository lock. The recursive `ci` child is a separate invocation containing only `capable-checks` and remains valid. |
| GitHub Actions pull-request gate | On the declared Ubuntu 24.04 runner with GNU Make 4.3, check out `.align-revision`, run `make align-build`, require the resulting release compiler, run `python3 scripts/check-gate-topology --self-test`, and invoke `make -j8 hosted-checks` with `ALIGNC` set to it. Preserve the aggregate recipe in the job log so review can verify the option-cleared child command, explicit `-j1`, and ordered focused-goal list. |
| Focused targets | Keep existing commands and semantics. Add only `git245-locked-inputs-unit` with the offline contract in `docs/specs/git-245-compat-image.md`. `failure-memory-smoke` continues to depend on `verify-loop-smoke`; naming both in an aggregate graph does not execute the shared recipe twice in one Make invocation. |
| Canonical C0 baseline | Record two deterministic-reference samples from a clean implementation source commit containing the final `Makefile`; commit the derived immutable oracle; finalize the canonical baseline with that full oracle commit; require the finalized record's source and oracle identities to equal those named commits; and keep the source, oracle, and finalization commits as ancestors of the final reviewed head and merge result. |

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
- `SERIAL_CHECK_AGGREGATES` is exactly `hosted-checks capable-checks ci`. A parse-time guard filters
  `MAKECMDGOALS` through that list. If the filtered result is nonempty, the complete
  `MAKECMDGOALS` list must contain exactly that one goal. Any additional or repeated goal emits the
  exact coexistence diagnostic from the ledger via `$(error ...)` before Make updates any target.
  The guard has this exact fail-closed shape after the three `override :=` graph declarations:

  ```text
  override REQUESTED_SERIAL_CHECK_AGGREGATES := \
    $(filter $(SERIAL_CHECK_AGGREGATES),$(MAKECMDGOALS))
  ifneq ($(REQUESTED_SERIAL_CHECK_AGGREGATES),)
  ifneq ($(words $(MAKECMDGOALS)),1)
  $(error verification aggregates must be requested alone)
  endif
  endif
  ```

  The continuation indentation is ordinary Makefile whitespace, not a recipe tab.
- `-j` and inherited `MAKEFLAGS` do not parallelize aggregate-level focused goals.
  `hosted-checks` and `capable-checks` each clear `MAKEFLAGS` and `GNUMAKEFLAGS` for exactly one
  recursive `$(MAKE)` and supply an explicit `-j1`. The child therefore does not inherit the
  parent's jobserver, keep-going, ignore-error, dry-run, output, or GNU Make 4.4 shuffle modes. The
  implementation must not depend on target-scoped `.NOTPARALLEL`, which is unavailable in the GNU
  Make 4.3 used by the declared Ubuntu 24.04 hosted runner. A focused recipe that needs internal
  concurrency must select it explicitly.
- The aggregate edges and recipes have this exact shape:

  ```text
  hosted-checks: gate-topology-check
  <TAB>+MAKEFLAGS= GNUMAKEFLAGS= $(MAKE) --no-print-directory -j1 \
  <TAB>  $(filter-out gate-topology-check,$(HOSTED_CHECK_TARGETS))

  capable-checks: gate-topology-check
  <TAB>+MAKEFLAGS= GNUMAKEFLAGS= $(MAKE) --no-print-directory -j1 \
  <TAB>  $(filter-out gate-topology-check,$(HOSTED_CHECK_TARGETS)) \
  <TAB>  $(CAPABLE_ONLY_CHECK_TARGETS)
  ```

  Here `<TAB>` is one literal recipe tab. Keeping all selected focused goals in one child invocation
  preserves Make's shared prerequisite de-duplication. The supported aggregate inputs `ALIGNC` and
  `ALIGN_REPO` remain exported by GNU Make and retain their values because the child Makefile
  declares them with `?=`. Clearing the two option variables deliberately does not promise
  command-line-origin propagation for undocumented Make-variable overrides whose child declarations
  use `:=`; the aggregate adds no replacement input channel for them.
- `-k`/`--keep-going`, `-i`/`--ignore-errors`, `-n`/`--just-print`, and equivalent inherited
  `MAKEFLAGS` remain diagnostic parent-caller modes, not valid verification evidence. They can
  change whether the parent prerequisite gate itself runs or propagates failure and must not appear
  in a claimed gate command. Once the aggregate recipe begins, none of those modes or `--shuffle`
  crosses into the child.
- No unnamed configuration input is added. Existing tool and operating-system requirements remain
  explicit in their owning scripts and documentation.
- The later `git245-locked-inputs-unit` recipe uses target-specific `override` assignments for
  `SHELL=/bin/sh` and `.SHELLFLAGS=-eu -c`. Its only direct acceptance invocation is the exact
  option-free `make git245-locked-inputs-unit`; other caller Make control-plane states remain
  unsupported diagnostics because GNU Make parses them before a recipe can establish isolation.
  The canonical aggregate child remains admitted because this topology clears inherited option
  variables and supplies only its owned `-j1` plus the exact goal list. The locked-input design owns
  the complete distinction between Make control state and the Python process's fixed empty-derived
  environment.

### 2.2 Result, error, ownership, and allocation

- Success is process exit status zero after every target in the selected graph succeeds.
- The first failing prerequisite or recipe makes the aggregate fail nonzero. No aggregate catches,
  retries, downgrades, or replaces a focused failure.
- Diagnostics remain the stdout and stderr of Make and the failing owner command. No new persisted
  result format is introduced.
- The child Make goal order in the ledger is deterministic even when the parent caller supplies
  `-j`. This preserves stable first-failure reporting and prevents aggregate-level overlap between
  checks that share the built executable or repository state. A recursive Make failure propagates
  directly through the aggregate recipe.
- Process ownership, cleanup, files, and allocation remain with their focused targets; the new
  locked-input target's sole executable and owned temporary state are defined in
  `docs/specs/git-245-compat-image.md`.
  The aggregate targets introduce no long-lived process, file, cache, or allocation.

### 2.3 Identity, versioning, and sources of truth

- The checked compiler identity remains `.align-revision`; no new schema version or cache identity
  applies.
- The coding-v1 baseline artifact manifest already includes `Makefile`. Therefore any implementation
  commit that changes the check graph is a new baseline source identity even when task verdicts and
  scoring semantics remain unchanged.
- The `Makefile` is the authoritative check graph.
- Its named `HOSTED_CHECK_TARGETS`, `CAPABLE_ONLY_CHECK_TARGETS`, and
  `SERIAL_CHECK_AGGREGATES` variables feed both the aggregate child-Make goal lists or parse-time
  coexistence guard and the three target-specific exported `ALIGN_LLM_*` values read by
  `scripts/check-gate-topology`.
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
Each value must name a raw commit object, not a symbolic ref or an annotated-tag object that Git
would implicitly peel to a commit. The source and oracle values must equal the identities embedded
in the finalized baseline, not merely name another valid ancestor chain. All structural Git
inspection runs in an empty environment with replacement objects and ambient Git configuration
disabled, matching the baseline recorder and verifier's repository-isolation boundary. Run these
exact checks before merge:

```bash
set -euo pipefail

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
python3 - "$SOURCE_COMMIT" "$ORACLE_COMMIT" "$FINALIZATION_COMMIT" <<'PY'
import json
import re
import sys
from pathlib import Path

baseline = json.loads(
    Path("eval/baselines/coding-v1-reference.json").read_text(encoding="utf-8")
)
expected_provider = {
    "id": "deterministic-reference",
    "model": "checked-in-patch",
    "prompt_version": "none",
}
if (
    baseline["baseline_id"]
    != "coding-v1-deterministic-reference-checked-in-patch"
    or baseline["provider"] != expected_provider
):
    raise SystemExit("refreshed baseline does not use the fixed provider identity")
for label, value in zip(
    ("source", "oracle", "finalization"),
    sys.argv[1:4],
    strict=True,
):
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise SystemExit(
            f"{label} commit must be a full lowercase 40-hex commit ID"
        )
expected = (baseline["align_llm_commit"], baseline["canonical_oracle_commit"])
actual = (sys.argv[1], sys.argv[2])
if actual != expected:
    raise SystemExit(
        "recorded provenance differs: "
        f"expected source/oracle {expected[0]} {expected[1]}, "
        f"received {actual[0]} {actual[1]}"
    )
runs = baseline["runs"]
if baseline["sample_count"] != 2 or len(runs) != 2:
    raise SystemExit("refreshed baseline must contain exactly two samples")
for sample, run in enumerate(runs, start=1):
    expected_summary = {"task_count": 1, "pass_count": 1, "fail_count": 0}
    if run["sample"] != sample or run["summary"] != expected_summary:
        raise SystemExit(f"sample {sample} does not have the fixed passing summary")
    tasks = run["task_results"]
    if len(tasks) != 1:
        raise SystemExit(f"sample {sample} does not contain exactly one fixed task")
    task = tasks[0]
    if (
        task["task_id"] != "python-inclusive-range"
        or task["verdict"] != "PASS"
        or task["expected_code"] != 0
        or task["actual_code"] != 0
        or task["time_to_passing_patch_ns"] != task["duration_ns"]
    ):
        raise SystemExit(f"sample {sample} does not contain the fixed passing task")
PY
if ! artifact_path_text="$(
  python3 - <<'PY'
import json
from pathlib import Path

baseline = json.loads(
    Path("eval/baselines/coding-v1-reference.json").read_text(encoding="utf-8")
)
files = baseline["artifacts"]["files"]
if not files:
    raise SystemExit("refreshed baseline artifact manifest is empty")
for artifact in files:
    path = artifact["path"]
    if not isinstance(path, str) or not path or "\n" in path or "\r" in path:
        raise SystemExit("refreshed baseline artifact path is not line-safe")
    print(path)
PY
)"; then
  printf '%s\n' "cannot read the refreshed baseline artifact manifest" >&2
  exit 1
fi
test -n "$artifact_path_text"
mapfile -t artifact_paths <<<"$artifact_path_text"
for label in SOURCE_COMMIT ORACLE_COMMIT FINALIZATION_COMMIT; do
  value="${!label}"
  if ! object_type="$(clean_git cat-file -t "$value")"; then
    printf '%s\n' "cannot inspect $label object type" >&2
    exit 1
  fi
  if test "$object_type" != commit; then
    printf '%s\n' "$label must name a raw commit object" >&2
    exit 1
  fi
done
python3 - <<'PY' | cmp - eval/expected/coding-v1-reference-oracle.json
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
baseline = json.loads(
    Path("eval/baselines/coding-v1-reference.json").read_text(encoding="utf-8")
)
projection = {field: baseline[field] for field in fields}
sys.stdout.buffer.write((json.dumps(projection, indent=2) + "\n").encode("utf-8"))
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
if ! recorded_input_changes="$(
  clean_git log --full-history --ancestry-path --format=%H \
    "$SOURCE_COMMIT"..HEAD -- "${artifact_paths[@]}"
)"; then
  printf '%s\n' "cannot inspect post-source recorded-input history" >&2
  exit 1
fi
test -z "$recorded_input_changes"
if ! oracle_changes="$(
  clean_git log --full-history --ancestry-path --format=%H \
    "$ORACLE_COMMIT"..HEAD -- \
    eval/expected/coding-v1-reference-oracle.json
)"; then
  printf '%s\n' "cannot inspect post-oracle history" >&2
  exit 1
fi
test -z "$oracle_changes"
if ! finalization_changes="$(
  clean_git log --full-history --ancestry-path --format=%H \
    "$FINALIZATION_COMMIT"..HEAD -- \
    eval/baselines/coding-v1-reference.json \
    eval/expected/coding-v1-reference.sha256
)"; then
  printf '%s\n' "cannot inspect post-finalization history" >&2
  exit 1
fi
test -z "$finalization_changes"
test ! -e eval/baselines/.coding-v1-reference.pending.json
```

Execute the complete block as one Bash process; running its lines independently is not acceptance
evidence. Before the positive run, an isolated temporary-clone harness must execute the same
fail-fast block once for each of these injected negative cases and require a nonzero overall status:
persisted source mismatch; one non-passing task; one sample instead of two; three samples instead of
two; reordered oracle fields; missing oracle final LF; a 40-character symbolic source ref; a
40-character symbolic oracle ref; a recorded input other than `Makefile` changed and then restored
in two linear post-source commits; abbreviated finalization ID; uppercase finalization ID; and a
`clean_git log` failure injected after the preceding Git operations succeed.

The history harness must additionally construct a TREESAME merge-hidden mutation independently for
four path classes: a recorded input other than `Makefile`, the immutable oracle, the canonical
baseline, and the canonical digest. In each isolated case, a second-parent commit changes the path
after its owning source, oracle, or finalization commit, while the first parent and merge result
retain the owning commit's bytes. The same complete block must return nonzero, proving that all
three `--full-history --ancestry-path` queries inspect second-parent history descended from the
owning commit even though ordinary simplified path history would omit it. The ancestry restriction
must also be covered by the positive case: history merged from a commit that is not a descendant of
the owning commit does not represent a post-owner mutation and must not create a false rejection.

The harness must also supply annotated-tag object IDs independently as the source, oracle, and
finalization values. For the source and oracle cases, it first replaces the corresponding persisted
identity in the temporary clone's finalized baseline with that same tag object ID so the identity
comparison passes and the raw-object guard is reached; it need not regenerate the oracle because
the guard precedes the projection comparison. These three cases must reject with the exact final
lines `SOURCE_COMMIT must name a raw commit object`, `ORACLE_COMMIT must name a raw commit object`,
and `FINALIZATION_COMMIT must name a raw commit object`, respectively.

The harness must not modify the source worktree, must remove its temporary clone on success or
failure, and must report one bounded English rejection line per case. The implementation pull
request records the command and all rejection lines as check evidence.

After merge, the source, oracle, and finalization commits must each be ancestors of refreshed
`main`, and the persisted-identity comparison, four final-tree byte comparisons, and three
no-later-change checks above must still pass with `HEAD` replaced by refreshed `main` in the same
isolated Git environment. The pending-record absence check must also pass in the refreshed `main`
worktree.

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

The capable gate adds exactly those two targets. It also includes the Git 2.45 locked-input unit and
every C1-C5 focused target through the hosted graph. New focused roadmap gates must be assigned
deliberately to the hosted graph, the capable-only set, or both through dependency, with the reason
recorded in the owning design and documentation.

`make ci` is not evidence that an arbitrary future focused target ran unless that target is
reachable in this authoritative graph at the tested commit.

## 4. Determinism and validation order

The aggregate graph performs no new semantic validation. Its deterministic dependency constraints
are:

1. `gate-topology-check` succeeds before the hosted focused checks;
2. `hosted-checks` launches one `-j1` child Make and runs `git245-locked-inputs-unit` first, then the
   existing focused targets in the ledger order;
3. `capable-checks` launches one `-j1` child Make and runs the complete hosted focused-target list,
   then `eval-coding`, then `baseline-check`;
4. `ci` completes `align-revision` before `align-build`;
5. `ci` completes `align-build` and the compiler executable check before its recursive
   `capable-checks` invocation;
6. focused targets retain their current `build` prerequisites; and
7. `failure-memory-smoke` retains its current `verify-loop-smoke` prerequisite.

Under the supported verification flags, the first failing command in that sequence reports the
aggregate failure and prevents later child-Make goals from running. The recursive Make exits
nonzero and the aggregate recipe does not catch, retry, or downgrade it. Within each focused target,
its existing validation and error precedence remain authoritative.

## 5. Topology inputs and oracle

The normal script mode accepts no arguments. It reads exactly the three named `ALIGN_LLM_*`
topology values from its environment in hosted, capable-only, serialized order. Each topology value
must encode as ASCII. The script constructs exactly these three lines in memory, in this order, with
one LF after every line including the last:

```text
hosted=gate-topology-check git245-locked-inputs-unit format-check check build eval-smoke loop-smoke provider-smoke index-smoke test-selection-smoke patch-eval-smoke verify-loop-smoke failure-memory-smoke prompt-model-smoke
capable-only=eval-coding baseline-check
serialized=hosted-checks capable-checks ci
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
returns zero only after the exact three values are accepted. For validation precedence, it enumerates
the complete 27-state Cartesian product in which each topology field is independently exact,
missing, or non-ASCII. With an empty argument vector, each state must produce success or the exact
first diagnostic defined above: the first missing field wins over every non-ASCII field, otherwise
the first non-ASCII field wins. With a non-empty argument vector, all 27 states must produce the
arity diagnostic.

After precedence coverage, each of these mutations is rejected with its specified error class: one
added target, one removed target, one duplicated target, one reordered target, one removed
serialized aggregate, empty field, leading space, trailing space, and repeated space.

The self-test also creates one temporary directory, invokes
`make --no-print-directory gate-topology-check` through a subprocess argument vector with dangerous
command-line overrides containing backticks, dollar-parenthesis text, quotes, backslashes, and a
marker-writing shell command, and supplies matching dangerous `ALIGN_LLM_*` values in the child
environment. It requires the target to emit the exact normal PASS line while the marker remains
absent.

In the same temporary directory, the self-test writes an instrumented Makefile with the exact
option-cleared recursive-Make recipe prescribed in section 2.1 and invokes its parent aggregate with
`make --no-print-directory -j8`. Three ordered synthetic goals each acquire an exclusive marker
directory, append distinct start and completion records, briefly hold the marker, and remove it
before returning. The parent receives distinct sentinel command-line values for `ALIGNC` and
`ALIGN_REPO`. A probe goal records those child values and their Make origins together with child
`MAKEFLAGS` and `GNUMAKEFLAGS`. The test requires the exact start/completion order with no failed
marker acquisition; exact sentinel values with `origin=environment` for both supported inputs;
child `MAKEFLAGS` containing the explicit `-j1` but no jobserver or inherited parallel option;
empty child `GNUMAKEFLAGS`; no jobserver warning; and one successful child invocation. This
exercises the prescribed boundary with the runner's installed GNU Make; the required Ubuntu 24.04
job therefore executes it specifically with GNU Make 4.3.

The self-test also invokes the repository Makefile with `-j8` for every ordered two-goal vector that
contains a serialized aggregate and either another serialized aggregate, the same name again, or a
test-only focused marker goal. Every invocation must fail with the exact coexistence diagnostic
before creating the marker added as a prerequisite through `--eval`. A focused-only zero-aggregate
parse completes without that diagnostic. The required hosted run and capable `make -j8 ci` are the
positive aggregate-alone controls; the self-test does not rerun product checks merely to repeat
those controls.

The child runner launches each child in a new POSIX session, owns binary stdout and stderr pipes, and
drains them concurrently in 8,192-byte read chunks so one full pipe cannot deadlock the other. It
retains at most 4,096 bytes per stream, keeps draining after that boundary without retaining further
bytes, and records an overflow bit. The real Make child has a 10-second monotonic deadline.

On timeout, a stream-reader error, or an unexpected runner exception after launch, cleanup first
sends `SIGTERM` to the owned process group, waits at most one second, then sends `SIGKILL` if any
group member or pipe-owning reader remains. It waits for and reaps the direct child, joins both
readers, and closes both pipes before returning the failure. An already-exited process or absent
process group is not a cleanup error; any other signal, wait, join, or close error remains a
self-test failure after cleanup is attempted. Success also requires the direct child to be reaped
and both readers to have reached EOF before the deadline.

Launch, read, wait, cleanup, or nonzero-exit failure; overflow of either stream; non-UTF-8 output;
any stderr; or stdout other than the exact PASS bytes makes the self-test fail. Synthetic output
tests use a five-second deadline. One child writes more than the operating-system pipe capacity to
stdout and stderr concurrently and must set both overflow bits while retaining exactly 4,096 bytes
from each stream. A second child and same-session descendant ignore `SIGTERM` and hold both pipes
open past a 100-millisecond deadline; the runner must take the `SIGTERM`/`SIGKILL` path, reap the
direct child, finish both readers, and leave no live member in the owned process group. Separate
synthetic children cover a nonzero exit with exact stdout, invalid UTF-8 stdout, non-empty stderr,
and wrong stdout; a nonexistent executable covers launch failure.

The hanging-child regression uses a test-only readiness pipe in addition to the captured streams.
It allows up to five seconds for setup. Only after the child and descendant have installed their
`SIGTERM` handlers, inherited both output pipes, and the child has written one exact readiness byte
does the runner start the 100-millisecond hang deadline. Missing, extra, or late readiness fails and
enters the same cleanup path. The readiness pipe is closed with the other owned descriptors. The
runner does not use `subprocess.run(capture_output=True)` or another whole-output buffer.

Self-test removes the temporary directory on success or failure and does not modify the repository.
On success it prints `check gate topology self-test: PASS` plus LF and nothing else.

## 6. Closure matrix

| Path | Owner | Intended implementation | Regression evidence |
| --- | --- | --- | --- |
| Topology success | `scripts/check-gate-topology` | three target-specific exported values, canonical byte construction, and embedded exact oracle | `make gate-topology-check` emits the single PASS line and returns zero. |
| Topology membership drift | script self-test | synthetic environment maps through the production comparator | Add/remove/duplicate/reorder and serialized-set negative cases all return nonzero internally. |
| Topology malformed input | script self-test | synthetic argument vectors and environment maps through production validation helpers | All 27 exact/missing/non-ASCII field states reach their exact empty-arity outcome and arity-first outcome; mutation, empty, and whitespace cases reach their specified diagnostics. |
| Topology bounded diagnostics | script self-test | compare full report bytes while bounding only each escaped diagnostic input to 4,096 bytes with an in-cap truncation marker | Two reports that differ only beyond their identical retained diagnostic prefix still reach different full-byte comparison outcomes; the retained prefix is exactly 4,096 bytes and both escaped diagnostic values contain the same in-cap marker. |
| Make-to-shell boundary | `Makefile` plus script self-test | `override :=` lists and target-specific `override export`; recipe contains no list expansion | Dangerous command-line and environment overrides are ignored, the gate passes, and no marker is created. |
| Locked-input Make control plane | `Makefile` plus script self-test | target-specific override `/bin/sh` and `-eu -c`; no audit-data expansion; exact option-free direct invocation or canonical option-cleared aggregate child only | Hostile `SHELL` and `.SHELLFLAGS` assignments cannot replace the recipe shell. A synthetic unit failure propagates through both admitted invocations. Ignore/dry-run/question/touch/keep-going/silent modes, inherited `MAKEFLAGS`/`GNUMAKEFLAGS`, alternate makefiles, `--eval`, assignments, and extra goals are classified as unsupported diagnostics rather than valid gate evidence. |
| Self-test child output and lifecycle | `scripts/check-gate-topology` | own a new-session child group; concurrently drain binary pipes in fixed chunks; retain at most 4,096 bytes per stream; enforce the deadline; terminate, kill, reap, join, and close in order; reject overflow or non-UTF-8 | A simultaneous two-pipe overflow child sets both overflow bits with exactly 4,096 retained bytes per stream; after a bounded readiness handshake, a hanging child plus descendant is terminated without a live process-group member or pipe reader; missing readiness plus synthetic launch, nonzero, invalid-UTF-8, stderr, and wrong-stdout cases reject; the real Make child returns exact PASS stdout and empty stderr within 10 seconds. |
| Self-test child OS-operation faults | `scripts/check-gate-topology` | put every operation after successful `Popen` inside the cleanup guard and track only successfully started readers | Injected first-reader start failure enters cleanup, reaps the direct child, closes both pipes, and leaves no process-group member. DEFERRED: deterministic injection of pipe-read, wait, signal, thread-join, and pipe-close failures requires a substitutable process-operation seam that this repository does not otherwise need. The implementation review audits the remaining post-launch exception paths against the specified cleanup order; timeout plus descendant and launch-failure regressions cover the executable lifecycle. A separate child-runner hardening slice must add the seam before claiming the remaining fault-injection coverage. |
| Direct hosted success | `Makefile` | one explicit `-j1` child Make over the ordered hosted goals | Run with the pinned compiler; the offline Git 2.45 locked-input unit and all existing hosted-compatible focused smokes pass. |
| Direct hosted failure | owning focused target | Make propagates nonzero | Invoke the aggregate with an invalid `ALIGNC`; the graph fails nonzero without fallback. |
| Direct capable success | `Makefile` | one explicit `-j1` child Make over hosted then capable-only goals | Run `make ci` on a capable Linux host; the locked-input unit, coding and baseline gates, and C1-C5 focused gates pass. |
| Direct capable failure | owning focused target | Make propagates nonzero | Existing focused negative-path regressions remain required; no aggregate suppression exists. |
| Aggregate coexistence | `Makefile` parse-time guard over `MAKECMDGOALS` and `SERIAL_CHECK_AGGREGATES` | when an aggregate is requested, require it to be the invocation's sole goal; the recursive `ci` child contains only `capable-checks` | Under `-j8`, self-test rejects every ordered pair of distinct aggregates, every repeated name, and each aggregate plus a focused marker goal in both positions with the exact diagnostic and no marker side effect. A focused-only parse plus the required hosted run and capable `make -j8 ci` are the non-rejection controls. Source review confirms the list is exactly `hosted-checks capable-checks ci`. Independent concurrent Make processes are explicitly unsupported and do not count as gate evidence. |
| Pin mismatch | `scripts/check-align-revision` | unchanged `align-build` prerequisite | DEFERRED: this slice does not change the owner script or prerequisite edge. The implementation review must confirm both are unchanged; automated mismatched-checkout fault injection belongs to a separate pin-hardening slice. |
| Compiler build failure | Align Cargo workspace | unchanged `align-build` recipe | DEFERRED: this slice does not change the Cargo recipe or its shell failure propagation. The implementation review must confirm both are unchanged; fake-toolchain fault injection belongs to a separate pin-hardening slice. |
| Missing built compiler | `ci` recipe | retain executable guard before recursive Make | DEFERRED: the implementation review must confirm the guard remains before `capable-checks`; a clean temporary pinned checkout plus successful fake Cargo build is the future fault-injection fixture, outside this topology slice. |
| Hosted workflow success | `.github/workflows/ci.yml` | on Ubuntu 24.04 with GNU Make 4.3 and CPython 3.12, build the pin, run the topology self-test, then call `make -j8 hosted-checks` | The required Actions check passes, including `git245-locked-inputs-unit` before existing focused checks. The self-test proves ordered, non-overlapping execution, option isolation, and exact supported-input propagation through the prescribed child boundary on GNU Make 4.3. The job log also preserves the real expanded aggregate recipe and shows one option-cleared child command with explicit `-j1` and the exact ordered hosted focused-goal list. |
| Hosted unsupported checks | workflow plus this plan | absent from `hosted-checks` | `make gate-topology-check` proves `eval-coding` and `baseline-check` appear only in the capable-only list. |
| Complete graph membership | `Makefile` | named child-Make goal lists | `make gate-topology-check` proves the exact hosted list, capable-only additions, and serialized aggregates. |
| Existing focused cleanup | focused scripts | unchanged | Existing ordinary, timeout, and abnormal cleanup regressions continue to own these paths. |
| Parallel and option-bearing parent invocation | recursive GNU Make | reject any aggregate that is not the invocation's sole goal; each permitted aggregate clears `MAKEFLAGS` and `GNUMAKEFLAGS`, then passes its full ordered goal list to one child Make with explicit `-j1`; no target-scoped `.NOTPARALLEL` dependency | The coexistence self-test rejects aggregate-plus-aggregate and aggregate-plus-focused invocations before side effects. The Ubuntu 24.04 required check runs the instrumented `-j8` parent self-test and `make -j8 hosted-checks` under GNU Make 4.3. The former proves child flags, exact order, non-overlap, absence of a jobserver warning, and distinct sentinel `ALIGNC`/`ALIGN_REPO` values retained with `origin=environment`; the latter preserves log evidence of the real option-cleared child command and exact hosted goal list. Separately, `make -j8 ci` passes on the capable host. On GNU Make 4.4 or later, an author-side synthetic invocation with parent `--shuffle=reverse -j8` proves the child order and child `MAKEFLAGS` contain neither shuffle nor inherited parallel flags. The topology oracle proves all three public aggregates remain in the serialized set. |
| Baseline source identity | implementation source commit | final identity-bound `Makefile` is clean and committed before recording | Pending record `align_llm_commit` equals the source commit and its Makefile digest equals the isolated section-2.4 `clean_git show <source>:Makefile` result. |
| Immutable oracle | oracle commit | exact canonical projection of the pending record | Independently regenerate the ordered, indented UTF-8 projection with its final LF from the finalized baseline and compare exact bytes; the oracle commit contains only that projection; the existing direct timing-mutation regression proves whole-projection equality is enforced; final-tree bytes equal the oracle commit. |
| Canonical finalization | finalization commit and final reviewed/merged worktree | finalizer binds full oracle commit and writes digest; the pending record is removed before the finalization commit and remains absent | `make baseline-check` passes; an explicit path check rejects a pending file at the reviewed head and refreshed `main`; canonical digest matches. |
| Baseline commit chain | finalized baseline, source, oracle, finalization, final reviewed head, and merge result | one fail-fast Bash process validates persisted source/oracle fields, full lowercase 40-hex raw commit objects for all three identities, and strict source → oracle → finalization → head/main ancestry in an isolated Git environment; merge method is `merge` | Exact identity, width, raw-object type, ancestry, and Git-command status checks pass without replacement objects or ambient Git configuration; the three annotated-tag regressions reach the type guard and require their exact diagnostics; oracle commit changes only the oracle, and finalization commit changes only canonical baseline plus digest. |
| Post-record input change | author/reviewer | re-record from a new clean source commit | The fail-fast block derives the complete path list from the finalized baseline artifact manifest and uses full ancestry-path history to reject any post-source change, including both linear modify-then-restore and TREESAME merge-hidden regressions for a recorded artifact other than `Makefile`; pre-owner side history does not create a false rejection. |
| Post-record output change | author/reviewer | regenerate through the owning projection/finalizer before finalization; restart the full sequence afterward | Final-tree oracle, baseline, and digest bytes equal their named owner commits; full ancestry-path history shows no later change. Separate TREESAME merge-hidden regressions cover the oracle, canonical baseline, and digest. |
| Measurement interpretation | pull request evidence | fixed deterministic-reference provider identity and exactly two samples on the recorded environment; each contains the single fixed task and passing summary | An explicit structural assertion requires the provider/model/prompt and both `python-inclusive-range` results and summaries to match and PASS; prior and refreshed timings are reported without a performance claim. |
| Baseline structural negative paths | isolated temporary-clone harness | execute the same complete fail-fast block against identity, raw-object type, outcome, count, oracle-byte, linear and merge-hidden full-history changes, finalization-width/case, and Git-log-failure injections | Every named negative case returns nonzero overall; the tag cases require their exact type-guard diagnostics, all other cases emit their bounded rejection line, and temporary state is removed. |
| Topology-checker persisted format | N/A | its byte oracle is embedded in the script; no topology file is created | N/A. |
| Canonical baseline JSON | existing schema version 1 | recorder emits indented UTF-8 JSON plus final LF; finalizer changes only `canonical_oracle_commit` | `make baseline-check` validates exact fields, identities, aggregates, malformed input, immutable oracle, and digest. |
| Immutable baseline oracle JSON | section 2.4 ordered projection | indented UTF-8 JSON plus final LF, committed before finalization | Projection command is reproducible; final-tree bytes equal the isolated section-2.4 `clean_git show <oracle-commit>:<oracle-path>` result; timing mutation is rejected. |
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
- Implement each aggregate with one recursive `$(MAKE)` command whose environment clears
  `MAKEFLAGS` and `GNUMAKEFLAGS` and whose explicit `-j1` precedes the selected ordered goals. Do not
  rely on target-scoped `.NOTPARALLEL`; keep the implementation compatible with GNU Make 4.3 on the
  declared hosted runner.
- Update only the contributor-facing descriptions and pull request reporting fields needed to
  distinguish complete, hosted, and focused verification.
- Run `make gate-topology-check`.
- Run `python3 scripts/check-gate-topology --self-test`; all specified negative cases pass by being
  rejected, including combined validation-precedence cases, bounded child-output overflow, and
  every serialized-aggregate invocation that also names another goal before side effects.
- Run `make hosted-checks` with the pinned release compiler.
- Record, project, commit, and finalize the canonical C0 baseline from the final clean implementation
  source commit using section 2.4. Verify the strict source → oracle → finalization → head chain,
  equality with both commit identities persisted in the finalized baseline, exact per-commit path
  sets, full raw provenance IDs, independently regenerated oracle serialization, two fixed passing
  samples, final-tree byte equality, pending-file absence, digest, replacement-object isolation,
  and the existing immutable-oracle timing-mutation regression.
- Run the isolated structural negative harness from section 2.4 and record every named rejection.
- Run `make -j8 ci` on a capable host after finalization to prove the refreshed baseline and
  aggregate serialization contract under inherited parallel Make flags.
- On GNU Make 4.4 or later, run the synthetic parent-shuffle regression from the closure matrix and
  prove the child receives neither shuffle nor inherited parallel flags.
- Obtain a passing Ubuntu 24.04 hosted required check that first runs the topology self-test and then
  uses `make -j8 hosted-checks`. The instrumented self-test must prove GNU Make 4.3 child flags,
  order, non-overlap, warning absence, and exact sentinel `ALIGNC`/`ALIGN_REPO` propagation with
  `origin=environment`; preserve log evidence that the real aggregate expands one option-cleared
  child command with explicit `-j1` and the exact ordered goal list.
- Review the full implementation against `docs/review-checklist.md`, including aggregate-name
  accuracy and any shared-target execution or cleanup regression.

The design and implementation are separate pull requests. The implementation and baseline refresh
remain one automation enabling slice because the baseline identity includes `Makefile`: separating
them would leave an intermediate `main` whose canonical baseline fails its own artifact check. The
pull request keeps implementation, oracle, and finalization in separately reviewable commits and
records why this identity-coupled exception cannot be split safely.
