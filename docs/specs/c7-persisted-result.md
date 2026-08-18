# C7-PersistedResult: owned verification result and artifact verification

Status: reviewed design plan of record; implementation remains blocked on the named Align and
platform prerequisites. Section 12 defines the consumer-complete delivery boundary.

This document is the plan of record for the first C7 consumer named by
`docs/specs/roadmap.md`. It defines a vertical capability: decode one declared
verification input into an owned record, let the input document and all borrowed views expire,
publish one canonical result artifact, reload that artifact, and verify its value with an
independent algorithm-testing gate. It does not define a general property-testing framework or
replace the existing provider, evaluation, or failure-memory records.

The implementation must not target a proposed Align surface. The owned JSON route below becomes
implementable only after Align Request 9 reaches `ALIGN_MERGED` at a named commit and its
align-llm adoption gate passes. Until then this file is a design and adoption contract, not an
implementation interface.

## 1. Goal, gate, and boundaries

### 1.1 Goal

The capability proves all of the following in one reproducible client path:

1. A JSON input is decoded into a declared record whose retained text fields are owned
   `string` values, not borrowed `str` views.
2. The input `string` and every decoder-owned view are dropped before the retained verification
   result is read, moved, encoded, or returned from the decoding phase.
3. The result is serialized as a versioned, canonical JSON artifact with a content-bound digest.
4. The original input file may be removed before the result is verified; verification reads only
   the persisted artifact.
5. A deterministic differential/property corpus detects boundary mistakes in the algorithm and
   distinguishes a valid semantic `FAIL` result from a malformed artifact.

The primary C7-PersistedResult metric is a passing lifetime-and-integrity gate: all required
ownership, wire, malformed-input, invariant, and differential cases pass, including the source
deletion case and the intentionally mutated upper-bound case. The capability makes no speed claim.

### 1.2 In scope

- The two CLI commands and two module functions in §3.
- One input record and one persisted result record in §4.
- The fixed `bounded-bucket-v1` algorithm in §5.
- Canonical JSON, SHA-256 identity, deterministic validation, and failure behavior in §§6–9.
- Checked-in bounded functional and focused qualification runners, with aggregate admission decided
  by measured cost and the policy in §12.
- Request 9 adoption evidence for the exact direct owned fields used by these records.

### 1.3 Explicitly out of scope

- C6 result/evidence records, C6c1/C6c2, provider responses, failure memory, or prompt artifacts.
- Nested records, `array<Struct>`, `Option<MoveStruct>`, unions, enums, `array<string>`, or any
  other recursive owned graph. Request 9 may ship those capabilities for other consumers; this
  first C7 consumer uses only direct `string` and direct `Option<string>` fields.
- A dynamic JSON value type, reflection, a private JSON parser, JSON fragment concatenation, or a
  second wire format.
- Coverage-guided fuzzing, a generic mutation engine, arbitrary algorithm registration, product
  process execution, network access, repository inspection, or model/provider calls. The compiler
  and temporary product processes used only by the external acceptance harness are specified in
  §9.4 and are not product behavior.
- Atomic publication, exclusive creation, no-replace rename, crash recovery, or concurrent
  same-path writers. The current `std.fs.write_file` whole-file boundary is used with the limits
  stated in §9. Request 14 remains a separate publication capability.
- A benchmark claim or performance threshold. A later claim-specific benchmark owns that work;
  this capability records no elapsed time in the artifact and must not be used to claim a speedup.

### 1.4 Gate statement

The C7-PersistedResult adoption gate passes only when:

- the pinned or newly adopted Align release accepts the exact owned record declarations and raw
  `Result<OwnedRecord, Error>` transfer cases;
- a valid artifact remains verifiable after its input file is removed;
- the canonical wire and digest vectors match independently generated expected bytes;
- the deterministic boundary corpus, generated differential corpus, malformed-byte corpus, and
  artifact-mutation corpus all produce their exact statuses and errors;
- a temporary source mutation that changes the upper-bound comparison is detected by the gate;
- focused and per-unit checks cover the changed owners, the qualification command covers the full
  algorithm-testing corpus, and one aggregate integration run passes without requiring that full
  corpus to become a permanent aggregate dependency; and
- the acceptance environment is the minimum pinned Align environment named in §11.

An artifact with a semantic `FAIL` is a valid persisted value but is not a passing verification
command. The gate must check both facts: the artifact can be decoded and its invariants can be
verified, while the command exits unsuccessfully for the failed semantic result.

## 2. Prerequisites and source-of-truth agreement

### 2.1 Current repository evidence

The current code does not satisfy this contract:

- `src/result.align::GenerationRecord` contains borrowed `str` fields and `save` immediately
  encodes the record. It is the provider-independent C1 format, not the C7 artifact schema.
- `src/eval.align::TaskSpec` and `TaskResult` use borrowed views and keep decode/use in one scope.
  Its existing round trip is valuable C0 evidence but does not prove an owned result survives the
  input lifetime.
- `src/verification_loop.align::VerificationResult` owns a rendered JSON document, but it is
  assembled as a string and is not a retained declared record reloaded and independently verified.
- The current pinned Align JSON path accepts the borrowed declared-record shapes. Request 9 is the
  recorded Align boundary for the direct owned `string` and `Option<string>` fields required here.

No existing result format is silently extended. A future implementation may share small validation
helpers with existing modules only when the helper has one owner and the wire/schema contract below
remains authoritative.

### 2.2 Align prerequisites

The first consumer depends on these exact conditions:

| Prerequisite | Required state | C7 consequence |
| --- | --- | --- |
| Request 7, `core.json` escape grammar | `ALIGN_MERGED` at a named commit, with its original align-llm acceptance gate passing | The C7 `note` vectors may contain escaped controls, embedded NUL, and multibyte UTF-8. C7 does not reimplement or redefine the grammar. |
| Request 9, owned direct JSON fields | `ALIGN_MERGED` at a named Align commit, with its managed pinned release compiler/runtime materialized | C7 may use only the shipped direct `string` and direct `Option<string>` shapes named in §4. |
| Align memory-model update required by Request 9 | Merged with Request 9 or an explicitly named prerequisite commit | The decoder may materialize a free-standing owned record inside the helper scope and return it after the input owner expires. |
| `.align-revision` and fresh compiler topology | Updated only after the common topology design/implementation prerequisites, then verified through `make ci` | No C7 implementation or adoption evidence may use an unpinned newer sibling checkout. |

Request 9 is `ALIGN_MERGED` at Align PR #852 (`2bb93a93a2f30da1daabd5b65d83863dab617560`), and
its managed pin and C7 adoption fixture remain pending. It is the current blocking prerequisite for
C7-PersistedResult implementation/adoption while independent platform work remains available. No
compatibility layer or hypothetical API is permitted.

### 2.3 Source-of-truth ledger

| Decision | Authoritative source | Required agreement |
| --- | --- | --- |
| Roadmap purpose and C7 ordering | `docs/specs/roadmap.md` §C7 | This document refines only the named first consumer and does not advance C6. |
| Algorithm-verifier categories | `docs/specs/align-llm.md` §10.4 | The qualification runner implements deterministic property-like generation, differential comparison, invariant checks, boundary checks, and a mutation check; generic fuzz/benchmark infrastructure remains deferred. |
| Owned JSON field formation and Move behavior | Align Request 9 and the shipped Align compiler/tests at its adoption commit | C7 uses no unshipped field shape and does not copy Request 9's implementation into align-llm. |
| JSON lexical grammar and escaping | Request 7's merged Align design/implementation | C7 golden vectors are consumers of that grammar, not a second grammar. |
| Ordinary file reads/writes and errno mapping | `../align/docs/guide/13-std-os.md` and shipped `std.fs` | C7 uses `read_file` and `write_file`; it claims neither bounded read allocation nor atomic publication. |
| SHA-256 and lowercase hex | shipped `std.crypto.sha256` and `std.encoding.hex_encode` | The implementation uses the standard-library operations; it does not self-host a digest. |
| Make aggregate topology | `docs/specs/check-gate-topology.md`, `Makefile`, and its identity-bound oracle | Focused qualification remains outside aggregates. If measured evidence admits the bounded functional smoke, update the Make list, topology oracle, runner, and affected baseline together. |
| Project continuity | `HANDOFF.md` | Record durable capability checkpoints, the active blocker, exact next step, and latest relevant verification without duplicating transient PR evidence. |

