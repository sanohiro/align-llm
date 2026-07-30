# Session handoff

Read `CLAUDE.md` first. This file records only durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/c6-json-escape-request-v2`
- Base and relevant main commit:
  `54f290154a5f33e476cd17d6770f90b0f3838903` (`origin/main`)
- Relevant Request 7 content head:
  `fef8c0daf482b1bb4d26704b944a5a91f4f57cf7`
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

Ordinary decode, encode, and owner drop for eligible `Option<Move record>` success are already
shipped. A first adversarial preflight proved that strict ignored-string rejection and
outside-arena escaped-view rejection add failure edges after earlier fields may make owners live.
Request 7 may therefore be registered independently but cannot advance to `IMPLEMENTING` until both
Request 6 and the next decoded-owner transition cleanup request are `ALIGN_MERGED` at distinct
named commits. Request 6 is a prerequisite because Request 7's scanner grammar coverage assumes
its recursively Copy row boundary; Request 6 is therefore now reclassified as blocking for the
Request 7 implementation slice even though no align-llm product path directly consumes
`json.scan`. The cleanup prerequisite must audit construction, speculative
write, replacement and source nulling, fallback success and failure, staging, return, and cleanup.
Demonstrated classes include optional owners followed by later enclosing-object failure, indexed
top-level AoS speculation overwritten by fallback, top-level `array<MoveStruct>` partial staging,
and required or optional top-level record owners followed by trailing-garbage rejection.

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
the exact hand-authored public matrices.

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
check-topology design instead of adding a workflow-only command. A reviewed topology-ledger update
must merge first; implementation then adds the target to `HOSTED_CHECK_TARGETS`, its embedded
oracle/self-test, and the workflow's canonical `hosted-checks` aggregate. All inspection uses
an empty, override-isolated Git environment with optional locks and lazy fetch disabled; standard
promisor-remote partial clones, including promisor keys reached through repository-local includes
or linked-worktree configuration, reject before object lookup; negative fixtures prove no
index/object mutation, hidden dirt, fsmonitor execution, or promisor access. A shared preflight
requires Git 2.45 or newer before hosted history preparation or target-side repository inspection,
so `GIT_NO_LAZY_FETCH` is enforced rather than silently ignored; sentinel capture and a C-locale
anchored parser preserve and validate the exact one-line version record. The performance gate
now owns a checked-in harness, two isolated clean revisions, byte-identical benchmark/configuration
inputs, native CPU mode, five named one-million-row fields, ten order-balanced sample pairs, an
exact median calculation, and a per-field 1.05 ratio threshold. Outside-arena key and skipped-value
validation is fixed-state and allocation-free rather than hidden input-sized scratch.

The final exact-SHA host-native review found two additional evidence gaps. The detached JSON
benchmark workspaces ignored their own lockfiles, so Request 7 now requires a separately reviewed
benchmark-input enabling slice to check in both lockfiles and use `cargo --locked --offline` before
the implementation baseline exists. The ancestry gate's graft absence test could also race a
concurrent graft-file write; every isolated Git command now sets `GIT_GRAFT_FILE=/dev/null`, and a
negative fixture races the repository file between the absence check and ancestry calls. The path
check remains fail-fast defense-in-depth.

A later host-native review closed four more acceptance-input gaps. Request 6's lifecycle now
reflects the concrete Request 7 dependency. The performance harness has required explicit
toolchain/cache inputs, an empty environment, isolated Cargo home/config discovery, protected
dependency metadata, and per-worktree default targets. The future topology design must name an
immutable actual-Git-2.45.0 execution image and run the complete adoption gate there, not merely
feed synthetic version text to the parser. It must also move exact `.align-revision` byte
validation into `scripts/check-align-revision` before any checkout lookup or release build.

The next exact-SHA reviews found that the benchmark still trusted PATH composition, covered only
the detached Cargo graphs, and left the scripts' root Cargo builds network-capable. The final
contract supplies absolute non-symlinked `cargo`/`rustc` files directly, uses a fixed system PATH,
requires `--locked --offline` for every Cargo command, and defines exact canonical metadata reports
for baseline/candidate across the root, json-decode, and json-SoA workspaces. It also rejects
assume-unchanged and skip-worktree index flags before accepting the pinned Align checkout, because
porcelain status alone can hide modified tracked bytes.

The final revised-diff review also required persistent Cargo/Rust executable mutation barriers,
coverage for the intermediate `bench/.cargo` configuration directory, ignored build-input
rejection, and consistent failure-path allocation semantics. The benchmark now revalidates complete
tool file identity before every Cargo command and after measurement. Every Cargo working
directory-to-root configuration path is protected or rejected. The exact-checkout gate rejects
ignored inputs outside an ordinary root `target/`. Typed paths perform fixed-state whole-input
string-grammar validation before retained-string materialization, so grammar failures allocate
zero; later semantic failures have an exact zero/one/two per-rail allocation oracle.

The latest exact-SHA reviews then closed the remaining evidence-level ambiguity in those two
boundaries. The benchmark comparator must isolate every field in the saved Cargo/Rust identity,
while real-file barriers cross both tools, both revalidation placements, and content, mode, mtime,
inode, size, and type mutations. Persisted revision validation now uses one shared binary-safe
reader for `.align-revision` and both prerequisite fixtures before shell extraction or Git access;
its matrix includes a NUL at every position and the command-substitution-sensitive
`<40-hex><NUL><LF>` case.

The next host-native review demonstrated that repository-local attributes and clean filters can
make porcelain status hide different tracked bytes, and found two related Git-isolation order
gaps. Exact checkout and benchmark worktrees now use raw tree/index/filesystem comparison and
filter-free raw materialization; clean, smudge, and process helpers must remain unexecuted. All
benchmark and hosted-history Git operations use explicit empty environments and disabled hooks.
Effective promisor configuration and common-object-directory alternates are rejected before
object reads, with alternate postchecks before output or status consumption and persistent-race
regressions.

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
`fef8c0daf482b1bb4d26704b944a5a91f4f57cf7` against a clean detached checkout of the exact pinned
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
3. Refresh `main`, run the bounded retrospective, and register decoded-owner transition cleanup
   first, then strict numeric grammar if retained and record-array construction as separate reviewed
   slices. Request 7 implementation remains blocked until the cleanup request reaches
   `ALIGN_MERGED`; it also requires Request 6 to reach `ALIGN_MERGED`.
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
