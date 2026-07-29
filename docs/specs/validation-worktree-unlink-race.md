# Validation worktree unlink race

## 1. Scope and audited state

This enabling slice makes the coding-task resource monitor tolerate a validator removing a visible
worktree entry between directory enumeration and metadata inspection, or removing a queued
descendant directory before its scan begins. It does not weaken the file-count or byte ceilings,
change sandbox ownership, change post-validation mutation detection, or make an unreadable existing
path optional.

The design was audited against align-llm merge commit
`34eac179f0bbe0036aacbcb62296509c93e93a40` and pinned Align commit
`d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`. The implemented surface is
`eval/runners/run-coding-task.py`; no Align language or standard-library change is required.

The runner is a canonical coding-v1 baseline artifact. Its implementation and the identity-coupled
baseline refresh therefore form one independently mergeable implementation pull request with
separate source, oracle, and finalization commits. Merging the runner fix without that refresh would
leave `main` failing its own baseline artifact check.

## 2. Public and implementation contract

| Surface | Exact contract |
| --- | --- |
| Coding-task CLI | Unchanged: `run-coding-task.py TASK_JSON CANDIDATE_PATCH`. No test flag, schema field, environment input, or diagnostic is added. |
| Resource-monitor success | Exclude the checkout root's read-only `.git` entry before metadata inspection, count every other entry whose metadata is obtained, enforce the existing 8,192-entry and 64-MiB ceilings, retain visible regular-file inode accounting, and continue periodic scans while validation runs. A nested `.git` name is ordinary writable-worktree content and is not excluded. |
| Entry disappearance | If a real `os.DirEntry` disappears after its parent `scandir` yielded it but before `DirEntry.stat(follow_symlinks=False)`, skip that entry for the current scan. It no longer occupies visible worktree storage; a later polling scan accounts for any path that exists then. |
| Queued-directory disappearance | If a non-root directory was successfully observed and queued, then `os.scandir` raises `FileNotFoundError` when that queued path is popped, skip that directory for the current scan. |
| Fail-closed errors | A missing checkout root, any `OSError` other than the two descendant/entry `FileNotFoundError` cases, deadline exhaustion, or a ceiling violation retains `TaskError` behavior and a bounded English diagnostic class. This includes scan construction, iterator advancement, metadata, and iterator close errors. Iterator-time `FileNotFoundError` is not a skip case. |
| Post-validation mutation checks | Unchanged. `directory_modes`, Git/index checks, and worktree snapshots still reject validator side effects after the process has completed. This slice changes only the concurrent resource scan. |
| Deterministic test seam | `validation_worktree_usage` accepts implementation-only keyword scan and monotonic-clock callables whose defaults are the real `os.scandir` and `time.monotonic` captured at function definition. Production passes neither override. The scan seam changes only directory enumeration; race cases use real temporary filesystem entries and real `DirEntry.stat`, while fail-closed operation cases use narrow delegating wrappers that inject the named `OSError`. The clock seam changes only deadline observation and uses a test flag rather than sleeping. |
| Regression command | `python3 scripts/run-coding-task-resource-scan-smoke` starts a fresh Linux process, snapshots existing runner-directory `__pycache__` paths and `*.pyc` bytes, enters one helper-owned temporary-directory scope, proves the stale-cache sentinel below while restoring normalized interpreter state, reads and executes the production runner's exact source bytes through a `compile`/`exec` source-only loader with non-`__main__` module identity, and runs all numbered cases below without a global monkeypatch. Each case has its own five-second `ITIMER_REAL`; every case timer is canceled, the prior signal handler is restored, and helper-owned temporary state is removed on success or failure before the outer runner-cache snapshot is verified byte-for-byte unchanged. The command prints one English PASS line. `scripts/run-coding-task-invalid-smoke` invokes it so `eval-coding` owns the regression. |

### 2.1 Ownership, counting, and race semantics

