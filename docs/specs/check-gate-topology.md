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

This document now has one additional prerequisite layer. Sections 1-7 describe the merged check
graph and its existing pinned-compiler implementation. Section 8 defines the future fresh-compiler
transition contract. Until its design and dependent implementation slices merge, the existing
`make ci` behavior remains the current implementation. For any later pin-changing adoption,
Section 8 supersedes the earlier `make ci`, `align-build`, compiler-selection, and source-build
claims; a later implementation may not satisfy this prerequisite by retaining the current direct
`../align/target/release/alignc` path.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| `make gate-topology-check` | Export the three Make-owned lists into `ALIGN_LLM_HOSTED_CHECK_TARGETS`, `ALIGN_LLM_CAPABLE_ONLY_CHECK_TARGETS`, and `ALIGN_LLM_SERIAL_CHECK_AGGREGATES` for this target, then invoke `python3 scripts/check-gate-topology` without interpolating list text into the recipe shell. The script constructs a canonical byte report from those values and compares it with an expected byte string embedded in that script. Fail before claiming an aggregate result if any list drifts without an intentional oracle update. |
| `make hosted-checks` | Run `gate-topology-check`, then clear `MAKEFLAGS` and `GNUMAKEFLAGS`, launch one recursive GNU Make with an explicit `-j1`, and run `git245-locked-inputs-unit`, `format-check`, `check`, `build`, `eval-smoke`, `loop-smoke`, `provider-smoke`, `index-smoke`, `test-selection-smoke`, `patch-eval-smoke`, `verify-loop-smoke`, `failure-memory-smoke`, `prompt-model-smoke`, `prompt-score-smoke`, and `prompt-score-prefix-smoke` as that child Make's ordered goals. All targets after the locked-input unit consume the compiler selected by `ALIGNC` where applicable. It does not build Align and does not run `eval-coding` or `baseline-check`. |
| `make capable-checks` | Run `gate-topology-check`, then clear `MAKEFLAGS` and `GNUMAKEFLAGS`, launch one recursive GNU Make with an explicit `-j1`, consume the compiler selected by `ALIGNC`, and run the complete hosted focused-target list followed by `eval-coding` and `baseline-check` as that child Make's ordered goals. It does not invoke `hosted-checks` as a nested aggregate and does not build Align. |
| `make ci` | Verify `.align-revision`, release-build the pinned sibling Align compiler, require that compiler to be executable, and invoke `capable-checks` with `ALIGNC` set to that exact release compiler. This remains the canonical complete local or capable-runner gate. |
| Aggregate coexistence | `hosted-checks`, `capable-checks`, and `ci` are the complete serialized-aggregate set. If a top-level GNU Make invocation requests one of them, that aggregate must be the invocation's sole goal. An aggregate plus any other goal, or a repeated aggregate, fails during Makefile parsing before a prerequisite or recipe runs, with `verification aggregates must be requested alone`. Separate concurrent Make processes are unsupported caller behavior and are not valid verification evidence; this slice adds no cross-process repository lock. The recursive `ci` child is a separate invocation containing only `capable-checks` and remains valid. |
| GitHub Actions pull-request gate | On the declared Ubuntu 24.04 runner with GNU Make 4.3, check out `.align-revision`, run `make align-build`, require the resulting release compiler, run `python3 scripts/check-gate-topology --self-test`, and invoke `make -j8 hosted-checks` with `ALIGNC` set to it. Preserve the aggregate recipe in the job log so review can verify the option-cleared child command, explicit `-j1`, and ordered focused-goal list. |
| Focused targets | Keep existing commands and semantics. Add `git245-locked-inputs-unit` with the offline contract in `docs/specs/git-245-compat-image.md` and `prompt-score-prefix-smoke` as the final hosted target for the C6c1p prefix-validator gate. `failure-memory-smoke` continues to depend on `verify-loop-smoke`; naming both in an aggregate graph does not execute the shared recipe twice in one Make invocation. |
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

## 8. Fresh compiler transition contract

This revision is the repository-wide prerequisite for every future adoption that changes
`.align-revision` or claims `ALIGN_LLM_VERIFIED` against a newly built compiler. It is a design
slice only; it does not change the current Makefile or compiler pin. A dependent implementation
must merge this contract first and then implement it in a separate slice. No later consumer may
introduce a narrower copy of this protocol.

### 8.1 Decision, threat boundary, and prerequisites

The final `make ci` path is controller-owned from source validation through the last capable check.
It builds the pinned Align compiler in a private target outside `ALIGN_REPO`, keeps the private
build root alive while it launches `capable-checks`, and removes that root only after the aggregate
process has terminated and the compiler descriptor is no longer reachable. `align-build` is a
diagnostic build-only entrypoint; it is not a prerequisite of the final `ci` path and its output
must never be reused by `ci`.

