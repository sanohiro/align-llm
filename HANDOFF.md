# Session handoff

Read `CLAUDE.md` first. This file records durable capability state; GitHub owns transient pull
request checks, reviews, findings, and attestations.

## Current state

- Branch: `agent/fresh-worker-capability`, based on `origin/main` merge commit
  `85cbcc969b08ee3a7b844737d36b15744e5a9d18` (PR #60).
- Open pull request: #61 (`agent/fresh-worker-capability`), current head
  `8921d4d3d1fee4c454a1514027a3c620a66bc447`; it is not merged and must remain merge-commit-only.
- Current baseline tuple for this head: source/checkpoint
  `ccb42a79f2392328725c8125aa0662c3825432a5`, oracle
  `36e087c67004dfda54c16f64f236221357c341b1`, finalization
  `8921d4d3d1fee4c454a1514027a3c620a66bc447`.
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
  `/proc/self/fd/...` view because bwrap has no overlay-fd option. The bwrap-only forwarder preserves
  only mount descriptors named by setup options; post-overlay fd-bind operations make bwrap consume
  the three overlay descriptors, and a tmpfs hides their holding mounts before the payload.
  Payloads still inherit no worker descriptors. Cleanup distinguishes stable root identity from normal owned-directory metadata
  changes.
- The original source/oracle/finalization history exists at `8eafdecf24caa7cd9c5c119f08335a77f0972759`,
  `4510138117e1fd612295256ba91f21361b84c3c5`, and
  `ce8a2ab1d42cef33fbbbf8b77893ac57268ff696`. The review repair changes recorded inputs. Merge only
  from a head whose latest non-evaluation source/checkpoint commit is followed by an oracle-only
  commit and a finalizer-only commit; older tuples remain historical ancestors, not merge evidence.

## Next actions

1. Use the retained diagnostic worktree `/tmp/align-llm-fresh-aggregate-diagnostic` and branch
   `agent/fresh-worker-aggregate-diagnostic`. Its current uncommitted file
   `image/fresh/control/fresh_image_control.py` emits the worker's bounded stdout/stderr before
   canonical-result rejection; commit/push it and dispatch CI to obtain the aggregate's actual
   failure. The prior diagnostic run `31022815776` still ended at generic `ERROR CHILD aggregate`
   because this upper-control diagnostic was not yet present.
2. Apply the evidence-backed aggregate repair to `agent/fresh-worker-capability`, run the focused
   qualification and topology checks, then refresh the Section 2.4 baseline tuple from the new
   source commit (source -> oracle-only -> finalizer-only). Push to PR #61.
3. Obtain fresh installed Ubuntu 24.04 FRESH-IMAGE/FRESH-WORKER evidence, record the required
   comprehensive and conditional final review envelopes and finding dispositions, and merge with a
   merge commit only after all checks pass. Do not start the next roadmap item; the user asked to
   stop after this PR.
4. After merge, perform the bounded retrospective, remove the temporary diagnostic branches and
   worktrees, update the merged-branch handoff as appropriate, and stop.

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
- `python3 scripts/run-fresh-image-control-smoke`: PASS, including compilation and execution of the
  bwrap-only forwarder with three recognized mount descriptors preserved and an unrecognized
  descriptor after `--` closed at target exec.
- Hosted PR run `31021997154`: Pinned Align job `92361333668` PASS. Its initial Installed job
  `92360777058` failed on a Docker Hub Ubuntu manifest `502`; rerun Installed job `92361332327`
  built and attested the image, passed the bwrap self-test, and failed only at the real worker
  aggregate with `fresh compiler: ERROR CHILD aggregate`.
- Diagnostic run `31022815776`: Pinned checks PASS and Installed image build/self-test reached the
  same aggregate failure. The worker-level diagnostic output was captured internally, but the
  upper image-control canonical-result check still suppressed it; the retained uncommitted control
  patch is the next diagnostic action.
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
- The current functional blocker is the unexplained installed aggregate failure after bwrap self-test;
  do not guess a repair before the retained upper-control diagnostic exposes the bounded child output.
- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; this capability does
  not adopt a new Align surface.
- FRESH-WORKER remains one capability because private admission, two namespaces, the compiler bundle,
  Make interposition, cache/image completion, and the first real consumer aggregate are not useful or
  reviewable as independently shipped helper surfaces.
- The pull request must use a merge commit so the implementation source, immutable oracle, and
  canonical finalization commits remain ancestors of the exact merged head.
- The diagnostic branch/worktree `agent/fresh-worker-aggregate-diagnostic` /
  `/tmp/align-llm-fresh-aggregate-diagnostic` is intentionally retained. It has one intentional
  uncommitted file: `image/fresh/control/fresh_image_control.py` with the upper-control diagnostic
  output patch. The older `agent/fresh-worker-diagnostic` worktree is also intentionally retained
  for historical FD-boundary evidence until the PR is resolved.
- The separate primary worktree has intentional uncommitted state; do not discard or overwrite it
  while this clean worktree is active.