`validation_worktree_usage` continues to own its local pending stack, counters, deadline, and visible
inode set. The scan callable owns construction; successful entry of its returned context manager
transfers ownership of the entered iterator to `validation_worktree_usage`. The context manager's
exception-table cleanup attempts `close` after normal exhaustion, entry failure, iterator failure,
deadline failure, or an unexpected exception. Scan-construction or context-entry failure transfers
no iterator. No iterator, `DirEntry`, path, descriptor, or temporary file escapes the call.

The scan has snapshot-like but not atomic semantics. A closed, unlinked file or fully removed
directory consumes no current worktree storage and may be absent from one poll. A renamed or
recreated path that remains in the checkout is eligible for a later poll. Deleted-but-open regular
files remain accounted separately through `/proc/<pid>/fd`; that logic is unchanged.

The skip is deliberately narrow:

1. `FileNotFoundError` from an individual entry's real `stat` skips that entry;
2. `FileNotFoundError` from scanning a queued path skips it only when the path is not the checkout
   root;
3. iterator-advance `FileNotFoundError` is a directory-enumeration failure, not an entry or
   queued-construction disappearance, and remains fatal;
4. root `FileNotFoundError`, `PermissionError`, `EIO`, close errors, and every other `OSError`
   retain a `cannot inspect validation ...` failure.

The monitor checks its captured monotonic deadline before every pending scan and after every
potentially blocking scan construction, iterator advance (including the advance that reports normal
exhaustion), metadata call, and iterator close. It also checks before accepting either disappearance
skip. If an operation crosses the deadline, the time-limit diagnostic wins over that operation's
success, exhaustion, disappearance, or other `OSError`. Otherwise, an iteration or entry error
remains primary if iterator close also fails; a close error becomes the primary `TaskError` only
when scan-body processing had no error.

Only a pending directory scan has a separate pre-operation clock read. Iterator advance, metadata,
and close proceed from the preceding in-budget adjudication and are checked immediately after their
result or error. The contract does not claim that those calls can never begin after wall-clock
expiry: a scheduler may suspend execution after any clock read. Their post-operation check owns
such delay and deterministically prevents the late result or error from being accepted.

File count increments only after metadata succeeds, exactly as before. A directory whose metadata
succeeds counts as one entry even if it disappears before its queued scan. Files that were inside
that vanished directory but were never yielded do not count. Size and visible-inode accounting
remain limited to successfully inspected regular files.

The existing root-only `.git` exclusion is not a disappearance skip. After a root iterator advance
remains within deadline, `entry.name == ".git"` is excluded before path construction, metadata,
count, size, or inode accounting because sandboxed Git metadata is read-only. The same name below
the checkout root is not excluded and follows the ordinary metadata and counting path.

### 2.2 Deterministic regression cases

The regression helper loads `eval/runners/run-coding-task.py` by reading its bytes, compiling those
bytes with the real path as the diagnostic filename, and executing the code in a fresh
`types.ModuleType` namespace whose `__file__` is the real path and whose `__name__` is a fixed
non-`__main__` value. It does not use importlib's source-file loader or consult an import cache. The
helper saves the real `os.scandir` callable before constructing wrappers and passes each wrapper
through the implementation-only seam. It does not replace `os.scandir` globally.
Every returned wrapper implements context-manager, iterator, and `close` behavior, records whether
close was attempted, and delegates real entries to the saved scanner. Deadline cases share one
ordered event log: the scan wrapper, iterator, entry/metadata proxies, close method, and injected
clock append their named operation or clock-read event. Each case asserts the exact relevant trace
prefix, so a later deadline read cannot stand in for the required post-operation adjudication.

1. **Stable control** — one stable regular file returns its exact size, count one, and exact
   `(st_dev, st_ino)` set; the wrapper records close after normal exhaustion.
2. **Entry disappears before stat** — the wrapper opens a real scan of the checkout, unlinks one
   named regular file immediately before yielding its real `DirEntry`, and yields a stable file
   normally. The result contains only the stable file's size, count, and inode. The transient path
   is absent afterward.
3. **Queued directory disappears before scandir** — the root iterator yields a real descendant
   directory. When the function later asks to scan that exact queued path, the wrapper removes the
   directory tree immediately before calling the saved real `os.scandir`, forcing its real
   `FileNotFoundError`. The already inspected directory counts once; its never-yielded child does
   not contribute bytes or an inode; stable root content remains exact.
