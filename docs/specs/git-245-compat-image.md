# Git 2.45 compatibility image

## 1. Purpose and delivery order

This enabling artifact supplies the immutable minimum-Git environment required by the common
fresh-compiler topology and later pin-changing Align adoptions. Request 7 requires its production
adoption gate to exercise `GIT_NO_LAZY_FETCH` with a real `/usr/bin/git` whose output is exactly
`git version 2.45.0`. A synthetic version string or a newer hosted runner is not minimum-version
evidence.

No suitable public image with that exact binary and the required hosted build toolchain is
registered. Delivery therefore has six reviewed repository slices and two explicit external
transitions:

1. this design merges;
2. the image source, source-lock validator, and runtime self-test merge after a local no-push
   build;
3. direct-process, OCI, archive, and credential-validation tooling merges against local synthetic
   fixtures and an unpushed OCI archive;
4. publisher, provenance, and registration validation tooling merges against the already-merged
   lower layers and a fake registry;
5. the publisher workflow merges after all non-publishing workflow tests;
6. a repository owner dispatches that workflow from the exact merged `main`;
7. on first creation, the owner of the personal GHCR package changes its default-private
   visibility to public and dispatches a new complete run; the first candidate remains
   unregistered;
8. a digest-registration pull request preserves the exact successful provenance as
   `.github/images/git-2.45-compat/provenance.json` and records that public candidate in
   `.github/images/git-2.45-compat/published.json`.

`docs/specs/check-gate-topology.md` may name the image only after step 8 merges. No consumer uses a
tag, an unregistered digest, a pull-request image, or an image produced from an unmerged commit.
Registration supplies an immutable environment candidate. The later topology and Request 7
compatibility jobs, not this slice, prove the production Git parser, full topology self-test, and
pinned Align build in that environment.

