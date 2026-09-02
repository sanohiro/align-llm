# Development preflight

Status: implementation plan of record.

This capability makes local verification and GitHub Actions select the same checks. It addresses
the repeated push-to-diagnose loop observed in FRESH-WORKER and Request 6 without changing product
behavior or the fresh-worker trust contract. The local toolchain extension makes the pinned Align
revision the default compiler source instead of an ambient sibling checkout.

## Public contract

| Surface | Contract |
| --- | --- |
| `python3 scripts/align-toolchain {path KIND | ensure KIND | verify}`, where `KIND` is `compiler` or `source` | Read `.align-revision` as exactly one lowercase 40-hex SHA followed by LF. Store developer-owned checkouts below `${XDG_CACHE_HOME}/align-llm/align/dev-v1` when `XDG_CACHE_HOME` is set, otherwise `${HOME}/.cache/align-llm/align/dev-v1`; `ALIGN_TOOLCHAIN_ROOT` replaces the base. Explicit toolchain paths and commands must contain no whitespace. `ALIGN_TOOLCHAIN_REPOSITORY` replaces the default `https://github.com/sanohiro/align.git`, and `CARGO` replaces the build command. `path` is side-effect free. `ensure` serializes cooperative same-revision callers, fetches and detaches the exact revision into a temporary directory, runs the locked release build with the developer's ordinary Cargo/Rust environment, validates the clean checkout and required outputs, and moves it to the revision path. A warm call validates and reuses that checkout without fetch or build. `verify` requires the exact clean HEAD plus usable `alignc` and `libalign_runtime.a`. Failure attempts removal of only invocation-owned temporary state; cleanup failure is nonzero. An existing invalid checkout fails with a diagnostic and is not repaired automatically. The cache is trusted, mutable, single-user development state, not an artifact, security, provenance, or hostile-concurrency boundary. Mutation by non-cooperating processes and reproducibility across different developer build environments are explicitly unsupported; remove the named revision directory to rebuild after intentionally changing those inputs. No Git-tracked generated artifact is created. |
| `scripts/alignc` and Make compiler selection | `ALIGN_LLM_FRESH_COMPILER=1` continues to require the authenticated `/tools/fresh-alignc` path. Otherwise a non-empty `ALIGNC` is the highest-priority direct compiler override. A non-empty explicit `ALIGN_REPO` selects that checkout's release compiler, then debug compiler, for active cross-repository development. Empty Make `ALIGNC` is normalized back to the wrapper. With neither override, the wrapper runs `align-toolchain ensure compiler`; it never searches `../align` or ambient `PATH`. `make check`, `run`, `build`, `fmt`, baseline recording, and every recursive functional target use that selection. The existing explicit source-build targets retain their hosted/fresh and cross-repository contract. |
| `python3 scripts/classify-verification --base REF --head REF` | Resolve both refs as commits, compute their merge base, inspect the no-renames name-status diff, and print a stable JSON object containing `scope`, `base`, `head`, `docs_only`, `hosted`, `fresh_focused`, and `fresh_installed`. `--github-output PATH` writes the same scalar fields as GitHub output rows. An added or modified `.align-revision` plus only added or modified Markdown selects `scope=pin`, keeps `hosted=true`, and leaves both fresh fields false. Ordinary application paths under `src/` and platform-independent evaluation paths under `eval/` select `hosted`: the pinned compiler plus hosted functional graph own their behavior. The Linux sandbox runner `eval/runners/run-coding-task.py` remains an exact `fresh-image` exception because it owns subreaper, process-scanning, and user-namespace behavior. Fresh-image construction, workflow, classifier, Make topology, worker/control, and qualification-owner paths also select `fresh-image`; a deleted/renamed pin fails closed to fresh-image. `--all --head REF` selects every executable gate when no trustworthy base exists. Invalid refs, malformed Git output, deletions, unknown statuses, and unknown non-Markdown paths fail closed to executable verification. |
| `python3 scripts/pre-pr [--base REF] [--align-repo PATH] --owner-test LABEL -- COMMAND ...` | Require a named non-`main` branch, a clean worktree, a non-empty merge-base diff, and one owner command for executable changes. Construct and validate the complete plan without mutation and run the owner first. Pin and fresh-image scopes leave the broad common functional graph to required hosted CI instead of repeating it locally. Other executable scopes retain that graph because it is their direct owner. In fresh-image scope, owner, managed-toolchain verification, focused qualification, and the installed owner run in order and must finish below 900 seconds. Top-level HUP, INT, QUIT, or TERM is forwarded by the output-summary owner to the active command process group, escalated to KILL after five seconds, reaped, and preserved. The installed image owner catches its first such signal and unwinds the existing Docker/profile finalizer within that grace. No failure or signal writes a stamp. Missing or failing owners perform no fetch/build. Documentation-only changes run only static owners. Explicit `--align-repo` retains the existing exact-checkout source-build override. Final clean/head checking and the versioned stamp are unchanged. `--plan` prints every ordered phase, predicts its path without side effects, and writes no stamp. |
| `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker [--complete-aggregate] [--align-repo PATH] [--prepared-image IMAGE --image-signing-seed PATH --run-signing-seed PATH]` | Verify the qualification inventory, skip the already-owned focused commands, and run only the installed profile. `--installed-profile` retains the focused-plus-installed capability gate. Neither installed mode reruns the complete common graph by default. `--complete-aggregate` requires either installed mode, is reserved for an aggregate-owner change or explicit audit, and forwards exactly once to the image owner. `--require-docker` turns an unavailable Docker daemon into failure instead of a skip. `--align-repo` forwards an explicit full pinned checkout to the image owner. The three prepared-image arguments are all-or-none, require an installed-profile mode, and are forwarded unchanged. The installed owner receives one private mode-0700 temporary `DOCKER_CONFIG`, never a caller or repository-local Docker configuration; the launcher removes it after success or failure. Every invoked owner emits one start and one terminal timing record. |
| `python3 scripts/prepare-fresh-image-build --directory PATH --github-output PATH` | Create a new current-user-owned mode-0700 directory containing two independent 32-byte current-user-owned mode-0400 signing seeds and a schema-1 ownership marker bound to the exact directory and generated image tag. Refuse an existing target, symlink, non-ASCII/non-line-safe or relative material path, or unavailable output file. Validate and ASCII-encode the complete output record before creating the directory, then append `image`, `image_public_key_hex`, `run_public_key_hex`, and `material_directory` in one write; never print either seed or expose partial rows after an encoding rejection. `--cleanup --directory PATH` accepts only the exact marked directory and known regular files, validates directory, inventory, image seed, run seed, then the exact integer marker version and remaining schema, removes the seeds before the marker, and finally removes the directory. Preparation cleans up its own partial output on every error. |
| `python3 scripts/materialize-fresh-tree SOURCE TARGET [SOURCE TARGET ...]` | Materialize one or more image-owned runtime trees at new targets without retaining symlinks. Require complete source/target pairs; canonicalize every source and target through existing symlink parents; reject every existing target, canonical target-target overlap, and canonical source-target overlap before constructing any target; then process pairs in argument order. Traverse entries in bytewise name order, follow regular-file and directory symlinks, omit dangling child links and directory cycles, preserve resolved modes and bytes, and reject an unsupported resolved entry type or a source that produces no root. All resolved regular-file entries with the same source device and inode across the complete invocation share one target inode, including true hardlinks and file aliases reached through symlinks, repeated directory aliases, or different source roots; equal bytes from distinct source identities remain distinct. The helper exits zero only after every complete target exists; an argument error exits 2 and a traversal, copy, or hardlink failure exits nonzero so the Docker build discards the failed layer. |
| `ALIGN_APT_PACKAGES="..." scripts/ci-apt-llvm.sh {key | install [--uncached] | verify}` | Own the Ubuntu CI LLVM 22 and native-library archive cache. Every mode parses the one-line request once as a non-empty, duplicate-free vector of Debian binary package names matching `[a-z0-9][a-z0-9+.-]+`; options, versions, architecture qualifiers, globs, uppercase, one-character names, and multiline input are rejected. `key` requires `RUNNER_TEMP` and `ImageVersion`, then prints exactly `path` and `key` GitHub-output rows; `RUNNER_OS` defaults to `Linux` and `RUNNER_ARCH` to `X64`. The key contains the LLVM major, runner OS and architecture, manual cache generation, runner image version, and a digest of the bytewise-sorted package vector. Validation order is mode and arity, package vector, `RUNNER_TEMP`, then mode-specific `ImageVersion` or Debian-host support. `install` accepts a restored set only when `SHA256SUMS` is a regular non-symlink file containing exactly one strict checksum row for every regular non-symlink `.deb` basename and no duplicate, missing, extra, absolute, nested, or traversal name; it then verifies every checksum, installs the same exact files with `dpkg`, and requires every requested package, `llvm-config`, and `cc`. A missing set performs the authoritative apt install; an unusable restored set first repairs dpkg state and then performs the same authoritative install. `verify` repeats exact archive membership, checksum, package, `llvm-config`, and `cc` validation without mutation, apt, or cleanup so the workflow can prove the post-consumer candidate immediately before save. The apt path accepts exactly the pinned apt.llvm.org primary signing key and its bound subkeys, proves the selected candidate comes from apt.llvm.org, tries the versioned suite before the current suite, and uses `--no-remove` so every saved transaction remains replayable by `dpkg`. Every fixed global path rejects any pre-existing object, including a dangling symlink; an existing real `/etc/apt/keyrings` directory is borrowed, while an invocation-created directory is tracked separately. Cleanup removes invocation-owned config, source, keyring, keyring directory, and work directory before deciding archive retention. Only a successful cache miss whose other cleanup succeeded leaves its archives eligible for save; every other exit attempts archive removal, and any cleanup failure exits nonzero so the workflow cannot save the candidate. Invalid arguments, an invalid package vector, or a non-Debian install host exit 2; missing inputs, pre-existing target state, repository/key failures, corrupt unrecoverable state, incomplete installation, an invalid verify candidate, or an empty cache-miss resolve exit nonzero. |
| `python3 scripts/ci-align-bundle {key | create | verify} --directory PATH --align-revision SHA --image-version VERSION --runner-os OS --runner-arch ARCH --rust-version VERSION --llvm-major MAJOR [--align-repo PATH --llvm-library PATH]` | Own the trusted hosted compiler bundle. Every mode requires an absolute ASCII line-safe directory without `:`; a lowercase 40-hex Align revision; 1..64-byte image, OS, architecture, and Rust identities matching `[A-Za-z0-9][A-Za-z0-9._-]*`; and an LLVM major in decimal range 1..65535. Validation order is mode/arity and option ownership, scalar identities, directory, then mode-specific source or admitted-bundle state. `key` and `verify` reject the create-only arguments; `create` requires both. `key` prints exactly `path=PATH` and `key=hosted-align-bundle-g1-rev-SHA-image-LEN-VERSION-os-LEN-OS-arch-LEN-ARCH-rust-LEN-RUST-llvm-MAJOR` rows, where each decimal `LEN` is the following token's ASCII byte length. Its generation-scoped key contains every supplied identity, so the external Align commit is nominal source identity and the exact runner image binds ambient ABI dependencies. `create` additionally requires an exact clean Align checkout at the named revision, regular non-symlink release `alignc` and `libalign_runtime.a` inputs, and an explicit LLVM input that resolves to one regular file with basename `libLLVM.so.MAJOR.1`. It refuses an existing bundle path, validates every source before creating a private sibling staging directory, copies exactly `alignc`, `libalign_runtime.a`, and `libLLVM.so.MAJOR.1` without symlinks, applies modes 0755/0644/0644, writes mode-0644 canonical schema-1 `manifest.json`, verifies the staged bundle, and atomically renames it into place without replacement. Any failure attempts to remove only its staging directory and leaves no target; an unsuccessful cleanup is itself a nonzero failure and never removes caller-owned state. `verify` requires exactly those four regular non-symlink files and no others; a manifest of at most 16,384 bytes with canonical identity, byte size, mode, SHA-256, field set, field order, and file order must match. It then runs the checksum-admitted `alignc --version` under an exact bundle-only `LD_LIBRARY_PATH` and requires the dynamic loader to resolve `libLLVM.so.MAJOR.1` to the admitted bundle file. `create` prints exactly `created bundle: PATH (N bytes)` and `verify` prints exactly `verified bundle: PATH (N bytes)` on success; diagnostics are prefixed `ci-align-bundle:` on stderr. Invalid arguments or identities exit 2; source, filesystem, manifest, checksum, mode, loader, executable, or cleanup failure exits nonzero. No mode mutates a supplied source checkout or an admitted bundle. |
| `python3 scripts/run-fresh-image-profile-smoke [--complete-aggregate] [--prepared-image IMAGE --image-signing-seed PATH --run-signing-seed PATH]` | With none of the prepared-image arguments, generate per-run signing seeds and build the image locally as before. With all three, validate the generated tag and two private regular 32-byte seed files before Docker side effects and use the already loaded image without rebuilding it. The default runs attestation, lifecycle, trust mutation, runtime replacement, real compiler self-test, adoption boundaries, worker mode `build`, and cleanup; it does not repeat the common functional graph. Worker `build` retains the native compiler namespace and installed bundle. `--complete-aggregate` selects worker mode `ci` instead, preserving that build and additionally running the unchanged aggregate as an explicit audit. The private Docker configuration supplied by the outer launcher is forwarded only to Docker CLI subprocesses. Partial prepared-image input is rejected. The image owner removes the loaded image and all Docker state on success or failure; the preparation owner retains seed-directory cleanup. |
| `python3 scripts/select-ci-reuse --event-name NAME --event-path PATH --repository OWNER/REPO --api-url URL [--github-output PATH]` | Select reuse only for a `push` to `refs/heads/main` whose checked-out commit has exactly two parents, whose first parent equals the event `before` SHA, whose first parent is the merge base of the two parents, and whose tree equals the second-parent tree. Through the GitHub API, require exactly one associated merged pull request whose base, head, merge commit, repository, and `main` ref equal those Git identities. Then require the uniquely identified latest successful `pull_request` run of `.github/workflows/ci.yml` at that exact second-parent head. All three required jobs must have completed successfully in the same run, and each must contain one successful API-visible step whose name binds that merged pull-request number, base SHA, and head SHA. Print a stable JSON record and optional GitHub output rows. Every malformed event, Git/API/read error, truncated response, recursion failure, pagination or latest-run ambiguity, missing field, identity mismatch, direct push, non-merge commit, missing job or evidence step, or non-success result selects `reused=false`; it never fails the workflow or suppresses verification. The token is read only from `GITHUB_TOKEN` and never printed or persisted. |
| Installed fresh-image source setup | Reuse the explicit full-history `.align-revision` checkout already built by local preflight, or clone the remote when no checkout is supplied. Clone without hardlinks into the disposable profile source, verify the checked-out identity, and preserve the FRESH-WORKER prohibition on shallow, promisor, alternate-object, and replacement-object repositories. The Docker build's Cargo-cache-only source may use an exact depth-1 filtered fetch because it is never admitted as worker source. Reconstruct the exact boundary environment before `fresh-supervise` on both supported cgroup drivers so Docker-injected variables cannot change validation precedence. |
| Installed fresh-image stage and native-platform boundary | `image/fresh/Dockerfile` has one named `builder` stage and one final named `runtime` stage pinned to the same immutable multi-architecture Ubuntu 24.04 OCI index `sha256:561618e2c15bf2397621dd04f96926663a3b5616c189cf7e38db7e82f5c538ea`. Docker selects either the native linux/amd64 or linux/arm64 child; emulation is not acceptance evidence. The builder binds the observed kernel architecture to the Rust host, Debian multiarch tuple, ELF machine, dynamic loader, runtime paths, and schema-2 manifest row, and the controller/worker independently reject a manifest/kernel mismatch before a child. It exclusively owns apt and apt.llvm.org access, source checkout, Rust installation, native compilation, runtime-tree materialization, Cargo fetch, manifest construction, and deterministic self-test fixture construction. The runtime stage performs no network or package-manager operation. It installs only builder-produced paths required by the installed-profile contract: the complete unpruned manifest-bound `/runtime` tree, `/opt/align-llm/tool-bin`, `/var/cache/align-llm/cargo`, the six runtime control/profile executables, the canonical manifests and public keys, and the self-test tree. LLVM and the architecture-specific system-library/header roots are materialized in one invocation so aliases that resolve to the same builder device and inode remain one inode across their separate runtime roots; the builder checks the constructed roots and the runtime stage repeats the representative three-root inode assertion immediately after `COPY --from=builder /runtime /runtime`. This changes only physical storage identity: every path, byte, mode, manifest digest, runtime binding, and admitted tool remains present, while distinct source inodes are never merged merely because their bytes match. An explicit builder-produced control tree supplies regular `/usr/bin/python3` and `/usr/bin/python3.12` files, a symlink-free Python 3.12 standard library, and the native multiarch `libexpat.so.1` dependency. Before completing the image, the runtime stage compares every transferred system path with the final base's retained dpkg ownership lists and fails if any path overlaps a base package. The manifest-bound runtime library trees remain only below `/runtime`; both controller and worker validate the complete runtime-binding manifests before probing retained tools and give those probes the architecture-specific internal `/runtime/system` library path. This capability does not classify or prune individual libraries within the materialized runtime tree; a future closure-minimization capability must derive a complete reachable inventory and own real-image absence checks before removing any such bytes. The builder verifies the exact control-tree inventory and representative supervisor imports before transfer; the final stage repeats those checks, and each native installed profile exercises every manifest tool probe, real compiler self-test, trust/replacement refusal, and adoption boundary after transfer. The explicit `--complete-aggregate` audit additionally exercises the common capable graph when its own owner changes. Builder-only roots such as `/root/.rustup`, `/root/.cargo`, `/usr/lib/llvm-22`, `/build`, compiler headers, builder apt state, and source checkouts are absent from the final filesystem; the untouched final base retains its coherent dpkg inventory. Public build arguments, entrypoint, command, manifest schema, signing-key layer ordering, and installed-profile behavior remain unchanged; runtime-binding targets are selected only by the authenticated native architecture row. |
| GitHub Actions | On each job, first evaluate exact merged-PR reuse. Every pull-request job finishes with an API-visible evidence step whose name contains the event's pull-request number, base SHA, and head SHA. Reuse requires the hosted job plus both native installed-profile jobs, `x86_64` on `ubuntu-24.04` and `aarch64` on `ubuntu-24.04-arm`, to select the same valid reviewed head evidence and expose that exact successful binding step. Otherwise resolve event refs, invoke the shared classifier, run documentation/static checks only for `docs_only`, run the compiler and hosted graph for `hosted`, and run focused qualification once in each native job followed by that row's installed-image qualification for `fresh_installed`. A pure pin scope therefore runs the ordinary hosted graph once and skips both native installed qualifications. Workflow dispatch, direct push, non-exact merge, unavailable evidence, or an unusable event base runs the normal gates. Both required job definitions use `timeout-minutes: 15`. Each installed step uses `--installed-profile-only` without `--complete-aggregate`; its full Align source cache and Buildx layer scope include the architecture, every restored checkout is revalidated, and `pull` remains enabled. A cache miss builds from source; export errors remain non-fatal, pull-request cache entries are never promoted to trusted `main` state, and an exact reused merge deliberately leaves the default-branch caches unchanged. Signing material is prepared only for a normally executing installed gate and cleaned in an `always()` step. Workflow permissions remain read-only and add only `actions: read` and `pull-requests: read` for the evidence queries; the cache service uses the run-scoped Actions credential and no registry or package write. |