4. **Missing root** — a nonexistent checkout root still raises `TaskError` with the existing
   `cannot inspect validation directory` class.
5. **Entry-stat non-disappearance error** — the iterator yields a proxy for one real entry that
   delegates its name and path but raises `PermissionError` from `stat`. The call raises `TaskError`
   with the worktree-path inspection class and records iterator close; it must not treat the error
   as a disappearance.
6. **Queued non-disappearance error** — a wrapper raises `PermissionError` for an existing queued
   descendant. The call still raises `TaskError` with the existing directory-inspection class.
7. **Iterator-advance errors** — separate context-compatible wrappers over a real root scan raise
   `PermissionError` and `FileNotFoundError` from `__next__` after construction. Each call raises
   `TaskError` with the directory-inspection class, does not emit a traceback, and records close.
   In particular, iterator-time `FileNotFoundError` must not enter either disappearance skip.
8. **Iterator-close errors** — separate wrappers complete a stable real scan and then raise
   `PermissionError` or `FileNotFoundError` from `close`. Each call raises `TaskError` with the
   directory-inspection class and records that close was attempted. In particular, close-time
   `FileNotFoundError` must not enter either disappearance skip.
9. **Deadline before queued-disappearance skip** — the checkout has exactly one visible entry: the
   descendant directory that becomes the sole queued pending item. The injected clock returns a
   constant start time until the queued-path wrapper removes that real directory and flips one flag
   immediately before saved real `os.scandir` raises `FileNotFoundError`; thereafter it returns a
   value beyond `MAX_RESOURCE_SCAN_SECONDS`. The event log proves the construction-error event is
   followed by its clock-read event and then terminates with no later operation. The deadline
   diagnostic wins instead of accepting the skip. If the target post-error read is omitted, the
   disappearance skip empties the pending stack and incorrectly returns success, so no later legal
   clock read can mask the omission. No sleep or scheduler timing is involved.
10. **Deadline at pending boundaries** — in an initial-root subcase, the injected clock returns the
    start value for deadline capture and an expired value at the first pending-item check; the exact
    time-limit diagnostic occurs before the scan callable is invoked. In a queued-item subcase, two
    real descendant directories are queued. The first queued scan is removed and skipped while the
    injected clock remains within budget, then the wrapper flips the clock flag. The next pending
    item fails with the deadline diagnostic before its scan callable is invoked.
11. **Body plus close errors within budget** — separate wrappers raise a body
    `PermissionError` from iterator `__next__` or a delegating real-entry `stat`, then raise a second
    distinct `PermissionError` from `close`. Close is attempted in both subcases, but the respective
    iterator- or entry-inspection diagnostic remains primary.
12. **Successful post-operation deadline boundaries** — table-driven wrappers flip the injected
    clock from the constant start time to an expired value immediately after exactly one successful
    operation: root scan construction; an iterator advance that yields a real stable entry; iterator
    exhaustion that raises normal `StopIteration`; a delegating real-entry `stat`; or iterator
    close. Each subcase raises the exact time-limit diagnostic, records close whenever iterator
    ownership transferred, and asserts the exact target-operation → clock-read ordering before any
    subsequent body operation. Construction records no iterator advance before that read; yielded
    advance records no entry-attribute access; normal exhaustion records the clock read before
    close; stat returns a metadata proxy whose `st_mode` access would fail and records the read
    before close; close records its clock read immediately afterward. The other operations in that
    subcase leave the clock within budget. Thus a later check cannot substitute for an omitted
    target post-operation check. A further yielded-advance variant establishes the time-limit
    diagnostic at that advance's post-operation read and then raises `PermissionError` from
    iterator close. Its exact trace records the close attempt and close error, but the already
    established time-limit diagnostic remains primary instead of being replaced by the cleanup
    error.