The image does not change `.align-revision`, product behavior, evaluation semantics, or the current
compiler pin.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Image repository | `ghcr.io/sanohiro/align-llm/git-2.45-compat`. Each publisher run uses the audit-only candidate tag `candidate-<decimal run_id>-<decimal run_attempt>`. Tags are never accepted identities, never promoted, and never recorded or consumed. |
| Image identity | Consumers use only `ghcr.io/sanohiro/align-llm/git-2.45-compat@sha256:<64 lowercase hex>` from `published.json`. The digest names one OCI image manifest, not an image index or tag. |
| OCI graph | The root object has exactly the fields `schemaVersion`, `mediaType`, `config`, and `layers`; media type is `application/vnd.oci.image.manifest.v1+json`, schema version is 2, config is one descriptor of media type `application/vnd.oci.image.config.v1+json`, and layers is a nonempty ordered descriptor array whose media type is always `application/vnd.oci.image.layer.v1.tar+gzip`. The config object says `os=linux`, `architecture=amd64`, and has no variant. Every descriptor has exactly `mediaType`, `digest`, and `size`, with a positive integer size and a `sha256:` plus 64-lowercase-hex digest. Fetched byte counts and hashes must match. No annotation, index, subject, artifact type, SBOM, provenance, signature, or referrer is part of this image contract. |
| Runtime Git | `/usr/bin/git --version` emits exactly `git version 2.45.0` plus LF and exits zero. `/usr/bin/git` is the selected `git` under `PATH=/opt/rust/bin:/usr/lib/llvm-22/bin:/usr/local/bin:/usr/bin:/bin`; no second Git precedes it. |
| Hosted toolchain | Ubuntu 24.04 amd64 userland; `/usr/bin/python3` is Python 3.10 or newer; `/usr/bin/make` is GNU Make 4.3 or newer; `/opt/rust/bin/cargo` and `/opt/rust/bin/rustc` are exactly 1.96.0; LLVM Config and Clang have major 22; the pinned Align workspace's native libraries are installed. Image configuration requires `CARGO_HOME=/opt/cargo`, `LLVM_SYS_221_PREFIX=/usr/lib/llvm-22`, `LLVM_CONFIG=/usr/lib/llvm-22/bin/llvm-config`, and `PATH=/opt/rust/bin:/usr/lib/llvm-22/bin:/usr/local/bin:/usr/bin:/bin`; no toolchain state is installed under `/root`. |
| Source lock | `.github/images/git-2.45-compat/sources.json`, schema version 1, owns every fixed source, action, builder, toolchain version, image parameter, post-pull command, and credential-scan rule named below. It is canonical two-space-indented UTF-8 JSON plus one final LF. |
| Image source | `.github/images/git-2.45-compat/Dockerfile` is the only Dockerfile. Its build context is exactly `.github/images/git-2.45-compat/`; it copies only validated tracked paths from that directory. It uses the locked Ubuntu digest; verifies Git, the Rust channel manifest and three component archives, and the LLVM installer before first execution or extraction; installs Git under `/usr` and Rust under `/opt/rust`; and removes downloads and extracted build source in their creating stage. |
| Publisher | `.github/workflows/publish-git-245-compat.yml` is `workflow_dispatch` only and declares no inputs. It accepts only `refs/heads/main`, checks out exact `GITHUB_SHA`, validates a clean exact source set, creates one unique candidate, records the immutable Buildx output digest, verifies only that digest, performs authenticated and then credential-free digest-only pulls, runs the complete post-pull bundle, and uploads canonical publisher provenance. |
| Pinned actions | `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5`, `docker/login-action@b45d80f862d83dbcd57f89517bcf500b2ab88fb2`, and `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`. Checkout uses `persist-credentials=false`. No other remote action is used. |
| Fixed builder | Buildx `v0.34.1` is downloaded from the locked official linux-amd64 asset and byte-hash verified before installation or execution. The manually created `docker-container` builder uses `moby/buildkit@sha256:0168606be2315b7c807a03b3d8aa79beefdb31c98740cebdffdfeebf31190c9f` (BuildKit `v0.30.0`), whose locked linux/amd64 child is `sha256:57269d1784e49b46228c45a1a1b870fbe40e0a639ab60b37b032d83af5bccdfc` and config/image ID is `sha256:6db049f808b3e0c0694b3522d85b5a9bee4a0248a1dc67559e05f57cc0f68bdd`; one unique builder name is `git245-<run_id>-<run_attempt>`. |
| Build parameters | Exactly `linux/amd64`, `pull=true`, `no-cache=true`, registry output with `oci-mediatypes=true`, `image-manifest=true`, `compression=gzip`, `compression-level=6`, and `force-compression=true`, plus `provenance=false` and `sbom=false`. There are no build arguments, secrets, SSH mounts, cache imports, cache exports, additional contexts, labels derived from an event, or caller-selected outputs. |
| Invocation and options | The publisher has only `workflow_dispatch` with no inputs. Repository, platform, source, builder, output, tag, checks, timeouts, and scan rules come only from reviewed workflow/source-lock bytes; there is no environment, repository variable, secret, or caller option that changes their semantics. GitHub supplies only the validated event/ref/SHA, run identity, runner identity, and `GITHUB_TOKEN`. |
| Cache identity | N/A: build cache import/export is forbidden and `no-cache=true`; hosted runner state is disposable. Registry blobs are content-addressed output, not a selected cache. |
| Publication permissions | Only `contents: read` and `packages: write`; unspecified permissions are `none`. `GITHUB_TOKEN` reaches only the pinned checkout and login actions; checkout does not persist it, and login writes only the isolated temporary `DOCKER_CONFIG`. It is not a Buildx input or persisted field. |
| Publication concurrency | Workflow concurrency group `publish-git-245-compat`, `cancel-in-progress: false`, `queue: max`. Up to 100 pending runs execute one at a time in FIFO order by the time each starts waiting; dispatch-time ordering is not promised. A 101st pending run is canceled before job-side effects and is not publication evidence. Registry writers outside this workflow are not serialized; the candidate tag is therefore only a locator and the returned immutable digest plus complete provenance are always revalidated. |
| Default-private bootstrap | The first push can create a private personal package. If credential-free manifest resolution or pull returns an authentication/authorization failure, the run emits `Git 2.45 compatibility package visibility must be public`, records no successful provenance, and fails. The package owner `sanohiro` may then use GHCR package settings to make it public; that irreversible external action is not inferred or automated. A new full dispatch produces the only registrable candidate. |
| Publisher provenance | `git-245-compat-provenance.json`, schema version 1, binds the source commit and every current source/action/helper/tool identity to the returned image manifest, config, ordered layers, package inventory, post-pull results, and Actions run. The pinned upload action stores it for 30 days as `git-245-compat-provenance-<run_id>-<run_attempt>` with `if-no-files-found=error`, `compression-level=0`, `overwrite=false`, and `include-hidden-files=false`. It is copied byte-for-byte to the reviewed registered provenance and is not an OCI attestation. |
| Registered provenance | `.github/images/git-2.45-compat/provenance.json` is byte-identical to the successful publisher provenance artifact. It is the durable repository source of truth for how the registered image was produced. |
| Registered record | `.github/images/git-2.45-compat/published.json`, schema version 1, contains only the immutable fields defined below. This reviewed file is the sole consumer source of truth for image identity. |
| Public availability | Before registration, a client with a new empty Docker configuration, no GHCR credential, and no local copy must resolve and pull the digest. The test removes any local tag or manifest reference first and verifies the remote returned manifest bytes hash to the registered digest. A private package, local-only hit, tag lookup, or authenticated fallback fails. |
| Retention | The registered manifest and referenced config/layers are immutable required project inputs and must not be deleted. Unregistered candidates are never selected automatically. Their later registry cleanup is a separate package-owner action; this design does not authorize deleting any package version. |
| Metric | N/A: this prerequisite makes no performance claim. Acceptance is exact compatibility and provenance evidence; later gates remain responsible for time-to-passing-patch measurements. |

## 3. Canonical source and record formats

### 3.1 Source lock

`sources.json` has these keys in exact order:

```text
schema_version
base_image
base_manifest_digest
base_amd64_digest
git_source_url
git_version
git_source_sha256
rust_channel_manifest_url
rust_channel_manifest_sha256
rust_version
rust_components
llvm_installer_url
llvm_installer_sha256
llvm_major
apt_packages
actions
buildx_version
buildx_asset_url
buildx_asset_sha256
buildkit_image
buildkit_version
buildkit_manifest_digest
buildkit_amd64_digest
buildkit_amd64_config_digest
platform
build_parameters
checks
forbidden_environment
forbidden_paths
```

Fixed values are:

```text
schema_version = 1
base_image = "docker.io/library/ubuntu"
base_manifest_digest = "sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90"
base_amd64_digest = "sha256:52df9b1ee71626e0088f7d400d5c6b5f7bb916f8f0c82b474289a4ece6cf3faf"
git_source_url = "https://www.kernel.org/pub/software/scm/git/git-2.45.0.tar.xz"
git_version = "2.45.0"
git_source_sha256 = "0aac200bd06476e7df1ff026eb123c6827bc10fe69d2823b4bf2ebebe5953429"
rust_channel_manifest_url = "https://static.rust-lang.org/dist/channel-rust-1.96.0.toml"
rust_channel_manifest_sha256 = "9af50610e1d82699f78a40b985c9277ae1a2c5a0bec86ae430cfe58832038285"
rust_version = "1.96.0"
llvm_installer_url = "https://apt.llvm.org/llvm.sh"
llvm_installer_sha256 = "9474ecd78b52aba6e923976b1e9773f5613027cc7e237b9956986cb536e02a36"
llvm_major = 22
buildx_version = "v0.34.1"
buildx_asset_url = "https://github.com/docker/buildx/releases/download/v0.34.1/buildx-v0.34.1.linux-amd64"
buildx_asset_sha256 = "f1332ddb9010bd0b72628266c3a906d9a6979848033df4c8d9bd2cd113bae12b"
buildkit_image = "docker.io/moby/buildkit"
buildkit_version = "v0.30.0"
buildkit_manifest_digest = "sha256:0168606be2315b7c807a03b3d8aa79beefdb31c98740cebdffdfeebf31190c9f"
buildkit_amd64_digest = "sha256:57269d1784e49b46228c45a1a1b870fbe40e0a639ab60b37b032d83af5bccdfc"
buildkit_amd64_config_digest = "sha256:6db049f808b3e0c0694b3522d85b5a9bee4a0248a1dc67559e05f57cc0f68bdd"
platform = "linux/amd64"
```

`rust_components` has exact object key order `name`, `url`, `sha256`, is ordered `cargo`,
`rust-std`, `rustc`, and has these values copied from the locked channel manifest and independently
download-verified:

```text
cargo
  https://static.rust-lang.org/dist/2026-05-28/cargo-1.96.0-x86_64-unknown-linux-gnu.tar.gz
  b691a9e31b1e5498017be91155a1e7501eccf6437e7dc9ff1896e38aa1584dbf
rust-std
  https://static.rust-lang.org/dist/2026-05-28/rust-std-1.96.0-x86_64-unknown-linux-gnu.tar.gz
  36e577b66f7b2f8fc6493f97f81329e5f6e1514360d0c6c31d5d8463184e6773
rustc
  https://static.rust-lang.org/dist/2026-05-28/rustc-1.96.0-x86_64-unknown-linux-gnu.tar.gz
  71143d6075582b7e65233992c77e375aadbec4dfda6df2675160bf05b89410f9
```

`apt_packages` is the following ASCII-byte-sorted array of explicitly requested top-level packages;
repository-resolved dependencies remain mutable publisher inputs captured by the inventory:

```text
build-essential
ca-certificates
clang-22
curl
gettext
gnupg
libclang-rt-22-dev
libcurl4-openssl-dev
libexpat1-dev
libssl-dev
libzstd-dev
llvm-22-dev
lsb-release
make
perl
pkg-config
python3
software-properties-common
wget
xz-utils
zlib1g-dev
```

`actions` has the three ledger names and commit values in ledger order. `build_parameters` has exact
key order `pull`, `no_cache`, `oci_mediatypes`, `image_manifest`, `compression`,
`compression_level`, `force_compression`, `provenance`, `sbom`; values are respectively `true`,
`true`, `true`, `true`, `"gzip"`, `6`, `true`, `false`, `false`.

`checks` is a nonempty ordered array of nonempty argument-vector arrays. `forbidden_environment`
contains exact names `GITHUB_TOKEN`, `GH_TOKEN`, `ACTIONS_RUNTIME_TOKEN`,
`ACTIONS_ID_TOKEN_REQUEST_TOKEN`, `DOCKER_AUTH_CONFIG`, `DOCKER_CONFIG`, `REGISTRY_AUTH_FILE`, and
`OPENAI_API_KEY`, followed by the ASCII case-insensitive suffix rule
`(^|_)(TOKEN|PASSWORD|SECRET|CREDENTIAL|CREDENTIALS|PRIVATE_KEY|API_KEY)$`.
`forbidden_paths` contains `/root/.docker`, `/root/.config/gh`, `/root/.config/git`,
`/root/.cargo`, `/root/.rustup`, `/github/home/.docker`, and `/github/workflow`.

The validator rejects duplicate commands, an empty argument, unknown or reordered keys, a scalar
type mismatch, noncanonical JSON numbers or escapes, invalid UTF-8, NUL, CR, missing/extra LF, and
any semantic value that does not equal this contract. It re-encodes with two-space indentation,
`ensure_ascii=false`, and one LF and requires exact byte equality.

For each Rust component, the Dockerfile rechecks the locked manifest's exact target section,
downloads and verifies the archive, extracts it only afterward, and invokes that archive's
`install.sh --prefix=/opt/rust --disable-ldconfig`. All three downloads and extracted directories
are removed in the same layer after installation.

### 3.2 Helper-tree identity

