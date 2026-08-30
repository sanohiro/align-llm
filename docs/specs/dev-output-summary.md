# DEV-OUTPUT-SUMMARY: concise verification output with retained evidence

Status: **design, written before implementation**. Branch `agent/dev-output-summary`, based on
`main` merge commit `e0b851acf1b0b73324be4bdda11c8242505c4415` (R6-PREFIX-TTFT, PR #157).
Roadmap item 40 is the charter. Sections 1 through 6 are committed before the first executable
change. Later implementation and measurements append a record without rewriting the baseline,
ceilings, or acceptance rule.

## 1. Decision and boundary

### 1.1 Consumer-complete capability

Successful verification currently sends the full output of every child through the terminal even
when almost all of it is repeated compiler warnings. A failed outer aggregate can do the opposite:
retain a large capture internally while showing only a generic status that hides the useful child
diagnostic. This capability ships one shared process wrapper that:

1. captures one command's merged stdout and stderr byte-for-byte in a retained log;
2. keeps one progress coordinate visible at least every 60 seconds;
3. emits a concise terminal result, normalized warning counts, exact log identity, and bounded
   useful failure diagnostics;
4. preserves the child's ordinary exit status or terminating signal; and
5. is used by direct `layer-forward-smoke`, every `scripts/pre-pr` process phase, and the hosted CI
   aggregate. CI uploads the retained logs after the aggregate step.

The narrow owner is deliberately the observed noisy local consumer. `scripts/pre-pr` and hosted CI
exercise the same wrapper around their existing command boundaries; neither receives a second
aggregate or a reordered target list.

### 1.2 Design-gate triggers

| Trigger | Fired | Reason |
| --- | --- | --- |
| Public CLI | **Yes** | `scripts/run-output-summary` adds a developer-facing command and line-oriented result contract |
| Persisted or exchanged format | **Yes** | the retained raw log has a digest identity and CI publishes it as a workflow artifact |
| Ownership / process boundary | **Yes** | the wrapper owns the child process group, its merged output descriptor, signal forwarding, log finalization, and terminal reduction |
| Coordinated invariant across at least three modules | **Yes** | the shared module, CLI, direct owner, preflight, workflow, and their regressions must agree on status, order, progress, and artifact identity |

### 1.3 Scope and non-goals

**In scope:** one command per wrapper invocation; inherited stdin; merged child stdout/stderr; local
Git-common-directory logs; an explicit CI log directory; GitHub artifact retention; ordinary exit,
child-signal, supervisor-signal, and broken-output-pipe behavior; exact warning-class counts;
bounded failure diagnostics; direct `layer-forward-smoke`; every external `scripts/pre-pr` phase;
the hosted CI aggregate; deterministic owner fixtures and mutants.

**Out of scope:** suppressing or fixing the warnings themselves; changing Align diagnostics;
parallel child orchestration; a terminal UI; log rotation or deletion; compression; remote upload
outside GitHub Actions; wrapping provider/model qualifications; changing aggregate membership;
replacing installed-profile evidence; or changing any product CLI, evaluation schema, baseline
artifact, compiler pin, or Align source.

## 2. Baseline and output-volume contract

### 2.1 Reproducible baseline

Before executable changes, the direct owner was run three times at unchanged base `e0b851a` with
the pinned managed compiler at `.align-revision` `3a34febe912db5096c58c74fede36ff53f223e04`.
The host was Apple M1, arm64, macOS 26.5.2. The command form was:

```text
LIBRARY_PATH=$HOMEBREW_LIB:$OPENSSL_LIB:$ZSTD_LIB \
ALIGNC=$MANAGED_ALIGNC \
gmake layer-forward-smoke >$LOG 2>&1
```

All three runs passed and ended with LF. The full logs remain outside Git.

| Repeat | Lines (`wc -l`) | Bytes (`wc -c`) | SHA-256 |
| --- | ---: | ---: | --- |
| 1 | 922 | 185,927 | `768e829b17d490f458bb369d7b3b960a9adab2abbe9c6e07ebcd4bff798dd96b` |
| 2 | 922 | 185,927 | `b2913f633abfe69226a55390c51aeff99879285b3fa476a835c1950256176a76` |
| 3 | 922 | 185,927 | `00bb6f9987545ad2d1c1b50a92c823dcfdd798da2bf36bd9d08df070957277ab` |

The differing digests are expected because the owner prints its unique scratch path. Every run
contains the same 910 warnings: `huge struct copy=813`, `lossy conversion=96`, and
`unused import=1`. The remaining 12 lines are the command, one shim-build record, and ten useful
owner results.

A deliberately incomplete local library search path produced a separate failure observation:
status 2, 917 lines, 183,272 bytes, SHA-256
`9ea2a980b000ac0ad3880e9d3ad8e7e3db8e04a145cbeee304696b223a87a916`. Its first actionable line
was `ld: library 'crypto' not found`; two linker lines and the Make failure followed after 910
warnings. It is a diagnostic-shape observation, not an owner failure attributed to the product and
not one of the three shipping-baseline samples.

### 2.2 Pre-committed ceiling, floor, and verdict

The selected owner clears an **admission floor** of 900 lines and 180,000 bytes in every baseline
sample. A smaller owner would not justify a process wrapper in this capability.

For the same successful owner after adoption:

- terminal output excluding time-based progress has a **maintenance ceiling** of 16 LF-terminated
  lines and 2,048 bytes;
- the change must remove at least the **acceptance floor** of 900 lines and 180,000 bytes from every
  baseline sample, so measured output must also be at most 22 lines and 5,927 bytes; and
- the retained log must have the same 922 lines, 185,927 bytes, warning counts, and owner result
  lines as the baseline, and its reported SHA-256 must match its exact retained bytes. A new scratch
  path means the post-change digest need not equal a pre-change repeat. The deterministic fixture
  separately compares an unwrapped byte sequence and its wrapped retained copy exactly.

The maintenance ceiling is the stricter result and therefore owns the verdict. **MET** requires all
three conditions plus the status/signal mutants in section 5. **NOT_MET** is any ceiling breach,
insufficient reduction, changed child result, incomplete log, or digest mismatch. There is no
statistical interpolation: lines and bytes are exact integers. Tokenizer-specific token counts are
reported only as a secondary observation.

On failure, the terminal reduction is bounded to 40 LF-terminated lines and 12,288 bytes, including
the first actionable diagnostic and useful tail. One progress record per completed 60-second
interval is outside both terminal ceilings because its count is a function of commanded duration;
the record itself remains one line and at most 256 bytes.

## 3. Public-contract ledger

### 3.1 Command and inputs

The public command is:

```text
python3 scripts/run-output-summary \
  --phase PHASE \
  [--log-directory DIRECTORY] \
  [--progress-seconds SECONDS] \
  -- COMMAND [ARG ...]
```

| Field | Contract |
| --- | --- |
| `PHASE` | required ASCII `[a-z0-9][a-z0-9._-]{0,63}`; copied into every record and the log prefix |
| `DIRECTORY` | optional nonempty filesystem path; command line wins over `ALIGN_LLM_OUTPUT_DIRECTORY` |
| `ALIGN_LLM_OUTPUT_DIRECTORY` | optional explicit log directory when the CLI argument is absent; an empty value is invalid |
| default directory | `$GIT_COMMON_DIR/align-llm-output`, resolved by Git from the repository that owns the script; no `.git` directory assumption |
| `SECONDS` | integer 1..3,600; default 60; a test may select 1 without changing production defaults |
| `COMMAND` | required nonempty argv after `--`; executed directly without a shell or reinterpretation |

`PYTHONDONTWRITEBYTECODE=1` and `ALIGN_LLM_OUTPUT_SUMMARY_ACTIVE=1` are added to the child
environment. The latter prevents the direct owner from nesting another wrapper when preflight or CI
already owns the outer capture. Every other inherited variable and argv byte is unchanged. The
marker is an implementation recursion guard, not an admission or security boundary.

Validation order is command syntax, phase, command presence, progress interval, explicit or
environment directory syntax, default Git-common-directory resolution, directory admission, log
reservation, and only then child launch. Invalid input exits 2 through `argparse`; setup or capture
failure exits 125; a missing executable exits 127; another launch refusal exits 126. None of these
pre-launch failures may execute the command.

### 3.2 Process, stream, and signal ownership

The wrapper inherits stdin. It starts exactly one new child process group with the supplied argv.
The child group's stdout and stderr are duplicate descriptors for one exclusively created log file,
so all successfully written bytes share one file offset. The wrapper does not echo child bytes on
success.

The wrapper owns the child process group until wait completes. On `HUP`, `INT`, `QUIT`, `TERM`, or
`PIPE`, it forwards the same signal to the group, waits for it, finalizes any bytes already written,
and terminates itself with that signal. A child that terminates by a signal likewise causes the
wrapper to terminate by the same signal after finalization. An ordinary child exit returns the
exact 0..255 status. `SIGKILL`, host loss, and storage loss are N/A because no user-space process can
finish cleanup or preserve bytes after them.

The wrapper's own progress and terminal records go to stderr and are never part of the retained
child log. A broken stderr pipe follows the `PIPE` rule rather than being converted to success.
Concurrent independent invocations are supported: each reserves a distinct `0600` file. There is
no process-global lock and no shared mutable index.

### 3.3 Log allocation, identity, and lifetime

The admitted directory must be a real directory rather than a symlink. A missing directory is
created with mode `0700`; an existing directory is reused without changing its mode. The wrapper
uses exclusive creation for `<phase>-<random>.log`, never follows or replaces a destination, and
opens it before the child exists. The producer owns the descriptor until child wait, `fsync`,
close, digest, and summary complete in that order.

The log has no schema: its identity is the exact byte sequence written by the two child descriptors.
The summary records SHA-256, bytes, logical lines, and absolute path. `lines` is the LF count plus
one only when a nonempty final record lacks LF. Logs survive every ordinary result and are never
automatically deleted. Local cleanup is user-owned. CI writes under `$RUNNER_TEMP` and uploads the
directory as `verification-output-<run-id>-<attempt>` for 14 days with hidden files excluded and
compression level 6. The workflow pins `actions/upload-artifact` v7.0.1 at
`043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`.

If a write, flush, close, or digest read fails, the wrapper reports infrastructure status 125 and
must not claim a complete-log digest. The already-reserved partial file remains for diagnosis. This
is distinct from deliberate truncation: the implementation has no log byte cap and never discards
successfully captured bytes.

### 3.4 Terminal record format

Every wrapper-owned record is one UTF-8 JSON object followed by LF, with keys sorted
lexicographically, compact separators, and `ensure_ascii=true`. The schema version is 1.

| `event` | Required fields | Order |
| --- | --- | --- |
| `verification-progress` | `elapsed_ms`, `event`, `phase`, `version` | once after each completed interval while the child remains live |
| `verification-result` | `elapsed_ms`, `event`, `phase`, `result`, `status`, `version` | first terminal record; `result` is `PASS`, `FAIL`, or `SIGNAL`; signal status is its positive number |
| `verification-warning` | `class`, `count`, `event`, `phase`, `version` | zero or more, sorted by normalized UTF-8 class bytes |
| `verification-log` | `bytes`, `event`, `lines`, `path`, `phase`, `sha256`, `version` | after warnings |
| `verification-diagnostic-first` | `event`, `phase`, `text`, `truncated`, `version` | failure/signal only, when an actionable line exists |
| `verification-diagnostic` | `event`, `ordinal`, `phase`, `text`, `truncated`, `version` | failure/signal only; useful tail in original order |

Warning normalization is byte-oriented before UTF-8 replacement and has a fixed thirteen-class
maximum:

1. `PATH:LINE:COLUMN: warning: CLASS: DETAIL` maps the five shipped Align classes to
   `align:huge-struct-copy`, `align:lossy-conversion`, `align:unused-import`,
   `align:unnecessary-heap-allocation`, or `align:unconstrained-element-type`; every other Align
   class is `align:other`;
2. a line beginning `warning:` maps by case-insensitive content to `tool:deprecated`,
   `tool:unused`, `tool:dead-code`, or `tool:pgo`, in that precedence, and otherwise to
   `tool:other`;
3. a line beginning `hint:` becomes `git:hint`; and
4. an otherwise recognizable but unclassifiable warning becomes `other`.

All occurrences are counted; no warning is suppressed from the retained log. The fixed taxonomy
keeps the result cardinality bounded without treating a future warning's prose as a stable API.

For a failure, warning and hint lines are excluded only from terminal diagnostics. The first
actionable line is the first non-warning line containing a case-insensitive error/fatal/traceback,
launch/refusal, timeout/signal, mismatch/difference, or not-found marker. Its visible text is capped
at 2,048 UTF-8 bytes with `truncated=true`. The tail is the last non-warning logical lines, at most
24 records and 8,192 serialized bytes, with an overlong individual line truncated. The reducer then
drops the earliest tail records, never the first-actionable record, until the complete terminal
sequence is at most 40 lines and 12,288 bytes. If there is no non-warning line, the raw final logical
lines supply the tail. The full log remains authoritative.

### 3.5 Adopters

| Consumer | Adoption |
| --- | --- |
| Direct local owner | `scripts/run-layer-forward-smoke` delegates itself once unless `ALIGN_LLM_OUTPUT_SUMMARY_ACTIVE=1`; its body and argv are unchanged |
| `scripts/pre-pr` | every external `PlanStep` uses the shared Python function; existing phase-start/pass/fail JSON records, plan order, environment unsets, stamp semantics, and fail-fast behavior remain |
| Hosted CI | `Run supported project checks` invokes the CLI around the unchanged `make -j8 ALIGNC="$ALIGNC" hosted-checks` argv; the later `always()` artifact step uploads any retained logs |
| Nested execution | the preflight/CI marker makes the direct owner run its body without a second log, process group, result, or progress stream |

The aggregate target vector remains byte-identical and continues to be owned by
`scripts/check-gate-topology`. A wrapper accepts one command; it has no API with which to schedule,
filter, or reorder Make targets.

## 4. Failure and cleanup rules

| Situation | Terminal status | Log and diagnostics |
| --- | --- | --- |
| Child passes | exact 0 | complete log, warning counts, no diagnostic records |
| Child exits nonzero | exact child status | complete log, first actionable diagnostic, bounded useful tail |
| Child terminates by supported signal | same signal terminates wrapper | terminal records are attempted after complete wait and before self-signal |
| Wrapper receives supported signal | same signal is forwarded to group and terminates wrapper | bytes written before group exit are finalized; no success record |
| Output pipe closes | `SIGPIPE` | child group receives `SIGPIPE`; no conversion to status 0 |
| Launch missing / refused | 127 / 126 | empty reserved log remains; bounded wrapper error identifies launch |
| Log unavailable before launch | 125 | child is not started and no unrelated path is changed |
| Capture/finalization failure | 125 | partial log remains; no complete digest claim |

Cleanup order is: stop or observe the child group, wait for the direct child, flush and `fsync` the
writer, close the log, read it for digest/reduction, emit terminal records, then return or
self-signal. An exception follows the same cleanup from the latest acquired owner. A failure to
emit terminal output cannot delete or rewrite the log.

## 5. Closure matrix

| Cell | Implementation owner | Exact regression or evidence |
| --- | --- | --- |
| CLI formation and validation | `run-output-summary`, `output_summary.parse` | invalid phase, empty command, invalid interval, and empty env directory exit before marker side effect |
| Default directory construction | Git-common-directory resolver | ordinary clone and linked-worktree fixtures resolve one common log namespace without assuming `.git` is a directory |
| Explicit directory construction | log reservation | missing real directory is created; file/symlink directory refuses before child launch |
| Concurrent construction | exclusive random log reservation | two independent wrappers retain distinct complete files |
| Child move-in | exact argv plus two named environment additions | fixture records argv including spaces/empty values and environment; no shell expansion occurs |
| Success | child exit 0 | exact log bytes/digest/lines, three normalized warning classes, PASS and original result lines |
| Ordinary failure | child exit 23 | wrapper exits 23, never PASS, retains complete log, and exposes early actionable plus final tail |
| Missing executable | launch path | status 127, child-side marker absent, empty exclusive log retained |
| Child signal | child sends `TERM` and `PIPE` to itself | wrapper return code is the same negative signal; no ordinary-success conversion |
| Supervisor early exit | parent signals live wrapper | signal reaches child group, cleanup marker appears, and wrapper terminates by the original signal |
| Long-running progress | one-second test interval | at least one progress record precedes terminal result; production default remains 60 seconds |
| Warning normalization | Align, tool, hint, malformed lines | exact sorted classes and counts; raw log remains byte-identical |
| Malformed UTF-8 / embedded NUL output | byte log plus JSON reducer | log digest is exact; visible text uses JSON escaping and replacement without multiline injection |
| First actionable diagnostic | early error followed by more than 8,192 warning/hint bytes | early error remains visible and final useful tail remains within both failure ceilings |
| Complete-log mutation | expected bytes versus retained file | deletion/truncation mutant changes bytes/digest and fails the owner |
| Exit-status mutation | nonzero child versus wrapper result | zero-on-failure mutant fails the owner |
| Diagnostic mutation | expected early marker versus terminal JSON | first-line-loss mutant fails the owner |
| Aggregate order mutation | unchanged Make vector and topology owner | `check-gate-topology --self-test` plus workflow regression require the original target order and exact wrapped argv |
| Preflight success/failure | injected `PlanStep` commands | shared runner is called in plan order, environment unset is honored, first failure stops later phases, and stamp remains post-success only |
| Nested direct owner | active marker | preflight/CI capture exactly one log and one result sequence for the owner |
| CI retention success/failure | workflow topology fixture | artifact step is `always()`, names the exact temp directory, and cannot change the supported-check result |
| Return / cleanup | descriptor and process-group owners | success, nonzero, launch error, signal, and summary-pipe fixtures leave no live child and never overwrite a prior log |

Generic monomorphization, Align move/source nulling, native FFI, runtime allocation parity, interface
serialization, provider networking, evaluation documents, and product persisted formats are N/A:
the implementation is Python orchestration around existing opaque argv and changes no Align or
product data type.

## 6. Verification, review, and delivery

The narrow deterministic owner is:

```text
python3 scripts/test-output-summary
```

The existing workflow owner also runs because `scripts/pre-pr` and `.github/workflows/ci.yml` change:

```text
python3 scripts/test-development-preflight
```

The local consumer measurement uses the section 2.1 environment and:

```text
gmake layer-forward-smoke >$VISIBLE 2>&1
```

The deterministic owner compares the retained file to an unwrapped same-byte fixture. The real
consumer measurement checks baseline line/byte/warning/result invariants, the retained digest, and
exact visible lines/bytes against section 2.2. `git diff --check` and Python syntax compilation
accompany the focused owner. `make ci` is not selected as a manual development ritual; the changed
workflow and preflight paths select their normal fresh-image publication lane, including hosted
checks, fresh-focused, and the installed profile.

Publication command:

```text
python3 scripts/pre-pr --owner-test DEV-OUTPUT-SUMMARY -- \
  python3 scripts/test-output-summary
```

One comprehensive review covers the design, process/signal ownership, retained bytes, reducer,
direct-owner recursion guard, preflight integration, workflow artifact lifetime, tests, and measured
claim. The pull request records the reviewed head/base/merge base, all finding dispositions, exact
owner and publication evidence, and the post-change output measurement.

## 7. Deferred work

- Other individual noisy owners may adopt the shared wrapper after their own exact baseline; this
  capability does not mechanically wrap every script.
- `fresh-align-compiler` may replace its diagnostic-only 8,192-byte aggregate seam with this shared
  path only in a separately reviewed worker/image boundary change.
- Local retention pruning needs an explicit age/size policy and is not inferred from CI's 14-day
  artifact retention.
- Warning remediation belongs to the modules that emit each class. A count is visibility, not a
  waiver or suppression policy.
