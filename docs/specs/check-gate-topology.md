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
graph and its existing pinned-compiler implementation. Section 9 defines the successor future
fresh-compiler transition contract; Section 8 is retained only as non-normative review history.
Until FRESH-WORKER and FRESH-IMAGE merge, the existing `make ci` behavior remains the current
implementation. For any later pin-changing adoption, Section 9 supersedes the
earlier `make ci`, `align-build`, compiler-selection, and source-build claims; a later implementation
may not satisfy this prerequisite by retaining the current direct
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
| Focused targets and qualifications | Existing public target commands remain stable, but their declared coverage is explicit. `eval-coding` runs the coding corpus, bounded invalid-input/containment smoke, Git-configuration isolation, and timeout/process cleanup; it intentionally does not run the deep resource/race/failure-injection qualification at `python3 scripts/run-coding-task-resource-scan-smoke`. `git245-locked-inputs-unit` retains the offline contract in `docs/specs/git-245-compat-image.md`, and `prompt-score-prefix-smoke` remains the final hosted target for the C6c1p prefix-validator gate. `failure-memory-smoke` continues to depend on `verify-loop-smoke`; naming both in an aggregate graph does not execute the shared recipe twice in one Make invocation. |
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

### 2.4.1 Post-review repair closure

The implementation repair keeps the public Section 9 contract and closes the four missed owner
boundaries as one consolidated repair, with no direct child-process implementation left outside the
worker controller:

1. `scripts/fresh-align-compiler` uses one bounded owned-child runner for tool probes, Git
   identity commands, the build bwrap, and the aggregate bwrap. Every launch gets a new session,
   binary bounded streams, captured PID start-time and process-group identity, the fixed rlimits,
   and a retained descriptor-bound cgroup lease. Timeout, cancellation, reader failure, launch
   failure, nonzero exit, and cleanup all use the same terminate, escalate, reap, join, and close
   order. The tool and Git callers consume the runner's bounded `CompletedProcess` result and may
   not call `subprocess.Popen` directly.
2. The cgroup lease owns retained descriptors for both the delegated parent and random leaf. Every
   read, write, membership check, kill, and removal is relative to those descriptors and rechecks
   parent and leaf device/inode identity. Admission proves empty `cgroup.procs` and
   `cgroup.threads` before `pids.max` configuration and again after the child attaches. Linux
   cgroup-v2 deliberately disallows `rename(2)`, so cgroup cleanup cannot use the regular-file
   `renameat2(RENAME_NOREPLACE)` quarantine protocol: the unique random leaf name is the quarantine
   identity, and after a final identity and empty-membership proof the worker invokes
   `rmdir(leaf_name, dir_fd=parent_fd)` on the retained parent descriptor. The protected delegated
   parent is an exclusive worker/profile writer boundary: a non-cooperating same-UID writer is
   outside this profile's threat model and is not admitted by the image/profile ownership contract.
   A changed parent, replaced leaf, nonempty leaf, name that remains after `rmdir`, or failed
   removal is left in place as a cleanup failure. The image control self-test uses the same
   membership and descriptor-relative sequence and propagates every cleanup failure instead of
   ignoring it.
3. Private-root cleanup moves each expected child and the admitted root through a unique
   worker-owned quarantine directory using Linux `renameat2(RENAME_NOREPLACE)`, verifies the
   destination descriptor identity before destructive cleanup, and restores/retains the moved
   entry on any mismatch. The protected per-user lock and mode-0700 parent are held for the whole
   quarantine lifetime; a non-cooperating same-UID writer is outside this profile's threat model.
   The root descriptor and quarantine descriptors remain open through the final identity checks and
   removal. A changed entry is left untouched and reports cleanup failure; a successful cleanup
   closes descriptors only after the quarantined root and its parent name are absent.
4. `scripts/check-baseline-chain` is the executable owner of the Section 2.4 positive chain. The
   `baseline-check` target invokes it after the schema verifier and failure smokes. It derives the
   source and oracle IDs only from the finalized baseline, identifies exactly one finalization
   commit as the direct oracle child with the exact two output paths, and validates raw object type,
   exact bytes, strict ancestry, complete post-owner history, and pending-record absence using the
   isolated Git environment. It has no caller-controlled ambient commit or repository input.

The implementation sequence is therefore: closure-plan update, shared runner and descriptor
ownership repair, baseline-chain gate and its focused regressions, a fresh identity-bound baseline
refresh for every recorded input change, then the final exact-head review and hosted checks. A
repair may not claim the affected gate until each owner and regression row below points to the
implemented path and passing command.

### 2.4.2 Conditional final-review repair closure

The conditional final review reopened the closure matrix after the first repair and found four
residual owner boundaries. They are one consolidated repair because each is a time-of-check or
ownership gap in the same fresh-worker lifecycle:

1. **Cgroup admission and cleanup.** `open_cgroup_lease` and the image-control lease must parse
   both membership files and prove them empty before configuration, before child attachment, and
   during cleanup. After attachment, the only permitted membership is the admitted child and its
   kernel-created threads; a foreign member is a platform/cleanup failure and is never killed as
   owned. Because cgroup-v2 disallows `rename(2)`, cleanup uses the unique leaf name as its
   quarantine identity, rechecks the retained parent/leaf descriptors and empty membership, and
   removes only that name with descriptor-relative `rmdir`. The delegated cgroup parent is an
   exclusive worker/profile writer boundary, so non-cooperating same-UID writers are explicitly
   outside the profile threat model. Any failed proof leaves the cgroup in place and reports
   cleanup failure. The image-control child runner enters this cleanup finalizer immediately after
   acquiring its lease: `Popen`, PID/group or membership setup, selector/pipe setup, and every
   later post-lease failure must close both retained descriptors and remove the authenticated empty
   leaf, or preserve it and report cleanup failure when removal cannot be proved.
2. **Private-root quarantine.** Ordinary mutable source names are never passed directly to the
   destructive unlink/rmdir phase. The worker creates a unique quarantine sibling, atomically
   moves each expected entry with `renameat2(RENAME_NOREPLACE)`, compares the moved descriptor to
   the retained expected descriptor, and restores or leaves a mismatch instead of deleting it.
   The admitted root is moved by the same protocol before its contents are removed. The lock,
   parent identity, and quarantine descriptors remain valid through the entire operation; any
   mismatch, replacement, non-empty state, or close error leaves the path and reports cleanup
   failure. The image-control cleanup is updated with the same owner boundary where applicable.
3. **Directory materialization snapshot.** Runtime and cache trees require a descriptor-relative
   canonical pre/post snapshot. The snapshot includes sorted entry names, type, mode, symlink
   target, regular-file size/digest, and recursive directory identity; directory `fstat`
   comparison includes link count, size, mtime, and ctime. The worker re-enumerates the source
   after copying and verifies the destination tree before publication. A deterministic mutation
   after the first enumeration or during recursion rejects before the staged tree is consumed.
4. **Regression ownership.** `scripts/run-fresh-worker-unit-smoke` owns deterministic cgroup
   admission, quarantine replacement, and directory post-enumeration mutations; the image-control
   smoke owns its cgroup admission/cleanup mirror. The closure plan, implementation, and handoff
   name these cases explicitly, and hosted Installed qualification is the required end-to-end
   acceptance for the authenticated boundary.
5. **Baseline-chain executable selection.** `scripts/check-baseline-chain` has two explicit
   environment profiles. With neither fresh marker present, its isolated Git environment uses
   `PATH=/usr/bin:/bin` for ordinary host execution. In the capable aggregate it requires exactly
   `ALIGN_LLM_FRESH_COMPILER=1`, `ALIGN_LLM_TOOL_ROOT=/tools`, and the worker-provided
   `ALIGN_LLM_BASELINE_GIT_DIR=/baseline-git`, `ALIGN_LLM_BASELINE_GIT_COMMON_DIR=/baseline-git`,
   and `ALIGN_LLM_BASELINE_GIT_WORK_TREE=/workspace` values, then uses `PATH=/tools` so the bare
   `git` argv resolves only to the authenticated `/tools/git` copy. The child environment carries
   only the corresponding `GIT_DIR`, `GIT_COMMON_DIR`, and `GIT_WORK_TREE` values. Any partial or
   different marker/tool-root/Git-view tuple rejects before a Git subprocess starts; no ambient
   `PATH` or Git identity value is copied into either profile. This keeps the baseline-chain
   checker aligned with the aggregate's closed executable inventory without exposing the whole
   runtime tree through `PATH`.

The repair may not be reviewed as merge-ready until the changed closure rows point to these
implementations and the focused commands pass with the current exact head.

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
every C1-C5 core focused target through the hosted graph. A new check must be classified deliberately
as a routine functional regression or a focused qualification. Routine regressions may be assigned
to the hosted graph, the capable-only set, or both through dependency after their runtime and
maintenance cost are measured. Security, resource-limit, race, fuzz, stress, platform, mutation,
and benchmark qualification may remain outside every aggregate; the owning design must name the
exact command and trigger. Aggregate membership is not a proxy for test importance.

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
| Worker tool/Git child ownership | `scripts/fresh-align-compiler` | route `run_tool` and `git` through the same descriptor-bound owned-child runner as build and aggregate; no direct `Popen` remains in probe or source identity paths | Unit smoke starts a probe and a Git child that create a session-breaking descendant, exceed each stream cap, and time out; the runner records start/group identity, terminates the group and cgroup, reaps descendants, closes pipes, and leaves no owned member. Static inspection rejects a direct probe/source `Popen` call outside the runner. |
| Cgroup leaf ownership | `scripts/fresh-align-compiler` and `image/fresh/control/fresh_image_control.py` | retain parent/leaf descriptors and snapshots; use descriptor-relative cgroup controls, strict membership proofs, the cgroup-v2 unique-leaf/rmdir cleanup primitive under the protected profile writer boundary, and non-ignored cleanup in both worker and image self-test; image-control launch and early-setup failures enter the same post-lease finalizer | The worker lifecycle smoke exercises leaf replacement before cleanup, nonempty/malformed membership, PID reuse, successful descriptor-relative rmdir, and failed removal; the image control smoke exercises the same admission, identity, rmdir, cleanup-failure, and injected child-launch-failure cases, verifies no leaf remains on the successful cleanup path, and requires the platform error when removal cannot be proved. |
| Private-root entry cleanup ownership | `scripts/fresh-align-compiler` | retain opened child/root descriptors through final identity validation and descriptor-relative removal; never close the identity witness before removal | Unit smoke injects replacement before and during child/root removal, verifies the replacement marker and moved original remain unchanged, and requires cleanup failure with all retained descriptors closed. |
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
| Executable baseline chain gate | `scripts/check-baseline-chain` plus `Makefile` | `baseline-check` invokes the complete isolated chain checker after schema validation; source/oracle come from the canonical record and finalization is the unique direct oracle child with exact output paths | The target passes on the recorded tuple and fails on source/oracle/finalization identity, raw-object, ancestry, exact-byte, post-owner, pending-file, and Git-command failure injections. |
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

## 7. Historical acceptance and pull request boundaries

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

## 8. Historical fresh compiler contract (superseded)

This section is retained as the review history for the unmerged `4eb878b` checkpoint. It is
non-normative and must not be used for implementation or adoption. The successor contract in
Section 9 is the only current fresh-compiler contract; where any wording below differs, Section 9
wins.

This revision is the repository-wide prerequisite for future Linux x86_64 adoption that changes
`.align-revision` or claims `ALIGN_LLM_VERIFIED` against a newly built compiler. It is a design
slice only; it does not change the current Makefile or compiler pin. A dependent implementation
must merge this contract first and then implement it in a separate slice. No later Linux x86_64
consumer may introduce a narrower copy of this protocol. This section deliberately does not claim
the aarch64 Linux or aarch64 macOS C7 acceptance environments: each of those environments needs a
separate reviewed platform profile that preserves this trust, identity, process, cache, and cleanup
ledger before it can adopt a changed pin.

### 8.1 Decision, threat boundary, and prerequisites

The final Linux x86_64 `make ci` path is controller-owned from source validation through the last
capable check. It builds the pinned Align compiler in a private target outside `ALIGN_REPO`, keeps
the private build root alive while it launches `capable-checks`, and removes that root only after
the aggregate process has terminated and the compiler descriptor is no longer reachable.
`align-build` is a diagnostic build-only entrypoint; it is not a prerequisite of the final `ci` path
and its output must never be reused by `ci`.

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
| `ALIGN_LLM_WORK_PARENT` and timeout variables | N/A: no caller override exists. The controller uses the fixed protected per-user root parent `/run/user/<uid>/align-llm-fresh/roots` and the constants in section 9.8, while `/tmp` is only a platform-checked executable temporary mount and never a private-root parent. A caller cannot redirect cleanup or extend a safety deadline. |
| `ALIGN_LLM_CARGO_CACHE` | N/A: the cache root and its manifest are fields of the authenticated toolchain manifest; a second environment channel would create two cache identities. |
| Fresh-build performance claim | N/A: this slice establishes source/compiler correctness and time-bounded cleanup, not an optimization. Any time-to-passing-patch or build-time claim requires a separate controlled benchmark with the manifest, hardware, sample count, and baseline recorded. |

`make ci` with `hosted-checks`, `capable-checks`, another aggregate, or any focused goal is
rejected by the existing parse-time aggregate guard. Concurrent independent invocations are
unsupported caller behavior; each accepted invocation nevertheless receives a fresh random root,
has no shared mutable Cargo target, and never removes a root it cannot prove it owns. The final
hosted aggregate does not build a compiler: it runs the fresh-controller self-test and uses the
workflow's separately selected compiler for hosted-compatible product checks. Only the capable
`make ci` acceptance proves a real fresh compiler build and its use by every capable check.

The `ci` Make control plane is itself fixed before the bootstrap recipe can run. When `ci` is among
the requested goals, the Makefile sets `override SHELL := /bin/sh` and
`override .SHELLFLAGS := -eu -c`, clears and exports `MAKEOVERRIDES`, and clears
`MAKEFLAGS`/`GNUMAKEFLAGS` on the worker recipe. A command-line or environment `SHELL`,
`.SHELLFLAGS`, or `MAKEOVERRIDES` value cannot select the recipe shell or inject a recursive Make
assignment. The implementation's parse-time negative fixtures prove that a marker shell and a
`MAKEOVERRIDES=ALIGN_LLM_COMPILER_DESCRIPTOR=...` value are rejected or cleared before the
bootstrap is launched. The documented `ALIGN_REPO` and manifest values are copied into explicit
controller-owned environment assignments; they are not propagated through `MAKEOVERRIDES`.

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
without an ASCII escape for ordinary printable characters, and one final LF. Every object and
array has a fixed field or element order; a producer must not rely on a JSON map's implementation
order. The complete nested order is:

```text
controller: path, sha256
bootstrap: path, sha256, api
platform: os, architecture, kernel_minimum, python_minimum, make_minimum
tool: name, path, namespace_path, mode, sha256, argv, stdout, stderr
runtime_binding: source, target, kind, manifest, manifest_sha256
cache: root, manifest, manifest_sha256, entry_count
cache_entry: path, kind, mode, size, sha256
runtime_manifest_entry: path, kind, mode, size, sha256
```

`controller` contains `path` equal to `scripts/fresh-align-compiler` and `sha256` as lowercase
64-hex. `bootstrap` contains the fixed path, lowercase 64-hex image digest, and `api` equal to
`1`. `platform` contains `os` `linux`, `architecture` `x86_64`, `kernel_minimum` `6.8`,
`python_minimum` `3.12`, and `make_minimum` `4.3`.

All strings are valid UTF-8, contain no NUL, and are at most 4,096 bytes except bounded probe
streams, which are at most 65,536 bytes. Absolute paths use one leading `/`, contain no empty,
`.` or `..` component, and are at most 4,096 bytes; relative manifest paths use raw-byte
lexicographic components with the same component restrictions. Decimal integers are unsigned
JSON integers with no leading zero and are at most 64 bits. Modes are four-octal-digit integers
between `0000` and `0777`. `argv` has at most 32 elements and 4,096 total encoded bytes. The
manifest has at most 128 tool records, 256 runtime bindings, a recursive digest manifest depth of
64, 200,000 entries, and 64 MiB of serialized bytes. A cache regular file is at most 512 MiB and
the complete materialized cache is at most 20 GiB. These limits are checked before allocation or
side effects and are part of schema version 1.

The format self-test owns this exact canonical wire vector (the final line terminator shown below
is one LF). It is a syntax/serialization vector rather than a runnable toolchain because the empty
`tools` array is intentionally rejected by the semantic inventory check; it fixes field order,
indentation, integer spelling, and final-LF behavior independently of host paths:

```json
{
  "schema_version": 1,
  "controller": {
    "path": "scripts/fresh-align-compiler",
    "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "bootstrap": {
    "path": "/usr/local/libexec/align-llm/fresh-bootstrap",
    "sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "api": 1
  },
  "platform": {
    "os": "linux",
    "architecture": "x86_64",
    "kernel_minimum": "6.8",
    "python_minimum": "3.12",
    "make_minimum": "4.3"
  },
  "tools": [],
  "runtime_bindings": [],
  "cargo_cache": {
    "root": "/cache",
    "manifest": "/cache/manifest.json",
    "manifest_sha256": "2222222222222222222222222222222222222222222222222222222222222222",
    "entry_count": 0
  }
}
```

The self-test compares bytes, not parsed values, and separately compares a complete synthetic
manifest with the closed tool inventory, bounded runtime digest tree, and zero-entry cache. That
second vector is the acceptance fixture `fresh-compiler-manifest-v1-complete`; it uses deterministic
synthetic executable bytes and paths, so no platform path or mutable host digest is left unspecified
by this design.

`tools` is a closed, ordered inventory with no duplicates. It includes the following currently
observed executable identities for the Align release build and the complete capable graph:

```text
git cargo rustc llvm-config cc cxx ar ranlib linker bwrap sh make python3 env bash prlimit
clang strip objdump objcopy llvm-profdata llvm-bcanalyzer llvm-readobj llvm-nm ld ld.lld id
```

The implementation's source scan and trace must produce the same or a strictly expanded inventory
before implementation acceptance; an executable name or absolute executable path not represented
in this inventory is a `TOOL` error, never a host fallback. Versioned spellings such as
`llvm-config-22`, `clang-22`, `llvm-profdata-22`, and `llvm-bcanalyzer-22` are represented by their
own records when that is the actual argv spelling. The list is therefore closed by the checked
manifest, not by `PATH` discovery.

Each tool record contains `name`, absolute host `path`, absolute namespace `path`, `mode`, lowercase
64-hex `sha256`, `argv`, `stdout`, and `stderr`. `argv` is a nonempty fixed argument vector whose
first element is the absolute host path; `stdout` and `stderr` are bounded ASCII probe results with
JSON escaping only where required by the JSON grammar. The controller opens each host path with
no-follow semantics, requires the declared executable regular-file mode, and hashes the complete
bytes before execution. It then copies the verified bytes into the private `tool-bin` staging
directory with direct create-exclusive operations, hashes and scans the copy again, makes it
read-only, and only then exposes that copy at its namespace path. The host path is never used after
staging. `git`'s expected output must report version 2.45 or newer; `cargo` and `rustc` must match
the manifest's exact Rust 1.96 toolchain; `llvm-config` must report LLVM major 22; the remaining
version and digest values are image-owned rather than inferred from `PATH`.

The manifest also contains `runtime_bindings` after `tools` and before `cargo_cache`. Each binding
has `source`, `target`, `kind`, a complete recursive digest manifest, and `manifest_sha256`.
Bindings are ordered, absolute, no-follow host inputs for dynamic libraries, Rust standard
libraries, LLVM resources, `/usr/bin/env`, the fixed image-owned `/usr/bin/bwrap` namespace
launcher, the fixed `/usr/bin/adoption-namespace` namespace supervisor, and other non-executable or
fixed-launcher files required by the declared tools. The
worker validates each source descriptor, copies the complete
tree into a private `runtime` staging directory with bounded direct operations, hashes the copy,
and then uses only that read-only copy in bwrap. A binding cannot overlap `/src`, `/tools`,
`/cargo`, or `/target`; its source and every descendant are validated before the build root exists.
Runtime regular files may have a stable link count greater than one because installed distribution
trees legitimately hard-link identical resources. Link count is included in each before/after
snapshot and must remain unchanged, while complete bytes are checked against the image-generated
manifest before and during the private copy. This runtime rule does not widen the Cargo-cache rule:
every cache regular file still requires `st_nlink == 1`.
This gives runtime bindings the same hash-then-use rule as tools without exposing a host `PATH` or
an unverified resource directory. The staged `/usr/bin/env` and `/bin/sh` launchers must have the
same digests as the corresponding `env` and `sh` tool records. The fixed schema-2 image profile
also carries two exact executable file bindings for ordinary adoption: `source` and `target`
`/usr/local/libexec/align-llm/request6-adoption-entrypoint`, the image-owned mode-`0755` public
dispatcher, and `source` and `target` `/usr/bin/adoption-namespace`, the image-owned mode-`0755`
namespace supervisor. Both bindings include their complete interpreter and library closures, are
intentionally runtime bindings rather than PATH tool records, and are executable only through their
direct retained descriptors at those fixed targets. The trusted `fresh-supervise` verifies the
dispatcher binding and invokes it through retained FD `14` with `execveat(AT_EMPTY_PATH)`; the
dispatcher digest, image-attestation digest, supervisor-channel ticket digest, and fresh
per-invocation nonce and source-exception digest are included in the `ordinary-adoption/v2` capsule. The ordinary wrapper separately
passes every ordered tool record through retained descriptors, seals those copies in `/tools`, and
resolves `make`, `git`, `tr`, `bash`, Python, and every other bare tool name only from that read-only
inventory. The dispatcher, helper binding, and complete tool inventory are root-owned image inputs and
are required by the installed profile before Request 6 ordinary adoption is eligible.

There are no unlisted identity probes. In particular, the controller does not run `command -v`,
`which`, a shell, `rustup`, a Git hook, a Cargo config helper, or a version command whose path came
from the environment. `bwrap` is probed because it owns the build namespace. `sh` is probed because
Cargo build scripts may request it; the build environment's `PATH` contains only the declared
namespace launchers under `/tools`. `RUSTC`, `CARGO`, `LLVM_CONFIG`, `CC`, `CXX`, `AR`, `RANLIB`,
and the target linker variable are all set to those namespace paths, whose executable bytes were
checked against the absolute host paths before the namespace was built. Cargo configuration,
rustup configuration, wrapper variables, proxy variables, credentials, and network configuration
are cleared rather than inherited. The capable aggregate receives `PATH=/tools`, `MAKE=/tools/make`,
`ALIGN_LLM_BWRAP=/tools/bwrap`, and `ALIGN_LLM_PRLIMIT=/tools/prlimit`; all Python and shell
shebangs therefore resolve to staged tool records. The implementation updates
`eval/runners/run-coding-task.py` to honor both explicit fresh-mode paths, eliminating its current
`/usr/bin/bwrap` and `/usr/bin/prlimit` fallbacks.

`cargo_cache` contains `root`, `manifest`, `manifest_sha256`, and `entry_count`. Both paths are
absolute and are opened before any owned output root is created. The cache manifest uses the same
canonical JSON rules and lists every admitted relative path in raw-byte lexicographic order with
`kind`, `mode`, `size`, and `sha256`. Only regular files and directories with the declared modes
are admitted. The hard-link check (`st_nlink == 1`) applies only to regular files; directory link
counts are not interpreted as hard-link evidence. Symlinks, devices, FIFOs, sockets, whiteouts,
absolute paths, `..`, duplicate paths, and entries outside the declared root reject. Cache entries
named `config`, `config.toml`, `credentials`, `credentials.toml`, `rustc-wrapper`, or
`rustc-workspace-wrapper`, any `.cargo` directory, and any path that could supply Cargo's
`target-dir`, source replacement, registry credential, proxy, or wrapper configuration reject.
Only the explicit registry and Git cache subtrees used by the locked offline build are admitted;
the allowlist is part of the manifest version and is checked before copying. The manifest's digest
is checked against the top-level record and the complete source cache is checked before copying.
The tracked project `/src/.cargo/config.toml`, when present, is a reviewed source input and is the
only project configuration Cargo may read; it is included in the source manifest. No CARGO_HOME,
HOME, RUSTUP_HOME, environment, or cache file can add a second configuration source. Namespace
root/output permissions make a source `target-dir` outside `/target` fail before a write.

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

The root owns exactly these children. `source`, `runtime`, and `tool-bin` are created mode `0700`
for staging and are changed to mode `0555` only after their complete post-copy scans succeed; the
other children retain their creation modes. No child is replaced or renamed:

```text
source/       0700 -> 0555 source materialization
cargo-home/   0700 private Cargo home
cargo-target/ 0700 empty Cargo target
runtime/      0700 -> 0555 copied runtime bindings
tool-bin/     0700 -> 0555 copied declared tools and compiler artifacts
descriptor/   0700 compiler descriptor and cleanup journal
```

The cache materializer walks the retained source-cache descriptor and copies each manifest entry
directly into `cargo-home`: directory entries use `mkdirat` with mode `0700`, and regular files use
`openat(O_CREAT|O_EXCL|O_NOFOLLOW, 0600)`, bounded reads, a fresh SHA-256, `fsync`, and a final
descriptor-relative enumeration. The hard-link check applies to source regular files only, never
to directories. It never uses `cp -a`, a recursive rename, a symlink-following library walk, or a
cache path as `CARGO_HOME`. A source cache mutation during a copy produces a digest or size
mismatch; a destination collision, symlink, hard link, unexpected special file, or post-copy extra
path produces a cache error. The source cache remains read-only and no network access is possible.

The build runs through the declared `bwrap` with the exact namespace construction below. The
`--tmpfs /` operation creates an empty namespace root rather than retaining the host root mount;
the subsequent explicit binds are the complete visible filesystem:

```text
bwrap --clearenv --die-with-parent --new-session --unshare-user --unshare-pid --unshare-net \
  --tmpfs / --proc /proc --dev /dev \
  --dir /src --dir /tools --dir /cargo --dir /target --dir /usr --dir /usr/bin --dir /bin \
  --ro-bind <private>/source /src \
  --ro-bind <private>/tool-bin /tools \
  --bind <private>/cargo-home /cargo \
  --bind <private>/cargo-target /target \
  --ro-bind <private>/runtime/... <manifest target paths> \
  --chmod 0555 / \
  --setenv HOME /nonexistent --setenv TMPDIR /target/tmp --setenv PATH /tools \
  --setenv MAKE /tools/make --setenv CARGO_HOME /cargo --setenv CARGO_TARGET_DIR /target \
  --setenv CARGO_NET_OFFLINE true \
  --setenv ALIGN_LLM_BWRAP /tools/bwrap --setenv ALIGN_LLM_PRLIMIT /tools/prlimit \
  -- /tools/cargo build --manifest-path /src/Cargo.toml --locked --offline --release \
     -p align_runtime -p align_driver
```

`<manifest target paths>` expands only to the ordered, digest-checked runtime bindings; it is not
an unconstrained host-root bind. The `--dir` operations occur before the final root chmod, and
`/cargo` and `/target` remain writable because their explicit binds are created with the caller's
private-root ownership after the root mount is constructed. The namespace has no host `HOME`, no
host `/tmp`, no host Cargo target, and no original `ALIGN_REPO`; only the declared runtime paths
and `/src`, `/tools`, `/cargo`, and `/target` are visible. The required `--unshare-pid` is tested
by the acceptance fixture with a double-forking child; absence of the PID namespace is a platform
error. `TMPDIR` points into a pre-created directory below `/target`, so no additional writable host
or namespace path is needed.

The exact build argv is:

```text
/tools/cargo build --manifest-path /src/Cargo.toml --locked --offline --release -p align_runtime -p align_driver
```

The controller also sets the namespace tool variables from the manifest. The `cargo` argv element
is `/tools/cargo`; its host path, digest, copied bytes, and required resource bindings were
validated before that namespace path was exposed. The same rule applies to `rustc`, `llvm-config`,
the C/C++ tools, linker, and `sh`. It rejects any Cargo output outside `/cargo` or `/target`, and
after success requires the release compiler plus its adjacent runtime artifacts to be regular files
with the declared build identity. The build is never allowed to reuse a pre-existing target or a
mutable Cargo home.

Cleanup has one owner: the worker that created the root. It first terminates and reaps every owned
child, closes source/cache/output descriptors, then removes only known children in reverse order
using the retained root descriptor. Before unlinking the random root name it compares the parent
entry's no-follow device/inode, directory type, mode, and owner to the creation identity. Directory
size, link count, mtime, and ctime are intentionally not creation invariants because owned staging
changes them. If the name is absent, renamed, replaced, or
contains an unexpected entry, cleanup reports failure and leaves the path; it never follows or
recursively deletes it. A cleanup failure never changes a successful or primary phase into a
different category; it appends one `cleanup` line.

### 8.5 Compiler descriptor and execution interposition

After the build, the worker writes one temporary canonical JSON `CompilerDescriptor` under the
private `descriptor/` child. It has schema version `1`, exact field order
`schema_version`, `align_revision`, `source_manifest_sha256`, `toolchain_manifest_sha256`,
`compiler_path`, `compiler_sha256`, `runtime_paths`, and `launcher_policy`. It is UTF-8, two-space
indented, has no unknown fields, and ends with one LF. `compiler_path` and each `runtime_paths`
entry are descriptor-relative records `{path, mode, size, sha256}` below the private root; the
descriptor records no original `ALIGN_REPO` path. The compiler digest and every runtime-artifact
digest are over complete regular-file bytes. Before the descriptor is written, the worker verifies
each artifact through a retained no-follow descriptor, changes all compiler/runtime files to
read-only, and holds those descriptors until the aggregate exits. The descriptor and its selected
files are therefore an immutable private snapshot, not path-only hints. The descriptor is not a
persisted project artifact and is valid only while its owning worker holds the root.

The worker launches the capable aggregate itself with this exact environment contract:

```text
ALIGNC=<align-llm>/scripts/alignc
ALIGN_LLM_FRESH_COMPILER=1
ALIGN_LLM_COMPILER_DESCRIPTOR=<private descriptor path>
ALIGN_LLM_COMPILER_REVISION=<descriptor align_revision>
```

`ALIGNC` and the three `ALIGN_LLM_*` values are exported through the recursive Make boundary. The
worker also exports the private `PATH=/private-root/tool-bin`, `MAKE=/private-root/tool-bin/make`,
`ALIGN_LLM_BWRAP=/private-root/tool-bin/bwrap`, and
`ALIGN_LLM_PRLIMIT=/private-root/tool-bin/prlimit` values for the host-side capable aggregate;
the corresponding bwrap values are `/tools/...`.
`Makefile`, every compiler-using script, and every nested runner must use the common
`scripts/alignc` launcher; a raw `../align/target/**/alignc`, `alignc` from `PATH`, or sibling
fallback is forbidden while `ALIGN_LLM_FRESH_COMPILER=1` is present. The implementation adds a
static compiler-call-site check and a runtime negative fixture that places a marker-writing fake
compiler at every old fallback path.

The static inventory explicitly includes current non-Make consumers: `scripts/check-format`,
`eval/runners/record-baseline.py`, the fixed-evaluation runners, and every prompt/evaluation smoke
that invokes Align. In particular, `record-baseline.py` must not retain its current direct sibling
release-compiler lookup; fresh mode passes the common launcher and descriptor through its explicit
compiler input. A source scan fails if any fresh-capable path reads the sibling release/debug
compiler, invokes bare `alignc`, or resolves an executable through the ambient `PATH`.

In fresh mode `scripts/alignc` does not search `ALIGNC`, `PATH`, or `ALIGN_REPO`. It reads the
descriptor with no-follow operations, verifies the four identity fields and all descriptor-relative
paths, opens the compiler executable, requires a regular executable, hashes it completely, and
executes that already-open file with `execveat(AT_EMPTY_PATH)`. If `execveat` is unavailable, it
fails closed; a pathname `/proc` fallback is not accepted. The wrapper emits no bytes before the
compiler and has no cache or output side effect. Consequently compiler identity is checked at the
actual process boundary for `check`, `run`, `build`, `fmt`, every focused script, every recursive
Make child, and aggregate-internal invocations below Make.

