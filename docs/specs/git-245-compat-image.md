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
2. implement and accept the lock, vendored installer, offline production parser/self-test, and Make
   target as one independently passing hosted slice;
3. extend that same executable with the bounded HTTPS transfer and real four-archive audit as a
   second independently passing slice;
4. separately design and implement Docker construction and local no-push acceptance against the
   merged locked inputs;
5. separately design and implement the hosted minimum-environment no-push gate;
6. design publication/provenance, then publish only with explicit repository-owner authority;
7. separately design and implement registration; and
8. let `docs/specs/check-gate-topology.md` consume only the registered immutable digest.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Input directory | `.github/images/git-2.45-compat/inputs/`. Its complete descendant topology is exactly two regular files, `sources.json` and `llvm.sh`, with no symlink, hard link, subdirectory, device, socket, or additional entry. Checked-in file modes are `100644`; an author filesystem may expose directory mode `0555`/`0755` and file mode `0444`/`0644`. |
| Source lock | `.github/images/git-2.45-compat/inputs/sources.json`, schema version 1. Its complete 1,301 bytes are the canonical JSON in section 3; SHA-256 is `0b27dd188cd4536efe2adb5b92e86d81bfbf23fd7fe87e770d58d03d061459a0`. |
| LLVM input | `.github/images/git-2.45-compat/inputs/llvm.sh`, exactly 8,277 bytes, SHA-256 `9474ecd78b52aba6e923976b1e9773f5613027cc7e237b9956986cb536e02a36`. The origin URL is attribution only; the audit never fetches or executes it. |
| Offline target | `make git245-locked-inputs-unit`. Under the admitted Make control plane below, its fixed recipe invokes the production audit executable's self-test mode through `/usr/bin/env -i`. It accepts no audit-data value, performs no network, Git, Docker, or repository write, and is a hosted focused target included in `hosted-checks`, `capable-checks`, and `make ci` through the authoritative graph in `docs/specs/check-gate-topology.md`. |
| Real audit command | `/usr/bin/env -i LC_ALL=C /usr/bin/python3 -I -B ./.github/image-tests/git-2.45-compat/audit-locked-archives --audit`, invoked from the repository root with exactly those fixed tokens. It accepts no Make variable, path, operation ID, URL, credential, or other caller value and downloads and audits only the four locked archives. |
| Minimum host | Linux x86_64, CPython 3.12 or newer at `/usr/bin/python3`, `/usr/bin/env`, the Python `errno`, `hashlib`, `json`, `lzma`, `os`, `platform`, `secrets`, `signal`, `ssl`, `stat`, `struct`, `sys`, `time`, `urllib.error`, `urllib.parse`, `urllib.request`, and `zlib` standard-library modules, a mode-`01777` `/tmp`, and HTTPS connectivity to the four locked origins. The offline target additionally requires GNU Make 4.3 or newer. Ubuntu 24.04 x86_64 with its `/usr/bin/python3` 3.12 and GNU Make 4.3 is the required minimum acceptance environment; newer local CPython and Make runs are supplementary. |
| Credentials and environment | None. Both public entrypoints start the Python process with exactly `LC_ALL=C` through `/usr/bin/env -i`; the executable rejects any other process-environment name or value before input, owned-root, or network side effects. The opener has no proxy, cookie, authentication, redirect, or caller-header handler. No secret value is inherited, read, or reported. |
| Make control plane | Valid focused evidence is the exact command `make git245-locked-inputs-unit` with the repository's default Makefile and no option, environment-supplied `MAKEFLAGS`/`GNUMAKEFLAGS`, alternate makefile, `--eval`, variable assignment, or additional goal. Canonical aggregate evidence is only the option-cleared child invocation owned by `docs/specs/check-gate-topology.md`. Target-specific `override` assignments fix `SHELL=/bin/sh` and `.SHELLFLAGS=-eu -c`. GNU Make parses caller control state before any recipe can establish a security boundary, so every other direct Make invocation is unsupported diagnostic behavior and is not acceptance evidence. |
| Output | For an admitted Make invocation, the offline recipe suppresses command echo and preserves the executable's status and bytes. On its failure GNU Make may append its own host-version diagnostic to stderr; that suffix is not part of the executable contract. Ignore-errors, dry-run, question, touch, keep-going, silent, alternate-makefile, `--eval`, or other caller Make modes are outside this promise. The direct audit command has no Make-owned suffix. Both executable modes otherwise use the exact status and byte contracts in sections 5.4 and 6 and stream no child output. |
| Persisted identity | `sources.json` and `llvm.sh` are reviewed inputs. The audit result, downloaded archives, and owned root are disposable and are never a persisted result, cache identity, or publication attestation. |
| Cache | N/A: the audit performs fresh fixed downloads and has no cache import, export, lookup, or write. |
| Hosted integration | The existing Ubuntu 24.04 workflow runs the offline target only through the canonical `make -j8 hosted-checks` aggregate. The real network audit remains an author acceptance command and is not added to Actions. Docker no-push acceptance, Actions credentials, OCI identity, registry authentication, visibility, provenance, artifact transport, and commit registration are deferred. |
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