The stage row's historical “installed-profile behavior remains unchanged” clause describes the
installed image and its entrypoints, not routine qualification cadence. Section 1.1 of
`check-gate-topology.md` supersedes that cadence: the complete aggregate is explicit-only.

Inputs are explicit command arguments or GitHub event fields. The stamp is local evidence only; it
is not a persisted product artifact or a substitute for the review envelope and hosted check
evidence. It contains no credential, machine path, or command output. Schema version 1 records the
head, merge base, scope, owner label, and UTC creation time.

## Classification ownership

Markdown-only additions and modifications are `docs`. A deletion is never light. Every other path
is executable verification. An added or modified `.align-revision` accompanied only by added or
modified Markdown selects `pin`: local preflight runs the request owner and exact managed-toolchain
verification, while `hosted=true` makes GitHub CI run the ordinary hosted graph once. A pin deletion
or rename fails closed to `fresh-image`; a pin plus another executable path selects that path's
ordinary `hosted` or `fresh-image` owner. Ordinary `src/` and platform-independent `eval/` changes
select `hosted`; the hosted graph compiles and exercises them with the pinned Align toolchain.
`eval/runners/run-coding-task.py` remains in `fresh-image` because its Linux subreaper,
process-scanning, and user-namespace behavior is target-local. The classifier owns the exact
fresh-image path inventory currently consumed by both CI jobs. Changes to that inventory, the
workflow, the Makefile, fresh image inputs, worker/control implementations, or their qualification
owners select `fresh-image`. A future target-local source or evaluation capability must add its
exact owner path to that inventory in the same change. Unknown executable paths select `hosted`;
selection machinery selects `fresh-image` so a classifier change cannot silently exempt its own
deepest consumer.

