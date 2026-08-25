# C6 Prompt and Context Optimizer

Status: design plan of record; C6-LIFECYCLE and C6-EVALUATION are implemented foundations, including
artifact codecs, rendering, failure-memory selection, verification, offline activation, deterministic
contained comparison, and result/evidence publication. C6-MEASURED remains to deliver provider
proposal and measured acceptance through the consumer-complete capability waves in Section 11.
Historical C6a-C6g labels identify acceptance and ownership cells, not required branch or pull
request boundaries. No code may target a proposed Align surface.

This document refines C6 from `docs/specs/roadmap.md` and the Prompt Optimizer contract in
`docs/specs/align-llm.md`. If this document conflicts with either parent specification, the parent
specification wins until the conflict is resolved in a separate design change.

## 1. Goal and gate

C6 lets a model propose a bounded learned prompt/context overlay, measures that overlay against its
current parent on a fixed coding-task corpus, accepts only a measured improvement with no serious
regression, and creates a new immutable activation that can be rolled back.

The C6 gate is complete only when all of the following are true:

1. The four logical commands exist:
   `align-coder prompt experiment`, `align-coder prompt evaluate`,
   `align-coder prompt accept`, and `align-coder prompt rollback`.
2. The repository's current executable exposes those commands as
   `./main prompt <operation> ...`; `align-coder` is the product name, not a request for an Align
   package manifest or installed-binary mechanism.
3. A model-provider proposal is parsed as a declared record and cannot modify the human-owned base
   prompt or fixed task prompt.
4. Evaluation runs the same fixed task adapter for the parent and candidate variants, records the
   exact inputs and per-task measurements, and rejects incomplete or incomparable runs.
5. The canonical C6 corpus contains at least two distinct fixed coding tasks and each variant has
   at least two samples per task.
6. An accepted candidate is strictly improved under the policy in section 8, has zero serious
   regressions, and is exercised by the real generation/verification consumer rather than only a
   lifecycle fixture.
7. A rollback creates a new activation that restores a previously accepted effective variant
   without deleting or rewriting history.
8. All regression checks pass through `make ci` on the pinned Align revision, and the measured gate
   passes through its named capable qualification `make prompt-gate-check` with the explicit
   `C6_GATE_*` values on that same revision.

A deterministic lifecycle smoke proves state transitions, validation, and scoring, but does not by
itself satisfy item 6.

### 1.1 Align prerequisites and blocked capability cells

The reviewed contract depends on capabilities whose shipped adoption gates are not complete. They
are recorded as separate requests in `docs/align-requests.md`; this design does not make any
hypothetical API part of C6:

1. **Request 5 — bounded HTTP response reception.** The HTTP client must enforce a caller-selected
   response-body cap while receiving, before an owning body can grow past that cap. Align shipped
   this surface, `provider_http.post_json` adopts it with `max_response_body_bytes` at the exact
   262,144-byte proposal allowance, and the request is `CLOSED` in `docs/align-requests.md`; C6e
   and the real-provider portion of C6g are no longer blocked on it.
2. **Request 6 — recursively Copy `json.scan` rows.** The scanner reuses one row slot and currently
   admits schemas with owned arrays or other transitively Move fields. C6 does not consume scanner
   rows; this request is an independent prerequisite for the later JSON escape acceptance matrix.
3. **Request 7 — escaped strings in declared-record JSON.** Typed `json.decode` must decode every
   JSON escape accepted by `json.encode` into declared `str` fields and `array<str>` elements,
   including nested records and options. This was a prerequisite for C6a and remains required by
   JSON-dependent C6 product cells. The merged C6b renderer core deliberately did not decode
   failure-memory JSONL; the C6b-memory consumer now adopts the declared-record decoder for that
   boundary. Escape-free fixtures, `json.doc`, and an application-specific base64 wire format are
   not substitutes for the declared-record round trip. Request 7 is `ALIGN_LLM_VERIFIED` at Align
   PR #850 (`18301b43d6256349f984e4aaf62e975bf4f42aa0`), with `c6-json-escape-adoption` and the
   final capable gate passing in Align-llm PR #94. C6c2 does not bypass this request: its pure
   verifier consumes only records that C6a1/C6a2 have already decoded and content-validated, and
   its implementation has no JSON reader.
4. **Request 8 — runtime construction of evaluator record arrays.** The pinned `array_builder<T>`
   accepts only scalar elements and owned `string`, while C6f2 must construct runtime-sized arrays
   of declared records such as snapshot requests, task rows, aggregates, and regression reasons.
   C6c2 also needs the declared record-array and scalar-scratch construction path to adapt decoded
   evaluation rows to the C6c1 scorer; a fixed-size local array or duplicated scorer is not allowed.
   Align provides a visible, ownership-safe construction path for the recursively Copy base record
   shapes, including partial push/build/drop behavior. Request 8 was registered in align-llm PR #32,
   its reviewed design merged in Align PR #799, and its implementation merged in Align PR #801 as
   `029e27465d79e24cd36d374aae41dca0ec7e6979`. Request 8 is `ALIGN_LLM_VERIFIED` after the
   `c6c2-request8-adoption` owner and final capable gate passed in Align-llm PR #94; C6-EVALUATION
   adds the paired-evaluator consumer evidence.
5. **Request 13 — recursive owned C6 JSON artifact graphs.** C6 artifacts contain nested records,
   options, runtime-sized arrays, and persistent text. Request 9's intentionally flat owned-text
   route is not sufficient, and the current borrowed JSON route cannot encode a record containing
   owned text fields after its input buffer expires. C6 therefore requires the exact Request 13
   graph and its shipped direct-owned route before C6a1/C6a2; a temporary borrowed wire view is
   materialized with explicit `.clone()` before its input buffer is dropped. Request 13 is now
   `ALIGN_LLM_VERIFIED` through the C6a1/C6a2 adoption wave in Align-llm PR #94.
6. **Request 10 — recursive evaluator record fields.** C6f2 also needs `Option<T>` and nested
   dynamic `array<T>` fields inside those records. Request 8 explicitly excludes them, so Request
   10 owns the separately reviewed recursive `DropPlan`, reallocation, and partial-construction
   extension. Its design merged in Align PR #802 and its implementation merged in PR #804 as
   `3ec710656c7ce7412da14a5c929529cb3e89caa3`. Requests 8 and 10 are `ALIGN_LLM_VERIFIED`
   through their ordered real-client adoption owners in Align-llm PR #94; C6-EVALUATION adds the
   C6f2 recursive result/evidence consumer qualification.
7. **Request 11 — bounded child-process capture.** Align ships the receiver-selected cap that
   kills/reaps over-limit children. C6-EVALUATION adopts it for the evaluator helper boundary and
   passes exact-cap, over-cap, timeout, post-EOF, concurrent, and descendant-cleanup evidence;
   C6g1 retains its later real-provider consumer check.
8. **Request 12 — bounded canonical JSON encoding.** The current `core.json.encode` returns a
   complete owned string and cannot prove the C6 268,435,456-byte result cap before allocation.
   Request 12 is `ALIGN_LLM_VERIFIED` through the C6-LIFECYCLE adoption wave in Align-llm PR #94;
   C6a1 and C6a2 use that shipped bounded canonical encoder, while later result/evidence writers
   retain it as a prerequisite.
9. **Request 14 — exclusive creation and no-replace publication.** C6f2's result/evidence pair
   contract uses Align's shipped `fs.create_exclusive` and `fs.rename_no_replace` surface. The
   current pin contains it, and C6-EVALUATION passes the named `c6f2-request14-adoption` gate with
   competing-creator, special-file, reverse-cleanup, and exact owned-orphan evidence. It uses no
   check-then-create, delete-before-rename, or undeclared native workaround.
10. **Request 16 — borrowed sum-payload projection.** C6c2's settled borrowed signature must inspect
   optional owned records without consuming or cloning them. Align PR #857 shipped the finite
   borrowed sum projection, and `c6-borrowed-option-adoption` now passes through the shared real C6
   graph fixture.
11. **Request 17 — borrowed dynamic aggregate projection.** The decoded graph contains dynamic
   string and record arrays, and C6c2 must pass indexed Move records to shared helpers without
   copying their owners. Align PR #865 shipped the admitted array and indexed-call projection;
   `c6-borrowed-array-adoption` and `prompt-verifier-smoke` pass at the exact pinned merge.
12. **Request 18 — retained-root regular-file access.** C6d opens every request and referenced
   artifact with `fs.open_beneath` and creates each activation result with
   `fs.create_exclusive_beneath`. Align PR #867 shipped the retained-root reader/writer surface as
   `19c3db144c462bf7d6784f88d64cc124229b7ec2`; `c6d-request18-adoption` owns the real-client
   symlink, special-file, bound, error-mapping, occupied-output, and competing-creator matrix.
13. **Request 2 — I/O timeout adoption.** Request 2 is `ALIGN_MERGED`, but its align-llm plaintext/TLS
   adoption gate remains pending. C6e and C6g1 cannot claim the provider timeout gate until that
   original acceptance target passes as C6-MEASURED's own named `c6e-request2-adoption`
   checkpoint (section 11.3).

Before a blocked consumer cell starts, every named request must reach `ALIGN_MERGED`. Batch the
requests needed by that consumer into one release build and `.align-revision` update, then pass each
original align-llm acceptance target and one final `make ci`. Do not write C6 declarations against
an unpinned newer checkout. Requests 6 and 9 remain independent of C6; Request 13 is the named
C6a1/C6a2 dependency because no C6 artifact may rely on a borrowed JSON view after its input buffer
expires.

### 1.2 Review-closure contract

The following decisions close the design-review dimensions that are easy to lose between the
schemas, command prose, and implementation checkpoints. They are normative for C6 and take precedence
over any earlier shorthand such as “bounded output” or “owning record” when the shorthand is less
specific.

#### Explicit task and environment inputs

Every adapter invocation receives one evaluator-created, content-bound `TaskAdapterRequest` file.
The evaluator appends exactly:

```text
--adapter-request <adapter-request-path>
```

The request contains `evaluation_id`, `task_id`, `sample_index`, `variant`,
`variant_path` plus its digest, `rendered_prompt_path` plus its digest, `generation_policy_path`
plus its digest, `provider_control_path` plus its digest, `workspace_path`, `result_path`,
`paired_seed`, `environment_policy_sha256`, and `content_sha256`. The adapter may read only the
declared paths and must write only its result and its owned workspace. The evaluator validates every
path, digest, task/variant/sample identity, and result location before process launch; the request
is included in the pre/post snapshot's `additional_files` and is removed during the same cleanup.
The adapter cannot infer policy, provider control, credentials, or a seed from ambient state.

`EnvironmentPolicy` is a declared, content-bound record with an explicit ordered allowlist of
environment names and values, an explicit executable search path or absolute executable paths, a
locale/encoding setting, and a non-secret source/precedence label for each value. Every helper and
adapter command starts with `env_clear()` and receives only the policy's exact entries. The
evaluator clears its own child environment before launching helpers; a credential is resolved once
from the explicitly named startup input, passed only to the adapter child that needs it, and never
passed to the snapshot helper or persisted. Ambient `PATH`, `HOME`, locale, provider variables,
credential variables, and inherited configuration are rejected or cleared. The policy digest
excludes secret values but includes the approved variable names, non-secret values, source labels,
and precedence; the provider-control artifact identifies the secret name, not its value. The
survival and rejection of every documented variable is tested in both directions.

#### Runtime ownership and bounded persistence

JSON schema notation uses `str` for a decoded view only. A decoder may borrow it while its input
buffer is live, but every record or array retained by the evaluator materializes persistent text as
an owned `string` before moving it into a collection. No persistent builder, result, snapshot,
task, row, aggregate, option, or reason contains a `str`, slice, resource, or input-buffer view.

The persistence boundary is explicit and has two phases:

1. A bounded file reader owns one `string` wire buffer. A declared JSON decode may create borrowed
   wire records, but those records are region-bound to that buffer and never cross the reader's
   function boundary.
2. Before a value enters a persistent record, builder, result, or artifact, every borrowed text
   view is copied with an explicit `.clone()` into the Request 8/10-owned record graph. Request 13
   supplies the exact recursive owned C6 JSON encode/decode path; Request 12 supplies the bounded
   canonical output operation. The owner keeps the cloned records live until encoding and writing
   finish, then drops them. There is no JSON-fragment concatenation, private wire format, hidden
   copy-on-escape, or retained `str` field.

The input/document buffer stays live until the last explicit clone completes and is then dropped.
Request 8 owns the recursively Copy base builder, and Request 10 owns `Option`/dynamic-array
recursion, deep cleanup, source nulling, reallocation, and abandonment. The closure tests cover
successful move-in/move-out, replacement, `Drop`, `?`, `map_err`, branch and loop joins, malformed
input, partial arrays, and early return at both the borrowed-wire and owned-record boundaries.

The result cap is a pre-allocation contract, not a post-encode check. C6 uses the Request 12
bounded canonical encoder for every capped persisted artifact. The Python adoption emits strings
in at most 16,384-character pieces and streams the canonical digest preimage and persisted-size
count without cloning the record graph or allocating the complete encoded result. C6 uses the
Request 11 cap-aware process surface for every helper and adapter child; `run()` followed by a
length check is not an allowed implementation. A result over 268,435,456 raw bytes returns the
bounded `RESULT_TOO_LARGE` compact error shape defined below; it never allocates or writes the
oversized result.

Every Python-owned direct process boundary starts the child in a new session whose process-group ID
is the retained direct-child PID. On timeout, output overflow, nonzero/malformed failure, or a
direct child that exits while its group still has members, the owner sends `SIGKILL` to that group,
waits the direct child, and polls the group until `killpg(pgid, 0)` proves absence. Every Python
owner first enables Linux child-subreaper mode. It enumerates direct and transitive `/proc`
descendants, kills members that entered nested sessions or process groups, reaps adopted children,
and proves both private-group and descendant absence before returning. The descendant enumeration
counts **live** entries only, and liveness is a property of the whole thread group rather than of
its leader alone. An entry is omitted only when it has fully terminated: `State: Z` with
`Threads: 1`, a zombie thread-group leader whose group holds no other task. That entry keeps only a
process-table slot until it is waited for, can never execute again, and is never a
descendant-absence failure. A zombie leader whose group still holds a live worker thread **is**
enumerated: its leader thread exited, but the worker keeps running and can still act, so omitting
every `State: Z` entry would hide a live descendant. Omitted entries are still traversed, so a live
entry parented to one is still enumerated. The two parse failures are deliberately asymmetric. A
`/proc` entry that disappears between the directory scan and the status read, or whose `PPid:` line
is absent or malformed, is skipped, because without a parent link it cannot be placed in the tree at
all. An absent or malformed `State:`/`Threads:` line instead fails closed and enumerates the entry,
because its parent link is already known and only the justification for omitting it is missing.
Child-subreaper mode makes this rule load-bearing rather than cosmetic: an orphan that
exited before its parent did is reparented to the owner and stays a zombie until the owner waits
for it, and counting it would fail containment for a process that no longer runs. The
private-group proof is a separate contract with different mechanics — a zombie member still keeps
`killpg(pgid, 0)` succeeding — and is unchanged. A group ID cannot be reused
while any member of the old group remains, and the owner sends no signal after the first complete
absence proof. A failed kill, direct wait, adopted-child reap, or bounded absence proof is
`CLEANUP_FAILED` and takes precedence over the triggering process error. Normal success performs
the same no-live-tree proof. This Linux model is required for gate evidence; a host without
`/proc/self/fd`, `/proc` parent identities, child-subreaper support, sessions, and group signaling
returns the explicit environment failure rather than claiming containment. Nested `setsid` is not
an escape from an invocation owner; the authenticated fresh-worker cgroup remains the outer owner
for abrupt termination of the complete evaluator.

The live-entry rule binds the six contained-execution owners listed in §10.1g. A seventh `/proc`
scan, in `eval/runners/run-coding-task.py`, is **deliberately deferred and does not implement it**.
That scan serves a different contract: it feeds `kill_owned_processes` and
`kill_adopted_descendants`, where signalling a terminated entry is a no-op, and
`validation_process_usage`, which counts entries against `MAX_VALIDATION_PROCESSES`. That is a
resource budget rather than a containment verdict, so a miscounted zombie inflates a budget instead
of reporting a false escape — a distinct failure domain. **Owner:** the coding runner.
**Resume condition:** the next capability that already pays for a frozen-corpus rebind and
provider-backed re-measurement, because the file is a frozen `FILE_SET` corpus member whose bytes
cannot move alone, or the next revision of the validation process budget, whichever comes first.

`src/prompt_evaluate.align` arms no second wall-clock deadline around the Python evaluator. Within
Python, every earlier-starting evaluator clock leaves its nested owner time to clean up and report:
an adapter receives the greater of its declared task and provider-control durations before the evaluator's additional 5-second margin,
the two 10-second snapshot Git operations finish inside a fixed 35-second evaluator boundary, and
the at-most-nine 10-second source-verifier Git operations finish inside a fixed 125-second
boundary. The Align wrapper retains Request 11's bounded capture and direct-child result handling.
The Python evaluator emits a one-byte discriminator plus one bounded canonical result and optional
evidence record on stdout; stderr is empty. The wrapper rejects malformed framing or an over-cap
stream, decodes and verifies the records while the captured owner lives, and alone publishes the
final result/evidence files.
`c6-evaluation-adoption` is a capable-only `make ci` goal, so capable gate execution places the
complete wrapper/evaluator tree in the authenticated fresh-worker cgroup; that cgroup is the
authoritative whole-tree owner for abrupt gate cancellation and is drained
before removal. A direct supplementary CLI run has no cleanup guarantee after an uncatchable host
termination.

#### Producer-owned environment identity

The producer/verifier table is fixed before implementation. A child never supplies the final
identity directly. It supplies a validated `EnvironmentProbe` carrier; the evaluator combines the
two matching carriers with the requested source-identity claims and policy identities.

| Field | Producer and source | Normalization and unavailable value |
| --- | --- | --- |
| `environment_id` | evaluator, SHA-256 of `EnvironmentIdentityCore` with no identity or content-digest field | lowercase SHA-256; never supplied by a helper |
| `os`, `os_release`, `architecture` | matching snapshot-helper and measurement-adapter `EnvironmentProbe` carriers | UTF-8, trimmed, bounded labels; `UNKNOWN` only when the probe explicitly reports unavailable |
| `cpu`, `logical_cpu_count` | matching carriers | normalized non-empty CPU label; `logical_cpu_count: Some(n)` is positive, `None` is the explicit unavailable value |
| `gpu` | matching carriers | normalized non-secret label; exact `NONE` means unavailable, never an omitted field |
| `align_llm_commit` | evaluator from the explicit expected identity in `PromptEvaluateRequest`; the source boundary supplies reachability separately | lowercase full SHA claim; `VERIFIED` means the named checkout proves it, while `UNVERIFIED` preserves the requested claim without proof |
| `align_revision` | evaluator from the explicit expected identity in `PromptEvaluateRequest`, checked against scope; the source boundary supplies reachability separately | lowercase full external SHA claim; `VERIFIED` means the named checkout proves it, while `UNVERIFIED` preserves the requested claim without proof |
| `measurement_adapter_runtime` | task manifest's content-bound adapter executable identity | bounded declared label/digest; carrier must match it |
| `snapshot_helper_runtime` | task manifest's content-bound snapshot-helper executable identity | bounded declared label/digest; carrier must match it |
| `source_verifier_runtime` | evaluator's content-bound source-verifier helper contract | bounded canonical runtime identity copied from the validated policy; never supplied by the helper result |
| `source_verifier_policy_sha256` | evaluator's content-bound source-verifier policy, including helper, interpreter, and Git-tool digests | lowercase full digest; the policy bytes and all executable identities are bound before source observation |
| `environment_policy_sha256` | evaluator from the validated policy artifact | full digest; included in the identity preimage |

`EnvironmentIdentityCore` is a declared record whose field order is its schema/kind fields followed
by the producer table order excluding `environment_id`; it contains `logical_cpu_count: Option<i64>`
and no identity or digest field. The evaluator
computes `environment_id = SHA256(canonical(EnvironmentIdentityCore))`, then computes the normal
record `content_sha256` over `EnvironmentIdentity { core, environment_id, content_sha256: "" }`.
This two-record construction is the non-circular preimage and is the only producer of the final
identity. `EnvironmentProbe` is an ephemeral, content-bound carrier with explicit producer,
runtime identity, and the six machine-probe fields; its `content_sha256` is verified before use.
The snapshot helper and adapter must emit matching carriers for every complete invocation. The
evaluator finalizes `Some(EnvironmentIdentity)` with one equal digest for every `MATCH`/`MISMATCH`
snapshot and every retained row; the wire-level snapshot records carry the producer-owned
`environment_probe` shown in §4.5, and the evaluator's normalized identity is retained at the
evaluation-result boundary. `ERROR` may retain a probe only when its validation succeeded. Missing
probe values are explicit `UNKNOWN`, `NONE`, or `None` according to the field table and are never
silently omitted. Fixtures cover every probe/identity field-presence, detail-level, variant, and
verification-state combination.

#### Explicit bounds for paths, commands, endpoints, and policy

All bounds below are byte bounds on UTF-8 input, not character counts. A rejected bound is
`INVALID_BOUNDS` before filesystem, process, or network side effects; C6 never truncates an
identifier, path, command, endpoint, or environment value to make it fit.

| Input family | Exact bound |
| --- | ---: |
| ordinary identifier or artifact label | 128 bytes; ASCII, non-empty |
| caller operation ID component | 96 bytes; the derived form must still fit 128 bytes |
| absolute or project-relative path | 4,096 bytes; no NUL, empty, `.` or `..` component |
| one path component | 255 bytes |
| command executable, one argument, or `cwd` | 4,096 bytes each; no NUL |
| command argument count | 64 entries including `argv[0]` |
| complete command vector | 262,144 bytes including one NUL separator per entry |
| source-verifier child timeout | exactly 60,000,000,000 ns per invocation; not caller- or policy-configurable |
| scorer reason records | `9 * task_count * sample_count + task_count + 2`; at most 9,282 records for the declared corpus bounds |
| endpoint or tokenize endpoint | 4,096 bytes; no userinfo or credential query |
| provider model, endpoint ID, or service revision | 256 bytes |
| environment variables | 64 entries, 256-byte names, 4,096-byte values, 65,536 total bytes |
| executable search paths | 32 absolute paths, 4,096 bytes each, 65,536 total bytes |
| workspace allowlist entries | 256 paths, 4,096 bytes each, 1,048,576 total bytes |
| task files and additional snapshot files | 64 and 32 entries respectively, 262,144 total path bytes per list |
| expanded tree entries | 128 files/directories and 1,073,741,824 file bytes per task |
| ancestor activation paths | 256 entries and 1,048,576 total path bytes |

The `EnvironmentPolicy` has no ambient fallback: `allowed_variables` is ordered by environment
name, contains no duplicates, excludes the provider credential name, and records each variable's
source and precedence. `executable_paths` is an explicit absolute search path; helpers and
adapters receive exactly that list after `env_clear()`. A policy's canonical bytes must fit
65,536 bytes in addition to the general referenced-artifact cap. `project_root`, `repo_path`,
`workspace_path`, `cwd`, every artifact path, every output parent, and every adapter-owned path
use the same lexical and physical checks; the list bounds above apply before expansion.
Ordinary JSON path fields require UTF-8 and reject a raw name that is not valid UTF-8 rather than
lossily transcoding it. The canonical `FILE_SET` manifest is the one byte-oriented exception: its
length-prefixed path payload may contain any non-NUL byte except `/` separators and the exact
`.`/`..` components, and the verifier traverses and hashes those bytes without converting them to
text. For UTF-8 tree paths, the tree digest still retains the raw filename bytes and `/` separators
exactly; this keeps the persisted representation and physical scan's byte order unambiguous.

Credential delivery is a separate ephemeral injection boundary, not an `EnvironmentPolicy` entry.
For an adapter child, the evaluator constructs the environment in this order: `env_clear()`, copy
the policy's ordered `allowed_variables`, then add exactly one credential entry when
`credential_env_name` is `Some`; the name must be absent from the policy and the value is the
one-shot temporary owner described below. The evaluator rejects a missing, duplicate, or
conflicting name before launch. Snapshot-helper children receive only the cleared policy
environment and never receive the credential injection. A provider call receives the same
one-shot value as an explicit boundary argument; if its implementation uses a child process, it
uses the same construction order. The injected name and value are not part of the policy digest,
environment identity, or any persisted diagnostic.

The evaluator requires the six machine-probe fields (`os`, `os_release`, `architecture`, `cpu`,
`logical_cpu_count`, and `gpu`) to be equal across the snapshot-helper and measurement-adapter
carriers. Their producer tags and runtime identities are intentionally different: each runtime
identity is checked against its own task-manifest declaration and is placed in its corresponding
field of `EnvironmentIdentityCore`. No producer is allowed to choose, omit, or hash the final
identity.

The following closure table is part of the C6 design review, not an implementation backlog. Each
row names the exact acceptance fixture that the first owning capability must add; a capability cannot claim
completion by adding only the prose or only a fixture that does not exercise the named boundary.

| Previous review class | Contract decision | First owner and exact acceptance fixture |
| --- | --- | --- |
| Borrowed wire versus owned persistence | bounded reader, explicit `.clone()`, Request 13 recursive graph, no escaping view | C6a1; `prompt-owned-wire-lifetime-smoke` |
| Environment identity circularity | evaluator-only two-record preimage plus explicit probe carriers and `Option` CPU count | C6a2; `prompt-environment-core-golden` and `prompt-environment-unavailable-smoke` |
| Environment policy and physical inputs | fixed byte/count bounds, `env_clear()`, lexical/physical path checks, no lossy filename conversion | C6a2; `prompt-policy-bounds-smoke` and `prompt-physical-input-bounds-smoke` |
| Seed capability | content-bound request digest and `APPLIED`/`UNSUPPORTED`/`REJECTED` attestation | C6e; `prompt-seed-attestation-smoke` |
| Proposal credential lifecycle | one startup read, allowlisted child handoff, pre-truncation redaction, drop before result | C6e; `prompt-credential-lifetime-smoke` |
| Derived identifiers | bounded ASCII components, exact derived forms, reject rather than truncate/hash | C6a2; `prompt-derived-id-bounds-smoke` |
| TREE root metadata | root mode/path is the first identity-bearing record, including an empty root | C6f1; `prompt-tree-root-metadata-smoke` |
| Corpus revision | tagged `GIT_COMMIT` or canonical `FILE_SET` manifest identity with no ambient branch/time | C6a2; `prompt-corpus-revision-smoke` and `prompt-file-set-manifest-smoke` |
| Command and endpoint inputs | explicit argv/path/vector/endpoint bounds and credential-free endpoint syntax | C6a2; `prompt-command-endpoint-bounds-smoke` |

#### Paths, ancestry, compatibility, and integration

Lexical normalization is not physical containment. Before any artifact or command side effect, the trusted path
boundary rejects a symlink or dangling-link component, a symlink output, a special or non-regular
input, a physical path outside the physical project root, and any workspace component that escapes
through a link. It checks the project root, workspace, every artifact/input, every output parent,
and every adapter-owned path; the same rule applies to relative and absolute spellings. The helper
does not promise race-free protection against an out-of-band mutator; the documented single-writer
precondition and preflight failure are part of the contract. Regression tests cover root,
component, output, dangling-link, physical-escape, non-regular, cleanup, and early-exit cases.

C6d is the first ordinary command owner to consume Request 18. It opens the request beneath its
lexically validated parent, opens each referenced artifact beneath the absolute `project_root`, and
creates the result beneath its lexically validated parent. Every traversal retains directory
descriptors and never restarts from a public ancestor spelling; ancestor replacement therefore
cannot redirect the operation after retention. An out-of-band writer may still mutate an already
opened regular input, so the immutable-input precondition remains. The result uses one native
exclusive create: an occupied regular file, directory, symlink, FIFO, socket, or device is unchanged,
and concurrent creators have exactly one winner.

The explicit verifier source roots are a read-only exception to the project-root-descendant rule:
`verifier_align_llm_repository_path`, `verifier_align_repository_path`, and
`verifier_corpus_source_path` may name external checkouts or a file-set root, including a sibling
checkout supplied by its absolute path. A `FILE_SET` request also names the separate
`verifier_corpus_file_set_manifest_path` sidecar. All four paths must have bounded NUL-free path
syntax, no `.`/`..` component, no symlink or dangling-link component in every existing
ancestor/root component, and the expected directory or regular-file type. A special file,
physical escape through a link, or unsafe component is `INVALID_INPUT`. A missing or unreadable but
syntactically safe source root or manifest is `UNVERIFIED`, not a reason to write or create it.
These paths are opened only by the trusted source boundary, never written or passed to an adapter,
and are not included in the project-root containment check. The source-boundary owner records the
resolved physical identity or the unavailable observation before releasing each path owner.

C6's minimum compatibility environment is the repository CI floor: Ubuntu 24.04 x86_64, Git
2.45.0 where ancestry is inspected, Rust 1.96.0, LLVM 22, CPython 3.12, GNU Make 4.3, and the
exact pinned Align release named by `.align-revision`. Newer environments are supplementary
evidence. The C6 coding-v1 gate requires a capable local or self-hosted environment but must run
the same minimum-floor checks.

Every persisted source identity claim records an exact clean commit or canonical FILE_SET manifest.
`align_llm_commit` and
`align_revision` in `EnvironmentIdentityCore` are the explicitly requested claims copied from the
validated evaluation input; they are not observations inferred from a source file or replaced by a
different checkout revision. A `VERIFIED` reachability state proves the corresponding claim from a
clean checkout; `UNVERIFIED` keeps the exact claim while recording that this evaluation did not prove
it. The external Align and corpus revisions are exact full SHA claims. The verifier source boundary
uses exact-HEAD equality rather than an ancestor-with-unchanged-scope rule, so no undefined source
scope is part of its proof. The checked-in gate is the one explicit exception: its validator derives
the actual CI align-llm `HEAD` at invocation time, requires the source-bundle checkout to equal that
head, and requires the evaluated commit in the evidence to be its ancestor. Normal merge is the
permitted integration method for this and other ancestry-bearing artifacts; squash and rebase are
not permitted when they would discard the recorded commit. CI records head, tested base tip, merge
base, and tested tree/integration identity, and verifies the required reachability before accepting
an artifact.
Verifier evidence records separate reachability results for the align-llm source repository, the
external Align repository, and the corpus source; a gate-eligible evaluation requires all three
EVALUATION-mode observations to be `VERIFIED` with their observed identities equal to the expected
claims. The checked-in gate separately validates the GATE-mode observed CI head and evaluated-commit
ancestry. The pure C6c2 verifier consumes those attestations and never walks a repository itself.

#### Complete operation overlap policy

The four public operations are `experiment`, `evaluate`, `accept`, and `rollback`. The policy is
pairwise and applies to aggregate-plus-focused and focused-plus-focused invocations as well as
two aggregate invocations:

| Pair/resource relation | Policy before side effects |
| --- | --- |
| Any pair using disjoint output paths, workspaces, and immutable inputs | supported concurrently in independent processes |
| Any pair sharing an output path or output parent race | rejected as `EXISTING_OUTPUT`/`INVALID_PATH` by preflight, or explicitly unsupported under the single-writer precondition; never last-writer-wins |
| Any pair sharing an evaluation workspace | rejected before helper/adapter launch; no overlapping adapter calls |
| `accept`/`rollback` on immutable activation DAGs with disjoint new output paths | supported as independent branches; neither mutates an existing activation |
| Any pair that would mutate a shared input, registry, active pointer, or provider credential | unsupported and rejected before side effects; C6 has no shared registry or implicit active pointer |

Within one `evaluate`, adapter calls are sequential, odd/even ordering is fixed, and no aggregate
or focused sub-operation overlaps a task call. The exact 4x4 operation matrix, both same-resource
and disjoint-resource cases, is a required `prompt-operation-overlap-smoke` fixture; process-global
concurrency is supported only for disjoint resources.

#### Syntax and Cartesian acceptance coverage

The schema and signature blocks in this design are non-normative contract notation until C6a1.
They intentionally do not claim to compile against the pinned language. C6a1 must add a pinned
Align syntax fixture with declarations separate from positional calls and run `alignc check` plus
the common `make ci` target. No current C6 code may target the merged-but-unpinned Requests 8/10
surfaces or the proposed Requests 11/12 surfaces. The ledger records this as an explicit deferred
acceptance cell, not an omission.

The C6a1/C6a2 fixtures enumerate the Cartesian product of `Option.None`/`Some`, empty/non-empty
arrays, parent/candidate variant, every terminal status, gate-eligible/ineligible, verification
`MATCH`/`MISMATCH`/`ERROR`, detail present/absent, and valid/invalid environment availability.
For each combination they assert exact field presence (including omitted `None`), row order,
ordinal, unavailable value, canonical bytes, and deterministic error precedence.

## 2. Non-goals

C6 does not:

- train or modify model weights;
- let a model change the base prompt, task instructions, evaluation policy, corpus, acceptance
  thresholds, test commands, or edit allowlists;
- accept a candidate merely because a model recommends it;
- mutate an implicit process-global or machine-global "current prompt";
- provide a prompt marketplace, distributed registry, concurrent writer service, or package
  resolver;
- optimize model routing, cache policy, or broad repository-context retrieval;
- claim a model-quality improvement from the checked-in deterministic patch fixture;
- replace C7 algorithm verification or C8 speed-first context optimization.

The full C6 context surface is deliberately limited to optional information already owned by the
verification loop: failure-memory events, patch-evaluation context, and bounded captured
diagnostics. The current C6b core starts with patch-evaluation context and diagnostics; adding
failure-memory adoption requires the later C6b-memory checkpoint inside C6-LIFECYCLE described
below.

## 3. Prompt hierarchy and ownership

Prompt composition has five ordered sections:

```text
Base Prompt
Repo Prompt
Task Prompt
Learned Prompt Append
Optional Context Sections
```

Ownership is explicit:

| Section | Owner | Candidate may change it? | Persistence |
| --- | --- | --- | --- |
| Base Prompt | human-maintained repository policy | no | content-bound input artifact |
| Repo Prompt | human-maintained repository rules | no | content-bound input artifact |
| Task Prompt | fixed evaluation task or current task | no | content-bound task input |
| Learned Prompt Append | accepted C6 candidate | yes, by replacement in a new candidate | immutable candidate and activation |
| Optional Context Sections | verification-loop owners under an accepted `ContextPolicy` | only declared inclusion/budget fields | immutable candidate and activation |

The renderer always emits the first three sections. A learned candidate cannot delete, reorder, or
substitute them. Empty learned text is allowed only when the candidate changes at least one context
policy field.

The full C6 target includes all optional context sections shown below. The merged C6b renderer core
implements the fixed hierarchy, learned append, bounded patch-evaluation context, and bounded
diagnostics. The C6b-memory consumer extends that renderer with complete failure-memory JSONL
validation and bounded selection. It starts only after Request 7 reaches `ALIGN_MERGED` and its
align-llm acceptance gate passes.

The exact rendering order and delimiters are stable:

```text
<base>

--- repo prompt ---
<repo>

--- task prompt ---
<task>

--- learned prompt append ---
<learned text or "(none)">

--- patch evaluation context ---
<included bounded content or "(omitted)">

--- failure memory context ---
<included bounded content or "(omitted)">

--- current failure diagnostics ---
<included bounded stdout/stderr or "(omitted)">
```

All text is preserved as UTF-8. A trailing newline difference is content-significant. The renderer
does not interpret learned text as code and does not treat it as a security boundary.

## 4. Immutable artifacts and identity

Existing C6 artifact writers use caller-named, immutable-after-success JSON artifacts under the
complete operation-overlap policy in §1.2. Earlier writers refuse an output path that already exists
before work starts; a caller that races a new path into existence between validation and their final
whole-file write violates the command precondition. C6d activation results are the first ordinary
exception: `fs.create_exclusive_beneath` atomically reserves the absent final entry beneath retained
parents before request-field validation, so no competing creator can be overwritten. C6f2's
result/evidence pair remains a separate blocked exception with the exclusive-create and no-replace
pair-publication contract in §5.2; it cannot start until Request 14 is adopted. There is no hidden
active pointer and no in-place registry rewrite.

This shape is intentional:

- it fits Align's implemented whole-file APIs for the existing artifact-writing slices without
  inventing rename, lock, transaction, or package features;
- an interrupted write cannot replace a previously valid activation;
- consumers select an activation explicitly;
- Git or another caller-owned system may version the artifacts without align-coder owning Git
  mutation.

Every optimizer-produced artifact and every content-bound input has `schema_version: 1`, an
`artifact_kind`, and a lowercase 64-character hexadecimal `content_sha256`. Operation request files
are control envelopes: they have a schema and kind but no content digest; every artifact they
reference is independently content-bound.

After Request 7 is merged and adopted, and Request 12's bounded canonical encoder is adopted, the
canonical payload is that shipped encoder applied to the declared record after replacing
`content_sha256` with an empty string. Therefore field order, escaping, nested records, arrays,
options, integers, booleans, and UTF-8 strings follow the pinned Align JSON encoder named by the
artifact scope rather than a second hand-written format. The bounded encoder is required before
any C6 slice writes a capped artifact. Persisted kind, status, operation, variant,
failure, stage, and reason-code fields are declared `str` fields with exact allowed uppercase
labels; internal Copy enums may map to and from them only through explicit validators. This avoids
making artifact identity depend on an implicit enum wire representation. Readers decode into the
declared record, clear the digest field, re-encode, and recompute before use. Unknown JSON fields
are ignored under Align's declared-record JSON contract and are not identity-bearing. Bytewise
stability is required only for canonical bytes emitted from the declared record: an input containing
unknown fields may decode semantically, but re-encoding omits those fields and is not required to
equal the original input bytes. `artifact_kind` provides domain separation between otherwise equal
records.

The first golden vector is normative:

```text
declared record:
  {"schema_version":1,"artifact_kind":"BASE_PROMPT","artifact_id":"base-v1","text":"x\n","content_sha256":""}
canonical UTF-8 bytes:
  {"schema_version":1,"artifact_kind":"BASE_PROMPT","artifact_id":"base-v1","text":"x\n","content_sha256":""}
content_sha256:
  21780af056f4245f2796e186c88064abe911ea287094dd22b4b3b9c8c07c4328
```

C6a adds golden vectors for every artifact kind, nested record, array, allowed label, and `Option` form
before any lifecycle implementation consumes the codec.

