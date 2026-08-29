# R6-OLMOE-DECODE: sixteen greedy steps on a routed model, and the runtime expert demand they make

Status: **implemented and measured, 2026-08-29.** Branch `agent/r6-olmoe-decode`, written on
`agent/r6-resident-weights` head `6facd56` and merged with `origin/main` `553563e` by `git merge`.
**Sections 1 to 11 are the pre-implementation design and are unedited**; sections 12 to 15 record
what was built, what it measured, every deviation, and what the result owes the toolchain. Read them
in that order: the point of committing the design first was that its predictions could be wrong in
public, and twelve of them were.

Sections 1 to 5 are written **before** the first line of implementation, and they are committed
before it, because `docs/specs/r6-resident-weights.md`'s preamble records that the previous Track B
performance capability could not prove the same ordering and asked its successor to make the
ordering a fact about the repository rather than a claim in a document. This document is that
successor. Section 6 onwards will record what was built, what it measured, and every deviation.

This capability extends four documents and restates a row only when it changes:

| Document | What this one inherits |
| --- | --- |
| `docs/specs/r5d-moe-layer-forward.md` | expert claims, the compact stack, `mul_mat_id`, the slot-order rule |
| `docs/specs/r5e-moe-model-prefill.md` | the whole-model OLMoE schedule, the four node tables, the routing-identity oracle, the residency metric |
| `docs/specs/r6-decode-kv-step1.md`, `r6-step-n.md` | the KV plane, slot numbering, the N-step loop, gate G |
| `docs/specs/r6-kv-persist.md`, `r6-resident-weights.md` | the `akvp` container's identity fields, and the arena this capability declines to use |

## 1. Decision and boundary

### 1.1 What this capability is

`--decode-step` runs `N` greedy steps on a **dense** model. `--moe-model-forward` runs **one**
prefill on OLMoE. Neither can answer the question Track B exists to answer, which
`docs/specs/r3-residency-sim.md` section 8 states in four words — **the intervention is decode** —
and which `docs/specs/r5e-moe-model-prefill.md` section 5.4 then declares unanswerable from a
prefill: within one prefill there are 343 demands over 343 distinct keys, so there is *nothing for
a cache to hit*, and every residency number R5E published is a routing property rather than a policy
result.

This capability ships the smallest thing that produces the missing measurement: **`N` greedy decode
steps on OLMoE-1B-7B-0125-Instruct Q4_K_M over an Align-owned KV plane, where each step resolves
that step's top-8 expert claims per layer and computes only those experts**, on CPU, with the
weights **streamed**, gated on routing identity against llama.cpp at every step and on the token ids
llama.cpp itself produces at `--temp 0 -s 0`.

**The deliverable is a demand stream, not a policy and not a speed.** What the run publishes is, per
step and per layer, exactly which `(layer, expert)` keys were claimed and exactly how many bytes were
read for them.

**What this adds over `docs/specs/r3-residency-sim.md` section 8, stated precisely, because that
capability already simulated decode residency and this document must not pretend otherwise.** R3
section 8 ran four policy arms over 40 prompts × 16 decode steps of *llama.cpp's* trace and reported
bytes a *simulator* would fetch. It is a strong result and this capability does not repeat it. What
it cannot say, and what only an arm that computes the model can:

1. **That the claimed bytes are the bytes actually read.** A simulation over a transcript assumes an
   implementation that reads exactly the routed planes. This capability *is* that implementation, and
   `residency.expert_bytes_read` is what its own pack reader counted.
2. **What the read costs beyond the claim.** Section 3.11 publishes the claim scatter's measured
   `pread` bytes beside the arithmetic claim bytes. Their ratio is read amplification, which no trace
   contains.
3. **That the routing the demand stream describes is llama.cpp's routing**, per step, per layer, over
   all eight slots — section 4.3.
4. **The per-prompt marginal curve**, which section 8.4 of R3 explicitly leaves open and which
   section 2.4 shows is where the whole result lives.

### 1.2 What is already known, and what is not

Section 2 is a probe record over two full-axis OLMoE decode transcripts that already exist in this
work tree. It settles more than the brief assumed, and the two things it settles change the design:

1. **A decode graph does not narrow, so every one of the sixteen layers routes.** R5E measured that
   an OLMoE prefill collapses to one token *inside* layer 15, which drops layer 15's routed union to
   exactly 8 and moves the whole-model figure by 2.1 points. At `T = 1` there is nothing to collapse:
   layer 15's `ffn_moe_topk` is `{8, 1}` in a decode graph exactly as layers 0 to 14 are, and R2A's
   token-reduced-tail exclusion — which discards prefill layer 15's selections — **does not apply to
   a decode graph**. Every step routes 16 × 8 = 128 slots and every one of them is comparable.
2. **The per-step demand is therefore a constant, and it is exactly 125,000 ppm.** Not
   approximately: `n_expert_used / n_expert = 8 / 64` of *every* layer's expert bytes, on every step,
   on every prompt, giving `3,900,702,720 / 8 = 487,587,840 B`. Measured identical on seven decode
   graphs across two prompts. **The number is not new** — it is exactly
   `docs/specs/r3-residency-sim.md` section 8.1's `one_token_working_set_bytes` of 487,587,840 B for
   the `decode_only` and `decode_head4` arms, 128 keys at 16 × 8, reached there by the same
   arithmetic. What is new is that this capability makes an implementation **read** that many bytes
   and no more, so the honest primary claim is not the figure but its **exactness**: a pack reader
   that accounts 487,587,840 B of expert traffic per step and not one byte more is a proof the arm
   computed only what it claimed.
3. **What is genuinely open is the per-prompt marginal curve, and section 2.4 shows it is where the
   whole result lives.** R3 section 8 pools 40 prompts and reports policy bytes; it publishes no
   per-prompt union curve, and its section 8.4 records the mechanism behind decode's loss as "one
   candidate explanation, not a demonstrated mechanism". Over four decode steps on one prompt the
   cumulative distinct-key set grows 128 → 167 → 214 → 274 of 1,024, **79.9 % of every decode demand
   was already read by the prefill**, and the marginal *new* bytes per step are 77.8, 18.8, 69.1, and
   46.3 MB against a 487.6 MB streamed demand — a **9.2× gap** between what a streaming arm reads and
   what an oracle-perfect cache would read. That gap is the intervention R3 section 8 named, and
   measuring it as real bytes at `N = 16` on four prompts is this capability's product.

### 1.3 Why a design gate is triggered

Three of the four triggers fire.

- **A changed public CLI surface.** A new arm, `--moe-decode-step`, with its own operand grammar,
  arity set, and refusal codes.
- **A changed exchanged format.** A new document kind, `R6_MOE_DECODE_STEP`, at `schema_version: 1`,
  with a new checked-in golden file.
- **A coordinated invariant across three or more modules.** This one genuinely fires, unlike in
  R6-STEP-N and R6-RESIDENT-WEIGHTS where it was recorded as not firing. The **expert claim's
  ownership across a step boundary** is an invariant that `src/moe_decode_step.align` (the arm and
  the loop), `src/layer_olmoe.align` (the decode node tables and the slot axis), and
  `src/moe_model_forward.align` (the two-phase read schedule and the claim window) must all agree
  on, and it is not an invariant any of them owns today: R5E's claim window is refilled once per
  layer within one prefill and freed with it, and this capability refills it `N × 16` times inside a
  loop whose plane is simultaneously live. Section 5 is built for exactly that.

### 1.4 Declared boundary

**In scope.** OLMoE-1B-7B-0125-Instruct Q4_K_M; CPU only; `N` greedy steps over one Align-owned KV
plane grown in place; per-step router resolution and a compact expert stack of exactly
`n_expert_used` planes per role per layer; **streamed** weights; the per-step and cumulative expert
demand published as exact integers; routing identity against the R2C-patched instrument at every
step and every layer; the token-id gate.

**Out of scope, declared non-goals, each with the reason it is not an omission.**

- **Resident weights.** Not deferred for cost — **excluded because it destroys the measurement.**
  `docs/specs/r6-resident-weights.md` makes a decode step read *zero* pack bytes by construction, and
  this capability's primary metric is the pack bytes a decode step reads. An arm that is both
  resident and measuring demand publishes `step_expert_bytes = 0` and has measured nothing. The two
  capabilities are mutually exclusive in one invocation and this one must come first, because the
  demand stream is the *input* to any partial-residency policy the arena would then serve. Section 8
  records the combination — resident dense weights with streamed experts — as the first deferred
  surface, with the exact operand it would take.
- **KV persistence (`KV_SAVE` / `KV_LOAD`).** The `akvp` v1 header carries
  `document_schema_version`, whose contract is "the `R6_DECODE_STEP` schema this writer emits"
  (`docs/specs/r6-kv-persist.md` section 2.3.1, offset 136). A container written by an arm that
  emits `R6_MOE_DECODE_STEP` would put a number in that field that means a different document, and
  the honest fix is a `document_kind` field and an `akvp` v2. That is a format change with no
  consumer in this capability, which never needs to reload a plane: section 8 defers it with the
  exact field.
- **Any sampler but greedy `argmax`; EOS and stop handling.** R6-STEP-N section 2.12's decision and
  its reason, unchanged, including the runner's graph-count refusal as the EOS detector.
- **Any eviction, tiering, prefetch, invalidation, or partial-residency policy.** This capability
  produces the input to one; it does not contain one. A policy claim needs the demand stream first,
  which is section 1.1.
- **Text.** No tokenizer and no detokenizer; the gate is on ids. R6-STEP-N section 1.3, unchanged,
  and Align Request 22 gains no consumer here.
- **The Metal arm, batch size above one, a growing `KV_WIDTH`, gpt-oss or any second routed
  architecture, and `--moe-layer-forward`.**
- **Any tokens-per-second, TTFT, or throughput claim, and any cost ceiling.** Section 3.11 states
  what is published instead and why no ledger ceiling is recorded. `docs/specs/r6-resident-weights.md`
  section 3.4 is the owner of Track B decode performance and this capability does not take that
  ownership or spend against it.

## 2. Probe record

No model was run for this document. Every number below is read out of transcripts that already exist
in this work tree, produced by the R2C-patched instrument, plus arithmetic on
`docs/specs/r5e-moe-model-prefill.md`'s published per-layer expert-byte table. The scanning script
is thirty lines of `re` and is reproduced by section 2.1's description; it is not checked in, because
section 4's routing oracle is the checked-in scanner and a second one would be a second thing to
maintain.

### 2.1 The two transcripts, and the instrument that produced them

| Field | Value |
| --- | --- |
| Instrument | `llama-eval-callback`, R2C-patched, generation `r2c-v2`, llama.cpp `bb4caa7540188872173c44d161602d9271386413`, build 10566, patch SHA-256 `fcab7ca9b6bbdc760da19e075a2c66d670d4737d7f7f07074676ec67dbd7d0ab` (2,170 B), instrument SHA-256 `1021d27c82358608f9a3c51c9a9f1070a27348b1288c8a64b69ea213b0679d4b` |
| Model | OLMoE-1B-7B-0125-Instruct Q4_K_M — `token_embd.weight{2048, 50304}`, `n_layer` 16, `n_expert` 64, `n_expert_used` 8 |
| Transcript A | `patched-n4.txt`, 4,827,944 B, 81,741 lines. Prompt token ids `1545, 823, 9, 66, 13, 270, 2262` (`T = 7` — R5E's six-token prompt plus the id R5E's prefill predicts), `-n 4`. **Five graphs**: one prefill and four decode |
| Transcript B | `probe.txt`, 3,845,047 B. A second prompt, `T = 5`, `-n 3`. **Four graphs**: one prefill and three decode |
| Router axes | **Full** in both, on every `ffn_moe_topk` row: all eight slots printed, no ellipsis, `slots_truncated: false`. This is what the R2C patch buys and it is the reason this capability is possible at all |

Both transcripts are working files, not checked-in fixtures. They are evidence for this design; the
capability captures its own.

### 2.2 Probe 1 — a decode graph does not narrow, so all sixteen layers route

`docs/specs/r5e-moe-model-prefill.md` section 2.2 located OLMoE's prefill narrowing: a pair of
`GET_ROWS` inside layer 15, after the attention output projection, on both residual branches, so
`ffn_inp-15` onward is `{2048, 1}` while layers 0 to 14 are `{2048, T}`. The consequence it recorded
is that layer 15's routed union is exactly 8, which alone moves the whole-model residency figure by
2.1 points.

Measured across all nine graphs of the two transcripts:

| Graph | `ffn_moe_topk-L` token rows, layers 0–14 | layer 15 | slots |
| --- | --- | --- | --- |
| A, prefill | 7 | **1** | 8 |
| A, decode 1–4 | 1 | **1** | 8 |
| B, prefill | 5 | **1** | 8 |
| B, decode 1–3 | 1 | **1** | 8 |

**In a decode graph the narrowing is a no-op and nothing is dropped.** Layer 15's routing row is
present, is the same shape as every other layer's, and carries eight real ids. Three consequences,
and each of them changes a rule inherited from a predecessor:

1. **R5E's `narrow_layer` / `narrow_index` selection fields are `N/A` for a decode graph** — there is
   no narrowing to report. Section 3.10 publishes `-1` for both rather than omitting them, so the
   field's absence is never confused with a value of zero.
2. **R2A's token-reduced-tail exclusion does not apply.** That rule discards a layer whose router
   token extent disagrees with the graph's token count, and it is why the R2A parser attributes
   **zero** selections to prefill layer 15 — measured directly: transcript A's parsed selection
   counts are `{0: 56, …, 14: 56, 15: 0}` for the prefill and `{0: 8, …, 15: 8}` for every decode
   graph. In a decode graph extent and count are both 1, so the rule never fires and **all sixteen
   layers are compared**. Section 4's routing oracle compares `16 × 8 = 128` ids per step where R5E
   compared 15 layers' worth plus a discarded tail.
3. **The per-step routed union is exactly `n_layer × n_expert_used` keys**, because `ARGSORT` over 64
   yields eight *distinct* indices and there is one token. It cannot be 127 and it cannot be 129.
   That is a structural oracle, not a measurement, and section 4 uses it as one.

### 2.3 Probe 2 — the per-step expert demand is a constant, and it is 125,000 ppm exactly

`docs/specs/r5e-moe-model-prefill.md` section 2.9 publishes the per-layer expert-byte table: eight
layers (0, 1, 4, 7, 10, 13, 14, 15) whose `ffn_down_exps` is Q6_K contribute 261,095,424 B each, and
the eight Q4_K layers contribute 226,492,416 B each, summing to the published 3,900,702,720 B. One
expert's three planes are that layer's total over 64 — 4,079,616 B in a Q6_K layer, 3,538,944 B in a
Q4_K layer.

With probe 1's result, a decode step claims exactly eight experts in every layer, so:

```text
step expert bytes = Σ_L 8 · (layer_expert_bytes(L) / 64)
                  = (Σ_L layer_expert_bytes(L)) / 8
                  = 3,900,702,720 / 8
                  = 487,587,840 B          =  125,000 ppm of the model's expert bytes, exactly
```

**Verified on all seven decode graphs of both transcripts: 128 keys per step, every time.** The
number does not depend on the prompt, the step index, the position, or the mix of Q4_K and Q6_K
layers — the eighth of each layer is taken from each layer separately and the ratio survives the sum.

**And it is already in the repository, which is why this document claims exactness rather than
novelty.** `docs/specs/r3-residency-sim.md` section 8.1 publishes
`one_token_working_set` = 128 keys = **487,587,840 B** for the `decode_only` and `decode_head4`
arms, against 120 keys / 454,950,912 B for `mixed` and `prefill_only` — the difference being exactly
probe 1's layer-15 result, sixteen routing layers against fifteen. The two derivations agree to the
byte.

Against the prefill this is a sharp fall and a sharp rise at once, and both readings belong in the
gate table rather than in a footnote:

| Quantity | Prefill, `T = 6` (R5E) | Prefill, `T = 7` (transcript A) | One decode step |
| --- | --- | --- | --- |
| distinct `(layer, expert)` keys | 343 of 1,024 | 366 of 1,024 | **128 of 1,024** |
| expert bytes | 1,301,446,656 | 1,390,411,776 | **487,587,840** |
| ppm of expert bytes | 333,644 | 356,452 | **125,000** |
| ppm **per token** | 55,607 | 50,922 | **125,000** |

**Per token, a decode step costs 2.3× to 2.5× what a prefill token costs**, because a prefill amortizes
one expert read over every token that selected it and a decode step has one token to amortize over.
That is the arithmetic behind R3 section 8's "the intervention is decode" stated in bytes, and it is
the first time this repository states it in bytes.

### 2.4 Probe 3 — the cross-step union, which is the number the capability exists to produce

Per-step demand is a constant; the *union* is not, and it is where a residency policy lives. Measured
over both transcripts, keys are `(layer, expert)` pairs and bytes are that layer's per-expert plane
triple:

**Transcript A — prompt `1545,823,9,66,13,270,2262`, `T = 7`, four decode steps:**

| After | distinct keys | cumulative expert bytes | ppm | new keys this step | new bytes this step |
| --- | --- | --- | --- | --- | --- |
| prefill | 366 | 1,390,411,776 | 356,452 | — | — |
| step 1 | 386 | 1,468,219,392 | 376,398 | 20 | 77,807,616 |
| step 2 | 391 | 1,486,995,456 | 381,211 | 5 | 18,776,064 |
| step 3 | 409 | 1,556,103,168 | 398,929 | 18 | 69,107,712 |
| step 4 | 421 | 1,602,355,200 | 410,786 | 12 | 46,252,032 |

**Transcript B — a second prompt, `T = 5`, three decode steps:**

| After | distinct keys | cumulative expert bytes | ppm | new keys | new bytes |
| --- | --- | --- | --- | --- | --- |
| prefill | 319 | 1,208,942,592 | 309,929 | — | — |
| step 1 | 343 | 1,303,068,672 | 334,061 | 24 | 94,126,080 |
| step 2 | 351 | 1,334,083,584 | 342,011 | 8 | 31,014,912 |
| step 3 | 369 | 1,403,731,968 | 359,865 | 18 | 69,648,384 |

Four readings, and every one of them is a design input:

1. **A streaming decode step reads 9.2× what an oracle-perfect cache would read.** Transcript A's
   mean marginal cost is `(77.8 + 18.8 + 69.1 + 46.3) / 4 = 53.0` MB against a 487.6 MB streamed
   demand; transcript B's is 64.9 MB, a 7.5× gap. **That ratio is the whole case for a decode-side
   residency policy**, and it is the first measurement of it on a real routed model.
2. **Roughly four fifths of every decode demand is already in the prefill's union** — 79.9 % on
   transcript A (219 of 274 decode-only keys), 75.2 % on transcript B (152 of 202). This is the
   mechanism behind `docs/specs/r3-residency-sim.md` section 8's otherwise surprising finding that a
   `prefill_only` policy *beats* LRU at a 25 % budget: the prefill's working set is not a warm-up for
   the decode's, it very nearly **is** the decode's.
3. **Step-to-step overlap is high and decays, and the decay is the finding.** Transcript A: 695, 609,
   484 per mille over consecutive steps. Transcript B: 695, 664. A policy whose window is one step
   wide captures most of the reuse *early*; whether it still does at step 16 is exactly what this
   capability measures and what three or four steps cannot say.
4. **Decode-only union over four steps is 274 of 1,024 keys — 26.8 %, against 512 demands**, or 465
   per mille of union-based reuse `(demands − distinct) / demands` over the whole window. This is a
   **different quantity** from the adjacent-pair figure in reading 3 and from R2D's, and section 2.5
   separates all three by name rather than letting three numbers near 450 read as one result.

### 2.5 Probe 4 — three reuse numbers near 450, and why they are three quantities

Three figures in this repository sit between 447 and 465 per mille, and a reader who treats them as
one measurement will draw a conclusion none of them supports. They are separated here, once.

| Figure | Where | What it counts | Denominator |
| --- | --- | --- | --- |
| **447** | `docs/specs/r2a-expert-trace.md` section 9 (R2D-DECODE-LOCALITY-GATE) | For each **adjacent decode position pair** in one `(document, layer)` chain, per router slot: was the later position's expert in the earlier position's top-8? | 9,600 pairs × 8 slots = **76,800 slot trials**, pooled over 40 prompts × 16 steps × 16 layers |
| **695 / 609 / 484** | section 2.4, reading 3 | The same adjacent-pair quantity, but on **one prompt** and aggregated over the sixteen layers, at steps 1→2, 2→3, 3→4 | 128 keys per step |
| **465** | section 2.4, reading 4 | **Union**-based reuse over a four-step window: `(512 demands − 274 distinct) / 512`, where `distinct` is the cardinality of the **decode steps' own** key set and the prefill's set is no part of it | 512 demands |

**A fourth quantity exists, is not any of these three, and shipped once under the third's name.**
`(demands − |decode keys the prefill did not already hold|) / demands` is *prefill-relative* reuse:
it asks how much of decode demand the cache would serve if the prefill's working set were already
resident, and on transcript A it is `(512 − 55) / 512 = 892` where the union quantity is 465. The
first implementation of `residency.step_reuse_per_mille` computed exactly that and published it
under section 3.11's name, and section 13 deviation 13 records the correction. The distinction is
the whole reason this section exists: **`distinct` is a decode-side cardinality and says nothing
about the prefill.** The prefill relationship is published separately, twice, by
`residency.decode_keys_in_prefill_union` and `residency.decode_distinct_keys_in_prefill_union`.

**The 447 and the 695/609/484 are the same quantity at different scopes, and they agree.** R2D pools
sixteen steps and forty prompts; this probe reports the first three transitions of one prompt and
sees them decay toward R2D's pooled mean. That agreement is worth having and it is worth stating that
it is agreement rather than corroboration by a second method.

