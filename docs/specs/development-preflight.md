# Development preflight

Status: implementation plan of record.

This capability makes local verification and GitHub Actions select the same checks. It addresses
the repeated push-to-diagnose loop observed in FRESH-WORKER and Request 6 without changing product
behavior, the fresh-worker trust contract, or the pinned Align revision.

## Public contract

| Surface | Contract |
| --- | --- |
| `python3 scripts/classify-verification --base REF --head REF` | Resolve both refs as commits, compute their merge base, inspect the no-renames name-status diff, and print a stable JSON object containing `scope`, `base`, `head`, `docs_only`, `hosted`, `fresh_focused`, and `fresh_installed`. `--github-output PATH` writes the same scalar fields as GitHub output rows. `--all --head REF` selects every executable gate when no trustworthy base exists. Invalid refs, malformed Git output, deletions, unknown statuses, and unknown non-Markdown paths fail closed to executable verification. |
| `python3 scripts/pre-pr [--base REF] [--align-repo PATH] --owner-test LABEL -- COMMAND ...` | Require a named non-`main` branch, a clean worktree, a non-empty merge-base diff, and one owner command for executable changes. Run the owner first, then the classifier-selected local CI-parity gates. Documentation-only changes run `git diff --check` and Markdown fence validation. Executable changes build the exact pinned sibling Align compiler and run `hosted-checks`. Fresh-image changes additionally run the focused qualification once and the installed profile once with `DOCKER_HOST` removed and Docker required. Recheck the exact HEAD and clean worktree, then write a versioned stamp below `git rev-parse --git-path align-llm-preflight`. `--plan` prints the selected commands without side effects and writes no stamp. |
| `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker [--align-repo PATH] [--prepared-image IMAGE --image-signing-seed PATH --run-signing-seed PATH]` | Verify the qualification inventory, skip the already-owned focused commands, and run only the installed profile. `--installed-profile` retains the complete focused-plus-installed capability gate. `--require-docker` turns an unavailable Docker daemon into failure instead of a skip. `--align-repo` forwards an explicit full pinned checkout to the image owner. The three prepared-image arguments are all-or-none, require an installed-profile mode, and are forwarded unchanged. Every invoked owner emits one start and one terminal timing record. |
| `python3 scripts/prepare-fresh-image-build --directory PATH --github-output PATH` | Create a new current-user-owned mode-0700 directory containing two independent 32-byte current-user-owned mode-0400 signing seeds and a schema-1 ownership marker bound to the exact directory and generated image tag. Refuse an existing target, symlink, non-ASCII/non-line-safe or relative material path, or unavailable output file. Validate and ASCII-encode the complete output record before creating the directory, then append `image`, `image_public_key_hex`, `run_public_key_hex`, and `material_directory` in one write; never print either seed or expose partial rows after an encoding rejection. `--cleanup --directory PATH` accepts only the exact marked directory and known regular files, validates directory, inventory, image seed, run seed, then the exact integer marker version and remaining schema, removes the seeds before the marker, and finally removes the directory. Preparation cleans up its own partial output on every error. |
| `python3 scripts/materialize-fresh-tree SOURCE TARGET` | Materialize one image-owned runtime tree at a new target without retaining symlinks. Traverse entries in bytewise name order, follow regular-file and directory symlinks, omit dangling child links and directory cycles, preserve resolved modes and bytes, and reject an unsupported resolved entry type or a source that produces no root. All resolved regular-file entries with the same source device and inode share one target inode, including true hardlinks and file aliases reached through symlinks or repeated directory aliases. Refuse an existing target before reading the source. The helper exits zero only after the complete target exists; an argument error exits 2 and a traversal, copy, or hardlink failure exits nonzero so the Docker build discards the failed layer. |
| `ALIGN_APT_PACKAGES="..." scripts/ci-apt-llvm.sh {key | install [--uncached] | verify}` | Own the Ubuntu CI LLVM 22 and native-library archive cache. Every mode parses the one-line request once as a non-empty, duplicate-free vector of Debian binary package names matching `[a-z0-9][a-z0-9+.-]+`; options, versions, architecture qualifiers, globs, uppercase, one-character names, and multiline input are rejected. `key` requires `RUNNER_TEMP` and `ImageVersion`, then prints exactly `path` and `key` GitHub-output rows; `RUNNER_OS` defaults to `Linux` and `RUNNER_ARCH` to `X64`. The key contains the LLVM major, runner OS and architecture, manual cache generation, runner image version, and a digest of the bytewise-sorted package vector. Validation order is mode and arity, package vector, `RUNNER_TEMP`, then mode-specific `ImageVersion` or Debian-host support. `install` accepts a restored set only when `SHA256SUMS` is a regular non-symlink file containing exactly one strict checksum row for every regular non-symlink `.deb` basename and no duplicate, missing, extra, absolute, nested, or traversal name; it then verifies every checksum, installs the same exact files with `dpkg`, and requires every requested package, `llvm-config`, and `cc`. A missing set performs the authoritative apt install; an unusable restored set first repairs dpkg state and then performs the same authoritative install. `verify` repeats exact archive membership, checksum, package, `llvm-config`, and `cc` validation without mutation, apt, or cleanup so the workflow can prove the post-consumer candidate immediately before save. The apt path accepts exactly the pinned apt.llvm.org primary signing key and its bound subkeys, proves the selected candidate comes from apt.llvm.org, tries the versioned suite before the current suite, and uses `--no-remove` so every saved transaction remains replayable by `dpkg`. Every fixed global path rejects any pre-existing object, including a dangling symlink; an existing real `/etc/apt/keyrings` directory is borrowed, while an invocation-created directory is tracked separately. Cleanup removes invocation-owned config, source, keyring, keyring directory, and work directory before deciding archive retention. Only a successful cache miss whose other cleanup succeeded leaves its archives eligible for save; every other exit attempts archive removal, and any cleanup failure exits nonzero so the workflow cannot save the candidate. Invalid arguments, an invalid package vector, or a non-Debian install host exit 2; missing inputs, pre-existing target state, repository/key failures, corrupt unrecoverable state, incomplete installation, an invalid verify candidate, or an empty cache-miss resolve exit nonzero. |
| `python3 scripts/ci-align-bundle {key | create | verify} --directory PATH --align-revision SHA --image-version VERSION --runner-os OS --runner-arch ARCH --rust-version VERSION --llvm-major MAJOR [--align-repo PATH --llvm-library PATH]` | Own the trusted hosted compiler bundle. Every mode requires an absolute ASCII line-safe directory; a lowercase 40-hex Align revision; image, OS, architecture, and Rust identities matching `[A-Za-z0-9][A-Za-z0-9._-]*`; and an LLVM major in decimal range 1..65535. Validation order is mode/arity and option ownership, scalar identities, directory, then mode-specific source or admitted-bundle state. `key` and `verify` reject the create-only arguments; `create` requires both. `key` prints exactly `path=PATH` and `key=hosted-align-bundle-g1-SHA-VERSION-OS-ARCH-rust-RUST-llvm-MAJOR` rows. Its generation-scoped key contains every supplied identity, so the external Align commit is nominal source identity and the exact runner image binds ambient ABI dependencies. `create` additionally requires an exact clean Align checkout at the named revision, regular non-symlink release `alignc` and `libalign_runtime.a` inputs, and an explicit LLVM input that resolves to one regular file with basename `libLLVM.so.MAJOR.1`. It refuses an existing bundle path, validates every source before creating a private sibling staging directory, copies exactly `alignc`, `libalign_runtime.a`, and `libLLVM.so.MAJOR.1` without symlinks, applies modes 0755/0644/0644, writes canonical schema-1 `manifest.json`, verifies the staged bundle, and atomically renames it into place. Any failure removes only its staging directory and leaves no target. `verify` requires exactly those four regular non-symlink files and no others; a manifest of at most 16,384 bytes with canonical identity, byte size, mode, SHA-256, field set, field order, and file order must match. It then runs the checksum-admitted `alignc --version` under an exact bundle-only `LD_LIBRARY_PATH` and requires the dynamic loader to resolve `libLLVM.so.MAJOR.1` to the admitted bundle file. `create` prints exactly `created bundle: PATH (N bytes)` and `verify` prints exactly `verified bundle: PATH (N bytes)` on success; diagnostics are prefixed `ci-align-bundle:` on stderr. Invalid arguments or identities exit 2; source, filesystem, manifest, checksum, mode, loader, executable, or cleanup failure exits nonzero. No mode mutates a supplied source checkout or an admitted bundle. |
| `python3 scripts/run-fresh-image-profile-smoke [--prepared-image IMAGE --image-signing-seed PATH --run-signing-seed PATH]` | With none of the prepared-image arguments, generate per-run signing seeds and build the image locally as before. With all three, validate the generated tag and two private regular 32-byte seed files before Docker side effects, use the already loaded image without rebuilding it, and run the unchanged attestation, lifecycle, trust-mutation, boundary, and worker-aggregate qualification. Partial prepared-image input is rejected. The image owner removes the loaded image and all Docker state on success or failure; the preparation owner retains seed-directory cleanup. |
| `python3 scripts/select-ci-reuse --event-name NAME --event-path PATH --repository OWNER/REPO --api-url URL [--github-output PATH]` | Select reuse only for a `push` to `refs/heads/main` whose checked-out commit has exactly two parents, whose first parent equals the event `before` SHA, whose first parent is the merge base of the two parents, and whose tree equals the second-parent tree. Through the GitHub API, require exactly one associated merged pull request whose base, head, merge commit, repository, and `main` ref equal those Git identities. Then require the uniquely identified latest successful `pull_request` run of `.github/workflows/ci.yml` at that exact second-parent head. Both required jobs must have completed successfully in the same run, and each must contain one successful API-visible step whose name binds that merged pull-request number, base SHA, and head SHA. Print a stable JSON record and optional GitHub output rows. Every malformed event, Git/API/read error, truncated response, recursion failure, pagination or latest-run ambiguity, missing field, identity mismatch, direct push, non-merge commit, missing job or evidence step, or non-success result selects `reused=false`; it never fails the workflow or suppresses verification. The token is read only from `GITHUB_TOKEN` and never printed or persisted. |
| Installed fresh-image source setup | Reuse the explicit full-history `.align-revision` checkout already built by local preflight, or clone the remote when no checkout is supplied. Clone without hardlinks into the disposable profile source, verify the checked-out identity, and preserve the FRESH-WORKER prohibition on shallow, promisor, alternate-object, and replacement-object repositories. The Docker build's Cargo-cache-only source may use an exact depth-1 filtered fetch because it is never admitted as worker source. Reconstruct the exact boundary environment before `fresh-supervise` on both supported cgroup drivers so Docker-injected variables cannot change validation precedence. |
| GitHub Actions | On each job, first evaluate exact merged-PR reuse. Every pull-request job finishes with an API-visible evidence step whose name contains the event's pull-request number, base SHA, and head SHA. When both merge-push jobs independently select the same valid reviewed head evidence and find that exact successful binding step in both source jobs, report reuse and skip functional verification except for the same-snapshot apt cache seed gate defined below. Otherwise resolve event refs, invoke the shared classifier, run documentation/static checks only for `docs_only`, run the compiler and hosted graph only for `hosted`, and run focused plus installed-image qualification only for `fresh_installed`. Workflow dispatch, direct push, non-exact merge, unavailable evidence, or an unusable event base runs the normal gates. The installed step uses `--installed-profile-only`, so focused qualification executes exactly once per executing job. Its full Align source cache is keyed by `.align-revision`; every restored checkout is revalidated before use. For `fresh_installed`, a commit-pinned Docker Buildx action builds the exact per-run-keyed image with `pull` enabled, imports the branch-visible GitHub Actions cache under schema scope `align-llm-fresh-image-v1`, and exports a complete cache with export errors ignored. Pull requests and non-reused runs load the image for qualification; exact merge pushes with reused functional evidence publish cache without loading the multi-gigabyte image into the daemon. A cache miss performs the same build from source. Exact merges publish the cache on `main`, making the trusted default-branch cache readable by later pull requests without repeating product qualification. Signing material is always prepared anew and cleaned in an `always()` step. Workflow permissions remain read-only and add only `actions: read` and `pull-requests: read` for the evidence queries; the cache service uses the run-scoped Actions credential and no registry or package write. |

