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
| Offline target | `make git245-locked-inputs-unit`. It performs no network, Git, Docker, or repository write and is included in `make ci`. |
| Real audit target | `make git245-locked-inputs-audit GIT245_AUDIT_TEMP_ROOT=<absolute directory> GIT245_AUDIT_OPERATION_ID=<16 lowercase hexadecimal characters>`. Both variables must have Make command-line origin. It downloads and audits only the four locked archives. |
| Host | A local Linux author environment with `/usr/bin/python3`, GNU Make, HTTPS connectivity to the four locked origins, writable `/tmp`, and an explicit audit temporary root satisfying section 5. Compatibility range and minimum Python/Make version are N/A: the later hosted image gate owns minimum-environment acceptance. |
| Credentials | None. The audit rejects the exact sensitive ambient-name set before owned-root or network side effects, constructs an opener with no proxy, cookie, authentication, or caller header, and never reads or reports a sensitive value. Code review remains the trust boundary for the already-started repository process; pre-execution isolation is not claimed. |
| Output | Both Make recipes suppress command echo. Real-audit status, stdout/stderr, finite categories, and cleanup precedence are exact in section 5.4; focused-unit output is exact in section 6. No child output is streamed. |
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

### 5.1 Make adapter, arguments, paths, and environment

Executable `.github/image-tests/git-2.45-compat/audit-locked-archives` is the sole implementation
behind the real target. The Make recipe begins with `@` and invokes exactly:

```text
["/usr/bin/python3","-I","-B",<absolute audit-locked-archives>,
 "--repository-root",<absolute Make CURDIR>,
 "--temporary-root",<GIT245_AUDIT_TEMP_ROOT>,
 "--temporary-root-origin",<Make origin of GIT245_AUDIT_TEMP_ROOT>,
 "--operation-id",<GIT245_AUDIT_OPERATION_ID>,
 "--operation-id-origin",<Make origin of GIT245_AUDIT_OPERATION_ID>]
```

The two origin values must be exactly `command line`. Unknown, repeated, empty, relative, or
positional script arguments reject. Text arguments must be UTF-8 without NUL, CR, or LF.

The repository root and temporary root must each be absolute lexical-normal paths. The audit opens
every path component from `/` with no-follow directory operations and rejects a symlink ancestor,
ownership other than the current user for the temporary root, or a descriptor/path identity
mismatch. The repository root must contain the executing audit
file and exact input directory at their declared descriptor-relative paths. The temporary root must
be neither equal to, inside, nor an ancestor of the repository root. No temporary-root path
component may begin `align-llm-git245-audit-` or `align-llm-git245-input-unit-`; this prevents an
audit root from containing another audit or focused-unit root.

The owned root is exactly
`<temporary-root>/align-llm-git245-audit-<operation-id>`, must be absent, and is created mode `0700`
with one mode-`0700` `downloads` child. All later filesystem access is descriptor-relative; no
external process consumes a path below the root. The supplied roots are never removed.

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

Downloads run sequentially in the section 3 order. Each destination begins absent. The audit opens
a create-exclusive mode-`0600` `<destination>.part` sibling, constructs an HTTPS opener with an empty proxy map
and no cookie, authentication, redirect, or caller-header handler, and implements redirects itself.
It accepts only HTTPS port 443 URLs without userinfo or fragment, a final status 200, no content
encoding, at most five redirects, no repeated URL, and no HTTPS downgrade.
TLS uses `ssl.create_default_context()` with hostname and certificate verification enabled and no
caller-supplied CA, client certificate, key-log path, or context mutation.

The reader fails before buffering or writing one byte beyond the locked compressed size. It
requires exact size and SHA-256, flushes and `fsync`s the file and parent, then installs the fixed
destination without replacement while retaining the same file descriptor for scanning. A failed
transfer removes only its `.part` file. No downloaded byte is logged.

### 5.3 Compression and tar contract

The audit scans the accepted file descriptor without extracting it. Decompression and tar parsing
are streaming: at most 4 GiB uncompressed bytes, 1,000,000 logical entries, 16 KiB for one resolved
path, a 256 MiB XZ decoder memory limit, and 8 MiB total Python-owned output/parser buffers per
archive; gzip uses the fixed zlib window. Limit overflow rejects before an additional byte or entry
is accepted.

The Git input must be exactly one XZ stream and one POSIX-ustar archive. The Rust inputs must each
be exactly one gzip member and one GNU-tar archive. The decompressor must reach its end marker and
reject concatenated members/streams, unused compressed bytes, truncation, checksum failure, and
trailing nonzero bytes.

Every tar header is 512 bytes; the stored checksum must match at least one independently computed
unsigned-byte or signed-byte interpretation. Names and link names must be valid UTF-8 without NUL after field decoding, empty
components, `.`, `..`, an absolute root, or backslash. Normalized paths must remain below exactly one
top-level directory and be unique. Size, mode, checksum, and numeric fields must use admitted octal
encoding; base-256 numbers, negative values, overflow, setuid, setgid, and sticky bits reject.

