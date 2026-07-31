# Git 2.45 compatibility image locked inputs

## 1. Purpose and slice boundary

Request 7 needs a real image whose `/usr/bin/git --version` is exactly `git version 2.45.0` and
whose Rust and LLVM toolchain can build the pinned Align compiler. Before Docker construction can
be designed safely, the upstream Git and Rust archives and the reviewed LLVM installer need one
immutable, reproducibly audited input contract.

This plan defines only that enabling slice:

- a canonical lock for Git 2.45.0, Rust 1.96.0 cargo, rust-std, and rustc archives;
- the exact vendored LLVM 22 installer bytes;
- offline source-lock and archive-parser tests; and
- one explicit author-run command that downloads and structurally audits the four locked archives.

This slice defines no Dockerfile, build context, Buildx or BuildKit invocation, daemon resource,
runtime container, hosted workflow, registry operation, OCI artifact, publication, provenance,
registration record, or product behavior. In particular, it creates no image and does not install
or modify LLVM on the developer machine.

Delivery order is:

1. merge this locked-input/audit design;
2. implement and accept the lock, vendored installer, audit executable, fixtures, and Make targets;
3. separately design and implement Docker construction and local no-push acceptance against the
   merged locked inputs;
4. separately design and implement the hosted minimum-environment no-push gate;
5. design publication/provenance, then publish only with explicit repository-owner authority;
6. separately design and implement registration; and
7. let `docs/specs/check-gate-topology.md` consume only the registered immutable digest.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Input directory | `.github/images/git-2.45-compat/inputs/`. Its complete descendant topology is exactly two regular files, `sources.json` and `llvm.sh`, with no symlink, hard link, subdirectory, device, socket, or additional entry. Checked-in file modes are `100644`; an author filesystem may expose directory mode `0555`/`0755` and file mode `0444`/`0644`. |
| Source lock | `.github/images/git-2.45-compat/inputs/sources.json`, schema version 1. Its complete 1,301 bytes are the canonical JSON in section 3; SHA-256 is `0b27dd188cd4536efe2adb5b92e86d81bfbf23fd7fe87e770d58d03d061459a0`. |
| LLVM input | `.github/images/git-2.45-compat/inputs/llvm.sh`, exactly 8,277 bytes, SHA-256 `9474ecd78b52aba6e923976b1e9773f5613027cc7e237b9956986cb536e02a36`. The origin URL is attribution only; the audit never fetches or executes it. |
| Offline target | `make git245-locked-inputs-unit`. It invokes the production audit executable's self-test mode, performs no network, Git, Docker, or repository write, and is a hosted focused target included in `hosted-checks`, `capable-checks`, and `make ci` through the authoritative graph in `docs/specs/check-gate-topology.md`. |
| Real audit target | `make git245-locked-inputs-audit GIT245_AUDIT_TEMP_ROOT=<absolute directory> GIT245_AUDIT_OPERATION_ID=<16 lowercase hexadecimal characters>`. Both variables must have Make command-line origin. Their values cross Make's environment boundary without recipe-shell interpolation. The target downloads and audits only the four locked archives. |
| Host | A local Linux author environment with `/usr/bin/python3`, GNU Make, HTTPS connectivity to the four locked origins, writable `/tmp`, and an explicit audit temporary root satisfying section 5. Compatibility range and minimum Python/Make version are N/A: the later hosted image gate owns minimum-environment acceptance. |
| Credentials | None. The audit rejects the exact sensitive ambient-name set before owned-root or network side effects, constructs an opener with no proxy, cookie, authentication, or caller header, and never reads or reports a sensitive value. Code review remains the trust boundary for the already-started repository process; pre-execution isolation is not claimed. |
| Output | Both Make recipes suppress command echo and preserve the executable's status and bytes. On success the Make target output is the exact executable PASS line. On failure the executable contract is exact in sections 5.4 and 6, after which GNU Make may append its own host-version diagnostic to stderr; that Make-owned suffix is not parsed or claimed as an executable diagnostic. No child output is streamed. |
| Persisted identity | `sources.json` and `llvm.sh` are reviewed inputs. The audit result, downloaded archives, and temporary root are disposable and are never a persisted result, cache identity, or publication attestation. |
| Cache | N/A: the audit performs fresh fixed downloads and has no cache import, export, lookup, or write. |
| Hosted/publication/registration | N/A in this slice. Actions credentials, Docker/OCI identity, registry authentication, visibility, provenance, artifact transport, and commit registration are deferred. |
| Metric | N/A: this prerequisite makes no performance claim. Acceptance is exact input identity and archive safety. |