The trust boundary is explicit:

- The Linux kernel, `/usr/bin/python3`, the host-installed bootstrap executable
  `/usr/local/libexec/align-llm/fresh-bootstrap`, and the external toolchain manifest are
  platform inputs. The bootstrap is the trust root for loading repository-controlled Python. It is
  installed and attested by the runner image; the repository worker does not validate the bootstrap
  before using it, and no repository file is allowed to replace that path during an invocation.
- `scripts/fresh-align-compiler` is repository-controlled worker code. The bootstrap opens it
  relative to an already retained project-root descriptor, verifies its SHA-256 against the
  externally authenticated manifest, and executes it from the retained file descriptor. A changed
  worker is therefore a reviewed source change and a manifest update, not an implicit runtime
  choice. A worker that is modified after its descriptor is opened fails before creating a build
  root. The bootstrap has no shell, imports no repository module, and starts no child before this
  check.
- The external manifest's bytes are authenticated by the explicitly supplied
  `ALIGN_LLM_TOOLCHAIN_MANIFEST_SHA256`; the manifest path and digest are required inputs to
  `make ci`, not a hidden home-directory or shell configuration. Hosted workflow configuration
  records the exact path and digest for its image. A local capable host must provide the same
  named inputs or fails before any temporary directory, Cargo target, network request, or compiler
  process is created. This is an operational trust contract, not a claim that an operator who can
  replace both the runner image and its manifest is adversarially constrained.
- A hostile committed repository is outside the trust model of a reviewed pull request. Runtime
  mutation, path replacement, Git configuration, cache mutation, and process races are inside the
  model and are handled by the descriptor, file-descriptor, digest, process, and cleanup rules
  below. No self-hash of repository code is presented as a cryptographic substitute for review.

The bootstrap image prerequisite is part of the implementation slice's acceptance environment. It
must provide an ELF executable at the fixed path above, mode `0755`, no symlink, an attested digest,
and an API that accepts exactly `--mode ci`, `--mode build`, or `--mode self-test`. It must use
`/usr/bin/python3 -I -B`, `execve` the retained worker without a shell, preserve only the documented
file descriptors and environment, and return the worker's status and byte stream. The host-image
change and the repository implementation are one enabling slice only if both are independently
reviewable; the plan does not permit silently substituting a mutable local script for the bootstrap.

The final public inputs are:

| Input | Exact rule and default |
| --- | --- |
| `make ci` | The sole complete-gate command. The final recipe invokes the fixed bootstrap with `--mode ci`; it does not invoke `cargo` or a compiler path from the Makefile. |
| `ALIGN_REPO` | Existing default `../align`, expanded by Make to the project-root-relative path before export. The controller requires the resulting path to be absolute, lexically normalized, an ordinary worktree, and a retained directory descriptor. |
| `ALIGN_LLM_TOOLCHAIN_MANIFEST` | Required absolute path to the external manifest. No default, `HOME` lookup, `PATH` lookup, or implicit sibling cache is permitted. |
| `ALIGN_LLM_TOOLCHAIN_MANIFEST_SHA256` | Required lowercase 64-hex digest of the exact manifest bytes. No digest is derived from a mutable manifest and accepted in the same invocation. |
| `ALIGNC` on `ci` | Rejected as an unsupported override before the bootstrap starts. Direct focused targets and direct hosted/capable aggregates retain their existing `ALIGNC` input when they are not called by the fresh controller. |
| `ALIGN_LLM_WORK_PARENT` and timeout variables | N/A: no caller override exists. The controller uses the fixed `/tmp` parent and the constants in section 8.9 so a caller cannot redirect cleanup or extend a safety deadline. |
| `ALIGN_LLM_CARGO_CACHE` | N/A: the cache root and its manifest are fields of the authenticated toolchain manifest; a second environment channel would create two cache identities. |
| Fresh-build performance claim | N/A: this slice establishes source/compiler correctness and time-bounded cleanup, not an optimization. Any time-to-passing-patch or build-time claim requires a separate controlled benchmark with the manifest, hardware, sample count, and baseline recorded. |

`make ci` with `hosted-checks`, `capable-checks`, another aggregate, or any focused goal is
rejected by the existing parse-time aggregate guard. Concurrent independent invocations are
unsupported caller behavior; each accepted invocation nevertheless receives a fresh random root,
has no shared mutable Cargo target, and never removes a root it cannot prove it owns. The final
hosted aggregate does not build a compiler: it runs the fresh-controller self-test and uses the
workflow's separately selected compiler for hosted-compatible product checks. Only the capable
`make ci` acceptance proves a real fresh compiler build and its use by every capable check.

### 8.2 Bootstrap and toolchain manifest