## 3. Public contract ledger

The following is the single public-contract ledger. All prose and acceptance rows below must agree
with it. `str` in a signature is a borrowed call view; it is never retained by either function.
`VerificationSummary` contains only Copy fields so the public functions do not expose a Move record
through an unadopted result boundary.

### 3.1 Module API

```align
pub VerificationStatus { Pass, Fail }

pub VerificationSummary {
  status: VerificationStatus,
  expected: i64,
  observed: i64,
}

pub fn persist_file(input_path: str, output_path: str) -> Result<VerificationSummary, Error>
pub fn verify_file(result_path: str) -> Result<VerificationSummary, Error>
```

The declarations above are design notation until Request 9 and the C7 implementation gate are
complete. The positional calls are intentionally shown separately:

```align
summary := persisted_result.persist_file(input_path, output_path)?
checked := persisted_result.verify_file(output_path)?
```

The implementation syntax fixture must keep these declarations and calls separate and run the
pinned `alignc fmt` parser-only check before any implementation code is accepted. It must not use
expression-position type arguments or invent an `Owned*` JSON marker type.

### 3.2 CLI surface

| Command | Exact arguments | Success | Semantic failure | Malformed/I/O failure | Side effects |
| --- | --- | --- | --- | --- | --- |
| `./main --persist-result INPUT_JSON RESULT_JSON` | Exactly two explicit paths | Writes and reloads a valid `C7_PersistedResult` with `status: "PASS"`; prints the summary block in §3.3; exits 0 | Writes and reloads a valid artifact with `status: "FAIL"`; prints the summary block; exits with the normal `Error.Invalid` failure path after a successful `fs.write_file` call | Returns the mapped `Error` before result publication for validation/decode failures; a write failure may leave the caller-owned destination absent or partial as stated in §9 | Reads `INPUT_JSON`, writes `RESULT_JSON`, then reads `RESULT_JSON`; never reads the input again during verification |
| `./main --verify-result RESULT_JSON` | Exactly one explicit path | Reads a valid `C7_PersistedResult` with `status: "PASS"`; prints the summary block; exits 0 | Reads a valid artifact with `status: "FAIL"`; prints the summary block and exits with `Error.Invalid`; never writes | Returns the mapped `Error`; never writes or removes any path | Read-only |

The CLI pre-dispatch contract is exact. `args[0]` is the executable name and is not interpreted as
a mode. With no mode argument, the existing help path prints help and returns `Ok(())`. A C7 mode
is selected only when `args[1]` is exactly `--persist-result` or `--verify-result`; the former
requires `args.len() == 4` and the latter requires `args.len() == 3`. Missing or extra arguments,
including a second C7 selector in an operand position, return `Error.Invalid` before path
validation or any file operation. An unrecognized first selector, including an unknown flag,
follows the existing `main` dispatcher: it prints the current help block and returns `Ok(())`,
with no C7 output or filesystem side effects. This compatibility rule is intentional; C7 does not
change unrelated unknown-selector behavior. Existing recognized non-C7 selectors retain their
existing owner and arity rules. The validation order is therefore: selector and exact arity,
path lexical bounds and exact-path overlap, then the operation-specific file work. No C7 mode is
combined with another mode, and no option parser consumes a path operand as a hidden flag.

No CLI option, environment variable, provider setting, locale, current-time field, random seed,
or implicit algorithm selector changes behavior. Relative paths are interpreted by `std.fs` from
the caller's current working directory; no home expansion, environment expansion, or path
normalization is performed. The path strings are not persisted in the artifact.

Both input and output paths must be nonempty UTF-8 strings of at most 4,096 bytes and must contain
no embedded NUL. Exact byte-identical input/output path strings are rejected before any file
operation. The 4,096-byte path limit is an application validation bound, not a promise that every
host filesystem accepts every path of that length.

The API returns `Ok(VerificationSummary)` for both `PASS` and valid semantic `FAIL`. Only malformed
input, invalid artifact/invariant data, path validation, or an operating-system failure returns
`Err`. The CLI maps a returned `Fail` summary to its existing `Error.Invalid` process exit after
printing it. This preserves the distinction between a valid negative measurement and a malformed
record.

### 3.3 Stable CLI summary

For a successful API call, the CLI prints exactly these logical lines through the existing `print`
primitive, in this order, with one newline per line:

```text
persisted-result:
status:
PASS | FAIL
expected:
<decimal i64>
observed:
<decimal i64>
```

The `PASS | FAIL` line and the two decimal values are the only result fields printed. Normal Align
error reporting remains the source of truth for `Err`; C7 does not add a second diagnostic grammar.

### 3.4 Ledger dimensions

| Surface dimension | Contract | Owner | Acceptance |
| --- | --- | --- | --- |
| Exact command/API | §3.1–§3.2 only; no aliases | `src/persisted_result.align`, `src/main.align` | `c7-persisted-result-cli-smoke`, syntax fixture |
| Input/defaults | Explicit paths; no defaults; fixed `bounded-bucket-v1`; no ambient options | `src/main.align`, `persist_file` | CLI arity and option-isolation rows |
| Status/errors | `PASS`/`FAIL` are valid data; `Err` is malformed/I/O; CLI maps valid `FAIL` to nonzero | module API and main adapter | semantic-fail and malformed-artifact rows |
| Ownership/lifetime | Owned record survives raw input/artifact source expiry; public summary is Copy | Request 9, `src/persisted_result.align` | lifetime, move, source-drop, and `check-per-unit` rows |
| Allocation | Request 9 owns direct text materialization; existing whole-file `std.fs` owns read/write buffers; no private collection | Align Request 9 and `std.fs`; C7 module owns only record construction | allocation-transfer and no-private-parser review/adoption |
| Persisted identity | `input_sha256` binds exact canonical input bytes; `content_sha256` binds the result preimage; no cache identity | `src/persisted_result.align` | golden digest and digest-mutation rows |
| Schema version | Both records use `schema_version: 1`; any field/order/type change requires a new version | artifact owner | schema/version/order mutations |
| Validation order | §8 tables are deterministic and side-effect ordered | module owner | first-failure corpus with exact error class/absence |
| Implementation owner | `src/persisted_result.align` owns records, algorithm, digest, and file orchestration; `src/main.align` owns CLI dispatch/output; runner owns independent reference and mutation harness | named modules | matrix-to-diff pass |
| Prerequisite gate | Request 9 named Align commit plus rebuild, `.align-revision`, adoption target, and `make ci` | Align request owner and C7 adoption owner | adoption gate |
| Acceptance metric | Passing lifetime/integrity/differential/mutation gate; no speed claim | C7 runner | §12 exact cases |
| Cache identity | N/A: C7 introduces no application cache and does not change Align compiler cache policy | N/A with reason | no cache behavior is claimed |
| CLI/build input explicitness | CLI paths and `ALIGNC`/compiler pin are explicit build inputs; no runtime env | `src/main.align`, Make adoption | option/environment matrix |
| Persisted wire | Canonical UTF-8 JSON, declaration order, no final LF, exact digest preimage | `src/persisted_result.align` | independent byte vectors |

## 4. Declared records and wire schema

### 4.1 Input record

The input file is one canonical `C7_VERIFICATION_INPUT` record. Its exact declared shape is:

```align
C7VerificationInput {
  schema_version: i64,
  artifact_kind: string,
  case_id: string,
  algorithm: string,
  left: i64,
  right: i64,
  lower_bound: i64,
  upper_bound: i64,
  expected: i64,
  note: Option<string>,
}
```

The record has direct owned `string` and direct `Option<string>` fields only. It deliberately does
not use `str`, `array<string>`, nested records, or any other aggregate owner. `note: None` is
omitted by canonical encoding; `Some("")` is present as an empty JSON string.

### 4.2 Persisted result record

The result file is one canonical `C7_PERSISTED_RESULT` record:

```align
C7PersistedResult {
  schema_version: i64,
  artifact_kind: string,
  case_id: string,
  algorithm: string,
  status: string,
  left: i64,
  right: i64,
  lower_bound: i64,
  upper_bound: i64,
  expected: i64,
  observed: i64,
  input_sha256: string,
  note: Option<string>,
  diagnostic: Option<string>,
  content_sha256: string,
}
```

