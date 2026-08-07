# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull request checks, review findings, and
attestations; this file records durable project state.

## Active continuation checkpoint (2026-08-07)

The checkpoint below supersedes the older historical entries in this file. PR #61 is merged;
continue with the corrected Request 6 adoption design before implementation.

- Branch: `agent/request6-adoption-contract-v2` at
  `e4669561b7f1df6a92293e38a692bc707d81d1c9`, based on merged `main` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`; the corrected design ledger and closure matrix are
  complete and await the fresh independent design review of `e466956` before the replacement PR is
  opened.
- PR #61 (`Install the authenticated fresh worker`) merged with method `merge` at
  `1fafcd8b4c5d4f1c147e51749f596662c4a60398`; its exact-head review and hosted evidence remain
  recorded in GitHub comment `5214227839` and run `31159427993`.
- PR #62 is not mergeable as written and must not be merged. Its final review found that ordinary
  Make-control options were consumed before the promised pre-Make rejection, the cleared PATH
  removed the rustup-based Cargo toolchain, the optional-schema oracle remained conditional in one
  acceptance item, and the branch handoff was stale. The replacement design splits the ordinary
  non-Make launcher and authenticated direct toolchain inputs from the fresh worker request.
- Active goal: finish and review the corrected Request 6 adoption contract, merge that design gate,
  then implement the wrapper, focused target, fixtures, pin wave, fresh adoption vector, and final
  fresh `make ci` on a new branch. Request 7 and later consumers remain blocked on this gate.
- Expected post-merge checkpoint: refresh `main` safely, perform the bounded design retrospective,
  and create `agent/request6-adoption-implementation` from the merged design. The next session must
  begin implementation of the ordinary launcher and authenticated focused consumer; it must not
  reopen this design PR or reuse PR #62's direct ordinary Make command.
- The shipped Align revision for Request 6 is
  `e65448b744c04e3868d079eef8b45ce0d43ac8ee`; `.align-revision` must remain unchanged until the
  reviewed implementation branch consumes the fresh adoption design.

## Review and repair

- PR #62's final `codex review --base main` against head `92220dfe5b77a38fc76f16a78c7ca3a4ab435873`
  found two P1 and two P2 design defects: ordinary Make options were consumed before the promised
  rejection, the cleared ordinary PATH removed the rustup-based Cargo toolchain, item 2 retained a
  conditional optional-schema oracle, and the branch handoff was stale. The PR is superseded rather
  than repaired in place. The replacement design adds a non-Make ordinary launcher, authenticated
  direct Rust/LLVM/native inputs, a fixed shipped scanner oracle, and this current checkpoint.
- The next design review of `b078048` found three P1 and two P2 gaps: Make recipes could reopen the
  caller cwd, the ordinary compiler handoff was not retained across the focused child, the native
  aliases could still execute manifest forwarders, phase precedence was under-specified, and the
  handoff did not name the current design head. Commit `5528cf0` closes these by fixing every child
  to `-C` the private project, adding the schema-1 launcher and descriptor with golden bytes,
  materializing aliases from authenticated compiler bytes, defining phase mapping, and recording
  the current head here.
- The fresh independent review of exact head `14eadde` found one P1 and one P2: ordinary mode bits
  did not protect the compiler handoff from same-UID mutation, and this handoff pointed at the older
  `5528cf0` head. Commit `bc8432f` adds the empty-root read-only namespace, fixed `/private-tool-bin`
  bind, retained-file `execveat` launcher contract, and the corrected design head; the next review
  must cover this new namespace boundary.
- The fresh independent review of exact head `d5f677e` found three P1 and one P2: the empty-root
  runtime lacked canonical loader/interpreter targets, descriptor identities were recorded before
  final bundle materialization, the host staging path remained a same-UID alias, and the handoff
  again named an older head. Commit `e466956` adds canonical runtime bindings, namespace-helper
  final stat/hash-before-descriptor ordering, a namespace-owned compiler tmpfs with no host alias,
  and this current head.
- A fresh independent adversarial review found four valid non-trivial gaps: tool/Git descendants
  were outside the shared worker owner, cgroup leaves were pathname-owned, private-root cleanup
  closed identity witnesses before removal, and `make baseline-check` did not execute the
  Section 2.4 commit-chain contract.
- Closure plan `b69aff1d6c6d8f5f1ed56742aaabc7fcc0dc7451` records the repair owners and regression
  boundaries.
- Implementation `10bcbdd8f112746756069fd72f765843b4ea286b` routes worker children through the
  bounded owner, hardens cgroup and private-root cleanup, hardens image-control children, and
  adds the executable baseline-chain checker. Source `83d9117` also aligns the recorder's
  artifact manifest with the verifier.
- Repair `1d33b90` fixes descriptor-relative materialization of single-file runtime bindings
  such as `/usr/bin/dash` and adds a regression case; the installed hosted diagnostic had
  exposed the prior `NotADirectoryError` at that boundary.
- Repair `8ff96a8` makes the replacement-object smoke explicitly disable the worker's inherited
  `GIT_NO_REPLACE_OBJECTS` only for the probe that must demonstrate replacement resolution; the
  verifier remains isolated with replacement objects disabled. Hosted diagnostic run `31143014723`
  exposed this inherited-environment mismatch after the runtime repair.
- The conditional final review against the earlier repair head found four valid P1 gaps: cgroup
  admission lacked strict membership proof, cgroup cleanup had a pathname TOCTOU, private-root
  cleanup had a pathname TOCTOU, and runtime/cache materialization did not prove a complete
  descriptor-relative pre/post tree snapshot. The reviewed design was reopened in `b9e4d37` and
  `baae181`; implementation `c61995f` adds cgroup membership/quarantine, private-root quarantine,
  complete materialization verification, image-control parity, and deterministic regression cases.
- Fresh independent review of exact head `e62eb6a` found three P1 gaps: a raced FIFO could block
  materialization, a same-size source mutation after the destination write was not rejected, and
  exact-head installed hosted evidence was still absent; it also found stale handoff head text.
  Design `0aa9d60` reopens the materialization closure matrix and implementation `aba1c84` adds
  no-follow/nonblocking file opens, retained-source post-write snapshots, and FIFO/same-size
  mutation regressions. The handoff head is corrected here; hosted evidence remains a PR concern.
- Hosted Installed run `31145643974` failed because cgroup-v2 rejects `renameat2(RENAME_NOREPLACE)`.
  Diagnostic run `31146342637` confirmed `OSError(22, "Invalid argument")` at the supervisor's
  first Git identity probe. Design `ca18317` records the kernel-supported cgroup-v2 primitive:
  the unique authenticated leaf name is the quarantine identity and descriptor-relative `rmdir`
  is used under the protected delegated-parent writer boundary. Implementation `acbba8e` applies
  that protocol to worker and image control and adds direct-removal and replacement-before-removal
  regressions. Diagnostic-only commits remain off the product branch.
- Exact-head diagnostic run `31148028562` reached the aggregate after the cgroup-v2 repair but
  rejected the generated ELF because the image exposes identical system-library trees at both
  `/lib` and `/usr/lib`; the existing derived loader list treated those authenticated structural
  aliases as ambiguous. Design `554dcbd` records first-manifest-order structural alias collapse
  while retaining rejection for distinct trees. Implementation `c12e4f6` applies it to all three
  derived path lists and adds focused identical/distinct alias and real ELF closure regressions.
- Exact-head diagnostic run `31151003872` showed the remaining ambiguity: relative
  `DT_NEEDED=ld-linux-x86-64.so.2` matched byte-identical loader files under the copied system
  library tree and an explicit `/lib64` file binding. Design `02b02f3` extends the contract to
  compare complete staged file bytes for multiple relative candidates, preserve the first
  candidate, and reject byte-distinct candidates. Implementation `29b4730` adds that resolver
  behavior plus single-file and real-ELF byte-distinct alias regressions. Diagnostic branch
  instrumentation remains off the product branch.
- Exact-head hosted run `31151900302` passed pinned checks but failed Installed at the aggregate
  baseline chain. Diagnostic run `31153583460` proved the ELF alias repair was working and exposed
  the actual failure: `scripts/check-baseline-chain` replaced the aggregate's staged `PATH=/tools`
  with `/usr/bin:/bin`, so its bare `git` subprocess was unavailable. Design `c2cdad7` records
  the closed two-profile executable contract; implementation `8fa4fd7` and regression repair
  `b82c56a` select `/tools` only for the exact fresh marker/tool-root pair and reject partial or
  different settings. The baseline was then refreshed through source `8fa4fd7`, oracle `d50a753`,
  and finalization `44c825e`.
- Exact-head hosted run `31154734504` passed Pinned but still failed Installed with the public
  `CHILD aggregate` category. Diagnostic run `31155288459` showed that the staged Git executable
  was now found, but the standalone chain checker had dropped the aggregate's private
  `GIT_DIR=/baseline-git`, `GIT_COMMON_DIR=/baseline-git`, and `GIT_WORK_TREE=/workspace` values;
  its first `cat-file` therefore rejected `SOURCE_COMMIT`. Design `b7a1370` extends the closure
  contract to the full executable/private-view tuple; implementation `d4cc7da` and baseline
  refresh `4831aa9`/`aeee406` propagate and regression-test those exact values. Diagnostic
  instrumentation remains off the product branch.
- The final exact-head comprehensive review of `ddb6a23` found one valid P1: image-control child
  launch and early setup failures could bypass cleanup after cgroup lease acquisition, leaving the
  cgroup leaf and retained descriptors. The closure matrix was reopened in `8432374`; implementation
  `03d77bb` routes every post-lease path, including `Popen` failure, through one cgroup/descriptor
  finalizer and adds the injected launch-failure regression. The focused image-control and worker
  smokes plus `make baseline-check` pass after this repair; exact-head hosted evidence and the final
  review envelope are still pending.
- The diagnostic branch `agent/fresh-worker-current-diagnostic` exposed only the hosted
  `filesystem` category before aggregate failure; diagnostic branch
  `agent/fresh-worker-aggregate-diagnostic-v5` isolated the runtime file-open failure and is
  not product code.

## Next steps, in priority order

1. Run one fresh independent adversarial review of `e466956`, then open the replacement design PR.
   Do not merge PR #62 or consume its unrevised ordinary command.
2. After the corrected design merges, refresh `main`, record the bounded retrospective, and create
   a new implementation branch from merged `main`; read the sibling Align instructions and shipped
   JSON scanner design, then implement the ordinary launcher, focused target/fixtures, exact pin,
   fresh adoption vector, baseline ancestry, and final fresh `make ci`.
3. Open the implementation PR, complete its review/fix/merge evidence, refresh `main` safely while
   preserving the primary intentional handoff, and continue to the next eligible roadmap gate.

## Latest verification

- `make gate-topology-check`: PASS at `e466956`.
- `git diff --check`: PASS at `e466956`.
- Markdown fence parity: PASS (`docs/align-requests.md` 94, `docs/specs/check-gate-topology.md` 76).
- Author-side design consistency review: PASS; the Request 6 public vectors, phase map, compiler
  handoff schema/golden bytes, namespace boundary, closure owners, and acceptance rows agree at
  `e466956`.

- `make check`: PASS; only existing Align compiler warnings remain.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-image-control-smoke`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-worker-qualification`: PASS after the
  immediate rerun of a transient linked-worktree source-identity smoke failure.
- After `1d33b90`, `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS,
  `run-fresh-image-control-smoke`: PASS, and `run-fresh-worker-qualification`: PASS.