`helper_tree_sha256` covers every tracked build-context path other than `Dockerfile` and
`sources.json`, sorted by raw UTF-8 path bytes. The framed byte stream is:

```text
ASCII "align-llm-git245-helper-tree-v1" ; u8 0
repeat:
  u32be path_byte_count
  path UTF-8 bytes
  u32be Git mode token (100644 or 100755) interpreted as a base-8 integer
  u64be content_byte_count
  raw content bytes
u32be 0
```

Paths are nonempty relative slash-separated names with no empty, `.`, `..`, or `.git`
component, so the zero path length is an unambiguous terminator. Symlinks, directories as records,
other modes, duplicate paths, and prefix collisions reject.

The independently checked one-file golden vector for path `a`, mode `100644`, and bytes `x` is:

```text
616c69676e2d6c6c6d2d6769743234352d68656c7065722d747265652d7631000000000161000081a400000000000000017800000000
sha256 cf1ca3f7bae65b4d1d0d583016352fbc8ac81660698ffdcfa3716862bf43349d
```

### 3.3 Publisher provenance and registered record

Publisher provenance keys, in exact order, are:

```text
schema_version                 integer 1
source_commit                 40 lowercase hex
source_lock_sha256            64 lowercase hex
dockerfile_sha256             64 lowercase hex
helper_tree_sha256            64 lowercase hex
workflow_sha256               64 lowercase hex
actions                       exact source-lock action object
publisher_tools               runner_image, docker_client, docker_server, buildx, buildkit
package_inventory             dpkg records and Rust component records defined below
package_inventory_sha256      64 lowercase hex
image_repository              exact ledger repository
image_digest                  "sha256:" plus 64 lowercase hex
config_digest                 "sha256:" plus 64 lowercase hex
layer_digests                 nonempty ordered array of "sha256:" digests
post_pull_checks              ordered check-result array
publication_run_id            nonzero decimal string without leading zero
publication_run_attempt       positive integer
publication_artifact_name     derived exact artifact name
publication_run_url           HTTPS Actions URL without query or credentials
```

`publisher_tools` has exact key order `runner_image`, `docker_client`, `docker_server`, `buildx`,
`buildkit`. `runner_image` is an object with exact key order `image_os`, `image_version` copied from
the hosted runner's nonempty `ImageOS` and `ImageVersion`. The remaining values are exact
single-line UTF-8 observations without LF from, respectively,
`["docker","version","--format","{{.Client.Version}}"]`,
`["docker","version","--format","{{.Server.Version}}"]`,
`["docker","buildx","version"]`, and the captured builder node's BuildKit version. The mutable
`ubuntu-24.04` runner image and Docker Engine are explicit
external publisher trust roots, not reproducibility claims. Pinned remote actions, Buildx, and
BuildKit are fixed inputs.

`package_inventory` has exact key order `dpkg`, `rust_components`. `dpkg` is a nonempty array of objects
with exact key order `name`, `version`, `architecture`, byte-sorted by the corresponding
tab-separated line. `rust_components` is byte-identical to the source-lock array. Names, versions,
architectures, URLs, and hashes are nonempty UTF-8 without NUL, CR, LF, or tab. Duplicate records
reject.

`package_inventory_sha256` hashes this framed projection of those exact arrays:

```text
ASCII "align-llm-git245-inventory-v1" plus LF
ASCII "[dpkg]" plus LF
LC_ALL=C byte-sorted lines from:
  dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n'
ASCII "[rust-components]" plus LF
source-lock-order lines:
  component name, TAB, URL, TAB, bare SHA-256, LF
```

Both reports must be nonempty UTF-8 without NUL or CR, each record must end in exactly one LF, and
duplicate lines reject. Ubuntu and LLVM package repositories are mutable network trust inputs; the
immutable output digest and inventory identify the realized candidate, but a later rebuild is a new
candidate.

Each `post_pull_checks` record has exact key order `command`, `stdout_sha256`, `status`;
`command` equals its source-lock argument vector, `stdout_sha256` is 64 lowercase hex, and `status`
is integer zero. `publication_artifact_name` is exactly
`git-245-compat-provenance-<publication_run_id>-<publication_run_attempt>`, and
`publication_run_url` is exactly
`https://github.com/sanohiro/align-llm/actions/runs/<publication_run_id>`. Publisher provenance uses
canonical two-space-indented UTF-8 JSON plus LF.

`published.json` has exact key order:

```text
schema_version
source_commit
image_repository
image_digest
config_digest
provenance_sha256
publication_run_id
publication_run_attempt
publication_run_url
```

The first value is integer 1; identities have the spellings above; `provenance_sha256` is the bare
64-lowercase-hex digest of the complete successful provenance bytes. Registration first requires
`provenance.json` to be byte-identical to the downloaded successful-run artifact. It then copies
semantic values from that file and independently regenerates canonical `published.json` bytes. No
field is optional, nullable, or extensible in version 1.

## 4. Publisher ownership, trust, and execution

The publisher owns its temporary Docker configuration, checked-out source view, unique Buildx
builder, test containers, bounded diagnostics, and provenance file for one job. The registry owns
pushed candidate blobs/manifests. The repository owns reviewed source, `provenance.json`, and
`published.json`.