### 5.1 Fixed entrypoints, host, paths, and environment

Executable `.github/image-tests/git-2.45-compat/audit-locked-archives` is the sole implementation
behind both modes. Neither Python invocation accepts a variable audit-data input. The offline target
has this exact Make fragment, with each `<TAB>` replaced by one literal recipe tab:

```text
.PHONY: git245-locked-inputs-unit

git245-locked-inputs-unit: override SHELL := /bin/sh
git245-locked-inputs-unit: override .SHELLFLAGS := -eu -c
git245-locked-inputs-unit:
<TAB>@/usr/bin/env -i LC_ALL=C \
<TAB>  /usr/bin/python3 -I -B \
<TAB>  ./.github/image-tests/git-2.45-compat/audit-locked-archives --self-test
```

The real audit bypasses Make and is the exact fixed command from the repository root:

```text
/usr/bin/env -i LC_ALL=C \
  /usr/bin/python3 -I -B \
  ./.github/image-tests/git-2.45-compat/audit-locked-archives --audit
```

The corresponding process argument vectors are exactly:

```text
["/usr/bin/env","-i","LC_ALL=C","/usr/bin/python3","-I","-B",
 "./.github/image-tests/git-2.45-compat/audit-locked-archives","--self-test"]
["/usr/bin/env","-i","LC_ALL=C","/usr/bin/python3","-I","-B",
 "./.github/image-tests/git-2.45-compat/audit-locked-archives","--audit"]
```

No Make variable, shell-expanded audit-data value, path, URL, operation ID, credential, or ambient
option reaches the Python process. The two target-specific `override` assignments prevent a
command-line or environment `SHELL` or `.SHELLFLAGS` value from changing the recipe shell. They do
not turn GNU Make into a security boundary: Make has already parsed its process options, alternate
makefiles, `--eval` text, variable values, and goals. Only the two admitted Make invocations in the
ledger are acceptance evidence; all other Make control-plane states are unsupported diagnostics.

Before selecting a mode, the executable admits exactly the complete argument vector containing one
token, `--audit` or `--self-test`. Missing, empty, unknown, repeated, or additional positional or
option tokens return status 1, empty stdout, and exactly
`git 2.45 locked-input: ERROR argument` plus LF on stderr. This pre-dispatch grammar is independent
of both mode-specific prefixes. An admitted mode then requires its complete environment map to be
exactly `{"LC_ALL": "C"}` and rejects any additional, missing, or changed name or value before
opening repository inputs, creating an owned root, or using the network. The executable reads no
stdin and launches no child process.

Both modes require Linux, machine `x86_64`, CPython 3.12 or newer, and the standard-library modules
named in the ledger. The offline target additionally relies on GNU Make 4.3 or newer only to invoke
its fixed recipe. The implementation must use no Python syntax or API absent from CPython 3.12.
Ubuntu 24.04 x86_64 runs the offline target through `make -j8 hosted-checks` and is the required
minimum acceptance environment. An author run on a newer compatible Linux, CPython, or Make is
supplementary evidence and cannot replace that hosted result.

The repository root is the inherited current working directory, opened as `.`; neither `CURDIR` nor
a repository path is expanded into a recipe. Its spelling from `os.getcwd()` must be absolute and
lexically normal, and the path and descriptor identities must agree. The repository descriptor
remains live through owned-root construction and the disjointness decision. It must contain the
executing audit file and exact input directory at their declared descriptor-relative paths.