Updating a URL, version, size, hash, file byte, schema field, admitted archive record, parser limit,
or public command is a contract change requiring design review.

## 3. Canonical source lock

`sources.json` is UTF-8 JSON with two-space indentation, the displayed key order, no escaped ASCII,
and exactly one final LF. These are its complete bytes:

```json
{
  "schema_version": 1,
  "git": {
    "version": "2.45.0",
    "url": "https://www.kernel.org/pub/software/scm/git/git-2.45.0.tar.xz",
    "size": 7482988,
    "sha256": "0aac200bd06476e7df1ff026eb123c6827bc10fe69d2823b4bf2ebebe5953429"
  },
  "rust": {
    "version": "1.96.0",
    "components": [
      {
        "name": "cargo",
        "url": "https://static.rust-lang.org/dist/2026-05-28/cargo-1.96.0-x86_64-unknown-linux-gnu.tar.gz",
        "size": 15645746,
        "sha256": "b691a9e31b1e5498017be91155a1e7501eccf6437e7dc9ff1896e38aa1584dbf"
      },
      {
        "name": "rust-std",
        "url": "https://static.rust-lang.org/dist/2026-05-28/rust-std-1.96.0-x86_64-unknown-linux-gnu.tar.gz",
        "size": 49703183,
        "sha256": "36e577b66f7b2f8fc6493f97f81329e5f6e1514360d0c6c31d5d8463184e6773"
      },
      {
        "name": "rustc",
        "url": "https://static.rust-lang.org/dist/2026-05-28/rustc-1.96.0-x86_64-unknown-linux-gnu.tar.gz",
        "size": 134687636,
        "sha256": "71143d6075582b7e65233992c77e375aadbec4dfda6df2675160bf05b89410f9"
      }
    ]
  },
  "llvm_installer": {
    "origin_url": "https://apt.llvm.org/llvm.sh",
    "path": "llvm.sh",
    "size": 8277,
    "sha256": "9474ecd78b52aba6e923976b1e9773f5613027cc7e237b9956986cb536e02a36"
  }
}
```

The validator embeds the source-lock SHA-256 constant and requires exact file size, digest, and
byte equality before decoding. It then rejects duplicate, missing, unknown, or reordered keys;
wrong scalar types; booleans where integers are required; invalid UTF-8; NUL; CR; noncanonical
number or string spelling; and any semantic value different from this section. It independently
re-encodes the parsed value with two-space indentation and one LF and requires byte equality.
Validated scalar/vector values are copied into immutable Python values before source descriptors
close or any owned-root/network side effect begins; later work never rereads a lexical input path.

The four downloadable archive identities and fixed audit destination names, in order, are:

```text
git
  destination git-2.45.0.tar.xz
  7482988 bytes
  0aac200bd06476e7df1ff026eb123c6827bc10fe69d2823b4bf2ebebe5953429
cargo
  destination cargo-1.96.0-x86_64-unknown-linux-gnu.tar.gz
  15645746 bytes
  b691a9e31b1e5498017be91155a1e7501eccf6437e7dc9ff1896e38aa1584dbf
rust-std
  destination rust-std-1.96.0-x86_64-unknown-linux-gnu.tar.gz
  49703183 bytes
  36e577b66f7b2f8fc6493f97f81329e5f6e1514360d0c6c31d5d8463184e6773
rustc
  destination rustc-1.96.0-x86_64-unknown-linux-gnu.tar.gz
  134687636 bytes
  71143d6075582b7e65233992c77e375aadbec4dfda6df2675160bf05b89410f9
```

## 4. Vendored LLVM installer

`llvm.sh` is the reviewed upstream installer from `https://apt.llvm.org/llvm.sh`. The URL is not an
audit input and is never contacted. The source validator opens the input directory and both files
descriptor-relatively without following symlinks, requires unique device/inode pairs and link count
one, enumerates exactly the two declared regular files, admits directory mode `0555`/`0755`, and
admits file mode `0444`/`0644` with no group/world write bit. It validates the exact lock bytes first, then requires the LLVM
descriptor's size and SHA-256 to match both the ledger and decoded lock.

The implementation requires these exact checked-in bytes and hash. Execution, APT behavior,
package selection, and Dockerfile invocation are deferred to the Docker construction design. This
slice makes no claim that the script has run.

## 5. Real locked-archive audit

### 5.1 Make adapter, mode, paths, and environment

