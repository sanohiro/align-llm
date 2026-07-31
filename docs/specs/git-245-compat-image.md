# Git 2.45 compatibility image

## 1. Purpose and delivery order

This enabling artifact supplies the immutable minimum-Git environment required by the common
fresh-compiler topology and every later pin-changing Align adoption. The production adoption gate
requires `GIT_NO_LAZY_FETCH`, introduced in Git 2.45, and must be exercised with `/usr/bin/git`
reporting exactly `git version 2.45.0`. A synthetic version string or a newer hosted runner is not
minimum-version evidence.

No suitable public image with that exact binary and the complete align-llm hosted build toolchain
is currently registered. The image is therefore delivered before the fresh-compiler topology in
three independently reviewable slices:

1. this design merges;
2. an image-source and publisher implementation merges, then a manually dispatched publisher run
   from that exact `main` commit builds, tests, and pushes one immutable image; and
3. a digest-registration pull request records the successful image and provenance in
   `.github/images/git-2.45-compat/published.json`.

`docs/specs/check-gate-topology.md` may name the image only after step 3 merges. No consumer may use
a tag, an unregistered digest, a pull-request image, or an image produced from an unmerged commit.
The image does not change `.align-revision`, product behavior, evaluation semantics, or the current
compiler pin.

## 2. Public-contract ledger

| Surface | Exact contract |
| --- | --- |
| Image repository | `ghcr.io/sanohiro/align-llm/git-2.45-compat`. Consumers use only the lowercase `sha256:<64 lowercase hex>` manifest-list digest recorded in `published.json`; tags are discovery metadata and never an input to a gate. |
| Platform | Exactly `linux/amd64`. The manifest list contains exactly one runnable platform descriptor with `os=linux`, `architecture=amd64`, and no variant. Attestation and SBOM descriptors may also be attached but are not runnable platforms. |
| Runtime Git | `/usr/bin/git --version` emits exactly `git version 2.45.0` plus LF and exits zero. `/usr/bin/git` is the selected `git` under `PATH=/opt/cargo/bin:/usr/lib/llvm-22/bin:/usr/local/bin:/usr/bin:/bin`; no second Git precedes it. |
| Hosted toolchain | Ubuntu 24.04 amd64 userland; `/usr/bin/python3` is Python 3.10 or newer; `/usr/bin/make` is GNU Make 4.3 or newer; Cargo and Rustc under `/opt/rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu/bin/` are exactly 1.96.0; `/usr/lib/llvm-22/bin/llvm-config --version` reports major 22; Clang 22 and the native libraries required by the pinned Align workspace are installed. `RUSTUP_HOME=/opt/rustup` and `CARGO_HOME=/opt/cargo`; no toolchain state is installed under `/root`. Exact package inventory belongs to the image SBOM. |
| Source lock | `.github/images/git-2.45-compat/sources.json`, schema version 1, is canonical UTF-8 JSON with final LF. It records the Ubuntu manifest-list digest `sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90`, its expected amd64 child digest `sha256:52df9b1ee71626e0088f7d400d5c6b5f7bb916f8f0c82b474289a4ece6cf3faf`, the Git source URL `https://www.kernel.org/pub/software/scm/git/git-2.45.0.tar.xz`, Git version `2.45.0`, source SHA-256 `0aac200bd06476e7df1ff026eb123c6827bc10fe69d2823b4bf2ebebe5953429`, Rust version `1.96.0`, LLVM major `22`, and the exact required smoke commands. |
| Image source | `.github/images/git-2.45-compat/Dockerfile` is the only Dockerfile. Its build context is exactly `.github/images/git-2.45-compat/`; it copies only `sources.json` and checked-in helper source from that directory. It uses the locked Ubuntu digest, verifies the downloaded Git archive before extraction, installs Git under `/usr`, and removes the extracted source and downloaded archive in the same build stage. |
| Publisher | `.github/workflows/publish-git-245-compat.yml` is `workflow_dispatch` only and declares no inputs. It rejects a ref other than `refs/heads/main`, checks out the exact `GITHUB_SHA`, requires the source and workflow paths to be tracked and the checkout clean, builds and pushes one uniquely tagged `linux/amd64` candidate with BuildKit SBOM and provenance, resolves its immutable digest, runs the complete test bundle from a fresh digest-only pull, proves credential-free access, promotes that same manifest digest to the source-commit tag, and uploads the provenance record. |
| Publication permissions | The publisher has `contents: read`, `packages: write`, and `attestations: write`; every other permission is `none`. `GITHUB_TOKEN` is supplied only to an isolated temporary Docker client configuration for GHCR login and is never a build argument, build secret, layer input, image environment value, log value, or provenance field. |
| Publication concurrency | One fixed repository-wide concurrency group, `publish-git-245-compat`, with `cancel-in-progress: false`. Concurrent dispatches serialize. Before building, a run queries the registry for the source-commit tag; if it already resolves, the run verifies that existing digest and exits without pushing another image. Each new candidate tag is `candidate-<decimal run_id>-<decimal run_attempt>` and is never a consumer input. |
| Source-commit tag | `source-<40 lowercase hex GITHUB_SHA>`. It is an audit locator only. The workflow fails if the tag appears during the run with a digest different from the image it built. A tag may never appear in `published.json` or a consumer command. |
| Provenance record | The publisher writes `git-245-compat-provenance.json`, schema version 1, as canonical UTF-8 JSON plus LF. Fields, in order, are `schema_version`, `source_commit`, `source_lock_sha256`, `dockerfile_sha256`, `helper_tree_sha256`, `workflow_sha256`, `base_manifest_digest`, `base_platform_digest`, `git_source_sha256`, `rust_version`, `llvm_major`, `platform`, `publisher_tools`, `image_repository`, `image_digest`, `platform_digest`, `config_digest`, `sbom_digest`, `provenance_digest`, `post_pull_checks`, and `run_url`. Every digest is full lowercase SHA-256. `helper_tree_sha256` covers canonical path, mode, byte count, bytes, and final record terminator for every other tracked build-context path in bytewise path order. `publisher_tools` records exact Docker Engine and Buildx version stdout. The check array preserves the source-lock order and contains command, exact stdout SHA-256, and exit status zero. |
| Registered record | `.github/images/git-2.45-compat/published.json`, schema version 1, is canonical UTF-8 JSON plus LF. It contains, in order, `schema_version`, `source_commit`, `image_repository`, `image_digest`, `platform_digest`, `config_digest`, `sbom_digest`, `provenance_digest`, and `publication_run_url`, copied byte-for-byte from one successful provenance record. This is the only repository source of truth for consumers. |
| Public availability | Before digest registration, a clean client with no Docker or GHCR credentials must pull the manifest-list digest and platform image. Failure keeps the image unregistered. Package visibility is an explicit publisher acceptance condition, not an implicit consumer credential. |
| Retention | Registered manifest, platform, config, SBOM, and provenance digests are immutable required project inputs and must not be deleted. Unregistered failed or superseded manifests are registry-owner cleanup work and are never selected automatically. This design does not authorize deleting a registered package version. |