The child Make invocation is the only aggregate entrypoint admitted by the worker. It is a direct
argument vector, not a shell string, with `MAKEFLAGS=`, `GNUMAKEFLAGS=`, and `MAKEOVERRIDES=`
cleared, fixed `SHELL=/bin/sh`, and explicit `--silent --no-print-directory -j1 capable-checks`.
It passes `ALIGNC`, the descriptor, the private tool paths, and the source identity as
controller-owned environment values with their exact documented origin. The child cannot replace
them with a caller command-line assignment because the worker rejects `ALIGNC` on the outer `ci`
call, clears recursive Make overrides, and supplies the child values as the only accepted
controller-owned assignments. A synthetic child that deliberately ignores `ALIGNC`, a synthetic
script that directly names the old sibling binary, and a marker injected through `MAKEOVERRIDES`
must all fail the fresh identity unit before their marker can run.

### 8.6 Process topology and ownership

The worker is the owner of one ordered process set: tool probes, the bwrap build, the compiler
identity probe, and the recursive capable aggregate. It starts each with `close_fds=True`, a new
session, binary stdout/stderr pipes, and a captured PID start-time and process-group ID. Output is
drained concurrently in 8,192-byte chunks, retained to 64 KiB per stream, and marked overflow after
the cap. No whole-output capture is allowed. Probe output is compared to the manifest before the
next probe. Compiler and aggregate output is captured for bounded internal diagnostics but is never
forwarded to the public controller streams; this is required for the exact status grammar in
section 8.7. A failure reports only its category and checked-in phase identifier, never a child
path, environment value, compiler diagnostic, or source byte.

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
`fresh compiler self-test: PASS`. A failure has exit `1`, empty stdout, exactly one primary line on
stderr, and at most one following cleanup line on stderr. No child stdout/stderr is forwarded on
success or failure. The primary grammar is:

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
| Tool identity | worker | No-follow executable open, full digest, exact version vector, copied private snapshot, sequential owned probe, closed executable inventory | `fresh-compiler-tool-identity-smoke` covers missing, symlink, replacement, version, stderr, timeout, overflow, unlisted executable, and nonzero probes for every named tool. |
| Runtime binding identity | worker plus bwrap | Complete recursive source digest, private copied snapshot, post-copy scan, target-parent construction, read-only namespace bind | `fresh-compiler-runtime-binding-smoke` mutates a library/resource/env binding during validation and after staging, checks the copy digest, and proves the host path is never used by the namespace. |
| Signal during setup | worker | Cancellation state before root ownership; no unowned deletion | `fresh-compiler-signal-setup-smoke` injects each supported signal after manifest, source, cache, `/tmp`, and child-owner transitions and verifies root absence or bounded cleanup error. |
| Source revision and Git | worker | Raw revision grammar, retained worktree/Git/common/index/object descriptors, fixed Git environment | `fresh-compiler-source-revision-smoke` covers encoding, tags, shallow/promisor/alternate/graft/replace/config/hook/filter cases and exact error precedence. |
| Raw source closure | worker | Tree/index and complete descriptor-relative worktree manifest; root `target/` is the only output exception | `fresh-compiler-source-tree-smoke` covers extra/ignored/empty/case-fold/prefix/special/symlink/assume-unchanged/skip-worktree/filter and mode/object mismatches without helper execution. |
| Ancestor/root ABA | worker | Retained descriptors and post-materialization manifest equality; no later Git pathname lookup | `fresh-compiler-source-aba-smoke` swaps ancestors, root, `.git`, and common directory; a same-HEAD repository with an extra Rust input is rejected and no outside marker is read. |
| Source materialization | worker | Direct no-follow create-exclusive copy, per-file digest, symlink target containment, private read-only source | `fresh-compiler-materialization-smoke` injects disappearing/replaced/type-changing files and proves no build starts and no outside path is opened. |
| Cache trust | worker | Authenticated cache manifest, explicit Cargo-cache allowlist, descriptor-relative source, regular-file-only hard-link check, directory-aware copy, size/digest/fsync/post-scan | `fresh-compiler-cache-smoke` covers missing/changed/extra/symlink/hardlink/special/rename/escape/config/wrapper entries and confirms no network or source-cache mutation. |
| Private root construction | worker | `/tmp` mode/identity, eight exclusive attempts, writable staging then read-only final modes, fixed child set, owner token and device/inode | `fresh-compiler-root-smoke` covers collision exhaustion, parent symlink/mode, child collision, staging-mode transition, root replacement, and ancestor rename. |
| Build containment | worker plus bwrap | Empty `--tmpfs /` root, explicit read-only runtime/tool/source binds, writable only `/cargo` and `/target`, explicit user/PID/net namespaces, exact locked offline argv | `fresh-compiler-build-namespace-smoke` places marker files in host root/cache/target/source/network/HOME/sibling target paths and uses a double-forking child to prove only owned outputs change and the PID namespace is required. |
| Private Cargo target | worker | Empty mode-0700 `cargo-target`, never `ALIGN_REPO/target`, no reuse or rename | `fresh-compiler-empty-target-smoke` seeds a stale target and symlinked target cases, requiring rejection or clean private build with no seed marker. |
| Build failure/timeout | worker | One process owner, bounded deadline, group/tree termination, reap, reverse cleanup | `fresh-compiler-build-failure-smoke` covers Cargo nonzero, hanging build script, output overflow, signal, and descendant survival. |
| Compiler descriptor | worker | Canonical schema-1 temp descriptor, exact source/tool/compiler/runtime-artifact digests, retained descriptors, read-only snapshot, and contained runtime paths | `fresh-compiler-descriptor-smoke` covers field order, digest, path, mode, runtime-artifact mutation, descriptor replacement, and owner-root replacement cases. |
| Direct compiler call | `scripts/alignc` | Fresh mode ignores fallback and PATH, hashes/open-execs the descriptor-selected binary | `fresh-compiler-direct-identity-smoke` replaces old sibling/debug/PATH compilers with marker writers and verifies the marker never runs. |
| Internal Make/compiler call | Makefile, `scripts/alignc`, focused scripts | Exported descriptor and launcher survive recursive Make; all call sites use the common launcher; `SHELL`, `.SHELLFLAGS`, `MAKEOVERRIDES`, and fallback tool paths cannot cross the boundary | `fresh-compiler-internal-identity-smoke` exercises `$(ALIGNC)`, hardcoded helper calls, recursive Make, `fmt`, `check`, `build`, every focused script, hostile shell values, and descriptor injection through `MAKEOVERRIDES`; a bypass is rejected before its marker. |
| Aggregate ownership | worker plus Makefile | Worker launches exactly one option-cleared `-j1 capable-checks`; outer `ci` owns no second aggregate | `fresh-compiler-aggregate-topology-smoke` covers aggregate-plus-goal parse rejection, child variable origin, order, no jobserver, and compiler descriptor propagation. |
| Aggregate timeout/early exit | worker | First failure stops later goals; controller kills/reaps all descendants and keeps descriptor root until exit | `fresh-compiler-aggregate-lifecycle-smoke` covers first focused failure, timeout, signal at each goal boundary, descendant escape, and cleanup ordering. |
| Cleanup success | worker | Reverse known-child removal, parent identity proof, root absence before PASS | Every positive mode runs a final absence assertion; `fresh-compiler-cleanup-smoke` verifies no root, descriptor, target, cache copy, or marker remains. |
| Cleanup failure | worker | Never delete an unowned/replaced name; append one cleanup line without masking primary | `fresh-compiler-cleanup-failure-smoke` injects close, unlink, parent replacement, live-child, and PID-reuse failures and checks exact primary/cleanup lines. |
| Hosted topology unit | Makefile/workflow | Self-test only; no compiler build or network; hosted product checks use their explicit compiler | Ubuntu 24.04/GNU Make 4.3 runs `fresh-compiler-topology-unit` before the existing hosted list and records that it is not fresh-build evidence. |
| Capable integration | worker/Makefile | Real pinned fresh build, descriptor interposition, complete capable graph, cleanup after aggregate | On the minimum capable Linux image, one `make ci` passes with the manifest, and the old sibling target/debug/PATH compilers are absent from all executed identities. |
| Identity-bound baseline refresh | baseline owner plus implementation branch | Final Makefile state is the recorded source; two deterministic reference samples, oracle, finalization, digest, and strict ancestry are refreshed before capable evidence | `fresh-compiler-baseline-integration-smoke` runs the section-2.4 source/oracle/finalization chain, exact artifact manifest, pending-file, raw-object, merge-ancestry, and `baseline-check` regressions after the implementation changes the Makefile. |
| Unsupported concurrent entrypoints | Makefile/worker | `ci` plus any aggregate/goal is parse-rejected; separate processes are unsupported and roots are never shared | `fresh-compiler-concurrency-smoke` enumerates every aggregate-plus-focused and aggregate-plus-aggregate order, plus two independent processes, and checks rejection/no shared deletion. |
| Platform profile boundary | topology plan | This section claims only Linux x86_64; aarch64 Linux and aarch64 macOS require separate reviewed profiles before C7 adoption | `fresh-compiler-platform-profile-smoke` proves unsupported platform rejection and records the named extension gate; no non-x86 adoption may use the x86 profile as evidence. |
| Align code/ownership parity | N/A | No Align source, public Align type, persisted result, or allocator is changed by this topology slice | N/A: compiler input and process artifacts are external to Align; the implementation review records this explicit exclusion. |

The matrix is also the implementation-to-diff checklist. Every row must point to a concrete function
or recipe and a passing named test before the dependent implementation is reviewed. A row may be
marked deferred only by changing this design first; the four formerly unresolved choices in the
request register are not deferred here.

### 8.9 Constants, compatibility, and acceptance commands

The minimum acceptance environment for this section is Ubuntu 24.04 x86_64, Linux kernel 6.8 or
newer, GNU Make 4.3, CPython 3.12, Git 2.45 or newer, Rust/Cargo 1.96.0, LLVM 22, and the fixed
bootstrap/bwrap image manifest. Tool versions newer than these are supplementary evidence only.
The fresh build and capable aggregate require the namespace capability declared by `bwrap`; the
ordinary hosted runner is not allowed to claim the capable result when its namespace probe fails.
This section does not satisfy the separate Request 7 `git-2.45-compat` acceptance requirement for
an immutable OCI image with `/usr/bin/git` exactly `2.45.0`; that image and job remain a named
Request 7 prerequisite. Likewise, the C7-required `aarch64-unknown-linux-gnu` and
`aarch64-apple-darwin` environments remain blocked on their own reviewed platform profiles and
must not report this x86_64 check as compatibility evidence.

The fixed monotonic deadlines are: each tool probe 5 seconds; manifest/source/cache validation
120 seconds; source materialization 120 seconds; private-root construction 10 seconds; fresh Cargo
build 1,800 seconds; compiler descriptor and identity probe 10 seconds; capable aggregate 1,800
seconds; termination grace 1 second; escalation/reap 5 seconds; and final cleanup 30 seconds.
Output caps are 64 KiB per phase stream and 1 MiB for the whole controller diagnostic stream. The
controller retains those bytes only for bounded internal diagnostics and never forwards them to
the public streams. A timeout includes all children of the owned phase, not merely its direct
process. These values are constants in the worker, not environment or Make inputs.

The design gate runs these docs-only checks before implementation:

```text
git diff --check
for file in docs/align-requests.md docs/specs/check-gate-topology.md; do
  awk '/^```/ { count++ } END { if (count % 2 != 0) exit 1 }' "$file"
done
make gate-topology-check
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
4. Because the implementation changes `Makefile`, refresh the identity-bound C0 baseline in the
   same enabling delivery: create the final clean implementation source commit, record the two
   deterministic reference samples, commit the regenerated oracle, finalize the canonical baseline,
   and run the complete section-2.4 structural and ancestry checks. The baseline source, oracle,
   and finalization commits must be ancestors of the reviewed implementation head and its merge
   result before `baseline-check` can be evidence. This is required even if the measured task
   verdicts are unchanged.
5. Run the local synthetic matrix, the Ubuntu 24.04 hosted topology unit, `baseline-check`, and
   one capable `make ci` at the unchanged pinned revision. The old direct sibling compiler must
   not be used by the fresh path, and the complete source-to-build-to-aggregate cleanup evidence
   must pass. The capable result is not accepted until the refreshed baseline is valid.
6. Only after that implementation merges may a separate consumer adoption slice update
   `.align-revision`, rebuild the sibling release/runtime if required, add its focused target, and
   run the original acceptance gate through the fresh `make ci` path.

No Request 6, Request 7, Request 9, C7, or later Linux x86_64 consumer implementation may consume
the controller, descriptor, cache, wrapper, or aggregate behavior before step 3 merges. A proposed
API, unmerged bootstrap, host image, or hypothetical compiler binary is not an implementation
input. C7's aarch64 Linux and aarch64 macOS consumers additionally require their platform-profile
designs and implementations before adoption. The request register remains the lifecycle authority
for each consumer; this section owns only the common Linux x86_64 fresh-compiler topology and its
evidence.

## 9. Fresh compiler transition contract (successor redesign)

This section is the merged successor contract for the historical contract in Section 8 and is the
only normative fresh-compiler contract in this document. Its wire, manifest, and source-identity
foundations are merged; FRESH-WORKER and FRESH-IMAGE still must implement the remaining repository
and host-profile behavior before `.align-revision` changes. Neither capability may consume an older
Section 8 rule by implication.

This successor is deliberately split into two planes. The image plane is the externally deployed
`fresh-supervise`/`fresh-bootstrap` pair and its fixed toolchain manifest; the repository plane is
the checked-in worker and Make integration. The fixed image manifest never contains a digest of a
repository worker, because a reviewed worker change must not require an out-of-band image-manifest
edit. After checkout, the trusted supervisor creates a per-invocation signed run capsule containing
the exact repository head, the canonical `ALIGN_REPO` selection, and the current worker digest. The
bootstrap authenticates that capsule,
seals the worker bytes, and passes only the sealed snapshot to the repository-plane worker. Thus the
image deployment and worker implementation are separate failure domains and may be developed in
parallel against this contract, but both are prerequisites for fresh adoption. The worker is not a
mutable input to image deployment and cannot create a manifest-update cycle.

### 9.1 Scope, trust root, and public surface

The profile in this section claims only Ubuntu/Linux x86_64 with kernel 6.8 or newer, GNU Make 4.3,
CPython 3.12, Git 2.45 or newer, Rust/Cargo 1.96.0, LLVM 22, and a bubblewrap installation that
passes the namespace, overlayfs, and namespace-owned `/target/tmp` no-symlink-mount self-tests. The
bwrap build is pinned to v0.11.2 commit `1b80120ef26a28e065e67f89bfef873f13bdd317` and must support
`--bind-fd`, `--ro-bind-fd`, `--overlay-src`, and `--overlay`; the kernel must permit the owner-only
upper/work pair and `mount_setattr(MOUNT_ATTR_NOSYMFOLLOW)` in the sandbox user namespace. Compiler
identity is carried by authenticated read-only handoff files inside the `/tools` bind. No compiler
identity or worker handoff descriptor is inherited by the legacy aggregate or its nested validation
bwrap. Ordinary Request 6 adoption is an explicit, narrower exception: the authenticated
repository worker receives sealed authority FDs `12`, `13`, and `15` as fixed input; it rewinds those
byte-bearing descriptors
and supplies them to the ordinary outer bwrap only as the sources of fixed `--ro-bind-fd` operations
at `/authority/capsule`, `/authority/worker`, and `/authority/nonce`. Pinned bwrap consumes and
closes those source descriptors while creating the read-only binds; no authority FD is inherited by
the namespace helper, an ordinary Make child, the legacy aggregate, the nested validation bwrap,
or any other repository-controlled process. The nested
validation bwrap has one separate exception: its prepared user-namespace descriptor is inherited
through `--userns <fd>`, so the bwrap forwarder must preserve that exact descriptor through its
`execve` boundary. No protected-fd seccomp filter is part of this profile. The platform self-test
instead proves that a read-only `/tools` bind pins the descriptor, guard, compiler, and runtime
archive as one immutable sibling bundle. C7's aarch64 Linux and aarch64 macOS environments require
separate platform profiles.
Request 7's immutable image whose `/usr/bin/git` is exactly Git 2.45.0 remains a separate
prerequisite. The accepted `/tmp` mount must be executable: a `noexec` mount is a `PLATFORM`
failure before private-root creation. The accepted image also provides the fixed process, descriptor,
inode, and temporary-entry limits in Section 9.8; a host that cannot enforce those limits is outside
this profile.

The trust root is the runner-installed image-owned ELF supervisor
`/usr/local/libexec/align-llm/fresh-supervise`. Its path, mode `0755`, digest, interpreter runtime,
and fixed entrypoint policy are image-owned inputs. The supervisor invokes the image-owned bootstrap
`/usr/local/libexec/align-llm/fresh-bootstrap`, whose path, mode, digest, interpreter, and API are
also image-owned. The same trusted runner image owns the fixed toolchain manifest at
`/usr/local/share/align-llm/fresh-toolchain.json`; that manifest authenticates image tools and
runtime bindings, but deliberately does not authenticate a repository worker digest. The installed
verification keys are the root-owned mode-`0444` raw Ed25519 keys
`/usr/local/share/align-llm/image-verifier.pub` and
`/usr/local/share/align-llm/run-verifier.pub`. A deployment mounts one root- or effective-uid-owned
read-only directory at `/run/align-llm-fresh`: `image-attestation.dsse`, `image-digest`, and
`provenance-digest` are single-link regular mode-`0444` files, while `run-signing-seed` is a
single-link regular mode-`0400` 32-byte seed whose derived public key must equal the installed run
verification key. The two digest files contain one canonical `sha256:<64 lowercase hex>` value and
final LF. No private signing seed is an image layer, repository file, build argument, environment
variable, or attestation payload.

The following runner-invocation path is limited to legacy `ci`, fresh `adoption`, image `build`, and
`self-test` modes. The external runner supervisor is the trust boundary for the image and for each
invocation. Before
checkout or bootstrap dispatch, the trusted job entrypoint verifies a signed in-toto DSSE envelope
with predicate type `https://align-llm.dev/attestations/runner-image/v1` against the pinned verifier
identity `align-llm-runner-image-v1`. It verifies the immutable OCI image digest
(`sha256:<64 lowercase hex>`), image provenance digest, supervisor digest, bootstrap digest, and
fixed-manifest digest. After checkout, it opens the retained project root. For `ci`, the focused
fresh `adoption` mode, and image `build`, the existing `ALIGN_REPO` input remains the optional
non-empty project-root-relative path (default `../align`) with no NUL or absolute form. For the
legacy modes described here, it then opens
`scripts/fresh-align-compiler` through the retained project descriptor with
`O_RDONLY|O_NOFOLLOW|O_CLOEXEC`. Before hashing or signing, the supervisor requires the worker to be
an euid-owned single-link regular `0755` file no larger than
`fresh_worker_max_bytes = 4194304`, reads exactly its descriptor-reported bytes in bounded chunks
within a fixed 5-second monotonic snapshot deadline, and rechecks its device, inode, type, link count,
mode, and size after the read. A FIFO, directory, symlink, oversized file, short read, replacement,
or read/deadline failure is rejected before the run capsule is created; no supervisor operation
hashes an unbounded, blocking, or pathname-reopened worker.
It computes the current repository head and worker digest from those retained descriptors, and signs
a second run capsule with predicate type `https://align-llm.dev/attestations/runner-invocation/v1`. The image attestation is
passed as a sealed read-only memfd at descriptor `6`; the per-invocation run capsule is passed as a
sealed read-only memfd at descriptor `5`. Neither is supplied by a repository environment variable.
The supervisor's pinned verification key, verifier binary digest, accepted predicate policy, and
run-capsule signer identity are image-deployment inputs, not repository files or caller environment.
The hosted and capable acceptance records must include both envelope digests, both predicate
digests, the image/manifest/supervisor/bootstrap tuple, the repository head, canonical
`align_repo_relative`, and the worker digest. The fixed bootstrap repeats the same no-follow,
regular-file, link-count, mode, size, bounded-read, and post-read identity checks against its sealed
worker snapshot before executing it.
A mutable image, unsigned/replayed attestation, missing descriptor, tuple mismatch, or legacy run
capsule whose repository head, canonical sibling path, or worker digest does not match the retained
checkout is rejected before worker execution and before private-root creation.

The Request 6 `ordinary-adoption` path is separate from that legacy flow. It does not open
`scripts/fresh-align-compiler`, create a `runner-invocation/v1` capsule, or pass run-capsule FD `5` to
its worker. After the image envelope and fixed schema-2 manifest are authenticated, the supervisor
retains the image-owned Request 6 dispatcher at FD `14`, walks and retains the absolute Align root as
FD `18`, creates the per-invocation ordinary nonce challenge at FD `15`, creates a connected
`SOCK_SEQPACKET|SOCK_CLOEXEC` supervisor channel, forks exactly one dispatcher child, keeps the parent
endpoint in `fresh-supervise`, and passes the child endpoint as FD `16` plus FD `18`. The parent sends
one fresh 32-byte ticket, retains its parent endpoint, and keeps it open until the helper exits; the
child endpoint remains inherited by the dispatcher, worker, and namespace helper. Only the child
receives project-root FD `4`, image-attestation FD `6`, manifest FD `8`, nonce FD `15`, channel FD `16`,
retained Align-root FD `18`, and the validated named path values, then invokes the retained dispatcher
descriptor. The dispatcher authenticates its current-parent peer PID, stable `/proc/<pid>/stat`
start-time, the controlled procfs magic-link executable digest, exact bounded
`fresh-supervise\0--mode\0ordinary-adoption\0` command line, ticket, and FD `18` before it can sign a
capsule; a directly invoked dispatcher has no acceptable supervisor channel and is rejected. The
dispatcher opens and authenticates `scripts/run-json-scan-row-ownership-adoption` as bounded source
data, binds the project/index/raw-tree/exception/Align identities and fresh nonce into
`ordinary-adoption/v2`, seals the worker, capsule, and nonce on FDs `13`, `12`, and `15`, and enters
the separate ordinary worker vector. No legacy bootstrap, run capsule, or `fresh-align-compiler` path
is reachable from ordinary mode.

The accepted pre-bootstrap entrypoint is the image-owned `fresh-supervise`, not a repository shell.
The trusted job entrypoint passes it one of the two public project requests
`make --no-print-directory ci` or
`make --no-print-directory json-scan-row-ownership-adoption`; FRESH-IMAGE-REQUEST6 additionally
admits the exact `--mode ordinary-adoption` selector, and the image-only qualification vectors are
exactly `--mode build` and `--mode self-test`. `fresh-supervise` validates one of those vectors as
input and never asks GNU Make to parse the retained project root. `build`, `ci`, and fresh `adoption`
use the same retained project and optional relative `ALIGN_REPO` input; `ordinary-adoption` requires
the separate validated absolute input and its canonical relative companion; `self-test` rejects
`ALIGN_REPO` and selects the immutable image-owned synthetic project. It opens the selected project root as descriptor `4` with
`O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`. For `ci`, fresh `adoption`, and `build`, it validates the
image envelope on descriptor `6` and the run capsule on descriptor `5`, clears `FD_CLOEXEC` only on
descriptors `4`, `5`, and `6` for the one bootstrap child, and runs `env -i` with exactly
`PATH=/usr/bin:/bin`, `LC_ALL=C`, `LANG=C`, `HOME=/nonexistent`, and `TMPDIR=/tmp`; no Make, Git,
Cargo, compiler, loader, Python, or raw `ALIGN_REPO` value is present in that child. Its child vector
is the image-owned `/usr/local/libexec/align-llm/fresh-bootstrap --mode <ci|adoption|build|self-test>` matching
the admitted logical request, with `cwd=/proc/self/fd/4` and
`close_fds=True, pass_fds=(4,5,6)`. For `ordinary-adoption`, it validates the image envelope on
descriptor `6` and the fixed schema-2 manifest snapshot on descriptor `8`, rejects all loader and
interpreter injection variables, opens `/` as temporary FD `17`, lexically validates and
component-walks the absolute Align path from that descriptor before channel creation, retains the final
descriptor as FD `18`, closes FD `17`, and retains the image-owned dispatcher at FD `14`,
creates the supervisor channel, forks exactly one dispatcher child, keeps the parent endpoint in
`fresh-supervise`, and passes the child endpoint as FD `16` plus FD `18`. Only that child invokes the
retained descriptor with `execveat(AT_EMPTY_PATH)`; the parent sends one fresh ticket and keeps the
channel open; it remains alive with its endpoint until the helper exits. The dispatcher requires its
`SO_PEERCRED` PID to be its current parent, a stable `/proc/<pid>/stat` start-time, the controlled
procfs magic-link `/proc/<pid>/exe` digest, and the exact bounded
`fresh-supervise\0--mode\0ordinary-adoption\0` command line before accepting the ticket as its first
message; EOF, an extra message, or a peer/liveness change fails closed. After the worker capsule is
signed, the dispatcher sends exactly one raw 32-byte `C = SHA-256(complete DSSE envelope bytes)` to
the parent. The parent accepts exactly that message and replies with one queued raw 32-byte
`P = SHA-256("align-llm/ordinary-adoption/worker-admission/v2\0" || dispatch_ticket_sha256_bytes ||
invocation_nonce_bytes || C)`, where the three binary operands `dispatch_ticket_sha256_bytes`,
`invocation_nonce_bytes`, and `C` are each exactly 32 bytes and the domain prefix is the literal
UTF-8 string including its trailing NUL. The dispatcher does not consume `P`; the worker peeks and
verifies it, and the namespace helper consumes and verifies it before any Make child. The dispatcher
and worker complete peer authentication before bwrap; the helper only checks channel HUP/EOF/protocol
liveness because outer PIDs and procfs entries are not visible in its private PID namespace. Its exact
named-option child vector, including `argv[0]`, is
`["request6-adoption-entrypoint", "--mode", "ordinary-adoption", "--project-root-fd", "4",
"--image-attestation-fd", "6", "--manifest-fd", "8", "--align-repo-root-fd", "18",
"--align-repo-absolute", "<normalized-absolute>", "--align-repo-relative", "<canonical-relative>",
"--invocation-nonce-fd", "15", "--supervisor-channel-fd", "16"]`, with
`cwd=/proc/self/fd/4`; after FD `14` is consumed, the child clears `FD_CLOEXEC` on FDs
`4`, `6`, `8`, `15`, `16`, and `18`, closes every other inherited data descriptor, and invokes
`execveat(AT_EMPTY_PATH)` on FD `14`. The
ordinary child has only `PATH=/usr/bin:/bin`, `LC_ALL=C`, `LANG=C`, `HOME=/nonexistent`, and
`TMPDIR=/tmp`; the validated Align path is an explicit argv value, not inherited environment. It
rejects every other command, option, assignment, and inherited `MAKEFLAGS` value before dispatch.
The ordinary descriptor offset contract applies only to byte-bearing memfds `12`, `13`, and `15` and
to local sealed memfds rehydrated from them: those owners use `pread` and restore offset zero with
`lseek` before each data handoff. O_PATH identity descriptors such as FD `18`, directory/runtime/tool
bind sources, the supervisor socket, and executable FD `27` have no byte-offset contract and are
validated by identity, protocol, bind, or exec checks without `lseek`/`pread`. The worker's bwrap
launcher invokes FD `27` with `execveat(AT_EMPTY_PATH)` and fixed `argv[0] = bwrap`.
Any closure-matrix shorthand that says the original descriptors are rewound means these
byte-bearing memfds; identity-only descriptors are revalidated by their stated identity, bind,
protocol, or exec contract instead.
The dispatcher FD shorthand in the public-surface and closure tables has the same explicit scope:
when it says the child has only FDs `4/6/8/15/16/18`, those are the inherited data and protocol
descriptors. FD `14` is additionally retained in that child as the image-owned executable authority,
is excluded from the data-descriptor list and Python `pass_fds`, and is closed only by failed cleanup
or the successful `execveat(AT_EMPTY_PATH)` edge. No table entry permits any other inherited data FD.
The supervisor maps a failed image, manifest, or ordinary nonce check to exit 1, empty stdout, and
exactly `fresh compiler: ERROR TRUST supervisor\n`; no repository worker, Make process, or private
root exists on that path. The worker runs either the fixed internal `capable-checks` Make graph or
the fixed focused-adoption Make goal only after it has accepted and materialized the project source;
the private source copy, not the retained host root, is the first repository Makefile that any fresh
process may parse. A direct host invocation of `make ci`, a focused adoption goal, or the dispatcher
pathname without this supervisor is non-evidence and fails the same pre-dispatch contract; the
accepted public requests remain the logical selectors handled by the image-owned supervisor.

For legacy modes, the bootstrap verifies descriptor `6` as a sealed memfd with the four required seals, reads and
validates the image envelope, verifies descriptor `5` as a separately sealed run capsule, and
cross-checks both signatures and their fixed image/repository tuple before creating any
repository-controlled child. The worker then re-verifies the sealed run capsule on descriptor `9`
and compares its `repository_head`, `repository_object_format`, and `align_repo_relative` with the
retained project/sibling descriptors before accepting the source manifest; the worker never treats
an observed `HEAD` as sufficient.
The `fresh-v2-image-trust-smoke` runs the same image path with a
mutable overlay, a replaced supervisor/bootstrap, a replaced manifest, a replayed image envelope,
a replayed run capsule, and missing descriptors; each case is rejected by the
supervisor/bootstrap boundary before worker execution and before private-root creation. The trusted
image identity is therefore the supervisor-verified OCI digest, not a mutable path or a pair of files
that could be replaced together. The bootstrap accepts exactly one of `--mode ci`, `--mode adoption`,
`--mode build`,
and `--mode self-test`; it performs no shell expansion, repository import, Git command, Cargo
command, network access, or repository-controlled child launch before both attestations and the
image-owned manifest snapshot are authenticated.

The bootstrap opens the fixed image manifest through retained no-follow descriptors, verifies its
image-attested digest, and copies its bounded bytes into a sealed `memfd_create` object. It retains
the supervisor-owned project-root descriptor `4`, opens the `scripts` directory relative to that
descriptor with `O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`, and opens `fresh-align-compiler` from
that descriptor with `O_RDONLY|O_NOFOLLOW|O_CLOEXEC`. Before reading a byte it requires the final
descriptor to be an euid-owned single-link regular file with exactly mode `0755`, no special bits,
and size at most `fresh_worker_max_bytes = 4194304`. It reads only from that descriptor through a
bounded loop, hashes the complete bytes against the run capsule's `controller_sha256`, and requires
the device, inode, type, link count, mode, and size to be unchanged after the read. A symlink, FIFO,
device, directory, oversized file, or replacement is a `TRUST` failure without a blocking read or
repository child. It copies the verified bytes into a second sealed object and copies the verified
run capsule into a third sealed object. All three objects use `MFD_ALLOW_SEALING` and require
`F_SEAL_WRITE|F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL`; failure to obtain any snapshot is a `TRUST`
error. The fixed fd map is: `4` retained project root, `5` sealed run capsule input, `6` sealed image
attestation input, `7` sealed worker snapshot, `8` sealed image-manifest snapshot, and `9` sealed
run-capsule snapshot. The bootstrap clears `FD_CLOEXEC` only on `4`, `7`, `8`, and `9` for the fixed
image `/usr/bin/python3 -I -B` vector
`/proc/self/fd/7 --mode <ci|adoption|build|self-test> --project-root-fd 4 --image-manifest-fd 8
--run-attestation-fd 9`, with
`close_fds=True, pass_fds=(4,7,8,9)` and a fixed worker environment of
`PATH=/usr/bin:/bin`, `LC_ALL=C`, `HOME=/nonexistent`, `TMPDIR=/tmp`, `PYTHONHOME=/usr`,
`PYTHONNOUSERSITE=1`, and `PYTHONDONTWRITEBYTECODE=1`. Descriptors `5` and `6` never reach the
worker. The bootstrap's Python interpreter, image runtime, manifest path, image attestation, and
run-capsule signer are image inputs; the worker bytes are a sealed, per-reviewed-head repository
input. An in-place overwrite of the checked-out worker after hashing therefore cannot change the
bytes executed by the worker, and a worker edit does not require a fixed image-manifest edit.

The final public contract is:

| Surface | Exact contract |
| --- | --- |
| `fresh-supervise` | Image-owned pre-bootstrap entrypoint. It accepts the public logical request `make --no-print-directory ci`, the focused fresh adoption request `make --no-print-directory json-scan-row-ownership-adoption`, the FRESH-IMAGE-REQUEST6 selector `--mode ordinary-adoption`, or image qualification request `--mode build`/`--mode self-test`. `ci`, fresh adoption, and `build` accept the optional parent-side relative `ALIGN_REPO` input bound into the run capsule; `ordinary-adoption` requires the separately validated absolute `ALIGN_REPO` and canonical relative companion; `self-test` rejects it and uses the installed synthetic project. The supervisor opens the selected project root as fd 4. Legacy modes authenticate run/image attestations on fds 5/6, scrub the child to the five-variable environment allowlist, and pass only fds 4/5/6 to the fixed matching `fresh-bootstrap --mode <mode>` child. Ordinary mode authenticates the image envelope and fixed manifest on fds 6/8, component-walks and retains the Align root at fd 18, creates the sealed fresh nonce at fd 15, creates the connected supervisor channel, forks exactly one dispatcher child, keeps the parent endpoint, and passes the child endpoint as fd 16 plus fd 18. The parent sends one ticket and remains alive until the helper exits; only the child invokes the retained image-owned Request 6 dispatcher with `execveat(AT_EMPTY_PATH)`, `argv[0] = request6-adoption-entrypoint`, and only fds 4/6/8/15/16/18 after the fixed named-option path values are validated. It never parses the repository Makefile. |
| `make ci` | The sole complete-gate request, represented inside the trusted image entrypoint by `make --no-print-directory ci`. The supervisor dispatches the fixed bootstrap directly; after source validation and private materialization, the worker runs the ordered `capable-checks` graph in the private source copy. A direct unsupervised repository Make invocation is non-evidence and fails before private-root creation. |
| focused adoption request | The exact public request `make --no-print-directory json-scan-row-ownership-adoption`. The supervisor maps it to `adoption`, and the worker runs the fixed internal `make --silent --no-print-directory -j1 -f /workspace/Makefile json-scan-row-ownership-adoption` goal in the same authenticated private source, runtime, cache, process, temporary-filesystem, and cleanup boundary as `ci`, with `ALIGNC_CACHE=off` and `/tools/fresh-alignc`. It is a focused acceptance vector, not routine aggregate membership, and it never publishes `/workspace/main`. |
| ordinary-adoption request | The exact evidence-bearing Request 6 public request is a direct runner `execve` of `/usr/local/libexec/align-llm/fresh-supervise --mode ordinary-adoption` with the five fixed environment entries plus the required absolute `ALIGN_REPO`. The supervisor validates the image envelope and schema-2 manifest, component-walks and retains the canonical sibling path as FD 18, creates the one-time supervisor channel, forks exactly one dispatcher child, keeps the parent endpoint, passes the child endpoint as FD 16 plus FD 18, sends one ticket, and remains alive until the helper exits. Only the child invokes the retained FD-14 dispatcher with `argv[0] = request6-adoption-entrypoint`, `--mode ordinary-adoption --project-root-fd 4 --image-attestation-fd 6 --manifest-fd 8 --align-repo-root-fd 18 --align-repo-absolute <normalized-absolute> --align-repo-relative <canonical-relative> --invocation-nonce-fd 15 --supervisor-channel-fd 16`. The dispatcher authenticates its current-parent channel peer, stable PID start-time, controlled procfs executable, exact supervisor command line, ticket, project/Align/raw-tree/exception snapshot, fresh nonce, and sealed worker before any repository Make process; direct `env`, dispatcher, worker, or repository-script paths are non-evidence. Before FD-14 dispatch, failure is exit 1 with empty stdout and exactly `fresh compiler: ERROR TRUST supervisor\n` on stderr. After dispatch, success is exit 0 with empty stderr and exactly `json-scan adoption: PASS\n` on stdout; failure is exit 1 with empty stdout and exactly `json-scan adoption: ERROR <phase>\n` on stderr, where the closed phase set is `input`, `toolchain`, `revision`, `build`, `fixture`, or `cleanup`, the special worker-death outcome is `json-scan adoption: ERROR unobserved\n`, the first failed phase wins, and cleanup never replaces the primary phase. |
| legacy run capsule | For legacy `ci`, fresh `adoption`, `build`, and `self-test` only, a supervisor-signed `runner-invocation/v1` DSSE envelope on descriptor 5 binds the current repository head/object format, canonical `ALIGN_REPO` relative path, `scripts/fresh-align-compiler` relative path and SHA-256, image-attestation digest, and image-manifest digest to this invocation. Ordinary Request 6 uses only `ordinary-adoption/v2` plus the supervisor-created fresh nonce, one-time channel ticket, and signed source-exception digest; its original authority FDs are consumed by bwrap as fixed read-only bind sources. |
| image deployment inputs | The image contains only the two root-owned public keys. The read-only `/run/align-llm-fresh` deployment mount contains root-owned `image-attestation.dsse` mode `0444`, `image-digest` mode `0444`, and `provenance-digest` mode `0444`, plus invoking-uid-owned `run-signing-seed` mode `0400`; all are single-link regular files. `scripts/fresh-image-attest` is the offline image-attestation producer; the seed files remain outside Git and OCI layers. |
| `fresh-profile setup <uid>` | Root-only image helper. It provisions the mode-`0700`, uid-owned `/run/user/<uid>/align-llm-fresh/{roots,lock}` profile (`lock` is a mode-`0600` single-link regular file) and delegated `/sys/fs/cgroup/align-llm-fresh/<uid>` parent with `pids` enabled. `cleanup <uid>` removes only an empty profile whose exact ownership and modes still match. |
| `fresh-bootstrap --mode build` | Image-supervisor-only diagnostic invocation with both sealed image/run attestation descriptors and fixed repository inputs as `ci`; it builds and authenticates the private compiler bundle, performs cleanup, and never launches `capable-checks` or claims consumer adoption. Its success bytes are exactly `fresh compiler: PASS\n`. |
| `fresh-bootstrap --mode adoption` | Image-supervisor-only focused adoption invocation with both sealed image/run attestation descriptors and fixed repository inputs. It authenticates and materializes the private compiler/runtime boundary, launches only the fixed focused adoption goal, performs cleanup, and never launches a routine aggregate or claims complete-gate evidence. Its success bytes are exactly `fresh compiler adoption: PASS\n`. |
| `fresh-bootstrap --mode self-test` | Image-supervisor-only synthetic contract invocation with both sealed attestation descriptors. It uses only checked-in fixtures and image-attested tools, creates no project or Align build output, and proves the manifest, namespace, launcher, process, admission-lock, resource-limit, and cleanup unit matrix. Its success bytes are exactly `fresh compiler self-test: PASS\n`. |
| `ALIGN_REPO` | For legacy `ci`, fresh `adoption`, and `build`, this is the optional non-empty project-root-relative input with default `../align`; the supervisor lexically normalizes it without following a symlink and records the canonical relative bytes as `align_repo_relative` in the signed run capsule. For `ordinary-adoption`, it is required as an absolute path with no empty, `.`, or `..` component or symlink; the supervisor walks every component before channel/FD-14 dispatch, retains the final root as FD 18, and the dispatcher independently verifies the descriptor identity and canonical relative spelling. No later operation reopens the pathname. A malformed or unadmittable ordinary public path before FD-14 dispatch is `fresh compiler: ERROR TRUST supervisor\n`; an FD 18/path or source identity mismatch after FD-14 dispatch is exactly `json-scan adoption: ERROR revision`; only malformed public input before dispatch is the supervisor `TRUST` result. Legacy modes retain their separate `ARGUMENT`/`SOURCE` category grammar. Its exact pinned commit and clean raw source tree are mandatory build inputs. |
| `ALIGN_LLM_TOOLCHAIN_MANIFEST` | Rejected before bootstrap dispatch. The fixed trusted runner image selects `/usr/local/share/align-llm/fresh-toolchain.json`; callers cannot select a manifest path. |
| `ALIGN_LLM_TOOLCHAIN_MANIFEST_SHA256` | Rejected before bootstrap dispatch. The image attestation supplies the exact manifest digest; callers cannot authenticate a different manifest by supplying a different digest. |
| `ALIGNC` on `ci` or focused adoption | Rejected before bootstrap dispatch. The worker supplies the fresh launcher `/tools/fresh-alignc`, its read-only `/tools/fresh-descriptor` and `/tools/fresh-guard`, the compiler `/tools/alignc`, and sibling `/tools/libalign_runtime.a`; caller compiler paths cannot cross the boundary. The focused adoption vector also fixes `ALIGNC_CACHE=off`; caller cache paths cannot cross the boundary. |
| caller Make options | The supervisor accepts exactly `make --no-print-directory ci` or `make --no-print-directory json-scan-row-ownership-adoption`, with no assignments and an empty `MAKEFLAGS`/`GNUMAKEFLAGS`/`MAKEOVERRIDES`. Its normalized GNU Make 4.3 rejection matrix covers `-b/-m`, `-B/--always-make`, `-C/--directory=`, `-d/--debug[=]`, `-e/--environment-overrides`, `-E/--eval=`, `-f/--file=/--makefile=`, `-h/--help`, `-i/--ignore-errors`, `-I/--include-dir=`, `-j/--jobs[=]`, `-k/--keep-going`, `-l/--load-average[=]/--max-load[=]`, `-L/--check-symlink-times`, `-n/--just-print/--dry-run/--recon`, `-o/--old-file=/--assume-old=`, `-O[TYPE]/--output-sync[=]`, `-p/--print-data-base`, `-q/--question`, `-r/--no-builtin-rules`, `-R/--no-builtin-variables`, `-s/--silent/--quiet`, `--no-silent`, `-S/--no-keep-going/--stop`, `-t/--touch`, `-v/--version`, `-w/--print-directory`, `-W/--what-if=/--new-file=/--assume-new=`, `--warn-undefined-variables`, and `--trace`, including separated and attached arguments and every long `--name=value` form. The newer/unsupported `--jobserver-style=` and `--shuffle[=]` spellings are explicit rejection rows even on a newer host. It rejects every unknown option, assignment, alternate goal, and alternate makefile. The accepted `--no-print-directory` spelling is tested separately for both admitted goals and is the only option retained in the logical request vectors. The private worker Make invocation is a different fixed vector and is not part of caller option admission. |
| `ALIGN_LLM_WORK_PARENT`, cgroup parent, cache, and timeout overrides | N/A. The private-root parent is the fixed protected per-user `roots` directory, the delegated cgroup parent is the fixed image/profile path `/sys/fs/cgroup/align-llm-fresh/<uid>`, the cache is named by the authenticated manifest, and all deadlines are worker constants. No caller can redirect cleanup, cgroup ownership, cache identity, or a safety deadline. |
| success bytes | Legacy `ci`: exit 0, empty stderr, and exactly `fresh compiler and capable checks: PASS\n`; legacy `adoption`: exactly `fresh compiler adoption: PASS\n`; `build`: exactly `fresh compiler: PASS\n`; `self-test`: exactly `fresh compiler self-test: PASS\n`. Ordinary Request 6 after FD-14 dispatch: exit 0, empty stderr, and exactly `json-scan adoption: PASS\n`. |
| failure bytes | Legacy modes: exit 1, empty stdout, one primary `fresh compiler: ERROR <CATEGORY> <PHASE>\n` (or the cleanup line alone when the phase itself succeeded), and optionally one `fresh compiler: ERROR CLEANUP cleanup\n`; no child bytes are forwarded. Ordinary Request 6 before FD-14 dispatch: empty stdout and exactly `fresh compiler: ERROR TRUST supervisor\n` on stderr. Ordinary Request 6 after dispatch: empty stdout and exactly one `json-scan adoption: ERROR <phase>\n` on stderr from the closed phase set, with first-failure precedence and no child-stream forwarding. |

Within the caller-option matrix, `--no-print-directory` has the sole accepted option row and only
with either admitted goal; every other option row is rejected. The newer/unsupported
`--jobserver-style=` and `--shuffle[=]` rows remain explicit rejections even on a newer host.

The worker is the sole owner of the private root, the admission lock, every build and aggregate
process, compiler and descriptor file descriptor, cache copy, and cleanup decision. Either admitted
public request plus any aggregate or focused goal is rejected before side effects. Independent concurrent invocations are
rejected before root creation: the worker opens the protected lock parent
`/run/user/<uid>/align-llm-fresh` component-by-component with no-follow operations, verifies
`/run` and `/run/user` as the fixed root-owned mode-`0755` ancestors, and verifies
`/run/user/<uid>` and the lock-parent component for the expected device/inode, effective-uid
ownership, and mode `0700`; it opens `lock` with `O_NOFOLLOW|O_CLOEXEC` mode `0600`,
fstats it as a single-link regular file owned by the effective uid with mode `0600`, and takes
`flock(LOCK_EX|LOCK_NB)` on its local descriptor `10`. The lock parent is outside `/tmp`
and is a fixed image/profile prerequisite; a missing, replaced, world-writable, or wrong-owner parent
is a `PLATFORM` failure. A held lock returns `fresh compiler: ERROR PLATFORM concurrency\n`. The lock
parent contains a profile-created `roots` directory that is opened descriptor-relatively, requires
mode `0700`, effective-uid ownership, and a stable device/inode, and is the only private-root parent.
With the lock held, the worker scans this protected per-user directory only for bounded raw name
existence, considering any name with the private-root prefix `align-llm-fresh-` a candidate and never
inspecting candidate contents: at most 65,536 directory entries and one second, with cap-plus-one,
read, or deadline failure returning `fresh compiler: ERROR FILESYSTEM filesystem\n`; it never reads,
classifies, or removes a candidate. A mode-`01777` shared `/tmp` name can never block or masquerade
as an orphan for another user. The concurrency smoke enumerates two simultaneous `ci`, `adoption`,
`build`, and `self-test` admissions, proves the first owns at most one root, and proves the second has no root or
cleanup authority. Concurrent independent processes are therefore explicitly rejected rather than
unsupported evidence.

There are two source roots and they are never interchangeable. The controller project root is the
checked-out `align-llm` worktree from which the bootstrap was launched; its private copy is the
aggregate input and is later exposed as `/workspace`. `ALIGN_REPO` is the separate sibling Align
worktree; its private copy is the only input to the Cargo compiler build and is later exposed as
`/align-src`. The worker retains descriptors for both roots and their Git state before any child,
source copy, or private output root is created. The project root's exact raw source manifest and the
Align root's exact raw source manifest are separate values in the compiler descriptor. No Cargo
command receives the project root, and no aggregate command receives the Align source tree.

The `ci` and focused-adoption control planes are fixed before any repository Makefile can run. The
image supervisor accepts only an admitted logical request vector and clears all loader, Python, Make,
Git, Cargo, and compiler override variables; it dispatches the fixed bootstrap rather than a
repository Make process. After source materialization, the worker uses the private copy's `Makefile`
with the fixed internal capable graph or focused-adoption goal and an explicit `-f /workspace/Makefile`,
so tracked `GNUmakefile` or lowercase `makefile` files cannot change the entrypoint.
The implementation uses `override SHELL := /bin/sh`, `override .SHELLFLAGS := -eu -c`, and a
parse-time guard for the internal aggregate invocation that rejects every inherited Make option or
assignment other than Make's own `--no-print-directory` bookkeeping. The complete GNU Make 4.3 option matrix is tested by the
supervisor unit (`-B/-b`, `-C`, `-d/--debug`, `-e`, `-E/--eval`, `-f/--file`, `-h`, `-i`,
`-I/--include-dir`, `-j/--jobs`, `-k/--keep-going`, `-l/--load-average`, `-L`, `-n/--just-print`,
`-o/--old-file`, `-O/--output-sync`, `-p/--print-data-base`, `-q/--question`, `-r`, `-R`, `-s`,
`-S`, `-t/--touch`, `-v`, `-w/--print-directory`, `-W/--what-if`, `--warn-undefined-variables`,
`--trace`, and every minimum-version long alias); unknown options are also rejected. A dry-run or
question invocation that suppresses recipes is rejected before the bootstrap even if Make would
return zero. The worker's child Make vector clears `MAKEFLAGS`, `GNUMAKEFLAGS`, and `MAKEOVERRIDES`,
supplies `SHELL=/bin/sh`, fixes `-f /workspace/Makefile`, and contains only the ordered
`capable-checks` goal for `ci` or only `json-scan-row-ownership-adoption` for `adoption`. A marker
shell, descriptor assignment, alternate makefile, or extra goal must fail before the bootstrap or
any private root is created.

The matrix includes the GNU Make 4.3 compatibility option `-m` alongside `-b`, every displayed
short-option alias and long alias (`--makefile`, `--assume-old`, `--assume-new`, `--max-load`,
`--dry-run`, and `--recon`), `--no-silent`, and `--stop`. It has explicit unsupported/newer rows for
`--jobserver-style` and `--shuffle`; neither may cross the exact supervisor boundary even when the
host Make accepts it. It tests each option with its separated argument, attached argument, and
`--name=value` spelling where the minimum version accepts one. The supervisor regression stores the
normalized option table and requires one rejection case per row, plus an unknown option, assignment,
alternate goal, and alternate makefile.

### 9.2 Authenticated manifest and canonical wire grammar

The two external attestations use the same canonical DSSE envelope grammar, but they are separate
signing domains. The complete envelope is UTF-8 JSON with exactly this field order and no unknown
fields:

```text
payloadType
payload
signatures
```

`payloadType` is the exact predicate URI, `payload` is unpadded base64url of the canonical predicate
bytes, and `signatures` contains exactly one object with field order `keyid`, `sig`; both signature
values are non-empty ASCII strings and `sig` is unpadded base64url of a 64-byte Ed25519 signature.
The signature covers the UTF-8 DSSE pre-authentication encoding
`DSSEv1 <decimal-byte-length(payloadType)> <payloadType> <decimal-byte-length(predicate)> <predicate>`
with one ASCII space between fields and no final newline. The pinned image verifier key is a raw
32-byte Ed25519 public key identified by `align-llm-runner-image-v1`; its SHA-256 is a lowercase
64-hex deployment value recorded in the image predicate. The invocation verifier uses the distinct
key identifier `align-llm-runner-run-v1` and the same raw-key/64-hex rule. Key IDs are compared
exactly before signature verification; key rotation requires a new image-attestation policy and a
new verifier identity. The envelope, predicate, payload, signature, key ID, and verifier binary
are all size-bounded before decoding, and the verifier rejects duplicate JSON names, unknown fields,
non-canonical escapes, padded base64url, invalid UTF-8, or a signature over any bytes other than
the exact predicate preimage.

The image predicate has schema version `1` and this exact field order:

```text
schema_version
image_digest
image_name
provenance_digest
verifier_identity
verifier_version
verifier_key_id
verifier_key_sha256
supervisor_path
supervisor_sha256
bootstrap_path
bootstrap_sha256
manifest_path
manifest_sha256
```

`schema_version` is the unsigned integer `1`; image, provenance, key, supervisor, bootstrap, and
manifest digests are SHA-256 strings in the form `sha256:<64 lowercase hex>` except the four
`*_sha256` fields, which are exactly 64 lowercase hex; there are four such fields
(`verifier_key_sha256`, `supervisor_sha256`, `bootstrap_sha256`, and `manifest_sha256`).
`image_name` is a non-authoritative OCI registry/name label; it cannot select or authenticate an
image, and the immutable identity is `image_digest`. The version is ASCII `major.minor.patch`; and
the three paths are absolute canonical no-symlink paths. The invocation predicate has schema version
`1` and this exact field order:

```text
schema_version
image_attestation_sha256
manifest_sha256
repository_object_format
repository_head
align_repo_relative
controller_path
controller_sha256
supervisor_identity
supervisor_version
supervisor_key_id
supervisor_key_sha256
```

Its `repository_object_format` is `sha1` or `sha256`; `repository_head` is respectively 40 or 64
lowercase hex; `align_repo_relative` is the supervisor-normalized, non-empty relative UTF-8 path
with no NUL, empty component, or absolute leading slash; `controller_path` is the exact relative byte
path `scripts/fresh-align-compiler`; and all other digest/version/identity fields use the image
rules. The supervisor signs the normalized path, and the worker resolves it only from retained
project-root descriptors, so an environment mutation cannot select a different sibling worktree.
The bootstrap requires the invocation predicate's `image_attestation_sha256` to equal the complete
descriptor-6 envelope digest and its `manifest_sha256` to equal the image predicate's manifest
digest. The supervisor computes `controller_sha256` from the retained descriptor-relative checkout
and the bootstrap independently recomputes it before sealing the worker.

The `fresh-v2-attestation-wire-golden` fixture contains deterministic zero-filled digest fields and
the synthetic repository head `1111111111111111111111111111111111111111`. Its canonical image
predicate SHA-256 is
`211475753df48fa9f8e6ae47b37c516be156ebebf6220433a0585cca723bd6d6`, its image DSSE pre-authentication
encoding SHA-256 is `c130bba24eafa371426e68a8267928d903ea7807764ad3c9d9fe7910b58bb1bd`, its invocation
predicate SHA-256 is `d09c3bd18106fad2dbe0beddf5aae360edf88f94bc98eafde5bdb5d04ab1a73d`, and its
invocation pre-authentication encoding SHA-256 is
`67d8b36f4d899a991eb5aa6620ff273aaf9b97d24d751537123f9748ae315037`. These hashes include the one
final LF required by the canonical predicate bytes. The fixture independently
checks the base64url payload bytes, DSSE pre-authentication lengths, key-id selection, and signature
verification with the checked-in synthetic public key; deployment keys never enter the repository.

The two predicate byte fixtures are shown here so the hashes are independently reproducible rather
than labels for an implementation-generated value:

```json
{
  "schema_version": 1,
  "image_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000001",
  "image_name": "oci://registry.example/align-llm-runner",
  "provenance_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000002",
  "verifier_identity": "align-llm-runner-image-v1",
  "verifier_version": "1.0.0",
  "verifier_key_id": "align-llm-runner-image-v1",
  "verifier_key_sha256": "0000000000000000000000000000000000000000000000000000000000000003",
  "supervisor_path": "/usr/local/libexec/align-llm/fresh-supervise",
  "supervisor_sha256": "0000000000000000000000000000000000000000000000000000000000000004",
  "bootstrap_path": "/usr/local/libexec/align-llm/fresh-bootstrap",
  "bootstrap_sha256": "0000000000000000000000000000000000000000000000000000000000000005",
  "manifest_path": "/usr/local/share/align-llm/fresh-toolchain.json",
  "manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000006"
}
```

```json
{
  "schema_version": 1,
  "image_attestation_sha256": "0000000000000000000000000000000000000000000000000000000000000007",
  "manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000006",
  "repository_object_format": "sha1",
  "repository_head": "1111111111111111111111111111111111111111",
  "align_repo_relative": "../align",
  "controller_path": "scripts/fresh-align-compiler",
  "controller_sha256": "0000000000000000000000000000000000000000000000000000000000000008",
  "supervisor_identity": "align-llm-runner-image-v1",
  "supervisor_version": "1.0.0",
  "supervisor_key_id": "align-llm-run-v1",
  "supervisor_key_sha256": "0000000000000000000000000000000000000000000000000000000000000009"
}
```

The JSON blocks above are canonical predicate bytes with two-space indentation and one final LF;
they are not complete DSSE envelopes, and their zero-filled cross-digests are intentionally a
predicate-only vector. The golden test separately wraps each byte string in the exact three-field
envelope and checks the PAE and Ed25519 signature; its integration case replaces the synthetic
cross-digests with the actual image-envelope and manifest digests before checking the binding.
The predicate-only key-binding fixture uses the RFC 8032 Ed25519 public-key bytes
`d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a` and SHA-256
`21fe31dfa154a261626bf854046fd2271b7bed4b6abe45aa58877ef47f9721b9`; the zero-filled digest in
the displayed vector is intentionally not a deployment key. The signed-envelope fixture uses the
corresponding deterministic test signature, while deployment private keys never enter the
repository.

The external toolchain manifest is schema version 2. Its top-level object has exactly this field
order, with no duplicate or unknown fields:

```text
schema_version
controller
bootstrap
platform
tools
runtime_bindings
cargo_cache
```

Every object and array is serialized in the stated order using UTF-8, two-space indentation, and
exactly one final LF. Strings use this complete escape table: `"` is `\"`, `\` is `\\`, U+0008,
U+0009, U+000A, U+000C, and U+000D use `\b`, `\t`, `\n`, `\f`, and `\r`, respectively, and every
other U+0001 through U+001F code point uses `\u00` followed by two uppercase hexadecimal digits.
All other Unicode scalar values are emitted as literal UTF-8; `/` is never escaped, and unpaired
surrogates are rejected. Standalone nested values use the same canonical serializer and final LF
when their digest is computed. Ordinary strings contain no NUL and are at most 4,096 bytes. The
`tool.stdout` and `tool.stderr` fields are the only size exception: they are lowercase hexadecimal
encodings of the exact raw probe bytes, accept at most 65,536 decoded bytes (at most 131,072 ASCII
hex characters), and reject any byte beyond that cap; they are not UTF-8 text and are never silently
truncated or replacement-decoded. Absolute paths have one leading `/`, no empty, `.`, or `..` component, and
no symlink component in their canonical host form. Relative paths use one or more raw-byte
lexicographic components, with the same component restrictions. Unsigned integers are decimal JSON
integers without a leading zero and at most 64 bits. File modes are strings of exactly four octal
ASCII digits, such as `"0755"` and `"0600"`; no JSON number is used for a mode. `argv`
has at most 32 elements and 4,096 encoded bytes. The complete manifest is at most 64 MiB, has at
most 128 tool records, 256 runtime bindings, digest-tree depth 64, and 200,000 non-root entries.
Cache admission additionally uses the fixed limits `cache_regular_file_max_bytes = 536870912`
(512 MiB) and `cache_total_max_bytes = 21474836480` (20 GiB). These are worker constants, not
manifest-controlled values; every regular-file size and the checked 64-bit sum are validated before
private-root creation or any cache copy.

The bootstrap passes the image-attested manifest snapshot on descriptor 8. The worker reads that
descriptor exactly once, rejects any caller-supplied manifest path or digest environment, and uses
the in-memory bytes for parsing, nested descriptor construction, and every later identity check; no
worker operation reopens a mutable manifest pathname. The manifest descriptor's device/inode/size
identity remains retained until the worker exits, and a changed image file is an image/`TRUST`
failure on the next bootstrap invocation rather than a selectable runtime input. The external cache
manifest is handled the same way during phase 6. Neither manifest is accepted from a symlink,
alternate object, or path below a private output root.

The nested field order is:

```text
controller: path, api
bootstrap: path, sha256, api
platform: os, architecture, kernel_minimum, python_minimum, make_minimum
tool: name, path, namespace_path, mode, sha256, argv, stdout, stderr
runtime_binding: source, target, kind, manifest, manifest_sha256
cache: root, manifest, manifest_sha256, entry_count
cache_manifest: schema_version, allowed_prefixes, root, entry_count, total_size
digest_root: kind, mode, staged_mode, size, sha256, entries
digest_entry: name, kind, mode, staged_mode, size, sha256, entries
```

`controller.path` is `scripts/fresh-align-compiler`, `controller.api` is `1`, `bootstrap.path` is
the fixed absolute path, and `platform` contains `linux`, `x86_64`, `6.8`, `3.12`, and `4.3`. The
image manifest generator records the controller path and API only; the per-invocation run capsule
records and authenticates the current controller digest. Tool `path` must be a canonical no-symlink
regular executable path and `tool.mode` is exactly the source file's `0755` mode. The image manifest
generator resolves and authenticates any installation symlink before writing the fixed manifest; a
symlink path is never accepted as an image tool input. The worker opens every component with
no-follow operations from retained image and parent descriptors, requires the declared mode and
regular-file type, hashes all bytes, and retains the descriptor through the identity probe. The
probe executes `/proc/self/fd/<retained-tool-fd>` with an explicit inherited-fd list and compares its
bounded output to the manifest; it never executes the mutable host pathname.
The worker later copies the same retained bytes into private `tool-bin` with create-exclusive
operations at derived mode `0555`, hashes the copy again, and exposes it read-only; no host tool path
is used after staging. `namespace_path` is `/tools/<name>`
and is the only executable path visible through the aggregate PATH. Runtime regular files use a
separate derived read-only mode: a source mode with any execute bit stages as `0555`, and a source
mode without an execute bit stages as `0444`; runtime directories stage as `0700`. The worker never
relies on a recursive namespace `chmod` to make an interpreter, loader, or executable library
runnable. Those raw and staged modes are both present in every runtime digest-tree node and the
structural digest preimage. Cargo-cache regular files must be owner-readable, have no execute/set-ID/
sticky bits, and use the separate mapping to staged `0600`; cache directories must provide owner
read/write/execute with no set-ID or sticky bit and stage as `0700`. The accepted cache manifest
records both values and the post-copy proof compares the staged value.

The `tool.stdout` and `tool.stderr` values in the manifest are lowercase hexadecimal byte strings.
An empty stream is `""`; each pair of ASCII hex digits represents one captured byte, and an odd
length, uppercase digit, non-hex byte, or decoded length above 65,536 is a `TOOL` rejection. The
probe reader rejects the 65,537th byte rather than truncating it. This exception is the only reason
these two manifest fields may exceed the ordinary 4,096-byte string limit; all other manifest
strings retain that limit. The manifest self-test includes empty, binary, exact-cap, and cap-plus-one
probe streams and compares the canonical hex bytes independently of JSON parser behavior.

The closed executable inventory is:

```text
git cargo rustc llvm-config llvm-config-22 cc cxx ar ranlib linker bwrap sh make python3 env bash
prlimit clang clang++ strip objdump objcopy llvm-profdata llvm-profdata-22 llvm-bcanalyzer
llvm-bcanalyzer-22 llvm-readobj llvm-nm ld ld.lld id mount-guard basename cat chmod cmp cp diff
dirname find grep head mkdir mktemp mv readlink realpath rm rmdir sed seq sleep stat tail tee touch tr wc
```

The implementation's source scan and trace must produce this inventory or a reviewed strict
expansion before acceptance. The scan includes shell-script command positions and Python
`subprocess` argv, while shell builtins (`cd`, `command`, `exec`, `printf`, `test`, and `wait`) are
not executable records. An actual argv spelling with a version suffix is a separate record. There
is no PATH discovery, `command -v`, `which`, rustup, Git hook, Cargo helper, shell probe, or unlisted
executable fallback. The only executable path outside the tool inventory is the exact
`/usr/bin/adoption-namespace` runtime binding defined above. Any other unlisted executable path is a
`TOOL` rejection.
Git must report at least 2.45, Cargo and rustc must match Rust 1.96.0, and LLVM must report major
22; the manifest owns all remaining versions and digests. `mount-guard` is
an image-owned, manifest-authenticated fixed executable whose accepted operations are applying
`mount_setattr(MOUNT_ATTR_NOSYMFOLLOW)` to the explicitly supplied mountpoints, verifying their
mount IDs before and after the operation, and, only when the aggregate invokes the optional
`--prepare-validation-userns` flag, preparing the single documented descendant user namespace.
After those operations it reduces its effective and permitted capability sets to `CAP_SETFCAP`
only, sets `no_new_privs`, and `execve`-s the post-`--` command. Its exact argv is
`mount-guard --no-symlink-follow <one-or-more-absolute-mountpoints> [--tmpfs-inodes <absolute-tmpfs-mount>] [--prepare-validation-userns] -- <absolute-command> <args>`;
it rejects relative, duplicate, or unlisted mountpoints, rejects the preparation flag more than
once, and has no shell, network, repository, or arbitrary mount operation.

The `bwrap` record is authenticated before any capability probe can execute it. Immediately after
manifest validation, the worker opens the declared bwrap path through retained no-follow parent
descriptors, requires the declared regular executable mode, hashes all bytes, checks its ELF
interpreter and declared loader closure, and retains that descriptor. A bwrap digest, type, mode, or
loader mismatch is a `TRUST` failure. Every namespace, overlay, no-symlink-mount, and read-only-tools
probe executes `/proc/self/fd/<retained-bwrap-fd>` with an empty worker-handoff descriptor set; it
never resolves the mutable manifest pathname. The retained descriptor remains open through all
probes and is the same input later copied into private `tool-bin/bwrap`. The no-symlink probe covers
only the namespace-owned `/target/tmp` mount; accepted contained source symlinks are covered by the
source identity fixture instead.

#### 9.2.1 Recursive digest-tree value

Every `runtime_binding.manifest` and the cache manifest's `root` is one `digest_root` value. A root
has `kind`, raw source `mode`, deterministic `staged_mode`, `size`, `sha256`, and `entries`; each
entry has `name`, `kind`, raw source `mode`, deterministic `staged_mode`, `size`, `sha256`, and
`entries`. `kind` is `file` or `dir`. A file has `entries: []`, its `size` is its byte length, and its
digest is SHA-256 of its complete bytes. A directory has `size: 0`, and its digest is the SHA-256 of
the following byte sequence, with entries in raw-byte lexicographic `name` order:

```text
ASCII("align-llm-digest-tree-v2") || NUL || four ASCII raw-mode bytes ||
four ASCII staged-mode bytes ||
uint64 big-endian directory size ||
for each child:
  one byte (0x01 file, 0x02 directory) ||
  uint32 big-endian byte length of name || name bytes ||
  four ASCII raw-mode bytes || four ASCII staged-mode bytes ||
  uint64 big-endian size || 32 raw digest bytes