Executable `.github/image-tests/git-2.45-compat/audit-locked-archives` is the sole implementation
behind both targets. The real target has six ordered target-specific immediate `override export`
assignments. First, `GIT245_AUDIT_TEMP_ROOT_VALUE` and `GIT245_AUDIT_OPERATION_ID_VALUE` receive
`$(value GIT245_AUDIT_TEMP_ROOT)` and `$(value GIT245_AUDIT_OPERATION_ID)`, preserving raw dollar
and Make-function text without expanding it. `GIT245_AUDIT_TEMP_ROOT_ORIGIN` and
`GIT245_AUDIT_OPERATION_ID_ORIGIN` then receive only the corresponding `$(origin ...)` results.
Finally target-specific overrides replace the two original recipe-environment variables with the
fixed literal `ignored-by-audit-transport`. This ordering prevents GNU Make's automatic export from
expanding a raw command-line value such as `$(shell ...)`. No caller value is expanded into a
recipe or ordinary exported variable. The executable tests the original names without reading their
fixed values and reads only the four suffixed transport fields. The silent recipe is the following
fixed token sequence:

```text
["/usr/bin/python3","-I","-B",
 "./.github/image-tests/git-2.45-compat/audit-locked-archives","--audit"]
```

The exact Make fragment, with each `<TAB>` replaced by one literal recipe tab, is:

```text
.PHONY: git245-locked-inputs-unit git245-locked-inputs-audit

git245-locked-inputs-unit:
<TAB>@/usr/bin/python3 -I -B \
<TAB>  ./.github/image-tests/git-2.45-compat/audit-locked-archives --self-test

git245-locked-inputs-audit: override export GIT245_AUDIT_TEMP_ROOT_VALUE := $(value GIT245_AUDIT_TEMP_ROOT)
git245-locked-inputs-audit: override export GIT245_AUDIT_OPERATION_ID_VALUE := $(value GIT245_AUDIT_OPERATION_ID)
git245-locked-inputs-audit: override export GIT245_AUDIT_TEMP_ROOT_ORIGIN := $(origin GIT245_AUDIT_TEMP_ROOT)
git245-locked-inputs-audit: override export GIT245_AUDIT_OPERATION_ID_ORIGIN := $(origin GIT245_AUDIT_OPERATION_ID)
git245-locked-inputs-audit: override export GIT245_AUDIT_TEMP_ROOT := ignored-by-audit-transport
git245-locked-inputs-audit: override export GIT245_AUDIT_OPERATION_ID := ignored-by-audit-transport
git245-locked-inputs-audit:
<TAB>@/usr/bin/python3 -I -B \
<TAB>  ./.github/image-tests/git-2.45-compat/audit-locked-archives --audit
```

The executable accepts exactly one mode token, `--audit` or `--self-test`; unknown, repeated, empty,
or positional tokens reject. Audit mode reads exactly the four suffixed `GIT245_AUDIT_*` transport
fields above. Both origin values must be exactly `command line`; the temporary-root value must be
nonempty absolute UTF-8 without NUL, CR, or LF, and the operation ID must be exactly 16 lowercase
hexadecimal ASCII bytes. Passing an arbitrary caller value from Make to the process does not invoke
a shell parser. The repository root is the inherited current working directory, opened as `.`;
neither `CURDIR` nor a repository path is expanded into the recipe.

The current-working-directory spelling and temporary root must each be absolute lexical-normal
paths. The audit opens `.` before input validation and, after input validation, opens every
temporary-root component from `/` with no-follow directory operations. It rejects a symlink
ancestor, ownership other than the current user for the
temporary root, or a descriptor/path identity mismatch. It retains both root descriptors through
the root-relation decision. The repository root must contain the executing audit file and exact
input directory at their declared descriptor-relative paths. The temporary root must be neither
equal to, inside, nor an ancestor of the repository root. No temporary-root path component may
begin `align-llm-git245-audit-` or `align-llm-git245-input-unit-`; this prevents an audit root from
containing another audit or focused-unit root.

The owned root is exactly
`<temporary-root>/align-llm-git245-audit-<operation-id>`, must be absent, and is created mode `0700`
with one mode-`0700` `downloads` child. `AuditRoot` retains the already validated temporary-root
parent descriptor and exact owned-root basename from the absence check through final unlink and
absence proof. All later filesystem access is descriptor-relative; no external process consumes a
path below the root. The supplied roots are never removed.