- `make baseline-check`: PASS; canonical baseline, invalid-input smokes, failure smoke, and the
  executable source/oracle/finalization chain checker all passed.
- `PYTHONDONTWRITEBYTECODE=1 make baseline-check`: PASS after the fresh baseline Git executable
  and private-view propagation repair and identity-bound refresh; the smoke covers staged
  `/tools`, ordinary host PATH, incomplete/different fresh settings, and mismatched Git views.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS after bounded
  materialization repair.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-image-control-smoke`: PASS after bounded
  materialization repair.
- The source recorder completed two deterministic-reference samples from source `d4cc7da`.
- `git diff --check`: PASS for the source, oracle, and finalization commits.
- `bash -n scripts/run-baseline-invalid-smoke` and
  `GIT_NO_REPLACE_OBJECTS=1 PYTHONDONTWRITEBYTECODE=1 make baseline-check`: PASS, including the
  inherited-environment replacement-object regression.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS after the hosted baseline
  smoke repair.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS after the conditional
  final-review repair, including cgroup membership, quarantine replacement, and materialization
  mutation cases.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-image-control-smoke`: PASS after the conditional
  final-review repair, including image-control membership parsing and rebuilt control bundles.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS after the cgroup-v2
  cleanup repair, including descriptor-relative leaf removal and replacement-before-removal.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-image-control-smoke`: PASS after the cgroup-v2
  cleanup repair, including mirrored descriptor-relative removal and replacement-before-removal.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-image-control-smoke`: PASS after the final-review
  launch-cleanup repair, including injected `Popen` failure, cgroup removal, and descriptor close.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS after the final-review
  launch-cleanup repair.