An output that is truncated by a crash or otherwise malformed is invalid. Recovery means rerunning
the command with a new output path; C6 does not claim atomic file replacement.

Operation IDs are bounded caller-supplied labels, not content identity. The caller-supplied
`experiment_id` and `decision_id` are each at most 96 ASCII bytes. `candidate_id` is exactly
`<experiment_id>/candidate`, `variant_id` is exactly `<experiment_id>/variant`, and `activation_id`
is exactly `<decision_id>/activation`; each derived value must be at most 128 bytes and is rejected
if the concatenation would overflow that bound. There is no truncation, hashing, or alternate
spelling for an overlong derived ID. These IDs aid diagnostics but do not replace a digest. Every
top-level cross-artifact reference carries its artifact kind,
locator path, referenced label, and full `content_sha256`. The kind, label, and digest must match
the artifact loaded from that path. The path is a locator rather than identity, and lineage is
followed by digest. Embedded records such as variants are copied in full when a later operation
must remain reconstructable without resolving the enclosing artifact.

In the schema blocks below, unannotated IDs, labels, paths, text, and digests are `str`/persisted
JSON strings; counts, byte sizes, indices, time values, and ppm values are `i64`; flags are `bool`.
Collections and optional values are written explicitly. A field whose allowed labels are separated
by `|` is a validated `str`, not an implicit JSON enum. Every present ID is ASCII and at most
128 bytes; every digest is lowercase hexadecimal. Every present required ID is non-empty; an
optional ID is empty only when its enclosing `Option` is `None`, and fields explicitly declared
empty for a baseline or invalid result remain empty. IDs and non-path labels cannot contain NUL.
Every operation request declares an absolute, lexically normalized `project_root`; all other
persisted paths are non-empty UTF-8 paths relative to that root, at most 4,096 bytes, cannot
contain NUL, and cannot contain an empty component, `.` or `..`, except for the explicitly
source-bundle-relative `PromptGateSourceLocator` paths defined in §9 and the absolute, read-only
`PromptEvaluateRequest` verifier source/helper/interpreter/tool paths. An environment-variable name
must match `[A-Za-z_][A-Za-z0-9_]*`, which also excludes `=` and every process-API-aborting form,
and is at most 256 ASCII bytes. Other provider, runtime, revision, and environment labels are
non-empty and at most 256 UTF-8 bytes. Every result `error`
and rollback `decision_reason` is at most 4,096 UTF-8 bytes. Successful terminal statuses and
complete scored evaluation statuses require `error_code: NONE` and an empty `error`; invalid or
operational-failure statuses require an allowed non-`NONE` code and non-empty detail.

Unless a schema says `ArtifactDigest.sha256` or `PromptRender.sha256`, a `*_sha256` field denotes
the referenced record's canonical `content_sha256`, not the raw bytes of one nested text field.
`ArtifactDigest.sha256` hashes raw file bytes; `PromptRender.sha256` hashes the exact rendered UTF-8
text.

### 4.1 Prompt and context artifacts

The content-bearing prompt records are:

```text
PromptTextArtifact:
  schema_version
  artifact_kind: BASE_PROMPT | REPO_PROMPT | TASK_PROMPT | OPPORTUNITY |
    PATCH_EVALUATION | FAILURE_MEMORY_JSONL | DIAGNOSTIC_STDOUT | DIAGNOSTIC_STDERR
  artifact_id
  text
  content_sha256

ArtifactReference:
  artifact_kind
  path
  artifact_id
  content_sha256

PromptVariant:
  schema_version
  artifact_kind: PROMPT_VARIANT
  variant_id
  base_prompt: PromptTextArtifact
  repo_prompt: PromptTextArtifact
  learned_prompt_append
  context_policy: ContextPolicy
  candidate_id
  content_sha256

ContextSources:
  schema_version
  artifact_kind: CONTEXT_SOURCES
  task_id
  patch_evaluation: PromptTextArtifact
  failure_memory_jsonl: PromptTextArtifact
  diagnostic_stdout: PromptTextArtifact
  diagnostic_stderr: PromptTextArtifact
  content_sha256

RenderedPromptArtifact:
  schema_version
  artifact_kind: RENDERED_PROMPT
  task_id
  variant_id
  variant_sha256
  task_prompt_sha256
  context_sources_sha256
  text
  content_sha256

PromptRender:
  status: VALID | INVALID_INPUT | INVALID_FAILURE_MEMORY
  text: string
  sha256: string
```

The C6b-memory extension adds `INVALID_FAILURE_MEMORY` without changing the valid rendered-text or
digest fields.

The learned fields are empty in the baseline variant. The checked-in baseline uses
`variant_id: baseline-v1` and `candidate_id: BASELINE`. A proposed candidate uses
`variant_id: <experiment_id>/variant` and `candidate_id: <experiment_id>/candidate`. A candidate
variant embeds the same base and repo artifacts byte-for-byte and changes only the learned append
and/or context policy. Accept and rollback embed the selected variant unchanged; they do not rename
it. Task prompt and context sources are task inputs, not activation state.

Context-source snapshots are bounded before decoding: patch-evaluation and each diagnostic text are
at most 65,536 bytes, and failure-memory JSONL is at most 1,048,576 bytes. A larger snapshot is
invalid input; the renderer never silently truncates the source artifact before applying the
declared per-section policy.

An activation embeds the complete effective `PromptVariant`, so its base/repo content is
reconstructable without resolving an old path. The evaluator resolves both the parent activation
and candidate experiment, renders their embedded variants, and passes evaluator-produced variant
and rendered-prompt artifacts to the task adapter. The task manifest supplies its content-bound
task prompt and context sources to the shared renderer.

### 4.2 Scope

Every experiment, evaluation, and activation embeds:

```text
PromptScope:
  schema_version
  artifact_kind: PROMPT_SCOPE
  repo_id
  repo_profile_revision
  align_revision
  corpus_id
  corpus_revision: CorpusRevision
  evaluation_provider_kind
  evaluation_provider_model
  generation_policy_sha256
  acceptance_policy_sha256
  base_prompt_sha256
  repo_prompt_sha256
  content_sha256
```

`CorpusRevision` is the exact source identity, not a free-form label:

```text
CorpusRevision:
  schema_version
  artifact_kind: CORPUS_REVISION
  source_kind: GIT_COMMIT | FILE_SET
  source_repository_id
  source_sha256
  content_sha256
```

For `GIT_COMMIT`, `source_repository_id` is a non-empty repository identity and
`source_sha256` is a lowercase full commit SHA whose clean checkout contains every corpus task.
For `FILE_SET`, `source_repository_id` is empty and `source_sha256` is the lowercase SHA-256 of
the canonical corpus file-set manifest, including the exact membership, relative path bytes, mode,
and file digest. The two forms are mutually exclusive and neither may use a shortened SHA, a branch,
a timestamp, or an ambient worktree. The record's own canonical `content_sha256` is not part of the
source preimage.

The `FILE_SET` manifest is a separate regular file and is not itself a member of the set. Its exact
canonical bytes are:

```text
ALIGN-LLM-CORPUS-FILE-SET-V1 LF
<entry_count in canonical unsigned decimal> LF
<six octal mode> SP <path byte count in canonical unsigned decimal> SP
<exact relative path bytes> NUL F SP <lowercase file SHA-256> LF
```

There is exactly one entry line for each of the declared `entry_count` entries and then end of file;
there are no extra bytes, blank lines, or alternate numeric spellings. `entry_count` is from 1
through 1,048,576, the complete manifest is at most 8,388,608 bytes, and each path is at most
4,096 bytes; all totals use checked arithmetic. Entries are sorted by the complete raw
relative-path byte sequence and are unique. A path is non-empty, uses `/` separators, has no NUL,
empty, `.` or `..` component, and names a regular file physically below the FILE_SET root; its
bytes may be non-UTF-8 but its length is measured before any text conversion. The mode is the
six-digit octal regular-file mode, the digest is over the exact file bytes, and the manifest digest
is SHA-256 over the complete bytes above. The manifest path itself is excluded even when it is
physically below the source bundle. A manifest entry whose path is the manifest itself is invalid;
when the manifest is physically below the source root, it remains metadata and is excluded from the
set. A validator rejects a path that escapes the source root,
duplicates an entry, names a symlink or special file, disagrees on mode or digest, or leaves any
entry unverified. A gate corpus must include every declared corpus task file in this manifest; a
file not listed is outside the FILE_SET identity and cannot be consumed by a gate task.

The verifier retains separate no-follow descriptors for the manifest and FILE_SET root. For every
raw path it duplicates the root owner, opens each intermediate byte component directory-relative
with directory/no-follow flags, opens the final component regular/no-follow, and obtains mode,
device/inode identity, byte count, and SHA-256 from that same final descriptor before closing it.
Manifest-self rejection compares final-file device/inode identity with the retained manifest
descriptor, so aliases do not evade exclusion. Any missing, replaced, symlinked, special,
mode-mismatching, digest-mismatching, or unreadable entry makes the corpus observation
`UNVERIFIED`. Once the request has supplied syntactically valid absolute root and manifest paths,
malformed manifest framing and an unsafe, unavailable, or wrong-type root/manifest likewise make
only that source observation `UNVERIFIED`.

`repo_profile_revision` names the immutable repository-rule/profile revision being optimized;
individual evaluation tasks bind their own source revisions. `corpus_revision` is the complete
tagged `CorpusRevision` record described above, never an ambient worktree or a free-form revision
label. The acceptance-policy digest prevents an
experiment from choosing easier thresholds than its parent activation. Acceptance and rollback
require an exact scope match.

### 4.3 Context policy

The C6b-memory renderer policy is:

```text
ContextPolicy:
  include_patch_evaluation: bool
  include_failure_memory: bool
  include_diagnostics: bool
  max_patch_evaluation_bytes: i64
  max_failure_events: i64
  max_failure_context_bytes: i64
  max_diagnostic_bytes_per_stream: i64
```

All limits are inclusive, non-negative byte or count limits. A disabled section requires its
corresponding limit to be zero. An enabled section requires a positive limit. Patch-evaluation,
failure-context, and per-diagnostic-stream limits cannot exceed 65,536 bytes, and
`max_failure_events` cannot exceed 64. Base, repo, task, and opportunity text inputs are each
bounded at 65,536 bytes.

Concretely, disabled patch evaluation requires `max_patch_evaluation_bytes == 0`; disabled failure
memory requires both failure limits to be zero; disabled diagnostics requires its stream limit to
be zero. The converse positive-limit rule applies to each enabled section.

The renderer validates these fields, a maximum 8,192-byte learned append, and the base/repo/task
and context-source limits before composing any text. The context source is an immutable snapshot
taken before the first A/B invocation and reused by both variants in the pair. Its digest is part of
the evaluation-input identity.

Context rendering is exact:

- Every section heading and the blank lines around it are always emitted as shown in section 3 and
  do not count against the section's content budget.
- A disabled section renders `(omitted)`. For diagnostics, `include_diagnostics: false` requires
  `max_diagnostic_bytes_per_stream: 0`; when enabled it requires a positive limit.
- Patch-evaluation text retains the longest UTF-8-safe prefix within
  `max_patch_evaluation_bytes`. If truncation occurs, the suffix
  `\n[context truncated]` is included inside that byte budget. A budget smaller than the suffix
  yields an empty body.
- Failure-memory matching uses the C5 key `task_id` only. Each non-empty JSONL line must decode as
  the shipped `MemoryEvent` schema with `schema_version: 1`; a malformed line or unknown schema
  version makes the context source invalid instead of being skipped. After validating the complete
  file, scan from the last line toward the first.
  Select a matching complete line only when it and its inter-line newline fit the remaining byte
  budget; otherwise skip it and continue. Stop when the event count is reached or the scan ends,
  then render selected lines in chronological file order. Non-matching lines are skipped. Newline
  separators count against the byte budget.
- Diagnostic stdout and stderr are bounded independently. Each retains the longest UTF-8-safe
  prefix and, when truncated, the existing `\n[output truncated]` marker inside the per-stream
  budget. The diagnostic body renders `stdout:\n<value>\nstderr:\n<value>`.

This intentionally replaces C5's fixed "most recent three" selection only when an activation is
supplied. Legacy verification tasks without an activation retain their current behavior until the
real-consumer slice changes that contract.

Policy flag/limit mismatches, policy limits above their declared caps, and oversized source
snapshots return `PromptRender` status `INVALID_INPUT` with empty text and digest before prompt
composition. The renderer validates the complete memory JSONL through
`failure_memory.select_context`; a malformed line or unknown schema version returns
`INVALID_FAILURE_MEMORY` with empty text and digest. The selector itself returns `valid: false` for
an invalid bound, while the renderer rejects that bound as an invalid policy before delegation.

`failure_memory.align` continues to own its private `MemoryEvent` schema and exposes:

```text
pub MemoryContext { valid: bool, text: string }

pub fn select_context(
  failure_memory_jsonl: str,
  task_id: str,
  max_events: i64,
  max_bytes: i64,
) -> MemoryContext
```

The bare Move result preserves the current Align ownership boundary. It validates every line and
implements the exact selection/order/budget policy above; invalid input returns `valid: false` and
empty text. `prompt_model.render` delegates selection to this API instead of copying the private
schema. It returns `INVALID_FAILURE_MEMORY` with empty text/digest when selection is invalid;
command-level validation maps that to `INVALID_INPUT` before external work.

### 4.4 Initial activation

C6d checks in a fixture-only human-owned `PromptActivationResult` envelope for deterministic
lifecycle tests. It is explicitly not the repository's canonical gate baseline and cannot satisfy
a real-provider acceptance. C6g1 first finalizes, reviews, and freezes the canonical corpus,
provider control, generation policy, acceptance policy, base prompt, and repo prompt. C6g2 then
checks in the repository's canonical human-owned baseline envelope before the first real
experiment; C6g2 must not mutate those scope assets after measuring against them.

Both fixture and canonical baseline envelopes have status `BASELINED`, nested operation
`BASELINE`, empty parent and accepted-evaluation fields, an empty learned append, and a reviewed
`ContextPolicy`. The canonical envelope uses `decision_id: baseline-v1` and
`activation_id: baseline-v1/activation`; its scope and prompt digests bind exactly the frozen
artifacts used by the first real experiment.

Every `parent_activation_path`, `current_activation_path`, `target_activation_path`, and ancestor
path resolves this same envelope type. Only a content-valid envelope with status `BASELINED`,
`ACCEPTED`, or `ROLLED_BACK`, empty `error`, and `activation: Some` is selectable. Its top-level
`ArtifactReference` uses kind `PROMPT_ACTIVATION_RESULT`, the envelope `decision_id`, and envelope
digest; lineage inside `PromptActivation` uses the nested activation ID and digest.

The four-command C6 surface does not add an implicit `init` mutation. A future repository can create
its first baseline activation from the documented declared record and verify it with the shared
model validator before any experiment. A general initialization command is deferred until a second
real consumer demonstrates that it reduces, rather than expands, the contract.

### 4.5 Evaluation-input identity

Labels alone never establish A/B comparability. Before running either variant,
`prompt evaluate` builds and persists:

```text
ArtifactDigest:
  path
  mode: str
  byte_count
  sha256

ArtifactExpectation:
  path
  kind: FILE | TREE
  expected_sha256

SnapshotRequest:
  schema_version
  artifact_kind: SNAPSHOT_REQUEST
  task_id
  project_root
  repo_path
  repo_revision
  require_clean_repo
  static_expectations: array<ArtifactExpectation>
  additional_files: array<str>
  workspace_path
  allowed_workspace_entries: array<str>
  content_sha256

WorkspacePreflightRequest:
  schema_version
  artifact_kind: WORKSPACE_PREFLIGHT_REQUEST
  evaluation_id
  project_root
  workspace_path
  content_sha256

WorkspacePreflightResult:
  schema_version
  artifact_kind: WORKSPACE_PREFLIGHT_RESULT
  evaluation_id
  status: SAFE | UNSAFE | ERROR
  error_code
  error
  physical_project_root
  physical_workspace_path
  environment_probe: Option<EnvironmentProbe>
  content_sha256

SnapshotResult:
  schema_version
  artifact_kind: SNAPSHOT_RESULT
  task_id
  status: MATCH | MISMATCH | ERROR
  error_code
  error
  environment_probe: Option<EnvironmentProbe>
  artifact_digests: array<ArtifactDigest>
  content_sha256

TaskInputSnapshot:
  schema_version
  artifact_kind: TASK_INPUT_SNAPSHOT
  task_id
  task_manifest_sha256
  artifact_digests: array<ArtifactDigest>
  environment_sha256
  content_sha256

RunSnapshotAttestation:
  schema_version
  artifact_kind: RUN_SNAPSHOT_ATTESTATION
  task_id
  sample_index
  variant: PARENT | CANDIDATE
  status: COMPLETE | PRECHECK_FAILED | PRECHECK_DRIFT | ADAPTER_FAILED | POSTCHECK_FAILED |
    POSTCHECK_DRIFT
  error_code
  error
  snapshot_request_sha256
  before_snapshot_result_sha256
  after_snapshot_result_sha256: Option<str>
  before_input_snapshot_sha256: Option<str>
  after_input_snapshot_sha256: Option<str>
  content_sha256

`RunSnapshotAttestation` has one deterministic state shape per attempted invocation:

| Status | Required fields | Error family |
| --- | --- | --- |
| `COMPLETE` | before and after snapshot results are `MATCH`; both input-snapshot references are `Some` and equal; a scored row exists | `NONE`, empty error |
| `PRECHECK_FAILED` | before snapshot result is `MISMATCH` or `ERROR`; all after and input-snapshot fields are `None`; no adapter call or row | `WORKSPACE_UNSAFE`, `SNAPSHOT_MISMATCH`, or `SNAPSHOT_ERROR` |
| `PRECHECK_DRIFT` | before snapshot result is `MATCH`; before input snapshot is `Some` but its environment or task-input identity differs from the established task baseline; all after fields are `None`; no adapter call or row | `INPUT_DRIFT` or `ENVIRONMENT_DRIFT` |
| `ADAPTER_FAILED` | before snapshot is `MATCH`, before input snapshot is `Some`; all after fields are `None`; no row | `ADAPTER_TIMEOUT`, `ADAPTER_PROCESS_OUTPUT`, or `ADAPTER_RESULT` |
| `POSTCHECK_FAILED` | before snapshot is `MATCH`, before input snapshot is `Some`, after snapshot is `Some` and `MISMATCH` or `ERROR`, after input snapshot is `None`; no row | `SNAPSHOT_MISMATCH` or `SNAPSHOT_ERROR` |
| `POSTCHECK_DRIFT` | before and after snapshot results are `MATCH`; both input-snapshot references are `Some`; the after environment or task-input identity differs from the established task baseline; no row | `INPUT_DRIFT` or `ENVIRONMENT_DRIFT` |

`COMPLETE` is the only row-producing attestation. A failed precheck or `PRECHECK_DRIFT` is terminal
before adapter launch; the evaluator does not run the adapter after a `MATCH` observation whose
environment or derived task-input snapshot differs from the established baseline. A failed adapter is
terminal immediately after a successful precheck, without an after snapshot. A failed postcheck or
`POSTCHECK_DRIFT` is terminal after the after observation and likewise produces no row; the drift
state retains the differing after snapshot and input snapshot so the verifier can distinguish it from
an ordinary snapshot failure.
`error_code` is `NONE` with empty `error` only for `COMPLETE`; every failed state has a non-empty
bounded English `error`. This explicit `ADAPTER_FAILED` state preserves timeout, output, and
malformed-result attempts in the persisted execution trace without inventing a `TaskMeasurement`.

GenerationPolicy:
  schema_version
  artifact_kind: GENERATION_POLICY
  generation_policy_id
  evaluation_provider_kind
  evaluation_provider_endpoint_id
  evaluation_provider_model
  provider_control_sha256
  provider_service_revision
  max_prompt_bytes
  max_tokens
  temperature_micros
  seed_mode: PAIRED_FIXED
  seed_base
  content_sha256

EvaluationProviderControl:
  schema_version
  artifact_kind: EVALUATION_PROVIDER_CONTROL
  provider_control_id
  provider_kind: CLOUD_OPENAI | LOCAL_OPENAI | LLAMA_CPP | FIXTURE
  endpoint
  endpoint_id
  model
  api_key_env: Option<str>
  tokenize_endpoint: Option<str>
  timeout_ns
  max_response_bytes
  content_sha256

EnvironmentPolicy:
  schema_version
  artifact_kind: ENVIRONMENT_POLICY
  policy_id
  allowed_variables: array<EnvironmentVariable>
  executable_paths: array<str>
  locale
  content_sha256

EnvironmentVariable:
  name
  non_secret_value
  source: EXPLICIT_POLICY
  precedence: i64

PromptSourceVerifierPolicy:
  schema_version: i64
  artifact_kind: PROMPT_SOURCE_VERIFIER_POLICY
  policy_id: string
  helper_path: string
  helper_sha256: string
  helper_runtime: string
  interpreter_sha256: string
  git_executable_sha256: string
  content_sha256: string

TaskAdapterRequest:
  schema_version
  artifact_kind: TASK_ADAPTER_REQUEST
  evaluation_id
  task_id
  sample_index
  variant: PARENT | CANDIDATE
  variant_path
  variant_sha256
  rendered_prompt_path
  rendered_prompt_sha256
  generation_policy_path
  generation_policy_sha256
  provider_control_path
  provider_control_sha256
  workspace_path
  result_path
  paired_seed
  credential_env_name: Option<str>
  environment_policy_sha256
  content_sha256

EnvironmentProbe:
  schema_version
  artifact_kind: ENVIRONMENT_PROBE
  producer: SNAPSHOT_HELPER | MEASUREMENT_ADAPTER
  os
  os_release
  architecture
  cpu
  logical_cpu_count: Option<i64>
  gpu
  runtime_identity
  content_sha256

EnvironmentIdentityCore:
  schema_version
  artifact_kind: ENVIRONMENT_IDENTITY_CORE
  os
  os_release
  architecture
  cpu
  logical_cpu_count: Option<i64>
  gpu
  align_llm_commit
  align_revision
  measurement_adapter_runtime
  snapshot_helper_runtime
  source_verifier_runtime
  source_verifier_policy_sha256
  environment_policy_sha256

EnvironmentIdentity:
  schema_version
  artifact_kind: ENVIRONMENT_IDENTITY
  core: EnvironmentIdentityCore
  environment_id
  content_sha256

EvaluationInputIdentity:
  schema_version
  artifact_kind: EVALUATION_INPUT
  task_id
  task_input_snapshot_sha256
  parent_variant_sha256
  candidate_variant_sha256
  task_prompt_sha256
  context_sources_sha256
  generation_policy_sha256
  generation_request_sha256
  adapter_request_sha256
  environment_policy_sha256
  environment_sha256
  sample_index
  paired_seed
  content_sha256

GenerationRequestIdentity:
  schema_version
  artifact_kind: GENERATION_REQUEST_IDENTITY
  rendered_prompt_sha256
  system_text_sha256
  user_text_sha256
  generation_policy_sha256
  provider_control_sha256
  environment_policy_sha256
  max_tokens
  temperature_micros
  paired_seed
  provider_request_sha256
  seed_attestation_sha256
  content_sha256

SeedCapabilityAttestation:
  schema_version
  artifact_kind: SEED_CAPABILITY_ATTESTATION
  provider_kind
  provider_model
  requested_seed
  result: APPLIED | UNSUPPORTED | REJECTED
  applied_seed: Option<i64>
  provider_request_sha256
  content_sha256
```

`EnvironmentVariable.name` is an ASCII environment name of at most 256 bytes and
`non_secret_value` is at most 4,096 UTF-8 bytes. `locale` is a non-empty label of at most 64
bytes. `precedence` is non-negative and at most 64;
the ordered list has no duplicate names. `runtime_identity` is a non-empty, non-secret label of
at most 256 bytes. `logical_cpu_count: Some(n)` requires `1 <= n <= 1,048,576`; `None` is the
only unavailable-count representation and makes a run non-gate-eligible, but does not by itself
make a non-gate diagnostic invalid.

`PromptSourceVerifierPolicy.helper_path` is a project-relative Python source path;
`helper_sha256`, `interpreter_sha256`, and `git_executable_sha256` are lowercase full digests of
the helper, the explicit `PromptEvaluateRequest.verifier_python_executable_path`, and the explicit
`PromptEvaluateRequest.verifier_git_executable_path`. `helper_runtime` is the canonical identity
`CPYTHON:<interpreter_sha256>:<helper_sha256>` and is copied into
`EnvironmentIdentityCore.source_verifier_runtime`; the policy's full digest is copied into
`EnvironmentIdentityCore.source_verifier_policy_sha256`. Thus the environment identity binds the
policy bytes, helper bytes, interpreter bytes, composite runtime identity, and Git-tool bytes rather
than relying on a nominal runtime label alone. The evaluator invokes exactly
`<verifier_python_executable_path> <helper_path> --source-verifier-request <request> --result <result>`;
it never uses a shebang, ambient `PATH`, `env`, or a nominal Python version. The policy digest is
checked before either executable path is opened, and the request's policy digest, Python executable
path, and Git executable path are not rewritten after validation.

This is an outright pre-release schema-version-1 change: an older version-1 policy without
`interpreter_sha256` is invalid, receives no compatibility default, and is never migrated or
rewritten. Declared-record order is exactly the order above. The codec owner adds semantic and byte
goldens for the new field, missing/duplicate/reordered-field rejection, and policy-digest changes
when any helper, interpreter, runtime, or Git identity changes.

On the Ubuntu 24.04 acceptance floor, validation opens every trusted executable or source carrier
with no-follow regular-file semantics and rejects its path, type, or digest before any helper side
effect. Invocation then reopens the same declared path with the same semantics, recomputes the
digest from that retained descriptor, and launches only from that descriptor. Python launches
through `/proc/self/fd/<interpreter-fd>` and receives
`/proc/self/fd/<helper-fd>` as its script argument with both descriptors explicitly inherited; Git
children likewise execute the retained Git descriptor rather than reopening the public pathname.
The immutable-input precondition forbids in-place mutation of an opened executable. The owner hashes
the same descriptor again after the child and rejects any byte or metadata change before accepting
its output. A pathname replacement between validation and invocation is accepted only when the
invocation descriptor independently matches the declared content digest; replacement after that
open cannot redirect it. Absence of the required Linux descriptor-exec facilities is `ENVIRONMENT` and cannot produce gate
eligibility; supplementary hosts may exercise non-gate paths but are not acceptance evidence.

`endpoint`, `tokenize_endpoint`, and `proposal_provider_endpoint` each have the 4,096-byte bound
from §1.2. They must use the provider's accepted scheme and host form, contain no userinfo, and
contain no credential query or fragment. `api_key_env` is only a validated name; the corresponding
value is never a field in any declared record.

`max_prompt_bytes` and `max_tokens` are from 1 through 1,048,576. The evaluated parent must fit the
prompt-byte limit or the fixed corpus/policy pair is `ERROR`. An oversized candidate is still
passed to the same adapter, which must return `POLICY_VIOLATION`; any other state is `ERROR`, and
the violation is a serious regression. `temperature_micros` is from zero through one million.
`seed_base` is read only from the evaluator-validated `GenerationPolicy`; it is not supplied by a
task adapter or selected independently for a row. Its value is covered by the generation-policy
content digest and must permit all requested one-based sample offsets without signed-`i64`
overflow. The evaluator recomputes every `paired_seed` as `seed_base + sample_index - 1`, copies
that result into `EvaluationInputIdentity` and `TaskAdapterRequest`, and rejects any returned or
persisted value that differs from that recomputation.
`logical_cpu_count: None` is the explicit unavailable value; a gate-eligible evaluation requires
`Some(n)` with a positive count. Provider endpoint and service-revision identities are non-secret,
non-empty labels; they are not inferred from a credential-bearing URL.

The provider control supplies the executable `model.ProviderConfig` inputs. Its kind, endpoint ID,
model, and digest must match `GenerationPolicy`; its timeout uses the common time bound.
`max_response_bytes` is from 1 through 1,048,576 and is enforced by the bounded transport required
by Align Request 5.
`api_key_env` is required for `CLOUD_OPENAI`, optional for `LOCAL_OPENAI`, and `None` for
`LLAMA_CPP` or `FIXTURE`; `tokenize_endpoint` is `Some` only when the selected adapter uses it.
`FIXTURE` is permitted only for non-gate deterministic evaluation and never dispatches a model
provider. Endpoint fields
must not contain URL userinfo or a credential query parameter. The evaluator resolves the named
credential once from its startup environment before any snapshot/helper/adapter call, passes the
same value explicitly to every measurement-adapter child that needs it, does not expose it to the
snapshot helper, and never persists the value or a reversible derivative.

The credential value must be non-empty. Before truncation, hashing, or persistence, provider
output, provider errors, adapter summaries, and adapter stdout/stderr diagnostics are sanitized by
one left-to-right pass that replaces every non-overlapping exact UTF-8 occurrence of the
credential in the original bytes with `[REDACTED]`. The unredacted bytes
exist only while the owning provider/process result is live. A trusted adapter must not emit an
encoded, transformed, or reversible derivative of the credential. The snapshot helper never
receives it. Deterministic fixtures cover credentials containing regex punctuation, overlapping
prefixes, and occurrences that cross the eventual truncation boundary.

Credential lifetime is a separate, non-persisted phase. After request validation, the command reads
the named startup environment entry exactly once into a temporary owner. For `experiment`, that
owner lives through proposal request construction and the provider call; for `evaluate`, it lives
through the adapter child launches only. The name is copied into `credential_env_name` in each
adapter request, but the value is passed only to the allowlisted measurement-adapter child under
that exact name. It is never placed in `EnvironmentPolicy.allowed_variables`, a snapshot request,
an `EnvironmentIdentity`, a result record, a digest preimage, or a diagnostic. The temporary owner
is dropped before result construction; redaction runs before any provider/adapter text is
truncated, hashed, or stored. Missing, empty, or duplicate credential names fail with
`MISSING_CREDENTIAL` before the first external call. A provider implementation may use the value
in-process or through the child environment, but it must receive the same explicit one-shot value
and may not reread ambient environment state.

The task manifest's `artifacts` array is mandatory and closed. It covers the adapter executable or
script, repository fixture tree, validation runner and command owner, task prompt/context
artifacts, and every other static file that can affect candidate generation or scoring. It does
not list the task manifest itself, which would create a circular digest. The evaluator
automatically adds the request's experiment, parent activation, corpus, acceptance policy,
generation policy, environment policy, workspace-preflight artifact, `.align-revision`, and the task manifest itself
to the snapshot.
The provider-control artifact is included alongside its generation policy.

For each task, the evaluator writes `SnapshotRequest.static_expectations` from the manifest and
puts those automatically added regular files in `additional_files`. It has already decoded and
content-validated every added artifact. It also copies the task's repository identity and clean
checkout requirement. The snapshot binds raw bytes and modes for pre/post equality, verifies the
named commit and clean worktree when required, and does not reinterpret added artifact schemas.
Duplicate or overlapping expanded paths are invalid.

Each expectation carries its reviewed digest. A `TREE` digest hashes the root and every descendant
directory and regular-file entry in one canonical bytewise path order. The root directory is always
the first record, so its mode and project-relative path are identity-bearing even when it is empty.
A directory contributes `octal-mode SP tree-relative-path NUL D LF`; a regular file contributes
`octal-mode SP tree-relative-path NUL F SP file-sha256 LF`. The root record uses the exact
expectation path without a trailing slash; descendant records use `/`-separated raw filename bytes
and are sorted by their complete relative path. Empty nested directories remain identity-bearing.
A root must be a real directory, but an empty root is valid because the root record itself is
present. A `FILE` expectation hashes
`octal-mode SP project-relative-path NUL F SP file-sha256 LF`. Modes are the zero-padded six octal
permission/type digits returned by the trusted snapshot helper, SHA values are lowercase
hexadecimal, and paths use `/` separators with their raw filename bytes unchanged. Expanded paths
are unique directories or regular files physically below the project root and are hashed
immediately before and after every adapter invocation. A missing, extra, changed, symlink, special
file, directory-topology, mode or digest mismatch, or dirty source commit makes the comparison
`ERROR`.

One task may expand at most 128 artifact files and 1,073,741,824 total bytes. Each byte count is
non-negative, the sum uses checked arithmetic, and exceeding either bound is `ERROR`. Static
expectations contain at most 64 entries and additional files at most 32.

The snapshot helper and measurement adapter both report an `EnvironmentProbe`; the evaluator
normalizes both carriers into one producer-owned `EnvironmentIdentity`, records its digest, and
requires the same normalized identity in both snapshots and every row in one evaluation. A `MATCH` or
`MISMATCH` snapshot requires a valid probe and a finalized identity; `ERROR` may omit both when
environment discovery itself failed. The provider endpoint identity is a non-secret stable service
label, not a credential-bearing URL. The service revision is required even when the provider exposes
only an operator-recorded API/model revision.

C6 gate evaluations require paired fixed randomness. For sample `n`, both variants receive the
same checked `seed_base + n - 1`; overflow is `ERROR`. Providers without seed support may exercise
non-gate lifecycle/evaluator paths, but their results are never gate-eligible or acceptable.

The real-consumer slice extends `model.GenerationRequest` with `seed: Option<i64>` and
`ModelInfo` with `supports_seed`. Existing callers use `None`; provider serializers retain their
legacy request record in that branch, while `Some` selects a declared seeded wire record. Thus
unseeded request bytes do not gain a JSON `null` field. Each adapter result also carries a
content-bound `SeedCapabilityAttestation`: the requested seed, the provider request digest, and
either `APPLIED`
with the same `applied_seed`, `UNSUPPORTED`, or `REJECTED`. The evaluator validates the attestation
digest and request identity before accepting the row. Every row in a gate-eligible evaluation must
be `APPLIED`; an unsupported or rejected seed may exercise a non-gate lifecycle path but makes the
evaluation ineligible. Earlier slices define and test the evaluation policy record without coding
against a hypothetical provider surface. `FIXTURE` records can exercise the seed/math contract but
are always non-gate.

For every evaluated generation, the provider-independent request mapping is normative:
`GenerationRequest.system` is the empty string and `GenerationRequest.user` is exactly
`RenderedPromptArtifact.text`; no adapter may prepend, append, or split other text. This makes the
OpenAI user-role content and llama.cpp concatenated prompt the same rendered bytes. Maximum tokens,
temperature, and seed come only from `GenerationPolicy`.

The evaluator, not the task adapter, writes task/sample/variant/input identities into the final row.
The measurement adapter returns only the measured payload plus its `EnvironmentProbe` and seed
attestation. A fixed snapshot helper returns only `SnapshotResult` with its probe carrier; the
evaluator validates and incorporates it. Both executables remain trusted,
content-bound task inputs, matching the current baseline trust model. Acceptance validates the
evaluation's complete persisted pre/post identities and embedded content digests. It does not
require historical task assets to remain at their old paths. The checked-in gate validator
separately rehashes the source-bundle corpus root through its exact `GIT_COMMIT` or canonical
`FILE_SET` manifest, and checks the tested align-llm head ancestry, so stale evidence cannot satisfy
`make ci`.

The evaluator also records the canonical `TaskAdapterRequest.content_sha256` in
`EvaluationInputIdentity.adapter_request_sha256`. This keeps the exact adapter request available to
the later independent evidence comparison without requiring C6c2 to read the request file.

## 5. CLI contracts

The commands use JSON request and result paths so the public boundary remains declared and
testable:

```text
./main prompt experiment <request.json> <result.json>
./main prompt evaluate   <request.json> <result.json>
./main prompt accept     <request.json> <result.json>
./main prompt rollback   <request.json> <result.json>
```

All commands:

- require exactly the documented argument count;
- reject unknown schema versions and empty required identifiers;
- validate all input artifact digests and cross-artifact identities before doing work;
- never persist API-key values;
- write one result artifact for a decoded request whenever the output path is new and writable;
- `prompt evaluate` writes the independently content-bound evidence artifact named by
  `evaluation_evidence_path` only after the evaluation has established its identity and reached the
  paired-evidence boundary; a pre-execution decoded-request `INVALID_INPUT` writes only the result
  and has no evidence sidecar;
- print the operation, terminal status, and output path in English;
- return success only for the successful terminal statuses listed below.

Malformed request JSON, an existing result output path, or an unreadable result output location
returns `Error.Invalid` or the underlying filesystem error without overwriting any file. For
`evaluate`, the request-declared evidence output path is validated after request decoding as a
request field. A missing, malformed, existing, or physically aliased evidence path is
`INVALID_INPUT` with `INVALID_PATH`; when the result output path passed its preflight, the command
writes result-only and never creates an evidence sidecar.

Opening or reading a referenced input is different from writing the result. A missing input,
non-regular input, permission failure, read failure, or invalid UTF-8 is a decoded-request
`INVALID_INPUT` with `INPUT_NOT_FOUND`, `INPUT_TYPE`, or `INPUT_READ`; the command writes that
result when the output path remains writable. Only an output persistence failure or a failure before
the request envelope decodes escapes as a filesystem `Result` error without a valid result artifact.
Pair cleanup failure is reported as `OUTPUT_PAIR_CLEANUP_FAILED` with the surviving evaluator-owned
path(s), and is never rewritten as a successful result. A destination created by a competing
publisher is not evaluator-owned, is never reported as a removable orphan, and is never removed by
the evaluator or by a retry instruction.

No command calls `fs.read_file` on an unbounded JSON input. A shared bounded reader uses a reusable
buffer and one probe byte, accumulating at most the applicable cap before `json.decode`. Earlier
owners obtain its reader with `fs.open`; C6d obtains it with `fs.open_beneath`:

| Input class | Maximum raw JSON bytes |
| --- | ---: |
| Operation request | 65,536 |
| Prompt/context, scope, policy, corpus, task, experiment, snapshot-request, or activation artifact | 2,097,152 |
| Snapshot result | 1,048,576 |
| Task measurement | 262,144 |
| Prompt evaluation result | 268,435,456 |
| Prompt evaluation evidence | 8,388,608 |

The lowest applicable cap wins for a nested operation. Exceeding it fails at validation step 1 for
the request itself or writes `INVALID_INPUT` at step 2 for a referenced artifact, before external
work. Unknown JSON fields remain non-identity-bearing but cannot bypass these raw-byte caps.

Validation and side-effect precedence is the same for every command:

1. Validate CLI arity and decode the declared request. Failure here produces no result artifact
   because there is no trusted result envelope.