```

The root uses an empty name in this structural encoding. Names are single relative components, so
an entry cannot hide a slash, dot component, duplicate, prefix collision, or parent traversal. The
tree value is canonicalized independently and `manifest_sha256` is SHA-256 of those exact canonical
JSON bytes including the final LF. The worker recomputes both the content/structural digest and the
serialized manifest digest before any copy or mount.

The independent digest golden vector is `fresh-compiler-digest-tree-v2-golden`:

```json
{
  "kind": "dir",
  "mode": "0755",
  "staged_mode": "0700",
  "size": 0,
  "sha256": "595f8a4c893a5e141d751b0c1e00d709790a5c7632edacf7fe26442a91c509be",
  "entries": [
    {
      "name": "a",
      "kind": "file",
      "mode": "0644",
      "staged_mode": "0444",
      "size": 3,
      "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      "entries": []
    }
  ]
}
```

The fixture's file is exactly the three bytes `abc`; its canonical standalone JSON bytes have
`manifest_sha256` `ecdbd9d189a098fd0e50450448102da644a672fe43264761c3982324025c66f5`. The format
self-test compares both the byte vector and the independently recomputed values. The complete
manifest fixture `fresh-compiler-manifest-v2-complete` contains one record for every closed tool,
one file runtime binding, one directory runtime binding using the golden tree, a cache manifest
outside its cache root, and deterministic synthetic executable bytes. It is not a host-path or
mutable-digest placeholder.

#### 9.2.2 Runtime and cache records

Each `runtime_binding` has `source`, `target`, `kind`, `manifest`, and `manifest_sha256`. Its private
staging basename is the zero-based array ordinal rendered as `runtime-` followed by six decimal
digits; this derived identity is part of schema version 2 and is not a mutable pathname input. `kind` is
`file` or `tree`. `source` is a canonical no-symlink host path; `target` is an absolute namespace
path. Targets are pairwise disjoint and no target may overlap `/align-src`, `/workspace`, `/tools`,
`/cargo`, or `/target`. For a file binding, the digest root is a file and the target is a file; for
a tree binding, the digest root is a directory and the target is a directory. The worker copies the
complete source object into private `runtime/runtime-<ordinal>` and uses only that copy for both
build and aggregate namespaces. The compiler descriptor's `runtime_path.path` names this actual
private staging path, such as `runtime/runtime-000000`; it never names the logical namespace target.
It opens each manifest-listed file with no-follow and nonblocking flags, rejects a nonregular object
after the open, retains each source descriptor through the copy, hashes from the retained descriptor,
and rechecks type/mode/size and digest after the destination write and before the descriptor is
released. Directory entry names and metadata receive the same descriptor-relative post-copy check;
the destination tree is independently rehashed and checked for type/mode/size. Any replacement,
special-file race, or mutation rejects. Parent directories are created explicitly before each bind;
no host root or unlisted directory is mounted.

Runtime bindings include the ELF interpreter and complete `DT_NEEDED` closure for every staged
executable and every generated product, Rust's sysroot and dynamic libraries, LLVM resources and
libraries, and the fixed absolute interpreter targets `/usr/bin/env`, `/usr/bin/python3`, `/bin/sh`,
and `/bin/bash`. The source for a target such as `/bin/sh` is the resolved regular file (for example
`/usr/bin/dash`), never a symlink. Before either namespace starts, the worker derives three ordered,
deduplicated namespace path lists from the authenticated binding trees: directories containing ELF
shared objects or static archives for `LIBRARY_PATH`, directories containing loadable ELF shared
objects for `LD_LIBRARY_PATH`, and directories containing `.pc` files for `PKG_CONFIG_PATH`. The
lists use manifest order and raw-entry order, are bounded by the manifest limits, and are the only
linker, loader, and pkg-config search paths supplied to build and aggregate children. Exact path
duplicates are omitted, and directory paths whose authenticated recursive manifest digest is an
identical structural alias of an earlier path are also omitted, preserving the first occurrence;
this supports image layouts that expose the same system library tree at both `/lib` and `/usr/lib`
without treating identical bytes as two loader candidates. An absolute ELF name still resolves
only its exact target path. When a relative ELF name has multiple candidate target paths, the worker
compares the complete staged file bytes and collapses byte-identical candidates in candidate order;
byte-distinct candidates remain ambiguous and reject. This covers both identical library-tree aliases
and an image's copied system loader plus an explicit single-file loader target. The worker's
byte-level ELF parser verifies that every staged executable and the final `/workspace/main` output's
interpreter and recursive `DT_NEEDED` closure resolves to one unambiguous authenticated binding
through one of those derived paths; an unlisted, byte-distinct ambiguous, RPATH/RUNPATH-escaping, or
host-resolved library rejects.
The same runtime bindings and derived path lists are supplied to the build and aggregate namespaces;
no ambient loader cache or host library lookup is a hidden input. Each list is serialized as a
colon-separated string in its derived order; an empty list is the empty string, never an inherited
value. The worker records the derived lists in diagnostics only by their fixed field names, not by
exposing host paths in public error bytes.

The C and C++ build tools use a self-contained compiler-suite closure rather than copied host GCC
drivers. The manifest's `cc` and `cxx` records are fixed image-owned no-shell driver executables;
they are not `/usr/bin/cc` or `/usr/bin/c++` compatibility links and may not discover GCC helpers
through `/usr/libexec`, `COMPILER_PATH`, or `PATH`. The drivers execute only the staged absolute
paths `/runtime/cc-suite/bin/clang` and `/runtime/cc-suite/bin/clang++`, with the fixed resource
directory `/runtime/cc-suite/lib/clang/22`, `-B/runtime/cc-suite/bin`, and
`-fuse-ld=/runtime/cc-suite/bin/ld.lld`. The authenticated `runtime_binding` at
`target=/runtime/cc-suite` contains the complete regular-file closure needed by those drivers:
`clang`, `clang++`, `ld.lld`, assembler and archive helpers, compiler-rt and startup objects,
LLVM resources and libraries, C and C++ headers, and every helper named by the fixed driver trace.
The image also carries a separate authenticated runtime-support tree at
`target=/usr/lib/gcc/x86_64-linux-gnu`. It contains only the image's GCC-compatible startup and
`libgcc_s` support files required by the fixed Clang driver for Rust's Linux target; it does not
include a GCC driver, `libexec` helpers, or a host-discovered executable path. The tree is mounted
read-only and is part of the same derived library closure.
The image installs `libzstd-dev` so the authenticated system-library tree contains the declared
`libzstd.so` linker input required by the pinned Align runtime build; the package's compiler or
header paths are not exposed through `PATH` or an undeclared search variable.
The `ar`, `ranlib`, and linker tool records point into this same closure and use no ambient helper
or library search path. The worker rejects a missing trace member, a host path in a driver result,
or a compiler invocation that would consult an undeclared helper before either namespace starts.
The compiler-suite tree is mounted read-only in both namespaces, and the closure regression removes
each helper/resource/header class and installs marker helpers to prove that no host fallback can run.

The Python record is not satisfied by the interpreter file alone. The manifest includes the complete
CPython standard-library and extension search roots used by the exact image, including the
`/usr/lib/python3.12` tree and its `lib-dynload` contents, plus an authenticated
`/usr/lib/python312.zip` file when that image supplies one. Any nonempty system site root that the accepted script graph
imports from is a separate authenticated tree binding; an import outside the listed roots is a
`TOOL` failure. The aggregate sets `PYTHONHOME=/usr`, `PYTHONNOUSERSITE=1`,
`PYTHONDONTWRITEBYTECODE=1`, and an unset `PYTHONPATH`; Python children use the staged interpreter
and these bindings only and cannot create `__pycache__` entries in the writable workspace overlay.
The complete
manifest fixture contains a standard-library package, a native extension under `lib-dynload`, and
the import trace for `json`, `pathlib`, `subprocess`, `tempfile`, `threading`, and the topology and
baseline runners, so omission of the standard library or extension tree is a fixture failure.

`cargo_cache.root` is an absolute retained directory and `cargo_cache.manifest` is an absolute
regular file outside that root and outside the repository. The external cache manifest is schema
version 2 with exactly this field order and canonical wire grammar:

```text
schema_version, allowed_prefixes, root, entry_count, total_size
```

`schema_version` is `2`; `allowed_prefixes` is the exact ordered array
`["git/checkouts", "git/db", "registry/cache", "registry/index", "registry/src"]`; `root` is the
complete `digest_root` value; `entry_count` is the number of non-root entries in that tree; and
`total_size` is the checked sum of all regular-file sizes. A directory is admitted only when it is
an ancestor of one of those five prefixes or lies below one of them; a regular file is admitted only
below one of those prefixes. `registry`, `git`, and the five prefix directories may be present as
intermediate directories, but a sibling such as `registry/config`, `registry/.package-cache`,
`git/config`, or any file at a prefix root outside the listed subtree is rejected. The file uses the
same exact JSON escape table, field order, two-space indentation, and final LF as the control
manifest. It contains no self-digest field. `cargo_cache.manifest_sha256` is the SHA-256 of those
exact bytes, and the worker independently recomputes the structural root digest, serialized manifest
digest, entry count, and total size before any copy. The cache golden vector
`fresh-compiler-cache-manifest-v2-golden` has one `registry/index/a` file containing `abc`, raw modes
`0755`/`0644`, staged modes `0700`/`0600`, `entry_count` `3`, `total_size` `3`, and root digest
`63f8236beb76d3197aad440b166958a92516cc6bd2b4d17c70264e0efce79509`, and manifest digest
`44a98ed3b3adf920e6e02a770d83dd6784e4c16fadcb19ec0f78cde1335261a0`; the complete bytes are
checked independently from the control manifest.

The cache golden vector's exact bytes are:

```json
{
  "schema_version": 2,
  "allowed_prefixes": [
    "git/checkouts",
    "git/db",
    "registry/cache",
    "registry/index",
    "registry/src"
  ],
  "root": {
    "kind": "dir",
    "mode": "0755",
    "staged_mode": "0700",
    "size": 0,
    "sha256": "63f8236beb76d3197aad440b166958a92516cc6bd2b4d17c70264e0efce79509",
    "entries": [
      {
        "name": "registry",
        "kind": "dir",
        "mode": "0755",
        "staged_mode": "0700",
        "size": 0,
        "sha256": "417987180d0d1a99b46745be018da4bd141a40de9e855385f5784c1ecf30ef18",
        "entries": [
          {
            "name": "index",
            "kind": "dir",
            "mode": "0755",
            "staged_mode": "0700",
            "size": 0,
            "sha256": "ef0e4496a41340e438a6ef7390fdd720e180081ff7349f80d23e4fa846e53717",
            "entries": [
              {
                "name": "a",
                "kind": "file",
                "mode": "0644",
                "staged_mode": "0600",
                "size": 3,
                "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                "entries": []
              }
            ]
          }
        ]
      }
    ]
  },
  "entry_count": 3,
  "total_size": 3
}
```

Only the explicitly allowlisted Cargo registry and Git cache subtrees are admitted. `config`,
`config.toml`, credentials, wrappers, `.cargo` directories, target-directory settings, source
replacement, proxy, and network configuration reject. Symlinks, devices, FIFOs, sockets, whiteouts,
absolute paths, duplicate entries, and regular files with `st_nlink != 1` reject; directory link
counts are not used as hard-link evidence. Every regular file must be at most `536870912` bytes, and
the checked sum of all regular-file sizes must be at most `21474836480` bytes; overflow or either
limit rejects before private-root creation. Phase 6 only validates and retains source descriptors.
After the private root exists, each destination directory is created with `mkdirat(...,0700)` and
each regular file with `openat(O_CREAT|O_EXCL|O_NOFOLLOW,0600)`; source descriptors remain retained
through each copy, bytes are bounded, rehashed, fsynced, and enumerated again. The destination
directory mode is `0700` and destination regular-file mode is `0600`; the post-copy comparison uses
`staged_mode`, while the source comparison uses raw `mode`. The source cache is never mounted or
mutated and Cargo runs offline.

The canonical syntax vector `fresh-compiler-manifest-v2-syntax` uses the exact top-level order and
the following cache placement, proving that the control manifest is outside the enumerated root:

```json
{
  "schema_version": 2,
  "controller": {
    "path": "scripts/fresh-align-compiler",
    "api": 1
  },
  "bootstrap": {
    "path": "/usr/local/libexec/align-llm/fresh-bootstrap",
    "sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "api": 1
  },
  "platform": {
    "os": "linux",
    "architecture": "x86_64",
    "kernel_minimum": "6.8",
    "python_minimum": "3.12",
    "make_minimum": "4.3"
  },
  "tools": [],
  "runtime_bindings": [],
  "cargo_cache": {
    "root": "/cache",
    "manifest": "/descriptor/cache-manifest.json",
    "manifest_sha256": "2222222222222222222222222222222222222222222222222222222222222222",
    "entry_count": 0
  }
}
```

This compact vector is syntax-only and is rejected semantically because `tools` is empty. The
complete fixture is the semantic vector; both vectors are checked byte-for-byte, including mode
strings, field order, one final LF, duplicate/unknown rejection, and the external cache-manifest
rule.

### 9.3 Two source identities and materialization

The controller reads the project root's `.align-revision` as raw bytes and accepts exactly one
lowercase 40-hex Align commit ID plus one LF. It rejects NUL, tags, uppercase, whitespace variants,
and extra bytes before asking Git for either repository object. The project root is the checked-out
`align-llm` worktree from which the bootstrap was launched. Its current `HEAD`, object format, tree
ID, index digest, and complete non-control raw worktree manifest are captured as the project-source
identity. The current `HEAD` and object format must equal the signed run capsule's `repository_head`
and `repository_object_format` exactly before the project source manifest is accepted; the run capsule
is therefore an externally bound input, not a record of an untrusted observation. A HEAD replacement,
object-format change, or mutation between supervisor signing and worker validation is a `SOURCE`
failure before materialization. The project root must be clean apart from the reserved root `.git`
control entry and the two output exceptions below.

`ALIGN_REPO` is validated independently as the sibling Align worktree. The trusted supervisor first
resolves the project-relative input from the signed run capsule to a lexical absolute component
sequence without following a symlink. The worker verifies that the capsule's `align_repo_relative`
value is the requested input, retains the project-root parent descriptor, and opens that sequence component-by-component
with `openat(O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)`, allowing `..` only while walking the already
retained parent chain. It records each opened ancestor's device/inode and rechecks the descriptor
before accepting the next component and again before source validation. A missing component,
symlink, ancestor replacement, component device/inode change, or final type mismatch is rejected;
the final descriptor, not the original pathname, is used for every later Git and copy operation.
This keeps the local linked-worktree `.git` file support separate from root-path alias resolution.
This Linux x86_64 profile requires the sibling Align repository to use Git SHA-1 object format:
`sha256` Align repositories are rejected as a `SOURCE` failure before the pinned revision is
accepted, because `.align-revision` and the compiler descriptor intentionally use a lowercase
40-hex Align pin. The source-manifest wire still supports SHA-256 for project repositories and
standalone source-format fixtures; that general wire support does not widen the Align pin contract.
Its raw `HEAD` object must
be a commit whose exact lowercase ID equals the bytes read from the project `.align-revision`; its
tree ID, index digest, and complete raw worktree manifest are captured as the Align-source identity.
An absent root `target/` is allowed. A present root `target/` must be one untracked ordinary directory
whose owner permission bits are exactly read/write/execute, whose group/other write bits are clear,
and whose set-ID and sticky bits are clear; the worker records only its presence and raw mode in the
output-exception check, never descends into it, and never reads, hashes, copies, or passes it to Cargo.
The project root has the same root `target/` exception plus the exact root
`main` exception: `main` must be absent or untracked; when present it must be a single-link regular
file with mode `0644` or `0755`. The worker records only its presence, type, link count, and raw mode
as output metadata and never reads, hashes, copies, or makes it available to Cargo. No root `main`
exception exists in `ALIGN_REPO`. A tracked `target` or `main`, a second output name outside the
whole untracked `target/` subtree, or a mode/type/link-count mismatch rejects. Untracked descendants
of an accepted root `target/` are part of that output exception and are never enumerated. The
source-manifest/v1 `exceptions` object remains the fixed `git`, `target`, and `main` label set;
ordinary Request 6 does not consume that legacy wire and instead uses its separate `raw-tree/v1`
plus source-exception vector. For ordinary Request 6, the project and Align root `HANDOFF.md` files
are explicit control exceptions in that separate vector; a dirty tracked input, staged index change,
ignored or untracked entry outside the root `.git`, root `HANDOFF.md`, root `target/`, and project
root `main` exceptions rejects. The root `.git` entry is reserved Git control metadata: it may be either the
ordinary-clone directory or the linked-worktree `gitdir` file, is validated only through the retained
Git descriptors, and is omitted from source entries and source bytes. A nested `.git` entry, a second
control directory, or a Git control file outside the root entry rejects.
A tracked relative symlink whose complete target chain is non-cyclic and contained by the same
source root is an ordinary source entry, not an output exception. An untracked, absolute, escaping,
or cyclic symlink, directory, device, hard link, or output name at any other path rejects.

For both roots, the worker rejects shallow or promisor repositories, alternates, grafts, replacement
refs, fsmonitor, hooks, filters, bare repositories, `core.worktree`, and caller Git configuration
before object lookup. From each admitted `O_PATH` root, it reopens `.` exactly once with
`O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`, retains and rechecks that scan-capable worktree
descriptor without resolving a mutable pathname, and uses it for filesystem enumeration. It also
retains the `.git` entry, Git directory, common directory, index,
HEAD, object store, and linked-worktree metadata descriptors for each root. Every Git child receives
the retained worktree descriptor as `cwd`,
`GIT_WORK_TREE=/proc/<worker-pid>/fd/<worktree-fd>`,
`GIT_DIR=/proc/<worker-pid>/fd/<git-dir-fd>`, and
`GIT_COMMON_DIR=/proc/<worker-pid>/fd/<common-dir-fd>`; these descriptors are explicitly inherited
and remain retained and rechecked by the worker while the child runs. The worker-owned descriptor
paths remain valid even when an installed Git closes inherited nonstandard descriptors before it
opens repository paths. The fixed environment clears ambient `GIT_*`
values and then adds exactly the retained descriptor variables plus `GIT_CONFIG_NOSYSTEM=1`,
`GIT_ATTR_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_NO_REPLACE_OBJECTS=1`,
`GIT_GRAFT_FILE=/dev/null`, `GIT_NO_LAZY_FETCH=1`, `GIT_OPTIONAL_LOCKS=0`,
`XDG_CONFIG_HOME=/dev/null`, and `LC_ALL=C`. No alternate-object variable is accepted. The worker
compares the project `HEAD` and object format to the run capsule before accepting the project source
manifest, and compares the Align `HEAD` and tree/index values to the pinned revision before any Cargo operation,
rechecks every retained descriptor after each Git child, and rejects any identity change. No source
Git child runs after either source materialization starts.

The ordinary Request 6 `raw-tree/v1` preimage has top-level fields `schema`, `source`, and `entries`
in that order. `source` is `project-source` or `align-source`; entries exclude the exact exception
rows `git`, `handoff`, `target`, and `main` from the source-kind table above, while the separate
canonical exception vector binds their type/mode/link-count state. For `project-source`, root
`HANDOFF.md`, root `target/`, and root `main` are allowed exceptions; for `align-source`, root
`HANDOFF.md` and root `target/` are allowed while `main` is always absent. The six-entry
non-UTF-8/symlink vector has canonical bytes
`8b30014d36e10e32e230fcbbcbe12b6933903da48c8569140cadd62795caad77`; the output-exception semantic
vector leaves those bytes unchanged and has exception-array bytes
`0c685027b378e6ef448e8efd807532eb8f056de04f550e884d56a5ef0834ead0` (1755 bytes). The source-manifest/v1 golden
must cover both semantic-to-byte vectors and reject tracked outputs, symlinked exception roots,
wrong modes/types/link counts, handoff content digest changes, and an ordinary capsule exception
digest mismatch before staging.

Each source manifest compares its raw Git tree and index with a complete descriptor-relative raw
filesystem enumeration excluding the reserved root `.git` control entry and the declared output
exceptions (`target/` for both roots and project `main`). The worker normalizes `git ls-tree`
records into raw-path byte order before validation and serialization; it does not treat Git's
directory-aware tree order as the manifest order. It includes raw path
bytes, type, raw source mode, deterministic staged
mode, Git mode, Git object identity, raw bytes, symlink target bytes, its observed commit or pinned
revision, tree ID, index digest, and output-exception metadata. Ignored, empty,
case-fold-colliding, assume-unchanged, skip-worktree, filter-hidden, special, and untracked build
inputs reject. A permitted symlink is recorded as a relative link and recreated only inside the
corresponding private tree after its target is proven tracked, non-cyclic, and contained. A
same-HEAD repository with an additional recursively consumed Rust or build input is rejected for
either source root, before any helper or compiler starts. The
`fresh-v2-source-manifest-output-exception-golden` regression covers absent and present untracked
`target/` for both roots, absent and present untracked project `main`, tracked-output rejection,
output-name rejection outside the exception roots, and exact type/mode/link-count metadata while proving that no exception bytes
enter `entries` or the source digest.

Its exception-metadata vector is separate from the canonical source bytes and has these exact rows;
`present=false` uses `type=null`, `mode=null`, and `link_count=null`, while `bytes_consumed` is
always `false`:

| Source kind | Label | Present | Type | Mode | Link count | Bytes consumed |
| --- | --- | --- | --- | --- | --- | --- |
| `project-source` | `git` | always | `directory` or linked-worktree `regular` file | retained-descriptor policy | N/A | false |
| `project-source` | `target` | absent or present | `null` or `directory` | `null` or owner-rwx/no-other-write/no-special | `null` or observed | false |
| `project-source` | `main` | absent or present | `null` or `regular` | `null` or `0644`/`0755` | `null` or `1` | false |
| `align-source` | `git` | always | `directory` or linked-worktree `regular` file | retained-descriptor policy | N/A | false |
| `align-source` | `target` | absent or present | `null` or `directory` | `null` or owner-rwx/no-other-write/no-special | `null` or observed | false |
| `align-source` | `main` | always absent | `null` | `null` | `null` | false |

The ordinary Request 6 source-exception wire is separate from source-manifest/v1 and has schema
label `source-exception/v2`. It is the canonical JSON array with one final LF and exact field order
`source`, `label`, `present`, `type`, `mode`, `link_count`, `bytes_consumed`, `content_sha256`.
Rows are ordered as project `{git,handoff,target,main}` followed by Align
`{git,handoff,target,main}`. Both handoff rows are present regular files in the named profile and
are bounded-read for `content_sha256`; project `main` is absent or an untracked regular file, Align
`main` is absent, and each target is absent or an untracked owner-rwx/no-other-write/no-special
directory. Present Git rows use `link_count=null` by explicit retained-descriptor policy;
`content_sha256` is null for Git, target, and main. The complete vector is hashed and carried as
`source_exception_sha256` in the signed `ordinary-adoption/v2` capsule, so the worker compares the
dispatcher-produced exception identity before staging and after each source snapshot. The required
semantic-to-byte golden is 1755 bytes with SHA-256
`0c685027b378e6ef448e8efd807532eb8f056de04f550e884d56a5ef0834ead0`; changing only an admitted
exception changes this digest while leaving raw-tree/v1 bytes unchanged.

The source-manifest value has schema version `1` and is serialized with the canonical JSON grammar
from section 9.2, including the final LF. Its exact top-level field order is
`schema_version`, `kind`, `revision`, `tree_id`, `object_format`, `index_sha256`, `root_mode`, `root_staged_mode`,
`entries`, `exceptions`; `kind` is `project-source` or `align-source`, `revision` is the observed
project `HEAD` or the pinned Align commit, and `tree_id` is the corresponding raw Git tree ID.
`object_format` is exactly `sha1` or `sha256`, obtained from the retained repository's
`extensions.objectFormat` and object-format policy before any lookup. `project-source` may use
either format, while `align-source` is restricted to `sha1` by this profile's fixed 40-hex
`.align-revision` and descriptor contract. A `sha1` repository uses lowercase 40-hex `tree_id` and
`git_object` values; a `sha256` repository uses lowercase 64-hex values. `git_object` is required for every entry: it is the Git tree object ID for a directory, and
the Git blob object ID for a regular file or symlink (the symlink blob contains its raw target
bytes). The object ID is independently checked against the retained object store; a missing,
wrong-width, uppercase, or semantically mismatched ID is a `SOURCE` failure.
`root_mode` is the observed root directory mode and `root_staged_mode` is always `0700`. Each entry
has the exact field order `path_hex`, `kind`, `mode`, `staged_mode`, `git_mode`, `git_object`,
`size`, `sha256`, `symlink_target_hex`. `path_hex` and `symlink_target_hex` are lowercase hex
encodings of the original non-NUL path bytes; `entries` are ordered by the original raw path bytes,
not by decoded text. `kind` is `dir`, `file`, or `symlink`; `git_mode` is one of `040000`, `100644`,
`100755`, or `120000`; a directory has four-digit octal `mode` and `staged_mode`, `size: 0`,
`sha256: null`, and `symlink_target_hex: null`; a regular file has four-digit octal `mode` and
`staged_mode`, its byte size, and complete-byte SHA-256 with a null symlink target; and a symlink has
`mode: null`, `staged_mode: null`, the target-byte size and SHA-256, and its target hex value.
`index_sha256` is SHA-256 of the complete raw `.git/index` byte sequence read from the retained
no-follow descriptor, including its `DIRC` header, version, entry records, extensions, and trailing
checksum; no canonical projection or extension filtering is permitted. The source golden vectors use
the valid empty Git index v2 byte sequence
`44495243000000020000000039d890139ee5356c7ef572216cebcd27aa41f9df` and its independently computed
SHA-256 `79dc0d556c3c637aad3efa1d3a1906e5abea7aa1ffdbb3d3ed9932eec3bf6954`. `null` is the only representation of a symlink mode; the literal string `N/A`, an omitted field, or
an octal mode for a symlink is invalid. `exceptions` has the exact field order `git`, `target`,
`main`; `git` is always `root-git-control`, `target` is always `root-directory-output` for both
source kinds whether the directory is absent or present, and `main` is `root-file-output` for
`project-source` or `null` for `align-source`. The root `.git` control entry is therefore excluded
by an explicit wire rule rather than silently disappearing. The source-manifest/v1 wire has no
`handoff` field and remains unchanged. Ordinary Request 6 does not place its handoff or output
exception metadata in this wire; its separate `raw-tree/v1` and source-exception vector are bound by
the `ordinary-adoption/v2` capsule's `source_exception_sha256`. No other field, encoding, path
normalization, or legacy exception is valid. The source-manifest digest stored in the compiler
descriptor is SHA-256 of these exact canonical bytes.

The independent source-manifest golden vector `fresh-v2-source-manifest-golden` is:

```json
{
  "schema_version": 1,
  "kind": "project-source",
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "tree_id": "1111111111111111111111111111111111111111",
  "object_format": "sha1",
  "index_sha256": "79dc0d556c3c637aad3efa1d3a1906e5abea7aa1ffdbb3d3ed9932eec3bf6954",
  "root_mode": "0755",
  "root_staged_mode": "0700",
  "entries": [
    {
      "path_hex": "61",
      "kind": "file",
      "mode": "0644",
      "staged_mode": "0444",
      "git_mode": "100644",
      "git_object": "3333333333333333333333333333333333333333",
      "size": 3,
      "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      "symlink_target_hex": null
    }
  ],
  "exceptions": {
    "git": "root-git-control",
    "target": "root-directory-output",
    "main": "root-file-output"
  }
}
```

Its canonical bytes hash to
`f5da8d8bbe02e4a7d32154ebeadd0e73beea213a4c036a08a34b313586007e23`; the self-test compares the
complete bytes and independently recomputes this digest before accepting either source root.

The independent contained-symlink vector `fresh-v2-source-manifest-symlink-golden` is:

```json
{
  "schema_version": 1,
  "kind": "project-source",
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "tree_id": "1111111111111111111111111111111111111111",
  "object_format": "sha1",
  "index_sha256": "79dc0d556c3c637aad3efa1d3a1906e5abea7aa1ffdbb3d3ed9932eec3bf6954",
  "root_mode": "0755",
  "root_staged_mode": "0700",
  "entries": [
    {
      "path_hex": "4147454e54532e6d64",
      "kind": "symlink",
      "mode": null,
      "staged_mode": null,
      "git_mode": "120000",
      "git_object": "4444444444444444444444444444444444444444",
      "size": 9,
      "sha256": "6ebdb617a8104a7756d0cf36578ab01103dc9f07e4dc6feb751296b9c402faf7",
      "symlink_target_hex": "434c415544452e6d64"
    }
  ],
  "exceptions": {
    "git": "root-git-control",
    "target": "root-directory-output",
    "main": "root-file-output"
  }
}
```

Its canonical bytes hash to
`14902048674d7363379f6427d8b4b305654794827e9481a3d831b244f0dc77ea`; the vector models the
tracked project `AGENTS.md -> CLAUDE.md` entry and proves that symlink modes are represented by
`null`, while the target bytes remain identity-bearing.

The complete object-format vector `fresh-v2-source-manifest-object-format-golden` covers a directory,
regular file, and contained symlink under both Git object formats. The `sha1` form is:

```json
{
  "schema_version": 1,
  "kind": "project-source",
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "tree_id": "1111111111111111111111111111111111111111",
  "object_format": "sha1",
  "index_sha256": "79dc0d556c3c637aad3efa1d3a1906e5abea7aa1ffdbb3d3ed9932eec3bf6954",
  "root_mode": "0755",
  "root_staged_mode": "0700",
  "entries": [
    {
      "path_hex": "646972",
      "kind": "dir",
      "mode": "0755",
      "staged_mode": "0700",
      "git_mode": "040000",
      "git_object": "2222222222222222222222222222222222222222",
      "size": 0,
      "sha256": null,
      "symlink_target_hex": null
    },
    {
      "path_hex": "6469722f66",
      "kind": "file",
      "mode": "0644",
      "staged_mode": "0444",
      "git_mode": "100644",
      "git_object": "3333333333333333333333333333333333333333",
      "size": 3,
      "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      "symlink_target_hex": null
    },
    {
      "path_hex": "6c",
      "kind": "symlink",
      "mode": null,
      "staged_mode": null,
      "git_mode": "120000",
      "git_object": "4444444444444444444444444444444444444444",
      "size": 5,
      "sha256": "fad5c4fc5b83ba1a282f0559f868876c78bb6e293a977c5a083935ccb0bbb34e",
      "symlink_target_hex": "6469722f66"
    }
  ],
  "exceptions": {
    "git": "root-git-control",
    "target": "root-directory-output",
    "main": "root-file-output"
  }
}
```

The corresponding `sha256` form is:

```json
{
  "schema_version": 1,
  "kind": "project-source",
  "revision": "0000000000000000000000000000000000000000000000000000000000000000",
  "tree_id": "1111111111111111111111111111111111111111111111111111111111111111",
  "object_format": "sha256",
  "index_sha256": "79dc0d556c3c637aad3efa1d3a1906e5abea7aa1ffdbb3d3ed9932eec3bf6954",
  "root_mode": "0755",
  "root_staged_mode": "0700",
  "entries": [
    {
      "path_hex": "646972",
      "kind": "dir",
      "mode": "0755",
      "staged_mode": "0700",
      "git_mode": "040000",
      "git_object": "2222222222222222222222222222222222222222222222222222222222222222",
      "size": 0,
      "sha256": null,
      "symlink_target_hex": null
    },
    {
      "path_hex": "6469722f66",
      "kind": "file",
      "mode": "0644",
      "staged_mode": "0444",
      "git_mode": "100644",
      "git_object": "3333333333333333333333333333333333333333333333333333333333333333",
      "size": 3,
      "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      "symlink_target_hex": null
    },
    {
      "path_hex": "6c",
      "kind": "symlink",
      "mode": null,
      "staged_mode": null,
      "git_mode": "120000",
      "git_object": "4444444444444444444444444444444444444444444444444444444444444444",
      "size": 5,
      "sha256": "fad5c4fc5b83ba1a282f0559f868876c78bb6e293a977c5a083935ccb0bbb34e",
      "symlink_target_hex": "6469722f66"
    }
  ],
  "exceptions": {
    "git": "root-git-control",
    "target": "root-directory-output",
    "main": "root-file-output"
  }
}
```

Its canonical digest is
`5dc22d576eb870679a1867a89d0b2a5f71c7465d1a5bd3586443105eec64c437` for the `sha1` form and
`f071ae8704196869192b8afe934b667046e0713e658ee909812da0781e874872` for the `sha256` form. The
self-test serializes both complete vectors and verifies directory tree IDs, blob IDs, raw symlink
bytes, object-ID widths, and the two independent canonical digests; it does not infer object format
from an ID's length.

The final accepted enumeration for each root retains the root descriptor, the current traversal
stack (at most the declared depth), and only the parent descriptors needed by the current batch. It
opens regular files, source directories, and symlink targets relative to retained parents with
no-follow operations in deterministic active batches of at most
`fresh_source_fd_window = 2048` total source descriptors. It records every accepted directory and
symlink identity as bounded metadata, but does not retain one descriptor per directory or entry.
Symlink targets are read from retained parents with `readlinkat`; no source pathname is used without
a retained parent and an identity check. After each batch closes its active source descriptors, the
worker reopens the affected parent chains descriptor-relatively from the retained root, compares
entry device/inode/type/mode/link bytes to the accepted manifest, and checks every ancestor identity
before opening the next batch. Before copying and after the final private enumeration, every opened
directory is `fstat`-checked for the recorded device/inode/type/mode and enumerated
descriptor-relatively; every symlink is `fstatat(AT_SYMLINK_NOFOLLOW)`-checked for the recorded
device/inode/type and read again with `readlinkat`, with identical target bytes and contained
target-chain identities. A directory entry replacement, removed/added child, mode change, symlink
replacement, target change, or target-chain change rejects before Cargo or the aggregate starts.

For each active regular-file descriptor, the worker records its accepted device/inode/type/mode/size,
reads the complete bytes from that descriptor, computes the accepted digest while copying, and checks
the descriptor again after the read. A changed descriptor identity, mode, size, or accepted digest
rejects. Each destination is then rehashed and its type/mode/size/digest is compared to the
corresponding accepted manifest before the next batch. The final private `project-source` and
`align-source` enumerations must equal their respective manifests. `aggregate-work` is copied only
from the verified `project-source` tree and is independently rehashed; it never reopens the original
project or Align path. The private `align-source` is copied separately and is the only source bound
at `/align-src` for Cargo. The fd-window regression drives more than 200,000 mixed files and
directories and asserts that the worker never exceeds the 2,048 active source window, the declared
depth, or the 4,096 total fd cap.

The fixed pre-dispatch worker snapshot limit is `fresh_worker_max_bytes = 4194304`, with a fixed
5-second monotonic supervisor/bootstrap read deadline and a 5,000-second worker invocation
deadline covering tool probes, source/cache validation, materialization, build, aggregate, and
final cleanup; the bootstrap
rejects a larger controller before reading beyond that bound or starting a repository child. The
fixed source/resource limits are: at most 200,000 non-root entries per source root, depth 64,
64 MiB of raw path and link bytes, 512 MiB per regular source file, 4 GiB total source bytes, 512
MiB per authenticated tool or runtime regular file, 20 GiB total runtime bytes, 8 GiB total staged
tool/runtime bytes, 4 GiB total private Git-view bytes, and 2,048 bytes per symlink target. The
hex-encoded `symlink_target_hex` field is therefore at most 4,096 bytes and fits the ordinary
canonical-string limit. The worker checks counts, depth, byte sums, and checked 64-bit overflow before private-root creation or
copy; `SOURCE` rejects source-limit failures, `TOOL` rejects tool/runtime-limit failures, and
`FILESYSTEM` rejects private staging-limit failures. These bounds include directories' names and
metadata but not their platform-specific link-count bookkeeping. No source, runtime, tool, Git-view,
or generated-output dimension is unbounded under this profile.

The accepted source manifests store raw source mode and a separate deterministic staged mode. A
regular tracked file must have filesystem mode `0644` with Git mode `100644`, or filesystem mode
`0755` with Git mode `100755`; its staged mode is respectively `0444` or `0555`. A source directory
must provide owner read/write/execute and no set-ID or sticky bit; its raw mode remains in the
manifest for the pre-copy repeat, while its private staged mode is always `0700`. A symlink has
`mode: null` and `staged_mode: null`; its contained target is the identity-bearing value and its
recreated link has no mode comparison. Destination comparison uses the staged mode for directories
and regular files, never the raw source mode, so ordinary `0644`/`0755` checkouts satisfy the
contract without an unstated normalization. The aggregate lower tree is exposed through a read-only overlay lower
layer; its private upper layer, not the lower tree, is the only place aggregate writes can land. The
immutable project copy is the aggregate identity reference, and the aggregate lower/upper trees are
rescanned after every aggregate to prove that no source input changed and every generated output is
an allowed private artifact. Neither original repository, sibling target, nor source cache is visible
inside either namespace.

The tracked Align file `.cargo/config.toml` is an intentional source input, not ambient Cargo
configuration. At the pinned revision its mode is `0644`, its staged mode is `0444`, its SHA-256 is
`65016e7a451dc056597b68e7b83ce989560aabf62f2a265d37ca61ddda0c1be3`, and its complete bytes must
match the retained Git object before Cargo starts. The only accepted Cargo configuration is that
file's `[env]` table with the single key `LLVM_SYS_221_PREFER_DYNAMIC = "1"`; a `build`, `target`,
`net`, `http`, `source`, `registries`, wrapper, path, proxy, or any other environment setting is a
`SOURCE` failure. The worker supplies `CARGO_HOME=/cargo`, `CARGO_NET_OFFLINE=true`, and the fixed
tool paths explicitly, with no `--config` argument and no host Cargo configuration. The source
manifest, source-copy proof, and the phase-5 Cargo-config parser all name this same digest and exact
key set. Phase 8 consumes only that accepted phase-5 snapshot; it does not parse or revalidate Cargo
configuration. A future pinned Align revision must update the reviewed contract before adoption.

### 9.4 Private root and build identity

After manifest, tool, Git, source, and cache validation, the worker opens `/tmp` with
`O_DIRECTORY|O_NOFOLLOW`, requires mode `01777`, and verifies from `/proc/self/mountinfo` that the
mount has no `MS_NOEXEC` flag. A `noexec` or ambiguous `/tmp` mount is a `PLATFORM` failure before
root creation; `/tmp` is never used as the private-root parent. Before scanning or creating a root,
it opens the protected lock parent
`/run/user/<uid>/align-llm-fresh` component-by-component with
`O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`, verifies `/run` and `/run/user` as fixed root-owned
mode-`0755` ancestors and verifies the device/inode, owner uid, and mode `0700` of
`/run/user/<uid>` and the lock-parent component, opens `lock` with
`O_CREAT|O_NOFOLLOW|O_CLOEXEC` mode `0600`, fstats it as a single-link regular file owned by the
effective uid with mode `0600`, and takes
`flock(LOCK_EX|LOCK_NB)` on descriptor `10`. The parent is outside `/tmp`, is created by the
image/profile installation, and is never replaceable by a process that lacks the effective uid;
replacement, unlink/recreate, wrong-owner, or wrong-mode detection is a `PLATFORM` failure. It then
opens the profile-created `roots` child with `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`, verifies mode `0700`,
effective-uid ownership, and stable device/inode, and retains that descriptor as the only root parent.
With the worker-owned lock held, it scans `roots` only for bounded raw name existence, considering any
name with the private-root prefix `align-llm-fresh-` a candidate and never inspecting candidate
contents: at most 65,536 directory entries and one second, with cap-plus-one or ambiguous
read/deadline failure returning `fresh compiler: ERROR FILESYSTEM filesystem\n`. It never reads,
classifies, or removes a candidate. With no candidate present, it creates one
`align-llm-fresh-<32 lowercase random hex>` with `mkdirat(roots_fd,O_EXCL,0700)`. It retries exactly
eight collisions and records parent device/inode, root device/inode, owner token, and root descriptor.
The worker resolves every private mount source relative to the retained root descriptor, opens it
with `O_PATH|O_NOFOLLOW|O_CLOEXEC`, verifies its type and effective-uid ownership, and passes only
those exact descriptors to the outer bwrap setup. The bwrap argv consumes each descriptor through
`--bind-fd` or `--ro-bind-fd`. Because bwrap has no descriptor form of its overlay operation, its
three retained overlay descriptors are named only as `/proc/self/fd/<fd>` in that bwrap's own argv.
The bwrap-only tool forwarder marks every nonstandard descriptor close-on-exec, recognizes mount
descriptors in `--bind-fd`, `--ro-bind-fd`, `--overlay-src`, and the writable arguments of `--overlay`,
and recognizes the namespace descriptor in `--userns` before the payload delimiter. It clears
close-on-exec only for that exact set. Read-only fd-bind operations for the three overlay descriptors
follow the overlay operation so bwrap consumes and closes them during setup; the `--userns` descriptor
is consumed by bwrap's pre-clone `setns` operation and is not inherited by the payload. A following
tmpfs hides the overlay holding mounts before the payload. The child never asks the new user namespace
to traverse the parent worker's procfs descriptor path. The worker retains its copies until bwrap
exits and closes them before cleanup.
It never removes shared `/tmp`, the profile root parent, the project root,
`ALIGN_REPO`, either source cache, or a path whose parent/name identity it cannot prove.

The private root owns exactly these children, all created with `mkdirat` and no replacement:

```text
project-source/  0700; aggregate source files 0444/0555; retained project identity copy
align-source/    0700; Align Cargo source files 0444/0555; retained pinned identity copy
aggregate-work/  0700; input files 0444/0555; immutable aggregate lower tree
cargo-home/      0700; copied offline registry/Git cache
cargo-target/    0700; private build output and pre-created tmp/
aggregate-output/0700; workspace-upper/0700 and empty workspace-work/0700 on one filesystem;
                 sole writable aggregate overlay owner