The exact canonical field sequence is the declaration sequence above. The output copies the input
case, algorithm, bounds, operands, expected value, and note; computes `observed`, `status`, and
`diagnostic`; and adds the two identity fields. It changes `artifact_kind` to
`C7_PERSISTED_RESULT`.

### 4.3 Scalar and text domains

| Field/group | Domain and validation |
| --- | --- |
| `schema_version` | JSON signed integer exactly `1`; no other version is accepted by v1. |
| `artifact_kind` | Input exactly `C7_VERIFICATION_INPUT`; output exactly `C7_PERSISTED_RESULT`. |
| `case_id` | ASCII bytes matching `[a-z0-9][a-z0-9._-]{0,63}`; no embedded NUL; no Unicode normalization or case folding. |
| `algorithm` | Exactly `bounded-bucket-v1`; arbitrary algorithm labels are not accepted. |
| `status` | Output exactly `PASS` or `FAIL`; input has no status. |
| `left`, `right` | Inclusive range `0..=1_000_000`. |
| `lower_bound`, `upper_bound` | Inclusive range `0..=2_000_000`; `lower_bound <= upper_bound`. |
| `expected`, `observed` | Inclusive range `0..=2`; these are bucket ordinals, not sums. |
| `note` | Optional valid UTF-8 `string`, at most 256 bytes. Embedded NUL, quotes, backslashes, controls, multibyte UTF-8, and empty `Some` are accepted and canonically escaped. |
| `diagnostic` | `None` for `PASS`; exactly `Some("expected does not match observed")` for `FAIL`. No caller-supplied diagnostic is accepted. |
| `input_sha256`, `content_sha256` | Lowercase ASCII hexadecimal, exactly 64 bytes. `content_sha256` is present in the result preimage as an empty string before it is finalized. |
| Paths and canonical bytes | Paths are at most 4,096 bytes. Canonical input and result bytes are at most 4,096 bytes after whole-file read/encode; this is a semantic bound, not a bounded-allocation guarantee for `std.fs.read_file`. |

The integer bounds make `left + right` at most `2_000_000`, so the algorithm's addition is
mathematically and machine-wise within the declared `i64` range. The bounds are checked before the
addition; no unchecked derived count or multiplication is introduced. The input and output JSON
decoders still reject wrong JSON shapes, fractional numbers, overflowed integer literals, duplicate
declared keys, malformed escapes, malformed UTF-8, and trailing non-whitespace bytes according to
the adopted Align JSON grammar. Application-level canonical-byte comparison additionally rejects
unknown fields, key reordering, leading/trailing whitespace, and a `null` spelling for either
optional field.

### 4.4 Canonical wire contract

- The file is UTF-8 JSON bytes produced by the declared-record `json.encode` path.
- There is no leading/trailing whitespace and no final newline.
- Object fields appear in declaration order.
- `Option.None` fields are omitted; `Option.Some("")` is present.
- Strings use the adopted JSON escape grammar. In particular, the semantic NUL byte is encoded as
  `\u0000`; a slash need not be escaped; valid non-ASCII UTF-8 is emitted according to the
  adopted encoder's canonical behavior.
- Numbers are the canonical decimal encoding of their declared signed `i64` values; no float or
  string-number fallback exists.
- A decoded record is re-encoded and compared byte-for-byte with the source bytes. This application
  check makes the artifact contract stricter than the core decoder's unknown-field ignore behavior;
  it prevents two byte representations from sharing one content identity.
- A duplicate declared key is rejected by the adopted JSON decoder before canonical comparison.

Normative input/output golden vectors are generated and checked independently in the adoption
runner. The minimum text vector contains the escaped-control, embedded-NUL, and UTF-8 note shown
in the exact byte vectors below. The optional-state vectors separately cover missing `note`,
`Some("")`, and `Some` with the text vector. These bytes must not be hand-assembled by
concatenating JSON fragments in Align.

The first normative byte vector is:

```text
input bytes:
{"schema_version":1,"artifact_kind":"C7_VERIFICATION_INPUT","case_id":"upper-equal","algorithm":"bounded-bucket-v1","left":4,"right":5,"lower_bound":0,"upper_bound":9,"expected":2,"note":"quote:\" slash:/ backslash:\\ controls:\\b\\f\\n\\r\\t NUL:\u0000 emoji:😀"}
input_sha256: 6de733d453b56f83c4dbe11406e72996cc52a3a236b8d221d383133b77bb89d2

result preimage bytes:
{"schema_version":1,"artifact_kind":"C7_PERSISTED_RESULT","case_id":"upper-equal","algorithm":"bounded-bucket-v1","status":"PASS","left":4,"right":5,"lower_bound":0,"upper_bound":9,"expected":2,"observed":2,"input_sha256":"6de733d453b56f83c4dbe11406e72996cc52a3a236b8d221d383133b77bb89d2","note":"quote:\" slash:/ backslash:\\ controls:\\b\\f\\n\\r\\t NUL:\u0000 emoji:😀","content_sha256":""}
content_sha256: a0160d3677ecac64c1682e3802e01462e178412702a8ca1cdf6c55c5841b379a

result bytes:
{"schema_version":1,"artifact_kind":"C7_PERSISTED_RESULT","case_id":"upper-equal","algorithm":"bounded-bucket-v1","status":"PASS","left":4,"right":5,"lower_bound":0,"upper_bound":9,"expected":2,"observed":2,"input_sha256":"6de733d453b56f83c4dbe11406e72996cc52a3a236b8d221d383133b77bb89d2","note":"quote:\" slash:/ backslash:\\ controls:\\b\\f\\n\\r\\t NUL:\u0000 emoji:😀","content_sha256":"a0160d3677ecac64c1682e3802e01462e178412702a8ca1cdf6c55c5841b379a"}
result_sha256 (external check only): 8fb29a7205886c45cff455b3061c605c83afc5e8fd3be58f37c00fa8d997fab5
```

`result_sha256` in this fixture is an independent test assertion over the exact file bytes; it is
not a field in `C7PersistedResult` and is not used as the persisted identity.

## 5. Algorithm and verification invariants

### 5.1 Fixed algorithm

`bounded-bucket-v1` is intentionally small enough that the acceptance runner can implement an
independent reference without sharing Align code:

```text
raw := left + right
if raw < lower_bound: observed := 0
else if raw < upper_bound: observed := 1
else: observed := 2
status := PASS iff observed == expected, otherwise FAIL
diagnostic := None for PASS, Some("expected does not match observed") for FAIL
```

The implementation validates all ranges before computing `raw`. The exact comparison operators are
part of the algorithm contract: values below the lower endpoint are bucket `0`, values at or above
the lower endpoint but below the upper endpoint are bucket `1`, and values at or above the upper
endpoint are bucket `2`. Equality at the lower endpoint must enter bucket `1`; equality at the upper
endpoint must enter bucket `2`. A mutation that changes the second strict `<` comparison to `<=`
therefore misclassifies the upper-equality case and is required to be detected by the boundary
corpus.

### 5.2 Result invariants

`verify_file` must recompute and require all of these, in order:

1. The output schema, kind, algorithm, status, field domains, and digest lexical forms are valid.
2. `content_sha256` equals SHA-256 of the canonical result with its own digest field set to `""`.
3. The raw result bytes equal the canonical encoding of the decoded result with the actual digest.
4. `observed` equals the bounded-bucket reference calculation.
5. `status` equals `PASS` exactly when `observed == expected` and `FAIL` otherwise.
6. `diagnostic` matches the status rule exactly.

The verifier never trusts `status`, `observed`, `diagnostic`, or either digest merely because the
fields are present. It recomputes the content digest and algorithm relation from the decoded
fields. It does not reload `input_sha256`'s source path; the input digest is an identity claim about
the original canonical bytes, while the result's own content digest protects the persisted claim.

### 5.3 Identity contract

| Identity | Meaning | Not meaning |
| --- | --- | --- |
| `case_id` | Human-selected bounded label used to name a fixture | Not a content identity and not a cache key |
| `algorithm` | Nominal algorithm/version selector; v1 has one accepted value | Not permission to dispatch arbitrary code |
| `input_sha256` | SHA-256 of the exact canonical input file bytes, before the input owner expires | Not a digest of a normalized semantic record or a path |
| `content_sha256` | Structural identity of the complete result record with the digest field blanked | Not a digest of only the observed value and not a signature |
| Schema identity | `schema_version`, artifact kind, declaration order, declared scalar widths, optional-field omission, and canonical encoding together | Not a nominal type name alone |
| Application cache identity | N/A; no cache is introduced | No path, timestamp, process ID, compiler path, or ambient environment is persisted |

