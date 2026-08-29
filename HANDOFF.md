# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active: R6-PREFIX-KEY (2026-08-29)

Branch `agent/r6-prefix-key-corpus`, cut from `agent/mf-single-token-logits` `40eb965` — that
branch's merge of `origin/main` `45ff38e` (PR #148). **Stacked on roadmap item 36 and must not merge
before it**: a store that *writes* containers requires item 36's fix, because item 33's
`T_prefix >= 2` refusal existed only because a one-token prefill computed the wrong embedding row,
and a store would persist that wrong plane and serve it forever. The block below records item 36's
own state; when it lands on `main`, merge `main` into this branch by `git merge`, **never a rebase**.

Roadmap item **37**. The design gate fires on all four `CLAUDE.md` triggers. The ledger is
`docs/specs/r6-prefix-key-corpus.md`, **committed at `8238df6` and not edited**: sections 1–10 are
the contract, section 11 is item 38's charter, **section 12 records every implementation deviation**,
and section 13 records the results.

**Implemented, hosted-verified, not yet published.** `--decode-step` gains a sixteenth operand,
`STORE`, a caller-created directory that is mutually exclusive with `KV_SAVE` and `KV_LOAD`. The arm
derives a 32-byte key — SHA-256 over a 152-byte preimage of three digests plus `pack_total_bytes`,
`kv_width`, `token_count`, `plane_layout_version`, `element_type`, `format_version`, `key_version` —
and addresses `<STORE>/<64-hex>.akvp`. **A hit loads through the unchanged L1–L14 path; a miss
prefills, saves through the unchanged writer, and continues**, and the two produce byte-identical
documents outside three store fields and oracle Q's own set (oracle K). **A miss is only a missing
file**: three hosted rows place a broken container at a key path and assert `R6_KV_DIGEST("plane")`,
`R6_KV_TOKENS`, and `R6_KV_IDENTITY("pack")` rather than a re-prefill. Schema **6** adds a `store`
object to every document; **no path is published**. `src/kv_plane.align`'s writer, reader, header
plan, and every bound are unchanged and the container is asserted byte-identical to a `KV_SAVE` one.

**Files.** `src/kv_plane.align` (+`derive_key`, `store_path`, four constants),
`src/decode_step.align` (the operand, step 2d, L0, `render_store`, schema 6),
`src/model_forward.align` (**five `Outcome` fields only** — section 12 deviation D1),
`scripts/kv_plane_reader.py` (a second preimage implementation and the `KEY` verdict),
`scripts/run-layer-forward-smoke` (a third preimage implementation, 15 golden rows, oracle K/D),
`scripts/run-decode-step` (the real-model store leg and a third analysis block),
`scripts/decode-step-golden.jsonl` (141 → 156 rows), plus `docs/specs/roadmap.md` (items 37 and 38),
`docs/align-development.md`, `docs/align-requests.md` (Request 53), and the ledger. **The Makefile
is untouched**: no target, no aggregate membership, and no check topology moves.

**Verification, all green at this head** (`gmake`, `LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib`):
`gmake build`, `gmake check` (31 units), `gmake layer-forward-smoke` (158 documented cases, 156
golden rows, 42 codes), `gmake ggml-spike-smoke`, `gmake gate-topology-check`, `gmake fmt` leaves no
diff, `gmake format-check`, `git diff --check`. The golden movement was verified **mechanically**:
all 141 pre-existing rows differ only in `document_schema_version` 5 → 6 plus a default `store`
object, in the same order, with no row removed. **Five ledger mutants were run at the final head and
all five died**: a preimage field dropped in one of the three implementations, a hit treated as a
miss, a key that ignores the token stream, the container's path published in the document, and a
miss that saves after the suffix pass.

**One real defect was found and fixed during implementation, and it is deviation D14.** The
`KV_SAVE` writer's call site is *after* the suffix pass, which was correct for every prior run
because `SUFFIX` is illegal beside `KV_SAVE`; a keyed **miss** is the first run that has both, and
the first implementation inherited the position and persisted a plane carrying `T_prefix + S`
columns under a header declaring `columns_persisted = T_prefix`, with the suffix pass's
`prefill_argmax`. It round-trips through the arm, so oracle K passed — it was caught by the two
container assertions instead: the keyed container was **not** byte-identical to the `KV_SAVE`
container of the same prefix, and the independent reader refuses it as `ZEROTAIL`. The fix is one
guarded call site before the pass; the regression is `ds-store-suffix-vs-kv-save`, which is also the
fifth mutant.

**Next actions, in order.** (1) `gmake decode-step-qualification` on the reference host — **not run:
the host never freed**. Memory was polled 18:30-20:01 (91 minutes) against the 6 GB coordination
floor and measured 3.2-4.97 GB throughout, with concurrent Docker-in-Docker preflights from other
work holding the box; nothing was killed and nothing was run below the floor. The leg and its
analysis block are implemented and dry-run against the hosted golden documents; this is the last
piece of the acceptance rule and must run before the pull request. (2) `python3 scripts/pre-pr
--owner-test layer-forward-smoke -- gmake layer-forward-smoke`. (3) One comprehensive review.
(4) Merge **after** item 36.

**Blockers.** Item 36's own two real-model legs, which block its publication and therefore this
branch's merge — not its implementation. Host memory for this branch's own qualification.

**New Align request 53** (`std.fs` `create_dir` / `read_dir` / `is_dir`), `PROPOSED`, `medium`,
non-blocking; its resume condition is a store eviction/GC capability. **52 is deliberately left
unclaimed** for the parallel item-31 branch, and both numbers must be re-checked at merge. Request 30
gains a third client (the store's check-then-create window, which at this pin lets a concurrent loser
**overwrite** rather than be refused — deviation D6), Request 49 gains a recorded **negative** client,
and Request 31 gains the correction a store owes it and **stays low and non-blocking** with its
reason.

## Stacked base: MF-SINGLE-TOKEN-LOGITS (2026-08-29)

