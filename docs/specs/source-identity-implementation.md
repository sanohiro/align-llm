# Source identity implementation slice

Section 9.3 of `docs/specs/check-gate-topology.md` remains the only normative public
contract. This document is the implementation checkpoint and closure record for its
source-identity slice; it does not introduce a second wire format or relax a Section 9
requirement.

## Scope and ownership

`scripts/fresh_source_identity.py` owns the descriptor-relative, read-only source gate:

- lexical resolution from a retained project-root descriptor;
- retained no-follow descriptors and identity snapshots for each worktree, root Git
  control entry, Git directory, common directory, `HEAD`, every loose symbolic-ref
  component or the selected `packed-refs`, index, and object store;
- the fixed Git child environment, explicit descriptor inheritance, and post-child
  descriptor rechecks;
- project capsule identity, Align revision and SHA-1-only policy, Git tree/index
  identity, clean-worktree policy, raw filesystem enumeration, contained symlink proof,
  exception metadata, and comparison with `fresh_source`'s canonical manifest;
- bounded recheck of the retained identities before the caller proceeds.

This slice does not own private-root admission, source/cache copies, bwrap, Cargo, Make,
process ownership, status output, or cleanup. Those are later slices and must consume an
accepted `SourceIdentityHandle` rather than re-resolve a pathname.

## Public implementation contract

| Surface | Contract |
| --- | --- |
| `open_relative_directory(root_fd, relative)` | Return an owned final directory descriptor. Reject absolute, empty, `.`, invalid, or escaping components. Walk with `O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`; permit `..` only within the retained ancestor chain. The caller's descriptor is borrowed and remains open. |
| `capture_project_source(root_fd, expected_head, expected_object_format)` | Duplicate the borrowed root, retain all required descriptors, validate root exceptions and fixed Git policy, require exact capsule `HEAD`/object-format equality, and return an owned `SourceIdentityHandle`. |
| `capture_align_source(project_root_fd, align_repo_relative, expected_revision)` | Resolve the signed relative sibling from the retained project parent, require the controller-supplied revision to be exactly lowercase 40-hex, reject SHA-256, require matching SHA-1 `HEAD`, and return an owned handle. The later worker-input slice owns reading the one-line `.align-revision` file before either capture. |
| `SourceIdentityHandle.identity` | Immutable `SourceIdentity` containing source kind, revision, tree, object format, index digest, canonical source manifest bytes/digest, exception metadata, and retained-descriptor snapshots. |
| `SourceIdentityHandle.recheck()` | Reconstruct and compare the complete identity from retained descriptors. Reject any source, Git-control, ancestor, object, index, exception, or descriptor change before materialization. |
| Errors | Raise a stable source-identity exception category with no cause/context chain and without paths, raw source bytes, environment values, credentials, Git child output, or errno text. Validation order follows Section 9.9's source phases. |
| Bounds | Reuse Section 9's 200,000-entry, depth-64, 64-MiB raw path/link, 512-MiB file, 4-GiB source/index, and 2,048-byte symlink bounds. Packed refs are capped at 64 MiB, Git policy output at 4 MiB, and tree/index-list output at 192 MiB, which covers the declared entry/path product; output beyond a cap rejects. |

Borrowed descriptors are never closed. Returned handles own every duplicate and close each
owned descriptor exactly once; close is idempotent and use after close is rejected. Git
children use `cwd=/proc/self/fd/<worktree>`, descriptor-backed `GIT_WORK_TREE`, `GIT_DIR`,
and `GIT_COMMON_DIR`, `close_fds=True`, and only the retained descriptors in `pass_fds`.
Ambient `GIT_*`, caller config, replacement refs, alternates, grafts, shallow/promisor
state, fsmonitor, hooks, filters, bare repositories, and `core.worktree` are rejected or
cleared before object lookup. The accepted full commit ID, never the mutable token `HEAD`,
is used for every tree and index comparison after the retained HEAD/ref equality check.
No Git child runs after source materialization begins.

This slice is larger than the usual 1,000-line review target because splitting resolver/Git
descriptor ownership from raw enumeration and `SourceIdentityHandle.recheck()` would publish an
acceptance result that cannot yet prove its own retained identity. The implementation remains one
read-only vertical gate with one public handle; private-root creation, copying, process behavior,
and Make integration stay out of scope.

## Closure matrix

| Area | Owner and regression evidence |
| --- | --- |
| Root ownership and relative resolver | `fresh_source_identity.py`; ordinary and linked roots, retained `..` traversal, absolute/empty/dot/symlink/missing rejection, root-path replacement, borrowed-fd survival, and closed-handle rejection in `run-fresh-source-identity-smoke`. |
| Descriptor lifetime and ABA | The smoke asserts a stable process fd count, idempotent close, caller-fd retention, same-byte file/root replacement rejection, and exact no-leak failure cleanup for missing `HEAD`, index, objects, and malformed linked `commondir`. Fine-grained private-copy mutation cases remain owned by the later materialization slice. |
| Ordinary and linked `.git` | Fixtures cover directory and exact linked-worktree `gitdir: <path>\n`/`commondir` forms, loose and packed symbolic refs, in-place ordinary/linked/packed ref races, linked Git-control mutation, common-directory mutation, retained worktree/index/common/object descriptors, and both root-control metadata forms. |
| Fixed Git boundary | Tests inject ambient Git/config state and reject filters, fsmonitor, hooks, `core.worktree`, partial-clone configuration, packed replacement refs, alternates, shallow metadata, and promisor packs while proving caller configuration is ignored. |
| Project and Align identities | Tests cover project HEAD/object-format mismatch, SHA-1 and SHA-256 project repositories, exact Align pin mismatch, SHA-256 Align rejection, staged/dirty/untracked input, and assume-unchanged/skip-worktree flags. The controller-owned raw `.align-revision` read remains in the later worker-input slice. |
| Raw enumeration and modes | Tests cover raw ordering, parent directories, regular/executable files, directories, symlinks, raw-to-staged mode mapping, tracked hard links, nested `.git`, case-fold collisions, target/main output rules, entry/depth/path-link/file/total/symlink/index/Git-output cap rejection, and identical manifest bytes for absent/present output exceptions. |
| Git object semantics | Tests independently hash directory/tree, regular-file/blob, and symlink/blob objects from both supported object formats and reject missing, wrong-type, wrong-size, or wrong-ID objects. |
| Symlink identity | Tests cover contained relative chains, absolute/escaping/cyclic/untracked targets, target replacement, and proof before acceptance. |
| Manifest and recheck | Tests load the reviewed module and its local wire dependencies from exact source bytes, prove a timestamp-valid stale cache is ignored, preserve the caller cache snapshot, parse canonical bytes, compare output-exception identity, prove the index is never eagerly read, retain raw index and descriptor snapshots, rerun the complete accepted identity, reject content/mode/inode/Git-policy/index/ref/root changes, and verify public exceptions have no cause, context, hostile path, or errno traceback. |
| Deferred surfaces | Private root, source/cache materialization, Cargo configuration, bwrap, Make, process, status, and cleanup are explicitly deferred to their named later slices. |

## Acceptance

The focused gate is:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-source-identity-smoke
```

It must prove ordinary and linked worktrees, all source exceptions, mutation rejection,
descriptor closure, and no caller-tree mutation. `git diff --check`, Python syntax checking,
the existing source-manifest wire smoke, and `make ci` apply to this implementation gate.
Image installation and capable fresh-image acceptance are `N/A` until the later worker/build
boundary; this slice does not alter the Make graph, compiler pin, or adoption contract.