The four outcomes share flags between local and hosted execution; `pin` is deliberately not a local
superset of `hosted`:

```text
docs         static documentation checks
pin          local owner + managed Align ensure/verify; hosted CI runs the hosted graph
hosted       owner + pinned Align build + hosted functional graph
fresh-image  local owner + focused qualification + installed profile; hosted CI runs the common graph
```

The managed local toolchain closes these paths before adoption:

| Path | Owner | Required regression |
| --- | --- | --- |
| First ensure and exact fetch/build | `scripts/align-toolchain` | a local repository plus fake Cargo fixture proves the pinned checkout and required release outputs are selected outside Git |
| Warm ensure and verify | `scripts/align-toolchain` | a warm invocation performs no build; dirty state, missing output, and failing compiler probe are rejected with the caller-owned checkout retained |
| Cooperative overlap and failed preparation | revision lock and private temporary directory | two same-revision helper invocations build once; injected build failure, missing output, and failing compiler probe publish nothing and remove their temporary state. Mutation by non-cooperating processes is explicitly outside this trusted developer-cache contract |
| Compiler-selection overrides and default | `scripts/alignc`, Makefile | authenticated fresh mode rejects every other path; explicit `ALIGNC` wins; explicit `ALIGN_REPO` selects only that checkout; default and empty Make `ALIGNC` select the managed wrapper and never sibling/PATH state |
| Local preflight plan and execution | `scripts/pre-pr` | missing owner is rejected before ensure; plan predicts and prints managed ensure without side effects; execution runs owner before ensure/verify; explicit `--align-repo` retains source-build behavior; fresh installed qualification receives the exact selected checkout after focused qualification; fresh scope omits the common hosted graph locally and required hosted CI still selects it; active-command termination is forwarded, reaped, and preserved without a stamp |
| Pin update | `.align-revision`, managed helper, and hosted bundle identity | the new pin invalidates revision-bound compiler caches, the real managed compiler builds, the request owner uses it locally, and hosted CI runs the ordinary graph against the same revision; installed-image identities move only when another changed path selects that owner |

Allocation, generic monomorphization, interface serialization, runtime inspection, detail levels,
and product migration are N/A because this capability owns an out-of-process development
toolchain, not an Align-language API or persisted product record. No cache manifest or persisted
schema exists. Repository credentials are N/A for the default public source;
an explicitly configured repository is delegated to Git credential handling and no credential is
read, printed, or copied by this helper.

Security, race, mutation, and resource qualifications that are not in the existing
`run-fresh-worker-qualification` inventory remain outside this capability. Local preflight keeps
the ordinary Docker daemon build and its local layer cache. Hosted CI uses BuildKit's
content-addressed cache: the base-image digest, Dockerfile instructions, copied file bytes and
modes, `.align-revision`, pinned Git and bubblewrap commits, and Rust version form the effective
build identity. A source or instruction change invalidates that layer and its descendants. Mutable
apt repository state is deliberately refreshed by incrementing the committed cache-scope schema,
which forces one cache-miss source build; it is not an unnamed clock input. The random public-key
build arguments occur only in the last layer, so every run rebuilds the trust-key binding while
retaining immutable toolchain layers.
The Cargo-cache image layer avoids unrelated Align history without weakening worker source
admission. Its cache identity is deliberately complete before any repository-owned controller,
worker, profile, manifest-generator, or self-test input enters the Docker build: the builder first
constructs and materializes the pinned Git and Rust runtimes, copies only `.align-revision`, and
performs the exact shallow Cargo fetch. A pin, Git/Rust toolchain, base-image, or fetch-instruction
change invalidates that layer; an image-control or worker-only source change does not. The later
control and manifest layers consume the admitted cache without changing this ownership boundary.

Runtime materialization is an image-size and transfer optimization, not a manifest-format change.
The helper owns construction of the new target within one Docker build layer; the Docker builder
owns rollback of a failed layer and the installed image owns the completed target. Its explicit
path arguments are the only inputs, there are no environment defaults, and its cache identity is
the source layer plus the helper bytes. The source trees are builder-owned and immutable during one
invocation, so concurrent source mutation and independent-process sharing are unsupported rather
than hidden synchronization contracts. Target hardlinks do not change per-path modes, bytes,
manifest digests, runtime-binding paths, or the worker's later private-copy behavior. There is no
persisted schema, wire encoding, migration, allocation transfer, product ownership surface, or
minimum tool-version contract; those dimensions are N/A because the output is an internal Linux
filesystem layer consumed and attested by the existing image owner.