Branch `agent/mf-single-token-logits`, cut from `origin/main` `553563e` (PR #147,
R6-RESIDENT-WEIGHTS) and brought up to `origin/main` `a9561a9` (PR #149, R6-PREFIX-SUFFIX-PREFILL)
by `git merge`, **never a rebase**. Three conflicts, all resolved by keeping both sides:
`HANDOFF.md` (item 33's block demoted to a merged checkpoint), `docs/specs/roadmap.md` (item 33 then
item 36), and `scripts/decode-step-golden.jsonl` (taken from `main` and regenerated).
Roadmap item **36**: 31, 32, 34 and 35 are reserved by capabilities on branches or in draft, and
this one merged out of order. A **bug fix**, filed by `R6-PREFIX-SUFFIX-PREFILL` 11.2;
`docs/specs/mf-single-token-logits.md` is the authoritative record and carries the result in its
section 5. No design gate (no CLI operand, exchanged or persisted format, or ownership boundary
moves), no Align gap, no new Align request.

**Defect.** `fill_members` and `compare_source` gathered a member's rows by token id only where
`m.pieces[at] > 1` — the piece count used as a proxy for "this member is the per-token embedding row
set". `build_embed_members` sets `pieces = tokens`, so a **one-token prefill** took the whole-member
branch and read row 0 of the embedding table instead of the prompt's row: wrong logits with
`status: ok` on four public arms — `--model-forward`, `--model-forward-gpu`, `--moe-model-forward`,
and `--decode-step`'s prefill. `--layer-forward` and `--moe-layer-forward` gather unconditionally
and were never affected. The resident path was **not** immune, correcting 11.2 of the filing
document: `stage_embed_row` staged the right row while `compare_source` still expected row 0, so a
one-token non-zero resident run with a reference reported `R5_SOURCE_DIVERGED` over a correct
result.

**Fix.** `gathered: bool` on both `GraphMembers` records, `true` from `build_embed_members` whatever
the count and `false` from every other builder across ten construction sites in four modules,
and the predicate `m.gathered && at == 0` at all four sites. `gathered` is true exactly where
`pieces > 1` was, so `T >= 2` is byte-identical.

**Evidence.** Six **new** golden rows and **no changed row** — verified mechanically: all six
corpora are pure appends, `mf-tokens-one-zero` keeps the `62a46efd…` digest the defect produced for
every one-token run and `mf-tokens-one` is now `867ebc4e…`, which `gf-tokens-one`, `ds-tokens-one`
and `ds-tokens-one-resident` also carry. Two mutants were run: reverting the four predicates to
`pieces > 1` kills exactly the six new rows and nothing else, and restores the
`R5_SOURCE_DIVERGED` false alarm on `ds-tokens-one-resident`; setting `gathered: false` at
`model_forward.build_embed_members` kills the three-token corpus as well.

**The lift, done in this branch.** Item 33's `T_prefix >= 2` bound existed only because of this
defect. Step 3c's term and its `R6_SUFFIX prefix[<n>]` detail are deleted; `ds-suffix-prefix-one` is
a passing oracle-S row at `T_prefix = 1` (`0cd795d9…`, byte-identical to the new
`ds-suffix-single-shot-2` comparand and to `--model-forward` at `3,5`), joined by
`ds-suffix-save-prefix-one` — a one-token prefill save whose `867ebc4e…` is the same digest
`mf-tokens-one` carries. `scripts/run-decode-step`'s split guard widens from `2 <= j` to `1 <= j`,
which adds no real-model run. `r6-prefix-suffix-prefill.md` gains **section 11.5** and its 2.3, 2.7,
3.7, 5.6, 5.7, 9.1, 11.1 correction 8, 11.2 and 12.1 are corrected in place. The decode-step corpus
is 137 → **141** rows with exactly one changed row, `ds-suffix-prefix-one`, refusal to pass.

**Not started / next.** The two real-model legs (`gmake model-forward-qualification` and
`gmake moe-model-forward-qualification`), which are waiting on host memory — another agent's DinD
holds the box below 6 GB free. Then publication
(`python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke`) and one
comprehensive review.

## Merged checkpoint: R6-OLMOE-DECODE (PR #148, 2026-08-29)

Branch `agent/r6-olmoe-decode`, implemented on `agent/r6-resident-weights` head `6facd56` and then
**merged** with `origin/main` `553563e` (R6-RESIDENT-WEIGHTS, PR #147, carrying `cec1758`) by
`git merge` — **never a rebase** — a clean fast-forward touching five files, none of them this
capability's. The four things that merge re-checks all held: roadmap item **32** (30 is
RESIDENT-WEIGHTS, 31 is claimed by `agent/c4-repair-measured` on its own branch), the new document
kind `R6_MOE_DECODE_STEP` at schema **1** (which collides with nothing, because it is a new kind),
the next free Align request number (**53**; 52 is taken by the C4 branch, and this capability takes
none), and which goldens regenerate.

**Merged a second time, with `origin/main` `a9561a9`** — R6-PREFIX-SUFFIX-PREFILL, PR #149, which
landed during this capability's publication — again by `git merge` and never a rebase, so the
recorded baseline-chain commits stay reachable. Three files conflicted and all three keep **both**
sides: `scripts/build-ggml-shim` (three routed forced-build arms beside that capability's two
suffix ones), `docs/specs/roadmap.md` (item 32 beside item 33, with the reservation comment narrowed
to item 31, which is still on the C4 branch), and `HANDOFF.md`. The four re-checks hold again:
roadmap item **32**, document kind `R6_MOE_DECODE_STEP` at schema **1**, the next free request number
(the register on `main` still ends at **51**, PR #149 filed none, and this capability files none),
and the goldens — `scripts/decode-step-golden.jsonl` is that capability's at **137** rows and this
branch does not touch it, `scripts/moe-decode-step-golden.jsonl` is this one's at **59**.

**Capability.** `N` greedy decode steps on OLMoE-1B-7B-0125-Instruct Q4_K_M over an Align-owned KV
plane, each step resolving its own top-8 expert claims per layer and computing only those experts,
weights **streamed**. CPU only. Authoritative ledger `docs/specs/r6-olmoe-decode.md`; sections 1 to 5
are the pre-implementation design and 6 onward record what was built and every deviation. Three of
the four design-gate triggers fire, including — for the first time in this wave — the
coordinated-invariant one.

**Complete.** Cell **G-P1** (50,304 rows of Q4_K, 50,057 distinct fingerprints, two collision
classes covering 249 ids of which **two** are not all-zero: `{45382, 50278}`); `src/layer_olmoe.align`
with `OP_CONCAT`, `WHEN_DECODE`, `mm_row_issued_at`, a **thirty-seven-row** `mm_decode_a_node_table`,
`mm_decode_b_node_table` at its own base 58, `MM_SLOT_KPAST`/`VPAST` at the top of the slot map,
`MM_K_ROW`/`MM_V_ROW`/`MM_DECODE_K_CONCAT_ROW`/`MM_DECODE_V_CONCAT_ROW` derived by reading the
tables, `mm_write_mask_offset`, `mm_oracle_table_at`, `MAX_DECODE_STEPS := 64`, and
`MAX_PREFILL_TOKENS 6 -> 32`; `src/moe_decode_step.align` (~4,400 lines) with the arm, the plane, the
loop, the two-way claim accounting, and the `R6_MOE_DECODE_STEP` schema-1 document;
`src/moe_model_forward.align` widened to `pub` where the new module imports it, plus
`stage_carry_at`, `stage_plan_owned`, and the decode arm's `Outcome` fields; `scan_transcript_after`
on the routed side; one `import` and one `if` in `src/ggml_spike.align`; the fixture's routed decode
corpus; the **seventh** block of `scripts/run-layer-forward-smoke` and
`scripts/moe-decode-step-golden.jsonl`; `scripts/run-moe-decode-step` and one `Makefile` target.

**The `R5_ORACLE_TRUNCATED` guard is new, and its absence was a real gap.** The design predicted that
`--moe-layer-forward` and `--moe-model-forward` already shipped it, as the dense arms do. They did
not: at a cap of six tokens the condition was unreachable. The lift to 32 makes it reachable, so both
arms now refuse a prefill above six tokens **with** a transcript, and `moe-tokens-33` /
`mm-tokens-33` plus `*-tokens-seven-with-transcript` pin both halves.

**Golden movement, measured against the merged head.** Five goldens byte-unchanged
(`layer-forward`, `model-forward`, `gpu-forward`, `decode-step`, `ggml-spike`); one new
(`moe-decode-step-golden.jsonl`, **59** cases after the review repair); and `moe-layer-forward-golden.jsonl` and
`moe-model-forward-golden.jsonl` each **-1 renamed, +3 added, and zero pre-existing rows changed in
value** — `moe-tokens-seven` becomes `moe-tokens-33` and gains
`moe-tokens-seven-with-transcript` and `moe-tokens-seven-no-transcript`, and the same three on the
`mm-` side. The routed pack itself is byte-identical, because
`MOE_MODEL_DECODE_RESEEDED_ROWS` is empty: the routed decode chain is already non-degenerate.

**Result** (the qualification of record, `gmake moe-decode-step-qualification`, four prompts x
`N = 16` x three runs, Apple M1, `KV_WIDTH` 256, weights streamed, CPU only, **re-run at the review
repair head**, exit 0; **1 min 23.4 s** warm and **5 min 41.3 s** with the page cache evicted by a
concurrent build, against 3 min 18 s cold at the implementation head — the spread is the 4.2 GB
pack's residency and every correctness value is identical across the runs). Gate G
over 64 ids, oracle R **`MATCH` at 8,192 of 8,192** — the first full-axis routing identity in the
repository — oracle B `IDENTICAL`, oracle T `PASS` with `max_abs_diff` **0**, and the claim
accounting exact on all 64 steps. **Every correctness value reproduced exactly**; the residency
columns below are the repaired metric:

| prompt | oracle R | step bytes (arith) | step bytes (`pread`) | ampl | union keys | mean marginal | demands in prefill | distinct in prefill | reuse ppm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `def add(a, b` | 2048/2048 | 487,587,840 | 487,587,840 | **0 ppm** | 585 | 57.9 MB | 1540/2048 (75.2 %) | 273/515 (53.0 %) | **748** |
| `The capital of` | 2048/2048 | 487,587,840 | 487,587,840 | **0 ppm** | 698 | 92.3 MB | 1064/2048 (52.0 %) | 240/627 (38.3 %) | **693** |
| `import os` | 2048/2048 | 487,587,840 | 487,587,840 | **0 ppm** | 614 | 95.4 MB | 1154/2048 (56.3 %) | 173/573 (30.2 %) | **720** |
| `return x +` | 2048/2048 | 487,587,840 | 487,587,840 | **0 ppm** | 607 | 83.1 MB | 1182/2048 (57.7 %) | 212/561 (37.8 %) | **726** |

**The two accountings agree to the byte and the read amplification is zero**, which is the strongest
form the primary claim could take: the arm read exactly what it claimed and not one byte more.
**The streamed-to-marginal gap is 5.1x to 8.4x at sixteen steps, not the 9.2x a four-step probe
suggested.**

**`step_reuse_per_mille` was the wrong quantity and is re-recorded.** The first implementation
published `(demands - |decode keys the prefill did not hold|) / demands` — prefill-relative reuse —
under section 3.11's name, which defines `distinct` as the decode steps' **own** key set. The
figures were 881/811/804/829; they are **748/693/720/726**. The fixture reproduced the
implementation's arithmetic verbatim, so the generator, the golden and the smoke assertion all
agreed with the wrong number: the oracle was co-derived with the subject, and it is now derived
independently from the routings alone. The hosted figure moved 833 -> 333. Section 12.3's "roughly
twice the adjacent-pair one" is **re-derived**: 1.55x to 1.67x R2D's pooled 447, about as much as an
adjacent-pair window captures at its *best* transition, not twice it.

**"Four fifths of every decode demand is already in the prefill" now has both of its fractions.**
Demand-weighted it is 52.0 % to 75.2 %; over **distinct** decode keys — the form section 2.4 reading
2 actually predicted at 79.9 % — it is **30.2 % to 53.0 %**, and that is the reading that collapses.

**Cell C-P1** selected oracle C′'s second branch and the fallback is now **implemented**, not
asserted on argmax alone: at all twelve checkpoints the runner reports the verdict with argmax
equality, top-ten **set** equality, and `max_abs_diff` in ten-thousandths over the union of the two
top-tens. Measured: 1 `IDENTICAL`, 6 `WITHIN`, 5 `FAIL`; argmax 12/12; the pre-committed 5000 bound
holds 12/12 (range 0 to 3,678); top-ten **set** equality holds only **7 of 12**. Section 4.4's
non-identical branch had already moved the acceptance weight to G, R and B, so the shipped rule
reports the verdict and gates on argmax alone — a first draft gated on the whole triple and refused
the run, and that refusal is the measurement.

**Verification, at the repair head.** `gmake build`, `gmake check`, `gmake layer-forward-smoke` (all
seven blocks, 80 s, 59 documented cases in the seventh, every golden as predicted),
`gmake ggml-spike-smoke`, `gmake gate-topology-check`, `gmake fmt` (no change), `gmake format-check`,
`git diff --check`, and the real-model qualification above. **Nine mutants re-injected by file-level
backup** (never by copying this linked worktree — its `.git` pointer writes through to the shared
worktree administration directory): eight die, including the three new ones — axis 0 mapped
unconditionally dies as `md-used-eight: routing MISMATCH`, axis 1 never mapped dies as
`md-used-eight: oracle T FAIL worst ffn_moe_up max_abs 8726`, and `step_reuse_per_mille` restored to
the prefill-relative quantity dies as `833, not the generator's 333`. The ninth, `MM_V_ROW` 13 -> 12,
is **inert and not a gap**: row 12 is the `MUL_MAT` and row 13 a `RESHAPE_3D` view over the same
buffer, so the plane receives the same bytes.

**The qualification needs one ggml build on both sides, and that is a toolchain debt this capability
records rather than pays** (section 15 of the ledger). `scripts/llama-eval-callback-toolchain` builds
the R2C instrument with `GGML_ACCELERATE=ON`/`GGML_BLAS=ON`; Homebrew's ggml at the **same commit**
has neither, and the same prompt gives `result_output` sums of -113,284.84 and -111,030.03. Every
earlier consumer of that instrument parsed text; this is the first to compare it numerically. The
runner's instrument cross-check caught it before the arm ran and reported it as an instrument skew,
which is what that check exists for.

**Constraints.** CPU only; streamed weights, **by design and not by cost** — residency would make the
primary metric zero. No TTFT, throughput, or performance claim, and no cost ceiling: this capability
makes a measurement claim and `docs/specs/r6-resident-weights.md` section 3.4 remains the owner of
Track B decode performance.

**Blockers.** None. Five Align gaps are met and all five are already recorded with named clients
(Requests 33, 36, 47, 48, 49); none blocks, and Request 49 gains its largest client — whose recorded
duplication count is corrected from 23 to **36**, regenerated from the source, with the predicted
duplicated `refill` removed because it does not exist.

**Final review minors applied.** One final delta review of the repair head `bf7c87d` returned
**approve with minors** — three stale "57" case counts in section 14 that the deviation-16 repair
took to 59, one deviation cross-reference (16 -> 18), a clause recording that the union-versus-
adjacent-pair ratio's *direction* is structural and only its magnitude informative, and one
108-column roadmap line. All four are applied in `a5c216a`, are **Markdown only**, and touch no
source, script, fixture, golden or `Makefile`, so the qualification recorded at `bf7c87d` stands.
Re-verified at `a5c216a`: `gmake build` ok, `gmake format-check` PASS, `gmake layer-forward-smoke`
PASS (seven blocks, 1 min 28 s, 13 no-document and 59 documented cases in the seventh),
`git diff --check` clean.

**Coding-baseline chain, re-recorded.** `Makefile` is in this publication diff, so `main`'s chain no
longer binds this head. The pending record was measured on **Linux** (aarch64, kernel
6.11.11-linuxkit, Python 3.12.3) through the DinD wrapper at the publication head, and the chain is
**source `a5c216a` -> oracle `4cab8a7` -> finalization `245f7f5`**. `gmake baseline-check` inside the
same Linux image ends `baseline chain: PASS`.

**Publication found one more thing, and it is deviation 19.** The `Installed Ubuntu 24.04
fresh-image profile (aarch64)` check failed **twice** at PR #148 with the canonical, detail-free
`fresh compiler: ERROR CHILD aggregate`, at `worker-aggregate` phase durations of **1,992 s** and
**2,000 s**, where `main` measured 1,867 s (PR #143) and 1,892 s (PR #144) and passed, `x86_64`
measured 1,778 s and passed, and this host's own installed-profile run passed at 1,875 s. The
aggregate child is `make capable-checks`, of which `layer-forward-smoke` — and therefore this
capability's seventh block — is a member, and it runs under one `AGGREGATE_TIMEOUT`. That constant is
**1,800 s -> 3,600 s** in `scripts/fresh-align-compiler`, with the measurement in its own comment.
`enforce_aggregate_quota` is unchanged, so what the child may *consume* is bounded exactly as before.

**Two environment findings worth carrying forward.** (1) The local DinD preflight must run
`scripts/pre-pr` as an **unprivileged uid**: R6-KV-PERSIST's `ds-kv-save-unwritable` builds a `0555`
directory and asserts `R6_KV_UNWRITABLE`, and root writes into it anyway, failing 26 assertions of
that block. GitHub's runners are unprivileged, which is why hosted CI never saw it.
`scratchpad/dind-prepr-r6m-user.sh` starts `dockerd` as root and drops to uid 501 for the preflight
itself. (2) The fresh worker's aggregate had been sitting at roughly 98 % of its wall-clock cap on
the slowest supported architecture; one added smoke block crossed it.

**Next actions, in order.**
1. `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` on the
   unchanged head. The diff touches `Makefile`, `scripts/build-ggml-shim`, the fixture, the smoke and
   the goldens, so the classifier selects the **executable** row and the **installed fresh-image
   profile** (`--plan` reports scope `fresh-image`); do not substitute a Docker skip or an ambient
   `DOCKER_HOST`.
2. Open the English pull request with the verification table, the review envelope, the finding
   dispositions and the consolidated repair commit. It must be a **merge** commit: squash or rebase
   would make the baseline commits unreachable from `main`.
3. `gmake ci` is **not** selected: this repair changes no aggregate membership, no check topology and
   no integration behaviour, and `scripts/check-gate-topology`'s byte-literal EXPECTED does not move
   (`moe-decode-step-qualification` stays in `.PHONY` and in no aggregate).
4. After merge, refresh `main` and start the next eligible roadmap capability.

**Reproducing the qualification on this host, exactly.** All three of the arm, `llama-eval-callback`
and `llama-debug` must be **one ggml build** (deviation 4). The `r2c-v2` cache holds only a
statically linked `llama-eval-callback`, so configure the pinned source once with
`BUILD_SHARED_LIBS=ON` and the toolchain's other flags verbatim
(`CMAKE_BUILD_TYPE=Release`, `GGML_NATIVE=OFF`, `GGML_METAL=OFF`, `GGML_OPENMP=OFF`,
`GGML_CCACHE=OFF`, `LLAMA_CURL=OFF`, `LLAMA_BUILD_EXAMPLES=ON`, `LLAMA_BUILD_TESTS=OFF`,
`LLAMA_BUILD_NUMBER=10566`, `LLAMA_BUILD_COMMIT=bb4caa754`) and build the `llama-eval-callback` and
`llama-debug` targets. Then `ALIGN_LLM_GGML_INCLUDE=<source>/ggml/include`,
`ALIGN_LLM_GGML_LIB=<build>/bin`, and both instruments from `<build>/bin`. The runner's new preflight
checks that pairing by resolved object identity and refuses a mismatch. **Two repairs were needed to
make this a one-command run**: `ALIGN_LLM_GGML_LIB` now joins the loader path, and the real shim
records it as an `-Wl,-rpath` — macOS strips `DYLD_*` from `/usr/bin/time`, which is how the arm is
launched, so the environment variable alone aborts it inside `dyld`.

**Intentional uncommitted files.** None.

## Merged checkpoint: R6-PREFIX-SUFFIX-PREFILL (PR #149, 2026-08-29)

Merged as `a9561a9` on `main` while R6-OLMOE-DECODE was in publication, and taken into
that branch by `git merge origin/main` — never a rebase. The next actions this section
recorded are discharged by that merge; the record below is kept as the capability's own.

Branch `agent/r6-prefix-suffix-prefill`, cut from `origin/main` `553563e` — the merge of
R6-RESIDENT-WEIGHTS (PR #147). **The capability is committed** (`6cef75b`), with its review repair
and the final delta review's minors on top; the tree is clean and every hosted check passes at the
head. `origin/main` has not moved since the branch was cut, so **no merge is owed**: the merge base
is still `553563e` and the branch is three commits ahead of it.
`docs/specs/r6-prefix-suffix-prefill.md` is the authoritative ledger: sections 1 to 4 are the design,
5.1 to 5.4 the verification plan, **5.5 to 5.10 the hosted, mutation, real-model and TTFT results**,
**11 what implementation and the review found**, and 12 the ledger-to-diff mapping.

**Reviewed and repaired.** One comprehensive review of `6cef75b` over two disjoint reviewers — A on
`src` plus the runner, smoke and shim, B on the document and the reconciliation edits — returned
8 major and 16 minor findings, no blocker; 24 dispositions, all applied, two of them as evidence
rather than a code change (the `R6_TOKENS` precedence row does establish `3 ≺ 3c`, recorded in 5.6;
and section 11.2's recorded digest does reproduce once the command is runnable). A **final delta
review** of the repair — required because the repair added a contract, `T_prefix >= 2` — approved
with three minors, applied on top: the 11.2 reproduction needed `LIBRARY_PATH` exported before the
build line (it now runs end to end and reproduces `62a46efd73d18be1...` and the control
`99781f3e63a67b18...`), acceptance rule 7 points at the shipped matrix in 5.6 rather than 5.2's
superseded prediction, and the smoke's refusal-detail assertions are one named
`SUFFIX_REFUSAL_DETAILS` tuple of all **thirteen** documented details that the summary line counts,
instead of a literal loop counted from `STUB_CASES` membership. The one that changes behaviour is a
**contract addition**: `SUFFIX` now requires `T_prefix >= 2` and refuses `R6_SUFFIX`/`prefix[<n>]`
otherwise, because a one-token prefill computes the wrong embedding row (see the defect below) and
the equality oracle would have failed silently. The rest are the split guard (`2 <= j`), the witness
guard checking fields rather than blocks, the stub's suffix latch being cleared after the pass, and
document currency.

**Capability.** `R6-KV-PERSIST` made a prefill plane outlive its process, but only for the prompt it
was saved for — the arm had no graph that computes more than one column at `n_past > 0`. This ships
that graph. `--decode-step` gains a fifteenth operand, `SUFFIX` (a token id list or `-`), legal only
with `KV_LOAD`: the arm loads a container holding `T_prefix` columns for exactly the tokens in
`TOKENS`, runs **one suffix pass** over the `S` suffix tokens at absolute positions
`T_prefix .. T_prefix+S-1` causally masked over prefix-plus-suffix, writes their K and V into the
plane at columns `T_prefix ..`, verifies the plane over all `T_prefix + S` columns, and then
continues the existing `N`-step loop from `n_past = T_prefix + S`. **Nothing is re-saved and the
`akvp` format is byte-unchanged.** Dense Qwen2.5-Coder-7B Q4_K_M, CPU only. The oracle is that a
suffix run and a single-shot prefill of `TOKENS ++ SUFFIX` are **the same run**.

**Complete.** `SUFFIX` at `args[14]` with arity 15 and step 2c's conditional rule; `R6_SUFFIX` with
four details (`suffix[<text>]`, `prefix[<n>]`, `sequence[<n>]`, `token[<index>]`); step 3c and the
widened step 6; `mf_decode_layer_node_table(g, n_past, tokens, width)`
with **six** literals parameterised across three functions; `decode_layer_inputs`/`_values`,
`capture_plane`, and `verify_plane` at `tokens`; `decode_pass` at `tokens_in` with its own
`suffix_pass` counter; eleven `Outcome` fields and the `suffix` object at document **schema 5**;
`output`/`oracle_logits` moved to the pass's own logits on a completed run with the container's
vector kept in `kv`; 22 new cases and **21** new golden rows (three oracle-S splits, twelve refusals
including the repair's `ds-suffix-prefix-one`, three comparands, two forced builds, and a resident
leg, minus the four-token comparand kept out of the cross-platform golden), two stub
shim arms and two builder flavours;
`scripts/run-decode-step`'s per-split suffix leg with oracle S, oracle C″, oracle B, gate G, the
accounting, and the three-leg TTFT diagnostic; roadmap item **33**, `docs/align-development.md`,
Request 49's negative client line and Request 22's cheaper-absence line, and
`docs/specs/r6-kv-persist.md`'s `document_schema_version` correction.

**`src/kv_plane.align`, `scripts/kv_plane_reader.py`, `src/ggml_ffi.align`, `scripts/ggml_shim.c`,
`src/ggml_spike.align`, the `Makefile`, and `scripts/layer_forward_fixture.py` are byte-unchanged.**
No new ggml op, shim symbol, node row, slot, or Align surface, and no aggregate membership or check
topology change, so `scripts/check-gate-topology`'s byte-literal EXPECTED does not move.
`scripts/ggml_shim_stub.c` and `scripts/build-ggml-shim` are not unchanged: two arms in the test
double, recorded as section 11.3 deviation 3.

**Risk 1 was discharged first, as the design asked.** `ds-suffix-3` was run before any refusal case
was written, and oracle C″ was byte-identical on the **first** implementation checkpoint: the
column-count sensitivity R6 measured in llama.cpp does not appear between this arm's own two paths
at `S >= 2` **and** `n_past > 0`. It never reappeared on any later run, hosted or real-model.

**Goldens.** `scripts/decode-step-golden.jsonl` 116 → **137**. A programmatic diff confirms the only
fields that changed in a pre-existing row are `.schema_version` (4 → 5) and the added `.suffix` — the
prediction exactly. **Every other golden in `scripts/` is byte-unchanged**, all six.
**Hosted CI refused one added row and it is out**, recorded as section 11.3 deviation 7:
`ds-suffix-single-shot-4`, a four-token single-shot prefill, has `.schedule[1].l_out_bit_sum`
12,689,786,356 on macOS/arm64 against 12,689,786,355 on Linux/x86_64. It moves into
`BOUNDARY_CASES` on `ds-resident-stage-full`'s precedent — still run, still recorded, still compared
by oracle S **within one host** — and only the committed row goes. Risk 4's five-column mitigation is
wrong as stated: a 1-ULP disagreement is available at any width and this fixture reaches it at four
tokens, which the next capability adding a multi-token prefill case needs to know.

**Findings, in section 11.** Oracle S's exclusion list needed four more fields and
`plane.roundtrip_bytes_compared` a fifth, each **compensated by an explicit assertion** rather than
dropped, with a witness guard so a later widening fails; two refusal details in the design's matrix
were wrong and the implementation follows `R6_TOKENS`' own shape; the decode table holds six
token-count literals and not five; the suffix pass's specs must carry `compare = false` or a run
with a transcript panics; and `output`'s digest is taken twice so that a failed pass publishes the
container's vector.

**A pre-existing defect this capability found and did not fix — follow-up capability
`MF-SINGLE-TOKEN-LOGITS`, no roadmap number yet (section 11.2, and a named follow-up under roadmap
item 33).** **A one-token prompt
computes the logits of token 0.** `model_forward.fill_members` gathers by id only when
`pieces > 1`, and `build_embed_members` sets `pieces = tokens`, so at `tokens == 1` it reads the
embedding table's first row. Measured: `--model-forward` at `0`, `3`, and `17` returns one digest.
Reachable from the shipped CLI, silent, and **not shared by the resident path**. No golden exercises
`token_count == 1`, so it has been latent since R5B. It is not fixed here because the honest fix is a
discriminator on `model_forward.GraphMembers` — eighteen construction sites, three modules, four
arms — needing its own regression and its own review, and it is a distinct failure domain, which is
`CLAUDE.md`'s own reason to split. This capability depends on none of it: the hosted matrix has no
`T_prefix = 1` case and the real-model leg's smallest split is already `j = 2`. **The review found
that avoiding it in the corpus is not the same as refusing it on the surface**, so the arm now
refuses `T_prefix = 1` with a `SUFFIX`. Completing `MF-SINGLE-TOKEN-LOGITS` removes that refusal,
which widens the surface rather than moving it. Reproduction, evidence, owner surface, blast radius,
and the regression it must add are the field table in section 11.2; it needs a
`python3 scripts/pre-pr` of its own and takes a roadmap number when it is picked up.

**Blockers.** None. No Align request is proposed; Request 49 gains a **negative** client (the gap
shaped nothing, because the plane's only mutator is already in `decode_step`) and Request 22 gains a
note that a suffix is an operand rather than decoded text.

**Classifier scope.** `src` and executable scripts change, so the classifier selects the executable
row and **hosted** preflight: `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake
layer-forward-smoke`. `make ci` is **not** selected — no aggregate membership, check topology, or
integration behaviour changes and this is not a `.align-revision` change — and `baseline-check` is
`N/A` on R6-STEP-N's condition (the `Makefile` is byte-unchanged and both new shim arms are inputs
to the **stub**). Re-checked at the publication head:
`python3 scripts/verification_scope.py --base origin/main --head HEAD` returns
`{"docs_only":false,"fresh_focused":false,"fresh_installed":false,"hosted":true,"scope":"hosted"}`,
so no fresh-image profile and no Docker are selected and the baseline artifacts are not consulted.

**Four merge re-checks this family always carries.** Roadmap item **33** (31 and 32 are on
branches), document schema **5**, next free Align request **53** (52 is expected to be claimed by a
parallel branch), and `scripts/decode-step-golden.jsonl` regenerated from the merged head. All four
hold at the publication head and `origin/main` is unmoved, so nothing was merged in; if it moves
before this lands, merge it by `git merge`, **never a rebase**, so every stacked branch's recorded
commits stay reachable, and re-check all four.

**Verification checkpoint (publication head).** `gmake build`, `gmake check`, `gmake fmt`,
`gmake format-check`, `git diff --check`, `gmake gate-topology-check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` (all six blocks; **139** documented decode-step cases, **137** with a
golden row, 42 codes, **13** suffix refusals each with its detail asserted, 52 `KV_REFUSALS` rows)
all pass; the owner is 65.9 s real at the repaired head and ~50 s at the publication head.
`python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` is stamped at
the publication head, and hosted CI passes there on all three jobs.
**`gmake decode-step-qualification` was not re-run for the repair or the minors**, and the reason is
that no changed line can reach it: the `2 <= j` guard removes a split the four prompts never
produce (the smallest `|L|` is 3), the `T_prefix >= 2` refusal cannot fire at `j >= 2`, the stub
latch lives in a forced build the qualification never builds, and the remaining changes are the
witness guard, the smoke's own assertions (this leg does not run that runner), comments, and
documents. The five recorded splits and every verdict below stand.
**`gmake decode-step-qualification`
exits 0 on the real model at `N = 16`**, with five prefix/suffix splits over the four prompts and
every one of oracle S, oracle C″, oracle B over `T_prefix + S` columns, and gate G1 **IDENTICAL** —
`case1` at `(T_prefix, S) = (2, 4)` and `(3, 3)`, the other three prompts at `(2, 1)` because they
tokenize to three ids. Both `case1` splits decode the same four ids, which is oracle S's claim seen
from outside: where the split falls does not change the run. It was run **twice** — the first run
found the TTFT trio's own comparability defect (section 11.3 deviation 6) and the second is at the
corrected head; the acceptance verdicts are identical in both. Instruments unchanged:
`ALIGN_LLM_LLAMA_DEBUG=/opt/homebrew/bin/llama-debug` (build 10566, `bb4caa754`) and the R2C-patched
`llama-eval-callback` from the `r2c-v2` cache. **The host was under memory pressure during both
runs** (another agent's OLMoE qualification had just finished), so R6-RESIDENT-WEIGHTS' own scaling
leg reports slower absolute elapsed times than its recorded run; that leg still reports its floor
MET and it is **not** this capability's claim — every verdict this capability owns is byte identity
and is unaffected by host load.

**Eight mutants injected at the repaired head, eight killed under `gmake layer-forward-smoke`.**
Suffix positions off by one; the mask offset wrong for `S > 1`; the write-back column base wrong
**at `S > 1` only**; the verify range at R6-STEP-N's exact old bound, which is correct for every
step and wrong only at `S > 1`; `mf_decode_row_tail`'s sixth literal back to a hardwired `1`, which
dies as `R5_SHAPE suffix[]node[26]`; and oracle S's exclusion list widened three ways — by the
**blocks** `decode`/`steps`/`output`, by the **field** `("decode", "token_ids")`, and by
`("decode", "n_past_first")`/`("n_past_last")`. **The `token_ids` field mutant survived at
`6cef75b`** and is why the witness guard now names fields rather than blocks; all three die now. The
two suffix-only arithmetic mutants die naming the exact case and the exact column
(`suffix[]layer[0]tensor[k]col[2]` and `col[-1]`).

**Next actions, in order.** (1) Publish the English pull request with the review envelope, every
finding's disposition, the consolidated repair commit, and the exact commands and results. (2) Merge
once the required checks pass. If `origin/main` moves first, `git merge` it — **never a rebase** —
re-check the four merge items above, regenerate `scripts/decode-step-golden.jsonl` from the merged
head, and re-stamp `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake
layer-forward-smoke`, because the stamp belongs to an exact unchanged `HEAD`. (3) Re-check the four
items at the merged head. (4) Pick up `MF-SINGLE-TOKEN-LOGITS` or the next eligible roadmap
capability.

**Intentional uncommitted files.** None. The tree is clean and there is no scratch file inside it.


## Merged checkpoint: R6-RESIDENT-WEIGHTS (PR #147, 2026-08-29)

Branch `agent/r6-resident-weights`. Implemented on `agent/r6-kv-persist` head `9699848`, then
**merged** with that branch's review repair `1971c61` and its own `main` merge `bdb34eb` — which
carries `main` `3df063b` (R6-STEP-N, PR #145) and R5E-MOE-MODEL-PREFILL — by `git merge`, **never a
rebase**, so every stacked branch's recorded commits stay reachable. The four things that merge
re-checks all held: roadmap item **30** (29 is KV-PERSIST), document schema **4** (KV-PERSIST took
3), Align Request **50** (1–49 taken), and `scripts/decode-step-golden.jsonl` regenerated from the
merged head. Both R6 branches have now landed: `origin/main` is at `a6e545b` (R6-KV-PERSIST, PR #146, carrying
its final review minors `5c53ea1`), taken here by `git merge origin/main` — a clean merge, two files,
no conflict — and all four re-checks held again: roadmap item **30**, schema **4**, the next free
Align request number (now **52**, because this capability's review filed **51**), and the golden.

**Capability.** The whole weight set held **resident for one process's lifetime**, so that after one
fill every decode step reads exactly zero pack bytes. Dense Qwen2.5-Coder-7B Q4_K_M, **CPU only**.
`docs/specs/r6-resident-weights.md` is the authoritative ledger; sections 1 to 4 are the
pre-implementation design, 5.8 to 5.10 the result, and 11.1 the corrections implementation found.
Three of the design gate's four triggers fire: a changed CLI arm, a changed exchanged format
(schema 4, a `weights` object), and — the load-bearing one — a changed **ownership/allocation
boundary**, because the weight `buffer` and its `ggml_backend_buffer` wrap move from per-graph to
run scope. `docs/specs/r5c-metal-prefill.md` section 5.4 refused that hoist once and said it belongs
to "the capability that also re-establishes the invariant it weakens"; section 4.3 is that
re-establishment, in a separate counter pair at run scope.

**Complete.** Cell RW-P1's probe (a 4.68 GB `buffer_from_host` wrap **accepted**, two context
generations placing into one wrap, interior offsets above `INT_MAX` exact, `RW-P1: PASS`);
`model_forward.ResidentLayout` + `plan_resident`/`stream_layout`/`stage_embed_row` and eight
`Outcome` fields; the `RESIDENT` operand at `args[13]` with arity 14; `R6_RESIDENT`,
`R6_RESIDENT_BUDGET`, `R6_RESIDENT_UNAVAILABLE`; `fill_resident` (one chunked pass, whole
`token_embd.weight` first); the run-scope wrap with its own counter pair and its teardown before
`backend_close`; document schema 4 with the `weights` object in **every** document; eight new smoke
cases with oracle R at one and three steps, plus `ds-force-resident-wrap` from the review repair and
`ds-resident-stage-full` from the final review; `scripts/run-decode-step`'s 12 GiB physical-memory
preflight, `vm_stat` compressor recording, both scaling legs at three runs each, oracle R on the
real model, and the arena's size recomputed independently from `pack.json`; roadmap item 30,
`docs/align-development.md`, **Align Request 50** (`std.os.physical_memory`), Request 35 raised to
**high** with the 4.68 GB abort as its evidence, and Request 38's measured Darwin `pread` boundary.

**The `Makefile` is byte-untouched.** No target, no `.PHONY` word, no build-list entry, so aggregate
membership and check topology are unchanged by construction and `scripts/check-gate-topology`'s
byte-literal EXPECTED does not move. `src/ggml_ffi.align`, `scripts/ggml_shim.c`,
`src/ggml_spike.align`, and `src/layer_qwen2.align` are **byte-unchanged**: no new shim symbol and
no new Align surface were needed, because the zero-copy placement path has been the primary weight
path since R4.5. `scripts/ggml_shim_stub.c` is **not** unchanged — one function in the test double,
recorded as section 5.9 deviation 1.

**Result** (run 4, the **interleaved** re-measurement at the repair head, which is the measurement
of record). On the reference host (Apple M1, 16 GiB), `def add(a, b):`, `KV_WIDTH` 256, baseline
re-taken back to back in the same session, three runs per point, legs alternating:

| `N` | streamed elapsed | resident elapsed | `weights.step_pack_bytes` |
| --- | --- | --- | --- |
| 1 | 5.355 s | 6.800 s | 4,370,560,992 -> **0** |
| 4 | 7.594 s | 7.721 s | 17,482,243,968 -> **0** |
| 16 | 17.112 s | **10.049 s** | 69,928,975,872 -> **0** |

**412,763 ppm of the `N = 16` fixed task against a 150,000 ppm floor: MET**, 2.75x the floor and
70 % of the 586,000 ppm ceiling recorded before implementation. That is a **shortfall with a named
cause** — the one-time fill the ceiling assumed away — and not a ceiling-estimation miss:
`docs/specs/c8-speed-first.md` section 1 reserves that label for a result *far* below its ceiling and
its own worked precedent is 41 % of one. The runner now prints the percentage on every run and
applies the label only below one half. **The qualification has now been run four times — 412,763 /
449,779 / 507,887 / 511,125 ppm — and the byte metric was identical in all four.** Run 4 is the
interleaved one: the first three took all three streamed repeats and then all three resident ones,
which confounded the leg with the clock, and the review found it. Interleaving moved the streamed
leg from 18.016 s to 17.112 s and the resident leg from 8.808 s to 10.049 s, landing **37,016 ppm
below the lowest blocked run and 98,362 below the highest** — comparable to their own 61,346 ppm
spread, so with one interleaved run the magnitude is **not separated from noise**. What is
established is that the confound is removed; the direction section 3.4 argued from thermal drift was
not confirmed. The conservative reading is the worst of the four, 412,763 ppm. Arena 4,677,533,696 B,
fill 4,669 `pread`s of 4,677,120,000 B in 1.6–2.6 s, paid once whatever `N` is. Peak footprint
504 MB -> 4.74 GB. **Residency is slower at `N = 1`, a coin toss at `N = 4`** where the four runs
disagree about the sign, and decisive from 16 up; the crossover is stated in section 5.8.1 with the
disagreement shown rather than averaged away, and it is the practical reason the operand is opt-in.
The streamed leg's total pack reads reproduce
R6-STEP-N section 5.4's recorded 8,741,169,024 / 21,852,852,000 / 74,299,583,904 **exactly at all
three points**, so the baseline this claim is made against is that document's, byte for byte.
Oracle R PASS on the real model at `N = 16` with the transcript, logits blob, and reference GGUF all
supplied.

**Goldens.** `scripts/decode-step-golden.jsonl` moves — every row to schema 4 plus a `weights`
object, and 9 new rows, 107 becoming **116** (115 at the implementation head; the review repair adds
`ds-force-resident-wrap`). A programmatic diff of the old and new files confirms the **only** fields
that changed in a pre-existing row are `.schema_version` and `.weights`, which is exactly what
section 4.5 predicted, and the repair's own regeneration is **one added row, no removal, and no
changed row**. The final review's `ds-resident-stage-full` is a **117th documented case with no
golden row**: hosted CI showed that a 32-token prefill's activations differ in the last bit between
macOS/arm64 and Linux/x86_64, so a committed row for it would pin the regenerating machine. Section
5.9 deviation 9 records it; the case is asserted by oracle R against its streamed twin, which is a
within-host comparison. The other **six** goldens — `scripts/layer-forward-golden.jsonl`,
`scripts/model-forward-golden.jsonl`, `scripts/gpu-forward-golden.jsonl`,
`scripts/moe-layer-forward-golden.jsonl`, `scripts/moe-model-forward-golden.jsonl`, and
`scripts/ggml-spike-golden.jsonl` — are byte-unchanged, verified by regenerating all six and
observing no diff.

**`arena` is a reserved word in Align at this pin.** `fn f(borrow arena: slice<u8>)` fails to parse
with `error: expected ':'` at the parameter name and cascades into a wall of unrelated top-level
errors; `arena := 3` reports at the `:=`, one token past the cause. Every identifier is
`resident_*`, `pool`, or `layout`. The reserved word is the language's prerogative and is not
requested; the **diagnostic** is **Align Request 51**, filed by the review repair with three minimal
repros at the pin.

**Blockers.** None. Request 35 makes a graceful out-of-memory refusal impossible and Request 50
makes a host-memory check impossible inside the arm; both are compensated by `RESIDENT` being
opt-in and by the runner's 12 GiB preflight, and both are recorded rather than worked around.

**Constraints.** CPU only; `--model-forward-gpu` keeps its per-graph wrap because R5C section 2.6
measured that an unfreed Metal buffer aborts at `exit`. `--model-forward` and `--moe-layer-forward`
are byte-unchanged and deferred, because they pay the streaming cost once rather than `N` times. The
measuring host is a 16 GiB Apple M1 that compresses memory under pressure, so every timed run
records `vm_stat`'s compressor counters.

**Review.** One comprehensive review of `c73d4b8` was taken as two independent adversarial passes —
one on implementation and measurement, one on specification, measurement, and governance — and
returned four major and thirteen minor findings. Every one is dispositioned; the consolidated repair
is one commit on top of the `origin/main` merge. A **delta review of the repair head `6facd56`**
returned approve-with-minors: six wording and count corrections plus one new hosted case, applied in
the final commit and changing no emitted byte of a real-model run. The load-bearing finding was the run-scope balance
assertion (`docs/specs/r6-resident-weights.md` section 11.1 correction 12): it read
`created != 1 || freed != 1`, so a resident run that failed **before** the wrap existed reported
`graph_balance_failures: 1` and `released_before_owner_scope_end: false` on a teardown that was in
fact perfect. It now asserts balance, with "exactly one" kept for successful runs, and
`ds-force-resident-wrap` — the early-exit case the first implementation retired as unnecessary — is
its regression.

**Verification checkpoint (final-minors head).** `gmake build`, `gmake format-check`,
`git diff --check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` (all six blocks; **117** documented decode-step cases, 116 of them with
a golden row, reaching 41 codes)
all pass at the final head; `gmake check` (31 units), `gmake fmt`, and `gmake gate-topology-check`
passed at the repair head `6facd56`, whose Align sources and `Makefile` the final commit does not
touch. `gmake decode-step-qualification` **exits 0** on the real model at `N = 16` in 827 s of the
1800 s cap at `6facd56`, with the scaling row interleaved for the first time; oracle R PASS, arena
reproduced independently from `pack.json`, floor MET at 412,763 ppm. It is **not** re-run for the
final minors: they touch documentation, one hosted case, and one source comment, and change no
emitted byte of a real-model run. Instruments unchanged:
`ALIGN_LLM_LLAMA_DEBUG=/opt/homebrew/bin/llama-debug` (Homebrew build 10566, commit `bb4caa754`) and
the R2c-patched `llama-eval-callback` from the `r2c-v2` cache.

**Six mutants injected, five killed under `gmake layer-forward-smoke`.** The arena refilled per decode step;
a layer filled at the wrong arena base; the run-scope wrap never freed; the wrap created **and**
freed twice (which is what the repaired condition's `created > 1` clause carries); and the
pre-repair balance condition restored, which `ds-force-resident-wrap` kills by name. A sixth —
`stage_embed_row`'s bound restored to the whole arena — is **not** killed by anything in the corpus,
and that is recorded in section 5.10 rather than papered over: the repair is defence in depth
against a future caller, not a fix for a reachable defect. That mutant loosens the bound; its
**tightening** direction is now covered by `ds-resident-stage-full`, the final review's case, which
runs a resident prefill of exactly `MAX_PREFILL_TOKENS` distinct ids — the highest slot either call
site can produce — against its streamed twin under oracle R.

**Merged** as PR #147; `origin/main` `553563e` is that merge and is the base of the branch above.

**Process correction this capability owes the next one.** Sections 1 to 4 of
`docs/specs/r6-resident-weights.md` were written before implementation, but the file's first commit
is the implementation commit, so the repository holds **no evidence** of that ordering and a reviewer
is right to say so. **The next Track B performance capability commits its sections 1 to 4 — ledger,
baseline, cost ceiling, and floor — before the first line of implementation**, so the ordering is a
fact about the repository rather than a claim in a document.

**Intentional uncommitted files.** None. The RW-P1 probe (`src/r6w_probe.align` and its binary) is a
throwaway that lives outside the work tree and is not committed; section 5.8 records its whole
output.

## Merged checkpoint: R6-KV-PERSIST (PR #146, 2026-08-29)

Branch `agent/r6-kv-persist`, stacked on `agent/r6-step-n`, which is merged into it at `6ca1eef`
(the STEP-N review repair) by `git merge` — **never a rebase**, so both stacked branches' recorded
commits stay reachable. **Three commits and nothing uncommitted:** `9699848` is the capability,
`1971c61` is the consolidated repair of the first comprehensive review's findings, and the head is
the merge of `origin/main` at `3df063b` — R6-STEP-N, PR #145, which itself carries
R6-DECODE-KV-STEP1 (PR #144) and R5E — again taken as `git merge origin/main` and never a rebase.
Both stacked prerequisites have now landed, so the reconciliation they were waiting on is **done**:
roadmap numbering is unchanged (27 / 28 / **29**), `docs/align-requests.md` now runs 1–49 on this
branch so the next free number is **50** and this capability still claims none, and `Makefile` and
`.gitattributes` moved on `main` rather than here.

**Capability.** The R6 KV plane persisted to disk and reloaded in a **fresh process**, dense
Qwen2.5-Coder-7B Q4_K_M, CPU. `docs/specs/r6-kv-persist.md` is the authoritative ledger. **All
four** of the design gate's triggers fire — a changed public CLI arm, a **new persisted format**
plus a document schema bump, a **process ownership boundary**, and a coordinated invariant across
three or more modules: the plane's layout stops being private to `src/decode_step.align` and becomes
a published contract with an independent second reader.

**Complete.** `src/kv_plane.align` (new module: the `akvp` v1 constants, the 192-byte header, the
192-byte identity record, non-wrapping region arithmetic, five `crypto.sha256` digests, and the
writer; no `unsafe`, no `extern`); `--decode-step` arity 12 and 13 with `KV_SAVE`/`KV_LOAD` and the
`-` convention; `R6_KV_ARGS` at step 2b, `R6_KV_TOO_LARGE` at 6a, `R6_KV_EXISTS` at 6b, the pack
identity read and its degenerate-digest refusal at step 7/7b, the save path W1–W4 after step 10, and
the load path L1–L14 replacing steps 9–10; the chunked refill through `model_forward.window_put`;
document schema 3 with `plane.source`, the `kv` object, and `timings.first_token_ns`;
`scripts/kv_plane_reader.py` (a second implementation written from the specification, driven as a
subprocess, 13 reject kinds); `scripts/layer_forward_fixture.py`'s `kv_container` (a **third**
implementation) plus 39 mutants, an honest short-prompt container, a zero-identity pack, and a
non-degenerate pack source-identity record; the fifth smoke block's 55 new cases;
`scripts/run-decode-step`'s save → separate-process load → compare leg with the determinism, `du`,
and TTFT-proxy legs; roadmap item 29, `docs/align-development.md`, and client lines under Align
Requests 21, 29, 30, 31, 38, 39, and 49 including **one correction to Request 31's own forward
text**.

**The review repair added four rules to the format, and they are contract additions rather than bug
fixes** (spec section 11.4): the **canonical region layout** is now enforced by the arm as well as
the reader (`R6_KV_REGION("layout")`); **inter-region padding must be zero** in the arm too
(`R6_KV_RESERVED("padding")`, and no digest covers the gaps); `MAX_KV_PLANE_BYTES` and
`MAX_KV_LOGITS_BYTES` are re-checked **on load** ahead of the length comparison (`R6_KV_TOO_LARGE`);
and a **thirty-two-zero-byte pack identity** is refused rather than compared
(`R6_KV_IDENTITY("pack_absent")`). Spec section 5.2.1 is the rule-by-rule arm-to-reader parity
table: three asymmetries survive and all three are stated — `ZEROTAIL` by design, `pack_absent`
because its subject is the pack, and two places where the two implementations refuse the same file
and only the name differs.

**The `Makefile` is byte-untouched** — no target, no `.PHONY` word, no build-list entry;
`src/kv_plane.align` enters through `src/decode_step.align`'s import graph — so aggregate
membership and check topology are unchanged by construction. `src/ggml_ffi.align`,
`scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`, `scripts/build-ggml-shim`, and
`src/ggml_spike.align` are **byte-unchanged**: the refill's only crossing is
`align_ggml_window_copy`, which shipped with R5B, and every new refusal is reachable from a
malformed file rather than from a forced compute failure, so this capability needs **no new forced
shim build**.

**Goldens.** `scripts/decode-step-golden.jsonl` moves — every row to schema 3, plus 55 new rows, 52
becoming 107. `scripts/layer-forward-golden.jsonl`, `scripts/model-forward-golden.jsonl`,
`scripts/gpu-forward-golden.jsonl`, `scripts/moe-layer-forward-golden.jsonl`, and
`scripts/ggml-spike-golden.jsonl` are **byte-unchanged**, verified by regenerating all five and
observing no diff — which is the check that the new `Outcome` fields and the fixture's new pack
source record moved no other arm's document.

**Oracle Q's exclusion list is sixteen groups, eight more than the design drafted, and the reason is
recorded.** The design named `kv`, `plane.source`, `plane.readback_ns`, `plane.upload_ns`, `graph`,
`schedule`, `timings`, and `lifetime`. An empirical diff of a save-run document against a load-run
document found eight more keys that differ: `pack.reader_pread_count`, `pack.reader_bytes_read`,
`head.node_count`, `head.pread_ns`, `head.compute_ns`, `window.reuse_count`,
`window.member_placements`, and the `reference` block. Seven are counts of work the load path did
not do; the eighth is a **verdict** — `reference.verdict`, whose byte comparison against the source
GGUF lives in the prefill pass, so a load run performs none of it and now publishes `"-"` rather
than claiming `IDENTICAL` over zero comparisons. That is a public field's behaviour changing, not
only a test exclusion, and the qualification asserts it positively on the save run. What stays
**inside** the comparison is unchanged and is the point: `decode` in full, every `steps[]` object,
`plane.roundtrip_*`, `output`, `oracle_logits`, `oracle_decode`, `model`, `selection`, and `abi`.

**Six mutants were injected and all six die under `gmake layer-forward-smoke`**: a wrong pack
identity accepted, the plane digest skipped, the plane read offset off by four, the logits region
not persisted, a truncated file accepted, and the independent reader accepting a flipped reserved
byte. The last is the one that matters most — it fails in the reader, on a file the arm refuses
correctly.

**Verification checkpoint** (repair head). `gmake build`, `gmake check` (31 units), `gmake fmt`,
`gmake format-check`, `git diff --check`, `gmake gate-topology-check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` (all five blocks; **107** documented decode-step cases reaching 40
codes; the akvp block's 51 refusal rows over 13 reject kinds) pass.

`gmake decode-step-qualification` **exits 0** on the real model at `N = 16`, 10 min 41 s (641 s) of
the 1800 s cap. It ran **twice** — once at the implementation head and once at the repair head,
which adds four refusals to the load path — and every correctness value reproduced exactly: the same
64 ids, the same four container digests, the same byte counts and verdicts, only the timings moving.
Instruments: `ALIGN_LLM_LLAMA_DEBUG=/opt/homebrew/bin/llama-debug`, the **pinned Homebrew build**
`version: 0.2.0 (build 10566, commit bb4caa754)`, and the R2c-patched `llama-eval-callback` from the
`r2c-v2` cache.

**Every rule this capability owns passes on all four prompts**: oracle Q `IDENTICAL`, gate G `PASS`
on the load path, oracle B `IDENTICAL` over 26,607,616 B (`T = 6`) and 21,102,592 B (`T = 3`) on the
load path, oracle C′ byte-identical at `k ∈ {1, 8, 16}` on the load path, containers of exactly
29,970,432 B that `du` confirms are dense, and three writes per prompt — one under a perturbed
environment — producing one digest. **`oracle_logits.verdict` is `IDENTICAL` and `byte_identical` on
all four prompts on both paths**, so gate G1 holds unconditionally.

The only `FAIL` in the run is oracle A′ on prompt 1 at step 1, `2391/1e-4` on `ffn_inp-27` — the
exact value R6-STEP-N recorded, admitted under R6's rule because oracle C′ at `k = 1` is
byte-identical, so the divergence is llama.cpp's decode-versus-prefill kernel selection and not this
arm's arithmetic. Nothing about it is this capability's. `docs/specs/r6-kv-persist.md` section 5.6
records every number; the earlier "this host has no `llama-debug`" narrative and its section 5.6.1
are **deleted**, because they were wrong: the `r2c-v2` cache holds only `llama-eval-callback`, and
that is not evidence about `llama-debug`.

`gmake baseline-check` is `N/A` — no `Makefile` line and no build input moved — and
must be re-checked at the publication head, because R5E moved `Makefile` and the baseline artifacts.

**Merged.** PR #146, `origin/main` at `a6e545b`, carrying the final review minors `5c53ea1`. The
comprehensive review's finding that the repair's four added refusals were contract additions rather
than bug fixes is recorded in `docs/specs/r6-kv-persist.md` section 11.4. Nothing here is open.

**Reproducing the qualification on this host.** Both instruments exist and neither is built here.
`ALIGN_LLM_LLAMA_DEBUG` **must** be the pinned Homebrew `llama-debug`, `version: 0.2.0 (build 10566,
commit bb4caa754)` at `/opt/homebrew/bin/llama-debug` — never a local source build, because
`oracle_logits` is a byte comparison and a source build has been measured to disagree with the
pinned build. `ALIGN_LLM_LLAMA_EVAL_CALLBACK` is the R2c-patched instrument under
`~/.cache/align-llm/llama.cpp/r2c-v2/<revision>-<digest>/build/bin/llama-eval-callback`; **that
cache holds `llama-eval-callback` and nothing else**, so its lack of a `llama-debug` says nothing
about the host. `docs/align-development.md`'s `--decode-step` section states both as rules.

**Blockers.** None. R6-STEP-N's publication is a sequencing dependency, not a blocker.

**Constraints.** **No new Align request is proposed** and number **50** stays free — re-check after
`git merge origin/main`, because this branch's register still lacks 47 and 48. Requests 21, 29, 30,
31, 38, 39, and 49 each gain a cited client and **none changes status**. **No durability claim and
no TTFT claim**: `timings.first_token_ns` and the runner's invocation wall clock are labelled
diagnostics and no acceptance decision is taken from either. The R6 roadmap gate stays **unmet**.

## Merged checkpoint: R6-STEP-N (2026-08-29)

Merged as `3df063b` (PR #145). The record below is the branch's own.

Branch `agent/r6-step-n`, in publication. **Three commits and nothing uncommitted:** `a9c6161` is
the capability, `6ca1eef` is the consolidated repair of the two disjoint comprehensive reviews'
findings, and the head is the merge of `origin/main` at `d9a91e4` — R6-DECODE-KV-STEP1, PR #144 —
taken as `git merge origin/main` and never a rebase, so every recorded commit stays reachable.

**Capability.** An N-step greedy decode loop over the R6 KV plane, dense Qwen2.5-Coder-7B Q4_K_M,
CPU, gated on **token ids**. `docs/specs/r6-step-n.md` is the authoritative ledger. The design gate
is triggered on two of its four triggers — a changed public CLI arm and a changed exchanged document
schema — and the third, a coordinated invariant across three or more modules, is recorded as **not
fired** with its reason: the invariant is R6's and is unchanged, only its consumers move.

**Complete.** The `STEPS` operand and its two refusals (`R6_STEPS`, and `R6_KV_WIDTH` for
`T + N > KV_WIDTH`, with the precedence between them asserted); `LOGITS` accepting `-`; the
write-back of each step's own K and V column into the plane, before verification, with oracle B's
bound widened from `n_past` to `n_past + 1`; per-step iteration of the node table, the offset mask,
and the position image; `MAX_PREFILL_TOKENS` 8 -> 32 with `R5_ORACLE_TRUNCATED` byte-unchanged;
schema 2 with `steps[]`, `decode.token_ids`, and `plane.first_mismatch_step`; the fixture's
three-step reference loop and four-graph transcript; thirteen new smoke cases including two new
forced builds; `scripts/run-decode-step` extended with gate G and oracle C' at three checkpoints;
`scripts/decode_step_fingerprint.py`; roadmap item 28, `docs/align-development.md`, and one
recorded client line under Align Request 22.

**The `Makefile` is byte-untouched** — no target, no `.PHONY` word — so aggregate membership and
check topology are unchanged by construction. `src/ggml_ffi.align`, `scripts/ggml_shim.c`, and
`src/ggml_spike.align` are **byte-unchanged** too: the loop needs no new ggml op, FFI symbol, node
row, or slot.

**Gate G's load-bearing measurement, taken before the gate was claimed.** The transcript does not
print the sampled token and `result_output`'s argmax is not derivable from six of 152,064 printed
values, so the ids are gated through each decode graph's
`embd = GET_ROWS(token_embd.weight, [d_k])`. Over all 152,064 rows of the qualification model's
`token_embd.weight` (Q4_K) there are **149,710 distinct printed fingerprints and exactly one
collision class**, and that class is **precisely the 2,355 all-zero rows** — the unused vocabulary
slots. Every row with any non-zero element is unique. The gate therefore holds unconditionally on
the used vocabulary, and the runner refuses per step if a decoded id is ever a member of the
colliding class. Section 3.2's fallback G3 — a patch bump to log the sampled id — is **not taken**.

**Verification checkpoint, at the repair head.** `gmake build`, `gmake check`, `gmake fmt`,
`gmake format-check`, `git diff --check`, `gmake gate-topology-check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` (all five blocks; 52 documented decode-step cases reaching 24 codes;
34.0 s whole owner, 6.9 s decode block) pass.

`gmake decode-step-qualification` passed on the real model at the capability head, at `N = 16` in
**8 min 27 s** of the 1800 s cap, so the documented fallback to `N = 8` is not taken; ledger section
5.1 records every number. It was run **twice** there, and every correctness value reproduced exactly
— the same 64 ids, gate verdicts, byte counts, and per-step maxima; only the timings moved. Headline
results: gate G `PASS` on all four prompts over sixteen ids each; oracle B `IDENTICAL` over
26,607,616 B (`T = 6`) and 21,102,592 B (`T = 3`); oracle C' byte-identical at `k ∈ {1, 8, 16}` on
all four; oracle A' `PASS` at `max_abs_diff` **0** at every one of sixteen steps on three prompts,
and `FAIL` on the `T = 6` prompt at 2391/1e-4 at step 1, admitted under R6's rule.

**It was not re-run at the repair head, and the reason is that nothing it reads moved.** The repair
changes the hosted fixture's synthetic weights, the fifth smoke block's own assertions, the
error-document accounting rule (which only a document with `status: error` can show, and the
qualification asserts `ok` on every run), three comment literals, and the *ordering* of one
`numpy` preflight in `scripts/run-decode-step`, which on a host that has `numpy` changes nothing at
all. Success-path arithmetic, the goldens the qualification does not read, and every asserted value
in section 5.1 are untouched.

**Eight mutants were injected into `src/decode_step.align` at the repair head and all eight die
under `gmake layer-forward-smoke`** (ledger section 5.2): a write-back column off by one and a
skipped write-back, both as `R6_PLANE_MISMATCH step[1]layer[0]tensor[k]col[3]`; a frozen `n_past` on
the plane's column count and every per-step oracle; a transcript-graph skip off by one on
`R6_ORACLE_MISSING step[3]`; **`token = first_token`, the mutant the first review found the owner
could not see**, now dying on `decoded [24, 24, 24], not the reference loop's [24, 9, 27]`; an
unsliced position image and an unsliced offset mask, both on per-step oracle A'; and oracle B's
bound narrowed back to `n_past`, which drops the column its own step wrote. Two more are not
hosted-reachable and are unchanged: gate G compared against graph `k` or `k+2` disagrees at step 1
on every prompt, and oracle C' with its step index off by one differs at every checkpoint.

**`scripts/build-ggml-shim` gains two forced-build arms** — `engine+compute-step2` and
`engine+writeback-offset` — which are inputs to the **stub** shim only and never to an ordinary
build. That is the one build-adjacent file this capability touches; the `Makefile` itself is
byte-unchanged, so `gmake baseline-check` needs no re-record. Re-checked at the merge head after
R5E and R6 both moved `Makefile` and the baseline artifacts: none of the baseline's twenty tracked
artifacts is in this capability's publication diff, and the source → oracle → finalization chain
`e61993d` → `3cde6e2` → `cb8d2ce` stays reachable from the merge commit.

**Numbering, reconciled 2026-08-29.** R5E merged as PR #143 (`main` `5ccc2aa`), so roadmap item 26
is R5E and Align Requests **47 and 48 are real on `main`**. R6-DECODE-KV-STEP1 keeps roadmap item
**27** and Request 49, so this capability is roadmap item **28** and the next free Request number is
**50** — which stays free, because this capability proposes none. R5E also moved `Makefile`,
`.gitattributes`, the baseline artifacts, and `docs/align-development.md`; none is a
`MAX_PREFILL_TOKENS` consumer and none conflicts with this diff, but all are re-checked at the
merge.

**The merge, taken and reconciled.** Two conflicts, both resolved by keeping **both** sides:
`docs/align-development.md` (R5E's "MoE whole-model prefill development" section above this
capability's renamed `--decode-step` heading) and `scripts/run-layer-forward-smoke` (R5E's fifth
block above this capability's renamed sixth-block banner). Roadmap item **28** and Align Request
numbering (**49** real, **50** free) are confirmed unchanged by the merge. R6's own final repair
`5445c14` had recorded the prefill cap as **8** in `docs/specs/r5a-dense-layer-forward.md` and
`docs/specs/r5b-model-prefill-forward.md`; the merge commit moves both to **32** — `TOKENS` 1 to 32,
the range `7 .. 32` open for arithmetic and closed for comparison — with `R5_ORACLE_TRUNCATED`
byte-unchanged, and brings the two source comments that narrate the lift
(`src/layer_forward.align`, `src/model_forward.align`) and `docs/align-development.md`'s
`R5_ORACLE_TRUNCATED` paragraph with them. Ledger sections 8 and 9 record it. **No golden moved:**
all six golden files were byte-identical to what the merged runner produces, so the documented
`ALIGN_LLM_LAYER_FORWARD_GOLDEN_UPDATE=1` regeneration was not needed.

**Verification at the merge head.** `gmake build`, `gmake layer-forward-smoke` (all six blocks,
2 min 32 s), `gmake ggml-spike-smoke`, `gmake format-check`, and `git diff --check` pass.
`gmake decode-step-qualification` was run a **third** time on the real model, at the merge head, and
**every correctness value in ledger section 5.1 reproduced exactly** — the same fingerprint
partition (149,710 / 1 class / 2,355 ids / 0 non-zero), the same 64 ids, gate G `PASS` × 4, oracle B
`IDENTICAL` over 26,607,616 B and 21,102,592 B, oracle C′ byte-identical at `k ∈ {1, 8, 16}` × 4,
and oracle A′ identical to the last digit including the `T = 6` prompt's admitted 2391/5878/1295.
Only the timings moved, downward. Section 5.1 records the third run.

**Next actions, in order.**
1. `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` at the
   pushed head. The publication diff touches `src/`, goldens, fixtures, and runners, so the
   classifier selects the executable row and the **hosted** profile: none of its twenty-four
   `FRESH_IMAGE_PATTERNS` is in the diff, `Makefile` and `.gitattributes` are byte-untouched
   relative to `origin/main`, and none of the baseline's twenty tracked artifacts (`src/main.align`
   and `Makefile` among them) moved, so `gmake baseline-check` passes without re-recording the
   chain. The stamp belongs to the exact unchanged head; re-merge and re-stamp if `main` moves.
2. The English pull request, with the review envelope and the exact commands and results.
3. **No further review.** Two disjoint comprehensive reviews read `a9c6161` against base `1671810`
   and their nine findings are all accepted and consolidated into `6ca1eef`; the repair did not
   expand scope, change approach, or change behavior, design, specification, or governance, so the
   final-review rule is not triggered. The merge is a base change and carries **fresh integration
   evidence** rather than a fresh review: it materially changes no reviewed risk — it adds R5E's
   already-reviewed sections beside this capability's, and moves two prose caps in the direction the
   reviewed ledger section 2.5 already specifies.

**Blockers.** None. R6 publication is a sequencing dependency, not a blocker.

**Constraints.** No new Align request is proposed and number **50** stays free. Request 22
(indexing arrays of Move element types) stays `PROPOSED` and **non-blocking**, and gains one
recorded line in `docs/align-requests.md`: it is now avoided in a **fourth** place, and the first
outside a container reader — `model_forward.StepColumns` carries its three string columns as the
stream-plus-column shape rather than `array<str>`. The tokenizer contact is unchanged: the gate is
on ids, not text, and the one place text would help — the external `llama-debug` corroboration leg —
stays hand-measured exactly as R6 left it. Requests 41 and 49 each gain a cited client and no
workaround is built for either. No hypothetical surface is consumed anywhere.

## Merged checkpoint: R6-DECODE-KV-STEP1 (2026-08-29)

Merged as `d9a91e4` (PR #144). The record below is the branch's own.

Branch `agent/r6-decode-kv-step1`, started from `main` at `c21b9e4` and **merged** twice rather than
rebased, so its recorded commits stay reachable: with `main` `76246f3` (R3-DECODE-RESIDENCY, PR #142)
and then with `main` `5ccc2aa` (R5E-MOE-MODEL-PREFILL, PR #143). Nothing uncommitted. `73557dc` is
the capability, `1671810` is the consolidated review repair, and `5445c14` is the narrow repair of
the final delta review's minors; the rest of the branch is the two merges, the re-recorded baseline
chain, and its record. Reviewers read `73557dc` against base tip `76246f3` with merge base `c21b9e4`;
the final delta review read `1671810`.

**Capability.** One decode step at `n_past = T` over an Align-owned KV plane, dense Qwen2.5-Coder-7B
Q4_K_M, CPU. `docs/specs/r6-decode-kv-step1.md` is the authoritative ledger. The design gate is
triggered — new public CLI surface, new exchanged format, coordinated invariant across six modules —
and the design was complete before implementation began.

**Complete and committed.** `align_ggml_op_concat` across the six FFI surfaces; `WHEN_DECODE`,
`OP_CONCAT`, the two plane slots (64/65), `mf_write_mask_offset`, the thirty-eight-row decode layer
table and its oracle map in `src/layer_qwen2.align`; the id/position split in
`src/model_forward.align`; the multi-graph transcript scan in `src/layer_forward.align`;
`src/decode_step.align` and its `--decode-step` arm; the fixture's decode reference and two-graph
transcript; the fifth `layer-forward-smoke` block and `scripts/decode-step-golden.jsonl`;
`scripts/run-decode-step` and the `decode-step-qualification` target; roadmap item 27,
`docs/align-development.md`, and Align Request 49. The real-model qualification is recorded in
ledger section 5.1.

**Review and repair.** One comprehensive review of `73557dc` over two independent reviewers on
disjoint risks. Reviewer B (spec/docs/governance) requested changes: 1 blocker, 4 major, 8 minor.
Reviewer A (Align/C/FFI) approved with 1 major and 6 minor. All 20 findings have a disposition and
are repaired in `1671810`, except the blocker, which is a **publication step** rather than a code
change and is next action 1 below. One final delta review of that repair approved it with three
minors — the R5A/R5B ledgers still described `MAX_PREFILL_TOKENS` as 6 and carried no
`R5_ORACLE_TRUNCATED` row; `verify_plane`'s size-disagreement early return named `k` even when only
the V concat row disagreed; and neither of that function's size guards has a shipped case — and
`5445c14` repairs all three. The repair narrows records and one diagnostic rather than expanding
scope, so no further full review is required.

The repair changes behaviour in two places and both are recorded in the ledger:

1. **A new refusal, `R5_ORACLE_TRUNCATED`** (ledger 2.7). Section 2.7 lifted `MAX_PREFILL_TOKENS`
   from 6 to 8 and documented at the constant that the cap was the oracle's. Documenting it was not
   a mitigation: `printed_count` clamps to six on both sides, so `--layer-forward`/`--model-forward`
   would have accepted `T` of 7 or 8 **with a transcript** and reported `PASS` over six of seven
   rows. Both arms now refuse that combination at their token stage. Without a transcript the same
   token count is admitted, which is what `--decode-step`'s own characterization pass needs.
2. **`graph.slot_high_water` is a maximum again.** `src/decode_step.align`'s copy of
   `model_forward.account` had dropped the `slot_high_water` line, so a run failing inside the
   prefill published 0.

Everything else is consistency: the shipped acceptance rule is now stated **once**, in ledger
section 2.11 (A, B, and C are all acceptance; an oracle A `FAIL` is admitted only inside the 0.5
bound **and** with oracle C byte-identical), with sections 3.3/3.4/5.1/10.2, the runner, the
roadmap, and `docs/align-development.md` pointing at it rather than paraphrasing it.

**Three mutants became shipped cases.** `ds-force-plane-stage-offset` (`R6_PLANE_MISMATCH`, which
was previously reachable only by mutating the source and was absent from `REQUIRED_CODES`),
`ds-force-decode-position`, and `ds-force-mask-offset`. Each is keyed on a slot only the decode
graph writes.

**Verification checkpoint (repair head).** `gmake build`, `gmake check`, `gmake fmt`,
`gmake format-check`, `git diff --check`, `gmake gate-topology-check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` — all five blocks, 40 documented decode-step cases reaching 23 codes —
pass. The four reviewer mutants and the new plane mutant were re-injected at the repair head and all
five still die with their distinct diagnoses: `R5_SHAPE node[24]` / `node[22]`, oracle A `FAIL` at
8092 on `q_rope` / 514 on `kqv`, and `R6_PLANE_MISMATCH layer[0]tensor[k]col[0]`.

**`gmake decode-step-qualification` was re-run on the real model at the repair head and again at the
publication head; both passed.** Every recorded value in ledger 5.1 reproduced on each: decoded
tokens 671/715/2691/526, oracle A `FAIL` at 2391 on `ffn_inp-27` for the first prompt and `PASS` at
0 for the other three over 5,058 elements each, oracle B `IDENTICAL` over 688,128 and 344,064 bytes,
oracle C byte-identical on all four with the argmax pairs 26312/262/1159/11844, `plane.bytes`
29,360,128, nodes 958/1014. Only the timings moved. Ledger 5.1 records all four runs. The
publication-head run took 3 m 48 s wall and was taken concurrently with an unrelated aggregate on
this host; no structural quantity moved.

**Goldens that moved, and why.** Ledger section 5.3 is exact. `gpu-forward-golden.jsonl` and
`moe-layer-forward-golden.jsonl` are byte-unchanged. `layer-forward-golden.jsonl` and
`model-forward-golden.jsonl` each rename one row for the token-cap lift and **add two**
(`*-tokens-seven-transcript` refused, `*-tokens-eight-no-transcript` admitted); no existing row's
bytes change. `decode-step-golden.jsonl` adds the three forced-build rows and changes seven existing
rows in one field, `graph.slot_high_water`, which is repair (2) above.

**Coding-baseline chain, re-recorded — reviewer B's blocker, discharged.** The capability changes
`Makefile`, one of the twenty recorded baseline artifacts, so the chain on `main` does not bind this
head. (`scripts/build-ggml-shim` also changes but is **not** a recorded artifact and does not itself
invalidate the chain; an earlier draft of this record said it did.) The identity-bound chain is
`e61993d` → `3cde6e2` → `cb8d2ce` — clean source, immutable oracle projection, finalization — with
the pending measurement recorded on Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) through
the DinD wrapper, exactly as R5D's and R5E's were. Exactly one of the twenty artifact digests moved
(`Makefile`); `.align-revision` is unchanged at `3a34febe` and the twenty paths are identical.
`gmake baseline-check` passes on Linux at the finalized head. This chain **supersedes** the one this
branch first recorded against `main` `76246f3` (`e4548b1` → `6d1c152` → `1bbacaa`), which PR #143
invalidated by changing recorded artifacts of its own; both chains stay in this branch's history and
only the later one is named in the finalized baseline.

**Next actions, in order.**
1. `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke`, on the
   unchanged head. The diff touches `Makefile`, `scripts/build-ggml-shim`, and the goldens, so the
   classifier selects the executable row and the installed fresh-image profile; do not substitute a
   Docker skip or an ambient `DOCKER_HOST`.
2. Open the English pull request with the verification table, the review envelope, and the finding
   dispositions. It must be a **merge** commit: squash and rebase would make the three baseline
   commits unreachable from `main`.
3. The next capability is step 2 and the decode loop, which needs a write-back at column `n_past` —
   the one thing that makes the plane both a read and a write target in one graph.

**Deviations from the ledger, recorded rather than hidden.** Ledger section 10 is authoritative and
now carries all of them: the decode layer is **thirty-eight** rows and not thirty-six (10.1); oracle
C is computed by the runner rather than by the arm, though it is acceptance (10.2); there is
deliberately no `R6_ORACLE_SHAPE` and the seam's `R5_ORACLE_SHAPE` reaches the document unchanged
(10.3); the golden rows that moved and why (10.4); the deferred closure cells, now including the
external oracle-C chain the review recommended and why it is deferred (10.5); and the nine
re-implemented functions, **each diffed against its original with every divergence named**,
plus the 1,328-byte `model_forward.Outcome` this created (10.6).

**Open decision for the user, unchanged from the design.** Whether to extend the R2c patch to
`examples/debug/debug.cpp` so a decode step gets a byte-exact external logits reference. It would
close ledger risk 3 at the cost of a new patch digest, a cache-generation bump to `r2c-v3`, and
re-running the R2c qualification. R6 ships without it. It is also the honest route to making the
review's "drive the C chain externally" recommendation possible: the operand `llama-debug` needs is
a prompt **string** and the runner holds token ids, so an external chain today would have to guess
the decoded token's text.

**Numbering, re-checked at the merge with `main` `5ccc2aa`.** Roadmap item **27** and Align Request
**49** are unchanged and are now contiguous rather than reserved: `main` carries roadmap items to
**26** and requests to **48**, because `agent/r3-decode-residency` landed item 25 as PR #142 and
`agent/r5e-moe-model-prefill` landed item 26 and Requests 47 and 48 as PR #143. The numbering hazard
ledger section 8 recorded is therefore closed — the numbers this branch chose against unmerged
claims are the numbers that are free.

## Merged checkpoint: R5E-MOE-MODEL-PREFILL (2026-08-28)

PR #143 merged as `5ccc2aa` on `main`. The publication and merge named in the next actions below
are complete; the rest of this record is unchanged.


Branch `agent/r5e-moe-model-prefill`, based on the merged MOE-PREREQ-DISCHARGE (PR #133, `35a0df6`)
and then **merged** with `main` `e312bd7` — the merged R5D at PR #139, which itself carries PR #134's
pin move, PR #135 (R3-RESIDENCY-SIM), PR #136, PR #138, and PR #140 (R2C-DECODE-INSTRUMENT) — rather
than rebased over it, so this branch's recorded baseline-chain commits stay reachable. The branch is
`5e3356d` (design ledger), `053de09` (implementation), `e7f727f` (review repair), the merge commit,
and the reconciliation and baseline commits on top. Design ledger
`docs/specs/r5e-moe-model-prefill.md` is authoritative and carries the implementation's corrections
C1–C25 and the cell-to-case map. **The capability is implemented, reviewed, verified, and committed**;
`src/moe_model_forward.align`, `scripts/run-moe-model-forward`,
`scripts/sweep-moe-model-forward-excerpt.py`, `scripts/moe-model-forward-golden.jsonl`, and
`eval/fixtures/olmoe-model-6tok.txt` are new, and `src/layer_olmoe.align`, `src/ggml_spike.align`,
`scripts/layer_forward_fixture.py`, `scripts/run-layer-forward-smoke`, `scripts/build-ggml-shim`,
and `scripts/ggml_shim_stub.c` are extended. **No `extern` symbol is added and `scripts/ggml_shim.c`
is unchanged.** No intentional uncommitted files. Merge is the only remaining step.

**What it does.** R5's **third** gate stage — 最小モデル on the routed path, after R4.5/MOE-PREREQ's
単一block and R5D's 単一layer: `ggml-spike --moe-model-forward` computes a
whole sixteen-layer OLMoE prefill of at most six tokens — per-layer routing, only the routed experts'
planes read into **one** Align-owned claim window reserved at the arithmetic union bound and reused
across layers, the narrowing inside layer fifteen where the instrument does, and the output head —
and emits one `R5_MOE_MODEL_FORWARD` (`schema_version: 1`) document with the per-layer union curve.
`KV_WIDTH` is a **mandatory** fifth operand, not R5B's optional trailing one, because on a routed
model the declared attention width changes which experts the router selects and therefore which bytes
the arm reads.

**Measured on the real model** at the adopted pin: the final logits are **byte-identical** to
`llama-debug --save-logits`, `sha256 a56195da2c913d8dd7fa608917a381200c4b59d1c534fae2d4bbb828f80d2383`;
the self-reference oracle is **227 of 227** nodes byte-identical over 34 graphs; the transcript oracle
is `PASS` over **16 of 16 layers, 227 of 227 nodes, 21,372 elements**, max |Δ| 0 ten-thousandths and
max |Δsum| 0 millionths; the routing-identity oracle is `MATCH` at **546 of 546** printed ids over 728
slots and 16 of 16 block sums; and the runtime-width run is `WITHIN`, argmax 2262, reading the same
1,301,446,656 expert bytes. **Residency: 1,301,446,656 of 3,900,702,720 expert bytes = 333,644 ppm
(33.36%)**, 1,029 of 3,072 planes, 343 of 1,024 keys — two thirds of this model's expert weights are
never touched by a prefill. Peak resident weight bytes 280,342,528 against 4,212,193,280 for the
container, **6.66%**; dense window 84,520,960 B; claim window 195,821,568 B reserved at `U_max` 48
with a 101,990,400 B peak use at layer 0; activation peak 4,440,064 B; 34 graphs, 918 ggml nodes.

**The residency *policy* stays deferred, deliberately.** Within one prefill there are 343 demands and
343 distinct `(layer, expert)` keys, so no cache can hit; a policy needs repeated prefills or decode
before a hit rate is a measurement. What this capability hands R6 and any residency work is the shape:
claim `pread` **560.8 ms** against **147.3 ms** of graph compute in this run — the claim read is
**3.8×** compute — so a six-token routed prefill of this model on this CPU is I/O bound even with the
pack in page cache. Both timings are single-run diagnostics inside the spreads ledger correction C16
records (109.9–252.8 ms compute, 519.9–612.0 ms claim `pread`); the exact-integer half carries no
measurement risk.

**Review.** One comprehensive review of the stable candidate, two complementary reviewers over
explicitly disjoint risks at implementation head `053de09`: reviewer A returned **no blocker** with 1
medium and 4 low findings; reviewer B returned **changes requested** with 3 medium, 3 low, and 2 info
findings. **All thirteen were validated and accepted**, none rejected, and all are repaired in the one
consolidated commit `e7f727f`; ledger corrections C17–C22 record the contract changes. The repair
built and measured the two promised window-budget fixtures (a member declaring 2^40 bytes reaches
`R4_PACK_OFFSET`, not `R5_WINDOW_BUDGET` or `R5D_CLAIM_BUDGET`, so both are recorded as fail-closed
guards and `R5_INDEX` as never emitted), fixed the coverage denominator at the 36 declared `R5*` codes
(32 reached plus 5 inherited, asserted in both directions), published `oracle.sums_expected` /
`sums_matched`, added the reference arm's non-aliasing assertion, made `residency.keys_distinct` a
real run-level set cardinality, refused a non-UTF-8 path with `R5E_PATH`, and corrected
`expert_bytes_read_ppm` to 333,644 at all three sites. After the merge with `main` a **final
comprehensive review of the merged candidate** was run because the merge brought in R5D's own review
repair, which this branch had not carried. It returned **approve after repair** with 13 findings — 1
high, 3 medium, 9 low/info — **no defect in shipped behaviour**; all were validated and accepted and
repaired in one consolidated commit, recorded as corrections **C24** and **C25** plus in-place record
fixes. Its envelope and every finding's disposition are on the pull request.

**Align capability requests.** Two new, both `PROPOSED` and non-blocking: **Request 47** (a `Borrow`
argument must be a stable named local or field) and **Request 48** (same-call aliasing between a
`borrow mut` owner and its own `Copy` scalar field, where the nested read-only-borrow spelling of the
same shape compiles). They were drafted as 46 and 47 and renumbered at reconciliation because R3's
pair merged first and took 45 and 46. Both probes were re-measured unchanged at the adopted
`3a34febe`. R5E is also appended as a **third client** of Requests 45 and 46 — the two it could only
anticipate while they lived on `agent/r3-residency-sim`.

**Verification, re-run in full at the merged head against the managed `3a34febe` compiler**, on this
macOS host with `gmake`, the recorded Homebrew
`LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib`, and the
`CARGO` wrapper (`docs/align-development.md`):

```text
gmake check                    ok: checked 31 unit(s) per-unit (153 s)
gmake build                    ok
gmake ggml-spike               ok, stub shim and real shim (37 s)
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases; olmoe 22 blocks /
                               69 members, 16 ExpertBlocks, claim surface PASS
gmake layer-forward-smoke      PASS x3, byte-identical apart from the mktemp path, 41 / 37 / 37 s -
                               R5A/R5B's 8 no-document and 75 documented cases, 59 model-forward,
                               28 gpu-forward, R5D's 8 / 78 with 29 codes, and R5E's 14 no-document
                               (R5E_ARITY, R5E_PATH) and 96 documented cases, 32 of the 36 declared
                               R5* codes plus 5 inherited R4/R2 codes, all four oracles, the routing
                               identity element-wise complete over a whole model, and
                               arm-r5a/r5b/r5d-unchanged
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,303 assertions
gmake residency-sim-smoke      PASS - PR #135's owner, unchanged by this branch
gmake expert-trace-smoke       PASS - PR #140's parser owner, unchanged by this branch
gmake gate-topology-check      PASS
gmake format-check             PASS; gmake fmt leaves no diff; git diff --check clean
```

The focused qualification — opt-in, capable-only, in **no** aggregate — on the host that holds the
model, at the adopted pin:

```text
gmake moe-model-forward-qualification   every section 5.2 assertion PASS

the two instruments agree (result_output sum -111030.031250, tokens 1545,823,9,66,13,270)
self-reference IDENTICAL (227/227 nodes byte-identical over 34 graphs)
routing identity MATCH, 546/546 printed ids over 728 slots, 16/16 block sums
transcript PASS, 16/16 layers, 227/227 nodes, 21372 elements, max |d| 0, max |dsum| 0
logits IDENTICAL at the reconciliation width, sha256 a56195da2c913d8dd...
logits WITHIN at the runtime width, argmax 2262, top-ten set 10/10
residency 1301446656/3900702720 expert bytes = 333644 ppm (33.36%), 1029/3072 planes, 343/1024 keys
peak resident weight bytes 280342528 against 4212193280 - 6.66%
34 graphs, 918 ggml nodes, activation peak 4440064 B, slot high water 80/128
microbenchmark B = 147.318 ms; dense pread 126.5 ms, claim pread 560.8 ms
```

**No golden byte changed at the new pin**, and every exact-integer quantity in ledger section 7 is
identical to the pre-pin run, so the adoption needs no behavioural correction row; ledger correction
C23 records the pin move, the request renumbering, and the appended client evidence.

**Baseline chain, re-recorded.** This branch changes `Makefile` and `.gitattributes`, both among the
twenty recorded canonical baseline artifacts, so the chain that shipped with R5D no longer binds this
head. See the pull request for the re-recorded identity-bound chain (clean source -> immutable oracle
-> finalization), measured on Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) with `make
baseline-check` there ending `baseline chain: PASS`. **This pull request must merge with a merge
commit**; squash and rebase merges would make the recorded commits unreachable.

**Next action.** Merge the pull request. `main` moved three times during publication — PR #139
(R5D), PR #141 (R2D-DECODE-LOCALITY-GATE) and PR #142 (R3-DECODE-RESIDENCY), the last two from a
parallel session — and this branch **merges** all three rather than rebasing over them. R2D took
roadmap item **24** and R3-DECODE-RESIDENCY item **25**, so R5E is item **26**. `make ci` is **not** selected: `HOSTED_CHECK_TARGETS`
membership is unchanged because R5E's owner is `layer-forward-smoke`'s fifth block, already a member,
and the one new Makefile target, `moe-model-forward-qualification`, joins no aggregate. The `Makefile`
edit is still an executable-contract boundary, so publication takes the **fresh-image
(Docker-in-Docker)** installed profile, not the documentation lane.

## Merged checkpoint: R3-DECODE-RESIDENCY (2026-08-29)

Branch `agent/r3-decode-residency` merged as PR #142, merge commit `76246f3` on `main`, by a
**parallel session**. It is the residency consumer of R2D's capture and closes the **decode half of
the R3 roadmap gate**; no design gate, no Align source change, no `Makefile` change, no aggregate
membership change, so R5E's baseline chain is unaffected by it.

`scripts/run-decode-residency-gate` replays `main --simulate-residency` four times at section 7.4's
975,175,680 B budget over the same 40-prompt corpus: mixed, decode-only, a prefill-only coverage
control, and a head-4 stream-length control. **The gate is met in the decode direction but the
answer is narrower than the prefill one**: `recent_reuse` beats `lru` by 59 to 238 per mille at
budgets of 15/31/62/125 per mille of the expert footprint, and at 250 and 500 per mille **no
candidate beats the baseline at all** on any decode arm. The prefill-only control at the same
250-per-mille budget is still `BEATS_BASELINE`, and the head-4 control — eleven per cent *fewer*
demands than that winning arm — is not, so what removes the win is the presence of decode demands
rather than coverage, working-set ratio, or stream length. R4B's decode-corpus resume condition is
discharged **negatively**, and R6's KV tiering is ordered ahead of a runtime expert-residency policy.
`docs/specs/r3-residency-sim.md` section 8 is the authoritative record.

**What it means for R5E.** R5E defers any residency policy because a single prefill has 343 demands
and 343 distinct keys. Item 25 is the first measurement of a policy in the decode regime that
deferral names, and it says the policy question is open at realistic budgets rather than settled —
which is the reason R5E ships the per-layer union curve (`schedule[].routed`) as an input to that
work instead of a policy of its own.

## Merged checkpoint: R2D-DECODE-LOCALITY-GATE (2026-08-29)

Branch `agent/r2d-decode-locality-gate` merged as PR #141, merge commit `c21b9e4` on `main`, by a
**parallel session**. It started from `main` `89d8721` (R2c PR #140) and merged `main` `e312bd7`
(R5D PR #139) rather than rebasing over it. It is the first measurement consumer of PR #140's
patched instrument and it closes the **decode half of the R2 roadmap gate**; no design gate was
triggered.

**The gate is met in the decode direction.** On the same 40-prompt corpus against
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` — 40 prefill and 640 decode graphs over 832 token positions
— all three arms are `LOCALITY` against a 125 per mille null: `prefill@8` **371** per mille,
cluster-robust [338, 405]; `decode@8` **447** per mille, cluster-robust [426, 468], 16 of 16 layers
clearing; `boundary` **364** per mille, cluster-robust [325, 405]. Greedy decode's token-repetition
rate is 51 per mille and excluding those pairs leaves the decode arm at 429 per mille, still
`LOCALITY`. `docs/specs/r2a-expert-trace.md` section 9 is the authoritative record; section 8's
prefill gate and its 286 per mille are untouched. It adds no `Makefile` target and changes no
recorded baseline artifact, so R5E's baseline chain is unaffected by it.

**What it means for R5E and for R3.** R5E records claim-level expert residency as a **decode-time**
property and defers any residency policy because a single prefill has 343 demands and 343 distinct
keys. R2D is the first direct measurement of the regime that deferral names: expert reuse between
consecutive decode steps is materially higher than in prefill (447 against 371 per mille). It does
not by itself make a cache-hit claim — that still needs a multi-prefill or decode **replay**, which
`docs/specs/r3-residency-sim.md` owns — but it removes the "decode was never observed" caveat that
R3's own measurement section records.

## Merged checkpoint: R5D-MOE-LAYER-FORWARD (2026-08-28)

Branch `agent/r5d-moe-layer-forward` merged as PR #139, merge commit `e312bd7` on `main`, preserving
its recorded baseline chain `7c4830a` -> `c6cee0c` -> `09de0fd` with a merge commit. Design ledger
`docs/specs/r5d-moe-layer-forward.md` remains authoritative.

**What it delivers.** R5's second gate stage for a **routed** OLMoE layer: one prefill of at most six
tokens through `blk.0`, computed by ggml over attention weights and only the routed experts' planes
held in Align-owned buffers, checked against llama.cpp's own numbers. The routed layer reads
**101,990,400 of 261,095,424** expert bytes (390,625 ppm, 75 of 192 planes, 25 block reads); the
self-reference oracle is 46 of 46 byte-identical; the routing-identity oracle is `MATCH` at 36 of 48
printed ids plus the exact sum 1,471; the transcript oracle is `PASS`, 26 nodes, 2,376 elements, max
|Δ| 0 ten-thousandths. Required microbenchmark B is **5.64 ms**. The residency win is a **decode-time
property**: 39% of the layer's expert bytes at six prefill tokens, 12.5% at one, 73% at eighteen. The
boundary change is five new FFI symbols plus one widened one; no new Align capability request was
needed, and Requests 37, 42, 45, and 46 gained R5D as a non-blocking client.

R5E is built directly on it: `src/layer_olmoe.align` is R5D's topology module, extended with
layer-parameterized tables, and R5E's arm is a fifth `ggml-spike` arm beside R5D's fourth. R5E takes
main's repaired R5D verbatim — R5D's `stage_claim_types` refusal, its stable-insertion-sort stub
`argsort`, its `view_2d` F32 gate, and its `moe-engine-claim-type-mismatch` case are unmodified by
R5E.

## Merged checkpoint: R3-QUALIFICATION-PREREQUISITES (2026-08-28)

Branch `fix/r3-qualification-prerequisites` merged as PR #138, merge commit `1b11245` on `main`,
authored by a **parallel Codex session** rather than by the session that produced R3 and R5D. It
started from `main` `95c47e7`, the merge of R3 PR #135. A second R3 implementation was independently completed before that merge became visible;
its duplicate PR #137 is closed and will not be integrated. Its final review nevertheless exposed
one root-cause class that applies to the merged qualification: the wrapper generated a Model IR but
did not validate it or the requested budget until after every prompt had invoked the external
instrument, so a locally knowable defect could consume up to 40 600-second prompt runs.
Published and merged as PR #138; R5D merges it in rather than rebasing over it, so this branch's
recorded baseline-chain commits stay reachable.

## Merged checkpoint: R2C-DECODE-INSTRUMENT (2026-08-28)

Branch `agent/r2c-decode-instrument` merged as PR #140, merge commit `89d8721` on `main`, authored
by a **parallel Codex session** rather than by the session that produced R3 and R5D. It started from
`main` `1b11245`, the merge of R3 follow-up PR #138.
It **takes** decision (c): the source build of llama.cpp at exact commit
`bb4caa7540188872173c44d161602d9271386413` with the minimal R2c instrument patch is pinned and
shipped, which unblocks R6 and therefore R7-R9. Its first measurement consumer,
**R2D-DECODE-LOCALITY-GATE**, is merged (above). R5 microbenchmark C remains independently blocked
on Align Request 41.

**Merged contents.** The triggered design ledger is `docs/specs/r2c-decode-instrument.md`
(`d8e4818`); the reviewed implementation head is `5f1eb3e`, the first consolidated review repair is
`46432de`, and the final review's three accepted findings are repaired in `76400f5`.
`.llama-revision` and the 2,170-byte patch pin the external source and
two-file diff. The `r2c-v2` managed builder has completed a fresh CPU build with Metal and
llama/ggml shared libraries disabled, verified build 10566 / commit `bb4caa7`, and emitted a
schema-1 attestation. The patch preserves the omitted/nonpositive `-n` one-prefill behavior, emits
up to `-n` one-token decode graphs with common sampling and EOG stop, and prints every
`ffn_moe_topk` axis while leaving all other debug tensors at three-plus-three.

The source-to-client check found and corrected one pre-existing R2A contradiction: prose said a
full-axis R2c transcript needed no parser change, but `src/expert_trace.align` accepted exactly six
values whenever an extent exceeded six and derived truncation flags from extent. Schema 1 now
admits exact compact or full forms based on the ellipsis actually observed. Existing compact
documents remain unchanged; the independent generator now owns full slot/token success and eight
malformed/mixed/non-router refusals. `make check`, `scripts/run-r2c-instrument-smoke` (54 contract
groups), and `scripts/run-expert-trace-smoke` (108 fixtures, 17 error codes) pass. The compiled dense
qualification passes through the product parser: omitted, zero, and negative `-n` each produce one
prefill graph, while `-n 2` produces one prefill plus two decode graphs. The real OLMoE half also
passes: three graphs including decode, 48 full-width groups, 384 selections, and full-axis extent
eight. Independent parity reports 16 layers, 64 experts, top-8, 488 retained selections, and the
known token-reduced final layer. No model or transcript is committed.

**Review envelope.** Host-native Codex (`gpt-5.6-sol`, xhigh) first reviewed
`5f1eb3e7614a8a8e1cfd4ee13e8b31db3b8c26a8` against base tip and merge base
`1b11245cee98bf3bba8ab874683206b4243d1761`. Verdict: four valid findings — two P1 and two P2 — all
accepted, none rejected. That repair compares staged and unstaged tracked source to `HEAD`; disables
Metal and advances the cache recipe to `r2c-v2`; requires an applicable router extent above six;
and downloads the tiny model to a hash-validated temporary sibling before atomic rename. The same
pass corrected the remaining compact-only normative prose in R2A. Deterministic owners and fresh
dense/MoE materialization pass after repair.

The required final comprehensive review covered `46432ded7e8d60d8bca4f4d33fdc80a252099aae`
against the same base tip and merge base. It found three further valid findings, all accepted and
none rejected: R2/R3 historical replays still changed from six to eight observed slots under the
R2c instrument; explicit/XDG/HOME cache roots could resolve inside the checkout; and router axis 2
could change compact/full print form between groups or blocks. The final repair makes historical
gates share an exact compact-axis admission check, rejects lexical and symlink-mediated checkout
cache containment, and settles the axis-2 form across every applicable group/block with a new
`R2_ROW_COUNT` fixture. The repair is limited to those recorded findings and their plan/owner
evidence, so the workflow requires repair-delta inspection and affected owner verification rather
than a third comprehensive review. Both are complete.

**Candidate contents.** The pin, patch, managed builder, deterministic smoke, focused qualification,
R2A parser/source oracle changes, R2A specification correction, roadmap and developer-guide
changes, and this handoff update belong to this capability. `Makefile` and aggregate topology are
intentionally unchanged, so the canonical coding baseline artifact set is unchanged.

Published and merged as PR #140. R5D merges it in rather than rebasing over it, so this branch's
recorded baseline-chain commits stay reachable; `Makefile` and the canonical baseline artifact set
are unchanged by it, so R5D's chain still binds.

**Latest durable verification.** On WSL2 x86_64 with GNU 14.2.0 and the managed Align
`3a34febe` toolchain:

```text
scripts/run-r2c-instrument-smoke                         PASS, 54 contract groups
make expert-trace-smoke                                  PASS, 108 fixtures / 17 error codes
make residency-sim-smoke                                 PASS, oracle and admission owners
make check                                               PASS, 31 units per-unit
scripts/run-r2c-instrument-qualification                 dense PASS; MoE PASS
scripts/run-expert-trace-parity                          MoE PASS; model read-only proof PASS
scripts/llama-eval-callback-toolchain verify             bb4caa7540188872173c44d161602d9271386413
scripts/llama-eval-callback-toolchain attest instrument  r2c-v2, instrument sha256 2911b1ffed36...
```

## Merged checkpoint: R3-RESIDENCY-SIM (2026-08-28)

PR #135 merged as `95c47e7` after all three GitHub checks passed. Design ledger
`docs/specs/r3-residency-sim.md` remains authoritative. Implementation, real-model qualification,
review, publication, and merge are complete.

**What it delivers.** The R3 roadmap gate, measured. `main --simulate-residency` replays the demand
stream implied by a set of real `R2_ACTIVATION_TRACE` documents against ten expert-residency cache
policies in four families — `lru`, `lfu`, three fixed-window `recent_reuse`, two `topk_prefetch`
degrees, plus the `null` / `compulsory` / `belady` references — at a nine-point budget sweep, with a
leave-one-document-out jackknife over the corpus and a headroom measure against the miss-optimal
offline reference, and emits one `R3_RESIDENCY_SIM` (`schema_version: 1`) document. The design gate
triggered on three counts: a new public CLI verb, a new versioned exchanged format, and a coordinated
invariant across three modules plus the `Makefile`.

**The gate is met.** On the real 40-prompt corpus (`eval/prompts/expert-locality-v1.txt`, md5
`d7fff23f5a1d4f6237e6f848f3318d8b`) against `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`: a stream of
17,280 demands over 938 distinct `(layer, expert)` keys of 1,024, 192 token positions, slot coverage
750 per mille. At the requested budget of 975,175,680 B (250 per mille of the 3,900,702,720 B expert
footprint), verdict `BEATS_BASELINE` — `recent_reuse_w32` fetches 26,033,848,320 B against the `lru`
baseline's 33,532,231,680 B, 223 per mille fewer against a 50-per-mille materiality floor, with a
40-fold jackknife minimum gain of 213 per mille (stable) and 574 per mille of headroom still left to
the offline optimum. Across the sweep: `BEATS_BASELINE` at 1/3/6/12/25 per cent,
`NO_POLICY_BEATS_BASELINE` at 0 and 50 per cent, `NO_HEADROOM` at 100 per cent. Top-k prefetch buys
hits and pays for them with more bytes than it saves: under the shipped MRU insertion rule
`topk_prefetch_k1` issues 219 prefetches of which 102 are later hit (465 per mille) and
`topk_prefetch_k8` issues 3,332 of which 1,590 are (477 per mille), and no `topk_prefetch` cell is
below `lru` at any budget. Roadmap section R3's other three policies — score-based, impact-driven
prefetch, CPU fallback — are deferred with named prerequisites (a router-weight column R2A does not
capture; R4.5's and R5's measured transfer costs; R5's microbenchmark) rather than simulated against
invented constants.

**Committed on the branch.** Nothing is uncommitted. After the rebase onto `4f01553` the branch is
`4951ff6` (design ledger), `424a516` (implementation), `a22f839` (review repair), `2e058f7` (final
review repair), and the reconciliation and baseline commits on top; before the two rebases the first
four were `198850b`, `ff4f76d`, `c7cfe1a`, and `967aadf`, and the review record on the pull request
names the pre-rebase heads the reviewers read. Two prerequisites the branch once carried are now in
`main` and are no longer part of this diff: the merged R2 wave's corrected `src/expert_trace.align`
and its four owners, without which every real OLMoE capture fails `R2_TOKEN_COUNT` on layer 15's
token-reduced `ffn_moe_topk`. **The `Makefile` changes** (`residency-sim-smoke`, a new
`HOSTED_CHECK_TARGETS` member, and `residency-sim-qualification`, in no aggregate), so the classifier
selects executable preflight and the baseline commit chain has to be re-recorded on this branch.

**Integration with PR #134 and PR #136.** C8-OPTIONAL-TARGETED-STAGE merged while this branch was
in publication, and GCC14-FP-CONTRACT-PORTABILITY (PR #136) merged after it — the ggml shim's
Clang-only `#pragma STDC FP_CONTRACT OFF` under GCC 14.2 and `-Werror`, a pre-existing hosted-check
failure this capability's own preflight surfaced; both are merged into this branch. PR #134 moved `.align-revision` from `4b515f8d` to **`3a34febe`** (Align PR #892, its own
Request 44). That renumbered this capability's two register entries — R3's requests are now
**Request 45** (the compiler soundness defect) and **Request 46** (the `borrow mut` array gaps) —
and it invalidated both the first preflight stamp and the first baseline chain, because
`.align-revision` is itself one of the twenty recorded baseline artifacts. Every owner below is
re-run against the managed `3a34febe` compiler; nothing in R3's own behaviour changed with the pin.

**Review envelope.** Two complementary reviewers covered explicitly disjoint risks at the pre-rebase
implementation head `ff4f76d` (`424a516` after the rebases): reviewer A the Align source and the
simulation semantics (1 blocker, 1 major, 4 minor, 1 observation), reviewer B the governance,
contract, and verification surface (1 high, 3 medium, 5 low). **All fourteen findings were accepted**,
none rejected, and all are repaired in one consolidated commit (`c7cfe1a`, `a22f839` after the
rebases), recorded as items 16 to 23 of the ledger's correction register. Two changed shipped
behaviour rather than prose: an `ExpertBlock` with `byte_size: 0` took `SIGABRT` through a
`resident_list` overrun and is now refused with `R3_EXPERT_BLOCK_SIZE`, and `best_policy` could name
a jackknife-**unstable** candidate beside `jackknife_stable: true` and now names the qualifying one.
Six hosted cases and five error-code cases were added, and the prefetch insertion rule is now
specified as MRU — which moved only the two `topk_prefetch` rows and changed no verdict, sweep row,
or non-prefetch policy on the fixtures or on the real corpus. The final review at `c7cfe1a` is
**approve** with five documentation-only findings, all repaired in `967aadf` (`2e058f7` after the
rebases); that repair is documentation-only apart from the smoke's new explicit-template B1
self-check, so no further comprehensive review is required. The reconciliation commits onto the
merged MoE prerequisites and onto PR #134 are documentation-only.

**Verification.** Durable owner evidence at the rebased head, on this macOS host with the recorded
Homebrew `LIBRARY_PATH` and the `CARGO` wrapper the managed `3a34febe` build needs
(`docs/align-development.md`):

```text
gmake check                    ok: checked 31 unit(s) per-unit
gmake build                    ok
gmake residency-sim-smoke      PASS x3, byte-identical - 2 model IRs, 23 traces, every policy at
                               every sweep budget in both orders against the independent Python
                               oracle, both CLI forms, the golden, determinism, the section 2.6
                               error corpus, and CLI arity/isolation
gmake expert-trace-smoke       PASS - 98 fixtures, 17 error codes
gmake model-ir-smoke           PASS - 49 qwen, 31 gpt-oss, 29 olmoe, 62 R0 fixtures re-run
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases; olmoe claim surface PASS
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,300 assertions
gmake verify-loop-smoke        PASS - PR #134's schema-v2 owner, unchanged by this branch
gmake gate-topology-check      PASS
gmake format-check             PASS; gmake fmt leaves no diff; git diff --check clean
```

The focused qualification, on the host that holds the models (MEASURED, in no aggregate):

```text
gmake residency-sim-qualification  BEATS_BASELINE - the numbers above; 40 captures in 55.7-64.1 s
                                   across three post-repair runs, every transcript deleted after
                                   conversion
```

**Measurement.** This is a policy claim about the named MoE model and this corpus, not a platform or
throughput claim. It compares fetched bytes only; elapsed time is printed as a diagnostic. The stream
is prefill-only, replayed in decode order because decode is the regime being modelled and not because
decode was observed; the instrument prints six of eight router slots; the corpus is 40 independent
prompts of at most six tokens, so cross-prompt reuse carries most of the cache pressure. Read the
result as "across a session of many short requests, frequency-aware residency beats recency", not as
"within a generation, expert reuse is high".

**Baseline chain, re-recorded.** The `Makefile` change, plus PR #134's `.align-revision` move that
this branch adopts, invalidate the chain that shipped with C8-OPTIONAL-TARGETED-STAGE, so the
identity-bound chain is re-recorded on this branch as `ec5ca39` -> `e729b68` -> `4bf5976` (clean
source -> immutable oracle -> finalization), measured on Linux (aarch64, kernel 6.11.11-linuxkit,
Python 3.12.3) and checked there with `make baseline-check` ending `baseline chain: PASS`. Three of
the twenty recorded artifacts changed: `.align-revision` (`4b515f8d` -> `3a34febe`, PR #134's, adopted
unchanged), `Makefile`, and `src/main.align`, the latter two this capability's own. The other
seventeen hashes are unchanged and the twenty paths are identical. PR #135 merged with merge commit
`95c47e7`, preserving the recorded source, oracle, and finalization commits.

**Align capability requests.** Implementation added Requests 45 and 46 (filed as 44 and 45 before
PR #134 took 44), both `PROPOSED`, non-blocking, and shipped around with documented workarounds.
**Request 45 is priority high**: a compiler soundness defect, where the region checker accepts a move
of a Move-typed field out of a `json.decode`d record through a two-hop field-access chain with no
diagnostic and the built program corrupts the heap at run time on the decoded record's recursive
`Drop`; the shipped fix is one `.clone()`. Request 46 is two related array-shape gaps
(`borrow mut array<T>` loop invalidation, and no element assignment through an array field). R3 also
strengthened Requests 21, 23, and 26 with new client evidence.

## Merged checkpoint: MOE-PREREQ-DISCHARGE (2026-08-28)

Branch `agent/moe-prereq-discharge` merged as PR #133 at `35a0df6`, preserving its recorded
baseline chain with a merge commit. Design ledger `docs/specs/moe-prereq-discharge.md` remains
authoritative. Implementation, review, publication, and merge are complete.

**What it delivers.** The per-expert half of the R4 and R4.5 gates, measured on the real olmoe
model rather than on the synthetic corpus. Two verdicts stop being constants and become rules over
the block set the run measured:

- `scripts/run-alignpack-qualification` reports the container's `ExpertBlock` improvement —
  1,024 blocks, 3,072 -> 1,024 ranges, 165,368,823,808 -> 3,900,702,720 span bytes,
  42,394,624 -> 1,000,000 ppm, 0 -> 1,024 of 1,024 contiguous;
- `scripts/run-ggml-spike` selects both arms by `role_id` out of the pack document it just wrote
  and computes real expert claims: all three members of the first `ExpertBlock` and member 0 of the
  last (block 1,056, plane 63 of 64), every one `EXTERNAL`, `IDENTICAL`, and bit-identical to the
  same plane read from the original GGUF.

Admitting the claim form required `R4_5_EXTERNAL_BUFFER` `schema_version: 2`, the split of step 7
into 7a (the slice pair) and 7b (the shape by form), and the new `R4_5_SLICE` code — the shipped arm
had refused a real expert claim with `R4_5_SHAPE`, detail `n_dims[3]`, so R4.5's own claim that the
CLI already addressed an `ExpertBlock` with no new surface is refuted and removed. R4's expert
hotness ordering and prefetch groups, and R4.5's GPU expert arm and discrete-VRAM half, stay
deferred and are unchanged.

**Committed on the branch.** Nothing is uncommitted. After the rebase onto `e15e3d3` the branch is
`4656d88` (design ledger), `eed850e` (implementation), `4bf25b8` (review repair), `0dd4ea8` (the
developer guide, which still described both qualifications as they were before this capability
changed them), and the reconciliation and baseline commits on top; the first three were `49f8e4c`,
`ee041a7`, and `5015daf` before the rebase, and the review record below names the pre-rebase head it
read. **The `Makefile`
changes** — `ggml-spike-smoke` gains a `build` prerequisite, because its claim cells are taken from
a container `main --pack` wrote — so the classifier selects executable preflight and the baseline
commit chain has to be re-recorded on this branch.

**Review envelope.** One comprehensive reviewer covered the whole diff at the pre-rebase
implementation head `ee041a7` (`eed850e` after the rebase): verdict **approve**, eight findings —
four minor, two low, two nits. **All eight were accepted**, none rejected, and all are repaired in
one consolidated commit on top of it (`4bf25b8`). The repair is narrow — a reclaim pattern, a
detail token, two documentation corrections, one added qualification run with its digest, a report
count, one assertion strengthened from a prefix to exact lines, and named refusals in the selector —
so it does not trigger a second comprehensive review, and the reconciliation commit onto the merged
R1C is documentation-only.

**Verification.** Durable owner evidence at the rebased head, on this macOS host with the recorded
Homebrew `LIBRARY_PATH` (`docs/align-development.md`):

```text
gmake check                    ok: checked 30 unit(s) per-unit
gmake build                    ok
gmake ggml-spike               ok, stub shim and real shim
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases; olmoe 22 blocks /
                               69 members, 16 ExpertBlocks, n_expert 8, claim surface PASS
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,298
                               assertions; qualification-verdict MoE PASS and dense N/A
gmake model-ir-smoke           PASS - 49 qwen, 31 gpt-oss, 29 olmoe, 62 R0 fixtures re-run
gmake expert-trace-smoke       PASS - 98 fixtures, 17 error codes
gmake layer-forward-smoke      PASS - 59 + 28 documented cases, three oracles
gmake gate-topology-check      PASS
gmake format-check             PASS; gmake fmt leaves no diff; git diff --check clean
```

Both focused qualifications, on the host that holds the models:

```text
gmake alignpack-qualification  PASS (olmoe) - identity, sequential read, and the MoE verdict above
gmake ggml-spike-qualification PASS (olmoe) - dense + three expert claims + the last plane;
                               1 dense, 3 expert, 1 last-plane digest checked
                               PASS (qwen2) - dense arm, expert arm N/A, 1 dense digest checked
```

**Consequence.** R3 residency simulation may now be reconciled onto the merged MoE result and
implemented after the bounded C8 re-entry. R2b's corpus-wide stratification consumes the merged
locality gate's corpus and aggregator.

**Measurement.** The layout numbers are a claim about this container on this named model, not a
platform or throughput claim; neither qualification asserts an elapsed bound.

**Baseline chain, re-recorded.** The `Makefile` change invalidates the chain that shipped with R5C,
so the identity-bound chain is re-recorded on this branch as
`157278c` -> `2dace6c` -> `b2267c7` (clean source -> immutable oracle -> finalization), measured on
Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) and checked there with `make baseline-check`
ending `baseline chain: PASS`. Two of the twenty recorded artifacts changed against the R5C chain:
`Makefile`, and `src/main.align` — the latter from the merged R1C, which changed no `Makefile` and
so required no re-record of its own. The other eighteen hashes are unchanged and the twenty paths
are identical. PR #133 merged with merge commit `35a0df6`, so these commits remain reachable.

## Pending decisions (2026-08-28)

**Decision (a) taken 2026-08-28.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (allenai;
4,213,512,192 B; sha256 `4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f`; arch
`olmoe`; 16 layers, 64 experts, top-8 routing; types F32/Q4_K/Q6_K) is downloaded to the local
models directory (path withheld from this file by convention). Disk free is now ~16 GiB on this
host. **Decision (b) is now infeasible on this host**: `gpt-oss-20b-mxfp4.gguf` at 12.1 GB no
longer fits alongside the downloaded model and its alignpack space; R1B's real-model
`model-ir-parity` qualification stays open pending a host with more free disk. **Decision (c) is
now TAKEN and merged** as PR #140; decision (d) is unchanged and still pending.

1. **Small MoE GGUF, 1-4 GB. — TAKEN.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (3.9 GiB) is on
   this host. It unblocked the R2 locality gate (merged, PR #131), R1C's `olmoe` frontend (merged,
   PR #132), and R4's per-expert half with R4.5's expert matmul (merged, PR #133). R3's residency
   simulation (merged, PR #135), its qualification-prerequisite follow-up (merged, PR #138), R5D's
   routed layer (merged, PR #139), and R5E's whole routed model, in publication above, follow from
   the same file rather than from another download, as does R2D's decode locality gate (merged,
   PR #141).
2. **`gpt-oss-20b-mxfp4.gguf`, 12.1 GB.** Unblocks R1B's real-model `model-ir-parity` qualification
   and every `ASSUMED` row of `docs/specs/r1b-gptoss-moe-ir.md` section 2.5 — including the two
   rows R1C has now contradicted from the olmoe side. **Infeasible on this host** after decision 1
   (disk free ~16 GiB); it stays open pending a host with more free disk.
3. **Build llama.cpp from source at `bb4caa754`** and apply the R2c minimal instrument patch (decode-
   step graphs, untruncated `ffn_moe_topk`). **TAKEN**, shipped and merged as PR #140,
   `docs/specs/r2c-decode-instrument.md`: `.llama-revision` and a 2,170-byte two-file patch pin the
   source, and the `r2c-v2` managed builder materializes the instrument into an identity-addressed
   cache outside Git. It unblocks R6 (Persistent KV) and, through it, R7-R9, and it is what extends
   the merged locality gate past prefill — R2D-DECODE-LOCALITY-GATE is doing exactly that now. The
   cost stands as recorded: a clone plus a cmake build, and a qualification reproducible only on
   hosts that repeat the build.
4. **Align Request 41** (non-`Copy` capture in `spawn` closures), Align-side. Unblocks R5's required
   microbenchmark C.

**Align capability requests.** Requests 1-20 CLOSED, Requests 21-43 and 45-48 PROPOSED and
non-blocking, and Request 44 ALIGN_LLM_VERIFIED, closed by PR #134. **Requests 47 and 48 are new,
filed by R5E-MOE-MODEL-PREFILL** (see above), drafted as 46 and 47 and renumbered at reconciliation
when R3's pair took 45 and 46; both probes re-measured unchanged at `3a34febe`. `.align-revision` now selects
`3a34febe`. Requests 45 and 46 are new, filed by R3-RESIDENCY-SIM (see above) and renumbered from
44 and 45 when PR #134 took 44; Request 45 is priority **high** — an accepted-but-unsound compiler
defect — rather than the medium/low of the rest of this range. **R5E added two requests and appended client evidence to two more**: Requests 45 and 46 each gain
R5E as a third client — `layer_olmoe.parse_geometry`'s decoded-record reads, reused unchanged, and
sixteen per-layer routing decisions that repeat R5D's two array-shape gaps once per layer. **R5D added no request and appended
client evidence to four**: Requests 45 and 46 gain `src/layer_olmoe.align`'s `parse_geometry` and its
routing decision (the two R5D could only anticipate before PR #135 merged them), Request 37 gains
R5D's per-unit check times — 15.6 s for the arm's own unit against 0.67 s for the 1,403-line module
beside it, which retires R5B's and R5C's under-10 s single-unit target rather than restating it — and
Request 42 gains the second exact repeat of one region diagnostic. Top clients by reference count in
`docs/align-requests.md` (grep-verified against the register): Request 34 (`Result` payloads beyond
scalars, 9 mentions), Requests 21 and 23 (read-only open; huge-struct-copy lint, 8 each — Request 23
gained R1C's `src/frontend_olmoe.align` and then R3's `residency_sim$Derived`, making six clients
across five wide records), and Requests 33 and 32 (aligned allocation; FFI by-value structs, 6 each);
Requests 32, 33, and 37 are also R5's own named clients.

**R2-LOCALITY-GATE merged checkpoint (PR #131, head `fff5806`, merge `546b5cc`).** The R2 gate is
**met in the prefill direction**. `scripts/run-expert-locality-gate` over
`eval/prompts/expert-locality-v1.txt` (40 prompts, all ≤ 6 tokens, md5
`d7fff23f5a1d4f6237e6f848f3318d8b`), one invocation per prompt, 51.8 s:

```text
verdict=LOCALITY prompts=40 layers=15 layers_clearing=15 pairs=2280 hits=3924 trials=13680
p0_per_mille=125 p_hat_per_mille=286 wilson_lo_per_mille=279 wilson_hi_per_mille=294 clusters=40
deff_per_mille=10460 cluster_lo_per_mille=262 cluster_hi_per_mille=311 ratio_per_mille=2288
entropy_per_mille=992 top8_mass_per_mille=180 truncated_documents=0 token_reduced_documents=40
token_reduced_layers=15
```

Adjacent-token expert reuse is 286 per mille against a 125 per mille null (`k/n` = 8/64), 2.29× the
null against a 1.5× materiality threshold, with all 15 contributing layers clearing the null on
their own stratum. The verdict is judged on the cluster-robust interval `[262, 311]` (design effect
10.460 over 40 prompt clusters), not the naive Wilson `[279, 294]`. The router histogram is nearly
uniform (entropy 992 per mille, all 64 experts used), so the effect is conditional structure rather
than popularity. Working sets grow sublinearly: 10.278 experts over two consecutive tokens where
independence predicts 11.437, 16.495 over four where it predicts 20.830. **Prefill only** — build
10566 evaluates one graph per invocation, `phase_split.decode` is `null`, and nothing there licenses
a decode or cache-policy claim. R2's contingency to shrink repo-expert-profile investment does
**not** fire; R3 has a measured demand signal. The same capability discharged R2A's `MOE-PREREQ`
cells (`expert trace parity (MoE): PASS` over 934 callback blocks) and added correction 20: build
10566 applies the output-token `GET_ROWS` reduction before the last layer's feed-forward, so a
*token-reduced* highest-index layer is parsed and validated but contributes no `selections[]` row
and is listed in the additive `moe.token_reduced_layers` field (`schema_version` stays 1). Full
numbers and every caveat: `docs/specs/r2a-expert-trace.md` section 8.

**R5C merged checkpoint.** Metal microbenchmark A, unified memory: self-reference `IDENTICAL` 479 of
479 nodes over 30 graphs; logits `WITHIN`, max `|Δ|` 2,936 of 6,000 ten-thousandths against R5B's
byte-identical CPU vector, `argmax` 671, top ten identical in order; bit-deterministic across paired
runs (`b6e473e8…` on both passes); transfer 59 wraps at ~12.4 ms each (732 ms total, both passes);
end-to-end wall ratio 0.99×/1.05×/1.31× across three paired runs, recorded **unresolved** rather than
claimed — the spread is `pread`'s. Correction C21 found and repaired a real cross-architecture NaN
sign-bit/payload difference (arm64's default NaN vs. x86-64 SSE's QNaN) surfacing only in the forced
non-finite-readback goldens, masked in golden normalization alone. Full ledger:
`docs/specs/r5c-metal-prefill.md`.

**Resume in another environment.** Fetch `origin`, check out `main`, then check out
`agent/r5e-moe-model-prefill` and read `docs/specs/r5e-moe-model-prefill.md` in full (and
`docs/specs/r5d-moe-layer-forward.md` for the layer half) before touching `src/layer_olmoe.align`,
`src/moe_model_forward.align`, or `scripts/run-moe-model-forward`. R5E's only remaining step is the
merge. After it merges, **no capability is active** here: R2D merged as PR #141 and R3-DECODE-RESIDENCY
as PR #142, and item 25 explicitly orders **R6 (Persistent KV)** ahead of a runtime
expert-residency policy. R6 is the next eligible roadmap work — decision (c)'s merged instrument
unblocks it, and its first task is naming the decode oracle. A separate worktree on
`agent/r6-decode-kv-step1` already exists in this session's scratchpad. R5's deferred microbenchmark
C stays blocked on Align Request 41. Decision 1 is taken; R2's
gate, R1C's frontend, R4's per-expert half, R4.5's expert matmul, C8's optional targeted stage, R3's
residency simulator, R2c's decode instrument, R5D's routed layer, R2D's decode locality gate, and R3's
decode residency gate are all merged, so R5E waits on no further decision. For the rest: decision 2 -> R1B's `model-ir-parity` qualification (section R1);
decision 3 is **taken and merged** as item 22, and its first consumer, item 24's decode locality
gate, is merged too, so R6 (section R6) and R7-R9 are unblocked; decision 4 -> R5's deferred
microbenchmark C (section R5).

**DinD preflight note.** The installed profile requires true Docker-in-Docker on macOS. The recipe
lives in this session's memory, not in the repository, and the scripts that ran it lived only in a
scratchpad and were never committed. Rebuild them from `docs/development-preflight.md` if that file
exists by the time work resumes; otherwise rebuild from the CLAUDE.md rules (the repository wrapper,
`scripts/pre-pr`, and the workflow classifier table) rather than relying on a cached copy.

## Merged checkpoints

Track B, dense local model (R0 → R5C), plus the merged R2 locality gate, the R1C olmoe frontend, the
MoE prerequisite discharge, the R3 residency simulator and its decode half, the R2c decode
instrument, R5D's routed layer, and R2D's decode locality gate; C8's optional targeted stage is the one merged Track A re-entry. The R3-DECODE-RESIDENCY, R2D, R5D, R2C,
R3-RESIDENCY-SIM, MOE-PREREQ-DISCHARGE, R2, and R5C checkpoints are above; the rest, newest first:

- **GCC14-FP-CONTRACT-PORTABILITY** (PR #136, merge `aad872f`): `#pragma STDC FP_CONTRACT OFF` is
  Clang-only, and GCC 14.2 diagnoses it as unknown while `scripts/build-ggml-shim` compiles with
  `-Werror`; the pragma is now guarded and the cross-compiler `-ffp-contract=off` flag plus the
  behavioural probe stay mandatory. It was discovered by **this capability's** publication preflight
  and merged as its prerequisite.
- **C8-OPTIONAL-TARGETED-STAGE** (PR #134, merge `4f01553`): authored and merged by a **parallel
  Codex session**, not by the session that produced the R3 and R5D capabilities above; it is recorded
  here because R3 and R5D both consume its pin move. The targeted verification stage becomes
  optional, `R2`-unrelated, on a fresh fixed-task baseline measuring a 326,093 ppm removable ceiling
  against C8's 2,000 ppm floor; the 101-pair acceptance improves 60,515,456 ns to 40,475,113 ns
  (331,160 ppm). It adopted Align `3a34febe` (Align PR #892) as `.align-revision` and closed
  Request 44 at `ALIGN_LLM_VERIFIED`. Ledger: `docs/specs/c8-optional-targeted-stage.md`.
- **R1C-OLMOE-MOE-IR** (PR #132, head `3580a62`, merge `e15e3d3`): `src/frontend_olmoe.align`, a
  three-way architecture dispatch, and two roles appended to the frozen `role_id` list
  (`attn_q_norm` 27, `attn_k_norm` 28). The real olmoe file reaches `R1_MODEL_IR` at the unchanged
  `schema_version: 2`, the size-sum oracle closes at
  `1,781,760 + 4,211,730,432 = 4,213,512,192`, and the Block IR reaches 1,058 blocks / 3,219 claims;
  `model-ir-parity` PASS against both real models, the first discharged against a real MoE model.
  It also contradicts two of R1B's `ASSUMED` rows — the stacked gate/up/down axis order and the
  required split expert biases — recorded as corrections in `docs/specs/r1b-gptoss-moe-ir.md`
  section 7. Ledger: `docs/specs/r1c-olmoe-moe-ir.md`.
- **R5B-MODEL-PREFILL-FORWARD** (PR #128, head `3470646`, merge `870bf31`): a whole 28-layer Qwen2
  CPU prefill computed over one Align-owned alignpack window, final logits byte-identical to
  `llama-debug --save-logits`. Ledger: `docs/specs/r5b-model-prefill-forward.md`.
- **R5A-DENSE-LAYER-FORWARD** (PR #127, head `0397228`, merge `ccbd8ae`): one Qwen2 dense layer
  computed by ggml over Align-owned weight windows, bit-exact self-reference oracle. Ledger:
  `docs/specs/r5a-dense-layer-forward.md`.
- **R4.5-EXTERNAL-BUFFER-SPIKE** (PR #126, head `d46fce6`, merge `fa567b1`): a ggml matmul over an
  Align-owned quantized DRAM buffer with no silent copy; dense-block gate achieved, expert-block half
  was `MOE-PREREQ`, now unblocked by decision (a) above. Ledger: `docs/specs/r4-5-external-buffer.md`.
- **R4-ALIGNPACK-LAYER-MAJOR** (PR #125, head `a7e72dc`, merge `991eab1`): the alignpack v1
  container, its layer-major layout, and its verifier. Ledger: `docs/specs/r4-alignpack-layer-major.md`.
- **R2A-EXPERT-TRACE-CAPTURE** (PR #124, head `ab5f7d8`, merge `b8e1cb6`): `--expert-trace` CLI
  producing an `R2_ACTIVATION_TRACE` document from a `llama-eval-callback` transcript. Ledger:
  `docs/specs/r2a-expert-trace.md`.
- **R1B-GPTOSS-MOE-IR** (PR #123, head `3bf5c9c`, merge `d8d4ef6`): gpt-oss MoE frontend and
  per-expert Block IR, `R1_MODEL_IR schema_version: 2`; the gpt-oss `model-ir-parity` qualification
  stays open — decision (b) above records it infeasible on this host. Ledger:
  `docs/specs/r1b-gptoss-moe-ir.md`.
- **R1-QWEN-MODEL-IR** (PR #122, head `85a3a97`, merge `08492dc`): Qwen2 Model IR and Block IR,
  `--model-ir`, parity `PASS` against the local Qwen2.5-Coder-7B model. Ledger:
  `docs/specs/r1-qwen-model-ir.md`.
- **R0-GGUF-INSPECT** (PR #121, head `dcd8801`, merge `6640dcf`): read-only `--inspect-gguf`
  inspection, parity `PASS`. Ledger: `docs/specs/r0-gguf-inspection.md`.
- **C8-SPEED-FIRST closed** (final capability PR #120, head `fd78482`, merge `92c0979`): nine
  consumer-complete capabilities, gate met; the ppm-floor rule is the one promoted retrospective
  lesson. Ledger: `docs/specs/c8-speed-first.md`.

Earlier checkpoints, kept for continuity; full evidence lives in the named specs and in git history
at the cited commits:

- **REQUEST20-PIN** (PR #107, head `e1351f8`, merge `eb61086`): adopted Align's macOS owned-JSON CI
  repair; `ALIGN_LLM_VERIFIED` at the selected pin.
- **ADAPTER-ZOMBIE** (PR #106, head `ba02f25`, merge `0a8b9cf`): repaired a zombie/thread-group-leader
  containment-scan defect across six process-containment scanners.
- **C7-P** (PR #105, head `c86ce1e`, merge `a4f8663`): `aarch64-apple-darwin` and
  `aarch64-unknown-linux-gnu` platform profiles for C7 evidence, both discharged.
- **C7-PERSISTED-RESULT** (PR #104, head `e14ba33`, merge `a52b9ac`): `persisted_result.align`
  bounded-bucket-v1 CLI (`persist_file`/`verify_file`) and the Request 9 owned-record adoption
  checkpoint. Ledger: `docs/specs/c7-persisted-result.md`.
- **C6-MEASURED** (PR #103, head `d7f1ff6`, merge `c9a510d`): C6e/C6g1/C6g2 provider proposal and
  measured acceptance gate, `make prompt-gate-check` PASS. Ledger:
  `docs/specs/c6-prompt-context-optimizer.md`.