**What is *not* a cross-step number, and would be easy to mistake for one.** The `locality` object the
R2A parser writes into `patched-n4.json` reports an aggregate `reuse_per_mille` of 454 with
`phase_split.decode: adjacent_pair_count 0, reuse_* null`. That field is R2A's original
**within-graph** token-adjacency metric, and a decode graph with one token has no adjacent pairs at
all, so its 454 is entirely the prefill's. R2D's 447 comes from a different aggregator
(`scripts/expert_locality_gate.py`, `aggregate_decode`) which orders one chain per `(document, layer)`
by `(graph ordinal, token index)` and pairs consecutive *positions across graphs*. Both are correct
about different things; only the second is a decode-step quantity.

**And the union figure is a third thing with no owner today.** Neither R2A nor R2D publishes a
cumulative distinct-key set or its byte curve, and R3 section 8 publishes policy bytes pooled over
prompts rather than a per-prompt union. Section 3.11 defines
`residency.union_bytes_final` and the per-step `new_bytes` curve as this capability's own metrics and
records that they are new rather than inherited.

### 2.6 What the probes settle, and what they leave

| Question | Settled by | Answer |
| --- | --- | --- |
| Does the last-layer token reduction occur in a decode graph? | 2.2 | **No.** All sixteen layers route, all eight slots print |
| Does R5D's one-token 12.5 % claim hold per step? | 2.2, 2.3 | **Yes, structurally and exactly**: 125,000 ppm, prompt- and step-independent |
| Does it hold over sixteen steps? | 2.3 | **Yes for the per-step demand**, which is why the per-step figure is a structural oracle rather than the result |
| What is the cumulative demand over sixteen steps? | **not settled** | Four steps reach 410,786 ppm on one prompt. Sixteen is the capability's measurement |
| Can routing identity be checked per step, at full width? | 2.1, 2.2 | **Yes**, 8 of 8 slots on 16 of 16 layers — better than R5E, which compared 546 of 728 prefill ids |
| Are the decoded ids exposed by the instrument? | 2.1 | **No.** Gate G's `embd` fingerprint is required, exactly as R6-STEP-N found for the dense model, and OLMoE's injectivity must be re-measured (section 4.2) |
| Is `token_embd.weight` fingerprint-injective on OLMoE? | **not settled** | 50,304 rows of 2,048 against Qwen2's 152,064 of 3,584. Cell G-P1, section 5.7 |
| Is the single-shot self-reference byte-identical across two stack shapes? | **not settled** | Cell C-P1, section 5.7. Section 4.4 fixes the fallback in advance |

## 3. Public-contract ledger

Every field marked `N/A` carries its reason. Rows the four predecessor documents settled are restated
only when they change.

### 3.1 The surface decision — a new arm, not a dispatch inside `--decode-step`

Both candidates were examined against the shipped code, not against a preference.

**What `--decode-step` does with an OLMoE geometry today.** It refuses it, deliberately and by name.
`layer_qwen2.parse_geometry` checks `n_expert != 0` **before** it checks the `arch` string
(`src/layer_qwen2.align:354-369`), and `decode_step.stage_inputs` re-labels exactly that case
(`src/decode_step.align:1763-1773`), whose comment reads *"OLMoE is a declared non-goal of section
1.3 and it deserves a code that says so"*. The result is `error_code: "R6_ARCH_UNSUPPORTED"`,
`error_detail: "n_expert"`.

| Consideration | `--moe-decode-step`, new module (**chosen**) | Architecture dispatch inside `--decode-step` |
| --- | --- | --- |
| The geometry type | `layer_olmoe.Geometry` carries `n_expert`, `n_expert_used`, `n_ff_exp`; `layer_qwen2.Geometry` carries `n_ff` and no routing fields. Two types, two `parse_geometry`s | One arm would need a union type or two whole staging paths behind one flag. At this pin that is two arms wearing one name |
| The op vocabulary | `layer_olmoe` numbers `OP_ARGSORT 12, OP_MUL_MAT_ID 13, OP_VIEW_2D 14, OP_PAD 15`; `layer_qwen2` numbers `OP_SWIGLU 11, OP_PAD 12, OP_CONCAT 16`. The two node walkers dispatch different integers to different symbols | `build_decode_nodes` would branch on architecture inside every row |
| The four write-back rows | `PREFILL_K_ROW 12`, `PREFILL_V_ROW 10`, `DECODE_K_CONCAT_ROW 16`, `DECODE_V_CONCAT_ROW 22` are **qwen2 table indices** (`src/decode_step.align:804-807`) and must be re-derived by reading the OLMoE table | Four constants become four pairs, selected at run time, in the one place a wrong index writes a plane column into the wrong tensor |
| The window model | Dense: one window sized by the head. Routed: **two** windows, a dense one and a claim one whose size is a function of `n_expert_used` and `T` | The `Plan`/`Ends` records and `plan_resident` do not describe a claim window |
| **Golden and identity impact** | A new kind `R6_MOE_DECODE_STEP` at `schema_version: 1` and a new `scripts/moe-decode-step-golden.jsonl`. **Zero existing golden rows move** | Publishing `n_expert`, `n_expert_used`, `routed[]`, and the expert-byte counters inside `R6_DECODE_STEP` bumps it **4 → 5** and rewrites all 116 rows of the dense golden for a capability that changes no dense behaviour |
| The `akvp` container | Out of scope here, so no interaction | The header's `document_schema_version` (offset 136, frozen at 3, contract "the `R6_DECODE_STEP` schema this writer emits") would silently start meaning two different documents |
| The existing refusal | Stays **byte-unchanged** and acquires a documented meaning: *use `--moe-decode-step`*. `docs/align-development.md` records it | The refusal is deleted, and with it the only test that proves the dense arm knows what it cannot do |
| Cost | One `if` and one import in `src/ggml_spike.align` (the dispatch ladder at `:1569-1616` is flat and ordered, with `--moe-model-forward` already sitting immediately above `--decode-step`), one new module, one new golden | Smaller diff, larger blast radius |

**The precedent is unambiguous and it is followed rather than re-argued.** `--moe-layer-forward` sits
beside `--layer-forward` and `--moe-model-forward` beside `--model-forward`, each with its own
module, its own document kind, and its own golden. `--moe-decode-step` beside `--decode-step` is the
third instance of one rule, not a new rule.

**What the choice costs, stated rather than absorbed.** Align Request 49 forbids a cross-module call
that takes a `borrow mut` argument beside a shorter-lived operand, and that request's own
`align-llm verification` block already names the nine functions `src/decode_step.align` duplicates
for it — `fail`, `fault_into`, `pack_fault_into`, `take`, `take_pack`, `account`, `check_types`,
`top_k`, `compare_prefill_logits`. **A tenth module means a third copy of that sink**, and section 13
deviation 16 records what the count actually came to: **36** of this module's 91 functions share a
name with a sibling module's and take a `borrow mut` parameter, which is Request 49's own shape.
There is **no** duplicated `refill`, and the design's prediction of one was wrong for a good reason —
KV persistence is out of this capability's scope, so the plane is never refilled from a container and
`src/kv_plane.align`'s split is not met here at all. Section 9 records this as Request 49's newest
and largest client with the regenerated list, and does not build a workaround around it.

### 3.2 The arm and its operands

| Field | Contract |
| --- | --- |
| Surface | `ggml-spike --moe-decode-step` — the first operand and nothing else selects the arm, inserted **above** `src/ggml_spike.align`'s `--*` catch-all or the flag becomes `Err(Error.Invalid)` before it is read |
| Owner module | `src/moe_decode_step.align`, new. `src/ggml_spike.align` gains one `import` and one `if` |
| Operand grammar | `--moe-decode-step PACK GEOMETRY TOKENS DOCUMENT REFERENCE TRANSCRIPT KV_WIDTH LOGITS STEPS` |
| Positions | `args[2] .. args[10]`, **identical to `--decode-step`'s first nine operands, position for position** |
| Arity | `args.len()` of 5, 6, 7, 9, 10, or 11. **8 is `R6M_ARITY`**, inherited from R6's reason — a transcript without a width refuses itself. **12 and above are `R6M_ARITY`**, and positions 11, 12, and 13 are **reserved** for `KV_SAVE`, `KV_LOAD`, and `RESIDENT` at the same indices the dense arm uses, so the capability that adds them renumbers nothing |
| Why not `--moe-model-forward`'s order | That arm promotes `KV_WIDTH` to operand five because R5B left it optional and R5E had to make it mandatory (`docs/specs/r5e-moe-model-prefill.md` section 3.3). `--decode-step`'s `KV_WIDTH` is **already** mandatory and fail-closed, so R5E's substantive point is satisfied at position seven and only the position would differ. Matching `--decode-step` instead lets `scripts/run-moe-decode-step` build its argument vector with the dense runner's code and stops a reader from silently reordering a command line between two arms that decode |
| What a mis-ordered command line does | Refuses. `--decode-step`'s order applied to this arm is the same order; `--moe-model-forward`'s order applied to it puts a path where `KV_WIDTH` is parsed and fails `R5_KV_WIDTH` before any allocation |
| `PACK`, `GEOMETRY`, `DOCUMENT`, `REFERENCE`, `TRANSCRIPT`, `LOGITS` | `docs/specs/r6-decode-kv-step1.md` section 2.1 and R6-STEP-N section 2.2, verbatim. `DOCUMENT` accepts `-` (stdout); `TRANSCRIPT` and `LOGITS` accept `-` (that oracle does not run); `REFERENCE` has no `-` form |
| `TOKENS` | 1 to `layer_olmoe.MAX_PREFILL_TOKENS` comma-separated ids, each `< n_vocab`. `R6M_TOKENS` otherwise. Section 3.8 moves the cap |
| `KV_WIDTH` | `args[8]`. Fail-closed, no default. `T + N <= KV_WIDTH <= layer_olmoe.MAX_ATTENTION_WIDTH` (4096). `R6M_KV_WIDTH` otherwise |
| `STEPS` | `args[10]`, decimal `N`. **Absent means 1**, the one default, closed the way R6-STEP-N closed it: `decode.steps_requested` is published in **every** document including error documents, so the count is never implicit |
| `MAX_DECODE_STEPS` | New in `src/layer_olmoe.align`, value **64**, for R6-STEP-N section 2.3's reason unchanged. `R6M_STEPS` above it |
| Refusal precedence | `R6M_STEPS` (parse and cap) before `R6M_KV_WIDTH` (plane bound), because `N` must be a number before `T + N` is one. R6-STEP-N section 2.3, unchanged |

**Codes are prefixed `R6M_` and not `R6_`**, so a document from this arm can never be confused with
one from the dense arm by grepping a code, and so the two arms' refusal corpora can share one smoke
file without either shadowing the other. Codes raised by re-used R5 seams (`R5_COMPUTE`,
`R5_GGML_INIT`, `R5_ORACLE_SHAPE`, `R5_KV_WIDTH` inside the shared reader) keep their names, exactly
as R6-STEP-N section 2.7 keeps them: a seam code that changes name by the arm that raised it is two
names for one condition.

### 3.3 Hyperparameters and geometry

`layer_olmoe.parse_geometry` is the owner and is **byte-unchanged**: it already refuses
`arch != "olmoe"`, `n_expert < 1`, `n_head != n_head_kv`, an out-of-range `n_expert_used`, and a
node-slot budget above `MAX_NODE_SLOTS`. On this model, from
`docs/specs/r5e-moe-model-prefill.md` section 5.2:

```text
arch olmoe   n_layer 16   n_embd 2048   n_head 16   n_head_kv 16   head_dim 128
n_ff_exp 1024   n_vocab 50304   n_expert 64   n_expert_used 8   context_length 4096
rms_eps_bits 3727c5ac   rope_type 2   rope_dim_count 128   rope_freq_base_bits 461c4000
attn_scale_bits 3db504f3   output_tied false   output_ggml_type 14
```

`n_head == n_head_kv` — OLMoE is MHA, not GQA. Section 3.4 is where that costs something.

### 3.4 The KV plane for OLMoE — the layout applies unchanged, the size does not

**The layout is architecture-free and is reused without a single change.**
`src/decode_step.align:515-536` defines it as layer-major, then tensor, then column, with
`plane_stride = KV_WIDTH · n_head_kv · head_dim · 4`, K at `stride · 2l` and V at
`stride · (2l+1)`, and within a tensor exactly ggml's order for a
`{head_dim, n_head_kv, KV_WIDTH}` f32 tensor. Nothing in it names an architecture, a rope type, or a
norm. `plane_stride`, `plane_bytes_for`, `plane_k_offset`, `plane_v_offset`, `plane_column_bytes`,
`stage_past_k`, `stage_past_v`, `compare_past_k`, `compare_past_v`, and `refill` take raw integers
or are coupled only through the `Geometry` **type**, not its semantics; they are re-typed on
`layer_olmoe.Geometry` and their bodies do not move.

**QK-norm does not reach the plane, and the reason is where it sits.** OLMoE applies `attn_q_norm`
and `attn_k_norm` to the **2-D projection**, before the reshape to `{head_dim, n_head, T}`, and the
reshape is followed by RoPE: `RMS_NORM` and `MUL` at rows 7 and 8 of `mm_a_node_table`, the
`RESHAPE_3D` after them, and `ROPE` after that (`src/layer_olmoe.align:1825-1845`). Either way the K
a layer hands the cache is post-norm and post-RoPE — the same kind of tensor the dense arm caches, at
the same shape — so the conclusion below is unaffected; the ordering above is the shipped one, and
section 13 deviation 15 records that this sentence said "after the reshape" before it was checked
against the table. The plane therefore stores exactly what it stores today and needs no marker for the
norm. **What must be re-derived, by reading the OLMoE decode table rather than by assuming, is the
row index of that post-RoPE K and of the reshaped V**, because
`PREFILL_K_ROW := 12` / `PREFILL_V_ROW := 10` / `DECODE_K_CONCAT_ROW := 16` /
`DECODE_V_CONCAT_ROW := 22` are qwen2 table indices whose comment
(`src/decode_step.align:794-802`) says so. Section 5.2 makes deriving them a named cell with its own
regression, and section 7 risk 2 records what a wrong one costs.

**The size is where MHA is paid for:**

| Quantity | Qwen2.5-Coder-7B Q4_K_M | OLMoE-1B-7B Q4_K_M |
| --- | --- | --- |
| `n_layer` / `n_head_kv` / `head_dim` | 28 / 4 / 128 | 16 / **16** / 128 |
| `plane_column_bytes` (one layer, one tensor) | 2,048 | **8,192** |
| bytes per column, all layers, K and V | 114,688 | **262,144** |
| `plane.bytes` at `KV_WIDTH` 256 | 29,360,128 | **67,108,864** |
| `plane.bytes` at `KV_WIDTH` 2048 | 234,881,024 | 536,870,912 |

**2.29× the dense arm's plane on a model with a fifth of its parameters**, because sixteen KV heads
against four beat sixteen layers against twenty-eight. `MAX_PLANE_BYTES` (8 GiB,
`src/decode_step.align:85`) is untouched at any legal width. The qualification runs at
`KV_WIDTH` 256 and 67,108,864 B, which is section 6's memory line.

**Container identity — the `akvp` header already covers OLMoE, and persistence is still deferred.**
Asked directly whether the geometry SHA covers the architecture: **yes.** `DIGEST_GEOMETRY` is
`crypto.sha256` over the exact bytes of the `GEOMETRY` file, which is an `R1_MODEL_IR` document
carrying `model.arch`, `n_expert`, `n_head_kv`, `head_dim`, and the rope block, so a qwen2 container
cannot be loaded against an OLMoE geometry — it fails `R6_KV_IDENTITY("geometry")` at L10. The
header additionally carries `n_layer`, `n_head_kv`, `head_dim`, and `kv_width` as plain `u32`s
checked field-by-field at L8. **No new identity field is needed and no `plane_layout_version` bump
is warranted.** Two couplings block reuse anyway and are the reason section 1.4 defers persistence
rather than taking it cheaply:

1. `src/kv_plane.align:519` bounds the header's `token_count` by `layer_qwen2.MAX_PREFILL_TOKENS`
   — the single qwen2 dependency in the format module — and OLMoE's cap is a different number
   (section 3.8).
2. The header's `document_schema_version` at offset 136 is frozen at 3 and means "the
   `R6_DECODE_STEP` schema this writer emits". An arm emitting `R6_MOE_DECODE_STEP` needs a
   `document_kind` field, which is an `akvp` v2.

Section 8 records both with these exact locations.

### 3.5 What `T = 1` changes — the R5D and R5E rows that move

`docs/specs/r5d-moe-layer-forward.md`'s routed-FFN contract is inherited whole: the router's
`SOFT_MAX` over `n_expert`, the `ARGSORT` and the `VIEW` that takes the first `n_expert_used`
indices, **no renormalisation of the selected weights**, the compact expert stack of exactly the
claimed planes in **ascending slot order**, and `mul_mat_id` against it. What changes is only what
`T` multiplies.

| Row | Prefill, `T` tokens | Decode step, `T = 1` |
| --- | --- | --- |
| `ffn_moe_logits-L`, `ffn_moe_probs-L`, `ffn_moe_argsort-L` | `{n_expert, T_out}` | `{64, 1}` in **every** layer |
| `ffn_moe_topk-L` | `{n_expert_used, T_out}` | `{8, 1}` in every layer |
| `ffn_moe_weights-L` | `{1, n_expert_used, T_out}` | `{1, 8, 1}` |
| `ffn_moe_gate/up/swiglu-L` | `{n_ff_exp, n_expert_used, T_out}` | `{1024, 8, 1}` |
| `ffn_moe_down/weighted-L` | `{n_embd, n_expert_used, T_out}` | `{2048, 8, 1}` |
| The narrowing (`T_in` > `T_out` at the narrow layer) | layer 15 only | **does not occur.** `selection.narrow_layer` and `narrow_index` publish `-1` (section 2.2) |
| Routed union `U_L` | prompt-dependent, 8 to 33 measured | **exactly 8, every layer, every step** (section 2.2) |
| `U_max = min(n_expert, n_expert_used · T)` | 48 at `T = 6` | **8** |
| `window.claim_bytes` | 195,821,568 at `U_max` 48 | see section 3.6 |
| The reduction chain's row count | `2 · n_expert_used + 8`, unchanged | unchanged — it depends on `n_expert_used`, not on `T` |
| `mm_row_issued(condition, last, wide)` | three axes | **needs a fourth, `decode`** — section 3.7 |

**Nothing in the routing arithmetic is `T`-conditional, and that is the finding.** The rows above
change *shape*, not *kind*. The claim-resolution code — read the router logits, softmax, argsort,
take the first eight, sort the eight into ascending slot order, resolve each to a `(layer, expert)`
block, read its three planes into the claim window, and build the `ids` tensor `mul_mat_id` indexes
with — is R5D's, unchanged, evaluated once per layer per step instead of once per layer.

### 3.6 The claim window at `T = 1`, and a deferral that closes itself

`docs/specs/r5e-moe-model-prefill.md` section 5.4 defers "a claim window that shrinks to the routing
decision" to R6, with 195,821,568 B reserved against a 101,990,400 B measured peak as the cost. At
`T = 1` the arithmetic bound **is** the decision: `U_max = min(64, 8 · 1) = 8`, and

```text
claim window, decode-only = 8 · (1,179,648 + 1,179,648 + 1,720,320) = 32,636,928 B
```

which is exactly R5E's measured layer-15 claim bytes, because layer 15 of a prefill *is* a one-token
routing decision. **The deferral closes itself at `T = 1` and does not close in general**, and this
document says which:

