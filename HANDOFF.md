# Session handoff

Read `CLAUDE.md` first. This file records only durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-json-escape-request-v2`
- Base and relevant main commit:
  `54f290154a5f33e476cd17d6770f90b0f3838903` (`origin/main`)
- Relevant Request 7 content head:
  `87566c4112759738bfb8ef19ad455dd664c03a76`
- Active goal: review and merge Request 7, escaped strings and strict string grammar for declared
  JSON decoding, as the next independently demonstrated Align prerequisite for C6.
- Product implementation: not started.
- Pinned Align commit: `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`
- C6 design draft: preserved separately on `agent/c6-prompt-context-design`.
- Original escaped-string work and its completed review follow-up remain preserved on
  `agent/c6-json-escape-request` at `1ef0d37c752eb94ad5457209946a5c587e14322e`.

PR #24 merged the scanner-safety request into the align-llm request register as Request 6. That
request exclusively owns the proposed recursively Copy `json.scan` row boundary. Request 7 now
owns escaped-string materialization for arena-backed declared record, AoS, and SoA decoding plus
shared strict string grammar. Scanner ownership and Move-row diagnostics are N/A here; Request 7
only specifies strict grammar for rows admitted by Request 6 and rejects escaped retained views
because the scanner has no arena.

The pinned implementation currently admits `Option<Move record>`: direct decode/encode succeeds,
and ordinary scope `Drop` frees the nested owner. That behavior contradicts the authoritative JSON
design and its stale rejection regression, while decode-error cleanup skips optional descriptors.
The decoded-owner prerequisite must therefore decide whether to restore rejection or specify and
repair the admitted surface. A first adversarial preflight also proved that strict ignored-string
rejection and outside-arena escaped-view rejection add failure edges after earlier fields may make
owners live. Request 7 may be registered independently but cannot advance to `IMPLEMENTING` until
both Request 6 and the next decoded-owner transition cleanup request are `ALIGN_MERGED` at distinct
named commits. Request 6 is a prerequisite because Request 7's scanner grammar coverage assumes
its recursively Copy row boundary; Request 6 is therefore now reclassified as blocking for the
Request 7 implementation slice even though no align-llm product path directly consumes
`json.scan`. The cleanup prerequisite must audit construction, speculative write, replacement and
source nulling, fallback success and failure, staging, return, and cleanup. Demonstrated classes
include optional owners followed by later enclosing-object failure on the currently admitted path,
indexed top-level AoS speculation overwritten by fallback, top-level `array<MoveStruct>` partial
staging, and required or currently admitted optional top-level record owners followed by
trailing-garbage rejection.

The persistent Request 6 adoption target must select its optional-owner fixtures from the active
pinned compiler, not the immutable Request 6 commit. Its first adoption records that compiler's
outcome. If decoded-owner cleanup later changes the schema decision, the align-llm adoption slice
that first advances `.align-revision` to the changed behavior must update both optional fixtures and
their exact expected diagnostic or success path in the same pull request. When Request 6 has
already merged, the later cleanup Align change must likewise update Request 6's checked-in optional
scanner, no-MIR, and ordinary-decode regressions before it merges. If cleanup merges first,
Request 6 records the already-shipped outcome in its initial tests.

The review follow-up also adds an exact per-path result oracle, hand-authored multi-invalid
precedence cases, an exact checked-in 4,096-line grammar manifest whose byte hash and Cartesian
coverage become authoritative before acceptance, and a caller-owned `cfg(test)`-only probe for
failure byte offsets and logical arena allocations. The probe is not a production ABI or
process-global counter. Tests that also read existing process-global heap counters must acquire
`ALLOC_COUNT_LOCK` before setup and hold it through cleanup and assertions. Every corpus validity
class now has a unique token-relative class anchor. A later
host-native review demonstrated that crossing all token classes with declared-key positions and
nested flat-SoA paths was not executable under Align's ASCII identifier and flat-column rules. The
corpus design was therefore reopened: the 4,096-row Cartesian artifact now owns grammar only,
places every token in a nested undeclared `probe` value that every named path can parse or skip,
and leaves declared-key, returned-value materialization, `json.doc.key`, and duplicate semantics to
the exact hand-authored public matrices. The latest host review also fixed every class's eight
variants to an exact token-body and semantic-byte table; the verifier derives the row's variant
from its ordinal and rejects any byte, meaning, order, or duplicate drift.

A second adversarial review found that a proposed joint-delivery exception contradicted the
cleanup-first lifecycle and that align-llm can pin only one Align commit. The final contract removes
joint delivery. A Request 7 implementation branch may start only after both named prerequisite
commits are merged, and the final Request 7 commit must retain both as strict ancestors. Adoption
pins only the final Request 7 commit in `.align-revision`, records both prerequisite commits in
checked-in fixtures, rejects equal, non-raw-commit, replacement-forged, shallow, and unrelated
revision states, and then runs isolated Align-repository `merge-base --is-ancestor` checks before
any client fixture. Hosted adoption CI must expand history without changing the exact detached
Request 7 checkout or worktree, and its fixed target list must invoke the same
`c6-json-escape-adoption` target that local `make ci` runs. A final preflight found that one
absolute corpus offset could not describe record, array, and NDJSON inputs with different outer
bytes. The corrected contract stores a token-relative anchor and defines byte-exact object, array,
and NDJSON adapters; each adapter independently derives the smallest ASCII padding, verifies its
absolute anchor and boundary equation, and asserts that path's parser offset. The ancestry gate
also captures Git common-directory output with a non-newline sentinel before command substitution
can strip its terminator, rejects a path containing any control byte, and rejects any existing or
symlinked `info/grafts` path before ancestry inspection. The negative matrix includes a valid common
directory whose basename ends in LF and whose graft would otherwise forge ancestry.
`GIT_NO_REPLACE_OBJECTS` alone does not disable graft parents.

The final host-native review also required the future adoption to follow the authoritative
check-topology design instead of adding a workflow-only command. A reviewed topology-ledger design
update must merge first; its dependent implementation must merge and install the common
fresh-compiler path before any pin-changing adoption. Request 7 adoption then adds its target to
`HOSTED_CHECK_TARGETS`, the embedded oracle/self-test, and the workflow's canonical
`hosted-checks` aggregate. All inspection uses
an empty, override-isolated Git environment with optional locks and lazy fetch disabled; standard
promisor-remote partial clones, including promisor keys reached through repository-local includes
or linked-worktree configuration, reject before object lookup; negative fixtures prove no
index/object mutation, hidden dirt, fsmonitor execution, or promisor access. A shared preflight
requires Git 2.45 or newer before hosted history preparation or target-side repository inspection,
so `GIT_NO_LAZY_FETCH` is enforced rather than silently ignored; sentinel capture and a C-locale
anchored parser preserve and validate the exact one-line version record. Request 7 fixes only the
benchmark workload and outcome: byte-identical protected inputs, native million-row decode/SoA
commands, five named fields, ten order-balanced sample pairs, exact medians, and a per-field 1.05
ratio threshold. Controller, checkout, tool, and report transport ownership remain deliberately
unassigned until the separate benchmark-evidence design below. Outside-arena key and skipped-value
validation is fixed-state and allocation-free rather than hidden input-sized scratch.

Repeated review exposed a separate design boundary around benchmark evidence: a candidate-owned
harness cannot safely choose or attest its own baseline, and attempts to specify an external runner
inside Request 7 recursively introduced an unowned native controller, executable race, descriptor,
credential, and provider-integration contract. The local patch loop is therefore closed. Request 7
now remains `PROPOSED` until a separate Align benchmark-evidence design merges and remains below
`IMPLEMENTING` until its dependent enabling implementation also merges. That prerequisite owns
controller source and delivery, immutable pre-work
baseline selection, candidate binding, trust roots, executable and descriptor identity,
credential/provider handling if applicable, report schema, exact-SHA review/integration evidence,
failure cleanup, and adversarial tests. Request 7 retains the fixed workload and acceptance outcome
as inputs to that design: the baseline is the exact implementation branch point, the candidate has
no unrelated delta, protected inputs and effective toolchain/configuration are identical, one
otherwise-idle host runs ten order-balanced sample pairs, and all five median ratios are at or below
1.05. No hypothetical controller API or merge mechanism remains in the request register.

The final exact-SHA host-native review found two additional evidence gaps. The detached JSON
benchmark workspaces ignored their own lockfiles, so Request 7 now requires a separately reviewed
benchmark-input enabling slice to check in both lockfiles and use `cargo --locked --offline` before
the implementation baseline exists. The ancestry gate's graft absence test could also race a
concurrent graft-file write; every isolated Git command now sets `GIT_GRAFT_FILE=/dev/null`, and a
negative fixture races the repository file between the absence check and ancestry calls. The path
check remains fail-fast defense-in-depth.

Earlier review iterations explored concrete benchmark-controller choices such as fixed tool paths,
empty environments, raw worktree materialization, and executable mutation barriers. Those
orchestration choices are no longer authoritative after the boundary split and must be decided by
the separate benchmark-evidence design rather than copied from review history. The retained
Request 7 requirements are only the protected-input/dependency equality, fixed native workloads,
sample order, fields, median calculation, threshold, fail-closed outcome, and observable evidence
listed in item 12.

Separately, the align-llm adoption gate still requires filter-independent revision and ancestry
inspection, binary-safe revision-file validation, Git 2.45 compatibility, promisor/alternate/graft
isolation, and a fresh compiler. The exact fresh-build identity, process, timeout, cache, and
cleanup mechanism belongs to the common prerequisite topology design described next.

The final host-native review reproduced another Git trust-boundary failure: repository-local
`core.ignoreCase=true` hides a case-fold-colliding untracked Rust source from both
`git ls-files --others` queries even though Align's recursive build script consumes it. The
corrected contract no longer delegates any additional-path decision to Git. Its binary-safe raw
comparator owns a complete dirfd-relative, no-follow filesystem enumeration and compares every
entry against the tree/index trie, excluding only the validated root `.git` administrative entry
and, only after proving that no tracked root `target` component exists, an ordinary root `target/`
output subtree. The hostile matrix fixes the reproduced `LIB.rs`/`lib.rs` collision, tracked
`target`, extra directories, type and rename observations, and ignore/excludes cases. Git's ignore
and case-fold configuration can therefore no longer make a compiler input invisible to the gate.

The fresh adversarial follow-up found two related trust-root gaps. Repository-local
`core.worktree` can redirect Git outside `ALIGN_REPO`, so the gate now retains the exact validated
`ALIGN_REPO` root, rejects effective direct, included, or worktree-local `core.worktree`, and
requires both inside-worktree status and byte-exact top-level equality before object lookup. More
fundamentally, a retained comparator descriptor alone cannot bind separate Git processes and a
later Cargo build across an ancestor/root ABA replacement. Request 7 does not invent that
mechanism: it requires the common topology design and implementation to install one
non-conflicting source-identity boundary spanning Git/config/object/index inspection, raw
enumeration, source materialization, and build, including root, Git-directory, common-directory,
and source-byte identity. A same-HEAD/tree/index replacement with an additional recursively
consumed Rust input is the required negative, and standalone comparator success cannot satisfy
adoption.

Two successive controller-design reviews found new critical correctness classes, so the local
patch loop is closed and that boundary is split out. Before the next `.align-revision` change or
`ALIGN_LLM_VERIFIED` claim against a new compiler, a separate reviewed
`docs/specs/check-gate-topology.md` design update and its dependent implementation must define,
merge, and install the fresh-compiler bootstrap, trusted tool and cache inputs, compiler-exec
identity enforcement, process ownership, deadlines, and fail-closed cleanup in canonical
`make ci`. This repository-wide prerequisite applies to Request 6, decoded-owner cleanup,
Request 7, and every later pin-changing adoption. The design must explicitly resolve
self-validation before bootstrap execution, ownership of any additional bootstrap/tool version
probes beyond the already required Git preflight, nested Cargo-cache symlink/rename escape, and
interposition below Make. Request 7 records the required safety outcomes and remains blocked
rather than naming a hypothetical controller or API.

Scanner framing repair is outside Request 7. Scanner coverage uses only valid top-level-array and
NDJSON frames and changes string-token grammar inside Request 6-admitted Copy rows. Missing
delimiters, ambiguous EOF, and other framing behavior remain shipped behavior; a future concrete
consumer must register a separate request if that boundary becomes necessary.

The bounded retrospective after PR #24 established three reusable decisions:

1. describe ownership defects by owner-live transitions rather than a container-type label;
2. split an independently sound safety boundary before resuming a broader consumer request; and
3. keep attestations in GitHub while recording reproducible verification commands and durable
   branch decisions here.

## Verification

Verified on 2026-07-30 at Request 7 content head
`87566c4112759738bfb8ef19ad455dd664c03a76` against a clean detached checkout of the exact pinned
Align commit:

```text
git diff --check                                      PASS
ALIGN_REPO=<clean detached pinned Align worktree> \
  make ci                                             PASS