The publisher runs on `ubuntu-24.04` with a 90-minute job deadline. Source validation has five
minutes; builder installation/bootstrap has ten minutes; build/push has 45 minutes; each registry
operation or post-pull command has ten minutes; provenance formation/upload and final cleanup each
have five minutes. The workflow
downloads Buildx into the isolated temporary Docker configuration, verifies its exact SHA-256
before setting executable mode or invoking Docker, and manually creates the builder. Before setup,
it snapshots daemon container IDs and requires no builder with the unique name. If creation or
bootstrap fails before one exact new builder-container ID is returned and its image ID is verified
against the locked BuildKit config digest, the workflow does not delete by name and relies on
disposal of the
dedicated ephemeral runner. After identity capture, cleanup addresses only that ID. Test containers
carry exact run-id and run-attempt labels and cleanup removes only IDs returned by a query that
matches both labels.

Checked-in process helpers own only their direct child: new session, binary stdout/stderr pipes,
concurrent draining, at most 65,536 retained bytes from each stream while continuing to drain,
deadline, `SIGTERM`, five-second grace, `SIGKILL`, direct reap, reader completion, and descriptor
closure. Stream overflow is a failure, not a truncated success. They never signal a numeric session
after the direct child is reaped. Escaped descendants of fixed trusted Docker/system tools are
outside that helper guarantee and are owned by the fixed Docker/Buildx tools or dedicated
ephemeral runner disposal. The publisher makes no general untrusted-command or
same-runner-multi-tenant containment claim.

The cleanup step runs with `if: always()`. An abrupt runner loss can leave an immutable unregistered
candidate, but cannot write `published.json` or make a tag a consumer identity. Cleanup never
deletes registry content, a caller path, the workspace, runner root, or home directory.

Every remote action is pinned in the ledger. The hosted runner image, Docker client/daemon, Ubuntu
and LLVM repositories, kernel.org, static.rust-lang.org, GitHub release assets, Docker Hub, and
GHCR are named external trust inputs. The Git source, Rust channel manifest and three component
archives, LLVM installer, and Buildx executable are complete-hash validated before use. The image
source also requires the three Rust URL/hash pairs to equal the locked manifest before installing
the archives. The builder resolves only the locked BuildKit manifest and verifies its selected
child and reported version.

The workflow creates `DOCKER_CONFIG` mode `0700`, logs in only after source validation, and never
passes its path or credential to the build context, BuildKit arguments, secrets, cache, or image.
After digest-only pull, the scanner checks:

- image config environment variable names against every exact and suffix rule;
- config labels and history strings for every forbidden name;
- the complete extracted final filesystem for forbidden paths and regular-file contents containing
  the actual `GITHUB_TOKEN` bytes, any other available protected-token bytes, or a scanner-only
  canary;
- raw manifest/config/layer bytes for the same protected values and canary; and
- build metadata for an unexpected build argument, secret, SSH, cache, context, label, or output.

The scanner receives each available protected value without logging it, never persists any value,
and emits only bounded English categories. An unavailable optional runner token is recorded as
unavailable rather than synthesized. Any match fails. Logout and validated temporary-config
cleanup are mandatory; a cleanup failure does not replace an earlier error.

For every layer, scanning includes the raw blob and the fully decompressed tar headers, path names,
link targets, PAX records, extended attributes, and regular-file byte streams. Final-filesystem
scanning searches every regular file for either byte sequence; it is not limited to whole-file
equality. This covers a credential added and deleted in different layers as well as one present in
the final filesystem. Extraction rejects absolute paths, `..`, device nodes, unsupported
compression, malformed archives, and links that escape the temporary root before reading content.

## 5. Deterministic validation and error order

The publisher uses this fail-fast order:

1. event, `refs/heads/main`, full `GITHUB_SHA`, and queued-run bound;
2. exact checkout HEAD, tracked required paths, clean index/worktree, source-lock bytes, and helper
   tree;
3. isolated Docker configuration, pinned action/workflow identities, Buildx asset hash, and
   mutable publisher-tool observations;
4. authenticated registry login;
5. dedicated-daemon empty-name precondition, builder creation, exact builder identity, and locked
   BuildKit child;
6. checked-in runner invocation of `docker buildx build`, its metadata-file immutable digest, and
   candidate push;
7. digest-only OCI graph, config, layers, package inventory, and credential scan;
8. authenticated digest-only pull and complete checks;
9. remove local reference; new empty unauthenticated Docker configuration; remote manifest byte
   hash; credential-free digest-only pull and complete checks;
10. canonical provenance generation and upload; and
11. logout, exact builder/container cleanup, and temporary-owner cleanup.

If step 9 fails specifically because the package is private, the exact visibility diagnostic wins,
no successful provenance is recorded, and later registration is impossible. The owner action and
new dispatch restart at step 1; an earlier candidate supplies no accepted evidence.

Error precedence is external cancellation, job/phase deadline, command launch/read/wait failure,
nonzero or output mismatch, OCI/identity/credential postcondition, provenance serialization, then
cleanup. Cleanup is always attempted; an earlier failure remains primary and a bounded cleanup
category is appended.

Registration accepts only a workflow run whose final GitHub conclusion is `success`. An uploaded
provenance artifact from a run whose post-job action or cleanup later fails is not registrable.

## 6. Build and runtime checks

The source-lock `checks` array is exactly these argument vectors in this order:

```text
["/usr/bin/git", "--version"]
["/usr/bin/python3", "--version"]
["/usr/bin/make", "--version"]
["/opt/rust/bin/cargo", "--version"]
["/opt/rust/bin/rustc", "--version"]
["/usr/lib/llvm-22/bin/llvm-config", "--version"]
["/usr/bin/clang-22", "--version"]
["/usr/local/libexec/align-llm/git245-image-self-test"]
```

Git stdout is byte-exact. Python parses to at least 3.10; GNU Make to at least 4.3; Cargo and Rustc
to exactly 1.96.0; LLVM and Clang to major 22. The final self-test emits exactly
`git 2.45 compatibility image self-test: PASS` plus LF after it:

- executes a tiny `cargo --locked --offline` build with an empty target;
- compiles, links, and runs a tiny C program with Clang 22;
- verifies the default `PATH` selects `/usr/bin/git`; and
- proves no Docker socket or inherited GHCR credential is visible inside the test container.

The tiny projects are checked-in build-context fixtures with exact stdout and no registry access.
Package inventory and credential scanning are publisher-side observations, not commands inside the
candidate. The image uses only byte-exact Git-version comparison; it does not implement or consume
the later production Git-version parser.

## 7. Implementation ownership and workflow-facing commands

The implementation uses these exact owners:

- `.github/images/git-2.45-compat/Dockerfile`, `sources.json`, `runtime-self-test`, and
  `test-image-source` own the build and image-local gate.
- `.github/images/git-2.45-compat/contract.py` owns canonical source-lock, helper-tree,
  provenance, and registered-record formats.
- `.github/images/git-2.45-compat/process_runner.py` owns direct-child execution and diagnostic
  bounds.
- `.github/images/git-2.45-compat/oci_inspector.py` owns OCI validation, archive extraction,
  credential scanning, and image inventory over caller-supplied byte streams.
- `.github/images/git-2.45-compat/publisher.py` owns authenticated/anonymous registry retrieval and
  workflow orchestration across those modules.
- `.github/images/git-2.45-compat/tests/` and executables
  `.github/images/git-2.45-compat/test-oci-tools` and `test-publisher-tools` own offline fixtures
  and tests.
- `.github/workflows/publish-git-245-compat.yml` and executable
  `.github/images/git-2.45-compat/test-publisher-workflow` own the dispatch boundary and its
  static/synthetic regressions.

The workflow invokes only these Python entrypoints:

```text
python3 publisher.py validate-source
  --repository-root ABSOLUTE_PATH
  --source-commit 40_LOWERCASE_HEX
  --workflow .github/workflows/publish-git-245-compat.yml

python3 publisher.py verify-candidate
  --repository-root ABSOLUTE_PATH
  --source-commit 40_LOWERCASE_HEX
  --workflow .github/workflows/publish-git-245-compat.yml
  --repository ghcr.io/sanohiro/align-llm/git-2.45-compat
  --digest SHA256_DIGEST
  --authenticated-docker-config ABSOLUTE_PATH
  --anonymous-docker-config ABSOLUTE_PATH
  --builder-container-id 64_LOWERCASE_HEX
  --build-metadata ABSOLUTE_PATH
  --run-id NONZERO_DECIMAL
  --run-attempt POSITIVE_DECIMAL
  --runner-image-os NONEMPTY_TEXT
  --runner-image-version NONEMPTY_TEXT
  --protected-environment GITHUB_TOKEN
  --protected-environment GH_TOKEN
  --protected-environment ACTIONS_RUNTIME_TOKEN
  --protected-environment ACTIONS_ID_TOKEN_REQUEST_TOKEN
  --provenance-output ABSOLUTE_PATH

python3 publisher.py validate-registration
  --repository-root ABSOLUTE_PATH
  --provenance ABSOLUTE_PATH
  --published ABSOLUTE_PATH
  --anonymous-docker-config ABSOLUTE_PATH
```

Arguments are positional only where shown and otherwise reject; options cannot repeat except the
four `--protected-environment` pairs, whose names and order must be exact. `validate-source`
produces only `git 2.45 compatibility source validation: PASS` plus LF. `verify-candidate` requires
the provenance target not to exist, reads each named nonempty environment value only for scanning,
also reads every current environment value whose name matches the locked suffix rule, generates its
own random canary, and creates mode-`0600` canonical provenance by same-directory temporary file
plus atomic replacement only after every check passes. Names or values are never emitted. Failure
removes only its owned temporary file and leaves the target absent. `validate-registration`
validates both
registered files before network access, derives the exact run/attempt from them, verifies the
public GitHub Actions API reports that attempt with the matching repository, source commit,
`workflow_dispatch` event, workflow path, and final `success` conclusion, then performs the public
digest checks; it emits only
`git 2.45 compatibility registration validation: PASS` plus LF.

The four implementation-slice acceptance commands are respectively:

```text
.github/images/git-2.45-compat/test-image-source
.github/images/git-2.45-compat/test-oci-tools
.github/images/git-2.45-compat/test-publisher-tools
.github/images/git-2.45-compat/test-publisher-workflow
```

Each accepts no arguments, rejects semantic environment overrides, runs repository bytes from its
own resolved Git worktree, removes only validated temporary owners, and emits one same-named
`PASS` line. The first may build an unpushed local image; the second uses synthetic OCI/archive
fixtures and an unpushed OCI archive; the third adds a fake registry; the fourth never logs in or
pushes.

