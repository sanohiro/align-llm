# Session handoff

Read `CLAUDE.md` first. This file records durable capability state; GitHub owns transient pull
request checks, reviews, findings, and attestations.

## Current state

- Branch: `agent/fresh-worker-capability`, based on `origin/main` merge commit
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18` (PR #60).
- Open pull request: #61 (`agent/fresh-worker-capability`); the branch is not merged and must
  remain merge-commit-only. The latest product/evaluation commit before this handoff is
  `81f80e94958876c5c4f9105be3589f395834cbb0`.
- Current baseline tuple: source/checkpoint
  `7bc459df4c5b34cbdd9b6e44b49b34dbeacd79d5`, oracle
  `4128b5aaa67f379f1cb8bae837d273dd7a3c4144`, finalization
  `4721da16435494b73b98e5f187a6adba6656d0ee`.
- Relevant review-repair checkpoint: `366dc3d02452c1775b2b97d307ebcdeba155c586`. Subsequent
  non-evaluation commits may contain installed-profile fixes or durable checkpoint corrections; use
  the latest non-evaluation source commit and its valid oracle/finalization descendants recorded by
  the pull request before merge.
- Active goal: complete, review, and merge the consumer-complete FRESH-WORKER capability, then
  continue with the next eligible roadmap item as requested by the user.
- In progress: the repository worker now cryptographically re-verifies the sealed Ed25519/DSSE
  invocation and image-manifest tuple,
  captures separate project/Align Git identities, admits one protected private root, materializes
  source/tool/runtime/offline-cache inputs, builds the pinned compiler in a first bwrap namespace,
  installs a descriptor/guard/compiler/archive bundle, and launches `capable-checks` through a
  writable overlay in a second namespace. Make and evaluation consumers use the fresh launcher,
  namespace-owned temporary root, nested staged tools, and private baseline Git view. The installed
  image now seeds the authenticated Cargo cache at the pinned Align revision, and its profile smoke
  contains the real no-network aggregate path. The cache manifest derives its cardinality and byte
  totals from that populated seed. Review repair additionally rejects local Git helpers
  before source queries, retains and rechecks Git/common/ref/index/object identity, streams source
  and child output under bounds, kills and reaps the complete cgroup, and makes staging and cleanup
  descriptor-relative so a replacement root is never deleted.
  Installed-profile source admission now reopens the supervisor's retained `O_PATH` project root as
  a no-follow scan-capable descriptor, gives Git worker-owned `/proc/<worker-pid>/fd/...` paths that
  remain valid if Git closes inherited nonstandard descriptors, and normalizes Git tree records to
  raw-path byte order before manifest construction. Runtime-tree validation accepts stable
  distribution hardlinks under full before/after identity and byte-digest checks, while Cargo-cache
  regular files retain their separate single-link requirement. Private build/aggregate mount
  sources are opened relative to the retained private-root descriptor. Ordinary mounts use bwrap
  `--bind-fd`/`--ro-bind-fd`; the three overlay operands use only the bwrap process's own
  `/proc/self/fd/...` view because bwrap has no overlay-fd option. The bwrap-only forwarder preserves
  only mount descriptors named by setup options; post-overlay fd-bind operations make bwrap consume
  the three overlay descriptors, and a tmpfs hides their holding mounts before the payload.
  Payloads still inherit no worker descriptors. Cleanup distinguishes stable root identity from normal owned-directory metadata
  changes. The installed build diagnostic then showed that Rust's target linker receives driver
  arguments (`-Wl,...`, `-m64`, and `-B...`) that the raw `ld.lld` entry point rejects. The worker
  now uses the authenticated `/tools/cc` Clang driver for the Rust target linker; the raw linker
  remains selected only by Clang's fixed `-fuse-ld` path. The next installed diagnostic showed that
  Clang then needed `crtbeginS.o`, `crtendS.o`, and `libgcc_s`; the image now authenticates and
  mounts only the GCC startup/runtime support tree at `/usr/lib/gcc/x86_64-linux-gnu`, without a
  GCC driver or host executable search path. The following diagnostic confirmed GCC 13 was selected
  and exposed the next missing linker input, `-lzstd`; the image now installs `libzstd-dev` so the
  authenticated `/usr/lib/x86_64-linux-gnu` tree contains its declared development symlink.
- The original source/oracle/finalization history exists at `8eafdecf24caa7cd9c5c119f08335a77f0972759`,
  `4510138117e1fd612295256ba91f21361b84c3c5`, and
  `ce8a2ab1d42cef33fbbbf8b77893ac57268ff696`. The review repair changes recorded inputs. Merge only
  from a head whose latest non-evaluation source/checkpoint commit is followed by an oracle-only
  commit and a finalizer-only commit; older tuples remain historical ancestors, not merge evidence.

## Next actions

1. Push the refreshed source/oracle/finalization tuple to PR #61 and obtain fresh pinned and
   installed Ubuntu 24.04 evidence. Hosted checks own the installed-platform evidence because the
   local Docker endpoint is unavailable.
2. Run one fresh independent adversarial review of the complete PR diff, record the SHA-bound review
   envelope and all finding dispositions, and apply any valid findings in one consolidated repair.
   Rerun only affected checks unless the repair materially changes the reviewed contract.
3. Mark the PR ready, verify the final head, base tip, required checks, ancestry, and merge method,
   then merge PR #61 with a merge commit only.
4. After merge, perform the bounded retrospective, refresh the main/worktree state without
   discarding intentional local changes, and start the next eligible roadmap gate.

## Latest verification

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS, batching the
  attestation/manifest/image-control owners, worker unit cases, topology oracle, and the complete
  Section 9.10 focused-case inventory. Manifest cases include a populated generated Cargo-cache
  tree. Worker cases include forged signatures, supervisor replay, Git helper and alternate
  rejection, packed/linked Git identity, source/common-dir replacement, bounded streams, and
  replacement-root cleanup authority.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-gate-topology --self-test`: PASS.