```

## Exact next steps

1. Rerun a preflight-equivalent independent adversarial review against the complete final diff and
   repeat both required post-open reviews on the resulting exact SHA.
2. Publish current-SHA preflight, host-native, independent-adversarial, and check evidence, and
   merge only when every envelope is clean against an unchanged base tip.
3. Refresh `main`, run the bounded retrospective, then make the common fresh-compiler check-topology
   design and dependent implementation the first align-llm enabling slices: no request may next
   change `.align-revision` or claim `ALIGN_LLM_VERIFIED` against a new compiler before both merge.
   Register decoded-owner transition cleanup separately, then strict numeric grammar if retained
   and record-array construction. Request 7 implementation remains blocked until cleanup and
   Request 6 reach `ALIGN_MERGED`, the benchmark-input slice and separate benchmark-evidence design
   plus dependent implementation merge, and that design selects the immutable pre-work baseline;
   its later
   adoption also consumes the already-shipped common topology path and waits for the separate
   Request 7 topology update that adds `c6-json-escape-adoption` to that graph.
4. Return to the C6 design branch only after its complete prerequisite set is registered; do not
   implement against a proposed Align surface.

## Constraints and intentional state

- This branch changes only `docs/align-requests.md` and this durable handoff. The worktree is
  expected to be clean after this handoff commit.
- The old escaped-string branch is a preserved source checkpoint, not a merge source.
- `agent/c6-prompt-context-design` preserves the C6 design draft.
- Existing governance, pin-adoption, topology, Request 5, and scanner-request worktrees belong to
  earlier scoped work; do not modify or remove them.
- Use the repository wrappers with the exact pinned Align checkout. Do not implement C6 against a
  proposed Align surface or introduce an application workaround.
