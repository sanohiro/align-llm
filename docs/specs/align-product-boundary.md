# Align product implementation boundary and migration

Status: native product cutover and A0–A6 acceptance pass at the 2026-09-13 checkpoint.
One comprehensive review identified two source-binding defects; the consolidated repair enforces
the existing TREE/source/repository contract and passes affected functional and relocated owners.
The user requested an audit and settled plan before implementation, with one concentrated
product cutover. This document owns the migration contract; the
[architecture](align-llm.md) owns the permanent language boundary and the
[roadmap](roadmap.md) owns priority. [Audit](../python-boundary-audit.md) and its
machine-readable inventory record observed code, not a compliance claim.

## 1. Outcome and delivery boundary

`ALIGN-PRODUCT-CUTOVER` delivers one usable operation: evaluate parent/candidate prompts against
a repository task, obtain edits from an existing provider, apply and validate them, repair within
the declared budget, score, publish evidence, accept the candidate, and roll back. All application
decisions execute in Align. Indexing, generation, verification, persisted results, packing, and
runtime commands retain their existing Align implementations and public behavior unless a ledger
row below explicitly changes the contract.

The evaluator, its task adapters, snapshot/source helpers, and the product use of the coding-task
runner migrate together. An Align wrapper invoking a Python feature implementation is not an
intermediate shipping outcome. Internal compiling, owner-tested commits are checkpoints; helper
modules, schema cells and adoption tests do not imply separate PRs. A larger change is justified
because splitting this chain would preserve the wrong execution boundary and repeatedly qualify
the same process, artifact and repair contracts. One comprehensive review covers the stable
consumer-complete candidate, followed by consolidated repairs under `CLAUDE.md`.

This preparation delivers the audit, authoritative language rule, migration ledger, closure matrix,
Align requests, and the contract for a development-only architecture checker. It does not implement
features, change `.align-revision`, regenerate historical evidence, run GPU campaigns, or claim
the final Python-free acceptance. No product or tooling implementation belongs to preparation.
The checker is the first implementation checkpoint on the later cutover branch.

## 2. Entry prerequisites and concentration of work

1. **BOUNDARY-PREPARE (complete):** inspect all Python files and production launch paths;
   freeze known violations; settle responsibilities and acceptance; record genuine Align gaps.
2. **ALIGN-PREREQUISITES:** request the capabilities in Requests 29, 53, 64, 65 and 66 together
   as one real-client requirement. Request 53's remaining directory operations are
   also needed; its existing `read_dir` is not complete hostile-tree enumeration. Adopt merged
   prerequisites in one pin wave, preserving each request's originally named owners. No consumer
   code may call proposed APIs. Language work is a distinct repository/failure domain, not a
   reason to publish a partial application rewrite.
3. **ALIGN-PRODUCT-CUTOVER:** first implement the narrow architecture checker, then admission,
   workspace/edits, verification/repair, evaluator,
   publication, offline verification and CLI adaptation on one branch. Reuse the current Align
   renderer/scorer/provider/persistence modules. Share policy between the current verification
   loop and evaluator without forcing their distinct task adapters to have identical inputs.
4. **Cutover acceptance and retirement:** part of the same capability, not a later cleanup PR.
   Switch documented recipes and newly authored corpora, remove the production launch, freeze
   retained historical adapters as external replay only, pass Python-free execution and independent
   result validation, then remove the migration allowances.

Safe work while prerequisites are unavailable: test-vector design, independent oracle isolation,
the prerequisite-independent A0 architecture guard, application algorithms using already shipped
interfaces, and schema/owner verification. Product
feature additions to Python are prohibited. The 2026-09-12 merged adoption removes the active
compilation blockers; application integration and final acceptance remain. No workaround in C,
shell, a helper service, or an installed Python supervisor can satisfy the missing application
boundary. No calendar promise is made before the prerequisite delivery is known.

## 3. Public contract ledger

### Merged toolchain adoption