Git admits only regular files, directories, and exactly one relative symbolic link whose target,
resolved from the link's parent, remains inside the top-level directory. Rust admits regular files, directories, and GNU
long-name records applying to exactly the next regular-file or directory header. Hard links, PAX,
global PAX, sparse records, devices, FIFOs, sockets, volume headers, continuation records, unknown
type flags, dangling long names, and data after the end-of-archive marker reject. Exactly two zero
blocks terminate tar; remaining decompressed bytes, if any, must be zero.

The offline unit fixtures independently cover one valid Git dialect, one valid Rust dialect, each
compression failure, both checksum interpretations, every admitted/rejected type flag, path and
link traversal, duplicate normalized paths, numeric/mode limits, GNU long-name state, terminator
placement, concatenation, and trailing bytes. The four real locked archives must also pass.

### 5.4 Status, validation order, and cleanup

The audit executable launches no child and streams no nonsemantic output. Success status is zero,
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

1. Make-origin and argument grammar;
2. sensitive ambient names;
3. repository/input/script descriptors, source-lock bytes/semantics, and LLVM bytes;
4. temporary-root ancestry, ownership, reserved-component, and absent-owned-root checks;
5. owned-root construction;
6. the four downloads in section 3 order; and
7. the four archive scans in section 3 order.

Argument failures map to `argument`, ambient names to `environment`, input validation to `source`,
root operations to `filesystem`, and each transfer/scan to its named category. An unexpected
exception maps to the active phase, or `internal` if no phase owns it. Cleanup then closes all
descriptors, unlinks fixed archive/partial names, removes fixed children, and removes the owned root
descriptor-relatively in reverse acquisition order. Cleanup failure appends exactly one final
`cleanup` line and never masks the primary. A cleanup-only failure emits only the cleanup line.
PASS is emitted only after cleanup proves the owned root absent.

## 6. Ownership and closure matrix

Offline target `make git245-locked-inputs-unit` has the silent exact recipe
`["/usr/bin/python3","-I","-B",<absolute test-locked-inputs>]`; the executable accepts no
argument, ignores caller `TMPDIR`, and performs no network or child-process call. Success status is
zero with exact stdout `git 2.45 locked-input unit tests: PASS` plus LF and empty stderr. Failure
status is 1 with empty stdout and bounded UTF-8 stderr: at most 1 MiB, LF-terminated lines without
NUL or CR. Fixed diagnostic lines are followed by exact primary line
`git 2.45 locked-input unit tests: ERROR unit`; when owned-root cleanup also fails, one exact
`git 2.45 locked-input unit tests: ERROR cleanup` line follows it. A cleanup-only failure emits only
the cleanup line. Other diagnostic lines contain only fixed checked-in test identifiers and
assertion categories, never fixture or environment bytes.

`audit-locked-archives` owns argument/environment validation, source descriptors, HTTPS transfer,
stream parsing, diagnostics, and cleanup. `test-locked-inputs` owns synthetic fixtures and private
mode-`0700` directories created directly below `/tmp` with prefix
`align-llm-git245-input-unit-`; it opens `/tmp` without following a symlink, requires a writable
sticky directory, ignores caller `TMPDIR`, and appends 32 lowercase hexadecimal characters from
`secrets.token_hex(16)`. It makes at most eight create-exclusive attempts, treats exhaustion as a
unit failure before fixture creation, and removes every owned root. The Makefile
owns only silent exact adapters and inclusion of the offline target in `make ci`.

The implementation uses five ordinary, non-persisted ownership records:

- `InputSet` retains no-follow descriptors for the repository root, audit file, input directory,
  lock, and LLVM file until all input validation completes, then closes them.
- `AuditRoot` owns the absent-then-created root and fixed child descriptors until proved absent.
- `UnitRoot` owns one create-exclusive random directory directly below `/tmp`; it never accepts a
  caller path and removes only descriptor-retained synthetic fixtures below that root.
- `DownloadFile` moves from absent to partial to installed while retaining the created descriptor;
  every non-absent state authorizes only exact-name unlink below the retained downloads descriptor.
- `ArchiveScan` borrows one installed descriptor and owns bounded decompressor/parser buffers; it
  closes buffers and transfers no handle or semantic object to a caller.