### 2.1 Ownership, lifetime, and allocation

The publisher owns its temporary Docker configuration, downloaded build context, local builder
state, test containers, captured bounded diagnostics, and provenance file until the job finishes.
The GitHub-hosted runner is ephemeral; no local layer or cache is a persisted project artifact.
The registry owns pushed blobs and manifests. The repository owns only reviewed source and the
registered JSON record.

The workflow creates its Docker configuration with mode `0700` in one runner-owned temporary
directory and passes that explicit path through `DOCKER_CONFIG`. Cleanup logs out, removes only
that validated directory through the runner's temporary owner, and does not act on a caller path.
The workflow never recursively deletes the workspace, runner root, home directory, or registry
content. A failed cleanup makes the run fail but does not replace an earlier build, test, push, or
digest error.

Build and test output is streamed. Each command additionally retains at most 65,536 bytes from each
of stdout and stderr for the provenance/check diagnostic; overflow is a failure rather than a
truncated success. The provenance record contains only SHA-256 values of successful exact stdout,
not arbitrary command output.

The publisher runs on `ubuntu-24.04` with a 90-minute job deadline. It creates exactly one Buildx
builder named `git245-<run_id>-<run_attempt>` and labels every test container with those two
validated decimal identifiers. Source validation has a five-minute monotonic deadline, the
build-and-push has 45 minutes, each registry inspect/pull or test command has ten minutes, and
cleanup has five minutes. The checked-in runner starts each direct CLI in a new session, drains
stdout and stderr concurrently, and on a phase deadline sends `SIGTERM` to the owned session,
waits at most five seconds, sends `SIGKILL`, reaps the direct process, and finishes both readers.
It then asks Docker to cancel and remove only the exact named builder and exact labeled test
containers. A Docker resource that cannot be proven to carry both labels is never removed.

