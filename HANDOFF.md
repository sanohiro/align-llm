# Session handoff

Read `CLAUDE.md` first. This file records durable capability state; GitHub owns transient pull
request checks, reviews, findings, and attestations.

## Current state

- Branch: `agent/fresh-worker-capability`, based on `origin/main` merge commit
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18` (PR #60).
- Relevant review-repair checkpoint: `366dc3d02452c1775b2b97d307ebcdeba155c586`. Subsequent
  non-evaluation commits may contain installed-profile fixes or durable checkpoint corrections; use
  the latest non-evaluation source commit and its valid oracle/finalization descendants recorded by
  the pull request before merge.
- Active goal: complete, review, and merge the consumer-complete FRESH-WORKER capability. The user
  requested that execution stop after this pull request merges; do not start the next roadmap item.
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
  `/proc/self/fd/...` view because bwrap has no overlay-fd option. Post-overlay fd-bind operations
  retain those descriptors through setup and a tmpfs hides their holding mounts before the payload.
  Payloads still inherit no worker descriptors. Cleanup distinguishes stable root identity from normal owned-directory metadata
  changes.
- The original source/oracle/finalization history exists at `8eafdecf24caa7cd9c5c119f08335a77f0972759`,
  `4510138117e1fd612295256ba91f21361b84c3c5`, and
  `ce8a2ab1d42cef33fbbbf8b77893ac57268ff696`. The review repair changes recorded inputs. Merge only
  from a head whose latest non-evaluation source/checkpoint commit is followed by an oracle-only
  commit and a finalizer-only commit; older tuples remain historical ancestors, not merge evidence.

## Next actions

1. If the current source/checkpoint commit does not yet have its final oracle-only and
   finalizer-only descendants, run the Section 2.4 pending measurement and create them. Otherwise,
   do not repeat the measurement.
2. Push the replacement history to the existing capability pull request, record finding
   dispositions, obtain fresh installed Ubuntu 24.04 FRESH-IMAGE/FRESH-WORKER evidence, and merge
   with a merge commit only after every required check passes.
3. After merge, perform the bounded retrospective, remove the temporary diagnostic branch/worktree,
   and stop. Leave the next eligible roadmap capability unstarted.

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
  descriptor-backed mount admission.
- Local bubblewrap 0.11.0 descriptor-bind smoke: PASS. A direct aggregate-shaped overlay smoke using
  retained lower/upper/work descriptors through bwrap's own `/proc/self/fd` view read the lower tree
  and published the expected upper-layer file.
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
  A first descriptor repair reached the image self-test but showed that bwrap closes descriptors not
  registered in its operation table before overlay setup. The revised ordering registers each
  overlay descriptor with a post-overlay read-only fd-bind and hides the holding mounts before the
  payload; fresh hosted evidence for that repair is pending.
  The dedicated hosted profile check must supply fresh installed-platform evidence after push.

## Blockers and decisions

- No implementation blocker is known. Local Docker unavailability is an execution condition, not a
  design blocker; hosted Ubuntu 24.04 owns the required installed-profile evidence.
- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; this capability does
  not adopt a new Align surface.
- FRESH-WORKER remains one capability because private admission, two namespaces, the compiler bundle,
  Make interposition, cache/image completion, and the first real consumer aggregate are not useful or
  reviewable as independently shipped helper surfaces.
- The pull request must use a merge commit so the implementation source, immutable oracle, and
  canonical finalization commits remain ancestors of the exact merged head.
- The separate primary worktree has intentional uncommitted state; do not discard or overwrite it
  while this clean worktree is active.
