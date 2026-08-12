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
| `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker [--align-repo PATH]` | Verify the qualification inventory, skip the already-owned focused commands, and run only the installed profile. `--installed-profile` retains the complete focused-plus-installed capability gate. `--require-docker` turns an unavailable Docker daemon into failure instead of a skip. `--align-repo` forwards an explicit full pinned checkout to the image owner. Every invoked owner emits one start and one terminal timing record. |
| `python3 scripts/select-ci-reuse --event-name NAME --event-path PATH --repository OWNER/REPO --api-url URL [--github-output PATH]` | Select reuse only for a `push` to `refs/heads/main` whose checked-out commit has exactly two parents, whose first parent equals the event `before` SHA, whose first parent is the merge base of the two parents, and whose tree equals the second-parent tree. Through the GitHub API, require exactly one associated merged pull request whose base, head, merge commit, repository, and `main` ref equal those Git identities. Then require the uniquely identified latest successful `pull_request` run of `.github/workflows/ci.yml` at that exact second-parent head. Both required jobs must have completed successfully in the same run, and each must contain one successful API-visible step whose name binds that merged pull-request number, base SHA, and head SHA. Print a stable JSON record and optional GitHub output rows. Every malformed event, Git/API/read error, truncated response, recursion failure, pagination or latest-run ambiguity, missing field, identity mismatch, direct push, non-merge commit, missing job or evidence step, or non-success result selects `reused=false`; it never fails the workflow or suppresses verification. The token is read only from `GITHUB_TOKEN` and never printed or persisted. |
| Installed fresh-image source setup | Reuse the explicit full-history `.align-revision` checkout already built by local preflight, or clone the remote when no checkout is supplied. Clone without hardlinks into the disposable profile source, verify the checked-out identity, and preserve the FRESH-WORKER prohibition on shallow, promisor, alternate-object, and replacement-object repositories. The Docker build's Cargo-cache-only source may use an exact depth-1 filtered fetch because it is never admitted as worker source. Reconstruct the exact boundary environment before `fresh-supervise` on both supported cgroup drivers so Docker-injected variables cannot change validation precedence. |
| GitHub Actions | On each job, first evaluate exact merged-PR reuse. Every pull-request job finishes with an API-visible evidence step whose name contains the event's pull-request number, base SHA, and head SHA. When both merge-push jobs independently select the same valid reviewed head evidence and find that exact successful binding step in both source jobs, report reuse and skip classification and execution. Otherwise resolve event refs, invoke the shared classifier, run documentation/static checks only for `docs_only`, run the compiler and hosted graph only for `hosted`, and run focused plus installed-image qualification only for `fresh_installed`. Workflow dispatch, direct push, non-exact merge, unavailable evidence, or an unusable event base runs the normal gates. The installed step uses `--installed-profile-only`, so focused qualification executes exactly once per executing job. Its full Align source cache is keyed by `.align-revision`; every restored checkout is revalidated before use. Workflow permissions remain read-only and add only `actions: read` and `pull-requests: read` for the evidence queries. |

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
`run-fresh-worker-qualification` inventory remain outside this capability. Cached versus scratch
image construction is a later capability; this change preserves a scratch installed-image build.
Local preflight reuses its already required full pinned checkout, while CI stores that immutable
source under a revision-keyed cache. The Cargo-cache image layer avoids unrelated Align history
without weakening worker source admission.

The implementation, regression, CI adoption, documentation, and timing records form one
consumer-complete capability. The candidate is roughly 1,200 changed hand-written lines because
the shared classifier must be adopted by both local preflight and both CI jobs, and the installed
runner must expose the non-duplicating mode before either consumer can use it. Splitting those
pieces would leave an unused producer or retain a second path inventory and would make drift more,
not less, likely during integration.

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
and retains installed-only qualification. Reuse tests use deterministic event, Git, PR, workflow,
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
