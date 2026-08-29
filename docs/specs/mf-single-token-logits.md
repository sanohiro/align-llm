# MF-SINGLE-TOKEN-LOGITS

**Designed 2026-08-29; implemented the same day — section 8 is the result.** Branch `agent/mf-single-token-logits` from `origin/main`
`553563e`, which sections 1 to 7 cite; merged up to `origin/main` `a9561a9` (PR #149, section 8.4),
then `45ff38e` (PR #148, section 8.5), then `4940005` (PR #150, section 8.6) before publication —
three `git merge`s, never a rebase. Filed by `R6-PREFIX-SUFFIX-PREFILL` 11.2. **Roadmap item 36**
(when this was written `main` carried items to 30 and 31–35 were on branches or in draft; 31, 32 and
33 have since landed, 34 and 35 are still reserved); re-check at merge.

## 1. Root cause

`fill_members` (`src/model_forward.align:2495`) and `compare_source` (`:2536`) gather by id only
`if m.pieces[at] > 1` — the piece count as a **proxy** for "this member is the per-token embedding
row set". `build_embed_members` (`:1474`) sets `pieces = tokens`, so a one-token prefill takes the
whole-member branch and reads the table's first row. `moe_model_forward` repeats both predicates
(`:1804`, `:1888`) over its own builder (`:1600`); `decode_step.decode_embed_members` (`:1678`)
*legitimately* sets `pieces = 1` and pre-bakes `token * row_bytes` into `pack`/`source`, so the two
meanings of `pieces == 1` are indistinguishable.

Blast radius, measured. **Four arms**: `--model-forward`, `--model-forward-gpu` (via `render_parts`
→ `execute`), `--moe-model-forward`, `--decode-step` prefill. `--layer-forward` and
`--moe-layer-forward` are **not** affected: they gather unconditionally on member 0
(`layer_forward.align:1847`, `:1488`; `moe_layer_forward.align:1974`, `:2338`). **Nine**
`GraphMembers` sites in three modules (4 + 4 + 1), not eighteen, and only the four predicates read
`pack`/`source`. *(Ten in four modules after item 32's merge, which added
`moe_decode_step.decode_embed_members`; section 8.5.)*

Reproduced here on the checked-in fixture under `ALIGN_LLM_GGML_FORCE=engine`: `--model-forward` at
`0`, `3`, `17` gives one digest `62a46efd…` against `99781f3e…` for the `3,17` control;
`--moe-model-forward` one `e67df972…`; `--decode-step 3` streamed `62a46efd…`/`ok`, and with
`RESIDENT=weights` **`R5_SOURCE_DIVERGED`**.

**Correcting 11.2: the resident path is not immune.** `stage_embed_row` stages the right row, but
`compare_source` still expects row 0, so a one-token non-zero resident run with a REFERENCE fails
today — a false alarm on a correct result. Both predicates must move together.

## 2. Fix

Add `gathered: bool` to both `GraphMembers` records; the predicate becomes `m.gathered && at == 0`.
`build_embed_members` sets it `true` **whatever the count**, the other four builders `false`.
Fifteen lines — 2 declarations, 9 literals, 4 predicates — and `T >= 2` is byte-identical, because
`gathered` is true exactly where `pieces > 1` was.

Rejected: baking `ids[0] * row_bytes` into `build_embed_members` at `tokens == 1` (five sites, no
record change) — smaller, but it keeps `pack`'s meaning count-dependent, the trap that produced the
defect. **No Align gap**: `bool` fields ship already (`Ends.tied`), no borrow or lifetime change,
Request 49's boundary untouched, no new request.

## 3. Design gate — not triggered

No CLI operand, exchanged or persisted format, or ownership boundary; the record is in-memory, with
no schema, `akvp`, or document field. The borderline trigger is a coordinated invariant across three
modules, `GraphMembers` being `pub` and built in three — answered by this row, not a design-only
pull request. **Behaviour delta:** at `T = 1` on four public arms wrong-but-`ok` logits become
correct and the resident false alarm disappears; `T >= 2` unchanged. **Acceptance:** sections 4–5.

## 4. Goldens

**No existing row changes bytes**: every successful case in all six corpora runs three tokens and
none passes a one-token `TOKENS` operand (checked mechanically over `run-layer-forward-smoke`). The
fix is invisible to the corpus yet changes a public arm's behaviour, so the regression is *new
rows*, one token each with a **non-zero** id: `mf-tokens-one` (id 3) with `mf-tokens-one-zero` (id
0, which must keep `62a46efd…`); `mm-tokens-one`; `ds-tokens-one` and `ds-tokens-one-resident`,
which must compare **equal** under `normalize_resident` — the cell failing today; and
`gf-tokens-one` in the `engine+gpu` leg.

## 5. Real-model qualification

Dense Qwen in `scripts/run-model-forward`: `llama-debug -p "def" … --save-logits`, read the
companion `<stem>-tokens.bin`, require **exactly one id, and that id != 0**, then `--model-forward …
<id> … <logits_bin>` with `logits.byte_identical = true`. OLMoE in `scripts/run-moe-model-forward`,
same shape. **Tokenization is checked, not assumed**: a prepended BOS makes a one-token prompt two
ids, and a BOS of id 0 would mask the defect, so the leg prints `N/A` with the observed ids rather
than substitute a prompt. The dense leg's `[750, 912, …]` shows Qwen prepends nothing.

## 6. Owner tests, classifier, and the consumer that reopens

`src/` plus the corpora and two qualification scripts: **executable consumer capability, hosted
preflight**. `gmake build`, then `gmake layer-forward-smoke`, owner of all six corpora; publication
`python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke`. Not `make
ci`: no `Makefile` word, aggregate membership, or topology change.

`R6-PREFIX-SUFFIX-PREFILL`'s `T_prefix >= 2` bound (`R6_SUFFIX`, `prefix[<n>]`, its 11.1 correction
8) exists only because of this defect. Lift it after this merges — drop the bound and
`ds-suffix-prefix-one`, restore the `T_prefix = 1` case its 5.1 dropped — as a follow-up there.

## 7. Handoff draft

> **Active.** `MF-SINGLE-TOKEN-LOGITS`, branch `agent/mf-single-token-logits` from `553563e`, item
> 36. Designed, not implemented; no blockers, no Align request. **Next:** add `gathered` and move
the
> four predicates; add the six golden rows; `gmake build`, `gmake layer-forward-smoke`; the
> real-model legs; then `scripts/pre-pr --owner-test layer-forward-smoke -- gmake
> layer-forward-smoke`.

## 8. Result

Implemented exactly as section 2 designed it: **fifteen lines**, 2 record fields, 9 literals, 4
predicates, and no other source change. `gathered: bool` sits beside `stride` on both `GraphMembers`
records; `build_embed_members` sets it `true` whatever the count and `empty_graph_members`,
`build_head_members`, `build_layer_members` (in each of the two modules) and
`decode_step.decode_embed_members` set it `false`; and `fill_members`/`compare_source` in both
modules read `m.gathered && at == 0`. `pieces` survives only as the loop bound, its one honest
meaning — audited with `grep -rn "pieces\["`, which now finds nothing but the two `break`
conditions per module.

### 8.1 Goldens

**At the implementation head, before any merge**: six new rows, **no existing row changed**,
verified mechanically rather than asserted — each of the
six corpora is a strict prefix of its successor, so the diff is `+6 / -0` lines over
`scripts/{model,gpu,moe-model,decode-step}-*golden.jsonl` and `scripts/{layer,moe-layer}-forward-golden.jsonl`
are byte-identical.

| row | corpus | `output.sha256` |
| --- | --- | --- |
| `mf-tokens-one` (id 3) | model-forward | `867ebc4ea19d2b1b…` |
| `mf-tokens-one-zero` (id 0, control) | model-forward | `62a46efd73d18be1…` |
| `gf-tokens-one` (id 3) | gpu-forward | `867ebc4ea19d2b1b…` |
| `mm-tokens-one` (id 3) | moe-model-forward | `5494edb5e4e86fda…` |
| `ds-tokens-one` (id 3, streamed) | decode-step | `867ebc4ea19d2b1b…` |
| `ds-tokens-one-resident` (id 3, `RESIDENT=weights`) | decode-step | `867ebc4ea19d2b1b…` |

(The `main` merge and the lift it carries add one more decode-step row and **remove**
`ds-suffix-prefix-one`'s, which was a refusal row; sections 8.4 and 8.8. Measured against
`origin/main` the branch adds **seven** golden rows, removes one, and changes none.)

Section 1's two predictions both hold. `mf-tokens-one-zero` carries `62a46efd…` — the digest the
defect produced for **every** one-token prefill, whatever the id — and the fixed non-zero run is a
different vector. `ds-tokens-one-resident` **completes**: the `R5_SOURCE_DIVERGED` false alarm
section 1 recorded is gone, and oracle R finds the streamed and resident documents identical outside
its four declared exclusions.

The rows run outside each block's `ENGINE_CASES` loop, whose assertions are arithmetic on that
block's three-token prompt, and are appended to `ORDER` so the corpora grow by append.

### 8.2 Mutants

Two, both built and run against the whole six-corpus runner with its per-block `SystemExit`
softened, so every block reports rather than the first one stopping the script.

* **The four predicates back to `pieces[at] > 1`.** Kills **exactly the six new rows and nothing
  else**: `mf-tokens-one`'s id-3/id-0 comparison and its golden, `gf-tokens-one`, `mm-tokens-one`,
  both `ds-` rows, oracle R, and `ds-tokens-one-resident` refused with
  `R5_SOURCE_DIVERGED layer[-1]role[token_embd]`. `mf-tokens-one-zero` survives, which is what a
  control is for. That no `T >= 2` row moves is the byte-identity claim of section 2, measured.
* **`gathered: false` at `model_forward.build_embed_members`.** 97 failures: the whole three-token
  dense and GPU corpora as well, because the gather is then disabled outright.

### 8.3 Commands

```text
gmake build                  ok
gmake check                  ok
gmake layer-forward-smoke    ok   (77 + 63 + 29 + 78 + 97 + 119 documented cases)
gmake ggml-spike-smoke       ok
gmake gate-topology-check    ok
gmake fmt / format-check     ok   (fmt changed nothing)
```

`git diff --check origin/main...HEAD` — the exact three-dot form `scripts/pre-pr` runs — is the
tenth command, and it is **clean only from the review-repair commit onward**. At head `8dadcc2` this
file ended with a blank line, so that command exited 2 while this section claimed it clean; the
first comprehensive review found it, the repair strips the line, and the claim is now the command's
own result rather than an assumption. The repair is documents and comments only — no `.align` file,
runner, corpus, or `Makefile` word moves — so `gmake build`, `gmake layer-forward-smoke` and
`gmake format-check` were re-run at the repair head and the real-model legs of 8.7 were not: nothing
a documents-and-comments diff contains can reach them. At the repair head the smoke is `ok` at
77 + 63 + 29 + 80 + 99 + 143 documented cases (139 with a golden row) plus item 32's 59-case
`--moe-decode-step` block; the counts above are the implementation head's, before two merges added
their own rows. Section 8.8 records the one further code change hosted CI required, and the same
commands were re-run after it.

### 8.4 The `main` merge and the `R6-PREFIX-SUFFIX-PREFILL` lift

`R6-PREFIX-SUFFIX-PREFILL` merged as PR #149 (`origin/main` `a9561a9`) while this capability was
waiting on host memory for its real-model legs, and section 6's follow-up came due. `git merge
origin/main`, never a rebase; three conflicts — `HANDOFF.md`, `docs/specs/roadmap.md`, and
`scripts/decode-step-golden.jsonl` — all resolved by keeping both sides, the golden taken from
`main` and regenerated. Item 33's own reconciliation was checked: no new `GraphMembers` builder and
no new copy of the predicate arrived, so the count was still **nine sites and four predicates**
at that head. Item 32 later added a tenth; section 8.5.

**The lift.** That capability required `T_prefix >= 2`, raising `R6_SUFFIX` with detail
`prefix[<n>]` at step 3c, for exactly this defect — its section 11.2 filed it and named this
capability as the consumer that reopens the surface. The bound is deleted:

* `src/decode_step.align` — step 3c's `lexical.count < 2` refusal is gone; the sequence cap is the
  only bound on `T_prefix`. The `tokens_in > 1` builder branch stays but stops citing the defect:
  the two builders now agree byte for byte at one row, so it is a specialization, not a correction.
* `scripts/run-layer-forward-smoke` — `ds-suffix-prefix-one` moves out of the refusal matrix and
  becomes a **passing oracle-S run at `T_prefix = 1`**, joined by
  `ds-suffix-save-prefix-one` (a one-token prefill save in its own process, in `ENGINE_CASES` with a
  golden row) and `ds-suffix-single-shot-2` (the two-token comparand). The two **two**-token runs
  carry no golden row: hosted CI measured a cross-host difference in the decode step at two tokens,
  so they sit in `BOUNDARY_CASES` beside item 33's own four-token comparand. Section 8.8.
* `scripts/run-decode-step` — the split guard widens from `2 <= j` to `1 <= j`. The two guards
  differ only where `⌈|L|/2⌉ == 1`, which needs `|L| <= 2`, and **no prompt that leg takes
  tokenizes to two ids or fewer** (item 33's 5.9 measured 6, 3, 3 and 3), so this adds no real-model
  run; it stops encoding a refusal that no longer exists. That invariant is the corpus's, not the
  code's, and `scripts/run-decode-step`'s comment now says so.
* `docs/specs/r6-prefix-suffix-prefill.md` — new **section 11.5**, plus in-place corrections to
  2.3, 2.7, 3.7, 5.6, 5.7, 9.1, 11.1 correction 8, 11.2 and 12.1. Section 11.5 also records the
  three measurements 11.2 got wrong: nine sites (ten after item 32) not eighteen,
  `--model-forward-gpu` affected while
  `--layer-forward` is not, and the resident path **not** immune.

```text
ds-suffix-save-prefix-one  TOKENS 3            -> ok, output 867ebc4e..., kv SAVED, plane 2 cols
ds-suffix-single-shot-2    TOKENS 3,5          -> ok, output 0cd795d9..., plane 5 cols
ds-suffix-prefix-one       TOKENS 3, SUFFIX 5  -> ok, output 0cd795d9..., suffix n_past_base 1
```

Oracle S and oracle C″ both hold at `T_prefix = 1`, and `867ebc4e…` is the same one-token digest
`mf-tokens-one` carries on `--model-forward`.

**The corpus after the merge.** `scripts/decode-step-golden.jsonl` 137 → **139** rows: three added
(`ds-tokens-one`, `ds-tokens-one-resident`, `ds-suffix-save-prefix-one`) and `ds-suffix-prefix-one`
**removed**, because a refusal pins across hosts and its replacement does not (8.8). No row changes
value. The runner reports **143 documented cases, 139 with a golden row**. The other five
corpora are unchanged from section 8.1. Re-running the predicate mutant against the merged head
kills `ds-suffix-prefix-one` through **both** oracle S and oracle C″, kills
`ds-suffix-save-prefix-one`'s golden row, kills the six rows of 8.1, and nothing else:
`ds-suffix-single-shot-2`, a two-token prefill, correctly survives.

Every command of 8.3 was re-run at the merged head and is `ok`.

### 8.5 The second `main` merge — item 32 adds a tenth construction site

`R6-OLMOE-DECODE` merged as PR #148 (`origin/main` `45ff38e`) while this capability was still
waiting on host memory. `git merge origin/main`, never a rebase; three conflicts — `HANDOFF.md`,
`docs/specs/roadmap.md`, and `docs/align-development.md` — each one both sides adding a block at the
same place, resolved by keeping both. A fourth edit was needed in `HANDOFF.md`: my side's demoted
`R6-PREFIX-SUFFIX-PREFILL` heading was orphaned, because `main` already carries that section.

**The tenth site.** Item 32 ships `src/moe_decode_step.align`, whose `decode_embed_members` builds a
`moe_model_forward.GraphMembers` — the MoE twin of `decode_step.decode_embed_members`, and the exact
shape section 1 names as legitimately carrying `pieces == 1` with `token * row_bytes` already baked
into `pack`/`source`. It takes `gathered: false`. The blast radius is therefore **ten sites in four
modules**, still **four predicates**, and item 32 added no new copy of the gather.

**This is the design choice paying for itself.** A `bool` on the record is a compile-time obligation:
item 32's builder arrived through a merge, from a branch that had never seen this fix, and the build
**refused it** until it said which kind of member it was. The rejected alternative of section 2 —
baking `ids[0] * row_bytes` into `build_embed_members` at `tokens == 1` — would have let that
builder merge silently, because it changes no record and asks nothing of a new construction site.

Nothing else moved: `--moe-decode-step` prefills through `moe_model_forward.build_embed_members`,
which is already correct, and its own decode graph gathers row 0 of a one-row window by
construction. All six corpora regenerated unchanged apart from item 32's own rows, and every command
of 8.3 was re-run at this head.

### 8.6 The third `main` merge — C4-REPAIR-MEASURED

`C4-REPAIR-MEASURED` merged as PR #150 (`origin/main` `4940005`), roadmap item **31**. Track A only:
no `src/` file this capability touches moves, no `GraphMembers` builder arrives, and the audit is
unchanged at **ten sites, ten `gathered` literals, four predicates, zero `pieces[at] > 1`**. Two
conflicts, both `Active`-block collisions: `HANDOFF.md` (item 31's block demoted to a merged
checkpoint) and `docs/specs/roadmap.md` (the reserve comment reduced to 34 and 35, since 31 and 32
have now both landed, then item 31, item 32, item 33, item 36). `main` carried two `Active` sections
at that head — C4's own and R6-OLMOE-DECODE's, which C4's branch had not demoted — so this merge
also demotes the second and leaves exactly one `Active` block.

Every command of 8.3 was re-run at this head and no golden needed regenerating.

### 8.7 Real-model result — section 5's acceptance, on both models

Both legs ran at head `a779979` on the reference host, streamed (no resident arena), against
Homebrew `llama-debug`/`llama-eval-callback` and the two checked-in GGUFs. **Both pass, and the
answer section 5 asked for is byte identity.**

| | dense Qwen2.5-Coder-7B Q4_K_M | OLMoE-1B-7B-0125-Instruct Q4_K_M |
| --- | --- | --- |
| Command | `gmake model-forward-qualification` | `gmake moe-model-forward-qualification` |
| Arm | `--model-forward` | `--moe-model-forward` |
| Prompt | `def` | `def` |
| Ids observed | `[750]` | `[1545]` |
| Exactly one, non-zero? | yes | yes |
| Logits | 152,064 | 50,304 |
| `oracle_logits.byte_identical` | **true** | **true** |
| `output.sha256` | `d639adb97337394649a1a94ccc70767cf989b75c14b80e1de31cfdde4745fb96` | `be4c699fbb888a3504b007c5d66925f621c8067a7f88191e0af42974c3c4ecc7` |
| `output.argmax` | 914 | 33007 |
| Oracle 1 over the one-token window | `IDENTICAL` | `IDENTICAL` |
| Exit | 0 | 0 |

**The tokenization guard did not fire, and that is a result rather than a formality.** Section 5
requires the leg to read `llama-debug`'s own `<stem>-tokens.bin` and print `N/A` with the ids it
observed unless there is exactly one and it is non-zero — because a prepended BOS makes a one-token
prompt two ids and a BOS of id 0 would mask the defect. Both tokenizers produced one non-zero id, so
both legs ran the arm. The dense leg's six-token list `[750, 912, 2877, 11, 293, 1648]` is the
independent confirmation that Qwen2 prepends nothing.

**Nothing else in either qualification moved.** Dense: logits `IDENTICAL` at the reconciliation
width (`d2e48620ae3e31e2066a6172aa32c19c974d996d232ab91b118335e3d245bf74`, argmax 671), transcript
`PASS` 479/479 nodes at max |d| 0 ten-thousandths, self-reference `IDENTICAL` 479/479 over 30 graphs,
both forced builds reaching their codes. Routed: logits `IDENTICAL`
(`a56195da2c913d8dd7fa608917a381200c4b59d1c534fae2d4bbb828f80d2383`), routing identity `MATCH`
546/546 printed ids over 728 slots and 16/16 block sums, transcript `PASS` 227/227 nodes at max |d|
0, self-reference `IDENTICAL` 227/227 over 34 graphs, 33.36 % of expert bytes read at six tokens.
The fix is invisible at `T >= 2` on the real models exactly as it is on the fixtures.

### 8.8 What hosted CI found — the two-token decode step is host-dependent

The first hosted CI run of this branch (`898c064`, PR #151) failed one check on two golden rows, and
the failure is a real property of the fixture rather than of this fix:

```text
ds-suffix-single-shot-2  .steps[0].bit_sum 71850835819 != 71850835587
ds-suffix-prefix-one     .steps[0].bit_sum 71850835819 != 71850835587
                         .steps[0].sha256  a206116118... != cbd24e660f...
```

macOS/arm64 against Linux/x86_64, and **both rows differ identically**, which is the point: oracle S
holds on each host, and what cannot hold is a file of digests compared across two. Item 33's
deviation 7 already recorded this class at a **four**-token prefill, and section 6 risk 4 of that
document had put the boundary higher still. It is lower again, and in a different place: the drift
is in the **decode step** after a two-token prefill, not in the prefill. The one-token rows this
capability adds — `ds-tokens-one`, `ds-tokens-one-resident`, `ds-suffix-save-prefix-one` — were
byte-identical on both hosts and stay pinned, which is what makes the boundary a measurement rather
than a guess.

`ds-suffix-single-shot-2` and `ds-suffix-prefix-one` therefore move from `ENGINE_CASES` into
`BOUNDARY_CASES`, exactly as `ds-suffix-2`'s comparand did. They remain **documented cases with
every assertion intact**: oracle S compares the pair within one host, oracle C″ compares the suffix
run against `--model-forward` on that host, and `record()`'s document-identity assertions run. Only
the two pinned digest rows are gone: `scripts/decode-step-golden.jsonl` is 137 → **139** and the
runner prints 143 documented cases, 139 with a golden row.

Nothing else moved. No `.align` file, no oracle, no refusal, and no other corpus.