Changing any reachable result field, its order, its scalar width, its optional encoding, or the
algorithm version changes the structural identity. A schema or wire change increments
`schema_version` rather than relying on a digest mismatch to provide compatibility.

## 6. Ownership, lifetime, and allocation contract

### 6.1 Required source/lifetime sequence

The implementation must use a helper boundary equivalent to this sequence:

1. `decode_input(path)` owns the `string` returned by `fs.read_file`.
2. The owned JSON decode creates a free-standing `C7VerificationInput` whose direct text fields
   do not borrow that input. The raw `Result<C7VerificationInput, Error>` transfer is consumed by
   the helper's caller using the adopted Request 9 Move carrier.
3. The helper returns only after its input `string` owner has been dropped. The caller is forbidden
   to keep a `str` view into that owner.
4. `persist_file` validates and consumes the owned input record. It moves the surviving fields into
   `C7PersistedResult`; it does not clone every field merely to hide ownership.
5. `json.encode` returns a borrowed canonical `str` view. Before hashing a result preimage or
   passing final bytes to `fs.write_file`, the caller explicitly invokes `canonical.clone()` and
   owns the resulting free-standing `string` until that one digest or write call completes. The
   borrowed view never escapes the encoder scope. The preimage clone is dropped immediately after
   `crypto.sha256`; the final-output clone is dropped after `fs.write_file`, including its failure
   path. This is the explicit persistence boundary required by Request 9.
6. Digest arrays and hex strings are consumed within their owner scopes; no `str` returned by
   `json.encode` is stored in the result record or returned from a function. The final result is
   written, the in-memory result owner is released at the publication boundary, and `verify_file`
   reads a fresh artifact owner.
7. `verify_file` decodes an independently owned result, drops the raw artifact input before
   recomputing the algorithm, and returns only the Copy summary.

The acceptance fixture must delete or rename the original input after `persist_file` returns and
before invoking `--verify-result`. A passing verification in that state is the required observable
proof that no result field still points into the input document.

That file-deletion check is not a substitute for the in-memory lifetime proof. The C7-A adoption
fixture must bind the owned decode result, end or explicitly drop the helper's input `string`
owner, and only then read or move every direct `string` and `Option<string>` field from the
retained record. It must exercise both `Some(empty)` and a non-empty escaped/NUL/UTF-8 value after
the source owner expires, plus the raw `Result<C7VerificationInput, Error>` return/parameter path.
The named regression is `c7-owned-record-source-expiry-adoption`; the later C7 persistence smoke
adds the file-deletion/reload proof but cannot replace this direct adoption fixture.

### 6.2 Ownership closure rules

| Value | Owner and lifetime | Move/borrow rule |
| --- | --- | --- |
| CLI path arguments | `main(args)`/argv; borrowed `str` views | Passed to calls only; never stored in a record. |
| `fs.read_file` input | Owned `string` in `decode_input` | Borrowed only during decode/hash; dropped before owned input is returned. |
| `C7VerificationInput` | Request 9 owned direct fields | Move into result construction or drop on every invalid/early path. |
| `json.encode` output | Borrowed encoder `str` view plus an explicit caller-owned `string` clone | The view is consumed only in the encoder scope; `canonical.clone()` is the sole value passed to `crypto.sha256` or `fs.write_file`, and that clone is dropped after the operation. |
| SHA-256 digest | Owned `array<u8>` from `std.crypto` | Sliced only for `hex_encode`; dropped after hex string creation. |
| `input_sha256`/`content_sha256` | Owned `string` fields | Moved into the result; replacement of the blank content digest drops the old owner exactly once. |
| `C7PersistedResult` | Move record with direct owned fields | Dropped on malformed/invariant/write/reload failure; moved only into the explicit next owner. |
| Reloaded artifact | New owned `string` plus owned result record | Raw bytes expire before verification; no input/result alias is permitted. |
| `VerificationSummary` | Copy enum and `i64` fields | Safe to return through `Result`; owns no allocation. |

No hidden arena, private vector, shallow byte copy, implicit clone, global owner, or process-global
artifact cache is allowed. Allocation failure follows the current Align terminal allocation policy;
the C7 contract does not promise a recoverable `Error` after an allocator abort. Recoverable JSON,
field, digest, and filesystem errors must release all ordinary live owners on their return path.

### 6.3 Construction and control-flow requirements

The implementation and adoption fixtures must cover the affected forms explicitly:

- declaration and direct construction of both records;
- decode success and failure with `?`;
- raw `Result<C7VerificationInput, Error>` binding, parameter transfer, return, reassignment,
  and explicit typed `map_err` transfer as allowed by Request 9;
- move-in of each owned field, source nulling, result return, and `Drop`;
- digest field replacement and result drop on a write or verification error;
- early returns for every validation phase;
- malformed JSON after a text owner is live and malformed artifact after the result owner is live;
- branch joins for `PASS`/`FAIL` diagnostic construction and loop joins in the external runner;
- no `continue`-specific Align case is claimed; the current Align language has no `continue`
  construct.

## 7. Persistence boundary and publication limitations

`persist_file` validates the complete input, computes and verifies the complete result in memory,
then calls the shipped `std.fs.write_file` once with the final canonical bytes. It does not write a
temporary file, append, concatenate fragments, or publish a pair. The current `write_file` contract
creates/truncates the destination and may leave a caller-owned destination absent or partial if the
underlying write fails. C7 returns the mapped error and performs no hidden remove or restoration.

The caller must provide a fresh destination path distinct from the input path. The implementation
rejects equal path strings before reading or writing. It does not promise physical alias detection
through symlinks, hard links, or different relative spellings, and it does not coordinate concurrent
writers. Those are explicit unsupported caller conditions, not silently accepted atomicity claims.
`verify_file` is read-only and never removes a malformed artifact.

This limitation is acceptable for the first local fixture consumer because the adoption runner owns
a fresh temporary directory and serializes one result per destination. A later
artifact-publication capability must adopt the reviewed exclusive-create/no-replace surface before
making stronger guarantees.

## 8. Deterministic validation and error precedence

### 8.1 `persist_file` order

The first applicable row wins. No output write occurs before row 10 completes.

| Order | Validation/action | Failure |
| ---: | --- | --- |
| 1 | Check nonempty input/output paths, UTF-8, no NUL, maximum path byte length, and exact-string distinctness | `Error.Invalid`; no read/write |
| 2 | Read the input file as UTF-8 using `fs.read_file` and reject raw input bytes above 4,096 | mapped filesystem error or `Error.Invalid`; no output write |
| 3 | Decode the expected `C7VerificationInput` with Request 9's owned direct-record path | `Error.Invalid`; input/result owners clean up |
| 4 | Re-encode the decoded input and compare exact bytes, including declaration order and optional omission | `Error.Invalid`; unknown fields, reordered keys, whitespace, or noncanonical optional spelling |
| 5 | Validate input schema/kind, identifier, algorithm, numeric ranges, bound ordering, and note byte length in declaration order | `Error.Invalid`; no algorithm or output side effect |
| 6 | Compute `input_sha256` over the exact canonical input bytes | standard-library digest operation; no recoverable digest error is claimed |
| 7 | Compute bounded-bucket `observed`, status, and diagnostic after all bounds pass | `Error.Invalid` only if an internal invariant is impossible; semantic mismatch is valid `FAIL` |
| 8 | Construct the result by moving owned fields and setting `content_sha256: ""` | owner cleanup on any construction/branch failure |
| 9 | Encode the blank-digest preimage and compute lowercase SHA-256; replace the digest field | `Error.Invalid` for an impossible digest-shape/invariant; digest arrays/temporary views clean up |
| 10 | Encode the final result and validate its canonical byte shape/size before publication | `Error.Invalid`; no output write |
| 11 | `fs.write_file(output_path, final_bytes)` | mapped filesystem error; destination state follows §7 |
| 12 | Release the original result owner and reload through `verify_file` | mapped/read/invalid error; destination is retained for inspection |