baseline-git/    0700; private read-only project Git view for baseline-check
runtime/         0700; copied runtime files 0444/0555 by source execute mode; directories remain 0700
tool-bin/        0700; copied executables 0555, runtime archive 0444, and handoff files 0444; directories remain 0700
descriptor/      0700; cleanup journal only
```

The admission and execution bounds are fixed worker constants and are enforced rather than merely
reported: `fresh_root_max_bytes = 68719476736` (64 GiB), `fresh_private_entry_max = 400000`,
`fresh_git_object_max = 1000000` per retained Git view, `fresh_aggregate_tmp_entry_max = 65536`,
`fresh_process_max = 512` descendants per child tree, `fresh_source_fd_window = 2048` active source
descriptors per batch, `fresh_open_fd_max = 4096` descriptors per worker/child, and
`fresh_child_file_max_bytes = 536870912` (512 MiB) for the child `RLIMIT_FSIZE` hard and soft limit.
The image/profile also exposes the fixed delegated cgroup-v2 parent
`/sys/fs/cgroup/align-llm-fresh/<uid>`; it is not a caller input and is verified before any child.
Source, manifest, cache, runtime, tool, and generated-output bounds in the other subsections are strict sub-bounds of
the root limit. The Git object scanner counts loose objects and
pack-index entries from retained descriptors before private-root creation; every private-tree scan
counts directory entries with checked overflow and fails at the cap-plus-one. The worker samples
its own and each child tree's `/proc/<pid>/fd` count, applies `RLIMIT_NOFILE=4096`,
`RLIMIT_NPROC=512`, and `RLIMIT_FSIZE=536870912` before every child, and requires each build and
aggregate process tree to use a unique leaf under the delegated cgroup parent with `pids.max=512`;
a host without that delegated cgroup control is outside this profile. The aggregate
tmpfs is created with both `size=268435456` and `nr_inodes=65536`. An inode, descriptor, process,
Git-object, or root-byte cap breach is a `FILESYSTEM` or `CHILD` failure before the next side effect.

`cargo-target/tmp` is created before the build bwrap with mode `0700` and is the sole pre-existing
entry in the private target. The build environment sets `TMPDIR=/target/tmp`; the build namespace
and empty-target fixture require this directory to exist and contain no unowned entry. The aggregate
does not bind this host-side directory: it receives a bounded namespace-owned tmpfs at
`/target/tmp`, and its nested validation bwrap may bind only that already-private namespace mount.
Staging directories deliberately remain writable by the worker owner. Read-only files and
read-only namespace binds prevent child writes, while retaining directory write authority allows
the owner to unlink staged files during cleanup. The worker never changes staging directories to
`0555` before cleanup. It verifies that `workspace-upper` and `workspace-work` have the same
device, are empty at creation, and remain owner-only before passing them to bwrap; a cross-device
pair or pre-existing overlay entry is a `FILESYSTEM` error before the aggregate child starts.

### 9.5 Exact build namespace

The worker launches the pinned Align release build through the declared bwrap. The following is the
exact argv shape; one `--ro-bind-fd` pair is emitted for each ordered runtime binding after its target
parents are created with `--dir`:

```text
bwrap --clearenv --die-with-parent --new-session --unshare-user --unshare-pid --unshare-net \
  --tmpfs / --proc /proc --dev /dev \
  --dir /align-src --dir /tools --dir /runtime --dir /cargo --dir /target --dir /target/tmp \
  --dir /bin --dir /lib --dir /lib64 --dir /usr --dir /usr/bin --dir /usr/lib \
  --dir /tmp --dir /dev/shm \
  --ro-bind-fd <align-source-fd> /align-src \
  --ro-bind-fd <tool-bin-fd> /tools \
  --ro-bind-fd <cargo-home-fd> /cargo \
  --bind-fd <cargo-target-fd> /target \
  <ordered runtime binding operations> \
  --setenv HOME /nonexistent --setenv TMPDIR /target/tmp --setenv PATH /tools \
  --setenv PYTHONDONTWRITEBYTECODE 1 \
  --setenv LIBRARY_PATH <derived-library-path> --setenv LD_LIBRARY_PATH <derived-loader-path> \
  --setenv PKG_CONFIG_PATH <derived-pkg-config-path> \
  --setenv CARGO_HOME /cargo --setenv CARGO_TARGET_DIR /target \
  --setenv CARGO_NET_OFFLINE true --setenv MAKE /tools/make \
  --setenv RUSTC /tools/rustc --setenv CARGO /tools/cargo \
  --setenv LLVM_CONFIG /tools/llvm-config-22 --setenv CC /tools/cc \
  --setenv CXX /tools/cxx --setenv AR /tools/ar --setenv RANLIB /tools/ranlib \
  --setenv CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER /tools/cc \
  --chdir /align-src \
  -- /tools/cargo build --manifest-path /align-src/Cargo.toml --locked --offline --release \
     -p align_runtime -p align_driver
```

The Rust target linker is the authenticated `/tools/cc` driver, not the raw `/tools/linker`
`ld.lld` executable. Rust passes driver options such as `-m64` and `-Wl,...` to its configured
linker; `/tools/cc` translates those options and invokes the fixed `/runtime/cc-suite/bin/ld.lld`
through its declared `-fuse-ld` path. The `linker` tool record remains in the closed inventory for
that direct compiler-suite linker and its identity checks; it is not used as the Rust driver entry
point.

`<ordered runtime binding operations>` is not a free-form placeholder: for each manifest binding,
the worker emits `--dir` for every missing target parent and then either
`--ro-bind-fd <runtime-binding-fd> <target-file>` or
`--ro-bind-fd <runtime-binding-fd> <target-tree>`, in manifest order. Overlapping targets,
missing parents, host paths, or bindings not represented in the manifest reject before bwrap. The
empty tmpfs root hides the host root, HOME, `/tmp`, original `ALIGN_REPO`, the project root, sibling
target, host PATH, and source cache. Only `/target` is writable; `/cargo` is a read-only authenticated cache copy and
`/target/tmp` is already owned by the worker. The build fixture writes markers through every visible
and hidden path and requires only the declared outputs to change; a double-fork child proves that
`--unshare-pid` is present.

After Cargo succeeds, the worker requires `/target/release/alignc` and its adjacent
`/target/release/libalign_runtime.a` to be bounded regular files with the expected
compiler/archive identity. Cargo may hard-link those release outputs to its `deps` copies, so the
worker reads each output only through a before/after no-follow identity check that includes its link
count, then materializes the bytes into the worker-owned
`/target/fresh-bundle/{alignc,libalign_runtime.a}` with create-exclusive writes. Each materialized
handoff file must be a regular single-link file with mode `0555` or `0444`; the raw Cargo release
paths never enter the descriptor or aggregate namespace. It checks the compiler's ELF interpreter
and complete dynamic dependency closure against the authenticated runtime bindings, hashes both
materialized outputs, and copies the compiler to `tool-bin/alignc` with mode `0555` and the archive
to `tool-bin/libalign_runtime.a` with mode `0444`.
It hashes both private copies and then creates the write-once descriptor and guard files beside them.
The compiler and archive are an inseparable private sibling bundle: the aggregate exposes them
read-only as `/tools/alignc` and `/tools/libalign_runtime.a`. A host path, pre-existing target, or
mutable Cargo home is never reused.

### 9.6 Read-only compiler identity and private executable bundle

The descriptor is schema version 4 and is never accepted from a mutable host pathname. The worker
serializes it with the same canonical JSON rules, creates `tool-bin/fresh-descriptor` with
create-exclusive write-once semantics, fsyncs it, changes its mode to `0444`, and reopens it with
`O_RDONLY|O_NOFOLLOW` to verify the exact bytes and device/inode identity. It performs the same
write-once procedure for `tool-bin/fresh-guard` at mode `0444`. The guard contains the canonical
descriptor-byte SHA-256 and compiler-byte SHA-256. These two files, the compiler, and its runtime
archive are copied into the same worker-owned `tool-bin` directory and exposed by one read-only
`/tools` bind; the worker retains the private root and both file identities until the aggregate has
exited. A sealed memfd may be used as the worker's temporary construction buffer, but no worker
descriptor or construction memfd crosses the aggregate boundary.

The build and aggregate bwrap setup processes are invoked with `close_fds=True` and only their
verified private mount-source descriptors in `pass_fds`; ordinary descriptors are consumed by a
`--bind-fd` or `--ro-bind-fd` operation. The nested validation bwrap additionally passes its one
prepared user-namespace descriptor in `pass_fds`, consumed by `--userns`. The bwrap-only forwarder
rejects malformed descriptor arguments, leaves unrelated descriptors close-on-exec, and passes only
the recognized setup set.
The three aggregate overlay descriptors are registered by post-overlay read-only fd-bind operations
and their holding mounts are hidden before the payload starts. The aggregate Make payload starts
with an empty inherited descriptor set. A nested coding-task bwrap receives exactly one additional
prepared user-namespace descriptor through the explicit exception in the coding-task runner; no
other descriptor is inherited. No compiler identity descriptor is inherited by Make, a shell,
Python, a fixture, or a nested validation task, so those helpers may close, mark, or replace their
ordinary descriptors without affecting the worker or another compiler invocation. The prior
protected-fd seccomp filter and bwrap `--seccomp` handoff
are deliberately absent from this contract: there are no worker-owned identity descriptors in the
child process tree to protect. The fixed read-only bind is the ownership boundary, and the closure
tests prove that replacing a path in the private root or attempting to create an alternate descriptor
cannot change the namespace-visible bundle.

The launcher opens exactly `/tools/fresh-descriptor`, `/tools/fresh-guard`, `/tools/alignc`, and
`/tools/libalign_runtime.a` with `O_RDONLY|O_NOFOLLOW`. It requires regular-file type, the descriptor's
declared mode, size, and bytes, the guard's exact digest pair, compiler/archive sibling paths, and
the private `/tools` mount identity. It hashes the namespace-visible compiler and archive against the
descriptor and guard, then executes the already-open `/tools/alignc` file with
`execveat(AT_EMPTY_PATH)`. This deliberate private-path execution is required because the pinned
Align compiler's current `runtime_archive()` uses `current_exe()` and searches beside the real
executable. The read-only `/tools` bind makes `/tools/alignc`, `/tools/libalign_runtime.a`, the
descriptor, and the guard immutable for the aggregate. The launcher accepts no compiler pathname,
descriptor pathname, or fallback from the environment, PATH, `ALIGN_REPO`, sibling release/debug
paths, or the host.

The descriptor's exact top-level order and nested order are:

```text
schema_version
align_revision
project_source_manifest_sha256
align_source_manifest_sha256
toolchain_manifest_sha256
compiler
compiler_support
runtime_paths
launcher_policy