## 8. Closure matrix

| Path | Owner | Intended implementation | Exact regression or evidence |
| --- | --- | --- | --- |
| Source-lock format | `contract.py` | exact schema/order/types/constants and canonical re-encode | `SourceLockTests.test_golden` and `test_malformed_matrix` cover missing, reordered, unknown, wrong-type, NUL-at-every-position, CRLF, missing/extra LF, and noncanonical number/string cases |
| Helper-tree identity | `contract.py` | fixed-width framing and raw-byte hash | `HelperTreeTests.test_golden` and `test_rejection_matrix` cover both golden directions plus path/mode/order/prefix negatives |
| Git/Rust/LLVM acquisition | `Dockerfile` and `test-image-source` | hash complete input before execute/extract | `ImageSourceTests.test_acquisition_hash_precedes_use` changes each downloaded byte and requires failure before the relevant execution/extraction marker |
| Base/builder selection | `publisher.py`, `oci_inspector.py`, and workflow | locked manifest plus amd64 child for Ubuntu; locked manifest, child, config/image ID, and reported version for BuildKit | `PublisherWorkflowTests.test_locked_base_and_builder_matrix` rejects wrong parent, child, config, platform, version, and mutable-tag-only inputs |
| Publisher trust inputs | `publisher.py` and workflow | pinned action commits, byte-locked Buildx asset, BuildKit version/manifest/child; record mutable runner/Engine | `PublisherWorkflowTests.test_trust_input_matrix` rejects changed Buildx bytes before executable mode or side effects and audits every remaining producer |
| Candidate success | `publisher.py` | unique tag only as locator; returned digest drives all validation | `PublisherIntegrationTests.test_candidate_success_fixture` completes authenticated/public digest checks and canonical provenance against the fake registry |
| Candidate-tag race | `publisher.py` | never trust or consume tag after Buildx returns digest | `PublisherIntegrationTests.test_candidate_tag_replacement` changes the tag between every phase while digest-addressed validation remains bound |
| Default-private package | `publisher.py`, workflow, and package owner | fail with exact visibility state; manual irreversible public transition; new full run | `PublisherIntegrationTests.test_private_bootstrap` produces no provenance for the private fixture and accepts only a separate complete public run |
| OCI graph | `oci_inspector.py` | one OCI manifest/config, nonempty layers, exact fields/media/type/size/digest/config platform and fetched-byte matches | `OciInspectorTests.test_graph_matrix` covers the golden plus index, annotation, attestation, subject, artifact, wrong/extra field, media, size, digest, platform, empty-layer, and blob-substitution cases |
| Credential isolation | `oci_inspector.py` and workflow | isolated login config; no build transport; exact environment/history/final-filesystem/raw and decompressed-layer scans | `CredentialScannerTests.test_surface_matrix` and `test_archive_rejection_matrix` inject every protected surface and archive traversal/device/link case without printing values |
| Authenticated/public pull | `publisher.py` and `oci_inspector.py` | remove local reference; separate configs; digest only; hash remote manifest bytes | `PublisherIntegrationTests.test_authenticated_and_anonymous_pull_matrix` covers local-only, tag, private, credential fallback, substitution, and valid-public cases |
| Concurrent dispatch | workflow | one running, at most 100 FIFO-pending by start-wait time; dispatch order is not promised; overflow cancels before the job | `PublisherWorkflowTests.test_concurrency_contract` fixes the exact AST; the current [GitHub concurrency contract](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) is external serialization/overflow evidence |
| Build/push failure | `publisher.py`, `process_runner.py`, and workflow | checked-in timed Buildx CLI invocation; no successful provenance or registration | `PublisherWorkflowTests.test_build_failure_has_no_provenance` and `test_denied_registry_has_no_provenance` use synthetic command outcomes |
| Direct process timeout | `process_runner.py` | direct session TERM/KILL/reap/drain/close only | `ProcessRunnerTests.test_failure_matrix` covers direct hang, nonzero, invalid UTF-8, reader failure, and close/reap order |
| Escaped process | `process_runner.py` and ephemeral runner | outside helper promise; outer disposal | `ProcessRunnerTests.test_escaped_descendant_scope` proves the helper does not reuse a reaped session ID; workflow source audit assigns outer disposal and prevents provenance after cancellation |
| Builder pre-ID failure | workflow/runner | snapshot daemon IDs, do not delete by name, rely on runner disposal | `PublisherWorkflowTests.test_builder_pre_id_cleanup` covers partial create/cancellation and leaves the same-name fixture untouched |
| Builder post-ID cleanup | workflow | exact new returned and verified container ID only | `PublisherWorkflowTests.test_builder_post_id_cleanup_matrix` covers success, failure, cancellation, and wrong-ID/name fixtures |
| Test-container cleanup | workflow | exact returned IDs matching both run labels | `PublisherWorkflowTests.test_container_cleanup_labels` leaves wrong/missing-label resources and removes exact owned IDs |
| Diagnostic bounds | `process_runner.py` | 65,536 bytes per stream while continuing drains | `ProcessRunnerTests.test_simultaneous_two_pipe_overflow` rejects without deadlock and retains exactly the bound |
| Provenance formation | `contract.py` and `publisher.py` | canonical schema, complete current identities, and atomic output | `ProvenanceTests.test_canonical_round_trip`, `test_identity_mismatch_matrix`, and `test_atomic_failure` |
| Registered provenance | `contract.py` and registration slice | download exact successful-run artifact, validate canonical schema/current identities, commit byte-identically | `RegistrationTests.test_artifact_byte_identity` and `test_provenance_identity_matrix` cover source, action, workflow, OCI, inventory, result, and conclusion mismatches |
| Registered-record formation | `contract.py` and registration slice | derive semantic fields from registered provenance, regenerate canonical bytes, bind its hash | `RegistrationTests.test_published_round_trip` independently regenerates and compares bytes |
| Registered-record malformed input | `contract.py` | validate provenance and record before registry access | `RegistrationTests.test_malformed_matrix` covers NUL, encoding, field/order/type, digest, URL, cross-file mismatch, and final LF |
| Registration reachability | `publisher.py` and registration PR | successful-run conclusion, public digest inspect/pull, provenance artifact/hash, and source ancestry verification | `RegistrationTests.test_reachability_matrix` rejects failed-cleanup, unrelated/stale source, expired/mismatched artifact, and private digest; registration records the real run |
| Retention | package/project owner | digest consumers only; no automated deletion | `PublisherWorkflowTests.test_no_delete_or_tag_consumer` plus later topology digest resolution |
| Caller options and cache | workflow and `contract.py` | no dispatch inputs or semantic environment overrides; cache import/export is forbidden | `PublisherWorkflowTests.test_option_and_cache_boundary` rejects inputs, option-bearing expressions, build arguments, secrets, extra contexts/outputs, or cache settings |
| Detail levels and runtime reflection | `contract.py` | no detail discriminator or reflected runtime field exists; every observation has a named producer | `ProvenanceTests.test_unknown_and_missing_fields` plus `PublisherWorkflowTests.test_producer_map` |
| Performance measurement | N/A | no optimization or performance claim | N/A: compatibility acceptance only; downstream evaluations own time-to-passing-patch evidence |
| Align ownership/ABI | N/A | no Align value, API, ownership, monomorphization, or ABI change | N/A: later topology builds the pinned compiler as real client |