The Docker daemon and BuildKit workers are runner services rather than descendants. Their durable
ownership boundary is the unique builder name, labels, candidate tag, and ephemeral hosted runner.
The cleanup step uses `if: always()`; GitHub runner disposal is the final outer cleanup after abrupt
job cancellation or runner loss. Such an abrupt loss may leave an immutable unregistered candidate
in GHCR, but can neither create `published.json` nor make a tag-based consumer. `SIGKILL` of the
hosted runner is otherwise N/A to in-process cleanup because the runner service owns machine
disposal.

### 2.2 Canonical JSON shapes

`sources.json` has these keys in this exact order:

```text
schema_version                  unsigned JSON integer, exactly 1
base_image                      "docker.io/library/ubuntu"
base_manifest_digest           "sha256:" plus 64 lowercase hex
base_amd64_digest              "sha256:" plus 64 lowercase hex
git_source_url                 exact HTTPS URL from the ledger
git_version                    "2.45.0"
git_source_sha256              64 lowercase hex
rust_version                   "1.96.0"
llvm_major                     unsigned JSON integer, exactly 22
platform                       "linux/amd64"
checks                         nonempty array of exact command arrays
```

Each `checks` element is a nonempty array of nonempty UTF-8 strings and is executed directly as an
argument vector. Duplicate commands, shell metacharacter interpretation, an empty argument, an
unknown key, a JSON numeric spelling other than the canonical decimal, or a noncanonical string
escape rejects the source lock. The checked-in validator re-encodes the parsed semantic object with
two-space indentation and `ensure_ascii=false`, appends one LF, and requires exact byte equality.
The Dockerfile consumes only values emitted by that validator.

`git-245-compat-provenance.json` and `published.json` use the field order and scalar types in the
ledger. Their encodings use the same two-space-indented UTF-8 plus final-LF rule.
`publisher_tools` has exact key order `docker`, `buildx`; each value is one UTF-8 line without its
terminating LF. `post_pull_checks` is an array of records with exact key order `command`,
`stdout_sha256`, `status`; `command` is the source-lock argument array, `stdout_sha256` is 64
lowercase hex, and `status` is the JSON integer zero. URLs are HTTPS GitHub Actions run URLs without
credentials or query strings. No field is optional, nullable, or extensible under schema version 1.

### 2.3 Trust and network boundary

The reviewed source lock, Dockerfile, publisher workflow, Git archive digest, Ubuntu base digests,
and exact publisher commit are trust inputs. The build requires network access only to pull the
locked base, Ubuntu and LLVM package repositories, the locked Git source URL, Rust distribution
servers for 1.96.0, and GHCR for push/pull. Package repositories are not claimed to make the build
reproducible. Their realized files, versions, and hashes are captured in the SBOM and immutable
output digest; a later rebuild is a new candidate requiring the full publish and registration flow.

The image build executes no file from the Git archive before its complete SHA-256 matches. Package
maintainer scripts execute inside the isolated image build and are therefore explicit base/package
trust, not checkout trust. The image contains no repository checkout, model data, user home,
credential, Docker configuration, Actions token, or registry authorization material.

### 2.4 Deterministic validation and error order

The publisher uses this fail-fast order:

1. event is `workflow_dispatch`, ref is `refs/heads/main`, and `GITHUB_SHA` is one full commit;
2. checkout HEAD equals that SHA; required source paths are tracked; worktree and index are clean;
3. `sources.json` has exact schema, field order, values, encoding, and final LF;
4. source-lock, Dockerfile, helper-tree, workflow, and publisher-tool identities are recorded;
5. the source-commit tag is absent, or already resolves to one digest that passes every remote
   record and post-pull test, in which case publication is idempotently complete;
6. the unique candidate tag is absent;
7. the BuildKit build-and-push succeeds without passing a credential into the build and returns one
   manifest-list digest;
8. image config, layer history, and SBOM contain no token, Docker configuration, credential path,
   checkout path, or disallowed environment key;
9. remote manifest has exactly the platform and attached non-runnable attestations permitted by
    the ledger, and all recorded digests resolve;
10. a fresh credential-free Docker configuration pulls only by manifest-list digest;
11. every post-pull command succeeds with exact required output;
12. promotion creates the source-commit tag for that same manifest-list digest without rebuilding;
13. the source-commit tag resolves to that digest;
14. canonical provenance generation succeeds; and
15. temporary logout and local cleanup succeed.