compiler: path, mode, size, sha256
compiler_support: runtime_archive
runtime_archive: path, mode, size, sha256
runtime_path: path, mode, size, sha256
launcher_policy: kind, descriptor_namespace_path, guard_namespace_path, compiler_namespace_path,
namespace
```

`schema_version` is `4`; `align_revision` is lowercase 40-hex; the three manifest digests are
lowercase 64-hex; `compiler.path` and `runtime_path.path` are private-root-relative no-dot paths;
all modes are four-character strings except the fixed compiler-support archive mode `0444`; all
sizes are bounded unsigned integers; and every digest is lowercase 64-hex.
`compiler_support.runtime_archive` is exactly
`{path:"tool-bin/libalign_runtime.a", mode:"0444", size:<build-size>, sha256:<build-digest>}`.
`launcher_policy` is exactly `{kind:"private-path-readonly-id",
descriptor_namespace_path:"/tools/fresh-descriptor", guard_namespace_path:"/tools/fresh-guard",
compiler_namespace_path:"/tools/alignc", namespace:"fresh-aggregate-v4"}`. Unknown fields,
duplicate fields, wrong order, path escapes, handoff-file replacement, wrong read-only mount, or a
file identity mismatch reject. `compiler.path` must be `tool-bin/alignc`, the descriptor path must
be `tool-bin/fresh-descriptor`, the guard path must be `tool-bin/fresh-guard`, and the only namespace
execution path derived from them is `/tools/alignc`; the archive must be its sibling at
`/tools/libalign_runtime.a`. Every `runtime_path.path` is exactly one
`runtime/runtime-<ordinal>` path from the authenticated runtime-binding array, and its mode, size,
and digest must equal that copied object; a logical namespace target or an unlisted staging path is a
`COMPILER` failure.

The descriptor golden vector `fresh-compiler-descriptor-v4-golden` is:

```json
{
  "schema_version": 4,
  "align_revision": "0123456789abcdef0123456789abcdef01234567",
  "project_source_manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "align_source_manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "toolchain_manifest_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
  "compiler": {
    "path": "tool-bin/alignc",
    "mode": "0555",
    "size": 3,
    "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
  },
  "compiler_support": {
    "runtime_archive": {
      "path": "tool-bin/libalign_runtime.a",
      "mode": "0444",
      "size": 3,
      "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    }
  },
  "runtime_paths": [
    {
      "path": "runtime/runtime-000000",
      "mode": "0444",
      "size": 3,
      "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    }
  ],
  "launcher_policy": {
    "kind": "private-path-readonly-id",
    "descriptor_namespace_path": "/tools/fresh-descriptor",
    "guard_namespace_path": "/tools/fresh-guard",
    "compiler_namespace_path": "/tools/alignc",
    "namespace": "fresh-aggregate-v4"
  }
}
```

The syntax vector is checked byte-for-byte and a separate fixture substitutes deterministic private
bytes whose digests are recomputed. The handoff guard vector `fresh-compiler-handoff-guard-v1-golden`
is the canonical JSON object `{schema_version:1, descriptor_sha256:<64-hex>,
compiler_sha256:<64-hex>}` in that field order and is checked independently. The descriptor and guard
are write-once private handoff files, not host paths or mutable environment hints.

Every fresh compiler consumer uses the common fresh launcher. In the aggregate namespace `ALIGNC` is
`/tools/fresh-alignc`; the launcher opens the four fixed handoff/bundle paths, verifies their bytes,
mount identity, revision, and digests, and executes the already-open `/tools/alignc` file with
`execveat(AT_EMPTY_PATH)`. If any handoff file or bundle member is absent, replaced, writable, or
fails identity validation, it returns a `COMPILER` error; it never falls back. The
`ALIGN_LLM_FRESH_COMPILER` environment marker is diagnostic only and is not the security gate.
Clearing or changing that marker, `ALIGNC`, or any handoff environment cannot enable a fallback
because the aggregate namespace contains no old compiler and the launcher uses only fixed
read-only `/tools` paths.

Before the aggregate namespace is built, the worker copies the reviewed source launcher
`scripts/fresh-alignc` into `tool-bin/fresh-alignc` with mode `0555` and binds it as
`/tools/fresh-alignc`; its bytes are covered by the source manifest and post-copy digest, not by an
ambient host tool record. The worker stages `fresh-descriptor` and `fresh-guard` beside that launcher
with mode `0444` and binds all three files through the same read-only `/tools` mount. The platform
self-test and aggregate regression replace each source path after staging, verify that the namespace
still exposes the retained bytes, assert that no worker identity fd is present in a non-compiler
child, and compile a tiny Align program through `/tools/alignc` using its sibling archive. The static
call-site check
requires `$(ALIGNC)` or the explicit fresh launcher for every compiler consumer, including
`scripts/check-format`, prompt/evaluation runners, and `eval/runners/record-baseline.py`. No fresh
path may resolve a compiler through a shebang, bare `alignc`, a sibling target, or ambient PATH; the
only permitted compiler execution path is the launcher-verified `/tools/alignc` bundle.

### 9.7 Exact aggregate namespace and interpreter boundary

The capable `ci` aggregate is not a host-side process. It runs in a second bwrap namespace so its
shell, Python, `env`, nested bwrap, loader, and compiler all use the authenticated staged copies.
The worker first creates `aggregate-work` from the immutable source copy, then creates two owner-only
directories `aggregate-output/workspace-upper` and `aggregate-output/workspace-work` on the same
filesystem. The second directory is empty before the mount and is used only as the overlayfs work
directory. bwrap mounts `aggregate-work` as the immutable lower layer and the two aggregate-output
directories as the overlay upper/work pair at `/workspace`. There is no standalone `/workspace/main`
file bind: the writable parent directory is intentional because the Align compiler stages
`.align-publish-*` beside `main` and atomically renames the staged executable into place. The upper
layer, not the lower source copy, receives that publication.

The focused `adoption` mode uses the same authenticated staged shell, Python, `env`, loader, compiler,
private source, cache, process, temporary-filesystem, and cleanup boundary, but it has a distinct
namespace profile: it binds the immutable private project source read-only at `/workspace`, creates
no overlay upper/work pair, runs no aggregate, and publishes no `/workspace/main`. All current smoke
scripts must direct temporary fixtures, invalid task files, markers, and baseline scratch files to
`/target/tmp` before the FRESH-WORKER capability can pass its call-site audit. The mode-specific
workspace output allowlists are therefore:

```text
ci:       /workspace/main                one regular compiler output file
adoption: /workspace/**                  immutable private source only; no new or changed entry
both:     /target/tmp/**                 bounded namespace-owned temporary files and directories
```

No `eval/`, `scripts/`, `src/`, `tests/`, `Makefile`, or source-control path is writable in the
lower tree. The aggregate enters its user namespace as UID/GID 0 with `CAP_SYS_ADMIN`,
`CAP_SETFCAP`, `CAP_SETUID`, and `CAP_SETGID` temporarily added. `CAP_SYS_ADMIN` lets the staged
`mount-guard` apply the required mount attribute; `CAP_SETUID` and `CAP_SETGID` let that guard
prepare one descendant user namespace whose UID/GID map is exactly `0 0 1`. The guard writes
`setgroups=deny` before the gid map, keeps the helper child alive under the aggregate process, and
publishes the helper's `/proc/<pid>/ns/user` path as the private
`ALIGN_LLM_VALIDATION_USERNS_PATH` environment value. This setup happens before capability
reduction and the path is available only inside the aggregate namespace. The guard then reduces
its effective and permitted capability sets to `CAP_SETFCAP` only, sets `no_new_privs`, and execs
the requested command; `CAP_SYS_ADMIN`, `CAP_SETUID`, and `CAP_SETGID` are not retained by Make or
its direct children. `CAP_SETFCAP` remains available for the nested bwrap's declared UID-0
mount-guard setup, but no nested task receives `CAP_SYS_ADMIN` after its own guard. The helper
inherits the aggregate parent's death signal and is therefore removed when Make or the aggregate
exits; a failed map or exec kills and reaps it before reporting failure.
The aggregate mounts a `268435456`-byte namespace-owned tmpfs at `/target/tmp`; it never binds the
host-side `cargo-target/tmp`. Before Make starts, the staged `mount-guard` executes
`mount_setattr(MOUNT_ATTR_NOSYMFOLLOW)` only on `/target/tmp` and verifies that mount identity. A symlink such as
`/target/tmp/e -> /workspace` therefore cannot turn a temporary pathname into a workspace write.
Contained relative symlinks in the immutable source remain usable because `/workspace` is not
marked no-symlink-follow; source enumeration and materialization already prove that every such link
stays within the private source tree. The nested validation bwrap may bind only this already-private
namespace mount and reapplies the same attribute before its task starts. Namespace tmpfs contents are removed by bwrap
unmount; the worker scans only the lower tree, overlay upper tree, and overlay work directory after
unmount, and requires the temporary mount to be gone.

For `ci`, the upper tree may contain no entry when publication never started, or exactly the final
regular `main` output when publication occurred; a successful aggregate requires exactly that one
`main`. The final `main` must be an x86_64 Linux ELF regular file with `st_nlink == 1`, exact mode `0755`
(read/execute for owner, group, and other; no write or special bits), and a size from 1 through the fixed
`generated_main_max_bytes = 268435456`. Before accepting aggregate success, the worker opens the
output with `O_RDONLY|O_NOFOLLOW|O_CLOEXEC`, records its device/inode/mode/size, reads and hashes all
bytes, and parses its `PT_INTERP`, `DT_NEEDED`, `RPATH`, and `RUNPATH`
from the retained output descriptor and recursively resolves every dynamic dependency against the
authenticated runtime tree and the derived `LD_LIBRARY_PATH`; every resolved file is compared to its
runtime digest and staged mode. A missing or ambiguous dependency, a loader outside the runtime
bindings, an absolute host path, or an unresolved `RPATH`/`RUNPATH` is an aggregate failure. A
statically linked output is rejected: the published contract requires one absolute `PT_INTERP` and
at least one `DT_NEEDED` entry before recursive closure resolution.

After the overlay is unmounted, the worker reopens the parent descriptor-relatively and rechecks
the final entry's device/inode, regular type, `st_nlink`, exact mode, size, and complete-byte
SHA-256. A changed, hard-linked, truncated, oversized, non-ELF, or differently hashed `main` is an
aggregate failure; output identity is not inferred from its pathname.
Compiler staging names such as `.align-publish-*` must be absent after a successful aggregate. The
work directory must contain no user-created entry. During live quota polling, the worker scans
every upper entry and every work-parent entry except the known kernel-owned internal `work/`
directory; that directory is counted as an opaque directory and is not recursively opened because
its overlayfs permissions are owned by the aggregate namespace. Any other work entry remains
subject to the full descriptor-relative quota scan. After an aggregate has started and its overlay
mount has exited, the only accepted overlayfs state is an empty work directory or exactly one
directory named `work`; the worker opens the parent descriptor-relatively, verifies that entry is a
directory without following a symlink, and removes it with one descriptor-relative `rmdir`. It never
recursively enters or deletes that internal directory. Any lower-tree mutation, upper entry other
than `main`, unknown work entry, source-control write, surviving temporary mount, or unbounded
temporary growth rejects. A failed aggregate is still rescanned and cleaned with the same allowlist;
it is not granted a wider write set because it failed. For `adoption`, the worker instead rechecks
the read-only `/workspace` source identity and requires no overlay directories, no `.align-publish-*`
entry, no `main` publication, and no source mutation; a failed focused run uses the same bounded
temporary and process cleanup path.

The generated-output and temporary bounds are fixed: the aggregate namespace tmpfs is 256 MiB, the
overlay upper/work pair is 512 MiB combined, and the post-build ELF dependency graph has at most
4,096 nodes and 64 levels. The worker checks these limits before and during publication and reports
`CHILD aggregate` on overflow; no output or temporary dimension is unbounded.

The implementation's call-site migration is explicit. Before the fresh aggregate is accepted, these
existing workspace-temp paths must be changed to the worker-provided temporary root:

| Existing call site | Required fresh behavior |
| --- | --- |
| `scripts/run-loop-smoke` and the loop marker in `src/main.align` | The script's output file and marker use `$ALIGN_LLM_TEMP_ROOT`; the Align loop obtains that existing environment value through `std.env` and writes, tests, and removes `<root>/loop-smoke-marker`. No `eval/.loop-smoke-marker` path remains. |
| `scripts/run-coding-task-timeout-smoke` | Its `.timeout.XXXXXX.json`, `.normal.XXXXXX.json`, and markers use `$ALIGN_LLM_TEMP_ROOT` below `/target/tmp`; no `project_root` temp path remains. |
| `scripts/run-coding-task-invalid-smoke` | Its task fixtures, ignored fixture directories, and whitespace fixtures use `$ALIGN_LLM_TEMP_ROOT`; its host-boundary marker is created in the aggregate `/workspace` and remains outside the nested validation bind list. Its subprocess fixture roots remain beneath the worker temporary root. |
| `scripts/run-baseline-invalid-smoke` | The invalid baseline temp file and its private Git fixture use `$ALIGN_LLM_TEMP_ROOT`; it never writes `eval/baselines/.invalid.*` or any ref below `/workspace/.git`. |
| `eval/runners/verify-baseline.py` and `eval/runners/record-baseline.py` | Every Git child uses the worker-provided private `/baseline-git` view; no helper resolves `.git`, `git-common-dir`, or an ambient `GIT_*` path from `/workspace`. Their own temporary fixtures use `$ALIGN_LLM_TEMP_ROOT`. |
| `eval` Git tasks and the Git calls in `src/main.align` | Project-root Git reads use the aggregate's exact `GIT_DIR=/baseline-git`, `GIT_COMMON_DIR=/baseline-git`, and `GIT_WORK_TREE=/workspace` values; fixture repositories explicitly clear those three variables before `git init` or a fixture-local Git operation. The call-site audit covers every direct Git argv and rejects an ambient or hidden-workspace Git view. |
| All other `mktemp`/`TemporaryDirectory` callers | The static fresh-call-site check proves the default resolves below `/target/tmp` and rejects an explicit project-root destination. |

The worker sets `ALIGN_LLM_TEMP_ROOT=/target/tmp` and the aggregate namespace rejects any alternate
value. This table is part of the public implementation ledger, not an optional cleanup optimization.

The exact `ci` aggregate argv shape is:

```text
bwrap --clearenv --die-with-parent --new-session --unshare-user --unshare-pid --unshare-net \
  --uid 0 --gid 0 --cap-add CAP_SYS_ADMIN --cap-add CAP_SETFCAP \
  --cap-add CAP_SETUID --cap-add CAP_SETGID \
  --size 268435456 --tmpfs / --proc /proc --dev /dev \
  --dir /workspace --dir /baseline-git --dir /tools --dir /cargo --dir /target \
  --dir /bin --dir /lib --dir /lib64 --dir /usr --dir /usr/bin --dir /usr/lib \
  --dir /fd-hold --dir /fd-hold/lower --dir /fd-hold/upper --dir /fd-hold/work \
  --overlay-src /proc/self/fd/<aggregate-work-fd> \
  --overlay /proc/self/fd/<workspace-upper-fd> \
            /proc/self/fd/<workspace-work-fd> /workspace \
  --ro-bind-fd <aggregate-work-fd> /fd-hold/lower \
  --ro-bind-fd <workspace-upper-fd> /fd-hold/upper \
  --ro-bind-fd <workspace-work-fd> /fd-hold/work --tmpfs /fd-hold \
  --ro-bind-fd <tool-bin-fd> /tools \
  --ro-bind-fd <cargo-home-fd> /cargo \
  --ro-bind-fd <cargo-target-fd> /target \
  --ro-bind-fd <baseline-git-fd> /baseline-git \
  --size 268435456 --tmpfs /target/tmp \
  <same ordered runtime binding operations> \
  --setenv HOME /nonexistent --setenv TMPDIR /target/tmp --setenv PATH /tools \
  --setenv PYTHONHOME /usr --setenv PYTHONNOUSERSITE 1 \
  --setenv PYTHONDONTWRITEBYTECODE 1 \
  --setenv LIBRARY_PATH <derived-library-path> --setenv LD_LIBRARY_PATH <derived-loader-path> \
  --setenv PKG_CONFIG_PATH <derived-pkg-config-path> \
  --setenv ALIGNC_CACHE off \
  --setenv ALIGN_LLM_TEMP_ROOT /target/tmp \
  --setenv ALIGN_LLM_TOOL_ROOT /tools --setenv ALIGN_LLM_PYTHON /tools/python3 \
  --setenv ALIGN_LLM_BASELINE_GIT_DIR /baseline-git \
  --setenv ALIGN_LLM_BASELINE_GIT_COMMON_DIR /baseline-git \
  --setenv ALIGN_LLM_BASELINE_GIT_WORK_TREE /workspace \
  --setenv GIT_DIR /baseline-git --setenv GIT_COMMON_DIR /baseline-git \
  --setenv GIT_WORK_TREE /workspace --setenv GIT_CONFIG_NOSYSTEM 1 \
  --setenv GIT_ATTR_NOSYSTEM 1 --setenv GIT_CONFIG_GLOBAL /dev/null \
  --setenv GIT_NO_REPLACE_OBJECTS 1 --setenv GIT_GRAFT_FILE /dev/null \
  --setenv GIT_NO_LAZY_FETCH 1 --setenv GIT_OPTIONAL_LOCKS 0 \
  --setenv XDG_CONFIG_HOME /dev/null --setenv LC_ALL C \
  --setenv SHELL /bin/sh --setenv MAKE /tools/make \
  --setenv ALIGNC /tools/fresh-alignc --setenv ALIGN_LLM_BWRAP /tools/bwrap \
  --setenv ALIGN_LLM_PRLIMIT /tools/prlimit \
  --chdir /workspace \
  -- /tools/mount-guard --no-symlink-follow /target/tmp \
       --tmpfs-inodes / --tmpfs-inodes /target/tmp --prepare-validation-userns -- \
       /tools/make --silent --no-print-directory -j1 -f /workspace/Makefile capable-checks
```

The focused adoption argv uses the same `--clearenv`, namespace, staged runtime, temporary-root,
cache-off, Git-hardening, compiler, and mount-guard fields in the same order as the `ci` vector
above, with these exact mode-specific substitutions: it omits the `aggregate-work`, workspace-upper,
workspace-work, and `/fd-hold` overlay fields; it binds the retained immutable private project-source
descriptor read-only as `/workspace`; it does not pass `--prepare-validation-userns`; and its final
command is:

```text
/tools/mount-guard --no-symlink-follow /target/tmp --tmpfs-inodes / --tmpfs-inodes /target/tmp -- \
  /tools/make --silent --no-print-directory -j1 -f /workspace/Makefile \
  json-scan-row-ownership-adoption
```

The adoption vector therefore has no writable `/workspace` or aggregate overlay descriptor, and its
success proof applies the `adoption` output allowlist above. The implementation must exercise both
vectors from the same authenticated worker and verify that the omitted overlay and prepared-userns
objects are absent before the focused child starts.

The image manifest contributes regular staged copies from `/usr/bin/env`, `/usr/bin/python3.12`,
`/usr/bin/dash`, and `/usr/bin/bash` at the exact namespace paths `/usr/bin/env`, `/usr/bin/python3`,
`/bin/sh`, and `/bin/bash`. Thus `#!/usr/bin/env python3`, `#!/usr/bin/env bash`, and Make's
`SHELL=/bin/sh` cannot reach a host interpreter. `PATH=/tools` contains only the closed staged launchers. The
aggregate always sets `ALIGNC_CACHE=off`; the compiler code-generation cache is not an implicit
aggregate input and cannot create an unbounded cache under `/nonexistent`.
implementation must update `eval/runners/run-coding-task.py` so both `ALIGN_LLM_BWRAP` and
`ALIGN_LLM_PRLIMIT` are explicit fresh inputs; its current `/usr/bin/bwrap` and `/usr/bin/prlimit`
fallbacks are forbidden in the aggregate. Fresh mode also supplies `ALIGN_LLM_TOOL_ROOT=/tools`
and `ALIGN_LLM_PYTHON=/tools/python3`; `fixture_environment()` must set `PATH=/tools`,
`TMPDIR=/target/tmp`, and the worker-owned HOME contract rather than restoring `/usr/bin:/bin`
and `/tmp`. `validation_command()` must resolve a `python3` task command to the staged
`/tools/python3`, never to `sys.executable` or a host pathname.

A nested validation sandbox must make the staged execution boundary visible explicitly. The
aggregate's prepared user namespace is the only user namespace the nested bwrap may use: the
runner opens `ALIGN_LLM_VALIDATION_USERNS_PATH` with `O_RDONLY|O_CLOEXEC`, passes that descriptor
as `--userns <fd>`, and requests `--unshare-ipc --unshare-pid --unshare-net --unshare-uts`.
`--unshare-all` and `--unshare-user` are forbidden in this nested argv because they would attempt
to create a user namespace from the already-root aggregate and fail after the aggregate has done
its work. The same retained namespace descriptor is passed to the sandbox capability probe and to
both pre-repair and post-repair validation invocations; it is closed after the candidate is
complete. The bwrap process receives it through `pass_fds`, while the validation task and its
descendants receive no namespace descriptor or helper path.

The nested argv begins with `--cap-drop ALL --cap-add CAP_SYS_ADMIN --cap-add CAP_SETFCAP` in that
order, so the nested admission retains `CAP_SYS_ADMIN` for the staged `mount-guard` mount-attribute
operation and `CAP_SETFCAP` for its capability reduction. The guard
then reduces capabilities before `prlimit` or the validation task starts. Its remaining bwrap argv
includes `--dir /tools --ro-bind /tools /tools`, `--bind /target/tmp /target/tmp`,
`--size 67108864 --tmpfs /workspace`, `--size 67108864 --tmpfs /tmp`,
`--size 67108864 --tmpfs /dev/shm`,
`--setenv PATH /tools`, `--setenv TMPDIR /tmp`, `--setenv ALIGNC_CACHE off`,
`--setenv PYTHONHOME /usr`, `--setenv PYTHONNOUSERSITE 1`, and
`--setenv PYTHONDONTWRITEBYTECODE 1`, plus the same authenticated runtime mounts
needed by the staged tools. The two 67108864-byte mounts preserve the existing per-validation
quotas for `/workspace`, `/tmp`, and `/dev/shm`; `/target/tmp` remains the outer namespace-owned task checkout and
artifact scratch, not the validation process's temporary filesystem. The source of that bind is the
outer namespace tmpfs, never a host directory; the nested sandbox's staged `mount-guard` receives
the fixed mount list `/target/tmp /workspace /tmp /dev/shm`, applies `nr_inodes=65536` to the nested
tmpfs mounts `/`, `/workspace`, `/tmp`, and `/dev/shm`, and reapplies `MOUNT_ATTR_NOSYMFOLLOW` to all four
guarded mounts before the task starts. It invokes `/tools/prlimit` and `/tools/python3` by
explicit path. The nested environment repeats `PYTHONHOME=/usr`, `PYTHONNOUSERSITE=1`,
`PYTHONDONTWRITEBYTECODE=1`, and the three derived search-path variables. The outer Python process
starts that bwrap with `close_fds=True` and passes only the one prepared user-namespace descriptor;
no worker identity descriptor or helper-control descriptor crosses into the nested child. The
sandbox capability probe uses the same staged bwrap, Python, and mount-guard paths and the same
exact descriptor allowlist. Every fresh Python
subprocess boundary uses `close_fds=True, pass_fds=()` except the fresh coding-task sandbox probe
and its two validation invocations, which pass exactly the one prepared user-namespace descriptor
and no other descriptor. Compiler-capable children use the fixed `/tools/fresh-alignc` pathname and
open the read-only handoff files themselves. This applies to the shared `run()` helper and to
direct `subprocess.run` calls in `run-coding-task.py` and `record-baseline.py`; relying on a host
compiler, `sys.executable`, or an ambient path remains forbidden. No host `/tmp`, HOME, loader
cache, source root, or target is visible.

Before the aggregate starts, the worker creates `baseline-git/` as a private read-only Git view of
the project source. It copies, through retained project Git descriptors and no-follow operations,
the project `HEAD`, index, refs, packed refs, and the complete object database required to resolve
the project `HEAD`, recorded baseline source/oracle/finalization commits, and every requested
`merge-base`; it creates no host-path alternates, hooks, config includes, grafts, or replacement
refs. Before the copy, a descriptor-backed `rev-list --objects --all` scan requires the
authenticated object-format width and at most `fresh_git_object_max = 1000000` reachable object IDs.
The recursive copy itself admits at most `fresh_private_entry_max = 400000` directory/file entries
and `fresh_git_view_max_bytes = 4294967296` bytes, including loose objects, pack files, refs, and
metadata; a cap breach fails before the next file is copied. The copy is rehashed and rescanned,
then mounted read-only at `/baseline-git`. All normal
project Git calls, including the fixed eval corpus and the Align loop, use the aggregate's exact
values `GIT_DIR=/baseline-git`, `GIT_COMMON_DIR=/baseline-git`, and `GIT_WORK_TREE=/workspace`;
baseline callers additionally receive the worker-provided exact values
`ALIGN_LLM_BASELINE_GIT_DIR=/baseline-git`,
`ALIGN_LLM_BASELINE_GIT_COMMON_DIR=/baseline-git`, and
`ALIGN_LLM_BASELINE_GIT_WORK_TREE=/workspace`. The `git_environment()` helpers reject missing or
different fresh values, clear ambient `GIT_*`, and re-add only these private values alongside the
fixed `GIT_CONFIG_NOSYSTEM=1`, `GIT_ATTR_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`,
`GIT_NO_REPLACE_OBJECTS=1`, `GIT_GRAFT_FILE=/dev/null`, `GIT_NO_LAZY_FETCH=1`,
`GIT_OPTIONAL_LOCKS=0`, `XDG_CONFIG_HOME=/dev/null`, and `LC_ALL=C` hardening values. Thus normal
verification never resolves the hidden workspace `.git` entry or a linked-worktree common path.
Independent fixture repositories must clear the aggregate project values and provide their own
retained `GIT_DIR`/work tree before any fixture Git command; the static call-site test rejects an
unclassified direct Git invocation.

The invalid-baseline and replacement-ref smoke uses a second worker-owned private Git fixture under
`/target/tmp`, with the same private `GIT_DIR`/`GIT_COMMON_DIR`, `GIT_WORK_TREE=/workspace`, copied
`HEAD`/refs, and authenticated no-follow object copy. `GIT_ALTERNATE_OBJECT_DIRECTORIES` and every
other alternate-object channel are prohibited; the fixture never depends on a host or original
linked-worktree object path. The smoke script receives its explicit fixture values before any
`git update-ref`; `GIT_NAMESPACE` alone is insufficient because it would still mutate a shared
common directory. The worker postscan proves that project source-control paths remain unchanged and
that both private Git views are removed during cleanup. No host baseline or sibling Align repository
is visible to the aggregate.

The `ci` child Make vector clears `MAKEFLAGS`, `GNUMAKEFLAGS`, and `MAKEOVERRIDES`, supplies
`SHELL=/bin/sh`, fixes `-f /workspace/Makefile`, and passes only the ordered `capable-checks` goal.
The `adoption` child vector uses the same cleared control variables and fixed Makefile, but passes
only `json-scan-row-ownership-adoption` and runs without an aggregate overlay or prepared validation
user namespace. The worker owns one mode-specific process tree; it does not launch a second host
aggregate. The aggregate plus any focused goal, aggregate plus aggregate, adoption plus any other
goal, or direct compiler call with an incompatible fd set is rejected by the parse and identity
fixtures before an output marker can run.

### 9.8 Process ownership, status, and cleanup

The worker enables Linux child-subreaper mode before its first child, starts each probe, build bwrap,
aggregate bwrap, and identity check in a new session, and retains pid start time, parent relation,
process-group identity, and every worker-owned fd identity. It drains stdout and stderr concurrently in
8,192-byte chunks and retains at most 65,536 bytes per phase stream. Probe streams are compared to
the manifest before the next probe; build and aggregate bytes are internal diagnostics only. The
worker uses monotonic deadlines of 5 seconds per probe, 120 seconds for validation/materialization,
1,800 seconds for build and aggregate, 1 second TERM grace, 5 seconds KILL/reap, and 30 seconds
cleanup. Signal handlers convert `SIGINT`, `SIGTERM`, and `SIGHUP` to one cancellation path.

The image/profile exposes one delegated cgroup-v2 parent at
`/sys/fs/cgroup/align-llm-fresh/<uid>`. Before root creation the worker verifies that the parent is
on the expected cgroup-v2 mount, has the recorded device/inode and delegation, is writable only by
the effective uid, has no unknown `align-llm-fresh-*` child, and has the required controllers. The
parent path is fixed profile state, not an environment or command-line input. Before each child
`execve`, the worker creates a fresh leaf named `align-llm-fresh-<32 lowercase random hex>` under
that parent, records the parent/leaf device and inode, requires empty `cgroup.procs` and
`cgroup.threads`, writes `pids.max=512`, and attaches only the just-created child after fork. The
child and its descendants inherit that leaf; no worker or unrelated process is attached. A changed
parent, pre-existing leaf, failed empty-membership proof, leaf replacement, or failed attach is a
`PLATFORM` failure before the real command starts.

The worker applies hard and soft `RLIMIT_NPROC=512`, `RLIMIT_NOFILE=4096`, and
`RLIMIT_FSIZE=536870912` before `execve`, and verifies the exact values and cgroup membership from
the child side before the command is admitted. A child write past `RLIMIT_FSIZE` fails with the
kernel file-size-limit result and is classified at the owning phase (`BUILD`/`aggregate`); it does
not override the smaller generated-`main`, tmpfs, overlay, or root-byte bounds. Failure to configure
or verify a cgroup or rlimit is a `PLATFORM` failure before child side effects.

After every normal exit, timeout, or signal, the worker terminates and reaps the owned process tree,
waits for the leaf's `cgroup.procs` and `cgroup.threads` to become empty, rechecks the parent/leaf
identity, and removes only that empty leaf. A nonempty, replaced, or unprovable leaf is never
removed and produces the documented cleanup failure. The delegated parent is an exclusive
worker/profile writer boundary for this lifecycle; a non-cooperating same-UID writer is outside
the profile threat model. An uncatchable worker death leaves the unique
leaf for the bounded orphan policy; the next invocation fails closed before creating a root until a
separately supervised profile cleanup proves the leaf empty and removes it. The worker's own fd table
is checked before root creation, after every descriptor handoff, and before cleanup.
The subreaper samples descendant count and every owned `/proc/<pid>/fd` directory at each deadline
tick; a process, open-fd, or private-entry cap-plus-one is terminated and reported before another
child is admitted. These controls are part of the platform profile, not optional tuning; the platform
probe rejects an undelegated or writable-by-another-uid cgroup.

On every catchable exit the worker terminates owned descendants, waits for pid start time and
process-group identity, waits for the aggregate bwrap to release its overlay mount, closes readers
and handoff files, removes the one known overlayfs work entry with descriptor-relative no-follow
operations, rescans the private root, and removes only known children. The overlay upper and work
directories are inspected before removal: the worker accepts only the declared final `main` output
and the exact known `work` directory state, and never recursively deletes an upper or work entry it
cannot classify. Before removing the random root name it
rechecks the parent descriptor, root device/inode, owner token, and empty child set. It restores
staging directory write authority (which remains `0700` throughout) and moves each expected child
through the unique worker-owned quarantine with `renameat2(RENAME_NOREPLACE)` before deleting it.
The moved descriptor is compared with the retained expected identity; an unexpected entry,
replacement, live child, PID reuse, parent change, or close/quarantine failure leaves the path and
records cleanup failure. It never recursively follows or directly deletes a mutable source name
or an unowned path.

An uncatchable worker death—`SIGKILL`, an OOM kill, kernel termination, or equivalent loss of the
worker before its cleanup path runs—is an explicit `UNOBSERVED_EXIT` exception: the killed process
cannot emit status, reap descendants, rescan, or remove its private root. The worker-owned protected
lock descriptor is released by the kernel, but the protected per-user root grammar and admission scan
make the resource policy fail closed: a later invocation performs only a bounded name-existence scan, returns
`fresh compiler: ERROR FILESYSTEM filesystem\n`, and creates no second root while any candidate
exists. It must never classify, read, or delete a candidate based only on a token or worker identity
stored inside that directory. Unknown names, live identities, changed parent/root identity, or an
unclassifiable child are all left untouched. Because at most one root can exist and its total size,
entry, process, descriptor, cache, and tmpfs dimensions are fixed above, repeated uncatchable deaths
cannot accumulate an unbounded set of roots. Manual or separately supervised reclamation is outside
this profile and cannot run as part of `make ci`. The SIGKILL fixture kills the worker after root
creation, proves that the live root is not deleted by an unrelated process or a later invocation,
proves the next invocation fails before root creation, and records the root for external cleanup; no
contract promises automatic or immediate cleanup after an uncatchable death.

Cleanup is part of the public status decision. The worker emits no success line until cleanup has
proved the root absent. A successful phase followed by cleanup failure returns exit 1, empty stdout,
and exactly `fresh compiler: ERROR CLEANUP cleanup\n`. A failed primary phase emits its exact
`fresh compiler: ERROR <CATEGORY> <PHASE>\n` line; if cleanup also fails, the cleanup line follows
it. A successful phase and successful cleanup alone returns the mode-specific PASS line. This
precedence is tested for every phase and catchable signal boundary. An uncatchable death has no
status line; its orphan-root behavior is covered by the next-invocation sweep fixture.

### 9.9 Validation order and failure categories

The first applicable failure wins in this fixed order. `supervisor` is evaluated by the image-owned
pre-bootstrap entrypoint before any repository-controlled Make process; it is included in the public
grammar so a trust failure has one deterministic status even though no worker root exists.

1. image supervisor and both signed attestation descriptors;
2. bootstrap mode, required input names, rejected caller manifest path/digest overrides, and ASCII/UTF-8 encoding;
3. image-attested manifest snapshot, schema, canonical order, and bounds;
4. fixed bootstrap, Python, Linux, architecture, `/proc`, and timer capabilities, followed by
   bwrap descriptor authentication and retention; no bwrap child runs in this phase;
5. namespace, overlay, no-symlink-mount, and read-only `/tools` capability probes using the retained
   bwrap descriptor, then no-follow controller-path component checks, bounded regular-file worker
   snapshot, and every other retained tool descriptor, digest, mode, version, and probe output;
6. project-root Git descriptors and policy, raw project tree/index/worktree and its root `.git`,
   `main`, and `target` output/control exceptions, then the exact `.align-revision`, retained
   `ALIGN_REPO` Git descriptors and policy, SHA-1-only pinned Align `HEAD`/tree/index/worktree, its
   root `.git` control entry, its root `target` output exception, and the exact tracked
   `.cargo/config.toml` snapshot and key set;
7. cache root, external cache manifest, digest tree, allowlist, count/size bounds, and retained
   cache descriptors; no destination copy;
8. private root admission lock, pending-root fail-closed scan, project/Align source, runtime/tool/cache, and baseline-Git materialization from
   retained inputs, post-copy proofs, and aggregate-work construction;
9. build namespace, Cargo result using the accepted phase-5 Cargo-configuration snapshot, ELF
   runtime closure, and compiler/runtime-archive sibling bundle;
10. descriptor/guard handoff files, launcher identity, aggregate namespace, child output, and
   aggregate result;
11. reverse cleanup and final root-absence proof.

The primary line is exactly `fresh compiler: ERROR <CATEGORY> <PHASE>\n`, where `CATEGORY` is one of
`ARGUMENT`, `TRUST`, `PLATFORM`, `TOOL`, `SOURCE`, `CACHE`, `FILESYSTEM`, `BUILD`, `COMPILER`,
`CHILD`, or `INTERNAL`, and `PHASE` is one of `supervisor`, `input`, `manifest`, `platform`, `bwrap`,
`tools`, `project-source`, `align-source`, `cache`, `concurrency`, `filesystem`, `build`, `compiler`,
`aggregate`, or `internal`. The cleanup line is exactly `fresh compiler: ERROR CLEANUP cleanup\n`. These are the
complete phase identifiers, not placeholders for paths or free-form diagnostics. Diagnostics never
contain environment values, compiler output, credentials, or source bytes. No later phase overwrites
a primary category or phase. If a caller manifest override and an invalid image-attestation descriptor
are supplied together, phase `input` wins and the result is exactly
`fresh compiler: ERROR ARGUMENT input\n`; the image descriptor is not opened first.

The category for each primary phase is fixed rather than selected by an implementation detail:
`supervisor` and `manifest` map to `TRUST`, `input` to `ARGUMENT`, `platform` and `concurrency` to
`PLATFORM`, `bwrap` to `TRUST`, `tools` to `TOOL`, both source phases to `SOURCE`, `cache` to
`CACHE`, `filesystem` to `FILESYSTEM`, `build` to `BUILD`, `compiler` to `COMPILER`, `aggregate`
to `CHILD`, and `internal` to `INTERNAL`. A malformed or mismatched value is therefore reported at
the first phase that owns its validation, with no path, errno, or free-form subcategory appended to
the public line.

### 9.10 Closure matrix

| Path | Owner | Required invariant | Exact regression |
| --- | --- | --- | --- |
| Ordinary native-parent continuity | native `fresh-supervise`, image preflight, and dispatcher | In `ordinary-adoption`, the native `fresh-supervise` ELF remains the direct parent of the dispatcher for the complete admission and worker lifetime. It does not `execve` the Python carrier before dispatch, and a Python interpreter digest or reconstructed command line is never accepted as a supervisor identity. Before creating the ordinary channel, the native supervisor performs only image-owned preflight through a short-lived embedded-control child, captures bounded empty output, and requires its successful return; the preflight child may not open the repository, create a channel, sign a capsule, or launch a worker. The native supervisor then creates the sealed image/manifest/nonce descriptors, walks and retains FD 18, opens the retained FD 14 dispatcher, creates the one channel, forks exactly one dispatcher child, and sends the ticket. The dispatcher authenticates `/proc/<pid>/exe` and the exact native `fresh-supervise\\0--mode\\0ordinary-adoption\\0` command line, with the stable peer start-time check, before receiving the ticket. Legacy modes may continue to use the Python carrier because they have no ordinary parent-authentication contract. | `run-fresh-image-profile-smoke` proves the ordinary child parent is the native supervisor at the `/proc/<pid>/exe` and cmdline boundary, the preflight child cannot reach a repository marker or create a channel, a Python carrier/direct dispatcher/caller-created channel is rejected, and the native parent remains alive through capsule digest, proof, bwrap, helper, and final cleanup. |
| Ordinary admission proof and liveness | supervisor, dispatcher, worker, and namespace helper | The supervisor opens `/` as temporary FD 17, component-walks and retains `ALIGN_REPO` as FD 18 before channel creation, closes FD 17, creates one `SOCK_SEQPACKET|SOCK_CLOEXEC` channel, and forks exactly one dispatcher child. The supervisor sends exactly one fresh ticket `T`; the dispatcher authenticates the current-parent peer and stable start-time/image/cmdline using the controlled procfs executable rule, receives `T`, signs the capsule, and sends exactly one 32-byte capsule digest `C`; the supervisor receives `C` and replies with exactly one queued 32-byte `P = SHA-256("align-llm/ordinary-adoption/worker-admission/v2\0" || dispatch_ticket_sha256_bytes || invocation_nonce_bytes || C)`. The dispatcher passes FD 16 and FD 18 to the worker after explicitly clearing `FD_CLOEXEC` with `pass_fds=(4,12,13,15,16,18)`; the worker peeks without consuming, verifies the outer peer before bwrap, closes FD 18 after source validation, and bwrap retains FD 16 with the exact `--as-pid-1 --sync-fd 16` vector. The PID-1 helper consumes the proof before any Make child and checks only channel HUP/EOF/protocol liveness because outer PIDs and procfs entries are not visible in its private PID namespace. The parent stays alive until helper exit; extra, missing, or mismatched messages fail closed with the exact owning phase. | `run-json-scan-row-ownership-adoption-smoke` covers direct-dispatcher admission, stale ticket/capsule/nonce/exception replay, proof mismatch, missing/extra proof, FD_CLOEXEC loss at both exec edges, parent death before/after proof, channel endpoint replacement, HUP during setup and each child row, outer-PID invisibility, IPC markers with and without `--unshare-ipc`, controlled `/proc/<pid>/exe` replacement/exec races, and exact proof consumption before the first Make marker. |
| Absolute sibling path admission | supervisor and dispatcher | `ALIGN_REPO` is lexically validated and walked by the trusted supervisor from a retained `/` descriptor FD 17 before channel creation and FD 14 dispatch, component-by-component with `openat(O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)` and before/after `fstatat(AT_SYMLINK_NOFOLLOW)` identity checks. The final retained descriptor is passed as FD 18 and FD 17 is closed before the child is forked; the dispatcher only rechecks FD 18 identity and uses it for all later Git/copy work. No intermediate or final symlink, replacement, or pathname reopen is accepted. | `run-json-scan-row-ownership-adoption-smoke` replaces every intermediate and final component with a symlink, FIFO, directory, or same-identity rename race and proves `fresh compiler: ERROR TRUST supervisor\n` before FD 14 dispatch; it also replaces FD 18 after dispatch and proves the ordinary `revision` result before capsule signing or staging. |
| Ordinary source-exception and raw-tree wire | dispatcher and worker | Request 6 uses `raw-tree/v1` plus the separate `source-exception/v2` vector; both project and Align root `HANDOFF.md` are control exceptions, project `main` is optional, Align `main` is absent, present handoff rows carry a bounded content digest, Git rows use `link_count=null` by retained-descriptor policy, and no exception bytes enter `raw-tree/v1` entries or digest. The raw-tree and exception semantic-to-byte goldens are `8b30014d36e10e32e230fcbbcbe12b6933903da48c8569140cadd62795caad77` and `0c685027b378e6ef448e8efd807532eb8f056de04f550e884d56a5ef0834ead0`. The complete exception digest is signed as `source_exception_sha256` in `ordinary-adoption/v2`; legacy source-manifest/v1 remains unchanged. | `run-json-scan-row-ownership-adoption-smoke` and `raw-tree-v1-output-exception-golden` cover present/absent rows, exact type/mode/link-count/content-digest metadata, exception-only mutation invariance, tracked/symlinked/wrong-type/wrong-mode/wrong-link-count negatives, handoff-content mutation, and independent semantic-to-byte/byte-to-semantic round trips. |
| Ordinary error phase grammar | dispatcher, worker, and namespace helper | The closed phase set is `input`, `toolchain`, `revision`, `build`, `fixture`, and `cleanup`; each validation, channel, staging, row, and cleanup failure has the exact mapping and first-failure precedence recorded in Request 6, while pre-FD-14 failure remains `TRUST supervisor`. Every post-FD-14 authority, offset, bind, proof, bwrap, namespace, and infrastructure failure is `toolchain`; project/Align/worker content or identity is `revision`; malformed public argv/env is `input`; a supervisor hangup maps to `toolchain` before the first child, the active row's phase while a row runs, and `cleanup` during reverse cleanup. A worker signal death or unknown exit status before a final phase result is the explicit terminal `UNOBSERVED_EXIT` outcome `json-scan adoption: ERROR unobserved\n`, not a phase. | `run-json-scan-row-ownership-adoption-smoke` injects every pre-dispatch, post-dispatch, source, authority, toolchain, capsule, path, channel, child, timeout, cancellation, cleanup, and uncatchable worker-death failure at each ordering point and compares exact stdout/stderr bytes, the `UNOBSERVED_EXIT` exception, and primary-phase precedence. |
| Ordinary worker exit observation | dispatcher and worker | The dispatcher remains the direct parent/monitor of the sealed worker child and owns the public stream. Worker exit status `0` is success; fixed statuses `1..6` map in order to `input`, `toolchain`, `revision`, `build`, `fixture`, and `cleanup`. A signal or any other status before a final phase result maps to `UNOBSERVED_EXIT`; the dispatcher emits exactly one `json-scan adoption: ERROR unobserved\n` after its safe outer cleanup. The helper and Make children never emit public status bytes. | `run-json-scan-row-ownership-adoption-smoke` kills the worker at each pre-phase and active-row boundary, supplies unknown exit statuses, proves no child stream escapes, and checks the exact `unobserved` result and cleanup ordering. |
| Runner-image trust boundary | image supervisor plus fixed bootstrap | Verify the signed image DSSE predicate against the pinned raw Ed25519 key, bind the immutable OCI digest to supervisor/bootstrap/manifest digests, pass the sealed image attestation at fd 6, and reject before any repository child | `fresh-v2-image-trust-smoke` mutates/replays the image, supervisor, bootstrap, manifest, attestation, and descriptor presence; the supervisor/bootstrap boundary rejects before private-root creation and records the complete image/verifier tuple. |
| Legacy per-invocation trust boundary | image supervisor plus fixed bootstrap and worker | For legacy `ci`, fresh `adoption`, `build`, and `self-test`, before signing, the supervisor opens the worker through no-follow descriptors, requires euid-owned single-link regular `0755` bytes at or below `fresh_worker_max_bytes = 4194304`, performs a bounded exact read and post-read identity check, and binds that digest plus the retained project head/object format and canonical `ALIGN_REPO` relative path into a distinct signed run-capsule DSSE predicate; the bootstrap repeats the worker checks, passes the sealed capsule at fd 5, snapshots it at fd 9, and requires the worker's observed project/sibling identities to equal the capsule before source acceptance | `fresh-v2-run-attestation-smoke` changes the checkout head, worker bytes, object format, canonical sibling path, parent-side `ALIGN_REPO`, run signature, key ID, image-attestation digest, and manifest digest; FIFO, directory, symlink, oversized, short-read, replacement, and deadline cases reject before capsule signing or root creation, and every mismatch rejects before the source manifest is accepted. |
| Pre-dispatch repository boundary | image supervisor plus bootstrap | Accept the logical request vector but dispatch only the image-owned bootstrap; no repository `Makefile`, tracked or untracked `GNUmakefile`/`makefile`, dirty tracked input, or repository Make process is parsed or executed from the retained root before source validation and private materialization. The supervisor and bootstrap both use bounded no-follow worker descriptors; the worker is read only as the bounded authenticated snapshot named by the run capsule. | `fresh-v2-pre-dispatch-source-smoke` plants tracked and untracked `GNUmakefile`/`makefile` alternates, mutates the retained `Makefile`, replaces the worker with a symlink/FIFO/directory/oversized file, and proves the supervisor launches only the fixed bootstrap and the worker rejects each source/worker fault before any private root or repository Make process. |
| Bootstrap snapshot | fixed bootstrap | Exact fd map: supervisor passes project root/run/image at 4/5/6; bootstrap opens `scripts` and `fresh-align-compiler` with no-follow descriptors, requires an euid-owned single-link regular `0755` file at or below `fresh_worker_max_bytes = 4194304`, verifies identity before and after a bounded read, seals worker/manifest/run snapshots at 7/8/9, clears only 4/7/8/9, passes the admitted mode in the fixed Python vector, and starts no repository child before all snapshots | `fresh-v2-bootstrap-snapshot-smoke` overwrites/truncates the worker, mutates the fixed manifest, changes the run capsule, injects both manifest environment overrides, exercises symlink/FIFO/directory/oversize/replacement workers and cap-plus-one reads, and proves descriptors 4/7/8/9 retain the authenticated bytes while 5/6 never reach the worker. |
| Attestation wire | image supervisor plus verifier | Exact DSSE envelope/predicate field order, schema/types/digest algorithms, Ed25519 key-id and key-digest policy, PAE lengths, base64url form, and independent golden bytes | `fresh-v2-attestation-wire-golden` checks both predicate and PAE hashes, payload decoding, key selection, signature verification, duplicate/unknown/padded input rejection, and deployment-key separation. |
| Manifest wire | bootstrap/worker | Schema 2 order, mode strings, ordinary and probe-byte string bounds, duplicate/unknown rejection, fixed image paths, and image-attested digest; controller path/API only, with worker digest owned by the run capsule | `fresh-v2-manifest-format-smoke` covers every scalar, order, mode, UTF-8, NUL, ordinary-string size, empty/binary/exact-cap/cap-plus-one probe streams, fixed-path replacement, and rejected caller-digest case. |
| Digest tree and cache wire | worker | Exact file/dir schema with raw/staged modes, structural hash, canonical JSON hash, raw-byte order, schema-2 cache manifest, and the five fixed Cargo prefixes | `fresh-v2-digest-tree-golden` checks the runtime `abc` vector; `fresh-v2-cache-manifest-golden` checks the nested `registry/index/a` bytes, allowed-prefix array, all digests, mode mapping, count, total, and malformed or out-of-prefix cache manifests. |
| Source-manifest wire | worker | Legacy schema-1 source identity bytes remain unchanged: object-format field, raw-byte path encoding/order, raw `.git/index` preimage including extensions/checksum, explicit root Git-control exception, Git tree/blob objects for directory/file/symlink in both SHA-1 and SHA-256 formats, raw/staged modes including `null` symlink modes, both root target exceptions, and descriptor digest; the project source may use either object format but the Align source is SHA-1-only in this profile. Ordinary Request 6 uses the separate `raw-tree/v1` and `source-exception/v2` wires, whose complete exception identity is carried by `ordinary-adoption/v2.source_exception_sha256`; it does not alter schema-1 readers. | `fresh-v2-source-manifest-golden`, `fresh-v2-source-manifest-symlink-golden`, and `fresh-v2-source-manifest-object-format-golden` independently recompute the unchanged schema-1 bytes; `raw-tree-v1-golden` and the Request 6 exception golden independently recompute `8b30014d36e10e32e230fcbbcbe12b6933903da48c8569140cadd62795caad77` and `0c685027b378e6ef448e8efd807532eb8f056de04f550e884d56a5ef0834ead0`, including semantic-to-byte and byte-to-semantic negatives for `.git`, both `HANDOFF.md` control rows, raw order, invalid paths, and symlink targets. `fresh-v2-source-identity-smoke` rejects a SHA-256 Align pin before source acceptance. |
| Bwrap trust and capability probe | worker | Authenticate and retain the exact image-owned `/usr/bin/bwrap` binding at FD 27 before any bwrap execution; the worker remains the outer owner, forks one launcher child, and that child invokes FD 27 with `execveat(AT_EMPTY_PATH)`, so successful exec closes FD 27 through its construction `FD_CLOEXEC` flag and bwrap/helper never receive it or list it in a Python `pass_fds` tuple; require and exercise descriptor-backed read-only/writable binds plus overlay support, `--as-pid-1 --sync-fd 16`, `--unshare-ipc`, run every platform probe from that descriptor, and reject mutable-path replacement. Every post-FD-14 launcher/bind/platform failure maps to `toolchain`; pre-dispatch image failure remains `TRUST supervisor`. | `fresh-v2-bwrap-trust-smoke` injects caller manifest overrides, mutates the fixed image manifest and bwrap sources before and during descriptor-bind, namespace, overlay, no-symlink, IPC-isolation, and read-only-tools probes, proves FD 27 survives only to the immediate exec edge, exercises `--sync-fd` with and without `--as-pid-1`, and requires the retained bytes or the exact `toolchain`/`TRUST` rejection before private-root creation. |
| Tool identity | worker | Canonical no-symlink host path, retained no-follow descriptor, full hash, probe from retained bytes, copied private bytes, exact probe | `fresh-v2-tool-identity-smoke` covers symlink aliases, replacement after open, version, timeout, overflow, unlisted names, retained-descriptor execution, and copied-byte mutation. |
| Runtime/loader/Python/compiler identity | worker plus bwrap | Complete ELF interpreter/DT_NEEDED closure for staged tools and generated `main`, authenticated derived linker/loader/pkg-config paths, stable installed-runtime hardlinks with complete before/copy byte proof, actual ordinal staging paths, CPython stdlib and `lib-dynload` trees, the self-contained `/runtime/cc-suite` driver/helper/resource/header closure, executable runtime modes 0555 versus data modes 0444, and no Python bytecode writes or host import | `fresh-v2-runtime-closure-smoke` replaces a library, interpreter, stdlib module, native extension, compiler-suite helper/resource/header, and product dependency, checks stable runtime-hardlink admission while cache hardlinks still reject, checks build and aggregate, proves identical structural library-tree and file aliases collapse in first-manifest order while byte-distinct aliases remain ambiguous, proves derived paths and final-output closure, proves descriptor paths name the copied ordinal object, rejects host GCC fallback/marker helpers, and proves no `__pycache__` or host path appears. |
| Cache placement/copy | worker | External manifest outside root with canonical schema-2 digest, exact five-prefix allowlist, semantically correct non-root count, pre-copy per-file/total bounds, retained source descriptors, directory-aware no-follow/nonblocking copy, complete descriptor-relative pre/post tree snapshot (names, types, modes, symlink targets, file sizes/digests, and directory metadata), raw/staged mode proof, destination rehash, and postscan | `fresh-v2-cache-smoke` covers manifest-in-root, malformed wire, the corrected three-node `registry/index/a` golden, every out-of-prefix config/wrapper case, symlink, FIFO/special-file races that must fail without blocking, hardlink, rename, 512-MiB file and 20-GiB total limits, raw/staged mode mismatch, digest, offline cases, and deterministic add/replace plus same-size post-write mutations after enumeration and during recursion. |
| Git/source identity | worker | Separate retained project and `ALIGN_REPO` worktree/Git/common descriptors, scan-capable no-follow reopen from each admitted `O_PATH` root, worker-owned procfs paths that survive Git closing inherited descriptors, project `HEAD`/object-format equality with the signed run capsule before source acceptance, exact SHA-1-only Align pin HEAD/tree/index/clean-worktree proof, explicit root `.git` control exclusion, raw-byte normalization of Git tree order, both raw manifests and exception metadata, raw-to-staged mode mapping, descriptor-relative copies with post-copy proof, fixed tracked Cargo config policy, no helper/config/filter | `fresh-v2-source-identity-smoke` covers `O_PATH` admission, a directory/file-name pair whose Git order differs from raw-byte order, ordinary and linked-worktree roots, root `.git` file/directory handling, common-directory replacement, ancestor ABA, project run-capsule-head mismatch, sibling SHA-1/SHA-256 pin and dirty-tree rejection, source replacement during copy, replacement refs, hidden inputs, contained symlinks, project `main`, both root `target` exceptions, exact `.cargo/config.toml`, mode normalization, and same-HEAD extra Rust input. The separate `raw-tree-v1-output-exception-golden` covers handoff content digests, exception metadata, and proves no exception bytes enter `entries`. |
| Private staging | worker plus admission lock | 0700 owner-only `project-source`, `align-source`, and baseline Git view; fixed source/tool/runtime/Git byte, entry, depth, inode, object, descriptor, process, root-byte, and overflow bounds; bounded source descriptor window with re-opened parent identity checks; root-relative no-follow mount descriptors consumed by bwrap fd-bind or self-fd overlay operations; pre-created build `/target/tmp` and `cargo-target/fresh-bundle`, namespace-owned aggregate tmpfs, same-filesystem overlay upper/work, descriptor-relative quarantine cleanup using `renameat2(RENAME_NOREPLACE)`, profile-owned protected per-user `roots` parent, and one-root-per-user admission | `fresh-v2-root-staging-smoke` covers protected-parent collisions, executable-bit preservation, every cap and cap-plus-one/overflow case, mixed 200,000-entry source fd-window exhaustion, directory replacement, symlink target replacement, both source copies, baseline Git copy, modes, target seed, compiler-output hardlink materialization, aggregate tmpfs/no-follow mount, upper/work ownership, known overlay `work` cleanup, output escape, overlay unmount, and cleanup quarantine replacement/identity cases. |
| Aggregate temporary call sites | scripts and Align loop | Every aggregate temporary file, fixture, marker, and negative Git state is below the no-symlink `/target/tmp`; the loop no longer writes `eval/`, and no host temp directory is aggregate-visible. Each nested coding-task validation retains independent `--size 67108864 --tmpfs /tmp` and `--size 67108864 --tmpfs /dev/shm` mounts, while `/target/tmp` remains outer task scratch. | `fresh-v2-temp-root-callsite-smoke` runs loop, coding-task, invalid-baseline, and every `mktemp`/`TemporaryDirectory` caller, exercises both nested 64 MiB mounts and `/dev/shm` smoke coverage, attempts a temp-to-workspace symlink, and proves no lower or upper source path changed. |
| Aggregate publication | worker plus bwrap | Immutable `aggregate-work` lower layer, writable upper/work pair, atomic rename, exact regular `main` mode/link-count/size/ELF/byte identity, generated-output and dependency-graph bounds, exact overlayfs internal-work cleanup state, and final `/workspace/main` allowlist | `fresh-v2-aggregate-publication-smoke` runs the real compiler publication path, proves `.align-publish-*` is transient, rejects an upper entry outside `main`, rejects an unknown workdir entry, mutates a declared product dependency, injects mode/link/size/hash changes after unmount, and checks the post-unmount output closure and scan. |
| Nested validation user namespace | aggregate mount-guard plus coding-task runner | Before Make loses `CAP_SETUID`/`CAP_SETGID`, exactly one descendant user namespace is created with `setgroups=deny` and maps `0 0 1`; its proc namespace path is private to the aggregate, inherited only through the documented environment lookup, opened as one `O_CLOEXEC` descriptor, passed to nested bwrap with explicit non-user namespace flags, reused for both validation runs, and closed on success or every failure path; helper death follows the aggregate parent and no helper or namespace descriptor reaches the validation task | `fresh-v2-aggregate-topology-smoke`, `fresh-v2-interpreter-boundary-smoke`, and `run-coding-task-invalid-smoke` cover aggregate capability admission, prepared-userns bwrap argv and descriptor allowlist, missing/probe-failure fail-closed behavior, and validation-run cleanup. |
| Build namespace | worker plus bwrap | Empty root, authenticated pinned `/align-src` only, no project source or host `ALIGN_REPO`, user/PID/net namespaces, read-only authenticated `/cargo`, tracked Cargo config policy, derived linker/loader/pkg-config paths, compiler closure, and writable `/target` only | `fresh-v2-build-namespace-smoke` uses host-root/cache/HOME/network/project-source/sibling-target markers, attempts a Cargo-cache write, verifies `/align-src/Cargo.toml` and the exact `.cargo/config.toml` digest/key set, checks derived OpenSSL/linker paths and compiler closure, double fork, and runtime loader probes. |
| Compiler descriptor | worker/launcher | Canonical schema 4 with separate project/Align source digests, write-once descriptor/guard files, authenticated single-link compiler/archive sibling bundle at `/tools/alignc` and `/tools/libalign_runtime.a` plus the `/tools/fresh-alignc` launcher, fixed read-only execution path, exact digest and revision, and no inherited identity fd | `fresh-v2-descriptor-file-smoke` replaces each source path after staging, mutates or makes the private handoff files writable, attempts alternate descriptor paths and compiler/archive names, proves Cargo hardlinks are materialized before descriptor publication, proves non-validation children use `pass_fds=()` while the coding-task boundary receives only its prepared user-namespace fd, compiles a tiny Align program through the namespace-visible launcher/compiler/archive bundle, and checks exact descriptor-v4 golden bytes. |
| Direct compiler call | fresh launcher | Execution is only the launcher-verified `/tools/alignc` path with its authenticated descriptor/guard and sibling archive; no flag-controlled, PATH, host, or old fallback. Request 6's fresh profile uses the same launcher and fixed `ALIGNC_CACHE=off` value. | `fresh-v2-direct-interposition-smoke` clears every fresh marker and installs old sibling/PATH marker compilers, replaces the private handoff files and bundle, and requires none to run while a tiny link proves `libalign_runtime.a` is found beside `current_exe()`; the Request 6 adoption smoke proves its `check` and `run` vectors use `/tools/fresh-alignc`. |
| Focused adoption request | supervisor/worker/Makefile plus Request 6 smoke | Admit only `make --no-print-directory json-scan-row-ownership-adoption`, map it to `adoption`, run only the fixed `json-scan-row-ownership-adoption` goal from the private `/workspace/Makefile`, preserve the same authenticated source/runtime/cache/process/tmpfs/cleanup boundary as `ci`, force `ALIGNC_CACHE=off` and `/tools/fresh-alignc`, publish no `/workspace/main`, and keep the target outside every routine aggregate | `fresh-v2-focused-adoption-request-smoke` exercises exact request admission and rejection before side effects, mode/argv/env/fd mapping, source mutation/FIFO/symlink/worker snapshot failures, fixed target and no-aggregate membership, cache-off/compiler identity, exact PASS/error bytes, cleanup and signal/timeout paths; `run-json-scan-row-ownership-adoption-smoke` proves the Copy-row diagnostic, fixed optional-schema outcome, ordinary decode, fixture preflight, fixed file order, cache closure, and ordinary/fresh vectors. |
| Ordinary public-entrypoint trust boundary | trusted `fresh-supervise` plus Request 6 dispatcher | The only evidence-bearing host command is a trusted runner's direct kernel `execve` of `/usr/local/libexec/align-llm/fresh-supervise --mode ordinary-adoption` with exactly `PATH`, `LC_ALL`, `LANG`, `HOME`, `TMPDIR`, and the required absolute `ALIGN_REPO`; no shell or `/usr/bin/env` runs before the image-owned supervisor. The supervisor authenticates the runner-image envelope and fixed schema-2 manifest, opens `/usr/local/libexec/align-llm/request6-adoption-entrypoint` through a retained no-follow descriptor, verifies its complete closure and digest, lexically validates and component-walks the absolute Align path before channel creation, retains FD 18, creates sealed nonce FD 15 and a connected channel, forks exactly one dispatcher child, passes the child endpoint as FD 16 plus FD 18, sends one fresh one-time ticket, and remains alive until the child exits. Only the child invokes FD 14 with `execveat(AT_EMPTY_PATH)`, including `argv[0] = request6-adoption-entrypoint` and only fds 4/6/8/15/16/18. The dispatcher authenticates its current-parent channel peer, stable PID start-time, the controlled procfs magic-link executable digest, exact supervisor command line, ticket, and retained FD 18 before any capsule signing; a direct dispatcher path, caller-created socket, or caller-created ticket is rejected. Direct repository-script paths are also untrusted developer checks. The dispatcher then authenticates the current project HEAD/index/raw-tree/exception identity and canonical `ALIGN_REPO` sibling, reads the repository worker as bounded no-follow data, and binds its digest, project identities, source-exception digest, request/API, nonce, dispatch-ticket digest, image digest, image-attestation digest, manifest digest, and dispatcher digest into a signed `ordinary-adoption/v2` capsule. | `run-json-scan-row-ownership-adoption-smoke` replaces or edits the supervisor, dispatcher, worker, project HEAD, raw tree, index, sibling, channel peer, channel endpoint, retained FD 18, or nonce before and after dispatch/capsule creation; exercises symlink/FIFO/directory/oversize/short-read/replacement worker cases, outer-PID invisibility, controlled `/proc/<pid>/exe` replacement/exec races, and bwrap FD27 fork/exec; replays or edits capsule fields/signature/image tuple or reuses a prior nonce/ticket/exception vector; supplies missing/wrong-peer/wrong-argv0 channels; and proves no repository worker, Make, or compiler marker occurs before the authenticated supervisor channel, dispatcher, and worker boundaries. |
| Ordinary adoption capsule wire | image dispatcher, profile signer/verifier, `adoption-namespace` | Existing Section 9 DSSE framing and image key policy with predicate `https://align-llm.dev/attestations/ordinary-adoption/v2`; canonical payload order is `api`, `request`, `invocation_nonce`, `dispatch_ticket_sha256`, `project_head`, `project_object_format`, `project_index_sha256`, `project_raw_tree_sha256`, `source_exception_sha256`, `align_head`, `align_object_format`, `align_repo_relative`, `worker_relative`, `worker_size`, `worker_sha256`, `image_digest`, `image_attestation_sha256`, `manifest_sha256`, `entrypoint_sha256`; FD 12/13/15 use the fixed `memfd_create` names and creator flags recorded in Request 6's adoption gate, while FD 18 is a retained host descriptor closed before bwrap. The receiver predicate is `S_IFREG`, `st_nlink == 0`, `fstatfs == TMPFS_MAGIC`, exact `/proc/self/fd` `/memfd:<fixed-name> (deleted)`, exact four-seal `F_GET_SEALS`, expected size, no trailing bytes, and offset zero; Linux exposes no post-hoc `MFD_ALLOW_SEALING` or `MFD_CLOEXEC` origin bits, so those creator traces are explicit owner invariants rather than invented `fstat` properties. The dispatcher and worker rewind the original descriptors before each real handoff; bwrap consumes them with fixed `--ro-bind-fd` operations and does not forward or rewind arbitrary FDs; the helper opens fixed read-only `/authority/*` paths and rehydrates local sealed memfds. The supervisor-created FD 15 and FD 16 channel/ticket, plus the signed `source_exception_sha256`, are the only accepted freshness/parent/source-exception proofs; there is no caller-selected capsule, nonce, signer, or Make-visible authority fd. | `run-json-scan-row-ownership-adoption-smoke` covers exact v2 predicate/envelope golden bytes (including `dispatch_ticket_sha256`, `source_exception_sha256`, and `image_attestation_sha256`), every field boundary, digest/hex/nonce case, duplicate/unknown/out-of-order/NUL/truncated/padded payload, signature/key/predicate/image/manifest mismatch, ordinary regular and unlinked tmpfs files, wrong-name memfds, every seal/size/offset/trailing-byte case, creator-flag trace failure, bwrap source consumption and fixed-path rehydration, supervisor-channel peer/ticket absence or replacement, retained-FD18 replacement, `argv[0]` and option parsing, replay with a prior capsule/worker/nonce/exception vector, and mutation between validation and child dispatch with independent capsule/worker/nonce/exception golden vectors. |
| Ordinary focused adoption launcher | image supervisor/dispatcher, Request 6 worker, Makefile/smoke | The trusted `fresh-supervise` authenticates the image envelope and fixed manifest, walks and retains absolute `ALIGN_REPO` as FD 18, creates nonce FD 15 plus a connected supervisor channel, forks exactly one dispatcher child, passes the child endpoint as FD 16 plus FD 18, sends one ticket, and remains alive until the child exits. Only the child dispatches the retained image-owned Request 6 entrypoint with `argv[0] = request6-adoption-entrypoint`; the dispatcher authenticates the current-parent peer, stable PID start-time, controlled procfs executable identity, exact supervisor command line, ticket, and FD 18, rejects arguments and non-empty Make-control variables before worker dispatch, reads the repository worker only as bounded no-follow data, seals the signed `ordinary-adoption/v2` capsule and worker on FDs 12/13, and invokes the worker exactly as `/usr/bin/python3 -I -B /proc/self/fd/13 --project-root-fd 4 --align-root-fd 18 --capsule-fd 12 --invocation-nonce-fd 15 --supervisor-channel-fd 16`. Before this exec it clears `FD_CLOEXEC` on 4/12/13/15/16/18 and uses `close_fds=True, pass_fds=(4,12,13,15,16,18)`. The worker verifies the outer peer before entering bwrap, closes FD 18, owns cgroup/staging/bwrap setup, forks one bwrap launcher child that invokes worker-owned FD 27 with `execveat(AT_EMPTY_PATH)`, and passes the sealed descriptors to bwrap as fixed read-only `/authority/capsule`, `/authority/worker`, and `/authority/nonce` binds plus the live FD 16 channel. Bwrap consumes the source descriptors, keeps FD 16 only because the exact vector has `--as-pid-1 --sync-fd 16`, uses `--unshare-ipc`, and the namespace supervisor opens the paths, consumes and verifies the single queued worker-admission proof, rehydrates local sealed memfds, checks only channel HUP/EOF/protocol liveness (outer PID/procfs checks are N/A inside the private PID namespace), and never executes the worker a second time. It stages the complete Rust prefix/sysroot plus LLVM/native tools and explicit `cc`/`cxx` aliases, passes every ordered manifest tool through retained descriptors into the namespace-owned read-only `/tools` inventory, clears rustup/Cargo ambient state, remounts `/` read-only after setup, and runs only the three fixed internal Make vectors owned by the helper. Wrapper-owned project/tool/cache inputs arrive only through retained `--ro-bind-fd` setup binds, are copied into namespace-owned trees, the setup binds are unmounted, the inventory source mount is detached before children, and all remaining copies are remounted read-only; project scripts are data arguments to `/tools/bash` or `/tools/python3`, never executable roots or shebang-resolved paths. | `run-json-scan-row-ownership-adoption-smoke` injects `MAKEFLAGS=-n/-i`, `GNUMAKEFLAGS`, `MAKEOVERRIDES`, alternate goals/makefiles, supervisor/dispatcher/manifest/path/nonce/channel/ticket/FD18 replacement, rustup shims, symlink/replacement tools, version mismatches, stale outputs, namespace setup failure, namespace-tmpfs mutation through both inventory aliases and root remount attempts, host-side source/worker/nonce/exception mutation before/during/after capsule and copy, retained-fd replacement, controlled procfs exec races, bwrap FD27 fork/exec, toolchain-path mutation, direct project-script exec attempts, and tool-inventory/source-resolution markers; every rejection occurs before a Make or compiler marker, while the positive vector records attested tool/cache/capsule/nonce/ticket/exception digests, versions, canonical runtime/mount identities, child argv[0] and options with separate interpreter/data slots, cache identity, sealed input binds, fixed three-row vector order, root read-only state, channel liveness, and cleanup. |
| Project-script interpreter boundary | Makefile and `adoption-namespace` | `align-revision` executes exactly `/tools/bash /private-project/scripts/check-align-revision`; the focused target executes exactly `/tools/python3 /private-project/scripts/run-json-scan-row-ownership-adoption-smoke`. The public worker executes from sealed FD 13 through `/usr/bin/python3`; no project script is an executable root, PATH-discovered executable, or shebang-resolved path; `git`, `tr`, and other commands called by Make scripts resolve only from `/tools`. | `run-json-scan-row-ownership-adoption-smoke` records child argv and exec provenance, rejects a project script in an executable slot, replaces/truncates/symlink-races each script and interpreter, plants host marker tools and shebangs, and proves only the attested interpreter bytes and separate data argument run. |
| Ordinary dependency source | adoption wrapper plus Section 9 cache manifest | The ordinary build has no network or ambient Cargo state: the attested schema-2 cache manifest and read-only source tree are copied into a unique private `CARGO_HOME`, `CARGO_NET_OFFLINE=true` is fixed, and every admitted registry/Git file is bounded, no-follow, owner-readable, single-link, and digest-checked before Cargo | `run-json-scan-row-ownership-adoption-smoke` covers missing/changed/extra/symlink/hardlink/wrapper/config/cache entries, cache mutation before and during copy, absent-package rejection, network-marker rejection, manifest replacement, and the exact attested manifest digest/entry/byte closure. |
| Ordinary immutable inputs | adoption wrapper plus retained bwrap descriptors and namespace seal | The project snapshot must match its recorded clean `HEAD`/index/raw tree, except for the explicit project and Align root `HANDOFF.md` control rows, project `target/`/`main` output exceptions, and Align `target/` exception; handoff content is bound by the signed source-exception digest and no exception bytes enter `raw-tree/v1`. Both project and Align Git views must report SHA-1 object format (SHA-256 is an explicit `revision` rejection for this ordinary profile); the private Align Git view rejects config includes, fsmonitor, hooks, alternates, replacement refs, and grafts; complete Rust prefix/sysroot, LLVM/native roots, Cargo cache, and compiler-input source are descriptor-relative copied inputs with complete pre-copy, post-copy, and final pre-child snapshots; ordinary-clone and linked-worktree `.git`/`commondir` views are rewritten to private siblings; the namespace has an empty root and exposes only namespace-owned sealed read-only input trees, declared writable tmpfs, and root-owned image runtime binds. Wrapper staging paths are visible only as `/input-*` setup binds; the supervisor revalidates, copies, unmounts those binds, remounts the `/private-*` copies read-only, and proves no host alias remains before Make. | `run-json-scan-row-ownership-adoption-smoke` mutates/replaces every source/tool/native/cache/Git-common path before, during, and after copy, injects same-size and extra-entry changes, exercises ordinary and linked worktrees plus rejected Git helper/config channels and SHA-256 rejection, replaces namespace bind sources and mountpoints, races compiler-input replacement during namespace copy and retained-fd bwrap startup, checks sealed-copy mutation and host-root absence, read-only canonical runtime identity, namespace-tmpfs no-alias identity, handoff-content digest changes, and requires rejection before the next child with the private root retained on an unprovable cleanup. |
| Ordinary child lifecycle and compiler handoff | adoption wrapper, cgroup gate, authenticated runtime/tool bindings, `adoption-namespace`, Makefile/smoke | The outer wrapper owns the bwrap/namespace-supervisor process, the retained `--ro-bind-fd` setup inputs, the delegated cgroup admission, and the host staging root. The exact bwrap vector enters UID/GID 0 with `--cap-drop ALL --cap-add CAP_SYS_ADMIN`; the worker parent forks a launcher child that closes FD 11, blocks on FD 10, and performs no bwrap operation while blocked. The worker parent attaches that recorded PID and start time to an empty leaf with `pids.max=512`, proves membership, and writes exactly one gate byte on FD 11; only then does the child close FD 10 and exec bwrap. Bwrap and all descendants inherit that leaf from their first executable instruction. The supervisor revalidates and copies `/input-*` to namespace-owned `/private-*` trees, unmounts every setup bind, remounts the copies read-only, and retains `CAP_SYS_ADMIN` only until that seal and the compiler-bundle remount are complete. The in-namespace supervisor owns the three Make children with child-subreaper mode, new sessions, PID start-time/process-group identity, bounded streams, fixed deadlines, TERM/KILL/reap order, and deterministic namespace cleanup; the outer wrapper never tries to reap descendants across the private PID namespace. Each child uses the fixed `-C /private-project -f /private-project/Makefile` vector inside the empty-root namespace, so recipes cannot reopen the caller's cwd or host root. The supervisor itself is the exact retained `/usr/bin/adoption-namespace` runtime binding, and every child invokes `/tools/make` from the complete retained schema-2 tool inventory; bare `git`, `tr`, `bash`, Python, and other tool names resolve only from that read-only `/tools` mount, never from an ambient path. The supervisor runs `align-revision`, the private no-prerequisite `align-build-only` target, and the focused target in that order. It verifies the new compiler/archive after `align-build-only`, computes their digests, copies those bytes plus the authenticated launcher into namespace-owned `/private-tool-bin`, writes the descriptor after final destination stat/hash including `launcher_sha256`, remounts it read-only, and launches each Make child through a capability-dropping boundary with native-first `PATH=/private-native/bin:/private-rust/bin:/private-llvm/bin:/tools:/usr/bin:/bin` plus `CC`/`CXX` needed by `alignc run`; the focused target rejects stale or replaced binaries and descriptor bytes before any fixture compiler call. After the supervisor exits, the outer wrapper proves and removes the empty cgroup leaf and performs descriptor-relative host staging-root cleanup; the namespace supervisor never removes a host pathname. | `run-json-scan-row-ownership-adoption-smoke` covers launch/reader/nonzero/timeout/cancellation, double-fork descendants, output cap, cleanup failure, child cwd and argv (including a caller-checkout marker that must remain untouched), exact three-vector order and `align-build-only` prerequisite absence, authenticated runtime/tool-inventory digest and source-resolution checks plus replacement-before-child failures, cgroup start-gate/membership and pids-cap boundaries, canonical runtime mount identity and host-root absence, namespace-tmpfs no-alias identity, new-build digest/version/archive identity, descriptor golden bytes, launcher digest, stale `ALIGNC`, handoff/path replacement, staged-versus-ambient `cc` interposition, retained-fd source replacement during startup, host-side mutation after seal, host-root cleanup, and no compiler invocation before handoff validation. |
| Ordinary direct compiler handoff | adoption wrapper, `adoption-namespace`, `scripts/adoption-alignc`, Makefile/smoke | The ordinary profile never passes the raw Cargo release path to a fixture. It copies the verified source bytes into the namespace-owned compiler tmpfs, stats/hashes the final destinations, writes the exact compiler/archive/launcher identities and project/revision binding into the canonical schema-1 descriptor, remounts the complete sibling bundle read-only with no host alias, and passes `ALIGNC=/private-tool-bin/adoption-alignc`, `ALIGNC_DESCRIPTOR=/private-tool-bin/adoption-handoff`, and `ALIGNC_CACHE=/private-compiler-cache` in that fixed filename order; the launcher opens the fixed handoff/bundle paths, verifies the read-only mount and all bytes including `launcher_sha256`, and executes the already-open compiler with `execveat(AT_EMPTY_PATH)`, with no sibling, PATH, or caller-selected fallback. | `run-json-scan-row-ownership-adoption-smoke` covers reordered/whitespace/trailing descriptor bytes, missing/relative/symlinked/stale/replaced compiler, archive, or launcher, writable/wrong mount identity, host-alias and source-race attempts, project/revision mismatch, launcher interposition, and compiler-call markers before and after each focused fixture. |
| Fresh internal compiler call | Makefile/scripts/Python runners | In the fresh profile all consumers use the fresh launcher and fixed read-only handoff paths; every Python boundary uses `close_fds=True, pass_fds=()` except the coding-task sandbox probe and its two validation invocations, which pass exactly the prepared user-namespace fd; the fresh environment disables bytecode writes; no bare compiler, sibling, mutable path, or fallback | `fresh-v2-callsite-smoke` exercises Make, format, prompt/evaluation, baseline, nested runners, Python subprocesses, recursive Make, handoff-file replacement, workspace `__pycache__` prevention, absence of worker identity fds, and the Section 9 Request 6 fresh-profile branch. |
| Aggregate interpreter boundary | aggregate and nested bwrap | Staged `/usr/bin/env`, `/bin/sh`, Python plus stdlib/extension roots, Bash, `mount-guard`, `/tools`, no-symlink aggregate `/target/tmp` plus nested validation `/tmp` and `/dev/shm`, derived linker/loader paths, `PYTHONDONTWRITEBYTECODE=1`, PATH, and the single prepared user-namespace descriptor as the only permitted nested input fd | `fresh-v2-interpreter-boundary-smoke` installs host marker interpreters/tools/modules, runs nested validation, exercises the independent 64 MiB `/tmp` and `/dev/shm` mounts, attempts a temp-to-workspace symlink and a contained source symlink, creates an importable runner module, and verifies staged identities, temp-root propagation, mount attributes, no `__pycache__`, and no worker identity fd; all other aggregate child launches retain the empty descriptor set. |
| Aggregate topology | supervisor/worker/Makefile | For `ci`, exactly one bwrap aggregate, UID/GID 0 with `CAP_SYS_ADMIN`/`CAP_SETFCAP` plus temporary setup-only `CAP_SETUID`/`CAP_SETGID`, mount-guard preparation of the one descendant validation user namespace, reduction to `CAP_SETFCAP` plus `no_new_privs` before Make, closed executable inventory including `seq`, supervisor exact request validation and direct-bootstrap argv/env/fd-4/5/6 boundary, private-source-only Make parsing, fixed internal `-f /workspace/Makefile`, complete normalized GNU Make 4.3 option/alias matrix with a separate accepted `--no-print-directory` row, separated/attached/`--name=value` arguments, explicit rejections for newer `--jobserver-style`/`--shuffle`, empty inherited-fd set after bootstrap, explicit `ALIGNC_CACHE=off`, `PYTHONDONTWRITEBYTECODE=1`, derived linker paths, private project Git environment, and fixed goal order; for `adoption`, exactly one focused bwrap with the same staged process/tool/source/cache/tmpfs boundary, no overlay upper/work, no prepared validation user namespace, no `/workspace/main`, and the fixed focused goal | `fresh-v2-aggregate-topology-smoke` covers every aggregate-plus-focused/aggregate order, every minimum-version option/alias/argument spelling/assignment, accepted-request and newer-option rejection, tracked and untracked alternate makefile bypass, fixed internal Makefile selection, repository Makefile supervisor bypass, loader-variable injection, read-only-tools identity, private Git propagation to eval/loop, cache-off and bytecode-disable propagation, inventory completeness, exact fd map, and empty descriptor propagation except for the single prepared user-namespace fd at the nested coding-task boundary; the qualification inventory additionally asserts the nested `--cap-drop ALL --cap-add CAP_SYS_ADMIN --cap-add CAP_SETFCAP` order, no nested `--unshare-all`/`--unshare-user`, prepared `--userns` descriptor use, the aggregate `--prepare-validation-userns` flag, root `--size 268435456`, authenticated `/tools/fresh-alignc`, bounded Git view, and published-ELF closure owners. `fresh-v2-focused-adoption-request-smoke` covers the adoption vector's omitted overlay/userns objects, read-only source workspace, fixed goal, no-publication proof, and focused cleanup. |
| Ordinary adoption concurrency and orphan cleanup | wrapper plus installed profile lock/cgroup parent | The ordinary wrapper and Section 9 fresh modes share the fixed per-user `flock` at `/run/user/<uid>/align-llm-fresh/lock`; `LOCK_NB` rejects every second ordinary/fresh entrypoint before cgroup, root, namespace, or Make side effects. A normal owner releases the lock only after child/cgroup/namespace/root cleanup; a `SIGKILL` owner relies on `--die-with-parent` and cgroup emptiness, and the next owner fails closed on an unprovable quarantine candidate. | `run-json-scan-row-ownership-adoption-smoke` runs ordinary+ordinary, ordinary+fresh in both orders, recursive entry, failed-second markers, orphaned cgroup/root, and replacement-before-admission cases with exact ordinary/fresh status bytes and no cross-root deletion. |
| Ordinary resource boundary | outer wrapper cgroup gate plus `adoption-namespace` | The installed profile supplies the existing delegated per-user cgroup parent under `/sys/fs/cgroup/align-llm-fresh/<uid>` with `pids.max=512`; memory cgroup enforcement is N/A because that profile delegates only pids. The outer wrapper owns the unique leaf, empty admission, start-gated bwrap attach, membership proof, and descriptor-relative leaf cleanup; the namespace never mounts host cgroup state. Every child inherits and verifies `RLIMIT_NPROC=512`, `RLIMIT_NOFILE=4096`, and `RLIMIT_FSIZE=536870912`. The ordinary namespace remounts root and private build trees at `68719476736` bytes/`2000000` inodes, `/private-cargo-home` at `25769803776` bytes/`400000` inodes, `/private-compiler-cache` at `8589934592` bytes/`400000` inodes, setup-only `/private-tool-inventory` at `268435456` bytes/`65536` inodes (unmounted before any child), `/private-tool-bin` at `268435456` bytes/`65536` inodes, and `/tmp` at `268435456` bytes/`65536` inodes. Sealed inputs are admitted only when their checked aggregate is at most 48 GiB and 1,500,000 entries. Cargo admission uses the schema-2 20 GiB/200,000-entry logical limit plus the page-rounded file, directory, and 2 GiB metadata-reserve formula, capped at the 24 GiB Cargo-home size. The supervisor counts bytes and entries during each vector, rejects cap-plus-one, and owns no host-writable target/cache bind. | `run-json-scan-row-ownership-adoption-smoke` covers process/fd/file-size/cgroup start-gate and membership limits, every tmpfs byte/inode boundary, the logical 20 GiB and materialized 24 GiB Cargo-home boundaries, the 1,500,000-entry sealed-input boundary, private-entry cap-plus-one, stream cap, host-root cleanup, and cleanup after timeout, signal, or uncatchable owner death. |
| Process ownership | worker plus per-invocation cgroup/rlimit boundary | Subreaper, sessions, bounded streams/deadlines, PID start-time checks, descendant reap, a unique worker-owned delegated cgroup leaf with strict empty admission and post-attach membership proof, cgroup-v2 unique-leaf/rmdir cleanup under the protected writer boundary, `pids.max=512`, `RLIMIT_NPROC=512`, `RLIMIT_NOFILE=4096`, `RLIMIT_FSIZE=536870912`, source active-window accounting, and bounded worker fd scans | `fresh-v2-process-lifecycle-smoke` covers build/aggregate hangs, stream overflow, double fork, signal, PID reuse, reader closure, process cap-plus-one, source-window cap-plus-one, total-fd cap-plus-one, exact file-size-limit boundary, cgroup leaf replacement-before-cleanup/nonempty cleanup, admission nonempty/malformed/foreign membership, successful descriptor-relative rmdir, uncatchable worker death, and missing cgroup delegation. |
| Cleanup success | worker | Reverse descriptor-relative quarantine removal, stable parent/root device-inode/type/mode/owner identity while owned content metadata changes, destination identity proof after every move, root absent before PASS | `fresh-v2-cleanup-smoke` proves normal staging metadata changes are accepted, while no private root, handoff file, cache copy, target, marker, or child remains; deterministic replacement-before-move cases leave the replacement and the admitted tree untouched. |
| Cleanup failure | worker plus admission lock | Never delete replacement/unowned path within the protected writer boundary; atomic no-replace private-root moves, cgroup-v2 unique-leaf/rmdir identity and empty proofs, exact primary/cleanup precedence; uncatchable death leaves one bounded root, releases only the kernel lock, and makes the next invocation fail closed before root creation | `fresh-v2-cleanup-failure-smoke` injects close, private quarantine move and identity mismatch, cgroup leaf identity/nonempty/rmdir failures, unlink, parent replacement, live child, catchable signal, successful-phase cleanup failures, worker `SIGKILL`, repeated death attempts, and later invocations that must leave the unprovable root untouched and refuse a second root. |
| Baseline Git identity | worker plus baseline runners | Normal baseline and project Git calls use a worker-copied read-only `/baseline-git` view; negative replacement fixtures use a separate `/target/tmp` private view; explicit `GIT_DIR`/`GIT_COMMON_DIR`/`GIT_WORK_TREE`, copied objects, fixed hardening variables, and the standalone chain checker's exact fresh executable and private-view tuple never resolve the hidden workspace, source common dir, host Git, or an unlisted runtime executable | `fresh-v2-baseline-scratch-smoke` plus `run-baseline-invalid-smoke` run normal, eval, loop, invalid-baseline, and chain-environment paths, check linked-worktree object resolution, private-object replacement, hardening-variable preservation, alternate rejection, fixture-variable clearing, partial/different fresh executable settings, mismatched Git-view settings, and unchanged project source-control state. |
| Status and error grammar | worker | Exact PASS bytes and `fresh compiler: ERROR <CATEGORY> <PHASE>\n` primary / `fresh compiler: ERROR CLEANUP cleanup\n` cleanup lines, with closed category/phase sets and fixed precedence | `fresh-v2-status-grammar-smoke` asserts every phase's first failure, successful-phase cleanup failure, primary-plus-cleanup failure, empty stdout, and no child bytes. |
| Baseline identity | baseline owner | Final Makefile source, two samples, oracle, finalization, ancestry, unchanged pin, and explicit read-only descriptor/guard paths through recorder subprocesses | `fresh-v2-baseline-integration-smoke` runs the Section 2.4 chain before capable evidence and asserts recorder Python children use the empty descriptor set and fixed handoff files in fresh mode. |
| Concurrent independent invocations | worker and image/profile lock parent | The worker owns a descriptor-relative `flock` on `/run/user/<uid>/align-llm-fresh/lock`, validates every protected parent component and `0600` lock identity, opens the profile-created `roots` child with mode `0700` and stable identity, then performs a bounded per-user candidate-name scan; a second `ci`, `adoption`, `build`, or `self-test` is rejected before private-root creation and no process classifies or deletes another root | `fresh-v2-concurrency-smoke` runs every pair of simultaneous modes, checks exact `PLATFORM concurrency`/`FILESYSTEM filesystem` status, replaces or weakens each lock-parent or `roots` component, proves only one root can exist per user, exercises the 65,536-entry/one-second fail-closed scan without shared-`/tmp` interference, and injects cross-root replacement/deletion attempts. |
| Platform boundary | topology plan | x86-only claim; executable `/tmp`; authenticated-retained-bwrap namespace/overlay/read-only-tools and `/target/tmp`-only no-symlink self-tests; delegated cgroup limits; non-x86 requires separate profile | `fresh-v2-platform-profile-smoke` rejects unsupported or `noexec` `/tmp`, missing cgroup delegation, replaces the mutable bwrap pathname and tool staging source, proves the read-only bundle survives replacement, checks a contained source symlink remains usable, and prevents C7 non-x86 evidence reuse. |

### 9.10.1 Current FRESH-IMAGE-REQUEST6-BOUNDARY enabling slice

The complete Request 6 rows above remain the future consumer contract. The current enabling slice
must not install a partially reachable worker, capsule, proof, bwrap, or namespace-helper path and
must not claim ordinary-adoption evidence. Its independent installed-image contract is the
non-evidence selector `--mode ordinary-adoption-boundary` and the separate image-owned dispatcher
`/usr/local/libexec/align-llm/request6-adoption-boundary-entrypoint`.

The boundary supervisor verifies the image envelope, schema-2 manifest, and dispatcher runtime
binding; opens the project root and walks the caller's absolute Align path from a retained root
descriptor; retains the final Align descriptor as FD 18; forks exactly one child; and invokes the
retained dispatcher through FD 14. Its fixed dispatcher vector contains only the named mode,
project/image/manifest/Align descriptors 4/6/8/18, and the normalized absolute/relative path pair.
It creates no nonce or supervisor channel. The child passes exactly descriptors 4/6/8/18 and the
standard streams `{0,1,2}`; the dispatcher post-exec set is exactly `{0,1,2,4,6,8,18}` and it
closes every other inherited descriptor before validation. A missing worker, a regular
worker, and every malformed/replaced worker are all deterministic `revision` rejections; no worker
bytes are signed, copied, executed, or handed to another process.

The boundary dispatcher accepts only its exact vector and the five fixed image environment entries,
verifies the sealed image/manifest inputs and retained FD 18 identity, and performs the bounded
no-follow worker-presence check before any source snapshot, signer, capsule, helper, or child
operation. An exact direct invocation with caller-created image/manifest descriptors is permitted
only as an untrusted diagnostic: it can reach the same pre-worker `revision` rejection, can never
produce a success or ordinary evidence, and has no channel, nonce, parent proof, or other
supervisor-origin authority. A malformed direct vector or any full `ordinary-adoption` vector is
rejected as `input` before a repository-controlled process. Its only installed-profile positive gate
is the exact pre-Make `revision` result for the absent worker; the present-worker case must prove
the same rejection and must not reach host-root Python.

The boundary public-contract ledger is:

| Surface | Exact contract | Ownership and identity | Acceptance |
| --- | --- | --- | --- |
| Installed entrypoint | `execve("/usr/local/libexec/align-llm/fresh-supervise", ["fresh-supervise", "--mode", "ordinary-adoption-boundary"], ["PATH=/usr/bin:/bin", "LC_ALL=C", "LANG=C", "HOME=/nonexistent", "TMPDIR=/tmp", "ALIGN_REPO=<absolute>"])`; caller cwd is the project root and no other environment entry is accepted | Image supervisor owns the first exec, validates the absolute path, and owns all child descriptors; no shell, repository executable, or ambient configuration is part of the contract | Installed boundary profile smoke, including missing, relative, and malformed `ALIGN_REPO` cases |
| Dispatcher vector | `request6-adoption-boundary-entrypoint --mode ordinary-adoption-boundary --project-root-fd 4 --image-attestation-fd 6 --manifest-fd 8 --align-repo-root-fd 18 --align-repo-absolute <normalized-absolute> --align-repo-relative <canonical-relative>` | Supervisor owns FD 14 executable authority and consumes it at `execveat(AT_EMPTY_PATH)`; the dispatcher post-exec set is exactly `{0,1,2,4,6,8,18}`. Standard streams remain the supervisor-owned pipes; FD 14 is not present after exec, and the dispatcher closes every other inherited descriptor. No nonce, socket, or worker FD exists in this slice | Direct argv/FD/env smoke plus installed retained-FD dispatch |
| Result | Missing, present, malformed, or replaced worker: child exit `1`, empty stdout, exactly `json-scan adoption: ERROR revision\n`; malformed boundary argv/env/FD set: child exit `1`, empty stdout, exactly `json-scan adoption: ERROR input\n`; pre-FD14 image/manifest/path failure: supervisor exit `1`, empty stdout, exactly `fresh compiler: ERROR TRUST supervisor\n`; dispatcher timeout, signal death, unknown status, or incomplete child output: supervisor kills/reaps the one child and emits the same trust line | The supervisor captures child stdout/stderr in bounded pipes and forwards only one validated complete boundary line; no child stream is forwarded on timeout, signal, or cleanup failure. The boundary has a fixed 5-second child deadline, and every failure exits `1`; there is no boundary success status | Exact byte/status assertions for every negative, timeout, signal, and cleanup vector |
| Dispatcher runtime binding | One schema-2 `runtime_bindings` record with `target` and `source` both `/usr/local/libexec/align-llm/request6-adoption-boundary-entrypoint`, `kind=file`, root owner, mode `0755`, full-byte `manifest.sha256`, and canonical serialized `manifest_sha256`; the deterministic static-PIE ELF has no interpreter or mutable runtime closure | Image build owns the bytes and manifest; supervisor opens the no-follow source, checks owner/mode/link-count/size, verifies both digests, and dispatches the retained descriptor rather than reopening the pathname | Manifest-wire assertion, two deterministic ELF builds, and replacement-before-dispatch rejection |
| Persisted identity | N/A: the boundary creates no capsule, nonce, worker snapshot, cache, or other persisted artifact | Image manifest and attestation remain the only authenticated inputs; future `ordinary-adoption` identity is owned by the consumer-complete slice | N/A with the concrete reason that this slice has no persisted output |

The boundary closure matrix is intentionally limited to the following paths: construction and
manifest binding (image Dockerfile/generator, deterministic ELF and manifest smoke); successful
retained dispatch (supervisor and boundary dispatcher, installed profile positive vector); malformed
input and direct invocation (dispatcher, focused boundary smoke); missing/present/replaced worker
(dispatcher, revision smoke); early exit, timeout, signal, and cleanup (supervisor reaps its one
dispatcher child and closes FDs 4/6/8/14/18, with no descendant worker to reap); and malformed
image/manifest/path inputs (supervisor trust smoke). Capsule, proof, namespace, worker, source,
resource, and consumer cleanup cells are N/A here because the slice deliberately creates none; each
is named as an owner and acceptance test in the full consumer-complete row rather than silently
omitted.

The applicable closure cells for this slice are therefore selector/argv/env validation, descriptor
closure, image manifest binding, retained absolute-path identity, worker-presence rejection, exact
failure bytes, deterministic ELF installation, and direct-entrypoint rejection. Their owners are
`fresh_image_control.py`, the boundary dispatcher, the image Dockerfile/manifest generator, and
the boundary profile smoke. The ordinary admission proof, capsule and worker memfds, source
identity vectors, bwrap FD 27, namespace helper, process ownership, resource limits, cleanup
quarantine, and focused Make vectors are explicitly deferred to the consumer-complete
FRESH-IMAGE-REQUEST6 slice below; no boundary check or HANDOFF may claim them as passed.

### 9.10.2 Corrected ordinary parent and exec design

The first ordinary-transport implementation attempt is superseded and is not an executable
checkpoint. Its Python-carrier parent and executable-digest fallback cannot authenticate provenance:
an unrelated same-UID Python process can reconstruct the same command line and bytes. The corrected
implementation therefore preserves the full Section 9.10 public contract and changes the ownership
boundary before code resumes.

For `ordinary-adoption`, the native image-owned `fresh-supervise` remains the direct parent of the
dispatcher from the first ordinary exec through final helper cleanup. It never `execve`s the Python
carrier before dispatch. A short-lived image-owned preflight child may run before the ordinary channel
exists; it validates the image envelope, fixed manifest, supervisor identity, and Request 6 dispatcher
runtime binding using the embedded control payload, captures bounded empty output, and exits. It may
not open the project or Align roots, inspect repository bytes, create a channel or nonce, sign a
capsule, or launch a worker. The native supervisor rejects any preflight failure as the pre-FD-14
`TRUST supervisor` result, then creates the sealed image/manifest/nonce descriptors, walks and retains
FD 18 from the `/` root, opens the retained dispatcher as FD 14, creates one
`SOCK_SEQPACKET|SOCK_CLOEXEC` channel, forks exactly one dispatcher child, and sends the fresh ticket.
The dispatcher authenticates its current parent through `SO_PEERCRED`, stable `/proc/<pid>/stat`
start-time, the one controlled `/proc/<pid>/exe` descriptor hash, and the exact native command line
`fresh-supervise\\0--mode\\0ordinary-adoption\\0`; a Python interpreter digest, reconstructed
command line, retained payload bytes, or caller-created descriptor cannot satisfy this predicate.

The native parent owns the public ordinary streams. It captures the dispatcher child through bounded
stdout/stderr pipes, remains alive while receiving the capsule digest and sending the queued proof,
waits for the dispatcher/worker/helper tree, and forwards only the exact success or phase result after
the child has been reaped. A signal, unknown status, partial output, stream overflow, missing/extra
channel packet, or cleanup failure follows the existing `TRUST supervisor` or ordinary phase grammar
at the owner boundary; no Python-carrier output escapes. Legacy `ci`, `build`, and `self-test` retain
their existing Python-carrier path because they have no ordinary parent-authentication contract.

The corrected design ledger is:

| Surface | Exact contract | Owner and lifetime | Acceptance |
| --- | --- | --- | --- |
| Ordinary native parent | `/usr/local/libexec/align-llm/fresh-supervise --mode ordinary-adoption`; exact five-variable environment plus absolute `ALIGN_REPO`; native ELF is the direct dispatcher parent | `fresh-supervise.c`; parent owns FD 4/6/8/14/15/16/18, ticket, proof, streams, child wait, and final close order | installed profile parent `/proc` identity and exact argv/env/fd smoke |
| Image preflight | embedded image-control child only; bounded empty stdout/stderr; no repository, channel, nonce, capsule, worker, or Make access; success required before channel creation | native supervisor starts and reaps the child before opening ordinary FD 16; all preflight descriptors are closed before ordinary setup | image/manifest/dispatcher replacement and repository-marker negatives |
| Dispatcher peer predicate | `SO_PEERCRED` current parent; unchanged start-time; bounded `/proc/<pid>/stat` and `/proc/<pid>/cmdline`; one controlled `/proc/<pid>/exe` open whose bytes equal the attested native supervisor; exact `fresh-supervise\\0--mode\\0ordinary-adoption\\0` cmdline | Request 6 dispatcher validates before receiving ticket or signing; no Python digest fallback and no extra procfs magic-link authority | direct dispatcher, Python carrier, caller-created channel, exec-race, PID-reuse, and wrong-parent negatives |
| Ordinary child streams | bounded pipes; no child bytes escape before validation; exact stdout/stderr/status mapping after reap | native supervisor is the sole public stream owner; dispatcher/worker/helper children are fully reaped | partial, overflow, signal, unknown status, timeout, and extra-message regressions |
| Deferred consumer | N/A in this correction: worker source, full staging, bwrap FD 27, namespace rows, and final adoption remain the Section 9.10 implementation slice | no implementation may claim a positive consumer result from this design checkpoint | N/A because this PR changes only ownership design |

The design closure matrix additionally requires construction, success, preflight failure, dispatcher
fork failure, parent death before/after ticket and proof, stream overflow, worker signal/unknown exit,
extra or missing channel packets, cleanup restoration, descriptor leakage, and malformed image/path
inputs to name the native owner and exact installed-profile regression. It must separately prove that
the preflight child cannot reach repository-controlled bytes and that an unrelated Python process
cannot satisfy the dispatcher peer predicate. No implementation PR may proceed until this correction
has passed an independent adversarial design review and merged.

### 9.11 Compatibility, verification, and delivery order

This design-only gate executes exactly `git diff --check`, the balanced Markdown fence parity check,
and `make gate-topology-check`. It does not execute or claim
passing the future digest-tree, source-manifest, cache-manifest, descriptor/guard, image-attestation,
run-capsule, supervisor, Make-option, pre-dispatch, source-fd-window, compiler-suite, lock,
concurrency, or error-grammar owners named in this section; those checks are acceptance contracts
whose executable owners are deferred to the implementation/profile slices. Source tests,
`make check`, `make build`, `make ci`, hosted checks, and benchmarks are N/A until an executable
implementation or executable contract boundary exists. A pull request description and HANDOFF must
record only the commands actually run at this design gate, never the deferred owner names as passed
evidence.

The successor design and its wire/source-identity foundations are merged. They are internal
checkpoints, not a precedent for more helper-only pull requests. Delivery now has two independently
owned base capabilities, one separately verified Request 6 boundary checkpoint, one
consumer-complete Request 6 image-profile extension, and one dependent adoption wave:

1. **FRESH-IMAGE — installed minimum-platform profile.** Install and attest the image-owned
   supervisor, fixed bootstrap, Python runtime, bwrap image, canonical schema-2 manifest, signed
   runner-image attestation, run-capsule signer/policy, protected per-user root parent, delegated
   cgroup/rlimit lifecycle, executable `/tmp`, and runtime/loader/linker bindings. The supervisor
   verifier, keys/digests, policy, and exact `env -i`/fd-5/fd-6 entrypoint are external acceptance
   evidence. This stays separate because host installation and repository implementation have
   different owners and failure domains. Worker implementation may progress in parallel, but the
   installed and attested image is required before worker capable acceptance or merge. Its bounded
   owner checks are `python3 scripts/run-fresh-attestation-wire-smoke` and
   `python3 scripts/run-fresh-image-control-smoke`; `scripts/run-fresh-image-profile-smoke` is the
   installed-profile acceptance that builds the OCI image twice-identically at the ELF-control
   layer, injects ephemeral distinct deployment keys, produces the external attestation, provisions
   the runtime/cgroup profile over the same persistent `/run/user` mount used by the worker, runs
   the no-network synthetic image path, and exercises canonical pre-worker rejection for missing or
   corrupt attestations, image-digest and run-key mismatches, and replaced bootstrap/manifest bytes.
   The separate hosted `fresh-image-profile` job owns this platform
   evidence and is not a permanent transitive child of routine `make ci`.
   This capability is expected to exceed 1,000 changed hand-written lines because its supervisor,
   bootstrap, manifest, deployment signer, runtime provisioner, installed image, and external
   profile smoke form one signed trust tuple. None is an independently usable or attestable public
   surface, so splitting them would create hypothetical intermediate contracts and duplicate the
   same installed-image qualification without producing a passing consumer capability.
2. **FRESH-WORKER — repository worker and Make integration.** Complete the remaining private-root
   admission, sealed snapshots, digest/cache/source materialization, one-root lock, compiler and
   archive bundle, two bwrap namespaces, writable aggregate overlay, namespace-owned no-symlink
   tmpfs, staged nested tools and `mount-guard`, descriptor/guard handoff, empty-fd subprocess
   policy with the single prepared-userns exception, Make interposition, isolated baseline Git scratch,
   process ownership, resource bounds,
   status grammar, and cleanup in one consumer-complete repository capability. It must include a
   core end-to-end functional smoke that actually runs the unchanged-pin aggregate through the
   installed FRESH-IMAGE trust root; a synthetic or direct host run is non-evidence. The named
   security, race, resource, mutation, and failure-injection closure tests remain focused
   qualification commands and all run before this capability merges; they do not all become
   permanent `make ci` dependencies. `python3 scripts/run-fresh-worker-qualification` executes
   every available focused owner and labels each closure row as focused or deferred; after the
   installed profile enables nested user namespaces, `python3 scripts/run-fresh-worker-qualification
   --installed-profile` invokes the installed image, aggregate, baseline, resource, cleanup, and
   failure owners before reporting those rows as executed. The qualification output never claims a
   deferred row passed. Because this capability changes the Makefile and compiler
   consumers, its branch also performs the Section 2.4 identity-bound baseline source, oracle,
   finalization, and merge-ancestry sequence.
3. **FRESH-IMAGE-REQUEST6-BOUNDARY — installed pre-consumer dispatch boundary.** After FRESH-IMAGE
   and FRESH-WORKER merge, install the separate `--mode ordinary-adoption-boundary` selector and
   image-owned boundary dispatcher described in Section 9.10.1. It verifies only the fixed image
   and manifest tuple, retained FD14/FD18 dispatch, strict input closure, and fail-closed worker
   presence rejection. It does not install or bind a namespace helper, create a nonce or channel,
   sign a capsule, copy worker bytes, or execute repository-controlled Python. Its acceptance is
   the installed boundary smoke and it is an enabling checkpoint for the consumer-complete slice;
   it does not advance Request 6 to `ALIGN_LLM_VERIFIED` or claim ordinary evidence.
4. **FRESH-IMAGE-REQUEST6 — installed focused-adoption profile extension.** After the boundary,
   FRESH-IMAGE, and FRESH-WORKER merge, extend the trusted `fresh-supervise` with the exact
   `--mode ordinary-adoption` dispatch,
   install and attest the image-owned
   `/usr/local/libexec/align-llm/request6-adoption-entrypoint`, its complete interpreter/loader
   closure, the `/usr/bin/adoption-namespace` runtime binding, the ordinary-adoption capsule signer
   and verifier policy, the complete ordered `/tools` inventory handoff used by ordinary adoption,
   the 24 GiB Cargo-home-capable ordinary profile, and the supervisor/bootstrap `adoption` dispatch
    required by Request 6. `fresh-supervise` verifies the dispatcher binding through retained FD 14,
    opens `/` as temporary FD 17, component-walks and retains the absolute Align root at FD 18 from
    that descriptor, closes FD 17, and forks exactly one dispatcher child,
    keeps the parent channel endpoint, passes the child endpoint as FD 16 plus FD 18, and sends one
    ticket. Only the child invokes the retained dispatcher with `execveat(AT_EMPTY_PATH)`, passing
    project-root FD 4, image-attestation FD 6, manifest FD 8, supervisor-created nonce FD 15,
    supervisor-channel FD 16, and retained Align-root FD 18, with the
   fixed named-option dispatcher vector whose `argv[0]` is `request6-adoption-entrypoint`:
   `--mode ordinary-adoption --project-root-fd 4 --image-attestation-fd 6 --manifest-fd 8
   --align-repo-root-fd 18 --align-repo-absolute <normalized-absolute> --align-repo-relative <canonical-relative>
   --invocation-nonce-fd 15 --supervisor-channel-fd 16`; the
   dispatcher pathname is never the trust root. The same profile authenticates `/usr/bin/bwrap` at
   FD 27 and consumes that descriptor with `execveat(AT_EMPTY_PATH)` before the namespace helper.
   This extension owns the Request 6 dispatcher and `/usr/bin/adoption-namespace` binding; FRESH-WORKER
   owns the generic sealed worker boundary but does not introduce a Request 6 helper or consumer path.
   This is a separate image-owned branch and pull request, not work smuggled into the repository
   worker or consumer adoption branch. Its acceptance builds the minimum image, verifies the exact
   schema-2 runtime/tool records and digest closures, exercises the descriptor-backed `/tools` mount,
   the retained-FD dispatcher path, the FD-12/FD-13 capsule/worker plus FD-15 fresh-nonce
    read-only bind handoff, the FD-16 supervisor-channel peer/ticket proof, the FD-18 retained-path
    identity, controlled procfs executable authentication, and the direct supervisor
   path under the installed attestation, and proves the ordinary cgroup/rlimit/tmpfs profile before
   any repository Make child. The image-profile smoke must also invoke the legacy image-owned
   `fresh-supervise --mode self-test` vector with no `ALIGN_REPO`, assert exactly
   `fresh compiler self-test: PASS\n`, and prove that no ordinary dispatcher, sealed worker,
   capsule, nonce, Make, or compiler marker occurs on that path. It must replace the dispatcher and
   worker independently, replay or edit the capsule, and prove rejection before any Make or compiler
   marker. It must pass against the exact installed manifest before this extension is considered
   merged; it records a new image/profile identity and does not change `.align-revision`.
5. **Fresh adoption wave.** After FRESH-IMAGE, FRESH-WORKER, the boundary, and the full
   FRESH-IMAGE-REQUEST6 all pass
   and merge, batch the merged Align requests
   required by the next real consumer into one `.align-revision` update, rebuild, and the original
   focused acceptance gate through the authenticated focused request, followed by one final fresh
   `make ci`. Request 6 has two explicit profiles: its ordinary host evidence must enter through
   the trusted `fresh-supervise --mode ordinary-adoption` request, which verifies and dispatches the
   image-owned Request 6 child before that child authenticates and transfers its sealed worker bytes,
   while its fresh evidence selects the Section 9 profile inside the fixed
   `make --no-print-directory json-scan-row-ownership-adoption` request with
   `ALIGNC_CACHE=off /tools/fresh-alignc check <file>` and
   `ALIGNC_CACHE=off /tools/fresh-alignc run <file>`. The focused target is deliberately absent from
   routine hosted/capable aggregate membership, and a host command that only names
   `/tools/fresh-alignc` is not fresh evidence.

The FRESH-IMAGE-REQUEST6 boundary is prerequisite infrastructure for the consumer-complete
FRESH-IMAGE-REQUEST6 profile and is explicitly allowed to implement only its installed boundary
contract after FRESH-IMAGE and FRESH-WORKER merge; it is not the Request 6 adoption consumer. The
full FRESH-IMAGE-REQUEST6 profile remains prerequisite infrastructure and is explicitly allowed to
implement the complete installed transport after the boundary, FRESH-IMAGE, and FRESH-WORKER
merge. No Request 6 adoption consumer may implement against or claim this redesign before
FRESH-WORKER, FRESH-IMAGE, the boundary, and full FRESH-IMAGE-REQUEST6 merge. Request 7 registration,
Request 9 design, C7 design, and other independent planning may continue, while their consumer
implementations remain governed by their own applicable image and worker profiles. A proposed
descriptor, manifest, host image, or platform profile is not an input. The request register remains
lifecycle authority; this section owns only the common Linux x86_64 fresh-compiler contract and its
evidence.
