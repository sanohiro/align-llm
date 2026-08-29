# MF-SINGLE-TOKEN-LOGITS

**Designed 2026-08-29; implemented the same day — section 8 is the result.** Branch `agent/mf-single-token-logits` from `origin/main`
`553563e`, which every line cites. Filed by `R6-PREFIX-SUFFIX-PREFILL` 11.2. **Roadmap item 36**
(`main` carries 30, 31–35 are on branches); re-check at merge.

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
`pack`/`source`.

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

Six new rows, **no existing row changed**, verified mechanically rather than asserted: each of the
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
git diff --check             clean
```