When a job cancellation or deadline coincides with another command result, cancellation wins,
followed by deadline, command launch/read/wait failure, nonzero or mismatching result, registry
postcondition, provenance serialization, and cleanup. Cleanup is always attempted. An earlier
failure remains primary and the bounded cleanup error is appended.

Embedded NUL, CR, missing or additional LF, uppercase digest text, unexpected fields, and invalid
UTF-8 in either JSON source are rejected before build. OCI strings are UTF-8. No public input is
passed through shell command substitution; digest and path values travel as workflow outputs or
argument-vector elements after validation.

## 3. Build and runtime checks

The checked-in test owner runs these ordered commands only after the fresh credential-free
digest-only pull; source validation and BuildKit own all pre-push checks:

```text
/usr/bin/git --version
/usr/bin/python3 --version
/usr/bin/make --version
/opt/rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu/bin/cargo --version
/opt/rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu/bin/rustc --version
/usr/lib/llvm-22/bin/llvm-config --version
/usr/bin/clang-22 --version
```

The Git output is byte-exact. Python parses to at least 3.10. GNU Make parses to at least 4.3.
Cargo and Rustc parse to exactly 1.96.0. LLVM and Clang parse to major 22. The helper also:

- runs the production Git-version parser planned by the common topology against the real
  `/usr/bin/git`, requiring its exact accepted record;
- executes a tiny offline locked Rust build using the installed toolchain and an empty target;
- compiles and links a tiny C program with Clang 22;
- verifies the default `PATH` selects `/usr/bin/git`;
- scans image configuration and layer history for the complete forbidden credential-key list; and
- proves the container has no Docker socket or inherited GHCR credential.

The tiny projects are checked-in build-context fixtures with exact expected stdout. They do not
clone a repository or contact a package registry. The later common-topology implementation adds its
full self-test and pinned Align build as consumers; this image slice proves only that the minimum
environment can host those commands.

## 4. Closure matrix