2. Validate the CLI result output path for bounded syntax, nonexistence, physical safety, and
   writability before validating request fields. C6d performs this preflight by exclusively creating
   and retaining the absent result writer beneath its parent; earlier owners retain their documented
   single-writer precondition. A result-output-path failure returns `Error.Invalid` or the underlying
   filesystem error and produces no result artifact. Then validate request fields, including the decoded `evaluate` evidence output path, directly readable artifact
   schemas/digests, scope, bounds, and cross-record identities. A decoded invalid request writes
   `INVALID_INPUT` and performs no provider, measurement-adapter, or snapshot-helper call; for
   `evaluate`, it writes no evidence sidecar unless evaluation has established its identity and
   reached the paired-evidence boundary.
3. Perform the operation-specific external work: a proposal-provider call for `experiment`, or a
   pre-snapshot, paired measurement-adapter calls, and post-snapshot for `evaluate`. `accept` and
   `rollback` perform no external process or network work.
4. Validate every external result; for `evaluate`, require equal valid pre/post snapshots.
5. Construct and validate the complete result in memory.
6. Write the new output bytes once—through C6d's retained writer where applicable—or for `evaluate`
   finalize the two validated temporary files in the exact pair order above. A temporary/finalization failure returns `OUTPUT_WRITE` after cleanup;
   an unsuccessful cleanup returns `OUTPUT_PAIR_CLEANUP_FAILED` with only the evaluator-owned
   recovery path(s); collision destinations are never included or removed. A partial
   output is invalid and is never reported as a successful artifact.

Stable error labels identify the first failing check in this order. Later checks do not overwrite
an earlier diagnosis.

Result operation IDs are `Option<str>`: a valid decoded ID is `Some`; an empty or malformed ID that
causes `INVALID_INPUT` is `None`.

Every declared-record validator uses one universal order before applying the operation table:
raw-byte cap; JSON decode; `schema_version`; `artifact_kind`; scalar fields in declaration order;
nested records depth-first in declaration order; arrays in index order; local bounds and
field-specific labels; the record's canonical digest; then cross-record references and semantic
constraints. A nested prompt field must use its named kind (`BASE_PROMPT`, `REPO_PROMPT`,
`TASK_PROMPT`, or the exact `ContextSources` child kind); nested task IDs and artifact IDs must
match their enclosing record where the schema names the same identity. Duplicate declared JSON
keys, a mismatched child kind, or a mismatched child identity is invalid. The acceptance fixtures
enumerate every field-specific child-kind/identity rule rather than relying on a permissive
generic artifact validator.

Within step 2, operation-specific precedence is:

| Operation | Semantic validation order after result-output preflight |
| --- | --- |
| experiment | request bounds; parent activation envelope; scope and embedded prompt variant; opportunity artifact; proposal-provider kind/config; environment-key presence |
| evaluate | result output-path preflight; request bounds and decoded evidence output path, including physical distinctness; explicit verifier source paths and expected identities; experiment and parent; scope; corpus then task manifests in declared order; acceptance, generation, and provider-control policies; credential-name/value presence; empty workspace |
| accept | evaluation and evidence artifacts and all nested records; persisted pre/post identity equality; gate eligibility and `IMPROVED`; empty serious-regression array; supplied-parent validity; parent identity match |
| rollback | current activation; target activation; ancestor paths in supplied order; digest links; scope match; target ancestry; effective-variant difference; bounded reason |

For example, a tampered evaluation is `INVALID_INPUT` even when its supplied parent also differs,
and an invalid ancestor link is `INVALID_INPUT` before `SCOPE_MISMATCH` or `UNKNOWN_TARGET`.

Every result has an exact machine-readable `error_code`; `error` is bounded English detail and is
never parsed. Successful or complete scored statuses use `NONE` and empty detail. Allowed codes are:

| Result/status family | Allowed non-`NONE` codes |
| --- | --- |
| Any `INVALID_INPUT` | `INPUT_NOT_FOUND`, `INPUT_TYPE`, `INPUT_READ`, `INVALID_ID`, `INVALID_PATH`, `INVALID_SCHEMA`, `INVALID_KIND`, `INVALID_LABEL`, `INVALID_BOUNDS`, `INVALID_DIGEST`, `INVALID_REFERENCE`, `SCOPE_MISMATCH`, `MISSING_CREDENTIAL`, `WORKSPACE_NOT_EMPTY` |
| `INVALID_PROPOSAL` | `PROPOSAL_SCHEMA`, `PROPOSAL_BOUNDS`, `PROPOSAL_NO_CHANGE` |
| `PROVIDER_ERROR` | `PROVIDER_TIMEOUT`, `PROVIDER_TRANSPORT`, `PROVIDER_HTTP_STATUS`, `PROVIDER_RESPONSE_TOO_LARGE` |
| Evaluation `ERROR` | `WORKSPACE_UNSAFE`, `SNAPSHOT_MISMATCH`, `SNAPSHOT_ERROR`, `ADAPTER_TIMEOUT`, `ADAPTER_PROCESS_OUTPUT`, `ADAPTER_RESULT`, `INPUT_DRIFT`, `ENVIRONMENT_DRIFT`, `ARITHMETIC`, `RESULT_TOO_LARGE`, `CLEANUP_FAILED` |
| Output persistence failure before a valid result | `OUTPUT_WRITE`, `OUTPUT_PAIR_CLEANUP_FAILED` |
| Failed activation decision | the terminal status label itself: `INELIGIBLE`, `PARENT_MISMATCH`, `SCOPE_MISMATCH`, `UNKNOWN_TARGET`, or `NO_CHANGE` |

The snapshot helper uses its narrower table:

| Snapshot status | Cross-field contract |
| --- | --- |
| `MATCH` | code `NONE`, empty detail, a valid `environment_probe`, and the complete ordered digest array |
| `MISMATCH` | code `PATH`, `TYPE`, `MODE`, `CONTENT`, `TREE`, `REPO_REVISION`, or `DIRTY_REPO`; non-empty detail; a valid `environment_probe`; successfully observed prefix through the entry before the first failure |
| `ERROR` | code `ENVIRONMENT` or `INTERNAL`; non-empty detail; the probe is absent only for `ENVIRONMENT`; successfully observed prefix when available |

Snapshot checks run in this order: environment, repository path/revision/cleanliness, static
expectations in declared/expanded order, then additional files. The first failing check fixes the
status/code and prefix. Complete evaluation statuses can reference only `MATCH` results.

Workspace preflight checks run in this order: environment, physical project-root resolution,
workspace type, workspace symlink/ancestor exclusion, physical containment, then raw-byte
emptiness. `SAFE` uses `NONE` and empty detail; `UNSAFE` uses `TYPE`, `SYMLINK`, `ESCAPE`, or
`NOT_EMPTY`; `ERROR` uses `ENVIRONMENT` or `INTERNAL`. Only `SAFE`
has both physical paths and `environment_probe: Some`.

### 5.1 `prompt experiment`

Purpose: ask a configured provider for one learned prompt/context candidate.

`PromptExperimentRequest` contains:

```text
schema_version
artifact_kind: PROMPT_EXPERIMENT_REQUEST
experiment_id
project_root
parent_activation_path
opportunity_path
proposal_provider_kind
proposal_provider_endpoint
proposal_provider_endpoint_id
proposal_provider_model
api_key_env: Option<str>
tokenize_endpoint: Option<str>
timeout_ns
max_prompt_bytes
max_tokens
temperature_micros
```

`api_key_env` is `Some` with an environment-variable name for a credentialed provider and `None`
for a provider that requires no credential. It is the only persisted credential-related field.
The variable's value is resolved once for the provider call and never appears in the result or
diagnostics. `tokenize_endpoint` is `Some` only for a provider kind that requires it. `timeout_ns`
is from 1 through `7_200_000_000_000`; `max_prompt_bytes` is from 1 through 262,144,
`max_tokens` is from 1 through 8,192, and temperature uses the common millionth-unit integer range.
The constructed proposal prompt must fit `max_prompt_bytes` before any provider call.
`proposal_provider_kind` uses exactly `CLOUD_OPENAI`, `LOCAL_OPENAI`, or `LLAMA_CPP` and maps
explicitly to the current internal `ProviderKind`; no other label or case is accepted.
Proposal endpoints follow the same no-userinfo/no-credential-query rule as evaluation control.

The 262,144-byte response limit is enforced while receiving, before an owning response body can
grow past the cap. The pinned `std.http` client ships Align Request 5's `max_response_body_bytes`,
and `provider_http.post_json` already applies exactly this cap before any JSON/SSE decoding; the
transport surfaces an over-cap response as its deterministic receive-side limit error without
buffering past the bound. No C6 code may bypass that bounded transport boundary or substitute a
post-allocation length check for this contract.

The opportunity artifact is human- or system-authored evidence such as a repeated failure,
unnecessary context, or repair-loop pattern. It contains a stable opportunity ID, English summary,
and bounded supporting diagnostics. The proposal prompt includes the current hierarchy, context
policy, immutable constraints, opportunity, and the exact candidate response schema.

The provider must return:

```text
CandidateProposal:
  schema_version
  summary
  learned_prompt_append
  context_policy
```

The model does not choose IDs, scope, parent, acceptance thresholds, or evaluation tasks.
align-coder validates the proposal and computes `candidate_id` and `content_sha256`. The rendered
learned append and context policy must differ from the parent effective variant; changing only the
summary is `INVALID_PROPOSAL`.

For `INVALID_PROPOSAL` and `PROVIDER_ERROR`, `bounded_provider_output`, provider status text,
elapsed diagnostics, and the proposal summary are redacted with the exact credential replacement
pass before UTF-8 truncation, digesting, or result construction. A successful proposal retains no
provider response bytes. The unredacted response owner is dropped before the result is encoded;
the output cap and `PROVIDER_RESPONSE_TOO_LARGE` outcome are enforced by Request 5 while receiving.

The parent specification's lifecycle terms map as follows: a `PROPOSED` candidate is experimental
until evaluated, a complete `NO_IMPROVEMENT` or `SERIOUS_REGRESSION` evaluation is its rejection
record, and only an `ACCEPTED` activation makes it an explicitly selectable accepted variant.

`PromptExperimentResult` terminal statuses are:

- `PROPOSED`: valid candidate artifact; command succeeds.
- `INVALID_INPUT`: decoded request or referenced input is invalid; command fails without calling the
  provider.
- `INVALID_PROPOSAL`: provider returned output but it did not match the declared schema or bounds;
  command fails after recording bounded diagnostics.
- `PROVIDER_ERROR`: provider failed or timed out; command fails after recording the proposal
  provider kind, model, stable error label, status code when available, and elapsed time.

The complete result schema is:

```text
PromptExperimentResult:
  schema_version
  artifact_kind: PROMPT_EXPERIMENT_RESULT
  experiment_id: Option<str>
  status: PROPOSED | INVALID_INPUT | INVALID_PROPOSAL | PROVIDER_ERROR
  error_code
  error
  parent_activation: Option<ArtifactReference>
  scope: Option<PromptScope>
  opportunity: Option<ArtifactReference>
  proposal_provider_kind: Option<str>
  proposal_provider_endpoint_id: Option<str>
  proposal_provider_model: Option<str>
  proposal_elapsed_ns
  proposal_status_code: Option<i64>
  proposal_summary
  candidate_variant: Option<PromptVariant>
  bounded_provider_output
  content_sha256
```

`candidate_variant` is `Some` only for `PROPOSED`; otherwise it is `None`. The result contains both
the parent identity and complete candidate variant required for evaluation. Input and provider
options become `Some` only after each value validates in the documented precedence; this keeps
`INVALID_INPUT` representable without inventing identities. The proposal summary is bounded at
4 KiB and is non-empty only for `PROPOSED`; the learned prompt text is bounded at 8 KiB, and the
provider response before decoding at 262,144 bytes. The only temperature conversion is
`(temperature_micros as f64) / 1_000_000.0` through the current provider request's `f64` field,
and both proposal construction and persisted policy use that same integer source. C6a golden tests
cover zero, one, and one million. `proposal_status_code` is `Some` only when the
provider returned an HTTP status. `proposal_elapsed_ns` is non-negative and at most the global time
bound. `bounded_provider_output` is empty for `PROPOSED` and `INVALID_INPUT`, and contains at most
16 KiB of UTF-8-safe diagnostic response for `INVALID_PROPOSAL` or `PROVIDER_ERROR`.

### 5.2 `prompt evaluate`

Purpose: execute a symmetric A/B comparison on the fixed corpus and apply the acceptance policy.

`PromptEvaluateRequest` contains:

```text
schema_version
artifact_kind: PROMPT_EVALUATE_REQUEST
evaluation_id
project_root
experiment_path
parent_activation_path
corpus_path
sample_count
acceptance_policy_path
workspace_path
workspace_preflight_path
verifier_align_llm_repository_path
verifier_align_llm_commit
verifier_align_repository_path
verifier_align_revision
verifier_corpus_source_path
verifier_corpus_source_kind: GIT_COMMIT | FILE_SET
verifier_corpus_file_set_manifest_path: Option<str>
verifier_corpus_source_repository_id
verifier_corpus_source_sha256
verifier_source_policy_path
verifier_source_policy_sha256
verifier_python_executable_path
verifier_git_executable_path
evaluation_evidence_path
```

All fields use their declared-record types: `schema_version` and `sample_count` are `i64`,
`verifier_corpus_file_set_manifest_path` is `Option<string>`, and every other non-discriminator
field is `string`; field order is exactly the order above. Canonical JSON includes the conditional
manifest field with its string value for `Some` and omits it for `None`; a decoded explicit `null`
normalizes to the same `None` and is also accepted at the input boundary. The new
`verifier_python_executable_path` is required in schema version 1. Older version-1 requests without
it are invalid with no default, migration, or compatibility path. `PromptGateSourceLocator`
likewise gains one required `string` field in its declared order and rejects older version-1 bytes.

`evaluation_evidence_path` is the new output path for the independently produced
`PromptEvaluationEvidence` sidecar. It is a required decoded request field and must be a writable,
non-existing path under the same project root; its syntax, physical safety, nonexistence, and
distinctness from the result path are validated before any snapshot, adapter, or other evaluator
side effect. A missing, malformed, existing, or aliased evidence path is decoded-request
`INVALID_INPUT`/`INVALID_PATH`: when the result output path passed preflight, the evaluator writes
result-only and never creates the evidence sidecar. The evaluator
writes the result at the CLI output path and the evidence at this explicit path as one logical pair;
the evidence never points back to a path in the result. The pair has no cross-file atomicity promise,
but its temporary and failure behavior is exact. C6f2 may implement this contract only after the
shipped Request 14 operations pass `c6f2-request14-adoption`; no check-then-create or delete-before-
rename substitute is permitted. Python never creates a deterministic prepared result or evidence
path: its bounded process-stream carrier transfers the canonical records to
`src/prompt_evaluate.align`. After both canonical byte strings are complete and validated in
memory, the Align publisher exclusively creates one bounded temporary file beside each target,
writes and closes both temporary files, and rechecks that both final target paths are still absent. The
evaluator owns both temporary files. It then finalizes in fixed order with no-replace renames: the
result temporary file to the result path followed by the evidence temporary file to the evidence
path. A successful rename transfers ownership of that final output to the evaluator. A target created
between the recheck and its rename is a finalization collision; the no-replace operation fails and the
competing destination remains owned by its creator. No evaluator cleanup or retry may remove or
overwrite that destination.

A temporary-write or first-finalization failure removes only evaluator-owned temporary files and
returns `OUTPUT_WRITE` when those owned paths and their rechecks are clean. If the second finalization
fails, the evaluator removes the evaluator-owned finalized result (if present) and the remaining
evidence temporary file, then rechecks every evaluator-owned path. It never removes the evidence
destination when that destination is a collision, and it does not require a collision destination to
be absent. A collision with otherwise successful owned cleanup returns `OUTPUT_WRITE` and leaves no
evaluator-owned output artifact. If any removal or recheck of an evaluator-owned path fails, the
evaluator returns `OUTPUT_PAIR_CLEANUP_FAILED` with only the exact surviving evaluator-owned paths;
it never reports a successful result. The caller owns removal of explicitly reported evaluator-owned
orphans before retrying, but never removes a competing destination. The evidence path must also be
physically distinct from the CLI result path, including after resolving existing parent components
and symlink aliases; an alias is `INVALID_INPUT` before any evaluator work.

The `verifier_*` fields are explicit source-boundary inputs, not ambient configuration. They have no
defaults and are not inherited from `project_root`, the task manifest, the process environment, or
the evidence artifact. The first path names the align-llm checkout and the second names the
external Align checkout; the corpus path names the repository for `GIT_COMMIT` or the canonical
file-set root for `FILE_SET`. `verifier_corpus_file_set_manifest_path` is `Some` exactly for
`FILE_SET` and names its separate canonical manifest; it is `None` for `GIT_COMMIT`.
`verifier_align_revision` must equal the scope's `align_revision`, and the corpus kind, repository
ID, and source digest must equal the complete scope `CorpusRevision`;
`verifier_align_llm_commit` names the expected align-llm source commit to be checked and later equals
the result environment's `align_llm_commit` claim. `verifier_source_policy_path` is a
project-relative content-bound policy path and its digest must match
`verifier_source_policy_sha256`; the policy supplies the helper path/digest/runtime and Git-tool
digest plus the interpreter digest. `verifier_python_executable_path` and
`verifier_git_executable_path` are explicit absolute read-only inputs; the former launches the
helper, while the latter is opened by the evaluator and passed to the helper as an inherited
`/proc/self/fd` carrier rather than reopened by pathname. Neither public path is persisted in the
result or evidence. The
source-boundary root, manifest, policy, helper, interpreter, and Git-tool fields are physically checked before use and do not use the ordinary
project-relative input-path rule where the schema declares an external absolute path. The
source-boundary inputs are consumed in this deterministic order after result-output preflight:
request scalar bounds and evidence path; source-policy path syntax; bounded policy decode,
schema/kind/fields/digest, then equality with `verifier_source_policy_sha256`; helper path syntax;
Python path syntax; Git path syntax; canonical composite-runtime comparison; validation
regular-file open and digest comparison of helper, Python, then Git; remaining evaluation-artifact
decode and identity checks; workspace preflight; invocation regular-file reopen and digest
comparison of helper, Python, then Git; source-root and conditional-manifest syntax/type checks; source-kind/manifest/repository-label
agreement; full expected identity shape; then helper invocation and checkout/file-set observation.
Policy validation therefore precedes every executable open. The retained executable descriptors are
released only after post-child same-descriptor digest checks complete.
A missing, duplicated, reordered, or malformed required field is `INVALID_INPUT` before any
snapshot or adapter call.
Path syntax/type failures map to `INVALID_PATH`/`INPUT_TYPE`, a digest or composite-runtime mismatch
maps to `INVALID_DIGEST`; an absolute source-root or FILE_SET path that passes request syntax but
cannot be opened, has the wrong observed type, or disagrees with the manifest maps to that source's
`UNVERIFIED`. A descendant cleanup failure overrides timeout,
output-cap, child-status, or malformed-result diagnosis as paired evaluation
`ERROR`/`CLEANUP_FAILED`; the original process diagnosis remains bounded English detail only.

`src/prompt_evaluate.align` owns the source-boundary call and constructs `PromptVerifierTrust`; it
does not accept caller-supplied reachability booleans. After request and policy validation, it invokes
the content-bound source verifier described below with the three source roots, the conditional
FILE_SET manifest path, the Git tool identity, and expected identities. The helper returns one
observation for each named source; the evaluator persists both the resulting `VERIFIED`/`UNVERIFIED`
states and the observed identity options alongside the unchanged expected identities in the evidence
sidecar. The evaluator copies those
expected identities into `EnvironmentIdentityCore`; it never
uses an observed checkout revision as the core field:

1. invalid or physically unsafe paths, malformed identities, or an expected identity that disagrees
   with the scope are `INVALID_INPUT` before external evaluation work;
2. a valid source path whose clean exact commit/file-set cannot be proven, or whose helper cannot
   complete within its declared boundary, produces `UNVERIFIED` for that repository and continues as
   a valid non-gate comparison;
3. only a clean, exact, reachable source identity checked in its named repository produces
   `VERIFIED`. The resulting three statuses and unchanged expected identities are captured in
   evidence before the source-boundary owners are released; an unavailable or mismatching source
   never changes the expected identity claim to an observed value.

The source verifier is a separate trusted executable boundary owned by C6f1; it is not an implicit
Align `std.fs` operation or a call to ambient `git`:

```text
PromptSourceVerifierRequest:
  schema_version
  artifact_kind: PROMPT_SOURCE_VERIFIER_REQUEST
  mode: EVALUATION | GATE
  align_llm_repository_path
  expected_align_llm_commit
  tested_align_llm_head: Option<str>
  align_repository_path
  expected_align_revision
  corpus_source_path
  corpus_source_kind: GIT_COMMIT | FILE_SET
  corpus_file_set_manifest_path: Option<str>
  expected_corpus_source_repository_id
  expected_corpus_source_sha256
  git_executable_path
  git_executable_sha256
  content_sha256

PromptSourceVerifierResult:
  schema_version
  artifact_kind: PROMPT_SOURCE_VERIFIER_RESULT
  status: COMPLETE | UNAVAILABLE
  error_code
  error
  align_llm_reachability: PromptVerifierReachability
  align_llm_observed_head: Option<str>
  align_reachability: PromptVerifierReachability
  align_observed_revision: Option<str>
  corpus_reachability: PromptVerifierReachability
  corpus_observed_source_sha256: Option<str>
  content_sha256
```

The request mode fixes the shape of `tested_align_llm_head`: `EVALUATION` requires `None`, while
`GATE` requires one full lowercase commit SHA supplied by the gate validator from its own clean CI
`HEAD`. The helper rejects the opposite pairing before opening a source. The result is interpreted
with the request mode; it does not carry an ambient mode or a caller-selected tested head.

`PromptSourceVerifierResult.status: COMPLETE` means that the helper produced a valid bounded
result; it requires `error_code: NONE`, an empty `error`, and one explicit
`VERIFIED`/`UNVERIFIED` value for each of the three reachability fields. Every observed option
records the identity actually obtained from the named source. For `mode: EVALUATION`,
`align_llm_reachability: VERIFIED` requires `align_llm_observed_head: Some(expected_align_llm_commit)`.
For `mode: GATE`, the helper result requires `align_llm_observed_head: Some(tested_align_llm_head)`;
the gate validator separately proves, with the same complete-history repository, that
`expected_align_llm_commit` is an ancestor of that observed head. The result has no ancestry
boolean: the gate validator accepts `align_llm_reachability: VERIFIED` only after both the helper's
head observation and its own ancestry command succeed. Thus GATE deliberately permits the observed
CI head to differ from the evaluated commit; the head equality and ancestor relation are two parts
of the gate proof, not one identity equality.
For both modes, `align_reachability: VERIFIED` requires
`align_observed_revision: Some(expected_align_revision)`, and
`corpus_reachability: VERIFIED` requires
`corpus_observed_source_sha256: Some(expected_corpus_source_sha256)`. `UNVERIFIED` permits an absent
observation or an observed value that differs from the mode-specific expected identity, but the
observed option is still present whenever the helper opened the source and obtained a value. `status: UNAVAILABLE` is
the parent-side envelope for a timeout, child-output cap, child-process failure, malformed result,
or unavailable Git tool; it requires a non-`NONE` code from `HELPER_TIMEOUT`, `HELPER_OUTPUT_LIMIT`,
`HELPER_PROCESS`, `HELPER_RESULT`, or `GIT_UNAVAILABLE`, a bounded non-empty English `error`, all
three reachability fields `UNVERIFIED`, and all observed fields `None`. The evaluator may synthesize
this envelope only after validating the child boundary and never treats it as source proof; gate
validation rejects it before acceptance.

`mode: EVALUATION` requires `tested_align_llm_head: None` and proves that the align-llm checkout
`HEAD` exactly equals `expected_align_llm_commit`. `mode: GATE` requires `tested_align_llm_head:
Some(h)`, and requires the helper to prove that the source-bundle align-llm checkout `HEAD` exactly
equals `h`; the gate validator separately proves that `expected_align_llm_commit` is an ancestor of
`h` in that same complete-history repository.
Both modes require a clean exact Align checkout and the exact corpus `GIT_COMMIT` or canonical
`FILE_SET` manifest described in §4.2. The helper reports an observed identity only for a source it
actually opened; the evaluator uses the expected claims for `EnvironmentIdentityCore` and persists
both the observation and reachability label in `PromptVerifierTrust`. `PromptVerifierTrust` is an
EVALUATION-mode evidence record; the GATE-mode observed head is validated by the gate validator and
is not rewritten into the evaluation's expected identity claim.

`expected_corpus_source_repository_id` is non-empty for `GIT_COMMIT` and empty for `FILE_SET`,
matching the `CorpusRevision` discriminator. `corpus_file_set_manifest_path` is `Some` exactly for
`FILE_SET` and `None` for `GIT_COMMIT`; in either mode, the expected source digest is the exact
commit or manifest digest rather than a helper-reported replacement claim.

The evaluator validates the helper, interpreter, and Git executable digests in the order above
before any source read, creates one bounded request file, and invokes exactly
`<retained-python> <retained-helper> --source-verifier-request <request> --result <result>` with no
user-supplied extra arguments. The helper runs with `env_clear()` and
only the fixed non-secret locale/Git configuration entries `LANG=C`, `LC_ALL=C`,
`GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`,
`GIT_OPTIONAL_LOCKS=0`, `GIT_TERMINAL_PROMPT=0`, `GIT_PAGER=cat`, `GIT_NO_REPLACE_OBJECTS=1`, and
`GIT_GRAFT_FILE=/dev/null`; its working directory is the declared project root for `EVALUATION`
and the explicit source-bundle root for `GATE`. The request is capped at
65,536 bytes, the result and captured child streams at 262,144 bytes, and the timeout is exactly
60,000,000,000 ns; this fixed timeout is part of the helper contract and cannot be selected by a
request, policy, environment, or caller. The helper uses raw byte filesystem APIs for FILE_SET
traversal and streams the manifest under its 8,388,608-byte cap; it does not use Align `fs.read_dir`,
ambient `PATH`, or a credential-bearing environment. A timeout, over-limit output, malformed result,
unavailable Git tool, missing safe source, or inability to prove a source yields `UNAVAILABLE`/`UNVERIFIED` for the
unproven sources and no gate eligibility. An invalid helper/interpreter/tool path, digest, mode, or request is
`INVALID_INPUT` before this child launch.

Before invoking Git for any purpose, the helper performs a bounded raw repository-metadata walk from
the explicit `<repository>` path. `<repository>/.git` must be either a non-symlink directory or a
regular `gitdir: <path>` pointer file; the pointer and any optional `commondir` file are parsed as
bounded raw bytes without Git config or include expansion. The walk resolves the Git directory and
common directory physically, identifies the common `config` and any active per-worktree
`config.worktree`, and rejects missing, non-regular, unreadable, malformed, symlinked, or physically
escaping metadata. It then scans those local config files before starting any Git child. An
`extensions.worktreeConfig` repository also requires its active per-worktree config to pass the same
scan; a present but unusable worktree config is `UNVERIFIED` rather than ignored. This pre-Git walk
is the only way the helper locates local configuration; it does not ask Git to discover the config
itself.

The raw local-config scan is bounded, parses Git section/key syntax without following includes, and
rejects an `include.path` or `includeIf.*.path` directive. A local config with any setting that can
execute a process, load an external file, change the worktree/object/ref location used by one of the
fixed commands, invoke a hook/helper/filter/pager, or cause one of those commands to contact a remote
is rejected before source observation, including `alias.*`, `browser.*.cmd`, `browser.*.path`,
`core.alternateRefsCommand`, `core.askPass`, `core.attributesFile`, `core.editor`,
`core.excludesFile`, `core.fsmonitor`, `core.fsmonitorHookVersion`, `core.gitProxy`,
`core.hooksPath`, `core.pager`, `core.sshCommand`, `core.worktree`, `credential.helper`,
`diff.external`, `diff.<driver>.command`, `diff.<driver>.textconv`, `difftool.*.cmd`,
`difftool.*.path`, `filter.<driver>.clean`, `filter.<driver>.smudge`,
`filter.<driver>.process`, `gpg.*.program`, `gpg.program`, `guitool.*.cmd`, `http.*.proxy`,
`man.*.cmd`, `man.*.path`, `mergetool.*.cmd`, `mergetool.*.path`, `pager.*`,
`remote.<name>.promisor`, `remote.<name>.partialclonefilter`, `remote.<name>.proxy`,
`remote.<name>.receivepack`, `remote.<name>.uploadpack`,
`sequence.editor`, and `uploadpack.packObjectsHook`. More generally, every local key whose pinned
Git 2.45.0 documentation identifies an executable, command, process, hook, helper, external file,
filter, pager, proxy, transport, repository-location, promisor, or alternate-ref command is rejected,
including newly discovered keys in those effect families. Ordinary clone metadata that the fixed
local commands do not consume is explicitly allowed: `remote.<name>.url`,
`remote.<name>.pushurl`, `remote.<name>.fetch`, `branch.<name>.remote`, and
`branch.<name>.merge` are inert here because the helper never invokes a remote, fetch, push, merge,
checkout, or transport command. A remote URL is not an executable input at this boundary; a promisor,
proxy, upload/receive-pack, or other setting that can change object lookup or launch a transport
remains rejected. The acceptance fixture includes an ordinary-clone configuration with those allowed
remote keys and an execution sentinel for every rejected command-bearing family. A missing,
non-regular, unreadable, malformed, included, or rejected-key local config is `UNVERIFIED`; no
repository-local command may execute before that result.

Only after this raw walk and scan does the helper resolve the repository's absolute Git common
directory with `<git> --no-pager -C <repository> -c core.useReplaceRefs=false -c core.alternateRefsCommand= -c core.fsmonitor=false -c core.hooksPath=/dev/null -c credential.helper= -c diff.external= rev-parse --path-format=absolute --git-common-dir`
under the same cleared environment. The result must be one existing physical directory and must
equal the raw-walk common directory. The raw byte filesystem check then rejects any present
`refs/replace`, `info/grafts`, or `objects/info/alternates` entry in that common directory, including
a symlink, directory, or other non-regular entry. It then enumerates the complete replacement
namespace with the fixed command
`<git> --no-pager -C <repository> -c core.useReplaceRefs=false -c core.alternateRefsCommand= -c core.fsmonitor=false -c core.hooksPath=/dev/null -c credential.helper= -c diff.external= for-each-ref --format=%(refname)%00 refs/replace/`;
the bounded raw output must be either empty or exactly `<refname> NUL LF` per record; a nonzero
exit, output cap, malformed record, or non-empty record makes the repository `UNVERIFIED`. This
enumeration covers loose refs, `packed-refs`, and every ref backend supported by the pinned Git tool,
including reftable. The helper also performs the same replacement namespace check for the gate source
bundle. The explicit `GIT_NO_REPLACE_OBJECTS=1` and `GIT_GRAFT_FILE=/dev/null` settings remain in
force for every subsequent status, revision, object, ref-enumeration, and ancestry command. A
repository using any of these mechanisms is `UNVERIFIED`, never `VERIFIED`.

For `mode: EVALUATION`, the align-llm observation requires a clean checkout whose `HEAD` exactly
equals `verifier_align_llm_commit`; no ancestor commit or source-scope exception is permitted. For
`mode: GATE`, the source-bundle align-llm observation requires a clean complete-history checkout
whose `HEAD` exactly equals the validator-derived `tested_align_llm_head`; the gate validator's
separate ancestry command proves that `verifier_align_llm_commit` is an ancestor of that head. The
Align observation requires the clean checkout revision from `verifier_align_repository_path` to equal the
project `.align-revision` and `verifier_align_revision`; and the corpus observation checks the named
`GIT_COMMIT` or canonical `FILE_SET` manifest and its physically verified entries under
`verifier_corpus_source_path`. A source path or manifest that is readable but cannot prove the exact
clean identity is not an input error: its state is `UNVERIFIED`; a syntactically valid but absent or
unreadable root or manifest has the same state. The evaluator never falls
back to the task repository's `repo_path`, an ambient sibling checkout, or an environment variable.
These three verifier roots are read-only source inputs and may be outside `project_root`; they use
the same physical-resolution, symlink, special-file, and single-writer checks but are not required
to be project-root descendants, and the evaluator never writes beneath them.

`sample_count` must be from two through sixteen. The corpus manifest is:

```text
PromptEvaluationCorpus:
  schema_version
  artifact_kind: PROMPT_EVALUATION_CORPUS
  corpus_id
  corpus_revision: CorpusRevision
  task_files: array<str>
  content_sha256
```

It contains from one through 64 unique task IDs; at least two are required for a gate-eligible
evaluation. The supplied acceptance policy must match the digest bound into the experiment's parent
scope. The supplied parent activation must match the experiment's parent reference. Every task
must resolve the same generation policy and provider control. Their digests, provider kind,
endpoint identity, and model must match each other and the parent scope. The corpus ID and complete
`CorpusRevision` record must also match that scope. Every task's
`repo_id` must equal the scope repo ID; its named repository revision is independently checked by
the snapshot helper so different fixed fixture revisions cannot hide behind one corpus label.

Each `PromptEvaluationTask` declares:

```text
schema_version
artifact_kind: PROMPT_EVALUATION_TASK
task_id
repo_id
repo_revision
repo_path
require_clean_repo
cmd
argv: array<str>
snapshot_cmd
snapshot_argv: array<str>
measurement_adapter_runtime
snapshot_helper_runtime
cwd
timeout_ns
task_prompt_path
context_sources_path
generation_policy_path
provider_control_path
environment_policy_path
artifacts: array<ArtifactExpectation>
regression_limits: RegressionLimits
content_sha256
```

`RegressionLimits` is the declared nested record:

```text
maximum_unrelated_diff_count
maximum_patch_size_bytes
maximum_public_api_change_count
maximum_repair_loops
maximum_benchmark_regression_ppm: Option<i64>
```

Limits are task-specific, non-negative, and human-owned by the fixed corpus. `None` means that the
task has no benchmark claim; it does not turn an unknown benchmark result into a pass.
`maximum_repair_loops` cannot exceed 64, `maximum_patch_size_bytes` cannot exceed 67,108,864, and
the remaining count limits cannot exceed 1,048,576. Benchmark ppm is from zero through one million.
`repo_revision` is a lowercase full commit SHA and must be clean/reachable when
`require_clean_repo` is true. `timeout_ns` is from 1 through `7_200_000_000_000`. Each command
argument array contains at most 64 entries, and each entry is at most 4,096 UTF-8 bytes; the
complete marshalled vector, including NUL separators, is at most 262,144 bytes. `cmd` and
`snapshot_cmd` are non-empty UTF-8 without NUL and each `argv[0]` must equal its command. The
declared `measurement_adapter_runtime` and `snapshot_helper_runtime` labels are non-empty and at
most 256 bytes, and are content-bound by the corresponding executable in `artifacts`. These checks
occur in validation step 2 before either command runs.

The evaluator creates and content-validates one `TaskAdapterRequest` for each invocation. It invokes
the same `cmd`, `argv`, `cwd`, and timeout for both variants and appends only:

```text
--prompt-variant <variant-artifact-path>
--rendered-prompt <rendered-prompt-path>
--sample-index <one-based-index>
--paired-seed <seed>
--adapter-request <adapter-request-path>
--result <new-measurement-path>
```

The adapter request is the sole explicit carrier of generation policy, provider-control identity,
variant/rendered-prompt paths and digests, sample identity, paired seed, environment-policy digest,
workspace, and result ownership. The evaluator rejects a mismatch before process launch. The
adapter receives the policy and provider-control files through the declared paths, but receives a
credential only as the exact allowlisted child environment entry named by that policy.

Immediately before and after every parent or candidate adapter invocation, the evaluator invokes
the same fixed `snapshot_cmd`, `snapshot_argv`, and `cwd`, appending only:

```text
--snapshot-request <snapshot-request-path>
--result <new-snapshot-path>
```

`workspace_preflight_path` names a caller-created, content-bound `WorkspacePreflightRequest` whose
evaluation ID, project root, and workspace path exactly match this request. After all step-2
validation and before creating any path under `workspace_path`, the evaluator
invokes the first task's content-bound snapshot helper once in workspace-preflight mode:

```text
--workspace-preflight-request <request-path>
```

Every task must name the same snapshot helper command, argv, cwd, and artifact digest. The helper
writes nothing and returns exactly one bounded `WorkspacePreflightResult` on stdout with no
stderr. It resolves both roots physically, rejects a workspace that is not a real directory, is a
symlink, has a symlinked component below the physical project root, escapes that root, is not
empty under a raw-byte directory scan. The same no-race/single-writer precondition as output
artifacts requires the caller not to mutate the workspace concurrently. `SAFE` requires a probe
whose normalized fields match the later `EnvironmentIdentity`. `UNSAFE` becomes evaluation
`ERROR`/`WORKSPACE_UNSAFE` with no workspace mutation or adapter call; helper execution failure is
`SNAPSHOT_ERROR`. The helper is trusted and content-bound; its fixed response is at most 65,536
bytes, enforced by the cap-aware process surface required by Request 11. Until that request is
adopted, C6f1 cannot claim this bound.

The snapshot helper emits no stdout or stderr, writes exactly one bounded `SnapshotResult`, and
does not mutate any declared input. It performs the file-type, mode, closed-tree, path, and content
checks that the current Align `std.fs` metadata surface does not expose. It also raw-byte scans the
workspace and rejects any entry not in `allowed_workspace_entries`; listed entries are permitted
to be absent so the same request can cover the before/after result-file transition. Its script or
executable is a declared artifact expectation; its external runtime identity is bound by the task
manifest and the finalized `EnvironmentIdentity`. `MATCH` is required before and after;
the two ordered `artifact_digests` arrays must be byte-for-byte equal. Result order is manifest
expectation order with each tree expanded in bytewise path order, followed by
`additional_files` in request order. `MISMATCH`, `ERROR`, process output, nonzero exit, malformed
output, or input mutation makes the evaluation `ERROR`.

The first valid pre-run observation establishes the task baseline. Every later before/after
observation must equal it, so a mutation by an early invocation cannot be hidden by restoration
during a later invocation. The content-bound adapter is also required to give its generated
checkout write access only inside its owned workspace; declared source inputs remain read-only.