## 9. Pull request boundaries and acceptance

### Design pull request

This file and `HANDOFF.md` are the only changed paths. `git diff --check` passes. One comprehensive
independent adversarial review covers trust, publication, default-private bootstrap, OCI identity,
credentials, execution, cleanup, records, and downstream scope. Findings receive explicit
dispositions under the repository review policy.

### Image-source pull request

Implementation adds only:

- `.github/images/git-2.45-compat/Dockerfile`;
- `.github/images/git-2.45-compat/sources.json`;
- `runtime-self-test`, the source-lock/helper subset of `contract.py`, `test-image-source`, and
  their fixtures under that directory; and
- narrowly required contributor documentation and handoff updates.

It performs a local unpushed build and complete image-local checks. It has no registry login,
publisher, provenance writer, registration validator, or workflow.

### OCI-validation tooling pull request

Implementation adds `process_runner.py`, `oci_inspector.py`, `test-oci-tools`, and their fixtures.
Tests exercise synthetic manifests, blobs, layers, process faults, and an unpushed OCI archive.
This slice has no registry client, publisher, provenance writer, Actions workflow, login, or push
path.

### Publisher and record-validation tooling pull request

Implementation adds `publisher.py`, the remaining canonical provenance/registration functions in
`contract.py`, `test-publisher-tools`, and fake-registry fixtures. It consumes the already-merged
OCI/process modules but has no Actions workflow or real GHCR login/push path and cannot publish.

### Non-publishing workflow pull request

Implementation adds `.github/workflows/publish-git-245-compat.yml`,
`test-publisher-workflow`, and narrowly required documentation/handoff updates. The workflow is
inert on pull requests, and its test command rejects any PR/push trigger, caller input, mutable
action ref, tag consumer, cache, secret build transport, or delete operation. One comprehensive
review covers the final workflow-to-tool boundary. After merge, a repository owner manually
dispatches the exact merged `main`.

Each implementation slice runs its named acceptance command plus `make check`, receives its own
full-diff review, and merges before the next slice starts. No pull-request execution authenticates
to GHCR or creates registry content.

### Publication and visibility transition

A successful public run is external immutable evidence, not a branch edit. If first creation reaches
the visibility failure, `sanohiro` must explicitly make the package public before a new dispatch.
The assistant must not infer authority to change package visibility. A failed/private run, candidate
tag, or authenticated-only result cannot advance the handoff.

### Digest-registration pull request

Registration changes only `provenance.json`, `published.json`, this document's status paragraph,
and `HANDOFF.md`. Its description records the successful run, credential-free digest pull, OCI
manifest/config, post-pull checks, package inventory, provenance hash, credential scan, and source
ancestry. It verifies byte identity with the downloaded artifact, current source-lock, Dockerfile,
helper-tree, workflow, and action identities against the provenance, and GHCR by digest before
merge. The provenance `source_commit` must be a raw commit and an ancestor of both the exact
registration base tip and head. Merge, squash, or rebase integration is permitted only while that
already-merged source commit remains an ancestor of the exact resulting `main`; this ancestry is
rechecked after integration.

The image prerequisite is complete only after registration merges and a fresh checkout validates
both registered files and pulls the digest without credentials. The next branch then updates
`docs/specs/check-gate-topology.md` to name that exact registered record.