The multi-stage boundary is an image construction and transfer optimization, not a runtime or
manifest-format change. The builder owns every mutable or network-derived intermediate until the
Docker stage completes. The final stage borrows no builder root and receives only explicit
`COPY --from=builder` artifacts. The outer control Python closure is separate from the
manifest-bound private runtime because `fresh-supervise` must validate and construct that private
runtime before it can enter it. Its fixed inventory is structural identity: regular files,
directories, modes, bytes, and relative paths are copied into a private builder output, checked
before the stage boundary, and checked again in the final stage before key binding. The Ubuntu base
digest, builder instructions, control-tree construction instructions, copied artifacts, and random
public keys are the complete image cache identity. The random keys remain final-stage-only so they
do not invalidate the transferred immutable artifacts. Concurrent stage execution, allocation
transfer, external schema compatibility, migration, and independent-process mutation are N/A
because Docker owns the immutable content-addressed stage graph and one build never exposes its
intermediate roots to a consumer.

The hosted apt archive cache is a transient CI dependency cache, not a product artifact. The
workflow owns the requested package list and the temporary archive directory; the helper owns
repository setup, verification, installation, and cleanup of every path it creates. A restored
entry is borrowed until `dpkg` completes and then removed. A successful miss becomes eligible to
leave only a current-user-owned archive set after every other owned path is cleaned; all other
paths attempt archive removal, and cleanup failure prevents the workflow save. The request
identity is structural over the sorted package names, LLVM major, runner OS/architecture,
`ImageVersion`, and manual generation `g2`. The moving apt.llvm.org snapshot is deliberately not in
the key: the first trusted `main` miss pins one signed snapshot for that runner-image generation,
and `dpkg-query --show llvm-22-dev` records the selected version. A generation bump is the explicit
escape from a bad entry.

Cache integrity against truncation or corruption comes from the exact checksum manifest; hostile
writer exclusion comes from GitHub Actions cache scope. Pull requests may restore the base/default
cache but never save this entry. The cache key and restore steps run for a normal hosted consumer
and on `main`. Installation runs for every normal hosted consumer, and also for an exact reused
`main` merge only when the entry is absent. That trusted miss runs Rust setup, the pinned Align
build, and the complete hosted functional graph against the exact resolved archive set before
saving it. The workflow then runs `verify` immediately before the save-only action, performs an
exact-key, lookup-only restore with cache-miss failure immediately afterward, and separately
requires the confirmation action's `cache-hit` output to equal the literal `true`. The explicit
output assertion covers cache-feature unavailability, for which the pinned action returns success
before enforcing cache-miss failure. A silent save warning or unavailable cache backend therefore
cannot leave the publishing job green without a branch-visible entry. Thus exact check
reuse cannot publish an unexercised moving snapshot, while later exact
merges with a cache hit do not install an unused toolchain. A restore miss or rejected set falls
back to the same signed apt path, and consumer, candidate verification, or publication confirmation
failure fails the publishing `main` job
rather than claiming the cache was seeded. Concurrent independent jobs are supported through
immutable cache keys; one process does not share apt or dpkg state with another. Wire schemas,
product ownership, allocation transfer, runtime inspection, migration, and non-Debian installation
are N/A because the helper is bounded Ubuntu-hosted automation and rejects unsupported install
hosts.

The fixed apt configuration and repository paths are process-global on one host. Overlapping
install invocations on the same host are unsupported rather than synchronized; sequential
invocations reject stale path objects before dpkg, apt, repository-network, or fixed-path mutation,
while the current invocation may retry repository setup over only the partial state it already
owns. GitHub invokes the helper once per fresh hosted job. Concurrent independent jobs run on
separate ephemeral hosts and share only the immutable cache service entry. `key` is read-only and
may run concurrently with any mode.

GitHub cache access is branch-scoped. Pull requests may read the trusted `main` cache and their own
cache but cannot publish into `main`. An exact reused merge does not rebuild merely to promote its
pull-request cache: the source PR's successful loaded-image qualification is the evidence, while
BuildKit state remains a non-authoritative performance optimization. A later pull request may read
matching older `main` layers and builds every missing layer from source before qualification. The
apt cache retains the distinct same-snapshot consumer exception defined above because it is an
immutable hosted-toolchain input, not qualified image evidence. BuildKit verifies content digests,
an export failure does not fail an otherwise valid PR build, and the loaded image still passes the
complete attestation and installed-profile owner on every normally executing pull request. Cache
archives, signing seeds, and prepared image tags are transient schema-N/A implementation data and
are never product artifacts. Concurrent jobs may race to export the same pull-request scope;
content addressing makes either result usable, and no check consumes another live job's output.

The merged archive-cache capability is the compiler bundle's miss-path prerequisite. The hosted
compiler bundle is the normal check job's first toolchain choice. A verified exact hit
sets `ALIGNC` to its `alignc`, replaces rather than appends `LD_LIBRARY_PATH` with the bundle
directory, and skips apt archive restore/replay, Rust setup, Align checkout, and compiler build.
A miss runs those existing fallback owners, builds the pinned compiler, creates the bundle before
the hosted functional graph, and makes that same bundle the graph's real compiler/runtime consumer.
Only a successful `main` miss may publish. Immediately before saving, the helper reverifies the
unchanged candidate; afterward an exact-key lookup and separate literal `cache-hit=true` assertion
prove branch-visible publication. Pull requests consume a miss-created bundle but never save it.
An invalid exact hit fails closed instead of falling back because immutable trusted state with the
right complete identity but wrong bytes is a generation defect. The external Align revision is
bound to its own repository rather than current-repository ancestry; `create` proves exact checkout
identity and clean source state. Ambient ELF dependencies are structural N/A because the exact
runner `ImageVersion`, OS, and architecture are cache identity and required acceptance context.

`manifest.json` is compact canonical ASCII JSON without insignificant whitespace and terminated by
exactly one LF. Its top-level field order is
`schema_version`, `align_revision`, `image_version`, `runner_os`, `runner_arch`, `rust_version`,
`llvm_major`, `bundle_bytes`, then `files`. `schema_version` is integer 1; `llvm_major`,
`bundle_bytes`, and file sizes are canonical JSON integers in unsigned 64-bit range; `llvm_major`
also satisfies the CLI's unsigned 16-bit range. Identity strings equal the explicit CLI inputs byte
for byte. `files` is ordered `alignc`, `libalign_runtime.a`, then
`libLLVM.so.MAJOR.1`; each row is ordered `name`, `size`, `mode`, then `sha256`. Modes are decimal
493, 420, and 420, and digests are lowercase 64-hex. `bundle_bytes` is the sum of the three payload
sizes and excludes the manifest. Unknown, duplicate, missing, reordered, non-canonical, non-ASCII,
oversized, wrong-width, or trailing data is rejected before executing the admitted compiler. The
producer and consumer share the helper, while independent semantic-to-byte and byte-to-semantic
golden vectors keep both directions owned. The workflow passes `.align-revision`, `ImageVersion`,
`RUNNER_OS`, `RUNNER_ARCH`, the pinned Rust version, and LLVM major explicitly and unchanged; no
unnamed environment input participates in bundle identity or validation.

On one target path, `key` is read-only. `verify` before `create` observes a missing target and after
the atomic rename observes a complete target. Concurrent creates use distinct private staging
directories: exactly one rename may establish the absent target, and a loser cleans only its own
staging directory. A target that exists at entry is rejected before staging. Concurrent verifies
are read-only; mutation of an admitted target is unsupported and fails verification rather than
being repaired. Independent paths and independent processes are supported. Python 3.12 on GitHub's
`ubuntu-24.04` runner is the minimum acceptance environment; newer versions are supplementary.
Detail levels, discriminators, option states, aggregate entrypoints, process-global state,
allocation ownership, embedded NUL, interface serialization, and generic monomorphization are N/A:
the helper has one exact filesystem representation, rejects NUL through OS path handling before
side effects, and neither exposes an in-process API nor shares mutable process state.

The proportional-preflight implementation, regression, CI adoption, documentation, and timing
records form one consumer-complete capability. That candidate is roughly 1,200 changed
hand-written lines because the shared classifier must be adopted by both local preflight and both
CI jobs, and the installed runner must expose the non-duplicating mode before either consumer can
use it. Splitting those pieces would leave an unused producer or retain a second path inventory and
would make drift more, not less, likely during integration.

The original hosted image cache was a follow-on consumer-complete capability. Its preparation
helper, prepared-image admission, workflow build owner, owner regressions, and then-required
cache-publication path landed together so no intermediate change exposed private signing material
to ad hoc shell or built the image twice. The later exact-reuse bypass removes only merge-push
publication after measurements showed it dominated the reused run; normally executing builds keep
the same preparation, admission, qualification, and cleanup owners.

Merge-push reuse is check evidence reuse, not a new test tier. The exact PR head remains the tested
tree, and the merge commit is accepted only when it has that identical tree and the exact tested
base as first parent and parent merge base. Each successful source job independently records the
PR number and those base/head identities in its API-visible step list; the selector requires both
exact step records. This excludes squash/rebase merges, conflict resolutions, direct pushes,
octopus merges, merge commits with a modified tree, and PR evidence from another PR, base, or
workflow even when another run uses the same head commit. It deliberately falls back to normal
execution rather than turning API availability into a new required service boundary.