The evaluator embeds every unique `SnapshotRequest`, `SnapshotResult`, and normalized
`TaskInputSnapshot` once, keyed by content digest, and persists one `RunSnapshotAttestation` per
attempted adapter invocation in execution order. A complete attestation requires two `MATCH`
results, two input-snapshot references equal to the task baseline, the common environment, and
`status: COMPLETE`. A failed precheck has no after fields and no adapter call. A later `MATCH`
precheck whose environment probe or derived task-input snapshot differs from the established task
baseline uses `status: PRECHECK_DRIFT`, retains the differing before references, has no after fields
or row, and is terminal before adapter launch. A failed postcheck retains the before references and
observed after result when available but no scored row. An after `MATCH` whose environment probe or
derived task-input snapshot differs from the established baseline uses `status: POSTCHECK_DRIFT`,
retains both differing after references, and is terminal without a row. An adapter timeout,
process-output violation, missing result, or malformed result after a successful precheck uses
`status: ADAPTER_FAILED`, retains the before references, has no after fields or row, and is the
terminal attestation. Thus acceptance can recompute the pre/post equality claim and distinguish an
adapter failure, snapshot failure, and baseline drift without historical helper files.

Tasks run sequentially in corpus order. Within each task, samples run in ascending order; odd
samples run parent then candidate and even samples candidate then parent. No task or variant call
overlaps another.

The task adapter owns deterministic checkout setup, candidate generation, verification, cleanup,
and resource containment. `workspace_path` must be a caller-created empty directory dedicated to
this evaluation and must pass the physical preflight above. The evaluator chooses one new
measurement path per invocation under it, exclusively creates that file, records ownership
immediately, and passes the retained writable descriptor to the adapter. The adapter writes exactly
one `TaskMeasurement` through that descriptor, emits no stdout or stderr, and exits zero for a
complete measured pass or failure. A nonzero exit, process output, missing result, or extra
workspace entry beyond the evaluator's exact currently owned request/variant/rendered/result paths
makes the evaluation `ERROR`; adapter checkouts must therefore be removed before it returns.

The evaluator reads at most 262,144 bytes plus one probe byte from each measurement through its
retained path after the child exits; a larger result is `ERROR` without whole-file allocation.
Snapshot results use the same parent-created descriptor protocol outside the raw workspace. A
create collision establishes no ownership and is never removed. The evaluator removes owned
measurement, snapshot, variant, and rendered-prompt files after incorporating them, then requires
the workspace to be empty. Snapshot files use a 1,048,576-byte bound plus one probe byte. Cleanup
failure is `ERROR` with `CLEANUP_FAILED`. If the measurement and its complete before/after
attestation were already valid, evaluator-owned cleanup failure does not discard that non-`ERROR`
measurement row: the row is retained as the final valid prefix, no later invocation starts, and the
terminal cleanup event is represented by the result status/error rather than by a synthetic scorer
row. Cleanup failure before a valid measurement or attestation contributes no row.
The evaluator creates each `PromptVariant` file and `RenderedPromptArtifact` itself, passes only
their paths to the adapter, and verifies that the returned digest names those exact rendered bytes.
Those per-run files, the exact adapter request file, and every other evaluator-created adapter
input are included in `SnapshotRequest.additional_files`; the measurement path is included in
`allowed_workspace_entries`. Thus the same pre/post attestation detects mutation of the exact
variant and rendered prompt, while allowing the new result file to appear.
The fixed, content-hashed adapter is intentionally a silent trusted boundary. Its output cap,
kill/reap behavior, and environment isolation come from Request 11; C6 does not run model-produced
commands directly through this boundary and does not use the current uncapped `run()` surface.

A candidate is never installed while evaluation is running. Every retained row's validated
`environment_probe` must normalize with the surrounding snapshots to the same non-empty final
`environment_id`; an environment change during the comparison makes it `ERROR`.

The adapter emits only this measured payload:

```text
TaskMeasurement:
  schema_version
  artifact_kind: TASK_MEASUREMENT
  status: PASS | FAIL | POLICY_VIOLATION | ERROR
  failure_kind: NONE | PROVIDER | PATCH | BUILD | TEST | POLICY | CLEANUP | CONTAINMENT | ADAPTER
  build_status: PASS | FAIL | NOT_RUN | ERROR
  test_status: PASS | FAIL | NOT_RUN | ERROR
  repair_loop_count
  unrelated_diff_count
  patch_size_bytes
  public_api_change_count
  policy_violation_count
  cleanup_passed
  containment_passed
  benchmark_regression_ppm: Option<i64>
  generation_to_passing_patch_ns: Option<i64>
  rendered_prompt_sha256
  generation_request: GenerationRequestIdentity
  environment_probe: EnvironmentProbe
  seed_attestation: SeedCapabilityAttestation
  diagnostic_summary
  diagnostic_stdout
  diagnostic_stderr
  content_sha256
```

`environment_probe.producer` must be `MEASUREMENT_ADAPTER`, its declared runtime identity must
match the task manifest, and its fields must equal the probe from the surrounding snapshots.
`SeedCapabilityAttestation` is content-bound and its `provider_request_sha256` must identify the
exact serialized provider request bytes containing `paired_seed`. The provider boundary computes
that hash from the bytes immediately before dispatch, independently of the attestation, and the
evaluator requires it to equal `GenerationRequestIdentity.provider_request_sha256`; the two values
therefore cannot be circular. `APPLIED` requires
`applied_seed == requested_seed`;
`UNSUPPORTED` and `REJECTED` require `applied_seed: None` and make the evaluation ineligible.

`rendered_prompt_sha256` is the evaluator-produced `RenderedPromptArtifact.content_sha256`. The
request identity uses the raw SHA-256 of an empty string for `system_text_sha256`, the
`PromptRender.sha256` raw text digest for `user_text_sha256`, and the exact policy/control/seed
values. The evaluator independently renders the prompt, constructs this identity, and requires the
adapter's record to match before
wrapping the payload in:

```text
PromptTaskRow:
  schema_version
  artifact_kind: PROMPT_TASK_ROW
  evaluation_id
  task_id
  sample_index
  variant: PARENT | CANDIDATE
  variant_id
  variant_sha256
  prompt_preparation_ns
  time_to_passing_patch_ns: Option<i64>
  evaluation_input: EvaluationInputIdentity
  measurement: TaskMeasurement
  content_sha256
```

The timing boundary is identical for every variant. The evaluator starts
`prompt_preparation_ns` immediately before context selection and prompt rendering and stops it
after the rendered artifact and generation-request identity validate. The adapter starts
`generation_to_passing_patch_ns` immediately before the first provider generation call. It
includes all provider latency, patch decoding/application, build and test verification,
diagnostics used for repair, subsequent repair provider calls, and re-verification, and stops
immediately after the first full required validation command passes. Exclude evaluator snapshots,
initial checkout preparation, input decoding, result encoding, and post-run cleanup.

For a passing row, the evaluator uses checked addition to persist
`time_to_passing_patch_ns = prompt_preparation_ns + generation_to_passing_patch_ns`; every
aggregate and acceptance threshold uses that total. A run that never reaches a passing patch has
`None` in both the adapter generation-time field and row total. Prompt preparation remains a
non-negative measured value on every structurally valid row so candidate context work cannot
escape the primary metric.

The row state machine is exhaustive:

| Measurement status | Required state |
| --- | --- |
| `PASS` | failure `NONE`; build and test `PASS`; cleanup and containment true; zero policy violations; positive `Some` generation time and row total |
| `FAIL` | failure is provider, patch, build, or test; cleanup and containment true; zero policy violations; stage states follow the failure table below; both time fields are `None` |
| `POLICY_VIOLATION` | failure `POLICY`; cleanup and containment true; positive policy violations; both time fields are `None`; stages are one of the exact combinations below |
| `ERROR` | failure precedence and fields follow the exact rules below; both time fields are `None`; this row makes the whole evaluation `ERROR` |

For `FAIL`, `PROVIDER` and `PATCH` require both stages `NOT_RUN`; `BUILD` requires build `FAIL` and
test `NOT_RUN`; `TEST` requires build `PASS` and test `FAIL`. `POLICY_VIOLATION` permits only
`NOT_RUN/NOT_RUN`, `PASS/NOT_RUN`, or `PASS/PASS` for build/test.

For `ERROR`, failure precedence is deterministic: failed containment yields `CONTAINMENT`;
otherwise failed cleanup yields `CLEANUP`; otherwise an internal adapter failure or any stage
`ERROR` yields `ADAPTER`. A malformed or missing adapter document produces no row. If containment
and cleanup both fail, `CONTAINMENT` wins. Non-error states require both flags true, a valid
measurement-adapter probe, and a valid seed attestation. `PASS`, `FAIL`, and
`POLICY_VIOLATION` may be structurally complete with `UNSUPPORTED`/`REJECTED` seed results, but
those rows make the evaluation non-gate-eligible.

`task_completed` is not persisted; it is derived only from `status == PASS`. All count fields and
optional numeric values are non-negative; repair loops cannot exceed 64, patch bytes cannot exceed
67,108,864, and other counts cannot exceed 1,048,576. Passing time is strictly positive. A passing
task with a benchmark limit must return `Some`; all non-passing tasks and tasks without a limit
return `None`. Any
contradictory combination, prompt-digest mismatch, missing or duplicate row, adapter timeout,
malformed output, or task-order drift makes the evaluation `ERROR`; it is never silently scored.

The diagnostic summary is at most 4,096 UTF-8 bytes. Each diagnostic stream is at most 16,384
bytes and uses the existing UTF-8-safe truncation marker. These fields retain the measured failure
evidence without relying on adapter process output.

`gate_eligible` is true only when every requested pair is complete, the corpus and sample minima
hold, the verifier evidence names the exact clean source, external Align, and corpus identities,
marks all three reachability fields `VERIFIED`, and each observed identity equals its corresponding
expected identity; the final
`EnvironmentIdentity.core.logical_cpu_count` is `Some(positive)`, the provider kind is not
`FIXTURE`, and every row's `SeedCapabilityAttestation.result` is `APPLIED` with the requested seed.
A complete evaluation with `None` CPU availability, any `UNSUPPORTED`/`REJECTED` seed, a
`FIXTURE` provider, or any `UNVERIFIED` reachability remains a valid non-gate comparison; it cannot
be accepted as C6 evidence. The evaluator computes this flag from the decoded records and evidence,
and the pure verifier recomputes it rather than trusting a persisted caller-provided value.

The complete result is:

```text
PromptTraceOverflow:
  schema_version
  artifact_kind: PROMPT_TRACE_OVERFLOW
  attempted_invocation_count
  trace_record_count
  trace_digest_sha256
  content_sha256

PromptEvaluationResult:
  schema_version
  artifact_kind: PROMPT_EVALUATION_RESULT
  evaluation_id: Option<str>
  status: IMPROVED | NO_IMPROVEMENT | SERIOUS_REGRESSION | INVALID_INPUT | ERROR
  error_code
  error
  experiment: Option<ArtifactReference>
  experiment_artifact: Option<PromptExperimentResult>
  parent_activation: Option<ArtifactReference>
  parent_activation_artifact: Option<PromptActivationResult>
  scope: Option<PromptScope>
  parent_variant: Option<PromptVariant>
  candidate_variant: Option<PromptVariant>
  corpus_source: Option<ArtifactReference>
  corpus: Option<PromptEvaluationCorpus>
  tasks: array<PromptEvaluationTask>
  acceptance_policy_source: Option<ArtifactReference>
  acceptance_policy: Option<PromptAcceptancePolicy>
  generation_policy_source: Option<ArtifactReference>
  generation_policy: Option<GenerationPolicy>
  provider_control_source: Option<ArtifactReference>
  provider_control: Option<EvaluationProviderControl>
  workspace_preflight_source: Option<ArtifactReference>
  workspace_preflight_request: Option<WorkspacePreflightRequest>
  workspace_preflight: Option<WorkspacePreflightResult>
  environment: Option<EnvironmentIdentity>
  snapshot_requests: array<SnapshotRequest>
  snapshot_results: array<SnapshotResult>
  input_snapshots: array<TaskInputSnapshot>
  snapshot_attestations: array<RunSnapshotAttestation>
  trace_failure: Option<PromptTraceOverflow>
  sample_count
  gate_eligible
  rows: array<PromptTaskRow>
  task_aggregates: array<TaskAggregate>
  corpus_aggregate: Option<CorpusAggregate>
  serious_regression_reasons: array<RegressionReason>
  content_sha256
```

`PromptTraceOverflow` is a compact diagnostic envelope, not a replacement score. Its
`attempted_invocation_count` is from zero through 2,048 and its `trace_record_count` is from zero
through 16,384. A trace record is one top-level preflight request/result, first-retained snapshot
request/result, first-retained task-input snapshot, or invocation attestation in the would-be
result; the stream is ordered by preflight, then first appearance in each deduplicated snapshot
and input array, then invocation order for attestations. A repeated observation contributes only
when it creates a new retained record, while an attestation always contributes once for its
invocation. The maximum is derived from 2 preflight records, 4,096 snapshot requests, 4,096
snapshot results, 64 task-input snapshots, and 2,048 attestations. `trace_digest_sha256` is the
SHA-256 of the ordered byte preimage
`<one-based ordinal decimal> SP <artifact kind> SP <record content_sha256> LF` for every such trace record
observed before the result-size failure; the preimage is streamed and is not persisted. The
`RESULT_TOO_LARGE` result has `status: ERROR`, `error_code: RESULT_TOO_LARGE`, `trace_failure: Some`,
`gate_eligible: false`, an established `evaluation_id` and `scope`, and only the bounded error,
scope, sample-count, and compact-envelope fields retained. Every other optional record is `None`
and every array (`tasks`, `snapshot_requests`, `snapshot_results`, `input_snapshots`,
`snapshot_attestations`, `rows`, `task_aggregates`, `serious_regression_reasons`) is empty. The
result environment is `None`. The evaluator drops the full trace before
constructing this shape; it retains no claim that the discarded trace can be independently replayed.
The declared bounds make this shape at most 1,048,576 raw canonical bytes, and the writer still
checks the Request 12 cap before writing it. C6c2 validates the status, empty-array/option shape,
counter bounds, digest shape, and evidence/result identity, then returns `NONCOMPLETE_ERROR` without
invoking C6c1 or treating the compact digest as a score.

The verifier sidecar is a separate persisted artifact:

```text
PromptVerifierReachability: VERIFIED | UNVERIFIED

PromptVerifierTrust:
  schema_version
  artifact_kind: PROMPT_VERIFIER_TRUST
  expected_align_llm_commit
  expected_align_revision
  expected_corpus_source_kind: GIT_COMMIT | FILE_SET
  expected_corpus_source_repository_id
  expected_corpus_source_sha256
  align_llm_reachability: PromptVerifierReachability
  align_llm_observed_head: Option<str>
  align_reachability: PromptVerifierReachability
  align_observed_revision: Option<str>
  corpus_reachability: PromptVerifierReachability
  corpus_observed_source_sha256: Option<str>
  content_sha256

PromptExpectedInputDigest:
  schema_version
  artifact_kind: PROMPT_EXPECTED_INPUT_DIGEST
  task_id
  sample_index
  variant: PARENT | CANDIDATE
  rendered_prompt_sha256
  context_sources_sha256
  generation_request_sha256
  adapter_request_sha256
  provider_request_sha256
  content_sha256

PromptEvaluationEvidence:
  schema_version
  artifact_kind: PROMPT_EVALUATION_EVIDENCE
  evaluation_id
  evaluation_result_sha256
  trust: PromptVerifierTrust
  expected_inputs: array<PromptExpectedInputDigest>
  content_sha256
```

Evidence is content-bound and has at most 2,048 expected-input entries. Its raw JSON cap is
8,388,608 bytes. `evaluation_result_sha256` equals the result record's `content_sha256`; the result
does not contain an evidence path or digest, so the two artifacts do not form a reference cycle.
The explicit `PromptAcceptRequest.evaluation_evidence_path` owns the pair for acceptance, and the
`PromptGateManifest.improved_evaluation_evidence` reference owns the pair for the checked-in gate;
neither owner is inferred from the result path.
The evaluator captures the expected-input table independently from the exact evaluator/producer
inputs before those owners are released, then binds the finished result's content digest when it
forms the sidecar. It must not reconstruct an entry by reading a completed result row. Entries are
in retained execution-row order, exactly one per retained `PromptTaskRow`, with no duplicate, missing,
or extra task/sample/variant identity.

For `RESULT_TOO_LARGE`, `expected_inputs` is empty because the full execution trace and all rows
are intentionally discarded; the sidecar still carries the established evaluation ID, result
digest, scope-bound expected identities, and the source reachability states observed before the
overflow. No compact trace digest is treated as an expected-input row or as score evidence.

The expected-input columns bind the independently observed values as follows: rendered prompt to
`TaskMeasurement.rendered_prompt_sha256`, context sources and generation request to the corresponding
`EvaluationInputIdentity` fields, adapter request to `EvaluationInputIdentity.adapter_request_sha256`,
and provider request to `GenerationRequestIdentity.provider_request_sha256`. The C6a1/C6a2 codec
validates both artifact content digests before C6c2 is called; C6c2 compares these decoded fields and
does not read JSON, re-encode records, or recompute canonical SHA-256 bytes.

`PromptVerifierTrust` carries expected and observed identities, not ambient labels, and is produced
only from the evaluator's `mode: EVALUATION` source observation. Its three
reachability and three observed-identity fields are supplied only by the explicit source boundary
described in `PromptEvaluateRequest`, after that boundary checks the exact clean commit or file-set
in each named repository. The evaluator copies the three expected source identities into the result
environment claim; reachability is the separate proof state and never substitutes an observed
checkout value. The pure verifier requires
`expected_align_llm_commit` to equal `EnvironmentIdentity.core.align_llm_commit` whenever the result
carries an environment (mandatory for every complete status), the expected Align revision to equal
both the evaluation scope and that environment, and the expected corpus fields to equal the complete
`CorpusRevision`. A noncomplete result without an environment cannot prove the align-llm or Align
equality; it preserves the source states already observed by the source boundary, while each source
observation that was unavailable remains `UNVERIFIED`, and it can return only the non-gate
`NONCOMPLETE_ERROR` verdict. All three reachability fields must be present; their value must be
`VERIFIED` before returning a gate-eligible verdict, and each `VERIFIED` field must have a `Some`
observed identity equal to its expected identity. `UNVERIFIED` is a valid reason for a complete
non-gate comparison, including an unavailable or mismatching verifier checkout; it may retain a
different observed identity for diagnostics. A malformed, scope-disagreeing, or
`VERIFIED`-without-equality identity is invalid. These content digests detect corruption, not author
authentication.

An `INVALID_INPUT` result emitted before evaluator inputs are established has no evidence sidecar and
cannot be supplied to `prompt accept`. Once evaluation has established an evaluation identity, an
`ERROR` result may have a paired evidence artifact for its retained prefix; unavailable environment
or source observations are represented by `UNVERIFIED`, while source observations completed before
the failure remain `VERIFIED`. The decoded verifier returns
`NONCOMPLETE_ERROR` without treating the prefix as a score. Only complete comparison statuses need a
full expected-input table and all three reachability and observed-identity fields; the fields may be
`VERIFIED` or `UNVERIFIED`, but only the all-`VERIFIED` combination with three exact observed
identities can satisfy the gate.

Terminal statuses are:

- `IMPROVED`: policy says strictly improved and the serious-regression array is empty; command
  succeeds.
- `NO_IMPROVEMENT`: comparison completed but no strict improvement exists; command succeeds.
- `SERIOUS_REGRESSION`: comparison completed and at least one serious regression exists; command
  succeeds so the negative result remains measurable.
- `INVALID_INPUT`: decoded request or referenced artifact is invalid before adapter execution;
  command fails.
- `ERROR`: comparison is incomplete or incomparable; command fails.

Completing an evaluation is not acceptance.

For `INVALID_INPUT`, references become `Some` only through the last successfully validated input
in the precedence table, rows and aggregates are empty, `corpus_aggregate` is `None`,
`snapshot_attestations` is empty, and `gate_eligible` is false. A pre-execution invalid result has
no evidence sidecar and is not supplied to `verify_result`; a paired invalid result is allowed only
after an evaluation identity and its evidence have been established. For `ERROR`, all input
references are `Some`; valid rows are retained by the exact rule below and `corpus_aggregate` is
`None`; `task_aggregates` and `serious_regression_reasons` are empty; and `environment` is `Some`
only if one valid measurement established it before the failure. `RESULT_TOO_LARGE` is the explicit
compact-shape exception: `evaluation_id`, `scope`, the error, sample count, and `trace_failure` are
the only retained evaluation fields besides the fixed status, error code, gate flag, and content
digest; every other optional record is `None`, and every array is empty. Its evidence sidecar has no
expected-input entries.
Retention is the longest execution-order prefix whose measurement and before/after attestation both
validate; a valid `ERROR` measurement with an unchanged complete attestation is the final retained
row, while a failed pre/post check, `PRECHECK_DRIFT`, `ADAPTER_FAILED`, or `POSTCHECK_DRIFT`
contributes no row and is represented only by its terminal attestation. A cleanup failure after a
valid non-`ERROR` measurement and complete attestation also retains that row and is represented by
the terminal `CLEANUP_FAILED` result error. The prefix validator returns `TERMINAL_ERROR` when that
final retained row has status `ERROR`, and `VALID_PREFIX` when the terminal failure contributes no
row or is this post-row cleanup failure.
No invocation or attestation occurs after the first error. `RESULT_TOO_LARGE` emits the compact
envelope and retains no scoreable prefix or trace array. All complete
comparison statuses require every
reference and its matching `experiment_artifact`/`parent_activation_artifact`, embedded scope,
variant, corpus, policy, successful workspace preflight, and environment, the complete declared task
array, the complete deduplicated snapshot records, one complete attestation per row, and the
aggregate to be present. Each row's
`task_input_snapshot_sha256` must resolve exactly one matching snapshot. The embedded records make
aggregation and acceptance reconstructable from the evaluation artifact. Their digests must match the
source references that were validated during evaluation, but acceptance need not reload historical
task assets. The paired `PromptEvaluationEvidence` must be content-valid, have the same evaluation ID
and result digest, and contain the complete independent input table before acceptance can proceed.
The gate validator does reload and rehash the source paths when proving that checked-in evidence still
matches the canonical corpus.

The canonical evaluation result is bounded at 268,435,456 bytes by Request 12's bounded canonical
encoder. The task, sample, artifact, path, and diagnostic limits are additional semantic limits,
not a substitute for the encoder bound. An attempted result larger than it is `ERROR` with
`RESULT_TOO_LARGE` and the bounded compact envelope above; the evaluator drops the full trace and
emits no oversized scored artifact.

### 5.3 `prompt accept`

Purpose: create a new effective activation from one eligible evaluation.

`PromptAcceptRequest` contains:

```text
schema_version
artifact_kind: PROMPT_ACCEPT_REQUEST
decision_id
project_root
evaluation_path
parent_activation_path
evaluation_evidence_path
```

`evaluation_evidence_path` is required and is an explicit input to acceptance; a result-only path is
never sufficient.

The CLI first validates and opens the request as a regular file beneath its lexical parent, with a
65,536-byte cap. A malformed, oversized, missing, symlinked, or special request returns a command
`Result` error and creates no result. After decode it validates the result path and exclusively
creates the result beneath its retained parent before validating request fields. Unsafe request
fields therefore produce a canonical `INVALID_INPUT` result when the result path is safe and absent;
an unsafe, missing, denied, or occupied result parent/final produces no result and no artifact read.
Referenced paths are relative to the absolute `project_root` and are opened beneath it in evaluation,
evidence, then parent order. Missing input maps to `INPUT_NOT_FOUND`, no-follow/type rejection to
`INPUT_TYPE`, and permission or other read failure to `INPUT_READ`; lexical request-field rejection
maps to `INVALID_BOUNDS` before any referenced input is opened.

Acceptance validates:

- evaluation status is `IMPROVED`;
- the serious-regression array is empty;
- the evaluation is gate-eligible;
- the evidence artifact is content-valid, has the same evaluation ID and result digest, and passes
  the independent expected-input and three-repository reachability checks;
- candidate, parent, scope, policy, corpus, and evaluation provider/model identities match;
- the supplied parent activation is exactly the evaluated parent;
- the same decoded-result verifier accepts the evaluation and evidence before activation
  construction; all persisted pre/post artifact identities, embedded content digests, and task rows
  verify.

The immutable activation and shared decision envelope are:

```text
PromptActivation:
  schema_version
  artifact_kind: PROMPT_ACTIVATION
  activation_id
  operation: BASELINE | ACCEPT | ROLLBACK
  scope: PromptScope
  parent_activation_id
  parent_activation_sha256
  effective_variant: PromptVariant
  accepted_evaluation_id
  accepted_evaluation_sha256
  rollback_target_activation_id
  rollback_target_activation_sha256
  decision_reason
  content_sha256

PromptActivationResult:
  schema_version
  artifact_kind: PROMPT_ACTIVATION_RESULT
  decision_id: Option<str>
  status: BASELINED | ACCEPTED | INELIGIBLE | PARENT_MISMATCH | ROLLED_BACK |
    SCOPE_MISMATCH | UNKNOWN_TARGET | NO_CHANGE | INVALID_INPUT
  error_code
  error
  activation: Option<PromptActivation>
  content_sha256
```

On successful acceptance, `status` is `ACCEPTED`, `operation` is `ACCEPT`, rollback fields and
`decision_reason` are empty, and `activation` is `Some`. On a failed decision, it is `None` and
`error` contains a stable bounded English label. Terminal statuses are:

- `ACCEPTED`: new activation written; command succeeds.
- `INELIGIBLE`: evaluation completed but cannot be accepted; command fails.
- `PARENT_MISMATCH`: supplied parent is not the evaluated parent; command fails.
- `INVALID_INPUT`: an artifact, identity, or decoded request is invalid; command fails.

`BASELINED` is valid only for the reviewed human-authored initial envelope and is not emitted by
`prompt accept` or `prompt rollback`. The command-specific result validators reject statuses that
belong to the other operation.

The command does not modify the parent activation or a global pointer. The immutable history is a
branching DAG: multiple accepted children of one parent are valid. `PARENT_MISMATCH` proves only
that this decision does not match its evaluated parent; it does not claim knowledge of a global
"latest" activation.

The activation cross-field invariants are exact:

| Operation | Parent fields | Accepted-evaluation fields | Rollback-target fields | Reason | Effective variant |
| --- | --- | --- | --- | --- | --- |
| `BASELINE` | empty | empty | empty | empty | reviewed baseline |
| `ACCEPT` | evaluated parent | accepted evaluation | empty | empty | evaluated candidate |
| `ROLLBACK` | current activation | copied from target, or empty when the target is baseline | target activation | required | target's effective variant |

“Empty” means the two corresponding ID/digest strings are both empty. “Copied from target” means
the rollback activation retains the evaluation provenance that originally accepted the target
variant; rolling back to a prior rollback copies that target's retained provenance. Validators
reject every other combination.

### 5.4 `prompt rollback`

Purpose: create a new activation whose effective variant equals a prior accepted activation.

`PromptRollbackRequest` contains:

```text
schema_version
artifact_kind: PROMPT_ROLLBACK_REQUEST
decision_id
project_root
current_activation_path
target_activation_path
ancestor_activation_paths
reason
```

The ancestor array contains at most 256 paths.

The validator loads the current activation, then the target, then each
`ancestor_activation_paths` entry in order. The first loaded ancestor must be the current parent, each subsequent artifact must
be the preceding parent, and the last link must name the target; a direct-parent target therefore
uses an empty ancestor array. Current, intermediate, and target IDs and digests must be unique, and
every link and scope must validate. The target may have operation `BASELINE`, `ACCEPT`, or
`ROLLBACK`. The reason is required and bounded. The target cannot equal the current activation and
must select a different effective candidate/context variant.
All request/result preflight and retained-root rules from `prompt accept` apply. Referenced activation
reads occur in current, target, then declared ancestor order. A missing, unsafe-type, denied, or other
read failure uses the same `INPUT_NOT_FOUND`/`INPUT_TYPE`/`INPUT_READ` mapping.

The successful `PromptActivationResult` has:

```text
operation: ROLLBACK
parent_activation_id: <current>
parent_activation_sha256: <current digest>
effective_variant: <target effective variant>
rollback_target_activation_id: <target>
rollback_target_activation_sha256: <target digest>
decision_reason: <bounded rollback reason>
accepted_evaluation_id: <target accepted evaluation, or empty for baseline>
accepted_evaluation_sha256: <target accepted evaluation digest, or empty for baseline>
```

It keeps the current scope and creates a new content identity. It does not delete the rejected or
rolled-back activation, and later evaluation may still compare against any explicitly selected
valid activation.

On failure, `activation` is `None` under the same rules as `prompt accept`.

Terminal statuses are:

- `ROLLED_BACK`: new rollback activation written; command succeeds.
- `SCOPE_MISMATCH`: target scope differs; command fails.
- `UNKNOWN_TARGET`: chain does not prove the target is an ancestor; command fails.
- `NO_CHANGE`: target selects the same effective variant; command fails.
- `INVALID_INPUT`: an artifact, chain, reason, or decoded request is invalid; command fails.

## 6. Persistence, ownership, and failure behavior

`src/prompt_model.align` owns the C6b-memory renderer policy, digest validation, bounds, prompt
rendering, source validation, UTF-8-safe context truncation, and integration of the invalid-memory
status. `src/failure_memory.align` remains the C5 owner of its existing failure-memory behavior and
also owns the Request 7-dependent JSONL decoding and bounded event selection through the public
Move-result API in section 4.3.

`src/prompt_experiment.align` owns proposal prompt construction, provider dispatch, response
decoding, and bounded provider diagnostics. It never owns acceptance.

`src/prompt_score.align` owns pure row validation, aggregation, policy application, and the decoded
evaluation-result verifier. It does not decode JSON, inspect paths, recompute canonical bytes, or
walk source repositories. `src/prompt_model.align` and the C6a1/C6a2 codec owners own canonical
document decoding and content-digest validation. `src/prompt_evaluate.align` owns snapshots, adapter
execution, A/B ordering, independent evidence construction, and construction of inputs for the
shared scorer. Task adapters own task-specific sandboxing and cleanup.

`src/prompt_state.align` owns accept/rollback validation and activation construction. It has no
provider or task-runner dependency.

`src/main.align` owns argument dispatch, stable English CLI summaries, and mapping unsuccessful
terminal states to `Error`.

The planned Align public surface respects the implemented Move limitation:

```text
prompt_model.render(
  base_prompt: str,
  repo_prompt: str,
  task_prompt: str,
  learned_prompt_append: str,
  task_id: str,
  failure_memory_jsonl: str,
  policy: ContextPolicy,
  patch_evaluation: str,
  diagnostic_stdout: str,
  diagnostic_stderr: str,
) -> PromptRender

prompt_experiment.experiment_file(request_path: str, result_path: str)
  -> PromptExperimentStatus
prompt_score.verify_result(
  borrow result: PromptEvaluationResult,
  borrow evidence: PromptEvaluationEvidence,
)
  -> Result<PromptScoreStatus, Error>
prompt_evaluate.evaluate_file(request_path: str, result_relative: str)
  -> PromptEvaluateStatus
prompt_state.accept_file(request_path: str, result_path: str)
  -> Result<PromptCommandStatus, Error>
prompt_state.rollback_file(request_path: str, result_path: str)
  -> Result<PromptCommandStatus, Error>
```

`ContextPolicy`, `PromptRenderStatus`, `PromptScoreStatus`, `PromptCommandStatus`, and
`PromptExperimentStatus` are Copy data. The shipped evaluate command follows this pattern as
`prompt_evaluate.evaluate_file` with its own per-command status, and `experiment` follows the same
per-command-status pattern per section 11.3.
`PromptScoreStatus` has exactly `IMPROVED_ELIGIBLE`, `COMPLETE_INELIGIBLE`, and
`NONCOMPLETE_ERROR`. A structurally and semantically valid result with status `IMPROVED` can return
`IMPROVED_ELIGIBLE` only when every gate condition and evidence attestation passes; a valid complete
`NO_IMPROVEMENT` or `SERIOUS_REGRESSION` result, or an otherwise non-gate complete comparison,
returns `COMPLETE_INELIGIBLE`; a valid `INVALID_INPUT` or `ERROR` result returns
`NONCOMPLETE_ERROR`. A valid noncomplete result is passed to this API only when evaluation reached
the paired evidence boundary; a pre-execution `INVALID_INPUT` result has no evidence sidecar and is
handled by the command codec. A malformed decoded record, mismatched evidence, or contradictory
field returns `Err(Error.Invalid)` before any status is emitted.
`PromptRender` owns
its rendered `string` and digest and is returned as a bare Move struct, never as a `Result`
payload. Each fallible
command entry — the `Result`-returning `accept_file`/`rollback_file` pair and the
bare-status `evaluate_file`/`experiment_file` pair alike — decodes records whose `str` fields
initially borrow the input buffer, materializes every retained text field into owned `string`,
uses the owning records, and drops them inside the same function; only the Copy status escapes.
Region-bound process stdout/stderr is
cloned or persisted while its `run_output` owner remains alive, following `src/verify.align`.
Persistent records and builder elements contain no borrowed view. Request 8 and Request 10 own the
recursive array/option cleanup required by the evaluator. The two `borrow` parameters to
`verify_result` are caller-owned decoded records whose `str` views remain live for the call; the
verifier retains no view, allocates no persistent value, mutates neither record, and returns only the
Copy status through `Result`.

`verify_result` receives records whose canonical content digests have already been checked by the
C6a1/C6a2 codec. It validates the result/evidence identity pair, embedded experiment and parent
activation references, the persisted workspace/snapshot/input-snapshot/attestation trace and its
prefix rules, trust identities and all three reachability states, every independent input digest row,
C6c1p prefix validation or C6c1 aggregate/reason output as appropriate, status/error family, and
recomputed gate eligibility. It does not decode a document, read a file, access a process or network,
traverse a repository, or re-encode a record.
`prompt state accept` loads the result and explicit evidence through separate paths, invokes this same
decoded verifier, and only then constructs an activation. The evaluator invokes it before writing the
result/evidence pair. No acceptance path trusts a persisted status, aggregate, reason, or gate flag.

The internal Copy verdict labels are `IMPROVED_ELIGIBLE`, `COMPLETE_INELIGIBLE`, and
`NONCOMPLETE_ERROR`; malformed or contradictory decoded records return `Err(Error.Invalid)`.

Output artifacts outside C6d and the blocked C6f2 pair are written only after their complete in-memory
record validates; those earlier writers have no cross-process lock or exclusive-create primitive.
C6d owns one pre-acquired `writer`, emits one bounded canonical activation result, explicitly flushes
it, and then drops it; an occupied final entry is never opened or changed. The C6f2 result/evidence
pair is governed by the separate Request 14 publication contract in §5.2. The operation-overlap matrix in §1.2 classifies every
aggregate-plus-focused and focused-plus-focused pair: disjoint resources are supported,
shared outputs/workspaces are rejected before side effects or explicitly unsupported under the
single-writer precondition, and no concurrent writer is last-writer-wins. After a successful write,
outputs are immutable and content-verified.
Consumers fail closed on an existing or corrupt artifact instead of selecting a guessed winner.

Content digests provide deterministic identity and corruption detection, not author
authentication. C6 is a local single-user workflow: a user who can replace every input artifact can
also construct a different internally consistent history. Repository review, fixed-corpus
provenance, and filesystem ownership are the trust boundary; C6 does not invent signatures or an
authorization service.

Provider errors and evaluation adapter failures are data in result artifacts. Referenced-input
filesystem failures map to the `INVALID_INPUT` codes in section 5; request-decode and output-write
filesystem failures remain `Result` errors. Cleanup failure from a task adapter makes its run
invalid and therefore makes the evaluation `ERROR`.

## 7. Acceptance policy artifact

Acceptance thresholds are human-owned input, not model output. Schema version 1 contains:

```text
PromptAcceptancePolicy:
  schema_version
  artifact_kind: PROMPT_ACCEPTANCE_POLICY
  policy_id
  minimum_task_count
  minimum_samples_per_variant
  minimum_completion_gain_count
  minimum_time_improvement_ppm
  maximum_time_regression_ppm
  maximum_repair_loop_regression_count
  content_sha256
```

The checked-in C6 policy uses:

```text
minimum_task_count: 2
minimum_samples_per_variant: 2
minimum_completion_gain_count: 1
minimum_time_improvement_ppm: 50000
maximum_time_regression_ppm: 100000
maximum_repair_loop_regression_count: 0
```

Parts per million avoid an implicit floating-point comparison policy:
`50000` is 5% and `100000` is 10%.

Policy task/sample minima must fit the corpus and evaluator bounds. Completion counts are
non-negative and at most `64 tasks * 16 samples`; repair-loop regression is at most that product
times 64.
`minimum_task_count` is from one through 64 and `minimum_samples_per_variant` from two through 16.
`minimum_completion_gain_count` is at least one, and `minimum_time_improvement_ppm` is from one
through one million, so neither improvement path can accept equality. Maximum-regression ppm is
from zero through one million. A policy whose bounds cannot be satisfied by its bound corpus is
invalid input rather than an automatic rejection.

## 8. Improvement and serious regression

First, a comparison is eligible only when all requested task/sample pairs complete for both
variants, every row is structurally valid, and every identity matches. Gate eligibility additionally
requires the policy minima, a non-`FIXTURE` provider, a clean named source commit, the exact pinned
Align revision and corpus source, `VERIFIED` reachability for align-llm, external Align, and the
corpus, and `PAIRED_FIXED` seed support.

The persisted aggregate records are:

```text
TaskAggregate:
  task_id
  parent_pass_count
  candidate_pass_count
  parent_repair_loop_count
  candidate_repair_loop_count
  paired_pass_count
  parent_paired_median_time_ns: Option<i64>
  candidate_paired_median_time_ns: Option<i64>
  time_improvement_ppm: Option<i64>
  time_regression_ppm: Option<i64>

CorpusAggregate:
  task_count
  sample_count
  parent_pass_count
  candidate_pass_count
  parent_repair_loop_count
  candidate_repair_loop_count
  paired_pass_count
  parent_paired_median_time_ns: Option<i64>
  candidate_paired_median_time_ns: Option<i64>
  completion_gain_count
  time_improvement_ppm: Option<i64>
  time_regression_ppm: Option<i64>
  repair_loop_regression_count

RegressionReason:
  task_id
  sample_index
  code: PASS_TO_FAIL | BUILD | TEST | POLICY | UNRELATED_DIFF | PUBLIC_API |
    PATCH_SIZE | REPAIR_LOOPS | BENCHMARK | TIME
  parent_value: str
  candidate_value: str
  limit: str
```