The bootstrap reads one canonical UTF-8 JSON manifest from the explicit path. The schema version is
`1`; unknown fields, duplicate fields, non-UTF-8 bytes, a missing final LF, non-canonical field
order, and values outside the bounds below fail before the worker is loaded. The exact top-level
field order is:

```text
schema_version
controller
bootstrap
platform
tools
runtime_bindings
cargo_cache
```

The canonical form is an object with those fields in that order, two-space indentation, UTF-8
without an ASCII escape for ordinary printable characters, and one final LF. `controller` contains
`path` equal to `scripts/fresh-align-compiler` and `sha256` as lowercase 64-hex. `bootstrap`
contains the fixed path, lowercase 64-hex image digest, and `api` equal to `1`. `platform` contains
`os` `linux`, `architecture` `x86_64`, `kernel_minimum` `6.8`, `python_minimum` `3.12`, and
`make_minimum` `4.3`.

`tools` is an ordered array with exactly these names and no duplicates:

```text
git cargo rustc llvm-config cc cxx ar ranlib linker bwrap sh
```

Each tool record contains `name`, absolute host `path`, absolute namespace `path`, `mode`, lowercase
64-hex `sha256`, `argv`, `stdout`, and `stderr`. `argv` is a nonempty fixed argument vector whose
first element is the absolute host path; `stdout` and `stderr` are bounded ASCII probe results with
JSON escaping only where required by the JSON grammar. The controller opens each host path with
no-follow semantics, requires the declared executable regular-file mode, hashes the complete bytes
before execution, and then runs the exact vector with a cleared probe environment. The worker
materializes or read-only-binds that same verified executable at its namespace path before bwrap
starts. `git`'s expected output must report version 2.45 or newer; `cargo` and `rustc` must match the
manifest's exact Rust 1.96 toolchain; `llvm-config` must report LLVM major 22; the remaining version
and digest values are image-owned rather than inferred from `PATH`.

The manifest also contains `runtime_bindings` after `tools` and before `cargo_cache`. Each binding
has `source`, `target`, `kind`, and a complete recursive digest manifest. Bindings are ordered,
absolute, no-follow read-only mounts for dynamic libraries, Rust standard libraries, LLVM resources,
and other non-executable files required by the declared tools. A binding cannot overlap `/src`,
`/tools`, `/cargo`, or `/target`; its source and every descendant are validated before the build
root exists. This makes the namespace paths usable without silently exposing a host `PATH` or an
unverified tool-resource directory.

There are no unlisted identity probes. In particular, the controller does not run `command -v`,
`which`, a shell, `rustup`, a Git hook, a Cargo config helper, or a version command whose path came
from the environment. `bwrap` is probed because it owns the build namespace. `sh` is probed because
Cargo build scripts may request it; the build environment's `PATH` contains only the declared
namespace launchers under `/tools`. `RUSTC`, `CARGO`, `LLVM_CONFIG`, `CC`, `CXX`, `AR`, `RANLIB`,
and the target linker variable are all set to those namespace paths, whose executable bytes were
checked against the absolute host paths before the namespace was built. Cargo configuration,
rustup configuration, wrapper variables, proxy variables, credentials, and network configuration
are cleared rather than inherited.

`cargo_cache` contains `root`, `manifest`, `manifest_sha256`, and `entry_count`. Both paths are
absolute and are opened before any owned output root is created. The cache manifest uses the same
canonical JSON rules and lists every admitted relative path in raw-byte lexicographic order with
`kind`, `mode`, `size`, and `sha256`. Only regular files and directories with the declared modes
are admitted. Symlinks, hard links (`st_nlink != 1`), devices, FIFOs, sockets, whiteouts, absolute
paths, `..`, duplicate paths, and entries outside the declared root reject. The manifest's digest
is checked against the top-level record and the complete source cache is checked before copying;
Cargo may not discover another cache through `HOME`, `RUSTUP_HOME`, `CARGO_HOME`, or a config file.

The bootstrap validates in this order and emits one bounded English line on failure: manifest
argument and digest, manifest schema, fixed bootstrap identity, controller path/hash, platform,
tool records, then cache path/manifest/hash. It performs no `mkdir`, `unlink`, `rename`, network
request, Git command, Cargo command, or compiler command during those checks. Every probe process
is created only after its executable hash is accepted and is owned by the bootstrap's process
controller as described in section 8.8.

### 8.3 Source identity and the retained-descriptor boundary

The worker reads `.align-revision` as raw bytes and accepts exactly one lowercase 40-hex commit ID
plus one LF. It rejects BOM, whitespace, embedded NUL, a second line, abbreviated IDs, uppercase
hex, tags, and any byte outside that grammar before asking Git for an object. The expected revision
is a value, not a path or a symbolic ref.