The current adoption selects merged Align `f502fe3da00ce0b39c4eeec40586b11688627fbd`
(PRs #1033/#1034). Managed release compiler/runtime materialization and verification
pass. `scripts/run-product-cutover-adoption-smoke` checks ordinary/per-unit source
admission and executes shared optional commands, independently owned JSON, written
initializer order, root-array parity/bounds and `fs.open_regular` on macOS/Linux.
The R86 optional move-after-use negative remains a recorded nonblocking compiler
residual; product code binds the digest before consuming the measurement and does
not rely on acceptance of that invalid pattern. R86 is not marked consumer-verified.

The earlier prerequisite adoption evidence follows for continuity.

The 2026-09-12 adoption selects Align PR #1027, merged commit
`1f0627bbb10bd305ecc497d5c21cd25a611c139c`. Managed compiler/runtime verification and
the source-collection, task-input, evaluation-input and measurement-assembly smoke owners pass
on macOS and on an exact Linux ARM64 source build. This discharges the prior R81/R83 compilation
blockers; final A2 consumer acceptance remains required. R78 is explicitly deferred and nonblocking.

`prompt_validation_attempt.run` now connects retained source copy (128 entries/64 MiB),
deterministic Git setup, the prepared containment probe and task validation. Its borrowed private
workspace, patch, signal subscription, tool images and commands remain evaluator-owned. The result
transfers any interrupted scope in a phase-specific sum arm; ordinary errors are returned only
where the composed owners retain no live scope. No storage deletion or signal restoration occurs
implicitly. `scripts/run-prompt-validation-attempt-smoke` covers success, test/baseline failure,
patch/policy refusal, probe failure, timeout, wrong revision, unsafe source and explicit cleanup.
The nine Linux cases pass with trusted fixture commands; macOS builds and reports unavailable.
This is an application integration checkpoint, not installed A3 containment or final Python removal.

`prompt_snapshot.observe` composes retained FILE/TREE observation, workspace admission,
before/after host probes and conditional Git revision/clean checks. Its caller-owned digest builder
is discarded unless the complete file set matches; no partial set authorizes execution. The
snapshot owner checks independent digest preimages, mode/content/path/type refusals, occupied or
outside workspaces, clean/dirty/wrong-revision Git and the explicit skip-Git request on Linux.

`prompt_edit_plan.build` admits the complete FILE response before reading pinned source, preserves
the 262144-byte original/body limits, and builds raw whole-file patch bytes separately from redacted
edit evidence. Refusals retain their stable diagnostic text and relevant normalized path. The
caller owns the output builder and discards partial results on failure. The edit-plan owner uses a
literal patch and actual Git application as independent checks; it does not apply persisted edits.

`prompt_task_attempt.run` connects the admitted task/request/rendered prompt to a prepared generation
worker, edit selection, exclusive patch storage, copied deterministic fixture, prepared containment
probe, validation and version4 measurement. The fixed branch retains its deterministic request/seed
identity; it never carries model-completion evidence. Failed provider envelopes
select the existing unavailable identity. Preparation/validation never inherit the provider secret.
Stopped operations transfer their whole scope until explicit release succeeds; the caller retains
the private directories. Finished certifies released subprocess writers, after which the evaluator
removes scratch and applies `storage_cleanup` before recording or publishing. The attempt fixes one
absolute monotonic deadline at entry: task timeout plus the provider timeout (zero for FIXTURE),
using checked arithmetic. Generation, edit observation, source copy, fixture setup, containment
probe, Git queries and both validations receive that same deadline. Each operation also retains its
existing narrower limit; starting another operation never renews the outer budget. Expiration
before launch returns Timeout without launching, and expiration after launch follows the existing
stopped-scope ownership path. Authenticated release and final capture drain keep their separate
cleanup deadlines so budget exhaustion cannot abandon writers. `prompt_validation_budget.deadline`
owns checked min(local duration, outer remaining); setup, Git, sandbox and validation owners accept
the explicit deadline. `prompt_validation_attempt_smoke` checks expired-before-copy and shared
deadline exhaustion during validation, including released scope and deleted storage; the existing
task-attempt owner checks the full composed path. Final row/repair integration remains P1/P2/P3.
Fifteen Linux task-attempt cases pass with independent measurement/attempt/skipped/expected-input
digest and reference checks, including both fixed variants; macOS builds and
reports ENOTSUP. These trusted-command controls do not qualify installed A3 containment or A4.

`prompt_task_environment.validate` restores the complete declared environment admission before
any task launch: at most64 ordered variables,32 absolute executable paths,65536bytes in each set,
name/value/source/precedence checks, and LANG/LC_ALL matching the declared locale. A credential
name cannot overlap the non-secret policy, is required for CLOUD_OPENAI, and is permitted only for
CLOUD_OPENAI/LOCAL_OPENAI. `worker` copies the admitted non-secret settings and exactly the supplied
resolved credential into an independently owned command environment; it rejects a missing/empty or
NUL-bearing declared credential and unexpected credential values. Neither function reads ambient
environment or grants command authority. Task-input and evaluation-input owners check complete-set
refusals; the focused task-environment owner checks credential separation and source-owner expiry.

`prompt_invocation_records` constructs the settled canonical invocation evidence from admitted or
observed values. Fixed bounded task/sample/attempt ordinals determine workspace names. Request,
snapshot/input, environment, repair provenance, attempted/skipped and expected-input records keep
their declared schema/order/digest preimages. The wire's repeated generation/seed fields are copied
while the single measurement owner moves into its attempt. Capture the measurement digest before
that move, independent of initializer field order; the independent owner checks both canonical
hashes and actual cross-record equality. Row/result assembly remains part of the same capability.

The native evaluator reuses the final verifier's experiment and activation header predicates
during complete input admission, and renders both variants for every task before execution.
A missing proposal opportunity, inconsistent activation operation/status, or malformed context
in the last task must refuse before any task is launched. The input owner includes these cases;
the full verifier owner preserves the historical acceptance/rejection surface. The existing
64-task, 16-sample, two-variant bounds allow 2048 rows and, in version2, 4096 attempted-input
records when every row uses its one repair. Version1 retains its 2048-record ceiling. This is
the same admitted schedule and repair bound, not an increase in task/sample/repair limits.

The selected toolchain is merged Align `f83f5c3c365ac992c6c2dc5a371164c9f7b4339f`,
including Requests 29/53/63–67. The provider's checked-in plans 41–45/47/49–50 own its actual
APIs; unpublished local prerequisite drafts are superseded. Materialize the exact managed
compiler/runtime and verify real client owners before advancing any request beyond ALIGN_MERGED.

R63 changes both JSON encoders to `Result<string, Error>`. Public `prompt_artifacts.encode_*`
unbounded helpers become `Result<string, Error>` and directly transfer the encoder result;
bounded helper signatures remain unchanged. Fallible caller chains propagate errors before
publishing bytes. No empty-output fallback substitutes for an encoding failure. Existing
provider request builders likewise propagate encoding errors. Static string-only JSON escaping
has no recoverable invalid-value case; any retained total helper must make its impossible-error
handling explicit, never emit a successful replacement value. The same invariant applies to
closed index/patch/verification/memory rendering schemas containing only text, integers and
booleans: preserve their total application APIs and abort on an impossible encoder error rather
than manufacturing a valid result. Float-bearing/provider encoders remain fallible and propagate.
Owner tests retain exact JSON golden values for these total renderers. Owned encoder results no longer
need clones merely to escape a source lifetime. Existing canonical bytes and artifact schemas
remain unchanged; R63's finite numeric contract applies where numeric data is encoded.

The unchanged filename-language and test-path policy shared by repository indexing
and patch analysis lives in `source_file_kind`. This pure application module owns
the target-language strings; the rendering modules retain their explicit impossible
encoder aborts. The architecture guard therefore distinguishes language data from
process operations without an exception for a mixed process/literal module. Existing
index, test-selection and patch-evaluation golden owners cover the shared policy.

R68 adoption selects merged Align `177224089629a269bc404f2958b8bfc67b79dcbe`
(PR #1021), superseding the initial f83f5c3c adoption pin above. The fix changes
producer certification only, without an API/ABI or product-policy change. Its
consumer owners are per-unit checking of `src/verify.align` and `make verify-loop-smoke`.

R65 replaces captured `code()` with a typed `status()` observation. Existing application
`verify.Captured.code` and `run_captured` preserve their integer convention: Exited(n) maps to n,
Signaled(n) maps to 128+n. Other callers use an explicit Exited(0) success test. Native wait-result
RSS is an observation, not a newly imposed product resource limit. The new live supervisor will
use typed termination and application-owned policy directly. Owner mapping: existing verification
loop and Request 11 smoke for process status; artifact/generation/verifier and encoding owners
for JSON; retained filesystem/process owners for the subsequent application cutover.

### Implementation-language ownership

Product orchestration, resource-limit comparison, timeout/cancellation decisions, first-error
selection, result assembly, cleanup retries and permission to remove a workspace execute in
application `.align` modules. Moving these from Python into the Align Rust runtime does not
satisfy this migration. R65 requests OS-owned primitives: immutable descriptor admission,
explicit descriptor inheritance, isolated child ownership, bounded I/O and authenticated process
observations/signalling/reaping. Native ownership checks and fail-closed release of OS resources
remain language responsibilities; they do not select product outcomes or resource policy.
The application composes these operations in Align. A missing composition feature is recorded
as an Align request rather than implemented as a native application supervisor.

Local P4 checkpoint: `prompt_measurement_outcome.align` implements the existing measurement and
repair adapters' `assemble` outcome selection, without changing the wire contract. Its Copy input
is a closed outcome enum (Pass/TestFail/Policy/Patch/AdapterError), cleanup/containment booleans
and `Option<i64>` generation duration. Its Copy result uses the existing `prompt_score` status,
failure and stage enums, policy violation count and optional passing duration. Containment failure
precedes cleanup failure; either forces Error and suppresses passing duration. Stage observations
remain those of the attempted work. Policy/Patch have both stages NotRun. Allocation, persisted
identity and OS prerequisites: N/A, pure scalar projection. Owner: exhaustive five-outcome × four
cleanup/containment combinations × present/absent duration smoke coverage. The new Align task
measurement producer consumes this module at cutover; this internal checkpoint alone does not
replace the current Python execution path or satisfy A4.

`prompt_validation_budget.align` owns the coding runner's resource comparison. Copy limits are
processes, resident bytes, workspace files and workspace bytes; Copy observations contain those
counts plus separately deduplicated deleted-file counts/bytes and an explicit completeness flag.
The pure result is InvalidObservation, IncompleteObservation, ProcessLimit, ResidentLimit,
FileLimit, ByteLimit or WithinBudget, in that validation order. Nonpositive limits and negative
observations are invalid. Exact limits pass; sums use subtraction guards to prevent wraparound.
Deleted-file observations must exclude identities already counted in the visible workspace, as
the existing runner requires. Defaults remain 256 processes, 512 MiB resident memory, 8192 files
and 64 MiB workspace storage. The Align supervisor supplies complete observations and acts on
the result; native code does not enforce these application limits. Owner: boundary, incomplete,
multi-limit precedence and i64-overflow smoke. No allocation, OS call or persisted format.

`prompt_process_usage` selects the transitive descendants of both a retained child scope's root
and its exclusive supervising owner from the shipped sorted process table. Include an observed
root, exclude the supervising owner itself, and close ancestry by bounded repeated passes (including
parents whose PID sorts after their children). The pure selector accepts at most32768 rows and
positive distinct root/owner IDs, rejects malformed/duplicate/unsorted identity rows and negative
usage, and returns owned sorted PID observations plus summed RSS and an explicit completeness flag.
Missing RSS and sum overflow are incomplete, never zero evidence. A missing root is allowed after
observed termination; the caller supplies that fact, otherwise it is incomplete. Selection is
observation only, never signal authority or an absence certificate. The live observer bounds
process.table to32768 candidates and checks the caller's absolute deadline before/after native
observation and selection. The256-process ceiling is enforced before allocating procfs owners.
Owner `src/prompt_process_usage_smoke.align`: reverse ancestry, adoption, unrelated processes,
root disappearance, unknown RSS, malformed tables, overflow, process cap and live Linux observation.

`prompt_workspace_usage.observe` counts every retained workspace entry except the root and the
root-level literal `.git` entry, matching the historical live resource scan. Directories count;
regular-file lengths add to bytes and their device/inode identities feed deleted-file exclusion.
Symlinks and special files count without following or reading them. This is resource accounting,
not final edit admission. Inputs are borrowed root, positive file/byte limits up to8192/67108864,
and absolute deadline. Return owned visible identities and Copy counts; any native failure,
negative size, cap breach or deadline expiration refuses rather than reporting partial success.
Retained no-follow recursion is explicitly bounded to128 directories deep and4096 path bytes;
raw non-UTF8 names remain valid for accounting. No content hashing, mode mutation, inode-based
deduplication of visible lengths, or absence/atomicity claim. Root `.git` still receives separate
Git integrity admission. Owner `src/prompt_workspace_usage_smoke.align`: entries/bytes boundaries,
hardlink length accounting, deleted-file exclusion, symlink/FIFO non-follow, nested `.git`, raw
names, retained root replacement, deadlines and depth refusal.

`prompt_deleted_open_file.observe` scans caller-retained descriptor directories, excluding
caller-supplied visible (device,inode) identities and deduplicating across all roots. A raw
` (deleted)` suffix selects followed regular-file metadata, even for a still-linked file with
that literal suffix, matching the historical selection rule. The caller owns process selection
and records failed directory acquisition as an incomplete observation before invoking this helper.
The explicit Context is Stable or Procfs. Stable fixtures mark every cursor/link/metadata error
incomplete. In Procfs, only NotFound after retaining the descriptor directory is an observed
disappearance and may end that directory or skip the vanished descriptor; all other errors mark
the observation incomplete. This repairs the real short-lived-child race: a retained procfs fd
directory can disappear between table observation, cursor creation and link reads. Previously
observed counts stay counted; this never certifies descendant absence or an atomic resource sum.
Unknown/denied observations cannot certify a task within budget. Check the caller's
absolute monotonic deadline before and after native calls; expiration returns Timeout. Limits
are 1..8192 files, 1..67108864 bytes, at most256 roots and8192 visible identities. Link reads use
an explicit4096-byte cap; over-cap becomes incomplete. A detected file/byte excess returns Invalid,
which the supervisor treats as failed resource admission. Owned dedup storage is bounded by visible
identities plus the file cap, and drops on all exits. Neither completeness nor metadata rechecks
claim an atomic kernel snapshot. Owner `src/prompt_deleted_open_file_smoke.align` covers multi-root
alias dedup, visible exclusion, literal suffix, nonregular targets, incomplete/refused observations,
deadlines and composition with `prompt_validation_budget`; Linux open-unlinked process fixtures
remain part of the focused platform owner and final A3 execution.

`prompt_worktree_changes` compares admitted Git TreeEntry records with the sorted retained
snapshot. Added, missing, kind/mode and Git blob changes produce a sorted owned path set. Regular
modes must equal exactly0644/0755; links require Git mode120000. Snapshot equality compares exact
paths, kind and permissions, regular lengths/SHA-256 and raw link targets; directory equality
compares the exact path/mode set. Timestamps and inode changes do not independently constitute
candidate-content changes, preserving the frozen snapshot meaning. `admit` unions actual and
cached changes, then chooses Untracked, Ignored, NoChange, Disallowed or Allowed in that order.
HEAD, index flags and directory admission precede these calls in the task supervisor, and native
transport/parse failures are not represented as empty inputs. These pure owners accept already
admitted records and return owned changed paths; no schema, process or cleanup boundary changes.
Owner: `src/prompt_worktree_changes_smoke.align`, covering additions/deletions, modes/kinds,
staged-only/empty/disallowed changes, refusal precedence and post-validation content mutations
including mutations to allowed paths.

`prompt_worktree.observe` composes per-entry observations into a compact sorted snapshot.
It returns owned Entry records (path, symlink boolean, permission mode, byte length, SHA-256, Git blob and
raw symlink target; regular targets are empty), plus sorted path/mode directory records including
the empty root path. Caller limits are1..8192 entries and0..67108864 regular-file bytes; count
all leaves and directories except root and an actual root `.git` directory. Nested `.git` names
are observed. Symlink targets are separately bounded to4096 bytes and never traversed. Release
regular payload storage before the next leaf. Reject invalid UTF-8 names, paths above4096 bytes,
unsupported kinds, hardlinks, native failures, and depth above128 (the admitted baseline already
fits this ceiling; new directories are forbidden by final change policy). Check the absolute
monotonic deadline before/after native operations. Errors return no partial snapshot and drop
all acquired owners; successful observation is not writer exclusion or an atomic snapshot.
Owner: `scripts/run-prompt-worktree-smoke`, covering actual content/mode/link/tree bounds,
Git-metadata exclusion, unsafe entries, retained replacement and owned output expiry.

`prompt_git_records` admits complete bounded Git machine output before source/change policy.
`parse_tree`, `parse_paths` and `validate_index_flags` borrow raw bytes and an explicit truncation
flag. Refuse truncation or more than65536 bytes before parsing; empty output is valid, nonempty
output requires final NUL and no empty interior record. Tree records split at the first tab,
require canonical blob mode100644/100755/120000 and40 lowercase hexadecimal OID bytes. Index
flags require exact `H ` prefixes. Paths are valid UTF-8, nonempty, relative and have no empty,
dot or dot-dot component; preserve embedded tabs/newlines. Reject duplicate paths. Owned output
keeps Git order; later change aggregation sorts. No path is reopened or executed by parsing.
These explicit validation repairs replace the frozen parser's duplicate overwrite and replacement
UTF-8/truncated machine-output acceptance; successful canonical Git data retains its behavior.
Owner: `src/prompt_git_records_smoke.align`, literal malformed/ordering/path cases plus a focused
Git fixture oracle. New wire/cache schema and native prerequisites: N/A.

`prompt_worktree_entry.observe` is the retained per-entry input to P3 change observation.
It borrows a directory and raw relative name, accepts a caller byte cap in 0..67108864,
and returns owned payload bytes, SHA-256, Git blob identity and Copy metadata. Regular files
require a single link; symlink payloads are exact raw target bytes, never target contents.
`observe_until` additionally accepts an absolute monotonic deadline and checks it around each
exposed filesystem operation, each bounded read and hashing; a native call is not preempted.
The original `observe` selects no practical deadline. Other kinds, excess bytes and observed
metadata changes refuse. Metadata is checked across
opening/reading and final pathname observation; this is not an atomic snapshot or writer exclusion.
The caller owns path enumeration, total budgets, source-tree membership and final containment.
`matches_source` compares the Git mode (100644/100755/120000), exact regular permission mode
and blob identity; unsupported modes refuse a match. This internal record has no persisted format.
Owner: `scripts/run-prompt-worktree-entry-smoke`, covering literal content/kind/mode changes,
raw targets, caps, unsafe kinds, retained-root replacement and input-owner expiry. R70/R76 supply
only generic retained observations and SHA-1; all framing and change decisions remain Align.

`prompt_patch.align` owns whole-file unified diff production from admitted, unredacted edits.
`whole_file_hunk(path: str, original: Option<str>, replacement: str) -> string` borrows all inputs
and returns an owned builder-produced hunk, empty for an unchanged existing file. Inputs are
already admitted relative paths and bounded UTF-8 source/response bodies; this function does not
authorize paths or perform I/O. Preserve the existing LF-only line grammar, new-file mode 100644,
zero/one starting line convention, exact no-final-newline markers and the special unchanged
case when an original lacking final LF matches the response's reconstructed lines. None means
absent file, distinct from Some(""). Allocation is explicit builder storage proportional to the
admitted input sizes; no new cap or wire format. The Align task producer concatenates hunks in
admitted path order and refuses an entirely empty patch before validation. Persisted redacted
`EditSetBlock` evidence is never used as the applied content. Owner: literal diff vectors and
independent `git apply` checks, including absent/empty files and both final-newline states.
One explicit compatibility repair: a newly created empty file emits the creation headers without
an empty `@@ -0,0 +0,0 @@` hunk. The existing Python output for this case is rejected by Git as a
corrupt patch; metadata-only creation applies correctly. This is an application producer repair,
not a grammar change or a change to historical frozen evidence.

`prompt_file_blocks.align` owns response parsing before edit admission. Its
`parse(content: str) -> ParsedBlocks` borrows bounded UTF-8 completion text and returns an owned
record with `status: ParseStatus` (Complete/HeaderWithoutBlock/UnterminatedBlock/TooManyBlocks)
and `blocks: array<FileBlock>`; each FileBlock owns `path: string` and `body: string`. Failure
returns an empty array, never partial edits; Complete may contain no blocks, leaving the later
NoFileBlock/allowlist/duplicate/body-size refusals to edit admission. Preserve the frozen
`response_lines`, `fence_run`, `closing_fence` and `parse_file_blocks` rules: LF splitting only,
one trailing CR stripped per line, ignored surrounding prose, header decoration stripping in the
same order, opening backtick count at least three with optional suffix, closing fence consisting
only of backticks and at least as long as the opener, and reconstructed LF after every body line.
A later header before an opener refuses the earlier header. The 33rd terminated block refuses
the entire result. Unicode whitespace in header/fence stripping follows the existing Python
protocol's explicit whitespace set, including U+001C..U+001F; ASCII-only `str.trim()` is insufficient.
No path, filesystem or task authorization occurs here. Allocation: owned bounded response-derived
strings and a maximum 32-block array, via explicit builders. Wire/cache identity: N/A, internal
parse result. Owner: literal grammar vectors for nested fences, CRLF, Unicode whitespace/separators,
decorations, ignored prose, malformed/truncated later blocks and the 32/33 boundary.

`prompt_edit_admission.align` composes that parser with the frozen `validated_edit_set` policy.
`admit(content: str, allowed: slice<str>) -> AdmittedEdits` returns a status
(Complete/NoFileBlock/HeaderWithoutBlock/UnterminatedBlock/TooManyBlocks/PathNotEditable/
DuplicatePath/BodyTooLarge) and owned sorted FileBlock array. Refusal always has an empty array.
The caller admits the task's nonempty bounded allowlist first. Parse the complete response before
checking edits; remove exactly one leading `./`, then check allowlist membership, previous-path
duplication and 262144-byte body maximum in response order. Return normalized paths in ascending
byte-lexicographic order. Allocate numeric sort indices and owned output; the merged R67 borrowed
record slice supplies keys directly without copying path text. No filesystem
access or authorization beyond membership in the admitted allowlist. Owner: mixed-error precedence,
normalized duplicates, out-of-set paths, byte-size boundary and sorted owned results. The subsequent
retained source owner still checks filesystem containment before producing a patch.

`prompt_environment.align` produces version-2 `EnvironmentProbe` records for P3. Its
`observe(producer: Producer, align_revision: str, product_sha256: str)` returns
`Result<EnvironmentProbe, Error>`; Producer is Snapshot or Task. Require lowercase hexadecimal
40-byte revision and 64-byte product digest before observing the OS. These are caller-admitted
identities, not proof of the executing image; the retained executable admission owner supplies
them at integration. Build exactly `ALIGN:<revision>:<digest>`, producer `ALIGN_SNAPSHOT` or
`ALIGN_TASK`, GPU `none`, and hash canonical ordered JSON with empty `content_sha256`.
Use `os.host()` for actual facts. Lowercase ASCII system/machine identifiers; reject non-ASCII
identifiers instead of inventing Unicode case semantics. Release remains exact UTF-8. CPU uses
the observed description when present and normalized architecture otherwise, preserving the
existing unavailable-description fallback. Retain the optional online CPU count unchanged.
OS/encoding errors propagate; no probe is emitted on failure. Owned strings and canonical
encoding use explicit allocation; encoding is capped at the existing 2 MiB artifact bound.
No persistence, cache, subprocess, self-admission or performance claim belongs to this module.
Closure owner `scripts/run-prompt-environment-smoke` checks both producers, invalid identity
rejection, actual host facts against a test-side OS oracle, canonical digest and owned returned
records. Final R66 acceptance still requires the named functional and no-Python cutover owners.

`prompt_source_file.align` owns a bounded file-content observation for the retained source/tree
consumer. `observe(borrow root: fs.directory, relative: slice<u8>, maximum: i64)` returns
`Result<FileObservation, Error>` with owned lowercase SHA-256 and Copy descriptor metadata.
Validate `0 <= maximum <= 2^61-1`, then open a single-link regular file relative to the retained
root using R64, rejecting all unsafe names/kinds through the real provider admission. Hash exact
bytes with R29 in at most 64 KiB read chunks, including one EOF probe at the cap. Reject initial
negative/oversized length, excess bytes, actual length mismatch, and any before/after change to
descriptor identity, kind, links, mode, size or modification/change timestamps. Native errors
propagate and failure publishes no observation. This is a bounded observation, not immutability,
permission to reopen a pathname, or executable admission. A writer that can restore observation
facts is outside this check's guarantee; final source isolation remains required by P3.
The reader and digest are local owners closed on every return; auxiliary storage is one bounded
chunk and digest state independent of file length. No tree traversal, deletion, cache or new wire
format. Owner `scripts/run-prompt-source-file-smoke` covers binary/empty/exact-cap/over-cap files,
unsafe paths and kinds, raw names where supported, and retained-root pathname replacement against
an independent digest oracle. Concurrent writer exclusion belongs to the final workspace owner.

`prompt_document_source.read` admits one UTF-8 document from a retained project directory.
Inputs are a relative byte path, explicit maximum 1..2097152 and monotonic deadline. Open a
single-link regular reader, check before/after identity, mode, size and timestamps, and read in
at most64KiB chunks with an EOF probe at the exact cap. Return owned text, raw SHA-256 and
descriptor metadata; the reader closes on every return. The owned text is the sole decoding
input and survives path replacement and root expiry; no later pathname read is authorized.
Deadline checks surround native reads, without claiming native-call preemption or atomicity.
Malformed UTF-8, unsafe file kind/path, changed observation, bounds and deadline refuse before
dispatch. Owner `prompt_document_source_smoke` covers these boundaries and retained text expiry.

`prompt_evaluation_documents` decodes the evaluator's typed bound documents from these owned
text snapshots. Each pure entry refuses input above2MiB, validates the existing kind/schema and
recomputes the canonical content digest with an empty digest field through the existing typed
bounded encoder. It returns the owned decoded record with its verified digest restored. Task
admission selects version2; historical records remain readable through their original codecs.
No I/O, cross-record authorization, process dispatch, wire change or new cache is introduced.
Owner `prompt_evaluation_documents_smoke` covers canonical digest, whitespace, kind/schema,
input cap and returned ownership; evaluator admission owns complete cross-record consistency.

`prompt_task_inputs.load` reads the complete ordered corpus task list (1..64 unique paths)
before returning an owned array. It uses retained document reads under one caller deadline and
a128MiB cumulative byte budget. Each task is version2 and passes the scorer's shared task-shape
admission; each task definition and optional patch is a FILE member with the declared raw digest.
The task definition ID agrees with its task. Its normalized `source_dir` must exactly equal
`repo_path`, and every version-2 task must declare that exact path as a `TREE` expectation.
Complete source admission verifies this tree before any dispatch; a FILE row or an ancestor/other
TREE does not substitute for it. Persisted task verification requires the same TREE declaration.
Editable paths are normalized relative paths,
unique and bounded before use. Task prompt/context and generation/control/environment documents
are canonically bound; contexts agree with task IDs and all tasks share exact policy digests.
Task IDs are unique. Repair templates retain their declared raw digest and existing profile
validation. No process or output publication occurs in this loader, including when the final
task fails. It returns owned decoded records and patch text rather than reopening admitted
paths. Source membership snapshots, scope/variant consistency, credential/tool admission and
rendering remain the evaluator's next admission phase. Owner `prompt_task_inputs_smoke` covers
complete-list success, final-task failure, duplicate identities, digest/membership/policy
disagreement, missing/wrong-kind/wrong-path source TREE, source/repository mismatch, bounds and
owner expiry. A2 additionally checks malformed final-task refusal before any attempted row and
changed source bytes against the declared TREE digest. This changes no persisted schema or acceptance metric.

`prompt_evaluation_inputs.load` composes the request's six bound documents and complete task
inputs from one retained project root. Request version2 and sample count2..16 precede file reads.
Scope, corpus revision, parent activation, proposed candidate, acceptance/generation identities,
source policy/product digest and preflight request identities must agree before returning the
owned bundle. Reuse the artifact owners for nested scope/variant/activation digest validation
and the scorer's policy-shape predicates; no second policy algorithm is introduced. Check the
last paired seed with checked arithmetic before scheduling. `schedule` returns an owned bounded
sequence of task/sample/variant/seed scalar rows: task order, samples1..N, odd samples parent then
candidate and even samples candidate then parent. All inputs remain available to later source
trust, environment/credential/tool admission, rendering and execution; returning this document
bundle does not assert that those later checks passed. Owner `prompt_evaluation_inputs_smoke`
covers a complete synthetic bundle, scope/source-policy identity mismatch, invalid sample, absent
parent path, sample/seed bounds, paired order and full-source expiry. Nested candidate digest and
candidate-absence cases remain part of the later evaluator-admission owner. No subprocess,
persistent artifact or cleanup side effect.

`prompt_task.render` now owns the first native task boundary after admission. It validates the
variant, task prompt and all four context identities, applies the existing bounded renderer, and
records the exact variant/task/context digests in a `RENDERED_PROMPT` artifact. Its
`prepare_generation` companion binds the declared generation and provider-control records to one
sample seed and a canonical `PROMPT_GENERATION_REQUEST`; fixture controls are refused before
provider dispatch. Neither function owns a workspace or performs network I/O, so the retained
input bundle can still be released by the caller on every refusal. Owner
`scripts/run-prompt-task-smoke` covers rendered identity, provider-request binding, tampered
rendered text, seed overflow, policy mismatch and task/context refusal.

`prompt_generate.generate` is the in-memory generation entry shared with `generate_file` and
the evaluator's forthcoming retained-product worker. It borrows the existing generation request
and rendered-prompt records, checks request admission, rendered kind/version, declared rendered
identity and canonical rendered bytes before any credential read or HTTP request. Return an
owned response carrying its terminal status, with an empty content digest for the existing explicit
response publisher to finalize. Provider wire production, seed attestation, credential lifetime,
diagnostic redaction and HTTP bounds retain their existing owner. Invalid admission returns
Error.Invalid without network work; provider failures return their ordinary response envelope.
`generate_file` preserves exclusive output preflight and earlier diagnostic precedence; a
forged rendered content digest is now refused before network work. Owner: existing
`scripts/run-prompt-generate-smoke` plus direct-memory admission/owner-expiry cases.

Generation runs in an explicitly selected retained product worker so the evaluator can enforce
its deadline and cancellation while native HTTP is blocked. `--prompt-generation-worker SHA256`
is an internal process entry, not an alternate provider implementation. The parent admits the
running product image, encodes a version1 `PROMPT_GENERATION_WORK` envelope with exactly
`schema_version`, `artifact_kind`, `request`, `rendered_prompt`, limits canonical bytes to4MiB,
seals those bytes as Data and inherits that object at slot3. The immutable input digest is the
only argv payload; argv0 is the literal `align-llm`, with no self-discovery or filesystem fallback.
The command borrows the admitted image and consumes the prepared envelope; cwd/environment are
explicit admitted caller inputs. Credential values travel only in the permitted environment,
never the envelope/argv. The worker reads `/proc/self/fd/3` through the shipped ordinary reader,
requires regular metadata and exact bounded length/EOF, closes its read owner and checks the
input digest before typed decoding and generation. This procfs path is the explicit inherited
slot of this Linux protocol, not a reopened source pathname or a raw descriptor cast.

`prompt_generation_worker.prepare` returns an independently owned command; input envelope,
sealed-file and image source lifetimes may end before launch. `run` refuses malformed arity,
digest, kind/schema, missing/oversized/changed input and invalid generation records before HTTP.
It prints exactly one finalized generation response JSON document to stdout; provider errors
remain valid response envelopes, and admission/write failures return Error with no success claim.
The raw inherited slot closes at worker exit; no target test code runs in this worker. The caller
uses a child scope and existing supervisor with resources disabled, command deadline and signal
subscription, and accepts bytes only after full release and untruncated output. Final worker
response decoding, identity checks and cleanup precede measurement construction. Native error
or failed release retains scope/workspace and terminal-error precedence as for task validation.
No new persisted external schema, environment authority or backend behavior is introduced.
Owner `prompt_generation_worker_smoke` covers sealed input and source expiry, malformed identity,
real fixture-provider response/seed parity, timeout/cancellation and cleanup. Final main-image
binding and full evaluator use remain A2/A3/A4 acceptance, not this focused owner alone.

`prompt_generation_request.build` preserves the existing measured request mapping: request ID is
`TASK-sSAMPLE-parent` or `TASK-sSAMPLE-candidate`, sample is positive, the rendered reference and
paired seed come from the admitted task request, and provider/credential-name/timeout/response
limits and generation parameters come from admitted control/policy records. It finalizes the
existing canonical content digest and verifies the resulting generation request before returning
owned data. It reads no credential or file and does not replace whole-task policy admission.
`prompt_generation_request_smoke` binds parent/absent and candidate/present credential-name
cases with independent canonical bytes/digests, including source expiry and malformed fields.

The shared capture owner permits explicit limits through2MiB for worker response JSON; task
streams remain65536 and measurement diagnostics16384 at their existing callers. Exact-cap and
overflow behavior, prefix redaction and bounded finalization are unchanged. Worker truncation
is terminal protocol failure, never a partial JSON response. The capture owner adds2MiB exact
and overflow cases while retaining the existing task-stream goldens.

The parent response owner `prompt_generation_response.decode` admits the existing declaration-order
response fields, with only `applied_seed`, `http_status` and `content` optional and omitted when
absent. It refuses unknown, missing, reordered or explicit-null members, invalid UTF-8/JSON or
over2MiB input. The finalized canonical content digest, request ID, provider kind/model, lowercase
provider request digest and paired-seed attestation must agree before any content is used. Dispatch
instants are nonnegative and ordered. Generated envelopes require nonempty content, a2xx status,
`NONE` error code and empty error; `INVALID_INPUT`/`PROVIDER_ERROR` envelopes require a nonempty
non-`NONE` error code and absent content, and remain owned failure data for measurement selection.
The decoder does not reconstruct provider request bytes. Owner `prompt_generation_response_smoke`
covers literal digest evidence, source expiry, each identity/seed refusal and malformed framing.

`prompt_generation_collect.run` borrows the caller-owned live scope and signal subscription,
supervises with an explicit deadline and resources disabled, and returns either an owned decoded
response or the complete stopped report. Its2MiB capture has no credential substitution because
the worker already redacts provider data before constructing the bound JSON. Nonzero exit,
timeout, cancellation, truncation, drain errors or incomplete release cannot reach decoding.
The caller retains scope/workspace ownership even on Error; it restores signals and obtains
release before deleting storage. A parse/identity failure after successful release is Error,
never a generated row. The real worker owner supplies transport evidence; the response owner
supplies decoding evidence. The A2 native CLI owner now covers the complete evaluator dispatch.

The pure `prompt_generation_evidence` producer preserves the existing measured adapter's
`GENERATION_REQUEST_IDENTITY` and `SEED_CAPABILITY_ATTESTATION` mapping. Admitted response
provider identity, actual provider request digest and seed result/applied seed are copied verbatim;
absence uses the existing64-zero unavailable digest, `UNSUPPORTED` and absent applied seed.
Requested seed and policy/rendered/environment identities come from admitted caller records.
System text hashes the empty string; user text hashes the exact rendered UTF-8 bytes. Each record
is finalized in declaration order with its own `content_sha256` empty in the preimage, and the
generation identity binds the finalized attestation. No provider request serialization, credential
value or process work occurs here. The collector preserves provider-error envelopes for terminal
diagnostics, but the persisted measurement caller uses absence for non-generated responses,
as the existing adapter does. Its nonzero provider request digest requires an actual completion;
an error envelope must never synthesize an empty completion to satisfy that invariant. Owner
`prompt_generation_evidence_smoke` compares independent canonical golden bytes/digests for
applied, unsupported, rejected and absent responses, including owned input expiry.

`prompt_measurement_assembly` constructs the version4 measurement from admitted generation/seed
records, the observed environment probe, execution outcome, cleanup/containment facts, measured
duration and patch size, and admitted edit/completion evidence. It reuses
`prompt_measurement_outcome.assemble` for status/stage/failure precedence; cleanup or containment
failure removes passing duration. It records no per-attempt repair loop, unrelated/API change or
benchmark claim (zero/absent as in the existing adapter). The product runtime is required, the
legacy adapter runtime is absent, and `edit_refusal` is always present. The caller supplies edit
blocks only after nonempty patch synthesis or the existing `UNCHANGED_FILES` refusal (which
preserves admitted blocks with zero patch bytes), and patch identity only after validation dispatch;
the assembly does not infer those facts from patch size or grant process/storage authority.
Diagnostics reuse the existing replacement-decode/redact/bound owner: summary4096bytes,
stdout/stderr16384bytes. Completion input is already fully redacted by generation; its full UTF-8
length/digest survive independently of disclosure. Text is carried only for refusal codes other
than `NONE`/`UNCHANGED_FILES`, bounded to32768bytes without redacting a second time. Finalized
declaration-order JSON is capped at262144bytes including its digest: if completion text alone
pushes the record over the cap, drop the whole optional text and finalize again; never omit its
identity or partially trim JSON. Any remaining overflow is Error. Schema/refusal/counter/presence
checks reject malformed construction inputs; a nonzero generation request digest requires actual
completion identity, and cleanup/containment precedence normalizes the final refusal to `NONE`
while retaining admitted edit/completion facts. Broader admission belongs to the caller. Owner
`prompt_measurement_assembly_smoke` compares independent version4 canonical fixtures, all outcome
and cleanup precedence classes, Unicode/redaction boundaries and completion whole-field overflow;
`scripts/run-prompt-measurement-assembly-smoke` passes with the explicit R83 provider branch,
and the managed-pin composed native owner now passes.

The historical replacement decoder can expand a cut UTF-8 scalar beyond the requested byte cap.
Optional completion disclosure is omitted whole if its decoded text exceeds32768bytes or contains
NUL; its full identity remains. Required diagnostics that violate the persisted final text bounds
or NUL restriction cause construction Error rather than a verifier-invalid measurement. This
preserves the existing verifier boundary and does not change shared decoder semantics. A future
change to diagnostic truncation must update the producer/repair/verifier expectations together;
this historical application mismatch is not an Align language request.

`prompt_tree_snapshot.observe(borrow root: fs.directory, relative: str, maximum_entries: i64,
maximum_bytes: i64) -> Result<TreeSnapshot, Error>` expands one UTF-8 TREE expectation. Require
1–128 remaining entries and 0–1,073,741,824 remaining bytes, preserving C6's per-task limits;
the caller subtracts earlier expansions. Count the tree root, directories and files. Reject
paths over 4096 bytes, invalid UTF-8 names, unsafe kinds, linked regular files, exhausted bounds
or changed observed metadata. Retain each traversed directory and independent cursor; recursion
depth is bounded by the existing entry budget. Check each directory's metadata before/after
enumeration and each opened entry against its preceding no-follow observation. Failures drop
partial arrays/owners and return no snapshot. This still needs isolated writers for final P3
admission, not an atomic-snapshot claim.
TreeSnapshot owns `artifact_digests: array<ArtifactDigest>`, `sha256: string`, and `byte_count: i64`.
Sort paths by exact UTF-8 byte order using borrowed Move-record slices and scalar indices. Hash
the frozen manifest: six-digit octal mode including kind bits, space, path, NUL, then `D\n` for
directories or `F <file-sha256>\n` for files. Directory result rows carry the final tree digest
and zero bytes; files carry their own digest/count. No schema/cache/CLI change. Allocation is
bounded owned paths/results/indices plus retained traversal frames and streaming file buffers.
Owner `scripts/run-prompt-tree-snapshot-smoke`: independent tree manifest/digest oracle, exact
entry/byte limits, deep/empty/Unicode trees, kinds/modes, invalid UTF-8 rejection where supported,
and composition with the retained file owner. FILE_SET raw-byte manifests remain a separate owner.

Before source-observation Git commands, `prompt_git_config.check` applies the frozen source
verifier's local-config rejection policy to retained metadata bytes. The pure owner accepts at
most4MiB, rejects NUL and malformed section/assignment syntax, admits the existing comments,
case-insensitive sections/keys and quoted subsections, and rejects the complete declared exact-key
and command-bearing pattern set. Remote URL/pushurl/fetch and branch remote/merge metadata retain
their existing treatment. Values are opaque bytes; this is a pre-execution safety classifier,
not a Git config evaluator or include resolver. Source trust must separately retain/check both
common config and worktree config and reject replacement/graft/alternate metadata before launch.
`prompt_git_config_smoke` covers every rejection class, quoted/case/comment syntax, malformed
and raw input, caps and independent frozen-parser comparisons. Its passing result alone does
not authenticate repository roots or establish safe execution under concurrent writers.

`prompt_file_set.parse` decodes the existing `ALIGN-LLM-CORPUS-FILE-SET-V1` raw-byte format before
file observation. Maximum manifest bytes are8388608 and declared entries1..1048576. Decimal count
and path lengths use the existing no-leading-zero grammar; mode is exactly six octal digits,
followed by the byte-counted1..4096-byte relative path, NUL, `F `,64 lowercase hex digest and LF.
Paths are strictly increasing by raw byte order, with no empty/dot/dot-dot/NUL component or
absolute prefix. Raw non-UTF-8 names and embedded newlines remain valid. The complete manifest
must end exactly after its declared entries. Return owned mode/path-byte/digest records without
filesystem activity; no source pathname is inferred from decoded text. The consumer separately
opens retained files, matches mode/digest, refuses manifest self-membership and observes bounded
unchanged metadata. Owner `prompt_file_set_smoke` covers literal/raw/newline fixtures, framing,
ordering, path and bound refusals, and independence from the manifest's input lifetime.

`prompt_file_set_observation.observe` retains a single-link manifest under an explicit manifest
root and verifies its exact raw SHA-256,8MiB bound and unchanged descriptor metadata before
parsing. It then observes every declared file under the retained corpus root, matching its mode
and digest, rejecting manifest inode self-membership, and accumulating file bytes under the
caller's explicit0..2^61-1 total cap. Monotonic deadline checks surround manifest chunks and
per-file bounded observations; native reads are not preemptible. No subprocess or publication is
performed. It returns the owned manifest identity, file count and observed total bytes only after
all entries pass and the still-retained manifest's metadata, including change time, remains
unchanged. Failure yields no partial attestation. Roots remain caller-owned. Existing
single-link/special-file/path rejection and non-atomic metadata limits apply. Owner
`prompt_file_set_observation_smoke` covers raw/newline paths, actual mode/digest/total limits,
manifest self-membership, malformed last entry, unsafe files, retained-root replacement and
deadline refusal on Linux/macOS where the raw-name surface is supported.

`prompt_source_directory.resolve` resolves an explicit absolute base plus a raw absolute/relative
Git metadata pointer. Both byte inputs are bounded to4096 and NUL-free; the normalized absolute
output is at most4096bytes. Start at the filesystem root and check every visited ordinary
component with retained no-follow directory traversal before accepting a later `..`; do not
lexically erase an unchecked symlink or missing component. Repeated separators and `.` collapse,
and `..` at root remains root, matching the existing physical-path semantics. Return an owned raw
absolute path and retained directory, never a borrowed name or an exec authorization. Raw names
remain raw; ordinary product request paths remain UTF-8 through their separate admission. Deadline
checks surround bounded traversal. All returned owners drop without mutation. Owner
`prompt_source_directory_smoke` covers relative linked-checkout pointers, absolute pointers,
dot/parent/repeated separators, raw names, symlink-before-parent refusal, missing-before-parent,
source expiry and path/byte/deadline bounds. Continued source-writer isolation and binding the
returned directory identity to any later command remain caller prerequisites.

`prompt_git_metadata.admit` composes ordinary `.git` directories and linked-checkout `gitdir:` /
`commondir` pointer files into retained repository/Git/common directory owners with owned raw
absolute paths. Pointer files are single-link regular files up to4096bytes with a nonempty target,
exactly one final LF (and the exact `gitdir: ` prefix where applicable). The empty-target case
refuses explicitly instead of collapsing to the containing directory. A CR immediately before
the final LF also refuses: Git's pointer reader strips trailing CR/LF, so accepting that CR as
part of a directory name could audit a different directory from the one Git uses. See Git's
[pointer readers](https://github.com/git/git/blob/master/setup.c). Missing commondir selects the same Git
directory, with matching retained identity. Read existing common `config` and Git `config.worktree`
as unchanged bounded regular observations and apply `prompt_git_config.check`. Refuse any
replacement refs directory, grafts or object alternates entry, including links and unsafe kinds;
only actual NotFound is absence. No Git process runs during this admission. The next source owner
must still inspect the packed replacement namespace, expected HEAD and cleanliness through
admitted Git under source-writer isolation. Owner `prompt_git_metadata_smoke` covers ordinary and
linked layouts, absolute/relative pointers, config refusal before any command, unsafe metadata,
missing/incorrect pointers, common identity and retained-owner expiry. No `.git` directory
assumption or repository mutation is introduced.

`prompt_source_git.observe` is the single-repository source observation producer. Inputs are
borrowed admitted Git image and `prompt_git_metadata.Metadata`, expected40/64-digit lowercase
revision, caller-owned signal subscription/procfs root and outer monotonic deadline. The caller
excludes source writers across admission and this operation. Resolve the repository's owned raw
path to UTF-8 for the existing native cwd/argv surface; before and after the queries, re-admit
metadata and require the same repository/Git/common device/inode. These checks detect observed
replacement but are not a retained-cwd or atomic-filesystem guarantee.

Execute exactly three sealed-image queries in order: `for-each-ref --format=%(refname)%00
refs/replace/`, `rev-parse --verify HEAD`, then `status --porcelain=v1 -z --untracked-files=all`.
Use the frozen verifier's literal `--no-pager`, `-C`, six `-c` overrides and cleared11-entry
environment; do not select ambient Git, helpers, credentials or user config. Each command gets
min(remaining outer deadline,10seconds), its own child scope and explicit256KiB raw captures.
No resources walk is selected for these read-only queries. Reuse supervisor cleanup and accept
transport only after zero exit, full release and complete untruncated drain. Nonempty replacement
namespace is refusal; HEAD is exactly one full lowercase revision plus LF. Return owned observed
revision and `verified = (HEAD == expected && status is empty)`. Dirty/mismatching repositories
are observations with verified false. Parse/admission/native-before-launch failures are Error;
supervisor/transport failure after launch returns a stopped attempt retaining scope/report/error,
never drops an unreleased scope. Parsing occurs only after accepted transport has released the
scope, so subsequent parse failure returns Error. The caller owns signal restoration and terminal error selection. Ordinary
source failures may become unverified at the outer trust-result layer; cleanup failure is terminal.
Owner `prompt_source_git_smoke` covers real SHA1/SHA256 ordinary/linked clean/dirty/mismatched
repositories, config/metadata refusal before launch, packed replacement refs, exact query/env,
malformed/nonzero/oversized child output, timeout/cancellation and cleanup. This focused producer
does not qualify final A3 isolation or gate-only ancestry.

The FILE_SET observation also returns the owned parsed `members` array from the exact raw bytes
whose SHA256 and filesystem members it verified. Consumers borrow these rows for membership;
they do not reopen and reparse an unbound manifest. Its existing `files` count remains equal to
`members.len()`. This is an internal owned-result extension, with no wire/cache schema change.
The file-set observation owner additionally checks raw-path/mode/digest rows after source expiry.

`prompt_source_command.prepare` owns the shared literal source-Git prefix and cleared environment;
its internal callers supply fixed query tails. `prompt_git_member.observe` checks one admitted
UTF-8 relative regular-file path against a full40/64-digit lowercase revision, six-octal regular
mode and lowercase raw SHA256. Inputs also borrow the admitted image, retained Git metadata,
signal subscription/procfs and outer deadline. Reject malformed path/revision/mode/digest before
launch (relative paths have1..4096 bytes and1..255-byte components, excluding empty/dot/parent).
The source-writer exclusion and before/after metadata identity checks above apply.
First run `ls-tree -z --full-tree REV -- PATH` with8192-byte captures, requiring exactly one
NUL record whose suffix is TAB plus the exact UTF-8 path plus NUL and whose header is the exact
mode, `blob`, and full lowercase object ID. Preserve Git's pathspec interpretation; exact output
matching prevents an interpreted pattern from certifying another path. A missing or mismatched
record returns false. Then run `cat-file blob OID` with2097152-byte captures and compare the raw
stdout SHA256. Both membership tails prepend `-c advice.graftFileDeprecated=false`: the fixed
`GIT_GRAFT_FILE=/dev/null` disables grafts but otherwise makes supported Git versions emit a
deprecation advisory even on successful queries. Suppress only that advice, preserving the
empty-stderr rule for other diagnostics. Each query uses the shared fixed source environment and min(10seconds, outer
deadline); require accepted released transport and empty stderr. Native-before-launch/admission
failures return Error; post-launch transport failures retain scope/report/error in Stopped.
Nonempty stderr after otherwise accepted transport returns Error after release. Return owned
Member(bool), never a partial positive result; digest mismatch is false. No persisted schema or
cache identity changes (N/A: internal observation); no performance claim. Owner
`prompt_git_member_smoke` covers real SHA1/SHA256 ordinary/linked membership, missing/wrong
path/mode/digest, exact/over byte caps, malformed or multiple records, child failure, timeout,
cancellation, metadata refusal and retained cleanup. Final evaluator remains the integration owner.

`prompt_verifier_trust.build` maps three admitted optional observations into the existing
`PROMPT_VERIFIER_TRUST` record. Expected identities come from the admitted evaluation request;
observed40/64-digit revisions and FILE_SET SHA256 remain optional on unavailable observation.
A verified observation must be present and exactly equal its expected identity. Preserve present
unverified observations, encode reachability as `VERIFIED`/`UNVERIFIED`, finalize the existing
canonical digest, and return owned data. This pure constructor does not run Git, infer trust from
declared hashes or downgrade a cleanup failure into unverified evidence; the live caller handles
those outcomes first. Owner `prompt_verifier_trust_smoke` binds complete/mixed/unavailable canonical
goldens, source expiry and false-verified/identity/schema refusals before final source integration.

`prompt_source_trust.run` composes three observations for an already admitted version2 evaluation
request and retained Git image: application Git, Align Git, then Git or FILE_SET corpus. It owns
no signals/workspace deletion authority. Ordinary metadata/parse or fully released verification
failure becomes absent/unverified for that source; cancellation, incomplete release, cleanup or
drain failure remains an explicit stopped attempt with its scope. Outer deadline expiration is
Error. A pending signal before or after the observation sequence returns explicit Cancelled and
cannot publish trust. The source-writer isolation precondition spans the sequence. FILE_SET uses
separate retained manifest-parent/corpus roots and the caller's explicit byte cap. A complete
sequence calls the pure trust constructor and returns owned Evidence containing `trust` plus
`file_set: Option<prompt_file_set_observation.Observation>`. The optional observation is present
exactly for a successfully verified FILE_SET corpus, retaining its authenticated members for
later task membership; Git or unavailable FILE_SET observations leave it absent. No trust wire
schema changes. Incomplete cleanup is never converted to unverified evidence.
Owner `prompt_source_trust_smoke` covers real three-repository and mixed FILE_SET
composition, dirty/unavailable source preservation, stopped/cancelled ownership and exact trust
identity; final evaluator and installed isolation remain separate acceptance.

`prompt_declared_source.expand` expands one task's admitted ArtifactExpectation slice under its
retained project root before corpus membership. Preserve the frozen declared-source limits:
at most128 expanded entries (including TREE roots/directories) and2097152 total regular-file
bytes per task. FILE uses retained single-link observation and binds the canonical expectation
preimage `six-octal-mode SP relative-path NUL F SP raw-sha256 LF`. TREE reuses the existing
bounded tree snapshot, verifies its declared manifest digest, counts all returned entries and
collects only regular file rows for membership. Each expectation is validated before its result
is appended; no partial expansion returns after failure. Return owned ArtifactDigest file rows
in declaration/traversal order plus total entry/byte counts. Overlapping declarations consume
their actual expansion budgets and remain explicit duplicate rows for the later membership
owner; no conflicting expectation is silently overwritten. Deadline checks surround each
bounded observation; this does not claim atomic source isolation. Owner
`prompt_declared_source_smoke` covers mixed FILE/TREE literal hashes/modes, wrong expectation,
exact/over entry and byte caps, overlap ordering, unsafe/missing source, deadline and source expiry.

`prompt_source_membership.compare` checks borrowed declared ArtifactDigest rows against retained
project and corpus roots. Validate each row's relative path, six-octal regular mode, lowercase
SHA256 and0..2097152 byte count; observe both files with the existing bounded single-link owner,
then require both mode/content/size identities equal the admitted row. Deadline checks surround
each observation, caller source-writer exclusion spans expansion and comparison, and any missing,
unsafe or changed file refuses the entire call. Return Result<(),Error>; allocate only bounded
per-file reads and digests, retain no new filesystem capability or persisted identity. Duplicate
rows remain explicit. `file_set` additionally checks the owned verified FILE_SET observation's
identity against the expected corpus SHA256 and binary-searches its sorted raw member paths for
every admitted row, requiring exact full mode and SHA256. Borrow the original observation, never
reopen the manifest. Its caller supplies the result of file-set observation under the same source
writer exclusion, not untrusted decoded data; this helper does not establish corpus trust itself.
Owner `prompt_source_membership_smoke` names exact file/row matches, project/corpus mutation,
wrong mode/size/digest, missing/unsafe paths, malformed rows, expired deadlines, raw sorted
manifest lookup and absent/wrong-identity membership. The A2 native CLI owner now covers final task-list integration.

`prompt_source_collection.collect` composes complete task declarations before source dispatch.
It borrows1..64 `TaskSource` records, each containing the raw manifest ArtifactDigest captured
by document admission and owned ArtifactExpectation declarations. Under caller source-writer
exclusion, expand every task with the existing per-task128-entry/2MiB limits; preserve duplicate
rows and conflicting declarations rather than overwrite them. Strict corpus admission prepends
each task's original raw manifest row, so whitespace and mode changes cannot silently replace the
admitted document. Return at most8256 owned rows in task order; no child, publication, cache or
wire change (N/A: internal admission). `prompt_source_admission.compare` uses retained project/corpus roots for the whole
set. Strict FILE_SET dispatch consumes the retained verified observation; strict Git dispatch
(`prompt_source_admission_git.run`) checks every row against the named commit and returns the first Stopped attempt with its scope
still owned. No failed/partial set authorizes execution. Deadlines bracket collection and each
observation; cancelled Git admission cannot return Ready, including an empty set. Unverified
source policy and unavailable-corpus decisions remain the evaluator's owner.
Owner `prompt_source_collection_smoke` covers ordered multi-task collection, duplicate/conflicting
declarations, strict raw task-manifest inclusion, last-task refusal, caps, source expiry and full-set
FILE_SET comparison. Its source check and executable owner pass with the explicit R81/R83 provider
branch (`651cd0a2`); the earlier managed `6ca79fee` pin was blocked until that provider implementation
is merged and adopted. Independent `prompt_source_admission_smoke` covers captured raw manifest
identity/expiry and full-set FILE_SET refusal after final-document mutation/removal.
`prompt_source_admission_git_smoke` covers complete Git membership, last-member mismatch,
cancellation and retained stopped-scope cleanup. Task input admission retains the original manifest
row for this boundary; the current managed-pin composed owner now passes.

The existing C6/C4/C7 specifications remain authoritative for unchanged fields, byte order, caps,
error codes and algorithms. References here are incorporation, not permission to reinterpret them.
Only the deltas below supersede their historical Python execution requirements. Implementation must
update affected source comments, examples, codec vectors and owner tests in the same cutover.

| ID / surface | Inputs and defaults / result | Ownership, identity and validation | Owner / prerequisites / acceptance / metric |
| --- | --- | --- | --- |
| P1 `main prompt evaluate REQUEST RESULT_RELATIVE` / `prompt_evaluate.evaluate_file(request_path: str, result_relative: str) -> PromptEvaluateStatus` | Same two positionals, statuses `Published`, `InvalidInput`, `EvaluationFailed`, `OutputWrite`, `CleanupFailed`; no interpreter or repository-local implementation child. Version-2 request delta below. | Borrow operands for call; decode into owned records; retain admitted inputs through use; allocate explicit bounded builders/buffers. Validate request syntax/version/caps, relative output grammar, record/reference hashes, source/environment prerequisites, workspace, then provider/validation work. No task runs before source admission. Cleanup failure has the current terminal precedence; no activation from incomplete evidence. | `prompt_evaluate`, new `prompt_workspace`, `prompt_task`; Requests 29/53/64/65/66; A1/A2/A3/A4; correctness, no speed claim. |
| P2 task execution / shared Align repair policy | Existing ordered parent/candidate/sample/attempt schedule, paired seeds, provider inputs, whole-file edit grammar, edit limits, repair drop ladder and retry ceiling from C6 and C4. Version-2 task delta below chooses an internal execution kind instead of interpreter/helper argv. | Align owns parsing, edit eligibility, unchanged/disallowed edit refusal, redaction, attempt transitions, scoring and publication. Each attempt gets its declared pristine base and owned scratch. Validation tools return observable exit/output; they do not decide retries, edit selection or candidate acceptance. | New `prompt_task`, `prompt_workspace`, `prompt_repair`; reuse `prompt_render`, `prompt_model`, `prompt_score`, `verification_loop`, `repair`, `verify`, provider modules; A1/A2/A3. |
| P3 source/workspace/validation boundary | C6 source and snapshot admission rules, task runner's allowed edits/modes, Git isolation and declared resource ceilings survive. Explicit admitted Git, test/build tools and platform sandbox executables are permitted. | Resolve one Git common directory, cover ordinary and linked checkouts and malformed cleanup. Retained regular files, complete tree observation, no-follow opens, tool identity checks, bounded captures/deadlines and all owned descendant cleanup precede result publication. No external program owns product policy. Unsupported containment refuses before executing task code. | `prompt_workspace`, new `prompt_source`, new `task_validation`; Requests 29/53/64/65/66; A2/A3. Linux capable qualification retains its installed profile. macOS must report unavailable where that containment contract is unsupported; no new cross-platform sandbox promise. |
| P4 records, scorer, accept/rollback | New evaluation uses version-2 request/task/runtime records, version-4 measurements and the version-2 independent gate locator below; old artifacts retain their schema meaning. Existing acceptance and rollback positionals/statuses are unchanged. | Canonical encoding, content digests, absence rules, structural references and exclusive result/evidence pair publication stay owned by `prompt_artifacts`, `prompt_artifact_io`, `prompt_score`, `prompt_state`. New evidence cannot pretend to have a Python producer identity. Historical digests and evidence bytes never change in place. The external oracle's interpreter identity is separate from product identity. | Existing artifact owners plus P1/P2 and independent `scripts/prompt-gate-validator.py`; A1/A2/A4/A5. C7 remains independent; its wire does not change. |
| P5 normal build and distribution | `make build` may use Python developer tooling to materialize the pinned compiler and build/link native dependencies. Its output and documented shipping CLI operations must run without a Python installation or repository scripts. | Distribution contains Align executable(s), admitted native libraries/backends and declared data. Native backend availability follows current explicit build inputs; a stub build is not real inference acceptance. Git/build/test tools for the user's project are declared external dependencies. No automatic helper download or interpreter discovery. | Build/CLI owners; A4. No build-tool rewrite required, no implied install/package command beyond current entrypoints. |
| P6 native boundary | Existing `ggml_ffi` operations, opaque backend/resource handles, native kernels and ABI validation remain. | Align decides model geometry, graph operation order, scheduling, sampling, residency budget, KV policy and resource lifetime. C translates explicit requests, checks native invariants and releases native resources. A low-level backend handle state machine is permitted; product decisions cannot migrate into it. | `ggml_ffi`, `scripts/ggml_shim.c`, runtime modules; A6. No new ABI in this migration unless concrete implementation requires a separately specified delta. |
| P7 architecture check | `python3 scripts/check-python-boundary [--strict] [--root ROOT]`; default root is the checkout containing the script. Exit 0: selected static checks pass; 1: violation; 2: malformed inventory/arguments/tool failure. | Read-only Git working-tree inventory includes tracked and nonignored untracked files; no changes to Git refs/index. Version-1 inventory schema below. Default mode permits only frozen legacy paths/bytes; strict mode permits no production violation/bootstrap. Static checks are not proof of dynamic execution closure. | `scripts/check-python-boundary`; A0 and independent mutation owner. Packaging/runtime proof is A4, never inferred from this scan. |
| P8 `main --eval [CORPUS]` | Keep the existing external-command corpus/task wire, default Git smoke corpus and result records. The historical bundled `coding-v1` execution path becomes replay-only: normal `--eval` returns `Error.Invalid` before any task child or result line. New coding evaluation uses P1 and version-2 tasks, including internal `FIXTURE_PATCH`. | Admit the complete task list before dispatch. Refuse the reserved `coding-v1` corpus identity and direct/interpreter selection of the frozen product implementations by resolved path or retained file digest, including renamed copies. Explicit target-project Python tests remain allowed. No interpreter backend or fallback is provided for bundled coding behavior. Section 3.3 defines the supported boundary and cases. | `main`, `eval`, `verify`, new `task_validation`; Requests 29/64/65 for retained command admission; A2/A4 plus existing `make eval-smoke`, adapted in cutover. |

P5's shared-library relocation input is `ALIGN_LLM_GGML_SHIM_RELOCATABLE=0|1` (default `0`),
owned by `scripts/build-ggml-shim`. Validate it before compilation; other values fail with exit 1.
Mode 0 preserves the existing absolute development library identity. Mode 1 uses the library
basename as ELF SONAME and `@loader_path/libalign_ggml_shim.dylib` on Darwin; distribute the Darwin
shim adjacent to the executable, and declare the ELF library search directory at launch. Static
stub mode rejects mode 1. No ABI, persisted schema, allocation or product subprocess changes.
The distribution includes the real backend's dynamic dependencies, whose own loader identities
must also resolve within the relocated distribution. `scripts/run-product-runtime-no-python`
owns the Linux real-backend relocation slice: copied executable/model/pack/geometry, no Python
or repository mounts, three generated tokens and complete descendant exec observation. It is
not the complete A4 or installed A3 owner and makes no performance claim.
`scripts/run-product-evaluation-no-python` owns the corresponding prepared FIXTURE_PATCH
evaluation slice: private copied product/inputs, explicit native test-tool mounts, eight paired
rows, verified result/evidence publication, descendant exec trace and removed workspace. Its
test-owned PID/mount namespace has a fresh writable procfs so the product can establish its
normal nested user/PID/task sandbox. It does not skip the product's containment probe or stand
in for installed A3 qualification. The same owner exercises the unchanged default Git corpus,
reserved coding identity refusal before dispatch, repository indexing/test selection/patch
analysis, repair-state demonstration and real verification retry with a failure-memory event.
A separate namespace then mounts one explicitly declared external Python target test and checks
its single interpreter execution; normal product traces are checked before that exception runs.
`scripts/run-product-state-no-python` reuses the independent state owner outside relocated
product namespaces to verify acceptance, rollback and exclusive publication. Its HTTP proposal
fixture likewise stays outside the product namespace, sharing only network for actual proposal
requests and checking golden wire prompts and bounds. Historical selector retirement remains
a separate A4 obligation.
Its optional `provider` mode shares network with the separately owned HTTP fixture and rebinds
the declared worker library directory to the relocated native libraries. The independent provider
owner accepts the relocatable binary and library directories as optional arguments and verifies
eight additional requests after namespace execution. No Python process or helper enters the
product PID/filesystem namespace. P8 now uses shipped R88 `fs.open_regular` for
ordinary-path file admission; the earlier `fs.open` FIFO witness remains historical.

### 3.1 Wire transition and historical artifacts

The cutover uses a new corpus identity; historical `canonical-v1*` files, baseline ancestry and
qualified GPU receipts remain byte-for-byte unchanged. Read-only decoding/replay of older records
is supported by independent developer validation; a legacy evaluation *request* is refused by the
new normal evaluator before executing helpers. `prompt accept`/`rollback` continue to verify old
valid activation history in Align; old bytes must not be relabelled as newly produced evidence.

New schemas are defined by these exact transformations of the checked-in ordered records in
`src/prompt_artifacts.align` at audit head `312dd65714036f9587329386b5fdbd65e91b97b9`:

Raw-wire admission must check removed-field presence before ordinary typed decoding: Align's
typed decoder skips undeclared keys and maps optional missing/null to None. The application
`prompt_product_wire.check_removed_fields(source: str) -> Result<(), Error>` checks the versioned
field exclusions below throughout nested artifact records, rejecting even a forbidden explicit
null. It does not validate required fields, content hashes, identity or cross-record bindings;
those remain with the typed codec/verifier. Parse once into an arena-owned JSON document, inspect
only the closed artifact-kind/version exclusion rules, and walk each materialized child level
once. The parser's shipped depth limit bounds recursion; malformed JSON and unsupported versions
of these changed record families refuse. Other artifact kinds retain their existing codec rules.
No wire fields, cache identity or CLI are added. Owner `prompt_product_wire_smoke.align` covers
both version directions, forbidden nulls, escaped keys, nested rows/attempts, malformed JSON and
unchanged artifact kinds. The guard is connected at the twelve decoder roots whose type graph contains changed families:
EnvironmentIdentity, EnvironmentIdentityCore, PromptEvaluateRequest, PromptEvaluationResult,
PromptEvaluationTask, PromptGateManifest, PromptGateSourceLocator, PromptSourceVerifierPolicy,
PromptTaskRow, TaskAdapterRequest, TaskAttemptRecord and TaskMeasurement. A direct source-policy
decoder regression and the existing complete/compact/tamper/repair verifier owner cover integration.
The guard alone does not establish identity or complete producer acceptance; the representation
and version-specific verifier rules below are required. PromptEvaluationEvidence has no changed record family in its present type graph.

| Record | Ordered transformation and validation |
| --- | --- |
| `PromptEvaluateRequest` | Keep all fields in order except remove `verifier_python_executable_path`, `generation_child_path`, `generation_child_sha256`. Set `schema_version = 2`. Append required `product_executable_path: string`, `product_executable_sha256: string` after `evaluation_evidence_path`. These identify the retained running/worker product binary; path is an explicit absolute NUL-free path, SHA is lowercase 64 hex. Request 65 must bind the currently executing image to this admitted identity; an arbitrary matching on-disk file is insufficient. No ambient `argv[0]` discovery or unverified self-exec. |
| `PromptSourceVerifierPolicy` | Set version 2; remove `helper_path`, `helper_sha256`, `helper_runtime`, `interpreter_sha256`. Preserve `git_executable_sha256`. Insert `product_executable_sha256: string` immediately before `content_sha256`. Its value must match the evaluate request. Keep source-policy identity and Git validation semantics. |
| `PromptEvaluationTask` | Set version 2; remove `cmd`, `argv`, `snapshot_cmd`, `snapshot_argv`, `measurement_adapter_runtime`, `snapshot_helper_runtime`, `validation_runner_path`, `validation_runner_sha256`, `validation_argv`. Insert required `execution_kind: string` immediately after `require_clean_repo`: exactly `PROVIDER_EDIT` or `FIXTURE_PATCH`. The latter requires both patch fields; the former requires neither. The removed task-level `validation_argv` was the runner tail (`%TASK%`, `%PATCH%`), not the target test command. The admitted task-definition record retains its own `validation_argv`; Align invokes that external build/test tool after applying the edit. All other fields keep order/type, including paired repair fields and `edit_policy`. |
| `EnvironmentIdentityCore` | Set version 2; replace the contiguous three fields `measurement_adapter_runtime`, `snapshot_helper_runtime`, `source_verifier_runtime` with `product_runtime: string`. Exact value `ALIGN:<align_revision>:<product_executable_sha256>`; both components bind the current admitted compiler/application identities. Existing environment-policy/source-policy hashes follow. No claim that replacing a producer preserves the old environment ID. |
| `EnvironmentProbe` | Set version 2 for new producers; keep field order/types. `producer` is exactly `ALIGN_SNAPSHOT` or `ALIGN_TASK`; `runtime_identity` equals the new `product_runtime` spelling. Host facts retain their old meaning, including host logical CPU count rather than quota-aware process count. Legacy version-1 probes remain independent historical evidence. |
| `TaskAdapterRequest` and attempt/input references | Keep the historical record decoder for old evidence. For new evidence use version 2, remove `validation_runner_path`, `validation_runner_sha256`, `validation_argv`, `generation_child_path`, `generation_child_sha256`; append `product_executable_sha256` before `content_sha256`. It is an internal task-input evidence record; it no longer authorizes helper execution. Existing `adapter_request_sha256` names its canonical digest and is not renamed. |
| `TaskMeasurement` | Set version 4. Starting with the version-3 ordered fields, replace `base_adapter_runtime_identity` in its declared position with required `product_runtime: string`; keep the other fields and their order. Versions 1–3 require `product_runtime` absent and keep their old identity/absence rules. Version 4 rejects `base_adapter_runtime_identity`, including a forged `PYTHON:` value. Every version-2 task requires version-4 measurements in all executed attempts and the final row. The detailed shape and cross-record checks below apply. |
| `PromptGateSourceLocator` | Set version 2. Replace the contiguous four `source_verifier_relative_path`, `source_verifier_sha256`, `source_verifier_runtime`, `source_verifier_interpreter_sha256` fields with `independent_verifier_relative_path`, `independent_verifier_sha256`, `independent_verifier_runtime`, `independent_verifier_interpreter_sha256`, all strings in that order. Replace `generation_child_sha256` in place with `product_executable_sha256: string`. Other fields keep order/type, including the source-policy locator/digest and Git digest. Relative-path and lowercase-digest grammar remain unchanged. Version 1 retains its historical fields and bindings; the two field sets cannot mix. |

In-memory representation: retain one ordered record family per existing public type. Fields
present in only one schema become `Option<T>` (including legacy command arrays); new version-only
members are also `Option<T>`. Place new members at the replacement/insertion positions above and
retain old members in their original relative order. Encoding omits None, so historical canonical
bytes remain unchanged; no JSON sum tag or wrapper is introduced. Common required fields retain
their original nonoptional types. The ordinary record representation is not permission to omit a
required wire field: `prompt_product_wire.check_versioned_fields` performs the same recursive
exclusion pass plus non-null presence of every schema-specific required field, before the twelve
typed root decoders. Keep the narrower exclusion owner for its targeted negative controls.
The typed verifier independently checks version-specific presence and bindings on programmatically
constructed records. Legacy required values must be Some; current fields must be None, and the
inverse holds for new records. TaskMeasurement's existing optional v1–3 members retain their
current verifier rules, while v4 requires product_runtime and forbids the legacy base identity.
No reader may select a version from member presence. Owner evidence includes byte-identical
historical codec/verifier goldens, missing/null required-member rejection, v2/v4 constructor and
round-trip vectors, and final/intermediate-attempt identity mutations. This representation and
decoder/verifier/test change form one local semantic batch, not a separate publication.

For version-4 measurements, `product_runtime` must equal the version-2 environment core's value
and the measurement probe's `runtime_identity`; that probe must be version 2 with producer
`ALIGN_TASK`. The compiler revision and product digest must also match the admitted source trust
and task-input/request identity. Check every attempt, including failed intermediate attempts and
measurements referenced by repair provenance, before scoring or publication. A final-row match
alone is insufficient. A skipped attempt retains its existing absence shape and cannot carry a
measurement from another version.

The version-2 edit-set/total and patch-digest rules continue at measurement version 4:
`edit_set` and `edit_set_total_bytes` are present together, with the established block ordering,
membership, byte-sum and disclosure caps; `patch_sha256` is present exactly when
`patch_size_bytes > 0`, and hashes the actual patch passed to validation. For `PROVIDER_EDIT`,
the version-3 refusal/completion rules also continue, including `UNCHANGED_FILES` retaining its
validated blocks, bounded redacted completion identity and the existing excerpt omission rule.
For `FIXTURE_PATCH`, edit-set/total and all completion fields are absent, `edit_refusal` is
required and exactly `NONE`, and fixed-adapter status/failure semantics remain. Its existing
deterministic fixture request/seed identity is retained; that request digest does not imply a
model response. The fixture branch cannot fabricate a completion or claim generated-edit evidence.

The version4 fixed branch measures its native span from immediately before fixture preparation
through completed passing validation for either variant. A passing fixture requires a positive
duration bounded by the evaluator's observed attempt span, just like any executed passing attempt.
Do not carry the frozen adapter's artificial candidate-only80000000ns into the new producer: a
native attempt can finish inside that constant, invalidating the required nonnegative overhead.
The `FIXTURE` provider/seed identity makes this a fixture-execution measurement, not model latency
or performance acceptance. Historical version1 fixture records and their replay remain unchanged.
The task-attempt owner binds each measured span into the persisted attempt and independently checks
its canonical digest/references; this is correctness evidence, not an optimization claim.

The version-2 gate locator binds two distinct observations. The source policy's digest and
`product_executable_sha256`, the explicitly admitted product binary, source trust's Align revision,
and each environment core's `product_runtime` must agree. Separately, the external validator
observes the retained independent verifier, Python interpreter and Git executable. Its exact
`independent_verifier_runtime` spelling is
`CPYTHON:<independent_verifier_interpreter_sha256>:<independent_verifier_sha256>`.
These oracle fields never populate or equal an Align product-runtime field. The independent
source verifier continues to recompute the source facts; neither it nor the gate validator is
called by product evaluation or activation. Its existing source-observation request/result format
can remain version 1 because those records carry source facts, not the removed execution policy.

The evaluation producer binds the admitted evaluate/task-input request's product digest before
computing its persisted request digest. Current result/evidence records retain request digests,
not those request preimages. The independent gate therefore does not claim to reconstruct or
re-authenticate unpersisted requests: it verifies existing digest references and independently
binds the explicitly retained product binary, locator, source policy, source revision and every
environment/probe/measurement identity. This distinction adds no request payload or wire field.

For locator v2, the independent source verifier is retained as a readable regular file without
requiring execute bits: the explicitly retained Python interpreter reads its inherited descriptor
through `/proc/self/fd/N`. The descriptor is hash-admitted before launch and identity/hash checked
after observation, then closed on success and all failure/cleanup paths. Retention binds pathname
replacement; it is not an immutable-content claim. Source-bundle helper admission failures keep
exit 2, while invalid explicit CLI pairs keep exit 1. The Linux containment floor and existing
cleanup-error precedence remain; legacy locator-v1 launch behavior is unchanged. A5 adds retained
helper path replacement, observed-content mutation, descriptor cleanup and actual inherited-reader
source observation to its focused source-revalidation owner.

The independent gate validator keeps its source-root, Python and Git explicit inputs. For a
version-2 locator the exact planned invocation is:

```sh
python3 scripts/prompt-gate-validator.py --source-bundle-root SOURCE_ROOT --python-executable-path PYTHON --git-executable-path GIT --product-executable-path PRODUCT --product-executable-sha256 SHA --gate-manifest MANIFEST
```

Paths supplied for executables/source root are explicit absolute paths under the existing
admission rules. The product path/digest pair is opened and verified without launching the
product, then bound to the locator and policy. Historical version-1 replay keeps the existing
`--generation-child-path`/`--generation-child-sha256` pair. Require exactly one complete pair;
reject mixed, missing or version-inconsistent pairs. Retain exit 0 for valid evidence, 1 for
invalid explicit input, 2 for rejected bundle/evidence and 3 for cleanup failure. The outer gate
manifest keeps its schema because the referenced locator declares its own version. A5 owns both
the old byte-stable chain and the new independently recomputed chain, including identity mismatch,
source revalidation and intermediate-attempt mutations. The existing `--gate-manifest` default
remains historical; new evidence supplies its manifest explicitly.

Outer result/evidence/row records keep their current algorithms and schema versions where their own
field set is unchanged; nested records carry their own version. All consumers must dispatch on that
version, reject mixed legacy/new task/runtime/input identities, and keep old fixture bytes stable.
There is no key-presence-based version inference. C4 optional edit policy is validated by version-2
task data and its declared edit grammar, never by a Python filename. No new source-verifier or
snapshot subprocess protocol is introduced: their existing result records become Align-produced
evidence. Application source/revision ancestry, corpus hashes, effective prompt/provider bytes,
paired seed, per-attempt traces and all acceptance-policy inputs remain identity-bearing.

Unknown fields, UTF-8/NUL handling, bounded canonical scalars/strings, omitted `Option::None` and
digest preimages follow the owning record's existing C6 codec contract. Removed version-1 execution
fields are explicitly rejected on version-2 request/task/policy documents, rather than ignored by
a declared-record decoder. The migration never silently drops a helper declaration then executes
with different meaning. There are no new inferred defaults or machine paths in frozen corpora.

Product executable admission uses a new explicit 268,435,456-byte main-image ceiling. This is a
cutover limit, not a claim that the historical generation child already had that cap. The private
`prompt_product_image.admit(root, relative, expected_sha256, maximum_bytes)` helper keeps its cap
explicit, streams in at most 65,536-byte chunks, and retains the requested regular single-link
executable reader throughout admission. It independently opens the actual running main image via
`process.current_image`, checks bounded content and unchanged descriptor metadata before/after,
and copies those exact observed bytes into an executable memory writer. Both observed digests must
match the admitted lowercase SHA-256; sealing and `process.executable` then return independently
owned immutable launch authority. A running sealed/unlinked image may have zero links. No caller
pathname, argv[0], libraries or source provenance substitute for the running-image observation.
macOS refuses the Linux-only capability explicitly; there is no helper fallback. The focused image
owner covers matching launch authority and path replacement on Linux, malformed input/bounds and
unsupported-platform refusal; final A2/A4 still own integrated execution.

Task-definition admission retains the existing seven-field schema-1 descriptor consumed by
`run-coding-task.py`: schema_version, id, source_dir, source_revision, allowed_edits,
validation_argv and validation_timeout_seconds. The Align decoder rejects unknown/missing fields,
requires nonempty strings and nonempty lists of nonempty strings, and preserves the historical
40-Unicode-code-point revision length check (Git admission separately authenticates the revision).
Two explicit parser limits apply to new evaluation: duplicate keys are rejected by the shipped
JSON decoder, and timeout seconds must be a positive representable i64. Execution converts seconds
to nanoseconds with checked arithmetic and applies the enclosing admitted deadline; it never wraps
or clamps an overflowing declaration. Frozen historical descriptors and evidence remain unchanged.
The decoder consumes caller-bounded source and returns owned data; it does not resolve source_dir,
execute validation_argv or authorize a shell. Owner `prompt_task_definition_smoke.align` covers the
exact field/type rules, duplicate/numeric limits, Unicode length and source-owner expiry.

### 3.2 Temporary state and inventory schema

No existing violation is retrospectively justified as a bootstrap. The inventory class remains
`PRODUCT_LOGIC_VIOLATION` for every file owning product behavior. Its SHA-256 freezes the audit
checkpoint; no feature addition is allowed while migration is pending. Removal means removal from
the product execution closure, followed by deletion or explicit retention solely for independent
historical replay. Historical adapters can remain at their digest-bound paths when frozen tests
need them; current commands must not select them.

A future `TEMPORARY_PRODUCT_BOOTSTRAP` entry requires, before use: an Align inability with concrete
evidence; exact blocking request (or explicit application reason); named migration capability;
consumer acceptance command; deletion condition; no-feature-growth rule; and reviewed source hash.
None is authorized by this plan. A changed hash alone is never approval for additional features.

`docs/python-boundary-inventory.json` has `schema_version: 1`, `audit_head`, `align_revision`,
`sibling_head`, `files`, `embedded_hosts`, `launch_sources`, `data_only_sources`, and
`manifest_sources`, and `replay_only_manifests`.
Every file row has exactly the
fields `path`, `classification`, `behavior`, `reachability`, `substitution`, `python_reason`,
`target`, `migration`, `acceptance`, `frozen_sha256`, `bootstrap`. The hash is lowercase SHA-256 for a current
violation/bootstrap and null otherwise. Paths are unique UTF-8 repository-relative paths. Each
classification is exactly one of the seven categories in the audit. Required text fields are
nonempty; `migration = N/A` is permitted only with a reason in `target`.
`bootstrap` is null except for a temporary-bootstrap row, where it contains nonempty `reason`,
`align_blocker`, `migration`, `acceptance`, `deletion_condition`, and `no_growth` strings.

`embedded_hosts` rows use the same fields for shell/build/image containers invoking Python;
they are not counted as standalone Python files. `launch_sources` maps each production Align
module importing `std.process` to its reviewed whole-file SHA-256. New process owners and changed
owners require an updated reviewed boundary record. Production means the recursively resolved
local import closures of `src/main.align` and `src/ggml_spike.align`; test filenames are not globally
excluded. `data_only_sources` freezes modules whose script/interpreter literals describe language
detection, historical evidence or retired-command refusal rather than executing a helper; they
cannot also be process owners.
`manifest_sources` maps the exact independently discovered set of repository JSON files whose
top-level object contains `cmd` or `snapshot_cmd` to whole-file SHA-256. Include tracked and
nonignored untracked files. This conservative command-carrier inventory binds argv changes even
between frozen helpers; it does not claim that every recorded manifest executes. Nested historical
evidence is not selected by this top-level rule. Both modes reject missing/new/changed manifests
until their inventory change is explicitly reviewed; strict mode additionally rejects product
delegation. The checker never derives approval by updating its own inventory.
`replay_only_manifests` is a unique list of paths contained in `manifest_sources`, empty at this
checkpoint. At cutover, reviewed retirement may place an immutable historical command carrier
there after its selected Python implementations have been reclassified as independent replay.
Its hash stays checked, but its historical command is excluded from current-product role checks.
It cannot conceal a violation/bootstrap; those rows fail strict mode wherever referenced.
This classification requires P8 refusal and A4 runtime evidence before final acceptance. Strict
mode also refuses interpreter/local-script literals in a process-owner module even when its
whole-file hash is recorded; source hashes do not authorize strict product delegation.
All standalone
Python, shebangs, and executable shell hosts containing Python are discovered independently of
the inventory. Static literal references to local scripts or interpreters are examined across
that closure. Also inventory the documented/default task-manifest argv reached through `eval`,
`verify` and prompt tasks; the old coding-v1 corpus is a named frozen replay dependency, not a
permanent exception for a shipping coding path. Unclassified bundled commands fail closed. Caller-supplied build/test argv remain permitted; arbitrary dynamic subprocess
construction needs review and the A4 runtime proof. The checker does not parse arbitrary shell
programs or prove unrestricted call-graph reachability.

### 3.3 Manifest-selected legacy coding execution

The current `main --eval eval/tasks/coding-v1.json` is a product launch even though its Python
command lives in JSON. At cutover, `eval.run_suite` admits every task before calling `verify.run`.
It refuses `corpus_id = coding-v1` and any direct executable/interpreter task declaration selecting
one of the eight retired product implementations in the audit. Selection checks use the resolved
repository-relative path and the retained selected file's frozen SHA-256; moving the old corpus,
renaming the runner, or changing only the corpus ID cannot restore that route. Keep this finite
retirement data in the Align admission owner; the product does not read the developer inventory
or invoke its checker. P7 must also reject newly bundled implementation commands before
qualification; that static check is separate from runtime task admission.

Refusal returns `Error.Invalid` before any task subprocess and before emitting task/suite result
lines. Ordinary file/decode errors keep their current error behavior. If a later task is refused,
an earlier task in the same corpus must not already have run; retained admitted inputs are used
through dispatch rather than reopened unchecked. No new corpus/task schema or global ban on
Python executables is introduced. The existing Git smoke corpus and explicit target-project
tests retain their wire and execution semantics. This rule covers the supported first-party
launch descriptors; it is not a sandbox claim that arbitrary caller-supplied shell programs can
be statically proven free of implementation code.

The replacement coding fixture is a new version-2 `PromptEvaluateRequest`/task corpus executed
through `main prompt evaluate REQUEST RESULT_RELATIVE`, with `FIXTURE_PATCH` and `PROVIDER_EDIT`
owned internally by Align. Its A2/A4 cases exercise coding, validation and repair; updating
`make eval-coding` and normal examples to this route belongs to the same cutover. Keep
`coding-v1` files and their baseline hashes unchanged for explicitly external historical replay.
Merely publishing the new corpus while leaving the old normal CLI route executable fails P8.

The implementation owner is `eval_retirement.admit(cmd, argv, cwd) -> Result<(), Error>`.
It borrows the decoded task strings and allocates explicit temporary path/digest
storage, with no persisted format or cache identity (N/A). It inspects the direct
executable and the script selected by literal Python/env-Python descriptors, honoring
ordinary cwd/dot/symlink resolution. Python option operands (`-W`, `-X`, and
`--check-hash-based-pycs`) are distinguished from the script. Script arguments after
that script and native-tool data operands are not selected implementations. Inline
or module programs and split-string/shell wrappers remain the caller's external
program under the existing non-sandbox boundary above.

Reserved path suffixes and identities of the original repository files refuse
before dispatch. A retained regular reader supplies the selected file's SHA-256,
with before/after descriptor metadata and exact byte-count checks. All frozen files
are below 1 MiB; a larger file cannot equal a frozen digest, so it needs no content
scan. A selected FIFO/device refuses without waiting for a writer. Missing or
inaccessible ordinary programs retain their existing spawn/test error behavior.
The complete task records remain owned in `eval.run_suite` through dispatch; task
manifests are not reopened after an earlier command changes them.

`scripts/run-eval-retirement-smoke` owns all eight direct/interpreter/renamed cases,
new corpus IDs, later refusal before the first marker/result, symlink/dot/cwd/env
descriptors, FIFO admission, explicit Python tests, native tools reading historical
source as data, ordinary spawn/test errors, and task-manifest replacement after
complete admission. The A4 owner additionally copies each frozen implementation
under a new name into its relocation fixture, and checks refusal and the complete
descendant exec trace with no Python mounted. Neither owner imports the historical
implementations into the product. A0 records this module as retirement data, not
a process owner or an interpreter backend.

The developer `make eval-coding` owner prepares a private `coding-v2` request and two task
manifests through `scripts/run-prompt-evaluation-native-smoke coding`, then invokes
`scripts/run-native-coding-smoke`. The latter reuses the unchanged inclusive-range source,
patch and external target tests, declares `/usr/bin/python3 -B` only for those tests, and
executes eight paired FIXTURE_PATCH attempts through the copied Align product. The independent
record oracle, unchanged original source and empty workspace are required. Fixture generation
and verification remain developer work; no historical runner is invoked. This owner cannot
close P8's separately required command-retirement admission or the installed profile.

`prompt_sandbox.normal`/`fresh` consume one prepared sandbox Config and an admitted bwrap image,
returning independently owned probe and validation commands. Normal rejects a fresh Config;
fresh requires it and borrows a retained namespace, duplicating that authority into both commands
at the declared slot. No optional-owner cast is used (R82 records shared optional matching).
Copy the explicit environment, runtime roots and cwd needed by two independently prepared commands
before consuming Config. Probe uses the same mounts/environment/workspace and /usr/bin/true with
a2-second profile; this replaces the historical Python `-c pass` without introducing product
behavior into an external tool. The caller has already admitted the readonly /usr runtime and
private workspace. `check` runs the prepared probe under the scope supervisor with2s, raw64KiB
captures and no validation resource scan, returning Available(report) only for zero status and
complete release/drain/untruncated output. Otherwise retain the scope/report/error in Unavailable;
prelaunch errors propagate without a local scope. Only after Available may the caller pass the
validation command to `prompt_task_validation`. Commands borrow no source Config/image/namespace
lifetime after construction. The native probe checks this concrete mount/runtime launch; it is
not the complete installed sandbox qualification. Owner `src/prompt_sandbox_smoke.align` checks
normal/fresh construction/descriptor inheritance, unchanged literal target argv after input expiry,
probe success/refusal/timeout/cancellation and explicit cleanup; final real installed A3 remains.

`prompt_sandbox_plan.arguments` consumes its explicitly prepared Config and builds the
application-owned bwrap/prlimit argv from those owned inputs. Config contains the
Config: fresh flag, real uid/gid, namespace slot, absolute bwrap/prlimit/workspace paths, admitted
readonly runtime roots, target argv, target environment and positive timeout seconds. Normal mode
uses the frozen unshare-all/uid/gid/cap-drop profile, /usr readonly plus explicit additional runtime
roots, standard usr symlinks, proc/dev and64MiB tmpfs mounts; create missing namespace parents
for additional roots/workspace and bind the workspace with its .git readonly. Fresh mode uses an
explicit namespace slot3..1023, the existing IPC/PID/network/UTS separation and mount-guard profile,
root/workspace tmpfs, exact optional runtime roots from /tools,/usr,/bin,/lib,/lib64,/runtime,
the /target/tmp bind and64MiB /tmp,/dev/shm. Require /tools and /usr in fresh roots and /usr in
normal roots; normal additional roots must be disjoint and cannot cover the workspace or overlap
the reserved /tmp,/dev,/proc,/bin,/lib,/lib64,/sbin mounts. Preserve historical ordered repeated
parent-directory declarations when two roots share an ancestor. Fresh
workspace must lie below /target/tmp. Environment --setenv entries are explicit in fresh argv;
normal environment belongs to command.prepare. Append the existing mount-guard arguments in fresh
mode, then prlimit --as=536870912 --fsize=67108864 --nproc=256 --nofile=512 and
--cpu=timeout_seconds+1, separator and the target's literal argv. No shell interpolation.
Target argv0 and prlimit must lie in admitted readonly roots; bwrap image admission is separate.
Paths must be normalized absolute component paths without NUL/dot/dotdot/empty components;
workspace cannot be / or overlap a readonly root. uid/gid are0..4294967295; timeout fits the
supervisor seconds-to-nanoseconds bound. Normal mode requires namespace_slot0 (no inheritance).
Enforce readonly-root count<=16, target argv1..4096 and final argv<=4096,
environment<=256 and2MiB input/output text budgets before launch; environment validation matches
command.prepare. Return independently owned strings, never fd authority or a containment proof.
Caller admits mounts/tools, probes the selected sandbox, prepares the command from the sealed
bwrap image, and in fresh mode installs the retained namespace at the exact advertised slot
before any task launch. The old implicit Python sys.base_prefix discovery becomes an explicit
admitted runtime-root input; no Python is required to discover target runtimes. Owner
`src/prompt_sandbox_plan_smoke.align` compares literal normal/fresh argv, roots/parents/env/limits,
ownership expiry and malformed input; installed native sandbox behavior remains A3.

`prompt_evaluation_runtime` resolves execution configuration solely from the admitted task
environment policy. `ALIGN_LLM_FRESH_COMPILER=1` selects fresh mode; absent or `0` selects normal,
and another value refuses. `ALIGN_LLM_BWRAP` and `ALIGN_LLM_PRLIMIT` default to `/usr/bin/bwrap`
and `/usr/bin/prlimit` in normal mode and are required in fresh mode. Optional
`ALIGN_LLM_RUNTIME_ROOTS` is a colon-separated list of at most16 absolute roots: absent means
`/usr` in normal mode and the existing present subset of `/tools,/usr,/bin,/lib,/lib64,/runtime`
in fresh mode. Explicit empty or missing roots refuse; the sandbox-plan overlap rules still apply.
Fresh mode requires `ALIGN_LLM_VALIDATION_USERNS_PATH`, opened once as a typed retained namespace
and inherited at slot3. `LIBRARY_PATH`, `LD_LIBRARY_PATH` and `PKG_CONFIG_PATH` retain their existing
fresh fixture meanings. These names carry non-secret configuration; no ambient value supplies a
default. The only ambient read in evaluation remains the admitted provider credential, resolved
once by the enclosing evaluator and passed only to the generation-worker environment.
Target argv0 must select one declared `executable_paths` entry, either exactly or by a basename
without a slash; ambiguous basename matches refuse. The resolved absolute argv0 and prlimit must
lie in admitted runtime roots. Git uses the request's exact path and policy digest. The current
product image uses the request's path/digest and OS running-image check; bwrap is observed and
sealed before launch. This does not attest shared libraries or isolate trusted host-side writers.
Normal scratch is an exclusive0700 random child of `/tmp`; fresh scratch is beneath `/target/tmp`.
The evaluator retains its parent/root, exact device/inode and workspace until every child writer
is released. Creation, command-preparation failure, normal completion, timeout and incomplete
cleanup must all preserve this ownership. `prompt_evaluation_runtime` integration and A2/A3/A4
own configuration/source refusal, real fixed/provider attempts and explicit storage cleanup.

`prompt_fixture_environment.values` returns the single owned environment-entry sequence used by
Git commands and target sandbox preparation. Explicit inputs are fresh, the three library-path
strings and validation. Preserve the existing fixture HOME/PATH/TMPDIR and deterministic Git
identity/isolation/locale values. Fresh includes PYTHONHOME=/usr and both Python site/bytecode
settings; validation in normal mode also adds those two settings for permitted external Python
tests, while fresh validation changes TMPDIR to/tmp and adds ALIGNC_CACHE=off. These values do
not launch Python. Reject NUL in used library values; normal mode ignores those values. No ambient
read or schema change. Output has unique names and independent owned strings. Fixture command
construction consumes this shared sequence through ordered native setters; sandbox preparation
passes validation entries to both command.prepare and the fresh --setenv plan. Existing real Git
command owners plus literal normal/fresh validation environments and source-expiry cases verify
the extraction; no aggregate is added for identical values.

`prompt_command.prepare` marshals owned application argv/environment into an independently owned
verified-image command. Inputs: borrowed image, argv slice of owned strings (1..4096, nonempty
argv0), absolute NUL-free cwd, and up to256 Environment{name:string,value:string} entries with
nonempty NUL/equals-free names and NUL-free values. Bound cwd to4096 bytes and combined argv/env
text to2MiB with checked addition; empty non-argv0 arguments and empty environment values remain
valid. Validate everything before command construction, then use an explicit named arena for
borrowed argv views, command_image's native copy, cwd, env_clear, ordered env setters and new
session. Duplicate environment names retain the native last-value rule. No ambient reads, launch,
timeout or sandbox policy occurs here. Owned command outlives all temporary strings/arena/image
inputs. Owner `src/prompt_command_smoke.align`: Linux sealed-image execution after input expiry,
literal whitespace/metacharacters/NUL refusals, cwd/env behavior, empty/duplicate values and bounds.
The explicit named-arena argv construction also passes a managed native echo prototype; no new
language surface or implicit owned-string-to-view-array conversion is assumed.

`prompt_tool_image.admit` turns an expected tool digest into retained immutable launch authority.
Inputs are borrowed directory, strict relative raw path, expected lowercase64-hex SHA-256, byte cap
1..268435456 and monotonic deadline. Open a no-follow single-link regular reader, require at least
one executable permission bit, stream64KiB chunks into an Executable memory writer while hashing,
and check exact observed length and before/after descriptor/path metadata. Require matching digest
before sealing and admitting the native ELF image. The returned process.image outlives input,
directory and writer owners; no execution or PATH lookup occurs here. All failures drop partial
memory/reader owners. The caller owns explicit runtime/library dependencies and source isolation;
metadata rechecks do not create an atomic snapshot guarantee. This is ordinary tool admission,
distinct from product-image admission's mandatory current-running-image binding. Owner
`src/prompt_tool_image_smoke.align`: real Git image hash/launch after source unlink, wrong digest,
mode/kind/link/cap/deadline refusal, non-ELF executable rejection and owner expiry; macOS explicitly
refuses the native executable-memory surface.

`prompt_fixture_command.build` constructs independently owned commands from an admitted sealed
Git image, a caller-admitted private workspace path, explicit environment Profile and closed
Operation. Operations are Init, ConfigureNewlines, ConfigureModes, Add, Commit, Status, Head,
Tree, IndexFlags, Index, Staged, Untracked, Ignored, ApplyCheck and Apply. Tree/Staged take the
admitted40-lowercase-hex revision; ApplyCheck/Apply take an admitted absolute patch path. Other
operations require an empty operand. Exact argv/options and deterministic Git author/committer
identity/date match `run-coding-task.py`; machine lists retain NUL framing and disable external
diff/renames where specified. Init explicitly selects SHA-1. Environment is cleared and rebuilt
from the historical normal/fresh fixture profiles, including the six Git identity values,
system/global config/attributes exclusion, no replacements and C locale. Fresh library paths are
explicit caller inputs, never ambient reads; reject interior NUL in fresh fields before allocating
the command, while normal mode ignores those fields. Command uses a new session
and the supplied cwd; no shell, timeout controller, process launch or filesystem mutation occurs
until the caller launches it. The caller runs the scope supervisor with a10s budget, refuses
nonzero status/incomplete cleanup and checks raw-machine-output truncation before parsing.
Owner `src/prompt_fixture_command_smoke.align` exercises the sealed real Git image on Linux,
deterministic fixture creation against an independent Git oracle, raw records, explicit environment
isolation, malformed operation inputs and patch checks/application. Path isolation remains the
caller's retained private-parent contract; cwd is the shipped pathname setter, not an invented
descriptor cwd primitive.

`prompt_fixture_setup.initialize` executes the fixed fixture Git operations in order:
Init, ConfigureNewlines, ConfigureModes, Add, Commit, Status and Head (seven launches).
The source copy and expected revision admission happen before this call. Each already-admitted
image command runs under the Align scope supervisor with10s and raw64KiB captures; the caller's
signal subscription and private workspace/procfs roots stay borrowed. A command attempt is
accepted only for Collected, Exited(0), released cleanup with no error, successful final drain and
untruncated machine output. Otherwise return a Stopped record retaining the exact operation index,
scope and full report (or the explicit unexpected supervisor error when no report was returned);
the caller must recover an unreleased scope. Native construction errors
before launch propagate; malformed output after a released attempt refuses. Status must be empty;
Head must be exactly the expected40-hex revision plus LF. Success owns no live child scope and
returns Ready. No workspace deletion or signal restoration is hidden. Owner
`src/prompt_fixture_setup_smoke.align`: source-copy-to-Git initialization with independent expected
revision, bad revision/output refusal, retained command failure and cancellation without launching
later operations. This internal integration becomes part of final A2/A3, not a separate rewrite PR.

`prompt_git_observation.observe` runs Head, Tree, IndexFlags, Index, Staged, Untracked and Ignored
through the same admitted Git image/environment and scope supervisor (10s per command). Refuse a
changed HEAD and non-H index flags before accepting other state. Parse complete untruncated raw
records with `prompt_git_records`; retain the full raw index bytes for post-validation equality.
Return owned tree/staged/untracked/ignored data and raw index in Ready, or a Stopped attempt owning
the unreleased/failed scope and report as in fixture setup. Native prelaunch/parse errors propagate
only with no live local scope. The caller retains isolation, snapshots directory/content state,
compares before/after index bytes and applies `prompt_worktree_changes` admission. No Git output
failure becomes an empty path set. Owner `src/prompt_git_observation_smoke.align` composes real
fixture setup, staged/unstaged/untracked/ignored changes, index flags and HEAD mutation; machine
truncation and malformed raw inputs retain their focused parser/supervisor owners.

`prompt_task_validation.run` executes one admitted fixture candidate against a caller-prepared,
rerunnable sandbox command. The caller owns sandbox/tool/namespace admission, private workspace,
patch path, expected source revision, signal subscription and credential Pattern. Validate positive
representable timeout seconds before launch. Capture original directory state, run pre-repair
validation (which must fail), and require pristine Git/worktree state afterward. Git ApplyCheck
and Apply then run under the same scope supervisor. Require allowed nonempty tracked changes and
unchanged directory modes before post-repair validation. Re-observe Git/worktree afterward and
require both candidate content and raw index unchanged, including allowed paths; only then does
the post-repair exit status choose Passed or TestFailed. Other completed outcomes are
UnexpectedBaselinePass, PristineChanged, PatchRejected or PolicyViolation. Return both available
owned validation reports with completed outcomes; any incomplete command returns Stopped retaining
the scope/report/error. Prelaunch or observation errors never own a live local scope. Validation
uses declared timeout and resource defaults; Git uses10s and no validation resource policy;
stable content snapshots use an explicit10s deadline (live metadata accounting remains100ms).
This module neither constructs a sandbox nor claims an unprepared command is contained. It never
removes the workspace or restores caller signals. Owner `src/prompt_task_validation_smoke.align`
composes real Git, patch application, before/after command behavior, allowed/disallowed mutations,
non-applying/no-op patches and status/cancellation cleanup on Linux. The final installed sandbox
and evaluator producers remain required by A2/A3/A4.

`prompt_source_copy.copy` fills a caller-retained empty private destination from an admitted,
writer-isolated source tree. Both roots remain caller-owned. Before the first write, traverse
the source to refuse destination identity anywhere within it, non-UTF8 names, symlinks/special
files/hardlinked regular files, negative lengths and bounds (128 entries including root,1GiB,
4096 relative path bytes). A second bounded retained traversal copies regular files in64KiB
chunks with exclusive creation, descriptor mode normalization (0755 for any source execute bit,
otherwise0644; directories0755), exact lengths and source metadata rechecks around reads.
Each exposed native operation is bounded by the caller's absolute deadline; native calls are not
preempted. Check opened directory identity and compare final source directory metadata. Empty
destination admission and source/destination identity checks precede mutation; unrelated same-UID
writers are excluded by the caller's private-parent/isolation contract. Return entry/byte counts;
any failure keeps partial destination storage caller-owned for explicit cleanup. No Git execution,
implicit recursive deletion, source chmod, or atomic tree snapshot promise. Source identity/hash
attestation still surrounds this operation in the source admission owner. Owner
`src/prompt_source_copy_smoke.align`: exact binary/empty/chunked bytes, modes, source unchanged,
exclusive destination, invalid kinds/links/over-budget before writes, overlap, retained roots,
expired deadline and owner expiry.

### 3.4 Private-directory cleanup and unsuccessful containment

Removal is an application-owned action after containment, not a directory-handle Drop effect.
Dropping retained filesystem owners closes descriptors. Before recursive removal, the product
must establish full absence of its contained writers and retain the owned parent/root identity;
the sandbox must not expose the host parent namespace as writable. The supported threat model
excludes unrelated trusted-host processes deliberately modifying that private parent. Mode 0700
alone does not exclude same-UID descendants, and an inode comparison followed by unlink is not an
atomic replacement-refusal primitive. An observed replacement or loss of ownership refuses
removal. The language filesystem contract must state its native concurrency limits honestly.

If complete absence or the exclusive-parent condition cannot be established, preserve the first
execution error, report cleanup failure and survivors/retained workspace through the existing
failure envelope, and retain the directory for later controlled recovery. Do not publish a
successful measurement, reusable workspace, or rollback completion. In particular, do not use an
unconditional recursive-delete destructor after failed containment. Successful acceptance requires
no live children and no stale writable workspace; failed cleanup is a reported incomplete state,
not permission to delete storage whose writers remain active.

This is an explicit cutover repair of a discovered application concern. The existing Python
measurement/repair/template adapters use unconditional `rmtree` in finally blocks; evaluator and
coding-runner TemporaryDirectory contexts can unwind before definitive descendant absence. Those
paths are not evidence of an existing unconditional replacement-safe removal guarantee. R64 owns
honest retained filesystem operations; R65 owns contained writer absence and isolation; the
application owns their ordering. Cases `owned-cleanup`, `cancel-cleanup` and
`concurrent-owner-isolation` must cover unsuccessful cleanup and preservation of replacement
entries as well as successful removal.

`prompt_workspace_cleanup.remove` is the explicit final remover. Caller supplies retained private
parent/root, one raw child component, the root's originally admitted device/inode, a writers-absent
flag, positive entry cap up to32768 and monotonic deadline. The flag must come from either no
child ever launched or successful child-scope release for every launch; it is an application
precondition, not a native boolean-as-authority cast. False refuses before filesystem mutation.
Check the retained root and parent's current named entry against the expected directory identity
before traversal and again before final unlink. Walk no-follow raw names, checking each opened
child directory identity, and remove one entry at a time with explicit retained operations.
Recursion is capped at128 and relative path bytes at4096; native errors, replacement, deadline or
entry cap stop and retain the remaining private storage. Return removed entry count including
the root only after final parent.remove_dir succeeds. Partial progress is not rollback success;
no recursive Drop is introduced and no atomic replacement refusal is claimed. The private parent
must remain isolated from same-UID writers as already required above. Owner
`src/prompt_workspace_cleanup_smoke.align`: live-writer refusal preserves all bytes, root/child
replacement, raw link/special-file removal without following, partial bounded cleanup and retry,
retained parent/root rename and successful no-stale-entry removal.

`prompt_validation_resources.observe` composes process ancestry/RSS, workspace metadata and
deleted-file observations. Caller retains workspace and host procfs roots and supplies root/owner
IDs, observed root termination, limits and command deadline. Each process scan receives at most
500ms; workspace and descriptor scans each at most100ms, bounded by the command deadline. Build
at most256 retained `<pid>/fd` owners from the retained procfs root and select the Procfs context.
An acquisition NotFound is treated as disappearance only when one fresh bounded process table
also omits that PID; a present PID, any other acquisition error or failed confirmation cannot
certify complete observation. Confirm all missing candidates together within the same descriptor
deadline. This keeps missing/fake procfs input incomplete while permitting normal process exit.
All observations remain non-atomic; no unknown or denied data is zero
evidence. The caller checks `prompt_validation_budget` and gives expired command time precedence
over scan errors. Owner `src/prompt_validation_resources_smoke.align` covers live scope/workspace
composition, missing descriptor roots, caps and command expiration.

`prompt_task_supervisor.run` borrows an already-launched scope, an explicit signal subscription,
workspace/procfs roots and immutable capture Pattern; the caller owns their admission and lifetime.
Its explicit configuration supplies absolute command deadline, optional resource checking and
resource limits. The loop checks command expiration, then cancellation, then resource observation,
then finite capture polling (at most250ms). A scan crossing the command deadline is Timeout;
otherwise preserve the first observed cancellation, resource refusal or native I/O error. Check
resources on the collection iteration too, including after EOF while root is alive. Capture
overflow truncates/drains and does not itself terminate the command. The owned result contains
raw redacted stdout/stderr, truncation flags, optional root termination/maximum RSS, a separate
execution stop cause, cleanup report and optional final-drain error. No persisted schema change.
Always attempt authenticated cleanup under a fresh1s deadline, including normal completion;
then drain under a separate1s deadline and finalize both streams. Cleanup/final-drain failure
never overwrites an earlier execution cause, and prevents successful publication. A final signal
observation changes otherwise Collected into Cancelled when cancellation arrived during cleanup;
an earlier failure keeps its cause. The borrowed
scope remains caller-owned on every return; an unreleased scope and workspace must be retained
for explicit retry/recovery. This module never removes filesystem entries or closes the caller's
signal subscription. The caller must explicitly restore that subscription before publication.
Owner `src/prompt_task_supervisor_smoke.align` covers dual streams, nonzero/signal status, timeout
after EOF, descendants after root exit, capture overflow, cancellation, resource refusal and
released-before-final-drain behavior on Linux; macOS refuses scope acquisition.

`prompt_scope_capture.step` connects live child-scope reads to the incremental capture owner.
The caller retains the scope, immutable Pattern, separate stdout/stderr buffers and cursors,
Copy stream State and a writable1..65536-byte scratch slice. One finite poll (explicit nonnegative
nanoseconds) reads at most one scratch-sized chunk from each ready stream and observes root
termination without reaping. Drop EOF/status interests once satisfied; both stream EOF and root
termination are required for its collected result. Neither this result nor root exit certifies
absence of descendants. Native/capture errors propagate with the borrowed scope intact; the
supervisor performs cleanup, final drain, capture finalization and resource/cancellation policy.
No native callback or hidden process controller is introduced. Owner `src/prompt_scope_capture_smoke.align`
checks actual binary/multibyte/credential chunks, stream caps, EOF before exit, exit before EOF,
finite polls and later cleanup/release on Linux; unsupported acquisition is explicit on macOS.

`prompt_scope_cleanup` performs bounded cleanup while borrowing the caller-owned child scope.
It repeatedly obtains authenticated direct/adopted child handles, signals unfinished members with
native Kill, reaps bounded events and asks `release` for the kernel absence certificate. Newly
adopted descendants are handled on the next iteration; no numeric-PID signalling or root-exit/EOF
absence inference is used. ESRCH during a racing member kill is benign, not an absence witness.
Return released flag, total newly reaped count and the first observed native error independently;
expiration stops further signalling/reaping without dropping the scope. An initial release query
recognizes an already released or childless scope even on an expired retry. Closed scopes are idempotent.
The caller retains the scope and workspace on incomplete cleanup, preserves the primary execution
error and controls retry/final shutdown. No filesystem removal occurs here. Scan/event bounds are
explicit positive inputs up to32768/8192; the caller supplies a monotonic deadline (normal cleanup
budget1s). A1ms pause between unsuccessful passes avoids unbounded busy polling. Native calls are
not preempted. Owner `src/prompt_scope_cleanup_smoke.align` checks Linux live nested-session cleanup,
root exit/EOF before descendant absence, repeat release, expired-budget retry and status causes;
macOS verifies explicit unsupported acquisition. Final installed-profile A3 remains separate.

`prompt_capture` owns incremental raw-byte redaction and output bounds for live task streams.
It uses one immutable owned Pattern (UTF-8 credential and explicit i64 prefix table), one Copy
Cursor per stream, and a caller-owned mutable buffer per stream. Empty credentials admit raw bytes.
A prefix-table scan delays only a possible credential prefix; confirmed matches emit exactly
`[REDACTED]` once. Finalization admits any unmatched prefix and preserves the existing truncation
marker/prefix rule. Configured byte limits are0..2097152 (worker response JSON2097152,
task streams65536, measurement16384);
matched credential state is scalar and never stores an unbounded raw tail. Allocation is explicit:
credential bytes plus eight bytes per credential byte, and each caller buffer's configured cap;
final output owns its bytes. Appending after finalization refuses; finalization is repeatable.
The scalar cursor and separate byte owner follow existing exclusive-borrow rules without a native
capture policy. Native reads, deadlines, EOF and signal decisions belong to the supervisor.

This repairs a frozen capture bug while implementing its declared complete-stream replacement
contract: with credential `ED]x` and chunks `ED]x` then `x`, Python re-redacts the generated marker's
pending tail and emits `[REDACT[REDACTED]` rather than whole-stream `[REDACTED]x`. The new state
machine never interprets replacement bytes as input. It also avoids retaining repeated raw secret
matches while the redacted tail remains short. Owner `src/prompt_capture_smoke.align` plus a focused
independent full-stream bytes.replace oracle covers all chunk boundaries, overlapping candidates,
marker-like credentials, binary input, exact/overflow/tiny caps, EOF tails and lifecycle errors.
No credential or raw unredacted digest is persisted by this capture owner.

`prompt_redaction.credential` is the shared owned text producer for exact non-overlapping
credential replacement. The existing generation/experiment public helpers delegate to this one
implementation without changing signatures or replacement bytes. Evidence construction consumes
the same owner directly, avoiding a dependency on provider orchestration. Empty patterns copy the
input unchanged; all results own their storage and retain neither source nor credential. Existing
experiment/generation golden vectors and the repair evidence owner verify the unchanged behavior.

`prompt_repair_evidence` constructs persisted edit blocks from the already-admitted sorted
FILE blocks. The caller gates construction on a nonempty applied patch. It reuses
`prompt_redaction.credential` for exact literal UTF-8 replacement before body hashing,
byte counting and canonical content hashing. Carry only the whole-block prefix whose redacted
bytes fit 16384; after the first omission all later bodies are absent, while full lengths and
identities remain. Empty credentials mean no replacement. Reject malformed ordering/duplicates
and input bounds rather than repairing admission. Return owned blocks and total pre-omission
bytes; the existing EditSetBlock schema is unchanged. Diagnostic construction decodes complete
raw input, redacts the resulting text, then bounds and replacement-decodes the final byte prefix,
using `prompt_diagnostic_decode`; streaming capture and raw generation-failure order remain
separate caller responsibilities. Owner: `src/prompt_repair_evidence_smoke.align`, covering
redaction-before-digest literal vectors, exact prefix/omission/empty behavior, malformed admission,
source expiry and composition into the existing repair section renderer. No process or native
policy is introduced by this producer.

The local repair assembly owner directly implements the existing C4 six-section algorithm:
STATUS/POLICY/EDITSET/SUMMARY/STDOUT/STDERR rendering order and whole-section removal in
STDOUT/STDERR/SUMMARY/EDITSET order. Empty or undeclared sections enter neither provenance list;
STATUS and POLICY never drop. Inputs are admitted template/measurement text, with no re-redaction
or recapture. The owned result carries optional text, canonical included/dropped section lists and
final UTF-8 byte count even when the remaining text exceeds budget. `prompt_repair_sections` renders the persisted status/edit-set diagnostics and the admitted policy
using the frozen whole-file format; it shares the FILE protocol's Unicode trimming only when
choosing a non-colliding backtick fence. It never trims or reapplies persisted body contents.
`prompt_file_blocks.protocol_trim` exposes that existing rule to this renderer; the prior parser
semantics and whitespace owner remain unchanged. The template owner validates
the existing ordered schema, four/five/six-header profiles, own canonical digest, text bounds and
fixed-template-plus-128-byte-status budget before assembly. Focused owners are
`prompt_repair_assembly_smoke.align` and `prompt_repair_template_smoke.align`; neither changes wire,
retry policy, source authentication or provider execution.

## 4. Implementation closure matrix

The case labels below identify closure obligations; the implementation paragraphs above and
section 5 name their focused and composed owners. Formation/allocation, moves and
early exits follow the shipped Align model; fatal OOM is not promised recoverable.

| Affected modules / owner | Construction and success | Malformed input and failure | Early exit / cleanup / ownership | Regression cells |
| --- | --- | --- | --- | --- |
| `prompt_source_collection`, `prompt_source_admission`, `prompt_task_inputs`, existing declaration/membership owners | Original manifest row plus complete ordered expansion; retained roots and verified FILE_SET/Git | Final declaration/member mismatch, raw manifest mutation, empty/over64 tasks, per-task caps | No partial success; owned rows survive inputs; Git Stopped scope transferred; deadline/cancellation before Ready | `prompt_source_collection_smoke`: multi-task, final refusal, strict manifests, ownership, bounds; `prompt_source_admission_smoke`: manifest expiry/mutation and FILE_SET; `prompt_source_admission_git_smoke`: last-member mismatch, cancel, stopped cleanup; focused managed-pin owners passed; current A2 covers the composed consumer |
| `prompt_evaluation_documents`, `prompt_evaluation_inputs`, `prompt_task_inputs` / A2 | Decode the six request documents and complete ordered task inputs, then return one owned identity bundle and paired scalar schedule | Wrong request/schema/sample bounds, scope or corpus identity mismatch, source-policy/product mismatch, invalid task set, seed overflow or expired retained source | No dispatch or publication; a failed final task, expired root or invalid identity returns before a bundle or schedule is exposed | `prompt_evaluation_inputs_smoke`: synthetic complete bundle, scope/source-policy mismatch, absent parent path, invalid sample, seed/sample bounds, paired order and full-source expiry; focused managed-pin owner passed; current A2 covers the composed consumer |
| `prompt_artifacts`, `prompt_artifact_io`, `prompt_score` / A1/A5 | Versioned decode, bounded canonical encode, same semantic score; before/after source lifetime; version-4 measurement identity in every attempt | old/new mix, removed execution field, wrong version/hash, cap overflow, forged base adapter or intermediate producer identity | Move record/array return, borrow expiry, partial-decode release, pair publication failure | `schema-v2-golden`, `measurement-v4-golden`, `fixture-measurement-v4`, `legacy-byte-replay`, `mixed-producer-refusal`, `forged-base-adapter`, `intermediate-producer-mismatch`, `removed-helper-field`, `source-expiry`, `pair-occupied`, `pair-second-write-failure`, `streamed-digest-parity`, `canonical-digest-cap`, `digest-source-expiry` |
| `prompt_render`, `prompt_model`, new `prompt_repair`, `repair`, `verification_loop` / A1/A2 | Shared renderer/repair policy, declared attempt budget and first-pass/repair success | malformed edit blocks, refusal classes, empty/unchanged edit, repair section drop ladder | stop after pass, budget exhaustion, declined repair, diagnostics ownership and redaction | `render-independent-parity`, `first-pass`, `repair-pass`, `repair-exhausted`, `edit-refusals`, `repair-drop-ladder`, `credential-redaction` |
| new `prompt_workspace`, `prompt_source` / A2/A3 | Private root, exact source/corpus/tool identity, pristine attempt checkout and bounded snapshots | symlink/hardlink/FIFO/device, raw byte name handling under the existing FILE_SET contract, concurrent replacement, Git config/hooks/replacement/graft, ordinary/linked checkout | input rejection before provider; remove only owned paths, close retained inputs, preserve first error, report survivors | `raw-tree-parity`, `raw-tree-rejection`, `retained-source-replacement`, `linked-worktree`, `git-config-nonexecution`, `input-change`, `owned-cleanup`, `nested-workspace`, `workspace-type-refusal`, `host-identity-observation` |
| new `task_validation`, `verify` / A2/A3 | Explicit environment/argv/cwd and resource profile; captured status/diagnostics | absent containment tool, nonzero test, timeout/output overflow, memory/file/process limits | nested `setsid`, zombie leader with live thread, adopted zombies, abrupt cancellation; successful cleanup leaves no live child or writable stale workspace; failure retains storage and reports incomplete cleanup under section 3.4 | `containment-unavailable`, `validation-nonzero`, `capture-limit`, `timeout-after-eof`, `descendant-escape`, `zombie-thread-group`, `resource-ceilings`, `cancel-cleanup`, `verified-exec-replacement`, `sealed-input`, `descriptor-allowlist`, `concurrent-owner-isolation`, `current-executable-mismatch` |
| `prompt_evaluate`, new `prompt_task`, provider modules / A1/A2 | Ordered paired execution, native prompt rendering, explicit seed, single provider wire producer, complete result/evidence | provider failure, seed rejection, invalid task, unusable source, tampered rendered identity, incomplete evidence | no retry after terminal success; no acceptance after failure; close invocation resources once | `scripts/run-prompt-task-smoke`: rendered/request identity and refusal cases; later `paired-order-seed`, `provider-request-parity`, `provider-failure`, `skipped-attempt-shape`, `ineligible-result` |
| `eval`, `main`, `verify`, new `task_validation` / A2/A4 | Complete external-task admission; existing Git smoke and explicit target Python tests; new Align coding corpus | reserved legacy corpus, copied/renamed frozen runner, changed corpus ID, later invalid task | no child/result before complete admission; retained inputs released on refusal and after dispatch | `legacy-eval-refused`, `legacy-eval-renamed-refused`, `legacy-eval-new-id-refused`, `eval-preflight-before-child`, `eval-python-target-allowed`, `align-coding-corpus` |
| `prompt_artifacts` and independent `scripts/prompt-gate-validator.py` / A5 | Locator v2, product/policy/core binding and independently observed verifier/Python/Git; legacy v1 replay | mixed locator/CLI versions, wrong product/policy/oracle identity, mutated source and intermediate measurement | bounded decode; release retained inputs on every exit; source verifier cleanup retains terminal precedence | `gate-locator-v2-golden`, `gate-legacy-replay`, `gate-mixed-input-pair`, `gate-product-mismatch`, `gate-oracle-mismatch`, `gate-source-revalidation`, `intermediate-producer-mismatch`, existing gate cleanup cases |
| `prompt_state`, `failure_memory`, `persisted_result` / A1/A4 | accept/rollback and failure memory preserve established semantics | missing evidence, ancestry mismatch, corrupt prior state | existing destination preservation; never mutate historical source evidence | `accept-rollback`, `failure-memory-parity`, `legacy-activation`, existing C7 owner |
| `main`, build launchers, distribution / A4 | ordinary build outputs; index/generate/evaluate/repair/accept/rollback and runtime exercised outside checkout | unavailable backend is truthful; no automatic Python fallback or download | no repository scripts/interpreter available, external task tools isolated and explicit | `relocated-no-python`, `external-python-task`, `runtime-real-backend`, `no-helper-fallback` |
| runtime/`ggml_ffi`/native shim / A6 | retain model/graph/policy ownership; native resource operations unchanged | existing backend/memory/op refusal remains observable | native Drop/unload safety and session ownership unchanged | existing GPU/provider/session owners if touched; native callsite audit for unchanged source |

Global runtime process state is not shared between independent evaluation invocations; each owns
its private root and containment domain. Concurrent publication to the same result path uses the
existing no-replace rejection. A failure to construct a second invocation must not terminate or
release the first. Source readers outlive borrowed views; writers and subprocess owners do not
escape through error records. Whole-program and per-unit compiler builds cover changed public
Move/borrow boundaries; no new generic or foreign ABI is promised by this plan (N/A unless an
implementation delta adds one).

## 5. Acceptance commands and measurement limits

The cutover coordinator accepts exactly one of `--functional`, `--containment`,
or `--no-python`. `--binary` selects an already built product (default `main`);
qualification does not silently rebuild it. `--no-python` additionally requires
`--models`, `--libraries` and `--shim` directories for real inference. Functional
and relocation owners require Linux. Containment includes the focused native
resource/scope owners and the required installed profile, removing `DOCKER_HOST`
for that profile; `--align-repo` may name its exact compiler source. Any missing
prerequisite or failed child stops the coordinator with a nonzero exit. It is
developer tooling only: it does not produce product decisions or evidence.

`run-prompt-evaluation-native-smoke cutover` copies the supplied product once,
constructs its private inputs, and runs the normal CLI/refusal/repair/failure/provider
owners. `cutover-no-python` also runs the evaluator and provider relocation owners
before removing that private fixture. The independently generated coding fixture
runs at the end. These modes reuse the completed product build but compile their
small input-fixture owner; neither skips runtime assertions. No aggregate is added.

| ID | Exact command / status at preparation | What it proves |
| --- | --- | --- |
| A0 | `python3 scripts/check-python-boundary`; `python3 scripts/test-python-boundary` — implemented as a local checkpoint | Complete inventory, allowed classes, frozen exceptions, process-owner/literal checks; independent mutation tests for missing files, shebangs, new/changed launches, manifest-selected bundled commands and frozen growth. A0 PASS is not Python-free product acceptance. Historical preparation used the audit's static consistency procedure. |
| A1 | `make prompt-render-parity-smoke prompt-score-smoke prompt-score-prefix-smoke prompt-verifier-smoke prompt-state-smoke` — PASS; state also passes with the relocated native product | Independent renderer/scorer vectors, evidence, acceptance/rollback. Historical vectors remain separately decodable. |
| A2 | `python3 scripts/run-align-product-cutover --functional --binary "$CUTOVER_BINARY"` — PASS; `make eval-smoke` — existing owner, adapted in cutover | Complete public input/refusal/failure/repair/provider/coding flow, together with the separately named section-4 focused owners; independent Python verification remains outside the product process tree. Includes old `--eval` rejection before any child, preserved external-test execution and the new Align coding corpus. Historical references stay frozen; the independent validator gains the specified new schemas. |
| A3 | `python3 scripts/run-align-product-cutover --containment --binary "$CUTOVER_BINARY" --align-repo "$PINNED_ALIGN_SOURCE"` — PASS with the actual installed Linux Docker profile | Required Linux installed profile, resource/descendant/tree/integration cases; no Docker skip, ambient endpoint or host-only substitute. Request 53 retains its original layer-forward acceptance in addition to this owner. |
| A4 | `python3 scripts/run-align-product-cutover --no-python --binary "$CUTOVER_BINARY" --models "$CUTOVER_MODELS" --libraries "$CUTOVER_LIBRARIES" --shim "$CUTOVER_SHIM"` — PASS | Build once with developer tools, relocate declared product outputs/data outside the checkout, run a non-Python coding fixture and all normal command families in an environment where Python binaries and repository scripts cannot be executed. Observe full descendant execution; hiding PATH alone is insufficient. Include P8 old-corpus refusal and Git smoke. Separately run an explicit Python target project with Python available only to its test tool; product decisions remain Align. Real inference uses the explicit real backend build, not the unavailable stub. |
| A5 | `python3 scripts/check-python-boundary --strict` — PASS with zero product exceptions after runtime retirement; `make prompt-gate-validator-smoke prompt-gate-source-bundle-smoke prompt-gate-source-revalidation-smoke` — existing independent owners, adapted in cutover | Zero product violations/bootstrap and no hardcoded Python/local-helper product delegation; historical identity/retirement literals are reviewed data. Independently verify the new corpus, locator v2 and measurements v4, both explicit-input branches, all attempt identities and unchanged legacy bytes. Historical Python adapters cannot be selected by normal requests. |
| A6 | Native responsibility audit and existing `make runtime-provider-smoke` — PASS (sampler plus 61 CLI assertions); no native ABI change | No product behavior moved to C; unchanged qualified GPU history is not rerun solely for this plan. |

Runtime observation must distinguish host logical CPU count from process-available parallelism;
Request 66 owns that missing observation, while the shipped `process.cpu_count()` is quota-aware.
Do not substitute declared host facts for independently observed environment evidence.

Publication uses the shared `scripts/pre-pr` classifier and an applicable owner; this preparation
does not wire a new aggregate, alter the installed profile, or run `make ci`. Future cutover changes
to those boundaries select their ordinary required checks. Static and runtime proof are both
required before declaring final compliance. The independent verifier may be Python, but its verdict
is external acceptance evidence; shipping accept/rollback recomputes its own decision in Align.

Migration itself makes no performance claim and therefore has no new benchmark shipping floor
(N/A). Preserve quality, caps and existing semantics first. Do not translate Python elapsed times
into Align performance gains or inherit historical measured acceptance as a new comparison.

## 6. GPU follow-on, without reopening the completed campaigns

The supplied 2026-09-07 speed-ideas memo is a hypothesis input. Its cross-hardware multipliers and
claims of impossibility/uniqueness are not accepted performance contracts. The completed Metal and
CUDA correctness receipts and negative speed results remain at their actual qualified heads.
The [performance plan](gpu-runtime-performance.md) retains its baseline, quality, cost-ceiling and
shipping-floor ownership. No old G1 stage is restarted by this plan.

At cutover, preserve the explicit Align ownership already present in `runtime_generation`,
`runtime_execution`, `runtime_memory`, `runtime_attention`, `runtime_kv` and `runtime_sampler`.
The current shim already probes graph operation support; treat that as existing behavior, not a
new optimization. Prefix persistence and reusable runtime sessions also have existing owners;
new work must name the missing integration, not rebuild them under new names.

After cutover, select the next measured consumer from: (1) reuse of stable repository prefix/KV
across real repair turns, (2) separate prefill/decode placement and batch choices, (3) MoE submission
and synchronization with actual capture/replay observation, (4) expert residency and useful model
capacity, (5) prompt-lookup speculation and measured kernel bottlenecks. This is an investigation
order, not five required PRs, guaranteed improvements or authorization to run a campaign now.
Compare both fixed-model inference and time to a passing patch, with capacity reported separately;
better coding quality cannot substitute for a runtime speed win, and faster decode cannot turn a
failed coding task into a pass. No speculative cache ABI or unused scheduler is added for this list.

## 7. Author consistency and review boundary

Before implementation, reconcile this ledger with architecture, roadmap, C6/C4 execution clauses,
the audit and request register. Each implementation matrix cell above has a consumer owner;
future aggregate commands are expressly unimplemented; A0 now has an implementation owner.
The current local checkpoint adds narrow source/task/evaluation-input and native prompt task
render/request owners without claiming A2/A4 cutover.
The preparation review covers classification, scope, prerequisites, wire deltas and enforcement
limits. Review does not advance any Align request or prove a future consumer test has passed.