A `PASS` row is one completed attempt. All medians use only paired rows where both variants are
`PASS`; newly completed candidate-only rows affect completion count but not timing. Sort times
ascending. For odd `n`, median is element `n / 2`. For even `n`, median is
`lower + (upper - lower) / 2`, rounded down. An empty set is `None`.

Prompt preparation and adapter generation times are each bounded from zero through
`7_200_000_000_000` ns; a passing adapter generation time and checked row total are positive and
the total cannot exceed that bound. Aggregate passing times use the row total. For positive parent
median `p` and candidate median `c`:

```text
if c <= p:
  time_improvement_ppm = ((p - c) * 1_000_000) / p
  time_regression_ppm = 0
else:
  time_improvement_ppm = 0
  time_regression_ppm = ((c - p) * 1_000_000) / p
```

Integer division rounds down. The time bound makes the multiplication fit signed `i64`; any
out-of-range value or arithmetic overflow is `ERROR`. When either median is `None`, both ppm values
are `None` and the time-based improvement path is unavailable.

`completion_gain_count` is candidate pass count minus parent pass count.
`repair_loop_regression_count` is `max(0, candidate total - parent total)` across every structurally
valid row. Task-level counts use the same formulas restricted to one task.

When a task declares a benchmark limit, each passing measurement's benchmark ppm is its non-negative
regression against the immutable benchmark reference named by that task's content-bound artifacts,
not a comparison the adapter invents between variants. Both passing variants must report a value from
zero through one million. Non-passing measurements report no benchmark value and cannot produce a
benchmark-specific reason. A passing candidate value above the task limit is serious regardless of
the parent value.

The corpus paired medians pool both values from every task/sample pair where both variants pass;
task medians pool only that task. The exact ppm formula is applied independently to every task
aggregate and the corpus aggregate. `serious_regression_reasons` is complete, contains no duplicates,
and is sorted by corpus task order, sample index, then the `RegressionReason.code` order shown in
the schema. Corpus-only time and repair-loop reasons use `task_id: CORPUS` and `sample_index: 0`.
Task-aggregate time reasons use that task ID and `sample_index: 0`.
The three value fields use canonical base-10 integers or the exact labels `NONE`, `PASS`, `FAIL`,
`POLICY_VIOLATION`, and `ERROR`.

The reason stream has a deterministic capacity bound. For each task/sample pair, the reason pass
emits at most one record for each of the nine non-`TIME` codes; task-level `TIME` emits at most one
record per task, and corpus-level `TIME` and `REPAIR_LOOPS` emit at most one record each. Therefore,
for `T = task_count` and `S = sample_count`, the exact checked maximum is
`R_max(T, S) = 9 * T * S + T + 2`, with checked arithmetic before allocation. The declared bounds
`1 <= T <= 64` and `2 <= S <= 16` give `R_max <= 9,282`. A reason count above this value is invalid
input, not truncation; every producer and consumer uses this same formula and preserves the complete
ordered stream.

A serious regression is any of:

- a paired parent `PASS` whose candidate is not `PASS`;
- a paired parent build or test `PASS` whose candidate stage is not `PASS`;
- any candidate `POLICY_VIOLATION`;
- candidate unrelated-diff, patch-size, public-API, or repair-loop count above its task limit;
- any task paired-median time regression above `maximum_time_regression_ppm`;
- corpus paired median time regression above `maximum_time_regression_ppm`, regardless of completion
  gain;
- corpus repair-loop regression above `maximum_repair_loop_regression_count`;
- a passing candidate's declared benchmark regresses beyond its task-specific limit.

Cleanup, containment, adapter, malformed-row, identity, and artifact-snapshot failures are
evaluation `ERROR`, not scoreable regressions.

When any serious regression exists, the result is `SERIOUS_REGRESSION` even if another task
improves.

With zero serious regressions, a candidate is strictly improved when either:

1. its pass count exceeds the parent's by at least `minimum_completion_gain_count`; or
2. completed counts are equal, no task completion rate is lower, and median time to passing patch
   improves by at least `minimum_time_improvement_ppm` without increasing total repair loops.

Because every task has the same sample count for both variants, “no task completion rate is lower”
means `candidate_pass_count >= parent_pass_count` in every `TaskAggregate`; no division or rounding
is involved.

All other complete comparisons are `NO_IMPROVEMENT`.

Task completion dominates speed. A fast failure is never an improvement. Unknown or unavailable
time values cannot satisfy the time-based path.

## 9. Evaluation assets and gate measurement

The deterministic smoke corpus may use fixed adapters to prove:

- malformed proposal rejection;
- parent/candidate symmetry and alternating order;
- missing, duplicate, stale, and mismatched rows fail closed;
- `NO_IMPROVEMENT` and `SERIOUS_REGRESSION` cannot be accepted;
- one valid improvement becomes `ACCEPTED`;
- evaluated-parent mismatch is rejected while explicit DAG branching remains valid;
- rollback restores a proven ancestor and rejects a foreign scope;
- previous artifacts remain byte-for-byte unchanged.

The gate corpus must additionally:

- contain at least two real fixed coding tasks with pinned repositories, edit allowlists, and
  validation commands;
- generate candidate patches through the same evaluation provider/model and generation policy for
  both prompt variants;
- include the prompt/context variant in the generation path used by the verification consumer;
- record at least two samples per task and exact environment/provider metadata;
- set each initial C6 gate task's `maximum_repair_loops` to zero and make exactly one bound provider
  generation call per sample, so the independently verified `GenerationRequestIdentity` covers the
  complete model-request path; deterministic scorer fixtures still exercise nonzero repair counts;
- retain complete bounded diagnostics for every non-passing attempt;
- produce a reproducible before/after result from a named clean commit and record it in the gate
  pull request.

The deterministic reference patch remains useful for evaluator correctness but is not counted as a
provider-generated C6 quality result.

```text
PromptGateManifest:
  schema_version
  artifact_kind: PROMPT_GATE_MANIFEST
  gate_id
  source_locator: PromptGateSourceLocator
  baseline_activation: ArtifactReference
  improved_evaluation: ArtifactReference
  improved_evaluation_evidence: ArtifactReference
  accepted_activation: ArtifactReference
  rollback_activation: ArtifactReference
  environment_policy: ArtifactReference
  content_sha256
```

`environment_policy` names the `EnvironmentPolicy` that travels with the gate evidence rather than
with the frozen scope set. It is appended after the settled references and before `content_sha256`,
following the `generation_child_sha256` precedent, so every existing field keeps its position; an
older version-1 manifest without it is invalid and receives no compatibility default. The reference
names kind `ENVIRONMENT_POLICY`, its `artifact_id` is the policy's `policy_id`, and its digest is
the policy's canonical content digest. The validator loads it through the same bounded, physical,
digest-checked reference path as every other manifest member and requires the evaluation's
`EnvironmentIdentityCore.environment_policy_sha256` to equal it, so the policy the measurement ran
under is a bound gate input rather than a path-only file in the evidence directory.

`PromptGateSourceLocator` is the checked-in, content-bound locator used by the independent gate
validator:

```text
PromptGateSourceLocator:
  schema_version
  artifact_kind: PROMPT_GATE_SOURCE_LOCATOR
  source_bundle_id
  align_llm_source_relative_path
  align_source_relative_path
  corpus_source_relative_path
  corpus_file_set_manifest_relative_path: Option<str>
  source_verifier_policy_relative_path
  source_verifier_policy_sha256
  source_verifier_relative_path
  source_verifier_sha256
  source_verifier_runtime
  source_verifier_interpreter_sha256
  git_executable_sha256
  generation_child_sha256
  content_sha256
```

`source_bundle_id` is a non-empty bounded ID for the CI-created bundle. The five required locator
paths are non-empty, source-bundle-relative UTF-8 paths with the ordinary path bound, no NUL, empty,
`.` or `..` component, and no absolute spelling; the conditional FILE_SET manifest path is subject
to the same rule when `Some`. `source_verifier_policy_relative_path` names a regular
`PromptSourceVerifierPolicy` file, and its digest must equal `source_verifier_policy_sha256`.
The decoded policy's helper path, helper digest, helper runtime, interpreter digest, and Git-tool
digest must equal the locator's `source_verifier_relative_path`, `source_verifier_sha256`,
`source_verifier_runtime`, `source_verifier_interpreter_sha256`, and `git_executable_sha256`; the
validator checks those equalities before launching the helper.
`source_verifier_sha256` is the lowercase digest of the exact helper bytes at
`source_verifier_relative_path`, `source_verifier_runtime` must be the canonical
`CPYTHON:<source_verifier_interpreter_sha256>:<source_verifier_sha256>` identity,
`source_verifier_interpreter_sha256` is the lowercase digest required for the explicit gate Python
input, `git_executable_sha256` is the lowercase digest required for the explicit gate Git-tool
input, and `generation_child_sha256` is the lowercase digest required for the explicit gate
generation-child input. The generation child is not a locator path: it is built rather than
committed, so the locator records its identity alone and the validator binds the explicit
`--generation-child-sha256` value to that field during source-bundle revalidation.
The locator does not persist a tested head: the validator derives the actual CI checkout head at
invocation time, which avoids a self-reference when the manifest is in that checkout.
`corpus_file_set_manifest_relative_path` is `Some` exactly when the evidence trust record says
`FILE_SET`, and names the separate regular-file manifest; it is `None` for `GIT_COMMIT`. All
locator paths and helper identity are content identity for the locator only; they do not contain a
machine-specific absolute path. The validator receives the source bundle root as an explicit build
input and resolves every applicable locator beneath it after the same physical symlink,
dangling-link, special-file, and expected-type checks as the evaluation source boundary: the
align-llm, Align, and corpus paths are real directories, the conditional FILE_SET manifest and
source-verifier policy and source verifier are regular files. The Python and Git executables are
explicit machine inputs and are never inferred from those locator paths.
The source bundle root is not
read from the environment or inferred from an evidence path.

The measured gate does not call a credentialed external provider. It validates the checked-in gate result's
schema, content identities, named source commit, task coverage, aggregates, acceptance decision,
and zero-regression claim, then runs deterministic lifecycle and evaluator regressions. The
canonical checked-in evidence set is named by one human-owned `PromptGateManifest` containing
references to the frozen baseline activation, the real `IMPROVED` evaluation and its independently
produced evidence sidecar, the `ACCEPTED` activation, and the subsequent `ROLLED_BACK` activation.
The evidence reference must have the same evaluation ID and result digest as the evaluation
reference. The gate validator recomputes every nested digest and requires this exact chain:

```text
eligible IMPROVED evaluation + matching PromptEvaluationEvidence
  -> ACCEPTED activation whose parent is the evaluated baseline
     and whose effective variant is the evaluated candidate
  -> ROLLED_BACK activation whose parent is that accepted activation
     and whose target/effective variant is the proven baseline
```

An absent artifact, a fixture-only artifact, a changed source asset, or any ID/digest/scope/variant
link mismatch fails the measured gate.

The validator recomputes every link the evaluation result declares, so no persisted cross-reference
is accepted on its own claim:

- the scope's `acceptance_policy_sha256`, `generation_policy_sha256`, `base_prompt_sha256`, and
  `repo_prompt_sha256` must equal the embedded acceptance policy, generation policy, and each
  variant's nested base and repo prompt digests, exactly as `valid_activation_shape` requires of an
  activation;
- every `*_source` `ArtifactReference` — experiment, parent activation, corpus, acceptance policy,
  generation policy, provider control, and workspace preflight — must name the kind, identity, and
  content digest of the document the same result embeds;
- the generation policy must bind the evaluated provider control by digest and repeat its kind,
  endpoint ID, and model, and the scope must repeat the same provider kind and model;
- the corpus must carry the scope's corpus ID and revision, and its `task_files` must be exactly
  the evaluated task list: one distinct declared file per task, each observed as the task file of
  that task's own automatic input snapshot, with no snapshot naming an undeclared task;
- the workspace preflight request and result must carry the evaluation ID, and the result must be
  `SAFE` with no error;
- the snapshot request, result, input-snapshot, and attestation streams must all be present, every
  snapshot result must be `MATCH`, and the attestations must cover every row once in row order,
  each `COMPLETE`, each with equal before/after digests, and each naming persisted records;
- `EnvironmentIdentityCore.source_verifier_runtime` and `source_verifier_policy_sha256` must equal
  the locator's values, and `environment_policy_sha256` must equal the manifest-referenced
  environment policy.

The gate pull request records the exact command and provider environment used to create the
measured artifact without recording credentials.

When a canonical C6 gate manifest is present, the complete command is
`make prompt-gate-check C6_GATE_SOURCE_BUNDLE_ROOT=/absolute/source-bundle-root C6_GATE_PYTHON_EXECUTABLE_PATH=/usr/bin/python3.12 C6_GATE_GIT_EXECUTABLE_PATH=/absolute/git`,
which section 11.3 extends with the generation-child pair.
The Make target passes these explicit command-line values to the gate validator as
`--source-bundle-root`, `--python-executable-path`, and `--git-executable-path`; it rejects a missing, empty, relative, unsafe,
or unreadable value and has no environment or sibling-checkout fallback.

`make prompt-gate-check` with those explicit `C6_GATE_*` command-line values is the named capable
gate qualification for the measured gate; it is a member of no lane and no aggregate. The
supervised `make ci` admits exactly `make --no-print-directory ci` with no variable assignments and
runs its graph under a cleared, fixed environment (`docs/specs/check-gate-topology.md`), so the
explicit values cannot reach a supervised aggregate target. That caller contract is unchanged and
`make ci` keeps its existing goals; the measured gate is instead documented, per the repository
verification policy, as a focused qualification not reached by the supervised aggregate. It runs
when the gate validator, the checked-in `eval/prompt/gate/` evidence, or the frozen
`eval/prompt/canonical-v1/` assets change, and at the C6-MEASURED publication gate. Its passing
evidence is `scripts/prompt-gate-validator.py` exiting 0 under this target with all five explicit
values against a clean capable checkout whose generation child was built in the same run, recorded
with the exact command and provider environment and without credentials.

Before deriving the head, the validator retains `C6_GATE_PYTHON_EXECUTABLE_PATH` and
`C6_GATE_GIT_EXECUTABLE_PATH` as explicit absolute regular executables and checks their same-descriptor bytes against
the locator/policy interpreter and Git digests. Ubuntu 24.04 gate evidence uses exactly
the physical, non-symlink Ubuntu 24.04 path `/usr/bin/python3.12` whose digest must match the locator;
a version string alone is insufficient. The
Make target does not invoke ambient Python or Git to perform these checks. The validator then invokes
those retained descriptors, with `env_clear()` and only `LANG=C`, `LC_ALL=C`, `GIT_CONFIG_NOSYSTEM=1`,
`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`, `GIT_OPTIONAL_LOCKS=0`,
`GIT_TERMINAL_PROMPT=0`, `GIT_PAGER=cat`, `GIT_NO_REPLACE_OBJECTS=1`, and `GIT_GRAFT_FILE=/dev/null`, for each
fixed command in the actual CI checkout at `$(pwd)`. Before any Git child, the validator performs
the same bounded raw `.git`/`gitdir`/`commondir` metadata walk and local/worktree config scan as the
source verifier for the CI checkout and every source-bundle Git checkout. It rejects local includes,
settings that can affect the fixed local commands (including command, hook, helper, filter, pager,
path, promisor, proxy, and transport settings), and malformed or unsafe metadata before invoking
Git. It explicitly allows only the inert ordinary-clone metadata `remote.<name>.url`,
`remote.<name>.pushurl`, `remote.<name>.fetch`, `branch.<name>.remote`, and
`branch.<name>.merge`; the gate validator has no other config-scan exception. It then runs the
fixed common-directory locator and requires the Git-reported physical directory to equal the
raw-walk result. The locator itself is
`<git> --no-pager -C <root> -c core.useReplaceRefs=false -c core.alternateRefsCommand= -c core.fsmonitor=false -c core.hooksPath=/dev/null -c credential.helper= -c diff.external= rev-parse --path-format=absolute --git-common-dir`.
Every Git child is a direct argv vector with the exact prefix
`<git> --no-pager -C <root> -c core.useReplaceRefs=false -c core.alternateRefsCommand= -c core.fsmonitor=false -c core.hooksPath=/dev/null -c credential.helper= -c diff.external=`;
no shell, ambient Git config, pager, hook, helper, proxy, or replacement setting may alter it.
The raw common-directory check rejects any present `refs/replace`, `info/grafts`, or
`objects/info/alternates` entry there, including symlinks, directories, and special files. A source
bundle with any rejected mechanism fails the gate before identity or ancestry observation.
The source verifier applies the same common-directory check and fixed environment to every source-bundle
Git checkout it opens; the gate validator's own identity and ancestry commands have no exception:
For each such common directory, the validator also runs the bounded
`<git> --no-pager -C <root> -c core.useReplaceRefs=false -c core.alternateRefsCommand= -c core.fsmonitor=false -c core.hooksPath=/dev/null -c credential.helper= -c diff.external= for-each-ref --format=%(refname)%00 refs/replace/`
check and fails if the exact `<refname> NUL LF` stream is non-empty; this covers loose, packed, and
reftable replacement refs before any source identity is accepted. A nonzero exit, output cap, or
malformed replacement stream also fails the gate.
Appending to that prefix, the validator runs `status --porcelain --untracked-files=all
--ignore-submodules=all`, `rev-parse --is-inside-work-tree`,
`rev-parse --is-shallow-repository`, and `rev-parse --verify HEAD` in that order. The required
results are an empty status, `true`, `false`, and one full lowercase commit SHA. The validator derives
`tested_align_llm_head` from
that last command and does not accept an environment or user override for the derived value. It
constructs the temporary GATE verifier request with that value; it does not expose a caller-supplied
`--tested-align-llm-head` gate argument. The validator resolves every applicable relative locator
from the manifest beneath the explicit root, invokes the content-bound source verifier with the
exact helper/runtime contract, and requires the source-bundle align-llm checkout's clean,
complete-history `HEAD` and the GATE helper's `align_llm_observed_head` to equal the derived actual
CI head, with `align_llm_reachability: VERIFIED`. This observed head is intentionally not required
to equal the evaluated commit in the evidence. The validator then runs `merge-base --is-ancestor
<evidence.expected_align_llm_commit> <tested_align_llm_head>` in the same fixed argv prefix, with
the same executable and cleared environment. A missing commit,
shallow/unavailable ancestry, or a non-zero ancestry result fails the gate. This binds a separate
source bundle to the actual checked head without persisting a self-referential head in the manifest.
The validator also proves exact pinned Align revision and
exact corpus `GIT_COMMIT` or `FILE_SET` identity. For `FILE_SET`, it reads the locator's manifest,
hashes its exact canonical bytes, verifies every listed regular file beneath the corpus root, and
requires the manifest digest and membership to equal the evidence's expected source identity. It
does not trust persisted reachability booleans and never uses the historical absolute paths from the
evaluation request. The required CI environment creates or checks out the source bundle at the
derived actual head, supplies its explicit root and Git-tool path to this command, and records the
command, actual head, tested base tip, merge base, Git-tool digest, and source-bundle content
identities as check evidence; neither absolute input path is persisted in the gate artifact.

## 10. Contract ledger and acceptance matrix

Before implementation review, each row must point to the actual diff and a passing test or to an
explicitly reviewed deferral.

| Contract | Intended owner | Planned acceptance evidence |
| --- | --- | --- |
| Four CLI operations and exact arguments | `src/main.align` | CLI smoke covers valid and invalid arity for every operation |
| Gate source-bundle validation input | `Makefile`, gate validator | the named capable qualification `make prompt-gate-check C6_GATE_SOURCE_BUNDLE_ROOT=<absolute-root> C6_GATE_PYTHON_EXECUTABLE_PATH=<absolute-python> C6_GATE_GIT_EXECUTABLE_PATH=<absolute-git> C6_GATE_GENERATION_CHILD_PATH=<absolute-child> C6_GATE_GENERATION_CHILD_SHA256=<digest>` passes all five explicit values as `--source-bundle-root`, `--python-executable-path`, `--git-executable-path`, `--generation-child-path`, and `--generation-child-sha256` — the section 11.3 generation-child pair is the fourth input and is checked before any evidence identity — rejects missing/relative/unsafe roots or tools before source reads, resolves the Git common directory, rejects replacement/graft/alternate mechanisms, scans local Git configuration while allowing only inert ordinary-clone remote/branch metadata, uses fixed no-replace/no-graft/no-pager/command overrides for every Git command, checks the derived clean CI head and evaluated-commit ancestry as separate proofs, validates the source-verifier policy/helper/interpreter/tool identities, and revalidates every locator and exact source identity |
| Source-verifier request/result boundary | C6f1 source verifier, `src/prompt_evaluate.align`, gate validator | request/result kind, mode-specific EVALUATION/GATE observed-head semantics, separate evaluated-commit ancestry, exact argv/env/cwd, common-directory and replacement/graft/alternate rejection, bounded local-config scan, fixed Git overrides, helper/interpreter/Git digests, timeout/capture caps, raw-byte FILE_SET fixtures, `COMPLETE`/`UNAVAILABLE` field shapes, observed-identity equality for `VERIFIED`, and gate rejection of unavailable proof |
| Mode-specific gate head and ancestry identity | C6f1 source verifier, gate validator | EVALUATION exact-head equality; GATE observed-head equality to derived CI head plus independent expected-commit ancestry; normal-merge fixture where the two SHAs differ; `prompt-source-verifier-mode-identity-smoke` and `prompt-gate-merge-head-ancestry-smoke` |
| Repository-local Git configuration isolation | C6f1 source verifier, gate validator | raw `.git`/`gitdir`/`commondir` and local/worktree config scan before any Git child, include rejection, command-bearing-key rejection, ordinary-clone inert remote/branch metadata allowlist, fixed `--no-pager`/`-c` overrides, fsmonitor sentinel non-execution, and gate rejection before identity observation; `prompt-source-verifier-local-git-config-smoke` and `prompt-gate-local-git-config-smoke` |
| Complete replacement-ref namespace | C6f1 source verifier, gate validator | loose, packed-refs, reftable, nonzero/malformed/capped/non-empty `for-each-ref` output, and no-replacement-object controls; `prompt-source-verifier-replacement-namespace-smoke` and `prompt-gate-replacement-namespace-smoke` |
| Declared records, bounds, canonical digest | `src/prompt_model.align`, `src/prompt_artifacts.align` | `PromptSourceVerifierPolicy`, `PromptEvaluateRequest`, and `PromptGateSourceLocator` exact field-order semantic/byte goldens; missing interpreter field rejects old version-1 bytes; helper/interpreter/runtime/Git identity mutations change canonical digests; round-trip, tamper, unknown-version, and oversize fixtures |
| Persisted string-label mapping | `src/prompt_model.align` | every allowed and unknown kind/status/operation/stage label plus canonical golden vectors |
| Fixed hierarchy and rendering order | `src/prompt_model.align` | golden rendered prompt and immutable base/repo/task tests |
| Initial context-policy semantics | `src/prompt_model.align` | disabled sections, source bounds, UTF-8-safe patch/diagnostic truncation, and C6b-memory failure-memory selection |
| Content-bound A/B inputs | `src/prompt_evaluate.align`, task manifests | expected digest, workspace preflight, deduplicated snapshot/input-snapshot records, per-invocation pre/post drift, mode, tree, dirty-source, seed, generation, environment, and FILE_SET-manifest regressions |
| Explicit verifier source inputs | `src/prompt_evaluate.align`, C6f1 source verifier | absolute root/manifest/interpreter/tool path validation, policy/helper/interpreter/Git digest and composite runtime validation, `FILE_SET` option pairing, canonical raw-byte manifest membership/mode/digest, exact clean checkout observations, fixed argv/env/cap/timeout, observed identity copied into evidence, `VERIFIED` equality, and `UNVERIFIED` preservation before any adapter or snapshot call |
| Explicit adapter request and environment isolation | `src/prompt_evaluate.align`, task adapter | adapter-request identity/path/digest fixtures; env-clear rejection and exact allowlisted-value survival in both directions |
| Producer-owned environment identity | trusted probe carriers, evaluator verifier | non-circular core preimage, carrier equality, OS/CPU/GPU/compiler/runtime unavailable-value, `Option` CPU-count, source-policy/helper/interpreter/Git identity, and digest fixtures |
| Physical path trust boundary | snapshot helper, all command owners, explicit verifier source boundary, and Align Request 18 adoption | project-root containment for ordinary inputs plus read-only external verifier-root exception; retained-root request/artifact/result traversal; symlink component, dangling link, output link, special file, physical escape, Git common-directory replacement/graft/alternate entries, relative/absolute, cleanup, and early-exit regressions |
| Bounded child capture | Align Request 11 adoption, evaluator/provider owners | exact cap, cap+1, stdout/stderr pressure, timeout precedence, kill/reap, invalid bytes, and allocation cleanup |
| Owned recursive artifact persistence | Align Request 13 adoption, `src/prompt_model.align` | borrowed-wire lifetime, explicit text clone, nested record/option/array graph, source drop, semantic/byte round-trip, and cleanup vectors |
| Bounded canonical persistence | Align Requests 12 and 13 adoption, codec owners | exact cap, cap+1, escape expansion, nested option/array, overflow, allocation failure, no-partial-write vectors, temporary/final output order, second-finalization failure, and pair cleanup-failure recovery |
| Exclusive artifact publication | Align Request 14 adoption, `src/prompt_evaluate.align` | `create_exclusive`/`rename_no_replace` or the reviewed shipped equivalents; existing-target and competing-creator failures, no replacement, same-filesystem publication, and pair cleanup/recovery before C6f2 writes any result/evidence output |
| Evaluation result/evidence pair persistence | `src/prompt_evaluate.align`, `src/main.align`, Request 14 adoption | two exclusively created sibling temporary files, bounded canonical bytes, result-then-evidence no-replace finalization, first-finalization and second-finalization failures, evaluator-owned reverse cleanup, collision destination preservation, owned-path rechecks, `OUTPUT_WRITE`, `OUTPUT_PAIR_CLEANUP_FAILED`, and explicit owned-orphan recovery path; no check-then-create or undeclared native publication workaround |
| Exact source identity and integration method | explicit evaluator source inputs, C6f1 source verifier, gate manifest, CI validator, verifier evidence | exact clean full SHA claims, exact-HEAD equality for evaluator align-llm, derived clean CI-head equality plus evaluated-commit ancestry for the gate, replacement/graft/alternate rejection through the resolved Git common directory, fixed no-replace/no-graft environment, policy/helper/interpreter/Git identity revalidation, expected/observed-identity binding, unavailable or mismatching source roots as `UNVERIFIED`, source-bundle locator revalidation, normal-merge, base-tip/head/merge-base, and separate align-llm/external-Align/corpus reachability fixtures |
| Minimum compatibility floor | `Makefile`, `.github/workflows/ci.yml`, compatibility job | Ubuntu 24.04 x86_64 / Rust 1.96 / LLVM 22 / CPython 3.12 / Make 4.3 acceptance environment |
| Normative Align syntax | C6a1 syntax fixture | declarations separate from positional calls, pinned `alignc check`, and explicit no-proposed-API deferral before C6a1 |
| Measurement state machine and integer math | `src/prompt_score.align` | exhaustive row combinations plus odd/even median, rounding, zero/None, threshold, and overflow fixtures |
| Incomplete-prefix row validation | C6c1p `src/prompt_score.align` | empty, strict-prefix, terminal-`ERROR`, post-error, complete-prefix, first-invalid-index, and no-output-mutation fixtures |
| Provider proposal with no secret persistence | `src/prompt_experiment.align`, bounded provider boundary | deterministic provider fixture over the adopted Request 5 bounded transport, transport-size cap, one-shot credential lifetime, pre-truncation redaction, and API-key regression |
| Executable provider control and prompt roles | provider control, task adapter | config-field identity fixtures and exact empty-system/rendered-user request bytes |
| Seed capability attestation | provider adapter, evaluator verifier | requested/applied seed equality, provider request digest, unsupported/rejected ineligibility, and paired-row fixtures |
| Same adapter and alternating A/B order | `src/prompt_evaluate.align` | invocation-log smoke with odd/even samples |
| Exact row and scope binding | `src/prompt_evaluate.align` | stale variant, wrong task/sample/provider/digest fixtures |
| Validation precedence and invalid-result shape | all command owners | table-driven first-failure fixtures prove no external call, source-helper/policy/tool rejection before source reads, evidence-output handling, result/evidence alias rejection, and exact `Option` population |
| Complete metrics and serious regressions | `src/prompt_score.align` | table-driven comparison fixtures for every rule in section 8 |
| Persisted evaluation execution trace | `src/prompt_evaluate.align`, `src/prompt_score.align` | workspace-preflight identity, snapshot/input-snapshot deduplication and order, complete/failed/drift attestation state shapes including `PRECHECK_DRIFT`, `ADAPTER_FAILED`, and `POSTCHECK_DRIFT`, retained non-`ERROR` row after post-row `CLEANUP_FAILED`, exact error prefix, bounded overflow counter/digest, and `RESULT_TOO_LARGE` empty-result fixtures |
| Compact result-size failure | `src/prompt_evaluate.align`, `src/prompt_model.align`, `src/prompt_score.align` | canonical `PromptTraceOverflow` counter/digest golden vectors, exact empty-array/option shape, cap+1 transition, bounded compact encoding, empty evidence inputs, and no scorer invocation |
| Evaluation evidence binding | `src/prompt_evaluate.align`, `src/prompt_model.align`, `src/prompt_score.align`, `src/prompt_state.align`, gate validator | missing/wrong/duplicate/out-of-order expected-input rows, empty compact-result evidence, result-digest mismatch, expected/observed source-identity binding for every `VERIFIED` state, each reachability state, explicit evidence-path acceptance, and gate-manifest pairing fixtures |
| Acceptance reuses the pure verifier | `src/prompt_score.align`, `src/prompt_state.align` | tampered fixture status/aggregate/reason/eligibility/evidence is rejected before activation |
| Accept only eligible improvement | `src/prompt_state.align` | improved/no-improvement/regression/error/parent-mismatch cases |
| Activation operation invariants | `src/prompt_state.align` | baseline/accept/rollback cross-field table plus every forbidden combination |
| Immutable rollback lineage | `src/prompt_state.align` | valid ancestor, broken chain, duplicate, foreign-scope, retained provenance, reason, and no-overwrite cases |
| C6d retained-root activation I/O | `src/prompt_state.align`, `src/prompt_artifact_io.align`, Align Request 18 adoption | exact/cap-plus-one request and short-read artifact bounds; request/root/intermediate/final symlink and dangling-link rejection; directory/FIFO/socket/device and denied/missing inputs; deterministic error mapping/order; unsafe/missing/denied/occupied result paths with no replacement; exact one-winner create race; explicit write/flush/Drop |
| Single-writer immutable persistence | all command owners | existing-output, result/evidence physical-alias, documented immutable-input precondition, C6d exclusive-create collision ownership, later C6f2 no-replace collision ownership, and corrupt-partial-artifact regressions |
| Physical workspace containment and raw entry closure | trusted snapshot helper, `src/prompt_evaluate.align` | symlink root/component, physical escape, non-UTF-8 extra entry, mutation, and cleanup regressions |
| Fixed-corpus provider quality gate | evaluation adapter and `eval/tasks/prompt-v1/` | at least 2 tasks x 2 samples; improvement and zero serious regressions |
| Canonical acceptance and rollback chain | gate manifest and validator | source-bundle locator/policy/helper/tool, derived tested-head ancestry, explicit root/FILE_SET-manifest revalidation plus real improved evaluation + matching evidence -> accepted activation -> rollback, with every wrong/missing digest or evidence reference rejected |
| Regression integration | `Makefile`, `.github/workflows/ci.yml`, smoke scripts | bounded functional owners in the routine graph; complete qualification commands at the owning capability gate; one final `make ci` per integrated wave |

### 10.1 Implementation closure matrix

Each named regression is introduced by the capability that first owns the cell. Before review of
that capability, the matrix-to-diff pass replaces the planned owner with the actual file/test
location.

C6d remains one mergeable capability even though its request records/codecs, retained-root I/O,
accept/rollback state owner, CLI dispatch, and adversarial smoke together exceed roughly 1,000
hand-written lines. These pieces are one strict producer-to-consumer chain: no prefix is useful
without the next piece, and splitting it would duplicate the canonical lifecycle fixture and path
proof while exposing dormant public records or I/O helpers. One boundary therefore carries less
integration risk and one complete verifier/path/publication proof.

| Path | Model/codec | Renderer/memory | Scorer/state | Evaluator/provider | Exact planned regression |
| --- | --- | --- | --- | --- | --- |
| Construction | declared record decode, field-order validation, canonical digest | owned `PromptRender` construction | aggregate/activation construction plus decoded result/evidence verifier inputs | request, snapshot, row, result, and independent evidence construction | `prompt-codec-construction`, `prompt-row-construction`, `prompt-evidence-construction` |
| Success | encode/decode semantic and byte golden vectors | fixed hierarchy, bounded patch/diagnostic contexts, and chronological bounded failure-memory selection | `IMPROVED`, `ACCEPTED`, `ROLLED_BACK`; decoded verifier returns the matching Copy verdict | proposal and alternating complete A/B run with evidence sidecar | `prompt-codec-golden`, `prompt-render-golden`, `prompt-model-smoke`, `prompt-lifecycle-smoke`, `prompt-evaluate-order-smoke`, `prompt-verifier-smoke` |
| Gate source revalidation | manifest/locator/policy decode, canonical raw-byte FILE_SET manifest, and digest | N/A | gate validator performs the raw `.git`/`gitdir`/`commondir` and local-config walk before any Git child, allows only inert ordinary-clone remote/branch metadata, resolves and checks each Git common directory, rejects replacement/graft/alternate mechanisms across loose and packed/ref-backend storage, validates policy/helper/interpreter/Git identities, checks the derived clean align-llm head and evaluated-commit ancestry as separate proofs, and compares exact identities | explicit `C6_GATE_SOURCE_BUNDLE_ROOT`, `C6_GATE_PYTHON_EXECUTABLE_PATH`, and `C6_GATE_GIT_EXECUTABLE_PATH` reach the validator; no ambient or historical absolute path | `prompt-gate-source-bundle-smoke`, `prompt-gate-source-revalidation-smoke`, `prompt-gate-git-replacement-graft-smoke`, `prompt-gate-local-git-config-smoke`, `prompt-gate-replacement-namespace-smoke`, `prompt-gate-merge-head-ancestry-smoke`, `prompt-gate-ancestry-smoke`, `prompt-file-set-manifest-smoke`, `prompt-source-verifier-boundary-smoke` |
| Source-verifier process boundary | policy/helper/interpreter/Git identity and request/result codecs | N/A | raw `.git`/`gitdir`/`commondir` metadata and local/worktree config are scanned before any Git child; retained-descriptor exact Python/helper/Git argv, fixed Git no-pager/no-replace/no-graft/command overrides, cleared environment, cwd, common-directory checks, complete replacement namespace enumeration, byte caps, timeout, raw-byte FILE_SET traversal, mode-specific result-status/observed-identity shape, and no side effect before digest validation | C6f1 trusted helper contract; child timeout/output/malformed/unavailable states become explicit unverified evidence or gate failure after complete descendant cleanup, while cleanup failure takes precedence | `prompt-source-verifier-argv-smoke`, `prompt-source-verifier-env-smoke`, `prompt-source-verifier-runtime-smoke`, `prompt-source-verifier-mode-identity-smoke`, `prompt-source-verifier-git-replacement-graft-smoke`, `prompt-source-verifier-local-git-config-smoke`, `prompt-source-verifier-fsmonitor-nonexecution-smoke`, `prompt-source-verifier-replacement-namespace-smoke`, `prompt-source-verifier-observed-identity-smoke`, `prompt-source-verifier-cap-smoke`, `prompt-source-verifier-file-set-bytes-smoke`, `prompt-source-verifier-descendant-cleanup-smoke` |
| Incomplete prefix | N/A: decoded records are not owned here | N/A | C6c1p `validate_prefix` accepts empty/strict/terminal-error prefixes and classifies all task-limit plan errors before counting; C6c2 skips aggregation and accepts a retained non-`ERROR` row after `CLEANUP_FAILED` | persisted rows and terminal attestation agree with the prefix result | `prompt-score-prefix-smoke`, `prompt-prefix-retention-smoke`, `prompt-verifier-prefix-smoke`, `prompt-verifier-cleanup-retention-smoke` |
| Invalid/malformed input | cap, schema, kind, field, nested, array, digest, reference order | invalid policy/source returns `INVALID_INPUT`; malformed or unknown-schema memory returns `INVALID_FAILURE_MEMORY` before composition | contradictory decoded result/evidence/row/lineage rejection | no provider/helper/adapter call before the evaluator's complete pre-side-effect validation | `make prompt-model-smoke`, `prompt-codec-invalid`, `prompt-score-invalid`, `prompt-verifier-invalid`, `prompt-evaluate-smoke` |
| Operational failure | output write returns `Result` error | N/A: renderer is pure and reports invalid context as data | incomplete evaluation cannot activate; evidence/result write errors are not successful pairs | provider/helper/adapter timeout, output, status, drift, cleanup, pair-finalization, collision ownership, and result-size errors | `prompt-output-error-smoke`, `prompt-external-error-smoke`, `prompt-evidence-output-smoke`, `prompt-evidence-pair-finalization-smoke`, `prompt-evidence-pair-collision-ownership-smoke`, `prompt-adapter-failed-attestation-smoke`, `prompt-trace-overflow-smoke` |
| Early exit | decoded invalid request writes one invalid result | N/A: pure function has no side effect to unwind | first serious result is still fully recomputed; first invalid lineage stops | first source-helper, snapshot, adapter, precheck drift, postcheck, postcheck drift, or result-size failure stops later invocations and retains only the valid prefix or explicit compact envelope | `prompt-first-failure-smoke`, `prompt-prefix-retention-smoke`, `prompt-adapter-failed-terminal-smoke`, `prompt-drift-attestation-smoke`, `prompt-trace-overflow-terminal-smoke` |
| Cleanup/drop | decoded Move records and digest buffers drop in owner function | rendered string/digest drop with bare result owner | temporary aggregate/activation records drop after encode; borrowed verifier inputs are not retained | process outputs cloned while owner lives; helper/tool owners, evaluator-owned result/evidence temp/final owners, and files/checkouts removed; collision destinations are never removed; failed pair finalization performs reverse cleanup or emits its explicit recovery error; empty raw workspace restored; overflow trace stream released | `prompt-owned-drop-smoke`, `prompt-workspace-cleanup-smoke`, `prompt-verifier-borrow-lifetime-smoke`, `prompt-source-helper-cleanup-smoke`, `prompt-evidence-pair-cleanup-smoke`, `prompt-evidence-pair-collision-ownership-smoke`, `prompt-trace-overflow-drop-smoke` |
| Replacement/move-out | source fields are reconstructed or moved once; no aliasing rewrite | `PromptRender` moves to caller as one bare value | accepted/rollback variant embedded unchanged; source not reused; verifier returns only Copy status | rows, snapshots, and independent evidence move into the final result/pair; builder source is consumed once | `prompt-move-compile-smoke`, `prompt-variant-identity-smoke`, `prompt-evidence-move-smoke` |
| Concurrent/overlap attempt | N/A: pure validation has no shared mutable state | N/A: pure rendering has no shared mutable state | immutable DAG branches are independent; shared output/activation mutation is rejected before side effects | complete experiment/evaluate/accept/rollback 4x4 matrix; no overlapping adapter calls; disjoint independent processes are supported | `prompt-operation-overlap-smoke`, `prompt-no-overlap-smoke`, `prompt-existing-output-smoke`, `prompt-evidence-result-alias-smoke` |