The reuse selector's schema-1 JSON fields are `version`, `reused`, `reason`, `source_head`,
`pull_request`, and `workflow_run`, in sorted-key compact JSON. GitHub output writes the same fields
as newline-terminated scalar rows; booleans are lowercase and unavailable identities are the empty
string or integer zero. Workflow expressions consume only `reused` and, when true, the three source
identities. `reason` is a bounded diagnostic enum, not persisted evidence or a compatibility API.
The selector exits zero for both reuse and fallback. Argument parsing exits 2; inability to append
the requested GitHub output exits 1 because later steps could otherwise observe missing state.

After the event body is bounded and decoded, a push validates the token/API URL before event and
Git/API identities. Local Git validation precedes remote reads; merged-PR identity precedes
workflow-run identity; and workflow identity precedes job status. Event and API bodies are limited
to 1 MiB, each API request has a
15-second timeout, and full pages are treated as pagination ambiguity. API calls are read-only.
Python owns all response allocations until process exit; there is no persisted cache, shared
mutable state, reflection, or runtime source read. Two CI jobs may query concurrently and must reach
the same immutable identities, but neither depends on the other's result. These dimensions are N/A
for product ownership, wire encoding beyond GitHub JSON/UTF-8, schema migration, and model metrics
because the selector produces only transient verification routing.

The signing-material helper exits 0 after complete preparation or cleanup, 1 for an operational or
validation failure, and 2 for invalid argument combinations. Preparation validates the target path
and its output encoding, generates image seed, run seed, tag, and the complete output buffer in
memory, then creates the directory, writes the seeds and marker, and performs one append; failure
removes only helper-owned known entries. Cleanup validates the absolute
line-safe path, directory type/owner/mode, exact inventory, both seed types/owners/modes/sizes, and
the bounded UTF-8 JSON marker in that order before deletion. The helper owns the directory and
files until cleanup; the image owner borrows seed bytes, copies them into its own temporary
directory, and never mutates the originals. There is no move-out, source nulling, replacement,
runtime inspection, reflection, or persisted migration because the material lives for one Actions
job. GitHub output is newline-delimited ASCII in the fixed row order named above; all values are
line-safe and embedded NUL is rejected through path validation. The marker uses sorted compact JSON
with schema `version: 1`; its semantic fields, rather than file bytes, are the cleanup identity.

Prepared-image options admit exactly two states: all absent, which owns seed generation and a local
Docker build; or all present, which validates before Docker and borrows an already loaded image.
Every partial combination is rejected before side effects. Concurrent use of one material path is
rejected by exclusive directory creation; independent absolute paths are supported. Aggregate and
focused verification do not share material, and cache exports are content-addressed independent
processes. Scalar-width, interface serialization, monomorphization, allocation parity, wire golden
vectors, and minimum Docker CLI versions are N/A: this is Ubuntu 24.04 hosted automation using
commit-pinned actions that install their owned Buildx version, while the unchanged local path uses
the repository's existing Docker prerequisite. The owner regression checks semantic-to-output and
output-to-semantic rows rather than a persisted byte format.

## Closure matrix

| Path | Owner | Regression |
| --- | --- | --- |
| Documentation addition/modification | classifier and preflight | docs scope; no Align, Make aggregate, Docker, or stamp in plan mode |
| Executable application (`src/`) or platform-independent evaluation/ordinary script change | classifier and preflight | hosted scope with owner before Align build and hosted graph; no focused or installed platform profile |
| Linux sandbox runner addition, modification, deletion, rename, or pin-mixed change | classifier and preflight | exact `eval/runners/run-coding-task.py` owner selects focused and installed native profiles |
| Added/modified pin plus added/modified documentation only | classifier, preflight, and hosted CI | pin scope; local owner, managed ensure, and exact verification without a local aggregate; hosted CI graph once; no focused or installed platform profile |
| Fresh-image, workflow, classifier, or Makefile change | classifier and preflight | fresh-image scope with focused once, installed once, required Docker, and `DOCKER_HOST` absent |
| Deleted/renamed pin or pin plus another executable change | classifier and preflight | fail closed to fresh-image or the other executable path's normal owner; never pin scope |
| Deletion, rename pair, unknown Git status, invalid ref, or failed diff | classifier | reject or fail closed; never docs-only |
| Dirty tree, `main`, empty diff, missing owner, owner failure, gate failure | preflight | reject before stamp; later gates do not replace the first failure |
| HEAD/worktree mutation during a gate | preflight | reject after the command sequence and write no stamp |
| Plan mode | preflight | stable plan, no command execution, no stamp, and no sibling build |
| Python entrypoints | classifier, preflight, and workflow owner | imports create no repository `__pycache__` or `.pyc`; a clean candidate remains clean before and after plan mode |
| Focused-only qualification | qualification runner | inventory check plus every focused owner exactly once; installed owner absent |
| Installed-only qualification | qualification runner | inventory check, no focused owner, installed owner exactly once |
| Complete qualification | qualification runner | focused owners once followed by installed owner once |
| Docker unavailable | image smoke and qualification runner | optional direct smoke reports SKIP; required preflight/CI mode fails |
| Signing-material preparation, partial failure, malformed reuse, and cleanup | preparation helper and image smoke | new absolute directory with two private 32-byte seeds and public-only outputs; no seed disclosure; partial prepared input, wrong mode/type/size/tag, unknown cleanup entry, or ownership marker mismatch is rejected before Docker; preparation failure removes owned partial state; workflow cleanup runs after build or qualification failure |
| Scratch and prepared image construction | image smoke and workflow | local/default mode builds with random public keys; hosted mode builds and loads the exact random-key image once, then the installed owner admits it without a second build and removes it on every exit |
| Runtime materialization success, aliases, cycles, and failure | materialization helper and Dockerfile | deterministic traversal preserves bytes and modes, removes all symlinks, omits dangling links and directory cycles, maps every repeated resolved regular-file identity across one or several source roots to one target inode, leaves equal-byte distinct identities separate, and produces the same logical digest tree as independent copies; incomplete pairs, canonical target overlaps including symlink-parent aliases, same-source descendant targets, and an earlier target inside any later source fail as arguments before construction; every existing target is rejected before any target construction, and an unsupported entry fails nonzero; the Dockerfile continues to materialize Git, Rust, bubblewrap, LLVM, and system roots before manifest generation and proves representative cross-root LLVM aliases share one inode both before and after the stage transfer |
| Builder/runtime image split, control closure, package identity, and final inventory | Dockerfile, controller, worker, and development-preflight owner | static ownership regression requires the exact pinned base digest in both stages, no network/package-manager command after the final `FROM`, explicit stage transfers, no complete builder library overlay, no post-materialization runtime-library pruning, runtime-binding validation before both controller and worker tool probes, fixed internal-only probe library paths, final-key ordering, and explicit rejection of builder-only roots; a real local image build checks the outer control closure twice across the stage boundary, rejects any symlink or unexpected entry, proves every transferred system file is absent from the final base's package ownership inventory, preserves the complete generated runtime manifest and entrypoint, passes the complete installed profile, and proves builder-only roots are absent from the loaded image. Runtime-library reachability and pruning are explicitly deferred until a separate capability owns a generated closure and real-image absence regressions. |
| Normal child exit with a briefly draining descendant or a persistent descendant | image supervisor/bootstrap, fresh worker, image-control owner, and worker unit owner | controller subreaper mode is established before its first child and verified after exec by the bootstrap; the worker establishes it independently. The direct child is already exited; a descendant that naturally exits within the fixed one-second grace is reaped without a signal and the owning operation may succeed; a descendant still present after the grace is killed through the authenticated exclusively owned cgroup, fully reaped through `waitpid(-1)` to `ECHILD`, and makes the owning operation fail even when it changed process group or session or the direct child returned zero. The controller owner reaches this path through production `_run_controlled_child`, and the worker owner reaches it through production `run_owned`; both retain the production termination, `cgroup.kill` ownership, forced-failure, and reap logic while replacing only the unavailable local cgroupfs transport. Both paths prove no child and an empty authenticated simulated leaf before production leaf removal. |
| Apt package vector; archive key, hit, miss, corruption, repair, cleanup, and branch scope | apt helper and check workflow | one-line Debian-name grammar, non-empty/duplicate rejection, key normalization, and missing-input rejection; a clean hit requires a bijection between strict manifest basenames and regular non-symlink archives before checksum and invokes neither apt nor the repository; duplicate, missing, extra, absolute, nested, traversal, symlink, truncated, corrupt, or unconfigurable sets are rejected and repaired before the authoritative no-removal signed install; a newly resolved set and the post-consumer candidate must pass the same exact verifier; repository suite fallback and exactly one pinned primary key fail closed; regular files, non-directory parents, and dangling-symlink collisions at every fixed global target remain caller-owned and are rejected before dpkg, apt, network, or fixed-path mutation; repository retry accepts only invocation-owned partial key, source, and directory state and can recover when a later probe succeeds; an invocation-created keyring directory is removed after its key; main/repository/key/config/work cleanup precedes archive retention, and injected cleanup failure attempts archive removal and exits nonzero; miss-then-hit round trip succeeds; pull requests never save; an exact reused `main` miss runs the real hosted consumer, reverifies the candidate, saves, confirms the exact key, and requires literal `cache-hit=true`; cache-miss failure, cache-feature unavailability, false output, and missing output all fail publication; a `main` hit skips unused installation |
| Hosted compiler bundle construction, hit, miss, invalidation, cleanup, and branch scope | compiler-bundle helper and check workflow | exact identity/key rows; existing target rejection; clean exact external checkout; regular source files and resolved LLVM SONAME; private sibling staging; exact four-file inventory; canonical schema and field/file order; size/mode/checksum rejection; no symlink or extra entry; admitted compiler version and exact bundled LLVM loader resolution; partial copy/manifest/verify/rename cleanup; a miss creates before and is consumed by the full hosted graph; a hit skips apt, Rust, checkout, and build; pull requests never save; main reverifies, saves, exact-lookups, and requires literal hit; cache miss, feature unavailability, false output, and missing output fail publication; invalid exact hits fail closed; independent jobs share only immutable entries |
| Build cache hit, miss, invalidation, export outage, and branch scope | Dockerfile, development-preflight owner, and Buildx workflow | static ordering proves the exact `.align-revision` copy and Cargo fetch complete after the materialized Git/Rust toolchain but before every controller, worker, profile, manifest-generator, and self-test input; a controller/worker-only change therefore retains the Cargo-fetch layer while a pin or toolchain change invalidates it. A normally executing hit reuses all content-identical visible layers but rebuilds the random-key layer; a miss or invalidated layer builds from source; export failure is non-fatal. Exact reused fresh-image merges skip classification, Buildx setup, signing-material preparation, image build/export, qualification, and cleanup; they do not promote PR cache state into `main`. PR caches never become trusted `main` cache, and a later PR must rebuild any layer missing from its visible older cache before installed qualification. Cache-service import transport failure is N/A as an independent fallback boundary because the job already depends on the same Actions service for checkout, event, and step execution. |
| Pinned Align source setup | preflight, qualification runner, image smoke, workflow, and Dockerfile regression | explicit full source propagates to the installed owner and is cloned without hardlinks; checked-out identity is exact; shallow/promisor source is not admitted; CI caches the immutable full source by revision; only the non-worker Cargo-cache layer uses an exact depth-1 filtered fetch |
| Boundary profile on `cgroupfs` or `systemd` | image smoke | exact allowed environment reaches `fresh-supervise`; missing, malformed, relative, or extra inputs retain deterministic precedence |
| Owner success/failure | qualification runner | start/terminal records contain owner, status, and non-negative duration; failure propagates |
| Pull request, workflow dispatch, direct/non-merge push, unusable event base | workflow plus classifier test | reuse is false; exact event refs or fail-closed all-gate selection; local and hosted inventories cannot drift |
| Exact GitHub merge commit after a successful PR run | reuse selector plus both workflow jobs | event after is the checked-out two-parent merge; before and parent merge base are parent 1; merge tree equals parent 2 tree; one associated merged PR binds repository, base, head, and merge; the uniquely identified latest successful `ci.yml` PR run contains both successful required jobs and both exact PR/base/head evidence steps; both merge-push jobs report reuse. The fresh-image job skips classification and every Buildx/signing/build/source/userns/qualification/cleanup step. The hosted job skips normal gates except that a missing trusted apt or compiler-bundle entry executes its same-snapshot consumer before publication. |
| Merge with changed tree, wrong first parent/base/ref/repository, another PR/base using the same head, ambiguous PRs/latest runs, incomplete or failed job/evidence | reuse selector | reuse is false and both jobs run normal classification and selected gates |
| GitHub event/API malformed, unavailable, truncated, recursively invalid, or paginated beyond the bounded response | reuse selector | production event/API readers return a bounded diagnostic with no credential or response-body disclosure; reuse is false and normal verification continues; inability to write required GitHub outputs remains an explicit job failure |