After source validation, each mode opens `/` and then `tmp` with no-follow directory operations,
requires path/descriptor identity, directory mode exactly `01777`, and sufficient access for the
current process. It generates a 32-character lowercase hexadecimal suffix with
`secrets.token_hex(16)` and attempts at most eight create-exclusive mode-`0700` directories directly
below the retained `/tmp` descriptor. Audit names use prefix `align-llm-git245-audit-`; self-test
names use prefix `align-llm-git245-input-unit-`. A collision retries with a new suffix; exhaustion
fails before fixture or network work. The audit root additionally owns one mode-`0700` `downloads`
child.

The chosen owned root and repository root must be neither equal nor ancestors of one another. Both
descriptors remain live through that decision. `AuditRoot` or `UnitRoot` retains the validated
`/tmp` descriptor and exact random basename from create-exclusive construction through final unlink
and parent-relative absence proof. All later temporary access is descriptor-relative; no external
process consumes a path below either root. The process never removes `/tmp` or the repository.

Pre-execution credential and option isolation is provided by the fixed `/usr/bin/env -i` command,
and the exact-map check makes that boundary fail closed. Before opening repository inputs, the
executable requires the inherited `SIGALRM` disposition to be default and both values from
`signal.getitimer(signal.ITIMER_REAL)` to be zero. `AuditDeadline` then installs one handler and a
300-second self-test or 3,600-second audit timer. Before each HTTPS open, the audit passes the
smaller positive value of 60 seconds or the then-remaining overall duration to the opener. The
resulting TLS socket retains that timeout for blocking response reads, while the overall timer
supplies the tighter current bound as it elapses. A deadline exception maps to the active phase.
Before cleanup, the owner replaces the work timer with one 30-second cleanup timer;
cleanup timeout produces the exact cleanup failure and may leave only the owned root. Finally it
disarms the timer and restores the default handler before reporting or returning. Handler/timer
install, replacement, disarm, and restore failures are retained as primary or cleanup failures
according to acquisition state. No mode overlaps two timed operations in one process.
`KeyboardInterrupt` and any other Python exception that reaches the owner use the same
cleanup attempt. An external signal that terminates the process without entering Python cleanup is
outside this slice's cleanup guarantee. If attempted cleanup cannot finish, at most one root with
the exact mode-specific prefix and a 32-hex suffix may remain: the current invocation's one retained
basename. The process neither counts, alters, nor makes any guarantee about matching roots left by
an earlier or simultaneous unsupported invocation. No broad recovery deletion is authorized.

### 5.2 Transfer contract

Downloads run sequentially in the section 3 order. Each fixed destination begins absent and is
opened directly, create-exclusive and mode `0600`, below the private downloads descriptor. There is
no partial sibling, rename, link, or replacement transition. The file is in `writing` state until
its size and digest are accepted; no scan observes that state. The audit constructs a fresh
`urllib.request.OpenerDirector`, sets `addheaders` to the empty list, and registers exactly one
`HTTPSHandler` made with the owned TLS context. It registers no `ProxyHandler`,
`HTTPErrorProcessor`, cookie, authentication, redirect, or caller-header handler.
It issues only `GET` with no body, fixed `Accept-Encoding: identity`, and no caller-derived header.
It admits each canonical locked origin only when it is an HTTPS port 443 URL without userinfo or
fragment. The response must be the immediate final status 200; every informational, redirect, other
successful, or error status rejects without following a `Location`. It requires exactly one
canonical-decimal `Content-Length` equal to the locked size, no `Transfer-Encoding`, and absent or
exactly `identity` `Content-Encoding`. Because no redirect is admitted, no redirect header encoding,
resolution, normalization, repetition, or allocation contract exists in this slice.
TLS uses `ssl.create_default_context()` with hostname and certificate verification enabled and no
caller-supplied CA, client certificate, key-log path, or context mutation. Each request produces at
most one owned `HttpsResponse`, comprising the response object and its underlying TLS socket. A
status/header rejection, read failure, digest failure, and successful EOF all close the current
response in a `finally` path before file acceptance or transfer cleanup; response-close failure
remains a failure in the active download phase. A rejected response never triggers another request
for that archive.