The application enforces the 4,096-byte canonical record bound after input read and after final
encode. It must not call that post-read check a memory-safety cap for `fs.read_file`, which is
deliberately whole-file and unbounded in the current standard-library surface. If an untrusted
bounded-read contract is needed, it is a separate Align request rather than a hidden C7 workaround.

### 8.2 `verify_file` order

`verify_file` has no write or delete side effect.

| Order | Validation/action | Failure |
| ---: | --- | --- |
| 1 | Validate the one nonempty, UTF-8, NUL-free result path | `Error.Invalid` |
| 2 | Read the artifact as UTF-8 using `fs.read_file` and reject raw artifact bytes above 4,096 | mapped filesystem error or `Error.Invalid` |
| 3 | Decode `C7PersistedResult` through the owned direct-record path | `Error.Invalid` |
| 4 | Check schema version, artifact kind, algorithm, status, and digest lexical shapes | `Error.Invalid`; unrecognized v1 data is not interpreted |
| 5 | Clear only the in-memory `content_sha256`, canonical-encode the preimage, hash it, and compare the supplied digest | `Error.Invalid`; do not trust any semantic field from a digest mismatch |
| 6 | Restore the supplied digest, canonical-encode the full record, and compare exact bytes with the file | `Error.Invalid`; rejects unknown fields, key/order changes, whitespace, and optional `null` |
| 7 | Validate numeric domains, bound ordering, note/diagnostic domains, and input digest format | `Error.Invalid` |
| 8 | Recompute bounded-bucket `observed` and compare it with the stored value | `Error.Invalid` |
| 9 | Recompute status and diagnostic from expected/observed and compare exactly | `Error.Invalid` for contradiction; otherwise return `Ok(Summary{PASS|FAIL})` |

This order ensures content identity and canonical bytes are checked before a persisted status or
measurement is accepted. A valid `FAIL` reaches row 9 and returns a summary; it is not a malformed
artifact.

### 8.3 Error/result matrix

| Input/artifact condition | Artifact written by `persist_file` | API result | CLI status/exit | Cleanup/ownership |
| --- | --- | --- | --- | --- |
| Valid input, expected equals observed | Yes, canonical PASS | `Ok(PASS)` | PASS / 0 | All source views expire before reload |
| Valid input, expected differs | Yes, canonical FAIL | `Ok(FAIL)` | FAIL / nonzero `Invalid` | Result is retained for inspection; no source view remains |
| Empty/malformed/noncanonical input | No new write | `Err(Invalid)` | normal error / nonzero | Partial decoded owners drop; existing destination is not touched |
| Invalid field/schema/range | No new write | `Err(Invalid)` | normal error / nonzero | No algorithm or output side effect |
| Input read failure | No new write | mapped `Err` | normal error / nonzero | No result owner exists |
| Output write failure | Destination may be absent/partial | mapped `Err` | normal error / nonzero | No hidden cleanup; caller owns destination state |
| Missing/malformed/noncanonical result | N/A | `Err` | normal error / nonzero | Verify is read-only; source bytes/result owners drop |
| Digest or invariant mutation | N/A | `Err(Invalid)` | normal error / nonzero | Verify is read-only and does not repair |

## 9. Options, concurrency, and process boundaries

### 9.1 Configuration isolation

There are no runtime options or environment variables. The option-state Cartesian product is a
single state: `NO_OPTIONS`. The adoption runner must prove both directions where applicable:

- setting unrelated environment variables, locale variables, provider credentials, or C7-looking
  names does not change the bytes, status, or error precedence;
- every documented input path and the exact selected `ALIGNC` build input is passed explicitly and
  is not replaced by an environment fallback.

`ALIGNC`, `.align-revision`, and the sibling compiler path are build/test inputs owned by Make and
the adoption runner, not runtime configuration read by `src/persisted_result.align`. No result field
contains a compiler path, current time, PID, CWD, or host identity.

### 9.2 Same-process entrypoint matrix

The module has two public operations and no aggregate operation, global registry, or shared cache.
The matrix is still explicit:

| Combination | Policy | Required evidence |
| --- | --- | --- |
| `persist_file` + `persist_file`, distinct input/output paths | Supported when calls are serialized or independent destinations are used | `c7-persisted-result-independent-destinations-smoke` |
| `verify_file` + `verify_file`, same or distinct path | Same-path concurrent reads are read-only and logically safe; file replacement during a read is outside the contract | read-only repeated verification row |
| `persist_file` + `verify_file`, distinct paths | Supported when the result path is not being replaced by another call | lifetime smoke |
| Any pair sharing a destination path with an overlapping write/read | Unsupported caller behavior; no lock or last-writer guarantee | explicit negative documentation row; no false success claim |
| Any API operation + a future aggregate operation | N/A: C7-PersistedResult adds no aggregate API; a later aggregate must extend this matrix before implementation | design update required before that milestone |

Separate processes with distinct input/output paths are supported. Separate processes sharing an
output path are unsupported. The adoption runner serializes all calls and uses a fresh temporary
directory, so the gate does not turn an unsupported race into evidence.

### 9.3 Product-process boundary

`persist_file` and `verify_file` use only `std.fs`, `core.json`, `std.crypto`, and
`std.encoding`. The product API does not launch processes, open network connections, read
environment variables, inspect repositories, or invoke providers. Consequently there is no child
timeout, product-child stdout/stderr capture, credential lifetime, or external helper contract in
this slice; each is `N/A` with this reason rather than an omitted decision.

### 9.4 Acceptance-runner process boundary

The algorithm-testing gate is deliberately different from the product-process boundary: the
Python 3.12 acceptance harness launches only the compiler and product executables. The bounded
functional smoke and full qualification runner have `build` prerequisites and resolve compiler and
product paths before any temporary `cwd` change, so neither takes user-supplied arguments:

```text
persisted-result-smoke: build
  -> resolve the selected compiler at the repository root
  -> ./scripts/run-persisted-result-smoke "<selected-compiler>" "<absolute-project-root>/main"

persisted-result-qualification: build
  -> resolve the selected compiler at the repository root
  -> ./scripts/run-persisted-result-qualification "<selected-compiler>" "<absolute-project-root>/main"
```

The resolution step follows the repository selection order at the repository root: authenticated
fresh compiler when required, explicit `ALIGNC`, explicit `ALIGN_REPO` release/debug compiler, then
the managed `.align-revision` release compiler. There is no implicit sibling or `PATH` fallback.
It resolves the selected executable with `realpath -e`, requires an absolute regular executable,
and passes that real compiler path to the runner. The default `scripts/alignc` wrapper is a
selector only; it is never passed to a child whose working directory changes, and it is never
allowed to rediscover a compiler from the temporary tree. A failed resolution is a harness error
before any temporary source or product child starts.

If measured evidence admits the bounded functional smoke to the Section 9 capable aggregate, its
ordinary selection is replaced by the controller-owned `/tools/fresh-alignc` launcher. The
qualification target remains focused and may use the same fresh profile when explicitly invoked.
Both runners must start
every child with `close_fds=True, pass_fds=()`; it must not resolve a sibling pathname, `sys.executable`,
or a host compiler from the temporary root. The mutation cases still pass the staged launcher as the
explicit compiler argv element, and the launcher opens the authenticated read-only
`/tools/fresh-descriptor`, `/tools/fresh-guard`, and compiler/archive bundle. The non-fresh hosted
profile retains the explicit real-path rule above.

For each qualification mutation case the qualification runner creates one `mkdtemp` root and preserves the repository source
layout below it: `<temporary-root>/src/main.align`, the reachable `src/*.align` modules, and the
temporary output remain in their corresponding relative locations. It replaces exactly one UTF-8
byte pattern in `<temporary-root>/src/persisted_result.align` (`else if raw < upper_bound` to
`else if raw <= upper_bound`), and invokes the compiler with the exact vector
`<selected-compiler> build <temporary-root>/src/main.align` and `cwd=<temporary-root>`; the
non-fresh profile substitutes the absolute real compiler path, while the Section 9 capable profile
uses `/tools/fresh-alignc` with the fixed read-only handoff files.
It then invokes the temporary executable with exactly `--persist-result <input> <result>` and
`--verify-result <result>`, one operation per child. The normal corpus invokes the already-built
absolute product path with the same two exact vectors and `cwd=<temporary-root>`.