### 10.1d C6b-memory renderer closure

This capability makes the deferred failure-memory section a usable renderer consumer. It does not
change the C5 event schema, add a second memory format, or consume Request 14/evaluator/activation
surfaces. The final matrix-to-diff pass must map every row below to the implementation and the
owner smoke before review.

| Axis | Actual implementation | Passing owner evidence |
| --- | --- | --- |
| Public policy and call formation | `prompt_artifacts.ContextPolicy` and `prompt_model.ContextPolicy` contain the same three failure-memory fields; `prompt_model.render` receives `task_id` and `failure_memory_jsonl` before the policy and returns the extended `PromptRenderStatus` | `src/prompt_artifacts.align`, `src/prompt_model.align`, `src/prompt_model_smoke.align`, and `make c6b-memory-adoption` |
| Policy and source validation order | policy flag/limit mismatches and oversized snapshots return `INVALID_INPUT`; both policy owners bound memory to 64 events and 65,536 bytes, and the renderer source cap is 1,048,576 bytes before JSONL decoding | `make c6b-memory-adoption` invalid-policy, oversized-source, oversized-memory, and limit cases |
| Complete JSONL validation | `failure_memory.select_context` validates every non-empty line as the private `MemoryEvent` with schema version 1; malformed and unknown-schema lines invalidate the complete source, including when the section is disabled | `prompt-model-smoke` malformed-memory, unknown-schema, and disabled-invalid-memory cases |
| Backward bounded selection | the selector scans newest-to-oldest by source offsets, matches only `task_id`, skips non-fitting matching lines, counts inter-line separators, stops at the event cap, and emits selected lines chronologically | `prompt-model-smoke` selected-memory, event-cap, and byte-budget cases |
| Renderer integration and status | `prompt_model.render` delegates selection after ordinary policy/source validation, emits the fixed failure-memory heading, preserves `(omitted)` when disabled, and returns empty text/digest for invalid memory | `prompt-model-smoke` exact rendered text/SHA, disabled-memory, and `INVALID_FAILURE_MEMORY` cases |
| Ownership and cleanup | the selector owns only bounded offset records and its output builder; the bare `MemoryContext` and `PromptRender` move to the caller with no retained source view or private event value | pinned per-unit/whole-program owner compile and the successful renderer smoke |

### 10.1c C6a1/C6a2 adoption closure

This capability implements only the declared artifact graph, its canonical codec, and the bounded
file consumer. The renderer-memory cells are consumed by the C6b-memory closure above; verifier,
evaluator, and activation cells remain deferred to their named C6 owners.

The candidate is intentionally larger than a small checkpoint because the 50-record graph, its 100
root codec entry points, and the adoption consumers must land as one synchronized boundary. Splitting
the declarations from the first real loader would leave no stable consumer and would duplicate the
graph-shape, ownership, and canonical-byte proof across pull requests.

| Axis | Actual implementation | Passing owner evidence |
| --- | --- | --- |
| Declared graph shape and codec coverage | `src/prompt_artifacts.align` contains the complete 50-record/543-field graph and one decode plus bounded encode wrapper per record | `scripts/run-c6-prompt-artifact-adoption`; pinned `check-per-unit` compiles the graph consumer |
| Owned wire lifetime | `src/prompt_artifact_io.align` reads one bounded wire buffer, decodes into the shipped owned graph, and returns only after the buffer scope ends | `scripts/run-c6-json-escape-adoption`, `scripts/run-c6-prompt-artifact-adoption`; escaped nested text round-trips byte-for-byte |
| Optional and malformed JSON ownership | Request 15's missing/`null` option, nested escaped text, later type error, trailing input, and duplicate field cases use the decoded owner | `scripts/run-c6-json-decoded-owner-adoption` |
| Recursive JSON graph decode | `PromptEvaluationResult` decodes after its input string's scope and retains a nested `Option<CorpusAggregate>` plus an array of `RegressionReason` records before canonical encode | `scripts/run-c6-json-recursive-graph-adoption` |
| Recursive record and array construction | Request 8/10 adoption owners construct runtime-sized arrays with owned records, nested `Option`, nested arrays, reallocation, and partial empty values | `scripts/run-c6c2-request8-adoption`, `scripts/run-c6c2-request10-adoption` |
| Canonical bounded persistence | Request 12 adoption exercises exact-cap success, cap-minus-one overflow, cap-plus-one success, malformed decode, and the bounded artifact reader's input cap | `scripts/run-c6-json-bounded-encoding-adoption`, `scripts/run-c6-prompt-artifact-adoption` |
| Semantic validation and unknown fields | Prompt-variant nested digests are recomputed before use; unknown fields are ignored on decode and omitted by canonical re-encode; tampered digests are rejected | `scripts/run-c6-prompt-artifact-adoption` |
| Full evaluator cleanup/publication | Not applicable to this capability; result/evidence pair publication, process cleanup, and activation cleanup remain deferred to C6f2/C6d owners and are not claimed here | Explicit deferral in Sections 1.2, 10, and 11 |

### 10.1a Final-review redesign closure

The terminal review reopened these cells rather than authorizing another local repair loop. The
redesigned capability is not implementation-ready until every row below has an actual owner and passing
fixture in the diff.

| Final-review invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Gate head versus evaluated commit | C6f1 source verifier and gate validator | EVALUATION records exact expected-head observation; GATE records the derived CI head and proves the evaluated commit is its ancestor; the two SHAs may differ after normal merge | `prompt-source-verifier-mode-identity-smoke`, `prompt-gate-merge-head-ancestry-smoke` |
| Repository-local Git command isolation | C6f1 source verifier and gate validator | raw-scan bounded `.git`/`gitdir`/`commondir` metadata and common/worktree config before any Git child, without following includes; reject command-bearing keys before observation while accepting only inert ordinary-clone remote/branch metadata; apply fixed no-pager/no-replace/no-graft/command overrides to every direct Git invocation | `prompt-source-verifier-local-git-config-smoke`, `prompt-gate-local-git-config-smoke`, `prompt-source-verifier-fsmonitor-nonexecution-smoke`, `prompt-source-verifier-ordinary-clone-config-smoke`, `prompt-gate-ordinary-clone-config-smoke` |
| Complete replacement-ref namespace | C6f1 source verifier and gate validator | raw-check unsafe loose entries, enumerate `refs/replace/` through the pinned Git ref backend, reject nonzero, capped, malformed, or non-empty output, and preserve the check for packed-refs and reftable | `prompt-source-verifier-replacement-namespace-smoke`, `prompt-gate-replacement-namespace-smoke`, `prompt-replacement-packed-ref-smoke` |

### 10.1b Conditional-final review rescope closure

The conditional final review found two implementation-level ownership contradictions, one output
state contradiction, and one continuity-boundary violation. This section reopens those cells before
any successor repair. PR #50 is a historical terminal review checkpoint; the capability must map each row below to
the final prose, ledger, and regression before it is reviewed.

| Rescope invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Scratch allocation failure | C6c2 `src/prompt_score.align`, Requests 8/10 | checked capacity overflow is recoverable `Err(Error.Invalid)` before allocation; runtime allocator failure follows the declared Request 8/10 terminal nonzero process policy and has no recoverable-result or cleanup-after-abort promise; normal successful/recoverable paths still drop scratch values | `prompt-c6c2-allocation-overflow-smoke`, `prompt-c6c2-allocation-terminal-failure-smoke`, `prompt-c6c2-scratch-drop-smoke` |
| Pair publication ownership | C6f2 `src/prompt_evaluate.align`, Request 14 | evaluator-owned temporary and successfully published paths are the only removable paths; a competing final destination is a collision owned by another publisher, is never removed or reported as an orphan, and leaves `OUTPUT_WRITE` after clean owned cleanup | `prompt-evidence-pair-collision-ownership-smoke`, `prompt-evidence-pair-cleanup-ownership-smoke`, `prompt-evidence-pair-no-replace-smoke` |
| Invalid-evaluation evidence boundary | CLI contract and `src/prompt_evaluate.align` | request decode or result-output preflight failure writes no artifact; a decoded evidence-path `INVALID_INPUT` writes result-only with no sidecar; only an evaluation that establishes identity and reaches the paired-evidence boundary writes evidence; every status/output combination is explicit | `prompt-evaluate-invalid-input-output-smoke`, `prompt-evaluate-evidence-boundary-smoke` |
| Durable continuity state | `HANDOFF.md` and GitHub review records | HANDOFF records only branch/checkpoint, durable design decisions, blockers, verification, and next work; review IDs, finding lists, dispositions, and pending-review status remain in GitHub | `git diff --check`, Markdown fence checks, and the author-side HANDOFF durable-state assertion in the successor PR |

The successor must not apply a narrow line edit that leaves the corresponding old wording in another
section. Its matrix-to-diff pass must find every occurrence of allocator failure, pair cleanup,
evidence publication, and review-state continuity and reconcile the public contract, ledger,
closure rows, delivery prerequisites, and `HANDOFF.md` in one pass.

### 10.1c Evaluator runtime-containment closure

The C6-EVALUATION candidate review exposed one missed runtime-identity axis and two manifestations
of the same containment gap. This matrix reopens that axis before the implementation is revised.

| Reopened invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Source-verifier runtime identity | `PromptSourceVerifierPolicy`, evaluator, future gate locator | bind the exact helper and explicit CPython executable bytes in `CPYTHON:<interpreter_sha256>:<helper_sha256>`; validate policy, helper, interpreter, and Git digests before launch; never select an interpreter through a shebang or ambient path | evaluator source-policy runtime mismatch, interpreter tamper, helper tamper, and exact-argv fixtures in `prompt-evaluate-smoke`; gate equivalents remain owned by C6-MEASURED |
| Descendant ownership | evaluator, snapshot helper, source verifier, fixed adapter, their Git/task children | on the required Linux floor enable child-subreaper mode, start every content-bound trusted direct child in a PID-owned private session/group, enumerate and kill transitive or adopted descendants even after nested `setsid` — enumerating live entries under the §1.2 rule, which omits an entry only at `State: Z` with `Threads: 1` and still reports a zombie leader whose group holds a live worker thread — then apply the specified group signal, direct wait, bounded reap/absence proof, and cleanup-precedence sequence for timeout, output cap where the boundary captures output, nonzero/malformed failure, and successful-parent-with-live-descendant states | marker-bearing nested-session evaluator timeout and successful-parent fixtures plus source-verifier, snapshot-helper, and fixed-adapter nested-session fixtures prove marker, process-group, and descendant absence; their existing timeout/output owners retain the ordinary failure cases; Request 11 owns bounded outer capture while the qualified fresh-worker cgroup owns abrupt whole-tree cancellation |
| FILE_SET physical containment | source verifier | retain separate manifest and source-root descriptors, walk every raw byte component with no-follow directory-relative opens, and obtain type/mode/device/inode/bytes/digest from the same retained final descriptor; reject a symlink ancestor, special final, root escape, and manifest physical alias while accepting valid non-UTF-8 path bytes | source-verifier FILE_SET symlink-ancestor, non-UTF-8 acceptance, special-file, root-escape, manifest-alias, and digest fixtures plus same-descriptor pre/post identity checks |

The runtime change is intentionally structural rather than a nominal-label patch. The interpreter
digest is a declared policy field, the evaluation request supplies its absolute executable path,
and the future gate supplies the same path as an explicit build input while the checked-in locator
stores only its digest. No machine-specific absolute interpreter path enters persisted evidence or
the gate locator.

For every reopened process state, a failed descendant kill/direct-wait/absence proof yields
`CLEANUP_FAILED` even when timeout, output overflow, child status, or malformed output happened
first. A syntactically valid FILE_SET whose retained root, manifest, or entry cannot be opened or
matched is `UNVERIFIED`; malformed request field or absolute-path syntax remains the earlier
`INVALID_INPUT`.
`prompt-evaluate-smoke` covers representative ordered invalid-input pairs and proves that no later
snapshot or adapter side effect occurs; the focused helper owners cover the observation failures.

### 10.1d Final-review evaluator boundary closure

The final C6-EVALUATION review found that the first runtime-containment matrix still treated a
flat Unix process group as if it were a hierarchy and did not close the complete invalid-input and
wire-compatibility surface. This matrix reopens `evaluator-runtime-containment` before the repair;
each row must map to the final diff and owner evidence before publication.

| Reopened invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Outer deadline and descendant ownership | `src/prompt_evaluate.align`, Python evaluator, authenticated fresh worker | the Align wrapper arms no independent timeout that can expire before a later-started maximum-time task; Python gives each nested owner a cleanup/report margin, while capable gate execution places the complete evaluator tree in the already-qualified fresh-worker cgroup whose teardown is authoritative for abrupt outer cancellation | `prompt-evaluate-smoke` rejects an outer `timeout_ns` arm, asserts the nested deadline constants, and retains the bounded inner timeout/descendant fixtures; `fresh-worker-qualification` and the capable gate retain cgroup admission, kill, drain, and removal evidence |
| Exactly-once group cleanup | evaluator, snapshot helper, source verifier, fixed adapter | every child boundary records whether cleanup was attempted; after the first successful group-absence proof it propagates the saved diagnosis without entering a generic cleanup path or signaling the reusable PGID again | evaluator, snapshot-helper, and source-verifier successful-parent/live-descendant fixtures count exactly one cleanup attempt; the fixed-adapter owner retains its single-return cleanup paths |
| Pre-side-effect source validation | decoded request boundary and source-policy owner | validate identifier, digest, discriminator, option-pairing, repository-ID, absolute-root, manifest, interpreter, Git, and policy shapes before any helper, snapshot, or adapter child; only a syntactically valid source whose physical observation is unavailable becomes `UNVERIFIED` | evaluator null/missing FILE_SET manifest, relative root, invalid identity, non-ASCII/oversized ID, and ordered multi-invalid fixtures prove result-only `INVALID_INPUT` and no child marker |
| Final result size | bounded result persistence owner | stream the final digest preimage and persisted-size count in bounded chunks before testing the byte bound; if it exceeds the cap, clear the large graph, construct and stream-bind the compact `RESULT_TOO_LARGE` record, and encode/write only that final representation | compact-overflow owner covers bounded canonical chunks, rejects whole-preimage binding, covers an unbound record whose final digest crosses the cap, and proves the compact pair persists |
| Raw FILE_SET malformed bytes | source verifier | validate digest bytes without an implicit Unicode decode and reject embedded NUL in every raw path component as corpus observation failure; no `UnicodeDecodeError` or `ValueError` escapes the declared `VerificationError` path | FILE_SET non-ASCII digest and embedded-NUL fixtures return bounded `UNVERIFIED` results with no traceback or partial output |
| Schema-v1 compatibility evidence | Align codec owner plus canonical digest owner | for policy, evaluate request, and gate locator, decode exact golden bytes and compare semantics, re-encode exact bytes, reject missing/duplicate/reordered fields, cover both optional manifest states, and prove every helper/interpreter/runtime/Git mutation changes the canonical preimage/digest | `prompt-runtime-schema-v1` semantic/byte, invalid-field-order, optional-`Some`, and mutation goldens |
| Durable continuation state | `HANDOFF.md` | while findings or the capable gate remain open, the next action names repair, owner verification, preflight, and capable CI before merge; merge becomes the next action only after those gates pass | author-side HANDOFF consistency pass and `git diff --check` |

The outer timeout removal is deliberate, not an unbounded-child promise. Every admitted task and
helper retains its own fixed or declared finite deadline. The wrapper performs only request/output
ownership around that Python owner. Abrupt cancellation of the wrapper is authoritative only in
the capable fresh-worker profile, where the complete wrapper, evaluator, private child groups, and
session-breaking descendants inherit one cgroup leaf before execution and the worker proves the
leaf empty before removal. A supplementary direct CLI invocation does not claim cleanup after an
uncatchable host termination.

### 10.1e Re-review containment and allocation closure

The required complete re-review of the reopened runtime boundary found that parent clocks still
could expire while a nested session owner was cleaning up, the claimed cgroup evidence did not
execute C6-EVALUATION, and result binding still materialized the complete canonical preimage before
the size check. This matrix reopens `evaluator-runtime-containment` again; the repair is one
boundary redesign, not another set of isolated line fixes.

| Reopened invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Nested deadline hierarchy | evaluator, snapshot helper, source verifier, fixed adapter | every earlier-starting evaluator deadline exceeds the complete inner work deadline plus bounded kill/reap/absence-proof/report time; adapter outer time is the greater of task/provider-control time plus 5 seconds, snapshot outer time is at least 35 seconds, and evaluation-mode source verification uses 125 seconds | `prompt-evaluate-smoke` asserts the exact increasing constants and retains timeout plus live-descendant cleanup fixtures |
| Capable whole-tree evidence | `Makefile`, gate-topology oracle, authenticated fresh worker | add `c6-evaluation-adoption` to the capable-only ordered goals so final `make ci` actually executes the wrapper/evaluator/helper/adapter tree after cgroup admission; keep it absent from hosted checks | `gate-topology-check` canonical report/self-test plus final capable `make ci` |
| Pre-allocation result binding | Python evaluator canonical encoder and result persistence | emit canonical strings in bounded pieces, stream the digest preimage without an omitted-`None` graph clone, stream-count the final representation, and allocate/write only a representation already proved at or below the cap | compact-overflow owner compares canonical bytes, bounds every emitted chunk, fails if whole-preimage binding is called, and retains digest-expansion/compact-pair cases |
| Deterministic validation precedence | decoded request, source-policy owner, remaining artifact owners, workspace owner | after output preflight validate request bounds, then source-policy syntax/decode/identity and executable bindings, then remaining artifact identities, and only then physically resolve the workspace | a malformed source policy paired with an unavailable workspace returns the earlier `INVALID_SCHEMA` result and produces no child marker |
| Durable continuation state | `HANDOFF.md` | record the reopened matrix, repair owners, exact-head preflight, and capable CI as the remaining sequence; do not describe an already committed matrix as future work | author-side matrix-to-diff and HANDOFF consistency pass |

### 10.1f Final ownership-boundary closure

The complete review of the preceding redesign found one remaining ownership model split across
workspace admission, terminal cleanup, and pair publication. This matrix reopens
`evaluator-runtime-containment` for that common ownership axis. The repair must close the class as
one boundary before another candidate review.

| Reopened invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Per-invocation workspace admission | evaluator and snapshot helper | each pre/post snapshot permits only the current invocation's evaluator-created variant, rendered prompt, adapter request, and reserved measurement path; future and retired invocation names are absent, and successful removal immediately retires ownership so a later occupant is never removed as stale evaluator state | evaluator ownership owner proves the exact four-name allowlist, future-name rejection, removal-time retirement, and competitor preservation |
| Cleanup-before-terminal-pair | evaluator result/evidence producer | incorporate every valid snapshot, measurement, row, and attestation before removing its owned files; perform the complete owned-workspace cleanup before constructing and writing the terminal pair; a cleanup failure produces `ERROR`/`CLEANUP_FAILED` with the final valid prefix retained and is never converted into a nonzero helper exit that discards prepared evidence | evaluator cleanup owner forces a post-row removal failure, verifies the retained-prefix pair, and proves no later invocation starts |
| Publication ownership retirement | `prompt_artifact_io` pair publisher | after every successful temporary or final removal, clear that path's ownership before any later observation; a replacement arriving after removal is competitor-owned, yields `OUTPUT_WRITE`, and is neither reported as an orphan nor removed | Request 14 adoption asserts ownership flags retire at each successful removal and retains the concurrent collision/cleanup fixtures |
| Bounded FILE_SET decimal decode | source verifier | reject a decimal token longer than the maximum field's canonical width before integer conversion, then apply its numeric bound; Python runtime integer-digit limits never escape the declared `VerificationError` observation path | source-verifier FILE_SET owner covers overlong entry-count and path-length tokens as bounded `UNVERIFIED` results without traceback or partial output |
| Durable continuation state | `HANDOFF.md` | name this ownership-boundary repair, its owner checks, the required exact-head review, preflight, and capable CI as the remaining sequence; completed matrix and baseline-chain commits are historical evidence, not future actions | author-side matrix-to-diff and HANDOFF consistency pass |

### 10.1g Evaluator child/result boundary redesign

The exact-head review of the ownership-boundary repair found that file ownership, child-tree
ownership, bounded capture, and operational-failure classification still changed meaning between
the Align wrapper, evaluator, and nested Python owners. This reopens
`evaluator-runtime-containment` for the missing cross-process result boundary. The repair is one
capability boundary: splitting it would leave either an unprovable file owner or an adapter outcome
that the scorer could still misclassify. It may exceed 1,000 changed hand-written lines because the
same behavioral owners must exercise the producer, carrier, consumer, and cleanup transitions
together; separate producer and consumer changes would duplicate fixtures while leaving a dormant
and unsafe intermediate protocol.

| Reopened invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Complete descendant ownership | evaluator, fixed adapter, measurement adapter, snapshot helper, source verifier, gate validator; the coding runner owns the group/kill/absence sequence only, and the live-entry rule is deferred there under §1.2 | every Python child owner enables Linux child-subreaper mode, kills the private process group and every direct, transitive, or adopted descendant across nested sessions, reaps owned children, and proves group and descendant absence before returning; a nested `setsid` child cannot survive into the next invocation; the enumeration counts live entries only, and liveness is a property of the thread group: an entry is omitted only at `State: Z` with `Threads: 1`, so an adopted fully terminated orphan is never a containment failure while every live descendant — including a zombie leader whose group still holds a live worker thread — still is | evaluator, adapter, snapshot-helper, and source-verifier owners launch a marker-bearing nested-session descendant and prove bounded cleanup plus marker absence; each repaired scan additionally carries a paired regression in its `descendant_scan_rows` owner — `prompt-evaluate-smoke`, `test-prompt-fixed-adapter`, `test-prompt-snapshot-helper`, `test-prompt-source-verifier`, and `prompt-gate-validator-smoke`'s `validator` family — covering a fully terminated zombie child that must not be reported, a zombie thread-group leader with a live worker thread that must be, and a live session-leading child that must; and the fixed-adapter and measurement-adapter owners drive an adopted zombie end to end through a contained runner and a generation child |
| Bounded adapter diagnostics | fixed adapter | drain stdout and stderr concurrently into independently bounded prefixes; never call an unbounded `communicate`; cap, cap+1, simultaneous-stream, timeout, and descendant cleanup preserve the declared diagnostic limit | fixed-adapter owner measures retained byte counts and termination for both streams at the boundary |
| Operational runner outcome | coding runner and fixed adapter | the content-bound runner uses a distinct terminal code for an expected post-repair validation failure; launch, timeout, containment, cleanup, output, and internal runner failures produce `ERROR`/`ADAPTER`, never an ordinary `FAIL`/`TEST` row eligible for improvement scoring | parent expected-failure and candidate-pass rows remain scoreable; timeout, launch, internal-error, and unexpected exit fixtures terminate evaluation as adapter errors |
| Child output-file ownership | evaluator, snapshot helper, fixed adapter | the evaluator exclusively creates each snapshot/measurement result, records ownership immediately after successful creation, and passes its retained descriptor to the child; a create collision establishes no ownership, while every successful removal retires ownership before later observation | occupied snapshot/measurement names are preserved end to end; descriptor-backed success, failed-child cleanup, and late replacement cases prove exact ownership transitions |
| Cross-language evaluation result carrier | Python evaluator and `src/prompt_evaluate.align` | Python returns one bounded canonical result and optional evidence record through the captured process stream and never creates deterministic prepared files; the Align wrapper owns decode, verification, and exclusive final pair publication, so no file is cleaned without an owner established in that process | result-only invalid input, verified pair, cap/over-cap process output, malformed framing, occupied final output, and wrapper publication cleanup owners |
| Output-parent preflight | evaluator | before source verification, snapshots, or adapters, require each output's immediate parent to be an existing physical writable directory and the two targets to remain distinct and absent | missing, non-directory, symlinked, and unwritable immediate-parent fixtures prove `INVALID_PATH` precedence and no child marker |
| Invalid identifier result | evaluator result-only boundary | a decoded request with an invalid evaluation identifier returns `INVALID_INPUT`/`INVALID_ID` with `evaluation_id: null`; it never uses invalid text as a filesystem component and never suppresses the required result artifact | empty, non-ASCII, separator, dot, and oversized identifier cases persist and verify a result-only record with no evidence |
| Unavailable source envelope | evaluator source-verifier consumer | `UNAVAILABLE` accepts only the declared `GIT_UNAVAILABLE` code, bounded non-empty detail, all three `UNVERIFIED` reachability values, and all three absent observations; no malformed unavailable envelope contributes trusted identity | wrong code, verified reachability, present observation, empty/oversized error, and reordered/extra-field cases terminate as source-verifier failure |
| Publication failure transitions | Request 14 pair publisher | runtime owners force result-write and evidence-write failures after exclusive creation, plus a competitor replacement immediately after successful removal; owned paths retire on removal and a later occupant is never removed or reported | executable Request 14 adoption covers both `WriteFailed` arms and the late-competitor transition without source-text counting |
| Durable continuation state | `HANDOFF.md` | record the completed replacement baseline chain as history and name this reopened redesign, its owner checks, replacement baseline if a recorded input changes, exact-head review, preflight, and capable CI as remaining work | author-side matrix-to-diff and HANDOFF consistency pass |

### 10.1h Reviewed-source execution boundary redesign

The exact-head review of the §10.1g redesign found that the child and file owners were locally
correct but the outer evaluator still crossed its source-trust boundary too late. A request-selected
project could replace the Python evaluator, task helpers could run before source observation, and a
verified corpus identity did not prove membership of the bytes actually executed. The same missed
pre-side-effect axis also left semantic child output, tree/task bounds, cross-invocation drift,
environment policy, and result-only cleanup to later consumers. This reopens
`evaluator-runtime-containment` for one reviewed-source execution boundary. Splitting the trust,
validation, and ownership changes would leave an intermediate evaluator that either executes
unproven bytes or cannot produce the required terminal artifact after rejecting them.

| Reopened invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Outer evaluator identity | `src/prompt_evaluate.align`, `prompt_artifact_io`, Python evaluator | the compiled wrapper retains and hashes the no-follow evaluator source beneath `project_root`, compares it with the reviewed digest embedded in the wrapper, and launches only that admitted source through the fixed physical interpreter path; a replacement or digest mismatch fails before evaluator side effects | evaluator source replacement, digest mismatch, and admitted exact-source fixtures prove no marker or output for an unreviewed evaluator |
| Source-first task admission | evaluator, source verifier, corpus/task manifests | complete source observation before workspace preflight or any task helper; require each interpreter command to contain only its declared executable plus one file-bound reviewed helper, retain the fixed adapter/snapshot base helpers as corpus members, and require every file execution artifact to be a byte-equal member of the observed corpus source root, so an unrelated clean checkout cannot attest arbitrary project bytes | unrelated clean corpus, task-helper replacement, missing execution artifact, and preflight-marker fixtures prove rejection before task code; the valid split project/source fixture remains accepted |
| Task-repository Git isolation | snapshot helper | apply the same fixed no-pager/no-replace/no-graft/fsmonitor/hook/credential/diff overrides and bounded local/worktree-config rejection before task-repository Git identity or cleanliness observation | malicious `core.fsmonitor`, include, and ordinary inert clone-config fixtures prove non-execution and deterministic acceptance/rejection |
| TREE and task expansion bounds | evaluator and snapshot helper | reject more than 64 task paths before loading any task; stream tree enumeration with at most 128 retained entries and hash at most 1,073,741,824 aggregate file bytes before further I/O or allocation; static and additional lists retain their 64/32 bounds | exact/cap-plus-one task count, tree entry count, and aggregate-byte fixtures prove early bounded rejection |
| Semantic child-result validation | evaluator snapshot/measurement consumers | after canonical digest validation, require exact field order, discriminator-specific field shapes, scalar bounds, nested record identities, and task/variant/environment bindings before any field is indexed or retained; malformed helper output becomes a paired `SNAPSHOT_ERROR` or `ADAPTER_RESULT`, never a helper exit that suppresses the terminal artifact | digest-valid missing/extra/reordered/wrong-type snapshot and measurement records persist and verify the required noncomplete pair |
| Cross-invocation baseline drift | evaluator trace producer | the first valid pre-run observation fixes each task's artifact and environment baseline; every later before and after observation compares with that baseline and emits `PRECHECK_DRIFT` or `POSTCHECK_DRIFT` with `INPUT_DRIFT`/`ENVIRONMENT_DRIFT` before a changed invocation can be scored | stable-between-invocation input and environment mutations exercise both precheck error families; the existing within-invocation mutation retains postcheck coverage |
| Environment-policy validation | evaluator | before any child launch require ASCII environment names, exact `EXPLICIT_POLICY` source tags, ordered unique precedence, locale equality with `LANG`/`LC_ALL`, and the declared per-entry and aggregate executable-path bounds | invalid name, source, locale, order, and cap-plus-one executable-path fixtures prove result-only rejection and no child marker |
| Result-only publication ownership | `prompt_artifact_io`, Align wrapper | result-only output uses an exclusively created sibling temporary, bounded write/flush, no-replace finalization, exact owner retirement, and competitor-preserving cleanup; a partial write never leaves the final path | result-only result-write failure, final collision, cleanup failure, and late-competitor fixtures exercise runtime transitions |
| Durable continuation state | `HANDOFF.md` | record the §10.1g chain and its finding review as history, and name this reopened redesign, replacement baseline, required redesigned exact-head review, preflight, and capable CI as the remaining sequence | author-side matrix-to-diff and HANDOFF consistency pass |

### 10.1i Retained-source and complete-score redesign

The redesigned exact-head review of §10.1h found that byte equality was still separated from the
actual launch and source identity: the outer wrapper closed the evaluator source before reopening
its path, task helpers were compared with a mutable source tree without proving commit or FILE_SET
membership, and a non-root task `cwd` changed which helper argument Python opened. It also found
that the evaluator persisted the one fixture's expected aggregates instead of producing every valid
outcome under the shared scorer, while its snapshots neither covered every identity-bearing input
nor proved that a helper returned the exact requested observation. This reopens
`evaluator-runtime-containment` as `retained-source-complete-score`. Source admission, launch,
snapshot completeness, and scoring remain one capability because any intermediate split can either
execute bytes outside the admitted source identity or publish a comparison the verifier cannot
derive from the trace.

| Reopened invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Retained outer evaluator | Align wrapper and artifact I/O | read and hash one no-follow bounded evaluator owner, then execute those exact retained bytes without reopening the caller-writable pathname | replace the evaluator after admission and prove neither replacement marker nor replacement result executes; exact admitted bytes still run |
| Corpus membership, including task manifests | evaluator and source identity | for `GIT_COMMIT`, require every executed/static task file and task manifest to be an exact tracked blob at the verified commit; for `FILE_SET`, require its raw path, mode, and digest entry; compare the project bytes with that admitted identity, not merely a second mutable path | ignored/untracked Git helper, unlisted FILE_SET helper, unlisted task manifest, mode mismatch, and valid split-source fixtures |
| Effective helper path | evaluator command owner | interpreter commands contain exactly interpreter plus one project-relative helper; resolve that helper from the validated project root and pass its absolute retained-source path, independent of task `cwd` | non-root `cwd` with a conflicting relative helper proves only the admitted root helper runs |
| Complete shared scoring | Python trace producer and `prompt_score` verifier | derive task/corpus aggregates, ordered reasons, status, and gate eligibility for every valid row outcome and policy; the Align wrapper applies the shared scorer verifier before publication, so no fixture-only shortcut or unverified aggregate can persist | parent/candidate pass/fail, serious regression, no-improvement, completion improvement, time improvement, task limit, corpus limit, and tampered aggregate/reason cases |
| Complete static snapshot set | evaluator snapshot producer | automatically add every identity-bearing decoded input named in §4.7, including task manifest and `.align-revision`, to each pre/post snapshot in deterministic order without duplicate or overlapping paths | mutation of each automatic input between observations yields drift before scoring; exact ordered fixture remains accepted |
| Snapshot request/result binding | evaluator snapshot consumer | validate a `MATCH` or `MISMATCH` digest array against the exact ordered expanded static expectations plus additional files requested for that invocation; an empty, reordered, missing, extra, or unrelated array is malformed | digest-valid empty/reordered/missing/extra/unrelated child results produce the paired terminal error |
| Canonical FILE expectation | snapshot helper | compare a FILE expectation with the SHA-256 of its canonical mode/path/type/content record while retaining the raw file digest in `ArtifactDigest` | same bytes with changed mode/path identity mismatch; exact canonical FILE digest matches |
| Declared mismatch family | snapshot helper | classify repository, path, type, mode, content, tree, and workspace mismatches at the first failed check as `MISMATCH` with its exact code and observed prefix; reserve `ERROR` for environment, internal, and cleanup failure | every mismatch code and prefix is covered separately; internal and cleanup remain `ERROR` |
| Durable continuation state | `HANDOFF.md` | record the §10.1h reviewed chain as superseded evidence and name this reopened matrix, its replacement baseline, final preflight, capable gate, and publication sequence | author-side matrix-to-diff and HANDOFF consistency pass |

### 10.1j Inner retained execution and admission bounds

The final review of §10.1i found that its retained-source proof ended at the fixed adapter: that
adapter still reopened its runner, task manifest, and patch pathnames after admission. The same
review found three pre-side-effect/resource closure gaps: generic content-digest admission did not
prove complete artifact schemas, reviewed TREE enumeration preceded its declared caps, and
publication derived a temporary component longer than a valid requested output component. This
reopens `retained-source-complete-score` as `inner-retained-admission-bounds`. The four cells remain
one consumer capability because malformed or over-limit input must terminate before any retained
execution owner is launched, and successful execution must retain the exact bytes through bounded
publication.

| Reopened invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Complete pre-side-effect schema admission | evaluator artifact loader and per-kind validators | every decoded experiment, activation, corpus, task, acceptance, generation, provider, preflight, environment, prompt, and context artifact has exact ordered fields, discriminator/option types, and scalar bounds validated before source verification, snapshots, or adapters | digest-valid missing, extra, reordered, wrong-type, and out-of-bound fields produce result-only `INVALID_INPUT` and no child marker |
| Inner retained runner inputs | fixed adapter and coding runner boundary | open no-follow bounded owners for the runner, task manifest, and selected patch; verify their admitted SHA-256 identities, pass the task and patch by retained descriptors, and execute the exact retained runner bytes without reopening its pathname | replace and restore runner, task, and patch after child admission; no replacement marker/result executes and the admitted result remains stable |
| Reviewed TREE resource parity | evaluator reviewed-source enumeration | count TREE roots, directories, files, and aggregate regular-file bytes with the source-admission 128-entry and 2,097,152-byte caps before retaining or comparing the source set | exact entry/byte caps pass; cap plus one fails before source membership Git/FILE_SET work or any child marker |
| Bounded publication sibling | artifact I/O publication owner | derive the temporary sibling component from a fixed bounded prefix plus content-bound identifier/suffix, independent of the requested basename length, while preserving exclusive creation and cleanup ownership | 255-byte requested basename publishes successfully; occupied target, competing creator, special file, and reverse cleanup remain unchanged |
| Durable continuation state | `HANDOFF.md` | record the §10.1i chain and review as superseded evidence and name this reopened matrix, replacement baseline, final review, preflight, capable gate, and publication sequence | author-side matrix-to-diff and HANDOFF consistency pass |

### 10.1k Evaluation semantic closure

The replacement review of §10.1j found that admission and retention were complete but the evaluator
still did not consume five already-settled semantic cells: prompt-size policy, the complete automatic
snapshot set across invocations, the 64-entry static declaration cap, unavailable-source non-gate
execution, and containment-first failure precedence. This is a new P1 after a revised full-diff
review, so the matrix reopens `inner-retained-admission-bounds` as `evaluation-semantic-closure`
rather than continuing the local patch loop. The root-cause audit also includes bounded TREE
expansion in the evaluator's snapshot-result validator and the complete adapter-measurement state
machine, because both are consumers of the same settled limits and precedence contract.

| Reopened invariant | Contract owner | Required design decision | Exact regression |
| --- | --- | --- | --- |
| Prompt-size policy | evaluator render boundary and fixed adapter | reject an oversized parent as evaluation `ERROR`; return and validate an exact `POLICY_VIOLATION` measurement for an oversized candidate before runner execution | parent/candidate exact cap and cap plus one; oversized candidate leaves no runner marker and scores a serious `POLICY` regression |
| Complete invocation drift | evaluator precheck comparison | compare the complete ordered snapshot digest array, including automatic and invocation-owned additional files, against the first invocation | mutate each automatic input between a prior postcheck and the next precheck; every mutation yields `PRECHECK_DRIFT` before adapter execution |
| Snapshot declaration/resource parity | evaluator input and child-result validators plus snapshot helper | admit at most 64 static expectations and 32 additional files before any child; enumerate expected TREE paths with the remaining 128-entry and 1,073,741,824-byte snapshot caps while walking, not after unbounded collection | exact static/additional/TREE caps pass; each cap plus one returns result-only `INVALID_INPUT` or a malformed-child terminal result without a child marker |
| Unavailable-source non-gate path | verifier trust and task-source membership | preserve physical byte/mode comparison whenever an unverified corpus root remains readable, but when the root is absent or unreadable preserve `UNVERIFIED` trust and execute the already-admitted project task boundary as a non-gate comparison | present-but-mismatched source still rejects unreviewed code; absent and unreadable corpus roots retain `UNVERIFIED`, produce a complete non-gate pair, and never become `SNAPSHOT_ERROR` |
| Complete measurement state machine | fixed adapter producer and evaluator child-result validator | enforce all `PASS`, `FAIL`, `POLICY_VIOLATION`, and `ERROR` field combinations; containment precedes cleanup, which precedes adapter/stage error | parameterized valid states plus contradictory status/failure/stage/flag/time/policy mutations; simultaneous containment and cleanup failure persists `CONTAINMENT` |
| Durable continuation state | `HANDOFF.md` | record the §10.1j chain and review as superseded evidence and name this reopened matrix, replacement baseline, preflight, capable gate, and publication sequence | author-side matrix-to-diff and HANDOFF consistency pass |