The workflow regression loads the production classifier and reuse selector as modules, crosses
every path and failure class above, checks plan ordering and environment isolation, and statically
confirms that CI invokes both selectors, grants only their read permissions, guards normal steps,
uses commit-pinned Buildx actions with the bounded cache scope and non-fatal export, prepares and
cleans per-run signing material, forwards the prepared image through installed-only qualification,
and retains installed-only qualification. Preparation and prepared-image tests cover the exact
filesystem, argument, output, disclosure, validation-order, and cleanup contract without Docker.
Reuse tests use deterministic event, Git, PR, workflow,
and job fixtures; acceptance also queries one historical merged PR through the same selector when
network evidence is available. The existing focused fresh owners continue to test their product
contracts; this capability does not duplicate them.

## Acceptance and measurement

Required owner command:

```text
python3 scripts/test-development-preflight
```

Merge-push reuse acceptance additionally requires a hosted PR run followed by its merge-push run.
The PR must execute the normal classifier-selected jobs. The merge push must finish both required
job records successfully while each reports the same reused PR number, head SHA, and workflow run
identity and executes no compiler, hosted aggregate, focused qualification, or installed profile.
The historical baseline is PR #70: its successful PR run took 496 seconds end to end and its exact
tree merge-push run repeated the gates for 492 seconds. These are one sample each (`n=1`) on GitHub's
`ubuntu-24.04` hosted environment, with end-to-end duration defined as the Actions run's
`updated_at - created_at`. The exact source timestamps are reproducible with:

```text
for run in 31561096413 31561600798; do gh api "repos/sanohiro/align-llm/actions/runs/$run" --jq '[.id,.event,.created_at,.updated_at] | @tsv'; done
```

The target is at least 95% lower merge-push wall time for an exact fresh-image merge, without
changing PR wall time or direct-push coverage.

PR #72 met that preceding target: run `31570429008` completed in 11 seconds, a 97.8% reduction from
the 492-second baseline, while both jobs independently bound reuse to PR #72, workflow run
`31569819343`, and head `9ce09f9a26465e68c357b8331d47d0226a073f9f`.

PR #81 exposed a later regression in that merge-push outcome after default-branch BuildKit cache
publication was added. Its exact merge run `31665748310` took 373 seconds end to end (`created_at`
to `updated_at`), and the fresh-image job took 361 seconds on GitHub `ubuntu-24.04` (`n=1`). The
cache-only `Build installed image with shared layers` step consumed 341 seconds even though the PR
had already passed the complete loaded-image qualification and the merge selector had accepted its
exact evidence. Reproduce that baseline with:

```text
gh api repos/sanohiro/align-llm/actions/runs/31665748310 --jq '[.id,.event,.head_sha,.created_at,.updated_at] | @tsv'
gh api repos/sanohiro/align-llm/actions/jobs/94339817556 --jq '{job: [.id,.name,.started_at,.completed_at], build: ([.steps[] | select(.name == "Build installed image with shared layers") | [.name,.started_at,.completed_at]][0])}'
```

The exact-reuse bypass target is at least 90% lower end-to-end merge-push wall time than this
373-second baseline and a fresh-image job of at most 30 seconds. The accepted merge run must show
the reuse report and must skip classification, Buildx setup, signing-material preparation,
image build/export, source restore, user-namespace changes, installed qualification, and signing
cleanup. The source PR must still execute and pass the normal fresh-image build plus complete
installed qualification. A direct push or any failed reuse identity must still execute the normal
classifier-selected path; neither cache presence nor cache publication is acceptance evidence.

The cached-image baseline is PR #72 run `31569819343`, job `94029193340`: 502 seconds end to end for
the run and 216,344 ms for its `image-build` phase on GitHub's `ubuntu-24.04` hosted environment
(`n=1`). Reproduce the phase record with:

```text
gh run view 31569819343 --job 94029193340 --log | grep '"phase":"image-build"'
```

A local Buildx probe on 2026-08-12 built the same source once into a `mode=max` local cache and then
rebuilt with different public-key arguments. The cold invocation took 2,076.861 seconds under a
slow network; the warm invocation took 39.568 seconds, with all 17 pre-key layers reported `CACHED`
and only the final key layer re-executed. This demonstrates layer separability, not a hosted
performance claim. Hosted acceptance requires two runs: the first exact fresh-image merge publishes
the default-branch cache, and a subsequent pull request imports it, rebuilds the key layer, passes
the complete installed qualification, and reduces the image-build step to at most 75 seconds and
the overall PR run by at least 25% relative to PR #72. Cache-miss execution must also pass from
source; no result may rely solely on cache-hit coverage.

