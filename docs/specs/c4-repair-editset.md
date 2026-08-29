# C4-REPAIR-EDITSET: the failing edit set in the repair prompt, via a second adapter

Status: **implemented and measured.** Section 11 carries the implementation record, the
ledger-to-diff mapping, the recorded deviations, and the gate result. This document is the
authoritative plan. The proportional
design gate in `CLAUDE.md` triggered on an exchanged-format change (`TASK_MEASUREMENT`
`schema_version` 1 → 2 carries the attempt's realized edit set and a digest of its patch body), on a
new frozen corpus scope with a **second measurement adapter** as a member, and on a coordinated
invariant across `scripts/prompt-repair-adapter.py`, `scripts/prompt-evaluate.py`,
`src/prompt_score.align`, `src/prompt_artifacts.align`, and the corpus assets. Branch
`agent/c4-repair-editset`, stacked on `agent/c4-repair-measured` at `c07775c`.

`docs/specs/c4-repair-measured.md` is the source of truth for everything this capability reuses
unchanged — the evaluator-owned attempt loop, `PROMPT_TASK_ROW` `schema_version: 2` and its
`TaskAttemptRecord`, the repair-prompt assembly and its re-derivation rule, the drop ladder, the
per-attempt timing definition, the provider topology, and the `eval/prompt/canonical-v1r/` freeze.
`docs/specs/c6-prompt-context-optimizer.md` remains the source of truth for the layer beneath both.
This document owns only what C4-REPAIR-EDITSET adds: the second adapter and the import-by-path
contract that keeps the first one byte-identical, `TASK_MEASUREMENT` version 2, the `EDITSET`
section, the extended drop ladder, the `canonical-v1e` freeze, and the C4 gate re-run.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

C4-REPAIR-MEASURED ran the loop and returned a measured negative. Its section 10.3 records
`repair_recovery_paired_count: 0` over ten repair attempts, and it named the reason directly:

> a `NOT_MET` gate in which attempt 2 repeats attempt 1's mistake is exactly the case where **the
> missing edit set is the binding constraint**, and it makes option B — a second corpus-member
> adapter that carries the failing edits into the repair prompt — the obvious next capability
> rather than a speculative one.

This is that capability. It lifts the deferral `c4-repair-measured.md` §5.4 opened, by the route
that document's §5.7 named option B, and it does so without the duplication that made §5.7 reject
option B at the time: the new adapter **loads the frozen one by path and calls its functions**, so
the reviewed containment, sealing, redaction, and process-ownership code has exactly one copy, and
the second file contains only the sequencing that differs.

The repair prompt then shows the model what it actually wrote, next to the assertion that rejected
it. `c4-repair-measured.md` §2.6 states the cost of not doing that in one sentence: "What is
genuinely lost is the model's ability to see its own mistake."

### 1.2 The measured evidence this capability is built on

Read directly out of `eval/prompt/c4-repair-gate/c4-repair-evaluation.json` (12 rows,
`schema_version: 2`, 22 provider calls). Every repair attempt and its `patch_size_bytes`:

| Task | Sample | Variant | Attempt 1 | patch | Attempt 2 | patch |
| --- | --- | --- | --- | --- | --- | --- |
| `duration-half-away-from-zero` | 1 | PARENT | FAIL/`TEST` | 716 | FAIL/`TEST` | **716** |
| `duration-half-away-from-zero` | 2 | PARENT | FAIL/`TEST` | 716 | FAIL/`TEST` | **716** |
| `duration-half-away-from-zero` | 1 | CANDIDATE | PASS | 758 | — | — |
| `duration-half-away-from-zero` | 2 | CANDIDATE | PASS | 758 | — | — |
| `record-codec-round-trip` | 1 | PARENT | FAIL/`TEST` | 1008 | FAIL/`TEST` | **1008** |
| `record-codec-round-trip` | 2 | PARENT | FAIL/`TEST` | 1008 | FAIL/`TEST` | **1008** |
| `record-codec-round-trip` | 1 | CANDIDATE | FAIL/`TEST` | 1008 | FAIL/`TEST` | **1008** |
| `record-codec-round-trip` | 2 | CANDIDATE | FAIL/`TEST` | 1008 | FAIL/`TEST` | **1008** |
| `layer-precedence-frozen-module` | 1 | PARENT | FAIL/`PATCH` | 0 | FAIL/`PATCH` | 0 |
| `layer-precedence-frozen-module` | 2 | PARENT | FAIL/`PATCH` | 0 | FAIL/`PATCH` | 0 |
| `layer-precedence-frozen-module` | 1 | CANDIDATE | FAIL/`PATCH` | 0 | POLICY_VIOLATION/`POLICY` | 0 |
| `layer-precedence-frozen-module` | 2 | CANDIDATE | FAIL/`PATCH` | 0 | POLICY_VIOLATION/`POLICY` | 0 |

**Two distinct modes, and only one of them is this capability's.**

**Mode 1 — identical-size patch re-emission. Six rows: `record-codec-round-trip` ×4 and
`duration-half-away-from-zero` PARENT ×2.** Attempt 1 produced a validated whole-file edit set, the
runner applied it, the test failed, and attempt 2 — given the status labels, the summary naming the
edited file, and the full pytest stdout and stderr — returned a patch of **exactly the same byte
count**. Every one of the six. This is the mode the edit set addresses: the model is not being told
what it wrote, so it writes it again.

The honest limit of that evidence is itself a C4 finding: `patch_size_bytes` is the only thing the
row persists about the patch, so "identical size" is all anyone can say. Whether the two patches
were byte-identical is **not currently checkable from any artifact this repository holds.** Making
it checkable is one of the two things this capability persists (§3.3, `patch_sha256`), and it is
the reason the digest is in the ledger rather than treated as a nicety.

**Mode 2 — the response reproduces the pinned files unchanged. Four rows:
`layer-precedence-frozen-module`.** Every attempt-1 on this task failed at `PATCH` with
`patch_size_bytes: 0`.

> **Corrected during implementation, from the evidence.** This section originally read "no parsable
> edit set at all — `parse_file_blocks` found no terminated `FILE:` block, so `validated_edit_set`
> never returned". **That is wrong**, and the persisted diagnostics say so directly: every
> `failure_kind: PATCH` row in `eval/prompt/c4-repair-gate/` carries
> `diagnostic_summary: "the response reproduced the pinned files unchanged"` — six of six — and not
> one carries `"the response declares no file block"` or `"a fenced file block is not terminated"`.
> That message is `synthesized_patch`'s refusal (`scripts/prompt-measurement-adapter.py:433`),
> raised **after** `parse_file_blocks` returned terminated blocks and **after**
> `validated_edit_set` accepted every declared path. So the model emits well-formed `FILE:` blocks
> naming allowlisted files, and fills them with the file's **existing** content: every whole-file
> hunk is empty, the synthesized patch is empty, and the adapter refuses it. §11.4 records the same
> tally for this capability's own run, where it is eight of eight.

The mode is therefore a **no-op answer**, not a format failure: the model understands the response
format and does not change anything. Attempt 2 then either repeated `PATCH` (PARENT ×2) or produced
a block naming `src/legacy.py`, outside the allowlist (CANDIDATE ×2).

**A validated edit set does exist on these rows, and this capability does not persist it.** The
`PATCH` outcome arrives after `validated_edit_set` returned, so §3.3's two clauses — "`Some` exactly
when `validated_edit_set` returned" and "`None` on `PATCH`" — are in tension for exactly this path.
The shipped adapter follows the second, so `edit_set` is `None` on all eight rows. That is a
contract-conformant choice and a real loss of the most interesting evidence on this corpus; §11.3
deviation 14 records it as the gap the fallback capability closes.

### 1.3 In scope

1. `scripts/prompt-repair-adapter.py`: a second measurement adapter that **loads
   `scripts/prompt-measurement-adapter.py` by path** (`importlib`-style `spec_from_file_location`
   semantics, over bytes it verified itself), reuses its containment, sealing, redaction, process
   ownership, generation child, validation execution, and edit parsing **without editing it**, and
   returns `TASK_MEASUREMENT` at `schema_version: 2`.
2. `TASK_MEASUREMENT` `schema_version: 2` = the 21 version-1 fields, byte-order unchanged, plus the
   attempt's realized edit set, its total size, a digest of the complete patch body, and the base
   adapter's runtime identity. Version 1 stays decodable, byte-for-byte, forever.
3. A repair-prompt content contract at version 2: a new sealed template with a fifth section kind,
   `EDITSET`, rendered in the response's own whole-file format, bounded, whole-block, and dropped
   **last** (§4.4).
4. A new frozen corpus scope, `eval/prompt/canonical-v1e/` + `eval/tasks/prompt-v1e/`, over the same
   three tasks and the same fixtures, differing from `canonical-v1r` only in the adapter it names,
   the repair template, the generation policy, and the recomputed digests.
5. One measured gate run and its checked-in evidence, including a measured negative.

### 1.4 Non-goals

1. 1. **No edit of `scripts/prompt-measurement-adapter.py`, `eval/runners/run-coding-task.py`,
   `scripts/prompt-fixed-adapter.py`, or `scripts/prompt-snapshot-helper.py`.** All four are
   byte-frozen `FILE_SET` members of `canonical-v1` **and** of `canonical-v1r`. Editing any of them
   breaks two merged evidence chains, not one. §2.5. 2. **No mutation of
   `eval/prompt/canonical-v1/`, `eval/prompt/canonical-v1r/`, `eval/prompt/gate/`,
   `eval/prompt/c4-repair-gate/`, `eval/tasks/prompt-v1/`, or `eval/tasks/prompt-v1r/`.** The C4
   evidence is now frozen on the same terms the C6 evidence was. 3. **No new attempt.** The cap
   stays one repair, two attempts. This capability changes what attempt 2 is *told*, not how many
   there are. 4. **No provider module change.** `src/provider_llama.align`,
   `src/provider_openai.align`, and `src/model.align` are untouched. 5. **No change to the
   evaluator's attempt loop, timing definition, or row schema.** `PROMPT_TASK_ROW` stays at
   `schema_version: 2`; §3.5 records that decision and its rejected alternative. 6. **No fix for
   mode 2.** The empty-patch mode is a prompt-format and edit-policy problem, and the fallback
   capability that owns it is named in §6.4. 7. **No prompt-quality, speed, provider-quality, or
   generality claim.** §6.3. 8. **No change to `src/repair.align` or
   `src/verification_loop.align`.** 9. **No failure-memory feedback.** C5 memory events are still
   not written or read across attempts.

### 1.5 Gate statement

**The C4 gate is met when, on the three-task corpus × two variants × two paired samples at
`temperature_micros: 0` and `seed_mode: PAIRED_FIXED`, at least one (task, variant) pair records
attempt 1 `FAIL` and attempt 2 `PASS` in *both* of its paired samples** — the identical predicate
`c4-repair-measured.md` §1.4 fixed, unchanged, so the two runs are directly comparable.

```text
gate MET  <=>  repair_recovery_paired_count >= 1
```

**The addressable arm, stated before the run.** Six of the ten repair attempts (§1.2, mode 1) can
carry a non-empty `EDITSET` section; four cannot. Three (task, variant) pairs are therefore live for
the gate: (`record-codec-round-trip`, PARENT), (`record-codec-round-trip`, CANDIDATE), and
(`duration-half-away-from-zero`, PARENT). The corpus aggregate gains
`repair_editset_attempt_count`, the count of repair attempts whose prompt actually included
`EDITSET`, so the denominator of any edit-set claim is a persisted number rather than an argument.
The expected value is 6; a value below 6 means the drop ladder fired or a mode-1 row changed mode,
and either is reported.

**What a `NOT_MET` result would then mean, fixed before the run.** If the six mode-1 attempts see
their own edits and still do not recover, the missing edit set was **not** the binding constraint,
and `c4-repair-measured.md` §5.7's tie-breaker is answered in the negative — which redirects the
next capability away from adapter surgery and toward the prompt, the template, and the edit policy.
That is a useful result and it is published as one. §6.3.

---

## 2. Probe record

No provider run, no `llama-server`, no Docker, and no model load was performed for this design.
Everything below is a static read of checked-in bytes on this branch's base. The design was written
against `b4cf98e`; every number was re-derived at the merged base `c07775c` before implementation,
and section 11.1 records the two figures that moved.

### 2.1 The adapter drops the edit set at exactly one place, and it is a local variable

`scripts/prompt-measurement-adapter.py` `measurement()` (line 1142) holds the model's output in
three locals and returns none of them:

```text
response  = run_generation_child(...)                     # the raw completion
edits     = validated_edit_set(response["content"], allowed_edits)   # [(path, body)]
patch     = ProducedInput(synthesized_patch(edits, source_root), "generated-patch")
```

`applied_edits = [path for path, _ in edits]` survives into `diagnostic_summary`; `patch.byte_count`
survives into `patch_size_bytes`; `patch` itself is closed in the `finally` block and the bodies go
out of scope. `assemble()` (line 1279) is handed `patch_byte_count`, an integer, and never sees the
bytes. This is `c4-repair-measured.md` §2.6 confirmed at the line level: the loss is one
assignment, not an architectural property.

It also fixes where the fix must live. `validated_edit_set` and `synthesized_patch` are **top-level
functions** (lines 302 and 428) with pure, total signatures — `(str, Sequence[str]) ->
list[tuple[str, str]]` and `(Sequence[tuple[str, str]], Path) -> bytes`. A second module can call
them directly and keep what `measurement()` discards.

### 2.2 The frozen adapter is import-safe, with exactly one module-level effect

Verified by reading the module top to bottom:

- The executable entry is guarded: `if __name__ == "__main__": raise SystemExit(main())` at line
  1444. Executing the module body does not run `main()`, does not parse `sys.argv`, and does not
  touch the filesystem for the request.
- Module level performs **one** effect: `CHILD_SUBREAPER_ENABLED = enable_child_subreaper()` at line
  100, which on Linux calls `prctl(PR_SET_CHILD_SUBREAPER, 1, …)` on the **importing** process and
  returns `False` everywhere else. Everything else at module level is constant or class/function
  definition.
- That effect is a prerequisite of the code being imported, not a side effect to be tolerated:
  `measurement()` raises `AdapterError("child-subreaper containment is unavailable")` unless
  `CHILD_SUBREAPER_ENABLED` is true. Importing the frozen module therefore establishes exactly the
  containment posture the frozen module demands, in the process that will own the children. The
  repair adapter must **not** set the flag itself; that would be a second writer for one process
  attribute.
- No `__init__`-time network, subprocess, or temporary-directory work exists anywhere in the module
  body.

### 2.3 Runtime identity is derived from `__file__`, and it is checked against the manifest

`runtime_identity()` (line 707) is `"PYTHON:" + sha256(Path(__file__).read_bytes())`, and
`environment_probe()` (line 711) embeds it. The consumer chain is not advisory:

```text
src/prompt_score.align:4757   row.measurement.environment_probe.producer == "MEASUREMENT_ADAPTER"
src/prompt_score.align:4758   row.measurement.environment_probe.runtime_identity
                                == task.measurement_adapter_runtime
scripts/prompt-evaluate.py:2265  helper.verify_unchanged(task["measurement_adapter_runtime"][7:])
scripts/prompt-evaluate.py:1269  the `argv` entry selects `measurement_adapter_runtime`
```

So the manifest's `measurement_adapter_runtime` must be the digest of the file named in `argv`, and
the probe the row carries must report the same digest. **A repair adapter that reused
`frozen.environment_probe()` would report the frozen adapter's digest while running its own code —
a false identity claim that the existing check would happily accept**, because the `prompt-v1e`
manifest would have had to declare the same false value to pass. §3.2 makes the repair adapter
produce its own identity and persist the base adapter's separately.

`producer` is *not* an enum in the artifact layer: `src/prompt_score.align:2767` only length-checks
it, and `"MEASUREMENT_ADAPTER"` is enforced in exactly one place, `:4757`, contextually. §3.2 keeps
that literal, because `producer` names a **role** and `runtime_identity` names a **file**.

A related gap, found while probing and closed by this capability: there is **no** producer or
runtime-identity check on an *attempt-level* measurement's probe. `verifier_ran_attempt_valid`
(`src/prompt_score.align:3022`) routes an attempt's measurement through `verifier_measurement_valid`
(`:2833`), which never inspects `environment_probe.producer`. Once a row runs twice, the row-level
check at `:4757` binds only the final attempt. §3.9 row 12 closes it.

### 2.4 The evaluator's repair machinery is already section-shaped

`scripts/prompt-evaluate.py` carries the whole assembly as data plus four small functions:

```text
REPAIR_SECTION_KINDS = ("STATUS", "SUMMARY", "STDOUT", "STDERR")     line 210
REPAIR_DROP_ORDER    = ("STDOUT", "STDERR", "SUMMARY")               line 214
repair_section_sources(measurement) -> dict[str, str]                line 1534
repair_prompt_text(template, base_text, sources, included) -> str    line 1549
assemble_repair_prompt(...) -> (text|None, included, dropped, bytes) line 1572
repair_eligibility(measurement) -> str                               line 1596
```

`valid_repair_template` (line 1509) requires `tuple(headers) == REPAIR_SECTION_KINDS` exactly, so a
fifth kind is a template change, hence a corpus-asset change, hence a new freeze — the same
mechanism that made `maximum_repair_loops` require one. Adding `EDITSET` is a five-line data change
in the evaluator plus one new source function; nothing about the loop, the re-derivation, the skip
reasons, or the timing moves.

### 2.5 Both frozen corpora are now immovable, and the shared members prove it

`eval/prompt/canonical-v1/corpus-file-set.manifest` declares 27 entries;
`eval/prompt/canonical-v1r/corpus-file-set.manifest` declares 29, in the form
`<mode> <path-byte-length> <path> <kind> <sha256>`, e.g.

```text
100755 37 scripts/prompt-measurement-adapter.py F 2d3796dbf1159d4a9528a62bbb9af0f36ccc5878b76d83aa65fa0d39cca7b20c
```

The 24 members the two share carry identical digests in both. `canonical-v1r/scope.json` pins
`corpus_revision.source_sha256 604f17bb…`, and `eval/prompt/c4-repair-gate/` was measured against
exactly that scope. **Editing `canonical-v1r` now costs the C4 evidence the same way editing
`canonical-v1` costs the C6 evidence.** There is also no in-place option even in principle: a
`prompt-v1e` task must name a different `argv` and a different `measurement_adapter_runtime`, which
changes its own `content_sha256`, which changes the corpus source digest. A third freeze is the only
shape available. §3.6.

The frozen adapter's digest appearing in `canonical-v1e`'s manifest at its unchanged value is not
bookkeeping: it is the machine-checkable form of this capability's central promise, and §3.2 binds
the repair adapter's hard-coded constant to it.

### 2.6 `make prompt-gate-check` is not available as evidence on this host

`HANDOFF.md` records that the C6 gate locator pins `generation_child_sha256 6650e448…`, a `./main`
built at the C6 head `762b1d0f` with the C6-era compiler, and that the bundle needs a clean checkout
at a tested head. The C4-REPAIR-MEASURED branch established the substitute and made it a permanent
regression: `validate_evaluation_pair` and `rescore` driven directly against the frozen
`eval/prompt/gate/` chain, plus an Align-side probe proving the frozen result and sidecar decode,
re-encode, and verify to `ImprovedEligible`. **This capability inherits that substitute and does not
claim `prompt-gate-check` as evidence.** §6.1 names what it runs instead, over both frozen chains.

### 2.7 The evaluator source pin and its size window, current state

`src/prompt_evaluate.align:8` pins `EVALUATOR_SOURCE_SHA256`; the window is now four chunks,
`EVALUATOR_ARG_CHUNK_BYTES * 3 < len <= * 4`, i.e. **196,609…262,144 bytes**, and
`EVALUATOR_BOOTSTRAP` pops four arguments (`c4-repair-measured.md` §10.2 deviation 5).
`scripts/prompt-evaluate.py` is **217,056 bytes** at the merged base `c07775c` — the C4 repair grew
it from `b4cf98e`'s 214,802 — leaving **45,088 bytes** of headroom. This capability's evaluator delta is a fifth section kind, one source function, one
aggregate, and a handful of ladder rows — comfortably inside it. Widening to five chunks is not
anticipated and is not planned; if implementation approaches the ceiling, that is a public change to
the launch contract and it comes back to this ledger before it is taken.

### 2.8 What the probes settle

1. The edit set is lost in one local variable and can be kept by a second module that calls the
   frozen top-level functions directly (2.1).
2. The frozen adapter is import-safe, and its single module-level effect is a prerequisite of the
   code being imported rather than a hazard (2.2).
3. The new adapter must produce its **own** runtime identity, or it persists a false one, and the
   existing checks would not catch it (2.3).
4. `EDITSET` is a template change and therefore a corpus change (2.4).
5. A third freeze, `canonical-v1e`, is mandatory; extending `canonical-v1r` is impossible in
   principle and would cost the C4 evidence in practice (2.5).
6. `make prompt-gate-check` is unavailable on this host; the C4 substitute is inherited and extended
   to both frozen chains (2.6).
7. The evaluator has 45,088 bytes of headroom; no window change is planned (2.7).
8. An attempt-level measurement's environment probe is unchecked today, and a row that runs twice
   makes that reachable (2.3).

---

## 3. Public-contract ledger

This ledger is the contract. If implementation discovers a different public promise, this table, the
closure matrix, the code, the fixtures, and the directly affected documentation are updated
together, before review.

### 3.1 The surface decision: a second adapter that imports the first

| Surface | Exact contract |
| --- | --- |
| New adapter | `scripts/prompt-repair-adapter.py`. Same CLI as the frozen adapter (`--prompt-variant`, `--rendered-prompt`, `--sample-index`, `--paired-seed`, `--adapter-request`, `--result`, `--result-fd`), same `TASK_ADAPTER_REQUEST` shape and field order, same sealing, same containment, same redaction. It differs in exactly two observable ways: it emits `TASK_MEASUREMENT` at `schema_version: 2`, and its `environment_probe.runtime_identity` is its own digest. |
| Base adapter | `scripts/prompt-measurement-adapter.py` is **byte-identical**, and is a member of `canonical-v1e`'s file-set manifest at its unchanged digest `2d3796db…`. It is loaded as a module, never edited, never copied, never re-implemented. |
| Validation runner | `eval/runners/run-coding-task.py` is **byte-identical**, a shared member at its unchanged digest. |
| Loop owner | `scripts/prompt-evaluate.py`, unchanged in structure. It renders, seals, invokes, and assembles exactly as `c4-repair-measured.md` §3.1 contracts. |
| Adapter selection | Purely a corpus property: the task manifest's `cmd`/`argv` name the adapter and `measurement_adapter_runtime` pins its digest. **There is no new CLI flag and no new environment variable.** `eval/prompt/gate/environment-policy.json` is reused byte-identical, so no new environment input is admissible. |
| Attempt bound | Unchanged: `1 + min(maximum_repair_loops, 1)`, and the corpus sets `maximum_repair_loops: 1`. |

**Why not extend the frozen adapter.** `c4-repair-measured.md` §5.7 option A, re-freezing
`canonical-v1`, is rejected for the reasons that document records and now costs a second evidence
chain as well (2.5).

**Why not the evaluator.** The evaluator never sees the generation response; only the adapter's
process does. Moving the response out of the adapter would mean the model's raw text crossing a
process boundary before redaction and bounding, which reverses the "redact, then bound, never the
other way round" order `bounded_diagnostic` exists to enforce.

**Why not monkeypatching.** A wrapper could rebind `frozen.validated_edit_set` and
`frozen.synthesized_patch` in the imported module's namespace to capturing shims, then call
`frozen.measurement()` unchanged, and no sequencing would be duplicated at all. **It is rejected.**
Three reasons, in order of weight: (1) it makes the *running* behaviour of a digest-verified module
differ from its verified bytes, which is precisely the property the digest is supposed to buy;
(2) the capture is invisible at the call site, so a reader of `measurement()` cannot see that a
global was replaced; (3) if the frozen function were ever inlined or renamed the capture would
silently produce *nothing* rather than an error — a silent-wrong-artifact hazard of the same class
as Request 52. The chosen route puts the divergence in a diff a reviewer can read, and §3.2 makes
its size an asserted number.

### 3.2 The import-by-path contract

| Surface | Exact contract |
| --- | --- |
| Load mechanism | The repair adapter reads `scripts/prompt-measurement-adapter.py` **once**, into memory, through the frozen `ImmutableInput`-style bounded read; computes SHA-256 over those exact bytes; refuses unless it equals the module constant `BASE_ADAPTER_SHA256`; and only then executes **those same bytes** as a module (`spec_from_file_location` semantics over a loader returning the verified bytes, or an equivalent `compile(raw, path, "exec")` into a fresh module namespace). The file is never read a second time for execution. Verify-then-execute on one byte sequence; no read-hash-read window. |
| `BASE_ADAPTER_SHA256` | The literal `2d3796dbf1159d4a9528a62bbb9af0f36ccc5878b76d83aa65fa0d39cca7b20c`, hard-coded in `scripts/prompt-repair-adapter.py`. |
| Three independent pins on the same file | (a) that constant; (b) `canonical-v1e/corpus-file-set.manifest`, which the gate validator verifies against the corpus root's bytes; (c) each `prompt-v1e` task manifest's `artifacts` entry, which the snapshot helper verifies **before and after every adapter invocation**. All three must agree; disagreement is fail-closed at ladder rows 2, 3, and 5 (§3.9). |
| `__file__` | Set to the frozen adapter's resolved path, so `frozen.runtime_identity()` and the `project = Path(__file__).resolve().parent.parent` idiom inside `main()` resolve exactly as they do when the frozen adapter runs standalone. `main()` is never called. |
| Base identity, cross-derived | `base_adapter_runtime_identity` is computed from the verified in-memory bytes and asserted equal to `frozen.runtime_identity()`, which re-reads the file. A mismatch means the file changed between the two reads and is `ERROR`/`BASE_ADAPTER`. Two derivations, one value, one check — not redundancy. |
| Own identity | `scripts/prompt-repair-adapter.py` defines its own `runtime_identity()` over its own `__file__`, and its own `environment_probe()` producing `producer: "MEASUREMENT_ADAPTER"` (the role is unchanged; §2.3) and `runtime_identity: "PYTHON:<own digest>"`. `prompt-v1e`'s `measurement_adapter_runtime` declares that value. |
| Module-level effect, disclosed | Executing the frozen module sets `PR_SET_CHILD_SUBREAPER` on the repair-adapter process (§2.2). The repair adapter does not set it and does not clear it; it reads `frozen.CHILD_SUBREAPER_ENABLED` and refuses to proceed when false, exactly as the frozen `measurement()` does. |
| Import-contract assertion | Immediately after execution, before any request is loaded, the repair adapter asserts that every consumed name exists in the module namespace with the expected kind (callable / class / `int` / `bytes` / `str`). A missing or wrong-kind name is `ERROR`/`BASE_ADAPTER` before any external call. |
| API privacy, stated | None of the consumed names is underscore-prefixed, and the frozen module's docstring describes a CLI adapter, not a library. **This capability consumes an undeclared internal API and says so.** The mitigation is not convention but immutability: the file is a digest-verified member of three frozen corpora, so it cannot change without minting a new corpus — which is the same event that would require re-reviewing the repair adapter. The residual risk is recorded in §6.6, not argued away. |
| Bounded divergence, asserted | The repair adapter's `measurement()` and `assemble()` are a deliberate near-copy of the frozen ones. `scripts/run-prompt-repair-adapter-smoke` extracts both sources from the two modules, applies a fixed normalizer, and asserts the unified diff equals a checked-in golden. Any drift in either function, in either file, turns it red. This converts §5.7's objection — "a second copy of containment logic is a second place for a containment bug" — into a bounded, machine-checked delta whose exact contents are reviewable as one artifact. |

**Consumed names, pinned by the file digest.** Everything else in the frozen module is unused.

| Kind | Names |
| --- | --- |
| Bounds | `REQUEST_LIMIT`, `ARTIFACT_LIMIT`, `RESULT_LIMIT`, `DIAGNOSTIC_LIMIT`, `SUMMARY_LIMIT`, `EXECUTABLE_LIMIT`, `MAXIMUM_FILE_BLOCKS`, `MAXIMUM_EDIT_BYTES`, `TRUNCATION_MARKER` |
| State | `CHILD_SUBREAPER_ENABLED` |
| Errors | `AdapterError`, `EditFormatError`, `PolicyViolation`, `GenerationFailure` |
| Sealed inputs | `ImmutableInput`, `ProducedInput` |
| Edit set | `validated_edit_set`, `synthesized_patch`, `task_edit_policy` |
| Digest / codec | `canonical_bytes`, `canonical_digest_bytes`, `bind_digest`, `valid_digest`, `decoded_artifact`, `load_request`, `same_path` |
| Redaction / bounding | `redact`, `redacted_bytes`, `bounded_diagnostic`, `bounded_text` |
| Execution | `child_environment`, `generation_request_document`, `run_generation_child`, `execute_validation`, `provider_identities` |
| Output | `write_exclusive`, `write_retained_result` |
| CLI | `parse_arguments` |
| Identity | `runtime_identity` (for the cross-derivation check only) |

**What the repair adapter defines itself, and nothing more:** `BASE_ADAPTER_SHA256`, the loader, the
import-contract assertion, `runtime_identity`, `environment_probe`, the edit-set record builders of
§3.3, a `measurement()` that keeps `edits` and the patch bytes, an `assemble()` that emits the four
version-2 members, and `main()`. Containment, sealing, redaction, process ownership, generation, and
validation are called, never re-implemented.

### 3.3 `TASK_MEASUREMENT`, `schema_version: 2`

Declared field order. The 21 version-1 fields are unchanged, in place, byte-for-byte. New members
are appended immediately before `content_sha256`, which is the position the canonical encoder and
every existing consumer already tolerate.

```text
TaskMeasurement:
  schema_version                      1 | 2
  artifact_kind: TASK_MEASUREMENT
  status                              PASS | FAIL | POLICY_VIOLATION | ERROR
  failure_kind                        NONE | TEST | POLICY | PATCH | CLEANUP | CONTAINMENT | ADAPTER
  build_status
  test_status
  repair_loop_count                   always 0 from either adapter
  unrelated_diff_count
  patch_size_bytes
  public_api_change_count
  policy_violation_count
  cleanup_passed
  containment_passed
  benchmark_regression_ppm: Option<i64>
  generation_to_passing_patch_ns: Option<i64>
  rendered_prompt_sha256
  generation_request: GenerationRequestIdentity
  environment_probe: EnvironmentProbe
  seed_attestation: SeedCapabilityAttestation
  diagnostic_summary
  diagnostic_stdout
  diagnostic_stderr
  edit_set: Option<[EditSetBlock]>                 new at 2
  edit_set_total_bytes: Option<i64>                new at 2
  patch_sha256: Option<str>                        new at 2
  base_adapter_runtime_identity: Option<str>       new at 2
  content_sha256
```

```text
EditSetBlock:
  schema_version                      1
  artifact_kind: EDIT_SET_BLOCK
  path                                a member of the task definition's allowed_edits
  body_bytes: i64                     the redacted body's full length, before any omission
  body_sha256                         over the redacted body bytes
  body_text: Option<str>              Some when the block is carried; None when omitted for budget
  content_sha256
```

**Presence rules, enforced in both directions.** This follows the mechanism `c4-repair-measured.md`
§10.2 deviation 10 established and proved at the pinned compiler: the new members are `Option`, the
canonical encoding omits an `Option::None`, and the verifier reads `schema_version` **first** and
then requires every version-2 member **present at 2 and absent at 1**. Presence never stands in for
a version, in either direction.

| Member | At version 1 | At version 2 |
| --- | --- | --- |
| `edit_set` | absent | `Some` exactly when `validated_edit_set` returned **and** a non-empty patch was synthesized from its return; `None` on `PATCH`, `POLICY`, `ERROR`-before-parse, and on the declared-patch path. The two clauses are not the same condition — a response can return a validated edit set whose every hunk is empty, and this corpus's dominant failure mode does exactly that. §11.3 deviation 14 records the measured consequence and owns the fix |
| `edit_set_total_bytes` | absent | `Some` exactly when `edit_set` is `Some`; the sum of `body_bytes` over every block, including omitted ones |
| `patch_sha256` | absent | `Some` exactly when a patch reached the validation runner; `None` otherwise |
| `base_adapter_runtime_identity` | absent | always `Some` |

**Invariants tying the new fields to the old ones**, all checked (§3.9):

```text
patch_sha256 is Some            <=>  patch_size_bytes > 0
edit_set is Some                 =>  every block path is in the task definition's allowed_edits
edit_set is Some                 =>  block paths are unique and sorted ascending
edit_set_total_bytes             =   sum(block.body_bytes)
diagnostic_summary's "applied edits:" list  ==  the edit_set paths, when edit_set is Some
```

The last one is the cheapest cross-check in the design and the most valuable: `diagnostic_summary`
is produced by the frozen `measurement()` sequencing from `applied_edits`, and `edit_set` is
produced from the same `edits` list, so a divergence means the near-copy of §3.2 diverged.

**Digests are over redacted bytes.** `body_sha256` and `patch_sha256` digest the bytes *after*
`redact_credential` has run, not before. A persisted digest of unredacted bytes is a credential
oracle: anyone holding a candidate credential could confirm it by recomputing the digest. The cost
is that with a credential-bearing provider the digest is a function of redaction as well as of
content — which is the correct trade and is stated here rather than discovered. `LOCAL_OPENAI` uses
no credential, so on this corpus the two are identical.

### 3.4 Where the four modes land, before the run

| Attempt-1 outcome | `edit_set` | `patch_sha256` | `EDITSET` section | Rows in the C4 run |
| --- | --- | --- | --- | --- |
| `PASS` | `Some` | `Some` | no repair attempt | 2 |
| `FAIL`/`TEST` | `Some` | `Some` | rendered | **6** |
| `FAIL`/`PATCH` | `None` | `None` | omitted (empty source) | 4 |
| `POLICY_VIOLATION`/`POLICY` | `None` | `None` | omitted (empty source) | 0 at attempt 1 |
| `ERROR` | `None` | `None` | repair `SKIPPED` per the existing eligibility rule | 0 |

The `FAIL`/`PATCH` row of this table is the one the run falsified in its *reason*, not its *shape*:
`edit_set` is indeed `None` there, but not because the response carried no edit set — it is because
the adapter discards a validated one when the synthesized patch turns out empty (§1.2, §11.3
deviation 14). The rendered outcome is unchanged; what changes is that "empty source" is a
consequence of this capability's own choice rather than of the model's answer.

No special case is added for the empty-`EDITSET` rows: a section whose source is empty is simply not
emitted, which is exactly how `SUMMARY`, `STDOUT`, and `STDERR` already behave
(`assemble_repair_prompt`, `included = [kind for kind in … if sources[kind]]`).
`repair_prompt_source.included_sections` records the absence, and
`repair_editset_attempt_count` (§1.5, §3.8) counts only the rows where it was present.

### 3.5 Persisted rows and evidence: what changes and what does not

Built up front, because the prior incident class is a persisted field list drifting away from what
its producer emits.

| Artifact | Version | Change |
| --- | --- | --- |
| `TASK_MEASUREMENT` | 1 → **2** | Four `Option` members (§3.3). Version 1 unchanged and permanently decodable. |
| `EDIT_SET_BLOCK` | **new, 1** | §3.3. |
| `REPAIR_PROMPT_TEMPLATE` | 1, **unchanged shape** | `section_headers` gains an `EDITSET` key; the record's field list does not move. A new template *file* in a new corpus, not a new schema. |
| `PROMPT_TASK_ROW` | 2, **unchanged** | No new field. §3.5's decision below. |
| `TaskAttemptRecord` | 1, **unchanged** | The edit set belongs to the measurement, whose producer is the adapter. Putting it on the attempt record would give it a second writer. |
| `RepairPromptSource` | 1, **unchanged** | `included_sections` / `dropped_sections` are `array<string>`; `EDITSET` is a new member of the existing vocabulary, not a new field. |
| `PROMPT_EVALUATION_RESULT` | 2, **unchanged** | |
| `PROMPT_EVALUATION_EVIDENCE`, `PROMPT_EXPECTED_INPUT_DIGEST` | 2, **unchanged** | |
| `TaskAggregate`, `CorpusAggregate` | version-2 `Option` block **extended** | One new member each: `parent_repair_editset_attempt_count` / `candidate_repair_editset_attempt_count` on the task aggregate, `repair_editset_attempt_count` on the corpus aggregate. Both are `Option`, absent at version 1, under the same present/absent rule. |
| `PROMPT_EVALUATION_TASK` | 1, **unchanged** | `prompt-v1e` manifests use the existing fields, including the `repair_template_path` / `repair_template_sha256` pair C4-REPAIR-MEASURED added. |
| `ENVIRONMENT_PROBE` | 1, **unchanged** | §2.3: `producer` stays `MEASUREMENT_ADAPTER`; only `runtime_identity` differs, which is what that field is for. |
| `TASK_ADAPTER_REQUEST`, `PROMPT_SCOPE`, `GENERATION_POLICY`, `EVALUATION_PROVIDER_CONTROL`, `PROMPT_ACCEPTANCE_POLICY`, `ENVIRONMENT_POLICY`, `PROVIDER_SERVICE_PROBE` | unchanged | |

**Decision: `PROMPT_TASK_ROW` stays at `schema_version: 2`.** The row gains no field. The rejected
alternative is a version 3 carrying the patch digest at row level: it would add nothing the nested
measurement does not already carry, and the container/member version-equality rule
(`c4-repair-measured.md` §3.2) would force `PROMPT_EVALUATION_RESULT`,
`PROMPT_EVALUATION_EVIDENCE`, and `PROMPT_EXPECTED_INPUT_DIGEST` to 3 in lockstep — four version
bumps and four sets of absence rules for zero new row fields. A version bump with no field change is
a false signal.

The measurement's version is therefore **decoupled** from the row's, which is not new: C4-REPAIR-
MEASURED moved the row to 2 while explicitly keeping the measurement at 1. What this capability adds
is a rule making the decoupling deterministic rather than free:

```text
a task whose measurement_adapter_runtime names the repair adapter
    => every ran attempt's measurement.schema_version == 2
a task whose measurement_adapter_runtime names any other adapter
    => every ran attempt's measurement.schema_version == 1
```

The measurement version is then a checked function of the corpus, not a variable a producer may
choose. Ladder row 11.

**Every persisted field list and its sole producer**, to be checked as one set in the author pass
and again in the matrix-to-diff pass:

| Field list | File | Producer of the bytes it describes |
| --- | --- | --- |
| `assemble()`'s literal dict | `scripts/prompt-measurement-adapter.py` | frozen; emits v1 only |
| `assemble()`'s literal dict | `scripts/prompt-fixed-adapter.py` | frozen; emits v1 only |
| the new `assemble()` | `scripts/prompt-repair-adapter.py` | emits v2 only |
| `TASK_MEASUREMENT_FIELDS` (line 93) | `scripts/prompt-evaluate.py` | consumer; becomes version-selected |
| `TaskMeasurement` record (line 594) | `src/prompt_artifacts.align` | consumer; gains four `Option` members |
| `verifier_measurement_valid` (line 2833) | `src/prompt_score.align` | validator; `schema_version == 1` becomes `1 or 2` plus presence rules |
| `verifier_measurement_equal` (line 2973) | `src/prompt_score.align` | field-wise equality; **must gain the four members or ladder row 18 silently weakens** |
| measurement constructors (lines 514, 1219, 1476) | `src/prompt_verifier_smoke.align` | fixtures; keep v1 cases, gain v2 cases |
| row-bearing fixtures | `src/prompt_render_smoke.align`, `src/prompt_render_parity_smoke.align`, `eval/fixtures/c6-prompt-state/templates.jsonl` | fixtures; keep v1 cases |
| smoke-built measurements | `scripts/run-prompt-evaluate-smoke`, `scripts/run-prompt-render-parity-smoke` | fixtures; gain v2 cases |

`verifier_measurement_equal` is called out because it is the one entry whose omission would not fail
anything: ladder row 18 (`row.measurement` byte-equal to the final attempt that ran) would still
pass while comparing 23 of 27 fields. It is the highest-value single line in the diff.

### 3.6 New and reused corpus assets

Nothing under `eval/prompt/canonical-v1/`, `eval/prompt/canonical-v1r/`, `eval/prompt/gate/`,
`eval/prompt/c4-repair-gate/`, `eval/tasks/prompt-v1/`, or `eval/tasks/prompt-v1r/` is modified,
moved, or deleted.

| Path | Contents |
| --- | --- |
| `scripts/prompt-repair-adapter.py` | §3.1, §3.2. A corpus member, mode `100755`. |
| `eval/tasks/prompt-v1e/duration-half-away-from-zero.json` | byte-for-byte the `prompt-v1r` manifest except `argv` and `cmd` naming the repair adapter, `measurement_adapter_runtime` at its digest, `generation_policy_path` and `repair_template_path` pointing at `canonical-v1e`, one added `artifacts` entry for the repair adapter (the frozen adapter's entry stays), and the recomputed `content_sha256`. `task_prompt_path`, `context_sources_path`, `task_definition_path`, `repo_path`, `repo_revision`, `validation_runner_path`, `validation_runner_sha256`, `validation_argv`, `snapshot_*`, `regression_limits`, and the rest of `artifacts` are `prompt-v1r`'s. |
| `eval/tasks/prompt-v1e/layer-precedence-frozen-module.json` | as above |
| `eval/tasks/prompt-v1e/record-codec-round-trip.json` | as above |
| `eval/prompt/canonical-v1e/repair-template.json` | `REPAIR_PROMPT_TEMPLATE`, `schema_version: 1`, `template_id: prompt-v1e-repair-v1`, five section headers. §4.2. |
| `eval/prompt/canonical-v1e/generation-policy.json` | `canonical-v1r`'s policy with `generation_policy_id: prompt-v1e-generation-v1` and the `provider_service_revision` **re-derived at freeze time**, never inherited (§3.7). `provider_control_sha256`, `max_prompt_bytes: 65536`, `max_tokens: 4096`, `temperature_micros: 0`, `seed_mode: PAIRED_FIXED`, `seed_base: 20260824` unchanged. |
| `eval/prompt/canonical-v1e/corpus.json` | `corpus_id: prompt-v1e`, naming the three `prompt-v1e` task files |
| `eval/prompt/canonical-v1e/corpus-file-set.manifest` | **30 entries**: `canonical-v1r`'s 24 shared members at **identical digests**, the 3 new task manifests, the new repair template, the new generation policy, and `scripts/prompt-repair-adapter.py`. `eval/runners/run-coding-task.py`, `scripts/prompt-measurement-adapter.py`, `scripts/prompt-fixed-adapter.py`, and `scripts/prompt-snapshot-helper.py` appear at the same digests as in both earlier manifests. |
| `eval/prompt/canonical-v1e/scope.json` | `corpus_id: prompt-v1e`, the new `corpus_revision`, the new `generation_policy_sha256`; `acceptance_policy_sha256`, `base_prompt_sha256`, `repo_prompt_sha256` **identical to `canonical-v1r`'s** and therefore to `canonical-v1`'s |
| `eval/prompt/canonical-v1e/prompt-activation-baseline-v1e.json` | the baseline activation over the new scope; the effective variant is byte-identical to `baseline-v1r`'s |
| `eval/prompt/canonical-v1e/README.md` | what is frozen, what is reused by digest, and the rule that it is never edited after measurement |
| `eval/prompt/c4-editset-gate/` | the measured evidence: `c4-editset-evaluation.json`, `c4-editset-evaluation-evidence.json`, `c4-editset-gate-record.json`, `README.md`. A separate directory; `eval/prompt/c4-repair-gate/` stays C4-REPAIR-MEASURED's. |
| `scripts/freeze-canonical-v1e` | mints the above reproducibly, as `scripts/freeze-canonical-v1r` does for `v1r` |
| `scripts/run-c4-editset-gate` | the run driver, mirroring `scripts/run-c4-repair-gate` |

Reused **by path, unmodified**: `eval/prompt/canonical-v1/base-prompt.json`, `repo-prompt.json`,
`evaluation-provider-control.json`, `prompt-acceptance-policy.json`;
`eval/prompt/gate/environment-policy.json`; every `eval/tasks/prompt-v1/<task>/` artifact; every
`eval/fixtures/prompt-v1-*/repository/` file; `eval/runners/run-coding-task.py`;
`scripts/prompt-measurement-adapter.py`; `scripts/prompt-fixed-adapter.py`;
`scripts/prompt-snapshot-helper.py`.

**The acceptance policy is reused byte-identical and is not relaxed**, on the same terms
`c4-repair-measured.md` §3.7 fixed: `maximum_repair_loop_regression_count: 0`, and a repair-loop
regression, if one occurs, is the measured result.

### 3.7 Provider topology and provider-revision evidence

Unchanged from `c4-repair-measured.md` §3.5 in every particular: `bwrap` inside a Linux aarch64
container built from the C6 measurement image plus `bwrap` and `socat` (`c4-repair-measure:latest`);
generation from inside that container to a container-local `socat` forwarder bound at
`127.0.0.1:18080`, proxying to the host `llama-server`; the provider control frozen and
digest-identical to C6's; `cap-add SYS_ADMIN` plus unconfined `seccomp`, `apparmor`, and
`systempaths`, published in the run record's `container_privileges`;
`scripts/probe-provider-service` emitting a fail-closed `PROVIDER_SERVICE_PROBE`; and the in-band
model-id check as the second half of the pair.

**The one rule this capability restates because it is easy to get wrong: the provider service
revision is re-derived at freeze time and never inherited.** `canonical-v1r`'s recorded value is

```text
llama.cpp/10566+bb4caa754;host:darwin-arm64;
server-sha256:b6ff7e912a9690ffec38878cad25b9ec1424a5537bd72010effe2fc9bfe64f74;
model-sha256:509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c
```

If the host binary or the model file has moved since, `canonical-v1e`'s policy records the observed
values and the probe fails closed against them. Copying the string forward would persist a false
claim about which service answered — the exact defect `c4-repair-measured.md` §2.5 caught in
`canonical-v1`'s policy.

The measurement-risk note carries over unchanged: neither the host probe nor the in-band model id
observes that the process answering inside the container is the process whose binary was hashed.

### 3.8 Scoring and aggregates

One new counted quantity, computed by the evaluator and **independently recomputed by the pure Align
verifier**, never trusted from the persisted document:

```text
task_aggregate:      parent_repair_editset_attempt_count, candidate_repair_editset_attempt_count
corpus_aggregate:    repair_editset_attempt_count
```

A repair attempt contributes when it ran (not `SKIPPED`) and its
`repair_prompt_source.included_sections` contains `EDITSET`. Both are `Option`, absent at version 1,
under the existing present-at-2 / absent-at-1 rule, and both extend the existing recomputation in
`verifier_task_repair_aggregate_matches` (`src/prompt_score.align:5266`) and
`verifier_corpus_repair_aggregate_matches` (`:5288`).

`repair_recovery_paired_count`, `repair_recovery_count`, `repair_attempt_count`,
`repair_loop_regression_count`, the `REPAIR_LOOPS` variant-symmetric check, and the C6 acceptance
arms are all **unchanged in mechanism and in value**. `verifier_reason_capacity`
(`src/prompt_score.align:5191`) does not move: no new per-pair serious-regression reason is added.

**The C4 gate consumes `repair_recovery_paired_count` only.** The C6 acceptance verdict is recorded
alongside as secondary evidence and is explicitly not a claim.

### 3.9 Validation order

First applicable row wins. This ladder **extends** `c4-repair-measured.md` §3.8; rows there that are
unchanged are not restated. Rows 1–9 run before any provider call or workspace mutation.

| # | Check | Failure |
| --- | --- | --- |
| 1 | Every §3.8 row of `c4-repair-measured.md` that is unchanged | as recorded there |
| 2 | The repair adapter's `BASE_ADAPTER_SHA256` equals the digest of the bytes it read, and those bytes are what it executes | `ERROR` / `BASE_ADAPTER` |
| 3 | `BASE_ADAPTER_SHA256` equals the `canonical-v1e` file-set manifest's entry for `scripts/prompt-measurement-adapter.py`, and equals that entry in `canonical-v1` and `canonical-v1r` | `INVALID_INPUT` / `SOURCE` |
| 4 | Every name in §3.2's consumed-name table exists in the loaded module with the expected kind | `ERROR` / `BASE_ADAPTER` |
| 5 | Each `prompt-v1e` task's `artifacts` list declares **both** adapters, and the snapshot helper verifies both before and after each invocation | `INVALID_INPUT` / `SOURCE` |
| 6 | `frozen.CHILD_SUBREAPER_ENABLED` is true | `ERROR` / `ADAPTER` |
| 7 | `base_adapter_runtime_identity` computed from the verified bytes equals `frozen.runtime_identity()` | `ERROR` / `BASE_ADAPTER` |
| 8 | The repair template decodes, its `section_headers` keys equal `("STATUS","EDITSET","SUMMARY","STDOUT","STDERR")` exactly, and its digest equals the task manifest's `repair_template_sha256` | `INVALID_INPUT` / `TEMPLATE` |
| — | *attempt 1 runs* | |
| 9 | The adapter result decodes as `TASK_MEASUREMENT` with `schema_version` in `{1,2}` and `artifact_kind == "TASK_MEASUREMENT"` | `ERROR` / `ADAPTER` |
| 10 | Every version-2 member is present at version 2 and **absent** at version 1 | `INVALID_INPUT` / `SCHEMA` |
| 11 | The measurement version equals the version the task's declared adapter runtime requires (§3.5) | `INVALID_INPUT` / `SCHEMA` |
| 12 | Every ran attempt's `measurement.environment_probe.producer == "MEASUREMENT_ADAPTER"` and its `runtime_identity == task.measurement_adapter_runtime` — the §2.3 gap, closed at attempt level | `INVALID_INPUT` / `IDENTITY` |
| 13 | `patch_sha256` is `Some` iff `patch_size_bytes > 0`; when `Some` it is a valid lowercase 64-hex digest | `INVALID_INPUT` / `EDIT_SET` |
| 14 | `edit_set_total_bytes` is `Some` iff `edit_set` is `Some`, and equals the sum of `body_bytes` | `INVALID_INPUT` / `EDIT_SET` |
| 15 | Every `EditSetBlock` decodes; `path` is non-empty, is a member of the task definition's `allowed_edits`, and paths are unique and sorted ascending; `body_bytes >= 0`; `body_sha256` is a valid digest; `body_sha256` equals the digest of `body_text` when `body_text` is `Some` | `INVALID_INPUT` / `EDIT_SET` |
| 16 | The block count is at most `MAXIMUM_FILE_BLOCKS` (32) and each `body_bytes` at most `MAXIMUM_EDIT_BYTES` | `INVALID_INPUT` / `EDIT_SET` |
| 17 | When `edit_set` is `Some`, its paths equal the path list `diagnostic_summary` names after `applied edits: ` | `INVALID_INPUT` / `EDIT_SET` |
| 18 | Repair eligibility, unchanged: cleanup and containment passed, and at least one of `SUMMARY`/`STDOUT`/`STDERR` is non-empty. **`EDITSET` alone does not make a repair eligible** — a run with no diagnostics at all is still `SKIPPED` | attempt 2 `SKIPPED` / `REPAIR_INPUT_UNAVAILABLE` |
| 19 | The assembled repair prompt is valid UTF-8 and `<= max_prompt_bytes` after the §4.4 ladder | attempt 2 `SKIPPED` / `REPAIR_PROMPT_BUDGET` |
| 20 | The repair prompt is byte-equal to `assemble(template, attempt 1's persisted fields)`, with `EDITSET` re-derived from the persisted `edit_set` | `ERROR` / `REPAIR_RENDER` |
| — | *attempt 2 runs; rows 9–17 repeat for it* | |
| 21 | `repair_editset_attempt_count` equals the recomputed count of ran repair attempts whose `included_sections` contains `EDITSET` | `INVALID_INPUT` / `AGGREGATE` |
| 22 | `verifier_measurement_equal` compares **all 27** version-2 fields when both sides are version 2 | `INVALID_INPUT` / `MEASUREMENT_BINDING` |

Rows 18 and 19 are terminal-but-not-error: the row closes with a recorded `SKIPPED` repair attempt
carrying its reason.

### 3.10 Ownership, allocation, lifetime, cleanup

| Surface | Exact contract |
| --- | --- |
| Loaded module | One module object per adapter process, created before the request is loaded and living until the process exits. It is never reloaded, never mutated, and never shared across invocations — each attempt is its own process. |
| Edit-set bytes | The block bodies are materialized once, from `validated_edit_set`'s return, redacted, digested, and encoded into the result. They are not re-read from the workspace, not re-derived from the response, and not retained past `assemble()`. |
| Patch bytes | `ProducedInput` continues to own the synthesized patch and to be closed in the frozen `finally` block. `patch_sha256` is computed from the redacted bytes **before** the `ProducedInput` is constructed, so nothing borrows a released descriptor. |
| Attempt workspaces | Unchanged: one workspace and result path per attempt, fixed-width `-a1`/`-a2` suffixes on a fixed-depth run directory, bounded and asserted components. Prior incident class: `ENAMETOOLONG`. |
| Cleanup order | Unchanged, including the rule that a cleanup failure in attempt 1 suppresses attempt 2 as `SKIPPED`/`REPAIR_INPUT_UNAVAILABLE`. |
| Align side | The `edit_set` array is a bounded slice whose length is checked against `MAXIMUM_FILE_BLOCKS` before allocation, and every `Option` member is read through a `borrow` binding (§6.7). |
| Credentials | Unchanged. `credential_env_name` is never rendered, never logged, and never enters a repair prompt. Redaction runs before bounding and before digesting (§3.3). |

### 3.11 The evaluator source pin and its size window

| Surface | Exact contract |
| --- | --- |
| `EVALUATOR_SOURCE_SHA256` | `src/prompt_evaluate.align:8` is updated to the new `scripts/prompt-evaluate.py` digest in the same commit that changes the file. |
| Size window | Four chunks, 196,609…262,144 bytes. The file is 217,056 bytes at the base, so the delta has **45,088 bytes** of headroom (§2.7). Realized: 235,059 bytes after the review repair, **27,085 bytes** of headroom (§11.1). |
| If the budget is exceeded | It returns to this ledger as a public change to the launch contract, before implementation, not after. No widening is planned. |
| What is not acceptable | Splitting the evaluator into a second file to dodge the window. |

### 3.12 Ledger dimensions

| Dimension | Answer |
| --- | --- |
| Exact commands and operands | §3.1 (no new flag, no new environment variable); §6.1 (owners); §6.2 (`make c4-editset-gate` and its three explicit inputs) |
| Inputs and defaults | §3.6. `maximum_repair_loops` stays 1; `max_prompt_bytes` stays 65,536; `EDIT_SET_LIMIT` is a new producer-side constant, 16,384 (§4.3) |
| Results, statuses, errors, precedence | §3.3 (`edit_set` presence by outcome), §3.4 (the four modes), §3.9 (22-row first-applicable ladder) |
| Ownership, lifetime, allocation, cleanup | §3.10 |
| Owner module | `scripts/prompt-repair-adapter.py` owns the edit set and the two digests. `scripts/prompt-evaluate.py` owns rendering, the ladder rows above the adapter boundary, and the aggregate. `src/prompt_score.align` owns independent recomputation. No field has two writers (§3.5) |
| Text and wire boundary | Canonical UTF-8 JSON, declaration order, integer-only comparisons, `Option::None` omitted. Block bodies are whole-block or absent, so **no UTF-8 code point is ever split by this capability** (§4.3). Embedded NUL is impossible: the frozen `bounded_text` decodes with `errors="replace"` and the JSON encoder escapes control characters |
| Persisted/cache identity | `artifact_kind` + `schema_version`, nominal; `content_sha256` over the canonical preimage with only the record's own digest field blanked. No cache is introduced |
| Schema version | `TASK_MEASUREMENT` 1 → 2; `EDIT_SET_BLOCK` new at 1; task and corpus aggregates gain one `Option` member each inside their existing version-2 block. Every other record, listed in §3.5, is unchanged |
| Validation order | §3.9 |
| Prerequisites | §6.5 |
| CLI, build, and environment inputs | §3.1. The evaluator reads exactly one environment value today (the provider credential) and continues to. Build inputs change through §3.11's pin and one new `.PHONY` target (§6.2) |
| Acceptance evidence | §6.1 (owner tests, no provider), §6.2 (the named gate qualification) |
| Metrics | §6.3 |
| Cost ceiling | §6.2: **60 minutes wall clock**, recorded before implementation |
| Minimum tool/platform versions | Docker 28.5.1; `c4-repair-measure:latest` on linux/aarch64 with `bwrap`, `prlimit`, `git`, `/usr/bin/python3`, `socat`; llama.cpp build 10566 (`bb4caa754`); Align `3a34febe912db5096c58c74fede36ff53f223e04` per `.align-revision` |
| Milestones not consuming a later slice | §1.4 and §6.4: one repair, three tasks, no memory feedback, no policy change, no provider change, no mode-2 fix |
| Runtime-inspection fields | `edit_set`, `edit_set_total_bytes`, `patch_sha256`, `base_adapter_runtime_identity` are producer-owned measured values written by the process that held the bytes; no reflection, no artifact re-read at report time |
| Normative examples | §4.2's template text and §4.3's rendered form are the only normative examples; the render-parity smoke turns both into byte goldens |

**Ledger field completion.** *Cache identity* is `N/A`: no cache is introduced, nothing is memoized
between attempts, and the loaded module is per-process. *Generic monomorphization,
compiler-interface serialization, native ABI* are `N/A`: the changed records are concrete and no
`extern` symbol, FFI boundary, or compiler surface is touched. *Concurrency and shared process
state* are `N/A`: attempts are strictly sequential within a row and rows within the run; the only
shared resource is the single `llama-server`, whose serialization is its own and is unchanged.
*Platform-local performance claims* are `N/A`: §6.3 makes no speed claim, so no native platform
profile is selected. The `ppm`-floor rule of `docs/specs/c8-speed-first.md` §1 is `N/A` because no
seam is optimized; §6.2's ceiling is a **run-cost** ceiling under the performance row's "cost
ceiling recorded before implementation" clause, not an optimization ceiling. *Minimum-version
acceptance evidence* is supplementary only: the gate runs on one host and claims nothing about
others.

---

## 4. The repair-prompt contract, version 2

### 4.1 Principle

Unchanged from `c4-repair-measured.md` §4.1: the repair prompt is a **pure, total function of bytes
the result document already persists**, plus one sealed corpus template. `EDITSET` does not weaken
that; it is what makes the persisted `edit_set` load-bearing. Before this capability the edit set
existed only inside a process; after it, the edit set is persisted first and rendered from the
persisted form, never from a live value.

That ordering is a rule, not an implementation detail: the evaluator renders `EDITSET` from
`attempts[0].measurement.edit_set` as decoded from the adapter's result document, exactly as it
renders `STDOUT` from `diagnostic_stdout`. If a block was omitted for budget at the producer, the
prompt cannot show it either, and the two stay in agreement by construction.

### 4.2 The sealed template

`eval/prompt/canonical-v1e/repair-template.json`, `REPAIR_PROMPT_TEMPLATE`, `schema_version: 1`,
`template_id: prompt-v1e-repair-v1`. The record shape is unchanged; `section_headers` carries five
keys in the §4.3 order.

The preamble keeps `canonical-v1r`'s text — the same four requirements, the same whole-file format
statement, the same "smallest change that makes the validation command exit zero" — and adds one
paragraph stating that the previous attempt's own edits follow, in the same format the answer must
use, and that they are the exact text that was applied and rejected. The `EDITSET` header names it
as the previous attempt's answer, not as a suggestion. The closing text is unchanged: it repeats the
format instruction, because that is the instruction the model is most likely to drop under a long
prompt — and mode 2 (§1.2) is direct evidence that this model does drop it.

**One risk the template must actively manage.** Showing the model its own previous answer invites it
to return that answer again — the copy-forward failure that a naive "here is what you wrote" prompt
produces. The preamble therefore states the previous answer's status as *rejected by the
repository's own validation*, adjacent to the status labels, before the blocks appear. Whether that
is sufficient is exactly what the gate measures; it is not asserted here.

The task prompt and the variant's base and repo prompts are rendered **byte-identically to attempt
1**, and the repair sections are appended, not substituted, so a version-2 repair prompt remains a
strict textual extension of its attempt-1 prompt.

### 4.3 Sections, order, and bounds

```text
REPAIR_SECTION_KINDS = ("STATUS", "EDITSET", "SUMMARY", "STDOUT", "STDERR")
```

| # | Section | Source | Bound |
| --- | --- | --- | --- |
| 1 | `STATUS` | attempt 1's `measurement.status`, `failure_kind`, `build_status`, `test_status`, one label per line | 128 |
| 2 | `EDITSET` | attempt 1's `measurement.edit_set` | 16,384 (`EDIT_SET_LIMIT`, applied at the producer) |
| 3 | `SUMMARY` | attempt 1's `measurement.diagnostic_summary` | 4,096 (`SUMMARY_LIMIT`) |
| 4 | `STDOUT` | attempt 1's `measurement.diagnostic_stdout` | 16,384 (`DIAGNOSTIC_LIMIT`) |
| 5 | `STDERR` | attempt 1's `measurement.diagnostic_stderr` | 16,384 (`DIAGNOSTIC_LIMIT`) |

`EDITSET` sits immediately after `STATUS` so the model reads the verdict and then what produced it,
before the output describing it. **The four existing sections keep their relative order**, so a
version-2 prompt with `EDITSET` absent has the same section sequence as a `canonical-v1r` prompt.

**`EDITSET` is rendered in the response's own format**, one `FILE:` line and one fenced block per
carried edit, in the sorted path order `validated_edit_set` returns:

````text
FILE: src/duration.py
```
<the exact body_text bytes>
```
````

Format-consistency is deliberate. A prompt that displayed a unified diff while demanding whole files
would ask the model to translate between two formats under a long prompt, which is work the answer
format does not need. (An earlier draft justified this by mode 2 "failing the whole-file format";
§1.2 records that mode 2 is a no-op answer rather than a format failure, so the argument stands on
its own terms and not on that evidence.) The rejected alternative — rendering the synthesized
unified diff — is smaller on the wire and is a *different* format from the one required, and is
rejected for that reason. The fence run is chosen longer than any run appearing in the body, using
the frozen `fence_run` / `closing_fence` rule, so a body containing fenced text nests correctly.

**Producer-side bounding, whole-block, and the carried set is a prefix.** The repair adapter carries
blocks in the sorted order until the running total of `body_bytes` would exceed
`EDIT_SET_LIMIT = 16,384`; that block **and every block after it** are persisted with
`body_text: None` and their `path`, `body_bytes`, and `body_sha256` intact. The rejected
alternative is a greedy best fit that keeps looking for a later block that still fits: it carries
more bytes, and it is rejected because the section the model reads would then omit an earlier file
while showing a later one, so the rendered answer would no longer be a prefix of the answer the
model actually gave. An omitted block is rendered as one line naming its path and byte count, never
as a partial file. A
half-truncated source file would be worse than none: it would invite the model to "complete" a file
it can only half see, and the whole-file format makes that a silent data-loss patch.

16,384 matches `DIAGNOSTIC_LIMIT`, so the four bounded sections sum to at most 36,992 + 16,384 =
53,376 bytes on top of an attempt-1 prompt. Against the C4 run's measured assembled sizes of 8,123
to 16,129 bytes over 65,536, the expectation is that the ladder still never fires. §4.4 says what
happens when it does.

### 4.4 The drop ladder, and why `EDITSET` is dropped last

```text
REPAIR_DROP_ORDER = ("STDOUT", "STDERR", "SUMMARY", "EDITSET")
```

`STATUS` remains the only never-dropped section. **This is a decision, and it is argued from the C4
failure modes rather than from tidiness.**

*Why `EDITSET` is not dropped first, before the diagnostics.* The C4 run measured what a repair
prompt carrying only the diagnostics achieves on this corpus: zero recoveries in ten attempts, and
six of six mode-1 attempts re-emitting an identical-size patch. Dropping `EDITSET` early would make
an over-budget row **silently degrade into the experiment that already returned a negative**, and
its evidence would look like an edit-set attempt while being a re-run of C4-REPAIR-MEASURED. The
section this capability exists to add must outlive the sections it already knows to be insufficient
alone.

*Why `EDITSET` is nevertheless droppable, rather than joining `STATUS`.* `EDITSET` is the only
section that can blow the budget by itself — up to 32 blocks against four fixed-size streams — so
making it undroppable would convert an over-budget row from "a weaker repair attempt" into
`SKIPPED`/`REPAIR_PROMPT_BUDGET`: **no provider call, no measurement, a hole in the run.** Losing a
measurement is worse than making one under a degraded prompt, provided the degradation is recorded.

*Why the loss is never silent.* `repair_prompt_source.dropped_sections` names every dropped section,
and `repair_editset_attempt_count` (§3.8) counts only attempts whose prompt actually carried
`EDITSET`. A row that dropped it is excluded from the denominator of every edit-set claim, by a
persisted number rather than by an argument in a pull request.

*The order among the other three is unchanged* — `STDOUT` before `STDERR` before `SUMMARY` — because
nothing measured suggests it is wrong and changing it would make the two runs' prompts differ for a
second, unrelated reason.

If the prompt still exceeds the budget with only the preamble, headers, attempt-1 text, and
`STATUS`, the repair attempt is `SKIPPED`/`REPAIR_PROMPT_BUDGET` and no provider call is made.

### 4.5 Re-derivability

Given a persisted version-2 row and the sealed template, a verifier recomputes

```text
assemble(template,
         attempts[0].measurement.status, failure_kind, build_status, test_status,
         attempts[0].measurement.edit_set,
         attempts[0].measurement.diagnostic_summary,
         attempts[0].measurement.diagnostic_stdout,
         attempts[0].measurement.diagnostic_stderr,
         included_sections, dropped_sections)
```

and requires the result's SHA-256 to equal `attempts[1].rendered_prompt_sha256` and
`attempts[1].generation_request.user_text_sha256`. Ladder row 20 makes the producer run this against
its own output; the evidence sidecar makes an independent producer run it again.

**Measurement-risk note, restated because `EDITSET` changes its shape slightly.** The repair
prompt's content is a function of the model's own attempt-1 output, so no verifier can derive it
from the frozen assets alone. What `EDITSET` adds is that the *largest* input to the repair prompt
is now itself persisted with a digest, so the claim strengthens from "this prompt is the recorded
assembly of the recorded attempt" to "…and the model's own text inside it hashes to the value the
producer recorded when it held the bytes." What remains merely observed is the attempt-1 output
itself. That is still the strongest statement available for a reactive loop.

### 4.6 What never enters a repair prompt, and what now does

**Never**, unchanged: any environment-variable value; any credential or credential env name; the
container hostname, `host.docker.internal`, the endpoint, the model path, or any Docker or
bind-mount detail; the `PROVIDER_SERVICE_PROBE`; any path the evaluator or the adapter constructs;
any other task's fixtures or diagnostics; any cross-sample or cross-variant content.

**Disclosed and inherited**, unchanged: the sandbox `mkdtemp` suffix already present in the frozen
diagnostics — e.g. `/tmp/align-llm-coding-task-076agahm/repository/tests/test_duration.py` — which
originates in the frozen `run-coding-task.py` and cannot be scrubbed here without breaking §4.5's
re-derivation. It is a temp directory name: no user path, no home directory, no credential, no host
identity. `c4-repair-measured.md` §5.4 holds the upstream fix.

**New in this capability, and it is worth naming explicitly: the model's own generated text is now
persisted and re-rendered.** Three properties bound it. (1) It is confined to files in the task
definition's `allowed_edits` — `validated_edit_set` refuses anything else before the block is kept,
so a block naming a path outside the set never reaches the record. (2) It passes through
`redact_credential` before it is digested or persisted, in the frozen order. (3) It is bounded at
`EDIT_SET_LIMIT` whole-block. The content is a rewritten copy of a checked-in fixture file — text
this repository already carries — not arbitrary model output about arbitrary subject matter. It is
still model output, and a reviewer should read a sample of the realized `edit_set` blocks in the
gate evidence rather than take that on trust.

---

## 5. Nondeterminism handling

Every quantity this capability introduces is a function of persisted bytes, and none of them is a
timing. That is deliberate, because the C4 run measured how little this path's timings support.

**What the C4 run measured about nondeterminism.** 22 provider calls at `temperature_micros: 0` with
greedy decoding, recomputed from the checked-in evidence at `c07775c`: `adapter_elapsed_ns` ranged
**7.98 s to 64.67 s**, median **18.59 s**, an **8.1× spread**, against `c4-repair-measured.md`
§2.1's 3.5× at `n=2`. Wall clock **824.243 s = 13.74 min**. `adapter_overhead_ns` on the two passing
attempts was **91.04 ms and 91.77 ms**. (The design's first draft quoted the C4 branch's *first*
run — 8.13–73.82 s, median 18.27 s, 9.1×, 14.69 min, 65.74/74.11 ms; the published evidence is the
second, clean-head run, and these are its figures. Every correctness value is identical between the
two runs; only the clocks moved, which is itself why §6.3 refuses a speed claim.) The two paired
samples of a row differ only in `paired_seed`, and a seed cannot change a greedy decode's output, so
the spread is server state, prompt-cache reuse, and host contention — not the sampling distribution.

**What follows for this design.**

1. **No timing is a gate input, a threshold, or a claim.** The gate predicate is a status pattern
   over two paired samples (§1.5). §6.3 refuses a speed claim outright.
2. **The reproducibility requirement is the paired predicate itself.** A recovery counts only when
   both samples of a (task, variant) pair recover. A single lucky sample is not a gate.
3. **Content nondeterminism is now measurable for the first time.** `patch_sha256` makes "attempt 2
   re-sent attempt 1's patch" and "sample 1 and sample 2 produced the same patch" checkable facts
   rather than inferences from a byte count. The gate does not consume either; both are reported.
4. **Prompt-cache reuse is a plausible confound and is not controlled.** The repair prompt is a
   strict textual extension of the attempt-1 prompt (§4.2), so a server caching the shared prefix
   makes attempt 2 cheaper than attempt 1 for reasons unrelated to the model. This affects timings
   only, and no timing is claimed. It is recorded so that a future capability that *does* claim a
   timing knows the confound exists.
5. **The evaluation is not re-run for a better result.** One gate run is recorded. If it must be
   re-run for an operational failure — a crashed server, a container that did not come up — the
   reason and both runs' outcomes are recorded, exactly as `c4-repair-measured.md` §10.3 recorded a
   first run that failed to publish.

---

## 6. Fixtures, qualification, metrics, deferrals, risks

### 6.1 Owner tests — deterministic, offline, no provider

| Owner | Adds |
| --- | --- |
| `scripts/run-prompt-repair-adapter-smoke` **(new)** | The import-by-path contract: verify-then-execute over one byte sequence; a mutated base file rejected; every consumed name present and of the expected kind; a removed name rejected; `base_adapter_runtime_identity` cross-derivation and its mismatch case; `producer` and own-`runtime_identity` values; the §4.3 budget as a pure function, separating a prefix cut from a greedy best fit; the §3.2 **bounded-divergence golden** over `measurement()` and `assemble()` with the compared span taken from the parser; and the version-2 `assemble()` output shape for each of the four §3.4 modes, driven by a stub generation child rather than a provider |
| `scripts/run-prompt-evaluate-smoke` | `EDITSET` through the loop against the deterministic `scripts/prompt-fixed-adapter.py` and a v2-emitting stub: an attempt-1 measurement with `edit_set` `Some` (section rendered), with `edit_set` `None` (section omitted), with an omitted block (placeholder line), the version-2 ladder rows 9–21 one case each, the version-selected `TASK_MEASUREMENT_FIELDS`, and `repair_editset_attempt_count` |
| `scripts/run-prompt-render-parity-smoke` | The §4.5 re-derivation as a byte golden with `EDITSET` present, with it absent, and with each block omitted; **each of the four drop-ladder steps as its own golden, including the new final `EDITSET` drop**; the budget-exhaustion `SKIPPED` case; a redaction case proving no credential, endpoint, or constructed path survives assembly; and a nested-fence case proving a body containing a fenced block round-trips |
| `scripts/run-prompt-score-smoke` | Version-2 measurement decode; **version-1 measurement decode unchanged**; the present-at-2 / absent-at-1 rule in both directions; the §3.3 invariants; `verifier_measurement_equal` over all 27 fields; the new aggregates |
| `scripts/run-prompt-gate-validator-smoke` | Version-2 evidence carrying version-2 measurements over a **two-block** edit set; the new aggregates recomputed by `rescore`; the attempt-level probe-identity check of ladder row 12; edit-set path order, path uniqueness, and the row-14 sum as rejection rows; the version-1 absence rule driven directly, one row per member, because ladder row 11 makes it unreachable through this fixture's corpus; the accepted truncated-summary row; **and the inherited regression asserting that the frozen version-1 chain *and* the frozen C4 version-2 chain both still validate and rescore byte-identically** |
| `scripts/run-prompt-measurement-adapter-smoke` | **Unchanged and must stay green.** Its passing is part of the proof that the frozen adapter still behaves as reviewed while being imported elsewhere |
| `make gate-topology-check` | Must pass with its byte-literal `EXPECTED` unmoved. `c4-editset-gate` joins no aggregate, exactly as `c4-repair-gate` does not. If `EXPECTED` moves, that is a check-topology change and it selects `make ci` per `CLAUDE.md` |
| `make check`, `make fmt`, `make format-check`, `make build` | The Align side: `src/prompt_artifacts.align`, `src/prompt_score.align`, `src/prompt_model.align`, `src/prompt_evaluate.align` (the §3.11 pin) |
| Row-bearing fixtures | `src/prompt_verifier_smoke.align` (a defect for each new presence rule, mutation-tested as defect 8 was), `src/prompt_render_smoke.align`, `src/prompt_render_parity_smoke.align`, and `eval/fixtures/c6-prompt-state/templates.jsonl` gain version-2 measurement cases and keep every version-1 case unchanged |

**The frozen-chain regressions are not optional politeness.** Two merged evidence chains now depend
on version-1 measurement decode — C6's and C4-REPAIR-MEASURED's — and `make prompt-gate-check` is
unavailable on this host (§2.6). The `validate_evaluation_pair` / `rescore` regression is the only
thing standing between a version-2-shaped decoder and the deletion of both.

### 6.2 The named qualification and its cost ceiling

```text
make c4-editset-gate \
  C4_EDITSET_SCOPE=eval/prompt/canonical-v1e/scope.json \
  C4_EDITSET_PROVIDER_PROBE=<absolute path to the PROVIDER_SERVICE_PROBE document> \
  C4_EDITSET_OUT=eval/prompt/c4-editset-gate/
```

A named focused qualification. **It joins no aggregate** — not `make ci`, not `hosted-checks`, not
`capable-checks` — for the reasons `c4-repair-measured.md` §5.2 records and the Makefile comment
already states: a provider-dependent, model-dependent, tens-of-minutes step in the routine path is
what `CLAUDE.md`'s verification section forbids. A missing or empty `C4_EDITSET_*` value fails
before the run starts.

**Cost ceiling, recorded before implementation.** The call count is unchanged from the C4 run: 12
initial attempts, at most 10 repair attempts, **at most 22 provider generation calls**. The C4 run
took **13.74 minutes** for exactly those 22 calls. The repair prompts grow by at most
`EDIT_SET_LIMIT` = 16,384 bytes on six of them, which lengthens prefill on those six only.

```text
expected gate run time:  12-30 minutes wall clock
recorded cost ceiling:   60 minutes wall clock, single run, this host
per-attempt ceiling:     provider_control.timeout_ns = 1,800,000,000,000 ns (1,800 s)
per-attempt observed:    7.98 s - 64.67 s, median 18.59 s (n=22, the C4 run)
```

**If a run exceeds 60 minutes, the capability stops and the boundary is reconsidered** rather than
the ceiling being raised after the fact.

The run records, in the C8 house form: the align-llm commit; `.align-revision`; the Docker image
digest and `docker version`; the forwarder command; the container privileges; the host
`llama-server` version string, binary SHA-256, and model SHA-256; the exact `make` command; the
container's OS, kernel, architecture, and logical CPU count; and the measured wall clock against the
ceiling.

### 6.3 Metrics, and what the measured claim is and is not

**Primary: `repair_recovery_paired_count`** — the §1.5 gate quantity — with `repair_attempt_count`
and the new `repair_editset_attempt_count` as its denominators.

**Secondary: `generation_to_passing_patch_ns`**, the evaluator-observed total including the repair,
reported per row and as the median over rows that reached a pass. Reported, not claimed.

**Reported alongside, and new: patch identity.** For every mode-1 row, whether
`attempts[1].measurement.patch_sha256` equals `attempts[0].measurement.patch_sha256`. This is the
question the C4 run could only answer as "the same size", and it is the sharpest single fact this
capability produces regardless of the gate's outcome.

**What this capability claims.** That the provider-backed measurement path can carry a bounded,
redacted, digest-verified copy of a failing attempt's own edits into its repair prompt, through a
second adapter that reuses the reviewed containment core without editing it; that the resulting
prompt is re-derivable from persisted evidence; and, if the gate is `MET`, that at least one task
recovered from a first-attempt failure reproducibly across both paired samples.

**What it does not claim.** **No speed claim of any kind** — §5's 8.1× spread at temperature 0
supports no baseline, no floor, and no comparison, and the prompt-cache confound is uncontrolled.
**No prompt-quality claim**: the CANDIDATE variant is not asserted to be better and the C6
acceptance verdict is secondary evidence only. **No provider-quality claim**: one model, one build,
one host. **No generality claim**: three tasks, one repository family, one language, and only six of
ten repair attempts are even addressable. **No claim that the edit set is the binding constraint** —
that is the hypothesis under test, and §1.5 fixes both readings of the result before the run.

If `repair_recovery_paired_count == 0`, the reported result is: the loop ran, `EDITSET` was carried
on N attempts, none recovered, here are the realized repair prompts' digests and the realized
patch-digest comparisons — and `c4-repair-measured.md` §5.7's tie-breaker is answered in the
negative. That is a **negative result about this model on these three tasks**, it materially
redirects the next capability, and it is published as one.

### 6.4 Deferred surfaces

| Deferred | Reason | Resume condition |
| --- | --- | --- |
| **Mode 2: the unchanged-file reproduction** | On `layer-precedence-frozen-module` the model emits well-formed `FILE:` blocks naming allowlisted files and fills them with the files' existing content, so every hunk is empty and `synthesized_patch` refuses (§1.2). It is a **no-op answer**, not a format failure, and the fix is therefore about making the required change legible rather than about the response format: a task statement that names the observable the test asserts, a worked before/after example, and possibly a producer-side check that refuses to call an unchanged reproduction an answer at all. Its first sub-problem is smaller and is this capability's own gap: **persist the edit set on the `PATCH` path** so the no-op answers can be read (§11.3 deviation 14) | Its own capability, whether this gate is `MET` or `NOT_MET`. A `NOT_MET` gate here makes it the next capability rather than a parallel one |
| Scrubbing the sandbox temp path out of persisted diagnostics | Unchanged from `c4-repair-measured.md` §5.4: it originates in the frozen runner and scrubbing here would break §4.5 | A capability that re-freezes the runner |
| Measuring `prompt_preparation_ns` instead of the hard-coded `20_000_000` | Unchanged: a separate pre-existing deviation with its own owner | Its own capability |
| More than one repair attempt | Unchanged. Each extra attempt multiplies run cost and further stretches C6 §9's coverage argument | A `MET` gate at one repair plus a measured recovery rate showing a second attempt would recover a task the first did not |
| Corpus expansion | Three tasks is the frozen corpus | A later Track A capability; no `C9` label exists today |
| Failure-memory feedback between attempts | Unchanged: it would make attempt 2 depend on prior runs and destroy single-row re-derivability | A design that persists the selected memory events into the attempt record |
| Persisting the raw generation response | The edit set is the *validated* subset; the raw response is unbounded, unstructured, and only redacted-and-bounded once it becomes a diagnostic. Persisting it would be a much larger disclosure surface for a much weaker signal | A capability whose question is about response content rather than edit validity — plausibly the mode-2 capability above, which would want the text of an answer the adapter refused |
| Retiring `scripts/prompt-repair-adapter.py` back into the frozen adapter | Two adapters now exist and one imports the other. Merging them means re-freezing `canonical-v1`, which costs three evidence chains | A capability that genuinely re-freezes the canonical corpus, which would also discharge `c6-prompt-context-optimizer.md` §1.2's `/proc` scan and the temp-path scrub |
| Converging `src/repair.align` / `src/verification_loop.align` with this loop | Unchanged | After this gate resolves either way |

Each deferral requires a new design review and an acceptance test tied to time to a passing patch or
another explicitly named metric.

### 6.5 Prerequisites

1. `agent/c4-repair-measured` merged, or its repair complete and its head stable, since this branch
   is stacked on it and consumes `PROMPT_TASK_ROW` version 2, the attempt record with its four
   snapshot digests, and the `canonical-v1r` freeze.
2. `llama-server` running on the host at `127.0.0.1:18080` with
   `~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf` under the model id
   `qwen2.5-coder-7b-instruct-q4_k_m`. Started by the operator; this capability never starts it.
3. The model file present and matching the `model-sha256` frozen into
   `canonical-v1e/generation-policy.json` at freeze time.
4. Docker 28.5.1 and the `c4-repair-measure:latest` linux/aarch64 image.
5. The container-local `socat` forwarder running before the evaluator starts.
6. The managed pinned toolchain at `.align-revision` `3a34febe912db5096c58c74fede36ff53f223e04`,
   materialized through `scripts/align-toolchain`.
7. The frozen-chain regressions of §6.1 green over **both** `eval/prompt/gate/` and
   `eval/prompt/c4-repair-gate/`.

No Align capability request is a prerequisite. §6.7 records why, and what would change that.

### 6.6 Risks

| Risk | Prior class | Mitigation |
| --- | --- | --- |
| The repair adapter persists the **frozen** adapter's runtime identity, and the existing check accepts it because the manifest declares the same false value | new; found by probe (§2.3) | The repair adapter defines its own `runtime_identity` and `environment_probe`; `base_adapter_runtime_identity` records the frozen one separately; ladder row 12 extends the check to every attempt, closing the §2.3 gap at the same time |
| A persisted field list drifts from what its producer emits | persisted field lists vs producer emission | §3.5's table is built **before** implementation and is re-walked in the author pass and in the matrix-to-diff pass. `verifier_measurement_equal` is named explicitly as the one omission that would fail nothing |
| The near-copy of `measurement()` diverges from the frozen original in a way review does not catch | duplicated containment logic (`c4-repair-measured.md` §5.7) | The §3.2 bounded-divergence golden makes the delta a checked-in artifact; the containment, sealing, redaction, and process-ownership primitives are **called**, never copied; `prompt-measurement-adapter-smoke` stays green |
| Consuming an undeclared internal API | new | Stated rather than argued away (§3.2). Three independent digest pins on the file, a startup name-and-kind assertion, and the fact that the file cannot change without minting a new corpus |
| Trace records produced by the second adapter are unreferenced in the evidence model | evidence-model referencing (the C4 publish defect closed by `TaskAttemptRecord`'s four snapshot digests) | The repair adapter produces the **same** snapshot request, before/after results, and input snapshot as the frozen one, through the same helper, so the attempt record binds them by the same mechanism. The gate-validator smoke asserts referencing on a version-2-measurement document explicitly, because "same mechanism" is the assumption that broke last time |
| Validator, fixture, Align, and spec parity: four places must gain the version-2 measurement shape together | new, but adjacent to the field-list class | `verifier_measurement_valid`, `verifier_measurement_equal`, the three `prompt_verifier_smoke.align` constructors, `TASK_MEASUREMENT_FIELDS`, and this document's §3.3 are enumerated in §3.5 and are one review unit |
| Showing the model its own answer makes it copy the answer forward | new | Not mitigated by construction — it is the hypothesis under test. The template states the previous answer's rejected status adjacent to it (§4.2); `patch_sha256` makes copy-forward a **measured** outcome instead of an inferred one (§6.3) |
| The `EDITSET` section blows the prompt budget and the ladder fires for the first time | new | Producer-side whole-block bounding at `EDIT_SET_LIMIT` (§4.3); `EDITSET` dropped last (§4.4); `repair_editset_attempt_count` excludes a dropped row from every edit-set denominator (§3.8) |
| A version-2-shaped decoder deletes C6's **and** C4's merged evidence | evidence loss | Version-1 decode is an explicit owner test in four smokes, and the frozen-chain `validate_evaluation_pair`/`rescore` regression runs over both chains (§6.1). `make prompt-gate-check` is not available as a substitute (§2.6) |
| The model's generated text enters a persisted artifact and a rendered prompt | new disclosure surface | Confined to `allowed_edits` paths, redacted before digesting, bounded whole-block (§4.6). A sample of realized blocks is read in review rather than trusted |
| A digest of unredacted bytes becomes a credential oracle | credential handling | `body_sha256` and `patch_sha256` are computed over **redacted** bytes (§3.3), with the consequence stated |
| The answering server is not the recorded server | provider drift | Unchanged: a fail-closed host probe plus an in-band model-id check, with the residual risk stated rather than resolved (§3.7) |
| Per-attempt run paths overflow a path limit | `ENAMETOOLONG` | Unchanged: fixed-width `-a1`/`-a2` suffixes, bounded and asserted components, owner-test assertion |
| `make gate-topology-check`'s byte-literal `EXPECTED` moves | check topology | Asserted as an owner check (§6.1); if it moves, that is a topology change selecting `make ci` |
| The gate is `NOT_MET` and the work looks wasted | scope pressure | §1.5 and §6.3 fix the reporting for a negative before the run, and a negative here is a **directional** result: it redirects the next capability from the adapter to the prompt |

### 6.7 Align capability requests

No new request is proposed. The two open items this capability touches are both already filed, and
both have a mitigation that reuses a pattern already proven at this pin. The next free number,
**53**, stays free unless implementation finds a genuine gap — in which case it is filed under the
normal lifecycle in `docs/align-requests.md`, and a workaround is not a reason to hide one.

| Request | Where it bites | Mitigation |
| --- | --- | --- |
| **Request 52** — `match` on an owned record's `Option` field partially moves the payload out with no diagnostic, and a later `json.encode` of that still-live record silently omits the field | `src/prompt_evaluate.align` decodes the evaluator's output and re-encodes it to produce the persisted artifact. Four new `Option` members on `TaskMeasurement` and one on each aggregate are exactly the hazard's shape, and the failure is a silent wrong artifact rather than a compile error | Every new `Option` member is read through a `borrow` binding, never through a `match` on the owned record — the same rule `c4-repair-measured.md` §10.2 adopted for its own `Option` members. The two spellings look interchangeable at the call site and are not, so the rule is stated in the closure matrix cell, not left to habit, and a review pass over every `match` on an owned record in the diff is a named repair-audit class |
| **Request 22** — indexing arrays of `Move` element types | `edit_set` is `Option<array<EditSetBlock>>`, and `EditSetBlock` carries `string` fields | Walk the array with the idiom `verifier_attempt_list_references` (`src/prompt_score.align:4563`) already uses for `Option<array<TaskAttemptRecord>>`, which is the identical shape and is proven at this pin. No new indexing form is introduced |

If the pinned compiler cannot express the version-selected presence rule for a nested record's
`Option` members the way it already does for the row's, that is a genuine gap and is filed — not
routed around with a permissive record. `c4-repair-measured.md` §10.2 deviation 10 records that the
mechanism works for `Option<array<T>>` at this pin, which is the harder half.

---

## 7. Closure matrix

Construction, success, failure, malformed input, early exit, and cleanup for each affected module.
Each cell names its implementation and its regression. Cases are
`scripts/run-prompt-repair-adapter-smoke` unless marked **(E)** for `run-prompt-evaluate-smoke`,
**(R)** for `run-prompt-render-parity-smoke`, **(S)** for `run-prompt-score-smoke`, **(G)** for
`run-prompt-gate-validator-smoke`, **(V)** for `src/prompt_verifier_smoke.align`, or **(Q)** for the
§6.2 qualification.

### 7.1 `scripts/prompt-repair-adapter.py` — the base-adapter loader

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | bounded read of the frozen file, digest over those bytes, execute those bytes into a fresh module | load succeeds; `frozen.CHILD_SUBREAPER_ENABLED` observed |
| Success | the module namespace carries every §3.2 name at the expected kind | name-and-kind assertion passes |
| Failure | digest mismatch against `BASE_ADAPTER_SHA256` | a one-byte-mutated copy is rejected, `ERROR`/`BASE_ADAPTER`, before any request load |
| Failure | `base_adapter_runtime_identity` disagrees with `frozen.runtime_identity()` | file replaced between the two derivations is rejected |
| Malformed input | a consumed name is missing or of the wrong kind | a namespace with `validated_edit_set` deleted, and one with it rebound to a non-callable, are both rejected |
| Early exit | executing the module must not run `main()` | a marker file the stub `main()` would create is absent after load |
| Cleanup | no module reload, no namespace mutation, no cross-invocation state | one module object per process; a second load attempt in one process is rejected |
| Divergence | `measurement()` / `assemble()` near-copy | the §3.2 bounded-divergence golden |

### 7.2 `scripts/prompt-repair-adapter.py` — the version-2 measurement

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `edit_set` built from `validated_edit_set`'s return, sorted, redacted, digested, bounded whole-block | a two-file edit set round-trips with both bodies |
| Success | `PASS` and `FAIL`/`TEST` carry `edit_set` `Some` and `patch_sha256` `Some` | both, against a stub generation child |
| Failure | `FAIL`/`PATCH` and `POLICY_VIOLATION`/`POLICY` carry both `None` | a response with no fenced block; a response naming a path outside `allowed_edits` |
| Failure | `ERROR` before the parse carries both `None` | a generation-child failure |
| Malformed input | a body exceeding `MAXIMUM_EDIT_BYTES`; more than `MAXIMUM_FILE_BLOCKS` blocks | both rejected by the frozen `validated_edit_set`, verbatim, with the frozen error mapping |
| Malformed input | `EDIT_SET_LIMIT` exceeded | the over-budget block is persisted with `body_text: None`, `body_bytes` and `body_sha256` intact; total is the pre-omission sum |
| Early exit | the declared-patch path never parses a response | `edit_set` `None`, `patch_sha256` `Some` over the declared patch bytes |
| Cleanup | the patch digest is taken before `ProducedInput` construction | no read after close; the frozen `finally` still closes every retained input |
| Redaction | bodies and digests are post-redaction | a credential-bearing stub run leaves no credential in `edit_set` and changes both digests |

### 7.3 `scripts/prompt-evaluate.py` — `EDITSET` assembly and the aggregate

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `REPAIR_SECTION_KINDS` gains `EDITSET`; `repair_section_sources` gains its renderer | (R) the byte golden with `EDITSET` present |
| Success | the section renders in whole-file format, sorted, correctly fenced | (R) golden; (R) a body containing a fenced block nests |
| Failure | `edit_set` `None` ⇒ section omitted, `included_sections` records it | (R) golden; (E) a mode-2-shaped attempt |
| Failure | an omitted block renders as one placeholder line, never a partial file | (R) golden |
| Malformed input | template `section_headers` keys not exactly the five kinds | (E) rejected, `INVALID_INPUT`/`TEMPLATE` |
| Malformed input | ladder rows 13–17 on a hostile adapter result | (E) one case each |
| Early exit | budget exhaustion after the full ladder ⇒ `SKIPPED`/`REPAIR_PROMPT_BUDGET`, no provider call | (E) and (R) |
| Early exit | ladder row 18: `EDITSET` alone does not make a repair eligible | (E) an attempt with `edit_set` `Some` and all three diagnostics empty is `SKIPPED` |
| Cleanup | unchanged; attempt-1 cleanup failure still suppresses attempt 2 | (E) unchanged case stays green |
| Aggregate | `repair_editset_attempt_count` counts ran repair attempts whose `included_sections` has `EDITSET` | (E) a mixed run of included, dropped, and absent |

### 7.4 The drop ladder

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `REPAIR_DROP_ORDER = ("STDOUT","STDERR","SUMMARY","EDITSET")` | (R) each of the four steps as its own byte golden |
| Success | no drop at realistic sizes | (R) a C4-sized fixture assembles with all five sections |
| Failure | `EDITSET` survives `SUMMARY` | (R) a fixture that must drop three sections keeps `EDITSET` |
| Malformed input | a section source that is present but empty is never "included" | (R) |
| Early exit | `STATUS`-only still over budget ⇒ `SKIPPED` | (R) |
| Cleanup | `dropped_sections` is ordered by `REPAIR_SECTION_KINDS`, disjoint from `included_sections` | (R), (S) |

### 7.5 `src/prompt_artifacts.align`, `src/prompt_score.align`

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `TaskMeasurement` gains four `Option` members; `EditSetBlock` is declared | (S) version-2 decode and re-encode |
| Success | version-1 decode, re-encode, and verdict are byte-identical | (S), (G) over both frozen chains |
| Failure | a version-2 member present at version 1 | (V) a new defect |
| Failure | a version-2 member absent at version 2 | (V) a new defect, one per member |
| Failure | the §3.5 measurement-version-versus-adapter rule violated | (V) a new defect |
| Failure | attempt-level probe producer or runtime identity wrong (ladder row 12) | (V) a new defect, mutation-tested as defect 8 was |
| Malformed input | `edit_set` invariants of ladder rows 13–17 | (S) one case each |
| Malformed input | `verifier_measurement_equal` must compare all 27 fields | (V) a defect that differs **only** in a version-2 member and must be rejected |
| Early exit | version peek before member decode; no presence sniffing | (S) a version-1 document with a stray version-2 key is rejected |
| Cleanup | `verifier_reason_capacity` unchanged; no new per-pair reason | (S) capacity assertion unchanged |
| Ownership | every `Option` member read through a `borrow` binding (Request 52) | `make check`; a review pass over every `match` on an owned record in the diff |
| Ownership | the block array walked with the proven `Option<array<T>>` idiom (Request 22) | `make check` |

### 7.6 Corpus assets and the two frozen chains

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `scripts/freeze-canonical-v1e` mints all 30 members reproducibly | re-running it is a no-op on a clean tree |
| Success | the 24 shared members carry identical digests in all three manifests | an explicit digest-equality assertion over `canonical-v1`, `canonical-v1r`, `canonical-v1e` |
| Failure | `BASE_ADAPTER_SHA256` disagreeing with any of the three | ladder row 3 |
| Malformed input | a `prompt-v1e` task naming only one adapter in `artifacts` | ladder row 5 |
| Early exit | `git diff` over `eval/prompt/canonical-v1/`, `canonical-v1r/`, `gate/`, `c4-repair-gate/`, `eval/tasks/prompt-v1/`, `prompt-v1r/`, `eval/runners/`, and the three frozen scripts is **empty** | a checked assertion in the pull request, not a claim |
| Cleanup | `eval/prompt/c4-editset-gate/` is a new directory; nothing is written into an existing gate directory | (Q) |

### 7.7 The run driver and the gate

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `scripts/run-c4-editset-gate`, `make c4-editset-gate` | (Q) |
| Success | 12 rows, at most 22 calls, evidence published through the Align path | (Q) |
| Failure | a missing or empty `C4_EDITSET_*` value | fails before the run starts |
| Failure | the provider probe disagrees with the policy revision | fails closed before the first call |
| Malformed input | the in-band model id is not the declared one | fails closed |
| Early exit | wall clock exceeds the 60-minute ceiling | the capability stops; the ceiling is not raised after the fact |
| Cleanup | `make gate-topology-check` passes with `EXPECTED` unmoved | an owner check |

### 7.8 Error-code-to-case map, and the final pass

`ERROR`/`BASE_ADAPTER` and the version-2 `ERROR`/`ADAPTER` cases belong to
`scripts/prompt-repair-adapter.py` and its own smoke. `INVALID_INPUT`/`SCHEMA`, `/EDIT_SET`,
`/IDENTITY`, `/AGGREGATE`, and `/MEASUREMENT_BINDING` belong to the Align verifier and the gate
validator, not to `scripts/prompt-evaluate.py`, which emits only its own families —
`c4-repair-measured.md` §10.2 deviation 15 recorded that assuming a single owner for the whole
vocabulary is wrong, and this matrix assigns three owners from the start.

Before review, every applicable cell above is mapped to the final diff and to passing evidence, or
to an explicit deferral recorded in §6.4.

---

## 8. Author consistency pass

Performed against this document as a whole; findings recorded rather than silently corrected.

1. 1. **Ledger-to-prose.** §3.3's field list, §3.5's change table, §3.9's ladder, §4.3's section
   table, and §7.5's cells were walked against each other. The four version-2 members appear
   identically in all five. `patch_sha256` is on the measurement in every one; no draft placed it on
   the attempt record. 2. **Gate predicate identity.** §1.5 restates `c4-repair-measured.md` §1.4's
   predicate verbatim so the two runs are comparable. `repair_editset_attempt_count` is a
   **denominator**, never a gate input; §3.8 and §6.3 agree. 3. **Numbers.** Every figure in §1.2,
   §2.7, §4.3, §5, and §6.2 was read from the checked-in evidence or the checked-in file, and
   re-derived at the merged base `c07775c` before implementation: 12 rows, 22 calls, 7.98–64.67 s,
   median 18.59 s, 8.1× spread, 13.74 min, 91.04 ms / 91.77 ms, 8,123–16,129 assembled bytes,
   217,056 evaluator bytes, 45,088 bytes headroom, patch sizes 716 / 758 / 1008 / 0. §11.1 records
   which two figures moved between `b4cf98e` and `c07775c` and why. 4. **The mode-1 count corrected upward.** An earlier reading counted
   four addressable rows (`record-codec-round-trip` only). The evidence shows **six**:
   `duration-half-away-from-zero` PARENT also re-emitted an identical-size patch (716 → 716) in both
   samples. §1.2, §1.5, §3.4, and §6.2 use six, and §1.5 names three live (task, variant) pairs
   rather than two. 5. **Section order versus drop order are distinct and both are stated.** Order:
   `STATUS, EDITSET, SUMMARY, STDOUT, STDERR`. Drop: `STDOUT, STDERR, SUMMARY, EDITSET`. §4.3 and
   §4.4 do not contradict each other, and §4.4 argues the drop order rather than asserting it. 6.
   **`prompt-gate-check` is not claimed anywhere.** §2.6 states it is unavailable; §6.1 names the
   substitute and extends it to the C4 chain; §6.5 lists it as a prerequisite in that substituted
   form. No section cites it as evidence. 7. **The frozen-file promise is stated once and enforced
   three times.** §1.4 states it, §3.2 lists the three pins, §3.9 rows 2, 3, and 5 check them, §7.6
   regresses them. No section claims the promise without naming its enforcement. 8. **Two open
   items, recorded rather than resolved.** (a) §3.2's bounded-divergence golden depends on a
   normalizer whose exact rules are not specified here; it is specified in the smoke, and if the
   normalizer turns out to hide a real divergence class that is a finding against this design. (b)
   §4.2's copy-forward risk has no mitigation by construction; it is the hypothesis under test and
   §6.3 refuses to claim otherwise. 9. **`N/A` fields.** §3.12's completion paragraph gives a
   concrete reason for each. None is speculative expansion of an untriggered checklist section.

---

## 9. Reconciliation drafts

Drafts only. They are applied in the implementation branch, not here.

### 9.1 `docs/specs/roadmap.md` — new forward-order item 34

> Items 32 and 33 are Track B (`agent/r6-olmoe-decode`, `agent/r6-prefix-suffix-prefill`) and are
> not yet on this branch's base. Item 34 is numbered on the assumption that 31, 32, and 33 land
> first; the number is corrected at reconciliation if that changes.

```text
34. **C4-REPAIR-EDITSET — the failing edit set in the repair prompt, through a second
    corpus-member adapter.** The direct consequence of item 31's measured negative. C4-REPAIR-
    MEASURED ran ten repair attempts and recovered nothing, and its evidence names the reason:
    on all six repair attempts where attempt 1 had produced a validated edit set, attempt 2
    returned a patch of exactly the same byte count. The model was never shown what it wrote.
    Design in [`c4-repair-editset.md`](c4-repair-editset.md), which owns the contract ledger,
    the import-by-path contract, the closure matrix, the repair-prompt contract version 2, the
    cost ceiling, and the gate statement. The design gate triggered on the `TASK_MEASUREMENT`
    schema-2 exchanged format, a new frozen corpus scope with a **second adapter** as a member,
    and a coordinated invariant across the new adapter, `scripts/prompt-evaluate.py`,
    `src/prompt_score.align`, and the corpus assets. `scripts/prompt-repair-adapter.py` **loads
    the frozen `scripts/prompt-measurement-adapter.py` by path and calls its functions**, so the
    reviewed containment, sealing, redaction, and process-ownership code has exactly one copy and
    the second file carries only the sequencing that differs — which is what makes item 31's
    section 5.7 option B affordable now that its tie-breaker has been answered. Three digest pins
    hold the base file byte-identical: a constant in the new adapter, the file-set manifest, and
    the per-invocation artifact snapshot. `TASK_MEASUREMENT` moves to `schema_version: 2` with the
    attempt's realized edit set, its total size, a **digest of the complete patch body**, and the
    base adapter's runtime identity; version 1 stays decodable forever, and `PROMPT_TASK_ROW`
    does **not** move, because the row gains no field. The repair prompt gains an `EDITSET`
    section rendered in the response's own whole-file format, bounded whole-block, and dropped
    **last** — after STDOUT, STDERR, and SUMMARY — so an over-budget row degrades into the
    diagnostics-only prompt that already measured zero recoveries only as a last resort, and
    `repair_editset_attempt_count` keeps a dropped row out of every edit-set denominator. New
    freeze `eval/prompt/canonical-v1e/` + `eval/tasks/prompt-v1e/`; the 24 members shared with
    both earlier corpora carry identical digests. **The addressable arm is six of ten repair
    attempts.** The other four are `layer-precedence-frozen-module`, where the model produced no
    changed file on any of eight attempts — it reproduces the pinned files unchanged, so every
    hunk is empty and no patch is synthesized; that mode is a
    prompt-template and edit-policy capability and is named as the fallback. The gate is item 31's
    predicate unchanged: `repair_recovery_paired_count >= 1`. **A measured negative is a published
    result**, and here it is directional — it would answer item 31's tie-breaker in the negative
    and move the next capability from the adapter to the prompt. No speed claim: the item 31 run
    measured an 8.1x spread over 22 calls at temperature 0. Recorded run-cost ceiling 60 minutes,
    expected 12-30, at most 22 provider calls. Named focused qualification
    `make c4-editset-gate`; it joins no aggregate.
```

### 9.2 `HANDOFF.md` — replacement "Active" section

```markdown
## Active: C4-REPAIR-EDITSET (2026-08-29)

Branch `agent/c4-repair-editset`, stacked on `agent/c4-repair-measured` at `c07775c`.

**Capability.** Carry the failing attempt's own edit set into the repair prompt.
`docs/specs/c4-repair-editset.md` is the authoritative ledger. C4-REPAIR-MEASURED returned
`repair_recovery_paired_count: 0` over ten repair attempts; its evidence shows that on all **six**
attempts where attempt 1 had produced a validated edit set — `record-codec-round-trip` x4 and
`duration-half-away-from-zero` PARENT x2 — attempt 2 returned a patch of exactly the same byte
count. That is the tie-breaker section 5.7 of that document named, and this capability is its
option B.

**The surface decision.** A new `scripts/prompt-repair-adapter.py` **loads the frozen
`scripts/prompt-measurement-adapter.py` by path** and calls its functions: containment, sealing,
redaction, process ownership, generation, validation, and edit parsing have exactly one copy. Only
the ~140 lines of sequencing that must keep `edits` and the patch bytes are near-copied, and their
divergence from the frozen originals is asserted against a checked-in golden. Three digest pins hold
the base file byte-identical: a constant in the new adapter, the `canonical-v1e` file-set manifest,
and the per-invocation artifact snapshot.

**Schema.** `TASK_MEASUREMENT` 1 -> 2, gaining `edit_set`, `edit_set_total_bytes`, `patch_sha256`,
and `base_adapter_runtime_identity` as `Option` members under the present-at-2 / absent-at-1 rule
that C4-REPAIR-MEASURED proved at this pin. **`PROMPT_TASK_ROW` does not move** — the row gains no
field, and a bump would cascade to four documents for nothing. The measurement's version is a
checked function of the task's declared adapter runtime.

**Found by probe, and it is a real defect risk.** `runtime_identity()` in the frozen adapter is
`sha256(Path(__file__).read_bytes())`, and `src/prompt_score.align:4758` requires it to equal the
task manifest's `measurement_adapter_runtime`. A repair adapter reusing the frozen
`environment_probe()` would persist the **frozen** file's digest while running its own code, and the
existing check would accept it because the manifest would declare the same false value. The repair
adapter therefore defines its own identity and persists the base one separately. The same probe
found that no producer or runtime-identity check exists on an *attempt-level* measurement's probe;
ladder row 12 closes it.

**Drop-ladder decision.** `STDOUT -> STDERR -> SUMMARY -> EDITSET`, `STATUS` never dropped.
`EDITSET` last, because dropping it first would silently degrade a row into the diagnostics-only
experiment that already measured zero recoveries; droppable at all, because it is the only section
that can blow the budget alone and a skipped attempt is a lost measurement.
`repair_editset_attempt_count` keeps a dropped row out of every edit-set denominator.

**Freeze.** New `eval/prompt/canonical-v1e/` + `eval/tasks/prompt-v1e/`, 30 file-set members.
`canonical-v1r` cannot be extended: `eval/prompt/c4-repair-gate/` was measured against its exact
scope digest, and a `prompt-v1e` task must name a different adapter anyway, which changes its own
`content_sha256`.

**Not available on this host, and inherited as such.** `make prompt-gate-check` (the C6 gate locator
pins a `./main` built at `762b1d0f`). The substitute C4-REPAIR-MEASURED established —
`validate_evaluation_pair` and `rescore` against the frozen chains, plus the Align-side decode /
re-encode / verify probe — is inherited and extended to cover `eval/prompt/c4-repair-gate/` as well.

**Next actions, in order.** (1) Land `agent/c4-repair-measured`. (2) Review this design. (3) Build
`scripts/prompt-repair-adapter.py` and its smoke, including the bounded-divergence golden.
(4) `TASK_MEASUREMENT` version 2 across `scripts/prompt-evaluate.py`, `src/prompt_artifacts.align`,
`src/prompt_score.align`, and the fixtures — `verifier_measurement_equal` is the one line whose
omission would fail nothing. (5) `EDITSET` assembly and the extended ladder. (6)
`scripts/freeze-canonical-v1e`. (7) `scripts/run-c4-editset-gate` and `make c4-editset-gate`.
(8) The gate run, inside its 60-minute ceiling.

**Blockers.** None besides prerequisite (1). No Align capability request blocks this design; next
free number 53 stays free unless implementation finds a genuine gap. Requests 22 and 52 both bite
and both are mitigated by reusing idioms already proven at this pin.
```

### 9.3 `docs/align-development.md` — addition after "Model-driven repair on the measurement path"

```markdown
#### The failing edit set, and the second adapter

C4-REPAIR-MEASURED's repair prompt carries the failing attempt's status labels, diagnostic summary,
stdout, and stderr, but not its edits: the model's output lives only inside
`scripts/prompt-measurement-adapter.py` and is dropped when `measurement()` returns. The measured
consequence is in `eval/prompt/c4-repair-gate/`: on all six repair attempts where attempt 1 had
produced a validated edit set, attempt 2 returned a patch of exactly the same byte count.

`docs/specs/c4-repair-editset.md` is the authoritative plan for closing that gap.
`scripts/prompt-repair-adapter.py` loads the frozen adapter **by path**, verifies its bytes against
a hard-coded digest before executing them, and calls its containment, sealing, redaction, generation,
validation, and edit-parsing functions unchanged. Only the sequencing that must retain the edit set
is a near-copy, and its divergence from the frozen original is asserted against a checked-in golden.
The frozen adapter stays byte-identical and remains a member of all three corpus file-set manifests
at the same digest.

Two rules that generalize beyond this capability:

- **A second adapter must produce its own `runtime_identity`.** The frozen `runtime_identity()` is
  `sha256(Path(__file__).read_bytes())`, and `src/prompt_score.align` requires the row's probe to
  match the task manifest's `measurement_adapter_runtime`. Reusing the frozen `environment_probe()`
  from an imported module persists the *imported* file's digest while running your own code, and the
  check accepts it. `producer` names a role and stays `MEASUREMENT_ADAPTER`; `runtime_identity` names
  a file and must not.
- **A digest of model output is taken after redaction, never before.** A persisted digest of
  unredacted bytes is a credential oracle.
```

---

## 10. Author-side design checks before implementation

1. Re-read `docs/review-checklist.md`'s "Public contract ledger", "Cross-cutting closure matrix",
   "Align correctness", and "Evaluation and repository integrity" sections against §3, §7, §6.7, and
   §7.6 respectively. Sections not triggered by this diff are omitted, not expanded.
2. Confirm at the pinned compiler, before writing the Align side, that a nested record's `Option`
   members can carry the present-at-2 / absent-at-1 rule the row's already do. If they cannot, file
   it rather than routing around it.
3. Walk §3.5's producer table against the actual files one more time immediately before
   implementation; it is the highest-value table in this document and it is the one most likely to
   have gone stale while `agent/c4-repair-measured` was under repair.
4. Re-derive §1.2's table from `eval/prompt/c4-repair-gate/c4-repair-evaluation.json` at the merged
   head, not at `b4cf98e`, and correct §1.5's addressable-arm count if the evidence moved.
5. Run `gmake format-check` and `git diff --check` on this document before publication.

---

## 11. Implementation record

### 11.1 Ledger-to-diff mapping

Every applicable ledger row and closure-matrix cell, mapped to the file that implements it and to
the owner test that would turn red if it were removed. A cell with no regression is not listed as
covered; it is listed as a deviation in §11.2.

| Ledger / matrix | Implementation | Regression |
| --- | --- | --- |
| §3.1 second adapter, same CLI, no new flag or environment variable | `scripts/prompt-repair-adapter.py` `main()` calls `frozen.parse_arguments` verbatim | `run-prompt-repair-adapter-smoke` launch rows drive the real CLI |
| §3.2 verify-then-execute over one byte sequence | `verified_base_adapter` → `execute_base_adapter(path, raw)`; `base_adapter()` returns the same `raw` | mutant M21 (digest check removed) dies |
| §3.2 `BASE_ADAPTER_SHA256` literal | `2d3796db…` in the adapter; `freeze-canonical-v1e` asserts it against both earlier manifests and the file's bytes | `run-prompt-gate-validator-smoke` three-corpus proof; mutant M21 |
| §3.2 three independent pins agree | the constant, `canonical-v1e/corpus-file-set.manifest`, and each task's `artifacts` entry | `frozen_corpus_rows` asserts all three |
| §3.2 `__file__` set to the frozen path | `execute_base_adapter` sets `module.__file__` before `exec` | `base_runtime_identity` cross-derivation row |
| §3.2 base identity cross-derived, mismatch is `ERROR`/`BASE_ADAPTER` | `base_runtime_identity` | portable row: `base_runtime_identity(raw[:-1], module)` is refused |
| §3.2 subreaper effect disclosed, never set here | the adapter sets no `prctl`; it reads `frozen.CHILD_SUBREAPER_ENABLED` | `grep` shows one writer; the Linux launch rows exercise the posture |
| §3.2 import-contract assertion, name and kind | `CONSUMED_NAMES` + `assert_import_contract` | mutant M22 dies; the missing-name and wrong-kind rows |
| §3.2 bounded-divergence golden | `eval/fixtures/c4-repair-editset/adapter-divergence.diff`, 209 normalized lines; the compared span is the parser's, not a column-0 scan | `check_divergence` runs on every invocation, on every platform; the triple-quoted-string span row (added in review repair) |
| §3.3 27 declared members, four appended before `content_sha256` | the adapter's `assemble()`; `TASK_MEASUREMENT_V2_FIELDS`; `TaskMeasurement` | `assert_version_two_shape`; `editset-fields` in the evaluate smoke |
| §3.3 `EditSetBlock` | `prompt_artifacts.EditSetBlock`; `edit_set_blocks()` | `EDIT_SET_BLOCK_FIELDS` shape row |
| §3.3 digests over **redacted** bytes | `edit_set_blocks` redacts before hashing; `patch_sha256` over `redacted_bytes(raw_patch, …)` | mutant M19 dies; the credential-bearing launch row |
| §3.3 presence rules, both directions | `valid_measurement_version_two`; `verifier_measurement_version_one_shape` / `…_two_shape`; `validate_measurement_version` | mutants M11, M12, M14; verifier defects 15, 17, and — added in review repair, one per version-1 absence clause — 21, 22, 23; the validator's four direct row-10 rows |
| §3.3 `patch_sha256` iff `patch_size_bytes > 0` | all three owners | evaluate-smoke `editset-row13-*`; verifier defect via `patch_valid` |
| §3.3 `edit_set_total_bytes` = sum | all three owners | mutant M10 dies; `editset-row14-total-disagrees`; validator `v2-editset-total` (added in review repair) |
| §3.3 summary cross-check, exempt on a **cut** summary | evaluator and gate validator (row 17) | mutant M2 dies; `editset-row17-truncated` and validator `v2-editset-summary-truncated` accept the cut case (both added in review repair) |
| §3.5 `PROMPT_TASK_ROW` unchanged | no row field added | `TASK_ROW_V2_FIELDS` unmoved |
| §3.5 measurement version = f(adapter) | `expected_template_kinds` / `verifier_task_expects_measurement_version_two` / validator row 11 | mutants M9 and M14 die; verifier defect 16 |
| §3.5 `verifier_measurement_equal` gains the four members | `src/prompt_score.align` | mutant M6 dies; verifier defect 19 |
| §3.5 every persisted field list and its sole producer | the parity table in §11.4 | walked before implementation and again at this mapping |
| §3.6 30 file-set members, 24 shared at identical digests | `scripts/freeze-canonical-v1e` | `frozen_corpus_rows`; the freeze refuses a member count other than 30 |
| §3.6 nothing under the earlier corpora is modified | `git diff` over them is empty | asserted in §11.3, not claimed |
| §3.7 provider revision re-derived, never inherited | `freeze-canonical-v1e --provider-service-revision` is required | §11.3 records the observed value |
| §3.8 aggregates recomputed, never trusted | `verifier_variant_repair_aggregate.editset`; `row_repair_editset_attempts` in both Python owners | mutants M8, M13, M17 die |
| §3.9 row 2 | `verified_base_adapter` | mutant M21 |
| §3.9 row 3 | `freeze-canonical-v1e`'s `assert_base_adapter_unmoved` | `frozen_corpus_rows` |
| §3.9 row 4 | `assert_import_contract` | mutant M22 |
| §3.9 row 5 | both adapters in each `prompt-v1e` task's `artifacts` | `frozen_corpus_rows` |
| §3.9 row 6 | `frozen.CHILD_SUBREAPER_ENABLED` read in `measurement()` | the Linux launch rows |
| §3.9 row 7 | `base_runtime_identity` | the mismatch row |
| §3.9 row 8 | `expected_template_kinds` + `valid_repair_template(value, kinds)` | `editset_template_cases`, both directions |
| §3.9 rows 9-10 | version-selected `TASK_MEASUREMENT_FIELDS` | `editset-row10`; verifier defect 15 |
| §3.9 row 11 | above | mutants M9, M14 |
| §3.9 row 12 | evaluator, gate validator, and Align verifier, per **ran attempt** | mutants M7, M16 die; verifier defect 18; validator `v2-attempt-probe-identity` |
| §3.9 rows 13-17 | `valid_measurement_version_two`, `validate_measurement_version`, `verifier_measurement_version_two_shape` | `editset-row13-*` … `editset-row17-*`; mutants M10, M15 |
| §3.9 row 15 paths unique and strictly ascending | the same three owners | verifier defects 24 (descending) and 25 (repeated path); validator `v2-editset-path-order` and `v2-editset-path-duplicate`; `editset-row15-unsorted`. All four added in review repair, which found the rule unfalsifiable while every fixture edit set held one block |
| §3.9 row 18 | `repair_eligibility` unchanged | `editset-eligibility` |
| §3.9 rows 19-20 | unchanged from C4-REPAIR-MEASURED | `editset-budget-exhausted`, `editset-rederive-self` |
| §3.9 row 21 | the recomputed denominator | mutants M8, M13, M17 |
| §3.9 row 22 | `verifier_measurement_equal` over all 27 | mutant M6 |
| §3.10 patch digest taken before `ProducedInput` | `measurement()` computes `patch_sha256` from `raw_patch` | the declared-patch and generated-patch launch rows |
| §3.10 one module per process, never reloaded | `_BASE` guard | the second-load row |
| §3.11 pin updated in the same commit | `EVALUATOR_SOURCE_SHA256` = `aa37a51c…`, 235,059 bytes after the review repair | `run-prompt-evaluate-smoke` fails outright on a stale pin, which is how it was caught |
| §4.2 template states the previous answer's rejected status | `REPAIR_PREAMBLE` and the `EDITSET` header in `freeze-canonical-v1e` | `editset_template_cases` |
| §4.3 whole-file format, sorted, fenced longer than any nested run | `repair_edit_set_text`, `edit_set_fence` | `editset-golden`, `editset-nested-fence` |
| §4.3 omitted block is one line | same | `editset-omitted`, both owners |
| §4.3 producer-side whole-block bound, carried set is a **prefix** | `edit_set_blocks` | mutant M20 dies; the 10,000/10,000/5,000 portable row separates a prefix cut from a greedy best fit (added in review repair, which found the code greedy and the prose a prefix) |
| §4.4 drop order, `EDITSET` last, `STATUS` never | `REPAIR_DROP_ORDER` | mutants M1 and M5 die; four ladder goldens |
| §4.5 re-derivability | unchanged `repair_prompt_text` path | `editset-rederive-self` at five budgets |
| §4.6 nothing constructed reaches the prompt | — | `editset-redaction` |
| §6.1 frozen chains green | `frozen_version_one_chain`, `frozen_version_two_chain` | both run in `prompt-gate-validator-smoke` |
| §6.2 `make c4-editset-gate`, joins no aggregate | `Makefile` | `gate-topology-check` passes with `EXPECTED` unmoved |
| §6.7 Request 52 idiom | every new `Option` read is a `borrow` binding | `gmake check`; the frozen-chain round trip |
| §6.7 Request 22 idiom | `verifier_edit_set_*` pass elements straight into `borrow` parameters | `gmake check` |

**Two design numbers moved between `b4cf98e` and the merged base `c07775c`, and §10 item 4 required
re-deriving them.** The evaluator grew from 214,802 to 217,056 bytes under the C4 repair, so the
headroom is 45,088 rather than 47,342; and the published C4 evidence is that branch's **second**,
clean-head run, whose timings are 7.98-64.67 s, median 18.59 s, 8.1x, 824.243 s wall clock, and
91.04 / 91.77 ms overhead. **§1.2's table itself is unchanged**: re-derived row by row from
`eval/prompt/c4-repair-gate/c4-repair-evaluation.json` at `c07775c`, every status, failure kind, and
`patch_size_bytes` is identical, so the **addressable arm is still exactly six rows** —
`record-codec-round-trip` x4 and `duration-half-away-from-zero` PARENT x2 — and §1.5's three live
(task, variant) pairs stand.

Realized size: `scripts/prompt-evaluate.py` is **235,059 bytes** after the review repair — 234,347
before it — leaving **27,085 bytes** of headroom inside the unchanged four-chunk window. No
widening was needed and none is planned.

### 11.2 The field-list parity table, built before implementation

§3.5's producer table was re-walked against the actual files immediately before coding (§10 item 3),
and this is the result: every place a `TASK_MEASUREMENT` field list exists, what it is at version 1,
and what it became. It was walked a second time at the ledger-to-diff mapping above.

| # | Place | File | Role | Version 1 | Version 2 |
| --- | --- | --- | --- | --- | --- |
| 1 | `assemble()`'s literal dict | `scripts/prompt-measurement-adapter.py` | producer | 23 keys | **frozen; emits v1 only, byte-identical** |
| 2 | `assemble()`'s literal dict | `scripts/prompt-fixed-adapter.py` | producer | 23 keys | **frozen; emits v1 only, byte-identical** |
| 3 | `assemble()`'s literal dict | `scripts/prompt-repair-adapter.py` | producer | — | **new; emits v2 only, 27 keys** |
| 4 | `TASK_MEASUREMENT_FIELDS` | `scripts/prompt-evaluate.py` | consumer | 23, unchanged | `TASK_MEASUREMENT_V2_FIELDS` = 23 - 1 + 4 + 1 = **27**, version-selected |
| 5 | `TaskMeasurement` record | `src/prompt_artifacts.align` | consumer | 23 members | **+4 `Option` members** before `content_sha256` |
| 6 | `verifier_measurement_valid` | `src/prompt_score.align` | validator | `schema_version == 1` | `1 or 2` + version-shape + row 11 |
| 7 | `verifier_measurement_equal` | `src/prompt_score.align` | field-wise equality | 23 comparisons | **27** — the single highest-value line in the diff |
| 8 | measurement constructors ×3 | `src/prompt_verifier_smoke.align` | fixtures | v1 cases kept | **+4 `None`**, plus `measurement_v2` and 7 new defect cases |
| 9 | *(no field list)* | `scripts/prompt-gate-validator.py` | validator | treats the measurement as an opaque record | **gains `validate_measurement_version` and `validate_measurement_probe`**, plus `EDIT_SET_BLOCK_FIELDS` |
| 10 | `attempt_measurement` | `scripts/prompt_gate_fixture.py` | fixture | emitted v1 | **emits v2**, and its tasks name the repair adapter |
| 11 | `repair_measurement` | `scripts/run-prompt-evaluate-smoke` | fixture | reduced v1 shape | **+`editset_measurement`** wrapper |
| 12 | `SYNTHETIC_MEASUREMENT` | `scripts/run-prompt-render-parity-smoke` | fixture | v1 | **+`editset_measurement`** wrapper |
| 13 | §3.3's declared order | this document | contract | 23 | **27** |
| 14 | row-bearing fixtures | `src/prompt_render_smoke.align`, `src/prompt_render_parity_smoke.align`, `eval/fixtures/c6-prompt-state/templates.jsonl` | fixtures | **untouched; no measurement field list** | — |

**Two findings from the walk, both acted on.** (a) Entry 9 was the surprise: the gate validator has
**no** `TASK_MEASUREMENT` field list at all — it compares `canonical_bytes(row["measurement"])`
against the final attempt's and reads named keys — so the version-2 rules had to be *added* there
rather than *extended*, and the §3.5 table's implicit assumption that every consumer enumerates
fields is wrong for this one. (b) Entry 14 was expected to need version-2 cases per §6.1 and does
not: those three fixtures carry rows, not measurement field lists, so they are unchanged and
`prompt-render-smoke` and `prompt-state-smoke` stay green without edits.

The two aggregate records were walked the same way: `TaskAggregate` gains two members and
`CorpusAggregate` one, in `src/prompt_artifacts.align`, `scripts/prompt-evaluate.py`,
`scripts/prompt-gate-validator.py` (`TASK_AGGREGATE_V2_FIELDS`, `CORPUS_AGGREGATE_V2_FIELDS`, and
`AGGREGATE_OPTIONAL`), `scripts/prompt_gate_fixture.py`, and `src/prompt_verifier_smoke.align` —
five places, all five changed together, with §11.3 deviation 2 governing their presence.

### 11.3 Deviations

Each is a place where implementation departed from, or had to decide something left open by, §1-§10.

1. **`valid_repair_template` takes the expected kind set as a parameter; it is not fixed at five.**
   §2.4 and §3.9 row 8 read as though the five-kind tuple simply replaces the four-kind one. Doing
   that made `eval/prompt/canonical-v1r/repair-template.json` undecodable, which would have left the
   merged `eval/prompt/c4-repair-gate/` evidence naming a corpus that can no longer be run — a
   non-goal (§1.4 item 2) reached by a route the design did not consider. The shipped rule selects
   the kind set the same way §3.5 selects the measurement version: by the adapter the corpus names.
   `make prompt-render-parity-smoke` went red and is what found it.

2. **The new aggregate members are present iff the corpus names the repair adapter, not "present at
   version 2".** §3.8 says they follow "the existing present-at-2 / absent-at-1 rule". They cannot:
   `eval/prompt/c4-repair-gate/c4-repair-evaluation.json` is a **version-2** document written before
   this capability existed, so requiring the members at version 2 rejects merged evidence outright —
   precisely the §6.6 risk row "a version-2-shaped decoder deletes C6's **and** C4's merged
   evidence". The new `frozen_version_two_chain` regression is what caught it, on its first run. The
   shipped rule is adapter-selected in all four owners, and a `canonical-v1r` corpus recomputes the
   member as **absent** rather than as zero, because a corpus whose template has no `EDITSET` kind
   cannot define the quantity.

3. **Ladder row 10's "present at version 2" is key-presence, not `Some`-ness.** §3.3's presence
   table already says `edit_set` and `patch_sha256` may be `None` at version 2, so row 10's
   shorthand cannot mean `Some` for all four. The shipped reading: all four keys are present at
   version 2 and absent at version 1 at the adapter boundary (the field-tuple check), and
   `base_adapter_runtime_identity` is additionally always `Some`. The other three follow rows 13
   and 14.

4. **`allowed_edits` membership is owned by `scripts/prompt-evaluate.py` alone, not by the gate
   validator.** §3.9 row 15 lists it with the other block rules. `validate_evaluation_pair` is a
   pure function of the two documents it is handed — that is what lets the frozen-chain regression
   call it with no source tree — and the editable set lives in a file outside them. The evaluator
   checks it against the manifest-declared digest-pinned task definition at the moment the adapter
   result is admitted, so no block can be persisted without passing it. The Align verifier owns
   every other row-15 rule, `body_sha256`-over-`body_text` included, because `crypto.sha256` is
   available to it.

5. **`load_bound` gained a `versions` parameter.** It hard-coded `schema_version != 1`, so a
   version-2 `TASK_MEASUREMENT` could not be read at all. The parameter defaults to `(1,)`, so no
   other artifact's decode widened.

6. **`valid_measurement_version_two` also enforces absence at version 1.** The field-tuple check in
   `valid_task_measurement` already rejects a stray key on any document that reached it through the
   adapter boundary, so this is redundant there — but it makes the function total and gives ladder
   row 10 an addressable owner instead of an emergent one. The evaluate smoke's `editset-row10` case
   is what forced the choice.

7. **The aggregate comparison in `validate_evaluation_pair` completes both sides.** It compared a
   completed persisted record against a raw computed one, which reads a legitimate canonical
   omission as a disagreement once any aggregate member can be absent.

8. **`src/prompt_verifier_smoke.align` builds two task shapes as one parameterized literal.** The
   pinned compiler supports owned field replacement only for `string` and `Option<string>` leaves,
   so `task_repair_adapter()` could not be `task()` with `argv` replaced, and
   `measurement_v2_wrong_identity` could not replace an `EnvironmentProbe` field. Recorded against
   Request 22 as known-limitation evidence rather than filed as a new request.

9. **The bounded-divergence normalizer's rules are stated in the smoke, not here.** §8 item 8(a)
   records this as an open item. The shipped rules are: only the two named functions' lines, over
   the span Python's own parser reports for that `def`; full-line `#` comments removed; blank lines
   removed; trailing whitespace stripped. Nothing else — no identifier rewriting, no `frozen.`
   prefix stripping, no whitespace-insensitive comparison — so every executable difference survives
   into the golden. A comment-only change in either file is deliberately not a divergence. The span
   was first written as a scan to the next column-0 line, which a triple-quoted string holding a
   column-0 line would end early, hiding every difference after it; review found it and the parser
   now owns the span, with a case in the smoke. The golden's bytes are unchanged by the switch.

10. **`make prompt-repair-adapter-smoke` joins no aggregate.** §6.1 requires
    `make gate-topology-check` to pass with its byte-literal `EXPECTED` unmoved, and adding the new
    owner to `HOSTED_CHECK_TARGETS` would move it. It is therefore a focused command not reached by
    an aggregate, documented here and in `HANDOFF.md` per `CLAUDE.md`'s verification section.

11. **The frozen C4 chain is regressed through `rescore` plus the row, attempt, and measurement
    walks, not through `validate_evaluation_pair`.** That function requires `IMPROVED` and
    `gate_eligible`, and the C4 run is a published measured negative with two `POLICY` reasons. The
    same rules are reached; the entry point is the one that document can legitimately take.

12. **No Align capability request was filed.** Request 53 stays free. `Option<array<EditSetBlock>>`
    decode, re-encode, the present/absent rule on a **nested** record's members, `crypto.sha256`
    over an `Option<string>` payload bound in a `match` on a borrowed record, and the Move-element
    array walk all worked at the pinned compiler on the first build. §10 item 2's pre-check was
    therefore answered affirmatively by the build itself.

13. **The gate validator's version-2 presence rule reads the wire form, not key presence.** Written
    as "all four keys present at version 2", it rejected the published gate evidence on its first
    contact with a real `FAIL`/`PATCH` row, because the canonical encoder omits an `Option::None`.
    The adapter boundary and the persisted document use different serializations and the rule
    differs accordingly; §11.4 records the finding and the fixture change that makes it
    falsifiable. Found by running the validator against real evidence, which no fixture could have
    told us.

14. **`edit_set` is not persisted on the `PATCH` path, and on this corpus that is where it would
    matter most.** `scripts/prompt-repair-adapter.py` builds the blocks from `validated_edit_set`'s
    return and then calls `synthesized_patch`, which raises `EditFormatError` when every hunk is
    empty; the handler resets `edit_set`, `edit_set_total_bytes`, and `patch_sha256` to `None`. So
    on all eight unchanged-reproduction rows an edit set existed one statement earlier and is
    discarded. This **conforms to §3.3**, whose presence table says `None` on `PATCH`, and it is
    the shipped behaviour — but as written the table's other clause said `Some` exactly when
    `validated_edit_set` returned, and the two clauses disagreed for precisely this path. The design
    wrote that table believing mode 2 never reached `validated_edit_set` at all (§1.2), which the
    evidence falsifies. §3.3's `edit_set` cell now states the shipped condition — a validated edit
    set **and** a non-empty synthesized patch — and points here; that is a wording repair to the
    presence rule, not a change to the persisted contract, which is unmoved. The
    consequence is concrete: the answers this corpus's dominant failure mode produces are the ones
    the capability cannot show a reader. Not changed here, and the reason is the measurement rather
    than the freeze: persisting the discarded blocks changes what the adapter records on the rows
    that dominate this corpus, so the published result would no longer be the result this document
    analyses. It is the first thing §6.4's fallback capability should fix, and that capability owns
    its own freeze and its own run.

15. **Review repair moved the repair adapter's bytes, so `canonical-v1e` was re-frozen and the
    gate was re-run.** Review found the producer-side budget implemented as a greedy best fit while
    §4.3, the adapter's own docstring, and `src/prompt_artifacts.align` all describe a prefix cut,
    and the prose was the intended rule: a best fit omits an earlier file while carrying a later
    one, so the `EDITSET` section would no longer be a prefix of the answer the model gave. The
    code moved to break-on-first-overflow. That changes `scripts/prompt-repair-adapter.py`'s
    digest, which three manifests and the corpus digest cascade pin, so `canonical-v1e` and
    `eval/tasks/prompt-v1e/` were re-frozen — **the same member set**, with the repair adapter's
    digest and every digest downstream of it moving and nothing else. The provider service revision
    was re-derived, not inherited, and came back unmoved. The gate evidence at the previous head
    could not have been affected in any correctness value — no row came within a factor of three of
    `EDIT_SET_LIMIT`, at 8,348 to 16,904 assembled bytes, and the ladder never fired, so no block
    was ever a candidate for omission — but the artifact's runtime-identity fields name the adapter
    by digest, so the run was repeated from the repaired head rather than re-labelled. §11.4
    records both runs.

### 11.4 The gate run and its result

**The checked-in evidence is the run from the clean committed head `de56c60`**, taken on the terms
`c4-repair-measured.md` §10.3 established: a gate record must name a reproducible commit.
`align_llm_clean: true`, and all three reachability fields — `align_llm_reachability`,
`align_reachability`, `corpus_reachability` — are `VERIFIED`. An earlier run from the same tree
before it was committed reported `align_llm_clean: false` and — of the three reachability fields —
`align_llm_reachability: UNVERIFIED`, the one an uncommitted head makes unanswerable;
`align_reachability` and `corpus_reachability` were `VERIFIED` in both runs;
**every correctness value below reproduced exactly between the two**, including both patch digests,
and only the clocks moved. That comparison is itself the reproducibility evidence, and it is why §6.3
refuses a speed claim.

```text
verdict:                      NOT_MET
repair_recovery_paired_count: 0        (the gate quantity; >= 1 was required)
repair_recovery_count:        0
repair_attempt_count:         10
repair_editset_attempt_count: 6        (the expected value, stated before the run)
wall clock:                   940.931 s = 15.68 min against a 60-minute recorded ceiling
provider calls:               22       (12 initial + 10 repair, the ceiling's exact estimate)
adapter_elapsed_ns:           8.93 s - 52.57 s, median 22.25 s, n = 22
assembled repair prompts:     8,348 - 16,904 bytes of 65,536; no section was ever dropped
evaluation status:            SERIOUS_REGRESSION (two POLICY reasons); gate_eligible false
```

`repair_editset_attempt_count` came out at **exactly 6**, the value §1.5 fixed before the run, so
the addressable arm was realized in full and the drop ladder never fired. The four
`layer-precedence-frozen-module` repairs carried `included_sections: [STATUS, SUMMARY, STDERR]`
with `dropped_sections: []`, which is the empty-source case behaving as §3.4 said it would.

| Task | S | Variant | Attempt 1 | Attempt 2 | `EDITSET` | patch identity |
| --- | --- | --- | --- | --- | --- | --- |
| `duration-half-away-from-zero` | 1 | PARENT | `FAIL`/`TEST`/716 | `FAIL`/**`PATCH`**/**0** | yes | a2 produced none |
| `duration-half-away-from-zero` | 2 | PARENT | `FAIL`/`TEST`/716 | `FAIL`/**`PATCH`**/**0** | yes | a2 produced none |
| `duration-half-away-from-zero` | 1 | CANDIDATE | `PASS`/758 | — | — | — |
| `duration-half-away-from-zero` | 2 | CANDIDATE | `PASS`/758 | — | — | — |
| `record-codec-round-trip` | 1 | PARENT | `FAIL`/`TEST`/1008 | `FAIL`/`TEST`/1008 | yes | **byte-identical** `8cd2aa30…` |
| `record-codec-round-trip` | 2 | PARENT | `FAIL`/`TEST`/1008 | `FAIL`/`TEST`/1008 | yes | **byte-identical** `8cd2aa30…` |
| `record-codec-round-trip` | 1 | CANDIDATE | `FAIL`/`TEST`/1008 | `FAIL`/`TEST`/1008 | yes | **byte-identical** `cd9ae218…` |
| `record-codec-round-trip` | 2 | CANDIDATE | `FAIL`/`TEST`/1008 | `FAIL`/`TEST`/1008 | yes | **byte-identical** `cd9ae218…` |
| `layer-precedence-frozen-module` | 1 | PARENT | `FAIL`/`PATCH`/0 | `FAIL`/`PATCH`/0 | no | neither produced one |
| `layer-precedence-frozen-module` | 2 | PARENT | `FAIL`/`PATCH`/0 | `FAIL`/`PATCH`/0 | no | neither produced one |
| `layer-precedence-frozen-module` | 1 | CANDIDATE | `FAIL`/`PATCH`/0 | `POLICY_VIOLATION`/`POLICY`/0 | no | neither produced one |
| `layer-precedence-frozen-module` | 2 | CANDIDATE | `FAIL`/`PATCH`/0 | `POLICY_VIOLATION`/`POLICY`/0 | no | neither produced one |

**The question §1.2 could not answer is now answered.** On all four rows where both attempts
produced a patch, `attempts[1].measurement.patch_sha256` equals `attempts[0]`'s **exactly**. C4
could only say "the same byte count"; this run says *the same bytes*. `same_patch_resent: 4`,
`patch_changed: 0`.

**And the persisted edit set says something the patch digest alone does not.** On the two
`record-codec-round-trip` **CANDIDATE** rows the model re-emitted a byte-identical edit set — one
file, `src/encode.py`, same `body_sha256` — which is copy-forward in its purest form. On the two
**PARENT** rows it did **not**: attempt 1 emitted two files (`src/decode.py` and `src/encode.py`)
and attempt 2 emitted only `src/encode.py`, with a byte-identical body. The model *acted on* being
shown its own answer — it dropped the file it had reproduced unchanged — and the synthesized patch
was byte-identical anyway, because `whole_file_hunk` contributes nothing for a file that matches the
pinned source. That distinction is invisible in `patch_size_bytes`, invisible in `patch_sha256`, and
visible only because `edit_set` is persisted.

**The `duration-half-away-from-zero` PARENT arm changed mode, and got worse.** In the C4 run those
two rows re-emitted a 716-byte patch. Shown their own rejected answer, they returned
`FAIL`/`PATCH` with `patch_size_bytes: 0` and
`diagnostic_summary: "the response reproduced the pinned files unchanged"` — a well-formed answer
that, on the adapter's own reading of it, **restores the file to its pinned content**. That reading
is an inference from the summary and the empty patch, not a persisted observation: `edit_set` is
`None` on exactly these rows (§11.3 deviation 14), so the blocks the model actually emitted are not
in any artifact and cannot be read back. So the edit set did change the model's behaviour
on that arm: from a wrong patch to a **no-op**. Read against the template, which states the previous
answer was rejected by the repository's own validation and instructs the model not to return it
unchanged, the model appears to have taken "your answer was rejected" as "revert it".

That is a stronger and more specific finding than "no effect", and it moves those two rows into the
same mode as `layer-precedence-frozen-module` — **unchanged-file reproduction**, not a format
failure. All eight `PATCH` rows in this run carry that identical summary, and none carries a
parse-failure message. §1.2 records the correction to the design's original characterization.

**What this settles.** `c4-repair-measured.md` §5.7's tie-breaker is answered **in the negative**:
on this model and this corpus, the missing edit set was **not** the binding constraint. Of six
addressable repair attempts, four re-sent a byte-identical patch and two lost the answer format
entirely. Zero recovered. The next capability is therefore the prompt, the template, and the edit
policy — §6.4's named fallback — and not further adapter work. That is a directional negative and it
is published as one.

**What this capability did deliver**, independently of the gate: a bounded, redacted,
digest-verified copy of a failing attempt's own edits reaches its repair prompt, through a second
adapter that reuses the reviewed containment core without editing a byte of it; the resulting prompt
is re-derivable from persisted evidence; and "attempt 2 re-sent attempt 1's patch" is now a
**verified fact** rather than an inference, on the first run that could state it.

**No speed claim.** Four runs of this corpus family at identical seeds and `temperature_micros: 0`
now exist: the C4 pair spanned 7.98-64.67 s and 8.13-73.82 s, and this capability's pair spans
8.93-52.57 s (committed head, 940.931 s wall clock) and 8.58-51.54 s (the pre-commit run, 823.67 s).
Four runs, four ranges, one greedy decode, and the 117-second wall-clock gap between this
capability's own two runs is host contention rather than anything about the model. §6.3 refuses a
speed claim and this is why.

**Run record.** align-llm commit `de56c60caab9f5aa169a71a5c9731a5bf259b3da`, `align_llm_clean:
true`, `.align-revision` `3a34febe912db5096c58c74fede36ff53f223e04`, image
`c4-repair-measure:latest` (`33fa9e4446ab`) on Docker 28.5.1, forwarder
`socat TCP-LISTEN:18080,fork,reuseaddr,bind=127.0.0.1 TCP:host.docker.internal:18080`, container
privileges `--cap-add=SYS_ADMIN` plus unconfined `seccomp`, `apparmor`, and `systempaths`, in-band
model id `qwen2.5-coder-7b-instruct-q4_k_m`. The provider service revision was **re-derived at
freeze time, not inherited** (§3.7), and re-probed again immediately before this run:
`llama-server --version` reports build 10566 commit `bb4caa754`, the resolved binary hashes to
`b6ff7e91…`, and the model file was re-hashed in full to `509287f7…`. The observed string equals
`canonical-v1r`'s, which is a measurement and not a copy — the probe would have failed closed had
any component moved.

Published digests:

```text
c4-editset-evaluation.json           1355d8e3d03919c7dff361d6262bab6d1eca84f20b5e981fc19de1cc7a6b021f
c4-editset-evaluation-evidence.json  cac6f466d6e9a72a5579bc53c5a6ecde6e5921fcf36272ae220651294a4c5b00
c4-editset-gate-record.json          561f74b8360c50baa0ca5d407d10021c247ce0113752744730d9eac40f922af0
```

The chain revalidates at this head: `src/prompt_evaluate_smoke.align` decodes, re-encodes, and
verifies it to `COMPLETE_INELIGIBLE` — structurally valid and correctly not acceptance-eligible —
and `scripts/prompt-gate-validator.py`'s `rescore` plus the row, attempt, and measurement walks
accept all 12 rows, recomputing `repair_editset_attempt_count` to the persisted 6.

`gate_eligible` is `false` and not for reachability: it is the **C6 acceptance** verdict, which
requires `IMPROVED` with no serious-regression reason, and this run's status is
`SERIOUS_REGRESSION` from the two `layer-precedence-frozen-module` `POLICY` rows. The C4 gate does
not read it.

**A defect this run found, in the validator, and the fix.** Running
`validate_evaluation_pair`'s row/attempt/measurement walk against the published evidence rejected
row 0 with "omits `edit_set` at version 2". The rule was written as key-presence, which is correct
at the **adapter boundary** — the adapter writes every key including `null`, and
`scripts/prompt-evaluate.py` holds it to the exact 27-key tuple there — but wrong on the
**persisted** document, where the canonical encoder omits an `Option::None`. A `FAIL`/`PATCH` row
legitimately has all three of `edit_set`, `edit_set_total_bytes`, and `patch_sha256` absent. Only
`base_adapter_runtime_identity` is unconditionally present at version 2. This is the mirror image of
`c4-repair-measured.md` §10.2 deviation 21b — a validator rule the fixture could not falsify because
the fixture wrote its `None`s explicitly — so the fix is both: the rule now reads the wire form, and
`scripts/prompt_gate_fixture.py` emits one row whose three members are **omitted** exactly as the
wire omits them. Recorded as deviation 13.