| Field | Contract |
| --- | --- |
| Sizing rule | One window for the whole run, reserved once, before any read, at `U_max = min(n_expert, n_expert_used · T)` where `T` is the **prefill** token count. `8 <= 8T` for every legal `T`, so one reservation covers the prefill and every decode step |
| On this model at `T = 6` | 195,821,568 B reserved; prefill peak use 101,990,400 B; **every decode step's peak use is 32,636,928 B** at a Q6_K layer and 28,311,552 B at a Q4_K layer |
| Published | `window.claim_bytes`, `window.claim_u_max`, `window.claim_peak_use_bytes`, `window.claim_peak_use_layer` (R5E's fields, unchanged) plus **`window.claim_decode_peak_use_bytes`**, new, the maximum over decode steps only. Without it the run's peak is the prefill's and the decode figure — the one a residency policy needs — is unpublished |
| Why not a second, smaller window for the decode phase | A second window is a second lifetime, a second alignment argument, a second budget refusal, and a second set of counters, for a run whose peak is the prefill's either way. `docs/specs/r5b-model-prefill-forward.md` section 3.5's three reasons, unchanged, and the slack is a published field rather than a paragraph |
| Budget refusal | `R5D_CLAIM_BUDGET` above `MAX_CLAIM_WINDOW_BYTES`, before a byte is reserved. Unchanged |
| Dense window | 84,520,960 B, sized by the head, unchanged from R5E |
| Peak resident weight bytes | 280,342,528 B (both windows), unchanged from R5E, **plus the 67,108,864 B plane** = 347,451,392 B, against a 4,212,193,280 B container — 8.2 % |

### 3.7 The one genuinely missing mechanism — a decode condition in `src/layer_olmoe.align`

Everything else this capability needs exists. This does not, and it is named rather than discovered:

| Needed | State |
| --- | --- |
| A new ggml op or FFI symbol | **None.** `ggml_ffi.op_concat` already ships (`src/ggml_ffi.align:898`) and is what the dense decode arm uses |
| A new shim entry point | **None** |
| A new Align language surface | **None.** Section 9 records four continuing gaps; none blocks |
| `OP_CONCAT` in the OLMoE op vocabulary | **Missing.** `layer_olmoe` numbers ops to `OP_PAD := 15` and has no concat. New constant, next free number. `ggml_ffi.op_concat` needs no change |
| A `WHEN_DECODE` condition | **Missing.** `layer_qwen2` has `WHEN_DECODE := 4` consumed by `mf_row_issued_at(condition, last, wide, decode)`; `layer_olmoe`'s `mm_row_issued(condition, last, wide)` has three axes and no decode one |
| A decode layer node table | **Missing.** `layer_qwen2.mf_decode_layer_node_table(g, n_past, width)` has no OLMoE counterpart |
| Past-K / past-V slots | **Missing.** See the slot budget below |

**`WHEN_WIDE` cannot be reused for the KV concatenation, and this is the trap the design has to name
before implementation rather than discover during it.** `WHEN_WIDE` is a *reconciliation-width*
device: rows 16 and 17 of `mm_a_node_table` make K contiguous and then `ggml_pad` it to `KV_WIDTH`,
row 22 does the same for the transposed V, and rows 18 and 23 swap their `a` operand to the padded
one — all conditioned on `wide := width > tokens.count`. `ggml_pad` **writes the source at the start
of each padded axis and zeroes the rest**. At `T = 1` over a plane, `width = KV_WIDTH > 1` is always
true, so those rows would fire and put the step's single new column at index **0** with zeros above
it — precisely the wrong place, because the plane's columns must occupy `[0, n_past)` and the new
column `n_past`. **A decode topology is a new condition and two `CONCAT` rows, not a reuse of
`WHEN_WIDE`.**

| Table | Rows | Shape |
| --- | --- | --- |
| `mm_a_node_table` (prefill) | `MM_A_NODE_COUNT` = 35 | unchanged |
| `mm_decode_a_node_table(g, n_past, width)` (new) | **37**, to be verified and published as `graph.table_rows_a_decode` | the prefill table at `T = 1`, with the post-RoPE K and the reshaped V each concatenated against the uploaded past along their own axis, and the existing `PAD` then widening `n_past + 1` to `KV_WIDTH` under a `wide` that now means `width > n_past + 1` |
| `mm_b_node_table` (both) | `2·n_expert_used + 8` | **unchanged.** Phase B never saw `T` except through three `p` parameters, and it already runs at `t_out = 1` today, at layer 15 of every prefill |

**The slot budget, re-derived rather than inherited.** `layer_qwen2` puts past-K and past-V at 64/65
so the prefill arm's `slot_high_water` stays 52 and no golden moves. OLMoE's map is different:
`MM_A_NODE_BASE := 21` with 35 rows occupies 21–55, `MM_B_NODE_BASE := 56` with `2u + 8` rows occupies
56 upward, and R5E's measured high water is 80 of `MAX_NODE_SLOTS := 128`. A fixed pair just above 80
would collide with phase B at `n_expert_used >= 13`. **The pair therefore takes the top two slots,
`MAX_NODE_SLOTS - 2` and `MAX_NODE_SLOTS - 1`**, and `stage_geometry`'s existing ceiling tightens by
two — `MM_B_NODE_BASE + b_node_count(n_expert_used) <= MAX_NODE_SLOTS - 2`, so `n_expert_used <= 31`
against R5E's 32 — refused as `R5_GEOMETRY` detail `n_expert_used`, naming the field exactly as R5E's
does rather than reaching the node walk. The decode arm's `slot_high_water` is published, not assumed.

**The write-back's ordering invariant is R6-STEP-N section 2.4's, unchanged and restated because it
now has to hold across a two-phase graph.** Within step `k`'s layer graph, in this order: (1) before
compute, the plane's columns `0 .. n_past-1` are a `slot_set` **source**; (2) compute — phase A, the
routing decision, the claim reads, phase B; (3) after compute, the plane's column `n_past` and only
that column is a `slot_get` **destination**. The two byte ranges are disjoint by construction and
separated by a completed compute. **The claim reads land between (1) and (3) and touch the claim
window, never the plane**, which is why the two-phase shape does not weaken the invariant — and
section 5 has a cell that says so with a regression rather than a sentence.

### 3.8 `MAX_PREFILL_TOKENS` for OLMoE — 6 to 32, and every consumer

| Field | Contract |
| --- | --- |
| Today | `src/layer_olmoe.align:67`, value **6** |
| Change | **6 → 32** |
| Why it must move | Oracle C′ (section 4.4) runs `--moe-model-forward` at `TOKENS,d_1..d_k`, which is `T + k` tokens. At the qualification's `T <= 6` and `N = 16` the last checkpoint is **22 tokens**, and the arm would refuse its own oracle at 6 |
| Why 32 | The smallest power of two above 22, with headroom, and **the same value `layer_qwen2.MAX_PREFILL_TOKENS` already holds** — two architectures with two different caps is a difference with no reason behind it, and `src/kv_plane.align:519` (section 3.4) would have to choose one of them if persistence is ever taken |
| Why the cap's original reason survives | The cap is the **oracle's**, not the arithmetic's: `llama-eval-callback` prints every row of an axis only while its extent is `<= 6`. R5E ships `R5_ORACLE_TRUNCATED`, raised when `transcript_present && tokens.count > TRUNCATION_PRINTED` (6), and that refusal is **byte-unchanged** and still fires at 7. The range 7..32 is open for arithmetic and closed for comparison, at 32 exactly as at 6 |
| Why this arm is unaffected by its own cap | A decode graph's router axes are `{·, 1}` and print in full at any `T`; the arm's prefill graph is compared only at `T <= 6`, which the qualification uses |

**Every consumer of `layer_olmoe.MAX_PREFILL_TOKENS`, enumerated so the lift is a change with a
known blast radius:**

| Site | Use | Effect of the lift |
| --- | --- | --- |
| `src/moe_layer_forward.align:343` | `parse_tokens` — the single token-count gate for `--moe-layer-forward` **and** `--moe-model-forward`, which imports it | Both arms accept 7..32 tokens **without a transcript**; with one, `R5_ORACLE_TRUNCATED` refuses at 7 exactly as today |
| `src/moe_decode_step.align` | this arm's `TOKENS` bound | the point of the lift |
| `src/kv_plane.align:519` | reads `layer_qwen2`'s, not this one | unaffected; recorded because it is the coupling section 3.4 defers on |
| `src/model_forward.align:3291` | `plan_resident`'s embed stage, reads `layer_qwen2`'s | unaffected; residency is out of scope |
| golden corpus | three cases assert the cap by name in the MoE smoke blocks | section 6.3 predicts the moved rows |

The lift makes `--moe-layer-forward` and `--moe-model-forward` accept longer prompts than any of
their qualifications use. That is a **widening of a public bound on two arms this capability does not
otherwise touch**, and it is recorded here rather than absorbed: the closure matrix has a cell for
each, the transcript refusal is the guard, and section 7 risk 5 states the residual.

### 3.9 Weights are streamed, and residency is excluded rather than deferred for cost

| Field | Contract |
| --- | --- |
| Mode | **Streamed, always.** There is no `RESIDENT` operand and position 13 is reserved |
| Why | `docs/specs/r6-resident-weights.md` section 3.5 defines `weights.step_pack_bytes` as "pack bytes read by decode steps only" and makes it **exactly 0** in resident mode. This capability's primary metric is the expert bytes a decode step reads. **An arm that is both resident and measuring reads zero and has measured nothing** |
| The two are not orderable the other way | A partial-residency policy needs to know *which* keys to hold. That is the demand stream this capability produces. Measuring first is not a preference, it is the dependency |
| Per-step pack bytes, predicted | 487,587,840 expert + 168,558,592 dense layers + 84,518,912 head + 1,152 embedding row = **740,666,496 B**, of which the experts are 65.8 % |
| The obvious middle | Dense weights resident, experts streamed — 253 MB of the 740 MB removed per step while the measured quantity stays exact. It is the **first** deferred surface (section 8) with its operand named, and it is not taken here because `model_forward.plan_resident` describes a dense `Plan`/`Ends` with a per-layer constant window, and a routed layer's window is not constant |

### 3.10 The document — `R6_MOE_DECODE_STEP`, `schema_version: 1`

One shape at `N = 1` and at `N = 64`, on success documents and error documents alike. No
conditional-presence rule, no operand-dependent shape. Every float is off the wire: digests are hex
SHA-256 over exact little-endian f32 bytes, tolerances are integer ten-thousandths or millionths,
and every ratio is integer ppm.

| Object | Fields | Provenance |
| --- | --- | --- |
| prologue | `schema_version` (1), `kind`, `pack_path`, `geometry_path`, `reference_path`, `transcript_path`, `logits_path`, `status`, `error_code`, `error_detail`, `verdict`, `pack{format_version, block_align, member_align, block_count, member_count, total_bytes, payload_offset, reader_pread_count, reader_bytes_read}` | `--decode-step`'s, unchanged in shape |
| `model` | R5E's routed block: the fields in section 3.3 **including `n_expert` and `n_expert_used`** | `--moe-model-forward`'s, not `--decode-step`'s. This is the one document-shape difference between the two decode arms and it is the reason a shared kind was rejected |
| `selection` | `embedding_block_index`, `output_block_index`, `expert_block_count`, `attention_width`, and `narrow_layer` / `narrow_index` = **`-1`** on every decode graph | R5E's, with section 2.2's `-1` |
| `plane` | `source`, `bytes`, `stride`, `layers`, `columns_written`, `readback_ns`, `upload_ns`, `roundtrip_verdict`, `roundtrip_bytes_compared`, `first_mismatch_layer`, `first_mismatch_tensor`, `first_mismatch_column`, `first_mismatch_step` | R6-KV-PERSIST's, unchanged |
| `decode` | `steps_requested`, `steps_completed`, `n_past_first`, `n_past_last`, `token_ids[]`, `graph_count`, `node_count`, `slot_high_water`, `compute_ns` | R6-STEP-N's, unchanged. `token_ids[]` is the field gate G reads |
| `steps[]` | one object per **completed** step: `index`, `n_past`, `token_id`, `argmax`, `sha256`, `bit_sum`, `element_count`, `nonfinite_count`, `compute_ns`, `node_count`, `plane_column_written`, `oracle{…}`, **and `routed{…}` and `residency{…}` below** | R6-STEP-N's, extended |
| **`steps[].routed`** | `layers[]` — for each of the 16 layers, the **eight** selected expert ids in ascending slot order — plus `keys_demanded` (128), `union_keys_after` and `union_bytes_after` (cumulative over prefill and every prior step), `new_keys` and `new_bytes` (this step's marginal cost) | **new.** This is the demand stream, and it is the deliverable |
| **`steps[].residency`** | `expert_bytes`, `expert_pread_bytes`, `expert_read_amplification_ppm`, `expert_bytes_ppm` (125,000), `dense_bytes`, `total_bytes`, `claim_planes_read` (384), `claim_peak_use_bytes` | **new**; section 3.11 defines the first three and the relation between them |
| `residency` (run scope) | R5E's `expert_bytes_read`, `expert_bytes_in_model`, `expert_bytes_read_ppm`, `keys_demanded`, `keys_distinct`, `planes_read`, `planes_in_model`, `total_bytes_read`, `model_bytes`, `cumulative_expert_bytes[]`, **plus `prefill_expert_bytes`, `decode_expert_bytes`, `union_keys_final`, `union_bytes_final`, `decode_keys_in_prefill_union`, `step_reuse_per_mille`** | R5E's, extended by section 3.11's two new metrics |
| `window` | R5E's, plus `claim_decode_peak_use_bytes` (section 3.6) | extended |
| `graph`, `head`, `reference`, `oracle_logits`, `timings`, `lifetime`, `abi` | R5E's and R6's, unchanged | — |
| `routing_oracle` | `verdict` (`MATCH`/`MISMATCH`/`-`), `steps_compared`, `layers_matched`, `ids_total`, `ids_printed_compared`, `sums_matched`, `first_mismatch_step`, `first_mismatch_layer`, `first_mismatch_slot` | R5E's, extended by step (section 4.3) |
| `oracle_decode` | R6-STEP-N's per-step transcript aggregate, unchanged in shape | — |
| `kv`, `weights` | **absent.** Persistence and residency are out of scope (section 1.4), and publishing an object that is always `-` is a field pretending to be a promise | — |
| `normalize` | Zeroes every `*_ns`, `steps[i].compute_ns`, `plane.readback_ns`/`upload_ns`, and `first_token_ns` before every golden compare. **`routed`, `residency`, and every `*_bytes` and `*_ppm` field are deterministic and are NOT normalized: they are the claim** | R6-STEP-N section 2.9's rule, with the exemption list stated |

**Per-step failure holds exactly what R6-STEP-N section 2.8 says it holds**, unchanged and
un-restated: `steps_completed = k - 1`, `k - 1` complete `steps[]` objects and no partial one,
`token_ids` of `k - 1` ids, `columns_written = T + k - 1`, aggregates over the published rows and
nothing else, never `IDENTICAL` on an error document, and the plane freed on every path. The one
addition: **`residency` and `routed` aggregate over the `k - 1` completed steps and nothing else**,
for the same reason — a byte count no published row accounts for is a half-filled row wearing a
different name.

### 3.11 Metrics

**No cost ceiling is recorded and no performance claim is made, and that is a deliberate reading of
`CLAUDE.md`'s Performance-claim row rather than an omission.** That row selects when a capability
claims an optimization. This one claims a **measurement**. `docs/specs/r6-resident-weights.md`
section 3.4 is the owner of Track B decode performance and defines the baseline (18.235 s at
`N = 16` on the dense model) and the 150,000 ppm shipping floor; this capability neither spends
against that floor nor moves it. Its elapsed figures are published as **diagnostics** and as the
input the *next* Track B performance capability records its ceiling against.

**The expert-byte figure is measured two ways, on purpose, because R5E's is arithmetic.**
`--moe-model-forward`'s `residency.expert_bytes_read` accumulates
`Σ_role routing.count · plane_bytes[L][role]` — it is computed **from the routing decision and the
container's plane sizes**, not from syscall accounting, and the real counters
(`pack.reader_pread_count` / `reader_bytes_read`) are separate and cover the whole run. That is fine
for a prefill whose claim is "the routing selected this much", and it is **not** enough for a
capability whose claim is "a decode step reads this much": an arm that resolved eight claims and then
read the whole layer would publish the same number. So this capability publishes both and requires a
relation between them, in the shape R5E's own `keys_demanded` / `keys_distinct` pair already uses —
"an equality between one accumulator written twice would be a tautology and would prove nothing":

| Field | Source | Relation |
| --- | --- | --- |
| `steps[i].residency.expert_bytes` | arithmetic, from `decide`'s output and `plan.plane_bytes` | the claim |
| `steps[i].residency.expert_pread_bytes` | **new**: `alignpack_read.Counters.bytes_read` accumulated across the step's `read_block_scatter` calls and nothing else | what the reader actually read |
| `steps[i].residency.expert_read_amplification_ppm` | `(pread_bytes − bytes) · 10^6 / bytes` | **published, not bounded.** `read_block_scatter` reads chunks intersected with the three claim spans, so the excess is the reader's chunk granularity and it is a measurement, not a defect |
| the assertion | `expert_pread_bytes >= expert_bytes` and `expert_pread_bytes <= expert_bytes + claim_planes · block_align` | a fail-closed `R6M_CLAIM_ACCOUNTING` if either side is violated. Neither can hold by construction, so neither is vacuous |

| Metric | Definition | Status | Predicted |
| --- | --- | --- | --- |
| **`steps[i].residency.expert_bytes`** | above | **primary, exact, noise-free** | **487,587,840 B on every step**, `expert_bytes_ppm` 125,000 |
| **`steps[i].residency.expert_pread_bytes`** | above | **primary** | 487,587,840 plus a bounded chunk remainder |
| **`residency.union_bytes_final`** and the per-step `new_bytes` curve | distinct `(layer, expert)` keys and their bytes, cumulative over the prefill and all `N` steps | **primary** | 4-step probe: 410,786 ppm and a 9.2× gap between streamed and marginal. `N = 16` unknown |
| `residency.decode_keys_in_prefill_union` | how much of decode **demand**, counted with repetition, the prefill already read. Denominator `decode_keys_demanded = 128N` | **primary** | see the row below — the prediction is stated over distinct keys and belongs to it |
| `residency.decode_keys_distinct` | the number of **distinct** `(layer, expert)` keys the `N` decode steps demanded, accumulated from the steps' own `ids` into a set seeded **empty**. It is `distinct` in the row below and it is independent of the prefill | **primary** | 274 over four steps on transcript A |
| `residency.decode_distinct_keys_in_prefill_union` | how many of those **distinct** decode keys the prefill already held. Denominator `decode_keys_distinct` | **primary** | 79.9 % / 75.2 % on the two probe prompts — 219 of 274 and 152 of 202, which is the form section 2.4 reading 2 predicted |
| `residency.step_reuse_per_mille` | `(demands − distinct) / demands` over decode steps only, `demands = 128N` and `distinct = decode_keys_distinct` | **primary, and it is a new metric** | 465 over four steps. Section 2.5 records why R2A's 447 is not this number, and why the prefill-relative 892 is not either |
| `routing_oracle.ids_total` / `ids_printed_compared` | routing identity coverage | **acceptance** | `128N` each, equal — 2,048 of 2,048 at `N = 16` |
| `decode.token_ids` | the gate | **acceptance** | `N` ids equal to llama.cpp's |
| `plane.roundtrip_bytes_compared` | oracle B's cumulative byte count | acceptance | `Σ_{k=1..N} 2 · 16 · (T+k) · 16 · 128 · 4` |
| `timings.elapsed_ns`, `decode.compute_ns`, `timings.pread_ns`, `first_token_ns` | wall, compute, read | **diagnostic. No claim** | see section 6.4 |
| `window.claim_decode_peak_use_bytes` | the decode-phase claim peak | characterization | 32,636,928 B |
| peak RSS | host | characterization | ≈ 350–470 MB (R5E) + 67 MB plane |

**Saturation, checked rather than assumed.** Every accumulator is `i64` and every one is bounded by
`N <= 64`. The largest is `residency.total_bytes_read`: at `N = 64` it is under
`1.6 × 10^9 + 64 · 7.5 × 10^8 ≈ 4.9 × 10^10`, nine orders below `i64`'s range.
`plane.roundtrip_bytes_compared` at `n_layer` 16, `N` 64, `KV_WIDTH` 4096 is under
`2 · 16 · 64 · 4096 · 2048 ≈ 1.7 × 10^10`. `ids_total` is at most 8,192. Nothing saturates.

### 3.12 Ownership, allocation, lifetime, and bounded memory

| Object | Owner | Allocated | Freed | Bound |
| --- | --- | --- | --- | --- |
| The plane | `moe_decode_step`'s `schedule` frame, one `buffer`, zero-filled, `KV_WIDTH` columns wide from the start | before the prefill | at that frame's exit, on every path including a failing step | `MAX_PLANE_BYTES` 8 GiB, refused as `R6M_PLANE_UNAVAILABLE` before `buffer(n)` |
| The dense window | the same frame | before the first graph | same | `MAX_WINDOW_BYTES`, `R5_WINDOW_BUDGET` |
| The claim window | the same frame | before the first graph, at `U_max(T)` | same | `MAX_CLAIM_WINDOW_BYTES`, `R5D_CLAIM_BUDGET` |
| ggml contexts, buffers, gallocrs | per graph, as R5E and R6 both do | per graph | per graph; `lifetime.*_created == *_freed` and `graph_balance_failures == 0` asserted after **`1 + (N+1)·17` graphs**, not after two | — |
| Per-step node tables | pure, allocate nothing, rebuilt per step | — | — | — |
| Mask, position, and out-ids images | one buffer each, sized for `N` steps and sliced per step, because Align's `buffer` is append-only (`src/decode_step.align:2704-2730`'s pattern) | once | with the frame | `width · N · 4` |
| The demand-stream arrays (`routed`, union sets) | the same frame | once, sized `n_layer · n_expert` bits for the union and `N · n_layer · n_expert_used` for the ids | with the frame | `64 · 16` bits and `64 · 16 · 8` i64 at the caps — under 70 KB |
| Move-in/out, source nulling, replacement | **N/A.** No ownership transfer is added. Records are returned by value, as `src/decode_step.align:3004-3010` records Request 49 forces | — | — | — |

### 3.13 Prerequisites

| Prerequisite | State |
| --- | --- |
| Everything R5D, R5E, R6, R6-STEP-N list | Shipped, unchanged |
| `R6-RESIDENT-WEIGHTS` merged, or this branch stacked on its head | **Stacked** on `6facd56`. If it merges with repairs this branch takes `git merge origin/main` — never a rebase — and re-runs its owner |
| `llama-eval-callback`, R2C-patched at generation `r2c-v2`, honouring `-n N` with full router axes on a routed model | **Probed and confirmed** on this exact model at `-n 4` and `-n 3` (section 2.1). **No patch change is taken and the generation does not move** |
| `llama-debug --save-logits` on OLMoE | Shipped; R5E section 5.2 asserts `oracle_logits.verdict IDENTICAL`, `byte_identical: true`, which is gate G1's root |
| `numpy`, importable by the `python3` on `PATH` | Inherited from R6-STEP-N. `scripts/decode_step_fingerprint.py` needs it and the runner prints one `N/A` line without it |
| `scripts/decode_step_fingerprint.py` accepting a **Q4_K** `token_embd.weight` with `n_embd % QK_K == 0` | **Holds**: OLMoE's table is Q4_K and `2048 % 256 == 0`. The script is otherwise architecture-agnostic. Section 5.7 cell G-P1 runs it |
| A host with the model and ~1 GiB of scratch above the pack | R5E's runner rule, unchanged |
| Align language features | **None new.** Section 9 records four continuing gaps; none blocks |

## 4. Oracles and the acceptance rule

Five oracles. Two are inherited unchanged, one is strengthened by probe 1, one is new, and one has a
fallback fixed in advance because a probe has not yet been taken.

### 4.1 What the instrument gives and what it does not

The invocation is fixed and is R5E's flag set with a step count:

```text
llama-eval-callback -m MODEL -p PROMPT -n N -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512 --temp 0 -s 0
```

`-n N` emits exactly `N + 1` graphs; graph `j` (`j = 2 .. N+1`) consumes `d_{j-1}`; this arm's step
`k` consumes `d_k` and produces `d_{k+1}`. So **this arm's `N` decode graphs are the instrument's
graphs 2 through `N+1`, one for one** — R6-STEP-N section 3.1's counting, re-confirmed on OLMoE in
section 2.1. `d_{N+1}` is consumed by neither and is **excluded by name**, reported as
`steps[N].argmax` and gated by nothing.

The instrument does **not** print the sampled token, on this model as on the dense one:
`inp_tokens` is a leaf and never a printed node; `result_output` is `{50304, 1}` printed at limit 3;
and stderr prints only the prompt ids. The `embd` fingerprint is therefore required, and section 4.2
is where it is earned rather than assumed.

### 4.2 Gate G — the token-id gate, with OLMoE's injectivity measured first

**G1 — `d_1` is byte-exact, and it is inherited.** R5E section 5.2 asserts
`oracle_logits.verdict: IDENTICAL`, `byte_identical: true` against `llama-debug --save-logits` on
this exact model at the reconciliation width. `d_1` is the argmax of that vector, so it is
llama.cpp's own argmax with no tolerance. This capability changes nothing about it and re-runs it.

**G2 — `d_1 .. d_N` through the `embd` fingerprint.** At step `k` the transcript's graph `k+1`
opens with `embd = GET_ROWS(token_embd.weight{2048, 50304}, inp_tokens{1,1,1,1}) = {2048, 1}`, which
is the vocabulary row of `d_k`. `GET_ROWS` is a copy of weight bytes, so equal ids give equal bytes,
and the only question is whether two different rows can print identically at the instrument's
`%12.4f` over the six printed values.

**That question is a measurement and it has not been taken for this model.** R6-STEP-N measured
Qwen2.5-Coder's table — 149,710 distinct fingerprints over 152,064 rows, one collision class, exactly
the 2,355 all-zero unused rows. OLMoE's table is **smaller in both dimensions**: 50,304 rows of 2,048
against 152,064 of 3,584. Fewer rows makes a collision less likely; a shorter row makes each
fingerprint carry less. The two effects do not cancel by argument and are not assumed to.

| Field | Contract |
| --- | --- |
| Cell | **G-P1**, section 5.7. It is the **first implementation step**, before the arm is written |
| Tool | `scripts/decode_step_fingerprint.py`, **unchanged**. It requires a Q4_K `token_embd.weight` with `n_embd % 256 == 0`; OLMoE's table is Q4_K and `2048 % 256 == 0`, so it applies as shipped |
| Key | the six `"%12.4f"` values `v[0..3]` and `v[n-3..n]`. The `sum` is recorded as corroboration and **not** gated, for R6-STEP-N section 3.2's reason: the sum is a sequential `float` accumulation inside the reference build and its last digit is exposed to that build's contraction, while the six values are copies of weight bytes |
| If the collision count is 0 | G2 is a token-id equality without qualification |
| If it is not 0 | the colliding ids are printed by name and the runner **refuses per step** if any decoded `d_k` is a member of a colliding class. The gate holds over the non-colliding vocabulary |
| If a colliding class contains rows that are **not** all-zero | this is the case R6-STEP-N did not meet and it is decided in advance: the run is **not** gated on a decoded id inside such a class, and if the qualification's four prompts decode one, **G3** is taken |
| **G3, named, costed, not taken** | one line in the R2C patch logging the sampled id and step index makes the gate a literal integer comparison. Cost: a new `PATCH_SHA256` and `PATCH_BYTES`, generation `r2c-v2 -> r2c-v3`, a full rebuild of the cached tree, and a re-run of the R2C qualification. It is section 8's first deferred item and is the declared response to the row above |

**The chain property.** `d_k` is the input to this arm's step `k` and to the instrument's graph
`k+1`, and `d_{k+1}` is computed from step `k`'s logits. A divergence at step `j` changes step `j`'s
`embd` and every subsequent step's input, so the `N` ids are gated as one chain rooted at G1's
byte-exact `d_1` and a single mismatch fails at the first step it reaches.

### 4.3 Oracle R — routing identity per step, and it is stronger than R5E's

At step `k`, for each of the sixteen layers, the eight ids this arm sliced out of
`ffn_moe_argsort-L` must equal the eight the instrument printed in `ffn_moe_topk-L` of transcript
graph `k+1`, and the block's exact integer sum must agree. This is R5E's oracle 3 — exact integer
equality, no tolerance — evaluated per step. **Three things change, and all three are improvements
that probe 1 and probe 2 earned:**

| | R5E, one prefill at `T = 6` | this capability, per decode step |
| --- | --- | --- |
| Layers compared | 15 of 16. Prefill layer 15's router row is `{8, 1}` while the graph carries 6 tokens, so R2A's token-reduced-tail rule discards its selections | **16 of 16.** Extent and count are both 1, the rule never fires |
| Slots compared per selection | **6 of 8.** `ids_printed_compared` is 546 of 728 — R5E ran against a compact-axis instrument, so two of every eight ids were only pinned in aggregate by the block sum | **8 of 8.** The R2C-patched instrument prints full router axes and section 2.1 confirms `slots_truncated: false` on this exact model |
| Coverage at `N = 16` | — | `ids_total == ids_printed_compared == 128N` = **2,048 of 2,048** |

**This is the first full-axis routing identity in the repository**, and it is worth naming as such
rather than presenting as inheritance: R5E's own ledger publishes 546/728 and says why.

`routing_oracle.verdict` is `MATCH` iff `ids_printed_compared > 0`, `ids_matched == ids_printed`,
and every step's sixteen block sums agree. **A `MISMATCH` is data on a successful run, not an error
code**, exactly as R5E has it — because a transcript comparison against a differently-routed step is
the diagnostic a reader needs, and oracle T is evaluated beside it. The **acceptance rule** in
section 4.6 requires `MATCH`.

### 4.4 Oracle C′ — the single-shot self-reference, with its fallback fixed in advance

At checkpoint `k`, `--moe-model-forward` at `TOKENS,d_1,…,d_k`, the same `KV_WIDTH`, and `-` in the
transcript position must reproduce `steps[k].sha256`. Checkpoints are `k ∈ {1, ⌈N/2⌉, N}` — at
`N = 16`, `{1, 8, 16}` — for R6-STEP-N section 3.4's cost reason, restated in section 6.4 with this
model's numbers.

**Byte-identity is *not* assumed here, and that is the difference from the dense arm.** R6's oracle C
holds byte-exactly because every operand the dense arm hands ggml is a contiguous F32 tensor, so its
decode path and its prefill path take the same kernel. On a routed model that reason **does not
carry**: the prefill at `T + k` tokens builds a compact stack of `U` planes and a `compact_ids`
tensor over `[0, U)`, while the decode step builds a stack of exactly 8 and a `compact_ids` tensor
over `[0, 8)`. The selected *experts* for the last token are the same eight; the `mul_mat_id` call
they are reached through is a different shape. Nothing measured says two `mul_mat_id` calls over
differently sized stacks produce bit-identical output for the plane they share.

| Field | Contract |
| --- | --- |
| Cell | **C-P1**, section 5.7. Taken **before** the arm's acceptance rule is fixed, using `--moe-model-forward` alone: run it at `T` and at `T + 1` on the same prompt and width and compare the `T + 1` run's logits against R5E's own recorded value, then compare the last token's `ffn_moe_out-L` digests between a run whose layer routes `U` experts and one where the same token routes 8 |
| **If byte-identical** | C′ is an **acceptance** oracle at all three checkpoints, exactly as R6 promoted oracle C |
| **If not byte-identical** | C′ becomes **characterization**, reported at all three checkpoints with its `max_abs_diff` in ten-thousandths, and the acceptance weight moves entirely to gate G, oracle R, and oracle B — none of which depends on it. The bound recorded in advance for a non-identical C′ is R5E's own `LOGIT_TOLERANCE_TEN_THOUSANDTHS` of **5000**, plus argmax equality, plus top-10 set equality: the rule R5E already ships for its runtime-width pass, applied unchanged rather than invented here |
| Either way | the outcome is published as `oracle_self.verdict` ∈ {`IDENTICAL`, `WITHIN`, `FAIL`} and the acceptance rule in 4.6 reads whichever branch C-P1 selected. **The branch is chosen by a measurement taken before implementation, and this document does not claim to know which** |

**`MAX_PREFILL_TOKENS` must move for C′ to run at all** — section 3.8. C′ is the only reason.

### 4.5 Oracles B and T — inherited

**Oracle B, the plane round trip (internal, byte-exact, acceptance, per step).** At step `k`, after
the write-back, the K and V the decode graph consumed — its two `CONCAT` nodes read back with
`slot_get` — must be byte-identical to the plane over columns `0 .. T+k-1`, on all sixteen layers.
Cumulative, and including the column the step just wrote, so a write-back one lane off dies in its
own step. R6-STEP-N section 3.4, unchanged, at OLMoE's geometry:
`plane.roundtrip_bytes_compared = Σ_{k=1..N} 2 · 16 · (T+k) · 16 · 128 · 4`.

**Oracle T, the per-step transcript (external, characterization above step 1).** 227 comparable rows
per graph — `1 + 14 · 16 + 2`, R5E's `mm_oracle_compared_count` unchanged, because a decode graph has
the same comparable node set. `kq-L` and `kq_soft_max-L` stay `shape_incomparable` with their `ne0`
validated against `KV_WIDTH`; the `norm-L` nodes stay `ambiguous_name`; the reduction chain's views
stay `unstable_name`. Tolerances are R5E's: 1 ten-thousandth per element, 1000 millionths or 10 ppm
per block sum.

**T is demoted to characterization at steps 2..N for R6-STEP-N section 3.4's measured reason**,
which applies here with one addition. The reason there: llama.cpp's decode graph takes a different
`MUL_MAT` accumulation path from its own multi-column prefill and the divergence rises with depth, so
gating on it would fail the run for something the arm cannot fix. The addition here: R5E section 2.8
measured that on this model a *routing* difference moves an affected node by whole units rather than
ten-thousandths, so a numeric bound on T would either be too tight to pass or too loose to mean
anything. **Oracle R is the gate on routing and T is the gate on structure.** What T asserts
unconditionally at every step:

| Assertion | What it catches |
| --- | --- |
| `instrument_graph == k + 1` | a mis-aligned graph skip |
| `nodes_matched == nodes_expected == 227` | a truncated transcript, a renamed node, a dropped layer |
| `layers_matched == 16` | a comparison that quietly covered four layers of sixteen |
| `elements_compared > 0` | the empty comparison, per step |
| `instrument_kv_width == KV_WIDTH` and every `kq-L` `ne0 == KV_WIDTH` | a width drift mid-loop |
| `tolerance_ten_thousandths == 1` | a silently widened tolerance |

At **step 1 only**, R6's full admission rule applies verbatim: `PASS`, or `FAIL` with
`max_abs_diff <= 5000` ten-thousandths **and** C′ at `k = 1` byte-identical — the second clause being
live only on the branch C-P1 selects.

### 4.6 The shipped acceptance rule, stated once

`scripts/run-moe-decode-step` implements it and its comment quotes it. Sections 4.2 to 4.5, 5, and 6
refer to it and do not restate it.

> For every prompt, all of the following, unconditionally:
>
> 1. **Gate G.** `decode.token_ids` has `N` entries and each `d_k` equals llama.cpp's — G1 for `d_1`,
>    G2 for `d_1 .. d_N`, over a vocabulary whose fingerprint collision classes were measured in this
>    run and none of whose members any step decoded.
> 2. **Oracle R.** `routing_oracle.verdict == "MATCH"` with `ids_total == ids_printed_compared ==
>    128N` and `steps_compared == N`, `layers_matched == 16N`.
> 3. **Oracle B.** `plane.roundtrip_verdict == "IDENTICAL"` over a positive byte count, with every
>    step's own verdict `IDENTICAL`.
> 4. **Oracle C′.** At `k ∈ {1, ⌈N/2⌉, N}`, `oracle_self[k].verdict` — `IDENTICAL`, or `WITHIN`
>    when argmax equality, top-10 **set** equality and a bound of 5000 ten-thousandths all hold, or
>    `FAIL` — is **reported with all three of its quantities**. On the branch cell C-P1 selected,
>    section 4.4 moves the acceptance weight "entirely to gate G, oracle R, and oracle B", so exactly
>    one clause is acceptance: **argmax equality**. The bound is taken over the union of the two
>    sides' top-10 index sets, from the raw `u32` of each logit that both documents publish; section
>    13 deviation 15 records why that is a narrower denominator than R5E's whole-vocabulary sweep,
>    and section 12.4 records what the three clauses measured — including the checkpoints where
>    `WITHIN` does **not** hold.
> 5. **Oracle T, structural.** Every assertion in section 4.5's table, at every step.
> 6. **Oracle T, numeric, at step 1 only.** `PASS`, or `FAIL` under R6's admission rule.
> 7. **Claim accounting.** For every step, `residency.expert_bytes == 487,587,840`,
>    `routed.keys_demanded == 128`, `claim_planes_read == 384`, and section 3.11's
>    `expert_pread_bytes` relation holds.
> 8. **Determinism.** Three consecutive runs byte-identical after `normalize`.
> 9. **The transcript holds exactly `N + 1` graphs.** Fewer means llama.cpp stopped early (EOS) and
>    the prompt is refused rather than compared over a shorter run.
>
> Oracle T at steps 2..N is **characterization**: its per-step maxima are reported and no acceptance
> decision is taken from them. The demand-stream metrics of section 3.11 are **measurements**: they
> are asserted for internal consistency by rule 7 and are otherwise reported, not gated.

### 4.7 The tolerance rule

| Comparison | Rule | Value | Derivation |
| --- | --- | --- | --- |
| Gate G, `d_1` | exact integer equality | 0 | argmax over a byte-identical logit vector |
| Gate G, `d_k` via `embd` | exact, conditional on a measured property | 0 | `GET_ROWS` is a copy. Conditioned on cell G-P1's collision measurement |
| Oracle R | exact integer equality | 0 | expert ids are integers; R5E's rule unchanged |
| Oracle B | byte identity | 0 | a byte plane either survives a round trip or it does not |
| Oracle C′ | byte identity, **or** R5E's runtime-pass rule | 0, or 5000 ten-thousandths + argmax + top-10 set | selected by cell C-P1 (section 4.4) |
| Oracle T, per element | absolute | 1 ten-thousandth | the instrument prints `%12.4f`. Inherited from R5A through R5E |
| Oracle T, per block sum | absolute then relative | 1000 millionths, 10 ppm | inherited unchanged |
| Oracle T step-1 admission | absolute | 5000 ten-thousandths | R6 section 3.4's, applied where R6 applied it |
| Oracle T, steps 2..N | **no numeric bound** | N/A | deliberate; section 4.5 gives the measured reason |
| Claim accounting | exact integer, and a bounded inequality | 0 / `claim_planes · block_align` | section 3.11 |

## 5. Closure matrix

Every cell names an implementation owner and an exact regression. `T` is the prefill length, `N` the
step count, `k` a step index, `L` a layer. Cases prefixed `md-` are new rows in the smoke; cases in
*italics* are qualification assertions.

### 5.1 `src/moe_decode_step.align` — the arm and the loop

| Phase | Implementation | Regression |
| --- | --- | --- |
| Formation / validation | operand parse, arity, `TOKENS`, `STEPS`, `KV_WIDTH`, geometry kind/schema/arch, the tightened slot ceiling | `md-arity-4`, `md-arity-8`, `md-arity-12`, `md-path-*-empty`, `md-path-dash-{pack,geometry,reference}`, `md-tokens-{empty,trailing,space,33,vocab}`, `md-steps-{empty,zero,negative,over-max,trailing}`, `md-steps-zero-and-narrow` (precedence), `md-kv-width-{empty,below-tokens,narrow-for-steps,over-max}`, `md-geometry-arch`, `md-geometry-expert-used-32` |
| Construction | plane, dense window, claim window at `U_max(T)`, mask/position/out-ids images sized for `N`, backend, slot store | `md-engine-ok` (`N` absent ≡ 1); `md-steps-3` asserts `steps_requested == 3`, `steps_completed == 3`, `columns_written == T + 3` |
| Success | prefill → plane → `N` × (upload, phase A, decide, claim, phase B, write-back, verify, decode) → document, `status: ok`, exit 0 | `md-steps-3`; *the acceptance rule at `N = 16` on four prompts* |
| Failure | any seam code, detail prefixed `step[<k>]` | `md-force-compute-step2` (a forced build keyed on `t == 1 && n_past > T`, so it fires at step 2 and not step 1) → `R5_COMPUTE` detail `step[2]` |
| Malformed input | validation order above; multi-invalid precedence `R6M_STEPS` before `R6M_KV_WIDTH` | `md-steps-zero-and-narrow` |
| Early exit | a failing step publishes `steps_completed = k-1`, `k-1` `steps[]` objects, `k-1` ids, `columns_written = T+k-1`, non-`IDENTICAL` round trip, `residency` over `k-1` steps, and frees the plane and both windows | `md-force-compute-step2` asserts all seven; `record()`'s universal `(returncode == 0) == (status == "ok")` on every case |
| Cleanup | plane, both windows, and every per-step buffer are ordinary `buffer`s at the arm's frame scope; ggml contexts/buffers/gallocrs balanced after `1 + (N+1)·17` graphs | `lifetime.*_created == *_freed`, `phase_balance_failures == 0`, per case; `md-steps-3` is where an unbalanced per-step context shows as `3 × 16 × 2` leaked |
| Move-in/out, source nulling, replacement, return | **N/A — no ownership transfer is added.** Records return by value, which `src/decode_step.align:3004-3010` records Request 49 forces | stated, with reason |

### 5.2 The KV plane at OLMoE's geometry

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | one zero-filled `buffer` of `plane_bytes_for(g, KV_WIDTH)`; `R6M_PLANE_UNAVAILABLE` above `MAX_PLANE_BYTES` | `md-plane-bytes` asserts `plane.bytes == 16 · 2 · KV_WIDTH · 16 · 128 · 4` on the hosted geometry |
| **Write-back rows, derived not assumed** | the OLMoE decode table's post-QK-norm post-RoPE K row and reshaped V row, read with `slot_get` after compute; the two `CONCAT` outputs are deliberately **not** the source, because the V concat's new column is strided | `md-force-writeback-row` swaps the K source to the pre-norm row and must produce `R6M_PLANE_MISMATCH` at step 1; `md-force-writeback-offset` writes column `n_past - 1` |
| Success | column `T+k-1` of layer `L`, K and V, one column each | oracle B per step, cumulative and including the new column |
| Failure | `R6M_PLANE_MISMATCH`, detail `step[<k>]layer[<n>]tensor[k\|v]col[<n>]` | `md-force-writeback-*` |
| Ordering invariant | upload (`slot_set` source, columns `0..n_past-1`) → compute (phases A and B, claim reads touch the **claim window only**) → write-back (`slot_get` destination, column `n_past` only). Disjoint by construction, separated by a completed compute | `md-steps-3` plus oracle B at every step; `md-force-claim-into-plane` forces a claim read whose destination lands in the plane and must be refused by the region check before any read |
| Cleanup | freed at the arm's frame exit on every path | `lifetime` assertions on every case |
| Persistence | **N/A.** Section 1.4 and section 3.4 record the two `akvp` couplings that would have to move first | stated, with the exact file and offset |

### 5.3 `src/layer_olmoe.align` — the decode topology as data

| Phase | Implementation | Regression |
| --- | --- | --- |
| Formation | `OP_CONCAT`, `WHEN_DECODE`, `mm_row_issued_at(condition, last, wide, decode)`, `mm_decode_a_node_table(g, n_past, width)`, the two plane slots at `MAX_NODE_SLOTS - 2`/`- 1`, `MAX_DECODE_STEPS := 64`, `MAX_PREFILL_TOKENS 6 -> 32` | `md-table-rows` asserts `graph.table_rows_a_decode` and `slot_high_water`; `md-geometry-expert-used-32` asserts the tightened ceiling refuses at 32 and admits at 31 |
| Success | the table is pure and allocates nothing; rebuilt per step for `n_past = T + k - 1` | `md-steps-3` |
| The prefill tables | **byte-unchanged.** `mm_a_node_table`, `mm_b_node_table`, `mm_embed_node_table`, `mm_head_node_table`, `mm_oracle_table`, `mm_write_mask`, every member table | `moe-model-forward-golden.jsonl` and `moe-layer-forward-golden.jsonl` **byte-unchanged**, verified by regeneration (section 6.3) |
| The `MAX_PREFILL_TOKENS` widening | `--moe-layer-forward` and `--moe-model-forward` accept 7..32 tokens without a transcript and are refused at 7 with one | `mm-tokens-seven` and `moe-tokens-seven` **change meaning** and are renamed `mm-tokens-33` / `moe-tokens-33`; two new cases `mm-tokens-seven-with-transcript` / `moe-tokens-seven-with-transcript` assert `R5_ORACLE_TRUNCATED` still fires at 7. Section 6.3 predicts the moved rows |
| Failure / malformed | a condition column value outside `{0,1,2,4}` is unreachable by construction; `mm_row_issued_at`'s default is `WHEN_WIDE`'s branch, as `mm_row_issued`'s is | stated; the table is data and its producer is the only writer |
| Cleanup, move-in/out | **N/A — pure functions returning owned column sets assigned once**, R5A correction C9's shape | stated, with reason |

### 5.4 `src/moe_model_forward.align` — what is re-used and what is duplicated

| Phase | Implementation | Regression |
| --- | --- | --- |
| Re-used unchanged, by import | `layer_olmoe.decide` and its slot-order/distinctness/bijection rules; `moe_layer_forward.parse_tokens`; `moe_layer_forward.scan_transcript`/`scan_transcript_after`; the four oracle comparators' row grammar | `moe-model-forward-golden.jsonl` byte-unchanged proves no behaviour moved |
| **Duplicated for Request 49** | the failure sink — `fail`, `fault_into`, `pack_fault_into`, `take`, `take_pack`, `account`, `check_types`, `top_k`, `compare_prefill_logits` — and the plane-owning `refill`, because both take a `borrow mut` beside a shorter-lived operand | section 9 records the count and the exact function list; Request 49's acceptance criteria gain `src/moe_decode_step.align` as a client and, on merge, the duplicates collapse |
| Claim window sizing / budget | `size_claim_window` at `U_max(T)`, `R5D_CLAIM_BUDGET` before reservation | `md-claim-window` asserts `window.claim_u_max == n_expert_used · T` and `claim_decode_peak_use_bytes` |
| Claim scatter and its accounting | `read_block_scatter` per routed expert; the **new** per-step `Counters` attribution of section 3.11 | `md-claim-accounting` forces a scatter to over-read and must raise `R6M_CLAIM_ACCOUNTING`; *the qualification asserts the exact 487,587,840 and the amplification bound* |
| `stage_carry`, `claim_tensors`, `mul_mat_id` | unchanged; `ne2 == routing.count == 8` at every decode step | `md-steps-3`; `window.claim_placements == 3 · 16 · (N + 1)` |
| Prefill behaviour | **byte-unchanged** | the two MoE goldens |

### 5.5 `src/ggml_ffi.align`, `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`, `src/ggml_spike.align`

| Phase | Implementation | Regression |
| --- | --- | --- |
| FFI | **no new `extern` symbol.** `op_concat` ships; `slot_get`/`slot_set` already move plane bytes | the smoke's existing source scan asserting no `unsafe`, no `extern` outside `ggml_ffi` |
| Both shims | **byte-unchanged.** The stub already implements `concat`, `argsort`, `mul_mat_id`, and `view_2d` for the two arms that use them | the goldens are generated against the stub; a shim change would move all six |
| `src/ggml_spike.align` | one `import` and one `if` at the dispatch ladder, above the `--*` catch-all | `md-arm-unknown-flag` passes `--moe-decode-stepped`, which is not and will not be an arm; a `NO_DOCUMENT` case carrying no golden row |

### 5.6 Fixture, smoke, runner, and the goldens

| Phase | Implementation | Regression |
| --- | --- | --- |
| `scripts/layer_forward_fixture.py` | `write_moe_model_corpus` gains a decode corpus: `moe_model_forward` gains a `planes` argument (its dense counterpart already has one), a new `moe_model_decode_layer` and `moe_model_decode`, and a `write_moe_decode_corpus` emitting a `DECODE_STEPS + 1`-graph transcript, its ids, its logits, and the onegraph / short-for-steps / perturbed / kv-width mutations. `plane_to_past_k`/`plane_to_past_v` are geometry-generic and are reused at `n_head_kv = 2`, `head_dim = 4` | the fixture **is** the second implementation; every `md-` case is scored against it |
| Reseeding | a `MOE_MODEL_DECODE_RESEEDED_ROWS` analogue, so the reference loop's three ids differ and non-degeneracy is asserted | the dense corpus's own non-degeneracy assertion, copied |
| CLI | `main` filters exactly `("--model", "--moe")`; the decode corpus rides `--moe --model` rather than adding a third flag, because that combination already selects the R5E corpus this one extends | `write_corpus` returns the new paths and the smoke consumes them |
| `scripts/run-layer-forward-smoke` | a **seventh** block. `layer-forward-smoke` is already in `HOSTED_CHECK_TARGETS`, so aggregate membership and check topology do not move and `scripts/check-gate-topology`'s byte-literal EXPECTED does not move | the block's own `ORDER` list and summary print |
| `scripts/moe-decode-step-golden.jsonl` | **new, seventh golden.** Every prior arm owns exactly one | the six existing goldens regenerate to **no diff**, asserted (section 6.3) |
| `scripts/run-moe-decode-step` | the opt-in real-model qualification; `Makefile` gains one target, `moe-decode-step-qualification`, in no aggregate | section 6.2 |
| `Makefile` | one `.PHONY` word and one target. **This is an executable-contract boundary**, so `scripts/pre-pr` selects the executable row and the installed profile, exactly as R5D and R5E record | `gate-topology-check` |

### 5.7 The two probe cells, which are the first implementation steps

| Cell | What it settles | If it fails |
| --- | --- | --- |
| **G-P1** | `scripts/decode_step_fingerprint.py OLMOE.gguf out.json` — the collision classes of OLMoE's 50,304 × 2,048 Q4_K `token_embd.weight` | a class containing non-all-zero rows selects G3 (section 4.2), which is a patch generation bump and is deferred, not taken silently |
| **C-P1** | whether two `mul_mat_id` calls over an 8-plane and a `U`-plane stack agree bit for bit on their shared token | C′ becomes characterization at R5E's runtime-pass bound (section 4.4). The acceptance rule loses one oracle and keeps four |

Both are runnable against the shipped arms with no new code. **Neither is a risk to the capability**;
each selects a branch of a rule this document has already written both sides of.

## 6. Verification — owner, qualification, goldens, and cost

### 6.1 The hosted owner — a seventh block in `scripts/run-layer-forward-smoke`

Hosted, ggml-free, model-free, llama.cpp-free. The corpus is `layer_forward_fixture.py --moe --model`
extended with a decode loop: a pure-Python routed decode step per iteration at `n_past = T + k - 1`
over the KV plane the routed prefill produced and each step grew, and a transcript holding
`DECODE_STEPS + 1` graphs exactly as `llama-eval-callback -n 3` emits them. Every oracle is reachable
with no ggml and no model — oracle R against transcript graph `k + 1` at three offsets, oracle B over
the plane's own bytes including each step's newly written column, oracle T against the same graphs,
and the claim accounting against the fixture's own routing.

The synthetic geometry is `GEOMETRY_MOE_MODEL` unchanged: `n_layer` 2, `n_embd` 8, `n_head` 2,
`n_head_kv` 2, `head_dim` 4, `n_ff_exp` 16, `n_vocab` 32, `n_expert` 8, `n_expert_used` 3, all F32.
`n_expert_used = 3 <= 6` keeps the routing oracle's element-wise coverage complete even against a
compact-axis printer, so the hosted block does **not** depend on the R2C patch — which is the
property that lets a hosted owner gate a capability whose real oracle needs a patched instrument.

**Hosted `K` is 3 and not 16 on purpose**, R6-STEP-N's reason unchanged: the loop's correctness is a
property of the second iteration, and sixteen synthetic steps buy nothing the third does not.

**`layer-forward-smoke` is already in `HOSTED_CHECK_TARGETS`**, so this changes no aggregate
membership and no check topology. Its measured budget history is 19.41 s at three blocks, 32.199 s at
four, and 2 min 32 s at six on the R6-STEP-N merge head; R5E pre-committed a dense/routed split if a
60 s ceiling were breached and that ceiling has already been superseded by the six-block reality.
**This block's own cost is recorded and the split decision is re-taken with the measurement, not
before it.**

### 6.2 The named qualification — `gmake moe-decode-step-qualification`

`scripts/run-moe-decode-step`, opt-in and capable-only, in neither `HOSTED_CHECK_TARGETS` nor
`CAPABLE_ONLY_CHECK_TARGETS` and in no aggregate, exactly as the five existing `*-qualification`
targets are not. `moe-decode-step-qualification: build ; ./scripts/run-moe-decode-step`.

One explicit `N/A` line and exit 0 when any of these is unset or absent:

```text
ALIGN_LLM_GGML_INCLUDE                ggml headers
ALIGN_LLM_GGML_LIB                    ggml libraries
ALIGN_LLM_GGUF_MODEL                  the OLMoE GGUF
ALIGN_LLM_LLAMA_EVAL_CALLBACK         path to llama-eval-callback, R2C-patched
ALIGN_LLM_LLAMA_DEBUG                 path to llama-debug
```

plus a non-`olmoe` container, `numpy` not importable, or free space under the pack's size plus 2 GiB
under `ALIGN_LLM_MOE_DECODE_STEP_TMPDIR` (defaulting to `TMPDIR`, and deliberately **not** an `N/A`
condition — it selects a location). `ALIGN_LLM_DECODE_STEPS` defaults to 16 and is the documented
cost fallback; `ALIGN_LLM_MOE_DECODE_STEP_PROMPTS` defaults to 4 and selects how many of the four
prompts run, which is the second documented fallback. Neither is ever an `N/A` condition.

Four prompts, at most six tokens each, taken from R5E's and R6's corpora so the tokenizer assertion
has a recorded expected id list; `KV_WIDTH` 256; three consecutive runs per prompt for determinism.
The runner asserts, **before** invoking the arm: the arm's `libggml-base` and `llama-debug`'s resolve
to the same file, the tokenizer produced the expected ids, the two instruments agree with each other,
the transcript holds exactly `N + 1` graphs, and cell G-P1's fingerprint measurement is complete and
names no colliding class any step reaches. An instrument skew is then reported as an instrument skew
and not as a failing oracle.

**The ggml identity check is asymmetric on purpose, and one half of it fails open.** Gate G1 is a
**byte** comparison against `llama-debug --save-logits`, so the arm and that binary must be one
arithmetic and a disagreement is a named refusal. `llama-eval-callback` is compared under a tolerance
by oracle T, and the pinned R2C instrument links its ggml statically (deviation 4), so its library
cannot be resolved at all: the runner **reports** what it found and enforces nothing. Where no loader
listing can be read the check says on one line that it failed open, because an unverifiable property
reported as verified is worse than an unverified one that is named. ggml publishes no build
identifier a runner can read, so resolved object identity is the strongest cheap statement available
and section 15 records the toolchain change that would make it unnecessary. A forced-failure loop over
`init` and `compute` against the real shim expects `R5_GGML_INIT` and `R5_COMPUTE`. Everything is
removed on every exit path including a signal.

### 6.3 Predicted golden movement

Goldens are keyed by `case` and the ordered case list must equal the runner's `ORDER` exactly, so an
insertion at the wrong position fails on the list comparison rather than on a value.

| Golden | Predicted |
| --- | --- |
| `scripts/moe-decode-step-golden.jsonl` | **new.** Its rows are this capability's own file, created here and consumed by nothing else |
| `scripts/moe-model-forward-golden.jsonl` | **two rows move and no others.** `mm-tokens-seven` is renamed `mm-tokens-33` with its token list changed (section 3.8), and `mm-tokens-seven-with-transcript` is added to keep `R5_ORACLE_TRUNCATED` covered. **Three landed, not two** — section 12.6 — because the open side of the new guard needs a case of its own: `mm-tokens-seven-no-transcript` proves that seven tokens are still *accepted* without a transcript, and a prediction of two rows would have been satisfied by a guard that refused both ways. The over-cap fixture is **33 repetitions of id 1**, not `1,2,…,33`: the hosted `n_vocab` is 32, so an ascending list would be refused as out-of-vocabulary and the case would stop being about the cap — R6-STEP-N section 2.5's own trap, inherited |
| `scripts/moe-layer-forward-golden.jsonl` | the same rows, `moe-tokens-seven` → `moe-tokens-33` plus `moe-tokens-seven-with-transcript` — and, for the reason above, `moe-tokens-seven-no-transcript`, so **three** land here too |
| `scripts/decode-step-golden.jsonl` | **byte-unchanged.** The dense arm is not touched and its schema does not move |
| `layer-forward`, `model-forward`, `gpu-forward`, `ggml-spike` goldens | **byte-unchanged**, verified by regenerating all seven and observing diffs only where predicted |

**A programmatic walk of the old and new files is the evidence, not an eyeball**, in the shape
`HANDOFF.md` records for R6-RESIDENT-WEIGHTS: report additions, removals, and, for every pre-existing
row, the exact set of fields that moved.

### 6.4 Cost — estimated before implementation, with the fallbacks named

Per decode step, this model reads `487,587,840` expert bytes plus R5E's measured `168,558,592` dense
layer bytes, `84,518,912` head bytes, and one `1,152`-byte embedding row — **740,666,496 B**. R5E
measured its own claim `pread` at 519.9–612.0 ms for 1,301,446,656 B, so roughly 2.2 GB/s warm.

| Item | Estimate |
| --- | --- |
| One `N = 16` arm run | prefill 1.55 GB + 16 × 0.74 GB = **13.4 GB** read, ≈ 6.1 s of `pread`, plus compute — R5E's whole-prefill compute is 147 ms and a `T = 1` step's is a small fraction of it. **≈ 8 s** |
| Four prompts × three determinism runs | **≈ 100 s** |
| Oracle C′ | 3 checkpoints × 4 prompts × one whole `--moe-model-forward` ≈ **25 s** |
| Instrument captures at `-n 16` | four transcripts. Section 2.1 measured 4.83 MB at `-n 4`; at `-n 16` expect ≈ 14 MB each and ≈ 40 s each — **≈ 160 s**, and ≈ 56 MB of scratch |
| Cell G-P1 | one dequantization of 50,304 × 2,048 Q4_K rows — **≈ 15 s**, once |
| Packing the model, geometry, shim build | **≈ 45 s** |
| **Total** | **≈ 6–8 minutes**, against the ≈ 1800 s **budget** `scripts/run-decode-step` records for itself. It is a budget and not a cap: neither runner enforces a timeout, and a run that exceeded it would be slow rather than refused. The fallbacks below are what a run over budget takes |
| Transcript rescan | `N` rescans of a 14 MB transcript per prompt, R6-STEP-N section 6 risk 3's accepted cost, ≈ 224 MB of scanning per prompt |
| Documented fallbacks, in order | `ALIGN_LLM_DECODE_STEPS=8`, then two prompts |
| Scratch | the pack (≈ 4.2 GB) plus ≈ 2 GiB |

**These are estimates recorded in advance so a measured result far from them is a miss to report.**
No cost ceiling is recorded because no performance claim is made (section 3.11).

## 7. Risks

1. **Cell C-P1 shows `mul_mat_id` is not stack-shape-invariant**, and oracle C′ demotes to
   characterization. *Likelihood:* real. *Mitigation:* section 4.4 writes both branches in advance and
   the acceptance rule keeps four oracles either way. **The risk is to the strength of one oracle, not
   to the capability.**
2. **The write-back rows are derived wrong.** The four qwen2 constants do not transfer and OLMoE's
   post-QK-norm post-RoPE K row must be read out of the new decode table. A wrong row writes a
   plausible plane. *Mitigation:* oracle B compares the column the graph produced against the column
   the plane holds **through a different node**, in the step that wrote it; `md-force-writeback-row`
   is the negative case; and the routing oracle would diverge at step 2 because a corrupted K changes
   the next step's attention and therefore its routing.
3. **Cell G-P1 finds a collision class with non-zero rows.** *Likelihood:* lower than for the dense
   table by row count, higher by row width; not argued, measured. *Mitigation:* section 4.2's decision
   rule is fixed in advance and G3 is costed.
4. **`WHEN_WIDE` is reused by accident.** The single most likely implementation error, because the
   rows exist, they type-check, they run, and they produce a finite wrong answer with the new column
   at index 0. *Mitigation:* section 3.7 names it before implementation; oracle B catches it in step 1;
   `md-force-writeback-offset` is the regression.
5. **The `MAX_PREFILL_TOKENS` lift widens two arms this capability does not otherwise touch.** At
   `T >= 8`, `U_max = min(64, 8T)` saturates at `n_expert = 64` and `--moe-model-forward`'s claim
   window becomes the whole expert plane set per layer — `window.claim_bytes` stops being a
   reservation figure with slack and becomes the maximum. *Mitigation:* the lift is required only by
   oracle C′, which runs at `T + k <= 22`; the transcript refusal `R5_ORACLE_TRUNCATED` is
   byte-unchanged and still fires at 7; the qualification's prefills stay at `T <= 6`; and
   `window.claim_bytes`, `claim_u_max`, and `claim_peak_use_bytes` are all published so the saturation
   is a document field rather than a surprise. **Recorded as a widening, not absorbed.**
6. **The claim window is refilled `16(N+1)` times inside a loop whose plane is live**, which is the
   coordinated invariant of section 1.3. A claim read whose destination lands in the plane would be a
   silent corruption. *Mitigation:* the two regions are separate `buffer`s with separate `ggml`
   wraps; `md-force-claim-into-plane` forces the aliasing and must be refused before any read; and
   `window.pointer_identity_failures == 0` covers every placement.
7. **A third copy of the Request 49 failure sink.** *Mitigation:* section 9 records the exact function
   list and adds this module as a client so the request's acceptance criteria collapse all three at
   once. No compatibility layer is built.
8. **The hosted block pushes `layer-forward-smoke` past a comfortable budget.** It is already 2 min
   32 s at six blocks. *Mitigation:* the block is measured and the dense/routed split R5E
   pre-committed is re-decided with that number rather than in advance.
9. **`n_expert_used` above 31 is now refused where R5E admitted 32.** A one-value narrowing of a
   public precondition on the new arm only; the prefill arms keep 32. Recorded rather than discovered,
   and `md-geometry-expert-used-32` is the case.
10. **Everything is one model, one host, one corpus of four prompts.** The demand-stream numbers are
    exact integers and are host-independent; the elapsed figures are diagnostics and are not. A second
    routed architecture is `moe-prereq-discharge.md` section 5.5's, deferred with its reason.

## 8. Deferred, with the reason each is a deferral and not an omission

- **Resident dense weights with streamed experts.** The obvious next capability and the one this
  measurement is *for*: it removes 253 MB of the 740 MB a step reads while leaving the measured
  quantity exact. The operand it would take is `RESIDENT` at position 13 with the value `dense`, and
  the work it needs is a routed `Plan`/`Ends` for `model_forward.plan_resident`, whose per-layer
  window is a constant today and is not on a routed model. **Partial expert residency comes after
  it**, and its input is this capability's `steps[].routed` stream.
- **KV persistence for a routed arm.** Two exact couplings, both named in section 3.4:
  `src/kv_plane.align:519` bounds `token_count` by `layer_qwen2.MAX_PREFILL_TOKENS`, and the header's
  `document_schema_version` at offset 136 means the `R6_DECODE_STEP` schema. An `akvp` v2 with a
  `document_kind` field is the honest fix and has no consumer yet.
- **G3, the exact-id gate.** Section 4.2, costed. It is also the declared response if G-P1 finds a
  non-degenerate collision class.
- **Per-step oracle C′.** Sixteen checkpoints × four prompts is sixty-four whole `--moe-model-forward`
  runs against three × four. Cost recorded in section 6.4.
- **EOS, a sampler, and stop strings.** They belong to the capability that produces *text*, which
  needs a detokenizer, which needs Align Request 22. R6-STEP-N section 2.12, unchanged; this
  capability adds no consumer to Request 22.
- **The Metal arm and any GPU residency of the plane or the claim window.**
- **`ggml_get_rows` over a resident embedding table**, gpt-oss and any second routed architecture,
  expert hotness ordering in the pack, and a slice rule in `--pack-verify` — R5E section 5.4's
  deferrals, unchanged, each still owned where it was.
- **Renaming to `align-runtime`.** `r5b-model-prefill-forward.md` section 5.4's condition is a
  residency policy, and this capability produces a policy's input rather than a policy.
- **Any TTFT, tokens-per-second, or throughput claim.** The R6 roadmap gate — TTFT on repeated coding
  tasks sharing a prefix — stays **unmet**, and this capability does not move it: it measures a
  routed decode's byte demand and neither shares a prefix nor keys a lookup.

## 9. Align capability requests

Classified per `CLAUDE.md`. **None blocks this capability. No new request is proposed**, and that is a
finding rather than an absence: every construct this design needs compiles against the shipped pin,
and the four gaps it meets are already recorded with named clients.

| Gap | Classification | Status |
| --- | --- | --- |
| A cross-module call with a `borrow mut` argument refuses every shorter-lived operand | Genuine Align gap, already recorded | **Request 49, `PROPOSED`.** This capability is its **largest client to date**: `src/moe_decode_step.align` must carry a **third** copy of `fail`, `fault_into`, `pack_fault_into`, `take`, `take_pack`, `account`, `check_types`, `top_k`, and the prefill-logits comparison — **36** functions in total, regenerated from the source and listed in the request. There is no duplicated `refill`: KV persistence is out of scope, so the plane is never refilled from a container. The request's `align-llm verification` block gains this module and `gmake layer-forward-smoke` with **seven** goldens byte-unchanged. **No status change**, `Blocking: no`, and no compatibility layer is built |
| A `Borrow` argument may be a temporary value | Genuine Align gap, already recorded | **Request 47, `PROPOSED`.** The new module inherits R5E's mitigation throughout — every window region, every claim region, every `str` view bound to a named local on the preceding line. One more client; the request already names `make layer-forward-smoke` as its verification |
| Same-call aliasing between a `borrow mut` owner and its own scalar field | Genuine Align gap, already recorded | **Request 48, `PROPOSED`.** Same shape: `alignment := o.tensor_alignment` and `width := o.attention_width` copied to locals before every call that also takes `borrow mut o`. One more client |
| No aligned heap allocation | Genuine Align gap, already recorded | **Request 33, `PROPOSED`.** This arm pays the 64-byte over-reservation **three** times — the dense window, the claim window, and the plane — where R5E pays it twice. One more client; the compensation is unchanged |
| In-place replacement of owned `array<i64>` record fields | Genuine Align gap, already recorded | **Request 36, `PROPOSED`.** R5A correction C9's shape forces `steps[].routed` to be rendered as it is produced rather than carried as columns, exactly as R5E's `schedule[]` is. One more client |
| A program cannot ask the host how much memory it has | Genuine gap, already recorded | **Request 50, `PROPOSED`. Not a client.** This capability streams, so it makes no large reservation and needs no host inquiry. Recorded here only so a reader does not expect it |

**Numbering.** The register ends at **51** and the next free number is **52**
(`HANDOFF.md`). This capability takes none. If implementation finds a genuine gap the design did not
predict — which is what happened to R5E, whose section 5.5 predicted no new request and produced two
— it takes 52 and section 10 is updated at that time.

**No hypothetical surface is consumed.** Every construct this document specifies compiles against the
shipped pin.

## 10. Reconciliation drafts

Written before implementation and kept verbatim afterwards, so the prediction can be read against the
result.

### 10.1 `docs/specs/roadmap.md` — item 32

**Numbering is provisional and the re-check is named.** `main` carries items to **30**
(R6-RESIDENT-WEIGHTS). Item **31** is claimed by `agent/c4-repair-measured` on its own branch. This
capability therefore drafts **32**, and re-checks four things at every `git merge origin/main` —
never a rebase — in the shape `HANDOFF.md` already records: **the roadmap item number, the document
schema number, the next free Align request number, and which goldens regenerate.**

> **32. R6-OLMOE-DECODE — N greedy decode steps on a routed model, and the per-step expert demand
> they make.** Design in [`r6-olmoe-decode.md`](r6-olmoe-decode.md). Item 26 computes one OLMoE
> prefill and measures that 33.36 % of the model's expert bytes are touched by it; item 30 makes a
> dense decode loop read zero weight bytes per step. Neither can say what a *routed* decode step
> demands, and `docs/specs/r3-residency-sim.md` section 8 — whose four-word finding is **the
> intervention is decode** — could only simulate it over llama.cpp's trace. This capability ships a
> seventh arm, `--moe-decode-step`, with `--decode-step`'s operand shape and its own document kind
> `R6_MOE_DECODE_STEP` at schema 1: `N` greedy steps on OLMoE-1B-7B-0125-Instruct Q4_K_M over an
> Align-owned KV plane, each step resolving that step's top-8 claims in **all sixteen** layers and
> computing only those experts, weights **streamed**. Weights are streamed **because residency would
> destroy the measurement** — item 30 makes `step_pack_bytes` zero by construction — so the two are
> mutually exclusive in one invocation and demand measurement comes first. The design's probe record
> settles three things before implementation, from two full-axis transcripts the R2C instrument had
> already produced: a decode graph does **not** narrow, so all sixteen layers route and the routing
> oracle compares 8 of 8 slots on 16 of 16 layers where item 26 compared 546 of 728; the per-step
> demand is therefore exactly `3,900,702,720 / 8 = 487,587,840` bytes, **125,000 ppm**, prompt- and
> step-independent, and the same number `r3-residency-sim.md` section 8.1 publishes as the decode
> arms' one-token working set; and the open quantity is the **union**, which over four steps on one
> prompt grows 128 → 274 keys of 1,024 while **79.9 %** of every decode demand was already read by
> the prefill and the marginal new bytes per step average 53 MB against a 487.6 MB streamed demand —
> a **9.2× gap** that is the case for a decode-side residency policy. The plane is OLMoE's geometry
> in R6's unchanged layout, 67,108,864 B at width 256 — **2.29×** the dense arm's on a model with a
> fifth of the parameters, because sixteen KV heads beat twenty-eight layers. What it needs that does
> not exist: an `OP_CONCAT` and a `WHEN_DECODE` condition in `src/layer_olmoe.align`, whose
> `mm_row_issued` has three axes and no decode one, and a decode phase-A table — **`WHEN_WIDE` cannot
> be reused, because `ggml_pad` writes the source at index 0 and a decode step's new column belongs
> at `n_past`.** `MAX_PREFILL_TOKENS` moves **6 → 32** so the self-reference oracle can run at
> `T + k` tokens; `R5_ORACLE_TRUNCATED` is byte-unchanged and still refuses a prefill above six
> tokens *with* a transcript. **No new ggml op, FFI symbol, or shim body**; both shims and
> `src/decode_step.align` are byte-unchanged, and the dense arm's `R6_ARCH_UNSUPPORTED` refusal keeps
> its meaning and gains a documented answer. Acceptance is stated once in `r6-olmoe-decode.md`
> section 4.6: **gate G**, the `N` ids equal llama.cpp's, over a vocabulary whose fingerprint
> collision classes are measured before the gate is claimed; **oracle R**, routing identity `MATCH`
> at every step over 2,048 of 2,048 ids; **oracle B**, the plane round trip `IDENTICAL` at every step
> including the column that step wrote; **oracle C′** at `k ∈ {1, ⌈N/2⌉, N}` on a branch a
> pre-implementation probe selects; and **oracle T**, structurally complete at every step and
> numerically admitted at step 1 only. Owner `gmake layer-forward-smoke`, whose **seventh** block
> gains a routed decode loop over the synthetic two-layer MoE model; focused
> `gmake moe-decode-step-qualification`. **No TTFT or throughput claim and no cost ceiling** — the
> claim is a byte demand and the byte counters are exact. **What it leaves open:** the R6 gate still
> asks that TTFT improve on repeated coding tasks *sharing a prefix*. A routed decode loop that
> streams its weights and shares no prefix does not answer it; the gate stays unmet, and the next
> capability toward it is resident dense weights with streamed experts, whose input is this
> capability's per-step demand stream.

### 10.2 `HANDOFF.md` — the active block

> ## Active: R6-OLMOE-DECODE (2026-08-29)
>
> Branch `agent/r6-olmoe-decode`, stacked on `agent/r6-resident-weights` head `6facd56`, which is
> publishing. This branch takes `git merge origin/main` — **never a rebase** — when that lands, and
> re-checks the same four things: roadmap item **32** (30 is RESIDENT-WEIGHTS, 31 is claimed by
> `agent/c4-repair-measured`), the new document kind `R6_MOE_DECODE_STEP` at schema **1** (which
> collides with nothing, because it is a new kind), the next free Align request number (**52**; this
> capability takes none), and which goldens regenerate.
>
> **Capability.** `N` greedy decode steps on OLMoE-1B-7B-0125-Instruct Q4_K_M over an Align-owned KV
> plane, each step resolving its own top-8 expert claims per layer and computing only those experts,
> weights streamed. CPU only. Authoritative ledger `docs/specs/r6-olmoe-decode.md`. Three of the four
> design-gate triggers fire, including — for the first time in this wave — the coordinated-invariant
> one.
>
> **State.** Design complete and **committed before implementation**, which is the process correction
> `R6-RESIDENT-WEIGHTS` recorded that its successor owes. Not implemented.
>
> **Next actions, in order.** (1) Cell **G-P1**, section 5.7: run
> `scripts/decode_step_fingerprint.py` on the OLMoE GGUF and record the collision classes — if a
> class holds non-all-zero rows, gate G2 narrows and G3 is the declared response. (2) Cell **C-P1**:
> settle whether `mul_mat_id` over an 8-plane stack and over a `U`-plane stack agree bit for bit, which
> selects oracle C′'s branch. (3) `src/layer_olmoe.align`: `OP_CONCAT`, `WHEN_DECODE`,
> `mm_decode_a_node_table`, the two plane slots at the top of the slot map with the ceiling tightened
> to `n_expert_used <= 31`, and `MAX_PREFILL_TOKENS 6 -> 32`. (4) `src/moe_decode_step.align`: the
> arm, the loop, the write-back rows **derived by reading the new table**, and the per-step claim
> accounting of section 3.11. (5) The fixture's routed decode corpus, the seventh smoke block, and
> `scripts/run-moe-decode-step`.
>
> **Blockers.** None. Four Align gaps are met and all four are already recorded with named clients
> (Requests 33, 36, 47, 48, 49); none blocks, and Request 49 gains its largest client.
>
> **Constraints.** CPU only; streamed weights, **by design and not by cost** — residency would make
> the primary metric zero. No TTFT, throughput, or performance claim, and no cost ceiling: this
> capability makes a measurement claim and `docs/specs/r6-resident-weights.md` section 3.4 remains the
> owner of Track B decode performance.
>
> **Intentional uncommitted files.** None.

### 10.3 `docs/align-development.md` — a new arm section

A new `## `-level section immediately after
`## The `--decode-step` arm (R6-DECODE-KV-STEP1, R6-STEP-N, R6-KV-PERSIST, R6-RESIDENT-WEIGHTS)`,
in the shape of the `--moe-model-forward` section at line 1929.

> ## The `--moe-decode-step` arm (R6-OLMOE-DECODE)
>
> `docs/specs/r6-olmoe-decode.md` is the authoritative ledger. It ships as a **seventh arm of the
> existing `ggml-spike` executable**, `--moe-decode-step`, beside R4.5's positional arm,
> `--layer-forward`, `--model-forward`/`--model-forward-gpu`, `--moe-layer-forward`,
> `--moe-model-forward`, and `--decode-step`. It reuses `src/layer_olmoe.align` — R5D's and R5E's
> topology module, extended with a decode condition and a decode phase-A table — rather than adding a
> second OLMoE description, and it reuses R6's KV plane layout unchanged.
>
> ```sh
> gmake ggml-spike                       # unchanged; also builds the --moe-decode-step arm
> gmake layer-forward-smoke              # extended with a seventh block; unchanged aggregate membership
> gmake moe-decode-step-qualification    # the opt-in real-ggml, real-model, two-instrument qualification
> ```
>
> `--moe-decode-step` is selected by its exact first operand and takes five, six, seven, nine, ten, or
> eleven operands. **Eight is `R6M_ARITY`**, for `--decode-step`'s own reason — a transcript without a
> width refuses itself — and twelve and above are `R6M_ARITY`, with positions 11, 12, and 13 reserved
> for `KV_SAVE`, `KV_LOAD`, and `RESIDENT` at the same indices the dense arm uses.
>
> ```sh
> ./ggml-spike --moe-decode-step PACK GEOM.json TOKENS
> ./ggml-spike --moe-decode-step PACK GEOM.json TOKENS DOC.json
> ./ggml-spike --moe-decode-step PACK GEOM.json TOKENS DOC.json REF.gguf
> ./ggml-spike --moe-decode-step PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH
> ./ggml-spike --moe-decode-step PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin
> ./ggml-spike --moe-decode-step PACK GEOM.json TOKENS DOC.json REF.gguf -              KV_WIDTH LOGITS.bin STEPS
> ```
>
> **The operand shape is `--decode-step`'s, position for position**, so the two decode runners build
> their argument vectors the same way and a command line cannot be silently reordered between them.
> `KV_WIDTH` is fail-closed with no default in both. `STEPS` is `1 .. MAX_DECODE_STEPS` (64) with
> `T + N <= KV_WIDTH`; absent means 1, and `decode.steps_requested` is published in every document so
> the count is never implicit. `-` is legal in the document, transcript, and logits positions only.
>
> **Weights are streamed and there is no `RESIDENT` operand**, because R6-RESIDENT-WEIGHTS makes a
> decode step read zero pack bytes and this arm exists to measure the bytes a decode step reads.
>
> **What it publishes that no other arm does:** per step, `routed.layers[]` — the eight expert ids
> claimed in each of the sixteen layers — with the cumulative union and the marginal new bytes, and
> `residency.expert_bytes` beside `residency.expert_pread_bytes` so the arithmetic claim and the
> reader's own accounting are two numbers rather than one. On this model a step claims exactly
> `487,587,840` expert bytes, 125,000 ppm, on every step of every prompt.
>
> **Env vars, read by `scripts/run-moe-decode-step`:** `ALIGN_LLM_GGML_INCLUDE`,
> `ALIGN_LLM_GGML_LIB`, `ALIGN_LLM_GGUF_MODEL` (an **olmoe** GGUF), `ALIGN_LLM_LLAMA_EVAL_CALLBACK`
> (**R2C-patched** — full router axes are required, and an unpatched instrument prints six of eight
> slots), `ALIGN_LLM_LLAMA_DEBUG`, `ALIGN_LLM_MOE_DECODE_STEP_TMPDIR`, `ALIGN_LLM_DECODE_STEPS`.
> `numpy` is required for gate G's fingerprint measurement.
>
> **`src/layer_olmoe.align`'s `MAX_PREFILL_TOKENS` moves 6 → 32**, matching `src/layer_qwen2.align`,
> because the self-reference oracle runs `--moe-model-forward` at `T + k` tokens. That widens
> `--moe-layer-forward` and `--moe-model-forward` too; `R5_ORACLE_TRUNCATED` is byte-unchanged and
> still refuses a prefill above six tokens **with** a transcript, so the range 7..32 is open for
> arithmetic and closed for comparison.
>
> `--decode-step` still refuses an OLMoE geometry with `R6_ARCH_UNSUPPORTED` detail `n_expert`, and
> that refusal now has an answer: use `--moe-decode-step`.

### 10.4 `docs/align-requests.md`

Requests **33, 36, 47, 48, and 49** gain `src/moe_decode_step.align` and
`gmake moe-decode-step-qualification` as clients; **Request 49's** `align-llm verification` block
additionally records that a third module now duplicates its nine-function sink, and that its
acceptance criterion becomes `gmake layer-forward-smoke` passing with **seven** goldens byte-unchanged.
**No status changes and no new request.**

### 10.5 One naming ambiguity, resolved here rather than propagated

`scripts/run-layer-forward-smoke` contains **six** blocks; `docs/specs/roadmap.md` items 27 to 30 and
`docs/align-development.md` all describe the `--decode-step` block as "a fifth block", which it is
not — R5E's is the fifth and `--decode-step`'s is the sixth. `HANDOFF.md` says "all six blocks" and is
correct. **This capability's block is the seventh and is called the seventh**, and section 10.1's
roadmap draft says so. The four existing mis-numberings are not corrected here: they are in merged
prose about capabilities this one does not touch, and rewriting them would put unrelated churn in this
diff. The discrepancy is recorded so the next reader does not add an eighth "fifth block".

## 11. Author consistency pass

One pass, ledger against prose, performed before this document was finished. What it found:

1. **The brief asked for a `pread`-counter expert-byte metric "as RW does". R5E's counter is
   arithmetic, not a `pread` counter.** Section 3.11 was rewritten to publish both and to require a
   bounded relation between them, because a single arithmetic figure cannot distinguish an arm that
   read eight planes from one that read sixty-four and computed eight.
2. **Section 1.1 originally claimed the cross-step union had never been measured.** R3 section 8
   simulates decode residency over 40 prompts × 16 steps, and R2D's 447 per mille *is* a cross-step
   quantity. Section 1.1 now states exactly what this capability adds over both, section 2.3 credits
   R3 section 8.1 with the 487,587,840 figure, and section 2.5 separates three reuse numbers that a
   reader would otherwise merge.
3. **Section 2.5 originally asserted R2D's 447 is a within-graph number.** It is not; the *R2A parser
   field* of the same name is. Two aggregators, two definitions, one corrected paragraph.
4. **The plane size was computed wrong on the first pass** — 268,435,456 B instead of 67,108,864 B,
   an order-of-magnitude slip that would have made a false claim about `MAX_KV_PLANE_BYTES`. Corrected
   against `plane_bytes_for`'s own formula and cross-checked against the dense arm's published
   29,360,128 B, which the same formula reproduces exactly.
5. **`WHEN_WIDE` was initially assumed reusable for the KV concatenation.** It is a zero-pad that
   writes the source at index 0. Section 3.7 now names it as the largest structural gap and section 7
   risk 4 makes it a named prior failure class before it can become one.
6. **The slot pair could not go just above R5E's high water of 80** without colliding with phase B at
   `n_expert_used >= 13`. Section 3.7 moves it to the top of the map and tightens the geometry ceiling
   by two, with a case.
7. **Oracle C′ was written as acceptance by inheritance.** The reason it holds on the dense arm — one
   kernel for both paths — does not carry to two `mul_mat_id` calls over differently sized stacks.
   Section 4.4 now fixes both branches in advance and cell C-P1 selects between them.
8. **The roadmap item number is 32 only because item 31 is claimed on another branch**, and the
   register's next free request number is 52, not 50. Both are stated with their re-check rule rather
   than asserted.

## 12. Result

Status: **implemented and measured, 2026-08-29.** Sections 1 to 11 are the pre-implementation design
and are kept verbatim, so every prediction below can be read against what it predicted. Section 13
records every deviation; section 14 maps the ledger and the closure matrix onto the diff.

### 12.1 The qualification of record

`gmake moe-decode-step-qualification`, four prompts × `N = 16` steps × three consecutive runs, on the
reference host (Apple M1, 16 GiB), `KV_WIDTH` 256, weights streamed, CPU only, **re-run at the final
tree**. **Exit 0.**

```text
moe decode step qualification: 4 prompt(s) x 16 steps PASS -- gate G, oracle R at 8192 of 8192 ids,
oracle B, oracle T, and the claim accounting
real 3m18.256s
```

Section 4.6's acceptance rule, clause by clause:

| Clause | Required | Measured |
| --- | --- | --- |
| 1, gate G | `N` ids equal llama.cpp's, over a measured vocabulary | **64 ids** over four prompts; G1 `IDENTICAL` and `byte_identical: true` on every prompt; no decoded id in a collision class |
| 2, oracle R | `MATCH`, `ids_total == ids_printed_compared == 128N` | **`MATCH`, 2,048 of 2,048 per prompt, 8,192 of 8,192 in all**, `steps_compared` 16, `layers_matched` 256 |
| 3, oracle B | `IDENTICAL` over a positive byte count | **`IDENTICAL`**, 60,817,408 / 48,234,496 / 44,040,192 / 48,234,496 B |
| 4, oracle C′ | the branch cell C-P1 selects | **characterization** — 1 of 12 checkpoints byte-identical, **12 of 12 argmax-equal** (section 12.4) |
| 5, oracle T structural | every assertion of section 4.5, per step | **227 nodes and 16 layers matched at every one of 64 steps**, `instrument_kv_width` 256, tolerance 1 |
| 6, oracle T numeric at step 1 | `PASS`, or `FAIL` under R6's admission rule | **`PASS`, `max_abs_diff` 0** |
| 7, claim accounting | `expert_bytes == 487,587,840`, `keys_demanded == 128`, `claim_planes_read == 384`, and the `pread` relation | **all four, on every one of the 64 steps** |
| 8, determinism | three consecutive runs byte-identical after `normalize` | **held on all four prompts** |
| 9, `N + 1` graphs | the transcript holds exactly 17 | **held on all four prompts** |

### 12.2 Cell G-P1 — measured, and it is the case section 4.2 wrote in advance

```text
50,304 rows of Q4_K, 50,057 distinct fingerprints, 2 collision classes covering 249 ids,
2 of them not all-zero: {45382, 50278}
```

The first class is the 247 all-zero unused rows, exactly as on the dense table. The second is a
**two-member class of real rows**, which is the case R6-STEP-N did not meet and section 4.2 decided
in advance: the gate is not claimed over `45382` or `50278`, the runner refuses per step if any
decoded id is a member, and **no decoded id of the four prompts is**. G3 stays deferred.

One corroboration worth recording because it was not required: adding the printed `sum` to the key
raises the count to 50,058 distinct and **one** collision class — the sum separates `45382` from
`50278`. Section 4.2 does not gate on the sum for R6-STEP-N's reason and this does not change that;
it is reported so a future capability that needs those two ids knows the cheapest way to get them.

### 12.3 The demand stream — the deliverable

`step_expert_bytes` is **487,587,840 B on every one of the 64 steps**, `expert_bytes_ppm` exactly
**125,000**, `keys_demanded` exactly **128**, and `claim_planes_read` exactly **384** — prompt- and
step-independent, as section 2.3 derived. And the second measurement, which is the one section 3.11
added because the first is arithmetic:

> **`expert_pread_bytes` is 487,587,840 B on every step too. The read amplification is 0 ppm.**

The pack reader read exactly the bytes the routing decision claimed and **not one byte more**, on
64 steps. Section 3.11 predicted "487,587,840 plus a bounded chunk remainder" and reserved
`expert_bytes + claim_planes · block_align` for it; the remainder is **zero**, because
`read_block_scatter` reads one `ExpertBlock` image and intersects each chunk with the three claim
spans, and on this container the three claims tile the block exactly. That is the capability's
primary claim in its strongest available form: the arm computed only what it claimed, and the
arithmetic and the syscall accounting agree to the byte.

| prompt | tokens | first four ids | oracle R | step bytes (arith) | step bytes (`pread`) | ampl ppm | union keys | union bytes | mean marginal | demands in prefill union | distinct keys in prefill union | step reuse ppm | elapsed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 `def add(a, b` | 1545,823,9,66,13,270 | 2262,187,50274,2309 | 2048/2048 | 487,587,840 | 487,587,840 | 0 | 585 | 2,227,617,792 | 57.9 MB | 1540/2048 (75.2 %) | 273/515 (53.0 %) | 748 | 3.63 s |
| 2 `The capital of` | 510,5347,273 | 253,4687,273,11011 | 2048/2048 | 487,587,840 | 487,587,840 | 0 | 698 | 2,658,336,768 | 92.3 MB | 1064/2048 (52.0 %) | 240/627 (38.3 %) | 693 | 3.39 s |
| 3 `import os` | 2948,7684 | 187,2948,11876,187 | 2048/2048 | 487,587,840 | 487,587,840 | 0 | 614 | 2,338,897,920 | 95.4 MB | 1154/2048 (56.3 %) | 173/573 (30.2 %) | 720 | 3.26 s |
| 4 `return x +` | 2309,1269,559 | 340,187,187,4 | 2048/2048 | 487,587,840 | 487,587,840 | 0 | 607 | 2,309,259,264 | 83.1 MB | 1182/2048 (57.7 %) | 212/561 (37.8 %) | 726 | 3.06 s |

The union curve, in distinct `(layer, expert)` keys of 1,024, starting at the **prefill's** set:

```text
prompt 1  370 390 395 413 423 432 440 447 452 461 496 539 577 579 583 585
prompt 2  357 411 428 462 506 534 572 602 621 640 647 668 684 691 696 698
prompt 3  257 290 316 328 336 352 408 445 492 537 568 576 584 590 601 614
prompt 4  295 331 349 361 412 461 500 536 554 569 575 583 589 596 604 607
```

and the marginal bytes each step added, in the same order:

```text
prompt 1  105.3 77.8 18.8 69.1 38.1 35.6 30.5 26.9 19.9 34.6 132.5 162.4 143.1  7.6 15.8  8.2  MB
prompt 2  175.8 206.2 66.7 129.0 166.0 109.4 143.1 114.8 73.2 71.6 27.5 78.1 60.4 28.0 19.3  7.6 MB
prompt 3  165.2 126.5 100.7 47.3 31.0 60.4 212.8 142.3 179.3 171.1 117.3 29.4 29.9 22.9 41.6 48.7 MB
prompt 4  141.8 138.2 70.2 46.3 193.5 184.2 147.8 137.1 68.6 58.0 22.9 31.0 22.9 25.3 31.0 11.2 MB
```

**Three findings, and two of them correct a number section 2.4 published from a four-step probe.**

1. **The streamed-to-marginal gap is 5.1× to 8.4× at sixteen steps, not 9.2×.** Section 2.4 measured
   a mean marginal cost of 53.0 MB over the *first four* steps of prompt 1 and reported a 9.2× gap.
   Over sixteen steps the same prompt's mean is 57.9 MB — a **8.4×** gap — and the other three
   prompts are 92.3, 95.4 and 83.1 MB, or **5.3×, 5.1× and 5.9×**. The four-step figure was the most
   favourable window and this document said the sixteen-step number was the measurement; it is, and
   it is smaller. **The case for a decode-side residency policy survives at 5.1× and is weaker than
   the probe suggested**, which is exactly why the probe was not the deliverable.
2. **"Roughly four fifths of every decode demand is already in the prefill's union" is a
   short-window artifact — and the two fractions that sentence can mean are far apart.** Section 2.4
   reading 2 measured 79.9 % and 75.2 % over three and four steps as a fraction of **distinct**
   decode keys (219 of 274, 152 of 202), and the arm's `decode_keys_in_prefill_union` counts
   **demands with repetition**. Deviation 14 records that the denominator changed; both are now
   published and each is compared against the prediction it belongs to.
   Over sixteen steps the demand-weighted figure is **75.2 %, 52.0 %, 56.3 % and 57.7 %**, and the
   distinct-key figure the probe actually predicted is **53.0 %, 38.3 %, 30.2 % and 37.8 %** — 273 of
   515, 240 of 627, 173 of 573 and 212 of 561. **The distinct-key form is the one that collapses.**
   A probe reading of 79.9 % becomes 53.0 % on the same prompt at sixteen steps, and 30.2 % at worst:
   the prefill's working set is not a large fraction of the decode's distinct demand at all, and the
   demand-weighted figure stays higher only because the keys the prefill *does* hold are the ones
   demanded repeatedly. Both readings matter to a residency policy and they say different things —
   a cache sized to the prefill's set serves between half and three quarters of decode **demands**,
   while the decode's *distinct* set is **1.9× to 3.3×** the part of it the prefill already holds
   (515/273, 627/240, 573/173, 561/212).
3. **The union curve is not smooth and its shape is the finding.** Prompt 1 adds 20, 5 and 18 keys
   in steps **2 to 4** — the curve's first entry is the union *after* step 1, so a delta between
   entries `i` and `i+1` is step `i+1`'s — and then 35, 43 and 38 in steps 11 to 13; prompt 3 adds 8 in step 5 and 56 in
   step 7. A residency policy sized against the early steps of a prompt will be resized by the
   middle of it, and this is the first per-prompt curve in the repository that shows it.

`residency.step_reuse_per_mille` — section 3.11's new metric, `(demands − distinct) / demands` over
decode steps only, with `distinct` the decode steps' **own** key set — is **748, 693, 720 and 726**,
over 515, 627, 573 and 561 distinct keys of 2,048 demands. Section 2.5 separates this from R2D's 447
and from the adjacent-pair figures by name, and the separation is worth having, but the size of the
separation is **not** what this document first published. **The earlier figures — 881, 811, 804 and
829 — were a different quantity**, `(demands − |decode keys the prefill did not hold|) / demands`,
which is prefill-relative reuse and not section 3.11's; deviation 13 records the correction and the
absent check that let it ship.

**The re-derived comparison, stated as what it is.** The union quantity over sixteen steps is
**1.55× to 1.67×** R2D's pooled adjacent-pair 447 — not "roughly twice", which was an artifact of the
substituted definition. It is also **at or just above** the *first* adjacent-pair transition section
2.4 reading 3 measured on one prompt (695), and well above the third (484). So the honest statement
is the narrower one: **a union window over sixteen steps captures about half again as much reuse as
an adjacent-pair window captures on average, and about as much as an adjacent-pair window captures at
its best — the first transition.** That is still a real difference and it is still a reason to name
the three quantities separately, but it is a weaker claim than the one this section made, and it is
weaker because the number it rested on was the wrong number.

### 12.4 Cell C-P1 and oracle C′ — the branch the measurement selected

Section 4.4 wrote both branches in advance and refused to guess. The measurement, over twelve
checkpoints (`k ∈ {1, 8, 16}` on four prompts):

| Outcome | Count |
| --- | --- |
| `--moe-model-forward` at `T + k` reproduces `steps[k].sha256` **byte for byte** | **1** of 12 (prompt 3, `k = 1`) |
| the two agree on the **argmax** | **12** of 12 |
| `max_abs_diff` over the compared indices is within the pre-committed 5000 ten-thousandths | **12** of 12 (range **0 to 3,678**) |
| the two agree on the top ten **as a set** | **7** of 12 |
| `oracle_self[k].verdict` | 1 `IDENTICAL`, 6 `WITHIN`, 5 `FAIL` |

Per checkpoint, because the pattern is not a function of `k` alone:

| prompt | `k = 1` | `k = ⌈N/2⌉ = 8` | `k = N = 16` |
| --- | --- | --- | --- |
| 1 `def add(a, b` | `WITHIN`, max_abs 1,224 | `FAIL`, set ✗, max_abs 984 | `FAIL`, set ✗, max_abs 2,541 |
| 2 `The capital of` | `WITHIN`, max_abs 1,861 | `FAIL`, set ✗, max_abs 2,389 | `WITHIN`, max_abs 3,678 |
| 3 `import os` | **`IDENTICAL`**, max_abs 0 | `FAIL`, set ✗, max_abs 943 | `WITHIN`, max_abs 2,594 |
| 4 `return x +` | `WITHIN`, max_abs 2,063 | `WITHIN`, max_abs 1,636 | `FAIL`, set ✗, max_abs 1,128 |

**Every `FAIL` is a top-ten *set* disagreement and nothing else.** The argmax agrees at all twelve
and the bound holds at all twelve; in each failing case exactly one member of the two top-tens
differs, which is why the union of the two sets is 11 indices rather than 10. Section 4.4's
non-identical branch had already moved the acceptance weight "entirely to gate G, oracle R, and
oracle B", so the shipped rule reports the verdict and gates on **argmax alone** — deviation 15
records that a first draft of the repair gated on the whole triple and refused this run, and that
refusal is what produced this table.

**The bound was pre-committed and it held; the set clause was pre-committed and it did not.** Both
are recorded, because a bound that passes is evidence only when the clause beside it was allowed to
fail.

**`mul_mat_id` is not stack-shape invariant, and section 4.4's second branch is the live one.** A
decode step builds a stack of exactly eight planes and a `compact_ids` tensor over `[0, 8)`; the
self-reference prefill at `T + k` builds a stack of `U_L` planes and a `compact_ids` tensor over
`[0, U_L)`, and the same eight experts reached through a differently sized stack do not produce
bit-identical output. The one byte-identical checkpoint is the case where the two stacks coincide.

Oracle C′ is therefore **characterization**, reported at all three checkpoints, and the acceptance
weight sits entirely on gate G, oracle R, oracle B and oracle T — none of which depends on it. What
C′ still asserts unconditionally, and what the runner fails on, is **argmax equality**: a
self-reference that disagreed about the token would mean the decode loop and the prefill compute
different models, which no tolerance excuses. Twelve of twelve agree.

### 12.5 Cost, against section 6.4's estimate

| Item | Estimated | Measured |
| --- | --- | --- |
| One `N = 16` arm run | ≈ 8 s | **2.7 – 3.7 s** warm at the repair head; 4.3 – 8.6 s at the implementation head, cold |
| Four prompts × three determinism runs | ≈ 100 s | **≈ 81 s** |
| Oracle C′, 12 whole prefills | ≈ 25 s | **≈ 30 s** |
| Instrument captures at `-n 16` | ≈ 160 s | **≈ 70 s** |
| Cell G-P1 | ≈ 15 s | **≈ 1 s** |
| Packing, geometry, shim build | ≈ 45 s | **≈ 25 s** |
| **Total** | **≈ 6–8 min** | **3 min 18 s cold, 1 min 23 s warm** — and at the repair head **1 min 23.4 s** warm, **5 min 41.3 s** with the page cache evicted by a concurrent build on the same host |

The estimate was conservative by roughly a factor of two on a cold page cache and by a factor of
five on a warm one, and the transcript capture was its largest error. **The spread is the page
cache and nothing else**: the same tree gives 1 min 23 s and 5 min 41 s depending on whether the
4.2 GB pack is resident, and every correctness value is identical across all three runs. That is
why the wall clock is a diagnostic here and no cost ceiling is recorded. `window.claim_decode_peak_use_bytes` is **32,636,928 B**, exactly the figure section 3.6
derived, and per-step `total_bytes` is **740,666,496 B**, exactly section 3.9's prediction. These
figures are **diagnostics**: no performance claim is made and no cost ceiling is recorded.

**The repair head's run reproduces every correctness value exactly.** The same 64 ids, the same
oracle R `MATCH` at 8,192 of 8,192, the same `expert_bytes` and `expert_pread_bytes` on all 64 steps,
the same four union curves and marginal-byte sequences, the same twelve C′ verdicts — only the
timings move and the three residency fields the repair added or corrected appear. That is what makes
the re-recorded numbers in section 12.3 a *correction of the metric* and not a different measurement
of a different thing.

### 12.6 The hosted owner

`gmake layer-forward-smoke`, all **seven** blocks, **80 s** total on the reference host at the repair
head. The seventh block: 13 no-document cases, **59 documented cases** — the two the deviation-16
repair adds — 8 of the **12** declared `R6M_*` codes reached plus 20 inherited codes, gate G against
the reference loop's own ids, oracle R `MATCH` element-wise complete at 18 of 18 ids over three
steps, oracle B `IDENTICAL` over 1,920 cumulative bytes, oracle T `PASS` against transcript graphs 2
to 4, and `arm-r5e-unchanged`, `arm-r6-unchanged` and the dense arm's OLMoE refusal all `PASS`.

**Risk 8 is answered with the measurement rather than in advance.** The whole seven-block runner is
**80 s** (1 min 19.9 s) at the repair head against **57 s** at the implementation head — the two new cases and their
corpus are the difference — and both were measured on this same host, so the comparison is a
comparison and not two numbers from two machines. The design quoted 2 min 32 s for **six** blocks,
and that figure was taken on another head and is not comparable to either; it is quoted here only as
the estimate the two measurements beat. **The dense/routed split R5E pre-committed is not taken**,
and the reason is the number: seven blocks with the new cases still cost less than the design's six.

### 12.7 The mutants

Four source mutations, each applied to `src/moe_decode_step.align` alone, scored against
`gmake layer-forward-smoke`'s seventh block, and reverted. Every one dies, and — after one repair to
the block, recorded below — every one dies **by name**:

| Mutant | What it breaks | Diagnosis |
| --- | --- | --- |
| the routing comparison reads transcript graph `k` instead of `k + 1` | oracle R and oracle T compare a step against the wrong graph | `R5_ORACLE_SHAPE step[1]layer[-1]node[embd]` — the prefill's `embd` is `{n_embd, T}` and a step's is `{n_embd, 1}`, so the shape check refuses before an element is compared |
| the compact expert stack is filled in descending slot order | `mul_mat_id` reads plane `u` at the wrong offset while every shape stays valid | `R5_SOURCE_DIVERGED layer[0]expert[1]role[ffn_gate_exps]` — oracle 1's claim comparison against the source GGUF catches the plane in the wrong slot |
| the plane is written from the row **before** the post-RoPE K | a numerically plausible plane, written from the wrong node | `R6M_PLANE_MISMATCH step[1]layer[0]tensor[k]col[3]` — oracle B names the column the step just wrote |
| the `pread` counter is not accumulated | the second of section 3.11's two measurements becomes a number nothing wrote | `R6M_CLAIM_ACCOUNTING step[1]bytes[9216]pread[0]` |

The last one also demonstrates that `R6M_CLAIM_ACCOUNTING` is reachable from a **defect** even though
it is unreachable from an **input**, which is the distinction the block's `UNREACHED_R6M_CODES` set
records.

**The comprehensive review's nine, re-injected at the repair head.** Each was applied alone by
file-level backup and restore — never by copying this linked worktree, whose `.git` pointer writes
through to the *shared* worktree administration directory — scored against
`gmake layer-forward-smoke`, and reverted. Eight die; the ninth is inert and is **not** a gap:

| Mutant | Result | Diagnosis |
| --- | --- | --- |
| top-8 → top-7 in the decode-local `decide` call | **dies** | `R5E_CARRY layer[0]input[length]` — `stage_carry_at` refuses the short `topk_image` before compute |
| the union not seeded from the prefill | **dies** | `md-oracle-full: step 1 routed.new_keys is 6, not the generator's 2` |
| the union key drops its layer term | **dies** | `md-oracle-full: step 1 routed.new_keys is 1, not the generator's 2` |
| `MM_V_ROW` 13 → 12 | **inert, and not a gap** | row 12 is the `MUL_MAT` producing `Vcur` and row 13 a `RESHAPE_3D` **view** over the same buffer: identical bytes, identical `slot_nbytes`. Every golden matched and oracle B stayed `IDENTICAL`, because the plane received the same data. Nothing is left unasserted |
| `MM_V_ROW` 13 → 11 (post-RoPE K into the V plane) | **dies** | `R6M_PLANE_MISMATCH step[1]layer[0]tensor[v]col[3]` — oracle B names the tensor **and** the column |
| the claim stack filled in descending slot order | **dies** | `R5_SOURCE_DIVERGED layer[0]expert[1]role[ffn_gate_exps]` |
| **new:** axis 0 mapped through `axis_index` unconditionally — the pre-deviation-3 behaviour | **dies** | `md-used-eight: routing 'MISMATCH' at step 1 layer 0 token 0 slot 5`. The base corpus at `n_expert_used = 3` does **not** kill it, which is exactly why the case exists |
| **new:** axis 1 never mapped through `axis_index` | **dies** | `md-used-eight: oracle T 'FAIL' worst 'ffn_moe_up' max_abs 8726` — the marker's raising is pinned, on nodes the router never touched |
| **new:** `step_reuse_per_mille` restored to the prefill-relative quantity | **dies** | `md-oracle-full: residency.step_reuse_per_mille is 833, not the generator's 333`. This is the mutant the pre-repair corpus could not kill, because its oracle was the mutant |

**One repair the mutants earned.** On the first pass all four died through
`IndexError: list index out of range` in the block's own analysis, because that analysis indexes
`steps[0..2]` directly and a mutant makes the case produce no third step. A crash says a mutant was
caught and does not say what caught it. The block now has one guard, `require`, which reports the
case's status, error code and completed-step count and gives up cleanly; every diagnosis in the table
above is what it prints.

## 13. Deviations — what implementation found that the design did not predict

Eighteen, each with what the design said, what is true, and what was done. Rows 1 to 12 are the
implementation's own; rows 13 to 18 are the comprehensive review's, and each one is a *correction*
rather than a discovery — the design was right and the first implementation was not. Sections 1 to
11 are unedited except where a row below says otherwise, so every row can be read against its
prediction.

1. **`--moe-layer-forward` and `--moe-model-forward` did not ship `R5_ORACLE_TRUNCATED`, and the
   `MAX_PREFILL_TOKENS` lift would have opened a real hole.** Section 3.8 asserted that R5E ships
   that refusal, "raised when `transcript_present && tokens.count > TRUNCATION_PRINTED`, and that
   refusal is **byte-unchanged** and still fires at 7". It does not exist on either routed arm: only
   `src/layer_forward.align` has it, because with the cap at 6 the condition was unreachable and the
   guard had never been needed. Lifting the cap to 32 makes it reachable, so **the guard is added**
   to both arms, identically to the dense one, and `moe-tokens-33` / `mm-tokens-33` and
   `moe-tokens-seven-with-transcript` / `mm-tokens-seven-with-transcript` pin both halves. Without
   it, a seven-token routed prefill with a transcript would have compared six of seven rows and
   reported `PASS` about a row it never saw. This is the single most consequential thing the
   capability found.

2. **The R2C-patched instrument prints full router axes, and R5A's element-count rule refuses
   them.** Section 2.1 records `slots_truncated: false` as what the patch buys and section 4.3 builds
   oracle R's whole coverage claim on it — but `moe_layer_forward.scan_transcript`'s completeness
   rule is an equality against `printed_count`, which clamps every axis to six. The first real run
   was refused `R6M_ORACLE_MISSING step[1]layer[0]node[ffn_moe_topk]` **by the very instrument the
   design fixes**. The rule is now "the block is complete", with exactly two admissible readings —
   the clamped count or the full count — so a transcript that lost value blocks is still refused and
   a partially printed axis still is too.

3. **And the ordinal-to-index mapping refused them a second time, silently.**
   `moe_layer_forward.axis_index` maps printed ordinal 3 of an eight-long axis to **index 5**,
   because it assumes three leading and three trailing values. On a full row the ordinal *is* the
   index. Measured before the fix: **routing 96 of 256 ids matched with 32 of 32 block sums
   matched** — the shape a reader would misread as a routing defect when it is a scanner defect. The
   row now says which it is: a row carrying an ellipsis keeps R5A's mapping and a row without one
   maps directly. Both fixes are inert when the axis is at or below six, so **every R5D and R5E
   corpus is unaffected and both MoE goldens are byte-unchanged for this reason.**

4. **The arm, the transcript instrument and `llama-debug` must be one ggml build, and the pinned
   toolchain's is not the host's.** `scripts/llama-eval-callback-toolchain` builds the R2C instrument
   with `GGML_ACCELERATE=ON` and `GGML_BLAS=ON`; Homebrew's `llama.cpp` 0.2.0 — **the same commit,
   `bb4caa754`, build 10566** — ships a ggml without them. The two are two numeric worlds: the same
   prompt gives `result_output` sums of −113,284.835938 and −111,030.031250. An arm linked against
   Homebrew's ggml and compared against the pinned instrument reports oracle T `FAIL` with
   `max_abs_diff` 560,000 and routing `MISMATCH`, and neither is a defect in the arm. Section 6.2's
   instrument cross-check is what caught it, before the arm ran, and reported it as an instrument
   skew — which is the property that check exists for. The qualification of record links the arm
   against the pinned tree's own ggml and uses a `llama-debug` built from the pinned source with the
   pinned flags; in that one world gate G1 is `IDENTICAL`, oracle R is `MATCH` at 8,192 of 8,192, and
   oracle T is `PASS` with `max_abs_diff` **0**. Section 15 records what this owes the toolchain.

5. **The decode phase-A table is 37 rows as predicted, and that made the decode phase-B base move.**
   Section 3.7 predicted 37 rows at `MM_A_NODE_BASE` and left phase B at 56; 21 + 37 is 58, so those
   two ranges overlap at slots 56 and 57 and the store's "disjoint ranges" property would be lost.
   `MM_DECODE_B_NODE_BASE` is therefore **58**, for the decode tables only, and R5E's
   `MM_B_NODE_BASE` is byte-unchanged. The consequence is one value of the tightened ceiling:
   `n_expert_used <= 30` where section 3.7 predicted 31. `md-geometry-expert-used-31` and
   `md-geometry-expert-used-30` are the cases, and the second proves the admitting side reaches the
   container rather than the geometry.

6. **One pair of write-back rows serves both passes, where the dense arm needed four constants.**
   Section 3.4 said the row indices "must be re-derived by reading the OLMoE decode table". They
   were, and the answer is simpler than the dense arm's: `mm_a_row_head` is `T`-independent and is
   shared by both tables byte for byte, so `MM_K_ROW` (11) and `MM_V_ROW` (13) are the same rows in
   a prefill and in a step. Only oracle B's readback needed a second pair,
   `MM_DECODE_K_CONCAT_ROW` (17) and `MM_DECODE_V_CONCAT_ROW` (23).

7. **`scripts/ggml_shim_stub.c` is not byte-unchanged.** Section 5.5 predicted "both shims
   byte-unchanged". Three of R6's forced builds are keyed on a `layer_qwen2` **slot number** that is
   an ordinary weight slot in a routed graph, so the routed arm needs its own:
   `engine+decode-position-moe`, `engine+mask-offset-moe`, and `engine+writeback-offset-moe`. They
   are **separate builds** rather than second indices on the dense ones, so every dense build stays
   behaviourally byte-unchanged and `scripts/decode-step-golden.jsonl` is byte-unchanged.
   `engine+plane-stage-offset` and `engine+compute-step2` needed no counterpart: both key on the
   past-K slot, which is 64 on one arm and 126 on the other and is written by no other graph on
   either. `scripts/ggml_shim.c` and `src/ggml_ffi.align` **are** byte-unchanged, as predicted.

8. **A concatenation on the wrong axis does not reach oracle B on this architecture.** Section 5.2
   expected `md-force-concat-axis` to produce `R6M_PLANE_MISMATCH`. It produces `R5_SHAPE` at the
   node the mis-shaped operand feeds, which is a stronger refusal taken earlier, and the case
   records the code it actually raises.

9. **Oracle C′ demoted to characterization, which is risk 1 realized.** Section 12.4 has the
   measurement. The design wrote both branches and the acceptance rule lost one oracle and kept
   four, exactly as planned; this is a deviation from the *hope* and not from the *design*.

10. **Cell C-P1 was taken as the first C′ measurement rather than before implementation.** Section
    5.7 wanted it settled with `--moe-model-forward` alone, before the arm existed. No experiment
    with the shipped arms compares the same token through an 8-plane and a `U`-plane stack: a prefill
    computes its head for the **last** token only, so two prefills of different lengths never share
    the token whose logits could be compared. The question is answerable only by an arm that decodes,
    which is this one. Both branches were still written before implementation and the acceptance rule
    still reads whichever the measurement selected, so the property section 4.4 wanted — the branch
    is chosen by a measurement and not by a preference — holds; only its timing moved.

11. **The next free Align request number is 53, not 52.** Section 9 recorded 52 with its re-check
    rule; `agent/c4-repair-measured` filed 52 on its own branch while this one was being written, so
    the register's next free number is **53**. This capability still takes none: every construct it
    needs compiles against the shipped pin, and the five gaps it meets — Requests 33, 36, 47, 48 and
    49 — were all already recorded. Section 10's reconciliation drafts are kept **verbatim** and
    therefore still say 52. `docs/align-requests.md` **on this branch** ends at Request **51** — it
    does not yet carry 52, which lives on `agent/c4-repair-measured` — so "53" is a statement about
    the register *after* that branch merges and not about the file in this diff. The re-check rule
    stands: confirm the next free number against `main` at the publication head, because a parallel
    session may have filed another.

12. **The runner asserts gate G1 in the hosted lane differently from the real one.** The hosted
    block's reference logits blob is the generator's pure-Python forward, which agrees with the engine
    shim's C kernels at every printed decimal and not to the last bit — the same `verdict: FAIL` with
    `max_abs_diff: 0` that `--moe-model-forward`'s own `mm-logits` has carried since R5E. The hosted
    block therefore asserts the comparison ran over the whole vocabulary, that every element agrees,
    and that the argmax the id chain is rooted at is the reference's; byte identity is asserted on the
    real model, where both sides are llama.cpp's arithmetic, and it holds there.

13. **`residency.step_reuse_per_mille` shipped a prefill-relative quantity under section 3.11's
    name, and section 12.3 drew a conclusion from it.** Section 3.11 defines `distinct` as the
    distinct `(layer, expert)` keys the decode steps demanded, and section 2.4 reading 4 states it
    as `(512 − 274) / 512`, where 274 is the decode-only cumulative set. `decode_loop` computed
    `|seen_keys \ prefill_keys|` — the union keys the prefill did **not** already hold — and
    published `(demands − that) / demands`. On section 2.4's own probe the two are 465 and 892. The
    metric now accumulates a **second key set seeded empty** and grown only from the steps' `ids`,
    beside the prefill-seeded union that `union_keys_final` and the `new_bytes` curve come from, and
    publishes its cardinality as `residency.decode_keys_distinct`.
    **No check caught it, and that is the more important half of this row.**
    `scripts/layer_forward_fixture.py` reproduced `len(seen - prefill_keys)` verbatim, so the
    generator, the golden and the smoke's assertion all pinned the implementation to its own
    restatement: the oracle was co-derived with the subject. The generator now derives the decode
    key set **independently**, from `step_routings` alone, and the seventh smoke block asserts that
    the two quantities actually differ in the corpus — a metric whose regression cannot tell the
    wrong answer from the right one is not a regression. The hosted figure moved **833 → 333** and
    section 12.3's real-model figures are re-recorded.

14. **`residency.decode_keys_in_prefill_union` changed denominator between the design and the
    implementation, and section 12.3 compared across the change.** Section 2.4 reading 2 and section
    3.11 predicted a fraction of **distinct** decode keys — 219 of 274 and 152 of 202 — and
    `keys_in_prefill` counts **demands with repetition**, 1,540 of 2,048. Both are real quantities
    and neither substitutes for the other. The arm now publishes **both**:
    `decode_keys_in_prefill_union / decode_keys_demanded` is the demand-weighted one and
    `decode_distinct_keys_in_prefill_union / decode_keys_distinct` is the one the prediction was
    stated over. Section 12.3 finding 2 reports both and compares each against the prediction it
    belongs to.

15. **Oracle C′'s shipped fallback asserted argmax alone, where section 4.4 pre-committed three
    clauses.** Section 4.4 recorded, before implementation, that a non-identical C′ becomes
    characterization "with its `max_abs_diff` in ten-thousandths … R5E's own
    `LOGIT_TOLERANCE_TEN_THOUSANDTHS` of **5000**, plus argmax equality, plus top-10 set equality",
    and section 4.6 clause 4 restates it. `scripts/run-moe-decode-step` failed only on argmax. All
    three clauses are now asserted at all three checkpoints, and the per-step `top_k` array the
    comparison needs — `--moe-model-forward`'s own shape, from the same `top_k` arithmetic — is
    published in every `steps[]` row.
    **One clause is narrower than R5E's and it is named rather than absorbed:** R5E sweeps the whole
    vocabulary because it holds a reference **blob**; neither document here publishes a logit
    vector, so the bound is taken over the **union of the two top-10 index sets**, from the raw
    `u32` of each logit. Those are the elements that decide the token and the comparison over them
    is exact, but it is not the whole-vocabulary maximum and section 4.6 clause 4 now says so. The
    alternative — a twelfth operand on the decode arm writing a logits blob per step — is a public
    CLI change this capability did not pre-commit, and section 15 is where it belongs if a later
    consumer needs the wider bound.
    **And asserting the clauses at all changed the rule, which is the point of asserting them.**
    Top-10 **set** equality does **not** hold on this model: section 12.4 records the checkpoints
    and their numbers. Section 4.4's own non-identical branch had already moved the acceptance weight
    "entirely to gate G, oracle R, and oracle B", so C′ is exactly what that branch says it is —
    characterization — and section 4.6 clause 4 now **reports** the verdict with all three quantities
    while gating on **argmax alone**. Gating on a clause the design had already demoted would have
    failed the run for something no oracle here owns, which is the same mistake deviation 4 records
    about the instrument. The first draft of this repair did gate on it, and the run refused; that
    refusal is what produced the measurement in section 12.4.

16. **Deviation 3's `axis_index` fix covered one of four axes.** The repair gated axis 0 on the
    row's own `truncated` flag and left `axis_index(o1..o3)` unconditional. The R2C patch's print
    limit is `max(ne)` applied to **all four** axes (`common_debug_print_limit`), so a routed prefill
    at `T = 7` prints `ffn_moe_topk-L` as `{8, 7}` in full and `axis_index(o1, 7)` maps printed
    ordinals 3..6 onto indices 4..7 — 32 of 56 ids on the wrong token and one index past the extent.
    It was unreachable only because `R5_ORACLE_TRUNCATED`, added in this same capability, refuses
    `tokens.count > 6` whenever a transcript is present. `scan_transcript` now records a per-axis
    "ellipsis seen" marker at the block header and gates all four mappings symmetrically.
    **The hosted regression is at both ends of the boundary, and one half of it is honestly
    unreachable.** `md-used-six` and `md-used-eight` run the same pack at `n_expert_used` 6 and 8:
    six is the last width at which `axis_index` is the identity, eight is the first at which it is
    not, and the fixture now emulates the R2C print limit so the eight-wide `ffn_moe_topk-L` row
    arrives with no ellipsis. `md-used-eight` also has a **truncated** axis 1 on
    `ffn_moe_weights-L` and the three `MUL_MAT_ID` nodes, so it pins the marker as well as the gate.
    What is **not** hosted is the axis-1 *direct* branch: reaching it needs a routed prefill above
    six tokens with a transcript, which `R5_ORACLE_TRUNCATED` refuses from every operand. The branch
    is implemented and correct; the guard is what keeps it unreachable, and
    `moe-tokens-seven-with-transcript` / `-no-transcript` are what pin the guard.

17. **Section 3.4's QK-norm ordering was inverted.** It stated that OLMoE applies `attn_q_norm` and
    `attn_k_norm` "after the reshape to `{head_dim, n_head, T}` and before RoPE". The shipped table
    norms the 2-D projection **first** — `RMS_NORM` and `MUL` at rows 7 and 8, then the
    `RESHAPE_3D`, then `ROPE` (`src/layer_olmoe.align:1825-1845`). The conclusion the paragraph
    draws — that the K reaching the plane is post-norm and post-RoPE, so the plane needs no marker —
    is unaffected; the stated mechanism was wrong and the sentence is corrected.

18. **Request 49's duplication list was short and named a function that does not exist.** Section
    3.1 and section 9 recorded nine functions plus "a second copy of the plane-owning `refill`", and
    section 14 recorded 23. There is **no** duplicated `refill` — correctly, because KV persistence
    is out of scope and this plane is never refilled from a container — and the real count is **36**
    of the module's 91 functions, by the criterion "shares a name with a sibling module's function
    **and** takes a `borrow mut` parameter". A future collapse following the recorded list verbatim
    would have left thirteen copies behind. The list in `docs/align-requests.md` is now regenerated
    from the source rather than written by hand.

**Six smaller repairs from the same review, recorded here rather than as rows of their own:**
`layer_olmoe.mm_write_mask_offset` fails **closed** on a negative offset — it wrote the fully masked
image instead of returning with the buffer's zero bits in place, which is `0.0f` everywhere and
therefore *unmasked* everywhere, a confidently wrong answer every shape check accepts;
`R5E_CLAIM_OVERFLOW` breaks its per-role loop after `fail`, as every other loop in the file does; the
key arithmetic's assumption that a step's `ids` is exactly `n_layer * n_expert_used` long is now a
fail-closed `R6M_ROUTED_SHAPE` rather than a comment, because the layer term is recovered by
division and a short `routed[]` would mis-attribute every later key's layer **and** its per-layer
byte size; `scripts/run-layer-forward-smoke`'s warning-budget comment carries the measured
**179,363 B** (29,460 B of it from this module) against `MAX_STREAM_BYTES` 65,536, where it said
"~22 KB" and called two runners "two thirds of that budget"; section 6.4's "1800 s cap" is a
**budget**, since neither runner enforces a timeout; and the qualification's preflight now compares
the arm's `libggml-base` against `llama-debug`'s by resolved object identity, hard, while reporting
`llama-eval-callback`'s without enforcing it and saying on one line when it fails open. That last
repair found one more thing: `ALIGN_LLM_GGML_LIB` was on the **link** path and not the **loader**
path, so section 15's own recommended configuration — point it at the instrument's ggml, which lives
in a build directory on no default loader path — aborted the arm inside `dyld` before its first
instruction. It is now exported into `DYLD_LIBRARY_PATH` and `LD_LIBRARY_PATH` beside the shim
**and** recorded as an `-Wl,-rpath` in the real shim itself, because macOS strips `DYLD_*` from any
SIP-protected binary's environment and this runner launches the arm through `/usr/bin/time`. The
qualification of record is the first run taken in that one ggml world through an unmodified
`gmake moe-decode-step-qualification`; every earlier one needed the operator to arrange the loader
path by hand, which is how deviation 4 stayed a narrative instead of a reproducible command.

## 14. Ledger and closure matrix against the diff

Every applicable cell of sections 3 and 5, mapped to where it is implemented and what proves it.

| Ledger row (section 3) | In the diff | Evidence |
| --- | --- | --- |
| 3.1 a new arm, not a dispatch | `src/moe_decode_step.align`, one `import` and one `if` in `src/ggml_spike.align` | `md-arm-unknown-flag`; `arm-r5e-unchanged`, `arm-r6-unchanged`; `src/decode_step.align` byte-unchanged |
| 3.2 operands, arity, codes | `run` and `stage_inputs` | 13 `NO_DOCUMENT` cases incl. `md-arity-4/8/12`; `md-steps-*`, `md-kv-width-*`, `md-tokens-*` |
| 3.3 geometry | `layer_olmoe.parse_geometry` **byte-unchanged** | `md-geometry-arch`, `md-geometry-not-json`, `md-geometry-absent` |
| 3.4 the plane at OLMoE's geometry | `plane_stride`/`plane_bytes_for`/`stage_past_*`/`compare_past_*` | `plane.bytes` 67,108,864 measured; `md-plane` assertions in the seventh block |
| 3.5 what `T = 1` changes | `mm_decode_a_node_table`, `selection.narrow_layer/index` = −1 | seventh block asserts both −1; oracle R at `{8,1}` on all 16 layers |
| 3.6 the claim window at `T = 1` | `size_claim_window` unchanged, `claim_decode_peak_use_bytes` new | measured **32,636,928 B**, the predicted value |
| 3.7 the decode condition and table | `OP_CONCAT`, `WHEN_DECODE`, `mm_row_issued_at`, `mm_decode_a_node_table`, the slot map | `graph.table_rows_a_decode` **37** published and asserted; `md-force-mask-offset`, `md-force-decode-position` |
| 3.8 `MAX_PREFILL_TOKENS` 6 → 32 | `src/layer_olmoe.align`; every consumer audited | `moe-tokens-33`, `mm-tokens-33`, both `*-seven-with-transcript`, both `*-seven-no-transcript` |
| 3.9 streamed, no `RESIDENT` | no operand; `weights` object absent | per-step `total_bytes` **740,666,496** measured |
| 3.10 the document | `render*` in `src/moe_decode_step.align` | `scripts/moe-decode-step-golden.jsonl`, 57 rows, one shape at `N = 1` and `N = 3` |
| 3.11 metrics | `StepResidency`, `union_grow` **twice** — once prefill-seeded for the union curve and once empty-seeded for `decode_keys_distinct` — `R6M_CLAIM_ACCOUNTING`, `R6M_ROUTED_SHAPE` | section 12.3; amplification **0 ppm** on 64 steps. `step_reuse_per_mille`'s oracle is derived **independently** in `layer_forward_fixture.py` and the seventh block asserts that the corpus separates it from the prefill-relative quantity (deviation 13) |
| 3.11 both prefill-union fractions | `keys_in_prefill` (demands) and the distinct sweep in `decode_loop` | seventh block bounds each by its own denominator; section 12.3 finding 2 reports both (deviation 14) |
| 3.12 ownership and lifetime | one frame owns the plane and both windows | `lifetime.*_created == *_freed` and `graph_balance_failures == 0` on **every** case |
| 3.13 prerequisites | all met; **no new Align request** | section 9's five gaps, all pre-existing |

| Closure cell (section 5) | Implementation | Regression |
| --- | --- | --- |
| 5.1 formation / validation | `run`, `stage_inputs` | 13 no-document + 26 stub cases |
| 5.1 construction | `schedule_decode` | `md-engine-ok` (`N` absent ≡ 1), `md-steps-3` |
| 5.1 success | `prefill_pass` → `decode_loop` | `md-oracle-full`; the qualification at `N = 16` × 4 |
| 5.1 failure | every seam code, detail prefixed `step[<k>]` | `md-force-compute-step2` → `R5_COMPUTE step[2]` |
| 5.1 malformed / precedence | `R6M_STEPS` before `R6M_KV_WIDTH` | `md-steps-zero-and-narrow` |
| 5.1 early exit | rollback of the partial step's counts | `md-force-compute-step2` asserts all five; `md-transcript-short-for-steps` asserts them at step 3 |
| 5.1 cleanup | one frame, `buffer`s only | `lifetime` assertions on all 57 cases |
| 5.2 write-back rows derived | `MM_K_ROW`/`MM_V_ROW` read out of the table | `md-force-writeback-offset` → `R6M_PLANE_MISMATCH`; `md-force-plane-stage-offset` |
| 5.2 ordering invariant | upload → compute → write-back → verify | oracle B cumulative and inclusive of the new column, at every step |
| 5.3 the decode topology as data | `src/layer_olmoe.align` | `table_rows_a_decode` 37 asserted; `md-geometry-expert-used-31`/`-30` |
| 5.3 prefill tables byte-unchanged | no prefill row moved | both MoE goldens: **zero pre-existing rows changed in value** |
| 5.4 re-used by import | `decide`, `parse_tokens`, `stage_carry_at`, `stage_plan_owned`, the comparators' grammar | `moe-model-forward-golden.jsonl` unchanged except the three predicted rows |
| 5.4 duplicated for Request 49 | **36** functions, regenerated from the source and listed in `docs/align-requests.md`; the design predicted 23 and a duplicated `refill` that does not exist (deviation 16) | section 9 and Request 49's client block |
| 5.5 no new FFI symbol or shim body | `src/ggml_ffi.align`, `scripts/ggml_shim.c` byte-unchanged | the smoke's source scan. `scripts/build-ggml-shim` gains one `-Wl,-rpath` on the real shim's link line — a **link-line** change, not a shim-body change — so that `ALIGN_LLM_GGML_LIB` can be a build directory (section 13's closing paragraph, the sixth smaller repair) |
| 5.6 fixture, smoke, runner, goldens | `write_moe_decode_corpus`, the seventh block, `scripts/run-moe-decode-step` | section 12.6 |
| 5.7 G-P1, C-P1 | sections 12.2 and 12.4 | both taken, both branches written in advance |
| 4.4 / 4.6 clause 4 oracle C′'s fallback, all three clauses | `scripts/run-moe-decode-step`'s `self_rows`; per-step `top_k` in `render_step_row` | section 12.4's table; the seventh block asserts every step publishes ten distinct indices whose first is the step's `argmax` (deviation 15) |
| deviation 3 generalised to every axis | `marked1`/`marked2`/`marked3` in `moe_layer_forward.scan_transcript` | `md-used-eight` (axis 0 direct, axis 1 truncated) and `md-used-six` (inert at the boundary). The axis-1 **direct** branch has **no** hosted regression and deviation 16 says why: `R5_ORACLE_TRUNCATED` refuses it from every operand, and `moe-tokens-seven-with-transcript` / `-no-transcript` pin that guard |
| the key arithmetic's shape assumption | `R6M_ROUTED_SHAPE` in `decode_loop` | declared and listed **unreached**, with its reason: `stage_carry_at` refuses a short `topk_image` with `R5E_CARRY` before compute |
| the mask's negative-offset path | `layer_olmoe.mm_write_mask_offset` | fails **closed** (fully masked) rather than leaving an all-zero, therefore all-unmasked, buffer. Unreachable; no regression, and it is defence rather than a fix |

**Not implemented, and each is a deferral rather than a gap:** section 8's list is unchanged, and
`md-force-claim-into-plane` (section 5.2's aliasing case) is **not** shipped — the claim window and
the plane are two distinct `buffer`s with two distinct ggml wraps and no operand can make a claim
read address the plane, so the case would have had to be forced by a shim build that writes to a
slot the arm never hands it. `window.pointer_identity_failures == 0` over every placement of every
case is what covers the property instead, and it is asserted on all 57 rows.

## 15. What this owes the toolchain

Section 13 deviation 4 is not a defect in this capability and it is not fixed by it, so it is
recorded where the next reader will need it.

`scripts/llama-eval-callback-toolchain` materializes the R2C instrument with `GGML_BLAS=ON` and
`GGML_ACCELERATE=ON`. Every capability before this one used that instrument to **parse text** —
R2A's trace, R2D's locality gate, R3's simulator — where the build's arithmetic never had to agree
with anything the repository computes. This is the first capability to compare it **numerically**
against an Align-computed graph, and a numeric oracle requires one ggml build on both sides.

Two ways to make `gmake moe-decode-step-qualification` a one-command run on an ordinary host, neither
taken here:

* materialize the instrument with the host's own ggml configuration — a generation bump, because the
  instrument's digest changes; or
* have the toolchain publish the ggml headers and libraries it built, so `ALIGN_LLM_GGML_INCLUDE` and
  `ALIGN_LLM_GGML_LIB` can point at them and the arm links what the instrument runs.

The second is smaller and is the one this capability recommends. Until then the qualification's
preflight is what stands in the way of a false result: **the instrument cross-check compares the
transcript's `result_output` sum against `llama-debug`'s logits before the arm runs**, and it caught
exactly this, reported it as an instrument skew, and refused. That is the check working.