The reader owns one fixed 65,536-byte `bytearray` and uses `response.readinto()` with a memoryview
bounded by both that capacity and the locked remaining size. After the locked size is reached it
performs exactly one one-byte `readinto()` EOF probe. It never calls unbounded `read()`, retains a
second body chunk, or hashes or writes bytes beyond the locked size. A returned count outside the
offered view rejects before hash or write. Each admitted slice is hashed and written completely
before the buffer is reused.

The reader requires exact size and SHA-256, flushes and `fsync`s the file and downloads directory,
then moves the already named file from `writing` to `accepted`. It performs exactly
`os.lseek(descriptor, 0, os.SEEK_SET)`, requires returned offset zero, and only then lends that same
descriptor to `ArchiveScan`. The scanner's first bounded read begins at offset zero, validates the
exact leading compression magic without discarding it, and feeds that complete buffered chunk,
including the magic, to the decompressor. A failed transfer or cursor transition closes and unlinks
only its exact fixed destination and `fsync`s the downloads directory. No downloaded byte is logged.

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
padding, tar padding, and trailing bytes. Separately, audit mode requires all four real locked
archives to pass those same production scanners.

### 5.4 Status, validation order, and cleanup

The pre-dispatch malformed-vector result is the exact universal argument error in section 5.1; it
creates no mode owner and emits no audit- or unit-prefixed line. After `--audit` is selected, the
executable launches no child and streams no nonsemantic output. Direct success status is zero,
stdout is exactly `git 2.45 locked-input archive audit: PASS` plus LF, and stderr is empty. Failure
status is 1, stdout is empty, and stderr contains one primary line and, only when cleanup also
fails, one following cleanup line. The finite categories are:

```text
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

Each audit-mode line is exactly `git 2.45 locked-input archive audit: ERROR <category>` plus LF.
Across dispatch and audit mode, the first failure in this validation order is immutable:

1. exact mode;
2. exact process environment, operating system, machine, CPython version, required modules, initial
   signal/timer state, and work-deadline acquisition;
3. repository/input/script descriptors, source-lock bytes/semantics, and LLVM bytes;
4. `/tmp` identity/mode/access and owned-root construction, identity, and disjointness;
5. the four downloads in section 3 order; and
6. the four archive scans in section 3 order.

Mode failures use the universal argument line; environment, host, initial signal/timer, or
work-deadline acquisition failures map to `environment`; input validation to `source`; root
operations to `filesystem`; and each transfer/scan to its named category. An unexpected exception
maps to the active phase, or `internal` if no phase owns it. Cleanup then closes every
response, buffer, file, and directory descriptor, unlinks fixed archive names, removes fixed
children, and removes the owned root descriptor-relatively through the retained `/tmp` descriptor
in reverse acquisition order. Cleanup failure appends exactly one final
`cleanup` line and never masks the primary. A cleanup-only failure emits only the cleanup line.
PASS is emitted only after cleanup proves the owned root absent. The offline Make adapter returns
nonzero when the executable does; any later GNU Make diagnostic is outside this executable grammar
and cannot mask or replace its already emitted primary and optional cleanup records. Audit mode is
direct and has no Make-owned suffix.

## 6. Ownership and closure matrix

Offline target `make git245-locked-inputs-unit` has the silent fixed recipe argument vector
`["/usr/bin/env","-i","LC_ALL=C","/usr/bin/python3","-I","-B",
"./.github/image-tests/git-2.45-compat/audit-locked-archives","--self-test"]`. It therefore executes
the same checked-in source and production helper functions as audit mode. Self-test mode receives
only the exact fixed environment, performs no network or child-process call, and accepts no
audit-data value from the caller. Direct success status is
zero with exact stdout `git 2.45 locked-input unit tests: PASS` plus LF and empty stderr. Failure
status is 1 with empty stdout and bounded UTF-8 stderr: at most 1 MiB, LF-terminated lines without
NUL or CR. Fixed diagnostic lines are followed by exact primary line
`git 2.45 locked-input unit tests: ERROR unit`; when owned-root cleanup also fails, one exact
`git 2.45 locked-input unit tests: ERROR cleanup` line follows it. A cleanup-only failure emits only
the cleanup line. Other diagnostic lines contain only fixed checked-in test identifiers and
assertion categories, never fixture or environment bytes. The Make adapter preserves that status
and byte stream, subject only to the same later Make-owned failure suffix described in the ledger.

`audit-locked-archives` owns both modes, argument/environment/host validation, source descriptors,
HTTPS transfer, streaming parsing, synthetic fixtures, diagnostics, and cleanup. In self-test mode
it owns private mode-`0700` directories created directly below `/tmp` with prefix
`align-llm-git245-input-unit-`; it opens `/tmp` without following a symlink, requires a writable
sticky directory, has no inherited `TMPDIR`, and appends 32 lowercase hexadecimal characters from
`secrets.token_hex(16)`. It makes at most eight create-exclusive attempts, treats exhaustion as a
unit failure before fixture creation, and removes every owned root. The Makefile owns only the one
fixed offline adapter and inclusion of the offline target in the authoritative hosted graph.
`scripts/check-gate-topology` owns the corresponding exact graph oracle. Audit mode is invoked only
through the direct fixed command and has no Makefile adapter.

The implementation uses nine ordinary, non-persisted ownership records:

- `InputSet` retains no-follow descriptors for the repository root, audit file, input directory,
  lock, and LLVM file. The repository descriptor remains live through owned-root construction and
  the separately ordered disjointness check; file descriptors may close after immutable values are
  copied, and the repository descriptor closes only after that decision.
- `AuditRoot` owns the validated `/tmp` descriptor and exact random owned-root basename
  before creation, then the absent-to-created root and fixed child descriptors until the parent-
  relative absence proof succeeds.
- `UnitRoot` owns the validated `/tmp` descriptor and one create-exclusive random directory below
  it; it never accepts a caller path and removes only descriptor-retained synthetic fixtures below
  that root.
- `AuditDeadline` owns the process-global `SIGALRM` handler and real-time interval timer after
  proving their initial default/zero state. It transitions from work deadline to cleanup deadline,
  then disarms and restores before output or return.
- `HttpsClient` owns one default-verifying TLS context and one exact-handler opener from construction
  in the first download phase until the four sequential downloads finish or cleanup releases them.
  It has no ambient proxy, credential, cookie, redirect, or caller-header state and issues exactly
  one request per archive.
- `HttpsResponse` owns at most one response and its TLS socket from opener return until mandatory
  close. Ownership ends before transfer acceptance or error return.
- `TransferBuffer` owns one 65,536-byte mutable body buffer from immediately before the final-status
  body loop until response closure. Only one bounded memoryview is live per `readinto()` call; an
  admitted slice is fully hashed and written before reuse, and no slice escapes the owner.
- `DownloadFile` moves from absent to writing to accepted while retaining the direct fixed-name
  descriptor; every non-absent state authorizes only exact-name unlink below the retained downloads
  descriptor. Acceptance includes an exact seek-to-zero transition before lending the descriptor;
  it has no second name or install transition.
- `ArchiveScan` borrows one accepted descriptor positioned at zero and owns bounded
  decompressor/parser buffers plus the complete-byte normalized-path set bounded by 16,384 entries
  and 64 MiB of path bytes. Its first buffer both validates and retains the exact compression magic
  for decompression; it closes buffers, releases the table, and transfers no handle or semantic
  object to a caller.

| Path | Owner | Success | Failure/early exit | Required regression |
| --- | --- | --- | --- | --- |
| Make control plane | Makefile | admitted direct command or canonical option-cleared aggregate child; target-specific override shell and flags | other Make options, environment flags, alternate files, eval text, assignments, and goals are unsupported diagnostics, not a security or evidence boundary | static exact fragment; `SHELL=/bin/false` and hostile `.SHELLFLAGS` cannot replace the recipe shell; admitted direct and aggregate invocations propagate a synthetic executable failure; `-i`, `-n`, `-q`, `-t`, `-k`, `-s`, inherited `MAKEFLAGS`/`GNUMAKEFLAGS`, `-f`, `--eval`, assignment, and extra-goal cases are explicitly rejected as acceptance evidence by the harness without claiming their Make-level status |
| Fixed entrypoints and mode | Makefile + audit | admitted offline recipe and direct audit command have the exact fixed `/usr/bin/env` and Python vectors; executable receives exactly one admitted mode | no audit-data input can undergo Make or recipe-shell expansion; malformed vector fails before environment/input/root/network | static byte/token comparison for the Make recipe and documented direct command; missing/empty/repeated/unknown/positional vectors each return status 1, empty stdout, and the exact universal argument line; no `GIT245_AUDIT_*` variable or parser exists |
| Environment and minimum host | audit | exact `LC_ALL=C` map; Linux x86_64; CPython 3.12+ and required stdlib; GNU Make 4.3+ for the offline adapter | exact environment diagnostic before input/root/network | added/missing/changed environment; wrong OS/machine/Python version; missing-module injected seams; required Ubuntu 24.04 x86_64 hosted run with CPython 3.12 and GNU Make 4.3; newer author run recorded separately |
| Source lock | `InputSet` | exact bytes/hash, canonical decode/re-encode, exact semantics | all opened descriptors close; no root/network | golden bytes/hash; every key/order/type/UTF-8/NUL/CR/LF/number/string mutation; replacement/in-place/short read |
| LLVM file | `InputSet` | exact descriptor kind/link-count/mode/size/hash | descriptors close; no root/network | missing/extra/symlink/hard-link/mode/size/hash/source replacement/partial-open cases |
| `/tmp` and root relation | `InputSet` + root owner | retained no-follow `/tmp`, repository, and owned-root descriptors; `/tmp` is exact mode `01777`; repository and owned root are disjoint | descriptors close; no network | `/tmp` kind/mode/access/path-identity seams; repository under `/tmp`; equal/ancestor/descendant decisions; rename/path-identity race while descriptors remain live |
| Audit-root creation | `AuditRoot` | retained `/tmp`, create-exclusive random basename, mode-`0700` root, and fixed child retained | `/tmp`-descriptor-relative partial cleanup and absence proof | deterministic suffix collision and eight-attempt exhaustion; partial mkdir/open/chmod/fsync; parent path replacement; cleanup failure |
| Unit-root lifecycle | `UnitRoot` | create-exclusive random root and synthetic fixtures removed | exact unit/cleanup diagnostics; no repository write | deterministic suffix collision and exhaustion; exact empty environment; partial fixture creation; cleanup failure; root absence proof |
| Deadline lifecycle | `AuditDeadline` | exact 300/3,600-second work timer, at-most-60-second network operations, 30-second cleanup timer, then default/zero restoration | timeout retains the active primary; cleanup timeout appends cleanup and may leave only the exact owned root | inherited ignored handler or active timer; install/replacement/disarm/restore faults; timeout in source/download/archive/unit and cleanup; remaining-duration boundary; final default/zero proof |
| HTTPS client | `HttpsClient` | one default TLS context and exact one-handler opener issue one request for each of four sequential downloads | construction/use failure maps to the active download and releases context/opener references; no redirect is followed | exact handler list and empty `addheaders`; no proxy/auth/cookie/redirect handler; context verification flags; every non-200 status including all redirect classes; construction failure; release on first-through-fourth download exits |
| HTTPS response and body buffer | `HttpsResponse` + `TransferBuffer` | each final response closes exactly once; one 65,536-byte buffer is reused with bounded `readinto`, exact EOF probe, and no retained slice | active download remains primary; no socket, response, memoryview, or body chunk retained | opener failure; status/header rejection; readinto counts 0/1/65,535/65,536 and invalid count; locked-size boundary plus extra byte; read/hash/write/EOF/close failure; proof that unbounded `read` is never called |
| HTTPS transfer and scan handoff | `DownloadFile` | direct fixed name moves writing to accepted with exact size/hash, exact seek-to-zero, and compression-magic first read | response/file close, exact fixed-name unlink, and parent fsync | each URL/status/encoding/size/hash/write/fsync/lseek failure; failure before/after direct create and acceptance; pre-seek EOF position followed by zero-offset/magic observation; no credential/proxy/header |
| Compression | `ArchiveScan` | exactly one bounded XZ stream or gzip member, with no unused byte including zero padding | buffers and table release; accepted file remains cleanup-owned | truncation/checksum/concatenation/unused/zero-padding/unconsumed-tail/uncompressed-size/buffer/allocation limits |
| Tar scan | `ArchiveScan` | exact header dialect, complete admitted semantic set, full-byte uniqueness, and terminator | buffers and table release; accepted file remains cleanup-owned | every field, checksum, type, path, collision, long-name, terminator, entry/path/table/buffer limit in section 5.3 |
| Diagnostics | audit | PASS only after absence proof | exact primary and optional cleanup lines | every category, active-phase exception, primary+cleanup, cleanup-only, exact status/stdout/stderr |
| Unit diagnostics | focused runner | exact PASS or bounded fixed-identifier failure grammar | primary unit line retained before optional cleanup | assertion failure, overflow, invalid diagnostic byte, unit+cleanup, cleanup-only |
| Production-source binding | audit executable | both modes dispatch to the same helper objects in the same loaded source | mode-specific failure grammar | source inspection plus sentinel mutation of each production helper observed by self-test; no duplicate parser implementation |
| Normal cleanup | all owners | responses closed; downloads, children, and root absent through retained parent | primary retained; one cleanup line | failure before/after every acquisition, response transition, unlink, and cleanup operation; repeated cleanup after success is no-op |
| Python interruption | audit owner | N/A | `KeyboardInterrupt` or another Python exception entering the owner attempts ordinary bounded cleanup; the current invocation may leave at most its own one retained mode-prefixed 32-hex basename below `/tmp`; no claim or mutation applies to another invocation's root | injected `KeyboardInterrupt` after each ownership acquisition and during active transfer/scan; stale matching-root fixture remains untouched and outside the current invocation's absence/count proof; static confirmation that externally terminating signals are outside this slice |

Construction, success, failure, malformed input, cleanup, and early exit are covered above.
Replacement, move-out, returned handles, generic monomorphization, interface serialization,
whole-program/per-unit compilation, and Align allocation parity are N/A: the two modes of the
stdlib-only Python executable return only process status and text.

The public entrypoints are focused offline Make target `F`, direct fixed audit command `A`, and the
serialized Make aggregates `hosted-checks`, `capable-checks`, and `ci`, collectively `C`. `C`
includes `F` through the hosted focused list and never invokes `A`. Only `F` and `C` can occur in
one top-level Make invocation. Their complete coexistence and independent-process policy is:

| Pair | Policy | Required evidence |
| --- | --- | --- |
| `F+F` | GNU Make de-duplicates the repeated goal and runs it once | focused marker/de-duplication self-test |
| `F+C` | rejected during Makefile parsing before side effects because an aggregate must be the sole top-level goal | existing aggregate-plus-focused topology self-test, with `F` as the real focused goal |
| `C+C` | every repeated or distinct aggregate pair rejects during Makefile parsing before side effects | existing aggregate coexistence self-test |
| `A+A` | simultaneous direct processes are unsupported; sequential commands are supported after the first proves its own root absence | static policy check; two sequential real audits each pass and prove their current-invocation root absent |
| `A+F` | simultaneous independent processes are unsupported; sequential execution in either order is supported | static policy check; sequential real-audit/offline-target controls in both orders |
| `A+hosted-checks` | simultaneous independent process trees are unsupported; sequential execution in either order is supported | static policy check; audit then hosted and hosted then audit controls on a capable author host |
| `A+capable-checks` | simultaneous independent process trees are unsupported; sequential execution in either order is supported | static policy check; audit then capable and capable then audit controls on a capable author host |
| `A+ci` | simultaneous independent process trees are unsupported; sequential execution in either order is supported | static policy check; audit then `ci` and `ci` then audit controls on a capable author host |

As already required by `docs/specs/check-gate-topology.md`, separate concurrent Make processes are
unsupported caller behavior in the same or independent worktrees and are never valid verification
evidence. This slice likewise adds no cross-process repository, `/tmp`, owned-root, network, or
Align-target lock for the direct audit. It makes no safety claim for any simultaneous independent
`A`, `F`, or `C` process pair. Sequential independent processes remain supported when each
invocation satisfies its own environment, host, source, and cleanup contract.

## 7. Acceptance and pull-request boundaries

### Design pull request

Only this file, the exact hosted-target amendment in `docs/specs/check-gate-topology.md`, and
`HANDOFF.md` change. Before commit, run the author ledger/prose/matrix pass, `git diff --check`, and
`make ci ALIGN_REPO=<sibling pinned Align checkout>`. After opening the pull request, run the one
comprehensive high-effort independent-adversarial review required by `CLAUDE.md`. Apply accepted
root-cause classes in one consolidated follow-up. Run the conditional final review only if that
repair meets the material-change trigger in `CLAUDE.md`. Review/check envelopes remain external
metadata and are not copied into `HANDOFF.md`.

### Offline locked-input implementation pull request

The first implementation slice adds only:

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
its bounded synthetic fixtures in self-test mode. This slice implements source and LLVM validation,
the unit-root/deadline/diagnostic owners, both streaming decompressors, the complete tar scanner,
and the production-bound offline regressions. It adds the one exact offline Make target and inserts
it into the existing hosted focused list. Until the second slice merges, `--audit` is not a public
entrypoint and deliberately returns the universal malformed-vector result; the hosted offline
target is complete and independently useful. Because
`Makefile` is a baseline-identity artifact, the implementation must follow the source -> oracle ->
finalization commit sequence in `docs/specs/check-gate-topology.md` and refresh only the three exact
baseline paths above. It adds no Dockerfile, Docker command, workflow, registry client, extracted
artifact parser, publication path, or registration record.

This offline slice is expected to be approximately 1,200–1,600 hand-written lines because the
single production parser and the synthetic byte-level regression corpus must land atomically before
the hosted target can truthfully pass. Splitting it again would either merge unreachable parser
fragments with no independently correct public behavior, expose a focused target before all four
archive dialect/limit contracts are enforced, or introduce a second implementation module and
invalidate the reviewed same-loaded-source binding. That is the recorded reason this smallest
independently correct vertical slice may exceed the repository's approximate 1,000-line threshold.

Required offline-slice checks are:

```text
make git245-locked-inputs-unit
make gate-topology-check
python3 scripts/check-gate-topology --self-test
make format-check
make check
make build
make -j8 ci ALIGN_REPO=<sibling pinned Align checkout>
```

The offline slice is complete only when the exact lock and LLVM bytes validate, every synthetic
format/ownership/diagnostic/Make-control regression passes, cleanup proves the unit root absent, and
full-diff inspection confirms that no network, Docker, publication, or registration surface was
added. The required Ubuntu 24.04 hosted check must pass with CPython 3.12 and GNU Make 4.3; a newer
author environment is supplementary only.

### Real locked-archive audit implementation pull request

After the offline slice merges, the second implementation slice changes only:

```text
.github/image-tests/git-2.45-compat/audit-locked-archives
HANDOFF.md
```

It admits final `--audit` dispatch and adds only `AuditRoot`, `HttpsClient`, `HttpsResponse`,
`TransferBuffer`, `DownloadFile`, real-download fault seams, and the direct audit orchestration over
the already merged production scanners. It adds no Make target or graph change. Neither changed path
belongs to the coding-v1 baseline artifact manifest, so this slice does not refresh the canonical
baseline. The final executable is expected to add less than approximately 1,000 hand-written lines.

Required audit-slice checks are the offline check block above plus the exact direct audit command.
The pull request also records these sequential coexistence controls, with every `A` expanded to the
exact direct audit command and every command required to pass before the next begins:

```text
A && A
A && make git245-locked-inputs-unit
make git245-locked-inputs-unit && A
A && make hosted-checks
make hosted-checks && A
A && make capable-checks
make capable-checks && A
A && make ci
make ci && A
```

These nine lines cover `A+A`, both orders of `A+F`, and both orders of `A` with each member of `C`.
They are acceptance notation, not an additional script, Make target, cache, or public input. The
audit slice is complete only when every synthetic transfer/ownership/diagnostic regression passes,
the four real archives pass the structural audit in every `A`, each current-invocation root absence
proof succeeds, and full-diff inspection confirms that no Docker, publication, or registration
surface was added.

### Deferred Docker, hosted image, publication, and registration work

The next design must consume these exact merged inputs and independently close canonical Dockerfile
byte identity, external-process path identity, Buildx/BuildKit composite daemon ownership, image
load reconciliation, runtime container ownership, and local no-push acceptance. The hosted gate then
owns minimum-environment execution, platform credential recipients, bounded execution, and abrupt
cleanup. Publication/provenance and registration remain separate contracts. No image publication,
GHCR visibility change, or registration is authorized by this slice.