Applicability decisions:

| Dimension | Decision |
| --- | --- |
| Wire/API schema | applicable; JSON schema version 1 records above |
| Text/encoding/NUL | applicable; UTF-8 JSON, Request 7 escape symmetry, raw tree-byte encoding, and pre-side-effect NUL rejection above |
| Persistent identity/version | applicable; content-bound immutable candidates, evaluations, and activations |
| Ownership/cleanup | applicable; module and task-adapter ownership defined in sections 6 and 9 |
| Allocation | applicable; bounded readers, Request 5 response cap, Request 11 process cap, Requests 12/13 result persistence, recursive record-array prerequisites, explicit text clones, and owned-result cleanup are explicit |
| External process/network | applicable; fixed helper/adapter commands, TaskAdapterRequest, EnvironmentPolicy/env-clear contract, provider controls, timeouts, cap-aware output, and validation-before-call order are explicit |
| Public CLI/build inputs | applicable; exact JSON command paths, explicit adapter request, environment policy, provider/helper/task inputs, and no unnamed ambient configuration |
| Global state | no implicit global active prompt; explicit activation input only |
| Concurrency | §1.2's complete 4x4 operation matrix; disjoint resources may run in separate processes, shared outputs/workspaces are rejected or explicitly unsupported before side effects, and adapter calls within one evaluation are serialized |
| Compatibility | Ubuntu 24.04 x86_64, Git 2.45.0, Rust 1.96.0, LLVM 22, CPython 3.12, GNU Make 4.3, and the exact `.align-revision` release; newer environments are supplementary |
| Commit reachability | exact clean align-llm, Align, and corpus SHAs; normal merge preserves required ancestors; CI verifies head/base-tip/merge-base and tested integration tree |
| Producer ownership | explicit EnvironmentIdentity producer table in §1.2; no hidden reflection or artifact/source inference |
| Syntax examples | design notation only until C6a1's declaration/positional-call fixture and pinned `alignc check`; no proposed API is consumed earlier |
| Generic/interface/per-unit compilation | applicable to every declared record and Request 10 recursive graph; Align adoption owns `prompt-record-graph-compile`, interface serialization, whole-program, per-unit, and cache-identity fixtures |
| Detail/discriminator/verification/option Cartesian product | applicable; C6a1/C6a2 own the §1.2 fixture over `None`/`Some`, empty/non-empty, parent/candidate, all statuses, verification states, and unavailable values |
| Performance | provider quality uses time to passing patch; lifecycle overhead is secondary and not a gate claim |
| Security/credentials | API-key values are environment-only, passed only to the allowlisted adapter child, and must not enter artifacts or diagnostics |

## 11. Capability waves and acceptance ownership

The labels C6a0-C6g2 below remain stable references for dependencies, closure-matrix ownership, and
focused acceptance. They are not a required sequence of branches or pull requests. A capability
branch may contain several labeled checkpoints as scoped commits and must include the production
consumer that makes its new foundations useful. A line-count estimate is planning information only;
large coherent behavior is made reviewable with commit structure, owner tests, and risk-partitioned
review rather than helper-only pull requests.

1. **C6-LIFECYCLE — offline prompt lifecycle.** Adopt the merged Align prerequisites needed by this
   consumer in one pin wave, then complete C6a1/C6a2 artifact declarations and codecs, C6b artifact
   binding and failure-memory selection, C6c2 verification using the merged C6c1/C6c1p surface,
   and C6d1/C6d2 activation and CLI.
   Requests 7, 8, 10, 12, 13, and 15 retain their individual lifecycle and acceptance evidence. The
   capability is not complete until a deterministic caller can load a candidate from declared
   inputs, render and score it, validate its result, persist it, accept it, and roll it back. The
   already merged C6b renderer, C6c1 scorer, and C6c1p prefix validator are foundations consumed
   here, not separate delivery milestones. The pure checkpoints use constructed values until their
   required codec surface is adopted; no code targets a proposed Align API.
2. **C6-EVALUATION — deterministic contained comparison.** Complete C6f1 and C6f2 together with the
   fixed adapter, workspace/source preflight, input snapshots, process and cleanup ownership,
   alternating paired execution, result/evidence publication, and deterministic corpus. Adopt the
   needed Requests 8, 10, 11, 12, 13, and 14 in the same consumer prerequisite wave when they are
   merged. This capability may proceed without C6e because its fixed adapter does not call a model
   provider. It is complete only when the lifecycle consumes an evaluator-produced artifact through
   the existing contained task runner.
   This wave deliberately exceeds roughly 1,000 hand-written lines because its trusted helpers,
   retained execution trace, pair publication, and lifecycle consumer form one strict proof chain.
   Splitting any helper from the evaluator would expose a dormant security boundary and duplicate
   the source, process, snapshot, and cleanup fixtures without leaving a useful stable consumer.
3. **C6-MEASURED — provider proposal and measured acceptance.** Complete C6e, C6g1, and C6g2.
   Request 5 and the shared persistence/process prerequisites are adopted; Request 2's
   plaintext/TLS timeout adoption is this wave's own named `c6e-request2-adoption` checkpoint and
   must pass before any real provider claim. Deliver the
   bounded provider proposal, declared decoding, secret redaction, real consumer, frozen corpus and
   policies, real parent/candidate comparison, checked-in gate evidence, accept decision, and linked
   rollback. This is the only wave that claims provider quality or prompt improvement, so its pull
   request owns the reproducible baseline and time-to-passing-patch measurement.

Within each wave, every existing ledger row and closure-matrix cell still needs its exact owner and
passing focused regression before review. Core functional checks join the aggregate only when they
protect ordinary integration for every future change. Security, resource, race, mutation, stress,
platform, and benchmark qualification remain named owner commands unless their contract explicitly
requires universal execution. Run the full aggregate once at the completed integration/adoption
gate, not after each labeled checkpoint.

If implementation discovers a missing Align language or standard-library capability, record it
through `docs/align-requests.md` and pause only the dependent capability. Continue an independent
wave when it does not pre-commit the blocked design. Do not replace immutable artifacts with a
fragile local compatibility layer.

### 11.1 C6c1 public-contract ledger

C6c1 is a merged scoring-kernel checkpoint. It deliberately does
not declare the persisted C6 artifact records owned by C6a1/C6a2. Its contract is complete here so
the implementation does not discover row semantics through test fixtures or a later decoded-record
verifier.

The module is `prompt_score` and exposes exactly these scalar or borrowed, non-owning types:

```text
ScoreVariant: PARENT | CANDIDATE
ScoreStatus: PASS | FAIL | POLICY_VIOLATION | ERROR
ScoreFailureKind: NONE | PROVIDER | PATCH | BUILD | TEST | POLICY | CLEANUP | CONTAINMENT | ADAPTER
ScoreStage: PASS | FAIL | NOT_RUN | ERROR

ScoreRow:
  task_ordinal: i64                 // zero-based position in the caller's corpus order
  sample_index: i64                 // one-based sample number
  variant: ScoreVariant
  status: ScoreStatus
  failure_kind: ScoreFailureKind
  build_status: ScoreStage
  test_status: ScoreStage
  repair_loop_count: i64
  unrelated_diff_count: i64
  patch_size_bytes: i64
  public_api_change_count: i64
  policy_violation_count: i64
  cleanup_passed: bool
  containment_passed: bool
  adapter_error: bool
  prompt_preparation_ns: i64
  generation_to_passing_patch_ns: Option<i64>
  time_to_passing_patch_ns: Option<i64>
  benchmark_regression_ppm: Option<i64>

ScoreTaskLimit:
  maximum_unrelated_diff_count: i64
  maximum_patch_size_bytes: i64
  maximum_public_api_change_count: i64
  maximum_repair_loops: i64
  maximum_benchmark_regression_ppm: Option<i64>

ScorePolicyLimit:
  maximum_time_regression_ppm: i64
  maximum_repair_loop_regression_count: i64
```

The exact public function is:

```text
pub fn aggregate(
  rows: slice<ScoreRow>,
  task_limits: slice<ScoreTaskLimit>,
  policy_limits: ScorePolicyLimit,
  sample_count: i64,
  out task_ordinal: slice<i64>,
  out task_parent_pass_count: slice<i64>,
  out task_candidate_pass_count: slice<i64>,
  out task_parent_repair_loop_count: slice<i64>,
  out task_candidate_repair_loop_count: slice<i64>,
  out task_paired_pass_count: slice<i64>,
  out task_parent_median_present: slice<bool>,
  out task_parent_median_ns: slice<i64>,
  out task_candidate_median_present: slice<bool>,
  out task_candidate_median_ns: slice<i64>,
  out task_time_improvement_present: slice<bool>,
  out task_time_improvement_ppm: slice<i64>,
  out task_time_regression_present: slice<bool>,
  out task_time_regression_ppm: slice<i64>,
  out reason_task_ordinal: slice<i64>,
  out reason_sample_index: slice<i64>,
  out reason_code: slice<i64>,
  out reason_parent_value_kind: slice<i64>,
  out reason_parent_value_number: slice<i64>,
  out reason_candidate_value_kind: slice<i64>,
  out reason_candidate_value_number: slice<i64>,
  out reason_limit_kind: slice<i64>,
  out reason_limit_number: slice<i64>,
) -> ScoreResult
```

`task_limits` is ordered by `task_ordinal`, and `policy_limits` carries the global acceptance
thresholds for time and corpus repair-loop regressions. The caller owns every input and output array
and keeps them live for the call; C6c1 retains no view and performs no filesystem, process, network,
or global-state operation. The output slices are caller-provided primitive columns, not hidden
allocation. Every `task_*` output column must have length at least the task count, and every
`reason_*` output column must have length at least the actual reason count. The columns reconstruct
the logical `ScoreTaskAggregate` and `ScoreReason` records below in their shared ordinal order.
`*_present` is false when the corresponding logical `Option<i64>` is `None`; its paired numeric
column is zero in that case. `reason_*_value_kind` uses `NONE = 0`, `PASS = 1`, `FAIL = 2`,
`POLICY_VIOLATION = 3`, `ERROR = 4`, and `NUMBER = 5`; its paired numeric column is meaningful only
for `NUMBER`. `reason_code` uses the `ScoreReasonCode` order below as zero-based ordinals. Validation
and the complete reason-count pass happen before any output column is written. An insufficient
column returns `OUTPUT_TOO_SMALL` with the required count and leaves every output column untouched.
The checked pass rejects a reason count above `R_max(task_limits.len(), sample_count)`; callers may
allocate each reason column to that exact declared maximum, and no larger or unbounded reason buffer
is part of the contract.
This explicit scalar-column topology keeps C6c1 independent of Request 8/10 runtime-sized
record-array construction and of the pinned compiler's unsupported struct-element output stores.

The complete-row aggregate is intentionally not the prefix validator. C6c1p, the enabling slice on
this module, exposes the following non-owning validation path for an incomplete evaluation:

```text
ScorePrefixStatus: VALID_PREFIX | TERMINAL_ERROR | INVALID_INPUT

ScorePrefixResult:
  status
  error_code                   // 0 valid; 1 invalid plan; 2 invalid row/order
  error_index                 // first invalid row, or -1
  row_count
  expected_row_count

pub fn validate_prefix(
  rows: slice<ScoreRow>,
  task_limits: slice<ScoreTaskLimit>,
  sample_count: i64,
) -> ScorePrefixResult
```

`validate_prefix` accepts zero through the complete expected row count, checks the same task-limit,
sample, alternating-order, bounds, and row-state rules as `aggregate`, and performs no aggregation
or output-column write. A structurally valid `ScoreRow.status: ERROR` is permitted only as the last
row; it returns `TERMINAL_ERROR` so the caller can bind a retained terminal measurement to the
evaluation error. A prefix that ends before such a row returns `VALID_PREFIX`. A row after an error,
an out-of-order row, a malformed row, or a row count above the complete expected count returns
`INVALID_INPUT` at the first failing index. The function borrows all inputs, retains no view, and
returns one Copy result without filesystem, process, network, or global-state work. C6c2 calls this
path for `ERROR`/paired noncomplete records and calls `aggregate` only after a complete prefix has
the exact expected row count and no terminal error.

The result and aggregate records are plain Copy values:

```text
ScoreTaskAggregate:
  task_ordinal
  parent_pass_count
  candidate_pass_count
  parent_repair_loop_count
  candidate_repair_loop_count
  paired_pass_count
  parent_paired_median_time_ns: Option<i64>
  candidate_paired_median_time_ns: Option<i64>
  time_improvement_ppm: Option<i64>
  time_regression_ppm: Option<i64>

ScoreCorpusAggregate:
  task_count
  sample_count
  parent_pass_count
  candidate_pass_count
  parent_repair_loop_count
  candidate_repair_loop_count
  paired_pass_count
  parent_paired_median_time_ns: Option<i64>
  candidate_paired_median_time_ns: Option<i64>
  completion_gain_count
  time_improvement_ppm: Option<i64>
  time_regression_ppm: Option<i64>
  repair_loop_regression_count

ScoreValue: NONE | PASS | FAIL | POLICY_VIOLATION | ERROR | NUMBER(i64)
ScoreReasonCode: PASS_TO_FAIL | BUILD | TEST | POLICY | UNRELATED_DIFF | PUBLIC_API |
  PATCH_SIZE | REPAIR_LOOPS | BENCHMARK | TIME
ScoreReason:
  task_ordinal
  sample_index
  code: ScoreReasonCode
  parent_value: ScoreValue
  candidate_value: ScoreValue
  limit: ScoreValue

ScoreOutputKind: NONE | TASK_AGGREGATES | REASONS
ScoreResultStatus: COMPLETE | EVALUATION_ERROR | INVALID_INPUT | OUTPUT_TOO_SMALL
ScoreResult:
  status: ScoreResultStatus
  error_code                   // 0 complete; 1 invalid plan; 2 invalid row; 3 evaluation error;
                                // 4 task-output capacity; 5 reason-output capacity
  error_index                  // row index or -1 when not row-specific
  reason_count
  output_kind: ScoreOutputKind
  required_output_count        // zero unless OUTPUT_TOO_SMALL; capacity for output_kind
  corpus: ScoreCorpusAggregate
```

`ScoreValue` is an internal scalar representation of the canonical value labels in section 8;
C6c2 owns mapping it to persisted task IDs and strings. C6c1 does not claim that these records are
the C6 JSON schema, does not calculate content digests, and does not validate artifact references,
environment identity, provider identity, or document lineage.

The deterministic validation order is:

1. `task_limits.len()` is 1 through 64, `sample_count` is 2 through 16, and the expected row
   count `task_count * sample_count * 2` fits and equals `rows.len()`.
2. Every task output column capacity is checked before any row or output mutation.
3. Every task limit is non-negative and within its corresponding C6 bound; an absent benchmark
   limit has value zero, while a present limit is 0 through 1,000,000 ppm. The policy time limit is
   0 through 1,000,000 ppm and the policy repair-loop limit is 0 through 65,536.
4. Rows are checked in exact corpus order: task ordinals are zero-based, samples are one-based,
   each pair has the expected alternating order (odd sample parent/candidate, even sample
   candidate/parent), and every row state follows the §5.2 state machine.
5. A structurally valid `ERROR` row returns `EVALUATION_ERROR` at its row index without scoring or
   writing output. A malformed combination returns `INVALID_INPUT` at its first row index.
6. The pure analysis pass computes the complete reason count with
   `R_max = 9 * task_count * sample_count + task_count + 2` using checked arithmetic, rejects an
   overflow or count above `R_max`, and checks the reason output capacity.
7. Only then are task output columns and reason output columns written in
   corpus/task/sample/code order, followed by the corpus aggregate in the returned value.

Row validation enforces the full C6c1 state machine: non-negative bounded counters; prompt
preparation in `[0, 7_200_000_000_000]`; checked positive passing generation and total time with
`time_to_passing_patch_ns = prompt_preparation_ns + generation_to_passing_patch_ns`; `PASS` as
`NONE/PASS/PASS`, clean containment and cleanup, and zero policy violations; `FAIL` with only
`PROVIDER`, `PATCH`, `BUILD`, or `TEST` and the exact stage combinations; `POLICY_VIOLATION` with
`POLICY`, positive policy count, clean containment and cleanup, and only `NOT_RUN/NOT_RUN`,
`PASS/NOT_RUN`, or `PASS/PASS`; and `ERROR` with no passing-time fields and deterministic
`CONTAINMENT` then `CLEANUP` then `ADAPTER` precedence. `adapter_error` is false on containment
or cleanup errors and is required only for an otherwise clean `ADAPTER` row; a stage `ERROR` is
independently sufficient. Non-error rows require `adapter_error: false`, valid cleanup/containment,
and no `ERROR` stage. A benchmark is present only
for a passing row of a task that declares a benchmark limit; all other rows and tasks without a
limit use `None`.

Rows are paired by their validated order. Pass counts count `PASS` rows, repair totals sum every
structurally valid row, and paired timing medians use only samples where both variants pass. Median
selection is ascending with zero-based `n / 2` for odd `n` and the floor of the two middle values
for even `n`; no allocation or hidden sort is used. Integer ppm uses the exact §8 formulas and
returns `None` when either median is absent. Completion gain is candidate pass count minus parent
pass count, and corpus repair-loop regression is `max(0, candidate total - parent total)`.

The reason pass emits every applicable reason, without deduplication or truncation, in the schema's
code order. It covers paired pass-to-fail, parent build/test pass to candidate non-pass, every
candidate policy violation, each candidate task-limit breach, task and corpus time regression above
`policy_limits.maximum_time_regression_ppm`, corpus repair-loop regression above
`policy_limits.maximum_repair_loop_regression_count`, and candidate benchmark regression above its
task limit. Benchmark reasons use only passing candidate rows, because non-passing rows have no
benchmark measurement. Task-level time reasons use the task ordinal and sample zero; corpus-only
reasons use task ordinal `-1` and sample zero. C6c2 maps these ordinals to canonical task IDs and
materializes `RegressionReason` records.

The C6c1 closure matrix is:

| Applicable path | Owner | Exact acceptance evidence |
| --- | --- | --- |
| construction and successful aggregation | `src/prompt_score.align` | `prompt-score-smoke` all-pass and mixed-pass fixtures; exact task/corpus counts, medians, and ppm |
| row state validation | `src/prompt_score.align` | `prompt-score-smoke` PASS/FAIL/POLICY/ERROR state matrix and every stage combination |
| malformed/order/bounds input | `src/prompt_score.align` | invalid first-row index, duplicate/missing/order, limit, time, count, and overflow fixtures |
| reason completeness/order/capacity | `src/prompt_score.align` | multi-reason pair plus task/corpus TIME and REPAIR_LOOPS output in canonical code order; exact `R_max` bound, checked arithmetic, and `OUTPUT_TOO_SMALL` sentinel fixtures |
| output ownership and early exit | `src/prompt_score.align` | undersized scalar-column output and invalid-input fixtures prove every caller buffer remains sentinel-filled |
| incomplete-prefix validation | `src/prompt_score.align` in C6c1p | empty, strict-prefix, terminal-`ERROR`, out-of-order, post-error, complete-prefix, invalid task-limit plan, invalid-plan sentinel, and checked-count/overflow fixtures through `validate_prefix` |
| cleanup/allocation | N/A: pure borrowed scalar kernel | `scripts/check-format`, `make check`, and no owned fields or retained views in the declared types |
| public topology | `Makefile`, topology oracle, smoke script | `make gate-topology-check`, `make prompt-score-smoke`, `make prompt-score-prefix-smoke`, and refreshed baseline sequence when the hosted list changes |

This ledger is intentionally limited to the C6c1 kernel. Artifact decoding, whole-document
error-prefix retention, and runtime-sized result construction remain named owners in C6a1/C6a2/C6f2
and are not silently pulled into this slice. C6c1p owns only the public borrowed prefix validator;
it does not persist artifacts or duplicate C6c2's identity checks. C6c2 may map already-decoded task
ordinals to their declared task IDs, but it does not move or persist the artifact records.

### 11.1a C6c1p public-contract ledger

C6c1p is a merged checkpoint on the C6c1 scorer. It adds only `validate_prefix`; it does
not change the complete-row `aggregate` contract, persisted schemas, JSON boundary, or evaluator
ownership. C6c2 consumes this merged surface. If future capability work changes the prefix boundary,
its owner checks must pass on that capability branch; it does not require a separate pull request.

The exact C6c1p surface is the `ScorePrefixStatus`, `ScorePrefixResult`, and
`validate_prefix` declaration above. Its result fields have these values on every return:

- `row_count` is always the supplied `rows.len()`.
- On a valid plan, `expected_row_count` is the checked value
  `task_limits.len() * sample_count * 2`, which is at most 2,048. On an invalid plan,
  `expected_row_count` is `-1`; no multiplication is attempted.
- `error_index` is `-1` for `VALID_PREFIX`, `TERMINAL_ERROR`, and invalid-plan returns. For an
  invalid row/order return it is the zero-based first failing row index; when `rows.len()` exceeds
  the valid-plan expected count, that index is `expected_row_count`, the first extra row.
- `error_code` is `0` for `VALID_PREFIX` and `TERMINAL_ERROR`, `1` for an invalid plan, and `2`
  for an invalid row or order.

Its validation order is:

1. Validate task-limit count, sample count, and every task-limit field before multiplication. If
   any plan field is invalid, return `INVALID_INPUT` with `error_code: 1`, `error_index: -1`,
   `row_count: rows.len()`, and `expected_row_count: -1`; no expected-count multiplication is
   attempted. Otherwise compute the bounded expected count and validate that `rows.len()` is no
   greater than it.
2. Validate every row in execution order using the merged C6c1 row-state rules.
3. A structurally valid `ERROR` row is terminal only when it is the final supplied row; a later row
   returns `INVALID_INPUT` at that later row's index. A prefix with no terminal row returns
   `VALID_PREFIX`.
4. Return the first invalid index without output mutation or any side effect.

The C6c1p acceptance gate is `prompt-score-prefix-smoke` plus the existing `prompt-score-smoke`,
`make check`, format/static checks, per-unit and whole-program compilation, and the source/consumer
allocation-parity fixture. A valid prefix never produces aggregates or reasons; C6c2 alone decides
whether the surrounding persisted result is complete, incomplete, or malformed.

### 11.2 C6c2 public-contract ledger

C6c2 is the pure decoded evaluation verifier. It is not a JSON reader or a file-backed document
validator. C6a1/C6a2 provide the declared records and canonical-content validation, and C6c1p
provides the public prefix validator. Requests 7, 8, 10, 12, 13, 16, and 17 are shipped and adopted
at the pinned Align revision. Their named owners are `c6c2-request8-adoption`,
`c6c2-request10-adoption`, `c6-borrowed-option-adoption`, and
`c6-borrowed-array-adoption`. No C6c2 fixture is an escape-free JSON workaround; the verifier
fixture constructs declared values directly after the codec gate.

The exact public surface is:

```text
PromptScoreStatus: IMPROVED_ELIGIBLE | COMPLETE_INELIGIBLE | NONCOMPLETE_ERROR

pub fn verify_result(
  borrow result: PromptEvaluationResult,
  borrow evidence: PromptEvaluationEvidence,
) -> Result<PromptScoreStatus, Error>
```

The caller owns both decoded records and keeps every borrowed string and nested array live for the
call. `verify_result` borrows, does not move, replace, null, mutate, or retain either input. It
returns one Copy status or `Err(Error.Invalid)` and performs no filesystem, JSON, canonical-encoding,
process, network, global-state, or repository-reachability operation. It constructs one bounded
temporary `array<ScoreRow>` and verifier-owned temporary
primitive output columns passed to C6c1's `aggregate` call. For an incomplete result it passes the
same borrowed scratch rows to C6c1p's `validate_prefix` and does not allocate aggregate/reason
columns. The row scratch is bounded by the declared maximum of 2,048 retained task/sample/variant
rows; task columns are bounded by 64 tasks, and every primitive reason column is allocated with
capacity `R_max = 9 * task_count * sample_count + task_count + 2`, at most 9,282, using the same
checked arithmetic as C6c1. A checked-capacity overflow returns `Err(Error.Invalid)` before invoking
C6c1 or writing output. A runtime allocator failure while constructing a bounded scratch array or
column follows the declared Request 8/10 terminal allocation policy: the process exits nonzero with
no recoverable result and no cleanup-after-abort promise. C6c2 never truncates reasons or retries
with an unbounded or fixed-size substitute. On every recoverable return and successful completion,
normally constructed scratch values are released before return and no scratch value becomes persisted
state.

The verifier's deterministic validation order is:

1. Validate schema version, artifact kinds, required scalar labels, digest shape, option/discriminator
   combinations, and status-specific error-code families in declaration order. Complete statuses
   require `error_code: NONE` and empty `error`; `INVALID_INPUT` and `ERROR` require their own
   allowed non-`NONE` families. `trace_failure` must be `None` for every status except
   `ERROR`/`RESULT_TOO_LARGE`; the compact status requires `trace_failure: Some` and the exact
   compact error family.
2. Validate the result's evaluation ID, scope, corpus revision, provider identity, task order,
   parent/candidate variants, and the `experiment`/`experiment_artifact` and
   `parent_activation`/`parent_activation_artifact` reference pairs. Embedded IDs, kinds, and
   digests must equal their references; no path is used as identity.
3. Validate the persisted execution trace before scoring. The workspace-preflight request/result
   must have the result's evaluation ID, project root, workspace path, and physical paths; a
   complete result requires `SAFE` and its producer-owned environment probe. `snapshot_requests`
   and `snapshot_results` must be content-deduplicated, task-identified, and retained in declared
   corpus order; every attestation reference must resolve to exactly one embedded record. Each
   task has exactly one matching `TaskInputSnapshot`, with the task-manifest digest, artifact
   closure, and baseline environment identity bound to that task. Attestations must follow the
   corpus/task/sample schedule and the odd/even variant order, and their task/sample/variant
   identities must equal the corresponding row. `COMPLETE` requires two `MATCH` snapshots, equal
   ordered artifact digests, equal before/after input snapshots, and the common result environment.
   `PRECHECK_FAILED`, `PRECHECK_DRIFT`, and `ADAPTER_FAILED` have no after fields or row;
   `POSTCHECK_FAILED` and `POSTCHECK_DRIFT` have the required before/after fields but no row.
   `PRECHECK_DRIFT` and `POSTCHECK_DRIFT` retain the differing `MATCH` observation and input
   snapshot, while the ordinary failed states retain only the fields in their state table. A failed
   attestation is terminal: no later attestation or row is permitted.
   For `ERROR`, rows are exactly the longest valid execution-order prefix; a valid `ERROR`
   measurement with an unchanged complete attestation is the final retained row, and an
   adapter/precheck/precheck-drift/postcheck/postcheck-drift/cleanup failure is the first terminal
   event. A cleanup failure after
   a valid non-`ERROR` measurement and complete attestation retains that final row, binds
   `CLEANUP_FAILED`, and is verified as `VALID_PREFIX`; cleanup before a valid row retains none.
   `RESULT_TOO_LARGE` is the sole compact-result exception: require `trace_failure: Some`, the
   declared `evaluation_id`/scope/error shape, `gate_eligible: false`, no environment, every large
   option `None`, and empty `tasks`, `snapshot_requests`, `snapshot_results`, `input_snapshots`,
   `snapshot_attestations`, `rows`, `task_aggregates`, and `serious_regression_reasons`. Validate
   only the bounded counter and digest fields of the compact envelope;
   the discarded trace is not replayable.
4. Validate the evidence artifact kind, evaluation ID, `evaluation_result_sha256`, trust identity
   fields, the three reachability labels, and the three observed-identity options. The result content
   digest must equal the evidence's result digest. For every source, `VERIFIED` requires the observed
   option to be `Some` and equal to its expected identity; `UNVERIFIED` permits `None` or a differing
   observed value, while an unavailable helper result requires all three observed options to be
   `None`. For a complete result, `expected_align_llm_commit` must equal
   `EnvironmentIdentity.core.align_llm_commit`, and expected Align revision must equal both that
   environment and scope. For a noncomplete result with an environment, the same equalities are
   checked; without an environment, preserve the source states captured before the failure, skip
   only the unavailable environment equalities, and return only `NONCOMPLETE_ERROR`. Expected corpus
   kind, repository ID, and source digest must equal the complete `CorpusRevision` in every paired
   result.
5. Compare `expected_inputs` to `result.rows` in retained execution order. Require exactly one
   matching task/sample/variant entry per row, no duplicate or extra identity, and equality of every
   rendered-prompt, context-source, generation-request, adapter-request, and provider-request
   digest. Missing, wrong, duplicate, or out-of-order evidence is invalid. The compact
   `RESULT_TOO_LARGE` exception requires both arrays to be empty and does not reinterpret the
   overflow digest as an input digest.
6. Map the validated rows and task limits to C6c1p's `validate_prefix`. For a complete result, require
   `VALID_PREFIX`, the exact expected row count, and no terminal `ERROR`, then call C6c1 `aggregate`
   and recompute task aggregates, the corpus aggregate, every regression reason, and their canonical
   order; compare every persisted aggregate/reason field. For a paired `ERROR` result, require an
   empty aggregate/reason set and use only the prefix result: `VALID_PREFIX` is allowed when the
   terminal event produced no retained row or when `CLEANUP_FAILED` occurred after a valid
   non-`ERROR` retained row, while `TERMINAL_ERROR` is required when the final retained row has
   status `ERROR`. For a paired `INVALID_INPUT`, require empty rows, aggregates, and reasons and do
   not invoke either C6c1 path. For `RESULT_TOO_LARGE`, return `NONCOMPLETE_ERROR` after the
   compact-envelope checks without invoking either scorer. A status-only or aggregate-only tamper is
   invalid.
7. Recompute comparison status from the policy and the recomputed values. Preserve a strict but
   non-gate `IMPROVED` result as a valid complete comparison; it returns
   `COMPLETE_INELIGIBLE`, not `NONCOMPLETE_ERROR`. A valid `NO_IMPROVEMENT` or
   `SERIOUS_REGRESSION` likewise returns `COMPLETE_INELIGIBLE`.
8. Recompute gate eligibility from the complete records, provider kind, CPU availability, seed
   attestations, exact identities, and all three reachability states. Compare the persisted boolean;
   a mismatch is invalid. Return `IMPROVED_ELIGIBLE` only for a valid `IMPROVED` result with zero
   serious regressions and every gate condition true.

After the structural and semantic checks, valid paired `INVALID_INPUT` or `ERROR` records return
`NONCOMPLETE_ERROR`. They never become a scoreable regression and never reach activation. A
malformed record, contradictory status, invalid evidence, mismatched digest, or any failure of the
ordered checks returns `Err(Error.Invalid)`; the verifier does not manufacture or rewrite a result
error code.

The C6c2 closure matrix is:

| Applicable path | Owner | Exact acceptance evidence |
| --- | --- | --- |
| borrowed input formation and lifetime | `src/prompt_score.align`, Align compiler | `c6-borrowed-option-adoption`, `c6-borrowed-array-adoption`, `prompt-verifier-smoke`, per-unit and whole-program compile, repeated caller-owned record use, and no retained view after return |
| successful decoded verification | `src/prompt_score.align` | `prompt-verifier-smoke` for eligible improvement, non-gate improvement, no improvement, serious regression, and valid incomplete statuses |
| embedded identity/reference pairs | `src/prompt_score.align`, C6a1/C6a2 codec | `prompt-verifier-smoke` covers mismatched references and stale row variants; codec owners cover wrong kind/ID/digest/path and missing embedded records |
| incomplete-prefix delegation | C6c1p and C6c2 owners in `src/prompt_score.align` | `prompt-score-prefix-smoke` plus `prompt-verifier-smoke` cover empty, terminal-error, cleanup-retained, and complete prefixes; `validate_prefix` agrees with the trace and no aggregate/reason output is manufactured |
| persisted execution trace | `src/prompt_evaluate.align`, `src/prompt_score.align` | `prompt-verifier-smoke` directly constructs complete, precheck, adapter, postcheck, pre/post drift, retained terminal-row, cleanup-retained, bounded overflow, and malformed-order shapes |
| independent evidence binding | `src/prompt_evaluate.align`, `src/prompt_score.align`, `src/prompt_state.align`, gate validator | `prompt-verifier-smoke` covers missing, duplicate, out-of-order, mismatched-input, and result-digest evidence; later acceptance/gate owners cover explicit paths, source identity, and manifest pairing |
| trust and reachability | explicit source boundary owned by `src/prompt_evaluate.align`, C6f1 source verifier, `src/prompt_score.align` | `prompt-verifier-smoke` covers verified, unverified, missing-observation, `FIXTURE`, and gate eligibility; C6f1/evaluator owners cover source paths, helper/interpreter/Git execution, and unavailable-state production |
| row, aggregate, reason, status, and gate tampering | `src/prompt_score.align` | `prompt-score-smoke`, `prompt-score-prefix-smoke`, and `prompt-verifier-smoke` cover every C6c1 boundary plus status-only, aggregate-only, reason-only, row-identity, and gate-only tampering |
| malformed input and error precedence | `src/prompt_score.align` | `prompt-verifier-smoke` covers status-specific precheck/adapter/postcheck/drift/cleanup/terminal families, invalid option/discriminator combinations, compact counter and empty-shape checks, and pure rejection without side effects |
| allocation and cleanup | `src/prompt_score.align`, C6c1p, Requests 8/10 | one bounded temporary `array<ScoreRow>` plus 64 task columns and primitive C6c1 reason columns of exact checked capacity `R_max <= 9,282` only for complete rows; prefix validation uses no output columns; compact overflow verification uses only bounded scalars; checked arithmetic overflow returns invalid before scorer call, while runtime allocator failure follows the declared Request 8/10 terminal child-process policy; no fixed-size workaround, no duplicated scorer, no moved input, no retained view, normal-path drop checks, and terminal allocator-failure fixture |
| JSON/document binding | C6a1/C6a2, deferred | N/A for C6c2; escaped-string round trips, canonical bytes, and content-digest recomputation require Request 7/12/13 acceptance before this verifier is called |

The implementation checkpoint is `src/prompt_score.align::verify_result`, with
`prompt-verifier-smoke` as the direct C6c2 owner. The verifier and fixture remain one capability:
splitting the public verifier from the only consumer of every borrowed record-array path would
leave an unexercised dormant boundary and duplicate the identity/trace proof.

The C6c2 metric is verifier correctness: every declared state, identity, evidence combination, and
tamper class reaches the specified status or error with zero false acceptance. Runtime performance
is secondary and is measured only after a real result/evidence pair exists; it is not a provider
quality or time-to-passing-patch claim.

### 11.3 C6-MEASURED public-contract ledger

C6-MEASURED delivers C6e, C6g1, and C6g2 as one consumer capability. The request/result schemas,
error-code families, validation precedence, credential and redaction behavior, seed-attestation
semantics, frozen-asset schemas, acceptance-policy values, the `baseline-v1` identifiers, and the
gate manifest/validator behavior are already settled in sections 1.2, 4.4, 4.5, 5, 5.1, 7, 8, and 9
and are not restated here. This ledger fixes the remaining public surfaces so implementation starts
against a settled contract. It also fixes the provider-backed gate measurement surface: the wave's
implementation found that this ledger contracted the gate's measurement semantics without naming a
measurement-adapter surface, while the shipped fixed adapter is `FIXTURE`-only and hard-bound to one
`coding-v1` task. Requests 11, 14, and 18 record their focused verification at the
pinned Align revision. Request 5's transport owner is re-verified at the current pin: the complete
`make provider-smoke`, including the bounded-response matrix and the `Error.Code(-1)` limit
sentinel, passes at `19c3db144c462bf7d6784f88d64cc124229b7ec2` (recorded in `HANDOFF.md`).
Request 2's plaintext/TLS adoption target is owned by this wave, and no `.align-revision` change is
required unless a new prerequisite is discovered and merged.

The exact new and changed public surface is:

```text
PromptExperimentStatus: Proposed | InvalidInput | InvalidProposal | ProviderError
  | OutputWrite                                        // Copy

prompt_experiment.experiment_file(request_path: str, result_path: str)
  -> PromptExperimentStatus                          // new module src/prompt_experiment.align
prompt_experiment.status_label(value: PromptExperimentStatus) -> str
prompt_experiment.status_success(value: PromptExperimentStatus) -> bool

./main prompt experiment <request.json> <result.json>  // new dispatch arm in src/main.align

PromptGenerateStatus: Generated | InvalidInput | ProviderError | OutputWrite   // Copy

prompt_generate.generate_file(request_path: str, result_path: str)
  -> PromptGenerateStatus                              // new module src/prompt_generate.align
prompt_generate.status_label(value: PromptGenerateStatus) -> str
prompt_generate.status_success(value: PromptGenerateStatus) -> bool

./main prompt generate <request.json> <response.json>  // new dispatch arm in src/main.align

model.GenerationRequest gains seed: Option<i64>        // shared-record extension
model.ModelInfo gains supports_seed: bool              // shared-record extension
model.ProviderConfig gains max_response_bytes: i64     // shared-record extension; no implicit
                                                       // default — pre-C6e construction sites,
                                                       // including the non-C6 `--provider` demo
                                                       // in src/main.align and the proposal
                                                       // path, supply 262,144 explicitly, while
                                                       // the evaluator supplies the frozen
                                                       // provider-control value

provider_http.post_json(endpoint: str, api_key: str, body: str, timeout_ns: i64,
  max_response_bytes: i64) -> Result<string, Error>    // the cap becomes an explicit argument

HttpPostResponse { status: i64, body: string }         // owned bounded response carrier
provider_http.post_json_response(endpoint: str, api_key: str, body: str, timeout_ns: i64,
  max_response_bytes: i64) -> Result<HttpPostResponse, Error>
                                                       // Ok for every received HTTP response,
                                                       // including non-2xx; Err only for
                                                       // transport failure

provider_openai.request_bytes(model_name: str, request: model.GenerationRequest,
  streaming: bool) -> string                           // pub export of the existing serializer
provider_openai.decode_content(response: str) -> Result<string, Error>
provider_llama.request_bytes(request: model.GenerationRequest, streaming: bool) -> string
provider_llama.decode_content(response: str) -> Result<string, Error>
```