| Path | Owner | Success | Failure/early exit | Required regression |
| --- | --- | --- | --- | --- |
| Make/argument validation | audit | exact command-line origins and argument grammar | no input/root/network side effect | missing/environment-origin/empty/relative/repeated/unknown/positional/NUL/CR/LF cases |
| Sensitive environment | audit | no rejected name present | no input/root/network side effect; value unread | every exact/suffix name, case boundaries, clean environment, value-not-read sentinel |
| Source lock | `InputSet` | exact bytes/hash, canonical decode/re-encode, exact semantics | all opened descriptors close; no root/network | golden bytes/hash; every key/order/type/UTF-8/NUL/CR/LF/number/string mutation; replacement/in-place/short read |
| LLVM file | `InputSet` | exact descriptor kind/link-count/mode/size/hash | descriptors close; no root/network | missing/extra/symlink/hard-link/mode/size/hash/source replacement/partial-open cases |
| Root relation | `InputSet` | canonical no-symlink roots are disjoint and reserved-component-free | descriptors close; no creation/network | root equal/ancestor/descendant; symlink ancestor; rename/path-identity race; reserved component; wrong owner |
| Audit-root creation | `AuditRoot` | exact absent root and children retained | descriptor-relative partial cleanup | collision; partial mkdir/open/chmod/fsync; cleanup failure |
| Unit-root lifecycle | `UnitRoot` | create-exclusive random root and synthetic fixtures removed | exact unit/cleanup diagnostics; no repository write | collision retry; ignored `TMPDIR`; partial fixture creation; cleanup failure; root absence proof |
| HTTPS transfer | `DownloadFile` | exact fixed file size/hash installed | exact partial removed | each URL/redirect/status/encoding/size/hash/write/fsync/install failure; no credential/proxy/header |
| Compression | `ArchiveScan` | exactly one bounded XZ stream or gzip member | buffers close; installed file remains cleanup-owned | truncation/checksum/concatenation/unused/trailing/size/buffer limits |
| Tar scan | `ArchiveScan` | complete admitted semantic set and terminator | buffers close; installed file remains cleanup-owned | every golden and mutation class in section 5.3, entry/path/buffer limits |
| Diagnostics | audit | PASS only after absence proof | exact primary and optional cleanup lines | every category, active-phase exception, primary+cleanup, cleanup-only, exact status/stdout/stderr |
| Unit diagnostics | focused runner | exact PASS or bounded fixed-identifier failure grammar | primary unit line retained before optional cleanup | assertion failure, overflow, invalid diagnostic byte, unit+cleanup, cleanup-only |
| Normal cleanup | all owners | downloads, children, and root absent | primary retained; one cleanup line | failure before/after every acquisition and cleanup operation; repeated cleanup after success is no-op |
| Caller interruption | caller | N/A | exact root may remain; no automatic broad deletion | documentation/static contract only |

Construction, success, failure, malformed input, cleanup, and early exit are covered above.
Replacement, move-out, returned handles, generic monomorphization, interface serialization,
whole-program/per-unit compilation, and Align allocation parity are N/A: both executables are
stdlib-only Python commands that return only process status and text.

The public entrypoints are focused offline target `F`, real audit target `A`, and aggregate
`make ci` target `C`; `C` includes `F` and never invokes `A`. Their complete same-worktree policy is:

| Pair | Policy | Required evidence |
| --- | --- | --- |
| `F+F` | safe; create-exclusive random unit roots below `/tmp` are disjoint | simultaneous focused smoke |
| `F+A` | safe; prefixes differ and `A` is outside the repository | injected overlap smoke |
| `F+C` | safe even though `C` invokes another `F` | Make dependency and simultaneous focused smoke |
| `A+A` | distinct operation roots are safe; an exact collision rejects the second before network | distinct-root overlap and collision smokes |
| `A+C` | safe because `A` writes only outside the repository and `C` never edits locked inputs | Make dependency/static write-set test |
| `C+C` | unsupported in one worktree because aggregate build outputs are shared | documentation/static contract only |

Independent worktrees follow the same `F` and `A` rules. `C+C` is also unsupported across worktrees
when both use the same Align checkout or target directory; otherwise their worktree-local outputs
are independent. Audit temporary roots remain outside and non-ancestral to their repository. Two
audits with the same exact operation path have one winner and one side-effect-free collision
failure; distinct paths are independent.

## 7. Acceptance and pull-request boundaries

### Design pull request

Only this file and `HANDOFF.md` change. Before commit, run the author ledger/prose/matrix pass,
`git diff --check`, and `make ci ALIGN_REPO=<sibling pinned Align checkout>`. After opening the pull
request, run the one comprehensive high-effort independent-adversarial review required by
`CLAUDE.md`. Apply accepted root-cause classes in one consolidated follow-up. An ordinary
finding-only repair does not invalidate that review; run the one conditional final review only for
the material triggers in the repository workflow. Review/check envelopes remain external metadata
and are not copied into `HANDOFF.md`.

### Locked-input implementation pull request

The implementation adds only:

```text
.github/images/git-2.45-compat/inputs/sources.json
.github/images/git-2.45-compat/inputs/llvm.sh
.github/image-tests/git-2.45-compat/audit-locked-archives
.github/image-tests/git-2.45-compat/test-locked-inputs
.github/image-tests/git-2.45-compat/fixtures/...
```

It also adds the two exact Make targets, includes only the offline target in `make ci`, adds narrowly
required contributor documentation, and updates `HANDOFF.md`. It adds no Dockerfile, Docker command,
workflow, registry client, artifact parser, publication path, or registration record.

Required checks are:

```text
make git245-locked-inputs-unit
make git245-locked-inputs-audit \
  GIT245_AUDIT_TEMP_ROOT=<absolute external writable directory> \
  GIT245_AUDIT_OPERATION_ID=0000000000000001
make format-check
make check
make build
make ci ALIGN_REPO=<sibling pinned Align checkout>
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