Inputs are explicit command arguments or GitHub event fields. The stamp is local evidence only; it
is not a persisted product artifact or a substitute for the review envelope and hosted check
evidence. It contains no credential, machine path, or command output. Schema version 1 records the
head, merge base, scope, owner label, and UTC creation time.

## Classification ownership

Markdown-only additions and modifications are `docs`. A deletion is never light. Every other path
is at least `hosted`. The classifier owns the exact fresh-image path inventory currently duplicated
between the two CI jobs. Changes to that inventory, the workflow, the Makefile, `.align-revision`,
fresh image inputs, worker/control implementations, or their qualification owners select
`fresh-image`. Unknown executable paths select `hosted`; selection machinery selects
`fresh-image` so a classifier change cannot silently exempt its own deepest consumer.

The three scopes are cumulative:

```text
docs         static documentation checks
hosted       owner + pinned Align build + hosted functional graph
fresh-image  hosted + focused fresh qualification + required installed profile
```

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
admission.

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
cache but cannot publish into `main`; an exact merge therefore publishes missing cache state, with
the apt cache's same-snapshot consumer exception defined above. Cache data is only a BuildKit
optimization: content digests are verified by BuildKit, a miss builds from source, an export
failure does not fail an otherwise valid build, and the loaded image still passes the
complete attestation and installed-profile owner on pull requests. Cache archives, signing seeds,
and prepared image tags are transient schema-N/A implementation data and are never product
artifacts. Concurrent jobs may race to export the same scope; content addressing makes either
result usable, and no check consumes another live job's output.

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