| Path | Owner | Intended implementation | Exact regression or evidence |
| --- | --- | --- | --- |
| Source-lock formation | source-lock validator | parse complete bytes, enforce schema/order/types/exact constants | valid golden plus missing, reordered, unknown, wrong-type, uppercase-digest, NUL-at-every-position, CRLF, missing-LF, and extra-LF cases |
| Git archive acquisition | Dockerfile | download fixed URL to a build-only path, hash before extract | wrong digest build argument is unavailable; a fixture proxy serving one changed byte fails before tar executes |
| Base selection | Dockerfile and publisher | `FROM` locked manifest digest with `linux/amd64`; inspect child digest before build acceptance | manifest and platform IDs equal the source lock; wrong architecture and multi-platform additions reject |
| Toolchain construction | Dockerfile | install exact Git/Rust/LLVM contract and required libraries | complete ordered post-pull tool/runtime bundle |
| Image success | publisher | candidate build/push, scan, inspect, fresh public digest pull, test, source-tag promotion | successful provenance record containing every exact post-pull stdout digest |
| Build failure | publisher child runner | propagate nonzero, do not promote or write accepted provenance | injected failing final build stage leaves source tag and provenance absent; BuildKit may leave only its unique unregistered candidate blobs |
| Post-pull test failure | test owner | reject before source-tag promotion | fake Git version and fake Rust version candidate cases leave source tag and provenance absent |
| Credential isolation | workflow and image scanner | isolated `DOCKER_CONFIG`; login authorizes only registry transport and is absent from BuildKit arguments/secrets | canary token is absent from config, history, SBOM, saved filesystem, logs, and provenance |
| Push failure | publisher | preserve build/test result only as failed job; no registration | denied-package fixture returns bounded registry failure and no provenance |
| Manifest mismatch | publisher inspector | compare remote manifest/platform/config/attestation graph to locally built graph | extra runnable platform, wrong platform digest, tag race, and missing SBOM/provenance reject |
| Credential-free pull | publisher | new empty Docker config, digest-only reference, no prior local image | private-package fixture rejects; successful public pull has exact manifest digest |
| Post-pull mismatch | test owner | source-lock command vectors and exact output rules | substituted remote image fails before provenance acceptance |
| Idempotent redispatch | publisher | resolve existing source tag and verify the full registered candidate without push | second dispatch emits the same digest and no push marker |
| Concurrent dispatch | Actions concurrency plus tag postcheck | serialize; never overwrite a differing source tag | two queued synthetic publishers result in one push or the same verified digest |
| Cancellation before promotion | publisher owner | terminate owned build/test containers, logout, clean local temp | cancellation at checkout, build, scan, or post-pull test leaves no source tag or accepted provenance; a unique candidate may remain unregistered |
| Cancellation during/after push | publisher owner | finish cleanup; remote immutable digest may remain unregistered | cancellation after blob or manifest upload never writes `published.json`; rerun verifies or rejects the existing source tag |
| Cleanup success | publisher | remove only validated temporary Docker config and test containers | success and each failure phase leave no credential config or live container |
| Cleanup failure | publisher | retain primary error, append cleanup error, fail | injected logout and container-removal failures preserve earlier failure and never claim provenance success |
| Diagnostic bounds | publisher child runner | concurrent pipe drain, 65,536-byte per-stream retention limit | simultaneous stdout/stderr overflow rejects without deadlock |
| Publisher process success | checked-in child runner | new session, concurrent bounded drains, direct-child reap, exact builder/container ownership | successful build, inspect, pull, and test phases leave no live direct child, builder, or test container |
| Publisher process timeout | checked-in child runner plus Docker cleanup | TERM, five-second grace, KILL, reap, reader completion, exact Docker resource cleanup | separately hanging build CLI, inspect CLI, and test container reject within their phase bounds and leave no exact owned resource |
| PID/session reuse | checked-in child runner | retain direct process identity and signal only the still-owned session while the direct child is live; Docker cleanup selects immutable resource IDs returned for the exact labels | exited-child PID-reuse fixture is never signaled; a same-name unlabeled and same-label wrong-name Docker resource is never removed |
| Registered-record formation | digest-registration slice | copy exact successful provenance fields into canonical schema | independent generator and validator produce byte-identical `published.json` |
| Registered-record malformed input | registered-record validator | validate before any registry access | NUL, encoding, field, order, digest, URL, platform, and final-LF negative corpus |
| Registry reachability | registration pull request | unauthenticated digest-only inspect/pull and complete post-pull checks | exact commands and successful publication run URL recorded in PR |
| Registered digest retention | project/package owner | no automated delete path; consumers use digest only | repository search rejects tag consumers; package digest resolves during topology CI |
| Argument ownership and Move/Drop | N/A | no Align API or ownership value is added | N/A: process, file, and registry ownership is specified above |
| Scalar widths and wire tags | OCI and JSON schemas above | SHA-256 digests and JSON schema version 1 | OCI inspector plus byte-exact JSON golden tests |
| Monomorphization/interface/runtime provenance | N/A | image does not change Align code or ABI | N/A: the later topology builds the pinned compiler as the real client |

## 5. Pull request boundaries and acceptance

### Design pull request

This file and `HANDOFF.md` are the only changed paths. `git diff --check` passes. One comprehensive
independent adversarial review covers the ledger, image trust boundary, credentials, publication,
registration, cleanup, and downstream topology prerequisite. Findings receive dispositions under
the repository review policy.

### Image-source and publisher pull request

The implementation adds only:

- `.github/images/git-2.45-compat/Dockerfile`;
- `.github/images/git-2.45-compat/sources.json`;
- checked-in image test and JSON validation helpers under that directory;
- `.github/workflows/publish-git-245-compat.yml`;
- narrowly required contributor documentation and handoff updates.

It does not publish from the pull request. Local BuildKit verification and the pull request's
non-publishing negative workflow tests pass. One comprehensive review covers all implementation
and workflow paths. After merge, a repository owner manually dispatches the workflow on the exact
merged `main` SHA.

### Digest-registration pull request

The registration changes only `published.json`, this document's status paragraph, and
`HANDOFF.md`. Its description records the exact publication run, unauthenticated digest-only pull,
post-pull checks, manifest graph, SBOM/provenance digests, and credential scan. It verifies
the publisher source commit is an ancestor of its exact base and that the source lock, Dockerfile,
and workflow bytes equal the provenance hashes. A comprehensive review checks the external record
against GHCR before merge.

The image prerequisite is complete only after the registration pull request merges and a fresh
checkout validates and pulls the registered digest without credentials. The next branch then
updates `docs/specs/check-gate-topology.md` to name that exact record and image.