The worker opens the supplied `ALIGN_REPO` root once with `O_DIRECTORY|O_NOFOLLOW`, retains that
descriptor, and uses it as the only worktree root. It parses the exact `.git` entry relative to that
descriptor, resolves ordinary-clone and linked-worktree `gitdir`/`commondir` entries with bounded
no-follow descriptor operations, and retains the worktree, Git directory, common directory, index,
HEAD, and object-store descriptors. Bare repositories, `core.worktree`, promisor or shallow state,
alternates, HTTP alternates, grafts, replace refs, fsmonitor, hooks, filters, and caller Git config
are rejected before object lookup.

Every Git child receives `cwd` as the retained worktree descriptor, `GIT_DIR` as an inherited
`/proc/self/fd/<fd>` descriptor path, and the fixed empty Git environment from the adoption
contract. It receives no pathname that requires re-resolving the original ancestor, worktree root,
`.git` entry, or common directory. The controller verifies the raw command result and the retained
descriptor identity after every Git operation. No Git child runs after source materialization
starts.

The worker then performs the existing binary-safe tree/index comparison and complete raw worktree
enumeration against those descriptors. Its canonical source manifest records, in raw-byte path
order, every tracked and accepted source entry, type, mode, Git object ID, byte size, symlink target
when applicable, and the allowed root `target/` output exception. It includes the exact `.align`
revision, object format, tree ID, index digest, and raw source-entry digest. Ignored files, empty
directories, case-fold collisions, hidden configuration, filters, assume-unchanged and
skip-worktree files, unsupported modes, and symlink escapes reject. The root `target/` entry is
never copied or read by the build.

After the manifest is accepted, the worker materializes a private source tree by opening every
source entry relative to retained parent descriptors, using no-follow operations and direct
create-exclusive destinations. A regular file is copied through one bounded buffer and rehashed
against its manifest entry. A permitted symlink is recreated only after its complete relative
target chain is validated inside the source root; the target's own regular bytes are materialized
inside the private tree, and the recreated link points only to that private relative target. No
source path is passed to Cargo. The worker repeats the complete raw enumeration and compares the
canonical manifest before and after materialization. A disappearing entry, type or mode change,
digest mismatch, persistent extra entry, or descriptor identity change rejects before the build
child is started.

This is the source-identity boundary: Git, raw enumeration, source copy, and build consume the
retained worktree/Git descriptors and then the immutable private source copy. Replacing an ancestor,
the root pathname, `.git`, or the common directory cannot redirect a retained descriptor. A second
repository with the same HEAD, tree, and index but an additional recursively consumed Rust input is
rejected by the raw manifest, whether it is present before the root is opened or during the
pre-materialization repeat. A same-byte replacement that leaves the canonical manifest unchanged is
not a semantic source change; the build consumes the copied bytes, not the replacement path. This
explicitly defines the permitted ABA case instead of claiming that pathname identity alone is
stable.

### 8.4 Private roots, cache materialization, and build namespace

Only after all manifest, tool, Git, and source checks succeed does the worker open `/tmp` with
`O_DIRECTORY|O_NOFOLLOW`, verify its exact mode `01777`, and create one mode-`0700` root directly
below it with `mkdirat(O_EXCL)`. The basename is `align-llm-fresh-<32 lowercase hex>` from
`secrets.token_hex(16)`; eight collisions are the fixed maximum. The worker retains the `/tmp`
descriptor, root descriptor, random basename, device/inode pair, and a private owner token. It
never removes `/tmp`, the project root, `ALIGN_REPO`, the source cache, or an unowned path.

The root owns exactly these children, created with fixed modes and no replacement or rename:

```text
source/       0555 source materialization
cargo-home/   0700 private Cargo home
cargo-target/ 0700 empty Cargo target
tool-bin/     0555 copied declared tool launchers
descriptor/   0700 compiler descriptor and cleanup journal
```

The cache materializer walks the retained source-cache descriptor and copies each manifest entry
directly into `cargo-home` with `openat(O_CREAT|O_EXCL|O_NOFOLLOW, 0600)`, bounded reads, a fresh
SHA-256, `fsync`, and a final descriptor-relative enumeration. It never uses `cp -a`, a recursive
rename, a symlink-following library walk, or a cache path as `CARGO_HOME`. A source cache mutation
during a copy produces a digest or size mismatch; a destination collision, symlink, hard link,
unexpected special file, or post-copy extra path produces a cache error. The source cache remains
read-only and no network access is possible.

The build runs through the declared `bwrap` in a new session and PID namespace with
`--die-with-parent`, `--unshare-net`, and read-only binds for the staged source, copied tool set,
system dynamic libraries, and source cache. Only `cargo-home` and `cargo-target` are writable
binds. The namespace has no host `HOME`, no host `/tmp`, no host Cargo target, and no original
`ALIGN_REPO`; `/src`, `/tools`, `/cargo`, and `/target` are the only build paths. The exact build
argv is:

```text
cargo build --manifest-path /src/Cargo.toml --locked --offline --release -p align_runtime -p align_driver
```

The controller additionally sets `CARGO_NET_OFFLINE=true`, `CARGO_HOME=/cargo`,
`CARGO_TARGET_DIR=/target`, fixed `PATH=/tools`, and the namespace tool variables from the
manifest. The `cargo` argv element is `/tools/cargo`; its host path, digest, and required resource
bindings were validated before that namespace path was exposed. The same rule applies to `rustc`,
`llvm-config`, the C/C++ tools, linker, and `sh`.
It rejects any Cargo output outside `/cargo` or `/target`, and after success requires the release
compiler plus its adjacent runtime artifacts to be regular files with the declared build identity.
The build is never allowed to reuse a pre-existing target or a mutable Cargo home.

Cleanup has one owner: the worker that created the root. It first terminates and reaps every owned
child, closes source/cache/output descriptors, then removes only known children in reverse order
using the retained root descriptor. Before unlinking the random root name it compares the parent
entry's no-follow device/inode to the creation pair. If the name is absent, renamed, replaced, or
contains an unexpected entry, cleanup reports failure and leaves the path; it never follows or
recursively deletes it. A cleanup failure never changes a successful or primary phase into a
different category; it appends one `cleanup` line.

### 8.5 Compiler descriptor and execution interposition

After the build, the worker writes one temporary canonical JSON `CompilerDescriptor` under the
private `descriptor/` child. It has schema version `1`, exact field order
`schema_version`, `align_revision`, `source_manifest_sha256`, `toolchain_manifest_sha256`,
`compiler_path`, `compiler_sha256`, `runtime_paths`, and `launcher_policy`. It is UTF-8, two-space
indented, has no unknown fields, and ends with one LF. `compiler_path` and each `runtime_paths`
entry are descriptor-relative paths below the private root; the descriptor records no original
`ALIGN_REPO` path. The compiler digest is over the complete regular executable bytes. The descriptor
is not a persisted project artifact and is valid only while its owning worker holds the root.

The worker launches the capable aggregate itself with this exact environment contract:

```text
ALIGNC=<align-llm>/scripts/alignc
ALIGN_LLM_FRESH_COMPILER=1
ALIGN_LLM_COMPILER_DESCRIPTOR=<private descriptor path>
ALIGN_LLM_COMPILER_REVISION=<descriptor align_revision>
```

`ALIGNC` and the three `ALIGN_LLM_*` values are exported through the recursive Make boundary.
`Makefile`, every compiler-using script, and every nested runner must use the common
`scripts/alignc` launcher; a raw `../align/target/**/alignc`, `alignc` from `PATH`, or sibling
fallback is forbidden while `ALIGN_LLM_FRESH_COMPILER=1` is present. The implementation adds a
static compiler-call-site check and a runtime negative fixture that places a marker-writing fake
compiler at every old fallback path.

In fresh mode `scripts/alignc` does not search `ALIGNC`, `PATH`, or `ALIGN_REPO`. It reads the
descriptor with no-follow operations, verifies the four identity fields and all descriptor-relative
paths, opens the compiler executable, requires a regular executable, hashes it completely, and
executes that already-open file with `execveat(AT_EMPTY_PATH)`. If `execveat` is unavailable, it
fails closed; a pathname `/proc` fallback is not accepted. The wrapper emits no bytes before the
compiler and has no cache or output side effect. Consequently compiler identity is checked at the
actual process boundary for `check`, `run`, `build`, `fmt`, every focused script, every recursive
Make child, and aggregate-internal invocations below Make.

The child Make invocation is the only aggregate entrypoint admitted by the worker. It is a direct
argument vector, not a shell string, with `MAKEFLAGS=` and `GNUMAKEFLAGS=` cleared and explicit
`-j1 capable-checks`. It passes `ALIGNC` and the descriptor as environment values with their exact
documented origin. The child cannot replace them with a caller command-line assignment because the
worker rejects `ALIGNC` on the outer `ci` call and supplies the child values as the only accepted
controller-owned command-line values. A synthetic child that deliberately ignores `ALIGNC` and a
synthetic script that directly names the old sibling binary must both fail the fresh identity unit
before their marker can run.

### 8.6 Process topology and ownership

The worker is the owner of one ordered process set: tool probes, the bwrap build, the compiler
identity probe, and the recursive capable aggregate. It starts each with `close_fds=True`, a new
session, binary stdout/stderr pipes, and a captured PID start-time and process-group ID. Output is
drained concurrently in 8,192-byte chunks, retained to 64 KiB per stream, and marked overflow after
the cap. No whole-output capture is allowed. Probe output is compared to the manifest before the
next probe; compiler and aggregate output remains the owning command's diagnostic stream.