PR #74 provided the first hosted warm-cache result: run `31579614586` completed in 472 seconds,
the fresh-image job in 468 seconds, image build/export/load in 182 seconds, and installed
qualification in 246 seconds (`n=1`, GitHub `ubuntu-24.04`). Every content-heavy Docker instruction
was reported `CACHED`, but cached-layer materialization and final image export/load dominated the
build. The result reduced overall time only 6.0% from 502 seconds and therefore missed both hosted
targets. Its default-branch merge run `31580371758` completed the cache-only fresh-image job in 102
seconds, including 88 seconds for build/export, without loading or qualifying the image. Reproduce
the job steps and BuildKit cache evidence with:

```text
gh run view 31579614586 --json createdAt,updatedAt,jobs
gh run view 31579614586 --job 94059472166 --log
gh run view 31580371758 --json createdAt,updatedAt,jobs
```

The next optimization gate measures the loaded image's Docker-reported virtual size and the
hardlink-aware apparent bytes under `/runtime/git` and `/runtime` before and after materialization,
using the same base commit, Docker daemon, Dockerfile inputs, and fixed public-key build arguments
(`n=1` each). It must preserve the complete installed qualification and reduce `/runtime/git` bytes
by at least 90%; hosted wall-time remains the cross-environment acceptance metric and must still meet
the existing 75-second image-build and 25% overall-reduction targets before an end-to-end speedup is
claimed. Build the first tag from a detached `d433e4d` worktree and the second from the candidate
worktree with the same command inputs:

```text
env -u DOCKER_HOST docker build --progress=plain -f image/fresh/Dockerfile --build-arg IMAGE_PUBLIC_KEY_HEX=1111111111111111111111111111111111111111111111111111111111111111 --build-arg RUN_PUBLIC_KEY_HEX=2222222222222222222222222222222222222222222222222222222222222222 -t align-llm-slim-measure:base .
env -u DOCKER_HOST docker build --progress=plain -f image/fresh/Dockerfile --build-arg IMAGE_PUBLIC_KEY_HEX=1111111111111111111111111111111111111111111111111111111111111111 --build-arg RUN_PUBLIC_KEY_HEX=2222222222222222222222222222222222222222222222222222222222222222 -t align-llm-slim-measure:candidate .
```

The 2026-08-12 local comparison used Docker Desktop 29.5.3's default Linux/amd64 builder from WSL2.
The exact `d433e4d` baseline was 10,451,313,589 image bytes, 7,397,588,418 `/runtime` bytes, and
2,617,299,268 `/runtime/git` bytes; its Git and `git-receive-pack` paths were distinct single-link
inodes. The hardlink-preserving candidate was 6,069,945,116 image bytes, 3,016,219,340 `/runtime`
bytes, and 83,290,477 `/runtime/git` bytes; both checked Git paths shared one 142-link inode. That is
a 41.9% image reduction, 59.2% runtime-tree reduction, and 96.8% Git-runtime reduction, satisfying
the local footprint gate. The baseline build took 1,084.585 seconds cold and the candidate took
44.283 seconds with its six heavy parent instructions cached; those build times have different cache
states and are diagnostics, not a wall-time speedup comparison. Reproduce each tag's footprint
records with:

```text
env -u DOCKER_HOST docker image inspect IMAGE --format 'image_bytes={{.Size}} image_id={{.Id}}'
env -u DOCKER_HOST docker run --rm --entrypoint /usr/bin/du IMAGE -sb /runtime/git
env -u DOCKER_HOST docker run --rm --entrypoint /usr/bin/du IMAGE -sb /runtime
env -u DOCKER_HOST docker run --rm --entrypoint /usr/bin/stat IMAGE -c '%d:%i links=%h' /runtime/git/bin/git /runtime/git/bin/git-receive-pack
```

The follow-on multi-stage gate uses the same Docker daemon, fixed public keys, and current
hardlink-preserving inputs. The observed baseline is image
`sha256:15d547a7b4c5823fda475297f46270711357d9f3f8b38d6d3346e6ff3dc00e7a` from exact `530da31`:
6,069,945,116 Docker-reported bytes (`n=1`, Docker Desktop 29.5.3, Linux/amd64). Its first rootfs
layer is `sha256:42724e448bf499ec7d4b3c21d6cc68fe665ef677ed393c3dbb5357394e89ff91`,
the same layer selected by the candidate's pinned Ubuntu platform manifest. Apt repositories remain
mutable inputs, so these exact historic bytes are an image-ID-bound observation, not a promise that
a future rebuild reproduces either image byte-for-byte. The reproducible structural claim is that
the final stage transfers only the ledger-owned runtime/control paths and none of the named builder
roots. The observed candidate must pass the unchanged complete installed profile and reduce
Docker-reported virtual size by at least 35%. This is a transfer-footprint claim, not a wall-time
claim. Hosted acceptance remains the next same-cache-state run: image build/export/load at most 75
seconds and at least 25% lower overall duration than the 502-second PR #72 baseline. Record step and
job timestamps even when hosted cache state prevents the wall-time target from being claimed.
Build and reproduce the re-scoped final-stage inventory and footprint from the candidate worktree
with:

```text
env -u DOCKER_HOST docker build --progress=plain -f image/fresh/Dockerfile --build-arg IMAGE_PUBLIC_KEY_HEX=1111111111111111111111111111111111111111111111111111111111111111 --build-arg RUN_PUBLIC_KEY_HEX=2222222222222222222222222222222222222222222222222222222222222222 -t align-llm-multistage-measure:rescoped .
env -u DOCKER_HOST docker image inspect align-llm-multistage-measure:rescoped --format 'image_bytes={{.Size}} image_id={{.Id}}'
env -u DOCKER_HOST docker run --rm --entrypoint /usr/bin/du align-llm-multistage-measure:rescoped -sb /runtime /var/cache/align-llm/cargo
env -u DOCKER_HOST docker run --rm --entrypoint /bin/sh align-llm-multistage-measure:rescoped -eu -c 'for path in /root/.rustup /root/.cargo /usr/lib/llvm-22 /build; do test ! -e "$path"; done; test -z "$(find /var/lib/apt/lists -mindepth 1 -print -quit)"'
```

The initial local candidate measured 3,800,869,143 Docker-reported bytes and exposed that copying
the complete builder library tree over the final base coupled runtime bytes to mutable package
snapshots and invalidated the final base's dpkg ownership model. That candidate was rejected. The
second, also rejected image `sha256:9f5af8b28c39e650f20cbfb411dc1409779837b1917e0511e5057de7a789c437`
measured 3,200,170,355 bytes, with a 3,000,924,060-byte `/runtime` and 23,056,659-byte Cargo cache.
Against the image-ID-bound baseline this removes 2,869,774,761 bytes, or 47.3%. Its 1,303
transferred Python/libexpat system paths had zero intersections with the final base's dpkg ownership
lists, but its hand-maintained pruning claim was false: `libcryptsetup.so.12*` remained in both
runtime library trees. The re-scoped candidate therefore preserves the generated runtime tree
without per-library pruning. The re-scoped image
`sha256:eb9162ba3d17494b41673635166dfd6eb23457bebfd9fd24e558049852024152`, built by the command
above under the same environment, measured 3,215,474,083 bytes, with a 3,016,219,340-byte
`/runtime` and 23,056,659-byte Cargo cache. It shares the baseline's exact first rootfs layer and
removes 2,854,471,033 bytes, or 47.0%, while retaining the complete generated runtime tree. Apt,
LLVM, Rust, Git, and runtime-materialization layers were cache hits; the Dockerfile-dependent Cargo
fetch and later control/manifest layers rebuilt. These measurements are `n=1` observations under
the environment above. The exact-head complete installed profile remains the acceptance boundary;
intermediate uncommitted probes are diagnostic because the profile intentionally clones the
committed repository worker.

PR #75 run `31588797654` passed the invalidating hosted path in 568 seconds end to end; the fresh
job took 564 seconds, its build/export/load step 293 seconds, and installed qualification 225
seconds (`n=1`, GitHub `ubuntu-24.04`). The build produced the new downstream layers in about 68
seconds, exported and loaded them in 121.5 seconds, and exported the pull-request cache in 103.2
seconds. Merge run `31589611628` then published the smaller trusted `main` cache in a 183-second
fresh job while reusing functional and qualification evidence. These are migration/cache-publication
measurements, not the clean warm-image result.