The hosted image cache is a follow-on consumer-complete capability. Its preparation helper,
prepared-image admission, workflow build owner, owner regressions, and cache-publication path must
land together: splitting them would either expose private signing material to ad hoc shell or build
the image twice. It does not change the installed image contract or qualify fewer behaviors.

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
| Executable application or ordinary script change | classifier and preflight | hosted scope with owner before Align build and hosted graph |
| Fresh-image, workflow, classifier, Makefile, or pin change | classifier and preflight | fresh-image scope with focused once, installed once, required Docker, and `DOCKER_HOST` absent |
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
| Runtime materialization success, aliases, cycles, and failure | materialization helper and Dockerfile | deterministic traversal preserves bytes and modes, removes all symlinks, omits dangling links and directory cycles, maps every repeated resolved regular-file identity to one target inode, and produces the same logical digest tree as independent copies; an existing target or unsupported entry fails nonzero; the Dockerfile continues to materialize Git, Rust, bubblewrap, and LLVM before manifest generation |
| Apt package vector; archive key, hit, miss, corruption, repair, cleanup, and branch scope | apt helper and check workflow | one-line Debian-name grammar, non-empty/duplicate rejection, key normalization, and missing-input rejection; a clean hit requires a bijection between strict manifest basenames and regular non-symlink archives before checksum and invokes neither apt nor the repository; duplicate, missing, extra, absolute, nested, traversal, symlink, truncated, corrupt, or unconfigurable sets are rejected and repaired before the authoritative no-removal signed install; a newly resolved set and the post-consumer candidate must pass the same exact verifier; repository suite fallback and exactly one pinned primary key fail closed; regular files, non-directory parents, and dangling-symlink collisions at every fixed global target remain caller-owned and are rejected before dpkg, apt, network, or fixed-path mutation; repository retry accepts only invocation-owned partial key, source, and directory state and can recover when a later probe succeeds; an invocation-created keyring directory is removed after its key; main/repository/key/config/work cleanup precedes archive retention, and injected cleanup failure attempts archive removal and exits nonzero; miss-then-hit round trip succeeds; pull requests never save; an exact reused `main` miss runs the real hosted consumer, reverifies the candidate, saves, confirms the exact key, and requires literal `cache-hit=true`; cache-miss failure, cache-feature unavailability, false output, and missing output all fail publication; a `main` hit skips unused installation |
| Hosted compiler bundle construction, hit, miss, invalidation, cleanup, and branch scope | compiler-bundle helper and check workflow | exact identity/key rows; existing target rejection; clean exact external checkout; regular source files and resolved LLVM SONAME; private sibling staging; exact four-file inventory; canonical schema and field/file order; size/mode/checksum rejection; no symlink or extra entry; admitted compiler version and exact bundled LLVM loader resolution; partial copy/manifest/verify/rename cleanup; a miss creates before and is consumed by the full hosted graph; a hit skips apt, Rust, checkout, and build; pull requests never save; main reverifies, saves, exact-lookups, and requires literal hit; cache miss, feature unavailability, false output, and missing output fail publication; invalid exact hits fail closed; independent jobs share only immutable entries |
| Build cache hit, miss, invalidation, export outage, and branch scope | Buildx workflow | a hit reuses all content-identical layers but rebuilds the random-key layer; a miss or invalidated layer builds from source; export failure is non-fatal; exact fresh-image merges publish `main` cache without repeating functional qualification; PR caches never become trusted `main` cache. Cache-service import transport failure is N/A as an independent fallback boundary because the job already depends on the same Actions service for checkout, event, and step execution. |
| Pinned Align source setup | preflight, qualification runner, image smoke, workflow, and Dockerfile regression | explicit full source propagates to the installed owner and is cloned without hardlinks; checked-out identity is exact; shallow/promisor source is not admitted; CI caches the immutable full source by revision; only the non-worker Cargo-cache layer uses an exact depth-1 filtered fetch |
| Boundary profile on `cgroupfs` or `systemd` | image smoke | exact allowed environment reaches `fresh-supervise`; missing, malformed, relative, or extra inputs retain deterministic precedence |
| Owner success/failure | qualification runner | start/terminal records contain owner, status, and non-negative duration; failure propagates |
| Pull request, workflow dispatch, direct/non-merge push, unusable event base | workflow plus classifier test | reuse is false; exact event refs or fail-closed all-gate selection; local and hosted inventories cannot drift |
| Exact GitHub merge commit after a successful PR run | reuse selector plus both workflow jobs | event after is the checked-out two-parent merge; before and parent merge base are parent 1; merge tree equals parent 2 tree; one associated merged PR binds repository, base, head, and merge; the uniquely identified latest successful `ci.yml` PR run contains both successful required jobs and both exact PR/base/head evidence steps; both merge-push jobs report reuse and skip normal gates except that a missing trusted apt entry executes its same-snapshot hosted consumer before publication |
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

PR #75 run `31588797654` passed the invalidating hosted path in 568 seconds end to end; the fresh
job took 564 seconds, its build/export/load step 293 seconds, and installed qualification 225
seconds (`n=1`, GitHub `ubuntu-24.04`). The build produced the new downstream layers in about 68
seconds, exported and loaded them in 121.5 seconds, and exported the pull-request cache in 103.2
seconds. Merge run `31589611628` then published the smaller trusted `main` cache in a 183-second
fresh job while reusing functional and qualification evidence. These are migration/cache-publication
measurements, not the clean warm-image result.

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
argument behavior without root, apt, or network access. `scripts/test-development-preflight` owns
the exact package request, action pins, restore/install/save routing, and the prohibition on the
old `llvm.sh` installer. Hosted CI remains the acceptance owner for the real Ubuntu repository,
GitHub cache service, and runner-image identity.

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