Before opening inputs, creating the root, or using the network, the audit rejects these exact
ambient names: `GITHUB_TOKEN`, `GH_TOKEN`, `ACTIONS_RUNTIME_TOKEN`,
`ACTIONS_ID_TOKEN_REQUEST_TOKEN`, `OPENAI_API_KEY`, `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`,
`NO_PROXY`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`,
`SSLKEYLOGFILE`, `OPENSSL_CONF`, `OPENSSL_MODULES`, `NETRC`, `PYTHONPATH`, and `PYTHONHOME`. It also rejects any name with the
ASCII-case-insensitive suffix `(^|_)(TOKEN|PASSWORD|SECRET|CREDENTIAL|CREDENTIALS|PRIVATE_KEY|API_KEY)$`.
It tests names only and never reads or reports their values.

Project-owned timeouts are N/A for this author command because it has no supervisor. Caller
interruption may leave only its exact owned root; no broad recovery deletion is authorized.

### 5.2 Transfer contract

Downloads run sequentially in the section 3 order. Each fixed destination begins absent and is
opened directly, create-exclusive and mode `0600`, below the private downloads descriptor. There is
no partial sibling, rename, link, or replacement transition. The file is in `writing` state until
its size and digest are accepted; no scan observes that state. The audit constructs an HTTPS opener
with an empty proxy map and no cookie, authentication, redirect, or caller-header handler, and
implements redirects itself.
It issues only `GET` with no body, fixed `Accept-Encoding: identity`, and no caller-derived header.
It accepts only HTTPS port 443 URLs without userinfo or fragment; redirect status 301, 302, 303,
307, or 308 with exactly one syntactically valid `Location`; a final status 200; exactly one
canonical-decimal `Content-Length` equal to the locked size; no `Transfer-Encoding`; and absent or
exactly `identity` `Content-Encoding`. It permits at most five redirects, rejects a repeated URL,
resolves a relative `Location` against the current HTTPS URL, and rejects userinfo, fragments,
non-443 ports, non-HTTPS schemes, and downgrade after every resolution.
TLS uses `ssl.create_default_context()` with hostname and certificate verification enabled and no
caller-supplied CA, client certificate, key-log path, or context mutation. Each request produces at
most one owned `HttpsResponse`, comprising the response object and its underlying TLS socket. A
redirect response is closed before the next request begins. Status/header rejection, read failure,
digest failure, and successful EOF all close the current response in a `finally` path before file
acceptance or transfer cleanup; response-close failure remains a failure in the active download
phase.

The reader fails before buffering or writing one byte beyond the locked compressed size. It
requires exact size and SHA-256, flushes and `fsync`s the file and downloads directory, then moves
the already named file from `writing` to `accepted` while retaining the same descriptor for
scanning. A failed transfer closes and unlinks only its exact fixed destination and `fsync`s the
downloads directory. No downloaded byte is logged.

### 5.3 Compression and tar contract

The audit scans the accepted file descriptor without extracting it. Decompression and tar parsing
are streaming: at most 4 GiB uncompressed bytes, 16,384 logical entries, 16 KiB for one resolved
UTF-8 path, a 256 MiB XZ decoder memory limit, and 8 MiB total Python-owned decompressor/output/header
buffers per archive; gzip uses one `zlib.decompressobj(16 + MAX_WBITS)`. The separately owned
normalized-path table retains complete immutable UTF-8 byte strings, never digest-only identities,
and admits at most 64 MiB of cumulative path bytes and 16,384 set entries. Count and cumulative-byte
limits are checked before retaining the next path. Python allocation failure rejects in the active
archive phase. Hash collisions are resolved by full byte equality. Limit overflow rejects before an
additional byte, entry, or table identity is accepted.

The Git input must be exactly one XZ 1.0 stream beginning with the six-byte XZ magic. Its stream
flags have reserved byte zero and Check ID 4 (CRC64); liblzma validates the header, every block,
index, stream footer, padding rules internal to blocks, and every CRC. `LZMADecompressor` uses
`FORMAT_XZ` and the stated memory limit; `eof` must become true and `unused_data` must be empty. Each
Rust input must be exactly one gzip member whose ten-byte header is
`1f 8b 08 00 00 00 00 00 02 ff`: DEFLATE, no optional flags, zero mtime, extra flags 2, OS 255.
The inflater uses the gzip wrapper, validates the CRC32 and ISIZE trailer, reaches EOF, and has empty
`unused_data` and `unconsumed_tail`. Concatenated streams/members, reserved/optional gzip flags,
another check type, truncation, checksum failure, and every unused compressed byte, including zero
compression padding, reject. The decompressed bytes must form complete 512-byte blocks.

Every nonzero tar header uses the POSIX 512-byte field offsets. Its checksum field is exactly seven
ASCII octal digits followed by NUL. For checksum calculation bytes 148 through 155 are replaced by
eight ASCII spaces; the stored value must equal at least one independently accumulated unsigned-byte
or signed-eight-bit sum. The accepted header dialects are exact:

- Git headers have magic `ustar` followed by NUL, version `00`, uname and gname equal to `root`
  followed by 28 NUL bytes, and type flag exactly `0`, `5`, or `2` for regular, directory, or
  symbolic-link records.
- Rust headers have magic `ustar` followed by one space, version one space followed by NUL,
  all-zero uname, gname, prefix, and linkname fields, and type flag exactly `0`, `5`, or `L` for
  regular, directory, or GNU long-name records.
- In both dialects the 155-byte prefix and final 12-byte padding fields are all zero. Consequently
  a non-long effective path is exactly the name field; no prefix/name concatenation is admitted.
  The 100-byte name and Git linkname fields are either 100 non-NUL bytes or a nonempty value
  followed only by NUL padding. Unused linkname bytes are all zero.
- Mode, uid, gid, size, mtime, and ordinary devmajor/devminor fields are exactly seven or eleven
  ASCII octal digits, according to their POSIX field width, followed by NUL, with no spaces or
  base-256 form. uid, gid, devmajor, and devminor decode to zero. A GNU `L` header instead has
  all-zero devmajor/devminor fields, exact name `././@LongLink` plus NUL padding, mode `0000644`,
  zero uid/gid/mtime, and otherwise the same magic, version, checksum, and zero-field rules.
- Directory and symlink sizes are zero. File and long-name sizes must fit the remaining
  uncompressed-byte bound. Modes contain only the low permission nine bits; setuid, setgid, sticky,
  negative, overflowing, space-padded, NUL-only, and otherwise malformed numeric fields reject.
  Every record-data pad byte through the next 512-byte boundary is zero.

Decoded effective names and the Git link target must be valid UTF-8 without an embedded NUL, empty
component, `.`, `..`, leading `/`, or backslash. A directory name may have exactly one final `/`,
which is removed before component and uniqueness checks; other records and interior components may
not be empty. Every path must equal or remain below its exact top-level directory: `git-2.45.0`,
`cargo-1.96.0-x86_64-unknown-linux-gnu`, `rust-std-1.96.0-x86_64-unknown-linux-gnu`, or
`rustc-1.96.0-x86_64-unknown-linux-gnu` for its named archive. The full normalized UTF-8 bytes enter
the bounded uniqueness table. The first semantic record must be the exact top-level directory and
no other record may equal it. Git admits exactly one relative symbolic link whose target, resolved
from the link's parent, remains inside that top-level directory. Rust admits no link. A GNU `L`
payload is 2 through 16,385 bytes: one nonempty
UTF-8 path of at most 16,384 bytes, exactly one final NUL, no earlier NUL, and zero block padding. It
replaces, rather than prefixes or appends to, the name of exactly the immediately following `0` or
`5` header. Consecutive, dangling, or otherwise targeted long-name records reject.

Hard links, PAX, global PAX, sparse records, devices, FIFOs, sockets, volume headers, continuation
records, GNU long links, NUL regular-file type flags, and every other type flag reject. The first
two consecutive all-zero blocks terminate the semantic tar. Every subsequent complete block through
decompressor EOF must also be all zero; a later nonzero block or partial block rejects.

Self-test mode constructs all fixtures in the production executable and calls the same production
source-validation, decompressor, header, path-table, transfer-state, diagnostic, and cleanup helpers
used by audit mode. It covers one valid Git dialect, one valid Rust dialect, every compression
failure, both checksum interpretations, each field-encoding boundary above, every admitted/rejected
type flag, path and link traversal, full-byte duplicate detection including forced hash collision,
entry/path/table exhaustion, GNU long-name state, terminator placement, concatenation, compression
padding, tar padding, and trailing bytes. The four real locked archives must also pass.

### 5.4 Status, validation order, and cleanup

In `--audit` mode the executable launches no child and streams no nonsemantic output. Direct
success status is zero,
stdout is exactly `git 2.45 locked-input archive audit: PASS` plus LF, and stderr is empty. Failure
status is 1, stdout is empty, and stderr contains one primary line and, only when cleanup also
fails, one following cleanup line. The finite categories are:

```text
argument
environment
source
filesystem
download-git
download-cargo
download-rust-std
download-rustc
archive-git
archive-cargo
archive-rust-std
archive-rustc
internal
cleanup
```

Each line is exactly `git 2.45 locked-input archive audit: ERROR <category>` plus LF. The first
failure in this validation order is immutable:

1. exact mode, Make-origin environment fields, and audit-value grammar;
2. sensitive ambient names;
3. repository/input/script descriptors, source-lock bytes/semantics, and LLVM bytes;
4. temporary-root ancestry, ownership, reserved-component, and absent-owned-root checks;
5. owned-root construction;
6. the four downloads in section 3 order; and
7. the four archive scans in section 3 order.

Argument failures map to `argument`, ambient names to `environment`, input validation to `source`,
root operations to `filesystem`, and each transfer/scan to its named category. An unexpected
exception maps to the active phase, or `internal` if no phase owns it. Cleanup then closes every
response, buffer, file, and directory descriptor, unlinks fixed archive names, removes fixed
children, and removes the owned root descriptor-relatively through the retained temporary-root
parent in reverse acquisition order. Cleanup failure appends exactly one final
`cleanup` line and never masks the primary. A cleanup-only failure emits only the cleanup line.
PASS is emitted only after cleanup proves the owned root absent. The Make adapter returns nonzero
when the executable does; any later GNU Make diagnostic is outside this executable grammar and
cannot mask or replace its already emitted primary and optional cleanup records.

## 6. Ownership and closure matrix

Offline target `make git245-locked-inputs-unit` has the silent fixed recipe
`["/usr/bin/python3","-I","-B","./.github/image-tests/git-2.45-compat/audit-locked-archives",
"--self-test"]`. It therefore executes the same checked-in source and production helper functions
as audit mode. Self-test mode ignores caller `TMPDIR`, performs no network or child-process call,
and does not read the four audit-mode transport values. Direct success status is
zero with exact stdout `git 2.45 locked-input unit tests: PASS` plus LF and empty stderr. Failure
status is 1 with empty stdout and bounded UTF-8 stderr: at most 1 MiB, LF-terminated lines without
NUL or CR. Fixed diagnostic lines are followed by exact primary line
`git 2.45 locked-input unit tests: ERROR unit`; when owned-root cleanup also fails, one exact
`git 2.45 locked-input unit tests: ERROR cleanup` line follows it. A cleanup-only failure emits only
the cleanup line. Other diagnostic lines contain only fixed checked-in test identifiers and
assertion categories, never fixture or environment bytes. The Make adapter preserves that status
and byte stream, subject only to the same later Make-owned failure suffix described in the ledger.

`audit-locked-archives` owns both modes, argument/environment validation, source descriptors, HTTPS
transfer, streaming parsing, synthetic fixtures, diagnostics, and cleanup. In self-test mode it
owns private mode-`0700` directories created directly below `/tmp` with prefix
`align-llm-git245-input-unit-`; it opens `/tmp` without following a symlink, requires a writable
sticky directory, ignores caller `TMPDIR`, and appends 32 lowercase hexadecimal characters from
`secrets.token_hex(16)`. It makes at most eight create-exclusive attempts, treats exhaustion as a
unit failure before fixture creation, and removes every owned root. The Makefile owns only the two
fixed silent adapters, target-specific origin exports, and inclusion of the offline target in the
authoritative hosted graph. `scripts/check-gate-topology` owns the corresponding exact graph oracle.

The implementation uses six ordinary, non-persisted ownership records:

- `InputSet` retains no-follow descriptors for the repository root, audit file, input directory,
  lock, and LLVM file. The repository descriptor remains live through the separately ordered
  temporary-root relation check; file descriptors may close after immutable values are copied, and
  the repository descriptor closes only after that relation decision.
- `AuditRoot` owns the validated temporary-root parent descriptor and exact owned-root basename
  before creation, then the absent-to-created root and fixed child descriptors until the parent-
  relative absence proof succeeds.
- `UnitRoot` owns one create-exclusive random directory directly below `/tmp`; it never accepts a
  caller path and removes only descriptor-retained synthetic fixtures below that root.
- `HttpsResponse` owns at most one response and its TLS socket from opener return until mandatory
  close. Ownership ends before a redirect, transfer acceptance, or error return.
- `DownloadFile` moves from absent to writing to accepted while retaining the direct fixed-name
  descriptor; every non-absent state authorizes only exact-name unlink below the retained downloads
  descriptor. It has no second name or install transition.
- `ArchiveScan` borrows one accepted descriptor and owns bounded decompressor/parser buffers plus
  the complete-byte normalized-path set bounded by 16,384 entries and 64 MiB of path bytes. It
  closes buffers, releases the table, and transfers no handle or semantic object to a caller.

| Path | Owner | Success | Failure/early exit | Required regression |
| --- | --- | --- | --- | --- |
| Make/mode/environment transport | audit | ordered raw-value/origin exports, fixed original-variable overrides, fixed recipe, exact mode, exact command-line origins, and value grammar | no Make-function, shell, input, root, or network side effect | missing/environment-origin/empty/relative/repeated/unknown/positional/NUL/CR/LF cases; literal `$(shell ...)`, quotes, dollars, backticks, spaces, and shell metacharacters retain exact raw bytes and create no marker |
| Sensitive environment | audit | no rejected name present | no input/root/network side effect; value unread | every exact/suffix name, case boundaries, clean environment, value-not-read sentinel |
| Source lock | `InputSet` | exact bytes/hash, canonical decode/re-encode, exact semantics | all opened descriptors close; no root/network | golden bytes/hash; every key/order/type/UTF-8/NUL/CR/LF/number/string mutation; replacement/in-place/short read |
| LLVM file | `InputSet` | exact descriptor kind/link-count/mode/size/hash | descriptors close; no root/network | missing/extra/symlink/hard-link/mode/size/hash/source replacement/partial-open cases |
| Root relation | `InputSet` + `AuditRoot` | both canonical no-symlink root descriptors remain live; roots are disjoint and reserved-component-free | descriptors close; no creation/network | root equal/ancestor/descendant; symlink ancestor; rename/path-identity race while both descriptors remain live; reserved component; wrong owner |
| Audit-root creation | `AuditRoot` | retained parent, exact basename, absent root, and children retained | parent-descriptor-relative partial cleanup and absence proof | collision; parent rename/replacement; partial mkdir/open/chmod/fsync; cleanup failure |
| Unit-root lifecycle | `UnitRoot` | create-exclusive random root and synthetic fixtures removed | exact unit/cleanup diagnostics; no repository write | collision retry; ignored `TMPDIR`; partial fixture creation; cleanup failure; root absence proof |
| HTTPS response | `HttpsResponse` | each final or redirect response closes exactly once before the next transition | active download remains primary; no socket/response retained | opener failure; redirect; status/header rejection; read/hash/EOF failure; close failure; success close |
| HTTPS transfer | `DownloadFile` | direct fixed name moves writing to accepted with exact size/hash | response/file close, exact fixed-name unlink, and parent fsync | each URL/redirect/status/encoding/size/hash/write/fsync failure; failure before/after direct create and acceptance; no credential/proxy/header |
| Compression | `ArchiveScan` | exactly one bounded XZ stream or gzip member, with no unused byte including zero padding | buffers and table release; accepted file remains cleanup-owned | truncation/checksum/concatenation/unused/zero-padding/unconsumed-tail/uncompressed-size/buffer/allocation limits |
| Tar scan | `ArchiveScan` | exact header dialect, complete admitted semantic set, full-byte uniqueness, and terminator | buffers and table release; accepted file remains cleanup-owned | every field, checksum, type, path, collision, long-name, terminator, entry/path/table/buffer limit in section 5.3 |
| Diagnostics | audit | PASS only after absence proof | exact primary and optional cleanup lines | every category, active-phase exception, primary+cleanup, cleanup-only, exact status/stdout/stderr |
| Unit diagnostics | focused runner | exact PASS or bounded fixed-identifier failure grammar | primary unit line retained before optional cleanup | assertion failure, overflow, invalid diagnostic byte, unit+cleanup, cleanup-only |
| Production-source binding | audit executable | both modes dispatch to the same helper objects in the same loaded source | mode-specific failure grammar | source inspection plus sentinel mutation of each production helper observed by self-test; no duplicate parser implementation |
| Normal cleanup | all owners | responses closed; downloads, children, and root absent through retained parent | primary retained; one cleanup line | failure before/after every acquisition, response transition, unlink, and cleanup operation; repeated cleanup after success is no-op |
| Caller interruption | caller | N/A | exact root may remain; no automatic broad deletion | documentation/static contract only |

Construction, success, failure, malformed input, cleanup, and early exit are covered above.
Replacement, move-out, returned handles, generic monomorphization, interface serialization,
whole-program/per-unit compilation, and Align allocation parity are N/A: the two modes of the
stdlib-only Python executable return only process status and text.

The public entrypoints are focused offline target `F`, real audit target `A`, and the serialized
aggregates `hosted-checks`, `capable-checks`, and `ci`, collectively `C`. `C` includes `F` through
the hosted focused list and never invokes `A`. In one top-level Make invocation their complete
coexistence policy is:

| Pair | Policy | Required evidence |
| --- | --- | --- |
| `F+F` | GNU Make de-duplicates the repeated goal and runs it once | focused marker/de-duplication self-test |
| `F+A` | safe, including `-j`: the unit root is under `/tmp`, the validated audit root is outside and non-ancestral to the repository, and neither writes the repository | same-invocation `-j2` overlap smoke with distinct retained roots |
| `F+C` | rejected during Makefile parsing before side effects because an aggregate must be the sole top-level goal | existing aggregate-plus-focused topology self-test, with `F` as the real focused goal |
| `A+A` | GNU Make de-duplicates the repeated goal and runs one audit with the one command-line value set | audit marker/de-duplication self-test; no second network opener |
| `A+C` | rejected during Makefile parsing before side effects because an aggregate must be the sole top-level goal | existing aggregate-plus-focused topology self-test, extended with `A` |
| `C+C` | every repeated or distinct aggregate pair rejects during Makefile parsing before side effects | existing aggregate coexistence self-test |

As already required by `docs/specs/check-gate-topology.md`, separate concurrent Make processes are
unsupported caller behavior in the same or independent worktrees and are never valid verification
evidence, for every `F`, `A`, and `C` pair. This slice adds no cross-process repository, `/tmp`,
temporary-root, network, or Align-target lock and makes no safety claim for such overlap. Sequential
independent processes remain supported when each invocation satisfies its own path and cleanup
contract.

## 7. Acceptance and pull-request boundaries

### Design pull request

Only this file, the exact hosted-target amendment in `docs/specs/check-gate-topology.md`, and
`HANDOFF.md` change. Before commit, run the author ledger/prose/matrix pass, `git diff --check`, and
`make ci ALIGN_REPO=<sibling pinned Align checkout>`. After opening the pull request, run the one
comprehensive high-effort independent-adversarial review required by `CLAUDE.md`. Apply accepted
root-cause classes in one consolidated follow-up. An ordinary finding-only repair does not
invalidate that review; the topology source-of-truth reconciliation materially expands this design,
so this pull request requires the conditional final review. Review/check envelopes remain external
metadata and are not copied into `HANDOFF.md`.

### Locked-input implementation pull request

The implementation adds only:

```text
.github/images/git-2.45-compat/inputs/sources.json
.github/images/git-2.45-compat/inputs/llvm.sh
.github/image-tests/git-2.45-compat/audit-locked-archives
Makefile
scripts/check-gate-topology
eval/expected/coding-v1-reference-oracle.json
eval/baselines/coding-v1-reference.json
eval/expected/coding-v1-reference.sha256
HANDOFF.md
```

No other source, fixture, workflow, or documentation path is permitted. The executable generates
its bounded synthetic fixtures in self-test mode. The implementation adds the two exact Make
targets and inserts only the offline target into the existing hosted focused list. Because
`Makefile` is a baseline-identity artifact, the implementation must follow the source -> oracle ->
finalization commit sequence in `docs/specs/check-gate-topology.md` and refresh only the three exact
baseline paths above. It adds no Dockerfile, Docker command, workflow, registry client, extracted
artifact parser, publication path, or registration record.

Required checks are:

```text
make git245-locked-inputs-unit
make GIT245_AUDIT_TEMP_ROOT=<absolute external writable directory> \
  GIT245_AUDIT_OPERATION_ID=0000000000000001 \
  git245-locked-inputs-audit
make gate-topology-check
python3 scripts/check-gate-topology --self-test
make format-check
make check
make build
make -j8 ci ALIGN_REPO=<sibling pinned Align checkout>
```

The implementation slice is complete only when the exact lock and LLVM bytes validate, every
synthetic format/ownership/diagnostic/concurrency regression passes, the four real archives pass
the structural audit, cleanup proves the audit root absent, and full-diff inspection confirms that
no Docker, hosted, publication, or registration surface was added.

### Deferred Docker, hosted, publication, and registration work

The next design must consume these exact merged inputs and independently close canonical Dockerfile
byte identity, external-process path identity, Buildx/BuildKit composite daemon ownership, image
load reconciliation, runtime container ownership, and local no-push acceptance. The hosted gate then
owns minimum-environment execution, platform credential recipients, bounded execution, and abrupt
cleanup. Publication/provenance and registration remain separate contracts. No image publication,
GHCR visibility change, or registration is authorized by this slice.
