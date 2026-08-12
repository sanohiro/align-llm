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
| Installed fresh-image source setup | Reuse the explicit full-history `.align-revision` checkout already built by local preflight, or clone the remote when no checkout is supplied. Clone without hardlinks into the disposable profile source, verify the checked-out identity, and preserve the FRESH-WORKER prohibition on shallow, promisor, alternate-object, and replacement-object repositories. The Docker build's Cargo-cache-only source may use an exact depth-1 filtered fetch because it is never admitted as worker source. Reconstruct the exact boundary environment before `fresh-supervise` on both supported cgroup drivers so Docker-injected variables cannot change validation precedence. |
| GitHub Actions | Resolve event refs, invoke the shared classifier, run documentation/static checks only for `docs_only`, run the compiler and hosted graph only for `hosted`, and run focused plus installed-image qualification only for `fresh_installed`. Workflow dispatch or an unusable event base selects all gates. The installed step uses `--installed-profile-only`, so focused qualification executes exactly once per job. Its full Align source cache is keyed by `.align-revision`; every restored checkout is revalidated before use. |

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
| Pull request, push, workflow dispatch, unusable event base | workflow plus classifier test | exact event refs or fail-closed all-gate selection; local and hosted inventories cannot drift |

The workflow regression loads the production classifier as a module, crosses every path class and
failure class above, checks plan ordering and environment isolation, and statically confirms that
CI invokes the shared classifier and installed-only qualification. The existing focused fresh
owners continue to test their product contracts; this capability does not duplicate them.

## Acceptance and measurement

Required owner command:

```text
python3 scripts/test-development-preflight
```

Before merge, run the local preflight when the pinned Align checkout is available without modifying
the paused Request 6 branch. The hosted CI jobs are final environment evidence. Compare the next
fresh-image capability's number of diagnostic pushes and repeated focused executions with PR #61
and PR #69. A 2026-08-12 local baseline reached 681.372 seconds before exposing the existing
`cgroupfs` environment leak; its boundary phase took 435.077 seconds and its image build took
195.235 seconds. Exact shallow source reduced the boundary phase to 86.945 seconds but was
correctly rejected by the worker's full-history source contract, so it is not an adopted result.
The valid exact shallow optimization for the Docker-only Cargo source reduced the image build to
144.999 seconds. The complete installed profile with reused full source must pass before this
candidate claims an end-to-end improvement; hosted results remain the cross-environment evidence.