The runner captures stdout and stderr separately with a 64 KiB limit per stream and applies a
fixed 60,000,000,000 ns timeout to each compiler or product child; timeout or capture overflow
enters terminate, kill-if-needed, wait, and close cleanup in that order and fails the gate. A
nonzero compiler status, unexpected product status/output, missing executable, or cleanup error
also fails the gate. The temporary root and all copied sources are runner-owned and are removed in
the enclosing `finally`; the repository source tree and checked-in fixtures are never mutated.

The product children run with an explicit environment map containing only `LANG=C`, `LC_ALL=C`,
`PATH`, and the exact linker/toolchain values supplied by the Align build gate (`LIBRARY_PATH`,
`LD_LIBRARY_PATH`, `PKG_CONFIG_PATH`, `LLVM_CONFIG`, and `LLVM_SYS_221_PREFIX` when required by
that target). All other inherited variables are cleared. The compiler path is passed as an
argument, not rediscovered from `PATH`; no C7 product option or ambient value crosses this
boundary. A missing required toolchain value or compiler path is a harness error before the first
child starts.

## 10. Acceptance contract and algorithm-testing gate

### 10.1 Independent reference

The acceptance runner owns a small independent reference implementation of the bounded-bucket
function. It must not import `src/persisted_result.align`, parse Align MIR, or derive expected
values from the produced artifact. Its integer arithmetic is Python's exact integer arithmetic after
the input-domain generator has enforced the C7 ranges.

The runner also owns an independent canonical-byte reference rather than calling Python's generic
JSON serializer. `quote_string` walks Unicode scalar values and emits the Request 7 grammar:
`\"`, `\\`, `\b`, `\f`, `\n`, `\r`, and `\t` use their short spellings; other U+0000 through
U+001F values use lowercase `\u00xx`; `/` and valid non-ASCII UTF-8 are emitted literally; invalid
UTF-8 and surrogate code points are rejected. `encode_input` and `encode_result` append fields from
literal ordered field tables, render integers with signed decimal notation, omit `None` optional
fields, emit `Some(empty)` as `""`, and add no whitespace or final LF. The result encoder has an
explicit `blank_content_sha256` mode for the preimage. These helpers are a separate Python
implementation of the fixed C7 field contract, not an import or wrapper around Align's encoder.
For every generated case the runner encodes the independent input, hashes those exact UTF-8 bytes
with `hashlib.sha256(...).hexdigest()`, constructs the independent result, hashes its blank-digest
preimage the same way, inserts that digest, and finally encodes and hashes the result bytes. The
fixed golden vector is checked both from its literal bytes and through these helpers; its external
`result_sha256` remains a test assertion, not a persisted field.

The deterministic generated corpus is:

- seed: decimal `20260803`;
- 256 PASS cases generated with `left/right` in `0..=1_000_000`, `lower_bound` in
  `0..=2_000_000`, `upper_bound` in `lower_bound..=2_000_000`, and `expected` set from the
  independent reference;
- 32 FAIL cases using the same generated operands and bounds, with `expected` changed to a
  different in-range value;
- the fixed boundary table below, which is not replaced by generated cases.

The runner compares every returned artifact's decoded fields, status, diagnostic, canonical bytes,
input digest, and content digest against the independent reference. It then removes the input and
invokes the standalone verifier on the result.

### 10.2 Boundary corpus

The checked-in acceptance fixture must include at least these exact cases:

| Case | `left` | `right` | `lower_bound` | `upper_bound` | `expected` | Purpose |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `zero` | 0 | 0 | 0 | 1 | 1 | Lower equality at zero enters the middle bucket |
| `lower-equal` | 2 | 3 | 5 | 9 | 1 | Equality at lower endpoint enters bucket `1` |
| `lower-below` | 1 | 1 | 5 | 9 | 0 | Strict lower boundary |
| `interior` | 4 | 3 | 0 | 9 | 1 | Interior bucket |
| `upper-equal` | 4 | 5 | 0 | 9 | 2 | Equality at upper endpoint enters bucket `2` |
| `upper-above` | 8 | 5 | 0 | 9 | 2 | At-or-above upper bucket |
| `operand-max` | 1_000_000 | 1_000_000 | 0 | 2_000_000 | 2 | Maximum safe addition |
| `single-point` | 7 | 0 | 7 | 7 | 2 | Equal bounds have no middle interval |
| `expected-mismatch` | 2 | 3 | 0 | 9 | 2 | Valid persisted FAIL and diagnostic; reference observed is `1` |

The `note` vector attaches the escaped-control/NUL/emoji text to `upper-equal`; separate copies
cover absent and empty optional notes. The input and expected output bytes for those cases are
committed only after the adopted Align encoder's exact canonical behavior is known.

### 10.3 Malformed and mutation corpus

The runner must exercise, with a fresh destination and an unchanged control file for each case:

- empty file, truncated object, wrong top-level shape, invalid UTF-8, malformed escape, lone or
  reversed surrogate, duplicate declared key, trailing non-whitespace bytes, unknown key,
  reordered key, leading/trailing whitespace, and `null` optional spelling;
- wrong schema/kind/algorithm, empty or invalid `case_id`, out-of-range operands/bounds/expected,
  reversed bounds, oversized note, wrong JSON scalar shape, and noncanonical digest spelling;
- result mutations for `content_sha256`, `input_sha256`, `observed`, `status`, `diagnostic`,
  `schema_version`, field order, unknown fields, whitespace, and optional-field presence;
- an exact temporary source mutation that changes the second strict upper comparison from `<` to
  `<=`, using the unique UTF-8 source pattern `else if raw < upper_bound` and replacing it with
  `else if raw <= upper_bound`. The mutation helper must assert that exactly one expected source
  byte pattern was replaced; a no-op or multiple replacement is a failed test, not a passing
  negative case. The mutated temporary compiler program must fail the `upper-equal` expected
  artifact/status assertion.

Every malformed input must fail before creating or changing its destination. Every malformed result
must fail read-only. Existing destination bytes are compared before and after invalid-input cases.

### 10.4 Property, differential, invariant, fuzz, and benchmark classifications

| C7 category | Capability treatment | Gate evidence |
| --- | --- | --- |
| Property-based testing | Deterministic generated domain corpus, seed and cardinality fixed in §10.1 | 256 PASS + 32 FAIL reference comparisons |
| Differential testing | Python reference calculation is independent of Align implementation | Per-case observed/status/diagnostic and digest comparison |
| Invariant checking | `verify_file` recomputes content identity, bounded bucket, status, and diagnostic | Result mutation corpus and standalone verifier |
| Fuzzing | Qualification-only deterministic byte mutations of valid input/result fixtures; no coverage-guided or unbounded campaign | Malformed/mutation corpus in §10.3 |
| Overflow/boundary check | Pre-addition range validation and exact lower/upper equality cases | Boundary table, max operand case, invalid range cases |
| Complexity/performance check | N/A for this capability; no performance-sensitive implementation or claim | A later C7 benchmark design must add baseline, hardware, sample count, and command before claiming regression/speed |

The runner may record wall-clock duration for diagnostics, but it must not persist it, compare it,
or describe it as a performance result. A future claim-specific benchmark must update this document or
supersede this section before adding a threshold.

## 11. Compatibility and adoption environment

The minimum C7 acceptance environment is the repository's pinned Align environment:

- `x86_64-unknown-linux-gnu` on Ubuntu 24.04;
- Rust 1.96 and LLVM 22 as required by the pinned Align release build;
- GNU Make 4.3 and Python 3.12 for the repository runner;
- Linux uses the Align CI's checksum-pinned OpenSSL 3.5.7 source build:
  `OPENSSL_VERSION=3.5.7`, SHA-256
  `a8c0d28a529ca480f9f36cf5792e2cd21984552a3c8e4aa11a24aa31aeac98e8e`,
  `./Configure --prefix="$OPENSSL_PREFIX" --libdir=lib shared no-tests`, `make`, and
  `make install_sw`; the resulting `LIBRARY_PATH`, `LD_LIBRARY_PATH`, and
  `PKG_CONFIG_PATH` are the only OpenSSL paths admitted to the runner;
- macOS uses the Align CI's native `openssl@3` Homebrew dependency and its
  `LIBRARY_PATH=$(brew --prefix openssl@3)/lib:$(brew --prefix zstd)/lib` setup;
- the exact Align revision recorded in `.align-revision`, materialized as the managed release
  compiler and runtime before adoption.