The worker enables Linux child-subreaper mode before the first child, records every descendant's
`/proc/<pid>/stat` start-time and parent relation, and requires `/proc` process identity reads to be
available. On timeout, cancellation, reader failure, unexpected exception, or nonzero phase result,
it sends `SIGTERM` to the captured process group, waits one second, rescans descendants, sends
`SIGKILL` to still-owned members, waits another five seconds, reaps the direct child and any
subreaper children, joins readers, and closes pipes. It never sends a signal to a PID whose current
start-time or captured process-group identity differs; PID/process-group reuse is a cleanup error,
not permission to signal the replacement.

The bwrap child additionally owns a PID namespace with `--die-with-parent`; a build script that
double-forks or calls `setsid` remains inside that namespace and is killed when the owner exits. The
aggregate is not placed in a separate namespace because product checks need the project workspace,
but child-subreaper descendant enumeration and the same session/process-group boundary cover its
escaped descendants. If a descendant becomes uninspectable or survives the bounded shutdown, the
worker leaves the private root and reports cleanup failure rather than guessing at ownership.

Signals are handled in every construction and active-process window. The worker installs a
self-pipe/wakeup handler before opening the source root, converts `SIGINT`, `SIGTERM`, and `SIGHUP`
to a cancellation state, and runs one reverse-order cleanup path. A signal during manifest or source
validation performs no partial deletion; a signal during cache copy, build, compiler probing, or
aggregate execution enters the same terminate/escalate/reap path. A signal during final unlink
causes the worker to recheck the parent entry and either prove removal or report cleanup failure.
The worker does not promise cleanup after `SIGKILL` or kernel termination.

### 8.7 Statuses, validation order, and bytes

The worker modes accept exactly one of `--mode ci`, `--mode build`, and `--mode self-test`. The
bootstrap rejects every other argument vector before worker dispatch. `ci` success is exit `0`,
empty stderr, and exactly:

```text
fresh compiler and capable checks: PASS
```

`build` success uses `fresh compiler: PASS`; `self-test` success uses
`fresh compiler self-test: PASS`. A failure has exit `1`, empty stdout, one primary line, and at
most one following cleanup line. The primary grammar is:

```text
fresh compiler: ERROR ARGUMENT|TRUST|PLATFORM|TOOL|SOURCE|CACHE|FILESYSTEM|BUILD|COMPILER|CHILD|INTERNAL
fresh compiler: ERROR cleanup
```

The exact primary categories are selected by this immutable order:

1. bootstrap mode and required environment names/encoding;
2. external manifest bytes, digest, schema, bootstrap identity, and controller identity;
3. Linux, architecture, Python, Make, `/proc`, signal, and timer prerequisites;
4. all declared executable paths, digests, version probes, and fixed tool outputs;
5. `.align-revision`, retained worktree/Git/common descriptors, Git policy, object/tree/index, and
   raw worktree manifest;
6. cache root, cache manifest, and cache entries;
7. `/tmp` identity, private-root creation, and source/cache materialization;
8. build namespace construction, Cargo exit, output containment, and compiler artifact identity;
9. compiler-launcher descriptor validation and aggregate child exit/output; and
10. reverse cleanup and final owner-root absence proof.

Malformed input is reported only at the first applicable phase. A missing manifest digest is
`TRUST`, a malformed revision is `SOURCE`, a cache digest or symlink escape is `CACHE`, an absent
`/tmp` or unsafe output entry is `FILESYSTEM`, a tool version mismatch is `TOOL`, and a failed
aggregate compiler invocation is `CHILD`. An unexpected exception maps to the active phase or
`INTERNAL` before a phase owner exists. No later phase may overwrite a primary category. Diagnostics
contain no path bytes, environment bytes, compiler output, credentials, or source content; bounded
phase details are checked-in identifiers only.

### 8.8 Descriptor and lifecycle closure matrix