- `PYTHONDONTWRITEBYTECODE=1 make baseline-check`: PASS after the final-review launch-cleanup
  repair; the existing identity-bound baseline tuple remains valid.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS after the ELF alias
  repair, including identical structural alias collapse, distinct-alias rejection, and real
  `/bin/true` closure validation.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-image-control-smoke`: PASS after the ELF alias
  repair; `git diff --check`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-worker-unit-smoke`: PASS after the identical ELF
  file-alias repair, including candidate-order preservation, identical-file acceptance, and
  byte-distinct file and real-ELF alias rejection.
- `PYTHONDONTWRITEBYTECODE=1 ./scripts/run-fresh-image-control-smoke`: PASS after the identical ELF
  file-alias repair; `git diff --check`: PASS.
- `python3 -m py_compile scripts/fresh-align-compiler image/fresh/control/fresh_image_control.py
  scripts/run-fresh-worker-unit-smoke`: PASS; `git diff --check`: PASS.
- Hosted run `31137327638` passed the pinned job but failed the installed aggregate with
  `filesystem`; diagnostic run `31142031436` exposed the underlying single-file runtime
  `NotADirectoryError`; diagnostic run `31143014723` then exposed the inherited replacement-object
  smoke mismatch. Hosted run `31145643974` exposed cgroup-v2 `renameat2` incompatibility;
  diagnostic run `31146342637` confirmed the `OSError(22, "Invalid argument")` probe failure.
  Exact-head diagnostic run `31148028562` exposed the duplicate-library ELF validation failure;
  all diagnostic runs are evidence only.

## Constraints and intentional state

- Keep all repository source, documentation, diagnostics, commits, and PR metadata in English.
- `.align-revision` remains
  `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no Align language request is open for this gate.
- The primary worktree `/home/hiro/prj/align-llm` has an intentional uncommitted
  `HANDOFF.md`; do not discard or overwrite it.
- Diagnostic worktrees and branches are intentionally retained for evidence; never merge their
  diagnostic-only instrumentation.
