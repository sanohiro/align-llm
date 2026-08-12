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
| `python3 scripts/run-fresh-image-profile-smoke [--prepared-image IMAGE --image-signing-seed PATH --run-signing-seed PATH]` | With none of the prepared-image arguments, generate per-run signing seeds and build the image locally as before. With all three, validate the generated tag and two private regular 32-byte seed files before Docker side effects, use the already loaded image without rebuilding it, and run the unchanged attestation, lifecycle, trust-mutation, boundary, and worker-aggregate qualification. Partial prepared-image input is rejected. The image owner removes the loaded image and all Docker state on success or failure; the preparation owner retains seed-directory cleanup. |
| `python3 scripts/select-ci-reuse --event-name NAME --event-path PATH --repository OWNER/REPO --api-url URL [--github-output PATH]` | Select reuse only for a `push` to `refs/heads/main` whose checked-out commit has exactly two parents, whose first parent equals the event `before` SHA, whose first parent is the merge base of the two parents, and whose tree equals the second-parent tree. Through the GitHub API, require exactly one associated merged pull request whose base, head, merge commit, repository, and `main` ref equal those Git identities. Then require the uniquely identified latest successful `pull_request` run of `.github/workflows/ci.yml` at that exact second-parent head. Both required jobs must have completed successfully in the same run, and each must contain one successful API-visible step whose name binds that merged pull-request number, base SHA, and head SHA. Print a stable JSON record and optional GitHub output rows. Every malformed event, Git/API/read error, truncated response, recursion failure, pagination or latest-run ambiguity, missing field, identity mismatch, direct push, non-merge commit, missing job or evidence step, or non-success result selects `reused=false`; it never fails the workflow or suppresses verification. The token is read only from `GITHUB_TOKEN` and never printed or persisted. |
| Installed fresh-image source setup | Reuse the explicit full-history `.align-revision` checkout already built by local preflight, or clone the remote when no checkout is supplied. Clone without hardlinks into the disposable profile source, verify the checked-out identity, and preserve the FRESH-WORKER prohibition on shallow, promisor, alternate-object, and replacement-object repositories. The Docker build's Cargo-cache-only source may use an exact depth-1 filtered fetch because it is never admitted as worker source. Reconstruct the exact boundary environment before `fresh-supervise` on both supported cgroup drivers so Docker-injected variables cannot change validation precedence. |
| GitHub Actions | On each job, first evaluate exact merged-PR reuse. Every pull-request job finishes with an API-visible evidence step whose name contains the event's pull-request number, base SHA, and head SHA. When both merge-push jobs independently select the same valid reviewed head evidence and find that exact successful binding step in both source jobs, report reuse and skip functional verification. Otherwise resolve event refs, invoke the shared classifier, run documentation/static checks only for `docs_only`, run the compiler and hosted graph only for `hosted`, and run focused plus installed-image qualification only for `fresh_installed`. Workflow dispatch, direct push, non-exact merge, unavailable evidence, or an unusable event base runs the normal gates. The installed step uses `--installed-profile-only`, so focused qualification executes exactly once per executing job. Its full Align source cache is keyed by `.align-revision`; every restored checkout is revalidated before use. For `fresh_installed`, a commit-pinned Docker Buildx action builds the exact per-run-keyed image with `pull` enabled, imports the branch-visible GitHub Actions cache under schema scope `align-llm-fresh-image-v1`, and exports a complete cache with export errors ignored. Pull requests and non-reused runs load the image for qualification; exact merge pushes with reused functional evidence publish cache without loading the multi-gigabyte image into the daemon. A cache miss performs the same build from source. Exact merges publish the cache on `main`, making the trusted default-branch cache readable by later pull requests without repeating product qualification. Signing material is always prepared anew and cleaned in an `always()` step. Workflow permissions remain read-only and add only `actions: read` and `pull-requests: read` for the evidence queries; the cache service uses the run-scoped Actions credential and no registry or package write. |

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

GitHub cache access is branch-scoped. Pull requests may read the trusted `main` cache and their own
cache but cannot publish into `main`; an exact merge therefore builds and publishes cache state
even when its already-passing functional checks are reused. Cache data is only a BuildKit
optimization: content digests are verified by BuildKit, a miss builds from source, an export
failure does not fail an otherwise valid build, and the loaded image still passes the
complete attestation and installed-profile owner on pull requests. Cache archives, signing seeds,
and prepared image tags are transient schema-N/A implementation data and are never product
artifacts. Concurrent jobs may race to export the same scope; content addressing makes either
result usable, and no check consumes another live job's output.

The implementation, regression, CI adoption, documentation, and timing records form one
consumer-complete capability. The candidate is roughly 1,200 changed hand-written lines because
the shared classifier must be adopted by both local preflight and both CI jobs, and the installed
runner must expose the non-duplicating mode before either consumer can use it. Splitting those
pieces would leave an unused producer or retain a second path inventory and would make drift more,
not less, likely during integration.

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
| Build cache hit, miss, invalidation, export outage, and branch scope | Buildx workflow | a hit reuses all content-identical layers but rebuilds the random-key layer; a miss or invalidated layer builds from source; export failure is non-fatal; exact fresh-image merges publish `main` cache without repeating functional qualification; PR caches never become trusted `main` cache. Cache-service import transport failure is N/A as an independent fallback boundary because the job already depends on the same Actions service for checkout, event, and step execution. |
| Pinned Align source setup | preflight, qualification runner, image smoke, workflow, and Dockerfile regression | explicit full source propagates to the installed owner and is cloned without hardlinks; checked-out identity is exact; shallow/promisor source is not admitted; CI caches the immutable full source by revision; only the non-worker Cargo-cache layer uses an exact depth-1 filtered fetch |
| Boundary profile on `cgroupfs` or `systemd` | image smoke | exact allowed environment reaches `fresh-supervise`; missing, malformed, relative, or extra inputs retain deterministic precedence |
| Owner success/failure | qualification runner | start/terminal records contain owner, status, and non-negative duration; failure propagates |
| Pull request, workflow dispatch, direct/non-merge push, unusable event base | workflow plus classifier test | reuse is false; exact event refs or fail-closed all-gate selection; local and hosted inventories cannot drift |
| Exact GitHub merge commit after a successful PR run | reuse selector plus both workflow jobs | event after is the checked-out two-parent merge; before and parent merge base are parent 1; merge tree equals parent 2 tree; one associated merged PR binds repository, base, head, and merge; the uniquely identified latest successful `ci.yml` PR run contains both successful required jobs and both exact PR/base/head evidence steps; both merge-push jobs report reuse and skip all normal gates |
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