The common fresh-compiler topology in Section 9 of `docs/specs/check-gate-topology.md` is only the
Linux x86_64 platform profile. The sibling Align release targets `aarch64-unknown-linux-gnu` on
Ubuntu 24.04-arm and `aarch64-apple-darwin` on macOS 15 are required C7 acceptance environments,
not supplementary evidence, because Request 9 makes target-local natural ownership/layout behavior
part of its contract. Before either non-x86 environment can enter C7 adoption or provide C7 evidence,
it needs its own reviewed platform-profile design and implementation, including the compiler/runtime
construction, namespace or process boundary, toolchain inputs, and exact acceptance commands. The
x86_64 Section 9 profile is not evidence for either target. Each native environment must run the C7
focused target against a compiler and runtime rebuilt at the exact pinned revision after its own
profile passes. A newer compiler, host, or generic OpenSSL 3.0 installation is not a substitute for
the named build configurations. The C7 artifact itself contains no target or ABI field; the adoption
result is bound externally to the tested compiler revision, platform profile, and environment.

The target-local nature of Request 9's owned descriptor is Align's contract. C7 does not invent a
portable binary layout or compare compiler descriptors. Per-unit and whole-program checks must
prove the imported `persisted_result` interface is the same as the implementation unit on each
declared target.

## 12. Capability delivery and acceptance ownership

The historical C7-D/P/A/I1/I2/I3/G labels remain useful references for prerequisites and closure
cells, but they are not required branch or pull request boundaries. Delivery has two operational
boundaries:

1. **C7-P — target platform profiles.** A platform profile is independently installable and has a
   distinct host-image failure domain. Before C7 evidence is claimed on aarch64 Linux or aarch64
   macOS, that target's reviewed profile must be implemented, the sibling compiler/runtime rebuilt
   at the pinned revision, and the target-local profile gate passed. The x86_64 Section 9 profile
   cannot substitute for another target.
2. **C7-PERSISTED-RESULT — complete product consumer.** After Request 9 is `ALIGN_MERGED` and the
   applicable platform profile is available, adopt the exact owned-record surface and implement the
   records, decode/encode lifetime boundary, digest identity, algorithm, `persist_file`/
   `verify_file`, both CLI branches, stable summaries, persistence, and functional end-to-end smoke
   in one capability branch. The adoption fixture is an internal checkpoint of this consumer: if it
   fails against the shipped compiler, stop the dependent implementation without merging a dormant
   adoption-only change. The Section 9 image selects the fixed toolchain manifest and its signed run
   capsule binds the checked-out head and worker digest; caller overrides remain rejected.

The capability owns two deliberately different test classes:

- `persisted-result-smoke` is the bounded functional path: valid ownership/lifetime transfer,
  canonical encode/decode, source deletion, CLI success, semantic `FAIL`, and representative
  malformed input. It may join the core aggregate only after measured runtime and maintenance cost
  show that it remains a small stable integration regression.
- `persisted-result-qualification` owns the complete boundary corpus, generated differential
  corpus, artifact mutation, intentionally mutated source, target matrix, and any later fuzz,
  stress, or benchmark work. The capability pull request runs it, and its owning boundary runs it
  when changed, but it remains outside routine hosted/capable aggregates. Performance checks run
  only when making a performance claim.

At the named capability gate, run the focused module/per-unit checks, both commands above, the
applicable platform-profile acceptance, and one full Section 9 supervisor-attested `make ci` after
integration. Record exact results in the pull request; `HANDOFF.md` retains only the durable outcome
and next capability. Update the topology oracle and identity-bound baseline only if the bounded
functional smoke is actually admitted to an aggregate. C7 does not modify C6 code or consume C6's
blocked records.

### 12.1 Planned file ownership

| File/surface | Owner | Required change |
| --- | --- | --- |
| `src/persisted_result.align` | C7 implementation | Records, validation, digest, algorithm, file orchestration, ownership comments |
| `src/main.align` | CLI integration | Exact dispatch, summary, semantic-Fail exit mapping |
| `scripts/run-persisted-result-smoke` | C7 functional owner | Bounded CLI, lifetime, canonical artifact, source deletion, semantic-Fail, and representative malformed cases |
| `scripts/run-persisted-result-qualification` | C7 qualification owner | Independent reference, full generated/boundary/malformed/mutation corpus, target matrix, and optional claim-specific stress/benchmark cases |
| `eval/` C7 fixtures | Acceptance owner | Canonical boundary inputs/expected bytes only after adopted encoder behavior is fixed |
| `docs/examples/c7-persisted-result-syntax.align` | Syntax/adoption owner | Declarations and calls separately; parser-only check |
| `docs/examples/c7-persisted-result-lifetime.align` | Request 9 adoption owner | Direct source-owner expiry before every retained field read/move; parser/runtime adoption fixture |
| `Makefile` | Check-topology owner | Focused commands; aggregate inclusion only after the bounded-smoke admission decision |
| `scripts/check-gate-topology` | Topology oracle owner | Update only if aggregate membership changes |
| `docs/specs/check-gate-topology.md` | Topology design owner | Record the admission decision and baseline implications when applicable |
| `docs/align-development.md` | Developer-guide owner | Command and adoption instructions |
| `HANDOFF.md` | Continuity owner | Durable capability checkpoint, blocker, next action, and latest relevant evidence |

The C7 implementation must not add an Align request record inside the product implementation
commit. A newly discovered Align gap is recorded separately in `docs/align-requests.md` before
the dependent capability consumes it.

## 13. Closure matrix

The following matrix is the pre-implementation closure contract. Each applicable cell names the
future owner and an exact regression or benchmark. `DEFERRED` is an intentional design decision,
not a missing owner.