13. **Error-result deadline dominance** — table-driven wrappers cover every remaining
    error-classification boundary while flipping the injected clock to an expired value:
    root scan construction produces real `FileNotFoundError`; scan construction raises
    `PermissionError`; iterator `__next__` raises `FileNotFoundError` or `PermissionError`; a real
    entry is unlinked before its delegated `stat` raises `FileNotFoundError`; a delegating
    real-entry `stat` raises `PermissionError`; or iterator `close` raises `PermissionError`.
    Each subcase produces the exact time-limit diagnostic rather than its root/descendant,
    disappearance, exhaustion, or operation-error classification, and records close whenever
    ownership transferred. Case 9 separately covers queued-scan-construction `FileNotFoundError`
    plus the expired clock, completing the construction outcome branches. Each subcase also asserts
    the target error event is followed by its clock-read event before root/descendant,
    disappearance, or operation-error classification and before close, so close's later deadline
    check cannot mask an omitted error-result check.

    Four further subcases first raise a distinct body `PermissionError` from iterator `__next__` or
    delegating real-entry `stat`, then have `close` cross the deadline and either succeed or raise a
    second distinct `PermissionError`. Every body kind × close result subcase records the close
    attempt and produces the time-limit diagnostic, proving that close-time expiry wins over both a
    prior body error and an optional close error.
14. **Visible byte ceiling** — one real sparse regular file is first truncated to exactly
    `MAX_VALIDATION_WORKTREE_BYTES`; a wrapper-backed call succeeds with that exact size, count one,
    and inode, and records close. Extending the same file by one byte makes the next call fail with
    the writable-worktree size diagnostic and record close. Three further plus-one subcases have
    close raise `PermissionError` within budget, flip the clock to expired and succeed, then flip
    the clock to expired and raise `PermissionError`; the size diagnostic remains primary in the
    first, while the exact time-limit diagnostic wins in both expired subcases, and all record
    close.
15. **Visible count ceiling** — one real checkout contains exactly
    `MAX_VALIDATION_WORKTREE_FILES` empty regular files directly under its root; a wrapper-backed
    call succeeds with count equal to the ceiling and zero bytes, and records close. Adding one more
    real empty file makes the next call fail with the writable-worktree file-limit diagnostic and
    record close. Three further plus-one subcases have close raise `PermissionError` within budget,
    flip the clock to expired and succeed, then flip the clock to expired and raise
    `PermissionError`; the count diagnostic remains primary in the first, while the exact
    time-limit diagnostic wins in both expired subcases, and all record close. The test does not
    lower or replace the production constant and does not synthesize repeated entries.
16. **Root-only `.git` exclusion and order** — one root wrapper yields a proxy for a real `.git`
    directory whose `name` is `.git`, but whose `path` and `stat` accessors record access and raise
    `PermissionError`, plus one stable real file. With the clock in budget, the scan succeeds with
    only the stable file's exact count, size, and inode, and neither forbidden accessor is reached,
    proving exclusion precedes path construction and metadata. In a deadline subcase, the iterator
    flips the clock to expired immediately after yielding a root `.git` proxy; the call returns the
    exact time-limit diagnostic, records iterator close, and records no access to even `name`,
    `path`, or `stat`, proving deadline adjudication precedes the exclusion branch. A separate real
    checkout contains a nested `.git` directory and one regular file inside it; both nested entries
    are inspected and counted, and the file contributes its exact bytes and inode, proving the
    exclusion is not name-global.
17. **Owner-scope asynchronous interruption** — two trace hooks bound to the exact executed runner
    bytes raise a helper-owned `BaseException` at the owner boundaries. The first enables opcode
    tracing and interrupts `STORE_FAST entries` immediately after the scan context successfully
    enters but before the entered iterator is bound for body processing. It runs once with
    successful close and once with close raising `FileNotFoundError`; both retain the original
    helper exception, and the close error cannot enter the descendant-disappearance skip. The final
    subcase has a wrapper raise a body `PermissionError`, then interrupts its body-error capture
    before ordinary post-body control can begin cleanup. The helper observes the exact exception
    and records iterator close in all three subcases, proving context-manager cleanup covers both
    the entry-to-binding and post-capture boundaries. The prior trace function is restored in a
    `finally` after each subcase.