PR #78 run `31633149090` passed the final multi-stage candidate in 605 seconds end to end; the
fresh job took 600 seconds, build/export/load 294 seconds, and installed qualification 262 seconds
(`n=1`, GitHub `ubuntu-24.04`). Exact-main run `31634023665` then passed in 281 seconds; its
cache-only fresh job took 276 seconds and build/export took 257 seconds while functional and
installed evidence were reused. These are the Cargo-layout capability's source baseline. On local
checkpoint `d94afbc`, relocating the unchanged pin-owned fetch took 7.7 seconds on its first layer
execution and the complete image build took 42.683 seconds. An immediate fixed-key rebuild took
3.185 seconds and reported the Cargo-fetch layer and every preceding toolchain layer `CACHED`
(`n=1` each, same Docker daemon). This local pair proves the new layer is reusable; the hosted PR
and exact-main runs remain the acceptance for branch-visible import and publication. Reproduce the
hosted timestamps with:

```text
for run in 31633149090 31634023665; do gh run view "$run" --json createdAt,updatedAt,jobs; done
```

The cross-root hardlink gate keeps the same Ubuntu base, complete unpruned runtime path inventory,
manifest bytes, and installed behavior. Its image-ID-bound baseline is the re-scoped PR #78 image

`sha256:eb9162ba3d17494b41673635166dfd6eb23457bebfd9fd24e558049852024152`:
3,215,474,083 Docker-reported bytes and 3,016,219,340 hardlink-aware `/runtime` bytes (`n=1`,
Docker Desktop 29.5.3, Linux/amd64). A read-only feasibility probe in the corresponding builder
materialized LLVM and the system roots with one shared source-inode table: their physical footprint
fell from 2,367,422,464 to 1,372,573,696 bytes while retaining 11,439 distinct regular-file source
identities. That probe predicts the opportunity but is not acceptance evidence. The committed
candidate must pass the owner regression and complete installed profile, prove representative
LLVM paths in `/runtime/cc-suite`, `/runtime/system/usr-lib-x86_64`, and
`/runtime/system/lib-x86_64` share one inode after the final-stage transfer, preserve an equal-byte
distinct-inode control, and reduce both Docker-reported image bytes and hardlink-aware `/runtime`
bytes by at least 25% against the baseline. Record the exact candidate image ID and `n=1` local
measurements with:

```text
env -u DOCKER_HOST docker image inspect IMAGE --format 'image_bytes={{.Size}} image_id={{.Id}}'
env -u DOCKER_HOST docker run --rm --entrypoint /usr/bin/du IMAGE -sb /runtime
env -u DOCKER_HOST docker run --rm --entrypoint /usr/bin/stat IMAGE -c '%d:%i links=%h' /runtime/cc-suite/lib/libLLVM.so.22.1 /runtime/system/usr-lib-x86_64/libLLVM.so.22.1 /runtime/system/lib-x86_64/libLLVM.so.22.1
```

The pull-request run records the fresh-image build/export/load and complete installed qualification
durations on GitHub `ubuntu-24.04`. Smaller bytes are a named footprint improvement; no hosted
wall-time improvement is claimed unless a same-cache-state comparison meets the existing targets.

Implementation checkpoint `b9d6728` produced fixed-key image
`sha256:381580c9aa6b211f440f665b1ffd306bd6065013312a8538e43013668c5b96ef` under the same local
daemon and command inputs. It measured 2,234,647,037 Docker-reported bytes and 2,035,380,006
hardlink-aware `/runtime` bytes: reductions of 980,827,046 bytes (30.5%) and 980,839,334 bytes
(32.5%), respectively. The three representative LLVM paths shared device/inode `142:678794` with
12 links after final-stage transfer. Installed qualification at checkpoint `2548a65` passed in
230.509 seconds (`n=1`, same Docker daemon and exact full Align checkout): its warm image build took
3.402 seconds, runtime-replacement checks 24.074 seconds, boundary profile 42.086 seconds, worker
aggregate 120.024 seconds, and cleanup 1.352 seconds. These local results establish the footprint
claim and unchanged consumer behavior; hosted wall time remains unclaimed until pull-request
evidence exists.

The consolidated review repair added the post-transfer assertion and fail-before-construction
canonical topology validation without changing admitted image bytes. Its exact fixed-key image is
`sha256:1ad39927516cf238a885abe65c7275442565a6235be91a217f65f3f439fecc1c` and reproduces the same
2,234,647,037 image bytes, 2,035,380,006 `/runtime` bytes, 23,056,659 Cargo-cache bytes, and shared
12-link representative LLVM inode (`n=1`, same Docker daemon and command inputs). The development
owner and Buildx Dockerfile check pass on the repair; exact-head complete preflight remains the
final local publication gate.

The hosted apt baseline is the same PR #75 run: the check job took 102 seconds and `Install LLVM
and native libraries` took 43 seconds (`n=1`, GitHub `ubuntu-24.04`). The first pull request for the
archive cache exercises a miss and must pass; its exact merge must seed the trusted `main` entry.
A subsequent run with the same runner `ImageVersion` and package request is the warm acceptance:
the install step must take at most 10 seconds and the complete check job at most 75 seconds, while
the exact package postcondition and hosted functional checks still pass. Step and job durations are
defined as `completedAt - startedAt`. Reproduce their source timestamps with:

```text
for run in 31588797654 RUN_ID; do gh run view "$run" --json jobs --jq '.jobs[] | select(.name == "Pinned Align compiler and supported checks") | {job: [.startedAt, .completedAt], install: (.steps[] | select(.name == "Install LLVM and native libraries") | [.startedAt, .completedAt])}'; done
```

PR #76 merged the archive cache after run `31597025980` passed its miss path. Main seed run
`31597640816` passed the exact archive consumer, revalidation, save, lookup, and literal-hit gates.
Clean same-commit workflow-dispatch run `31597786779` then disproved the warm performance target:
cache restore took 3 seconds, cached dpkg replay 36 seconds, Rust setup 6 seconds, supported checks
39 seconds, and the complete check job 100 seconds (`n=1`, GitHub `ubuntu-24.04`, runner
`ImageVersion=20260720.247.2`). Repository downloads no longer repeat, but package-database replay
is slower than the intended boundary.

The follow-on bundle baseline is those same 100 seconds. A local real-client feasibility probe
copied release `alignc` (5,042,072 bytes), `libalign_runtime.a` (28,454,582 bytes), and the resolved
`libLLVM.so.22.1` (150,502,496 bytes), set an exact bundle-only `LD_LIBRARY_PATH`, and passed
`alignc --version` plus complete `make hosted-checks`. This 183,999,150-byte uncompressed result is
diagnostic feasibility evidence, not a hosted performance claim. After one exact main miss publishes
the bundle, a clean same-image normal run must restore plus verify it in at most 10 seconds, skip
apt/Rust/Align source setup, pass the unchanged hosted graph, and complete the check job in at most
60 seconds. Reproduce hosted timestamps with:

```text
for run in 31597025980 31597640816 31597786779 BUNDLE_RUN_ID; do gh run view "$run" --json jobs --jq '.jobs[] | select(.name == "Pinned Align compiler and supported checks") | {job: [.startedAt, .completedAt], steps: [.steps[] | select(.name == "Restore the apt package cache" or .name == "Install LLVM and native libraries" or .name == "Install Rust" or .name == "Restore the hosted Align compiler bundle" or .name == "Verify the hosted Align compiler bundle" or .name == "Run supported project checks") | {name, time: [.startedAt, .completedAt]}]}'; done
```

`scripts/test-apt-llvm` owns replay, recovery, repository provenance, signing-key, cache-key, and
argument behavior without root, apt, or network access. `scripts/test-ci-align-bundle` owns the
independent manifest goldens, exact checkout and source admission, construction, runtime admission,
mutation rejection, cleanup, and concurrent-create behavior with a real test ELF dependency.
`scripts/test-development-preflight` owns the exact package and bundle requests, action pins,
hit/miss/consumer/publication routing, and the prohibition on the old `llvm.sh` installer. Hosted
CI remains the acceptance owner for the real Ubuntu repository, GitHub cache service, runner-image
identity, and cache transfer duration.

Before merge, run the local preflight when the pinned Align checkout is available without modifying
the paused Request 6 branch. The hosted CI jobs are final environment evidence. Compare the next
fresh-image capability's number of diagnostic pushes and repeated focused executions with PR #61
and PR #69. A 2026-08-12 local baseline reached 681.372 seconds before exposing the existing
`cgroupfs` environment leak; its boundary phase took 435.077 seconds and its image build took
195.235 seconds. Exact shallow source reduced the boundary phase to 86.945 seconds but was
correctly rejected by the worker's full-history source contract, so it is not an adopted result.
After adopting the valid exact shallow fetch for the Docker-only Cargo source, a later invocation
observed a 144.999-second image build. With that layer warm and a reusable full source checkout,
the complete installed profile passed in 198.572 seconds: image build 4.555 seconds, boundary
profile 36.441 seconds, and worker aggregate 104.677 seconds. These failed cold/network and passing
warm/reused invocations are diagnostic observations under different conditions, not a reproducible
speedup comparison. An equivalent passing baseline and candidate run remain required before making
an end-to-end performance claim; hosted results remain the cross-environment evidence.