| Case | Applicable owner | Contract to close | Exact regression/measurement |
| --- | --- | --- | --- |
| Record type formation and direct field predicate | Align Request 9 adoption; `src/persisted_result.align` consumer | Admit only direct `string`/`Option<string>` plus Copy `i64`; reject borrowed/mixed/nested shapes before C7 allocation | `c7_owned_record_formation` in the Request 9 adoption target; C7 syntax fixture |
| CLI dispatch and malformed invocation | `src/main.align` | Select only the two exact C7 selectors, require exact arity, reject selector conflicts before path or file work, and preserve the existing help/`Ok(())` behavior for unknown first selectors | `c7-persisted-result-cli-smoke` covers no-mode help, both valid arities, missing/extra operands, unknown selectors, and conflicting C7 selectors |
| Input decode construction | `persisted_result.decode_input` | Decode one owned `C7VerificationInput`; raw result transfer is explicit | `c7-persisted-result-lifetime-smoke` |
| Result construction | `persisted_result.make_result` | Move text/options, compute scalars, initialize blank content digest | `c7-persisted-result-owned-move-smoke` |
| Input source expiry | Request 9 free-standing JSON allocation + `decode_input` | Drop input bytes before caller reads/moves input record; exercise every retained direct field after source expiry | `c7-owned-record-source-expiry-adoption` plus input removal before standalone verify in the lifetime smoke |
| Raw `Result` bind/parameter/return/map_err | Align Request 9 Move carrier | Source nulling and exactly-once drop for accepted raw result paths | `c7_owned_result_move_control_flow` syntax/runtime adoption fixture |
| JSON escape/NUL/UTF-8 | Request 7 grammar; Request 9 owned materializer | NUL/control/quote/backslash/multibyte note survives canonical round trip | `c7-persisted-result-wire-smoke` exact bytes |
| Input canonical bytes | `persisted_result.persist_file` | Re-encode and exact-compare before digest/algorithm/output | `c7-persisted-result-noncanonical-input-smoke` |
| Input schema/range precedence | `persisted_result.validate_input` | First applicable §8.1 row wins; no algorithm/output side effect before all validation | Ordered malformed corpus and untouched-destination assertions |
| SHA-256 input identity | `persisted_result.digest_input` plus `std.crypto` | Digest exact canonical input bytes, lowercase 64 hex | Independent Python digest comparison and known empty/text vectors |
| Algorithm lower/upper equality | `persisted_result.bounded_bucket` | Strict `<` endpoint semantics for both bucket boundaries | Boundary table and upper-comparison source mutation |
| Algorithm arithmetic bound | `persisted_result.validate_input` | Validate operands before addition; no unchecked overflow path | max operand and out-of-range corpus |
| Semantic PASS/FAIL | `persisted_result.make_result`, `main` | Valid FAIL persists, API returns summary, CLI exits nonzero after publication | `expected-mismatch` case and artifact reload |
| Diagnostic relation | `persisted_result.make_result`/`verify_file` | None for PASS, exact text for FAIL | status/diagnostic mutation corpus |
| Content digest preimage | `persisted_result.finalize_digest` | Blank only own digest field, declaration-order encode, SHA-256 compare | golden result bytes and digest-field mutation |
| Result canonical bytes | `verify_file` | Restore digest, encode, compare raw file bytes | field order/whitespace/unknown/null mutation corpus |
| Result source expiry | `verify_file` | Drop artifact input before invariant recomputation | standalone verify after artifact read helper boundary; source deletion |
| Result invariant recomputation | `verify_file` | Never trust stored observed/status/diagnostic | observed/status/digest mutation corpus |
| Malformed input cleanup | Request 9 runtime + C7 decode owner | Partial owned fields drop on malformed escape/shape/range/trailing bytes | malformed-input child cases; no leaked output owner observable |
| Malformed result cleanup | Request 9 runtime + C7 verify owner | Partial owned fields drop on malformed result | malformed-result child cases; read-only assertion |
| Early `?`/return paths | C7 module | No output before validation; all live Move values drop | error precedence and source/output state table |
| Branch joins | C7 module | PASS/FAIL option construction and result return have one owner | ownership smoke with both statuses |
| Loop joins | external Python runner; C7 has no persistent loop | Temporary fixture paths and generated cases are cleaned on every iteration | runner `finally` cleanup and stale-fixture test |
| Replacement/drop of `content_sha256` | C7 module | Blank digest owner is dropped before final digest moves in | digest finalization smoke |
| Output write success | C7 module / `std.fs.write_file` | One final canonical write after all validation | PASS/FAIL file byte comparison |
| Output write failure | `std.fs.write_file`; caller-owned limitation | Return mapped error; no hidden delete/restore/atomicity claim | DEFERRED fault injection; contract explicitly permits absent/partial destination |
| Existing destination on invalid input | C7 module | No write side effect before §8.1 row 10 | sentinel destination before/after malformed input |
| Existing destination on valid input | `std.fs.write_file` | Current whole-file replace semantics are used; no no-replace guarantee | fresh-destination adoption only; publication upgrade is Request 14/future |
| Same-path input/output | C7 path preflight | Exact equal path strings reject before read/write | CLI path validation smoke |
| Physical alias/symlink | N/A for v1 | Caller precondition; no physical alias detection claim | Unsupported-case documentation, no false acceptance |
| Repeated standalone verify | C7 module | Read-only deterministic result | two verifies after input deletion |
| Same-process operation pairs | C7 module/file boundary | §9.2 matrix is explicit; no shared mutable state | independent-destination/read-only pair smoke |
| Same-output concurrent processes | N/A/unsupported | No lock or race guarantee | documented unsupported caller case |
| CLI option/environment isolation | `src/main.align`, runner | No runtime option/env can alter result | environment perturbation smoke |
| Make target graph | Make/topology owner | Qualification stays focused; bounded smoke enters the authoritative graph only after the §12 admission decision | focused commands; topology self-test only if membership changes |
| Aggregate-plus-focused invocation | existing Make topology owner | Aggregate remains sole top-level goal; focused qualification is invoked separately | topology checker coexistence case only if functional smoke joins the graph |
| Per-unit/imported interface | Align compiler adoption + C7 module | Imported public surface and whole-program build agree | `alignc check-per-unit`, `make check`, `make build` |
| Generic monomorphization | N/A: no generic C7 public type/function | No generic implementation or acceptance claim | N/A with this reason |
| Structural Align compiler cache identity | N/A: C7 owns no compiler/cache artifact | Request 9/Align owns descriptor identity; C7 uses no application cache | N/A with this reason; adoption compiler checks remain required |
| Artifact schema/wire identity | C7 plan and module | Field order/types/version/content digest agree | canonical golden vectors, schema mutation |
| Producer-owned inspection fields | C7 module | Every persisted field is constructed from explicit input or deterministic algorithm; no reflection/source read | producer table below and independent reference comparison |
| Minimum tool/platform compatibility | adoption Make/CI owner | Pin and test every named native environment; no supplementary host substitutes for a required target | named environments in §11 and hosted evidence |
| Performance benchmark | N/A for this capability | No threshold or speed claim | Later C7 benchmark design required before a performance claim |
| Syntax examples | docs/adoption owner | Declaration and positional-call examples parse separately | `alignc fmt docs/examples/c7-persisted-result-syntax.align` |
| Milestone ordering | C7 design owner | Shipped Request 9 surface and platform profile precede dependent implementation; internal checkpoints remain on the capability branch | capability commits and focused acceptance evidence |

### 13.1 Producer-owned field table

No hidden reflection, source read, or artifact inference may populate these fields:

| Field | Producer | Source/derivation |
| --- | --- | --- |
| `schema_version` | record constructor | constant `1` |
| `artifact_kind` | record constructor | input/output constant |
| `case_id`, `algorithm`, operands, bounds, expected, `note` | result constructor | moved from validated owned input |
| `observed` | bounded-bucket function | checked deterministic calculation |
| `status`, `diagnostic` | result constructor/verifier | deterministic comparison of `observed` and `expected` |
| `input_sha256` | input digest owner | SHA-256 of exact canonical input bytes |
| `content_sha256` | finalizer | SHA-256 of result preimage with only this field blank |
| `VerificationSummary` | verifier | Copy projection of validated `expected`, `observed`, and recomputed status |

### 13.2 Cartesian acceptance matrix

There are no detail levels or configurable options, but the remaining discriminators and states are
explicitly crossed:

| Command | Discriminator | Note state | Verification state | Expected behavior |
| --- | --- | --- | --- | --- |
| persist | input record | None | PASS | canonical write, reload, summary, exit 0 |
| persist | input record | Some(empty) | PASS | explicit empty note field, canonical write, exit 0 |
| persist | input record | Some(escaped/NUL/UTF-8) | PASS | exact escaped wire and digest, exit 0 |
| persist | input record | any valid note | FAIL | canonical write, exact diagnostic, summary, nonzero exit |
| persist | malformed input | any bytes | INVALID_INPUT | no destination mutation, nonzero exit |
| verify | result artifact | None/omitted | PASS | read-only summary, exit 0 |
| verify | result artifact | Some(empty or text) | PASS or FAIL by fields | read-only exact invariant result |
| verify | mutated result | any | INVALID_INPUT | digest/canonical/invariant error, no write |

`detail level` is N/A because neither command has a detail flag or output detail mode. `option
state` is the single `NO_OPTIONS` state because the runtime has no configuration options. A future
algorithm discriminator or detail mode must extend this matrix before it is added.

## 14. Author-side design checks before implementation

Before opening the design PR, the author must complete all of these checks and record the result in
the PR description:

1. Ledger-to-prose: every command, field, status, error, ownership rule, digest rule, precedence
   row, limitation, prerequisite, and acceptance claim appears in both the ledger/matrix and the
   explanatory prose with the same meaning.
2. Matrix-to-diff preparation: each applicable closure row has a future owner and exact named
   regression; every `N/A` row has a concrete reason; no implementation file is changed by the
   design PR.
3. Source-of-truth check: re-read the pinned Align Request 9 evidence and current `std.fs`,
   `std.crypto`, `std.encoding`, JSON, and memory guides; confirm no proposed syntax is described
   as shipped.
4. Wire check: independently expand the field order, optional omission, digest preimage, NUL, and
   semantic-failure examples; do not derive an expected artifact by parsing the implementation.
5. Gate-topology check: keep qualification outside the aggregate; if the bounded smoke is admitted,
   identify and update the exact Make list, oracle, and identity-bound baseline together.
6. Review check: the merged design review remains historical evidence. Review the stable product
   capability once with its implementation and resolve valid findings in one consolidated repair.

The original design change was documentation/specification-only. Future documentation-only updates
use `git diff --check` plus targeted Markdown/link assertions. Source tests remain `N/A` until the
consumer capability changes an executable contract boundary; then its owner checks, both C7
commands, applicable platform evidence, and one final aggregate integration run are required.