Every case has a fresh subtree and an exact result or diagnostic assertion. Before loading the
runner, the helper snapshots existing `__pycache__` directory paths and the relative path plus
SHA-256 of every `*.pyc` below `eval/runners`. It never deletes or rewrites pre-existing caller
files, and an outer `finally` fails the command if that exact cache snapshot changes on success or
failure.

Before the runner cases, the helper proves its source-only loader independently in a helper-owned
temporary directory. It writes and imports an `OLD` source once through Python's ordinary import
machinery to create a valid timestamp-based `.pyc`. Around only the sentinel's ordinary-import
operations, it saves `sys.dont_write_bytecode` and `sys.pycache_prefix`, sets them to `False` and
`None`, respectively, and restores both in a `finally` on sentinel success or failure. It asserts
that the expected helper-owned cache exists, records its exact bytes, then replaces the source with
same-length `NEW` content and restores the source timestamp. A fresh ordinary-loader module
namespace must expose the cached `OLD` sentinel, proving that the stale cache is valid; the
source-only loader must then expose the current-source `NEW` sentinel. The pre-existing `.pyc` must
remain byte-identical and no new cache path may appear. After the `finally`, both interpreter values
must equal their saved values. Only then is the production runner loaded through that same
source-only function.

The helper enters one `TemporaryDirectory` owner scope before creating the loader fixture or any
numbered-case subtree. Inside it, the helper saves and replaces the `SIGALRM` handler.
It arms a fresh five-second `signal.setitimer(signal.ITIMER_REAL, ...)` immediately before each
numbered case and cancels that timer in the case's `finally`, so the 8,192-entry boundary case
receives its own full bound rather than consuming a shared cumulative budget. Its handler raises a
helper-owned exception in the main thread so iterator contexts unwind. An enclosing `finally`
cancels any remaining timer and restores the prior handler before control leaves the
temporary-directory scope, so recursive cleanup cannot be interrupted by the owned alarm. Failure
is reported after cleanup as one bounded English line without a traceback. The process is
Linux-only for the same reason as the runner it tests. Unexpected success, a traceback, an unclosed
wrapper, a leaked path, or any different count/size/inode result fails the command.

### 2.3 Baseline identity and commit topology

The implementation pull request follows the canonical source → oracle → finalization history from
`docs/specs/check-gate-topology.md` section 2.4:

1. a clean source commit contains the final runner, deterministic regression helper, invalid-smoke
   invocation, runner documentation, and durable handoff;
2. record two deterministic-reference coding-v1 samples from that exact source commit into the
   uncommitted pending path;
3. commit only the exact immutable-oracle projection;
4. finalize against the full oracle commit, remove the pending file, and commit only the canonical
   baseline plus digest;
5. preserve source, oracle, and finalization commits as ancestors with a merge commit.

All raw-commit, persisted-identity, path-history, replacement-object isolation, byte-equality,
pending-file absence, structural outcome, and negative-harness requirements from that section apply
unchanged. The source commit changes `eval/runners/run-coding-task.py`, so the pending record's
`align_llm_commit` and runner digest must name those exact bytes. The two samples must remain passing
and structurally equal to the fixed corpus expectation. Report old and new timings without a
performance claim.

## 3. Validation and error order

Within one resource poll, existing process-count and resident-memory validation runs before
worktree usage, followed by deleted-open-file accounting and the aggregate file/byte checks. This
slice does not reorder those stages.

Within `validation_worktree_usage`, the monitor checks before every pending directory scan and after
every potentially blocking scan construction, iterator advance, metadata call, and close. It does
not add a separate pre-operation read for iterator, metadata, or close. After an iterator advance
remains within deadline, the checkout root's `.git` entry is excluded before path construction or
metadata inspection. Every other entry follows metadata inspection, count ceiling, directory
queueing, regular-file filtering, byte accumulation, inode recording, and byte ceiling in that
order. Disappearance skips only the unavailable entry or queued descendant and proceeds to the next
pending item. A deadline crossed during an operation wins before its result or error is classified;
otherwise a non-disappearance error fails immediately and no later count or byte diagnostic
replaces it. Iterator close is always attempted; without a crossed deadline, a preexisting body
error wins over a simultaneous close error, while a close-only error becomes the
directory-inspection failure.