`experiment_file` follows the shipped `prompt_evaluate.evaluate_file` pattern, not the section 6
`run_file`/`PromptCommandStatus` sketch, which cannot express an experiment outcome:
`status_success` is true only for `Proposed`, `OutputWrite` carries the post-validation
persistence failure exactly as `PromptEvaluateStatus.OutputWrite` does, and the `src/main.align`
dispatch arm prints the label and maps non-success to `Error.Invalid` exactly like the shipped
evaluate arm. The `request_bytes`/`decode_content` pairs are `pub` exports of the existing private
serializers and envelope decoders, so the experiment path, the evaluation path, and the
`provider_request_sha256` digest preimage share one byte source per provider without duplicating
the wire schema. The llama wire record carries no model field, so its export takes no model name;
llama model identity is bound by the provider-control and model-info fields, not the request
bytes. `post_json_response` exists because the shipped `post_json` folds HTTP statuses and
transport errnos into one `Error.Code` constructor: the proposal path needs a received non-2xx
status as data with its bounded body, while a transport `Err` stays unambiguous.

`src/prompt_artifacts.align` gains one declared proposal-path record with the existing
decode/encode/bounded-encode function trio, canonical content digest, and golden semantic-to-byte
plus byte-to-semantic vectors: `PromptExperimentRequest` carries exactly the section 5.1 fields with
`schema_version` 1 and `artifact_kind: PROMPT_EXPERIMENT_REQUEST`. Validation follows the
universal section 5 record order and the section 5.1 bounds. The record has no credential-value
field; `api_key_env` is a validated name only.

The opportunity artifact needs no new record: it is the settled section 4.1 `PromptTextArtifact`
with `artifact_kind: OPPORTUNITY` and the section 4.3 inclusive 65,536-byte text bound, exactly
what the shipped verifier and codec already accept. Its text carries the stable opportunity
summary and bounded supporting diagnostics; `artifact_id` is the stable opportunity ID.
`PromptExperimentResult.opportunity` references kind `OPPORTUNITY` with that `artifact_id` and
content digest.

**Proposal prompt construction.** `src/prompt_experiment.align` composes the proposal prompt in
one fixed labeled-section order: (1) the parent activation's effective hierarchy (base prompt,
repo prompt, effective learned append), (2) the parent effective `ContextPolicy` in canonical
field order, (3) the immutable constraint text derived from the section 5.1 "model does not
choose" list, (4) the opportunity ID, summary, and diagnostics in persisted order, and (5) the
exact `CandidateProposal` response-schema text. One golden proposal-prompt vector plus an exact
`max_prompt_bytes` and cap-plus-one pair prove the bound is enforced before any provider call.

**Credential lifetime and redaction surface.** After request validation and before any provider
call, `experiment_file` reads the validated `api_key_env` name, when it is `Some`, exactly once
with `env.get` into one temporary owned `string`; a `None` name performs no environment read and
passes an empty `api_key`. A missing or empty value for a `Some` name is `MISSING_CREDENTIAL`
before the first external call. The owner is passed only as the explicit `api_key` argument of the single provider
call, is never encoded, digested, logged, or copied into a persisted or diagnostic value, and is
dropped before result construction on every terminal path, including `?` and early returns. The
redaction surface is:

```text
prompt_experiment.redact_credential(borrow text: str, borrow credential: str) -> string
```

It performs the exact section 1.2 pass: one left-to-right replacement of every non-overlapping
exact UTF-8 occurrence of the credential with `[REDACTED]`, applied to provider output, provider
status text, error detail, and the proposal summary before truncation, hashing, or persistence.
An empty credential pattern returns the input unchanged; this is the ordinary path for every
`api_key_env: None` provider run, not a defensive edge, and has its own vector. Golden vectors
cover regex punctuation, overlapping prefixes, adjacent multi-byte UTF-8, and occurrences crossing
the 16 KiB truncation boundary.

**Provider call, decode order, and error mapping.** The deterministic order after validation is:
construct the proposal prompt; enforce `max_prompt_bytes`; build the provider wire bytes through
the selected provider's `pub` `request_bytes` export with empty `system`, the proposal prompt as
`user`, `max_tokens` and `temperature_micros` from the request, and `seed: None` (a proposal call
is unseeded and records no seed attestation); make exactly one bounded
`provider_http.post_json_response` call with the request `timeout_ns` and `max_response_bytes`
262,144 so a received status and the raw bounded response text stay available as data for
diagnostics; for a 2xx response, extract the single content text with the provider's `pub`
`decode_content` export; `decode_candidate_proposal`; validate the proposal schema version and
bounds; compare the rendered learned append and context policy against the parent effective
variant. A received HTTP response is an `Ok(HttpPostResponse)` and is never classified by a
numeric range over `Error.Code`; a transport `Err` is matched as `Error.Timeout`, then
`Error.Code(-1)` (the receive-side limit sentinel), then everything else, so a transport errno —
connection reset, refused connect, unreachable host — can never masquerade as an HTTP status.
Outcomes map to exactly one code, first failure wins:

| Outcome | Status / `error_code` |
| --- | --- |
| transport `Err(Error.Timeout)` | `PROVIDER_ERROR` / `PROVIDER_TIMEOUT` |
| transport `Err(Error.Code(-1))`, the receive-side limit sentinel | `PROVIDER_ERROR` / `PROVIDER_RESPONSE_TOO_LARGE` |
| any other transport `Err` (errno, connect, TLS, DNS, non-UTF-8 body) | `PROVIDER_ERROR` / `PROVIDER_TRANSPORT` |
| `Ok` with a non-2xx `status` | `PROVIDER_ERROR` / `PROVIDER_HTTP_STATUS` with `proposal_status_code: Some(status)` and the redacted bounded body as diagnostics |
| provider envelope decode or content extraction failure on a 2xx body | `INVALID_PROPOSAL` / `PROPOSAL_SCHEMA` |
| `CandidateProposal` decode or schema-version failure | `INVALID_PROPOSAL` / `PROPOSAL_SCHEMA` |
| summary, learned-append, or context-policy bounds failure | `INVALID_PROPOSAL` / `PROPOSAL_BOUNDS` |
| equal rendered learned append and context policy | `INVALID_PROPOSAL` / `PROPOSAL_NO_CHANGE` |

`proposal_status_code` is `Some` only for `PROVIDER_HTTP_STATUS`, and only a genuinely received
HTTP status can reach it. The result is a single artifact published through the C6d direct
retained exclusive-create write path in `prompt_artifact_io` — no temporary-plus-rename pair and
no evidence sidecar. The section 5 step-2 preflight is exactly that retained exclusive creation:
an existing or unwritable result output path fails the create with `Error.Invalid` (or the
underlying filesystem error) before any external work and produces no result artifact, and the
retained writer is the one later used to persist the bounded result bytes. A write, flush, or
close failure after a valid terminal result is `OutputWrite` with `OUTPUT_WRITE`.

**Shared seed extension.** `model.GenerationRequest.seed: Option<i64>` and
`model.ModelInfo.supports_seed: bool` extend the shared records; every existing caller passes
`None`, and the single kind-dispatched `model_info` constructor in `src/provider.align` reports
`supports_seed` truthfully per selected adapter kind.
`src/provider_openai.align` and `src/provider_llama.align` keep their current wire records for
`seed: None` and select a declared seeded twin record adding exactly one `seed` field for `Some`,
so unseeded request bytes remain byte-identical to the pre-extension encoding. Each provider's
`pub` `request_bytes` export is the single source of provider request bytes: the same bytes are
sent on the wire and are the SHA-256 preimage of `provider_request_sha256` in
`SeedCapabilityAttestation` and the evidence input rows, and the evaluator verifier validates that
binding per section 10. `model.ProviderKind` gains no `FIXTURE` variant; `FIXTURE` remains an
evaluator-level control that never reaches provider dispatch.
`model.ProviderConfig.max_response_bytes` carries the caller's cap to the transport through every
`post_json` call site in `src/provider_openai.align` and `src/provider_llama.align`: the evaluator
supplies the frozen provider-control value (1 through 1,048,576, section 1.2), while the proposal
path and the pre-C6e construction sites fix 262,144.

**Request 2 adoption.** The named target `c6e-request2-adoption` runs
`scripts/run-http-timeout-adoption-smoke`: one plaintext fixture listener accepts the TCP
connection and never writes a response, and one TLS listener accepts and never completes the
handshake; both `post_json` calls must return the transport timeout error within a bounded
wall-clock multiple of the configured sub-second `timeout_ns`, and a control request against a
responsive listener succeeds under the same configuration. Passing this target plus the wave's
final capable gate advances Request 2 in `docs/align-requests.md`.

**Provider-backed gate measurement.** This ledger already settles the gate's measurement semantics:
the adapter owns the generation call, the evaluator supplies the frozen provider-control
`max_response_bytes`, and each provider's `pub` `request_bytes` export is the single source of
provider request bytes. It named no measurement-adapter surface, and the shipped
`scripts/prompt-fixed-adapter.py` is a `FIXTURE`-only adapter hard-bound to one `coding-v1` task,
its runner, and its two checked-in patches, so no gate-eligible row can be produced by it. The
settled surface splits that work across two owners without weakening the reviewed-source,
credential, or identity rules beyond the one explicit relaxation recorded below.
`scripts/prompt-measurement-adapter.py` is a task-parameterized sibling of the fixed adapter: a
byte-equal corpus member carrying a `PYTHON:<sha>` runtime label that satisfies the unchanged outer
admission rules, so the evaluator's task-command owner still admits exactly
`<interpreter> <one helper>` argv, still resolves the helper from the validated project root, and
still requires its declared `measurement_adapter_runtime` digest and reviewed corpus membership. It
owns workspace orchestration, sealed input admission, contained execution of the validation runner,
`TaskMeasurement` assembly, and redaction, and it performs no provider wire serialization. The
single provider generation call is delegated to a derived Align generation child so that provider
request bytes keep exactly one producer. The fixed adapter keeps its hard-coded runner, task, and
patch identities, remains the deterministic non-gate fixture owner, and is unchanged except for the
adapter-request field-order additions below.

**Evaluator provider admission and credential threading.** The evaluator admits the section 4.5
provider kinds with their exact `api_key_env` pairing — required for `CLOUD_OPENAI`, optional for
`LOCAL_OPENAI`, and `None` for `LLAMA_CPP` and `FIXTURE` — and keeps every other provider-control
check unchanged. The shipped `FIXTURE`-only admission in `scripts/prompt-evaluate.py` was an
implementation restriction introduced by the C6-EVALUATION wave rather than a contract; C6-MEASURED
lifts it, because section 5.2's `gate_eligible` rule already forbids a `FIXTURE` provider and no
gate-eligible row can exist while the restriction stands. The evaluator resolves the named
credential exactly once from its startup environment before any snapshot, helper, or adapter call,
copies the validated name — never the value — into `TaskAdapterRequest.credential_env_name` for
every measurement-adapter invocation, and injects the value with the section 1.2 construction order.
A `None` name performs no environment read and writes `None`. Every existing rule about the snapshot
helper, the source verifier, digests, diagnostics, and persistence is unchanged.

**Generation child contract.** `src/prompt_generate.align` owns exactly one bounded provider
generation. `generate_file` follows the same shipped pattern as `prompt_evaluate.evaluate_file` and
`prompt_experiment.experiment_file`: `status_success` is true only for `Generated`, `OutputWrite`
carries the post-dispatch persistence failure, and the `./main prompt generate` arm has arity 5 and
prints the operation, status label, and output path, mapping non-success to `Error.Invalid` exactly
like the shipped evaluate and experiment arms. `src/prompt_artifacts.align` gains two declared
measurement-path records with the same decode/encode/bounded-encode trio, canonical content digest,
and semantic-to-byte plus byte-to-semantic goldens as every other record in that module:

```text
PromptGenerationRequest:
  schema_version
  artifact_kind: PROMPT_GENERATION_REQUEST
  request_id
  provider_kind
  endpoint
  provider_model
  api_key_env: Option<str>
  rendered_prompt_path
  rendered_prompt_sha256
  max_tokens
  temperature_micros
  paired_seed
  timeout_ns
  max_response_bytes
  content_sha256

PromptGenerationResponse:
  schema_version
  artifact_kind: PROMPT_GENERATION_RESPONSE
  request_id
  status: GENERATED | INVALID_INPUT | PROVIDER_ERROR
  error_code
  error
  provider_kind
  provider_model
  provider_request_sha256
  seed_result: APPLIED | UNSUPPORTED | REJECTED
  applied_seed: Option<i64>
  http_status: Option<i64>
  content: Option<string>
  dispatch_start_ns
  dispatch_end_ns
  content_sha256
```

Both records use `schema_version` 1 and follow the universal section 5 record order and the section
1.2 identifier, path, endpoint, and digest bounds. `api_key_env` is a validated name only; no
declared record carries a credential value. `provider_kind` admits only a dispatchable kind:
`FIXTURE` is `INVALID_INPUT` here because `model.ProviderKind` gains no `FIXTURE` variant and that
control never reaches provider dispatch. The child reads the rendered prompt through the declared
path and requires its `RenderedPromptArtifact` digest to equal `rendered_prompt_sha256`, so the
section 4.5 request mapping stays normative and no intermediate owner can prepend, append, or split
the rendered bytes. Measurement-risk note: the gate binds the rendered prompt by digest only — it
re-derives no rendered text from the frozen assets, so a rendered prompt whose digest is consistent
everywhere is accepted without the gate reproducing its content; `prompt-render-parity-smoke` is the
owner that keeps the two renderers byte-equal. `dispatch_start_ns` and `dispatch_end_ns` are child-observed diagnostics for the
measurement-risk record; they never define a scored duration. `OUTPUT_WRITE` is a command status
only: a failed response write persists no response artifact, and the adapter classifies the missing
document exactly like any other failed handoff below.

The child's deterministic order is: decode and validate the request; read and verify the rendered
prompt; build `model.GenerationRequest` with the empty `system`, the rendered text as `user`, the
policy `max_tokens` and `temperature_micros`, and `seed: Some(paired_seed)`; obtain the wire bytes
from the selected provider's `pub` `request_bytes` export; compute `provider_request_sha256` over
exactly those bytes immediately before dispatch; perform exactly one
`provider_http.post_json_response` with the request `timeout_ns` and the frozen provider-control
`max_response_bytes`; and write the response. The adapter launches the child exactly once per
invocation, so one bound provider generation call per sample satisfies the section 9 gate-corpus
rule at the initial gate tasks' `maximum_repair_loops: 0`. `seed_result` is the sections 4.5 and 5.2
attestation semantics
observed at this boundary: `APPLIED` with `applied_seed: Some(paired_seed)` when the selected
adapter reports `supports_seed` and the seeded twin bytes carry the paired seed, `UNSUPPORTED` with
`applied_seed: None` when the adapter does not support a seed, and `REJECTED` with
`applied_seed: None` when a seed-supporting provider returns a received response refusing it.
Measurement-risk note: `APPLIED` attests that the seeded twin bytes carried the paired seed and the
provider accepted the request, not that the provider produced a deterministic completion from it;
the gate evidence therefore proves seed transport, never provider reproducibility. The
transport, status, and decode error mapping is exactly the section 11.3 proposal table above:
`Error.Timeout`, the `Error.Code(-1)` receive-side limit sentinel, any other transport `Err`, a
received non-2xx status as `Ok` data with its bounded body, and a 2xx envelope or content-extraction
failure. A 2xx envelope whose completion text decodes to zero bytes is a content-extraction failure:
it is `PROVIDER_ERROR` / `PROVIDER_RESPONSE_SCHEMA` exactly like a malformed envelope, never a
`GENERATED` response carrying empty content, so `content: Some` always names at least one byte and
no consumer distinguishes an empty success from a real one. This is the generate-side analogue of
the proposal path's `INVALID_PROPOSAL` / `PROPOSAL_SCHEMA` row for an unusable 2xx body. Every
persisted diagnostic is redacted before truncation, hashing, or persistence.

**Measurement response edit format.** The rendered task prompt instructs the model to emit, for each
edited file, a block of the exact form:

```text
FILE: <repo-relative-path>
```<the complete new file content>```
```

The measurement adapter parses these blocks, tolerating a language tag after the opening fence and
prose before, between, and after them; a closing fence is a line of backticks at least as long as the
opening run, so a longer outer fence carries nested fences as content. Whole-file content, not a
diff, is the settled response shape: the pinned corpus files are small, and a whole file removes the
context-matching failure mode that makes an unusable model diff indistinguishable from a wrong
repair. The adapter requires every declared path to be inside the task definition's `allowed_edits`
and refuses the edit set before it launches the validation runner — any out-of-allowlist path,
including an absolute or escaping spelling, is `POLICY_VIOLATION` / `POLICY` with both stages
`NOT_RUN`. It requires at least one complete block; a response with no block, an unterminated block,
a `FILE:` header with no block, or a duplicated path is the patch-absent outcome `FAIL` / `PATCH`
with both stages `NOT_RUN`, which is a scored task failure rather than an adapter error. Both
outcomes retain the generation response's provider identity, request digest, and seed attestation,
because the provider did answer. The adapter then writes the validated edit set as the whole-file
replacement hunks the declared validation runner applies, and records the applied edit set in the
bounded diagnostic summary; `patch_size_bytes` is the size of those bytes. The runner's own
allowlist, pristine-checkout, and mode checks are unchanged and remain the authoritative second
gate. A task that declares the `Some` `patch_path`/`patch_sha256` pair is unaffected: its fixture
patch is admitted verbatim and nothing is parsed from a response. This paragraph settles the format
only; section 5.2's adapter contract, output cap, containment, and redaction rules are unchanged.

The adapter copies `provider_request_sha256`, `seed_result`, `applied_seed`, and the provider
identity verbatim from the response into `GenerationRequestIdentity` and
`SeedCapabilityAttestation`; it never re-serializes provider bytes and never derives that digest
from any other preimage. The section 5.2 non-circularity rule is therefore preserved with the child
as the provider boundary: the digest comes from the dispatched wire bytes alone, independently of
the attestation, and the evaluator still requires the two persisted values to be equal.
Measurement-risk note: that digest is nonetheless self-attested by the generation child — no owner
outside the child witnesses the bytes actually written to the socket — so its trust rests on the
child's reviewed source, its declared per-run digest, and the adapter's pre-launch and post-return
verification of the sealed binary, not on an independent observation of the wire.

**Derived-child admission and credential handoff.** The generation child is the one explicit
relaxation of the reviewed-source execution boundary, and its exact shape is fixed here. The child
binary is built, not committed, so it cannot be a corpus member; its reviewed `src/` TREE and
`.align-revision` remain corpus members and carry the reviewed-source proof. The binary's path and
digest are supplied per run: `PromptEvaluateRequest` gains `generation_child_path` and
`generation_child_sha256`, the evaluator copies both into `TaskAdapterRequest`, and the checked-in
gate supplies the same pair as a fourth explicit `C6_GATE_*` input alongside the existing three,
mapped to `--generation-child-path` and `--generation-child-sha256` with the same missing, empty,
relative, unsafe, and unreadable rejection and no environment or sibling-checkout fallback. The
validator retains the path as an absolute regular executable and requires its same-descriptor bytes,
the declared digest input, and the evidence-recorded
`PromptGateSourceLocator.generation_child_sha256` to be equal, so neither a stale evidence claim nor
an unverified local build can satisfy the gate. Neither the absolute path nor a machine-specific
spelling is ever frozen into `eval/prompt/canonical-v1/`; the pair belongs to the per-run request
and the recorded check evidence. The adapter admits the child as a sealed immutable
input following the section 10.1j inner-retained precedent: it opens a no-follow bounded owner,
verifies the declared digest before launch, launches only the retained descriptor without reopening
the public pathname, and verifies the retained input unchanged after the child returns. The child is
one more contained direct child of the adapter and inherits the section 10.1c and 10.1d descendant
ownership, private session/group, kill, reap, absence-proof, and exactly-once cleanup rules already
owned by that boundary. It produces no `EnvironmentProbe`: section 1.2's two probe carriers and
`EnvironmentIdentityCore`'s three runtime-identity fields are unchanged, and the child's identity
binds through the declared per-run digest and the adapter's pre-launch and post-return verification
rather than through the environment identity.

The credential value continues to reach only the allowlisted measurement-adapter child, and the
handoff to the generation child is licensed by the section 1.2 rule that a provider call receives
the same one-shot value as an explicit boundary argument and, when its implementation uses a child
process, uses the same construction order, and by the section 4.5 rule that a provider
implementation may use the value in-process or through the child environment provided it receives
the same explicit one-shot value and rereads no ambient environment state. The adapter therefore
constructs the generation child's environment as `env_clear()`, the policy's ordered
`allowed_variables`, then exactly one credential entry under the same name it received, and the
child reads that name exactly once from its own constructed startup environment. The value reaches
exactly two processes — the adapter and its generation child — and never the snapshot helper,
the source verifier, or the validation runner, whose environment stays the cleared policy
environment with no credential entry. A missing or empty value for a `Some` name is a
pre-dispatch failure before the first external call. Redaction runs in both owners: the child
redacts its own diagnostics before writing the response, and the adapter redacts everything it
persists into `TaskMeasurement`.

**Task parameterization of the measurement adapter.** The identities that
`scripts/prompt-fixed-adapter.py` hard-codes become declared inputs. `PromptEvaluationTask` gains
`validation_runner_path`, `validation_runner_sha256`, `task_definition_path`,
`task_definition_sha256`, and `validation_argv`, plus the `Option` pair `patch_path` and
`patch_sha256` that is `None` for a provider-backed task whose patch comes from the generation
response and `Some` only for a deterministic fixture-style task. `TaskAdapterRequest` gains exactly
those fields plus `generation_child_path` and `generation_child_sha256`, appended after
`environment_policy_sha256` and before `content_sha256` so every existing field keeps its position.
Every referenced file except the generation child is a corpus member and inherits the existing
membership, digest, and admission checks unchanged; the adapter verifies each declared digest before
launch and admits each as a sealed immutable input. These are outright pre-release schema-version-1
changes for both records, following the section 4.5 `PromptSourceVerifierPolicy` precedent: an older
version-1 record without the new fields is invalid, receives no compatibility default, and is never
migrated. The exact-field-order check and the `EvaluationInputIdentity.adapter_request_sha256`
preimage in the shipped fixed adapter and evaluator change in the same commit; the fixed adapter
continues to reject a non-`None` `credential_env_name` and remains non-gate-eligible.

**Measured timing boundary.** `generation_to_passing_patch_ns` starts in the adapter immediately
before it launches the generation child, so child spawn and initialization cost is inside the
measured window; the child's own clock never defines the boundary. This is the settled section 5.2
reading of "immediately before the first provider generation call" for a two-process implementation,
and the exclusions are unchanged: evaluator snapshots, checkout preparation, input decoding, result
encoding, and post-run cleanup stay outside. The overhead is symmetric across parent and candidate,
so it cannot bias the paired comparison, but its magnitude is measurement risk and the generation
smoke must record it. Because the adapter now runs two sequential contained children, the section
10.1e adapter outer deadline is the sum of the provider-control and task deadlines plus the existing
bounded cleanup and report margin rather than their maximum; the constants remain evaluator-owned
and asserted by `prompt-evaluate-smoke`, and every inner deadline remains strictly smaller than the
evaluator deadline that started earlier.

**Repository identity of the C6g assets and gate validator.**

- Gate corpus tasks: `eval/tasks/prompt-v1/` (at least two tasks per section 9).
- Canonical frozen scope assets and the `baseline-v1` envelope: `eval/prompt/canonical-v1/`
  holding the section 4.4 freeze set — `corpus.json` (the `PromptEvaluationCorpus` manifest whose
  `task_files` pin the frozen `eval/tasks/prompt-v1/` membership; the evaluate request's
  `corpus_path` target), `scope.json` (the section 4.2 `PromptScope` binding the frozen corpus
  revision, required because the baseline envelope's scope digest binds it),
  `generation-policy.json`, `evaluation-provider-control.json`, `prompt-acceptance-policy.json`
  (the section 7 record), and `base-prompt.json` and `repo-prompt.json` (section 4.1
  `PromptTextArtifact` records with kinds `BASE_PROMPT` and `REPO_PROMPT`) — plus
  `prompt-activation-baseline-v1.json`, whose scope and prompt digests bind exactly these frozen
  artifacts. The evaluate request's environment policy is not part of the frozen scope set; it
  travels with the checked-in gate evidence under `eval/prompt/gate/`. The C6g1 freeze review
  fixes the frozen contents; C6g2 must not mutate them after measuring against them.
- Measurement adapter: `scripts/prompt-measurement-adapter.py`, the task-parameterized sibling of
  `scripts/prompt-fixed-adapter.py`. It is a byte-equal corpus member declared by each gate task
  with a `PYTHON:<sha>` `measurement_adapter_runtime` label, satisfies the unchanged
  `<interpreter> <one helper>` outer admission rules, and owns workspace orchestration, sealed input
  admission, contained validation-runner execution, `TaskMeasurement` assembly, and redaction. It
  performs no provider wire serialization; the single generation call belongs to the derived
  `./main prompt generate` child, whose per-run path and digest travel in the evaluate request and
  the recorded check evidence and are never frozen here.
- Checked-in gate evidence: `eval/prompt/gate/` holding `prompt-gate-manifest.json` and the
  referenced evaluation result, evidence, activation, and environment-policy artifacts. The gate
  environment policy is a manifest `ArtifactReference` per the section 9 field list, not a
  path-only sibling.
- Gate validator: `scripts/prompt-gate-validator.py` under CPython 3.12, invoked only by the
  `make prompt-gate-check` gate target with the explicit `C6_GATE_*` values mapped to `--source-bundle-root`,
  `--python-executable-path`, `--git-executable-path`, `--generation-child-path`, and
  `--generation-child-sha256`. The first three are settled by section 9; the generation-child pair
  is the fourth input described above and is checked before any evidence identity. Its behavior
  matrix is settled by section 9 and the section 10/10.1 gate rows, whose named
  `prompt-gate-*-smoke` targets are owned by this wave's validator implementation.

**Owner targets and lanes.** `prompt-experiment-smoke`, `prompt-credential-lifetime-smoke`,
`prompt-seed-attestation-smoke`, `prompt-generate-smoke`, `prompt-measurement-adapter-smoke`,
`prompt-render-parity-smoke` (the owner of the renderer-parity row below, placed beside
`prompt-model-smoke` in the lane's declaration order), and
`c6e-request2-adoption` join the hosted check lane as new
additions; the named `prompt-gate-*-smoke` fixtures are likewise new hosted additions (today's
gate/evaluator fixtures run only inside the capable-only `c6-evaluation-adoption`), and the real
`make prompt-gate-check C6_GATE_...` run remains the named capable gate qualification for the
measured gate, outside every lane and aggregate. Every hosted-lane
addition changes the literal lane bytes owned by `scripts/check-gate-topology`, so the same
change refreshes its `EXPECTED` sequence and the check-baseline chain, following the section 11.1
precedent.

C6-MEASURED also removes one member from that lane. `prompt-verifier-smoke` stays the direct C6c2
owner and a `.PHONY` public target, but it is now a **named focused qualification** rather than a
hosted-lane member. At the pinned Align revision `2f33ac5c33a898a7894af58322852632ce6ffe42`,
`make prompt-verifier-smoke` costs roughly 720 s of wall time at a 1,525,732 KiB peak resident set,
while `alignc check` of the same unit costs 0.494 s. The unit's many large by-value record
literals — 100 of its 345 `huge struct copy` warnings name one 5,056-byte record — hit a compiler
code-generation cost that one smoke alone exceeded the supervised fresh-worker aggregate's
practical budget with. Run `make prompt-verifier-smoke` directly whenever
the section 10 verifier boundary in `src/prompt_score.align` changes, and before publishing such a
change; it is not reached by `hosted-checks`, `capable-checks`, or `ci`. `docs/align-requests.md`
Request 19 records the compiler-side gap, and the member rejoins the lane when that gap closes.
Removing it changes the same lane bytes an addition would, so this change refreshes
`scripts/check-gate-topology`, the `docs/specs/check-gate-topology.md` oracle, and the
check-baseline chain together.

The C6-MEASURED closure matrix is:

| Applicable path | Owner | Exact acceptance evidence |
| --- | --- | --- |
| request decode, validation order, and no-external-call proof | `src/prompt_experiment.align`, `src/prompt_artifacts.align` | `prompt-experiment-smoke` table-driven first-failure rows for every section 5 `experiment` precedence entry, each proving no listener contact |
| opportunity artifact | settled `PromptTextArtifact` codec in `src/prompt_artifacts.align` | existing kind-`OPPORTUNITY` goldens plus `prompt-experiment-smoke` reference rows binding `artifact_id`, kind, digest, and the inclusive 65,536-byte text bound |
| proposal prompt construction and bounds | `src/prompt_experiment.align` | golden proposal-prompt vector; exact `max_prompt_bytes` and cap-plus-one before any provider call |
| credential lifetime | `src/prompt_experiment.align` | `prompt-credential-lifetime-smoke`: `MISSING_CREDENTIAL` precedence, single explicit one-shot argument, no credential bytes in any persisted or diagnostic output, drop before result construction on success and on every terminal error path |
| redaction | `src/prompt_experiment.align` | golden vectors for punctuation, overlapping prefixes, multi-byte adjacency, truncation-boundary crossing, and the ordinary empty-pattern (`api_key_env: None`) case |
| transport error mapping | `src/prompt_experiment.align`, `src/provider_http.align` | fixture server rows for stall/timeout, over-cap limit sentinel, received HTTP 4xx/5xx as `Ok` data with `Some(status)` and redacted body, connection-reset and refused-connect errnos mapping to `PROVIDER_TRANSPORT` (never `PROVIDER_HTTP_STATUS`), and non-UTF-8 body |
| proposal decode, bounds, and no-change | `src/prompt_experiment.align` | `PROPOSAL_SCHEMA`, `PROPOSAL_BOUNDS`, and `PROPOSAL_NO_CHANGE` rows including summary-only change |
| result construction and publication | `src/prompt_experiment.align`, `src/prompt_artifact_io.align` | per-status golden results, exact `Option` population, 4 KiB summary and 16 KiB output bounds, occupied-output rejection at the retained exclusive create with no result artifact, and post-validation write/flush/close failure as `OutputWrite`/`OUTPUT_WRITE` |
| shared seed extension | `src/model.align`, `src/provider.align`, `src/provider_openai.align`, `src/provider_llama.align`, evaluator verifier | `prompt-seed-attestation-smoke`: unseeded byte-identity regression, seeded twin bytes, request-digest equality, truthful `supports_seed` per adapter, and `APPLIED`/`UNSUPPORTED`/`REJECTED` ineligibility rows |
| parameterized transport cap | `src/provider_http.align` plus every `post_json` call site in `src/provider_openai.align`, `src/provider_llama.align`, and the `src/main.align` demo config | bounded adoption smoke extended with exact-cap and cap-plus-one per configured value, including a non-default provider-control value; pre-C6e callers compile with the explicit 262,144 argument |
| hosted lane topology | `scripts/check-gate-topology`, `Makefile`, check-baseline chain | refreshed `EXPECTED` lane bytes and baseline sequence in the same change that adds the hosted targets, per the section 11.1 precedent |
| allocation and cleanup | `src/prompt_experiment.align`, `src/prompt_artifacts.align` | every owned temporary — the credential, the raw bounded response, the decoded proposal, and the constructed result — is bounded by its declared cap and dropped before return on success and on every terminal path including `?`; no borrowed view is retained after `experiment_file` returns; runtime allocator failure follows the declared Request 8/10 terminal policy; the credential drop-before-result rule is asserted by `prompt-credential-lifetime-smoke` |
| CLI dispatch | `src/main.align` | CLI smoke covers valid and invalid arity and the updated usage line |
| Request 2 timeouts | `src/provider_http.align`, `c6e-request2-adoption` | plaintext read-stall and TLS handshake-stall within the bounded wall clock plus the responsive control request |
| frozen canonical assets and `baseline-v1` | `eval/prompt/canonical-v1/`, C6g1 freeze review | digest-bound goldens; C6g2 evidence chain binds exactly these artifacts |
| gate validator | `scripts/prompt-gate-validator.py`, `Makefile` | the named `prompt-gate-*-smoke` fixtures plus one real capable `make prompt-gate-check C6_GATE_...` run |
| generation child dispatch | `src/prompt_generate.align`, `src/provider.align`, `src/provider_openai.align`, `src/provider_llama.align`, `src/provider_http.align` | `prompt-generate-smoke`: golden request bytes per provider kind, `provider_request_sha256` equal to the exact dispatched bytes, `APPLIED`/`UNSUPPORTED`/`REJECTED` seed rows with their required `applied_seed` shape, the complete transport/status/decode error mapping, no credential byte in the response or any diagnostic, and the recorded child spawn-overhead measurement |
| derived-child admission | `scripts/prompt-measurement-adapter.py` | `prompt-measurement-adapter-smoke`: a declared digest mismatch and a post-admission binary replacement each produce no scoreable row, and a sealed launch of the admitted bytes succeeds and verifies the retained input unchanged |
| two-process handoff | `scripts/prompt-measurement-adapter.py`, `src/prompt_generate.align` | `prompt-measurement-adapter-smoke`: mutated or absent response digest, truncated response, nonzero child exit, and child timeout each yield `ERROR` with the section 5.2 and 10.1k precedence — `CONTAINMENT`, then `CLEANUP`, then `ADAPTER` — both time fields `None`, and never a scoreable row |
| measurement response edit format | `scripts/prompt-measurement-adapter.py`, `eval/tasks/prompt-v1/*/task-prompt.json` | `prompt-measurement-adapter-smoke`: parse rows for single and multiple blocks, a language-tagged fence, surrounding and trailing prose, a nested fence under a longer outer fence, and CRLF; refusal rows for no block, an unterminated block, a header without a block, and a duplicate path as `FAIL`/`PATCH`, and out-of-allowlist, absolute, and escaping paths as `POLICY_VIOLATION`/`POLICY` with no runner launch; a golden whole-file hunk that `git apply` really applies, an unchanged-content refusal, and a created-file hunk; plus `prompt-generate-smoke`'s empty-2xx-content row proving the child never publishes empty `GENERATED` content |
| task parameterization | `scripts/prompt-measurement-adapter.py`, `scripts/prompt-evaluate.py` | `prompt-measurement-adapter-smoke`: manifest-driven runner and task-definition digests admit and execute; a wrong declared digest is rejected before launch with no runner marker; the extended `TaskAdapterRequest` field order and its `EvaluationInputIdentity` preimage are golden-bound |
| renderer parity | `scripts/prompt-evaluate.py`, `src/prompt_model.align` | `prompt-render-parity-smoke`: shared golden rendered-prompt vectors over all eight section 4.3 enable/disable combinations, each section's truncation boundary, and `task_id` failure-memory selection, asserted byte-equal across both implementations; this row records the already-settled section 4.3 contract, and the Python renderer's disabled-section-only restriction was an implementation defect |
| measured claim | gate pull request | reproducible before/after from a named clean commit, exact command and provider environment without credentials, and the delivered result stated exactly as measured — see "What the measured claim is and is not" below |

Ledger field completion: persisted and cache identity are `N/A` for `redact_credential` and for both
modules' `status_label` and `status_success` (pure functions with no persisted output); schema
versioning is `N/A` for the in-memory `model` record extensions (the persisted identities are the
wire records and the section 4 artifacts, which carry their own versions); persisted canonical
identity is `N/A` for the generation child's per-run path and digest, which are validated request
and gate inputs recorded in check evidence rather than frozen assets; and ownership/allocation for
the settled section 5.1 record fields is owned by the existing codec rows and is not restated
here.

**What the measured claim is and is not.** The delivered C6g2 result is a **completion-count gain
on one task**, not a timing result. The frozen corpus has three tasks and two samples per variant.
`duration-half-away-from-zero` moves from 0/2 passing under the parent variant to 2/2 under the
candidate, giving `completion_gain_count: 2`; the other two tasks fail in both variants, so their
`candidate_pass_count` and `parent_pass_count` are both zero. `paired_pass_count` is therefore **0
for every task and 0 for the corpus**, `parent_paired_median_time_ns` and
`candidate_paired_median_time_ns` are absent, and **no time-to-passing-patch comparison exists in
this evidence at all**. Acceptance is reached solely through the section 8 completion-gain path,
which is the one path that does not require a paired pass. The lever is a single task, so the result
is a demonstration that the measurement chain produces a real, gate-eligible improvement end to end,
not a corpus-level or statistical quality result.

Two caveats belong in the pull request beside the numbers. First, the accepted candidate's learned
append names the failing task's fix in prose; it was produced by the real `prompt experiment` run
from an opportunity artifact that describes that task's recurring failure, so the candidate is
model-authored but the opportunity that seeded it was human-authored and task-specific. Second,
**no provider-quality claim is made or implied by this wave.** The reproducible baseline is the
parent-vs-parent null replicate over the same frozen corpus, run with the same command and the same
provider environment, which flipped no cell; its exact command and result digest are recorded in
`HANDOFF.md`.

The implementation checkpoint is one consumer-complete capability: `src/prompt_experiment.align`
and `src/prompt_generate.align` with their smoke owners, the shared seed extension, the Request 2
adoption target, `scripts/prompt-measurement-adapter.py` with the evaluator provider admission and
task parameterization it requires, the frozen C6g1 assets, and the C6g2 evidence chain and validator
belong to the same wave because the gate evidence is the only real consumer of the proposal and
measurement surfaces. The C6e metric is proposal-command
correctness with zero credential leakage across every terminal path. The C6-MEASURED metric is the
section 11 wave claim as narrowed above: the gate pull request owns the reproducible null baseline
and states the delivered completion-count gain exactly as measured. It delivers no paired timing
evidence, so it makes no time-to-passing-patch claim, and no capability in this wave claims provider
quality.

## 12. Deferred extensions

The following are explicitly deferred and are not implied by the schema:

- repository-index chunk ranking beyond the existing verification-loop context;
- learned model selection, sampling parameters, test policy, or acceptance policy;
- multi-repository activation registries;
- concurrent service mutation and atomic active-pointer replacement;
- automatic production activation after `accept`;
- distributed evaluation and statistical significance tests beyond paired fixed samples.

Each extension requires a new design review and an acceptance test tied to time to a passing patch
or another explicitly named metric.