- `ALIGNC=../align/target/release/alignc PYTHONDONTWRITEBYTECODE=1 make hosted-checks`: PASS.
- `ALIGNC=../align/target/release/alignc PYTHONDONTWRITEBYTECODE=1 make eval-coding`: PASS, including
  invalid, Git-configuration, timeout, namespace, resource, mutation, and descendant cleanup smokes.
- `git diff --check`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-unit-smoke`: PASS after exercising the
  supervisor-equivalent `O_PATH` root, a Git-tree/raw-byte ordering inversion, and private
  descriptor-backed mount admission; the Rust linker contract requires `/tools/cc`.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS after the image
  contract check for the authenticated GCC startup/runtime support tree.
- Local bubblewrap 0.11.0 descriptor-bind smoke: PASS. A direct aggregate-shaped overlay smoke using
  retained lower/upper/work descriptors through bwrap's own `/proc/self/fd` view read the lower tree
  and published the expected upper-layer file.
- `python3 scripts/run-fresh-image-control-smoke`: PASS, including compilation and execution of the
  bwrap-only forwarder with three recognized mount descriptors preserved and an unrecognized
  descriptor after `--` closed at target exec.
- Hosted diagnostic run `31063159443`: Pinned checks PASS; Installed image build and bwrap
  self-test passed, and the aggregate failure was traced to cleanup attempting to remove the
  read-only staged Git `refs/tags` directory (`PermissionError: [Errno 13] Permission denied`).
- Source fix `1120e7e` restores directory write access before descriptor-relative cleanup and adds a
  read-only nested-directory regression. Local worker qualification and baseline checks pass.
- Diagnostic run `31064929389`: Pinned checks PASS; Installed image build and bwrap self-test
  passed, and the aggregate failure was traced to the runtime manifest's `kind: tree` being
  interpreted as a regular file by private mount admission. Source fix `4e71ecd` accepts `tree` as
  a directory kind and adds a direct regression. Local worker qualification passes.
- Diagnostic run `31066038115`: Pinned checks PASS; Installed image build and bwrap self-test
  passed through the compiler build, then exposed the exact derived paths and Rust linker argv.
  The raw `ld.lld` target rejected driver options and could not resolve the `-l...` inputs; source
  fix `11c07ae` selects `/tools/cc` and updates the Section 9.5 contract with a linker-entry
  regression. Local worker unit and focused qualification pass.
- Diagnostic run `31067093178`: Pinned checks PASS; `/tools/cc` was accepted and the build reached
  Clang, which exposed missing `crtbeginS.o`, `crtendS.o`, and `libgcc_s` support. Source fix
  `81f80e9` stages `/usr/lib/gcc/x86_64-linux-gnu` as an authenticated runtime binding and adds
  a static image-contract regression. Diagnostic run `31068073929` then confirmed GCC 13 was
  selected and exposed the next missing `-lzstd` linker input; the product repair is in progress.
- `make baseline-check`: PASS, including canonical verification, invalid-input rejection, and
  failure-retention smoke tests for the current tuple above. Hosted checks for the pushed head
  remain pending.
- Installed image build/E2E: not run locally because the Docker daemon at the configured endpoint is
  unavailable. Hosted attempts identified and fixed the cache seed's explicit `RUSTC` input, raw-mode
  normalization, populated-tree count derivation, and the installed job's incorrect assumption that
  a sibling Align checkout exists. The profile now obtains the pinned Align source from its canonical
  repository before entering the no-network worker boundary. Installed diagnostics also showed that
  Git could not reopen an inherited config memfd through its procfs view; admission now feeds the
  already retained config bytes through Git's documented stdin path. A later installed run showed
  that Git closes inherited nonstandard descriptors before repository lookup and that the admitted
  root is intentionally `O_PATH`; the worker now supplies worker-owned descriptor paths, reopens a
  scan-capable root without pathname resolution, and raw-byte sorts Git tree records. That source
  admission then exposed a policy leak in the next phase: the cache single-link rule was also being
  applied to installed runtime trees containing legitimate distribution hardlinks. Runtime reads
  now preserve and compare link count without requiring one; cache reads still reject hardlinks.
  Private staging then exposed an over-strict cleanup comparison that treated normal directory
  timestamp changes as replacement; cleanup now uses the retained worker identity contract. The
  next installed diagnostic proved that a new bwrap user namespace cannot traverse the parent
  worker's procfs descriptor paths. Mount sources now cross that boundary as retained descriptors.
  Descriptor diagnostics proved every mount fd present immediately before the authenticated tool
  forwarder, then missing in bwrap. The forwarder was closing all nonstandard descriptors before
  executing its target. Its bwrap-only mode now marks all such descriptors close-on-exec, parses the
  fixed setup argv before `--`, and clears the flag only for recognized bind and overlay mount fds;
  the bwrap setup then consumes every preserved descriptor before the payload. The image retains its
  v0.11.2 pin `1b80120ef26a28e065e67f89bfef873f13bdd317`. Hosted run `31020180770`
  reproduced the opaque failure and diagnostic run `31020913056` exposed the forwarder close; fresh
  hosted evidence for the repair is pending.
  The dedicated hosted profile check must supply fresh installed-platform evidence after push.

## Blockers and decisions

- No implementation blocker is known. Local Docker unavailability is an execution condition, not a
  design blocker; hosted Ubuntu 24.04 owns the required installed-profile evidence.
- Fresh hosted installed-profile evidence for the GCC runtime-support and `libzstd-dev` repair is
  pending after push. No implementation blocker is known; the cleanup, runtime-tree, linker-driver,
  startup-runtime, and zstd-linker failures each have evidence-backed fixes and local regression
  coverage.
- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; this capability does
  not adopt a new Align surface.
- FRESH-WORKER remains one capability because private admission, two namespaces, the compiler bundle,
  Make interposition, cache/image completion, and the first real consumer aggregate are not useful or
  reviewable as independently shipped helper surfaces.
- The pull request must use a merge commit so the implementation source, immutable oracle, and
  canonical finalization commits remain ancestors of the exact merged head.
- The diagnostic branch/worktree `agent/fresh-worker-aggregate-diagnostic` /
  `/tmp/align-llm-fresh-aggregate-diagnostic` is intentionally retained for hosted aggregate
  diagnostics through commit `bc7ab2c`; its changes must not enter PR #61. The older
  `agent/fresh-worker-diagnostic` worktree is also intentionally retained for historical FD-boundary
  evidence until the PR is resolved.
- The separate primary worktree has intentional uncommitted state; do not discard or overwrite it
  while this clean worktree is active.