| Path | Owner | Construction and invariant | Exact regression |
| --- | --- | --- | --- |
| Bootstrap trust | host bootstrap and toolchain manifest | Fixed image executable, external manifest digest, retained worker fd; no repository code or child before controller hash | `fresh-compiler-bootstrap-trust-smoke` mutates the worker, manifest, bootstrap path, and manifest digest independently and requires rejection before root creation. |
| Manifest wire format | bootstrap | Schema-1 canonical UTF-8 JSON, ordered fields, final LF, bounded fields, duplicate/unknown rejection | `fresh-compiler-manifest-format-smoke` covers every malformed field, order, UTF-8, NUL, width, and digest case. |
| Tool identity | worker | No-follow executable open, full digest, exact version vector, sequential owned probe | `fresh-compiler-tool-identity-smoke` covers missing, symlink, replacement, version, stderr, timeout, overflow, and nonzero probes for every named tool. |
| Signal during setup | worker | Cancellation state before root ownership; no unowned deletion | `fresh-compiler-signal-setup-smoke` injects each supported signal after manifest, source, cache, `/tmp`, and child-owner transitions and verifies root absence or bounded cleanup error. |
| Source revision and Git | worker | Raw revision grammar, retained worktree/Git/common/index/object descriptors, fixed Git environment | `fresh-compiler-source-revision-smoke` covers encoding, tags, shallow/promisor/alternate/graft/replace/config/hook/filter cases and exact error precedence. |
| Raw source closure | worker | Tree/index and complete descriptor-relative worktree manifest; root `target/` is the only output exception | `fresh-compiler-source-tree-smoke` covers extra/ignored/empty/case-fold/prefix/special/symlink/assume-unchanged/skip-worktree/filter and mode/object mismatches without helper execution. |
| Ancestor/root ABA | worker | Retained descriptors and post-materialization manifest equality; no later Git pathname lookup | `fresh-compiler-source-aba-smoke` swaps ancestors, root, `.git`, and common directory; a same-HEAD repository with an extra Rust input is rejected and no outside marker is read. |
| Source materialization | worker | Direct no-follow create-exclusive copy, per-file digest, symlink target containment, private read-only source | `fresh-compiler-materialization-smoke` injects disappearing/replaced/type-changing files and proves no build starts and no outside path is opened. |
| Cache trust | worker | Authenticated cache manifest, descriptor-relative source, regular-file/no-hardlink copy, size/digest/fsync/post-scan | `fresh-compiler-cache-smoke` covers missing/changed/extra/symlink/hardlink/special/rename/escape entries and confirms no network or source-cache mutation. |
| Private root construction | worker | `/tmp` mode/identity, eight exclusive attempts, fixed child set, owner token and device/inode | `fresh-compiler-root-smoke` covers collision exhaustion, parent symlink/mode, child collision, root replacement, and ancestor rename. |
| Build containment | worker plus bwrap | New session/PID/net namespace; only `/src`, `/tools`, `/cargo`, `/target`; exact locked offline argv | `fresh-compiler-build-namespace-smoke` places marker files in host cache, target, source, network, HOME, and sibling target paths and proves only owned outputs change. |
| Private Cargo target | worker | Empty mode-0700 `cargo-target`, never `ALIGN_REPO/target`, no reuse or rename | `fresh-compiler-empty-target-smoke` seeds a stale target and symlinked target cases, requiring rejection or clean private build with no seed marker. |
| Build failure/timeout | worker | One process owner, bounded deadline, group/tree termination, reap, reverse cleanup | `fresh-compiler-build-failure-smoke` covers Cargo nonzero, hanging build script, output overflow, signal, and descendant survival. |
| Compiler descriptor | worker | Canonical schema-1 temp descriptor, exact source/tool/compiler digests and contained runtime paths | `fresh-compiler-descriptor-smoke` covers field order, digest, path, mode, runtime-artifact, and owner-root replacement cases. |
| Direct compiler call | `scripts/alignc` | Fresh mode ignores fallback and PATH, hashes/open-execs the descriptor-selected binary | `fresh-compiler-direct-identity-smoke` replaces old sibling/debug/PATH compilers with marker writers and verifies the marker never runs. |
| Internal Make/compiler call | Makefile, `scripts/alignc`, focused scripts | Exported descriptor and launcher survive recursive Make; all call sites use the common launcher | `fresh-compiler-internal-identity-smoke` exercises `$(ALIGNC)`, hardcoded helper calls, recursive Make, `fmt`, `check`, `build`, and every focused script; a bypass is rejected before its marker. |
| Aggregate ownership | worker plus Makefile | Worker launches exactly one option-cleared `-j1 capable-checks`; outer `ci` owns no second aggregate | `fresh-compiler-aggregate-topology-smoke` covers aggregate-plus-goal parse rejection, child variable origin, order, no jobserver, and compiler descriptor propagation. |
| Aggregate timeout/early exit | worker | First failure stops later goals; controller kills/reaps all descendants and keeps descriptor root until exit | `fresh-compiler-aggregate-lifecycle-smoke` covers first focused failure, timeout, signal at each goal boundary, descendant escape, and cleanup ordering. |
| Cleanup success | worker | Reverse known-child removal, parent identity proof, root absence before PASS | Every positive mode runs a final absence assertion; `fresh-compiler-cleanup-smoke` verifies no root, descriptor, target, cache copy, or marker remains. |
| Cleanup failure | worker | Never delete an unowned/replaced name; append one cleanup line without masking primary | `fresh-compiler-cleanup-failure-smoke` injects close, unlink, parent replacement, live-child, and PID-reuse failures and checks exact primary/cleanup lines. |
| Hosted topology unit | Makefile/workflow | Self-test only; no compiler build or network; hosted product checks use their explicit compiler | Ubuntu 24.04/GNU Make 4.3 runs `fresh-compiler-topology-unit` before the existing hosted list and records that it is not fresh-build evidence. |
| Capable integration | worker/Makefile | Real pinned fresh build, descriptor interposition, complete capable graph, cleanup after aggregate | On the minimum capable Linux image, one `make ci` passes with the manifest, and the old sibling target/debug/PATH compilers are absent from all executed identities. |
| Unsupported concurrent entrypoints | Makefile/worker | `ci` plus any aggregate/goal is parse-rejected; separate processes are unsupported and roots are never shared | `fresh-compiler-concurrency-smoke` enumerates every aggregate-plus-focused and aggregate-plus-aggregate order, plus two independent processes, and checks rejection/no shared deletion. |
| Align code/ownership parity | N/A | No Align source, public Align type, persisted result, or allocator is changed by this topology slice | N/A: compiler input and process artifacts are external to Align; the implementation review records this explicit exclusion. |