## 4. Closure matrix

| Path | Owner | Intended implementation | Regression evidence |
| --- | --- | --- | --- |
| Stable scan | runner | default real scan callable and unchanged counters | Stable control asserts exact bytes, count, and inode. |
| Root `.git` exclusion | runner | after the yielded-entry deadline check, exclude only `current == checkout and entry.name == ".git"` before path construction, metadata, or accounting | An in-budget root proxy fails on `path`/`stat` access but is excluded with stable content exact. An expired-after-yield root proxy reaches the time-limit diagnostic with no `name`/`path`/`stat` access and with close recorded. A separate nested real `.git` directory and file are both counted. |
| File-entry disappearance | runner | catch only `FileNotFoundError` from `DirEntry.stat` and continue | Real `DirEntry` is unlinked immediately before yield; exact stable-only result passes. |
| Queued-directory disappearance | runner | catch `FileNotFoundError` from non-root scan and continue | Real queued tree is removed immediately before saved real `os.scandir`; directory-only count plus stable result passes. |
| Missing root | runner | do not apply descendant skip to `current == checkout` | Nonexistent root reaches existing `TaskError` class. |
| Existing unreadable entry | runner | every entry-stat `OSError` except `FileNotFoundError` remains fatal | Delegating real-entry proxy raises `PermissionError` from `stat`; exact worktree-path `TaskError` and close record pass. |
| Existing unreadable descendant | runner | every non-`FileNotFoundError` `OSError` remains fatal | Injected `PermissionError` on an existing queued directory reaches existing `TaskError` class. |
| Iterator advancement | runner | translate iterator `OSError`, including `FileNotFoundError`, to directory-inspection `TaskError` inside an explicit closing owner scope | Separate wrappers raise `PermissionError` and `FileNotFoundError` from `__next__`; both exact error classes and close records pass. |
| Iterator close | runner | attempt close in `finally`; close-only `OSError`, including `FileNotFoundError`, becomes directory-inspection `TaskError`, while an existing body error remains primary within budget | Separate close-only `PermissionError`/`FileNotFoundError` cases plus iterator-body/close-error and stat-body/close-error wrappers assert exact fatal classification, in-budget precedence, and close-attempt records. |
| Deadline | runner | injected monotonic callable defaults to captured real clock; check before each pending scan and after construction, every advance including normal exhaustion or error, stat, and close, before root/descendant, exhaustion, disappearance, or operation-error classification; a separate no-start guarantee for advance/stat/close is N/A because scheduler suspension can follow any pre-operation read and their post-operation adjudication owns that delay | The construction matrix covers success, root FNF, descendant FNF, and generic `OSError`; the iterator matrix covers yielded success, normal exhaustion, FNF, and generic `OSError`; the stat matrix covers success, FNF, and generic `OSError`; the close matrix covers success and generic `OSError`. Prior iterator/stat, count-ceiling, and byte-ceiling body errors are each combined with both close success and close error crossing the deadline. A yielded-advance post-operation timeout is also followed by a close `PermissionError` and must retain the already established time-limit diagnostic. Every crossed subcase requires the exact time-limit diagnostic without sleep and an event trace proving the target operation/error's clock read occurs before any later operation or classification; separate initial-root and queued-item pending-boundary subcases prove rejection before either scan callable is invoked. Existing coding-task resource-limit coverage remains passing. |
| File-count and byte ceilings | runner | unchanged post-stat count and regular-file size checks inside the explicit iterator owner scope | Real sparse-file exact-limit/plus-one calls prove the visible byte boundary. Real 8,192-entry/8,193-entry calls prove the visible count boundary without test-only limit substitution. Wrapper records prove normal and ceiling exits close; per-ceiling close-error subcases preserve the body diagnostic within budget, and close-expiry subcases select the time-limit diagnostic. Existing deleted-open-file smoke remains passing. |
| Deleted-open file | runner `/proc` accounting | unchanged inode de-duplication and descriptor scan | Existing 65-MiB deleted-open-file regression remains passing. |
| Production seam | runner caller | default captured real `os.scandir`; no production override | Source review and full coding-v1 run confirm no test callable enters production dispatch. |
| Iterator cleanup | runner plus helper | enter the context manager returned by the scan seam directly; successful context entry transfers iterator ownership to `validation_worktree_usage`, and the `with` exception table owns close before binding or body processing; if close replaces a pre-binding interruption, recover the original exception from its explicit exception context and adjudicate it as the body error | Stable success, entry disappearance, iterator/stat errors, count/byte ceiling exits, close errors, dual errors, and deadline exits assert close. Exact-source trace interruptions at the entered-iterator store opcode with close success and close `FileNotFoundError`, plus interruption during body-error capture, assert close and preserve body-error precedence; helper exits with no leaked path. |
| Runner source identity and import state | helper | read/compile/exec exact runner source bytes in a fresh non-`__main__` module namespace without importlib cache lookup; snapshot runner-directory `__pycache__` paths and `*.pyc` hashes; retain pre-existing caller files; verify the snapshot in an outer `finally`; save, normalize, and finally restore `sys.dont_write_bytecode` and `sys.pycache_prefix` around only sentinel ordinary imports | Under ambient bytecode-disabled and redirected-cache settings, a helper-owned timestamp cache exists before same-length/same-mtime source replacement, a fresh ordinary loader exposes cached `OLD`, and the source-only loader exposes current-source `NEW`, while the old `.pyc` remains byte-identical and no cache path appears. Success and injected sentinel failure restore both interpreter settings before any production-runner load. Focused helper success and failure leave the runner-directory cache snapshot unchanged; the later clean source commit and baseline recorder precondition remain clean. |
| Regression deadline and temporary cleanup | helper | acquire temporary owner first; arm one fresh five-second alarm per numbered case; cancel in each case `finally`; helper-owned alarm raises in the main thread; an enclosing `finally` cancels again and restores the handler before temporary cleanup | Source review maps acquisition, setup, success, assertion/OSError, alarm, per-case cancellation, final cancellation, handler restoration, and unarmed recursive cleanup; every ordinary success/error case asserts wrapper closure and no leaked subtree. Abrupt external `SIGKILL` cleanup is N/A because no external-kill contract is claimed. |
| Post-validation mutation | existing runner checks | unchanged | Existing invalid-smoke mutation cases remain passing. |
| CLI/schema/environment | N/A | no public input or output change | Existing arity/schema/environment negative cases remain passing. |
| Align ownership/language | N/A | Python runner-only slice | Pinned Align build and `make ci` pass; no Align request is needed. |
| Baseline source identity | canonical baseline flow | clean source commit contains final runner bytes | Pending runner digest and `align_llm_commit` equal isolated source bytes and commit. |
| Oracle/finalization ancestry | canonical baseline flow | separate oracle and finalization commits, merge-only integration | Full section-2.4 provenance block and negative harness pass before and after merge. |

## 5. Acceptance and pull request boundary

The design and implementation are separate pull requests. After this design merges, the
implementation pull request:

- changes only the runner, deterministic helper, invalid-smoke invocation, runner documentation,
  durable handoff, and identity-coupled baseline outputs described above;
- runs `python3 scripts/run-coding-task-resource-scan-smoke`;
- runs `scripts/run-coding-task-invalid-smoke` and `make eval-coding`;
- records, projects, and finalizes the baseline from the final clean source commit;
- runs `make baseline-check`, the complete structural provenance/negative harness from
  `docs/specs/check-gate-topology.md` section 2.4, and `make ci`;
- obtains a fresh independent adversarial review of the exact source/oracle/finalization chain and
  final pushed diff; and
- merges only with a merge commit that preserves all three identity commits.

After merge, refreshed `main` must pass the same ancestry, persisted-identity, byte-equality,
pending-absence, baseline, and focused race checks. Only then may the topology implementation
integrate main and record its own later Makefile-bound baseline.