The matrix is also the implementation-to-diff checklist. Every row must point to a concrete function
or recipe and a passing named test before the dependent implementation is reviewed. A row may be
marked deferred only by changing this design first; the four formerly unresolved choices in the
request register are not deferred here.

### 8.9 Constants, compatibility, and acceptance commands

The minimum acceptance environment is Ubuntu 24.04 x86_64, Linux kernel 6.8 or newer, GNU Make
4.3, CPython 3.12, Git 2.45 or newer, Rust/Cargo 1.96.0, LLVM 22, and the fixed bootstrap/bwrap
image manifest. Tool versions newer than these are supplementary evidence only. The fresh build
and capable aggregate require the namespace capability declared by `bwrap`; the ordinary hosted
runner is not allowed to claim the capable result when its namespace probe fails.

The fixed monotonic deadlines are: each tool probe 5 seconds; manifest/source/cache validation
120 seconds; source materialization 120 seconds; private-root construction 10 seconds; fresh Cargo
build 1,800 seconds; compiler descriptor and identity probe 10 seconds; capable aggregate 1,800
seconds; termination grace 1 second; escalation/reap 5 seconds; and final cleanup 30 seconds.
Output caps are 64 KiB per phase stream and 1 MiB for the whole controller diagnostic stream. A
timeout includes all children of the owned phase, not merely its direct process. These values are
constants in the worker, not environment or Make inputs.

The design gate runs these docs-only checks before implementation:

```text
git diff --check
awk '/^```/ { count++ } END { if (count % 2 != 0) exit 1 }' docs/specs/check-gate-topology.md
```

No repository link checker exists and this revision adds no Markdown links; link-target validation
is therefore `N/A` for this docs-only slice.

The implementation gate must run, at minimum:

```text
make fresh-compiler-topology-unit
make gate-topology-check
make hosted-checks
make ci ALIGN_LLM_TOOLCHAIN_MANIFEST=/absolute/manifest.json \
  ALIGN_LLM_TOOLCHAIN_MANIFEST_SHA256=<external-64-hex>
```

The self-test uses only synthetic source/cache/tool/process fixtures and never network or a
repository-controlled compiler. The hosted command proves the graph and worker topology but does
not substitute for the capable fresh build. The capable command is the only acceptance that can
advance a pin-changing request; it must record the external manifest identity, exact Align revision,
fresh compiler digest, complete cleanup result, and the exact local/hosted base and head evidence.

### 8.10 Delivery order and non-consumption rule

The slices are ordered as follows:

1. Merge this reviewed design update, including the complete ledger and closure matrix.
2. Install and attest the fixed bootstrap/toolchain manifest on the minimum hosted and capable
   images; run its independent bootstrap contract tests.
3. Implement the controller, source descriptor boundary, cache materializer, private build root,
   process owner, compiler launcher, Make export/interposition, and named unit tests as one
   dependent enabling slice. Do not update `.align-revision` in that slice.
4. Run the local synthetic matrix, the Ubuntu 24.04 hosted topology unit, and one capable `make ci`
   at the unchanged pinned revision. The old direct sibling compiler must not be used by the fresh
   path, and the complete source-to-build-to-aggregate cleanup evidence must pass.
5. Only after that implementation merges may a separate consumer adoption slice update
   `.align-revision`, rebuild the sibling release/runtime if required, add its focused target, and
   run the original acceptance gate through the fresh `make ci` path.

No Request 6, Request 7, Request 9, C7, or later consumer implementation may consume the controller,
descriptor, cache, wrapper, or aggregate behavior before step 3 merges. A proposed API, unmerged
bootstrap, host image, or hypothetical compiler binary is not an implementation input. The request
register remains the lifecycle authority for each consumer; this section owns only the common
fresh-compiler topology and its evidence.
